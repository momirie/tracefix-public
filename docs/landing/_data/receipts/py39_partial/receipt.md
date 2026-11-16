## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The original bug was reproduced and the fix now passes the guard with no regressions found, but Break My Fix found an input that still breaks it: ordinal(111) returns '111st' instead of '111th'. Look next at how the fix handles the teens exception for numbers above 100 (for example 111, 112, 113), likely by checking n % 100 rather than n itself.

**Why this level:** Break My Fix finding 1: an input that breaks standings.ordinal.ordinal

**Issue:** Final table says "11st place" · **Repo:** py39\_partial · **Base** `base` (`1c75aaf`) → **head** `head` (`d0df1eb`)\
**Isolation:** basic (bubblewrap (bwrap) is not installed)

> [!WARNING]
> - Generated tests ran with basic isolation only (no bubblewrap sandbox): tampering inside the watched folders is detected, but code could still read or write elsewhere on this machine, and a process that escaped could influence a later run. For untrusted changes run Tracefix in GitHub Actions or on Linux with bubblewrap.

### Counterexamples
1. `ordinal(n=111)` → `returns '111st'` (before the fix: `returns '111st'`); breaks **teens\_take\_th**: “A number ending in 11, 12 or 13 takes "th"” (docstring); 3 more inputs break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 0\.8, mutants 5, killed 4, survived 1 |
| `regressions` | `none_found` | compared 3, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 2 |
| `behaviour_diff` | `compared` | inputs compared 14, changes 3, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 426, properties counted 5, findings 1 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `standings.ordinal.ordinal` (`value`, 3 inputs): `returns '11st'` → `returns '11th'`; the Judge (advisory) calls it intended: The issue says 11 should read '11th', and the docstring lists "11th".; the Judge (advisory) calls it intended: The issue says 12 should read '12th', and the docstring lists "12th".; the Judge (advisory) calls it intended: The issue says 13 should read '13th', and the docstring lists "13th".

### Changes no test noticed
- `src/standings/ordinal.py:17`: `     if n in (11, 12, 13): ` → `     if n % 1000 in (11, 12, 13): ` made no test fail; no input tried behaved differently from the fix (`m-8597fce603ac`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 15,709 input and 2,932 output tokens, cost $0.1081 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 1.26 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.28 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 6.78 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `guarded`, 57.16 s: the reproduction test fails with the fix reverted, and the tests killed 4 of 5 mutants
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 1.09 s: none of the 3 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.47 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `compared`, 5.01 s: 14 input(s) compared on 1 function(s): 3 changed with the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `found`, 12.45 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 0.01 s: no candidate was confirmed (3 reported)
#### Break My Fix targets
- `standings.ordinal.ordinal` (`src/standings/ordinal.py`): 426 inputs
#### Fix lines run (report only)
- repro: 2 of 2 fix lines run
- pr\_test: 2 of 2 fix lines run
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
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.25: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T14:15:20+00:00, issue sha256 `d9aee825b5d699005e3f8345fdf550897cb337d0b8b76bf7de2bf97df369c567`

</details>
