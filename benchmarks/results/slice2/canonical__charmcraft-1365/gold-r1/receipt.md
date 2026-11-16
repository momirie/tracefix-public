## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test that fails on the old code with the empty-requirements-line IndexError passes after the fix, no regressions were found, and the fixed lines were covered, but the guard stage reported the fix as not guarded and mutation testing did not meet the L2 threshold. Next, look at strengthening the tests so they would catch variations of the fix (for example, whitespace-only lines or comment lines i…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 4 mutants; 80% is needed

**Issue:** New dependency resolution fails with empty lines in requirements file · **Repo:** testbed · **Base** `tf-base` (`acf98be`) → **head** `tf-gold` (`1a6b6a1`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.5, mutants 4, killed 2, survived 2 |
| `regressions` | `none_found` | compared 1408, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 1 |
| `behaviour_diff` | `compared` | inputs compared 1, changes 0, groups 0 |
| `break_my_fix` | `skipped` | targets 0, inputs tried 0, properties counted 0, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed
- `charmcraft/utils/package.py:39`: `             if not line or line[0] not in valid_package_star... ` → `             if not line or line[-1] not in valid_package_sta... ` made no test fail; no input tried behaved differently from the fix (`m-3bb791e1b3f0`)
- `charmcraft/utils/package.py:39`: `             if not line or line[0] not in valid_package_star... ` → `             if not line or line[0] not in string.ascii_letters: ` made no test fail; no input tried behaved differently from the fix (`m-00c16ec23336`)
- `charmcraft/utils/package.py:39`: `             if not line or line[0] not in valid_package_star... ` → `             if not line or line[(-1)] not in valid_package_s... ` made no test fail; no input tried behaved differently from the fix (`m-5043d2d1cfab`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; break\_my\_fix: skipped (the fix changes no function Break My Fix can call (get\_pypi\_packages: it takes no parameters to vary)); Break My Fix could not attack get\_pypi\_packages: it takes no parameters to vary; 9 things the behaviour diff can't observe (run log)
- **Model use:** 3 calls, 10,475 input and 988 output tokens, cost $0.0390 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 46.22 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.12 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 36.25 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 488.52 s: the tests killed 2 of 4 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 177.61 s: none of the 1408 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.39 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `compared`, 11.96 s: 1 input(s) compared on 1 function(s): 0 changed with the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `skipped`, 0.01 s: the fix changes no function Break My Fix can call (get\_pypi\_packages: it takes no parameters to vary)
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
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
- break\_my\_fix: skipped (the fix changes no function Break My Fix can call (get\_pypi\_packages: it takes no parameters to vary))
- Break My Fix could not attack get\_pypi\_packages: it takes no parameters to vary
#### Notes
- not copied: base: tools/external (submodule)
- not copied: head: tools/external (submodule)
- reproduce: pyproject truncated to 3000 characters for the prompt
- guard: 1 of the kills were crashes on the mutated line rather than failed checks; they still count (open question 26)
- guard: 2 of the rule mutant kills were crashes on the mutated line
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.16: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T18:10:08+00:00, issue sha256 `aedb7cf276dcfd641ffb2cd95ca27a7c2cae3fb8e7ec7d943750f0ec5f6f9f44`

</details>
