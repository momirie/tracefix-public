## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The evidence reached L1: a test reproduced the corrupted model string bug by failing before the fix and passing after it, with no regressions or breaking inputs found, but the tests did not kill enough mutants to show the fix is guarded. The most important thing to look at next is the value changes in api.config.\_custom\_provider\_slug\_from\_name, where three of the six behaviour changes were labell…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 7 mutants; 80% is needed

**Issue:** Custom provider name containing parentheses and port leads to corrupted model string ("15721):deepseek-v4-flash") · **Repo:** testbed · **Base** `tf-base` (`b766b7f`) → **head** `tf-v2` (`2782948`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.286, mutants 7, killed 2, survived 5 |
| `regressions` | `none_found` | compared 4908, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 23 |
| `behaviour_diff` | `partial` | inputs compared 638, changes 19, groups 1 |
| `break_my_fix` | `none_found` | targets 6, inputs tried 1601, properties counted 15, findings 0 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `api.config._custom_provider_slug_from_name` (`value`, 19 inputs): `returns 'custom:local-(127.0.0.1:15721)'` → `returns 'custom:local-127.0.0.1-15721'`; the Judge (advisory) calls it intended: This is the exact case in the issue: 'Local (127.0.0.1:15721)' should not keep the ':' or parentheses, and the slug now matches the suggested 'local-127.0.0.1-15721'.; the Judge (advisory) calls it intended: The issue's Fix 1 says to strip or replace '(', ')' and other non-alphanumeric characters in the name-derived slug, and that is what happens here.; the Judge (advisory) calls it suspicious: The issue only asks to remove problematic characters like parentheses and colons; dropping a leading '-' silently renames an otherwise valid slug.; the Judge (advisory) calls it intended: Quotes and backslashes are non-alphanumeric decorations, so replacing them follows the Fix 1 sanitization rule in the issue.; the Judge (advisory) calls it suspicious: Stripping the leading hyphen from '-inf' is not asked for; the issue only targets characters such as ':' and parentheses that break the @​provider:model grammar.; the Judge (advisory) calls it suspicious: Stripping the leading '-' and turning '+' into '-' gives 'e-88', a different name that can collide with another one; the issue asks for nothing beyond stripping parentheses and colons.

### Changes no test noticed (3 of 10; the rest in receipt.json)
- `api/config.py:755`: `     slug = re.sub(r"-{2,}", "-", slug) ` → `     slug = re.sub(r"-{3,}", "-", slug) ` made no test fail; no input tried behaved differently from the fix (`m-baa296c00ee8`)
- `api/config.py:754`: `     slug = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-") ` → `     slug = re.sub(r"[^a-z0-9._-]+", "-", raw) ` made no test fail; behaves differently from the fix on inputs no test checks (`m-0d6f038a4725`)
- `api/config.py:754`: `     slug = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-") ` → `     slug = re.sub(r"[^a-z0-9-]+", "-", raw).strip("-") ` made no test fail; behaves differently from the fix on inputs no test checks (`m-5d6d6233ce3f`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack get\_available\_models.\_build\_available\_models\_uncached.\_configured\_provider\_for\_base\_url: a nested function: it can't be imported, not attacked yet; Break My Fix could not attack get\_providers: it takes no parameters to vary; the behaviour diff could not compare get\_available\_models.\_build\_available\_models\_uncached.\_configured\_provider\_for\_base\_url: a nested function: it can't be imported, not attacked yet; the behaviour diff could not compare get\_available\_models: past the cap of 6 functions; and 4 more in receipt.json
- **Model use:** 8 calls, 100,951 input and 10,670 output tokens, cost $0.5571 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 63.51 s: base suite failed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 6.32 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 24.67 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 1727.9 s: the tests killed 2 of 7 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 252.33 s: none of the 4908 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 4.01 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `partial`, 85.77 s: 638 input(s) compared on 5 function(s): 19 changed with the fix; not complete: get\_available\_models.\_build\_available\_models\_uncached.\_configured\_provider\_for\_base\_url: not compared (a nested function: it can't be imported, not attacked yet)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `none_found`, 124.46 s: no counterexample found in 1601 inputs against 15 properties
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_issue1094_provider_bugs.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_issue1500_lmstudio_env_var_alignment.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_issue2025_xiaomi_env_key.py`
  - 3 more command(s) in receipt.json
- `integrity`: `clean`, 0.1 s: nothing suspicious in the fix's test or source changes
#### More changes no test noticed
- `api/providers.py:51`: `     return pid in candidates ` → `     return pid in candidates and pid != slug ` made no test fail; no input tried behaved differently from the fix (`m-1f18a1d75574`)
- `api/providers.py:48`: `     candidates = {raw_name, f"custom:{raw_name}"} ` → `     candidates = {raw_name} ` made no test fail; no input tried behaved differently from the fix (`m-a143756ff0c6`)
- `api/config.py:2868`: `             target = _normalize_base_url_for_match(base_url)... ` → `             return "" ` made no test fail; no input tried behaved differently from the fix (`m-63a666445e5b`)
- `api/providers.py:43`: `     pid = str(provider_id or "").strip().lower() ` → `     pid = str(provider_id and "").strip().lower() ` made no test fail; no input tried behaved differently from the fix (`m-a7c884ac19f5`)
- `api/providers.py:44`: `     raw_name = str(name or "").strip().lower() ` → `     raw_name = str(name and "").strip().lower() ` made no test fail; no input tried behaved differently from the fix (`m-20c053bc5b6b`)
- `api/providers.py:45`: `     if not pid or not raw_name: ` → `     if pid or not raw_name: ` made no test fail; no input tried behaved differently from the fix (`m-167929147b17`)
- `api/providers.py:45`: `     if not pid or not raw_name: ` → `     if not (not pid or not raw_name): ` made no test fail; no input tried behaved differently from the fix (`m-ee151d0d07c2`)
#### Fix lines run (report only)
- repro: 5 of 23 fix lines run
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
- Break My Fix could not attack get\_available\_models.\_build\_available\_models\_uncached.\_configured\_provider\_for\_base\_url: a nested function: it can't be imported, not attacked yet
- Break My Fix could not attack get\_providers: it takes no parameters to vary
- the behaviour diff could not compare get\_available\_models.\_build\_available\_models\_uncached.\_configured\_provider\_for\_base\_url: a nested function: it can't be imported, not attacked yet
- the behaviour diff could not compare get\_available\_models: past the cap of 6 functions
- the behaviour diff could not compare get\_provider\_quota: past the cap of 6 functions
- the behaviour diff could not compare remove\_provider\_key: past the cap of 6 functions
- the behaviour diff could not compare \_custom\_provider\_name\_matches: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 16 functions were shown
- guard: only the first 10 of 28 rule mutants were run
- guard: 1 of the rule mutant kills were crashes on the mutated line
- behaviour\_diff: only the first 6 of 9 functions are attacked
- break\_my\_fix: only the first 6 of 7 functions are attacked
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-15T17:30:12+00:00, issue sha256 `0ccf920ad7e71c8f2e6ee755c5252cc27bf23c4b445fb607da873a269fd0ea76`

</details>
