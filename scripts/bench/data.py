"""Benchmark data in: SWE-rebench rows, pinned and parsed strictly (M10 plan P2).

Two task datasets share one row schema: the leaderboard (slice 1) and SWE-rebench itself
(slice 2, M10 part 2 plan C1). Rows come from Hugging Face's datasets-server JSON API (stdlib
only) and are cached under `benchmarks/cache/` as canonical JSONL. Each dataset's revision, its
row count and the sha256 of that JSONL are pinned in `benchmarks/sources.json`: a different
revision or different rows are refused unless the caller asks to re-pin.

Every row is untrusted text (CLAUDE.md rule 7). It becomes a frozen `Task` with size caps and
fixed patterns, or it is rejected with a reason built from our own field names and error codes
(never from the row's text). A bad row is never half-used.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    model_validator,
)
from pydantic_core import PydanticCustomError

LICENSE = "CC BY 4.0"
ROWS_API = "https://datasets-server.huggingface.co/rows"
INFO_API = "https://huggingface.co/api/datasets/"
PAGE_ROWS = 100  # the API's maximum page size
MAX_RESPONSE_BYTES = 64 * 1024 * 1024
MAX_WAIT_SECONDS = 300.0  # the longest wait between two tries
RETRY_CODES = frozenset({429, 500, 502, 503, 504})

MAX_ISSUE_CHARS = 100_000
MAX_PATCH_BYTES = 1_000_000
MAX_HIDDEN_TESTS = 5_000
MAX_TEST_ID_CHARS = 2_000
MAX_COMMAND_CHARS = 10_000

Get = Callable[[str], bytes]  # url -> response body
RawRow = dict[str, Any]  # {"row_idx": int, "row": {...}} as the API returns it


@dataclass(frozen=True)
class Dataset:
    """One split of a Hugging Face dataset, and its key in sources.json and the cache."""

    name: str
    id: str
    config: str
    split: str
    max_rows: int  # a larger row count is refused

    @property
    def url(self) -> str:
        return f"https://huggingface.co/datasets/{self.id}"


LEADERBOARD = Dataset(
    "swe-rebench-leaderboard", "nebius/SWE-rebench-leaderboard", "default", "test", 10_000
)
REBENCH = Dataset("swe-rebench", "nebius/SWE-rebench", "default", "test", 30_000)


class DataError(Exception):
    """The source could not be read, or it doesn't match its pin."""


class InvalidRow(Exception):
    """One row failed strict parsing; `str(exc)` is a reason in our own words."""


def _pattern(pattern: str, max_length: int = 300) -> StringConstraints:
    return StringConstraints(max_length=max_length, pattern=pattern)


def _no_nul(value: str) -> str:
    if "\x00" in value:
        raise PydanticCustomError("nul_character", "contains a NUL character")
    return value


def _patch_size(value: str) -> str:
    if len(value.encode("utf-8", "surrogatepass")) > MAX_PATCH_BYTES:
        raise PydanticCustomError("too_large", "larger than the patch cap")
    return value


Sha = Annotated[str, _pattern(r"^[0-9a-f]{40}$")]
Digest = Annotated[str, _pattern(r"^[0-9a-f]{64}$")]
InstanceId = Annotated[
    str, _pattern(r"^[A-Za-z0-9][A-Za-z0-9_.-]*__[A-Za-z0-9_.-]+-[0-9]+(?:_interface)?$", 200)
]
Repo = Annotated[str, _pattern(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9_.-]+$", 200)]
Image = Annotated[
    str, _pattern(r"^(?:swerebench/sweb\.eval\.x86_64\.[a-z0-9][a-z0-9_.-]*:latest)?$")
]
PythonVersion = Annotated[str, _pattern(r"^[0-9]{1,2}\.[0-9]{1,3}(?:\.[0-9]{1,3})?$")]
# "2025-06-13 10:18:30", newer rows add an offset: "2026-01-05 09:00:00+00:00".
Timestamp = Annotated[
    str,
    _pattern(r"^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}(?:[+-][0-9]{2}:[0-9]{2})?$"),
]
# A pytest node id: a .py path, then ::, then names; no control characters.
TestId = Annotated[str, _pattern(r"^[^\x00-\x1f\x7f]+\.py::[^\x00-\x1f\x7f]+$", MAX_TEST_ID_CHARS)]
Patch = Annotated[str, AfterValidator(_no_nul), AfterValidator(_patch_size)]
Issue = Annotated[str, StringConstraints(max_length=MAX_ISSUE_CHARS), AfterValidator(_no_nul)]
Command = Annotated[str, StringConstraints(max_length=MAX_COMMAND_CHARS), AfterValidator(_no_nul)]


def image_for(instance_id: str) -> str:
    """SWE-rebench's image name for a task (holds for every row of the pinned revisions)."""
    return f"swerebench/sweb.eval.x86_64.{instance_id.lower().replace('__', '_1776_')}:latest"


class Task(BaseModel):
    """One benchmark task: only the fields the harness uses, plus where it came from."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    instance_id: InstanceId
    repo: Repo
    base_commit: Sha
    patch: Patch  # the gold fix
    test_patch: Patch  # the hidden tests; never shown to Tracefix
    issue: Issue
    fail_to_pass: tuple[TestId, ...]
    pass_to_pass: tuple[TestId, ...]
    image: Image  # "" when the row names none
    python: PythonVersion
    test_cmd: Command
    created_at: Timestamp
    source_row: Annotated[int, Field(ge=0)]
    source_revision: Sha

    @model_validator(mode="after")
    def _consistent(self) -> Task:
        repo_id = self.repo.replace("/", "__").lower()
        base = self.instance_id.lower().removesuffix("_interface")
        if base.rpartition("-")[0] != repo_id:
            raise PydanticCustomError("id_repo_mismatch", "instance id doesn't name the repo")
        if self.image and self.image != image_for(self.instance_id):
            raise PydanticCustomError("image_mismatch", "image doesn't belong to the task")
        hidden = self.fail_to_pass + self.pass_to_pass
        if len(hidden) > MAX_HIDDEN_TESTS:
            raise PydanticCustomError("too_many_tests", "more hidden tests than the cap")
        if len(set(hidden)) != len(hidden):
            raise PydanticCustomError("duplicate_tests", "a hidden test is listed twice")
        return self

    @property
    def python_version(self) -> tuple[int, int]:
        major, minor = self.python.split(".")[:2]
        return int(major), int(minor)


class Source(BaseModel):
    """The pin of one dataset (an entry of benchmarks/sources.json)."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    dataset: str
    config: str
    split: str
    revision: Sha
    rows: int
    rows_sha256: Digest
    license: str
    url: str


def reason(error: ValidationError) -> str:
    """A rejection reason from the first error: our field name and pydantic's error code only."""
    first = error.errors()[0]
    field = next((str(p) for p in first["loc"] if isinstance(p, str)), "row")
    return f"invalid {field} ({first['type']})"


def _tuple(value: object) -> object:
    return tuple(value) if isinstance(value, list) else value


def _tagged(image: object) -> object:
    """SWE-rebench names its images without a tag, which Docker reads as `:latest`."""
    if isinstance(image, str) and image and ":" not in image:
        return f"{image}:latest"
    return image


def parse_row(raw: RawRow, revision: str) -> Task:
    """One API row as a Task, or InvalidRow with a reason."""
    try:
        row = raw["row"]
        config = row["install_config"]
        fields = {
            "instance_id": row["instance_id"],
            "repo": row["repo"],
            "base_commit": row["base_commit"],
            "patch": row["patch"],
            "test_patch": row["test_patch"],
            "issue": row["problem_statement"],
            "fail_to_pass": _tuple(row["FAIL_TO_PASS"]),
            "pass_to_pass": _tuple(row["PASS_TO_PASS"]),
            "image": _tagged(row["image_name"] or ""),
            "python": config["python"],
            "test_cmd": config["test_cmd"] or "",
            "created_at": row["created_at"],
            "source_row": raw["row_idx"],
            "source_revision": revision,
        }
    except (KeyError, TypeError) as exc:
        raise InvalidRow("invalid row (missing field)") from exc
    try:
        return Task.model_validate(fields)
    except ValidationError as exc:
        raise InvalidRow(reason(exc)) from exc


# --- fetching -----------------------------------------------------------------------------------


def http_get(url: str, *, attempts: int = 4, timeout: float = 60.0) -> bytes:
    """GET with retries on rate limits, server errors and network failures. A rate limit's
    Retry-After is waited out (capped), else the waits double."""
    for attempt in range(attempts):
        last = attempt == attempts - 1
        request = urllib.request.Request(url, headers={"User-Agent": "tracefix-benchmark"})
        wait = float(min(2**attempt, MAX_WAIT_SECONDS))
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body: bytes = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_CODES or last:
                raise DataError(f"HTTP {exc.code} from {url}") from exc
            wait = max(wait, _retry_after(exc.headers))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if last:
                raise DataError(f"could not reach {url}") from exc
        else:
            if len(body) > MAX_RESPONSE_BYTES:
                raise DataError(f"response from {url} is too large")
            return body
        time.sleep(wait)
    raise AssertionError("unreachable")


def _retry_after(headers: Any) -> float:
    """Retry-After in seconds (0 when absent or not a number), at most MAX_WAIT_SECONDS."""
    value = headers.get("Retry-After") if headers is not None else None
    try:
        seconds = float(str(value))
    except (TypeError, ValueError):
        return 0.0
    return min(max(seconds, 0.0), MAX_WAIT_SECONDS) if seconds == seconds else 0.0


def patient_get(url: str) -> bytes:
    """For long reads of the datasets-server: it rate-limits a few dozen pages in (HTTP 429),
    and /filter answers 500 ("the dataset index is loading") for minutes after a quiet spell,
    then serves pages of several MB. More and longer tries than one page needs."""
    return http_get(url, attempts=10, timeout=180.0)


def rows_url(dataset: Dataset, offset: int) -> str:
    query = {"dataset": dataset.id, "config": dataset.config, "split": dataset.split}
    query |= {"offset": str(offset), "length": str(PAGE_ROWS)}
    return f"{ROWS_API}?{urllib.parse.urlencode(query)}"


def parse_json(body: bytes, what: str) -> Any:
    try:
        return json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise DataError(f"{what} is not JSON") from exc


def current_revision(get: Get, dataset_id: str) -> str:
    info = parse_json(get(INFO_API + dataset_id), "dataset info")
    sha = info.get("sha") if isinstance(info, dict) else None
    if not isinstance(sha, str) or len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha):
        raise DataError("dataset info has no commit id")
    return sha


def download_rows(get: Get, dataset: Dataset) -> list[RawRow]:
    """Every row of the split, page by page; complete and in order, or DataError."""
    rows: list[RawRow] = []
    total: int | None = None
    while total is None or len(rows) < total:
        page = parse_json(get(rows_url(dataset, len(rows))), "a rows page")
        if not isinstance(page, dict) or page.get("partial") is not False:
            raise DataError("the API returned a partial page")
        count, items = page.get("num_rows_total"), page.get("rows")
        limit = dataset.max_rows
        if not isinstance(count, int) or not 0 < count <= limit or not isinstance(items, list):
            raise DataError("a rows page has no row count or rows")
        if total is not None and count != total:
            raise DataError("the row count changed during the download")
        total = count
        if not items:
            raise DataError("a rows page came back empty")
        for item in items:
            if not isinstance(item, dict) or item.get("row_idx") != len(rows):
                raise DataError("rows are missing or out of order")
            if item.get("truncated_cells") != [] or not isinstance(item.get("row"), dict):
                raise DataError(f"row {len(rows)} was truncated by the API")
            rows.append({"row_idx": item["row_idx"], "row": item["row"]})
    if len(rows) != total:
        raise DataError("more rows than the row count")
    return rows


def canonical(rows: Iterable[RawRow]) -> bytes:
    """The cache file: one row per line, sorted keys, ASCII; its sha256 is the pin."""
    lines = (json.dumps(r, sort_keys=True, ensure_ascii=True, separators=(",", ":")) for r in rows)
    return "".join(f"{line}\n" for line in lines).encode("ascii")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _from_cache(data: bytes) -> list[RawRow]:
    return [json.loads(line) for line in data.decode("ascii").splitlines()]


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    partial.write_bytes(data)
    partial.replace(path)


def cache_path(cache_dir: Path, dataset: Dataset, revision: str) -> Path:
    return cache_dir / f"{dataset.name}-{revision}.jsonl"


def load_rows(
    dataset: Dataset, source: Source, cache_dir: Path, get: Get = http_get
) -> list[RawRow]:
    """The pinned rows: from the cache when it matches the pin, else downloaded and checked."""
    if (source.dataset, source.config, source.split) != (dataset.id, dataset.config, dataset.split):
        raise DataError(f"the pin in sources.json is not {dataset.id}'s")
    path = cache_path(cache_dir, dataset, source.revision)
    if path.is_file():
        data = path.read_bytes()
        if digest(data) == source.rows_sha256:
            return _from_cache(data)
    revision = current_revision(get, dataset.id)
    if revision != source.revision:
        raise DataError(
            f"{dataset.id} is now at {revision}, the pin is {source.revision} (re-pin with --repin)"
        )
    data = _download(get, dataset, revision)
    if digest(data) != source.rows_sha256:
        raise DataError(f"{dataset.id} rows don't match the pinned digest")
    _write(path, data)
    return _from_cache(data)


def repin(dataset: Dataset, cache_dir: Path, get: Get = http_get) -> Source:
    """Pin the dataset's current revision (only when asked for: `select --repin`)."""
    revision = current_revision(get, dataset.id)
    data = _download(get, dataset, revision)
    _write(cache_path(cache_dir, dataset, revision), data)
    return Source(
        dataset=dataset.id,
        config=dataset.config,
        split=dataset.split,
        revision=revision,
        rows=data.count(b"\n"),
        rows_sha256=digest(data),
        license=LICENSE,
        url=dataset.url,
    )


def _download(get: Get, dataset: Dataset, revision: str) -> bytes:
    data = canonical(download_rows(get, dataset))
    if current_revision(get, dataset.id) != revision:
        raise DataError(f"{dataset.id} changed during the download")
    return data


def read_pins(path: Path) -> dict[str, Any]:
    """benchmarks/sources.json: one pin per dataset name ({} before the first)."""
    if not path.is_file():
        return {}
    pins = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(pins, dict):
        raise DataError(f"{path.name} is not a JSON object")
    return pins


def read_source(path: Path, dataset: Dataset) -> Source:
    """The dataset's pin; DataError when it has none yet."""
    pin = read_pins(path).get(dataset.name)
    if pin is None:
        raise DataError(f"{path} has no pin for {dataset.id}: pin it first with --repin")
    return Source.model_validate_json(json.dumps(pin))


def write_source(path: Path, dataset: Dataset, source: Source) -> None:
    """Set the dataset's pin; the other datasets' pins stay as they are."""
    write_pins(path, read_pins(path) | {dataset.name: source.model_dump()})


def write_pins(path: Path, pins: dict[str, Any]) -> None:
    _write(path, (json.dumps(pins, indent=2) + "\n").encode("utf-8"))


class AgentRun(BaseModel):
    """One coding agent's run on a task (slice 2): only the fields the harness uses."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    instance_id: InstanceId
    source_row: Annotated[int, Field(ge=0)]
    patch: Patch  # the agent's final diff, its own tests included; "" when it changed nothing
    submitted: bool  # it ended with its terminating action (not an error)
    resolved: bool  # the dataset's hidden-test verdict: it selects, our own runs label (C3)


class Case(BaseModel):
    """One line of benchmarks/cases/<slice>.jsonl: a chosen task, its rank and its split, and
    (slice 2) the agent runs chosen for it: at most one resolved and one not."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    slice: Annotated[str, _pattern(r"^[a-z0-9][a-z0-9_-]*$", 40)]
    rank: Annotated[int, Field(ge=0)]
    split: Literal["dev", "held_out"]
    task: Task
    agents: tuple[AgentRun, ...] = ()


def write_cases(path: Path, cases: Iterable[Case]) -> None:
    # A case without agent runs is written without the field, as slice 1's were.
    lines = (
        json.dumps(
            c.model_dump(mode="json", exclude=set() if c.agents else {"agents"}),
            ensure_ascii=True,
            sort_keys=True,
        )
        for c in cases
    )
    _write(path, "".join(f"{line}\n" for line in lines).encode("ascii"))


def read_cases(path: Path) -> list[Case]:
    lines = path.read_text(encoding="ascii").splitlines()
    return [Case.model_validate_json(line) for line in lines]
