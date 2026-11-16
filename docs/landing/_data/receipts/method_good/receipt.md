## Fix Receipt: L4 (L3, and Break My Fix found no counterexample)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): At L4, a test reproduced the minor-bump bug (1.2.3 becoming 1.3.3 instead of 1.3.0), passes after the fix, and fails when the fix is reverted or broken; Break My Fix found no breaking inputs, and the only behaviour change, in Version.bump, was labelled intended. Next, check that the tests also cover the patch reset on other bump paths, such as major bumps, since the issue only described the minor…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; the tests guard the fix: they fail when it is reverted or broken; the behaviour diff found no unexplained change in what it observes; Break My Fix attacked every changed function to the end and found nothing

**Issue:** Minor bump keeps the old patch number · **Repo:** method\_good · **Base** `base` (`daec69a`) → **head** `head` (`4b38a3a`)\
**Isolation:** basic (bubblewrap (bwrap) is not installed)

> [!WARNING]
> - Generated tests ran with basic isolation only (no bubblewrap sandbox): tampering inside the watched folders is detected, but code could still read or write elsewhere on this machine, and a process that escaped could influence a later run. For untrusted changes run Tracefix in GitHub Actions or on Linux with bubblewrap.

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 1\.0, mutants 5, killed 5, survived 0 |
| `regressions` | `none_found` | compared 5, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 1 |
| `behaviour_diff` | `compared` | inputs compared 155, changes 3, groups 1 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 1255, properties counted 9, findings 0 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `vtools.version.Version.bump` (`value`, 3 inputs): `returns Version(major=1, minor=3, patch=3)` → `returns Version(major=1, minor=3, patch=0)`; explained by: the reproduction test calls this input; the issue names this call; it now keeps the docstring example \`&gt;&gt;&gt; Version(1, 2, 3).bump("minor") Version(major=1, minor=3, patch=0)\`; the Judge (advisory) calls it intended: The issue names this call and expects 1.3.0; the docstring example now holds.; the Judge (advisory) calls it intended: The docstring says bumping "minor" resets patch; this is the same rule the issue reports, on another input.; the Judge (advisory) calls it intended: The docstring's "minor resets patch" rule from the issue, applied to a different patch value.

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 16,966 input and 3,444 output tokens, cost $0.1237 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 1.03 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 1.92 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 6.0 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `guarded`, 42.91 s: the reproduction test fails with the fix reverted, and the tests killed 5 of 5 mutants
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_version.py`
- `regressions`: `none_found`, 0.95 s: none of the 5 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 2.96 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_version.py`
- `behaviour_diff`: `compared`, 5.95 s: 155 input(s) compared on 1 function(s): 3 changed with the fix
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `none_found`, 128.96 s: no counterexample found in 1255 inputs against 9 properties
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_version.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `vtools.version.Version.bump` (`src/vtools/version.py`): 1,255 inputs
#### Fix lines run (report only)
- repro: 1 of 1 fix lines run
- pr\_test: 1 of 1 fix lines run
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
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T14:08:50+00:00, issue sha256 `232692d1b25c5c959b6a0f543bcf71a10fad15ab46efcd72539a0bb739859d06`

</details>
