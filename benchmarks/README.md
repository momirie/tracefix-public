# Benchmarks

Data, labels and results of Tracefix's benchmark. The harness that makes them is
`scripts/benchmark.py` with the `scripts/bench/` package. Method, results and caveats:
`docs/BENCHMARK.md`.

## At a glance

Slice 2's dev split, run with M11's code (13 Nov 2026; the full table is the release gate in
`docs/ROADMAP.md`). These are fixes Tracefix was tuned on, so they show the direction, not a
gate passed; the held-out split is still unrun.

| | Result | Target |
|---|---|---|
| Correct fixes (gold) certified at L2 or above | 11/47 (23%) | ≥ 50% |
| False alarms on correct fixes | 7/85 (8%) | ≤ 5% |
| Wrong agent fixes not green-lit | 16/20 (80%) | ≥ 90% |
| Median / 90th percentile time per run | 3.2 min / 14.7 min | ≤ 5 min / ≤ 15 min |

The summaries are `results/<set>/report.md` (and `results/slice2-m11/compare-slice2.md` for
M11 against M10). The receipt folders beside them are the raw evidence each number is rebuilt
from; a test checks the rebuild byte for byte.

## Where the tasks come from

- **SWE-rebench leaderboard** (`nebius/SWE-rebench-leaderboard`, split `test`), by Nebius:
  <https://huggingface.co/datasets/nebius/SWE-rebench-leaderboard>, paper arXiv:2505.20411.
  Licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- The revision used, the row count and the sha256 of the rows are pinned in `sources.json`. The
  harness refuses other rows unless asked to re-pin (`select --repin`).
- Changes made to the data: only a subset of each row's fields is kept, and rows are filtered and
  ordered by the rules in the plan (P3). Field values are not edited.

## Files

| Path | What | In git |
|---|---|---|
| `sources.json` | the dataset pin | yes |
| `cases/<slice>.jsonl` | the chosen tasks, in rank order, with their dev/held-out split | yes |
| `cases/<slice>.funnel.json` | every row left out, with its reason, and the counts | yes |
| `cache/` | the downloaded rows (re-made from the pin) | no |
| `prepared/<slice>/<id>.json` | each task after `prepare`: excluded with a reason, or ready (commits, suite timeout, plugins, the kept partial-fix variant) | yes |
| `results/<slice>/runs.jsonl` | one line per `run` (a run's last line counts; harness errors are tried again) | yes |
| `results/<slice>/<id>/<run>/` | that run's receipt folder (`receipt.json`, `receipt.md`, findings, repro test) | yes |
| `results/<slice>/summary.json`, `report.md` | the numbers, rebuilt by `report` from the files above and the labels | yes |
| `labels/<slice>.json` | the developer's label for each finding that needs one (`label` adds empty entries; finding `0` is a gold COUNTEREXAMPLE with no finding, labelled as the run itself) | yes |
| `work/`, `recordings/` | per-task work folders, model recordings | no |

Make or refresh a slice: `uv run python scripts/benchmark.py select --slice slice1 --limit 60`.
Then `prepare --limit N`, `run` (add `--live --max-spend USD` to call the model API), `label`,
`report`; `uv run python scripts/benchmark.py --help` lists the options.
