## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): At L1, the evidence shows the bug was reproduced: a test fails before the fix and passes after it, with no regressions or breaking inputs found, but the tests did not kill enough mutants to reach L2 and the guard stage reported the fix as not guarded. The most important thing to check next is the output changes in kraken\_biom.handle\_program\_options and kraken\_biom.main, which the Judge labelled s…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 7 of 9 mutants; 80% is needed

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
| `guard` | `not_guarded` | kill rate 0\.778, mutants 9, killed 7, survived 2 |
| `regressions` | `none_found` | compared 12, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 20 |
| `behaviour_diff` | `partial` | inputs compared 2, changes 2, groups 2 |
| `break_my_fix` | `none_found` | targets 2, inputs tried 16, properties counted 11, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_on_head` | attempts 2, report only True |

**Rule mutants by kind (report only):** body: 2 of 2 killed; compare: 0 of 1 killed; negate\_if: 0 of 1 killed; constant: 2 of 2 killed; arithmetic: 1 of 2 killed; membership: 1 of 1 killed; drop\_call: 1 of 1 killed; no place for logic, loop, reraise

### Behaviour changes
- `kraken_biom.handle_program_options` (`output`, 1 input): `raises SystemExit; printed nothing; wrote 'stderr usage: __m...` → `raises SystemExit; printed nothing; wrote 'stderr usage: __m...`; the Judge (advisory) calls it suspicious: The issue is only about taxonomic hierarchy parsing via indentation; removing the -k/--kraken\_reports\_fp option and changing nargs from '\*' to '+' alters the CLI usage text, and nothing in the issue asks for that.
- `kraken_biom.main` (`output`, 1 input): `raises SystemExit; printed nothing; wrote 'stderr usage: __m...` → `raises SystemExit; printed nothing; wrote 'stderr usage: __m...`; the Judge (advisory) calls it suspicious: Same unrelated CLI change seen through main: the -k option is dropped and the positional becomes required. The issue about lineage assignment does not ask for this, and the fix also tightens the max/min check to &gt;=.

### Changes no test noticed (3 of 5; the rest in receipt.json)
- `kraken_biom.py:107`: `     tax_lvl = {x[0]: x[1] for x in tax_lvl_depth if x[0] in ... ` → `     tax_lvl = {x[0]: x[1] for x in tax_lvl_depth} ` made no test fail; behaves differently from the fix on inputs no test checks (`m-1d0efd51f6d4`)
- `kraken_biom.py:385`: `     if ranks.index(args.max) >= ranks.index(args.min): ` → `     if ranks.index(args.max) > ranks.index(args.min): ` made no test fail; behaves differently from the fix on inputs no test checks (`m-1059cbc025d4`)
- `kraken_biom.py:385`: `     if ranks.index(args.max) >= ranks.index(args.min): ` → `     if ranks.index(args.max) > ranks.index(args.min): ` made no test fail; behaves differently from the fix on inputs no test checks (`m-1059cbc025d4`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack handle\_program\_options: it takes no parameters to vary; Break My Fix could not attack main: it takes no parameters to vary; the behaviour diff could not compare parse\_tax\_lvl: new with the fix: nothing to compare; 9 things the behaviour diff can't observe (run log)
- **Model use:** 11 calls, 102,064 input and 25,760 output tokens, cost $0.7860 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.93 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.67 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 36.1 s: attempt 2: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `guard`: `not_guarded`, 127.32 s: the tests killed 7 of 9 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 2.99 s: none of the 12 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.85 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `behaviour_diff`: `partial`, 31.62 s: 2 input(s) compared on 2 function(s): 2 changed with the fix; not complete: kraken\_biom.py: module-level code that computes a value changed (line 36); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 46.59 s: no counterexample found in 16 inputs against 11 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_on_head`, 39.63 s: attempt 2: fails the same way before and after the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
#### Break My Fix targets
- `kraken_biom.parse_tax_lvl` (`kraken_biom.py`): 10 inputs
- `kraken_biom.parse_kraken_report` (`kraken_biom.py`): 6 inputs
#### More changes no test noticed
- `kraken_biom.py:385`: `     if ranks.index(args.max) >= ranks.index(args.min): ` → `     if not (ranks.index(args.max) >= ranks.index(args.min)): ` made no test fail; behaves differently from the fix on inputs no test checks (`m-e09f0c9114ab`)
- `kraken_biom.py:336`: `     parser.add_argument('--max', default="O", choices=ranks[... ` → `     parser.add_argument('--max', default="O", choices=ranks[... ` made no test fail; behaves differently from the fix on inputs no test checks (`m-ebf8c96ff10c`)
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
- guard: only the first 10 of 25 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: style example test/test\_biom\_create.py truncated to 6000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T19:35:01+00:00, issue sha256 `049a791deef8b876a4e8afff00275a5fe6d578c6b4c5b7883fac2a687491625a`

</details>
