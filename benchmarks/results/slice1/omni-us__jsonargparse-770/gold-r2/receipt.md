## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The bug was reproduced: a test fails before the fix and passes after it, with no regressions found and no inputs found that break the fixed code. The tests did not kill enough mutants to reach L2 and the behaviour diff was only partial, so the next thing to look at is strengthening the tests around Callable types configured with class\_path functions like torch.argmax.

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 0 of 5 mutants; 80% is needed

**Issue:** Any ways to support torch functions · **Repo:** testbed · **Base** `tf-base` (`cb4e633`) → **head** `tf-gold` (`17d119b`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 5, killed 0, survived 5 |
| `regressions` | `none_found` | compared 1106, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 13 |
| `behaviour_diff` | `partial` | inputs compared 1, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 2, inputs tried 188, properties counted 5, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 8; the rest in receipt.json)
- `jsonargparse/_common.py:99`: `     "stubs_resolver_allow_py_files": False, ` → `     "stubs_resolver_allow_py_files": True, ` made no test fail; no input tried behaved differently from the fix (`m-961869980ad0`)
- `jsonargparse/_common.py:159`: `         parsing_settings["stubs_resolver_allow_py_files"] = ... ` → `         parsing_settings["stubs_resolver_allow_py_files"] = ... ` made no test fail; no input tried behaved differently from the fix (`m-3308af1e5846`)
- `jsonargparse/_stubs_resolver.py:108`: `         search_context = tc.get_search_context(allow_py_file... ` → `         search_context = tc.get_search_context(allow_py_file... ` made no test fail; not compared with the fix (`m-ab7434fb0ebc`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack get\_stubs\_resolver: it takes no parameters to vary; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 62,096 input and 6,683 output tokens, cost $0.3096 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 11.35 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.74 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_imports.py`
- `reproduce`: `reproduced`, 39.24 s: attempt 2: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no jsonargparse_tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 197.39 s: the tests killed 0 of 5 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no jsonargparse_tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 11.99 s: none of the 1106 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 3.82 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no jsonargparse_tests/test_tracefix_repro.py`
- `behaviour_diff`: `partial`, 41.11 s: 1 input(s) compared on 2 function(s): 0 changed with the fix; not complete: jsonargparse/\_common.py: module-level code that computes a value changed (line 99); what uses it is not compared
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no jsonargparse_tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s test_tracefix_diff.py`
- `break_my_fix`: `none_found`, 66.03 s: no counterexample found in 188 inputs against 5 properties
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_attack.py`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
#### More changes no test noticed
- `jsonargparse/_stubs_resolver.py:107`: `         allow_py_files = get_parsing_setting("stubs_resolver... ` → `         allow_py_files = False ` made no test fail; not compared with the fix (`m-273197423272`)
- `jsonargparse/_common.py:158`: `     if isinstance(stubs_resolver_allow_py_files, bool): ` → `     if stubs_resolver_allow_py_files: ` made no test fail; no input tried behaved differently from the fix (`m-b11e4dce16df`)
- `jsonargparse/_stubs_resolver.py:105`: `     global stubs_resolver\n    if not stubs_resolver:\n       ... ` → `     return None ` made no test fail; not compared with the fix (`m-b9930e486fb5`)
- `jsonargparse/_common.py:99`: `     "stubs_resolver_allow_py_files": False, ` → `     "stubs_resolver_allow_py_files": True, ` made no test fail; no input tried behaved differently from the fix (`m-961869980ad0`)
- `jsonargparse/_common.py:158`: `     if isinstance(stubs_resolver_allow_py_files, bool): ` → `     if not (isinstance(stubs_resolver_allow_py_files, bool)): ` made no test fail; behaves differently from the fix on inputs no test checks (`m-3884bca7a280`)
#### Fix lines run (report only)
- repro: 2 of 13 fix lines run
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
- Break My Fix could not attack get\_stubs\_resolver: it takes no parameters to vary
#### Notes
- reproduce: style example jsonargparse\_tests/test\_actions.py truncated to 6000 characters for the prompt
- reproduce: pyproject truncated to 3000 characters for the prompt
- regressions: 1 untouched test(s) that passed before the fix did not run after it (skipped or not collected), so they were not compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-20T11:48:35+00:00, issue sha256 `2d800fb9fcf781856206ad2b7300c8e52f86c02831518f86fbb7951c42eceb14`

</details>
