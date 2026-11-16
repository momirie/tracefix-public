## Fix Receipt: L2 (L1, and the tests notice the fix being undone)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The evidence shows the bug was reproduced and guarded: a test fails before the fix and passes after it, it fails again when the fix is reverted or broken, and no regressions or breaking inputs were found. Most important next: review the unexplained inputs where ExpressionTokenizer.tokenize changed from raising ExpressionTokenizerError to returning a list (the Judge labeled this intended), and not…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; the tests guard the fix: they fail when it is reverted or broken; not L3: ExpressionTokenizer.equal: the comparison did not finish; not L3: 1 input(s) changed from 'raises ExpressionTokenizerError' to 'returns list' and nothing explains it (not the reproduction test, the issue or a docstring example)

**Issue:** Tabs in constant expression should be treated like spaces · **Repo:** testbed · **Base** `tf-base` (`95a4928`) → **head** `tf-gold` (`ee2d29a`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 1\.0, mutants 3, killed 3, survived 0 |
| `regressions` | `none_found` | compared 236, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 4 |
| `behaviour_diff` | `partial` | inputs compared 388, changes 1, groups 1 |
| `break_my_fix` | `none_found` | targets 3, inputs tried 443, properties counted 11, findings 0 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `cstruct.expression.ExpressionTokenizer.tokenize` (`no_raise`, 1 input): `raises ExpressionTokenizerError; left its arguments as built...` → `returns []; left its arguments as builtins.list([builtins.tu...`; the Judge (advisory) calls it intended: The issue says tabs are legal whitespace and should be treated like spaces, so a lone tab now tokenizes to \[\] just as a lone space would instead of raising.

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 49,503 input and 7,481 output tokens, cost $0.3230 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.08 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.4 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 21.46 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `guarded`, 86.0 s: the reproduction test fails with the fix reverted, and the tests killed 3 of 3 mutants
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `regressions`: `none_found`, 2.12 s: none of the 236 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 1.66 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `partial`, 14.52 s: 388 input(s) compared on 2 function(s): 1 changed with the fix; not complete: ExpressionTokenizer.equal: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `none_found`, 84.56 s: no counterexample found in 443 inputs against 11 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `cstruct.expression.ExpressionTokenizer.equal` (`dissect/cstruct/expression.py`): 32 inputs
- `cstruct.expression.ExpressionTokenizer.match` (`dissect/cstruct/expression.py`): 7 inputs
- `cstruct.expression.ExpressionTokenizer.tokenize` (`dissect/cstruct/expression.py`): 404 inputs
#### Fix lines run (report only)
- repro: 3 of 4 fix lines run
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
- reproduce: only the first 8 of 9 functions were shown
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T18:59:03+00:00, issue sha256 `d9a52364a56dc16341daf4613925cf1bff25961b5ea3326ca685828cd92b262e`

</details>
