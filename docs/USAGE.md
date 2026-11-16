# Using Tracefix

Tracefix runs your tests, so they need your project's environment, the one with your
dependencies, pytest and Hypothesis. It isn't on PyPI yet: install it from a clone, then point it
at a fix. On Python 3.11.4+ the simplest is Tracefix in that environment:

```
uv add --dev /path/to/tracefix         # into the project you want to verify
uv run tracefix verify --repo . --base main --head my-fix --issue issue.md
```

A project on Python 3.9 to 3.11.3 (or any project you'd rather keep Tracefix out of) uses two
environments: Tracefix in its own (Python 3.11.4+), and `--python` naming the project's interpreter,
which runs the tests:

```
uv tool install /path/to/tracefix
uv pip install --python .venv/bin/python hypothesis   # Break My Fix and the behaviour diff need it
tracefix verify --repo . --base main --head my-fix --issue issue.md --python .venv/bin/python
```

Tracefix checks that interpreter once before anything runs (3.9 or newer, with pytest) and names
its version in the receipt. Without Hypothesis there, or older than 6.141, Break My Fix and the
behaviour diff are inconclusive and say how to install it. Below Python 3.11 the behaviour diff
can't prove that the reproduction test's calls ran (Python gives no column positions before 3.11),
so they don't count: a change only they would explain keeps the receipt below L3, and it says
why.

## Input and output

- `--issue` takes a file, the text itself, or `-` for stdin.
- The receipt goes to `./tracefix-receipt/` (`--out DIR`): `receipt.md`, `receipt.json`, the
  reproduction test in `repro/` and each finding's pytest file in `findings/`. See
  [an example receipt](EXAMPLE_RECEIPT.md).
- `--json` prints the receipt JSON alone on stdout, for agents and scripts; progress goes to
  stderr.
- The exit code is 0 whenever a receipt was written, whatever the level; 2 when there was
  nothing to verify (not a git repo, unknown ref, bad settings, empty issue, an `--out` that can't
  be written); 3 when Tracefix itself failed (a bug in Tracefix: the message and traceback are on
  stderr).
- `--python PATH` (command line only, since a path belongs to the machine): the interpreter that
  runs the project's tests, as above. Default: Tracefix's own.
- `--require-strict` refuses to run (exit 2, with the reason) unless the tests can run at strict
  isolation (bubblewrap, Linux), before any copy of the code is made. Use it for code you don't
  trust.
- `--previous DIR` replays an earlier receipt: DIR is an earlier `--out` folder (or the Action's
  artifact) with `receipt.json` and `findings/`. Each of its findings runs again on `--head`, and
  the new receipt says which ones this commit fixed (a finding counts as fixed after 3 clean
  passes in a row). L4 also needs every one of them fixed; one that still fails never makes a
  COUNTEREXAMPLE by itself. A missing folder or `receipt.json` is exit 2; content that can't be
  used is noted in the receipt and the run goes on. See [`SPEC.md`](SPEC.md) 2.10.

## Model credentials and cost

The models need Anthropic API credentials (`ANTHROPIC_API_KEY`, or another form the Anthropic SDK
reads). The [example receipt](EXAMPLE_RECEIPT.md) made 8 model calls (about $0.15 at list
prices); every receipt shows the calls, tokens and an estimated cost. If your account hits a limit
(rate limit, no access to a model, no credit left), the receipt says so on the stage it hit, so
lower evidence isn't blamed on your fix.

## Settings

In `tracefix.yml` at the base commit (the fix under test can't change how it is verified) or as
flags, which win:

| Setting | Flag | Default |
|---|---|---|
| `suite_timeout_seconds` | `--suite-timeout SECONDS` | 300 |
| `max_llm_calls` | `--max-llm-calls N` | 40 |
| `token_budget` | `--token-budget N` | 500,000 |
| `max_tokens` (per answer) | `--max-tokens N` | 16,000 |
| `effort` | `--effort low\|medium\|high\|xhigh\|max` | `medium` |
| `models` (per role) | `--model ROLE=MODEL` (repeatable) | Sonnet 5.5 for the reproducer and mutator, Opus 5.5 for the adversary and judge |
| `pytest_plugins` | `--pytest-plugin MODULE` (repeatable) | none (plugin autoload is off) |

`--config FILE` uses another settings file instead. Settings only shape what the models propose
and how long runs may take; none of them decides a verdict. `tracefix verify --help` lists every
flag.

## Running untrusted changes

Tracefix runs the repository's tests and tests written by a model, whose input includes the issue
text. A fix from someone you don't trust, such as a pull request from a fork, is untrusted code.

Isolation is built into every test run, at one of two levels, recorded with each result:
- **strict** (Linux with [bubblewrap](https://github.com/containers/bubblewrap) installed, e.g.
  `apt install bubblewrap`): read-only system, only a temporary copy of the code writable, no
  network, no access to your home folder.
- **basic** (Windows, macOS, Linux without bubblewrap): temporary copies, a private home and temp
  folder, no secrets in the environment, a best-effort network block, and tamper detection around
  every run. Results carry a warning. That is fine for changes you would run `pytest` on anyway,
  not for untrusted code.

Untrusted changes should be verified on Linux with bubblewrap and `--require-strict`, ideally
on a throwaway machine. On GitHub, [the Action's fork flow](GITHUB_ACTION.md#fork-pull-requests)
does that for pull requests from forks: a maintainer's label approves each commit, strict
isolation is required, and the job that posts results never holds the API key. A later hosted
version will run in containers. See [`SPEC.md`](SPEC.md) §4 for the details and limits.
