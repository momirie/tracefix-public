## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the issue, but Break My Fix found an input the fixed code still mishandles: \_normalize\_name\_in\_topic\_msg(topic='shellies/shelly/emeter/0/power', payload='123.45') returns ('shellies/shelly', {'power': '123.45'}), which drops the emeter index so the three phases still collapse into one metric. Look at how the fix handles Shelly 3EM topics like this one, and note that no tes…

**Why this level:** Break My Fix finding 1: an input that breaks mqtt\_exporter.main.\_normalize\_name\_in\_topic\_msg

**Issue:** Doesn't support Shelly 3EM format very well · **Repo:** testbed · **Base** `tf-base` (`4126ec6`) → **head** `tf-agent_wrong` (`76d4b3f`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `_normalize_name_in_topic_msg(topic='shellies/shelly/emeter/0...` → `returns ('shellies/shelly', {'power': '123.45'})` (before the fix: `returns ('shellies/shelly', {'power': '123.45'})`); breaks **emeter\_phases\_differentiated**: “there's no way to either sum, or differentiate the three phases' measurements” (issue); 1 more input break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.714, mutants 7, killed 5, survived 2 |
| `regressions` | `none_found` | compared 10, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 9 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 1, inputs tried 380, properties counted 7, findings 1 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; compare: 3 of 3 killed; logic: 0 of 2 killed; constant: 1 of 2 killed; arithmetic: 2 of 2 killed; no place for negate\_if, membership, loop, drop\_call, reraise

### Changes no test noticed (3 of 5; the rest in receipt.json)
- `mqtt_exporter/main.py:172`: `         if (len(info) >= 5 and  ` → `         if (len(info) >= 4 and  ` made no test fail; not compared with the fix (`m-a382e4d88f5c`)
- `mqtt_exporter/main.py:178`: `             topic = f"{info[0]}/{info[1]}/{info[2]}/{info[3]... ` → `             topic = f"{info[0]}/{info[1]}/{info[3]}/{info[2]... ` made no test fail; not compared with the fix (`m-cdaa493ce070`)
- `mqtt_exporter/main.py:172`: `         if (len(info) >= 5 and  ` → `         if (len(info) >= 5 or  ` made no test fail; not compared with the fix (`m-944137fc949f`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 25,867 input and 6,002 output tokens, cost $0.1925 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 1.92 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.71 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 11.28 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 75.64 s: the tests killed 5 of 7 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 2.0 s: none of the 10 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.29 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 2.2 s: nothing was compared: \_normalize\_name\_in\_topic\_msg: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `found`, 16.96 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.01 s: no candidate was confirmed (2 reported)
- `blind`: `reproduced`, 11.45 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### Break My Fix targets
- `mqtt_exporter.main._normalize_name_in_topic_msg` (`mqtt_exporter/main.py`): 380 inputs
#### More changes no test noticed
- `mqtt_exporter/main.py:172`: `         if (len(info) >= 5 and  ` → `         if (len(info) >= 4 and  ` made no test fail; not compared with the fix (`m-a382e4d88f5c`)
- `mqtt_exporter/main.py:173`: `             info[0].lower() == "shellies" and  ` → `             info[0].lower() == "shellies" or  ` made no test fail; not compared with the fix (`m-92a2fafd07f8`)
#### Fix lines run (report only)
- repro: 7 of 9 fix lines run
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
- guard: 1 of the 8 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 24 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.16: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T17:10:33+00:00, issue sha256 `30d313b29c762ef5dfe77bb749b6a9c32038847e555576df2c995ada678eaade`

</details>
