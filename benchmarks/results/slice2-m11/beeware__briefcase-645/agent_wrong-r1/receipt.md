## Fix Receipt: L2 (L1, and the tests notice the fix being undone)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): At L2, a test reproduced the leftover app\_packages artefacts (it failed before the fix and passed after), and the tests fail again when the fix is reverted or broken, with no regressions found. Behaviour comparison was skipped because UpdateCommand.install\_app\_dependencies is new, and Break My Fix was inconclusive, so a reviewer should check by hand that clearing app\_packages before reinstalling…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; the tests guard the fix: they fail when it is reverted or broken; not L3: UpdateCommand.install\_app\_dependencies: before the fix it was not a method defined in class UpdateCommand; not L3: no changed function was compared

**Issue:** Remove previous install artefacts when updating app\_packages · **Repo:** testbed · **Base** `tf-base` (`0b204c0`) → **head** `tf-agent_wrong` (`8804aa4`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `guarded` | kill rate 0\.833, mutants 6, killed 5, survived 1 |
| `regressions` | `none_found` | compared 805, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 11 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 1, inputs tried 0, properties counted 2, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_on_head` | attempts 2, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; negate\_if: 2 of 2 killed; drop\_call: 2 of 4 killed; no place for compare, logic, constant, arithmetic, membership, loop, reraise

### Changes no test noticed
- `src/briefcase/commands/update.py:46`: `         super().install_app_dependencies(app) ` → `         return None ` made no test fail; not compared with the fix (`m-09e903076ca8`)
- `src/briefcase/commands/update.py:37`: `             print('[{app.app_name}] Removing old dependencie... ` → `             pass ` made no test fail; not compared with the fix (`m-0b99069e058f`)
- `src/briefcase/commands/update.py:46`: `         super().install_app_dependencies(app) ` → `         pass ` made no test fail; not compared with the fix (`m-5225b1848362`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call); 9 things the behaviour diff can't observe (run log)
- **Model use:** 10 calls, 37,750 input and 6,284 output tokens, cost $0.1945 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 5.4 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.83 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 29.0 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `guarded`, 75.97 s: the reproduction test fails with the fix reverted, and the tests killed 5 of 6 mutants
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 6.04 s: none of the 805 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.65 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `skipped`, 0.42 s: the fix changes no function the behaviour diff can call
- `break_my_fix`: `inconclusive`, 2.81 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_on_head`, 25.22 s: attempt 2: fails the same way before and after the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### Break My Fix targets
- `briefcase.commands.update.UpdateCommand.install_app_dependencies` (`src/briefcase/commands/update.py`): 0 inputs (nothing was judged, and 4 object(s) of UpdateCommand could not be built here (no object from UpdateCommand(): TypeError: Can't instantiate abstract class UpdateCommand with abstract methods binary\_path, distribution\_path))
#### Fix lines run (report only)
- repro: 11 of 11 fix lines run
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call)
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T23:45:30+00:00, issue sha256 `ba245583053c57f35fabfd90dacdda8ce774b35514bbed7b359f5fba2e9a2cb2`

</details>
