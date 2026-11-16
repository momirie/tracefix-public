## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): At L1, the bug was reproduced: a test fails before the fix and passes after it, but the PR's own test file test\_5ttgen\_issue.py still passed with the fix reverted, so it does not guard against this bug. The most important next step is to strengthen test\_5ttgen\_issue.py so it exercises the new 5ttgen inputs and fails without the fix; regression and break-my-fix stages were skipped.

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the PR's test file test\_5ttgen\_issue.py does not fail with the fix reverted (passed)

**Issue:** \[ENH\] Enhance implementation of 5ttgen · **Repo:** testbed · **Base** `tf-base` (`e03ab6f`) → **head** `tf-agent_ok` (`83bd9e1`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.5, mutants 10, killed 5, survived 5 |
| `regressions` | `skipped` | compared 0, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 164 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 15; the rest in receipt.json)
- `nipype/interfaces/mrtrix3/utils.py:270`: `         argstr="-template %s", ` → `         argstr="-templ %s", ` made no test fail; not compared with the fix (`m-14415dc5ccc9`)
- `nipype/interfaces/mrtrix3/utils.py:277`: `         argstr="-hippocampi %s", ` → `         argstr="-hippocampus %s", ` made no test fail; not compared with the fix (`m-0d7b2fbcf2fb`)
- `nipype/interfaces/mrtrix3/utils.py:281`: `         argstr="-white_stem", ` → `         argstr="-white-stem", ` made no test fail; not compared with the fix (`m-d9e66c776f2b`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; regressions: skipped (no test the fix left untouched passed before it); behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (test\_fsl\_algorithm: new with the fix: nothing to compare; test\_freesurfer\_algorithm: new with the fix: nothing to compare; test\_hsvs\_algorithm: new with the fix: nothing to compare)); break\_my\_fix: skipped (the fix changes no function Break My Fix can call (cleanup\_dummy\_files: it takes no parameters to vary; test\_freesurfer\_algorithm: it takes no parameters to vary; test\_fsl\_algorithm: it takes no parameters to vary)); Break My Fix could not attack cleanup\_dummy\_files: it takes no parameters to vary; and 10 more in receipt.json
- **Model use:** 4 calls, 25,219 input and 2,133 output tokens, cost $0.0762 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 141.41 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.51 s: 2 changed module(s) imported from the copies (3 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 28.11 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no nipype/alg...`
- `guard`: `not_guarded`, 4658.48 s: the PR's test file test\_5ttgen\_issue.py does not fail with the fix reverted (passed)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no nipype/alg...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_5ttge...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `skipped`, 3.29 s: no test the fix left untouched passed before it
- `fix_line_coverage`: `ok`, 7.21 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no nipype/alg...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_5ttge...`
- `behaviour_diff`: `skipped`, 3.29 s: the fix changes no function the behaviour diff can call (test\_fsl\_algorithm: new with the fix: nothing to compare; test\_freesurfer\_algorithm: new with the fix: nothing to compare; test\_hsvs\_algorithm: new with the fix: nothing to compare)
- `break_my_fix`: `skipped`, 0.03 s: the fix changes no function Break My Fix can call (cleanup\_dummy\_files: it takes no parameters to vary; test\_freesurfer\_algorithm: it takes no parameters to vary; test\_fsl\_algorithm: it takes no parameters to vary)
- `integrity`: `clean`, 0.04 s: no candidate was confirmed (1 reported)
#### More changes no test noticed
- `nipype/interfaces/mrtrix3/utils.py:286`: `         argstr="-lut %s", ` → `         argstr="-lut_file %s", ` made no test fail; not compared with the fix (`m-a8a02022093f`)
- `nipype/interfaces/mrtrix3/utils.py:275`: `         "first", ` → `         "frst", ` made no test fail; not compared with the fix (`m-e870e7fb4ed2`)
- `comprehensive_test_5ttgen.py:33`: `     print("=== TESTING FSL ALGORITHM ===")\n    \n    try:\n   ... ` → `     return None ` made no test fail; not compared with the fix (`m-392499a0829d`)
- `comprehensive_test_5ttgen.py:79`: `     print("\n=== TESTING FREESURFER ALGORITHM ===")\n    \n   ... ` → `     return None ` made no test fail; not compared with the fix (`m-f3ef341fc6dc`)
- `comprehensive_test_5ttgen.py:120`: `     print("\n=== TESTING HSVS ALGORITHM ===")\n    \n    try:\n... ` → `     return None ` made no test fail; not compared with the fix (`m-9254fed7036a`)
- `comprehensive_test_5ttgen.py:161`: `     print("\n=== TESTING GENERAL PARAMETERS ===")\n    \n    t... ` → `     return None ` made no test fail; not compared with the fix (`m-ed6b54f57b90`)
- `comprehensive_test_5ttgen.py:9`: `sys.path.insert(0, '/workspace/nipy__nipype__1.8')` → `sys.path.insert((-1), '/workspace/nipy__nipype__1.8')` made no test fail; not compared with the fix (`m-ec51e93482b0`)
- `comprehensive_test_5ttgen.py:9`: `sys.path.insert(0, '/workspace/nipy__nipype__1.8')` → `sys.path.insert(1, '/workspace/nipy__nipype__1.8')` made no test fail; not compared with the fix (`m-2c48c37f59df`)
- `comprehensive_test_5ttgen.py:21`: `     if not os.path.exists(dummy_file): ` → `     if os.path.exists(dummy_file): ` made no test fail; not compared with the fix (`m-f67ffe4bbf49`)
- `comprehensive_test_5ttgen.py:29`: `     sys.exit(1) ` → `     sys.exit(0) ` made no test fail; not compared with the fix (`m-3ec70956a7b7`)
- `comprehensive_test_5ttgen.py:29`: `     sys.exit(1) ` → `     sys.exit(2) ` made no test fail; not compared with the fix (`m-8ae1f055f532`)
- `comprehensive_test_5ttgen.py:44`: `         gen5tt.inputs.premasked = True ` → `         gen5tt.inputs.premasked = False ` made no test fail; not compared with the fix (`m-4172487c53eb`)
#### Fix lines run (report only)
- repro: 34 of 164 fix lines run
- pr\_test: 34 of 164 fix lines run
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
- regressions: skipped (no test the fix left untouched passed before it)
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (test\_fsl\_algorithm: new with the fix: nothing to compare; test\_freesurfer\_algorithm: new with the fix: nothing to compare; test\_hsvs\_algorithm: new with the fix: nothing to compare))
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call (cleanup\_dummy\_files: it takes no parameters to vary; test\_freesurfer\_algorithm: it takes no parameters to vary; test\_fsl\_algorithm: it takes no parameters to vary))
- Break My Fix could not attack cleanup\_dummy\_files: it takes no parameters to vary
- Break My Fix could not attack test\_freesurfer\_algorithm: it takes no parameters to vary
- Break My Fix could not attack test\_fsl\_algorithm: it takes no parameters to vary
- Break My Fix could not attack test\_general\_parameters: it takes no parameters to vary
- Break My Fix could not attack test\_hsvs\_algorithm: it takes no parameters to vary
- the behaviour diff could not compare test\_fsl\_algorithm: new with the fix: nothing to compare
- the behaviour diff could not compare test\_freesurfer\_algorithm: new with the fix: nothing to compare
- the behaviour diff could not compare test\_hsvs\_algorithm: new with the fix: nothing to compare
- the behaviour diff could not compare test\_general\_parameters: new with the fix: nothing to compare
- the behaviour diff could not compare cleanup\_dummy\_files: new with the fix: nothing to compare
#### Notes
- guard: only the first 10 of 47 rule mutants were run
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T19:05:50+00:00, issue sha256 `7b35bf59a6794ddaae6c84c7c52d1688c89340fa5a23d7318626b39b1e4e041d`

</details>
