## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier found counterexamples: the fixed parse\_tax\_lvl raises NameError: name 're' is not defined (the fix appears to use the re module without importing it), parse\_kraken\_report also breaks on a crafted report, and 14 previously passing tests in test\_parsing.py, test\_biom\_create.py and test\_process\_samples.py now fail. Look first at the missing 're' import in kraken\_biom and rerun those tes…

**Why this level:** Break My Fix finding 1: an input that breaks kraken\_biom.parse\_tax\_lvl; Break My Fix finding 2: an input that breaks kraken\_biom.parse\_kraken\_report; regression: test/test\_biom\_create.py::kraken\_biom\_Test.test\_sample\_ids passed before the fix and fails after it; regression: test/test\_biom\_create.py::kraken\_biom\_Test.test\_observation\_ids passed before the fix and fails after it; regression: test/test\_biom\_create.py::kraken\_biom\_Test.test\_sample\_counts passed before the fix and fails after it; regression: test/test\_parsing.py::kraken\_biom\_Test.test\_parse\_kraken\_report\_O\_S passed before the fix and fails after it; and 8 more in receipt.json

**Issue:** Taxonomic hierarchy incorrect for certain cases · **Repo:** testbed · **Base** `tf-base` (`e8e9d45`) → **head** `tf-v0` (`f281fbb`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples (5 of 14; the rest in receipt.json)
1. `parse_tax_lvl(entry={'pct_reads': '0.00', 'clade_reads': '1'...` → `raises NameError: name 're' is not defined`; breaks **keys\_are\_named\_ranks**: “return a dictionary of taxa for its named ranks” (docstring); 3 more inputs break it the same way; test: `findings/finding_1.py`
2. `parse_kraken_report(kdata=[{'pct_reads': '0.00', 'clade_read...` → `raises NameError: name 're' is not defined` (before the fix: `returns (OrderedDict([('5693', 1)]), OrderedDict([('5693', [...`); breaks **cruzi\_not\_under\_chlorophyta**: “that group doesn't actually include ID 5693, so we shouldn't have a phylum or class assigned” (issue); 2 more inputs break it the same way; test: `findings/finding_2.py`
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
| `break_my_fix` | `found` | targets 2, inputs tried 17, properties counted 12, findings 2 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_differently` | attempts 2, report only True |

**Rule mutants by kind (report only):** body: 2 of 2 killed; compare: 0 of 1 killed; negate\_if: 0 of 1 killed; constant: 2 of 2 killed; arithmetic: 1 of 2 killed; membership: 1 of 1 killed; drop\_call: 1 of 1 killed; no place for logic, loop, reraise

### Behaviour changes
- `kraken_biom.handle_program_options` (`output`, 1 input): `raises SystemExit; printed nothing; wrote 'stderr usage: __m...` → `raises SystemExit; printed nothing; wrote 'stderr usage: __m...`; the Judge (advisory) calls it suspicious: The issue is only about taxonomic hierarchy parsing; removing the -k/--kraken\_reports\_fp option and changing nargs to '+' (visible in the changed usage text) is CLI behaviour nothing in the issue asks for.
- `kraken_biom.main` (`output`, 1 input): `raises SystemExit; printed nothing; wrote 'stderr usage: __m...` → `raises SystemExit; printed nothing; wrote 'stderr usage: __m...`; the Judge (advisory) calls it suspicious: main's usage output changes because the -k option was dropped and positional args became required, and the max/min check was tightened to &gt;=. The issue on lineage assignment by indentation asks for none of this.

### Changes no test noticed (3 of 5; the rest in receipt.json)
- `kraken_biom.py:99`: `     depth = len(depth_and_name.group(1))//2 ` → `     depth = len(depth_and_name.group(1))//4 ` made no test fail; behaves differently from the fix on inputs no test checks (`m-5eed730ef502`)
- `kraken_biom.py:133`: `             r = ranks.index(erank) ` → `             r = ranks.index(erank) + 1 ` made no test fail; behaves differently from the fix on inputs no test checks (`m-b04e6355edd2`)
- `kraken_biom.py:385`: `     if ranks.index(args.max) >= ranks.index(args.min): ` → `     if ranks.index(args.max) > ranks.index(args.min): ` made no test fail; behaves differently from the fix on inputs no test checks (`m-1059cbc025d4`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack handle\_program\_options: it takes no parameters to vary; Break My Fix could not attack main: it takes no parameters to vary; the behaviour diff could not compare parse\_tax\_lvl: new with the fix: nothing to compare; 9 things the behaviour diff can't observe (run log)
- **Model use:** 11 calls, 100,546 input and 20,986 output tokens, cost $0.6802 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.93 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.77 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 36.11 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `guard`: `inconclusive`, 124.41 s: the tests killed 5 of 7 mutants; 80% is needed, but the existing suite could not run cleanly on the fixed code, so the rate is incomplete
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 22.37 s: 12 confirmed: test/test\_biom\_create.py::kraken\_biom\_Test.test\_sample\_ids, test/test\_biom\_create.py::kraken\_biom\_Test.test\_observation\_ids, test/test\_biom\_create.py::kraken\_biom\_Test.test\_sample\_counts, test/test\_parsing.py::kraken\_biom\_Test.test\_parse\_kraken\_report\_O\_S, test/test\_parsing.py::kraken\_biom\_Test.test\_parse\_kraken\_report\_F\_S and 7 more
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.84 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `behaviour_diff`: `partial`, 30.42 s: 2 input(s) compared on 2 function(s): 2 changed with the fix; not complete: kraken\_biom.py: module-level code that computes a value changed (line 36); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 65.52 s: 2 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_differently`, 21.35 s: attempt 2: fails after the fix too, but differently
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
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
- `kraken_biom.parse_tax_lvl` (`kraken_biom.py`): 13 inputs
- `kraken_biom.parse_kraken_report` (`kraken_biom.py`): 4 inputs
#### More changes no test noticed
- `kraken_biom.py:385`: `     if ranks.index(args.max) >= ranks.index(args.min): ` → `     if not (ranks.index(args.max) >= ranks.index(args.min)): ` made no test fail; behaves differently from the fix on inputs no test checks (`m-e09f0c9114ab`)
- `kraken_biom.py:336`: `     parser.add_argument('--max', default="O", choices=ranks[... ` → `     parser.add_argument('--max', default="O", choices=ranks[... ` made no test fail; behaves differently from the fix on inputs no test checks (`m-ebf8c96ff10c`)
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
- guard: 1 of the 8 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: the existing suite did not run cleanly on the fixed code
- guard: only the first 10 of 25 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: style example test/test\_biom\_create.py truncated to 6000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T19:39:58+00:00, issue sha256 `049a791deef8b876a4e8afff00275a5fe6d578c6b4c5b7883fac2a687491625a`

</details>
