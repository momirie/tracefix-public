"""Service settings loaded from environment variables.

Recognised variables:

HOST: interface to bind. Optional; defaults to DEFAULT_HOST.
PORT: TCP port to listen on. Optional; if unset or blank, DEFAULT_PORT (8080) is used.
"""

from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
MIN_PORT = 1
MAX_PORT = 65535


class ConfigError(Exception):
    """Raised when a setting has a value the service cannot use."""


@dataclass(frozen=True)
class Settings:
    host: str
    port: int


def parse_port(raw: str | None) -> int:
    """Parse the PORT variable.

    PORT: TCP port to listen on. Optional; if unset or blank, DEFAULT_PORT (8080) is used.
    Surrounding whitespace is ignored. Raises ConfigError if the port is outside 1..65535.
    """
    if raw is None:
        return DEFAULT_PORT
    port = int(raw.strip())
    if not MIN_PORT <= port <= MAX_PORT:
        raise ConfigError(f"PORT must be between {MIN_PORT} and {MAX_PORT}, got {port}")
    return port


def load_settings(env: Mapping[str, str | None]) -> Settings:
    """Build Settings from an environment mapping such as os.environ."""
    host = (env.get("HOST") or "").strip() or DEFAULT_HOST
    return Settings(host=host, port=parse_port(env.get("PORT")))
