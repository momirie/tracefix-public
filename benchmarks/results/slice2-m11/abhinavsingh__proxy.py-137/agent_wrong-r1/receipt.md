## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The bug was reproduced: a test fails before the fix and passes after it, and the fix changes how HttpParser.process\_line raises exceptions on malformed request lines, a change the Judge labelled as intended. The most important next step is getting the existing suite to run cleanly on the fixed code, because the guard stage was inconclusive and regressions were skipped, so the mutation rate is inc…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 0 of 3 mutants; 80% is needed, but the existing suite could not run cleanly on the fixed code, so the rate is incomplete

**Issue:** \[HttpParser\] Handle invalid/malformed request chunks from client · **Repo:** testbed · **Base** `tf-base` (`69445a8`) → **head** `tf-agent_wrong` (`b905940`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite no\_tests |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `inconclusive` | kill rate 0\.0, mutants 3, killed 0, survived 3 |
| `regressions` | `skipped` | compared 0, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 4 |
| `behaviour_diff` | `compared` | inputs compared 204, changes 198, groups 1 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 318, properties counted 2, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_differently` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 0 of 1 killed; compare: 0 of 2 killed; negate\_if: 1 of 2 killed; constant: 0 of 4 killed; no place for logic, arithmetic, membership, loop, drop\_call, reraise

### Behaviour changes
- `proxy.HttpParser.process_line` (`exception`, 198 inputs): `raises IndexError; left its arguments as builtins.list([buil...` → `raises ProtocolException: Invalid response line b''; left it...`; the Judge (advisory) calls it intended: The issue asks HttpParser to be strict about malformed lines rather than crash with IndexError; an empty response line now raises ProtocolException, the same rule applied to the response branch.; the Judge (advisory) calls it intended: The issue says HttpParser must ignore invalid chunks or drop the connection; an empty status line now raises ProtocolException instead of an IndexError crash.; the Judge (advisory) calls it intended: A single-token line is malformed; per the issue it should be rejected cleanly, and ProtocolException does that where IndexError crashed.; the Judge (advisory) calls it intended: A malformed one-token line now gets the strict ProtocolException handling the issue's expected behaviour asks for, replacing an IndexError.; the Judge (advisory) calls it intended: A bare CRLF line is malformed input like the issue's telnet newline; it is now rejected with ProtocolException instead of crashing with IndexError.

### Changes no test noticed (3 of 11; the rest in receipt.json)
- `proxy.py:727`: `             if len(line) < 3: ` → `             if len(line) < 2: ` made no test fail; no input tried behaved differently from the fix (`m-a1f6a0210625`)
- `proxy.py:727`: `             if len(line) < 3: ` → `             if len(line) < 4: ` made no test fail; no input tried behaved differently from the fix (`m-6b4c6200e8c7`)
- `proxy.py:727`: `             if len(line) < 3: ` → `             if len(line) <= 3: ` made no test fail; no input tried behaved differently from the fix (`m-e1437f300950`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; regressions: skipped (no test the fix left untouched passed before it); 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 46,410 input and 6,178 output tokens, cost $0.2820 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 1.14 s: base suite no\_tests
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.47 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 17.27 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `guard`: `inconclusive`, 46.38 s: the tests killed 0 of 3 mutants; 80% is needed, but the existing suite could not run cleanly on the fixed code, so the rate is incomplete
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `skipped`, 0.0 s: no test the fix left untouched passed before it
- `fix_line_coverage`: `ok`, 1.67 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `behaviour_diff`: `compared`, 31.99 s: 204 input(s) compared on 1 function(s): 198 changed with the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 9.2 s: no counterexample found in 318 inputs against 2 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.07 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_differently`, 9.75 s: attempt 1: fails after the fix too, but differently
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
#### Break My Fix targets
- `proxy.HttpParser.process_line` (`proxy.py`): 318 inputs
#### More changes no test noticed
- `proxy.py:725`: `         line = raw.split(WHITESPACE)\n        if self.type ==... ` → `         return None ` made no test fail; behaves differently from the fix on inputs no test checks (`m-94e6e64ffd5c`)
- `proxy.py:727`: `             if len(line) < 3: ` → `             if len(line) <= 3: ` made no test fail; no input tried behaved differently from the fix (`m-e1437f300950`)
- `proxy.py:727`: `             if len(line) < 3: ` → `             if len(line) < 2: ` made no test fail; no input tried behaved differently from the fix (`m-a1f6a0210625`)
- `proxy.py:733`: `             if len(line) < 2: ` → `             if len(line) <= 2: ` made no test fail; behaves differently from the fix on inputs no test checks (`m-6b7f3ef04d7c`)
- `proxy.py:733`: `             if len(line) < 2: ` → `             if not (len(line) < 2): ` made no test fail; behaves differently from the fix on inputs no test checks (`m-ca15fe1163e8`)
- `proxy.py:727`: `             if len(line) < 3: ` → `             if len(line) < 4: ` made no test fail; no input tried behaved differently from the fix (`m-6b4c6200e8c7`)
- `proxy.py:733`: `             if len(line) < 2: ` → `             if len(line) < 1: ` made no test fail; behaves differently from the fix on inputs no test checks (`m-be87525fba76`)
- `proxy.py:733`: `             if len(line) < 2: ` → `             if len(line) < 3: ` made no test fail; behaves differently from the fix on inputs no test checks (`m-06869ea9525d`)
#### Fix lines run (report only)
- repro: 2 of 4 fix lines run
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
- regressions: skipped (no test the fix left untouched passed before it)
#### Notes
- guard: 7 of the 10 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: the existing suite did not run cleanly on the fixed code
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T20:12:53+00:00, issue sha256 `f8ea962c17cbcb50b04b5d93316cea7ff73189c2ae5dbeac958aa669c19db987`

</details>
