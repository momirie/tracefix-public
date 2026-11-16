## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the issue, but the fix introduced a regression: tests/commands/test\_mapping\_sheet.py::test\_command passed before the fix and fails after it. Check whether that test's expected output needs updating for the new "reference" rows or whether the fix broke existing mapping-sheet behaviour, and note that the reproduction was not confirmed as guarded by the fix.

**Why this level:** regression: tests/commands/test\_mapping\_sheet.py::test\_command passed before the fix and fails after it

**Issue:** mapping-sheet: script omits original description when a reference is used for an object · **Repo:** testbed · **Base** `tf-base` (`c7aa013`) → **head** `tf-agent_wrong` (`5f1721a`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. Regression: `tests/commands/test_mapping_sheet.py::test_command` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert 'section,path....1,uri,,,\\r\\n' == 'section,path....1,uri,,,\\r\\n')

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 3, killed 0, survived 3 |
| `regressions` | `found` | compared 12, regressions 1, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 38 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_on_head` | attempts 2, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; compare: 0 of 1 killed; logic: 0 of 2 killed; negate\_if: 1 of 2 killed; arithmetic: 2 of 2 killed; membership: 1 of 1 killed; drop\_call: 1 of 1 killed; no place for constant, loop, reraise

### Changes no test noticed (3 of 7; the rest in receipt.json)
- `ocdskit/cli/commands/mapping_sheet.py:63`: `original_title = original_ref.get('title', field + '*')` → `original_title = original_ref.get('title', field)` made no test fail; not compared with the fix (`m-c1e6df20f988`)
- `ocdskit/cli/commands/mapping_sheet.py:73`: `'type': 'reference'` → `'type': 'unknown'` made no test fail; not compared with the fix (`m-d99337964283`)
- `ocdskit/cli/commands/mapping_sheet.py:78`: `original_row['values'] = obj[field]['format']` → `original_row['values'] = ''` made no test fail; not compared with the fix (`m-3cac6f759086`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet)); break\_my\_fix: skipped (the fix changes no function Break My Fix can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet)); Break My Fix could not attack Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet; the behaviour diff could not compare Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet; and 1 more in receipt.json
- **Model use:** 6 calls, 30,714 input and 5,313 output tokens, cost $0.1195 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 3.36 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.85 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 11.54 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 95.67 s: the tests killed 0 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 19.36 s: 1 confirmed: tests/commands/test\_mapping\_sheet.py::test\_command
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.55 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `skipped`, 0.05 s: the fix changes no function the behaviour diff can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet)
- `break_my_fix`: `skipped`, 0.01 s: the fix changes no function Break My Fix can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet)
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_on_head`, 11.9 s: attempt 2: fails the same way before and after the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### More changes no test noticed
- `ocdskit/cli/commands/mapping_sheet.py:99`: `                     maxn = 'n' if obj[field].get('type') == ... ` → `                     maxn = 'n' if obj[field].get('type') != ... ` made no test fail; not compared with the fix (`m-073644e4aaa9`)
- `ocdskit/cli/commands/mapping_sheet.py:97`: `                     required = field in required_fields or (... ` → `                     required = field in required_fields and ... ` made no test fail; not compared with the fix (`m-84c3bf1dd374`)
- `ocdskit/cli/commands/mapping_sheet.py:97`: `                     required = field in required_fields or (... ` → `                     required = field in required_fields or (... ` made no test fail; not compared with the fix (`m-f59d7e051db3`)
- `ocdskit/cli/commands/mapping_sheet.py:89`: `                     if original_description: ` → `                     if not (original_description): ` made no test fail; not compared with the fix (`m-5d93a1f8298c`)
#### Fix lines run (report only)
- repro: 30 of 38 fix lines run
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet))
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet))
- Break My Fix could not attack Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet
- the behaviour diff could not compare Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet
#### Notes
- guard: 7 of the 10 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 23 rule mutants were run
- guard: 2 of the rule mutant kills were crashes on the mutated line
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T22:59:34+00:00, issue sha256 `16e5061586f299b970735dfc1be22d6612db2861e3b7c9d7cd87115aa4ab907f`

</details>
