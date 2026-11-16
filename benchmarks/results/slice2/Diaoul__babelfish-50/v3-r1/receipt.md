## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier found 15 regressions: tests that passed before the fix now fail, covering Country equality, hashing, attribute access and pickling, Language equality, hashing, pickling and IETF formatting/parsing, and the OpenSubtitles converter; the bug reproduced but the fix's tests did not guard it. Look first at the Country and Language equality/hash failures and the Language.fromietf behaviour…

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
| `guard` | `not_guarded` | kill rate 0\.5, mutants 8, killed 4, survived 4 |
| `regressions` | `found` | compared 49, regressions 15, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 58 |
| `behaviour_diff` | `partial` | inputs compared 203, changes 8, groups 3 |
| `break_my_fix` | `none_found` | targets 5, inputs tried 27, properties counted 15, findings 0 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `babelfish.language.Language.fromietf` (`message`, 3 inputs): `raises ValueError: '' is not a valid language` → `raises ValueError: '1' is not a valid script`; the Judge (advisory) calls it suspicious: The issue only asks for immutability. Deferring language validation until after the subtags are parsed changes which error is reported for an invalid language subtag, and nothing asks for that.; the Judge (advisory) calls it suspicious: Same deferred validation: the invalid language '' is now hidden behind a script error. Neither the issue nor the fromietf docstring asks for a different error.; the Judge (advisory) calls it suspicious: The invalid language subtag is now reported as an invalid country instead. This reorders validation errors, which goes beyond the immutability the issue requests.
- `babelfish.language.Language.fromietf` (`value`, 3 inputs): `returns <Language [en-Latn]>` → `returns <Language [en-Latn]>`; the Judge (advisory) calls it intended: The issue asks for frozen dataclasses and accepts a breaking change. The same language and script are parsed; only the internal field name changed (alpha3 to language), and alpha3 stays available as a property.; the Judge (advisory) calls it intended: The parsed value is the same Language('fra'). The field rename comes from the dataclass conversion the issue asks for ('making use of ... dataclasses frozen options').; the Judge (advisory) calls it intended: The parsed value is the same Language('fra'). Only the dataclass field naming differs, which follows from the immutability rewrite the issue requests.
- `babelfish.language.Language.fromietf` (`value`, 2 inputs): `returns <Language [fr-FR-Latn]>; left module data as babelfi...` → `returns <unprintable Language: AttributeError>; left module ...`; the Judge (advisory) calls it suspicious: The returned Language can no longer be printed (AttributeError), likely because Country lost its alpha2 attribute. This breaks the README's '&lt;Language \[fr-FR\]&gt;' output and an untouched project test calls this input.; the Judge (advisory) calls it suspicious: The returned Language with a country and script is now unprintable (AttributeError). This is a regression the issue never asks for, it contradicts the README repr examples, and an untouched project test calls this input.

### Changes no test noticed (3 of 7; the rest in receipt.json)
- `babelfish/language.py:166`: `                 country_subtag = Country(subtag.upper()) ` → `                 country_subtag = Country(subtag) ` made no test fail; behaves differently from the fix on inputs no test checks (`m-09439349340e`)
- `babelfish/language.py:168`: `                 script_subtag = Script(subtag.capitalize()) ` → `                 script_subtag = Script(subtag) ` made no test fail; behaves differently from the fix on inputs no test checks (`m-1773013a135e`)
- `babelfish/language.py:169`: `             if script_subtag is not None: ` → `             if script_subtag is None: ` made no test fail; behaves differently from the fix on inputs no test checks (`m-aa638b33e457`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack Country.\_\_post\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Language.\_\_bool\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Language.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Language.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; and 10 more in receipt.json
- **Model use:** 8 calls, 69,708 input and 11,936 output tokens, cost $0.4827 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.44 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.9 s: 3 changed module(s) imported from the copies (6 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 15.62 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 94.21 s: the tests killed 4 of 8 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 14.03 s: 15 confirmed: tests/test\_converters.py::test\_converter\_opensubtitles, tests/test\_country.py::test\_eq, tests/test\_country.py::test\_ne, tests/test\_country.py::test\_hash\_eq, tests/test\_country.py::test\_hasattr\_name and 10 more
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.55 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `partial`, 74.97 s: 203 input(s) compared on 1 function(s): 8 changed with the fix; not complete: Country.\_\_post\_init\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `none_found`, 116.96 s: no counterexample found in 27 inputs against 15 properties
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.03 s: nothing suspicious in the fix's test or source changes
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
- `babelfish/language.py:184`: `         if name.startswith('_'): ` → `         if name.startswith('__'): ` made no test fail; no input tried behaved differently from the fix (`m-1a644ef0e8d6`)
- `babelfish/country.py:56`: `@dataclass(frozen=True)` → `@dataclass(frozen=False)` made no test fail; not compared with the fix (`m-cfc1e92e28b4`)
- `babelfish/country.py:70`: `         if self.country not in COUNTRIES: ` → `         if self.country in COUNTRIES: ` made no test fail; not compared with the fix (`m-cfa20cd066a6`)
- `babelfish/language.py:56`: `     if isinstance(country, Country): ` → `     if not (isinstance(country, Country)): ` made no test fail; behaves differently from the fix on inputs no test checks (`m-7dee587bcdad`)
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
- guard: only the first 10 of 34 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T16:53:48+00:00, issue sha256 `f6a175555206d2b505515c94a4f32de1eca268f5e1c0abdb7a2e1ef10e1c1e75`

</details>
