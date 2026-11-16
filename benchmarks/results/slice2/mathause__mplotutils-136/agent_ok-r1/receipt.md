## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The bug was reproduced: a test fails before the fix and passes after it, with no regressions found, no breaking inputs from Break My Fix, and the fix lines covered. The most important thing to look at next is the guard stage, which ended not\_guarded, and the mutation results that kept this at L1, so consider strengthening the tests to catch more mutants; the behaviour diff was also inconclusive.

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 5 mutants; 80% is needed

**Issue:** \`mpu.colorbar\` overwrites gca · **Repo:** testbed · **Base** `tf-base` (`52068a6`) → **head** `tf-agent_ok` (`c0b4da0`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.4, mutants 5, killed 2, survived 3 |
| `regressions` | `none_found` | compared 134, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 9 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 3, properties counted 4, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `mplotutils/_colorbar.py:254`: `             plt.sca(original_ax) ` → `             plt.sca(axs[0]) ` made no test fail; not compared with the fix (`m-88a241356387`)
- `mplotutils/_colorbar.py:216`: `         original_ax = plt.gca() ` → `         original_ax = axs[0] ` made no test fail; not compared with the fix (`m-0192bd1da2fe`)
- `mplotutils/_colorbar.py:219`: `         original_ax = None ` → `         original_ax = axs[0] ` made no test fail; not compared with the fix (`m-cca84a81f27d`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 5 calls, 26,238 input and 3,156 output tokens, cost $0.1382 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 9.84 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 6.3 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 24.49 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no mplotutils...`
- `guard`: `not_guarded`, 83.68 s: the tests killed 2 of 5 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no mplotutils...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 9.0 s: none of the 134 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.5 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no mplotutils...`
- `behaviour_diff`: `inconclusive`, 3.38 s: nothing was compared: colorbar: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 48.67 s: no counterexample found in 3 inputs against 4 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Found before the fix too
- `colorbar(mappable=None)` → `raises TypeError: colorbar() missing 1 required positional a...` (before the fix: `raises TypeError: colorbar() missing 1 required positional a...`); breaks **colorbar\_does\_not\_become\_current\_axes**: “\`mpu.colorbar\` creates a new axes and hijacks \`plt.gca()\` - see if we can avoid this” (issue); 2 more inputs break it the same way
#### Break My Fix targets
- `mplotutils._colorbar.colorbar` (`mplotutils/_colorbar.py`): 3 inputs
#### Fix lines run (report only)
- repro: 5 of 9 fix lines run
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
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.16: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T22:09:58+00:00, issue sha256 `1dd0b042efb5ca2f6e347102bef5136f99a33cfdf01a2b0ceb40ad7af0e69e36`

</details>
