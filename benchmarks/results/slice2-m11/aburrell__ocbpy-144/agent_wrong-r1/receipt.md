## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug with a test that fails before the fix and passes after it, but the PR's own test file test\_fix.py still passes with the fix reverted, so it does not guard against this regression. The most important next step is to add or adjust a test that exercises a dual boundary pair with a good OCB and an out-of-range EAB index, so that it fails without the fix.

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the PR's test file test\_fix.py does not fail with the fix reverted (passed)

**Issue:** dual boundary class can have a bad pair · **Repo:** testbed · **Base** `tf-base` (`728bfcb`) → **head** `tf-agent_wrong` (`cce6983`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 3, killed 0, survived 3 |
| `regressions` | `none_found` | compared 363, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 169 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_on_head` | attempts 2, report only True |

**Rule mutants by kind (report only):** body: 0 of 2 killed; compare: 0 of 2 killed; logic: 0 of 1 killed; negate\_if: 0 of 1 killed; constant: 0 of 1 killed; arithmetic: 0 of 1 killed; drop\_call: 0 of 1 killed; reraise: 0 of 1 killed; no place for membership, loop

### Changes no test noticed (3 of 13; the rest in receipt.json)
- `ocbpy/_boundary.py:1210`: `             if ocb_target_ind < self.ocb.records: ` → `             if ocb_target_ind <= self.ocb.records: ` made no test fail; not compared with the fix (`m-2e2ffff51f70`)
- `ocbpy/_boundary.py:1215`: `             if eab_target_ind < self.eab.records: ` → `             if eab_target_ind <= self.eab.records: ` made no test fail; not compared with the fix (`m-7dc17bc520ca`)
- `ocbpy/_boundary.py:1213`: `                 self.ocb.rec_ind = self.ocb.records  # Set t... ` → `                 self.ocb.rec_ind = self.ocb.records - 1  # S... ` made no test fail; not compared with the fix (`m-f3a4eb64d07a`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (DualBoundary.rec\_ind: a property setter or deleter: not called yet; debug\_dual\_boundary\_pairing: new with the fix: nothing to compare; debug\_specific\_timestamp: new with the fix: nothing to compare)); break\_my\_fix: skipped (the fix changes no function Break My Fix can call (debug\_dual\_boundary\_pairing: it takes no parameters to vary; debug\_specific\_timestamp: it takes no parameters to vary; DualBoundary.rec\_ind: a property setter or deleter: not called yet)); Break My Fix could not attack debug\_dual\_boundary\_pairing: it takes no parameters to vary; Break My Fix could not attack debug\_specific\_timestamp: it takes no parameters to vary; and 9 more in receipt.json
- **Model use:** 5 calls, 25,234 input and 2,765 output tokens, cost $0.0820 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 99.56 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.39 s: 3 changed module(s) imported from the copies (4 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 9.18 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no ocbpy/test...`
- `guard`: `not_guarded`, 2022.11 s: the PR's test file test\_fix.py does not fail with the fix reverted (passed)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no ocbpy/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_fix.py`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 100.55 s: none of the 363 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 4.47 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no ocbpy/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_fix.py`
- `behaviour_diff`: `skipped`, 0.29 s: the fix changes no function the behaviour diff can call (DualBoundary.rec\_ind: a property setter or deleter: not called yet; debug\_dual\_boundary\_pairing: new with the fix: nothing to compare; debug\_specific\_timestamp: new with the fix: nothing to compare)
- `break_my_fix`: `skipped`, 0.02 s: the fix changes no function Break My Fix can call (debug\_dual\_boundary\_pairing: it takes no parameters to vary; debug\_specific\_timestamp: it takes no parameters to vary; DualBoundary.rec\_ind: a property setter or deleter: not called yet)
- `integrity`: `clean`, 0.07 s: no candidate was confirmed (2 reported)
- `blind`: `fails_on_head`, 175.91 s: attempt 2: fails the same way before and after the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no ocbpy/test...`
#### More changes no test noticed
- `debug_issue.py:12`: `     print("=== Debugging DualBoundary Pairing Logic ===")\n  ... ` → `     return None ` made no test fail; not compared with the fix (`m-3cc2e00d301c`)
- `debug_issue.py:30`: `         if dual.records > 0: ` → `         if dual.records >= 0: ` made no test fail; not compared with the fix (`m-cc2b1d7950e6`)
- `debug_issue.py:125`: `     if success1 and success2: ` → `     if success1 or success2: ` made no test fail; not compared with the fix (`m-d87761d4bf07`)
- `debug_issue.py:30`: `         if dual.records > 0: ` → `         if not (dual.records > 0): ` made no test fail; not compared with the fix (`m-f0be09719aa7`)
- `debug_issue.py:15`: `     stime = dt.datetime(2000, 1, 1) ` → `     stime = dt.datetime(1999, 1, 1) ` made no test fail; not compared with the fix (`m-4d20c3f66347`)
- `debug_issue.py:88`: `     stime = target_time - dt.timedelta(days=30) ` → `     stime = target_time + dt.timedelta(days=30) ` made no test fail; not compared with the fix (`m-37c329ad7ebf`)
- `debug_issue.py:12`: `     print("=== Debugging DualBoundary Pairing Logic ===") ` → `     pass ` made no test fail; not compared with the fix (`m-454b3ef52bd6`)
- `debug_issue.py:62`: `                     print(f"    ERROR: {e}") ` → `                     raise\n                    print(f"    ER... ` made no test fail; not compared with the fix (`m-d4409e890539`)
- `debug_issue.py:81`: `     print("\n=== Debugging Specific Timestamp (2002-10-31 20... ` → `     return None ` made no test fail; not compared with the fix (`m-89316997dc40`)
- `debug_issue.py:56`: `                     if dual.ocb.rec_ind >= dual.ocb.records: ` → `                     if dual.ocb.rec_ind > dual.ocb.records: ` made no test fail; not compared with the fix (`m-aec104221dca`)
#### Fix lines run (report only)
- repro: 6 of 169 fix lines run
- pr\_test: 0 of 169 fix lines run
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
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (DualBoundary.rec\_ind: a property setter or deleter: not called yet; debug\_dual\_boundary\_pairing: new with the fix: nothing to compare; debug\_specific\_timestamp: new with the fix: nothing to compare))
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call (debug\_dual\_boundary\_pairing: it takes no parameters to vary; debug\_specific\_timestamp: it takes no parameters to vary; DualBoundary.rec\_ind: a property setter or deleter: not called yet))
- Break My Fix could not attack debug\_dual\_boundary\_pairing: it takes no parameters to vary
- Break My Fix could not attack debug\_specific\_timestamp: it takes no parameters to vary
- Break My Fix could not attack DualBoundary.rec\_ind: a property setter or deleter: not called yet
- Break My Fix could not attack test\_dual\_boundary\_issue: it takes no parameters to vary
- Break My Fix could not attack test\_vort2ascii\_with\_dual\_boundary: it takes no parameters to vary
- the behaviour diff could not compare DualBoundary.rec\_ind: a property setter or deleter: not called yet
- the behaviour diff could not compare debug\_dual\_boundary\_pairing: new with the fix: nothing to compare
- the behaviour diff could not compare debug\_specific\_timestamp: new with the fix: nothing to compare
- the behaviour diff could not compare test\_dual\_boundary\_issue: new with the fix: nothing to compare
- the behaviour diff could not compare test\_vort2ascii\_with\_dual\_boundary: new with the fix: nothing to compare
#### Notes
- guard: 6 of the 9 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 196 rule mutants were run
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-07T15:54:57+00:00, issue sha256 `df0b89ebbdaec29b1769274cd6105d54d6735eaacf18bdeab34158668fce44bf`

</details>
