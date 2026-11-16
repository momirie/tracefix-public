## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A Break My Fix input made the fixed StatelessServer.get\_or\_create\_application\_instance raise NameError because 'guarantee\_single\_callable' is not defined, and the original bug was not reproduced, so the evidence shows a concrete break rather than a demonstrated fix. Next, check that guarantee\_single\_callable is imported in asgiref/server.py and re-run the pipeline so the reproduce stage can actua…

**Why this level:** Break My Fix finding 1: an input that breaks asgiref.server.StatelessServer.get\_or\_create\_application\_instance

**Issue:** Has StatelessServer been updated to the ASGI 3.0 spec? · **Repo:** testbed · **Base** `tf-base` (`251e983`) → **head** `tf-v0` (`404d26f`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `get_or_create_application_instance(self='StatelessServer(Sta...` → `raises NameError: name 'guarantee_single_callable' is not de...` (before the fix: `raises TypeError: __init__() got an unexpected keyword argum...`); breaks **max\_applications\_respected**: “reclaimed and shut down to make space” (docstring); 3 more inputs break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `not_reproduced` | attempts 3 |
| `guard` | `skipped` | mutants 0, killed 0, survived 0 |
| `regressions` | `none_found` | compared 45, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 2 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 1, inputs tried 5, properties counted 8, findings 1 |
| `integrity` | `clean` | flags 0 |
| `blind` | `not_run` | attempts 0, report only True |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; guard: skipped (there is no reproduction test to judge the tests with (not\_reproduced)); 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 38,966 input and 9,279 output tokens, cost $0.2853 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 9.66 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.47 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `not_reproduced`, 42.0 s: no attempt reproduced the bug; last: fails after the fix too, but differently
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `skipped`, 0.0 s: there is no reproduction test to judge the tests with (not\_reproduced)
- `regressions`: `none_found`, 9.62 s: none of the 45 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 0.0 s: report only: which fix lines the tests run
- `behaviour_diff`: `inconclusive`, 2.31 s: nothing was compared: StatelessServer.get\_or\_create\_application\_instance: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `found`, 41.97 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
- `blind`: `not_run`, 0.0 s: the main test did not reproduce the bug
#### Break My Fix targets
- `asgiref.server.StatelessServer.get_or_create_application_instance` (`asgiref/server.py`): 5 inputs
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
- guard: skipped (there is no reproduction test to judge the tests with (not\_reproduced))
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T17:01:19+00:00, issue sha256 `eceb67c997473478a8b3640c9ca6db91fc5c5bbbff0836962ba4430535cc8d8c`

</details>
