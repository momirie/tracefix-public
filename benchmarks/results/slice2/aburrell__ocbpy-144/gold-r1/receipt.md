## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The bug was reproduced, but two tests that passed before the fix now fail after it (test\_boundary\_dual.py::TestDualBoundaryMethodsGeneral::test\_custom\_ind\_selection and test\_vort.py::TestVortLogWarnings::test\_vort\_unexpected\_line), and no test was shown to guard the reported failure. Start by examining why those two tests now fail, and decide whether the fix changed custom index selection or vort…

**Why this level:** regression: ocbpy/tests/test\_boundary\_dual.py::TestDualBoundaryMethodsGeneral.test\_custom\_ind\_selection passed before the fix and fails after it; regression: ocbpy/tests/test\_vort.py::TestVortLogWarnings.test\_vort\_unexpected\_line passed before the fix and fails after it

**Issue:** dual boundary class can have a bad pair · **Repo:** testbed · **Base** `tf-base` (`728bfcb`) → **head** `tf-gold` (`a1efb71`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. Regression: `ocbpy/tests/test_boundary_dual.py::TestDualBoundaryMethodsGeneral.test_custom_ind_selection` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: -1 not greater than np.int64(0))
2. Regression: `ocbpy/tests/test_vort.py::TestVortLogWarnings.test_vort_unexpected_line` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: OSError: unexpected line encountered when number of entries line expected \[0 1 13 14 5532.5 0.0011232 3.0527)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 3 |
| `guard` | `not_guarded` | kill rate 0\.333, mutants 9, killed 3, survived 6 |
| `regressions` | `found` | compared 363, regressions 2, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 30 |
| `behaviour_diff` | `compared` | inputs compared 1, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 2, inputs tried 4, properties counted 9, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 7; the rest in receipt.json)
- `ocbpy/_boundary.py:1293`: `             if self.eab.rec_ind < self.eab.records: ` → `             if self.eab.rec_ind <= self.eab.records: ` made no test fail; not compared with the fix (`m-3aa5b728714d`)
- `ocbpy/instruments/vort.py:273`: `         while len(vsplit) > 0 and vsplit[0] == "#": ` → `         while len(vsplit) > 1 and vsplit[0] == "#": ` made no test fail; no input tried behaved differently from the fix (`m-d6d0cd5bb0a8`)
- `ocbpy/instruments/vort.py:282`: `                 if len(vsplit) != 4: ` → `                 if len(vsplit) < 4: ` made no test fail; no input tried behaved differently from the fix (`m-dd0a7fac6bc9`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 82,693 input and 9,165 output tokens, cost $0.3632 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 90.19 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.13 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 198.39 s: attempt 3: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no ocbpy/test...`
- `guard`: `not_guarded`, 2524.7 s: the tests killed 3 of 9 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no ocbpy/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 583.27 s: 2 confirmed: ocbpy/tests/test\_boundary\_dual.py::TestDualBoundaryMethodsGeneral.test\_custom\_ind\_selection, ocbpy/tests/test\_vort.py::TestVortLogWarnings.test\_vort\_unexpected\_line
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 49.86 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no ocbpy/test...`
- `behaviour_diff`: `compared`, 984.16 s: 1 input(s) compared on 2 function(s): 0 changed with the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `inconclusive`, 771.2 s: the attack on DualBoundary.set\_good\_ind did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no ocbpy/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.07 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `ocbpy._boundary.DualBoundary.set_good_ind` (`ocbpy/_boundary.py`): 3 inputs; its attack did not finish
- `ocbpy.instruments.vort.load_vorticity_ascii_data` (`ocbpy/instruments/vort.py`): 1 input
#### More changes no test noticed
- `ocbpy/instruments/vort.py:304`: `                 if len(vsplit) != 1: ` → `                 if len(vsplit) < 1: ` made no test fail; no input tried behaved differently from the fix (`m-adf469165368`)
- `ocbpy/instruments/vort.py:331`: `                         if len(vsplit) != len(bklist): ` → `                         if len(vsplit) < len(bklist): ` made no test fail; no input tried behaved differently from the fix (`m-bf2c0cf2fe8e`)
- `ocbpy/instruments/vort.py:357`: `         if len(vdata[vkey]) > 0: ` → `         if len(vdata[vkey]) > 1: ` made no test fail; no input tried behaved differently from the fix (`m-3469aefafe16`)
- `ocbpy/_boundary.py:1293`: `             if self.eab.rec_ind < self.eab.records: ` → `             if self.eab.rec_ind <= self.eab.records: ` made no test fail; not compared with the fix (`m-3aa5b728714d`)
#### Fix lines run (report only)
- repro: 4 of 30 fix lines run
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
- guard: only the first 10 of 28 rule mutants were run
- guard: 1 of the rule mutant kills were crashes on the mutated line
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T17:38:07+00:00, issue sha256 `df0b89ebbdaec29b1769274cd6105d54d6735eaacf18bdeab34158668fce44bf`

</details>
