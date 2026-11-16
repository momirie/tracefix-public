"""tracefix.yml and the run's settings (M8, plan P7): read from the base commit, strict, safe."""

from pathlib import Path
from typing import get_args

import pytest
from conftest import make_repo

from tracefix.config import (
    CONFIG_NAME,
    MAX_CONFIG_BYTES,
    NOT_SUPPORTED,
    ConfigError,
    Effort,
    FileSettings,
    load,
    parse,
    resolve,
)
from tracefix.llm import DEFAULT_MODELS, EFFORTS
from tracefix.runner import DEFAULT_TIMEOUT_S
from tracefix.workspace import resolve_ref

FULL = b"""\
suite_timeout_seconds: 900
max_llm_calls: 12
token_budget: 200000
max_tokens: 8000
effort: high
models:
  reproducer: claude-opus-5-5
  judge: claude-sonnet-5-5
pytest_plugins: [pytest_mock, pytest_asyncio.plugin]
"""


def test_a_full_file_is_read_as_written() -> None:
    settings = parse(FULL, CONFIG_NAME)
    assert settings.suite_timeout_seconds == 900 and settings.effort == "high"
    assert settings.models == {"reproducer": "claude-opus-5-5", "judge": "claude-sonnet-5-5"}
    assert settings.pytest_plugins == ["pytest_mock", "pytest_asyncio.plugin"]


@pytest.mark.parametrize("raw", [b"", b"# only a comment\n", b"---\n"])
def test_an_empty_file_sets_nothing(raw: bytes) -> None:
    assert parse(raw, CONFIG_NAME) == FileSettings()


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b"- a list\n", "must be a mapping"),
        (b"effort: extreme\n", "effort"),
        (b"max_llm_calls: 0\n", "max_llm_calls"),
        (b"suite_timeout_seconds: 5\n", "suite_timeout_seconds"),
        (b"max_tokens: 50000\n", "max_tokens"),
        (b"models: {writer: claude-opus-5-5}\n", "models.writer"),
        (b"models: {judge: 'Claude Opus!'}\n", "not a model id"),
        (b"pytest_plugins: ['os; rm -rf']\n", "not a module name"),
        (b"colour: blue\n", "unknown setting (allowed: suite_timeout_seconds"),
        (b"effort: [high\n", "not valid YAML"),
        (b"effort: !!python/object:os.system x\n", "not valid YAML"),
        (b"\xff\xfe effort: high\n", "not UTF-8"),
    ],
)
def test_bad_settings_say_what_is_wrong(raw: bytes, message: str) -> None:
    with pytest.raises(ConfigError, match=message.replace("(", r"\(").replace(".", r"\.")):
        parse(raw, CONFIG_NAME)


@pytest.mark.parametrize("key", sorted(NOT_SUPPORTED))
def test_keys_from_the_early_spec_draft_get_their_own_message(key: str) -> None:
    with pytest.raises(ConfigError) as caught:
        parse(f"{key}: something\n".encode(), CONFIG_NAME)
    assert NOT_SUPPORTED[key] in str(caught.value)


def test_anchors_and_aliases_are_refused_before_anything_expands() -> None:
    """A few lines of aliases can expand to billions of entries in a YAML loader."""
    bomb = b'a: &a ["x","x","x","x","x","x","x","x","x"]\nb: &b [*a,*a,*a,*a,*a,*a,*a,*a,*a]\n'
    with pytest.raises(ConfigError, match="anchors and aliases"):
        parse(bomb, CONFIG_NAME)


def test_a_key_given_twice_is_refused() -> None:
    with pytest.raises(ConfigError, match="given twice: max_llm_calls"):
        parse(b"max_llm_calls: 5\neffort: low\nmax_llm_calls: 500\n", CONFIG_NAME)


def test_a_file_over_the_size_cap_is_refused_unread() -> None:
    with pytest.raises(ConfigError, match="larger than 64 KB"):
        parse(b"#" * (MAX_CONFIG_BYTES + 1), CONFIG_NAME)


def test_deep_nesting_is_a_config_error_not_a_crash() -> None:
    """Within the size cap, but deeper than Python's recursion limit (verifier S3)."""
    deep = b"models: " + b"[" * 20_000 + b"]" * 20_000 + b"\n"
    assert len(deep) <= MAX_CONFIG_BYTES
    with pytest.raises(ConfigError, match="nested too deeply"):
        parse(deep, CONFIG_NAME)


@pytest.mark.parametrize("raw", [b"max_llm_calls: true\n", b"token_budget: '20000'\n",
                                 b"suite_timeout_seconds: 60.0\n"])  # fmt: skip
def test_a_number_must_be_written_as_a_whole_number(raw: bytes) -> None:
    with pytest.raises(ConfigError):
        parse(raw, CONFIG_NAME)


def test_an_oversized_file_at_base_is_refused_unread(tmp_path: Path) -> None:
    big = "#" * (MAX_CONFIG_BYTES + 1)
    repo, base, head = _repo(tmp_path, big, big)
    with pytest.raises(ConfigError, match=r"tracefix\.yml at base is larger than 64 KB"):
        load(repo, base, head)


def test_the_effort_values_are_the_ones_the_client_takes() -> None:
    assert set(get_args(Effort)) == set(EFFORTS)


def _repo(tmp_path: Path, base: str | None, head: str | None) -> tuple[Path, str, str]:
    commits: list[dict[str, str | None]] = [{"app.py": "x = 1\n"}, {"app.py": "x = 2\n"}]
    if base is not None:
        commits[0][CONFIG_NAME] = base
    if head is not None:
        commits[1][CONFIG_NAME] = head
    elif base is not None:
        commits[1][CONFIG_NAME] = None
    repo = make_repo(tmp_path / "repo", commits)
    return repo, resolve_ref(repo, "c0"), resolve_ref(repo, "c1")


def test_the_settings_come_from_the_base_commit_whatever_the_fix_does(tmp_path: Path) -> None:
    repo, base, head = _repo(tmp_path, "max_llm_calls: 7\n", "max_llm_calls: 200\n")
    settings, source, notes = load(repo, base, head)
    assert settings.max_llm_calls == 7 and source == f"{CONFIG_NAME} at base"
    assert notes and "the fix changes tracefix.yml" in notes[0]


def test_a_config_the_fix_adds_is_not_used(tmp_path: Path) -> None:
    repo, base, head = _repo(tmp_path, None, "max_llm_calls: 200\n")
    settings, source, notes = load(repo, base, head)
    assert settings == FileSettings() and source == "defaults"
    assert "the fix adds tracefix.yml" in notes[0]


def test_no_config_anywhere_means_defaults_and_no_note(tmp_path: Path) -> None:
    repo, base, head = _repo(tmp_path, None, None)
    assert load(repo, base, head) == (FileSettings(), "defaults", ())


def test_an_unchanged_config_gives_no_note(tmp_path: Path) -> None:
    repo, base, head = _repo(tmp_path, "effort: low\n", "effort: low\n")
    assert load(repo, base, head)[2] == ()


def test_a_bad_config_at_base_stops_the_run(tmp_path: Path) -> None:
    repo, base, head = _repo(tmp_path, "setup: uv sync\n", "setup: uv sync\n")
    with pytest.raises(ConfigError, match="setup"):
        load(repo, base, head)


def test_a_config_file_given_on_the_command_line_replaces_the_base_one(tmp_path: Path) -> None:
    repo, base, head = _repo(tmp_path, "max_llm_calls: 7\n", "max_llm_calls: 7\n")
    mine = tmp_path / "mine.yml"
    mine.write_bytes(b"max_llm_calls: 9\n")
    settings, source, notes = load(repo, base, head, mine)
    assert settings.max_llm_calls == 9 and source == "mine.yml" and notes == ()
    with pytest.raises(ConfigError, match="can't read"):
        load(repo, base, head, tmp_path / "missing.yml")


def test_command_line_flags_win_over_the_file_which_wins_over_the_defaults() -> None:
    file = parse(FULL, CONFIG_NAME)
    flags = FileSettings(effort="low", models={"adversary": "claude-sonnet-5-5"})
    settings = resolve(file, flags, f"{CONFIG_NAME} at base")
    assert settings.effort == "low"  # flag
    assert settings.max_llm_calls == 12 and settings.suite_timeout_s == 900.0  # file
    assert settings.models == {
        **DEFAULT_MODELS,
        "reproducer": "claude-opus-5-5",  # file
        "judge": "claude-sonnet-5-5",  # file
        "adversary": "claude-sonnet-5-5",  # flag
    }
    assert settings.pytest_plugins == ("pytest_mock", "pytest_asyncio.plugin")


def test_with_nothing_set_the_defaults_are_todays_constants() -> None:
    settings = resolve(FileSettings(), FileSettings())
    assert settings.models == DEFAULT_MODELS and settings.effort == "medium"
    assert (settings.max_llm_calls, settings.token_budget) == (40, 500_000)
    assert settings.max_tokens == 16_000 and settings.suite_timeout_s == DEFAULT_TIMEOUT_S
    assert settings.pytest_plugins == () and settings.source == "defaults"


def test_a_plugin_named_twice_is_loaded_once() -> None:
    flags = FileSettings(pytest_plugins=["pytest_mock", "pytest_mock"])
    assert resolve(FileSettings(), flags).pytest_plugins == ("pytest_mock",)
