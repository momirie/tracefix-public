## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the original issue, but found a regression: the existing test test\_endpoint\_shadowing in phabricator/tests/test\_phabricator.py passed before the fix and fails after it, so this fix is a counterexample, not a confirmed fix. Look first at why test\_endpoint\_shadowing now fails, since it likely covers the same Resource-attribute-versus-endpoint naming conflict this fix changes.

**Why this level:** regression: phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_endpoint\_shadowing passed before the fix and fails after it

**Issue:** Conflict between Resource class attribute and new almanac interface endpoints · **Repo:** testbed · **Base** `tf-base` (`57b954c`) → **head** `tf-gold` (`3509fca`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. Regression: `phabricator/tests/test_phabricator.py::PhabricatorTest.test_endpoint_shadowing` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: requests.exceptions.ConnectionError: HTTPConnectionPool(host='localhost', port=80): Max retries exceeded with url: /api/conduit.connect (Caused by NewConnectionError('&lt;urllib3.connection.HTTPConnection object at 0x77fcbf330ca0&gt;: Failed to establish a new connection: \[Errno 111\] Connection refused')))

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.5, mutants 4, killed 2, survived 2 |
| `regressions` | `found` | compared 10, regressions 1, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 5 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 2, inputs tried 0, properties counted 1, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `phabricator/__init__.py:227`: `         self._interface = interface or copy.deepcopy(parse_i... ` → `         self._interface = interface or parse_interfaces(INTE... ` made no test fail; not compared with the fix (`m-1e82c5a4ab9a`)
- `phabricator/__init__.py:394`: `         self._interface = parse_interfaces(interfaces) ` → `         self._interface = interfaces ` made no test fail; not compared with the fix (`m-68ed007c1d69`)
- `phabricator/__init__.py:390`: `         query = Resource(api=self, method='conduit', endpoin... ` → `         return None ` made no test fail; not compared with the fix (`m-075a789aaf25`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; the behaviour diff could not compare Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; the behaviour diff could not compare Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; and 1 more in receipt.json
- **Model use:** 7 calls, 35,703 input and 4,952 output tokens, cost $0.2049 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.5 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.22 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 34.41 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
- `guard`: `not_guarded`, 60.82 s: the tests killed 2 of 4 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 17.22 s: 1 confirmed: phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_endpoint\_shadowing
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.33 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
- `behaviour_diff`: `inconclusive`, 10.98 s: nothing was compared: Resource.\_\_getattr\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `inconclusive`, 43.77 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `phabricator.Phabricator.update_interfaces` (`phabricator/__init__.py`): not attacked (no property to check it against)
- `phabricator.Resource._request` (`phabricator/__init__.py`): 0 inputs
#### Fix lines run (report only)
- repro: 2 of 5 fix lines run
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
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.20: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T18:35:27+00:00, issue sha256 `c7bf5b8dd3b29f88fcb2e52f6f065c1914b9d9a73ffd9c75661e83bc74d6eda7`

</details>
