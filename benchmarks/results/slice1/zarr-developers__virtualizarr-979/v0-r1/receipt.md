## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the inlined-reference read failure, found no regressions, and saw the intended exception change in manifest\_from\_kerchunk\_chunk\_dict, but Break My Fix found a counterexample: a chunk dict like {'0': 'base64:'} raises NameError because 'base64' is not defined. Check that the fix imports the base64 module where inlined data is decoded, and note that the reproduce stage repor…

**Why this level:** Break My Fix finding 1: an input that breaks virtualizarr.parsers.kerchunk.translator.manifest\_from\_kerchunk\_chunk\_dict

**Issue:** Error reading inlined reference data when trying to roundtrip virtual dataset · **Repo:** testbed · **Base** `tf-base` (`3194b09`) → **head** `tf-v0` (`4c86088`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `manifest_from_kerchunk_chunk_dict(kerchunk_chunk_dict={'0': ...` → `raises NameError: name 'base64' is not defined` (before the fix: `raises NotImplementedError: Reading inlined reference data i...`); breaks **inline\_base64\_refs\_do\_not\_raise**: “Error reading inlined reference data when trying to roundtrip virtual dataset” (issue); 1 more input break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.5, mutants 6, killed 3, survived 3 |
| `regressions` | `none_found` | compared 271, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 10 |
| `behaviour_diff` | `partial` | inputs compared 73, changes 7, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 204, properties counted 2, findings 1 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `virtualizarr.parsers.kerchunk.translator.manifest_from_kerchunk_chunk_dict` (`exception`, 7 inputs): `raises NotImplementedError` → `raises ValueError: Invalid format for chunk key: ''`; the Judge (advisory) calls it intended: The issue asks that inlined (string) reference values stop raising NotImplementedError. With that gone, the invalid chunk key '' is now rejected by the normal key validation with ValueError.; the Judge (advisory) calls it intended: Same rule as the issue: inline string values are now parsed instead of rejected. The malformed key is then caught by the existing chunk-key validation.; the Judge (advisory) calls it intended: The issue's request to support inlined data removes the NotImplementedError. The ValueError comes from the pre-existing check on the invalid key.; the Judge (advisory) calls it intended: Inline data is accepted, as the issue requests. The key 'INF' is not a valid chunk key, so the ValueError from key validation is appropriate.; the Judge (advisory) calls it intended: Following the issue, inline string values no longer raise NotImplementedError. The invalid keys now surface the existing ValueError for an invalid chunk key.

### Changes no test noticed (3 of 5; the rest in receipt.json)
- `virtualizarr/parsers/kerchunk/translator.py:222`: `data = base64.b64decode(raw[len(b"base64:") :])` → `data = base64.b64decode(raw)` made no test fail; not compared with the fix (`m-4613162b810c`)
- `virtualizarr/parsers/kerchunk/translator.py:222`: `data = base64.b64decode(raw[len(b"base64:") :])` → `data = base64.b64decode(raw[len(b"base64:") - 1 :])` made no test fail; not compared with the fix (`m-a994ef77248f`)
- `virtualizarr/parsers/kerchunk/translator.py:226`: `path="", offset=0, length=len(data), data=data` → `path="", offset=0, length=len(raw), data=data` made no test fail; not compared with the fix (`m-14a3c541511a`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 9 calls, 55,542 input and 8,330 output tokens, cost $0.3401 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 16.83 s: base suite failed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 10.42 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_imports.py`
- `reproduce`: `reproduced`, 74.61 s: attempt 2: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 308.06 s: the tests killed 3 of 6 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 74.33 s: none of the 271 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 4.6 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
- `behaviour_diff`: `partial`, 1355.66 s: 73 input(s) compared on 1 function(s): 7 changed with the fix; not complete: manifest\_from\_kerchunk\_chunk\_dict: the comparison did not finish
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no virtualizarr/tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s test_tracefix_diff.py`
- `break_my_fix`: `found`, 108.51 s: 1 finding(s), each proven by a failing repro file
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_finding_1.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_attack.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no test_tracefix_probe.py`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### More changes no test noticed
- `virtualizarr/parsers/kerchunk/translator.py:226`: `                 path="", offset=0, length=len(data), data=data ` → `                 path="", offset=(-1), length=len(data), data... ` made no test fail; not compared with the fix (`m-07364016083b`)
- `virtualizarr/parsers/kerchunk/translator.py:226`: `                 path="", offset=0, length=len(data), data=data ` → `                 path="", offset=1, length=len(data), data=data ` made no test fail; not compared with the fix (`m-90caa072c9c8`)
#### Fix lines run (report only)
- repro: 8 of 10 fix lines run
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
- behaviour\_diff: the behaviour diff on surviving mutant 10 ended error before it finished:
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T14:01:04+00:00, issue sha256 `850a4bd16b4d94eceb05987913d87311358409fdd8fbb60824bfee4701ab0f2e`

</details>
