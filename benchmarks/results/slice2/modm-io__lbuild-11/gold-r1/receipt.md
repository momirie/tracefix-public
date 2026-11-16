## Fix Receipt: L2 (L1, and the tests notice the fix being undone)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): At L2, a test reproduced the missing error for non-existent module names, failing before the fix and passing after it, and the tests also fail when the fix is reverted or broken, with no regressions or breaking inputs found. The behaviour comparison did not finish for Parser.find\_any, BaseNode.\_resolve\_dependencies and BaseNode.dependencies, and the changed module-level value in lbuild/main.py wa…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; the tests guard the fix: they fail when it is reverted or broken; not L3: lbuild/main.py: module-level code that computes a value changed (line 27); what uses it is not compared; not L3: Parser.find\_any: the comparison did not finish; not L3: BaseNode.\_resolve\_dependencies: the comparison did not finish; not L3: BaseNode.dependencies: the comparison did not finish

**Issue:** No warning/error on non-existing modules · **Repo:** testbed · **Base** `tf-base` (`b279753`) → **head** `tf-gold` (`253e72a`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 0\.8, mutants 5, killed 4, survived 1 |
| `regressions` | `none_found` | compared 78, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 6 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 3, inputs tried 293, properties counted 4, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `lbuild/parser.py:224`: `             if result is None: ` → `             if not result: ` made no test fail; not compared with the fix (`m-80c4ac381226`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 37,326 input and 4,441 output tokens, cost $0.2160 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.3 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.55 s: 3 changed module(s) imported from the copies (6 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 13.58 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `guard`: `guarded`, 33.88 s: the reproduction test fails with the fix reverted, and the tests killed 4 of 5 mutants
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 2.16 s: none of the 78 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 1.76 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test/test_...`
- `behaviour_diff`: `inconclusive`, 1.9 s: nothing was compared: lbuild/main.py: module-level code that computes a value changed (line 27); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 47.03 s: no counterexample found in 293 inputs against 4 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.03 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `lbuild.parser.Parser.find_any` (`lbuild/parser.py`): 293 inputs
- `lbuild.node.BaseNode._resolve_dependencies` (`lbuild/node.py`): not attacked (no property to check it against)
- `lbuild.node.BaseNode.dependencies` (`lbuild/node.py`): not attacked (no property to check it against); a public caller of the changed BaseNode.\_resolve\_dependencies
#### Fix lines run (report only)
- repro: 4 of 6 fix lines run
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
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T18:50:24+00:00, issue sha256 `af40b9e724e04233c0fa87d489d19ba3aa3839edfdadcdac56b8005608788cbc`

</details>
