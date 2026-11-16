## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug and found no regressions, but Break My Fix found that the fixed comparison.routes.\_aggregate\_period raises UnboundLocalError (on a variable starting 'corr\_errors\_su...') when a snapshot has both correctable and uncorrectable DOCSIS error counters set to None. That is exactly the unsupported-counter case this fix targets, so check that variable's initialization on t…

**Why this level:** Break My Fix finding 1: an input that breaks comparison.routes.\_aggregate\_period

**Issue:** Hide unsupported DOCSIS errors in Before/After Comparison · **Repo:** testbed · **Base** `tf-base` (`f478c6e`) → **head** `tf-v1` (`4ff3b00`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `_aggregate_period(snapshots=[{'timestamp': '2024-01-01T00:00...` → `raises UnboundLocalError: cannot access local variable 'corr...` (before the fix: `returns {'snapshots': 1, 'avg': {'ds_power': 1.0, 'ds_snr': ...`); breaks **never\_crashes\_on\_snapshot\_lists**: “using comparison API data with unsupported/null DOCSIS error counters” (issue); 3 more inputs break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.286, mutants 7, killed 2, survived 5 |
| `regressions` | `none_found` | compared 2246, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 30 |
| `behaviour_diff` | `partial` | inputs compared 1, changes 1, groups 1 |
| `break_my_fix` | `found` | targets 4, inputs tried 9, properties counted 12, findings 1 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `comparison.routes._aggregate_period` (`value`, 1 input): `returns {'snapshots': 0, 'avg': {'ds_power': None, 'ds_snr':...` → `returns {'snapshots': 0, 'avg': {'ds_power': None, 'ds_snr':...`; the Judge (advisory) calls it intended: The issue asks to hide \`cmp-chart-errors\` when the selected periods have unsupported error counters. Adding \`errors\_supported\`/\`\*\_supported: False\` flags to the empty-period summary is purely additive and leaves the existing keys and values unchanged, so it serves that goal.

### Changes no test noticed (3 of 8; the rest in receipt.json)
- `app/modules/comparison/routes.py:76`: `         "errors_supported": corr_errors_supported or uncorr_... ` → `         "errors_supported": corr_errors_supported and uncorr... ` made no test fail; no input tried behaved differently from the fix (`m-36540dfa695e`)
- `app/modules/comparison/routes.py:74`: `             "uncorr_errors": uncorr_total if uncorr_errors_s... ` → `             "uncorr_errors": uncorr_total if corr_errors_sup... ` made no test fail; no input tried behaved differently from the fix (`m-84f42d992ce2`)
- `app/modules/comparison/routes.py:99`: `     if period_a["total"].get("uncorr_errors") is not None an... ` → `     if period_a["total"].get("uncorr_errors") is not None or... ` made no test fail; no input tried behaved differently from the fix (`m-1b475133786e`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 9 calls, 86,748 input and 14,525 output tokens, cost $0.5575 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 104.72 s: base suite failed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.63 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_imports.py`
- `reproduce`: `reproduced`, 64.72 s: attempt 2: fails before the fix and passes after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `guard`: `not_guarded`, 2778.47 s: the tests killed 2 of 7 mutants; 80% is needed
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 514.28 s: none of the 2246 untouched tests that passed before the fix fails after it
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no --continue-on-collection-errors`
- `fix_line_coverage`: `ok`, 4.74 s: report only: which fix lines the tests run
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
- `behaviour_diff`: `partial`, 70.09 s: 1 input(s) compared on 1 function(s): 1 changed with the fix; not complete: AnalysisMixin.get\_correlation\_timeline: the comparison did not finish
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_repro.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no -s tests/test_tracefix_diff.py`
- `break_my_fix`: `found`, 125.9 s: 1 finding(s), each proven by a failing repro file
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_finding_1.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_comparison_module.py`
  - `python -P -m pytest -q -p no:cacheprovider --tb=long -rN --color=no tests/test_tracefix_attack.py`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
#### More changes no test noticed
- `app/modules/comparison/routes.py:101`: `     elif period_a.get("snapshots", 0) == 0 and period_b.get(... ` → `     elif period_a.get("snapshots", 0) == 0 or period_b.get("... ` made no test fail; no input tried behaved differently from the fix (`m-b782bf13b0e2`)
- `app/modules/comparison/routes.py:115`: `         if uncorr_d > 10: ` → `         if uncorr_d >= 10: ` made no test fail; no input tried behaved differently from the fix (`m-f52575040015`)
- `app/modules/comparison/routes.py:20`: `             "errors_supported": False, ` → `             "errors_supported": True, ` made no test fail; behaves differently from the fix on inputs no test checks (`m-2f3fb61a1d72`)
- `app/modules/comparison/routes.py:21`: `             "corr_errors_supported": False, ` → `             "corr_errors_supported": True, ` made no test fail; behaves differently from the fix on inputs no test checks (`m-6bd03dcd61d6`)
- `app/modules/comparison/routes.py:22`: `             "uncorr_errors_supported": False, ` → `             "uncorr_errors_supported": True, ` made no test fail; behaves differently from the fix on inputs no test checks (`m-51d6b259ef9b`)
#### Fix lines run (report only)
- repro: 15 of 30 fix lines run
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
- guard: only the first 10 of 47 rule mutants were run
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-16T15:43:13+00:00, issue sha256 `e9818f01f4ad39c2d0c0e8a0279c1e87dc59d73384b1be35810167e71da3a132`

</details>
