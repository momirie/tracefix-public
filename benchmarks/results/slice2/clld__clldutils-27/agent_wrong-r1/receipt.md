## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the issue and found inputs that break the fixed \`clldutils.badge.badge\`: labels or messages containing dashes (e.g. label='a-b', message='1-2', or message='X-X' with an empty label) are inserted unescaped, producing ambiguous shields.io URLs such as 'https:​//img.shields.io/badge/a-b-1-2-green.svg'.

**Why this level:** Break My Fix finding 1: an input that breaks clldutils.badge.badge; Break My Fix finding 2: an input that breaks clldutils.badge.badge

**Issue:** The \`badge\` function should be more flexible · **Repo:** testbed · **Base** `tf-base` (`ef7578f`) → **head** `tf-agent_wrong` (`de2de9d`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `badge(subject='', status='', color='green', message='1-2', l...` → `returns 'https://img.shields.io/badge/a-b-1-2-green.svg'` (before the fix: `returns 'https://img.shields.io/badge/--green.svg'`); breaks **three\_part\_path\_structure**: “Either {message}-{color} or {label}-{message}-{color}” (comment); 1 more input break it the same way; test: `findings/finding_1.py`
2. `badge(subject='', status='', color='green', message='X-X', l...` → `returns 'https://img.shields.io/badge/X-X-green.svg'` (before the fix: `returns 'https://img.shields.io/badge/--green.svg'`); breaks **two\_part\_path\_structure**: “Either {message}-{color} or {label}-{message}-{color}” (comment); test: `findings/finding_2.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.286, mutants 7, killed 2, survived 5 |
| `regressions` | `none_found` | compared 45, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 30 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 1, inputs tried 482, properties counted 8, findings 2 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 6; the rest in receipt.json)
- `clldutils/badge.py:57`: `         label = label or subject ` → `         label = subject or label ` made no test fail; no input tried behaved differently from the fix (`m-2fe994328634`)
- `clldutils/badge.py:58`: `         message = message or status ` → `         message = status or message ` made no test fail; no input tried behaved differently from the fix (`m-9860c2df9c8a`)
- `clldutils/badge.py:64`: `     if label and message and color: ` → `     if label and message: ` made no test fail; no input tried behaved differently from the fix (`m-0b31c94b0692`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 5 calls, 19,401 input and 7,264 output tokens, cost $0.2017 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.58 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.45 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 40.41 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no clldutils/...`
- `guard`: `not_guarded`, 99.36 s: the tests killed 2 of 7 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no clldutils/...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 2.5 s: none of the 45 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.43 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no clldutils/...`
- `behaviour_diff`: `inconclusive`, 18.71 s: nothing was compared: no input could be compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 87.06 s: 2 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 0.01 s: no candidate was confirmed (1 reported)
#### Break My Fix targets
- `clldutils.badge.badge` (`clldutils/badge.py`): 482 inputs
#### More changes no test noticed
- `clldutils/badge.py:98`: `         if label and message: ` → `         if label or message: ` made no test fail; no input tried behaved differently from the fix (`m-be6de0b29fed`)
- `clldutils/badge.py:70`: `     elif message: ` → `     elif message and not label: ` made no test fail; no input tried behaved differently from the fix (`m-a463202adae9`)
- `clldutils/badge.py:56`: `     if subject or status: ` → `     if subject and status: ` made no test fail; no input tried behaved differently from the fix (`m-5879b8965018`)
#### Fix lines run (report only)
- repro: 14 of 30 fix lines run
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
- guard: only the first 10 of 32 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.20: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T17:35:34+00:00, issue sha256 `c913352ff9bb8567fa821f844cf28c91afb6dce3dcf74333322b3030f3a03660`

</details>
