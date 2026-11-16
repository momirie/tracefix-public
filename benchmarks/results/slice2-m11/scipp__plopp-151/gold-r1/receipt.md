## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The bug was reproduced: a test that fails before the fix passes after it, no regressions were found, and the fixed lines were covered, but behaviour-diff and break-my-fix runs were inconclusive and the mutation check did not reach the threshold for a higher level. Next, check that the tests exercise the datetime bin-edge error-bar path in both the matplotlib and plotly backends, as the issue requ…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 1 of 4 mutants; 80% is needed

**Issue:** Cannot make 1d plot for data with datetime coord and variances · **Repo:** testbed · **Base** `tf-base` (`df3a5f2`) → **head** `tf-gold` (`a11ae82`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.25, mutants 4, killed 1, survived 3 |
| `regressions` | `none_found` | compared 245, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 88 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 6, inputs tried 0, properties counted 12, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_differently` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 2 of 2 killed; compare: 1 of 2 killed; logic: 1 of 2 killed; negate\_if: 1 of 1 killed; constant: 0 of 1 killed; membership: 1 of 1 killed; drop\_call: 0 of 1 killed; no place for arithmetic, loop, reraise

### Changes no test noticed (3 of 7; the rest in receipt.json)
- `src/plopp/backends/matplotlib/line.py:182`: `             y = sc.concat([y[0:1], y], dim=self._dim) ` → `             y = sc.concat([y[-1:], y], dim=self._dim) ` made no test fail; not compared with the fix (`m-f7bf27a83c90`)
- `src/plopp/backends/matplotlib/line.py:184`: `                 mask['y'] = np.concatenate([mask['y'][0:1], ... ` → `                 mask['y'] = np.concatenate([mask['y'][-1:], ... ` made no test fail; not compared with the fix (`m-07333422ca86`)
- `src/plopp/backends/matplotlib/line.py:178`: `                 'y': np.where(one_mask, y.values, np.nan), ` → `                 'y': np.where(one_mask, np.nan, y.values), ` made no test fail; not compared with the fix (`m-ed32d9f70a95`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 79,420 input and 8,765 output tokens, cost $0.4211 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 22.97 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.58 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 16.77 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/back...`
- `guard`: `not_guarded`, 377.58 s: the tests killed 1 of 4 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/back...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 23.16 s: none of the 245 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.53 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/back...`
- `behaviour_diff`: `inconclusive`, 4.71 s: nothing was compared: Line.update: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 33.62 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_differently`, 21.03 s: attempt 1: fails after the fix too, but differently
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/back...`
#### Break My Fix targets
- `plopp.backends.matplotlib.line.Line.update` (`src/plopp/backends/matplotlib/line.py`): 0 inputs (no object of Line was built: none was given, and no type hints make one)
- `plopp.backends.plotly.line.Line.update` (`src/plopp/backends/plotly/line.py`): 0 inputs (no object of Line was built: none was given, and no type hints make one)
- `plopp.backends.matplotlib.line.Line._make_line` (`src/plopp/backends/matplotlib/line.py`): not attacked (no property to check it against)
- `plopp.backends.matplotlib.line.Line._make_data` (`src/plopp/backends/matplotlib/line.py`): 0 inputs (no object of Line was built: none was given, and no type hints make one)
- `plopp.backends.plotly.line.Line._make_line` (`src/plopp/backends/plotly/line.py`): not attacked (no property to check it against)
- `plopp.backends.plotly.line.Line._make_data` (`src/plopp/backends/plotly/line.py`): 0 inputs (no object of Line was built: none was given, and no type hints make one)
#### More changes no test noticed
- `src/plopp/backends/matplotlib/line.py:124`: `             self._mask = self._ax.step(data['mask']['x'], da... ` → `             self._mask = self._ax.step(data['mask']['x'], da... ` made no test fail; not compared with the fix (`m-731c84b867ba`)
- `src/plopp/backends/matplotlib/line.py:130`: `             self._mask.set_visible(data['mask']['visible']) ` → `             pass ` made no test fail; not compared with the fix (`m-827bef2b42fb`)
- `src/plopp/backends/plotly/line.py:178`: `         hist = len(x) != len(y) ` → `         hist = len(x) == len(y) ` made no test fail; not compared with the fix (`m-26207bde799b`)
- `src/plopp/backends/matplotlib/line.py:214`: `         if (self._error is not None) and (new_values['stddev... ` → `         if (self._error is not None) or (new_values['stddevs... ` made no test fail; not compared with the fix (`m-c1a39c15bbf0`)
#### Fix lines run (report only)
- repro: 29 of 88 fix lines run
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
- reproduce: only the first 8 of 22 functions were shown
- guard: 6 of the 10 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 55 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: only the first 8 of 24 functions were shown
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T19:46:44+00:00, issue sha256 `30ebb317fbea9c21e2d8795faba583da1f6a9baba1dfd044727e8e15e540c900`

</details>
