## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the issue, but tests/commands/test\_mapping\_sheet.py::test\_command passed before the fix and fails after it, which is a regression counterexample; the fix was also not shown to guard against the original bug. Look first at why test\_command now fails, whether its expected output needs a deliberate update for the new "reference" rows or the fix broke existing mapping-sheet ou…

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
| `guard` | `not_guarded` | kill rate 0\.0, mutants 8, killed 0, survived 8 |
| `regressions` | `found` | compared 12, regressions 1, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 38 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 11; the rest in receipt.json)
- `ocdskit/cli/commands/mapping_sheet.py:63`: `original_title = original_ref.get('title', field + '*')` → `original_title = original_ref.get('title', field)` made no test fail; not compared with the fix (`m-c1e6df20f988`)
- `ocdskit/cli/commands/mapping_sheet.py:73`: `'type': 'reference'` → `'type': 'unknown'` made no test fail; not compared with the fix (`m-d99337964283`)
- `ocdskit/cli/commands/mapping_sheet.py:99`: `maxn = 'n' if obj[field].get('type') == 'array' else '1'` → `maxn = '1'` made no test fail; not compared with the fix (`m-f3ce0c746324`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet)); break\_my\_fix: skipped (the fix changes no function Break My Fix can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet)); Break My Fix could not attack Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet; the behaviour diff could not compare Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet; and 1 more in receipt.json
- **Model use:** 4 calls, 21,255 input and 2,829 output tokens, cost $0.0758 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 3.16 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.55 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 25.63 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 116.22 s: the tests killed 0 of 8 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 17.17 s: 1 confirmed: tests/commands/test\_mapping\_sheet.py::test\_command
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.22 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `skipped`, 0.05 s: the fix changes no function the behaviour diff can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet)
- `break_my_fix`: `skipped`, 0.0 s: the fix changes no function Break My Fix can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet)
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### More changes no test noticed
- `ocdskit/cli/commands/mapping_sheet.py:100`: `minn = '1' if required else '0'` → `minn = '0' if required else '1'` made no test fail; not compared with the fix (`m-c0b3e59e3669`)
- `ocdskit/cli/commands/mapping_sheet.py:97`: `required = field in required_fields or ('type' in obj[field]...` → `required = field in required_fields and ('type' in obj[field...` made no test fail; not compared with the fix (`m-82b621da0877`)
- `ocdskit/cli/commands/mapping_sheet.py:81`: `temp_enum = [x for x in obj[field]['enum'] if x is not None]` → `temp_enum = [x for x in obj[field]['enum'] if x is None]` made no test fail; not compared with the fix (`m-cbd2ef88c518`)
- `ocdskit/cli/commands/mapping_sheet.py:105`: `original_row['deprecated'] = original_ref['deprecated'].get(...` → `original_row['deprecated'] = original_ref['deprecated'].get(...` made no test fail; not compared with the fix (`m-ecb4a4c70831`)
- `ocdskit/cli/commands/mapping_sheet.py:89`: `if original_description:` → `if not original_description:` made no test fail; not compared with the fix (`m-2ca00ccd7420`)
- `ocdskit/cli/commands/mapping_sheet.py:80`: `                         if None in obj[field]['enum']: ` → `                         if None not in obj[field]['enum']: ` made no test fail; not compared with the fix (`m-1669e0c3faf5`)
- `ocdskit/cli/commands/mapping_sheet.py:81`: `                             temp_enum = [x for x in obj[fiel... ` → `                             temp_enum = [x for x in obj[fiel... ` made no test fail; not compared with the fix (`m-d0a417c705a9`)
- `ocdskit/cli/commands/mapping_sheet.py:84`: `                         original_row['values'] = 'Codelist: ... ` → `                         original_row['values'] = 'Codelist: ... ` made no test fail; not compared with the fix (`m-43fa19c0a38b`)
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
- guard: only the first 10 of 22 rule mutants were run
- guard: 2 of the rule mutant kills were crashes on the mutated line
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T21:49:59+00:00, issue sha256 `16e5061586f299b970735dfc1be22d6612db2861e3b7c9d7cd87115aa4ab907f`

</details>
