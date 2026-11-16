## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproducing the TOP-property bug failed before the fix and passed after it, but the existing suite could not run cleanly on the fixed code, so the guard, regression, and behaviour-diff checks were inconclusive or skipped and the mutation rate is incomplete. Next, get the existing test suite running on the fixed code so regressions and mutant kill rate can actually be measured.

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 0 of 3 mutants; 80% is needed, but the existing suite could not run cleanly on the fixed code, so the rate is incomplete

**Issue:** interpretation of TOP property · **Repo:** testbed · **Base** `tf-base` (`e045328`) → **head** `tf-gold` (`b62eed0`)\
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
| `fix_line_coverage` | `ok` | fix lines 1 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 28, properties counted 8, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 5; the rest in receipt.json)
- `amr.py:424`: `         attribute_list[0].append(["TOP", 'top']) ` → `         attribute_list[-1].append(["TOP", 'top']) ` made no test fail; not compared with the fix (`m-0c4e4172e04e`)
- `amr.py:424`: `         attribute_list[0].append(["TOP", 'top']) ` → `         attribute_list[0].append(["TOP", 'TOP']) ` made no test fail; not compared with the fix (`m-977359dc218e`)
- `amr.py:424`: `         attribute_list[0].append(["TOP", 'top']) ` → `         attribute_list[0].append(['top', "TOP"]) ` made no test fail; not compared with the fix (`m-61815774dbe9`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; regressions: skipped (no test the fix left untouched passed before it); 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 39,458 input and 6,347 output tokens, cost $0.2496 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 3.57 s: base suite no\_tests
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 6.35 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 28.64 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `guard`: `inconclusive`, 58.34 s: the tests killed 0 of 3 mutants; 80% is needed, but the existing suite could not run cleanly on the fixed code, so the rate is incomplete
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `skipped`, 0.0 s: no test the fix left untouched passed before it
- `fix_line_coverage`: `ok`, 3.59 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `behaviour_diff`: `inconclusive`, 3.41 s: nothing was compared: AMR.parse\_AMR\_line: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 57.69 s: no counterexample found in 28 inputs against 8 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `amr.AMR.parse_AMR_line` (`amr.py`): 28 inputs
#### More changes no test noticed
- `amr.py:424`: `         attribute_list[0].append(["TOP", 'top']) ` → `         attribute_list[(-1)].append(["TOP", 'top']) ` made no test fail; not compared with the fix (`m-ce0d56295915`)
- `amr.py:424`: `         attribute_list[0].append(["TOP", 'top']) ` → `         attribute_list[1].append(["TOP", 'top']) ` made no test fail; not compared with the fix (`m-3c66c29003a0`)
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
- regressions: skipped (no test the fix left untouched passed before it)
#### Notes
- guard: the existing suite did not run cleanly on the fixed code
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.20: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T17:12:27+00:00, issue sha256 `e4406d58dca2359f4a498c2ed346d366242aa580c0b28eae3d74ccf67985e987`

</details>
