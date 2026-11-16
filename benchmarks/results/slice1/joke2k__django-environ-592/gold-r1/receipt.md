## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The fix reproduced and guarded the reported issue with no regressions found, but Break My Fix found that extra\_options is silently dropped for in-memory SQLite URLs: db\_url and db\_url\_config with 'sqlite:​//:memory:' and extra\_options={'timeout': 20} return only ENGINE and NAME, with no OPTIONS. Check the early-return path for ':memory:' SQLite URLs in db\_url\_config and make sure extra\_options is…

**Why this level:** Break My Fix finding 1: an input that breaks environ.environ.Env.db\_url; Break My Fix finding 2: an input that breaks environ.environ.Env.db\_url; Break My Fix finding 3: an input that breaks environ.environ.Env.db\_url\_config; Break My Fix finding 4: an input that breaks environ.environ.Env.db\_url\_config

**Issue:** Add support for Django 5.1 PostgreSQL connection pools to env.db\_url · **Repo:** testbed · **Base** `tf-base` (`e2e50de`) → **head** `tf-gold` (`20774f9`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `db_url(self='Env()', var='DJANGO_ENVIRON_SURELY_UNSET_VAR', ...` → `returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':m...` (before the fix: `returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':m...`); breaks **db\_url\_passes\_extra\_options**: “Perhaps they can be passed in a new \`extra\_options\` argument?” (issue); 1 more input break it the same way; test: `findings/finding_1.py`
2. `db_url(self='Env()', var='DJANGO_ENVIRON_TEST_UNSET_DB_URL_X...` → `returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':m...` (before the fix: `returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':m...`); breaks **db\_url\_merges\_extra\_options**: “Perhaps they can be passed in a new \`extra\_options\` argument?” (issue); test: `findings/finding_2.py`
3. `db_url_config(url='sqlite://:memory:', extra_options={'timeo...` → `returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':m...` (before the fix: `returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':m...`); breaks **extra\_options\_merged\_into\_OPTIONS**: “Optional dictionary merged into \`\`OPTIONS\`\` after URL parsing.” (docstring); test: `findings/finding_3.py`
4. `db_url_config(url='sqlite://:memory:', engine=None, options_...` → `returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':m...` (before the fix: `returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':m...`); breaks **extra\_options\_merged\_into\_OPTIONS**: “Optional dictionary merged into \`\`OPTIONS\`\` after URL parsing.” (docstring); 1 more input break it the same way; test: `findings/finding_4.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `guarded` | kill rate 0\.8, mutants 5, killed 4, survived 1 |
| `regressions` | `none_found` | compared 276, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 9 |
| `behaviour_diff` | `compared` | inputs compared 2, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 2, inputs tried 405, properties counted 10, findings 4 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `environ/environ.py:725`: `             config['OPTIONS'].update(extra_options) ` → `             config['OPTIONS'] = {**extra_options, **config['... ` made no test fail; no input tried behaved differently from the fix (`m-a8c3a3614a0c`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 65,968 input and 11,618 output tokens, cost $0.4486 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 5.3 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 8.53 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 75.47 s: attempt 2: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `guarded`, 75.75 s: the reproduction test fails with the fix reverted, and the tests killed 4 of 5 mutants
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 5.81 s: none of the 276 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 5.25 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `compared`, 21.36 s: 2 input(s) compared on 2 function(s): 0 changed with the fix
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `found`, 159.62 s: 4 finding(s), each proven by a failing repro file
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_finding_1.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_finding_2.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_finding_3.py`
  - 4 more command(s) in receipt.json
- `integrity`: `clean`, 0.04 s: nothing suspicious in the fix's test or source changes
#### Fix lines run (report only)
- repro: 9 of 9 fix lines run
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
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T18:07:01+00:00, issue sha256 `2cbb4f257490d858bb2ff6821a4c4810dd9f62f62b58304f1b7aaf5343af936e`

</details>
