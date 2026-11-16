## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The evidence shows the bug was reproduced, with a test that fails before the fix and passes after it, but the tests did not kill enough mutants to reach L2, and the fix was not guarded. The most important thing to look at next is the change to the arguments of responses.RequestsMock.reset, which the Judge labelled suspicious; check that it is intended and does not break existing callers.

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 2 of 5 mutants; 80% is needed

**Issue:** ability to pass a regex to add\_passthru · **Repo:** testbed · **Base** `tf-base` (`b741b6e`) → **head** `tf-agent_ok` (`b384a42`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.4, mutants 5, killed 2, survived 3 |
| `regressions` | `none_found` | compared 54, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 11 |
| `behaviour_diff` | `partial` | inputs compared 1, changes 1, groups 1 |
| `break_my_fix` | `none_found` | targets 4, inputs tried 371, properties counted 7, findings 0 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `responses.RequestsMock.reset` (`arguments`, 1 input): `returns None; left its arguments as builtins.list([builtins....` → `returns None; left its arguments as builtins.list([builtins....`; the Judge (advisory) calls it suspicious: The issue only asks add\_passthru to accept a regex, and nothing written asks reset() to clear passthru patterns. reset() never cleared passthru\_prefixes, so now clearing registered regex passthrus but not string prefixes is an unrequested, inconsistent behaviour change.

### Changes no test noticed
- `responses.py:475`: `         self.passthru_patterns = () ` → `         pass ` made no test fail; no input tried behaved differently from the fix (`m-aaf290241efe`)
- `responses.py:545`: `             self.passthru_patterns += (prefix,) ` → `             self.passthru_patterns = (prefix,) ` made no test fail; no input tried behaved differently from the fix (`m-3c0148cacdc9`)
- `responses.py:643`: `             for pattern in self.passthru_patterns: ` → `             for pattern in self.passthru_patterns[:1]: ` made no test fail; no input tried behaved differently from the fix (`m-ce2e7e0375d0`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack RequestsMock.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; the behaviour diff could not compare RequestsMock.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 57,284 input and 6,893 output tokens, cost $0.3422 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.91 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.97 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 18.32 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `guard`: `not_guarded`, 80.64 s: the tests killed 2 of 5 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 8.93 s: none of the 54 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.12 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `behaviour_diff`: `partial`, 25.11 s: 1 input(s) compared on 2 function(s): 1 changed with the fix; not complete: RequestsMock.\_\_init\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 57.01 s: no counterexample found in 371 inputs against 7 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_respo...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `responses.RequestsMock.reset` (`responses.py`): not attacked (no property to check it against)
- `responses.RequestsMock.add_passthru` (`responses.py`): 371 inputs
- `responses.RequestsMock._on_request` (`responses.py`): not attacked (no property to check it against)
- `responses.RequestsMock.start` (`responses.py`): not attacked (no property to check it against); a public caller of the changed RequestsMock.\_on\_request
#### Fix lines run (report only)
- repro: 8 of 11 fix lines run
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
- Break My Fix could not attack RequestsMock.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare RequestsMock.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
#### Notes
- reproduce: style example test\_responses.py truncated to 6000 characters for the prompt
- guard: 2 of the rule mutant kills were crashes on the mutated line
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.20: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T22:24:50+00:00, issue sha256 `403cb9241b39e66739ca4aa2b04bf4b2563dc40e3a17965496459df16aaacc08`

</details>
