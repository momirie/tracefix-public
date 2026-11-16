## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the original bug, but six existing tests in phabricator/tests/test\_phabricator.py (including test\_connect, test\_user\_whoami, test\_validation and test\_endpoint\_shadowing) passed before the fix and fail after it, which is a counterexample against this change. Look first at why these previously passing tests now fail, starting with test\_endpoint\_shadowing and test\_connect, si…

**Why this level:** regression: phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_connect passed before the fix and fails after it; regression: phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_user\_whoami passed before the fix and fails after it; regression: phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_bad\_status passed before the fix and fails after it; regression: phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_maniphest\_find passed before the fix and fails after it; regression: phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_validation passed before the fix and fails after it; regression: phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_endpoint\_shadowing passed before the fix and fails after it

**Issue:** Conflict between Resource class attribute and new almanac interface endpoints · **Repo:** testbed · **Base** `tf-base` (`57b954c`) → **head** `tf-v2` (`d6429c4`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples (5 of 6; the rest in receipt.json)
1. Regression: `phabricator/tests/test_phabricator.py::PhabricatorTest.test_connect` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: TypeError: \_\_call\_\_() takes 1 positional argument but 3 were given)
2. Regression: `phabricator/tests/test_phabricator.py::PhabricatorTest.test_user_whoami` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: TypeError: \_\_call\_\_() takes 1 positional argument but 3 were given)
3. Regression: `phabricator/tests/test_phabricator.py::PhabricatorTest.test_bad_status` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: TypeError: \_\_call\_\_() takes 1 positional argument but 3 were given)
4. Regression: `phabricator/tests/test_phabricator.py::PhabricatorTest.test_maniphest_find` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: TypeError: \_\_call\_\_() takes 1 positional argument but 3 were given)
5. Regression: `phabricator/tests/test_phabricator.py::PhabricatorTest.test_validation` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: TypeError: \_\_call\_\_() takes 1 positional argument but 3 were given)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.5, mutants 4, killed 2, survived 2 |
| `regressions` | `found` | compared 10, regressions 6, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 4 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 3, properties counted 3, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_differently` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 2 of 3 killed; logic: 1 of 1 killed; no place for compare, negate\_if, constant, arithmetic, membership, loop, drop\_call, reraise

### Changes no test noticed
- `phabricator/__init__.py:227`: `         self._interface = interface or copy.deepcopy(parse_i... ` → `         self._interface = interface or parse_interfaces(INTE... ` made no test fail; not compared with the fix (`m-1e82c5a4ab9a`)
- `phabricator/__init__.py:394`: `         self._interface = parse_interfaces(interfaces) ` → `         self._interface = interfaces ` made no test fail; not compared with the fix (`m-68ed007c1d69`)
- `phabricator/__init__.py:390`: `         query = Resource(api=self, method='conduit', endpoin... ` → `         return None ` made no test fail; not compared with the fix (`m-075a789aaf25`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; the behaviour diff could not compare Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; the behaviour diff could not compare Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; and 1 more in receipt.json
- **Model use:** 8 calls, 26,116 input and 4,821 output tokens, cost $0.1483 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.44 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.51 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 28.61 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
- `guard`: `not_guarded`, 73.46 s: the tests killed 2 of 4 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 18.15 s: 6 confirmed: phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_connect, phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_user\_whoami, phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_bad\_status, phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_maniphest\_find, phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_validation and 1 more
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.6 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
- `behaviour_diff`: `inconclusive`, 11.92 s: nothing was compared: Resource.\_\_getattr\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 5.55 s: no counterexample found in 3 inputs against 3 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_differently`, 18.26 s: attempt 1: fails after the fix too, but differently
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
#### More counterexamples
- Regression: `phabricator/tests/test_phabricator.py::PhabricatorTest.test_endpoint_shadowing` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: TypeError: \_\_call\_\_() takes 1 positional argument but 3 were given)
#### Break My Fix targets
- `phabricator.Phabricator.update_interfaces` (`phabricator/__init__.py`): 3 inputs
#### Fix lines run (report only)
- repro: 2 of 4 fix lines run
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
- Break My Fix could not attack Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
#### Notes
- guard: 4 of the 8 mutants were not run: the tests could no longer reach 80% even if they killed them all
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.20: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T21:11:21+00:00, issue sha256 `c7bf5b8dd3b29f88fcb2e52f6f065c1914b9d9a73ffd9c75661e83bc74d6eda7`

</details>
