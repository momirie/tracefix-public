## Fix Receipt: L1 (the bug is reproduced and this fix removes it)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproducing the IRAFStarFinder empty-cutout broadcasting error failed before the fix and passed after it, with no regressions found and no breaking inputs from Break My Fix, though the behaviour diff was inconclusive. The main gap is that the tests did not guard the fix against mutants, so a reviewer should add tests that pin down the fixed behaviour more tightly.

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; not L2: the tests killed 0 of 3 mutants; 80% is needed

**Issue:** IRAFStarFinder Error: self.cutout\_data\_nosub is size (0,) · **Repo:** testbed · **Base** `tf-base` (`8735398`) → **head** `tf-gold` (`5b241b9`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 4 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 3, killed 0, survived 3 |
| `regressions` | `none_found` | compared 1658, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 22 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `none_found` | targets 6, inputs tried 406, properties counted 15, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 2 of 2 killed; compare: 1 of 2 killed; negate\_if: 1 of 2 killed; constant: 0 of 2 killed; arithmetic: 0 of 2 killed; no place for logic, membership, loop, drop\_call, reraise

### Changes no test noticed (3 of 9; the rest in receipt.json)
- `photutils/detection/core.py:90`: `yborder = (kernel.shape[0] - 1) // 2` → `yborder = kernel.shape[0] // 2` made no test fail; not compared with the fix (`m-5c0fb1ebca2d`)
- `photutils/detection/core.py:91`: `xborder = (kernel.shape[1] - 1) // 2` → `xborder = (kernel.shape[1] + 1) // 2` made no test fail; not compared with the fix (`m-6b4f7c60d7f7`)
- `photutils/detection/core.py:91`: `xborder = (kernel.shape[1] - 1) // 2` → `xborder = (kernel.shape[0] - 1) // 2` made no test fail; not compared with the fix (`m-b846f9cabb14`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 7 calls, 122,905 input and 12,239 output tokens, cost $0.6296 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 112.65 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 7.3 s: 4 changed module(s) imported from the copies (8 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `reproduce`: `reproduced`, 23.98 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no photutils/...`
- `guard`: `not_guarded`, 1819.37 s: the tests killed 0 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no photutils/...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 110.56 s: none of the 1658 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 4.46 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no photutils/...`
- `behaviour_diff`: `inconclusive`, 5.57 s: nothing was compared: \_IRAFStarFinderCatalog.sky: it could not be loaded after the fix: \_IRAFStarFinderCatalog.sky is a property here, not a method
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s test_tr...`
- `break_my_fix`: `none_found`, 21.79 s: no counterexample found in 406 inputs against 15 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no test_trace...`
- `integrity`: `clean`, 0.04 s: no candidate was confirmed (2 reported)
- `blind`: `reproduced`, 33.21 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no photutils/...`
#### Break My Fix targets
- `photutils.detection.irafstarfinder._IRAFStarFinderCatalog.sky` (`photutils/detection/irafstarfinder.py`): not attacked (\_IRAFStarFinderCatalog.sky is a property here, not a method)
- `photutils.detection.irafstarfinder._IRAFStarFinderCatalog.cutout_convdata` (`photutils/detection/irafstarfinder.py`): not attacked (\_IRAFStarFinderCatalog.cutout\_convdata is a property here, not a method)
- `photutils.detection.peakfinder.find_peaks` (`photutils/detection/peakfinder.py`): 406 inputs
- `photutils.detection.core.StarFinderBase._find_stars` (`photutils/detection/core.py`): 0 inputs (no strategy for convolved\_data, kernel, threshold)
- `photutils.detection.starfinder.StarFinder._get_raw_catalog` (`photutils/detection/starfinder.py`): 0 inputs (no object of StarFinder was built: none was given, and no type hints make one)
- `photutils.detection.starfinder.StarFinder.find_stars` (`photutils/detection/starfinder.py`): 0 inputs (no object of StarFinder was built: none was given, and no type hints make one); a public caller of the changed StarFinder.\_get\_raw\_catalog
#### More changes no test noticed
- `photutils/detection/irafstarfinder.py:419`: `         if nsky == 0.0:  # pragma: no cover ` → `         if nsky != 0.0:  # pragma: no cover ` made no test fail; not compared with the fix (`m-ae744b2b3730`)
- `photutils/detection/core.py:90`: `                 yborder = (kernel.shape[0] - 1) // 2 ` → `                 yborder = (kernel.shape[(-1)] - 1) // 2 ` made no test fail; not compared with the fix (`m-97b4008100d9`)
- `photutils/detection/core.py:90`: `                 yborder = (kernel.shape[0] - 1) // 2 ` → `                 yborder = (kernel.shape[0] + 1) // 2 ` made no test fail; not compared with the fix (`m-68c1b1f35f03`)
- `photutils/detection/core.py:89`: `             if isinstance(kernel, np.ndarray): ` → `             if not (isinstance(kernel, np.ndarray)): ` made no test fail; not compared with the fix (`m-e08dd7eb0c81`)
- `photutils/detection/core.py:90`: `                 yborder = (kernel.shape[0] - 1) // 2 ` → `                 yborder = (kernel.shape[1] - 1) // 2 ` made no test fail; not compared with the fix (`m-cd560dc2a021`)
- `photutils/detection/core.py:90`: `                 yborder = (kernel.shape[0] - 1) // 2 ` → `                 yborder = (kernel.shape[0] - 1) / 2 ` made no test fail; not compared with the fix (`m-8e0e060edc86`)
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
- guard: 6 of the 9 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 44 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.10.16: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: only the first 8 of 10 functions were shown
- blind: pyproject truncated to 3000 characters for the prompt
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T17:44:29+00:00, issue sha256 `a2211dd712e1f7629dce5130a03d1e69e121f6cbfde432dbdfd95a863006bd7d`

</details>
