# Example receipt

A real receipt from one of the test fixtures, `partial_fix`: the issue says the service crashes
when `PORT` is not set, and the fix handles a missing value but not an empty one. Tracefix
reproduced the bug, found the fix guarded, then broke it with an empty string, and wrote a
standalone pytest file that proves it. (Made with recorded model answers, replayed without an API
call; "Model use" is what those answers cost when they were recorded. Headings are shrunk to fit
this page.)

#### Fix Receipt: COUNTEREXAMPLE (concrete evidence against this fix)

**Summary** (advisory, written by the model claude-opus-5-5; it never sets the level): The original crash was reproduced and the fix guards against it (PORT unset no longer raises, with no regressions found), but Break My Fix found that parse\_port(raw='') still raises ValueError: invalid literal for int() with base 10: ''. Next, check whether an empty PORT value should also fall back to 8080 as the README describes, and handle that case.

**Why this level:** Break My Fix finding 1: an input that breaks svc.config.parse\_port

**Issue:** Service crashes at startup when PORT is not set · **Repo:** partial\_fix · **Base** `base` (`878c55e`) → **head** `head` (`8c47ba4`)\
**Isolation:** basic (bubblewrap needs Linux (this is win32))

> [!WARNING]
> - Generated tests ran with basic isolation only (no bubblewrap sandbox): tampering inside the watched folders is detected, but code could still read or write elsewhere on this machine, and a process that escaped could influence a later run. For untrusted changes run Tracefix in GitHub Actions or on Linux with bubblewrap.

##### Counterexamples
1. `parse_port(raw='')` → `raises ValueError: invalid literal for int() with base 10: ''` (before the fix: `raises ValueError: invalid literal for int() with base 10: ''`); breaks **blank\_returns\_default**: “if unset or blank, DEFAULT\_PORT (8080) is used” (docstring); 3 more inputs break it the same way; test: `findings/finding_1.py`

##### Stages
| Stage | Status | Key numbers |
|---|---|---|
| `environment` | `ok` | base suite passed |
| `import_check` | `ok` | modules 1 |
| `reproduce` | `reproduced` | attempts 1 |
| `guard` | `guarded` | kill rate 1\.0, mutants 4, killed 4, survived 0 |
| `regressions` | `none_found` | compared 5, regressions 0, unconfirmed 0 |
| `fix_line_coverage` | `ok` | fix lines 2 |
| `behaviour_diff` | `compared` | inputs compared 200, changes 1, groups 1 |
| `break_my_fix` | `found` | targets 1, inputs tried 420, properties counted 6, findings 1 |
| `integrity` | `clean` | flags 0 |

##### Behaviour changes
- `svc.config.parse_port` (`no_raise`, 1 input): `raises AttributeError` → `returns 8080`; explained by: the reproduction test calls this input; the Judge (advisory) calls it intended: The issue reports the AttributeError when PORT is unset, and the README and docstring say unset PORT falls back to 8080.

- **Not checked:** concurrency; database state; network and external services; authentication and authorisation; performance; configuration; 9 things the behaviour diff can't observe (run log)
- **Model use:** 8 calls, 21,638 input and 4,057 output tokens, cost $0.1523 (estimate at list prices)

<sub>Below this, `receipt.md` has a collapsed run log: every command run, what was not checked,
and the model settings. `receipt.json` holds the same receipt for programs and agents.</sub>

The finding's file, `findings/finding_1.py`, written by Tracefix and failing on the fixed code:

<!-- fmt:off -->
```python
from svc.config import parse_port


def test_break_my_fix_1() -> None:
    raw = ''
    # The property applies to this input: raw is not None and raw.strip() == ''
    result = parse_port(raw=raw)
    assert result == (8080)
```
<!-- fmt:on -->
