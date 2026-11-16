# Roadmap

Updated at the end of every milestone. Acceptance criteria are in `docs/MILESTONES.md`.

## Milestones

| # | Milestone | Status | Purpose |
|---|---|---|---|
| M0 | Skeleton | Done (`baf652e`) | uv project, CLI stub, lint/types/tests config and CI. |
| M1 | Ground-truth fixtures | Done (`34961fb`) | Eight buggy repos with known answers, the ground truth for everything else. |
| M2 | Workspace, runner, diff scope | Done (`68ac6c2`) | Refs resolved to exact commits, a pytest runner with timeout and reruns, and changed-function detection. (Its worktrees were replaced by plain copies in M3.5.) |
| M3 | LLM layer + Reproducer | Done (`2d2c944`) | Provider interface plus recorded provider; generate and validate fail-to-pass tests. |
| M3.5 | Execution isolation | Done (`c23030d`, merged in PR #1 as `52ec716`) | Plain copies, tamper detection around every run, bubblewrap sandbox on Linux, basic isolation with a warning elsewhere. |
| M4 | Guard | Done (`389ab04`, PR #8) | Revert-the-fix and mutation checks: does the test actually guard the fix? |
| M5 | Integrity audit | Done (`c406ec4`, PR #17; cleanup PR #18) | Detect test weakening (confirmed by running the old tests on the fixed code) and report special-casing. |
| M6 | Break My Fix | Done (`4509547`, merged in PR #22 as `eba1a46`, 7 Oct 2026) | Hero feature: find concrete inputs that break the fixed code. |
| M7 | Behaviour diff + Judge | Done (`a689db6`, merged in PR #23 as `a03f9b5`, 8 Oct 2026) | Run the same inputs on base vs head; an advisory LLM labels the changes. L3 claims no unexplained change in what the diff observes; the rest is listed as unchecked. |
| M7.5 | Methods as Break My Fix targets (and behaviour diff targets) | Done (`c09c1f7`, merged in PR #24 as `fb49e44`, 12 Oct 2026; plan: `docs/plans/M7.5.md`) | Attack fixes inside class methods (today skipped) and compare them on base and head; the largest gap the real-bug trial showed. |
| M8 | Receipt + end-to-end CLI | Done (`a33619f`, merged in PR #25, 13 Oct 2026; plan: `docs/plans/M8.md`) | Evidence ladder, receipt.json/receipt.md, `tracefix verify` end to end. |
| M9 | GitHub Action | Done (`bff5a20`, merged in PR #28 as `e6468e2`, 15 Oct 2026, CI skipped: see side tasks; plan: `docs/plans/M9.md`) | Check Run plus a PR comment on real PRs. |
| M10 | Benchmark harness | Part 1 done (`d19af3c`, merged in PR #30 as `fdb669e`, 20 Oct 2026, CI skipped: see DECISIONS; slice 1: 22 ready tasks, 56 runs, $12.56 by the receipts plus 2 timeouts of unknown cost; results `docs/BENCHMARK.md`; plan: `docs/plans/M10.md`). Part 2 done 4 Nov 2026 (`502be86`, PR #35; plan: `docs/plans/M10-part2.md`): `tracefix verify --python` for 3.9/3.10 projects, and slice 2 on SWE-rebench's dev split with real OpenHands agent patches: 145 runs, about $37-40 of real spend (results `docs/BENCHMARK.md`, gates below). Slice 2's held_out split, SWE-bench Verified and PatchDiff wait for later slices. **M10 closed 4 Nov 2026** with the Windows CI fit (PR #39, `4f69bbf`) | Measure Tracefix on real bug fixes and on agent-written ones. |
| M11 | Slice 2's weak spots | Done 13 Nov 2026 (PR #48, branch `m11-s9`, checks on `38eca02`; plan: `docs/plans/M11.md`, replacing the 21 Oct "thin issues" plan, whose first three steps were built in M10 part 2). Slice 2's dev split run again with M11's code, anchored on M10's answers (145 runs, about $8 of the $30): 4 of 6 targets met; **2 missed and recorded as missed** (developer): Guard verdicts one mutant from the other side (87/118, was 49/115) and Break My Fix runs with no input (31/144, was 33; limit 22). One false alarm gone (7/85, was 8/85), no wrong fix's level changed. Developer, 13 Nov 2026: the doubt flags stay report only until held_out; the blind test will cap at L1 in a step of its own (side tasks). Results: `docs/BENCHMARK.md` | Fix what slice 2 showed: Guard's few mutants, Break My Fix runs with no input, false alarms from warnings and out-of-domain inputs, wrong agent fixes reaching L2 through the Reproducer; report-only checks from prove-your-tests; measured on slice 2 dev against M10. |

## Release gate

Developer, 20 Oct 2026: Tracefix is released (Action published, any launch) only
after every gate below holds. Each is a worry from M10 slice 1; the numbers are proposals the
developer can change. Measured on benchmark tasks Tracefix was not tuned on (the `held_out`
split), with real agent patches where it says so; each benchmark run is the developer's call
(it costs money). Slice 2's columns are its dev split, so they show the direction, not a gate
passed (`docs/BENCHMARK.md`). The M11 column is the same dev fixes run again with M11's code,
after M11 was tuned on them, replaying M10's model answers where the request was unchanged
(which also flatters its times). The held_out split is still unrun.

| # | Gate | Slice 1 (20 Oct 2026) | Slice 2, dev (4 Nov 2026) | Slice 2, dev, M11's code (13 Nov 2026) | Target | Status |
|---|---|---|---|---|---|---|
| 1 | **Certifies correct fixes**: gold fixes at ≥ L2 / ≥ L3 | 5/19 (26%) / 0 | 12/47 (26%) / 0 | 11/47 (23%) / 0 | ≥ 50% / ≥ 20% | Open |
| 2 | **Few false alarms**: correct fixes (gold and correct agent fixes) given a COUNTEREXAMPLE that the developer labels false | 3/19 (16%) | 8/85 (9%) | 7/85 (8%) | ≤ 5% | Open |
| 3 | **Catches real agent mistakes**: wrong agent fixes not green-lit / caught (COUNTEREXAMPLE) | not measured (synthetic partial fixes only: 11/12, 7/12) | 16/20 (80%) / 6/20 (30%) (partial fixes: 26/28, 19/28) | 16/20 (80%) / 6/20 (30%) (partial fixes: 26/28, 19/28) | ≥ 90% / ≥ 50% | Open |
| 4 | **Enough data**: correct and wrong fixes in the measurement | 19 gold, 12 partial | 85 correct (47 gold, 38 agent), 20 wrong agent (plus 28 partial) | the same fixes | ≥ 40 and ≥ 30 | Open (30 wrong agent fixes on held_out still needed) |
| 5 | **Stable**: COUNTEREXAMPLE verdict changes between two runs of the same fix / Break My Fix runs no input | 2/18 (11%) / 6/54 (11%) | not measured (no repeats) / 33/145 (23%) | not measured (no repeats) / 31/144 (22%) | ≤ 5% / ≤ 3%, over ≥ 20 repeated fixes | Open |
| 6 | **Fast enough for CI**: median / 90th percentile time per run, two-hour timeouts | 6.5 min / 38 min, 2 timeouts in 36 runs | 3.7 min / 16.5 min, no timeouts in 145 runs | 3.2 min / 14.7 min, 1 timeout in 145 runs (counted in both times) | ≤ 5 min / ≤ 15 min, none | Open |
| 7 | **Someone wants it**: conversations with people who review AI-written PRs | 0 | 0 | 0 | ≥ 5, notes kept | Open |
