## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproducing the empty-list prefetch\_perms error failed before the fix and passed after it, with no regressions or breaking inputs found, but the tests did not kill enough mutants to show they guard the fix (the behaviour diff was also inconclusive). Next, strengthen the tests so they would fail if the change to \_get\_pks\_model\_and\_ctype were altered or reverted, for example by asserting the…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 4 mutants; 80% is needed

**Issue:** Using prefetch\_permissions with an empty list throws an error · **Repo:** testbed · **Base** `tf-base` (`d9f15f2`) → **head** `tf-gold` (`522666e`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.5, mutants 4, killed 2, survived 2 |
| `regressions` | `none_found` | compared 255, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 3 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 4, properties counted 5, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `guardian/core.py:22`: `     pks = None ` → `     pks = [0] ` made no test fail; not compared with the fix (`m-822907200fe2`)
- `guardian/core.py:22`: `     pks = None ` → `     pks = objects ` made no test fail; not compared with the fix (`m-45a258134355`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 17,742 input and 2,764 output tokens, cost $0.1047 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 57.95 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 18.58 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_imports.py`
- `reproduce`: `reproduced`, 56.48 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no guardian/testapp/tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 269.83 s: the tests killed 2 of 4 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no guardian/testapp/tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 59.09 s: none of the 255 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 10.82 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no guardian/testapp/tests/test_tracefix_repro.py`
- `behaviour_diff`: `inconclusive`, 21.73 s: nothing was compared: \_get\_pks\_model\_and\_ctype: the comparison did not finish
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no guardian/testapp/tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s test_tracefix_diff.py`
- `break_my_fix`: `none_found`, 37.95 s: no counterexample found in 4 inputs against 5 properties
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_attack.py`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Fix lines run (report only)
- repro: 3 of 3 fix lines run
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
- reproduce: pyproject truncated to 3000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T17:57:47+00:00, issue sha256 `947548f69073e3722753dd46a22da30126d44c70de0594620e88a179400e4db6`

</details>
