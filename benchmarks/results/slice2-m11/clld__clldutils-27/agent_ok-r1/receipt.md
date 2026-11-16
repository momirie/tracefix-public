## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproduced the issue, failing before the fix and passing after it, with no regressions found and no breaking inputs discovered, but the evidence stayed at L1 because the tests did not kill enough mutants and the guard stage reported the fix as not guarded. The most important next step is to strengthen the tests so they catch mutations of the new badge arguments, since the behaviour diff wa…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 3 of 6 mutants; 80% is needed

**Issue:** The \`badge\` function should be more flexible · **Repo:** testbed · **Base** `tf-base` (`ef7578f`) → **head** `tf-agent_ok` (`518c701`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.5, mutants 6, killed 3, survived 3 |
| `regressions` | `none_found` | compared 45, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 21 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 1072, properties counted 8, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_on_head` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; constant: 1 of 1 killed; membership: 4 of 4 killed; no place for compare, logic, negate\_if, arithmetic, loop, drop\_call, reraise

### Changes no test noticed
- `clldutils/badge.py:57`: `         url = '{0}{1}.{2}{3}'.format(base_url, path, fmt, qu... ` → `         url = '{0}{1}{2}{3}'.format(base_url, path, fmt, query) ` made no test fail; no input tried behaved differently from the fix (`m-9b76211e5c22`)
- `clldutils/badge.py:63`: `                 subject=quote(subject),  ` → `                 subject=subject,  ` made no test fail; no input tried behaved differently from the fix (`m-2f5dad54aeae`)
- `clldutils/badge.py:64`: `                 status=quote(status),  ` → `                 status=quote(subject),  ` made no test fail; no input tried behaved differently from the fix (`m-1aa9da26602a`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 17,705 input and 6,561 output tokens, cost $0.1707 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.43 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.41 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 13.7 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no clldutils/...`
- `guard`: `not_guarded`, 65.2 s: the tests killed 3 of 6 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no clldutils/...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 2.51 s: none of the 45 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.42 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no clldutils/...`
- `behaviour_diff`: `inconclusive`, 11.6 s: nothing was compared: no input could be compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 16.1 s: no counterexample found in 1072 inputs against 8 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.0 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_on_head`, 14.11 s: attempt 1: fails the same way before and after the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no clldutils/...`
#### Break My Fix targets
- `clldutils.badge.badge` (`clldutils/badge.py`): 1,072 inputs
#### Fix lines run (report only)
- repro: 10 of 21 fix lines run
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
- guard: 4 of the 10 mutants were not run: the tests could no longer reach 80% even if they killed them all
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.20: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T17:40:55+00:00, issue sha256 `c913352ff9bb8567fa821f844cf28c91afb6dce3dcf74333322b3030f3a03660`

</details>
