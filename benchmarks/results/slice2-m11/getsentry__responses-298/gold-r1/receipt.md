## Fix Receipt: L2 (L1, and the tests notice the fix being undone)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproduced the missing regex support in add\_passthru (failing before the fix and passing after), and the tests fail when the fix is reverted or broken, with no regressions or breaking inputs found. The behaviour comparison for add\_passthru, \_on\_request and start did not finish, so a reviewer should check by hand how the new regex matching changes passthru decisions for existing string pref…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; the tests guard the fix: they fail when it is reverted or broken; not L3: RequestsMock.add\_passthru: the comparison did not finish; not L3: RequestsMock.\_on\_request: the comparison did not finish; not L3: RequestsMock.start: no input could be compared

**Issue:** ability to pass a regex to add\_passthru · **Repo:** testbed · **Base** `tf-base` (`b741b6e`) → **head** `tf-gold` (`1a01713`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `guarded` | kill rate 0\.833, mutants 6, killed 5, survived 1 |
| `regressions` | `none_found` | compared 54, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 7 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 3, inputs tried 189, properties counted 8, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_differently` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 2 of 2 killed; logic: 2 of 2 killed; negate\_if: 1 of 1 killed; no place for compare, constant, arithmetic, membership, loop, drop\_call, reraise

### Changes no test noticed
- `responses.py:541`: `         if not isinstance(prefix, Pattern) and _has_unicode(... ` → `         if not isinstance(prefix, Pattern): ` made no test fail; not compared with the fix (`m-2a6c5ca6fa4a`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 52,106 input and 6,965 output tokens, cost $0.2923 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 3.05 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.74 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 36.29 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `guard`: `guarded`, 66.73 s: the reproduction test fails with the fix reverted, and the tests killed 5 of 6 mutants
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 10.2 s: none of the 54 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.54 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `behaviour_diff`: `inconclusive`, 7.54 s: nothing was compared: RequestsMock.add\_passthru: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 11.4 s: no counterexample found in 189 inputs against 8 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_respo...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_differently`, 18.41 s: attempt 1: fails after the fix too, but differently
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
#### Break My Fix targets
- `responses.RequestsMock.add_passthru` (`responses.py`): 189 inputs
- `responses.RequestsMock._on_request` (`responses.py`): not attacked (no property to check it against)
- `responses.RequestsMock.start` (`responses.py`): not attacked (no property to check it against); a public caller of the changed RequestsMock.\_on\_request
#### Fix lines run (report only)
- repro: 6 of 7 fix lines run
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
- reproduce: style example test\_responses.py truncated to 6000 characters for the prompt
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.20: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: style example test\_responses.py truncated to 6000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T23:51:43+00:00, issue sha256 `403cb9241b39e66739ca4aa2b04bf4b2563dc40e3a17965496459df16aaacc08`

</details>
