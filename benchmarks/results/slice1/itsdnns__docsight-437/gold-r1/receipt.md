## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproduced the bug and passes after the fix, with no regressions or breaking inputs found; the one behaviour change in comparison.routes.\_aggregate\_period was judged intended, but the guard stage reported the fix as not guarded and mutation testing fell short of L2. Next, check that the regression test would catch a reverted or weakened fix, especially that unsupported error counters stay…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 8 mutants; 80% is needed

**Issue:** Hide unsupported DOCSIS errors in Before/After Comparison · **Repo:** testbed · **Base** `tf-base` (`f478c6e`) → **head** `tf-gold` (`dc12da2`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.25, mutants 8, killed 2, survived 6 |
| `regressions` | `none_found` | compared 2246, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 32 |
| `behaviour_diff` | `partial` | inputs compared 1, changes 1, groups 1 |
| `break_my_fix` | `none_found` | targets 4, inputs tried 11, properties counted 13, findings 0 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `comparison.routes._aggregate_period` (`value`, 1 input): `returns {'snapshots': 0, 'avg': {'ds_power': None, 'ds_snr':...` → `returns {'snapshots': 0, 'avg': {'ds_power': None, 'ds_snr':...`; the Judge (advisory) calls it intended: The issue asks the comparison view to hide the errors chart when error counters are unsupported. Adding the errors\_supported flags (all False) to the empty-period result is additive and keeps the existing keys. The 0 totals are unchanged, so the untouched test on this input should still hold.

### Changes no test noticed (3 of 9; the rest in receipt.json)
- `app/modules/comparison/routes.py:101`: `     if period_a["total"].get("uncorr_errors") is not None an... ` → `     if period_a["total"].get("uncorr_errors") is not None or... ` made no test fail; no input tried behaved differently from the fix (`m-bfd3f5063462`)
- `app/modules/comparison/routes.py:103`: `     elif period_a.get("snapshots", 0) == 0 and period_b.get(... ` → `     elif period_a.get("snapshots", 0) == 0 or period_b.get("... ` made no test fail; no input tried behaved differently from the fix (`m-7bcd82d481e8`)
- `app/modules/comparison/routes.py:75`: `             "corr_errors": corr_total if corr_errors_support... ` → `             "corr_errors": corr_total if uncorr_errors_suppo... ` made no test fail; no input tried behaved differently from the fix (`m-2e0ca841dd93`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 75,619 input and 14,206 output tokens, cost $0.5393 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 122.95 s: base suite failed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 7.33 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 56.12 s: attempt 1: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 3336.77 s: the tests killed 2 of 8 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 435.69 s: none of the 2246 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 4.5 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `partial`, 50.93 s: 1 input(s) compared on 1 function(s): 1 changed with the fix; not complete: AnalysisMixin.get\_correlation\_timeline: the comparison did not finish
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `none_found`, 120.75 s: no counterexample found in 11 inputs against 13 properties
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_comparison_module.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### More changes no test noticed
- `app/modules/comparison/routes.py:78`: `         "errors_supported": corr_errors_supported or uncorr_... ` → `         "errors_supported": corr_errors_supported and uncorr... ` made no test fail; no input tried behaved differently from the fix (`m-faa1cb8a455e`)
- `app/modules/comparison/routes.py:47`: `         if corr_errors is not None: ` → `         if corr_errors: ` made no test fail; no input tried behaved differently from the fix (`m-64f6684b70ef`)
- `app/modules/comparison/routes.py:75`: `             "corr_errors": corr_total if corr_errors_support... ` → `             "corr_errors": corr_total if corr_errors_support... ` made no test fail; no input tried behaved differently from the fix (`m-0b00a3c47fba`)
- `app/modules/comparison/routes.py:20`: `             "errors_supported": False, ` → `             "errors_supported": True, ` made no test fail; behaves differently from the fix on inputs no test checks (`m-2f3fb61a1d72`)
- `app/modules/comparison/routes.py:21`: `             "corr_errors_supported": False, ` → `             "corr_errors_supported": True, ` made no test fail; behaves differently from the fix on inputs no test checks (`m-6bd03dcd61d6`)
- `app/modules/comparison/routes.py:22`: `             "uncorr_errors_supported": False, ` → `             "uncorr_errors_supported": True, ` made no test fail; behaves differently from the fix on inputs no test checks (`m-51d6b259ef9b`)
#### Fix lines run (report only)
- repro: 17 of 32 fix lines run
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
- guard: only the first 10 of 49 rule mutants were run
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T14:34:13+00:00, issue sha256 `e9818f01f4ad39c2d0c0e8a0279c1e87dc59d73384b1be35810167e71da3a132`

</details>
