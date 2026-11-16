## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The original IRAFStarFinder failure was reproduced, no regressions were found and the fix lines were covered, but no guard test was confirmed and Break My Fix found an input where find\_peaks on a 5x5 array with peaks at (1,3) and (2,2), threshold=1.0 and border\_width=2 raises NoDetectionsWarning saying no local peaks were found. Look next at how find\_peaks handles border\_width relative to array s…

**Why this level:** Break My Fix finding 1: an input that breaks photutils.detection.peakfinder.find\_peaks

**Issue:** IRAFStarFinder Error: self.cutout\_data\_nosub is size (0,) · **Repo:** testbed · **Base** `tf-base` (`8735398`) → **head** `tf-gold` (`5b241b9`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `find_peaks(data=[[0.0, 0.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, ...` → `raises NoDetectionsWarning: No local peaks were found.` (before the fix: `raises NoDetectionsWarning: No local peaks were found.`); breaks **border\_excluded**: “The width in pixels to exclude around the border of the” (docstring); 1 more input break it the same way; test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 4 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 7, killed 0, survived 7 |
| `regressions` | `none_found` | compared 1658, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 22 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `found` | targets 6, inputs tried 207, properties counted 15, findings 1 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 13; the rest in receipt.json)
- `photutils/detection/core.py:90`: `                 yborder = (kernel.shape[0] - 1) // 2 ` → `                 yborder = kernel.shape[0] // 2 ` made no test fail; not compared with the fix (`m-293537b39b7f`)
- `photutils/detection/core.py:91`: `                 xborder = (kernel.shape[1] - 1) // 2 ` → `                 xborder = (kernel.shape[1] - 1) // 2 + 1 ` made no test fail; not compared with the fix (`m-b3373b0a36cb`)
- `photutils/detection/core.py:93`: `                 yborder = kernel.yradius ` → `                 yborder = kernel.xradius ` made no test fail; not compared with the fix (`m-1fff59b547be`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 107,933 input and 11,322 output tokens, cost $0.5902 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 113.07 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 7.41 s: 4 changed module(s) imported from the copies (8 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 35.84 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no photutils/...`
- `guard`: `not_guarded`, 2261.98 s: the tests killed 0 of 7 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no photutils/...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 110.83 s: none of the 1658 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 4.52 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no photutils/...`
- `behaviour_diff`: `inconclusive`, 5.66 s: nothing was compared: \_IRAFStarFinderCatalog.sky: it could not be loaded after the fix: \_IRAFStarFinderCatalog.sky is a property here, not a method
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `found`, 120.11 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.04 s: no candidate was confirmed (2 reported)
#### Break My Fix targets
- `photutils.detection.irafstarfinder._IRAFStarFinderCatalog.sky` (`photutils/detection/irafstarfinder.py`): not attacked (\_IRAFStarFinderCatalog.sky is a property here, not a method)
- `photutils.detection.irafstarfinder._IRAFStarFinderCatalog.cutout_convdata` (`photutils/detection/irafstarfinder.py`): not attacked (\_IRAFStarFinderCatalog.cutout\_convdata is a property here, not a method)
- `photutils.detection.peakfinder.find_peaks` (`photutils/detection/peakfinder.py`): 207 inputs
- `photutils.detection.core.StarFinderBase._find_stars` (`photutils/detection/core.py`): 0 inputs
- `photutils.detection.starfinder.StarFinder._get_raw_catalog` (`photutils/detection/starfinder.py`): 0 inputs
- `photutils.detection.starfinder.StarFinder.find_stars` (`photutils/detection/starfinder.py`): 0 inputs; a public caller of the changed StarFinder.\_get\_raw\_catalog
#### More changes no test noticed
- `photutils/detection/peakfinder.py:142`: `     if border_width < 0: ` → `     if border_width < -1: ` made no test fail; not compared with the fix (`m-0171941d079c`)
- `photutils/detection/peakfinder.py:168`: `     if border_width > 0: ` → `     if border_width > 1: ` made no test fail; not compared with the fix (`m-7274ab8cf9d0`)
- `photutils/detection/starfinder.py:99`: `         if denom > 0: ` → `         if denom >= 0: ` made no test fail; not compared with the fix (`m-bed4c6b0d92e`)
- `photutils/detection/peakfinder.py:144`: `     if int(border_width) != border_width: ` → `     if int(border_width) > border_width: ` made no test fail; not compared with the fix (`m-e36df5c2694e`)
- `photutils/detection/irafstarfinder.py:456`: `         return self.make_cutouts(self.convolved_data) ` → `         return None ` made no test fail; not compared with the fix (`m-8c9773796408`)
- `photutils/detection/core.py:89`: `             if isinstance(kernel, np.ndarray): ` → `             if not (isinstance(kernel, np.ndarray)): ` made no test fail; not compared with the fix (`m-e08dd7eb0c81`)
- `photutils/detection/core.py:90`: `                 yborder = (kernel.shape[0] - 1) // 2 ` → `                 yborder = (kernel.shape[(-1)] - 1) // 2 ` made no test fail; not compared with the fix (`m-97b4008100d9`)
- `photutils/detection/core.py:90`: `                 yborder = (kernel.shape[0] - 1) // 2 ` → `                 yborder = (kernel.shape[1] - 1) // 2 ` made no test fail; not compared with the fix (`m-cd560dc2a021`)
- `photutils/detection/core.py:90`: `                 yborder = (kernel.shape[0] - 1) // 2 ` → `                 yborder = (kernel.shape[0] + 1) // 2 ` made no test fail; not compared with the fix (`m-68c1b1f35f03`)
- `photutils/detection/core.py:90`: `                 yborder = (kernel.shape[0] - 1) // 2 ` → `                 yborder = (kernel.shape[0] - 0) // 2 ` made no test fail; not compared with the fix (`m-5ca2ce7b4b41`)
#### Fix lines run (report only)
- repro: 13 of 22 fix lines run
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
- reproduce: only the first 8 of 10 functions were shown
- reproduce: pyproject truncated to 3000 characters for the prompt
- guard: only the first 10 of 44 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.16: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T17:43:24+00:00, issue sha256 `a2211dd712e1f7629dce5130a03d1e69e121f6cbfde432dbdfd95a863006bd7d`

</details>
