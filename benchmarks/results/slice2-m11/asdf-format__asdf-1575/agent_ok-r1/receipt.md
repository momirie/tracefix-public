## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the issue and the fix guards against it, but asdf/\_tests/test\_info.py::test\_info\_module passed before the fix and fails after it, which is a regression. Look first at why clearing the tree on close breaks the info module test, for example whether the info code reads the tree after the file is closed.

**Why this level:** regression: asdf/\_tests/test\_info.py::test\_info\_module passed before the fix and fails after it

**Issue:** closed \`AsdfFile\` instances hold private reference to tree · **Repo:** testbed · **Base** `tf-base` (`24d9855`) → **head** `tf-agent_ok` (`969d6a2`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. Regression: `asdf/_tests/test_info.py::test_info_module` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: OSError: Cannot access data from closed ASDF file)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 4 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 0\.833, mutants 6, killed 5, survived 1 |
| `regressions` | `found` | compared 1220, regressions 1, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 130 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 1, inputs tried 0, properties counted 1, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 2 killed; compare: 0 of 2 killed; logic: 0 of 1 killed; constant: 1 of 2 killed; membership: 0 of 1 killed; drop\_call: 0 of 1 killed; reraise: 0 of 1 killed; no place for negate\_if, arithmetic, loop

### Changes no test noticed (3 of 9; the rest in receipt.json)
- `asdf/asdf.py:460`: `         self._tree = None ` → `         self._tree = {} ` made no test fail; not compared with the fix (`m-54c0286c83da`)
- `comprehensive_test_v2.py:118`: `if __name__ == "__main__":` → `if __name__ != "__main__":` made no test fail; not compared with the fix (`m-9ca1decf586e`)
- `reproduce_issue.py:42`: `     if not success: ` → `     if success: ` made no test fail; not compared with the fix (`m-cebd224effb7`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack test\_basic\_gc\_fix: it takes no parameters to vary; Break My Fix could not attack test\_close\_without\_fd: it takes no parameters to vary; Break My Fix could not attack test\_double\_close: it takes no parameters to vary; Break My Fix could not attack test\_manual\_close\_vs\_context\_manager: it takes no parameters to vary; and 9 more in receipt.json
- **Model use:** 5 calls, 37,553 input and 2,154 output tokens, cost $0.1339 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 68.56 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 5.64 s: 4 changed module(s) imported from the copies (5 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 22.7 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no asdf/_json...`
- `guard`: `guarded`, 2017.97 s: the reproduction test fails with the fix reverted, and the tests killed 5 of 6 mutants
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no asdf/_json...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
  - 1 more command(s) in receipt.json
- `regressions`: `found`, 294.26 s: 1 confirmed: asdf/\_tests/test\_info.py::test\_info\_module
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 12.73 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no asdf/_json...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
- `behaviour_diff`: `inconclusive`, 3.33 s: nothing was compared: test\_closed\_asdf\_file\_gc\_issue: not compared (past the cap of 6 functions)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `inconclusive`, 2.97 s: no target could be attacked: asdf/asdf.py could not be imported as a module here (tried asdf.asdf, asdf)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.04 s: no candidate was confirmed (2 reported)
- `blind`: `reproduced`, 24.21 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no asdf/_json...`
#### Break My Fix targets
- `asdf.asdf.AsdfFile.close` (`asdf/asdf.py`): not attacked (asdf/asdf.py could not be imported as a module here (tried asdf.asdf, asdf))
#### More changes no test noticed
- `comprehensive_test_v2.py:21`: `         assert array_ref() is not None ` → `         assert array_ref() is None ` made no test fail; not compared with the fix (`m-afb4f249f678`)
- `comprehensive_test_v2.py:14`: `     print("Testing basic garbage collection fix...") ` → `     pass ` made no test fail; not compared with the fix (`m-4388eaa4c5b6`)
- `comprehensive_test_v2.py:43`: `         assert "Cannot access data from closed ASDF file" in... ` → `         raise\n        assert "Cannot access data from closed... ` made no test fail; not compared with the fix (`m-f441e29180a4`)
- `comprehensive_test_v2.py:14`: `     print("Testing basic garbage collection fix...")\n    \n  ... ` → `     return None ` made no test fail; not compared with the fix (`m-2beb6b7111b0`)
- `reproduce_issue.py:40`: `if __name__ == "__main__":` → `if __name__ != "__main__":` made no test fail; not compared with the fix (`m-868c503f79d3`)
- `comprehensive_test_v2.py:17`: `     asdf.AsdfFile({'arr': np.arange(100)}).write_to(fn) ` → `     asdf.AsdfFile({'arr': np.arange(101)}).write_to(fn) ` made no test fail; not compared with the fix (`m-6a49427336df`)
#### Fix lines run (report only)
- repro: 4 of 130 fix lines run
- pr\_test: 4 of 130 fix lines run
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
- Break My Fix could not attack test\_basic\_gc\_fix: it takes no parameters to vary
- Break My Fix could not attack test\_close\_without\_fd: it takes no parameters to vary
- Break My Fix could not attack test\_double\_close: it takes no parameters to vary
- Break My Fix could not attack test\_manual\_close\_vs\_context\_manager: it takes no parameters to vary
- Break My Fix could not attack test\_tree\_access\_after\_close: it takes no parameters to vary
- Break My Fix could not attack test\_closed\_asdf\_file\_gc\_issue: it takes no parameters to vary
- the behaviour diff could not compare test\_closed\_asdf\_file\_gc\_issue: past the cap of 6 functions
- the behaviour diff could not compare test\_basic\_gc\_fix: new with the fix: nothing to compare
- the behaviour diff could not compare test\_tree\_access\_after\_close: new with the fix: nothing to compare
- the behaviour diff could not compare test\_double\_close: new with the fix: nothing to compare
- the behaviour diff could not compare test\_close\_without\_fd: new with the fix: nothing to compare
- the behaviour diff could not compare test\_manual\_close\_vs\_context\_manager: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 26 functions were shown
- reproduce: pyproject truncated to 3000 characters for the prompt
- guard: debug\_test.py has no tests, so it is not counted as a PR test
- guard: only the first 10 of 120 rule mutants were run
- behaviour\_diff: only the first 6 of 7 functions are attacked
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: only the first 8 of 20 functions were shown
- blind: pyproject truncated to 3000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-07T13:45:54+00:00, issue sha256 `55393f402bdec65b59bff4d105f48b93b78d64bf8a50100d8f54aac143acd3a9`

</details>
