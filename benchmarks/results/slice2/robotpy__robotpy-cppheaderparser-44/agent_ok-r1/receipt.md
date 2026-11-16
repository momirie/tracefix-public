## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the original KeyError, found no regressions, and confirmed the fix lines are covered, but Break My Fix found an input where calling finalize on a CppHeader built from the issue's own example raises AttributeError: 'CppHeader' object has no attribute '\_precomp\_macro\_buf'. Check whether this comes from finalize being re-invoked on an already-finalized object (a harness artif…

**Why this level:** Break My Fix finding 1: an input that breaks CppHeaderParser.CppHeaderParser.\_CppHeader.finalize

**Issue:** Another regression in 4.0.0 · **Repo:** testbed · **Base** `tf-base` (`0a1511b`) → **head** `tf-agent_ok` (`b0670da`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `finalize(self="CppHeader('\\ntypedef C A;\\n\\nclass B\\n{\\...` → `raises AttributeError: 'CppHeader' object has no attribute '...`; breaks **finalize\_no\_keyerror\_on\_typedef\_return**: “Following example fails using 4.0.0 and newer (but not with 3.3.0 and older)” (issue); 3 more inputs break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.667, mutants 3, killed 2, survived 1 |
| `regressions` | `none_found` | compared 55, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 1 |
| `behaviour_diff` | `compared` | inputs compared 1, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 1, inputs tried 15, properties counted 2, findings 1 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `CppHeaderParser/CppHeaderParser.py:1960`: `                     "typedefs": 0, ` → `                     "typedefs": 1, ` made no test fail; no input tried behaved differently from the fix (`m-4d3397eda5a7`)
- `CppHeaderParser/CppHeaderParser.py:1960`: `                     "typedefs": 0, ` → `                     "typedefs": (-1), ` made no test fail; no input tried behaved differently from the fix (`m-6f07b16c03d1`)
- `CppHeaderParser/CppHeaderParser.py:1960`: `                     "typedefs": 0, ` → `                     "typedefs": 1, ` made no test fail; no input tried behaved differently from the fix (`m-4d3397eda5a7`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 5 calls, 31,626 input and 3,244 output tokens, cost $0.1539 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 28.02 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.57 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 23.23 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `guard`: `not_guarded`, 325.85 s: the tests killed 2 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 114.58 s: none of the 55 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.4 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `behaviour_diff`: `compared`, 16.05 s: 1 input(s) compared on 1 function(s): 0 changed with the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 53.14 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.18 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `CppHeaderParser.CppHeaderParser._CppHeader.finalize` (`CppHeaderParser/CppHeaderParser.py`): 15 inputs
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
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.20: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T20:42:39+00:00, issue sha256 `4724e29bf19bd7b12356b9564237c5a21835feb338ed71b5f59b67ad0c09f3b1`

</details>
