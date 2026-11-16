## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): Break My Fix found \`f\_t1(x=-1)\` still returns -1. Start there.

**Why this level:** Break My Fix finding 1: an input that breaks pkg.calc.f\_t1; integrity flag: weakened\_assert at tests/test\_calc.py:7; regression: tests/test\_other.py::test\_total passed before the fix and fails after it

**Issue:** f(-1) returns -1 instead of 0 · **Repo:** calc · **Base** `main` (`aaaaaaa`) → **head** `fix` (`bbbbbbb`)\
**Isolation:** basic (bubblewrap needs Linux)

> [!WARNING]
> - Generated tests ran with basic isolation only (no bubblewrap sandbox): tampering inside the watched folders is detected, but code could still read or write elsewhere on this machine, and a process that escaped could influence a later run. For untrusted changes run Tracefix in GitHub Actions or on Linux with bubblewrap.

### Counterexamples
1. `f_t1(x=-1)` → `returns -1` (before the fix: `returns -1`); breaks **never negative**: “must never be negative” (issue); test: `findings/finding_1.py`
2. Regression: `tests/test_other.py::test_total` passed before the fix and fails after it (passed on base every time, failed on head 4 times)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | none |
| `reproduce` | `reproduced` | attempts 0 |
| `guard` | `guarded` | mutants 2, killed 1, survived 1 |
| `regressions` | `found` | compared 5, regressions 1, unconfirmed 0 |
| `behaviour_diff` | `compared` | inputs compared 0, changes 1, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 150, properties counted 1, findings 1 |
| `integrity` | `flagged` | flags 1 |

**Rule mutants by kind (report only):** compare: 1 of 1 killed; no place for body, logic, negate\_if, constant, arithmetic, membership, loop, drop\_call, reraise

### Behaviour changes
- `t1` (`value`, 1 input): `returns -1` → `returns 0`; explained by: the issue calls f(-1); the Judge (advisory) calls it intended: the issue's own case

### Changes no test noticed
- `pkg/calc.py:3`: `x < 0` → `x <= 0` made no test fail; behaves differently from the fix on inputs no test checks (`m-0e1cf47729be`)

### Integrity flags
- **f1** `weakened_assert` in `tests/test_calc.py:7` (`test_calc`): assert loosened (fails on head with the old assert); the Judge's note (advisory): The old assert encoded the bug; check \`test\_calc\` still covers negative inputs.

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; import\_check: did not run; fix\_line\_coverage: did not run; 9 things the behaviour diff can't observe (run log)
- **Model use:** 1 call, 12,000 input and 3,000 output tokens, cost $0.1080 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 3.2 s: the base suite runs
  - `python -m pytest -q tests`
- `reproduce`: `reproduced`, 1.0 s: reproduced
- `guard`: `guarded`, 1.0 s: guarded
- `regressions`: `found`, 1.0 s: found
- `behaviour_diff`: `compared`, 1.0 s: compared
- `break_my_fix`: `found`, 1.0 s: nothing found
- `integrity`: `flagged`, 1.0 s: flagged
#### Break My Fix targets
- `pkg.calc.f_t1` (`pkg/calc.py`): 150 inputs
#### Not checked
- concurrency
- database state
- network and external services
- authentication and authorisation
- performance
- configuration
- not observed by the behaviour diff: files written outside the copy, and anything sent off the machine
- not observed by the behaviour diff: in the copy: folders made or removed, file modes and other metadata, and files under \_\_pycache\_\_, .pytest\_cache, .hypothesis or .git folders
- not observed by the behaviour diff: state of dependencies and C extensions (an lru\_cache's contents, a C object's fields)
- not observed by the behaviour diff: process-wide state the function's code doesn't reach by name (os.environ, the working directory, sys.path, logging setup beyond the loggers it reaches, the decimal context, warning filters, the random module's state)
- not observed by the behaviour diff: module data reached only through importlib, sys.modules or getattr with a computed name
- not observed by the behaviour diff: code put into module data during a call (it is walked as it was before the first call)
- not observed by the behaviour diff: threads and processes a call starts, and what they do after it returns
- not observed by the behaviour diff: objects shared between the result, the arguments and module data
- not observed by the behaviour diff: output past 1 MB, and output a C library flushes after the call
- import\_check: did not run
- fix\_line\_coverage: did not run
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.0-test, receipt schema 1, created 2026-10-13T12:00:00+00:00, issue sha256 `64d2def5d21eeedd2c117ff95d06f65c221ae9d7b0fba6f67d201a9890c49e1b`

</details>
