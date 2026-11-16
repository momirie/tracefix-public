"""M2: ref resolution and worktrees."""

import os
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import make_fixtures
import pytest
from conftest import make_repo

from tracefix.workspace import Workspace, WorkspaceError, resolve_ref

CASES = sorted(make_fixtures.CASES)


def rev(repo: Path, ref: str) -> str:
    return make_fixtures.git(repo, "rev-parse", ref)


@pytest.fixture
def good_fix(tmp_path: Path) -> Path:
    """A private build, so tests can add refs or check out without affecting other tests."""
    return make_fixtures.build_case("good_fix", tmp_path / "repos")


# --- resolve_ref ------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES)
def test_base_and_head_resolve_to_their_tags(case: str, built: dict[str, Path]) -> None:
    repo = built[case]
    assert resolve_ref(repo, "base") == rev(repo, "refs/tags/base")
    assert resolve_ref(repo, "head") == rev(repo, "refs/tags/head")


def test_bare_head_means_head_tag_not_dot_git_head(good_fix: Path) -> None:
    # On Windows/macOS git would match `head` to .git/HEAD; with base checked out that is wrong.
    make_fixtures.git(good_fix, "checkout", "--quiet", "refs/tags/base")
    assert resolve_ref(good_fix, "head") == rev(good_fix, "refs/tags/head")
    assert resolve_ref(good_fix, "HEAD") == rev(good_fix, "refs/tags/base")


def test_full_ref_names_and_branches(good_fix: Path) -> None:
    head = rev(good_fix, "refs/tags/head")
    assert resolve_ref(good_fix, "refs/tags/head") == head
    assert resolve_ref(good_fix, "main") == head
    assert resolve_ref(good_fix, "refs/heads/main") == head


def test_abbreviated_and_full_commit_ids(good_fix: Path) -> None:
    head = rev(good_fix, "refs/tags/head")
    assert resolve_ref(good_fix, head) == head
    assert resolve_ref(good_fix, head[:7]) == head
    assert resolve_ref(good_fix, head[:10].upper()) == head


def test_tag_and_branch_with_same_name_on_different_commits_is_ambiguous(good_fix: Path) -> None:
    make_fixtures.git(good_fix, "branch", "base", "refs/tags/head")
    with pytest.raises(WorkspaceError, match="ambiguous"):
        resolve_ref(good_fix, "base")


def test_tag_and_branch_with_same_name_on_same_commit_is_accepted(good_fix: Path) -> None:
    make_fixtures.git(good_fix, "branch", "head", "refs/tags/head")
    assert resolve_ref(good_fix, "head") == rev(good_fix, "refs/tags/head")


def test_name_that_is_also_a_commit_prefix_is_ambiguous(good_fix: Path) -> None:
    base_prefix = rev(good_fix, "refs/tags/base")[:8]
    make_fixtures.git(good_fix, "tag", base_prefix, "refs/tags/head")
    with pytest.raises(WorkspaceError, match="ambiguous"):
        resolve_ref(good_fix, base_prefix)


def test_annotated_tag_is_peeled_to_its_commit(good_fix: Path) -> None:
    make_fixtures.git(good_fix, "tag", "-a", "v1", "-m", "release", "refs/tags/base")
    assert resolve_ref(good_fix, "v1") == rev(good_fix, "refs/tags/base")


def test_ref_to_a_tree_is_rejected(good_fix: Path) -> None:
    make_fixtures.git(good_fix, "tag", "treetag", "refs/tags/head^{tree}")
    with pytest.raises(WorkspaceError, match="not a commit"):
        resolve_ref(good_fix, "treetag")


@pytest.mark.parametrize(
    "ref", ["nope", "abc", "HEAD~1", "Head", "-x", "--output=x", "", "a b", "base\n"]
)
def test_unknown_or_unsafe_refs_are_rejected(good_fix: Path, ref: str) -> None:
    with pytest.raises(WorkspaceError):
        resolve_ref(good_fix, ref)


# --- Workspace --------------------------------------------------------------------------------


def test_copies_are_exactly_the_resolved_commits(built: dict[str, Path]) -> None:
    # M3.5 replaced worktrees with plain copies: every file must match the commit byte for byte,
    # nothing else may be there, and there is no .git link back to the user's repo.
    repo = built["no_fix"]
    with Workspace(repo, "base", "head") as ws:
        assert ws.base_sha == rev(repo, "refs/tags/base")
        assert ws.head_sha == rev(repo, "refs/tags/head")
        for sha, copy in ((ws.base_sha, ws.base), (ws.head_sha, ws.head)):
            listed = make_fixtures.git(repo, "ls-tree", "-r", "--name-only", sha).split()
            on_disk = sorted(p.relative_to(copy).as_posix() for p in copy.rglob("*") if p.is_file())
            assert on_disk == sorted(listed)
            for name in listed:
                blob = subprocess.run(
                    ["git", "show", f"{sha}:{name}"], cwd=repo, capture_output=True, check=True
                ).stdout
                assert (copy / name).read_bytes() == blob, name
            assert not (copy / ".git").exists()
        assert (ws.head / "src" / "crm" / "contacts.py").read_text("utf-8") != (
            ws.base / "src" / "crm" / "contacts.py"
        ).read_text("utf-8")


def test_copy_paths_are_neutral(built: dict[str, Path]) -> None:
    # Fixture dirs are named after their answers; nothing downstream may see that name. Base and
    # head have the same name in different random folders, so a path never tells them apart.
    for case in CASES:
        with Workspace(built[case], "base", "head") as ws:
            for path in (ws.root, ws.base, ws.head):
                assert case not in str(path)
            assert ws.base.name == ws.head.name == "repo"
            parents = {ws.root, ws.base.parent, ws.head.parent}
            assert len(parents) == 3
            assert all(p.name.startswith("tracefix-") for p in parents)


def test_users_working_copy_and_worktree_list_are_unchanged(good_fix: Path) -> None:
    (good_fix / "uncommitted.txt").write_text("user's work in progress")
    status_before = make_fixtures.git(good_fix, "status", "--porcelain")
    worktrees_before = make_fixtures.git(good_fix, "worktree", "list", "--porcelain")
    head_before = rev(good_fix, "HEAD")

    with Workspace(good_fix, "base", "head") as ws:
        root = ws.root
        assert "uncommitted.txt" not in {p.name for p in ws.head.iterdir()}

    assert not root.exists()
    assert make_fixtures.git(good_fix, "status", "--porcelain") == status_before
    assert make_fixtures.git(good_fix, "worktree", "list", "--porcelain") == worktrees_before
    assert rev(good_fix, "HEAD") == head_before


def test_cleanup_happens_after_an_error(good_fix: Path) -> None:
    with pytest.raises(RuntimeError), Workspace(good_fix, "base", "head") as ws:
        root = ws.root
        raise RuntimeError("stage crashed")
    assert not root.exists()
    assert len(make_fixtures.git(good_fix, "worktree", "list").splitlines()) == 1


def test_cleanup_survives_a_worktree_already_deleted(good_fix: Path) -> None:
    with Workspace(good_fix, "base", "head") as ws:
        shutil.rmtree(ws.head)
    assert len(make_fixtures.git(good_fix, "worktree", "list").splitlines()) == 1


def test_bad_ref_creates_nothing(good_fix: Path) -> None:
    with pytest.raises(WorkspaceError, match="unknown ref"):
        Workspace(good_fix, "base", "nope").__enter__()
    assert len(make_fixtures.git(good_fix, "worktree", "list").splitlines()) == 1


def test_not_a_git_repo(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="not a git repository"):
        Workspace(tmp_path, "base", "head").__enter__()


def test_repo_hooks_do_not_run_on_checkout(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "repo", [{"a.py": "x = 1\n"}, {"a.py": "x = 2\n"}])
    marker = tmp_path / "hook-ran"
    hooks = repo / ".git" / "hooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "post-checkout"
    hook.write_text(f"#!/bin/sh\necho ran > '{marker.as_posix()}'\n", newline="\n")
    hook.chmod(0o755)
    with Workspace(repo, "c0", "c1"):
        pass
    assert not marker.exists()


def test_folder_inside_a_repo_is_rejected(good_fix: Path) -> None:
    # Otherwise a mistyped path inside some enclosing repo would silently verify that repo.
    with pytest.raises(WorkspaceError, match="not a git repository"):
        Workspace(good_fix / "src", "base", "head").__enter__()


def test_failing_cleanup_never_hides_the_original_error(
    good_fix: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tracefix.workspace as workspace

    real_rmtree = workspace.rmtree

    def locked(path: Path) -> None:
        raise PermissionError(f"[WinError 32] file in use: {path}")

    monkeypatch.setattr(workspace, "rmtree", locked)
    monkeypatch.setattr(workspace.time, "sleep", lambda _s: None)
    with (
        pytest.warns(UserWarning, match="could not remove"),
        pytest.raises(RuntimeError, match="original stage error"),
        Workspace(good_fix, "base", "head") as ws,
    ):
        raise RuntimeError("original stage error")
    assert ws.root in ws.leftovers
    real_rmtree(ws.root)  # tidy up for real


def test_users_own_stale_worktree_entry_is_kept(good_fix: Path, tmp_path: Path) -> None:
    # A user worktree whose folder is temporarily missing (e.g. on an unmounted drive).
    user_wt = tmp_path / "usr-wt"
    make_fixtures.git(
        good_fix, "worktree", "add", "--quiet", "-b", "feature", str(user_wt), "refs/tags/base"
    )
    shutil.rmtree(user_wt)
    before = make_fixtures.git(good_fix, "worktree", "list", "--porcelain")
    assert "usr-wt" in before
    with Workspace(good_fix, "base", "head"):
        pass
    assert make_fixtures.git(good_fix, "worktree", "list", "--porcelain") == before


def test_cleanup_works_when_repo_uses_relative_worktree_paths(good_fix: Path) -> None:
    make_fixtures.git(good_fix, "config", "worktree.useRelativePaths", "true")
    with Workspace(good_fix, "base", "head"):
        pass
    assert len(make_fixtures.git(good_fix, "worktree", "list").splitlines()) == 1
    assert not (good_fix / ".git" / "worktrees").exists() or not any(
        (good_fix / ".git" / "worktrees").iterdir()
    )


@pytest.fixture
def other_owner(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """Make git treat every repo as owned by another account, and replace the machine's global
    and system git config with empty files, so the test doesn't depend on what this machine
    trusts (CI runners trust more than a dev laptop). Tests write trust into home/.gitconfig.
    """
    import tracefix.workspace as workspace

    real_env = workspace.git_env
    monkeypatch.setattr(
        workspace, "git_env", lambda: {**real_env(), "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1"}
    )
    home = tmp_path / "home"
    home.mkdir()
    (home / ".gitconfig").write_text("")
    (tmp_path / "system-gitconfig").write_text("")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    # `git config --system` ignores GIT_CONFIG_NOSYSTEM, so point both files somewhere empty.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / ".gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "system-gitconfig"))
    workspace.user_safe_directories.cache_clear()
    yield home
    workspace.user_safe_directories.cache_clear()


def test_repo_owned_by_another_account_gets_a_clear_message(
    good_fix: Path, other_owner: Path
) -> None:
    with pytest.raises(WorkspaceError, match="another account owns it"):
        Workspace(good_fix, "base", "head").__enter__()


def test_users_own_safe_directory_trust_is_honoured(good_fix: Path, other_owner: Path) -> None:
    (other_owner / ".gitconfig").write_text(f"[safe]\n\tdirectory = {good_fix.as_posix()}\n")
    with Workspace(good_fix, "base", "head") as ws:
        assert ws.head_sha


def test_repo_cannot_mark_itself_safe(good_fix: Path, other_owner: Path) -> None:
    make_fixtures.git(good_fix, "config", "--add", "safe.directory", "*")
    assert "*" in make_fixtures.git(good_fix, "config", "--local", "--get-all", "safe.directory")
    with pytest.raises(WorkspaceError, match="another account owns it"):
        Workspace(good_fix, "base", "head").__enter__()


# --- M3.5: plain exported copies ----------------------------------------------------------------


def _index_add(repo: Path, mode: str, content_or_oid: str, path: str) -> None:
    """Stage an entry with any mode (symlink, submodule) without needing it on disk."""
    if mode == "160000":
        oid = content_or_oid
    else:
        oid = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=repo, input=content_or_oid.encode(), capture_output=True, check=True,
        ).stdout.decode().strip()  # fmt: skip
    make_fixtures.git(repo, "update-index", "--add", "--cacheinfo", f"{mode},{oid},{path}")


def test_export_ignores_attributes_and_handles_odd_entries(tmp_path: Path) -> None:
    repo = make_repo(
        tmp_path / "odd",
        [{
            ".gitattributes": "secret.py export-ignore\nsubst.py export-subst\n",
            "secret.py": "x = 1\n",
            "subst.py": "v = '$Format:%H$'\n",
            "run.sh": "#!/bin/sh\necho hi\n",
        }],
    )  # fmt: skip
    make_fixtures.git(repo, "update-index", "--chmod=+x", "run.sh")
    _index_add(repo, "120000", "../../outside/target", "link")
    _index_add(repo, "160000", "1" * 40, "vendor/sub")
    make_fixtures.git(repo, "commit", "--quiet", "--no-verify", "-m", "odd entries")
    make_fixtures.git(repo, "tag", "odd")
    with Workspace(repo, "odd", "odd") as ws:
        assert (ws.base / "secret.py").read_text() == "x = 1\n"  # export-ignore has no effect
        assert (ws.base / "subst.py").read_text() == "v = '$Format:%H$'\n"  # no substitution
        link = ws.base / "link"
        assert not link.is_symlink() and link.read_text() == "../../outside/target"
        assert not (ws.base / "vendor" / "sub").exists()
        assert "base: vendor/sub (submodule)" in ws.skipped
        if os.name == "posix":
            assert os.access(ws.base / "run.sh", os.X_OK)


@pytest.mark.parametrize(
    ("path", "safe"),
    [
        ("src/pkg/m.py", True),
        ("../escape.py", False),
        ("a/../../escape.py", False),
        ("/etc/passwd", False),
        ("C:/Windows/x.py", False),
        (r"a\b.py", False),
        (".git/hooks/post-checkout", False),
        ("sub/.GIT/config", False),
        ("a//b.py", False),
    ],
)
def test_only_safe_relative_paths_are_exported(path: str, safe: bool) -> None:
    from tracefix.workspace import safe_relpath

    assert (safe_relpath(path) is not None) is safe


def test_files_too_large_to_hash_are_noted_where_rewrites_could_go_unseen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tracefix.snapshots as snapshots

    monkeypatch.setattr(snapshots, "HASH_CAP_BYTES", 10)
    repo = make_repo(tmp_path / "repo", [{"data.bin": "a" * 100, "a.py": "x = 1\n"}, {}])
    with Workspace(repo, "c0", "c1") as ws:
        notes = list(ws.notes)
    if os.name == "nt":
        assert len(notes) == 2 and all("data.bin" in n for n in notes)
        assert {n.split(":")[0] for n in notes} == {"base", "head"}
    else:
        assert notes == []  # POSIX ctime gives a same-size rewrite away
