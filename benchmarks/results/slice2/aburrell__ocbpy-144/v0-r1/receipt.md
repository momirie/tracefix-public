## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier found a counterexample: calling DualBoundary.set\_good\_ind on a DualBoundary spanning 2002-10-30 to 2002-11-01 (hemisphere 1) returns None after the fix. Also, test\_vort.py::TestVortLogWarnings.test\_vort\_unexpected\_line passed before the fix and fails after it, and the original failure was not reproduced.

**Why this level:** Break My Fix finding 1: an input that breaks ocbpy.\_boundary.DualBoundary.set\_good\_ind; regression: ocbpy/tests/test\_vort.py::TestVortLogWarnings.test\_vort\_unexpected\_line passed before the fix and fails after it

**Issue:** dual boundary class can have a bad pair · **Repo:** testbed · **Base** `tf-base` (`728bfcb`) → **head** `tf-v0` (`1a57390`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `set_good_ind(self='DualBoundary(stime=datetime.datetime(2002...` → `returns None` (before the fix: `returns None`); breaks **eab\_indices\_within\_data\_range**: “a 'pair' was established with a good OCB and an EAB index outside of the data range” (issue); 1 more input break it the same way; test: `findings/finding_1.py`
2. Regression: `ocbpy/tests/test_vort.py::TestVortLogWarnings.test_vort_unexpected_line` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: OSError: unexpected line encountered when number of entries line expected \[0 1 13 14 5532.5 0.0011232 3.0527)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `not_reproduced` | attempts 3 |
| `guard` | `skipped` | mutants 0, killed 0, survived 0 |
| `regressions` | `found` | compared 363, regressions 1, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 28 |
| `behaviour_diff` | `compared` | inputs compared 1, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 2, inputs tried 14, properties counted 12, findings 1 |
| `integrity` | `clean` | flags 0 |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; guard: skipped (there is no reproduction test to judge the tests with (not\_reproduced)); 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 89,679 input and 10,338 output tokens, cost $0.4459 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 91.82 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.1 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `not_reproduced`, 182.23 s: attempt 3 failed the same way before and after the fix, but the model never got to review that result, so it does not count as fix\_does\_not\_fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no ocbpy/test...`
- `guard`: `skipped`, 0.0 s: there is no reproduction test to judge the tests with (not\_reproduced)
- `regressions`: `found`, 369.76 s: 1 confirmed: ocbpy/tests/test\_vort.py::TestVortLogWarnings.test\_vort\_unexpected\_line
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 0.02 s: report only: which fix lines the tests run
- `behaviour_diff`: `compared`, 488.25 s: 1 input(s) compared on 2 function(s): 0 changed with the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 953.68 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no ocbpy/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 0.08 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `ocbpy._boundary.DualBoundary.set_good_ind` (`ocbpy/_boundary.py`): 0 inputs; its attack did not finish
- `ocbpy.instruments.vort.load_vorticity_ascii_data` (`ocbpy/instruments/vort.py`): 14 inputs
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
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T19:05:01+00:00, issue sha256 `df0b89ebbdaec29b1769274cd6105d54d6735eaacf18bdeab34158668fce44bf`

</details>
