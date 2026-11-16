# Tracefix milestones

One milestone per session. Each ends with: tests green, `verifier` subagent review addressed, commit.
Status of each milestone: `docs/ROADMAP.md` (the only place it is kept).
Do not start the next milestone until the previous one's acceptance criteria are met.

Original estimates were in days; milestones have actually taken hours (see `docs/ROADMAP.md`, Pace).
The figures below are the rough size observed so far, not deadlines.

## Rules every milestone from M4 on must respect

These were decided in M1, M3 and M3.5 and are in `docs/SPEC.md`; new stages must not bypass them.

- **Isolation (M3.5, SPEC §4).** Every execution of repo or generated code goes through
  `isolation.run_checked` (or `isolation.check_environment`), in the Workspace copies, never in the
  user's working copy. New copies (e.g. Guard's reverted or mutated head) must be exported and
  recorded the same way, so tamper detection covers them. Tampering makes the stage `invalid`, never a
  verdict. Each stage result records its isolation level.
- **Verdicts from runs only.** A stage verdict comes from exit codes, JUnit reports, diffs or counters.
  A run whose exit code and report disagree is an error, not a result.
- **Tests at both isolation levels.** A test that depends on basic-mode behaviour needs an explicit
  strict-mode branch (Linux CI runs strict). Attack tests must prove their write happened (basic) or
  was blocked for the expected reason (strict); they must never pass vacuously.
- **No simulated replacements.** Replacing a real test with a simulated one counts as weakening it and
  needs the developer's approval (CLAUDE.md).

## M0 — Skeleton
- `uv` project, `src/tracefix/`, CLI stub (`tracefix --help`), ruff/mypy/pytest config, CI workflow
  running lint + tests.
- Accept: `uv run pytest` passes; `uv run tracefix --help` prints usage.

## M1 — Ground-truth fixtures ← most important milestone
Create 8 tiny git repos under `tests/fixtures/` via a script (`scripts/make_fixtures.py`) that builds
them with real commits (base = buggy, head = fix). Each has an `expected.json`.
1. `good_fix` — correct fix for an off-by-one; expected ≥ L2.
2. `partial_fix` — fixes `None` but not empty string; Break My Fix must find `""`.
3. `wrong_but_green` — fix passes the repro but changes behaviour for negatives; behaviour diff must flag it.
4. `test_weakened` — fix deletes an assert in an existing test; integrity must flag it.
5. `special_cased` — fix adds `if year == 2100 and month == 2: return 28`; integrity reports it
   and Break My Fix finds another century year (2200) still wrong. *(Changed in M5 by the
   developer: a hard-coded value is report only in integrity, see DECISIONS.)*
6. `unguarded_test` — provided test passes even with fix reverted; guard must fail.
7. `no_fix` — head doesn't fix the bug; result `fix_does_not_fix`.
8. `env_broken` — missing dependency; result `ENVIRONMENT_ERROR`.
- Accept: script builds all repos reproducibly; a README table lists each case and expected result.

## M2 — Workspace, runner, diff scope
- Ref resolution, test runner with timeout + reruns, changed-function detection, test-vs-source split.
  (Worktrees were replaced by plain copies in M3.5.)
- Accept: unit tests over all fixtures; env_broken detected; no LLM involved.

## M3 — LLM layer + Reproducer
- Provider interface, Anthropic provider, recorded provider, pydantic schemas, budgets.
- Reproducer with 3-attempt loop and fail-to-pass validation.
- `fix_does_not_fix` rule (decided in M3, SPEC 2.3): only if no attempt reproduced AND the last attempt
  failed on base and head with the same failure signatures AND the model had already been shown that
  result.
- Accept: recorded tests reproduce fixtures 1–7; `no_fix` → fix_does_not_fix; one opt-in live test.

## M3.5 — Execution isolation
- Plain copies exported from git objects (no `.git` link to the user's repo), tamper detection around
  every run, strict isolation with bubblewrap on Linux, basic isolation with a warning elsewhere,
  isolation level in every result, exit-code/report cross-check.
- Accept: malicious generated tests that edit the other copy, Tracefix's environment or the user's
  repository are caught (basic) or blocked for the expected reason (strict), each by a test; CI runs
  Linux in strict mode and fails if it falls back to basic; README and SPEC explain how to run
  untrusted changes.

## M4 — Guard (a few hours)
- Revert check + LLM mutations applied deterministically, following SPEC 2.4, including the rules
  decided in M1:
  - if the PR adds or modifies tests and *all* of them still pass on the reverted code, the result is
    `not_guarded`, whatever the mutation check says;
  - a mutant is killed if the repro test, the PR's tests or the existing suite fails; mutations that
    don't import or compile are discarded and not counted;
  - `guarded` needs: repro test fails on the reverted code, the PR's tests (if any) don't all pass on
    it, and ≥ 80% of valid mutants killed.
- The reverted and mutated trees are new isolated copies (see the rules above). *(Built as one
  extra exported copy of head, files swapped in per run and checked against head at the end;
  see DECISIONS 2026-10-02.)*
- Accept: `unguarded_test` fails guard; `good_fix` passes guard; the result shows which test set
  (repro / PR test / suite) killed each mutant and the repro test's own kill rate separately; every run
  goes through the tamper watch, at both isolation levels.

## M5 — Integrity audit
- Accept: flags `test_weakened`; reports `special_cased`'s hard-coded `2100` without flagging it
  (developer, 5 Oct 2026); zero flags on `good_fix` and on every case without an integrity
  `must_find`.

## M6 — Break My Fix ← hero feature
- Boundary attacks, LLM properties, Hypothesis search, finding validation (standalone repro file),
  pre-existing detection (SPEC 2.6, decided in M1), dedupe.
- Accept: finds `""` in `partial_fix` and a century year (e.g. `days_in_month(2200, 2)` → 29) in
  `special_cased`, each with a runnable repro file; no findings on `good_fix`
  (false alarm = failure); every finding's repro file actually fails when run on head, in an isolated
  copy.

## M7 — Behaviour diff + Judge
- Accept: `wrong_but_green` shows suspicious change for negative inputs; `good_fix` changes are
  labelled intended or absent; the L3 rule guarantees a model label can never raise the level.

## M7.5 — Methods as Break My Fix targets (and behaviour diff targets)
- Today Break My Fix attacks module-level functions only; a fix inside a method is skipped with a
  note, and on real repos that is likely the largest gap (real-bug trial, 6 Oct 2026).
- Build `self` from `st.builds` on the class or a model-proposed constructor call that passes the
  same hygiene as other expressions; properties may also use `self`'s public attributes. Classes
  that need I/O or global setup to construct are skipped with a reason.
- *(Developer, 9 Oct 2026:)* the behaviour diff compares methods too: the object's state after the
  call and its class's data are compared; special methods, property setters and methods of
  nested classes still keep L3 out of reach. Objects Tracefix makes up count only for properties
  whose `when` names `self`. Plan: `docs/plans/M7.5.md`.
- Accept: a new fixture whose bug and partial fix sit in a method gives a proven finding; a correct
  method fix gives none; a changed method is compared on base and head, its object's state
  included; the existing fixtures' answers are unchanged.

## M8 — Receipt + end-to-end CLI
- Ladder computation, JSON schema, markdown rendering, `tracefix verify` end to end, `tracefix.yml`.
- The Judge's receipt-level call (moved from M7): the two-sentence summary and a note beside each
  integrity flag (it can never dismiss one). L3 = L2 and the behaviour diff's `l3_gate`.
- Break My Fix findings that are one bug found through two properties (e.g. both adversary samples
  wrote the same rule; real-bug trial run 4) are shown as one finding; decide the grouping rule so two
  different bugs with the same output are never merged.
- *(Developer, 13 Oct 2026, plan mode; plan: `docs/plans/M8.md`:)* L4 is strict (Break My Fix found
  nothing, every changed function attacked to the end with at least 100 inputs and at least one
  counted model property that constrains its result, every executable fix line run by the attacks,
  and, since verifier round 1, the integrity audit and the no-regression check finished clean);
  a confirmed regression (an untouched test that passed before the fix fails after it, on every
  rerun) is a COUNTEREXAMPLE; tampering in any stage caps the level at L0 (a proven counterexample
  stays); tests run in the project's own environment, with the copies' packages ahead of installed
  ones and a check that every changed module is imported from the copy (no `--python`, no `setup`
  command yet). Also in M8: the ROADMAP rows for confirming the head pass, model and budget settings,
  account-caused failures and stable mutant IDs.
- Accept: every fixture's receipt matches `expected.json` level; receipt.md fits ~60 lines; the receipt
  shows the isolation level and the basic-isolation warning when it applies; `tracefix verify` runs end
  to end from the CLI and its JSON output alone can be read by an agent.
  Graded by `tests/test_pipeline_recorded.py`: `tracefix verify` on each fixture with recorded
  answers, checked from `receipt.json` alone (level bound, status, stage statuses, every
  `must_find` and `must_not_find`), with no stage error and no model problem.

## M9 — GitHub Action
- `action.yml`, Check Run + single updated PR comment, artefact upload, docs on fork-PR safety.
- *(Developer, 14 Oct 2026, plan mode; plan: `docs/plans/M9.md`:)*
  - Fork PRs are skipped on `pull_request` and run only after a maintainer adds the `tracefix`
    label. That starts a `pull_request_target` workflow:
    - the environment is built from the base branch;
    - the PR's code stays git data until it runs inside bubblewrap;
    - strict isolation is required;
    - results are posted by a second job that never holds the API key;
    - the label is removed after each run.
  - On each new push, the last receipt's findings are re-run, and L4 also needs every one of them
    fixed. A still-failing one is not a COUNTEREXAMPLE by itself.
  - The live run uses a private demo repo with a small Actions budget (Tracefix stays private).
  - The live model spend ceiling is $5.
  - Also in M9: the ROADMAP rows for inline annotations, one PR comment edited in place with the
    earlier verdicts, and the replay of the last receipt.
- Accept: works on a test repo you own (a private demo; developer, 14 Oct 2026: a public repo
  can't use an action from a private one), on a real PR:
  - a partial fix gets a failing Tracefix check, an annotation on the fixed line and a receipt
    comment;
  - a later push edits the same comment and says which earlier findings it fixed;
  - untrusted (fork) PRs run only with strict isolation, after a maintainer's label.

## M10 — Benchmark harness
Split in two by the developer (15 Oct 2026; plan: `docs/plans/M10.md`), because Tracefix needs
Python 3.11+ and most of SWE-bench Verified and PatchDiff runs on 3.6–3.10.
- **Part 1:** a harness that selects, prepares, runs and scores tasks reproducibly from pinned
  data, in each task's Docker image (`scripts/benchmark.py`). Tasks from the SWE-rebench
  leaderboard on Python 3.11+ with pytest; the correct class is the upstream fix, the incorrect
  class the same fix with one source hunk removed, kept only when the hidden tests then fail.
  Slice 1 (~20–30 tasks) within $60 of model spend, a report whose every number comes from a run
  or the developer's label, and a fixed dev/held-out split for M11.
  - Accept: `report` rebuilds `report.md` byte for byte from the committed files; the default
    suite tests the harness with no network, Docker or API key; results and caveats in
    `docs/BENCHMARK.md`.
- **Part 2** (plan: `docs/plans/M10-part2.md`, approved 21 Oct 2026): run the project's tests
  with an older interpreter (3.9/3.10) while Tracefix stays on 3.11+, then slice 2 on
  SWE-rebench tasks with real OpenHands agent patches, right and wrong, beside gold and partial
  fixes (the AI-fix audit). SWE-bench Verified and PatchDiff wait for a later slice (developer,
  21 Oct 2026: unclear licence of their agent patches, suites over the 180 s cap).
  - Accept: `tracefix verify --python` gives a 3.9 fixture its known answer with the same
    isolation and tamper watch; the report gives wrong and right agent fixes' rates by split;
    spend ≤ $60.

## M11 — Slice 2's weak spots
- Re-planned from M10 slice 2's findings (developer, 4 Nov 2026, plan mode; plan:
  `docs/plans/M11.md`). It replaces "Break My Fix recall on thin issues" (21 Oct plan). That
  plan's first three steps were built in M10 part 2; the rest is a ROADMAP row.
- Scope:
  - Guard's few model mutants (NOTES 24);
  - Break My Fix runs that try no input (NOTES 33);
  - false alarms from warnings and from inputs or objects outside a function's domain (NOTES 39,
    40, 30);
  - wrong agent fixes reaching L2 through the Reproducer's own test (NOTES 42);
  - from prove-your-tests: rule mutants spread over kinds, with drop-call and re-raise kinds and
    the kinds shown; more tricky strings; $0 measurements of "replaced code still exists
    elsewhere" and "a test reads the code's own constant".
- What changes a verdict in M11: a warning that only the project's filters turn into an error is
  not a raise. Three other rules (deliberate refusals the same on base, OS refusals, finished
  objects) and a blind reproduction test are report only. The developer decides them after the
  rerun.
- Accept:
  - every fixture keeps its answer;
  - on slice 2's dev split, arm B (M11) against arm A (M10), paired and anchored (unchanged
    requests replay M10's answers):
    - median valid model mutants ≥ 7, read only on runs Guard did not stop early (`not_run` = 0;
      developer, 6 Nov 2026, before any S10 result), and the Guard verdicts one mutant from the
      other side at most half of A's;
    - Break My Fix runs with no input down by at least a third (≤ 22/145);
    - correct-fix false alarms no more than A's 8/85;
    - wrong agent fixes not green-lit no fewer than A's 16/20;
    - median ≤ 5 min and p90 ≤ 20 min per run;
  - the report-only rules' counterfactuals and the $0 measurements are reported. Dev numbers
    show direction only; the held_out split is the test.
- Result (13 Nov 2026; arm B is `benchmarks/results/slice2-m11`, numbers in `docs/BENCHMARK.md`):
  - every fixture kept its answer;
  - met: the mutant median (7 on runs played to the end, A 5: on the line), false alarms (7/85,
    A 8/85), wrong agent fixes not green-lit (16/20, A 16/20), time (median 3.2 min, p90 14.7 min,
    with the one run that hit the 2-hour limit counted at its 2 hours);
  - **missed, and recorded as missed, not reworded** (developer, 13 Nov 2026): Guard verdicts one
    mutant from the other side (87/118, 74%; A 49/115, 43%; the limit was half of A's) and Break
    My Fix runs with no input (31/144; A 33/144; the limit was 22). Why neither could be met by
    what M11 built: NOTES 24 and 33. The follow-ups are ROADMAP rows;
  - reported: the doubt flags and the blind test's counterfactuals, the tricky strings, and the
    sibling-site measurement (nothing built from it; its constant-read signal met the rule's bar
    for "build", 6 of 162, and was left out after all 6 hits were read by hand: DECISIONS
    2026-11-05);
  - decided from them by the developer (13 Nov 2026): the doubt flags stay report only until the
    held_out split, with the rule to test there fixed now; the blind test will cap a receipt at
    L1, as a step of its own after M11. M11 itself changes one thing a level reads: a warning is
    not a raise.
