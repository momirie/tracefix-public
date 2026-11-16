"""M9 end to end: the Action's Python steps in GitHub's order, as action.yml wires them.

Each test plays whole workflow runs on a pull request. The test sets up:
- a fixture repo pushed to a local bare "server" (`<server>/octo/svc.git`, the pull request's
  commit at refs/pull/7/head, as on GitHub), and a fresh checkout of main for each run;
- a real event payload;
- the loopback GitHub fake (tests/github_fake.py).

The steps then run as the runner runs them:
- prepare and report run as subprocesses, so the real HTTP and git code runs;
- verify runs in this process with the recorded model answers (no network, no spend);
- between verify and report, the receipt folder is zipped into the fake's artifact store, as the
  upload-artifact step does.

Each step's environment is built from action.yml's own `env:` entries, so the key reaches only
verify and the token only prepare and report, here as on GitHub.
"""

from __future__ import annotations

import io
import json
import re
import shlex
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import make_fixtures
import pytest
from github_fake import FakeGitHub
from test_action import runner_env
from test_action_yml import ACTION, load, step
from test_guard_recorded import provider

from tracefix import action
from tracefix import action_report as ar
from tracefix.ladder import EvidenceLevel
from tracefix.previous import Replay
from tracefix.receipt import Receipt

REPO = "octo/svc"
PR = 7
WORKFLOW = ".github/workflows/tracefix.yml"
TOKEN = "ghs_e2e_token"
KEY = "sk-ant-e2e-not-a-real-key"
PAYLOAD = Path(__file__).parent / "github_events" / "pull_request_same_repo.json"
# What the workflow passes the action (`with:`); every other input keeps action.yml's default.
WITH = {"anthropic-api-key": KEY}


def git(repo: Path, *args: str) -> str:
    return make_fixtures.git(repo, *args)


@dataclass
class Server:
    """The repository on "GitHub": the fixture's two commits, main at the base one."""

    root: Path  # GITHUB_SERVER_URL: git fetches <root>/octo/svc.git
    origin: Path  # where new pull request commits are made
    base: str
    head: str

    @property
    def bare(self) -> Path:
        return self.root / "octo" / "svc.git"

    def push(self, files: dict[str, str], message: str) -> str:
        """A new commit on the pull request's branch: its id."""
        for rel, content in files.items():
            (self.origin / rel).write_text(content, encoding="utf-8", newline="\n")
        git(self.origin, "add", "--all")
        git(self.origin, "commit", "--quiet", "--no-verify", "-m", message)
        git(self.origin, "push", "--quiet", str(self.bare), "HEAD:refs/pull/7/head")
        self.head = git(self.origin, "rev-parse", "HEAD")
        return self.head


def github_server(tmp_path: Path, case: str) -> Server:
    origin = make_fixtures.build_case(case, tmp_path / "built")
    base = git(origin, "rev-parse", make_fixtures.tag_ref("base"))
    head = git(origin, "rev-parse", make_fixtures.tag_ref("head"))
    server = Server(tmp_path / "server", origin, base, head)
    server.bare.parent.mkdir(parents=True)
    git(tmp_path, "clone", "--quiet", "--bare", str(origin), str(server.bare))
    git(server.bare, "update-ref", "refs/heads/main", base)
    git(server.bare, "update-ref", "refs/pull/7/head", head)
    git(server.bare, "tag", "--delete", "base", "head")
    return server


def action_inputs() -> dict[str, str]:
    """The action's inputs: action.yml's defaults, then the workflow's `with:`."""
    inputs = {}
    for name, spec in load(ACTION)["inputs"].items():
        default = str(spec.get("default", ""))
        inputs[name] = TOKEN if default == "${{ github.token }}" else default
    return {**inputs, **WITH}


def step_env(step_id: str) -> dict[str, str]:
    """The `env:` action.yml gives one step, its expressions evaluated as GitHub would."""
    found = step(ACTION, step_id)
    assert found["run"] == f'"$PY" -P -m tracefix.action {step_id}'
    inputs, env = action_inputs(), {}
    for name, value in found["env"].items():
        expr = re.fullmatch(r"\$\{\{ (.+) \}\}", value)
        assert expr, value
        if expr[1] in ("steps.python.outputs.path", "steps.python.outputs.project"):
            env[name] = sys.executable  # Tracefix's Python, and here the project's too
        elif match := re.fullmatch(r"inputs\.([\w-]+) != ''", expr[1]):
            env[name] = "true" if inputs[match[1]] else "false"
        else:
            match = re.fullmatch(r"inputs\.([\w-]+)", expr[1])
            assert match, value
            env[name] = inputs[match[1]]
    return env


@dataclass
class Job:
    """One workflow run of the trusted example (docs/examples/tracefix.yml) on a fresh runner."""

    tmp: Path
    server: Server
    fake: FakeGitHub
    run_id: int
    body: str = "Fixes #1"
    title: str = "Fix crash when PORT is unset"
    event_action: str = "synchronize"
    printed: dict[str, str] = field(default_factory=dict)

    @property
    def root(self) -> Path:
        return self.tmp / f"run-{self.run_id}"

    @property
    def receipt_dir(self) -> Path:
        return action.state_path(self.root / "temp" / "tracefix").parent

    def github_env(self, step_id: str) -> dict[str, str]:
        """The variables GitHub sets for every step (an output and summary file per step)."""
        return {
            "GITHUB_REPOSITORY": REPO,
            "GITHUB_RUN_ID": str(self.run_id),
            "GITHUB_WORKSPACE": str(self.root / "work"),
            "RUNNER_TEMP": str(self.root / "temp"),
            "GITHUB_SERVER_URL": self.server.root.as_posix(),
            "GITHUB_API_URL": self.fake.api_url,
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_EVENT_PATH": str(self.root / "event.json"),
            "GITHUB_WORKFLOW_REF": f"{REPO}/{WORKFLOW}@refs/pull/{PR}/merge",
            "GITHUB_OUTPUT": str(self.root / f"{step_id}-output.txt"),
            "GITHUB_STEP_SUMMARY": str(self.root / f"{step_id}-summary.md"),
        }

    def outputs(self, step_id: str) -> dict[str, str]:
        path = self.root / f"{step_id}-output.txt"
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        return dict(line.split("=", 1) for line in lines)

    def checkout(self) -> None:
        """actions/checkout with fetch-depth 0 of the base branch, plus the event payload."""
        self.root.mkdir(parents=True)
        git(self.tmp, "clone", "--quiet", "--single-branch", "--branch", "main",
            self.server.bare.as_uri(), str(self.root / "work"))  # fmt: skip
        payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
        payload["action"] = self.event_action
        pr = payload["pull_request"]
        pr.update(number=PR, title=self.title, body=self.body)
        pr["base"]["sha"], pr["head"]["sha"] = self.server.base, self.server.head
        (self.root / "event.json").write_text(json.dumps(payload), encoding="utf-8")

    def subprocess_step(self, step_id: str) -> int:
        env = {**runner_env(), **self.github_env(step_id), **step_env(step_id)}
        result = subprocess.run(
            [sys.executable, "-P", "-m", "tracefix.action", step_id],
            env=env, capture_output=True, text=True, timeout=300,
        )  # fmt: skip
        self.printed[step_id] = result.stdout
        assert not result.stderr.strip(), result.stderr
        return result.returncode

    def verify(self) -> None:
        env = {**self.github_env("verify"), **step_env("verify")}
        assert env["ANTHROPIC_API_KEY"] == KEY
        assert action.run_verify(env, provider=provider()) == 0

    def upload(self) -> None:
        """actions/upload-artifact: the receipt folder, zipped, under prepare's artifact name."""
        prepared = self.outputs("prepare")
        buffer = io.BytesIO()
        folder = Path(prepared["receipt-dir"])
        with zipfile.ZipFile(buffer, "w") as archive:
            for path in sorted(p for p in folder.rglob("*") if p.is_file()):
                archive.write(path, path.relative_to(folder).as_posix())
        self.fake.add_artifact(prepared["artifact-name"], buffer.getvalue(), self.run_id)
        self.fake.runs[self.run_id] = {"id": self.run_id, "path": WORKFLOW,
                                       "event": "pull_request",
                                       "head_repository": {"full_name": REPO}}  # fmt: skip

    def run(self) -> None:
        """The composite action's steps, with their `if:` conditions."""
        self.checkout()
        assert self.subprocess_step("prepare") == 0
        assert self.outputs("prepare")["skip"] == "false", self.printed["prepare"]
        self.verify()
        self.upload()
        assert self.subprocess_step("report") == 0, self.printed["report"]

    def state(self) -> action.State:
        return action.read_state(self.receipt_dir / "state.json")

    def receipt(self) -> Receipt:
        raw = (self.receipt_dir / "receipt.json").read_text(encoding="utf-8")
        return Receipt.model_validate_json(raw)


def the_comment(fake: FakeGitHub) -> dict[str, Any]:
    (comment,) = fake.comments
    assert comment["user"]["login"] == ar.BOT_LOGIN
    assert comment["body"].startswith(ar.MARKER + "\n")
    return comment


def actions_fake() -> FakeGitHub:
    """GitHub as the workflow token sees it: GET /user is refused (the token is not a user)."""
    return FakeGitHub(repo=REPO, token=TOKEN, login=None)


def test_env_broken_two_pushes_one_comment(tmp_path: Path) -> None:
    """A run that can't verify (the project's dependency can't be installed): a neutral L0
    check and a comment. A second push edits that comment, which keeps the first verdict."""
    server = github_server(tmp_path, "env_broken")
    fake = actions_fake()
    fake.issues[1] = {"number": 1, "title": "Week off by one", "body": "On Mondays."}
    with fake.serve():
        first = Job(tmp_path, server, fake, 500)
        first.run()
        assert first.state().verify_exit == 0
        assert first.receipt().status.value == "ENVIRONMENT_ERROR"
        (check,) = fake.check_runs
        assert (check["head_sha"], check["conclusion"]) == (server.head, "neutral")
        assert check["output"]["title"].startswith("L0: ")
        comment = dict(the_comment(fake))  # the fake edits its own dict in place
        assert first.outputs("report") == {
            "level": "L0", "status": "ENVIRONMENT_ERROR", "conclusion": "neutral",
            "receipt-dir": str(first.receipt_dir),
            "check-run-url": check["html_url"], "comment-url": comment["html_url"],
        }  # fmt: skip

        first_head = server.head
        second_head = server.push({"NOTES.md": "Week numbers follow ISO 8601.\n"}, "Add a note")
        second = Job(tmp_path, server, fake, 501)
        second.run()

    assert [c["head_sha"] for c in fake.check_runs] == [first_head, second_head]
    edited = the_comment(fake)
    assert edited["id"] == comment["id"] and edited["body"] != comment["body"]
    history = ar.parse_history(edited["body"])
    assert [(e.sha, e.level, e.status, e.run) for e in history] == [
        (second_head, EvidenceLevel.L0, "ENVIRONMENT_ERROR", 501),
        (first_head, EvidenceLevel.L0, "ENVIRONMENT_ERROR", 500),
    ]
    assert f"`{first_head[:7]}`" in edited["body"]  # the earlier verdict's row
    # The second run fetched the first one's receipt through the artifacts API and its redirect.
    blob = [s for s in fake.seen if s.host == "blob"]
    assert len(blob) == 1 and blob[0].authorization is None
    assert "tracefix: replaying the receipt of run 500" in second.printed["prepare"]


def test_partial_fix_counterexample_then_replay(tmp_path: Path) -> None:
    """The headline flow: issue text from the issue the pull request closes; a failing check with
    the counterexample's annotation on the fixed line; one comment; the receipt artifact. A later
    run on the same commit fetches that artifact, replays finding 1 (it still fails) and edits
    the same comment."""
    server = github_server(tmp_path, "partial_fix")
    issue = (make_fixtures.FIXTURES_DIR / "partial_fix" / "ISSUE.md").read_text(encoding="utf-8")
    title, body = issue.removeprefix("# ").split("\n", 1)
    fake = actions_fake()
    fake.issues[1] = {"number": 1, "title": title, "body": body}
    with fake.serve():
        first = Job(tmp_path, server, fake, 500)
        first.run()
        state = first.state()
        assert (state.base, state.head, state.issue_source) == (server.base, server.head,
                                                                 "from #1")  # fmt: skip
        # Byte for byte the fixture's issue, so the recorded model answers apply.
        assert Path(state.issue_file).read_text(encoding="utf-8") == issue
        receipt = first.receipt()
        assert receipt.level is EvidenceLevel.COUNTEREXAMPLE and receipt.previous is None
        (check,) = fake.check_runs
        assert (check["head_sha"], check["conclusion"]) == (server.head, "failure")
        failures = [a for a in check["output"]["annotations"]
                    if a["annotation_level"] == "failure"]  # fmt: skip
        assert failures and (failures[0]["path"], failures[0]["start_line"]) == (
            "src/svc/config.py", 34)  # `if raw is None:`, the fix's first line  # fmt: skip
        assert "parse_port" in failures[0]["message"]
        comment = dict(the_comment(fake))
        (artifact,) = fake.artifacts
        assert artifact["name"] == f"tracefix-receipt-pr-{PR}"

        again = Job(tmp_path, server, fake, 501, event_action="reopened")
        again.run()

    assert "tracefix: replaying the receipt of run 500" in again.printed["prepare"]
    replayed = again.receipt()
    assert replayed.level is EvidenceLevel.COUNTEREXAMPLE
    assert replayed.previous is not None and replayed.previous.head_sha == server.head
    (old,) = [f for f in replayed.previous.findings if f.number == 1]
    assert old.result is Replay.STILL_FAILS
    assert len(fake.check_runs) == 2 and fake.check_runs[1]["conclusion"] == "failure"
    edited = the_comment(fake)
    assert edited["id"] == comment["id"]
    assert "still fails" in edited["body"]
    # A run on the same commit replaces that commit's entry: one entry, the newer run's.
    assert [(e.sha, e.run) for e in ar.parse_history(edited["body"])] == [(server.head, 501)]
    blob = [s for s in fake.seen if s.host == "blob"]
    assert len(blob) == 1 and blob[0].authorization is None
    assert all(s.authorization == f"Bearer {TOKEN}" for s in fake.seen if s.host == "api")


@pytest.mark.parametrize("step_id", ["prepare", "verify", "report"])
def test_each_step_gets_only_its_secret(step_id: str) -> None:
    """The environments these tests give the steps are action.yml's: the key only in verify's,
    the token only in prepare's and report's."""
    env = step_env(step_id)
    assert (env.get("ANTHROPIC_API_KEY") == KEY) is (step_id == "verify")
    assert (env.get("INPUT_GITHUB_TOKEN") == TOKEN) is (step_id != "verify")
    assert KEY not in {v for k, v in env.items() if k != "ANTHROPIC_API_KEY"}


def test_files_in_the_checkout_never_replace_the_actions_modules(tmp_path: Path) -> None:
    """The steps start in the checkout: with `-P` (as action.yml runs them) its root is not on
    sys.path, so a project's own `secrets.py` or `tracefix/` can't run in their place (verifier
    M9 S4)."""
    (tmp_path / "secrets.py").write_text("print('PLANTED secrets')\n", encoding="utf-8")
    (tmp_path / "tracefix").mkdir()
    (tmp_path / "tracefix" / "__init__.py").write_text("print('PLANTED tracefix')\n", "utf-8")
    command = shlex.split(step(ACTION, "prepare")["run"].replace('"$PY"', "python"))
    assert command[:3] == ["python", "-P", "-m"]
    result = subprocess.run([sys.executable, *command[1:], "--help"], cwd=tmp_path,
                            capture_output=True, text=True, timeout=60)  # fmt: skip
    assert result.returncode == 0 and "PLANTED" not in result.stdout + result.stderr
    assert "python -m tracefix.action" in result.stdout
