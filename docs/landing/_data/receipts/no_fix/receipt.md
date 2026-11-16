## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The reproduction test fails the same way before and after this fix, and Break My Fix found that dedupe\_emails(\['Bob@​Example.com', 'bob@​example.com'\]) still returns both addresses, so the capitalisation duplicate from the issue remains. Look next at how crm.contacts.dedupe\_emails compares emails (for example, whether it normalises case before deduplicating) and at its behaviour change, which the J…

**Why this level:** the fix does not fix the bug: the reproduction test fails the same way before and after it; Break My Fix finding 1: an input that breaks crm.contacts.dedupe\_emails

**Issue:** Contact import creates duplicates for differently-capitalised emails · **Repo:** no\_fix · **Base** `base` (`b82706e`) → **head** `head` (`242a3d9`)\
**Isolation:** basic (bubblewrap (bwrap) is not installed)

> [!WARNING]
> - Generated tests ran with basic isolation only (no bubblewrap sandbox): tampering inside the watched folders is detected, but code could still read or write elsewhere on this machine, and a process that escaped could influence a later run. For untrusted changes run Tracefix in GitHub Actions or on Linux with bubblewrap.

### Counterexamples
1. `dedupe_emails(emails=['Bob@Example.com', 'bob@example.com'])` → `returns ['Bob@Example.com', 'bob@example.com']` (before the fix: `returns ['Bob@Example.com', 'bob@example.com']`); breaks **no\_case\_insensitive\_duplicates**: “creates duplicates when the same email differs only in capitalisation” (issue); 3 more inputs break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `fix_does_not_fix` | attempts 1 |
| `guard` | `skipped` | mutants 0, killed 0, survived 0 |
| `regressions` | `none_found` | compared 4, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 2 |
| `behaviour_diff` | `compared` | inputs compared 76, changes 20, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 735, properties counted 8, findings 1 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `crm.contacts.dedupe_emails` (`value`, 20 inputs): `returns ['bob@example.com', ' bob@example.com ']` → `returns ['bob@example.com']`; the Judge (advisory) calls it suspicious: The issue asks for case-insensitive deduplication (Bob@​Example.com vs bob@​example.com); merging whitespace-padded addresses is not requested, even though the PR's tests call this input.; the Judge (advisory) calls it suspicious: The docstring only says to remove duplicates, so rewriting ' ' to '' alters a returned value that nothing in the issue or docstring asks to change.; the Judge (advisory) calls it suspicious: The input is a frozenset, so the reordered output likely reflects set iteration order rather than anything the issue about capitalisation asks for; it needs a human check.; the Judge (advisory) calls it suspicious: The fix strips the trailing \\x85 (NEL) from an entry and the output order changes; neither is requested by the capitalisation issue or the docstring's 'in order' contract.; the Judge (advisory) calls it suspicious: The fix strips a leading \\xa0 from an address, which is whitespace normalisation that the capitalisation issue does not ask for.

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; guard: skipped (there is no reproduction test to judge the tests with (fix\_does\_not\_fix)); 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 20,076 input and 5,556 output tokens, cost $0.1755 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 0.97 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.02 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `fix_does_not_fix`, 6.11 s: attempt 1: the test fails before and after the fix with the same failure signature, also after the model was shown the result This rests on a test written by the model claude-sonnet-5-5.
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `skipped`, 0.0 s: there is no reproduction test to judge the tests with (fix\_does\_not\_fix)
- `regressions`: `none_found`, 0.95 s: none of the 4 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 1.46 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_contacts.py`
- `behaviour_diff`: `compared`, 4.18 s: 76 input(s) compared on 1 function(s): 20 changed with the fix
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `found`, 17.43 s: 1 finding(s), each proven by a failing repro file
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_finding_1.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_contacts.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `crm.contacts.dedupe_emails` (`src/crm/contacts.py`): 735 inputs
#### Fix lines run (report only)
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
- guard: skipped (there is no reproduction test to judge the tests with (fix\_does\_not\_fix))
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T14:13:32+00:00, issue sha256 `809ffafaffcc7764eed77d22a0cd53ef480afee8cc38256ec26777aef0f87f1a`

</details>
