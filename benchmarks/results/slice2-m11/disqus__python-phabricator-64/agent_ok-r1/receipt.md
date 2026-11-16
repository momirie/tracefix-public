## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug, where \`phab.almanac.interface.search\` resolved to the Resource's internal \`interface\` attribute instead of a conduit method: a test fails before the fix and passes after it, no regressions were found, and the fixed lines were covered. The guard and mutation checks did not reach L2, and the behaviour diff and break-my-fix stages were inconclusive, so next check tha…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 1 of 3 mutants; 80% is needed

**Issue:** Conflict between Resource class attribute and new almanac interface endpoints · **Repo:** testbed · **Base** `tf-base` (`57b954c`) → **head** `tf-agent_ok` (`7464c30`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.333, mutants 3, killed 1, survived 2 |
| `regressions` | `none_found` | compared 9, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 14 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 2, inputs tried 0, properties counted 1, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_differently` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 2 of 2 killed; compare: 0 of 1 killed; logic: 1 of 2 killed; negate\_if: 0 of 2 killed; constant: 0 of 1 killed; membership: 0 of 1 killed; reraise: 0 of 1 killed; no place for arithmetic, loop, drop\_call

### Changes no test noticed (3 of 9; the rest in receipt.json)
- `phabricator/__init__.py:227`: `         self._interface = interface or copy.deepcopy(parse_i... ` → `         self._interface = interface or parse_interfaces(INTE... ` made no test fail; not compared with the fix (`m-1e82c5a4ab9a`)
- `phabricator/__init__.py:235`: `         if name != '__dict__' and name in ('interface', 'api... ` → `         if name != '__dict__' and name in ('interface', 'api... ` made no test fail; not compared with the fix (`m-542fbd0129eb`)
- `phabricator/__init__.py:235`: `         if name != '__dict__' and name in ('interface', 'api... ` → `         if name == '__dict__' and name in ('interface', 'api... ` made no test fail; not compared with the fix (`m-42afe8d6419c`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Resource.\_\_getattribute\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; the behaviour diff could not compare Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; and 3 more in receipt.json
- **Model use:** 8 calls, 47,246 input and 5,380 output tokens, cost $0.2252 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.4 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.53 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 28.56 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
- `guard`: `not_guarded`, 121.54 s: the tests killed 1 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 2.46 s: none of the 9 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 5.7 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
- `behaviour_diff`: `inconclusive`, 26.56 s: nothing was compared: Resource.\_\_getattr\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `inconclusive`, 2.55 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.05 s: no candidate was confirmed (4 reported)
- `blind`: `fails_differently`, 18.34 s: attempt 1: fails after the fix too, but differently
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no phabricato...`
#### Break My Fix targets
- `phabricator.Phabricator.update_interfaces` (`phabricator/__init__.py`): not attacked (no property to check it against)
- `phabricator.Resource._request` (`phabricator/__init__.py`): 0 inputs (the property expressions failed on every input (PropertyError: the object could not be copied before the call))
#### More changes no test noticed
- `phabricator/__init__.py:235`: `         if name != '__dict__' and name in ('interface', 'api... ` → `         if not (name != '__dict__' and name in ('interface',... ` made no test fail; not compared with the fix (`m-14b62778b793`)
- `phabricator/__init__.py:239`: `                 if obj_dict.get('nested', False): ` → `                 if obj_dict.get('nested', True): ` made no test fail; not compared with the fix (`m-7ac11aceea84`)
- `phabricator/__init__.py:235`: `         if name != '__dict__' and name in ('interface', 'api... ` → `         if name != '__dict__' and name not in ('interface', ... ` made no test fail; not compared with the fix (`m-87677e1c9f63`)
- `phabricator/__init__.py:248`: `                 pass ` → `                 raise\n                pass ` made no test fail; not compared with the fix (`m-f8fac6103fe3`)
- `phabricator/__init__.py:235`: `         if name != '__dict__' and name in ('interface', 'api... ` → `         if name != '__dict__' or name in ('interface', 'api'... ` made no test fail; not compared with the fix (`m-b1750bf8df75`)
- `phabricator/__init__.py:239`: `                 if obj_dict.get('nested', False): ` → `                 if not (obj_dict.get('nested', False)): ` made no test fail; not compared with the fix (`m-f5db86d7cc54`)
#### Fix lines run (report only)
- repro: 11 of 14 fix lines run
- pr\_test: 11 of 14 fix lines run
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
- Break My Fix could not attack Resource.\_\_getattribute\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Resource.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Resource.\_\_getattribute\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Resource.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
#### Notes
- guard: 5 of the 8 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 13 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.20: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T21:17:13+00:00, issue sha256 `c7bf5b8dd3b29f88fcb2e52f6f065c1914b9d9a73ffd9c75661e83bc74d6eda7`

</details>
