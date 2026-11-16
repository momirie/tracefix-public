## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The bug was reproduced: a test fails before the fix and passes after it, no regressions were found, and the one behaviour change (arguments to DataStructureConfig.repos) was judged intended, but the tests did not kill enough mutants for L2 and Break My Fix was inconclusive. Next, look at whether the tests actually guard the fixed path for a region config with only the country attribute and no rep…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 0 of 3 mutants; 80% is needed

**Issue:** Using only country in nomenclature config breaks CodeList · **Repo:** testbed · **Base** `tf-base` (`86d38f9`) → **head** `tf-gold` (`792f749`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 4 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 3, killed 0, survived 3 |
| `regressions` | `none_found` | compared 150, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 53 |
| `behaviour_diff` | `partial` | inputs compared 1, changes 1, groups 1 |
| `break_my_fix` | `inconclusive` | targets 5, inputs tried 10, properties counted 10, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 2 of 2 killed; logic: 2 of 2 killed; constant: 1 of 1 killed; arithmetic: 0 of 2 killed; membership: 1 of 1 killed; drop\_call: 0 of 1 killed; reraise: 1 of 1 killed; no place for compare, negate\_if, loop

### Behaviour changes
- `nomenclature.config.DataStructureConfig.repos` (`arguments`, 1 input): `returns {}; left its arguments as builtins.list([builtins.tu...` → `returns {}; left its arguments as builtins.list([builtins.tu...`; the Judge (advisory) calls it intended: The return value is still {}. The only difference is that region/variable now default to empty config objects instead of None, and that default change is how the fix stops the issue's crash when iterating over empty region.repositories.

### Changes no test noticed (3 of 6; the rest in receipt.json)
- `nomenclature/codelist.py:199`: `         config = config or NomenclatureConfig() ` → `         config = NomenclatureConfig() ` made no test fail; not compared with the fix (`m-bdff6ddca126`)
- `nomenclature/codelist.py:201`: `             config.definitions, name.lower(), CodeListConfig() ` → `             config.definitions, name, CodeListConfig() ` made no test fail; not compared with the fix (`m-ed5ab82d983d`)
- `nomenclature/codelist.py:205`: `                 cls._parse_codelist_dir(repo_path, file_glob... ` → `                 code_list + cls._parse_codelist_dir(repo_pat... ` made no test fail; not compared with the fix (`m-2a4e62891046`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack DataStructureDefinition.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; the behaviour diff could not compare DataStructureDefinition.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; 9 things the behaviour diff can't observe (run log)
- **Model use:** 9 calls, 86,606 input and 8,244 output tokens, cost $0.4406 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 10.35 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 14.44 s: 4 changed module(s) imported from the copies (8 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 48.15 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 320.1 s: the tests killed 0 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 37.39 s: none of the 150 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 7.71 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `partial`, 16.99 s: 1 input(s) compared on 1 function(s): 1 changed with the fix; not complete: DataStructureDefinition.\_\_init\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 26.08 s: no candidate checked counts, but 1 could not be checked
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.04 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 57.24 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### Break My Fix targets
- `nomenclature.codelist.CodeList.from_directory` (`nomenclature/codelist.py`): not attacked (ValidationError: 3 validation errors for NomenclatureConfig repositories Input should be a valid dictionary \[type=dict\_type, input\_value=&lt;factory&gt;, input\_type=\_HAS\_DEFAULT\_FACTORY\_CLASS\] For further information visit https:​//errors.pydantic.dev/2.11/v/dict\_type definitions Input should be a valid dictionary or instance of DataStructureConfig \[type=model\_type, input\_value=&lt;factory&gt;, input\_type=\_HAS\_DEFAULT\_FACTORY\_CLASS\] For further information visit https:​//errors.pydantic.dev/2.11/v)
- `nomenclature.codelist.RegionCodeList.from_directory` (`nomenclature/codelist.py`): not attacked (ValidationError: 3 validation errors for NomenclatureConfig repositories Input should be a valid dictionary \[type=dict\_type, input\_value=&lt;factory&gt;, input\_type=\_HAS\_DEFAULT\_FACTORY\_CLASS\] For further information visit https:​//errors.pydantic.dev/2.11/v/dict\_type definitions Input should be a valid dictionary or instance of DataStructureConfig \[type=model\_type, input\_value=&lt;factory&gt;, input\_type=\_HAS\_DEFAULT\_FACTORY\_CLASS\] For further information visit https:​//errors.pydantic.dev/2.11/v)
- `nomenclature.config.DataStructureConfig.repos` (`nomenclature/config.py`): 4 inputs
- `nomenclature.config.NomenclatureConfig.check_definitions_repository` (`nomenclature/config.py`): not attacked (ValidationError: 3 validation errors for NomenclatureConfig repositories Input should be a valid dictionary \[type=dict\_type, input\_value=&lt;factory&gt;, input\_type=\_HAS\_DEFAULT\_FACTORY\_CLASS\] For further information visit https:​//errors.pydantic.dev/2.11/v/dict\_type definitions Input should be a valid dictionary or instance of DataStructureConfig \[type=model\_type, input\_value=&lt;factory&gt;, input\_type=\_HAS\_DEFAULT\_FACTORY\_CLASS\] For further information visit https:​//errors.pydantic.dev/2.11/v)
- `nomenclature.processor.region.RegionProcessor.from_directory` (`nomenclature/processor/region.py`): 0 inputs (nothing generated)
#### More changes no test noticed
- `nomenclature/codelist.py:203`: `             repo_path = config.repositories[repo].local_path... ` → `             repo_path = config.repositories[repo].local_path... ` made no test fail; not compared with the fix (`m-0efb6c3f110e`)
- `nomenclature/codelist.py:610`: `                     code_list.append(RegionCode(name=c.name,... ` → `                     pass ` made no test fail; not compared with the fix (`m-e34b1a4b8319`)
- `nomenclature/codelist.py:203`: `             repo_path = config.repositories[repo].local_path... ` → `             repo_path = config.repositories[repo].local_path... ` made no test fail; not compared with the fix (`m-6e260fb9448f`)
#### Fix lines run (report only)
- repro: 18 of 53 fix lines run
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
- Break My Fix could not attack DataStructureDefinition.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare DataStructureDefinition.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
#### Notes
- reproduce: only the first 8 of 10 functions were shown
- guard: 7 of the 10 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 23 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.16: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: only the first 8 of 10 functions were shown
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T22:09:57+00:00, issue sha256 `aa138782041dc27f468e3d21f21cba90bf1803f58a7e19ea3322d5436e78e656`

</details>
