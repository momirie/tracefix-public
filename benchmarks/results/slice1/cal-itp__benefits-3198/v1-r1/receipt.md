## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the admin 'transit\_processor' lookup error and found the fix guards against it, but it also found a regression: TestTransitAgencyAdmin.test\_get\_readonly\_fields\[staff-expected0\] passed before the fix and fails after it. Look next at how the fix changed the staff user's readonly fields on TransitAgencyAdmin, and whether that test's expected list or the fix needs to change.

**Why this level:** regression: tests/pytest/core/admin/test\_transit.py::TestTransitAgencyAdmin.test\_get\_readonly\_fields\[staff-expected0\] passed before the fix and fails after it

**Issue:** AttributeError: Unable to lookup 'transit\_processor' on TransitAgency or TransitAgencyAdmin or TransitAgencyForm · **Repo:** testbed · **Base** `tf-base` (`f9203e4`) → **head** `tf-v1` (`024f756`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. Regression: `tests/pytest/core/admin/test_transit.py::TestTransitAgencyAdmin.test_get_readonly_fields[staff-expected0]` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert {'eligibility\_api\_id'} == {'eligibility...it\_processor'})

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 1\.0, mutants 3, killed 3, survived 0 |
| `regressions` | `found` | compared 510, regressions 1, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 1 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 1, inputs tried 0, properties counted 2, findings 0 |
| `integrity` | `clean` | flags 0 |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 5 calls, 16,111 input and 2,118 output tokens, cost $0.0902 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 73.05 s: base suite failed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 20.48 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 60.41 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `guarded`, 86.05 s: the reproduction test fails with the fix reverted, and the tests killed 3 of 3 mutants
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `regressions`: `found`, 308.97 s: 1 confirmed: tests/pytest/core/admin/test\_transit.py::TestTransitAgencyAdmin.test\_get\_readonly\_fields\[staff-expected0\]
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors tests/pytest/core/admin/test_transit.py`
- `fix_line_coverage`: `ok`, 11.46 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `inconclusive`, 23.75 s: nothing was compared: TransitAgencyAdmin.get\_readonly\_fields: the comparison did not finish
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `inconclusive`, 28.22 s: the attack ran no input
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Fix lines run (report only)
- repro: 1 of 1 fix lines run
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
#### Notes
- regressions: 3 untouched test(s) that passed before the fix did not run after it (skipped or not collected), so they were not compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T17:04:07+00:00, issue sha256 `cd4596ad24d51fee4c31ad60210b0b3216f0c5f818c90768e9bdbb4b3d9168c6`

</details>
