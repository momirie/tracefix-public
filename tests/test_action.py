"""The Action's prepare step (plan P2, P3, P6): event payloads, trust, skips, commits, the issue
text and the last receipt. Git runs on temp repos (a bare repo stands in for GitHub's git server);
the API is the loopback fake, called in-process through its transport, and once over real HTTP in
a subprocess."""

from __future__ import annotations

import base64
import io
import json
import os
import subprocess
import sys
import time
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from conftest import make_repo
from github_fake import IN_PROCESS_API, FakeGitHub
from hypothesis import given
from hypothesis import strategies as st
from make_fixtures import git as fixture_git
from synthetic import attack, finding, l4_run

from tracefix import action
from tracefix import action_report as ar
from tracefix.action import ActionError, Context, Event, Inputs, PullRequest, Skip, State
from tracefix.attack import AttackStatus
from tracefix.attack_rules import Expectation
from tracefix.cli import write_out
from tracefix.github_api import GitHub
from tracefix.ladder import EvidenceLevel
from tracefix.pipeline import Verified
from tracefix.previous import load
from tracefix.receipt import Receipt, build
from tracefix.receipt_md import render
from tracefix.workspace import Workspace

EVENTS = Path(__file__).parent / "github_events"
REPO = "octo/svc"
WORKFLOW = ".github/workflows/tracefix.yml"
STRICT = ("strict", "bubblewrap works")
BASIC = ("basic", "bubblewrap (bwrap) is not installed")


def strict() -> tuple[str, str]:
    return STRICT


def basic() -> tuple[str, str]:
    return BASIC


def event_file(tmp_path: Path, name: str, **changes: Any) -> Path:
    payload = json.loads((EVENTS / name).read_text(encoding="utf-8"))
    pr = payload.get("pull_request")
    for key, value in changes.items():
        if key == "base_sha":
            pr["base"]["sha"] = value
        elif key == "head_sha":
            pr["head"]["sha"] = value
        else:
            pr[key] = value
    path = tmp_path / f"event-{name}"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def base_env(tmp_path: Path, event: str, event_path: Path, **inputs: str) -> dict[str, str]:
    env = {
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_RUN_ID": "500",
        "GITHUB_WORKSPACE": str(tmp_path / "work"),
        "RUNNER_TEMP": str(tmp_path / "runner-temp"),
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_EVENT_NAME": event,
        "GITHUB_EVENT_PATH": str(event_path),
        "GITHUB_WORKFLOW_REF": f"{REPO}/{WORKFLOW}@refs/pull/7/merge",
        "INPUT_GITHUB_TOKEN": "ghs_fake_token",
        "INPUT_HAS_API_KEY": "true",
    }
    env.update({f"INPUT_{k.upper()}": v for k, v in inputs.items()})
    return env


def runner_env() -> dict[str, str]:
    """This machine's environment for a step's subprocess, without what could leak into it: a
    runner's own variables (CI's GITHUB_OUTPUT, say), inputs, a model key, or a proxy."""
    dropped = ("GITHUB_", "INPUT_", "RUNNER_", "ANTHROPIC_")
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(dropped) and not k.lower().endswith("_proxy")}  # fmt: skip
    return {**env, "NO_PROXY": "127.0.0.1"}


def context(tmp_path: Path, event: Event, *, inputs: Inputs | None = None, **kw: Any) -> Context:
    fields: dict[str, Any] = {
        "repo": REPO,
        "workspace": tmp_path / "work",
        "temp": tmp_path / "runner-temp" / "tracefix",
        "server_url": "https://github.com",
        "api_url": IN_PROCESS_API,
        "run_id": 500,
        "workflow_path": WORKFLOW,
        "token": "ghs_fake_token",
        "event": event,
        "inputs": inputs or Inputs(has_api_key=True),
    }
    fields.update(kw)
    return Context(**fields)


def pr_event(
    name: str = "pull_request", *, head_repo: str = REPO, body: str = "", **kw: Any
) -> Event:
    pr = PullRequest(
        7, kw.pop("base", "3" * 40), kw.pop("head", "2" * 40), head_repo, "Title", body
    )
    return Event(name, kw.pop("act", "synchronize"), pr, kw.pop("label", ""))


def client(fake: FakeGitHub) -> GitHub:
    return GitHub(fake.token, fake.repo, transport=fake.transport(), api_url=IN_PROCESS_API)


# --- events and inputs ----------------------------------------------------------------------------


def test_real_payload_shapes_are_read(tmp_path: Path) -> None:
    same = action.read_event("pull_request", str(EVENTS / "pull_request_same_repo.json"))
    assert same.pr == PullRequest(
        7,
        "3" * 40,
        "2" * 40,
        "octo/svc",
        "Fix crash when PORT is unset",
        "Fixes #1\r\n\r\nAn empty PORT now falls back to the default.",
    )
    assert (same.action, same.label) == ("synchronize", "")
    fork = action.read_event("pull_request", str(EVENTS / "pull_request_fork.json"))
    assert fork.pr is not None and fork.pr.head_repo == "outsider/svc"
    target = action.read_event(
        "pull_request_target", str(EVENTS / "pull_request_target_labeled.json")
    )
    assert (target.action, target.label) == ("labeled", "tracefix")
    dispatch = action.read_event("workflow_dispatch", str(EVENTS / "workflow_dispatch.json"))
    assert dispatch.pr is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"number": "7"}, "no number"),
        ({"head_sha": "abc"}, "commit ids"),
        ({"base_sha": "G" * 40}, "commit ids"),
    ],
)
def test_malformed_pull_requests_are_errors(
    tmp_path: Path, changes: dict[str, Any], message: str
) -> None:
    path = event_file(tmp_path, "pull_request_same_repo.json", **changes)
    with pytest.raises(ActionError, match=message):
        action.read_event("pull_request", str(path))


def test_event_name_and_payload_are_checked(tmp_path: Path) -> None:
    with pytest.raises(ActionError, match="not an event name"):
        action.read_event("pull_request; rm -rf /", "")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ActionError, match="can't read the event payload"):
        action.read_event("pull_request", str(bad))


def test_inputs_are_parsed_and_checked() -> None:
    inputs = action.read_inputs(
        {
            "INPUT_TRUST": "Untrusted",
            "INPUT_MIN_LEVEL": "l3",
            "INPUT_COMMENT": "false",
            "INPUT_REPORT": "FALSE",
            "INPUT_HAS_API_KEY": "true",
        }
    )
    assert (inputs.trust, inputs.min_level, inputs.comment, inputs.report) == (
        "untrusted",
        "L3",
        False,
        False,
    )
    assert (inputs.annotations, inputs.previous, inputs.has_api_key) == (True, True, True)
    assert action.read_inputs({}) == Inputs()
    for env, message in [
        ({"INPUT_TRUST": "trusted"}, "only make a run stricter"),
        ({"INPUT_TRUST": "maybe"}, "auto or untrusted"),
        ({"INPUT_MIN_LEVEL": "L5"}, "min-level"),
        ({"INPUT_COMMENT": "yes"}, "comment must be true or false"),
    ]:
        with pytest.raises(ActionError, match=message):
            action.read_inputs(env)


def test_context_comes_from_the_environment(tmp_path: Path) -> None:
    env = base_env(tmp_path, "pull_request", EVENTS / "pull_request_same_repo.json")
    ctx = action.read_context(env)
    assert (ctx.repo, ctx.run_id, ctx.workflow_path) == (REPO, 500, WORKFLOW)
    assert ctx.temp == tmp_path / "runner-temp" / "tracefix"
    assert ctx.run_url == "https://github.com/octo/svc/actions/runs/500"
    for name, value, message in [
        ("GITHUB_REPOSITORY", "", "GITHUB_REPOSITORY is not set"),
        ("GITHUB_REPOSITORY", "octo", "not owner/name"),
        ("GITHUB_RUN_ID", "12a", "not a number"),
        ("INPUT_GITHUB_TOKEN", "", "github-token is empty"),
    ]:
        with pytest.raises(ActionError, match=message):
            action.read_context({**env, name: value})
    other = {**env, "GITHUB_WORKFLOW_REF": "someone/else/.github/workflows/x.yml@main"}
    assert action.read_context(other).workflow_path == ""


# --- trust and skips ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("event", "trust"),
    [
        (pr_event("pull_request"), "trusted"),
        (pr_event("pull_request", head_repo="OCTO/SVC"), "trusted"),
        (pr_event("pull_request", head_repo="outsider/svc"), "untrusted"),
        (pr_event("pull_request", head_repo=""), "untrusted"),  # the fork was deleted
        (pr_event("pull_request_target"), "untrusted"),
        (pr_event("pull_request_target", head_repo="outsider/svc"), "untrusted"),
        (Event("workflow_dispatch", "", None, ""), "trusted"),
        (Event("push", "", None, ""), "trusted"),
        (Event("issue_comment", "created", None, ""), "untrusted"),
        (Event("workflow_run", "completed", None, ""), "untrusted"),
    ],
)
def test_trust(tmp_path: Path, event: Event, trust: str) -> None:
    assert action.decide_trust(context(tmp_path, event)) == trust


@given(
    name=st.sampled_from(
        [
            "pull_request",
            "pull_request_target",
            "workflow_dispatch",
            "push",
            "issue_comment",
            "merge_group",
        ]
    ),
    head_repo=st.sampled_from([REPO, "outsider/svc", ""]),
    with_pr=st.booleans(),
)
def test_the_input_only_tightens_trust(name: str, head_repo: str, with_pr: bool) -> None:
    event = pr_event(name, head_repo=head_repo) if with_pr else Event(name, "", None, "")
    auto = context(Path("."), event)
    tight = replace(auto, inputs=Inputs(trust="untrusted"))
    assert action.decide_trust(tight) == "untrusted"
    if action.decide_trust(auto) == "trusted":
        assert name in action.TRUSTED_EVENTS and (not with_pr or head_repo == REPO)


def test_early_skips(tmp_path: Path) -> None:
    def skip(ctx: Context, probe: Any = strict) -> str:
        with pytest.raises(Skip) as caught:
            action.early_skip(ctx, action.decide_trust(ctx), probe)
        return str(caught.value)

    fork = context(tmp_path, pr_event("pull_request", head_repo="outsider/svc"))
    assert "label flow" in skip(fork)
    assert "label flow" in skip(replace(fork, inputs=Inputs(has_api_key=False)))  # fork first
    dispatch = context(tmp_path, Event("workflow_dispatch", "", None, ""))
    assert "has no pull request" in skip(dispatch)
    with pytest.raises(ActionError, match="set both base and head"):
        action.early_skip(
            replace(dispatch, inputs=Inputs(head="x", has_api_key=True)), "trusted", strict
        )
    same = context(tmp_path, pr_event())
    assert "no model API key" in skip(replace(same, inputs=Inputs()))
    target = context(tmp_path, pr_event("pull_request_target", head_repo="outsider/svc"))
    assert "needs strict isolation" in skip(target, basic)
    assert BASIC[1] in skip(target, basic)
    action.early_skip(target, "untrusted", strict)  # no skip
    action.early_skip(same, "trusted", basic)  # trusted runs at basic isolation too
    untrusted_input = replace(same, inputs=Inputs(trust="untrusted", has_api_key=True))
    assert "needs strict isolation" in skip(untrusted_input, basic)


# --- commits (temp repos; a bare repo is the "server") --------------------------------------------


def _sha(repo: Path, ref: str) -> str:
    return fixture_git(repo, "rev-parse", ref)


@pytest.fixture
def server(tmp_path: Path) -> dict[str, Any]:
    """A repo with main (c0 -> c2) and a pull request branch from c0 (c1), pushed to a bare
    "server" at <server>/octo/svc.git with refs/pull/7/head; and a full clone of main only."""
    origin = make_repo(tmp_path / "origin", [{"app.py": "x = 1\n"}])
    fixture_git(origin, "checkout", "--quiet", "-b", "fix")
    (origin / "app.py").write_text("x = 2\n", encoding="utf-8")
    fixture_git(origin, "commit", "--quiet", "-am", "fix")
    fixture_git(origin, "checkout", "--quiet", "main")
    (origin / "other.py").write_text("y = 1\n", encoding="utf-8")
    fixture_git(origin, "add", "other.py")
    fixture_git(origin, "commit", "--quiet", "-m", "main moves on")
    root = tmp_path / "server"
    bare = root / "octo" / "svc.git"
    bare.parent.mkdir(parents=True)
    fixture_git(tmp_path, "clone", "--quiet", "--bare", str(origin), str(bare))
    fork_point, head, main = _sha(origin, "c0"), _sha(origin, "fix"), _sha(origin, "main")
    fixture_git(bare, "update-ref", "refs/pull/7/head", head)
    work = tmp_path / "work"
    fixture_git(
        tmp_path,
        "clone",
        "--quiet",
        "--single-branch",
        "--branch",
        "main",
        bare.as_uri(),
        str(work),
    )  # file://: only main's objects
    return {
        "origin": origin,
        "bare": bare,
        "root": root,
        "work": work,
        "fork_point": fork_point,
        "head": head,
        "main": main,
    }


def server_context(tmp_path: Path, server: dict[str, Any], event: Event, **kw: Any) -> Context:
    return context(tmp_path, event, server_url=server["root"].as_posix(), **kw)


def test_base_is_the_merge_base_and_head_is_fetched(tmp_path: Path, server: dict[str, Any]) -> None:
    event = pr_event(base=server["main"], head=server["head"])
    ctx = server_context(tmp_path, server, event)
    assert not action.has_commit(server["work"], server["head"])  # main only: fetched below
    assert action.find_commits(ctx, "trusted") == (server["fork_point"], server["head"])
    assert action.has_commit(server["work"], server["head"])
    untrusted = action.find_commits(ctx, "untrusted")  # base checkout: allowed
    assert untrusted == (server["fork_point"], server["head"])


def test_a_force_pushed_head_is_refused(tmp_path: Path, server: dict[str, Any]) -> None:
    gone = "9" * 40
    ctx = server_context(tmp_path, server, pr_event(base=server["main"], head=gone))
    with pytest.raises(Skip, match="no longer on pull request #7"):
        action.find_commits(ctx, "untrusted")


def test_a_failed_fetch_is_a_skip(tmp_path: Path, server: dict[str, Any]) -> None:
    event = pr_event(base=server["main"], head=server["head"])
    ctx = server_context(tmp_path, server, replace(event, pr=replace(event.pr, number=8)))
    with pytest.raises(Skip, match="can't fetch pull request #8"):
        action.find_commits(ctx, "untrusted")


def test_untrusted_refuses_a_checkout_holding_the_pr(
    tmp_path: Path, server: dict[str, Any]
) -> None:
    event = pr_event(base=server["main"], head=server["head"])
    ctx = server_context(tmp_path, server, event)
    action.find_commits(ctx, "trusted")  # fetches the head
    fixture_git(server["work"], "checkout", "--quiet", server["head"])
    with pytest.raises(Skip, match="already holds the pull request's code"):
        action.find_commits(ctx, "untrusted")
    assert action.find_commits(ctx, "trusted")[1] == server["head"]  # trusted: expected
    fixture_git(server["work"], "checkout", "--quiet", "-b", "merged", server["main"])
    fixture_git(server["work"], "merge", "--quiet", "--no-edit", server["head"])
    with pytest.raises(Skip, match="already holds"):  # the classic refs/pull/N/merge checkout
        action.find_commits(ctx, "untrusted")


def test_shallow_checkouts_and_missing_repos(tmp_path: Path, server: dict[str, Any]) -> None:
    shallow = tmp_path / "shallow"
    url = server["bare"].as_uri()
    fixture_git(tmp_path, "clone", "--quiet", "--depth", "1", url, str(shallow))
    event = pr_event(base=server["main"], head=server["head"])
    with pytest.raises(Skip, match="fetch-depth: 0"):
        action.find_commits(server_context(tmp_path, server, event, workspace=shallow), "trusted")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ActionError, match="check out the repository first"):
        action.find_commits(server_context(tmp_path, server, event, workspace=empty), "trusted")


def test_missing_base_and_unrelated_histories(tmp_path: Path, server: dict[str, Any]) -> None:
    event = pr_event(base="8" * 40, head=server["head"])
    with pytest.raises(Skip, match="base commit 888888888888 is not in the checkout"):
        action.find_commits(server_context(tmp_path, server, event), "trusted")
    lonely = make_repo(tmp_path / "lonely", [{"z.py": "z = 0\n"}])
    fixture_git(server["work"], "fetch", "--quiet", str(lonely), "main:lonely")
    unrelated = pr_event(base=_sha(server["work"], "lonely"), head=server["head"])
    with pytest.raises(Skip, match="share no commit"):
        action.find_commits(server_context(tmp_path, server, unrelated), "trusted")


def test_inputs_override_the_commits(tmp_path: Path, server: dict[str, Any]) -> None:
    fixture_git(server["work"], "tag", "v0", server["fork_point"])
    dispatch = Event("workflow_dispatch", "", None, "")
    inputs = Inputs(base="v0", head="main", has_api_key=True)
    ctx = server_context(tmp_path, server, dispatch, inputs=inputs)
    assert action.find_commits(ctx, "trusted") == (server["fork_point"], server["main"])
    bad = replace(ctx, inputs=replace(inputs, head="no-such-branch"))
    with pytest.raises(ActionError, match="input head: unknown ref"):
        action.find_commits(bad, "trusted")


def test_the_token_never_reaches_argv(tmp_path: Path) -> None:
    ctx = context(tmp_path, pr_event(), token="ghs_SECRET")
    args, env = action.fetch_command(ctx, 7)
    assert not any("SECRET" in a for a in args)
    assert args[-1] == f"+refs/pull/7/head:{action.FETCHED_REF}"
    assert (
        env["GIT_CONFIG_KEY_0"] == env["GIT_CONFIG_KEY_1"] == "http.https://github.com/.extraheader"
    )
    assert env["GIT_CONFIG_VALUE_0"] == ""  # clears a header actions/checkout stored
    secret = base64.b64encode(b"x-access-token:ghs_SECRET").decode()
    assert env["GIT_CONFIG_VALUE_1"] == f"AUTHORIZATION: basic {secret}"


# --- the issue text -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "numbers"),
    [
        ("Fixes #12", [12]),
        ("fixes: #3 and Closes #4\nresolved #5", [3, 4, 5]),
        ("FIX #1, close #2, resolve #3, closed #4", [1, 2, 3]),  # at most 3
        ("Fixes #2. Fixes #2 again", [2]),
        ("Fixes octo/svc#8", [8]),
        ("Fixes OCTO/Svc#8", [8]),
        ("Fixes outsider/svc#8", []),
        ("Fixes https://github.com/octo/svc/issues/9", [9]),
        ("Fixes https://github.com/outsider/svc/issues/9", []),
        ("Fixes https://evil.example/octo/svc/issues/9", []),
        ("Fixes https://github.com.evil.example/octo/svc/issues/9", []),
        ("prefixes #6, unfixed #6, fixes#6", []),
        ("Fixes #7abc, Fixes #7/x", []),
        ("Fixes #0", []),
        ("Refs #4, see #5", []),
        ("", []),
    ],
)
def test_closing_references(body: str, numbers: list[int]) -> None:
    assert action.closed_issues(body, REPO, "https://github.com") == numbers


@given(st.text(max_size=300))
def test_closing_references_never_raise(body: str) -> None:
    found = action.closed_issues(body, REPO, "https://github.com")
    assert len(found) <= action.MAX_CLOSED_ISSUES
    assert all(n > 0 for n in found)


def test_a_long_hostile_body_is_read_in_linear_time() -> None:
    """GitHub allows 65,536 characters; the old URL pattern took 10 s on this (verifier M9 N7)."""
    body = "fix:http://" * 6000 + "Fixes https://github.com/octo/svc/issues/9"
    start = time.monotonic()
    assert action.closed_issues(body, REPO, "https://github.com") == [9]
    assert time.monotonic() - start < 1.0


def test_issue_text_from_closed_issues(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    fake.issues[1] = {"number": 1, "title": "Crash on empty PORT", "body": "Traceback..."}
    fake.issues[2] = {"number": 2, "title": "A PR", "body": "", "pull_request": {"url": "u"}}
    fake.issues[4] = {"number": 4, "title": "Second", "body": None}
    ctx = context(tmp_path, pr_event(body="Fixes #1, fixes #2, fixes #3, fixes #4"))
    notes: list[str] = []
    text, source = action.issue_text(ctx, client(fake), notes)
    assert text == "# Crash on empty PORT\n\nTraceback...\n"  # #2 is a PR, #3 is missing
    assert source == "from #1"
    assert notes == [
        f"can't read issue #3: GitHub API 404: GET {IN_PROCESS_API}/repos/octo/svc/issues/3: "
        "Not Found"
    ]
    ctx2 = context(tmp_path, pr_event(body="Fixes #1 and fixes #4"))
    text2, source2 = action.issue_text(ctx2, client(fake), [])
    assert source2 == "from #1 and #4"
    assert text2.endswith("# Second\n")


def test_issue_text_falls_back_and_the_input_wins(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    ctx = context(tmp_path, pr_event(body="Empty PORT crashes.\r\n"))
    assert action.issue_text(ctx, client(fake), []) == (
        "# Title\n\nEmpty PORT crashes.\n",
        "from the pull request description",
    )
    ctx_input = replace(ctx, inputs=Inputs(issue="Given text", has_api_key=True))
    assert action.issue_text(ctx_input, client(fake), []) == ("Given text", "from the issue input")
    assert fake.seen == []  # neither asked the API
    no_pr = context(tmp_path, Event("workflow_dispatch", "", None, ""))
    with pytest.raises(Skip, match="set the issue input"):
        action.issue_text(no_pr, client(fake), [])


def test_write_issue(tmp_path: Path) -> None:
    ctx = context(tmp_path, pr_event())
    ctx.temp.mkdir(parents=True)
    notes: list[str] = []
    path = action.write_issue(ctx, "a\r\nb\rc\0d", notes)
    assert path.read_bytes() == b"a\nb\ncd"
    long = action.write_issue(ctx, "x" * (action.MAX_ISSUE_CHARS + 10), notes)
    assert len(long.read_text(encoding="utf-8")) == action.MAX_ISSUE_CHARS
    assert notes == ["the issue text was cut to 100,000 characters"]
    with pytest.raises(Skip, match="empty"):
        action.write_issue(ctx, " \r\n\0", [])


def test_lone_surrogates_in_untrusted_text_are_written(tmp_path: Path) -> None:
    payload = json.loads((EVENTS / "pull_request_target_labeled.json").read_text(encoding="utf-8"))
    payload["pull_request"]["title"] = "Fix \ud800"
    payload["pull_request"]["body"] = "body \udfff"
    payload["label"]["name"] = "tracefix\ud800"
    path = tmp_path / "event.json"
    path.write_text(json.dumps(payload), encoding="utf-8")  # ASCII: "\ud800" as an escape
    event = action.read_event("pull_request_target", str(path))
    assert event.pr is not None and (event.pr.title, event.label) == ("Fix ?", "tracefix?")
    ctx = context(tmp_path, event)
    ctx.temp.mkdir(parents=True)
    issue = action.write_issue(ctx, "# \ud800 from an env input", [])
    assert issue.read_text(encoding="utf-8") == "# ? from an env input"
    state = State(
        repo=REPO,
        run_id=1,
        run_url="u",
        event="pull_request_target",
        trust="untrusted",
        label=event.label,
    )
    action.write_state(tmp_path / "state.json", state)
    assert action.read_state(tmp_path / "state.json").label == "tracefix?"


# --- the last receipt -----------------------------------------------------------------------------


def make_zip(files: dict[str, bytes], *, compress: bool = True) -> bytes:
    buffer = io.BytesIO()
    method = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    with zipfile.ZipFile(buffer, "w", method) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def state_json(run_id: int, *, verify_exit: int | None = 0, skip: str = "", pr: int = 7) -> bytes:
    """The state.json an earlier run of PR 7 uploaded beside its receipt."""
    state = State(repo=REPO, run_id=run_id, run_url=f"https://github.com/{REPO}/actions/runs/1",
                  event="pull_request", trust="trusted", pr=pr, skip=skip,
                  verify_exit=verify_exit)  # fmt: skip
    return state.model_dump_json().encode("utf-8")


def receipt_files(tmp_path: Path, run_id: int = 10) -> dict[str, bytes]:
    """A real `--out` folder's files (one finding), as upload-artifact zips them."""
    repo = tmp_path / "dummy"
    repo.mkdir(exist_ok=True)
    ws = Workspace(repo, "main", "fix")
    ws.root = tmp_path / "copies"
    code = "from port import parse_port\n\n\ndef test_break_my_fix_1() -> None:\n    pass\n"
    found = finding(
        1,
        function="port.parse_port",
        repro_code=code,
        expect=Expectation(frozenset({"AssertionError"}), True),
    )
    record = l4_run(break_my_fix=attack(status=AttackStatus.FOUND, findings=(found,)))
    out = tmp_path / "out"
    write_out(out, Verified(record, build(record, ws)))
    files = {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    assert "findings/finding_1.py" in files
    return {**files, "state.json": state_json(run_id)}


def test_unpack_keeps_only_the_receipt_files() -> None:
    data = make_zip(
        {
            "receipt.json": b"{}",
            "state.json": b"{}",
            "findings/finding_1.py": b"x = 1\n",
            "findings/previous_2.py": b"y = 2\n",
            "receipt.md": b"# hostile markdown",
            "../receipt.json": b"evil",
            "/etc/receipt.json": b"evil",
            "findings/../../x.py": b"evil",
            "findings/finding_1.py.bak": b"evil",
            "findings/sub/finding_2.py": b"evil",
            "repro/test_repro.py": b"evil",
            "findings/finding_0.py": b"evil",
            "findings/previous_0.py": b"evil",
        }
    )
    files = action.unpack_receipt(data)
    assert files == {
        "receipt.json": b"{}",
        "state.json": b"{}",
        "findings/finding_1.py": b"x = 1\n",
        "findings/previous_2.py": b"y = 2\n",
    }


STATE = {"state.json": b"{}"}


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"not a zip", "can't be read"),
        (make_zip({"receipt.json": b"{}"}), "no state.json"),
        (make_zip({"../state.json": b"{}"}), "no state.json"),
        (make_zip({**STATE, "receipt.json": b" " * (action.MAX_RECEIPT_BYTES + 1)}), "larger than"),
        (
            make_zip({**STATE, **{f"findings/finding_{i}.py": b"" for i in range(1, 7)}}),
            "more than 5 finding files",
        ),
        (
            make_zip({**STATE, **{f"findings/previous_{i}.py": b"" for i in range(1, 22)}}),
            "more than 20 earlier finding files",
        ),
        (make_zip({**STATE, "findings/finding_1.py": b"#" * 200_001}), "larger than"),
    ],
    ids=[
        "not-a-zip",
        "no-state",
        "traversal-only",
        "big-receipt",
        "six-findings",
        "21-earlier",
        "big-finding",
    ],
)
def test_unusable_zips(data: bytes, message: str) -> None:
    with pytest.raises(action.ArtifactError, match=message):
        action.unpack_receipt(data)


def test_zip_tricks_are_refused() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive, pytest.warns(UserWarning, match="Duplicate"):
        archive.writestr("receipt.json", b"{}")
        archive.writestr("receipt.json", b"{} ")
    with pytest.raises(action.ArtifactError, match="names one file twice"):
        action.unpack_receipt(buffer.getvalue())
    encrypted = bytearray(make_zip({"receipt.json": b"{}"}, compress=False))
    for marker in (b"PK\x03\x04", b"PK\x01\x02"):  # set the "encrypted" bit in both headers
        at = encrypted.index(marker)
        offset = at + (6 if marker == b"PK\x03\x04" else 8)
        encrypted[offset] |= 0x1
    with pytest.raises(action.ArtifactError, match="encrypted"):
        action.unpack_receipt(bytes(encrypted))
    # A member whose declared size is small but whose data inflates past the limit.
    big = b"0" * (action.MAX_RECEIPT_BYTES + 100)
    lying = bytearray(make_zip({"receipt.json": big}))
    central = lying.index(b"PK\x01\x02")
    lying[central + 24 : central + 28] = (10).to_bytes(4, "little")  # uncompressed size
    with pytest.raises(action.ArtifactError):
        action.unpack_receipt(bytes(lying))


def _run(
    fake: FakeGitHub,
    run_id: int,
    *,
    path: str = WORKFLOW,
    event: str = "pull_request",
    head_repo: str = REPO,
) -> None:
    fake.runs[run_id] = {
        "id": run_id,
        "path": path,
        "event": event,
        "head_repository": {"full_name": head_repo},
    }


def test_only_this_workflows_artifacts_for_this_pr_count(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    data = make_zip(STATE)
    name = "tracefix-receipt-pr-7"
    _run(fake, 10)
    good = fake.add_artifact(name, data, 10)
    _run(fake, 11, path=".github/workflows/other.yml")
    fake.add_artifact(name, data, 11)
    _run(fake, 12, head_repo="outsider/svc")  # a fork's own pull_request run
    fake.add_artifact(name, data, 12)
    _run(fake, 13, event="pull_request_target")
    target = fake.add_artifact(name, data, 13)
    fake.add_artifact(name, data, 500)  # this run's own
    _run(fake, 14)
    expired = fake.add_artifact(name, data, 14, expired=True)
    _run(fake, 15)
    fake.add_artifact("tracefix-receipt-pr-70", data, 15)
    _run(fake, 16)
    newer = fake.add_artifact(name, data, 16)
    newer["created_at"] = "2026-10-15T09:00:00Z"
    ctx = context(tmp_path, pr_event())
    ids = [a.id for a in action.our_artifacts(ctx, client(fake), "trusted")]
    assert ids == [newer["id"], expired["id"], good["id"]]
    assert [a.id for a in action.our_artifacts(ctx, client(fake), "untrusted")] == [target["id"]]
    assert list(action.our_artifacts(replace(ctx, workflow_path=""), client(fake), "trusted")) == []


def fetched(tmp_path: Path, fake: FakeGitHub) -> tuple[str, int, list[str]]:
    ctx = context(tmp_path, pr_event())
    ctx.temp.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    folder, run_id = action.fetch_previous(ctx, client(fake), "trusted", notes)
    return folder, run_id, notes


def test_the_last_receipt_is_downloaded_and_loads(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    _run(fake, 10)
    fake.add_artifact("tracefix-receipt-pr-7", make_zip(receipt_files(tmp_path, 10)), 10)
    folder, run_id, notes = fetched(tmp_path, fake)
    assert (run_id, notes) == (10, [])
    assert Path(folder).parent == tmp_path / "runner-temp" / "tracefix"
    blob = [s for s in fake.seen if s.host == "blob"]
    assert len(blob) == 1 and blob[0].authorization is None  # the token stayed behind
    previous = load(Path(folder))
    assert previous.problem == "" and previous.head_sha


@pytest.mark.parametrize(
    "state",
    [state_json(11, verify_exit=3), state_json(11, verify_exit=2), state_json(11, verify_exit=None),
     state_json(11, verify_exit=None, skip="the checkout is shallow")],
    ids=["crashed", "nothing-to-verify", "cancelled", "skipped"],
)  # fmt: skip
def test_a_newer_run_that_wrote_no_receipt_is_passed_over(tmp_path: Path, state: bytes) -> None:
    """It showed nothing fixed: the receipt before it still holds the open findings."""
    fake = FakeGitHub(repo=REPO)
    _run(fake, 10)
    fake.add_artifact("tracefix-receipt-pr-7", make_zip(receipt_files(tmp_path, 10)), 10)
    _run(fake, 11)
    fake.add_artifact("tracefix-receipt-pr-7", make_zip({"state.json": state}), 11)
    folder, run_id, notes = fetched(tmp_path, fake)
    assert (run_id, notes) == (10, []) and load(Path(folder)).problem == ""


def _unusable(tmp_path: Path, fake: FakeGitHub) -> str:
    folder, run_id, notes = fetched(tmp_path, fake)
    assert run_id == 0 and folder and notes[0].startswith("the last receipt can't be used, so")
    problem = load(Path(folder)).problem
    assert problem.startswith("the last receipt can't be used: ")
    return problem


def test_the_newest_receipt_that_cant_be_used_makes_the_replay_inconclusive(
    tmp_path: Path,
) -> None:
    """Never passed over for an older one (verifier M9 S3; developer, 14 Oct 2026)."""
    good = make_zip(receipt_files(tmp_path, 10))
    cases = {
        "the zip can't be read": b"garbage",
        "holds no receipt.json": make_zip({"state.json": state_json(11)}),
        "not a valid state": make_zip({**receipt_files(tmp_path, 11), "state.json": b"{}"}),
        "not from the run that uploaded it": make_zip(receipt_files(tmp_path, 99)),
    }
    for says, data in cases.items():
        fake = FakeGitHub(repo=REPO)
        _run(fake, 10)
        fake.add_artifact("tracefix-receipt-pr-7", good, 10)
        _run(fake, 11)
        fake.add_artifact("tracefix-receipt-pr-7", data, 11)
        assert says in _unusable(tmp_path, fake), says
    fake = FakeGitHub(repo=REPO)
    _run(fake, 10)
    fake.add_artifact("tracefix-receipt-pr-7", good, 10)
    _run(fake, 11)
    fake.add_artifact("tracefix-receipt-pr-7", good, 11)["size_in_bytes"] = 30_000_000
    assert "is 30,000,000 bytes" in _unusable(tmp_path, fake)


def test_past_the_lookup_limit_the_replay_is_inconclusive(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    _run(fake, 10)
    fake.add_artifact("tracefix-receipt-pr-7", make_zip(receipt_files(tmp_path, 10)), 10)
    for run_id in range(11, 11 + action.MAX_RUN_LOOKUPS):
        _run(fake, run_id)
        fake.add_artifact(
            "tracefix-receipt-pr-7",
            make_zip({"state.json": state_json(run_id, verify_exit=3)}),
            run_id,
        )
    assert "no receipt among this pull request's 10 newest artifacts" in _unusable(tmp_path, fake)


NEWER = "2026-10-15T09:00:00Z"


def test_others_artifacts_dont_count_toward_the_limit(tmp_path: Path) -> None:
    """Anyone whose workflows run can upload the name (verifier M9 round 2, S3)."""
    fake = FakeGitHub(repo=REPO)
    _run(fake, 10)
    fake.add_artifact("tracefix-receipt-pr-7", make_zip(receipt_files(tmp_path, 10)), 10)
    for run_id in range(11, 11 + 3 * action.MAX_RUN_LOOKUPS):
        _run(fake, run_id, head_repo="mallory/fork")
        fake.add_artifact("tracefix-receipt-pr-7", b"junk", run_id)["created_at"] = NEWER
    fake.add_artifact("tracefix-receipt-pr-7", b"junk", 999)["created_at"] = NEWER  # run deleted
    folder, run_id, notes = fetched(tmp_path, fake)
    assert (run_id, notes) == (10, []) and load(Path(folder)).problem == ""
    for run_id in range(100, 100 + action.MAX_RUN_QUERIES):
        _run(fake, run_id, head_repo="mallory/fork")
        fake.add_artifact("tracefix-receipt-pr-7", b"junk", run_id)["created_at"] = NEWER
    assert "(100 looked up)" in _unusable(tmp_path, fake)


def test_an_expired_receipt_is_a_fresh_start_with_a_note(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    _run(fake, 10)
    fake.add_artifact("tracefix-receipt-pr-7", b"", 10, expired=True)
    assert fetched(tmp_path, fake) == (
        "", 0, ["the last receipt (run 10) has expired, so its findings were not replayed"]
    )  # fmt: skip


def test_github_errors_skip_or_fail_never_drop_the_replay(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    fake.queued = [(502, {}, b"")] * 3
    with pytest.raises(Skip, match="re-run the job"):
        fetched(tmp_path, fake)
    fake.queued = [(403, {"content-type": "application/json"}, b'{"message": "no"}')]
    with pytest.raises(ActionError, match="actions: read"):
        fetched(tmp_path, fake)


def test_no_receipt_yet_or_replay_off_fetches_nothing(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    assert fetched(tmp_path, fake) == ("", 0, [])
    ctx = context(tmp_path, pr_event(), inputs=Inputs(previous=False, has_api_key=True))
    fake.seen.clear()
    assert action.fetch_previous(ctx, client(fake), "trusted", []) == ("", 0)
    assert fake.seen == []


# --- the whole step -------------------------------------------------------------------------------


def test_prepare_a_same_repo_pull_request(tmp_path: Path, server: dict[str, Any]) -> None:
    fake = FakeGitHub(repo=REPO)
    fake.issues[1] = {"number": 1, "title": "Crash", "body": "Empty PORT"}
    event = pr_event(base=server["main"], head=server["head"], body="Fixes #1")
    ctx = server_context(tmp_path, server, event)
    ctx.temp.mkdir(parents=True)
    (ctx.temp / "receipt").mkdir()  # left by an earlier step: removed
    state = action.prepare(ctx, client(fake), probe=basic)
    assert not (ctx.temp / "receipt").exists()
    assert (state.trust, state.pr, state.skip) == ("trusted", 7, "")
    assert (state.base, state.head) == (server["fork_point"], server["head"])
    assert state.issue_source == "from #1"
    assert Path(state.issue_file).read_text(encoding="utf-8") == "# Crash\n\nEmpty PORT\n"
    assert (state.previous_dir, state.notes) == ("", ())
    action.write_state(ctx.temp / "state.json", state)
    assert action.read_state(ctx.temp / "state.json") == state


def test_prepare_records_a_skip(tmp_path: Path, server: dict[str, Any]) -> None:
    event = pr_event(
        "pull_request_target",
        head_repo="outsider/svc",
        act="labeled",
        label="tracefix",
        base=server["main"],
        head=server["head"],
    )
    ctx = server_context(tmp_path, server, event)
    state = action.prepare(ctx, client(FakeGitHub(repo=REPO)), probe=basic)
    assert state.trust == "untrusted" and "strict isolation" in state.skip
    assert (state.head, state.label, state.base) == (server["head"], "tracefix", None)
    assert not action.has_commit(server["work"], server["head"])  # nothing was fetched
    ok = action.prepare(ctx, client(FakeGitHub(repo=REPO)), probe=strict)
    assert (ok.skip, ok.base) == ("", server["fork_point"])


@pytest.mark.parametrize(
    "change",
    [
        {"head": "abc"},
        {"repo": "a/b; echo"},
        {"extra": 1},
        {"skip": "x" * 1001},
        {"notes": ["n"] * (action.MAX_NOTES + 1)},
        {"trust": "trusted-ish"},
        {"pr": "7"},
    ],
)
def test_a_forged_state_is_refused(tmp_path: Path, change: dict[str, Any]) -> None:
    state = State(repo=REPO, run_id=1, run_url="u", event="pull_request", trust="untrusted")
    path = tmp_path / "state.json"
    path.write_text(json.dumps({**state.model_dump(mode="json"), **change}), encoding="utf-8")
    with pytest.raises(ActionError, match="not a valid state"):
        action.read_state(path)


def test_log_lines_and_commands_are_escaped(capsys: pytest.CaptureFixture[str]) -> None:
    action.say("line one\n::error::forged\r\x1b[31m")
    out = capsys.readouterr().out
    assert out == "tracefix: line one ::error::forged [31m\n"
    command = action._command("notice", "a: b, c", "100%\nnext\r")
    assert command == "::notice title=a%3A b%2C c::100%25%0Anext%0D"


def test_main_fails_the_step_on_a_misconfiguration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    env = base_env(
        tmp_path, "pull_request", EVENTS / "pull_request_same_repo.json", trust="trusted"
    )
    assert action.main(["prepare"], env) == 1
    assert capsys.readouterr().out.startswith("::error title=Tracefix::input trust can only")


def test_prepare_over_real_http(tmp_path: Path, server: dict[str, Any]) -> None:
    """The step as GitHub runs it: a subprocess, its environment, and the API over HTTP."""
    fake, data = FakeGitHub(repo=REPO), make_zip(receipt_files(tmp_path, 10))
    fake.issues[1] = {"number": 1, "title": "Crash", "body": "Empty PORT"}
    _run(fake, 10)
    fake.add_artifact("tracefix-receipt-pr-7", data, 10)
    event = event_file(
        tmp_path, "pull_request_same_repo.json", base_sha=server["main"], head_sha=server["head"]
    )
    env = {**runner_env(), **base_env(tmp_path, "pull_request", event)}
    env.update(GITHUB_SERVER_URL=server["root"].as_posix())
    with fake.serve():
        env["GITHUB_API_URL"] = fake.api_url
        result = subprocess.run(
            [sys.executable, "-m", "tracefix.action", "prepare"],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f"tracefix: trusted run for pull request #7: base {server['fork_point'][:12]}, "
        f"head {server['head'][:12]}",
        "tracefix: issue text from #1",
        "tracefix: replaying the receipt of run 10",
    ]
    state = action.read_state(tmp_path / "runner-temp" / "tracefix" / "receipt" / "state.json")
    assert state.previous_run == 10 and Path(state.previous_dir, "receipt.json").is_file()
    assert {s.host for s in fake.seen} == {"api", "blob"}
    assert all(s.authorization is None for s in fake.seen if s.host == "blob")


# --- verify ---------------------------------------------------------------------------------------

BASE_SHA, HEAD_SHA = "a" * 40, "b" * 40  # the synthetic run's commits


def ready_state(**changes: Any) -> State:
    fields: dict[str, Any] = {
        "repo": REPO, "run_id": 500, "run_url": "u", "event": "pull_request", "trust": "trusted",
        "pr": 7, "base": BASE_SHA, "head": HEAD_SHA, "issue_file": "/t/issue.md",
        "issue_source": "from #1", "verify_exit": 0,
    }  # fmt: skip
    return State(**{**fields, **changes})


def test_verify_arguments(tmp_path: Path) -> None:
    out = tmp_path / "receipt"
    args = action.verify_args(ready_state(config="-x.yml"), tmp_path, out)
    assert args == ["verify", f"--repo={tmp_path}", f"--base={BASE_SHA}", f"--head={HEAD_SHA}",
                    "--issue=/t/issue.md", f"--out={out}", "--config=-x.yml"]  # fmt: skip
    strict_args = action.verify_args(
        ready_state(trust="untrusted", previous_dir="/t/previous-1"), tmp_path, out
    )
    assert strict_args[-2:] == ["--previous=/t/previous-1", "--require-strict"]
    project = action.verify_args(ready_state(), tmp_path, out, "/opt/py39/bin/python")
    assert project[-1] == "--python=/opt/py39/bin/python"


def test_verify_passes_the_project_python(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """action.yml's install step names the project's Python; verify runs its tests with it."""
    seen: list[list[str]] = []

    def record(argv: list[str], provider: object = None) -> int:
        seen.append(argv)
        return 0

    monkeypatch.setattr(action.cli, "main", record)
    env = _verify_env(tmp_path, ready_state(verify_exit=None))
    assert action.run_verify({**env, "PROJECT_PYTHON": "/opt/py39/bin/python"}) == 0
    assert action.run_verify(env) == 0
    assert seen[0][-1] == "--python=/opt/py39/bin/python"
    assert not any(a.startswith("--python") for a in seen[1])


def _verify_env(tmp_path: Path, state: State) -> dict[str, str]:
    path = action.state_path(tmp_path / "runner-temp" / "tracefix")
    path.parent.mkdir(parents=True)
    action.write_state(path, state)
    return {
        "RUNNER_TEMP": str(tmp_path / "runner-temp"),
        "GITHUB_WORKSPACE": str(tmp_path / "work"),
        "ANTHROPIC_API_KEY": "sk-ant-secret-key",
    }


def test_verify_records_nothing_to_verify(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real CLI on a folder that is not a repository: exit 2, its message kept, masked."""
    (tmp_path / "work").mkdir()
    issue = tmp_path / "issue.md"
    issue.write_text("# Crash\n", encoding="utf-8")
    env = _verify_env(tmp_path, ready_state(issue_file=str(issue), verify_exit=None))
    assert action.run_verify(env) == 0
    state = action.read_state(action.state_path(tmp_path / "runner-temp" / "tracefix"))
    assert state.verify_exit == 2
    assert state.verify_message.startswith("tracefix verify: ")
    assert str(tmp_path / "work") not in state.verify_message
    assert "<workspace>" in state.verify_message
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("::stop-commands::") and out[-2] == f"::{out[0][17:]}::"
    assert out[-1].startswith("tracefix: tracefix verify exited 2: tracefix verify: ")


def test_verify_records_a_crash_without_the_key_or_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def crash(argv: list[str], provider: object = None) -> int:
        sys.stderr.write("[1/9] environment: ok\n")
        sys.stderr.write(f"tracefix verify: internal error (a bug in Tracefix): KeyError: "
                         f"sk-ant-secret-key at {tmp_path / 'runner-temp' / 'x'}\n")  # fmt: skip
        sys.stderr.write("Traceback (most recent call last):\n  ...\n")
        return 3

    monkeypatch.setattr(action.cli, "main", crash)
    env = _verify_env(tmp_path, ready_state(verify_exit=None))
    assert action.run_verify(env) == 0
    state = action.read_state(action.state_path(tmp_path / "runner-temp" / "tracefix"))
    assert state.verify_exit == 3
    assert state.verify_message == (
        "tracefix verify: internal error (a bug in Tracefix): KeyError: *** at "
        f"<runner temp>{os.sep}x"
    )
    assert "[1/9] environment: ok" in capsys.readouterr().err  # passed through


def test_verify_does_nothing_after_a_skip(tmp_path: Path) -> None:
    env = _verify_env(tmp_path, ready_state(skip="no model API key", verify_exit=None))
    assert action.run_verify(env) == 0
    path = action.state_path(tmp_path / "runner-temp" / "tracefix")
    assert action.read_state(path).verify_exit is None
    with pytest.raises(ActionError, match="prepare step must run first"):
        action.run_verify({"RUNNER_TEMP": str(tmp_path / "elsewhere")})


# --- report ---------------------------------------------------------------------------------------

FIX_FILE = "src/svc/config.py"


def counterexample(tmp_path: Path) -> Receipt:
    ws = Workspace(tmp_path / "dummy", "main", "fix")
    ws.root = tmp_path / "copies"
    found = finding(1, path=FIX_FILE, line=12)
    record = l4_run(break_my_fix=attack(status=AttackStatus.FOUND, findings=(found,)))
    return build(record, ws)


def strict_receipt(receipt: Receipt) -> Receipt:
    """As an untrusted run's receipt is (verify refuses basic isolation there)."""
    isolation = receipt.isolation.model_copy(update={"level": "strict", "warning": None})
    return receipt.model_copy(update={"isolation": isolation})


def report_env(
    tmp_path: Path, receipt: Receipt | None, state: State, *,
    payload: str = "pull_request_same_repo.json", **inputs: str,
) -> dict[str, str]:  # fmt: skip
    event = event_file(tmp_path, payload, head_sha=state.head or HEAD_SHA)
    env = base_env(tmp_path, state.event, event, **inputs)
    env["GITHUB_RUN_ID"] = str(state.run_id)
    env["GITHUB_OUTPUT"] = str(tmp_path / "output.txt")
    env["GITHUB_STEP_SUMMARY"] = str(tmp_path / "summary.md")
    folder = action.state_path(tmp_path / "runner-temp" / "tracefix").parent
    folder.mkdir(parents=True, exist_ok=True)
    action.write_state(folder / "state.json", state)
    (folder / "receipt.json").unlink(missing_ok=True)
    (tmp_path / "output.txt").unlink(missing_ok=True)
    if receipt is not None:
        (folder / "receipt.json").write_text(receipt.model_dump_json(), encoding="utf-8")
        (folder / "receipt.md").write_text("HOSTILE ![x](https://evil) @everyone", encoding="utf-8")
    return env


def outputs(tmp_path: Path) -> dict[str, str]:
    lines = (tmp_path / "output.txt").read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines)


def report(env: dict[str, str], fake: FakeGitHub) -> int:
    return action.run_report(env, github=client(fake), now=lambda: "2026-10-14T12:00:00Z")


def test_report_posts_a_failing_check_with_the_annotation_and_one_comment(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    receipt = counterexample(tmp_path)
    env = report_env(tmp_path, receipt, ready_state())
    assert report(env, fake) == 0
    (check,) = fake.check_runs
    assert (check["head_sha"], check["status"], check["conclusion"]) == (
        HEAD_SHA, "completed", "failure")  # fmt: skip
    assert check["details_url"] == "https://github.com/octo/svc/actions/runs/500"
    first = check["output"]["annotations"][0]
    assert (first["path"], first["start_line"], first["annotation_level"]) == (
        FIX_FILE, 12, "failure")  # fmt: skip
    assert check["output"]["title"].startswith("COUNTEREXAMPLE: ")
    (posted,) = fake.comments
    body = posted["body"]
    assert body.startswith(ar.MARKER + "\n") and "HOSTILE" not in body  # re-rendered, not the md
    assert render(receipt, max_chars=ar.COMMENT_RECEIPT_CHARS) in body
    assert "HOSTILE" not in check["output"]["summary"]
    assert outputs(tmp_path) == {
        "level": "COUNTEREXAMPLE", "status": "ok", "conclusion": "failure",
        "receipt-dir": str(action.state_path(tmp_path / "runner-temp" / "tracefix").parent),
        "check-run-url": f"https://github.com/{REPO}/runs/{check['id']}",
        "comment-url": posted["html_url"],
    }  # fmt: skip
    assert (tmp_path / "summary.md").read_text(encoding="utf-8").startswith("Tracefix on commit")


def test_a_new_push_edits_the_same_comment_and_keeps_the_history(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    assert report(report_env(tmp_path, counterexample(tmp_path), ready_state()), fake) == 0
    fake.add_comment(7, f"{ar.MARKER}\nforged by someone else", "mallory")
    first = counterexample(tmp_path)
    fixed = first.model_copy(update={"head": first.head.model_copy(update={"sha": "d" * 40}),
                                     "level": EvidenceLevel.L4, "findings": []})  # fmt: skip
    env = report_env(tmp_path, fixed, ready_state(head="d" * 40, run_id=501))
    assert report(env, fake) == 0
    ours = [c for c in fake.comments if c["user"]["login"] == ar.BOT_LOGIN]
    assert len(ours) == 1 and fake.comments[1]["body"].endswith("forged by someone else")
    history = ar.parse_history(ours[0]["body"])
    assert [(e.sha[0], e.level, e.run) for e in history] == [
        ("d", EvidenceLevel.L4, 501), ("b", EvidenceLevel.COUNTEREXAMPLE, 500)]  # fmt: skip
    assert "Earlier receipts on this pull request (1)" in ours[0]["body"]
    assert [c["conclusion"] for c in fake.check_runs] == ["failure", "success"]


def test_a_skip_never_creates_a_comment_but_rewrites_ours(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    skipped = ready_state(skip="the checkout is shallow", verify_exit=None, issue_source="")
    assert report(report_env(tmp_path, None, skipped), fake) == 0
    assert fake.comments == []
    (check,) = fake.check_runs
    assert (check["conclusion"], check["output"]["title"]) == (
        "neutral", "Not verified: the checkout is shallow")  # fmt: skip
    assert outputs(tmp_path)["status"] == "not_verified"
    old = ar.with_entry((), ar.Entry(sha="c" * 40, level=EvidenceLevel.L2, status="ok",
                                     when="2026-10-13T12:00:00Z", run=400))  # fmt: skip
    body = ar.comment_body(ar.Header("c" * 40, "u", "a", "b"), ar.Report(None, "x"), old,
                           lambda run: f"https://x/{run}")  # fmt: skip
    fake.add_comment(7, body, ar.BOT_LOGIN)
    assert report(report_env(tmp_path, None, skipped), fake) == 0
    (rewritten,) = fake.comments
    assert "Tracefix did not verify this commit: the checkout is shallow" in rewritten["body"]
    assert [e.sha[0] for e in ar.parse_history(rewritten["body"])] == ["b", "c"]


def test_a_tracefix_crash_fails_the_step_with_a_neutral_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGitHub(repo=REPO)
    crashed = ready_state(verify_exit=3, verify_message="tracefix verify: internal error: boom")
    assert report(report_env(tmp_path, None, crashed), fake) == 1
    (check,) = fake.check_runs
    assert check["conclusion"] == "neutral"
    assert check["output"]["title"] == "Tracefix failed: tracefix verify: internal error: boom"
    assert capsys.readouterr().out.splitlines()[-1].startswith("::error title=Tracefix failed::")
    nothing = ready_state(verify_exit=2, verify_message="tracefix verify: not a git repository")
    assert report(report_env(tmp_path, None, nothing), fake) == 0
    assert fake.check_runs[-1]["output"]["title"].startswith("Not verified: tracefix verify: ")
    assert report(report_env(tmp_path, None, ready_state(verify_exit=None)), fake) == 1


def test_min_level_and_switches_come_from_the_reports_own_inputs(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    l2 = counterexample(tmp_path).model_copy(update={"level": EvidenceLevel.L2, "findings": []})
    assert report(report_env(tmp_path, l2, ready_state(), min_level="L3"), fake) == 0
    assert fake.check_runs[-1]["conclusion"] == "failure"
    assert report(report_env(tmp_path, l2, ready_state()), fake) == 0
    assert fake.check_runs[-1]["conclusion"] == "success"
    env = report_env(tmp_path, counterexample(tmp_path), ready_state(), comment="false",
                     annotations="false")  # fmt: skip
    fake.comments.clear()
    assert report(env, fake) == 0
    assert fake.comments == [] and fake.check_runs[-1]["output"]["annotations"] == []


@pytest.mark.parametrize(
    "changes",
    [{"run_id": 499}, {"pr": 8}, {"repo": "octo/other"}, {"head": "c" * 40}],
    ids=["other-run", "other-pr", "other-repo", "other-head"],
)
def test_a_state_from_another_run_is_refused(tmp_path: Path, changes: dict[str, Any]) -> None:
    fake = FakeGitHub(repo=REPO)
    env = report_env(tmp_path, counterexample(tmp_path), ready_state())
    action.write_state(action.state_path(tmp_path / "runner-temp" / "tracefix"),
                       ready_state(**changes))  # fmt: skip
    with pytest.raises(ActionError, match="not from this run"):
        report(env, fake)
    assert fake.seen == []


def _refused(fake: FakeGitHub, env: dict[str, str], says: str) -> None:
    """Never used: the step fails, after a check run saying Tracefix failed (verifier M9 N11)."""
    assert report(env, fake) == 1
    check = fake.check_runs[-1]
    assert (check["conclusion"], check["output"]["title"][:16]) == ("neutral", "Tracefix failed:")
    assert says in check["output"]["title"] + check["output"]["summary"]


def test_a_receipt_for_other_commits_or_forged_is_refused(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    first = counterexample(tmp_path)
    other = first.model_copy(update={"base": first.base.model_copy(update={"sha": "e" * 40})})
    _refused(fake, report_env(tmp_path, other, ready_state()), "other commits")
    env = report_env(tmp_path, None, ready_state())
    folder = action.state_path(tmp_path / "runner-temp" / "tracefix").parent
    (folder / "receipt.json").write_text('{"level": "L4"}', encoding="utf-8")
    _refused(fake, env, "not a valid receipt")
    assert len(fake.check_runs) == 2


def test_an_untrusted_runs_receipt_must_say_strict(tmp_path: Path) -> None:
    """Defense in depth (verifier M9 N10): verify already refused basic isolation there."""
    fake = FakeGitHub(repo=REPO)
    basic = counterexample(tmp_path)
    assert basic.isolation.level == "basic"
    state = ready_state(event="pull_request_target", trust="untrusted")
    env = report_env(tmp_path, basic, state, payload="pull_request_target_labeled.json")
    _refused(fake, env, "says basic isolation, but this run was untrusted")
    assert report(report_env(tmp_path, strict_receipt(basic), state,
                             payload="pull_request_target_labeled.json"), fake) == 0  # fmt: skip
    assert fake.check_runs[-1]["conclusion"] == "failure"  # the counterexample


def test_a_read_only_token_on_a_fork_pr_is_a_note(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeGitHub(repo=REPO)
    denied = (403, {}, b'{"message": "Resource not accessible by integration"}')
    fake.queued = [denied]
    skipped = ready_state(skip="a pull request from a fork gets no secrets", verify_exit=None,
                          trust="untrusted")  # fmt: skip
    env = report_env(tmp_path, None, skipped, payload="pull_request_fork.json")
    assert report(env, fake) == 0
    assert "the token is read-only on a pull request from a fork" in capsys.readouterr().out
    fake.queued = [denied]
    same_repo = report_env(tmp_path, counterexample(tmp_path), ready_state())
    with pytest.raises(ActionError, match="permissions: checks: write"):
        report(same_repo, fake)


def test_the_label_flow_removes_the_approval_label(tmp_path: Path) -> None:
    fake = FakeGitHub(repo=REPO)
    fake.labels[7] = ["tracefix", "bug"]
    state = ready_state(event="pull_request_target", trust="untrusted", label="tracefix")
    env = report_env(tmp_path, strict_receipt(counterexample(tmp_path)), state,
                     payload="pull_request_target_labeled.json")  # fmt: skip
    assert report(env, fake) == 0
    assert fake.labels[7] == ["bug"]
    assert report(env, fake) == 0  # already gone: fine


def test_main_knows_each_step(tmp_path: Path) -> None:
    assert set(action.STEPS) == {"prepare", "verify", "report"}
    env = base_env(tmp_path, "pull_request", EVENTS / "pull_request_same_repo.json")
    assert action.main(["report"], env) == 1  # no state.json: a misconfiguration
