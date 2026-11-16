## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the issue, but the fix introduced a regression: tests/commands/test\_mapping\_sheet.py::test\_command passed before the fix and fails after it. Check whether that test's expected output needs updating for the new "reference" rows or whether the fix broke existing mapping-sheet behaviour, and note that the reproduction was not confirmed as guarded by the fix.

**Why this level:** regression: tests/commands/test\_mapping\_sheet.py::test\_command passed before the fix and fails after it

**Issue:** mapping-sheet: script omits original description when a reference is used for an object · **Repo:** testbed · **Base** `tf-base` (`c7aa013`) → **head** `tf-gold` (`ad9aebf`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. Regression: `tests/commands/test_mapping_sheet.py::test_command` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert 'section,path....1,uri,,,\\r\\n' == 'section,path....1,uri,,,\\r\\n')

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.25, mutants 4, killed 1, survived 3 |
| `regressions` | `found` | compared 12, regressions 1, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 52 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_on_head` | attempts 2, report only True |

**Rule mutants by kind (report only):** body: 2 of 2 killed; compare: 0 of 1 killed; logic: 0 of 2 killed; negate\_if: 1 of 1 killed; constant: 0 of 1 killed; arithmetic: 1 of 1 killed; membership: 0 of 1 killed; drop\_call: 0 of 1 killed; no place for loop, reraise

### Changes no test noticed (3 of 9; the rest in receipt.json)
- `ocdskit/cli/commands/mapping_sheet.py:59`: `                     required = 'string' in type_ or 'integer... ` → `                     required = 'string' in type_ and 'intege... ` made no test fail; not compared with the fix (`m-eca406e0f749`)
- `ocdskit/cli/commands/mapping_sheet.py:59`: `                     required = 'string' in type_ or 'integer... ` → `                     required = 'string' in type_ ` made no test fail; not compared with the fix (`m-3583848fb8d7`)
- `ocdskit/cli/commands/mapping_sheet.py:69`: `             if field in required_fields: ` → `             if field not in required_fields: ` made no test fail; not compared with the fix (`m-2c1c2c8ff19f`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet; Command.handle.make\_row: a nested function: it can't be imported, not attacked yet)); break\_my\_fix: skipped (the fix changes no function Break My Fix can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet; Command.handle.make\_row: a nested function: it can't be imported, not attacked yet)); Break My Fix could not attack Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet; Break My Fix could not attack Command.handle.make\_row: a nested function: it can't be imported, not attacked yet; and 3 more in receipt.json
- **Model use:** 6 calls, 28,718 input and 5,580 output tokens, cost $0.1182 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 3.41 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.83 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 12.89 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 132.15 s: the tests killed 1 of 4 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 20.02 s: 1 confirmed: tests/commands/test\_mapping\_sheet.py::test\_command
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.69 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `skipped`, 0.08 s: the fix changes no function the behaviour diff can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet; Command.handle.make\_row: a nested function: it can't be imported, not attacked yet)
- `break_my_fix`: `skipped`, 0.0 s: the fix changes no function Break My Fix can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet; Command.handle.make\_row: a nested function: it can't be imported, not attacked yet)
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_on_head`, 28.57 s: attempt 2: fails the same way before and after the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### More changes no test noticed
- `ocdskit/cli/commands/mapping_sheet.py:72`: `             maxn = 'n' if row['type'] == 'array' else '1' ` → `             maxn = 'n' if row['type'] != 'array' else '1' ` made no test fail; not compared with the fix (`m-1c38a890c407`)
- `ocdskit/cli/commands/mapping_sheet.py:59`: `                     required = 'string' in type_ or 'integer... ` → `                     required = 'string' in type_ and 'intege... ` made no test fail; not compared with the fix (`m-eca406e0f749`)
- `ocdskit/cli/commands/mapping_sheet.py:36`: `         def make_row(path, field, schema, deprecated, requir... ` → `         def make_row(path, field, schema, deprecated, requir... ` made no test fail; not compared with the fix (`m-8f37a90c72d3`)
- `ocdskit/cli/commands/mapping_sheet.py:39`: `             section = row['path'].split('/')[0] if '/' in ro... ` → `             section = row['path'].split('/')[0] if '/' not i... ` made no test fail; not compared with the fix (`m-58afaa7e991f`)
- `ocdskit/cli/commands/mapping_sheet.py:57`: `                     type_.remove('null') ` → `                     pass ` made no test fail; not compared with the fix (`m-fb9c6a5e3b80`)
- `ocdskit/cli/commands/mapping_sheet.py:102`: `                     if 'type' not in reference and 'type' in... ` → `                     if 'type' not in reference or 'type' in ... ` made no test fail; not compared with the fix (`m-bb7b258ae0c4`)
#### Fix lines run (report only)
- repro: 41 of 52 fix lines run
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet; Command.handle.make\_row: a nested function: it can't be imported, not attacked yet))
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call (Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet; Command.handle.make\_row: a nested function: it can't be imported, not attacked yet))
- Break My Fix could not attack Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet
- Break My Fix could not attack Command.handle.make\_row: a nested function: it can't be imported, not attacked yet
- the behaviour diff could not compare Command.handle.display\_properties: a nested function: it can't be imported, not attacked yet
- the behaviour diff could not compare Command.handle.make\_row: a nested function: it can't be imported, not attacked yet
#### Notes
- guard: 6 of the 10 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 41 rule mutants were run
- guard: 1 of the rule mutant kills were crashes on the mutated line
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T22:56:10+00:00, issue sha256 `16e5061586f299b970735dfc1be22d6612db2861e3b7c9d7cd87115aa4ab907f`

</details>
