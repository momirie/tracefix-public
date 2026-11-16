## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug with a test that fails before the fix and passes after it, with no regressions found and the fix lines covered, but the tests did not kill enough mutants to reach L2 and the behaviour-diff and break-my-fix stages were inconclusive. Next, look at strengthening the tests so they would catch mutations of the fix, for example by covering the other cases the issue lists…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 5 mutants; 80% is needed

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
| `guard` | `not_guarded` | kill rate 0\.4, mutants 5, killed 2, survived 3 |
| `regressions` | `none_found` | compared 26251, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 17 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 2, inputs tried 0, properties counted 5, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 4; the rest in receipt.json)
- `mashumaro/jsonschema/schema.py:668`: `         return evaluate_forward_ref(forward_ref, globalns, {}) ` → `         return evaluate_forward_ref(forward_ref, {}, {}) ` made no test fail; not compared with the fix (`m-93a19ccd8d9c`)
- `mashumaro/jsonschema/schema.py:672`: `         return forward_ref ` → `         return None ` made no test fail; not compared with the fix (`m-1a688dd44ef2`)
- `mashumaro/jsonschema/schema.py:687`: `             resolved_v = _evaluate_forward_ref(resolved_v, i... ` → `             resolved_v = _evaluate_forward_ref(resolved_v, i... ` made no test fail; not compared with the fix (`m-d10a0c0c9467`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; the behaviour diff could not compare \_evaluate\_forward\_ref: new with the fix: nothing to compare; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 44,157 input and 6,046 output tokens, cost $0.2713 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 65.49 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.36 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 14.93 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 474.74 s: the tests killed 2 of 5 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 63.4 s: none of the 26251 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.25 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 3.25 s: nothing was compared: on\_typed\_dict: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 52.5 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `mashumaro.jsonschema.schema.on_typed_dict` (`mashumaro/jsonschema/schema.py`): 0 inputs
- `mashumaro.jsonschema.schema._evaluate_forward_ref` (`mashumaro/jsonschema/schema.py`): 0 inputs
#### More changes no test noticed
- `mashumaro/jsonschema/schema.py:661`: `     if module_name: ` → `     if not (module_name): ` made no test fail; not compared with the fix (`m-8190f7246645`)
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
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T22:48:35+00:00, issue sha256 `0c15e5cd0b16660a6077861462066c7212260ea746e63cab9912935a626a3da4`

</details>
