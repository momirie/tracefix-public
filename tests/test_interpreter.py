"""M10 part 2: the project's Python (--python) and its check."""

import ast
import json
import sys
from pathlib import Path

import pytest
from conftest import old_python

from tracefix import interpreter
from tracefix.interpreter import (
    MARKER,
    SCRIPT,
    Interpreter,
    check,
    current,
    parse_report,
    refusal,
    version_of,
)
from tracefix.runner import Outcome
from tracefix.sandbox import sandbox_level

OLD = {"3.9": ("8.4.2", "6.141.1"), "3.10": ("9.1.1", "6.168.5")}  # tests/old_pythons pins
WINDOWS = sys.platform == "win32"
# Folders in a report are read with this machine's path rules: the samples are absolute here.
ROOT = Path(sys.executable).anchor  # "C:\\" on Windows, "/" elsewhere


def at(relative: str) -> str:
    return str(Path(ROOT) / relative)


def report(**changes: object) -> str:
    data: dict[str, object] = {
        "version": [3, 9, 25], "prefixes": [at("p"), at("p"), at("b"), at("b")],
        "dirs": [at("b/lib/python3.9"), at("p/lib/python3.9/site-packages")],
        "pytest": "8.4.2", "hypothesis": "6.141.1",
    }  # fmt: skip
    data.update(changes)
    return "noise from a .pth file\n" + MARKER + json.dumps(data) + "\n"


@pytest.mark.parametrize("version", sorted(OLD))
def test_the_check_reads_an_old_python(version: str) -> None:
    python = old_python(version)
    checked = check(str(python), sandbox_level())
    found = checked.interpreter
    assert checked.reason == "" and found is not None, checked.run.first.output
    assert found.label.startswith(version + ".") and not found.safe_path and not found.own
    assert (found.pytest, found.hypothesis) == OLD[version]
    assert found.executable == str(python.absolute())
    assert len(found.prefixes) == 4 and python.parent.parent in found.prefixes
    assert found.hypothesis_problem() is None
    assert checked.run.outcome is Outcome.PASSED
    assert checked.run.command == ("python", "-I", "-c", "<Tracefix's interpreter check>")


def test_the_check_reads_tracefix_s_own_python_like_current() -> None:
    found = check(sys.executable, sandbox_level()).interpreter
    own = current()
    assert found is not None and own.own and not found.own
    assert found.version == own.version and found.safe_path
    assert (found.pytest, found.hypothesis) == (own.pytest, own.hypothesis)


def test_an_import_hook_on_sys_path_does_not_refuse_the_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S10: an editable install of a namespace package puts a hook name, not a folder, on
    sys.path; 11 benchmark runs were refused for it. The script leaves such entries out, and
    the report's parsing stays strict."""
    hook = "__editable__.demo-1.0.finder.__path_hook__"
    monkeypatch.setattr(interpreter, "SCRIPT", f"import sys; sys.path.append({hook!r})\n{SCRIPT}")
    checked = check(sys.executable, sandbox_level())
    found = checked.interpreter
    assert checked.reason == "" and found is not None, checked.run.first.output
    assert all(d.is_absolute() for d in found.code_dirs)
    assert hook not in checked.run.first.output
    assert parse_report(report(dirs=[at("b/lib"), hook]), at("p/bin/python")) is None


def test_a_python_that_is_not_there_is_refused_in_fixed_words(tmp_path: Path) -> None:
    checked = check(str(tmp_path / "no-python"), "basic")
    assert checked.interpreter is None
    assert checked.reason == "the project's Python (--python) was not found"
    assert str(tmp_path) not in str(checked.run.command)  # no machine path in the receipt


def test_something_that_is_not_python_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "not-python.txt"
    target.write_text("hello", encoding="utf-8")
    checked = check(str(target), "basic")
    assert checked.interpreter is None
    assert "the project's Python (--python) could not be started" in checked.reason


def test_the_script_runs_on_any_python_old_enough_to_ask() -> None:
    """No f-strings or other new syntax: a Python 2 or 3.5 must still say how old it is."""
    tree = ast.parse(SCRIPT)
    assert not any(isinstance(node, ast.JoinedStr | ast.NamedExpr) for node in ast.walk(tree))


def test_a_report_in_the_expected_shape_is_read() -> None:
    found = parse_report(report(), at("p/bin/python"))
    prefixes = tuple(Path(at(p)) for p in ("p", "p", "b", "b"))
    dirs = (Path(at("b/lib/python3.9")), Path(at("p/lib/python3.9/site-packages")))
    assert found == Interpreter(at("p/bin/python"), (3, 9, 25), prefixes, dirs, "8.4.2",
                                "6.141.1")  # fmt: skip
    assert refusal(found) == ""


@pytest.mark.parametrize(
    "output",
    [
        "",
        "no marker\n",
        MARKER + "{not json\n",
        MARKER + "[1, 2]\n",
        report(version=[3, 9]),
        report(version=["3", 9, 1]),
        report(version=[3, 9, True]),
        report(prefixes=[at("p")]),
        report(prefixes=None),
        report(dirs=[at("d")] * 201),
        report(dirs=[at("x" * 4097)]),
        report(dirs=[""]),
        report(dirs=[1]),
        # Relative folders would resolve against Tracefix's own; a drive's root watches it all.
        report(prefixes=[".", "..", "rel", "x"]),
        report(dirs=["."]),
        report(dirs=["C:\\"]),
        report(dirs=["C:rel"]),
        # Absolute only on the other OS: on Windows `/Users` takes the current drive, and on
        # POSIX a Windows path is a relative file name.
        report(dirs=["/Users" if WINDOWS else "C:\\Py39"]),
        report(prefixes=["/usr/lib" if WINDOWS else "\\\\server\\share\\py"] * 4),
    ],
)
def test_a_report_out_of_shape_is_refused(output: str) -> None:
    assert parse_report(output, at("p/bin/python")) is None
    assert "did not report its version and folders" in refusal(None)


HOST_FOLDERS = (
    ["C:\\Users\\u\\.venv", "\\\\server\\share\\py", "\\\\?\\C:\\Py39", "D:\\Py39\\Lib"]
    if WINDOWS
    else ["/usr/lib/python3.9", "/usr/lib/python39.zip", "/home/u/.venv", "/opt/py"]
)


@pytest.mark.parametrize("folder", HOST_FOLDERS)
def test_real_interpreters_folders_are_read(folder: str) -> None:
    found = parse_report(report(prefixes=[folder] * 4, dirs=[folder]), at("p/bin/python"))
    assert found is not None and refusal(found) == ""


def test_a_bare_root_is_read_only_where_isolation_shares_it() -> None:
    """POSIX `/` is a shared prefix (isolation watches only Python's own folders in it); a
    drive's root on Windows would make the whole drive a watched folder."""
    found = parse_report(report(prefixes=[ROOT] * 4), at("p/bin/python"))
    assert (found is None) == WINDOWS


def test_the_last_marked_line_counts() -> None:
    output = report(version=[3, 12, 0]) + report()
    found = parse_report(output, "py")
    assert found is not None and found.version == (3, 9, 25)


def test_a_version_string_that_is_not_one_is_dropped() -> None:
    found = parse_report(report(pytest="8.4.2; rm -rf /", hypothesis=7), "py")
    assert found is not None and found.pytest is None and found.hypothesis is None
    assert "pytest is not installed" in refusal(found)


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"version": [3, 8, 18]}, "the project's Python is 3.8.18; Tracefix runs projects on 3.9"),
        ({"version": [2, 7, 18], "prefixes": None}, "the project's Python is 2.7.18"),
        ({"pytest": None}, "pytest is not installed in the project's Python (--python)"),
        ({"pytest": "6.2.5"}, "has pytest 6.2.5; Tracefix needs pytest 7.0 or later"),
    ],
)
def test_too_old_or_without_pytest_is_refused_in_fixed_words(
    changes: dict[str, object], words: str
) -> None:
    assert words in refusal(parse_report(report(**changes), "py"))


def test_hypothesis_missing_or_too_old_is_named_with_the_install_command() -> None:
    found = parse_report(report(hypothesis=None), "py")
    assert found is not None
    assert "Hypothesis is not installed" in (found.hypothesis_problem() or "")
    old = parse_report(report(hypothesis="6.100.0"), "py")
    assert old is not None
    problem = old.hypothesis_problem() or ""
    assert "Hypothesis 6.100.0, older than 6.141" in problem and "pip install -U" in problem


@pytest.mark.parametrize(
    ("text", "version"),
    [("8.4.2", (8, 4)), ("7.0.0rc1", (7, 0)), ("6.141", (6, 141)), ("x", (0, 0)), ("", (0, 0))],
)
def test_version_of(text: str, version: tuple[int, int]) -> None:
    assert version_of(text) == version


def test_a_python_that_hangs_is_cut_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(interpreter, "SCRIPT", "import time; time.sleep(30)")
    checked = check(sys.executable, "basic", timeout_s=2)
    assert checked.interpreter is None
    assert checked.reason == "the project's Python (--python) did not answer within 2s"
    assert checked.run.first.exit_code is None
