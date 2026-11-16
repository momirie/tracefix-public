## Fix Receipt: L0 (no evidence for this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier could not reproduce the wildcard search bug (e.g. \`author:german\*\`): the test passes on the code before the fix, so this run gives no evidence that the change fixes anything, though no regressions were found and the fix lines were covered.

**Why this level:** not L1: no attempt reproduced the bug; last: the test passes on the code before the fix

**Issue:** Logical field wildcard serarch bugfix · **Repo:** testbed · **Base** `tf-base` (`b367c10`) → **head** `tf-gold` (`ea5a279`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `not_reproduced` | attempts 3 |
| `guard` | `skipped` | mutants 0, killed 0, survived 0 |
| `regressions` | `none_found` | compared 76, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 3 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; guard: skipped (there is no reproduction test to judge the tests with (not\_reproduced)); behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Query.from\_string.process\_string: a nested function: it can't be imported, not attacked yet; WildcardRegex.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)); break\_my\_fix: skipped (the fix changes no function Break My Fix can call (Query.from\_string.process\_string: a nested function: it can't be imported, not attacked yet; WildcardRegex.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)); Break My Fix could not attack Query.from\_string.process\_string: a nested function: it can't be imported, not attacked yet; and 4 more in receipt.json
- **Model use:** 4 calls, 20,821 input and 2,011 output tokens, cost $0.0653 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 8.0 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.51 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `not_reproduced`, 57.35 s: no attempt reproduced the bug; last: the test passes on the code before the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `skipped`, 0.0 s: there is no reproduction test to judge the tests with (not\_reproduced)
- `regressions`: `none_found`, 8.62 s: none of the 76 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 0.06 s: report only: which fix lines the tests run
- `behaviour_diff`: `skipped`, 0.1 s: the fix changes no function the behaviour diff can call (Query.from\_string.process\_string: a nested function: it can't be imported, not attacked yet; WildcardRegex.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
- `break_my_fix`: `skipped`, 0.05 s: the fix changes no function Break My Fix can call (Query.from\_string.process\_string: a nested function: it can't be imported, not attacked yet; WildcardRegex.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
- `integrity`: `clean`, 0.03 s: nothing suspicious in the fix's test or source changes
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Query.from\_string.process\_string: a nested function: it can't be imported, not attacked yet; WildcardRegex.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet))
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call (Query.from\_string.process\_string: a nested function: it can't be imported, not attacked yet; WildcardRegex.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet))
- Break My Fix could not attack Query.from\_string.process\_string: a nested function: it can't be imported, not attacked yet
- Break My Fix could not attack WildcardRegex.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Query.from\_string.process\_string: a nested function: it can't be imported, not attacked yet
- the behaviour diff could not compare WildcardRegex.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
#### Notes
- reproduce: only the first 8 of 19 functions were shown
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T16:26:23+00:00, issue sha256 `7e63a63ac7f1d161f8e28f907e70b559b1f82e93483f3f082a1fe393a25ebda7`

</details>
