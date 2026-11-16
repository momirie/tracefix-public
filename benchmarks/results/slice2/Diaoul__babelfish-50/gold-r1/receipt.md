## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier found counterexamples: two previously passing tests (tests/test\_country.py::test\_hash\_eq and tests/test\_language.py::test\_hash) now fail, and Language.fromietf raises errors on inputs like '\_\_' (LanguageReverseError) and 'script' (ValueError), with some of its error-message changes labelled suspicious. Look first at the two hash/equality test regressions to see whether the new immuta…

**Why this level:** Break My Fix finding 1: an input that breaks babelfish.language.Language.fromietf; Break My Fix finding 2: an input that breaks babelfish.language.Language.fromietf; regression: tests/test\_country.py::test\_hash\_eq passed before the fix and fails after it; regression: tests/test\_language.py::test\_hash passed before the fix and fails after it

**Issue:** Immutability issues · **Repo:** testbed · **Base** `tf-base` (`7584c2a`) → **head** `tf-gold` (`f99f616`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `fromietf(ietf='__')` → `raises LanguageReverseError: '__'` (before the fix: `raises LanguageReverseError: '__'`); breaks **deterministic\_equal**: “I want to have true immutability of babelfish objects” (issue); test: `findings/finding_1.py`
2. `fromietf(ietf='script')` → `raises ValueError: 'script' is not a valid language` (before the fix: `raises ValueError: 'script' is not a valid language`); breaks **deterministic\_equal**: “I want to have true immutability of babelfish objects” (issue); 3 more inputs break it the same way; test: `findings/finding_2.py`
3. Regression: `tests/test_country.py::test_hash_eq` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert -455832130340910505 == -8328537658613580243)
4. Regression: `tests/test_language.py::test_hash` passed before the fix and fails after it (passed before the fix (also when its file ran alone); fails after it in all 4 attempts: AssertionError: assert -7925703438484343201 == 6342665614943625794)

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.375, mutants 8, killed 3, survived 5 |
| `regressions` | `found` | compared 49, regressions 2, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 64 |
| `behaviour_diff` | `partial` | inputs compared 203, changes 8, groups 2 |
| `break_my_fix` | `found` | targets 6, inputs tried 62, properties counted 21, findings 2 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `babelfish.language.Language.fromietf` (`value`, 5 inputs): `returns <Language [fr-FR-Latn]>` → `returns <Language [fr-FR-Latn]>`; the Judge (advisory) calls it intended: The issue asks for immutability via frozen dataclasses and accepts a breaking change; only the internal field layout changed (alpha3 became language), and the parsed value is the same fr-FR.; the Judge (advisory) calls it intended: Same frozen-dataclass refactor the issue requests; the parsed eng-Latn language is unchanged, only the stored field names differ.; the Judge (advisory) calls it intended: Same frozen-dataclass refactor the issue requests; the parsed fra-FR-Latn value is unchanged, only the stored field names differ.; the Judge (advisory) calls it intended: Same frozen-dataclass refactor the issue requests; it still parses to 'fra', only the stored field names differ.; the Judge (advisory) calls it intended: Same frozen-dataclass refactor the issue requests; it still parses to 'fra', only the stored field names differ.
- `babelfish.language.Language.fromietf` (`message`, 3 inputs): `raises ValueError: '' is not a valid language` → `raises ValueError: '1' is not a valid script`; the Judge (advisory) calls it suspicious: The fix now validates the language only after parsing the other subtags, so a different error is reported for an invalid language; the immutability issue does not ask to change validation order or error messages.; the Judge (advisory) calls it suspicious: Same reordering of validation: the script error now masks the invalid-language error, which nothing in the issue or docstring requests.; the Judge (advisory) calls it suspicious: Same reordering of validation: a country error now replaces the invalid-language error, which goes beyond the immutability request.

### Changes no test noticed (3 of 7; the rest in receipt.json)
- `babelfish/language.py:166`: `                 country_subtag = Country(subtag.upper()) ` → `                 country_subtag = Country(subtag) ` made no test fail; behaves differently from the fix on inputs no test checks (`m-09439349340e`)
- `babelfish/language.py:168`: `                 script_subtag = Script(subtag.capitalize()) ` → `                 script_subtag = Script(subtag) ` made no test fail; behaves differently from the fix on inputs no test checks (`m-1773013a135e`)
- `babelfish/language.py:184`: `         if name.startswith('_'): ` → `         if name.startswith('__'): ` made no test fail; no input tried behaved differently from the fix (`m-1a644ef0e8d6`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack Country.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Country.\_\_post\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Language.\_\_bool\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Language.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; and 12 more in receipt.json
- **Model use:** 8 calls, 74,583 input and 15,192 output tokens, cost $0.5656 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.55 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.08 s: 3 changed module(s) imported from the copies (6 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 14.06 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 90.45 s: the tests killed 3 of 8 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `found`, 11.82 s: 2 confirmed: tests/test\_country.py::test\_hash\_eq, tests/test\_language.py::test\_hash
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.49 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `partial`, 60.24 s: 203 input(s) compared on 1 function(s): 8 changed with the fix; not complete: Country.\_\_getattr\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `found`, 169.08 s: 2 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - 2 more command(s) in receipt.json
- `integrity`: `clean`, 0.03 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `babelfish.country.Country.alpha2` (`babelfish/country.py`): 3 inputs
- `babelfish.language.to_country` (`babelfish/language.py`): 7 inputs
- `babelfish.language.to_script` (`babelfish/language.py`): 7 inputs
- `babelfish.language.Language.fromietf` (`babelfish/language.py`): 40 inputs
- `babelfish.language.Language.alpha3` (`babelfish/language.py`): 3 inputs
- `babelfish.script.Script.code` (`babelfish/script.py`): 2 inputs
#### More changes no test noticed
- `babelfish/language.py:173`: `                 break ` → `                 continue ` made no test fail; no input tried behaved differently from the fix (`m-689a753486c2`)
- `babelfish/country.py:94`: `         if name.startswith('_'): ` → `         if name.startswith('__'): ` made no test fail; not compared with the fix (`m-b449025ac1c5`)
- `babelfish/country.py:56`: `@dataclass(frozen=True)` → `@dataclass(frozen=False)` made no test fail; not compared with the fix (`m-cfc1e92e28b4`)
- `babelfish/country.py:70`: `         if self.country not in COUNTRIES: ` → `         if self.country in COUNTRIES: ` made no test fail; not compared with the fix (`m-cfa20cd066a6`)
#### Fix lines run (report only)
- repro: 35 of 64 fix lines run
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
- Break My Fix could not attack Country.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Country.\_\_post\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Language.\_\_bool\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Language.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Language.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Script.\_\_post\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Country.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Country.\_\_post\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Language.\_\_bool\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Language.\_\_getattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Language.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Script.\_\_post\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare to\_country: new with the fix: nothing to compare
- the behaviour diff could not compare to\_script: new with the fix: nothing to compare
- the behaviour diff could not compare Script.code: new with the fix: nothing to compare
#### Notes
- reproduce: only the first 8 of 12 functions were shown
- guard: only the first 10 of 41 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T16:47:49+00:00, issue sha256 `f6a175555206d2b505515c94a4f32de1eca268f5e1c0abdb7a2e1ef10e1c1e75`

</details>
