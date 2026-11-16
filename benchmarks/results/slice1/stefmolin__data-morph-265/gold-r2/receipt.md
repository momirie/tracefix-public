## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test that failed before this change now passes after it, no regressions were found, and the fixed lines were covered, but the guard stage reported the tests do not adequately guard the change (they did not kill enough mutants to reach L2). The most important next step is strengthening the tests so they would catch a broken version of the fix, for example by asserting both orientations of the fi…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 6 mutants; 80% is needed

**Issue:** Add figure eight target shape · **Repo:** testbed · **Base** `tf-base` (`9391f31`) → **head** `tf-gold` (`d37b325`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.333, mutants 6, killed 2, survived 4 |
| `regressions` | `none_found` | compared 345, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 20 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 11; the rest in receipt.json)
- `src/data_morph/shapes/points/figure_eight.py:51`: `             *np.stack([x, y] if x_range >= y_range else [y, ... ` → `             *np.stack([x, y] if x_range > y_range else [y, x... ` made no test fail; not compared with the fix (`m-e5e61d7ab949`)
- `src/data_morph/shapes/points/figure_eight.py:52`: `             + np.array([x_shift, y_shift]) ` → `             + np.array([y_shift, x_shift]) ` made no test fail; not compared with the fix (`m-15981c2f0a21`)
- `src/data_morph/shapes/points/figure_eight.py:42`: `         t = np.linspace(-3.1, 3.1, num=80) ` → `         t = np.linspace(-3.1, 3.1, num=79) ` made no test fail; not compared with the fix (`m-0afbda5079de`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)); break\_my\_fix: skipped (the fix changes no function Break My Fix can call (FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)); Break My Fix could not attack FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; the behaviour diff could not compare FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; and 1 more in receipt.json
- **Model use:** 3 calls, 9,399 input and 1,749 output tokens, cost $0.0416 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 16.8 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 8.01 s: 3 changed module(s) imported from the copies (5 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 66.58 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 298.79 s: the tests killed 2 of 6 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 16.83 s: none of the 345 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 8.59 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `skipped`, 0.1 s: the fix changes no function the behaviour diff can call (FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
- `break_my_fix`: `skipped`, 0.01 s: the fix changes no function Break My Fix can call (FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### More changes no test noticed
- `src/data_morph/shapes/points/figure_eight.py:45`: `         half_width = focal_distance * np.sqrt(2) ` → `         half_width = focal_distance * np.sqrt(3) ` made no test fail; not compared with the fix (`m-2b17eae8266f`)
- `src/data_morph/shapes/points/figure_eight.py:42`: `         t = np.linspace(-3.1, 3.1, num=80) ` → `         t = np.linspace(-3.1, 3.1, num=79) ` made no test fail; not compared with the fix (`m-0afbda5079de`)
- `src/data_morph/shapes/points/figure_eight.py:42`: `         t = np.linspace(-3.1, 3.1, num=80) ` → `         t = np.linspace(-3.1, 3.1, num=81) ` made no test fail; not compared with the fix (`m-f02108893164`)
- `src/data_morph/shapes/points/figure_eight.py:44`: `         focal_distance = max(x_range, y_range) * 0.3 ` → `         focal_distance = max(x_range, y_range) / 0.3 ` made no test fail; not compared with the fix (`m-a79e3ea09127`)
- `src/data_morph/shapes/points/figure_eight.py:45`: `         half_width = focal_distance * np.sqrt(2) ` → `         half_width = focal_distance / np.sqrt(2) ` made no test fail; not compared with the fix (`m-e6e3ccc926bb`)
- `src/data_morph/shapes/points/figure_eight.py:45`: `         half_width = focal_distance * np.sqrt(2) ` → `         half_width = focal_distance * np.sqrt(1) ` made no test fail; not compared with the fix (`m-c6013977aa87`)
- `src/data_morph/shapes/points/figure_eight.py:45`: `         half_width = focal_distance * np.sqrt(2) ` → `         half_width = focal_distance * np.sqrt(3) ` made no test fail; not compared with the fix (`m-2b17eae8266f`)
- `src/data_morph/shapes/points/figure_eight.py:47`: `         x = (half_width * np.cos(t)) / (1 + np.square(np.sin... ` → `         x = (half_width * np.cos(t)) * (1 + np.square(np.sin... ` made no test fail; not compared with the fix (`m-cc2c877df9e4`)
#### Fix lines run (report only)
- repro: 20 of 20 fix lines run
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet))
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call (FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet))
- Break My Fix could not attack FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
#### Notes
- reproduce: only the first 8 of 22 functions were shown
- reproduce: pyproject truncated to 3000 characters for the prompt
- guard: only the first 10 of 18 rule mutants were run
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-20T09:24:57+00:00, issue sha256 `1aeefc46e723d1ac2f518647b871390362036d19909f7d319e4bc57d2508bf8c`

</details>
