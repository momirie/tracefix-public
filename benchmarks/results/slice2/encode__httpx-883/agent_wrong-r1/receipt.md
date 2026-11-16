## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test fails before this fix and passes after it, so the reported failure of the sync client on ASGI apps was reproduced and no regressions were found, but the existing tests did not kill enough mutants and the behaviour-diff and Break My Fix stages were inconclusive. The most important next step is to strengthen the tests around the changed lines (the fix was marked not guarded) so that mutation…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 6 mutants; 80% is needed

**Issue:** Sync client fails on ASGI apps with unhelpful traceback · **Repo:** testbed · **Base** `tf-base` (`21f5337`) → **head** `tf-agent_wrong` (`a12ebe6`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.333, mutants 6, killed 2, survived 4 |
| `regressions` | `none_found` | compared 478, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 96 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 2, inputs tried 0, properties counted 1, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 6; the rest in receipt.json)
- `httpx/_client.py:513`: `                 if arg_count == 3: ` → `                 if arg_count >= 3: ` made no test fail; not compared with the fix (`m-a8bc0f295712`)
- `httpx/_dispatch/sync_asgi.py:79`: `                 if body and request.method != "HEAD": ` → `                 if body: ` made no test fail; not compared with the fix (`m-aa4f23e58217`)
- `httpx/_dispatch/sync_asgi.py:92`: `                 if self.raise_app_exceptions or not response... ` → `                 if self.raise_app_exceptions and not respons... ` made no test fail; not compared with the fix (`m-0bd65ef2d323`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack SyncASGIDispatch.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack SyncASGIDispatch.send.receive: a nested function: it can't be imported, not attacked yet; Break My Fix could not attack SyncASGIDispatch.send.run\_app: a nested function: it can't be imported, not attacked yet; Break My Fix could not attack SyncASGIDispatch.send.send: a nested function: it can't be imported, not attacked yet; and 6 more in receipt.json
- **Model use:** 6 calls, 55,484 input and 4,295 output tokens, cost $0.2734 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 10.96 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.79 s: 3 changed module(s) imported from the copies (5 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 18.71 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 207.81 s: the tests killed 2 of 6 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 40.03 s: none of the 478 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.53 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 2.77 s: nothing was compared: SyncASGIDispatch.\_\_init\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 42.41 s: no target could be attacked: TypeError: unhashable type: 'list'
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.03 s: no candidate was confirmed (2 reported)
#### Break My Fix targets
- `httpx._client.Client.init_dispatch` (`httpx/_client.py`): not attacked (TypeError: unhashable type: 'list')
- `httpx._dispatch.sync_asgi.SyncASGIDispatch.send` (`httpx/_dispatch/sync_asgi.py`): not attacked (no property to check it against)
#### More changes no test noticed
- `httpx/_dispatch/sync_asgi.py:40`: `             "server": (request.url.host, request.url.port) i... ` → `             "server": (request.url.host, request.url.port) i... ` made no test fail; not compared with the fix (`m-2868677e43d5`)
- `httpx/_dispatch/sync_asgi.py:58`: `             try:\n                body = next(request_body_ch... ` → `             return {} ` made no test fail; not compared with the fix (`m-d143170c0af6`)
- `httpx/_client.py:503`: `                 if hasattr(app, '__call__') and not isinstan... ` → `                 if hasattr(app, '__call__') or not isinstanc... ` made no test fail; not compared with the fix (`m-d92608e7e072`)
#### Fix lines run (report only)
- repro: 60 of 96 fix lines run
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
- Break My Fix could not attack SyncASGIDispatch.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack SyncASGIDispatch.send.receive: a nested function: it can't be imported, not attacked yet
- Break My Fix could not attack SyncASGIDispatch.send.run\_app: a nested function: it can't be imported, not attacked yet
- Break My Fix could not attack SyncASGIDispatch.send.send: a nested function: it can't be imported, not attacked yet
- the behaviour diff could not compare SyncASGIDispatch.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare SyncASGIDispatch.send.receive: a nested function: it can't be imported, not attacked yet
- the behaviour diff could not compare SyncASGIDispatch.send.run\_app: a nested function: it can't be imported, not attacked yet
- the behaviour diff could not compare SyncASGIDispatch.send.send: a nested function: it can't be imported, not attacked yet
- the behaviour diff could not compare SyncASGIDispatch.send: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 27 functions were shown
- guard: only the first 10 of 41 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T21:40:56+00:00, issue sha256 `54139a820af0ed1f90161802c7e82cc05222e1a15f46c9892d98df1f187ca713`

</details>
