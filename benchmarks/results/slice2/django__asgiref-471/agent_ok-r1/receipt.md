## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test failed before this fix and passed after it, so the reported \`got multiple values for argument 'context'\` error was reproduced and no longer occurs, with no regressions found and the fixed lines covered. The fix did not reach L2 because the tests did not catch enough mutants, and the behaviour-diff and break-my-fix stages were inconclusive, so the next step is to add tests that would fail i…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 4 of 7 mutants; 80% is needed

**Issue:** \`AsyncToSync\` incorrectly passes arguments when called function arguments to internal wrapper · **Repo:** testbed · **Base** `tf-base` (`b7aaa79`) → **head** `tf-agent_ok` (`3ab4dc3`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.571, mutants 7, killed 4, survived 3 |
| `regressions` | `none_found` | compared 71, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 25 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 1, inputs tried 0, properties counted 2, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 5; the rest in receipt.json)
- `asgiref/sync.py:217`: `                 _exc_info=sys.exc_info(), ` → `                 _exc_info=(None, None, None), ` made no test fail; not compared with the fix (`m-64f0ebc416f9`)
- `asgiref/sync.py:325`: `             if _exc_info[1]: ` → `             if not _exc_info[1]: ` made no test fail; not compared with the fix (`m-70396078c964`)
- `asgiref/sync.py:329`: `                     result = await self.awaitable(*_args, **... ` → `                     result = await self.awaitable(**_kwargs) ` made no test fail; not compared with the fix (`m-711e7613987b`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack AsyncToSync.\_\_call\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; the behaviour diff could not compare AsyncToSync.\_\_call\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 36,140 input and 3,852 output tokens, cost $0.1956 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 14.77 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.16 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 16.69 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 554.24 s: the tests killed 4 of 7 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 14.6 s: none of the 71 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.43 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 2.71 s: nothing was compared: AsyncToSync.\_\_call\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 32.41 s: no target could be attacked: TypeError: unhashable type: 'list'
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `asgiref.sync.AsyncToSync.main_wrap` (`asgiref/sync.py`): not attacked (TypeError: unhashable type: 'list')
#### More changes no test noticed
- `asgiref/sync.py:316`: `             _restore_context(_context[0]) ` → `             _restore_context(_context[(-1)]) ` made no test fail; not compared with the fix (`m-91cdcd3324c5`)
- `asgiref/sync.py:325`: `             if _exc_info[1]: ` → `             if not (_exc_info[1]): ` made no test fail; not compared with the fix (`m-babac04390a5`)
#### Fix lines run (report only)
- repro: 12 of 25 fix lines run
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
- Break My Fix could not attack AsyncToSync.\_\_call\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare AsyncToSync.\_\_call\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
#### Notes
- guard: only the first 10 of 20 rule mutants were run
- guard: 1 of the rule mutant kills were crashes on the mutated line
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T20:34:02+00:00, issue sha256 `0a523d38f87cafeb2c9a0dacffc1e962eece77d2bd673710d01ddb071435644a`

</details>
