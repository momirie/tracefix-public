## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproduced the NOS livestream bug, failing before the fix and passing after it, with no regressions found and the changed lines covered, but the evidence stays at L1 because the tests did not kill enough mutants and the behaviour-diff and Break My Fix stages were inconclusive. Next, strengthen the tests around the fixed plugin code so they catch mutants, and check the fix against a live NO…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 4 of 7 mutants; 80% is needed

**Issue:** plugins.nos: No playable streams found on this URL · **Repo:** testbed · **Base** `tf-base` (`22f1917`) → **head** `tf-gold` (`a495227`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.571, mutants 7, killed 4, survived 3 |
| `regressions` | `none_found` | compared 3736, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 27 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 1, inputs tried 0, properties counted 3, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 7; the rest in receipt.json)
- `src/streamlink/plugins/nos.py:54`: `         if res.status_code >= 400: ` → `         if res.status_code > 400: ` made no test fail; not compared with the fix (`m-d6b57d0baaf5`)
- `src/streamlink/plugins/nos.py:54`: `         if res.status_code >= 400: ` → `         if res.status_code >= 500: ` made no test fail; not compared with the fix (`m-e8805e394706`)
- `src/streamlink/plugins/nos.py:51`: `         hls_url, self.id, self.title = data ` → `         hls_url, self.title, self.id = data ` made no test fail; not compared with the fix (`m-8fe2492af878`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 36,346 input and 2,780 output tokens, cost $0.1691 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 23.5 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 4.48 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 22.72 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no build_back...`
- `guard`: `not_guarded`, 476.26 s: the tests killed 4 of 7 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no build_back...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 95.44 s: none of the 3736 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.99 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no build_back...`
- `behaviour_diff`: `inconclusive`, 3.62 s: nothing was compared: src/streamlink/plugins/nos.py: module-level code that computes a value changed (line 22, 24); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 25.43 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `streamlink.plugins.nos.NOS._get_streams` (`src/streamlink/plugins/nos.py`): 0 inputs
#### More changes no test noticed
- `src/streamlink/plugins/nos.py:53`: `         res = self.session.http.get(hls_url, raise_for_statu... ` → `         res = self.session.http.get(hls_url, raise_for_statu... ` made no test fail; not compared with the fix (`m-5cad14b46a36`)
- `src/streamlink/plugins/nos.py:54`: `         if res.status_code >= 400: ` → `         if res.status_code > 400: ` made no test fail; not compared with the fix (`m-d6b57d0baaf5`)
- `src/streamlink/plugins/nos.py:54`: `         if res.status_code >= 400: ` → `         if res.status_code >= 399: ` made no test fail; not compared with the fix (`m-1dc148cfb1e0`)
- `src/streamlink/plugins/nos.py:54`: `         if res.status_code >= 400: ` → `         if res.status_code >= 401: ` made no test fail; not compared with the fix (`m-9cb7ade435c5`)
#### Fix lines run (report only)
- repro: 24 of 27 fix lines run
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
- reproduce: pyproject truncated to 3000 characters for the prompt
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T17:38:00+00:00, issue sha256 `fd8de88cf76ee41447cf118e1c6440e69fc732b7c61984b31f27958027add3dc`

</details>
