## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The reproduction test for tabs in constant expressions (e.g. \`#​define A&lt;tab&gt;(B + C)&lt;tab&gt;// comment\`) fails the same way before and after this fix, so the evidence shows the fix does not resolve the reported bug.

**Why this level:** the fix does not fix the bug: the reproduction test fails the same way before and after it

**Issue:** Tabs in constant expression should be treated like spaces · **Repo:** testbed · **Base** `tf-base` (`95a4928`) → **head** `tf-agent_wrong` (`0fd6f07`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 10 |
| `reproduce` | `fix_does_not_fix` | attempts 2 |
| `guard` | `skipped` | mutants 0, killed 0, survived 0 |
| `regressions` | `none_found` | compared 236, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 468 |
| `behaviour_diff` | `skipped` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 2, inputs tried 0, properties counted 8, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `not_run` | attempts 0, report only True |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; guard: skipped (there is no reproduction test to judge the tests with (fix\_does\_not\_fix)); behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (debug\_legacy\_parser: past the cap of 6 functions; debug\_tab\_legacy\_parser: past the cap of 6 functions; test\_newline\_requirements: past the cap of 6 functions)); Break My Fix could not attack analyze\_regex\_issue: it takes no parameters to vary; Break My Fix could not attack test\_individual\_components: it takes no parameters to vary; and 49 more in receipt.json
- **Model use:** 7 calls, 97,997 input and 9,922 output tokens, cost $0.4550 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 1.99 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.46 s: 10 changed module(s) imported from the copies (11 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `fix_does_not_fix`, 12.81 s: attempt 2: the test fails before and after the fix with the same failure signature, also after the model was shown the result This rests on a test written by the model claude-sonnet-5-5.
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `skipped`, 0.0 s: there is no reproduction test to judge the tests with (fix\_does\_not\_fix)
- `regressions`: `none_found`, 2.07 s: none of the 236 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 1.71 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no comprehens...`
- `behaviour_diff`: `skipped`, 0.25 s: the fix changes no function the behaviour diff can call (debug\_legacy\_parser: past the cap of 6 functions; debug\_tab\_legacy\_parser: past the cap of 6 functions; test\_newline\_requirements: past the cap of 6 functions)
- `break_my_fix`: `inconclusive`, 27.65 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.05 s: no candidate was confirmed (9 reported)
- `blind`: `not_run`, 0.0 s: the main test did not reproduce the bug
#### Break My Fix targets
- `cstruct.parser.CStyleParser._constants` (`dissect/cstruct/parser.py`): 0 inputs (no object of CStyleParser was built: none was given, and no type hints make one)
- `cstruct.parser.CStyleParser.parse` (`dissect/cstruct/parser.py`): 0 inputs (no object of CStyleParser was built: none was given, and no type hints make one); a public caller of the changed CStyleParser.\_constants
#### Fix lines run (report only)
- pr\_test: 1 of 468 fix lines run
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
- guard: skipped (there is no reproduction test to judge the tests with (fix\_does\_not\_fix))
- behaviour\_diff: skipped (the fix changes no function the behaviour diff can call (debug\_legacy\_parser: past the cap of 6 functions; debug\_tab\_legacy\_parser: past the cap of 6 functions; test\_newline\_requirements: past the cap of 6 functions))
- Break My Fix could not attack analyze\_regex\_issue: it takes no parameters to vary
- Break My Fix could not attack test\_individual\_components: it takes no parameters to vary
- Break My Fix could not attack test\_regex\_patterns: it takes no parameters to vary
- Break My Fix could not attack manual\_test\_constants\_method: it takes no parameters to vary
- Break My Fix could not attack test\_comment\_removal: it takes no parameters to vary
- Break My Fix could not attack test\_constants\_step\_by\_step: it takes no parameters to vary
- Break My Fix could not attack debug\_legacy\_parser: it takes no parameters to vary
- Break My Fix could not attack debug\_tab\_legacy\_parser: it takes no parameters to vary
- Break My Fix could not attack test\_cstyleparser\_with\_newlines: it takes no parameters to vary
- Break My Fix could not attack test\_newline\_requirements: it takes no parameters to vary
- Break My Fix could not attack test\_both\_parsers: it takes no parameters to vary
- Break My Fix could not attack test\_evaluation\_of\_values: it takes no parameters to vary
- Break My Fix could not attack test\_complex\_expression\_with\_tabs: it takes no parameters to vary
- Break My Fix could not attack test\_mixed\_whitespace: it takes no parameters to vary
- Break My Fix could not attack test\_normal\_define: it takes no parameters to vary
- Break My Fix could not attack test\_tab\_in\_define: it takes no parameters to vary
- Break My Fix could not attack test\_complex\_expression\_with\_tabs\_legacy: it takes no parameters to vary
- Break My Fix could not attack test\_mixed\_whitespace\_legacy: it takes no parameters to vary
- Break My Fix could not attack test\_normal\_define\_legacy: it takes no parameters to vary
- Break My Fix could not attack test\_tab\_in\_define\_legacy: it takes no parameters to vary
- Break My Fix could not attack test\_complex\_expression\_with\_tabs\_legacy: it takes no parameters to vary
- Break My Fix could not attack test\_mixed\_whitespace\_legacy: it takes no parameters to vary
- Break My Fix could not attack test\_normal\_define\_legacy: it takes no parameters to vary
- Break My Fix could not attack test\_tab\_in\_define\_legacy: it takes no parameters to vary
- the behaviour diff could not compare debug\_legacy\_parser: past the cap of 6 functions
- the behaviour diff could not compare debug\_tab\_legacy\_parser: past the cap of 6 functions
- the behaviour diff could not compare test\_newline\_requirements: past the cap of 6 functions
- the behaviour diff could not compare test\_cstyleparser\_with\_newlines: past the cap of 6 functions
- the behaviour diff could not compare test\_both\_parsers: past the cap of 6 functions
- the behaviour diff could not compare test\_evaluation\_of\_values: past the cap of 6 functions
- the behaviour diff could not compare test\_tab\_in\_define: past the cap of 6 functions
- the behaviour diff could not compare test\_mixed\_whitespace: past the cap of 6 functions
- the behaviour diff could not compare test\_normal\_define: past the cap of 6 functions
- the behaviour diff could not compare test\_complex\_expression\_with\_tabs: past the cap of 6 functions
- the behaviour diff could not compare test\_tab\_in\_define\_legacy: past the cap of 6 functions
- the behaviour diff could not compare test\_mixed\_whitespace\_legacy: past the cap of 6 functions
- the behaviour diff could not compare test\_normal\_define\_legacy: past the cap of 6 functions
- the behaviour diff could not compare test\_complex\_expression\_with\_tabs\_legacy: past the cap of 6 functions
- the behaviour diff could not compare test\_tab\_in\_define\_legacy: past the cap of 6 functions
- the behaviour diff could not compare test\_mixed\_whitespace\_legacy: past the cap of 6 functions
- the behaviour diff could not compare test\_normal\_define\_legacy: past the cap of 6 functions
- the behaviour diff could not compare test\_complex\_expression\_with\_tabs\_legacy: past the cap of 6 functions
- the behaviour diff could not compare CStyleParser.\_constants: past the cap of 6 functions
- the behaviour diff could not compare CStyleParser.parse: past the cap of 6 functions
- the behaviour diff could not compare analyze\_regex\_issue: new with the fix: nothing to compare
- the behaviour diff could not compare test\_regex\_patterns: new with the fix: nothing to compare
- the behaviour diff could not compare test\_individual\_components: new with the fix: nothing to compare
- the behaviour diff could not compare manual\_test\_constants\_method: new with the fix: nothing to compare
- the behaviour diff could not compare test\_constants\_step\_by\_step: new with the fix: nothing to compare
- the behaviour diff could not compare test\_comment\_removal: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 26 functions were shown
- behaviour\_diff: only the first 6 of 26 functions are attacked
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-07T13:24:19+00:00, issue sha256 `d9a52364a56dc16341daf4613925cf1bff25961b5ea3326ca685828cd92b262e`

</details>
