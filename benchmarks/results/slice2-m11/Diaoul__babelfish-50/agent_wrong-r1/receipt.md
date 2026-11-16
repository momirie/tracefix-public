## Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The verifier reproduced the original issue and found no regressions, but Break My Fix found an input that breaks the fixed code: Language.fromietf('İ') raises LanguageReverseError: 'i̇'. Look first at how fromietf handles case conversion of non-ASCII input such as the Turkish dotted capital I, since lowercasing it yields a two-character string that the reverse lookup rejects; note also that the f…

**Why this level:** Break My Fix finding 1: an input that breaks babelfish.language.Language.fromietf

**Issue:** Immutability issues · **Repo:** testbed · **Base** `tf-base` (`7584c2a`) → **head** `tf-agent_wrong` (`e138fa7`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
1. `fromietf(ietf='İ')` → `raises LanguageReverseError: 'i̇'` (before the fix: `raises LanguageReverseError: 'i̇'`); breaks **returns\_language\_instance**: “:return: the corresponding :class:\`Language\` instance” (docstring); 3 more inputs break it the same way; test: `findings/finding_1.py`; **Doubt (still counted):** this may be the code's own refusal: a `raise` in the project, same before the fix

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 3 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `not_guarded` | kill rate 0\.0, mutants 3, killed 0, survived 3 |
| `regressions` | `none_found` | compared 49, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 49 |
| `behaviour_diff` | `partial` | inputs compared 204, changes 6, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 46, properties counted 6, findings 1 |
| `integrity` | `clean` | flags 0 |
| `blind` | `reproduced` | attempts 1, report only True |

**Rule mutants by kind (report only):** body: 2 of 3 killed; compare: 1 of 1 killed; constant: 2 of 2 killed; membership: 2 of 2 killed; drop\_call: 2 of 2 killed; no place for logic, negate\_if, arithmetic, loop, reraise

### Behaviour changes
- `babelfish.language.Language.fromietf` (`value`, 6 inputs): `returns <Language [fr-FR-Latn]>` → `returns <Language [fr-FR-Latn]>`; the Judge (advisory) calls it intended: Same alpha3/country/script as before; the only difference is the internal \_\_slots\_\_/\_hash state that the issue's request for true immutability calls for.; the Judge (advisory) calls it intended: Logical value (eng, Latn script) is unchanged; only the slot-based immutable representation, which the issue asks for, differs.; the Judge (advisory) calls it intended: Same fra/FR/Latn result; the difference is only the immutable slot layout the issue requests, not the parsed value.; the Judge (advisory) calls it intended: Still returns fra with no country or script; the added \_hash slot is an artefact of the immutability the issue asks for.; the Judge (advisory) calls it intended: Same fra value as before; only the internal immutable representation that the issue requests has changed.

### Changes no test noticed (3 of 4; the rest in receipt.json)
- `babelfish/language.py:152`: `                 country = Country(subtag.upper()) ` → `                 country = Country(subtag) ` made no test fail; no input tried behaved differently from the fix (`m-5ee141576d4c`)
- `babelfish/language.py:154`: `                 script = Script(subtag.capitalize()) ` → `                 script = Script(subtag) ` made no test fail; no input tried behaved differently from the fix (`m-09e3788c6bdb`)
- `babelfish/language.py:155`: `             if script is not None: ` → `             if script is not None and not subtags: ` made no test fail; no input tried behaved differently from the fix (`m-7472b63e98f3`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; Break My Fix could not attack Country.\_\_hash\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Country.\_\_init\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Country.\_\_setattr\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; Break My Fix could not attack Country.\_\_setstate\_\_: a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet; and 21 more in receipt.json
- **Model use:** 9 calls, 64,010 input and 10,282 output tokens, cost $0.4094 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 1.28 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 2.19 s: 3 changed module(s) imported from the copies (6 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 6.11 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `not_guarded`, 51.29 s: the tests killed 0 of 3 mutants; 80% is needed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 1.31 s: none of the 49 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 1.63 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `partial`, 34.22 s: 204 input(s) compared on 1 function(s): 6 changed with the fix; not complete: Country.\_\_hash\_\_: not compared (a special method (such as \_\_init\_\_ or \_\_eq\_\_): not called yet)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `found`, 18.74 s: 1 finding(s), each proven by a failing repro file
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - 1 more command(s) in receipt.json
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
- `blind`: `reproduced`, 10.77 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
#### Break My Fix targets
- `babelfish.language.Language.fromietf` (`babelfish/language.py`): 46 inputs
#### More changes no test noticed
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
- guard: 6 of the 9 mutants were not run: the tests could no longer reach 80% even if they killed them all
- guard: only the first 10 of 46 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
- blind: only the first 8 of 13 functions were shown
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-11-06T20:31:40+00:00, issue sha256 `f6a175555206d2b505515c94a4f32de1eca268f5e1c0abdb7a2e1ef10e1c1e75`

</details>
