## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The original bug reproduced and the fix changes yaml\_load's return type as intended with no regressions found, but Break My Fix found a counterexample: yaml\_load(stream='on:') raises TypeError: unsupported operand type(s) for +: 'bool' and 'str'. Look next at how the fix rebuilds the string when the parsed key is not a str (YAML parses 'on' as a boolean), and note that no test guards the reproduc…

**Why this level:** Break My Fix finding 1: an input that breaks jsonargparse.loaders\_dumpers.yaml\_load

**Issue:** str argument is mistaken as a dict if it looks like 'Foo:' · **Repo:** testbed · **Base** `tf-base` (`3f40766`) → **head** `tf-agent_ok` (`8c386c2`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `yaml_load(stream='on:')` → `raises TypeError: unsupported operand type(s) for +: 'bool' ...` (before the fix: `returns {True: None}`); breaks **word\_colon\_is\_string**: “str argument is mistaken as a dict if it looks like 'Foo:'” (issue); 3 more inputs break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.6, mutants 5, killed 3, survived 2 |
| `regressions` | `none_found` | compared 315, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 4 |
| `behaviour_diff` | `compared` | inputs compared 1, changes 1, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 511, properties counted 8, findings 1 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; compare: 2 of 2 killed; logic: 1 of 1 killed; negate\_if: 1 of 1 killed; constant: 2 of 3 killed; arithmetic: 1 of 1 killed; membership: 1 of 1 killed; no place for loop, drop\_call, reraise

### Behaviour changes
- `jsonargparse.loaders_dumpers.yaml_load` (`type`, 1 input): `returns {'Foo': None}` → `returns 'Foo:'`; the Judge (advisory) calls it intended: The issue reports that the str value 'Foo:' is wrongly parsed as {'Foo': None}; returning the string 'Foo:' is exactly the requested behaviour.

### Changes no test noticed
- `jsonargparse/loaders_dumpers.py:64`: `         elif len(value) == 1 and list(value.values())[0] is ... ` → `         elif len(value) >= 1 and list(value.values())[0] is ... ` made no test fail; no input tried behaved differently from the fix (`m-64061ffcbfb5`)
- `jsonargparse/loaders_dumpers.py:65`: `             key = list(value.keys())[0] ` → `             key = list(value.keys())[-1] ` made no test fail; no input tried behaved differently from the fix (`m-2cf971a990e5`)
- `jsonargparse/loaders_dumpers.py:64`: `         elif len(value) == 1 and list(value.values())[0] is ... ` → `         elif len(value) == 1 and list(value.values())[(-1)] ... ` made no test fail; no input tried behaved differently from the fix (`m-b3c59b931eed`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 49,109 input and 6,405 output tokens, cost $0.2592 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 5.05 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.44 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 24.36 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no jsonargpar...`
- `guard`: `not_guarded`, 117.61 s: the tests killed 3 of 5 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no jsonargpar...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 18.13 s: none of the 315 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.32 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no jsonargpar...`
- `behaviour_diff`: `compared`, 10.61 s: 1 input(s) compared on 1 function(s): 1 changed with the fix
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 24.84 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.01 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 10.6 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no jsonargpar...`
#### Break My Fix targets
- `jsonargparse.loaders_dumpers.yaml_load` (`jsonargparse/loaders_dumpers.py`): 511 inputs
#### Fix lines run (report only)
- repro: 4 of 4 fix lines run
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
- guard: 4 of the 9 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: 1 of the kills were crashes on the mutated line rather than failed checks; they still count (open question 26)
- guard: only the first 10 of 13 rule mutants were run
- guard: 1 of the rule mutant kills were crashes on the mutated line
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: style example jsonargparse\_tests/test\_actions.py truncated to 6000 characters for the prompt
- blind: pyproject truncated to 3000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T21:33:37+00:00, issue sha256 `cc92012dbba3dca7cb0ffec949988bbdd31ec48df8a372d012353a8b7bcd324e`

</details>
