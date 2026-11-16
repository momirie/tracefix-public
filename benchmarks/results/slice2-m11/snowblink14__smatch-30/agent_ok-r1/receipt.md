## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproducing the TOP-property issue (TOP only counted correct when node labels also match) fails before the fix and passes after it, and no breaking inputs or integrity problems were found, but the evidence stays at L1 because the tests did not kill enough mutants of the fix. The most important next step is to strengthen the tests so they catch mutated versions of the changed lines, and to…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 0 of 3 mutants; 80% is needed

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
| `guard` | `not_guarded` | kill rate 0\.0, mutants 3, killed 0, survived 3 |
| `regressions` | `skipped` | compared 0, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 98 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 17, properties counted 8, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 2 killed; compare: 0 of 2 killed; constant: 0 of 2 killed; arithmetic: 0 of 2 killed; drop\_call: 1 of 1 killed; reraise: 0 of 1 killed; no place for logic, negate\_if, membership, loop

### Changes no test noticed (3 of 11; the rest in receipt.json)
- `amr.py:424`: `         attribute_list[0].append(["TOP", "TOP"]) ` → `         attribute_list[0].append(["TOP", ""]) ` made no test fail; not compared with the fix (`m-815a0808c232`)
- `amr.py:424`: `         attribute_list[0].append(["TOP", "TOP"]) ` → `         attribute_list[-1].append(["TOP", "TOP"]) ` made no test fail; not compared with the fix (`m-26f0f255cd48`)
- `amr.py:424`: `         attribute_list[0].append(["TOP", "TOP"]) ` → `         attribute_list[0].append(["top", "TOP"]) ` made no test fail; not compared with the fix (`m-1bd0a75dc1c5`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; regressions: skipped (no test the fix left untouched passed before it); Break My Fix could not attack debug\_matching: it takes no parameters to vary; Break My Fix could not attack test\_edge\_cases: it takes no parameters to vary; Break My Fix could not attack demonstrate\_fix: it takes no parameters to vary; and 4 more in receipt.json
- **Model use:** 7 calls, 63,959 input and 7,494 output tokens, cost $0.3333 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.2 s: base suite no\_tests
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.48 s: 4 changed module(s) imported from the copies (5 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 13.65 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `guard`: `not_guarded`, 125.58 s: the tests killed 0 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_top_i...`
  - 3 more command(s) in receipt.json
- `regressions`: `skipped`, 0.01 s: no test the fix left untouched passed before it
- `fix_line_coverage`: `ok`, 4.88 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
- `behaviour_diff`: `inconclusive`, 2.44 s: nothing was compared: debug\_matching.py: module-level code that computes a value changed (line 37, 38); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 6.98 s: no counterexample found in 17 inputs against 8 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.02 s: no candidate was confirmed (3 reported)
- `blind`: `reproduced`, 13.93 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
#### Break My Fix targets
- `amr.AMR.parse_AMR_line` (`amr.py`): 17 inputs
#### More changes no test noticed
- `debug_matching.py:37`: `if __name__ == "__main__":` → `if __name__ != "__main__":` made no test fail; not compared with the fix (`m-8b2c6bc624b5`)
- `amr.py:424`: `         attribute_list[0].append(["TOP", "TOP"]) ` → `         attribute_list[(-1)].append(["TOP", "TOP"]) ` made no test fail; not compared with the fix (`m-780104b1065c`)
- `final_demo.py:14`: `     print("=" * 50) ` → `     print("=" / 50) ` made no test fail; not compared with the fix (`m-ad3a33a09579`)
- `debug_matching.py:32`: `         print(f"Error: {e}") ` → `         raise\n        print(f"Error: {e}") ` made no test fail; not compared with the fix (`m-9b6f174d255d`)
- `debug_matching.py:13`: `     print("=== Debug Matching Process ===\n")\n    \n    amr1 ... ` → `     return None ` made no test fail; not compared with the fix (`m-8363d2d4e95d`)
- `edge_case_tests.py:54`: `if __name__ == "__main__":` → `if __name__ != "__main__":` made no test fail; not compared with the fix (`m-78e09af80f82`)
- `amr.py:424`: `         attribute_list[0].append(["TOP", "TOP"]) ` → `         attribute_list[1].append(["TOP", "TOP"]) ` made no test fail; not compared with the fix (`m-2bd6f18739b9`)
- `final_demo.py:38`: `     precision = match_num / test_num if test_num > 0 else 0 ` → `     precision = match_num * test_num if test_num > 0 else 0 ` made no test fail; not compared with the fix (`m-49aa63587f7a`)
#### Fix lines run (report only)
- repro: 1 of 98 fix lines run
- pr\_test: 1 of 98 fix lines run
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
- the behaviour diff could not compare debug\_matching: new with the fix: nothing to compare
- the behaviour diff could not compare test\_edge\_cases: new with the fix: nothing to compare
- the behaviour diff could not compare demonstrate\_fix: new with the fix: nothing to compare
#### Notes
- guard: 3 of the 6 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 97 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.20: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T17:18:31+00:00, issue sha256 `e4406d58dca2359f4a498c2ed346d366242aa580c0b28eae3d74ccf67985e987`

</details>
