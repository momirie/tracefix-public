## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug with a test that fails before the fix and passes after it, and it found no regressions, no breaking inputs, and only behaviour changes judged intended. However, the PR's own test file tests/test\_trunc.py still passes with the fix reverted, so next look at adding a test there that actually fails on the old code (for example, asserting len(truncate('hello world', 5))…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the PR's test file tests/test\_trunc.py does not fail with the fix reverted (passed)

**Issue:** truncate() returns strings longer than max\_len · **Repo:** unguarded\_test · **Base** `base` (`47cc8c4`) → **head** `head` (`9f620ef`)\
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
| `guard` | `not_guarded` | kill rate 0\.2, mutants 5, killed 1, survived 4 |
| `regressions` | `none_found` | compared 4, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 2 |
| `behaviour_diff` | `compared` | inputs compared 287, changes 24, groups 1 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 990, properties counted 7, findings 0 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `textutil.trunc.truncate` (`value`, 24 inputs): `returns 'hello…'` → `returns 'hell…'`; explained by: the issue names this call; the Judge (advisory) calls it intended: The issue names this exact call: the result must not exceed max\_len=5, and 'hell…' is 5 characters.; the Judge (advisory) calls it intended: Same issue rule with a multi-character ellipsis: the old 11-character result exceeded max\_len=8, and the new one is exactly 8.; the Judge (advisory) calls it intended: The result must never exceed max\_len per the issue; with max\_len=0 the only fitting result is '', which the new docstring states.; the Judge (advisory) calls it intended: Same as the issue's example on a longer text: the 6-character result is cut to 5.; the Judge (advisory) calls it intended: max\_len=0 must give a result of at most 0 characters per the issue; the docstring says max\_len == 0 gives ''.; the Judge (advisory) calls it intended: A custom ellipsis longer than max\_len=0 is cut to fit, which is the issue's length rule; the docstring states it.; the Judge (advisory) calls it intended: Same max\_len=0 rule: the old 2-character result exceeded max\_len, and '' fits.; the Judge (advisory) calls it intended: The old 2-character result exceeded max\_len=1; the issue's rule requires at most 1 character, and the ellipsis alone fits.; the Judge (advisory) calls it intended: The old 2-character result exceeded max\_len=1 with a custom ellipsis; the same issue rule applies.

### Changes no test noticed (3 of 6; the rest in receipt.json)
- `src/textutil/trunc.py:17`: `     keep = max(max_len - len(ellipsis), 0) ` → `     keep = max(max_len - len(ellipsis), 1) ` made no test fail; behaves differently from the fix on inputs no test checks (`m-579fad2b936a`)
- `src/textutil/trunc.py:18`: `     return (text[:keep] + ellipsis)[:max_len] ` → `     return (text[:keep] + ellipsis)[:max_len + 1] ` made no test fail; behaves differently from the fix on inputs no test checks (`m-f80fdb4af18f`)
- `src/textutil/trunc.py:18`: `     return (text[:keep] + ellipsis)[:max_len] ` → `     return (text[:keep] + ellipsis)[-max_len:] ` made no test fail; behaves differently from the fix on inputs no test checks (`m-6db47f738159`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 19,311 input and 5,020 output tokens, cost $0.1622 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 0.98 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 1.83 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 14.98 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 40.45 s: the PR's test file tests/test\_trunc.py does not fail with the fix reverted (passed)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_trunc.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 0.99 s: none of the 4 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 2.92 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_trunc.py`
- `behaviour_diff`: `compared`, 15.28 s: 287 input(s) compared on 1 function(s): 24 changed with the fix
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `none_found`, 17.11 s: no counterexample found in 990 inputs against 7 properties
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_trunc.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `textutil.trunc.truncate` (`src/textutil/trunc.py`): 990 inputs
#### More changes no test noticed
- `src/textutil/trunc.py:18`: `     return (text[:keep] + ellipsis)[:max_len] ` → `     return text[:keep] + ellipsis ` made no test fail; behaves differently from the fix on inputs no test checks (`m-51752bbfdc07`)
- `src/textutil/trunc.py:17`: `     keep = max(max_len - len(ellipsis), 0) ` → `     keep = max(max_len - len(ellipsis), (-1)) ` made no test fail; no input tried behaved differently from the fix (`m-c52cf8322818`)
- `src/textutil/trunc.py:17`: `     keep = max(max_len - len(ellipsis), 0) ` → `     keep = max(max_len - len(ellipsis), 1) ` made no test fail; behaves differently from the fix on inputs no test checks (`m-579fad2b936a`)
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
- guard: 1 of the rule mutant kills were crashes on the mutated line
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T14:19:06+00:00, issue sha256 `23985096b51eee866e3522d089e64bb9e72a0cc006a5a8094a13c8cdd2c0e264`

</details>
