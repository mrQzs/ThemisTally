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


def _root_is_link() -> bool:
    root = _plugins_root()
    if not root.exists():
        return False
    return pd.is_link_or_junction(root)


def _enumerate_entries() -> List[Tuple[str, bool]]:
    """plugins/ 下匹配 PLUGIN_ID 的直接子目录 [(名字, 是否链接)]；根是链接或不存在时为空。

    链接目录也列出（list / verify 把它报成“无效：链接”），但 _installed_ids 会排除它们。
    """
    root = _plugins_root()
    if not root.is_dir() or pd.is_link_or_junction(root):
        return []
    try:
        children = sorted(root.iterdir())
    except OSError:
        return []
    entries: List[Tuple[str, bool]] = []
    for child in children:
        if not plugins.PLUGIN_ID.match(child.name) or not child.is_dir():
            continue
        entries.append((child.name, pd.is_link_or_junction(child)))
    return entries


def _installed_ids() -> List[str]:
    return sorted(name for name, is_link in _enumerate_entries() if not is_link)


def _require_exists(plugin_id: str) -> None:
    names = {name for name, _ in _enumerate_entries()}
    if plugin_id not in names:
        raise pd.DispatchError("插件不存在或未安装：%s" % plugin_id, EXIT_USAGE)


def _link_level(kit_root: Path, rel: str) -> Optional[str]:
    """rel 从 kit_root 往下第一个链接/junction 那一级；没有返回 None，路径非法也当作被挡下。"""
    try:
        return pd.first_link_component(kit_root, rel)
    except ValueError:
        return rel


def _read_json_file(kit_root: Path, rel: str) -> Tuple[Any, bool, Optional[str]]:
    """读前逐级链接检查 + 普通文件确认 + strict 解析。返回 (obj, is_link_error, msg)。

    obj 为 None 时 is_link_error 区分“链接/越界”（调用方记 无效：链接）与其它失败（记 无效）。
    """
    link = _link_level(kit_root, rel)
    if link is not None:
        return None, True, "链接：%s" % link
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
    return obj, False, None


# ---------------------------------------------------------------------------
# 单插件核对（D5）
# ---------------------------------------------------------------------------

def _check_resources(kit_root: Path, plugin_id: str, normalized_lock: Dict[str, Any]
                     ) -> Tuple[str, List[str], List[Dict[str, Any]]]:
    prefix = "plugins/%s/" % plugin_id
    resources: List[Dict[str, Any]] = []
    for row in normalized_lock.get("plugins", []):
        if row.get("plugin_id") == plugin_id:
            resources = row.get("resources", [])
            break
    rows: List[Dict[str, Any]] = []
    problems: List[str] = []
    for ref in resources:
        rel = ref["path"]
        rows.append({"path": rel, "id": ref.get("id", ""), "sha256": ref.get("sha256", ""),
                     "status": _OK, "detail": ""})
        link = _link_level(kit_root, rel)
        if link is not None:
            rows[-1]["status"] = _LINK
            problems.append("资源 %s：链接 %s" % (rel, link))
            return _LINK, problems, rows
        if not rel.startswith(prefix):
            rows[-1]["status"] = _LINK
            problems.append("资源 %s：路径越出插件目录" % rel)
            return _LINK, problems, rows
        path = kit_root / rel
        if pd.is_link_or_junction(path) or not path.is_file():
            rows[-1]["status"] = _LINK
            problems.append("资源 %s：不是普通文件" % rel)
            return _LINK, problems, rows
        try:
            data = path.read_bytes()
        except OSError as exc:
            rows[-1]["status"] = _MISMATCH
            problems.append("资源 %s 读取失败：%s" % (rel, exc))
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
    status = _MISMATCH if any(row["status"] == _MISMATCH for row in rows) else _OK
    return status, problems, rows


def _check_battery(kit_root: Path, plugin_id: str) -> Tuple[bool, List[str]]:
    """decisions 的题库：questions/ 目录与其中每个 *.json 读前链接检查，再调 verify_battery_lock。"""
    rel = "plugins/%s/questions" % plugin_id
    link = _link_level(kit_root, rel)
    if link is not None:
        return False, ["questions 目录：链接 %s" % link]
    questions = kit_root / rel
    if pd.is_link_or_junction(questions) or not questions.is_dir():
        return False, ["questions 目录：不是普通目录"]
    try:
        names = sorted(entry.name for entry in questions.glob("*.json"))
    except OSError as exc:
        return False, ["questions 目录列举失败：%s" % exc]
    for name in names:
        file_link = _link_level(kit_root, "plugins/%s/questions/%s" % (plugin_id, name))
        if file_link is not None:
            return False, ["题库 %s：链接 %s" % (name, file_link)]
        entry = kit_root / ("plugins/%s/questions/%s" % (plugin_id, name))
        if pd.is_link_or_junction(entry) or not entry.is_file():
            return False, ["题库 %s：不是普通文件" % name]
    try:
        decisions.verify_battery_lock(pd.DECISIONS_PLUGIN_DIR)
    except (ValueError, OSError, decisions.DecisionError) as exc:
        return False, ["题库与内容锁不一致：%s" % exc]
    return True, []


def _check_plugin(plugin_id: str) -> Dict[str, Any]:
    kit_root = pd.KIT_ROOT
    report: Dict[str, Any] = {
        "plugin_id": plugin_id, "lock_status": _INVALID, "resource_status": None,
        "problems": [], "manifest": None, "lock": None, "resource_rows": [],
        "permissions": [], "depends_on": [], "conflicts": [],
    }
    manifest, m_link, m_msg = _read_json_file(kit_root, "plugins/%s/manifest.json" % plugin_id)
    if manifest is None:
        report["lock_status"] = _LINK if m_link else _INVALID
        report["problems"].append("manifest.json：%s" % m_msg)
        return report
    lock, l_link, l_msg = _read_json_file(kit_root, "plugins/%s/lock.json" % plugin_id)
    if lock is None:
        report["lock_status"] = _LINK if l_link else _INVALID
        report["problems"].append("lock.json：%s" % l_msg)
        return report
    if isinstance(manifest, dict) and manifest.get("plugin_id") != plugin_id:
        report["problems"].append("目录名与 plugin_id 不一致：目录 %s，plugin_id %s"
                                  % (plugin_id, manifest.get("plugin_id")))
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
    resource_status, resource_problems, resource_rows = _check_resources(kit_root, plugin_id, normalized_lock)
    report["resource_rows"] = resource_rows
    if resource_status == _LINK:
        report["lock_status"] = _LINK
        report["problems"].extend(resource_problems)
        return report
    report["resource_status"] = resource_status
    report["problems"].extend(resource_problems)
    if plugin_id == decisions.PLUGIN_ID:
        battery_ok, battery_problems = _check_battery(kit_root, plugin_id)
        if not battery_ok:
            report["resource_status"] = _MISMATCH
            report["problems"].extend(battery_problems)
    return report


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


def _enabled_label(view: Dict[str, Any], plugin_id: str) -> str:
    if not view["enabled_present"]:
        return "不限制"
    value = view["enabled_value"]
    return "是" if isinstance(value, list) and plugin_id in value else "否"


def _missing_permissions(view: Dict[str, Any], permissions: List[str]) -> List[str]:
    allowed = view["allowed_value"]
    if not view["allowed_present"] or not isinstance(allowed, list):
        return []
    return sorted(set(permissions) - set(allowed))


def _not_installed(config: Dict[str, Any]) -> List[str]:
    view = _plugins_view(config)
    value = view["enabled_value"]
    if not view["enabled_present"] or not isinstance(value, list):
        return []
    installed = set(_installed_ids())
    return [name for name in value if name not in installed]


# ---------------------------------------------------------------------------
# list / show / verify 的渲染
# ---------------------------------------------------------------------------

def _list_row(report: Dict[str, Any], view: Dict[str, Any]) -> Dict[str, Any]:
    version = report["manifest"]["version"] if report["manifest"] else "-"
    missing = _missing_permissions(view, report["permissions"])
    enabled = _enabled_label(view, report["plugin_id"])
    resource = report["resource_status"] if report["resource_status"] else "-"
    if _is_consistent(report) and not missing:
        status, reason = _READY, ""
    else:
        status = _BLOCKED
        if report["lock_status"] != _OK:
            reason = report["lock_status"]
        elif report["resource_status"] != _OK:
            reason = "资源%s" % (report["resource_status"] or "未核对")
        else:
            reason = "缺 %s" % "、".join(missing)
    return {"id": report["plugin_id"], "version": version, "enabled": enabled,
            "lock": report["lock_status"], "resource": resource, "missing": missing,
            "status": status, "reason": reason}


def _format_list_row(row: Dict[str, Any]) -> str:
    perm = "缺 %s" % "、".join(row["missing"]) if row["missing"] else "无缺失"
    tail = "（%s）" % row["reason"] if row["reason"] else ""
    return "%s  %s  启用:%s  锁:%s  资源:%s  权限:%s  状态:%s%s" % (
        row["id"], row["version"], row["enabled"], row["lock"], row["resource"], perm, row["status"], tail)


def cmd_list(args: argparse.Namespace) -> int:
    repo = _discover(args.repo)
    config = kit_config.load_config(repo)
    view = _plugins_view(config)
    entries = _enumerate_entries()
    root_link = _root_is_link()
    rows: List[Dict[str, Any]] = []
    for name, is_link in entries:
        if is_link:
            rows.append({"id": name, "version": "-", "enabled": _enabled_label(view, name),
                         "lock": _LINK, "resource": "-", "missing": [], "status": _BLOCKED, "reason": _LINK})
        else:
            rows.append(_list_row(_check_plugin(name), view))
    not_installed = _not_installed(config)
    if args.json:
        print(json.dumps({"plugins_root_link": root_link, "plugins": rows, "not_installed": not_installed},
                         ensure_ascii=False))
        return EXIT_OK
    if root_link:
        print("无效：链接 plugins")
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
    view = _plugins_view(config)
    report = _check_plugin(plugin_id)
    manifest = report["manifest"]
    lock = report["lock"]
    if args.json:
        obj = {
            "plugin_id": plugin_id, "lock_status": report["lock_status"],
            "resource_status": report["resource_status"], "problems": report["problems"],
            "version": manifest.get("version") if manifest else None,
            "api_version": manifest.get("api_version") if manifest else None,
            "capabilities": manifest.get("capabilities", []) if manifest else [],
            "permissions": report["permissions"], "platforms": manifest.get("platforms", []) if manifest else [],
            "depends_on": report["depends_on"], "conflicts": report["conflicts"],
            "checks": manifest.get("checks", []) if manifest else [],
            "lock": {"generation": lock.get("generation") if lock else None,
                     "lock_sha256": lock.get("lock_sha256") if lock else None},
            "resources": report["resource_rows"],
            "config": {"enabled": _enabled_label(view, plugin_id),
                       "allowed_permissions": view["allowed_value"] if view["allowed_present"] else None,
                       "missing_permissions": _missing_permissions(view, report["permissions"])},
        }
        print(json.dumps(obj, ensure_ascii=False))
        return EXIT_OK
    print("插件 %s" % plugin_id)
    if manifest is None:
        print("状态：%s" % report["lock_status"])
        for problem in report["problems"]:
            print("  %s" % problem)
        return EXIT_OK
    print("版本 %s" % manifest.get("version"))
    print("api_version %s" % manifest.get("api_version"))
    print("capabilities %s" % "、".join(manifest.get("capabilities", [])))
    print("permissions %s" % "、".join(report["permissions"]))
    print("platforms %s" % "、".join(manifest.get("platforms", [])))
    print("depends_on %s" % ("、".join(report["depends_on"]) if report["depends_on"] else "（无）"))
    print("conflicts %s" % ("、".join(report["conflicts"]) if report["conflicts"] else "（无）"))
    print("checks %s" % json.dumps(manifest.get("checks", []), ensure_ascii=False))
    if lock is not None:
        print("锁 generation %s" % lock.get("generation"))
        print("锁 lock_sha256 %s" % lock.get("lock_sha256"))
    for row in report["resource_rows"]:
        detail = "（%s）" % row["detail"] if row["detail"] else ""
        print("资源 %s %s%s" % (row["path"], row["status"], detail))
    print("启用 %s" % _enabled_label(view, plugin_id))
    missing = _missing_permissions(view, report["permissions"])
    print("权限 %s" % ("缺 %s" % "、".join(missing) if missing else "无缺失"))
    print("状态 %s%s" % (report["lock_status"],
                         "" if report["resource_status"] in (None, _OK) else "／资源%s" % report["resource_status"]))
    return EXIT_OK


def cmd_verify(args: argparse.Namespace) -> int:
    repo = _discover(args.repo)
    config = kit_config.load_config(repo)
    root_link = _root_is_link()
    targets: List[str] = []
    if args.plugin_id is not None:
        plugin_id = _validate_id(args.plugin_id)
        _require_exists(plugin_id)
        targets = [plugin_id]
        not_installed: List[str] = []
    else:
        targets = [name for name, _ in _enumerate_entries()]
        not_installed = _not_installed(config)
    reports = [_check_plugin(name) for name in targets]
    problematic = root_link or bool(not_installed) or any(not _is_consistent(r) for r in reports)
    if args.json:
        print(json.dumps({
            "ok": not problematic, "plugins_root_link": root_link,
            "plugins": [{"id": r["plugin_id"], "lock": r["lock_status"],
                         "resource": r["resource_status"], "problems": r["problems"]} for r in reports],
            "not_installed": not_installed,
        }, ensure_ascii=False))
        return EXIT_FAIL if problematic else EXIT_OK
    if root_link:
        print("无效：链接 plugins")
    for report in reports:
        if _is_consistent(report):
            print("%s %s" % (report["plugin_id"], _OK))
        else:
            print("%s %s" % (report["plugin_id"], report["lock_status"]))
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
    """授予权限后因此满足权限条件的其它插件，以及它们读取时的问题（不静默跳过）。"""
    granted = new_allowed - old_allowed
    impact: List[str] = []
    problems: List[str] = []
    for name, is_link in _enumerate_entries():
        if name == plugin_id or is_link:
            continue
        obj, is_link_error, msg = _read_json_file(pd.KIT_ROOT, "plugins/%s/manifest.json" % name)
        if obj is None:
            problems.append("%s %s：%s" % (name, _LINK if is_link_error else _INVALID, msg))
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
        decisions.verify_battery_lock(pd.DECISIONS_PLUGIN_DIR)
    except (ValueError, OSError, decisions.DecisionError) as exc:
        raise kit_config.ConfigError(
            "决策插件生效且问题清单与内容锁不一致，未写入。恢复顺序：先 `plugins disable decisions` 或 "
            "`config decisions off`（写入后决策插件不再生效、不再触发题库核对，可以落盘），修好题库后再启用。（%s）" % exc)


def _finish_mutation(repo: Any, old_config: Dict[str, Any], new_config: Dict[str, Any], dry_run: bool,
                     messages: List[str], impact: List[str], grant_problems: List[str]) -> int:
    changed = new_config != old_config
    for problem in grant_problems:
        print(problem)
    if impact:
        print("以下插件也将满足权限条件：%s" % "、".join(impact))
    if not changed:
        errors = kit_config.validate_config(new_config, repo)
        if errors:
            raise kit_config.ConfigError("没有写入：" + "；".join(errors))
        for message in messages:
            print(message)
        print("没有变化")
        return EXIT_OK
    _battery_gate(repo, new_config)
    if dry_run:
        errors = kit_config.validate_config(new_config, repo)
        if errors:
            raise kit_config.ConfigError("没有写入：" + "；".join(errors))
        for message in messages:
            print(message)
        print("plugins 段（dry-run，未写入）：")
        print(json.dumps(new_config.get("plugins", {}), ensure_ascii=False, indent=2))
        return EXIT_OK
    try:
        kit_config.write_checked(repo, new_config)
    except OSError as exc:
        raise kit_config.ConfigError("写入失败：%s" % exc)
    for message in messages:
        print(message)
    print("已写入 %s" % kit_config.config_path(repo))
    return EXIT_OK


def cmd_enable(args: argparse.Namespace) -> int:
    repo = _discover(args.repo)
    plugin_id = _validate_id(args.plugin_id)
    _require_exists(plugin_id)
    config = kit_config.load_config(repo)
    report = _check_plugin(plugin_id)
    if not _is_consistent(report):
        raise kit_config.ConfigError("无法启用 %s：%s" % (plugin_id, _reject_reason(report)))
    view = _plugins_view(config)
    supplied = list(args.allow_permission or [])
    new_config = copy.deepcopy(config)
    messages: List[str] = []
    changed = False
    if not view["enabled_present"]:
        messages.append("当前不限制，所有插件都算启用")
    elif isinstance(view["enabled_value"], list) and plugin_id not in view["enabled_value"]:
        new_config.setdefault("plugins", {})["enabled"] = sorted(set(view["enabled_value"]) | {plugin_id})
        changed = True
    impact: List[str] = []
    grant_problems: List[str] = []
    if view["allowed_present"] and isinstance(view["allowed_value"], list):
        missing = sorted(set(report["permissions"]) - set(view["allowed_value"]))
        if missing:
            if set(supplied) != set(missing):
                raise pd.DispatchError(
                    "启用 %s 缺权限 %s，--allow-permission 必须一个不多一个不少地给出（收到 %s）"
                    % (plugin_id, "、".join(missing), "、".join(sorted(set(supplied))) or "无"), EXIT_USAGE)
            new_allowed = sorted(set(view["allowed_value"]) | set(supplied))
            new_config.setdefault("plugins", {})["allowed_permissions"] = new_allowed
            changed = True
            impact, grant_problems = _permission_impact(plugin_id, set(view["allowed_value"]), set(new_allowed))
        elif supplied:
            raise pd.DispatchError("没有缺失的权限，不需要 --allow-permission", EXIT_USAGE)
    elif not view["allowed_present"]:
        if supplied:
            raise pd.DispatchError("当前不限制权限，不需要 --allow-permission", EXIT_USAGE)
    return _finish_mutation(repo, config, new_config, args.dry_run, messages, impact, grant_problems)


def cmd_disable(args: argparse.Namespace) -> int:
    repo = _discover(args.repo)
    plugin_id = _validate_id(args.plugin_id)
    _require_exists(plugin_id)
    config = kit_config.load_config(repo)
    view = _plugins_view(config)
    new_config = copy.deepcopy(config)
    messages: List[str] = []
    changed = False
    if not view["enabled_present"]:
        new_enabled = sorted(name for name in _installed_ids() if name != plugin_id)
        new_config.setdefault("plugins", {})["enabled"] = new_enabled
        changed = True
        messages.append("从不限制改为显式列表，之后新增的插件不会自动启用")
    elif isinstance(view["enabled_value"], list):
        if plugin_id in view["enabled_value"]:
            new_config.setdefault("plugins", {})["enabled"] = sorted(
                name for name in view["enabled_value"] if name != plugin_id)
            changed = True
        else:
            messages.append("没有变化")
    if plugin_id == decisions.PLUGIN_ID:
        messages.append("决策插件会因此变为 off")
    return _finish_mutation(repo, config, new_config, args.dry_run, messages, [], [])


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
    if not isinstance(plugin_id, str) or not plugins.PLUGIN_ID.match(plugin_id):
        raise pd.DispatchError("插件 ID 不合法：%r" % (plugin_id,), EXIT_USAGE)
    return plugin_id


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
