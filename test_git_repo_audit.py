import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from git_repo_audit import inspect, parse_status, read_status


SCRIPT = Path(__file__).with_name("git_repo_audit.py")


class StatusParserTests(unittest.TestCase):
    def test_parses_nul_separated_git_records(self):
        result = parse_status(
            "# branch.head main\0# branch.upstream origin/main\0# branch.ab +2 -3\0"
            "1 MM m metadata with whitespace\0? new file\0u UU unresolved\0"
        )
        self.assertEqual(
            (result["ahead"], result["behind"], result["staged"], result["unstaged"],
             result["untracked"], result["conflicts"]),
            (2, 3, 1, 1, 1, 1),
        )


@unittest.skipUnless(shutil.which("git"), "Git gerekli")
class GitRepoAuditTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
        environment.start()
        self.addCleanup(environment.stop)

    def git(self, path, *args):
        return subprocess.run(["git", "-C", str(path), *args], capture_output=True, check=True)

    def init(self, path):
        path.mkdir(parents=True)
        self.git(path, "init", "--template=")
        self.git(path, "symbolic-ref", "HEAD", "refs/heads/main")

    def commit(self, path, message):
        self.git(path, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "--allow-empty", "-m", message)

    def test_dirty_status_and_index_unchanged(self):
        repo = self.root / "example"
        self.init(repo)
        target = repo / "tracked.txt"
        target.write_text("original", encoding="utf-8")
        self.git(repo, "add", "tracked.txt")
        self.commit(repo, "first")
        target.write_text("staged", encoding="utf-8")
        self.git(repo, "add", "tracked.txt")
        target.write_text("unstaged", encoding="utf-8")
        (repo / "other file.txt").touch()
        index = repo / ".git" / "index"
        before = index.stat().st_mtime_ns, index.read_bytes()
        report = read_status(repo)
        self.assertEqual((report["staged"], report["unstaged"], report["untracked"]), (1, 1, 1))
        self.assertEqual((index.stat().st_mtime_ns, index.read_bytes()), before)

    def test_ahead_and_behind_are_local(self):
        repo = self.root / "example"
        self.init(repo)
        self.commit(repo, "base")
        self.git(repo, "switch", "-c", "baseline")
        self.commit(repo, "baseline only")
        self.git(repo, "switch", "main")
        self.commit(repo, "main only")
        self.git(repo, "branch", "--set-upstream-to", "baseline")
        report = read_status(repo)
        self.assertEqual((report["upstream"], report["ahead"], report["behind"]), ("baseline", 1, 1))

    def test_worktree_and_depth_are_recognized(self):
        repo = self.root / "example"
        self.init(repo)
        self.commit(repo, "base")
        worktree = self.root / "nested" / "working"
        worktree.parent.mkdir()
        self.git(repo, "worktree", "add", "--detach", str(worktree))
        self.assertEqual(len(inspect(self.root.resolve(), 1)["repositories"]), 1)
        reports = inspect(self.root.resolve(), 2)["repositories"]
        self.assertEqual(len(reports), 2)
        self.assertTrue(next(item for item in reports if Path(item["path"]).name == "working")["detached"])

    def test_cli_returns_one_for_untracked_file_in_unborn_repo(self):
        repo = self.root / "example"
        self.init(repo)
        (repo / "untracked.txt").touch()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.root), "--check", "--json"], capture_output=True, check=False
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["repositories"][0]["untracked"], 1)
        self.assertTrue(report["repositories"][0]["unborn"])


if __name__ == "__main__":
    unittest.main()
