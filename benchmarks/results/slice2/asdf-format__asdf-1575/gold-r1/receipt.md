## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproducing the issue (a closed AsdfFile still holding its tree and keeping objects from being garbage collected) failed before the fix and passed after it, with no regressions found and the fix lines covered. The tests did not kill enough mutants to reach L2, and the behaviour-diff and break-my-fix stages were inconclusive, so the next step is to strengthen the tests so they distinguish t…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 3 mutants; 80% is needed

**Issue:** closed \`AsdfFile\` instances hold private reference to tree · **Repo:** testbed · **Base** `tf-base` (`24d9855`) → **head** `tf-gold` (`5a2671f`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.667, mutants 3, killed 2, survived 1 |
| `regressions` | `none_found` | compared 1220, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 1 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 1, inputs tried 0, properties counted 1, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `asdf/asdf.py:459`: `             self._tree = AsdfObject() ` → `             self._tree = None ` made no test fail; not compared with the fix (`m-7511b862b036`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 4 calls, 21,355 input and 1,255 output tokens, cost $0.0831 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 63.06 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.7 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 26.6 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no asdf/_json...`
- `guard`: `not_guarded`, 279.56 s: the tests killed 2 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no asdf/_json...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 243.69 s: none of the 1220 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 5.31 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no asdf/_json...`
- `behaviour_diff`: `inconclusive`, 2.88 s: nothing was compared: AsdfFile.close: it could not be loaded after the fix: asdf/asdf.py could not be imported as a module here (tried asdf.asdf, asdf)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `inconclusive`, 9.48 s: no target could be attacked: asdf/asdf.py could not be imported as a module here (tried asdf.asdf, asdf)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `asdf.asdf.AsdfFile.close` (`asdf/asdf.py`): not attacked (asdf/asdf.py could not be imported as a module here (tried asdf.asdf, asdf))
#### Fix lines run (report only)
- repro: 1 of 1 fix lines run
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
- reproduce: only the first 8 of 20 functions were shown
- reproduce: pyproject truncated to 3000 characters for the prompt
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T19:25:55+00:00, issue sha256 `55393f402bdec65b59bff4d105f48b93b78d64bf8a50100d8f54aac143acd3a9`

</details>
