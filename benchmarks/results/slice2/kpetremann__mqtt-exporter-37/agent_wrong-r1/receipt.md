## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug and the fix guards it with no regressions found, but Break My Fix found a counterexample: \_normalize\_name\_in\_topic\_msg(topic='shellies/shelly/emeter/0/power', payload='123.45') returns ('shellies/shelly', {'power': '123.45'}), dropping the emeter index so the three phases are still not distinguished. Look next at how the Shelly emeter/&lt;n&gt;/&lt;metric&gt; topic is normaliz…

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
| `guard` | `guarded` | kill rate 0\.8, mutants 5, killed 4, survived 1 |
| `regressions` | `none_found` | compared 10, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 9 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 1, inputs tried 380, properties counted 7, findings 1 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 4; the rest in receipt.json)
- `mqtt_exporter/main.py:172`: `         if (len(info) >= 5 and  ` → `         if (len(info) >= 4 and  ` made no test fail; not compared with the fix (`m-a382e4d88f5c`)
- `mqtt_exporter/main.py:172`: `         if (len(info) >= 5 and  ` → `         if (len(info) >= 4 and  ` made no test fail; not compared with the fix (`m-a382e4d88f5c`)
- `mqtt_exporter/main.py:172`: `         if (len(info) >= 5 and  ` → `         if (len(info) >= 5 or  ` made no test fail; not compared with the fix (`m-944137fc949f`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 5 calls, 23,240 input and 5,421 output tokens, cost $0.1816 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 3.62 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 6.65 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 23.64 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `guarded`, 100.96 s: the reproduction test fails with the fix reverted, and the tests killed 4 of 5 mutants
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 3.0 s: none of the 10 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.45 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 3.42 s: nothing was compared: \_normalize\_name\_in\_topic\_msg: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `found`, 66.58 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.02 s: no candidate was confirmed (2 reported)
#### Break My Fix targets
- `mqtt_exporter.main._normalize_name_in_topic_msg` (`mqtt_exporter/main.py`): 380 inputs
#### More changes no test noticed
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
- guard: only the first 10 of 24 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.16: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T17:02:51+00:00, issue sha256 `30d313b29c762ef5dfe77bb749b6a9c32038847e555576df2c995ada678eaade`

</details>
