## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the issue, but two existing tests (TestOtherHouses.test\_external\_id\_passthru and test\_external\_id\_extension\_passthru in tests/test\_translation.py) passed before the fix and fail after it, which is a counterexample. Check whether those tests still assert external\_building\_id under building.about; if so, either update them deliberately to expect building\_address or adjust th…

**Why this level:** regression: tests/test\_translation.py::TestOtherHouses.test\_external\_id\_passthru passed before the fix and fails after it; regression: tests/test\_translation.py::TestOtherHouses.test\_external\_id\_extension\_passthru passed before the fix and fails after it

**Issue:** Move external\_building\_id to building\_address · **Repo:** testbed · **Base** `tf-base` (`e5af845`) → **head** `tf-agent_wrong` (`92bf5a6`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. Regression: `tests/test_translation.py::TestOtherHouses.test_external_id_passthru` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: '7bf8eabe06c6495ca67df7c9f3f17d21' != None)
2. Regression: `tests/test_translation.py::TestOtherHouses.test_external_id_extension_passthru` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: '4ca20e6231b14c098b8d5c2e63d47061' != None)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 3 |
| `guard` | `not_guarded` | kill rate 0\.5, mutants 4, killed 2, survived 2 |
| `regressions` | `found` | compared 172, regressions 2, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 45 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 2, inputs tried 0, properties counted 5, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_on_head` | attempts 2, report only True |

**Rule mutants by kind (report only):** body: 2 of 3 killed; compare: 0 of 1 killed; constant: 0 of 2 killed; membership: 1 of 1 killed; loop: 0 of 1 killed; drop\_call: 0 of 2 killed; no place for logic, negate\_if, arithmetic, reraise

### Changes no test noticed (3 of 9; the rest in receipt.json)
- `hescorehpxml/base.py:815`: `         ext_id_xpath_exprs = (\n            'h:BuildingID/h:S... ` → `         ext_id_xpath_exprs = (\n            'h:extension/h:HE... ` made no test fail; not compared with the fix (`m-3c994eca6503`)
- `hescorehpxml/base.py:823`: `                 break ` → `                 continue ` made no test fail; not compared with the fix (`m-16258169ce36`)
- `debug_priority.py:18`: `     print("=== Debugging Priority Order ===")\n    \n    # Loa... ` → `     return None ` made no test fail; not compared with the fix (`m-632b4c8a7b22`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack debug\_priority: it takes no parameters to vary; the behaviour diff could not compare debug\_priority: new with the fix: nothing to compare; 9 things the behaviour diff can't observe (run log)
- **Model use:** 10 calls, 94,050 input and 9,413 output tokens, cost $0.4165 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 4.67 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.21 s: 2 changed module(s) imported from the copies (3 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 8.01 s: attempt 3: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 162.6 s: the PR's test file comprehensive\_test.py does not fail with the fix reverted (passed); the PR's test file test\_external\_id\_reproduction.py does not fail with the fix reverted (passed)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_exter...`
  - 2 more command(s) in receipt.json
- `regressions`: `found`, 35.69 s: 2 confirmed: tests/test\_translation.py::TestOtherHouses.test\_external\_id\_passthru, tests/test\_translation.py::TestOtherHouses.test\_external\_id\_extension\_passthru
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.84 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
- `behaviour_diff`: `inconclusive`, 2.31 s: nothing was compared: debug\_priority.py: module-level code that computes a value changed (line 9, 66, 67); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 26.71 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.11 s: no candidate was confirmed (1 reported)
- `blind`: `fails_on_head`, 6.99 s: attempt 2: fails the same way before and after the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### Break My Fix targets
- `hescorehpxml.base.HPXMLtoHEScoreTranslatorBase.get_building_address` (`hescorehpxml/base.py`): 0 inputs (no object of HPXMLtoHEScoreTranslatorBase was built: none was given, and no type hints make one)
- `hescorehpxml.base.HPXMLtoHEScoreTranslatorBase.get_building_about` (`hescorehpxml/base.py`): 0 inputs (no object of HPXMLtoHEScoreTranslatorBase was built: none was given, and no type hints make one)
#### More changes no test noticed
- `debug_priority.py:66`: `if __name__ == '__main__':` → `if __name__ != '__main__':` made no test fail; not compared with the fix (`m-1d5ae06f21e4`)
- `debug_priority.py:9`: `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '...` → `sys.path.insert((-1), os.path.join(os.path.dirname(__file__)...` made no test fail; not compared with the fix (`m-8f8dcbacd2af`)
- `hescorehpxml/base.py:823`: `                 break ` → `                 continue ` made no test fail; not compared with the fix (`m-16258169ce36`)
- `debug_priority.py:9`: `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '...` → `pass` made no test fail; not compared with the fix (`m-24e73d71dbcc`)
- `debug_priority.py:9`: `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '...` → `sys.path.insert(1, os.path.join(os.path.dirname(__file__), '...` made no test fail; not compared with the fix (`m-4fa4d68239e7`)
- `debug_priority.py:18`: `     print("=== Debugging Priority Order ===") ` → `     pass ` made no test fail; not compared with the fix (`m-05ca8ff4c3e4`)
#### Fix lines run (report only)
- repro: 7 of 45 fix lines run
- pr\_test: 7 of 45 fix lines run
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
- Break My Fix could not attack debug\_priority: it takes no parameters to vary
- the behaviour diff could not compare debug\_priority: new with the fix: nothing to compare
#### Notes
- guard: 3 of the 7 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 30 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T21:27:54+00:00, issue sha256 `924cf63e9b7d80caf2fa9b5cae607516d7009b7b08e4d7f509feb54ae622ab49`

</details>
