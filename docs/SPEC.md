# Tracefix MVP specification

This is the target design. Built so far (see `docs/ROADMAP.md`): all of §2 to §5. Since M8,
`tracefix verify` runs every stage in order and writes the receipt (2.8); since M9 the GitHub
Action (§5) runs it on pull requests.
Points marked *(Decided in Mx)* were settled during that milestone; points marked *Open* are not settled yet.

## 1. What it does

Given a repo, a base ref (before the fix), a head ref (with the fix) and an issue description,
Tracefix runs a fixed pipeline and emits a Fix Receipt.

```
Fix arrives → Reproduce → Confirm → Guard → Behaviour diff → Break My Fix → Integrity audit → Receipt
```

If reproduction fails, the pipeline still runs Integrity and Break My Fix, but the receipt can be at
most L0 (a valid finding or an integrity flag still makes it `COUNTEREXAMPLE`, see 2.8).

*(Decided in M8; `pipeline.py`.)* The exact order:
```
resolve refs → settings (tracefix.yml at base, 2.1) → copies → diff scope → environment check
→ import origin check → [replay of the last receipt, with `--previous` (2.10)] → Reproduce → Guard → no-regression check (2.9) → fix-line coverage
(report only) → Behaviour diff (+ Judge labels) → Break My Fix → Integrity → ladder → receipt
(+ Judge summary) → files
```
- Every stage runs whatever the earlier ones found; there is no early exit on a counterexample, so
  the receipt lists every problem at once. One `LLMClient` (one budget) per run; one progress line
  per stage on stderr.
- Each stage gets a record: name, its own status value, reason, duration, result, the model
  problems hit while it ran (§3), and `error` when Tracefix's own code raised. A stage that raises
  is `error` with no evidence from it, and the run goes on; without a reproduction result Guard,
  fix-line coverage and Integrity are `skipped` with the reason.
- **Run statuses:**

  | status | when | level |
  |---|---|---|
  | `ok` | the stages ran (any may be skipped, inconclusive or invalid) | from the ladder (2.8) |
  | `ENVIRONMENT_ERROR` | the base suite can't run (pytest exit 2/3/4, timeout), or a changed module imports from outside the copy (2.1) | L0 |
  | `INVALID` | tampering during the environment or import origin check: nothing can run safely | L0 |
  | `ERROR` | the fix's diff can't be read (a crafted `..` tree entry, an expression too deep to parse), or the environment or origin check itself raised | L0 |

  Problems before any copy exists (not a git repo, unknown ref, base and head holding the same
  files, bad settings, an empty issue) print a message and exit 2, with no receipt.

## 2. Pipeline stages

### 2.1 Workspace
- Export plain copies of the base and head commits, each into its own random temp folder (both named
  `repo`), straight from git objects: no checkout, hooks, filters or `.gitattributes`, and no `.git`
  link back to the user's repository. Never touch the user's working copy. *(Decided in M3.5;
  replaces worktrees.)*
- *(Decided in M8; `config.py`.)* Settings come from the defaults, then `tracefix.yml`, then
  command-line flags (each flag overrides one setting; `--model` one role). Every key is optional:
  ```yaml
  suite_timeout_seconds: 300   # time limit of one run of the whole suite (30 to 86,400)
  max_llm_calls: 40
  token_budget: 500000
  max_tokens: 16000            # per model answer (at most 20,000: calls are not streamed)
  effort: medium               # low | medium | high | xhigh | max
  models: {reproducer: claude-sonnet-5-5, adversary: claude-opus-5-5}
  pytest_plugins: [pytest_mock]
  ```
  - Read from the **base commit's** git objects, never head's: the fix under test can't change how
    it is verified. If the fix changes `tracefix.yml`, the receipt says the base version was used.
    `--config FILE` replaces it (to try settings before committing them).
  - Untrusted text: PyYAML's safe loader, files over 64 KB, anchors and aliases (a few lines could
    expand to gigabytes), duplicate keys and non-UTF-8 refused; strict validation (unknown keys
    are rejected with the allowed ones listed). The early draft's `setup`, `test` and
    `timeout_seconds` get their own messages: there is no setup command, pytest is always the
    test command, and a whole-run time budget would make results depend on machine speed.
  - Settings shape what the models propose and how long runs may take; none decides a verdict.
- *(Decided in M8 by the developer: the project's own environment.)* Tracefix is installed into the
  project's environment (`uv add --dev tracefix`) and runs from it, so runs use that
  interpreter, with the project's dependencies, pytest and Hypothesis; the tamper watch and the
  sandbox cover that environment. There is no setup command; M10's benchmark defines its own
  environment.
- *(M10 part 2, plan B1-B7.)* **`--python PATH`** (command line only: a path belongs to the
  machine, so `tracefix.yml` can't set it) names the project's interpreter, 3.9 or newer; Tracefix
  stays on 3.11+ in its own environment. Default: Tracefix's own interpreter, as before.
  - `interpreter.py` checks it once before any stage: one run with `-I`, a fixed script, the
    allowlisted environment and a timeout reports its version, prefixes, stdlib and site-packages
    folders and its pytest and Hypothesis versions (parsed strictly, size-capped). Below 3.9 or
    without pytest: `ENVIRONMENT_ERROR`, in fixed words. The receipt's `isolation.python` names
    its version.
  - Every run uses it. 3.11+ starts pytest with `-P`; 3.9/3.10 have no `-P`, so a fixed `-c`
    bootstrap drops `sys.path[0]` and runs pytest as `-m` would: a repo's `pytest.py` still can't
    replace the test runner.
  - Without Hypothesis there, or older than 6.141, Break My Fix and the behaviour diff are
    inconclusive (with the reason and the install command) before any model call; never a verdict.
  - Below 3.11 the Reproducer, mutator and adversary requests end with one fixed sentence naming
    that Python (from the interpreter check, never from repo text); at 3.11+ they are unchanged.
    The call recorder (2.5) needs column positions (3.11+), so below 3.11 the reproduction test's
    calls are reported unproven and none counts as compared (a note says so). This can only keep
    L3 closed, never open it.
  - **Import roots** (`workspace.package_roots`): the folders that hold the copies' top-level
    packages (a folder with `__init__.py` whose parent has none gives that parent; hidden, cache,
    venv, build and `tests` folders skipped; at most 20, shallowest first), and the copy itself or
    `src` when it directly holds a top-level module such as `slug.py` (the single-module layouts;
    test files and scripts such as `setup.py` don't count; verifier round 1 of M8). Every run loads a small
    Tracefix plugin (`-p tracefix_paths`, §4) that puts those folders of the copy under test into
    `sys.path` just before the first `site-packages`, so the copy's code wins over an installed or
    editable copy of the project (often the user's working copy), while the standard library and
    pytest can't be shadowed. Never `PYTHONPATH`: that would put a repo's `pytest.py` ahead of
    pytest.
  - **Import origin check** (`envcheck.py`, after the environment check): one watched run per copy
    imports every changed source module and reports its file. One that imports from outside the
    copy gives `ENVIRONMENT_ERROR`, naming the module and where it came from. One that fails to
    import is left to the stages. Scripts (`setup.py`, `conftest.py`, `noxfile.py`, `fabfile.py`)
    are never imported (that would run them). A changed source file with no import name (under no
    import root, e.g. in a namespace package) can't be checked: the stage says so and the receipt
    lists it under "not checked". The report comes from inside the run, so it catches
    misconfiguration, not hostile code.
  - `pytest_plugins` (config or `--pytest-plugin`) are passed with `-p` to every run, after
    Tracefix's own; plugin autoload stays off (*Decided in M2*).
- If the test command fails on base *before any changes* for reasons unrelated to the bug (import
  errors, missing deps), stop with status `ENVIRONMENT_ERROR`.
  *(Decided in M2:)* base-suite errors (pytest exit 2/3/4) or a timeout mean `ENVIRONMENT_ERROR`; test
  failures do not (they may be the bug). *(Decided in M3.5:)* this check runs watched like every other
  run (§4). *(Decided in M8:)* when the base suite errors (not a timeout), head's suite runs once,
  only to word the reason: "the code before the fix can't be collected, perhaps because of the bug
  itself" when head runs; "the environment Tracefix runs in lacks X" when both miss the same
  module. The level stays L0 either way.
- pytest always runs as `python -P -m pytest` with an allowlisted environment, `--tb=long`, `-rN`,
  `--color=no` and `COLUMNS=80`, and never reads configuration from outside the copy: `-c` the nearest
  pytest config found from the targets' folder up to the top of the copy (or an empty one), its folder
  as `--rootdir`, and `--confcutdir` at the copy. A test failure is rerun up to 3 times to tell
  `failed` from `flaky`.
  *(Decided in M2, M3 and M3.5.)*

### 2.2 Diff scope (deterministic)
- Changed files, hunks, and changed Python functions/methods (use `ast` on both sides; map line ranges).
- Separate source changes from test-file changes (`test_*.py`, `*_test.py`, `tests/`, `conftest.py`).

### 2.3 Reproduce + Confirm (Reproducer, LLM + runner)
- LLM input: issue text, fix diff, source of changed functions and their direct callers, existing test
  style example (one nearby test file, truncated).
- LLM output: one pytest file `test_tracefix_repro.py` (content only).
- Validation (deterministic): write it next to the repo's existing tests in both copies (never over an
  existing file), run only that file, remove it afterwards. *(Decided in M3:)*
  - Must FAIL on base with a real test failure: not a collection, import, syntax or setup error, and
    not an ImportError/NameError/"no attribute"/"unexpected keyword" raised in the test file itself
    (that usually means it uses something only the fix added).
  - Must PASS on head, with at least one test, none skipped, on three consecutive runs.
  - Rejected before running: files over 50k characters, files that don't compile, and files using
    names that can fake a result (e.g. `os._exit`, `subprocess`, `sys.argv`, `__file__`, any "junit"
    string). This is defence in depth only (open question 17).
- Up to 3 attempts; feed back the failure output each time, sanitised so it contains no machine paths
  and is identical on every OS.
- Result: `reproduced` | `not_reproduced` | `fix_does_not_fix` (fails on both) | `invalid`
  (tampering detected, §4; no verdict at all, *decided in M3.5*).
  *(Decided in M3:)* `fix_does_not_fix` only if no attempt reproduced AND the last attempt failed on
  base and head with the same set of failure signatures (test id, exception type, crash location
  file:line, from pytest's JUnit report), and the model had already been shown that result before it
  submitted or kept that test (a budget or output stop before then gives `not_reproduced`). A different
  failure on head is `not_reproduced`, never a counterexample. Remaining risk: a model can still
  write the same wrong expectation on every attempt; the receipt's reproduce entry names the
  model-written test as the oracle, so `fix_does_not_fix` is read as resting on it *(M8)*.
- *(Decided in M8:)* **The head pass is confirmed** when the repro file holds 2+ tests: each test
  that failed on base runs alone on base (it must still fail properly) and alone on head (it must
  pass), and the whole file runs once more on head in reverse order. Any miss makes that attempt
  `order_dependent` (not a reproduction), with a hint in the next attempt's feedback. Tests are
  found the way pytest collects by default. A one-test file runs nothing extra.
- *(Decided in M11:)* **The blind shadow test** is a stage of its own, `blind`, and **report only: no
  level reads its result.** It runs last, after every stage a level reads, so its model calls can't
  use up their call limit or token budget, and only when the main test reproduced the bug.
  - LLM input: the issue, the code the fix touches at base (each changed or removed function; for a
    method the fix added, its class), their direct callers at base, the style example and
    `pyproject.toml` at base. Never the diff, head's code or head's results. Which code to show still
    comes from the diff, and a fix's own test file can be the style example, at its base content.
  - One file, `test_tracefix_blind.py`, validated like the main test, with up to 2 attempts. Head
    runs only for a test that fails properly on base, and that attempt is the last: the model never
    sees a head result.
  - Result: `reproduced` | `fails_on_head` (some of it still fails the same way) |
    `fails_differently` | `head_not_clean` | `not_reproduced_on_base` | `not_run`. A model failure
    leaves it unfinished and changes nothing else. Tampering makes the stage `invalid`, as for the
    main test, and the ladder's tampering rule applies. The Judge's summary facts leave it out. The
    file is saved as `repro/test_tracefix_blind.py`.
  - *(Developer, 13 Nov 2026, after M11's rerun of slice 2:)* **it will set a level, in a step of
    its own after M11.** A receipt whose blind test still fails on head (`fails_on_head` or
    `fails_differently`) will be capped at L1, which changes what L2 means. Not built yet: M11's
    receipts only report it, and `ladder.py` does not read it. On slice 2's dev split, at L2 or
    above, it still fails on head for 4 of 6 wrong fixes and for 3 of 19 correct ones, each of
    those a blind test that guessed an internal the fix changed (`docs/BENCHMARK.md`). Every
    fixture's answer is checked before the rule is built, and the held_out split can reverse it.

### 2.4 Guard (deterministic + LLM mutations)
- The reverted and mutated trees are new copies, exported and watched like base and head (§4).
- Revert check: apply head, then reverse only the source (non-test) hunks of the fix. Run the repro test
  and the PR's own added/modified test files on the reverted code.
  - The repro test must fail.
  - If the PR adds or modifies tests and *all* of them still pass on the reverted code, the result is
    `not_guarded` whatever the mutation check says: the PR's test does not guard its fix.
    *(Decided in M1; see fixture `unguarded_test`.)*
  *(Decided in M4:)* the revert is done per file: every non-test file the fix changed gets its base
  content back (a file the fix added is removed), tests stay at head. The PR's tests are its added or
  modified test files that pytest collects by the repo's own `python_files` setting (not
  `conftest.py`/`__init__.py`) and whose run on head finds tests, each run on its own. A file
  catches the revert if a test that passed on head fails, or if a file that passed on head can no
  longer be collected (e.g. it imports a name only the fix added). The repro test must end `failed`.
  `inconclusive` instead of a verdict: the repro run on the reverted code ends neither passed nor
  failed; no PR file caught the revert and one of them ended unclean on it (a hang, a flaky run,
  an internal error); or none of the PR's files runs cleanly on head (with at least one test
  passing). Paths from the diff are only written to if the export wrote them, never through a link.
- Mutation check: LLM proposes 3–10 small edits to the *fixed lines* (e.g. flip a comparison, drop a
  None-check, change a boundary). Apply each as a text/AST edit to head; run the repro test, the PR's
  added/modified tests and the existing suite. A mutant is killed if any of them fails.
  Discard mutations that fail to import/compile (not counted). *(Decided in M1.)*
  - Record, for each mutant, which test sets killed it: `repro`, `pr_test`, `suite`.
  - Report the repro test's own kill rate separately from the combined kill rate.
  - *(Decided in M4 by the developer:)* the mutator is its own LLM role (`mutator`, Sonnet 5.5). It
    sees only head's numbered fixed lines: never the issue text, any test, or the code before the
    fix (which would be a ready-made easy kill), so it cannot aim at what the tests check.
    **Hygiene rules** (deterministic) decide which proposals count: the edit is on fixed lines only
    (measured on the result, line by line; an insertion needs a fixed line next to it), ≤ 5 lines
    and ≤ 300 characters; the file compiles; the code changes (not only layout) and is not the base
    code; no name, attribute or keyword that isn't already in the file as that kind; no added
    import, raise, assert, loop, `with`, `try`, `lambda`, `yield`/`await`, `global`/`nonlocal`,
    `del`, comprehension or definition; no call to a function (by name) more often than head does;
    no `**` or `<<`, division by a constant 0 (or `False`), arithmetic with `None`, or indexing an
    empty literal; no duplicate. At most two mutator calls (one follow-up listing the rejections);
    at most 10 mutants run.
  - *(M11, NOTES 24:)* the mutator is asked for 8–10 mutants (was 3–10); its one follow-up fires
    when fewer than 6 pass hygiene (was 3). The 3-mutant minimum and the 80% line are unchanged.
    **Early stop:** model mutants run in order, and the rest are left unrun once "not guarded" is
    certain: at least 3 valid mutants have run, and even if every remaining one were valid and
    killed the rate would stay under 80% (`guard.certain_not_guarded`). A remaining mutant that
    turned out discarded would only lower the rate, so the stop never changes the verdict (a
    property test checks `decide` on every outcome sequence). The unrun mutants are counted in
    Guard's evidence (`not_run`) and named in a note; rule mutants still run after them. What the
    stop does change is outside Guard: an unrun mutant can't survive, and surviving model
    mutants' replacement text seeds Break My Fix (2.6), so a stopped run gives it fewer seed
    values than running every mutant would (the behaviour diff seeds from rule mutants only,
    which always run) *(verifier round 1 of M11; kept as it
    is, since arm B was measured with it)*.
  - *(Decided in M8:)* each mutant has a **stable id**, `m-` + 12 hex digits of sha256 over
    `[path, line, original, replacement]`: the same edit has the same id in every run and receipt.
    The receipt cuts a mutant's original and replacement to 200 characters and its diff to 30
    lines (a body mutant of a long function).
  - *(Decided in M4:)* killed means a test that passed on head fails on every attempt (one rerun),
    or the run times out twice in a row (timeout = max(30 s, 10 × the set's head run), flagged
    `timed_out`). A flaky failure is not a kill. A test set that can't run cleanly on head kills
    nothing, and if that could change the verdict the result is `inconclusive`. A mutant whose
    repro run is a pytest error doesn't import: discarded. A kill whose every new failure is an
    exception (not an assertion) raised on the mutated lines is flagged `crash_only` and counted in
    `crash_kills`; it still counts towards the rate (open question 26).
    The repro and PR tests run on every mutant (exact rates); the suite runs only on mutants they
    both missed *(Decided in M4 by the developer)*, so `suite` shows as not run on the others.
- *(Decided 3 Oct 2026 by the developer:)* **fixed rule mutants, report only.** Beside the model's
  mutants, `mutation_rules.py` proposes the same edits for the same fix: comparisons
  (`<`↔`<=`, `>`↔`>=`, `==`↔`!=`), `is`↔`is not`, `in`↔`not in`, `and`↔`or`, `+`↔`-`, each
  integer ±1, and `if c` → `if not (c)` (skipped where the flipped comparison already is the
  negation). Only fixed lines, one whole line per edit, through the same hygiene rules (a rule
  edit that fails them is dropped, not listed as rejected), at most 10 (the order is M11's, below),
  run exactly like a model mutant. They are shown with their own kill rate (`rule_mutants`,
  `rule_kill_rate`) and never count toward the verdict, because some are equivalent (`<` to `<=`
  where the sides are never equal) and no test can kill those. Revisit counting after M7, when a
  behaviour diff (e.g. CrossHair) can show a surviving rule mutant really behaves differently.
  *(M7:)* the behaviour diff now shows that for every survivor, report only (2.5, survivor
  evidence); counting is still open. Tampering during their runs still makes the stage `invalid`.
  *(Added 5 Oct 2026:)* also `*`↔`/` between operands, `//`→`/`, `+=`↔`-=`, `True`↔`False`,
  `break`↔`continue` and a dropped `not` (then `if not x` is not negated again). **Body
  mutants** (cargo-mutants, PIT Descartes): the innermost function holding a fixed line gets its
  body after the docstring replaced by `return <value>` for its return annotation (at most 2
  values; `None` when unannotated). Skipped: generators, bodies on the `def` line, docstring-only
  bodies, and files with a bare `\r` (ast and our line split would disagree). They pass the
  code rules but not the line rules (they span unfixed lines; the line rules bound the model,
  not our own code). A body mutant that survives means no test looked at what the function
  returns. Any error while making or running rule mutants, other than tampering, becomes a note.
  *(M11, NOTES 24:)* **kinds, spread.** Every rule edit has one of 10 kinds, in this fixed order:
  `body`, `compare` (`<`...`!=`), `logic` (`and`/`or`, a dropped `not`), `negate_if`, `constant`
  (integers ±1, `True`/`False`), `arithmetic`, `membership` (`is`/`in`), `loop`
  (`break`/`continue`), `drop_call`, `reraise`. The kinds take turns, body first; within a kind,
  line and column order; still at most 10 in all. So one of each fits, and which kinds run no
  longer depends on line order (48 of slice 2's 145 runs reached the cap). Two kinds are new.
  `drop_call`: a call statement on one fixed line becomes `pass`. `reraise`: a bare `raise` on its
  own line before the first statement of an `except` body, when that statement or the `except`
  line is fixed; skipped for a one-line handler or a body already starting with a bare `raise`.
  A re-raise is the one rule edit that may add a `raise`, and only exactly that line
  (`guard.check_reraise`); the model's mutants still can't, and every other hygiene rule applies.
  `drop_call`, `reraise` and `negate_if` read `ast`'s line numbers, so a file with a bare `\r`
  gets none (like body mutants). A mutant's stable id does not include its kind. The receipt
  shows `survivors[].kind` (none for a model mutant) and Guard evidence `rule_kinds`
  ("compare: 2 of 3 killed", valid mutants only) and `rule_kinds_absent` (no valid edit of that
  kind on the fixed lines; empty when no rule mutant ran, since their step may have failed), with
  one line under receipt.md's stage table. Counting them stays rejected: on slice 2, counting
  gave gold +5/-1 guarded but partial +3 and agent_wrong +1/-2, so no cleaner separation.
- Result: `guarded` if the repro test fails on the reverted code, the PR's tests (if any) do not all pass
  on it, AND ≥ 80% of valid mutants are killed by the combined tests. Otherwise `not_guarded`.
  *(Decided in M4 by the developer:)* at least 3 valid mutants are needed; with fewer (LLM failure,
  rejections, discards) the result is `inconclusive`, which never gives L2. A revert failure gives
  `not_guarded` even then. Also `skipped` (not reproduced, or no non-test change to revert) and
  `invalid` (tampering detected, §4).
- *Remaining risk:* a model can still choose mutants that are easy to kill (e.g. `return None`), and
  equivalent mutants (same behaviour) can never be killed; hygiene bounds the first, the receipt
  shows every mutant and survivor for the second. A survivor can also be an *improvement* rather
  than a bug (partial_fix: `if not raw:` completes the fix, so no test fails); no deterministic rule
  can tell the two apart, so the receipt (M8) must list survivors as "changes no test noticed", not
  as bugs, and must not drop them from the count. With only 3–10 mutants one survivor moves the
  rate by 10–33%, so verdicts near 80% can flip between model runs (open question 24). *(M11:)*
  asking for 8–10 did not change that. On slice 2's dev split the median of valid mutants rose
  from 5 to 7 on runs played to the end, yet with a new set of mutants the verdict differed in 12
  of the 115 runs both arms judged, and a guarded verdict with one survivor stays one mutant
  from the line until there are 10 valid ones (the most any run had was 9). Still open: 10 or
  more mutants, or a margin instead of a hard line (the developer's call). A test that reads the
  source text instead of calling the code would kill every mutant (open question 17).

### 2.5 Behaviour diff
- For each changed function that is importable: the same inputs run on base and on head, in
  separate watched runs; every input whose outcome differs is a `BehaviourChange`.
- Judge (LLM) labels each change `intended` (asked for by the issue or the documented contract) or
  `suspicious`, with a one-line reason. The label is advisory (it can only withhold L3); the raw
  inputs and outcomes are always shown.

*(Decided in M7; eleven verifier rounds.)* How it is built (`behaviour_diff.py`,
`behaviour_rules.py`, `judge.py`, the runtime's `diff` mode and call recorder, role `judge`):
- **Targets:** Break My Fix's (`select_targets`), plus functions without parameters (called once).
  A function is new with the fix only if diffscope says ADDED, base binds the name nowhere at
  module scope (read from the source: also inside `if`/`try`/`with`/`for`, tuple and starred
  targets, `global`, walrus, a star import or a module `__getattr__` count as binding it), and
  base's module doesn't have the name when it runs. A new function has nothing to compare and
  doesn't block L3.
- **Methods** *(M7.5)*: a changed method is compared like a function, its object built the same
  way on both sides from the same text (typical objects from tests, docstrings and the issue, plus
  made-up ones; none of the model's). The object as the call left it is part of "the arguments as
  the call left them", and the module data walk includes its class (caches and registries kept on
  the class, along the MRO). A method is new only if diffscope says ADDED, base's class never
  binds the name and has nothing to inherit it from (a base other than `object`, a metaclass,
  `__getattr__`), and base's class lacks it at run time; a method base's class only inherited,
  or had as another kind, blocks L3. An object that fails to build on both sides with the same
  error is not an input; on one side only (or with different errors) the input is lost and never
  allowed, like an unreadable outcome. Method lines (defaults, decorators) belong to the method,
  not to module-level code; other class-body lines still do. A method called on an object
  (instance method, property) never has the finite-input waiver: its object's state also comes
  from other methods, which the run doesn't try (developer, 12 Oct 2026); class and static
  methods keep it.
- **L3 blockers besides the gate below** (each a plain-English reason): a changed special method
  (`__init__`, `__eq__`...), property setter or deleter, method of a nested class, or nested
  or generator function (not compared); changed functions
  past the cap of 6; a changed function base had in another form, async on one side only
  included *(M11 early: an async function or method is compared with each call awaited on a
  fresh event loop; awaiting both sides would hide that callers now get a coroutine, or no
  longer do)*; a removed public function or
  method (dunders included; not a function nested in another); changed module-level code that
  computes a value, outside top-level functions; a changed import that rebinds a name to
  something else; a file that doesn't parse on one side; a comparison that didn't finish.
- **Inputs, deterministic only** (no model strategies, and no values from the reproduction test
  or its attempts as seeds: a model's values would count toward the L3 floor): docstring examples
  of base and head, literal calls in the tests and in the issue, the fix's grid and evidence
  values, type boundaries, then 200 Hypothesis draws from type hints and seeds (derandomized).
  The reproduction test's own literal calls are inputs too, but don't count toward the floor.
- **Runs:** head generates the list once and calls each input twice; base replays the same
  literals in its own copy. An input is compared only if both sides answered, both signatures
  accept it as given (a parameter only the fix added is never dropped), both calls on each side
  agreed, and both outcomes can be read in full. When the time limit kills a run, the input
  that was running is run once more on its own: killed again, it hangs, a one-sided hang is a
  change of kind `hang`, and the run is resumed past it (at most twice per target and side); if
  it returns, the run only ran out of time, and the function is unfinished (no change, no L3;
  developer, 8 Oct 2026, after verifier round 11: resuming mid-way left the two sides with
  different module data).
- **What is compared** (each by a sha256 digest of its whole text; shown text is cut to 1,000
  characters):
  - the result as a *snapshot* of its whole state. Only what Tracefix provably understands is
    read (an allowlist): plain values and standard-library value types (dates, Decimal, Fraction,
    UUID, paths, IP addresses, ranges) by repr, except where a repr hides part of the value (a
    pattern by its full text and flags, a slice by its parts, a date or time with a project
    tzinfo by its naive value and that tzinfo; a project subclass of a date type by the base's
    own fields; a repr that still shows only an address is opaque); the builtin containers item
    by item,
    through the builtin's own methods, with a deque's `maxlen` and a defaultdict's factory;
    builtin exceptions by args, every C field (`name`, `filename`, `errno`...), cause and
    context; objects of classes written in Python (a class statement's class: no C methods or C
    fields in its namespace) by every attribute and slot, read through the slot itself, never by
    `__repr__`, with their plain value or items when they subclass one; functions, classes and
    modules by a name that leads back to the very object (a C wrapper such as an lru_cache too:
    its cache is not compared); bound methods by function and object;
    type hints by repr; the standard streams and OS files by name, mode and whether closed; a
    lock by whether it is held, an RLock by whether this thread holds it and how often (Event,
    Semaphore, Condition and Barrier are Python classes, read as such); a logger by name, level,
    `disabled`, `propagate` and its handlers' types and levels; Enum members by name, value and
    any attributes set on them; `os.environ` and mapping proxies by their items. A mutable object
    (a bytearray too) met again is
    written as a reference to its first place (shared state and cycles show). Anything else (a C
    object such as `re.Match`, an iterator, a function or class made at run time, over 20,000
    values or 200 levels) is *opaque*;
  - for a raise: its type, message and that snapshot; whether anything besides the message
    differs decides `message` or `exception`;
  - what the call printed (up to 1 MB, streams with a `.buffer`), and everything that reached
    file descriptors 1 and 2 (a stream kept from import time, C code; diff runs start pytest with
    `-s`; each cut at 1 MB); stderr, warnings and every log record the loggers' levels let
    through (`side`). Each log record the call makes gets a fixed time, thread and process id
    (two calls of one input log at different times, and base and head run in different
    processes);
  - whether the function changed any file in the copy: *what* it writes is not compared
    (developer, 8 Oct 2026, after verifier rounds 9 to 11 found a new gap in each way of
    comparing writes call by call). Every file is looked at just before the function's first
    input and after its last (size, modification time, and the change time where `utime` can't
    set it; a file whose times are too close to the first look to trust, git's "racily clean"
    rule, has its content read). A file created, changed or deleted keeps L3 out of reach for
    that function, as does a copy of over 20,000 files (caches such as `__pycache__` aside);
  - the arguments as the call left them;
  - module data (`state`, compared call for call, not between the two calls; each place
    snapshotted on its own, and only the places the call changed count, so a name only one
    side reaches but no call changes is no change): every global the
    function's code names, and the globals of the project's own functions it calls, in any
    module (helpers, methods, through decorators and `functools.partial`); every data attribute
    of each project class it reaches (named, or the class of a value it reaches, along the MRO:
    caches and registries written through `self` or `cls`); each reached function's closure
    cells, defaults and attributes, at every layer of its decorators (`__wrapped__`), with a
    decorator object's own state; the project's functions, methods, partials and classes kept
    in data it reaches (a dispatch table, a registry), walked like named ones; attributes it
    names of a project module; data of any kind,
    and a name it binds with `global` that doesn't exist yet (all of its module's names if it
    uses `globals`, `vars`, `setattr` or `delattr`). Functions, classes and modules are code,
    compared by diffscope; a function made at run time inside module data (a table of lambdas)
    is read by its code, defaults and closure.
  An input whose result, arguments or module data is opaque is not compared, and blocks L3 (see
  2.8): a change there could never show.
- **Not observed** (`behaviour_rules.UNOBSERVED`, carried on every result for the receipt's
  `unchecked`): files written outside the copy and anything sent off the machine; folders,
  file modes and metadata in the copy, and files under its cache folders; state of
  dependencies and C extensions; process-wide state the code doesn't reach by name; module data
  reached only through `importlib`, `sys.modules` or a computed `getattr`; code put into module
  data during a call; threads and processes a call starts; objects shared between the result,
  the arguments and module data; output past 1 MB. A change only there can't show, so L3 makes
  no claim about it (2.8).
- **Changes** are grouped by (function, outcome class before, outcome class after); a new
  message (only the wording: args that are just the message, nothing else in the exception
  different), printed or logged output, argument state or module data forms its own group
  (`message`, `output`, `arguments`, `state`); an exception that differs beyond its wording is
  `exception`. Whatever else differs on the same input (output, arguments, module data) goes
  with the change: it forms its own group, which must be explained on its own (a new message
  with anything else changed is no longer exempt), and the Judge is shown every part that
  differs.
- **Deterministic tags:** a group is *explained* by an input the issue calls literally, a
  docstring example the PR left alone that base breaks and head keeps, or a reproduction call our
  own run vouches for: the reproduction test runs once more on base (watched, 300 s) with a call
  recorder that notes each call to a target made from the test file (through decorator wrappers
  too), by its exact place and test case, and where each case failed; the call must sit inside
  the check (`assert`, `pytest.raises`) on the line where that case failed, in that same case,
  and base's JUnit report must agree the test failed; a second report from the run counts as
  forged. A change *contradicts* a docstring example of base's that base keeps and head breaks.
  The PR's own tests and docstrings never explain (an AI fix often writes them to fit itself):
  they, and the untouched tests' calls, are advisory notes.
- **Blind spots:** a check of the reproduction test our run vouches for (it failed on base,
  holds on head) in which every call was compared and none differs means the comparison can't
  see that change: L3 is out of reach. One call in the check that differs (a refactored helper
  beside the changed call) is enough.
- **The Judge** sees the issue, the source diff, the functions after the fix, the README start,
  and one change of every input shape and result direction in every group (then up to 5 per
  group; 40 in all, else L3 is out of reach), each as a call with its outcome before and after
  (and what it printed, logged or did to its arguments, for those kinds), the kind of change in
  each heading, and the tags as "verifier facts" (when the shown texts are the same, it sees
  the snapshots; if those still look the same, a fact says they differ further on). Text is sanitised and ASCII; an exception's message is shown only
  when a `raise` in the repo wrote it. It is asked twice, in independent conversations (each the
  request and at most one follow-up for missing ids): a change is `intended` only if both say
  so; `suspicious` from either wins; a missing label stays missing. Our code reads each reply:
  unknown ids ignored, reasons cut to one line.
- **Survivor evidence (report only):** each mutant that survived Guard runs on head's inputs in
  one variant copy of head (no resumes): `differs` (with up to 3 inputs), `no_difference_found`
  (maybe equivalent) or `not_checked`. Never part of Guard's verdict.
- **Statuses:** `compared`, `partial` (something not compared or not finished), `inconclusive`
  (nothing compared), `skipped` (no target), `invalid` (tampering, in any of its runs). Changes
  found before an error are kept.
- **L3 (see 2.8):** `checks_gate` (no model output) and `l3_gate` (the checks plus the Judge,
  who can only veto).

### 2.6 Break My Fix (hero feature)
- Target: changed functions on head only.
- Attack sources, in order:
  1. Boundary values from the type/usage: None, empty, 0, -1, max int, huge strings, unicode,
     whitespace, NaN/inf, nested empties, malformed shapes.
  2. LLM-proposed properties/invariants from the issue and docstrings
     (e.g. "never raises for any str", "output sorted", "idempotent", "round-trips").
  3. Hypothesis search against those properties with shrinking.
- A finding counts ONLY with: the exact input, the observed output/exception, the violated property,
  and a standalone pytest file that reproduces it. Otherwise it is discarded.
- Deduplicate findings by (function, exception type / property). Cap at 5 shown.
- A finding is `pre-existing` (reported, but not a fix failure) only if the same input gives the same
  outcome on base AND the failing run on head executes no line the fix added or changed (checked by
  line tracing). Otherwise it counts even though base also failed: the fix touched that path and left
  it broken. *(Decided in M1; see fixture `partial_fix`, where `parse_port("")` runs the new check.)*

*(Decided in M6.)* How it is built (`attack.py`, `attack_inputs.py`, `attack_rules.py`,
`attack_runtime.py`, role `adversary`):
- **Targets:** changed module-level functions, plus up to 2 public same-file callers of a changed
  private function (its contract lives there); at most 6. Nested and generator functions (async
  generators too) and functions without parameters are skipped with a reason. The attack calls
  the binding the module exports (an `@overload` stub is never it). *(M11 early:)* an `async def`
  function or method is a target: each call runs to the end with `asyncio.run` on a fresh event
  loop (never inside a running one: the target is then not loaded), in the run and in its repro
  file; an async property stays skipped. *(M11, NOTES 30:)* a method marked `@abstractmethod` or
  `@abstractproperty` is skipped with a reason, and a changed abstract private method brings in no
  callers: its body is not what runs (twyn-317's false alarm reported the `None` of a docstring-only
  body). A concrete override that changed is a target as usual.
- **Methods** *(M7.5)*: instance methods, class and static methods, and property getters of
  top-level classes are targets (a changed private method also brings up to 2 public methods of
  its class that call it). Special methods, setters and deleters, nested classes and an instance
  method whose first parameter isn't `self` are skipped with a reason. A method's input holds
  `self`: the text of a call that builds a fresh object (`Listener(default_port=9000)`), checked
  like a property expression and built only inside the sandboxed run. Typical objects come from
  the default constructor, the project's tests (an object built fresh for the call), docstring
  examples, the issue, the reproduction test and the model's examples; made-up objects are built
  from the constructor's signature. A violation on a made-up object counts only for a property
  whose `when` names `self`; otherwise it must survive on the first typical object, else it is a
  report-only note (developer, 9 Oct 2026). An object that can't be built is not an input; a
  class none of whose objects build is skipped with the reason. In properties `self` is the
  object before the call, `self_after` after it. Repro files build the object and call the
  method on it.
- **Properties** come from a fixed menu: `returns` (`check` and/or `expected`), `raises`,
  `raises_only` (an empty list means never raises) and `relation` (a second call with
  `transform`ed arguments, `check` over `result` and `result2`), each limited by `when`. Named
  patterns (reference value, bounds, idempotent, round trip, monotonic, documented errors) are
  built from these. Expressions are single Python expressions, checked as syntax trees (no lambda,
  walrus, f-string, `**`, `<<`, attribute starting with `_`, forbidden name, or call to the
  function under test) over the parameters, `result`, the module's own public names (no
  imported module or function: only class-like imported names, for exceptions; the run refuses
  anything that is not the module's own or plain data), a fixed list of builtins and pure stdlib
  modules (one the repo could shadow is withheld). A `check` that compares something with itself
  is rejected. They are never evaluated in Tracefix's own process, only inside the sandboxed
  runs, and a run's report only decides about the properties in that run.
- **A model property counts only after two deterministic checks** *(developer, 6 Oct 2026)*:
  1. *quote:* it quotes, word for word (whitespace collapsed, at least 12 characters), the text it
     rests on, from what the adversary was shown: the issue, a docstring, a comment, the README,
     the signature or an existing test;
  2. *project tests:* it agrees with every call to the function that the project's own unchanged,
     passing tests (and a reproduction test that reproduced) make with literal arguments
     ("witnesses"). A violation at a witness *contradicts* the property; none of its violations
     count. The PR's own new or changed tests are advisory only: a disagreement is shown, never
     decides (an AI fix often writes tests that assert its own behaviour). A test also counts as
     changed when the PR changed its file outside test functions, or a conftest or helper in its
     folder or above. Relations are not judged on witnesses (the test vouches for one call
     only). NaN and infinities are judged only by a property whose expression names them (`nan`,
     `inf`, `isnan`, `isinf`, `isfinite`, or a string such as `"nan"`; read from the syntax tree,
     so `nanos` does not count).
- **What a model expression can reach** *(verifier round 2)*: the safe builtins only; standard
  library modules as read-only stand-ins holding only their public functions, classes and
  immutable constants (no imported modules, no shared mutable objects, no setters of global state
  such as `decimal.setcontext`); the target module's own names, its data copied afresh for each
  evaluation. Attribute names that lead to the process or the file system (`sys`, `os`,
  `environ`, `open`, `write`, `get_field`...) and frame, generator, traceback and code attributes
  (`gi_`, `f_`, `tb_`, `cr_`, `ag_`, `co_`) are rejected by hygiene. (`str.format` can still show
  underscore attributes as text; never add a helper that returns the objects.) A run's "finished"
  line counts only from a run that passed, and only once.
- **Docstring examples count, model-free** *(developer, 6 Oct 2026)*: `f(literals) == literal`
  in the prose and `>>>` doctests (compared like doctest: printed output, then the repr; one with
  a directive such as `+ELLIPSIS` is skipped). They run on their own, with no model code in the
  run. One the code breaks is a candidate finding; one the run reports as held is a witness (one
  that never ran, or whose comparison errored, is neither). The pre-existing
  rule still applies.
- **Inputs, in this order:** docstring examples; the **grid** from the fix's own comparisons
  (`year == 2100 and month == 2` gives that input, then one parameter at a time moved to a
  neighbour: 2101, 2099, 2200, 2000, -2100); evidence values (literals on the fix's lines, numbers
  and quoted strings in the issue, the repro test's and partly fixed attempts' calls, Guard's
  surviving mutants, fewer when Guard stopped early: 2.4) swept over typical inputs; the model's examples; type boundaries (empty,
  blank, zero, ±1, huge, NaN, unicode, ...; strings also the tricky ones where text methods and
  number parsers surprise: mixed case, a case mapping that changes the length, a decomposed accent,
  digits `isdigit()` and `int()` disagree on, a zero-width space, CRLF, a byte-order mark; the
  behaviour diff shares them) swept one parameter at a time; then a Hypothesis search
  per property (`find`, derandomized, `max_examples` 200 inputs the property applies to, shrunk).
  Limits are counts, never wall-clock time; an attack run that hangs is resumed past the hung
  input (report-only note), at most twice.
- **A candidate becomes a finding only through runs**, at most 10 checked: its input is a plain
  literal; a probe calls it again on head (the same outcome, else "not reproducible") and on base;
  a standalone repro file written by Tracefix (the property as a plain `assert` or `pytest.raises`)
  fails on head in the watched copy on all 3 attempts, with the expected failure (an
  `AssertionError` in the file for a wrong value, the raised exception outside the file, `Failed`
  for a missing raise). Then the pre-existing rule, which also never excuses a finding when the
  fix changed module-level code in the target's own file that computes a value (a constant, a
  regex, a default, a decorator: a call uses it without "running" it; an added import, `def` line
  or docstring does not count). *(M11 early:)* nor does a removed function, when that is all the
  file changed at import time (a removal marks the unchanged lines either side of it): its
  decorators only mark it (`staticmethod`, `classmethod`, `abstractmethod`, `override`), its
  defaults are constants, no non-test source file at head names it, and the file uses no dynamic
  lookup (`getattr`, `vars`, `__dict__`…); a special method (`__eq__`, a module's
  `__getattr__`) never counts as removed this way, since Python calls it unnamed. Only the
  target's own file is scanned for dynamic lookups: a base class in another file that dispatches
  by `getattr(self, f"handle_{kind}")` is not seen (a known limit). A group's representable inputs (its representative and up to 3
  others, those whose call ran a fix line first) are probed this way, and at most 2 repro files
  are tried per group, so an excused input never hides one that counts.
- **Dedupe:** a raise by (function, exception type), a wrong value by (function, property); a
  group's input is the one that breaks the most properties, then the earliest source above, then
  the shortest; groups whose input and outcome are the same merge (one bug, several properties).
  At most 5 counting findings and 5 pre-existing ones are kept.
  *(Decided in M8:)* so that one bug found through two properties merges, each attack run also
  judges the inputs that broke a property of the same target in earlier runs (at most 10, on top
  of the explicit-input cap): an input that breaks both properties becomes both groups'
  representative, and the absorbed group's inputs join the finding's other inputs. Without such a
  shared input nothing merges, so two different bugs with the same output stay two findings.
  Adversary requests are unchanged.
- **Statuses:** `found`, `none_found` (live properties, inputs tried, nothing found, every
  candidate checked (none dropped for a non-literal input or a probe that did not finish), every
  target's attack finished and every search ran), `inconclusive`, `skipped`, `invalid`
  (tampering). An error after a confirmed finding keeps it. A target that hangs is resumed past
  the hung input at most twice, then given up (and the stage can't be `none_found`).
  Report only: crashes no property covers, hangs, the PR tests' advisory disagreements, inputs
  tried and the fix lines the attacks reached (open question 27: what L4 needs from these).
- The adversary makes at most 3 calls: the request; one follow-up, only to repair rejected or
  contradicted properties, to cover a function left without one, or for a function that ran no
  input; then one independent second sample of the same request in a fresh conversation, whose
  new properties go through the same checks *(developer, 6 Oct 2026: the model's properties vary
  from run to run; the temperature can't be set for this model)*. It never sees an attack result.
- *(M11, NOTES 33:)* a function that ran no input says why in the receipt
  (`attack_targets[].reason`), in fixed words, the first that applies: its error; it has no
  property; the attack did not finish; every property was contradicted or could not run; no object
  could be built (with the first build error); no strategy for the named parameters; no input fits
  any `when` (with a count); the expressions failed on every input (with the first error); nothing
  generated. If it could still be helped (it loads, the model has a property that counts on it,
  the run finished), that line goes to the model in the follow-up, as harness facts inside a data
  block, with a fixed hint; a build or expression error is named there by its type only (its
  message came from running head, and the receipt keeps it; verifier round 1 of M11). If the answer brings a new object or strategy, the function's properties
  run again; its new examples go first, and a new strategy replaces the old one. No level or count
  reads the reason. On slice 2's dev split the runs with no input went from 33 to 31 of 144, short
  of M11's target of 22; in 19 of the 31 the reason is that no object of the method's class could
  be built, which a second answer from the model rarely repairs (NOTES 33).
- *(M11, NOTES 39; developer, 4 Nov 2026:)* **a warning is not a raise.** A call that raises a
  `Warning` (a project's `filterwarnings = error` does this) is called once more without the
  "error" filters in force when the run started (the project's pytest config, `-W`,
  `PYTHONWARNINGS`), and that second call is what gets judged: a value, or a real crash. Its
  outcome says so (`warned`, the first warning's name; "returns None (with warnings ignored; X
  would have raised)"). A property that names the warning (`exceptions` of a `raises`,
  `raises_only` or `relation` property, or a docstring example that says it raises it) is judged
  on the raise. If the second call still raises a warning, the code raises it itself (`raise X`,
  or a filter the code set after the run started, at import or during a call), and that raise
  stands (one set at import is then lost by the repro file, under pytest: NOTES "M11's limits")
  *(verifier round 1 of M11: the second call first ignored every warning, which hid a raise from
  a package that makes its own warning an error on first use)*. A relation's second call follows
  the same rule. The head and base probes judge the same way, and the repro file of such a
  finding runs its call inside `catch_warnings` with every "error" filter taken away (when a test
  starts they are all the project's), so it fails for the reason the run judged *(verifier
  round 2: ignoring every warning there changed what code that records its own warnings
  returns, and lost the finding)*. The
  behaviour diff is unchanged (2.5: it compares warnings too). Known limits: a call with side
  effects runs twice; a constructor that warns under such a filter still means "no object built"
  (an input lost, never a finding).
- *(M11, NOTES 40; developer, 4 Nov 2026:)* **doubt flags, measured and not deciding.** A
  finding may carry one fixed word for why it may be a false alarm. It still counts: no status,
  count, level or Judge request reads the word. *(Developer, 13 Nov 2026, after the rerun:)* all
  three stay report only until the held_out split is run, and the rule to test there is fixed
  now: a finding flagged `finished_object` or `refused` stops counting, and `os_limit` stays
  report only. On slice 2's dev split all 8 flagged findings were the developer's false alarms
  and none of the 9 real-bug findings was flagged, but the flags were written from those same
  cases, so that shows only that they hit nothing else. The first that applies, for an outcome
  that raised:
  - `os_limit`: the OS said the name is too long (`ENAMETOOLONG`, or Windows `winerror` 206). A
    too-long name on Windows usually comes as `ENOENT`, which says nothing, so this is mostly Linux.
  - `finished_object`: a method's `AttributeError` ("'X' object has no attribute 'y'") on an
    attribute that `X` (or, if `X` isn't in the file, the method's class), or one of its bases in
    the same file, deletes from `self`: `del self.y`, `del self.__dict__[k]` or `delattr(self, k)`,
    with `k` a string or a loop's variable over listed strings. A class or base in another file
    isn't read, nor a name-mangled `__y`.
  - `refused`: a `raise` statement in the copy made it, with the same type and message before the
    fix. The run reads the instruction the innermost frame stopped at (`raised_by: raise|crash`,
    `in_project`), so a `raise` written over several lines counts; an `assert` doesn't (the code
    never expected it), nor a `raise` inside a library. "The same before the fix" alone flags
    nothing: mqtt-exporter-37's real catch was the same on base, a wrong value and no raise.
- **Who is to blame for a violation** *(real-bug trial, 6 Oct 2026)*: a violation counts against
  a property only if it survives putting every parameter the property's expressions don't name
  back to its default (the cleaner input is the one reported, with the defaults its expressions
  name written out, so the repro file binds them); otherwise it is a report-only note and the
  input does not count as judged. Expressions see a left-out parameter at its default only
  when that default is a plain literal. A repro file that errors, times out or fails the wrong
  way makes the stage inconclusive; only one that passes discards a candidate. A raise on an input holding one of the huge boundary values (|int| >= 2**31 - 1,
  |float| >= 1e300) is also only a crash note, unless the property's quote speaks of large
  values ("large", "overflow", "arbitrary", "any size"...) *(developer)*.

### 2.7 Integrity audit (deterministic first)
- Flag in test files changed by the fix: deleted test functions, removed/loosened asserts
  (`assert x == y` → removed or replaced by weaker), new `skip`/`xfail`, broadened `pytest.raises`.
- Flag special-casing: literals from the repro test's inputs appearing in newly added source lines
  inside conditionals.
- An LLM may annotate each flag (e.g. "looks legitimate because …"), shown next to it, but can never
  dismiss a deterministic flag. *(Decided in M1; exact candidate rules settled in M5.)*

*(Decided in M5.)* Two steps, no model at all:
1. **Candidates** from the code alone (`integrity_rules.py`). In changed test files:
   - `deleted_test` (a same-body rename is not one);
   - `removed_assert` (an assert, `self.assert*` call, `pytest.raises` block or parametrize case
     gone; a check moved to another test in the file is not removed);
   - `weakened_assert` (`==`/`is` replaced by a weaker check, or a looser `approx`);
   - `changed_expectation` (same check, new expected value);
   - `added_skip`, `broadened_raises`;
   - `collection_changed` (conftest or pytest config changes what is collected).

   In changed source files, `special_case`: a literal in an equality, identity or membership test
   (never `<`/`>=`) on the fix's changed lines that is non-trivial (not `None`, booleans, `0`, `1`,
   `-1` or empty), new to that file, and written in the evidence (issue text, repro test or the
   PR's changed test lines; numbers match as whole tokens). Plus `added_pragma` for new
   `# pragma: no cover / no mutate / no branch`.
2. **Confirmation by runs**, each watched (§4). *Developer's decision:* only a confirmed candidate
   is a **flag**; everything else is a report-only candidate with the reason.
   - **Old tests, new code:** every test-layout file (tests, conftests, helpers, data) and pytest
     config the PR changed goes back to base; each changed test file then runs on its own, in the
     base copy and in a copy of head. A deleted test, removed or weakened check, new skip or
     broadened raises is confirmed when its old version passes before the fix and fails on it on
     every attempt: on that check's own line (for checks), with `AssertionError` or pytest's
     `Failed` (any exception for broadened raises). An import, attribute, type, name or collection
     error means the old test no longer fits the new code (not confirmed); any other crash (e.g.
     `KeyError`) can't be told from a deliberate change (unjudged). Test ids are read relative to
     the rootdir the runner pins.
   - A check's identity includes where it sits (conditions, `with`, `try` around it, code after a
     `return`), so `with suppress(AssertionError):`, `if False:` or an early return around an old
     check makes it a `weakened_assert`; a check "moved" into a skipped test is still removed; skip
     marks are also found through aliases. A test renamed with at least half of its checks on the
     same subjects, and a parametrize case whose inputs come back with a new expected value, are
     compared as changed expectations.
   - **Branch removed (report only):** a special case whose branch only returns a literal is cut
     out of head and the repro test (else the PR's tests) run again; the result is shown with the
     candidate. At most 5 branches per audit.
   - `changed_expectation`, `special_case`, `collection_changed` and `added_pragma` are never flags
     (*developer's decisions*: a changed expectation is often a legitimate correction, revisit
     after M7; no fixed rule can tell `if year == 2100: return 28` from a legitimate fix for one
     value such as `if status == 429: return True`, so `special_cased`'s COUNTEREXAMPLE comes from
     Break My Fix in M6).
   - Statuses: `flagged`, `clean`, `inconclusive` (something could not be judged, no flag),
     `skipped` (no test or source change), `invalid` (tampering). An error after a confirmed flag
     keeps the flag.
   - LLM annotation of flags: *(built in M8)* the Judge's receipt call (2.8) may add one line per
     flag, shown beside it; a note never removes a flag.

### 2.8 Receipt
Evidence ladder (computed, never model-chosen):

| Level | Condition |
|---|---|
| `COUNTEREXAMPLE` | Any valid Break My Fix finding not pre-existing, OR an integrity flag (deterministic, see 2.7), OR `fix_does_not_fix`, OR a confirmed regression (2.9) |
| `L0` | not reproduced, or any stage `invalid` (tampering), or the run status is not `ok` |
| `L1` | reproduced |
| `L2` | L1 + guarded |
| `L3` | L2 + behaviour diff `l3_gate` allowed: complete, every kind of change explained, no docstring example broken, and no change the Judge calls `suspicious` (see below) |
| `L4` | L3 + the strict L4 gate (below): Break My Fix found nothing, with every changed function attacked to the end, and the integrity audit and the no-regression check finished clean; with `--previous`, every finding of the last receipt shown fixed (2.10) |

*(Decided in M8; `ladder.py`, pure.)* Our code reads the facts from the stage statuses and climbs:
```
run status not ok                                   → L0
any counterexample (a counted Break My Fix finding, an integrity flag,
  fix_does_not_fix, a confirmed regression)         → COUNTEREXAMPLE
any stage invalid (tampering)                       → L0
not reproduced                                      → L0
not guarded                                         → L1
behaviour diff l3_gate closed                       → L2
L4 gate closed                                      → L3
otherwise                                           → L4
```
Order: `COUNTEREXAMPLE < L0 < L1 < L2 < L3 < L4`. A counterexample counts only from a stage whose
status says so (attack `found`, integrity `flagged`, regressions `found`, reproduce
`fix_does_not_fix`), so the findings of an `invalid` stage never count. The level carries plain
reasons: what each passed gate showed, then `not Lk: …` for the first gate that closed. The only
model influence is the Judge's veto inside `l3_gate` (M7).

- A run that stops with status `ENVIRONMENT_ERROR` gets level `L0`, and the receipt says why.
  *(Decided in M1.)*
- *(Decided in M8 by the developer:)* **tampering in any stage caps the level at L0**, with the
  tampering listed prominently; a counterexample proven by clean runs stays `COUNTEREXAMPLE`
  (tampering must never give a pass, and must never lift a counterexample to L0).
- *(Decided in M8 by the developer:)* **L4 is strict.** All of: (1) Break My Fix `none_found`; (2)
  no changed function it had to skip; (3) every target attacked and finished, with at least 100
  inputs tried (`L4_MIN_INPUTS`, per target, not in total); (4) every target has a counted
  **model** property that constrains its result (`constrains_result`; docstring examples don't
  count: each checks one input); (5) every executable fix line inside a function
  (`AttackResult.fix_lines`) is in some target's `reached`; (6) *(developer, verifier round 1)*
  the integrity audit ended `clean` or `skipped` and the no-regression check `none_found` or
  `skipped`: one that raised, didn't run or was `inconclusive` could hide a counterexample
  (`ladder.audits_gate`; it keeps only L4 out of reach); (7) *(developer, 14 Oct 2026)* with
  `--previous`, the replay ended `replayed` with every finding `fixed`, or `skipped`
  (`ladder.previous_gate`, 2.10; it keeps only L4 out of reach). A weak or narrow property, or attacks
  that never reach the fixed lines, can't lift the level; some correct fixes stop at L3.
- *(Decided in M7 by the developer:)* **L3 = deterministic checks + Judge veto.** Our own code
  decides whether L3 is possible at all (`behaviour_rules.checks_gate`, which reads no model
  output): no L3 blocker from 2.5 (everything changed was compared, to the end); each function
  compared on at least 50 inputs besides the reproduction test's own (or every input of a
  domain our own reading of the annotations shows is finite) with at most 20% lost, and none
  lost because its result, arguments or module data can't be read in full; every kind of change explained by the issue, a docstring example, or
  a reproduction call our recorded run vouches for (an error message's wording is exempt); no
  docstring example broken; no blind spot; every input shape of every group shown to the Judge.
  The Judge can then only veto (`l3_gate`): with changes, every shown change needs the label
  `intended` from both samples; one `suspicious` label, or a missing one (no Judge, a failed
  call, a skipped id), keeps L2. A fix with no behaviour change needs no Judge. Property tests
  prove no Judge answer allows what the checks don't.
- *(Decided in M7 by the developer, 8 Oct 2026, after verifier round 9:)* **What L3 claims:** no
  unexplained change in what the behaviour diff observes (2.5 "What is compared"), not that
  nothing else changed. Proving the second would mean observing every way Python code can
  affect the world, a list with no end: nine verifier rounds each found another channel. The
  channels not observed (2.5 "Not observed") are always listed in the receipt's `unchecked`. A
  route by which a wrong change reaches L3 through an observed channel is a bug; a change only
  in an unobserved one is a listed limit.
- `fix_does_not_fix` requires the same failure signature on base and head (see 2.3).
  *(Decided in M3.)*
- *(Decided in M6 by the developer:)* **fix-line coverage is report only.** Which of the fix's
  executable lines the reproduction test and the PR's tests run (`linetrace.fix_line_coverage`) is
  shown in the receipt; L2 keeps its meaning. Revisit with numbers from real fixes (M10).
  M10 slice 1: the reproduction test ran 61% of gold fixes' lines (125/204) and 50% of partial
  fixes' (61/122), too close to separate them; no change proposed (`docs/BENCHMARK.md`).
- Guard's crash kills (2.4) are shown in the receipt and still counted (open question 26). M10
  slice 1 had none: 0 of 76 kills were crash-only (0/52 on gold, 0/24 on partial fixes).
- *(M11:)* **what M11 added is in the receipt and read by no level:** the blind shadow test
  (2.3; its stage is also left out of `unchecked` and of the Judge's facts), a finding's doubt
  flag (2.6), why a function ran no input (2.6), rule mutants' kinds and the mutants Guard left
  unrun (2.4). One exception, as for every stage: tampering seen while the blind test runs makes
  its stage `invalid`, and the tampering rule caps the receipt at L0 (2.3; it can only lower a
  level, and the code under test runs in that stage too; developer, 13 Nov 2026, after verifier
  round 1). The one M11 rule that changes a level is in 2.6: a warning is not a raise.
  *(Developer, 13 Nov 2026:)* the blind test will cap a receipt at L1 in a later step (2.3); the
  table above changes when that is built, not before.

Always include `unchecked`: concurrency, database state, network/external services, auth,
performance, configuration, the behaviour diff's unobserved channels (2.5) — plus any stage
that was skipped and why.

*(Decided in M8; `receipt.py`.)* **`receipt.json`, schema v1**, built from the stage results only,
as pydantic models (frozen, no extra keys); `docs/receipt.schema.json` is generated from them and a
test fails when it is stale. Top level: `schema_version, tracefix_version, created_at, status,
status_reason, level, level_reasons[], repo{name}, base{ref,sha}, head{ref,sha},
issue{title,sha256}, isolation{level,why,warning}, summary{text,by}, stages[]{name, status,
reason, duration_s, commands[], problems[], error, evidence}, findings[], pre_existing[],
behaviour_changes[], integrity_flags[] (with the Judge's note), regressions[], survivors[],
fix_line_coverage, unchecked[], llm{calls, tokens, cost_estimate, settings, problems[]},
tampering[], warnings[], notes[]`, and *(M9, optional)* `previous{head_sha, level, created_at,
findings[]{number, call, file, result, detail, carried}, still_open[]{number, call, file, expect},
still_open_known}` (null without `--previous`; `head_sha` empty and `level` null when the last
receipt could not be read).
M9 also added optional `path`, `line` and `expect{types, in_file}` to findings and `line` to
regressions; every M9 field is optional, so earlier v1 receipts still validate. M11 added, all
optional and report only: `doubt` on findings (2.6), `kind` on survivors (a rule mutant's kind,
2.4), Guard evidence `not_run`, `rule_kinds` and `rule_kinds_absent` (2.4), and a stage `blind` whose
evidence holds `attempts`, `test_file`, `oracle` and `report_only: true` (2.3). It also fills
`attack_targets[].reason` for a function that ran no input (2.6; the field was empty before).
- No machine path leaves the machine: every string of the dump is masked at the end, so no field
  can be forgotten (the user's repo becomes `<repo>`; the copies, the environment, temp and home
  folders become tokens; other paths on traceback lines keep only their file name), and the
  interpreter in commands becomes `python`.
- The reproduce entry names the model-written oracle and the isolation level (open questions 14,
  17). Survivors are worded as "changes no test noticed", never as bugs. The cost is labelled
  "estimate at list prices".
- Beside it: `repro/<file>` (the reproduction test) and `findings/finding_<n>.py` (each finding's
  standalone pytest file).

**`receipt.md`** (`receipt_md.py`) is rendered from the same model, so the two can't disagree: the
level; the Judge's summary, marked advisory; why this level; issue, refs and isolation (with the
basic-isolation warning when it applies); findings (input → outcome, property and quote, repro
file); one row per stage with its key numbers; behaviour changes, survivors, integrity flags with
their notes; what was not checked; model use, cost and problems; tampering; then the run log in a
collapsed `<details>`. At most 60 lines above the run log and 150 in all, at most 6 level reasons
and 10 "not checked" items above the run log, 500 characters of any one untrusted text, and
60,000 characters in all (a GitHub comment holds 65,536); each cut says "… in receipt.json". M9
posts it as a PR comment, so every repo, issue or model string is escaped (Markdown and HTML, no
mentions or issue links, bare URLs broken so GitHub doesn't link them, control characters shown
as escapes) or put in a
backtick-safe code span: hostile text can't fake a verdict, hide the receipt or ping people.

**The Judge's summary** *(Decided in M8, moved from M7)*: one call (role `judge`) after the ladder,
only when the run status is `ok`. It sees the issue (as data) and facts from the receipt: the
level and its reasons, each stage's status, findings, flags (`f1`, …) and change labels; no
counts, durations or paths, ASCII only, so the request (its recording key) is the same on every
machine. Our code keeps two sentences (≤ 400 characters) and one line per existing flag id (≤ 300);
unknown ids are ignored. Display only: the level, findings and flags exist before the call (a
property test feeds it arbitrary answers). Any model problem → the summary is our own "why this
level" line (`by: tracefix`).

**Account-caused failures** *(Decided in M8)*: a model call that fails is shown on the stage it
hit, in fixed words chosen by our code from the error it caught (e.g. "the API account's rate
limit was reached (HTTP 429): this stage's evidence is lower because of that, not because of the
fix"), never from model or API message text.

### 2.9 No-regression check *(Decided in M8 by the developer; `regressions.py`)*
A fix must not break tests that passed before it (SWE-bench's `PASS_TO_PASS`).
- **Compared:** tests that passed in the environment check's base run, in places the PR left
  untouched. "Untouched" is Break My Fix's witness rule (2.6, `attack_inputs.head_tests`): the file
  is unchanged, or the test and the code around it are; no conftest or helper changed in its
  folder or above. (A test file the PR deleted doesn't make its folder touched: a test that
  imported it no longer collects, which the check reports.)
- **Skipped**, with the reason, when the PR changes the pytest options, the base run has no
  readable report, or nothing is compared.
- **Candidates:** the whole suite runs once on head (watched, suite timeout, the runner's reruns,
  `--continue-on-collection-errors` so one broken file doesn't hide the rest); a compared test that
  failed in every head attempt, or a compared file that no longer collects.
- **Confirmed** by two more runs, only when there are candidates: the candidates' files on base
  (every compared test must pass in every attempt), then on head (must fail every attempt, with
  the candidate among the failures). Flaky or unfinished → `inconclusive`, never a regression. A
  test that passed on base but didn't run on head is counted in `not_run` and noted.
- *(Developer, verifier round 1 of M8:)* a candidate that fails on head with `ModuleNotFoundError`
  for a module that is in neither copy and that an `import` statement the fix added names (read
  with `ast` from the changed `.py` files: the fix needs a dependency this environment lacks) is
  not confirmed: an environment problem, so the check ends `inconclusive`. A missing module of the
  project itself (e.g. one the fix deleted) stays a regression, and so does a module the code only
  asks for by name (e.g. `importlib.import_module("x")`) while the same test passed on base
  (verifier round 2). The evidence quotes pytest's own
  error line (e.g. the `ModuleNotFoundError`), not only "collection failure".
- Statuses `found`, `none_found`, `inconclusive`, `skipped`, `invalid`. A confirmed regression is a
  `COUNTEREXAMPLE`: concrete, executed proof that the fix breaks behaviour a test documents.

### 2.10 Replaying the last receipt *(Decided in M9; `previous.py`)*
On a new push to a PR, the last receipt's findings are run again, so the receipt says which ones
the new commit fixed (Schemathesis-style replay). No model is involved.
- **Input:** `tracefix verify --previous DIR`, a folder with `receipt.json`,
  `findings/finding_<n>.py` and `findings/previous_<n>.py` (an earlier `--out`, or the Action's
  downloaded artifact). A missing folder or `receipt.json` is exit 2; the Action's `unusable.txt`
  instead of a receipt (the last receipt exists but can't be used) makes the stage `inconclusive`.
  The rest is read into memory before the run, within limits, and is untrusted: `receipt.json` at
  most 5 MB and a strictly valid `Receipt`; at most 5 counted findings (`findings`, never
  `pre_existing`) and 20 carried ones (`previous.still_open`), each file named exactly as the
  receipt says, a regular file, UTF-8, at most 50,000 characters, and compiling. Anything else
  makes the stage `inconclusive` with the reason, and nothing is replayed.
- **Old findings stay open until shown fixed** *(developer, 14 Oct 2026, verifier M9 B2)*. The
  replay runs the last receipt's own findings and the earlier ones it carried. The new receipt
  carries every one it did not show `fixed` (`previous.still_open`, files
  `findings/previous_<n>.py`), all of them when the replay did not finish (the run stopped first,
  tampering, a run that could not be set up). So one more push can't forget a finding that still
  fails. Each check is carried once, and not beside this run's own finding that runs the same
  check (same code apart from comments and the number). Two ways out *(developer, verifier M9
  round 2)*: a finding that is `cannot_run` (e.g. its function was renamed) keeps L4 out of reach
  on that push only and is not carried; and a run that can't tell which are open (its last
  receipt can't be used, or says `still_open_known: false` because more than 20 were open) has an
  `inconclusive` replay, so it is held below L4, and its receipt carries nothing: the chain starts
  afresh from its own findings.
- **The replay trusts the PR's pytest** like every other stage: a `conftest.py` hook can make a
  replayed file pass, as it can hide Break My Fix's own findings (§4 Limits, NOTES; developer,
  verifier M9 round 2).
- **Stage `previous`**, optional (not in the fixed stage list, so runs without it are unchanged),
  right after the import origin check. Each old finding file is placed next to the tests and run
  on head, watched, with the finding timeout and no reruns:
  - `fixed`: 3 clean passes in a row (one pass by luck is not a fix); a pass is clean only if its
    test ran and was not skipped (a skip is `cannot_run`, verifier M9 B1);
  - `still_fails`: failed every attempt the way its `expect` says (a receipt from before M9 has
    no `expect`: any test failure counts, and the detail says so);
  - `fails_differently`, `cannot_run` (an import or collection error, e.g. a renamed function),
    `flaky` (passes and failures mixed), `unfinished` (a timeout).
- **Statuses:** `replayed`, `skipped` (the last receipt had no findings), `inconclusive`, `invalid`
  (tampering: L0 through the usual cap).
- **Ladder** (`previous_gate`, *developer, 14 Oct 2026*): L4 also needs the stage `replayed` with
  every finding `fixed`, or `skipped`; otherwise "not L4: finding 1 of the last receipt (…) still
  fails on this commit". It can only keep L4 out of reach: it never makes a `COUNTEREXAMPLE`
  (this run's own Break My Fix decides that) and never raises a level.
- **Receipt:** `previous{…}` (2.8) and, on receipt.md, one line under Counterexamples: "Since the
  last receipt (`abc1234`, COUNTEREXAMPLE): finding 1 `…` fixed; finding 2 `…` still fails". The
  Judge's summary request leaves the stage out, so it is the same with or without `--previous`.
- *Later (ROADMAP):* re-proposing the old properties and inputs to Break My Fix, so that an old
  finding that still holds becomes a counted finding of the new run.

## 3. LLM usage *(built in M3)*
- `llm.py` exposes `LLMClient.complete(role, system, messages, schema) -> parsed object`. Roles:
  reproducer, mutator (added in M4, default `claude-sonnet-5-5`), adversary (built in M6, default
  `claude-opus-5-5`: proposes properties, strategies and examples; it sees the issue, the fix, the
  changed functions, the README start and the untouched tests that call them, never a result),
  judge (built in M7, default `claude-opus-5-5`: labels behaviour changes; its labels can only
  keep L3 out of reach; since M8 it also writes the receipt summary and notes on integrity flags,
  display only, 2.8).
- Structured outputs (JSON) validated with pydantic; invalid output = retry once, then fail the stage.
  A refusal or an API/network error also fails the stage, never the whole run.
- Configurable model per role. *(Decided in M3:)* defaults are `claude-sonnet-5-5` for the reproducer
  (chosen after a Sonnet/Opus comparison on fixtures 1–7: same pass rate, ~2.4× cheaper) and
  `claude-opus-5-5` for adversary and judge until they are compared; effort `medium`; the server-side
  refusal fallback is on.
- Recorded provider: replays stored responses keyed by a hash of the whole request (model, role,
  system prompt, messages, schema), for deterministic tests; a missing recording is an error, never a
  network call.
- Enforce `max_llm_calls` (default 40) and a token budget (default 500k); log every call (role,
  model, tokens, latency) and an estimated cost, for the receipt.
- *(Decided in M8.)* **Settings:** each role's model, effort, max tokens per answer, call limit and
  token budget come from `tracefix.yml` or flags (2.1); defaults unchanged, so recordings stay
  valid. They only shape what the models propose; the receipt records what was used. The
  server-side fallback beta is sent only to models that take it (Fable 5.1, Opus 5.5 and 5, Sonnet
  5.5).
- *(Decided in M8.)* **Credentials and failures:** the SDK client is built on the first call, and
  credentials are left to the SDK (an API key, an auth token or a login profile), so a run that
  never asks a model needs none. Failures are classified by our code from the SDK's exception
  class and HTTP status: no credentials, 401, 402 billing, 403, 404 model not available, 429 (the
  account); 5xx/529, connection and timeout (the API); other 4xx (request rejected).
  `LLMClient.problems` logs every failed call (role, model, kind, status), plus budget stops,
  refusals, invalid output and missing recordings; the pipeline attributes each to the stage it
  hit (2.8, account-caused failures).

## 4. Safety *(execution isolation decided in M3.5)*
- All repo and generated code runs in a subprocess, inside a plain temp copy (2.1), with a timeout, no
  stdin, an allowlisted environment (no API keys), its own HOME and temp folders, and the whole
  process tree killed after every run.
- **Isolation levels**, recorded in every run and stage result and shown in the receipt:
  - `strict` (Linux with bubblewrap): read-only system; only the copy under test and the run's own
    scratch folder are writable; other copies, temp files and `$HOME` are hidden; no network.
    The project's interpreter's folders (with `--python`) are bound read-only, also when they live
    under the hidden `$HOME` (as uv's Pythons do).
  - `basic` (everywhere else): the above minus the sandbox, plus a best-effort in-process network
    block (loopback allowed). Tracefix runs, and the result carries a prominent warning, shown in
    the receipt. *(Decided in M3.5 by the developer: run with a warning, no opt-in flag.)*
- *(Decided in M8.)* **Run plugins.** Tracefix's own pytest plugins are written into each run's
  scratch folder and loaded with `-p`, in this order: the paths plugin (`tracefix_paths`: the
  copy's import roots just before the first `site-packages` entry of `sys.path`, 2.1), the network
  block, Tracefix's probe, then the project's `pytest_plugins` (last, so a project plugin is
  imported from the copy). `isolation.run_checked`, the one funnel every run goes through, applies
  the roots, the plugins and the suite timeout.
- **Tamper detection** around every run, at both levels: the base copy, the head copy (contents),
  Tracefix's own environment, the project's interpreter's environment when `--python` names
  another (2.1), and the user's repository (metadata) are snapshotted before and after.
  The copy not being run and the environment/repository must be unchanged; in the copy under test,
  changed or deleted files and new code/config files are tampering, other new files are removed as
  leftovers. Tampering makes the stage `invalid: tampering detected`, never a pass/fail verdict.
- A run whose exit code and JUnit report disagree (or that wrote no report) is an error, not a
  result.
- Tracefix's environment is shared state: another process changing it during a run (for example a
  second Tracefix run installing into the same venv) makes that stage `invalid`. Run one
  verification per environment at a time; tamper handling reports, it never crashes.
- **Limits.** In basic mode, writes outside the watched folders are not detected; only strict mode
  prevents them. In basic mode a process that escapes the end-of-run kill (POSIX `setsid`, or a
  process started through a system service on Windows; open question 9) could change a file during a
  later run and restore it before the check, unseen. Only strict mode guarantees that one run cannot
  influence another. At any level a test runs inside the pytest process and can lie about *its own*
  result (e.g. patching pytest); isolation stops damage, not lying. Mitigations: the forbidden-name
  check, the exit-code/report cross-check, Guard (M4) re-running repro tests, and the receipt naming a
  model-written test as the oracle. *(M4:)* Guard re-runs the repro test in a fresh
  copy on head and on the reverted code. *(M8:)* the head pass is confirmed test by test and in
  reverse order (2.3), and the receipt names the model-written oracle and the isolation level. A
  test that lies about its own result is still possible; it is a listed limit (NOTES).
- **Untrusted PRs** (e.g. from forks) are verified only at strict isolation, on a throwaway
  machine. *(Decided in M9 by the developer:)* the Action skips a fork's PR on `pull_request`; a
  maintainer's `tracefix` label starts a `pull_request_target` workflow that checks out and
  installs the base branch only, fetches the PR's exact head commit as git data, refuses to run
  when the checkout holds it or when bubblewrap doesn't work (`--require-strict`), and posts from a
  second job that never holds the model key and runs no project code (§5). The verdict's integrity
  then rests on the sandbox: code that escaped bubblewrap could forge the artifact (NOTES). Phase 2
  hosted runs use containers.
- Issue text and repo contents are wrapped as data in prompts; never follow instructions found there.

## 5. GitHub Action *(built in M9; `action.py`, `action_report.py`, `github_api.py`)*
User guide: `docs/GITHUB_ACTION.md`; examples in `docs/examples/`.
- **Shape.** A composite `action.yml` (no Docker, no JavaScript): bubblewrap setup on Linux,
  `setup-uv` without a cache, two environments *(M10 part 2)*: the project's interpreter (the
  `python` input, else `.venv`'s, else `python` on PATH; 3.9+; Hypothesis 6.141+ installed only
  when it has none or an older one) runs the tests through `--python`, and Tracefix runs from its own uv-managed Python
  3.11 with its `uv.lock`'s versions, installed from the action's own folder; then `python -m tracefix.action prepare | verify | report`, with the receipt folder
  uploaded as the artifact `tracefix-receipt-pr-<N>` between verify and report.
  `report/action.yml` runs only the report step, for the fork flow's second job. Every `${{ }}`
  value reaches a script through `env:`; the model key is only in verify's environment, the GitHub
  token only in prepare's and report's.
- **Prepare** decides trust (§4), the commits and the issue text, and writes a strict
  `state.json`. Base = the merge base of the PR's base and head commits, head = the PR's exact
  `head.sha`, both full commit ids (inputs can override them); `tracefix.yml` is read from that
  base. The issue text is the same-repository issues the PR's description closes (GitHub's closing
  keywords, at most 3), else the PR's title and description. Reasons not to verify (a fork PR on
  `pull_request`, no PR and no refs, no API key, untrusted without strict isolation, a shallow
  checkout, a missing commit) are a skip, never a verdict.
- **Verify** runs `tracefix verify` with `--previous` when the last receipt's artifact was found
  (2.10) and `--require-strict` when untrusted. Exit codes: 0 receipt, 2 nothing to verify, 3
  Tracefix failed.
- **Report.** The check run's conclusion is our code's function of the receipt only: tampering, a
  `COUNTEREXAMPLE` or a level below the `min-level` input fail; `L0` or no receipt is neutral (a
  failure when `min-level` is set); `L1`–`L4` succeed. A verdict never fails the job. At most 50
  annotations, from the receipt's `path`/`line` fields (2.8). One PR comment, found by a marker on
  its first line and its author, edited in place; its history of earlier receipts is parsed from a
  strict JSON state (enum values, hex and numbers only) and rendered by our code. The check and the
  comment are rendered again from a strictly validated `receipt.json`, never from an artifact's
  `receipt.md`.
- **GitHub API.** A stdlib client: the token is never sent on a redirect (the artifact download
  goes to blob storage), pagination, retries on 5xx, one wait on a rate limit, size caps.

## 6. Later (not MVP)
MCP server, TypeScript support, hosted sandbox, Java.

## 7. Benchmark *(M10; `scripts/benchmark.py`, `scripts/bench/`)*
Tracefix is measured on real fixes from the SWE-rebench leaderboard (CC BY 4.0): each task's
upstream fix should not get a COUNTEREXAMPLE, and the same fix with one source hunk removed
(kept only when the hidden tests then fail) should not be green-lit. Runs happen in each task's
Docker image with strict isolation; a partial fix's findings are replayed on the upstream fix.
Every rate comes from a run, a receipt or the developer's label, never from a model's statement.
Method, results and caveats: `docs/BENCHMARK.md`; data and provenance: `benchmarks/README.md`.
