## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the issue, but three previously passing tests in tests/nxtransformations\_test.py (test\_chain\_with\_single\_values\_and\_different\_unit, test\_chain\_with\_multiple\_values, and test\_chain\_with\_multiple\_values\_and\_different\_time\_unit) fail after the fix, and no test was found that guards the new behaviour. Look first at why these depends\_on chain tests now fail, since changing how…

**Why this level:** regression: tests/nxtransformations\_test.py::test\_chain\_with\_single\_values\_and\_different\_unit passed before the fix and fails after it; regression: tests/nxtransformations\_test.py::test\_chain\_with\_multiple\_values passed before the fix and fails after it; regression: tests/nxtransformations\_test.py::test\_chain\_with\_multiple\_values\_and\_different\_time\_unit passed before the fix and fails after it

**Issue:** Improve loading of NXtransformations · **Repo:** testbed · **Base** `tf-base` (`6da5856`) → **head** `tf-gold` (`4456beb`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. Regression: `tests/nxtransformations_test.py::test_chain_with_single_values_and_different_unit` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: assert False)
2. Regression: `tests/nxtransformations_test.py::test_chain_with_multiple_values` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: assert False)
3. Regression: `tests/nxtransformations_test.py::test_chain_with_multiple_values_and_different_time_unit` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: assert False)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.5, mutants 4, killed 2, survived 2 |
| `regressions` | `found` | compared 131, regressions 3, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 28 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 6, inputs tried 2, properties counted 8, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 5 of 6 killed; logic: 0 of 1 killed; membership: 2 of 2 killed; drop\_call: 1 of 1 killed; no place for compare, negate\_if, constant, arithmetic, loop, reraise

### Changes no test noticed (3 of 4; the rest in receipt.json)
- `src/scippnexus/nxtransformations.py:130`: `     return get_full_transformation_starting_at(t0) ` → `     return get_full_transformation_starting_at(t0, index=None) ` made no test fail; not compared with the fix (`m-a8786a154dd2`)
- `src/scippnexus/nxtransformations.py:172`: `         transformations.append(t[index]) ` → `         transformations.append(t[()]) ` made no test fail; not compared with the fix (`m-1f4ee191e5bd`)
- `src/scippnexus/nxdetector.py:95`: `         return self._nxevent_data.unit ` → `         return None ` made no test fail; not compared with the fix (`m-a11cbb1aa4c9`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; the behaviour diff could not compare \_get\_transformations: past the cap of 6 functions; the behaviour diff could not compare get\_full\_transformation\_starting\_at: new with the fix: nothing to compare; the behaviour diff could not compare NXtransformations.\_getitem: new with the fix: nothing to compare; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 54,112 input and 6,738 output tokens, cost $0.2750 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 4.57 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.2 s: 3 changed module(s) imported from the copies (6 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 17.62 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 123.67 s: the tests killed 2 of 4 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 27.0 s: 3 confirmed: tests/nxtransformations\_test.py::test\_chain\_with\_single\_values\_and\_different\_unit, tests/nxtransformations\_test.py::test\_chain\_with\_multiple\_values, tests/nxtransformations\_test.py::test\_chain\_with\_multiple\_values\_and\_different\_time\_unit
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.18 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 6.11 s: nothing was compared: \_get\_transformations: not compared (past the cap of 6 functions)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `none_found`, 7.26 s: no counterexample found in 2 inputs against 8 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 14.16 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### Break My Fix targets
- `scippnexus.nxdetector._EventField.unit` (`src/scippnexus/nxdetector.py`): 0 inputs (no object of \_EventField was built: none was given, and no type hints make one)
- `scippnexus.nxtransformations.make_transformation` (`src/scippnexus/nxtransformations.py`): 2 inputs
- `scippnexus.nxtransformations.get_full_transformation` (`src/scippnexus/nxtransformations.py`): 0 inputs (nothing generated)
- `scippnexus.nxtransformations.get_full_transformation_starting_at` (`src/scippnexus/nxtransformations.py`): 0 inputs (nothing generated)
- `scippnexus.nxdetector.NXdetector._event_grouping` (`src/scippnexus/nxdetector.py`): 0 inputs (nothing was judged, and 4 object(s) of NXdetector could not be built here (no object from NXdetector(): TypeError: \_\_init\_\_() missing 1 required positional argument: 'group'))
- `scippnexus.nxtransformations.NXtransformations._getitem` (`src/scippnexus/nxtransformations.py`): 0 inputs (no object of NXtransformations was built: none was given, and no type hints make one)
#### More changes no test noticed
- `src/scippnexus/nxtransformations.py:143`: `         elif isinstance(total_transform, sc.DataArray) and i... ` → `         elif isinstance(total_transform, sc.DataArray) or is... ` made no test fail; not compared with the fix (`m-4fc2ff97c077`)
#### Fix lines run (report only)
- repro: 25 of 28 fix lines run
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
- the behaviour diff could not compare \_get\_transformations: past the cap of 6 functions
- the behaviour diff could not compare get\_full\_transformation\_starting\_at: new with the fix: nothing to compare
- the behaviour diff could not compare NXtransformations.\_getitem: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 12 functions were shown
- guard: 3 of the 7 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 11 rule mutants were run
- behaviour\_diff: only the first 6 of 7 functions are attacked
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- break\_my\_fix: only the first 6 of 7 functions are attacked
- blind: only the first 8 of 10 functions were shown
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T20:18:41+00:00, issue sha256 `580d792de1b5b266fc794b770534eab9fb18479bb4fc838a0112ae4e830ae078`

</details>
