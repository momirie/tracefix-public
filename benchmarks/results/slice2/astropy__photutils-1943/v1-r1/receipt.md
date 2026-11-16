## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier's reproduction test for the empty cutout\_data\_nosub broadcasting error in IRAFStarFinder failed the same way before and after this fix, and Break My Fix found two inputs to find\_peaks (an all-zero 6x6 array that raises NoDetectionsWarning, and a 5x5 array with border\_width=1 that returns two peaks) that it flagged as breaking the fixed code. Start by checking why the reproduction sti…

**Why this level:** the fix does not fix the bug: the reproduction test fails the same way before and after it; Break My Fix finding 1: an input that breaks photutils.detection.peakfinder.find\_peaks; Break My Fix finding 2: an input that breaks photutils.detection.peakfinder.find\_peaks

**Issue:** IRAFStarFinder Error: self.cutout\_data\_nosub is size (0,) · **Repo:** testbed · **Base** `tf-base` (`8735398`) → **head** `tf-v1` (`6ac466f`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `find_peaks(data=[[0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, ...` → `raises NoDetectionsWarning: Input data is constant. No local...` (before the fix: `raises NoDetectionsWarning: Input data is constant. No local...`); breaks **peaks\_above\_threshold**: “Peaks are the maxima above the \`\`threshold\`\` within a local” (docstring); 1 more input break it the same way; test: `findings/finding_1.py`
2. `find_peaks(data=[[0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 5.0, 0.0, ...` → `returns <QTable length=2>\n  id  x_peak y_peak peak_value\nint...` (before the fix: `returns <QTable length=2>\n  id  x_peak y_peak peak_value\nint...`); breaks **larger\_border\_fewer\_peaks**: “The width in pixels to exclude around the border of the” (docstring); 1 more input break it the same way; test: `findings/finding_2.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 4 |
| `reproduce` | `fix_does_not_fix` | attempts 1 |
| `guard` | `skipped` | mutants 0, killed 0, survived 0 |
| `regressions` | `none_found` | compared 1658, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 12 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 6, inputs tried 537, properties counted 10, findings 2 |
| `integrity` | `clean` | flags 0 |

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; guard: skipped (there is no reproduction test to judge the tests with (fix\_does\_not\_fix)); 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 119,938 input and 11,394 output tokens, cost $0.6096 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 109.76 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 7.22 s: 4 changed module(s) imported from the copies (8 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `fix_does_not_fix`, 44.13 s: attempt 1: the test fails before and after the fix with the same failure signature, also after the model was shown the result This rests on a test written by the model claude-sonnet-5-5.
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no photutils/...`
- `guard`: `skipped`, 0.0 s: there is no reproduction test to judge the tests with (fix\_does\_not\_fix)
- `regressions`: `none_found`, 109.75 s: none of the 1658 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 0.02 s: report only: which fix lines the tests run
- `behaviour_diff`: `inconclusive`, 5.59 s: nothing was compared: \_IRAFStarFinderCatalog.sky: it could not be loaded after the fix: \_IRAFStarFinderCatalog.sky is a property here, not a method
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 130.25 s: 2 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 0.07 s: no candidate was confirmed (2 reported)
#### Break My Fix targets
- `photutils.detection.irafstarfinder._IRAFStarFinderCatalog.sky` (`photutils/detection/irafstarfinder.py`): not attacked (no property to check it against)
- `photutils.detection.irafstarfinder._IRAFStarFinderCatalog.cutout_convdata` (`photutils/detection/irafstarfinder.py`): not attacked (no property to check it against)
- `photutils.detection.peakfinder.find_peaks` (`photutils/detection/peakfinder.py`): 537 inputs
- `photutils.detection.core.StarFinderBase._find_stars` (`photutils/detection/core.py`): not attacked (no property to check it against)
- `photutils.detection.starfinder.StarFinder._get_raw_catalog` (`photutils/detection/starfinder.py`): not attacked (no property to check it against)
- `photutils.detection.starfinder.StarFinder.find_stars` (`photutils/detection/starfinder.py`): 0 inputs; a public caller of the changed StarFinder.\_get\_raw\_catalog
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
#### Notes
- reproduce: only the first 8 of 10 functions were shown
- reproduce: pyproject truncated to 3000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T18:27:48+00:00, issue sha256 `a2211dd712e1f7629dce5130a03d1e69e121f6cbfde432dbdfd95a863006bd7d`

</details>
