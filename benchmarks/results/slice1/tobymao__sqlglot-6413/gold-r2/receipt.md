## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The evidence reached L1: a test reproducing the DuckDB CTE-followed-by-PIVOT parse error fails before the fix and passes after it, no regressions or breaking inputs were found, and integrity was clean. It did not reach L2 because the guard stage was not satisfied by the mutation results, and the behaviour diff was inconclusive, so the next thing to check is whether the tests actually pin down the…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 5 of 7 mutants; 80% is needed

**Issue:** DuckDB dialect parse error: \`CTE PIVOT\` · **Repo:** testbed · **Base** `tf-base` (`b796783`) → **head** `tf-gold` (`a50a988`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.714, mutants 7, killed 5, survived 2 |
| `regressions` | `none_found` | compared 931, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 11 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 2, properties counted 7, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `sqlglot/generator.py:2186`: `                 sql = f"{direction} {this}{on}{into}{using}{... ` → `                 sql = f"{direction} {this}{on}{using}{into}{... ` made no test fail; not compared with the fix (`m-5e50571aa4dc`)
- `sqlglot/generator.py:2211`: `         return self.prepend_ctes(expression, sql) ` → `         return sql ` made no test fail; not compared with the fix (`m-80471c4097be`)
- `sqlglot/generator.py:2184`: `                 using = self.expressions(expression, key="us... ` → `                 using = self.expressions(expression, key="us... ` made no test fail; not compared with the fix (`m-98d33a95fc20`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 5 calls, 28,545 input and 3,962 output tokens, cost $0.1722 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 44.4 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.83 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 16.46 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 492.26 s: the tests killed 5 of 7 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 46.41 s: none of the 931 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 2.2 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `inconclusive`, 7.54 s: nothing was compared: sqlglot/expressions.py: module-level code that computes a value changed (line 4546); what uses it is not compared
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `none_found`, 40.39 s: no counterexample found in 2 inputs against 7 properties
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
- `integrity`: `clean`, 0.39 s: nothing suspicious in the fix's test or source changes
#### Fix lines run (report only)
- repro: 8 of 11 fix lines run
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
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-20T08:54:30+00:00, issue sha256 `e85675ec8655f07ea050a8aa7bba8079e5c72d86d5d3639c5f6efeed2a3aff4a`

</details>
