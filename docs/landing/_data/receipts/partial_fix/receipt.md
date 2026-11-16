## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The original crash was reproduced and the fix guards against it (PORT unset no longer raises, with no regressions found), but Break My Fix found that parse\_port(raw='') still raises ValueError: invalid literal for int() with base 10: ''. Next, check whether an empty PORT value should also fall back to 8080 as the README describes, and handle that case.

**Why this level:** Break My Fix finding 1: an input that breaks svc.config.parse\_port

**Issue:** Service crashes at startup when PORT is not set · **Repo:** partial\_fix · **Base** `base` (`878c55e`) → **head** `head` (`8c47ba4`)\
**Isolation:** basic (bubblewrap (bwrap) is not installed)

> [!WARNING]
> - Generated tests ran with basic isolation only (no bubblewrap sandbox): tampering inside the watched folders is detected, but code could still read or write elsewhere on this machine, and a process that escaped could influence a later run. For untrusted changes run Tracefix in GitHub Actions or on Linux with bubblewrap.

### Counterexamples
1. `parse_port(raw='')` → `raises ValueError: invalid literal for int() with base 10: ''` (before the fix: `raises ValueError: invalid literal for int() with base 10: ''`); breaks **blank\_returns\_default**: “if unset or blank, DEFAULT\_PORT (8080) is used” (docstring); 3 more inputs break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 1\.0, mutants 4, killed 4, survived 0 |
| `regressions` | `none_found` | compared 5, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 2 |
| `behaviour_diff` | `compared` | inputs compared 200, changes 1, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 420, properties counted 6, findings 1 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `svc.config.parse_port` (`no_raise`, 1 input): `raises AttributeError` → `returns 8080`; explained by: the reproduction test calls this input; the Judge (advisory) calls it intended: The issue reports the AttributeError when PORT is unset, and the README and docstring say unset PORT falls back to 8080.

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 21,638 input and 4,057 output tokens, cost $0.1523 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 0.92 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 1.92 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 14.7 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `guarded`, 28.21 s: the reproduction test fails with the fix reverted, and the tests killed 4 of 4 mutants
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_config.py`
- `regressions`: `none_found`, 0.9 s: none of the 5 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 2.88 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_config.py`
- `behaviour_diff`: `compared`, 5.78 s: 200 input(s) compared on 1 function(s): 1 changed with the fix
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `found`, 18.35 s: 1 finding(s), each proven by a failing repro file
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_finding_1.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_config.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `svc.config.parse_port` (`src/svc/config.py`): 420 inputs
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
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T14:14:06+00:00, issue sha256 `6fd36ac7130d5fd14972921f51e524a021bc06704416a0b01561182e376f2c43`

</details>
