## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): At L1, the bug was reproduced: a test fails before the fix and passes after it, and the only behaviour changes observed are exception changes in manifest\_from\_kerchunk\_chunk\_dict that the Judge labelled intended. The tests did not kill enough mutants to reach L2 and Break My Fix was inconclusive, so the next thing to look at is strengthening tests around reading inlined kerchunk references so the…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 5 of 7 mutants; 80% is needed

**Issue:** Error reading inlined reference data when trying to roundtrip virtual dataset · **Repo:** testbed · **Base** `tf-base` (`3194b09`) → **head** `tf-gold` (`718532e`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.714, mutants 7, killed 5, survived 2 |
| `regressions` | `none_found` | compared 271, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 11 |
| `behaviour_diff` | `compared` | inputs compared 149, changes 29, groups 2 |
| `break_my_fix` | `inconclusive` | targets 1, inputs tried 1, properties counted 1, findings 0 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `virtualizarr.parsers.kerchunk.translator.manifest_from_kerchunk_chunk_dict` (`exception`, 16 inputs): `raises NotImplementedError` → `raises TypeError`; the Judge (advisory) calls it intended: The issue asks that inlined string refs stop raising NotImplementedError; the TypeError comes from pre-existing handling of the malformed tuple entries, not from the new inline path.; the Judge (advisory) calls it intended: Inline refs are now accepted as the issue requests; the TypeError comes from pre-existing validation of the malformed tuple refs elsewhere in the dict.; the Judge (advisory) calls it intended: Inline refs are now accepted as the issue requests; the TypeError comes from pre-existing validation of the malformed tuple refs elsewhere in the dict.; the Judge (advisory) calls it intended: Inline refs are now accepted as the issue requests; the TypeError comes from pre-existing validation of the invalid tuple refs elsewhere in the dict.; the Judge (advisory) calls it intended: Inline refs are now accepted as the issue requests; the TypeError comes from pre-existing validation of the malformed tuple refs elsewhere in the dict.; the Judge (advisory) calls it intended: Inline refs are now accepted as the issue requests; the TypeError comes from pre-existing validation of the malformed tuple refs elsewhere in the dict.; the Judge (advisory) calls it intended: Inline refs are now accepted as the issue requests; the TypeError comes from pre-existing validation of the invalid tuple refs elsewhere in the dict.; the Judge (advisory) calls it intended: Inline refs are now accepted as the issue requests; the TypeError comes from pre-existing validation of the invalid tuple refs elsewhere in the dict.; the Judge (advisory) calls it intended: Inline refs are now accepted as the issue requests; the TypeError comes from pre-existing validation of the malformed tuple refs elsewhere in the dict.; the Judge (advisory) calls it intended: Inline refs are now accepted as the issue requests; the TypeError comes from pre-existing validation of the malformed tuple refs elsewhere in the dict.; the Judge (advisory) calls it intended: Inline refs are now accepted as the issue requests; the TypeError comes from pre-existing validation of the malformed tuple refs elsewhere in the dict.
- `virtualizarr.parsers.kerchunk.translator.manifest_from_kerchunk_chunk_dict` (`exception`, 13 inputs): `raises NotImplementedError` → `raises ValueError: Invalid format for chunk key: ''`; the Judge (advisory) calls it intended: Inline data no longer raises NotImplementedError, per the issue; the invalid chunk key '' is now rejected by the existing ChunkManifest key validation.; the Judge (advisory) calls it intended: Inline data no longer raises NotImplementedError, per the issue; the invalid chunk key is now rejected by the existing key validation.; the Judge (advisory) calls it intended: Inline data no longer raises NotImplementedError, per the issue; the invalid chunk key is now rejected by the existing key validation.; the Judge (advisory) calls it intended: Inline data no longer raises NotImplementedError, per the issue; the invalid chunk key is now rejected by the existing key validation.; the Judge (advisory) calls it intended: Inline data no longer raises NotImplementedError, per the issue; the invalid chunk key is now rejected by the existing key validation.; the Judge (advisory) calls it intended: Inline data no longer raises NotImplementedError, per the issue; the invalid chunk key is now rejected by the existing key validation.; the Judge (advisory) calls it intended: Inline data no longer raises NotImplementedError, per the issue; the invalid chunk key is now rejected by the existing key validation.

### Changes no test noticed (3 of 4; the rest in receipt.json)
- `virtualizarr/parsers/kerchunk/translator.py:223`: `                 data = base64.b64decode(raw[len(b"base64:") :]) ` → `                 data = base64.b64decode(raw[len(b"base64:") ... ` made no test fail; no input tried behaved differently from the fix (`m-29be6916140c`)
- `virtualizarr/parsers/kerchunk/translator.py:227`: `                 path="", offset=0, length=len(data), data=data ` → `                 path="", offset=0, length=len(raw), data=data ` made no test fail; no input tried behaved differently from the fix (`m-c1c0173c8fdb`)
- `virtualizarr/parsers/kerchunk/translator.py:227`: `                 path="", offset=0, length=len(data), data=data ` → `                 path="", offset=(-1), length=len(data), data... ` made no test fail; no input tried behaved differently from the fix (`m-e55543ebd7b4`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 57,261 input and 9,706 output tokens, cost $0.3977 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 16.24 s: base suite failed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 7.92 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_imports.py`
- `reproduce`: `reproduced`, 29.62 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 296.36 s: the tests killed 5 of 7 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 57.08 s: none of the 271 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 4.57 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
- `behaviour_diff`: `compared`, 75.68 s: 149 input(s) compared on 1 function(s): 29 changed with the fix
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s test_tracefix_diff.py`
- `break_my_fix`: `inconclusive`, 191.77 s: the attack on manifest\_from\_kerchunk\_chunk\_dict did not finish
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_attack.py`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
#### More changes no test noticed
- `virtualizarr/parsers/kerchunk/translator.py:227`: `                 path="", offset=0, length=len(data), data=data ` → `                 path="", offset=1, length=len(data), data=data ` made no test fail; no input tried behaved differently from the fix (`m-5448b1c90a93`)
#### Fix lines run (report only)
- repro: 6 of 11 fix lines run
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
- Tracefix 0.0.1, receipt schema 1, created 2026-10-20T12:09:33+00:00, issue sha256 `850a4bd16b4d94eceb05987913d87311358409fdd8fbb60824bfee4701ab0f2e`

</details>
