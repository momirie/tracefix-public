## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The bug was reproduced, with a test that fails before the fix and passes after it, no regressions were found, and the fixed lines were covered, but the guard stage reported the fix as not guarded and the evidence stayed at L1 because the mutation threshold for L2 was not met. Next, look at why the tests did not guard the fix against mutants, and consider strengthening the test for the sync-client…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 1 of 4 mutants; 80% is needed

**Issue:** Sync client fails on ASGI apps with unhelpful traceback · **Repo:** testbed · **Base** `tf-base` (`21f5337`) → **head** `tf-v1` (`fb4d75e`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.25, mutants 4, killed 1, survived 3 |
| `regressions` | `none_found` | compared 478, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 0 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `httpx/_client.py:429`: `An WSGI application to send requests to,` → `An WSGI application to receive requests from,` made no test fail; not compared with the fix (`m-444fd6841942`)
- `httpx/_client.py:429`: `*(optional)* An WSGI application` → `*(required)* An WSGI application` made no test fail; not compared with the fix (`m-71213b5dff61`)
- `httpx/_client.py:429`: `An WSGI application to send requests to,` → `An WSGI application to send responses to,` made no test fail; not compared with the fix (`m-0782e1a221d4`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call); break\_my\_fix: skipped (the fix changes no function Break My Fix can call); 9 things the behaviour diff can't observe (run log)
- **Model use:** 4 calls, 6,225 input and 1,141 output tokens, cost $0.0292 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 11.26 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.77 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 18.53 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 106.27 s: the tests killed 1 of 4 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 39.02 s: none of the 478 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 0.01 s: report only: which fix lines the tests run
- `behaviour_diff`: `skipped`, 0.17 s: the fix changes no function the behaviour diff can call
- `break_my_fix`: `skipped`, 0.01 s: the fix changes no function Break My Fix can call
- `integrity`: `clean`, 0.05 s: nothing suspicious in the fix's test or source changes
#### Fix lines run (report only)
- the fix has no executable lines
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
- fix\_line\_coverage: the fix has no executable lines
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T21:37:50+00:00, issue sha256 `54139a820af0ed1f90161802c7e82cc05222e1a15f46c9892d98df1f187ca713`

</details>
