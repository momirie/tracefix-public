"""Prompts and output schemas for the LLM roles. Repo and issue text is always wrapped as data."""

import re

_CLOSING = re.compile(r"</(data)", re.IGNORECASE)


def data_block(name: str, content: str) -> str:
    """Wrap untrusted content; a closing tag inside it is escaped so it cannot end the block."""
    safe = _CLOSING.sub(r"<\\/\1", content)
    safe_name = name.replace("&", "&amp;").replace('"', "&quot;").replace(">", "&gt;")
    return f'<data name="{safe_name}">\n{safe}\n</data>'


def python_note(version: tuple[int, ...]) -> str | None:
    """One fixed sentence naming the project's Python when it is older than 3.11, for the roles
    whose code runs there; None from 3.11 on, so those prompts (and their recordings) stay byte
    for byte as before. The version comes from Tracefix's interpreter check, never from repo
    text."""
    if version[:2] >= (3, 11):
        return None
    name = f"Python {version[0]}.{version[1]}"
    return (f"The project's tests run with {name}: everything you write must run on {name}, "
            "without syntax or library features of later versions.")  # fmt: skip
