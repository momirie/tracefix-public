<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/brand/masters/tracefix-horizontal-reversed.svg">
  <img src="docs/brand/masters/tracefix-horizontal.svg" alt="Tracefix" width="300">
</picture>

**An independent fix verifier for Python: executed evidence that a bug fix works, and concrete inputs that break it.**

[![CI](https://github.com/momirie/tracefix/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/momirie/tracefix/actions/workflows/ci.yml)
[![Status: pre-alpha](https://img.shields.io/badge/status-pre--alpha-orange)](docs/ROADMAP.md)
[![Python 3.11.4+](https://img.shields.io/badge/python-3.11.4%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

Tracefix takes a bug fix (from a coding agent or a person) as a base ref, a head ref and the
issue text, runs it, and writes a **Fix Receipt**: whether the bug reproduces, whether the fix
removes it, whether the tests guard it, and the inputs that still break it (**Break My Fix**).
Models propose tests, mutants and properties; every verdict comes from an exit code, a diff or a
counter computed by Tracefix's own code.

The overview, a live replay and the four ways a green fix goes wrong are on the
[website](docs/landing/). This README is the technical reference.

## Requirements

| For | Needs |
|---|---|
| Tracefix | Python **3.11.4+**, git 2.32+ |
| The project under test | pytest on Python 3.9+ (in its own environment, also Hypothesis 6.141+) |
| Models | An Anthropic API key (`ANTHROPIC_API_KEY`); the code and the issue are sent to Anthropic's API |
| Strict isolation (optional) | Linux with [bubblewrap](https://github.com/containers/bubblewrap) |

## Install and run

Not on PyPI yet. Install from a clone into the project you want to check: Tracefix runs its tests,
so it needs its dependencies.

```bash
git clone https://github.com/momirie/tracefix ~/tracefix
uv add --dev ~/tracefix                 # pip: pip install ~/tracefix, then drop "uv run"
export ANTHROPIC_API_KEY=sk-ant-...
uv run tracefix verify --repo . --base main --head my-fix \
    --issue "Service crashes at startup when PORT is not set"
```

A project on Python 3.9 to 3.11.3 keeps its own environment: install Tracefix with
`uv tool install ~/tracefix` and pass `--python .venv/bin/python` so the project's interpreter runs
the tests ([`docs/USAGE.md`](docs/USAGE.md)).

| What | How |
|---|---|
| Input | `--issue` takes text, a file, or `-` for stdin. Settings: `tracefix.yml` at the base commit, or flags |
| Output | `tracefix-receipt/` (`--out DIR`): `receipt.md` (safe as a PR comment), `receipt.json` ([schema](docs/receipt.schema.json)), `repro/`, `findings/` |
| `--json` | Receipt JSON alone on stdout, progress on stderr |
| Exit codes | `0` a receipt was written (any level) · `2` nothing to verify (bad ref, empty issue, `--require-strict` without bubblewrap) · `3` Tracefix crashed |
| Cost and time | About 5 minutes and $0.15 on a small project ([example receipt](docs/EXAMPLE_RECEIPT.md)); every receipt shows calls, tokens and cost |

Every flag: `tracefix verify --help` and [`docs/USAGE.md`](docs/USAGE.md).

## GitHub Action

Runs on every push to a pull request, posts a `Tracefix` check, one receipt comment edited in
place, and annotations on the fixed lines. Fork PRs need a maintainer's label and strict isolation
([`docs/GITHUB_ACTION.md`](docs/GITHUB_ACTION.md), workflows in [`docs/examples/`](docs/examples/)).

```yaml
on: pull_request
permissions: {}
jobs:
  tracefix:
    runs-on: ubuntu-24.04
    permissions: {contents: read, checks: write, pull-requests: write, issues: read, actions: read}
    steps:
      - uses: actions/checkout@<sha>
        with: {fetch-depth: 0, persist-credentials: false}
      - uses: astral-sh/setup-uv@<sha>
      - run: uv sync --locked
      - uses: momirie/tracefix@<sha>
        with:
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Pipeline

| Stage | Passes when | Module |
|---|---|---|
| Environment | Every changed module imports from the copy under test | `envcheck.py` |
| Reproduce | A generated test fails on base and passes on head, both by running | `repro.py` |
| Guard | Reverting the fix, or planting mutants in it, makes a test fail | `guard.py` |
| No regressions | Untouched tests that passed on base still pass on head | `regressions.py` |
| Behaviour diff | Same generated inputs on base and head; every changed outcome is explained | `behaviour_diff.py` |
| Break My Fix | Properties, boundaries and a Hypothesis search find no failing input on head | `attack.py` |
| Integrity audit | No weakened assert, new `skip` or special case that hid a failure | `integrity.py` |

A Break My Fix finding counts only with a pytest file that fails on head. Stage details and limits:
[`docs/SPEC.md`](docs/SPEC.md) §2.

## Evidence levels

| Level | Meaning |
|---|---|
| ![COUNTEREXAMPLE](https://img.shields.io/badge/-COUNTEREXAMPLE-cf222e) | Proof against the fix: a breaking input, a regression, a weakened test, or the bug isn't fixed |
| ![L0](https://img.shields.io/badge/-L0-6e7781) | Not reproduced, the tests couldn't run, or tampering was detected |
| ![L1](https://img.shields.io/badge/-L1-bf8700) | Reproduced: a test fails before the fix and passes after it |
| ![L2](https://img.shields.io/badge/-L2-9a9a00) | L1, and the tests guard the fix |
| ![L3](https://img.shields.io/badge/-L3-4c9a2a) | L2, and every behaviour change the diff observed is explained |
| ![L4](https://img.shields.io/badge/-L4-1a7f37) | L3, and a full Break My Fix attack found nothing |

L4 means "tried hard to break it and nothing broke", never "this is correct". The ladder and the
strict L4 gate: `src/tracefix/ladder.py`.

## Isolation

Generated and repository code runs only in temporary copies, under a timeout, with a tamper watch
around every run. **Strict** (Linux + bubblewrap): read-only system, no network, no home folder.
**Basic** (everywhere else): private home and temp, no secrets in the environment, best-effort
network block; fine for code you'd run `pytest` on anyway. Use `--require-strict` for untrusted
changes ([`docs/USAGE.md`](docs/USAGE.md#running-untrusted-changes), [`docs/SPEC.md`](docs/SPEC.md) §4).

## Documentation

| Doc | Covers |
|---|---|
| [`docs/USAGE.md`](docs/USAGE.md) | Flags, settings, two-environment setup, untrusted changes |
| [`docs/SPEC.md`](docs/SPEC.md) | Every stage, the receipt format, safety |
| [`docs/GITHUB_ACTION.md`](docs/GITHUB_ACTION.md) | The Action, fork PRs, permissions |
| [`docs/EXAMPLE_RECEIPT.md`](docs/EXAMPLE_RECEIPT.md) | A real receipt (`partial_fix`, COUNTEREXAMPLE) |
| [`docs/BENCHMARK.md`](docs/BENCHMARK.md) | Results on real fixes, false-alarm rates |
| [`tests/fixtures/`](tests/fixtures/README.md) | Known-answer buggy repos the suite checks every receipt against |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Status and release gates |

## Development

```bash
uv sync
uv run python scripts/check.py          # everything CI runs; --fast skips the tests
```

The test suite needs no network or API key (recorded model answers). Setup, test groups and Linux
checks in Docker: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

MIT. See [`LICENSE`](LICENSE).
