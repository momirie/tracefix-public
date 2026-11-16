## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug and found no regressions, but Break My Fix found an input that breaks the fixed yaml\_load: yaml\_load(stream='null:') raises TypeError (unsupported operand type(s) for +: 'NoneType' and 'str'). Look next at how the fix rebuilds a string from a single-key dict whose key parses to None (and likely other non-string keys such as numbers or booleans), and note that the r…

**Why this level:** Break My Fix finding 1: an input that breaks jsonargparse.loaders\_dumpers.yaml\_load

**Issue:** str argument is mistaken as a dict if it looks like 'Foo:' · **Repo:** testbed · **Base** `tf-base` (`3f40766`) → **head** `tf-gold` (`01bd33c`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `yaml_load(stream='null:')` → `raises TypeError: unsupported operand type(s) for +: 'NoneTy...` (before the fix: `returns {None: None}`); breaks **colon\_suffixed\_word\_stays\_string**: “str argument is mistaken as a dict if it looks like 'Foo:'” (issue); 3 more inputs break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.333, mutants 3, killed 1, survived 2 |
| `regressions` | `none_found` | compared 315, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 5 |
| `behaviour_diff` | `compared` | inputs compared 1, changes 1, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 213, properties counted 7, findings 1 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; compare: 2 of 2 killed; logic: 2 of 2 killed; negate\_if: 2 of 2 killed; constant: 1 of 1 killed; arithmetic: 1 of 1 killed; membership: 1 of 1 killed; no place for loop, drop\_call, reraise

### Behaviour changes
- `jsonargparse.loaders_dumpers.yaml_load` (`type`, 1 input): `returns {'Foo': None}` → `returns 'Foo:'`; the Judge (advisory) calls it intended: The issue reports that the str value 'Foo:' is parsed as {'Foo': None}, and this change makes yaml\_load return the string 'Foo:' unchanged, which is exactly that bug fixed.

### Changes no test noticed
- `jsonargparse/loaders_dumpers.py:59`: `     if isinstance(value, dict) and value and all(v is None f... ` → `     if isinstance(value, dict) and all(v is None for v in va... ` made no test fail; no input tried behaved differently from the fix (`m-9cc137fe0e56`)
- `jsonargparse/loaders_dumpers.py:64`: `             if len(keys) > 0 and keys == set(value.keys()): ` → `             if len(keys) > 0 and keys <= set(value.keys()): ` made no test fail; no input tried behaved differently from the fix (`m-b2b587368885`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 48,901 input and 5,531 output tokens, cost $0.2410 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 5.11 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.43 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 24.45 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no jsonargpar...`
- `guard`: `not_guarded`, 76.85 s: the tests killed 1 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no jsonargpar...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 17.33 s: none of the 315 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.25 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no jsonargpar...`
- `behaviour_diff`: `compared`, 8.44 s: 1 input(s) compared on 1 function(s): 1 changed with the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 17.6 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 13.94 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no jsonargpar...`
#### Break My Fix targets
- `jsonargparse.loaders_dumpers.yaml_load` (`jsonargparse/loaders_dumpers.py`): 213 inputs
#### Fix lines run (report only)
- repro: 2 of 5 fix lines run
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
- reproduce: style example jsonargparse\_tests/test\_actions.py truncated to 6000 characters for the prompt
- reproduce: pyproject truncated to 3000 characters for the prompt
- guard: 3 of the 6 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 18 rule mutants were run
- guard: 2 of the rule mutant kills were crashes on the mutated line
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: style example jsonargparse\_tests/test\_actions.py truncated to 6000 characters for the prompt
- blind: pyproject truncated to 3000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T21:30:47+00:00, issue sha256 `cc92012dbba3dca7cb0ffec949988bbdd31ec48df8a372d012353a8b7bcd324e`

</details>
