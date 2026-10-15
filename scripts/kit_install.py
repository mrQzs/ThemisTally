#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kit_install —— 把 PI-Kit 装进另一个 Git 仓库，并按安装记录分辨“kit 更新了”与“目标本地改过”。

用法：
  python scripts/kit_install.py check <目标仓库>               只读：列出每个条目的状态与汇总，不写任何文件
  python scripts/kit_install.py install <目标仓库> [--force]   首次安装；目标已有安装记录则拒绝（改用 update）
  python scripts/kit_install.py update <目标仓库> [--force]    按安装记录更新；目标没有记录则拒绝（先 install）
  --force                                                    覆盖 KEEP 与 CONFLICT 的文件，覆盖前先备份

这是“把 kit 装进目标仓库”的布局：kit 的运行时、技能与示例按字节复制进目标的 scripts/、.agents/、.claude/ 等，
并留下安装记录 .agent/kit-install.json，供 update 与 doctor 分辨“过期”和“本地改过”。
另一种布局是从 kit 目录直接运行调度器（例如 KitExperiment），那样不需要安装，也不该用本脚本。

每个条目输出一行 `<状态> <路径>`，最后一行是 JSON 汇总。状态：
  ADD       目标里没有这个文件，本次写入 kit 的字节
  SAME      目标里的字节与 kit 相同
  UPDATE    目标是上次安装时的原样而 kit 已经更新，本次写入 kit 的新字节
  KEEP      目标与安装记录不同，是本地改过的，不写（--force 才覆盖并备份）
  CONFLICT  目标已有同名文件而安装记录里没有它，不写（--force 才覆盖并备份）
  APPEND    目标的 .gitignore / .gitattributes 缺少 kit 的规则，本次只在末尾追加，原内容一个字节不改
  MANUAL    AGENTS.md 已存在，永不改写；列出目标里缺少的 kit 章节，由人手工合并
  REMOVED   安装记录里有而 kit 已不再发放的路径，只报告，不删文件

拒绝（退出码 2，stdout 不输出，stderr 一行以 `ERROR: ` 开头，目标里什么也不写）：目标不存在或不是目录；
目标就是 kit 根目录；目标不是 Git 工作区的根目录；kit 的发放内容缺失或其中有符号链接 / junction；
目标里要读写的路径从目标根往下有任何一级是链接，或已存在却不是预期的类型；install 时已有安装记录；
update 时没有记录；记录不是 JSON 对象、record_type 不是 code-kit-install 或 files 不是对象；
未知命令（argparse 的退出码 2）；check 带 --force。
退出码：0 完成；1 这次运行之后仍有 KEEP 或 CONFLICT；2 拒绝或用法错误。
只用标准库；导入无副作用（只在 __main__ 下运行 main）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pi_dispatch as pd  # noqa: E402

#: 八个状态，顺序即输出时的分组顺序（发放文件之后是其它条目）。
STATUSES = ("ADD", "SAME", "UPDATE", "KEEP", "CONFLICT", "APPEND", "MANUAL", "REMOVED")
#: 安装记录在目标仓库里的位置。
RECORD = ".agent/kit-install.json"
RECORD_TYPE = "code-kit-install"
SCHEMA_VERSION = 1
AGENTS_NAME = "AGENTS.md"
CONFIG_NAME = ".agent/dispatch.config.json"
CONFIG_EXAMPLE = ".agent/dispatch.config.example.json"
BACKUP_DIR = ".agent/kit-backup"
APPEND_HEADER = "# Code-Kit（kit_install.py 追加）"
#: 目标仓库名 → kit 里的规则片段。
RULE_SNIPPETS = ((".gitignore", "gitignore.append.txt"), (".gitattributes", "gitattributes.append.txt"))
#: 除运行时、技能与规则之外还发放的文件。
EXTRA_FILES = (".claude/agents/pi-reviewer.md", ".agent/README.md", ".agent/dispatch.config.example.json",
               ".codex/config.example.toml", ".claude/settings.example.json")
EXIT_OK, EXIT_UNRESOLVED, EXIT_USAGE = 0, 1, 2
REPARSE_POINT = 0x400  # Windows 的 FILE_ATTRIBUTE_REPARSE_POINT：junction、符号链接都带


class InstallError(Exception):
    """拒绝：stdout 不输出，stderr 一行 `ERROR: …`，目标里什么也不写。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# --------------------------------------------------------------------------- 小工具


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _norm(path: Path) -> str:
    return os.path.normcase(str(path))


def _is_link(path: str) -> bool:
    """符号链接、Windows junction 或其他重解析点（os.walk 会进入 junction，所以另外查属性）。"""
    if os.path.islink(path):
        return True
    if os.name == "nt":
        try:
            return bool(os.lstat(path).st_file_attributes & REPARSE_POINT)
        except (OSError, AttributeError):
            return False
    return False


def _link_level(root: Path, rel: str) -> Optional[str]:
    """root 之下 rel 从根往下第一个是链接或 junction 的那一级（相对 root 的 POSIX 路径）；没有则 None。"""
    parts = PurePosixPath(rel).parts
    current = root
    for index, part in enumerate(parts):
        current = current / part
        if _is_link(str(current)):
            return PurePosixPath(*parts[:index + 1]).as_posix()
    return None


def _git_toplevel(path: Path) -> Optional[Path]:
    proc = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return None
    out = proc.stdout.decode("utf-8", "replace").strip()
    return Path(out).resolve() if out else None


def _git_head(kit_root: Path) -> Optional[str]:
    proc = subprocess.run(["git", "-C", str(kit_root), "rev-parse", "--verify", "HEAD"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace").strip() or None


def _write_bytes(path: Path, data: bytes) -> None:
    """按字节写入：先写同一目录里的临时文件，再 os.replace；父目录不存在就建。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".kit-install.tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
    os.replace(str(tmp), str(path))


# --------------------------------------------------------------------------- 发放内容


def _collect_dir(kit_root: Path, base: str) -> Set[str]:
    """`base/**` 这一项里的文件（相对 kit_root 的 POSIX 路径）。

    跳过名为 __pycache__ 的目录（连同其中一切）与以 .pyc 结尾的文件；其余任何目录或文件是链接都拒绝。
    """
    root = kit_root / base
    if not root.is_dir():
        raise InstallError("kit 缺少发放目录：%s" % base)
    level = _link_level(kit_root, base)
    if level is not None:
        raise InstallError("kit 的 %s 是符号链接或 junction" % level)
    found: Set[str] = set()
    for dirpath, dirnames, filenames in os.walk(str(root)):
        here = Path(dirpath)
        keep: List[str] = []
        for name in sorted(dirnames):
            child = here / name
            if name == "__pycache__":
                continue
            if _is_link(str(child)):
                raise InstallError("kit 的 %s 是符号链接或 junction" % child.relative_to(kit_root).as_posix())
            keep.append(name)
        dirnames[:] = keep
        for name in sorted(filenames):
            if name.endswith(".pyc"):
                continue
            child = here / name
            if _is_link(str(child)):
                raise InstallError("kit 的 %s 是符号链接或 junction" % child.relative_to(kit_root).as_posix())
            found.add(child.relative_to(kit_root).as_posix())
    return found


def payload(kit_root: Path) -> List[str]:
    """kit 发放给目标仓库的文件：排序、不重复的仓库相对 POSIX 路径列表。

    依次是调度器与它的入口脚本、`pd.KIT_LOADED_FILES` 的每一项、四个技能在 `pd.SKILL_SOURCE_DIR` 与
    `pd.CLAUDE_SKILL_DIR` 的两份副本、以及 EXTRA_FILES。AGENTS.md、两个 .append.txt 与 kit_install.py
    本身不在其中。缺少任何一项、或任何条目及其中的目录、文件是符号链接或 junction 时拒绝。
    """
    entries = ["scripts/pi_dispatch.py", "scripts/dispatch-pi.sh"]
    entries.extend(pd.KIT_LOADED_FILES)
    for skill in pd.KIT_SKILLS:
        entries.append("%s/%s/**" % (pd.SKILL_SOURCE_DIR, skill))
        entries.append("%s/%s/**" % (pd.CLAUDE_SKILL_DIR, skill))
    entries.extend(EXTRA_FILES)
    found: Set[str] = set()
    for entry in entries:
        if entry.endswith("/**"):
            found |= _collect_dir(kit_root, entry[:-3])
            continue
        level = _link_level(kit_root, entry)
        if level is not None:
            raise InstallError("kit 的 %s 是符号链接或 junction" % level)
        if not (kit_root / entry).is_file():
            raise InstallError("kit 缺少发放文件：%s" % entry)
        found.add(entry)
    return sorted(found)


# --------------------------------------------------------------------------- 拒绝检查


def _check_target_path(target: Path, rel: str, want: str) -> None:
    """目标里要读写的 rel：从目标根往下每一级都不得是链接；末级存在时类型必须匹配（file 或 dir）。"""
    parts = PurePosixPath(rel).parts
    current = target
    for index, part in enumerate(parts):
        current = current / part
        level = PurePosixPath(*parts[:index + 1]).as_posix()
        if _is_link(str(current)):
            raise InstallError("目标里的 %s 是符号链接或 junction（%s）" % (rel, level))
        if not current.exists():
            continue
        if index == len(parts) - 1:
            if want == "file" and not current.is_file():
                raise InstallError("目标里的 %s 已存在且不是普通文件" % rel)
            if want == "dir" and not current.is_dir():
                raise InstallError("目标里的 %s 已存在且不是目录" % rel)
        elif not current.is_dir():
            raise InstallError("目标里的 %s 的上级 %s 已存在且不是目录" % (rel, level))


def _load_record(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InstallError("安装记录 %s 读不出来或不是 JSON：%s" % (RECORD, exc))
    if not isinstance(data, dict):
        raise InstallError("安装记录 %s 不是 JSON 对象" % RECORD)
    if data.get("record_type") != RECORD_TYPE:
        raise InstallError("安装记录 %s 的 record_type 不是 %s" % (RECORD, RECORD_TYPE))
    if not isinstance(data.get("files"), dict):
        raise InstallError("安装记录 %s 的 files 不是对象" % RECORD)
    return data


def _snippet_rules(kit_root: Path, name: str) -> List[str]:
    """kit 规则片段里去掉首尾空白后非空、且不以 # 开头的行（保持顺序、去重）。"""
    rules: List[str] = []
    for line in (kit_root / name).read_text(encoding="utf-8").splitlines():
        rule = line.strip()
        if rule and not rule.startswith("#") and rule not in rules:
            rules.append(rule)
    return rules


def _lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines()]


# --------------------------------------------------------------------------- 主流程


def _run(command: str, target_arg: str, force: bool) -> int:
    if command == "check" and force:
        raise InstallError("check 是只读的，不接受 --force")
    kit_root = HERE.parent
    raw = Path(target_arg)
    if not raw.is_dir():
        raise InstallError("目标不存在或不是目录：%s" % target_arg)
    target = raw.resolve()
    if _norm(target) == _norm(kit_root):
        raise InstallError("目标就是 kit 根目录本身：%s（从 kit 目录直接运行调度器不需要安装）" % target)
    toplevel = _git_toplevel(target)
    if toplevel is None or _norm(toplevel) != _norm(target):
        raise InstallError("目标不是 Git 工作区的根目录：%s" % target_arg)
    files = payload(kit_root)
    kit_bytes = {rel: (kit_root / rel).read_bytes() for rel in files}

    for rel in list(files) + [AGENTS_NAME, CONFIG_NAME] + [name for name, _ in RULE_SNIPPETS]:
        _check_target_path(target, rel, "file")
    _check_target_path(target, RECORD, "file")
    _check_target_path(target, BACKUP_DIR, "dir")

    record: Optional[Dict[str, Any]] = None
    if (target / RECORD).is_file():
        record = _load_record(target / RECORD)
    if command == "install" and record is not None:
        raise InstallError("目标已有安装记录 %s：改用 update（加 --force 才会覆盖本地改过的文件）" % RECORD)
    if command == "update" and record is None:
        raise InstallError("目标没有安装记录 %s：先运行 install" % RECORD)

    old_files: Dict[str, Any] = dict(record["files"]) if record else {}
    writable = command in ("install", "update")
    rows: List[Tuple[str, str, Optional[str]]] = []
    writes: List[Tuple[str, bytes]] = []
    new_files: Dict[str, str] = {}
    unresolved: List[str] = []
    backup_rel: Optional[str] = None

    def backup_dir() -> str:
        nonlocal backup_rel
        if backup_rel is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            candidate = "%s/%s" % (BACKUP_DIR, stamp)
            index = 2
            while (target / candidate).exists():
                candidate = "%s/%s-%d" % (BACKUP_DIR, stamp, index)
                index += 1
            backup_rel = candidate
        return backup_rel

    for rel in files:
        data = kit_bytes[rel]
        path = target / rel
        known = old_files.get(rel)
        if not path.exists():
            rows.append(("ADD", rel, None))
            if writable:
                writes.append((rel, data))
            new_files[rel] = _sha(data)
            continue
        current = path.read_bytes()
        if current == data:
            rows.append(("SAME", rel, None))
            new_files[rel] = _sha(data)
        elif known is not None and _sha(current) == known:
            rows.append(("UPDATE", rel, None))
            if writable:
                writes.append((rel, data))
            new_files[rel] = _sha(data)
        elif force and writable:
            folder = backup_dir()
            writes.append(("%s/%s" % (folder, rel), current))
            writes.append((rel, data))
            new_files[rel] = _sha(data)
            rows.append(("UPDATE", rel, "--force：原文件备份到 %s/%s" % (folder, rel)))
        elif known is None:
            rows.append(("CONFLICT", rel, None))
            unresolved.append(rel)
        else:
            rows.append(("KEEP", rel, None))
            new_files[rel] = known
            unresolved.append(rel)

    agents_path = target / AGENTS_NAME
    if not agents_path.exists():
        rows.append(("ADD", AGENTS_NAME, None))
        if writable:
            writes.append((AGENTS_NAME, (kit_root / AGENTS_NAME).read_bytes()))
    else:
        kit_heads = [line[3:].strip() for line in (kit_root / AGENTS_NAME).read_text(encoding="utf-8").splitlines()
                     if line.startswith("## ")]
        mine = set(line[3:].strip() for line in agents_path.read_text(encoding="utf-8", errors="replace").splitlines()
                   if line.startswith("## "))
        missing = [head for head in kit_heads if head not in mine]
        if missing:
            rows.append(("MANUAL", AGENTS_NAME, "缺少 kit 章节：" + "、".join(missing)))
        else:
            rows.append(("SAME", AGENTS_NAME, None))

    for name, snippet in RULE_SNIPPETS:
        rules = _snippet_rules(kit_root, snippet)
        path = target / name
        original = path.read_bytes() if path.exists() else b""
        mine = set(_lines(original.decode("utf-8", errors="replace")))
        missing = [rule for rule in rules if rule not in mine]
        if not missing:
            rows.append(("SAME", name, None))
            continue
        rows.append(("APPEND", name, "补上 " + "、".join(missing)))
        data = original
        if data and not data.endswith(b"\n"):
            data += b"\n"
        if data:
            data += b"\n"
        data += (APPEND_HEADER + "\n" + "".join(rule + "\n" for rule in missing)).encode("utf-8")
        if writable:
            writes.append((name, data))

    if not (target / CONFIG_NAME).exists():
        rows.append(("ADD", CONFIG_NAME, None))
        if writable:
            writes.append((CONFIG_NAME, (kit_root / CONFIG_EXAMPLE).read_bytes()))

    for rel in sorted(set(old_files) - set(files)):
        rows.append(("REMOVED", rel, "kit 已不再发放，没有删除"))

    kit_toplevel = _git_toplevel(kit_root)
    if kit_toplevel is not None and _norm(kit_toplevel) == _norm(kit_root):
        kit_commit = _git_head(kit_root)
        if kit_commit:
            proc = subprocess.run(["git", "-C", str(kit_root), "diff", "--quiet", "HEAD", "--"] + list(files),
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            kit_dirty: Optional[bool] = proc.returncode != 0
        else:
            kit_dirty = None
    else:
        kit_commit, kit_dirty = None, None

    if writable:
        for rel, data in writes:
            _write_bytes(target / rel, data)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        installed_at = record.get("installed_at") if record else None
        if not isinstance(installed_at, str) or not installed_at:
            installed_at = now
        record_out = {
            "record_type": RECORD_TYPE,
            "schema_version": SCHEMA_VERSION,
            "kit_version": pd.TOOL_VERSION,
            "kit_commit": kit_commit,
            "kit_dirty": kit_dirty,
            "installed_at": installed_at,
            "updated_at": now,
            "files": {rel: new_files[rel] for rel in sorted(new_files)},
        }
        _write_bytes(target / RECORD,
                     (json.dumps(record_out, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    counts = {status: 0 for status in STATUSES}
    for status, _rel, _detail in rows:
        counts[status] += 1
    summary = {
        "command": command,
        "target": str(target),
        "kit_root": str(kit_root),
        "kit_version": pd.TOOL_VERSION,
        "kit_commit": kit_commit,
        "counts": counts,
        "unresolved": unresolved,
        "backup": backup_rel,
        "record": RECORD if writable else (RECORD if record is not None else None),
    }
    for status, rel, detail in rows:
        print("%s %s%s" % (status, rel, ("  " + detail) if detail else ""))
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return EXIT_UNRESOLVED if unresolved else EXIT_OK


class _Parser(argparse.ArgumentParser):
    """用法错误也走 `ERROR: ` 一行，退出码仍是 argparse 的 2。"""

    def error(self, message: str) -> Any:
        print("ERROR: %s" % message, file=sys.stderr)
        raise SystemExit(EXIT_USAGE)


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="kit_install", description="把 PI-Kit 装进另一个 Git 仓库，并按记录分辨更新与本地改动",
                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("check", "install", "update"),
                        help="check 只读；install 首次安装；update 按安装记录更新")
    parser.add_argument("target", help="目标仓库的工作区根目录")
    parser.add_argument("--force", action="store_true",
                        help="覆盖 KEEP 与 CONFLICT 的文件，覆盖前把原文件备份到 .agent/kit-backup/<时间>/")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        return _run(args.command, args.target, bool(args.force))
    except InstallError as exc:
        print("ERROR: %s" % exc.message, file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
