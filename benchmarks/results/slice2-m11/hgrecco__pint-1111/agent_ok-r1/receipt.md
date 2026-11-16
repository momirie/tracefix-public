## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug: a test fails before the fix and passes after it. The fix still reached only L1, because the tests did not kill enough mutants for L2 and the behaviour-diff and break-my-fix stages were inconclusive, so the next step is to strengthen the tests around overlaying multiple context redefinitions of the same unit.

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 3 of 5 mutants; 80% is needed

**Issue:** Context redefinitions can't be overlayed · **Repo:** testbed · **Base** `tf-base` (`af723fa`) → **head** `tf-agent_ok` (`55f8ba9`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.6, mutants 5, killed 3, survived 2 |
| `regressions` | `none_found` | compared 283, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 1 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 3, inputs tried 4, properties counted 4, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; no place for compare, logic, negate\_if, constant, arithmetic, membership, loop, drop\_call, reraise

### Changes no test noticed
- `pint/registry.py:1550`: `             for ctx in reversed(self._active_ctx.contexts): ` → `             for ctx in reversed(self._active_ctx.contexts[:1]): ` made no test fail; not compared with the fix (`m-0ba1a34b88e6`)
- `pint/registry.py:1550`: `             for ctx in reversed(self._active_ctx.contexts): ` → `             for ctx in reversed(self._active_ctx.contexts[::... ` made no test fail; not compared with the fix (`m-ae9ca82f291e`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 50,513 input and 9,650 output tokens, cost $0.3449 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 13.68 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.58 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 8.94 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no pint/tests...`
- `guard`: `not_guarded`, 70.34 s: the tests killed 3 of 5 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no pint/tests...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 14.14 s: none of the 283 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.47 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no pint/tests...`
- `behaviour_diff`: `inconclusive`, 41.4 s: nothing was compared: no input could be compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `inconclusive`, 262.92 s: the attack on ContextRegistry.disable\_contexts did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.03 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 9.24 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no pint/tests...`
#### Break My Fix targets
- `pint.registry.ContextRegistry._switch_context_cache_and_units` (`pint/registry.py`): 1 input
- `pint.registry.ContextRegistry.enable_contexts` (`pint/registry.py`): 1 input; a public caller of the changed ContextRegistry.\_switch\_context\_cache\_and\_units
- `pint.registry.ContextRegistry.disable_contexts` (`pint/registry.py`): 2 inputs; its attack did not finish; a public caller of the changed ContextRegistry.\_switch\_context\_cache\_and\_units
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
#### Notes
- reproduce: style example pint/testsuite/test\_application\_registry.py truncated to 6000 characters for the prompt
- guard: 2 of the 7 mutants were not run: the tests could no longer reach 80% even if they killed them all
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: style example pint/testsuite/test\_application\_registry.py truncated to 6000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T18:33:08+00:00, issue sha256 `1d339d791f5547c6886a5bfd805f6e5ec345d248f31d41f3eb8e9a83b271961e`

</details>
