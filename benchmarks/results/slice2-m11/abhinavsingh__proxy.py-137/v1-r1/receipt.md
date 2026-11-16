## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The reproduction test fails the same way before and after the fix, and Break My Fix found that HttpParser(parser\_type=1).parse(b'\\r\\n') still raises IndexError: list index out of range, which is the exact crash from the issue. Start with how process\_line handles an empty or malformed request line; also look at the type change in proxy.ChunkParser.parse, which the Judge labelled suspicious.

**Why this level:** the fix does not fix the bug: the reproduction test fails the same way before and after it; Break My Fix finding 1: an input that breaks proxy.HttpParser.parse

**Issue:** \[HttpParser\] Handle invalid/malformed request chunks from client · **Repo:** testbed · **Base** `tf-base` (`69445a8`) → **head** `tf-v1` (`55b97a2`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `parse(self='HttpParser(parser_type=1)', raw=b'\r\n')` → `raises IndexError: list index out of range` (before the fix: `raises IndexError: list index out of range`); breaks **malformed\_request\_line\_does\_not\_crash**: “Handle cases when client can send invalid chunks in requests.” (issue); 3 more inputs break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite no\_tests |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `fix_does_not_fix` | attempts 1 |
| `guard` | `skipped` | mutants 0, killed 0, survived 0 |
| `regressions` | `skipped` | compared 0, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 39 |
| `behaviour_diff` | `partial` | inputs compared 595, changes 187, groups 1 |
| `break_my_fix` | `found` | targets 6, inputs tried 470, properties counted 10, findings 1 |
| `integrity` | `clean` | flags 0 |
| `blind` | `not_run` | attempts 0, report only True |

### Behaviour changes
- `proxy.ChunkParser.parse` (`type`, 187 inputs): `returns None` → `returns b''`; the Judge (advisory) calls it suspicious: The issue is about HttpParser crashing (IndexError) on malformed request lines; nothing in it or in the ChunkParser docstring asks parse() to return leftover bytes instead of None.; the Judge (advisory) calls it suspicious: The return-type change from None to b'' on empty input is an API change for pipelining support that the issue about invalid client request chunks does not request.; the Judge (advisory) calls it suspicious: The ChunkParser docstring ('HTTP chunked encoding response parser') and the issue say nothing about parse() returning remaining bytes, so the new b'' return is unrequested.; the Judge (advisory) calls it suspicious: The issue asks HttpParser to ignore or reject malformed request lines, not to change ChunkParser.parse's return value; this goes beyond the report.; the Judge (advisory) calls it suspicious: The new bytes return value comes from unrelated pipelining refactoring that no text in the issue or docs asks for.

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; guard: skipped (there is no reproduction test to judge the tests with (fix\_does\_not\_fix)); regressions: skipped (no test the fix left untouched passed before it); the behaviour diff could not compare Benchmark.parse\_pipeline\_response: new with the fix: nothing to compare; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 105,559 input and 7,935 output tokens, cost $0.5399 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 1.1 s: base suite no\_tests
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.51 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `fix_does_not_fix`, 6.43 s: attempt 1: the test fails before and after the fix with the same failure signature, also after the model was shown the result This rests on a test written by the model claude-sonnet-5-5.
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `guard`: `skipped`, 0.0 s: there is no reproduction test to judge the tests with (fix\_does\_not\_fix)
- `regressions`: `skipped`, 0.0 s: no test the fix left untouched passed before it
- `fix_line_coverage`: `ok`, 0.04 s: report only: which fix lines the tests run
- `behaviour_diff`: `partial`, 7.91 s: 595 input(s) compared on 3 function(s): 187 changed with the fix; not complete: Benchmark.send: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 14.12 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 0.09 s: nothing suspicious in the fix's test or source changes
- `blind`: `not_run`, 0.0 s: the main test did not reproduce the bug
#### Found before the fix too
- `process(self='HttpParser(parser_type=1)', raw=b'\r\n')` → `raises IndexError: list index out of range` (before the fix: `raises IndexError: list index out of range`); breaks **malformed\_line\_no\_indexerror**: “\`HttpParser\` must either ignore invalid chunks or be strict about it and drop the connection.” (issue); 3 more inputs break it the same way
#### Break My Fix targets
- `benchmark.Benchmark.send` (`benchmark.py`): 0 inputs (nothing generated)
- `benchmark.Benchmark.parse_pipeline_response` (`benchmark.py`): 1 input
- `benchmark.Benchmark.recv` (`benchmark.py`): 1 input
- `proxy.ChunkParser.parse` (`proxy.py`): not attacked (no property to check it against)
- `proxy.HttpParser.parse` (`proxy.py`): 45 inputs
- `proxy.HttpParser.process` (`proxy.py`): 423 inputs
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
- regressions: skipped (no test the fix left untouched passed before it)
- the behaviour diff could not compare Benchmark.parse\_pipeline\_response: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 45 functions were shown
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T20:12:16+00:00, issue sha256 `f8ea962c17cbcb50b04b5d93316cea7ff73189c2ae5dbeac958aa669c19db987`

</details>
