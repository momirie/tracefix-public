## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test failed before the fix and passes after it, so the NOS plugin "No playable streams found" bug was reproduced and is addressed in the tested scenario; no regressions, breaking inputs, or integrity flags were found. The level stayed at L1 because the mutation stage did not meet the L2 threshold (the guard stage ended as not\_guarded), so the next thing to look at is strengthening the tests so…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 0 of 6 mutants; 80% is needed

**Issue:** plugins.nos: No playable streams found on this URL · **Repo:** testbed · **Base** `tf-base` (`22f1917`) → **head** `tf-agent_wrong` (`9a1b7d9`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 9 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 6, killed 0, survived 6 |
| `regressions` | `none_found` | compared 3736, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 521 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 6, inputs tried 2, properties counted 6, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 16; the rest in receipt.json)
- `src/streamlink/plugins/nos.py:51`: `                 if stream_url and is_live: ` → `                 if stream_url or is_live: ` made no test fail; not compared with the fix (`m-ce020cea2c4b`)
- `src/streamlink/plugins/nos.py:45`: `                 is_live = livestream.get("isLive", False) ` → `                 is_live = livestream.get("isLive", True) ` made no test fail; not compared with the fix (`m-42502bbb8abf`)
- `src/streamlink/plugins/nos.py:63`: `                         first_live = live_livestreams[0] ` → `                         first_live = live_livestreams[-1] ` made no test fail; not compared with the fix (`m-f463a7fa7166`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (deep\_analyze\_nos\_data.search\_dict: a nested function: it can't be imported, not attacked yet; test\_original\_issue: past the cap of 6 functions; test\_original\_issue: past the cap of 6 functions)); Break My Fix could not attack deep\_analyze\_nos\_data.search\_dict: a nested function: it can't be imported, not attacked yet; Break My Fix could not attack test\_original\_issue: it takes no parameters to vary; Break My Fix could not attack test\_original\_issue: it takes no parameters to vary; and 12 more in receipt.json
- **Model use:** 6 calls, 95,225 input and 3,028 output tokens, cost $0.3445 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 23.24 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.53 s: 9 changed module(s) imported from the copies (10 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 22.31 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no build_back...`
- `guard`: `not_guarded`, 887.52 s: the tests killed 0 of 6 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no build_back...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_fix.py`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_live_...`
  - 4 more command(s) in receipt.json
- `regressions`: `none_found`, 88.72 s: none of the 3736 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 6.02 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no build_back...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_fix.p...`
- `behaviour_diff`: `skipped`, 0.94 s: the fix changes no function the behaviour diff can call (deep\_analyze\_nos\_data.search\_dict: a nested function: it can't be imported, not attacked yet; test\_original\_issue: past the cap of 6 functions; test\_original\_issue: past the cap of 6 functions)
- `break_my_fix`: `none_found`, 23.89 s: no counterexample found in 2 inputs against 6 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.05 s: no candidate was confirmed (22 reported)
#### Break My Fix targets
- `debug_nos.debug_nos_plugin` (`debug_nos.py`): 2 inputs
- `debug_nos_analysis.analyze_nos_html` (`debug_nos_analysis.py`): 0 inputs
- `debug_nos_deep.deep_analyze_nos_data` (`debug_nos_deep.py`): 0 inputs
- `debug_nos_detailed.debug_nos_plugin_detailed` (`debug_nos_detailed.py`): 0 inputs
- `debug_script40.debug_script40` (`debug_script40.py`): 0 inputs
- `debug_xpath.debug_xpath` (`debug_xpath.py`): 0 inputs
#### More changes no test noticed
- `src/streamlink/plugins/nos.py:86`: `                     if profile.get("name") == "hls_unencrypt... ` → `                     if profile.get("name") != "hls_unencrypt... ` made no test fail; not compared with the fix (`m-2d05763d10b0`)
- `src/streamlink/plugins/nos.py:118`: `                         if "props" in json_data and "pagePro... ` → `                         if "props" in json_data or "pageProp... ` made no test fail; not compared with the fix (`m-d739860fd93d`)
- `src/streamlink/plugins/nos.py:57`: `                 elif not stream_url: ` → `                 elif stream_url: ` made no test fail; not compared with the fix (`m-d6ed64788509`)
- `debug_nos.py:17`: `     print(f"Testing URL: {url}")\n    \n    # Create a Streaml... ` → `     return None ` made no test fail; not compared with the fix (`m-0e7fef1fb43c`)
- `debug_nos_analysis.py:19`: `     print(f"Analyzing URL: {url}")\n    \n    # Create a Strea... ` → `     return None ` made no test fail; not compared with the fix (`m-3e77380eea56`)
- `debug_nos_deep.py:19`: `     print(f"Deep analyzing URL: {url}")\n    \n    # Create a ... ` → `     return None ` made no test fail; not compared with the fix (`m-b1cd14c8b13b`)
- `debug_nos_deep.py:57`: `                             if isinstance(d, dict):\n        ... ` → `                             return None ` made no test fail; not compared with the fix (`m-d860b98dd125`)
- `debug_nos.py:27`: `         if plugin: ` → `         if not (plugin): ` made no test fail; not compared with the fix (`m-1048e98a6180`)
- `debug_nos.py:38`: `if __name__ == "__main__":` → `if __name__ != "__main__":` made no test fail; not compared with the fix (`m-f6421711ad1b`)
- `debug_nos.py:42`: `     if len(sys.argv) > 1: ` → `     if not (len(sys.argv) > 1): ` made no test fail; not compared with the fix (`m-436686b22c2e`)
- `debug_nos.py:42`: `     if len(sys.argv) > 1: ` → `     if len(sys.argv) >= 1: ` made no test fail; not compared with the fix (`m-244a5be066ec`)
- `debug_nos.py:42`: `     if len(sys.argv) > 1: ` → `     if len(sys.argv) > 0: ` made no test fail; not compared with the fix (`m-526c96a70e79`)
- `debug_nos.py:42`: `     if len(sys.argv) > 1: ` → `     if len(sys.argv) > 2: ` made no test fail; not compared with the fix (`m-01b517b50e1c`)
#### Fix lines run (report only)
- repro: 34 of 521 fix lines run
- pr\_test: 57 of 521 fix lines run
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (deep\_analyze\_nos\_data.search\_dict: a nested function: it can't be imported, not attacked yet; test\_original\_issue: past the cap of 6 functions; test\_original\_issue: past the cap of 6 functions))
- Break My Fix could not attack deep\_analyze\_nos\_data.search\_dict: a nested function: it can't be imported, not attacked yet
- Break My Fix could not attack test\_original\_issue: it takes no parameters to vary
- Break My Fix could not attack test\_original\_issue: it takes no parameters to vary
- the behaviour diff could not compare deep\_analyze\_nos\_data.search\_dict: a nested function: it can't be imported, not attacked yet
- the behaviour diff could not compare test\_original\_issue: past the cap of 6 functions
- the behaviour diff could not compare test\_original\_issue: past the cap of 6 functions
- the behaviour diff could not compare NOS.\_parse\_next\_data: past the cap of 6 functions
- the behaviour diff could not compare NOS.\_get\_streams: past the cap of 6 functions
- the behaviour diff could not compare debug\_nos\_plugin: new with the fix: nothing to compare
- the behaviour diff could not compare analyze\_nos\_html: new with the fix: nothing to compare
- the behaviour diff could not compare deep\_analyze\_nos\_data: new with the fix: nothing to compare
- the behaviour diff could not compare debug\_nos\_plugin\_detailed: new with the fix: nothing to compare
- the behaviour diff could not compare debug\_script40: new with the fix: nothing to compare
- the behaviour diff could not compare debug\_xpath: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 14 functions were shown
- reproduce: pyproject truncated to 3000 characters for the prompt
- guard: only the first 10 of 210 rule mutants were run
- behaviour\_diff: only the first 6 of 10 functions are attacked
- break\_my\_fix: only the first 6 of 8 functions are attacked
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T17:52:08+00:00, issue sha256 `fd8de88cf76ee41447cf118e1c6440e69fc732b7c61984b31f27958027add3dc`

</details>
