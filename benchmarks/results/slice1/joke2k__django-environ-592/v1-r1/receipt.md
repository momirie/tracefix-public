## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): Break My Fix found inputs where the fixed db\_url and db\_url\_config accept extra\_options but drop them: for example, db\_url with a postgres default and extra\_options={'pool': True} returns a config with no OPTIONS key, and db\_url\_config('sqlite:​//:memory:', extra\_options={'timeout': 20}) also omits the options. Look next at how extra\_options is merged into the returned config, especially when the…

**Why this level:** Break My Fix finding 1: an input that breaks environ.environ.Env.db\_url; Break My Fix finding 2: an input that breaks environ.environ.Env.db\_url; Break My Fix finding 3: an input that breaks environ.environ.Env.db\_url; Break My Fix finding 4: an input that breaks environ.environ.Env.db\_url\_config

**Issue:** Add support for Django 5.1 PostgreSQL connection pools to env.db\_url · **Repo:** testbed · **Base** `tf-base` (`e2e50de`) → **head** `tf-v1` (`566b712`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `db_url(self='Env()', var='ENVIRON_TEST_UNSET_VAR_XYZ', defau...` → `returns {'NAME': 'db', 'USER': 'user', 'PASSWORD': 'pass', '...` (before the fix: `returns {'NAME': 'db', 'USER': 'user', 'PASSWORD': 'pass', '...`); breaks **db\_url\_passes\_extra\_options**: “Perhaps they can be passed in a new \`extra\_options\` argument?” (issue); 2 more inputs break it the same way; test: `findings/finding_1.py`
2. `db_url(self='Env()', var='DJANGO_ENVIRON_UNSET_TEST_VAR_XYZ'...` → `returns {'NAME': 'db', 'USER': 'user', 'PASSWORD': 'pass', '...` (before the fix: `returns {'NAME': 'db', 'USER': 'user', 'PASSWORD': 'pass', '...`); breaks **db\_url\_passes\_extra\_options**: “Perhaps they can be passed in a new \`extra\_options\` argument?” (issue); test: `findings/finding_2.py`
3. `db_url(self='Env()', var='DJANGO_ENVIRON_UNSET_TEST_VAR_XYZ'...` → `returns {'NAME': 'db', 'USER': 'user', 'PASSWORD': 'pass', '...` (before the fix: `returns {'NAME': 'db', 'USER': 'user', 'PASSWORD': 'pass', '...`); breaks **db\_url\_matches\_db\_url\_config**: “Perhaps they can be passed in a new \`extra\_options\` argument?” (issue); test: `findings/finding_3.py`
4. `db_url_config(url='sqlite://:memory:', extra_options={'timeo...` → `returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':m...` (before the fix: `returns {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':m...`); breaks **extra\_options\_present\_in\_OPTIONS**: “Values in \`\`extra\_options\`\` override query-string \`\`OPTIONS\`\`.” (docstring); 2 more inputs break it the same way; test: `findings/finding_4.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 3 |
| `guard` | `not_guarded` | kill rate 0\.667, mutants 3, killed 2, survived 1 |
| `regressions` | `none_found` | compared 276, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 7 |
| `behaviour_diff` | `compared` | inputs compared 2, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 2, inputs tried 403, properties counted 9, findings 4 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `environ/environ.py:723`: `             config['OPTIONS'].update(extra_options) ` → `             config['OPTIONS'] = {**extra_options, **config['... ` made no test fail; no input tried behaved differently from the fix (`m-eb5b03542d78`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 74,079 input and 11,659 output tokens, cost $0.4559 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 5.61 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 8.7 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 91.67 s: attempt 3: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 64.58 s: the tests killed 2 of 3 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 5.54 s: none of the 276 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 5.35 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `compared`, 22.87 s: 2 input(s) compared on 2 function(s): 0 changed with the fix
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `found`, 130.79 s: 4 finding(s), each proven by a failing repro file
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_finding_1.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_finding_2.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_finding_3.py`
  - 4 more command(s) in receipt.json
- `integrity`: `clean`, 0.04 s: nothing suspicious in the fix's test or source changes
#### Fix lines run (report only)
- repro: 7 of 7 fix lines run
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
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T18:13:03+00:00, issue sha256 `2cbb4f257490d858bb2ff6821a4c4810dd9f62f62b58304f1b7aaf5343af936e`

</details>
