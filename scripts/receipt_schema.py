"""Write docs/receipt.schema.json from the receipt's models (tracefix.receipt).

tests/test_receipt.py fails when the committed file differs from what this writes, so the schema
agents read can't drift from the receipts Tracefix writes.

Usage: uv run python scripts/receipt_schema.py
"""

import json
from pathlib import Path

from tracefix.receipt import schema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = ROOT / "docs" / "receipt.schema.json"


def text() -> str:
    return json.dumps(schema(), indent=2, sort_keys=True) + "\n"


if __name__ == "__main__":
    SCHEMA_FILE.write_text(text(), encoding="utf-8", newline="\n")
    print(f"wrote {SCHEMA_FILE.relative_to(ROOT).as_posix()}")
