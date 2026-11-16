"""The GitHub Action's steps (plan P1-P6): `python -m tracefix.action prepare|verify|report`.

`prepare` runs first, before any test, with the GitHub token but never the model API key. It
decides whether this run verifies anything and how far the pull request's author is trusted, finds
the two commits, writes the issue text to a file, fetches the last receipt of this pull request
for the replay, and records all of it in `$RUNNER_TEMP/tracefix/receipt/state.json` for the later
steps (it travels with the receipt artifact, which the fork flow's report job reads).

`verify` runs `tracefix verify` with the model API key and no token, and adds its exit code and
last error line to the state. `report` runs with the token and no key: it checks that the state
and the receipt belong to this run, then posts the check run, edits the one PR comment, and writes
the step's outputs and the job summary (`action_report` computes all of it).

Trust (P2): a pull request from a branch of the same repository, or a run started by someone with
write access (workflow_dispatch, push, schedule), is trusted: GitHub already gave that workflow
the repository's secrets. Everything else is untrusted: `pull_request_target`, a pull request from
another repository, any other event, or the `trust: untrusted` input (which can only tighten).
An untrusted run needs strict isolation, and is refused when the pull request's code is already in
the checkout: its commits are fetched as git data only, and run only inside bubblewrap.

Event payloads, pull request text, issue text, API answers and artifacts are all untrusted data:
they are parsed and written to files, never run by a shell and never printed raw (a line printed
by a step can be a workflow command).
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import io
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import zipfile
import zlib
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal, TextIO, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tracefix import action_report as ar
from tracefix import cli, sandbox
from tracefix.cli import MAX_ISSUE_CHARS
from tracefix.github_api import MAX_ZIP_BYTES, Artifact, GitHub, GitHubError
from tracefix.llm import Provider
from tracefix.previous import MAX_FINDING_CHARS, MAX_FINDINGS, MAX_OPEN, MAX_RECEIPT_BYTES, UNUSABLE
from tracefix.receipt import Receipt
from tracefix.workspace import WorkspaceError, git, git_run, require_repo, resolve_ref

Trust = Literal["trusted", "untrusted"]
MinLevel = Literal["", "L1", "L2", "L3", "L4"]
TRUSTED_EVENTS = frozenset({"pull_request", "workflow_dispatch", "push", "schedule"})
ARTIFACT_PREFIX = "tracefix-receipt-pr-"
MAX_CLOSED_ISSUES = 3
MAX_RUN_LOOKUPS = 10  # earlier artifacts of ours checked for a receipt
MAX_RUN_QUERIES = 100  # workflow runs looked up to find ours among same-named artifacts
MAX_EVENT_BYTES = 25_000_000
MAX_STATE_BYTES = 1_000_000
MAX_ZIP_ENTRIES = 1_000
MAX_NOTE_CHARS = 500
MAX_NOTES = 20
MAX_MESSAGE_CHARS = 1_000
RECEIPT = "receipt"  # the receipt folder in $RUNNER_TEMP/tracefix (uploaded as the artifact)
FETCHED_REF = "refs/tracefix/pull-head"
# The outputs each step writes (action.yml maps the action's outputs onto these).
OUTPUTS = {
    "prepare": frozenset({"receipt-dir", "artifact-name", "skip"}),
    "report": frozenset({"level", "status", "conclusion", "receipt-dir", "check-run-url",
                         "comment-url"}),
}  # fmt: skip
_SHA_PATTERN = r"^[0-9a-f]{40}([0-9a-f]{24})?$"
_SHA = re.compile(_SHA_PATTERN)
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_KEEP = re.compile(r"receipt\.json|state\.json|findings/(?:finding|previous)_[1-9][0-9]{0,2}\.py")
_KEEP_LIMITS = {
    "receipt.json": MAX_RECEIPT_BYTES,
    "state.json": MAX_STATE_BYTES,
    "finding": 4 * MAX_FINDING_CHARS,  # UTF-8 bytes of at most MAX_FINDING_CHARS characters
}
# GitHub's closing keywords, then `#N`, `owner/repo#N` or an issue URL (checked against this repo).
_CLOSING = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)(?:\s*:\s*|\s+)"
    r"(?:#(?P<number>[0-9]{1,9})"
    r"|(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#(?P<cross>[0-9]{1,9})"
    r"|(?P<url>https?://[^\s/]+/[^\s/]+/[^\s/]+)/issues/(?P<linked>[0-9]{1,9}))(?![\w#/-])",
    re.IGNORECASE,
)


class ActionError(Exception):
    """A misconfiguration (bad input, no checkout, a missing variable): the step fails."""


class Skip(Exception):
    """Nothing is verified on this run, for this reason (a neutral check, never a failure)."""


# --- the event and the inputs ---------------------------------------------------------------------


@dataclass(frozen=True)
class PullRequest:
    number: int
    base_sha: str
    head_sha: str
    head_repo: str  # "owner/name" of the head branch's repository ("" for a deleted fork)
    title: str
    body: str


@dataclass(frozen=True)
class Event:
    name: str
    action: str
    pr: PullRequest | None
    label: str  # the label just added (a `labeled` action), else ""


@dataclass(frozen=True)
class Inputs:
    issue: str = ""
    base: str = ""
    head: str = ""
    config: str = ""
    min_level: MinLevel = ""
    trust: str = "auto"
    comment: bool = True
    annotations: bool = True
    previous: bool = True
    report: bool = True
    has_api_key: bool = False


@dataclass(frozen=True)
class Context:
    repo: str
    workspace: Path
    temp: Path  # $RUNNER_TEMP/tracefix: state, issue text, the receipt, the last receipt
    server_url: str
    api_url: str
    run_id: int
    workflow_path: str  # e.g. ".github/workflows/tracefix.yml" ("" when unknown)
    token: str
    event: Event
    inputs: Inputs

    @property
    def run_url(self) -> str:
        return f"{self.server_url}/{self.repo}/actions/runs/{self.run_id}"


def _field(data: object, *keys: str) -> object:
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _text(data: object, *keys: str) -> str:
    value = _field(data, *keys)
    return _encodable(value) if isinstance(value, str) else ""


def _encodable(text: str) -> str:
    """`text` with lone surrogates (JSON allows `"\\ud800"`) made `?`, so it can be written."""
    return text.encode("utf-8", errors="replace").decode("utf-8")


def _pull_request(payload: object) -> PullRequest | None:
    pr = _field(payload, "pull_request")
    if not isinstance(pr, dict):
        return None
    number = pr.get("number")
    base, head = _text(pr, "base", "sha"), _text(pr, "head", "sha")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise ActionError("the event's pull request has no number")
    if not (_SHA.fullmatch(base) and _SHA.fullmatch(head)):
        raise ActionError("the event's pull request has no base and head commit ids")
    return PullRequest(
        number,
        base,
        head,
        _text(pr, "head", "repo", "full_name"),
        _text(pr, "title"),
        _text(pr, "body"),
    )


def read_event(name: str, path: str) -> Event:
    """The event that started the workflow, from GitHub's payload file (only the fields used)."""
    if not re.fullmatch(r"[a-z_]{1,50}", name):
        raise ActionError(f"GITHUB_EVENT_NAME is not an event name: {name!r}")
    payload: object = {}
    if path:
        try:
            with open(path, "rb") as handle:
                raw = handle.read(MAX_EVENT_BYTES + 1)
            if len(raw) > MAX_EVENT_BYTES:
                raise ActionError("the event payload is too large")
            payload = json.loads(raw)
        except (OSError, ValueError) as exc:
            raise ActionError(f"can't read the event payload: {exc}") from None
    label = _text(payload, "label", "name") if _text(payload, "action") == "labeled" else ""
    return Event(name, _text(payload, "action"), _pull_request(payload), label)


def _flag(env: Mapping[str, str], name: str, default: bool) -> bool:
    value = env.get(name, "").strip().lower()
    if not value:
        return default
    if value not in ("true", "false"):
        raise ActionError(f"input {_input_name(name)} must be true or false, not {value!r}")
    return value == "true"


def _input_name(variable: str) -> str:
    return variable.removeprefix("INPUT_").lower().replace("_", "-")


def read_inputs(env: Mapping[str, str]) -> Inputs:
    """The action's inputs, passed by action.yml as INPUT_* variables (never inside a script)."""
    trust = env.get("INPUT_TRUST", "").strip().lower() or "auto"
    if trust == "trusted":
        raise ActionError("input trust can only make a run stricter: use auto or untrusted")
    if trust not in ("auto", "untrusted"):
        raise ActionError(f"input trust must be auto or untrusted, not {trust!r}")
    min_level = env.get("INPUT_MIN_LEVEL", "").strip().upper()
    if min_level and min_level not in ("L1", "L2", "L3", "L4"):
        raise ActionError(f"input min-level must be one of L1, L2, L3, L4, not {min_level!r}")
    return Inputs(
        issue=env.get("INPUT_ISSUE", ""),
        base=env.get("INPUT_BASE", "").strip(),
        head=env.get("INPUT_HEAD", "").strip(),
        config=env.get("INPUT_CONFIG", "").strip(),
        min_level=cast(MinLevel, min_level),
        trust=trust,
        comment=_flag(env, "INPUT_COMMENT", True),
        annotations=_flag(env, "INPUT_ANNOTATIONS", True),
        previous=_flag(env, "INPUT_PREVIOUS", True),
        report=_flag(env, "INPUT_REPORT", True),
        has_api_key=_flag(env, "INPUT_HAS_API_KEY", False),
    )


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "")
    if not value:
        raise ActionError(f"{name} is not set: run Tracefix as a step of a GitHub Actions job")
    return value


def _workflow_path(env: Mapping[str, str], repo: str) -> str:
    """The workflow file from GITHUB_WORKFLOW_REF (`owner/repo/.github/workflows/x.yml@ref`)."""
    ref = env.get("GITHUB_WORKFLOW_REF", "")
    prefix = repo + "/"
    if not ref.lower().startswith(prefix.lower()) or "@" not in ref:
        return ""
    return ref[len(prefix) :].rsplit("@", 1)[0]


def read_context(env: Mapping[str, str]) -> Context:
    repo = _required(env, "GITHUB_REPOSITORY")
    if not _REPO.fullmatch(repo):
        raise ActionError(f"GITHUB_REPOSITORY is not owner/name: {repo!r}")
    run_id = _required(env, "GITHUB_RUN_ID")
    if not run_id.isdigit():
        raise ActionError(f"GITHUB_RUN_ID is not a number: {run_id!r}")
    token = env.get("INPUT_GITHUB_TOKEN", "")
    if not token:
        raise ActionError("input github-token is empty (its default is the workflow's token)")
    return Context(
        repo=repo,
        workspace=Path(_required(env, "GITHUB_WORKSPACE")),
        temp=Path(_required(env, "RUNNER_TEMP")) / "tracefix",
        server_url=env.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/"),
        api_url=env.get("GITHUB_API_URL", ""),
        run_id=int(run_id),
        workflow_path=_workflow_path(env, repo),
        token=token,
        event=read_event(_required(env, "GITHUB_EVENT_NAME"), env.get("GITHUB_EVENT_PATH", "")),
        inputs=read_inputs(env),
    )


# --- the state the later steps read ---------------------------------------------------------------

Sha = Annotated[str, Field(pattern=_SHA_PATTERN)]
Note = Annotated[str, Field(max_length=MAX_NOTE_CHARS)]


class State(BaseModel):
    """What prepare decided. The fork flow's report job reads it back from an artifact, so it is
    validated strictly there: every field is bounded, and commit ids are hex."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    version: Literal[1] = 1
    repo: Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")]
    run_id: Annotated[int, Field(ge=0)]
    run_url: Annotated[str, Field(max_length=500)]
    event: Annotated[str, Field(pattern=r"^[a-z_]{1,50}$")]
    trust: Trust
    pr: Annotated[int, Field(ge=1)] | None = None
    base: Sha | None = None
    head: Sha | None = None  # also the commit a skip's check run goes on
    label: Annotated[str, Field(max_length=100)] = ""
    issue_file: Annotated[str, Field(max_length=4096)] = ""
    issue_source: Annotated[str, Field(max_length=200)] = ""
    config: Annotated[str, Field(max_length=4096)] = ""
    previous_dir: Annotated[str, Field(max_length=4096)] = ""
    previous_run: Annotated[int, Field(ge=0)] = 0
    skip: Annotated[str, Field(max_length=1000)] = ""
    notes: Annotated[tuple[Note, ...], Field(max_length=MAX_NOTES)] = ()
    verify_exit: Annotated[int, Field(ge=0, le=255)] | None = None  # None: verify did not finish
    verify_message: Annotated[str, Field(max_length=MAX_MESSAGE_CHARS)] = ""  # its last error


def state_path(temp: Path) -> Path:
    return temp / RECEIPT / "state.json"


def artifact_name(state: State) -> str:
    return f"{ARTIFACT_PREFIX}{state.pr}" if state.pr else f"tracefix-receipt-run-{state.run_id}"


def write_state(path: Path, state: State) -> None:
    path.write_text(state.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")


def read_state(path: Path) -> State:
    with path.open("rb") as handle:
        raw = handle.read(MAX_STATE_BYTES + 1)
    if len(raw) > MAX_STATE_BYTES:
        raise ActionError(f"{path.name} is larger than {MAX_STATE_BYTES:,} bytes")
    try:
        return State.model_validate_json(raw, strict=True)
    except ValidationError as exc:
        raise ActionError(
            f"{path.name} is not a valid state ({exc.error_count()} errors)"
        ) from None


def _note(text: str) -> str:
    return one_line(text, MAX_NOTE_CHARS)


# --- trust and skips ------------------------------------------------------------------------------


def is_fork(ctx: Context) -> bool:
    pr = ctx.event.pr
    return pr is not None and pr.head_repo.lower() != ctx.repo.lower()


def decide_trust(ctx: Context) -> Trust:
    """Trusted only for a same-repository pull request or an event only writers can start; the
    input can make any run untrusted, never the other way round."""
    if ctx.inputs.trust == "untrusted" or ctx.event.name not in TRUSTED_EVENTS:
        return "untrusted"
    return "untrusted" if is_fork(ctx) else "trusted"


def early_skip(ctx: Context, trust: Trust, probe: Callable[[], tuple[str, str]]) -> None:
    """The reasons not to run that need no git and no API (raises Skip)."""
    event, inputs = ctx.event, ctx.inputs
    if event.name == "pull_request" and is_fork(ctx):
        raise Skip(
            "a pull request from a fork gets no secrets on `pull_request`; a maintainer can "
            "verify it through the label flow (pull_request_target, docs/GITHUB_ACTION.md)"
        )
    if event.pr is None and not (inputs.base and inputs.head):
        if inputs.base or inputs.head:
            raise ActionError("set both base and head (there is no pull request in this event)")
        raise Skip(f"a {event.name} event has no pull request; set the base and head inputs")
    if not inputs.has_api_key:
        raise Skip("no model API key: set the anthropic-api-key input from a secret")
    if trust == "untrusted":
        level, why = probe()
        if level != "strict":
            raise Skip(f"an untrusted run needs strict isolation (bubblewrap), but: {why}")


# --- commits --------------------------------------------------------------------------------------


def has_commit(repo: Path, sha: str) -> bool:
    return git_run(repo, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def fetch_command(ctx: Context, number: int) -> tuple[list[str], dict[str, str]]:
    """git's arguments and extra environment for fetching a pull request's head as objects only.
    The token goes in through GIT_CONFIG_* variables, never in argv or .git/config; the first
    entry clears any header actions/checkout stored for the same server."""
    key = f"http.{ctx.server_url}/.extraheader"
    secret = base64.b64encode(f"x-access-token:{ctx.token}".encode()).decode("ascii")
    env = {
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": key,
        "GIT_CONFIG_VALUE_0": "",
        "GIT_CONFIG_KEY_1": key,
        "GIT_CONFIG_VALUE_1": f"AUTHORIZATION: basic {secret}",
    }
    args = [
        "fetch", "--quiet", "--no-tags", "--no-recurse-submodules", "--no-write-fetch-head",
        f"{ctx.server_url}/{ctx.repo}.git", f"+refs/pull/{number}/head:{FETCHED_REF}",
    ]  # fmt: skip
    return args, env


def _fetch_head(ctx: Context, pr: PullRequest) -> None:
    args, env = fetch_command(ctx, pr.number)
    result = git_run(ctx.workspace, *args, extra_env=env)
    if result.returncode != 0:
        why = one_line(result.stderr.decode("utf-8", errors="replace"), 300)
        raise Skip(f"can't fetch pull request #{pr.number}'s commits: {why}")
    if not has_commit(ctx.workspace, pr.head_sha):
        raise Skip(
            f"commit {pr.head_sha[:12]} is no longer on pull request #{pr.number} "
            "(force-pushed?); a newer run verifies the new head"
        )


def workspace_holds(repo: Path, sha: str) -> bool:
    """Whether the checked-out commit already contains `sha` (exit 0 of is-ancestor); any answer
    other than a clear "no" (exit 1) counts as yes."""
    result = git_run(repo, "merge-base", "--is-ancestor", sha, "HEAD")
    return result.returncode != 1


def _resolve(repo: Path, ref: str, what: str) -> str:
    try:
        return resolve_ref(repo, ref)
    except WorkspaceError as exc:
        raise ActionError(f"input {what}: {exc}") from None


def find_commits(ctx: Context, trust: Trust) -> tuple[str, str]:
    """(base, head) as full commit ids: the pull request's merge-base and exact head commit,
    unless the base/head inputs say otherwise."""
    repo, pr, inputs = ctx.workspace, ctx.event.pr, ctx.inputs
    try:
        require_repo(repo)
    except WorkspaceError as exc:
        raise ActionError(f"{exc}: check out the repository first (actions/checkout)") from None
    if git(repo, "rev-parse", "--is-shallow-repository").strip() == "true":
        raise Skip("the checkout is shallow: set `fetch-depth: 0` on actions/checkout")
    if inputs.head:
        head = _resolve(repo, inputs.head, "head")
    else:
        assert pr is not None  # early_skip: no pull request means both inputs are set
        if not has_commit(repo, pr.head_sha):
            _fetch_head(ctx, pr)
        head = pr.head_sha
    if trust == "untrusted" and workspace_holds(repo, head):
        raise Skip(
            "the checkout already holds the pull request's code: an untrusted run must check "
            "out the base branch only (Tracefix fetches the pull request itself)"
        )
    if inputs.base:
        return _resolve(repo, inputs.base, "base"), head
    assert pr is not None
    if not has_commit(repo, pr.base_sha):
        raise Skip(f"the base commit {pr.base_sha[:12]} is not in the checkout")
    found = git_run(repo, "merge-base", pr.base_sha, head)
    base = found.stdout.decode("ascii", errors="replace").strip()
    if found.returncode != 0 or not _SHA.fullmatch(base):
        raise Skip("the pull request's base and head share no commit")
    return base, head


# --- the issue text -------------------------------------------------------------------------------


def closed_issues(text: str, repo: str, server_url: str) -> list[int]:
    """The same-repository issue numbers `text` closes with GitHub's keywords, first ones first,
    at most MAX_CLOSED_ISSUES; references to other repositories or servers are ignored."""
    found: list[int] = []
    for match in _CLOSING.finditer(text):
        if match["number"]:
            number = match["number"]
        elif match["cross"]:
            if match["repo"].lower() != repo.lower():
                continue
            number = match["cross"]
        elif match["url"].lower() == f"{server_url}/{repo}".lower():
            number = match["linked"]
        else:
            continue
        if int(number) > 0 and int(number) not in found:
            found.append(int(number))
    return found[:MAX_CLOSED_ISSUES]


def _issue_section(title: str, body: str) -> str:
    return f"# {title.strip()}\n\n{body.strip()}".strip() + "\n"


def _joined(numbers: Sequence[int]) -> str:
    refs = [f"#{n}" for n in numbers]
    return refs[0] if len(refs) == 1 else ", ".join(refs[:-1]) + " and " + refs[-1]


def issue_text(ctx: Context, github: GitHub, notes: list[str]) -> tuple[str, str]:
    """(text, where it came from): the input, else the issues the pull request closes, else the
    pull request's own title and description."""
    pr = ctx.event.pr
    if ctx.inputs.issue.strip():
        return ctx.inputs.issue, "from the issue input"
    if pr is None:
        raise Skip("no issue text: set the issue input (there is no pull request to read it from)")
    sections: list[str] = []
    used: list[int] = []
    for number in closed_issues(pr.body, ctx.repo, ctx.server_url):
        try:
            issue = github.get_issue(number)
        except GitHubError as exc:
            notes.append(_note(f"can't read issue #{number}: {exc}"))
            continue
        if issue.is_pull_request:
            continue
        sections.append(_issue_section(issue.title, issue.body))
        used.append(number)
    if used:
        return "\n".join(sections), f"from {_joined(used)}"
    return _issue_section(pr.title, pr.body), "from the pull request description"


def write_issue(ctx: Context, text: str, notes: list[str]) -> Path:
    text = _encodable(text).replace("\r\n", "\n").replace("\r", "\n").replace("\0", "")
    if not text.strip():
        raise Skip("the issue text is empty")
    if len(text) > MAX_ISSUE_CHARS:
        text = text[:MAX_ISSUE_CHARS]
        notes.append(_note(f"the issue text was cut to {MAX_ISSUE_CHARS:,} characters"))
    path = ctx.temp / "issue.md"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


# --- the last receipt of this pull request --------------------------------------------------------


class ArtifactError(Exception):
    """The earlier artifact can't be used (the run goes on without the replay)."""


def _newest_first(artifacts: Sequence[Artifact]) -> list[Artifact]:
    """By creation time (an unreadable or zone-less time sorts last), then by id."""

    def key(artifact: Artifact) -> tuple[float, int]:
        try:
            when = datetime.fromisoformat(artifact.created_at)
        except ValueError:
            return float("-inf"), artifact.id
        return (when.timestamp() if when.tzinfo else float("-inf")), artifact.id

    return sorted(artifacts, key=key, reverse=True)


def our_artifacts(ctx: Context, github: GitHub, trust: Trust) -> Iterator[Artifact]:
    """This pull request's receipt artifacts from earlier runs of this same workflow file, in this
    repository (a fork's own `pull_request` run can upload any artifact name, from its own copy of
    the workflow), and from `pull_request_target` runs when this run is untrusted, `pull_request`
    runs otherwise; newest first. ArtifactError past MAX_RUN_LOOKUPS of ours, or MAX_RUN_QUERIES
    runs looked up (others' artifacts don't count toward the first: anyone can upload the name)."""
    pr = ctx.event.pr
    if pr is None or not ctx.workflow_path:
        return
    wanted_event = "pull_request_target" if trust == "untrusted" else "pull_request"
    name = f"{ARTIFACT_PREFIX}{pr.number}"
    candidates = [
        a for a in github.list_artifacts(name) if a.name == name and a.run_id not in (0, ctx.run_id)
    ]
    ours = 0
    for queried, artifact in enumerate(_newest_first(candidates)):
        if ours == MAX_RUN_LOOKUPS or queried == MAX_RUN_QUERIES:
            raise ArtifactError(f"no receipt among this pull request's {ours} newest artifacts "
                                f"from this workflow ({queried} looked up)")  # fmt: skip
        try:
            run = github.get_workflow_run(artifact.run_id)
        except GitHubError as exc:
            if exc.status == 404:  # the run was deleted: not one of ours any more
                continue
            raise
        if (
            run.id == artifact.run_id
            and run.path == ctx.workflow_path
            and run.head_repo.lower() == ctx.repo.lower()
            and run.event == wanted_event
        ):
            ours += 1
            yield artifact


def _artifact_state(files: Mapping[str, bytes], artifact: Artifact, pr: int) -> State:
    try:
        state = State.model_validate_json(files["state.json"], strict=True)
    except ValidationError:
        raise ArtifactError("its state.json is not a valid state") from None
    if state.run_id != artifact.run_id or state.pr != pr:
        raise ArtifactError("its state.json is not from the run that uploaded it")
    return state


def last_receipt(ctx: Context, github: GitHub, trust: Trust,
                 notes: list[str]) -> tuple[dict[str, bytes], int] | None:  # fmt: skip
    """The files and run id of the newest receipt among `our_artifacts`, or None when there is
    none. A run that wrote no receipt (a skip, exit 2 or 3, a cancelled verify) is passed over:
    it showed nothing fixed, so the receipt before it still holds the open findings. The newest
    receipt that can't be used is never passed over (ArtifactError: the replay is inconclusive)."""
    pr = ctx.event.pr
    assert pr is not None
    for artifact in our_artifacts(ctx, github, trust):
        if artifact.expired:  # GitHub deleted it after the retention period: a fresh start
            notes.append(_note(f"the last receipt (run {artifact.run_id}) has expired, so its "
                               "findings were not replayed"))  # fmt: skip
            return None
        if not 0 < artifact.size <= MAX_ZIP_BYTES:
            raise ArtifactError(f"run {artifact.run_id}'s artifact is {artifact.size:,} bytes "
                                f"(at most {MAX_ZIP_BYTES:,})")  # fmt: skip
        files = unpack_receipt(github.download_artifact(artifact.id))
        state = _artifact_state(files, artifact, pr.number)
        if state.skip or state.verify_exit != cli.EXIT_OK:
            continue
        if "receipt.json" not in files:
            raise ArtifactError(f"run {artifact.run_id}'s artifact holds no receipt.json")
        return files, artifact.run_id
    return None


def _kept(info: zipfile.ZipInfo) -> int | None:
    """The size limit of a member we keep, or None for one we skip."""
    if info.is_dir() or not _KEEP.fullmatch(info.filename):
        return None
    return _KEEP_LIMITS.get(info.filename, _KEEP_LIMITS["finding"])


def unpack_receipt(data: bytes) -> dict[str, bytes]:
    """state.json, receipt.json and findings/finding_<n>.py or previous_<n>.py from an artifact
    zip, read in memory with a size limit each. Every other member is skipped; a repeated name, an
    encrypted member or a damaged zip makes the whole artifact unusable."""
    if len(data) > MAX_ZIP_BYTES:
        raise ArtifactError(f"the zip is larger than {MAX_ZIP_BYTES:,} bytes")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_ENTRIES:
                raise ArtifactError(f"the zip has more than {MAX_ZIP_ENTRIES:,} entries")
            names = [i.filename for i in infos]
            if len(set(names)) != len(names):
                raise ArtifactError("the zip names one file twice")
            files: dict[str, bytes] = {}
            for info in infos:
                limit = _kept(info)
                if limit is None:
                    continue
                if info.flag_bits & 0x1:
                    raise ArtifactError(f"{info.filename} is encrypted")
                if info.file_size > limit:
                    raise ArtifactError(f"{info.filename} is larger than {limit:,} bytes")
                with archive.open(info) as member:
                    content = member.read(limit + 1)  # never trust the declared size
                if len(content) > limit:
                    raise ArtifactError(f"{info.filename} is larger than {limit:,} bytes")
                files[info.filename] = content
    except (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error, EOFError,
            NotImplementedError, RuntimeError, ValueError, OSError) as exc:  # fmt: skip
        raise ArtifactError(f"the zip can't be read ({type(exc).__name__})") from None
    if "state.json" not in files:
        raise ArtifactError("the zip holds no state.json")
    if sum(name.startswith("findings/finding_") for name in files) > MAX_FINDINGS:
        raise ArtifactError(f"the zip holds more than {MAX_FINDINGS} finding files")
    if sum(name.startswith("findings/previous_") for name in files) > MAX_OPEN:
        raise ArtifactError(f"the zip holds more than {MAX_OPEN} earlier finding files")
    return files


def _transient(exc: GitHubError) -> bool:
    """No answer, a server error or a rate limit: a re-run may work."""
    return exc.status == 0 or exc.status == 429 or exc.status >= 500


def fetch_previous(ctx: Context, github: GitHub, trust: Trust, notes: list[str]) -> tuple[str, int]:
    """(folder, run id) for `--previous`: the last receipt of this pull request, written to a
    fresh folder; or, when it exists but can't be used, a folder holding only UNUSABLE (the
    replay is then inconclusive, which keeps L4 out of reach); ("", 0) when there is none. Skip
    when GitHub did not answer (a re-run can find it); ActionError when it refused (a missing
    permission: the job must be fixed, not the receipt chain broken)."""
    if not ctx.inputs.previous or ctx.event.pr is None:
        return "", 0
    folder = Path(tempfile.mkdtemp(prefix="previous-", dir=ctx.temp))
    try:
        found = last_receipt(ctx, github, trust, notes)
    except GitHubError as exc:
        if _transient(exc):
            raise Skip(f"can't look up the last receipt of this pull request ({exc}); "
                       "re-run the job") from None  # fmt: skip
        hint = "the job needs `permissions: actions: read` (or the previous input false)"
        raise ActionError(f"can't read the last receipt: {exc}; {hint}") from None
    except ArtifactError as exc:
        why = one_line(str(exc), MAX_NOTE_CHARS)
        notes.append(_note(f"the last receipt can't be used, so the replay is inconclusive: {why}"))
        (folder / UNUSABLE).write_text(why + "\n", encoding="utf-8")
        return str(folder), 0
    if found is None:
        folder.rmdir()
        return "", 0
    files, run_id = found
    (folder / "findings").mkdir()
    for name, content in files.items():
        (folder / name).write_bytes(content)
    return str(folder), run_id


# --- the step -------------------------------------------------------------------------------------


def one_line(text: str, limit: int) -> str:
    """Printable, on one line, at most `limit` characters."""
    flat = " ".join("".join(c if c.isprintable() else " " for c in text).split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


def prepare(
    ctx: Context, github: GitHub, *, probe: Callable[[], tuple[str, str]] = sandbox.probe
) -> State:
    """Decide and record what this run verifies (a skip is a state too, never an exception)."""
    if ctx.temp.exists():  # an earlier step of this job left files: none may be reported again
        shutil.rmtree(ctx.temp)
    ctx.temp.mkdir(parents=True)
    trust = decide_trust(ctx)
    pr = ctx.event.pr
    state = State(
        repo=ctx.repo,
        run_id=ctx.run_id,
        run_url=ctx.run_url,
        event=ctx.event.name,
        trust=trust,
        pr=pr.number if pr else None,
        head=pr.head_sha if pr else None,
        label=ctx.event.label[:100],
        config=ctx.inputs.config,
    )
    notes: list[str] = []
    try:
        early_skip(ctx, trust, probe)
        base, head = find_commits(ctx, trust)
        state = replace_state(state, base=base, head=head)
        text, source = issue_text(ctx, github, notes)
        issue_file = write_issue(ctx, text, notes)
        previous_dir, previous_run = fetch_previous(ctx, github, trust, notes)
    except Skip as skip:
        return replace_state(state, skip=one_line(str(skip), 1000), notes=tuple(notes))
    return replace_state(
        state,
        issue_file=str(issue_file),
        issue_source=source,
        previous_dir=previous_dir,
        previous_run=previous_run,
        notes=tuple(notes[:MAX_NOTES]),
    )


def replace_state(state: State, **changes: object) -> State:
    """A copy with `changes`, validated again (model_copy would skip validation)."""
    return State.model_validate({**state.model_dump(), **changes}, strict=False)


def _command(kind: str, title: str, message: str) -> str:
    """A workflow command (`::notice title=...::message`) with its data escaped."""

    def data(text: str) -> str:
        return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    prop = data(title).replace(":", "%3A").replace(",", "%2C")
    return f"::{kind} title={prop}::{data(message)}"


def say(line: str) -> None:
    """One log line. It starts with `tracefix:`, so untrusted text in it is never a command."""
    print("tracefix: " + one_line(line, 2000), flush=True)


def _report_prepared(state: State) -> None:
    for note in state.notes:
        say(f"note: {note}")
    if state.skip:
        say(f"not verifying: {state.skip}")
        print(_command("notice", "Tracefix: not verified", state.skip), flush=True)
        return
    what = f"pull request #{state.pr}" if state.pr else f"a {state.event} event"
    assert state.base and state.head
    say(f"{state.trust} run for {what}: base {state.base[:12]}, head {state.head[:12]}")
    say(f"issue text {state.issue_source}")
    if state.previous_run:
        say(f"replaying the receipt of run {state.previous_run}")


def _client(ctx: Context) -> GitHub:
    try:
        return GitHub(ctx.token, ctx.repo, api_url=ctx.api_url or None)
    except ValueError as exc:
        raise ActionError(str(exc)) from None


def write_outputs(env: Mapping[str, str], step: str, outputs: Mapping[str, str]) -> None:
    """The step's outputs (`name=value` lines in $GITHUB_OUTPUT), each value on one line."""
    assert set(outputs) <= OUTPUTS[step], set(outputs) - OUTPUTS[step]
    _append(env, "GITHUB_OUTPUT", "".join(f"{k}={one_line(v, 2000)}\n" for k, v in outputs.items()))


def _append(env: Mapping[str, str], variable: str, text: str) -> None:
    path = env.get(variable, "")
    if path:
        with open(path, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(text)


def run_prepare(env: Mapping[str, str]) -> int:
    ctx = read_context(env)
    state = prepare(ctx, _client(ctx))
    path = state_path(ctx.temp)
    path.parent.mkdir()
    write_state(path, state)
    _report_prepared(state)
    write_outputs(env, "prepare", {
        "receipt-dir": str(path.parent),
        "artifact-name": artifact_name(state),
        "skip": "true" if state.skip else "false",
    })  # fmt: skip
    return 0


# --- verify ---------------------------------------------------------------------------------------


def verify_args(state: State, workspace: Path, out: Path, python: str = "") -> list[str]:
    """`tracefix verify`'s arguments, every value after `=` (so none can read as an option).
    `python` is the project's interpreter, which runs its tests (`--python`)."""
    assert state.base and state.head and state.issue_file
    args = ["verify", f"--repo={workspace}", f"--base={state.base}", f"--head={state.head}",
            f"--issue={state.issue_file}", f"--out={out}"]  # fmt: skip
    if python:
        args.append(f"--python={python}")
    if state.config:
        args.append(f"--config={state.config}")
    if state.previous_dir:
        args.append(f"--previous={state.previous_dir}")
    if state.trust == "untrusted":
        args.append("--require-strict")
    return args


class _Lines(io.StringIO):
    """stderr passed through, with its last lines kept."""

    def __init__(self, out: TextIO) -> None:
        super().__init__()
        self.out = out
        self.lines: list[str] = []
        self._part = ""

    def write(self, s: str) -> int:
        self.out.write(s)
        *done, self._part = (self._part + s).split("\n")
        self.lines = [*self.lines, *done][-200:]
        return len(s)

    def flush(self) -> None:
        self.out.flush()


def masked(text: str, secret: str, folders: Sequence[tuple[Path, str]]) -> str:
    """`text` without the API key, and with this runner's folders as tokens."""
    if len(secret) >= 8:
        text = text.replace(secret, "***")
    for folder, token in folders:
        for form in sorted({str(folder), folder.as_posix()}, key=len, reverse=True):
            text = text.replace(form, token)
    return text


def last_message(lines: Sequence[str]) -> str:
    """The CLI's own last line (`tracefix verify: ...`), else the last line with text."""
    own = [line for line in lines if line.startswith("tracefix verify:")]
    rest = [line for line in lines if line.strip()]
    return (own or rest or [""])[-1]


def verify(state: State, workspace: Path, out: Path, *, secret: str = "", python: str = "",
           provider: Provider | None = None) -> tuple[int, str]:  # fmt: skip
    """Run `tracefix verify` in this process: its exit code and last message, masked. Workflow
    commands are off meanwhile, since its output carries repo, issue and model text."""
    stop = secrets.token_hex(16)
    print(f"::stop-commands::{stop}", flush=True)
    lines = _Lines(sys.stderr)
    try:
        with contextlib.redirect_stderr(lines):
            code = cli.main(verify_args(state, workspace, out, python), provider=provider)
    except SystemExit as exc:  # argparse refused the arguments
        code = exc.code if isinstance(exc.code, int) else cli.EXIT_NOTHING_TO_VERIFY
    finally:
        print(f"::{stop}::", flush=True)
    folders = [(workspace, "<workspace>"), (out.parent.parent, "<runner temp>")]
    message = masked(last_message(lines.lines), secret, folders)
    return code, one_line(message, MAX_MESSAGE_CHARS)


def run_verify(env: Mapping[str, str], *, provider: Provider | None = None) -> int:
    """Never holds the token: only the state, the checkout and the model key."""
    path = state_path(Path(_required(env, "RUNNER_TEMP")) / "tracefix")
    if not path.is_file():
        raise ActionError("no state.json: the prepare step must run first")
    state = read_state(path)
    if state.skip:
        say("nothing to verify (see the prepare step)")
        return 0
    workspace = Path(_required(env, "GITHUB_WORKSPACE"))
    secret = env.get("ANTHROPIC_API_KEY", "")
    python = env.get("PROJECT_PYTHON", "")  # set by action.yml's install step
    code, message = verify(state, workspace, path.parent, secret=secret, python=python,
                           provider=provider)  # fmt: skip
    write_state(path, replace_state(state, verify_exit=code, verify_message=message))
    say(f"tracefix verify exited {code}" + (f": {message}" if code else ""))
    return 0


# --- report ---------------------------------------------------------------------------------------


def check_binding(ctx: Context, state: State) -> None:
    """The state (from an artifact, in the fork flow) must be this run's, for this event's pull
    request and its exact head commit."""
    pr = ctx.event.pr
    wrong = (
        state.repo.lower() != ctx.repo.lower()
        or state.run_id != ctx.run_id
        or state.pr != (pr.number if pr else None)
        or (pr is not None and not ctx.inputs.head and state.head != pr.head_sha)
    )
    if wrong:
        raise ActionError("the receipt's state.json is not from this run of this pull request")


def read_receipt(folder: Path, state: State) -> Receipt:
    """receipt.json, strictly validated, for this run's two commits."""
    try:
        with (folder / "receipt.json").open("rb") as handle:
            raw = handle.read(MAX_RECEIPT_BYTES + 1)
    except OSError as exc:
        raise ActionError(f"can't read receipt.json: {exc.strerror or exc}") from None
    if len(raw) > MAX_RECEIPT_BYTES:
        raise ActionError(f"receipt.json is larger than {MAX_RECEIPT_BYTES:,} bytes")
    try:
        receipt = Receipt.model_validate_json(raw, strict=True)
    except ValidationError as exc:
        errors = exc.error_count()
        raise ActionError(f"receipt.json is not a valid receipt ({errors} errors)") from None
    if (receipt.base.sha, receipt.head.sha) != (state.base, state.head):
        raise ActionError("receipt.json is for other commits than this run's")
    if state.trust == "untrusted" and receipt.isolation.level != "strict":
        raise ActionError("receipt.json says basic isolation, but this run was untrusted")
    return receipt


def load_report(state: State, folder: Path) -> ar.Report:
    """The receipt, or why there is none (exit 2: not verified; exit 3: Tracefix failed)."""
    if state.skip:
        return ar.Report(None, state.skip)
    code, message = state.verify_exit, state.verify_message
    if code is None:
        return ar.Report(None, "the verify step did not finish (see its log)", failed=True)
    if code == cli.EXIT_NOTHING_TO_VERIFY:
        return ar.Report(None, message or "nothing to verify")
    if code != cli.EXIT_OK:
        return ar.Report(None, message or f"tracefix verify exited {code}", failed=True)
    return ar.Report(read_receipt(folder, state))


def _refused(exc: GitHubError, ctx: Context, what: str, permission: str) -> None:
    """A read-only token on a fork's pull request is expected (a note); anything else fails."""
    if exc.status == 403 and ctx.event.name == "pull_request" and is_fork(ctx):
        say(f"note: no {what}: the token is read-only on a pull request from a fork")
        return
    hint = f"; the job needs `permissions: {permission}`" if exc.status in (403, 404) else ""
    raise ActionError(f"can't post the {what}: {exc}{hint}")


def _login(github: GitHub) -> str:
    """The token's own login (a personal token); the workflow token is not a user (403)."""
    try:
        return github.get_user() or ar.BOT_LOGIN
    except GitHubError:
        return ar.BOT_LOGIN


def post_comment(ctx: Context, github: GitHub, state: State, report: ar.Report,
                 header: ar.Header, when: str) -> str:  # fmt: skip
    """Create or edit our one comment: its URL ("" when none). A run that verified nothing never
    creates one, but rewrites ours, so a stale receipt never reads as current."""
    if not ctx.inputs.comment or state.pr is None or state.head is None:
        return ""
    mine = ar.ours(github.list_comments(state.pr), _login(github))
    if mine is None and report.receipt is None:
        return ""
    earlier = ar.parse_history(mine.body) if mine else ()
    history = ar.with_entry(earlier, ar.entry(state.head, report, when, ctx.run_id))
    runs = f"{ctx.server_url}/{ctx.repo}/actions/runs"
    body = ar.comment_body(header, report, history, lambda run: f"{runs}/{run}")
    if mine is None:
        return github.create_comment(state.pr, body).html_url
    return github.update_comment(mine.id, body).html_url


def remove_label(ctx: Context, github: GitHub) -> None:
    """The maintainer's approval label goes after one run: each new commit needs a new one."""
    pr, label = ctx.event.pr, ctx.event.label
    if ctx.event.name != "pull_request_target" or pr is None or not label:
        return
    try:
        github.remove_label(pr.number, label)
    except GitHubError as exc:
        if exc.status != 404:  # 404: already removed
            say(f"note: can't remove the label: {exc}")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_report(
    env: Mapping[str, str], *, now: Callable[[], str] = _now, github: GitHub | None = None
) -> int:
    """Never holds the model key. Fails the step only for a misconfiguration or when Tracefix
    itself failed; a verdict is the check run's conclusion, never the job's."""
    ctx = read_context(env)
    path = state_path(ctx.temp)
    if not path.is_file():
        raise ActionError("no state.json: the prepare step (or the receipt artifact) is missing")
    state = read_state(path)
    check_binding(ctx, state)
    try:
        report = load_report(state, path.parent)
    except ActionError as exc:  # said on the PR as a failure of Tracefix; the step fails below
        report = ar.Report(None, str(exc), failed=True)
    receipt, min_level = report.receipt, ctx.inputs.min_level
    shown, more = ar.annotations_for(receipt) if receipt and ctx.inputs.annotations else ([], 0)
    header = ar.Header(state.head or "", ctx.run_url, "" if state.skip else artifact_name(state),
                       state.issue_source)  # fmt: skip
    verdict = ar.conclusion(receipt, min_level)
    status = receipt.status.value if receipt else "failed" if report.failed else "not_verified"
    write_outputs(env, "report", {
        "level": receipt.level.value if receipt else "",
        "status": status,
        "conclusion": verdict,
        "receipt-dir": str(path.parent),
    })  # fmt: skip
    _append(env, "GITHUB_STEP_SUMMARY", ar.check_summary(header, report, more))
    say(f"conclusion: {verdict} ({ar.check_title(report, min_level)})")
    github, when = github or _client(ctx), now()
    links = {"check-run-url": "", "comment-url": ""}
    if state.head:
        fields = ar.check_run(header, report, min_level, shown, more, when)
        try:
            links["check-run-url"] = github.create_check_run(fields).html_url
        except GitHubError as exc:
            _refused(exc, ctx, "check run", "checks: write")
    try:
        links["comment-url"] = post_comment(ctx, github, state, report, header, when)
    except GitHubError as exc:
        _refused(exc, ctx, "pull request comment", "pull-requests: write")
    remove_label(ctx, github)
    write_outputs(env, "report", links)
    if report.failed:
        print(_command("error", "Tracefix failed", report.why_not), flush=True)
        return 1
    return 0


STEPS: dict[str, Callable[[Mapping[str, str]], int]] = {
    "prepare": run_prepare,
    "verify": run_verify,
    "report": run_report,
}


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tracefix.action")
    parser.add_argument("step", choices=sorted(STEPS))
    args = parser.parse_args(argv)
    try:
        return STEPS[args.step](os.environ if env is None else env)
    except ActionError as exc:
        print(_command("error", "Tracefix", str(exc)), flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
