## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The original bug was reproduced and the fix guards against it with no regressions found, but Break My Fix found that days\_in\_month(year=2200, month=2) still returns 29, so the leap-year logic appears to handle 2100 but not other century years. Look next at the century/400-year rule in billing.calendar.days\_in\_month and add a test covering years like 2200 and 2000.

**Why this level:** Break My Fix finding 1: an input that breaks billing.calendar.days\_in\_month

**Issue:** Lease schedule contains a payment on 29 Feb 2100 · **Repo:** special\_cased · **Base** `base` (`9e0465b`) → **head** `head` (`5678c1f`)\
**Isolation:** basic (bubblewrap (bwrap) is not installed)

> [!WARNING]
> - Generated tests ran with basic isolation only (no bubblewrap sandbox): tampering inside the watched folders is detected, but code could still read or write elsewhere on this machine, and a process that escaped could influence a later run. For untrusted changes run Tracefix in GitHub Actions or on Linux with bubblewrap.

### Counterexamples
1. `days_in_month(year=2200, month=2)` → `returns 29` (before the fix: `returns 29`); breaks **matches\_gregorian\_calendar**: “Return the number of days in \`month\` (1-12) of \`year\`.” (docstring); 3 more inputs break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 0\.833, mutants 6, killed 5, survived 1 |
| `regressions` | `none_found` | compared 5, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 2 |
| `behaviour_diff` | `compared` | inputs compared 276, changes 1, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 855, properties counted 7, findings 1 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `billing.calendar.days_in_month` (`value`, 1 input): `returns 29` → `returns 28`; the Judge (advisory) calls it intended: The issue reports that 29 Feb 2100 does not exist, so February 2100 must have 28 days. The hardcoded special case is a narrow fix, but this specific input's change is exactly what the issue asks for.

### Changes no test noticed
- `src/billing/calendar.py:19`: `     if year == 2100 and month == 2: ` → `     if year >= 2100 and month == 2: ` made no test fail; behaves differently from the fix on inputs no test checks (`m-96df6c7e78cb`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 15,182 input and 3,535 output tokens, cost $0.1175 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 0.93 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 1.88 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 5.87 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `guarded`, 29.84 s: the reproduction test fails with the fix reverted, and the tests killed 5 of 6 mutants
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 1.01 s: none of the 5 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 1.4 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `compared`, 6.53 s: 276 input(s) compared on 1 function(s): 1 changed with the fix
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `found`, 11.08 s: 1 finding(s), each proven by a failing repro file
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_finding_1.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_calendar.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 2.72 s: no candidate was confirmed (1 reported)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
#### Break My Fix targets
- `billing.calendar.days_in_month` (`src/billing/calendar.py`): 855 inputs
#### Fix lines run (report only)
- repro: 2 of 2 fix lines run
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
- guard: only the first 10 of 12 rule mutants were run
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T14:16:49+00:00, issue sha256 `565ea0aae1a7ea87d95618a69da5d38edbb0bcbe44570c0fa07278726dd1949c`

</details>
