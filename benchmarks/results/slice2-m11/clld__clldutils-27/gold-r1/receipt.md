## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the original issue, confirmed the fix guards it with no regressions found and full fix-line coverage, but Break My Fix found an input that breaks clldutils.badge.badge: badge(subject='a b', status='c', color='blue', markdown=False) returns 'https:​//img.shields.io/badge/a%20b-c-blue.svg'. Check how the fixed code escapes spaces and other special characters in subject/status…

**Why this level:** Break My Fix finding 1: an input that breaks clldutils.badge.badge

**Issue:** The \`badge\` function should be more flexible · **Repo:** testbed · **Base** `tf-base` (`ef7578f`) → **head** `tf-gold` (`a4659a7`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `badge(subject='a b', status='c', color='blue', markdown=False)` → `returns 'https://img.shields.io/badge/a%20b-c-blue.svg'` (before the fix: `returns 'https://img.shields.io/badge/a%20b-c-blue.svg'`); breaks **markdown\_embeds\_url**: “markdown=True” (signature); test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 0\.889, mutants 9, killed 8, survived 1 |
| `regressions` | `none_found` | compared 45, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 4 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 1, inputs tried 731, properties counted 8, findings 1 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_on_head` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; logic: 1 of 1 killed; constant: 1 of 1 killed; arithmetic: 1 of 1 killed; no place for compare, negate\_if, membership, loop, drop\_call, reraise

### Changes no test noticed
- `clldutils/badge.py:25`: `quote(subject), quote(status), color, fmt, '?' + urlencode(k...` → `subject, quote(status), color, fmt, '?' + urlencode(kw) if k...` made no test fail; no input tried behaved differently from the fix (`m-77f94a9b8feb`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 13,019 input and 5,147 output tokens, cost $0.1283 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.38 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.38 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 13.48 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no clldutils/...`
- `guard`: `guarded`, 77.84 s: the reproduction test fails with the fix reverted, and the tests killed 8 of 9 mutants
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no clldutils/...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 2.49 s: none of the 45 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.47 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no clldutils/...`
- `behaviour_diff`: `inconclusive`, 7.07 s: nothing was compared: no input could be compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 23.69 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.0 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_on_head`, 22.1 s: attempt 1: fails the same way before and after the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no clldutils/...`
#### Break My Fix targets
- `clldutils.badge.badge` (`clldutils/badge.py`): 731 inputs
#### Fix lines run (report only)
- repro: 4 of 4 fix lines run
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
- guard: 1 of the rule mutant kills were crashes on the mutated line
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.20: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T17:34:49+00:00, issue sha256 `c913352ff9bb8567fa821f844cf28c91afb6dce3dcf74333322b3030f3a03660`

</details>
