## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the original issue, found no regressions, and confirmed the fix lines are covered, but Break My Fix found a counterexample: Language.fromietf('00') raises LanguageReverseError in the fixed code. Check whether that error is the expected behaviour for an invalid IETF tag or a crash the fix introduced, and note that the guard stage reported the fix as not guarded.

**Why this level:** Break My Fix finding 1: an input that breaks babelfish.language.Language.fromietf

**Issue:** Immutability issues · **Repo:** testbed · **Base** `tf-base` (`7584c2a`) → **head** `tf-agent_wrong` (`e138fa7`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `fromietf(ietf='00')` → `raises LanguageReverseError: '00'` (before the fix: `raises LanguageReverseError: '00'`); breaks **returns\_language\_instance**: “:return: the corresponding :class:\`Language\` instance” (docstring); test: `findings/finding_1.py`

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.333, mutants 9, killed 3, survived 6 |
| `regressions` | `none_found` | compared 49, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 49 |
| `behaviour_diff` | `partial` | inputs compared 204, changes 5, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 37, properties counted 6, findings 1 |
| `integrity` | `clean` | flags 0 |

### Behaviour changes
- `babelfish.language.Language.fromietf` (`value`, 5 inputs): `returns <Language [fr-FR-Latn]>` → `returns <Language [fr-FR-Latn]>`; the Judge (advisory) calls it intended: Same alpha3/country/script; the only difference is the \_\_slots\_\_ layout with a cached \_hash, which is how the issue's request for immutable, hash-stable objects is implemented.; the Judge (advisory) calls it intended: Logical value unchanged (eng with script Latn); the slot-based layout with \_hash follows from the issue's request for true immutability.; the Judge (advisory) calls it intended: Same language, country and script; fromietf now builds a new instance instead of mutating one, as the immutability the issue asks for requires.; the Judge (advisory) calls it intended: Same 'fra' Language with no country or script; only the immutable slot representation differs, per the issue.; the Judge (advisory) calls it intended: Same 'fra' Language; the representation change (slots plus \_hash) is the immutability refactor the issue requests.

### Changes no test noticed (3 of 7; the rest in receipt.json)
- `babelfish/language.py:152`: `                 country = Country(subtag.upper()) ` → `                 country = Country(subtag) ` made no test fail; no input tried behaved differently from the fix (`m-5ee141576d4c`)
- `babelfish/language.py:154`: `                 script = Script(subtag.capitalize()) ` → `                 script = Script(subtag) ` made no test fail; no input tried behaved differently from the fix (`m-09e3788c6bdb`)
- `babelfish/language.py:155`: `             if script is not None: ` → `             if script is not None and not subtags: ` made no test fail; no input tried behaved differently from the fix (`m-7472b63e98f3`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack Country.\_\_hash\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Country.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Country.\_\_setattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Country.\_\_setstate\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; and 21 more in receipt.json
- **Model use:** 8 calls, 56,170 input and 10,095 output tokens, cost $0.3922 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 2.49 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.86 s: 3 changed module(s) imported from the copies (6 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 16.27 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 100.9 s: the tests killed 3 of 9 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 2.15 s: none of the 49 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 2.61 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `partial`, 65.45 s: 204 input(s) compared on 1 function(s): 5 changed with the fix; not complete: Country.\_\_hash\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `found`, 98.18 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `babelfish.language.Language.fromietf` (`babelfish/language.py`): 37 inputs
#### More changes no test noticed
- `babelfish/language.py:146`: `         country = language_obj.country ` → `         country = None ` made no test fail; no input tried behaved differently from the fix (`m-8ae74615d9e8`)
- `babelfish/language.py:172`: `         object.__setattr__(self, '_hash', None) ` → `         object.__setattr__(self, '_hash', 0) ` made no test fail; no input tried behaved differently from the fix (`m-558ebcc5b913`)
- `babelfish/script.py:68`: `         object.__setattr__(self, '_hash', None) ` → `         object.__setattr__(self, '_hash', 0) ` made no test fail; not compared with the fix (`m-04652c136a5d`)
- `babelfish/country.py:77`: `         msg = f"can't set attribute '{name}' on immutable Co... ` → `         return None ` made no test fail; not compared with the fix (`m-eb24adde2072`)
#### Fix lines run (report only)
- repro: 17 of 49 fix lines run
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
- Break My Fix could not attack Country.\_\_hash\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Country.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Country.\_\_setattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Country.\_\_setstate\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Language.\_\_hash\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Language.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Language.\_\_setattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Language.\_\_setstate\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Script.\_\_hash\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Script.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Script.\_\_setattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- Break My Fix could not attack Script.\_\_setstate\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Country.\_\_hash\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Country.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Country.\_\_setattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Country.\_\_setstate\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Language.\_\_hash\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Language.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Language.\_\_setattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Language.\_\_setstate\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Script.\_\_hash\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Script.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Script.\_\_setattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
- the behaviour diff could not compare Script.\_\_setstate\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet
#### Notes
- reproduce: only the first 8 of 13 functions were shown
- guard: only the first 10 of 23 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-03T16:59:19+00:00, issue sha256 `f6a175555206d2b505515c94a4f32de1eca268f5e1c0abdb7a2e1ef10e1c1e75`

</details>
