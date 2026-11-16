## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The bug was reproduced: a test fails before the fix and passes after it, no regressions or breaking inputs were found, and the changed lines were covered. The most important thing to check next is test strength, since the fix was not guarded and the tests did not kill enough mutants to reach L2, so stronger assertions on per-phase Shelly 3EM topic handling would help.

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 4 mutants; 80% is needed

**Issue:** Doesn't support Shelly 3EM format very well · **Repo:** testbed · **Base** `tf-base` (`4126ec6`) → **head** `tf-agent_ok` (`d40d01e`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 4 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.5, mutants 4, killed 2, survived 2 |
| `regressions` | `none_found` | compared 10, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 96 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 882, properties counted 8, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 0 of 2 killed; compare: 0 of 2 killed; logic: 0 of 1 killed; negate\_if: 0 of 1 killed; constant: 0 of 1 killed; arithmetic: 0 of 1 killed; membership: 0 of 1 killed; drop\_call: 0 of 1 killed; no place for loop, reraise

### Changes no test noticed (3 of 12; the rest in receipt.json)
- `mqtt_exporter/main.py:171`: `         if len(info) >= 5 and info[0] == "shellies" and info... ` → `         if len(info) >= 4 and info[0] == "shellies" and info... ` made no test fail; not compared with the fix (`m-5acf36e13dfc`)
- `mqtt_exporter/main.py:171`: `         if len(info) >= 5 and info[0] == "shellies" and info... ` → `         if len(info) >= 5 and info[0] == "shellies" or info[... ` made no test fail; not compared with the fix (`m-ff59fcff4497`)
- `debug_edge_case.py:12`: `     topic = "shellies/livingroom/relay/0"\n    payload = "ON"... ` → `     return None ` made no test fail; not compared with the fix (`m-c5c49624dcb6`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack debug\_shelly\_relay: it takes no parameters to vary; Break My Fix could not attack test\_exact\_issue\_scenario: it takes no parameters to vary; Break My Fix could not attack test\_shelly\_3em\_issue: it takes no parameters to vary; the behaviour diff could not compare debug\_shelly\_relay: new with the fix: nothing to compare; and 3 more in receipt.json
- **Model use:** 7 calls, 53,420 input and 7,537 output tokens, cost $0.3116 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 1.85 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.68 s: 4 changed module(s) imported from the copies (5 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 11.3 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 115.63 s: the tests killed 2 of 4 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_edge_...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_edge_...`
  - 3 more command(s) in receipt.json
- `regressions`: `none_found`, 2.01 s: none of the 10 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 4.54 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_edge_...`
- `behaviour_diff`: `inconclusive`, 2.26 s: nothing was compared: debug\_edge\_case.py: module-level code that computes a value changed (line 8, 19, 20); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `none_found`, 15.21 s: no counterexample found in 882 inputs against 8 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.03 s: no candidate was confirmed (8 reported)
- `blind`: `reproduced`, 11.5 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### Break My Fix targets
- `mqtt_exporter.main._normalize_name_in_topic_msg` (`mqtt_exporter/main.py`): 882 inputs
#### More changes no test noticed
- `debug_edge_case.py:19`: `if __name__ == "__main__":` → `if __name__ != "__main__":` made no test fail; not compared with the fix (`m-c65ccef7769b`)
- `mqtt_exporter/main.py:171`: `         if len(info) >= 5 and info[0] == "shellies" and info... ` → `         if len(info) >= 5 or info[0] == "shellies" and info[... ` made no test fail; not compared with the fix (`m-bd71839c49df`)
- `final_verification.py:86`: `         if all(count == 6 for count in phase_metrics):  # 6 ... ` → `         if not (all(count == 6 for count in phase_metrics)):... ` made no test fail; not compared with the fix (`m-9f701b8cdf11`)
- `final_verification.py:47`: `         metric_name = topic.split('/')[-1] ` → `         metric_name = topic.split('/')[-0] ` made no test fail; not compared with the fix (`m-e305373f9143`)
- `final_verification.py:47`: `         metric_name = topic.split('/')[-1] ` → `         metric_name = topic.split('/')[+1] ` made no test fail; not compared with the fix (`m-ca5102d1d5cc`)
- `final_verification.py:52`: `         if parsed_topic not in results: ` → `         if parsed_topic in results: ` made no test fail; not compared with the fix (`m-6b587546d66b`)
- `debug_edge_case.py:8`: `logging.basicConfig(level=logging.DEBUG)` → `pass` made no test fail; not compared with the fix (`m-e53b3119a402`)
- `final_verification.py:9`: `     print("Testing exact Shelly 3EM scenario from issue desc... ` → `     return None ` made no test fail; not compared with the fix (`m-e7ade1299659`)
- `final_verification.py:78`: `     if total_metrics == len(topics_from_issue): ` → `     if total_metrics != len(topics_from_issue): ` made no test fail; not compared with the fix (`m-4ce878914da5`)
#### Fix lines run (report only)
- repro: 3 of 96 fix lines run
- pr\_test: 5 of 96 fix lines run
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
- Break My Fix could not attack debug\_shelly\_relay: it takes no parameters to vary
- Break My Fix could not attack test\_exact\_issue\_scenario: it takes no parameters to vary
- Break My Fix could not attack test\_shelly\_3em\_issue: it takes no parameters to vary
- the behaviour diff could not compare debug\_shelly\_relay: new with the fix: nothing to compare
- the behaviour diff could not compare test\_exact\_issue\_scenario: new with the fix: nothing to compare
- the behaviour diff could not compare test\_shelly\_3em\_issue: new with the fix: nothing to compare
#### Notes
- guard: 5 of the 9 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 89 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.16: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T17:12:51+00:00, issue sha256 `30d313b29c762ef5dfe77bb749b6a9c32038847e555576df2c995ada678eaade`

</details>
