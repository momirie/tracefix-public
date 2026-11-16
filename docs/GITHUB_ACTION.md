# Tracefix as a GitHub Action

The Action runs `tracefix verify` on every push to a pull request and posts the Fix Receipt where
the fix gets reviewed:
- a **check run** named `Tracefix`, whose conclusion our code computes from the receipt's level;
- **one PR comment** with the receipt, edited in place on every push, with the earlier verdicts in
  a collapsed table;
- **inline annotations** on the lines a finding, a regression or an integrity flag points at;
- the receipt folder as an **artifact** (`tracefix-receipt-pr-<N>`). On the next push, the last
  receipt's findings are run again, so the new receipt says which ones that commit fixed.

It is a composite action (no Docker, no JavaScript): `action.yml` wires the steps together, and the
logic is Python in `src/tracefix/action.py` and `action_report.py`.

## Quickstart

Copy [`examples/tracefix.yml`](examples/tracefix.yml) to `.github/workflows/tracefix.yml`, and add
your Anthropic API key as the repository secret `ANTHROPIC_API_KEY`
(`gh secret set ANTHROPIC_API_KEY`). The heart of it:

```yaml
on:
  pull_request:

permissions: {}

jobs:
  tracefix:
    runs-on: ubuntu-24.04 # bubblewrap (strict isolation) is known to work here
    timeout-minutes: 30
    permissions:
      contents: read
      checks: write # the Tracefix check run
      pull-requests: write # the one receipt comment
      issues: read # the text of the issues the pull request closes
      actions: read # the last receipt of this pull request, to replay its findings
    steps:
      - uses: actions/checkout@<sha> # v7
        with:
          fetch-depth: 0 # Tracefix needs the base and head commits
          persist-credentials: false # no token left on disk while tests run
      - uses: astral-sh/setup-uv@<sha>
      - run: uv sync --locked # your project's environment, with its test dependencies
      - uses: momirie/tracefix@<sha> # pin a Tracefix commit
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

Your tests run with your project's Python (the `.venv` the step before made, or the `python`
input), 3.9 or newer, with your dependencies. The action adds Hypothesis 6.141 or newer there
when it has none, and upgrades one older than that (Break My Fix needs it; if your tests rely on
an older Hypothesis, the receipt's regression check shows it). Tracefix itself runs from its own
environment: uv's Python 3.11 with the dependency versions in Tracefix's `uv.lock`, so it never
changes your project's other packages.
Pin it, and every other action, to a full commit id.

The issue text comes from the issues the PR closes ("Fixes #12" in its description), else from the
PR's title and description. Write the closing reference, and the receipt checks the fix against
the bug report rather than against the PR's own summary of it.

## Inputs

| Input | Default | What it does |
|---|---|---|
| `anthropic-api-key` | none | The model key, from a secret. Without it the run is skipped with a notice. |
| `github-token` | `${{ github.token }}` | For the check run, the comment, the issue text and the last receipt. |
| `python` | `.venv`'s interpreter, else `python` on PATH | The project's interpreter (3.9+), whose environment holds the project and its test dependencies; it runs the tests. |
| `issue` | the closed issues, else the PR | The issue text itself (not a file path). |
| `base`, `head` | the PR's merge base and head commit | Other commits to verify; both are needed for an event with no PR (`workflow_dispatch`). |
| `config` | `tracefix.yml` at the base commit | Another settings file ([USAGE](USAGE.md#settings)). |
| `min-level` | none | `L1`–`L4`: a receipt below it, or no receipt, makes the check fail. |
| `trust` | `auto` | `untrusted` forces the fork rules (strict isolation required). It can only make a run stricter. |
| `comment`, `annotations`, `previous`, `report` | `true` | Turn off the comment, the annotations, the replay of the last receipt, or posting from this job (the fork flow posts from a second job). |

Outputs: `level`, `status`, `conclusion` (`success`, `failure` or `neutral`), `receipt-dir`,
`check-run-url`, `comment-url`.

## Permissions

| Permission | Why |
|---|---|
| `contents: read` | the base and head commits |
| `checks: write` | the `Tracefix` check run |
| `pull-requests: write` | the one receipt comment |
| `issues: read` | the text of the issues the PR closes |
| `actions: read` | the last receipt's artifact, to replay its findings |

A missing write permission fails the report step and names it. Set `permissions: {}` at the top of
the workflow and grant these on the job, so no other job gets them by default.

## What you see

**The check run.** Its conclusion comes from the receipt only:

| Receipt | Conclusion |
|---|---|
| tampering detected | failure |
| `COUNTEREXAMPLE` | failure |
| a level below `min-level` (when set) | failure |
| `L0`, or no receipt (skipped, nothing to verify, Tracefix failed) | neutral (failure when `min-level` is set) |
| `L1`–`L4` | success |

Its title is the level and what it means ("L2: the tests guard the fix") or "Not verified:
<reason>"; its summary is the receipt. The job itself never fails because of a verdict: the
verdict is the check. Make the check required in branch protection to block merges on it, or use
the `conclusion` output. The job fails only on a misconfiguration (a missing permission, a bad
input) or when Tracefix itself crashed.

**The comment.** One per PR, starting with a header line (the commit, the run, the artifact, where
the issue text came from), then the receipt, then "Earlier receipts on this pull request (N)": a
table of commit, level, status, time and run for each earlier push (at most 20). When a push can't
be verified (a skip or a crash), the comment says so instead of showing the old receipt as
current. No comment is created just for a skip.

**Annotations**, at most 50, failures first: Break My Fix findings on the fixed line the failing
call ran, confirmed regressions on the test's line, integrity flags; then warnings for the last
receipt's findings this commit didn't fix, and notices for "a change no test noticed" (surviving
mutants). The rest are counted in the check summary.

**The artifact** `tracefix-receipt-pr-<N>`: `receipt.json`, `receipt.md`, the reproduction test,
each finding's pytest file and `state.json` (what the run verified). Each push replaces it.

## Cost and time

Each run makes up to `max_llm_calls` model calls (default 40); the receipt shows the calls, tokens
and estimated cost. On the live demo (the `partial_fix` fixture as a project, 14 Oct 2026) each
run made 7 calls for $0.10–0.17 at list prices, and the Action's step took 3–4 minutes on
`ubuntu-24.04` (the whole job about 4). Guard runs your suite once per mutant,
so time grows with your suite: give the job a `timeout-minutes`, and set `suite_timeout_seconds`
and `max_llm_calls` in `tracefix.yml` at the base branch. A newer push cancels the run it replaces
(the examples' `concurrency` block).

## Re-runs and replay

- **Replay.** Before verifying, the Action downloads the last receipt of this PR: the newest
  `tracefix-receipt-pr-<N>` artifact from an earlier run of the same workflow file in this
  repository (from a `pull_request_target` run in the fork flow) that holds a receipt; a run that
  wrote none (a skip, or Tracefix failed) is passed over. Each of its findings, and each earlier
  one it still lists as open, runs again on the new commit (`tracefix verify --previous`,
  [SPEC 2.10](SPEC.md)). A finding counts as fixed only after 3 clean passes in a row. L4 also
  needs every earlier finding fixed; one that still fails keeps the level at L3 or below, is
  carried into the new receipt, and is replayed again on every later push until it is fixed. It
  is never a COUNTEREXAMPLE by itself.
- **When the last receipt can't be used** (a damaged or oversized artifact, or none among this
  workflow's 10 newest), the replay is inconclusive, which keeps that run below L4; its receipt
  then starts afresh from its own findings. A finding whose test can't run any more (say, its
  function was renamed) keeps one push below L4 and is then dropped. When GitHub doesn't answer,
  the run is not verified (re-run the job); when it refuses, the step fails (the job needs
  `permissions: actions: read`).
- **Re-running a job** verifies the same commit again: the comment's history entry for that commit
  is replaced, not added. A re-run replays the receipt of the run before it, never its own.
- **Artifacts expire** after your repository's retention period (90 days by default). After that,
  there is nothing to replay: the log notes it, and the receipt doesn't mention the earlier
  findings.

## Fork pull requests

A pull request from a fork is code from someone who may not be trusted, and the run holds your
model key. Tracefix handles that in three ways: trust is decided by our code from the event, never
by an input that could loosen it; untrusted code runs only inside bubblewrap; the job that posts
results never holds the key.

### Who is trusted

- **Trusted:** a `pull_request` from a branch of this repository, and the events only people with
  write access can start (`workflow_dispatch`, `push`, `schedule`). GitHub already gives these
  workflows your secrets, so their authors are trusted with them. The environment is built from
  the PR's checkout. Tracefix still runs every test in its sandbox, at strict isolation when
  bubblewrap works and basic otherwise.
- **Untrusted:** `pull_request_target`, any PR whose head is in another repository, any other
  event, or the input `trust: untrusted`. Strict isolation is required: without bubblewrap the run
  is refused with the reason, never run at basic isolation.

### Why the normal workflow skips forks

On `pull_request`, GitHub gives a fork's PR no secrets and a read-only token, which is what keeps
your key safe. The Action skips it with a notice pointing to the label flow, instead of failing.

### The label flow

[`examples/tracefix-fork.yml`](examples/tracefix-fork.yml) runs on `pull_request_target` when a
maintainer adds the `tracefix` label, after reading the PR. `pull_request_target` runs the base
branch's workflow with your secrets, which is exactly why the PR's code must never run outside the
sandbox there. Line by line:

1. **Trigger:** `pull_request_target: [labeled]`, and each job only for the `tracefix` label.
2. **Job `verify`** has `contents: read`, `issues: read` and `actions: read`, and the model key.
   - It checks out the **base branch only**, and installs the **base branch's** dependencies. A
     PR's dependency changes are not installed, because installing them would run its code
     outside the sandbox, where it could leave a process behind that reads later steps' secrets.
   - Tracefix fetches the PR's commits as git data (the token goes to git through environment
     variables, never on the command line or in `.git/config`). It verifies the exact commit the
     maintainer saw when labelling (the event's `head.sha`); if that commit was force-pushed away,
     the run is refused.
   - It refuses to run when the checkout already contains the PR's commits: that catches the
     classic mistake of checking out the PR in a `pull_request_target` workflow.
   - It runs with `trust: untrusted` (strict isolation required, and `tracefix verify
     --require-strict`) and `report: false`, and uploads the receipt as an artifact.
3. **Job `report`** has `checks: write` and `pull-requests: write`, and **no model key**. It runs
   [`report/action.yml`](../report/action.yml), which installs Tracefix from the action's own
   folder into a throwaway environment and runs no project code. It treats the artifact as
   untrusted data: `state.json` must belong to this run, this PR and its head commit;
   `receipt.json` is validated strictly; the comment and check are rendered again from it (the
   artifact's `receipt.md` is never posted). `min-level`, `comment` and `annotations` are this
   job's inputs.
4. **The label is removed** after the run, so each new commit needs a maintainer's new approval.

Never add a step that checks out or installs the PR's code to this workflow.

### What strict isolation protects, and what it doesn't

Strict isolation runs every test (the project's, the PR's and the model-written ones) inside
bubblewrap: a read-only system, only the copy under test and its scratch folder writable, no
network, its own process namespace, and `$HOME` hidden (on a runner, that is where the checkout and
the runner's temp folder live). The environment is allowlisted, so the model key and the token are
not in it.

It does not protect against:
- **an escape from bubblewrap** (a kernel bug). Code that escaped could read the key and forge the
  artifact, and so the verdict: the verdict's integrity rests on the sandbox.
- **a test lying about its own result.** A test runs inside the pytest process and can patch it;
  isolation stops damage, not lying. Guard's re-runs, the cross-checks and the receipt naming the
  oracle limit this ([SPEC §4](SPEC.md)).
- **the base branch's own dependencies.** They are installed and trusted as your code.
- **instructions in the PR, issue or code.** They reach the models as data. A model only proposes
  tests and properties; every verdict comes from runs, which happen inside the sandbox.

Ubuntu 24.04 restricts the user namespaces bubblewrap needs; the Action lifts that restriction on
GitHub's own runners, which are throwaway machines. On a **self-hosted runner** it changes nothing
(the setting would outlive the job): allow unprivileged user namespaces yourself
(`kernel.apparmor_restrict_unprivileged_userns=0`, or an AppArmor profile for `bwrap`), or the run
is basic isolation, and an untrusted one is refused. The examples pin `ubuntu-24.04`, where this
is known to work. Ubuntu 26.04 (`ubuntu-latest` from 19 Oct 2026) is not yet checked.

## Limits

- **Python and pytest only**, like Tracefix itself; the project's environment must hold Tracefix's
  own dependencies (pytest, pydantic, Hypothesis) at versions that fit.
- **Fork PRs use the base branch's dependencies**, so a fix that needs a new dependency can't pass
  there.
- **Tracefix's own dependencies are resolved into your environment** (within its declared
  ranges, not its lockfile), because it runs your tests with your packages; pin them in your
  project if you need that. The fork flow's report job, which runs no project code, installs them
  at the locked versions.
- **The comment's author** is matched to find our comment: `github-actions[bot]` for the workflow
  token, the token's user for a personal token. A GitHub App token gets a new comment on each run.
- **At most 50 annotations**; the rest are in the check summary and `receipt.json`.
- **The replay reaches back only as far as artifact retention.**
- **All check runs made with the workflow token are grouped under one workflow in GitHub's UI**
  (a GitHub quirk), so the `Tracefix` check may appear under another workflow's name.
- **Run time on large suites:** Guard runs the suite once per mutant (see Cost and time).
