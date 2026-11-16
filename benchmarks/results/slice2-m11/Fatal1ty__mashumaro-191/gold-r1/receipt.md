## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug, with a test that fails before the fix and passes after it, and found no regressions, no breaking inputs, and no integrity flags, but the fix was not guarded because the tests did not kill enough mutants to reach L2. Next, look at strengthening the tests around TypedDict schema generation under \`from \_\_future\_\_ import annotations\`, including the other affected test…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 0 of 3 mutants; 80% is needed

**Issue:** TypedDicts not working with \`from \_\_future\_\_ import annotations\` · **Repo:** testbed · **Base** `tf-base` (`c3c6739`) → **head** `tf-gold` (`4d84137`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 3, killed 0, survived 3 |
| `regressions` | `none_found` | compared 26251, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 33 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 5, inputs tried 3, properties counted 7, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 0 of 3 killed; logic: 0 of 2 killed; negate\_if: 2 of 3 killed; membership: 0 of 2 killed; no place for compare, constant, arithmetic, loop, drop\_call, reraise

### Changes no test noticed (3 of 11; the rest in receipt.json)
- `mashumaro/core/meta/helpers.py:784`: `     if not forward_module and referencing_object: ` → `     if forward_module and referencing_object: ` made no test fail; not compared with the fix (`m-c0bab31f278c`)
- `mashumaro/core/meta/helpers.py:784`: `     if not forward_module and referencing_object: ` → `     if not forward_module or referencing_object: ` made no test fail; not compared with the fix (`m-bca156079025`)
- `mashumaro/core/meta/helpers.py:792`: `             fallback,\n        )\n    else: ` → `             {},\n        )\n    else: ` made no test fail; not compared with the fix (`m-d204149a4396`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; the behaviour diff could not compare get\_forward\_ref\_referencing\_globals: new with the fix: nothing to compare; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 84,011 input and 9,460 output tokens, cost $0.4711 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 77.57 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.48 s: 3 changed module(s) imported from the copies (6 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 10.32 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 803.7 s: the tests killed 0 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 68.83 s: none of the 26251 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.79 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 4.06 s: nothing was compared: mashumaro/core/meta/helpers.py: module-level code that computes a value changed (line 86); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `none_found`, 22.68 s: no counterexample found in 3 inputs against 7 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.11 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 13.49 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### Break My Fix targets
- `mashumaro.core.meta.code.builder.CodeBuilder.evaluate_forward_ref` (`mashumaro/core/meta/code/builder.py`): 0 inputs (no object of CodeBuilder was built: none was given, and no type hints make one)
- `mashumaro.core.meta.helpers.get_function_arg_annotation` (`mashumaro/core/meta/helpers.py`): not attacked (no property to check it against)
- `mashumaro.core.meta.helpers.get_forward_ref_referencing_globals` (`mashumaro/core/meta/helpers.py`): 3 inputs
- `mashumaro.jsonschema.schema.Instance.derive` (`mashumaro/jsonschema/schema.py`): 0 inputs (every property was contradicted or could not run)
- `mashumaro.jsonschema.schema.on_special_typing_primitive` (`mashumaro/jsonschema/schema.py`): 0 inputs (nothing generated)
#### More changes no test noticed
- `mashumaro/core/meta/code/builder.py:337`: `         globalns = get_forward_ref_referencing_globals(\n    ... ` → `         return None ` made no test fail; not compared with the fix (`m-90b8f7d2ab21`)
- `mashumaro/core/meta/helpers.py:784`: `     if not forward_module and referencing_object: ` → `     if forward_module and referencing_object: ` made no test fail; not compared with the fix (`m-c0bab31f278c`)
- `mashumaro/core/meta/helpers.py:784`: `     if not forward_module and referencing_object: ` → `     if not (not forward_module and referencing_object): ` made no test fail; not compared with the fix (`m-d7c41beed7f2`)
- `mashumaro/core/meta/helpers.py:781`: `     if fallback is None: ` → `     if fallback is not None: ` made no test fail; not compared with the fix (`m-96c97b0d9787`)
- `mashumaro/core/meta/helpers.py:679`: `     parameters = inspect.signature(function).parameters\n    ... ` → `     return None ` made no test fail; not compared with the fix (`m-72d220f47b04`)
- `mashumaro/core/meta/helpers.py:784`: `     if not forward_module and referencing_object: ` → `     if not forward_module or referencing_object: ` made no test fail; not compared with the fix (`m-bca156079025`)
- `mashumaro/jsonschema/schema.py:456`: `         if evaluated is not None: ` → `         if evaluated is None: ` made no test fail; not compared with the fix (`m-a66b4ba342aa`)
- `mashumaro/core/meta/helpers.py:781`: `     if fallback is None:\n        fallback = {}\n    forward_m... ` → `     return {} ` made no test fail; not compared with the fix (`m-8351943bc056`)
#### Fix lines run (report only)
- repro: 20 of 33 fix lines run
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
- the behaviour diff could not compare get\_forward\_ref\_referencing\_globals: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 16 functions were shown
- guard: 5 of the 8 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 12 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: only the first 8 of 15 functions were shown
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T23:58:16+00:00, issue sha256 `0c15e5cd0b16660a6077861462066c7212260ea746e63cab9912935a626a3da4`

</details>
