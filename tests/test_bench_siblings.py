"""M11 S0's measurement harness (scripts/bench/siblings.py): a local repo stands in for GitHub."""

from pathlib import Path

import pytest
from bench import patches, prepare, siblings
from bench.data import AgentRun, Case
from bench_fakes import task, tried
from conftest import make_repo

from tracefix.workspace import git

BLOCK = "    total = price * quantity\n    total = total - discount\n"
FIXED = "    total = price * quantity\n    total = max(total - discount, 0)\n"
PAD = "".join(f"# line {n}\n" for n in range(12))  # keeps the hunks apart


def _module(name: str, body: str, limit: int) -> str:
    return (f"LIMIT = {limit}\n{PAD}\n\ndef {name}(price, quantity, discount):\n{body}"
            "    return total\n")  # fmt: skip


BASE = {"pkg/a.py": _module("bill", BLOCK, 50), "pkg/b.py": _module("quote", BLOCK, 50)}
GOLD = {"pkg/a.py": _module("bill", FIXED, 100), "pkg/b.py": _module("quote", FIXED, 50)}
WRONG = {"pkg/a.py": _module("bill", FIXED, 50)}


def _diff(repo: Path, a: str, b: str) -> str:
    return git(repo, "diff", "--no-color", "--no-ext-diff", a, b)


@pytest.fixture
def remote(tmp_path: Path) -> tuple[Path, str, str, str]:
    """The upstream repo: base, gold and a wrong agent fix (only a.py), as patches."""
    repo = make_repo(tmp_path / "upstream", [BASE, GOLD])
    make_fixtures_wrong = make_repo(tmp_path / "wrong", [BASE, WRONG])
    base = git(repo, "rev-parse", "c0").strip()
    return repo, base, _diff(repo, "c0", "c1"), _diff(make_fixtures_wrong, "c0", "c1")


def _case(base: str, gold: str, wrong: str) -> tuple[Case, prepare.Prepared]:
    t = task().model_copy(update={"base_commit": base, "patch": gold})
    agent = AgentRun(instance_id=t.instance_id, source_row=7, patch=wrong.rstrip("\n"),
                     submitted=True, resolved=False)  # fmt: skip
    kept = next(v.index for v in patches.variants(gold) if v.path == "pkg/b.py")
    ready = prepare.Prepared(instance_id=t.instance_id, excluded=None, suite_timeout=120,
                             kept=kept, agents=(tried("agent_wrong"),))  # fmt: skip
    return Case(slice="slice2", rank=0, split="dev", task=t, agents=(agent,)), ready


def test_each_fix_is_checked_from_a_fetched_base(
    tmp_path: Path, remote: tuple[Path, str, str, str]
) -> None:
    upstream, base, gold, wrong = remote
    case, ready = _case(base, gold, wrong)
    bench = tmp_path / "bench"
    repro = bench / "results" / "slice2" / case.task.instance_id / "gold-r1" / "repro"
    repro.mkdir(parents=True)
    (repro / "test_tracefix_repro.py").write_text(
        "from pkg import a\n\ndef test_it():\n    assert a.bill(a.LIMIT, 1, 0) == a.LIMIT\n",
        encoding="utf-8",
    )
    found = siblings.measure_task(bench, "slice2", case, ready, url=lambda _: str(upstream))
    assert found["excluded"] is None and found["notes"] == []
    fixes = found["fixes"]
    variant = prepare.variant_kind(ready.kept or 0)
    assert set(fixes) == {"gold", variant, "agent_wrong"}
    assert fixes["gold"]["replaced_code"] == []  # gold fixes both copies
    assert fixes["gold"]["constants"] == ["LIMIT"]
    assert fixes["gold"]["constant_reads"] == ["LIMIT"]
    partial = fixes[variant]
    assert [(s["path"], s["line"]) for s in partial["replaced_code"]] == [("pkg/b.py", 18)]
    assert partial["in_dropped_hunk"] is True
    assert partial["constant_reads"] is None  # no test of that run to read
    assert [(s["path"], s["fixed_at"]) for s in fixes["agent_wrong"]["replaced_code"]] == [
        ("pkg/b.py", "pkg/a.py:18")
    ]
    assert fixes["agent_wrong"]["group"] == "agent_wrong" and partial["group"] == "partial"


def test_a_base_commit_that_cant_be_fetched_excludes_the_task(
    tmp_path: Path, remote: tuple[Path, str, str, str]
) -> None:
    _, base, gold, wrong = remote
    case, ready = _case(base, gold, wrong)
    found = siblings.measure_task(tmp_path / "bench", "slice2", case, ready,
                                  url=lambda _: str(tmp_path / "missing"))  # fmt: skip
    assert found["fixes"] == {} and found["excluded"].startswith("git fetch failed")


def test_the_fetched_tree_is_reused(tmp_path: Path, remote: tuple[Path, str, str, str]) -> None:
    upstream, base, *_ = remote
    tree = tmp_path / "tree"
    siblings.fetch(str(upstream), base, tree)
    siblings.fetch(str(tmp_path / "gone"), base, tree)  # the commit is there: no fetch at all
    assert git(tree, "cat-file", "-t", base).strip() == "commit"


def _fix(group: str, **fired: bool) -> dict[str, object]:
    out: dict[str, object] = {"group": group, "constant_reads": None}
    for signal in ("replaced_code", "replaced_line", "same_name"):
        out[signal] = [{"path": "x.py"}] if fired.get(signal) else []
    if fired.get("constant_reads"):
        out["constant_reads"] = ["LIMIT"]
    return out


def test_summary_and_the_pre_registered_rule() -> None:
    wrong = [_fix("partial", replaced_code=True) for _ in range(4)] + [_fix("agent_wrong")] * 6
    right = [_fix("gold")] * 9 + [_fix("agent_ok", replaced_code=True, same_name=True)]
    tasks = [{"excluded": None, "fixes": {str(i): f for i, f in enumerate(wrong + right)}},
             {"excluded": "git fetch failed", "fixes": {}}]  # fmt: skip
    summary = siblings.summarise(tasks)
    assert summary["excluded_tasks"] == 1
    assert summary["groups"]["partial"]["replaced_code"] == {"n": 4, "of": 4}
    decision = siblings.decide(summary)
    # 4/10 wrong against 1/10 correct: 30 points apart, correct at 10%: built.
    assert decision["replaced_code"] == {"wrong": "4/10", "correct": "1/10", "build": True}
    assert decision["same_name"]["build"] is False  # 0/10 against 1/10
    assert decision["constant_reads"] == {"fires": "0/0", "build": False}


def test_the_rule_needs_correct_fixes_quiet() -> None:
    fixes = [_fix("partial", replaced_code=True)] * 5 + [_fix("gold", replaced_code=True)] * 2
    fixes += [_fix("gold")] * 3
    summary = siblings.summarise([{"excluded": None,
                                   "fixes": {str(i): f for i, f in enumerate(fixes)}}])  # fmt: skip
    # 100% wrong against 40% correct: far apart, but correct fixes fire too often.
    assert siblings.decide(summary)["replaced_code"]["build"] is False
    md = siblings.markdown("t", summary, siblings.decide(summary))
    assert "| partial | 5 | 5/5 (100%)" in md and "do not build" in md
