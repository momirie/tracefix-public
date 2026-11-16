## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The bug was reproduced, with a test that fails before the fix and passes after it, and no regressions or breaking inputs were found; however, the tests did not catch enough mutants of the fix to guard it, and the behaviour diff was inconclusive. Next, add tests that pin down the default \`--min\` of 8 and explicitly passed min/max values, so that changes to the fix would be caught.

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 1 of 3 mutants; 80% is needed

**Issue:** Min/max length filtering is not working · **Repo:** testbed · **Base** `tf-base` (`ebeb249`) → **head** `tf-gold` (`7a17810`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.333, mutants 3, killed 1, survived 2 |
| `regressions` | `none_found` | compared 49, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 9 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 6, inputs tried 8, properties counted 10, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 3 of 4 killed; drop\_call: 1 of 3 killed; no place for compare, logic, negate\_if, constant, arithmetic, membership, loop, reraise

### Changes no test noticed (3 of 5; the rest in receipt.json)
- `dphon/cli.py:202`: `     logging.info(f"indexed {graph.number_of_docs} docs in {s... ` → `     logging.info(f"indexed {graph.number_of_matches} docs in... ` made no test fail; not compared with the fix (`m-4cbc0232726d`)
- `dphon/cli.py:233`: `     logging.info(f"seeded {graph.number_of_matches} matches ... ` → `     logging.info(f"seeded {graph.number_of_docs} matches in ... ` made no test fail; not compared with the fix (`m-d2ea3c329580`)
- `dphon/cli.py:202`: `     logging.info(f"indexed {graph.number_of_docs} docs in {s... ` → `     pass ` made no test fail; not compared with the fix (`m-3815c7980e75`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 64,871 input and 9,550 output tokens, cost $0.3639 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 6.17 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 7.7 s: 3 changed module(s) imported from the copies (6 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 24.03 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 129.22 s: the tests killed 1 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 6.16 s: none of the 49 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 5.71 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 14.46 s: nothing was compared: MatchGraph.number\_of\_matches: before the fix it was not a property defined in class MatchGraph
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `none_found`, 36.68 s: no counterexample found in 8 inputs against 10 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.06 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 35.67 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### Break My Fix targets
- `dphon.cli.process` (`dphon/cli.py`): 0 inputs (nothing generated)
- `dphon.reuse.MatchGraph.number_of_matches` (`dphon/reuse.py`): 1 input
- `dphon.reuse.MatchGraph.number_of_docs` (`dphon/reuse.py`): 1 input
- `dphon.reuse.MatchGraph.extend` (`dphon/reuse.py`): 2 inputs
- `dphon.reuse.MatchGraph.align` (`dphon/reuse.py`): 2 inputs
- `dphon.reuse.MatchGraph.group` (`dphon/reuse.py`): 2 inputs
#### More changes no test noticed
- `dphon/cli.py:233`: `     logging.info(f"seeded {graph.number_of_matches} matches ... ` → `     pass ` made no test fail; not compared with the fix (`m-b5a7c02ad9d7`)
- `dphon/reuse.py:172`: `         task = self.progress.add_task(\n            "aligning... ` → `         return None ` made no test fail; not compared with the fix (`m-f64ec3e4d254`)
#### Fix lines run (report only)
- repro: 6 of 9 fix lines run
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
- guard: 4 of the 7 mutants were not run: the tests could no longer reach 80% even if they killed them all
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T20:26:31+00:00, issue sha256 `3c98009cb5b50d6ffe901342abba9c4de6717db9104f62f85abd0c443aba1032`

</details>
