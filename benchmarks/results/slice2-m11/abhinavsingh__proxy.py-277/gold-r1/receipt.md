## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): At level L1, a test reproduced the CONNECT host/port parsing failure before the fix and passed after it, with no regressions found and no breaking inputs from Break My Fix, but the fix was not guarded: the tests did not kill enough mutants to reach L2. The most important next step is to strengthen tests around the changed parsing lines (e.g., CONNECT targets like 'host:443' across Python versions…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 4 of 6 mutants; 80% is needed

**Issue:** Broken tests on Python 3.7+ (urllib.parse behavior has changed) · **Repo:** testbed · **Base** `tf-base` (`f75e21c`) → **head** `tf-gold` (`3fb6eab`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 2 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.667, mutants 6, killed 4, survived 2 |
| `regressions` | `none_found` | compared 114, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 5 |
| `behaviour_diff` | `partial` | inputs compared 194, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 1, inputs tried 13, properties counted 4, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; compare: 1 of 1 killed; constant: 0 of 8 killed; no place for logic, negate\_if, arithmetic, membership, loop, drop\_call, reraise

### Changes no test noticed (3 of 10; the rest in receipt.json)
- `proxy/http/parser.py:115`: `                 self.port = 443 if self.url.path == b'' else \ ` → `                 self.port = 80 if self.url.path == b'' else \ ` made no test fail; no input tried behaved differently from the fix (`m-ffef36f1c944`)
- `proxy/http/parser.py:115`: `                 self.port = 443 if self.url.path == b'' else \ ` → `                 self.port = 443 if self.url.path is None else \ ` made no test fail; no input tried behaved differently from the fix (`m-3ec3774f0983`)
- `proxy/common/version.py:11`: `VERSION = (2, 1, 1)` → `VERSION = (1, 1, 1)` made no test fail; not compared with the fix (`m-9cdf9393d44c`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 111,485 input and 8,946 output tokens, cost $0.5456 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 6.51 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.52 s: 2 changed module(s) imported from the copies (4 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 16.87 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no proxy/test...`
- `guard`: `not_guarded`, 108.69 s: the tests killed 4 of 6 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no proxy/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 6.6 s: none of the 114 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 1.75 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no proxy/test...`
- `behaviour_diff`: `partial`, 14.67 s: 194 input(s) compared on 1 function(s): 0 changed with the fix; not complete: proxy/common/version.py: module-level code that computes a value changed (line 11); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `none_found`, 14.28 s: no counterexample found in 13 inputs against 4 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 10.29 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no proxy/test...`
#### Break My Fix targets
- `proxy.http.parser.HttpParser.set_line_attributes` (`proxy/http/parser.py`): 13 inputs
#### More changes no test noticed
- `proxy/common/version.py:11`: `VERSION = (2, 1, 1)` → `VERSION = (3, 1, 1)` made no test fail; not compared with the fix (`m-a492beefbb07`)
- `proxy/common/version.py:11`: `VERSION = (2, 1, 1)` → `VERSION = (2, 0, 1)` made no test fail; not compared with the fix (`m-af2058390ef4`)
- `proxy/common/version.py:11`: `VERSION = (2, 1, 1)` → `VERSION = (2, 2, 1)` made no test fail; not compared with the fix (`m-f8eb791aec8a`)
- `proxy/common/version.py:11`: `VERSION = (2, 1, 1)` → `VERSION = (2, 1, 2)` made no test fail; not compared with the fix (`m-fe9164575dee`)
- `proxy/http/parser.py:115`: `                 self.port = 443 if self.url.path == b'' else \ ` → `                 self.port = 442 if self.url.path == b'' else \ ` made no test fail; no input tried behaved differently from the fix (`m-6ae23836ed86`)
- `proxy/http/parser.py:115`: `                 self.port = 443 if self.url.path == b'' else \ ` → `                 self.port = 444 if self.url.path == b'' else \ ` made no test fail; no input tried behaved differently from the fix (`m-478d79617c6b`)
- `setup.py:13`: `VERSION = (2, 1, 1)` → `VERSION = (1, 1, 1)` made no test fail; not compared with the fix (`m-fecb4f9fe5a0`)
#### Fix lines run (report only)
- repro: 4 of 5 fix lines run
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
- guard: 2 of the 8 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: 1 of the kills were crashes on the mutated line rather than failed checks; they still count (open question 26)
- guard: only the first 10 of 14 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T21:42:38+00:00, issue sha256 `1a9973633c6b722591405c3e874223aa2c0300c03ed7877ea166a2dfe4ae851c`

</details>
