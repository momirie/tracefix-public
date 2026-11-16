## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier's reproduction test fails the same way before and after this fix, and 11 previously passing tests now fail, including header tests in tests/client/test\_headers.py, the redirect no-body tests, and the empty-content/no-content tests. Look first at the value change in httpx.\_content\_streams.ByteStream.get\_headers, which the Judge labelled suspicious and which likely explains the empty-b…

**Why this level:** the fix does not fix the bug: the reproduction test fails the same way before and after it; regression: tests/client/test\_headers.py::test\_client\_header passed before the fix and fails after it; regression: tests/client/test\_headers.py::test\_header\_merge passed before the fix and fails after it; regression: tests/client/test\_headers.py::test\_header\_merge\_conflicting\_headers passed before the fix and fails after it; regression: tests/client/test\_headers.py::test\_header\_update passed before the fix and fails after it; regression: tests/client/test\_headers.py::test\_host\_with\_auth\_and\_port\_in\_url passed before the fix and fails after it; and 6 more in receipt.json

**Issue:** Sync client fails on ASGI apps with unhelpful traceback · **Repo:** testbed · **Base** `tf-base` (`21f5337`) → **head** `tf-gold` (`73ac62b`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples (5 of 11; the rest in receipt.json)
1. Regression: `tests/client/test_headers.py::test_client_header` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert {'headers': {...h': '0', ...}} == {'headers': {...-value', ...}})
2. Regression: `tests/client/test_headers.py::test_header_merge` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert {'headers': {...h': '0', ...}} == {'headers': {...le.org', ...}})
3. Regression: `tests/client/test_headers.py::test_header_merge_conflicting_headers` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert {'headers': {...h': '0', ...}} == {'headers': {...le.org', ...}})
4. Regression: `tests/client/test_headers.py::test_header_update` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert {'headers': {...h': '0', ...}} == {'headers': {...le.org', ...}})
5. Regression: `tests/client/test_headers.py::test_host_with_auth_and_port_in_url` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert {'headers': {...-alive', ...}} == {'headers': {...-alive', ...}})

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `fix_does_not_fix` | attempts 1 |
| `guard` | `skipped` | mutants 0, killed 0, survived 0 |
| `regressions` | `found` | compared 478, regressions 11, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 2 |
| `behaviour_diff` | `compared` | inputs compared 196, changes 2, groups 1 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 394, properties counted 4, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `not_run` | attempts 0, report only True |

### Behaviour changes
- `httpx._content_streams.ByteStream.get_headers` (`value`, 2 inputs): `returns {}` → `returns {'Content-Length': '0'}`; the Judge (advisory) calls it suspicious: The issue is about the sync Client being handed an ASGI app (its docstring says ASGI). Nothing in it mentions Content-Length on empty bodies, so adding 'Content-Length: 0' for body='' is unrequested.; the Judge (advisory) calls it suspicious: The issue concerns ASGI apps used with the sync Client and asks nothing about ByteStream headers. Emitting 'Content-Length: 0' for b'' goes beyond what was reported.

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; guard: skipped (there is no reproduction test to judge the tests with (fix\_does\_not\_fix)); 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 35,085 input and 4,122 output tokens, cost $0.1893 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 11.68 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.27 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `fix_does_not_fix`, 14.18 s: attempt 1: the test fails before and after the fix with the same failure signature, also after the model was shown the result This rests on a test written by the model claude-sonnet-5-5.
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `skipped`, 0.0 s: there is no reproduction test to judge the tests with (fix\_does\_not\_fix)
- `regressions`: `found`, 53.89 s: 11 confirmed: tests/client/test\_headers.py::test\_client\_header, tests/client/test\_headers.py::test\_header\_merge, tests/client/test\_headers.py::test\_header\_merge\_conflicting\_headers, tests/client/test\_headers.py::test\_header\_update, tests/client/test\_headers.py::test\_host\_with\_auth\_and\_port\_in\_url and 6 more
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 0.02 s: report only: which fix lines the tests run
- `behaviour_diff`: `compared`, 7.25 s: 196 input(s) compared on 1 function(s): 2 changed with the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `none_found`, 9.07 s: no counterexample found in 394 inputs against 4 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.03 s: nothing suspicious in the fix's test or source changes
- `blind`: `not_run`, 0.0 s: the main test did not reproduce the bug
#### More counterexamples
- Regression: `tests/client/test_headers.py::test_host_with_non_default_port_in_url` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert {'headers': {...-alive', ...}} == {'headers': {...-alive', ...}})
- Regression: `tests/client/test_redirects.py::test_no_body_redirect[asyncio]` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert 'content-length' not in {'accept': '\*/\*', 'accept-encoding': 'gzip, deflate, br', 'connection': 'keep-alive', 'content-length': '0', ...})
- Regression: `tests/client/test_redirects.py::test_no_body_redirect[trio]` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: exceptiongroup.ExceptionGroup: Exceptions from Trio nursery (1 sub-exception))
- Regression: `tests/models/test_requests.py::test_no_content` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert 'Content-Length' not in Headers({'host': 'example.org', 'user-agent': 'python-httpx/0.12.1', 'accept': '\*/\*', 'accept-encoding': 'gzip, deflate, br', 'connection': 'keep-alive', 'content-length': '0'}))
- Regression: `tests/test_content_streams.py::test_empty_content` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert {'Content-Length': '0'} == {})
- Regression: `tests/test_content_streams.py::test_empty_request` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert {'Content-Length': '0'} == {})
#### Break My Fix targets
- `httpx._content_streams.ByteStream.get_headers` (`httpx/_content_streams.py`): 394 inputs
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
- guard: skipped (there is no reproduction test to judge the tests with (fix\_does\_not\_fix))
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T22:43:48+00:00, issue sha256 `54139a820af0ed1f90161802c7e82cc05222e1a15f46c9892d98df1f187ca713`

</details>
