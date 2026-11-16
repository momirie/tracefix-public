## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier's runs found five existing tests that passed before the fix and fail after it (three in tests/commands/create/test\_install\_app\_dependencies.py and two in tests/platforms/linux/appimage/test\_create.py), and it could not reproduce the original lingering-artefacts bug. Look first at why those install\_app\_dependencies tests now fail, for example whether the new clearing of app\_packages c…

**Why this level:** regression: tests/commands/create/test\_install\_app\_dependencies.py::test\_valid\_requires passed before the fix and fails after it; regression: tests/commands/create/test\_install\_app\_dependencies.py::test\_invalid\_requires passed before the fix and fails after it; regression: tests/commands/create/test\_install\_app\_dependencies.py::test\_offline passed before the fix and fails after it; regression: tests/platforms/linux/appimage/test\_create.py::test\_install\_app\_dependencies passed before the fix and fails after it; regression: tests/platforms/linux/appimage/test\_create.py::test\_install\_app\_dependencies\_no\_docker passed before the fix and fails after it

**Issue:** Remove previous install artefacts when updating app\_packages · **Repo:** testbed · **Base** `tf-base` (`0b204c0`) → **head** `tf-v1` (`df93982`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. Regression: `tests/commands/create/test_install_app_dependencies.py::test_valid_requires` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'target' is not defined)
2. Regression: `tests/commands/create/test_install_app_dependencies.py::test_invalid_requires` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'target' is not defined)
3. Regression: `tests/commands/create/test_install_app_dependencies.py::test_offline` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'target' is not defined)
4. Regression: `tests/platforms/linux/appimage/test_create.py::test_install_app_dependencies` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'target' is not defined)
5. Regression: `tests/platforms/linux/appimage/test_create.py::test_install_app_dependencies_no_docker` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'target' is not defined)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `not_reproduced` | attempts 3 |
| `guard` | `skipped` | mutants 0, killed 0, survived 0 |
| `regressions` | `found` | compared 805, regressions 5, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 1 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 2, inputs tried 0, properties counted 3, findings 0 |
| `integrity` | `clean` | flags 0 |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; guard: skipped (there is no reproduction test to judge the tests with (not\_reproduced)); 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 42,368 input and 5,292 output tokens, cost $0.2137 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 5.12 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.38 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `not_reproduced`, 33.48 s: no attempt reproduced the bug; last: the test uses names it must not use: \_\_import\_\_
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `skipped`, 0.0 s: there is no reproduction test to judge the tests with (not\_reproduced)
- `regressions`: `found`, 25.88 s: 5 confirmed: tests/commands/create/test\_install\_app\_dependencies.py::test\_valid\_requires, tests/commands/create/test\_install\_app\_dependencies.py::test\_invalid\_requires, tests/commands/create/test\_install\_app\_dependencies.py::test\_offline, tests/platforms/linux/appimage/test\_create.py::test\_install\_app\_dependencies, tests/platforms/linux/appimage/test\_create.py::test\_install\_app\_dependencies\_no\_docker
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 0.01 s: report only: which fix lines the tests run
- `behaviour_diff`: `inconclusive`, 2.75 s: nothing was compared: CreateCommand.install\_app\_support\_package: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 33.3 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `briefcase.commands.create.CreateCommand.install_app_support_package` (`src/briefcase/commands/create.py`): 0 inputs
- `briefcase.commands.create.CreateCommand.install_app_dependencies` (`src/briefcase/commands/create.py`): 0 inputs
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
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T22:14:49+00:00, issue sha256 `ba245583053c57f35fabfd90dacdda8ce774b35514bbed7b359f5fba2e9a2cb2`

</details>
