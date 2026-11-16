# Ground-truth fixtures

Eleven tiny Python repos with known answers. Every later milestone is graded against them.
Each case is stored as plain files and built into a real git repo by `scripts/make_fixtures.py`:
commit 1 = `base/` (buggy, tag `base`), commit 2 = `head/` (the "fix", tag `head`).

| Case | Bug | The "fix" | Expected receipt | Must find |
|---|---|---|---|---|
| `good_fix` | `total_pages` drops the last partial page (off-by-one) | Correct ceiling division + a test | at least **L2** | nothing (any finding is a false alarm) |
| `partial_fix` | `parse_port(None)` crashes; docs say unset/blank → 8080 | Handles `None` only | exactly **COUNTEREXAMPLE** | Break My Fix: `parse_port("")` → `ValueError` |
| `wrong_but_green` | `bucket_of` loses float precision above 2**53 | Floor division: fixes large values, floors negatives (-5 → -10) against the documented contract | at most **L2** | Behaviour diff: suspicious change for negative inputs |
| `test_weakened` | `slugify("Hello World!")` → `hello-world-` | Rewrite that breaks `"Rock & Roll"`, and deletes that assert | exactly **COUNTEREXAMPLE** | Integrity: removed assert in `tests/test_slug.py` |
| `special_cased` | Leap years use only `year % 4` | `if year == 2100 and month == 2: return 28` | exactly **COUNTEREXAMPLE** | Break My Fix: `days_in_month(2200, 2)` → 29 (integrity only reports the hard-coded `2100`, Decided in M5) |
| `unguarded_test` | `truncate` returns `max_len + 1` characters | Correct fix, but its new test also passes on the buggy code | exactly **L1** | Guard: PR's test passes with the fix reverted |
| `no_fix` | Case-sensitive email dedupe | Strips whitespace only; bug remains | exactly **COUNTEREXAMPLE** | Reproduce: `fix_does_not_fix` |
| `env_broken` | Week number off by one on Mondays | Real fix, but `acme_metrics` can't be installed | status **ENVIRONMENT_ERROR**, L0 | Environment error on base |
| `method_partial` | `Listener().port(None)` crashes; docs say unset/blank → `self.default_port` | Hard-codes `return 8080` for `None` only | exactly **COUNTEREXAMPLE** | Break My Fix on a method: `port("")` → `ValueError` (any object), and `Listener(default_port=9000).port(None)` → returns 8080 |
| `method_good` | `Version.bump("minor")` keeps the patch number | Resets patch + a test | at least **L2** | nothing (any finding is a false alarm) |
| `py39_partial` | A **Python 3.9** project: `ordinal(11)` → `"11st"` | Hard-codes 11, 12 and 13 to `"th"` | exactly **COUNTEREXAMPLE** | Break My Fix: `ordinal(111)` → `'111st'` |

Level order used by `at_least` / `at_most`: `COUNTEREXAMPLE < L0 < L1 < L2 < L3 < L4`.

## Layout of a case

```
<case>/
  base/           full project snapshot before the fix (pyproject.toml, src/, tests/)
  head/           full project snapshot after the fix
  ISSUE.md        the bug report Tracefix receives (symptom only)
  expected.json   the known answer
  oracle/         our own tests proving the bug and the fix quality
```

`ISSUE.md`, `expected.json` and `oracle/` are never copied into the built repo, so Tracefix cannot
see the answers.

## expected.json

- `receipt` — what a correct Tracefix receipt must say: `status`, `level`
  (`{"exactly"|"at_least"|"at_most": LEVEL}`), expected `stages` results, `must_find`, `must_not_find`.
  Graded stage by stage as stages are built (`stages.reproduce` since M3, by
  `tests/test_repro_recorded.py`; `stages.guard` and guard `must_find` since M4, by
  `tests/test_guard_recorded.py`; integrity `must_find` since M5, by
  `tests/test_integrity_recorded.py`, where every case without one must give no integrity flag;
  Break My Fix `must_find` and the `break_my_fix_finding` entry of `must_not_find` since M6, by
  `tests/test_attack_recorded.py`: the expected input must be the finding's input or one of its
  "also fails for" inputs, with the expected exception or `returns X, not Y`); the behaviour diff `must_find` and the
  `suspicious_behaviour_change` entry of `must_not_find` since M7, by
  `tests/test_behaviour_recorded.py` (the expected input among the Judge's shown changes, with
  its outcome before and after the fix and the label). Since M8 the whole receipt is graded
  end to end by `tests/test_pipeline_recorded.py`: `tracefix verify` runs on the built repo
  with recorded answers, and `receipt.json` alone must give the `status`, a `level` within the
  bound, the expected `stages` statuses, every `must_find` (findings, flags, Guard findings,
  behaviour changes, the environment error) and no `must_not_find`; any stage error or model
  problem (a missing recording included) fails the case.
- `checks` — executed now by `tests/test_fixtures.py`. Each runs pytest on one ref and asserts its
  exit code (`pass`=0, `fail`=1, `error`=2). Every `fail`/`error` check also has a `match` string
  that must appear in pytest's output, so a check can't pass by failing for the wrong reason
  (e.g. a typo raising `NameError`):
  - `"suite"` — the repo's own tests.
  - `"oracle/<file>.py"` — an oracle test copied into the tree.
  - `"head:<path>"` — a file from head copied onto the tree (e.g. head's test run against base code).

## Notes on individual cases

- `py39_partial` — the one case on an older project Python (`"python": "3.9"` in expected.json,
  registered in `OLD_PYTHON_CASES`, M10 part 2). Its package imports `Iterable` from
  `collections`, which Python 3.10 removed, so its tests can't even be collected on Tracefix's
  own Python (`test_old_python_case_cannot_run_on_tracefix_python`). The checks run with the 3.9
  venv from `scripts/old_pythons.py`, and the acceptance test passes it as `--python`: a stage
  that ignored `--python` would hit that import error, never the known answer. The stage-level
  recorded tests keep to the other ten cases; the acceptance test grades this one end to end.

- `good_fix` — `oracle/test_no_counterexample.py` checks the documented pagination contract
  exhaustively for n in 0..59 and per_page in 1..14; it passes on head, so any Break My Fix finding
  on good_fix is a false alarm. `page_slice([], 1, n) == []` although `total_pages(0, n) == 0` is
  deliberate and documented: it tests that proposed properties follow the docstring, not a guess.
- `unguarded_test` — head's docstring documents that the ellipsis itself is cut when `max_len` is
  shorter than it, so that behaviour is not a counterexample.
- `partial_fix` — has no expected guard result since M4 (the developer's decision, 2 Oct 2026). Its
  guard verdict sits on the 80% line and flips with the mutants the model picks: mutants such as
  `if not raw:` *complete* the fix (blank → 8080, as documented), so no test fails on them. One
  recording gave 4 of 5 killed (guarded), the next 2 of 4 (not_guarded). The case exists for Break
  My Fix; its receipt stays exactly COUNTEREXAMPLE.

## Commands

```
uv run python scripts/make_fixtures.py              # build all into build/fixtures/
uv run python scripts/make_fixtures.py partial_fix  # build one
uv run pytest tests/test_fixtures.py -q             # build + verify every check
```

Commit ids are pinned in `tests/test_fixtures.py` (`PINNED_SHAS`) so every OS builds identical
history. After a deliberate fixture change, rebuild and update the pins from the script's output.

## Decisions these answers depend on (recorded in docs/SPEC.md, marked "Decided in M1")

- `unguarded_test` (SPEC 2.4): if the PR's own added/changed tests all pass with the fix reverted,
  guard = `not_guarded`.
- `good_fix` (SPEC 2.4): a mutant is killed if the repro test, the PR's tests or the existing suite
  fails, so a repro built from the issue's single example doesn't sink the guard. (This also named
  `partial_fix` until M4; see its note above.)
- `partial_fix` (SPEC 2.6): a finding is pre-existing only if it also fails on base AND the failing run
  on head executes no line the fix added or changed. `parse_port("")` executes the new `None` check.
- `env_broken` (SPEC 2.8): `ENVIRONMENT_ERROR` receipts have level L0.
- `wrong_but_green`: `at_most L2` because Break My Fix may also find the negative-input breakage.
