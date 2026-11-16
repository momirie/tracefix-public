## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the issue, but 13 tests that passed before the fix now fail after it, including TestCheckDependencies npm\_v3/yarn in tests/main/test\_main.py and most of the TestAbstractPackageReference, TestTopPyPiReference and TestTopNpmReference tests in tests/trusted\_packages/test\_references.py. Look first at why the package-reference tests (cache handling, parsing, downloads) break un…

**Why this level:** regression: tests/main/test\_main.py::TestCheckDependencies.test\_check\_dependencies\_npm\_v3 passed before the fix and fails after it; regression: tests/main/test\_main.py::TestCheckDependencies.test\_check\_dependencies\_yarn passed before the fix and fails after it; regression: tests/trusted\_packages/test\_references.py::TestAbstractPackageReference.test\_get\_packages\_no\_cache passed before the fix and fails after it; regression: tests/trusted\_packages/test\_references.py::TestAbstractPackageReference.test\_get\_packages\_downloads\_when\_cache\_has\_invalid\_package\_names passed before the fix and fails after it; regression: tests/trusted\_packages/test\_references.py::TestAbstractPackageReference.test\_cache\_is\_saved\_when\_not\_existing passed before the fix and fails after it; regression: tests/trusted\_packages/test\_references.py::TestTopPyPiReference.test\_get\_trusted\_packages passed before the fix and fails after it; and 7 more in receipt.json

**Issue:** Vendor dependencies in out repo · **Repo:** testbed · **Base** `tf-base` (`640e122`) → **head** `tf-v0` (`391c584`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples (5 of 13; the rest in receipt.json)
1. Regression: `tests/main/test_main.py::TestCheckDependencies.test_check_dependencies_npm_v3` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: TypeError: unhashable type: 'dict')
2. Regression: `tests/main/test_main.py::TestCheckDependencies.test_check_dependencies_yarn` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: TypeError: unhashable type: 'dict')
3. Regression: `tests/trusted_packages/test_references.py::TestAbstractPackageReference.test_get_packages_no_cache` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: twyn.trusted\_packages.exceptions.InvalidJSONError: \`packages\` key not in JSON.)
4. Regression: `tests/trusted_packages/test_references.py::TestAbstractPackageReference.test_get_packages_downloads_when_cache_has_invalid_package_names` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: twyn.trusted\_packages.exceptions.InvalidJSONError: \`packages\` key not in JSON.)
5. Regression: `tests/trusted_packages/test_references.py::TestAbstractPackageReference.test_cache_is_saved_when_not_existing` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: twyn.trusted\_packages.exceptions.InvalidJSONError: \`packages\` key not in JSON.)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.333, mutants 6, killed 2, survived 4 |
| `regressions` | `found` | compared 151, regressions 13, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 26 |
| `behaviour_diff` | `partial` | inputs compared 442, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 3, inputs tried 177, properties counted 1, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 5; the rest in receipt.json)
- `src/twyn/trusted_packages/references/base.py:78`: `             if not packages: ` → `             if packages: ` made no test fail; no input tried behaved differently from the fix (`m-0443ca862eea`)
- `src/twyn/trusted_packages/references/base.py:84`: `         normalized_packages = self.normalize_packages(packages) ` → `         normalized_packages = packages ` made no test fail; no input tried behaved differently from the fix (`m-2b772e4fc830`)
- `src/twyn/trusted_packages/references/base.py:38`: `         response.raise_for_status() ` → `         pass ` made no test fail; no input tried behaved differently from the fix (`m-9a1726d99a62`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 41,092 input and 2,733 output tokens, cost $0.1918 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 3.13 s: base suite passed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.9 s: 3 changed module(s) imported from the copies (6 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 19.61 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 96.91 s: the tests killed 2 of 6 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 19.38 s: 13 confirmed: tests/main/test\_main.py::TestCheckDependencies.test\_check\_dependencies\_npm\_v3, tests/main/test\_main.py::TestCheckDependencies.test\_check\_dependencies\_yarn, tests/trusted\_packages/test\_references.py::TestAbstractPackageReference.test\_get\_packages\_no\_cache, tests/trusted\_packages/test\_references.py::TestAbstractPackageReference.test\_get\_packages\_downloads\_when\_cache\_has\_invalid\_package\_names, tests/trusted\_packages/test\_references.py::TestAbstractPackageReference.test\_cache\_is\_saved\_...
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors tests/main/test_main.py tests/trusted_packages/test_references.py`
- `fix_line_coverage`: `ok`, 4.33 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `partial`, 31.71 s: 442 input(s) compared on 3 function(s): 0 changed with the fix; not complete: src/twyn/trusted\_packages/references/top\_npm\_reference.py: module-level code that computes a value changed (line 17, 18, 19); what uses it is not compared
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `none_found`, 30.81 s: no counterexample found in 177 inputs against 1 properties
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### More counterexamples
- Regression: `tests/trusted_packages/test_references.py::TestTopPyPiReference.test_get_trusted_packages` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: twyn.trusted\_packages.exceptions.InvalidJSONError: \`packages\` key not in JSON.)
- Regression: `tests/trusted_packages/test_references.py::TestTopPyPiReference.test__parse_no_rows` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: 'TopPyPiReference' object has no attribute '\_parse')
- Regression: `tests/trusted_packages/test_references.py::TestTopPyPiReference.test_empty_packages_list_exception` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: type object 'TopPyPiReference' has no attribute '\_parse')
- Regression: `tests/trusted_packages/test_references.py::TestTopPyPiReference.test__parse_retrieves_package_names` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: 'TopPyPiReference' object has no attribute '\_parse')
- Regression: `tests/trusted_packages/test_references.py::TestTopNpmReference.test_get_trusted_packages_v2` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: TypeError: unhashable type: 'dict')
- Regression: `tests/trusted_packages/test_references.py::TestTopNpmReference.test__parse_no_rows` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: 'TopNpmReference' object has no attribute '\_parse')
- Regression: `tests/trusted_packages/test_references.py::TestTopNpmReference.test_empty_packages_list_exception` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: type object 'TopNpmReference' has no attribute '\_parse')
- Regression: `tests/trusted_packages/test_references.py::TestTopNpmReference.test__parse_retrieves_package_names` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: 'TopNpmReference' object has no attribute '\_parse')
#### More changes no test noticed
- `src/twyn/trusted_packages/references/base.py:82`: `             self._save_trusted_packages_to_cache_if_enabled(... ` → `             pass ` made no test fail; no input tried behaved differently from the fix (`m-34de9424e2e6`)
- `src/twyn/trusted_packages/references/base.py:78`: `             if not packages: ` → `             if packages: ` made no test fail; no input tried behaved differently from the fix (`m-0443ca862eea`)
#### Fix lines run (report only)
- repro: 10 of 26 fix lines run
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
- reproduce: pyproject truncated to 3000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T12:33:08+00:00, issue sha256 `61835d7a10d782278c6c1b632106481024cfc2fa378ad46cc9015303d90715fc`

</details>
