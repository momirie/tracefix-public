## Fix Receipt: L2 (L1, and the tests notice the fix being undone)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproducing the issue (an int-typed argument with choices rejecting a valid value like '--mode 1') failed before the fix and passed after it, the tests fail when the fix is reverted or broken, and no regressions were found. The behaviour comparison for ActionTypeHint.prepare\_add\_argument did not finish, so a reviewer should check by hand how the changed choices handling behaves for other t…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; the tests guard the fix: they fail when it is reverted or broken; not L3: ActionTypeHint.prepare\_add\_argument: the comparison did not finish

**Issue:** The \`choices\` parameter of \`add\_argument()\` is not functioning correctly. · **Repo:** testbed · **Base** `tf-base` (`7e97a30`) → **head** `tf-gold` (`5ca475e`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 1\.0, mutants 4, killed 4, survived 0 |
| `regressions` | `none_found` | compared 1167, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 2 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 1, inputs tried 0, properties counted 3, findings 0 |
| `integrity` | `clean` | flags 0 |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 43,826 input and 5,294 output tokens, cost $0.2530 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 13.71 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 6.55 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_imports.py`
- `reproduce`: `reproduced`, 24.94 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no jsonargparse_tests/test_tracefix_repro.py`
- `guard`: `guarded`, 53.18 s: the reproduction test fails with the fix reverted, and the tests killed 4 of 4 mutants
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no jsonargparse_tests/test_tracefix_repro.py`
- `regressions`: `none_found`, 17.42 s: none of the 1167 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 5.15 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no jsonargparse_tests/test_tracefix_repro.py`
- `behaviour_diff`: `inconclusive`, 11.48 s: nothing was compared: ActionTypeHint.prepare\_add\_argument: the comparison did not finish
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no jsonargparse_tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s test_tracefix_diff.py`
- `break_my_fix`: `inconclusive`, 59.05 s: the attack ran no input
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_attack.py`
- `integrity`: `clean`, 0.05 s: nothing suspicious in the fix's test or source changes
#### Fix lines run (report only)
- repro: 2 of 2 fix lines run
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
- reproduce: style example jsonargparse\_tests/test\_actions.py truncated to 6000 characters for the prompt
- reproduce: pyproject truncated to 3000 characters for the prompt
- regressions: 1 untouched test(s) that passed before the fix did not run after it (skipped or not collected), so they were not compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T14:25:19+00:00, issue sha256 `9098454bd1474874fe59fba475a9b20ee586817480984c55b604af03b3d9615d`

</details>
