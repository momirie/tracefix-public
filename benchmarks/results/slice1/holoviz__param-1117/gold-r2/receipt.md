## Fix Receipt: L2 (L1, and the tests notice the fix being undone)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): At L2, a test reproduced the repeated upstream evaluation (failing before the fix, passing after) and fails again when the fix is reverted or broken, with no regressions or breaking inputs found. The behaviour comparison was inconclusive for the changed rx methods (\_resolve, \_lazy\_resolve, \_clone, the async path and the new \_is\_async property), so a reviewer should check those directly, especiall…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; the tests guard the fix: they fail when it is reverted or broken; not L3: rx.\_\_init\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet); not L3: rx.\_resolve\_async: not compared (async methods are not called yet); not L3: rx.\_is\_async: before the fix it was not a property defined in class rx; not L3: rx.\_lazy\_resolve: the comparison did not finish; and 5 more in receipt.json

**Issue:** Shared rx inputs are not reused · **Repo:** testbed · **Base** `tf-base` (`1ab8c90`) → **head** `tf-gold` (`cac8784`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 1\.0, mutants 8, killed 8, survived 0 |
| `regressions` | `none_found` | compared 1179, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 29 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 4, inputs tried 10, properties counted 6, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `param/reactive.py:1655`: `             if self._shared._current_task: ` → `             if not (self._shared._current_task): ` made no test fail; not compared with the fix (`m-fb59e7b6c219`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack rx.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack rx.\_resolve\_async: async methods are not called yet; the behaviour diff could not compare rx.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; the behaviour diff could not compare rx.\_resolve\_async: async methods are not called yet; and 1 more in receipt.json
- **Model use:** 6 calls, 74,826 input and 5,333 output tokens, cost $0.3711 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 8.29 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.75 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 16.5 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `guarded`, 434.25 s: the reproduction test fails with the fix reverted, and the tests killed 8 of 8 mutants
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 8.81 s: none of the 1179 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 2.43 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `inconclusive`, 11.57 s: nothing was compared: rx.\_\_init\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `none_found`, 45.93 s: no counterexample found in 10 inputs against 6 properties
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
- `integrity`: `clean`, 0.03 s: nothing suspicious in the fix's test or source changes
#### Fix lines run (report only)
- repro: 15 of 29 fix lines run
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
- Break My Fix could not attack rx.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack rx.\_resolve\_async: async methods are not called yet
- the behaviour diff could not compare rx.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare rx.\_resolve\_async: async methods are not called yet
#### Notes
- reproduce: only the first 8 of 55 functions were shown
- reproduce: pyproject truncated to 3000 characters for the prompt
- guard: only the first 10 of 21 rule mutants were run
- behaviour\_diff: the behaviour diff on the fixed code reported it finished but ended failed: not trusted
- behaviour\_diff: the behaviour diff on surviving mutant 18 reported it finished but ended failed: not trusted
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-20T09:08:45+00:00, issue sha256 `4b1604f157870a58aefb6cfe2322250fe5d3a7140c1ca343499da2d86bf467b8`

</details>
