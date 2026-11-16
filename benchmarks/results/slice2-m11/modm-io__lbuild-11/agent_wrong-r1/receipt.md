## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproducing the missing error for non-existent module names failed before the fix and passes after it, no regressions were found, and Break My Fix found no inputs that break the fixed code. The next thing to look at is the guard stage, which reported the fix as not guarded, along with the inconclusive behaviour diff; the verifier's L2 note on mutant kills is garbled ("N of N", "N%"), so ch…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 0 of 3 mutants; 80% is needed

**Issue:** No warning/error on non-existing modules · **Repo:** testbed · **Base** `tf-base` (`b279753`) → **head** `tf-agent_wrong` (`84391a9`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 3, killed 0, survived 3 |
| `regressions` | `none_found` | compared 78, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 20 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 2, properties counted 1, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; compare: 0 of 1 killed; logic: 1 of 2 killed; negate\_if: 2 of 2 killed; constant: 1 of 1 killed; membership: 1 of 1 killed; loop: 0 of 1 killed; drop\_call: 1 of 1 killed; no place for arithmetic, reraise

### Changes no test noticed (3 of 6; the rest in receipt.json)
- `lbuild/parser.py:222`: `             if '*' in query or query.startswith(':'): ` → `             if '*' in query and query.startswith(':'): ` made no test fail; not compared with the fix (`m-0c5392696211`)
- `lbuild/parser.py:222`: `             if '*' in query or query.startswith(':'): ` → `             if '*' in query: ` made no test fail; not compared with the fix (`m-a5a2d402919f`)
- `lbuild/parser.py:222`: `             if '*' in query or query.startswith(':'): ` → `             if query.startswith(':'): ` made no test fail; not compared with the fix (`m-bee56dadb972`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 32,966 input and 5,286 output tokens, cost $0.1995 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.01 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.38 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 6.67 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `guard`: `not_guarded`, 46.7 s: the tests killed 0 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 2.16 s: none of the 78 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 1.74 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `behaviour_diff`: `inconclusive`, 1.73 s: nothing was compared: Parser.find\_modules: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 9.23 s: no counterexample found in 2 inputs against 1 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 13.25 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
#### Break My Fix targets
- `lbuild.parser.Parser.find_modules` (`lbuild/parser.py`): 2 inputs
#### More changes no test noticed
- `lbuild/parser.py:228`: `                 if node.fullname == query: ` → `                 if node.fullname != query: ` made no test fail; not compared with the fix (`m-bdb6f42a84db`)
- `lbuild/parser.py:222`: `             if '*' in query or query.startswith(':'): ` → `             if '*' in query and query.startswith(':'): ` made no test fail; not compared with the fix (`m-0c5392696211`)
- `lbuild/parser.py:223`: `                 continue ` → `                 break ` made no test fail; not compared with the fix (`m-4c03d8c40b3f`)
#### Fix lines run (report only)
- repro: 15 of 20 fix lines run
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
- guard: 5 of the 8 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 13 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T18:44:17+00:00, issue sha256 `af40b9e724e04233c0fa87d489d19ba3aa3839edfdadcdac56b8005608788cbc`

</details>
