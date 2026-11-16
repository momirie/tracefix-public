"""The GitHub API client (plan P9): in-process tests with a scripted transport, and real HTTP in a
subprocess against the loopback fake (the default suite blocks connections in this process)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any

import pytest
from github_fake import FakeGitHub

from tracefix import github_api
from tracefix.github_api import GitHub, GitHubError, Response

API = "https://api.test"


def reply(payload: Any = None, status: int = 200, **headers: str) -> Response:
    body = b"" if payload is None else json.dumps(payload).encode("utf-8")
    return Response(status, {k.replace("_", "-"): v for k, v in headers.items()}, body)


class Scripted:
    """A transport that answers from a list (a Response, or an exception to raise)."""

    def __init__(self, *replies: Response | Exception) -> None:
        self.replies = list(replies)
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request: urllib.request.Request, timeout: float, limit: int) -> Response:
        self.requests.append(request)
        answer = self.replies.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return Response(answer.status, answer.headers, answer.body[: limit + 1])

    @property
    def urls(self) -> list[str]:
        return [r.full_url for r in self.requests]


def client(transport: Scripted, sleeps: list[float] | None = None) -> GitHub:
    record = sleeps if sleeps is not None else []
    return GitHub(
        "tok", "o/r", api_url=API, transport=transport, sleep=record.append, clock=lambda: 1000.0
    )


def comment(number: int, author: str | None = "github-actions[bot]") -> dict[str, Any]:
    user = None if author is None else {"login": author}
    return {"id": number, "body": f"c{number}", "user": user, "html_url": "", "created_at": ""}


# --- pagination -----------------------------------------------------------------------------------


def test_pagination_follows_next_links() -> None:
    page2 = f'<{API}/repos/o/r/issues/5/comments?per_page=100&page=2>; rel="next"'
    page3 = f'<{API}/repos/o/r/issues/5/comments?per_page=100&page=3>; rel="next", <x>; rel="last"'
    t = Scripted(
        reply([comment(1), comment(2)], link=page2),
        reply([comment(3)], link=page3),
        reply([comment(4)]),
    )
    assert [c.id for c in client(t).list_comments(5)] == [1, 2, 3, 4]
    assert t.urls[0] == f"{API}/repos/o/r/issues/5/comments?per_page=100"
    assert t.urls[2].endswith("page=3")


def test_pagination_stops_after_max_pages() -> None:
    link = f'<{API}/repos/o/r/issues/5/comments?page=n>; rel="next"'
    t = Scripted(*[reply([comment(i)], link=link) for i in range(github_api.MAX_PAGES + 5)])
    assert len(client(t).list_comments(5)) == github_api.MAX_PAGES
    assert len(t.requests) == github_api.MAX_PAGES


@pytest.mark.parametrize(
    "target", ["https://evil.test/repos/o/r/x", "https://api.test.evil.test/x", "http://api.test/x"]
)
def test_a_pagination_link_away_from_the_api_is_refused(target: str) -> None:
    t = Scripted(reply([comment(1)], link=f'<{target}>; rel="next"'))
    with pytest.raises(GitHubError, match="points away from the API"):
        client(t).list_comments(5)
    assert len(t.requests) == 1  # the token never went there


def test_artifacts_are_listed_by_name_from_the_envelope() -> None:
    artifact = {
        "id": 9,
        "name": "tracefix-receipt-pr-7",
        "size_in_bytes": 1234,
        "expired": True,
        "created_at": "2026-10-14T10:00:00Z",
        "workflow_run": {"id": 77},
    }
    bare = {**artifact, "id": 10, "workflow_run": None, "expired": False}
    t = Scripted(reply({"total_count": 2, "artifacts": [artifact, bare]}))
    found = client(t).list_artifacts("tracefix-receipt-pr-7")
    assert t.urls[0] == f"{API}/repos/o/r/actions/artifacts?name=tracefix-receipt-pr-7&per_page=100"
    assert [(a.id, a.size, a.expired, a.run_id) for a in found] == [
        (9, 1234, True, 77),
        (10, 1234, False, 0),
    ]
    assert found[0].name == "tracefix-receipt-pr-7"
    assert found[0].created_at == "2026-10-14T10:00:00Z"


# --- retries and rate limits ----------------------------------------------------------------------


def test_server_errors_are_retried() -> None:
    sleeps: list[float] = []
    t = Scripted(reply(status=502), reply(status=503), reply({"login": "me"}))
    assert client(t, sleeps).get_user() == "me"
    assert sleeps == [1.0, 2.0]


def test_three_server_errors_raise() -> None:
    t = Scripted(*[reply({"message": "busy"}, status=503)] * 3)
    with pytest.raises(GitHubError) as caught:
        client(t).get_user()
    assert (caught.value.status, len(t.requests)) == (503, 3)
    assert "busy" in caught.value.message


def test_dropped_connections_are_retried_then_raise() -> None:
    sleeps: list[float] = []
    t = Scripted(urllib.error.URLError("refused"), TimeoutError(), ConnectionResetError())
    with pytest.raises(GitHubError, match="no response") as caught:
        client(t, sleeps).get_user()
    assert caught.value.status == 0
    assert sleeps == [1.0, 2.0]


def test_a_rate_limit_is_waited_out_once() -> None:
    sleeps: list[float] = []
    t = Scripted(reply(status=429, retry_after="7"), reply({"login": "me"}))
    assert client(t, sleeps).get_user() == "me"
    assert sleeps == [7.0]

    sleeps.clear()
    t = Scripted(reply(status=429, retry_after="7"), reply(status=429, retry_after="7"))
    with pytest.raises(GitHubError) as caught:
        client(t, sleeps).get_user()
    assert (caught.value.status, sleeps) == (429, [7.0])


def test_the_wait_does_not_use_up_an_attempt() -> None:
    sleeps: list[float] = []
    t = Scripted(reply(status=500), reply(status=429), reply(status=500), reply({"login": "me"}))
    assert client(t, sleeps).get_user() == "me"
    assert sleeps == [1.0, github_api.MAX_WAIT_S, 2.0]


def test_secondary_and_primary_rate_limits() -> None:
    sleeps: list[float] = []
    secondary = reply({"message": "secondary rate limit"}, status=403, retry_after="3")
    primary = reply(status=403, x_ratelimit_remaining="0", x_ratelimit_reset="1010")
    t = Scripted(secondary, reply({"login": "a"}), primary, reply({"login": "b"}))
    gh = client(t, sleeps)
    assert (gh.get_user(), gh.get_user()) == ("a", "b")
    assert sleeps == [3.0, 10.0]  # the reset is at 1010 and the clock says 1000


def test_a_long_wait_is_not_waited() -> None:
    sleeps: list[float] = []
    t = Scripted(reply(status=429, retry_after="120"))
    with pytest.raises(GitHubError):
        client(t, sleeps).get_user()
    assert sleeps == []


@pytest.mark.parametrize(
    "failure", [reply(status=502), ConnectionResetError()], ids=["server-error", "dropped"]
)
def test_a_write_is_never_sent_twice(failure: object) -> None:
    """It may have reached GitHub before its answer was lost: a second comment or check run
    (verifier M9 N8). A rate limit is still waited out (GitHub did not take the first one)."""
    sleeps: list[float] = []
    t = Scripted(failure, reply(comment(1)))  # type: ignore[arg-type]
    with pytest.raises(GitHubError):
        client(t, sleeps).create_comment(5, "x")
    assert (len(t.requests), sleeps) == (1, [])
    limited = Scripted(reply(status=429, retry_after="2"), reply(comment(4)))
    assert client(limited, sleeps).create_comment(5, "x").id == 4
    assert (len(limited.requests), sleeps) == (2, [2.0])


def test_a_permission_error_is_not_retried() -> None:
    sleeps: list[float] = []
    t = Scripted(reply({"message": "Resource not accessible by integration"}, status=403))
    with pytest.raises(GitHubError) as caught:
        client(t, sleeps).create_comment(5, "x")
    assert caught.value.status == 403
    assert caught.value.message == (
        f"POST {API}/repos/o/r/issues/5/comments: Resource not accessible by integration"
    )
    assert (len(t.requests), sleeps) == (1, [])


# --- errors, caps and shapes ----------------------------------------------------------------------


def test_error_messages_are_one_capped_line() -> None:
    long = reply({"message": "a\nb\r\n" + "x" * 1000}, status=422)
    for answer, expected in [
        (Response(404, {}, b"<html>not json</html>"), "HTTP 404"),
        (reply({"message": None}, status=404), "HTTP 404"),
        (long, "a b " + "x" * (github_api.MAX_MESSAGE_CHARS - 4)),
    ]:
        with pytest.raises(GitHubError) as caught:
            client(Scripted(answer)).get_issue(1)
        assert caught.value.message.split(": ", 1)[1] == expected


def test_responses_over_the_cap_are_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(github_api, "MAX_JSON_BYTES", 20)
    t = Scripted(reply({"login": "x" * 50}))
    with pytest.raises(GitHubError, match="over 20 bytes"):
        client(t).get_user()

    monkeypatch.setattr(github_api, "MAX_ZIP_BYTES", 4)
    with pytest.raises(GitHubError, match="over 4 bytes"):
        client(Scripted(Response(200, {}, b"PK\x03\x04more"))).download_artifact(3)
    assert client(Scripted(Response(200, {}, b"PK\x03\x04"))).download_artifact(3) == b"PK\x03\x04"


@pytest.mark.parametrize(
    "answer",
    [
        Response(200, {}, b"not json"),
        reply([1, 2]),
        reply({"id": True, "html_url": ""}),
        reply({"id": "1", "html_url": ""}),
        reply({"id": 1, "html_url": 5}),
    ],
)
def test_unexpected_shapes_are_errors(answer: Response) -> None:
    with pytest.raises(GitHubError, match="unexpected response") as caught:
        client(Scripted(answer)).create_check_run({"name": "Tracefix"})
    assert caught.value.status == 0


def test_typed_results() -> None:
    issue = {"number": 3, "title": "Crash", "body": None, "pull_request": {"url": "..."}}
    run = {
        "id": 77,
        "path": ".github/workflows/tracefix.yml",
        "event": "pull_request_target",
        "head_repository": {"full_name": "o/r"},
    }
    t = Scripted(
        reply(issue),
        reply({"number": 4, "title": "Bug", "body": "text"}),
        reply([comment(1, author=None), comment(2)]),
        reply(run),
        reply({"id": 5, "html_url": "https://github.com/o/r/runs/5"}),
    )
    gh = client(t)
    pull, issue_4 = gh.get_issue(3), gh.get_issue(4)
    assert pull == github_api.Issue(3, "Crash", "", True)  # a PR is an issue with `pull_request`
    assert (pull.is_pull_request, issue_4.is_pull_request) == (True, False)
    assert issue_4 == github_api.Issue(4, "Bug", "text", False)
    assert [(c.id, c.author, c.body) for c in gh.list_comments(1)] == [
        (1, "", "c1"),
        (2, "github-actions[bot]", "c2"),
    ]
    assert gh.get_workflow_run(77) == github_api.WorkflowRun(77, run["path"], run["event"], "o/r")
    check = gh.create_check_run({"name": "Tracefix", "head_sha": "a" * 40})
    assert (check.id, check.html_url) == (5, "https://github.com/o/r/runs/5")


# --- requests -------------------------------------------------------------------------------------


def test_requests_carry_the_api_headers_and_json() -> None:
    t = Scripted(reply(comment(8)), reply(comment(8)))
    gh = client(t)
    gh.update_comment(8, "new ✓")
    gh.create_comment(2, "x")
    patch = t.requests[0]
    assert (patch.get_method(), patch.full_url) == ("PATCH", f"{API}/repos/o/r/issues/comments/8")
    assert json.loads(patch.data) == {"body": "new ✓"}
    assert patch.get_header("Content-type") == "application/json"
    assert patch.get_header("Accept") == "application/vnd.github+json"
    assert patch.get_header("X-github-api-version") == github_api.API_VERSION
    assert t.requests[1].full_url == f"{API}/repos/o/r/issues/2/comments"


def test_the_token_is_never_copied_onto_a_redirect() -> None:
    t = Scripted(Response(200, {}, b"PK"))
    client(t).download_artifact(3)
    request = t.requests[0]
    assert request.unredirected_hdrs["Authorization"] == "Bearer tok"
    assert "Authorization" not in request.headers
    hop = urllib.request.HTTPRedirectHandler().redirect_request(
        request, None, 302, "Found", {}, "https://blob.test/zip?sig=1"
    )
    assert hop is not None
    assert not hop.has_header("Authorization")


def test_label_names_are_quoted_into_one_path_segment() -> None:
    t = Scripted(reply([]))
    client(t).remove_label(3, "trace fix/../../x")
    assert t.urls[0] == f"{API}/repos/o/r/issues/3/labels/trace%20fix%2F..%2F..%2Fx"
    assert t.requests[0].get_method() == "DELETE"


def test_repository_and_api_url_are_checked(monkeypatch: pytest.MonkeyPatch) -> None:
    for repo in ["o", "o/r/x", "../r", "o/..", "o r/x", ""]:
        with pytest.raises(ValueError, match="repository"):
            GitHub("tok", repo, api_url=API)
    with pytest.raises(ValueError, match="API URL"):
        GitHub("tok", "o/r", api_url="file:///etc")
    monkeypatch.setenv("GITHUB_API_URL", "https://ghe.test/api/v3/")
    assert GitHub("tok", "o/r").api == "https://ghe.test/api/v3"
    monkeypatch.delenv("GITHUB_API_URL")
    assert GitHub("tok", "o/r").api == github_api.DEFAULT_API


def test_the_opener_speaks_only_http() -> None:
    request = urllib.request.Request("file:///etc/passwd")
    with pytest.raises(urllib.error.URLError, match="unknown url type"):
        github_api.urllib_transport(request, 1.0, 100)


# --- real HTTP against the loopback fake (subprocess) ---------------------------------------------

DRIVER = r"""
import dataclasses, json, sys
from tracefix.github_api import GitHub, GitHubError

spec = json.load(sys.stdin)
gh = GitHub(spec["token"], spec["repo"], api_url=spec["api"])
out = []
for name, args in spec["ops"]:
    try:
        value = getattr(gh, name)(*args)
    except GitHubError as error:
        out.append({"error": [error.status, error.message]})
        continue
    if isinstance(value, bytes):
        value = value.hex()
    elif isinstance(value, list):
        value = [dataclasses.asdict(v) for v in value]
    elif dataclasses.is_dataclass(value):
        value = dataclasses.asdict(value)
    out.append({"ok": value})
print(json.dumps(out))
"""


def drive(fake: FakeGitHub, ops: list[tuple[str, list[Any]]], token: str = "") -> list[Any]:
    env = {k: v for k, v in os.environ.items() if not k.lower().endswith("_proxy")}
    env.update(NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
    spec = {"token": token or fake.token, "repo": fake.repo, "api": fake.api_url, "ops": ops}
    result = subprocess.run(
        [sys.executable, "-c", DRIVER],
        input=json.dumps(spec),
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    out: list[Any] = json.loads(result.stdout)
    return out


def test_every_endpoint_against_the_fake() -> None:
    fake = FakeGitHub(per_page_cap=40)
    for i in range(95):
        fake.add_comment(7, f"comment {i}", "someone")
    fake.issues[12] = {"number": 12, "title": "Port crash", "body": "Empty port", "state": "open"}
    fake.runs[55] = {"id": 55, "path": ".github/workflows/tracefix.yml", "event": "pull_request"}
    fake.labels[7] = ["tracefix", "bug"]
    fake.add_artifact("tracefix-receipt-pr-7", b"zip1", 55, expired=True)
    fake.add_artifact("other", b"zip2", 55)
    with fake.serve():
        out = drive(
            fake,
            [
                ("list_comments", [7]),
                ("create_comment", [7, "<!-- tracefix-receipt -->\nfirst"]),
                ("update_comment", [fake.comments[0]["id"], "edited"]),
                ("get_issue", [12]),
                ("get_issue", [999]),
                ("get_user", []),
                ("list_artifacts", ["tracefix-receipt-pr-7"]),
                ("get_workflow_run", [55]),
                ("remove_label", [7, "tracefix"]),
                ("create_check_run", [{"name": "Tracefix", "conclusion": "neutral"}]),
            ],
        )
    comments, created, edited, issue, missing, user, artifacts, run, _, check = out
    assert len(comments["ok"]) == 95  # 3 pages of at most 40, through real Link headers
    assert [c["body"] for c in comments["ok"][:2]] == ["comment 0", "comment 1"]
    assert created["ok"]["author"] == "github-actions[bot]"
    assert fake.comments[-1]["body"] == "<!-- tracefix-receipt -->\nfirst"
    assert (edited["ok"]["body"], fake.comments[0]["body"]) == ("edited", "edited")
    assert issue["ok"] == {
        "number": 12,
        "title": "Port crash",
        "body": "Empty port",
        "is_pull_request": False,
    }
    assert missing["error"][0] == 404
    assert user["ok"] == "github-actions[bot]"
    assert [(a["name"], a["expired"], a["run_id"]) for a in artifacts["ok"]] == [
        ("tracefix-receipt-pr-7", True, 55)
    ]
    assert run["ok"]["event"] == "pull_request"
    assert fake.labels[7] == ["bug"]
    assert check["ok"]["id"] == fake.check_runs[0]["id"]
    assert fake.check_runs[0]["conclusion"] == "neutral"
    assert [s.method for s in fake.seen if "/comments" in s.path][:3] == ["GET"] * 3


def test_errors_over_real_http() -> None:
    fake = FakeGitHub(login=None)
    fake.queued = [(500, {}, b""), (500, {}, b"")]
    with fake.serve():
        out = drive(fake, [("get_user", [])])
        bad = drive(fake, [("get_user", [])], token="wrong")
    assert out[0]["error"] == [
        403,
        f"GET {fake.api_url}/user: Resource not accessible by integration",
    ]
    tried = [s for s in fake.seen if s.authorization == f"Bearer {fake.token}"]
    assert len(tried) == 3  # two 500s retried, then the 403 (not retried)
    assert bad[0]["error"][0] == 401


def test_the_token_reaches_the_api_but_not_the_blob_host() -> None:
    fake = FakeGitHub()
    artifact = fake.add_artifact("tracefix-receipt-pr-7", b"PK\x03\x04 receipt", 55)
    with fake.serve():
        out = drive(fake, [("download_artifact", [artifact["id"]])])
    assert bytes.fromhex(out[0]["ok"]) == b"PK\x03\x04 receipt"
    api, blob = fake.seen
    assert (api.host, api.authorization) == ("api", f"Bearer {fake.token}")
    assert (blob.host, blob.authorization) == ("blob", None)
    assert blob.path == f"/blob/{artifact['id']}?sig=signed"
