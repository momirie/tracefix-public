"""Extract slice 2's agent runs from the OpenHands trajectories' parquet file (run once).

    uv run --with pyarrow==18.1.0 python scripts/extract_agents.py

Downloads `trajectories.parquet` (2 GB) at the dataset's current revision into
benchmarks/cache/ (once), checks its sha256 against the Hub's LFS id, reads four of its columns
and writes the runs file bench.agents reads (`agents.group`: strict parsing, a bad run dropped
and counted). Then it pins the revision and both digests in benchmarks/sources.json.

pyarrow is not a Tracefix dependency: only this script needs it, through `uv run --with`
(DECISIONS 2026-10-21). Everything it reads is untrusted data; only the four columns are read.
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-not-found]
from bench import agents, data

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks"
CHUNK = 1024 * 1024


def lfs_sha256(revision: str) -> tuple[str, int]:
    """The parquet file's sha256 and size, as the Hub lists them at this revision."""
    url = f"{data.INFO_API}{agents.DATASET}/tree/{revision}"
    entries = data.parse_json(data.patient_get(url), "the file list")
    for entry in entries if isinstance(entries, list) else []:
        if isinstance(entry, dict) and entry.get("path") == agents.FILE:
            lfs = entry.get("lfs") or {}
            oid, size = lfs.get("oid"), lfs.get("size")
            if isinstance(oid, str) and len(oid) == 64 and isinstance(size, int):
                return oid, size
    raise data.DataError(f"{agents.FILE} has no LFS id at {revision}")


def file_digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(CHUNK):
            sha.update(block)
    return sha.hexdigest()


def download(revision: str, path: Path, sha256: str, size: int) -> None:
    """The parquet file at `path`, unless a copy with the right digest is already there."""
    if path.is_file() and file_digest(path) == sha256:
        return
    url = f"https://huggingface.co/datasets/{agents.DATASET}/resolve/{revision}/{agents.FILE}"
    partial = path.with_suffix(".part")
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "tracefix-benchmark"})
    sha, got = hashlib.sha256(), 0
    with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as out:
        while block := response.read(CHUNK):
            got += len(block)
            if got > size:
                raise data.DataError(f"{agents.FILE} is larger than the Hub says")
            sha.update(block)
            out.write(block)
            if got % (256 * CHUNK) < len(block):
                print(f"  {got // CHUNK} of {size // CHUNK} MB", file=sys.stderr, flush=True)
    if sha.hexdigest() != sha256:
        partial.unlink()
        raise data.DataError(f"{agents.FILE} doesn't match the Hub's sha256")
    partial.replace(path)


def rows(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    """(row index, the four kept fields) for every row, in the file's order."""
    parquet = pq.ParquetFile(path)
    missing = set(agents.COLUMNS) - set(parquet.schema_arrow.names)
    if missing:
        raise data.DataError(f"{agents.FILE} has no column {sorted(missing)[0]}")
    index = 0
    for batch in parquet.iter_batches(batch_size=2_000, columns=list(agents.COLUMNS)):
        for row in batch.to_pylist():
            yield index, row
            index += 1


def main() -> int:
    revision = data.current_revision(data.patient_get, agents.DATASET)
    sha256, size = lfs_sha256(revision)
    cache = BENCH / "cache"
    parquet = cache / f"{agents.NAME}-{revision}.parquet"
    download(revision, parquet, sha256, size)
    counted = 0

    def counting() -> Iterator[tuple[int, dict[str, Any]]]:
        nonlocal counted
        for item in rows(parquet):
            counted += 1
            if counted > agents.MAX_ROWS:
                raise data.DataError(f"{agents.FILE} has more rows than {agents.MAX_ROWS}")
            yield item

    tasks, unreadable = agents.group(counting())
    blob = agents.encode(tasks)
    if data.current_revision(data.patient_get, agents.DATASET) != revision:
        raise data.DataError(f"{agents.DATASET} changed during the extraction")
    out = agents.runs_path(cache, revision)
    out.write_bytes(blob)
    pin = agents.Pin(
        dataset=agents.DATASET,
        revision=revision,
        file=agents.FILE,
        file_sha256=sha256,
        rows=counted,
        unreadable_rows=unreadable,
        runs_sha256=data.digest(blob),
        license=data.LICENSE,
        url=f"https://huggingface.co/datasets/{agents.DATASET}",
    )
    agents.write_pin(BENCH / "sources.json", pin)
    runs = sum(len(t.runs) for t in tasks)
    summary = {
        "rows": counted,
        "tasks": len(tasks),
        "runs_kept": runs,
        "runs_dropped": sum(t.dropped for t in tasks),
        "rows_without_id": unreadable,
        "resolved": sum(r.resolved for t in tasks for r in t.runs),
        "submitted": sum(r.submitted for t in tasks for r in t.runs),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except data.DataError as exc:
        print(f"extract_agents: {exc}", file=sys.stderr)
        sys.exit(2)
