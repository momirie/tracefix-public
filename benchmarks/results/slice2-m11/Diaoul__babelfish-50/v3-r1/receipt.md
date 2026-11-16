## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The fix makes 15 previously passing tests fail, including Country equality, hashing, pickling and attribute tests, Language equality/hash/pickle tests, IETF formatting and parsing, and the opensubtitles converter, and the verifier could not confirm a test guards the reported bug. Look first at the Country regressions (test\_eq, test\_hash\_eq, test\_pickle) and the Language.fromietf changes the Judge…

**Why this level:** regression: tests/test\_converters.py::test\_converter\_opensubtitles passed before the fix and fails after it; regression: tests/test\_country.py::test\_eq passed before the fix and fails after it; regression: tests/test\_country.py::test\_ne passed before the fix and fails after it; regression: tests/test\_country.py::test\_hash\_eq passed before the fix and fails after it; regression: tests/test\_country.py::test\_hasattr\_name passed before the fix and fails after it; regression: tests/test\_country.py::test\_hasattr\_alpha2 passed before the fix and fails after it; and 9 more in receipt.json

**Issue:** Immutability issues · **Repo:** testbed · **Base** `tf-base` (`7584c2a`) → **head** `tf-v3` (`b6dfd94`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples (5 of 15; the rest in receipt.json)
1. Regression: `tests/test_converters.py::test_converter_opensubtitles` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: alpha2)
2. Regression: `tests/test_country.py::test_eq` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: alpha2)
3. Regression: `tests/test_country.py::test_ne` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: alpha2)
4. Regression: `tests/test_country.py::test_hash_eq` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: alpha2)
5. Regression: `tests/test_country.py::test_hasattr_name` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert False)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 3, killed 0, survived 3 |
| `regressions` | `found` | compared 49, regressions 15, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 58 |
| `behaviour_diff` | `partial` | inputs compared 203, changes 9, groups 3 |
| `break_my_fix` | `none_found` | targets 5, inputs tried 27, properties counted 15, findings 0 |
| `integrity` | `clean` | flags 0 |
| `blind` | `fails_differently` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 2 of 2 killed; compare: 2 of 2 killed; negate\_if: 1 of 2 killed; constant: 0 of 1 killed; membership: 0 of 1 killed; loop: 0 of 1 killed; drop\_call: 1 of 1 killed; no place for logic, arithmetic, reraise

### Behaviour changes
- `babelfish.language.Language.fromietf` (`value`, 4 inputs): `returns <Language [en-Latn]>` → `returns <Language [en-Latn]>`; the Judge (advisory) calls it intended: Same language and script; only the internal field names differ, a side effect of the frozen dataclass the issue explicitly asks for (and accepts as breaking).; the Judge (advisory) calls it intended: Same language value; the 'alpha3' to 'language' field rename comes from the frozen-dataclass immutability the issue requests.; the Judge (advisory) calls it intended: Same language value; only the internal representation changed as part of the frozen dataclass conversion the issue requests.; the Judge (advisory) calls it intended: Same resolved language 'abk'; only the internal field naming changed under the immutability rework the issue asks for.
- `babelfish.language.Language.fromietf` (`message`, 3 inputs): `raises ValueError: '' is not a valid language` → `raises ValueError: '1' is not a valid script`; the Judge (advisory) calls it suspicious: The error now reports an invalid script instead of the invalid empty language; the issue only asks for immutability, not a change in validation order or error messages.; the Judge (advisory) calls it suspicious: Validation order changed so the script error is raised before the invalid-language error; nothing in the issue or docstring asks for this.; the Judge (advisory) calls it suspicious: The invalid language is no longer reported first; a country error is raised instead, a reordering the immutability issue does not request.
- `babelfish.language.Language.fromietf` (`value`, 2 inputs): `returns <Language [fr-FR-Latn]>; left module data as babelfi...` → `returns <unprintable Language: AttributeError>; left module ...`; the Judge (advisory) calls it suspicious: The result is now unprintable (AttributeError), apparently because Country no longer has 'alpha2' after its field rename; this breaks README examples like &lt;Language \[pt-BR\]&gt; and an untouched test calls this input.; the Judge (advisory) calls it suspicious: The result can no longer be printed (AttributeError) where it used to give &lt;Language \[fr-FR-Latn\]&gt;; this is a regression the issue does not ask for, on an input an untouched test uses.

### Changes no test noticed (3 of 7; the rest in receipt.json)
- `babelfish/language.py:58`: `     if country is None: ` → `     if not country: ` made no test fail; no input tried behaved differently from the fix (`m-b100e5a152ea`)
- `babelfish/language.py:67`: `     if script is None: ` → `     if not script: ` made no test fail; no input tried behaved differently from the fix (`m-91241a1d1c7a`)
- `babelfish/language.py:156`: `         if len(language_subtag) == 2: ` → `         if len(language_subtag) <= 2: ` made no test fail; behaves differently from the fix on inputs no test checks (`m-90b6a2a6577b`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack Country.\_\_post\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Language.\_\_bool\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Language.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Language.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; and 10 more in receipt.json
- **Model use:** 9 calls, 76,210 input and 12,123 output tokens, cost $0.4954 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 1.25 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.28 s: 3 changed module(s) imported from the copies (6 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 6.16 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 54.86 s: the tests killed 0 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 8.77 s: 15 confirmed: tests/test\_converters.py::test\_converter\_opensubtitles, tests/test\_country.py::test\_eq, tests/test\_country.py::test\_ne, tests/test\_country.py::test\_hash\_eq, tests/test\_country.py::test\_hasattr\_name and 10 more
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 1.54 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `partial`, 52.81 s: 203 input(s) compared on 1 function(s): 9 changed with the fix; not complete: Country.\_\_post\_init\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `none_found`, 23.12 s: no counterexample found in 27 inputs against 15 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
- `blind`: `fails_differently`, 8.23 s: attempt 1: fails after the fix too, but differently
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### More counterexamples
- Regression: `tests/test_country.py::test_hasattr_alpha2` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert False)
- Regression: `tests/test_country.py::test_pickle` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: alpha2)
- Regression: `tests/test_language.py::test_eq_with_country` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: alpha2)
- Regression: `tests/test_language.py::test_ne_with_country` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: alpha2)
- Regression: `tests/test_language.py::test_hash` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert -7925703438484343201 == 6342665614943625794)
- Regression: `tests/test_language.py::test_pickle[language1]` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: alpha2)
- Regression: `tests/test_language.py::test_pickle[language3]` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: alpha2)
- Regression: `tests/test_language.py::test_str_ietf_format` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: alpha2)
- Regression: `tests/test_language.py::test_fromietf_with_country_and_script` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: alpha2)
- Regression: `tests/test_language.py::test_fromietf_with_country_and_no_script` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AttributeError: alpha2)
#### Break My Fix targets
- `babelfish.language.to_country` (`babelfish/language.py`): 2 inputs
- `babelfish.language.to_script` (`babelfish/language.py`): 2 inputs
- `babelfish.language.Language.fromietf` (`babelfish/language.py`): 16 inputs
- `babelfish.language.Language.alpha3` (`babelfish/language.py`): 5 inputs
- `babelfish.script.Script.code` (`babelfish/script.py`): 2 inputs
#### More changes no test noticed
- `babelfish/language.py:56`: `     if isinstance(country, Country): ` → `     if not (isinstance(country, Country)): ` made no test fail; behaves differently from the fix on inputs no test checks (`m-7dee587bcdad`)
- `babelfish/country.py:56`: `@dataclass(frozen=True)` → `@dataclass(frozen=False)` made no test fail; not compared with the fix (`m-cfc1e92e28b4`)
- `babelfish/country.py:70`: `         if self.country not in COUNTRIES: ` → `         if self.country in COUNTRIES: ` made no test fail; not compared with the fix (`m-cfa20cd066a6`)
- `babelfish/language.py:173`: `                 break ` → `                 continue ` made no test fail; no input tried behaved differently from the fix (`m-689a753486c2`)
#### Fix lines run (report only)
- repro: 32 of 58 fix lines run
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
- Break My Fix could not attack Country.\_\_post\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Language.\_\_bool\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Language.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Language.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Script.\_\_post\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Country.\_\_post\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Language.\_\_bool\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Language.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Language.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Script.\_\_post\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare to\_country: new with the fix: nothing to compare
- the behaviour diff could not compare to\_script: new with the fix: nothing to compare
- the behaviour diff could not compare Script.code: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 10 functions were shown
- guard: 5 of the 8 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 37 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: only the first 8 of 19 functions were shown
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T20:28:57+00:00, issue sha256 `f6a175555206d2b505515c94a4f32de1eca268f5e1c0abdb7a2e1ef10e1c1e75`

</details>
