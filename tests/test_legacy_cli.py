#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧调度器入口的特征化回归（01-A07、01 文档附录 C.4；P4 旧行为锁定）。

目的：锁定提交 a4fa199b0e5bdc658215765ee7558b9fe6723940 中 scripts/pi_dispatch.py（TOOL_VERSION 2.2.2）的
**现有**行为，给后续重写提供可比较的旧观测。这里只断言现状，不修缺陷；现状可疑的地方在测试 docstring 中标“可疑”，
并引用 docs/code-kit-v2/01-baseline/legacy-inventory.md 的条目号或小节，或 compatibility-matrix.md 的 D 编号。

覆盖范围（对应 legacy-inventory.md 第 10 节与 11.5 节列出的回归缺口）：
- wait 与退出码语义：--timeout<1、state.json 缺失/为 null/非对象、PREPARING/COLLECTING 到时、PREPARED 宽限、
  已结束时的“摘要：”行、live 片段（经 wait 与 status）、找不到 git 时的 3；
- main：无子命令、argparse 用法错误、--version、DispatchError/KeyboardInterrupt/其他异常的映射、--repo 的错误；
- 各子命令拒绝路径的精确退出码（prepare、run、collect、verdict、branch、mark、cleanup、baseline、doctor），
  含 mark/cleanup 按状态的拒绝与 cleanup 对候选补丁被改动的保护；
- run 以 INFRA_FAILURE、TIMEOUT、CANCELLED 结束时退出 1；timed_out 与 interrupted 同时为真时判为 TIMEOUT；
  wait 轮询期间收到 CTRL_BREAK 不经 main 处理（Windows）；
- 旧合同缺省值（normalize_contract）；Markdown 改、JSON 不改方向的一致性检查与已记录边界；
- 范围判定：删除越界、大小写不同的受保护路径、新增或改为符号链接、local_commit 下 head_moved 降为警告。

运行：`PYTHONDONTWRITEBYTECODE=1 python tests/test_legacy_cli.py`（按 01-L04 单独运行，不用 unittest discover）。
每个用例在自己的临时区域里建临时仓库，子进程在受控环境中运行（见 tests/legacy_harness.py，01-L05）：
不调用真实 pi/claude/codex，不联网，不读取凭据。被测源码取 tests/legacy_harness.kit_dir()（默认本仓库；
设置 CODEKIT_LEGACY_KIT_DIR 时改用该目录，供变异反测）。

平台：本机为 Windows Server 2025 + Python 3.12.10 + Git for Windows。只在某一平台可行的用例用 skipUnless 标明原因；
Linux、macOS 上的结果本次没有取得（01-D10）。
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import io
import json
import os
import re
import shutil
import sys
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.dont_write_bytecode = True
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
from legacy_harness import (  # noqa: E402
    IS_WINDOWS, KIT_ENV_VAR, OK_FILES, PLAN_KEY, PY, LegacyCase, build_md, contract, default_checks, legacy_facts,
    load_legacy_module, ok_events, send_interrupt,
)

#: 各用例中 attempt-001 的仓库相对显示路径（display_path 的输出，正斜杠）。
RUN_REL = ".agent/runs/normalize-query/attempt-001"
#: 进程内校验用的基线 ID（validate_contract 只查格式，不查仓库）。
FAKE_BASE = "a" * 40
#: build_md 把检查的 argv[0] 写成解释器的文件名（stem）：Windows 上是 python，macOS 自带的是 python3。
#: 用例按它拼 Markdown 中的检查行，不能写死 python（2026-10-04 macOS 实测：写死时替换落空）。
V01_LINE = "- V01: %s run_tests.py" % Path(PY).stem
#: Windows 上被 CTRL_BREAK 的默认处理结束的进程退出码（STATUS_CONTROL_C_EXIT）。
STATUS_CONTROL_C_EXIT = 0xC000013A
FAILURE_CLASS_LIST = ("PLAN_ERROR, EXECUTION_ERROR, INFRA_FAILURE, SCOPE_VIOLATION, REQUIREMENT_BLOCKED, TIMEOUT, "
                      "BUDGET_EXCEEDED, CANCELLED")


def lines(text: str) -> List[str]:
    """按行拆分（Windows 上子进程输出是 CRLF）。"""
    return text.splitlines()


# ---------------------------------------------------------------------------
# 被测来源
# ---------------------------------------------------------------------------

class LegacySourceTest(unittest.TestCase):

    @unittest.skipIf(os.environ.get(KIT_ENV_VAR), "设置了 %s：在临时副本上做变异反测，摘要必然不同" % KIT_ENV_VAR)
    def test_source_under_test_is_a4fa199(self) -> None:
        """新增：被测字节就是 a4fa199 的 scripts/pi_dispatch.py（legacy_harness.LOCKED_PI_DISPATCH_SHA256）。

        01-A07：特征化结果只对这份字节成立；工作区里的调度器被改动时本用例失败，其余结论不再代表 a4fa199。
        """
        facts = legacy_facts()
        self.assertTrue(facts["pi_dispatch_matches_a4fa199"], facts["pi_dispatch_sha256"])
        self.assertEqual(load_legacy_module().TOOL_VERSION, "2.2.2")


# ---------------------------------------------------------------------------
# 旧合同缺省值（进程内调用 normalize_contract / validate_contract）
# ---------------------------------------------------------------------------

class LegacyContractDefaultsTest(unittest.TestCase):
    """C.4“旧合同默认值”：legacy-inventory.md 3.2 节；旧测试没有直接断言（第 10 节 LB-TEST-COV-01 缺口）。"""

    pd: Any = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.pd = load_legacy_module()

    def test_LB_CONTRACT_003_normalize_empty_contract_defaults(self) -> None:
        """LB-CONTRACT-003（scripts/pi_dispatch.py:1189-1214）；01-A07，C.4“旧合同默认值”。

        normalize_contract({}) 只补 executor/scope/authorization/budget 四节与 setup/checks/definition_of_done，
        不补 schema_version、task_id、plan_version、base_sha、risk_level，也不补 executor.provider/model。
        """
        self.assertEqual(self.pd.normalize_contract({}), {
            "executor": {"thinking": "high", "tools": ["read", "grep", "find", "ls", "edit", "write", "bash"],
                         "context_files": "project"},
            "scope": {"allowed_modified_files": [], "allowed_new_files": [], "allowed_deleted_files": [],
                      "forbidden_paths": [], "dependency_changes": "forbidden"},
            "authorization": {"executor": ["local_edit", "local_test"], "integration": []},
            "budget": {"max_attempts_total": 2, "max_wall_seconds_per_attempt": 1200,
                       "max_wall_seconds_total": 2400, "cost_budget": None},
            "setup": [], "checks": [], "definition_of_done": [],
        })

    def test_LB_CONTRACT_003_command_item_defaults_setup_has_no_required(self) -> None:
        """LB-CONTRACT-003、LB-CONTRACT-004（:1207-1213、读取时缺省 :1171、1174、1183）；01-A07，C.4“旧合同默认值”。

        checks 中的对象项补 cwd/required/expected_exit_code；setup 项不补 required；expect_on_base、output 模式、env
        只在读取时按缺省处理，不写回；数组中不是对象的项原样保留。
        """
        normalized = self.pd.normalize_contract({"checks": [{"id": "V01"}, "x"], "setup": [{"id": "S01"}]})
        self.assertEqual(normalized["checks"], [{"id": "V01", "cwd": ".", "required": True, "expected_exit_code": 0},
                                                "x"])
        self.assertEqual(normalized["setup"], [{"id": "S01", "cwd": ".", "expected_exit_code": 0}])

    def test_LB_CONTRACT_004_explicit_null_and_wrong_types_not_filled(self) -> None:
        """LB-CONTRACT-004（:1200-1211，setdefault 只补缺失键）；01-A07，C.4“旧合同默认值”。

        显式 null 保留（thinking=None 不会变成 high）；节存在但类型不对时整节不补（scope=["x"] 原样）；
        cost_budget 为对象时不检查、不补其中的键。
        """
        normalized = self.pd.normalize_contract({"executor": {"thinking": None}, "scope": ["x"], "checks": {},
                                                 "budget": {"cost_budget": {"amount": 1}}})
        self.assertIsNone(normalized["executor"]["thinking"])
        self.assertEqual(normalized["executor"]["tools"], ["read", "grep", "find", "ls", "edit", "write", "bash"])
        self.assertEqual(normalized["scope"], ["x"])
        self.assertEqual(normalized["checks"], {})
        self.assertEqual(normalized["budget"], {"cost_budget": {"amount": 1}, "max_attempts_total": 2,
                                                "max_wall_seconds_per_attempt": 1200, "max_wall_seconds_total": 2400})

    def test_LB_CONTRACT_004_normalize_deep_copies_input(self) -> None:
        """LB-CONTRACT-004（:1191 先 json.loads(json.dumps(raw)) 深拷贝）；01-A07，C.4“旧合同默认值”。"""
        raw: Dict[str, Any] = {"executor": {}, "checks": [{"id": "V01"}]}
        self.pd.normalize_contract(raw)
        self.assertEqual(raw, {"executor": {}, "checks": [{"id": "V01"}]})

    def test_LB_CONTRACT_005_unserializable_raw_wrapped_as_structure_error(self) -> None:
        """LB-CONTRACT-005（:1191 抛 TypeError，由 :1432-1437 包装）；01-A07，C.4“旧合同默认值”。

        只在进程内直接调用时可达（经 CLI 时 raw 来自 json.loads）。包装后丢弃已收集的警告。
        """
        self.assertEqual(self.pd.validate_contract("# TASK: normalize-query\n", {"x": {1}}, PLAN_KEY),
                         (None, ["合同结构无效：TypeError: Object of type set is not JSON serializable"], []))

    def test_LB_CONTRACT_003_provider_model_have_no_default_and_validate_passes(self) -> None:
        """LB-CONTRACT-003（:1484-1487，provider/model 没有缺省也不要求）；01-A07，C.4“旧合同默认值”。

        可疑：合同可以不写执行模型而通过校验，run 时再由 PI_EXEC_* 补值（legacy-inventory.md 11.6 第 4 条、
        LB-CONTRACT-033）。
        """
        raw = contract(FAKE_BASE)
        raw["executor"] = {k: v for k, v in raw["executor"].items() if k not in ("provider", "model")}
        md = build_md(raw)
        self.assertIn("- executor: None/None · thinking high", md)
        result, errors, warnings = self.pd.validate_contract(md, raw, PLAN_KEY)
        self.assertEqual((errors, warnings), ([], []))
        self.assertNotIn("provider", result["executor"])
        self.assertNotIn("model", result["executor"])


# ---------------------------------------------------------------------------
# Markdown 改、JSON 不改；Identity 全角冒号；risk_level 大小写
# ---------------------------------------------------------------------------

class LegacyMarkdownJsonConsistencyTest(unittest.TestCase):
    """C.4“Markdown/JSON 一致性”：legacy-inventory.md 3.4 节。旧测试只改 JSON（第 10 节 LB-TEST-COV-02 缺口）。"""

    pd: Any = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.pd = load_legacy_module()

    def setUp(self) -> None:
        self.raw = contract(FAKE_BASE)
        self.md = build_md(self.raw)
        result, errors, warnings = self.pd.validate_contract(self.md, self.raw, PLAN_KEY)
        self.assertEqual((errors, warnings), ([], []), "基准合同应当一致")

    def md_errors(self, old: str, new: str, raw: Optional[Dict[str, Any]] = None) -> List[str]:
        """把 Markdown 中恰好一处 old 换成 new（JSON 不变），返回 validate_contract 的错误列表。"""
        self.assertEqual(self.md.count(old), 1, old)
        result, errors, _warnings = self.pd.validate_contract(self.md.replace(old, new), raw or self.raw, PLAN_KEY)
        self.assertEqual(result is None, bool(errors))
        return errors

    def test_LB_CONTRACT_017_md_budget_changed_json_unchanged(self) -> None:
        """LB-CONTRACT-017（:1618-1622）；01-A07，C.4“Markdown/JSON 一致性”。"""
        self.assertEqual(self.md_errors("- max_attempts_total: 3", "- max_attempts_total: 5"),
                         ["Markdown Budget 的 max_attempts_total（5）与 JSON（3）不一致"])

    def test_LB_CONTRACT_016_md_identity_risk_level_changed(self) -> None:
        """LB-CONTRACT-016（:1594-1598）；01-A07，C.4“Markdown/JSON 一致性”。"""
        self.assertEqual(self.md_errors("- risk_level: low", "- risk_level: medium"),
                         ["Markdown Identity 的 risk_level（'medium'）与 JSON（'low'）不一致"])

    def test_LB_CONTRACT_016_md_thinking_changed(self) -> None:
        """LB-CONTRACT-016（:1610-1611，要求 thinking\\s+<级别>\\b）；01-A07，C.4“Markdown/JSON 一致性”。"""
        self.assertEqual(self.md_errors("· thinking high", "· thinking xhigh"),
                         ["Markdown Identity 的 executor 应写明 thinking high"])

    def test_LB_CONTRACT_016_md_integration_actions_changed(self) -> None:
        """LB-CONTRACT-016（:1599-1605、1409-1413）；01-A07，C.4“Markdown/JSON 一致性”。"""
        self.assertEqual(self.md_errors("- integration_actions: local_branch",
                                        "- integration_actions: local_branch, push"),
                         ["Markdown Identity 的 integration_actions（local_branch, push）与 JSON（local_branch）不一致"])

    def test_LB_CONTRACT_017_md_dependency_changes_changed(self) -> None:
        """LB-CONTRACT-017（:1615-1617）；01-A07，C.4“Markdown/JSON 一致性”。"""
        self.assertEqual(self.md_errors("- dependency_changes: forbidden", "- dependency_changes: allowed"),
                         ["Markdown Scope 的 dependency_changes 与 JSON（forbidden）不一致"])

    def test_LB_CONTRACT_017_md_validation_argv_changed(self) -> None:
        """LB-CONTRACT-017（:1623-1630、1416-1429）；01-A07，C.4“Markdown/JSON 一致性”。"""
        errors = self.md_errors(V01_LINE, V01_LINE.replace("run_tests.py", "run_all.py"))
        self.assertEqual(errors, ["Markdown 中 V01 的命令与 JSON argv 不一致：%s run_tests.py" % PY])

    def test_LB_CONTRACT_017_md_validation_line_removed(self) -> None:
        """LB-CONTRACT-017（:1623-1628）；01-A07，C.4“Markdown/JSON 一致性”。"""
        self.assertEqual(self.md_errors(V01_LINE, "- 运行测试"),
                         ["Markdown Validation commands 未列出 V01"])

    def test_LB_CONTRACT_017_md_forbidden_path_removed(self) -> None:
        """LB-CONTRACT-017（:1612-1614，JSON 的路径要以子串出现在 Markdown 全文）；01-A07，C.4“Markdown/JSON 一致性”。"""
        self.assertEqual(self.md_errors("- forbidden_paths: package.json", "- forbidden_paths: 无"),
                         ["Markdown 未列出 JSON 中的路径：package.json"])

    def test_LB_CONTRACT_018_md_only_additions_and_dod_text_not_compared(self) -> None:
        """LB-CONTRACT-017、LB-CONTRACT-018（:1582-1633 的比较范围之外）；01-A07，C.4“Markdown/JSON 一致性”。

        可疑：只检查 JSON→Markdown 一个方向；Markdown 多列的路径、多出的检查行、改写的 DoD 文字都不报错，
        调度器只按 JSON 执行（legacy-inventory.md 11.2 第 1 条 (4)、第 2 条）。
        """
        self.assertEqual(self.md.count(V01_LINE), 1, V01_LINE)  # 替换落空时用例会空转通过
        md = (self.md.replace("- allowed_new_files: tests/test_normalize.py",
                              "- allowed_new_files: tests/test_normalize.py, src/extra.py")
              .replace(V01_LINE, V01_LINE + "\n- V02: python other.py")
              .replace("行为正确", "完全不同的验收文字"))
        self.assertNotEqual(md, self.md)
        self.assertEqual(self.pd.validate_contract(md, self.raw, PLAN_KEY)[1:], ([], []))

    def test_LB_CONTRACT_016_fullwidth_colon_identity_value_reads_as_none(self) -> None:
        """LB-CONTRACT-016（:1134-1141 只认半角冒号）；01-A07，C.4“Markdown/JSON 一致性”。

        可疑：全角冒号写的 Identity 行解析不到，报“（None）与 JSON 不一致”而不是“缺少”
        （legacy-inventory.md 3.4 第 5 行、11.2 第 1 条 (8)）。
        """
        self.assertEqual(self.md_errors("- risk_level: low", "- risk_level：low"),
                         ["Markdown Identity 的 risk_level（None）与 JSON（'low'）不一致"])

    def test_LB_CONTRACT_016_fullwidth_colon_action_list_reads_as_missing(self) -> None:
        """LB-CONTRACT-016（:1599-1603）；01-A07，C.4“Markdown/JSON 一致性”。可疑：同 11.2 第 1 条 (8)。"""
        self.assertEqual(self.md_errors("- authorized_actions: local_edit, local_test",
                                        "- authorized_actions：local_edit, local_test"),
                         ["Markdown Identity 缺少 authorized_actions"])

    def test_LB_CONTRACT_017_fullwidth_colon_dependency_changes_not_recognised(self) -> None:
        """LB-CONTRACT-017（:1615 的正则只认半角冒号）；01-A07，C.4“Markdown/JSON 一致性”。可疑：11.2 第 1 条 (8)。"""
        self.assertEqual(self.md_errors("- dependency_changes: forbidden", "- dependency_changes：forbidden"),
                         ["Markdown Scope 的 dependency_changes 与 JSON（forbidden）不一致"])

    def test_LB_CONTRACT_016_identity_value_note_is_stripped(self) -> None:
        """LB-CONTRACT-016（:1126-1131 _md_value 去掉反引号与结尾的括号说明）；01-A07，C.4“Markdown/JSON 一致性”。"""
        self.assertEqual(self.md_errors("- risk_level: low", "- risk_level: `low`（改动集中）"), [])

    def test_LB_CONTRACT_035_risk_level_upper_in_json_lower_in_md(self) -> None:
        """LB-CONTRACT-035、LB-CONTRACT-007（:1468-1469、1594-1598，级联错误）；01-A07，C.4“Markdown/JSON 一致性”。"""
        raw = contract(FAKE_BASE, risk_level="Low")
        result, errors, _ = self.pd.validate_contract(self.md, raw, PLAN_KEY)
        self.assertIsNone(result)
        self.assertEqual(errors, ["risk_level 必须是 low/medium/high 之一",
                                  "Markdown Identity 的 risk_level（'low'）与 JSON（'Low'）不一致"])

    def test_LB_CONTRACT_035_risk_level_upper_in_both(self) -> None:
        """LB-CONTRACT-035、LB-CONTRACT-007（大小写敏感的取值检查）；01-A07，C.4“Markdown/JSON 一致性”。"""
        raw = contract(FAKE_BASE, risk_level="Low")
        self.assertEqual(self.pd.validate_contract(build_md(raw), raw, PLAN_KEY)[1],
                         ["risk_level 必须是 low/medium/high 之一"])

    def test_LB_CONTRACT_016_risk_level_upper_in_md_only(self) -> None:
        """LB-CONTRACT-016（Identity 按字符串完全相等比较）；01-A07，C.4“Markdown/JSON 一致性”。"""
        self.assertEqual(self.md_errors("- risk_level: low", "- risk_level: Low"),
                         ["Markdown Identity 的 risk_level（'Low'）与 JSON（'low'）不一致"])

    def test_LB_CONTRACT_015_title_capture_stops_at_first_foreign_char(self) -> None:
        """LB-CONTRACT-015（:1591-1593）；01-A07，C.4“Markdown/JSON 一致性”。

        可疑：标题捕获在第一个不属于 [a-z0-9-] 的字符处停止，`# TASK: normalize-queryX` 也能通过
        （legacy-inventory.md 3.4 第 4 行、11.2 第 1 条 (6)）。
        """
        self.assertEqual(self.md_errors("# TASK: normalize-query", "# TASK: normalize-queryX"), [])
        self.assertEqual(self.md_errors("# TASK: normalize-query", "# TASK: normalize-query-x"),
                         ["Markdown 标题应为 '# TASK: normalize-query'"])


# ---------------------------------------------------------------------------
# 范围判定 evaluate_scope（进程内）
# ---------------------------------------------------------------------------

def _change(path: str, status: str, old_mode: str = "100644", new_mode: str = "100644") -> Dict[str, str]:
    return {"path": path, "status": status, "old_mode": old_mode, "new_mode": new_mode}


class LegacyScopeInProcessTest(unittest.TestCase):
    """C.4“范围检查”：legacy-inventory.md 5.4 节；删除越界、大小写、symlink、local_commit 是第 10 节列出的缺口。"""

    pd: Any = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.pd = load_legacy_module()

    def scope(self, changes: List[Dict[str, str]], head_after: str = FAKE_BASE, **over: Any) -> Dict[str, Any]:
        return self.pd.evaluate_scope(changes, self.pd.normalize_contract(contract(FAKE_BASE, **over)), head_after,
                                      FAKE_BASE)

    def test_LB_GATES_018_deleted_file_outside_allowed_deleted_is_out_of_scope(self) -> None:
        """LB-GATES-018（:2465-2467，D 只看 allowed_deleted_files）；01-A07，C.4“范围检查”。

        删除一个“允许修改”的文件也算越界。
        """
        result = self.scope([_change("README.md", "D", new_mode="000000"),
                             _change("src/normalize.py", "D", new_mode="000000")])
        self.assertEqual(result["violations"], [
            {"path": "README.md", "kind": "out_of_scope", "detail": "状态 D 不在允许集合"},
            {"path": "src/normalize.py", "kind": "out_of_scope", "detail": "状态 D 不在允许集合"}])
        self.assertEqual((result["warnings"], result["ok"], result["counts"]),
                         ([], False, {"A": 0, "M": 0, "D": 2, "T": 0}))
        allowed = contract(FAKE_BASE)["scope"]
        allowed["allowed_deleted_files"] = ["README.md"]
        self.assertTrue(self.scope([_change("README.md", "D", new_mode="000000")], scope=allowed)["ok"])

    def test_LB_GATES_017_protected_paths_ignore_case_scope_lists_do_not(self) -> None:
        """LB-GATES-017、LB-GATES-018（:1063-1093、2459-2467、2478-2484）；01-A07，C.4“范围检查”。

        受保护路径不区分大小写；scope 各列表与依赖清单区分大小写（`Package.json` 只算越界，不算依赖变更）。
        """
        protected = ["Agents.md", "docs/CLAUDE.MD", ".Agent/plans/x.md", "Scripts/Pi_Dispatch.py"]
        result = self.scope([_change(p, "M") for p in protected] + [_change("Package.json", "M"),
                                                                     _change("src/Normalize.py", "M")])
        self.assertEqual(result["violations"], [
            {"path": p, "kind": "protected_path", "detail": "合同、证据、代理规则或调度器文件"} for p in protected] + [
            {"path": "Package.json", "kind": "out_of_scope", "detail": "状态 M 不在允许集合"},
            {"path": "src/Normalize.py", "kind": "out_of_scope", "detail": "状态 M 不在允许集合"}])
        self.assertEqual(result["warnings"], [])

    def test_LB_GATES_018_new_symlink_is_violation_symlink_to_file_is_silent(self) -> None:
        """LB-GATES-018（:2465-2477）；01-A07，C.4“范围检查”。

        新增 120000（A，000000→120000）与普通文件改为符号链接（T，100644→120000）都记 symlink 违规：:2468 对任何
        new_mode==120000 生效，与“在允许集合内”叠加；T 按 allowed_modified_files 判定（:2465，在集合内，不报
        out_of_scope），涉及 120000 的模式变化不报 mode_changed（:2474-2477）。可疑：符号链接改回普通文件（T，120000→100644）
        既不算违规也不算警告（legacy-inventory.md 5.4、11.2 第 9 条）。
        """
        scope = contract(FAKE_BASE)["scope"]
        scope["allowed_new_files"] = ["tests/test_normalize.py", "src/link.py"]
        scope["allowed_modified_files"] = ["src/normalize.py", "src/to_link.py"]
        result = self.scope([_change("src/link.py", "A", "000000", "120000"),
                             _change("src/normalize.py", "T", "120000", "100644"),
                             _change("src/to_link.py", "T", "100644", "120000")], scope=scope)
        self.assertEqual(result["violations"], [
            {"path": "src/link.py", "kind": "symlink", "detail": "新增或改为符号链接"},
            {"path": "src/to_link.py", "kind": "symlink", "detail": "新增或改为符号链接"}])
        self.assertEqual(result["warnings"], [])
        self.assertEqual([f["scope"] for f in result["files"]], ["violation", "in_scope", "violation"])
        self.assertEqual(result["counts"], {"A": 1, "M": 0, "D": 0, "T": 2})

    def test_LB_GATES_019_head_moved_is_warning_only_with_local_commit(self) -> None:
        """LB-GATES-019（:2488-2491）；01-A07，C.4“范围检查”。"""
        moved = "b" * 40
        item = {"path": "HEAD", "kind": "head_moved", "detail": "执行器改变了 HEAD（bbbbbbbbbbbb）"}
        plain = self.scope([_change("src/normalize.py", "M")], head_after=moved)
        self.assertEqual((plain["violations"], plain["warnings"], plain["ok"]), ([item], [], False))
        with_commit = self.scope([_change("src/normalize.py", "M")], head_after=moved,
                                 authorization={"executor": ["local_edit", "local_test", "local_commit"],
                                                "integration": ["local_branch"]})
        self.assertEqual((with_commit["violations"], with_commit["warnings"], with_commit["ok"]), ([], [item], True))


# ---------------------------------------------------------------------------
# main 的返回值映射（进程内）
# ---------------------------------------------------------------------------

class LegacyMainInProcessTest(unittest.TestCase):
    """main（scripts/pi_dispatch.py:4953-4971）的异常映射。子进程里无法可靠地在 run_supervised 之外触发
    KeyboardInterrupt（Windows 不能只向一个进程组发送 CTRL_C），所以在进程内替换子命令函数来触发。"""

    pd: Any = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.pd = load_legacy_module()

    def call_main(self, exc: BaseException) -> tuple:
        original = self.pd.cmd_wait

        def raising(_args: Any) -> int:
            raise exc

        err = io.StringIO()
        self.pd.cmd_wait = raising
        try:
            with contextlib.redirect_stderr(err):
                code = self.pd.main(["wait", "normalize-query/attempt-001"])
        finally:
            self.pd.cmd_wait = original
        return code, err.getvalue()

    def test_LB_EXIT_002_main_maps_keyboard_interrupt_to_130(self) -> None:
        """LB-EXIT-002（:4969-4971）；01-A07，C.4“wait/退出码语义”（main 的 130）。"""
        self.assertEqual(self.call_main(KeyboardInterrupt()), (130, "已取消。\n"))

    def test_LB_EXIT_002_main_maps_dispatch_error_to_its_code(self) -> None:
        """LB-EXIT-002、LB-EXIT-001（:304-309、4966-4968）；01-A07，C.4“wait/退出码语义”。"""
        self.assertEqual(self.call_main(self.pd.DispatchError("boom")), (3, "ERROR: boom\n"))
        self.assertEqual(self.call_main(self.pd.DispatchError("bad", self.pd.EXIT_USAGE)), (2, "ERROR: bad\n"))

    def test_LB_EXIT_002_main_does_not_catch_other_exceptions(self) -> None:
        """LB-EXIT-002（:4964-4971 只捕获 DispatchError 与 KeyboardInterrupt）；01-A07，C.4“wait/退出码语义”。

        其他异常从 main 传出，经 sys.exit(main()) 以 Traceback 退出 1（子进程层见 LegacyMainEntryTest）。
        """
        with self.assertRaises(RuntimeError):
            self.call_main(RuntimeError("x"))


# ---------------------------------------------------------------------------
# 子进程用例的公共辅助
# ---------------------------------------------------------------------------

class _CliCase(LegacyCase):

    def scripts_dir(self, name: str = "plain") -> Path:
        """只含 scripts/pi_dispatch.py、不是 Git 仓库的目录（tool() 按 cwd 相对路径运行脚本）。"""
        target = self.work / name
        (target / "scripts").mkdir(parents=True)
        shutil.copyfile(str(self.kit / "scripts" / "pi_dispatch.py"), str(target / "scripts" / "pi_dispatch.py"))
        return target

    def mini_repo(self, name: str = "mini") -> Path:
        """只做 git init 的仓库（wait、mark、status 只读 attempt 目录，不需要合同与 worktree）。"""
        repo = self.scripts_dir(name)
        self.sh(["git", "init", "-q"], repo)
        return repo

    def fake_attempt(self, repo: Path, state: Any = None, n: int = 1, meta: bool = True,
                     files: Optional[Dict[str, bytes]] = None) -> Path:
        """手工建立 attempt 目录：meta.json 为 {}；state 为 None 时不写 state.json，bytes 原样写，其他值写 JSON。"""
        run_dir = repo / (".agent/runs/normalize-query/attempt-%03d" % n)
        run_dir.mkdir(parents=True)
        if meta:
            (run_dir / "meta.json").write_bytes(b"{}\n")
        if state is not None:
            data = state if isinstance(state, bytes) else json.dumps(state).encode("utf-8")
            (run_dir / "state.json").write_bytes(data)
        for rel, content in (files or {}).items():
            (run_dir / rel).write_bytes(content)
        return run_dir

    def prepared(self, name: str = "repo", **over: Any) -> tuple:
        """make_repo + prepare（断言 PREPARED），返回 (repo, base, run_dir)。"""
        repo, base = self.make_repo(name, **over)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual((code, self.state(repo)), (0, "PREPARED"), out)
        return repo, base, self.rd(repo)

    def set_md(self, repo: Path, old: str, new: str) -> None:
        path = repo / ".agent/plans/normalize-query.v1.md"
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count(old), 1, old)
        path.write_text(text.replace(old, new), encoding="utf-8")

    def assert_refused(self, result: tuple, code: int, error: str, stdout_has: Optional[List[str]] = None) -> None:
        """result 为 tool_split 的 (code, stdout, stderr)：退出码精确相等，stderr 恰为一行 `ERROR: <error>`。"""
        got_code, out, err = result
        self.assertEqual(got_code, code, "stdout:\n%s\nstderr:\n%s" % (out, err))
        self.assertEqual(lines(err), ["ERROR: " + error], err)
        for fragment in stdout_has or []:
            self.assertIn(fragment, lines(out), out)


# ---------------------------------------------------------------------------
# wait 与 live 进度
# ---------------------------------------------------------------------------

class LegacyWaitTest(_CliCase):
    """C.4“wait/退出码语义”：legacy-inventory.md 7.4、7.5 节；11.5 第 9 条列出的 wait 缺口。"""

    def wait(self, repo: Path, *extra: str, ref: str = "normalize-query/attempt-001") -> tuple:
        return self.tool_split(repo, "wait", ref, *extra)

    def test_LB_EXIT_023_wait_timeout_below_one_is_usage_2(self) -> None:
        """LB-EXIT-023（:3926-3927）；01-A07，C.4“wait/退出码语义”。"""
        repo = self.mini_repo()
        self.fake_attempt(repo, {"state": "RUNNING"})
        for value in ("0", "-5"):
            with self.subTest(timeout=value):
                code, out, err = self.wait(repo, "--timeout", value)
                self.assertEqual((code, out), (2, ""))
                self.assertEqual(lines(err), ["ERROR: --timeout 必须是正整数（秒）"])

    def test_LB_EXIT_023_wait_unknown_attempt_reported_before_timeout_check(self) -> None:
        """LB-EXIT-023、LB-EXIT-005（:3924-3927，resolve_run_dir 在 --timeout 检查之前；:2650）；01-A07，
        C.4“wait/退出码语义”。"""
        repo = self.mini_repo()
        code, out, err = self.wait(repo, "--timeout", "0", ref="normalize-query/attempt-009")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(lines(err), ["ERROR: 找不到 attempt：normalize-query/attempt-009"])

    def test_LB_EXIT_024_wait_missing_state_json_is_unknown_exit_1(self) -> None:
        """LB-EXIT-024、LB-LIFE-029（:2554-2555、3943-3945）；01-A07，C.4“wait/退出码语义”（state.json 缺失）。"""
        repo = self.mini_repo()
        self.fake_attempt(repo, None)
        code, out, err = self.wait(repo, "--timeout", "5")
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(lines(out), ["无法确定 attempt 的状态（UNKNOWN）：state.json 缺失、损坏或状态未知。检查 %s"
                                      % RUN_REL])

    def test_LB_EXIT_024_wait_null_missing_key_or_unknown_state_exit_1(self) -> None:
        """LB-EXIT-024（:2555 str(...get("state", "UNKNOWN"))）；01-A07，C.4“wait/退出码语义”。

        可疑：`"state": null` 显示为 None（legacy-inventory.md 7.4“无法确定”一行）。
        """
        cases = ((b'{"state": null}', "None"), (b'{"at": "x"}', "UNKNOWN"), (b'{"state": "FOO"}', "FOO"),
                 (b"{", "UNKNOWN"))
        for index, (data, shown) in enumerate(cases, 1):
            with self.subTest(state_json=data):
                repo = self.mini_repo("mini%d" % index)
                self.fake_attempt(repo, data)
                code, out, err = self.wait(repo, "--timeout", "5")
                self.assertEqual((code, err), (1, ""))
                self.assertEqual(lines(out), ["无法确定 attempt 的状态（%s）：state.json 缺失、损坏或状态未知。检查 %s"
                                              % (shown, RUN_REL)])

    def test_LB_EXIT_030_wait_non_object_state_json_traceback_exit_1(self) -> None:
        """LB-EXIT-030（:2555 对非对象调用 .get）；01-A07，C.4“wait/退出码语义”。

        可疑：未捕获的 AttributeError 以 Traceback 退出 1，与 EXIT_FAIL 同码（legacy-inventory.md 11.2 第 3 条）。
        """
        repo = self.mini_repo()
        self.fake_attempt(repo, b"[]")
        code, out, err = self.wait(repo, "--timeout", "5")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("Traceback (most recent call last):", err)
        self.assertIn("AttributeError: 'list' object has no attribute 'get'", err)
        self.assertNotIn("ERROR:", err)

    def test_LB_EXIT_024_wait_preparing_and_collecting_time_out_with_3_without_live(self) -> None:
        """LB-EXIT-024（:3933-3937，只有 RUNNING 附加 live）；01-A07，C.4“wait/退出码语义”（PREPARING/COLLECTING 到时）。"""
        for state in ("PREPARING", "COLLECTING"):
            with self.subTest(state=state):
                repo = self.mini_repo("mini-" + state.lower())
                self.fake_attempt(repo, {"state": state},
                                  files={"events.jsonl": b'{"type":"tool_execution_end"}\n'})
                started = time.monotonic()
                code, out, err = self.wait(repo, "--timeout", "1", "--interval", "0.2")
                self.assertGreaterEqual(time.monotonic() - started, 1.0)
                self.assertEqual((code, err), (3, ""))
                self.assertEqual(lines(out), ["仍在运行：%s · %s。再次运行 wait 继续等待。" % (RUN_REL, state)])

    def test_LB_EXIT_025_wait_running_time_out_appends_live_fragment(self) -> None:
        """LB-EXIT-025、LB-EXIT-024（:3935、4525-4548）；01-A07，C.4“wait/退出码语义”（到时输出中的 live 片段）。"""
        repo = self.mini_repo()
        events = b'{"type":"tool_execution_end","id":1}\n{"type":"message_update"}\n{"type":"tool_execution_end"}\n'
        self.fake_attempt(repo, {"state": "RUNNING"}, files={"events.jsonl": events})
        code, out, err = self.wait(repo, "--timeout", "1", "--interval", "0.2")
        self.assertEqual((code, err), (3, ""))
        self.assertEqual(lines(out), ["仍在运行：%s · RUNNING · live:2t。再次运行 wait 继续等待。" % RUN_REL])

    def test_LB_EXIT_025_live_progress_variants_via_status_json(self) -> None:
        """LB-EXIT-025、LB-EXIT-019（:4522、4531-4548、4562-4564）；01-A07，C.4“wait/退出码语义”（live 片段）。

        status 对 RUNNING 行把 events_ok 换成 live 字符串，退出 0。可疑：只数紧凑写法的字节串
        `"type":"tool_execution_end"`，带空格的 JSON（stub 的写法）计为 0（legacy-inventory.md 7.5、11.3 第 6 条）。
        """
        repo = self.mini_repo()
        started_at = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(seconds=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
        compact = b'{"type":"tool_execution_end"}\n{"type":"tool_execution_end"}\n'
        self.fake_attempt(repo, {"state": "RUNNING"}, 1, files={"events.jsonl": compact})
        self.fake_attempt(repo, {"state": "RUNNING"}, 2,
                          files={"events.jsonl": b'{"type": "tool_execution_end", "toolCallId": "c1"}\n'})
        self.fake_attempt(repo, {"state": "RUNNING"}, 3, files={
            "events.jsonl": compact, "run-started.json": json.dumps({"started_at": started_at}).encode("utf-8")})
        self.fake_attempt(repo, {"state": "RUNNING"}, 4, files={
            "events.jsonl": b'{"type":"tool_execution_end"}\n' + b'{"type":"message_update"}\n' * 6000})
        self.fake_attempt(repo, {"state": "NEEDS_REVIEW"}, 5, files={"events.jsonl": compact})
        code, out, err = self.tool_split(repo, "status", "normalize-query", "--json")
        self.assertEqual((code, err), (0, ""))
        rows = json.loads(out)
        self.assertEqual([r["state"] for r in rows], ["RUNNING"] * 4 + ["NEEDS_REVIEW"])
        self.assertEqual(rows[0]["events_ok"], "live:2t")
        self.assertEqual(rows[1]["events_ok"], "live:0t")
        self.assertRegex(rows[2]["events_ok"], r"^live:2t \d+s$")
        self.assertTrue(100 <= int(rows[2]["events_ok"].split()[1][:-1]) < 1000, rows[2])
        self.assertEqual(rows[3]["events_ok"], "live:1t 长时间没有工具调用（6000 个增量）")
        self.assertIsNone(rows[4]["events_ok"])

    def test_LB_EXIT_024_wait_terminal_prints_summary_line(self) -> None:
        """LB-EXIT-024（:3946-3950）；01-A07，C.4“wait/退出码语义”（已结束时的“摘要：”行）。"""
        repo = self.mini_repo()
        self.fake_attempt(repo, {"state": "NEEDS_REVIEW"}, files={"summary.md": b"# summary\n"})
        code, out, err = self.wait(repo, "--timeout", "5")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(lines(out), ["已结束：%s · NEEDS_REVIEW" % RUN_REL, "摘要：%s/summary.md" % RUN_REL])

    def test_LB_EXIT_026_wait_exit_0_for_failed_terminal_state_without_summary(self) -> None:
        """LB-EXIT-026（:3946-3950，TERMINAL_STATES :81-82）；01-A07，C.4“wait/退出码语义”。

        可疑：wait 退出 0 只表示已结束，INFRA_FAILURE、REVISE 等也是 0（legacy-inventory.md 7.6、7.7）。
        """
        for state in ("INFRA_FAILURE", "REVISE", "PREPARE_FAILED"):
            with self.subTest(state=state):
                repo = self.mini_repo("mini-" + state.lower())
                self.fake_attempt(repo, {"state": state})
                code, out, err = self.wait(repo, "--timeout", "5")
                self.assertEqual((code, err), (0, ""))
                self.assertEqual(lines(out), ["已结束：%s · %s" % (RUN_REL, state)])

    def test_LB_EXIT_024_wait_prepared_returns_3_after_min_60_timeout(self) -> None:
        """LB-EXIT-024、LB-LIFE-029（:3933、3940-3942）；01-A07，C.4“wait/退出码语义”。

        timeout < 60 时 PREPARED 等满 timeout 后退出 3，用“未开始”的文案，不用“仍在运行”。
        """
        repo = self.mini_repo()
        self.fake_attempt(repo, {"state": "PREPARED"})
        started = time.monotonic()
        code, out, err = self.wait(repo, "--timeout", "2", "--interval", "0.2")
        self.assertGreaterEqual(time.monotonic() - started, 2.0)
        self.assertEqual((code, err), (3, ""))
        self.assertEqual(lines(out), ["attempt 仍是 PREPARED：run 没有开始（或启动前就失败了）。检查后台命令的输出：%s"
                                      % RUN_REL])

    def test_LB_EXIT_024_wait_prepared_grace_keeps_polling(self) -> None:
        """LB-EXIT-024（:3933 的 min(60, timeout) 宽限）；01-A07，C.4“wait/退出码语义”。

        timeout=120 时，PREPARED 的 attempt 不会马上返回 3；期间状态变为 NEEDS_REVIEW 后返回 0。
        60 秒上限本身没有测（要等满 60 秒）。
        """
        repo = self.mini_repo()
        run_dir = self.fake_attempt(repo, {"state": "PREPARED"})
        proc = self.popen_tool(repo, "wait", "normalize-query/attempt-001", "--timeout", "120", "--interval", "0.2")
        time.sleep(3.0)  # 有意的延迟：证明 PREPARED 时 wait 仍在等待
        self.assertIsNone(proc.poll(), "PREPARED 在宽限内不应返回")
        (run_dir / "state.json").write_bytes(b'{"state": "NEEDS_REVIEW"}')
        out, _ = proc.communicate(timeout=60)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(lines(out.decode("utf-8", "replace")), ["已结束：%s · NEEDS_REVIEW" % RUN_REL])

    def test_LB_EXIT_026_wait_git_missing_is_3(self) -> None:
        """LB-EXIT-026（:3924→958→756-757，DispatchError 缺省码 3）；01-A07，C.4“wait/退出码语义”。

        可疑：与“仍在运行”的 3 同码，只看退出码重复调用 wait 会一直循环（legacy-inventory.md 11.2 第 15 条）。
        """
        repo = self.mini_repo()
        self.fake_attempt(repo, {"state": "NEEDS_REVIEW"})
        # PATH 只留一个没有 git 的目录。PY 所在目录在 macOS 上不行：/usr/bin/python3 实际运行 Xcode 的
        # Developer/usr/bin/python3，同一目录就有 git（2026-10-04 实测）。Windows 保持原有写法。
        path = os.path.dirname(PY)
        if not IS_WINDOWS:
            path = str(self.work / "path-without-git")
            os.mkdir(path)
        code, out, err = self.tool_split(repo, "wait", "normalize-query/attempt-001", env={"PATH": path})
        self.assertEqual((code, out), (3, ""))
        self.assertEqual(lines(err), ["ERROR: 未找到 git，请先安装 Git。"])

    def test_LB_EXIT_038_resolve_by_task_id_picks_latest_attempt_without_meta(self) -> None:
        """LB-EXIT-038、LB-LIFE-033（:2643-2649）；01-A07，C.4“wait/退出码语义”。

        可疑：按 task-id 取编号最大的 attempt，不要求 meta.json（legacy-inventory.md 7.2、11.2 第 13 条）。
        """
        repo = self.mini_repo()
        self.fake_attempt(repo, {"state": "NEEDS_REVIEW"}, 1)
        self.fake_attempt(repo, {"state": "INFRA_FAILURE"}, 2, meta=False)
        code, out, err = self.tool_split(repo, "wait", "normalize-query", "--timeout", "5")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(lines(out), ["已结束：.agent/runs/normalize-query/attempt-002 · INFRA_FAILURE"])


# ---------------------------------------------------------------------------
# main 入口（子进程）
# ---------------------------------------------------------------------------

class LegacyMainEntryTest(_CliCase):
    """legacy-inventory.md 7.1、7.2 节；11.5 第 9 条“main 的无子命令 2、argparse 2、未捕获异常 1”。"""

    def test_LB_EXIT_002_no_subcommand_prints_help_to_stdout_exit_2(self) -> None:
        """LB-EXIT-002、LB-CONTRACT-034（:4961-4963）；01-A07，C.4“wait/退出码语义”。"""
        code, out, err = self.tool_split(self.scripts_dir())
        self.assertEqual((code, err), (2, ""))
        self.assertTrue(out.startswith("usage: pi_dispatch.py"), out[:200])
        self.assertIn("{doctor,smoke,validate,derive-json,baseline,prepare,run,collect,check,mutate,wait,", out)

    def test_LB_EXIT_003_argparse_usage_errors_exit_2_without_error_prefix(self) -> None:
        """LB-EXIT-003（:4960，parse_args 在 try 之外）；01-A07，C.4“wait/退出码语义”（argparse 的 2）。"""
        target = self.scripts_dir()
        cases = (
            (["nope"], "pi_dispatch.py: error: argument command: invalid choice: 'nope'"),
            (["wait"], "pi_dispatch.py wait: error: the following arguments are required: run_dir"),
            (["wait", "x", "--timeout", "abc"], "pi_dispatch.py wait: error: argument --timeout: invalid int value: 'abc'"),
            (["verdict", "x", "--verdict", "NOPE", "--review", "r.md"],
             "pi_dispatch.py verdict: error: argument --verdict: invalid choice: 'NOPE'"),
            (["verdict", "x", "--verdict", "PASS"],
             "pi_dispatch.py verdict: error: the following arguments are required: --review"),
            (["mark", "x", "FOO"], "pi_dispatch.py mark: error: argument state: invalid choice: 'FOO'"),
            (["smoke"], "pi_dispatch.py smoke: error: the following arguments are required: --provider, --model"),
            (["mutate", "x"], "pi_dispatch.py mutate: error: the following arguments are required: --spec"),
        )
        for argv, message in cases:
            with self.subTest(argv=argv):
                code, out, err = self.tool_split(target, *argv)
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err.startswith("usage: pi_dispatch.py"), err)
                self.assertTrue(lines(err)[-1].startswith(message), err)
                self.assertNotIn("ERROR:", err)

    def test_LB_EXIT_003_version_exit_0(self) -> None:
        """LB-EXIT-003（:4835、48）；01-A07，C.4“wait/退出码语义”。"""
        code, out, err = self.tool_split(self.scripts_dir(), "--version")
        # a4fa199 输出 "pi_dispatch 2.2.2"；工作区的后续版本（2.3.0 起）输出自己的 TOOL_VERSION，格式与退出码不变。
        live = (self.kit / "scripts" / "pi_dispatch.py").read_text(encoding="utf-8")
        version = re.search(r'^TOOL_VERSION = "([0-9]+\.[0-9]+\.[0-9]+)"$', live, re.M).group(1)
        self.assertEqual((code, lines(out), err), (0, ["pi_dispatch " + version], ""))

    def test_LB_EXIT_002_uncaught_exception_traceback_exit_1(self) -> None:
        """LB-EXIT-002、LB-CONTRACT-030、LB-EXIT-040（:1668 在 try 外读取 Markdown）；01-A07，C.4“wait/退出码语义”。

        可疑：Markdown 不是 UTF-8 时以 Traceback 退出 1，与 EXIT_FAIL 同码；同样的问题出现在 JSON 时是 2
        （compatibility-matrix.md D-22；legacy-inventory.md 11.2 第 3 条）。
        """
        repo, _base = self.make_repo()
        (repo / ".agent/plans/normalize-query.v1.md").write_bytes(b"\xff\xfe# TASK: normalize-query\n")
        code, out, err = self.tool_split(repo, "validate", PLAN_KEY)
        self.assertEqual((code, out), (1, ""))
        self.assertIn("Traceback (most recent call last):", err)
        self.assertIn("UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0", err)
        self.assertNotIn("ERROR:", err)

    def test_LB_EXIT_029_repo_not_a_repository_is_2(self) -> None:
        """LB-EXIT-029、LB-EXIT-005（:958-960）；01-A07，C.4“wait/退出码语义”。"""
        target = self.scripts_dir()
        code, out, err = self.tool_split(target, "--repo", str(target), "status")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(lines(err), ["ERROR: 当前目录不在 Git 仓库中：%s" % target])

    @unittest.skipUnless(IS_WINDOWS, "Windows 上 subprocess 对不存在的 cwd 抛 NotADirectoryError；POSIX 见下一用例")
    def test_LB_EXIT_029_repo_missing_path_windows_traceback_1(self) -> None:
        """LB-EXIT-029（:957-958、754-757 只捕获 FileNotFoundError）；01-A07、01-A15，C.4“wait/退出码语义”。

        可疑：未捕获的 NotADirectoryError 以 Traceback 退出 1（legacy-inventory.md 7.2、11.4 第 2 条）。
        """
        target = self.scripts_dir()
        code, out, err = self.tool_split(target, "--repo", str(self.work / "missing"), "status")
        self.assertEqual((code, out), (1, ""))
        self.assertIn("Traceback (most recent call last):", err)
        self.assertIn("NotADirectoryError: [WinError 267]", err)

    @unittest.skipUnless(os.name == "posix", "POSIX 分支；本机 Windows 的结果见上一用例（本次 NOT_RUN）")
    def test_LB_EXIT_029_repo_missing_path_posix_reported_as_git_missing_3(self) -> None:
        """LB-EXIT-029（:756-757 把 cwd 不存在的 FileNotFoundError 误报为找不到 git）；01-A07、01-A15。

        依据源码推断（legacy-inventory.md 7.9、11.4 第 2 条），本机没有运行。
        """
        target = self.scripts_dir()
        code, out, err = self.tool_split(target, "--repo", str(self.work / "missing"), "status")
        self.assertEqual((code, out), (3, ""))
        self.assertEqual(lines(err), ["ERROR: 未找到 git，请先安装 Git。"])


# ---------------------------------------------------------------------------
# 各子命令拒绝路径的精确退出码
# ---------------------------------------------------------------------------

class LegacyRefusalCodesTest(_CliCase):
    """legacy-inventory.md 7.3 节逐子命令退出码表；11.5 第 9 条“许多拒绝路径只断言 code != 0”。"""

    def test_LB_EXIT_008_prepare_contract_invalid_is_2_without_attempt(self) -> None:
        """LB-EXIT-008、LB-CONTRACT-018（:3172-3173）；01-A07，C.4“wait/退出码语义”“Markdown/JSON 一致性”。"""
        repo, _base = self.make_repo()
        self.set_md(repo, "- max_attempts_total: 3", "- max_attempts_total: 5")
        result = self.tool_split(repo, "prepare", PLAN_KEY)
        self.assert_refused(result, 2, "合同校验失败，未创建 attempt。",
                            ["ERROR Markdown Budget 的 max_attempts_total（5）与 JSON（3）不一致"])
        self.assertFalse((repo / ".agent/runs/normalize-query").exists())
        code, out, err = self.tool_split(repo, "validate", PLAN_KEY)
        self.assertEqual((code, lines(out), err), (2, [
            "ERROR Markdown Budget 的 max_attempts_total（5）与 JSON（3）不一致", "合同无效：1 个错误，0 个警告。"], ""))

    def test_LB_EXIT_008_prepare_runs_not_ignored_is_3(self) -> None:
        """LB-EXIT-008（:3174-3175 显式 EXIT_BLOCKED；validate 的 WARN :1688-1689）；01-A07，C.4“wait/退出码语义”。"""
        repo, _base = self.make_repo(gitignore=".env\n")
        result = self.tool_split(repo, "prepare", PLAN_KEY)
        self.assert_refused(result, 3, "请先把 .agent/runs/ 加入 .gitignore：运行证据含源码与日志，不应进入提交。",
                            ["WARN  .agent/runs/ 尚未被 .gitignore 忽略；prepare 会拒绝运行"])

    def test_LB_EXIT_035_prepare_env_conflict_2_precedes_allowlist_3(self) -> None:
        """LB-EXIT-035、LB-EXIT-008（:2668-2699：环境变量冲突 2 先于 allowlist 3；思考级别固定 3）；
        01-A07，C.4“wait/退出码语义”“实际模型与思考级别证据”。"""
        repo, _base = self.make_repo()
        self.write_config(repo, allowed_executors=[{"provider": "other", "model": "m"}])
        self.assert_refused(self.tool_split(repo, "prepare", PLAN_KEY, env={"PI_EXEC_MODEL": "other-model"}), 2,
                            "PI_EXEC_MODEL=other-model 与合同 executor.model=step-5-preview 冲突；以审阅过的合同为准，"
                            "请移除环境变量")
        self.assert_refused(self.tool_split(repo, "prepare", PLAN_KEY), 3,
                            "执行模型 step/step-5-preview 不在 .agent/dispatch.config.json 的 allowed_executors 中")
        self.write_config(repo, allowed_executors=[{"provider": "step", "model": "step-5-preview", "thinking": "low"}])
        self.assert_refused(self.tool_split(repo, "prepare", PLAN_KEY), 3, "该执行模型的思考级别固定为 low，合同为 high")
        self.assertFalse((repo / ".agent/runs/normalize-query").exists())

    def test_LB_EXIT_009_run_refusals_keep_prepared(self) -> None:
        """LB-EXIT-009、LB-LIFE-013、LB-LIFE-036（:3254-3285：各拒绝都不领取，状态保持 PREPARED）；
        01-A07，C.4“wait/退出码语义”“锁与预算竞争”。"""
        repo, _base, run_dir = self.prepared()
        ref = self.attempt_ref(1)
        self.assert_refused(self.tool_split(repo, "run", ref, env={"PI_EXEC_PROVIDER": "other"}), 2,
                            "PI_EXEC_PROVIDER=other 与合同 executor.provider=step 冲突；以审阅过的合同为准，请移除环境变量")
        self.assert_refused(self.tool_split(repo, "run", ref, env={"PI_DISPATCH_PI_CMD": "[]"}), 2,
                            "PI_DISPATCH_PI_CMD 必须是 JSON 字符串数组或单个可执行文件路径")
        code, out, err = self.tool_split(repo, "run", ref, env={"STUB_MODELS": ""})
        self.assertEqual(code, 3, out + err)
        self.assertEqual(lines(err), ["ERROR: 预检失败：attempt 保持 PREPARED，未计入尝试次数。修正环境后可再次 run。"])
        self.assertIn("PREFLIGHT 模型 step/step-5-preview 不在本机可用模型列表中（可能是拼写错误、缺少凭据或未在 "
                      "models.json 定义；Pi 对未知模型可能只警告并按自定义 ID 发送）", lines(out))
        self.assertEqual((self.state(repo), (run_dir / "claim").exists()), ("PREPARED", False))
        (run_dir / "plan.md").write_bytes((run_dir / "plan.md").read_bytes() + b"\n")
        self.assert_refused(self.tool_split(repo, "run", ref), 3,
                            "输入不一致（G0）：plan.md 的哈希与 prepare 时记录的不一致")
        self.assertEqual((self.state(repo), (run_dir / "claim").exists()), ("PREPARED", False))
        (run_dir / "claim").mkdir()
        self.assert_refused(self.tool_split(repo, "run", ref), 3,
                            "attempt 状态为 PREPARED（已领取），只能运行未领取的 PREPARED attempt；返工请重新 prepare。")
        self.pd.set_state(run_dir, "ABANDONED")
        self.assert_refused(self.tool_split(repo, "run", ref), 3,
                            "attempt 状态为 ABANDONED（已领取），只能运行未领取的 PREPARED attempt；返工请重新 prepare。")

    def test_LB_EXIT_010_collect_refusals_2_and_live_pid_3(self) -> None:
        """LB-EXIT-010、LB-LIFE-022、LB-LIFE-024（:3416-3425）；01-A07，C.4“进程恢复”“wait/退出码语义”。

        记录的 Pi 进程仍存活时拒绝恢复（旧测试没有覆盖，legacy-inventory.md 第 10 节 LB-TEST-COV-10）。
        """
        repo, _base, run_dir = self.prepared()
        ref = self.attempt_ref(1)
        message = ("collect 只用于调度器异常退出后的恢复：需要状态 RUNNING/COLLECTING（或已领取的 PREPARED）"
                   "且指定 --recover（当前 %s）。")
        self.assert_refused(self.tool_split(repo, "collect", ref), 2, message % "PREPARED")
        self.assert_refused(self.tool_split(repo, "collect", ref, "--recover"), 2, message % "PREPARED")
        self.pd.set_state(run_dir, "RUNNING")
        (run_dir / "pid.txt").write_text("%d\n" % os.getpid(), encoding="utf-8")
        self.assert_refused(self.tool_split(repo, "collect", ref), 2, message % "RUNNING")
        self.assert_refused(self.tool_split(repo, "collect", ref, "--recover"), 3,
                            "记录的 Pi 进程 %d 可能仍在运行；确认终止后再恢复。" % os.getpid())
        self.assertEqual((self.state(repo), (run_dir / "run.json").exists()), ("RUNNING", False))

    def test_LB_EXIT_014_verdict_on_unreviewable_state_is_3(self) -> None:
        """LB-EXIT-014、LB-GATES-031、LB-LIFE-026（:4263-4265）；01-A07，C.4“G0–G6”“wait/退出码语义”。"""
        repo, _base, _run_dir = self.prepared()
        self.assert_refused(self.tool_split(repo, "verdict", self.attempt_ref(1), "--verdict", "PASS",
                                            "--review", self.review(repo, "PASS")), 3, "状态 PREPARED 不能记录验收结论")

    def test_LB_EXIT_014_verdict_usage_2_and_gate_refusal_1(self) -> None:
        """LB-EXIT-014、LB-EXIT-035、LB-GATES-031、LB-GATES-032（:4266-4300）；01-A07，C.4“G0–G6”“wait/退出码语义”。

        没有运行 check 时 G3、G4 失败：PASS 被拒绝为 1（即使带了 --waive，门禁先于豁免检查）；
        其余参数与豁免问题为 2。所有拒绝都不改状态、不写 verdicts/。
        """
        repo, _base = self.make_repo()
        code, out = self.run_ok(repo)
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        ref = self.attempt_ref(1)
        missing = str(repo / ".agent/reviews/none.md")
        self.assert_refused(self.tool_split(repo, "verdict", ref, "--verdict", "PASS", "--review", missing), 2,
                            "找不到复审报告：%s" % missing)
        revise = self.review(repo, "REVISE", name="revise.md")
        self.assert_refused(self.tool_split(repo, "verdict", ref, "--verdict", "PASS", "--review", revise), 2,
                            "复审报告中的 'Verdict:' 行必须恰好是 PASS")
        passing = self.review(repo, "PASS")
        self.assert_refused(self.tool_split(repo, "verdict", ref, "--verdict", "PASS", "--review", passing,
                                            "--waive", "G3"), 2, "--waive 格式应为 G2=原因")
        self.assert_refused(self.tool_split(repo, "verdict", ref, "--verdict", "REVISE", "--review", revise), 2,
                            "REVISE 需要 --class（%s）" % FAILURE_CLASS_LIST)
        gate_lines = ["GATE G3 没有有效的独立检查记录", "GATE G4 没有有效的独立检查记录"]
        refused = "PASS 被拒绝：门禁 G3, G4 未通过。修正后重新验收，或按授权使用 ACCEPTED_WITH_EXCEPTION 并逐项豁免。"
        self.assert_refused(self.tool_split(repo, "verdict", ref, "--verdict", "PASS", "--review", passing), 1,
                            refused, gate_lines)
        self.assert_refused(self.tool_split(repo, "verdict", ref, "--verdict", "PASS", "--review", passing,
                                            "--waive", "G3=x"), 1, refused, gate_lines)
        awe = self.review(repo, "ACCEPTED_WITH_EXCEPTION", name="awe.md")
        self.assert_refused(self.tool_split(repo, "verdict", ref, "--verdict", "ACCEPTED_WITH_EXCEPTION",
                                            "--review", awe), 2, "以下失败门禁没有豁免理由：G3, G4")
        self.assert_refused(self.tool_split(repo, "verdict", ref, "--verdict", "ACCEPTED_WITH_EXCEPTION",
                                            "--review", awe, "--waive", "G3=a", "--waive", "G4=b"), 2,
                            "ACCEPTED_WITH_EXCEPTION 需要至少一项 --waive 与 --decided-by")
        self.assertEqual((self.state(repo), (self.rd(repo) / "verdicts").exists()), ("NEEDS_REVIEW", False))

    def test_LB_EXIT_015_branch_without_passing_verdict_is_3(self) -> None:
        """LB-EXIT-015、LB-GATES-035、LB-EXIT-035（:4331-4342：结论检查先于 --trailer 的 2）；
        01-A07，C.4“补丁往返/完整性”“wait/退出码语义”。"""
        repo, _base, _run_dir = self.prepared()
        message = "最新结论为 None：只有 PASS / ACCEPTED_WITH_EXCEPTION（或 --rework 时的 REVISE）可以建分支。"
        for extra in ([], ["--rework"], ["--trailer", "not a trailer"]):
            with self.subTest(extra=extra):
                self.assert_refused(self.tool_split(repo, "branch", self.attempt_ref(1), *extra), 3, message)

    def test_LB_EXIT_016_mark_refusal_codes(self) -> None:
        """LB-EXIT-016、LB-LIFE-025、LB-GATES-036、LB-EXIT-035（:4395-4419）；01-A07，C.4“wait/退出码语义”。

        INTEGRATED 先检查结论（3）再检查 --ref（2）。PREPARING、COLLECTING、RUNNING 三个状态（:4412）不带 --force
        放弃时都拒绝为 3，状态不变。可疑：INTEGRATED 只看最新结论、不看当前状态，已 ABANDONED 的
        attempt 仍可标为 INTEGRATED（legacy-inventory.md 11.2 第 12 条）。
        """
        repo = self.mini_repo()
        run_dir = self.fake_attempt(repo)
        ref = self.attempt_ref(1)
        self.pd.set_state(run_dir, "PREPARED")
        self.assert_refused(self.tool_split(repo, "mark", ref, "INTEGRATED"), 3,
                            "只有通过验收的候选可以标记为 INTEGRATED；候选已并入后续提交（返工或规划器补齐）时用 SUPERSEDED")
        self.assert_refused(self.tool_split(repo, "mark", ref, "SUPERSEDED", "--ref", "abc", "--reason", "r"), 2,
                            "SUPERSEDED 只用于已结束、尚未集成的 attempt（当前 PREPARED）")
        self.pd.set_state(run_dir, "NEEDS_REVIEW")
        self.assert_refused(self.tool_split(repo, "mark", ref, "SUPERSEDED", "--ref", "abc"), 2,
                            "SUPERSEDED 需要 --ref（包含该候选的提交）与 --reason（由谁、怎样收尾）")
        for active in ("PREPARING", "COLLECTING", "RUNNING"):
            with self.subTest(state=active):
                self.pd.set_state(run_dir, active)
                self.assert_refused(self.tool_split(repo, "mark", ref, "ABANDONED"), 3,
                                    "attempt 处于 %s；如果确认调度器已退出，可加 --force 放弃" % active)
                self.assertEqual(self.state_record(repo)["state"], active)
        self.pd.set_state(run_dir, "RUNNING")
        (run_dir / "pid.txt").write_text("%d\n" % os.getpid(), encoding="utf-8")
        self.assert_refused(self.tool_split(repo, "mark", ref, "ABANDONED", "--force"), 3,
                            "记录的 Pi 进程 %d 仍在运行，不能放弃" % os.getpid())
        self.assertEqual(self.state_record(repo)["state"], "RUNNING")
        # 可疑行为：ABANDONED 之后凭旧的 PASS 结论仍可标 INTEGRATED。
        self.pd.set_state(run_dir, "ABANDONED")
        (run_dir / "verdicts").mkdir()
        (run_dir / "verdicts" / "01.json").write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")
        self.assert_refused(self.tool_split(repo, "mark", ref, "INTEGRATED"), 2,
                            "INTEGRATED 需要 --ref（提交、PR 或合并记录）")
        code, out, err = self.tool_split(repo, "mark", ref, "INTEGRATED", "--ref", "abc")
        self.assertEqual((code, lines(out), err), (0, ["%s 已标记为 INTEGRATED。" % RUN_REL], ""))
        record = self.state_record(repo)
        self.assertEqual((record["state"], record["previous_state"], record["ref"]), ("INTEGRATED", "ABANDONED", "abc"))

    def test_LB_EXIT_017_cleanup_refusal_codes(self) -> None:
        """LB-EXIT-017、LB-LIFE-030、LB-GATES-037（:4435-4467）；01-A07，C.4“候选树漂移”“wait/退出码语义”。

        状态拒绝（:4435-4438）：PREPARED、PREPARING 不带 --force 为 3；RUNNING、COLLECTING 即使带 --force 也为 3。
        状态允许后，没有候选记录属于会丢失内容（:4448-4449），不带 --force 为 3。以上拒绝都不删除 worktree。
        候选补丁被改动的 LOSS 分支（:4451-4452）见下一用例。
        """
        repo, _base, run_dir = self.prepared()
        ref = self.attempt_ref(1)
        worktree = self.worktree_of(repo)
        for state in ("PREPARED", "PREPARING"):
            with self.subTest(state=state):
                self.pd.set_state(run_dir, state)
                self.assert_refused(self.tool_split(repo, "cleanup", ref), 3,
                                    "attempt 尚未运行（%s）；确定放弃请加 --force" % state)
                self.assertTrue(worktree.is_dir())
        for state in ("RUNNING", "COLLECTING"):
            with self.subTest(state=state):
                self.pd.set_state(run_dir, state)
                self.assert_refused(self.tool_split(repo, "cleanup", ref, "--force"), 3,
                                    "attempt 正在运行或收集（%s），不能清理；调度器已退出时先 collect --recover" % state)
                self.assertTrue(worktree.is_dir())
        self.pd.set_state(run_dir, "NEEDS_REVIEW")
        self.assert_refused(self.tool_split(repo, "cleanup", ref), 3,
                            "拒绝清理：以上内容不在已保存的候选中，删除 worktree 会丢失它们。先保存需要的内容；确认放弃请加 --force。",
                            ["LOSS  没有候选记录：worktree 中的全部改动都会丢失"])
        self.assertTrue(worktree.is_dir())
        code, out, err = self.tool_split(repo, "cleanup", ref, "--force")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(lines(out), ["已移除 worktree：%s" % worktree])
        self.assertFalse(worktree.exists())

    def test_LB_GATES_037_cleanup_refuses_when_candidate_patch_tampered(self) -> None:
        """LB-GATES-037、LB-EXIT-017（:4451-4452 调用 candidate_patch_ok :3474-3477；:4463-4467、4481）；01-A07，
        C.4“补丁往返/完整性”“候选树漂移”。

        有候选记录、worktree 与候选树一致，但 candidate.patch 末尾多一个字节（sha256 与 candidate.json 不符）：
        不带 --force 时只报这一条 LOSS、退出 3，worktree 保留；带 --force 时退出 0，history.jsonl 的 cleanup 记录
        把这一条列入 discarded。
        """
        repo, _base = self.make_repo()
        code, out = self.run_ok(repo)
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        run_dir = self.rd(repo)
        ref = self.attempt_ref(1)
        worktree = self.worktree_of(repo)
        loss = "候选补丁缺失、被改动或未通过往返校验：删除后无法重建候选"
        patch = run_dir / "candidate.patch"
        self.assertTrue(self.jload(run_dir / "candidate.json")["patch_roundtrip_verified"])
        patch.write_bytes(patch.read_bytes() + b"\n")
        code, out, err = self.tool_split(repo, "cleanup", ref)
        self.assertEqual(code, 3, out + err)
        self.assertEqual(lines(out), ["LOSS  " + loss])
        self.assertEqual(lines(err), ["ERROR: 拒绝清理：以上内容不在已保存的候选中，删除 worktree 会丢失它们。"
                                      "先保存需要的内容；确认放弃请加 --force。"])
        self.assertTrue(worktree.is_dir())
        self.assertEqual(self.state(repo), "NEEDS_REVIEW")
        code, out, err = self.tool_split(repo, "cleanup", ref, "--force")
        self.assertEqual((code, err), (0, ""), out)
        self.assertEqual(lines(out), ["已移除 worktree：%s" % worktree])
        self.assertFalse(worktree.exists())
        history = [json.loads(l) for l in (run_dir / "history.jsonl").read_text(encoding="utf-8").splitlines() if l]
        cleanup = [r for r in history if r.get("event") == "cleanup"]
        self.assertEqual([(r["forced"], r["discarded"], r["state"]) for r in cleanup], [(True, [loss], "NEEDS_REVIEW")])

    def test_LB_EXIT_012_baseline_refusal_codes(self) -> None:
        """LB-EXIT-012、LB-GATES-015（:4081-4149）；01-A07，C.4“wait/退出码语义”。

        --only 未知检查与合同无效为 2；基线副本的 setup 失败为 3（try/finally 仍移除副本）；expect_on_base 不符为 1。
        """
        repo, base = self.make_repo()
        self.assert_refused(self.tool_split(repo, "baseline", PLAN_KEY, "--only", "V99"), 2, "未知检查：V99")
        self.set_md(repo, "- max_attempts_total: 3", "- max_attempts_total: 5")
        self.assert_refused(self.tool_split(repo, "baseline", PLAN_KEY), 2, "合同校验失败，无法运行基线检查。",
                            ["ERROR Markdown Budget 的 max_attempts_total（5）与 JSON（3）不一致"])
        self.write_plan(repo, base, 1, setup=[{"id": "S01", "argv": [PY, "-c", "import sys; sys.exit(5)"],
                                               "timeout_seconds": 60}])
        code, out, err = self.tool_split(repo, "baseline", PLAN_KEY)
        self.assertEqual(code, 3, out + err)
        self.assertEqual(len(lines(err)), 1, err)
        self.assertTrue(err.startswith("ERROR: 基线副本的 setup S01 失败："), err)
        worktrees = [l for l in self.git(repo, "worktree", "list", "--porcelain").splitlines() if l.startswith("worktree ")]
        self.assertEqual(len(worktrees), 1, worktrees)
        self.write_plan(repo, base, 1, checks=[dict(default_checks()[0], expect_on_base="pass")])
        code, out, err = self.tool_split(repo, "baseline", PLAN_KEY)
        self.assertEqual((code, err), (1, ""), out)
        self.assertTrue(any(l.startswith("V01") and "不符：期望在基线上通过（回归保护），实际未通过——检查本身或基线有问题" in l
                            for l in lines(out)), out)

    def test_LB_EXIT_021_doctor_codes(self) -> None:
        """LB-EXIT-021（:4657-4762：problems→1；--out 非法→2；不带 --out 时仓库错误只进 notes，不返回 2/3）；
        01-A07，C.4“wait/退出码语义”。"""
        repo, _base = self.make_repo(gitignore=".env\n")
        code, out, err = self.tool_split(repo, "doctor")
        self.assertEqual((code, err), (1, ""), out)
        facts = json.loads(out)
        self.assertEqual((facts["ok"], facts["problems"]), (False, [".agent/runs/ 未被 .gitignore 忽略"]))
        code, out, err = self.tool_split(repo, "doctor", "--out", "README.md")
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(lines(err), ["ERROR: --out 只能指向 .agent/runs/_env/ 或 .agent/runs/_reports/ 下的文件：%s"
                                      % (repo / "README.md")])
        plain = self.scripts_dir()
        code, out, err = self.tool_split(plain, "doctor")
        self.assertEqual((code, err), (0, ""), out)
        facts = json.loads(out)
        self.assertEqual(facts["problems"], [])
        self.assertIn("未在 Git 仓库中运行：当前目录不在 Git 仓库中：%s" % plain, facts["notes"])


# ---------------------------------------------------------------------------
# run 的结束状态与退出码
# ---------------------------------------------------------------------------

class LegacyRunOutcomeTest(_CliCase):
    """legacy-inventory.md 7.3“run 的中断”、6.5 节；11.5 第 3、9 条（run 在 TIMEOUT/CANCELLED/INFRA_FAILURE 时退出 1）。"""

    def test_LB_EXIT_009_run_infra_failure_exits_1(self) -> None:
        """LB-EXIT-009、LB-LIFE-019（:3349、3401-3402 没有 assistant 回复→INFRA_FAILURE）；01-A07，C.4“wait/退出码语义”。"""
        repo, _base = self.make_repo()
        code, out = self.run_ok(repo, STUB_SCENARIO="startfail")
        self.assertEqual((code, self.state(repo)), (1, "INFRA_FAILURE"), out)
        self.assertIn("INFRA_FAILURE normalize-query.v1.a001", lines(out))

    def test_LB_EXIT_009_run_timeout_exits_1(self) -> None:
        """LB-EXIT-009、LB-LIFE-016（:691-697、3397-3398）；01-A07，C.4“超时”“wait/退出码语义”。

        旧 test_timeout 只检查状态，不检查退出码（legacy-inventory.md 7.9）。
        """
        repo, _base = self.make_repo()
        self.write_config(repo, kill_grace_seconds=1)
        pi = self.fake_pi(ok_events()[:3], 0, hang_seconds=300)
        self.assertEqual(self.tool(repo, "prepare", PLAN_KEY)[0], 0)
        started = time.monotonic()
        code, out = self.tool(repo, "run", self.attempt_ref(1), "--timeout", "2", pi_cmd=pi)
        self.assertLess(time.monotonic() - started, 120)
        self.assertEqual((code, self.state(repo)), (1, "TIMEOUT"), out)
        run = self.jload(self.rd(repo) / "run.json")
        self.assertEqual((run["timed_out"], run["interrupted"], run["timeout_seconds"]), (True, False, 2))
        self.assertIn("TIMEOUT normalize-query.v1.a001", lines(out))

    def test_LB_LIFE_019_timed_out_and_interrupted_resolves_to_timeout(self) -> None:
        """LB-LIFE-019、LB-LIFE-023（collect 的判定顺序 :3395-3404：TIMEOUT 先于 CANCELLED）；01-A07，C.4“超时”“取消”。

        两个标志同时为真是可达的：run_supervised 到时后置 timed_out（:695），在 try 内调用 _terminate_tree 等待
        宽限（:696），这期间收到中断会由 :703-704 再置 interrupted。在子进程里卡准这个窗口依赖时序，所以这里经
        collect --recover 构造：一次正常运行后把状态改回 COLLECTING，把 run.json 改为两者都为 true；恢复收集原样沿用
        run.json（:3426），最终状态为 TIMEOUT，不是 CANCELLED。
        """
        repo, _base = self.make_repo()
        code, out = self.run_ok(repo)
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        run_dir = self.rd(repo)
        run = self.jload(run_dir / "run.json")
        self.assertEqual((run["timed_out"], run["interrupted"], run.get("spawn_error")), (False, False, None))
        run.update(timed_out=True, interrupted=True)
        (run_dir / "run.json").write_text(json.dumps(run), encoding="utf-8")
        self.pd.set_state(run_dir, "COLLECTING")
        code, out, err = self.tool_split(repo, "collect", self.attempt_ref(1), "--recover")
        self.assertEqual((code, err), (0, ""), out)
        self.assertEqual(lines(out), ["TIMEOUT（恢复收集；事件可能不完整）"])
        self.assertEqual(self.state(repo), "TIMEOUT")
        self.assertEqual(self.jload(run_dir / "run.json"), run)

    def test_LB_EXIT_031_interrupt_during_pi_is_cancelled_exit_1(self) -> None:
        """LB-EXIT-031、LB-LIFE-017（:571-585、703-706、3399-3400、3349）；01-A07，C.4“取消”。

        Pi 运行期间调度器收到中断（Windows 为 CTRL_BREAK，POSIX 为 SIGINT）：由 run_supervised 接管，状态 CANCELLED，
        run 退出 1，不是 130，也不输出“已取消。”（legacy-inventory.md 7.3、11.2 第 15 条）。
        """
        repo, _base = self.make_repo()
        self.write_config(repo, kill_grace_seconds=2)
        pi = self.fake_pi(ok_events()[:3], 0, hang_seconds=300)
        self.assertEqual(self.tool(repo, "prepare", PLAN_KEY)[0], 0)
        run_dir = self.rd(repo)
        proc = self.popen_tool(repo, "run", self.attempt_ref(1), pi_cmd=pi, new_process_group=True)
        # pid.txt 由 on_spawn 写出：此时中断处理器已安装（:676 先于 :680 的 Popen）。
        self.assertTrue(self.wait_for(lambda: (run_dir / "pid.txt").is_file() or proc.poll() is not None, 120),
                        "run 没有启动 Pi")
        self.assertIsNone(proc.poll(), "run 提前结束")
        send_interrupt(proc)
        out, _ = proc.communicate(timeout=180)
        text = out.decode("utf-8", "replace")
        self.assertEqual((proc.returncode, self.state(repo)), (1, "CANCELLED"), text)
        run = self.jload(run_dir / "run.json")
        self.assertEqual((run["interrupted"], run["timed_out"]), (True, False))
        self.assertIn("CANCELLED normalize-query.v1.a001", lines(text))
        self.assertNotIn("已取消。", text)

    def test_LB_LIFE_035_interrupt_during_prepare_setup_is_prepare_failed_exit_1(self) -> None:
        """LB-LIFE-035、LB-EXIT-008（:3087、3097-3098、3225-3229：setup 在 run_supervised 中运行）；01-A07，C.4“取消”。

        prepare 的 setup 期间收到中断：setup 项记为“被取消”，attempt 为 PREPARE_FAILED，prepare 退出 1（不是 130）。
        legacy-inventory.md 6.5“setup 期间 Ctrl+C（prepare）”一行，旧测试没有覆盖。
        """
        repo, _base = self.make_repo(setup=[{"id": "S01", "timeout_seconds": 600, "argv": [
            PY, "-c", "import time; print('setup-ready', flush=True); time.sleep(300)"]}])
        self.write_config(repo, kill_grace_seconds=2)
        run_dir = self.rd(repo)
        log = run_dir / "setup" / "S01.log"
        proc = self.popen_tool(repo, "prepare", PLAN_KEY, new_process_group=True)
        # setup 进程写出标记时，它已由 run_supervised 启动，中断处理器已安装（:676 先于 :680）。
        self.assertTrue(self.wait_for(lambda: (log.is_file() and b"setup-ready" in log.read_bytes())
                                      or proc.poll() is not None, 120), "setup 没有启动")
        self.assertIsNone(proc.poll(), "prepare 提前结束")
        send_interrupt(proc)
        out, _ = proc.communicate(timeout=180)
        text = out.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 1, text)
        self.assertIn("setup 失败：S01（日志 %s/setup/S01.log）。修正后重新 prepare；本 attempt 未领取，不计入尝试次数。"
                      % RUN_REL, lines(text))
        self.assertNotIn("已取消。", text)
        record = self.state_record(repo)
        self.assertEqual((record["state"], record["reason"]), ("PREPARE_FAILED", "setup S01 失败：被取消"))
        setup = self.jload(run_dir / "setup.json")
        self.assertEqual([(s["id"], s["status"], s["interrupted"], s["reason"]) for s in setup],
                         [("S01", "failed", True, "被取消")])
        self.assertFalse((run_dir / "claim").exists())

    @unittest.skipUnless(IS_WINDOWS, "CTRL_BREAK_EVENT 只在 Windows 上存在；POSIX 上 run_supervised 之外的信号未取证")
    def test_LB_LIFE_035_ctrl_break_in_wait_loop_is_not_handled(self) -> None:
        """LB-LIFE-035、LB-EXIT-002（:4964-4971 只处理 KeyboardInterrupt；SIGBREAK 只在 run_supervised 内登记 :676）；
        01-A07，C.4“取消”。

        可疑：wait 在轮询循环（:3930-3939）中收到 CTRL_BREAK，进程由系统默认处理结束（STATUS_CONTROL_C_EXIT），
        没有任何输出（不输出“已取消。”），也不是 130（legacy-inventory.md 7.9、11.3 第 11 条）。
        送达时机：必须在 wait 进入轮询循环之后发送。更早送达测到的只是解释器启动或导入阶段（进程初始化完成之前
        还会得到别的系统退出码，本机观察到 0xC0000142），循环里的信号处理变了也发现不了。wait 在进入循环之前只调用
        一次 git（Repo.discover :958），之后只读文件。所以用 GIT_TRACE2_EVENT 让 git 把 trace2 事件追加到本用例
        临时区域的文件里：读到这次调用的 atexit 事件（git 即将退出，Repo.discover 随即返回）后再等 1.5 秒，并确认
        进程仍在运行（--timeout 120，仍在循环中）、trace 中恰有这一次 rev-parse 调用，才发送。这个变量只让 git
        另写诊断文件，不改变 git 的输出，也不改变被测脚本的逻辑（git_env :412-417 原样传递）。
        """
        repo = self.mini_repo()
        self.fake_attempt(repo, {"state": "RUNNING"})
        trace = self.work / "git-trace2.jsonl"
        proc = self.popen_tool(repo, "wait", "normalize-query/attempt-001", "--timeout", "120", "--interval", "0.5",
                               env={"GIT_TRACE2_EVENT": str(trace)}, new_process_group=True)
        self.assertTrue(self.wait_for(lambda: (trace.is_file() and b'"event":"atexit"' in trace.read_bytes())
                                      or proc.poll() is not None, 60), "wait 没有调用 git")
        self.assertIsNone(proc.poll(), "wait 提前结束")
        time.sleep(1.5)  # 有意的延迟：git 退出后 Repo.discover 返回，wait 进入轮询循环
        self.assertIsNone(proc.poll(), "wait 提前结束")
        starts = [e for e in (json.loads(l) for l in trace.read_bytes().splitlines() if l.strip())
                  if e.get("event") == "start"]
        self.assertEqual(len(starts), 1, starts)
        self.assertIn("rev-parse", starts[0]["argv"])
        send_interrupt(proc)
        out, _ = proc.communicate(timeout=60)
        text = out.decode("utf-8", "replace")
        self.assertEqual(proc.returncode, STATUS_CONTROL_C_EXIT, text[-500:])
        self.assertEqual(text, "")


# ---------------------------------------------------------------------------
# 范围判定（端到端：假 pi 在 worktree 中制造改动）
# ---------------------------------------------------------------------------

_SYMLINK_PI = r'''# -*- coding: utf-8 -*-
"""测试用包装：运行模式下先在工作目录建符号链接，再原样运行内层的 stub（不调用模型、不联网）。"""
import os
import runpy
import sys

args = sys.argv[1:]
if not ("--help" in args or "--version" in args or (args and args[0] == "auth") or "--list-models" in args):
    os.makedirs(os.path.dirname(LINK) or ".", exist_ok=True)
    os.symlink(TARGET, LINK)
sys.argv = [INNER] + args
runpy.run_path(INNER, run_name="__main__")
'''


class LegacyScopeEndToEndTest(_CliCase):
    """C.4“范围检查”的端到端样本：collect 写出的 changes.json / scope.json（legacy-inventory.md 5.2、5.4）。"""

    def scope_of(self, repo: Path) -> Dict[str, Any]:
        return self.jload(self.rd(repo) / "scope.json")

    def test_LB_GATES_018_e2e_deleted_file_is_out_of_scope_run_still_0(self) -> None:
        """LB-GATES-018、LB-GATES-007（:2465-2467；越界不改变 collect 状态 :3395-3406）；01-A07，C.4“范围检查”。

        可疑：范围违规时 run 仍以 NEEDS_REVIEW 退出 0，违规只在 G2 拦下（legacy-inventory.md 5.2 collect 状态一行）。
        """
        repo, _base = self.make_repo()
        pi = self.fake_pi(ok_events(), 0, files=dict(OK_FILES, **{"README.md": None}))
        code, out = self.run_ok(repo, pi_cmd=pi)
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        scope = self.scope_of(repo)
        self.assertEqual(scope["violations"], [{"path": "README.md", "kind": "out_of_scope",
                                                "detail": "状态 D 不在允许集合"}])
        self.assertEqual((scope["ok"], scope["counts"]), (False, {"A": 1, "M": 1, "D": 1, "T": 0}))

    def test_LB_GATES_017_e2e_case_variant_protected_paths(self) -> None:
        """LB-GATES-017（受保护模式忽略大小写 :2459-2461）；01-A07，C.4“范围检查”（大小写不同的受保护路径）。"""
        repo, _base = self.make_repo()
        files = dict(OK_FILES, **{".Agent/notes.md": "x\n", "sub/Agents.md": "x\n"})
        code, out = self.run_ok(repo, pi_cmd=self.fake_pi(ok_events(), 0, files=files))
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        scope = self.scope_of(repo)
        self.assertEqual(sorted(scope["violations"], key=lambda v: v["path"]), [
            {"path": ".Agent/notes.md", "kind": "protected_path", "detail": "合同、证据、代理规则或调度器文件"},
            {"path": "sub/Agents.md", "kind": "protected_path", "detail": "合同、证据、代理规则或调度器文件"}])
        self.assertFalse(scope["ok"])

    def test_LB_GATES_018_e2e_new_symlink_is_violation(self) -> None:
        """LB-GATES-018、LB-GATES-009（:2468-2470；diff_raw 记 new_mode 120000）；01-A07，C.4“范围检查”（symlink）。"""
        probe = self.work / "symlink-probe"
        try:
            os.symlink("missing-target", str(probe))
        except (OSError, NotImplementedError) as exc:
            self.skipTest("当前账户不能创建符号链接（Windows 需要开发者模式或 SeCreateSymbolicLinkPrivilege）：%s" % exc)
        probe.unlink()
        scope_over = contract("0" * 40)["scope"]
        scope_over["allowed_new_files"] = ["tests/test_normalize.py", "src/link.py"]
        repo, _base = self.make_repo(scope=scope_over)
        wrapper = self.work / "symlink_pi.py"
        header = "LINK = %r\nTARGET = %r\nINNER = %r\n" % ("src/link.py", "normalize.py", self.stub_cmd[1])
        wrapper.write_text(_SYMLINK_PI.replace("import os\n", header + "import os\n", 1), encoding="utf-8")
        code, out = self.run_ok(repo, pi_cmd=[PY, str(wrapper)])
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        changes = self.jload(self.rd(repo) / "changes.json")
        self.assertIn({"path": "src/link.py", "status": "A", "old_mode": "000000", "new_mode": "120000"}, changes)
        scope = self.scope_of(repo)
        self.assertEqual(scope["violations"], [{"path": "src/link.py", "kind": "symlink",
                                                "detail": "新增或改为符号链接"}])
        self.assertFalse(scope["ok"])

    def test_LB_GATES_019_e2e_local_commit_head_moved_is_warning(self) -> None:
        """LB-GATES-019（:2488-2491、3367）；01-A07，C.4“范围检查”（local_commit 下的 head_moved）。

        旧 test_commit_outside_main 只测了没有 local_commit 时记违规。
        """
        repo, base = self.make_repo(authorization={"executor": ["local_edit", "local_test", "local_commit"],
                                                   "integration": ["local_branch"]})
        code, out = self.run_ok(repo, STUB_SCENARIO="commit")
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        scope = self.scope_of(repo)
        self.assertNotEqual(scope["head_after"], base)
        self.assertEqual(scope["violations"], [])
        self.assertEqual(scope["warnings"], [{"path": "HEAD", "kind": "head_moved",
                                              "detail": "执行器改变了 HEAD（%s）" % scope["head_after"][:12]}])
        self.assertTrue(scope["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
