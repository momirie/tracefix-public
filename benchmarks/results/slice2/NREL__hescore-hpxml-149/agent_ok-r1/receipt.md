## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the issue, but two existing tests (TestOtherHouses.test\_external\_id\_passthru and test\_external\_id\_extension\_passthru) passed before the fix and fail after it, so the evidence is a counterexample. Look first at whether those tests still expect external\_building\_id under building.about.

**Why this level:** regression: tests/test\_translation.py::TestOtherHouses.test\_external\_id\_passthru passed before the fix and fails after it; regression: tests/test\_translation.py::TestOtherHouses.test\_external\_id\_extension\_passthru passed before the fix and fails after it

**Issue:** Move external\_building\_id to building\_address · **Repo:** testbed · **Base** `tf-base` (`e5af845`) → **head** `tf-agent_ok` (`b8e8633`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. Regression: `tests/test_translation.py::TestOtherHouses.test_external_id_passthru` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: '6d1e249c716d4cef830ef8e59ce38ea2' != None)
2. Regression: `tests/test_translation.py::TestOtherHouses.test_external_id_extension_passthru` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: '7f73c7e27f2647af995955f33f5e71bc' != None)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 3 |
| `guard` | `not_guarded` | kill rate 0\.6, mutants 5, killed 3, survived 2 |
| `regressions` | `found` | compared 172, regressions 2, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 7 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 2, inputs tried 0, properties counted 5, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `hescorehpxml/base.py:815`: `                 break ` → `                 continue ` made no test fail; not compared with the fix (`m-ceb977beed25`)
- `hescorehpxml/base.py:808`: `             'h:extension/h:HESExternalID/text()', ` → `             'h:extension/h:HESExternalId/text()', ` made no test fail; not compared with the fix (`m-a663bab6e47d`)
- `hescorehpxml/base.py:815`: `                 break ` → `                 continue ` made no test fail; not compared with the fix (`m-ceb977beed25`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 55,049 input and 5,508 output tokens, cost $0.2396 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 4.36 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.58 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 27.12 s: attempt 3: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 57.68 s: the tests killed 3 of 5 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 32.15 s: 2 confirmed: tests/test\_translation.py::TestOtherHouses.test\_external\_id\_passthru, tests/test\_translation.py::TestOtherHouses.test\_external\_id\_extension\_passthru
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 1.76 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 2.08 s: nothing was compared: HPXMLtoHEScoreTranslatorBase.get\_building\_address: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 25.78 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.09 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `hescorehpxml.base.HPXMLtoHEScoreTranslatorBase.get_building_address` (`hescorehpxml/base.py`): 0 inputs
- `hescorehpxml.base.HPXMLtoHEScoreTranslatorBase.get_building_about` (`hescorehpxml/base.py`): 0 inputs
#### Fix lines run (report only)
- repro: 7 of 7 fix lines run
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
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T19:07:47+00:00, issue sha256 `924cf63e9b7d80caf2fa9b5cae607516d7009b7b08e4d7f509feb54ae622ab49`

</details>
