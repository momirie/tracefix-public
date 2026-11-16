## Fix Receipt: L0 (no evidence for this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier could not reproduce the bug: an attempt failed the same way before and after the fix but was never reviewed. Behaviour-diff and break-my-fix were inconclusive, so this receipt shows only that the fix imports, its lines were covered, and no regressions were found.

**Why this level:** not L1: attempt 3 failed the same way before and after the fix, but the model never got to review that result, so it does not count as fix\_does\_not\_fix

**Issue:** Extra user arguments in RulesEngine.apply\_rules are not given to actions and condition functions · **Repo:** testbed · **Base** `tf-base` (`4554f44`) → **head** `tf-v0` (`6215d53`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `not_reproduced` | attempts 3 |
| `guard` | `skipped` | mutants 0, killed 0, survived 0 |
| `regressions` | `none_found` | compared 93, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 2 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 1, inputs tried 0, properties counted 2, findings 0 |
| `integrity` | `clean` | flags 0 |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; guard: skipped (there is no reproduction test to judge the tests with (not\_reproduced)); 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 44,563 input and 11,320 output tokens, cost $0.3143 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.99 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.01 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `not_reproduced`, 79.97 s: attempt 3 failed the same way before and after the fix, but the model never got to review that result, so it does not count as fix\_does\_not\_fix
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `skipped`, 0.0 s: there is no reproduction test to judge the tests with (not\_reproduced)
- `regressions`: `none_found`, 3.27 s: none of the 93 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 0.01 s: report only: which fix lines the tests run
- `behaviour_diff`: `inconclusive`, 4.1 s: nothing was compared: Rule.apply: the comparison did not finish
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `inconclusive`, 66.31 s: the attack ran no input
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
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
- guard: skipped (there is no reproduction test to judge the tests with (not\_reproduced))
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T13:39:52+00:00, issue sha256 `83aa7acd66e69c153ab27d19c9e78d0c435e67b24386b048063ac9f508498b9d`

</details>
