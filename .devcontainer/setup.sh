#!/usr/bin/env bash
# Runs once when the codespace is created: bubblewrap, uv, the project, then a strict-mode check.
set -euo pipefail

# The base image lists a Yarn package source whose signing key has expired, which makes
# `apt-get update` fail; Tracefix doesn't use Yarn. The file's name differs between image
# versions, so remove whichever source file names it.
{ sudo grep -rl yarnpkg /etc/apt/sources.list.d/ || true; } | xargs -r sudo rm -f
sudo apt-get update -q
sudo apt-get install -y -q bubblewrap
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv sync --locked

# Tracefix's own check (its real sandbox, with a fresh /proc), not just whether bwrap starts.
level=$(uv run python -c "from tracefix.sandbox import probe; print(probe()[0])")
uv run python -c "from tracefix.sandbox import probe; print('isolation level:', probe())"
if [ "$level" != "strict" ]; then
  echo "strict mode is NOT available here: strict-mode tests will fail (see README.md)" >&2
fi
