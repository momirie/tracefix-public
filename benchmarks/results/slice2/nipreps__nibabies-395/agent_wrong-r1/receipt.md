## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The original ValueError was reproduced and the fix guards against it with no regressions found, but Break My Fix found an input that still breaks parse\_bids\_for\_age\_months (a call with a very long bids\_root string). Look at that counterexample first to see whether the long path needs handling, and note the behaviour diff was only partial.

**Why this level:** Break My Fix finding 1: an input that breaks nibabies.utils.bids.parse\_bids\_for\_age\_months

**Issue:** Issue finding age in months from participants.tsv for v24.0.0 · **Repo:** testbed · **Base** `tf-base` (`f7969c8`) → **head** `tf-agent_wrong` (`777c5db`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `parse_bids_for_age_months(bids_root='aaaaaaaaaaaaaaaaaaaaaaa...` → `raises OSError: [Errno 36] File name too long: 'aaaaaaaaaaaa...` (before the fix: `raises OSError: [Errno 36] File name too long: 'aaaaaaaaaaaa...`); breaks **returns\_int\_or\_none\_without\_raising**: “session\_id: str \| None = None, ) -&gt; int \| None:” (signature); 3 more inputs break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 0\.875, mutants 8, killed 7, survived 1 |
| `regressions` | `none_found` | compared 12, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 26 |
| `behaviour_diff` | `partial` | inputs compared 211, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 2, inputs tried 466, properties counted 6, findings 1 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `nibabies/utils/bids.py:311`: `         if secondary_column and secondary_val: ` → `         if secondary_column or secondary_val: ` made no test fail; no input tried behaved differently from the fix (`m-2faa144b8fa4`)
- `nibabies/utils/bids.py:311`: `         if secondary_column and secondary_val: ` → `         if secondary_column or secondary_val: ` made no test fail; no input tried behaved differently from the fix (`m-2faa144b8fa4`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 41,268 input and 6,064 output tokens, cost $0.2475 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 13.27 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 6.42 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 28.84 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no nibabies/u...`
- `guard`: `guarded`, 263.31 s: the reproduction test fails with the fix reverted, and the tests killed 7 of 8 mutants
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no nibabies/u...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no nibabies/u...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 13.53 s: none of the 12 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 9.61 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no nibabies/u...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no nibabies/u...`
- `behaviour_diff`: `partial`, 17.68 s: 211 input(s) compared on 1 function(s): 0 changed with the fix; not complete: \_get\_age\_from\_tsv: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 69.19 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.02 s: no candidate was confirmed (1 reported)
#### Break My Fix targets
- `nibabies.utils.bids.parse_bids_for_age_months` (`nibabies/utils/bids.py`): 286 inputs
- `nibabies.utils.bids._get_age_from_tsv` (`nibabies/utils/bids.py`): 180 inputs
#### Fix lines run (report only)
- repro: 20 of 26 fix lines run
- pr\_test: 21 of 26 fix lines run
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
- guard: only the first 10 of 18 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.16: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T19:47:10+00:00, issue sha256 `4f75d1904f5cc1b73746999247f16ca2772b86a628216c0d72ac874dc050e548`

</details>
