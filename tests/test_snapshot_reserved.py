"""Windows 保留设备名的文件不拖垮候选快照（第 104 轮）。

新版 Windows 在带目录的路径里会把 `nul`、`con` 这类名字建成真文件，git 却打不开它们，`git add -A` 整个失败。
T017 attempt-001 的测试替身把报告写到了 `ts/nul`，90 分钟、20 个文件的改动没收进候选。快照现在排除这些路径，
并在候选记录里列出来交给复审。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "scripts"))

import pi_dispatch as pd  # noqa: E402

pytestmark = pytest.mark.skipif(os.name != "nt", reason="只有 Windows 上 git 打不开保留设备名")


def repo_with_reserved_file(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "t"]):
        subprocess.run(["git"] + args, cwd=str(repo), check=True)
    (repo / "base.txt").write_text("基线\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=str(repo), check=True)
    (repo / "ts").mkdir()
    (repo / "ts" / "kept.ts").write_text("export const x = 1;\n", encoding="utf-8")
    with open("\\\\?\\" + str(repo / "ts" / "nul"), "w", encoding="utf-8") as handle:  # 只有扩展路径建得出来
        handle.write("测试替身的报告\n")
    return repo


def test_reserved_names_are_left_out_of_the_snapshot(tmp_path):
    repo = repo_with_reserved_file(tmp_path)
    base = pd.git_text(["rev-parse", "HEAD"], repo)
    with pytest.raises(pd.DispatchError, match="ts/nul"):  # 不排除就是 T017 attempt-001 的样子
        pd.git(["add", "-A", "--", "."], repo, index_file=tmp_path / "plain.index")
    assert pd.unindexable_paths(repo) == ["ts/nul"]
    tree = pd.snapshot_tree(repo, base, tmp_path, "candidate")
    names = pd.git(["ls-tree", "-r", "--name-only", tree], repo).stdout.decode("utf-8").split()
    assert names == ["base.txt", "ts/kept.ts"]


def test_the_candidate_lists_what_it_left_out(tmp_path):
    repo = repo_with_reserved_file(tmp_path)
    base = pd.git_text(["rev-parse", "HEAD"], repo)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    candidate = pd.record_candidate(pd.Repo(repo), run_dir, repo, base)
    assert candidate["unindexable_skipped"] == ["ts/nul"] and candidate["patch_roundtrip_verified"] is True
    assert "ts/kept.ts" in (run_dir / "candidate.patch").read_text(encoding="utf-8")


@pytest.mark.parametrize("name, reserved", [("nul", True), ("NUL.txt", True), ("con", True), ("com1.log", True),
                                            ("lpt9", True), ("null", False), ("console", False), ("com10", False),
                                            ("nul_report", False)])
def test_which_names_are_reserved(name, reserved):
    assert bool(pd.RESERVED_NAME_RE.match(name)) is reserved
