# Benchmark

How well does Tracefix tell a correct fix from an incomplete one, on real projects it has never
seen? This page gives the method, how to run it, the results of slices 1 and 2, M11's second
run of slice 2 and what they don't show. Every number below comes from
`benchmarks/results/<slice>/report.md` (M11's also from its `compare-slice2.md`), which `report`
and `compare` rebuild from the committed runs, receipts and labels (a test checks they do, byte
for byte; data and provenance: `benchmarks/README.md`; the plans: `docs/plans/M10.md`,
`docs/plans/M10-part2.md`, `docs/plans/M11.md`).

## Method

**Tasks.** Real bug fixes from the SWE-rebench leaderboard (Nebius, CC BY 4.0): 860 merged
fixes from 302 open-source Python projects, Jan 2025 – May 2026, each with a Docker image and
hidden tests (the tests the upstream PR added or changed, which show whether a fix works).
Tracefix runs inside the project's own interpreter, so only projects on Python 3.11+ with pytest
qualify; at most 2 tasks per project, in a fixed rank order.

**Two fixes per task.**
- *Correct*: the upstream fix (the "gold" patch). Tracefix should not raise a counterexample.
- *Partial*: the gold patch with one source hunk removed. It is kept only when the hidden tests
  then fail, so every partial fix is proven incomplete. Tracefix should not green-light it.

Tracefix sees what a reviewer would: the repo at the base commit, the fix, and the issue text. It
never sees the hidden tests or the PR's own test changes.

**Prepare** (in each task's container, before any model call). The base suite must pass and
finish within 180 s, the hidden tests must fail on base and pass on gold, and the image must be at
the base commit. Each check that fails excludes the task, with its reason.

**Run.** `tracefix verify` once per fix, in Docker, with strict isolation (bubblewrap) and a 2-hour
limit per run. A partial fix's findings are then replayed on the gold fix: `fixed` on gold means
the finding pointed at exactly what the removed hunk did, confirmed by our own run.

**Labels.** Every finding on a gold fix, and every partial-fix finding the gold fix doesn't pass,
is judged by the developer (`benchmarks/labels/slice1.json`): `real_bug`, `false_alarm` or
`unclear`. Claude proposes labels with its reasons; only the developer's count in the headline
rates. A gold COUNTEREXAMPLE with no finding behind it (the Reproducer's `fix_does_not_fix`) is
labelled as the run itself. Each label names the receipt it judged (its `created_at`): a run tried
again keeps its tag but gets a new receipt, so the old label stops counting and `label` replaces
it with an empty entry (the old verdict kept in its note).

**Set aside.** A COUNTEREXAMPLE whose only causes are regressions in test files the PR's own test
patch changed says nothing about the fix (the upstream PR updated those tests with it), so it is
counted apart and left out of the gold, partial and separation rates (developer, 17 Oct 2026).

**API errors.** A run in which a model call failed for a reason outside Tracefix (network, API
outage, rate limit, billing, credentials) measured the API, not the fix: it is left out of every
number and run again by the next `run`. Model failures that are Tracefix's own (budget used up,
invalid output, a refusal) still count. So does a `run` without `--live` that met a model call
with no recorded answer (outcome `no_recording`): its model stages never ran.

**Hidden tests stay out of the run.** Only prepare's container gets the PR's test patch and the
commits with the hidden tests; each run's fresh container is made from the base, gold and partial
patches alone, so nothing run during `verify` can read them.

**Split.** A third of the tasks (by a hash of the task id) are held out for M11: tune on `dev`,
report on `held_out`.

**Slice 2 adds real agent fixes** (M10 part 2). Its tasks come from the full SWE-rebench task set
(21,336 rows, Python 3.9–3.13), and each task can have two more fixes, both written by an
OpenHands agent (Qwen3-Coder) in Nebius's published runs:
- *agent_wrong*: an agent patch the hidden tests fail on. Read like a partial fix: Tracefix should
  not green-light it.
- *agent_ok*: one they pass. Read like gold: Tracefix should not raise a counterexample. Gold and
  agent_ok together are the "correct fixes".

The dataset's own verdict only picks the candidates; prepare runs the hidden tests on each patch
itself, and a patch whose result disagrees is left out and counted. Tracefix sees the agent's
whole patch, tests the agent wrote included, as a reviewer would. Projects on Python 3.9 or 3.10
run their tests with their own interpreter (`tracefix verify --python`), while Tracefix runs from
a 3.11 environment of its own in the same container.

## How to run

Needs Docker and, for live runs, `ANTHROPIC_API_KEY`. All commands are
`uv run python scripts/benchmark.py <command>`; `--help` lists the options.

```
select  --slice slice1 --limit 80          # choose tasks from the pinned dataset rows
prepare --limit 80                         # run the checks above in each task's container
run --live --max-spend 20                  # verify every ready fix (refuses to pass the ceiling)
run --live --max-spend 25 --limit 35 --repeats 2   # a second run of the first tasks
label                                      # add an empty label for each finding to judge
report                                     # write report.md and summary.json
```

Slice 2 was prepared and run on its dev split only: `prepare --slice slice2 --split dev --limit N`
(in chunks of rising N), then `run --slice slice2 --split dev --live --max-spend 70`.

M11's arm B: `run --slice slice2 --split dev --results m11 --anchored --max-spend 25` (slice 2's
recordings copied in as the anchor; in this mode the ceiling counts live calls only), then
`label`, `report` and `compare --slice slice2 --b m11`, each with `--slice slice2`, the first two
also with `--results m11`.

`run` without `--live` replays recorded model answers, with no network. The spend guard adds
what receipts report spending plus a reserve per run in flight, and starts no run that could pass
`--max-spend`. Interrupted runs resume where they stopped.

## Results: slice 1 (October 2026)

80 tasks chosen of 860; 22 passed prepare (16 with a partial variant); 38 runs on the first
repeat (22 gold, 16 partial), 2 of them timed out (one task, both fixes) and 2 hit an API
outage (mitmproxy, both fixes: no model call got through), so 34 count. Models: claude-sonnet-5-5 (Reproducer,
mutator), claude-opus-5-5 (adversary, Judge).

| | |
|---|---|
| **Partial fixes not green-lit** (COUNTEREXAMPLE or ≤ L1) | 11/12 (92%) |
| **Partial fixes caught** (COUNTEREXAMPLE) | 7/12 (58%) |
| **Leftover bug found** (a finding confirmed `fixed` on gold) | 4/12 (33%) |
| Partial fixes at L2 (a false pass) | 1/12 (8%) |
| **Gold COUNTEREXAMPLE** | 4/19 (21%) |
| … a real bug in the merged fix | 1/19 (5%) |
| … a false alarm (developer label) | 3/19 (16%) |
| Gold at ≥ L2 / ≥ L3 / L4 | 5/19 (26%) / 0 / 0 |
| Gold above its partial fix | 6/12 (50%) |
| Reproducer fail-to-pass on gold | 18/20 (90%) |
| Set aside (regressions only in tests the PR updated) | gold 1/20, partial 2/14 |
| Cost per run | mean $0.24, median $0.20, max $0.68 |
| Time per run | median 6.5 min, 90th percentile 38 min, mean 15 min, max 69 min (plus 2 two-hour timeouts) |

What this says in plain words:

- **Tracefix rarely green-lights an incomplete fix** (1 of 12 reached L2), and in 4 of 12 it found
  the exact input the missing hunk handles. But it **also rarely certifies a correct one**: no gold
  fix reached L3, and only 5 of 19 reached L2.
- **One gold "false alarm" is a real bug in the merged fix.** joke2k/django-environ#592 adds
  `extra_options`, but `db_url_config` returns early for `sqlite://:memory:`, so the options are
  silently dropped for that URL (the fix's own docstring says they are merged).
- **The false alarms have named causes**, each an M11 item: attacking an `@abstractmethod`
  (NOTES #30), a property quoting one exception counting an unrelated one (NOTES #31), and a
  Reproducer test that never reached the fix yet decided a COUNTEREXAMPLE (NOTES #29).
- **Why correct fixes stall:**
  - At L1, Guard: all 9 gold runs at L1 stopped at the 80% kill bar, with only 4–8 mutants
    (one survivor moves the rate by 12–25 points). No kill was crash-only (0 of 52 on gold).
  - At L2, the behaviour diff: the L3 gate never opened (0/20 gold). The first blockers were
    special methods (`__init__`, `__array_ufunc__`) not yet called, module-level code that
    computes a value, a comparison that didn't finish, and no changed function compared. A rule
    documented only in prose never got that far.
- **Break My Fix skipped 6 of 20 gold runs**: each time the fix changed no function it can call
  yet (4 of them only special methods such as `__init__` or `__repr__`, 1 a nested function).
- **Guard is the time cost**: mean 8.5 of a run's 15 minutes (it runs the suite once per mutant).
  The one task with a ~3-minute suite timed out at 2 hours on both fixes.

### Stability (repeated runs)

The first 10 tasks ran a second time (18 fixes: 2 of the tasks have no partial variant; 18 runs,
$4.52, no timeouts). How often the second run differed from the first:

| | |
|---|---|
| **COUNTEREXAMPLE or not** (what the gold and partial rates rest on) | 2/18 (11%) |
| Level | 6/18 (33%) |
| Guard's status | 4/18 (22%) |
| Having a Break My Fix finding | 4/18 (22%) |

- **Both verdict changes are one task, virtualizarr-979, and both are Break My Fix.** On gold, the
  first run's false alarm (NOTES #31) did not come back. On the partial fix, the first run's real
  catch was lost: the second run's attack crashed before trying a single input (NOTES #33).
- **Level changes without a verdict change come from the 80% Guard line and the Reproducer.**
  Two runs crossed the line with a different set of mutants (sqlglot-6413 gold, pelita-863 gold: 0
  of 5 killed, then guarded), and two reproduced the bug only the second time (L0 → L1).
- **The twyn-317 abstract-method false alarm (NOTES #30) moved between runs**: gold in the first
  run, the partial fix in the second.

So one run per fix gives a stable verdict in 16 of 18 cases here, but its level is a sample, not a
fixed property of the fix.

### Where the funnel lost tasks

Of 860 rows: 261 on Python below 3.11, 10 invalid, 3 with compiled sources, 3 with no source
change, 1 with no pytest command, 96 over the 2-per-repo cap, and 406 past the 80-task limit. Of the 80 prepared: 39 base suites can't run in the image (24 a
missing optional module, 2 tampering detected), 14 take over 180 s, 4 hidden tests fail on gold,
1 image isn't at the base commit. 5 of the 22 ready tasks needed files git ignores (a generated
`_version.py`); the harness commits them first, a real CI run would not have them.

## Results: slice 2 (November 2026, dev split)

150 tasks chosen of 21,336 (109 dev, 41 held out); the held-out tasks stay unrun until M11's
changes are done (developer, 22 Oct 2026). 111 prepared, 56 ready, 54 of them dev. 145 runs, every
one with a receipt, at strict isolation, no timeouts: 54 gold, 30 partial, 22 agent_wrong, 39
agent_ok. 12 are set aside (regressions only in tests the PR updated: gold 7, partial 2,
agent_wrong 2, agent_ok 1), so 133 count. The runs cover 54 tasks, 53 of them on Python 3.9
or 3.10 (the project's own interpreter) and 1 on 3.11: most SWE-rebench tasks with an image
and agent runs are 3.9 projects. Models as in slice 1. Every finding is labelled by the
developer (37 in all: 24 false alarm, 12 real bug, 1 unclear).

| | Slice 2 | Slice 1 |
|---|---|---|
| **Wrong agent fixes not green-lit** (COUNTEREXAMPLE or ≤ L1) | 16/20 (80%) | not measured |
| **Wrong agent fixes caught** (COUNTEREXAMPLE) | 6/20 (30%) | not measured |
| Wrong agent fixes at L2 (a false pass) | 4/20 (20%) | not measured |
| **Partial fixes not green-lit** / caught | 26/28 (93%) / 19/28 (68%) | 11/12 (92%) / 7/12 (58%) |
| Leftover bug found: partial / wrong agent fix | 3/28 (11%) / 0/20 | 4/12 (33%) / - |
| **Correct fixes with a false alarm** (gold and agent_ok) | 8/85 (9%) | gold only: 3/19 (16%) |
| … gold / agent_ok | 6/47 (13%) / 2/38 (5%) | |
| Real bugs found in correct fixes (developer label) | gold 3/47, agent_ok 3/38 | gold 1/19 |
| Gold at ≥ L2 / ≥ L3 / L4 | 12/47 (26%) / 0 / 0 | 5/19 (26%) / 0 / 0 |
| agent_ok at ≥ L2 / ≥ L3 | 10/38 (26%) / 0 | |
| Gold above its partial fix | 16/24 (67%) | 6/12 (50%) |
| Gold above / same as / below the wrong agent fix | 3/17 (18%) / 8/17 / 6/17 (35%) | |
| Reproducer fail-to-pass on gold | 49/54 (91%) | 18/20 (90%) |
| Break My Fix ran no input (all runs) | 33/145 (23%) | 6/54 (11%) |
| Cost per run | mean $0.23, median $0.21, max $0.72 | mean $0.24, median $0.20, max $0.68 |
| Time per run | median 3.7 min, 90th percentile 16.5 min, mean 7.9 min, max 87 min, no timeouts | median 6.5 min, 90th percentile 38 min, 2 timeouts |

Spend: $33.56 by the receipts for the 145 runs. With the 3.9 fixture's recording ($0.11), the
smoke run ($2.28) and two asgiref-211 runs redone after the model was paid ($0.36), part 2
spent about $36.31 that is recorded, plus some that isn't: two runs lost when the editor
crashed (under $1) and the boxes that kept working after the 22 Oct Ctrl+C (NOTES #38). So
about $37-40 in all, under the plan's $60. The spend guard counted $60.56, because 9 lines from the interrupted
22 Oct run have no cost and it reserves $3 for each (NOTES #38); the developer raised the ceiling
to $70 for the rest.

What this says in plain words:

- **On real agent mistakes Tracefix is a brake, not yet a detector.** It kept 16 of 20 wrong
  agent fixes from looking verified, but caught only 6, and by our own runs only 1 of those 6
  rests on what the agent got wrong: dissect.cstruct-88 (the Reproducer's test still failed on
  the agent's patch; on gold its own run reproduced the bug cleanly). mqtt-exporter-37's
  finding is labelled a real bug, but gold gives the same answer for it (replay `still_fails`:
  gold keeps the topic's full name only when `KEEP_FULL_TOPIC` is on, which is off by default).
  The other 4 rest on something gold shares: a real bug that is also in base and gold
  (clldutils-27), a regression gold has too (ocdskit-51), or a Break My Fix false alarm
  (babelfish-50, nibabies-395). No finding on a wrong agent fix was confirmed `fixed` on gold.
- **Most wrong agent fixes do nothing.** 21 of the 24 wrong agent patches prepare kept leave the
  hidden tests failing exactly as on base; 3 fix part of the bug.
- **4 wrong agent fixes reached L2, each through the Reproducer.** In all 4 (briefcase-645,
  autodocsumm-101, dphon-366, nipype-3658) the Reproducer's own test failed before the agent's
  patch and passed after it, and Guard found the tests guard the patch; only nipype-3658's
  Guard also ran a test file the agent wrote. Likely (not yet checked) the Reproducer read the
  issue the way the agent did, so the bug it reproduced is the one the agent fixed. Gold ranked
  below the wrong agent fix in 6 of 17 tasks: these 4, and 2 where gold had a COUNTEREXAMPLE
  (proxy.py-137's real bug, httpx-883 labelled unclear).
- **Partial fixes: as in slice 1, better caught.** 26 of 28 not green-lit, 19 caught (was 7 of 12).
- **False alarms on correct fixes fell** (9% of 85, was 16% of 19), and they have the same kinds
  of cause as slice 1: a regression the issue asked for (the PR's own test patch rewrites that
  test or its fixture file: babelfish-50, ocdskit-51), a project's warning filter turning a
  documented warning into a raise (photutils-1943, NOTES #39), inputs outside a function's domain
  or a property's own condition ignored (babelfish-50, pre-commit-hooks-98, dissect.cstruct-88,
  clldutils-27; NOTES #40), and a method called again on an object whose constructor had
  already called it and cleaned up after it (cppheaderparser-44, on gold and agent_ok).
- **Real bugs in merged fixes, again.** proxy.py-137's gold parser raises `IndexError` on a bare
  `b'\r\n'`; jsonargparse-263's `yaml_load('null:')` raises `TypeError` (the agent's fix fails
  on `'on:'` the same way); unyt-437's `to_astropy` turns 5 km/m into a plain 5, silently
  1000× off (the agent's fix too). asdf-1575's agent fix broke a test of the project's own
  `info` output.
- **Correct fixes still stall at L1/L2** for slice 1's reasons. Guard: 32 of 54 gold runs not
  guarded, with a median of 4.5 mutants (3 to 9; NOTES #24). L3: the behaviour diff's gate opened
  in 4 runs (all on 3.9/3.10), but none reached L3: 3 stopped at Guard, 1 had a finding; the
  comparison not finishing is the first blocker in 7 of 12 gold runs at L2 (module-level code
  3, a special method 1, an unexplained change 1).
- **Break My Fix ran no input in 23% of runs** (was 11%): the model-written harness didn't run,
  or no strategy could build the inputs (NOTES #33). It is the largest single loss of evidence.
- **Faster than slice 1**: median 3.7 min (was 6.5), 90th percentile 16.5 min (was 38), no
  timeouts. Guard is still most of a run (mean 4.5 of 7.9 min).
- **Crash-only kills stay rare**: 3 of 331 kills (NOTES #26); not counting them would change no
  Guard verdict.

### Where the funnel lost tasks (slice 2)

Of 21,336 rows: 9,730 with no image, 6,908 outside Python 3.9–3.13, 127 invalid, 16 with no
source change, 15 with compiled sources, 6 with no pytest command, 1 unreadable patch, 23 with
no usable agent patch, 672 over the 2-per-repo cap, and 3,688 past the 150-task limit. Of the 111
prepared: 45 base suites can't run in the image (NOTES #36, #37), 5 take over 180 s, 4 hidden
tests fail on gold, 1 hidden test passes on base. Agent patches set aside in prepare: 3 that don't apply, 1 the dataset calls
wrong but our hidden-test run passes, 1 with an unsettled result. 21 of the 56 ready tasks needed
the harness to commit the image's setup changes first.

## Results: M11 on slice 2 (November 2026, dev split again)

M11 changed Tracefix where slice 2 showed it weak (plan: `docs/plans/M11.md`) and ran the same
dev fixes again. **Arm A** is slice 2 above, M10's code. **Arm B** is M11's code
(`benchmarks/results/slice2-m11/`). The numbers here come from that folder's `report.md` and
`compare-slice2.md`, which `report --slice slice2 --results m11` and
`compare --slice slice2 --b m11` rebuild from the committed files (a test checks both, byte for
byte).

**Anchored.** Arm B replays arm A's recorded model answer wherever its request is the same, byte
for byte, and calls the model only for a new request (`run --anchored`). So a difference between
the arms comes from M11's code and from the answers it had to ask for anew (every mutator call:
its prompt changed), not from the model answering one question twice. The price: the arms are
not independent samples, and a replayed call takes no time, which flatters B's times.

145 runs: 144 receipts and 1 timeout (ocbpy-144 gold hit the 2-hour limit; it took 87 min in arm
A). That leaves 144 pairs. 11 are set aside in each arm, so 133 count: 85 correct fixes (47 gold,
38 agent_ok) and 48 wrong ones (28 partial, 20 agent_wrong). The developer labelled arm B's
findings afresh (32: 20 false alarm, 11 real bug, 1 unclear).

**M11's targets**, fixed before the run (MILESTONES M11). Two were missed and stay recorded as
missed (developer, 13 Nov 2026):

| Target | Arm A | Arm B | |
|---|---|---|---|
| Median valid model mutants ≥ 7, on runs Guard did not stop early | 5 (115 runs) | 7 (39 runs) | met, on the line |
| Guard verdicts one mutant from flipping: at most half of A's | 49/115 (43%) | 87/118 (74%) | **missed** |
| Break My Fix ran no input: down a third (≤ 22) | 33/144 (23%) | 31/144 (22%) | **missed** |
| Correct fixes with a false alarm: no more than A | 8/85 (9%) | 7/85 (8%) | met |
| Wrong agent fixes not green-lit: no fewer than A | 16/20 (80%) | 16/20 (80%) | met |
| Time per run: median ≤ 5 min, 90th percentile ≤ 20 min | 3.6 / 14.1 min on the 144 paired runs (3.7 / 16.5 on all 145, with A's 87-min ocbpy-144 gold run, which has no pair) | 3.2 / 14.7 min on the 144 paired runs plus its timeout, counted at its 2 hours | met |

The other headline rates barely moved:

| | Arm A | Arm B |
|---|---|---|
| Wrong agent fixes caught / at L2 (a false pass) | 6/20 / 4/20 | 6/20 / 4/20 |
| Partial fixes not green-lit / caught | 26/28 / 19/28 | 26/28 / 19/28 |
| Leftover bug found (partial and wrong agent fixes) | 3/48 | 4/48 |
| Gold at ≥ L2 / ≥ L3 | 12/47 (26%) / 0 | 11/47 (23%) / 0 |
| agent_ok at ≥ L2 | 10/38 (26%) | 8/38 (21%) |
| Cost per run, estimate at list prices | mean $0.23 | mean $0.26 |

What this says in plain words:

- **No wrong fix changed level.** All 48 (20 agent, 28 partial) got the same level in both arms.
  B found one more leftover (asgiref-211's partial fix); one run is not evidence (sign test
  p = 0.5).
- **One false alarm is gone, by a rule that changes what counts.** photutils-1943's gold fix went
  from COUNTEREXAMPLE to L1: a warning that only the project's own filter turns into an error is no
  longer a raise (NOTES #39). The other seven are still there.
- **Guard writes more mutants, and its verdicts are no firmer.** On runs played to the end the
  median rose from 5 to 7. The share one mutant from the other side rose too, for two reasons that
  are arithmetic, not behaviour:
  - Guard now stops once "not guarded" is certain (79 of the 118 judged runs). The measure reads
    a stopped run as if every mutant left had been killed, so a run stopped at the first certain
    moment reads as close: 64 of the 79.
  - A guarded verdict with one survivor is one mutant from 80% until there are 10 valid mutants,
    and B's most is 9.

  On the 37 runs both arms judged and B played to the end, A has 24 close and B 23: no change.
  The verdict itself differed between the arms in 12 of the 115 runs both judged (8 guarded in A
  only, 4 in B only), each time with a new set of mutants. Those crossings are 8 of the 10 level
  moves on correct fixes: all 6 down (L2 to L1) and 2 of the 4 up. The other two: photutils-1943
  below, and dlx-375's gold fix, reproduced in B and not in A. So gold at L2 went from 12 to 11
  (4 down, 3 up). NOTES #24 stays open: 10 or more mutants, or a margin instead of a hard line.
- **Break My Fix still tries no input in a fifth of the runs, and now says why.** 30 runs had
  none in both arms; 3 gained inputs and 1 lost them. Of B's 31: in 19 no object of the method's
  class could be built, in 5 a parameter had no type to build from, in 3 (one task) the object
  could not be copied before the call, and in 4 nothing was generated or no input fitted a
  property's condition. Telling the model what went wrong bought little here; the fix is
  building the object (ROADMAP).
- **The doubt flags hit only false alarms here, and were written from these cases.** 8 counted
  findings on 4 tasks carry a flag (babelfish-50, dissect.cstruct-88, cppheaderparser-44,
  nibabies-395); the developer labelled all 8 false alarms, and none of the 9 real-bug findings
  is flagged. A rule that stops counting `finished_object` and `refused` would take false alarms
  from 7 to 4 of 85 and lose no real bug or leftover found. `os_limit` would remove none: its two
  findings are on nibabies-395's wrong agent fix and partial fix, and without it that wrong agent
  fix would probably pass.
  The flags stay report only, and that rule is fixed now for the held_out split (developer,
  13 Nov 2026).
- **The blind test separates, at a price.** It is a second reproduction test written without
  seeing the fix. At L2 it still fails on head for 4 of 6 wrong fixes (briefcase-645 and
  nipype-3658's agent fixes, two partial fixes) and for 3 of 19 correct ones (gold, each a blind
  test that guessed an internal the fix changed). autodocsumm-101 and dphon-366's wrong agent
  fixes would still pass. Capping at L1 would give wrong agent fixes not green-lit 18 of 20 and
  gold at L2 8 of 47. The developer decided it will cap, as a step of its own after M11 (13 Nov
  2026); M11's receipts only report it.
- **The new tricky strings found nothing real yet.** 2 findings use one (babelfish-50, a dotted
  capital I), both labelled false alarms; no leftover was found through one.
- **Cost and time.** The blind test adds a median of 17 s a run, and a run's estimate at list
  prices is about 3 cents higher (the blind test and the longer mutant lists). Live spend was
  $7.58 by the receipts, plus the timed-out run's unknown cost (the spend guard counted
  $10.58 with its $3 reserve): most calls were replays. M11 spent about $8 of its $30 in all,
  with about $0.40 of fixture recordings.

Also measured in M11, with no model and no Docker: whether the code a fix replaced is still
elsewhere, and whether an untouched function shares a changed one's name. Neither separates
wrong fixes from correct ones (wrong 8/61 and 15/61, correct 15/103 and 23/103). A third signal,
a test reading a constant the fix assigns, met the bar fixed in advance (it fired in 6 of 162
fixes; the rule said build), but read by hand none of the 6 was a test taking its expected value
from the code, so it was not built either, a departure from that rule (DECISIONS 2026-11-04 and
2026-11-05). Nothing went into the receipt (`benchmarks/results/sibling-sites/summary.md`, NOTES
"Sibling sites measured").

## Caveats

- **M11's arm B is the same dev tasks, after tuning on them.** The warnings rule, the doubt flags
  and the no-input reasons were written from slice 2's own cases, so arm B shows that they hit
  those cases and nothing else, not how they do on new ones. The arms share every replayed model
  answer. held_out is still unrun.
- **Small numbers.** Slice 1: 19 gold and 12 partial runs, so one run moves a rate by 5–8
  points. Slice 2: 47 gold, 38 agent_ok, 28 partial and 20 wrong agent fixes, so one run still
  moves a wrong-agent rate by 5 points. Treat the rates as measurements in progress.
- **Dev split only, and not yet what the release gates ask for.** Every slice 2 number is from
  the dev split: Tracefix wasn't tuned on it yet, but M11 will be, so the gates (ROADMAP) are
  read on held_out after M11. Slice 2 ran no repeats, so its stability is unmeasured.
- **One model run per fix.** The headline reads each fix's first run. In slice 1 a second run of
  18 fixes changed the COUNTEREXAMPLE verdict in 2 and the level in 6 (see Stability), so each
  rate carries that noise on top of the small numbers.
- **One agent.** Every agent patch comes from one OpenHands setup (Qwen3-Coder) in Nebius's
  published runs. Other agents make other mistakes; 21 of its 24 wrong patches change nothing the
  hidden tests see, which a stronger agent may do less often.
- **Contamination.** Slice 1's 22 tasks were merged between Jan 2025 and May 2026, likely before
  the models' training data ends; slice 2's tasks (mostly Python 3.9 projects from SWE-rebench)
  are older still. A model may have seen the upstream fix or its tests. That would more likely
  help the Reproducer and Break My Fix than hurt them.
- **Synthetic partial fixes.** A gold patch minus one hunk is an incomplete fix a human wrote most
  of, not an agent's wrong fix; slice 2 measures both, side by side.
- **The projects that qualify are a skewed sample**: a pytest suite under 3 minutes that runs in
  the published image. Slice 1 is all Python 3.11+, slice 2 all but one task 3.9/3.10, so neither
  says much about the other's Pythons. Large projects are not represented yet.
- **Labels are one person's judgement**, written down with reasons, on the findings shown in
  report.md.
