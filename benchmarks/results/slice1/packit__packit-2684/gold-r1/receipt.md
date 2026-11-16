## Fix Receipt: L2 (L1, and the tests notice the fix being undone)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test failed before this change and passes after it, and the tests fail again when the Koji-cancelling code is reverted or broken; no regressions or breaking inputs were found, but no changed function was compared for behaviour, so the evidence stays at L2. Next, check by hand that the chosen Koji API calls (cancelBuild, cancelTask, cancelTaskFull) map correctly onto scratch versus production bu…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; the tests guard the fix: they fail when it is reverted or broken; not L3: no changed function was compared

**Issue:** Implement cancelling of the Koji jobs · **Repo:** testbed · **Base** `tf-base` (`291d745`) → **head** `tf-gold` (`da60a63`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `guarded` | kill rate 1\.0, mutants 4, killed 4, survived 0 |
| `regressions` | `none_found` | compared 1410, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 8 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 241, properties counted 3, findings 0 |
| `integrity` | `clean` | flags 0 |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (KojiHelper.cancel\_task: new with the fix: nothing to compare)); the behaviour diff could not compare KojiHelper.cancel\_task: new with the fix: nothing to compare; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 32,809 input and 2,779 output tokens, cost $0.1511 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 121.99 s: base suite failed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 17.75 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 174.89 s: attempt 2: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `guarded`, 126.3 s: the reproduction test fails with the fix reverted, and the tests killed 4 of 4 mutants
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `regressions`: `none_found`, 443.45 s: none of the 1410 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 7.53 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `skipped`, 0.4 s: the fix changes no function the behaviour diff can call (KojiHelper.cancel\_task: new with the fix: nothing to compare)
- `break_my_fix`: `none_found`, 38.19 s: no counterexample found in 241 inputs against 3 properties
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Fix lines run (report only)
- repro: 7 of 8 fix lines run
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (KojiHelper.cancel\_task: new with the fix: nothing to compare))
- the behaviour diff could not compare KojiHelper.cancel\_task: new with the fix: nothing to compare
#### Notes
- reproduce: pyproject truncated to 3000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T13:43:23+00:00, issue sha256 `019acd57c7213e05ef91d2ad27ab4968608604f7109479fed7ca9c60b1487757`

</details>
