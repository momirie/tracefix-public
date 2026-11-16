"""A listener that decides which TCP port to bind."""

MIN_PORT = 1
MAX_PORT = 65535


class Listener:
    """Binds to a port taken from configuration, falling back to a default."""

    def __init__(self, default_port: int = 8080) -> None:
        self.default_port = default_port

    def port(self, raw: str | None) -> int:
        """Parse a configured port.

        An unset (None) or blank value gives `self.default_port`. Raises ValueError for
        text that is not a whole number from 1 to 65535.
        """
        if raw is None:
            return 8080
        number = int(raw.strip())
        if not MIN_PORT <= number <= MAX_PORT:
            raise ValueError(f"port must be between {MIN_PORT} and {MAX_PORT}, got {number}")
        return number
