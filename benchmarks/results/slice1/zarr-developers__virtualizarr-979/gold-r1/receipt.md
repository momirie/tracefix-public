## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the inlined-reference read failure and found no regressions, but Break My Fix showed that manifest\_from\_kerchunk\_chunk\_dict still breaks on an empty chunk dict ({}), raising ValueError: need a chunk grid shape if no chunks given. The fix also was not guarded by a test that fails without it.

**Why this level:** Break My Fix finding 1: an input that breaks virtualizarr.parsers.kerchunk.translator.manifest\_from\_kerchunk\_chunk\_dict

**Issue:** Error reading inlined reference data when trying to roundtrip virtual dataset · **Repo:** testbed · **Base** `tf-base` (`3194b09`) → **head** `tf-gold` (`718532e`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `manifest_from_kerchunk_chunk_dict(kerchunk_chunk_dict={})` → `raises ValueError: need a chunk grid shape if no chunks given` (before the fix: `raises ValueError: need a chunk grid shape if no chunks given`); breaks **inline\_never\_notimplemented**: “NotImplementedError: Reading inlined reference data is currently not supported. \[ToDo\]” (issue); test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.2, mutants 5, killed 1, survived 4 |
| `regressions` | `none_found` | compared 271, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 11 |
| `behaviour_diff` | `partial` | inputs compared 73, changes 7, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 30, properties counted 2, findings 1 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `virtualizarr.parsers.kerchunk.translator.manifest_from_kerchunk_chunk_dict` (`exception`, 7 inputs): `raises NotImplementedError` → `raises ValueError: Invalid format for chunk key: ''`; the Judge (advisory) calls it intended: The issue asks that inlined reference data stop raising NotImplementedError. With that fixed, the empty chunk key '' now hits the same invalid-key ValueError that list-form references already get.; the Judge (advisory) calls it intended: Inlined values are now parsed as the issue requests. The malformed chunk key is then rejected by the existing ChunkManifest key validation, so this is the normal error for a bad key.; the Judge (advisory) calls it intended: Following the issue's request to support inlined data, the NotImplementedError is gone. The invalid key now surfaces through the standard key validation.; the Judge (advisory) calls it intended: The inline string value is now accepted per the issue. The key 'INF' is not a valid chunk key, so the ValueError is the existing validation and not a new restriction.; the Judge (advisory) calls it intended: With inline-data support added as the issue asks, these malformed keys fail the same key-format check that applies to non-inlined references.

### Changes no test noticed (3 of 7; the rest in receipt.json)
- `virtualizarr/parsers/kerchunk/translator.py:222`: `             if raw.startswith(b"base64:"): ` → `             if not raw.startswith(b"base64:"): ` made no test fail; behaves differently from the fix on inputs no test checks (`m-fbb5f02a0c06`)
- `virtualizarr/parsers/kerchunk/translator.py:223`: `                 data = base64.b64decode(raw[len(b"base64:") :]) ` → `                 data = base64.b64decode(raw[len(b"base64:") ... ` made no test fail; not compared with the fix (`m-29be6916140c`)
- `virtualizarr/parsers/kerchunk/translator.py:223`: `                 data = base64.b64decode(raw[len(b"base64:") :]) ` → `                 data = raw[len(b"base64:") :] ` made no test fail; not compared with the fix (`m-2d4d458725b2`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 46,967 input and 7,208 output tokens, cost $0.3081 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 19.7 s: base suite failed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 8.37 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_imports.py`
- `reproduce`: `reproduced`, 30.56 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 362.42 s: the tests killed 1 of 5 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 55.01 s: none of the 271 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 5.01 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
- `behaviour_diff`: `partial`, 1597.44 s: 73 input(s) compared on 1 function(s): 7 changed with the fix; not complete: manifest\_from\_kerchunk\_chunk\_dict: the comparison did not finish
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s test_tracefix_diff.py`
- `break_my_fix`: `found`, 104.52 s: 1 finding(s), each proven by a failing repro file
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_finding_1.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_attack.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_probe.py`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### More changes no test noticed
- `virtualizarr/parsers/kerchunk/translator.py:227`: `                 path="", offset=0, length=len(data), data=data ` → `                 path="", offset=0, length=len(raw), data=data ` made no test fail; not compared with the fix (`m-c1c0173c8fdb`)
- `virtualizarr/parsers/kerchunk/translator.py:222`: `             if raw.startswith(b"base64:"): ` → `             if not (raw.startswith(b"base64:")): ` made no test fail; behaves differently from the fix on inputs no test checks (`m-dce85a510194`)
- `virtualizarr/parsers/kerchunk/translator.py:227`: `                 path="", offset=0, length=len(data), data=data ` → `                 path="", offset=(-1), length=len(data), data... ` made no test fail; not compared with the fix (`m-e55543ebd7b4`)
- `virtualizarr/parsers/kerchunk/translator.py:227`: `                 path="", offset=0, length=len(data), data=data ` → `                 path="", offset=1, length=len(data), data=data ` made no test fail; not compared with the fix (`m-5448b1c90a93`)
#### Fix lines run (report only)
- repro: 7 of 11 fix lines run
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
- behaviour\_diff: t1: the run ran out of time at input 105; it returns when run alone, so nothing hangs, but the comparison did not finish
- behaviour\_diff: the behaviour diff on surviving mutant 2 ended error before it finished:
- behaviour\_diff: the behaviour diff on surviving mutant 4 ended error before it finished:
- behaviour\_diff: the behaviour diff on surviving mutant 8 ended error before it finished:
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T13:24:35+00:00, issue sha256 `850a4bd16b4d94eceb05987913d87311358409fdd8fbb60824bfee4701ab0f2e`

</details>
