## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproduced the TypedDict-with-postponed-annotations failure before the fix and passed after it, with no regressions found and the changed lines covered; the evidence stays at L1 because the tests did not kill enough mutants to show they guard the fix. Next, look at strengthening the tests so they fail when the fix is altered, and check the other cases named in the issue (named tuples and o…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 0 of 8 mutants; 80% is needed

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
| `guard` | `not_guarded` | kill rate 0\.0, mutants 8, killed 0, survived 8 |
| `regressions` | `none_found` | compared 26251, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 33 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 5, inputs tried 0, properties counted 9, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 15; the rest in receipt.json)
- `mashumaro/core/meta/helpers.py:784`: `     if not forward_module and referencing_object: ` → `     if forward_module and referencing_object: ` made no test fail; not compared with the fix (`m-c0bab31f278c`)
- `mashumaro/core/meta/helpers.py:784`: `     if not forward_module and referencing_object: ` → `     if not forward_module or referencing_object: ` made no test fail; not compared with the fix (`m-bca156079025`)
- `mashumaro/core/meta/helpers.py:790`: `             sys.modules.get(referencing_object.__module__, N... ` → `             sys.modules.get(referencing_object.__class__.__m... ` made no test fail; not compared with the fix (`m-c99310fe4983`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; the behaviour diff could not compare get\_forward\_ref\_referencing\_globals: new with the fix: nothing to compare; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 77,142 input and 9,200 output tokens, cost $0.4554 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 63.0 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.08 s: 3 changed module(s) imported from the copies (6 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 13.64 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 965.23 s: the tests killed 0 of 8 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 66.28 s: none of the 26251 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.72 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 3.9 s: nothing was compared: mashumaro/core/meta/helpers.py: module-level code that computes a value changed (line 86); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 81.87 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.1 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `mashumaro.core.meta.code.builder.CodeBuilder.evaluate_forward_ref` (`mashumaro/core/meta/code/builder.py`): 0 inputs
- `mashumaro.core.meta.helpers.get_function_arg_annotation` (`mashumaro/core/meta/helpers.py`): not attacked (no property to check it against)
- `mashumaro.core.meta.helpers.get_forward_ref_referencing_globals` (`mashumaro/core/meta/helpers.py`): 0 inputs
- `mashumaro.jsonschema.schema.Instance.derive` (`mashumaro/jsonschema/schema.py`): 0 inputs
- `mashumaro.jsonschema.schema.on_special_typing_primitive` (`mashumaro/jsonschema/schema.py`): 0 inputs
#### More changes no test noticed
- `mashumaro/core/meta/helpers.py:795`: `         return getattr(forward_module, "__dict__", fallback) ` → `         return fallback ` made no test fail; not compared with the fix (`m-f9e5da9a85a1`)
- `mashumaro/core/meta/helpers.py:781`: `     if fallback is None: ` → `     if fallback is not None: ` made no test fail; not compared with the fix (`m-96c97b0d9787`)
- `mashumaro/core/meta/code/builder.py:338`: `             typ, owner, self.globals ` → `             typ, None, self.globals ` made no test fail; not compared with the fix (`m-98b76b793b6f`)
- `mashumaro/jsonschema/schema.py:148`: `                 get_forward_ref_referencing_globals(new_type... ` → `                 get_forward_ref_referencing_globals(new_type), ` made no test fail; not compared with the fix (`m-fbf7d0ca6813`)
- `mashumaro/jsonschema/schema.py:453`: `             get_forward_ref_referencing_globals(instance.type), ` → `             get_forward_ref_referencing_globals(instance.typ... ` made no test fail; not compared with the fix (`m-163e3ad42cd9`)
- `mashumaro/core/meta/code/builder.py:337`: `         globalns = get_forward_ref_referencing_globals(\n    ... ` → `         return None ` made no test fail; not compared with the fix (`m-90b8f7d2ab21`)
- `mashumaro/core/meta/helpers.py:679`: `     parameters = inspect.signature(function).parameters\n    ... ` → `     return None ` made no test fail; not compared with the fix (`m-72d220f47b04`)
- `mashumaro/core/meta/helpers.py:781`: `     if fallback is None:\n        fallback = {}\n    forward_m... ` → `     return {} ` made no test fail; not compared with the fix (`m-8351943bc056`)
- `mashumaro/core/meta/helpers.py:781`: `     if fallback is None: ` → `     if fallback is not None: ` made no test fail; not compared with the fix (`m-96c97b0d9787`)
- `mashumaro/core/meta/helpers.py:784`: `     if not forward_module and referencing_object: ` → `     if forward_module and referencing_object: ` made no test fail; not compared with the fix (`m-c0bab31f278c`)
- `mashumaro/core/meta/helpers.py:784`: `     if not forward_module and referencing_object: ` → `     if not (not forward_module and referencing_object): ` made no test fail; not compared with the fix (`m-d7c41beed7f2`)
- `mashumaro/core/meta/helpers.py:784`: `     if not forward_module and referencing_object: ` → `     if not forward_module or referencing_object: ` made no test fail; not compared with the fix (`m-bca156079025`)
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
- guard: only the first 10 of 12 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T22:28:31+00:00, issue sha256 `0c15e5cd0b16660a6077861462066c7212260ea746e63cab9912935a626a3da4`

</details>
