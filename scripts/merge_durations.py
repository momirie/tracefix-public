"""Merge the test times each Windows CI job measured into one durations file (Windows CI fit).

    python scripts/merge_durations.py BASE JOB_FILE... --out OUT

Each Windows job starts from BASE (`.test_durations_windows`), runs its share of the tests with
pytest-split's `--store-durations` and uploads the file: its own tests carry new times, the rest
still hold BASE's. A time that differs from BASE, or a test BASE doesn't know, came from the job
that ran it. Tests nobody measured keep BASE's time, so a job cut off by its timeout loses only
its own share. Standard library only: the merge job runs it without installing anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

Durations = dict[str, float]


def load(path: Path) -> Durations:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(
        isinstance(k, str) and isinstance(v, int | float) for k, v in data.items()
    ):
        raise ValueError(f"{path}: not a durations file (test id -> seconds)")
    return {k: float(v) for k, v in data.items()}


def measured(base: Durations, job: Durations) -> Durations:
    """The times this job wrote: new tests, and times that differ from BASE."""
    return {k: v for k, v in job.items() if k not in base or v != base[k]}


def merge(base: Durations, jobs: list[Durations]) -> tuple[Durations, list[str]]:
    """BASE with every job's measured times. A test two jobs measured (it should run in one
    group only) keeps the longer time and is returned, so the caller can warn."""
    merged, seen, twice = dict(base), set[str](), list[str]()
    for job in jobs:
        for test, seconds in measured(base, job).items():
            if test in seen:
                twice.append(test)
                seconds = max(seconds, merged[test])
            merged[test] = seconds
            seen.add(test)
    return merged, sorted(set(twice))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base", type=Path)
    parser.add_argument("jobs", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    base = load(args.base)
    jobs = [load(path) for path in args.jobs]
    merged, twice = merge(base, jobs)
    for test in twice:
        print(f"warning: measured by more than one job (kept the longer time): {test}")
    for path, job in zip(args.jobs, jobs, strict=True):
        times = measured(base, job)
        print(f"{path}: {len(times)} tests, {sum(times.values()) / 60:.1f} min")
    text = json.dumps(merged, sort_keys=True, indent=4)  # pytest-split's own layout
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"{args.out}: {len(merged)} tests, {sum(merged.values()) / 60:.1f} min in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
