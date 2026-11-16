## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproduced the nested-output bug for inline \`\$\$x\$\$\` before the fix and passed after it, no regressions were found, and the changed lines were covered, but the guard stage reported the fix as not guarded and the tests did not kill enough mutants to reach L2. Next, strengthen the tests so they catch mutations of the fix, for example by asserting the exact single-span output for inline \`\$\$x\$\$…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 3 of 5 mutants; 80% is needed

**Issue:** inline \`\$\$x\$\$\` math matches 2 times and returns nested mathjax · **Repo:** testbed · **Base** `tf-base` (`6ed9a36`) → **head** `tf-gold` (`b03abe9`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.6, mutants 5, killed 3, survived 2 |
| `regressions` | `none_found` | compared 702, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 4 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 7; the rest in receipt.json)
- `pymdownx/arithmatex.py:55`: `(?<!\\)(\$)((?:\\.|[^\\$\x02\x03])+?)(?:\$))'` → `(?<!\\)(\$)((?:\\.|[^\\$\x02\x03])*?)(?:\$))'` made no test fail; not compared with the fix (`m-2c2faa7479d7`)
- `pymdownx/arithmatex.py:56`: `((?:\\[^)]|[^\\\x02\x03])+?)` → `((?:\\[^)]|[^\\])+?)` made no test fail; not compared with the fix (`m-796a9e365e32`)
- `pymdownx/__meta__.py:196`: `__version_info__ = Version(10, 19, 1, "final")` → `__version_info__ = Version(11, 19, 1, "final")` made no test fail; not compared with the fix (`m-81b2f0957ea2`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call); break\_my\_fix: skipped (the fix changes no function Break My Fix can call); 9 things the behaviour diff can't observe (run log)
- **Model use:** 3 calls, 6,968 input and 1,088 output tokens, cost $0.0292 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 7.21 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 6.51 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 21.07 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 197.11 s: the tests killed 3 of 5 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 7.55 s: none of the 702 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 4.65 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `skipped`, 0.15 s: the fix changes no function the behaviour diff can call
- `break_my_fix`: `skipped`, 0.01 s: the fix changes no function Break My Fix can call
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
#### More changes no test noticed
- `pymdownx/__meta__.py:196`: `__version_info__ = Version(10, 19, 1, "final")` → `__version_info__ = Version(9, 19, 1, "final")` made no test fail; not compared with the fix (`m-139b139367ff`)
- `pymdownx/__meta__.py:196`: `__version_info__ = Version(10, 19, 1, "final")` → `__version_info__ = Version(10, 18, 1, "final")` made no test fail; not compared with the fix (`m-e5b7bb7d816e`)
- `pymdownx/__meta__.py:196`: `__version_info__ = Version(10, 19, 1, "final")` → `__version_info__ = Version(10, 20, 1, "final")` made no test fail; not compared with the fix (`m-30093cbc9718`)
- `pymdownx/__meta__.py:196`: `__version_info__ = Version(10, 19, 1, "final")` → `__version_info__ = Version(10, 19, 2, "final")` made no test fail; not compared with the fix (`m-14debaa7db47`)
#### Fix lines run (report only)
- repro: 4 of 4 fix lines run
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
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call)
#### Notes
- reproduce: pyproject truncated to 3000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T12:36:58+00:00, issue sha256 `589b894b7b539bbbde0f69a5235aa4c038ded2d1b06548cc9954e788d70badac`

</details>
