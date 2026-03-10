#!/usr/bin/env python3

import subprocess
import tempfile
from pathlib import Path


def run(cmd, cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        text=True,
        capture_output=True,
    )
    if check and proc.returncode != 0:
        cmd_text = " ".join(cmd)
        raise AssertionError(
            f"command failed: {cmd_text}\n"
            f"cwd: {cwd}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def assert_in(needle: str, haystack: str, message: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"{message}: missing {needle!r}\n--- output ---\n{haystack}")


def assert_not_in(needle: str, haystack: str, message: str) -> None:
    if needle in haystack:
        raise AssertionError(f"{message}: found unexpected {needle!r}\n--- output ---\n{haystack}")


def main() -> None:
    branch_name = "feature/foo"
    worktree_dir_name = "feature-foo"
    target_branch = "main"

    with tempfile.TemporaryDirectory(prefix="git-worktrees-smoke-") as tmp_dir:
        temp_root = Path(tmp_dir)
        repo_root = temp_root / "repo"
        repo_root.mkdir()

        run(["git", "init", "-b", target_branch], cwd=repo_root)
        run(["git", "config", "user.name", "Smoke Test"], cwd=repo_root)
        run(["git", "config", "user.email", "smoke@example.com"], cwd=repo_root)

        write_file(repo_root / ".gitignore", ".worktrees/\n")
        write_file(repo_root / "README.md", "# temp repo\n")
        run(["git", "add", ".gitignore", "README.md"], cwd=repo_root)
        run(["git", "commit", "-m", "init"], cwd=repo_root)
        print("OK: created temp repository with ignored .worktrees/ layout")

        (repo_root / ".worktrees").mkdir()
        check_ignore = run(
            ["git", "check-ignore", "-q", ".worktrees/probe"],
            cwd=repo_root,
            check=False,
        )
        assert_equal(check_ignore.returncode, 0, ".worktrees subtree should be ignored")
        print("OK: verified project-local .worktrees/ is ignored")

        initial_worktrees = run(["git", "worktree", "list", "--porcelain"], cwd=repo_root)
        assert_in(str(repo_root), initial_worktrees.stdout, "main checkout missing from worktree list")
        print("OK: recorded baseline worktree list")

        worktree_path = repo_root / ".worktrees" / worktree_dir_name
        run(["git", "worktree", "add", "-b", branch_name, str(worktree_path)], cwd=repo_root)
        assert_equal(worktree_path.parent, repo_root / ".worktrees", "worktree parent should be .worktrees")
        assert_equal(len(worktree_path.relative_to(repo_root / ".worktrees").parts), 1, "worktree dir should be single-segment")
        print(f"OK: created {worktree_path.relative_to(repo_root)} from branch {branch_name}")

        worktree_list = run(["git", "worktree", "list", "--porcelain"], cwd=repo_root).stdout
        assert_in(str(worktree_path), worktree_list, "new worktree missing from porcelain list")
        print("OK: verified new worktree is registered")

        lane_file = worktree_path / "lane.txt"
        write_file(lane_file, "lane-owned change\n")
        run(["git", "add", "lane.txt"], cwd=worktree_path)
        run(["git", "commit", "-m", "add lane change"], cwd=worktree_path)
        print("OK: committed a lane change inside the linked worktree")

        run(["git", "merge", "--ff-only", branch_name], cwd=repo_root)
        main_head = run(["git", "rev-parse", "HEAD"], cwd=repo_root).stdout.strip()
        lane_head = run(["git", "rev-parse", branch_name], cwd=repo_root).stdout.strip()
        assert_equal(main_head, lane_head, "main should fast-forward to the lane head")
        print("OK: merged lane into main with fast-forward history preservation")

        merged_branches = run(["git", "branch", "--merged", target_branch], cwd=repo_root).stdout
        assert_in(branch_name, merged_branches, "lane branch should be marked merged")
        unique_commits = run(["git", "log", f"{target_branch}..{branch_name}"], cwd=repo_root).stdout.strip()
        assert_equal(unique_commits, "", "lane branch should have no unique commits after merge")
        print("OK: verified no unique lane commits remain after merge")

        clean_status = run(["git", "status", "--short"], cwd=worktree_path).stdout.strip()
        assert_equal(clean_status, "", "worktree should be clean before teardown")
        print("OK: verified worktree is clean before teardown")

        run(["git", "worktree", "remove", str(worktree_path)], cwd=repo_root)
        if worktree_path.exists():
            raise AssertionError(f"worktree path still exists after removal: {worktree_path}")
        print("OK: removed the linked worktree")

        branch_list = run(["git", "branch", "--list", branch_name], cwd=repo_root).stdout
        assert_in(branch_name, branch_list, "worktree removal should not delete the branch ref")
        print("OK: verified branch ref still exists after worktree removal")

        run(["git", "worktree", "prune"], cwd=repo_root)
        pruned_worktrees = run(["git", "worktree", "list", "--porcelain"], cwd=repo_root).stdout
        assert_not_in(str(worktree_path), pruned_worktrees, "removed worktree should not remain after prune")
        worktree_entries = [line for line in pruned_worktrees.splitlines() if line.startswith("worktree ")]
        assert_equal(len(worktree_entries), 1, "only the main checkout should remain after prune")
        print("OK: pruned worktree metadata and found no stale worktree entry")

        print("OK: lifecycle smoke completed")


if __name__ == "__main__":
    main()
