## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproducing the RecursionError failed before the fix and passed after it, the fixed lines were covered, and Break My Fix found no breaking inputs, though the guard stage reported the fix as not guarded and the regression and behaviour-diff stages were skipped. The most important next step is to strengthen the tests so they kill enough mutants of the fix, and to run the skipped regression c…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 1 of 6 mutants; 80% is needed

**Issue:** Raises RecursionError under certain conditions · **Repo:** testbed · **Base** `tf-base` (`ca43530`) → **head** `tf-agent_ok` (`72e5848`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 6 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.167, mutants 6, killed 1, survived 5 |
| `regressions` | `skipped` | compared 0, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 131 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 3, inputs tried 6, properties counted 6, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 13; the rest in receipt.json)
- `faker/proxy.py:104`: `         if attr.startswith('__') and attr.endswith('__'): ` → `         if attr.startswith('__') or attr.endswith('__'): ` made no test fail; not compared with the fix (`m-33df99d41800`)
- `faker/proxy.py:269`: `         if name.startswith('__') and name.endswith('__'): ` → `         if name.startswith('__') or name.endswith('__'): ` made no test fail; not compared with the fix (`m-bae272d9ef0c`)
- `faker/proxy.py:104`: `         if attr.startswith('__') and attr.endswith('__'): ` → `         if attr.startswith('__'): ` made no test fail; not compared with the fix (`m-744f32eb554a`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; regressions: skipped (no test the fix left untouched passed before it); behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (MyFaker.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; UniqueProxy.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)); Break My Fix could not attack MyFaker.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack debug\_deepcopy: it takes no parameters to vary; and 24 more in receipt.json
- **Model use:** 5 calls, 35,719 input and 3,382 output tokens, cost $0.1779 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 15.03 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.91 s: 6 changed module(s) imported from the copies (7 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 32.78 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 492.05 s: the tests killed 1 of 6 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `skipped`, 0.42 s: no test the fix left untouched passed before it
- `fix_line_coverage`: `ok`, 3.15 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `skipped`, 0.47 s: the fix changes no function the behaviour diff can call (MyFaker.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; UniqueProxy.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
- `break_my_fix`: `none_found`, 34.27 s: no counterexample found in 6 inputs against 6 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.03 s: no candidate was confirmed (5 reported)
#### Break My Fix targets
- `debug_issue.MyFaker.example` (`debug_issue.py`): 2 inputs
- `full_traceback.MyFaker.example` (`full_traceback.py`): 2 inputs
- `reproduce_issue.MyFaker.example` (`reproduce_issue.py`): 2 inputs
#### More changes no test noticed
- `faker/proxy.py:269`: `         if name.startswith('__') and name.endswith('__'): ` → `         if name.endswith('__'): ` made no test fail; not compared with the fix (`m-9218445c383e`)
- `faker/proxy.py:104`: `         if attr.startswith('__') and attr.endswith('__'): ` → `         if attr.startswith('_') and attr.endswith('_'): ` made no test fail; not compared with the fix (`m-e3a11e092340`)
- `debug_issue.py:13`: `         self.fake = Faker() ` → `         return None ` made no test fail; not compared with the fix (`m-014972935d35`)
- `debug_issue.py:16`: `         pass ` → `         return None ` made no test fail; not compared with the fix (`m-d1f4a0786df6`)
- `debug_issue.py:21`: `     print("Creating MyFaker instance...")\n    my_faker = MyF... ` → `     return None ` made no test fail; not compared with the fix (`m-6afaa78616d9`)
- `deep_debug.py:10`: `     print("Creating Faker instance...")\n    fake = Faker()\n ... ` → `     return None ` made no test fail; not compared with the fix (`m-a7cdf5bf2282`)
- `debug_issue.py:36`: `if __name__ == "__main__":` → `if __name__ != "__main__":` made no test fail; not compared with the fix (`m-95067347b38f`)
- `deep_debug.py:27`: `if __name__ == "__main__":` → `if __name__ != "__main__":` made no test fail; not compared with the fix (`m-4743dc4e7025`)
- `faker/proxy.py:104`: `         if attr.startswith('__') and attr.endswith('__'): ` → `         if attr.startswith('__') or attr.endswith('__'): ` made no test fail; not compared with the fix (`m-33df99d41800`)
- `faker/proxy.py:269`: `         if name.startswith('__') and name.endswith('__'): ` → `         if name.startswith('__') or name.endswith('__'): ` made no test fail; not compared with the fix (`m-bae272d9ef0c`)
#### Fix lines run (report only)
- repro: 4 of 131 fix lines run
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
- regressions: skipped (no test the fix left untouched passed before it)
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (MyFaker.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; UniqueProxy.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet))
- Break My Fix could not attack MyFaker.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack debug\_deepcopy: it takes no parameters to vary
- Break My Fix could not attack test\_deep: it takes no parameters to vary
- Break My Fix could not attack Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack UniqueProxy.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack MyFaker.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack main: it takes no parameters to vary
- Break My Fix could not attack MyFaker.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack test\_deepcopy\_recursion\_error: it takes no parameters to vary
- Break My Fix could not attack test\_hasattr\_setstate: it takes no parameters to vary
- Break My Fix could not attack test\_simple: it takes no parameters to vary
- the behaviour diff could not compare MyFaker.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare UniqueProxy.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare MyFaker.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare MyFaker.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare test\_deepcopy\_recursion\_error: past the cap of 6 functions
- the behaviour diff could not compare test\_hasattr\_setstate: past the cap of 6 functions
- the behaviour diff could not compare test\_simple: past the cap of 6 functions
- the behaviour diff could not compare MyFaker.example: new with the fix: nothing to compare
- the behaviour diff could not compare debug\_deepcopy: new with the fix: nothing to compare
- the behaviour diff could not compare test\_deep: new with the fix: nothing to compare
- the behaviour diff could not compare MyFaker.example: new with the fix: nothing to compare
- the behaviour diff could not compare main: new with the fix: nothing to compare
- the behaviour diff could not compare MyFaker.example: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 17 functions were shown
- guard: only the first 10 of 38 rule mutants were run
- behaviour\_diff: only the first 6 of 9 functions are attacked
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T20:19:25+00:00, issue sha256 `69a4bfe759ee3d30453f6db223eea3c294f94b6edc55b2a03b164f3d8a33a409`

</details>
