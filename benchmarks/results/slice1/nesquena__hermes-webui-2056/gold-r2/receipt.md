## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproduced the corrupted model string before the fix and passes after it, no regressions or breaking inputs were found, but the mutation guard did not reach the level needed for L2. Look next at the value changes in api.config.\_custom\_provider\_slug\_from\_name: the Judge marked four of its six behaviour changes as suspicious, so check that slugs for existing custom provider names (not just o…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 8 mutants; 80% is needed

**Issue:** Custom provider name containing parentheses and port leads to corrupted model string ("15721):deepseek-v4-flash") · **Repo:** testbed · **Base** `tf-base` (`b766b7f`) → **head** `tf-gold` (`f2e3c9d`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.25, mutants 8, killed 2, survived 6 |
| `regressions` | `none_found` | compared 4908, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 24 |
| `behaviour_diff` | `partial` | inputs compared 657, changes 18, groups 1 |
| `break_my_fix` | `none_found` | targets 6, inputs tried 2298, properties counted 23, findings 0 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `api.config._custom_provider_slug_from_name` (`value`, 18 inputs): `returns 'custom:ñym\U00061ee2\x18º\x97\U000bb1aci²\x1fr\x9fã...` → `returns 'custom:ym-i-r-tg'`; the Judge (advisory) calls it intended: The issue's Fix 1 asks the name-to-slug transform to strip characters like '(' and ')', e.g. "Local (127.0.0.1:15721)" → "local-127.0.0.1-15721"; replacing parentheses and the comma applies that same rule.; the Judge (advisory) calls it suspicious: The name has no parentheses, colon or other problem character; the issue never asks for a name's own leading '-' to be dropped, and doing so silently changes the slug of an existing provider name.; the Judge (advisory) calls it intended: The issue's Fix 1 asks to strip or replace non-alphanumeric characters such as quotes and backslashes in the slug; this input gets that same sanitisation.; the Judge (advisory) calls it suspicious: The name contains only letters and a leading hyphen; nothing in the issue asks to strip an existing leading '-', so the change from 'custom:-inf' to 'custom:inf' goes beyond the reported bug.; the Judge (advisory) calls it suspicious: Beyond replacing '+', the fix drops the leading '-' and turns 'e+88' into 'e-88'; the issue only targets parentheses and colons from the setup-generated name, so this rewrite is not asked for.; the Judge (advisory) calls it suspicious: Same as c5: the leading '-' is stripped and '+' becomes '-' (e+16 → e-16); the issue asks for none of this, as it targets names with parentheses and a port colon.

### Changes no test noticed (3 of 11; the rest in receipt.json)
- `api/config.py:754`: `     slug = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-") ` → `     slug = re.sub(r"[^a-z0-9._:-]+", "-", raw).strip("-") ` made no test fail; no input tried behaved differently from the fix (`m-46845b0c1bb2`)
- `api/config.py:754`: `     slug = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-") ` → `     slug = re.sub(r"[^a-z0-9._-]+", "-", raw) ` made no test fail; behaves differently from the fix on inputs no test checks (`m-0d6f038a4725`)
- `api/config.py:755`: `     slug = re.sub(r"-{2,}", "-", slug) ` → `     slug = re.sub(r"-{3,}", "-", slug) ` made no test fail; no input tried behaved differently from the fix (`m-baa296c00ee8`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack get\_available\_models.\_build\_available\_models\_uncached.\_configured\_provider\_for\_base\_url: a nested function: it can't be imported, not attacked yet; Break My Fix could not attack get\_providers: it takes no parameters to vary; the behaviour diff could not compare get\_available\_models.\_build\_available\_models\_uncached.\_configured\_provider\_for\_base\_url: a nested function: it can't be imported, not attacked yet; the behaviour diff could not compare \_clean\_provider\_key\_from\_config: past the cap of 6 functions; and 5 more in receipt.json
- **Model use:** 8 calls, 119,334 input and 13,105 output tokens, cost $0.6605 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 63.45 s: base suite failed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 6.37 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 25.25 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 2193.59 s: the tests killed 2 of 8 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 249.01 s: none of the 4908 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 3.99 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `partial`, 102.52 s: 657 input(s) compared on 5 function(s): 18 changed with the fix; not complete: get\_available\_models.\_build\_available\_models\_uncached.\_configured\_provider\_for\_base\_url: not compared (a nested function: it can't be imported, not attacked yet)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `none_found`, 172.66 s: no counterexample found in 2298 inputs against 23 properties
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_issue1094_provider_bugs.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_issue1228_model_picker_duplicate_ids.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_issue1384_local_provider.py`
  - 8 more command(s) in receipt.json
- `integrity`: `clean`, 0.13 s: nothing suspicious in the fix's test or source changes
#### More changes no test noticed
- `api/config.py:754`: `     slug = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-") ` → `     slug = re.sub(r"[^a-z0-9_-]+", "-", raw).strip("-") ` made no test fail; behaves differently from the fix on inputs no test checks (`m-7c29ffa467ef`)
- `api/providers.py:48`: `     candidates = {raw_name, f"custom:{raw_name}"} ` → `     candidates = {raw_name} ` made no test fail; no input tried behaved differently from the fix (`m-a143756ff0c6`)
- `api/providers.py:51`: `     return pid in candidates ` → `     return pid in candidates and pid != slug ` made no test fail; no input tried behaved differently from the fix (`m-1f18a1d75574`)
- `api/config.py:2868`: `             target = _normalize_base_url_for_match(base_url)... ` → `             return "" ` made no test fail; no input tried behaved differently from the fix (`m-63a666445e5b`)
- `api/providers.py:43`: `     pid = str(provider_id or "").strip().lower() ` → `     pid = str(provider_id and "").strip().lower() ` made no test fail; no input tried behaved differently from the fix (`m-a7c884ac19f5`)
- `api/providers.py:44`: `     raw_name = str(name or "").strip().lower() ` → `     raw_name = str(name and "").strip().lower() ` made no test fail; no input tried behaved differently from the fix (`m-20c053bc5b6b`)
- `api/providers.py:45`: `     if not pid or not raw_name: ` → `     if pid or not raw_name: ` made no test fail; no input tried behaved differently from the fix (`m-167929147b17`)
- `api/providers.py:45`: `     if not pid or not raw_name: ` → `     if not (not pid or not raw_name): ` made no test fail; no input tried behaved differently from the fix (`m-ee151d0d07c2`)
#### Fix lines run (report only)
- repro: 6 of 24 fix lines run
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
- the behaviour diff could not compare \_clean\_provider\_key\_from\_config: past the cap of 6 functions
- the behaviour diff could not compare get\_available\_models: past the cap of 6 functions
- the behaviour diff could not compare get\_provider\_quota: past the cap of 6 functions
- the behaviour diff could not compare remove\_provider\_key: past the cap of 6 functions
- the behaviour diff could not compare \_custom\_provider\_name\_matches: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 22 functions were shown
- guard: only the first 10 of 29 rule mutants were run
- guard: 1 of the rule mutant kills were crashes on the mutated line
- behaviour\_diff: only the first 6 of 10 functions are attacked
- break\_my\_fix: only the first 6 of 8 functions are attacked
- break\_my\_fix: only 10 of 11 test files were run for witnesses
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-20T10:10:27+00:00, issue sha256 `0ccf920ad7e71c8f2e6ee755c5252cc27bf23c4b445fb607da873a269fd0ea76`

</details>
