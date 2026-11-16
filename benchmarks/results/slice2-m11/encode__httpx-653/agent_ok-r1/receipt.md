## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The bug was reproduced: a test that checks \`params\` being merged into an existing URL query string fails before the fix and passes after it, but the regression run was inconclusive and the guard stage found the fix not guarded by mutation-killing tests. Next, get a conclusive regression run and add tests that pin the merge behaviour (for example, duplicate keys and empty query strings) so mutants…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 5 of 7 mutants; 80% is needed

**Issue:** \`params\` overrides query string in url · **Repo:** testbed · **Base** `tf-base` (`5ee512d`) → **head** `tf-agent_ok` (`84b75b6`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.714, mutants 7, killed 5, survived 2 |
| `regressions` | `inconclusive` | compared 460, regressions 0, unconfirmed 1 |
| `fix_line_coverage` | `ok` | fix lines 35 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 2 killed; compare: 0 of 1 killed; logic: 1 of 2 killed; negate\_if: 0 of 1 killed; constant: 0 of 1 killed; membership: 0 of 1 killed; drop\_call: 1 of 1 killed; reraise: 0 of 1 killed; no place for arithmetic, loop

### Changes no test noticed (3 of 9; the rest in receipt.json)
- `httpx/models.py:99`: `             query_string = str(existing_params) ` → `             query_string = str(existing_params) or self._uri... ` made no test fail; not compared with the fix (`m-0cf41a4b1891`)
- `httpx/models.py:96`: `             existing_params = QueryParams(self._uri_referenc... ` → `             existing_params = QueryParams(self._uri_referenc... ` made no test fail; not compared with the fix (`m-00126e44b114`)
- `reproduce_issue.py:52`: `if __name__ == "__main__":` → `if __name__ != "__main__":` made no test fail; not compared with the fix (`m-1177efd36dc3`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (URL.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; test\_params\_merge: new with the fix: nothing to compare)); break\_my\_fix: skipped (the fix changes no function Break My Fix can call (URL.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; test\_params\_merge: it takes no parameters to vary)); Break My Fix could not attack URL.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack test\_params\_merge: it takes no parameters to vary; and 3 more in receipt.json
- **Model use:** 5 calls, 19,118 input and 1,857 output tokens, cost $0.0608 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 8.91 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.93 s: 2 changed module(s) imported from the copies (3 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 13.96 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/mode...`
- `guard`: `not_guarded`, 317.4 s: the tests killed 5 of 7 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/mode...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no final_test.py`
  - 3 more command(s) in receipt.json
- `regressions`: `inconclusive`, 51.68 s: not confirmed: tests/test\_concurrency.py::test\_lookup\_backend
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 5.77 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/mode...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
- `behaviour_diff`: `skipped`, 0.23 s: the fix changes no function the behaviour diff can call (URL.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; test\_params\_merge: new with the fix: nothing to compare)
- `break_my_fix`: `skipped`, 0.01 s: the fix changes no function Break My Fix can call (URL.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; test\_params\_merge: it takes no parameters to vary)
- `integrity`: `clean`, 6.93 s: no candidate was confirmed (2 reported)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/mode...`
- `blind`: `reproduced`, 16.26 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/mode...`
#### More changes no test noticed
- `reproduce_issue.py:20`: `         if 'a' in result and 'b' in result: ` → `         if not ('a' in result and 'b' in result): ` made no test fail; not compared with the fix (`m-42310889b159`)
- `reproduce_issue.py:15`: `         response = await httpx.get(URL, params={'b': 2}) ` → `         response = await httpx.get(URL, params={'b': 1}) ` made no test fail; not compared with the fix (`m-a84544ea0470`)
- `reproduce_issue.py:20`: `         if 'a' in result and 'b' in result: ` → `         if 'a' not in result and 'b' in result: ` made no test fail; not compared with the fix (`m-b6350c3ecdba`)
- `reproduce_issue.py:28`: `         print(f"❌ ERROR: {e}") ` → `         raise\n        print(f"❌ ERROR: {e}") ` made no test fail; not compared with the fix (`m-b48e754da703`)
- `reproduce_issue.py:10`: `     print("Testing params merging behavior...")\n    \n    # T... ` → `     return None ` made no test fail; not compared with the fix (`m-79aa96bbd647`)
- `reproduce_issue.py:20`: `         if 'a' in result and 'b' in result: ` → `         if 'a' in result or 'b' in result: ` made no test fail; not compared with the fix (`m-2e4239211db2`)
#### Fix lines run (report only)
- repro: 3 of 35 fix lines run
- pr\_test: 3 of 35 fix lines run
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (URL.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; test\_params\_merge: new with the fix: nothing to compare))
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call (URL.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; test\_params\_merge: it takes no parameters to vary))
- Break My Fix could not attack URL.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack test\_params\_merge: it takes no parameters to vary
- the behaviour diff could not compare URL.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare test\_params\_merge: new with the fix: nothing to compare
#### Notes
- reproduce: style example tests/models/test\_url.py truncated to 6000 characters for the prompt
- guard: local\_final\_test.py has no tests, so it is not counted as a PR test
- guard: 1 of the 8 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 41 rule mutants were run
- blind: style example tests/models/test\_url.py truncated to 6000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T18:53:07+00:00, issue sha256 `f3c62b22034b4766405dbb0063d0cce7b38976a932b8ae4a37c9cde13bef26e6`

</details>
