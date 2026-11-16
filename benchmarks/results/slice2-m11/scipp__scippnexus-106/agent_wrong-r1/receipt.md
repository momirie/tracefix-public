## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug: a test that fails before the fix passes after it, no regressions were found, and the changed lines were covered, but the guard stage reported the fix as not guarded and the mutation check did not reach the threshold needed for L2. Next, strengthen the tests so they pin down the new behaviour, for example by asserting that plain NXtransformations entries load as Va…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 1 of 3 mutants; 80% is needed

**Issue:** Improve loading of NXtransformations · **Repo:** testbed · **Base** `tf-base` (`6da5856`) → **head** `tf-agent_wrong` (`0f95efe`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.333, mutants 3, killed 1, survived 2 |
| `regressions` | `none_found` | compared 131, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 13 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 1, inputs tried 0, properties counted 2, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_on_head` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; logic: 0 of 1 killed; negate\_if: 1 of 1 killed; membership: 1 of 1 killed; reraise: 0 of 1 killed; no place for compare, constant, arithmetic, loop, drop\_call

### Changes no test noticed (3 of 4; the rest in receipt.json)
- `src/scippnexus/nexus_classes.py:46`: `if hasattr(obj, 'attrs') and 'transformation_type' in obj.at...` → `if hasattr(obj, 'attrs') or 'transformation_type' in obj.attrs:` made no test fail; not compared with the fix (`m-8f7ec819e6db`)
- `src/scippnexus/nexus_classes.py:46`: `if hasattr(obj, 'attrs') and 'transformation_type' in obj.at...` → `if hasattr(obj, 'attrs') and 'depends_on' in obj.attrs:` made no test fail; not compared with the fix (`m-5770a466caf3`)
- `src/scippnexus/nexus_classes.py:46`: `                 if hasattr(obj, 'attrs') and 'transformation... ` → `                 if hasattr(obj, 'attrs') or 'transformation_... ` made no test fail; not compared with the fix (`m-b5646cefccf1`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call); 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 34,554 input and 5,578 output tokens, cost $0.1963 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 4.59 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.23 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 10.77 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 62.94 s: the tests killed 1 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 5.08 s: none of the 131 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.25 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `skipped`, 0.12 s: the fix changes no function the behaviour diff can call
- `break_my_fix`: `inconclusive`, 12.7 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.01 s: no candidate was confirmed (1 reported)
- `blind`: `fails_on_head`, 17.19 s: attempt 1: fails the same way before and after the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### Break My Fix targets
- `scippnexus.nexus_classes.NXtransformations._getitem` (`src/scippnexus/nexus_classes.py`): 0 inputs (no object of NXtransformations was built: none was given, and no type hints make one)
#### More changes no test noticed
- `src/scippnexus/nexus_classes.py:56`: `                 content[key] = obj[select] ` → `                 raise\n                content[key] = obj[sel... ` made no test fail; not compared with the fix (`m-ed8ceda4694c`)
#### Fix lines run (report only)
- repro: 10 of 13 fix lines run
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call)
#### Notes
- guard: 5 of the 8 mutants were not run: the tests could no longer reach 80% even if they killed them all
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T20:23:18+00:00, issue sha256 `580d792de1b5b266fc794b770534eab9fb18479bb4fc838a0112ae4e830ae078`

</details>
