"""A small GitHub REST client for the Action (plan P9): standard library only, no new dependency.

Only the endpoints the Action uses. The token goes in an *unredirected* header, so a redirect (the
artifact download's hop to blob storage) never carries it, and pagination only follows links back
to the same API. Every response has a size cap; server errors and dropped connections are retried
(ATTEMPTS in all), and a rate limit is waited out once, for at most MAX_WAIT_S. Every failure is a
`GitHubError(status, message)`; status 0 means no usable response (no connection, or a body that
is not what GitHub sends). Everything a response says is untrusted data: callers render it, never
run it.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from urllib.parse import quote, urlencode

DEFAULT_API = "https://api.github.com"
API_VERSION = "2022-11-28"
TIMEOUT_S = 30.0  # per request (each socket operation)
ATTEMPTS = 3  # a GET, on a 5xx or a dropped connection
MAX_WAIT_S = 60.0  # one rate-limit wait at most this long
MAX_PAGES = 30
PER_PAGE = 100
MAX_JSON_BYTES = 30_000_000  # a page of 100 comments of up to 65,536 characters each
MAX_ZIP_BYTES = 20_000_000
MAX_MESSAGE_CHARS = 300
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_NEXT = re.compile(r'<([^<>]+)>\s*;\s*rel="next"')


class GitHubError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"GitHub API {status}: {message}" if status else f"GitHub API: {message}")
        self.status = status
        self.message = message


@dataclass(frozen=True)
class Response:
    status: int
    headers: Mapping[str, str]  # names in lower case
    body: bytes  # at most the request's limit + 1 bytes


# (request, timeout in seconds, byte limit) -> response; raises OSError when there is no response.
Transport = Callable[[urllib.request.Request, float, int], Response]


def _opener() -> urllib.request.OpenerDirector:
    """HTTP(S) only: no file:, ftp: or data: handler a redirect could reach (any other scheme is a
    URLError, from UnknownHandler)."""
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.UnknownHandler(),
        urllib.request.ProxyHandler(),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPSHandler(),
        urllib.request.HTTPRedirectHandler(),
        urllib.request.HTTPDefaultErrorHandler(),
        urllib.request.HTTPErrorProcessor(),
    ):
        opener.add_handler(handler)
    return opener


def urllib_transport(request: urllib.request.Request, timeout: float, limit: int) -> Response:
    try:
        with _opener().open(request, timeout=timeout) as reply:
            headers = {k.lower(): v for k, v in reply.headers.items()}
            return Response(reply.status, headers, reply.read(limit + 1))
    except urllib.error.HTTPError as error:  # a 4xx/5xx is still a response
        with error:
            headers = {k.lower(): v for k, v in error.headers.items()}
            return Response(error.code, headers, error.read(limit + 1))


# --- typed results --------------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckRun:
    id: int
    html_url: str


@dataclass(frozen=True)
class Comment:
    id: int
    body: str
    author: str  # the user's login ("" for a deleted account)
    html_url: str
    created_at: str


@dataclass(frozen=True)
class Issue:
    number: int
    title: str
    body: str
    is_pull_request: bool


@dataclass(frozen=True)
class Artifact:
    id: int
    name: str
    size: int
    expired: bool
    created_at: str
    run_id: int  # the workflow run that uploaded it (0 when GitHub doesn't say)


@dataclass(frozen=True)
class WorkflowRun:
    id: int
    path: str  # the workflow file, e.g. ".github/workflows/tracefix.yml"
    event: str
    head_repo: str  # the repository the run's commit came from ("" when GitHub doesn't say)


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise GitHubError(0, "unexpected response: not a JSON object")
    return value


def _int(data: Mapping[str, object], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise GitHubError(0, f"unexpected response: {key!r} is not a number")
    return value


def _str(data: Mapping[str, object], key: str) -> str:
    """A text field; a missing or null one (a PR with no description) is ""."""
    value = data.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise GitHubError(0, f"unexpected response: {key!r} is not text")
    return value


def _comment(value: object) -> Comment:
    data = _object(value)
    user = data.get("user")
    author = _str(user, "login") if isinstance(user, dict) else ""
    return Comment(
        _int(data, "id"),
        _str(data, "body"),
        author,
        _str(data, "html_url"),
        _str(data, "created_at"),
    )


def _artifact(value: object) -> Artifact:
    data = _object(value)
    run = data.get("workflow_run")
    run_id = run.get("id") if isinstance(run, dict) else None
    return Artifact(
        _int(data, "id"),
        _str(data, "name"),
        _int(data, "size_in_bytes"),
        data.get("expired") is True,
        _str(data, "created_at"),
        run_id if isinstance(run_id, int) and not isinstance(run_id, bool) else 0,
    )


def _message(response: Response) -> str:
    """GitHub's own error message, on one line and capped, else the bare status."""
    try:
        text = _str(_object(json.loads(response.body)), "message")
    except (ValueError, GitHubError):
        text = ""
    text = " ".join(text.split())[:MAX_MESSAGE_CHARS]
    return text or f"HTTP {response.status}"


# --- the client -----------------------------------------------------------------------------------


class GitHub:
    """One repository's API, with one token."""

    def __init__(
        self,
        token: str,
        repo: str,
        *,
        api_url: str | None = None,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not _REPO.fullmatch(repo) or ".." in repo:
            raise ValueError(f"not an owner/name repository: {repo!r}")
        base = (api_url or os.environ.get("GITHUB_API_URL") or DEFAULT_API).rstrip("/")
        if not base.startswith(("https://", "http://")):
            raise ValueError(f"not an http(s) API URL: {base!r}")
        self.api = base
        self._token = token
        self._repo = f"/repos/{repo}"
        self._transport = transport
        self._sleep = sleep
        self._clock = clock

    # --- endpoints (only the ones the Action uses) ---

    def create_check_run(self, fields: Mapping[str, object]) -> CheckRun:
        data = _object(self._json("POST", f"{self._repo}/check-runs", fields))
        return CheckRun(_int(data, "id"), _str(data, "html_url"))

    def list_comments(self, issue: int) -> list[Comment]:
        return [_comment(c) for c in self._pages(f"{self._repo}/issues/{issue}/comments", None)]

    def create_comment(self, issue: int, body: str) -> Comment:
        return _comment(self._json("POST", f"{self._repo}/issues/{issue}/comments", {"body": body}))

    def update_comment(self, comment_id: int, body: str) -> Comment:
        path = f"{self._repo}/issues/comments/{comment_id}"
        return _comment(self._json("PATCH", path, {"body": body}))

    def get_issue(self, number: int) -> Issue:
        data = _object(self._json("GET", f"{self._repo}/issues/{number}"))
        return Issue(
            _int(data, "number"), _str(data, "title"), _str(data, "body"), "pull_request" in data
        )

    def get_user(self) -> str:
        """The token's own login (403 for the Actions token, which is not a user)."""
        return _str(_object(self._json("GET", "/user")), "login")

    def list_artifacts(self, name: str) -> list[Artifact]:
        path = f"{self._repo}/actions/artifacts?{urlencode({'name': name})}"
        return [_artifact(a) for a in self._pages(path, "artifacts")]

    def download_artifact(self, artifact_id: int) -> bytes:
        """The artifact's zip (GitHub redirects to blob storage; the token stays behind)."""
        path = f"{self._repo}/actions/artifacts/{artifact_id}/zip"
        return self._call("GET", self.api + path, None, MAX_ZIP_BYTES).body

    def get_workflow_run(self, run_id: int) -> WorkflowRun:
        data = _object(self._json("GET", f"{self._repo}/actions/runs/{run_id}"))
        head = data.get("head_repository")
        head_repo = _str(head, "full_name") if isinstance(head, dict) else ""
        return WorkflowRun(_int(data, "id"), _str(data, "path"), _str(data, "event"), head_repo)

    def remove_label(self, issue: int, label: str) -> None:
        self._json("DELETE", f"{self._repo}/issues/{issue}/labels/{quote(label, safe='')}")

    # --- plumbing ---

    def _json(self, method: str, path: str, body: Mapping[str, object] | None = None) -> object:
        return self._decode(self._call(method, self.api + path, body, MAX_JSON_BYTES))

    def _pages(self, path: str, key: str | None) -> list[object]:
        """Every item of a list endpoint, following `Link: rel="next"` (at most MAX_PAGES)."""
        sep = "&" if "?" in path else "?"
        url: str | None = f"{self.api}{path}{sep}per_page={PER_PAGE}"
        items: list[object] = []
        for _ in range(MAX_PAGES):
            if url is None:
                break
            response = self._call("GET", url, None, MAX_JSON_BYTES)
            data = self._decode(response)
            page = data if key is None else _object(data).get(key)
            if not isinstance(page, list):
                raise GitHubError(0, "unexpected response: not a list")
            items.extend(page)
            url = self._next(response)
        return items

    def _next(self, response: Response) -> str | None:
        found = _NEXT.search(response.headers.get("link", ""))
        if found is None:
            return None
        url = found.group(1)
        if not url.startswith(self.api + "/"):  # the token goes only to the API itself
            raise GitHubError(0, "a pagination link points away from the API")
        return url

    def _decode(self, response: Response) -> object:
        if not response.body.strip():
            return {}
        try:
            return json.loads(response.body)
        except ValueError:
            raise GitHubError(0, "unexpected response: not JSON") from None

    def _call(
        self, method: str, url: str, body: Mapping[str, object] | None, limit: int
    ) -> Response:
        """One request; a GET retried on a 5xx or a dropped connection (a write may have reached
        GitHub before its answer was lost: never sent twice); a rate limit waited out once."""
        data = None if body is None else json.dumps(body).encode("utf-8")
        retries = method == "GET"
        waited = False
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._transport(self._request(method, url, data), TIMEOUT_S, limit)
            except (OSError, http.client.HTTPException) as error:
                if retries and attempt < ATTEMPTS:
                    self._sleep(float(attempt))
                    continue
                raise GitHubError(0, f"no response from {method} {_where(url)}: {error}") from None
            if len(response.body) > limit:
                raise GitHubError(response.status, f"response over {limit:,} bytes")
            if 200 <= response.status < 300:
                return response
            wait = None if waited else self._rate_wait(response)
            if wait is not None:
                waited = True
                attempt -= 1  # the wait is not one of the attempts
                self._sleep(wait)
                continue
            if response.status >= 500 and retries and attempt < ATTEMPTS:
                self._sleep(float(attempt))
                continue
            raise GitHubError(response.status, f"{method} {_where(url)}: {_message(response)}")

    def _rate_wait(self, response: Response) -> float | None:
        """Seconds to wait before one retry, or None (not a rate limit, or too long a wait)."""
        if response.status not in (403, 429):
            return None
        headers = response.headers
        wait: float | None = None
        if headers.get("retry-after", "").strip().isdigit():
            wait = float(headers["retry-after"])
        elif headers.get("x-ratelimit-remaining") == "0":
            reset = headers.get("x-ratelimit-reset", "")
            wait = max(0.0, float(reset) - self._clock()) if reset.isdigit() else MAX_WAIT_S
        elif response.status == 429:
            wait = MAX_WAIT_S
        return wait if wait is not None and wait <= MAX_WAIT_S else None

    def _request(self, method: str, url: str, data: bytes | None) -> urllib.request.Request:
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", API_VERSION)
        request.add_header("User-Agent", "tracefix")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        # Unredirected: urllib copies only the other headers onto a redirect's new request.
        request.add_unredirected_header("Authorization", f"Bearer {self._token}")
        return request


def _where(url: str) -> str:
    """The URL's path, without the query (for messages)."""
    return url.split("?", 1)[0]
