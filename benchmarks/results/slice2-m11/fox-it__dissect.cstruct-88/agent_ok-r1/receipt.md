## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The original bug was reproduced and the fix makes ExpressionTokenizer.tokenize stop raising in the intended case, but Break My Fix found an input where it still raises ExpressionTokenizerError on '#', and no test guards the fix. Check whether feeding full '#​define' lines with tabs to the tokenizer is a realistic path from the issue's parsing scenario or falls outside the tokenizer's scope, and ad…

**Why this level:** Break My Fix finding 1: an input that breaks cstruct.expression.ExpressionTokenizer.tokenize

**Issue:** Tabs in constant expression should be treated like spaces · **Repo:** testbed · **Base** `tf-base` (`95a4928`) → **head** `tf-agent_ok` (`0d420a7`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `tokenize(self="ExpressionTokenizer(expression='#define B 1\\...` → `raises ExpressionTokenizerError: Tokenizer does not recogniz...` (before the fix: `raises ExpressionTokenizerError: Tokenizer does not recogniz...`); breaks **tokens\_contain\_no\_whitespace\_separators**: “tabs are legal whitespace separators” (issue); 3 more inputs break it the same way; test: `findings/finding_1.py`; **Doubt (still counted):** this may be the code's own refusal: a `raise` in the project, same before the fix

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 1\.0, mutants 7, killed 7, survived 0 |
| `regressions` | `none_found` | compared 236, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 104 |
| `behaviour_diff` | `partial` | inputs compared 195, changes 1, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 334, properties counted 6, findings 1 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; compare: 0 of 1 killed; logic: 0 of 1 killed; negate\_if: 1 of 1 killed; constant: 1 of 1 killed; arithmetic: 0 of 1 killed; membership: 0 of 1 killed; loop: 1 of 1 killed; drop\_call: 0 of 1 killed; reraise: 0 of 1 killed

### Behaviour changes
- `cstruct.expression.ExpressionTokenizer.tokenize` (`no_raise`, 1 input): `raises ExpressionTokenizerError; left its arguments as built...` → `returns []; left its arguments as builtins.list([builtins.tu...`; the Judge (advisory) calls it intended: The issue says tabs in a constant expression should be treated like spaces, and a lone space is skipped. So a lone tab should now tokenize to \[\] instead of raising.

### Changes no test noticed (3 of 6; the rest in receipt.json)
- `final_verification.py:71`: `if __name__ == "__main__":` → `if __name__ != "__main__":` made no test fail; not compared with the fix (`m-0e7fb4b4446e`)
- `final_verification.py:26`: `         if isinstance(result, str) and '(' in result: ` → `         if isinstance(result, str) or '(' in result: ` made no test fail; not compared with the fix (`m-9c6ee0e5588b`)
- `final_verification.py:62`: `             c.load(definition + '\n')  # Add newline like in... ` → `             c.load(definition - '\n')  # Add newline like in... ` made no test fail; not compared with the fix (`m-511b40765462`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack test\_exact\_issue\_example: it takes no parameters to vary; Break My Fix could not attack test\_various\_tab\_formats: it takes no parameters to vary; Break My Fix could not attack test\_mixed\_whitespace: it takes no parameters to vary; Break My Fix could not attack test\_normal\_spaces: it takes no parameters to vary; and 7 more in receipt.json
- **Model use:** 10 calls, 67,530 input and 7,513 output tokens, cost $0.3595 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.0 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.44 s: 3 changed module(s) imported from the copies (4 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 17.34 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 210.21 s: the PR's test file comprehensive\_test.py does not fail with the fix reverted (passed); the PR's test file test\_detailed.py does not fail with the fix reverted (passed)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_detai...`
  - 2 more command(s) in receipt.json
- `regressions`: `none_found`, 2.31 s: none of the 236 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.68 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
- `behaviour_diff`: `partial`, 5.73 s: 195 input(s) compared on 1 function(s): 1 changed with the fix; not complete: final\_verification.py: module-level code that computes a value changed (line 71, 72, 73, 75, 76); what uses it is not compared
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `found`, 28.54 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.02 s: no candidate was confirmed (2 reported)
- `blind`: `reproduced`, 20.61 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### Break My Fix targets
- `cstruct.expression.ExpressionTokenizer.tokenize` (`dissect/cstruct/expression.py`): 334 inputs
#### More changes no test noticed
- `final_verification.py:26`: `         if isinstance(result, str) and '(' in result: ` → `         if isinstance(result, str) and '(' not in result: ` made no test fail; not compared with the fix (`m-9930bc9570ee`)
- `final_verification.py:10`: `     print("Testing the exact issue example:") ` → `     pass ` made no test fail; not compared with the fix (`m-38a52ca6bbea`)
- `final_verification.py:37`: `         print(f"✗ FAILED: {e}") ` → `         raise\n        print(f"✗ FAILED: {e}") ` made no test fail; not compared with the fix (`m-02542e6ea08b`)
#### Fix lines run (report only)
- repro: 2 of 104 fix lines run
- pr\_test: 2 of 104 fix lines run
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
- Break My Fix could not attack test\_exact\_issue\_example: it takes no parameters to vary
- Break My Fix could not attack test\_various\_tab\_formats: it takes no parameters to vary
- Break My Fix could not attack test\_mixed\_whitespace: it takes no parameters to vary
- Break My Fix could not attack test\_normal\_spaces: it takes no parameters to vary
- Break My Fix could not attack test\_tab\_in\_define: it takes no parameters to vary
- the behaviour diff could not compare test\_exact\_issue\_example: new with the fix: nothing to compare
- the behaviour diff could not compare test\_various\_tab\_formats: new with the fix: nothing to compare
- the behaviour diff could not compare test\_tab\_in\_define: new with the fix: nothing to compare
- the behaviour diff could not compare test\_normal\_spaces: new with the fix: nothing to compare
- the behaviour diff could not compare test\_mixed\_whitespace: new with the fix: nothing to compare
#### Notes
- guard: only the first 10 of 89 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-07T13:25:09+00:00, issue sha256 `d9a52364a56dc16341daf4613925cf1bff25961b5ea3326ca685828cd92b262e`

</details>
