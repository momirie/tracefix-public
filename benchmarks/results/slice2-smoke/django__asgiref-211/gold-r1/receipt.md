## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproduced the bug (StatelessServer calling the application in the old two-step ASGI 2 style) by failing before the fix and passing after it, with no regressions found and the changed lines covered, but the guard stage reported the fix as not guarded and the mutation, behaviour-diff and break-my-fix checks did not add further evidence. The most important next step is to strengthen the test…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 3 of 4 mutants; 80% is needed

**Issue:** Has StatelessServer been updated to the ASGI 3.0 spec? · **Repo:** testbed · **Base** `tf-base` (`251e983`) → **head** `tf-gold` (`2b6f2dd`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.75, mutants 4, killed 3, survived 1 |
| `regressions` | `none_found` | compared 45, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 3 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `asgiref/server.py:89`: `         application_instance = guarantee_single_callable(sel... ` → `         application_instance = self.application ` made no test fail; not compared with the fix (`m-3135ec81e686`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 4 calls, 7,804 input and 1,355 output tokens, cost $0.0337 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 9.87 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.23 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 19.74 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 49.73 s: the tests killed 3 of 4 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 9.66 s: none of the 45 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 0.0 s: report only: which fix lines the tests run
- `behaviour_diff`: `inconclusive`, 0.01 s: the behaviour diff can't run in the project's Python: the project's Python has Hypothesis 6.119.3, older than 6.141, the oldest Tracefix is tested with: upgrade it there (python -m pip install -U hypothesis)
- `break_my_fix`: `inconclusive`, 0.01 s: Break My Fix can't run in the project's Python: the project's Python has Hypothesis 6.119.3, older than 6.141, the oldest Tracefix is tested with: upgrade it there (python -m pip install -U hypothesis)
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Fix lines run (report only)
- not measured: the project's Python has Hypothesis 6.119.3, older than 6.141, the oldest Tracefix is tested with: upgrade it there (python -m pip install -U hypothesis)
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
- fix\_line\_coverage: not measured: the project's Python has Hypothesis 6.119.3, older than 6.141, the oldest Tracefix is tested with: upgrade it there (python -m pip install -U hypothesis)
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T10:27:37+00:00, issue sha256 `eceb67c997473478a8b3640c9ca6db91fc5c5bbbff0836962ba4430535cc8d8c`

</details>
