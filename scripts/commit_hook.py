"""Claude Code PreToolUse hook: run `scripts/check.py --fast` before a `git commit`, and block the
commit (exit 2) if it fails.

Reads the hook's JSON from stdin and acts only when the command really runs `git commit`: the
settings' `if` filter also matched other commands (journal 2026-10-03), and then blocked plain
reads whenever the work in progress didn't pass the checks yet.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# `git [options] commit`; an option may take one value (`git -c user.name=x commit`).
COMMIT = re.compile(r"(?:^|[;&|(\s])git\s+(?:-\S+(?:\s+[^-\s]\S*)?\s+)*commit\b")


def main() -> int:
    try:
        command = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    except (ValueError, AttributeError):
        return 0
    if not isinstance(command, str) or not COMMIT.search(command):
        return 0
    check = Path(__file__).with_name("check.py")
    result = subprocess.run([sys.executable, str(check), "--fast"], stdout=sys.stderr, check=False)
    return 0 if result.returncode == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
