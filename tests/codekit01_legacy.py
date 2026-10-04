#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""01-T3 legacy fixtures：旧实现的比较投影与锁定预期（投影修订号 codekit01-legacy-projection-v1）。

本模块是 legacy fixture 比较投影的**唯一定义**：锁定预期（tests/fixtures/codekit01/expected/legacy-*.json）
与后续差分测试都调用这里的函数，不在别处另写一份投影。

- 旧实现：scripts/pi_dispatch.py（提交 a4fa199b0e5bdc658215765ee7558b9fe6723940，工具版本 2.2.2）。
  从读到的同一份字节编译执行（不经 import 缓存，不写字节码）；只调用纯函数与只读的 validate 子命令，
  不调用 run/prepare 等会写状态的入口。生成预期与 --check 时先核对文件 SHA-256 必须等于 a4fa199
  （预期只能由旧实现生成）；差分测试传 require_locked_bytes=False，按当前字节重算并只比较 cases，
  “字节是否仍为 a4fa199”由单独的测试判断。
- 预期只来自旧实现。新严格入口（codekit.protocols.strict_json_loads）的判断由 new_strict_verdict 单独给出，
  写入单独的 tests/fixtures/codekit01/expected/legacy-new-strict.json，**不写入** legacy 预期文件；
  新旧判断的差异是兼容矩阵的输入，不是失败。
- legacy 条目的 manifest 定义（build_legacy_manifest_entries）也在本模块；整份
  tests/fixtures/codekit01/manifest.json 由 tests/test_codekit01_fixtures.py --write 合并生成
  （P3 第一部分的 manifest.legacy.draft.json 已并入该文件并删除）。
- 本模块导入时只解析本文件所在目录，不读文件内容、不起进程、不写任何东西；所有动作都在函数被调用时发生。
- 收尾轮（裁决 R-P11）：legacy 条目填写 integrity、platform_scope、capture、redaction.protocol_structure_preserved
  与 origin.traceable，登记规则见 build_legacy_manifest_entries 前的常量说明。
- 收尾轮（acceptance.md M-04）：为兼容矩阵 D-20–D-23 增加 6 个合同单一故障负例（非有限费用金额 2 个、深层嵌套、
  JSON 与 Markdown 非 UTF-8 各 1 个、setup id 末尾换行），旧判断进入 legacy-contracts.json 的新用例，新严格入口
  的判断进入 legacy-new-strict.json；已有用例的投影不变。
- 收尾轮（文档 8.4，acceptance.md R-12）：本模块的递归删除只删除自己用 _make_owned_tempdir 建立的目录；删除前
  核对真实路径的父目录是系统临时目录（逐段比较）、目录名前缀属于本工具、目录本身不是链接，以及目录内的所有权
  标记与本进程登记的随机令牌相同，任一不满足即拒绝删除并报 CleanupRefused（见 _rmtree）。

用法（在仓库根目录运行）：
  PYTHONDONTWRITEBYTECODE=1 python tests/codekit01_legacy.py --write
      从 a4fa199 取合同原字节、派生单一故障负例、运行 tests/stub_pi.py 取事件流，
      再用旧实现计算预期、用新严格入口计算 legacy-new-strict.json。
  PYTHONDONTWRITEBYTECODE=1 python tests/codekit01_legacy.py --write-derived
      不重取 blob、不重跑 stub：从已锁定的 legacy 字节重新派生合同与事件负例，再重算三份预期文件。
      新增负例变体时用它，已锁定的原字节与 stub 事件字节不被重写。
  PYTHONDONTWRITEBYTECODE=1 python tests/codekit01_legacy.py --write-expected
      只根据已锁定的 fixture 字节重算三份预期文件（不重跑 stub）。
  之后运行 PYTHONDONTWRITEBYTECODE=1 python tests/test_codekit01_fixtures.py --write 重建 manifest.json
  （预期文件的摘要变化会进入 manifest）。
  PYTHONDONTWRITEBYTECODE=1 python tests/codekit01_legacy.py --check
      核对 legacy 合同副本、工作区来源文件与 a4fa199 的 blob 相同，从已锁定的 fixture 字节重新派生负例、
      重算预期，并与 manifest.json 中的 legacy 条目逐字节比较；不写文件。
  PYTHONDONTWRITEBYTECODE=1 python tests/codekit01_legacy.py --check-stub-regen
      重新运行 stub，与已锁定的事件字节比较（stub 输出的行尾随平台变化，只在 Windows 上实测一致）。
      默认测试 tests/test_codekit01_fixtures.py 的 StubTests 在 Windows 上也调用 check_stub_regen，其他平台记为 NOT_RUN。
"""
from __future__ import annotations

import hashlib
import hmac
import io
import json
import math
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# 固定常量
# ---------------------------------------------------------------------------

SOURCE_REVISION = "a4fa199b0e5bdc658215765ee7558b9fe6723940"
PROJECTION_REVISION = "codekit01-legacy-projection-v1"
#: v1（P3）：legacy 合同副本、13 个合同负例、10 条 stub 流与 3 个事件负例。
#: v2（收尾轮）：新增 D-20–D-23 的 6 个合同负例（NEGATIVE_CONTRACT_VARIANTS 末尾）；递归删除加归属核对。
#: v3（01 完善）：新增 JSON 缺 task_id 与最后一条 message_end 的 usage 缺 token 字段两个单一故障负例。
#: 已有 fixture 的派生函数与字节不变（--check 与 --check-stub-regen 逐字节核对）。
FIXTURE_GENERATOR_REVISION = "codekit01-legacy-fixtures-v3"
STUB_CWD_RULE_REVISION = "codekit01-legacy-stub-cwd-v1"
STUB_CWD_PLACEHOLDER = "<redacted:stub-cwd>"

#: scripts/pi_dispatch.py 在 a4fa199 的字节摘要（blob 8e7df57c91fc589895c171254e71cbc3d056c313）。
LEGACY_PI_DISPATCH_PATH = "scripts/pi_dispatch.py"
LEGACY_PI_DISPATCH_SHA256 = "a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4"
LEGACY_PI_DISPATCH_BLOB = "8e7df57c91fc589895c171254e71cbc3d056c313"
#: tests/stub_pi.py 在 a4fa199 的字节摘要。
LEGACY_STUB_PATH = "tests/stub_pi.py"
LEGACY_STUB_SHA256 = "96c0d4a5ba775e9c23ce104176f1e2f0fbe6eb2925eafef5b0c5fd5c248e916a"

#: 锁定预期时的环境（事实记录；投影内容本身不含机器路径或时间）。
LOCKED_WITH = "Windows Server 2025 Standard 10.0.26100；Python 3.12.10；Git 2.55（Git for Windows）"

WRITE_COMMAND = "PYTHONDONTWRITEBYTECODE=1 python tests/codekit01_legacy.py --write"
CHECK_COMMAND = "PYTHONDONTWRITEBYTECODE=1 python tests/codekit01_legacy.py --check"

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_DIR = "tests/fixtures/codekit01"
EXPECTED_CONTRACTS_PATH = FIXTURE_DIR + "/expected/legacy-contracts.json"
EXPECTED_EVENTS_PATH = FIXTURE_DIR + "/expected/legacy-events.json"
EXPECTED_NEW_STRICT_PATH = FIXTURE_DIR + "/expected/legacy-new-strict.json"
MANIFEST_PATH = FIXTURE_DIR + "/manifest.json"
EXPECTED_CONTRACTS_ID = "expected-legacy-contracts"
EXPECTED_EVENTS_ID = "expected-legacy-events"
EXPECTED_NEW_STRICT_ID = "expected-legacy-new-strict"
NEW_STRICT_REVISION = "codekit01-new-strict-projection-v1"

#: 本模块允许写入的前缀（任务分配的独占范围）。manifest.json 由 tests/test_codekit01_fixtures.py 写。
_WRITE_PREFIXES = (
    FIXTURE_DIR + "/legacy/",
    FIXTURE_DIR + "/negative/legacy-",
    FIXTURE_DIR + "/expected/legacy-",
)

UTF8_BOM = b"\xef\xbb\xbf"

# ---------------------------------------------------------------------------
# legacy 合同选样（原字节，取自 a4fa199）
# ---------------------------------------------------------------------------

#: (fixture_id, 仓库中的来源路径, fixture 路径, 说明)
LEGACY_CONTRACT_FILES: Tuple[Tuple[str, str, str, str], ...] = (
    ("legacy-contract-normalize-query-v1-md", ".agents/skills/plan-task/examples/normalize-query.v1.md",
     FIXTURE_DIR + "/legacy/contracts/normalize-query.v1.md",
     "plan-task 技能示例合同 normalize-query.v1 的 Markdown（虚构仓库 example-search-app，base_sha 为虚构值）"),
    ("legacy-contract-normalize-query-v1-json", ".agents/skills/plan-task/examples/normalize-query.v1.json",
     FIXTURE_DIR + "/legacy/contracts/normalize-query.v1.json",
     "plan-task 技能示例合同 normalize-query.v1 的机器合同 JSON（base_sha 为虚构值）"),
    ("legacy-contract-auth-refresh-401-v1-md", ".agents/skills/plan-task/examples/auth-refresh-401.v1.md",
     FIXTURE_DIR + "/legacy/contracts/auth-refresh-401.v1.md",
     "plan-task 技能示例合同 auth-refresh-401.v1 的 Markdown（base_sha 为虚构值）"),
    ("legacy-contract-auth-refresh-401-v1-json", ".agents/skills/plan-task/examples/auth-refresh-401.v1.json",
     FIXTURE_DIR + "/legacy/contracts/auth-refresh-401.v1.json",
     "plan-task 技能示例合同 auth-refresh-401.v1 的机器合同 JSON（base_sha 为虚构值）"),
    ("legacy-contract-template-md", ".agents/skills/plan-task/contract-template.md",
     FIXTURE_DIR + "/legacy/contracts/contract-template.md",
     "plan-task 技能的合同模板 Markdown（含【待填…】占位符，不是可派遣的合同）"),
    ("legacy-contract-template-json", ".agents/skills/plan-task/contract-template.json",
     FIXTURE_DIR + "/legacy/contracts/contract-template.json",
     "plan-task 技能的合同模板 JSON（含【待填…】占位符，不是可派遣的合同）"),
)

#: (case_id, plan_key, md fixture_id, json fixture_id, 说明)
#: contract-template 的文件名不是计划标识；投影固定用 contract-template.v1 作为计划标识（投影输入，不来自旧实现）。
LEGACY_CONTRACT_CASES: Tuple[Tuple[str, str, str, str, str], ...] = (
    ("legacy-contract-normalize-query-v1", "normalize-query.v1",
     "legacy-contract-normalize-query-v1-md", "legacy-contract-normalize-query-v1-json", "技能示例原样"),
    ("legacy-contract-auth-refresh-401-v1", "auth-refresh-401.v1",
     "legacy-contract-auth-refresh-401-v1-md", "legacy-contract-auth-refresh-401-v1-json", "技能示例原样"),
    ("legacy-contract-template", "contract-template.v1",
     "legacy-contract-template-md", "legacy-contract-template-json",
     "合同模板原样；计划标识 contract-template.v1 由投影指定"),
)

# ---------------------------------------------------------------------------
# 单一故障负例（从 normalize-query.v1 出发，每个变体只改一处）
# ---------------------------------------------------------------------------

_BASE_SHA = b"0123456789abcdef0123456789abcdef01234567"


def _replace_once(old: bytes, new: bytes) -> Callable[[bytes], bytes]:
    def transform(data: bytes) -> bytes:
        if data.count(old) != 1:
            raise AssertionError("单一故障变体的锚点必须恰好出现一次：%r" % old)
        return data.replace(old, new, 1)
    return transform


def _prefix_bom(data: bytes) -> bytes:
    if data.startswith(UTF8_BOM):
        raise AssertionError("来源已带 BOM")
    return UTF8_BOM + data


def _lf_to_crlf(data: bytes) -> bytes:
    if b"\r" in data:
        raise AssertionError("来源已含 CR")
    return data.replace(b"\n", b"\r\n")


def _drop_md_section(name: bytes, next_name: bytes) -> Callable[[bytes], bytes]:
    def transform(data: bytes) -> bytes:
        start_marker = b"\n## " + name + b"\n"
        end_marker = b"\n## " + next_name + b"\n"
        if data.count(start_marker) != 1 or data.count(end_marker) != 1:
            raise AssertionError("章节锚点必须恰好出现一次")
        start = data.index(start_marker) + 1
        end = data.index(end_marker) + 1
        if not start < end:
            raise AssertionError("章节顺序与预期不符")
        return data[:start] + data[end:]
    return transform


#: (case 后缀, 被修改的文件 "md"/"json", 变换, 故障说明)
NEGATIVE_CONTRACT_VARIANTS: Tuple[Tuple[str, str, Callable[[bytes], bytes], str], ...] = (
    ("json-task-id-mismatch", "json",
     _replace_once(b'"task_id": "normalize-query",', b'"task_id": "normalize-queries",'),
     "JSON 的 task_id 改为 normalize-queries，与文件名和 Markdown 标题中的 normalize-query 不一致"),
    ("json-plan-version-string", "json",
     _replace_once(b'"plan_version": 1,', b'"plan_version": "1",'),
     "JSON 的 plan_version 由整数 1 改为字符串 \"1\""),
    ("json-plan-version-float", "json",
     _replace_once(b'"plan_version": 1,', b'"plan_version": 1.0,'),
     "JSON 的 plan_version 由整数 1 改为实数 1.0"),
    ("json-schema-version-true", "json",
     _replace_once(b'"schema_version": 1,', b'"schema_version": true,'),
     "JSON 的 schema_version 由整数 1 改为布尔 true"),
    ("json-base-sha-short-oid", "json",
     _replace_once(b'"base_sha": "' + _BASE_SHA + b'",', b'"base_sha": "0123456",'),
     "JSON 的 base_sha 改为 7 位短 OID 0123456（Markdown 仍是完整 40 位值）"),
    ("json-base-sha-trailing-newline", "json",
     _replace_once(b'"base_sha": "' + _BASE_SHA + b'",', b'"base_sha": "' + _BASE_SHA + b'\\n",'),
     "JSON 的 base_sha 末尾多一个换行（JSON 转义 \\n）"),
    ("json-unknown-top-level-field", "json",
     _replace_once(b'  "schema_version": 1,\n', b'  "schema_version": 1,\n  "unexpected_field": true,\n'),
     "JSON 顶层增加未知字段 unexpected_field"),
    ("json-utf8-bom", "json", _prefix_bom, "JSON 文件开头加 UTF-8 BOM（EF BB BF）"),
    ("json-duplicate-key-first-differs", "json",
     _replace_once(b'  "risk_level": "low",\n', b'  "risk_level": "high",\n  "risk_level": "low",\n'),
     "JSON 顶层重复键 risk_level：先写 high，后写与 Markdown 一致的 low"),
    ("json-duplicate-key-last-differs", "json",
     _replace_once(b'  "risk_level": "low",\n', b'  "risk_level": "low",\n  "risk_level": "high",\n'),
     "JSON 顶层重复键 risk_level：先写与 Markdown 一致的 low，后写 high"),
    ("md-missing-scope-section", "md", _drop_md_section(b"Scope", b"Behavior contract"),
     "Markdown 删除整个 ## Scope 节（标题与节体）"),
    ("md-utf8-bom", "md", _prefix_bom, "Markdown 文件开头加 UTF-8 BOM（EF BB BF）"),
    ("md-crlf-line-endings", "md", _lf_to_crlf, "Markdown 的全部 LF 行尾改为 CRLF（内容不变）"),
    # --- 收尾轮（acceptance.md M-04）：兼容矩阵 4.3 节 D-20–D-23，追加在末尾，已有变体的顺序与字节不变 ---
    ("json-cost-budget-infinity", "json",
     _replace_once(b'"cost_budget": null', b'"cost_budget": {"amount": Infinity, "currency": "USD"}'),
     "兼容矩阵 D-20：budget.cost_budget 由 null 改为 {amount: Infinity, currency: USD}，金额是 JSON 之外的非有限字面量"
     "（Markdown 的 Budget 节写 cost_budget: tracking-only，旧实现不比较费用预算；与 NaN 变体只差金额字面量）"),
    ("json-cost-budget-nan", "json",
     _replace_once(b'"cost_budget": null', b'"cost_budget": {"amount": NaN, "currency": "USD"}'),
     "兼容矩阵 D-20：budget.cost_budget 由 null 改为 {amount: NaN, currency: USD}（与 Infinity 变体只差金额字面量）"),
    ("json-deep-nesting", "json",
     _replace_once(b'  "schema_version": 1,\n',
                   b'  "schema_version": 1,\n  "unexpected_nesting": ' + b"[" * 100000 + b"]" * 100000 + b",\n"),
     "兼容矩阵 D-21：顶层增加字段 unexpected_nesting，值为 100000 层嵌套的空数组（本机 Python 3.12.10 的 json 实测 2000 层"
     "可解析、5000 层抛 RecursionError，取远大于阈值的层数）。旧实现忽略未知顶层字段、新严格入口只判断 JSON 层（两者都由 "
     "json-unknown-top-level-field 锁定），所以起作用的故障只有嵌套深度"),
    ("json-invalid-utf8", "json", _replace_once(b'"risk_level": "low",', b'"risk_level": "low\xff",'),
     "兼容矩阵 D-22：JSON 的 risk_level 字符串中插入字节 0xFF（不是有效 UTF-8）"),
    ("md-invalid-utf8", "md", _replace_once(b"- risk_level: low\n", b"- risk_level: low\xff\n"),
     "兼容矩阵 D-22：Markdown Identity 的 risk_level 行末插入字节 0xFF（不是有效 UTF-8）"),
    ("json-setup-id-trailing-newline", "json", _replace_once(b'{"id": "S01",', b'{"id": "S01\\n",'),
     "兼容矩阵 D-23：setup 项的 id 由 S01 改为 S01 加末尾换行（JSON 转义 \\n）。setup id 只经 ITEM_ID_RE（^…$ 加 "
     "re.match）检查，不与 Markdown 比较"),
    ("json-missing-task-id", "json", _replace_once(b'  "task_id": "normalize-query",\n', b""),
     "文档 6.6 缺字段类：只删除 JSON 顶层必填 task_id，Markdown 与其他 JSON 字段保持原字节"),
)

#: D-20–D-23 与负例变体的对应（兼容矩阵 4.3 节；测试核对这些变体都存在）。
COMPAT_MATRIX_D_CASES: Dict[str, Tuple[str, ...]] = {
    "D-20": ("json-cost-budget-infinity", "json-cost-budget-nan"),
    "D-21": ("json-deep-nesting",),
    "D-22": ("json-invalid-utf8", "md-invalid-utf8"),
    "D-23": ("json-setup-id-trailing-newline",),
}

NEGATIVE_CONTRACT_BASE_CASE = "legacy-contract-normalize-query-v1"
NEGATIVE_CONTRACT_PLAN_KEY = "normalize-query.v1"


def negative_contract_fixture_id(slug: str) -> str:
    return "negative-legacy-contract-" + slug


def negative_contract_path(slug: str, target: str) -> str:
    return "%s/negative/legacy-contracts/%s/normalize-query.v1.%s" % (FIXTURE_DIR, slug, target)


# ---------------------------------------------------------------------------
# stub 事件流场景（tests/stub_pi.py 在 a4fa199 生成）
# ---------------------------------------------------------------------------

#: 与 pi_dispatch 测试合同、normalize-query 示例一致的请求执行器。
REQUESTED_EXECUTOR = {"provider": "step", "model": "step-5-preview", "thinking": "high"}
REQUESTED_TOOLS = ("read", "grep", "find", "ls", "edit", "write", "bash")

#: (slug, 环境变量, 生成时观察到的 stub 退出码, 说明)
STUB_SCENARIOS: Tuple[Tuple[str, Dict[str, str], int, str], ...] = (
    ("ok", {"STUB_SCENARIO": "ok"}, 0,
     "正常结束：以 agent_settled 结束，两条 assistant 消息带用量与费用，不回报 providerThinkingLevel"),
    ("ok-nocost", {"STUB_SCENARIO": "ok", "STUB_NOCOST": "1"}, 0,
     "费用缺失：assistant 用量的 cost 各项为 0（旧实现判为费用未知）"),
    ("ok-ptl-low", {"STUB_SCENARIO": "ok", "STUB_PTL": "low"}, 0,
     "思考级别不符：assistant 回报 providerThinkingLevel=low，请求为 high"),
    ("ok-ptl-high", {"STUB_SCENARIO": "ok", "STUB_PTL": "high"}, 0,
     "思考级别一致：assistant 回报 providerThinkingLevel=high"),
    ("nosettle", {"STUB_SCENARIO": "nosettle"}, 0,
     "缺结束证据：有 agent_end(willRetry=false) 但没有 agent_settled，进程退出 0"),
    ("startfail", {"STUB_SCENARIO": "startfail"}, 1,
     "启动失败：只有 session 事件，没有 assistant 消息、用量与结束事件，进程退出 1"),
    ("model", {"STUB_SCENARIO": "model"}, 0,
     "模型不符：assistant 的 model/responseModel 为 stepfun/step-3.5-flash，provider 仍为 step"),
    ("error", {"STUB_SCENARIO": "error"}, 0,
     "最终消息出错：stopReason=error，errorMessage=429 rate limited，进程仍退出 0"),
    ("scope", {"STUB_SCENARIO": "scope"}, 0,
     "工具调用与错误：写/改多个文件，一条 bash 调用 isError=true"),
    ("textcall", {"STUB_SCENARIO": "textcall"}, 0,
     "最终正文含文本形式的工具调用（<tool_call>），Pi 未执行"),
)

#: 运行 stub 时需要从继承环境中去掉的变量（与 tests/test_dispatch.py 的 BASE_ENV 一致，外加 PI_DISPATCH_PI_CMD）。
_STUB_ENV_REMOVE = ("PI_EXEC_PROVIDER", "PI_EXEC_MODEL", "PI_EXEC_THINKING", "STUB_SCENARIO", "STUB_MODELS",
                    "STUB_AUTH", "STUB_PTL", "STUB_NOCOST", "STUB_LIST_FAIL", "STUB_AUTH_DETAIL",
                    "STUB_MAIN_REPO", "PI_DISPATCH_PI_CMD")


def stub_fixture_id(slug: str) -> str:
    return "legacy-stub-events-" + slug


def stub_fixture_path(slug: str) -> str:
    return "%s/legacy/stub-events/%s.jsonl" % (FIXTURE_DIR, slug)


def stub_source_test_id(env: Dict[str, str]) -> str:
    parts = ["STUB_SCENARIO=%s" % env["STUB_SCENARIO"]]
    parts += ["%s=%s" % (k, env[k]) for k in sorted(env) if k != "STUB_SCENARIO"]
    return "tests/stub_pi.py " + " ".join(parts)


def _split_lines_keepends(data: bytes) -> List[bytes]:
    return data.splitlines(keepends=True)


def _truncate_last_line(data: bytes) -> bytes:
    lines = _split_lines_keepends(data)
    last = lines[-1]
    body = last.rstrip(b"\r\n")
    if not body:
        raise AssertionError("最后一行为空")
    cut = len(b"".join(lines[:-1])) + len(body) // 2
    return data[:cut]


def _duplicate_final_message_end(data: bytes) -> bytes:
    lines = _split_lines_keepends(data)
    indexes = [i for i, line in enumerate(lines) if b'"type": "message_end"' in line
               and b'"role": "assistant"' in line]
    if not indexes:
        raise AssertionError("没有 assistant message_end")
    i = indexes[-1]
    return b"".join(lines[:i + 1] + [lines[i]] + lines[i + 1:])


def _insert_unparseable_line(data: bytes) -> bytes:
    lines = _split_lines_keepends(data)
    ending = b"\r\n" if lines[0].endswith(b"\r\n") else b"\n"
    return b"".join(lines[:1] + [b"this line is not json" + ending] + lines[1:])


def _drop_final_usage_tokens(data: bytes) -> bytes:
    """只删除最终 assistant message_end 的 usage token 字段；保留 cost、其他消息和全部行尾。"""
    lines = _split_lines_keepends(data)
    indexes = [i for i, line in enumerate(lines) if b'"type": "message_end"' in line
               and b'"role": "assistant"' in line and b'"stopReason": "stop"' in line]
    if len(indexes) != 1:
        raise AssertionError("最终 assistant message_end 锚点必须恰好出现一次")
    index = indexes[0]
    lines[index] = _replace_once(
        b'"usage": {"input": 1000, "output": 200, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 1200, ',
        b'"usage": {')(lines[index])
    return b"".join(lines)


#: (slug, 来源 stub slug, 变换, 故障说明)
NEGATIVE_EVENT_VARIANTS: Tuple[Tuple[str, str, Callable[[bytes], bytes], str], ...] = (
    ("ok-truncated-tail", "ok", _truncate_last_line,
     "尾部截断：保留最后一行（agent_settled）的前一半字节，删去其余部分与行尾"),
    ("ok-duplicate-final-message-end", "ok", _duplicate_final_message_end,
     "重复投递：最后一条 assistant message_end 行原样重复一次，紧跟在原行之后"),
    ("ok-unparseable-line", "ok", _insert_unparseable_line,
     "夹入无法解析的行：在 session 行之后插入一行非 JSON 文本（沿用原流行尾）"),
    ("ok-final-usage-missing-tokens", "ok", _drop_final_usage_tokens,
     "文档 6.6 缺字段类：只删除最终 assistant message_end 中 usage 的 input/output/cacheRead/cacheWrite/totalTokens；"
     "usage 对象及 cost、其他事件与行尾不变。旧实现将该消息缺失的 token 记为 0，仍累计其费用"),
)

#: 事件负例的 integrity（裁决 R-P11）。它们代表的是证据流本身：尾部截断的流为 truncated，夹入无法解析的行
#: （记录被破坏）为 corrupted；重复投递没有丢失或损坏任何字节，只是同一条记录多出现一次，为 complete。
NEGATIVE_EVENT_INTEGRITY: Dict[str, str] = {
    "ok-truncated-tail": "truncated",
    "ok-duplicate-final-message-end": "complete",
    "ok-unparseable-line": "corrupted",
    "ok-final-usage-missing-tokens": "complete",
}


def negative_event_fixture_id(slug: str) -> str:
    return "negative-legacy-events-" + slug


def negative_event_path(slug: str) -> str:
    return "%s/negative/legacy-events/%s/events.jsonl" % (FIXTURE_DIR, slug)


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def render_json(value: Any) -> bytes:
    """固定序列化：UTF-8、无 BOM、键排序、缩进 2、LF、禁止 NaN/Infinity，末尾一个 LF。"""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def repo_path(rel: str) -> Path:
    return REPO_ROOT.joinpath(*rel.split("/"))


def read_fixture(rel: str) -> bytes:
    return repo_path(rel).read_bytes()


def _write_bytes(rel: str, raw: bytes) -> None:
    if not any(rel.startswith(prefix) or rel == prefix for prefix in _WRITE_PREFIXES):
        raise AssertionError("拒绝写入任务范围之外的路径：%s" % rel)
    target = repo_path(rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as handle:  # 二进制写入：不做行尾转换
        handle.write(raw)


def line_terminator(raw: bytes) -> str:
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    if crlf and not lf:
        return "CRLF"
    if lf and not crlf:
        return "LF"
    if not crlf and not lf:
        return "none"
    return "mixed"


def _json_pointer(parts: Sequence[Any]) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def _added_pointers(raw: Any, normalized: Any, parts: Tuple[Any, ...] = ()) -> List[str]:
    """normalize_contract 补上的键（原始 JSON 中缺失、规范化后存在）的 JSON Pointer。"""
    out: List[str] = []
    if isinstance(raw, dict) and isinstance(normalized, dict):
        for key, value in normalized.items():
            if key not in raw:
                out.append(_json_pointer(parts + (key,)))
            else:
                out.extend(_added_pointers(raw[key], value, parts + (key,)))
    elif isinstance(raw, list) and isinstance(normalized, list) and len(raw) == len(normalized):
        for index, (a, b) in enumerate(zip(raw, normalized)):
            out.extend(_added_pointers(a, b, parts + (index,)))
    return out


def _legacy_text(raw: bytes) -> str:
    """复现 Path.read_text(encoding="utf-8")：严格 UTF-8（不去 BOM），通用换行（CRLF/CR → LF）。"""
    return io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8", newline=None).read()


#: 旧实现的 json.loads 接受 NaN/Infinity/-Infinity，锁定预期却按严格 JSON（allow_nan=False）序列化。投影中的非有限
#: 浮点数写成下面的固定字符串（收尾轮 D-20 用例首次出现；此前的用例没有非有限数，投影不变）。
NON_FINITE_MARKERS = {"nan": "<non-finite:NaN>", "inf": "<non-finite:Infinity>", "-inf": "<non-finite:-Infinity>"}


def _encode_non_finite(value: Any) -> Any:
    """把投影中的非有限浮点数替换为 NON_FINITE_MARKERS 中的字符串；其他值原样返回（容器逐层复制）。"""
    if type(value) is float and not math.isfinite(value):
        return NON_FINITE_MARKERS["nan" if math.isnan(value) else ("inf" if value > 0 else "-inf")]
    if isinstance(value, dict):
        return {key: _encode_non_finite(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):  # 元组与列表序列化为同一 JSON 数组
        return [_encode_non_finite(item) for item in value]
    return value


def _clean_env(extra: Optional[Dict[str, str]] = None, remove: Sequence[str] = ()) -> Dict[str, str]:
    """子进程环境：继承当前环境（不读取、不输出其值），去掉 Git 重定向变量与指定变量。"""
    git_redirect = {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_PREFIX"}
    drop = {name.upper() for name in remove} | git_redirect
    env = {k: v for k, v in os.environ.items() if k.upper() not in drop}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra or {})
    return env


# ---------------------------------------------------------------------------
# 旧实现加载（只读调用）
# ---------------------------------------------------------------------------

#: 按字节摘要缓存的已加载模块（同一份字节只编译执行一次）。
_LEGACY_MODULES: Dict[str, types.ModuleType] = {}


def load_legacy_pi_dispatch(*, require_locked_bytes: bool = True) -> types.ModuleType:
    """加载旧调度器的固定源码，从读到的同一份字节编译执行。

    ``require_locked_bytes=True``（生成预期与 ``--check`` 的默认）从
    ``SOURCE_REVISION`` 的 Git blob 读取；这样后续版本可以继续演进工作区
    调度器，而旧投影仍由不可变的 a4fa199 源码生成。``False``（只供差分
    测试）读取当前工作区字节，用来比较当前实现与锁定预期的 cases。
    """
    path = repo_path(LEGACY_PI_DISPATCH_PATH)
    if require_locked_bytes:
        try:
            raw = _git_blob_bytes("%s:%s" % (SOURCE_REVISION, LEGACY_PI_DISPATCH_PATH), command="show")
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            raise RuntimeError("无法读取 %s 的固定旧调度器源码：%s" % (SOURCE_REVISION[:12], exc)) from exc
    else:
        raw = path.read_bytes()
    digest = sha256_hex(raw)
    if require_locked_bytes and digest != LEGACY_PI_DISPATCH_SHA256:
        raise RuntimeError("%s 的旧调度器 blob 摘要不匹配（sha256=%s），不能用来生成旧预期" % (SOURCE_REVISION[:12], digest))
    cached = _LEGACY_MODULES.get(digest)
    if cached is not None:
        return cached
    name = "codekit01_legacy_pi_dispatch"
    if digest != LEGACY_PI_DISPATCH_SHA256:
        name += "_" + digest[:12]
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    _LEGACY_MODULES[digest] = module
    return module


# ---------------------------------------------------------------------------
# 合同投影
# ---------------------------------------------------------------------------

CONTRACT_PROJECTION_NOTES = {
    "included": [
        "read：按 validate_plan 第 3–4 步的读法（严格 UTF-8、不去 BOM、通用换行，json.loads 的 ValueError 记为"
        "“JSON 合同解析失败：…”）得到的读取结果",
        "normalize_contract：规范化后的完整合同，以及规范化补上的键（JSON Pointer）",
        "validate_contract：是否返回合同、错误列表、警告列表（原文、原顺序）",
        "inprocess_validate_plan：validate_plan 第 3–6 步在进程内的组合结果（错误、警告、是否返回合同）",
        "cli_validate_temp_repo：在固定构造的临时 Git 仓库中运行旧 CLI `validate` 的退出码、stdout、stderr",
        "derive_contract_json：由 Markdown 派生的 JSON、问题列表，以及派生 JSON 与同一 Markdown 的 validate_contract 结果",
        "非有限数的表示：旧实现接受的 NaN、Infinity、-Infinity 在进程内投影中写成字符串 <non-finite:NaN>、"
        "<non-finite:Infinity>、<non-finite:-Infinity>（锁定预期按严格 JSON 序列化；收尾轮 D-20 用例首次出现）",
    ],
    "excluded": [
        {"field": "validate_plan 第 7–8 步（进程内视图）",
         "reason": "base_sha 是否存在、基线中的 AGENTS.md、HEAD 与 base 的关系、Repository facts 文件是否存在、"
                   ".agent/runs 是否被忽略，取决于运行时所在仓库而不是 fixture 字节；进程内视图不执行，"
                   "改由 cli_validate_temp_repo 在固定构造的临时仓库中观察"},
        {"field": "base_sha 存在时才执行的分支（AGENTS.md 警告、HEAD NOTE/WARN、Repository facts 警告）",
         "reason": "全部 fixture 的 base_sha 都是虚构值或格式不合法，在临时仓库中不存在，这些分支没有被执行；"
                   "要覆盖它们须像 tests/test_dispatch.py 那样改写 base_sha，会改变 fixture 字节，本投影不做"},
        {"field": "cli_validate_temp_repo 的换行形式",
         "reason": "Windows 控制台输出的 CRLF 统一为 LF 后记录（机器相关的输出形式，不是判断内容）"},
        {"field": "cli_validate_temp_repo 中 Python traceback 的调用栈",
         "reason": "含本机绝对路径（机器定位）；出现 traceback 时只记录最后一行异常类型与消息。P3 的用例都没有出现；"
                   "收尾轮新增的 json-deep-nesting（RecursionError）与 md-invalid-utf8（UnicodeDecodeError）出现，"
                   "只记录了最后一行"},
        {"field": "derive-json CLI 的写文件、--title、--force 与长标题 NOTE",
         "reason": "只在进程内调用 derive_contract_json（title=None），不写文件；CLI 写入路径不在本投影"},
    ],
    "temp_repo_construction": [
        "git -c init.defaultBranch=main init；GIT_CONFIG_NOSYSTEM=1，GIT_CONFIG_GLOBAL 指向空文件",
        "本地配置 user.name/user.email、core.autocrlf=false、core.excludesFile 指向空文件、commit.gpgsign=false",
        "提交 .gitignore（内容 `.agent/runs/`）与 README.md；不写 .agent/dispatch.config.json",
        "每个用例把 md/json 原字节写到 .agent/plans/<plan_key>.md/.json 后运行 "
        "`python scripts/pi_dispatch.py --repo <临时仓库> validate <plan_key>`",
        "输出中不得出现临时仓库的 HEAD（生成时断言），以保证结果与临时仓库的提交无关",
    ],
}


def _validate_view(pd: types.ModuleType, md_text: str, raw: Any, plan_key: str) -> Dict[str, Any]:
    contract, errors, warnings = pd.validate_contract(md_text, raw, plan_key)
    return {"contract_returned": contract is not None, "errors": list(errors), "warnings": list(warnings)}


def project_contract_inprocess(md_raw: bytes, json_raw: bytes, plan_key: str,
                               pd: Optional[types.ModuleType] = None) -> Dict[str, Any]:
    """合同的进程内投影：只调用旧实现的纯函数，不需要仓库。pd 为 None 时加载 a4fa199 字节的旧实现。"""
    if pd is None:
        pd = load_legacy_pi_dispatch()
    result: Dict[str, Any] = {}
    read: Dict[str, Any] = {"md_decode_error": None, "json_decode_or_parse_error": None}
    md_text: Optional[str] = None
    try:
        md_text = _legacy_text(md_raw)
    except UnicodeDecodeError as exc:
        # 旧 validate_plan 不捕获：CLI 以 traceback 退出 1。
        read["md_decode_error"] = "%s: %s" % (type(exc).__name__, exc)
    raw: Any = None
    json_ok = False
    json_uncaught: Optional[str] = None
    json_text: Optional[str] = None
    try:
        json_text = _legacy_text(json_raw)
        raw = json.loads(json_text)
        json_ok = True
    except ValueError as exc:  # 与 validate_plan 相同：UnicodeDecodeError 也是 ValueError
        read["json_decode_or_parse_error"] = "JSON 合同解析失败：%s" % exc
    except RecursionError as exc:  # 旧实现不捕获（CLI traceback 退出 1）
        json_uncaught = type(exc).__name__
        read["json_decode_or_parse_error"] = "未捕获：%s" % json_uncaught
    result["read"] = read

    if json_ok and isinstance(raw, dict):
        try:
            normalized = pd.normalize_contract(raw)
            result["normalize_contract"] = {"status": "ok", "contract": normalized,
                                            "defaults_added": sorted(_added_pointers(raw, normalized))}
        except (TypeError, ValueError) as exc:
            result["normalize_contract"] = {"status": "exception", "exception": type(exc).__name__,
                                            "contract": None, "defaults_added": None}
    else:
        reason = "json_not_parsed" if not json_ok else "json_top_level_not_object"
        result["normalize_contract"] = {"status": "not_applicable:" + reason, "contract": None,
                                        "defaults_added": None}

    if md_text is not None and json_ok:
        result["validate_contract"] = _validate_view(pd, md_text, raw, plan_key)
    else:
        result["validate_contract"] = None

    # validate_plan 第 3–6 步：解析失败立即返回（不产生不可见字符警告）；否则 validate_contract 之后追加
    # Markdown 与 JSON 的不可见字符警告。第 7–8 步不在进程内执行（见 CONTRACT_PROJECTION_NOTES）。
    if md_text is None or json_uncaught:
        inprocess = {"outcome": "uncaught_exception",
                     "exception": "UnicodeDecodeError" if md_text is None else json_uncaught,
                     "contract_returned": False, "errors": [], "warnings": []}
    elif not json_ok:
        inprocess = {"outcome": "returned", "contract_returned": False,
                     "errors": [read["json_decode_or_parse_error"]], "warnings": []}
    else:
        view = result["validate_contract"]
        warnings = list(view["warnings"])
        warnings += pd.invisible_char_warnings(md_text, "Markdown")
        warnings += pd.invisible_char_warnings(json_text or "", "JSON")
        inprocess = {"outcome": "returned", "contract_returned": view["contract_returned"],
                     "errors": list(view["errors"]), "warnings": warnings}
    inprocess["excluded_steps"] = ["validate_plan 第 7 步（base_sha 仓库核验及其后的提示）",
                                   "validate_plan 第 8 步（.agent/runs 是否被忽略）"]
    result["inprocess_validate_plan"] = inprocess

    if md_text is not None:
        derived, problems = pd.derive_contract_json(md_text)
        result["derive_contract_json"] = {
            "contract": derived,
            "problems": list(problems),
            "validate_contract_on_derived": _validate_view(pd, md_text, derived, plan_key),
            "derived_equals_parsed_json": (derived == raw) if json_ok else None,
        }
    else:
        result["derive_contract_json"] = None
    return _encode_non_finite(result)


def _git(args: Sequence[str], cwd: Path, env: Dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + list(args), cwd=str(cwd), env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def _make_temp_repo(root: Path) -> Tuple[Path, Dict[str, str], str]:
    empty = root / "empty-config"
    empty.write_bytes(b"")
    env = _clean_env({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(empty),
                      "GIT_AUTHOR_DATE": "2026-09-25T00:00:00+00:00",
                      "GIT_COMMITTER_DATE": "2026-09-25T00:00:00+00:00",
                      "GIT_TERMINAL_PROMPT": "0"})
    repo = root / "repo"
    repo.mkdir()
    _git(["-c", "init.defaultBranch=main", "init", "-q"], repo, env)
    for key, value in (("user.name", "codekit01"), ("user.email", "codekit01@example.invalid"),
                       ("core.autocrlf", "false"), ("core.excludesFile", str(empty)),
                       ("commit.gpgsign", "false")):
        _git(["config", key, value], repo, env)
    (repo / ".gitignore").write_bytes(b".agent/runs/\n")
    (repo / "README.md").write_bytes(b"# codekit01 legacy temp repo\n")
    _git(["add", ".gitignore", "README.md"], repo, env)
    _git(["commit", "-q", "-m", "init"], repo, env)
    head = _git(["rev-parse", "HEAD"], repo, env).stdout.decode("ascii").strip()
    (repo / ".agent" / "plans").mkdir(parents=True)
    return repo, env, head


def _normalize_cli_text(raw: bytes) -> str:
    return raw.decode("utf-8", "replace").replace("\r\n", "\n")


def _cli_stream_view(raw: bytes) -> Any:
    text = _normalize_cli_text(raw)
    if "Traceback (most recent call last)" in text:
        last = [line for line in text.splitlines() if line.strip()][-1]
        return {"traceback_last_line": last}
    return text


def project_contracts_cli_temp_repo(cases: Sequence[Tuple[str, str, bytes, bytes]], *,
                                   require_locked_bytes: bool = True) -> Dict[str, Dict[str, Any]]:
    """在自建临时 Git 仓库中逐个运行旧 CLI `validate`。cases: (case_id, plan_key, md 字节, json 字节)。

    require_locked_bytes 的含义同 load_legacy_pi_dispatch。
    """
    pd_path = repo_path(LEGACY_PI_DISPATCH_PATH)
    out: Dict[str, Dict[str, Any]] = {}
    root = _make_owned_tempdir("codekit01-legacy-repo-")
    source_root: Optional[Path] = None
    try:
        repo, env, head = _make_temp_repo(root)
        command_path = pd_path
        if require_locked_bytes:
            # The live dispatcher is a successor. Materialize only the
            # immutable historical blob inside our owned temp area.
            source_root = _make_owned_tempdir("codekit01-legacy-dispatch-")
            command_path = source_root / "pi_dispatch.py"
            command_path.write_bytes(_git_blob_bytes(
                "%s:%s" % (SOURCE_REVISION, LEGACY_PI_DISPATCH_PATH), command="show"))
            if sha256_hex(command_path.read_bytes()) != LEGACY_PI_DISPATCH_SHA256:
                raise RuntimeError("%s 的旧调度器 blob 摘要不匹配" % SOURCE_REVISION[:12])
        plans = repo / ".agent" / "plans"
        for case_id, plan_key, md_raw, json_raw in cases:
            for leftover in plans.iterdir():
                leftover.unlink()
            (plans / (plan_key + ".md")).write_bytes(md_raw)
            (plans / (plan_key + ".json")).write_bytes(json_raw)
            proc = subprocess.run([sys.executable, str(command_path), "--repo", str(repo), "validate", plan_key],
                                  cwd=str(repo), env=env, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
            stdout = _normalize_cli_text(proc.stdout)
            stderr = _normalize_cli_text(proc.stderr)
            for text in (stdout, stderr):
                if head[:12] in text or str(root) in text or os.path.realpath(str(root)) in text:
                    raise AssertionError("CLI 输出含临时仓库的提交或路径，结果与临时仓库相关：%s" % case_id)
            out[case_id] = {"argv": ["python", LEGACY_PI_DISPATCH_PATH, "--repo", "<临时仓库>", "validate",
                                     plan_key],
                            "exit_code": proc.returncode,
                            "stdout": _cli_stream_view(proc.stdout),
                            "stderr": _cli_stream_view(proc.stderr)}
    finally:
        if source_root is not None:
            _rmtree(source_root)
        _rmtree(root)
    return out


def _force_remove(func: Callable[..., Any], path: str, _exc: Any) -> None:
    os.chmod(path, 0o700)
    func(path)


# ---------------------------------------------------------------------------
# 自建临时目录与删除前的归属核对（文档 8.4；acceptance.md R-12）
# ---------------------------------------------------------------------------

#: 本模块建立临时目录时允许的目录名前缀；_rmtree 只删除名称以其中之一开头的目录。后两个供
#: tests/test_codekit01_fixtures.py 借用同一套建立与归属核对（生成护栏的链接实测、归属核对的对照用例），
#: 该文件不另写递归删除。
OWNED_TEMP_PREFIXES = ("codekit01-legacy-repo-", "codekit01-legacy-work-", "codekit01-legacy-stub-", "codekit01-legacy-dispatch-",
                       "codekit01-fixtures-guard-", "codekit01-fixtures-cleanup-")
#: 所有权标记文件名。内容是建立目录时生成的随机令牌，令牌只保存在本进程内（_OWNED_TEMP_DIRS），不能从磁盘伪造。
OWNER_MARKER_NAME = ".codekit01-legacy-owner"
_OWNER_TOKEN_BYTES = 32
#: 本进程建立、尚未删除的目录：规范化真实路径 -> 令牌（十六进制文本）。
_OWNED_TEMP_DIRS: Dict[str, str] = {}
_FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class CleanupRefused(RuntimeError):
    """递归删除前的归属核对失败：不删除任何东西（文档 8.4“不确定时不递归删除”）。"""


def _path_segments(path: str) -> Tuple[str, ...]:
    """按路径分段比较用的形式：逐段 normcase（Windows 上不区分大小写、统一分隔符）。"""
    return tuple(os.path.normcase(part) for part in Path(path).parts)


def _owned_key(real: str) -> str:
    return "/".join(_path_segments(real))


def _is_link_like(path: str) -> bool:
    """符号链接、目录联接（junction）或其他重解析点。"""
    if os.path.islink(path):
        return True
    isjunction = getattr(os.path, "isjunction", None)
    if isjunction is not None and isjunction(path):
        return True
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & _FILE_ATTRIBUTE_REPARSE_POINT)


def _make_owned_tempdir(prefix: str) -> Path:
    """在系统临时目录下建立本模块的临时目录（tempfile.mkdtemp），写入所有权标记并登记令牌。
    用完必须交给 _rmtree（它先核对归属再删除）。"""
    if prefix not in OWNED_TEMP_PREFIXES:
        raise ValueError("未登记的临时目录前缀：%s" % prefix)
    path = tempfile.mkdtemp(prefix=prefix)
    token = secrets.token_hex(_OWNER_TOKEN_BYTES)
    with open(os.path.join(path, OWNER_MARKER_NAME), "x", encoding="ascii", newline="") as handle:  # 独占创建
        handle.write(token)
    _OWNED_TEMP_DIRS[_owned_key(os.path.realpath(path))] = token
    return Path(path)


def ownership_problem(path: Any) -> Optional[str]:
    """path 能否作为本模块自建的临时目录递归删除：可以时返回 None，否则返回原因（不含令牌）。

    同时核对（文档 8.4：只凭名称、字符串包含 tmp 或一个可伪造的标记都不充分）：
    1. path 本身不是链接或重解析点，且是目录；
    2. 真实路径的父目录就是 tempfile.gettempdir() 的真实路径（逐段比较，不做字符串前缀比较）；
    3. 目录名以 OWNED_TEMP_PREFIXES 之一开头；
    4. 真实路径已由本进程的 _make_owned_tempdir 登记；
    5. 目录内的所有权标记是普通文件（不是链接），内容与登记的随机令牌相同。
    """
    raw = os.fspath(path)
    if _is_link_like(raw):
        return "目标本身是链接或重解析点"
    if not os.path.isdir(raw):
        return "目标不是目录"
    real = os.path.realpath(raw)
    segments = _path_segments(real)
    temp_segments = _path_segments(os.path.realpath(tempfile.gettempdir()))
    if len(segments) != len(temp_segments) + 1 or segments[:-1] != temp_segments:
        return "真实路径的父目录不是系统临时目录"
    if not os.path.basename(real).startswith(OWNED_TEMP_PREFIXES):
        return "目录名前缀不属于本工具"
    token = _OWNED_TEMP_DIRS.get(_owned_key(real))
    if token is None:
        return "该目录不是本进程建立并登记的临时目录"
    marker = os.path.join(real, OWNER_MARKER_NAME)
    if _is_link_like(marker) or not os.path.isfile(marker):
        return "所有权标记缺失，或不是普通文件"
    try:
        with open(marker, "rb") as handle:
            content = handle.read(_OWNER_TOKEN_BYTES * 2 + 1)
    except OSError:
        return "所有权标记不可读"
    if not hmac.compare_digest(content, token.encode("ascii")):
        return "所有权标记与登记的令牌不符"
    return None


def _rmtree(path: Path) -> None:
    """删除本模块自建的临时目录（只读文件先改权限再删）。归属核对（ownership_problem）不通过时报 CleanupRefused，
    不删除任何东西；通过后按真实路径删除并注销登记。"""
    problem = ownership_problem(path)
    if problem is not None:
        raise CleanupRefused("拒绝递归删除 %s：%s" % (os.fspath(path), problem))
    real = os.path.realpath(os.fspath(path))
    _OWNED_TEMP_DIRS.pop(_owned_key(real), None)
    if sys.version_info >= (3, 12):
        shutil.rmtree(real, onexc=_force_remove)
    else:  # pragma: no cover - Python 3.10/3.11
        shutil.rmtree(real, onerror=_force_remove)


def contract_cases() -> List[Dict[str, Any]]:
    """全部合同用例（legacy 原样 + 单一故障负例），含输入 fixture 的路径。"""
    files = {fid: path for fid, _src, path, _d in LEGACY_CONTRACT_FILES}
    cases: List[Dict[str, Any]] = []
    for case_id, plan_key, md_id, json_id, note in LEGACY_CONTRACT_CASES:
        cases.append({"case_id": case_id, "plan_key": plan_key, "note": note,
                      "md": {"fixture_id": md_id, "path": files[md_id]},
                      "json": {"fixture_id": json_id, "path": files[json_id]},
                      "fault": None, "derived_from": None})
    base = next(c for c in cases if c["case_id"] == NEGATIVE_CONTRACT_BASE_CASE)
    for slug, target, _transform, fault in NEGATIVE_CONTRACT_VARIANTS:
        case = {"case_id": negative_contract_fixture_id(slug), "plan_key": NEGATIVE_CONTRACT_PLAN_KEY,
                "note": "单一故障负例", "md": dict(base["md"]), "json": dict(base["json"]),
                "fault": fault, "derived_from": base[target]["fixture_id"]}
        case[target] = {"fixture_id": negative_contract_fixture_id(slug), "path": negative_contract_path(slug, target)}
        cases.append(case)
    return cases


def compute_expected_contracts(*, require_locked_bytes: bool = True) -> Dict[str, Any]:
    """合同预期。默认只接受 a4fa199 字节的旧实现（生成预期）；差分测试传 require_locked_bytes=False，
    只比较返回值的 cases（头部的 legacy_implementation 是锁定时的记录，不是按当前字节计算的）。"""
    pd = load_legacy_pi_dispatch(require_locked_bytes=require_locked_bytes)
    cases = contract_cases()
    loaded = []
    for case in cases:
        md_raw = read_fixture(case["md"]["path"])
        json_raw = read_fixture(case["json"]["path"])
        loaded.append((case, md_raw, json_raw))
    cli = project_contracts_cli_temp_repo([(c["case_id"], c["plan_key"], m, j) for c, m, j in loaded],
                                          require_locked_bytes=require_locked_bytes)
    records: Dict[str, Any] = {}
    for case, md_raw, json_raw in loaded:
        legacy = project_contract_inprocess(md_raw, json_raw, case["plan_key"], pd)
        legacy["cli_validate_temp_repo"] = cli[case["case_id"]]
        records[case["case_id"]] = {
            "plan_key": case["plan_key"],
            "note": case["note"],
            "fault": case["fault"],
            "derived_from": case["derived_from"],
            "inputs": {
                "md": dict(case["md"], sha256=sha256_hex(md_raw), line_terminator=line_terminator(md_raw),
                           utf8_bom=md_raw.startswith(UTF8_BOM)),
                "json": dict(case["json"], sha256=sha256_hex(json_raw), line_terminator=line_terminator(json_raw),
                             utf8_bom=json_raw.startswith(UTF8_BOM)),
            },
            "legacy": legacy,
        }
    return {
        "schema_version": 1,
        "record_type": "codekit01-legacy-expected",
        "expected_kind": "legacy-contracts",
        "projection_revision": PROJECTION_REVISION,
        "source_revision": SOURCE_REVISION,
        "legacy_implementation": {"path": LEGACY_PI_DISPATCH_PATH, "sha256": LEGACY_PI_DISPATCH_SHA256,
                                  "git_blob": LEGACY_PI_DISPATCH_BLOB, "tool_version": pd.TOOL_VERSION,
                                  "functions": ["normalize_contract", "validate_contract", "invisible_char_warnings",
                                                "derive_contract_json", "main（validate 子命令，临时仓库）"]},
        "generator": {"path": "tests/codekit01_legacy.py", "write_command": WRITE_COMMAND,
                      "check_command": CHECK_COMMAND},
        "locked_with": LOCKED_WITH,
        "projection": CONTRACT_PROJECTION_NOTES,
        "new_strict_verdict": "不在本文件：新严格入口的判断由 tests/codekit01_legacy.py 的 new_strict_verdict 单独计算，"
                              "依赖 codekit.protocols.strict_json_loads，不属于旧预期",
        "cases": records,
    }


# ---------------------------------------------------------------------------
# 事件投影
# ---------------------------------------------------------------------------

EVENT_SUMMARY_INCLUDED = (
    "lines", "event_counts", "parse_error_lines", "truncated", "session_header", "terminal_event", "complete",
    "final_stop_reason", "final_error", "requested_model", "actual_models", "response_models",
    "provider_thinking_levels", "thinking_evidence", "model_match", "assistant_messages", "tool_calls",
    "tool_errors", "auto_retries", "compactions", "system_prompt_sections", "usage", "cost", "stderr_flags",
    "problems", "ok",
)
EVENT_SUMMARY_EXCLUDED = {
    "shell_commands": "复审证据（命令原文），依赖执行上下文，不产生 problem，不属于完整性/模型/用量判断",
    "suspicious_commands": "复审证据（可疑命令），不产生 problem",
    "temp_path_uses": "复审证据（临时路径使用），按 work_dir 掩码，属于机器定位相关内容，不产生 problem",
    "temp_path_use_count": "同 temp_path_uses",
    "cache_dir_cleanups": "复审证据（缓存目录清理），不产生 problem",
    "outside_worktree_paths": "复审证据（工作副本外路径及其 exists），依赖 work_dir 与本机文件系统（机器定位），不产生 problem",
    "own_run_paths": "复审证据（运行目录内路径），依赖 allowed_outside（机器定位），不产生 problem",
    "ambiguity_mention_count": "歧义提示，依赖 plan_text 调用参数，只进入 summary.md 与 G3 备注，不产生 problem",
    "ambiguity_domain_words": "同 ambiguity_mention_count",
    "ambiguity_mentions": "同 ambiguity_mention_count",
}
EVENT_PROJECTION_NOTES = {
    "call": "summarize_events(<fixture 路径>, <空临时目录>, REQUESTED_EXECUTOR, stderr_path=None, "
            "expects_settled=<true/false/null>, allowed_outside=(), plan_text=\"\")",
    "primary_expects_settled": "true：stub 的 --version 为 0.87.0 ≥ 0.80.4，旧 run 按 _expects_settled 传 True；"
                               "false/null 两个变体只用来锁定旧实现的另外两个分支（recover/smoke/旧 run.json 可能进入）",
    "included": list(EVENT_SUMMARY_INCLUDED),
    "excluded": [{"field": k, "reason": v} for k, v in sorted(EVENT_SUMMARY_EXCLUDED.items())] + [
        {"field": "summarize_events 的第二个返回值（最终 assistant 文本）",
         "reason": "属于执行报告解析（另一旧函数），不在本投影；它对 problems 的影响（文本工具调用）已随 problems 保留"},
        {"field": "stderr（stderr_flags 的输入）",
         "reason": "未采集 stub 的 stderr；stub 不模拟 stderr 警告模式，stderr_flags 在本投影中恒为空列表"},
    ],
    "token_zero_semantics": "旧实现 token 缺失时输出 0 而不是 null；usage 中的 0 可能表示未知（例如 startfail）。"
                            "cost.total 为 null、status=unknown 才表示费用未知",
}


def project_event_stream(events_path: Path, work_dir: Path, expects_settled: Optional[bool],
                         pd: Optional[types.ModuleType] = None) -> Dict[str, Any]:
    if pd is None:
        pd = load_legacy_pi_dispatch()
    summary, _final_text = pd.summarize_events(events_path, work_dir, dict(REQUESTED_EXECUTOR),
                                               stderr_path=None, expects_settled=expects_settled,
                                               allowed_outside=(), plan_text="")
    keys = set(summary)
    expected_keys = set(EVENT_SUMMARY_INCLUDED) | set(EVENT_SUMMARY_EXCLUDED)
    if keys != expected_keys:
        raise AssertionError("summarize_events 的字段与投影定义不符：多 %s，少 %s"
                             % (sorted(keys - expected_keys), sorted(expected_keys - keys)))
    return {key: summary[key] for key in EVENT_SUMMARY_INCLUDED}


def event_cases() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for slug, env, exit_code, description in STUB_SCENARIOS:
        cases.append({"case_id": stub_fixture_id(slug), "fixture_id": stub_fixture_id(slug),
                      "path": stub_fixture_path(slug), "description": description,
                      "generation": {"kind": "stub-run", "env": dict(env), "stub_exit_code": exit_code,
                                     "source_test_id": stub_source_test_id(env)},
                      "fault": None, "derived_from": None})
    for slug, source_slug, _transform, fault in NEGATIVE_EVENT_VARIANTS:
        cases.append({"case_id": negative_event_fixture_id(slug), "fixture_id": negative_event_fixture_id(slug),
                      "path": negative_event_path(slug), "description": fault,
                      "generation": {"kind": "single-fault-derivation", "derived_from": stub_fixture_id(source_slug)},
                      "fault": fault, "derived_from": stub_fixture_id(source_slug)})
    return cases


def compute_expected_events(*, require_locked_bytes: bool = True) -> Dict[str, Any]:
    """事件预期。require_locked_bytes 的含义同 compute_expected_contracts。"""
    pd = load_legacy_pi_dispatch(require_locked_bytes=require_locked_bytes)
    records: Dict[str, Any] = {}
    work = _make_owned_tempdir("codekit01-legacy-work-")
    try:
        for case in event_cases():
            raw = read_fixture(case["path"])
            summaries = {}
            for label, value in (("expects_settled=true", True), ("expects_settled=false", False),
                                 ("expects_settled=null", None)):
                summaries[label] = project_event_stream(repo_path(case["path"]), work, value, pd)
            records[case["case_id"]] = {
                "description": case["description"],
                "fault": case["fault"],
                "derived_from": case["derived_from"],
                "generation": case["generation"],
                "inputs": {"events": {"fixture_id": case["fixture_id"], "path": case["path"],
                                      "sha256": sha256_hex(raw), "line_terminator": line_terminator(raw),
                                      "bytes": len(raw)}},
                "requested_executor": dict(REQUESTED_EXECUTOR),
                "primary": "expects_settled=true",
                "summaries": summaries,
            }
    finally:
        _rmtree(work)
    return {
        "schema_version": 1,
        "record_type": "codekit01-legacy-expected",
        "expected_kind": "legacy-events",
        "projection_revision": PROJECTION_REVISION,
        "source_revision": SOURCE_REVISION,
        "legacy_implementation": {"path": LEGACY_PI_DISPATCH_PATH, "sha256": LEGACY_PI_DISPATCH_SHA256,
                                  "git_blob": LEGACY_PI_DISPATCH_BLOB, "tool_version": pd.TOOL_VERSION,
                                  "functions": ["summarize_events"]},
        "stub": {"path": LEGACY_STUB_PATH, "sha256": LEGACY_STUB_SHA256,
                 "argv_template": stub_argv_template(pd),
                 "cwd_rule": {"revision": STUB_CWD_RULE_REVISION, "placeholder": STUB_CWD_PLACEHOLDER,
                              "description": "session 事件的 cwd（生成时临时目录的绝对路径）替换为固定占位值"}},
        "generator": {"path": "tests/codekit01_legacy.py", "write_command": WRITE_COMMAND,
                      "check_command": CHECK_COMMAND},
        "locked_with": LOCKED_WITH,
        "projection": EVENT_PROJECTION_NOTES,
        "cases": records,
    }


# ---------------------------------------------------------------------------
# stub 运行与 cwd 占位
# ---------------------------------------------------------------------------

def stub_argv_template(pd: Optional[types.ModuleType] = None) -> List[str]:
    """与 pi_dispatch cmd_run 组装的命令同形（scripts/pi_dispatch.py:3290-3294）；可执行文件与 @ 路径用占位表示。"""
    if pd is None:
        pd = load_legacy_pi_dispatch()
    return (["<python>", LEGACY_STUB_PATH, "--provider", REQUESTED_EXECUTOR["provider"],
             "--model", REQUESTED_EXECUTOR["model"], "--thinking", REQUESTED_EXECUTOR["thinking"], "--no-session"]
            + list(pd.RESOURCE_FLAGS)
            + ["--tools", ",".join(REQUESTED_TOOLS), "--mode", "json", "@<run_dir>/plan.md",
               "@<run_dir>/instruction.md"])


def _replace_session_cwd(stdout: bytes, temp_root: Path) -> Tuple[bytes, Dict[str, Any]]:
    lines = _split_lines_keepends(stdout)
    first = json.loads(lines[0].decode("utf-8"))
    if first.get("type") != "session" or not isinstance(first.get("cwd"), str):
        raise AssertionError("stub 的第一行不是带 cwd 的 session 事件")
    encoded = json.dumps(first["cwd"]).encode("ascii")  # 与 stub 的 json.dumps 默认参数一致
    needle = b'"cwd": ' + encoded
    if lines[0].count(needle) != 1 or stdout.count(encoded[1:-1]) != 1:
        raise AssertionError("cwd 在 stub 输出中出现的次数不是 1")
    replacement = b'"cwd": ' + json.dumps(STUB_CWD_PLACEHOLDER).encode("ascii")
    new_first = lines[0].replace(needle, replacement, 1)
    result = new_first + b"".join(lines[1:])
    forms = {str(temp_root), os.path.realpath(str(temp_root))}
    for form in forms:
        for variant in (form, json.dumps(form)[1:-1], form.replace("\\", "/")):
            if variant.encode("utf-8", "replace") in result:
                raise AssertionError("替换后仍含临时目录路径")
    return result, {"original_length": len(stdout), "redacted_length": len(result),
                    "length_changed": len(stdout) != len(result)}


def run_stub(env_extra: Dict[str, str], *, require_locked_bytes: bool = True) -> Tuple[bytes, int, Dict[str, Any]]:
    """在自建临时目录中按 cmd_run 的参数形状运行 tests/stub_pi.py，返回（已替换 cwd 的 stdout 字节、退出码、替换记录）。

    stub 的字节必须等于 a4fa199。scripts/pi_dispatch.py 只用来取 RESOURCE_FLAGS（参数形状）：
    require_locked_bytes=True（生成）要求它也等于 a4fa199；False（默认测试的重跑核对）按当前字节取。
    """
    stub = repo_path(LEGACY_STUB_PATH)
    if sha256_hex(stub.read_bytes()) != LEGACY_STUB_SHA256:
        raise RuntimeError("tests/stub_pi.py 与 a4fa199 的字节不同")
    pd = load_legacy_pi_dispatch(require_locked_bytes=require_locked_bytes)
    root = _make_owned_tempdir("codekit01-legacy-stub-")
    try:
        work = root / "wt"
        run_dir = root / "run"
        work.mkdir()
        run_dir.mkdir()
        # stub 只检查附件是否同时含 “TASK:” 与 “执行说明”，内容不进入事件流。
        (run_dir / "plan.md").write_bytes(read_fixture(FIXTURE_DIR + "/legacy/contracts/normalize-query.v1.md"))
        (run_dir / "instruction.md").write_bytes("# 执行说明\n\n（codekit01 legacy fixture 生成用占位说明）\n"
                                                 .encode("utf-8"))
        argv = ([sys.executable, str(stub), "--provider", REQUESTED_EXECUTOR["provider"],
                 "--model", REQUESTED_EXECUTOR["model"], "--thinking", REQUESTED_EXECUTOR["thinking"],
                 "--no-session"] + list(pd.RESOURCE_FLAGS)
                + ["--tools", ",".join(REQUESTED_TOOLS), "--mode", "json",
                   "@" + str(run_dir / "plan.md"), "@" + str(run_dir / "instruction.md")])
        env = _clean_env(env_extra, remove=_STUB_ENV_REMOVE)
        proc = subprocess.run(argv, cwd=str(work), env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        redacted, record = _replace_session_cwd(proc.stdout, root)
        return redacted, proc.returncode, record
    finally:
        _rmtree(root)


# ---------------------------------------------------------------------------
# fixture 生成
# ---------------------------------------------------------------------------

def _git_blob_bytes(rev_path: str, *, command: str) -> bytes:
    env = _clean_env({"GIT_TERMINAL_PROMPT": "0"})
    args = ["show", rev_path] if command == "show" else ["cat-file", "blob", rev_path]
    return _git(args, REPO_ROOT, env).stdout


def legacy_contract_source_report() -> List[Dict[str, Any]]:
    """核对每个 legacy 合同：a4fa199 的 blob 字节、工作区字节与 fixture 字节。"""
    report = []
    for fid, source, path, _desc in LEGACY_CONTRACT_FILES:
        head = _git_blob_bytes("%s:%s" % (SOURCE_REVISION, source), command="show")
        head_raw = _git_blob_bytes("%s:%s" % (SOURCE_REVISION, source), command="cat-file")
        work = repo_path(source).read_bytes() if repo_path(source).exists() else None
        fixture = repo_path(path).read_bytes() if repo_path(path).exists() else None
        report.append({"fixture_id": fid, "source_path": source,
                       "head_sha256": sha256_hex(head),
                       "git_show_equals_cat_file": head == head_raw,
                       "worktree_equals_head": work == head,
                       "fixture_equals_head": fixture == head})
    return report


def write_legacy_contracts() -> None:
    """按 a4fa199 的 blob 写 legacy 合同副本。写入前核对：git show 与 git cat-file blob 的字节相同，
    且工作区中的来源文件与该 blob 相同（manifest 条目的描述声称了这一项）。"""
    for _fid, source, path, _desc in LEGACY_CONTRACT_FILES:
        head = _git_blob_bytes("%s:%s" % (SOURCE_REVISION, source), command="show")
        if head != _git_blob_bytes("%s:%s" % (SOURCE_REVISION, source), command="cat-file"):
            raise AssertionError("git show 与 git cat-file blob 的字节不同：%s" % source)
        work = repo_path(source).read_bytes() if repo_path(source).exists() else None
        if work != head:
            raise AssertionError("工作区中的 %s 与 %s 的 blob 字节不同（或文件不存在），不生成副本"
                                 % (source, SOURCE_REVISION[:12]))
        _write_bytes(path, head)


def derive_negative_contracts() -> Dict[str, bytes]:
    files = {fid: path for fid, _src, path, _d in LEGACY_CONTRACT_FILES}
    base_case = next(c for c in LEGACY_CONTRACT_CASES if c[0] == NEGATIVE_CONTRACT_BASE_CASE)
    sources = {"md": read_fixture(files[base_case[2]]), "json": read_fixture(files[base_case[3]])}
    out: Dict[str, bytes] = {}
    for slug, target, transform, _fault in NEGATIVE_CONTRACT_VARIANTS:
        out[negative_contract_path(slug, target)] = transform(sources[target])
    return out


def derive_negative_events() -> Dict[str, bytes]:
    out: Dict[str, bytes] = {}
    for slug, source_slug, transform, _fault in NEGATIVE_EVENT_VARIANTS:
        out[negative_event_path(slug)] = transform(read_fixture(stub_fixture_path(source_slug)))
    return out


def write_stub_events() -> Dict[str, Dict[str, Any]]:
    records: Dict[str, Dict[str, Any]] = {}
    for slug, env, expected_exit, _desc in STUB_SCENARIOS:
        stdout, code, record = run_stub(env)
        if code != expected_exit:
            raise AssertionError("stub 场景 %s 的退出码为 %s，与记录的 %s 不同" % (slug, code, expected_exit))
        if not record["length_changed"]:  # manifest 中 redaction.length_changed 固定写 true
            raise AssertionError("cwd 占位替换没有改变长度：%s" % slug)
        _write_bytes(stub_fixture_path(slug), stdout)
        records[slug] = record
    return records


def stub_redaction_records() -> Dict[str, Dict[str, Any]]:
    """核对锁定的 stub 事件字节中 session.cwd 已是占位值（原路径不保存，长度是否改变只在生成时断言）。"""
    out = {}
    for slug, _env, _code, _desc in STUB_SCENARIOS:
        raw = read_fixture(stub_fixture_path(slug))
        first = json.loads(_split_lines_keepends(raw)[0].decode("utf-8"))
        if first.get("cwd") != STUB_CWD_PLACEHOLDER:
            raise AssertionError("stub fixture %s 的 session.cwd 不是占位值" % slug)
        out[slug] = {"placeholder_present": True}
    return out


# ---------------------------------------------------------------------------
# manifest 的 legacy 条目（整份 manifest.json 由 tests/test_codekit01_fixtures.py 合并生成）
# ---------------------------------------------------------------------------

def _resource(fixture_id: str, path: str, raw: bytes) -> Dict[str, Any]:
    return {"kind": "fixture", "id": fixture_id, "sha256": sha256_hex(raw), "path": path}


#: legacy 条目的 platform_scope（裁决 R-P11，文档 1.1“平台适用性”）。它们的期望都是旧实现的判断
#: （expected.outcome=legacy-judgment），只在 Windows Server 2025 + Python 3.12.10 上锁定：合同投影含临时仓库中旧 CLI
#: 的输出与 Python 的报错原文，stub 流的 CRLF 行尾是 Windows 上的输出。所以如实登记 ["windows"]；这只表示适用范围
#: 已知的平台，不表示其他平台上一定不同（Linux、macOS 为 NOT_RUN）。
LEGACY_PLATFORM_SCOPE = ("windows",)


def _entry(fixture_id: str, origin: Dict[str, Any], redaction: Dict[str, Any], path: str,
           proves: List[str], does_not_prove: List[str], entry: str, expected_ref: Dict[str, Any], *,
           integrity: str = "complete") -> Dict[str, Any]:
    """legacy 条目。R-P11 的五个字段：origin.traceable 恒为 true（legacy 必须可追溯；派生负例可由 derived_from 与
    本模块的确定性变换复现）；redaction.protocol_structure_preserved 由调用方写入 redaction；integrity 默认 complete；
    platform_scope 为 LEGACY_PLATFORM_SCOPE；capture 恒为 null（本清单没有 captured 条目）。"""
    full_origin = {"class": None, "source_revision": None, "source_test_id": None, "source_path": None,
                   "generator_revision": None, "derived_from": None, "fault": None, "description": "",
                   "traceable": True}
    full_origin.update(origin)
    if "protocol_structure_preserved" not in redaction:
        raise AssertionError("redaction 必须写明 protocol_structure_preserved：%s" % fixture_id)
    return {
        "schema_version": 1,
        "record_type": "fixture-manifest",
        "fixture_id": fixture_id,
        "origin": full_origin,
        "representation": "synthetic_fixture",
        "redaction": redaction,
        "resource": _resource(fixture_id, path, read_fixture(path)),
        "proves": proves,
        "does_not_prove": does_not_prove,
        "expected": {"outcome": "legacy-judgment", "code": None, "entry": entry, "expected_ref": expected_ref},
        "integrity": integrity,
        "platform_scope": list(LEGACY_PLATFORM_SCOPE),
        "capture": None,
    }


#: 未脱敏（applied=false）的条目，protocol_structure_preserved 写 null：没有脱敏步骤，谈不上是否保留协议结构。
_NO_REDACTION_CONTRACT = {"applied": False, "rule_revision": None, "length_changed": None,
                          "reason": "仓库内的技能示例/模板，不含凭据或真实用户数据；按 a4fa199 的原字节保存",
                          "protocol_structure_preserved": None}

CONTRACT_ENTRY = "tests/codekit01_legacy.py::compute_expected_contracts（旧实现 scripts/pi_dispatch.py @ a4fa199）"
EVENT_ENTRY = "tests/codekit01_legacy.py::compute_expected_events（旧实现 pi_dispatch.summarize_events @ a4fa199）"


def build_legacy_manifest_entries() -> List[Dict[str, Any]]:
    """legacy 合同、legacy 负例、stub 事件与事件负例的 manifest 条目（顺序固定：合同 6、合同负例 20、stub 流 10、
    事件负例 4，共 40 条）。

    P3 第一部分的 manifest.legacy.draft.json 已并入 manifest.json 并删除。收尾轮按裁决 R-P11 增加五个字段，
    并在合同负例末尾增加 D-20–D-23 的 6 条（此前 32 条）；01 完善再增加合同与事件缺字段各 1 条。
    """
    if set(NEGATIVE_EVENT_INTEGRITY) != {slug for slug, _s, _t, _f in NEGATIVE_EVENT_VARIANTS}:
        raise AssertionError("NEGATIVE_EVENT_INTEGRITY 必须恰好覆盖全部事件负例")
    contracts_ref = _resource(EXPECTED_CONTRACTS_ID, EXPECTED_CONTRACTS_PATH, read_fixture(EXPECTED_CONTRACTS_PATH))
    events_ref = _resource(EXPECTED_EVENTS_ID, EXPECTED_EVENTS_PATH, read_fixture(EXPECTED_EVENTS_PATH))
    entries: List[Dict[str, Any]] = []
    for fid, source, path, desc in LEGACY_CONTRACT_FILES:
        entries.append(_entry(
            fid,
            {"class": "legacy", "source_revision": SOURCE_REVISION, "source_path": source,
             "description": desc + "。字节由 `git show %s:%s` 取得；生成（--write，write_legacy_contracts）与 "
                                   "--check 时核对工作区中的来源文件与该 blob 相同，默认测试只核对 fixture 与 blob 相同。"
                                   "旧预期见 expected_ref 中含本 fixture 的用例。" % (SOURCE_REVISION[:12], source)},
            dict(_NO_REDACTION_CONTRACT), path,
            ["exact_byte_digest", "legacy_source_bytes", "legacy_contract_judgment"],
            ["real_repository_state", "new_protocol_acceptance"],
            CONTRACT_ENTRY, contracts_ref))
    for slug, target, _transform, fault in NEGATIVE_CONTRACT_VARIANTS:
        base_case = next(c for c in LEGACY_CONTRACT_CASES if c[0] == NEGATIVE_CONTRACT_BASE_CASE)
        derived_from = base_case[2] if target == "md" else base_case[3]
        partner = base_case[3] if target == "md" else base_case[2]
        entries.append(_entry(
            negative_contract_fixture_id(slug),
            {"class": "negative", "generator_revision": FIXTURE_GENERATOR_REVISION, "derived_from": derived_from,
             "fault": fault,
             "description": "从 %s 派生的单一故障变体（tests/codekit01_legacy.py 的确定性字节变换）；"
                            "判断时与未修改的 %s 配对，计划标识 %s。"
                            % (derived_from, partner, NEGATIVE_CONTRACT_PLAN_KEY)},
            {"applied": False, "rule_revision": None, "length_changed": None,
             "reason": "由仓库示例派生，不含凭据或真实用户数据", "protocol_structure_preserved": None},
            negative_contract_path(slug, target),
            ["exact_byte_digest", "single_fault_derivation", "legacy_contract_judgment"],
            ["real_repository_state", "new_protocol_acceptance"],
            CONTRACT_ENTRY, contracts_ref))
    for slug, env, exit_code, desc in STUB_SCENARIOS:
        raw = read_fixture(stub_fixture_path(slug))
        entries.append(_entry(
            stub_fixture_id(slug),
            {"class": "legacy", "source_revision": SOURCE_REVISION, "source_test_id": stub_source_test_id(env),
             "source_path": LEGACY_STUB_PATH, "generator_revision": FIXTURE_GENERATOR_REVISION,
             "description": "%s。仓库测试桩 tests/stub_pi.py 在 a4fa199 生成的 stdout 事件字节（不是厂商真实输出）；"
                            "按 pi_dispatch cmd_run 的参数形状直接运行 stub（未经 pi_dispatch run、预检与 worktree），"
                            "进程退出码 %d；行尾 %s（Windows 上 Python 的 stdout 把 LF 转成 CRLF）。"
                            % (desc, exit_code, line_terminator(raw))},
            {"applied": True, "rule_revision": STUB_CWD_RULE_REVISION, "length_changed": True,
             "reason": "session 事件的 cwd 是生成时临时目录的绝对路径（机器定位，含本机账户目录），替换为固定占位值 %s；"
                       "该字段不参与旧实现的完整性、模型、用量判断（summarize_events 只把它抄进 session_header）。"
                       "只替换这一个字符串值，每行仍是同一 JSON 对象、键与其余值不变，所以协议结构保留"
                       % STUB_CWD_PLACEHOLDER,
             "protocol_structure_preserved": True},
            stub_fixture_path(slug),
            ["exact_byte_digest", "stub_output_at_source_revision", "legacy_event_summary_judgment"],
            ["real_cli_compatibility", "vendor_protocol", "legacy_end_to_end_run", "cross_platform_bytes",
             "new_protocol_acceptance"],
            EVENT_ENTRY, events_ref))
    for slug, source_slug, _transform, fault in NEGATIVE_EVENT_VARIANTS:
        entries.append(_entry(
            negative_event_fixture_id(slug),
            {"class": "negative", "generator_revision": FIXTURE_GENERATOR_REVISION,
             "derived_from": stub_fixture_id(source_slug), "fault": fault,
             "description": "从 %s 派生的单一故障变体（tests/codekit01_legacy.py 的确定性字节变换）；不是厂商真实输出。"
                            % stub_fixture_id(source_slug)},
            {"applied": False, "rule_revision": None, "length_changed": None,
             "reason": "派生步骤未再脱敏；来源 %s 的 session.cwd 已按 %s 替换为占位值"
                       % (stub_fixture_id(source_slug), STUB_CWD_RULE_REVISION),
             "protocol_structure_preserved": None},
            negative_event_path(slug),
            ["exact_byte_digest", "single_fault_derivation", "legacy_event_summary_judgment"],
            ["real_cli_compatibility", "vendor_protocol", "legacy_end_to_end_run", "cross_platform_bytes",
             "new_protocol_acceptance"],
            EVENT_ENTRY, events_ref, integrity=NEGATIVE_EVENT_INTEGRITY[slug]))
    return entries


# ---------------------------------------------------------------------------
# 新严格入口（依赖 01-T2 codekit.protocols；结果单独存放，不参与旧预期）
# ---------------------------------------------------------------------------

def _import_protocols() -> types.ModuleType:
    import importlib

    scripts = str(REPO_ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        return importlib.import_module("codekit.protocols")
    except ImportError as exc:
        raise NotImplementedError("codekit.protocols 尚未就绪，无法给出新严格入口判断：%s" % exc)


NEW_STRICT_ENTRY = "codekit.protocols.strict_json_loads"


def new_strict_verdict(json_bytes: bytes) -> Dict[str, Any]:
    """新严格入口对一份 JSON 字节的判断：{"entry", "accepted", "code", "field", "reason"}。

    依赖 codekit.protocols.strict_json_loads（01-T2 公共协议，默认上限 1 MiB / 64 层）。只判断严格 JSON 层
    （BOM、UTF-8、重复键、非有限数、整数范围、孤立代理项、文法与尾随文档），不做合同 v1 的业务校验；
    合同 v1 不是 01 的公共记录类型，01 的新入口不对它做 Schema 判断。结果**不得**写入 legacy 预期文件。
    reason 是 ProtocolError 的固定原因文字（不含输入值；P4 第 3 轮起文法错误也是固定的 syntax_error，行列号只在
    ProtocolError.hint 中，不写入本投影）。
    """
    protocols = _import_protocols()
    try:
        protocols.strict_json_loads(json_bytes)
    except protocols.ProtocolError as exc:
        return {"entry": NEW_STRICT_ENTRY, "accepted": False, "code": exc.code, "field": exc.field,
                "reason": exc.reason}
    return {"entry": NEW_STRICT_ENTRY, "accepted": True, "code": None, "field": None, "reason": None}


def new_strict_jsonl_verdict(raw: bytes) -> Dict[str, Any]:
    """把 JSON Lines 字节按行交给 new_strict_verdict：按 LF 切分，文件以 LF 结尾时丢弃最后的空片段，
    每行原样（含行尾的 CR）传入。只说明“每行能否作为单个严格 JSON 文档”；原始厂商流的解析与结束判定
    归 04（01-D07），这不是新入口对事件流的判断。"""
    pieces = raw.split(b"\n")
    if pieces and pieces[-1] == b"":
        pieces.pop()
    rejected = []
    for number, line in enumerate(pieces, start=1):
        verdict = new_strict_verdict(line)
        if not verdict["accepted"]:
            rejected.append({"line": number, "code": verdict["code"], "field": verdict["field"],
                             "reason": verdict["reason"]})
    return {"entry": NEW_STRICT_ENTRY + "（逐行）", "lines": len(pieces),
            "final_line_terminated": raw.endswith(b"\n"),
            "accepted_lines": len(pieces) - len(rejected), "rejected_lines": rejected}


def legacy_json_fixture_paths() -> List[Tuple[str, str]]:
    """全部 legacy 与负例 JSON 合同 fixture：(fixture_id, path)。"""
    out = [(fid, path) for fid, _src, path, _d in LEGACY_CONTRACT_FILES if path.endswith(".json")]
    out += [(negative_contract_fixture_id(slug), negative_contract_path(slug, target))
            for slug, target, _t, _f in NEGATIVE_CONTRACT_VARIANTS if target == "json"]
    return out


def legacy_jsonl_fixture_paths() -> List[Tuple[str, str]]:
    """全部 stub 事件与事件负例 fixture：(fixture_id, path)。"""
    out = [(stub_fixture_id(slug), stub_fixture_path(slug)) for slug, _e, _c, _d in STUB_SCENARIOS]
    out += [(negative_event_fixture_id(slug), negative_event_path(slug)) for slug, _s, _t, _f in NEGATIVE_EVENT_VARIANTS]
    return out


def collect_new_strict_verdicts() -> Dict[str, Dict[str, Any]]:
    """对每个 legacy/负例 JSON 合同调用 new_strict_verdict（依赖 codekit.protocols.strict_json_loads）。"""
    return {fid: new_strict_verdict(read_fixture(path)) for fid, path in legacy_json_fixture_paths()}


def compute_new_strict_expected() -> Dict[str, Any]:
    """新严格入口对 legacy JSON 合同（整份）与 legacy 事件流（逐行）的判断，写入 legacy-new-strict.json。

    与旧实现的预期分开存放：两边判断不同是兼容矩阵（01-D09）的输入，不是失败。
    """
    documents: Dict[str, Any] = {}
    for fid, path in legacy_json_fixture_paths():
        raw = read_fixture(path)
        documents[fid] = {"path": path, "sha256": sha256_hex(raw), "new_strict": new_strict_verdict(raw)}
    streams: Dict[str, Any] = {}
    for fid, path in legacy_jsonl_fixture_paths():
        raw = read_fixture(path)
        streams[fid] = {"path": path, "sha256": sha256_hex(raw), "new_strict": new_strict_jsonl_verdict(raw)}
    return {
        "schema_version": 1,
        "record_type": "codekit01-new-strict-expected",
        "expected_kind": "legacy-new-strict",
        "projection_revision": NEW_STRICT_REVISION,
        "source_revision": SOURCE_REVISION,
        "entry": NEW_STRICT_ENTRY + "(raw, max_bytes=1048576, max_depth=64)",
        "implementation": {"path": "scripts/codekit/protocols.py",
                           "note": "按当前文件计算，不记录其摘要；判断一旦变化，差分测试即失败"},
        "generator": {"path": "tests/codekit01_legacy.py", "function": "compute_new_strict_expected",
                      "write_command": "PYTHONDONTWRITEBYTECODE=1 python tests/codekit01_legacy.py --write-expected",
                      "check_command": CHECK_COMMAND},
        "semantics": [
            "只判断严格 JSON 层；合同 v1 的字段语义（task_id、plan_version 类型、未知字段等）不属于 01 的新入口，"
            "01 不对合同 v1 做新 Schema 判断",
            "与 expected/legacy-contracts.json、legacy-events.json 中的旧实现判断分开存放；两边不同是兼容矩阵的输入，不是失败",
            "json_documents：整份文件交给 strict_json_loads",
            "jsonl_streams：按 LF 切分，文件以 LF 结尾时丢弃最后的空片段，每行原样（含行尾 CR）交给 strict_json_loads；"
            "只说明每行能否作为单个严格 JSON 文档，原始厂商流的解析与结束判定归 04（01-D07）",
        ],
        "json_documents": documents,
        "jsonl_streams": streams,
    }


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def write_expected() -> None:
    """写三份预期文件；manifest.json 随后由 tests/test_codekit01_fixtures.py --write 重建。"""
    _write_bytes(EXPECTED_CONTRACTS_PATH, render_json(compute_expected_contracts()))
    _write_bytes(EXPECTED_EVENTS_PATH, render_json(compute_expected_events()))
    _write_bytes(EXPECTED_NEW_STRICT_PATH, render_json(compute_new_strict_expected()))


def write_all() -> Dict[str, Any]:
    write_legacy_contracts()
    for path, raw in derive_negative_contracts().items():
        _write_bytes(path, raw)
    stub_records = write_stub_events()
    for path, raw in derive_negative_events().items():
        _write_bytes(path, raw)
    write_expected()
    return {"stub_cwd_replacement": stub_records, "sources": legacy_contract_source_report(),
            "next_step": "PYTHONDONTWRITEBYTECODE=1 python tests/test_codekit01_fixtures.py --write"}


def write_derived() -> Dict[str, Any]:
    """不重取 blob、不重跑 stub：先核对 legacy 合同副本与 a4fa199 的 blob 相同、stub 流的 cwd 已是占位值，再从这些
    已锁定的字节派生合同与事件负例，最后重算三份预期文件。已存在的负例文件只在字节不同时才会被改写，函数返回
    新写入与被改写的路径（新增变体时，被改写的列表应为空）。"""
    for item in legacy_contract_source_report():
        if not (item["fixture_equals_head"] and item["git_show_equals_cat_file"]):
            raise AssertionError("legacy 合同副本与 a4fa199 的 blob 不同：%s" % item["fixture_id"])
    stub_redaction_records()
    created: List[str] = []
    rewritten: List[str] = []
    for path, raw in list(derive_negative_contracts().items()) + list(derive_negative_events().items()):
        if not repo_path(path).exists():
            created.append(path)
        elif read_fixture(path) != raw:
            rewritten.append(path)
        else:
            continue
        _write_bytes(path, raw)
    write_expected()
    return {"created": created, "rewritten": rewritten,
            "next_step": "PYTHONDONTWRITEBYTECODE=1 python tests/test_codekit01_fixtures.py --write"}


def manifest_legacy_entries_match() -> bool:
    """manifest.json 中与 legacy 条目同 fixture_id 的条目，按出现顺序逐条等于 build_legacy_manifest_entries()。"""
    expected = build_legacy_manifest_entries()
    ids = {entry["fixture_id"] for entry in expected}
    document = json.loads(read_fixture(MANIFEST_PATH).decode("utf-8"))
    present = [entry for entry in document.get("entries", []) if entry.get("fixture_id") in ids]
    return [render_json(e) for e in present] == [render_json(e) for e in expected]


def check_all() -> List[Tuple[str, bool]]:
    """重新派生与重算，逐字节比较锁定文件；不写文件。"""
    results: List[Tuple[str, bool]] = []
    for item in legacy_contract_source_report():
        results.append(("legacy source bytes %s" % item["fixture_id"],
                        item["fixture_equals_head"] and item["git_show_equals_cat_file"]))
        results.append(("legacy worktree bytes %s" % item["fixture_id"], item["worktree_equals_head"]))
    for path, raw in list(derive_negative_contracts().items()) + list(derive_negative_events().items()):
        results.append(("negative derivation %s" % path, read_fixture(path) == raw))
    stub_redaction_records()
    results.append((EXPECTED_CONTRACTS_PATH, read_fixture(EXPECTED_CONTRACTS_PATH)
                    == render_json(compute_expected_contracts())))
    results.append((EXPECTED_EVENTS_PATH, read_fixture(EXPECTED_EVENTS_PATH) == render_json(compute_expected_events())))
    results.append((EXPECTED_NEW_STRICT_PATH, read_fixture(EXPECTED_NEW_STRICT_PATH)
                    == render_json(compute_new_strict_expected())))
    results.append((MANIFEST_PATH + " 的 legacy 条目", manifest_legacy_entries_match()))
    return results


def check_stub_regen(*, require_locked_bytes: bool = True) -> List[Tuple[str, bool]]:
    """重跑 stub，与锁定的事件字节和记录的退出码比较。require_locked_bytes 的含义同 run_stub。"""
    results = []
    for slug, env, expected_exit, _desc in STUB_SCENARIOS:
        stdout, code, _record = run_stub(env, require_locked_bytes=require_locked_bytes)
        results.append(("stub regen %s" % slug, code == expected_exit and stdout == read_fixture(stub_fixture_path(slug))))
    return results


def _print_results(results: Sequence[Tuple[str, bool]]) -> int:
    failed = 0
    for name, ok in results:
        print("%s %s" % ("SAME" if ok else "DIFF", name))
        failed += 0 if ok else 1
    print("%d checks, %d differ" % (len(results), failed))
    return 1 if failed else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass
    args = list(sys.argv[1:] if argv is None else argv)
    sys.dont_write_bytecode = True
    if args == ["--write"]:
        info = write_all()
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    if args == ["--write-derived"]:
        print(json.dumps(write_derived(), ensure_ascii=False, indent=2))
        return 0
    if args == ["--write-expected"]:
        write_expected()
        return 0
    if args == ["--check"]:
        return _print_results(check_all())
    if args == ["--check-stub-regen"]:
        return _print_results(check_stub_regen())
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
