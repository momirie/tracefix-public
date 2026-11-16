## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproducing the tensorstore failure (extra "checksum" member in the v2 compressor metadata) fails before the fix and passes after it, with no regressions found and the fix lines covered. However, the guard stage found the fix not guarded and mutation testing did not reach the L2 threshold, so the next step is to strengthen the tests so they catch mutations of the fixed code.

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 3 of 5 mutants; 80% is needed

**Issue:** Regression with 3.0.0rc1: reading zarr with tensorstore · **Repo:** testbed · **Base** `tf-base` (`f5cd290`) → **head** `tf-gold` (`ecca8b8`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.6, mutants 5, killed 3, survived 2 |
| `regressions` | `none_found` | compared 2222, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 4 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 4; the rest in receipt.json)
- `src/zarr/core/metadata/v2.py:122`: `                 if codec_config["id"] == "zstd" and not code... ` → `                 if codec_config["id"] == "zstd" or not codec... ` made no test fail; not compared with the fix (`m-d6d356cc0214`)
- `src/zarr/core/metadata/v2.py:122`: `                 if codec_config["id"] == "zstd" and not code... ` → `                 if codec_config["id"] == "zstd" and not code... ` made no test fail; not compared with the fix (`m-9f402501cc60`)
- `src/zarr/core/metadata/v2.py:122`: `                 if codec_config["id"] == "zstd" and not code... ` → `                 if codec_config["id"] == "zstd" or not codec... ` made no test fail; not compared with the fix (`m-d6d356cc0214`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (ArrayV2Metadata.to\_buffer\_dict.\_json\_convert: a nested function: it can't be imported, not attacked yet)); break\_my\_fix: skipped (the fix changes no function Break My Fix can call (ArrayV2Metadata.to\_buffer\_dict.\_json\_convert: a nested function: it can't be imported, not attacked yet)); Break My Fix could not attack ArrayV2Metadata.to\_buffer\_dict.\_json\_convert: a nested function: it can't be imported, not attacked yet; the behaviour diff could not compare ArrayV2Metadata.to\_buffer\_dict.\_json\_convert: a nested function: it can't be imported, not attacked yet; and 1 more in receipt.json
- **Model use:** 3 calls, 8,105 input and 1,267 output tokens, cost $0.0345 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 108.38 s: base suite failed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 6.99 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 26.36 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 1007.74 s: the tests killed 3 of 5 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 361.95 s: none of the 2222 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 3.28 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `skipped`, 0.29 s: the fix changes no function the behaviour diff can call (ArrayV2Metadata.to\_buffer\_dict.\_json\_convert: a nested function: it can't be imported, not attacked yet)
- `break_my_fix`: `skipped`, 0.01 s: the fix changes no function Break My Fix can call (ArrayV2Metadata.to\_buffer\_dict.\_json\_convert: a nested function: it can't be imported, not attacked yet)
- `integrity`: `clean`, 0.01 s: no candidate was confirmed (1 reported)
#### More changes no test noticed
- `src/zarr/core/metadata/v2.py:122`: `                 if codec_config["id"] == "zstd" and not code... ` → `                 if codec_config["id"] == "zstd" and not code... ` made no test fail; not compared with the fix (`m-9f402501cc60`)
#### Fix lines run (report only)
- repro: 0 of 4 fix lines run
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (ArrayV2Metadata.to\_buffer\_dict.\_json\_convert: a nested function: it can't be imported, not attacked yet))
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call (ArrayV2Metadata.to\_buffer\_dict.\_json\_convert: a nested function: it can't be imported, not attacked yet))
- Break My Fix could not attack ArrayV2Metadata.to\_buffer\_dict.\_json\_convert: a nested function: it can't be imported, not attacked yet
- the behaviour diff could not compare ArrayV2Metadata.to\_buffer\_dict.\_json\_convert: a nested function: it can't be imported, not attacked yet
#### Notes
- reproduce: pyproject truncated to 3000 characters for the prompt
- regressions: 1 untouched test(s) that passed before the fix did not run after it (skipped or not collected), so they were not compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T13:59:19+00:00, issue sha256 `b43dd1f4dba38d62644e33fd829f4a878bf4ba5d89170a26c836f8f2594219db`

</details>
