"""Claude Code PostToolUse hook: format a Python file right after Claude edits or writes it.

Reads the hook's JSON from stdin. Only `ruff format` (layout), never `ruff check --fix`: a fix such
as removing an unused import would undo an edit made one step before its use. Ruff's own excludes
apply (`--force-exclude`), so the fixture repos are never touched. Never fails the edit.
"""

import json
import subprocess
import sys


def main() -> int:
    try:
        path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
    except (ValueError, AttributeError):
        return 0
    if isinstance(path, str) and path.endswith(".py"):
        subprocess.run(["ruff", "format", "--force-exclude", "--quiet", path], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
