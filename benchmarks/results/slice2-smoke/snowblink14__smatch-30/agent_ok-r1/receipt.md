## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproducing the TOP-property issue failed before the fix and passes after it, but the evidence stops at L1 because the tests did not kill enough mutants, and the guard, behaviour-diff, and break-my-fix stages were not conclusive (regressions were skipped). Next, strengthen the tests so they distinguish the fix from mutated versions, for example by asserting that a TOP match is credited eve…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 1 of 3 mutants; 80% is needed

**Issue:** interpretation of TOP property · **Repo:** testbed · **Base** `tf-base` (`e045328`) → **head** `tf-agent_ok` (`4cddf2d`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite no\_tests |
| `import_check` | `ok` | modules 4 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.333, mutants 3, killed 1, survived 2 |
| `regressions` | `skipped` | compared 0, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 98 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 11; the rest in receipt.json)
- `amr.py:424`: `         attribute_list[0].append(["TOP", "TOP"]) ` → `         attribute_list[-1].append(["TOP", "TOP"]) ` made no test fail; not compared with the fix (`m-26f0f255cd48`)
- `amr.py:424`: `         attribute_list[0].append(["TOP", "TOP"]) ` → `         attribute_list[0].append(["TOP", "TOP"]) if not attr... ` made no test fail; not compared with the fix (`m-1f12f011c2c2`)
- `debug_matching.py:13`: `     print("=== Debug Matching Process ===\n")\n    \n    amr1 ... ` → `     return None ` made no test fail; not compared with the fix (`m-8363d2d4e95d`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; regressions: skipped (no test the fix left untouched passed before it); Break My Fix could not attack debug\_matching: it takes no parameters to vary; Break My Fix could not attack test\_edge\_cases: it takes no parameters to vary; Break My Fix could not attack demonstrate\_fix: it takes no parameters to vary; and 1 more in receipt.json
- **Model use:** 4 calls, 32,340 input and 1,318 output tokens, cost $0.0818 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.24 s: base suite no\_tests
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.3 s: 4 changed module(s) imported from the copies (5 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 18.42 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `guard`: `not_guarded`, 121.49 s: the tests killed 1 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_top_i...`
  - 3 more command(s) in receipt.json
- `regressions`: `skipped`, 0.01 s: no test the fix left untouched passed before it
- `fix_line_coverage`: `ok`, 0.01 s: report only: which fix lines the tests run
- `behaviour_diff`: `inconclusive`, 0.02 s: the behaviour diff can't run in the project's Python: the project's Python has Hypothesis 6.119.3, older than 6.141, the oldest Tracefix is tested with: upgrade it there (python -m pip install -U hypothesis)
- `break_my_fix`: `inconclusive`, 0.02 s: Break My Fix can't run in the project's Python: the project's Python has Hypothesis 6.119.3, older than 6.141, the oldest Tracefix is tested with: upgrade it there (python -m pip install -U hypothesis)
- `integrity`: `clean`, 0.03 s: no candidate was confirmed (3 reported)
#### More changes no test noticed
- `edge_case_tests.py:13`: `     print("=== Edge Case Tests ===\n")\n    \n    # Edge Case ... ` → `     return None ` made no test fail; not compared with the fix (`m-976b33e41fec`)
- `final_demo.py:13`: `     print("🔧 SMATCH TOP Property Fix Demonstration")\n    pri... ` → `     return None ` made no test fail; not compared with the fix (`m-9ac2967c1731`)
- `amr.py:424`: `         attribute_list[0].append(["TOP", "TOP"]) ` → `         attribute_list[(-1)].append(["TOP", "TOP"]) ` made no test fail; not compared with the fix (`m-780104b1065c`)
- `amr.py:424`: `         attribute_list[0].append(["TOP", "TOP"]) ` → `         attribute_list[1].append(["TOP", "TOP"]) ` made no test fail; not compared with the fix (`m-2bd6f18739b9`)
- `debug_matching.py:23`: `     smatch.verbose = True ` → `     smatch.verbose = False ` made no test fail; not compared with the fix (`m-7ebc8fbc4379`)
- `debug_matching.py:24`: `     smatch.veryVerbose = True ` → `     smatch.veryVerbose = False ` made no test fail; not compared with the fix (`m-59a33eeec548`)
- `debug_matching.py:34`: `         smatch.verbose = False ` → `         smatch.verbose = True ` made no test fail; not compared with the fix (`m-356325b4c897`)
- `debug_matching.py:35`: `         smatch.veryVerbose = False ` → `         smatch.veryVerbose = True ` made no test fail; not compared with the fix (`m-c8361e7489eb`)
#### Fix lines run (report only)
- not measured: the project's Python has Hypothesis 6.119.3, older than 6.141, the oldest Tracefix is tested with: upgrade it there (python -m pip install -U hypothesis)
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
- Break My Fix could not attack debug\_matching: it takes no parameters to vary
- Break My Fix could not attack test\_edge\_cases: it takes no parameters to vary
- Break My Fix could not attack demonstrate\_fix: it takes no parameters to vary
#### Notes
- guard: only the first 10 of 42 rule mutants were run
- fix\_line\_coverage: not measured: the project's Python has Hypothesis 6.119.3, older than 6.141, the oldest Tracefix is tested with: upgrade it there (python -m pip install -U hypothesis)
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T11:11:30+00:00, issue sha256 `e4406d58dca2359f4a498c2ed346d366242aa580c0b28eae3d74ccf67985e987`

</details>
