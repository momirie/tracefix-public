## Fix Receipt: L2 (L1, and the tests notice the fix being undone)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the bug with a test that fails before the fix and passes after it, and showed the tests fail again when the fix is reverted or broken, with no regressions found. The behaviour comparison did not finish for Trajectory.\_get\_df\_with\_distance, \_get\_df\_with\_acceleration, add\_distance and add\_acceleration, so check those paths with nanosecond-precision timestamps next.

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; the tests guard the fix: they fail when it is reverted or broken; not L3: Trajectory.\_get\_df\_with\_distance: the comparison did not finish; not L3: Trajectory.\_get\_df\_with\_acceleration: the comparison did not finish; not L3: Trajectory.add\_distance: the comparison did not finish; not L3: Trajectory.add\_acceleration: the comparison did not finish

**Issue:** set\_speed inaccurate with floating point (nanosecond) datetime values results in unmitigatable error · **Repo:** testbed · **Base** `tf-base` (`843ef83`) → **head** `tf-v1` (`8fcba9a`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 3 |
| `guard` | `guarded` | kill rate 0\.833, mutants 6, killed 5, survived 1 |
| `regressions` | `none_found` | compared 312, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 4 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 4, inputs tried 0, properties counted 14, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_on_head` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 2 of 2 killed; constant: 4 of 4 killed; no place for compare, logic, negate\_if, arithmetic, membership, loop, drop\_call, reraise

### Changes no test noticed
- `movingpandas/trajectory.py:1401`: `         temp_df.at[t0, name] = temp_df.iloc[1][name] ` → `         temp_df.at[t0, name] = 0 ` made no test fail; not compared with the fix (`m-1a44fd70cf04`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 9 calls, 95,021 input and 12,327 output tokens, cost $0.5375 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 23.68 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 13.5 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 120.16 s: attempt 3: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no movingpand...`
- `guard`: `guarded`, 493.7 s: the reproduction test fails with the fix reverted, and the tests killed 5 of 6 mutants
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no movingpand...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 24.07 s: none of the 312 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 9.72 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no movingpand...`
- `behaviour_diff`: `inconclusive`, 7.92 s: nothing was compared: Trajectory.\_get\_df\_with\_distance: the comparison did not finish
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `inconclusive`, 21.77 s: no target could be attacked: its objects' code can't run here: DataFrame is not the module's own name or plain data
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.05 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_on_head`, 44.62 s: attempt 1: after the fix some tests pass, but these still fail the same way: test\_add\_acceleration\_nanosecond\_index
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no movingpand...`
#### Break My Fix targets
- `movingpandas.trajectory.Trajectory._get_df_with_distance` (`movingpandas/trajectory.py`): 0 inputs (no object of Trajectory was built: none was given, and no type hints make one)
- `movingpandas.trajectory.Trajectory._get_df_with_acceleration` (`movingpandas/trajectory.py`): 0 inputs (no object of Trajectory was built: none was given, and no type hints make one)
- `movingpandas.trajectory.Trajectory.add_distance` (`movingpandas/trajectory.py`): not attacked (its objects' code can't run here: DataFrame is not the module's own name or plain data); a public caller of the changed Trajectory.\_get\_df\_with\_distance
- `movingpandas.trajectory.Trajectory.add_acceleration` (`movingpandas/trajectory.py`): not attacked (its objects' code can't run here: DataFrame is not the module's own name or plain data); a public caller of the changed Trajectory.\_get\_df\_with\_acceleration
#### Fix lines run (report only)
- repro: 2 of 4 fix lines run
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
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.17: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T23:17:43+00:00, issue sha256 `9e0ab80810abf536dc2b2a539222020404402dd054716d07e3e9db25e0a72383`

</details>
