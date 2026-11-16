## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): At L1, the evidence shows the bug was reproduced: a test fails before the fix and passes after it, with no regressions or breaking inputs found, but the tests did not kill enough mutants to reach L2 and the guard stage reported the fix as not guarded. The most important thing to check next is the output changes in kraken\_biom.handle\_program\_options and kraken\_biom.main, which the Judge labelled s…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 4 of 6 mutants; 80% is needed

**Issue:** Taxonomic hierarchy incorrect for certain cases · **Repo:** testbed · **Base** `tf-base` (`e8e9d45`) → **head** `tf-gold` (`425f423`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `not_guarded` | kill rate 0\.667, mutants 6, killed 4, survived 2 |
| `regressions` | `none_found` | compared 12, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 20 |
| `behaviour_diff` | `partial` | inputs compared 2, changes 2, groups 2 |
| `break_my_fix` | `none_found` | targets 2, inputs tried 6, properties counted 11, findings 0 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `kraken_biom.handle_program_options` (`output`, 1 input): `raises SystemExit; printed nothing; wrote 'stderr usage: __m...` → `raises SystemExit; printed nothing; wrote 'stderr usage: __m...`; the Judge (advisory) calls it suspicious: The issue concerns only taxonomic hierarchy parsing. Removing the -k/--kraken\_reports\_fp option and making kraken\_reports required (nargs '+') changes the CLI usage text, and nothing in the issue asks for that.
- `kraken_biom.main` (`output`, 1 input): `raises SystemExit; printed nothing; wrote 'stderr usage: __m...` → `raises SystemExit; printed nothing; wrote 'stderr usage: __m...`; the Judge (advisory) calls it suspicious: main's changed usage output comes from the unrequested removal of -k and the switch to nargs '+'. The fix also changed max&gt;=min validation; the issue is only about lineage assignment from indentation.

### Changes no test noticed (3 of 4; the rest in receipt.json)
- `kraken_biom.py:107`: `     tax_lvl = {x[0]: x[1] for x in tax_lvl_depth if x[0] in ... ` → `     tax_lvl = {x[0]: x[1] for x in tax_lvl_depth} ` made no test fail; behaves differently from the fix on inputs no test checks (`m-1d0efd51f6d4`)
- `kraken_biom.py:385`: `     if ranks.index(args.max) >= ranks.index(args.min): ` → `     if ranks.index(args.max) > ranks.index(args.min): ` made no test fail; behaves differently from the fix on inputs no test checks (`m-1059cbc025d4`)
- `kraken_biom.py:274`: `     descr = """\\n    Create BIOM-format tables (http://biom-... ` → `     return None ` made no test fail; behaves differently from the fix on inputs no test checks (`m-e02840de7ec6`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack handle\_program\_options: it takes no parameters to vary; Break My Fix could not attack main: it takes no parameters to vary; the behaviour diff could not compare parse\_tax\_lvl: new with the fix: nothing to compare; 9 things the behaviour diff can't observe (run log)
- **Model use:** 9 calls, 84,432 input and 23,239 output tokens, cost $0.7236 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 3.56 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.71 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 48.38 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `guard`: `not_guarded`, 106.28 s: the tests killed 4 of 6 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 3.01 s: none of the 12 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.98 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `behaviour_diff`: `partial`, 27.88 s: 2 input(s) compared on 2 function(s): 2 changed with the fix; not complete: kraken\_biom.py: module-level code that computes a value changed (line 36); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 182.9 s: no counterexample found in 6 inputs against 11 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `kraken_biom.parse_tax_lvl` (`kraken_biom.py`): 0 inputs
- `kraken_biom.parse_kraken_report` (`kraken_biom.py`): 6 inputs
#### More changes no test noticed
- `kraken_biom.py:376`: `     args = handle_program_options()\n\n    if args.fmt == 'hdf... ` → `     return None ` made no test fail; behaves differently from the fix on inputs no test checks (`m-f883b1d22f6b`)
#### Fix lines run (report only)
- repro: 15 of 20 fix lines run
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
- Break My Fix could not attack handle\_program\_options: it takes no parameters to vary
- Break My Fix could not attack main: it takes no parameters to vary
- the behaviour diff could not compare parse\_tax\_lvl: new with the fix: nothing to compare
#### Notes
- reproduce: style example test/test\_biom\_create.py truncated to 6000 characters for the prompt
- guard: only the first 10 of 24 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T19:54:48+00:00, issue sha256 `049a791deef8b876a4e8afff00275a5fe6d578c6b4c5b7883fac2a687491625a`

</details>
