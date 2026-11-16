## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the original KeyError, covered the fix lines and found no regressions, but Break My Fix found that calling finalize on a CppHeader already built from the issue's example raises AttributeError: 'CppHeader' object has no attribute '\_precomp\_macro\_buf'. Next, check whether that failure can happen in normal use or only when finalize is called a second time, and add a test for…

**Why this level:** Break My Fix finding 1: an input that breaks CppHeaderParser.CppHeaderParser.\_CppHeader.finalize

**Issue:** Another regression in 4.0.0 · **Repo:** testbed · **Base** `tf-base` (`0a1511b`) → **head** `tf-agent_ok` (`b0670da`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `finalize(self="CppHeader('\\ntypedef C A;\\n\\nclass B\\n{\\...` → `raises AttributeError: 'CppHeader' object has no attribute '...`; breaks **finalize\_does\_not\_raise\_on\_typedef\_return\_type**: “Following example fails using 4.0.0 and newer (but not with 3.3.0 and older)” (issue); 3 more inputs break it the same way; test: `findings/finding_1.py`; **Doubt (still counted):** the object's class deletes this attribute itself: it may be finished

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.5, mutants 4, killed 2, survived 2 |
| `regressions` | `none_found` | compared 55, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 1 |
| `behaviour_diff` | `compared` | inputs compared 1, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 1, inputs tried 15, properties counted 4, findings 1 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; constant: 0 of 2 killed; no place for compare, logic, negate\_if, arithmetic, membership, loop, drop\_call, reraise

### Changes no test noticed (3 of 4; the rest in receipt.json)
- `CppHeaderParser/CppHeaderParser.py:1960`: `                     "typedefs": 0, ` → `                     "typedefs": 1, ` made no test fail; no input tried behaved differently from the fix (`m-4d3397eda5a7`)
- `CppHeaderParser/CppHeaderParser.py:1960`: `                     "typedefs": 0, ` → `                     "typedefs": -1, ` made no test fail; no input tried behaved differently from the fix (`m-50e8985e3538`)
- `CppHeaderParser/CppHeaderParser.py:1960`: `                     "typedefs": 0, ` → `                     "typedefs": (-1), ` made no test fail; no input tried behaved differently from the fix (`m-6f07b16c03d1`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 48,272 input and 5,429 output tokens, cost $0.2128 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 18.95 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.38 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 13.77 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `guard`: `not_guarded`, 267.92 s: the tests killed 2 of 4 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 77.73 s: none of the 55 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.44 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `behaviour_diff`: `compared`, 14.11 s: 1 input(s) compared on 1 function(s): 0 changed with the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 14.99 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.09 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 14.02 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
#### Break My Fix targets
- `CppHeaderParser.CppHeaderParser._CppHeader.finalize` (`CppHeaderParser/CppHeaderParser.py`): 15 inputs
#### More changes no test noticed
- `CppHeaderParser/CppHeaderParser.py:1960`: `                     "typedefs": 0, ` → `                     "typedefs": 1, ` made no test fail; no input tried behaved differently from the fix (`m-4d3397eda5a7`)
#### Fix lines run (report only)
- repro: 1 of 1 fix lines run
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
#### Notes
- reproduce: style example test/test\_CppHeaderParser.py truncated to 6000 characters for the prompt
- guard: 5 of the 9 mutants were not run: the tests could no longer reach 80% even if they killed them all
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.20: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: style example test/test\_CppHeaderParser.py truncated to 6000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T22:01:25+00:00, issue sha256 `4724e29bf19bd7b12356b9564237c5a21835feb338ed71b5f59b67ad0c09f3b1`

</details>
