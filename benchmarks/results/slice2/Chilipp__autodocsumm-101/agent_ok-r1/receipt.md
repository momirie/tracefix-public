## Fix Receipt: L2 (L1, and the tests notice the fix being undone)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): A test reproduced the alias-expansion bug (failing before the fix, passing after) and fails again when the fix is reverted or broken, with no regressions found, but behaviour comparison was inconclusive because \_is\_class\_alias is new and add\_content had no comparable inputs. Next, review how AutoSummClassDocumenter.add\_content and the new \_is\_class\_alias decide when a class attribute is an alias,…

**Why this level:** the bug was reproduced: a test fails before the fix and passes after it; the tests guard the fix: they fail when it is reverted or broken; not L3: AutoSummClassDocumenter.\_is\_class\_alias: before the fix it was not a method defined in class AutoSummClassDocumenter; not L3: AutoSummClassDocumenter.add\_content: no input could be compared

**Issue:** Alias Expands Nested Class Documentation · **Repo:** testbed · **Base** `tf-base` (`354e67b`) → **head** `tf-agent_ok` (`7ace577`)\
**Isolation:** strict (bubblewrap works)

### Counterexamples
None found.

### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 0\.833, mutants 6, killed 5, survived 1 |
| `regressions` | `none_found` | compared 22, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 9 |
| `behaviour_diff` | `inconclusive` | inputs compared 0, changes 0, groups 0 |
| `break_my_fix` | `inconclusive` | targets 2, inputs tried 0, properties counted 5, findings 0 |
| `integrity` | `clean` | flags 0 |

### Changes no test noticed (3 of 7; the rest in receipt.json)
- `autodocsumm/__init__.py:433`: `             hasattr(self, 'objpath') and len(self.objpath) >... ` → `             hasattr(self, 'objpath') and len(self.objpath) >... ` made no test fail; not compared with the fix (`m-76e5f4930488`)
- `autodocsumm/__init__.py:421`: `             self.add_autosummary(relative_ref_paths=True) ` → `             self.add_autosummary(relative_ref_paths=False) ` made no test fail; not compared with the fix (`m-cd5f1236087f`)
- `autodocsumm/__init__.py:431`: `         if (hasattr(self, 'parent') and self.parent is not N... ` → `         if (hasattr(self, 'parent') or self.parent is not No... ` made no test fail; not compared with the fix (`m-70feddeabb30`)

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 6 calls, 33,751 input and 4,836 output tokens, cost $0.2078 (estimate at list prices)

<details>
<summary>Run log</summary>

#### Stages
- `environment`: `ok`, 4.62 s: base suite passed
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `import_check`: `ok`, 3.43 s: 1 changed module(s) imported from the copies (2 imports in all)
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `reproduce`: `reproduced`, 21.66 s: attempt 1: fails before the fix and passes after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `guard`: `guarded`, 108.55 s: the reproduction test fails with the fix reverted, and the tests killed 5 of 6 mutants
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no`
- `regressions`: `none_found`, 4.68 s: none of the 22 untouched tests that passed before the fix fails after it
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no --continue...`
- `fix_line_coverage`: `ok`, 3.22 s: report only: which fix lines the tests run
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `behaviour_diff`: `inconclusive`, 19.03 s: nothing was compared: AutoSummClassDocumenter.\_is\_class\_alias: before the fix it was not a method defined in class AutoSummClassDocumenter
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no -s tests/t...`
- `break_my_fix`: `inconclusive`, 41.09 s: the attack ran no input
  - `python -c import sys; sys.path[:1] == [''] and sys.path.pop(0); import runpy; runpy.run_module('pytest', run_name='__main__', alter_sys=True) -q -p no:cacheprovider --tb=long -rN --color=no tests/test...`
- `integrity`: `clean`, 0.02 s: nothing suspicious in the fix's test or source changes
#### Break My Fix targets
- `autodocsumm.AutoSummClassDocumenter.add_content` (`autodocsumm/__init__.py`): not attacked (no property to check it against)
- `autodocsumm.AutoSummClassDocumenter._is_class_alias` (`autodocsumm/__init__.py`): 0 inputs
#### More changes no test noticed
- `autodocsumm/__init__.py:431`: `         if (hasattr(self, 'parent') and self.parent is not N... ` → `         if (hasattr(self, 'parent') and self.parent is not N... ` made no test fail; not compared with the fix (`m-917566ee9cf4`)
- `autodocsumm/__init__.py:432`: `             hasattr(self, 'object') and isinstance(self.obje... ` → `             hasattr(self, 'object') or isinstance(self.objec... ` made no test fail; not compared with the fix (`m-8df462c824f0`)
- `autodocsumm/__init__.py:432`: `             hasattr(self, 'object') and isinstance(self.obje... ` → `             hasattr(self, 'object') and isinstance(self.obje... ` made no test fail; not compared with the fix (`m-a01e10a22048`)
- `autodocsumm/__init__.py:433`: `             hasattr(self, 'objpath') and len(self.objpath) >... ` → `             hasattr(self, 'objpath') or len(self.objpath) > 1): ` made no test fail; not compared with the fix (`m-eee4e0bfab40`)
#### Fix lines run (report only)
- repro: 9 of 9 fix lines run
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
- guard: only the first 10 of 16 rule mutants were run
- behaviour\_diff: the reproduction test's calls are not proven on Python 3.9.21: the call recorder places calls by line and column, which Python gives from 3.11 on, so none of them counts as compared
#### This receipt
- models: reproducer claude-sonnet-5-5, mutator claude-sonnet-5-5, adversary claude-opus-5-5, judge claude-opus-5-5; effort medium; at most 40 calls and 500,000 tokens
- Tracefix 0.0.1, receipt schema 1, created 2026-10-22T17:28:55+00:00, issue sha256 `513a925c0b6fa6f4ef2c7213adca09819b2a86a70650322ba27537f0a34fea64`

</details>
