## Fix Receipt: L2 (L1, and the tests notice the fix being undone)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): At L2, a test reproduced the garage duct-location mapping bug (failing before the fix and passing after), and the tests fail again when the fix is reverted or broken, with no regressions found. Behaviour comparison was skipped because the change is to a module-level mapping in hescorehpxml/hpxml2.py, so next check that code relying on that mapping (and the Read the Docs HVAC distribution page the…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; the tests guard the fix: they fail when it is reverted or broken; not L3: hescorehpxml/hpxml2.py: module-level code that computes a value changed (line 185); what uses it is not compared; not L3: no changed function was compared

**Issue:** Duct Location - Garage - HPXML Translator Mapping Adjustment · **Repo:** testbed · **Base** `tf-base` (`644f8f8`) → **head** `tf-gold` (`01adc51`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 1\.0, mutants 7, killed 7, survived 0 |
| `regressions` | `none_found` | compared 224, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 1 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_on_head` | attempts 2, report only True |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call); break\_my\_fix: skipped (the fix changes no function Break My Fix can call); 9 things the behaviour diff can't observe (run log)
- **Model use:** 5 calls, 6,251 input and 3,290 output tokens, cost $0.0496 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 10.26 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.57 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 10.12 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `guarded`, 30.94 s: the reproduction test fails with the fix reverted, and the tests killed 7 of 7 mutants
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `regressions`: `none_found`, 10.29 s: none of the 224 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.16 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `skipped`, 0.11 s: the fix changes no function the behaviour diff can call
- `break_my_fix`: `skipped`, 0.01 s: the fix changes no function Break My Fix can call
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_on_head`, 31.6 s: attempt 2: fails the same way before and after the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call)
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call)
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T22:38:00+00:00, issue sha256 `9ff81d9c32e8122cb4a8f603e2b5c484af41f889544a7360f6cb5fc4d4fd9462`

</details>
