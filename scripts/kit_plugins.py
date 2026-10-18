#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kit_plugins —— 插件管理的第一片（3.0 第一轮）：list / show / verify 只读，enable / disable 只改 `plugins` 键。

用法（调度器 `python scripts/pi_dispatch.py plugins …` 原样转发到这里）：
  python scripts/kit_plugins.py list [--json]              每个插件一行：ID、版本、启用、锁、资源、缺的权限、状态
  python scripts/kit_plugins.py show <ID> [--json]         manifest 字段、每个资源的哈希核对、锁的 generation 与 lock_sha256
  python scripts/kit_plugins.py verify [ID] [--json]       核对所选插件（缺省全部）与“列入但未安装”；有问题退出 1
  python scripts/kit_plugins.py enable <ID> [--allow-permission P …] [--dry-run]
  python scripts/kit_plugins.py disable <ID> [--dry-run]

设计与调用边界见 docs/themis-tally-3.0-r1-日志与插件管理.md 的 D5、D6、D10、D11：只读核对复用 codekit/plugins.py，
决策题库另调 codekit/decisions.verify_battery_lock；链接与 junction 检查、fix 提示、整份校验写入都复用
pi_dispatch 与 kit_config 的公开函数，不另写同类实现。只依赖标准库。
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pi_dispatch as pd  # noqa: E402
import kit_config  # noqa: E402

try:
    from codekit import decisions as decisions  # noqa: E402
    from codekit import plugins as plugins  # noqa: E402
    from codekit import protocols as protocols  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - 包就在本文件旁边
    from scripts.codekit import decisions as decisions  # type: ignore[no-redef]
    from scripts.codekit import plugins as plugins  # type: ignore[no-redef]
    from scripts.codekit import protocols as protocols  # type: ignore[no-redef]

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2

# 合同写明的固定词。
_OK = "一致"
_DRIFT = "漂移"
_INVALID = "无效"
_LINK = "无效：链接"
_ROOT_LINK = "无效：链接 plugins"  # 第八节第 1 行：plugins 根是链接（文字与 --json 都含它）
_UNSUPPORTED = "本轮不支持"
_MISMATCH = "不一致"
_READY = "READY"
_BLOCKED = "BLOCKED"

_CRLF = b"\r\n"
_LF = b"\n"


# ---------------------------------------------------------------------------
# 枚举与读前检查
# ---------------------------------------------------------------------------

def _plugins_root() -> Path:
    return pd.KIT_ROOT / "plugins"


def _root_problem() -> Optional[str]:
    """plugins/ 根本身的问题：是链接（第八节第 1 行），或是目录却列不出来（闸二 B2）；没有问题时 None。

    列不出来时枚举为空，不能当作“没有插件”：list 与 verify 把它报出来，verify 因此退出 1。
    """
    root = _plugins_root()
    if pd.is_link_or_junction(root):
        return _ROOT_LINK
    try:
        if not root.is_dir():
            return None
        next(iter(root.iterdir()), None)
    except OSError as exc:
        return "无效：plugins 列不出来：%s" % exc
    return None


def _enumerate_entries() -> List[Tuple[str, bool]]:
    """plugins/ 下匹配 PLUGIN_ID 的直接子目录 [(名字, 是否链接)]；根是链接或不存在时为空。

    链接目录（含悬空链接）也列出，list / verify 把它报成“无效：链接”。普通文件不列出。
    """
    root = _plugins_root()
    try:  # 根与子目录的 is_dir() 遇到 EACCES 也会抛（闸二第 2 轮 B2）；根的问题由 _root_problem 报出
        if pd.is_link_or_junction(root) or not root.is_dir():
            return []
        children = sorted(root.iterdir())
    except OSError:
        return []
    entries: List[Tuple[str, bool]] = []
    for child in children:
        if not plugins.PLUGIN_ID.fullmatch(child.name):  # match 会放过末尾的换行
            continue
        is_link = pd.is_link_or_junction(child)
        try:
            if not is_link and not child.is_dir():
                continue
        except OSError:
            pass  # 判断不了是不是目录：照常列出，由逐插件核对报“无效”
        entries.append((child.name, is_link))
    return entries


def _require_exists(plugin_id: str) -> None:
    names = {name for name, _ in _enumerate_entries()}
    if plugin_id not in names:
        problem = _root_problem()
        raise pd.DispatchError("插件不存在或未安装：%s%s" % (plugin_id, "（%s）" % problem if problem else ""),
                               EXIT_USAGE)


def _link_level(kit_root: Path, rel: str) -> Optional[str]:
    """rel 从 kit_root 往下第一个链接/junction 那一级；没有返回 None，路径非法也当作被挡下。"""
    try:
        return pd.first_link_component(kit_root, rel)
    except ValueError:
        return rel


def _read_json_file(kit_root: Path, rel: str) -> Tuple[Any, bool, Optional[str]]:
    """读前逐级链接检查 + 普通文件确认 + strict 解析。返回 (obj, is_link_error, msg)。

    obj 为 None 时 is_link_error 区分“链接/越界”（msg 是链接那一级，调用方记 无效：链接）与其它失败
    （msg 是具体原因，调用方记 无效）。
    """
    link = _link_level(kit_root, rel)
    if link is not None:
        return None, True, link
    path = kit_root / rel
    if pd.is_link_or_junction(path) or not path.is_file():
        return None, False, "不是普通文件"
    try:
        data = path.read_bytes()
    except OSError as exc:
        return None, False, "读取失败：%s" % exc
    try:
        obj = protocols.strict_json_loads(data)
    except ValueError as exc:
        return None, False, "解析失败：%s" % exc
    if obj is None:  # JSON 的 null：调用方把 None 当作读取失败，原因要写具体（第八节第 4、6 行）
        return None, False, "不是对象（内容是 null）"
    return obj, False, None


def _json_problem(label: str, is_link: bool, msg: str) -> str:
    """清单读失败的问题文字：链接类含“无效：链接”，其它类只写具体原因。"""
    if is_link:
        return "%s：%s %s" % (label, _LINK, msg)
    return "%s：%s" % (label, msg)


# ---------------------------------------------------------------------------
# 单插件核对（D5、第八节裁定表）
# ---------------------------------------------------------------------------

def _check_resources(kit_root: Path, plugin_id: str, normalized_lock: Dict[str, Any]
                     ) -> Tuple[str, Optional[str], List[str], List[Dict[str, Any]]]:
    """核对插件的资源。返回 (锁列, 资源列, 问题, 行)。

    资源列为 None 表示“未核对/被链接类失败挡下”（list 显示 -）；锁列只在出现读取失败时改“无效”，
    哈希不符（含仅 CRLF）不改锁列。链接/越界/非普通文件（第 10–12 行）立即停止并返回。
    """
    prefix = "plugins/%s" % plugin_id
    resources: List[Dict[str, Any]] = []
    for row in normalized_lock.get("plugins", []):
        if row.get("plugin_id") == plugin_id:
            resources = row.get("resources", [])
            break
    rows: List[Dict[str, Any]] = []
    problems: List[str] = []
    read_failed = False
    for ref in resources:
        rel = ref["path"]
        rows.append({"path": rel, "id": ref.get("id", ""), "sha256": ref.get("sha256", ""),
                     "status": _OK, "detail": ""})
        link = _link_level(kit_root, rel)
        if link is not None:
            rows[-1]["status"] = _LINK
            problems.append("资源 %s：%s %s" % (rel, _LINK, link))
            return _INVALID, None, problems, rows
        if not pd.is_within(kit_root / rel, kit_root / prefix):
            rows[-1]["status"] = _LINK
            problems.append("资源 %s：%s（路径越出插件目录）" % (rel, _LINK))
            return _INVALID, None, problems, rows
        path = kit_root / rel
        if pd.is_link_or_junction(path) or not path.is_file():
            rows[-1]["status"] = _LINK
            problems.append("资源 %s：%s（不是普通文件）" % (rel, _LINK))
            return _INVALID, None, problems, rows
        try:
            data = path.read_bytes()
        except OSError as exc:
            rows[-1]["status"] = _MISMATCH
            problems.append("资源读取失败：资源 %s：%s" % (rel, exc))
            read_failed = True
            continue
        if hashlib.sha256(data).hexdigest() == ref["sha256"]:
            rows[-1]["status"] = _OK
        else:
            rows[-1]["status"] = _MISMATCH
            if hashlib.sha256(data.replace(_CRLF, _LF)).hexdigest() == ref["sha256"]:
                rows[-1]["detail"] = "仅行尾不同（CRLF）"
                problems.append("资源 %s 不一致：仅行尾不同（CRLF）" % rel)
            else:
                problems.append("资源 %s 与锁不一致" % rel)
    resource_status: Optional[str] = _MISMATCH if any(r["status"] == _MISMATCH for r in rows) else _OK
    lock_status = _INVALID if read_failed else _OK
    return lock_status, resource_status, problems, rows


def _check_battery(kit_root: Path, plugin_id: str) -> Tuple[Optional[str], Optional[str], List[str]]:
    """decisions 的题库。返回 (锁列或 None, 资源列或 None, 问题)；None 表示不改动对应列。

    链接/非普通目录/非普通清单（第 15–16 行）→ 锁列“无效”；列举失败或 verify_battery_lock 抛错
    （第 17–18 行）→ 资源列“不一致”、锁列不改。
    """
    rel = "plugins/%s/questions" % plugin_id
    link = _link_level(kit_root, rel)
    if link is not None:
        return _INVALID, None, ["questions 目录：%s %s" % (_LINK, link)]
    questions = kit_root / rel
    if pd.is_link_or_junction(questions) or not questions.is_dir():
        return _INVALID, None, ["questions 目录：%s（不是普通目录）" % _LINK]
    try:
        names = sorted(entry.name for entry in questions.glob("*.json"))
    except OSError as exc:
        return None, _MISMATCH, ["题库与内容锁不一致：questions 列举失败：%s" % exc]
    for name in names:
        file_link = _link_level(kit_root, "plugins/%s/questions/%s" % (plugin_id, name))
        if file_link is not None:
            return _INVALID, None, ["题库 %s：%s %s" % (name, _LINK, file_link)]
        entry = kit_root / ("plugins/%s/questions/%s" % (plugin_id, name))
        if pd.is_link_or_junction(entry) or not entry.is_file():
            return _INVALID, None, ["题库 %s：%s（不是普通文件）" % (name, _LINK)]
    try:
        decisions.verify_battery_lock(pd.DECISIONS_PLUGIN_DIR)
    except (ValueError, OSError, decisions.DecisionError) as exc:
        return None, _MISMATCH, ["题库与内容锁不一致：%s" % exc]
    return None, None, []


def _check_plugin(plugin_id: str, allowed: Any = None) -> Dict[str, Any]:
    kit_root = pd.KIT_ROOT
    report: Dict[str, Any] = {
        "plugin_id": plugin_id, "lock_status": _INVALID, "resource_status": None,
        "problems": [], "manifest": None, "lock": None, "lock_raw": None,
        "resource_rows": [], "permissions": [], "depends_on": [], "conflicts": [],
        "missing_permissions": [], "permission_ready": True,
    }
    manifest, m_link, m_msg = _read_json_file(kit_root, "plugins/%s/manifest.json" % plugin_id)
    if manifest is None:
        report["problems"].append(_json_problem("manifest.json", m_link, m_msg))
        return report
    lock, l_link, l_msg = _read_json_file(kit_root, "plugins/%s/lock.json" % plugin_id)
    if lock is None:
        report["problems"].append(_json_problem("lock.json", l_link, l_msg))
        return report
    report["lock_raw"] = lock if isinstance(lock, dict) else None
    if not isinstance(manifest, dict) or manifest.get("plugin_id") != plugin_id:
        pid = manifest.get("plugin_id") if isinstance(manifest, dict) else "（非对象）"
        report["problems"].append("目录名与 plugin_id 不一致：目录 %s，plugin_id %s" % (plugin_id, pid))
        return report
    try:
        normalized_manifest = plugins.validate_manifest(manifest)
    except ValueError as exc:
        report["problems"].append("manifest.json 无效：%s" % exc)
        return report
    report["manifest"] = normalized_manifest
    report["permissions"] = list(normalized_manifest.get("permissions", []))
    report["depends_on"] = list(normalized_manifest.get("depends_on", []))
    report["conflicts"] = list(normalized_manifest.get("conflicts", []))
    if isinstance(allowed, list):
        try:
            result = plugins.check_permission_intersection(
                normalized_manifest, allowed_permissions=allowed, platform_name=None)
            report["missing_permissions"] = list(result.get("missing_permissions", []))
            report["permission_ready"] = result.get("status") == _READY
        except ValueError as exc:  # 核对不了就按不满足处理，不放行（kit-plugins a002 复审 F5）
            report["permission_ready"] = False
            report["problems"].append("权限核对失败：%s" % exc)
    if not isinstance(lock, dict):  # 第八节第 6 行先于第 7 行
        report["problems"].append("lock.json：不是对象")
        return report
    if normalized_manifest.get("depends_on") or normalized_manifest.get("conflicts"):
        report["lock_status"] = _UNSUPPORTED
        report["problems"].append("带 depends_on 或 conflicts 的插件本轮不支持")
        return report
    try:
        normalized_lock = plugins.validate_lock(lock, {plugin_id: normalized_manifest})
    except ValueError as exc:
        code = getattr(exc, "code", "")
        report["lock_status"] = _DRIFT if code in ("E_PLUGIN_LOCK_DRIFT", "E_PLUGIN_LOCK_BINDING") else _INVALID
        report["problems"].append("lock.json：%s" % exc)
        return report
    report["lock"] = normalized_lock
    report["lock_status"] = _OK
    res_lock, res_status, res_problems, res_rows = _check_resources(kit_root, plugin_id, normalized_lock)
    report["resource_rows"] = res_rows
    report["lock_status"] = res_lock
    if res_status is not None:
        report["resource_status"] = res_status
    report["problems"].extend(res_problems)
    if res_status is None:
        return report  # 链接类资源失败：停止，不核对题库
    if plugin_id == decisions.PLUGIN_ID:
        b_lock, b_resource, b_problems = _check_battery(kit_root, plugin_id)
        if b_lock is not None:
            report["lock_status"] = b_lock
        if b_resource is not None:
            report["resource_status"] = b_resource
        report["problems"].extend(b_problems)
    return report


def _check_plugin_safe(plugin_id: str, allowed: Any = None) -> Dict[str, Any]:
    """逐插件收集 ValueError/OSError/DecisionError（第十六节）：记“无效”，不拖垮命令。"""
    try:
        return _check_plugin(plugin_id, allowed)
    except (ValueError, OSError, decisions.DecisionError) as exc:
        return {"plugin_id": plugin_id, "lock_status": _INVALID, "resource_status": None,
                "problems": ["核对失败：%s" % exc], "manifest": None, "lock": None, "lock_raw": None,
                "resource_rows": [], "permissions": [], "depends_on": [], "conflicts": [],
                "missing_permissions": [], "permission_ready": True}


def _is_consistent(report: Dict[str, Any]) -> bool:
    return report["lock_status"] == _OK and report["resource_status"] == _OK


# ---------------------------------------------------------------------------
# 配置视图
# ---------------------------------------------------------------------------

def _plugins_view(config: Dict[str, Any]) -> Dict[str, Any]:
    section = config.get("plugins")
    is_dict = isinstance(section, dict)
    return {
        "enabled_present": is_dict and "enabled" in section,
        "enabled_value": section.get("enabled") if is_dict else None,
        "allowed_present": is_dict and "allowed_permissions" in section,
        "allowed_value": section.get("allowed_permissions") if is_dict else None,
    }


def _allowed_list(view: Dict[str, Any]) -> Optional[List[str]]:
    """限制时的 allowed_permissions 列表；不限制或不是列表时 None（第九节：此时不调用权限核对）。"""
    if view["allowed_present"] and isinstance(view["allowed_value"], list):
        return view["allowed_value"]
    return None


def _is_enabled(view: Dict[str, Any], plugin_id: str) -> bool:
    if not view["enabled_present"]:
        return True  # 不限制：全部算启用
    value = view["enabled_value"]
    return isinstance(value, list) and plugin_id in value


def _enabled_label(view: Dict[str, Any], plugin_id: str) -> str:
    if not view["enabled_present"]:
        return "不限制"
    return "是" if _is_enabled(view, plugin_id) else "否"


def _not_installed(config: Dict[str, Any], entries: List[Tuple[str, bool]]) -> List[str]:
    """enabled 里不在枚举结果（含链接目录）中的 ID（第六、七节）。"""
    view = _plugins_view(config)
    value = view["enabled_value"]
    if not view["enabled_present"] or not isinstance(value, list):
        return []
    present = {name for name, _ in entries}
    return [name for name in value if name not in present]


# ---------------------------------------------------------------------------
# list / show / verify 的渲染
# ---------------------------------------------------------------------------

def _list_row(report: Dict[str, Any], view: Dict[str, Any]) -> Dict[str, Any]:
    version = report["manifest"]["version"] if report["manifest"] else "-"
    missing = report["missing_permissions"]
    enabled = _enabled_label(view, report["plugin_id"])
    resource = report["resource_status"] if report["resource_status"] else "-"
    lock_ok = report["lock_status"] == _OK
    resource_ok = report["resource_status"] == _OK
    if lock_ok and resource_ok and report["permission_ready"]:
        status, reason = _READY, ""
    else:
        status = _BLOCKED
        if not lock_ok:
            # 原因带上首条问题：链接类失败因此含“无效：链接”（第二节、裁定表），漂移等词照旧可见
            reason = report["lock_status"]
            if report["problems"]:
                reason = "%s：%s" % (reason, report["problems"][0])
        elif not resource_ok:
            reason = "资源%s" % (report["resource_status"] or "未核对")
        elif missing:
            reason = "缺 %s" % "、".join(missing)
        else:
            reason = report["problems"][0] if report["problems"] else "权限未满足"
    return {"id": report["plugin_id"], "version": version, "enabled": enabled,
            "lock": report["lock_status"], "resource": resource, "missing": missing,
            "status": status, "reason": reason}


def _format_list_row(row: Dict[str, Any]) -> str:
    perm = "缺 %s" % "、".join(row["missing"]) if row["missing"] else "无缺失"
    tail = "（%s）" % row["reason"] if row["reason"] else ""
    return "%s  %s  启用:%s  锁:%s  资源:%s  权限:%s  状态:%s%s" % (
        row["id"], row["version"], row["enabled"], row["lock"], row["resource"], perm, row["status"], tail)


def _verify_word(report: Dict[str, Any]) -> str:
    """verify 标题行的词（第二节）：锁列非一致用锁列值；锁一致而资源不一致用“资源不一致”；都一致用“一致”。"""
    if report["lock_status"] != _OK:
        return report["lock_status"]
    if report["resource_status"] != _OK:
        return "资源%s" % (report["resource_status"] or "未核对")
    return _OK


def cmd_list(args: argparse.Namespace) -> int:
    repo = _discover(args.repo)
    config = kit_config.load_config(repo)
    _require_plugins_section(config, repo)
    view = _plugins_view(config)
    allowed = _allowed_list(view)
    entries = _enumerate_entries()
    root_problem = _root_problem()
    rows: List[Dict[str, Any]] = []
    for name, is_link in entries:
        if is_link:
            rows.append({"id": name, "version": "-", "enabled": _enabled_label(view, name),
                         "lock": _INVALID, "resource": "-", "missing": [], "status": _BLOCKED,
                         "reason": "%s plugins/%s" % (_LINK, name)})
        else:
            rows.append(_list_row(_check_plugin_safe(name, allowed), view))
    not_installed = _not_installed(config, entries)
    if args.json:
        print(json.dumps({"plugins_root_link": root_problem == _ROOT_LINK, "plugins": rows,
                          "not_installed": not_installed, "problems": [root_problem] if root_problem else []},
                         ensure_ascii=False))
        return EXIT_OK
    if root_problem:
        print(root_problem)
    for row in rows:
        print(_format_list_row(row))
    for name in not_installed:
        print("%s 未安装" % name)
    return EXIT_OK


def cmd_show(args: argparse.Namespace) -> int:
    repo = _discover(args.repo)
    plugin_id = _validate_id(args.plugin_id)
    _require_exists(plugin_id)
    config = kit_config.load_config(repo)
    _require_plugins_section(config, repo)
    view = _plugins_view(config)
    report = _check_plugin_safe(plugin_id, _allowed_list(view))
    manifest = report["manifest"]
    lock_raw = report["lock_raw"]
    missing = report["missing_permissions"]
    if args.json:
        obj = {
            "plugin_id": plugin_id, "lock_status": report["lock_status"],
            "resource_status": report["resource_status"], "problems": report["problems"],
            "version": manifest.get("version") if manifest else None,
            "api_version": manifest.get("api_version") if manifest else None,
            "capabilities": manifest.get("capabilities", []) if manifest else [],
            "permissions": report["permissions"],
            "platforms": manifest.get("platforms", []) if manifest else [],
            "depends_on": report["depends_on"], "conflicts": report["conflicts"],
            "checks": manifest.get("checks", []) if manifest else [],
            "lock": {"generation": lock_raw.get("generation") if lock_raw else None,
                     "lock_sha256": lock_raw.get("lock_sha256") if lock_raw else None},
            "resources": report["resource_rows"],
            "config": {"enabled": _enabled_label(view, plugin_id),
                       "allowed_permissions": view["allowed_value"] if view["allowed_present"] else None,
                       "missing_permissions": missing},
        }
        print(json.dumps(obj, ensure_ascii=False))
        return EXIT_OK
    print("插件 %s" % plugin_id)
    if manifest is not None:  # manifest 没通过核对时没有这些字段；锁、启用、权限、状态与问题照常输出（第二节）
        print("版本 %s" % manifest.get("version"))
        print("api_version %s" % manifest.get("api_version"))
        print("capabilities %s" % "、".join(manifest.get("capabilities", [])))
        print("permissions %s" % "、".join(report["permissions"]))
        print("platforms %s" % "、".join(manifest.get("platforms", [])))
        print("depends_on %s" % ("、".join(report["depends_on"]) if report["depends_on"] else "（无）"))
        print("conflicts %s" % ("、".join(report["conflicts"]) if report["conflicts"] else "（无）"))
        print("checks %s" % json.dumps(manifest.get("checks", []), ensure_ascii=False))
    if lock_raw is not None:
        print("锁 generation %s" % lock_raw.get("generation"))
        print("锁 lock_sha256 %s" % lock_raw.get("lock_sha256"))
    for row in report["resource_rows"]:
        detail = "（%s）" % row["detail"] if row["detail"] else ""
        print("资源 %s %s%s" % (row["path"], row["status"], detail))
    print("启用 %s" % _enabled_label(view, plugin_id))
    print("权限 %s" % ("缺 %s" % "、".join(missing) if missing else "无缺失"))
    print("状态 %s%s" % (report["lock_status"],
                         "" if report["resource_status"] in (None, _OK) else "／资源%s" % report["resource_status"]))
    for problem in report["problems"]:
        print("问题：%s" % problem)
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    repo = _discover(args.repo)
    targets: List[str] = []
    if args.plugin_id is not None:
        plugin_id = _validate_id(args.plugin_id)
        _require_exists(plugin_id)
        targets = [plugin_id]
    config = kit_config.load_config(repo)
    _require_plugins_section(config, repo)
    view = _plugins_view(config)
    allowed = _allowed_list(view)
    root_problem = _root_problem() if args.plugin_id is None else None
    not_installed: List[str] = []
    if args.plugin_id is None:
        entries = _enumerate_entries()
        targets = [name for name, _ in entries]
        not_installed = _not_installed(config, entries)
    reports = [_check_plugin_safe(name, allowed) for name in targets]
    problematic = bool(root_problem) or bool(not_installed) or any(not _is_consistent(r) for r in reports)
    if args.json:
        print(json.dumps({
            "ok": not problematic, "plugins_root_link": root_problem == _ROOT_LINK,
            "plugins": [{"id": r["plugin_id"], "lock": r["lock_status"],
                         "resource": r["resource_status"], "problems": r["problems"]} for r in reports],
            "not_installed": not_installed, "problems": [root_problem] if root_problem else [],
        }, ensure_ascii=False))
        return EXIT_FAIL if problematic else EXIT_OK
    if root_problem:
        print(root_problem)
    for report in reports:
        print("%s %s" % (report["plugin_id"], _verify_word(report)))
        if not _is_consistent(report):
            for problem in report["problems"]:
                print("  %s" % problem)
    for name in not_installed:
        print("%s 未安装" % name)
    return EXIT_FAIL if problematic else EXIT_OK


# ---------------------------------------------------------------------------
# enable / disable（D6）
# ---------------------------------------------------------------------------

def _permission_impact(plugin_id: str, old_allowed: set, new_allowed: set
                       ) -> Tuple[List[str], List[str]]:
    """授予权限后因此满足权限条件的其它插件，以及它们读取时的问题（不静默跳过，含链接目录）。"""
    granted = new_allowed - old_allowed
    impact: List[str] = []
    problems: List[str] = []
    for name, _is_link in _enumerate_entries():
        if name == plugin_id:
            continue
        try:
            obj, is_link_error, msg = _read_json_file(pd.KIT_ROOT, "plugins/%s/manifest.json" % name)
        except (ValueError, OSError) as exc:  # 第十六节：授予路径同样逐插件收集
            problems.append("%s %s：核对失败：%s" % (name, _INVALID, exc))
            continue
        if obj is None:
            if is_link_error:
                problems.append("%s %s %s" % (name, _LINK, msg))
            else:
                problems.append("%s %s：%s" % (name, _INVALID, msg))
            continue
        try:
            normalized = plugins.validate_manifest(obj)
        except ValueError as exc:
            problems.append("%s %s：%s" % (name, _INVALID, exc))
            continue
        required = set(normalized.get("permissions", []))
        if required & granted and not (required - new_allowed):
            impact.append(name)
    return impact, problems


def _battery_gate(repo: Any, new_config: Dict[str, Any]) -> None:
    """写入前：新配置里决策插件若仍生效，先核对题库；不一致就拒绝并给恢复顺序（D6）。"""
    try:
        settings = decisions.settings_from_config(new_config, repo.agent_dir, pd.DECISIONS_PLUGIN_DIR)
    except decisions.DecisionError:
        return  # 配置错误交给整份校验报告
    if not settings.active:
        return
    try:
        link = kit_config.battery_link_problem()  # 读之前先查链接，经过链接就不读（闸二 B1）
        if link is not None:
            raise decisions.DecisionError("battery_drift", "%s %s" % (_LINK, link))
        decisions.verify_battery_lock(pd.DECISIONS_PLUGIN_DIR)
    except (ValueError, OSError, decisions.DecisionError) as exc:
        raise kit_config.ConfigError(
            "决策插件生效且问题清单与内容锁不一致，未写入。恢复顺序：先 `plugins disable decisions` 或 "
            "`config decisions off`（写入后决策插件不再生效、不再触发题库核对，可以落盘），修好题库后再启用。（%s）" % exc)


def _change_lines(old_config: Dict[str, Any], new_config: Dict[str, Any]) -> List[str]:
    """每个发生变化的 plugins 子键一行：`plugins.<键>: <旧> → <新>`（旧值不存在写“未设置”）。"""
    old_p = old_config.get("plugins")
    new_p = new_config.get("plugins")
    old_p = old_p if isinstance(old_p, dict) else {}
    new_p = new_p if isinstance(new_p, dict) else {}
    lines: List[str] = []
    for key in ("enabled", "allowed_permissions"):
        old_has, new_has = key in old_p, key in new_p
        if not old_has and not new_has:
            continue
        old_text = json.dumps(old_p[key], ensure_ascii=False) if old_has else "未设置"
        new_text = json.dumps(new_p[key], ensure_ascii=False) if new_has else "未设置"
        if old_text != new_text:
            lines.append("plugins.%s: %s → %s" % (key, old_text, new_text))
    return lines


def _finish_mutation(repo: Any, txn: Any, old_config: Dict[str, Any], new_config: Dict[str, Any], dry_run: bool,
                     messages: List[str], impact: List[str], grant_problems: List[str]) -> int:
    change_lines = _change_lines(old_config, new_config)
    changed = bool(change_lines)
    _battery_gate(repo, new_config)  # 无变化与写入共用：先题库门禁
    if not dry_run and changed:
        try:
            txn.publish(new_config)  # 锁内整份校验、记历史与审计、原子替换（3.0 第二轮 D7）；“审计不全”原样透传
        except OSError as exc:
            raise kit_config.ConfigError("写入失败：%s" % exc)
    else:
        errors = kit_config.validate_config(new_config, repo)
        if errors:
            raise kit_config.ConfigError("没有写入：" + "；".join(errors))
    # 到这里就是成功（写入 / dry-run / 无变化）
    for line in change_lines:
        print(line)
    for problem in grant_problems:
        print(problem)
    if impact:
        print("以下插件也将满足权限条件：%s" % "、".join(impact))
    for message in messages:
        print(message)
    if not changed:
        print("没有变化")
        return EXIT_OK
    if dry_run:
        print("plugins 段（dry-run，未写入）：")
        print(json.dumps(new_config.get("plugins", {}), ensure_ascii=False, indent=2))
    else:
        print("已写入 %s" % kit_config.config_path(repo))
    return EXIT_OK


def cmd_enable(args: argparse.Namespace) -> int:
    repo = _discover(args.repo)
    plugin_id = _validate_id(args.plugin_id)
    _require_exists(plugin_id)
    with kit_config.config_transaction(repo, "plugin.enable", plugin_id) as txn:  # 读改写都在配置锁内
        return _enable(repo, txn, plugin_id, args)


def _enable(repo: Any, txn: Any, plugin_id: str, args: argparse.Namespace) -> int:
    config = txn.config
    _require_plugins_section(config, repo)
    view = _plugins_view(config)
    report = _check_plugin_safe(plugin_id, _allowed_list(view))
    if not _is_consistent(report):
        raise kit_config.ConfigError("无法启用 %s：%s" % (plugin_id, _reject_reason(report)))
    supplied = list(args.allow_permission or [])
    new_config = copy.deepcopy(config)
    messages: List[str] = []
    if not view["enabled_present"]:
        messages.append("当前不限制，所有插件都算启用")
    elif isinstance(view["enabled_value"], list) and plugin_id not in view["enabled_value"]:
        new_config.setdefault("plugins", {})["enabled"] = sorted(set(view["enabled_value"]) | {plugin_id})
    impact: List[str] = []
    grant_problems: List[str] = []
    if view["allowed_present"] and isinstance(view["allowed_value"], list):
        missing = list(report["missing_permissions"])
        if missing:
            if set(supplied) != set(missing):
                raise pd.DispatchError(
                    "启用 %s 缺权限 %s，--allow-permission 必须一个不多一个不少地给出（收到 %s）"
                    % (plugin_id, "、".join(missing), "、".join(sorted(set(supplied))) or "无"), EXIT_USAGE)
            new_allowed = sorted(set(view["allowed_value"]) | set(supplied))
            new_config.setdefault("plugins", {})["allowed_permissions"] = new_allowed
            impact, grant_problems = _permission_impact(plugin_id, set(view["allowed_value"]), set(new_allowed))
        elif supplied:
            raise pd.DispatchError("没有缺失的权限，不需要 --allow-permission", EXIT_USAGE)
    elif supplied:
        raise pd.DispatchError("当前不限制权限，不需要 --allow-permission", EXIT_USAGE)
    return _finish_mutation(repo, txn, config, new_config, args.dry_run, messages, impact, grant_problems)


def cmd_disable(args: argparse.Namespace) -> int:
    repo = _discover(args.repo)
    plugin_id = _validate_id(args.plugin_id)
    _require_exists(plugin_id)
    with kit_config.config_transaction(repo, "plugin.disable", plugin_id) as txn:  # 读改写都在配置锁内
        return _disable(repo, txn, plugin_id, args)


def _disable(repo: Any, txn: Any, plugin_id: str, args: argparse.Namespace) -> int:
    config = txn.config
    _require_plugins_section(config, repo)
    view = _plugins_view(config)
    new_config = copy.deepcopy(config)
    messages: List[str] = []
    if not view["enabled_present"]:
        new_enabled = sorted(name for name, is_link in _enumerate_entries()
                             if not is_link and name != plugin_id)
        new_config.setdefault("plugins", {})["enabled"] = new_enabled
        messages.append("从不限制改为显式列表，之后新增的插件不会自动启用")
    elif isinstance(view["enabled_value"], list) and plugin_id in view["enabled_value"]:
        new_config.setdefault("plugins", {})["enabled"] = sorted(
            name for name in view["enabled_value"] if name != plugin_id)
    # 否则不在列表里：无变化
    if plugin_id == decisions.PLUGIN_ID and _is_enabled(view, decisions.PLUGIN_ID) \
            and not _is_enabled(_plugins_view(new_config), decisions.PLUGIN_ID):
        messages.append("决策插件会因此变为 off")
    return _finish_mutation(repo, txn, config, new_config, args.dry_run, messages, [], [])


def _reject_reason(report: Dict[str, Any]) -> str:
    parts: List[str] = []
    if report["lock_status"] != _OK:
        parts.append("锁%s" % report["lock_status"])
    if report["resource_status"] not in (None, _OK):
        parts.append("资源%s" % report["resource_status"])
    parts.extend(report["problems"])
    return "；".join(parts) if parts else _MISMATCH


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def _discover(repo_arg: Optional[str]) -> Any:
    return pd.Repo.discover(repo_arg)


def _validate_id(plugin_id: Any) -> str:
    if not isinstance(plugin_id, str) or not plugins.PLUGIN_ID.fullmatch(plugin_id):
        raise pd.DispatchError("插件 ID 不合法：%r" % (plugin_id,), EXIT_USAGE)
    return plugin_id


def _require_plugins_section(config: Dict[str, Any], repo: Any) -> None:
    """plugins 段格式校验（第七节）：不合法就拒绝（退出 1），附 plugins_fix_hint 的修复提示，不写配置。"""
    error = kit_config.plugins_section_error(config)
    if error is None:
        return
    hint = kit_config.plugins_fix_hint(config, repo)
    message = error if not hint else "%s；修复：%s" % (error, hint)
    raise kit_config.ConfigError(message, EXIT_FAIL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kit_plugins.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", help="仓库路径（默认当前目录）")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("list", help="每个插件一行：启用、锁、资源、缺的权限、状态")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="manifest 字段、资源哈希核对、锁的 generation 与 lock_sha256")
    p.add_argument("plugin_id")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("verify", help="核对所选插件（缺省全部）与“列入但未安装”；有问题退出 1")
    p.add_argument("plugin_id", nargs="?")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("enable", help="启用一个插件，可授予所缺权限；--dry-run 只预览")
    p.add_argument("plugin_id")
    p.add_argument("--allow-permission", action="append", default=[], metavar="P")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_enable)

    p = sub.add_parser("disable", help="关闭一个插件；--dry-run 只预览")
    p.add_argument("plugin_id")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_disable)
    return parser


def main(argv: Optional[Sequence[str]] = None, repo: Optional[str] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if repo is not None and not args.repo:
        args.repo = repo
    if not getattr(args, "func", None):
        parser.print_help()
        return EXIT_USAGE
    try:
        return int(args.func(args))
    except pd.DispatchError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return exc.code
    except kit_config.ConfigError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("已取消。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
