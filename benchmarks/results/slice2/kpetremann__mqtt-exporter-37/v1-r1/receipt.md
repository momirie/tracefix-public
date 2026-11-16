## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier found that the fixed \_normalize\_name\_in\_topic\_msg raises AttributeError on a plain Shelly-style topic ('shellies/room/sensor/temperature') because mqtt\_exporter.settings has no KEEP\_FULL\_TOPIC attribute, and two existing tests (test\_\_parse\_message\_\_shelly\_style and test\_\_parse\_message\_\_generic\_single\_value\_style) passed before the fix and fail after it. Look first at the missing KEEP…

**Why this level:** Break My Fix finding 1: an input that breaks mqtt\_exporter.main.\_normalize\_name\_in\_topic\_msg; regression: tests/functional/test\_parse\_message.py::test\_\_parse\_message\_\_shelly\_style passed before the fix and fails after it; regression: tests/functional/test\_parse\_message.py::test\_\_parse\_message\_\_generic\_single\_value\_style passed before the fix and fails after it

**Issue:** Doesn't support Shelly 3EM format very well · **Repo:** testbed · **Base** `tf-base` (`4126ec6`) → **head** `tf-v1` (`e72a7e2`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `_normalize_name_in_topic_msg(topic='shellies/room/sensor/tem...` → `raises AttributeError: module 'mqtt_exporter.settings' has n...` (before the fix: `returns ('shellies/room', {'temperature': '20.00'})`); breaks **last\_topic\_item\_is\_metric\_name**: “only support when the last item in the topic is the actual metric name” (docstring); 2 more inputs break it the same way; test: `findings/finding_1.py`
2. Regression: `tests/functional/test_parse_message.py::test__parse_message__shelly_style` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: module 'mqtt\_exporter.settings' has no attribute 'KEEP\_FULL\_TOPIC')
3. Regression: `tests/functional/test_parse_message.py::test__parse_message__generic_single_value_style` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: module 'mqtt\_exporter.settings' has no attribute 'KEEP\_FULL\_TOPIC')

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.667, mutants 6, killed 4, survived 2 |
| `regressions` | `found` | compared 10, regressions 2, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 3 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 1, inputs tried 10, properties counted 7, findings 1 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `mqtt_exporter/main.py:166`: `             topic = "/".join(info[:-1]).lower() ` → `             topic = "/".join(info[:-1]) ` made no test fail; not compared with the fix (`m-f804726069eb`)
- `mqtt_exporter/main.py:168`: `             topic = f"{info[0]}/{info[1]}".lower() ` → `             topic = f"{info[0]}/{info[1]}" ` made no test fail; not compared with the fix (`m-edbefdad418c`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 29,523 input and 4,939 output tokens, cost $0.1973 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 4.34 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 7.29 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 27.12 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 81.91 s: the tests killed 4 of 6 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 21.85 s: 2 confirmed: tests/functional/test\_parse\_message.py::test\_\_parse\_message\_\_shelly\_style, tests/functional/test\_parse\_message.py::test\_\_parse\_message\_\_generic\_single\_value\_style
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.83 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 3.47 s: nothing was compared: \_normalize\_name\_in\_topic\_msg: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `found`, 55.86 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `mqtt_exporter.main._normalize_name_in_topic_msg` (`mqtt_exporter/main.py`): 10 inputs
#### Fix lines run (report only)
- repro: 2 of 3 fix lines run
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
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.16: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T16:59:07+00:00, issue sha256 `30d313b29c762ef5dfe77bb749b6a9c32038847e555576df2c995ada678eaade`

</details>
