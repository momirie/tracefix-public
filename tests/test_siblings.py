"""Sibling sites (M11 S0): replaced code still elsewhere, same-named functions, constant reads."""

from pathlib import Path

from conftest import make_repo

from tracefix.diffscope import DiffScope, compute_scope
from tracefix.siblings import (
    constant_reads,
    find_runs,
    fix_constants,
    normalise,
    replaced_code,
    same_name,
)
from tracefix.workspace import git

BLOCK = "    total = price * quantity\n    total = total - discount\n"
FIXED = "    total = price * quantity\n    total = max(total - discount, 0)\n"


def _fn(name: str, body: str) -> str:
    return f"def {name}(price, quantity, discount):\n{body}    return total\n\n\n"


def _scope(repo: Path) -> DiffScope:
    sha = {tag: git(repo, "rev-parse", tag).strip() for tag in ("c0", "c1")}
    return compute_scope(repo, sha["c0"], sha["c1"])


def test_normalise_keeps_only_lines_that_say_something() -> None:
    assert normalise("    total  =  price *   quantity  ") == "total = price * quantity"
    assert normalise("    return x") is None  # too short to tell copies apart
    assert normalise("   # a comment that is long enough") is None
    assert normalise("") is None


def test_find_runs_skips_lines_that_dont_count() -> None:
    lines = ["def g():", "    total = price * quantity", "", "    # note",
             "    total = total - discount", "    return total"]  # fmt: skip
    block = ["total = price * quantity", "total = total - discount"]
    assert find_runs(block, lines) == [[2, 5]]
    assert find_runs([], lines) == []


def test_replaced_code_left_in_another_file_is_a_sibling_site(tmp_path: Path) -> None:
    base = {"shop/a.py": _fn("bill", BLOCK), "shop/b.py": _fn("quote", BLOCK)}
    repo = make_repo(tmp_path / "r", [base, {"shop/a.py": _fn("bill", FIXED)}])
    sites = replaced_code(repo, _scope(repo))
    assert [(s.kind, s.path, s.line, s.fixed_at) for s in sites] == [
        ("replaced_code", "shop/b.py", 3, "shop/a.py:3")
    ]
    assert sites[0].text == "total = total - discount"


def test_a_fix_that_changes_every_copy_leaves_no_site(tmp_path: Path) -> None:
    base = {"shop/a.py": _fn("bill", BLOCK) + _fn("quote", BLOCK)}
    head = {"shop/a.py": _fn("bill", FIXED) + _fn("quote", FIXED)}
    repo = make_repo(tmp_path / "r", [base, head])
    assert replaced_code(repo, _scope(repo)) == []


def test_copies_in_tests_and_reindented_copies(tmp_path: Path) -> None:
    other = "class Q:\n    def quote(self, price, quantity, discount):\n" + "".join(
        "    " + line + "\n" for line in BLOCK.splitlines()
    ).replace("total = total -", "total  =  total -")
    base = {"shop/a.py": _fn("bill", BLOCK), "tests/test_a.py": _fn("t", BLOCK),
            "shop/q.py": other}  # fmt: skip
    repo = make_repo(tmp_path / "r", [base, {"shop/a.py": _fn("bill", FIXED)}])
    found = [(s.path, s.line) for s in replaced_code(repo, _scope(repo))]
    assert found == []  # the test file is no source; q.py's spacing hides it from grep's first line
    grep_friendly = other.replace("total  =  total -", "total = total -")
    repo2 = make_repo(tmp_path / "r2", [{**base, "shop/q.py": grep_friendly},
                                        {"shop/a.py": _fn("bill", FIXED)}])  # fmt: skip
    assert [(s.path, s.line) for s in replaced_code(repo2, _scope(repo2))] == [("shop/q.py", 4)]


def test_short_removed_lines_make_no_block(tmp_path: Path) -> None:
    base = {"m.py": "def f(x):\n    return x\n", "n.py": "def g(x):\n    return x\n"}
    repo = make_repo(tmp_path / "r", [base, {"m.py": "def f(x):\n    return -x\n"}])
    assert replaced_code(repo, _scope(repo)) == []


def test_single_line_variant_needs_long_lines(tmp_path: Path) -> None:
    long = "    url = base_url.rstrip('/') + '/' + path.lstrip('/')\n"
    base = {"m.py": "def f(base_url, path):\n" + long + "    return url\n",
            "n.py": "def g(base_url, path):\n" + long + "    return url.lower()\n"}  # fmt: skip
    head = {"m.py": "def f(base_url, path):\n    url = join(base_url, path)\n    return url\n"}
    repo = make_repo(tmp_path / "r", [base, head])
    lines = replaced_code(repo, _scope(repo), single_lines=True)
    assert [(s.kind, s.path, s.line) for s in lines] == [("replaced_line", "n.py", 2)]
    assert [(s.path, s.line) for s in replaced_code(repo, _scope(repo))] == [("n.py", 2)]


def test_same_name_finds_the_untouched_namesake(tmp_path: Path) -> None:
    create = ("class CreateCommand:\n    def install(self, app):\n        return app\n\n"
              "    def __init__(self):\n        self.x = 1\n")  # fmt: skip
    update = "from create import CreateCommand\n\n\nclass UpdateCommand(CreateCommand):\n    pass\n"
    fixed = update.replace(
        "    pass\n",
        "    def install(self, app):\n        return super().install(app)\n\n"
        "    def __init__(self):\n        self.y = 2\n",
    )
    base = {"pkg/create.py": create, "pkg/update.py": update,
            "tests/test_c.py": "def install(app):\n    return 1\n"}  # fmt: skip
    repo = make_repo(tmp_path / "r", [base, {"pkg/update.py": fixed}])
    sites = same_name(repo, _scope(repo))
    assert [(s.path, s.line, s.text) for s in sites] == [
        ("pkg/create.py", 2, "def install(self, app):")
    ]
    assert sites[0].fixed_at == "pkg/update.py:5 UpdateCommand.install"


def test_same_name_skips_namesakes_the_fix_also_changed(tmp_path: Path) -> None:
    base = {"a.py": "def run(x):\n    return x\n", "b.py": "def run(y):\n    return y\n"}
    head = {"a.py": "def run(x):\n    return -x\n", "b.py": "def run(y):\n    return -y\n"}
    repo = make_repo(tmp_path / "r", [base, head])
    assert same_name(repo, _scope(repo)) == []


def test_fix_constants_and_the_tests_that_read_them(tmp_path: Path) -> None:
    base = {"pkg/limits.py": "MAX = 50\nMIN = 1\n__all__ = ['MAX']\n"}
    head = {"pkg/limits.py": "MAX = 100\nMIN = 1\nNEW: int = 3\n__all__ = ['MAX', 'NEW']\n"}
    repo = make_repo(tmp_path / "r", [base, head])
    names = fix_constants(repo, _scope(repo))
    assert names == frozenset({"MAX", "NEW"})
    test = ("from pkg.limits import NEW\nimport pkg.limits as lim\n\n"
            "def test_it():\n    assert f(lim.MAX + 1) == lim.MIN\n")  # fmt: skip
    assert constant_reads(test, names) == ["MAX", "NEW"]
    assert constant_reads("def test_x(:\n", names) == []
    assert constant_reads("def test_x():\n    assert f(51) == 1\n", names) == []
