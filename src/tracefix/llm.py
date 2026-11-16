"""LLM layer: one `complete()` call per role, with schema validation, budgets, a call log and a log
of failed calls with the reason our code gave each (`Problem`: the API account, the API, or
Tracefix's own limits).

Providers: `AnthropicProvider` (live), `RecordedProvider` (replays stored responses, used by the
default test suite), `RecordingProvider` (live + stores responses) and `FakeProvider` (scripted).

AI proposes, deterministic code decides: nothing returned from here sets a verdict on its own.
"""

import hashlib
import json
import time
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

Role = Literal["reproducer", "mutator", "adversary", "judge"]
DEFAULT_MODELS: dict[Role, str] = {
    "reproducer": "claude-sonnet-5-5",  # compared with Opus on fixtures 1-7: see DECISIONS.md
    "mutator": "claude-sonnet-5-5",  # proposals only; hygiene rules and runs decide (M4)
    "adversary": "claude-opus-5-5",
    "judge": "claude-opus-5-5",
}
DEFAULT_EFFORT = "medium"
EFFORTS = ("low", "medium", "high", "xhigh", "max")
# List prices in US dollars per million tokens (input, output), as listed on 6 Oct 2026, for cost
# estimates only.
PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-fable-5-1": (10.00, 50.00),
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),  # prompts up to 100k tokens, which ours stay under
    "claude-haiku-4-5": (1.00, 5.00),
}
DEFAULT_MAX_TOKENS = 16_000  # per response; thinking counts towards it
# Calls are not streamed, and the SDK refuses a non-streamed call whose answer could take longer
# than its timeout, so a user's setting stays well under that.
MAX_TOKENS_LIMIT = 20_000
DEFAULT_MAX_CALLS = 40  # SPEC 2.1 max_llm_calls
DEFAULT_TOKEN_BUDGET = 500_000  # input + output tokens over a whole run
API_TIMEOUT_S = 300.0
API_MAX_RETRIES = 2
# Only what the standard library decodes. httpx2 also asks for brotli or zstd whenever those
# libraries import, and Tracefix may share the project's environment: Brotli 1.1 there made
# every answer undecodable, which the SDK reports as "Connection error." (NOTES 41).
ACCEPT_ENCODING = "gzip, deflate"
CAUSE_WORDS = 300  # characters of an error's innermost cause kept in its words
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Models that take the server-side refusal fallback in its "default" form; any other model is
# sent without it (Haiku 5.5, for one, rejects the parameter).
FALLBACK_MODELS = frozenset({"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5",
                             "claude-sonnet-5-5"})  # fmt: skip
RERECORD_HINT = "re-record with TRACEFIX_RECORD=1 (costs money; see docs)"
# What the SDK raises (a plain TypeError, before any request) when it finds no credentials at all.
_NO_CREDENTIALS = "Could not resolve authentication method"

# Why a model call failed, decided by our code from the exception it caught, never from model
# text. The receipt words each kind (account, API, Tracefix's own limits).
ProblemKind = Literal[
    "no_credentials",  # no API key, auth token or login profile found
    "auth",  # 401: the credentials were rejected
    "billing",  # 402: e.g. no credit left
    "permission",  # 403: the account may not use this model or feature
    "model_unavailable",  # 404: no such model, or not available to this account
    "rate_limit",  # 429: the account's rate or usage limit
    "api_unavailable",  # 5xx and 529: the API was failing or overloaded
    "network",  # no connection, or the call timed out
    "rejected",  # another 4xx: the API refused Tracefix's request
    "budget",  # Tracefix's own call limit or token budget for the run
    "refusal",  # the model declined the request
    "invalid_output",  # the answer did not match the schema, even after one retry
    "missing_recording",  # tests: no recorded answer for this request
    "other",
]

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base class: the stage that asked fails, the run goes on."""


class BudgetExceeded(LLMError):
    pass


class LLMOutputError(LLMError):
    """The model's answer did not match the schema, even after one retry."""


class MissingRecording(LLMError):
    pass


class LLMProviderError(LLMError):
    """The API call itself failed (network, rate limit, server error) after the SDK's retries.
    `kind` and `status` say why, as our code classified it (`api_problem`)."""

    def __init__(self, message: str, kind: ProblemKind = "other", status: int | None = None):
        super().__init__(message)
        self.kind: ProblemKind = kind
        self.status = status


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMRequest:
    role: Role
    model: str
    system: str
    messages: tuple[Message, ...]
    schema: dict[str, Any]
    max_tokens: int = DEFAULT_MAX_TOKENS
    effort: str = DEFAULT_EFFORT

    def key(self) -> str:
        """Stable hash of everything that shapes the answer; names the recording file."""
        canonical = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    stop_reason: str | None = None


@dataclass(frozen=True)
class CallRecord:
    role: Role
    model: str
    input_tokens: int
    output_tokens: int
    latency_s: float
    valid: bool  # the answer matched the schema


@dataclass(frozen=True)
class Problem:
    """A model call that failed, and why (for the receipt: which stage it hurt, in plain words)."""

    role: Role
    model: str
    kind: ProblemKind
    status: int | None  # the HTTP status, when the API answered
    detail: str  # the exception's own text, cut short: shown masked, never decides anything


class Provider(Protocol):
    def send(self, request: LLMRequest) -> LLMResponse: ...


def api_problem(exc: BaseException) -> tuple[ProblemKind, int | None]:
    """Why an API call failed, from the SDK's exception class and the HTTP status."""
    import anthropic

    if isinstance(exc, anthropic.APIConnectionError):  # a timeout is one too
        return "network", None
    if isinstance(exc, anthropic.APIStatusError):
        status = exc.status_code
        by_status: dict[int, ProblemKind] = {
            401: "auth",
            402: "billing",
            403: "permission",
            404: "model_unavailable",
            429: "rate_limit",
        }
        if status in by_status:
            return by_status[status], status
        return ("api_unavailable" if status >= 500 else "rejected"), status
    return "other", None


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema for structured output: every property required, no extra keys, no titles."""

    def clean(node: Any) -> Any:
        if isinstance(node, dict):
            out = {k: clean(v) for k, v in node.items() if k != "title"}
            if out.get("type") == "object":
                out["additionalProperties"] = False
                out["required"] = sorted(out.get("properties", {}))
            return out
        if isinstance(node, list):
            return [clean(v) for v in node]
        return node

    result: dict[str, Any] = clean(model.model_json_schema())
    return result


def described(exc: BaseException) -> str:
    """An SDK error in words, with its innermost cause: the SDK says "Connection error." for any
    failure while reading an answer, which hid a decoding bug (NOTES 41)."""
    words = f"{type(exc).__name__}: {exc}"
    root, seen = exc, {id(exc)}
    while root.__cause__ is not None and id(root.__cause__) not in seen:
        root = root.__cause__
        seen.add(id(root))
    if root is exc:
        return words
    return f"{words} (cause: {type(root).__name__}: {str(root)[:CAUSE_WORDS]})"


class AnthropicProvider:
    """Live calls. Credentials are whatever the SDK finds (ANTHROPIC_API_KEY, an auth token or a
    login profile); they are never logged. The SDK client is built on the first call, so a run
    that never asks a model needs none."""

    def __init__(self, client: Any = None) -> None:
        self._client = client

    def _sdk(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(
                timeout=API_TIMEOUT_S,
                max_retries=API_MAX_RETRIES,
                default_headers={"Accept-Encoding": ACCEPT_ENCODING},
            )
        return self._client

    def send(self, request: LLMRequest) -> LLMResponse:
        import anthropic

        try:
            return self._send(request)
        except anthropic.APIError as exc:  # also covers connection errors and timeouts
            kind, status = api_problem(exc)
            raise LLMProviderError(described(exc), kind, status) from exc
        except TypeError as exc:
            if not str(exc).startswith(_NO_CREDENTIALS):
                raise  # a bug of ours, not an API problem
            raise LLMProviderError(f"no API credentials: {exc}", "no_credentials") from exc

    def _send(self, request: LLMRequest) -> LLMResponse:
        fallback: dict[str, Any] = (
            {"betas": [FALLBACK_BETA], "fallbacks": "default"}
            if request.model in FALLBACK_MODELS
            else {}
        )
        response = self._sdk().beta.messages.create(
            model=request.model,
            max_tokens=request.max_tokens,
            system=request.system,
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            output_config={
                "effort": request.effort,
                "format": {"type": "json_schema", "schema": request.schema},
            },
            **fallback,
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        usage = response.usage
        return LLMResponse(text, usage.input_tokens, usage.output_tokens, response.stop_reason)


def _recording_path(directory: Path, request: LLMRequest) -> Path:
    return directory / f"{request.role}-{request.key()[:32]}.json"


class RecordedProvider:
    """Replays stored responses. Never touches the network."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def send(self, request: LLMRequest) -> LLMResponse:
        path = _recording_path(self.directory, request)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise MissingRecording(f"no recorded response {path.name}; {RERECORD_HINT}") from None
        if data.get("key") != request.key():
            raise MissingRecording(f"recording {path.name} is for another request; {RERECORD_HINT}")
        return LLMResponse(**data["response"])


class RecordingProvider:
    """Sends to a live provider and stores each response for RecordedProvider."""

    def __init__(self, inner: Provider, directory: Path) -> None:
        self.inner = inner
        self.directory = directory

    def send(self, request: LLMRequest) -> LLMResponse:
        response = self.inner.send(request)
        self.directory.mkdir(parents=True, exist_ok=True)
        record = {"key": request.key(), "role": request.role, "model": request.model,
                  "response": asdict(response)}  # fmt: skip
        path = _recording_path(self.directory, request)
        path.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return response


class FakeProvider:
    """Returns scripted answers in order and keeps every request it saw (for unit tests)."""

    def __init__(self, answers: Iterable[str | dict[str, Any]]) -> None:
        self.answers = [a if isinstance(a, str) else json.dumps(a) for a in answers]
        self.requests: list[LLMRequest] = []

    def send(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self.answers:
            raise LLMError("FakeProvider ran out of scripted answers")
        return LLMResponse(self.answers.pop(0), 100, 50, "end_turn")


def cost_usd(calls: Sequence[CallRecord]) -> float | None:
    """Estimated list-price cost of these calls; None if a model has no known price."""
    total = 0.0
    for c in calls:
        if c.model not in PRICES_PER_MTOK:
            return None
        price_in, price_out = PRICES_PER_MTOK[c.model]
        total += (c.input_tokens * price_in + c.output_tokens * price_out) / 1_000_000
    return total


@dataclass
class LLMClient:
    provider: Provider
    models: dict[Role, str] = field(default_factory=lambda: dict(DEFAULT_MODELS))
    max_calls: int = DEFAULT_MAX_CALLS
    token_budget: int = DEFAULT_TOKEN_BUDGET
    calls: list[CallRecord] = field(default_factory=list)
    # The user's settings (M8). They shape what the model proposes, never a verdict; at their
    # defaults every request is exactly what it was before, so recordings stay valid.
    effort: str = DEFAULT_EFFORT
    max_tokens: int = DEFAULT_MAX_TOKENS
    problems: list[Problem] = field(default_factory=list)  # every call that failed, and why

    def __post_init__(self) -> None:
        if self.effort not in EFFORTS:
            raise ValueError(f"effort must be one of {', '.join(EFFORTS)}, not {self.effort!r}")
        if not 1 <= self.max_tokens <= MAX_TOKENS_LIMIT:
            raise ValueError(f"max_tokens must be between 1 and {MAX_TOKENS_LIMIT}")

    @property
    def tokens_used(self) -> int:
        return sum(c.input_tokens + c.output_tokens for c in self.calls)

    def _problem(self, request: LLMRequest, kind: ProblemKind, status: int | None,
                 exc: BaseException) -> None:  # fmt: skip
        detail = f"{type(exc).__name__}: {exc}"[:300]
        self.problems.append(Problem(request.role, request.model, kind, status, detail))

    @property
    def cost_usd(self) -> float | None:
        """Estimated list-price cost of all calls; None if a model has no known price."""
        return cost_usd(self.calls)

    def _send(self, request: LLMRequest) -> LLMResponse:
        stop = None
        if len(self.calls) >= self.max_calls:
            stop = BudgetExceeded(f"LLM call limit reached ({self.max_calls} calls)")
        elif self.tokens_used >= self.token_budget:
            stop = BudgetExceeded(f"LLM token budget used up ({self.token_budget} tokens)")
        if stop is not None:
            self._problem(request, "budget", None, stop)
            raise stop
        start = time.monotonic()
        try:
            response = self.provider.send(request)
        except LLMProviderError as exc:
            self._problem(request, exc.kind, exc.status, exc)
            raise
        except MissingRecording as exc:
            self._problem(request, "missing_recording", None, exc)
            raise
        except LLMError as exc:
            self._problem(request, "other", None, exc)
            raise
        latency = round(time.monotonic() - start, 3)
        self.calls.append(CallRecord(request.role, request.model, response.input_tokens,
                                     response.output_tokens, latency, valid=False))  # fmt: skip
        return response

    def _mark_valid(self) -> None:
        last = self.calls[-1]
        self.calls[-1] = CallRecord(last.role, last.model, last.input_tokens,
                                    last.output_tokens, last.latency_s, valid=True)  # fmt: skip

    def complete(self, role: Role, system: str, messages: Sequence[Message], schema: type[T]) -> T:
        """Ask the model for one answer of type `schema`. Invalid output: one retry, then error."""
        history = tuple(messages)
        json_schema = strict_schema(schema)
        for attempt in range(2):
            request = LLMRequest(role, self.models[role], system, history, json_schema,
                                 self.max_tokens, self.effort)  # fmt: skip
            response = self._send(request)
            if response.stop_reason == "refusal":
                declined = LLMOutputError(f"the {role} model declined the request")
                self._problem(request, "refusal", None, declined)
                raise declined
            try:
                parsed = schema.model_validate_json(response.text)
            except ValidationError as exc:
                if attempt == 1:
                    invalid = LLMOutputError(f"invalid {role} output after a retry: {exc}")
                    self._problem(request, "invalid_output", None, invalid)
                    raise invalid from exc
                problem = str(exc)[:2000]
                history += (
                    Message("assistant", response.text),
                    Message("user", f"That answer did not match the JSON schema:\n{problem}\n"
                                    "Reply again with only JSON that matches it."),
                )  # fmt: skip
                continue
            self._mark_valid()
            return parsed
        raise AssertionError("unreachable")
