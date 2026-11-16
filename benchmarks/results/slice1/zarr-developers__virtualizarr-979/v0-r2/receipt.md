## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The bug was reproduced, with a test that fails before the fix and passes after it, and the only behaviour changes found were exception changes in manifest\_from\_kerchunk\_chunk\_dict, all judged intended; no regressions or breaking inputs were found. The main gap is that the tests did not kill enough mutants to reach L2 and Break My Fix was inconclusive, so the next step is to strengthen tests aroun…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 4 mutants; 80% is needed

**Issue:** Error reading inlined reference data when trying to roundtrip virtual dataset · **Repo:** testbed · **Base** `tf-base` (`3194b09`) → **head** `tf-v0` (`4c86088`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.5, mutants 4, killed 2, survived 2 |
| `regressions` | `none_found` | compared 271, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 10 |
| `behaviour_diff` | `compared` | inputs compared 149, changes 29, groups 2 |
| `break_my_fix` | `inconclusive` | targets 1, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `virtualizarr.parsers.kerchunk.translator.manifest_from_kerchunk_chunk_dict` (`exception`, 16 inputs): `raises NotImplementedError` → `raises TypeError`; the Judge (advisory) calls it intended: The issue asks that inlined (string) chunk values be read rather than raising NotImplementedError. The inline entries are now accepted, and the TypeError comes from the other malformed tuple entries in the same dict.; the Judge (advisory) calls it intended: Per the issue, inline string values are now parsed instead of raising NotImplementedError. The TypeError is raised for the separate malformed tuple references.; the Judge (advisory) calls it intended: The issue's inline-data support removes the NotImplementedError. The remaining TypeError stems from the invalid non-inline entries.; the Judge (advisory) calls it intended: Inline values are now handled as the issue requests. The error now surfaces from the malformed tuple entries with bogus offsets and lengths.; the Judge (advisory) calls it intended: Same rule from the issue: inline strings are no longer rejected, so validation of the other invalid entries raises instead.; the Judge (advisory) calls it intended: The issue asks for inline reference data to be readable. The TypeError comes from the other garbage tuple entries.; the Judge (advisory) calls it intended: Inline support requested in the issue removes the early NotImplementedError. The later TypeError is from the invalid tuple refs.; the Judge (advisory) calls it intended: The issue's inline-data rule is applied here. The resulting error is from the malformed non-inline references.; the Judge (advisory) calls it intended: Inline strings are parsed per the issue. The TypeError reflects the other invalid entries in the input.; the Judge (advisory) calls it intended: Per the issue, inline data is no longer unsupported. The failure now comes from the malformed tuple entries.; the Judge (advisory) calls it intended: The issue asks to support inline values. The remaining TypeError comes from the invalid tuple references, not the inline handling.
- `virtualizarr.parsers.kerchunk.translator.manifest_from_kerchunk_chunk_dict` (`exception`, 13 inputs): `raises NotImplementedError` → `raises ValueError: Invalid format for chunk key: ''`; the Judge (advisory) calls it intended: The inline value is now accepted as the issue asks. The ValueError is normal manifest validation of the invalid chunk key ''.; the Judge (advisory) calls it intended: Inline data is read per the issue. Chunk-key validation then rejects the malformed key, which is expected.; the Judge (advisory) calls it intended: The issue's inline support removes the NotImplementedError. The invalid chunk key '\\xca' is correctly rejected by ChunkManifest.; the Judge (advisory) calls it intended: Inline values are accepted as the issue requests. The ValueError comes from the existing chunk-key format validation.; the Judge (advisory) calls it intended: Same issue rule: inline data is now parsed. The invalid key is then rejected by the manifest's key check.; the Judge (advisory) calls it intended: Inline strings are handled per the issue. The ValueError is pre-existing validation of the malformed chunk keys.; the Judge (advisory) calls it intended: The issue asks to read inline reference data. The subsequent ValueError is due to the invalid chunk key format, not the fix.

### Changes no test noticed (3 of 4; the rest in receipt.json)
- `virtualizarr/parsers/kerchunk/translator.py:222`: `data = base64.b64decode(raw[len(b"base64:") :])` → `data = base64.b64decode(raw[len(b"base64:") - 1 :])` made no test fail; no input tried behaved differently from the fix (`m-a994ef77248f`)
- `virtualizarr/parsers/kerchunk/translator.py:222`: `data = base64.b64decode(raw[len(b"base64:") :])` → `data = base64.b64decode(raw)` made no test fail; no input tried behaved differently from the fix (`m-4613162b810c`)
- `virtualizarr/parsers/kerchunk/translator.py:226`: `                 path="", offset=0, length=len(data), data=data ` → `                 path="", offset=(-1), length=len(data), data... ` made no test fail; no input tried behaved differently from the fix (`m-07364016083b`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 9 calls, 65,222 input and 10,448 output tokens, cost $0.4262 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 15.21 s: base suite failed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 7.96 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_imports.py`
- `reproduce`: `reproduced`, 56.46 s: attempt 2: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 282.7 s: the tests killed 2 of 4 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 70.46 s: none of the 271 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 4.51 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
- `behaviour_diff`: `compared`, 74.3 s: 149 input(s) compared on 1 function(s): 29 changed with the fix
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s test_tracefix_diff.py`
- `break_my_fix`: `inconclusive`, 62.38 s: every property was contradicted or could not run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_attack.py`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### More changes no test noticed
- `virtualizarr/parsers/kerchunk/translator.py:226`: `                 path="", offset=0, length=len(data), data=data ` → `                 path="", offset=1, length=len(data), data=data ` made no test fail; no input tried behaved differently from the fix (`m-90caa072c9c8`)
#### Fix lines run (report only)
- repro: 6 of 10 fix lines run
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
- Tracefix 0.0.1, receipt schema 1, created 2026-10-20T12:20:57+00:00, issue sha256 `850a4bd16b4d94eceb05987913d87311358409fdd8fbb60824bfee4701ab0f2e`

</details>
