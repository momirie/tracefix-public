"""Settings for one run: defaults, then `tracefix.yml`, then command-line flags (SPEC 2.1, Decided
in M8).

`tracefix.yml` is read from the base commit's git objects, never from head: the fix under test
can't change how it is verified (its budgets, models, plugins or timeouts). `--config FILE`
replaces it, to try settings before committing them. The file is untrusted text: it is parsed
with PyYAML's safe loader, refused over 64 KB or with anchors and aliases (a few lines could
otherwise expand to gigabytes) or duplicate keys, and validated strictly. Settings shape what the
models propose and how long runs may take; none of them decides a verdict.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from tracefix.llm import (
    DEFAULT_EFFORT,
    DEFAULT_MAX_CALLS,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODELS,
    DEFAULT_TOKEN_BUDGET,
    MAX_TOKENS_LIMIT,
    Role,
)
from tracefix.runner import DEFAULT_TIMEOUT_S
from tracefix.workspace import WorkspaceError, git_bytes

CONFIG_NAME = "tracefix.yml"
MAX_CONFIG_BYTES = 64 * 1024
MAX_PLUGINS = 20
_MODEL_ID = re.compile(r"[a-z0-9][a-z0-9.\-]{0,63}")
_MODULE = re.compile(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)*")
# Keys from SPEC 2.1's early draft, which M8 doesn't take (developer, 13 Oct 2026): a clear word
# instead of the generic "unknown key".
NOT_SUPPORTED = {
    "setup": "Tracefix doesn't run setup commands: install the project and its test "
    "dependencies in one environment, then run Tracefix from it or point --python at its "
    "interpreter (see the README)",
    "test": "Tracefix always runs pytest with the project's own pytest configuration; use "
    "pytest_plugins to load plugins",
    "timeout_seconds": "use suite_timeout_seconds (the time limit of one run of the whole suite)",
}


class ConfigError(Exception):
    """The settings can't be used; nothing runs (the CLI exits 2 with this message)."""


Effort = Literal["low", "medium", "high", "xhigh", "max"]


class FileSettings(BaseModel):
    """What tracefix.yml (and, as overrides, the command line) may set. None: not set here."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # strict: `true` or "20000" is a mistake to point out, not a number to guess
    suite_timeout_seconds: int | None = Field(default=None, ge=30, le=86_400, strict=True)
    max_llm_calls: int | None = Field(default=None, ge=1, le=200, strict=True)
    token_budget: int | None = Field(default=None, ge=10_000, le=10_000_000, strict=True)
    max_tokens: int | None = Field(default=None, ge=1_000, le=MAX_TOKENS_LIMIT, strict=True)
    effort: Effort | None = None
    models: dict[Role, str] | None = None
    pytest_plugins: list[str] | None = Field(default=None, max_length=MAX_PLUGINS)

    @field_validator("models")
    @classmethod
    def _model_ids(cls, models: dict[Role, str] | None) -> dict[Role, str] | None:
        for role, model in (models or {}).items():
            if not _MODEL_ID.fullmatch(model):
                raise ValueError(f"{role}: {model!r} is not a model id like claude-opus-5-5")
        return models

    @field_validator("pytest_plugins")
    @classmethod
    def _module_names(cls, plugins: list[str] | None) -> list[str] | None:
        for name in plugins or []:
            if not _MODULE.fullmatch(name):
                raise ValueError(f"{name!r} is not a module name like pytest_mock")
        return plugins


@dataclass(frozen=True)
class Settings:
    """The settings one run uses, after defaults, the config file and the command line."""

    models: Mapping[Role, str]
    effort: str
    max_tokens: int
    max_llm_calls: int
    token_budget: int
    suite_timeout_s: float
    pytest_plugins: tuple[str, ...]
    source: str  # where the file settings came from: "defaults", "tracefix.yml at base", a file
    notes: tuple[str, ...] = ()  # e.g. the fix changes tracefix.yml, so the base version was used
    # The project's Python (--python; command line only: a path belongs to one machine). None:
    # Tracefix's own interpreter runs the tests.
    python: str | None = None


class _UniqueKeyLoader(yaml.SafeLoader):
    """The safe loader, refusing a key given twice (PyYAML would silently keep the last one,
    hiding a setting from whoever reads the file top down)."""


def _unique_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode) -> dict[Any, Any]:
    keys = [loader.construct_object(key) for key, _ in node.value]
    repeated = sorted({str(k) for k in keys if keys.count(k) > 1})
    if repeated:
        raise ConfigError(f"a key is given twice: {', '.join(repeated)}")
    return dict(loader.construct_mapping(node))


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def _yaml(text: str, where: str) -> object:
    try:
        for token in yaml.scan(text, Loader=yaml.SafeLoader):
            if isinstance(token, yaml.AnchorToken | yaml.AliasToken):
                raise ConfigError(f"{where}: anchors and aliases (& and *) are not allowed")
        return yaml.load(text, Loader=_UniqueKeyLoader)  # the safe loader, plus the key check
    except yaml.YAMLError as exc:
        raise ConfigError(f"{where} is not valid YAML: {exc}") from None
    except RecursionError:  # flow collections nested thousands deep, within the size cap
        raise ConfigError(f"{where} is nested too deeply to read") from None


def _problem(error: Mapping[str, Any]) -> str:
    where = ".".join(str(part) for part in error.get("loc", ())) or "the file"
    if error.get("type") == "extra_forbidden":
        allowed = ", ".join(FileSettings.model_fields)
        return f"{where}: unknown setting (allowed: {allowed})"
    return f"{where}: {error.get('msg', 'invalid value')}"


def parse(raw: bytes, where: str) -> FileSettings:
    """tracefix.yml's content, checked; ConfigError says what is wrong, in plain words."""
    if len(raw) > MAX_CONFIG_BYTES:
        raise ConfigError(f"{where} is larger than {MAX_CONFIG_BYTES // 1024} KB")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ConfigError(f"{where} is not UTF-8 text") from None
    data = _yaml(text, where)
    if data is None:
        return FileSettings()
    if not isinstance(data, dict):
        raise ConfigError(f"{where} must be a mapping of settings (key: value lines)")
    for key in data:
        if key in NOT_SUPPORTED:
            raise ConfigError(f"{where}: {key}: {NOT_SUPPORTED[key]}")
    try:
        return FileSettings.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(_problem(e) for e in exc.errors())
        raise ConfigError(f"{where}: {problems}") from None


def from_flags(values: Mapping[str, object]) -> FileSettings:
    """Command-line settings (the same names and checks as the file); only those given."""
    given = {key: value for key, value in values.items() if value is not None}
    try:
        return FileSettings.model_validate(given)
    except ValidationError as exc:
        problems = "; ".join(_problem(e) for e in exc.errors())
        raise ConfigError(f"command line: {problems}") from None


def _blob_id(repo: Path, sha: str) -> str | None:
    """The git object id of tracefix.yml at a commit, or None if the commit has no such file."""
    try:
        return (
            git_bytes(repo, "rev-parse", "--verify", "-q", f"{sha}:{CONFIG_NAME}").decode().strip()
        )
    except WorkspaceError:
        return None


def _blob(repo: Path, blob_id: str, where: str) -> bytes:
    """A blob's bytes; one over the size cap is refused before it is read."""
    size = int(git_bytes(repo, "cat-file", "-s", blob_id))
    if size > MAX_CONFIG_BYTES:
        raise ConfigError(f"{where} is larger than {MAX_CONFIG_BYTES // 1024} KB")
    return git_bytes(repo, "cat-file", "blob", blob_id)


def load(
    repo: Path, base_sha: str, head_sha: str, config_file: Path | None = None
) -> tuple[FileSettings, str, tuple[str, ...]]:
    """The file settings for a run, where they came from, and notes for the receipt."""
    if config_file is not None:
        try:
            raw = config_file.read_bytes()
        except OSError as exc:
            raise ConfigError(f"can't read {config_file.name}: {exc.strerror or exc}") from None
        return parse(raw, config_file.name), config_file.name, ()
    base, head = _blob_id(repo, base_sha), _blob_id(repo, head_sha)
    notes: tuple[str, ...] = ()
    if head != base:
        notes = (
            f"the fix {'adds' if base is None else 'changes'} {CONFIG_NAME}; the base commit's "
            f"{'defaults' if base is None else 'version'} were used, since a fix can't change "
            "how it is verified",
        )
    if base is None:
        return FileSettings(), "defaults", notes
    where = f"{CONFIG_NAME} at base"
    return parse(_blob(repo, base, where), where), where, notes


def resolve(
    file: FileSettings,
    flags: FileSettings,
    source: str = "defaults",
    notes: tuple[str, ...] = (),
    python: str | None = None,
) -> Settings:
    """Defaults, then the file, then the command line (`flags`, the same shape, and `python`)."""

    def pick(name: str, default: Any) -> Any:
        for layer in (flags, file):
            value = getattr(layer, name)
            if value is not None:
                return value
        return default

    models = {**DEFAULT_MODELS, **(file.models or {}), **(flags.models or {})}
    plugins = pick("pytest_plugins", [])
    return Settings(
        models=models,
        effort=pick("effort", DEFAULT_EFFORT),
        max_tokens=pick("max_tokens", DEFAULT_MAX_TOKENS),
        max_llm_calls=pick("max_llm_calls", DEFAULT_MAX_CALLS),
        token_budget=pick("token_budget", DEFAULT_TOKEN_BUDGET),
        suite_timeout_s=float(pick("suite_timeout_seconds", DEFAULT_TIMEOUT_S)),
        pytest_plugins=tuple(dict.fromkeys(plugins)),
        source=source,
        notes=notes,
        python=python,
    )
