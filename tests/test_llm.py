"""LLM layer tests. No network: fake, recorded and recording providers only."""

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict

from tracefix.llm import (
    BudgetExceeded,
    FakeProvider,
    LLMClient,
    LLMOutputError,
    LLMRequest,
    LLMResponse,
    Message,
    MissingRecording,
    RecordedProvider,
    RecordingProvider,
    strict_schema,
)


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int
    note: str


GOOD = {"value": 1, "note": "ok"}
ASK = [Message("user", "give me a number")]


def request(content: str = "hi") -> LLMRequest:
    return LLMRequest("reproducer", "m", "sys", (Message("user", content),), strict_schema(Answer))


def test_strict_schema_requires_every_property_and_forbids_extras() -> None:
    schema = strict_schema(Answer)
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["note", "value"]
    assert "title" not in json.dumps(schema)


def test_request_key_is_stable_and_content_sensitive() -> None:
    assert request().key() == request().key()
    assert request().key() != request("other").key()


def test_complete_parses_a_valid_answer_and_logs_the_call() -> None:
    client = LLMClient(FakeProvider([GOOD]))
    answer = client.complete("reproducer", "sys", ASK, Answer)
    assert answer == Answer(value=1, note="ok")
    assert len(client.calls) == 1 and client.calls[0].valid
    assert client.tokens_used == 150


def test_invalid_answer_is_retried_once_with_the_error() -> None:
    fake = FakeProvider(["not json", GOOD])
    client = LLMClient(fake)
    assert client.complete("reproducer", "sys", ASK, Answer).value == 1
    retry = fake.requests[1].messages
    assert retry[-2] == Message("assistant", "not json")
    assert "did not match the JSON schema" in retry[-1].content
    assert [c.valid for c in client.calls] == [False, True]


def test_two_invalid_answers_raise() -> None:
    client = LLMClient(FakeProvider([{"value": "x"}, {"value": 1}]))
    with pytest.raises(LLMOutputError):
        client.complete("reproducer", "sys", ASK, Answer)


def test_call_limit_is_enforced_before_sending() -> None:
    fake = FakeProvider([GOOD, GOOD])
    client = LLMClient(fake, max_calls=1)
    client.complete("reproducer", "sys", ASK, Answer)
    with pytest.raises(BudgetExceeded):
        client.complete("reproducer", "sys", ASK, Answer)
    assert len(fake.requests) == 1


def test_token_budget_is_enforced() -> None:
    client = LLMClient(FakeProvider([GOOD, GOOD]), token_budget=150)
    client.complete("reproducer", "sys", ASK, Answer)
    with pytest.raises(BudgetExceeded):
        client.complete("reproducer", "sys", ASK, Answer)


def test_refusal_is_an_output_error() -> None:
    class Refuses:
        def send(self, request: LLMRequest) -> LLMResponse:
            return LLMResponse("", 10, 0, "refusal")

    with pytest.raises(LLMOutputError, match="declined"):
        LLMClient(Refuses()).complete("reproducer", "sys", ASK, Answer)


def test_recording_then_replay_round_trips(tmp_path: Path) -> None:
    recorder = RecordingProvider(FakeProvider([GOOD]), tmp_path)
    live = recorder.send(request())
    replayed = RecordedProvider(tmp_path).send(request())
    assert replayed == live
    stored = next(tmp_path.iterdir()).read_text(encoding="utf-8")
    assert "sys" not in stored  # only the key and the response are stored, not the prompt


def test_missing_recording_never_falls_back_to_the_network(tmp_path: Path) -> None:
    with pytest.raises(MissingRecording, match="TRACEFIX_RECORD=1"):
        RecordedProvider(tmp_path).send(request())


def test_recording_for_a_different_request_is_rejected(tmp_path: Path) -> None:
    RecordingProvider(FakeProvider([GOOD]), tmp_path).send(request())
    path = next(tmp_path.iterdir())
    data = json.loads(path.read_text(encoding="utf-8"))
    data["key"] = "0" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(MissingRecording, match="another request"):
        RecordedProvider(tmp_path).send(request())


def test_api_errors_become_provider_errors_that_end_only_the_stage() -> None:
    import anthropic
    import httpx2

    from tracefix.llm import AnthropicProvider, LLMProviderError

    def create(**kwargs: object) -> object:
        raise anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x"))

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    with pytest.raises(LLMProviderError, match="APIConnectionError"):
        AnthropicProvider(client).send(request())


def test_cost_estimate_uses_list_prices() -> None:
    client = LLMClient(FakeProvider([GOOD]), models={"reproducer": "claude-sonnet-5-5"})  # type: ignore[dict-item]
    client.complete("reproducer", "sys", ASK, Answer)
    assert client.cost_usd == pytest.approx((100 * 2.00 + 50 * 10.00) / 1_000_000)
    unknown = LLMClient(FakeProvider([GOOD]), models={"reproducer": "some-model"})  # type: ignore[dict-item]
    unknown.complete("reproducer", "sys", ASK, Answer)
    assert unknown.cost_usd is None


# --- M8: settings, account problems and the provider ----------------------------------------------


def _api_request() -> object:
    import httpx2

    return httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _status_error(status: int) -> BaseException:
    import anthropic
    import httpx2

    response = httpx2.Response(status, request=_api_request())  # type: ignore[arg-type]
    by_status: dict[int, type[anthropic.APIStatusError]] = {
        400: anthropic.BadRequestError, 401: anthropic.AuthenticationError,
        403: anthropic.PermissionDeniedError, 404: anthropic.NotFoundError,
        429: anthropic.RateLimitError, 500: anthropic.InternalServerError,
    }  # fmt: skip
    error_class = by_status.get(status, anthropic.APIStatusError)
    return error_class(f"HTTP {status}", response=response, body=None)


def _raising(exc: BaseException) -> object:
    def create(**kwargs: object) -> object:
        raise exc

    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))


@pytest.mark.parametrize(
    ("status", "kind"),
    [(401, "auth"), (402, "billing"), (403, "permission"), (404, "model_unavailable"),
     (429, "rate_limit"), (500, "api_unavailable"), (529, "api_unavailable"),
     (400, "rejected"), (413, "rejected"), (422, "rejected")],
)  # fmt: skip
def test_each_api_status_is_classified_by_our_code(status: int, kind: str) -> None:
    from tracefix.llm import AnthropicProvider, LLMProviderError

    with pytest.raises(LLMProviderError) as caught:
        AnthropicProvider(_raising(_status_error(status))).send(request())
    assert (caught.value.kind, caught.value.status) == (kind, status)


def test_connection_errors_and_timeouts_are_network_problems() -> None:
    import anthropic

    from tracefix.llm import AnthropicProvider, LLMProviderError

    errors: list[BaseException] = [
        anthropic.APIConnectionError(request=_api_request()),  # type: ignore[arg-type]
        anthropic.APITimeoutError(request=_api_request()),  # type: ignore[arg-type]
    ]
    for exc in errors:
        with pytest.raises(LLMProviderError) as caught:
            AnthropicProvider(_raising(exc)).send(request())
        assert (caught.value.kind, caught.value.status) == ("network", None)


def test_a_problem_names_its_innermost_cause() -> None:
    """The SDK says only 'Connection error.' for any failure while reading an answer; the cause
    (here the decoding bug of xcdat-569, NOTES 41) must reach the receipt's words."""
    import anthropic

    from tracefix.llm import AnthropicProvider, LLMProviderError

    exc = anthropic.APIConnectionError(request=_api_request())  # type: ignore[arg-type]
    middle = RuntimeError("decoding failed")
    middle.__cause__ = TypeError("process() takes no keyword arguments")
    exc.__cause__ = middle
    with pytest.raises(LLMProviderError) as caught:
        AnthropicProvider(_raising(exc)).send(request())
    assert str(caught.value) == (
        "APIConnectionError: Connection error. "
        "(cause: TypeError: process() takes no keyword arguments)"
    )
    assert caught.value.kind == "network"
    plain = anthropic.APIConnectionError(request=_api_request())  # type: ignore[arg-type]
    with pytest.raises(LLMProviderError, match=r"^APIConnectionError: Connection error\.$"):
        AnthropicProvider(_raising(plain)).send(request())


SDK_DRIVER = r"""
import json, sys, types

# A project environment with Brotli 1.1, as xcdat-569's (NOTES 41): importable, so httpx2 would
# ask for brotli; its process() takes no keyword arguments, so httpx2 could not decode one.
brotli = types.ModuleType("brotli")
class Decompressor:
    def process(self, data):
        return data
brotli.Decompressor, brotli.error = Decompressor, Exception
sys.modules["brotli"] = brotli

from tracefix.llm import AnthropicProvider, LLMRequest, Message

got = AnthropicProvider().send(LLMRequest("judge", "claude-opus-5-5", "sys",
                                          (Message("user", "x"),), {}))
print(json.dumps([got.text, got.input_tokens, got.output_tokens]))
"""


def test_answers_are_asked_for_only_in_encodings_the_standard_library_decodes() -> None:
    """The real SDK (in a subprocess: this one blocks connections) against a loopback server:
    no brotli or zstd in Accept-Encoding, whatever is installed (a project's Brotli 1.1 made
    every answer undecodable: NOTES 41), and a gzip answer decodes."""
    import gzip
    import http.server
    import subprocess
    import sys
    import threading

    answer = {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": '{"ok": true}'}], "stop_reason": "end_turn",
        "stop_sequence": None, "usage": {"input_tokens": 3, "output_tokens": 2},
    }  # fmt: skip
    body = gzip.compress(json.dumps(answer).encode())
    asked: list[str | None] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            asked.append(self.headers.get("Accept-Encoding"))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")}
    env.update(
        NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost",
        ANTHROPIC_BASE_URL=f"http://127.0.0.1:{server.server_port}",
        ANTHROPIC_API_KEY="not-a-real-key",
    )  # fmt: skip
    try:
        ran = subprocess.run(
            [sys.executable, "-c", SDK_DRIVER],
            capture_output=True, text=True, timeout=60, env=env,
        )  # fmt: skip
    finally:
        server.shutdown()
        server.server_close()
    assert ran.returncode == 0, ran.stderr
    assert asked == ["gzip, deflate"]
    assert json.loads(ran.stdout) == ['{"ok": true}', 3, 2]


def test_no_credentials_at_all_fails_the_call_not_the_run() -> None:
    """The SDK raises a plain TypeError when it finds no credentials; that must end the stage like
    any API problem, while any other TypeError (a bug of ours) still surfaces."""
    from tracefix.llm import AnthropicProvider, LLMProviderError

    missing = TypeError("Could not resolve authentication method. Expected one of api_key, ...")
    with pytest.raises(LLMProviderError) as caught:
        AnthropicProvider(_raising(missing)).send(request())
    assert caught.value.kind == "no_credentials"
    with pytest.raises(TypeError, match="unrelated"):
        AnthropicProvider(_raising(TypeError("unrelated"))).send(request())


def _answering(seen: list[dict[str, object]]) -> object:
    def create(**kwargs: object) -> object:
        seen.append(kwargs)
        usage = SimpleNamespace(input_tokens=3, output_tokens=2)
        text = SimpleNamespace(type="text", text="{}")
        return SimpleNamespace(content=[text], usage=usage, stop_reason="end_turn")

    return SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))


def test_the_fallback_is_sent_only_to_models_that_take_it() -> None:
    from tracefix.llm import FALLBACK_BETA, AnthropicProvider

    seen: list[dict[str, object]] = []
    provider = AnthropicProvider(_answering(seen))
    for model in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-opus-4-8"):
        provider.send(LLMRequest("judge", model, "sys", (Message("user", "x"),), {}))
    assert [s.get("fallbacks") for s in seen] == ["default", "default", None, None]
    assert [s.get("betas") for s in seen[:2]] == [[FALLBACK_BETA], [FALLBACK_BETA]]
    assert all("betas" not in s for s in seen[2:])


def test_the_sdk_client_is_built_only_when_a_call_is_made(monkeypatch: pytest.MonkeyPatch) -> None:
    import anthropic

    from tracefix.llm import AnthropicProvider

    built: list[dict[str, object]] = []
    seen: list[dict[str, object]] = []

    def fake_client(**kwargs: object) -> object:
        built.append(kwargs)
        return _answering(seen)

    monkeypatch.setattr(anthropic, "Anthropic", fake_client)
    provider = AnthropicProvider()
    assert built == []  # nothing yet: a run that never asks a model needs no credentials
    provider.send(request())
    provider.send(request())
    assert len(built) == 1 and len(seen) == 2


def test_effort_and_max_tokens_reach_every_request() -> None:
    fake = FakeProvider([GOOD])
    LLMClient(fake, effort="high", max_tokens=8_000).complete("reproducer", "sys", ASK, Answer)
    assert (fake.requests[0].effort, fake.requests[0].max_tokens) == ("high", 8_000)


def test_default_settings_leave_every_request_key_unchanged() -> None:
    """Recordings are named by the request key: the new settings must not move it."""
    fake = FakeProvider([GOOD])
    LLMClient(fake).complete("reproducer", "sys", ASK, Answer)
    sent = fake.requests[0]
    before_m8 = LLMRequest("reproducer", sent.model, "sys", tuple(ASK), strict_schema(Answer))
    assert sent.key() == before_m8.key()


@pytest.mark.parametrize(
    ("effort", "max_tokens"), [("extreme", 16_000), ("medium", 0), ("medium", 20_001)]
)
def test_settings_outside_what_the_api_takes_are_refused(effort: str, max_tokens: int) -> None:
    with pytest.raises(ValueError):
        LLMClient(FakeProvider([]), effort=effort, max_tokens=max_tokens)


def test_every_failed_call_is_logged_with_its_kind() -> None:
    from tracefix.llm import AnthropicProvider, LLMProviderError

    limited = LLMClient(AnthropicProvider(_raising(_status_error(429))))
    with pytest.raises(LLMProviderError):
        limited.complete("adversary", "sys", ASK, Answer)
    [problem] = limited.problems
    assert (problem.role, problem.kind, problem.status) == ("adversary", "rate_limit", 429)
    assert problem.model == limited.models["adversary"] and "RateLimitError" in problem.detail

    budget = LLMClient(FakeProvider([GOOD, GOOD]), max_calls=1)
    budget.complete("judge", "sys", ASK, Answer)
    with pytest.raises(BudgetExceeded):
        budget.complete("judge", "sys", ASK, Answer)
    assert [p.kind for p in budget.problems] == ["budget"]

    class Refuses:
        def send(self, request: LLMRequest) -> LLMResponse:
            return LLMResponse("", 10, 0, "refusal")

    refused = LLMClient(Refuses())
    with pytest.raises(LLMOutputError):
        refused.complete("judge", "sys", ASK, Answer)
    invalid = LLMClient(FakeProvider([{"value": "x"}, {"value": "y"}]))
    with pytest.raises(LLMOutputError):
        invalid.complete("judge", "sys", ASK, Answer)
    assert [p.kind for p in refused.problems + invalid.problems] == ["refusal", "invalid_output"]


def test_a_missing_recording_is_logged_and_still_fails_loudly(tmp_path: Path) -> None:
    client = LLMClient(RecordedProvider(tmp_path))
    with pytest.raises(MissingRecording):
        client.complete("reproducer", "sys", ASK, Answer)
    assert [p.kind for p in client.problems] == ["missing_recording"]


def test_every_default_model_has_a_list_price() -> None:
    from tracefix.llm import DEFAULT_MODELS, PRICES_PER_MTOK

    assert set(DEFAULT_MODELS.values()) <= set(PRICES_PER_MTOK)
    assert PRICES_PER_MTOK["claude-haiku-5-5"] == (0.10, 0.50)
