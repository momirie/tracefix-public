## Fix Receipt: L2 (L1, and the tests notice the fix being undone)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproduced the missing Bot repr (failing before the fix, passing after) and fails again when the fix is reverted or broken, with no regressions found; Bot.\_\_repr\_\_ was not compared against the old behaviour because the special method was not called in that stage. Next, check by hand that the new repr output matches the format the issue asks for (bot name, team side, position, turn and roun…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; the tests guard the fix: they fail when it is reverted or broken; not L3: Bot.\_\_repr\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet); not L3: no changed function was compared

**Issue:** Better Bot repr · **Repo:** testbed · **Base** `tf-base` (`ab9217f`) → **head** `tf-gold` (`3a2d8a0`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 1\.0, mutants 5, killed 5, survived 0 |
| `regressions` | `none_found` | compared 1710, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 2 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Bot.\_\_repr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)); break\_my\_fix: skipped (the fix changes no function Break My Fix can call (Bot.\_\_repr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)); Break My Fix could not attack Bot.\_\_repr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; the behaviour diff could not compare Bot.\_\_repr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; and 1 more in receipt.json
- **Model use:** 3 calls, 8,180 input and 1,690 output tokens, cost $0.0383 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 110.14 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.21 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_imports.py`
- `reproduce`: `reproduced`, 30.03 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no contrib/test_tracefix_repro.py`
- `guard`: `guarded`, 32.84 s: the reproduction test fails with the fix reverted, and the tests killed 5 of 5 mutants
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no contrib/test_tracefix_repro.py`
- `regressions`: `none_found`, 110.84 s: none of the 1710 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 2.73 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no contrib/test_tracefix_repro.py`
- `behaviour_diff`: `skipped`, 0.15 s: the fix changes no function the behaviour diff can call (Bot.\_\_repr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
- `break_my_fix`: `skipped`, 0.01 s: the fix changes no function Break My Fix can call (Bot.\_\_repr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Fix lines run (report only)
- repro: 2 of 2 fix lines run
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Bot.\_\_repr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet))
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call (Bot.\_\_repr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet))
- Break My Fix could not attack Bot.\_\_repr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Bot.\_\_repr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-20T11:58:50+00:00, issue sha256 `70b628a034861d96787844c44db748628cd5941a9ecd7f66a4a05139a94e6b1a`

</details>
