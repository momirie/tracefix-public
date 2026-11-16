# Contributing

## Development setup

Requirements: Python 3.11.4 or newer, git 2.32 or newer, and [uv](https://docs.astral.sh/uv/).
Optional on Linux: bubblewrap, so tests run with strict isolation.

```
uv sync                       # create .venv with Tracefix and the dev tools
uv run pytest -q              # run the tests (no network or API key needed)
uv run ruff check .           # lint
uv run ruff format --check .  # formatting
uv run mypy                   # type-check (src and scripts/bench)
uv run tracefix verify --help # CLI usage
```

Or run everything CI runs, in parallel, with one command (`--fast` skips the test suite):

```
uv run python scripts/check.py
```

The suite runs real pytest sessions inside watched temporary copies, so it is not quick: about
30 minutes in parallel on a 16-core Windows laptop since M8's end-to-end acceptance test (the
whole pipeline on all ten fixtures); plain `pytest -q` runs serially and takes much longer.

Strict isolation (bubblewrap) runs only on Linux. With Docker Desktop running, run Linux CI's
checks on your own machine (free, no CI minutes); the container gets what `git add -A` would
commit:

```
uv run python scripts/check_linux.py                 # Python 3.11; --python 3.13; --fast
```

CI splits the suite over several jobs (pytest-split, balanced by `.test_durations`):

- every PR, once it is ready for review (drafts skip CI): Linux, Python 3.11 and 3.13, two jobs
  each (`ci.yml`). Not on push to `main`: the PR's run already tested what merges. Run it by
  hand from the Actions tab when needed;
- on demand: Windows, Python 3.13, five jobs (`ci-windows.yml`). Add the `ci-windows` label to a
  PR to run it, and remove and re-add the label to run it again after new pushes. Every
  milestone gets it before merging.

Both call the same steps (`.github/workflows/tests.yml`). `all-checks` is the one check `main`
requires.

Opt-in live test (calls the Anthropic API, costs a little money; needs `ANTHROPIC_API_KEY`):

```
TRACEFIX_LIVE=1 uv run pytest -m live              # bash
$env:TRACEFIX_LIVE = "1"; uv run pytest -m live    # PowerShell
```

## Fixtures

The fixture repositories in `tests/fixtures/` are built into real git repos by
`scripts/make_fixtures.py`. See [`tests/fixtures/README.md`](tests/fixtures/README.md) for each case
and its expected result. They are the ground truth: never change an expected answer to make a test
pass.

## Where things are

- [`docs/SPEC.md`](docs/SPEC.md): the specification.
- [`docs/ROADMAP.md`](docs/ROADMAP.md): milestone status (the only place it is kept).
- [`docs/MILESTONES.md`](docs/MILESTONES.md): the plan and acceptance criteria.
