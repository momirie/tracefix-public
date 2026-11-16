## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug, but the fixed code broke 14 previously passing tests across the parsing, BIOM-creation and sample-processing suites, and parse\_tax\_lvl raises NameError: name 're' is not defined on a plain Chlorophyta entry. Check first whether the fix is missing an \`import re\`, which would likely explain both Break My Fix findings and the regressions, then re-run the suite.

**Why this level:** Break My Fix finding 1: an input that breaks kraken\_biom.parse\_kraken\_report; Break My Fix finding 2: an input that breaks kraken\_biom.parse\_tax\_lvl; regression: test/test\_biom\_create.py::kraken\_biom\_Test.test\_sample\_ids passed before the fix and fails after it; regression: test/test\_biom\_create.py::kraken\_biom\_Test.test\_observation\_ids passed before the fix and fails after it; regression: test/test\_biom\_create.py::kraken\_biom\_Test.test\_sample\_counts passed before the fix and fails after it; regression: test/test\_parsing.py::kraken\_biom\_Test.test\_parse\_kraken\_report\_O\_S passed before the fix and fails after it; and 8 more in receipt.json

**Issue:** Taxonomic hierarchy incorrect for certain cases · **Repo:** testbed · **Base** `tf-base` (`e8e9d45`) → **head** `tf-v0` (`f281fbb`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples (5 of 14; the rest in receipt.json)
1. `parse_kraken_report(kdata=[{'pct_reads': '0.00', 'clade_read...` → `raises NameError: name 're' is not defined` (before the fix: `returns (OrderedDict([('5693', 1)]), OrderedDict([('5693', [...`); breaks **taxa\_ids\_from\_report**: “a list of NCBI IDs and a formatted string representing their taxonomic hierarchies” (docstring); 2 more inputs break it the same way; test: `findings/finding_1.py`
2. `parse_tax_lvl(entry={'pct_reads': '0.00', 'clade_reads': '1'...` → `raises NameError: name 're' is not defined`; breaks **own\_rank\_maps\_to\_own\_name**: “Parse a single kraken-report entry and return a dictionary of taxa for its named ranks.” (docstring); 2 more inputs break it the same way; test: `findings/finding_2.py`
3. Regression: `test/test_biom_create.py::kraken_biom_Test.test_sample_ids` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 're' is not defined)
4. Regression: `test/test_biom_create.py::kraken_biom_Test.test_observation_ids` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 're' is not defined)
5. Regression: `test/test_biom_create.py::kraken_biom_Test.test_sample_counts` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 're' is not defined)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 2 |
| `guard` | `inconclusive` | kill rate 0\.714, mutants 7, killed 5, survived 2 |
| `regressions` | `found` | compared 12, regressions 12, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 18 |
| `behaviour_diff` | `partial` | inputs compared 2, changes 2, groups 2 |
| `break_my_fix` | `found` | targets 2, inputs tried 7, properties counted 11, findings 2 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `kraken_biom.handle_program_options` (`output`, 1 input): `raises SystemExit; printed nothing; wrote 'stderr usage: __m...` → `raises SystemExit; printed nothing; wrote 'stderr usage: __m...`; the Judge (advisory) calls it suspicious: The issue is only about taxonomy hierarchy parsing. Removing the -k/--kraken\_reports\_fp option and changing nargs from '\*' to '+' alters the CLI usage, and nothing in the issue asks for that (it looks like a reverted feature).
- `kraken_biom.main` (`output`, 1 input): `raises SystemExit; printed nothing; wrote 'stderr usage: __m...` → `raises SystemExit; printed nothing; wrote 'stderr usage: __m...`; the Judge (advisory) calls it suspicious: The issue concerns lineage assignment only. main's CLI changed (the -k option was dropped and kraken\_reports is now required), which no text asks for; the fix also tightened the max/min check to '&gt;='.

### Changes no test noticed (3 of 4; the rest in receipt.json)
- `kraken_biom.py:107`: `     tax_lvl = {x[0]: x[1] for x in tax_lvl_depth if x[0] in ... ` → `     tax_lvl = {x[0]: x[1] for x in tax_lvl_depth} ` made no test fail; behaves differently from the fix on inputs no test checks (`m-1d0efd51f6d4`)
- `kraken_biom.py:105`: `     tax_lvl_depth.append((entry['rank'], name)) ` → `     tax_lvl_depth.append((entry['rank'], entry['sci_name'])) ` made no test fail; behaves differently from the fix on inputs no test checks (`m-7a42eafacc56`)
- `kraken_biom.py:274`: `     descr = """\\n    Create BIOM-format tables (http://biom-... ` → `     return None ` made no test fail; behaves differently from the fix on inputs no test checks (`m-e02840de7ec6`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack handle\_program\_options: it takes no parameters to vary; Break My Fix could not attack main: it takes no parameters to vary; the behaviour diff could not compare parse\_tax\_lvl: new with the fix: nothing to compare; 9 things the behaviour diff can't observe (run log)
- **Model use:** 9 calls, 82,907 input and 17,078 output tokens, cost $0.5889 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 3.07 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.71 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 56.31 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `guard`: `inconclusive`, 119.06 s: the tests killed 5 of 7 mutants; 80% is needed, but the existing suite could not run cleanly on the fixed code, so the rate is incomplete
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 22.55 s: 12 confirmed: test/test\_biom\_create.py::kraken\_biom\_Test.test\_sample\_ids, test/test\_biom\_create.py::kraken\_biom\_Test.test\_observation\_ids, test/test\_biom\_create.py::kraken\_biom\_Test.test\_sample\_counts, test/test\_parsing.py::kraken\_biom\_Test.test\_parse\_kraken\_report\_O\_S, test/test\_parsing.py::kraken\_biom\_Test.test\_parse\_kraken\_report\_F\_S and 7 more
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.9 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `behaviour_diff`: `partial`, 27.29 s: 2 input(s) compared on 2 function(s): 2 changed with the fix; not complete: kraken\_biom.py: module-level code that computes a value changed (line 36); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 151.86 s: 2 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### More counterexamples
- Regression: `test/test_parsing.py::kraken_biom_Test.test_parse_kraken_report_O_S` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 're' is not defined)
- Regression: `test/test_parsing.py::kraken_biom_Test.test_parse_kraken_report_F_S` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 're' is not defined)
- Regression: `test/test_parsing.py::kraken_biom_Test.test_parse_kraken_report_G_S` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 're' is not defined)
- Regression: `test/test_parsing.py::kraken_biom_Test.test_parse_kraken_report_S` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 're' is not defined)
- Regression: `test/test_parsing.py::kraken_biom_Test.test_parse_kraken_report_C_G` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 're' is not defined)
- Regression: `test/test_parsing.py::kraken_biom_Test.test_parse_kraken_report_taxonomy` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 're' is not defined)
- Regression: `test/test_process_samples.py::kraken_biom_Test.test_sample_ids` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 're' is not defined)
- Regression: `test/test_process_samples.py::kraken_biom_Test.test_sample_counts` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 're' is not defined)
- Regression: `test/test_process_samples.py::kraken_biom_Test.test_taxa` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: NameError: name 're' is not defined)
#### Break My Fix targets
- `kraken_biom.parse_tax_lvl` (`kraken_biom.py`): 3 inputs
- `kraken_biom.parse_kraken_report` (`kraken_biom.py`): 4 inputs
#### More changes no test noticed
- `kraken_biom.py:376`: `     args = handle_program_options()\n\n    if args.fmt == 'hdf... ` → `     return None ` made no test fail; behaves differently from the fix on inputs no test checks (`m-f883b1d22f6b`)
#### Fix lines run (report only)
- repro: 13 of 18 fix lines run
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
- guard: the existing suite did not run cleanly on the fixed code
- guard: only the first 10 of 24 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T20:01:14+00:00, issue sha256 `049a791deef8b876a4e8afff00275a5fe6d578c6b4c5b7883fac2a687491625a`

</details>
