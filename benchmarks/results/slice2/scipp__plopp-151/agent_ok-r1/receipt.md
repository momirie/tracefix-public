## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproducing the datetime bin-edge error-bar failure fails before the fix and passes after it, with no regressions found and the fix lines covered, but the guard stage reported the bug as not guarded and the behaviour-diff and break-my-fix stages were inconclusive. Next, check that the fix and a guarding test cover both the matplotlib and plotly backends, as the issue requires, and that the…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 3 of 7 mutants; 80% is needed

**Issue:** Cannot make 1d plot for data with datetime coord and variances · **Repo:** testbed · **Base** `tf-base` (`df3a5f2`) → **head** `tf-agent_ok` (`3ca2da0`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 5 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.429, mutants 7, killed 3, survived 4 |
| `regressions` | `none_found` | compared 245, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 98 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 2, inputs tried 0, properties counted 8, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 13; the rest in receipt.json)
- `src/plopp/backends/matplotlib/line.py:181`: `                 data["variances"]["x"] = sc.midpoints(coord)... ` → `                 data["variances"]["x"] = coord.values[:-1] ` made no test fail; not compared with the fix (`m-4ededce56d37`)
- `src/plopp/backends/plotly/line.py:192`: `             if hist: ` → `             if not hist: ` made no test fail; not compared with the fix (`m-9dce87d34f53`)
- `src/plopp/backends/plotly/line.py:195`: `                 data["variances"]["x"] = sc.midpoints(coord)... ` → `                 data["variances"]["x"] = coord.values[1:] ` made no test fail; not compared with the fix (`m-e14b796b1859`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 5 calls, 35,684 input and 4,232 output tokens, cost $0.1897 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 24.18 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 6.46 s: 4 changed module(s) imported from the copies (6 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 23.47 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/back...`
- `guard`: `not_guarded`, 829.91 s: the tests killed 3 of 7 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/back...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no simple_tes...`
  - 3 more command(s) in receipt.json
- `regressions`: `none_found`, 35.04 s: none of the 245 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 11.9 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/back...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
- `behaviour_diff`: `inconclusive`, 4.73 s: nothing was compared: final\_verification.py: module-level code that computes a value changed (line 11, 14, 15, 16, 17); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 50.54 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.05 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `plopp.backends.matplotlib.line.Line._preprocess_hist` (`src/plopp/backends/matplotlib/line.py`): 0 inputs
- `plopp.backends.plotly.line.Line._preprocess_hist` (`src/plopp/backends/plotly/line.py`): 0 inputs
#### More changes no test noticed
- `src/plopp/backends/plotly/line.py:197`: `                 data["variances"]["x"] = x ` → `                 data["variances"]["x"] = x[1:] ` made no test fail; not compared with the fix (`m-9c30546ac7c5`)
- `src/plopp/backends/plotly/line.py:183`: `         x = data["values"]["x"]\n        y = data["values"]["... ` → `         return {} ` made no test fail; not compared with the fix (`m-50a88c435d4c`)
- `final_verification.py:16`: `                                                 np.datetime6... ` → `                                                 np.datetime6... ` made no test fail; not compared with the fix (`m-049f7110706b`)
- `final_verification.py:16`: `                                                 np.datetime6... ` → `                                                 np.datetime6... ` made no test fail; not compared with the fix (`m-919703f5517a`)
- `final_verification.py:17`: `v = np.random.rand(time.sizes['time']-1)` → `v = np.random.rand(time.sizes['time']+1)` made no test fail; not compared with the fix (`m-4a030c50a6f8`)
- `final_verification.py:17`: `v = np.random.rand(time.sizes['time']-1)` → `v = np.random.rand(time.sizes['time']-0)` made no test fail; not compared with the fix (`m-55729db8ac4f`)
- `final_verification.py:17`: `v = np.random.rand(time.sizes['time']-1)` → `v = np.random.rand(time.sizes['time']-2)` made no test fail; not compared with the fix (`m-04793d926df0`)
- `final_verification.py:18`: `da = sc.DataArray(data=sc.array(dims=['time'], values=10 * v...` → `da = sc.DataArray(data=sc.array(dims=['time'], values=11 * v...` made no test fail; not compared with the fix (`m-31813d150e0e`)
- `final_verification.py:18`: `da = sc.DataArray(data=sc.array(dims=['time'], values=10 * v...` → `da = sc.DataArray(data=sc.array(dims=['time'], values=9 * v,...` made no test fail; not compared with the fix (`m-d463a624a1ad`)
- `final_verification.py:18`: `da = sc.DataArray(data=sc.array(dims=['time'], values=10 * v...` → `da = sc.DataArray(data=sc.array(dims=['time'], values=10 / v...` made no test fail; not compared with the fix (`m-649e1b0e7d42`)
#### Fix lines run (report only)
- repro: 3 of 98 fix lines run
- pr\_test: 4 of 98 fix lines run
- reproduce\_issue.py is not UTF-8 Python that parses, so it is not mutated
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
- guard: exact\_issue\_test.py has no tests, so it is not counted as a PR test
- guard: reproduce\_issue.py is not UTF-8 Python that parses, so it is not mutated
- guard: only the first 10 of 48 rule mutants were run
- fix\_line\_coverage: reproduce\_issue.py is not UTF-8 Python that parses, so it is not mutated
- behaviour\_diff: reproduce\_issue.py is not UTF-8 Python that parses, so it is not mutated
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- break\_my\_fix: reproduce\_issue.py is not UTF-8 Python that parses, so it is not mutated
- integrity: reproduce\_issue.py is not UTF-8 Python that parses, so it is not mutated
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T16:30:54+00:00, issue sha256 `30ebb317fbea9c21e2d8795faba583da1f6a9baba1dfd044727e8e15e540c900`

</details>
