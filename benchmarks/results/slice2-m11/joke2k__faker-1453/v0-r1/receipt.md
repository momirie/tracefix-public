## Fix Receipt: L0 (no evidence for this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier could not reproduce the RecursionError on the unfixed code, and its last attempt failed after the fix as well but in a different way, so these runs give no evidence that this change addresses the reported deepcopy recursion; no regressions were found, the fixed lines were covered, and no integrity flags were raised. The next thing to look at is a working reproduction (for example, de…

**Why this level:** not L1: no attempt reproduced the bug; last: fails after the fix too, but differently

**Issue:** Raises RecursionError under certain conditions · **Repo:** testbed · **Base** `tf-base` (`ca43530`) → **head** `tf-v0` (`d7ac64e`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `not_reproduced` | attempts 3 |
| `guard` | `skipped` | mutants 0, killed 0, survived 0 |
| `regressions` | `none_found` | compared 171, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 13 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `not_run` | attempts 0, report only True |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; guard: skipped (there is no reproduction test to judge the tests with (not\_reproduced)); behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Faker.\_\_deepcopy\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)); break\_my\_fix: skipped (the fix changes no function Break My Fix can call (Faker.\_\_deepcopy\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)); Break My Fix could not attack Faker.\_\_deepcopy\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; and 4 more in receipt.json
- **Model use:** 4 calls, 25,505 input and 1,632 output tokens, cost $0.0740 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 11.9 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.03 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `not_reproduced`, 35.44 s: no attempt reproduced the bug; last: fails after the fix too, but differently
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `skipped`, 0.0 s: there is no reproduction test to judge the tests with (not\_reproduced)
- `regressions`: `none_found`, 44.44 s: none of the 171 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 0.01 s: report only: which fix lines the tests run
- `behaviour_diff`: `skipped`, 0.24 s: the fix changes no function the behaviour diff can call (Faker.\_\_deepcopy\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
- `break_my_fix`: `skipped`, 0.01 s: the fix changes no function Break My Fix can call (Faker.\_\_deepcopy\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
- `integrity`: `clean`, 0.04 s: nothing suspicious in the fix's test or source changes
- `blind`: `not_run`, 0.0 s: the main test did not reproduce the bug
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Faker.\_\_deepcopy\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet))
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call (Faker.\_\_deepcopy\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet))
- Break My Fix could not attack Faker.\_\_deepcopy\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Faker.\_\_deepcopy\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Faker.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T21:43:13+00:00, issue sha256 `69a4bfe759ee3d30453f6db223eea3c294f94b6edc55b2a03b164f3d8a33a409`

</details>
