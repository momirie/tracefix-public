## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the participants.tsv age error and found counterexamples against the fix: an existing test (test\_get\_age\_from\_tsv\[session\_id-x1-data0-False-None\]) passed before the fix and fails after it, and Break My Fix found an input that breaks parse\_bids\_for\_age\_months. Look first at that regressed test and at the new exceptions age\_to\_months now raises, which the Judge labelled susp…

**Why this level:** Break My Fix finding 1: an input that breaks nibabies.utils.bids.parse\_bids\_for\_age\_months; regression: nibabies/utils/tests/test\_bids.py::test\_get\_age\_from\_tsv\[session\_id-x1-data0-False-None\] passed before the fix and fails after it

**Issue:** Issue finding age in months from participants.tsv for v24.0.0 · **Repo:** testbed · **Base** `tf-base` (`f7969c8`) → **head** `tf-v0` (`9884089`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `parse_bids_for_age_months(bids_root='aaaaaaaaaaaaaaaaaaaaaaa...` → `raises OSError: [Errno 36] File name too long: 'aaaaaaaaaaaa...` (before the fix: `raises OSError: [Errno 36] File name too long: 'aaaaaaaaaaaa...`); breaks **returns\_int\_or\_none**: “session\_id: str \| None = None, ) -&gt; int \| None:” (signature); 1 more input break it the same way; test: `findings/finding_1.py`
2. Regression: `nibabies/utils/tests/test_bids.py::test_get_age_from_tsv[session_id-x1-data0-False-None]` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 'pd' is not defined)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.6, mutants 5, killed 3, survived 2 |
| `regressions` | `found` | compared 21, regressions 1, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 19 |
| `behaviour_diff` | `partial` | inputs compared 428, changes 58, groups 3 |
| `break_my_fix` | `found` | targets 3, inputs tried 831, properties counted 15, findings 1 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `nibabies.utils.bids.age_to_months` (`type`, 55 inputs): `returns 6.0` → `returns 6`; the Judge (advisory) calls it intended: Matches the docstring example the PR added (\`age\_to\_months(0.5, 'years')\` -&gt; 6) and the \`-&gt; int\` return annotation.; the Judge (advisory) calls it intended: Float ages now flow in from the TSV, and the \`-&gt; int\` annotation requires an integer month count. Rounding 0.5 to 0 follows Python's round-half-to-even.; the Judge (advisory) calls it intended: The \`-&gt; int\` contract applied to a float input; 0 is the correct integer month count.; the Judge (advisory) calls it intended: Same rule as the 0.5-year docstring example: fractional years are converted and rounded to an int, as the annotation says.; the Judge (advisory) calls it intended: The \`-&gt; int\` rounding rule applied to a float month input. Negative ages are odd, but the type contract is the same.; the Judge (advisory) calls it intended: Same int-return rule from the \`-&gt; int\` annotation and the new docstring example, applied to a large float.; the Judge (advisory) calls it intended: Same int-return rounding rule from the \`-&gt; int\` annotation applied to a tiny float.
- `nibabies.utils.bids.age_to_months` (`new_raise`, 2 inputs): `returns -inf` → `raises OverflowError`; the Judge (advisory) calls it suspicious: Nothing in the issue or docstring asks for a new OverflowError. The function used to return -inf without raising, and the fix adds a crash on this input.; the Judge (advisory) calls it suspicious: Nothing written asks age\_to\_months to raise on infinite input. This is a new OverflowError the issue does not mention.
- `nibabies.utils.bids.age_to_months` (`new_raise`, 1 input): `returns nan` → `raises ValueError`; the Judge (advisory) calls it suspicious: A NaN age, for example from a missing TSV value, now raises ValueError instead of passing through. The issue asked to stop crashes on participants.tsv, not to add new ones.

### Changes no test noticed (3 of 8; the rest in receipt.json)
- `nibabies/utils/bids.py:290`: `     if len(df) > 1: ` → `     if len(df) > 2: ` made no test fail; no input tried behaved differently from the fix (`m-50b7d078d86f`)
- `nibabies/utils/bids.py:250`: `             index_val=r'^anat.*', ` → `             index_val=r'^func.*', ` made no test fail; no input tried behaved differently from the fix (`m-cb569da1fe7b`)
- `nibabies/utils/bids.py:290`: `     if len(df) > 1: ` → `     if not (len(df) > 1): ` made no test fail; no input tried behaved differently from the fix (`m-4ef81822a4b9`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 9 calls, 70,441 input and 10,470 output tokens, cost $0.4206 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 14.0 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 6.57 s: 2 changed module(s) imported from the copies (3 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 120.69 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no nibabies/i...`
- `guard`: `not_guarded`, 434.58 s: the tests killed 3 of 5 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no nibabies/i...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 57.84 s: 1 confirmed: nibabies/utils/tests/test\_bids.py::test\_get\_age\_from\_tsv\[session\_id-x1-data0-False-None\]
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 14.78 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no nibabies/i...`
- `behaviour_diff`: `partial`, 64.11 s: 428 input(s) compared on 2 function(s): 58 changed with the fix; not complete: \_get\_age\_from\_tsv: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 85.42 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `nibabies.utils.bids.parse_bids_for_age_months` (`nibabies/utils/bids.py`): 355 inputs
- `nibabies.utils.bids.age_to_months` (`nibabies/utils/bids.py`): 476 inputs
- `nibabies.utils.bids._get_age_from_tsv` (`nibabies/utils/bids.py`): not attacked (no property to check it against)
#### More changes no test noticed
- `nibabies/utils/bids.py:290`: `     if len(df) > 1: ` → `     if len(df) >= 1: ` made no test fail; no input tried behaved differently from the fix (`m-24f5649c9ac7`)
- `nibabies/utils/bids.py:290`: `     if len(df) > 1: ` → `     if len(df) > 0: ` made no test fail; no input tried behaved differently from the fix (`m-4548f90b5c82`)
- `nibabies/utils/bids.py:290`: `     if len(df) > 1: ` → `     if len(df) > 2: ` made no test fail; no input tried behaved differently from the fix (`m-50b7d078d86f`)
- `nibabies/utils/bids.py:293`: `             stacklevel=1, ` → `             stacklevel=0, ` made no test fail; no input tried behaved differently from the fix (`m-70d559b26ddc`)
- `nibabies/utils/bids.py:293`: `             stacklevel=1, ` → `             stacklevel=2, ` made no test fail; no input tried behaved differently from the fix (`m-441c9a60c829`)
#### Fix lines run (report only)
- repro: 12 of 19 fix lines run
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
- guard: only the first 10 of 14 rule mutants were run
- regressions: 10 untouched test(s) that passed before the fix did not run after it (skipped or not collected), so they were not compared
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.16: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T19:33:35+00:00, issue sha256 `4f75d1904f5cc1b73746999247f16ca2772b86a628216c0d72ac874dc050e548`

</details>
