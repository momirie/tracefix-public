## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproduced the bug (it fails before the fix and passes after), no regressions or breaking inputs were found, and the changed lines were covered, but the guard stage reported the fix as not guarded and the behaviour comparison was inconclusive. Next, check why the mutation results did not reach the L2 threshold, and consider adding a test that pins a region config with only \`country: true\`…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 0 of 4 mutants; 80% is needed

**Issue:** Using only country in nomenclature config breaks CodeList · **Repo:** testbed · **Base** `tf-base` (`86d38f9`) → **head** `tf-agent_wrong` (`9294a80`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 4, killed 0, survived 4 |
| `regressions` | `none_found` | compared 150, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 11 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 43, properties counted 1, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 6; the rest in receipt.json)
- `nomenclature/codelist.py:625`: `                         config.repositories[repo].local_path... ` → `                         config.repositories[repo].local_path... ` made no test fail; not compared with the fix (`m-7069f0865372`)
- `nomenclature/codelist.py:632`: `                         repository=config.definitions.region... ` → `                         repository=repo, ` made no test fail; not compared with the fix (`m-95b579597b49`)
- `nomenclature/codelist.py:635`: `                         code_list, repo_path, file_glob_pattern ` → `                         code_list, path, file_glob_pattern ` made no test fail; not compared with the fix (`m-91f33c84e01a`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 5 calls, 23,736 input and 2,860 output tokens, cost $0.1233 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 14.08 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 19.41 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 69.92 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 240.79 s: the tests killed 0 of 4 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 33.53 s: none of the 150 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 6.73 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 8.13 s: nothing was compared: RegionCodeList.from\_directory: it could not be loaded after the fix: TypeError: 'NoneType' object is not a mapping
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `none_found`, 67.52 s: no counterexample found in 43 inputs against 1 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Found before the fix too
- `from_directory(name='region', path='/nonexistent_dir_for_tes...` → `raises AttributeError: 'str' object has no attribute 'glob'` (before the fix: `raises AttributeError: 'str' object has no attribute 'glob'`); breaks **returns\_regioncodelist\_with\_given\_name**: “Initialize a RegionCodeList from a directory with codelist files” (docstring); 3 more inputs break it the same way
#### Break My Fix targets
- `nomenclature.codelist.RegionCodeList.from_directory` (`nomenclature/codelist.py`): not attacked (TypeError: 'NoneType' object is not a mapping)
#### More changes no test noticed
- `nomenclature/codelist.py:630`: `                         repo_path, ` → `                         path, ` made no test fail; not compared with the fix (`m-d41d602d2fb8`)
- `nomenclature/codelist.py:625`: `                         config.repositories[repo].local_path... ` → `                         config.repositories[repo].local_path... ` made no test fail; not compared with the fix (`m-f7e5e37955b7`)
- `nomenclature/codelist.py:625`: `                         config.repositories[repo].local_path... ` → `                         config.repositories[repo].local_path... ` made no test fail; not compared with the fix (`m-1ff1a26fea35`)
#### Fix lines run (report only)
- repro: 1 of 11 fix lines run
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
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.16: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T21:23:23+00:00, issue sha256 `aa138782041dc27f468e3d21f21cba90bf1803f58a7e19ea3322d5436e78e656`

</details>
