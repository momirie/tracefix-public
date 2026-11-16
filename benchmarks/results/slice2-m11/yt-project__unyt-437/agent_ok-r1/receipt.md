## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The original bug was reproduced, but Break My Fix found an input the fixed \`to\_astropy\` mishandles. \`unyt\_array(\[1, 2, 3\], 'km/m')\` returns a dimensionless \`Quantity \[1., 2., 3.\]\`, which appears to drop the km/m scale factor of 1000; check how the fix handles dimensionless units that are not pure numbers.

**Why this level:** Break My Fix finding 1: an input that breaks unyt.array.unyt\_array.to\_astropy

**Issue:** unyt fails to convert dimensionless array to astropy using .to\_astropy() · **Repo:** testbed · **Base** `tf-base` (`f794930`) → **head** `tf-agent_ok` (`324208f`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `to_astropy(self="unyt_array([1, 2, 3], 'km/m')")` → `returns <Quantity [1., 2., 3.]>` (before the fix: `returns <Quantity [1., 2., 3.] km / m>`); breaks **dimensionless\_values\_preserved\_with\_scale**: “Creates a new AstroPy quantity with the same unit information.” (docstring); 2 more inputs break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite failed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.6, mutants 5, killed 3, survived 2 |
| `regressions` | `none_found` | compared 491, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 2 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 1, inputs tried 13, properties counted 8, findings 1 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 1 of 1 killed; negate\_if: 1 of 1 killed; arithmetic: 0 of 1 killed; no place for compare, logic, constant, membership, loop, drop\_call, reraise

### Changes no test noticed
- `unyt/array.py:1317`: `             return self.value * _astropy.units.dimensionless... ` → `             return self * _astropy.units.dimensionless_unscaled ` made no test fail; not compared with the fix (`m-c1ac8ff26cc7`)
- `unyt/array.py:1316`: `         if self.units.is_dimensionless: ` → `         if self.units.is_dimensionless and not kwargs: ` made no test fail; not compared with the fix (`m-6c8da52fd809`)
- `unyt/array.py:1317`: `             return self.value * _astropy.units.dimensionless... ` → `             return self.value / _astropy.units.dimensionless... ` made no test fail; not compared with the fix (`m-8b288e6575d6`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 45,535 input and 7,007 output tokens, cost $0.2892 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 8.78 s: base suite failed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 6.37 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 21.32 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no unyt/tests...`
- `guard`: `not_guarded`, 123.46 s: the tests killed 3 of 5 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no unyt/tests...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 33.99 s: none of the 491 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 6.41 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no unyt/tests...`
- `behaviour_diff`: `inconclusive`, 4.8 s: nothing was compared: unyt\_array.to\_astropy: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 28.91 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.04 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 21.83 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no unyt/tests...`
#### Break My Fix targets
- `unyt.array.unyt_array.to_astropy` (`unyt/array.py`): 13 inputs
#### Fix lines run (report only)
- repro: 2 of 2 fix lines run
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
- guard: 1 of the 6 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: 1 of the kills were crashes on the mutated line rather than failed checks; they still count (open question 26)
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T22:38:16+00:00, issue sha256 `3fb54e58477933587f9e7eda0582c579612f7da844e2b72b123e869d0dc1ebef`

</details>
