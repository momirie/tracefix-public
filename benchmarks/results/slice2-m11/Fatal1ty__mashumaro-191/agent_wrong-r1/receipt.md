## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproduced the TypedDict-with-postponed-annotations failure before the fix and passed after it, with no regressions found and the changed lines covered; the evidence stays at L1 because the tests did not kill enough mutants to show they guard the fix. Next, look at strengthening the tests so they fail when the fix is altered, and check the other cases named in the issue (named tuples and o…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 0 of 3 mutants; 80% is needed

**Issue:** TypedDicts not working with \`from \_\_future\_\_ import annotations\` · **Repo:** testbed · **Base** `tf-base` (`c3c6739`) → **head** `tf-agent_wrong` (`148f3c6`)\
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
| `regressions` | `none_found` | compared 26251, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 17 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 2, inputs tried 0, properties counted 5, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 2 of 2 killed; negate\_if: 1 of 2 killed; reraise: 0 of 1 killed; no place for compare, logic, constant, arithmetic, membership, loop, drop\_call

### Changes no test noticed (3 of 5; the rest in receipt.json)
- `mashumaro/jsonschema/schema.py:661`: `     if module_name: ` → `     if not module_name: ` made no test fail; not compared with the fix (`m-4b57c2f58d3d`)
- `mashumaro/jsonschema/schema.py:662`: `         globalns = getattr(sys.modules.get(module_name, None... ` → `         globalns = {} ` made no test fail; not compared with the fix (`m-c2c64a897e6a`)
- `mashumaro/jsonschema/schema.py:668`: `         return evaluate_forward_ref(forward_ref, globalns, {}) ` → `         return evaluate_forward_ref(forward_ref, {}, {}) ` made no test fail; not compared with the fix (`m-93a19ccd8d9c`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; the behaviour diff could not compare \_evaluate\_forward\_ref: new with the fix: nothing to compare; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 48,280 input and 6,611 output tokens, cost $0.2853 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 68.38 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.43 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 9.97 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 439.88 s: the tests killed 0 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 69.45 s: none of the 26251 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.45 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 3.49 s: nothing was compared: on\_typed\_dict: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 9.37 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 13.53 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### Break My Fix targets
- `mashumaro.jsonschema.schema.on_typed_dict` (`mashumaro/jsonschema/schema.py`): 0 inputs (nothing generated)
- `mashumaro.jsonschema.schema._evaluate_forward_ref` (`mashumaro/jsonschema/schema.py`): 0 inputs (nothing generated)
#### More changes no test noticed
- `mashumaro/jsonschema/schema.py:661`: `     if module_name: ` → `     if not (module_name): ` made no test fail; not compared with the fix (`m-8190f7246645`)
- `mashumaro/jsonschema/schema.py:672`: `         return forward_ref ` → `         raise\n        return forward_ref ` made no test fail; not compared with the fix (`m-e0684ad62737`)
#### Fix lines run (report only)
- repro: 14 of 17 fix lines run
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
- the behaviour diff could not compare \_evaluate\_forward\_ref: new with the fix: nothing to compare
#### Notes
- guard: 6 of the 9 mutants were not run: the tests could no longer reach 80% even if they killed them all
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-07T00:15:07+00:00, issue sha256 `0c15e5cd0b16660a6077861462066c7212260ea746e63cab9912935a626a3da4`

</details>
