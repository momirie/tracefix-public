## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug, but the existing test phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_endpoint\_shadowing passed before the fix and fails after it, so the fix introduces a regression. Look first at why the fix breaks test\_endpoint\_shadowing, likely around how Resource attributes such as interface are now resolved, and note that no test was found guarding the reported b…

**Why this level:** regression: phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_endpoint\_shadowing passed before the fix and fails after it

**Issue:** Conflict between Resource class attribute and new almanac interface endpoints · **Repo:** testbed · **Base** `tf-base` (`57b954c`) → **head** `tf-agent_wrong` (`c3292a4`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. Regression: `phabricator/tests/test_phabricator.py::PhabricatorTest.test_endpoint_shadowing` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: requests.exceptions.ConnectionError: HTTPConnectionPool(host='localhost', port=80): Max retries exceeded with url: /api/conduit.connect (Caused by NewConnectionError('&lt;urllib3.connection.HTTPConnection object at 0x7c379765ba60&gt;: Failed to establish a new connection: \[Errno 111\] Connection refused')))

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 7 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.4, mutants 5, killed 2, survived 3 |
| `regressions` | `found` | compared 10, regressions 1, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 269 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 4, inputs tried 0, properties counted 1, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 13; the rest in receipt.json)
- `phabricator/__init__.py:252`: `         elif original_attr in getattr(self, '__dict__', {}): ` → `         elif attr in getattr(self, '__dict__', {}): ` made no test fail; not compared with the fix (`m-29e2f53af83b`)
- `phabricator/__init__.py:227`: `         self._interface_data = interface or copy.deepcopy(pa... ` → `         self._interface_data = interface if interface is not... ` made no test fail; not compared with the fix (`m-f1bcc43b90d6`)
- `phabricator/__init__.py:403`: `         self._interface_data = parse_interfaces(interfaces) ` → `         self._interface_data = interfaces ` made no test fail; not compared with the fix (`m-cbcd160af885`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; debug\_interface\_access: past the cap of 6 functions)); Break My Fix could not attack check\_endpoints: it takes no parameters to vary; Break My Fix could not attack debug\_attrs: it takes no parameters to vary; Break My Fix could not attack debug\_clean: it takes no parameters to vary; and 18 more in receipt.json
- **Model use:** 6 calls, 64,877 input and 4,382 output tokens, cost $0.2861 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.34 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.37 s: 7 changed module(s) imported from the copies (8 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 19.11 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
- `guard`: `not_guarded`, 111.87 s: the tests killed 2 of 5 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no proper_tes...`
  - 1 more command(s) in receipt.json
- `regressions`: `found`, 17.05 s: 1 confirmed: phabricator/tests/test\_phabricator.py::PhabricatorTest.test\_endpoint\_shadowing
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 4.67 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no proper_tes...`
- `behaviour_diff`: `skipped`, 0.12 s: the fix changes no function the behaviour diff can call (Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; debug\_interface\_access: past the cap of 6 functions)
- `break_my_fix`: `inconclusive`, 44.29 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.03 s: no candidate was confirmed (8 reported)
#### Break My Fix targets
- `debug_clean.debug_getattr` (`debug_clean.py`): 0 inputs
- `debug_detailed.debug_getattr` (`debug_detailed.py`): 0 inputs
- `phabricator.Phabricator.update_interfaces` (`phabricator/__init__.py`): not attacked (no property to check it against)
- `phabricator.Resource._request` (`phabricator/__init__.py`): 0 inputs
#### More changes no test noticed
- `check_endpoints.py:12`: `     phab = Phabricator(username='test', certificate='test', ... ` → `     return None ` made no test fail; not compared with the fix (`m-93989614f68c`)
- `debug_attrs.py:12`: `     phab = Phabricator(username='test', certificate='test', ... ` → `     return None ` made no test fail; not compared with the fix (`m-46a94d9f2ec7`)
- `debug_clean.py:12`: `     print(f"DEBUG __getattr__: attr='{attr}', nested={getatt... ` → `     return None ` made no test fail; not compared with the fix (`m-e29bd9b091e8`)
- `debug_clean.py:66`: `     phab = Phabricator(username='test', certificate='test', ... ` → `     return None ` made no test fail; not compared with the fix (`m-399865e7d057`)
- `check_endpoints.py:21`: `     interface_endpoints = [k for k in phab.interface.keys() ... ` → `     interface_endpoints = [k for k in phab.interface.keys() ... ` made no test fail; not compared with the fix (`m-94c6fb58ec79`)
- `check_endpoints.py:44`: `if __name__ == '__main__':` → `if __name__ != '__main__':` made no test fail; not compared with the fix (`m-584426d32050`)
- `debug_attrs.py:49`: `if __name__ == '__main__':` → `if __name__ != '__main__':` made no test fail; not compared with the fix (`m-ce53e8877cfb`)
- `debug_clean.py:15`: `     if getattr(self, 'nested', False): ` → `     if not (getattr(self, 'nested', False)): ` made no test fail; not compared with the fix (`m-9efdca029477`)
- `debug_clean.py:15`: `     if getattr(self, 'nested', False): ` → `     if getattr(self, 'nested', True): ` made no test fail; not compared with the fix (`m-b3e130856a76`)
- `debug_clean.py:19`: `     submethod_exists = False ` → `     submethod_exists = True ` made no test fail; not compared with the fix (`m-6413f487449d`)
#### Fix lines run (report only)
- repro: 9 of 269 fix lines run
- pr\_test: 0 of 269 fix lines run
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; debug\_interface\_access: past the cap of 6 functions))
- Break My Fix could not attack check\_endpoints: it takes no parameters to vary
- Break My Fix could not attack debug\_attrs: it takes no parameters to vary
- Break My Fix could not attack debug\_clean: it takes no parameters to vary
- Break My Fix could not attack debug\_detailed: it takes no parameters to vary
- Break My Fix could not attack debug\_interface\_access: it takes no parameters to vary
- Break My Fix could not attack Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack test\_interface\_conflict: it takes no parameters to vary
- the behaviour diff could not compare Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare debug\_interface\_access: past the cap of 6 functions
- the behaviour diff could not compare Phabricator.update\_interfaces: past the cap of 6 functions
- the behaviour diff could not compare test\_interface\_conflict: past the cap of 6 functions
- the behaviour diff could not compare Resource.\_request: past the cap of 6 functions
- the behaviour diff could not compare check\_endpoints: new with the fix: nothing to compare
- the behaviour diff could not compare debug\_attrs: new with the fix: nothing to compare
- the behaviour diff could not compare debug\_getattr: new with the fix: nothing to compare
- the behaviour diff could not compare debug\_clean: new with the fix: nothing to compare
- the behaviour diff could not compare debug\_getattr: new with the fix: nothing to compare
- the behaviour diff could not compare debug\_detailed: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 13 functions were shown
- guard: proper\_test.py has no tests, so it is not counted as a PR test
- guard: simple\_test.py has no tests, so it is not counted as a PR test
- guard: only the first 10 of 66 rule mutants were run
- behaviour\_diff: only the first 6 of 10 functions are attacked
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T18:41:20+00:00, issue sha256 `c7bf5b8dd3b29f88fcb2e52f6f065c1914b9d9a73ffd9c75661e83bc74d6eda7`

</details>
