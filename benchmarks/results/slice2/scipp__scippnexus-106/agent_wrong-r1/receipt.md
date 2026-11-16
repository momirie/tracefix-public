## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug: a test that fails before the fix passes after it, no regressions were found, and the changed lines were covered, but the guard stage reported the fix as not guarded and the mutation check did not reach the threshold needed for L2. Next, strengthen the tests so they pin down the new behaviour, for example by asserting that plain NXtransformations entries load as Va…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 6 mutants; 80% is needed

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
| `guard` | `not_guarded` | kill rate 0\.333, mutants 6, killed 2, survived 4 |
| `regressions` | `none_found` | compared 131, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 13 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 1, inputs tried 0, properties counted 2, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 5; the rest in receipt.json)
- `src/scippnexus/nexus_classes.py:46`: `                 if hasattr(obj, 'attrs') and 'transformation... ` → `                 if hasattr(obj, 'attrs') and 'depends_on' in... ` made no test fail; not compared with the fix (`m-39eac5a9f3c5`)
- `src/scippnexus/nexus_classes.py:49`: `                     content[key] = transform[select]  # Proc... ` → `                     content[key] = transform[()]  # Process ... ` made no test fail; not compared with the fix (`m-d322435562e1`)
- `src/scippnexus/nexus_classes.py:52`: `                     content[key] = obj[select] ` → `                     content[key] = obj[()] ` made no test fail; not compared with the fix (`m-e7f6c5b548ca`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call); 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 24,542 input and 4,099 output tokens, cost $0.1408 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 7.73 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.86 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 23.85 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 86.13 s: the tests killed 2 of 6 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 6.65 s: none of the 131 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.37 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `skipped`, 0.1 s: the fix changes no function the behaviour diff can call
- `break_my_fix`: `inconclusive`, 28.06 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.01 s: no candidate was confirmed (1 reported)
#### Break My Fix targets
- `scippnexus.nexus_classes.NXtransformations._getitem` (`src/scippnexus/nexus_classes.py`): 0 inputs
#### More changes no test noticed
- `src/scippnexus/nexus_classes.py:46`: `                 if hasattr(obj, 'attrs') and 'transformation... ` → `                 if hasattr(obj, 'attrs') or 'transformation_... ` made no test fail; not compared with the fix (`m-b5646cefccf1`)
- `src/scippnexus/nexus_classes.py:46`: `                 if hasattr(obj, 'attrs') and 'transformation... ` → `                 if hasattr(obj, 'attrs') or 'transformation_... ` made no test fail; not compared with the fix (`m-b5646cefccf1`)
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
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T16:37:48+00:00, issue sha256 `580d792de1b5b266fc794b770534eab9fb18479bb4fc838a0112ae4e830ae078`

</details>
