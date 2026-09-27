#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""01-T3 兼容 fixtures：合成样本、单一故障负例、来源清单，以及差分与完整性测试（01-A02、A09、A12）。

本文件有两个用途：
1. 测试（默认）：`PYTHONDONTWRITEBYTECODE=1 python tests/test_codekit01_fixtures.py`
   不写任何文件；外部命令只有 git（只读：--version、rev-parse、show、cat-file、check-attr、不带 -w 的 hash-object）与
   tests/codekit01_legacy.py 重算旧实现投影、重跑 stub（只在 Windows）时在它自建的临时目录/临时仓库中运行的
   git、旧 CLI 与 tests/stub_pi.py。
   取不到 git 或提交 a4fa199 时，依赖它们的检查默认判为失败（01-A02：未取得旧结果不通过）；只有显式设置
   环境变量 CODEKIT01_ALLOW_NOT_RUN=1 时才跳过并标为 NOT_RUN（不算通过）。
2. 生成：`PYTHONDONTWRITEBYTECODE=1 python tests/test_codekit01_fixtures.py --write`
   按本文件的定义写 tests/fixtures/codekit01/synthetic/、negative/protocol/ 与 manifest.json。
   legacy 部分（legacy/、negative/legacy-*/、expected/）由 tests/codekit01_legacy.py 生成，先运行它。
   文档样例的字节取自设计文档，生成时文档必须存在。

定义与约定
- 合成样本（synthetic/）：设计文档 4.1.3、4.2.2（两个代码块）、4.3.1、4.3.6、4.3.9 的样例字节
  （代码块内容，不含围栏，末尾一个 LF，与附录 E.2 的约定相同）；附录 C.1 示例按 protocols-api.md 14.1
  补齐后的条目；附录 C.2 五组黄金向量；本文件定义的三个合成正例（vendor 事件、它引用的原始分段、
  已知费用的用量观测）；以及 legacy-stub-events-ok 的 manifest 条目副本。它们用来派生单一故障负例。
- 负例（negative/protocol/<组>/<变体>.json）：从某个被入口接受的正例做确定性字节变换（锚点必须恰好出现一次），
  只改变**一个目标条件**（设计文档 7.4）；个别变体要改几处字节才能不同时违反别的规则，fault 中写明原因。
  manifest 的 expected 写明入口与期望错误码，description 写明期望 field 与 reason；测试三项都断言。
- 能力声明（P4 起由产品入口按来源类别与表示约束全部条目）：validate_fixture_manifest_entry 对 legacy、negative
  条目同样拒绝 real_cli_compatibility、vendor_protocol 与 real_/vendor_ 前缀（只允许 captured + captured_raw/
  redacted_raw），legacy_dispatch_behavior 只允许 legacy + legacy-judgment；validate_fixture_manifest_set 要求声明
  legacy_ 能力的负例从 legacy 条目派生。本文件的 check_synthetic_fixture_claims 是**额外的**测试层规则（不是产品
  入口）：representation=synthetic_fixture 的条目连 legacy_dispatch_behavior 也不得声明，legacy_ 前缀只放行
  LEGACY_CLAIM_WHITELIST 中与旧实现差分入口对应的能力。P4 第 3 轮：产品入口要求声明符合封闭词法
  [a-z][a-z0-9_]{0,127}（claim_syntax）；测试层规则先按 ASCII 小写化、"-" 归一为 "_" 再判定，大小写与连字符变体
  都不能绕过。
- 生成模式的写入护栏（_check_write_target，P4 第 3 轮）：每个待写路径先经 validate_business_path，再按解析后的真实
  路径逐组件确认位于仓库根下对应的允许目录之内；write_all 在写任何文件之前先检查全部待写路径。
- manifest.json：fixture-manifest-set，按 tests/codekit01_legacy.render_json 固定序列化
  （json.dumps(ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + LF，UTF-8 无 BOM），不含自身摘要。
  条目顺序：legacy（codekit01_legacy.build_legacy_manifest_entries）、expected 三份、合成样本、协议负例。
- 期望入口（expected.entry）只取 ENTRY_RUNNERS 与 DIFFERENTIAL_ENTRIES 中列出的固定字符串；测试会拒绝未登记的入口。
- 收尾轮（裁决 R-P11）：每个条目都有 integrity、platform_scope、capture、redaction.protocol_structure_preserved 与
  origin.traceable。本清单的登记规则（R11Tests 逐条断言）：
  * capture 恒为 null（没有 captured 条目）；origin.traceable 恒为 true（legacy 按 source_revision 与
    source_path/source_test_id 追溯，synthetic 按设计文档修订或本文件的确定性构造追溯，negative 按 derived_from 与
    确定性字节变换复现）；
  * protocol_structure_preserved：redaction.applied=false 的条目写 null（没有脱敏步骤），只有 stub 流的 cwd 占位
    替换（applied=true）写 true；
  * integrity：文件是它所代表样本的完整字节时为 complete，包括值、语法或编码层面的单一故障负例（故障本身就是被测
    输入）；代表“证据或引用字节被截断/被破坏”的负例分别为 truncated/corrupted：事件流的尾部截断与夹入坏行
    （codekit01_legacy.NEGATIVE_EVENT_INTEGRITY），sample-1 副本去掉末尾 LF 与行尾被转换为 CRLF；
  * platform_scope：expected.outcome=legacy-judgment 的条目（旧实现判断，只在 Windows + Python 3.12.10 上锁定，含
    临时仓库中旧 CLI 的输出、Python 报错原文或 Windows 上生成的 CRLF 字节）为 ["windows"]；其余条目的判断由
    codekit.protocols 的函数对固定字节作出，不依赖平台，为 ["any"]。两者都是登记者的声明，不是各平台的实测。
- 收尾轮（文档 8.3“fixture 含真实凭据”）：CredentialScanTests 逐字节扫描 tests/fixtures/codekit01/ 下的每个文件
  （原字节即 UTF-8 视图、UTF-16 LE/BE 两种对齐下的 ASCII 视图，以及能严格解析的 JSON/JSONL 中的每个字符串），
  命中凭据形态（非白名单）即失败；失败信息只给文件与偏移（或 JSON 位置）和规则名，不回显匹配到的值。
- 收尾轮（acceptance.md M-04）：PublicEntryRejectionTests 把兼容矩阵第 1 节的抽查写成回归测试；
  CompatMatrixDCaseTests 按兼容矩阵 4.3 节断言 D-20–D-23 负例的旧判断与新严格入口判断（由 codekit01_legacy 生成）。
- 收尾轮（文档 8.4，acceptance.md R-12）：本文件不再用 TemporaryDirectory 做无核对的递归清理，临时区域由
  codekit01_legacy._make_owned_tempdir 建立、_rmtree 核对归属后删除；CleanupOwnershipTests 逐项对照归属核对。
- 收尾轮返工（复审 fidelity 与 tests-mutation 视角）：CREDENTIAL_RULES 由 9 条增加到 15 条（Stripe、Hugging Face、
  GitLab、npm、HTTP Basic、URL 内嵌口令），另有同一规则中其他前缀的对照样本，真实扫描核对已扫描的文件数与字节数；
  HarnessCleanupOwnershipTests 为 tests/legacy_harness.py 的 make_temp_area / remove_tree 归属核对补上回归测试
  （此前没有）；CleanupOwnershipTests 补上标记末尾多字节、标记是链接、删除后注销登记三项；CompatMatrixDCaseTests
  反向核对 D-xx 映射表的完整性；R11Tests 在真实条目上核对 R-P11 受控词表中的同义声明。
- 运行时按方法逐行输出（unittest.main(verbosity=2)），便于方法级取证。
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

sys.dont_write_bytecode = True

# 中文的 skip 原因与失败说明在 Git Bash（控制台代码页不是 UTF-8）中按 UTF-8 输出才可读（参照
# tests/test_dispatch.py 的做法）；无法编码的字符写成反斜杠转义，不因输出编码中断测试。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
for _entry in (str(TESTS_DIR), str(SCRIPTS_DIR)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

import codekit01_legacy as L  # noqa: E402
import legacy_harness as H  # noqa: E402  导入时只解析路径与常量，不建目录、不写文件（01-L04）
from codekit import protocols as P  # noqa: E402

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

FIXTURE_DIR = L.FIXTURE_DIR
MANIFEST_PATH = L.MANIFEST_PATH
LEGACY_DRAFT_PATH = FIXTURE_DIR + "/manifest.legacy.draft.json"
SYN = FIXTURE_DIR + "/synthetic"
NEG = FIXTURE_DIR + "/negative/protocol"
DOC_REVISION = "review-expanded-2026-09-25"
#: v2（P3 返工）：3 个负例改为只违反一个条件、期望增加 reason、新增 stub 条目副本与 fixture-manifest-claims 负例。
#: v3（P4）：产品来源规则改为按来源类别与表示约束全部条目：stub 条目声称 real_cli_compatibility 的负例改由产品入口
#: 拒绝，新增 vendor_protocol（产品入口）与未登记 legacy_ 能力（测试层规则）两个负例；captured 表示规则的 reason 改名。
#: v4（P4 第 3 轮）：E_JSON_SYNTAX 的期望 reason 改为固定的 syntax_error（位置移到 hint）；seq 的 4 个数值负例
#: （NaN、-Infinity、1e10000、2^53）的期望 field 由 null 改为 /seq（严格解析的数值错误带指针）；新增 vendor 事件
#: role=null（产品入口，vendor_event_requires_role）与 stub 条目声称大写变体 REAL_CLI_COMPATIBILITY（产品入口，
#: claim_syntax）两个负例。负例字节只新增，已有负例的字节不变。
#: v5（收尾轮，裁决 R-P11）：条目增加 integrity、platform_scope、capture、redaction.protocol_structure_preserved、
#: origin.traceable。两个基样本（synthetic-doc-c.1-manifest-entry-completed 与 legacy-stub-events-ok 条目副本）随之
#: 增加这些字段，从它们派生的 15 个 fixture-manifest 类负例的字节改变（变换与期望不变）；另新增 8 个针对新字段的
#: fixture-manifest-entry 负例；两个 synthetic-sample 负例的 integrity 登记为 corrupted/truncated。其他负例的字节不变。
GENERATOR_REVISION = "codekit01-protocol-fixtures-v5"
DOC_DIR = REPO_ROOT / "docs" / "code-kit-v2"
DOC_PREFIX = "01-baseline-and-protocols-"

SAMPLE_1_BYTES = b'{"fixture":"synthetic","ok":true}\n'
SAMPLE_1_SHA256 = "0036dde35a13e287320b6399674c46649365553a0ab6d3edf2a2111d6f83c4e1"

#: 生成模式允许写入的前缀（任务分配的独占范围）。
_WRITE_PREFIXES = (SYN + "/", NEG + "/", MANIFEST_PATH)

render_json = L.render_json


def repo_path(rel: str) -> Path:
    return REPO_ROOT.joinpath(*rel.split("/"))


def read_fixture(rel: str) -> bytes:
    return repo_path(rel).read_bytes()


def registry() -> P.ResourceKindRegistry:
    return P.build_default_registry()


# ---------------------------------------------------------------------------
# 期望入口（manifest 的 expected.entry）与执行方式
# ---------------------------------------------------------------------------

ENTRY_STRICT = "codekit.protocols.strict_json_loads"
ENTRY_RUN_CONTEXT = ("strict_json_loads -> validate_public_record(expected_record_type=run-context, "
                     "registry=build_default_registry())")
ENTRY_RUN_EVENT_CORE = ("strict_json_loads -> validate_public_record(expected_record_type=run-event, "
                        "registry=build_default_registry(), event_types=build_default_event_types())")
ENTRY_RUN_EVENT_VENDOR = ("strict_json_loads -> validate_public_record(expected_record_type=run-event, "
                          "registry=build_default_registry(), segment_sizes={sha256: 字节数} of synthetic-raw-segment-1)")
ENTRY_USAGE = ("strict_json_loads -> validate_public_record(expected_record_type=usage-observation, "
               "registry=build_default_registry())")
ENTRY_RESOURCE_REF = "strict_json_loads -> validate_resource_ref(registry=build_default_registry())"
ENTRY_VERIFY_BYTES = ("verify_resource_bytes(ref=synthetic-doc-4.2.2-resource-ref 的 ResourceRef, raw=本文件字节, "
                      "registry=build_default_registry())")
ENTRY_VERIFY_REF = ("strict_json_loads -> verify_resource_bytes(ref=本文件, raw=synthetic-protocol-sample-1 的字节, "
                    "registry=build_default_registry())")
ENTRY_ERROR_RECORD = ("strict_json_loads -> ProtocolError(code, field, phase, reason, hint, source_ref).to_record() "
                      "必须与本记录相等")
ENTRY_MANIFEST_ENTRY = "strict_json_loads -> validate_fixture_manifest_entry(registry=build_default_registry())"
ENTRY_GOLDEN = ("strict_json_loads -> 逐项 strict_json_loads(input_json) -> stable_snapshot_bytes -> sha256_hex，"
                "与 expected_snapshot_utf8_hex / expected_sha256 比较")
#: 合成 vendor 事件的类型名。01 不登记厂商事件类型（归 04）；只有 ENTRY_RUN_EVENT_VENDOR_TYPED 在测试内登记它。
SYNTHETIC_VENDOR_EVENT_TYPE = "synthetic.vendor.message_end"
ENTRY_RUN_EVENT_VENDOR_TYPED = ("strict_json_loads -> validate_public_record(run-event, build_default_registry(), "
                                "event_types=build_default_event_types() 加测试内登记的 synthetic.vendor.message_end"
                                "（仅 vendor、无载荷校验）, segment_sizes 同 synthetic-raw-segment-1)")
#: 产品入口之后再加测试层规则（不是产品入口）：见 check_synthetic_fixture_claims。
ENTRY_MANIFEST_CLAIMS = ("strict_json_loads -> validate_fixture_manifest_entry(registry=build_default_registry()) -> "
                         "tests/test_codekit01_fixtures.py::check_synthetic_fixture_claims（测试层规则，不是产品入口）")

ENTRY_LEGACY_CONTRACTS_EXPECTED = ("tests/codekit01_legacy.py::compute_expected_contracts"
                                   "（以当前 scripts/pi_dispatch.py 重算，逐字节比较）")
ENTRY_LEGACY_EVENTS_EXPECTED = ("tests/codekit01_legacy.py::compute_expected_events"
                                "（以当前 scripts/pi_dispatch.py 重算，逐字节比较）")
ENTRY_NEW_STRICT_EXPECTED = ("tests/codekit01_legacy.py::compute_new_strict_expected"
                             "（以当前 scripts/codekit/protocols.py 重算，逐字节比较）")

#: 由差分测试检查的入口（旧实现判断与锁定预期）。
DIFFERENTIAL_ENTRIES = (L.CONTRACT_ENTRY, L.EVENT_ENTRY, ENTRY_LEGACY_CONTRACTS_EXPECTED,
                        ENTRY_LEGACY_EVENTS_EXPECTED, ENTRY_NEW_STRICT_EXPECTED)

RAW_SEGMENT_ID = "synthetic-raw-segment-1"
DOC_REF_ID = "synthetic-doc-4.2.2-resource-ref"
SAMPLE_1_ID = "synthetic-protocol-sample-1"
STUB_ENTRY_SOURCE_ID = L.stub_fixture_id("ok")
STUB_ENTRY_COPY_ID = "synthetic-manifest-entry-legacy-stub-events-ok"


def _segment_sizes() -> Dict[str, int]:
    raw = read_fixture(SYNTHETIC_PATHS[RAW_SEGMENT_ID])
    return {P.sha256_hex(raw): len(raw)}


def _run_public(raw: bytes, record_type: str, **kwargs: Any) -> Any:
    return P.validate_public_record(P.strict_json_loads(raw), expected_record_type=record_type,
                                    registry=registry(), **kwargs)


def _run_error_record(raw: bytes) -> None:
    record = P.strict_json_loads(raw)
    if type(record) is not dict or set(record) != {"code", "message", "details", "retryable"}:
        raise AssertionError("错误记录的顶层字段不是 code/message/details/retryable")
    details = record["details"]
    if type(details) is not dict or set(details) != {"field", "source_ref", "phase", "reason", "hint"}:
        raise AssertionError("错误记录的 details 字段不是 field/source_ref/phase/reason/hint")
    rebuilt = P.ProtocolError(record["code"], field=details["field"], phase=details["phase"],
                              reason=details["reason"], hint=details["hint"],
                              source_ref=details["source_ref"]).to_record()
    if rebuilt != record:
        raise AssertionError("错误记录与 ProtocolError.to_record() 的结果不同")


def event_types_with_synthetic_vendor() -> P.EventTypeRegistry:
    """默认事件类型（只有 core 的 run.prepared）加一个测试内登记的合成 vendor 类型。"""
    return P.build_default_event_types().extended(
        [P.EventType(SYNTHETIC_VENDOR_EVENT_TYPE, frozenset({"vendor"}), None, "synthetic")])


# ---------------------------------------------------------------------------
# representation=synthetic_fixture 的能力声明（测试层规则）
# ---------------------------------------------------------------------------

#: 设计文档 4.3.3：synthetic_fixture 是“人工/程序构造的测试样本……无真实厂商来源声明”。
#: P4 起产品入口（protocols._validate_fixture_entry 与 validate_fixture_manifest_set）已按来源类别与表示约束全部
#: 条目：real_/vendor_ 类声明只允许 captured + captured_raw/redacted_raw，legacy_dispatch_behavior 只允许
#: legacy + legacy-judgment，声明 legacy_ 能力的负例必须从 legacy 条目派生。下面的规则是在此之上的**测试层**
#: 约定（本清单特有，不是产品入口）：representation=synthetic_fixture 的条目连 legacy_dispatch_behavior 也不得
#: 声明（本清单用更具体的 legacy_*_judgment），legacy_ 前缀只放行白名单中与旧实现差分入口对应的能力。
#: 由 ManifestTests.test_provenance_consistency、NegativeTests 与生成（write_all）调用。
CLAIM_RULE_REAL = "test_rule_synthetic_fixture_cannot_prove_real_compatibility"
CLAIM_RULE_LEGACY = "test_rule_legacy_claim_not_whitelisted"
_REAL_CLAIM_PREFIXES_EXCEPT_LEGACY = ("real_", "vendor_")

#: legacy_ 前缀能力的来源白名单：能力 -> 允许声明它的期望入口（旧实现的差分入口）。只放行 origin.class 为
#: legacy 或 negative 的条目；legacy_source_bytes 另要求 origin.class=legacy、带 source_path、不带
#: source_test_id（原字节副本）。负例的派生来源必须是 legacy 条目：单条目看不到派生来源，由清单级的
#: check_manifest_claims 与 test_provenance_consistency 另行断言。
LEGACY_CLAIM_WHITELIST: Dict[str, Tuple[str, ...]] = {
    "legacy_source_bytes": (L.CONTRACT_ENTRY,),
    "legacy_contract_judgment": (L.CONTRACT_ENTRY, ENTRY_LEGACY_CONTRACTS_EXPECTED),
    "legacy_event_summary_judgment": (L.EVENT_ENTRY, ENTRY_LEGACY_EVENTS_EXPECTED),
}


def _claim_rule_error(reason: str) -> P.ProtocolError:
    return P.ProtocolError("E_PROVENANCE_CLAIM", field="/proves", phase="provenance", reason=reason)


def _legacy_claim_allowed(claim: str, entry: Dict[str, Any]) -> bool:
    origin = entry["origin"]
    if claim not in LEGACY_CLAIM_WHITELIST or origin["class"] not in ("legacy", "negative"):
        return False
    if entry["expected"]["entry"] not in LEGACY_CLAIM_WHITELIST[claim]:
        return False
    if claim == "legacy_source_bytes":
        return (origin["class"] == "legacy" and origin["source_path"] is not None
                and origin["source_test_id"] is None)
    return True


def check_synthetic_fixture_claims(entry: Dict[str, Any]) -> None:
    """representation=synthetic_fixture 的条目不得在 proves 中声称真实兼容：不得含 P.REAL_COMPATIBILITY_CLAIMS，
    不得有 real_、vendor_ 前缀；legacy_ 前缀只放行 LEGACY_CLAIM_WHITELIST。违反时抛 E_PROVENANCE_CLAIM
    （field=/proves，reason 以 test_rule_ 开头，表明来自测试层规则）。

    P4 第 3 轮（复审 tests-mutation 视角，major）：判定前把声明按 ASCII 小写化、把 "-" 归一为 "_"，大小写与连字符变体
    （REAL_CLI_COMPATIBILITY、Vendor_Protocol、vendor-protocol）按同一条规则拒绝；归一后与原文不同的 legacy_ 声明
    也不在白名单内（白名单只放行原样拼写）。产品入口另在结构层按封闭词法拒绝这些变体（claim_syntax）。"""
    if entry["representation"] != "synthetic_fixture":
        return
    for original in entry["proves"]:
        claim = original.lower().replace("-", "_") if original.isascii() else original
        if claim in P.REAL_COMPATIBILITY_CLAIMS or claim.startswith(_REAL_CLAIM_PREFIXES_EXCEPT_LEGACY):
            raise _claim_rule_error(CLAIM_RULE_REAL)
        if claim.startswith("legacy_") and (claim != original or not _legacy_claim_allowed(claim, entry)):
            raise _claim_rule_error(CLAIM_RULE_LEGACY)


def check_manifest_claims(manifest: Dict[str, Any]) -> None:
    """整份清单逐条调用 check_synthetic_fixture_claims，并要求声明 legacy_ 能力的负例从 legacy 条目派生。"""
    by_id = {e["fixture_id"]: e for e in manifest["entries"]}
    for entry in manifest["entries"]:
        check_synthetic_fixture_claims(entry)
        if entry["origin"]["class"] == "negative" and any(c.lower().replace("-", "_").startswith("legacy_")
                                                          for c in entry["proves"]):
            base = by_id.get(entry["origin"]["derived_from"])
            if base is None or base["origin"]["class"] != "legacy":
                raise _claim_rule_error(CLAIM_RULE_LEGACY)


def _run_manifest_claims(raw: bytes) -> None:
    entry = P.strict_json_loads(raw)
    P.validate_fixture_manifest_entry(entry, registry())
    check_synthetic_fixture_claims(entry)


def _run_golden(raw: bytes) -> None:
    document = P.strict_json_loads(raw)
    for vector in document["vectors"]:
        value = P.strict_json_loads(vector["input_json"].encode("utf-8"))
        snapshot = P.stable_snapshot_bytes(value)
        if snapshot.hex() != vector["expected_snapshot_utf8_hex"]:
            raise AssertionError("黄金向量 %s 的快照字节不符" % vector["id"])
        if P.sha256_hex(snapshot) != vector["expected_sha256"]:
            raise AssertionError("黄金向量 %s 的摘要不符" % vector["id"])


ENTRY_RUNNERS: Dict[str, Callable[[bytes], Any]] = {
    ENTRY_STRICT: lambda raw: P.strict_json_loads(raw),
    ENTRY_RUN_CONTEXT: lambda raw: _run_public(raw, "run-context"),
    ENTRY_RUN_EVENT_CORE: lambda raw: _run_public(raw, "run-event", event_types=P.build_default_event_types()),
    ENTRY_RUN_EVENT_VENDOR: lambda raw: _run_public(raw, "run-event", segment_sizes=_segment_sizes()),
    ENTRY_RUN_EVENT_VENDOR_TYPED: lambda raw: _run_public(raw, "run-event", segment_sizes=_segment_sizes(),
                                                          event_types=event_types_with_synthetic_vendor()),
    ENTRY_USAGE: lambda raw: _run_public(raw, "usage-observation"),
    ENTRY_RESOURCE_REF: lambda raw: P.validate_resource_ref(P.strict_json_loads(raw), registry()),
    ENTRY_VERIFY_BYTES: lambda raw: P.verify_resource_bytes(
        P.strict_json_loads(read_fixture(SYNTHETIC_PATHS[DOC_REF_ID])), raw, registry()),
    ENTRY_VERIFY_REF: lambda raw: P.verify_resource_bytes(
        P.strict_json_loads(raw), read_fixture(SYNTHETIC_PATHS[SAMPLE_1_ID]), registry()),
    ENTRY_ERROR_RECORD: _run_error_record,
    ENTRY_MANIFEST_ENTRY: lambda raw: P.validate_fixture_manifest_entry(P.strict_json_loads(raw), registry()),
    ENTRY_MANIFEST_CLAIMS: _run_manifest_claims,
    ENTRY_GOLDEN: _run_golden,
}


# ---------------------------------------------------------------------------
# 设计文档代码块
# ---------------------------------------------------------------------------

def find_design_doc() -> Optional[Path]:
    """按前缀查找 01 设计文档（仓库中文件名因编码显示为乱码，与 tests/test_protocols.py 相同的做法）。"""
    if not DOC_DIR.is_dir():
        return None
    matches = sorted(p for p in DOC_DIR.iterdir()
                     if p.name.startswith(DOC_PREFIX) and p.name.endswith(".md") and p.is_file())
    return matches[0] if len(matches) == 1 else None


def design_doc_text() -> Optional[str]:
    doc = find_design_doc()
    if doc is None:
        return None
    return doc.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _heading_level(line: str) -> int:
    stripped = line.lstrip("#")
    hashes = len(line) - len(stripped)
    return hashes if hashes and stripped.startswith(" ") else 0


def doc_code_block(text: str, heading: str, lang: str, index: int = 0) -> bytes:
    """取某标题下（到下一个同级或更高级标题为止）第 index 个 ```lang 代码块：内容不含围栏，末尾一个 LF。"""
    lines = text.split("\n")
    if lines.count(heading) != 1:
        raise AssertionError("设计文档中的标题必须恰好出现一次：%s" % heading)
    level = _heading_level(heading)
    blocks: List[str] = []
    i = lines.index(heading) + 1
    while i < len(lines):
        line = lines[i]
        if 0 < _heading_level(line) <= level:
            break
        if line.startswith("```"):
            end = lines.index("```", i + 1)
            if line == "```" + lang:
                blocks.append("\n".join(lines[i + 1:end]) + "\n")
            i = end + 1
            continue
        i += 1
    return blocks[index].encode("utf-8")


def doc_table_rows(text: str, heading: str) -> List[List[str]]:
    """取某标题下第一张 Markdown 表格的数据行（去掉表头与分隔行），每格去掉首尾空白。"""
    lines = text.split("\n")
    level = _heading_level(heading)
    rows: List[List[str]] = []
    started = False
    for line in lines[lines.index(heading) + 1:]:
        if 0 < _heading_level(line) <= level:
            break
        if line.startswith("|"):
            started = True
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
        elif started:
            break
    return rows[2:]


# ---------------------------------------------------------------------------
# 合成样本（synthetic/）
# ---------------------------------------------------------------------------

class SyntheticSpec(NamedTuple):
    fixture_id: str
    path: str
    doc_source: Optional[Tuple[str, str, int]]  # (标题, 代码块语言, 序号)；None 表示本文件定义的字节
    entry: str
    description: str
    proves: Tuple[str, ...]
    does_not_prove: Tuple[str, ...]
    generator_revision: str = DOC_REVISION  # 字节来自设计文档（含 C.1 补齐、C.2 表格）时为文档修订


_DOC_PROVES = ("exact_byte_digest", "doc_sample_bytes", "structure_accepted_by_entry")
_DOC_NOT_PROVES = ("real_cli_compatibility", "vendor_protocol", "legacy_dispatch_behavior")

SYNTHETIC_SPECS: Tuple[SyntheticSpec, ...] = (
    SyntheticSpec(
        SAMPLE_1_ID, SYN + "/synthetic-protocol-sample-1.json", ("#### 4.2.2 可复算的合成引用示例", "text", 0),
        ENTRY_VERIFY_BYTES,
        "01 审阅增强版 4.2.2 的合成字节：{\"fixture\":\"synthetic\",\"ok\":true} 加一个 LF（取自该节 text 代码块，"
        "不含围栏）。用于完整字节哈希与来源标签，不是厂商输出。期望按同节 ResourceRef（synthetic-doc-4.2.2-resource-ref）"
        "核对摘要通过；这组字节恰好也等于该对象的固定快照输出，测试把两件事分开断言。",
        ("exact_byte_digest", "synthetic_provenance_label"),
        ("real_cli_compatibility", "legacy_dispatch_behavior")),
    SyntheticSpec(
        "synthetic-doc-4.1.3-run-context", SYN + "/doc-4.1.3-run-context.json",
        ("#### 4.1.3 RunContext 示例", "json", 0), ENTRY_RUN_CONTEXT,
        "01 审阅增强版 4.1.3 RunContext 示例代码块的字节（不含围栏，末尾一个 LF）。合成结构示例："
        "attempt=null 表示尚未绑定执行尝试，不表示调用已发生；标识由可信核心分配、与 07 受信记录一致等检查不在入口内。",
        _DOC_PROVES, _DOC_NOT_PROVES + ("trusted_context_binding", "executor_dispatch_readiness")),
    SyntheticSpec(
        DOC_REF_ID, SYN + "/doc-4.2.2-resource-ref.json", ("#### 4.2.2 可复算的合成引用示例", "json", 0),
        ENTRY_RESOURCE_REF,
        "01 审阅增强版 4.2.2 文件资源引用示例代码块的字节。其 path 是文档建议位置 "
        "tests/fixtures/synthetic-protocol-sample-1.json（本仓库的副本在 synthetic/ 下），sha256 是 "
        "synthetic-protocol-sample-1 的完整字节摘要；本入口只检查结构与登记，字节核对见 synthetic-protocol-sample-1。",
        _DOC_PROVES, _DOC_NOT_PROVES + ("resource_bytes_readable_at_path",)),
    SyntheticSpec(
        "synthetic-doc-4.3.1-run-event", SYN + "/doc-4.3.1-run-event.json",
        ("#### 4.3.1 标准运行事件封装", "json", 0), ENTRY_RUN_EVENT_CORE,
        "01 审阅增强版 4.3.1 合成核心事件示例代码块的字节。run.prepared 只说明运行上下文已准备，"
        "不证明子进程或模型已启动；seq 连续性与受信上下文绑定不在单条记录入口内。",
        _DOC_PROVES + ("event_type_registered",), _DOC_NOT_PROVES + ("process_started", "seq_continuity")),
    SyntheticSpec(
        "synthetic-doc-4.3.6-error-record", SYN + "/doc-4.3.6-error-record.json",
        ("#### 4.3.6 结构化错误与退出兼容", "json", 0), ENTRY_ERROR_RECORD,
        "01 审阅增强版 4.3.6 结构化错误示例代码块的字节。期望与 ProtocolError(...).to_record() 逐字段相等"
        "（message 取错误码表的安全文案，retryable 取错误码表的值）。",
        _DOC_PROVES + ("error_record_matches_to_record",), _DOC_NOT_PROVES + ("legacy_exit_code_mapping",)),
    SyntheticSpec(
        "synthetic-doc-4.3.9-usage-unknown", SYN + "/doc-4.3.9-usage-unknown.json",
        ("#### 4.3.9 全未知用量样例", "json", 0), ENTRY_USAGE,
        "01 审阅增强版 4.3.9 全未知用量样例代码块的字节。合成结构示例，不是主会话或真实厂商的计量记录；"
        "单条校验不做范围、去重与记账（usage_view 与 07）。",
        _DOC_PROVES, _DOC_NOT_PROVES + ("usage_accounting",)),
    SyntheticSpec(
        "synthetic-doc-c.1-manifest-entry-completed", SYN + "/doc-c.1-manifest-entry-completed.json", None,
        ENTRY_MANIFEST_ENTRY,
        "01 审阅增强版附录 C.1 fixture Manifest 示例，按 protocols-api.md 14.1 补齐 origin.source_path/derived_from/"
        "fault、redaction.rule_revision/length_changed、expected，以及收尾轮（R-P11）的 origin.traceable、"
        "redaction.protocol_structure_preserved、integrity、platform_scope、capture 后的条目；去掉补齐的字段后与 C.1 原文"
        "逐值相同，且与 protocols-api.md 14.1 的补齐示例相同（测试核对）。C.1 原文按封闭结构会被拒绝。条目中的 "
        "resource.path 是文档建议位置，不是本仓库的 fixture 路径。",
        ("exact_byte_digest", "structure_accepted_by_entry", "provenance_rules_accepted"),
        _DOC_NOT_PROVES),
    SyntheticSpec(
        "synthetic-golden-vectors-c.2", SYN + "/golden-vectors-c.2.json", None, ENTRY_GOLDEN,
        "01 审阅增强版附录 C.2 五组固定快照黄金向量：输入（JSON 文本，非 ASCII 字符写成 \\u 转义）、期望快照字节"
        "（十六进制）与期望 SHA-256（抄自 C.2 表，测试另与文档表格核对）。只测试序列化器，不表示任何 Schema 接受任意实数。",
        ("exact_byte_digest", "snapshot_golden_vectors"),
        ("real_cli_compatibility", "rfc8785_jcs_compatibility", "config_schema_acceptance")),
    SyntheticSpec(
        RAW_SEGMENT_ID, SYN + "/raw-segment-1.jsonl", None, ENTRY_STRICT,
        "合成的原始流分段字节（一行 JSON 加 LF），供 synthetic-vendor-event-1 的 raw_refs 引用，"
        "并作为 vendor 入口 segment_sizes 的唯一来源（按实际字节计算大小）。不是厂商输出；分段语义归 04。",
        ("exact_byte_digest", "raw_segment_size_source"),
        ("real_cli_compatibility", "vendor_protocol", "sealed_segment_index"), GENERATOR_REVISION),
    SyntheticSpec(
        "synthetic-vendor-event-1", SYN + "/vendor-event-1.json", None, ENTRY_RUN_EVENT_VENDOR,
        "合成的 vendor 事件封装：带 adapter_revision，integrity=complete，raw_refs 引用 synthetic-raw-segment-1 的"
        "完整字节区间 [0, 大小)。type 是合成名称；01 不登记厂商事件类型（归 04），所以入口不传 event_types。不是厂商输出。",
        ("exact_byte_digest", "structure_accepted_by_entry", "raw_span_within_segment"),
        ("real_cli_compatibility", "vendor_protocol", "adapter_revision_is_locked", "payload_schema"),
        GENERATOR_REVISION),
    SyntheticSpec(
        "synthetic-usage-reported-cost-1", SYN + "/usage-reported-cost-1.json", None, ENTRY_USAGE,
        "合成的已知用量观测：delta，input_tokens=1000 且说明已含 cache_read_tokens=800，reported_cost 为 "
        "vendor_reported 的十进制字符串金额；为 null 的可未知字段都写了原因。不是真实计量或费用。",
        ("exact_byte_digest", "structure_accepted_by_entry", "usage_money_format"),
        ("real_cli_compatibility", "vendor_protocol", "usage_accounting", "iso4217_membership"),
        GENERATOR_REVISION),
    SyntheticSpec(
        STUB_ENTRY_COPY_ID, SYN + "/manifest-entry-legacy-stub-events-ok.json", None, ENTRY_MANIFEST_CLAIMS,
        "manifest.json 中 legacy-stub-events-ok 条目的独立副本（codekit01_legacy.build_legacy_manifest_entries 生成的"
        "同一对象，按 render_json 固定序列化）。用作 fixture-manifest-claims 负例的基样本：stub 生成的流"
        "（representation=synthetic_fixture）不得声称真实 CLI 或厂商兼容（产品入口 validate_fixture_manifest_entry "
        "拒绝），也不得声称白名单之外的 legacy_ 能力（entry 中的测试层规则，不是产品入口）。",
        ("exact_byte_digest", "structure_accepted_by_entry", "provenance_rules_accepted",
         "synthetic_fixture_claims_test_rule_accepted"),
        ("real_cli_compatibility", "vendor_protocol", "legacy_dispatch_behavior"),
        GENERATOR_REVISION),
)

SYNTHETIC_PATHS: Dict[str, str] = {spec.fixture_id: spec.path for spec in SYNTHETIC_SPECS}

RAW_SEGMENT_1_BYTES = (b'{"type":"message_end","synthetic":true,'
                       b'"note":"synthetic raw segment for raw_refs bounds checks; not vendor output"}\n')

C1_COMPLETED_TEXT = """{
  "schema_version": 1,
  "record_type": "fixture-manifest",
  "fixture_id": "synthetic-protocol-sample-1",
  "origin": {
    "class": "synthetic",
    "source_revision": null,
    "source_test_id": null,
    "source_path": null,
    "generator_revision": "review-expanded-2026-09-25",
    "derived_from": null,
    "fault": null,
    "description": "用于完整字节哈希和来源标签的合成示例，不是厂商输出。",
    "traceable": true
  },
  "representation": "synthetic_fixture",
  "redaction": {
    "applied": false,
    "rule_revision": null,
    "length_changed": null,
    "reason": "构造时不包含真实凭据或真实用户数据。",
    "protocol_structure_preserved": null
  },
  "resource": {
    "kind": "fixture",
    "id": "synthetic-protocol-sample-1",
    "sha256": "0036dde35a13e287320b6399674c46649365553a0ab6d3edf2a2111d6f83c4e1",
    "path": "tests/fixtures/synthetic-protocol-sample-1.json"
  },
  "proves": ["exact_byte_digest", "synthetic_provenance_label"],
  "does_not_prove": ["real_cli_compatibility", "legacy_dispatch_behavior"],
  "expected": {"outcome": "accept", "code": null, "entry": "strict_json_loads", "expected_ref": null},
  "integrity": "complete",
  "platform_scope": ["any"],
  "capture": null
}
"""

#: C.1 补齐的字段（JSON Pointer 的父对象, 键）。后五项是收尾轮（裁决 R-P11）新增的字段。
C1_COMPLETION_FIELDS = ((("origin",), "source_path"), (("origin",), "derived_from"), (("origin",), "fault"),
                        (("redaction",), "rule_revision"), (("redaction",), "length_changed"), ((), "expected"),
                        (("origin",), "traceable"), (("redaction",), "protocol_structure_preserved"),
                        ((), "integrity"), ((), "platform_scope"), ((), "capture"))

USAGE_REPORTED_COST_TEXT = """{
  "schema_version": 1,
  "record_type": "usage-observation",
  "usage_id": "usage-synthetic-reported-1",
  "request_id": "req-11111111111141118111111111111111",
  "run_id": "run-22222222222242228222222222222222",
  "role": "planner",
  "provider": "synthetic-provider",
  "model": "synthetic-model",
  "observation_kind": "delta",
  "input_tokens": 1000,
  "cache_read_tokens": 800,
  "cache_write_tokens": 0,
  "output_tokens": 200,
  "reasoning_tokens": null,
  "input_includes_cache": true,
  "output_includes_reasoning": null,
  "reported_cost": {"amount": "0.00129", "currency": "USD"},
  "estimated_cost": null,
  "billing_source": "vendor_reported",
  "billing_event_id": "synthetic-billing-event-1",
  "supersedes_usage_id": null,
  "unknown_reasons": {
    "reasoning_tokens": "not_reported",
    "output_includes_reasoning": "vendor_semantics_unavailable",
    "estimated_cost": "no_pricing_basis"
  },
  "evidence_refs": []
}
"""


def build_vendor_event(raw_segment: bytes) -> bytes:
    return ("""{
  "schema_version": 1,
  "record_type": "run-event",
  "request_id": "req-11111111111141118111111111111111",
  "run_id": "run-22222222222242228222222222222222",
  "seq": 2,
  "observed_at": "2026-09-25T00:00:01.000000Z",
  "role": "planner",
  "type": "%s",
  "source_kind": "vendor",
  "payload": {"example_only": true},
  "raw_refs": [{"ref": {"kind": "raw-segment", "id": "%s", "sha256": "%s", "path": "%s"}, "byte_start": 0, \
"byte_end": %d, "stream": "stdout"}],
  "integrity": "complete",
  "adapter_revision": "synthetic-adapter-r1"
}
""" % (SYNTHETIC_VENDOR_EVENT_TYPE, RAW_SEGMENT_ID, P.sha256_hex(raw_segment), SYNTHETIC_PATHS[RAW_SEGMENT_ID],
       len(raw_segment))).encode("utf-8")


#: (id, input_json, input_codepoints, 关键检查点, 期望快照（文本）, 期望 SHA-256（抄自附录 C.2）)
GOLDEN_VECTORS: Tuple[Tuple[str, str, Optional[List[str]], str, str, str], ...] = (
    ("c2-1-key-order", '{"b":2,"a":1}', None, "输出严格为 {\"a\":1,\"b\":2} 加 LF", '{"a":1,"b":2}\n',
     "e8d38819d39f705646bfb643368eca78f7db476c16471dbc33b941b27326410d"),
    ("c2-2-precomposed", '{"text":"\\u00e9"}', ["U+00E9"], "UTF-8 原样输出，不加 BOM", '{"text":"\u00e9"}\n',
     "4dbc4b223d0da4858700d9a483553a9f2d5c31d2c2fcb7e45e41c56e3bd1f20c"),
    ("c2-3-decomposed", '{"text":"\\u0065\\u0301"}', ["U+0065", "U+0301"], "不归一化成上一行",
     '{"text":"\u0065\u0301"}\n', "4ae0b8cab5f8efd099785478bbd470b23d1c0eb7424b785416f3ee5496245948"),
    ("c2-4-integer", '{"n":1}', None, "整数表示", '{"n":1}\n',
     "cedf74272c9fc8db5448283a93277e7e7eb7534b71df3bd8ab35fd9b1b73404c"),
    ("c2-5-real", '{"n":1.0}', None, "实数表示与上一行不同", '{"n":1.0}\n',
     "4352df4233f0d6492477e70dab0a2b2aa9683d2297d61c8e8d98b515a4bc2f8d"),
)


def build_golden_document() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "record_type": "codekit01-golden-vectors",
        "source": "01 审阅增强版附录 C.2（修订 %s）" % DOC_REVISION,
        "profile": "codekit-config-json-py-v1",
        "serializer": "json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(\",\", \":\"), "
                      "allow_nan=False) + \"\\n\"，按 UTF-8 编码，无 BOM",
        "input_encoding": "input_json 是 JSON 文本，非 ASCII 字符写成 \\uXXXX 转义；经 strict_json_loads 解析后"
                          "得到 input_codepoints 所列的码点",
        "note": "只测试序列化器，不表示具体配置 Schema 接受任意实数；整数字段的 1.0 应在进入快照器前被拒绝（附录 C.2）",
        "vectors": [{"id": vid, "input_json": text, "input_codepoints": cps, "check": check,
                     "expected_snapshot_utf8_hex": snapshot.encode("utf-8").hex(), "expected_sha256": digest}
                    for vid, text, cps, check, snapshot, digest in GOLDEN_VECTORS],
    }


def build_stub_entry_copy() -> bytes:
    """legacy-stub-events-ok 的 manifest 条目（与 manifest.json 中的同一条目相同的对象）按 render_json 序列化。"""
    matches = [e for e in L.build_legacy_manifest_entries() if e["fixture_id"] == STUB_ENTRY_SOURCE_ID]
    if len(matches) != 1:
        raise AssertionError("legacy 条目中 %s 必须恰好出现一次" % STUB_ENTRY_SOURCE_ID)
    return render_json(matches[0])


def build_literal_synthetic_files() -> Dict[str, bytes]:
    """本文件定义字节的合成样本（不依赖设计文档）。"""
    return {
        SYNTHETIC_PATHS["synthetic-doc-c.1-manifest-entry-completed"]: C1_COMPLETED_TEXT.encode("utf-8"),
        SYNTHETIC_PATHS["synthetic-golden-vectors-c.2"]: render_json(build_golden_document()),
        SYNTHETIC_PATHS[RAW_SEGMENT_ID]: RAW_SEGMENT_1_BYTES,
        SYNTHETIC_PATHS["synthetic-vendor-event-1"]: build_vendor_event(RAW_SEGMENT_1_BYTES),
        SYNTHETIC_PATHS["synthetic-usage-reported-cost-1"]: USAGE_REPORTED_COST_TEXT.encode("utf-8"),
        SYNTHETIC_PATHS[STUB_ENTRY_COPY_ID]: build_stub_entry_copy(),
    }


def build_doc_synthetic_files(doc_text: str) -> Dict[str, bytes]:
    """取自设计文档代码块的合成样本。"""
    return {spec.path: doc_code_block(doc_text, *spec.doc_source)
            for spec in SYNTHETIC_SPECS if spec.doc_source is not None}


# ---------------------------------------------------------------------------
# 单一故障负例（negative/protocol/）
# ---------------------------------------------------------------------------

Transform = Callable[[bytes], bytes]


def _b(value: Any) -> bytes:
    return value if isinstance(value, bytes) else str(value).encode("utf-8")


def sub(old: Any, new: Any) -> Transform:
    old_b, new_b = _b(old), _b(new)

    def transform(data: bytes) -> bytes:
        if data.count(old_b) != 1:
            raise AssertionError("单一故障变体的锚点必须恰好出现一次：%r" % old_b)
        return data.replace(old_b, new_b, 1)
    return transform


def insert_after(anchor: Any, text: Any) -> Transform:
    return sub(anchor, _b(anchor) + _b(text))


def chain(*transforms: Transform) -> Transform:
    """依次应用多个字节变换。只用于“一个目标条件需要改动几处字节才能不同时违反别的规则”的变体，
    每个变体的 fault 说明必须写明为什么需要这几处改动。"""
    def transform(data: bytes) -> bytes:
        for step in transforms:
            data = step(data)
        return data
    return transform


def prefix_bom(data: bytes) -> bytes:
    if data.startswith(b"\xef\xbb\xbf"):
        raise AssertionError("来源已带 BOM")
    return b"\xef\xbb\xbf" + data


def append(tail: Any) -> Transform:
    def transform(data: bytes) -> bytes:
        return data + _b(tail)
    return transform


def lf_to_crlf(data: bytes) -> bytes:
    if b"\r" in data:
        raise AssertionError("来源已含 CR")
    return data.replace(b"\n", b"\r\n")


def drop_final_lf(data: bytes) -> bytes:
    if not data.endswith(b"\n") or data.endswith(b"\r\n"):
        raise AssertionError("来源不是以单个 LF 结尾")
    return data[:-1]


def replace_raw_refs_line(new_array: bytes) -> Transform:
    """把唯一一行 `  "raw_refs": [...],`（数组写在同一行内）的数组整体替换。"""
    def transform(data: bytes) -> bytes:
        lines = data.split(b"\n")
        hits = [i for i, line in enumerate(lines) if line.startswith(b'  "raw_refs": [') and line.endswith(b"],")]
        if len(hits) != 1:
            raise AssertionError("raw_refs 行必须恰好出现一次")
        lines[hits[0]] = b'  "raw_refs": ' + new_array + b","
        return b"\n".join(lines)
    return transform


class NegativeSpec(NamedTuple):
    """单一故障负例。code、field、reason 三项都要与入口抛出的 ProtocolError 相同：只断言 code 与 field 时，
    同码同位置的另一条规则可能掩盖目标规则（设计文档 7.4“只改变一个目标条件”）。"""
    group: str
    slug: str
    base_id: str
    transform: Transform
    entry: str
    code: str
    field: Optional[str]
    reason: str
    fault: str
    #: 条目的 integrity（裁决 R-P11）。默认 complete：负例文件是一份完整的、带单一故障的输入；只有代表“被截断或
    #: 被破坏的证据/引用字节”的负例登记 truncated 或 corrupted（见文件头说明）。
    integrity: str = "complete"


REQ = "req-11111111111141118111111111111111"
RUN = "run-22222222222242228222222222222222"
_RC = "synthetic-doc-4.1.3-run-context"
_EV = "synthetic-doc-4.3.1-run-event"
_VE = "synthetic-vendor-event-1"
_REF = DOC_REF_ID
_UU = "synthetic-doc-4.3.9-usage-unknown"
_UC = "synthetic-usage-reported-cost-1"
_ER = "synthetic-doc-4.3.6-error-record"
_FM = "synthetic-doc-c.1-manifest-entry-completed"
_SE = STUB_ENTRY_COPY_ID
_REF_PATH = '"path": "tests/fixtures/synthetic-protocol-sample-1.json"'
_RAW_SEG_SHA = P.sha256_hex(RAW_SEGMENT_1_BYTES)
_RAW_SEG_LEN = len(RAW_SEGMENT_1_BYTES)
_EMPTY_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _header_variants(group: str, base: str, entry: str, record_type: str, other_type: str,
                     anchor_line: str, unknown_line: str, unknown_field: str) -> List[NegativeSpec]:
    """记录头与字段封闭：schema_version 为 true/"1"/1.0/2、record_type 不符、未知顶层字段。"""
    return [
        NegativeSpec(group, "schema-version-true", base, sub('"schema_version": 1,', '"schema_version": true,'),
                     entry, "E_SCHEMA_VERSION_TYPE", "/schema_version", "schema_version_not_positive_integer",
                     "schema_version 由整数 1 改为布尔 true"),
        NegativeSpec(group, "schema-version-string", base, sub('"schema_version": 1,', '"schema_version": "1",'),
                     entry, "E_SCHEMA_VERSION_TYPE", "/schema_version", "schema_version_not_positive_integer",
                     "schema_version 由整数 1 改为字符串 \"1\""),
        NegativeSpec(group, "schema-version-float", base, sub('"schema_version": 1,', '"schema_version": 1.0,'),
                     entry, "E_SCHEMA_VERSION_TYPE", "/schema_version", "schema_version_not_positive_integer",
                     "schema_version 由整数 1 改为实数 1.0"),
        NegativeSpec(group, "schema-version-2", base, sub('"schema_version": 1,', '"schema_version": 2,'),
                     entry, "E_SCHEMA_VERSION_UNSUPPORTED", "/schema_version", "schema_version_unsupported",
                     "schema_version 改为未知版本 2（不得回退到 v1 解释）"),
        NegativeSpec(group, "record-type-mismatch", base,
                     sub('"record_type": "%s",' % record_type, '"record_type": "%s",' % other_type),
                     entry, "E_SCHEMA_RECORD_TYPE", "/record_type", "record_type_mismatch",
                     "record_type 由 %s 改为 %s，与受信入口声明的类型不符" % (record_type, other_type)),
        NegativeSpec(group, "unknown-top-level-field", base, insert_after(anchor_line, unknown_line),
                     entry, "E_SCHEMA_FIELDS", "/" + unknown_field, "unknown_field",
                     "顶层增加未知字段 %s（不得静默丢弃）" % unknown_field),
    ]


def _path_variants(group: str, base: str, entry: str, anchor: str, field: str) -> List[NegativeSpec]:
    """业务路径的越界与不可移植写法（4.1.5）。anchor 是 "path": "<原值>" 的完整片段。"""
    original = "tests/fixtures/synthetic-protocol-sample-1.json"
    #: (slug, 新的 path 值, 错误码, 原因, 故障说明)
    cases = (
        ("path-parent-segment", "tests/fixtures/../../../synthetic-protocol-sample-1.json", "E_PATH_SYNTAX",
         "invalid_path_component", "path 含 .. 分段（越出仓库根的写法）"),
        ("path-absolute-posix", "/" + original, "E_PATH_SYNTAX", "nonportable_path_syntax",
         "path 改为以 / 开头的绝对路径"),
        ("path-drive-letter", "C:/" + original, "E_PATH_SYNTAX", "nonportable_path_syntax",
         "path 改为带盘符 C: 的绝对路径"),
        ("path-backslash", original.replace("/", "\\\\"), "E_PATH_SYNTAX", "nonportable_path_syntax",
         "path 的分隔符改为反斜杠"),
        ("path-unc", "//server/share/" + original, "E_PATH_SYNTAX", "nonportable_path_syntax",
         "path 改为 UNC 形式 //server/share/…"),
        ("path-ads", original + ":stream", "E_PATH_SYNTAX", "nonportable_path_syntax",
         "path 末尾加 NTFS 备用数据流 :stream"),
        ("path-reserved-device", "tests/fixtures/nul.json", "E_PATH_RESERVED", "reserved_device_name",
         "path 的文件名改为 Windows 保留设备名 nul.json"),
        ("path-trailing-dot", original + ".", "E_PATH_SYNTAX", "segment_ends_with_dot_or_space",
         "path 末尾加一个点（Windows 会静默去掉）"),
        ("path-empty-segment", "tests//fixtures/synthetic-protocol-sample-1.json", "E_PATH_SYNTAX",
         "invalid_path_component", "path 含空分段 //"),
        ("path-nul-char", original + "\\u0000", "E_PATH_SYNTAX", "control_character",
         "path 末尾加 NUL 字符（JSON 转义 \\u0000）"),
    )
    return [NegativeSpec(group, slug, base, sub(anchor, anchor.replace(original, value)), entry, code, field, reason,
                         fault)
            for slug, value, code, reason, fault in cases]


def _amount_variants() -> List[NegativeSpec]:
    anchor = '"amount": "0.00129"'
    cases = (
        ("amount-plus-sign", '"amount": "+0.00129"', "金额带正号 +"),
        ("amount-negative", '"amount": "-0.00129"', "金额带负号（退款/抵扣须由 07 定义独立调整类型）"),
        ("amount-exponent", '"amount": "1.29e-3"', "金额写成指数形式 1.29e-3"),
        ("amount-thousands-separator", '"amount": "1,290.00"', "金额带千分位逗号 1,290.00"),
        ("amount-currency-symbol", '"amount": "$0.00129"', "金额带货币符号 $"),
        ("amount-whitespace", '"amount": " 0.00129"', "金额带前导空格"),
        ("amount-leading-zero", '"amount": "00.00129"', "金额整数部分带多余的前导零"),
        ("amount-json-number", '"amount": 0.00129', "金额写成 JSON 数值（二进制浮点）而不是十进制字符串"),
    )
    return [NegativeSpec("usage-cost", slug, _UC, sub(anchor, new), ENTRY_USAGE, "E_USAGE_VALUE", "/reported_cost",
                         "amount_not_plain_nonnegative_decimal", fault) for slug, new, fault in cases]


_C1_PROVES = '"proves": ["exact_byte_digest", "synthetic_provenance_label"],'

#: R-P11 第 5 步的两条规则，目标条件本身由两处字节构成（“不完整”与“声称完整运行流”；“未保留协议结构”与“声称协议
#: 字段语义”）。负例依次应用两步；R11Tests 核对每一步单独应用时条目仍被接受，保证负例只违反这一个目标条件。
R11_TWO_STEP_VARIANTS: Dict[str, Tuple[Transform, Transform]] = {
    "incomplete-claims-complete-stream": (
        sub('"integrity": "complete",', '"integrity": "partial",'),
        sub(_C1_PROVES, _C1_PROVES[:-2] + ', "complete_run_stream"],'),
    ),
    "structure-not-preserved-claims-field-semantics": (
        sub('"protocol_structure_preserved": null', '"protocol_structure_preserved": false'),
        sub(_C1_PROVES, _C1_PROVES[:-2] + ', "protocol_field_semantics"],'),
    ),
}

NEGATIVE_SPECS: Tuple[NegativeSpec, ...] = tuple(
    # --- run-context（4.1.3） ---
    _header_variants("run-context", _RC, ENTRY_RUN_CONTEXT, "run-context", "run-event",
                     '  "record_type": "run-context",\n', '  "family": "codekit-public",\n', "family")
    + [
        NegativeSpec("run-context", "json-duplicate-key-role", _RC,
                     insert_after('  "role": "planner",\n', '  "role": "executor",\n'), ENTRY_RUN_CONTEXT,
                     "E_JSON_DUPLICATE_KEY", "/role", "duplicate_object_member", "顶层重复键 role：后写的 executor 不得“后者生效”"),
        NegativeSpec("run-context", "request-id-trailing-newline", _RC, sub('"%s"' % REQ, '"%s\\n"' % REQ),
                     ENTRY_RUN_CONTEXT, "E_ID_SYNTAX", "/request_id", "identifier_syntax",
                     "request_id 末尾多一个换行（JSON 转义 \\n）"),
        NegativeSpec("run-context", "run-id-uppercase-hex", _RC, sub('"%s"' % RUN, '"%sA"' % RUN[:-1]),
                     ENTRY_RUN_CONTEXT, "E_ID_SYNTAX", "/run_id", "identifier_syntax", "run_id 的最后一位十六进制改为大写 A"),
        NegativeSpec("run-context", "task-id-syntax", _RC, sub('"baseline-review"', '"Baseline_Review"'),
                     ENTRY_RUN_CONTEXT, "E_ID_SYNTAX", "/task_id", "identifier_syntax", "task_id 含大写与下划线"),
        NegativeSpec("run-context", "plan-version-float", _RC, sub('"plan_version": null,', '"plan_version": 1.0,'),
                     ENTRY_RUN_CONTEXT, "E_SCHEMA_TYPE", "/plan_version", "exact_integer_required",
                     "plan_version 由 null 改为实数 1.0"),
        NegativeSpec("run-context", "plan-version-zero", _RC, sub('"plan_version": null,', '"plan_version": 0,'),
                     ENTRY_RUN_CONTEXT, "E_INTEGER_RANGE", "/plan_version", "integer_out_of_range",
                     "plan_version 由 null 改为 0（下界为 1）"),
        NegativeSpec("run-context", "attempt-negative", _RC, sub('"attempt": null,', '"attempt": -1,'),
                     ENTRY_RUN_CONTEXT, "E_INTEGER_RANGE", "/attempt", "integer_out_of_range", "attempt 由 null 改为 -1"),
        NegativeSpec("run-context", "role-unknown", _RC, sub('"role": "planner",', '"role": "admin",'),
                     ENTRY_RUN_CONTEXT, "E_SCHEMA_FIELDS", "/role", "value_not_in_enum", "role 改为封闭枚举之外的 admin"),
        NegativeSpec("run-context", "platform-uname-spelling", _RC, sub('"platform": "linux",', '"platform": "Linux",'),
                     ENTRY_RUN_CONTEXT, "E_SCHEMA_FIELDS", "/platform", "value_not_in_enum",
                     "platform 改为 uname 拼写 Linux（新协议只接受映射后的 linux，不猜测）"),
        NegativeSpec("run-context", "contract-ref-string", _RC,
                     sub('"contract_ref": null', '"contract_ref": ".agent/plans/baseline-review.v1.json"'),
                     ENTRY_RUN_CONTEXT, "E_SCHEMA_TYPE", "/contract_ref", "object_required",
                     "contract_ref 由 null 改为路径字符串（必须是 ResourceRef 对象）"),
    ]
    # --- run-event 核心事件（4.3.1） ---
    + _header_variants("run-event", _EV, ENTRY_RUN_EVENT_CORE, "run-event", "usage-observation",
                       '  "seq": 1,\n', '  "vendor_seq": 7,\n', "vendor_seq")
    + [
        NegativeSpec("run-event", "json-duplicate-key-seq", _EV, insert_after('  "seq": 1,\n', '  "seq": 2,\n'),
                     ENTRY_RUN_EVENT_CORE, "E_JSON_DUPLICATE_KEY", "/seq", "duplicate_object_member",
                     "顶层重复键 seq（1 与 2）"),
        NegativeSpec("run-event", "json-escaped-duplicate-key-seq", _EV,
                     insert_after('  "seq": 1,\n', '  "\\u0073eq": 1,\n'), ENTRY_RUN_EVENT_CORE,
                     "E_JSON_DUPLICATE_KEY", "/seq", "duplicate_object_member", "转义后相同的重复键：\\u0073eq 与 seq（值也相同）"),
        NegativeSpec("run-event", "json-nested-duplicate-key", _EV,
                     sub('{"example_only": true}', '{"example_only": true, "example_only": true}'),
                     ENTRY_RUN_EVENT_CORE, "E_JSON_DUPLICATE_KEY", "/payload/example_only", "duplicate_object_member",
                     "payload 内的嵌套重复键 example_only"),
        NegativeSpec("run-event", "json-utf8-bom", _EV, prefix_bom, ENTRY_RUN_EVENT_CORE, "E_JSON_BOM", None,
                     "utf8_bom_not_accepted",
                     "文件开头加 UTF-8 BOM（EF BB BF）"),
        NegativeSpec("run-event", "json-invalid-utf8", _EV, sub(b'"role": "planner",', b'"role": "planner\xff",'),
                     ENTRY_RUN_EVENT_CORE, "E_JSON_ENCODING", None, "utf8_decoding_failed",
                     "role 的字符串中插入字节 0xFF（不是有效 UTF-8）"),
        NegativeSpec("run-event", "json-lone-surrogate", _EV,
                     sub('{"example_only": true}', '{"example_only": "\\ud800"}'), ENTRY_RUN_EVENT_CORE,
                     "E_JSON_UNICODE", "/payload/example_only", "unpaired_surrogate", "payload 值改为孤立代理项 \\ud800"),
        NegativeSpec("run-event", "json-trailing-second-document", _EV, append("{}\n"), ENTRY_RUN_EVENT_CORE,
                     "E_JSON_SYNTAX", None, "syntax_error", "文件末尾追加第二个 JSON 文档 {}"),
        NegativeSpec("run-event", "json-nan", _EV, sub('"seq": 1,', '"seq": NaN,'), ENTRY_RUN_EVENT_CORE,
                     "E_JSON_NON_FINITE", "/seq", "non_finite_literal", "seq 改为 NaN"),
        NegativeSpec("run-event", "json-negative-infinity", _EV, sub('"seq": 1,', '"seq": -Infinity,'),
                     ENTRY_RUN_EVENT_CORE, "E_JSON_NON_FINITE", "/seq", "non_finite_literal", "seq 改为 -Infinity"),
        NegativeSpec("run-event", "json-overflow-1e10000", _EV, sub('"seq": 1,', '"seq": 1e10000,'),
                     ENTRY_RUN_EVENT_CORE, "E_JSON_NON_FINITE", "/seq", "numeric_overflow", "seq 改为 1e10000（解析后溢出为无穷大）"),
        NegativeSpec("run-event", "json-integer-out-of-range", _EV, sub('"seq": 1,', '"seq": 9007199254740992,'),
                     ENTRY_RUN_EVENT_CORE, "E_INTEGER_RANGE", "/seq", "integer_outside_profile",
                     "seq 改为 2^53（超出 0..2^53-1）"),
        NegativeSpec("run-event", "json-depth-limit", _EV,
                     sub('{"example_only": true}', '{"example_only": %s%s}' % ("[" * 63, "]" * 63)),
                     ENTRY_RUN_EVENT_CORE, "E_JSON_LIMIT", "/payload/example_only" + "/0" * 62,
                     "nesting_limit_exceeded",
                     "payload 值改为 63 层嵌套数组，整条记录 65 层（上限 64）"),
        NegativeSpec("run-event", "request-id-trailing-newline", _EV, sub('"%s"' % REQ, '"%s\\n"' % REQ),
                     ENTRY_RUN_EVENT_CORE, "E_ID_SYNTAX", "/request_id", "identifier_syntax",
                     "request_id 末尾多一个换行（JSON 转义 \\n）"),
        NegativeSpec("run-event", "seq-zero", _EV, sub('"seq": 1,', '"seq": 0,'), ENTRY_RUN_EVENT_CORE,
                     "E_INTEGER_RANGE", "/seq", "integer_out_of_range", "seq 改为 0（从 1 开始）"),
        NegativeSpec("run-event", "seq-float", _EV, sub('"seq": 1,', '"seq": 1.0,'), ENTRY_RUN_EVENT_CORE,
                     "E_SCHEMA_TYPE", "/seq", "exact_integer_required", "seq 改为实数 1.0"),
        NegativeSpec("run-event", "seq-string", _EV, sub('"seq": 1,', '"seq": "1",'), ENTRY_RUN_EVENT_CORE,
                     "E_SCHEMA_TYPE", "/seq", "exact_integer_required", "seq 改为字符串 \"1\""),
        NegativeSpec("run-event", "observed-at-invalid-date", _EV,
                     sub('"2026-09-25T00:00:00.000000Z"', '"2026-02-30T00:00:00.000000Z"'), ENTRY_RUN_EVENT_CORE,
                     "E_TIME_FORMAT", "/observed_at", "invalid_calendar_value", "observed_at 改为不存在的日期 2026-02-30"),
        NegativeSpec("run-event", "observed-at-offset-suffix", _EV,
                     sub('"2026-09-25T00:00:00.000000Z"', '"2026-09-25T00:00:00.000000+00:00"'),
                     ENTRY_RUN_EVENT_CORE, "E_TIME_FORMAT", "/observed_at", "fixed_utc_format_required",
                     "observed_at 用 +00:00 代替固定的 Z"),
        NegativeSpec("run-event", "role-unknown", _EV, sub('"role": "planner",', '"role": "admin",'),
                     ENTRY_RUN_EVENT_CORE, "E_SCHEMA_FIELDS", "/role", "value_not_in_enum", "role 改为封闭枚举之外的 admin"),
        NegativeSpec("run-event", "source-kind-unknown", _EV, sub('"source_kind": "core",', '"source_kind": "plugin",'),
                     ENTRY_RUN_EVENT_CORE, "E_SCHEMA_FIELDS", "/source_kind", "value_not_in_enum",
                     "source_kind 改为 plugin"),
        NegativeSpec("run-event", "integrity-unknown", _EV, sub('"integrity": "complete",', '"integrity": "ok",'),
                     ENTRY_RUN_EVENT_CORE, "E_SCHEMA_FIELDS", "/integrity", "value_not_in_enum", "integrity 改为 ok"),
        NegativeSpec("run-event", "payload-not-object", _EV, sub('{"example_only": true}', '["example_only"]'),
                     ENTRY_RUN_EVENT_CORE, "E_SCHEMA_TYPE", "/payload", "object_required", "payload 改为数组"),
        NegativeSpec("run-event", "raw-refs-not-array", _EV, sub('"raw_refs": [],', '"raw_refs": {},'),
                     ENTRY_RUN_EVENT_CORE, "E_SCHEMA_TYPE", "/raw_refs", "array_required", "raw_refs 改为对象"),
        NegativeSpec("run-event", "type-unregistered", _EV, sub('"type": "run.prepared",', '"type": "run.started",'),
                     ENTRY_RUN_EVENT_CORE, "E_EVENT_TYPE_UNKNOWN", "/type", "event_type_not_registered",
                     "type 改为未登记的 run.started"),
        # 基样本用 synthetic-vendor-event-1 而不是 4.3.1：4.3.1 的 adapter_revision 为 null、raw_refs 为空且
        # integrity=complete，把它的 source_kind 改成 vendor 会同时违反 vendor 证据规则（多故障）。
        NegativeSpec("run-event", "core-type-claimed-by-vendor", _VE,
                     sub('"type": "%s",' % SYNTHETIC_VENDOR_EVENT_TYPE, '"type": "run.prepared",'),
                     ENTRY_RUN_EVENT_VENDOR_TYPED, "E_EVENT_SOURCE", "/source_kind", "source_not_allowed_for_type",
                     "vendor 事件（adapter_revision、raw_refs、integrity 都满足 vendor 证据规则）把 type 由测试内登记"
                     "的合成 vendor 类型改为只允许 core 的 run.prepared（冒用核心事件类型）"),
    ]
    # --- vendor 事件与 raw_refs（4.3.1、4.3.3） ---
    + [
        NegativeSpec("vendor-event", "adapter-revision-null", _VE,
                     sub('"adapter_revision": "synthetic-adapter-r1"', '"adapter_revision": null'),
                     ENTRY_RUN_EVENT_VENDOR, "E_EVENT_EVIDENCE_MISSING", "/adapter_revision",
                     "vendor_event_requires_adapter_revision",
                     "vendor 事件缺 adapter_revision（改为 null）"),
        NegativeSpec("vendor-event", "complete-without-raw-refs", _VE, replace_raw_refs_line(b"[]"),
                     ENTRY_RUN_EVENT_VENDOR, "E_EVENT_EVIDENCE_MISSING", "/raw_refs",
                     "complete_vendor_event_requires_raw_refs",
                     "raw_refs 改为空数组，integrity 仍声称 complete"),
        NegativeSpec("vendor-event", "raw-span-exceeds-segment", _VE,
                     sub('"byte_end": %d,' % _RAW_SEG_LEN, '"byte_end": %d,' % (_RAW_SEG_LEN + 1)),
                     ENTRY_RUN_EVENT_VENDOR, "E_EVENT_RAW_RANGE", "/raw_refs/0/byte_end", "range_exceeds_segment",
                     "byte_end 比被引用分段的实际字节数多 1"),
        NegativeSpec("vendor-event", "raw-span-empty", _VE,
                     sub('"byte_start": 0,', '"byte_start": %d,' % _RAW_SEG_LEN), ENTRY_RUN_EVENT_VENDOR,
                     "E_EVENT_RAW_RANGE", "/raw_refs/0/byte_end", "invalid_byte_end", "byte_start 改为等于 byte_end（空区间）"),
        NegativeSpec("vendor-event", "raw-span-negative-start", _VE, sub('"byte_start": 0,', '"byte_start": -1,'),
                     ENTRY_RUN_EVENT_VENDOR, "E_EVENT_RAW_RANGE", "/raw_refs/0/byte_start", "invalid_byte_start",
                     "byte_start 改为 -1"),
        NegativeSpec("vendor-event", "raw-ref-unknown-version", _VE, sub(_RAW_SEG_SHA, _EMPTY_SHA),
                     ENTRY_RUN_EVENT_VENDOR, "E_EVENT_RAW_REF_UNKNOWN", "/raw_refs/0/ref/sha256",
                     "segment_version_unknown",
                     "raw_refs 引用的分段摘要改为未封存的版本（空字节的 SHA-256）"),
        NegativeSpec("vendor-event", "raw-stream-invalid", _VE, sub('"stream": "stdout"', '"stream": "stdin"'),
                     ENTRY_RUN_EVENT_VENDOR, "E_SCHEMA_FIELDS", "/raw_refs/0/stream", "value_not_in_enum",
                     "stream 改为 stdin"),
        NegativeSpec("vendor-event", "raw-ref-path-parent-segment", _VE,
                     sub('"path": "%s"' % SYNTHETIC_PATHS[RAW_SEGMENT_ID],
                         '"path": "%s"' % (FIXTURE_DIR + "/synthetic/../../../../raw-segment-1.jsonl")),
                     ENTRY_RUN_EVENT_VENDOR, "E_PATH_SYNTAX", "/raw_refs/0/ref/path", "invalid_path_component",
                     "raw_refs 的 ref.path 含 .. 分段（越出仓库根的写法）"),
        NegativeSpec("vendor-event", "role-null", _VE, sub('"role": "planner",', '"role": null,'),
                     ENTRY_RUN_EVENT_VENDOR, "E_SCHEMA_FIELDS", "/role", "vendor_event_requires_role",
                     "vendor 事件的 role 改为 null（4.3.1 只允许无角色的核心事件不带 role；vendor 事件置空 role 会脱离"
                     "角色绑定。JSON Schema 允许 null，这是 Schema 之外的领域检查）"),
    ]
    # --- ResourceRef（4.2.1、4.2.2） ---
    + [
        NegativeSpec("resource-ref", "sha256-uppercase", _REF, sub(SAMPLE_1_SHA256, SAMPLE_1_SHA256.upper()),
                     ENTRY_RESOURCE_REF, "E_RESOURCE_FIELD", "/sha256", "resource_field_syntax", "sha256 改为大写十六进制"),
        NegativeSpec("resource-ref", "sha256-short", _REF, sub(SAMPLE_1_SHA256, SAMPLE_1_SHA256[:12]),
                     ENTRY_RESOURCE_REF, "E_RESOURCE_FIELD", "/sha256", "resource_field_syntax", "sha256 截成前 12 位"),
        NegativeSpec("resource-ref", "sha256-prefixed", _REF, sub(SAMPLE_1_SHA256, "sha256:" + SAMPLE_1_SHA256),
                     ENTRY_RESOURCE_REF, "E_RESOURCE_FIELD", "/sha256", "resource_field_syntax", "sha256 加 sha256: 前缀"),
        NegativeSpec("resource-ref", "sha256-trailing-newline", _REF,
                     sub('"%s"' % SAMPLE_1_SHA256, '"%s\\n"' % SAMPLE_1_SHA256), ENTRY_RESOURCE_REF,
                     "E_RESOURCE_FIELD", "/sha256", "resource_field_syntax", "sha256 末尾多一个换行（JSON 转义 \\n）"),
        NegativeSpec("resource-ref", "sha256-wrong-value", _REF, sub(SAMPLE_1_SHA256, SAMPLE_1_SHA256[:-1] + "0"),
                     ENTRY_VERIFY_REF, "E_RESOURCE_HASH_MISMATCH", "/sha256", "digest_mismatch",
                     "sha256 长度与格式正确，但最后一位改为 0，与 synthetic-protocol-sample-1 的字节不符"),
        NegativeSpec("resource-ref", "kind-unregistered", _REF, sub('"kind": "fixture",', '"kind": "plugin-lock",'),
                     ENTRY_RESOURCE_REF, "E_RESOURCE_KIND", "/kind", "resource_kind_not_registered",
                     "kind 改为 01 默认注册表中没有的 plugin-lock"),
        NegativeSpec("resource-ref", "kind-syntax", _REF, sub('"kind": "fixture",', '"kind": "Fixture",'),
                     ENTRY_RESOURCE_REF, "E_RESOURCE_FIELD", "/kind", "resource_field_syntax", "kind 改为首字母大写"),
        NegativeSpec("resource-ref", "id-syntax", _REF,
                     sub('"id": "synthetic-protocol-sample-1",', '"id": "Synthetic Sample 1",'), ENTRY_RESOURCE_REF,
                     "E_RESOURCE_FIELD", "/id", "resource_field_syntax", "id 含大写与空格"),
        NegativeSpec("resource-ref", "file-kind-missing-path", _REF, sub(',\n  %s\n}' % _REF_PATH, "\n}"),
                     ENTRY_RESOURCE_REF, "E_RESOURCE_PATH_REQUIRED", "/path", "file_resource_requires_path",
                     "文件型 kind（fixture）去掉 path"),
        NegativeSpec("resource-ref", "unknown-field", _REF, insert_after('  "kind": "fixture",\n', '  "size": 34,\n'),
                     ENTRY_RESOURCE_REF, "E_SCHEMA_FIELDS", "/size", "unknown_field", "增加未知字段 size"),
    ]
    + _path_variants("resource-ref", _REF, ENTRY_RESOURCE_REF, _REF_PATH, "/path")
    # --- usage-observation 全未知样例（4.3.9） ---
    + _header_variants("usage-unknown", _UU, ENTRY_USAGE, "usage-observation", "run-event",
                       '  "usage_id": "usage-synthetic-unknown-1",\n', '  "account_scope": null,\n', "account_scope")
    + [
        NegativeSpec("usage-unknown", "run-id-trailing-newline", _UU, sub('"%s"' % RUN, '"%s\\n"' % RUN),
                     ENTRY_USAGE, "E_ID_SYNTAX", "/run_id", "identifier_syntax", "run_id 末尾多一个换行（JSON 转义 \\n）"),
        NegativeSpec("usage-unknown", "unknown-reasons-extra-key", _UU,
                     insert_after('  "unknown_reasons": {\n', '    "billing_override": "manual",\n'), ENTRY_USAGE,
                     "E_USAGE_UNKNOWN_REASON", "/unknown_reasons", "reason_key_not_allowed",
                     "unknown_reasons 增加不属于可未知字段的键 billing_override（不得借此塞入控制参数）"),
        NegativeSpec("usage-unknown", "unknown-reason-missing", _UU,
                     sub('    "model": "synthetic_example_without_vendor_evidence",\n', ""), ENTRY_USAGE,
                     "E_USAGE_UNKNOWN_REASON", "/model", "unknown_field_requires_reason",
                     "删去 model 的未知原因（model 仍为 null）"),
        NegativeSpec("usage-unknown", "unknown-reason-empty-text", _UU,
                     sub('"reported_cost": "not_reported",', '"reported_cost": "",'), ENTRY_USAGE,
                     "E_USAGE_UNKNOWN_REASON", "/unknown_reasons/reported_cost", "reason_text_invalid",
                     "reported_cost 的未知原因改为空字符串"),
        NegativeSpec("usage-unknown", "unknown-counter-filled-with-zero", _UU,
                     sub('"input_tokens": null,', '"input_tokens": 0,'), ENTRY_USAGE,
                     "E_USAGE_UNKNOWN_REASON", "/unknown_reasons/input_tokens", "reason_given_for_known_field",
                     "input_tokens 由 null 补成 0，原因仍写 not_reported（0 表示有证据的零，未知不得补零）"),
        NegativeSpec("usage-unknown", "observation-kind-unknown-value", _UU,
                     sub('"observation_kind": "unknown",', '"observation_kind": "total",'), ENTRY_USAGE,
                     "E_SCHEMA_FIELDS", "/observation_kind", "value_not_in_enum", "observation_kind 改为封闭枚举之外的 total"),
        NegativeSpec("usage-unknown", "billing-source-unknown-value", _UU,
                     sub('"billing_source": "unavailable",', '"billing_source": "free",'), ENTRY_USAGE,
                     "E_SCHEMA_FIELDS", "/billing_source", "value_not_in_enum", "billing_source 改为封闭枚举之外的 free"),
    ]
    # --- usage-observation 已知费用（4.3.7） ---
    + _amount_variants()
    + [
        NegativeSpec("usage-cost", "currency-lowercase", _UC, sub('"currency": "USD"', '"currency": "usd"'),
                     ENTRY_USAGE, "E_USAGE_VALUE", "/reported_cost", "currency_code_invalid", "币种改为小写 usd"),
        NegativeSpec("usage-cost", "money-extra-field", _UC,
                     sub('"currency": "USD"}', '"currency": "USD", "tax": "0"}'), ENTRY_USAGE, "E_USAGE_VALUE",
                     "/reported_cost", "money_object_required", "reported_cost 增加字段 tax"),
        NegativeSpec("usage-cost", "estimate-as-reported", _UC,
                     sub('"billing_source": "vendor_reported",', '"billing_source": "adapter_estimated",'),
                     ENTRY_USAGE, "E_USAGE_VALUE", "/reported_cost", "reported_cost_requires_vendor_or_invoice_source",
                     "billing_source 改为 adapter_estimated，reported_cost 不变（估算冒充实际费用）"),
        NegativeSpec("usage-cost", "counter-negative", _UC, sub('"input_tokens": 1000,', '"input_tokens": -1,'),
                     ENTRY_USAGE, "E_INTEGER_RANGE", "/input_tokens", "integer_out_of_range", "input_tokens 改为 -1"),
        NegativeSpec("usage-cost", "counter-float", _UC, sub('"input_tokens": 1000,', '"input_tokens": 1000.0,'),
                     ENTRY_USAGE, "E_SCHEMA_TYPE", "/input_tokens", "exact_integer_required",
                     "input_tokens 改为实数 1000.0"),
        NegativeSpec("usage-cost", "includes-flag-string", _UC,
                     sub('"input_includes_cache": true,', '"input_includes_cache": "yes",'), ENTRY_USAGE,
                     "E_SCHEMA_TYPE", "/input_includes_cache", "boolean_required", "input_includes_cache 改为字符串 yes"),
        NegativeSpec("usage-cost", "supersedes-self", _UC,
                     sub('"supersedes_usage_id": null,', '"supersedes_usage_id": "usage-synthetic-reported-1",'),
                     ENTRY_USAGE, "E_USAGE_CONFLICT", "/supersedes_usage_id", "observation_supersedes_itself",
                     "supersedes_usage_id 指向自身"),
        NegativeSpec("usage-cost", "reason-for-known-counter", _UC,
                     insert_after('  "unknown_reasons": {\n', '    "input_tokens": "not_reported",\n'), ENTRY_USAGE,
                     "E_USAGE_UNKNOWN_REASON", "/unknown_reasons/input_tokens", "reason_given_for_known_field",
                     "给已知的 input_tokens（1000）写未知原因"),
        NegativeSpec("usage-cost", "evidence-ref-kind-unregistered", _UC,
                     sub('"evidence_refs": []',
                         '"evidence_refs": [{"kind": "vendor-bill", "id": "synthetic-bill-1", "sha256": "%s"}]'
                         % _EMPTY_SHA),
                     ENTRY_USAGE, "E_RESOURCE_KIND", "/evidence_refs/0/kind", "resource_kind_not_registered",
                     "evidence_refs 增加 kind 未登记（vendor-bill）的引用"),
    ]
    # --- 结构化错误（4.3.6） ---
    + [
        NegativeSpec("error-record", "json-nested-duplicate-key", _ER,
                     insert_after('    "reason": "duplicate_object_member",\n', '    "reason": "retry_allowed",\n'),
                     ENTRY_ERROR_RECORD, "E_JSON_DUPLICATE_KEY", "/details/reason", "duplicate_object_member",
                     "details 内的重复键 reason"),
    ]
    # --- fixture manifest 条目（附录 C.1、4.3.3） ---
    + [
        NegativeSpec("fixture-manifest-entry", "synthetic-claims-captured-representation", _FM,
                     sub('"representation": "synthetic_fixture",', '"representation": "captured_raw",'),
                     ENTRY_MANIFEST_ENTRY, "E_PROVENANCE_CLAIM", "/representation",
                     "synthetic_requires_synthetic_fixture",
                     "合成样本把 representation 写成 captured_raw（冒充采集原件）"),
        NegativeSpec("fixture-manifest-entry", "synthetic-relabelled-captured", _FM,
                     chain(sub('"class": "synthetic",', '"class": "captured",'),
                           sub('"source_test_id": null,', '"source_test_id": "synthetic-capture-session-1",')),
                     ENTRY_MANIFEST_ENTRY, "E_PROVENANCE_CLAIM", "/representation",
                     "captured_requires_captured_redacted_or_normalized",
                     "合成样本把 origin.class 改成 captured，representation 仍是 synthetic_fixture；同时补上 "
                     "source_test_id，使 captured 的来源要求（captured_requires_source）成立，只留下“captured 必须是 "
                     "captured_raw、redacted_raw 或 normalized_event”这一个条件不符"),
        NegativeSpec("fixture-manifest-entry", "synthetic-claims-vendor-protocol", _FM,
                     sub('"proves": ["exact_byte_digest", "synthetic_provenance_label"],',
                         '"proves": ["exact_byte_digest", "synthetic_provenance_label", "vendor_protocol"],'),
                     ENTRY_MANIFEST_ENTRY, "E_PROVENANCE_CLAIM", "/proves", "synthetic_cannot_prove_real_compatibility",
                     "合成样本在 proves 中声称 vendor_protocol"),
        NegativeSpec("fixture-manifest-entry", "synthetic-claims-legacy-judgment", _FM,
                     sub('"proves": ["exact_byte_digest", "synthetic_provenance_label"],',
                         '"proves": ["exact_byte_digest", "synthetic_provenance_label", "legacy_contract_judgment"],'),
                     ENTRY_MANIFEST_ENTRY, "E_PROVENANCE_CLAIM", "/proves", "synthetic_cannot_prove_real_compatibility",
                     "合成样本在 proves 中声称 legacy_ 前缀的能力"),
        NegativeSpec("fixture-manifest-entry", "claim-both-proved-and-not", _FM,
                     sub('"legacy_dispatch_behavior"],', '"legacy_dispatch_behavior", "exact_byte_digest"],'),
                     ENTRY_MANIFEST_ENTRY, "E_PROVENANCE_CLAIM", "/proves", "claim_both_proved_and_not_proved",
                     "does_not_prove 增加 proves 中已有的 exact_byte_digest（同一能力既声称证明又声称不证明；"
                     "不引入 real_ 类声明，避免同时触发合成样本的真实兼容声明规则）"),
        NegativeSpec("fixture-manifest-entry", "redaction-applied-without-rule", _FM,
                     sub('"applied": false,', '"applied": true,'), ENTRY_MANIFEST_ENTRY, "E_PROVENANCE_CLAIM",
                     "/redaction/rule_revision", "redaction_requires_rule_revision",
                     "redaction.applied 改为 true，rule_revision 仍为 null"),
        NegativeSpec("fixture-manifest-entry", "source-revision-short", _FM,
                     sub('"source_revision": null,', '"source_revision": "a4fa199",'), ENTRY_MANIFEST_ENTRY,
                     "E_GIT_OID_SYNTAX", "/origin/source_revision", "full_lowercase_oid_required",
                     "source_revision 写成 7 位短 OID"),
        NegativeSpec("fixture-manifest-entry", "resource-kind-not-fixture", _FM,
                     sub('"kind": "fixture",', '"kind": "public-schema",'), ENTRY_MANIFEST_ENTRY, "E_RESOURCE_KIND",
                     "/resource/kind", "fixture_resource_kind_required",
                     "resource.kind 改为已登记但不是 fixture 的 public-schema"),
        NegativeSpec("fixture-manifest-entry", "accept-with-code", _FM,
                     sub('"code": null', '"code": "E_JSON_SYNTAX"'), ENTRY_MANIFEST_ENTRY, "E_SCHEMA_FIELDS",
                     "/expected/code", "accept_must_not_carry_code", "expected.outcome 为 accept 却带错误码"),
        NegativeSpec("fixture-manifest-entry", "origin-unknown-field", _FM,
                     insert_after('    "class": "synthetic",\n', '    "captured_at": null,\n'), ENTRY_MANIFEST_ENTRY,
                     "E_SCHEMA_FIELDS", "/origin/captured_at", "unknown_field", "origin 增加未知字段 captured_at"),
        NegativeSpec("fixture-manifest-entry", "schema-version-true", _FM,
                     sub('"schema_version": 1,', '"schema_version": true,'), ENTRY_MANIFEST_ENTRY,
                     "E_SCHEMA_VERSION_TYPE", "/schema_version", "schema_version_not_positive_integer",
                     "schema_version 由整数 1 改为布尔 true"),
        # 收尾轮（裁决 R-P11）新增字段的单一故障负例；前 7 个从 C.1 补齐条目派生，最后 1 个从 legacy stub 条目副本派生。
        NegativeSpec("fixture-manifest-entry", "integrity-not-in-enum", _FM,
                     sub('"integrity": "complete",', '"integrity": "intact",'), ENTRY_MANIFEST_ENTRY,
                     "E_SCHEMA_FIELDS", "/integrity", "value_not_in_enum",
                     "integrity 改为封闭枚举（complete、partial、truncated、corrupted）之外的 intact"),
        NegativeSpec("fixture-manifest-entry", "platform-scope-empty", _FM,
                     sub('"platform_scope": ["any"],', '"platform_scope": [],'), ENTRY_MANIFEST_ENTRY,
                     "E_SCHEMA_FIELDS", "/platform_scope", "platform_scope_empty", "platform_scope 改为空数组"),
        NegativeSpec("fixture-manifest-entry", "platform-scope-any-with-platform", _FM,
                     sub('"platform_scope": ["any"],', '"platform_scope": ["any", "windows"],'), ENTRY_MANIFEST_ENTRY,
                     "E_SCHEMA_FIELDS", "/platform_scope/0", "platform_scope_any_must_be_alone",
                     "platform_scope 在 any 之外再列 windows（any 必须单独出现）"),
        NegativeSpec("fixture-manifest-entry", "platform-scope-uname-spelling", _FM,
                     sub('"platform_scope": ["any"],', '"platform_scope": ["Windows"],'), ENTRY_MANIFEST_ENTRY,
                     "E_SCHEMA_FIELDS", "/platform_scope/0", "value_not_in_enum",
                     "platform_scope 改为 uname 拼写 Windows（只接受映射后的小写平台名）"),
        NegativeSpec("fixture-manifest-entry", "capture-on-synthetic", _FM,
                     sub('"capture": null',
                         '"capture": {"environment_ref": {"kind": "baseline-evidence", "id": "capture-env-1", '
                         '"sha256": "%s", "path": "evidence/capture-env-1.json"}, "range": "stdout 全部字节"}'
                         % _EMPTY_SHA),
                     ENTRY_MANIFEST_ENTRY, "E_PROVENANCE_CLAIM", "/capture", "capture_only_for_captured",
                     "合成条目的 capture 由 null 改为结构合法的采集记录（引用已登记的 baseline-evidence；只有 captured "
                     "条目可以带 capture）"),
        NegativeSpec("fixture-manifest-entry", "traceable-null", _FM,
                     sub('"traceable": true', '"traceable": null'), ENTRY_MANIFEST_ENTRY,
                     "E_SCHEMA_TYPE", "/origin/traceable", "boolean_required",
                     "origin.traceable 由 true 改为 null（只接受布尔值）"),
        NegativeSpec("fixture-manifest-entry", "capture-field-missing", _FM,
                     sub(',\n  "capture": null\n}', "\n}"), ENTRY_MANIFEST_ENTRY,
                     "E_SCHEMA_FIELDS", "/capture", "missing_field",
                     "删去收尾轮新增的顶层字段 capture（旧结构的条目按缺字段拒绝）"),
        NegativeSpec("fixture-manifest-entry", "legacy-untraceable", _SE,
                     sub('"traceable": true', '"traceable": false'), ENTRY_MANIFEST_ENTRY,
                     "E_PROVENANCE_CLAIM", "/origin/traceable", "traceable_required_for_legacy_or_captured",
                     "legacy-stub-events-ok 条目（legacy 类）的 origin.traceable 改为 false（legacy 与 captured 的来源必须"
                     "可追溯）"),
        NegativeSpec("fixture-manifest-entry", "platform-scope-duplicate", _FM,
                     sub('"platform_scope": ["any"],', '"platform_scope": ["windows", "windows"],'),
                     ENTRY_MANIFEST_ENTRY, "E_SCHEMA_FIELDS", "/platform_scope/1", "duplicate_platform",
                     "platform_scope 改为重复列出 windows（[\"windows\"] 本身合法，只有重复这一个条件不符）"),
        NegativeSpec("fixture-manifest-entry", "incomplete-claims-complete-stream", _FM,
                     chain(*R11_TWO_STEP_VARIANTS["incomplete-claims-complete-stream"]), ENTRY_MANIFEST_ENTRY,
                     "E_PROVENANCE_CLAIM", "/proves", "incomplete_fixture_cannot_prove_complete_stream",
                     "integrity 改为 partial，同时在 proves 中声称 complete_run_stream。目标条件“不完整的样本声称完整运行流”"
                     "本身由两处字节构成：只改 integrity 或只加声明，条目都被接受（R11Tests 逐步核对）"),
        NegativeSpec("fixture-manifest-entry", "structure-not-preserved-claims-field-semantics", _FM,
                     chain(*R11_TWO_STEP_VARIANTS["structure-not-preserved-claims-field-semantics"]),
                     ENTRY_MANIFEST_ENTRY, "E_PROVENANCE_CLAIM", "/proves",
                     "structure_not_preserved_cannot_prove_field_semantics",
                     "redaction.protocol_structure_preserved 由 null 改为 false，同时在 proves 中声称 protocol_field_semantics。"
                     "目标条件本身由两处字节构成：只改任一处，条目都被接受（R11Tests 逐步核对）"),
    ]
    # --- representation=synthetic_fixture 的能力声明（4.3.3）：前两个由产品入口拒绝，第三个由测试层规则拒绝 ---
    + [
        NegativeSpec("fixture-manifest-claims", "legacy-stub-claims-real-cli-compatibility", _SE,
                     chain(sub('    "real_cli_compatibility",\n', ""),
                           sub('    "legacy_event_summary_judgment"\n  ],',
                               '    "legacy_event_summary_judgment",\n    "real_cli_compatibility"\n  ],')),
                     ENTRY_MANIFEST_ENTRY, "E_PROVENANCE_CLAIM", "/proves",
                     "real_compatibility_claim_requires_captured_raw",
                     "legacy-stub-events-ok 条目（stub 生成的流，legacy 类，representation=synthetic_fixture）把 "
                     "real_cli_compatibility 从 does_not_prove 移到 proves。只改变“是否声称真实 CLI 兼容”这一个条件："
                     "若不从 does_not_prove 移除，会同时触发 claim_both_proved_and_not_proved。产品入口按来源类别与表示"
                     "拒绝（只有 captured + captured_raw/redacted_raw 可以声称）"),
        NegativeSpec("fixture-manifest-claims", "legacy-stub-claims-vendor-protocol", _SE,
                     chain(sub('    "vendor_protocol",\n', ""),
                           sub('    "legacy_event_summary_judgment"\n  ],',
                               '    "legacy_event_summary_judgment",\n    "vendor_protocol"\n  ],')),
                     ENTRY_MANIFEST_ENTRY, "E_PROVENANCE_CLAIM", "/proves",
                     "real_compatibility_claim_requires_captured_raw",
                     "legacy-stub-events-ok 条目把 vendor_protocol 从 does_not_prove 移到 proves（只改变“是否声称厂商"
                     "协议兼容”这一个条件）。产品入口按来源类别与表示拒绝"),
        NegativeSpec("fixture-manifest-claims", "legacy-stub-claims-unlisted-legacy-capability", _SE,
                     chain(sub('    "legacy_end_to_end_run",\n', ""),
                           sub('    "legacy_event_summary_judgment"\n  ],',
                               '    "legacy_event_summary_judgment",\n    "legacy_end_to_end_run"\n  ],')),
                     ENTRY_MANIFEST_CLAIMS, "E_PROVENANCE_CLAIM", "/proves", CLAIM_RULE_LEGACY,
                     "legacy-stub-events-ok 条目把 legacy_end_to_end_run 从 does_not_prove 移到 proves（stub 流没有经过 "
                     "pi_dispatch run、预检与 worktree，不能证明端到端运行）。legacy 类可以声明 legacy_ 前缀能力，产品入口"
                     "接受；本清单的测试层规则只放行白名单中的 legacy_ 能力，报 test_rule_legacy_claim_not_whitelisted"),
        NegativeSpec("fixture-manifest-claims", "legacy-stub-claims-uppercase-real-cli-compatibility", _SE,
                     sub('    "legacy_event_summary_judgment"\n  ],',
                         '    "legacy_event_summary_judgment",\n    "REAL_CLI_COMPATIBILITY"\n  ],'),
                     ENTRY_MANIFEST_ENTRY, "E_SCHEMA_FIELDS", "/proves/3", "claim_syntax",
                     "legacy-stub-events-ok 条目在 proves 末尾加上大写变体 REAL_CLI_COMPATIBILITY（只改变“声明拼写不在封闭"
                     "词法内”这一个条件；与 does_not_prove 中的小写 real_cli_compatibility 不是同一字符串，不触发"
                     "claim_both_proved_and_not_proved）。P4 第 3 轮起声明必须符合 [a-z][a-z0-9_]{0,127}，产品入口在结构层"
                     "拒绝，大小写或连字符变体不能绕过按名称与前缀判定的来源规则"),
    ]
    # --- 合成字节与引用摘要（4.2.2、01-F033） ---
    + [
        NegativeSpec("synthetic-sample", "lf-to-crlf", SAMPLE_1_ID, lf_to_crlf, ENTRY_VERIFY_BYTES,
                     "E_RESOURCE_HASH_MISMATCH", "/sha256", "digest_mismatch", "只把行尾 LF 改为 CRLF（摘要必须不符，不得重算期望值）",
                     "corrupted"),
        NegativeSpec("synthetic-sample", "missing-final-lf", SAMPLE_1_ID, drop_final_lf, ENTRY_VERIFY_BYTES,
                     "E_RESOURCE_HASH_MISMATCH", "/sha256", "digest_mismatch", "去掉末尾的 LF", "truncated"),
    ]
)


def negative_fixture_id(spec: NegativeSpec) -> str:
    return "negative-protocol-%s-%s" % (spec.group, spec.slug)


def negative_path(spec: NegativeSpec) -> str:
    base = SYNTHETIC_PATHS[spec.base_id]
    return "%s/%s/%s%s" % (NEG, spec.group, spec.slug, base[base.rindex("."):])


def build_negative_files() -> Dict[str, bytes]:
    """从磁盘上的正例字节派生全部负例。"""
    return {negative_path(spec): spec.transform(read_fixture(SYNTHETIC_PATHS[spec.base_id])) for spec in NEGATIVE_SPECS}


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------

def _resource(fixture_id: str, path: str) -> Dict[str, Any]:
    return {"kind": "fixture", "id": fixture_id, "sha256": P.sha256_hex(read_fixture(path)), "path": path}


def _origin(**fields: Any) -> Dict[str, Any]:
    """origin.traceable 恒为 true（R-P11）：synthetic 按设计文档修订或本文件的确定性构造追溯，negative 按
    derived_from 与本文件的确定性字节变换复现，expected 的 legacy 条目按 source_revision 与生成命令追溯。"""
    origin = {"class": None, "source_revision": None, "source_test_id": None, "source_path": None,
              "generator_revision": None, "derived_from": None, "fault": None, "description": "",
              "traceable": True}
    origin.update(fields)
    return origin


def platform_scope_for(outcome: str) -> List[str]:
    """条目的 platform_scope（R-P11，文档 1.1“平台适用性”）。expected.outcome=legacy-judgment 的期望是旧实现的判断，
    只在 Windows + Python 3.12.10 上锁定（codekit01_legacy.LEGACY_PLATFORM_SCOPE）；其余条目的判断由
    codekit.protocols 的函数对固定字节作出，不依赖平台，登记 ["any"]。都是登记者的声明，不是各平台的实测。"""
    return list(L.LEGACY_PLATFORM_SCOPE) if outcome == "legacy-judgment" else [P.PLATFORM_SCOPE_ANY]


def _entry(fixture_id: str, path: str, origin: Dict[str, Any], redaction_reason: str, proves: Sequence[str],
           does_not_prove: Sequence[str], outcome: str, code: Optional[str], entry: str, *,
           integrity: str = "complete") -> Dict[str, Any]:
    """本文件登记的条目都没有脱敏步骤（applied=false），protocol_structure_preserved 写 null；capture 为 null
    （本清单没有 captured 条目）。"""
    return {
        "schema_version": 1,
        "record_type": "fixture-manifest",
        "fixture_id": fixture_id,
        "origin": origin,
        "representation": "synthetic_fixture",
        "redaction": {"applied": False, "rule_revision": None, "length_changed": None, "reason": redaction_reason,
                      "protocol_structure_preserved": None},
        "resource": _resource(fixture_id, path),
        "proves": list(proves),
        "does_not_prove": list(does_not_prove),
        "expected": {"outcome": outcome, "code": code, "entry": entry, "expected_ref": None},
        "integrity": integrity,
        "platform_scope": platform_scope_for(outcome),
        "capture": None,
    }


_PROJECTION_REDACTION = ("投影不含机器路径、时间或凭据；旧 CLI 输出在临时仓库中取得，生成时断言其中不出现临时仓库的路径"
                         "与提交；stub 事件的 session.cwd 已在事件 fixture 中替换为占位值")


def build_expected_entries() -> List[Dict[str, Any]]:
    """三份预期文件的条目（它们本身也是 tests/fixtures/codekit01/ 下的文件，必须登记）。"""
    return [
        _entry(L.EXPECTED_CONTRACTS_ID, L.EXPECTED_CONTRACTS_PATH,
               _origin(**{"class": "legacy", "source_revision": L.SOURCE_REVISION,
                          "source_test_id": "tests/codekit01_legacy.py --write-expected",
                          "source_path": L.LEGACY_PI_DISPATCH_PATH, "generator_revision": L.PROJECTION_REVISION,
                          "description": "旧实现 scripts/pi_dispatch.py（a4fa199，sha256 %s）对 legacy 合同与合同负例"
                                         "（%d 个用例）的判断投影，投影修订 %s。差分测试以当前 scripts/pi_dispatch.py "
                                         "重算并逐字节比较（01-A02）。" % (L.LEGACY_PI_DISPATCH_SHA256[:12],
                                                                        len(L.contract_cases()),
                                                                        L.PROJECTION_REVISION)}),
               _PROJECTION_REDACTION, ("exact_byte_digest", "legacy_contract_judgment"),
               ("new_protocol_acceptance", "real_repository_state", "cross_platform_bytes"),
               "legacy-judgment", None, ENTRY_LEGACY_CONTRACTS_EXPECTED),
        _entry(L.EXPECTED_EVENTS_ID, L.EXPECTED_EVENTS_PATH,
               _origin(**{"class": "legacy", "source_revision": L.SOURCE_REVISION,
                          "source_test_id": "tests/codekit01_legacy.py --write-expected",
                          "source_path": L.LEGACY_PI_DISPATCH_PATH, "generator_revision": L.PROJECTION_REVISION,
                          "description": "旧实现 summarize_events（scripts/pi_dispatch.py @ a4fa199）对 stub 事件流与事件"
                                         "负例（%d 个用例，每个锁定 expects_settled=true/false/null 三个分支）的判断投影，"
                                         "投影修订 %s。差分测试以当前 scripts/pi_dispatch.py 重算并逐字节比较（01-A02）。"
                                         % (len(L.event_cases()), L.PROJECTION_REVISION)}),
               _PROJECTION_REDACTION, ("exact_byte_digest", "legacy_event_summary_judgment"),
               ("new_protocol_acceptance", "real_cli_compatibility", "vendor_protocol", "cross_platform_bytes"),
               "legacy-judgment", None, ENTRY_LEGACY_EVENTS_EXPECTED),
        _entry(L.EXPECTED_NEW_STRICT_ID, L.EXPECTED_NEW_STRICT_PATH,
               _origin(**{"class": "synthetic", "generator_revision": L.NEW_STRICT_REVISION,
                          "description": "新严格入口 codekit.protocols.strict_json_loads 对 legacy JSON 合同（整份，%d 个）"
                                         "与 legacy 事件流（逐行，%d 个）的判断，与旧实现预期分开存放；新旧判断不同是"
                                         "兼容矩阵（01-D09）的输入，不是失败。差分测试以当前 scripts/codekit/protocols.py "
                                         "重算并逐字节比较。" % (len(L.legacy_json_fixture_paths()),
                                                               len(L.legacy_jsonl_fixture_paths()))}),
               "判断记录只含 fixture 标识、路径、摘要与固定错误码/原因，不含输入值或凭据",
               ("exact_byte_digest", "new_strict_entry_judgment"),
               ("legacy_dispatch_behavior", "contract_v1_schema_judgment", "real_cli_compatibility"),
               "accept", None, ENTRY_NEW_STRICT_EXPECTED),
    ]


def build_synthetic_entries() -> List[Dict[str, Any]]:
    entries = []
    for spec in SYNTHETIC_SPECS:
        entries.append(_entry(
            spec.fixture_id, spec.path,
            _origin(**{"class": "synthetic", "generator_revision": spec.generator_revision,
                       "description": spec.description}),
            "构造时不包含真实凭据或真实用户数据。", spec.proves, spec.does_not_prove, "accept", None, spec.entry))
    return entries


def build_negative_entries() -> List[Dict[str, Any]]:
    entries = []
    for spec in NEGATIVE_SPECS:
        entries.append(_entry(
            negative_fixture_id(spec), negative_path(spec),
            _origin(**{"class": "negative", "generator_revision": GENERATOR_REVISION, "derived_from": spec.base_id,
                       "fault": spec.fault,
                       "description": "从 %s 派生的单一故障变体（tests/test_codekit01_fixtures.py 的确定性字节变换，锚点恰好"
                                      "出现一次；只改变一个目标条件）。期望入口见 expected.entry，期望错误码 %s，"
                                      "期望 field %s，期望 reason %s。"
                                      % (spec.base_id, spec.code, "null" if spec.field is None else spec.field,
                                         spec.reason)}),
            "由合成样本派生，不含凭据或真实用户数据。",
            ("exact_byte_digest", "single_fault_derivation", "stable_error_code"),
            ("multi_fault_first_error", "real_cli_compatibility", "legacy_dispatch_behavior"),
            "reject", spec.code, spec.entry, integrity=spec.integrity))
    return entries


def build_manifest() -> Dict[str, Any]:
    entries = (L.build_legacy_manifest_entries() + build_expected_entries() + build_synthetic_entries()
               + build_negative_entries())
    return {"schema_version": 1, "record_type": "fixture-manifest-set", "entries": entries}


# ---------------------------------------------------------------------------
# 生成
# ---------------------------------------------------------------------------

def _check_write_target(rel: str) -> Path:
    """生成模式的写入护栏（P4 第 3 轮，复审 paths 视角）：rel 必须是合法业务路径（拒绝 ..、反斜杠、盘符等，
    P.validate_business_path），逐字落在允许的前缀之内；按目录解析后的真实路径还必须逐组件位于仓库根下对应的
    允许目录之内（P._is_within；已存在的祖先是指向别处的链接时同样拒绝）。只做检查，不创建任何东西；
    返回要写入的路径。原来只做字符串前缀比较，含 .. 或反斜杠的路径能写到允许前缀之外，甚至仓库之外。"""
    try:
        P.validate_business_path(rel)
    except P.ProtocolError as exc:
        raise AssertionError("拒绝写入不合法的路径（%s）：%s" % (exc.reason, rel)) from None
    allowed = None
    for prefix in _WRITE_PREFIXES:
        if rel == prefix:
            allowed = prefix.rsplit("/", 1)[0]
        elif prefix.endswith("/") and rel.startswith(prefix):
            allowed = prefix[:-1]
        if allowed is not None:
            break
    if allowed is None:
        raise AssertionError("拒绝写入任务范围之外的路径：%s" % rel)
    root = REPO_ROOT.resolve(strict=True)
    base = repo_path(allowed)
    existing = base
    while not existing.exists():  # 允许目录可能尚未创建：取最近的已存在祖先
        existing = existing.parent
    resolved_base = existing.resolve(strict=True).joinpath(*base.relative_to(existing).parts)
    target = repo_path(rel)
    if os.path.islink(target) or (os.path.lexists(target) and not target.is_file()):
        raise AssertionError("拒绝写入：目标已存在且是链接或不是普通文件：%s" % rel)
    existing = target.parent
    while not existing.exists():
        existing = existing.parent
    resolved_target = existing.resolve(strict=True).joinpath(*target.relative_to(existing).parts)
    if not (P._is_within(root, resolved_base) and P._is_within(resolved_base, resolved_target)):
        raise AssertionError("拒绝写入解析后位于允许目录之外的路径：%s" % rel)
    return target


def _write_bytes(rel: str, raw: bytes) -> None:
    target = _check_write_target(rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "wb") as handle:  # 二进制写入：不做行尾转换
        handle.write(raw)


def write_all() -> Dict[str, Any]:
    text = design_doc_text()
    if text is None:
        raise RuntimeError("找不到设计文档 docs/code-kit-v2/%s*.md（生成文档样例需要它）" % DOC_PREFIX)
    synthetic = dict(list(build_doc_synthetic_files(text).items()) + list(build_literal_synthetic_files().items()))
    # 写任何文件之前，先对全部待写路径做词法与范围检查（P4 第 3 轮）：清单层的校验在写完负例之后才进行，太晚。
    for path in list(synthetic) + [negative_path(spec) for spec in NEGATIVE_SPECS] + [MANIFEST_PATH]:
        _check_write_target(path)
    for path, raw in synthetic.items():
        _write_bytes(path, raw)
    negatives = build_negative_files()  # 从刚写入的正例字节派生
    for path, raw in negatives.items():
        _write_bytes(path, raw)
    manifest = build_manifest()
    P.validate_fixture_manifest_set(manifest, registry())
    check_manifest_claims(manifest)  # 产品来源规则之外，再加本清单的测试层规则（白名单）
    _write_bytes(MANIFEST_PATH, render_json(manifest))
    return {"entries": len(manifest["entries"]), "negatives": len(negatives)}


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

def load_manifest() -> Dict[str, Any]:
    return P.strict_json_loads(read_fixture(MANIFEST_PATH))


def manifest_entries() -> List[Dict[str, Any]]:
    return load_manifest()["entries"]


def fixture_files_on_disk() -> List[str]:
    root = repo_path(FIXTURE_DIR)
    out = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            out.append(Path(dirpath, name).relative_to(REPO_ROOT).as_posix())
    return sorted(out)


def run_git(args: Sequence[str], *, stdin: Optional[bytes] = None) -> Optional[subprocess.CompletedProcess]:
    """只读 git 调用；git 不可用时返回 None。"""
    try:
        return subprocess.run(["git"] + list(args), cwd=str(REPO_ROOT), input=stdin,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=L._clean_env({"GIT_TERMINAL_PROMPT": "0"}), timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None


def git_unavailable_reason() -> Optional[str]:
    proc = run_git(["rev-parse", "--is-inside-work-tree"])
    if proc is None:
        return "git 不可用（无法启动）"
    if proc.returncode != 0 or proc.stdout.strip() != b"true":
        return "当前目录不在 git 工作区中"
    return None


def git_commit_unavailable_reason(revision: str) -> Optional[str]:
    reason = git_unavailable_reason()
    if reason:
        return reason
    proc = run_git(["cat-file", "-t", revision])
    if proc is None or proc.returncode != 0 or proc.stdout.strip() != b"commit":
        return "提交 %s 在本仓库中不可用" % revision
    return None


#: 设为 1 时，取不到 git、提交 a4fa199 的检查记为 NOT_RUN（跳过，不算通过）；未设置时判为失败
#: （设计文档 01-A02：“未取得旧结果不通过”）。只读取这个开关本身的值。
ALLOW_NOT_RUN_ENV = "CODEKIT01_ALLOW_NOT_RUN"


def not_run_or_fail(test: unittest.TestCase, reason: str) -> None:
    """前提不满足时：默认 fail；显式设置 CODEKIT01_ALLOW_NOT_RUN=1 时 skip 并标为 NOT_RUN。"""
    if os.environ.get(ALLOW_NOT_RUN_ENV) == "1":
        test.skipTest("NOT_RUN（%s=1 显式降级，不算通过）：%s" % (ALLOW_NOT_RUN_ENV, reason))
    test.fail("%s。01-A02 要求取得旧结果，未取得时不通过；确需在没有 git 或没有提交 a4fa199 的环境中运行，"
              "设置 %s=1，把这项检查记为 NOT_RUN（不算通过）" % (reason, ALLOW_NOT_RUN_ENV))


_NOT_CHECKED = "<不检查>"


def expect_code(test: unittest.TestCase, entry: str, raw: bytes, code: str, field: Any = _NOT_CHECKED,
                reason: Any = _NOT_CHECKED) -> None:
    """入口必须抛 ProtocolError，code 相同；给出 field、reason 时也必须相同。reason 用来区分同码同位置的规则。"""
    with test.assertRaises(P.ProtocolError) as caught:
        ENTRY_RUNNERS[entry](raw)
    error = caught.exception
    test.assertEqual(error.code, code)
    if field != _NOT_CHECKED:
        test.assertEqual(error.field, field)
    if reason != _NOT_CHECKED:
        test.assertEqual(error.reason, reason, "错误码与位置相同，但触发的是另一条规则（目标规则可能被掩盖）")


# ---------------------------------------------------------------------------
# 测试
# ---------------------------------------------------------------------------

class ManifestTests(unittest.TestCase):
    """manifest 结构、固定序列化与来源一致性（01-A12）。"""

    def test_manifest_is_strict_json_and_validates(self) -> None:
        raw = read_fixture(MANIFEST_PATH)
        document = P.strict_json_loads(raw)
        self.assertEqual(set(document), {"schema_version", "record_type", "entries"})  # 不含自身摘要
        result = P.validate_fixture_manifest_set(document, registry())
        self.assertEqual(result["entries"], len(document["entries"]))
        self.assertEqual(raw, render_json(document), "manifest.json 不是固定序列化的形式")

    def test_manifest_matches_generator_definitions(self) -> None:
        self.assertEqual(read_fixture(MANIFEST_PATH), render_json(build_manifest()),
                         "manifest.json 与本文件及 codekit01_legacy 的定义不一致；按文件头说明重新生成并复核")

    def test_legacy_draft_merged_and_removed(self) -> None:
        self.assertFalse(repo_path(LEGACY_DRAFT_PATH).exists(), "manifest.legacy.draft.json 应已并入 manifest.json")
        ids = [e["fixture_id"] for e in manifest_entries()]
        legacy_ids = [e["fixture_id"] for e in L.build_legacy_manifest_entries()]
        self.assertEqual(ids[:len(legacy_ids)], legacy_ids)
        # 合同 6、合同负例 13+6+1（缺 task_id）、stub 流 10、事件负例 3+1（usage 缺 token）。
        self.assertEqual(len(legacy_ids), 6 + 13 + 6 + 1 + 10 + 3 + 1)

    def test_provenance_consistency(self) -> None:
        entries = manifest_entries()
        by_id = {e["fixture_id"]: e for e in entries}
        for e in entries:
            with self.subTest(fixture_id=e["fixture_id"]):
                origin, resource, expected = e["origin"], e["resource"], e["expected"]
                path = resource["path"]
                self.assertEqual(resource["id"], e["fixture_id"])
                self.assertEqual(resource["kind"], "fixture")
                self.assertTrue(path.startswith(FIXTURE_DIR + "/"))
                directory = path[len(FIXTURE_DIR) + 1:].split("/", 1)[0]
                allowed_dirs = {"legacy": {"legacy", "expected"}, "synthetic": {"synthetic", "expected"},
                                "negative": {"negative"}, "captured": {"captured"}}[origin["class"]]
                self.assertIn(directory, allowed_dirs, "来源类别与目录不符")
                self.assertEqual(e["representation"], "synthetic_fixture",
                                 "本清单没有采集原件，所有条目都应是 synthetic_fixture")
                self.assertFalse(e["redaction"]["applied"] and e["redaction"]["rule_revision"] is None)
                if origin["class"] == "negative":
                    base = by_id[origin["derived_from"]]
                    self.assertNotEqual(base["origin"]["class"], "negative", "负例必须从正例或 legacy 样本派生")
                    self.assertIn(base["expected"]["outcome"], ("accept", "legacy-judgment"))
                    if expected["outcome"] == "reject":
                        self.assertIn(expected["code"], P.ERROR_CODES)
                        self.assertIn(expected["entry"], ENTRY_RUNNERS)  # 正例被同一入口接受见 NegativeTests
                else:
                    self.assertIsNone(origin["derived_from"])
                    self.assertIsNone(origin["fault"])
                ref = expected["expected_ref"]
                if ref is not None:
                    target = by_id[ref["id"]]
                    self.assertEqual(ref, target["resource"], "expected_ref 必须与被引用条目的 resource 相同")
                self.assertTrue(expected["entry"] in ENTRY_RUNNERS or expected["entry"] in DIFFERENTIAL_ENTRIES,
                                "未登记的期望入口：%s" % expected["entry"])
                if expected["entry"] in DIFFERENTIAL_ENTRIES:
                    self.assertIn(expected["outcome"], ("legacy-judgment", "accept"))
                # synthetic_fixture 不得声称真实兼容（4.3.3）。产品入口（P4 起）按来源类别与表示约束全部条目；
                # 这里再按本清单的约定逐条断言，并核对测试层白名单。
                self.assertEqual(e["representation"], "synthetic_fixture")
                for claim in e["proves"]:
                    self.assertNotIn(claim, P.REAL_COMPATIBILITY_CLAIMS, "synthetic_fixture 声称了真实兼容")
                    self.assertFalse(claim.startswith(("real_", "vendor_")), "synthetic_fixture 声称了 %s" % claim)
                    if claim.startswith("legacy_"):
                        self.assertIn(claim, LEGACY_CLAIM_WHITELIST, "未登记的 legacy_ 能力")
                        self.assertIn(expected["entry"], LEGACY_CLAIM_WHITELIST[claim],
                                      "%s 只能由旧实现的差分入口证明" % claim)
                        root = by_id[origin["derived_from"]] if origin["class"] == "negative" else e
                        self.assertEqual(root["origin"]["class"], "legacy", "legacy_ 能力只能来自 legacy 样本或其派生负例")
                try:
                    check_synthetic_fixture_claims(e)
                except P.ProtocolError as exc:
                    self.fail("测试层能力声明规则拒绝了本条目：%s" % exc.reason)
        check_manifest_claims(load_manifest())

    def test_claim_rule_rejects_real_and_unlisted_legacy_claims(self) -> None:
        """产品来源规则与测试层规则的每个分支都能拒绝（对照：未修改的条目被接受）。

        P4：产品入口已按来源类别与表示约束全部条目。real_/vendor_ 类声明由产品入口拒绝（测试层规则同样拒绝，
        作为第二道检查）；legacy_dispatch_behavior 与白名单之外的 legacy_ 能力，产品入口对 legacy 条目接受，
        只由测试层规则拒绝；从合成样本派生的负例声称 legacy_ 能力，由产品的清单级规则与测试层规则拒绝。"""
        by_id = {e["fixture_id"]: e for e in manifest_entries()}
        stub = by_id[STUB_ENTRY_SOURCE_ID]
        contract = by_id["legacy-contract-normalize-query-v1-json"]
        protocol_negative = by_id[negative_fixture_id(NEGATIVE_SPECS[0])]
        legacy_negative = by_id[L.negative_contract_fixture_id("json-utf8-bom")]
        for accepted in (stub, contract, protocol_negative, legacy_negative, by_id[L.EXPECTED_EVENTS_ID]):
            check_synthetic_fixture_claims(accepted)
        # legacy_source_bytes 只属于按 source_path 取得的原字节副本：带 source_test_id（生成输出）时拒绝。
        generated = P.strict_json_loads(render_json(contract))
        generated["origin"]["source_test_id"] = "tests/stub_pi.py STUB_SCENARIO=ok"
        with self.assertRaises(P.ProtocolError) as caught:
            check_synthetic_fixture_claims(generated)
        self.assertEqual(caught.exception.reason, CLAIM_RULE_LEGACY)

        def claiming(entry: Dict[str, Any], claim: str) -> Dict[str, Any]:
            changed = P.strict_json_loads(render_json(entry))
            changed["proves"] = changed["proves"] + [claim]
            changed["does_not_prove"] = [c for c in changed["does_not_prove"] if c != claim]
            return changed

        product_real = "real_compatibility_claim_requires_captured_raw"
        #: (条目, 声明, 产品入口的 reason（None 表示产品入口接受）, 测试层规则的 reason)
        cases = (
            (stub, "real_cli_compatibility", product_real, CLAIM_RULE_REAL),
            (stub, "vendor_protocol", product_real, CLAIM_RULE_REAL),
            (stub, "real_pi_stream", product_real, CLAIM_RULE_REAL),
            (stub, "vendor_usage_accounting", product_real, CLAIM_RULE_REAL),
            (protocol_negative, "real_cli_compatibility", product_real, CLAIM_RULE_REAL),
            (legacy_negative, "vendor_protocol", product_real, CLAIM_RULE_REAL),
            # 产品入口允许 legacy + legacy-judgment 声明旧调度器行为；本清单约定用更具体的 legacy_*_judgment。
            (stub, "legacy_dispatch_behavior", None, CLAIM_RULE_REAL),
            (stub, "legacy_end_to_end_run", None, CLAIM_RULE_LEGACY),  # 未登记的 legacy_ 能力
            (stub, "legacy_source_bytes", None, CLAIM_RULE_LEGACY),  # stub 输出不是原字节副本
            (stub, "legacy_contract_judgment", None, CLAIM_RULE_LEGACY),  # 入口是事件差分，不是合同差分
            (protocol_negative, "legacy_contract_judgment", None, CLAIM_RULE_LEGACY),  # 单条接受，清单级拒绝
            (legacy_negative, "legacy_source_bytes", None, CLAIM_RULE_LEGACY),  # 派生负例不是原字节副本
        )
        for entry, claim, product_reason, test_reason in cases:
            with self.subTest(fixture_id=entry["fixture_id"], claim=claim):
                changed = claiming(entry, claim)
                if product_reason is None:
                    P.validate_fixture_manifest_entry(changed, registry())
                else:
                    with self.assertRaises(P.ProtocolError) as caught:
                        P.validate_fixture_manifest_entry(changed, registry())
                    self.assertEqual((caught.exception.code, caught.exception.field, caught.exception.reason),
                                     ("E_PROVENANCE_CLAIM", "/proves", product_reason))
                with self.assertRaises(P.ProtocolError) as caught:
                    check_synthetic_fixture_claims(changed)
                self.assertEqual((caught.exception.code, caught.exception.field, caught.exception.reason),
                                 ("E_PROVENANCE_CLAIM", "/proves", test_reason))
        # 声明 legacy_ 能力的负例必须从 legacy 条目派生：产品的清单级规则与测试层规则都拒绝。
        manifest = load_manifest()
        target = negative_fixture_id(NEGATIVE_SPECS[0])
        index = [e["fixture_id"] for e in manifest["entries"]].index(target)
        manifest["entries"][index]["proves"] = manifest["entries"][index]["proves"] + ["legacy_event_summary_judgment"]
        manifest["entries"][index]["expected"]["entry"] = L.EVENT_ENTRY
        with self.assertRaises(P.ProtocolError) as caught:
            P.validate_fixture_manifest_set(manifest, registry())
        self.assertEqual((caught.exception.code, caught.exception.field, caught.exception.reason),
                         ("E_PROVENANCE_CLAIM", "/entries/%d/proves" % index,
                          "negative_legacy_claim_requires_legacy_base"))
        with self.assertRaises(P.ProtocolError) as caught:
            check_manifest_claims(manifest)
        self.assertEqual(caught.exception.reason, CLAIM_RULE_LEGACY)

    def test_claim_spelling_variants_rejected(self) -> None:
        """P4 第 3 轮（复审 tests-mutation 视角，major）：大小写与连字符变体不能绕过来源规则。产品入口在结构层按封闭词法
        拒绝（E_SCHEMA_FIELDS，/proves/<i>，claim_syntax）；测试层规则先把声明按 ASCII 小写化、"-" 归一为 "_" 再判定，
        同样拒绝（real_/vendor_ 类 → test_rule_synthetic_fixture_cannot_prove_real_compatibility，legacy_ 类 →
        test_rule_legacy_claim_not_whitelisted）。stub（legacy）、协议负例、legacy 负例与合成条目都覆盖；把变体写进
        manifest.json 的 stub 条目后，整份清单也被拒绝。"""
        by_id = {e["fixture_id"]: e for e in manifest_entries()}
        entries = (by_id[STUB_ENTRY_SOURCE_ID], by_id[negative_fixture_id(NEGATIVE_SPECS[0])],
                   by_id[L.negative_contract_fixture_id("json-utf8-bom")], by_id[SAMPLE_1_ID])
        variants = (("REAL_CLI_COMPATIBILITY", CLAIM_RULE_REAL), ("Vendor_Protocol", CLAIM_RULE_REAL),
                    ("vendor-protocol", CLAIM_RULE_REAL), ("Real_Pi_Stream", CLAIM_RULE_REAL),
                    ("Legacy_dispatch_behavior", CLAIM_RULE_REAL),  # legacy_dispatch_behavior 属于 3 个真实兼容声明
                    ("legacy-contract-judgment", CLAIM_RULE_LEGACY))
        for entry in entries:
            for claim, test_reason in variants:
                with self.subTest(fixture_id=entry["fixture_id"], claim=claim):
                    changed = P.strict_json_loads(render_json(entry))
                    changed["proves"] = changed["proves"] + [claim]
                    with self.assertRaises(P.ProtocolError) as caught:
                        P.validate_fixture_manifest_entry(changed, registry())
                    self.assertEqual((caught.exception.code, caught.exception.field, caught.exception.reason),
                                     ("E_SCHEMA_FIELDS", "/proves/%d" % (len(changed["proves"]) - 1), "claim_syntax"))
                    with self.assertRaises(P.ProtocolError) as caught:
                        check_synthetic_fixture_claims(changed)
                    self.assertEqual(caught.exception.reason, test_reason)
        manifest = load_manifest()
        index = [e["fixture_id"] for e in manifest["entries"]].index(STUB_ENTRY_SOURCE_ID)
        manifest["entries"][index]["proves"] = manifest["entries"][index]["proves"] + ["REAL_CLI_COMPATIBILITY"]
        with self.assertRaises(P.ProtocolError) as caught:
            P.validate_fixture_manifest_set(manifest, registry())
        self.assertEqual((caught.exception.code, caught.exception.reason), ("E_SCHEMA_FIELDS", "claim_syntax"))
        with self.assertRaises(P.ProtocolError) as caught:
            check_manifest_claims(manifest)
        self.assertEqual(caught.exception.reason, CLAIM_RULE_REAL)

    def test_counts_by_class_and_representation(self) -> None:
        counts: Dict[Tuple[str, str], int] = {}
        for e in manifest_entries():
            key = (e["origin"]["class"], e["representation"])
            counts[key] = counts.get(key, 0) + 1
        self.assertEqual(counts, {
            ("legacy", "synthetic_fixture"): 6 + 10 + 2,
            ("negative", "synthetic_fixture"): 20 + 4 + len(NEGATIVE_SPECS),
            ("synthetic", "synthetic_fixture"): len(SYNTHETIC_SPECS) + 1,
        })


class FileIntegrityTests(unittest.TestCase):
    """逐文件摘要、目录完整性与 git 行尾转换（01-F033、01-A02）。"""

    def test_every_manifest_digest_matches_file_bytes(self) -> None:
        for e in manifest_entries():
            with self.subTest(path=e["resource"]["path"]):
                raw = read_fixture(e["resource"]["path"])
                P.verify_resource_bytes(e["resource"], raw, registry())

    def test_directory_has_no_unregistered_or_missing_files(self) -> None:
        registered = sorted(e["resource"]["path"] for e in manifest_entries())
        self.assertEqual(len(registered), len(set(registered)))
        on_disk = [p for p in fixture_files_on_disk() if p != MANIFEST_PATH]
        self.assertEqual(sorted(set(on_disk) - set(registered)), [], "有未登记的文件")
        self.assertEqual(sorted(set(registered) - set(on_disk)), [], "manifest 中的文件缺失")

    def test_git_attributes_disable_line_ending_conversion(self) -> None:
        reason = git_unavailable_reason()
        if reason:
            not_run_or_fail(self, reason)
        paths = fixture_files_on_disk()
        proc = run_git(["check-attr", "-z", "--stdin", "text", "eol"], stdin=b"\0".join(p.encode() for p in paths))
        self.assertIsNotNone(proc)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
        fields = proc.stdout.split(b"\0")
        if fields and fields[-1] == b"":
            fields.pop()
        self.assertEqual(len(fields) % 3, 0)
        seen: Dict[Tuple[str, str], str] = {}
        for i in range(0, len(fields), 3):
            seen[(fields[i].decode(), fields[i + 1].decode())] = fields[i + 2].decode()
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(seen.get((path, "text")), "unset",
                                 "fixture 没有被 .gitattributes 标为 -text，提交或检出时可能发生行尾转换")
                self.assertEqual(seen.get((path, "eol")), "unspecified")

    def test_git_clean_filter_keeps_bytes(self) -> None:
        """git 按路径属性与配置（本机 core.autocrlf=true）清洗后的对象摘要必须等于不经过滤的摘要。"""
        reason = git_unavailable_reason()
        if reason:
            not_run_or_fail(self, reason)
        paths = fixture_files_on_disk()
        listing = "\n".join(paths).encode() + b"\n"
        filtered = run_git(["hash-object", "--stdin-paths"], stdin=listing)
        raw = run_git(["hash-object", "--no-filters", "--stdin-paths"], stdin=listing)
        self.assertEqual(filtered.returncode, 0, filtered.stderr.decode("utf-8", "replace"))
        self.assertEqual(raw.returncode, 0, raw.stderr.decode("utf-8", "replace"))
        for path, a, b in zip(paths, filtered.stdout.split(), raw.stdout.split()):
            with self.subTest(path=path):
                self.assertEqual(a, b, "git 会在提交时改写该文件的字节（行尾转换）")
        # 对照：同一份 CRLF 字节放在未标 -text 的路径下、打开 autocrlf 时必然被改写，证明本检查能发现转换。
        probe = L.stub_fixture_path("ok")
        self.assertIn(b"\r\n", read_fixture(probe))
        converted = run_git(["-c", "core.autocrlf=true", "hash-object", "--path=codekit01-eol-probe/probe.jsonl", probe])
        unfiltered = run_git(["hash-object", "--no-filters", probe])
        self.assertNotEqual(converted.stdout.strip(), unfiltered.stdout.strip(), "对照失败：检查对行尾转换不敏感")


class LegacySourceTests(unittest.TestCase):
    """legacy 字节等于 git show <source_revision>:<source_path>（01-A02）。"""

    def test_legacy_copies_equal_git_show(self) -> None:
        checked = 0
        for e in manifest_entries():
            origin = e["origin"]
            if origin["class"] != "legacy" or origin["source_test_id"] is not None:
                continue  # 只有字节副本；stub 输出与预期文件见下一个测试
            reason = git_commit_unavailable_reason(origin["source_revision"])
            if reason:
                not_run_or_fail(self, reason)
            with self.subTest(fixture_id=e["fixture_id"]):
                spec = "%s:%s" % (origin["source_revision"], origin["source_path"])
                shown = run_git(["show", spec])
                blob = run_git(["cat-file", "blob", spec])
                self.assertEqual(shown.returncode, 0)
                self.assertEqual(shown.stdout, blob.stdout)
                self.assertEqual(read_fixture(e["resource"]["path"]), shown.stdout)
                checked += 1
        self.assertEqual(checked, 6)

    def test_generator_sources_at_revision(self) -> None:
        known = {L.LEGACY_STUB_PATH: L.LEGACY_STUB_SHA256, L.LEGACY_PI_DISPATCH_PATH: L.LEGACY_PI_DISPATCH_SHA256}
        pairs = sorted({(e["origin"]["source_revision"], e["origin"]["source_path"]) for e in manifest_entries()
                        if e["origin"]["class"] == "legacy" and e["origin"]["source_test_id"] is not None})
        self.assertEqual({path for _rev, path in pairs}, set(known))
        for revision, path in pairs:
            reason = git_commit_unavailable_reason(revision)
            if reason:
                not_run_or_fail(self, reason)
            with self.subTest(path=path):
                shown = run_git(["show", "%s:%s" % (revision, path)])
                self.assertEqual(shown.returncode, 0)
                self.assertEqual(P.sha256_hex(shown.stdout), known[path])


def json_differences(locked: Any, current: Any, pointer: str = "") -> List[str]:
    """两个 JSON 值不同的位置（JSON Pointer）。类型不同（int 与 float、bool 与 int）也算不同。"""
    if type(locked) is not type(current):
        return [pointer or "/"]
    if isinstance(locked, dict):
        out: List[str] = []
        for key in sorted(set(locked) | set(current)):
            child = pointer + "/" + str(key).replace("~", "~0").replace("/", "~1")
            if key not in current:
                out.append(child + "（重算结果中没有）")
            elif key not in locked:
                out.append(child + "（锁定预期中没有）")
            else:
                out.extend(json_differences(locked[key], current[key], child))
        return out
    if isinstance(locked, list):
        if len(locked) != len(current):
            return ["%s（长度 %d -> %d）" % (pointer or "/", len(locked), len(current))]
        out = []
        for index, (old, new) in enumerate(zip(locked, current)):
            out.extend(json_differences(old, new, "%s/%d" % (pointer, index)))
        return out
    return [] if locked == current else [pointer or "/"]


def case_differences(locked_cases: Dict[str, Any], current_cases: Dict[str, Any]) -> List[str]:
    """按 case_id 列出重算结果与锁定预期不同的字段："<case_id>：<JSON Pointer>"。"""
    out: List[str] = []
    for case_id in sorted(set(locked_cases) | set(current_cases)):
        if case_id not in current_cases:
            out.append("%s：重算结果中没有这个用例" % case_id)
        elif case_id not in locked_cases:
            out.append("%s：锁定预期中没有这个用例" % case_id)
        else:
            out.extend("%s：%s" % (case_id, where)
                       for where in json_differences(locked_cases[case_id], current_cases[case_id]))
    return out


_RECOMPUTED: Dict[str, Dict[str, Any]] = {}


def recompute_with_current_implementation(kind: str) -> Dict[str, Any]:
    """以当前 scripts/pi_dispatch.py 的字节重算旧投影（不要求字节等于 a4fa199），同一进程内只算一次。"""
    if kind not in _RECOMPUTED:
        compute = {"contracts": L.compute_expected_contracts, "events": L.compute_expected_events}[kind]
        _RECOMPUTED[kind] = compute(require_locked_bytes=False)
    return _RECOMPUTED[kind]


class DifferentialTests(unittest.TestCase):
    """用 tests/codekit01_legacy.py 以当前实现重算，与锁定预期比较（01-A02：旧行为没有漂移）。

    三件事分开报告：
    - 实现字节是否仍为 a4fa199：test_legacy_implementation_bytes_are_source_revision；
    - 判断是否漂移：test_legacy_*_projection_unchanged 只比较 cases，失败时列出不同的 case_id 与字段；
    - 预期文件头与生成器定义一致：test_legacy_expected_headers_match_generator（头部记录锁定时的实现摘要，
      是记录，不参与判断内容的比较）。
    预期只由 a4fa199 的旧实现生成（codekit01_legacy.py --write-expected 要求字节相同）；不为消除差异而重新生成。
    """

    def _require_git_for_contracts(self) -> None:
        if run_git(["--version"]) is None:  # 旧 CLI 的 validate 在自建临时 git 仓库中运行
            not_run_or_fail(self, "git 不可用（无法启动），不能在临时仓库中运行旧 CLI validate")

    def _assert_cases_unchanged(self, kind: str, locked_path: str) -> None:
        current = recompute_with_current_implementation(kind)
        locked = json.loads(read_fixture(locked_path).decode("utf-8"))
        differences = case_differences(locked["cases"], current["cases"])
        if differences:
            more = "\n……另有 %d 处" % (len(differences) - 60) if len(differences) > 60 else ""
            self.fail("当前实现的判断与锁定预期不同（case_id：字段）：\n" + "\n".join(differences[:60]) + more)
        self.assertEqual(render_json(current["cases"]), render_json(locked["cases"]))

    def test_legacy_implementation_bytes_are_source_revision(self) -> None:
        for path, digest in ((L.LEGACY_PI_DISPATCH_PATH, L.LEGACY_PI_DISPATCH_SHA256),
                             (L.LEGACY_STUB_PATH, L.LEGACY_STUB_SHA256)):
            with self.subTest(path=path):
                self.assertEqual(P.sha256_hex(read_fixture(path)), digest,
                                 "%s 的字节与 a4fa199 不同。这一项只说明字节变了；判断是否漂移看 "
                                 "test_legacy_*_projection_unchanged 列出的用例与字段" % path)

    def test_legacy_contract_projection_unchanged(self) -> None:
        self._require_git_for_contracts()
        self._assert_cases_unchanged("contracts", L.EXPECTED_CONTRACTS_PATH)

    def test_legacy_event_projection_unchanged(self) -> None:
        self._assert_cases_unchanged("events", L.EXPECTED_EVENTS_PATH)

    def test_legacy_expected_headers_match_generator(self) -> None:
        self._require_git_for_contracts()
        for kind, path in (("contracts", L.EXPECTED_CONTRACTS_PATH), ("events", L.EXPECTED_EVENTS_PATH)):
            with self.subTest(path=path):
                raw = read_fixture(path)
                locked = json.loads(raw.decode("utf-8"))
                self.assertEqual(raw, render_json(locked), "预期文件不是固定序列化的形式")
                current = {k: v for k, v in recompute_with_current_implementation(kind).items() if k != "cases"}
                header = {k: v for k, v in locked.items() if k != "cases"}
                self.assertEqual(json_differences(header, current), [], "预期文件头与生成器定义不同")
                self.assertEqual(render_json(header), render_json(current))

    def test_legacy_negative_derivations_reproducible(self) -> None:
        for path, raw in list(L.derive_negative_contracts().items()) + list(L.derive_negative_events().items()):
            with self.subTest(path=path):
                self.assertEqual(read_fixture(path), raw)

    def test_new_strict_verdicts_unchanged(self) -> None:
        self.assertEqual(render_json(L.compute_new_strict_expected()), read_fixture(L.EXPECTED_NEW_STRICT_PATH))

    def test_new_strict_verdicts_are_separate_from_legacy_expectations(self) -> None:
        for rel in (L.EXPECTED_CONTRACTS_PATH, L.EXPECTED_EVENTS_PATH):
            self.assertNotIn(b'"new_strict"', read_fixture(rel))
        document = P.strict_json_loads(read_fixture(L.EXPECTED_NEW_STRICT_PATH))
        self.assertEqual(sorted(document["json_documents"]), sorted(fid for fid, _p in L.legacy_json_fixture_paths()))
        self.assertEqual(sorted(document["jsonl_streams"]), sorted(fid for fid, _p in L.legacy_jsonl_fixture_paths()))


def _path_forms(path: str) -> List[bytes]:
    """一个本机路径可能出现在 JSON 字节中的写法（原样、正斜杠、JSON 转义），小写后比较。"""
    forms = set()
    for base in {path, os.path.realpath(path)}:
        for variant in (base, base.replace("\\", "/"), json.dumps(base)[1:-1]):
            if len(variant) >= 4:
                forms.add(variant.lower().encode("utf-8", "replace"))
    return sorted(forms)


_GENERIC_LOCAL_PATH_PATTERNS = (
    ("盘符绝对路径", re.compile(rb"(?<![a-z0-9])[a-z]:[\\/]")),
    ("POSIX 用户或临时目录", re.compile(rb"/(?:home|users|tmp|private/var|var/folders)/")),
    ("AppData 目录", re.compile(rb"appdata")),
)


def local_path_markers(raw: bytes) -> List[str]:
    """raw 中出现的本机路径痕迹的**类别名**（不回显路径本身）：仓库根、用户主目录、临时目录，以及通用的
    盘符路径、POSIX 用户/临时目录、AppData。按小写比较。"""
    lowered = raw.lower()
    hits: List[str] = []
    for label, path in (("仓库根目录", str(REPO_ROOT)), ("用户主目录", str(Path.home())),
                        ("系统临时目录", tempfile.gettempdir())):
        if any(form in lowered for form in _path_forms(path)):
            hits.append(label)
    hits.extend(label for label, pattern in _GENERIC_LOCAL_PATH_PATTERNS if pattern.search(lowered))
    return hits


class StubTests(unittest.TestCase):
    """stub 生成的事件流：cwd 占位与无本机路径（各平台），重跑 stub 与锁定字节相同（只在 Windows）。

    manifest 中 stub 条目的 proves 含 stub_output_at_source_revision，redaction 声称 session.cwd 已替换为占位值；
    这两项在默认测试中核对，不只靠手工命令 codekit01_legacy.py --check-stub-regen / --check。
    """

    def test_stub_cwd_placeholder_and_no_local_paths(self) -> None:
        records = L.stub_redaction_records()  # 每个 stub fixture 的 session.cwd 都是占位值，否则抛 AssertionError
        self.assertEqual(sorted(records), sorted(slug for slug, _env, _code, _desc in L.STUB_SCENARIOS))
        paths = ([L.stub_fixture_path(slug) for slug, _env, _code, _desc in L.STUB_SCENARIOS]
                 + [L.negative_event_path(slug) for slug, _src, _t, _f in L.NEGATIVE_EVENT_VARIANTS]
                 + [L.EXPECTED_EVENTS_PATH])
        for path in paths:
            with self.subTest(path=path):
                raw = read_fixture(path)
                if path != L.EXPECTED_EVENTS_PATH:
                    self.assertEqual(raw.count(json.dumps(L.STUB_CWD_PLACEHOLDER).encode("ascii")), 1,
                                     "cwd 占位值应恰好出现一次（session 行）")
                self.assertEqual(local_path_markers(raw), [], "fixture 中含本机路径痕迹")
        # 对照：检查对真实的本机路径写法敏感。
        self.assertIn("仓库根目录", local_path_markers(json.dumps({"cwd": str(REPO_ROOT)}).encode("utf-8")))
        self.assertIn("系统临时目录", local_path_markers(json.dumps({"cwd": tempfile.gettempdir()}).encode("utf-8")))

    @unittest.skipUnless(os.name == "nt", "NOT_RUN：stub 输出的行尾随平台变化（Windows 为 CRLF），"
                                          "锁定字节只在 Windows 上生成与核对")
    def test_stub_regeneration_matches_locked_bytes(self) -> None:
        try:  # pi_dispatch 只提供参数形状，按当前字节取；stub 本身必须是 a4fa199 的字节
            results = L.check_stub_regen(require_locked_bytes=False)
        except RuntimeError as exc:  # tests/stub_pi.py 的字节不是 a4fa199：原因另见 test_legacy_implementation_bytes_*
            self.fail("不能按锁定的字节运行 stub：%s" % exc)
        self.assertEqual(len(results), len(L.STUB_SCENARIOS))
        self.assertEqual([name for name, same in results if not same], [],
                         "重跑 tests/stub_pi.py 的输出或退出码与锁定的事件字节不同")


class SyntheticTests(unittest.TestCase):
    """合成样本：文档字节、黄金向量与正例接受（01-A03、A04、A12）。"""

    def test_sample_1_exact_bytes_and_digest(self) -> None:
        raw = read_fixture(SYNTHETIC_PATHS[SAMPLE_1_ID])
        self.assertEqual(raw, SAMPLE_1_BYTES)
        self.assertEqual(P.sha256_hex(raw), SAMPLE_1_SHA256)
        # 另一件事：这组文件字节恰好也等于该对象的固定快照输出。
        self.assertEqual(P.stable_snapshot_bytes({"fixture": "synthetic", "ok": True}), raw)

    def test_doc_samples_equal_design_doc_blocks(self) -> None:
        text = design_doc_text()
        if text is None:
            self.skipTest("找不到设计文档 docs/code-kit-v2/%s*.md" % DOC_PREFIX)
        for path, raw in build_doc_synthetic_files(text).items():
            with self.subTest(path=path):
                self.assertEqual(read_fixture(path), raw)

    def test_c1_completed_entry_matches_doc(self) -> None:
        completed = P.strict_json_loads(read_fixture(SYNTHETIC_PATHS["synthetic-doc-c.1-manifest-entry-completed"]))
        text = design_doc_text()
        if text is None:
            self.skipTest("找不到设计文档 docs/code-kit-v2/%s*.md" % DOC_PREFIX)
        original = P.strict_json_loads(doc_code_block(text, "### C.1 fixture Manifest 示例", "json"))
        with self.assertRaises(P.ProtocolError) as caught:
            P.validate_fixture_manifest_entry(original, registry())
        self.assertEqual((caught.exception.code, caught.exception.field), ("E_SCHEMA_FIELDS", "/expected"))
        for parents, key in C1_COMPLETION_FIELDS:
            target = completed
            for name in parents:
                target = target[name]
            del target[key]
        self.assertEqual(completed, original)

    def test_stub_entry_copy_equals_manifest_entry(self) -> None:
        copy = P.strict_json_loads(read_fixture(SYNTHETIC_PATHS[STUB_ENTRY_COPY_ID]))
        by_id = {e["fixture_id"]: e for e in manifest_entries()}
        self.assertEqual(render_json(copy), render_json(by_id[STUB_ENTRY_SOURCE_ID]))

    def test_literal_synthetic_files_reproducible(self) -> None:
        for path, raw in build_literal_synthetic_files().items():
            with self.subTest(path=path):
                self.assertEqual(read_fixture(path), raw)

    def test_synthetic_positives_accepted(self) -> None:
        checked = 0
        for e in manifest_entries():
            if e["origin"]["class"] != "synthetic" or e["expected"]["entry"] not in ENTRY_RUNNERS:
                continue
            with self.subTest(fixture_id=e["fixture_id"]):
                self.assertEqual(e["expected"]["outcome"], "accept")
                ENTRY_RUNNERS[e["expected"]["entry"]](read_fixture(e["resource"]["path"]))
                checked += 1
        self.assertEqual(checked, len(SYNTHETIC_SPECS))

    def test_golden_vectors_byte_exact(self) -> None:
        document = P.strict_json_loads(read_fixture(SYNTHETIC_PATHS["synthetic-golden-vectors-c.2"]))
        self.assertEqual(len(document["vectors"]), 5)
        for vector in document["vectors"]:
            with self.subTest(vector=vector["id"]):
                value = P.strict_json_loads(vector["input_json"].encode("utf-8"))
                snapshot = P.stable_snapshot_bytes(value)
                self.assertEqual(snapshot, bytes.fromhex(vector["expected_snapshot_utf8_hex"]))
                self.assertEqual(P.sha256_hex(snapshot), vector["expected_sha256"])
                if vector["input_codepoints"] is not None:
                    self.assertEqual(["U+%04X" % ord(ch) for ch in value["text"]], vector["input_codepoints"])
        self.assertNotEqual(document["vectors"][1]["expected_sha256"], document["vectors"][2]["expected_sha256"])
        self.assertNotEqual(document["vectors"][3]["expected_sha256"], document["vectors"][4]["expected_sha256"])

    def test_golden_vectors_match_design_doc_table(self) -> None:
        text = design_doc_text()
        if text is None:
            self.skipTest("找不到设计文档 docs/code-kit-v2/%s*.md" % DOC_PREFIX)
        rows = doc_table_rows(text, "### C.2 固定快照字节与 SHA-256 黄金向量")
        document = P.strict_json_loads(read_fixture(SYNTHETIC_PATHS["synthetic-golden-vectors-c.2"]))
        self.assertEqual(len(rows), len(document["vectors"]))
        for row, vector in zip(rows, document["vectors"]):
            with self.subTest(vector=vector["id"]):
                shown = row[0][row[0].index("`") + 1:row[0].index("`", row[0].index("`") + 1)]
                self.assertEqual(P.strict_json_loads(shown.encode("utf-8")),
                                 P.strict_json_loads(vector["input_json"].encode("utf-8")))
                self.assertEqual(row[2].strip("`"), vector["expected_sha256"])


class NegativeTests(unittest.TestCase):
    """单一故障负例：可从正例复现、正例被同一入口接受、恰好得到 manifest 写的错误码（01-A04、A09、7.4）。"""

    def test_negative_bytes_reproducible_from_base(self) -> None:
        derived = build_negative_files()
        self.assertEqual(len(derived), len(NEGATIVE_SPECS))
        for spec in NEGATIVE_SPECS:
            path = negative_path(spec)
            with self.subTest(path=path):
                self.assertEqual(read_fixture(path), derived[path])
                self.assertNotEqual(derived[path], read_fixture(SYNTHETIC_PATHS[spec.base_id]))

    def test_each_negative_yields_exactly_manifest_code(self) -> None:
        by_id = {e["fixture_id"]: e for e in manifest_entries()}
        for spec in NEGATIVE_SPECS:
            with self.subTest(fixture=negative_fixture_id(spec)):
                entry = by_id[negative_fixture_id(spec)]
                self.assertEqual(entry["expected"]["outcome"], "reject")
                self.assertEqual(entry["expected"]["code"], spec.code)
                self.assertEqual(entry["expected"]["entry"], spec.entry)
                base = by_id[spec.base_id]
                # 单一故障的前提：同一入口接受未修改的正例（正例自己的 expected.entry 可能是另一个更窄的入口，
                # 例如 synthetic-doc-4.2.2-resource-ref 的 sha256-wrong-value 变体用 verify_resource_bytes 判断）。
                ENTRY_RUNNERS[spec.entry](read_fixture(base["resource"]["path"]))
                expect_code(self, spec.entry, read_fixture(entry["resource"]["path"]), spec.code, spec.field,
                            spec.reason)
                self.assertIn("期望 reason %s。" % spec.reason, entry["origin"]["description"])

    def test_negative_catalog_is_unique(self) -> None:
        ids = [negative_fixture_id(s) for s in NEGATIVE_SPECS]
        self.assertEqual(len(ids), len(set(ids)))
        for fid in ids:
            P.validate_logical_id(fid)
        for spec in NEGATIVE_SPECS:
            with self.subTest(fixture=negative_fixture_id(spec)):
                self.assertTrue(spec.reason, "每个负例都要写期望 reason")

    def test_negative_counts_by_group(self) -> None:
        """兼容矩阵按组引用这些计数；增删负例时同步更新 compatibility-matrix.md。"""
        counts: Dict[str, int] = {}
        for spec in NEGATIVE_SPECS:
            counts[spec.group] = counts.get(spec.group, 0) + 1
        self.assertEqual(counts, {
            "run-context": 16, "run-event": 31, "vendor-event": 9, "resource-ref": 20, "usage-unknown": 13,
            "usage-cost": 17, "error-record": 1, "fixture-manifest-entry": 22, "fixture-manifest-claims": 4,
            "synthetic-sample": 2,
        })


class GeneratorGuardTests(unittest.TestCase):
    """生成模式的写入护栏（P4 第 3 轮，复审 paths 视角）。只调用检查函数 _check_write_target，不写任何文件。"""

    def test_guard_rejects_paths_outside_allowed_prefixes(self) -> None:
        """含 ..、反斜杠的路径与允许前缀之外的路径都在写入前被拒绝（原来只做字符串前缀比较，前两类能写到允许前缀
        之外，甚至仓库之外）；允许范围内的路径返回仓库根下的目标。"""
        rejected = (SYN + "/../../../../AGENTS.md", SYN + "/../../../../../outside-repo.txt",
                    NEG + "/..\\..\\..\\..\\..\\esc2.txt", NEG + "/x/./y.json", "AGENTS.md", "tests/x.json",
                    SYN, MANIFEST_PATH + ".bak", "scripts/pi_dispatch.py", "/" + SYN + "/x.json",
                    "C:/" + SYN + "/x.json")
        for rel in rejected:
            with self.subTest(rel=rel):
                with self.assertRaises(AssertionError):
                    _check_write_target(rel)
        for rel in (SYN + "/synthetic-protocol-sample-1.json", NEG + "/run-event/new-variant.json", MANIFEST_PATH):
            with self.subTest(allowed=rel):
                self.assertEqual(_check_write_target(rel), repo_path(rel))

    def test_guard_rejects_linked_directory_leaving_allowed_prefix(self) -> None:
        """允许目录（或其祖先）是指向别处的链接时，按解析后的真实路径逐组件判定，拒绝写入。在 tempfile 目录中建
        一个假仓库，把模块的 REPO_ROOT 临时指向它，用后恢复；不能创建目录链接时 skip。

        收尾轮（文档 8.4）：临时区域由 codekit01_legacy._make_owned_tempdir 建立、_rmtree 删除（删除前核对归属），
        不再用 TemporaryDirectory 的无核对递归清理；链接本身先单独删除，递归删除不经过链接。"""
        module = sys.modules[__name__]
        td = L._make_owned_tempdir("codekit01-fixtures-guard-")
        try:
            fake_repo = td / "repo"
            outside = td / "outside"
            outside.mkdir()
            (fake_repo / FIXTURE_DIR).mkdir(parents=True)
            link = fake_repo.joinpath(*SYN.split("/"))
            try:
                if os.name == "nt":
                    import _winapi
                    _winapi.CreateJunction(str(outside), str(link))
                else:
                    os.symlink(outside, link, target_is_directory=True)
            except OSError as exc:
                self.skipTest("无法创建目录链接（%s），未实测" % type(exc).__name__)
            original = module.REPO_ROOT
            module.REPO_ROOT = fake_repo.resolve(strict=True)
            try:
                with self.assertRaises(AssertionError):
                    _check_write_target(SYN + "/x.json")
                self.assertEqual(module._check_write_target(MANIFEST_PATH).name, "manifest.json")
            finally:
                module.REPO_ROOT = original
                if os.name == "nt":
                    os.rmdir(link)  # 删除联接本身，不进入目标
                else:
                    os.unlink(link)
            self.assertEqual(list(outside.iterdir()), [])
        finally:
            L._rmtree(td)


# ---------------------------------------------------------------------------
# 收尾轮：R-P11 新字段的登记规则（acceptance.md M-03）
# ---------------------------------------------------------------------------

def expected_integrity(entry: Dict[str, Any]) -> str:
    """本清单对 integrity 的登记规则（见文件头）：协议负例取 NegativeSpec.integrity，legacy 事件负例取
    codekit01_legacy.NEGATIVE_EVENT_INTEGRITY，其余条目为 complete。"""
    fixture_id = entry["fixture_id"]
    for spec in NEGATIVE_SPECS:
        if negative_fixture_id(spec) == fixture_id:
            return spec.integrity
    for slug, value in L.NEGATIVE_EVENT_INTEGRITY.items():
        if L.negative_event_fixture_id(slug) == fixture_id:
            return value
    return "complete"


def _copy_json(value: Any) -> Any:
    return P.strict_json_loads(render_json(value))


class R11Tests(unittest.TestCase):
    """裁决 R-P11：每个条目的 integrity、platform_scope、capture、redaction.protocol_structure_preserved 与
    origin.traceable 按本清单的登记规则填写；新规则在单条与整份清单两级都由产品入口执行。"""

    def test_every_entry_follows_registration_rules(self) -> None:
        for e in manifest_entries():
            with self.subTest(fixture_id=e["fixture_id"]):
                self.assertIsNone(e["capture"], "本清单没有 captured 条目，capture 必须为 null")
                self.assertIs(e["origin"]["traceable"], True)
                redaction = e["redaction"]
                if redaction["applied"]:
                    # 只有 stub 流的 session.cwd 占位替换：只换一个字符串值，每行仍是同一 JSON 对象
                    self.assertEqual(redaction["rule_revision"], L.STUB_CWD_RULE_REVISION)
                    self.assertIs(redaction["protocol_structure_preserved"], True)
                else:
                    self.assertIsNone(redaction["protocol_structure_preserved"])
                self.assertEqual(e["integrity"], expected_integrity(e))
                self.assertEqual(e["platform_scope"], platform_scope_for(e["expected"]["outcome"]))

    def test_registration_counts(self) -> None:
        """manifest 条目按 integrity、platform_scope 与 protocol_structure_preserved 的分布（兼容矩阵引用这些计数）。"""
        entries = manifest_entries()
        integrity: Dict[str, int] = {}
        scopes: Dict[str, int] = {}
        structure: Dict[str, int] = {}
        for e in entries:
            integrity[e["integrity"]] = integrity.get(e["integrity"], 0) + 1
            scope = ",".join(e["platform_scope"])
            scopes[scope] = scopes.get(scope, 0) + 1
            psp = json.dumps(e["redaction"]["protocol_structure_preserved"])
            structure[psp] = structure.get(psp, 0) + 1
        legacy_judgment = len(L.build_legacy_manifest_entries()) + 2  # 另有 expected-legacy-contracts/-events
        self.assertEqual(len(entries), 190)
        self.assertEqual(integrity, {"complete": len(entries) - 4, "truncated": 2, "corrupted": 2})
        self.assertEqual(scopes, {"windows": legacy_judgment, "any": len(entries) - legacy_judgment})
        self.assertEqual(structure, {"true": len(L.STUB_SCENARIOS), "null": len(entries) - len(L.STUB_SCENARIOS)})

    def test_manifest_level_errors_carry_entry_prefix(self) -> None:
        """新字段出错时，整份清单的错误 field 带 /entries/<i> 前缀；对照：同样的修改在另一些条目上被接受。"""
        manifest = load_manifest()
        ids = [e["fixture_id"] for e in manifest["entries"]]
        c1 = ids.index("synthetic-doc-c.1-manifest-entry-completed")
        stub = ids.index(STUB_ENTRY_SOURCE_ID)
        truncated = ids.index(L.negative_event_fixture_id("ok-truncated-tail"))

        def set_key(key: str, value: Any) -> Callable[[Dict[str, Any]], None]:
            return lambda e: e.__setitem__(key, value)

        def add_claim(claim: str) -> Callable[[Dict[str, Any]], None]:
            return lambda e: e["proves"].append(claim)

        #: (条目下标, 修改, 期望 (code, 条目内 field, reason))；期望为 None 表示对照：整份清单仍被接受。
        cases = (
            (c1, set_key("integrity", "intact"), ("E_SCHEMA_FIELDS", "/integrity", "value_not_in_enum")),
            (c1, set_key("platform_scope", ["linux", "linux"]),
             ("E_SCHEMA_FIELDS", "/platform_scope/1", "duplicate_platform")),
            (c1, set_key("platform_scope", ["ANY"]), ("E_SCHEMA_FIELDS", "/platform_scope/0", "value_not_in_enum")),
            (c1, set_key("platform_scope", "any"), ("E_SCHEMA_TYPE", "/platform_scope", "array_required")),
            (c1, lambda e: e.pop("capture"), ("E_SCHEMA_FIELDS", "/capture", "missing_field")),
            (c1, lambda e: e["origin"].pop("traceable"), ("E_SCHEMA_FIELDS", "/origin/traceable", "missing_field")),
            (stub, lambda e: e["origin"].__setitem__("traceable", False),
             ("E_PROVENANCE_CLAIM", "/origin/traceable", "traceable_required_for_legacy_or_captured")),
            (stub, lambda e: e["redaction"].__setitem__("protocol_structure_preserved", "yes"),
             ("E_SCHEMA_TYPE", "/redaction/protocol_structure_preserved", "boolean_required")),
            # 登记为 truncated 的事件负例不能声称完整运行流；同一声明放在 complete 的条目上被接受。
            (truncated, add_claim("full_run_replay"),
             ("E_PROVENANCE_CLAIM", "/proves", "incomplete_fixture_cannot_prove_complete_stream")),
            (c1, add_claim("full_run_replay"), None),
            # 收尾轮返工（复审 fidelity 视角 major）：复审在同一真实条目上实测能绕过前缀规则的同义名称，按受控词表拒绝。
            (truncated, add_claim("complete_run"),
             ("E_PROVENANCE_CLAIM", "/proves", "incomplete_fixture_cannot_prove_complete_stream")),
            (truncated, add_claim("run_stream_complete"),
             ("E_PROVENANCE_CLAIM", "/proves", "incomplete_fixture_cannot_prove_complete_stream")),
            (truncated, add_claim("complete_event_stream"),
             ("E_PROVENANCE_CLAIM", "/proves", "incomplete_fixture_cannot_prove_complete_stream")),
            (truncated, add_claim("full_event_log"),
             ("E_PROVENANCE_CLAIM", "/proves", "incomplete_fixture_cannot_prove_complete_stream")),
            (truncated, add_claim("entire_run_stream"),
             ("E_PROVENANCE_CLAIM", "/proves", "incomplete_fixture_cannot_prove_complete_stream")),
            (truncated, add_claim("partial_run_stream"), None),
            (c1, add_claim("entire_run_stream"), None),
            # stub 流的 cwd 替换登记为保留协议结构（true），可以声称协议字段语义；改为 false 后同一声明被拒绝。
            (stub, add_claim("protocol_field_semantics_session_header"), None),
            (stub, lambda e: (e["redaction"].__setitem__("protocol_structure_preserved", False),
                              e["proves"].append("protocol_field_semantics_session_header")),
             ("E_PROVENANCE_CLAIM", "/proves", "structure_not_preserved_cannot_prove_field_semantics")),
            (stub, lambda e: (e["redaction"].__setitem__("protocol_structure_preserved", False),
                              e["proves"].append("field_semantics")),
             ("E_PROVENANCE_CLAIM", "/proves", "structure_not_preserved_cannot_prove_field_semantics")),
            (stub, add_claim("field_semantics"), None),
        )
        for index, change, expected in cases:
            with self.subTest(fixture_id=ids[index], expected=expected):
                changed = _copy_json(manifest)
                change(changed["entries"][index])
                if expected is None:
                    P.validate_fixture_manifest_set(changed, registry())
                    continue
                with self.assertRaises(P.ProtocolError) as caught:
                    P.validate_fixture_manifest_set(changed, registry())
                code, field, reason = expected
                self.assertEqual((caught.exception.code, caught.exception.field, caught.exception.reason),
                                 (code, "/entries/%d%s" % (index, field), reason))

    def test_two_step_negatives_each_step_alone_accepted(self) -> None:
        base = read_fixture(SYNTHETIC_PATHS[_FM])
        for slug, steps in R11_TWO_STEP_VARIANTS.items():
            spec = next(s for s in NEGATIVE_SPECS if s.slug == slug)
            for number, step in enumerate(steps, start=1):
                with self.subTest(slug=slug, step=number):
                    ENTRY_RUNNERS[spec.entry](step(base))  # 单独一步：仍被接受
            self.assertEqual(read_fixture(negative_path(spec)), chain(*steps)(base))

    def test_c1_completed_entry_matches_protocols_api_example(self) -> None:
        """synthetic-doc-c.1-manifest-entry-completed 与 protocols-api.md 14.1 的补齐示例逐值相同（条目 description
        的声称由此核对）。"""
        path = REPO_ROOT / "docs" / "code-kit-v2" / "01-baseline" / "protocols-api.md"
        text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
        example = P.strict_json_loads(doc_code_block(text, "### 14.1 条目结构", "json", 0))
        self.assertEqual(example, P.strict_json_loads(read_fixture(SYNTHETIC_PATHS[_FM])))

    def test_whole_manifest_bytes_pass_fixture_manifest_payload_validator(self) -> None:
        """整份 manifest.json 按资源类型 fixture-manifest 核验（R-P10：摘要 → 载荷表示 json → 校验器
        validate_fixture_manifest_set）；旧结构与未知版本的清单字节被拒绝，校验器的错误码原样传出。"""
        raw = read_fixture(MANIFEST_PATH)

        def ref(data: bytes) -> Dict[str, Any]:
            return {"kind": "fixture-manifest", "id": "codekit01-fixture-manifest", "sha256": P.sha256_hex(data),
                    "path": MANIFEST_PATH}

        result = P.validate_resource_payload(ref(raw), raw, registry())
        self.assertEqual(result["kind"], "fixture-manifest")
        self.assertTrue(result["payload_validated"])
        self.assertIn("payload_validator", result["semantic_checks"])
        with self.assertRaises(P.ProtocolError) as caught:
            P.validate_resource_payload(ref(raw), raw + b"\n", registry())
        self.assertEqual(caught.exception.code, "E_RESOURCE_HASH_MISMATCH")
        old_structure = load_manifest()
        del old_structure["entries"][0]["capture"]
        version_2 = load_manifest()
        version_2["schema_version"] = 2
        for label, data, expected in (
                ("缺收尾轮字段的旧结构", render_json(old_structure),
                 ("E_SCHEMA_FIELDS", "/entries/0/capture", "missing_field")),
                ("schema_version=2", render_json(version_2),
                 ("E_SCHEMA_VERSION_UNSUPPORTED", "/schema_version", "schema_version_unsupported")),
                ("UTF-8 BOM", b"\xef\xbb\xbf" + raw, ("E_JSON_BOM", None, "utf8_bom_not_accepted"))):
            with self.subTest(case=label):
                with self.assertRaises(P.ProtocolError) as caught:
                    P.validate_resource_payload(ref(data), data, registry())
                self.assertEqual((caught.exception.code, caught.exception.field, caught.exception.reason), expected)


# ---------------------------------------------------------------------------
# 收尾轮：fixture 凭据扫描（文档 8.3“fixture 含真实凭据”）
# ---------------------------------------------------------------------------

#: 凭据形态（规则名, 正则）。只匹配 ASCII；有捕获组时第 1 组是“值”，否则整个匹配是值。每条规则在原字节（UTF-8 视图）、
#: UTF-16 LE/BE 各两种对齐的 ASCII 视图，以及能严格解析的 JSON/JSONL 中的每个字符串上各运行一次。secret_assignment
#: 只在值像长随机串时算命中（_looks_random），避免把 "input_tokens": 1000、"reason": "not_reported" 这类字段当成凭据。
#: 覆盖的形态就是下面这 15 条（收尾轮返工由 9 条增加 6 条：Stripe、Hugging Face、GitLab、npm 令牌，HTTP Basic 认证头，
#: URL 内嵌口令；复审 fidelity 视角 major）。清单之外的形态不会被发现，例如没有固定前缀、也不在凭据类键名、Bearer/Basic
#: 认证头或 URL 写法中的口令，以及其他厂商的专有前缀。这是形态匹配，不是完整的秘密检测。
CREDENTIAL_RULES: Tuple[Tuple[str, str], ...] = (
    ("bearer_token", r"(?i)\bbearer[ \t]+([A-Za-z0-9._~+/-]{16,}=*)"),
    ("sk_prefixed_key", r"\b(sk-(?:[A-Za-z0-9]+-)?[A-Za-z0-9_-]{20,})"),
    ("github_token", r"\b((?:gh[pousr]_[A-Za-z0-9]{30,})|(?:github_pat_[A-Za-z0-9_]{20,}))"),
    ("slack_token", r"\b(xox[abposr]-[A-Za-z0-9-]{10,})"),
    ("pem_private_key", r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----"),
    ("aws_access_key_id", r"\b((?:AKIA|ASIA|AGPA|AIDA|AROA|ANPA)[A-Z0-9]{16})\b"),
    ("google_api_key", r"\b(AIza[0-9A-Za-z_-]{35})"),
    ("jwt", r"\b(eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})"),
    ("secret_assignment", r"(?i)(?:api[_-]?key|apikey|secret|token|passwd|password|access[_-]?key|auth)"
                          r"[a-z0-9_-]*[\"']?[ \t]*[:=][ \t]*[\"']?([A-Za-z0-9+/_.~-]{20,})"),
    # 收尾轮返工：复审实测漏掉的 7 种写法（sk_live_ 与 rk_live_ 同属 Stripe 一条）。
    ("stripe_key", r"((?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,})"),
    ("huggingface_token", r"(hf_[A-Za-z]{30,})"),
    ("gitlab_token", r"(glpat-[A-Za-z0-9_-]{20,})"),
    ("npm_token", r"(npm_[A-Za-z0-9]{36})"),
    ("basic_auth", r"(?i)\bbasic[ \t]+([A-Za-z0-9+/]{16,}={0,2})"),
    ("url_credentials", r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:([^/\s@]{8,})@"),
)
#: JSON 视图中“键名像凭据字段”的判定（值另须 _looks_random）。
_SECRET_KEY_RE = re.compile(r"(?i)(?:api[_-]?key|apikey|secret|token|passwd|password|access[_-]?key|auth)")
#: 凭据值是一个连续的可打印 ASCII 串（不含空白）。
_PRINTABLE_TOKEN_RE = re.compile(r"[!-~]+")

#: 已知合成标记的白名单：(名称, 值必须整串匹配的正则, 来源)。只按命中的“值”整串放行，不按文件或规则整体放行；
#: 标记后面多出任何字符（例如接上随机串）就不再放行。本次扫描时 fixture 目录中没有出现这些标记；登记它们是因为仓库
#: 的脱敏自测与取证归档使用这些合成值，今后从那里派生 fixture 时可能带入。
CREDENTIAL_ALLOWLIST: Tuple[Tuple[str, str, str], ...] = (
    ("DEMO_REVIEW_SECRET", r"DEMO_REVIEW_SECRET[0-9]{0,2}",
     "tests/test_dispatch.py:1607-1619 脱敏自测的合成值 DEMO_REVIEW_SECRET、DEMO_REVIEW_SECRET2 至 "
     "DEMO_REVIEW_SECRET11；baseline-report.md 第 9 节 L-EVID-SECRETS 登记为合成示例值"),
    ("DEMO_TOKEN_FOR_REVIEW", r"DEMO_TOKEN_FOR_REVIEW",
     "tests/test_dispatch.py:728、1601 doctor 凭据回显脱敏自测的合成值（apiKey=DEMO_TOKEN_FOR_REVIEW）；"
     "baseline-report.md L-EVID-SECRETS"),
    ("SYNTHETIC_CREDENTIAL", r"SYNTHETIC_(?:REVIEW_)?CREDENTIAL(?:_[A-Z0-9]+)*",
     "evidence/run-controls/offline-boundary.redacted.json 说明文字中的 SYNTHETIC_CREDENTIAL，以及取证归档差异中的 "
     "SYNTHETIC_REVIEW_CREDENTIAL（baseline-report.md L-EVID-SECRETS）；允许用大写字母、数字组成的 _后缀区分样本"),
)

_CREDENTIAL_PATTERNS = tuple((name, re.compile(pattern), re.compile(pattern.encode("ascii")))
                             for name, pattern in CREDENTIAL_RULES)
_ALLOW_PATTERNS = tuple((name, re.compile(pattern)) for name, pattern, _source in CREDENTIAL_ALLOWLIST)


def _looks_random(value: str) -> bool:
    """值像长随机串：至少 20 个字符，整串是不含空白的可打印 ASCII（说明文字、含非 ASCII 的文本不算），小写字母、
    大写字母、数字三类中至少出现两类，按字符计的香农熵不低于 3.0 位。"""
    if len(value) < 20 or _PRINTABLE_TOKEN_RE.fullmatch(value) is None:
        return False
    classes = sum(1 for chars in ("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "0123456789")
                  if any(ch in chars for ch in value))
    counts: Dict[str, int] = {}
    for ch in value:
        counts[ch] = counts.get(ch, 0) + 1
    entropy = -sum(n / len(value) * math.log2(n / len(value)) for n in counts.values())
    return classes >= 2 and entropy >= 3.0


def _allowlisted(value: str) -> Optional[str]:
    for name, pattern in _ALLOW_PATTERNS:
        if pattern.fullmatch(value):
            return name
    return None


def _rule_hits(text: Any) -> List[Tuple[str, int, str]]:
    """text（str 或 bytes）中的凭据形态命中：(规则名, 偏移, 值)。值只用于白名单判断，不进入任何输出。"""
    is_bytes = isinstance(text, bytes)
    hits: List[Tuple[str, int, str]] = []
    for name, str_pattern, bytes_pattern in _CREDENTIAL_PATTERNS:
        pattern = bytes_pattern if is_bytes else str_pattern
        for match in pattern.finditer(text):
            value = match.group(1) if pattern.groups else match.group(0)
            if is_bytes:
                value = value.decode("ascii", "replace")
            if name == "secret_assignment" and not _looks_random(value):
                continue
            hits.append((name, match.start(), value))
    return hits


def _utf16_ascii_view(raw: bytes, big_endian: bool, shift: int) -> bytes:
    """按 UTF-16（LE 或 BE，从第 shift 个字节起对齐）取码元：码元是可打印 ASCII 时保留该字符，否则写 NUL。
    视图第 i 个字节对应原文件偏移 shift + 2*i。"""
    data = raw[shift:]
    first, second = data[0::2], data[1::2]
    low, high = (second, first) if big_endian else (first, second)
    return bytes(lo if hi == 0 and 0x20 <= lo < 0x7F else 0 for lo, hi in zip(low, high))


def _json_documents(label: str, raw: bytes) -> List[Tuple[str, Any]]:
    """能严格解析的 JSON 文档：.json 整份；.jsonl 按 LF 逐行（行尾 CR 属于 JSON 空白）。解析不了的（故意损坏的负例、
    D-21 的深层嵌套负例）跳过，这些文件仍由字节视图扫描。"""
    limit = max(len(raw) + 1, P.DEFAULT_MAX_BYTES)
    documents: List[Tuple[str, Any]] = []
    if label.endswith(".json"):
        try:
            documents.append(("JSON", P.strict_json_loads(raw, max_bytes=limit)))
        except P.ProtocolError:
            pass
    elif label.endswith(".jsonl"):
        for number, line in enumerate(raw.split(b"\n"), start=1):
            if line.strip():
                try:
                    documents.append(("JSONL 第 %d 行" % number, P.strict_json_loads(line, max_bytes=limit)))
                except P.ProtocolError:
                    pass
    return documents


def _json_strings(value: Any) -> List[Tuple[Optional[str], str]]:
    """JSON 值中的每个字符串（对象的键与字符串值），按确定的顺序：(所属键, 字符串)，键本身与数组元素的所属键为 None。"""
    out: List[Tuple[Optional[str], str]] = []
    stack: List[Tuple[Optional[str], Any]] = [(None, value)]
    while stack:
        key, item = stack.pop()
        if isinstance(item, str):
            out.append((key, item))
        elif isinstance(item, dict):
            for name, child in item.items():
                out.append((None, name))
                stack.append((name, child))
        elif isinstance(item, list):
            stack.extend((None, child) for child in item)
    return out


def scan_bytes_for_credentials(label: str, raw: bytes) -> Tuple[List[str], List[str]]:
    """扫描一个文件的字节。返回 (问题, 白名单放行)，两者都只含文件、视图、偏移（或 JSON 中第几个字符串）与规则名，
    放行记录另含白名单条目名；**不含**匹配到的值。"""
    problems: List[str] = []
    allowed: List[str] = []

    def record(view: str, location: str, rule: str, value: str) -> None:
        text = "%s：%s，%s：%s" % (label, view, location, rule)
        name = _allowlisted(value)
        if name is None:
            problems.append(text)
        else:
            allowed.append("%s（白名单 %s）" % (text, name))

    for rule, offset, value in _rule_hits(raw):
        record("原字节（UTF-8 视图）", "偏移 %d" % offset, rule, value)
    for big_endian in (False, True):
        for shift in (0, 1):
            view = "UTF-16%s 视图（对齐 %d）" % ("BE" if big_endian else "LE", shift)
            for rule, offset, value in _rule_hits(_utf16_ascii_view(raw, big_endian, shift)):
                record(view, "偏移 %d" % (shift + 2 * offset), rule, value)
    for where, document in _json_documents(label, raw):
        for index, (key, text) in enumerate(_json_strings(document)):
            place = "%s 解析后的第 %d 个字符串" % (where, index)
            for rule, offset, value in _rule_hits(text):
                record(place, "字符 %d" % offset, rule, value)
            if key is not None and _SECRET_KEY_RE.search(key) and _looks_random(text):
                record(place, "键名像凭据字段", "secret_assignment", text)
    return problems, allowed


def _credential_samples() -> Dict[str, str]:
    """每条规则一个在运行时拼出的样本（源码中不出现完整的凭据形态字面量）。只在内存中使用，不写文件。"""
    digest = hashlib.sha256(b"codekit01 credential scan self-test").hexdigest()
    mixed = "".join(ch.upper() if index % 3 == 0 else ch for index, ch in enumerate(digest * 2))
    return {
        "bearer_token": "Authorization: " + "Bear" + "er " + mixed[:32],
        "sk_prefixed_key": "s" + "k-" + mixed[:40],
        "github_token": "gh" + "p_" + mixed[:36],
        "slack_token": "xo" + "xb-" + digest[:12] + "-" + digest[12:30],
        "pem_private_key": "-----BEGIN " + "RSA PRIV" + "ATE KEY-----",
        "aws_access_key_id": "AK" + "IA" + digest[:16].upper(),
        "google_api_key": "AI" + "za" + mixed[:35],
        "jwt": "ey" + "J" + mixed[:20] + ".ey" + "J" + mixed[20:40] + "." + mixed[40:60],
        "secret_assignment": "api" + "_key = " + mixed[:32],
        # 收尾轮返工新增的 6 条规则。
        "stripe_key": "sk" + "_live_" + mixed[:24],
        "huggingface_token": "hf" + "_" + _letters(digest, 34),
        "gitlab_token": "glp" + "at-" + mixed[:20],
        "npm_token": "np" + "m_" + mixed[:36],
        "basic_auth": "Authorization: " + "Bas" + "ic " + base64.b64encode(("deploy:" + mixed[:24]).encode("ascii"))
        .decode("ascii"),
        "url_credentials": "https" + "://deploy:" + mixed[:20] + "@example.invalid/repo.git",
    }


def _letters(digest: str, count: int) -> str:
    """把十六进制摘要映射成大小写交替的 ASCII 字母串（Hugging Face 令牌的形态只含字母）。"""
    text = "".join(chr(ord("a") + int(ch, 16)) for ch in digest * 2)[:count]
    return "".join(ch.upper() if index % 2 else ch for index, ch in enumerate(text))


def _credential_variant_samples() -> List[Tuple[str, str, str]]:
    """同一条规则中其他前缀或写法的样本：(规则名, 说明, 样本)。收尾轮返工（复审 tests-mutation 视角）：此前每条规则只有
    一个样本，AWS 的 ASIA 等前缀、GitHub 的 gho_ 等前缀从正则中删去也不会被发现。同样在运行时拼出，只在内存中使用。"""
    digest = hashlib.sha256(b"codekit01 credential scan variants").hexdigest()
    mixed = "".join(ch.upper() if index % 3 == 0 else ch for index, ch in enumerate(digest * 2))
    samples: List[Tuple[str, str, str]] = []
    for prefix in ("AK" + "IA", "AS" + "IA", "AG" + "PA", "AI" + "DA", "AR" + "OA", "AN" + "PA"):
        samples.append(("aws_access_key_id", prefix, prefix + digest[:16].upper()))
    for prefix in ("gh" + "p_", "gh" + "o_", "gh" + "u_", "gh" + "s_", "gh" + "r_"):
        samples.append(("github_token", prefix, prefix + mixed[:36]))
    samples.append(("github_token", "github_pat_", "github" + "_pat_" + mixed[:22] + "_" + mixed[22:44]))
    for letter in "abposr":
        samples.append(("slack_token", "xox%s-" % letter, "xo" + "x" + letter + "-" + digest[:12] + "-" + digest[12:30]))
    samples.append(("sk_prefixed_key", "sk-proj-", "s" + "k-proj-" + mixed[:40]))
    samples.append(("sk_prefixed_key", "sk-ant-api03-", "s" + "k-ant-api03-" + mixed[:40]))
    for head in ("sk" + "_test_", "rk" + "_live_", "rk" + "_test_", "pk" + "_live_", "pk" + "_test_"):
        samples.append(("stripe_key", head, head + mixed[:24]))
    for kind in ("", "EC ", "OPENSSH ", "ENCRYPTED "):
        samples.append(("pem_private_key", kind or "PKCS#8", "-----BEGIN " + kind + "PRIV" + "ATE KEY-----"))
    samples.append(("bearer_token", "小写 bearer", "authorization: " + "bear" + "er " + mixed[:32]))
    samples.append(("basic_auth", "大写 BASIC", "AUTHORIZATION: " + "BAS" + "IC " + base64.b64encode(
        ("ci-user:" + mixed[:30]).encode("ascii")).decode("ascii")))
    for scheme in ("http", "git+ssh", "postgres"):
        samples.append(("url_credentials", scheme, scheme + "://svc:" + mixed[:16] + "@db.example.invalid:5432/x"))
    for assignment in ("OPENAI_API" + "_KEY=", "AWS_SECRET" + "_ACCESS_KEY=", "pass" + "word: ", "client_" + "secret = "):
        samples.append(("secret_assignment", assignment, assignment + mixed[:32]))
    return samples


class CredentialScanTests(unittest.TestCase):
    """文档 8.3“fixture 含真实凭据”：逐字节扫描 tests/fixtures/codekit01/ 下的每个文件，命中凭据形态（非白名单）即失败。
    当前入库 fixture 也不得依赖合成标记白名单放行；白名单功能仅在专门的扫描器对照测试中验证。
    失败信息只给文件、视图与偏移（或 JSON 中第几个字符串）和规则名，不回显匹配到的值。发现真实凭据后的处置（停止分发、
    限制访问、凭据处置、事故记录）归规划端与用户，不由测试执行。"""

    def test_fixture_files_contain_no_credential_shapes(self) -> None:
        paths = fixture_files_on_disk()
        self.assertEqual(len(paths), len(manifest_entries()) + 1, "扫描范围应是全部登记文件加 manifest.json 本身")
        problems: List[str] = []
        allowlisted: List[str] = []
        # 收尾轮返工（复审 tests-mutation 视角）：累计实际扫描的文件数与字节数，核对确实逐个扫描了全部文件的全部字节
        # （此前只扫第一个文件也能通过）。期望字节数按文件大小独立计算，不经 read_fixture。
        scanned_files = 0
        scanned_bytes = 0
        for path in paths:
            raw = read_fixture(path)
            found, allowed = scan_bytes_for_credentials(path, raw)
            scanned_files += 1
            scanned_bytes += len(raw)
            problems.extend(found)
            allowlisted.extend(allowed)
        self.assertEqual(scanned_files, len(paths))
        self.assertEqual(scanned_bytes, sum(repo_path(path).stat().st_size for path in paths))
        self.assertGreater(scanned_bytes, 0)
        self.assertEqual(allowlisted, [], "入库 fixture 不得依赖凭据扫描白名单放行（只列位置与规则，不回显值）")
        if problems:
            more = "\n……另有 %d 处" % (len(problems) - 50) if len(problems) > 50 else ""
            self.fail("fixture 中出现凭据形态（只列位置与规则，不回显值；按文档 8.3 停止分发并交规划端处置）：\n"
                      + "\n".join(problems[:50]) + more)

    def test_scanner_detects_every_rule_in_every_view(self) -> None:
        """对照：每条规则的样本分别放进原字节、UTF-16 LE（两种对齐）、UTF-16 BE，以及只有解析后才可见的 JSON \\u 转义，
        都被发现；失败信息中不出现样本的值。收尾轮返工：每条规则都有样本（集合相等），另对同一规则中的其他前缀或写法
        （_credential_variant_samples：AWS 的 6 个前缀、GitHub 的 6 种、Slack 的 6 种、sk- 的 proj/ant 写法、Stripe 的
        6 种组合等）逐一核对。"""
        backslash = chr(92)
        self.assertEqual(set(_credential_samples()), {name for name, _pattern in CREDENTIAL_RULES})
        self.assertEqual(len(CREDENTIAL_RULES), 15)
        variants = _credential_variant_samples()
        self.assertTrue({rule for rule, _label, _sample in variants} <= {name for name, _pattern in CREDENTIAL_RULES})
        aws = [label for rule, label, _sample in variants if rule == "aws_access_key_id"]
        self.assertEqual(sorted(aws), ["AGPA", "AIDA", "AKIA", "ANPA", "AROA", "ASIA"])
        cases = [(rule, rule, sample) for rule, sample in _credential_samples().items()] + variants
        for rule, variant, sample in cases:
            text = "prefix " + sample + " suffix\n"
            escaped = "".join("%su%04x" % (backslash, ord(ch)) for ch in sample)
            contexts = (
                ("sample.txt", text.encode("ascii"), "原字节"),
                ("sample.txt", text.encode("utf-16-le"), "UTF-16LE 视图（对齐 0）"),
                ("sample.txt", b"\x00" + text.encode("utf-16-le"), "UTF-16LE 视图（对齐 1）"),
                ("sample.txt", text.encode("utf-16-be"), "UTF-16BE 视图（对齐 0）"),
                ("sample.json", ('{"note": "%s"}\n' % escaped).encode("ascii"), "JSON 解析后"),
                ("sample.jsonl", ('{"a": 1}\n{"note": "%s"}\n' % escaped).encode("ascii"), "JSONL 第 2 行 解析后"),
            )
            for label, raw, view in contexts:
                with self.subTest(rule=rule, variant=variant, view=view):
                    problems, allowed = scan_bytes_for_credentials(label, raw)
                    self.assertEqual(allowed, [])
                    self.assertTrue(any(view in p and p.endswith("：" + rule) for p in problems),
                                    "规则 %s（%s）在 %s 中没有被发现" % (rule, variant, view))
                    joined = "\n".join(problems)
                    for secret_part in (sample, sample[-16:]):
                        self.assertNotIn(secret_part, joined, "失败信息回显了匹配到的值")

    def test_secret_key_in_json_with_random_value_detected(self) -> None:
        """JSON 中键名像凭据字段、值像长随机串时发现（值被 \\u 转义也一样）；值像普通文字或数字时不算。"""
        value = _credential_samples()["secret_assignment"].split("= ")[1]
        backslash = chr(92)
        escaped = "".join("%su%04x" % (backslash, ord(ch)) for ch in value)
        problems, _ = scan_bytes_for_credentials("k.json", ('{"clientSecret": "%s"}' % escaped).encode("ascii"))
        self.assertTrue(any("键名像凭据字段" in p for p in problems))
        with_symbols = "!@" + value[:10] + "#%" + value[10:20]  # 口令可以含符号
        problems, _ = scan_bytes_for_credentials("k.json", json.dumps({"db_password": with_symbols}).encode("ascii"))
        self.assertTrue(any("键名像凭据字段" in p for p in problems))
        for benign in (b'{"input_tokens": 1000, "reasoning_tokens": "not_reported"}',
                       # 收尾轮返工（复审 tests-mutation 视角）：键名像凭据、值够长且有两类字符，但熵很低（30 个 A 加 2 个
                       # 数字，约 0.34 位），固定 _looks_random 的熵阈值：去掉熵条件时这里失败。
                       b'{"api_key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA11"}',
                       b'{"token_budget": "tracking-only-without-any-limit"}',
                       # 说明文字（含空白或非 ASCII）不是凭据值：legacy-events.json 的 token_zero_semantics 就是这种
                       json.dumps({"token_zero_semantics": "旧实现 token 缺失时输出 0 而不是 null；ABCdef0123456789XYZ"},
                                  ensure_ascii=False).encode("utf-8")):
            with self.subTest(benign=benign):
                self.assertEqual(scan_bytes_for_credentials("b.json", benign), ([], []))

    def test_allowlist_is_exact_and_documented(self) -> None:
        """白名单只放行整串匹配的合成标记；标记后多出随机串就不再放行。每个条目都写明来源。"""
        tail = _credential_samples()["secret_assignment"][-8:]
        for text, name in (("password=DEMO_REVIEW_SECRET10", "DEMO_REVIEW_SECRET"),
                           ("Authorization: Bearer DEMO_TOKEN_FOR_REVIEW", "DEMO_TOKEN_FOR_REVIEW"),
                           ("api_key: SYNTHETIC_CREDENTIAL_2026", "SYNTHETIC_CREDENTIAL")):
            with self.subTest(marker=name):
                problems, allowed = scan_bytes_for_credentials("m.txt", text.encode("ascii"))
                self.assertEqual(problems, [])
                self.assertTrue(allowed and all("白名单 %s" % name in a for a in allowed))
                problems, allowed = scan_bytes_for_credentials("m.txt", (text + tail).encode("ascii"))
                self.assertTrue(problems, "标记后接随机串时仍被放行")
                self.assertEqual(allowed, [])
        for name, pattern, source in CREDENTIAL_ALLOWLIST:
            with self.subTest(entry=name):
                self.assertTrue(re.fullmatch(pattern, name), "条目名本身应是被放行的标记")
                self.assertIn(".", source, "来源说明应指向具体文件")


# ---------------------------------------------------------------------------
# 收尾轮：兼容矩阵第 1 节的抽查写成回归测试（acceptance.md M-04）
# ---------------------------------------------------------------------------

EVIDENCE_DIR = REPO_ROOT / "docs" / "code-kit-v2" / "01-baseline" / "evidence"
#: 01 基线取证的四种内部记录与归档中的文件名。
BASELINE_RECORD_FILES = (("baseline-capture", "capture.json"), ("baseline-input-manifest", "input-manifest.json"),
                         ("baseline-environment", "environment.json"),
                         ("baseline-archive-manifest", "archive-manifest.json"))


class PublicEntryRejectionTests(unittest.TestCase):
    """合同 v1 与 01 内部记录（fixture-manifest-set、baseline-*）都不是公共记录：交给公共入口按稳定错误码拒绝，
    不降级、不回退 v1，也不修改输入（兼容矩阵第 1 节抽查、第 2 节“01 内部记录”行、E07）。基线记录取自入库的脱敏
    归档 evidence/（.agent/baseline/ 的原件被 Git 忽略，测试不依赖它）。"""

    def _expect(self, func: Callable[..., Any], value: Any, expected: Tuple[str, Optional[str], str],
                **kwargs: Any) -> None:
        before = render_json(value)
        with self.assertRaises(P.ProtocolError) as caught:
            func(value, **kwargs)
        self.assertEqual((caught.exception.code, caught.exception.field, caught.exception.reason), expected)
        self.assertEqual(render_json(value), before, "入口修改了输入")

    def test_contract_v1_json_is_not_a_public_record(self) -> None:
        contracts = [(fid, path) for fid, _src, path, _d in L.LEGACY_CONTRACT_FILES if path.endswith(".json")]
        self.assertEqual(len(contracts), 3)
        for fixture_id, path in contracts:
            with self.subTest(fixture_id=fixture_id):
                contract = P.strict_json_loads(read_fixture(path))
                self.assertNotIn("record_type", contract)
                self._expect(P.validate_public_record, contract,
                             ("E_SCHEMA_RECORD_TYPE", "/record_type", "record_type_mismatch"),
                             expected_record_type="run-context", registry=registry())
                self._expect(P.route_public_record, contract, ("E_COMPAT_UNSUPPORTED", None, "record_type_unsupported"),
                             expected_record_type="contract")

    def test_fixture_manifest_set_is_internal_and_version_2_rejected(self) -> None:
        manifest = load_manifest()
        self._expect(P.route_public_record, manifest, ("E_COMPAT_UNSUPPORTED", None, "record_type_unsupported"),
                     expected_record_type="fixture-manifest-set")
        self._expect(P.validate_public_record, manifest,
                     ("E_SCHEMA_RECORD_TYPE", "/record_type", "record_type_mismatch"),
                     expected_record_type="run-context", registry=registry())
        manifest["schema_version"] = 2
        before = render_json(manifest)
        with self.assertRaises(P.ProtocolError) as caught:
            P.validate_fixture_manifest_set(manifest, registry())
        self.assertEqual((caught.exception.code, caught.exception.field, caught.exception.reason),
                         ("E_SCHEMA_VERSION_UNSUPPORTED", "/schema_version", "schema_version_unsupported"))
        self.assertEqual(render_json(manifest), before, "未知版本不得被改写或回退到 v1 解释")

    def test_baseline_records_are_internal(self) -> None:
        for record_type, name in BASELINE_RECORD_FILES:
            paths = sorted(EVIDENCE_DIR.rglob(name))
            with self.subTest(record_type=record_type):
                self.assertTrue(paths, "归档中没有 %s（01 的脱敏归档应随仓库存在）" % name)
            for path in paths:
                with self.subTest(path=path.relative_to(REPO_ROOT).as_posix()):
                    record = P.strict_json_loads(path.read_bytes())  # 严格 JSON 层接受
                    self.assertEqual(record.get("record_type"), record_type)
                    self._expect(P.route_public_record, record,
                                 ("E_COMPAT_UNSUPPORTED", None, "record_type_unsupported"),
                                 expected_record_type=record_type)
                    self._expect(P.validate_public_record, record,
                                 ("E_SCHEMA_RECORD_TYPE", "/record_type", "record_type_mismatch"),
                                 expected_record_type="run-context", registry=registry())


# ---------------------------------------------------------------------------
# 收尾轮：兼容矩阵 D-20–D-23 的 legacy 负例（acceptance.md M-04）
# ---------------------------------------------------------------------------

class MissingFieldLegacyTests(unittest.TestCase):
    """文档 6.6 的缺字段样本：锁定必填合同字段缺失的拒绝，以及旧事件摘要将缺失 token 当 0 的现状。

    差分测试另行重算所有锁定投影；这里用独立的字节/字段断言防止把缺失改成空值，或连费用与相邻消息一起删掉。
    """

    def test_missing_required_contract_field_is_rejected_without_default(self) -> None:
        fixture_id = "negative-legacy-contract-json-missing-task-id"
        entries = {e["fixture_id"]: e for e in manifest_entries()}
        self.assertTrue(fixture_id in entries, "JSON 合同缺必填字段必须有可追溯的 legacy fixture")
        entry = entries[fixture_id]
        base_id = "legacy-contract-normalize-query-v1-json"
        self.assertEqual(entry["origin"]["derived_from"], base_id)
        original = read_fixture(entries[base_id]["resource"]["path"])
        raw = read_fixture(entry["resource"]["path"])
        self.assertEqual(raw, original.replace(b'  "task_id": "normalize-query",\n', b"", 1))
        parsed = json.loads(raw)
        self.assertNotIn("task_id", parsed)
        before = json.loads(original)
        del before["task_id"]
        self.assertEqual(parsed, before)
        locked = json.loads(read_fixture(L.EXPECTED_CONTRACTS_PATH))["cases"][fixture_id]["legacy"]
        self.assertNotIn("task_id", locked["normalize_contract"]["contract"])
        self.assertFalse(locked["inprocess_validate_plan"]["contract_returned"])
        self.assertIn("task_id 应为 normalize-query，实际为 None", locked["inprocess_validate_plan"]["errors"])
        self.assertEqual(locked["cli_validate_temp_repo"]["exit_code"], 2)
        strict = json.loads(read_fixture(L.EXPECTED_NEW_STRICT_PATH))["json_documents"][fixture_id]["new_strict"]
        self.assertEqual((strict["accepted"], strict["code"]), (True, None),
                         "新严格入口只判断 JSON 文法；不把通过解释成合同字段有效")

    def test_usage_without_tokens_preserves_cost_and_only_zeros_missing_message(self) -> None:
        fixture_id = "negative-legacy-events-ok-final-usage-missing-tokens"
        entries = {e["fixture_id"]: e for e in manifest_entries()}
        self.assertTrue(fixture_id in entries, "usage 存在但缺 token 字段必须有可追溯的 legacy fixture")
        entry = entries[fixture_id]
        self.assertEqual(entry["origin"]["derived_from"], "legacy-stub-events-ok")
        original = read_fixture(entries["legacy-stub-events-ok"]["resource"]["path"]).splitlines(keepends=True)
        changed = read_fixture(entry["resource"]["path"]).splitlines(keepends=True)
        self.assertEqual(len(changed), len(original))
        indices = [i for i, (a, b) in enumerate(zip(original, changed)) if a != b]
        self.assertEqual(len(indices), 1, "只能改一条 message_end，其他事件与行尾必须原样保留")
        index = indices[0]
        source, event = json.loads(original[index]), json.loads(changed[index])
        self.assertEqual((event["type"], event["message"]["role"], event["message"]["stopReason"]),
                         ("message_end", "assistant", "stop"))
        self.assertEqual(set(event["message"]["usage"]), {"cost"})
        for key in ("input", "output", "cacheRead", "cacheWrite", "totalTokens"):
            del source["message"]["usage"][key]
        self.assertEqual(event, source, "只删除该消息 usage 的 token 字段，费用/报告/结束信息不变")
        cases = json.loads(read_fixture(L.EXPECTED_EVENTS_PATH))["cases"]
        summaries = cases[fixture_id]["summaries"]
        for label in ("expects_settled=true", "expects_settled=false", "expects_settled=null"):
            with self.subTest(expects_settled=label):
                summary = summaries[label]
                self.assertEqual(summary["usage"], {"input": 1000, "output": 200, "cacheRead": 0,
                                                     "cacheWrite": 0, "totalTokens": 1200})
                self.assertEqual(summary["cost"], cases["legacy-stub-events-ok"]["summaries"][label]["cost"])
                self.assertEqual((summary["cost"]["total"], summary["cost"]["status"],
                                  summary["cost"]["unpriced_messages"]), (0.00086, "estimated", 0))
                self.assertEqual(summary["problems"], [])
        strict = json.loads(read_fixture(L.EXPECTED_NEW_STRICT_PATH))["jsonl_streams"][fixture_id]["new_strict"]
        self.assertEqual(strict["rejected_lines"], [], "新入口的逐行 JSON 接受不等于厂商字段语义校验")


class CompatMatrixDCaseTests(unittest.TestCase):
    """兼容矩阵 4.3 节 D-20–D-23 落为合同单一故障负例：旧判断在 expected/legacy-contracts.json（由 a4fa199 的旧实现
    生成），新严格入口的判断在 expected/legacy-new-strict.json。两份文件由 DifferentialTests 逐字节锁定；这里按矩阵
    的表述逐项断言要点，矩阵与锁定预期不一致时在这里失败。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.legacy = json.loads(read_fixture(L.EXPECTED_CONTRACTS_PATH).decode("utf-8"))["cases"]
        cls.strict = json.loads(read_fixture(L.EXPECTED_NEW_STRICT_PATH).decode("utf-8"))["json_documents"]

    def _case(self, slug: str) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        fixture_id = L.negative_contract_fixture_id(slug)
        document = self.strict.get(fixture_id)
        return self.legacy[fixture_id]["legacy"], (document["new_strict"] if document else None)

    def test_every_d_case_is_a_registered_single_fault_fixture(self) -> None:
        variants = {slug: (target, fault) for slug, target, _transform, fault in L.NEGATIVE_CONTRACT_VARIANTS}
        ids = {e["fixture_id"] for e in manifest_entries()}
        self.assertEqual(sorted(L.COMPAT_MATRIX_D_CASES), ["D-20", "D-21", "D-22", "D-23"])
        # 收尾轮返工（复审 tests-mutation 视角）：反向核对映射表是否完整。凡是故障说明写明“兼容矩阵 D-xx”的合同或事件
        # 负例变体，都必须登记在 COMPAT_MATRIX_D_CASES["D-xx"] 中，两边的集合相等（此前漏登记一个变体也不会被发现）。
        declared: Dict[str, set] = {}
        for slug, _target, _transform, fault in L.NEGATIVE_CONTRACT_VARIANTS:
            for d_case in re.findall(r"兼容矩阵 (D-[0-9]+)", fault):
                declared.setdefault(d_case, set()).add(slug)
        for _slug, _target, _transform, fault in L.NEGATIVE_EVENT_VARIANTS:
            self.assertNotRegex(fault, r"兼容矩阵 D-[0-9]+", "事件负例不在 D-xx 映射表中，故障说明不应引用 D 编号")
        self.assertEqual(declared, {d_case: set(slugs) for d_case, slugs in L.COMPAT_MATRIX_D_CASES.items()})
        for d_case, slugs in L.COMPAT_MATRIX_D_CASES.items():
            self.assertEqual(len(slugs), len(set(slugs)), "%s 的映射有重复变体" % d_case)
        for d_case, slugs in L.COMPAT_MATRIX_D_CASES.items():
            for slug in slugs:
                with self.subTest(d_case=d_case, slug=slug):
                    target, fault = variants[slug]
                    fixture_id = L.negative_contract_fixture_id(slug)
                    self.assertIn("兼容矩阵 " + d_case, fault)
                    self.assertIn(fixture_id, ids)
                    self.assertIn(fixture_id, self.legacy)
                    self.assertEqual(fixture_id in self.strict, target == "json")

    def test_d20_non_finite_cost_amount(self) -> None:
        legacy, strict = self._case("json-cost-budget-infinity")  # 旧：Infinity 通过
        self.assertEqual(legacy["inprocess_validate_plan"]["errors"], [])
        self.assertTrue(legacy["inprocess_validate_plan"]["contract_returned"])
        self.assertEqual(legacy["normalize_contract"]["contract"]["budget"]["cost_budget"]["amount"],
                         L.NON_FINITE_MARKERS["inf"])
        self.assertEqual((strict["accepted"], strict["code"], strict["field"]),
                         (False, "E_JSON_NON_FINITE", "/budget/cost_budget/amount"))
        legacy, strict = self._case("json-cost-budget-nan")  # 旧：NaN 被字段检查拒绝
        self.assertFalse(legacy["inprocess_validate_plan"]["contract_returned"])
        self.assertEqual(legacy["inprocess_validate_plan"]["errors"], ["budget.cost_budget 必须为 null 或 {amount, currency}"])
        self.assertEqual((strict["accepted"], strict["code"], strict["field"]),
                         (False, "E_JSON_NON_FINITE", "/budget/cost_budget/amount"))

    def test_d21_deep_nesting(self) -> None:
        legacy, strict = self._case("json-deep-nesting")
        inprocess, cli = legacy["inprocess_validate_plan"], legacy["cli_validate_temp_repo"]
        self.assertEqual((inprocess["outcome"], inprocess["exception"]), ("uncaught_exception", "RecursionError"))
        self.assertEqual((cli["exit_code"], cli["stdout"]), (1, ""))
        self.assertTrue(cli["stderr"]["traceback_last_line"].startswith("RecursionError: "))
        self.assertEqual((strict["accepted"], strict["code"]), (False, "E_JSON_LIMIT"))

    def test_d22_invalid_utf8(self) -> None:
        legacy, strict = self._case("json-invalid-utf8")  # 旧：JSON 解析失败，CLI 退出 2
        self.assertEqual(legacy["cli_validate_temp_repo"]["exit_code"], 2)
        self.assertEqual(len(legacy["inprocess_validate_plan"]["errors"]), 1)
        self.assertTrue(legacy["inprocess_validate_plan"]["errors"][0].startswith("JSON 合同解析失败：'utf-8' codec"))
        self.assertEqual((strict["accepted"], strict["code"]), (False, "E_JSON_ENCODING"))
        legacy, strict = self._case("md-invalid-utf8")  # 旧：Markdown 未捕获，CLI 以 traceback 退出 1
        inprocess, cli = legacy["inprocess_validate_plan"], legacy["cli_validate_temp_repo"]
        self.assertEqual((inprocess["outcome"], inprocess["exception"]), ("uncaught_exception", "UnicodeDecodeError"))
        self.assertEqual((cli["exit_code"], cli["stdout"]), (1, ""))
        self.assertTrue(cli["stderr"]["traceback_last_line"].startswith("UnicodeDecodeError: "))
        self.assertIsNone(strict, "新严格入口不判断 Markdown")

    def test_d23_identifier_trailing_newline(self) -> None:
        legacy, strict = self._case("json-setup-id-trailing-newline")  # 旧：ITEM_ID_RE 的 $ 放过末尾换行
        self.assertEqual(legacy["inprocess_validate_plan"]["errors"], [])
        self.assertTrue(legacy["inprocess_validate_plan"]["contract_returned"])
        self.assertEqual(legacy["normalize_contract"]["contract"]["setup"][0]["id"], "S01\n")
        self.assertEqual((strict["accepted"], strict["code"]), (True, None), "新严格入口只判断 JSON 层，不判断合同字段")
        # 新协议的标识规则整串匹配（fullmatch）：同样的末尾换行写法在公共记录的标识上被拒绝（见
        # negative-protocol-run-context-request-id-trailing-newline 等）。
        for validator, value in ((P.validate_task_id, "normalize-query"), (P.validate_logical_id, "s01")):
            with self.subTest(validator=validator.__name__):
                validator(value)
                with self.assertRaises(P.ProtocolError) as caught:
                    validator(value + "\n")
                self.assertEqual(caught.exception.code, "E_ID_SYNTAX")


# ---------------------------------------------------------------------------
# 收尾轮：递归删除前的归属核对（文档 8.4，acceptance.md R-12）
# ---------------------------------------------------------------------------

class CleanupOwnershipTests(unittest.TestCase):
    """codekit01_legacy._rmtree 递归删除前核对归属：目标不是链接、真实路径的父目录就是系统临时目录（逐段比较）、目录名
    前缀属于本工具、目录由本进程登记、所有权标记与登记的随机令牌相同；任一不满足即报 CleanupRefused，不删除任何东西。
    对照用例都在本测试自建的临时目录中进行；对仓库内的路径只调用只读的 ownership_problem，不调用删除。"""

    PREFIX = "codekit01-fixtures-cleanup-"

    def _owned(self) -> Path:
        path = L._make_owned_tempdir(self.PREFIX)
        self.addCleanup(self._remove_owned, path)
        return path

    @staticmethod
    def _remove_owned(path: Path) -> None:
        if path.exists():
            L._rmtree(path)

    def _assert_refused(self, path: Any, fragment: str) -> None:
        problem = L.ownership_problem(path)
        self.assertIsNotNone(problem)
        self.assertIn(fragment, problem)
        with self.assertRaises(L.CleanupRefused):
            L._rmtree(path)
        self.assertTrue(os.path.lexists(path), "归属核对不通过时不得删除任何东西")

    def test_owned_directory_is_removed(self) -> None:
        path = L._make_owned_tempdir(self.PREFIX)
        (path / "sub").mkdir()
        (path / "sub" / "f.txt").write_bytes(b"x")
        self.assertIsNone(L.ownership_problem(path))
        L._rmtree(path)
        self.assertFalse(os.path.lexists(path))
        self.assertEqual(L.ownership_problem(path), "目标不是目录")  # 目录已不存在（这一条不检验登记是否注销）

    def test_removal_unregisters_directory(self) -> None:
        """收尾轮返工（复审 tests-mutation 视角）：删除后注销登记。此前的断言由“目标不是目录”满足，没有检验注销：
        在同一路径重建目录并写入同一个令牌后，仍因“不是本进程建立并登记”被拒绝，且不删除。"""
        path = L._make_owned_tempdir(self.PREFIX)
        real = os.path.realpath(os.fspath(path))
        marker = path / L.OWNER_MARKER_NAME
        token = marker.read_bytes()
        self.assertIn(L._owned_key(real), L._OWNED_TEMP_DIRS)
        L._rmtree(path)
        self.assertNotIn(L._owned_key(real), L._OWNED_TEMP_DIRS)
        os.mkdir(path)  # 同一路径（本测试刚删除的 mkdtemp 目录）重建，用后由下面两个清理删除
        self.addCleanup(os.rmdir, path)
        marker.write_bytes(token)
        self.addCleanup(os.unlink, marker)
        self._assert_refused(path, "不是本进程建立并登记")
        self.assertEqual(marker.read_bytes(), token)

    def test_marker_with_trailing_newline_refused(self) -> None:
        """收尾轮返工（复审 tests-mutation 视角）：标记必须与令牌逐字节相同，末尾多一个换行也不行（读取长度比令牌多，
        能看到多出的字节）。"""
        path = self._owned()
        marker = path / L.OWNER_MARKER_NAME
        original = marker.read_bytes()
        self.assertEqual(len(original), L._OWNER_TOKEN_BYTES * 2)
        for extra in (b"\n", b"\r\n", b" "):
            with self.subTest(extra=extra):
                marker.write_bytes(original + extra)
                self._assert_refused(path, "令牌不符")
        marker.write_bytes(original)
        self.assertIsNone(L.ownership_problem(path))

    def test_marker_link_to_valid_token_refused(self) -> None:
        """收尾轮返工（复审 tests-mutation 视角）：标记必须是普通文件，不能是链接，即使链接指向的文件内容恰好是正确的
        令牌（去掉链接检查时，按内容比较会通过）。无法创建文件符号链接时跳过并记为未实测。"""
        path = self._owned()
        holder = self._owned()
        marker = path / L.OWNER_MARKER_NAME
        original = marker.read_bytes()
        copy_path = holder / "token-copy"
        copy_path.write_bytes(original)
        marker.unlink()
        try:
            os.symlink(copy_path, marker)
        except OSError as exc:
            marker.write_bytes(original)
            self.skipTest("无法创建文件符号链接（%s），未实测" % type(exc).__name__)
        try:
            self.assertEqual(marker.read_bytes(), original, "链接读出的内容就是正确的令牌")
            self._assert_refused(path, "标记缺失，或不是普通文件")
        finally:
            os.unlink(marker)
            marker.write_bytes(original)
        self.assertIsNone(L.ownership_problem(path))

    def test_unregistered_directory_refused_even_with_forged_marker(self) -> None:
        raw = tempfile.mkdtemp(prefix=self.PREFIX)
        self.addCleanup(os.rmdir, raw)
        self._assert_refused(raw, "不是本进程建立并登记")
        marker = os.path.join(raw, L.OWNER_MARKER_NAME)
        with open(marker, "x", encoding="ascii") as handle:
            handle.write("0" * 64)
        self.addCleanup(os.unlink, marker)
        self._assert_refused(raw, "不是本进程建立并登记")

    def test_tampered_or_missing_marker_refused(self) -> None:
        path = self._owned()
        marker = path / L.OWNER_MARKER_NAME
        original = marker.read_bytes()
        marker.write_bytes(b"0" * len(original))
        self._assert_refused(path, "令牌不符")
        marker.unlink()
        self._assert_refused(path, "标记缺失")
        marker.write_bytes(original)
        self.assertIsNone(L.ownership_problem(path))

    def test_nested_directory_and_foreign_prefix_refused(self) -> None:
        path = self._owned()
        nested = path / (self.PREFIX + "nested")
        nested.mkdir()
        self._assert_refused(nested, "父目录不是系统临时目录")
        foreign = tempfile.mkdtemp(prefix="codekit01-unrelated-")
        self.addCleanup(os.rmdir, foreign)
        self._assert_refused(foreign, "前缀不属于本工具")

    def test_link_to_owned_directory_refused(self) -> None:
        target = self._owned()
        holder = self._owned()
        link = holder / (self.PREFIX + "link")
        try:
            if os.name == "nt":
                import _winapi
                _winapi.CreateJunction(str(target), str(link))
            else:
                os.symlink(target, link, target_is_directory=True)
        except OSError as exc:
            self.skipTest("无法创建目录链接（%s），未实测" % type(exc).__name__)
        self.addCleanup(os.rmdir if os.name == "nt" else os.unlink, link)  # 先于 holder 的清理执行
        self._assert_refused(link, "链接")
        self.assertIsNone(L.ownership_problem(target), "链接目标本身不受影响")

    def test_repository_paths_refused_by_read_only_check(self) -> None:
        for path in (REPO_ROOT, REPO_ROOT / "tests", repo_path(FIXTURE_DIR)):
            with self.subTest(path=path.name):
                self.assertIsNotNone(L.ownership_problem(path))

    def test_unregistered_prefix_cannot_be_created(self) -> None:
        with self.assertRaises(ValueError):
            L._make_owned_tempdir("codekit01-unregistered-")


def _make_dir_link(test: unittest.TestCase, target: Path, link: Path) -> None:
    """建立目录链接（Windows 用目录联接，其他平台用符号链接）；建不了时跳过并记为未实测。"""
    try:
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
        else:
            os.symlink(target, link, target_is_directory=True)
    except OSError as exc:
        test.skipTest("无法创建目录链接（%s），未实测" % type(exc).__name__)


def _remove_dir_link(link: Path) -> None:
    """只删除链接本身，不进入目标（Windows 上 os.rmdir 删除联接，其他平台 os.unlink 删除符号链接）。"""
    if os.name == "nt":
        os.rmdir(link)
    else:
        os.unlink(link)


class HarnessCleanupOwnershipTests(unittest.TestCase):
    """tests/legacy_harness.py 的 make_temp_area / remove_tree 删除前的归属核对（文档 8.4，acceptance.md R-12）。

    收尾轮返工（复审 tests-mutation 视角 major）：这部分核对此前在仓库中没有回归测试（实施者自述的自检写在已删除的临时
    脚本里）。这里把自检项落成断言：每项都断言 remove_tree 抛出 CleanupOwnershipError（不是静默返回，也不是被当作
    OSError 重试后的其他异常），并断言目标仍在。

    安全约定：只向 remove_tree 传本测试自建的路径。harness 的区域由 H.make_temp_area() 建立；“区域外”的目录与各种
    替身目录由 L._make_owned_tempdir 建立（属于 codekit01_legacy 的登记，不是 harness 的区域），用后由 L._rmtree 核对
    归属后删除；本测试在系统临时目录中按原名重建的目录由本测试逐个文件删除。不向 remove_tree 传仓库内的路径。"""

    OUTER_PREFIX = "codekit01-fixtures-cleanup-"

    def _area(self) -> Path:
        area = H.make_temp_area()
        self.addCleanup(self._remove_area, area)
        return area

    @staticmethod
    def _remove_area(area: Path) -> None:
        if os.path.lexists(area):
            H.remove_tree(area)

    def _outer(self) -> Path:
        path = L._make_owned_tempdir(self.OUTER_PREFIX)
        self.addCleanup(CleanupOwnershipTests._remove_owned, path)
        return path

    def _assert_refused(self, path: Any, fragment: str, *kept: Any) -> None:
        with self.assertRaises(H.CleanupOwnershipError) as caught:
            H.remove_tree(path)
        self.assertIn("拒绝删除归属不明的路径", str(caught.exception))
        self.assertIn(fragment, str(caught.exception))
        for item in (path,) + kept:
            self.assertTrue(os.path.lexists(item), "归属核对不通过时不得删除任何东西：%s" % item)

    def _set_tempdir(self, value: Optional[str]) -> None:
        """临时改写 tempfile.tempdir（gettempdir() 的返回值）；本测试结束前一定恢复。"""
        original = tempfile.tempdir
        tempfile.tempdir = value
        self.addCleanup(setattr, tempfile, "tempdir", original)

    def test_area_is_created_owned_and_removed(self) -> None:
        """正向对照：区域是 realpath(gettempdir()) 的直接子目录、名称带前缀、根目录有标记；区域内的子路径与区域本身都能
        删除（含只读文件）；删除后再删一次不报错。"""
        area = self._area()
        self.assertEqual(Path(os.path.realpath(tempfile.gettempdir())), area.parent)
        self.assertTrue(area.name.startswith(H.TEMP_AREA_PREFIX))
        self.assertEqual(len((area / H.OWNER_MARKER_NAME).read_bytes()), 64)
        (area / "sub" / "deep").mkdir(parents=True)
        (area / "sub" / "deep" / "f.txt").write_bytes(b"x")
        readonly = area / "readonly.txt"
        readonly.write_bytes(b"r")
        os.chmod(readonly, 0o400)
        H.remove_tree(area / "sub")
        self.assertFalse(os.path.lexists(area / "sub"))
        self.assertTrue(os.path.lexists(area / H.OWNER_MARKER_NAME))
        H.remove_tree(area)
        self.assertFalse(os.path.lexists(area))
        H.remove_tree(area)  # 已删除且不存在：直接返回

    def test_unregistered_directory_refused_even_with_forged_marker(self) -> None:
        """未登记的 codekit-legacy-* 目录：没有标记、标记是伪造值、甚至标记内容恰是某个已登记区域的真实令牌，都拒绝；
        其中的文件与不存在的路径同样拒绝。"""
        live = self._area()
        raw = Path(tempfile.mkdtemp(prefix=H.TEMP_AREA_PREFIX))
        self.addCleanup(os.rmdir, raw)
        reason = "不在本进程用 make_temp_area() 建立的临时区域内"
        self._assert_refused(raw, reason)
        marker = raw / H.OWNER_MARKER_NAME
        marker.write_bytes(b"0" * 64)
        self.addCleanup(os.unlink, marker)
        self._assert_refused(raw, reason, marker)
        marker.write_bytes((live / H.OWNER_MARKER_NAME).read_bytes())
        self._assert_refused(raw, reason, marker)
        self._assert_refused(marker, reason, raw)
        with self.assertRaises(H.CleanupOwnershipError):
            H.remove_tree(raw / "missing")
        self.assertTrue(os.path.lexists(live / H.OWNER_MARKER_NAME), "已登记的区域不受影响")

    def test_paths_outside_any_area_refused(self) -> None:
        """区域外的路径（其他工具登记的临时目录、其中的文件、不存在的路径）一律拒绝，不存在也不直接返回。"""
        outer = self._outer()
        keep = outer / "keep.txt"
        keep.write_bytes(b"k")
        reason = "不在本进程用 make_temp_area() 建立的临时区域内"
        self._assert_refused(outer, reason, keep)
        self._assert_refused(keep, reason, outer)
        with self.assertRaises(H.CleanupOwnershipError):
            H.remove_tree(outer / "missing")
        with self.assertRaises(H.CleanupOwnershipError):
            H.remove_tree(Path(tempfile.gettempdir()) / (H.TEMP_AREA_PREFIX + "never-created-by-this-test"))

    def test_marker_tampered_extended_missing_directory_or_link_refused(self) -> None:
        """所有权标记：内容被改（同长度）、末尾多出字节（换行、空格）、缺失、是目录、是指向正确令牌副本的链接，都拒绝
        删除区域本身与区域内的路径；恢复原标记后照常删除。"""
        area = self._area()
        data = area / "data"  # remove_tree 只用于目录（现有调用都传目录），区域内的对照路径也用目录
        data.mkdir()
        (data / "f.txt").write_bytes(b"d")
        marker = area / H.OWNER_MARKER_NAME
        original = marker.read_bytes()
        content = "所有权标记内容与本进程创建时记录的随机值不一致"
        for label, value in (("同长度改写", b"0" * len(original)), ("末尾换行", original + b"\n"),
                             ("末尾 CRLF", original + b"\r\n"), ("末尾空格", original + b" "),
                             ("截短", original[:-1])):
            with self.subTest(marker=label):
                marker.write_bytes(value)
                self._assert_refused(area, content, data)
                self._assert_refused(data, content, area)
        marker.unlink()
        with self.subTest(marker="缺失"):
            self._assert_refused(area, "缺少所有权标记文件", data)
            self._assert_refused(data, "缺少所有权标记文件", area)
        marker.mkdir()
        with self.subTest(marker="目录"):
            self._assert_refused(area, "所有权标记不是普通文件", data, marker)
            self._assert_refused(data, "所有权标记不是普通文件", area)
        marker.rmdir()
        outer = self._outer()
        token_copy = outer / "token-copy"
        token_copy.write_bytes(original)
        linked = True
        try:
            os.symlink(token_copy, marker)
        except OSError:
            linked = False  # 无法创建文件符号链接：这一项未实测，其余项照常断言
        if linked:
            with self.subTest(marker="指向正确令牌副本的链接"):
                try:
                    self.assertEqual(marker.read_bytes(), original)
                    self._assert_refused(area, "所有权标记不是普通文件", data, token_copy)
                finally:
                    os.unlink(marker)
        marker.write_bytes(original)
        H.remove_tree(data)
        self.assertFalse(os.path.lexists(data))

    def test_area_not_direct_child_of_tempdir_refused(self) -> None:
        """区域不是系统临时目录的直接子目录（这里：在另一个临时目录下建立后，gettempdir 恢复原值）时拒绝，区域本身与
        区域内的路径都拒绝。"""
        outer = self._outer()
        original = tempfile.tempdir
        tempfile.tempdir = os.fspath(outer)
        try:
            inner = H.make_temp_area()
        finally:
            tempfile.tempdir = original
        self.assertEqual(inner.parent, Path(os.path.realpath(outer)))

        def remove_inner() -> None:  # 先于 outer 的清理执行：按建立时的系统临时目录删除
            saved = tempfile.tempdir
            tempfile.tempdir = os.fspath(outer)
            try:
                H.remove_tree(inner)
            finally:
                tempfile.tempdir = saved
        self.addCleanup(remove_inner)
        (inner / "f.txt").write_bytes(b"f")
        reason = "不是系统临时目录的直接子目录"
        self._assert_refused(inner, reason, inner / "f.txt", inner / H.OWNER_MARKER_NAME)
        self._assert_refused(inner / "f.txt", reason, inner)

    def test_gettempdir_changed_refused(self) -> None:
        """建立区域之后 tempfile.gettempdir() 改变（区域的父目录不再是它）：拒绝；恢复后照常删除。"""
        area = self._area()
        (area / "f.txt").write_bytes(b"f")
        other = self._outer()
        self._set_tempdir(os.fspath(other))
        self._assert_refused(area, "不是系统临时目录的直接子目录", area / "f.txt")
        self._assert_refused(area / "f.txt", "不是系统临时目录的直接子目录", area)

    def test_prefix_no_longer_owned_refused(self) -> None:
        """目录名前缀必须属于本工具：登记后本工具的前缀改变（模拟“目录名不以本工具前缀开头”），拒绝。"""
        area = self._area()
        original = H.TEMP_AREA_PREFIX
        H.TEMP_AREA_PREFIX = "codekit-legacy-other-owner-"
        try:
            self._assert_refused(area, "目录名不以 codekit-legacy-other-owner- 开头", area / H.OWNER_MARKER_NAME)
        finally:
            H.TEMP_AREA_PREFIX = original

    def test_replaced_directory_with_copied_marker_refused(self) -> None:
        """区域根目录被替换为同名新目录、并复制了原标记（内容就是正确令牌）：目录身份（st_dev, st_ino）不同，拒绝。"""
        area = self._area()
        marker = area / H.OWNER_MARKER_NAME
        token = marker.read_bytes()
        outer = self._outer()
        moved = outer / "moved-area"
        os.rename(area, moved)
        restored = False

        def restore() -> None:
            if not restored:
                for name in os.listdir(area):
                    os.unlink(area / name)
                os.rmdir(area)
                os.rename(moved, area)
        self.addCleanup(restore)
        os.mkdir(area)
        marker.write_bytes(token)
        (area / "f.txt").write_bytes(b"f")
        self._assert_refused(area, "目录身份与创建时不同", marker, area / "f.txt", moved)
        self._assert_refused(area / "f.txt", "目录身份与创建时不同", area)
        restore()
        restored = True
        self.assertTrue(os.path.lexists(area / H.OWNER_MARKER_NAME))

    def test_link_target_or_link_root_refused(self) -> None:
        """待删路径本身是链接或联接（即使目标在同一区域内）时拒绝，目标不受影响。区域根目录被换成指向原目录的联接时
        同样拒绝：解析后的真实路径落在登记区域之外，在根目录的真实路径、链接与身份检查之前就被拒绝（所以单独放宽根目录的
        链接检查不改变结果，那一道检查是纵深防御）。"""
        area = self._area()
        target = area / "target"
        target.mkdir()
        (target / "keep.txt").write_bytes(b"k")
        link = area / "link"
        _make_dir_link(self, target, link)
        self._assert_refused(link, "要删除的路径本身是链接或联接", target / "keep.txt")
        _remove_dir_link(link)
        # 区域根目录换成联接。
        other = self._area()
        outer = self._outer()
        moved = outer / "moved-root"
        os.rename(other, moved)
        _make_dir_link(self, moved, other)

        def restore() -> None:
            _remove_dir_link(other)
            os.rename(moved, other)
        self.addCleanup(restore)
        for path in (other, other / H.OWNER_MARKER_NAME):
            with self.subTest(path=path.name):
                with self.assertRaises(H.CleanupOwnershipError):
                    H.remove_tree(path)
                self.assertTrue(os.path.lexists(moved / H.OWNER_MARKER_NAME))
                self.assertTrue(os.path.lexists(other))

    def test_new_path_in_removed_area_refused(self) -> None:
        """区域删除后，同一路径下新出现的目录与文件无法核对归属：拒绝，且不删除。"""
        area = H.make_temp_area()
        H.remove_tree(area)
        self.assertFalse(os.path.lexists(area))
        os.mkdir(area)  # 按原名重建（本测试刚删除的 mkdtemp 目录），用后由下面两个清理删除
        self.addCleanup(os.rmdir, area)
        late = area / "late.txt"
        late.write_bytes(b"late")
        self.addCleanup(os.unlink, late)
        reason = "所在的临时区域已被删除"
        self._assert_refused(area, reason, late)
        self._assert_refused(late, reason, area)

    def test_removing_area_does_not_follow_links_to_outside(self) -> None:
        """正向对照：区域内有指向区域外目录的联接（以及可能时指向区域外文件的符号链接）时，删除区域只删链接本身，
        区域外的目录与文件不受影响。"""
        area = self._area()
        outer = self._outer()
        external_dir = outer / "external-dir"
        external_dir.mkdir()
        (external_dir / "f.txt").write_bytes(b"external")
        external_file = outer / "external.txt"
        external_file.write_bytes(b"external")
        (area / "nested").mkdir()
        _make_dir_link(self, external_dir, area / "to-outside")
        _make_dir_link(self, external_dir, area / "nested" / "to-outside")
        try:
            os.symlink(external_file, area / "file-link")
        except OSError:
            pass  # 无法创建文件符号链接：只核对目录链接
        H.remove_tree(area)
        self.assertFalse(os.path.lexists(area))
        self.assertEqual((external_dir / "f.txt").read_bytes(), b"external")
        self.assertEqual(external_file.read_bytes(), b"external")


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        print(write_all())
        sys.exit(0)
    unittest.main(verbosity=2)  # 方法级取证：每个测试方法各占一行（acceptance.md 第 7 节第 6 项）
