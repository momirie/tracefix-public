"""A loopback fake of the GitHub REST API, for tests (plan P9; also the Action's end-to-end test).

Two servers on 127.0.0.1: the API, and a "blob storage" host the artifact download redirects to
(like GitHub's). The API checks the token; the blob host refuses any Authorization header, as
blob storage with a signed URL does, and records what arrived. Only the endpoints
`tracefix.github_api` uses exist. State is plain lists and dicts the test sets up and reads back;
`queued` replies are served first, in order (failures, rate limits). The default suite blocks
outgoing connections in the test process, so clients run in a subprocess (servers only accept),
or in-process through `transport()`, which calls the fake directly and follows a redirect the way
urllib does (only the request's redirectable headers go along).
"""

from __future__ import annotations

import json
import re
import socketserver
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlsplit
from urllib.request import Request

from tracefix.github_api import Response, Transport

IN_PROCESS_API = "http://api.fake"
IN_PROCESS_BLOB = "http://blob.fake"


@dataclass(frozen=True)
class Seen:
    host: str  # "api" or "blob"
    method: str
    path: str  # with the query
    authorization: str | None
    body: Any  # the parsed JSON body, or None


@dataclass
class FakeGitHub:
    repo: str = "owner/repo"
    token: str = "ghs_fake_token"
    login: str | None = "github-actions[bot]"  # None: GET /user is 403, as for the Actions token
    per_page_cap: int = 100
    seen: list[Seen] = field(default_factory=list)
    check_runs: list[dict[str, Any]] = field(default_factory=list)
    comments: list[dict[str, Any]] = field(default_factory=list)
    issues: dict[int, dict[str, Any]] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    zips: dict[int, bytes] = field(default_factory=dict)
    runs: dict[int, dict[str, Any]] = field(default_factory=dict)
    labels: dict[int, list[str]] = field(default_factory=dict)
    queued: list[tuple[int, dict[str, str], bytes]] = field(default_factory=list)
    api_url: str = ""
    blob_url: str = ""
    _ids: int = 1000
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # --- setting up state ---

    def _next_id(self) -> int:
        self._ids += 1
        return self._ids

    def add_comment(self, issue: int, body: str, author: str) -> dict[str, Any]:
        number = self._next_id()
        comment = {
            "id": number,
            "issue": issue,
            "body": body,
            "user": {"login": author},
            "html_url": f"https://github.com/{self.repo}/pull/{issue}#issuecomment-{number}",
            "created_at": f"2026-10-14T10:{number % 60:02d}:00Z",
        }
        self.comments.append(comment)
        return comment

    def add_artifact(
        self, name: str, data: bytes, run_id: int, *, expired: bool = False
    ) -> dict[str, Any]:
        number = self._next_id()
        artifact = {
            "id": number,
            "name": name,
            "size_in_bytes": len(data),
            "expired": expired,
            "created_at": f"2026-10-14T11:{number % 60:02d}:00Z",
            "workflow_run": {"id": run_id},
        }
        self.artifacts.append(artifact)
        self.zips[number] = data
        return artifact

    @contextmanager
    def serve(self) -> Iterator[FakeGitHub]:
        api, blob = _server(self, "api"), _server(self, "blob")
        self.api_url = f"http://127.0.0.1:{api.server_address[1]}"
        self.blob_url = f"http://127.0.0.1:{blob.server_address[1]}"
        threads = [
            threading.Thread(target=s.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
            for s in (api, blob)
        ]
        for thread in threads:
            thread.start()
        try:
            yield self
        finally:
            for server in (api, blob):
                server.shutdown()
                server.server_close()

    def transport(self) -> Transport:
        """A `github_api.Transport` that answers in-process (no socket): use the client with
        `api_url=IN_PROCESS_API`."""
        self.api_url, self.blob_url = IN_PROCESS_API, IN_PROCESS_BLOB

        def call(request: Request, timeout: float, limit: int) -> Response:
            headers = {k.lower(): v for k, v in request.header_items()}
            body = json.loads(request.data) if isinstance(request.data, bytes) else None
            status, extra, data = self.answer(
                "api", request.get_method(), _target(request.full_url), headers, body
            )
            if status in (301, 302, 307) and extra["location"].startswith(IN_PROCESS_BLOB):
                moved = {k.lower(): v for k, v in request.headers.items()}  # not unredirected
                status, extra, data = self.answer(
                    "blob", "GET", _target(extra["location"]), moved, None
                )
            return Response(status, extra, data[: limit + 1])

        return call

    # --- answering ---

    def answer(
        self, host: str, method: str, target: str, headers: dict[str, str], body: Any
    ) -> tuple[int, dict[str, str], bytes]:
        with self._lock:
            self.seen.append(Seen(host, method, target, headers.get("authorization"), body))
            if host == "blob":
                return self._blob(target, headers)
            if headers.get("authorization") != f"Bearer {self.token}":
                return _json(401, {"message": "Bad credentials"})
            if self.queued:
                return self.queued.pop(0)
            return self._api(method, target, body)

    def _blob(self, target: str, headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
        found = re.fullmatch(r"/blob/(\d+)", urlsplit(target).path)
        if "authorization" in headers:  # signed-URL storage rejects a second credential
            return 400, {}, b"Authorization header not allowed"
        if found is None or int(found.group(1)) not in self.zips:
            return 404, {}, b""
        return 200, {"content-type": "application/zip"}, self.zips[int(found.group(1))]

    def _api(self, method: str, target: str, body: Any) -> tuple[int, dict[str, str], bytes]:
        parts = urlsplit(target)
        path, query = parts.path, parse_qs(parts.query)
        if method == "GET" and path == "/user":
            if self.login is None:
                return _json(403, {"message": "Resource not accessible by integration"})
            return _json(200, {"login": self.login})
        prefix = f"/repos/{self.repo}"
        if not path.startswith(prefix + "/"):
            return _json(404, {"message": "Not Found"})
        rest = path[len(prefix) :]
        for route_method, pattern, handler in self._routes():
            found = re.fullmatch(pattern, rest)
            if found and route_method == method:
                return handler(found, query, body)
        return _json(404, {"message": "Not Found"})

    def _routes(self) -> list[tuple[str, str, Any]]:
        return [
            ("POST", r"/check-runs", self._create_check_run),
            ("GET", r"/issues/(\d+)/comments", self._list_comments),
            ("POST", r"/issues/(\d+)/comments", self._create_comment),
            ("PATCH", r"/issues/comments/(\d+)", self._update_comment),
            ("GET", r"/issues/(\d+)", self._get_issue),
            ("DELETE", r"/issues/(\d+)/labels/([^/]+)", self._remove_label),
            ("GET", r"/actions/artifacts", self._list_artifacts),
            ("GET", r"/actions/artifacts/(\d+)/zip", self._download),
            ("GET", r"/actions/runs/(\d+)", self._get_run),
        ]

    def _create_check_run(self, found: Any, query: Any, body: Any) -> tuple[int, dict, bytes]:
        number = self._next_id()
        run = {**body, "id": number, "html_url": f"https://github.com/{self.repo}/runs/{number}"}
        self.check_runs.append(run)
        return _json(201, run)

    def _list_comments(self, found: Any, query: Any, body: Any) -> tuple[int, dict, bytes]:
        issue = int(found.group(1))
        mine = [_public(c) for c in self.comments if c["issue"] == issue]
        return self._page(f"/repos/{self.repo}/issues/{issue}/comments", query, mine, None)

    def _create_comment(self, found: Any, query: Any, body: Any) -> tuple[int, dict, bytes]:
        login = self.login or "github-actions[bot]"
        return _json(201, _public(self.add_comment(int(found.group(1)), body["body"], login)))

    def _update_comment(self, found: Any, query: Any, body: Any) -> tuple[int, dict, bytes]:
        for comment in self.comments:
            if comment["id"] == int(found.group(1)):
                comment["body"] = body["body"]
                return _json(200, _public(comment))
        return _json(404, {"message": "Not Found"})

    def _get_issue(self, found: Any, query: Any, body: Any) -> tuple[int, dict, bytes]:
        issue = self.issues.get(int(found.group(1)))
        return _json(200, issue) if issue else _json(404, {"message": "Not Found"})

    def _remove_label(self, found: Any, query: Any, body: Any) -> tuple[int, dict, bytes]:
        labels = self.labels.get(int(found.group(1)), [])
        name = unquote(found.group(2))
        if name not in labels:
            return _json(404, {"message": "Label does not exist"})
        labels.remove(name)
        return _json(200, [{"name": n} for n in labels])

    def _list_artifacts(self, found: Any, query: Any, body: Any) -> tuple[int, dict, bytes]:
        name = query.get("name", [None])[0]
        chosen = [a for a in self.artifacts if name is None or a["name"] == name]
        extra = {} if name is None else {"name": name}
        return self._page(f"/repos/{self.repo}/actions/artifacts", query, chosen, extra)

    def _download(self, found: Any, query: Any, body: Any) -> tuple[int, dict, bytes]:
        number = int(found.group(1))
        if number not in self.zips:
            return _json(404, {"message": "Not Found"})
        return 302, {"location": f"{self.blob_url}/blob/{number}?sig=signed"}, b""

    def _get_run(self, found: Any, query: Any, body: Any) -> tuple[int, dict, bytes]:
        run = self.runs.get(int(found.group(1)))
        return _json(200, run) if run else _json(404, {"message": "Not Found"})

    def _page(
        self, path: str, query: Any, items: list[Any], extra: dict[str, str] | None
    ) -> tuple[int, dict[str, str], bytes]:
        """One page; `extra` is not None for an envelope endpoint (`{total_count, artifacts}`)."""
        per_page = min(int(query.get("per_page", ["30"])[0]), self.per_page_cap)
        page = int(query.get("page", ["1"])[0])
        chunk = items[(page - 1) * per_page : page * per_page]
        headers = {}
        if page * per_page < len(items):
            params = {**(extra or {}), "per_page": str(per_page), "page": str(page + 1)}
            headers["link"] = f'<{self.api_url}{path}?{urlencode(params)}>; rel="next"'
        payload: Any = chunk if extra is None else {"total_count": len(items), "artifacts": chunk}
        status, base, data = _json(200, payload)
        return status, {**base, **headers}, data


def _target(url: str) -> str:
    parts = urlsplit(url)
    return parts.path + (f"?{parts.query}" if parts.query else "")


def _public(comment: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in comment.items() if k != "issue"}


def _json(status: int, payload: Any) -> tuple[int, dict[str, str], bytes]:
    return status, {"content-type": "application/json"}, json.dumps(payload).encode("utf-8")


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)  # no getfqdn: no name lookup for 127.0.0.1
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]


def _server(fake: FakeGitHub, host: str) -> _Server:
    class Handler(BaseHTTPRequestHandler):
        def _handle(self) -> None:
            length = int(self.headers.get("content-length") or 0)
            raw = self.rfile.read(length) if length else b""
            headers = {k.lower(): v for k, v in self.headers.items()}
            body = json.loads(raw) if raw else None
            status, extra, data = fake.answer(host, self.command, self.path, headers, body)
            self.send_response(status)
            for name, value in extra.items():
                self.send_header(name, value)
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PATCH = do_DELETE = _handle

        def log_message(self, format: str, *args: Any) -> None:
            pass  # quiet test output

    return _Server(("127.0.0.1", 0), Handler)
