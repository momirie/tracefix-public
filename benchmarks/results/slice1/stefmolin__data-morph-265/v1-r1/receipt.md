## Fix Receipt: L0 (no evidence for this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The evidence stays at L0 because the repro test test\_figure\_eight\_orientation failed with an AttributeError before the fix, so it never reached the orientation behaviour and only showed that the new figure-eight shape did not exist yet; no regressions were found and the fix lines were covered. Next, look at a repro that runs against the pre-fix code without depending on new attributes, or at a di…

**Why this level:** not L1: no attempt reproduced the bug; last: tests.test\_tracefix\_repro::test\_figure\_eight\_orientation fails with AttributeError before the fix, which usually means it uses something that only exists after the fix

**Issue:** Add figure eight target shape · **Repo:** testbed · **Base** `tf-base` (`9391f31`) → **head** `tf-v1` (`23bf1f9`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `not_reproduced` | attempts 3 |
| `guard` | `skipped` | mutants 0, killed 0, survived 0 |
| `regressions` | `none_found` | compared 345, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 19 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; guard: skipped (there is no reproduction test to judge the tests with (not\_reproduced)); behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)); break\_my\_fix: skipped (the fix changes no function Break My Fix can call (FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)); Break My Fix could not attack FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; and 2 more in receipt.json
- **Model use:** 4 calls, 24,301 input and 2,497 output tokens, cost $0.0774 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 17.3 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 8.15 s: 3 changed module(s) imported from the copies (5 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `not_reproduced`, 67.29 s: no attempt reproduced the bug; last: tests.test\_tracefix\_repro::test\_figure\_eight\_orientation fails with AttributeError before the fix, which usually means it uses something that only exists after the fix
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `skipped`, 0.0 s: there is no reproduction test to judge the tests with (not\_reproduced)
- `regressions`: `none_found`, 17.09 s: none of the 345 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 0.01 s: report only: which fix lines the tests run
- `behaviour_diff`: `skipped`, 0.14 s: the fix changes no function the behaviour diff can call (FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
- `break_my_fix`: `skipped`, 0.01 s: the fix changes no function Break My Fix can call (FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet))
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call (FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet))
- Break My Fix could not attack FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare FigureEight.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
#### Notes
- reproduce: only the first 8 of 22 functions were shown
- reproduce: pyproject truncated to 3000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-15T16:40:25+00:00, issue sha256 `1aeefc46e723d1ac2f518647b871390362036d19909f7d319e4bc57d2508bf8c`

</details>
