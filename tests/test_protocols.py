#!/usr/bin/env python3
"""01-T2 公共协议独立测试（黑盒）。

依据：
- 设计文档 docs/code-kit-v2/01-baseline-and-protocols-审阅增强版.md（修订 review-expanded-2026-09-25；
  仓库中文件名因编码显示为乱码，按前缀 01-baseline-and-protocols- 查找）；
- docs/code-kit-v2/01-baseline/decisions.md（01-D01–D10、01-L01–L04）；
- 01-T2 接口规格（函数名、常量与错误码固定，供 02/03/04 使用）。

本文件最初只按规格与文档黑盒编写，不参考 scripts/codekit/protocols.py、sealing.py 的实现细节。
每个测试方法的 docstring 写明对应的文档章节或用例号。

P2 调和（实现与测试对照后）：规格未固定、原测试只断言“被拒绝”或接受多个错误码的地方，
已按 docs/code-kit-v2/01-baseline/protocols-api.md“规格澄清”一节的裁决改为断言唯一错误码与
结构；被修改或新增的测试在 docstring/注释中写明“P2 调和”和对应的澄清编号 C-xx。
白盒用例只有两个：test_A13_seal_readback_mismatch_publishes_nothing（替换 sealing 内部读回函数
注入摘要不符）与 P2 返工新增的 test_A13_seal_temp_file_is_exclusive_and_fsynced（替换 sealing 模块内
的 secrets 与 os 引用），原因见各自的 docstring。
P2 返工（多视角复审后）：新增与修改的测试在 docstring/注释中写明“P2 返工”和复审视角或变异编号；
裁决见 protocols-api.md 第 19 节“P2 返工”（R-xx）。P2 第二轮返工又新增两个白盒用例：
test_A13_read_sealed_reads_once_returns_verified_bytes（替换 sealing 内部读取函数，断言只读一次）与
test_A10_is_within_compares_components_exactly（直接检查共用的越界判定 _is_within），原因见各自的 docstring。
P4（规划端裁决 R-P1–R-P8 落实、第 2 轮复审 minor 与 fixtures 复审处理，见 protocols-api.md 第 19 节“P4”）：
新增与修改的测试在 docstring 中写明“P4”与裁决编号或复审视角、变异编号。白盒用例新增两处：
test_A13_seal_failure_leaves_only_empty_new_parents（替换 sealing 内部的 _read_all 与模块内的 os 引用）与
test_A10_filesystem_aliases_rejected 中对 _check_listed_name 的直接调用（自动生成的 8.3 短名在词法层已被拒绝）。
修订成环用例在子进程中运行（test_A06_revision_cycle_detected_within_timeout），外部命令因此多了一次当前解释器。
P4 第 3 轮（第 3 轮复审返工，见 protocols-api.md 第 19 节“P4 第 3 轮”）：新增与修改的测试在 docstring 中写明
“P4 第 3 轮”与复审视角或变异编号。物理层对别名的黑盒兜底改用手工设置、不含 "~" 的短名（fsutil file
setshortname，只对本用例 tempfile 目录中的对象；不可用时 skip）；白盒用例新增
test_A13_seal_post_publish_escape_is_reported（替换 sealing 模块内的 os 引用，让“发布”落成指向根外的链接）。
P4 第 4 轮（第 4 轮复审返工，见 protocols-api.md 第 19 节“P4 第 4 轮”）：新增的测试在 docstring 中写明“P4 第 4 轮”
与复审视角。名称末尾带点或空格的链接经 \\\\?\\ 逐字路径创建，并按逐字路径删除（先于临时目录的清理）。白盒用例新增
test_A10_split_link_target_forms（直接调用 _split_link_target 与 _os_path，只拆分文本）、
test_A10_link_walk_unsupported_form_and_divergence 与 test_A13_link_walk_divergence_rejected_by_seal_and_read
（替换 protocols._link_target_text），以及 test_A10_link_walk_physical_dotdot_branch（替换 protocols._split_link_target，
在 Windows 上走 POSIX 的物理 ".." 分支），原因见各自的 docstring。
P4 第 5 轮（裁决 R-P9 落实与第 5 轮复审返工，见 protocols-api.md 第 19 节“P4 第 5 轮”）：新增与修改的测试在 docstring
中写明“P4 第 5 轮”与复审视角。物理检查按 R-P9 定位为“静态审阅 + 纵深防御”，相关 docstring 只写“已检测的情形”与
“已知不检测”，不写绝对表述（test_A10_physical_check_wording_follows_r_p9）。黑盒用例
test_A10_windows_link_target_forms_measured 用 ctypes 调用 FSCTL_SET_REPARSE_POINT，只对本用例 tempfile 目录中新建的
空文件或空目录写入重解析数据（os.symlink 造不出这些写法），用后先于临时目录的清理删除；无法设置时 skip。白盒用例新增
test_A10_unrecognized_name_surrogate_reparse_point_fails_closed 与 test_A13_unrecognized_name_surrogate_rejected_by_seal_and_read
（替换 protocols 模块内的 os，模拟有过滤驱动处理名称代理类重解析点的机器），以及 test_A10_link_walk_failure_reasons_fail_closed
（替换 protocols._link_target_text）。test_A13_hard_link_alias_is_known_not_detected 固定“已知不检测”清单中的硬链接一项，
不是安全性测试，01-F030 仍为 skip。
收尾轮（裁决 R-P10、R-P11 与 acceptance.md M-01，见 protocols-api.md 第 19 节“收尾轮”）：新增测试的方法名带 r_p10、r_p11
或 m01。登记资源类型必须声明 schema_ref、payload_representations、payload_validator，测试用辅助函数 make_kind 登记；
fixture 条目的五个新字段由 make_manifest_entry 与 ProvenanceTests.captured 补上默认值。没有新增白盒用例。
收尾轮返工（复审 fidelity 与 tests-mutation 视角，见 protocols-api.md 第 19 节“收尾轮返工”）：R-P11 第 5 步的两条规则
改按受控词表判定，删去把 complete_run、run_stream_complete、fullrun、field_semantics、protocol_fields 当作“无关名称”
的断言，改为断言拒绝；新增 test_A12_r_p11_check_order_structure_then_steps，并在 M-01、R-P10 的已有测试中补上检查
顺序与 json+markdown 回退的用例。没有新增白盒用例。

运行方式：python tests/test_protocols.py
不要用 unittest discover（tests/test_dispatch.py 导入时就建临时目录，见 01-L04）。

范围：
- 附录 C.3 的 01-F001–F049 中可在单元层验证的项，以及 01-A03–A06、A08–A14 的最小正反例；
- 01-F029、01-F030 属于生产安全访问，01 不实现（01-D06），写成 skip，不伪装成通过；
- 01-F050（基线漂移）归 01-T1 取证工具（tests/test_baseline_tool.py），本文件不覆盖；
- 只在 tempfile 创建的目录中写文件，结束时清理；不联网；外部命令只有 git（F035 临时仓库）、
  当前解释器（A14 子进程导入检查、A06 修订成环的带超时子进程），以及 Windows 上的 fsutil（只对本用例
  tempfile 目录启用大小写敏感，A10 大小写敏感目录变体；只对本用例 tempfile 目录中的对象手工设置短名，
  A10/A13 别名黑盒用例；不可用时 skip）。
"""
from __future__ import annotations

import ast
import copy
import datetime as _dt
import decimal
import enum
import hashlib
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from collections import OrderedDict
from pathlib import Path

sys.dont_write_bytecode = True

# 中文的 skip 原因与 docstring 在 Git Bash（控制台代码页不是 UTF-8）中按 UTF-8 输出才可读（参照
# tests/test_dispatch.py 的做法）；无法编码的字符写成反斜杠转义，不因输出编码中断测试。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
SCHEMA_PATH = REPO_ROOT / "schemas" / "codekit-public-v1.schema.json"
DOC_DIR = REPO_ROOT / "docs" / "code-kit-v2"
PI_DISPATCH_PATH = SCRIPTS_DIR / "pi_dispatch.py"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from codekit import protocols as P  # noqa: E402

try:  # sealing 缺失时只让 SealingTests 报错，不影响其他测试
    from codekit import sealing as S  # noqa: E402
    _SEALING_IMPORT_ERROR = None
except Exception as _exc:  # pragma: no cover - 取决于实现是否就位
    S = None
    _SEALING_IMPORT_ERROR = _exc

IS_WINDOWS = os.name == "nt"
_UNSET = object()

SCHEMA_SHA256 = "7895442dc9907b6ab1a0c1dd946a1b0caaf2cdd49caaa1ebabff94fa10cdf291"
SYNTHETIC_SAMPLE_BYTES = b'{"fixture":"synthetic","ok":true}\n'
SYNTHETIC_SAMPLE_SHA256 = "0036dde35a13e287320b6399674c46649365553a0ab6d3edf2a2111d6f83c4e1"

REQ = "req-11111111111141118111111111111111"
RUN = "run-22222222222242228222222222222222"
OTHER_REQ = "req-" + "3" * 32
OTHER_RUN = "run-" + "4" * 32
FULL_SHA1_OID = "a4fa199b0e5bdc658215765ee7558b9fe6723940"

# ---------------------------------------------------------------------------
# 文档样例：逐字取自设计文档代码块（4.1.3、4.2.2、4.3.1、4.3.6、4.3.9）。
# test_A09_doc_samples_are_verbatim 核对它们仍与文档字节一致。
# ---------------------------------------------------------------------------
SAMPLE_RUN_CONTEXT = """{
  "schema_version": 1,
  "record_type": "run-context",
  "request_id": "req-11111111111141118111111111111111",
  "task_id": "baseline-review",
  "plan_version": null,
  "run_id": "run-22222222222242228222222222222222",
  "attempt": null,
  "role": "planner",
  "platform": "linux",
  "contract_ref": null
}
"""

SAMPLE_RESOURCE_REF = """{
  "kind": "fixture",
  "id": "synthetic-protocol-sample-1",
  "sha256": "0036dde35a13e287320b6399674c46649365553a0ab6d3edf2a2111d6f83c4e1",
  "path": "tests/fixtures/synthetic-protocol-sample-1.json"
}
"""

SAMPLE_RUN_EVENT = """{
  "schema_version": 1,
  "record_type": "run-event",
  "request_id": "req-11111111111141118111111111111111",
  "run_id": "run-22222222222242228222222222222222",
  "seq": 1,
  "observed_at": "2026-09-25T00:00:00.000000Z",
  "role": "planner",
  "type": "run.prepared",
  "source_kind": "core",
  "payload": {"example_only": true},
  "raw_refs": [],
  "integrity": "complete",
  "adapter_revision": null
}
"""

SAMPLE_ERROR = """{
  "code": "E_JSON_DUPLICATE_KEY",
  "message": "输入对象包含重复字段，不能形成审核输入。",
  "details": {
    "field": "/profiles/default/model",
    "source_ref": null,
    "phase": "decode",
    "reason": "duplicate_object_member",
    "hint": "修正重复字段后重新提交；不要保留最后一个值后继续审核。"
  },
  "retryable": false
}
"""

SAMPLE_USAGE = """{
  "schema_version": 1,
  "record_type": "usage-observation",
  "usage_id": "usage-synthetic-unknown-1",
  "request_id": "req-11111111111141118111111111111111",
  "run_id": "run-22222222222242228222222222222222",
  "role": "planner",
  "provider": null,
  "model": null,
  "observation_kind": "unknown",
  "input_tokens": null,
  "cache_read_tokens": null,
  "cache_write_tokens": null,
  "output_tokens": null,
  "reasoning_tokens": null,
  "input_includes_cache": null,
  "output_includes_reasoning": null,
  "reported_cost": null,
  "estimated_cost": null,
  "billing_source": "unavailable",
  "billing_event_id": null,
  "supersedes_usage_id": null,
  "unknown_reasons": {
    "provider": "synthetic_example_without_vendor_evidence",
    "model": "synthetic_example_without_vendor_evidence",
    "observation_kind": "not_reported",
    "input_tokens": "not_reported",
    "cache_read_tokens": "not_reported",
    "cache_write_tokens": "not_reported",
    "output_tokens": "not_reported",
    "reasoning_tokens": "not_reported",
    "input_includes_cache": "vendor_semantics_unavailable",
    "output_includes_reasoning": "vendor_semantics_unavailable",
    "reported_cost": "not_reported",
    "estimated_cost": "no_pricing_basis"
  },
  "evidence_refs": []
}
"""

DOC_SAMPLES = {
    "4.1.3 RunContext": SAMPLE_RUN_CONTEXT,
    "4.2.2 ResourceRef": SAMPLE_RESOURCE_REF,
    "4.3.1 run-event": SAMPLE_RUN_EVENT,
    "4.3.6 error": SAMPLE_ERROR,
    "4.3.9 usage": SAMPLE_USAGE,
}

# 附录 C.2：固定快照黄金向量（输入对象、期望字节、期望 SHA-256）。
GOLDEN_VECTORS = [
    ({"b": 2, "a": 1}, b'{"a":1,"b":2}\n',
     "e8d38819d39f705646bfb643368eca78f7db476c16471dbc33b941b27326410d"),
    ({"text": "\u00e9"}, b'{"text":"\xc3\xa9"}\n',
     "4dbc4b223d0da4858700d9a483553a9f2d5c31d2c2fcb7e45e41c56e3bd1f20c"),
    ({"text": "e\u0301"}, b'{"text":"e\xcc\x81"}\n',
     "4ae0b8cab5f8efd099785478bbd470b23d1c0eb7424b785416f3ee5496245948"),
    ({"n": 1}, b'{"n":1}\n',
     "cedf74272c9fc8db5448283a93277e7e7eb7534b71df3bd8ab35fd9b1b73404c"),
    ({"n": 1.0}, b'{"n":1.0}\n',
     "4352df4233f0d6492477e70dab0a2b2aa9683d2297d61c8e8d98b515a4bc2f8d"),
]

UNKNOWABLE = (
    "provider", "model", "observation_kind", "input_tokens", "cache_read_tokens",
    "cache_write_tokens", "output_tokens", "reasoning_tokens", "input_includes_cache",
    "output_includes_reasoning", "reported_cost", "estimated_cost",
)
TOKEN_METRICS = ("input_tokens", "cache_read_tokens", "cache_write_tokens",
                 "output_tokens", "reasoning_tokens")
AMOUNT_RE = re.compile(r"(0|[1-9][0-9]*)(\.[0-9]+)?")


# ---------------------------------------------------------------------------
# 通用构造器（只用标准库 json 解析文档样例，避免构造器依赖被测实现）
# ---------------------------------------------------------------------------
def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def expected_snapshot(value) -> bytes:
    """4.2.6 固定表达式，原文保留。"""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def make_context(**overrides):
    ctx = json.loads(SAMPLE_RUN_CONTEXT)
    ctx.update(overrides)
    return ctx


CONTRACT_BYTES = b"# contract sample\n"
CONTRACT_REF = {
    "kind": "fixture",
    "id": "contract-sample-1",
    "sha256": sha(CONTRACT_BYTES),
    "path": "tests/fixtures/codekit01/synthetic/contract-sample-1.md",
}


def make_executor_context(**overrides):
    ctx = make_context(role="executor", task_id="baseline-review", plan_version=1,
                       attempt=1, contract_ref=copy.deepcopy(CONTRACT_REF), platform="windows")
    ctx.update(overrides)
    return ctx


SEGMENT_BYTES = b'{"type":"message","text":"hello"}\n'


def make_segment_ref(raw: bytes = SEGMENT_BYTES, rid: str = "segment-000001",
                     path: str = "runs/sample/raw/stdout-000001.seg"):
    return {"kind": "raw-segment", "id": rid, "sha256": sha(raw), "path": path}


def make_span(ref=None, start=0, end=None, stream="stdout"):
    ref = make_segment_ref() if ref is None else ref
    return {"ref": ref, "byte_start": start,
            "byte_end": len(SEGMENT_BYTES) if end is None else end, "stream": stream}


def make_event(seq=1, **overrides):
    ev = json.loads(SAMPLE_RUN_EVENT)
    ev["seq"] = seq
    ev.update(overrides)
    return ev


def make_vendor_event(seq=1, **overrides):
    ev = make_event(seq, type="vendor.message", source_kind="vendor",
                    adapter_revision="adapter-r1", raw_refs=[make_span()],
                    integrity="complete", payload={"text": "hello"})
    ev.update(overrides)
    return ev


def make_usage(usage_id="usage-1", **overrides):
    """合成用量观测；为 null 的可未知字段自动补原因（4.3.7、4.3.9），除非显式给出 unknown_reasons。"""
    obs = {
        "schema_version": 1, "record_type": "usage-observation", "usage_id": usage_id,
        "request_id": REQ, "run_id": RUN, "role": "planner",
        "provider": "synthetic-provider", "model": "synthetic-model-a",
        "observation_kind": "delta",
        "input_tokens": 100, "cache_read_tokens": 0, "cache_write_tokens": 0,
        "output_tokens": 10, "reasoning_tokens": 0,
        "input_includes_cache": False, "output_includes_reasoning": False,
        "reported_cost": {"amount": "0.10", "currency": "USD"},
        "estimated_cost": {"amount": "0.09", "currency": "USD"},
        "billing_source": "vendor_reported", "billing_event_id": None,
        "supersedes_usage_id": None, "unknown_reasons": {}, "evidence_refs": [],
    }
    explicit_reasons = "unknown_reasons" in overrides
    obs.update(overrides)
    if not explicit_reasons:
        reasons = {}
        for name in UNKNOWABLE:
            if name == "observation_kind":
                if obs[name] == "unknown":
                    reasons[name] = "not_reported"
            elif obs[name] is None:
                reasons[name] = "not_reported"
        obs["unknown_reasons"] = reasons
    return obs


def make_manifest_entry(**overrides):
    """01-T2 规格的 fixture-manifest 条目（封闭字段），合成来源正例。"""
    entry = {
        "schema_version": 1,
        "record_type": "fixture-manifest",
        "fixture_id": "synthetic-protocol-sample-1",
        "origin": {
            "class": "synthetic",
            "source_revision": None,
            "source_test_id": None,
            "source_path": None,
            "generator_revision": "review-expanded-2026-09-25",
            "derived_from": None,
            "fault": None,
            "description": "用于完整字节哈希和来源标签的合成示例，不是厂商输出。",
        },
        "representation": "synthetic_fixture",
        "redaction": {
            "applied": False,
            "rule_revision": None,
            "length_changed": None,
            "reason": "构造时不包含真实凭据或真实用户数据。",
        },
        "resource": {
            "kind": "fixture",
            "id": "synthetic-protocol-sample-1",
            "sha256": SYNTHETIC_SAMPLE_SHA256,
            "path": "tests/fixtures/codekit01/synthetic/synthetic-protocol-sample-1.json",
        },
        "proves": ["exact_byte_digest", "synthetic_provenance_label"],
        "does_not_prove": ["real_cli_compatibility", "legacy_dispatch_behavior"],
        "expected": {"outcome": "accept", "code": None, "entry": "strict_json_loads",
                     "expected_ref": None},
        # 收尾轮（裁决 R-P11）新增的条目字段。
        "integrity": "complete",
        "platform_scope": ["any"],
        "capture": None,
    }
    # 收尾轮（裁决 R-P11）：origin.traceable 与 redaction.protocol_structure_preserved。
    entry["origin"]["traceable"] = True
    entry["redaction"]["protocol_structure_preserved"] = None
    for key, value in overrides.items():
        if (key in ("origin", "redaction", "resource", "expected", "capture") and isinstance(value, dict)
                and isinstance(entry.get(key), dict)):
            entry[key] = {**entry[key], **value}
        else:
            entry[key] = value
    return entry


#: 收尾轮（裁决 R-P11）：captured 条目的采集环境引用（附录 C.1“采集环境”）；kind 取 01 已登记的 baseline-evidence。
CAPTURE_ENV_BYTES = b'{"environment":"synthetic capture host"}\n'
CAPTURE_ENV_REF = {"kind": "baseline-evidence", "id": "capture-env-1", "sha256": sha(CAPTURE_ENV_BYTES),
                   "path": "evidence/capture-env-1.json"}


def make_kind(name, is_file, owner_module, description, **declared):
    """收尾轮（裁决 R-P10）：登记类型时必须声明 schema_ref、payload_representations、payload_validator；
    测试中没有特别要求时取 None、("binary",)、None。"""
    declared.setdefault("schema_ref", None)
    declared.setdefault("payload_representations", ("binary",))
    declared.setdefault("payload_validator", None)
    return P.ResourceKind(name, is_file, owner_module, description, **declared)


def nested_list(depth: int):
    value: list = []
    for _ in range(depth - 1):
        value = [value]
    return value


def all_keys(obj):
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= all_keys(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            keys |= all_keys(v)
    return keys


def all_values_for(obj, key):
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                found.append(v)
            found.extend(all_values_for(v, key))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found.extend(all_values_for(v, key))
    return found


def verbatim(path) -> str:
    """Windows 逐字路径（\\\\?\\ 前缀）：创建、删除名称末尾带点或空格的对象时使用（Win32 规范化会去掉它们）。"""
    text = str(path)
    return text if text.startswith("\\\\?\\") else "\\\\?\\" + text


def windows_short_name(path: Path):
    """返回 path 末段的 Windows 8.3 短名；不是 Windows、卷未启用短名或短名与长名相同时返回 None。"""
    if not IS_WINDOWS:
        return None
    import ctypes
    buffer = ctypes.create_unicode_buffer(1024)
    length = ctypes.windll.kernel32.GetShortPathNameW(str(path), buffer, len(buffer))
    if not length or length >= len(buffer):
        return None
    name = Path(buffer.value).name
    return None if name == Path(path).name else name


def set_manual_short_name(path: Path, short: str):
    """用 fsutil file setshortname 给 path 手工设置不含 "~" 的 8.3 短名（只对本用例 tempfile 目录中的对象）。
    成功返回 None；不是 Windows、fsutil 不可用或失败（权限、卷未启用 8.3）时返回原因文字，供 skip 使用。"""
    if not IS_WINDOWS:
        return "手工短名是 Windows 卷的特性（非 Windows 平台不适用）"
    try:
        result = subprocess.run(["fsutil", "file", "setshortname", str(path), short],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return f"无法运行 fsutil（{type(exc).__name__}）"
    if result.returncode != 0:
        return f"fsutil 未能设置短名（退出码 {result.returncode}，可能缺少权限或卷未启用 8.3 短名）"
    if not (path.parent / short).exists():
        return "设置后短名不能解析到对象"
    return None


IO_REPARSE_TAG_SYMLINK = 0xA000000C
IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003
SYMLINK_FLAG_RELATIVE = 1


def symlink_reparse_buffer(substitute: str, *, relative: bool) -> bytes:
    """REPARSE_DATA_BUFFER（IO_REPARSE_TAG_SYMLINK）：SubstituteName 按原样写入，PrintName 与之相同。
    os.symlink 只能写出 CreateSymbolicLinkW 规范化后的文本；这里用来造出黑盒无法直接创建的写法。"""
    import struct
    name = substitute.encode("utf-16-le")
    body = struct.pack("<HHHHI", 0, len(name), len(name), len(name),
                       SYMLINK_FLAG_RELATIVE if relative else 0) + name + name
    return struct.pack("<IHH", IO_REPARSE_TAG_SYMLINK, len(body), 0) + body


def mount_point_reparse_buffer(substitute: str) -> bytes:
    """REPARSE_DATA_BUFFER（IO_REPARSE_TAG_MOUNT_POINT，即 junction/卷挂载点）：名称后带终止符，PrintName 为空。"""
    import struct
    name = substitute.encode("utf-16-le")
    body = struct.pack("<HHHH", 0, len(name), len(name) + 2, 0) + name + b"\0\0" + b"\0\0"
    return struct.pack("<IHH", IO_REPARSE_TAG_MOUNT_POINT, len(body), 0) + body


def guid_reparse_buffer(tag: int) -> bytes:
    """REPARSE_GUID_DATA_BUFFER：第三方（非 Microsoft）标签必须带 GUID；数据内容无意义（本机没有处理它的过滤驱动）。"""
    import struct
    data = b"codekit\0"
    return struct.pack("<IHH", tag, len(data), 0) + uuid.uuid4().bytes_le + data


def set_reparse_point(path, buffer: bytes):
    """对已存在的空文件或空目录 path 执行 FSCTL_SET_REPARSE_POINT（只对本用例 tempfile 目录中的对象）。
    成功返回 None；不是 Windows 或调用失败（例如缺少创建符号链接的权限）时返回原因文字，供 skip 使用。"""
    if not IS_WINDOWS:
        return "重解析点是 Windows 的特性（非 Windows 平台不适用）"
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD,
                                         wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                         wintypes.LPVOID]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    generic_write, open_existing = 0x40000000, 3
    open_reparse_point, backup_semantics = 0x00200000, 0x02000000
    handle = kernel32.CreateFileW(str(path), generic_write, 0, None, open_existing,
                                  open_reparse_point | backup_semantics, None)
    if handle == wintypes.HANDLE(-1).value:
        return f"无法打开对象设置重解析点（winerror {ctypes.get_last_error()}）"
    try:
        returned = wintypes.DWORD()
        if not kernel32.DeviceIoControl(handle, 0x000900A4, buffer, len(buffer), None, 0,
                                        ctypes.byref(returned), None):
            return f"FSCTL_SET_REPARSE_POINT 失败（winerror {ctypes.get_last_error()}，可能缺少权限）"
    finally:
        kernel32.CloseHandle(handle)
    return None


def fake_reparse_tags(fake: dict):
    """白盒注入：把 protocols 模块内的 os 换成代理，os.lstat 对 fake 中列出的名称（末段）返回给定的
    (st_mode, st_reparse_tag)，其余属性转给真实的 os。模拟“有过滤驱动处理该标签、OS 能解析”的机器（本机没有
    这样的驱动）。不修改全局 os 模块；返回恢复函数，调用方必须在 finally 中调用。"""
    from types import SimpleNamespace

    real_os = P.os

    class FakeReparseOs:
        def __getattr__(self, name):
            return getattr(real_os, name)

        @staticmethod
        def lstat(path, *args, **kwargs):
            entry = fake.get(os.path.basename(str(path)))
            if entry is None:
                return real_os.lstat(path, *args, **kwargs)
            mode, tag = entry
            return SimpleNamespace(st_mode=mode, st_reparse_tag=tag)

    P.os = FakeReparseOs()

    def restore():
        P.os = real_os
    return restore


def minimal_child_env(extra=None):
    """子进程最小环境：只传平台启动必需的变量名，不传凭据。"""
    env = {}
    for name in ("SYSTEMROOT", "WINDIR"):
        if name in os.environ:
            env[name] = os.environ[name]
    if extra:
        env.update(extra)
    return env


# ---------------------------------------------------------------------------
# 迷你 JSON Schema 校验器：只覆盖本 Schema 用到的关键字（A.1；format 只作注解）
# ---------------------------------------------------------------------------
def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _json_equal(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if _is_number(a) and _is_number(b):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_json_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_json_equal(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def _type_ok(value, name: str) -> bool:
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    if name == "number":
        return _is_number(value)
    if name == "integer":  # Draft 2020-12：小数部分为零的数也算 integer
        return (isinstance(value, int) and not isinstance(value, bool)) or (
            isinstance(value, float) and value.is_integer())
    raise ValueError(f"unsupported type keyword value: {name}")


class MiniSchemaValidator:
    SUPPORTED = frozenset({
        "type", "const", "enum", "pattern", "minLength", "maxLength", "minimum", "maximum",
        "required", "properties", "additionalProperties", "anyOf", "oneOf", "$ref",
        "items", "maxItems",
    })
    ANNOTATIONS = frozenset({"$schema", "$id", "title", "description", "format", "$defs"})

    def __init__(self, root):
        self.root = root

    def resolve(self, ref: str):
        if not ref.startswith("#/$defs/"):
            raise ValueError(f"non-local $ref: {ref}")
        node = self.root
        for token in ref[2:].split("/"):
            node = node[token.replace("~1", "/").replace("~0", "~")]
        return node

    def errors(self, instance, schema, path: str = ""):
        if schema is True:
            return []
        if schema is False:
            return [f"{path}: false schema"]
        unknown = set(schema) - self.SUPPORTED - self.ANNOTATIONS
        if unknown:
            raise ValueError(f"unsupported keywords {sorted(unknown)}")
        errs = []
        if "$ref" in schema:
            errs += self.errors(instance, self.resolve(schema["$ref"]), path)
        if "type" in schema:
            names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_type_ok(instance, n) for n in names):
                errs.append(f"{path}: type")
        if "const" in schema and not _json_equal(instance, schema["const"]):
            errs.append(f"{path}: const")
        if "enum" in schema and not any(_json_equal(instance, e) for e in schema["enum"]):
            errs.append(f"{path}: enum")
        if isinstance(instance, str):
            if "pattern" in schema and not re.search(schema["pattern"], instance):
                errs.append(f"{path}: pattern")
            if "minLength" in schema and len(instance) < schema["minLength"]:
                errs.append(f"{path}: minLength")
            if "maxLength" in schema and len(instance) > schema["maxLength"]:
                errs.append(f"{path}: maxLength")
        if _is_number(instance):
            if "minimum" in schema and instance < schema["minimum"]:
                errs.append(f"{path}: minimum")
            if "maximum" in schema and instance > schema["maximum"]:
                errs.append(f"{path}: maximum")
        if isinstance(instance, dict):
            for name in schema.get("required", []):
                if name not in instance:
                    errs.append(f"{path}: required {name}")
            props = schema.get("properties", {})
            for key, value in instance.items():
                child = f"{path}/{key}"
                if key in props:
                    errs += self.errors(value, props[key], child)
                elif "additionalProperties" in schema:
                    errs += self.errors(value, schema["additionalProperties"], child)
        if isinstance(instance, list):
            if "maxItems" in schema and len(instance) > schema["maxItems"]:
                errs.append(f"{path}: maxItems")
            if "items" in schema:
                for index, item in enumerate(instance):
                    errs += self.errors(item, schema["items"], f"{path}/{index}")
        if "anyOf" in schema:
            if not any(not self.errors(instance, s, path) for s in schema["anyOf"]):
                errs.append(f"{path}: anyOf")
        if "oneOf" in schema:
            matched = sum(1 for s in schema["oneOf"] if not self.errors(instance, s, path))
            if matched != 1:
                errs.append(f"{path}: oneOf matched {matched}")
        return errs

    def errors_for_def(self, instance, def_name: str):
        return self.errors(instance, {"$ref": f"#/$defs/{def_name}"})


def iter_subschemas(schema):
    """遍历 Schema 中所有处于“子 Schema 位置”的对象（不把属性名当关键字）。"""
    if not isinstance(schema, dict):
        return
    yield schema
    for key in ("properties", "$defs"):
        for sub in schema.get(key, {}).values():
            yield from iter_subschemas(sub)
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            yield from iter_subschemas(schema[key])
    for key in ("anyOf", "oneOf"):
        for sub in schema.get(key, []):
            yield from iter_subschemas(sub)


SCHEMA_BYTES = SCHEMA_PATH.read_bytes()
SCHEMA = json.loads(SCHEMA_BYTES.decode("utf-8"))
MINI = MiniSchemaValidator(SCHEMA)


# ---------------------------------------------------------------------------
# 断言辅助
# ---------------------------------------------------------------------------
class ProtocolTestCase(unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.reg = P.build_default_registry()

    def assertCode(self, code, func, *args, expect_field=_UNSET, **kwargs):
        with self.assertRaises(P.ProtocolError) as caught:
            func(*args, **kwargs)
        exc = caught.exception
        self.assertEqual(exc.code, code, f"期望错误码 {code}，实际 {exc.code}")
        if expect_field is not _UNSET:
            self.assertEqual(exc.field, expect_field)
        return exc

    # P2 调和：原有的 assertCodeIn（接受多个码）与 assertRejected（只要求被拒绝）已随各处
    # 歧义的裁决一并移除；所有负例都用 assertCode 断言唯一稳定错误码（7.4、规格澄清第 19 节）。

    def assertUnchanged(self, before, after):
        self.assertEqual(before, after, "被校验对象不得被修改（不删字段、不补默认值）")


# ===========================================================================
# 常量与结构化错误（01-D02、4.3.6）
# ===========================================================================
class ConstantsAndErrorTests(ProtocolTestCase):
    REQUIRED_CODES = {
        # 4.2.7 表
        "E_JSON_INPUT_TYPE", "E_JSON_LIMIT", "E_JSON_ENCODING", "E_JSON_BOM", "E_JSON_SYNTAX",
        "E_JSON_DUPLICATE_KEY",
        # 4.3.6 表
        "E_INTEGER_RANGE", "E_PATH_SYNTAX", "E_PATH_RESERVED", "E_PATH_ESCAPE",
        "E_PATH_RESOLUTION_FAILED", "E_RESOURCE_KIND", "E_RESOURCE_HASH_MISMATCH",
        "E_RESOURCE_CYCLE", "E_GIT_OBJECT_MISSING", "E_GIT_OBJECT_TYPE",
        "E_GIT_FORMAT_UNSUPPORTED", "E_EVENT_GAP", "E_EVENT_REPLAY_CONFLICT",
        "E_PROTOCOL_INCOMPLETE", "E_USAGE_CONFLICT", "E_USAGE_SCOPE_UNKNOWN",
        "E_USAGE_CURRENCY_MISMATCH", "E_BASELINE_DRIFT", "E_BASELINE_INPUT_MISSING",
        "E_COMPAT_UNSUPPORTED",
        # 附录 B.2 参考实现用到的码
        "E_JSON_UNICODE", "E_JSON_NON_FINITE", "E_JSON_VALUE_TYPE", "E_JSON_CYCLE",
        "E_JSON_KEY_TYPE", "E_SCHEMA_TYPE", "E_SCHEMA_VERSION_TYPE",
        "E_SCHEMA_VERSION_UNSUPPORTED", "E_SCHEMA_FIELDS", "E_RESOURCE_FIELD",
        "E_RESOURCE_PATH_REQUIRED", "E_RESOURCE_BYTES",
        # 01-T2 新增
        "E_ID_SYNTAX", "E_SCHEMA_RECORD_TYPE", "E_CONTEXT_INCOMPLETE", "E_CONTEXT_BINDING",
        "E_PATH_COLLISION", "E_PATH_NOT_FOUND", "E_PATH_ROOT", "E_GIT_OID_SYNTAX",
        "E_TIME_FORMAT", "E_EVENT_RAW_RANGE", "E_EVENT_RAW_REF_UNKNOWN",
        "E_EVENT_TYPE_UNKNOWN", "E_EVENT_SOURCE", "E_EVENT_EVIDENCE_MISSING",
        "E_USAGE_UNKNOWN_REASON", "E_USAGE_VALUE", "E_PROVENANCE_CLAIM",
        "E_RESOURCE_CONFLICT", "E_RESOURCE_INDEX_FAILED", "E_RESOURCE_MISSING",
    }

    def test_A09_protocol_constants(self):
        """1.3、01-D01/D02/D04：协议家族、公共记录版本、Schema $id、序列化 profile 与上限固定。"""
        self.assertEqual(P.PROTOCOL_FAMILY, "codekit-public")
        self.assertEqual(P.PUBLIC_SCHEMA_VERSION, 1)
        self.assertIs(type(P.PUBLIC_SCHEMA_VERSION), int)
        self.assertEqual(P.SCHEMA_ID, "urn:codekit:public-protocol:1")
        self.assertEqual(P.SNAPSHOT_PROFILE, "codekit-config-json-py-v1")
        self.assertEqual(P.MAX_SAFE_INTEGER, 2**53 - 1)
        self.assertEqual(P.DEFAULT_MAX_BYTES, 1_048_576)
        self.assertEqual(P.DEFAULT_MAX_DEPTH, 64)
        self.assertEqual(tuple(P.ROLES), ("planner", "executor", "observer"))
        self.assertEqual(tuple(P.PLATFORMS), ("linux", "macos", "windows"))
        self.assertEqual(tuple(P.PUBLIC_RECORD_TYPES),
                         ("run-context", "run-event", "usage-observation"))
        self.assertEqual(tuple(P.REPRESENTATIONS),
                         ("captured_raw", "redacted_raw", "normalized_event", "synthetic_fixture"))
        self.assertEqual(tuple(P.ORIGIN_CLASSES), ("legacy", "captured", "synthetic", "negative"))

    def test_A05_legacy_verdicts_match_dispatcher(self):
        """4.1.4、01-A05：旧 verdict 名称原样保留；与 scripts/pi_dispatch.py 的 VERDICTS 一致以防漂移。
        用 AST 读取常量，不执行旧调度器模块。"""
        tree = ast.parse(PI_DISPATCH_PATH.read_text(encoding="utf-8"))
        legacy = None
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "VERDICTS" for t in node.targets):
                legacy = ast.literal_eval(node.value)
        self.assertIsNotNone(legacy, "scripts/pi_dispatch.py 中找不到 VERDICTS")
        self.assertEqual(tuple(P.LEGACY_VERDICTS), tuple(legacy))
        self.assertEqual(tuple(P.LEGACY_VERDICTS),
                         ("PASS", "ACCEPTED_WITH_EXCEPTION", "REVISE", "BLOCKED", "ESCALATE"))

    def test_A04_error_codes_complete(self):
        """4.2.7、4.3.6、附录 B.2 与 01-T2 新增码都已登记。
        P2 调和补充（protocols-api.md 规格澄清 C-01）：01 的错误码表恰好是这 58 个码，
        不含未写入接口说明的额外码。"""
        missing = self.REQUIRED_CODES - set(P.ERROR_CODES)
        self.assertEqual(missing, set(), f"ERROR_CODES 缺少：{sorted(missing)}")
        extra = set(P.ERROR_CODES) - self.REQUIRED_CODES
        self.assertEqual(extra, set(), f"ERROR_CODES 含未登记于规格的码：{sorted(extra)}")
        self.assertEqual(len(P.ERROR_CODES), 58)

    def test_A04_error_specs_well_formed(self):
        """4.3.6、附录 A error：code 形如 E_[A-Z0-9_]+；message 为安全中文文案且不超过 512；
        retryable 为布尔；category 为非空字符串。"""
        for code, spec in P.ERROR_CODES.items():
            with self.subTest(code=code):
                self.assertRegex(code, r"\AE_[A-Z0-9_]+\Z")
                self.assertIsInstance(spec.message, str)
                self.assertTrue(1 <= len(spec.message) <= 512)
                self.assertRegex(spec.message, r"[\u4e00-\u9fff]", "message 应为中文文案")
                self.assertIs(type(spec.retryable), bool)
                self.assertIsInstance(spec.category, str)
                self.assertTrue(spec.category)

    def test_A04_retryable_semantics(self):
        """4.3.6：输入格式类（E_JSON_*、E_SCHEMA_*、E_INTEGER_RANGE）不可重试；只有“可恢复读取”的码
        与 E_RESOURCE_INDEX_FAILED 为 retryable。
        P4（裁决 R-P1）：不再是全部 E_EVENT_* 为 True。为 True 的恰好是 4.3.6 表“事件完整性”一行的
        E_EVENT_GAP、E_EVENT_REPLAY_CONFLICT、E_PROTOCOL_INCOMPLETE，分段可能尚未封存的
        E_EVENT_RAW_REF_UNKNOWN，以及可幂等补录的 E_RESOURCE_INDEX_FAILED；E_EVENT_RAW_RANGE、
        E_EVENT_TYPE_UNKNOWN、E_EVENT_SOURCE、E_EVENT_EVIDENCE_MISSING 是输入缺陷，同一记录重读仍失败，为 False。
        其余码一律为 False。"""
        expected_true = {"E_EVENT_GAP", "E_EVENT_REPLAY_CONFLICT", "E_PROTOCOL_INCOMPLETE",
                         "E_EVENT_RAW_REF_UNKNOWN", "E_RESOURCE_INDEX_FAILED"}
        for code in ("E_EVENT_RAW_RANGE", "E_EVENT_TYPE_UNKNOWN", "E_EVENT_SOURCE",
                     "E_EVENT_EVIDENCE_MISSING"):
            self.assertIn(code, P.ERROR_CODES)
            self.assertNotIn(code, expected_true)
        for code, spec in P.ERROR_CODES.items():
            with self.subTest(code=code):
                self.assertIs(spec.retryable, code in expected_true)
        # 构造错误时不覆盖 retryable，取错误码表的值。
        self.assertIs(P.ProtocolError("E_EVENT_SOURCE").retryable, False)
        self.assertIs(P.ProtocolError("E_EVENT_RAW_REF_UNKNOWN").retryable, True)

    def test_A04_protocol_error_rejects_unregistered_code(self):
        """4.3.6：错误码是机器接口；未登记的码在构造时就抛 ValueError。"""
        self.assertTrue(issubclass(P.ProtocolError, ValueError))
        with self.assertRaises(ValueError):
            P.ProtocolError("E_NOT_A_REGISTERED_CODE_FOR_TEST")

    def test_A04_error_record_shape_and_no_echo(self):
        """4.3.6、附录 A error/errorDetail、B.1：to_record 给出封闭结构，message 取登记文案，
        retryable 与登记一致，且不回显输入值（这里的值模拟密钥）。"""
        secret = "sk-SECRET-VALUE-0123456789"
        raw = ('{"api_key":"%s","api_key":"%s"}' % (secret, secret)).encode()
        exc = self.assertCode("E_JSON_DUPLICATE_KEY", P.strict_json_loads, raw)
        rec = exc.to_record()
        self.assertEqual(set(rec), {"code", "message", "details", "retryable"})
        self.assertEqual(set(rec["details"]),
                         {"field", "source_ref", "phase", "reason", "hint"})
        self.assertEqual(rec["code"], "E_JSON_DUPLICATE_KEY")
        self.assertEqual(rec["message"], P.ERROR_CODES["E_JSON_DUPLICATE_KEY"].message)
        self.assertIs(rec["retryable"], P.ERROR_CODES["E_JSON_DUPLICATE_KEY"].retryable)
        self.assertIs(exc.retryable, rec["retryable"])
        self.assertEqual(rec["details"]["field"], "/api_key")
        self.assertNotIn(secret, json.dumps(rec, ensure_ascii=False))
        self.assertEqual(MINI.errors_for_def(rec, "error"), [])

    def test_A04_error_record_truncated_to_schema_limits(self):
        """附录 A errorDetail（field/reason/hint ≤ 512、phase ≤ 64）与 B.1“限制字段长度”：
        超长键名形成的 JSON Pointer 在 to_record 中被截断，记录仍通过 Schema。"""
        key = "k" * 5000
        raw = ('{"%s":1,"%s":2}' % (key, key)).encode()
        exc = self.assertCode("E_JSON_DUPLICATE_KEY", P.strict_json_loads, raw)
        rec = exc.to_record()
        details = rec["details"]
        self.assertLessEqual(len(details["field"]), 512)
        self.assertLessEqual(len(details["phase"]), 64)
        self.assertLessEqual(len(details["reason"]), 512)
        if details["hint"] is not None:
            self.assertLessEqual(len(details["hint"]), 512)
        self.assertLessEqual(len(rec["message"]), 512)
        self.assertEqual(MINI.errors_for_def(rec, "error"), [])

    def test_A04_error_record_text_limits_and_retryable_type(self):
        """附录 A errorDetail（phase ≤ 64、reason/hint ≤ 512）与 B.1：P4 新增（第 2 轮复审 tests-mutation
        P251/P254/Q001/Q002/P256）。phase、reason、hint 超长时恰好截到 64/512/512 个码点，记录仍通过
        Schema；其中的孤立代理项替换为 U+FFFD，记录可按 UTF-8 编码；retryable 覆盖值必须是 bool。"""
        exc = P.ProtocolError("E_JSON_SYNTAX", phase="p" * 100, reason="r" * 1000, hint="h" * 1000)
        rec = exc.to_record()
        self.assertEqual((len(rec["details"]["phase"]), len(rec["details"]["reason"]),
                          len(rec["details"]["hint"])), (64, 512, 512))
        self.assertEqual(rec["details"]["phase"], "p" * 64)
        self.assertEqual(MINI.errors_for_def(rec, "error"), [])
        # 恰好等于上限时不截断。
        exact = P.ProtocolError("E_JSON_SYNTAX", phase="p" * 64, reason="r" * 512, hint="h" * 512).to_record()
        self.assertEqual((exact["details"]["phase"], exact["details"]["reason"], exact["details"]["hint"]),
                         ("p" * 64, "r" * 512, "h" * 512))
        dirty = P.ProtocolError("E_JSON_SYNTAX", phase="ph\ud800", reason="bad\ud800", hint="x\udfffy")
        for details in (dirty.to_record()["details"], dirty.details):
            self.assertEqual((details["phase"], details["reason"], details["hint"]),
                             ("ph�", "bad�", "x�y"))
            json.dumps(details, ensure_ascii=False).encode("utf-8")
        P.check_json_value(dirty.to_record())
        for bad in ("yes", 1, 0, None.__class__):
            with self.subTest(retryable=bad):
                with self.assertRaises(ValueError):
                    P.ProtocolError("E_JSON_SYNTAX", retryable=bad)
        self.assertIs(P.ProtocolError("E_JSON_SYNTAX", retryable=True).to_record()["retryable"], True)

    def test_A04_error_record_is_strict_json_for_bad_key(self):
        """4.2.7 顺序 6、4.3.6：键中含孤立代理项时，错误记录本身仍须是合法 Unicode 标量的 JSON，
        能被 check_json_value 接受并以 UTF-8 编码（不能把非法输入原样带进错误出口）。"""
        exc = self.assertCode("E_JSON_UNICODE", P.strict_json_loads, b'{"\\ud800":1}')
        rec = exc.to_record()
        P.check_json_value(rec)
        json.dumps(rec, ensure_ascii=False).encode("utf-8")
        self.assertEqual(MINI.errors_for_def(rec, "error"), [])

    def test_A04_error_details_encodable_and_field_marked(self):
        """4.3.6、B.1：P2 返工新增（复审 json 视角：details 回显孤立代理项、截断指针可能指向别的键）。
        details 与 to_record 中的 field 含孤立代理项或超过上限时，截到最长的**祖先**指针（最短为根
        ""），不在 "~" 与 0/1 之间截断，也不把代理项换成 U+FFFD 而误指向另一个真实键；reason 末尾追加
        FIELD_TRUNCATED_MARK。details 可按 UTF-8 编码；原始指针仍保留在 exc.field 上。"""
        mark = P.FIELD_TRUNCATED_MARK
        exc = self.assertCode("E_JSON_UNICODE", P.strict_json_loads, b'{"p":{"\\ud800":1}}')
        self.assertEqual(exc.field, "/p/\ud800")
        for details in (exc.details, exc.to_record()["details"]):
            self.assertEqual(details["field"], "/p")
            self.assertTrue(details["reason"].endswith(mark))
            json.dumps(details, ensure_ascii=False).encode("utf-8")
        P.check_json_value(exc.details)
        # 超长键：截到祖先 /p；不会留下以 "~" 结尾的非法指针，也不会指向更短的另一个键。
        key = "a" * 510 + "~b"
        raw = ('{"p":{"%s":1,"%s":2}}' % (key, key)).encode()
        exc = self.assertCode("E_JSON_DUPLICATE_KEY", P.strict_json_loads, raw)
        self.assertEqual(exc.details["field"], "/p/" + "a" * 510 + "~0b")  # details 不按长度截断
        self.assertFalse(exc.details["reason"].endswith(mark))
        rec = exc.to_record()
        self.assertEqual(rec["details"]["field"], "/p")
        self.assertTrue(rec["details"]["reason"].endswith(mark))
        self.assertEqual(MINI.errors_for_def(rec, "error"), [])
        # 未改写的指针不加标记。
        rec = self.assertCode("E_JSON_DUPLICATE_KEY", P.strict_json_loads,
                              b'{"a~b":{"x":1,"x":2}}').to_record()
        self.assertEqual(rec["details"]["field"], "/a~0b/x")
        self.assertEqual(rec["details"]["reason"], "duplicate_object_member")

    def test_A04_doc_sample_4_3_6_error(self):
        """4.3.6 样例逐字取出：通过附录 A error 结构；同一故障（嵌套重复键）由实现产生的记录
        code、field、retryable 与样例一致，message 取登记文案。"""
        sample = P.strict_json_loads(SAMPLE_ERROR.encode("utf-8"))
        self.assertEqual(MINI.errors_for_def(sample, "error"), [])
        self.assertIn(sample["code"], P.ERROR_CODES)
        self.assertIs(P.ERROR_CODES[sample["code"]].retryable, sample["retryable"])
        exc = self.assertCode("E_JSON_DUPLICATE_KEY", P.strict_json_loads,
                              b'{"profiles":{"default":{"model":"a","model":"b"}}}',
                              expect_field="/profiles/default/model")
        rec = exc.to_record()
        self.assertEqual(rec["details"]["field"], sample["details"]["field"])
        self.assertEqual(rec["retryable"], sample["retryable"])
        self.assertEqual(set(rec["details"]), set(sample["details"]))


# ===========================================================================
# 严格 JSON（4.2.6、4.2.7；01-F001–F013）
# ===========================================================================
class StrictJsonTests(ProtocolTestCase):
    def test_F001_valid_utf8_object_unchanged(self):
        """01-F001：合法 UTF-8 对象解析成功，字段值与类型不变（int 仍为 int，1.0 仍为 float）。"""
        raw = ('{"文字":"测试","n":1,"neg":-0,"f":1.5,"one":1.0,"big":9007199254740991,'
               '"a":[null,true,false,"x"],"o":{},"esc":"\\u00e9\\n"}').encode("utf-8")
        value = P.strict_json_loads(raw)
        self.assertEqual(value["文字"], "测试")
        self.assertIs(type(value["n"]), int)
        self.assertEqual(value["neg"], 0)
        self.assertIs(type(value["f"]), float)
        self.assertIs(type(value["one"]), float)
        self.assertEqual(value["big"], 2**53 - 1)
        self.assertEqual(value["a"], [None, True, False, "x"])
        self.assertIs(value["a"][1], True)
        self.assertEqual(value["o"], {})
        self.assertEqual(value["esc"], "\u00e9\n")

    def test_F001_scalars_and_surrounding_whitespace(self):
        """RFC 8259 / 4.2.7 顺序 4：顶层标量与前后空白合法；文件末尾 LF 不构成第二文档。"""
        self.assertEqual(P.strict_json_loads(b'"x"'), "x")
        self.assertIsNone(P.strict_json_loads(b"null"))
        self.assertEqual(P.strict_json_loads(b' {"a":1} \n'), {"a": 1})
        self.assertEqual(P.strict_json_loads(SYNTHETIC_SAMPLE_BYTES),
                         {"fixture": "synthetic", "ok": True})

    def test_F002_top_level_duplicate_key(self):
        """01-F002 / 4.2.7 顺序 5：顶层重复键 → E_JSON_DUPLICATE_KEY，field 为 JSON Pointer。"""
        self.assertCode("E_JSON_DUPLICATE_KEY", P.strict_json_loads, b'{"a":1,"a":2}',
                        expect_field="/a")
        self.assertCode("E_JSON_DUPLICATE_KEY", P.strict_json_loads, b'{"a":1,"a":1}',
                        expect_field="/a")

    def test_F003_nested_duplicate_key_pointer(self):
        """01-F003：嵌套重复键同样拒绝，定位实际字段；~ 与 / 按 RFC 6901 转义。"""
        cases = [
            (b'{"a":[{"x/y":1,"x/y":2}]}', "/a/0/x~1y"),
            (b'{"m":{"a~b":1,"a~b":2}}', "/m/a~0b"),
            (b'[{"x":1,"x":2}]', "/0/x"),
            (b'{"profiles":{"default":{"model":"a","model":"b"}}}', "/profiles/default/model"),
        ]
        for raw, pointer in cases:
            with self.subTest(raw=raw):
                self.assertCode("E_JSON_DUPLICATE_KEY", P.strict_json_loads, raw,
                                expect_field=pointer)

    def test_F004_escaped_duplicate_key(self):
        """01-F004：a 与 \\u0061 转义后相同，按重复键拒绝；\\/ 与 / 同理。"""
        self.assertCode("E_JSON_DUPLICATE_KEY", P.strict_json_loads, b'{"a":1,"\\u0061":2}',
                        expect_field="/a")
        self.assertCode("E_JSON_DUPLICATE_KEY", P.strict_json_loads, b'{"a/b":1,"a\\/b":2}',
                        expect_field="/a~1b")

    def test_F005_non_finite_literals(self):
        """01-F005 / 4.2.6：NaN、Infinity、-Infinity 字面量拒绝（顶层与嵌套）。"""
        for raw in (b"NaN", b"Infinity", b"-Infinity", b'{"x":NaN}', b'[1,Infinity]',
                    b'{"x":-Infinity}'):
            with self.subTest(raw=raw):
                self.assertCode("E_JSON_NON_FINITE", P.strict_json_loads, raw)

    def test_F006_float_overflow(self):
        """01-F006：1e10000 这类溢出为无穷大的数值同样拒绝，不只拦字面 Infinity。"""
        for raw in (b"1e10000", b"-1e10000", b'{"x":1E400}', b"[1.5e999]"):
            with self.subTest(raw=raw):
                self.assertCode("E_JSON_NON_FINITE", P.strict_json_loads, raw)

    def test_F007_bom_rejected(self):
        """01-F007 / 4.2.7 顺序 2：新协议 JSON 带 UTF-8 BOM → E_JSON_BOM。"""
        raw = b'\xef\xbb\xbf{"a":1}'
        self.assertCode("E_JSON_BOM", P.strict_json_loads, raw)
        self.assertEqual(raw, b'\xef\xbb\xbf{"a":1}')

    def test_F008_invalid_utf8(self):
        """01-F008 / 4.2.7 顺序 2：无效 UTF-8（孤立续字节、过长编码、UTF-8 编码的代理项、UTF-16）
        → E_JSON_ENCODING；原字节不被改写。"""
        for raw in (b'{"a":"\xff"}', b'{"a":"\xc0\xaf"}', b'"\xed\xa0\x80"',
                    b'\xff\xfe{\x00}\x00', b'{"a":"\xe6\xb5"}'):
            with self.subTest(raw=raw):
                before = bytes(raw)
                self.assertCode("E_JSON_ENCODING", P.strict_json_loads, raw)
                self.assertEqual(raw, before)

    def test_F009_lone_surrogate(self):
        """01-F009 / 4.2.7 顺序 6：孤立代理项转义（值与键都查、顺序颠倒的代理对）→ E_JSON_UNICODE。"""
        self.assertCode("E_JSON_UNICODE", P.strict_json_loads, b'"\\ud800"')
        self.assertCode("E_JSON_UNICODE", P.strict_json_loads, b'{"a":"\\udc00"}',
                        expect_field="/a")
        for raw in (b'{"\\ud800":1}', b'"\\ude00\\ud83d"', b'"\\ud83dx"', b'["ok","\\udfff"]'):
            with self.subTest(raw=raw):
                self.assertCode("E_JSON_UNICODE", P.strict_json_loads, raw)

    def test_F010_surrogate_pair_accepted(self):
        """01-F010：合法代理对解码为对应字符（值与键）。"""
        self.assertEqual(P.strict_json_loads(b'"\\ud83d\\ude00"'), "\U0001f600")
        self.assertEqual(P.strict_json_loads(b'{"\\ud83d\\ude00":1}'), {"\U0001f600": 1})

    def test_F011_trailing_document_and_syntax(self):
        """01-F011 / 4.2.7 顺序 4：尾随第二文档及其他文法错误 → E_JSON_SYNTAX。"""
        for raw in (b"{}{}", b'{"a":1} {"b":2}', b"1 2", b'{"a":}', b"{'a':1}",
                    b'{"a":1,}', b"[1,]", b"tru", b'"unterminated', b"01", b"+1", b".5",
                    b'"a\nb"', b" "):
            with self.subTest(raw=raw):
                self.assertCode("E_JSON_SYNTAX", P.strict_json_loads, raw)

    def test_F012_empty_and_byte_limit(self):
        """01-F012 / 4.2.7 顺序 1、01-D04：空输入与超过字节上限 → E_JSON_LIMIT；恰好等于上限可接受。"""
        self.assertCode("E_JSON_LIMIT", P.strict_json_loads, b"")
        self.assertCode("E_JSON_LIMIT", P.strict_json_loads, b"{}", max_bytes=1)
        self.assertEqual(P.strict_json_loads(b"{}", max_bytes=2), {})
        at_limit = b'"' + b"a" * (P.DEFAULT_MAX_BYTES - 2) + b'"'
        self.assertEqual(len(at_limit), 1_048_576)
        self.assertEqual(len(P.strict_json_loads(at_limit)), P.DEFAULT_MAX_BYTES - 2)
        over = b'"' + b"a" * (P.DEFAULT_MAX_BYTES - 1) + b'"'
        self.assertCode("E_JSON_LIMIT", P.strict_json_loads, over)

    def test_F012_depth_limit(self):
        """01-F012 / 4.2.7 顺序 3、01-D04：嵌套 64 层可接受，65 层 → E_JSON_LIMIT；
        字符串中的括号不计深度；max_depth 可调。"""
        self.assertIsInstance(P.strict_json_loads(b"[" * 64 + b"]" * 64), list)
        self.assertCode("E_JSON_LIMIT", P.strict_json_loads, b"[" * 65 + b"]" * 65)
        self.assertCode("E_JSON_LIMIT", P.strict_json_loads, b"[[[]]]", max_depth=2)
        self.assertEqual(P.strict_json_loads(b'{"literal":"[[["}', max_depth=1),
                         {"literal": "[[["})
        self.assertCode("E_JSON_LIMIT", P.strict_json_loads,
                        b'{"a":' * 65 + b"1" + b"}" * 65)

    def test_F012_depth_ignores_brackets_in_escaped_strings(self):
        """01-F012 / 4.2.7：P2 返工新增（复审变异：深度检查的转义处理退化后测试仍全过）。
        字符串里的 \\"、\\\\、\\u005b 之后跟括号都不计深度；字符串之后的真实嵌套照常计数。"""
        value = P.strict_json_loads(b'["a\\"' + b"[" * 70 + b'"]')
        self.assertEqual(value, ['a"' + "[" * 70])
        self.assertEqual(P.strict_json_loads(b'["\\"[[[", "\\u005b\\u005b"]', max_depth=1),
                         ['"[[[', "[["])
        self.assertEqual(P.strict_json_loads(b'{"k\\"[[[":"\\\\[{"}', max_depth=1),
                         {'k"[[[': "\\[{"})
        # "\\\\" 是一个反斜杠，字符串随后闭合：之后的真实嵌套必须计数。
        accepted = P.strict_json_loads(b'["\\\\",' + b"[" * 63 + b"]" * 63 + b"]")
        self.assertEqual(accepted[0], "\\")
        self.assertCode("E_JSON_LIMIT", P.strict_json_loads,
                        b'["\\\\",' + b"[" * 64 + b"]" * 64 + b"]")
        # 字符串内含 \\" 之后是 71 层真实嵌套：必须按超深拒绝，不能被转义处理“吞掉”。
        self.assertCode("E_JSON_LIMIT", P.strict_json_loads,
                        b'["\\"",' + b"[" * 70 + b"]" * 70 + b"]")

    def test_F011_unescaped_quote_is_syntax_not_limit(self):
        """4.2.7“单一故障输入稳定返回对应码”：P2 返工新增（复审 json 视角）。字符串里漏写反斜杠
        （唯一故障）无论后面有多少个括号都报 E_JSON_SYNTAX，不因括号数量变成 E_JSON_LIMIT；
        尾随的第二文档本身过深，也按尾随文档报 E_JSON_SYNTAX。"""
        for n in (1, 60, 63, 64, 65, 70, 200):
            with self.subTest(brackets=n):
                self.assertCode("E_JSON_SYNTAX", P.strict_json_loads,
                                b'{"msg":"a"b' + b"[" * n + b'"}')
        self.assertCode("E_JSON_SYNTAX", P.strict_json_loads, b"{}" + b"[" * 65 + b"]" * 65)

    def test_F012_long_parent_pointer_is_not_quadratic(self):
        """01-D04 资源上限：P2 返工新增（复审 json 视角，major）。父路径很长（长键，或含 / ~ 的键
        转义后更长）时，遍历不得为每个元素复制整条父路径：1 MiB 以内的输入，解析、原生值检查与
        快照都应在秒级以内完成（修复前分别约 21 s 与 16 s）。阈值取 5 s，留足慢机器余量。"""
        for key in (b"/" * 500_000, b"k" * 500_000):
            raw = b'{"' + key + b'":[' + b",".join([b"0"] * 273_995) + b"]}"
            self.assertLessEqual(len(raw), P.DEFAULT_MAX_BYTES)
            with self.subTest(key=key[:1]):
                start = time.perf_counter()
                value = P.strict_json_loads(raw)
                P.check_json_value(value)
                P.stable_snapshot_bytes(value)
                self.assertLess(time.perf_counter() - start, 5.0)
        # 错误定位仍是完整、正确转义的指针。
        long_key = "x/" * 1000
        raw = ('{"%s":[{"d":1,"d":2}]}' % long_key).encode()
        self.assertCode("E_JSON_DUPLICATE_KEY", P.strict_json_loads, raw,
                        expect_field="/" + long_key.replace("/", "~1") + "/0/d")

    def test_F012_recursion_is_limit_not_crash(self):
        """01-F012 / 01-T2 规格：递归超限归入 E_JSON_LIMIT，不能泄漏 RecursionError。
        （非递归实现可以直接接受该输入；两种结果都合规。）"""
        raw = b"[" * 100_000 + b"]" * 100_000
        try:
            P.strict_json_loads(raw, max_depth=10**9)
        except P.ProtocolError as exc:
            self.assertEqual(exc.code, "E_JSON_LIMIT")

    def test_F013_integer_range(self):
        """4.1.1、01-D04：整数绝对值不超过 2^53-1；超出或超长数字串 → E_INTEGER_RANGE（不截断）。"""
        self.assertEqual(P.strict_json_loads(b"9007199254740991"), 2**53 - 1)
        self.assertEqual(P.strict_json_loads(b"-9007199254740991"), -(2**53 - 1))
        for raw in (b"9007199254740992", b"-9007199254740992", b'{"n":18446744073709551616}',
                    b"1" * 5000):
            with self.subTest(raw=raw[:24]):
                self.assertCode("E_INTEGER_RANGE", P.strict_json_loads, raw)

    def test_A04_numeric_errors_carry_pointer(self):
        """4.2.7、protocols-api.md 第 4 节：P4 第 3 轮新增（复审 json 视角）。严格解析阶段的 E_JSON_NON_FINITE 与
        E_INTEGER_RANGE 也带 JSON Pointer，并与 check_json_value 对同一个值给出的 field 相同（修复前解析钩子内
        直接抛错，field 恒为 None）；顶层标量的 field 为 None。超长数字串仍按位数判定。"""
        cases = [
            (b'{"n":[1,9007199254740992]}', {"n": [1, 2**53]}, "E_INTEGER_RANGE", "/n/1",
             "integer_outside_profile"),
            (b'{"n":[1,-9007199254740992]}', {"n": [1, -(2**53)]}, "E_INTEGER_RANGE", "/n/1",
             "integer_outside_profile"),
            (b'{"n":[1,NaN]}', {"n": [1, float("nan")]}, "E_JSON_NON_FINITE", "/n/1", "non_finite_literal"),
            (b'{"a/b":{"x~y":-Infinity}}', {"a/b": {"x~y": float("-inf")}}, "E_JSON_NON_FINITE",
             "/a~1b/x~0y", "non_finite_literal"),
            (b'{"f":1e400}', {"f": float("inf")}, "E_JSON_NON_FINITE", "/f", "numeric_overflow"),
        ]
        for raw, value, code, pointer, reason in cases:
            with self.subTest(raw=raw):
                exc = self.assertCode(code, P.strict_json_loads, raw, expect_field=pointer)
                self.assertEqual(exc.reason, reason)
                self.assertCode(code, P.check_json_value, value, expect_field=pointer)
        exc = self.assertCode("E_INTEGER_RANGE", P.strict_json_loads, b'{"big":[' + b"1" * 5000 + b"]}",
                              expect_field="/big/0")
        self.assertEqual(exc.reason, "integer_outside_profile")
        for raw, code in ((b"NaN", "E_JSON_NON_FINITE"), (b"1e10000", "E_JSON_NON_FINITE"),
                          (b"9007199254740992", "E_INTEGER_RANGE")):
            with self.subTest(top_level=raw):
                self.assertCode(code, P.strict_json_loads, raw, expect_field=None)

    def test_A04_multi_defect_examples_in_document_order(self):
        """protocols-api.md 第 4 节“检查时机”：P4 第 3 轮（数值错误改在解析后按文档顺序报告）。文档列出的多缺陷
        示例固定为：{"a":1,"a":NaN} → 重复键（先于第二个值检出）；{"a":NaN,"a":1} → 非有限数（/a）；
        [1e400,] → 文法错误（数值错误不再在解析中途抛出）；{"a":"\\ud800","b":1,"b":2} → 孤立代理项。
        多缺陷输入本来不承诺首错；这里固定的是文档示例本身，改动须同步修改文档。"""
        self.assertCode("E_JSON_DUPLICATE_KEY", P.strict_json_loads, b'{"a":1,"a":NaN}', expect_field="/a")
        self.assertCode("E_JSON_NON_FINITE", P.strict_json_loads, b'{"a":NaN,"a":1}', expect_field="/a")
        self.assertCode("E_JSON_SYNTAX", P.strict_json_loads, b"[1e400,]")
        self.assertCode("E_JSON_UNICODE", P.strict_json_loads, b'{"a":"\\ud800","b":1,"b":2}',
                        expect_field="/a")

    def test_F011_syntax_reason_is_fixed_position_in_hint(self):
        """protocols-api.md 3.1“reason：固定的机器可读原因”：P4 第 3 轮新增（复审 fidelity/json 视角）。
        E_JSON_SYNTAX 的 reason 恒为 syntax_error，不随输入位置变化；行/列位置（取自标准库 json）只放在可选的
        hint 中，to_record() 的 reason 同样固定。"""
        for raw, hint in ((b"[1,2", "line=1 column=5"), (b"\n", "line=2 column=1"),
                          (b'{"a":1}\xef\xbb\xbf', "line=1 column=8"), (b"{}{}", "line=1 column=3")):
            with self.subTest(raw=raw):
                exc = self.assertCode("E_JSON_SYNTAX", P.strict_json_loads, raw)
                self.assertEqual(exc.reason, "syntax_error")
                self.assertEqual(exc.hint, hint)
                self.assertEqual(exc.to_record()["details"]["reason"], "syntax_error")

    def test_A04_input_type(self):
        """4.2.7 顺序 1：输入必须是 bytes；str、bytearray、memoryview、None → E_JSON_INPUT_TYPE。"""
        for value in ('{"a":1}', bytearray(b'{"a":1}'), memoryview(b'{"a":1}'), None, 1, ""):
            with self.subTest(value=type(value).__name__):
                self.assertCode("E_JSON_INPUT_TYPE", P.strict_json_loads, value)

    def test_A04_pre_parse_stage_order(self):
        """4.2.7 顺序 1→2：类型检查先于长度，长度检查先于 BOM/编码。"""
        self.assertCode("E_JSON_INPUT_TYPE", P.strict_json_loads, "x" * 2_000_000)
        self.assertCode("E_JSON_LIMIT", P.strict_json_loads, b"\xef\xbb\xbf{}", max_bytes=3)
        self.assertCode("E_JSON_LIMIT", P.strict_json_loads, b'"\xff\xff"', max_bytes=3)


# ===========================================================================
# 原生 JSON 值与固定快照（4.2.6、附录 C.2；01-F015–F020，01-A03）
# ===========================================================================
class SnapshotTests(ProtocolTestCase):
    def test_A03_golden_vectors(self):
        """附录 C.2：五组黄金向量逐字节、逐摘要一致。"""
        for value, expected_bytes, expected_digest in GOLDEN_VECTORS:
            with self.subTest(value=value):
                out = P.stable_snapshot_bytes(value)
                self.assertIs(type(out), bytes)
                self.assertEqual(out, expected_bytes)
                self.assertEqual(sha(out), expected_digest)
                self.assertEqual(P.sha256_hex(out), expected_digest)

    def test_A03_synthetic_sample_is_file_bytes_not_snapshot(self):
        """4.2.2、4.2.4：0036dde3… 是合成文件字节 {"fixture":"synthetic","ok":true}\\n 的摘要。
        资源摘要覆盖文件原字节：语义相同但排版不同的字节摘要不同，不能用快照去“等价化”。"""
        self.assertEqual(P.sha256_hex(SYNTHETIC_SAMPLE_BYTES), SYNTHETIC_SAMPLE_SHA256)
        ref = P.strict_json_loads(SAMPLE_RESOURCE_REF.encode("utf-8"))
        P.verify_resource_bytes(ref, SYNTHETIC_SAMPLE_BYTES, self.reg)
        reordered = b'{"ok":true,"fixture":"synthetic"}\n'
        spaced = b'{"fixture": "synthetic", "ok": true}\n'
        for raw in (reordered, spaced, SYNTHETIC_SAMPLE_BYTES.rstrip(b"\n")):
            with self.subTest(raw=raw):
                self.assertEqual(P.stable_snapshot_bytes(P.strict_json_loads(raw)),
                                 SYNTHETIC_SAMPLE_BYTES)
                self.assertNotEqual(P.sha256_hex(raw), SYNTHETIC_SAMPLE_SHA256)
                self.assertCode("E_RESOURCE_HASH_MISMATCH", P.verify_resource_bytes, ref, raw,
                                self.reg)

    def test_A03_sha256_hex(self):
        """原文保留 4.2.1：SHA-256 为 64 位小写十六进制。"""
        self.assertEqual(P.sha256_hex(b""),
                         "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertRegex(P.sha256_hex(b"abc"), r"\A[0-9a-f]{64}\Z")

    def test_A03_snapshot_matches_fixed_expression(self):
        """4.2.6：输出严格等于 json.dumps(... ensure_ascii=False, sort_keys=True,
        separators=(",",":"), allow_nan=False) + LF 的 UTF-8，无 BOM；不排序数组、不做 Unicode 归一化。"""
        values = [
            {"z": [3, 1, 2], "a": {"y": None, "x": True}, "m": -0.0, "f": 0.1, "e": 1e-7,
             "big": 1e21, "s": "tab\t nl\n nul\u0000 ls\u2028 </script>", "u": "文档"},
            {"": "", "nested": [[], {}, [{}]]},
            {"n": 2**53 - 1, "neg": -(2**53 - 1)},
        ]
        for value in values:
            with self.subTest(value=value):
                out = P.stable_snapshot_bytes(value)
                self.assertEqual(out, expected_snapshot(value))
                self.assertFalse(out.startswith(b"\xef\xbb\xbf"))
                self.assertTrue(out.endswith(b"\n"))
                self.assertFalse(out.endswith(b"\n\n"))

    def test_A03_snapshot_is_not_jcs(self):
        """4.2.6：本 profile 不是 RFC 8785/JCS；键按 Python 码点排序，U+FF61 排在 U+1F600 之前。"""
        out = P.stable_snapshot_bytes({"\U0001f600": 1, "\uff61": 2})
        self.assertEqual(out, b'{"\xef\xbd\xa1":2,"\xf0\x9f\x98\x80":1}\n')

    def test_A03_snapshot_does_not_mutate_input(self):
        """4.2.6、01-D05：快照函数不替调用方删除字段、补默认值或改写数组。"""
        value = {"b": [2, 1], "_note": "说明字段不由 01 删除", "a": {"k": 1.0}}
        before = copy.deepcopy(value)
        out = P.stable_snapshot_bytes(value)
        self.assertUnchanged(before, value)
        self.assertIn(b'"_note"', out)

    def test_A03_snapshot_root_must_be_object(self):
        """01-T2 规格、B.2：快照根必须是对象 → 否则 E_SCHEMA_TYPE。"""
        for value in ([], "x", 1, None, [{"a": 1}]):
            with self.subTest(value=value):
                self.assertCode("E_SCHEMA_TYPE", P.stable_snapshot_bytes, value)

    def test_A03_snapshot_root_type_checked_before_values(self):
        """附录 B.2 参考实现、protocols-api.md 开头“参考实现的错误码语义保持不变”：P4 第 3 轮新增（复审 fidelity
        视角）。先检查根的 type 是否精确为 dict，再检查值：OrderedDict 根、含 NaN 或非原生值的 list 根、共享结构
        展开后超大的 list 根都报 E_SCHEMA_TYPE（修复前前两者报 E_JSON_VALUE_TYPE / E_JSON_NON_FINITE，与参考
        实现不同），且不遍历根的内容。根是 dict 时值的错误码不变。"""
        wide: list = [0] * 1000
        for _ in range(8):
            wide = [wide] * 1000
        for value in (OrderedDict(a=1), [float("nan")], [object()], wide, {1, 2}):
            with self.subTest(value=type(value).__name__):
                exc = self.assertCode("E_SCHEMA_TYPE", P.stable_snapshot_bytes, value)
                self.assertEqual(exc.reason, "snapshot_root_must_be_object")
        self.assertCode("E_JSON_NON_FINITE", P.stable_snapshot_bytes, {"x": float("nan")}, expect_field="/x")
        self.assertCode("E_JSON_VALUE_TYPE", P.stable_snapshot_bytes, {"x": OrderedDict()}, expect_field="/x")

    def test_A03_snapshot_byte_limit(self):
        """01-D04：快照输出超过 1 MiB → E_JSON_LIMIT；恰好 1 MiB 可接受。"""
        n = 1_048_576 - len(b'{"a":""}\n')
        self.assertEqual(len(P.stable_snapshot_bytes({"a": "x" * n})), 1_048_576)
        self.assertCode("E_JSON_LIMIT", P.stable_snapshot_bytes, {"a": "x" * (n + 1)})

    def test_A03_snapshot_limit_after_serialization(self):
        """01-D04：P4 新增（第 2 轮复审 json 视角，变异 M1）。遍历时的字节下界不计 UTF-8 多字节，多字节
        字符串能通过下界预算，只能由序列化后的检查拦下：输出 1,048,575 字节接受，1,048,577 字节 →
        E_JSON_LIMIT（reason=snapshot_byte_limit_exceeded，不是下界预算的原因）。"""
        ok = {"a": "é" * 524283}
        self.assertEqual(len(expected_snapshot(ok)), 1_048_575)
        self.assertEqual(P.stable_snapshot_bytes(ok), expected_snapshot(ok))
        over = {"a": "é" * 524284}
        self.assertEqual(len(expected_snapshot(over)), 1_048_577)
        exc = self.assertCode("E_JSON_LIMIT", P.stable_snapshot_bytes, over)
        self.assertEqual(exc.reason, "snapshot_byte_limit_exceeded")

    def test_A03_lower_bound_constants_do_not_reject_valid_values(self):
        """01-D04“只有超过 1 MiB 才报 E_JSON_LIMIT”：P4 新增（第 2 轮复审 json 视角，变异 M2/M3/M5）。
        下界常量（float 3、null 4、true 4、false 5、空容器 2 字节）一旦被高估，合法的 ≤1 MiB 值会被误拒。
        每种值各取恰好不超过 1 MiB 的最大数组：输出与固定表达式相同；各再加一个元素 → E_JSON_LIMIT。"""
        cases = [(0.0, 262142, 1_048_576), (None, 209713, 1_048_573), (True, 209713, 1_048_573),
                 (False, 174761, 1_048_574), ([], 349522, 1_048_574), ({}, 349522, 1_048_574)]
        for item, count, size in cases:
            with self.subTest(item=repr(item)):
                value = {"a": [item] * count}
                self.assertEqual(len(expected_snapshot(value)), size)
                self.assertEqual(P.stable_snapshot_bytes(value), expected_snapshot(value))
                bigger = {"a": [item] * (count + 1)}
                self.assertGreater(len(expected_snapshot(bigger)), 1_048_576)
                self.assertCode("E_JSON_LIMIT", P.stable_snapshot_bytes, bigger)

    def test_A03_underflow_and_negative_zero_integer(self):
        """4.2.6、4.2.7：P4（裁决 R-P6，接受并写明）。下溢不报错：1e-400 解析为 0.0；整数 -0 解析为 int 0，
        快照输出 0（符号丢失，JSON 文法允许）；-0.0 保留为 -0.0。公共记录的数值字段都是整数，需要精确实数的
        字段（金额）用十进制字符串，所以这两点不影响公共记录。"""
        self.assertEqual(P.strict_json_loads(b'{"a":1e-400}'), {"a": 0.0})
        self.assertIs(type(P.strict_json_loads(b'{"a":1e-400}')["a"]), float)
        zero = P.strict_json_loads(b'{"a":-0}')
        self.assertIs(type(zero["a"]), int)
        self.assertEqual(P.stable_snapshot_bytes(zero), b'{"a":0}\n')
        self.assertEqual(P.stable_snapshot_bytes(P.strict_json_loads(b'{"a":-0.0}')), b'{"a":-0.0}\n')
        # 金额是十进制字符串：不经浮点，不会下溢。
        P.validate_usage_observation(make_usage(reported_cost={"amount": "0." + "0" * 60 + "1",
                                                               "currency": "USD"}))

    def test_F015_key_order_irrelevant(self):
        """01-F015：同配置仅对象键插入次序不同 → 相同快照字节与摘要。"""
        a = {"b": {"y": 2, "x": 1}, "a": [{"k": 1, "j": 2}], "c": "v"}
        b = {"c": "v", "a": [{"j": 2, "k": 1}], "b": {"x": 1, "y": 2}}
        self.assertEqual(P.stable_snapshot_bytes(a), P.stable_snapshot_bytes(b))
        self.assertEqual(P.sha256_hex(P.stable_snapshot_bytes(a)),
                         P.sha256_hex(P.stable_snapshot_bytes(b)))

    def test_F016_model_or_authorization_change_changes_digest(self):
        """01-F016 / 4.2.5：只改模型或授权字段 → 快照摘要改变（是否重新审核由 03 判断）。"""
        base = {"model": {"provider": "p", "id": "model-a"}, "network": {"allow": False},
                "role": "executor"}
        model_changed = copy.deepcopy(base)
        model_changed["model"]["id"] = "model-b"
        auth_changed = copy.deepcopy(base)
        auth_changed["network"]["allow"] = True
        d0 = P.sha256_hex(P.stable_snapshot_bytes(base))
        self.assertNotEqual(d0, P.sha256_hex(P.stable_snapshot_bytes(model_changed)))
        self.assertNotEqual(d0, P.sha256_hex(P.stable_snapshot_bytes(auth_changed)))

    def test_F017_machine_path_projection_belongs_to_02(self):
        """01-F017：“仅机器 executable 路径改变 → 语义快照不变、环境锁变化”依赖 02 的语义投影
        （01-D05），01 无法验证。P2 返工（复审：原用例名为 F017 却只测快照器不删字段，会被验收映射
        当作 F017 已覆盖）：改为 skip，原断言移到 test_A03_snapshot_does_not_project_machine_fields。"""
        self.skipTest("01-D05：配置语义投影归 02，F017 由 02 验收；此处未测试，不代表通过")

    def test_A03_snapshot_does_not_project_machine_fields(self):
        """4.2.5、01-D05（A03 边界）：01 快照器不擅自删字段、不做投影。已投影对象字节稳定；
        环境锁因路径不同而变化；调用方未投影时快照会变——这证明 01 不替调用方做投影，
        不是 F017“语义不变”的证明（F017 归 02）。"""
        projection = {"model": {"provider": "p", "id": "m"}, "role": "executor"}
        env_lock_a = {"executor_path": "C:/tools/pi.exe"}
        env_lock_b = {"executor_path": "/usr/local/bin/pi"}
        self.assertEqual(P.stable_snapshot_bytes(projection),
                         P.stable_snapshot_bytes(copy.deepcopy(projection)))
        self.assertNotEqual(P.stable_snapshot_bytes(env_lock_a),
                            P.stable_snapshot_bytes(env_lock_b))
        unprojected = {**projection, **env_lock_a}
        self.assertNotEqual(P.stable_snapshot_bytes(unprojected),
                            P.stable_snapshot_bytes(projection))

    def test_F018_array_order_matters(self):
        """01-F018 / 4.2.6：数组顺序改变 → 默认产生不同字节。"""
        self.assertNotEqual(P.stable_snapshot_bytes({"a": [1, 2]}),
                            P.stable_snapshot_bytes({"a": [2, 1]}))

    def test_F019_unicode_not_normalized(self):
        """01-F019 / 4.2.6：组合（U+00E9）与分解（U+0065 U+0301）形式不归一化，输出原样 UTF-8。"""
        nfc = P.stable_snapshot_bytes({"text": "\u00e9"})
        nfd = P.stable_snapshot_bytes({"text": "e\u0301"})
        self.assertNotEqual(nfc, nfd)
        self.assertIn(b"\xc3\xa9", nfc)
        self.assertIn(b"e\xcc\x81", nfd)

    def test_F019_int_float_and_negative_zero_distinct(self):
        """4.2.6：1 与 1.0、0.0 与 -0.0 按固定表达式保留不同文本，不做“差不多相等”的处理。"""
        self.assertNotEqual(P.stable_snapshot_bytes({"n": 1}), P.stable_snapshot_bytes({"n": 1.0}))
        self.assertEqual(P.stable_snapshot_bytes({"n": -0.0}), b'{"n":-0.0}\n')
        self.assertEqual(P.stable_snapshot_bytes({"n": 0.0}), b'{"n":0.0}\n')

    def test_F020_non_string_keys(self):
        """01-F020：非字符串字典键（int、bool、None、tuple）→ E_JSON_KEY_TYPE，不做隐式转换。
        P4（第 2 轮复审 tests-mutation P017）：键同样要求类型精确为 str，str 子类键也 → E_JSON_KEY_TYPE。"""

        class K(str):
            pass

        for value in ({1: "a"}, {True: 1}, {None: 1}, {(1, 2): 1}, {"ok": {2.5: 1}}, {K("a"): 1},
                      {"ok": {K("b"): 1}}):
            with self.subTest(value=value):
                self.assertCode("E_JSON_KEY_TYPE", P.check_json_value, value)
                self.assertCode("E_JSON_KEY_TYPE", P.stable_snapshot_bytes, value)

    def test_F020_non_native_values(self):
        """01-F020 / B.2：只接受 type() 精确为 dict/list/str/int/float/bool/NoneType 的值；
        子类与其他类型一律 E_JSON_VALUE_TYPE。"""

        class D(dict):
            pass

        class L(list):
            pass

        class Str(str):
            pass

        class Int(int):
            pass

        class Flt(float):
            pass

        class Color(enum.IntEnum):
            RED = 1

        bad = [(1, 2), {1, 2}, frozenset(), b"a", bytearray(b"a"), decimal.Decimal("1"),
               _dt.datetime(2026, 1, 1), OrderedDict(), D(), L(), Str("s"), Int(1), Flt(1.0),
               Color.RED, object(), Path("a")]
        for item in bad:
            with self.subTest(item=type(item).__name__):
                self.assertCode("E_JSON_VALUE_TYPE", P.check_json_value, {"x": item})
                self.assertCode("E_JSON_VALUE_TYPE", P.stable_snapshot_bytes, {"x": item})

    def test_F020_native_values_accepted(self):
        """B.2：原生 JSON 值（含标量根）被 check_json_value 接受并返回 None。"""
        for value in (None, True, False, 0, -1, 1.5, "s", [], {}, {"a": [1, {"b": None}]}):
            with self.subTest(value=value):
                self.assertIsNone(P.check_json_value(value))

    def test_F020_numeric_and_unicode_checks(self):
        """4.2.7 顺序 6、B.2：值检查同样拒绝越界整数、非有限浮点与孤立代理项（键和值）。"""
        cases = [
            ({"x": 2**53}, "E_INTEGER_RANGE"),
            ({"x": -(2**53)}, "E_INTEGER_RANGE"),
            ({"x": float("nan")}, "E_JSON_NON_FINITE"),
            ({"x": float("inf")}, "E_JSON_NON_FINITE"),
            ({"x": float("-inf")}, "E_JSON_NON_FINITE"),
            ({"x": "\ud800"}, "E_JSON_UNICODE"),
            ({"\udc00": 1}, "E_JSON_UNICODE"),
        ]
        for value, code in cases:
            with self.subTest(code=code, value=repr(value)):
                self.assertCode(code, P.check_json_value, value)
                self.assertCode(code, P.stable_snapshot_bytes, value)

    def test_F020_cycles_and_shared_containers(self):
        """B.2：成环容器 → E_JSON_CYCLE；同一容器被复用但不成环可接受。"""
        cyclic: dict = {}
        cyclic["self"] = cyclic
        self.assertCode("E_JSON_CYCLE", P.check_json_value, cyclic)
        self.assertCode("E_JSON_CYCLE", P.stable_snapshot_bytes, cyclic)
        loop: list = []
        loop.append(loop)
        self.assertCode("E_JSON_CYCLE", P.check_json_value, {"a": loop})
        shared = [1]
        self.assertIsNone(P.check_json_value({"a": shared, "b": shared}))
        self.assertEqual(P.stable_snapshot_bytes({"a": shared, "b": shared}),
                         b'{"a":[1],"b":[1]}\n')

    def test_F020_long_cycles_are_cycles_not_limits(self):
        """B.2、protocols-api.md 第 4 节：P4 第 3 轮新增（复审 json 视角）。同一种单一故障（一条回边）无论环多长都报
        E_JSON_CYCLE：修复前深度检查先于环检查，环长超过剩余深度（check_json_value 中 L≥64，快照中 L≥63，记录
        payload 中更低）时报 E_JSON_LIMIT。现在环先于深度判断，深度超限处另做一次不限深度的迭代环检测。过深而
        无环（含共享但不成环的深结构）仍是 E_JSON_LIMIT。"""
        def list_cycle(length):
            head: list = []
            node = head
            for _ in range(length - 1):
                child: list = []
                node.append(child)
                node = child
            node.append(head)
            return head

        def dict_cycle(length):
            head: dict = {}
            node = head
            for index in range(length - 1):
                child: dict = {}
                node["k%d" % index] = child
                node = child
            node["back"] = head
            return head

        for length in (1, 2, 63, 64, 65, 100, 500):
            with self.subTest(length=length):
                self.assertCode("E_JSON_CYCLE", P.check_json_value, list_cycle(length))
                self.assertCode("E_JSON_CYCLE", P.check_json_value, dict_cycle(length))
                self.assertCode("E_JSON_CYCLE", P.check_json_value, list_cycle(length), max_bytes=1 << 20)
                self.assertCode("E_JSON_CYCLE", P.stable_snapshot_bytes, {"k": list_cycle(length)})
                event = make_event(payload={"loop": list_cycle(length)})
                self.assertCode("E_JSON_CYCLE", P.validate_run_event, event, registry=self.reg)
        # 环在深度超限点之下、并经过深度超限点之前的祖先。
        tail = nested_list(80)
        deep = tail
        while deep:
            deep = deep[0]
        root = [tail]
        deep.append(root)
        self.assertCode("E_JSON_CYCLE", P.check_json_value, root)
        # 过深而无环：仍是 E_JSON_LIMIT（含共享子结构）。
        self.assertCode("E_JSON_LIMIT", P.check_json_value, nested_list(65))
        self.assertCode("E_JSON_LIMIT", P.check_json_value, nested_list(100_000))
        shared = nested_list(10)
        diamond = [[shared, shared], [shared]]
        for _ in range(60):
            diamond = [diamond, diamond]
        self.assertCode("E_JSON_LIMIT", P.check_json_value, diamond)
        self.assertCode("E_JSON_LIMIT", P.stable_snapshot_bytes, {"k": nested_list(64)})

    def test_A03_shared_containers_have_serialized_size_budget(self):
        """01-D04、4.2.6：P2 返工新增（复审 json 视角）。共享但不成环的容器按规格可以接受，但展开后
        指数级的共享结构与被反复引用的大字符串，必须在生成输出之前按字节下界预算止损（E_JSON_LIMIT），
        不能先指数级遍历或生成 GB 级输出再判断。check_json_value 的 max_bytes 可显式给出；默认不限。"""
        # 24 层共享展开后约 3300 万个节点：修复前约 16 s（有限时间内以超时断言失败，而不是挂起）。
        dag = [1]
        for _ in range(24):
            dag = [dag, dag]
        start = time.perf_counter()
        self.assertCode("E_JSON_LIMIT", P.stable_snapshot_bytes, {"x": dag})
        self.assertCode("E_JSON_LIMIT", P.check_json_value, {"x": dag}, max_bytes=1_000_000)
        big = "x" * 600_000
        self.assertCode("E_JSON_LIMIT", P.stable_snapshot_bytes, {"a": [big, big]})
        self.assertLess(time.perf_counter() - start, 5.0)
        small = [1]
        for _ in range(5):
            small = [small, small]
        self.assertIsNone(P.check_json_value({"x": small}))
        self.assertEqual(P.stable_snapshot_bytes({"x": small}), expected_snapshot({"x": small}))
        # 下界预算：{"a":"x"} 紧凑输出 9 字节，恰好等于上限时接受，少一字节时拒绝。
        self.assertIsNone(P.check_json_value({"a": "x"}, max_bytes=9))
        self.assertCode("E_JSON_LIMIT", P.check_json_value, {"a": "x"}, max_bytes=8)
        with self.assertRaises(ValueError):
            P.check_json_value({}, max_bytes=0)

    def test_A03_record_validators_budget_shared_dag(self):
        """01-D04、protocols-api.md 6.2/6.3 json_native_record：P4 新增（第 2 轮复审 json 视角，变异 M12 与
        validate_fixture_manifest_set、run.prepared 载荷校验器没有预算的问题）。各记录校验入口、fixture 清单
        与单独调用的 run.prepared 载荷校验器都按 1 MiB 字节下界止损：24 层共享结构（展开后约 3300 万个
        节点）在有限时间内报 E_JSON_LIMIT（reason=serialized_size_lower_bound_exceeded），不做指数级遍历。"""
        dag = [1]
        for _ in range(24):
            dag = [dag, dag]
        reg = self.reg
        prepared = P.build_default_event_types().get("run.prepared").payload_validator
        cases = {
            "validate_run_context": lambda: P.validate_run_context(make_context(x=dag)),
            "validate_run_event": lambda: P.validate_run_event(make_event(payload={"x": dag}), registry=reg),
            "validate_usage_observation": lambda: P.validate_usage_observation(make_usage(x=dag)),
            "validate_public_record": lambda: P.validate_public_record(
                make_usage(x=dag), expected_record_type="usage-observation", registry=reg),
            "validate_raw_span": lambda: P.validate_raw_span({**make_span(), "x": dag}, registry=reg),
            "validate_fixture_manifest_entry": lambda: P.validate_fixture_manifest_entry(
                make_manifest_entry(x=dag), reg),
            "validate_fixture_manifest_set": lambda: P.validate_fixture_manifest_set(
                {"schema_version": 1, "record_type": "fixture-manifest-set", "entries": [], "x": dag}, reg),
            "run.prepared payload_validator": lambda: prepared({"x": dag}),
        }
        for name, call in cases.items():
            with self.subTest(entry=name):
                start = time.perf_counter()
                exc = self.assertCode("E_JSON_LIMIT", call)
                self.assertEqual(exc.reason, "serialized_size_lower_bound_exceeded")
                self.assertLess(time.perf_counter() - start, 5.0)

    def test_F012_value_depth_same_as_parser(self):
        """01-T2 规格（check_json_value 深度“同上”）、01-D04：64 层可接受，65 层 → E_JSON_LIMIT；
        max_depth 可调；超深值不泄漏 RecursionError。"""
        self.assertIsNone(P.check_json_value(nested_list(64)))
        self.assertCode("E_JSON_LIMIT", P.check_json_value, nested_list(65))
        self.assertCode("E_JSON_LIMIT", P.check_json_value, nested_list(3), max_depth=2)
        try:
            P.check_json_value(nested_list(100_000), max_depth=10**9)
        except P.ProtocolError as exc:
            self.assertEqual(exc.code, "E_JSON_LIMIT")


# ===========================================================================
# 标识、RunContext 与派生（4.1.1–4.1.3；01-F021–F023，01-A08）
# ===========================================================================
class IdentifierTests(ProtocolTestCase):
    def test_A08_new_ids_format(self):
        """4.1.1、01-D01：新 request/run 为 req-/run- 加 UUID4 的 32 位小写十六进制。"""
        for maker, prefix, validator in ((P.new_request_id, "req-", P.validate_request_id),
                                         (P.new_run_id, "run-", P.validate_run_id)):
            ids = {maker() for _ in range(64)}
            self.assertEqual(len(ids), 64)
            for value in ids:
                self.assertRegex(value, r"\A%s[0-9a-f]{32}\Z" % prefix)
                self.assertEqual(uuid.UUID(hex=value[4:]).version, 4)
                validator(value)

    def test_F021_request_and_run_id_syntax(self):
        """01-F021 / 4.1.1：非法字符、大写、长度不符、前缀错误、尾随换行、非 str → E_ID_SYNTAX。"""
        P.validate_request_id(REQ)
        P.validate_run_id(RUN)
        bad_req = [REQ + "\n", REQ.upper(), "req-" + "1" * 31, "req-" + "1" * 33, RUN,
                   " " + REQ, "req_" + "1" * 32, "req-" + "g" * 32, "", None, 1,
                   REQ.encode()]
        for value in bad_req:
            with self.subTest(value=value):
                self.assertCode("E_ID_SYNTAX", P.validate_request_id, value)
        bad_run = [RUN + "\n", "RUN-" + "2" * 32, REQ, "run-" + "2" * 31, None]
        for value in bad_run:
            with self.subTest(value=value):
                self.assertCode("E_ID_SYNTAX", P.validate_run_id, value)

    def test_F021_task_logical_kind_sha_syntax(self):
        """01-F021 / 4.1.1、4.2.1：task_id、逻辑 ID、资源 kind、sha256 整串匹配，拒绝尾随换行 → E_ID_SYNTAX。"""
        good = [
            (P.validate_task_id, ["baseline-review", "a", "a" * 64, "a1-b2"]),
            (P.validate_logical_id, ["usage-synthetic-unknown-1", "a.b:c_d-e", "0" + "a" * 127]),
            (P.validate_resource_kind, ["fixture", "raw-segment", "a" + "b" * 63]),
            (P.validate_sha256, ["0" * 64, SYNTHETIC_SAMPLE_SHA256]),
        ]
        for func, values in good:
            for value in values:
                with self.subTest(func=func.__name__, value=value):
                    func(value)
        bad = [
            (P.validate_task_id, ["", "a" * 65, "A", "a--b", "-a", "a-", "a_b", "a\n", " a",
                                  None, 1]),
            (P.validate_logical_id, ["", "a" * 129, ".a", "A", "a\n", "a b", "a/b", None]),
            (P.validate_resource_kind, ["1a", "Fixture", "a_b", "a" * 65, "fixture\n", "", None]),
            (P.validate_sha256, ["A" * 64, "0" * 63, "0" * 65, "sha256:" + "0" * 64,
                                 "0" * 64 + "\n", "placeholder", None]),
        ]
        for func, values in bad:
            for value in values:
                with self.subTest(func=func.__name__, value=value):
                    self.assertCode("E_ID_SYNTAX", func, value)

    def test_A08_require_int_exact_type(self):
        """4.1.1：整数字段只收精确 int；bool、float（含 1.0）、str → E_SCHEMA_TYPE；越界 → E_INTEGER_RANGE。"""
        self.assertEqual(P.require_int(5, field="/x", minimum=1), 5)
        self.assertEqual(P.require_int(2**53 - 1, field="/x", minimum=0), 2**53 - 1)
        for value in (True, False, 1.0, "1", None, [1]):
            with self.subTest(value=value):
                self.assertCode("E_SCHEMA_TYPE", P.require_int, value, field="/x", minimum=0,
                                expect_field="/x")
        self.assertCode("E_INTEGER_RANGE", P.require_int, 0, field="/x", minimum=1,
                        expect_field="/x")
        self.assertCode("E_INTEGER_RANGE", P.require_int, 2**53, field="/x", minimum=0)
        self.assertCode("E_INTEGER_RANGE", P.require_int, 11, field="/x", minimum=0, maximum=10)

    def test_A08_plan_version_and_attempt(self):
        """4.1.1、01-D03：plan_version 为正整数（可空由调用方决定）；attempt 为 None 或非负整数
        （新格式允许 0，不平移历史编号）。"""
        P.validate_plan_version(1, allow_null=False)
        P.validate_plan_version(None, allow_null=True)
        self.assertCode("E_INTEGER_RANGE", P.validate_plan_version, 0, allow_null=True)
        self.assertCode("E_INTEGER_RANGE", P.validate_plan_version, -1, allow_null=True)
        for value in (True, "1", 1.0):
            with self.subTest(value=value):
                self.assertCode("E_SCHEMA_TYPE", P.validate_plan_version, value, allow_null=True)
        self.assertCode("E_SCHEMA_TYPE", P.validate_plan_version, None, allow_null=False)
        for value in (None, 0, 1, 2**53 - 1):
            P.validate_attempt(value)
        self.assertCode("E_INTEGER_RANGE", P.validate_attempt, -1)
        self.assertCode("E_INTEGER_RANGE", P.validate_attempt, 2**53)
        for value in (True, 1.0, "0"):
            with self.subTest(value=value):
                self.assertCode("E_SCHEMA_TYPE", P.validate_attempt, value)

    def test_A08_role_and_platform(self):
        """4.1.1：role ∈ planner/executor/observer；platform ∈ linux/macos/windows（精确、区分大小写）。
        P2 调和（规格澄清 C-03）：封闭枚举外的值（包括 None 与类型不对）统一 → E_SCHEMA_FIELDS，
        field 指向该字段；原测试只断言“被拒绝”。"""
        for role in ("planner", "executor", "observer"):
            P.validate_role(role)
        self.assertIsNone(P.validate_role(None, allow_null=True))
        for role in ("Planner", "admin", "", None, "executor ", 1):
            with self.subTest(role=role):
                self.assertCode("E_SCHEMA_FIELDS", P.validate_role, role, expect_field="/role")
        for platform_name in ("linux", "macos", "windows"):
            P.validate_platform(platform_name)
        for platform_name in ("Linux", "darwin", "win32", "", None, 1):
            with self.subTest(platform=platform_name):
                self.assertCode("E_SCHEMA_FIELDS", P.validate_platform, platform_name,
                                expect_field="/platform")

    def test_A08_platform_from_system(self):
        """4.1.1：platform 由受信环境事实精确映射；未知系统显式不支持（E_COMPAT_UNSUPPORTED），不猜 linux。"""
        self.assertEqual(P.platform_from_system("Linux"), "linux")
        self.assertEqual(P.platform_from_system("Darwin"), "macos")
        self.assertEqual(P.platform_from_system("Windows"), "windows")
        for system in ("linux", "FreeBSD", "Java", "", "CYGWIN_NT-10.0", "Windows ", "AIX"):
            with self.subTest(system=system):
                self.assertCode("E_COMPAT_UNSUPPORTED", P.platform_from_system, system)


class RunContextTests(ProtocolTestCase):
    def test_A08_doc_sample_4_1_3_run_context(self):
        """4.1.3 样例逐字取出：通过 RunContext 结构校验，且不被修改。"""
        ctx = P.strict_json_loads(SAMPLE_RUN_CONTEXT.encode("utf-8"))
        before = copy.deepcopy(ctx)
        P.validate_run_context(ctx)
        self.assertUnchanged(before, ctx)

    def test_A08_run_context_closed_fields(self):
        """附录 A runContext：字段封闭；未知字段或缺字段 → E_SCHEMA_FIELDS。
        P2 调和（规格澄清 C-07）：直接调用记录校验函数时，与 route_public_record 相同，先查
        schema_version（缺失 → E_SCHEMA_VERSION_TYPE）和 record_type（缺失 → E_SCHEMA_RECORD_TYPE），
        再查字段封闭；同一输入经路由或直接校验得到同一个码。"""
        extra = make_context(approved=True)
        self.assertCode("E_SCHEMA_FIELDS", P.validate_run_context, extra, expect_field="/approved")
        for name in ("contract_ref", "attempt", "task_id", "platform"):
            ctx = make_context()
            del ctx[name]
            with self.subTest(missing=name):
                self.assertCode("E_SCHEMA_FIELDS", P.validate_run_context, ctx,
                                expect_field="/" + name)
        for name, code in (("schema_version", "E_SCHEMA_VERSION_TYPE"),
                           ("record_type", "E_SCHEMA_RECORD_TYPE")):
            ctx = make_context()
            del ctx[name]
            with self.subTest(missing=name):
                self.assertCode(code, P.validate_run_context, ctx)
                self.assertCode(code, P.route_public_record, ctx,
                                expected_record_type="run-context")

    def test_A08_run_context_field_rules(self):
        """4.1.1、附录 A：单字段故障分别拒绝（标识语法、整数类型与范围、枚举、引用形状）。"""
        self.assertCode("E_ID_SYNTAX", P.validate_run_context, make_context(request_id=REQ + "\n"))
        self.assertCode("E_ID_SYNTAX", P.validate_run_context, make_context(run_id="run-x"))
        self.assertCode("E_ID_SYNTAX", P.validate_run_context, make_context(task_id="Bad_Task"))
        self.assertCode("E_SCHEMA_TYPE", P.validate_run_context, make_context(plan_version="1"))
        self.assertCode("E_INTEGER_RANGE", P.validate_run_context, make_context(plan_version=0))
        self.assertCode("E_INTEGER_RANGE", P.validate_run_context, make_context(attempt=-1))
        self.assertCode("E_SCHEMA_TYPE", P.validate_run_context, make_context(attempt=True))
        # P2 调和（规格澄清 C-03）：枚举外的值固定为 E_SCHEMA_FIELDS（原为“被拒绝即可”）。
        self.assertCode("E_SCHEMA_FIELDS", P.validate_run_context, make_context(role="admin"),
                        expect_field="/role")
        self.assertCode("E_SCHEMA_FIELDS", P.validate_run_context, make_context(platform="Linux"),
                        expect_field="/platform")
        bad_ref = {**CONTRACT_REF, "sha256": CONTRACT_REF["sha256"].upper()}
        self.assertCode("E_RESOURCE_FIELD", P.validate_run_context, make_context(contract_ref=bad_ref),
                        expect_field="/contract_ref/sha256")
        P.validate_run_context(make_context(attempt=0, plan_version=1, platform="windows"))

    def test_A08_executor_dispatch_requires_binding_fields(self):
        """4.1.3：进入 executor 派遣前 task_id、plan_version、attempt、contract_ref 必须齐全
        → 否则 E_CONTEXT_INCOMPLETE；attempt=0 是非空值。"""
        complete = make_executor_context()
        P.validate_run_context(complete, for_executor_dispatch=True)
        P.validate_run_context(make_executor_context(attempt=0), for_executor_dispatch=True)
        for name in ("task_id", "plan_version", "attempt", "contract_ref"):
            with self.subTest(null=name):
                ctx = make_executor_context(**{name: None})
                P.validate_run_context(ctx)  # 结构上合法
                self.assertCode("E_CONTEXT_INCOMPLETE", P.validate_run_context, ctx,
                                for_executor_dispatch=True)
        self.assertCode("E_CONTEXT_INCOMPLETE", P.validate_run_context,
                        P.strict_json_loads(SAMPLE_RUN_CONTEXT.encode()),
                        for_executor_dispatch=True)

    def test_A08_executor_dispatch_requires_executor_role(self):
        """4.1.3“进入 executor 派遣前”：P4 新增（第 2 轮复审 fidelity 视角）。字段齐全的 planner 或
        observer 上下文不能通过 executor 派遣检查 → E_SCHEMA_FIELDS（field=/role，与 C-04 的 executor_retry
        父角色规则一致）；不要求派遣时结构上仍合法。"""
        for role in ("planner", "observer"):
            with self.subTest(role=role):
                ctx = make_executor_context(role=role)
                report = P.validate_run_context(ctx)
                self.assertIn("executor_dispatch_fields", report["semantic_checks_skipped"])
                exc = self.assertCode("E_SCHEMA_FIELDS", P.validate_run_context, ctx,
                                      for_executor_dispatch=True, expect_field="/role")
                self.assertEqual(exc.reason, "executor_dispatch_requires_executor_role")
        report = P.validate_run_context(make_executor_context(), for_executor_dispatch=True)
        self.assertIn("executor_dispatch_fields", report["semantic_checks"])

    def test_F022_reconnect_and_replay_keep_identity(self):
        """01-F022 / 4.1.2：重连查询与重放不新建 run：request、run、attempt 不变；parent 不被修改。"""
        parent = make_executor_context()
        before = copy.deepcopy(parent)
        for action in ("reconnect", "replay"):
            with self.subTest(action=action):
                derived = P.derive_run_context(parent, action)
                self.assertEqual(derived, parent)
                self.assertEqual(derived["run_id"], RUN)
                self.assertEqual(derived["attempt"], 1)
                # P2 返工（复审变异 M70）：返回的是深拷贝，改动派生结果不会连带改掉 parent。
                self.assertIsNot(derived, parent)
                self.assertIsNot(derived["contract_ref"], parent["contract_ref"])
                derived["contract_ref"]["path"] = "changed/by-caller.md"
        self.assertUnchanged(before, parent)

    def test_A08_derive_result_is_validated(self):
        """4.1.2、protocols-api.md 5.2：P2 返工新增（复审变异 M52）。派生结果须经 validate_run_context
        校验：参数带入非法值时报对应码，不返回非法上下文。"""
        parent = make_executor_context()
        self.assertCode("E_ID_SYNTAX", P.derive_run_context, parent, "new_goal",
                        new_task_id="Bad_Task", expect_field="/task_id")
        self.assertCode("E_INTEGER_RANGE", P.derive_run_context, parent, "new_goal",
                        new_plan_version=0, expect_field="/plan_version")
        self.assertCode("E_INTEGER_RANGE", P.derive_run_context, parent, "observer_call",
                        attempt=-1, expect_field="/attempt")
        bad_ref = {**CONTRACT_REF, "kind": "Bad"}
        self.assertCode("E_RESOURCE_FIELD", P.derive_run_context, parent, "rework_new_contract",
                        new_plan_version=2, contract_ref=bad_ref, expect_field="/contract_ref/kind")

    def test_F023_executor_retry_new_run_same_request(self):
        """01-F023 / 4.1.2：真正重试：request 保持（预算根不变），run 新建，attempt 取受信分配器给出的编号。
        P4（裁决 R-P2）：纯函数不再自行把 parent.attempt 加 1；调用方传入旧实现 allocate_attempt（将来由 07）
        分配的编号。它可以大于 parent.attempt（例如从非最新的 attempt 派生，旧规则是“已有最大值 + 1”），
        也可以等于 parent.attempt（同一 prepared attempt 在预检失败后再次 run，沿用原编号，01-D03）。"""
        parent = make_executor_context(attempt=1)
        before = copy.deepcopy(parent)
        for allocated in (2, 1, 5):
            with self.subTest(attempt=allocated):
                derived = P.derive_run_context(parent, "executor_retry", attempt=allocated)
                self.assertEqual(derived["request_id"], parent["request_id"])
                self.assertNotEqual(derived["run_id"], parent["run_id"])
                P.validate_run_id(derived["run_id"])
                self.assertEqual(derived["attempt"], allocated)
                for name in ("task_id", "plan_version", "contract_ref", "role", "platform"):
                    self.assertEqual(derived[name], parent[name])
                P.validate_run_context(derived, for_executor_dispatch=True)
        self.assertUnchanged(before, parent)

    def test_A08_executor_retry_requires_attempt(self):
        """4.1.2、01-D03：父上下文 attempt 未知时无法核对编号 → E_CONTEXT_INCOMPLETE。
        P4（裁决 R-P2）：未传入受信分配的 attempt → E_CONTEXT_INCOMPLETE（/attempt，reason 不同）；
        编号小于 parent.attempt（倒退）→ E_CONTEXT_BINDING（/attempt）；编号本身不合法按 validate_attempt
        报码（类型 E_SCHEMA_TYPE、负数 E_INTEGER_RANGE）。parent 都不被修改。"""
        exc = self.assertCode("E_CONTEXT_INCOMPLETE", P.derive_run_context,
                              make_executor_context(attempt=None), "executor_retry", attempt=1,
                              expect_field="/attempt")
        self.assertEqual(exc.reason, "retry_requires_attempt")
        parent = make_executor_context(attempt=3)
        before = copy.deepcopy(parent)
        exc = self.assertCode("E_CONTEXT_INCOMPLETE", P.derive_run_context, parent, "executor_retry",
                              expect_field="/attempt")
        self.assertEqual(exc.reason, "executor_retry_requires_allocated_attempt")
        for regressed in (2, 0):
            with self.subTest(attempt=regressed):
                exc = self.assertCode("E_CONTEXT_BINDING", P.derive_run_context, parent, "executor_retry",
                                      attempt=regressed, expect_field="/attempt")
                self.assertEqual(exc.reason, "retry_attempt_below_parent")
        for bad, code in (("4", "E_SCHEMA_TYPE"), (True, "E_SCHEMA_TYPE"), (4.0, "E_SCHEMA_TYPE"),
                          (-1, "E_INTEGER_RANGE")):
            with self.subTest(attempt=bad):
                self.assertCode(code, P.derive_run_context, parent, "executor_retry", attempt=bad,
                                expect_field="/attempt")
        self.assertUnchanged(before, parent)

    def test_A08_executor_retry_requires_executor_parent(self):
        """4.1.2“原执行失败后再次启动 executor”：P2 调和新增（规格澄清 C-04）。规格未写父上下文
        角色；按更严格的解释，只有 executor 运行才能派生 executor_retry，planner/observer 父上下文
        → E_SCHEMA_FIELDS（field=/role），不修改 parent。"""
        for role in ("planner", "observer"):
            with self.subTest(role=role):
                parent = make_executor_context(role=role)
                before = copy.deepcopy(parent)
                self.assertCode("E_SCHEMA_FIELDS", P.derive_run_context, parent, "executor_retry",
                                expect_field="/role")
                self.assertUnchanged(before, parent)

    def test_A08_derive_rejects_inapplicable_parameters(self):
        """4.1.2 表：P2 调和新增（规格澄清 C-04）。参数不适用于该动作时报 E_SCHEMA_FIELDS，
        不静默忽略；observer_call 只能得到 observer 角色；返工必须给出新的 plan_version
        （否则 E_CONTEXT_INCOMPLETE）。"""
        parent = make_executor_context()
        # P4（裁决 R-P2）：executor_retry 现在接受 attempt（受信分配的编号），其他参数仍不适用。
        for action, kwargs in (("reconnect", {"attempt": 3}), ("replay", {"role": "planner"}),
                               ("executor_retry", {"attempt": 5, "new_plan_version": 2}),
                               ("executor_retry", {"attempt": 5, "role": "executor"}),
                               ("executor_retry", {"attempt": 5, "new_task_id": "other-task"}),
                               ("observer_call", {"new_plan_version": 2}),
                               ("observer_call", {"role": "planner"})):
            with self.subTest(action=action, kwargs=kwargs):
                self.assertCode("E_SCHEMA_FIELDS", P.derive_run_context, parent, action, **kwargs)
        self.assertCode("E_CONTEXT_INCOMPLETE", P.derive_run_context, parent,
                        "rework_new_contract", contract_ref=copy.deepcopy(CONTRACT_REF),
                        expect_field="/plan_version")

    def test_A08_observer_rework_and_new_goal(self):
        """4.1.2 表：observer 调用保持 request、新 run、role=observer、attempt 取参数；
        返工新合同保持 request、新 run、换 plan_version/contract_ref；独立新目标新 request 与新 run。"""
        parent = make_executor_context()
        observer = P.derive_run_context(parent, "observer_call", attempt=None)
        self.assertEqual(observer["request_id"], REQ)
        self.assertNotEqual(observer["run_id"], RUN)
        self.assertEqual(observer["role"], "observer")
        self.assertIsNone(observer["attempt"])
        P.validate_run_context(observer)
        observer_bound = P.derive_run_context(parent, "observer_call", attempt=1)
        self.assertEqual(observer_bound["attempt"], 1)

        # P2 调和（规格澄清 C-04）：observer 调用不改任务、合同与平台绑定。
        for name in ("task_id", "plan_version", "contract_ref", "platform"):
            self.assertEqual(observer[name], parent[name])

        new_ref = {**CONTRACT_REF, "id": "contract-sample-2", "sha256": sha(b"v2\n")}
        rework = P.derive_run_context(parent, "rework_new_contract", new_plan_version=2,
                                      contract_ref=new_ref)
        self.assertEqual(rework["request_id"], REQ)
        self.assertNotEqual(rework["run_id"], RUN)
        self.assertEqual(rework["plan_version"], 2)
        self.assertEqual(rework["contract_ref"], new_ref)
        # 规格澄清 C-04：“沿用调度器规则”的 attempt 由调用方（07）给出，未给出时为 null，
        # 不从父上下文自动 +1；task_id、role、platform 未给新值时保持。
        self.assertIsNone(rework["attempt"])
        for name in ("task_id", "role", "platform"):
            self.assertEqual(rework[name], parent[name])
        self.assertEqual(P.derive_run_context(parent, "rework_new_contract", new_plan_version=2,
                                              contract_ref=new_ref, attempt=4)["attempt"], 4)
        P.validate_run_context(rework)

        goal = P.derive_run_context(parent, "new_goal", new_task_id="another-goal")
        self.assertNotEqual(goal["request_id"], REQ)
        P.validate_request_id(goal["request_id"])
        self.assertNotEqual(goal["run_id"], RUN)
        # 规格澄清 C-04：独立新目标的任务、合同、版本与尝试序号都取参数（未给出即 null）。
        self.assertEqual(goal["task_id"], "another-goal")
        for name in ("plan_version", "contract_ref", "attempt"):
            self.assertIsNone(goal[name])
        P.validate_run_context(goal)
        self.assertEqual(len({RUN, observer["run_id"], rework["run_id"], goal["run_id"]}), 4)

    def test_A08_derive_validates_parent_first(self):
        """4.1.2、protocols-api.md 5.2：P4 新增（第 2 轮复审 tests-mutation Q045）。派生前先校验 parent：非法
        parent 对每个动作都得到与 validate_run_context 相同的错误码与 field，reconnect/replay 也不例外
        （否则会原样返回非法上下文）。"""
        no_platform = make_executor_context()
        del no_platform["platform"]
        parents = [(make_executor_context(run_id="run-XYZ"), "E_ID_SYNTAX", "/run_id"),
                   (no_platform, "E_SCHEMA_FIELDS", "/platform")]
        kwargs = {"executor_retry": {"attempt": 2}, "rework_new_contract": {"new_plan_version": 2}}
        for parent, code, pointer in parents:
            self.assertCode(code, P.validate_run_context, parent, expect_field=pointer)
            for action in P.DERIVE_ACTIONS:
                with self.subTest(action=action, field=pointer):
                    self.assertCode(code, P.derive_run_context, parent, action,
                                    expect_field=pointer, **kwargs.get(action, {}))

    def test_A08_derive_validates_contract_ref_before_copy(self):
        """4.1.2、F012、protocols-api.md 5.2：P4 第 3 轮新增（复审 json 视角）。derive_run_context 先校验、再拷贝
        contract_ref：过深（5000 层、100000 层）、含不可拷贝对象（Lock、生成器）或 dict 子类的参数，与把同一个
        contract_ref 放进上下文直接调用 validate_run_context 得到同一个码与 field（E_JSON_LIMIT /
        E_JSON_VALUE_TYPE），不漏出 RecursionError/TypeError；调用方对象的 __deepcopy__ 在校验前不被执行。
        合法的 contract_ref 被拷贝，返回值不与调用方对象共享。"""
        import threading

        deepcopy_calls = []

        class RefDict(dict):
            def __deepcopy__(self, memo):
                deepcopy_calls.append(1)
                return dict(self)

        def generator():
            yield 1

        parent = make_executor_context()
        bad_refs = {
            "nested-5000": {**CONTRACT_REF, "x": nested_list(5000)},
            "nested-100000": {**CONTRACT_REF, "x": nested_list(100_000)},
            "lock": {**CONTRACT_REF, "x": threading.Lock()},
            "generator": {**CONTRACT_REF, "x": generator()},
            "dict-subclass": RefDict(CONTRACT_REF),
        }
        actions = (("new_goal", {}), ("rework_new_contract", {"new_plan_version": 2}))
        for name, bad in bad_refs.items():
            direct = {**parent, "contract_ref": bad}
            with self.assertRaises(P.ProtocolError) as caught:
                P.validate_run_context(direct)
            expected = (caught.exception.code, caught.exception.field)
            self.assertIn(expected[0], ("E_JSON_LIMIT", "E_JSON_VALUE_TYPE"))
            for action, kwargs in actions:
                with self.subTest(contract_ref=name, action=action):
                    self.assertCode(expected[0], P.derive_run_context, parent, action, contract_ref=bad,
                                    expect_field=expected[1], **kwargs)
        self.assertEqual(deepcopy_calls, [], "校验前不得执行调用方对象的 __deepcopy__")
        ref = copy.deepcopy(CONTRACT_REF)
        for action, kwargs in actions:
            with self.subTest(valid_action=action):
                child = P.derive_run_context(parent, action, contract_ref=ref, **kwargs)
                self.assertEqual(child["contract_ref"], ref)
                self.assertIsNot(child["contract_ref"], ref)
                self.assertIs(type(child["contract_ref"]), dict)

    def test_A08_unknown_derive_action(self):
        """4.1.2：未登记的派生动作 → E_SCHEMA_FIELDS（不猜为重试或重连）。"""
        for action in ("retry", "RECONNECT", "", "http_retry"):
            with self.subTest(action=action):
                self.assertCode("E_SCHEMA_FIELDS", P.derive_run_context, make_context(), action)


# ===========================================================================
# Schema 路由（1.3、4.4.2、A.2；01-F013、F014，01-A09）
# ===========================================================================
class SchemaRoutingTests(ProtocolTestCase):
    def test_F013_schema_version_type(self):
        """01-F013：schema_version 为 true、"1"、1.0、null 或缺失 → E_SCHEMA_VERSION_TYPE，不当整数版本。
        P2 调和（规格澄清 C-07）：0 与负数沿用附录 B.2 参考实现（version < 1）→ E_SCHEMA_VERSION_TYPE；
        只有 ≥1 的精确整数才进入“是否受支持”的判断。"""
        for value in (True, "1", 1.0, None, 0, -1):
            with self.subTest(value=value):
                self.assertCode("E_SCHEMA_VERSION_TYPE", P.route_public_record,
                                make_context(schema_version=value),
                                expected_record_type="run-context")
        ctx = make_context()
        del ctx["schema_version"]
        self.assertCode("E_SCHEMA_VERSION_TYPE", P.route_public_record, ctx,
                        expected_record_type="run-context")

    def test_F013_require_schema_version_reference_behavior(self):
        """附录 B.2/B.3（保留参考实现行为）：True、"1"、1.0、0、None → E_SCHEMA_VERSION_TYPE；
        未支持的版本 → E_SCHEMA_VERSION_UNSUPPORTED。"""
        for value in (True, "1", 1.0, 0, None):
            with self.subTest(value=value):
                self.assertCode("E_SCHEMA_VERSION_TYPE", P.require_schema_version,
                                {"schema_version": value}, {1})
        self.assertEqual(P.require_schema_version({"schema_version": 1}, {1}), 1)
        self.assertCode("E_SCHEMA_VERSION_UNSUPPORTED", P.require_schema_version,
                        {"schema_version": 2}, {1})

    def test_F014_unknown_version_no_legacy_fallback(self):
        """01-F014 / 4.4.2、01-A09：未知新版本 → E_SCHEMA_VERSION_UNSUPPORTED；不删字段回退 v1，
        带新字段的 v2 记录也不会被“降级”成 v1 通过；输入不被修改。"""
        v2 = make_context(schema_version=2)
        v2_with_field = make_context(schema_version=2, new_v2_field={"x": 1})
        for value in (v2, v2_with_field):
            before = copy.deepcopy(value)
            self.assertCode("E_SCHEMA_VERSION_UNSUPPORTED", P.route_public_record, value,
                            expected_record_type="run-context")
            self.assertCode("E_SCHEMA_VERSION_UNSUPPORTED", P.validate_public_record, value,
                            expected_record_type="run-context", registry=self.reg)
            self.assertUnchanged(before, value)

    def test_A09_route_positive(self):
        """1.3：受信入口声明的记录类型 + 家族版本一致时返回版本 1。"""
        self.assertEqual(P.route_public_record(make_context(), expected_record_type="run-context"), 1)
        self.assertEqual(P.route_public_record(make_event(), expected_record_type="run-event"), 1)
        usage = json.loads(SAMPLE_USAGE)
        self.assertEqual(P.route_public_record(usage, expected_record_type="usage-observation"), 1)

    def test_A09_route_expected_type_and_record_type(self):
        """1.3：受信入口的期望类型不在公共记录类型中 → E_COMPAT_UNSUPPORTED；值非对象 → E_SCHEMA_TYPE；
        record_type 与期望不同（含缺失）→ E_SCHEMA_RECORD_TYPE（不能只看 schema_version 就分派）。"""
        for expected in ("contract", "fixture-manifest", "RUN-CONTEXT", "error"):
            with self.subTest(expected=expected):
                self.assertCode("E_COMPAT_UNSUPPORTED", P.route_public_record, make_context(),
                                expected_record_type=expected)
        for value in ([], "run-context", None, 1):
            with self.subTest(value=value):
                self.assertCode("E_SCHEMA_TYPE", P.route_public_record, value,
                                expected_record_type="run-context")
        self.assertCode("E_SCHEMA_RECORD_TYPE", P.route_public_record, make_event(),
                        expected_record_type="run-context")
        self.assertCode("E_SCHEMA_RECORD_TYPE", P.route_public_record, make_context(),
                        expected_record_type="usage-observation")
        ctx = make_context()
        del ctx["record_type"]
        self.assertCode("E_SCHEMA_RECORD_TYPE", P.route_public_record, ctx,
                        expected_record_type="run-context")

    def test_A09_validate_public_record_reports_checks_honestly(self):
        """A.2 末段：返回值声明结构校验已做，并如实列出执行过的语义检查；
        未提供事件类型注册表时 payload_validated=False；提供上下文与类型后执行的检查更多。"""
        ev = make_event()
        bare = P.validate_public_record(ev, expected_record_type="run-event", registry=self.reg)
        self.assertEqual(bare["record_type"], "run-event")
        self.assertEqual(bare["schema_version"], 1)
        self.assertIs(bare["structural"], True)
        self.assertIs(bare["payload_validated"], False)
        self.assertIsInstance(bare["semantic_checks"], list)
        self.assertTrue(all(isinstance(x, str) for x in bare["semantic_checks"]))
        full = P.validate_public_record(ev, expected_record_type="run-event", registry=self.reg,
                                        context=make_context(),
                                        event_types=P.build_default_event_types(),
                                        segment_sizes={})
        self.assertIs(full["payload_validated"], True)
        self.assertGreater(len(full["semantic_checks"]), len(bare["semantic_checks"]))
        # P2 调和（规格澄清 C-08）：报告另有 semantic_checks_skipped，逐项写明没做的检查；
        # 同一检查不会同时出现在两边。
        for report in (bare, full):
            self.assertEqual(set(report["semantic_checks"]) & set(report["semantic_checks_skipped"]),
                             set())
        for name in ("context_binding", "event_type_registered", "payload_validator"):
            self.assertIn(name, bare["semantic_checks_skipped"])
            self.assertIn(name, full["semantic_checks"])
        for name in ("seq_continuity", "core_event_claims"):
            self.assertIn(name, full["semantic_checks_skipped"])

    def test_A09_validate_public_record_passes_registry(self):
        """protocols-api.md 6.2、18.2：P2 返工新增（复审变异 M90/M102，major）。公共入口把 registry 传给
        run-context 的 contract_ref 与 usage 的 evidence_refs：未登记 kind 经 validate_public_record
        一律 E_RESOURCE_KIND，并指向具体字段；已登记时报告 resource_kind_registered。"""
        unregistered = {**CONTRACT_REF, "kind": "plugin-lock"}
        ctx = make_executor_context(contract_ref=unregistered)
        self.assertCode("E_RESOURCE_KIND", P.validate_public_record, ctx,
                        expected_record_type="run-context", registry=self.reg,
                        expect_field="/contract_ref/kind")
        usage = make_usage(evidence_refs=[copy.deepcopy(unregistered)])
        self.assertCode("E_RESOURCE_KIND", P.validate_public_record, usage,
                        expected_record_type="usage-observation", registry=self.reg,
                        expect_field="/evidence_refs/0/kind")
        ok_ctx = P.validate_public_record(make_executor_context(), expected_record_type="run-context",
                                          registry=self.reg)
        ok_usage = P.validate_public_record(make_usage(evidence_refs=[copy.deepcopy(CONTRACT_REF)]),
                                            expected_record_type="usage-observation",
                                            registry=self.reg)
        for report in (ok_ctx, ok_usage):
            self.assertIn("resource_kind_registered", report["semantic_checks"])
            self.assertNotIn("resource_kind_registered", report["semantic_checks_skipped"])

    def test_A09_validate_public_record_rejects_inapplicable_parameters(self):
        """A.2“诚实声明”：P2 返工新增（复审 fidelity 视角）。不适用于该记录类型的参数给了非 None 值时
        E_SCHEMA_FIELDS（reason=parameter_not_applicable），不静默忽略（与 derive_run_context 一致）。"""
        types = P.build_default_event_types()
        cases = [(make_context(), "run-context", {"context": make_context()}),
                 (make_context(), "run-context", {"event_types": types}),
                 (make_context(), "run-context", {"segment_sizes": {}}),
                 (make_usage(), "usage-observation", {"event_types": types}),
                 (make_usage(), "usage-observation", {"segment_sizes": {}})]
        for value, record_type, kwargs in cases:
            with self.subTest(record_type=record_type, parameter=sorted(kwargs)):
                exc = self.assertCode("E_SCHEMA_FIELDS", P.validate_public_record, value,
                                      expected_record_type=record_type, registry=self.reg, **kwargs)
                self.assertEqual(exc.reason, "parameter_not_applicable")
        report = P.validate_public_record(make_usage(), expected_record_type="usage-observation",
                                          registry=self.reg, context=make_context())
        self.assertIn("context_binding", report["semantic_checks"])

    def test_A09_record_type_must_be_exact_str(self):
        """4.4.2、A.2：P2 返工新增（复审 json 视角）。record_type 为 str 子类时，路由按类型不符报
        E_SCHEMA_RECORD_TYPE；记录校验先做整条记录的 JSON 原生值检查 → E_JSON_VALUE_TYPE
        （与 stable_snapshot_bytes 的判断一致，不会出现“校验通过、快照拒绝”）。"""

        class Str(str):
            pass

        self.assertCode("E_SCHEMA_RECORD_TYPE", P.route_public_record,
                        make_context(record_type=Str("run-context")), expected_record_type="run-context")
        for value, validator, record_type in (
                (make_context(record_type=Str("run-context")), P.validate_run_context, "run-context"),
                (make_event(record_type=Str("run-event")),
                 lambda v: P.validate_run_event(v, registry=self.reg), "run-event"),
                (make_usage(record_type=Str("usage-observation")), P.validate_usage_observation,
                 "usage-observation")):
            with self.subTest(record_type=value["record_type"]):
                self.assertCode("E_JSON_VALUE_TYPE", validator, value, expect_field="/record_type")
                self.assertCode("E_JSON_VALUE_TYPE", P.stable_snapshot_bytes, value)
                # P4（C-07）：受信入口 validate_public_record 与直接校验先做同样的 JSON 原生值检查，码相同。
                self.assertCode("E_JSON_VALUE_TYPE", P.validate_public_record, value,
                                expected_record_type=record_type, registry=self.reg,
                                expect_field="/record_type")

    def test_A09_public_entry_and_direct_validators_agree(self):
        """7.4“单一故障输入返回稳定错误码”、C-07：P4 新增（第 2 轮复审 fidelity/json 视角）。记录头字段的
        单一故障（整数越界、非有限数、孤立代理项、int/str 子类）经 validate_public_record 与直接调用
        validate_run_context / validate_run_event / validate_usage_observation 得到同一个码与 field；
        raw_refs 区间单独调用 validate_raw_span 与嵌在事件中时也得到同一个码。"""

        class Level(enum.IntEnum):
            ONE = 1

        faults = [({"schema_version": 2**60}, "E_INTEGER_RANGE", "/schema_version"),
                  ({"schema_version": 2**53}, "E_INTEGER_RANGE", "/schema_version"),
                  ({"schema_version": float("nan")}, "E_JSON_NON_FINITE", "/schema_version"),
                  ({"schema_version": float("inf")}, "E_JSON_NON_FINITE", "/schema_version"),
                  ({"schema_version": Level.ONE}, "E_JSON_VALUE_TYPE", "/schema_version"),
                  ({"record_type": "x\ud800"}, "E_JSON_UNICODE", "/record_type")]
        records = (("run-context", make_context, P.validate_run_context),
                   ("run-event", make_event, lambda v: P.validate_run_event(v, registry=self.reg)),
                   ("usage-observation", make_usage, P.validate_usage_observation))
        for record_type, factory, direct in records:
            for change, code, pointer in faults:
                with self.subTest(record_type=record_type, change=repr(change)):
                    value = factory(**change)
                    self.assertCode(code, direct, value, expect_field=pointer)
                    self.assertCode(code, P.validate_public_record, value, expected_record_type=record_type,
                                    registry=self.reg, expect_field=pointer)
        # 区间：单独调用与嵌在事件中都先做 JSON 原生值检查（字段指针按各自的根计算）。
        span = make_span(end=2**60)
        self.assertCode("E_INTEGER_RANGE", P.validate_raw_span, span, registry=self.reg,
                        expect_field="/byte_end")
        self.assertCode("E_INTEGER_RANGE", P.validate_run_event, make_vendor_event(raw_refs=[span]),
                        registry=self.reg, expect_field="/raw_refs/0/byte_end")
        # 在 JSON 原生值范围内的越界仍按区间规则报 E_EVENT_RAW_RANGE，两处一致。
        span = make_span(start=5, end=5)
        self.assertCode("E_EVENT_RAW_RANGE", P.validate_raw_span, span, registry=self.reg,
                        expect_field="/byte_end")
        self.assertCode("E_EVENT_RAW_RANGE", P.validate_run_event, make_vendor_event(raw_refs=[span]),
                        registry=self.reg, expect_field="/raw_refs/0/byte_end")

    def test_A09_validate_public_record_doc_samples(self):
        """4.1.3、4.3.1、4.3.9 样例经受信入口分派后通过对应校验。"""
        cases = [(SAMPLE_RUN_CONTEXT, "run-context"), (SAMPLE_RUN_EVENT, "run-event"),
                 (SAMPLE_USAGE, "usage-observation")]
        for text, record_type in cases:
            with self.subTest(record_type=record_type):
                value = P.strict_json_loads(text.encode("utf-8"))
                result = P.validate_public_record(value, expected_record_type=record_type,
                                                  registry=self.reg)
                self.assertEqual(result["record_type"], record_type)
                self.assertIs(result["structural"], True)
                self.assertIs(type(result["payload_validated"]), bool)


# ===========================================================================
# Schema 文件一致性（附录 A、A.2、E.2；01-A09）
# ===========================================================================
class SchemaFileTests(ProtocolTestCase):
    def _structural_negatives(self):
        """每项：(Schema 定义名, 实例, 用 protocols 校验的函数, 稳定错误码)。实例都从有效样本只改一处。
        P2 调和（规格澄清 C-03、7.4）：原测试只要求 protocols“拒绝”；现逐项固定错误码。"""
        reg = self.reg
        v_ctx = P.validate_run_context
        v_ev = lambda v: P.validate_run_event(v, registry=reg)  # noqa: E731
        v_usage = P.validate_usage_observation
        v_ref = lambda v: P.validate_resource_ref(v, reg)  # noqa: E731
        items = []

        def ctx_without(name):
            c = make_context()
            del c[name]
            return c

        items += [("runContext", make_context(approved=True), v_ctx, "E_SCHEMA_FIELDS"),
                  ("runContext", ctx_without("contract_ref"), v_ctx, "E_SCHEMA_FIELDS"),
                  ("runContext", make_context(request_id=REQ + "\n"), v_ctx, "E_ID_SYNTAX"),
                  ("runContext", make_context(request_id="req-" + "A" * 32), v_ctx, "E_ID_SYNTAX"),
                  ("runContext", make_context(task_id="Bad_Task"), v_ctx, "E_ID_SYNTAX"),
                  ("runContext", make_context(plan_version=0), v_ctx, "E_INTEGER_RANGE"),
                  ("runContext", make_context(attempt=-1), v_ctx, "E_INTEGER_RANGE"),
                  ("runContext", make_context(role="admin"), v_ctx, "E_SCHEMA_FIELDS"),
                  ("runContext", make_context(platform="Linux"), v_ctx, "E_SCHEMA_FIELDS"),
                  ("runContext", make_context(record_type="run-event"), v_ctx,
                   "E_SCHEMA_RECORD_TYPE"),
                  ("runContext", make_context(schema_version=2), v_ctx,
                   "E_SCHEMA_VERSION_UNSUPPORTED"),
                  ("runContext", make_context(contract_ref={**CONTRACT_REF, "sha256": "A" * 64}),
                   v_ctx, "E_RESOURCE_FIELD")]

        def ev_without(name):
            e = make_event()
            del e[name]
            return e

        items += [("event", make_event(seq=0), v_ev, "E_INTEGER_RANGE"),
                  ("event", make_event(seq="1"), v_ev, "E_SCHEMA_TYPE"),
                  ("event", make_event(observed_at="2026-09-25T00:00:00Z"), v_ev, "E_TIME_FORMAT"),
                  ("event", make_event(source_kind="model"), v_ev, "E_SCHEMA_FIELDS"),
                  ("event", make_event(integrity="done"), v_ev, "E_SCHEMA_FIELDS"),
                  ("event", make_event(role="admin"), v_ev, "E_SCHEMA_FIELDS"),
                  ("event", make_event(type=""), v_ev, "E_SCHEMA_FIELDS"),
                  ("event", make_event(type="x" * 97), v_ev, "E_SCHEMA_FIELDS"),
                  ("event", make_event(adapter_revision=""), v_ev, "E_SCHEMA_FIELDS"),
                  ("event", make_event(adapter_revision="x" * 129), v_ev, "E_SCHEMA_FIELDS"),
                  ("event", make_event(raw_refs=[make_span()] * 257), v_ev, "E_SCHEMA_FIELDS"),
                  ("event", make_event(extra=1), v_ev, "E_SCHEMA_FIELDS"),
                  ("event", ev_without("payload"), v_ev, "E_SCHEMA_FIELDS"),
                  ("event", make_event(payload=[]), v_ev, "E_SCHEMA_TYPE"),
                  ("event", make_event(raw_refs=[{**make_span(), "extra": 1}]), v_ev,
                   "E_SCHEMA_FIELDS"),
                  ("event", make_event(raw_refs=[make_span(stream="stdin")]), v_ev,
                   "E_SCHEMA_FIELDS"),
                  ("event", make_event(raw_refs=[make_span(start=0, end=0)]), v_ev,
                   "E_EVENT_RAW_RANGE")]

        def usage_without(name):
            u = make_usage()
            del u[name]
            return u

        items += [("usage", make_usage(reported_cost={"amount": "1e3", "currency": "USD"}), v_usage,
                   "E_USAGE_VALUE"),
                  ("usage", make_usage(reported_cost={"amount": "-1", "currency": "USD"}), v_usage,
                   "E_USAGE_VALUE"),
                  ("usage", make_usage(reported_cost={"amount": "1,000", "currency": "USD"}),
                   v_usage, "E_USAGE_VALUE"),
                  ("usage", make_usage(reported_cost={"amount": "01", "currency": "USD"}), v_usage,
                   "E_USAGE_VALUE"),
                  ("usage", make_usage(reported_cost={"amount": "1.0", "currency": "usd"}), v_usage,
                   "E_USAGE_VALUE"),
                  ("usage", make_usage(input_tokens=-1), v_usage, "E_INTEGER_RANGE"),
                  ("usage", make_usage(billing_source="free"), v_usage, "E_SCHEMA_FIELDS"),
                  ("usage", make_usage(observation_kind="total"), v_usage, "E_SCHEMA_FIELDS"),
                  ("usage", make_usage(extra=1), v_usage, "E_SCHEMA_FIELDS"),
                  ("usage", usage_without("evidence_refs"), v_usage, "E_SCHEMA_FIELDS"),
                  ("usage", make_usage(provider=""), v_usage, "E_SCHEMA_FIELDS"),
                  ("usage", make_usage(usage_id="Bad ID"), v_usage, "E_ID_SYNTAX"),
                  ("usage", make_usage(input_tokens=None, unknown_reasons={"input_tokens": ""}),
                   v_usage, "E_USAGE_UNKNOWN_REASON"),
                  # P2 返工（复审变异 M67）：evidence_refs 同样最多 256 条（C-03）。
                  ("usage", make_usage(evidence_refs=[json.loads(SAMPLE_RESOURCE_REF)] * 257),
                   v_usage, "E_SCHEMA_FIELDS")]

        ref = json.loads(SAMPLE_RESOURCE_REF)

        def ref_with(**kw):
            r = dict(ref)
            r.update(kw)
            return r

        def ref_without(name):
            r = dict(ref)
            del r[name]
            return r

        items += [("resourceRef", ref_with(sha256=ref["sha256"].upper()), v_ref, "E_RESOURCE_FIELD"),
                  ("resourceRef", ref_with(sha256="sha256:" + ref["sha256"]), v_ref,
                   "E_RESOURCE_FIELD"),
                  ("resourceRef", ref_with(sha256=ref["sha256"][:63]), v_ref, "E_RESOURCE_FIELD"),
                  ("resourceRef", ref_with(sha256=ref["sha256"] + "\n"), v_ref, "E_RESOURCE_FIELD"),
                  ("resourceRef", ref_with(extra=True), v_ref, "E_SCHEMA_FIELDS"),
                  ("resourceRef", ref_without("id"), v_ref, "E_SCHEMA_FIELDS"),
                  ("resourceRef", ref_with(kind="Fixture"), v_ref, "E_RESOURCE_FIELD"),
                  ("resourceRef", ref_with(id="-bad"), v_ref, "E_RESOURCE_FIELD"),
                  ("resourceRef", ref_with(path=""), v_ref, "E_PATH_SYNTAX")]
        return items

    def test_A09_schema_file_digest(self):
        """附录 E.2、01-L02：本地 Schema 字节摘要等于附录 A 抽取结果。"""
        self.assertEqual(sha(SCHEMA_BYTES), SCHEMA_SHA256)

    def test_A09_schema_parses_strictly(self):
        """4.2.7、A.1：Schema 文件本身能通过严格 JSON 解析，$id 与协议常量一致。"""
        parsed = P.strict_json_loads(SCHEMA_BYTES)
        self.assertEqual(parsed, SCHEMA)
        self.assertEqual(parsed["$id"], P.SCHEMA_ID)
        self.assertEqual(parsed["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_A09_schema_refs_local_only(self):
        """A.1、4.4.3：所有 $ref 都是本地 #/$defs/ 且能解析；没有远程引用或动态引用；
        所用关键字都在迷你校验器覆盖范围内（format 只作注解）。"""
        refs = []

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "$ref":
                        refs.append(value)
                    self.assertNotIn(key, ("$dynamicRef", "$recursiveRef", "$anchor",
                                           "$dynamicAnchor"))
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(SCHEMA)
        self.assertTrue(refs)
        for ref in refs:
            with self.subTest(ref=ref):
                self.assertTrue(ref.startswith("#/$defs/"), ref)
                self.assertNotRegex(ref, r"(?i)^(https?|urn|file):")
                MINI.resolve(ref)
        used = set()
        for sub in iter_subschemas(SCHEMA):
            used |= set(sub)
        self.assertEqual(used - MINI.SUPPORTED - MINI.ANNOTATIONS, set())

    def test_A09_mini_validator_accepts_doc_samples(self):
        """A.1、E.1：五个文档样例通过迷你校验器（根 oneOf 恰好命中一个定义，也通过对应定义）。"""
        expected_def = {"4.1.3 RunContext": "runContext", "4.2.2 ResourceRef": "resourceRef",
                        "4.3.1 run-event": "event", "4.3.6 error": "error",
                        "4.3.9 usage": "usage"}
        for name, text in DOC_SAMPLES.items():
            with self.subTest(sample=name):
                value = json.loads(text)
                self.assertEqual(MINI.errors(value, SCHEMA), [])
                self.assertEqual(MINI.errors_for_def(value, expected_def[name]), [])

    def test_A09_mini_validator_and_protocols_agree_on_structure(self):
        """A.1/A.2、7.4：正例两者都接受；从有效样本只改一处的结构负例，迷你校验器与 protocols 都拒绝。"""
        P.validate_run_context(json.loads(SAMPLE_RUN_CONTEXT))
        P.validate_run_event(json.loads(SAMPLE_RUN_EVENT), registry=self.reg)
        P.validate_usage_observation(json.loads(SAMPLE_USAGE))
        P.validate_resource_ref(json.loads(SAMPLE_RESOURCE_REF), self.reg)
        self.assertEqual(MINI.errors_for_def(make_usage(), "usage"), [])
        P.validate_usage_observation(make_usage())
        self.assertEqual(MINI.errors_for_def(make_vendor_event(), "event"), [])
        P.validate_run_event(make_vendor_event(), registry=self.reg)
        for def_name, instance, validator, code in self._structural_negatives():
            with self.subTest(def_name=def_name, instance=repr(instance)[:160]):
                self.assertNotEqual(MINI.errors_for_def(instance, def_name), [],
                                    "迷你校验器应拒绝该结构负例")
                self.assertCode(code, validator, instance)

    def test_A09_schema_gaps_need_semantic_checks(self):
        """A.2：以下输入能通过结构 Schema（JSON Schema 把 1.0 视为整数、format 只是注解、
        unknown_reasons 键开放、kind 注册与 path 词法不在 Schema 内），但 protocols 必须拒绝——
        Schema 通过不等于领域检查通过。"""
        reg = self.reg
        gaps = [
            ("runContext", make_context(schema_version=1.0),
             lambda v: P.validate_public_record(v, expected_record_type="run-context",
                                                registry=reg), "E_SCHEMA_VERSION_TYPE"),
            # P2 调和（规格澄清 C-09）：1.0 是 float，按 require_int → E_SCHEMA_TYPE（原为“被拒绝即可”）。
            ("event", make_event(seq=1.0),
             lambda v: P.validate_run_event(v, registry=reg), "E_SCHEMA_TYPE"),
            ("event", make_event(observed_at="2026-02-30T00:00:00.000000Z"),
             lambda v: P.validate_run_event(v, registry=reg), "E_TIME_FORMAT"),
            ("event", make_vendor_event(raw_refs=[]),
             lambda v: P.validate_run_event(v, registry=reg), "E_EVENT_EVIDENCE_MISSING"),
            ("usage", make_usage(input_tokens=100.0), P.validate_usage_observation, "E_SCHEMA_TYPE"),
            ("usage", make_usage(unknown_reasons={"budget_override": "x"}),
             P.validate_usage_observation, "E_USAGE_UNKNOWN_REASON"),
            ("runContext", make_executor_context(attempt=None),
             lambda v: P.validate_run_context(v, for_executor_dispatch=True),
             "E_CONTEXT_INCOMPLETE"),
            ("resourceRef", {**json.loads(SAMPLE_RESOURCE_REF), "kind": "plugin-lock"},
             lambda v: P.validate_resource_ref(v, reg), "E_RESOURCE_KIND"),
            ("resourceRef", {**json.loads(SAMPLE_RESOURCE_REF), "path": "../x"},
             lambda v: P.validate_resource_ref(v, reg), "E_PATH_SYNTAX"),
            # P4：裁决 R-P3、R-P4、R-P7 与 executor 派遣的角色规则也都是 Schema 之外的领域检查。
            ("resourceRef", {**json.loads(SAMPLE_RESOURCE_REF), "path": "tests/AGENTS~1.MD"},
             lambda v: P.validate_resource_ref(v, reg), "E_PATH_RESERVED"),
            ("resourceRef", {**json.loads(SAMPLE_RESOURCE_REF), "path": "tests/a b.json"},
             lambda v: P.validate_resource_ref(v, reg), "E_PATH_SYNTAX"),
            ("resourceRef", {**json.loads(SAMPLE_RESOURCE_REF), "path": "tests/‮b.json"},
             lambda v: P.validate_resource_ref(v, reg), "E_PATH_SYNTAX"),
            ("event", make_vendor_event(raw_refs=[make_span(ref={**make_segment_ref(), "kind": "fixture"})]),
             lambda v: P.validate_run_event(v, registry=reg), "E_RESOURCE_KIND"),
            ("runContext", make_executor_context(role="planner"),
             lambda v: P.validate_run_context(v, for_executor_dispatch=True), "E_SCHEMA_FIELDS"),
            # P4 第 3 轮：只有核心事件的 role 可以为 null（4.3.1），vendor 事件 role=null 是领域检查。
            ("event", make_vendor_event(role=None),
             lambda v: P.validate_run_event(v, registry=reg), "E_SCHEMA_FIELDS"),
        ]
        no_path = json.loads(SAMPLE_RESOURCE_REF)
        del no_path["path"]
        gaps.append(("resourceRef", no_path, lambda v: P.validate_resource_ref(v, reg),
                     "E_RESOURCE_PATH_REQUIRED"))
        for def_name, instance, validator, code in gaps:
            with self.subTest(def_name=def_name, instance=repr(instance)[:160]):
                self.assertEqual(MINI.errors_for_def(instance, def_name), [])
                self.assertCode(code, validator, instance)

    def test_A09_record_strings_reject_lone_surrogates(self):
        """protocols-api.md 18.4、C-17：P2 返工新增（复审变异 M105）。记录字符串字段中的孤立代理项
        → E_JSON_UNICODE，field 指向该字段（Schema 的 string 类型拦不住，属于领域检查）。"""
        cases = [(make_event(type="a\ud800"), lambda v: P.validate_run_event(v, registry=self.reg),
                  "/type"),
                 (make_usage(provider="p\udc00"), P.validate_usage_observation, "/provider"),
                 (make_context(task_id="a\ud800"), P.validate_run_context, "/task_id")]
        for value, validator, pointer in cases:
            with self.subTest(pointer=pointer):
                self.assertCode("E_JSON_UNICODE", validator, value, expect_field=pointer)

    def test_A09_jsonschema_metaschema_optional(self):
        """E.1（可选）：若本机装有 jsonschema，则做 Draft 2020-12 元校验并用它验证文档样例。"""
        try:
            import jsonschema  # noqa: F401
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("未安装 jsonschema，未做元校验（本机不得安装依赖，见 01-L01）")
        Draft202012Validator.check_schema(SCHEMA)
        validator = Draft202012Validator(SCHEMA)
        for name, text in DOC_SAMPLES.items():
            with self.subTest(sample=name):
                validator.validate(json.loads(text))

    def test_A09_doc_samples_are_verbatim(self):
        """E.1：测试中使用的五个样例与设计文档代码块逐字一致（防止样例漂移）。"""
        docs = sorted(DOC_DIR.glob("01-baseline-and-protocols-*.md"))
        if not docs:
            self.skipTest("未找到 01 设计文档，无法核对样例逐字一致")
        text = docs[0].read_bytes().decode("utf-8").replace("\r\n", "\n")
        blocks = re.findall(r"```json\n(.*?)```", text, re.S)
        for name, sample in DOC_SAMPLES.items():
            with self.subTest(sample=name):
                self.assertIn(sample, blocks)


# ===========================================================================
# 业务路径（4.1.5–4.1.7；01-F024–F028，01-A10）
# ===========================================================================
class BusinessPathTests(ProtocolTestCase):
    def test_A10_valid_paths_returned_unchanged(self):
        """4.1.5：合法词法路径原样返回，不归一化、不解码、不展开 ~ 或环境变量。"""
        long_ok = "/".join(["a" * 255] * 15 + ["b" * 200, "c" * 55])
        self.assertEqual(len(long_ok.encode("utf-8")), 4096)
        values = ["src/main.py", "文档/说明.md", ".config/profile.json", "a/b/c.txt",
                  "cafe\u0301.txt", "%2e%2e/x", "~/notes.txt", "$HOME/x", "文" * 85,
                  long_ok, "CONSOLE.txt", "NULL.txt", "COM10.log", "LPT", "aux-notes.md",
                  "com1x.txt", "my-NUL.txt", "COM\u2074.log", "CON_old/file.txt"]
        for value in values:
            with self.subTest(value=value[:40]):
                result = P.validate_business_path(value)
                self.assertEqual(result, value)
                self.assertIs(type(result), str)

    def test_F024_absolute_drive_unc_backslash(self):
        """01-F024 / 4.1.5：绝对路径、盘符、UNC、设备路径、反斜杠 → E_PATH_SYNTAX。
        P4（第 2 轮复审 paths 视角）：补上 \\\\.\\ 设备命名空间与正斜杠写法 //./COM1、//?/C:/x。"""
        for value in ("/etc/passwd", "C:/temp/a", "C:a", "c:", "//server/share/a",
                      "a\\b", "\\\\server\\share", "\\\\?\\C:\\x", "/",
                      "\\\\.\\PhysicalDrive0", "//./COM1", "//?/C:/x", "\\\\.\\pipe\\x"):
            with self.subTest(value=value):
                exc = self.assertCode("E_PATH_SYNTAX", P.validate_business_path, value)
                self.assertEqual(exc.reason, "nonportable_path_syntax")

    def test_F025_dot_segments_empty_nul(self):
        """01-F025 / 4.1.5：父目录、空分段、点分段、末尾斜杠、NUL 与控制字符、DEL、空串、非 str → E_PATH_SYNTAX。"""
        for value in ("../a", "a/../b", "./a", "a//b", "a/.", "a/..", "..", ".", "a/",
                      "a\x00b", "a\nb", "a\x7fb", "a\x1fb", "a\tb", "", None, b"a", Path("a"), 1):
            with self.subTest(value=value):
                self.assertCode("E_PATH_SYNTAX", P.validate_business_path, value)

    def test_F025_length_and_segment_limits(self):
        """4.1.5：总长 > 4096 UTF-8 字节或单段 > 255 UTF-8 字节 → E_PATH_SYNTAX（按字节不按字符）。"""
        too_long = "/".join(["a" * 255] * 15 + ["b" * 201, "c" * 55])
        self.assertEqual(len(too_long.encode("utf-8")), 4097)
        self.assertCode("E_PATH_SYNTAX", P.validate_business_path, too_long)
        self.assertCode("E_PATH_SYNTAX", P.validate_business_path, "a" * 256)
        self.assertCode("E_PATH_SYNTAX", P.validate_business_path, "文" * 86)
        # P2 返工（复审变异 M55）：总长同样按 UTF-8 字节计。每段 255 字节的多字节路径共 4351 字节
        # （1461 个码点）必须拒绝；恰好 4096 字节的多字节路径接受。
        multibyte_over = "/".join(["文" * 85] * 17)
        self.assertEqual(len(multibyte_over.encode("utf-8")), 4351)
        self.assertLess(len(multibyte_over), 4096)
        self.assertCode("E_PATH_SYNTAX", P.validate_business_path, multibyte_over)
        multibyte_exact = "/".join(["文" * 85] * 15 + ["文" * 84, "abc"])
        self.assertEqual(len(multibyte_exact.encode("utf-8")), 4096)
        self.assertEqual(P.validate_business_path(multibyte_exact), multibyte_exact)

    def test_F025_c1_control_characters(self):
        """4.1.5“控制字符”：P2 返工新增（复审 fidelity/paths 视角）。按 Unicode 类别 Cc 理解，C1 控制字符
        U+0080–U+009F（例如 U+0085 NEL、U+009B CSI）与 C0、DEL 一样 → E_PATH_SYNTAX；
        U+00A0 起不再是控制字符。U+2028/U+2029 见 test_F025_line_separators_and_bidi_controls。"""
        for value in ("\x85x", "a\x9bb.txt", "\x80", "dir/\x9f.txt"):
            with self.subTest(value=repr(value)):
                exc = self.assertCode("E_PATH_SYNTAX", P.validate_business_path, value)
                self.assertEqual(exc.reason, "control_character")
        nbsp = "a" + chr(0xA0) + "b.txt"  # U+00A0 不是控制字符
        self.assertEqual(P.validate_business_path(nbsp), nbsp)

    def test_F025_line_separators_and_bidi_controls(self):
        """4.1.5：P4（裁决 R-P4）。行/段分隔符 U+2028、U+2029（str.splitlines() 会在此断行，日志注入）与
        双向控制字符 U+061C、U+200E、U+200F、U+202A–U+202E、U+2066–U+2069（Trojan Source）→ E_PATH_SYNTAX
        （reason=line_separator_or_bidi_control）；其他格式字符（ZWNJ U+200C、ZWJ U+200D、ZWSP U+200B、
        U+2060）与相邻码点（U+2027、U+202F、U+2065、U+206A）不拒绝。"""
        rejected = [0x2028, 0x2029, 0x061C, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
                    0x2066, 0x2067, 0x2068, 0x2069]
        for point in rejected:
            for value in ("a%sb.txt" % chr(point), "dir/%s" % chr(point) + "x", chr(point) + "x/y"):
                with self.subTest(codepoint="U+%04X" % point, value=repr(value)):
                    exc = self.assertCode("E_PATH_SYNTAX", P.validate_business_path, value,
                                          expect_field="/path")
                    self.assertEqual(exc.reason, "line_separator_or_bidi_control")
        for point in (0x200B, 0x200C, 0x200D, 0x2060, 0x2027, 0x202F, 0x2065, 0x206A):
            value = "a%sb.txt" % chr(point)
            with self.subTest(accepted="U+%04X" % point):
                self.assertEqual(P.validate_business_path(value), value)

    def test_A10_windows_short_name_form_reserved(self):
        """4.1.5、4.1.6：P4（裁决 R-P3）。形如 ABCDEF~1、PROGRA~1.TXT 的分段（基名是 1–6 个非 "." 字符的前缀 +
        "~" + 数字、基名总长 ≤ 8，可带 1–3 字符扩展名，大小写不敏感）在 Windows 上可能是另一文件的别名（例如
        AGENTS~1.MD），会绕过按字符串比较的保护路径 → E_PATH_RESERVED（reason=windows_short_name_form），在任一
        分段都拒绝。不是 8.3 形态的 "~" 名称照常接受。
        P4 第 3 轮（复审 paths 视角 major 与 tests-mutation M10/M11）：前缀**允许含 "~"**——Windows 对前 6 个有效
        字符含 "~" 的长名自动生成的短名前缀也含 "~"（~$DOCU~1.DOC、A~BCDE~1.TXT、~AGENT~1、哈希形态
        ~~1BC3~1.MD，实测见 test_A10_generated_short_names_with_tilde_prefix_reserved）；因此 a~b~1、x~y~2.txt
        也按短名形态拒绝（保守方向，与原裁决文字“非 ~ 字符”不同，理由见 protocols-api.md 第 19 节）。
        扩展名的边界：3 个字符（ABCDEF~1.JSO）拒绝，4 个字符（notes~1.json、ABCDEF~1.JSON、PROGRA~1.HTML）
        与 5 个字符接受。"""
        for value in ("ABCDEF~1", "PROGRA~1.TXT", "progra~1.txt", "AGENTS~1.MD", "a~1", "A~123456",
                      "AB~12345.X", "dir/LONGFI~1.TXT/x.json", "AGENT-~1/cfg.json", "CODEKI~1.TMP",
                      "文档~1.md", "ABCDEF~1.JSO",
                      # 前缀含 "~" 的真实短名形态（P4 第 3 轮）
                      "~$DOCU~1.DOC", "A~BCDE~1.TXT", "~~~~~~~1.TXT", "AB~CDE~1", "~AGENT~1", "~AGENT~1.BAK",
                      "~A4EF~1.TXT", "~~1BC3~1.MD", "dir/~AGENT~1/cfg.json", "a~b~1", "x~y~2.txt", "~~1"):
            with self.subTest(value=value):
                exc = self.assertCode("E_PATH_RESERVED", P.validate_business_path, value,
                                      expect_field="/path")
                self.assertEqual(exc.reason, "windows_short_name_form")
        for value in ("~/notes.txt", "a~b.txt", "ABCDEFG~1", "A~1234567", "backup~2024.tar",
                      "notes~1.json5", "a~1.b.c", "~1", "a.b~1", "x~.txt", "a~1x.txt",
                      # 扩展名 4 个字符不是 8.3 形态（tests-mutation M10）
                      "notes~1.json", "ABCDEF~1.JSON", "PROGRA~1.HTML", "file~2.yaml",
                      # 基名超过 8：前缀最多 6 个字符（含 "~" 时同样计数）
                      "~~~~~~~~1", "a~b~c~d~1", "~~~~~~~~1.TXT"):
            with self.subTest(accepted=value):
                self.assertEqual(P.validate_business_path(value), value)

    def test_A10_generated_short_names_with_tilde_prefix_reserved(self):
        """4.1.5、裁决 R-P3：P4 第 3 轮新增（复审 paths 视角，major）。在 tempfile 目录中建长名含 "~" 的文件与目录，
        用 GetShortPathNameW 取 Windows 自动生成的短名：它们的前缀含 "~"（例如 ~$DOCU~1.DOC），修复前词法层照常
        接受。现在全部以 E_PATH_RESERVED（windows_short_name_form）拒绝；长名本身不是 8.3 形态，照常接受。
        不是 Windows 或卷未启用 8.3 短名时 skip。"""
        if not IS_WINDOWS:
            self.skipTest("8.3 短名是 Windows 卷的特性（非 Windows 平台不适用）")
        with tempfile.TemporaryDirectory(prefix="codekit-short-") as td:
            top = Path(td)
            names = ["~$document.docx", "a~bcdefghijk.txt", "~~~~~~~~~~.txt", "ab~cdefghijkl",
                     "~agents.md.bak", "中文~文档说明书.txt"]
            for name in names:
                (top / name).write_bytes(b"x")
            (top / ".~agentconfig").mkdir()
            names.append(".~agentconfig")
            checked = []
            for name in names:
                short = windows_short_name(top / name)
                if short is None:
                    continue
                with self.subTest(long=name, short=short):
                    exc = self.assertCode("E_PATH_RESERVED", P.validate_business_path, short,
                                          expect_field="/path")
                    self.assertEqual(exc.reason, "windows_short_name_form")
                    self.assertEqual(P.validate_business_path(name), name)
                    checked.append(short)
            if not checked:
                self.skipTest("本卷没有 8.3 短名，前缀含 ~ 的短名部分未实测")
            self.assertTrue(any(short.rsplit("~", 1)[0].count("~") for short in checked),
                            "至少一个实测短名的前缀含 ~（修复前被漏掉的那一类）")

    def test_A10_ansi_best_fit_characters_not_rejected(self):
        """4.1.5：P4（裁决 R-P5，不增加严格 profile）。全角或兼容字符在 ANSI 代码页的 best-fit 转换后可能变成
        路径元字符（例如 U+FF0E U+FF0E U+FF3C → ..\\），但 01 只用宽字符 API，词法层不拒绝它们；把业务路径
        交给 ANSI API 程序的消费者必须自行复核（protocols-api.md 第 7 节）。本用例固定这一裁决。"""
        for value in ("．．＼victim.txt", "．．/x", "a：b", "／／x"):
            with self.subTest(value=repr(value)):
                self.assertEqual(P.validate_business_path(value), value)

    def test_F025_nonportable_characters_and_segment_endings(self):
        """4.1.5：: < > " | ? * 、分段末尾点或空格、孤立代理项 → E_PATH_SYNTAX。"""
        for ch in ':<>"|?*':
            with self.subTest(ch=ch):
                self.assertCode("E_PATH_SYNTAX", P.validate_business_path, f"a{ch}b")
        for value in ("dir./file", "a/space ", "a.", "a ", "a\ud800b"):
            with self.subTest(value=value):
                self.assertCode("E_PATH_SYNTAX", P.validate_business_path, value)

    def test_F026_reserved_device_names_and_ads(self):
        """01-F026 / 4.1.5（Microsoft 命名规则）：保留设备名大小写不敏感、带扩展名也算、
        基名末尾空格也算，任一分段命中 → E_PATH_RESERVED；ADS 形式 a:stream → E_PATH_SYNTAX。"""
        names = ["CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"]
        names += [f"COM{i}" for i in range(10)] + [f"LPT{i}" for i in range(10)]
        names += ["COM\u00b9", "COM\u00b2", "COM\u00b3", "LPT\u00b9", "LPT\u00b2", "LPT\u00b3"]
        for name in names:
            for variant in (name, name.lower(), f"dir/{name}.txt", f"{name}.tar.gz",
                            f"{name}/file.txt"):
                with self.subTest(variant=variant):
                    self.assertCode("E_PATH_RESERVED", P.validate_business_path, variant)
        for value in ("NUL .txt", "nul .tar.gz", "Com1", "conout$", "COM\u00b9.log"):
            with self.subTest(value=value):
                self.assertCode("E_PATH_RESERVED", P.validate_business_path, value)
        self.assertCode("E_PATH_SYNTAX", P.validate_business_path, "a:stream")
        # P4（第 2 轮复审 paths 视角）：带类型后缀的 ADS 写法同样拒绝。
        for value in ("a::$DATA", "file.txt::$DATA", "dir::$INDEX_ALLOCATION/x", "a:s:$DATA"):
            with self.subTest(value=value):
                exc = self.assertCode("E_PATH_SYNTAX", P.validate_business_path, value)
                self.assertEqual(exc.reason, "nonportable_path_syntax")
        # P2 \u8fd4\u5de5\uff08\u590d\u5ba1 paths \u89c6\u89d2\uff09\uff1a\u8bbe\u5907\u540d\u53ea\u505a ASCII \u5927\u5c0f\u5199\u6298\u53e0\u3002"CON\u0131N$"\uff08U+0131 \u65e0\u70b9 i\uff09\u7ecf
        # str.upper() \u4f1a\u53d8\u6210 CONIN$\uff0c\u4f46 Windows \u628a\u5b83\u5f53\u666e\u901a\u6587\u4ef6\u540d\uff0c\u4e0d\u80fd\u8bef\u62a5\u3002
        for value in ("CON\u0131N$", "con\u0131n$.txt", "\uff23\uff2f\uff2e", "COM\uff11"):
            with self.subTest(value=value):
                self.assertEqual(P.validate_business_path(value), value)

    def test_A10_name_collisions(self):
        """4.1.5：大小写与 Unicode 形式不擅自归一化，但跨平台名称碰撞要检出并阻断（NFC + casefold）。"""
        def groups(paths):
            return sorted(sorted(g) for g in P.find_name_collisions(paths))

        self.assertEqual(groups(["README.md", "readme.md", "src/a.py"]),
                         [["README.md", "readme.md"]])
        self.assertEqual(groups(["caf\u00e9.txt", "cafe\u0301.txt"]),
                         [sorted(["caf\u00e9.txt", "cafe\u0301.txt"])])
        self.assertEqual(groups(["STRASSE.txt", "stra\u00dfe.txt"]),
                         [["STRASSE.txt", "stra\u00dfe.txt"]])
        self.assertEqual(groups(["Src/a.py", "src/a.py"]), [["Src/a.py", "src/a.py"]])
        self.assertEqual(groups(["a.txt", "a.txt"]), [])
        self.assertEqual(groups(["a.txt", "b.txt"]), [])
        self.assertEqual(groups(["x.txt", "\uff58.txt"]), [], "NFC 不做兼容分解（不是 NFKC）")
        self.assertCode("E_PATH_COLLISION", P.check_no_name_collisions, ["README.md", "readme.md"])
        self.assertIsNone(P.check_no_name_collisions(["a.txt", "b.txt"]))

    def test_A10_prefix_and_file_directory_collisions(self):
        """4.1.5“跨平台实际名称碰撞应被检出并阻断”：P2 返工新增（复审 paths 视角）。
        check_no_name_collisions 还检查各级目录前缀（Fixtures/a.json 与 fixtures/b.json 在 Windows/macOS
        上落进同一目录）与“同名既是文件又是目录”；find_name_collisions 仍只按整条路径分组。"""
        cases = [(["Fixtures/a.json", "fixtures/b.json"], "directory_prefix_collision"),
                 (["caf\u00e9/a.json", "cafe\u0301/b.json"], "directory_prefix_collision"),
                 (["a/B/x.txt", "a/b/y.txt"], "directory_prefix_collision"),
                 (["data", "DATA/x.json"], "file_directory_conflict"),
                 (["data", "data/x.json"], "file_directory_conflict"),
                 (["README.md", "readme.md"], "case_or_normalization_collision")]
        for paths, reason in cases:
            with self.subTest(paths=paths):
                exc = self.assertCode("E_PATH_COLLISION", P.check_no_name_collisions, paths)
                self.assertEqual(exc.reason, reason)
        self.assertEqual(P.find_name_collisions(["Fixtures/a.json", "fixtures/b.json"]), [])
        self.assertIsNone(P.check_no_name_collisions(["src/a.py", "src/b.py", "src/sub/c.py",
                                                      "srcx/d.py", "a.txt", "a.txt"]))


class PhysicalPathTests(ProtocolTestCase):
    """4.1.6 物理层静态审阅；比较时一律用 resolve 后的根（本机临时目录含 8.3 短名）。"""

    def setUp(self):
        super().setUp()
        self._td = tempfile.TemporaryDirectory(prefix="codekit-path-")
        self.addCleanup(self._td.cleanup)
        self.top = Path(self._td.name)
        self.root = self.top / "repo"
        self.root.mkdir()
        self.outside = self.top / "outside"
        self.outside.mkdir()
        (self.outside / "secret.txt").write_bytes(b"outside\n")
        (self.root / "ok.txt").write_bytes(b"ok\n")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "inner.txt").write_bytes(b"inner\n")

    def _symlink(self, target: Path, link: Path, is_dir: bool = False):
        try:
            os.symlink(target, link, target_is_directory=is_dir)
        except (OSError, NotImplementedError, AttributeError) as exc:
            self.skipTest(f"无法创建符号链接（{type(exc).__name__}，可能缺少创建符号链接的权限），"
                          "未实测该项")

    def test_A10_static_resolution_positive(self):
        """4.1.6、B.1：根内已有文件静态解析成功；返回值相对 resolve 后的根计算（不受 8.3 短名影响）。"""
        resolved_root = self.root.resolve(strict=True)
        self.assertEqual(P.resolve_existing_path_for_review(self.root, "ok.txt"),
                         resolved_root / "ok.txt")
        result = P.resolve_existing_path_for_review(self.root, "sub/inner.txt")
        self.assertEqual(result, resolved_root / "sub" / "inner.txt")
        result.relative_to(resolved_root)

    def test_A10_static_resolution_docstring_limits(self):
        """4.1.6、4.1.7、01-D06：静态解析 docstring 写明不是访问凭证、不消除 TOCTOU。"""
        doc = P.resolve_existing_path_for_review.__doc__ or ""
        self.assertIn("TOCTOU", doc)

    # 裁决 R-P9 (2) 禁止的绝对表述。末尾三项由 P4 第 5 轮核验后增补：第 18 节第 20 项的“与 I/O 管理器一致”、
    # 第 19 节“P4 第 4 轮”第 1 条的“绝对目标同样折叠”，以及“不会在根外创建目录”这类条件式的绝对表述。
    R_P9_FORBIDDEN = ("杜绝", "都会被发现", "任一级", "任一个链接对象", "每一个链接对象", "每个链接对象",
                      "内核一致", "这一保证", "不放过", "逐字比较可靠",
                      "管理器一致", "同样折叠", "不会在根外")
    # 第 19 节历轮记录中保留被取代的原表述时，该行必须带的更正标记。
    R_P9_SUPERSEDED_MARK = "已由 R-P9 / P4 第 5 轮更正"
    # 中文引号内的文字是对原表述的引用，不是本文的断言。
    _QUOTED = re.compile(r"“[^“”]*”")

    def _assert_r_p9_wording(self, label, text):
        """第 7、15、16、18 节与物理检查 docstring 的规则：不含 R_P9_FORBIDDEN；“保证”只出现在“不保证”
        “不是安全访问保证”中。"""
        for phrase in self.R_P9_FORBIDDEN:
            self.assertNotIn(phrase, text, f"{label} 含绝对表述：{phrase}")
        residue = text.replace("不保证", "").replace("安全访问保证", "")
        self.assertNotIn("保证", residue, f"{label} 含“保证”")

    def test_A10_physical_check_wording_follows_r_p9(self):
        """裁决 R-P9 (2)(3)、01-D06：P4 第 5 轮新增（复审 paths 与 fidelity 视角，major）。物理检查是“静态审阅 + 纵深
        防御”，不是安全访问保证：
        - 相关 docstring 与 protocols-api.md 第 7、15、16 节不得使用绝对表述（“杜绝”“任一级越界都会被发现”“链上每一个
          链接对象都必须……”“与本平台内核一致”“这一保证”等）；“保证”只能出现在“不保证”“不是安全访问保证”中；
        - 第 7、15 节必须给出“已检测的情形”与“已知不检测”两张清单，第 16 节引用 R-P9；
        - PATH_REVIEW_LIMITATIONS 与 SEALING_LIMITATIONS 必须列出 R-P9 点名的各项（TOCTOU 与并发替换、检查后父目录或
          目标被替换、硬链接、挂载点、NT/Win32 尚未枚举的写法、POSIX 未实测、同账户进程篡改）；
        - sealing 必须写明存储根由可信核心独占控制、A13 的范围是发布与索引补偿（R-P9 (3)）。
        禁止的表述见 R_P9_FORBIDDEN（第 5 轮核验后增补了三项，本用例同时适用）；检查范围的扩大见
        test_A10_r_p9_wording_covers_changelog_history_and_tests。"""
        check_wording = self._assert_r_p9_wording

        docs = {
            "protocols.resolve_existing_path_for_review": P.resolve_existing_path_for_review.__doc__,
            "protocols._check_link_hops": P._check_link_hops.__doc__,
            "protocols._is_within": P._is_within.__doc__,
            "protocols._link_target_text": P._link_target_text.__doc__,
            "protocols._split_link_target": P._split_link_target.__doc__,
            "protocols._check_listed_name": P._check_listed_name.__doc__,
            "sealing": S.__doc__,
            "sealing.seal_bytes": S.seal_bytes.__doc__,
            "sealing.read_sealed": S.read_sealed.__doc__,
            "sealing._step": S._step.__doc__,
            "sealing._ensure_parent": S._ensure_parent.__doc__,
        }
        for label, text in docs.items():
            with self.subTest(docstring=label):
                self.assertTrue(text)
                check_wording(label, text)
        for label in ("protocols.resolve_existing_path_for_review", "protocols._check_link_hops", "sealing",
                      "sealing.seal_bytes", "sealing.read_sealed", "sealing._step", "sealing._ensure_parent"):
            with self.subTest(mentions_r_p9=label):
                self.assertIn("R-P9", docs[label])
        path_items = ("TOCTOU", "父目录或目标被替换", "硬链接不检测", "挂载点", "NT 层与 Win32 层", "POSIX",
                      "同一账户", "名称代理位")
        seal_items = ("可信核心独占控制", "发布与索引补偿", "父目录或目标被替换", "硬链接不检测", "挂载点",
                      "NT 层与 Win32 层", "POSIX", "同一账户")
        for constant, items in ((P.PATH_REVIEW_LIMITATIONS, path_items), (S.SEALING_LIMITATIONS, seal_items)):
            for item in items:
                with self.subTest(limitation=item):
                    self.assertTrue(any(item in entry for entry in constant), item)
        text = (REPO_ROOT / "docs" / "code-kit-v2" / "01-baseline" / "protocols-api.md").read_text(encoding="utf-8")
        sections = {}
        for chunk in text.split("\n## ")[1:]:
            number = chunk.split(".", 1)[0]
            sections[number] = chunk
        required = {"7": ("R-P9", "已检测的情形", "已知不检测"),
                    "15": ("R-P9", "已检测的情形", "已知不检测", "可信核心独占控制", "发布与索引补偿"),
                    "16": ("R-P9",)}
        for number, phrases in required.items():
            with self.subTest(section=number):
                for phrase in phrases:
                    self.assertIn(phrase, sections[number])
                check_wording(f"protocols-api.md 第 {number} 节", sections[number])

    def test_A10_r_p9_wording_covers_changelog_history_and_tests(self):
        """裁决 R-P9 (2)：P4 第 5 轮核验后新增（核验 minor 两条）。上一用例只检查第 7、15、16 节，漏掉了：第 18 节
        第 20 项仍写“按词法折叠目标文本中的 . 与 ..（与 I/O 管理器一致…）”，没有限定相对目标，而第 5 轮起逐字绝对
        目标中的 . 与 .. 被拒绝（内核也是拒绝而不是折叠）；第 19 节“P4 第 3 轮”第 1 条与“P4 第 4 轮”第 1 条保留了
        被取代的绝对表述，没有更正说明。本用例把检查扩大到：
        - 第 18 节整节：规则与第 7、15、16 节相同（含“保证”的限制）；第 20 项必须把词法折叠限定为相对目标，并写明
          逐字绝对目标由第 5 轮改为拒绝；
        - 开头与第 1–6、8–14、17 节：不得出现 R_P9_FORBIDDEN；
        - 第 19 节（历轮处理记录）：允许在中文引号中引用原表述；引号之外出现 R_P9_FORBIDDEN 的行必须带更正标记
          R_P9_SUPERSEDED_MARK，上述两条历史行必须带这个标记；
        - 本文件全部测试类与测试方法的 docstring 以及模块 docstring（去掉引号中的引用后）不得出现 R_P9_FORBIDDEN；
          物理检查的两个测试类（PhysicalPathTests、SealingTests）另按“保证”的限制检查。"""
        def unquoted(text):
            return self._QUOTED.sub("", text)

        def forbidden_in(text):
            return [phrase for phrase in self.R_P9_FORBIDDEN if phrase in text]

        text = (REPO_ROOT / "docs" / "code-kit-v2" / "01-baseline" / "protocols-api.md").read_text(encoding="utf-8")
        chunks = text.split("\n## ")
        sections = {"head": chunks[0]}
        for chunk in chunks[1:]:
            sections[chunk.split(".", 1)[0]] = chunk
        self.assertEqual(set(sections), {"head"} | {str(n) for n in range(1, 20)})

        # 第 18 节整节。
        self._assert_r_p9_wording("protocols-api.md 第 18 节", sections["18"])
        item20 = sections["18"].split("\n20. ", 1)[1].split("\n21. ", 1)[0]
        for phrase in ("按词法折叠相对目标", "逐字绝对目标", self.R_P9_SUPERSEDED_MARK, "拒绝解析",
                       "按不受支持的写法拒绝"):
            with self.subTest(section18_item20=phrase):
                self.assertIn(phrase, item20)

        # 开头与其余章节（第 7、15、16 节由上一用例检查）。
        for key, body in sections.items():
            if key in ("7", "15", "16", "18", "19"):
                continue
            with self.subTest(section=key):
                self.assertEqual(forbidden_in(body), [])

        # 第 19 节：引号外的禁止表述只允许出现在带更正标记的历史行中。
        lines = sections["19"].splitlines()
        for line in lines:
            hits = forbidden_in(unquoted(line))
            if hits:
                with self.subTest(section19_line=line[:60]):
                    self.assertIn(self.R_P9_SUPERSEDED_MARK, line, hits)
        history_rows = ("| 1 | fidelity | major | 同一分段内的链接链",
                        "| 1 | fidelity | major | `_check_link_hops` 把目标文本中的 `..`")
        for prefix in history_rows:
            with self.subTest(history_row=prefix):
                matches = [line for line in lines if line.startswith(prefix)]
                self.assertEqual(len(matches), 1)
                self.assertIn(self.R_P9_SUPERSEDED_MARK, matches[0])
        # 判别力自检：引号外的禁止表述会被识别，引号内的引用不会。
        self.assertEqual(forbidden_in(unquoted("绝对目标同样折叠；“链上任一个链接对象位于根外”")), ["同样折叠"])

        # 测试 docstring。
        module = sys.modules[type(self).__module__]
        with self.subTest(docstring="module"):
            self.assertEqual(forbidden_in(unquoted(module.__doc__ or "")), [])
        checked = 0
        for class_name, cls in sorted(vars(module).items()):
            if not (isinstance(cls, type) and issubclass(cls, unittest.TestCase)):
                continue
            docs = [(class_name, cls.__doc__)]
            docs += [(f"{class_name}.{name}", getattr(value, "__doc__", None))
                     for name, value in sorted(vars(cls).items()) if name.startswith("test")]
            for label, doc in docs:
                if not doc:
                    continue
                checked += 1
                body = unquoted(doc)
                with self.subTest(docstring=label):
                    self.assertEqual(forbidden_in(body), [])
                    if class_name in ("PhysicalPathTests", "SealingTests"):
                        residue = body.replace("不保证", "").replace("安全访问保证", "")
                        self.assertNotIn("保证", residue)
        self.assertGreater(checked, 300)

    def test_A10_static_resolution_errors(self):
        """4.1.6、4.1.7：词法非法先拒绝（E_PATH_SYNTAX）；目标不存在 → E_PATH_NOT_FOUND；
        根不是目录或不存在 → E_PATH_ROOT。"""
        self.assertCode("E_PATH_SYNTAX", P.resolve_existing_path_for_review, self.root, "../outside")
        self.assertCode("E_PATH_NOT_FOUND", P.resolve_existing_path_for_review, self.root,
                        "missing.txt")
        self.assertCode("E_PATH_ROOT", P.resolve_existing_path_for_review, self.root / "ok.txt",
                        "x.txt")
        self.assertCode("E_PATH_ROOT", P.resolve_existing_path_for_review, self.top / "no-root",
                        "x.txt")

    def test_F027_symlink_escape(self):
        """01-F027 / 4.1.5、4.1.6：根内符号链接（文件与目录）指向根外 → E_PATH_ESCAPE（Windows 实测）。
        根内指向根内的链接可解析，返回解析后的真实目标。"""
        self._symlink(self.outside / "secret.txt", self.root / "escape.txt")
        self._symlink(self.outside, self.root / "linkdir", is_dir=True)
        self._symlink(self.root / "ok.txt", self.root / "alias.txt")
        self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root,
                        "escape.txt")
        self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root,
                        "linkdir/secret.txt")
        self.assertEqual(P.resolve_existing_path_for_review(self.root, "alias.txt"),
                         self.root.resolve(strict=True) / "ok.txt")

    def test_A10_symlink_loop_resolution_failed(self):
        """4.1.6：链接环等解析失败 → E_PATH_RESOLUTION_FAILED（不泄漏 OSError/RuntimeError）。"""
        self._symlink(self.root / "loop-b", self.root / "loop-a")
        self._symlink(self.root / "loop-a", self.root / "loop-b")
        self.assertCode("E_PATH_RESOLUTION_FAILED", P.resolve_existing_path_for_review, self.root,
                        "loop-a")

    @unittest.skipUnless(IS_WINDOWS, "junction 只在 Windows 上实测（非 Windows 平台不适用）")
    def test_F028_junction_escape(self):
        """01-F028 / 4.1.6、7.5：Windows junction（重解析点）越界 → E_PATH_ESCAPE；指向根内的 junction 可解析。"""
        import _winapi

        junction = self.root / "jn"
        _winapi.CreateJunction(str(self.outside), str(junction))
        self.addCleanup(os.rmdir, junction)
        inner_junction = self.root / "jn-inner"
        _winapi.CreateJunction(str(self.root / "sub"), str(inner_junction))
        self.addCleanup(os.rmdir, inner_junction)
        self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root,
                        "jn/secret.txt")
        self.assertEqual(P.resolve_existing_path_for_review(self.root, "jn-inner/inner.txt"),
                         self.root.resolve(strict=True) / "sub" / "inner.txt")

    def _junction(self, target: Path, link: Path):
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
        self.addCleanup(os.rmdir, link)

    def test_A10_root_variants(self):
        """4.1.6：P2 返工新增（复审 paths 视角）。根本身是 junction、根的拼写大小写不同，都按
        resolve 后的根计算返回值；返回值不受根的拼写影响。"""
        resolved_root = self.root.resolve(strict=True)
        if IS_WINDOWS:
            jroot = self.top / "jroot"
            self._junction(self.root, jroot)
            self.assertEqual(P.resolve_existing_path_for_review(jroot, "sub/inner.txt"),
                             resolved_root / "sub" / "inner.txt")
            lower = Path(str(self.root).lower())
            self.assertEqual(P.resolve_existing_path_for_review(lower, "ok.txt"),
                             resolved_root / "ok.txt")
        else:
            link_root = self.top / "linkroot"
            self._symlink(self.root, link_root, is_dir=True)
            self.assertEqual(P.resolve_existing_path_for_review(link_root, "sub/inner.txt"),
                             resolved_root / "sub" / "inner.txt")

    def test_A10_target_is_directory_link(self):
        """4.1.6：P2 返工新增。目标本身就是目录链接（不是经由它访问下层文件）：指向根内时返回解析后的
        目录，指向根外 → E_PATH_ESCAPE。Windows 同时实测 junction 与目录 symlink。"""
        resolved_root = self.root.resolve(strict=True)
        self._symlink(self.root / "sub", self.root / "dirlink-in", is_dir=True)
        self._symlink(self.outside, self.root / "dirlink-out", is_dir=True)
        self.assertEqual(P.resolve_existing_path_for_review(self.root, "dirlink-in"),
                         resolved_root / "sub")
        self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root, "dirlink-out")
        if IS_WINDOWS:
            self._junction(self.root / "sub", self.root / "jn-in")
            self._junction(self.outside, self.root / "jn-out")
            self.assertEqual(P.resolve_existing_path_for_review(self.root, "jn-in"),
                             resolved_root / "sub")
            self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root, "jn-out")

    def test_A10_dangling_links_not_found(self):
        """4.1.6：P2 返工新增。悬空的目录 symlink（以及 Windows 上悬空的 junction）→ E_PATH_NOT_FOUND。"""
        self._symlink(self.root / "gone-dir", self.root / "dangling", is_dir=True)
        self.assertCode("E_PATH_NOT_FOUND", P.resolve_existing_path_for_review, self.root, "dangling")
        self.assertCode("E_PATH_NOT_FOUND", P.resolve_existing_path_for_review, self.root,
                        "dangling/x.txt")
        if IS_WINDOWS:
            gone = self.top / "gone"
            gone.mkdir()
            self._junction(gone, self.root / "jn-dangling")
            gone.rmdir()
            self.assertCode("E_PATH_NOT_FOUND", P.resolve_existing_path_for_review, self.root,
                            "jn-dangling/x.txt")

    def test_A10_path_through_outside_is_escape(self):
        """4.1.6：P2 返工新增。逐级解析：多分段路径的中间一级落到根外、之后又经链接绕回根内，同样 →
        E_PATH_ESCAPE（审阅时不在根外列目录）。同一分段内的链接链（根内链接 → 根外链接 → 根内目标）见
        test_A10_single_segment_link_chain_through_outside_is_escape（P4 第 3 轮逐跳核对）。"""
        self._symlink(self.outside, self.root / "out", is_dir=True)
        self._symlink(self.root, self.outside / "back", is_dir=True)
        self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root,
                        "out/back/ok.txt")

    def test_A10_single_segment_link_chain_through_outside_is_escape(self):
        """4.1.6、01-A10：P4 第 3 轮新增（复审 fidelity 视角，major）。逐级检查原来只看每个分段 resolve 后的最终
        目标：同一分段内的链接链 repo/hop → outside/hop2 → repo/ok.txt（以及目录链 repo/dhop → outside/dhop2 →
        repo/sub）最终目标在根内，被接受，解析结果却依赖根外对象。已检测的情形（R-P9 起按“已检测/已知不检测”两张
        清单表述，见 protocols-api.md 第 7 节）：逐跳展开时遇到位于根外的链接对象 →
        E_PATH_ESCAPE（reason=link_hop_outside_trusted_root）。根内的链接链（含相对目标、目标文本中带 8.3 形式的
        临时目录与 ".."）照常接受。Windows 另测 junction 组成的链。"""
        resolved_root = self.root.resolve(strict=True)
        self._symlink(self.root / "ok.txt", self.outside / "hop2")
        self._symlink(self.outside / "hop2", self.root / "hop")
        self._symlink(self.root / "sub", self.outside / "dhop2", is_dir=True)
        self._symlink(self.outside / "dhop2", self.root / "dhop", is_dir=True)
        # 对照：修复前被接受的正是这些输入（最终目标都在根内）。
        self.assertEqual((self.root / "hop").resolve(strict=True), resolved_root / "ok.txt")
        for business_path in ("hop", "dhop", "dhop/inner.txt"):
            with self.subTest(business_path=business_path):
                exc = self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root,
                                      business_path, expect_field="/path")
                self.assertEqual(exc.reason, "link_hop_outside_trusted_root")
        # 根内的链接链照常接受：绝对目标（文本含 tempfile 给出的 8.3 形式路径）、相对目标、含 ".." 的相对目标。
        self._symlink(self.root / "ok.txt", self.root / "in2")
        self._symlink(self.root / "in2", self.root / "in1")
        os.symlink("ok.txt", self.root / "rel")
        os.symlink(os.path.join("..", "ok.txt"), self.root / "sub" / "up")
        self._symlink(self.root / "sub", self.root / "dl", is_dir=True)
        for business_path, expected in (("in1", resolved_root / "ok.txt"), ("rel", resolved_root / "ok.txt"),
                                        ("sub/up", resolved_root / "ok.txt"),
                                        ("dl/up", resolved_root / "ok.txt"),
                                        ("dl/inner.txt", resolved_root / "sub" / "inner.txt")):
            with self.subTest(accepted=business_path):
                self.assertEqual(P.resolve_existing_path_for_review(self.root, business_path), expected)
        if IS_WINDOWS:
            self._junction(self.root / "sub", self.outside / "jn2")
            self._junction(self.outside / "jn2", self.root / "jn1")
            self.assertEqual((self.root / "jn1").resolve(strict=True), resolved_root / "sub")
            for business_path in ("jn1", "jn1/inner.txt"):
                with self.subTest(junction_chain=business_path):
                    self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root,
                                    business_path)
            # 链接目标文本经过根外的 junction（它本身位于根外）再回到根内：同样越界。
            self._junction(self.root, self.outside / "jroot")
            self._symlink(self.outside / "jroot" / "ok.txt", self.root / "via-outside-junction")
            self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root,
                            "via-outside-junction")
            self._junction(self.root / "sub", self.root / "jn-in")
            self.assertEqual(P.resolve_existing_path_for_review(self.root, "jn-in/inner.txt"),
                             resolved_root / "sub" / "inner.txt")

    def _verbatim_symlink(self, target, link: str, is_dir: bool = False):
        """按 Windows 逐字路径（\\\\?\\）创建链接，名称可以带末尾的点或空格（Win32 规范化会去掉它们）；
        用后按逐字路径删除（先于临时目录的清理执行）。无法创建时 skip。"""
        try:
            os.symlink(target, link, target_is_directory=is_dir)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"无法按逐字路径创建符号链接（{type(exc).__name__}），未实测该项")
        self.addCleanup(os.rmdir if is_dir else os.unlink, link)

    @unittest.skipUnless(IS_WINDOWS, "Windows 按词法折叠链接目标中的 \"..\"；POSIX 按物理语义，"
                                     "见 test_A10_split_link_target_forms")
    def test_A10_windows_link_target_dotdot_is_lexical(self):
        """4.1.6、01-A10：P4 第 4 轮新增（复审 fidelity 与 paths 视角，major）。Windows 解析相对 symlink 时按词法
        折叠目标文本中的 ".."：a/l → "x\\..\\y" 等同于 a/y，不访问 x（x 是指向 deep/dir 的目录链接）。修复前逐跳
        核对先跟随 x 再取真实目录的上一级，走到不存在的 deep/y 就静默结束，于是经 a/y → outside/hop2 →
        ok.txt 绕到根外的链被接受（目录链 a/ld → "x\\..\\yd" 同理）；反方向把根内的 "missing\\..\\y.txt"、
        "L\\..\\sub\\inner.txt" 误报 E_PATH_RESOLUTION_FAILED（link_hop_unresolvable）。本机实测两个方向现在都与 OS 的解析一致。"""
        resolved_root = self.root.resolve(strict=True)
        a = self.root / "a"
        a.mkdir()
        (self.root / "deep" / "dir").mkdir(parents=True)
        self._symlink(self.root / "deep" / "dir", a / "x", is_dir=True)
        self._symlink(self.root / "ok.txt", self.outside / "hop2")
        self._symlink(self.outside / "hop2", a / "y")
        self._symlink("x\\..\\y", a / "l")
        self._symlink(self.root / "sub", self.outside / "dhop2", is_dir=True)
        self._symlink(self.outside / "dhop2", a / "yd", is_dir=True)
        self._symlink("x\\..\\yd", a / "ld", is_dir=True)
        # 前提：OS 按词法折叠，经过的是 a/y 与 a/yd（链上有根外的 hop2、dhop2），不是 deep 下不存在的 y、yd。
        self.assertEqual(os.readlink(a / "l"), "x\\..\\y")
        self.assertEqual((a / "l").resolve(strict=True), resolved_root / "ok.txt")
        self.assertEqual((a / "ld" / "inner.txt").resolve(strict=True), resolved_root / "sub" / "inner.txt")
        self.assertFalse(os.path.lexists(self.root / "deep" / "y"))
        for business_path in ("a/y", "a/l", "a/yd", "a/ld", "a/ld/inner.txt"):
            with self.subTest(escape=business_path):
                exc = self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root,
                                      business_path, expect_field="/path")
                self.assertEqual(exc.reason, "link_hop_outside_trusted_root")
        # 反方向：根内的链照常接受。
        (a / "y.txt").write_bytes(b"y\n")
        self._symlink("missing\\..\\y.txt", a / "m")
        (a / "b").mkdir()
        self._symlink(a / "b", self.root / "L", is_dir=True)
        self._symlink("L\\..\\sub\\inner.txt", self.root / "seg")
        self._symlink("L\\..\\..\\" + self.root.name + "\\ok.txt", self.root / "seg2")
        for business_path, expected in (("a/m", resolved_root / "a" / "y.txt"),
                                        ("seg", resolved_root / "sub" / "inner.txt"),
                                        ("seg2", resolved_root / "ok.txt")):
            with self.subTest(accepted=business_path):
                self.assertEqual(P.resolve_existing_path_for_review(self.root, business_path), expected)

    @unittest.skipUnless(IS_WINDOWS, "名称末尾的点与空格被 Win32 规范化去掉，是 Windows 特有的情形")
    def test_A10_link_target_names_with_trailing_dot_or_space(self):
        """4.1.6、01-A10：P4 第 4 轮新增（复审 paths 视角，major）。NTFS 允许以 "." 或空格结尾的名称（经 \\\\?\\
        创建）。内核在 NT 层逐字解析链接目标文本，Win32 路径却去掉分段末尾的点与空格：修复前逐跳核对对
        "hop." 做 lstat 时看的是不存在的 "hop"，没有识别出它是指向根外的链接，于是 segdot → "hop." →
        outside/hop2 → ok.txt 被接受（末尾空格、目录链 segd → "dhop." → outside/dhop2 → sub 同理）。现在逐跳
        核对按逐字路径访问，这些链都 → E_PATH_ESCAPE；根内名称末尾带点的真实目录照常可用。"""
        resolved_root = self.root.resolve(strict=True)
        self._symlink(self.root / "ok.txt", self.outside / "hop2")
        self._symlink(self.root / "sub", self.outside / "dhop2", is_dir=True)
        prefix = verbatim(self.root) + "\\"
        self._verbatim_symlink(verbatim(self.outside / "hop2"), prefix + "hop.")
        self._verbatim_symlink(verbatim(self.outside / "hop2"), prefix + "hop ")
        self._verbatim_symlink(verbatim(self.outside / "dhop2"), prefix + "dhop.", is_dir=True)
        self._symlink("hop.", self.root / "segdot")
        self._symlink("hop ", self.root / "segsp")
        self._symlink("dhop.", self.root / "segd", is_dir=True)
        # 前提：Win32 路径看不到这些链接（名称被规范化成不存在的 hop/dhop），OS 解析却经过它们。
        self.assertFalse(os.path.lexists(str(self.root) + "\\hop."))
        self.assertTrue(os.path.islink(prefix + "hop."))
        for business_path, expected in (("segdot", resolved_root / "ok.txt"), ("segsp", resolved_root / "ok.txt"),
                                        ("segd", resolved_root / "sub")):
            self.assertEqual((self.root / business_path).resolve(strict=True), expected)
        for business_path in ("segdot", "segsp", "segd", "segd/inner.txt"):
            with self.subTest(escape=business_path):
                exc = self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root,
                                      business_path, expect_field="/path")
                self.assertEqual(exc.reason, "link_hop_outside_trusted_root")
        dotted = prefix + "dd."
        os.mkdir(dotted)
        self.addCleanup(os.rmdir, dotted)
        with open(dotted + "\\in.txt", "wb") as handle:
            handle.write(b"in\n")
        self.addCleanup(os.unlink, dotted + "\\in.txt")
        self._symlink("dd.\\in.txt", self.root / "middot")
        self._symlink(dotted, self.root / "todd", is_dir=True)
        for business_path in ("middot", "todd/in.txt"):
            with self.subTest(accepted=business_path):
                result = P.resolve_existing_path_for_review(self.root, business_path)
                # resolve 对含 "dd." 的真实路径保留 \\?\ 前缀，按组件逐字比较（与 _is_within 同一口径）。
                self.assertEqual(P._exact_parts(result), P._exact_parts(resolved_root / "dd." / "in.txt"))

    def test_A10_relative_link_chain_through_outside_is_escape(self):
        """4.1.6、01-A10：P4 第 4 轮新增（复审 tests-mutation 视角，major）。经根外绕回根内的链接链以**相对**目标
        开头：relhop → "hop2"、sub/up → "..\\hop2"（hop2 → outside/hop3 → ok.txt），目录链 reld → "dhop2"
        （dhop2 → outside/dhop3 → sub）。此前越界链全部使用绝对目标，把相对目标改为从盘符根起算、或把 ".."
        改成空操作的变异都存活。Windows 另测只有根、没有盘符的目标（"\\Users\\…\\ok.txt"）：P4 第 4 轮时根内接受、
        经根外链接 → E_PATH_ESCAPE；P4 第 5 轮（裁决 R-P9，失败关闭）起两者都 → E_PATH_RESOLUTION_FAILED
        （link_target_form_unsupported）：os.readlink 不给出相对/绝对标志位，这种文本在绝对标志下是 NT 命名空间路径
        （见 test_A10_windows_link_target_forms_measured），语义无法确定。这是有意收紧（接受 → 拒绝；越界链仍被
        拒绝，只是错误码改为失败关闭的码），不是削弱断言。"""
        resolved_root = self.root.resolve(strict=True)
        self._symlink(self.root / "ok.txt", self.outside / "hop3")
        self._symlink(self.outside / "hop3", self.root / "hop2")
        self._symlink("hop2", self.root / "relhop")
        self._symlink(os.path.join("..", "hop2"), self.root / "sub" / "up")
        self._symlink(self.root / "sub", self.outside / "dhop3", is_dir=True)
        self._symlink(self.outside / "dhop3", self.root / "dhop2", is_dir=True)
        self._symlink("dhop2", self.root / "reld", is_dir=True)
        self.assertEqual((self.root / "sub" / "up").resolve(strict=True), resolved_root / "ok.txt")
        for business_path in ("relhop", "sub/up", "reld", "reld/inner.txt"):
            with self.subTest(escape=business_path):
                exc = self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root,
                                      business_path, expect_field="/path")
                self.assertEqual(exc.reason, "link_hop_outside_trusted_root")
        if IS_WINDOWS:
            self._symlink(str(resolved_root / "ok.txt")[2:], self.root / "rootrel")
            self._symlink(str(self.outside.resolve(strict=True) / "hop3")[2:], self.root / "rootrel-out")
            self.assertTrue(os.readlink(self.root / "rootrel").startswith("\\"),
                            "前提：链接目标以根开头、不带盘符")
            self.assertEqual((self.root / "rootrel").resolve(strict=True), resolved_root / "ok.txt",
                             "前提：OS 能解析这条链接（相对标志下从链接所在盘的根起算）")
            for business_path in ("rootrel", "rootrel-out"):
                with self.subTest(root_only=business_path):
                    exc = self.assertCode("E_PATH_RESOLUTION_FAILED", P.resolve_existing_path_for_review,
                                          self.root, business_path, expect_field="/path")
                    self.assertEqual(exc.reason, "link_target_form_unsupported")

    def test_A10_split_link_target_forms(self):
        """01-A10：P4 第 4 轮新增（白盒，复审 tests-mutation 视角）。_split_link_target 对各种目标写法的拆分：
        Windows 相对目标按词法折叠 "."、".." 与空分段，开头的 ".." 作用于链接所在的真实目录；只有盘符的半相对路径、
        卷 GUID 等设备路径、含 "/" 的目标、".." 越过盘符根 → None（调用方报 link_target_form_unsupported）。POSIX 把
        ".." 原样留给调用方按物理语义处理。只拆分文本，不访问文件系统。
        P4 第 5 轮（裁决 R-P9，失败关闭；复审 fidelity 视角）：以下写法由“接受”改为 None，内核的实际处理见
        test_A10_windows_link_target_forms_measured——逐字绝对目标中含 "."、".." 或空分段（内核拒绝，而不是按词法
        折叠）；不带 \\\\?\\ 的盘符绝对路径（内核在两种标志位下都拒绝）；只有根、没有盘符的目标（语义无法确定）。
        逐字绝对目标末尾的一个分隔符照常接受（内核实测可解析）。"""
        where = self.root.resolve(strict=True) / "sub"
        if IS_WINDOWS:
            accepted = [("x\\..\\y", where, ["y"]),
                        ("..\\a\\.\\b\\..\\c", where.parent, ["a", "c"]),
                        ("a\\\\b\\", where, ["a", "b"]),
                        ("\\\\?\\C:\\a\\b", Path("C:\\"), ["a", "b"]),
                        ("\\\\?\\C:\\a\\b\\", Path("C:\\"), ["a", "b"]),
                        ("\\\\?\\C:\\", Path("C:\\"), []),
                        ("\\\\?\\UNC\\srv\\share\\x", Path("\\\\srv\\share\\"), ["x"])]
            rejected = ["C:x", "C:", "x/y", "\\\\?\\Volume{00000000-0000-0000-0000-000000000000}\\x",
                        "\\\\.\\C:\\x", "..\\" * len(where.parts) + "x", "C:\\..\\x",
                        # P4 第 5 轮（R-P9）起拒绝：
                        "\\x\\y", "\\Device\\HarddiskVolume2\\x", "\\GLOBAL??\\C:\\x",
                        "\\\\?\\C:\\a\\..\\b", "\\\\?\\C:\\a\\.\\b", "\\\\?\\C:\\a\\\\b", "\\\\?\\C:\\a\\b\\\\",
                        "\\\\?\\UNC\\srv\\share\\x\\..\\y", "\\\\?\\C:", "C:\\a\\b", "C:\\a\\.\\b",
                        "\\\\srv\\share\\x", "\\\\?\\GLOBALROOT\\Device\\HarddiskVolume2\\x"]
        else:
            accepted = [("a/../b", where, ["a", "..", "b"]), ("/x/../y", Path("/"), ["x", "..", "y"])]
            rejected = []
        for text, start, parts in accepted:
            with self.subTest(accepted=text):
                self.assertEqual(P._split_link_target(text, where), (start, parts))
        for text in rejected:
            with self.subTest(rejected=text):
                self.assertIsNone(P._split_link_target(text, where))
        # 逐跳展开交给 lstat/readlink/resolve 的逐字路径形式（与平台无关，用 Pure*Path 构造）。
        from pathlib import PurePosixPath, PureWindowsPath

        for given, expected in ((PureWindowsPath("C:\\a\\hop."), "\\\\?\\C:\\a\\hop."),
                                (PureWindowsPath("\\\\srv\\share\\x"), "\\\\?\\UNC\\srv\\share\\x"),
                                (PureWindowsPath("\\\\?\\C:\\a"), "\\\\?\\C:\\a")):
            with self.subTest(os_path=str(given)):
                self.assertEqual(P._os_path(given), expected)
        self.assertEqual(P._os_path(PurePosixPath("/a/hop.")), PurePosixPath("/a/hop."))

    def test_A10_link_walk_unsupported_form_and_divergence(self):
        """01-A10：P4 第 4 轮新增（白盒注入，复审 tests-mutation 视角）。替换 protocols._link_target_text，让逐跳
        展开读到的目标文本与磁盘上的不同（模拟逐跳展开与 OS 走了不同的链）：
        - Windows 上读到只有盘符的半相对目标 "C:ok.txt" → E_PATH_RESOLUTION_FAILED（link_target_form_unsupported）；
        - 读到另一个根内对象 sub/inner.txt，或读到 "."（折叠后没有剩余分段，终点是链接所在目录本身）：展开终点
          与 resolve 的结果不同 → E_PATH_RESOLUTION_FAILED（link_walk_diverged）。这是兜底检查，此前没有。
        用后恢复；真实文本下同一链接照常接受。"""
        resolved_root = self.root.resolve(strict=True)
        self._symlink(self.root / "ok.txt", self.root / "alias")
        real = P._link_target_text
        fake = {}

        def patched(path):
            text = fake.get(path.name)
            return real(path) if text is None else text

        cases = [(os.path.join("sub", "inner.txt"), "link_walk_diverged"), (".", "link_walk_diverged")]
        if IS_WINDOWS:
            cases.append(("C:ok.txt", "link_target_form_unsupported"))
        P._link_target_text = patched
        try:
            for text, reason in cases:
                with self.subTest(target_text=text):
                    fake["alias"] = text
                    exc = self.assertCode("E_PATH_RESOLUTION_FAILED", P.resolve_existing_path_for_review,
                                          self.root, "alias", expect_field="/path")
                    self.assertEqual(exc.reason, reason)
        finally:
            P._link_target_text = real
        self.assertEqual(P.resolve_existing_path_for_review(self.root, "alias"), resolved_root / "ok.txt")

    def test_A10_link_walk_failure_reasons_fail_closed(self):
        """01-A10、裁决 R-P9 (1)：P4 第 5 轮新增（白盒注入）。第 7 节“已检测的情形”列出的另外三种逐跳展开失败此前没有
        用例：替换 protocols._link_target_text，让 alias（→ ok.txt，OS 照常解析）的逐跳展开
        - 读到指向自身的目标 "alias"（跳数超过 64）→ link_hop_limit_exceeded（本机内核的重解析上限是 63，黑盒在
          resolve 阶段就失败，到不了这一步）；
        - 读到 "missing\\ok.txt"（中间分段不存在，无法取真实拼写）→ link_hop_unresolvable；
        - 读取时抛 PermissionError → link_hop_unreadable。
        三者都是 E_PATH_RESOLUTION_FAILED（失败关闭），不当作普通名称放行。用后恢复。"""
        resolved_root = self.root.resolve(strict=True)
        self._symlink(self.root / "ok.txt", self.root / "alias")
        real = P._link_target_text
        behaviour = {}

        def patched(path):
            action = behaviour.get(path.name)
            if action is None:
                return real(path)
            if isinstance(action, BaseException):
                raise action
            return action

        cases = [("alias", "link_hop_limit_exceeded"), (os.path.join("missing", "ok.txt"), "link_hop_unresolvable"),
                 (PermissionError(13, "denied"), "link_hop_unreadable")]
        P._link_target_text = patched
        try:
            for action, reason in cases:
                with self.subTest(reason=reason):
                    behaviour["alias"] = action
                    exc = self.assertCode("E_PATH_RESOLUTION_FAILED", P.resolve_existing_path_for_review,
                                          self.root, "alias", expect_field="/path")
                    self.assertEqual(exc.reason, reason)
        finally:
            P._link_target_text = real
        self.assertEqual(P.resolve_existing_path_for_review(self.root, "alias"), resolved_root / "ok.txt")

    def test_A10_link_walk_physical_dotdot_branch(self):
        """01-A10：P4 第 4 轮新增（白盒注入，复审 tests-mutation 视角，变异 P60）。_check_link_hops 中按物理语义处理
        ".." 的分支只在 POSIX 上由 _split_link_target 触发（Windows 的分段已按词法折叠），本机没有 POSIX 环境。这里替换
        protocols._split_link_target，让 alias（→ ok.txt）的目标拆成 POSIX 形式的分段：
        - ["sub", "..", "ok.txt"]：先进入 sub，再按物理上一级回到根，终点是 ok.txt，与 resolve 结果相同 → 接受；
        - ["sub", "..", "hop"]（hop → outside/hop2 → ok.txt）：回到根后经过根外链接 → E_PATH_ESCAPE。
        把 ".." 改成空操作的变异会停在 sub 下，前者变成 link_walk_diverged、后者不再越界，两种情形都会让本用例失败。用后恢复。"""
        resolved_root = self.root.resolve(strict=True)
        self._symlink(self.root / "ok.txt", self.outside / "hop2")
        self._symlink(self.outside / "hop2", self.root / "hop")
        self._symlink(self.root / "ok.txt", self.root / "alias")
        alias_text = os.readlink(self.root / "alias")
        real = P._split_link_target
        parts = {}

        def patched(text, where):
            return (where, list(parts["value"])) if text == alias_text else real(text, where)

        P._split_link_target = patched
        try:
            parts["value"] = ["sub", "..", "ok.txt"]
            self.assertEqual(P.resolve_existing_path_for_review(self.root, "alias"), resolved_root / "ok.txt")
            parts["value"] = ["sub", "..", "hop"]
            exc = self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root, "alias")
            self.assertEqual(exc.reason, "link_hop_outside_trusted_root")
        finally:
            P._split_link_target = real

    def _reparse_object(self, path: Path, buffer: bytes, *, is_dir: bool = False):
        """在本用例 tempfile 目录中建空文件（或空目录）并写入给定的重解析数据；用后先于临时目录的清理删除。
        无法设置时 skip。"""
        if is_dir:
            path.mkdir()
        else:
            path.write_bytes(b"")
        reason = set_reparse_point(path, buffer)
        if reason is not None:
            (os.rmdir if is_dir else os.unlink)(path)
            self.skipTest(f"{reason}，未实测该项")
        self.addCleanup(os.rmdir if is_dir else os.unlink, path)

    @unittest.skipUnless(IS_WINDOWS, "链接目标文本的写法与重解析点标签是 Windows 特有的情形")
    def test_A10_windows_link_target_forms_measured(self):
        """4.1.6、01-A10：P4 第 5 轮新增（裁决 R-P9，复审 fidelity 视角）。黑盒实测：用 FSCTL_SET_REPARSE_POINT 直接写入
        os.symlink 造不出的链接写法（只对本用例 tempfile 目录中的对象），固定本机内核的处理方式，并断言三类写法都
        失败关闭（R-P9：无法确定语义的写法不猜测放行）：
        - 内核拒绝解析的写法（逐字绝对目标中含 ".."、"." 或空分段；不带 \\\\?\\ 的盘符绝对路径，两种标志位；只有根、
          没有盘符的文本配绝对标志；标志位与文本不一致）：resolve(strict=True) 先行失败，入口报 E_PATH_RESOLUTION_FAILED
          或 E_PATH_NOT_FOUND（取决于内核给出的错误），逐跳核对不会被执行。这说明逐字绝对目标中的 ".." 并不按词法
          折叠（P4 第 4 轮文档曾写“绝对目标同样按词法折叠”），_split_link_target 对这些写法返回 None 只是保守兜底；
        - 内核能跟随、但 os.readlink 给出的文本无法确定语义的写法：只有根、没有盘符的文本配相对标志（从链接所在盘的
          根起算），与 NT 命名空间路径 "\\Device\\HarddiskVolumeN\\…"、"\\GLOBAL??\\C:\\…" 配绝对标志，readlink 给出的
          文本形状相同（都以单个 "\\" 开头），而 os.readlink 不给出标志位；以卷 GUID 为目标的 junction（卷挂载点的
          写法）。这些链的最终目标都在根内，入口报 E_PATH_RESOLUTION_FAILED（link_target_form_unsupported）；
        - 名称代理类的第三方重解析点（标签 0x2000ABCD）：os.lstat 报告 S_ISLNK=False 与该标签，本机没有处理它的过滤
          驱动，resolve 失败（入口报 static_resolution_failed）；_link_target_text 对它抛 _UnsupportedLinkKind（有过滤
          驱动、resolve 成功时的入口行为见 test_A10_unrecognized_name_surrogate_reparse_point_fails_closed）。不带名称
          代理位的第三方标签按普通名称处理（返回 None，列入“已知不检测”清单）。
        对照：逐字绝对目标末尾带一个分隔符的目录链接（os.symlink 原样保留）内核照常解析，入口也接受。"""
        import ctypes
        import stat as stat_module

        resolved_root = self.root.resolve(strict=True)
        # Probe the privilege/filesystem capability once.  ``_reparse_object``
        # uses ``subTest`` callers below; a ``skipTest`` raised from a subtest
        # skips only that child and would otherwise let the method continue
        # with an incomplete ``texts`` mapping (and fail with KeyError).
        probe = self.root / "_reparse-capability-probe"
        probe.write_bytes(b"")
        probe_reason = set_reparse_point(probe, symlink_reparse_buffer("ok.txt", relative=True))
        if probe_reason is not None:
            probe.unlink(missing_ok=True)
            self.skipTest(f"{probe_reason}，未实测该项")
        self.addCleanup(probe.unlink)
        where = resolved_root
        drive = resolved_root.drive
        device = ctypes.create_unicode_buffer(1024)
        if not ctypes.windll.kernel32.QueryDosDeviceW(drive, device, len(device)):
            self.skipTest(f"QueryDosDeviceW({drive}) 失败，未实测该项")
        volume = ctypes.create_unicode_buffer(128)
        if not ctypes.windll.kernel32.GetVolumeNameForVolumeMountPointW(drive + "\\", volume, len(volume)):
            self.skipTest(f"GetVolumeNameForVolumeMountPointW({drive}) 失败，未实测该项")
        (self.root / "x").mkdir()
        ok = str(resolved_root / "ok.txt")
        nt_prefix = "\\??\\"
        rooted = ok[len(drive):]  # "\Users\…\repo\ok.txt"
        # (名称, SubstituteName, 相对标志, 入口的错误码, 拆分是否拒绝)
        kernel_rejects = [
            ("abs-dotdot", nt_prefix + str(resolved_root / "x") + "\\..\\ok.txt", False,
             "E_PATH_RESOLUTION_FAILED", True),
            ("abs-dot", nt_prefix + str(resolved_root) + "\\.\\ok.txt", False, "E_PATH_NOT_FOUND", True),
            ("abs-empty", nt_prefix + str(resolved_root) + "\\\\ok.txt", False, "E_PATH_RESOLUTION_FAILED", True),
            ("drive-abs-flag", ok, False, "E_PATH_RESOLUTION_FAILED", True),
            ("drive-rel-flag", ok, True, "E_PATH_RESOLUTION_FAILED", True),
            ("rooted-abs-flag", rooted, False, "E_PATH_NOT_FOUND", True),
            # 标志位与文本不一致：拆分只看文本（os.readlink 不给出标志位），由 resolve 先行失败关闭。
            ("verbatim-rel-flag", nt_prefix + ok, True, "E_PATH_RESOLUTION_FAILED", False),
            ("relative-abs-flag", "ok.txt", False, "E_PATH_RESOLUTION_FAILED", False),
        ]
        for name, substitute, relative, code, split_rejects in kernel_rejects:
            with self.subTest(kernel_rejects=name):
                link = self.root / name
                self._reparse_object(link, symlink_reparse_buffer(substitute, relative=relative))
                with self.assertRaises((OSError, RuntimeError), msg="前提：本机内核拒绝解析这种写法"):
                    link.resolve(strict=True)
                self.assertEqual(P._split_link_target(os.readlink(link), where) is None, split_rejects)
                self.assertCode(code, P.resolve_existing_path_for_review, self.root, name, expect_field="/path")
        kernel_follows = [
            ("rooted-rel-flag", rooted, True),
            # 相对标志下只有根的文本同样按词法折叠 ".."（x 是真实目录，不影响结果）。
            ("rooted-rel-flag-dotdot", str(resolved_root / "x")[len(drive):] + "\\..\\ok.txt", True),
            ("nt-device-abs-flag", device.value + rooted, False),
            ("global-abs-flag", "\\GLOBAL??\\" + ok, False),
        ]
        texts = {}
        for name, substitute, relative in kernel_follows:
            with self.subTest(kernel_follows=name):
                link = self.root / name
                self._reparse_object(link, symlink_reparse_buffer(substitute, relative=relative))
                self.assertEqual(link.resolve(strict=True), resolved_root / "ok.txt",
                                 "前提：本机内核跟随这种写法，最终目标在根内")
                texts[name] = os.readlink(link)
                self.assertIsNone(P._split_link_target(texts[name], where))
                exc = self.assertCode("E_PATH_RESOLUTION_FAILED", P.resolve_existing_path_for_review, self.root,
                                      name, expect_field="/path")
                self.assertEqual(exc.reason, "link_target_form_unsupported")
        for name in ("rooted-rel-flag", "nt-device-abs-flag"):  # 相对与绝对两种标志下文本形状相同，语义无法确定
            self.assertTrue(texts[name].startswith("\\") and not texts[name].startswith("\\\\"), texts[name])
        with self.subTest(kernel_follows="volume-guid-junction"):
            junction = self.root / "jv"
            volume_target = nt_prefix + volume.value[len("\\\\?\\"):] + str(resolved_root / "sub")[len(drive) + 1:]
            self._reparse_object(junction, mount_point_reparse_buffer(volume_target), is_dir=True)
            self.assertEqual((junction / "inner.txt").resolve(strict=True), resolved_root / "sub" / "inner.txt")
            self.assertTrue(os.readlink(junction).startswith("\\\\?\\Volume{"))
            for business_path in ("jv", "jv/inner.txt"):
                exc = self.assertCode("E_PATH_RESOLUTION_FAILED", P.resolve_existing_path_for_review, self.root,
                                      business_path, expect_field="/path")
                self.assertEqual(exc.reason, "link_target_form_unsupported")
        for tag, surrogate in ((0x2000ABCD, True), (0x0000ABCD, False)):
            with self.subTest(third_party_tag=hex(tag)):
                obj = self.root / f"tag-{tag:08x}"
                self._reparse_object(obj, guid_reparse_buffer(tag))
                info = os.lstat(obj)
                self.assertFalse(stat_module.S_ISLNK(info.st_mode))
                self.assertEqual(info.st_reparse_tag, tag)
                with self.assertRaises((OSError, RuntimeError), msg="前提：本机没有处理该标签的过滤驱动"):
                    obj.resolve(strict=True)
                exc = self.assertCode("E_PATH_RESOLUTION_FAILED", P.resolve_existing_path_for_review, self.root,
                                      obj.name, expect_field="/path")
                self.assertEqual(exc.reason, "static_resolution_failed")
                if surrogate:
                    with self.assertRaises(P._UnsupportedLinkKind):
                        P._link_target_text(obj)
                else:
                    self.assertIsNone(P._link_target_text(obj))
        with self.subTest(accepted="verbatim-trailing-separator-directory-link"):
            self._symlink(str(resolved_root / "sub") + "\\", self.root / "dsl", is_dir=True)
            self.assertTrue(os.readlink(self.root / "dsl").endswith("\\"))
            self.assertEqual(P.resolve_existing_path_for_review(self.root, "dsl/inner.txt"),
                             resolved_root / "sub" / "inner.txt")

    def test_A10_unrecognized_name_surrogate_reparse_point_fails_closed(self):
        """4.1.6、01-A10：P4 第 5 轮新增（裁决 R-P9 (1)，复审 fidelity 视角 major；白盒注入）。_link_target_text 原来只认
        symlink 与 junction/挂载点，其他带名称代理位（0x20000000）的重解析点（GLOBAL_REPARSE 0xA0000019、LX_SYMLINK
        0xA000001D、WCI_LINK 0xA0000027、第三方 0x2000ABCD）返回 None，被当作普通名称，逐跳核对跳过它：有过滤驱动
        跟随这类对象的机器上，repo/a → outside/hop2 → repo/ok.txt 这样经根外绕回根内的链被接受。复现方式与复审相同：
        替换 protocols 模块内的 os，让 os.lstat 对 a 返回 S_IFREG 与该标签（CPython 的 lstat 对不是 SYMLINK 的名称
        代理类重解析点正是这样报告的），resolve 仍按真实的链解析。现在失败关闭：E_PATH_RESOLUTION_FAILED
        （link_kind_unsupported），不论目标在根内还是根外，目录分段同样如此。对照：不注入时同一条链 → E_PATH_ESCAPE；
        不带名称代理位的标签（去重 0x80000013、云文件 0x9000001A、AppExecLink 0x8000001B）按普通名称处理，照常接受
        （列入“已知不检测”清单）。用后恢复。"""
        import stat as stat_module

        resolved_root = self.root.resolve(strict=True)
        self._symlink(self.root / "ok.txt", self.outside / "hop2")
        self._symlink(self.outside / "hop2", self.root / "a")
        self._symlink(self.root / "ok.txt", self.root / "alias")
        self._symlink(self.root / "sub", self.outside / "dhop2", is_dir=True)
        self._symlink(self.outside / "dhop2", self.root / "d", is_dir=True)
        for business_path in ("a", "d/inner.txt"):
            with self.subTest(control=business_path):
                exc = self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, self.root, business_path)
                self.assertEqual(exc.reason, "link_hop_outside_trusted_root")
        file_mode, dir_mode = stat_module.S_IFREG | 0o644, stat_module.S_IFDIR | 0o755
        for tag in (0xA0000019, 0xA000001D, 0xA0000027, 0x2000ABCD):
            restore = fake_reparse_tags({"a": (file_mode, tag), "alias": (file_mode, tag),
                                                    "d": (dir_mode, tag)})
            try:
                for business_path in ("a", "alias", "d", "d/inner.txt"):
                    with self.subTest(tag=hex(tag), business_path=business_path):
                        exc = self.assertCode("E_PATH_RESOLUTION_FAILED", P.resolve_existing_path_for_review,
                                              self.root, business_path, expect_field="/path")
                        self.assertEqual(exc.reason, "link_kind_unsupported")
            finally:
                restore()
        for tag in (0x80000013, 0x9000001A, 0x8000001B):
            restore = fake_reparse_tags({"ok.txt": (file_mode, tag)})
            try:
                with self.subTest(non_surrogate=hex(tag)):
                    self.assertEqual(P.resolve_existing_path_for_review(self.root, "ok.txt"),
                                     resolved_root / "ok.txt")
            finally:
                restore()
        self.assertEqual(P.resolve_existing_path_for_review(self.root, "alias"), resolved_root / "ok.txt")

    def _try_symlink(self, target: Path, link: Path, is_dir: bool = False) -> bool:
        try:
            os.symlink(target, link, target_is_directory=is_dir)
        except (OSError, NotImplementedError, AttributeError):
            return False
        return True

    def _lower_equivalent_sibling(self, parent: Path, root_name: str, sibling_name: str):
        """在 parent 下建根与“只在 str.lower() 下同名”的兄弟目录；文件系统把两者视为同一名称时 skip。"""
        root = parent / root_name
        root.mkdir()
        sibling = parent / sibling_name
        try:
            sibling.mkdir()
        except FileExistsError:
            self.skipTest("本文件系统把这两个名称视为同一名称（例如大小写不敏感的 APFS），不存在该别名问题，未实测")
        if os.path.samefile(root, sibling):
            self.skipTest("两个名称解析到同一目录，不存在该别名问题，未实测")
        self.assertEqual(root_name.lower(), sibling_name.lower(),
                         "前提：两个名称在 str.lower() 下相同（修复前 PureWindowsPath 比较的误判来源）")
        (root / "inside.txt").write_bytes(b"inside\n")
        (sibling / "secret.txt").write_bytes(b"outside secret\n")
        return root, sibling

    def _assert_lower_equivalent_sibling_escapes(self, root: Path, sibling: Path):
        exercised = []
        if IS_WINDOWS:
            self._junction(sibling, root / "jn")
            exercised.append("junction")
            for business_path in ("jn", "jn/secret.txt"):
                self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, root,
                                business_path)
        if self._try_symlink(sibling / "secret.txt", root / "x.txt"):
            exercised.append("file-symlink")
            self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, root, "x.txt")
        if self._try_symlink(sibling, root / "dl", is_dir=True):
            exercised.append("dir-symlink")
            self.assertCode("E_PATH_ESCAPE", P.resolve_existing_path_for_review, root,
                            "dl/secret.txt")
        if not exercised:
            self.skipTest("既不能建 junction 也不能建符号链接，未实测")
        # 正例不受影响：根内文件照常解析，返回值相对 resolve 后的根。
        self.assertEqual(P.resolve_existing_path_for_review(root, "inside.txt"),
                         root.resolve(strict=True) / "inside.txt")
        return exercised

    def test_A10_kelvin_sign_sibling_is_escape(self):
        """4.1.6、01-A10：P2 返工新增（复审 paths 视角，blocker）。越界判定不能用 str.lower()：
        根 Kit-root 与兄弟目录 \\u212Ait-root（U+212A 开尔文符号）在 lower() 后相同，在 NTFS 上却是
        两个目录。根内的 junction、文件 symlink、目录 symlink 指向这个兄弟目录 → E_PATH_ESCAPE
        （修复前 PureWindowsPath.relative_to 判为根内并返回根外路径）。"""
        root, sibling = self._lower_equivalent_sibling(self.top, "Kit-root", "\u212Ait-root")
        self._assert_lower_equivalent_sibling_escapes(root, sibling)

    @unittest.skipUnless(IS_WINDOWS, "按目录启用大小写敏感是 NTFS 特性（非 Windows 平台不适用）")
    def test_A10_case_sensitive_directory_sibling_is_escape(self):
        """4.1.6、01-A10：P2 返工新增（复审 paths 视角，blocker）。按目录启用了大小写敏感的 NTFS 目录中
        （例如 WSL 创建的目录），repo 与 REPO 是两个目录：经链接指向 REPO → E_PATH_ESCAPE。
        用 fsutil 对临时目录启用该属性；不可用（权限或系统功能缺失）时 skip 并写明原因。"""
        parent = self.top / "case-sensitive"
        parent.mkdir()
        try:
            result = subprocess.run(["fsutil", "file", "setCaseSensitiveInfo", str(parent), "enable"],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=60)
        except (OSError, subprocess.SubprocessError) as exc:
            self.skipTest(f"无法运行 fsutil（{type(exc).__name__}），大小写敏感目录变体未实测")
        if result.returncode != 0:
            self.skipTest(f"fsutil 未能对临时目录启用大小写敏感（退出码 {result.returncode}，"
                          "可能缺少权限或系统功能），该变体未实测")
        root, sibling = self._lower_equivalent_sibling(parent, "repo", "REPO")
        self._assert_lower_equivalent_sibling_escapes(root, sibling)

    def test_A10_is_within_compares_components_exactly(self):
        """01-A10：P2 返工新增（复审 paths 视角，blocker；白盒）。越界判定的共用实现 _is_within 按路径组件
        逐字比较前缀：lower() 后相同的不同名称、大小写不同的名称、只共享字符串前缀的兄弟目录都算根外；
        根本身与根下路径算根内；Windows 路径去掉 resolve 在超长路径上保留的 \\\\?\\ 前缀后再比较。
        用 PureWindowsPath/PurePosixPath 构造，与平台无关。"""
        from pathlib import PurePosixPath, PureWindowsPath

        root = PureWindowsPath("C:\\Users\\Example\\Code-Kit")
        inside = [root, root / "a.txt", root / "sub" / "b.txt",
                  PureWindowsPath("\\\\?\\C:\\Users\\Example\\Code-Kit\\long\\c.txt")]
        outside = [PureWindowsPath("C:\\Users\\Example\\Code-\u212Ait\\a.txt"),
                   PureWindowsPath("C:\\Users\\Example\\code-kit\\a.txt"),
                   PureWindowsPath("C:\\Users\\Example\\Code-Kit2\\a.txt"),
                   PureWindowsPath("C:\\Users\\Example"),
                   PureWindowsPath("D:\\Users\\Example\\Code-Kit\\a.txt")]
        for target in inside:
            with self.subTest(target=str(target)):
                self.assertIs(P._is_within(root, target), True)
        for target in outside:
            with self.subTest(target=str(target)):
                self.assertIs(P._is_within(root, target), False)
        unc_root = PureWindowsPath("\\\\server\\share\\repo")
        self.assertIs(P._is_within(unc_root, PureWindowsPath("\\\\?\\UNC\\server\\share\\repo\\x")), True)
        self.assertIs(P._is_within(unc_root, PureWindowsPath("\\\\server\\share\\REPO\\x")), False)
        posix_root = PurePosixPath("/srv/Repo")
        self.assertIs(P._is_within(posix_root, PurePosixPath("/srv/Repo/x")), True)
        self.assertIs(P._is_within(posix_root, PurePosixPath("/srv/repo/x")), False)
        self.assertIs(P._is_within(posix_root, PurePosixPath("/srv/Repo2/x")), False)
        if S is not None:
            self.assertIn("_is_within", S._PROTOCOL_NAMES, "sealing 必须与 protocols 共用同一越界判定")
            self.assertFalse(hasattr(S, "_within"), "sealing 不得保留自己的 relative_to 越界判定")

    def test_A10_filesystem_aliases_rejected(self):
        """4.1.5、4.1.6：P2 返工新增（复审 paths 视角，major）。词法合法不代表对象身份唯一：
        大小写不同的拼写在大小写不敏感的文件系统上会解析到同一对象 → E_PATH_COLLISION；物理层核对每一级
        拼写都是目录中登记的真实名称。
        P4（裁决 R-P3）：自动生成的 8.3 短名（例如 LONGFI~1.TXT）已在词法层 → E_PATH_RESERVED，不再访问
        文件系统；这里再用共用的 _check_listed_name 直接核对自动生成的短名在物理层同样被拒绝（白盒）。
        P4 第 3 轮：物理层对手工设置、不含 "~" 的短名的黑盒兜底见 test_A10_manual_short_name_alias_black_box
        与 SealingTests.test_A13_short_name_aliases_rejected_by_all_entries（fsutil file setshortname）。"""
        (self.root / "longfilename_alpha.txt").write_bytes(b"long\n")
        case_alias = self.root / "OK.TXT"
        if case_alias.exists():  # 大小写不敏感的文件系统
            self.assertCode("E_PATH_COLLISION", P.resolve_existing_path_for_review, self.root,
                            "OK.TXT")
            self.assertCode("E_PATH_COLLISION", P.resolve_existing_path_for_review, self.root,
                            "SUB/inner.txt")
        else:
            self.assertCode("E_PATH_NOT_FOUND", P.resolve_existing_path_for_review, self.root,
                            "OK.TXT")
        short = windows_short_name(self.root / "longfilename_alpha.txt")
        if short is None:
            self.skipTest("本卷没有 8.3 短名（或不是 Windows），8.3 别名部分未实测")
        exc = self.assertCode("E_PATH_RESERVED", P.resolve_existing_path_for_review, self.root, short)
        self.assertEqual(exc.reason, "windows_short_name_form")
        self.assertEqual(P.resolve_existing_path_for_review(self.root, "longfilename_alpha.txt"),
                         self.root.resolve(strict=True) / "longfilename_alpha.txt")
        # 物理层兜底：短名确实能在本卷上解析到同一对象，但不是目录中登记的名称 → E_PATH_RESOLUTION_FAILED。
        resolved_root = self.root.resolve(strict=True)
        self.assertTrue((resolved_root / short).exists(), "对照：短名在本卷上可以解析")
        exc = self.assertCode("E_PATH_RESOLUTION_FAILED", P._check_listed_name, resolved_root, short)
        self.assertEqual(exc.reason, "noncanonical_filesystem_alias")
        self.assertIsNone(P._check_listed_name(resolved_root, "longfilename_alpha.txt"))

    def test_A10_manual_short_name_alias_black_box(self):
        """4.1.5、4.1.6：P4 第 3 轮新增（复审 paths 视角）。手工设置、不含 "~" 的短名（fsutil file setshortname）不是
        8.3 形态，词法层接受；它能在本卷上解析到同一对象，但不是目录中登记的名称 → 物理层黑盒报
        E_PATH_RESOLUTION_FAILED（reason=noncanonical_filesystem_alias），文件与目录分段都一样。
        fsutil 不可用或卷未启用 8.3 时 skip 并写明原因。"""
        target = self.root / "longfilename_gamma.txt"
        target.write_bytes(b"gamma\n")
        directory = self.root / "longdirectoryname_delta"
        directory.mkdir()
        (directory / "x.json").write_bytes(b"{}")
        for path, short in ((target, "GAMMAX"), (directory, "DELTAX")):
            reason = set_manual_short_name(path, short)
            if reason is not None:
                self.skipTest(reason + "，手工短名的物理层黑盒部分未实测")
        self.assertEqual(P.validate_business_path("GAMMAX"), "GAMMAX")
        for business_path in ("GAMMAX", "DELTAX/x.json", "DELTAX"):
            with self.subTest(business_path=business_path):
                exc = self.assertCode("E_PATH_RESOLUTION_FAILED", P.resolve_existing_path_for_review,
                                      self.root, business_path, expect_field="/path")
                self.assertEqual(exc.reason, "noncanonical_filesystem_alias")
        self.assertEqual(P.resolve_existing_path_for_review(self.root, "longdirectoryname_delta/x.json"),
                         self.root.resolve(strict=True) / "longdirectoryname_delta" / "x.json")

    def test_F029_replacement_after_check(self):
        """01-F029：检查后父目录/目标被替换——生产安全访问不在 01 实现范围（01-D06）。"""
        self.skipTest("01-D06：01 只提供词法校验与静态解析，不实现抗 TOCTOU 的受控访问；"
                      "F029 由后续访问实现模块验收，此处未测试，不代表通过")

    def test_F030_fifo_device_hardlink(self):
        """01-F030：目标替换为 FIFO/设备/共享硬链接——生产安全访问不在 01 实现范围（01-D06）。"""
        self.skipTest("01-D06：01 不实现文件类型与硬链接受控读写；F030 由后续访问实现模块验收，"
                      "此处未测试，不代表通过")


# ===========================================================================
# ResourceRef、资源依赖（4.2.1–4.2.3、4.2.8；01-F031–F034、F036）
# ===========================================================================
class ResourceRefTests(ProtocolTestCase):
    def _ref(self, **kw):
        ref = json.loads(SAMPLE_RESOURCE_REF)
        ref.update(kw)
        return ref

    def test_A04_doc_sample_4_2_2_resource_ref(self):
        """4.2.2 样例逐字取出：fixture 类型已登记，引用通过校验且与合成字节摘要一致。"""
        ref = P.strict_json_loads(SAMPLE_RESOURCE_REF.encode("utf-8"))
        P.validate_resource_ref(ref, self.reg)
        P.verify_resource_bytes(ref, SYNTHETIC_SAMPLE_BYTES, self.reg)

    def test_A04_default_registry_kinds(self):
        """4.2.1、01-T2：默认登记 fixture、fixture-manifest、public-schema、baseline-evidence、raw-segment，
        都是文件型（缺 path 被拒绝）；未登记类型（如 contract、plugin-lock）被拒绝。"""
        for kind in ("fixture", "fixture-manifest", "public-schema", "baseline-evidence",
                     "raw-segment"):
            with self.subTest(kind=kind):
                ref = self._ref(kind=kind)
                P.validate_resource_ref(ref, self.reg)
                del ref["path"]
                self.assertCode("E_RESOURCE_PATH_REQUIRED", P.validate_resource_ref, ref, self.reg)
        for kind in ("contract", "plugin-lock", "config-snapshot"):
            with self.subTest(kind=kind):
                self.assertCode("E_RESOURCE_KIND", P.validate_resource_ref, self._ref(kind=kind),
                                self.reg)

    def test_A04_default_registry_owners(self):
        """4.2.1、4.4.1、01-T2：默认登记项的 owner_module：fixture 等四类归 01，raw-segment 归 04
        （由 01 预登记封装）；都为文件型。
        P2 调和修正（规格澄清 C-14）：原测试在找不到 get()/[] 时 skip。按名查询接口现固定为
        get(name)（未登记返回 None）、registry[name]（未登记抛 KeyError）、name in registry、
        names()、is_file_kind(name)；不再允许 skip。默认登记恰好是这五类。"""
        expected = {"fixture": "01", "fixture-manifest": "01", "public-schema": "01",
                    "baseline-evidence": "01", "raw-segment": "04"}
        self.assertEqual(set(self.reg.names()), set(expected))
        for name, owner in expected.items():
            with self.subTest(kind=name):
                kind = self.reg.get(name)
                self.assertIs(self.reg[name], kind)
                self.assertIn(name, self.reg)
                self.assertIsNotNone(kind)
                self.assertEqual(kind.name, name)
                self.assertIs(kind.is_file, True)
                self.assertIs(self.reg.is_file_kind(name), True)
                self.assertEqual(kind.owner_module, owner)
                self.assertIsInstance(kind.description, str)
        self.assertIsNone(self.reg.get("contract"))
        self.assertNotIn("contract", self.reg)
        self.assertIs(self.reg.is_file_kind("contract"), False)
        with self.assertRaises(KeyError):
            self.reg["contract"]  # noqa: B018

    def test_A04_registry_immutable_and_extended(self):
        """4.2.1、4.4.3：注册表属于可信核心，构造后不可增删改；extended() 返回新对象，原对象不变。"""
        reg = self.reg
        kind = make_kind(name="plugin-lock", is_file=False, owner_module="06",
                         description="测试用非文件型类型")
        # P2 返工（复审变异 M57/M58）：断言具体异常类型，并覆盖内部表与登记项本身的不可变性。
        with self.assertRaises(TypeError):
            reg["plugin-lock"] = kind
        with self.assertRaises(TypeError):
            del reg["fixture"]
        with self.assertRaises(TypeError):
            reg._items["evil"] = kind  # 内部表是只读映射
        with self.assertRaises(AttributeError):
            reg._items = {}
        fixture = reg.get("fixture")
        with self.assertRaises(AttributeError):
            fixture.is_file = False
        with self.assertRaises(AttributeError):
            del fixture.name
        self.assertIs(reg.is_file_kind("fixture"), True)
        self.assertNotIn("evil", reg)
        extended = reg.extended([kind])
        self.assertIsNot(extended, reg)
        ref = self._ref(kind="plugin-lock", id="plugin-lock-1")
        del ref["path"]
        P.validate_resource_ref(ref, extended)  # 非文件型不要求 path
        self.assertCode("E_RESOURCE_KIND", P.validate_resource_ref, ref, reg)
        self.assertCode("E_RESOURCE_KIND", P.validate_resource_ref, ref, P.build_default_registry())

    def test_A04_registry_extension_cannot_override(self):
        """4.2.1、protocols-api.md 第 8 节与 17 节：P2 返工新增（复审变异 M56，major）。extended() 遇到
        同名项抛 ValueError、不覆盖：06 等下游不能把 01 的 fixture 改成非文件型，也不能给
        run.prepared 加上 vendor 来源；原注册表不变。"""
        # 收尾轮（裁决 R-P10）：登记项声明齐三项，确保这里触发的是“同名不覆盖”（普通 ValueError），
        # 不是“三项未声明”（E_SCHEMA_FIELDS，ProtocolError 也是 ValueError 的子类）。
        with self.assertRaises(ValueError) as caught:
            self.reg.extended([make_kind("fixture", False, "06", "override")])
        self.assertNotIsInstance(caught.exception, P.ProtocolError)
        with self.assertRaises(ValueError) as caught:
            P.ResourceKindRegistry([make_kind("x-kind", True, "06", "a"),
                                    make_kind("x-kind", False, "06", "b")])
        self.assertNotIsInstance(caught.exception, P.ProtocolError)
        self.assertIs(self.reg.get("fixture").is_file, True)
        self.assertEqual(self.reg.get("fixture").owner_module, "01")
        types = P.build_default_event_types()
        with self.assertRaises(ValueError):
            types.extended([P.EventType("run.prepared", frozenset({"core", "vendor"}), None, "vendor")])
        self.assertEqual(types.get("run.prepared").allowed_sources, frozenset({"core"}))
        with self.assertRaises(TypeError):
            types._items["run.prepared"] = None
        with self.assertRaises(AttributeError):
            types.get("run.prepared").allowed_sources = frozenset({"vendor"})

    # -- 收尾轮：裁决 R-P10（文档 4.2.1 注册表的 schema、允许的载荷表示、语义校验器；acceptance.md M-10） --

    def _payload_ref(self, kind, raw, rid="payload-sample-1", path=None):
        ref = {"kind": kind, "id": rid, "sha256": sha(raw)}
        if path is not None:
            ref["path"] = path
        return ref

    def test_A04_r_p10_default_registry_declarations(self):
        """裁决 R-P10：01 预登记的 5 个类型都声明了三项。schema_ref 都为 None；payload_representations 为：
        fixture = json/text/markdown/binary，fixture-manifest = json，public-schema = json，
        baseline-evidence = json/text/binary，raw-segment = binary；只有 fixture-manifest 与 public-schema 有校验器。
        三项都是只读属性，登记项没有未声明的字段。"""
        expected = {
            "fixture": (frozenset({"json", "text", "markdown", "binary"}), False),
            "fixture-manifest": (frozenset({"json"}), True),
            "public-schema": (frozenset({"json"}), True),
            "baseline-evidence": (frozenset({"json", "text", "binary"}), False),
            "raw-segment": (frozenset({"binary"}), False),
        }
        self.assertEqual(P.PAYLOAD_REPRESENTATIONS, ("json", "text", "markdown", "binary"))
        self.assertEqual(P.RESOURCE_KIND_DECLARED_FIELDS,
                         ("schema_ref", "payload_representations", "payload_validator"))
        self.assertEqual(set(self.reg.names()), set(expected))
        for name, (representations, has_validator) in expected.items():
            with self.subTest(kind=name):
                kind = self.reg[name]
                self.assertIsNone(kind.schema_ref)
                self.assertEqual(kind.payload_representations, representations)
                self.assertIs(type(kind.payload_representations), frozenset)
                self.assertIs(callable(kind.payload_validator), has_validator)
                if not has_validator:
                    self.assertIsNone(kind.payload_validator)
                self.assertEqual(kind.undeclared_fields(), ())
                with self.assertRaises(AttributeError):
                    kind.payload_representations = frozenset({"binary"})
                with self.assertRaises(AttributeError):
                    kind.payload_validator = None

    def test_A04_r_p10_registration_requires_three_declarations(self):
        """裁决 R-P10：“其他模块登记自己的类型时必须提供这三项”。未声明任何一项的登记项，经 extended() 或直接构造
        ResourceKindRegistry 都报 E_SCHEMA_FIELDS（field 为首个缺失项，reason=resource_kind_registration_incomplete），
        原注册表不变；显式声明为 None（schema_ref、payload_validator）不算缺失。"""
        full = {"schema_ref": None, "payload_representations": ("json",), "payload_validator": None}
        bare = P.ResourceKind("plugin-lock", False, "06", "插件锁（测试）")
        self.assertEqual(bare.undeclared_fields(), P.RESOURCE_KIND_DECLARED_FIELDS)
        cases = [(bare, "/schema_ref")]
        for missing in P.RESOURCE_KIND_DECLARED_FIELDS:
            declared = {k: v for k, v in full.items() if k != missing}
            cases.append((P.ResourceKind("plugin-lock", False, "06", "插件锁（测试）", **declared), "/" + missing))
        before = self.reg.names()
        for kind, pointer in cases:
            with self.subTest(undeclared=kind.undeclared_fields()):
                exc = self.assertCode("E_SCHEMA_FIELDS", self.reg.extended, [kind], expect_field=pointer)
                self.assertEqual(exc.reason, "resource_kind_registration_incomplete")
                self.assertEqual(exc.phase, "resource")
                exc = self.assertCode("E_SCHEMA_FIELDS", P.ResourceKindRegistry, [kind], expect_field=pointer)
                self.assertEqual(exc.reason, "resource_kind_registration_incomplete")
                self.assertEqual(self.reg.names(), before)
                self.assertNotIn("plugin-lock", self.reg)
        extended = self.reg.extended([P.ResourceKind("plugin-lock", False, "06", "插件锁（测试）", **full)])
        self.assertIn("plugin-lock", extended)
        self.assertEqual(extended["plugin-lock"].undeclared_fields(), ())
        # 登记项的类型仍先于三项检查（TypeError），同名项仍不覆盖（普通 ValueError）。
        with self.assertRaises(TypeError):
            self.reg.extended(["plugin-lock"])
        # 收尾轮返工（复审 tests-mutation 视角）：三项检查先于同名检查。与已有项同名、又未声明三项的登记项报
        # E_SCHEMA_FIELDS（resource_kind_registration_incomplete），不是同名的普通 ValueError。
        for name in ("fixture", "raw-segment"):
            with self.subTest(same_name_undeclared=name):
                exc = self.assertCode("E_SCHEMA_FIELDS", self.reg.extended,
                                      [P.ResourceKind(name, True, "06", "未声明三项的同名项")], expect_field="/schema_ref")
                self.assertEqual(exc.reason, "resource_kind_registration_incomplete")
                exc = self.assertCode("E_SCHEMA_FIELDS", P.ResourceKindRegistry,
                                      [self.reg[name], P.ResourceKind(name, True, "06", "未声明三项的同名项")],
                                      expect_field="/schema_ref")
                self.assertEqual(exc.reason, "resource_kind_registration_incomplete")
        with self.assertRaises(ValueError) as caught:
            extended.extended([P.ResourceKind("plugin-lock", True, "06", "覆盖", **full)])
        self.assertNotIsInstance(caught.exception, P.ProtocolError)

    def test_A04_r_p10_declaration_values_validated(self):
        """裁决 R-P10：显式声明的值不合法时，与 ResourceKind 其他字段一样抛 ValueError（不是 ProtocolError）。
        schema_ref 为 None 或 1–256 个可打印 ASCII（不含空白）；payload_representations 为 json/text/markdown/binary
        的非空子集（str 本身、空集合、未知表示、非 str 元素都拒绝），保存为 frozenset；payload_validator 为可调用对象
        或 None。"""
        bad = [
            {"schema_ref": ""}, {"schema_ref": "has space"}, {"schema_ref": "x" * 257}, {"schema_ref": 1},
            {"schema_ref": "中文"}, {"payload_representations": "json"}, {"payload_representations": b"json"},
            {"payload_representations": []}, {"payload_representations": ["yaml"]},
            {"payload_representations": ["json", 1]}, {"payload_representations": None},
            {"payload_representations": 3}, {"payload_validator": "not-callable"},
        ]
        for change in bad:
            with self.subTest(change=repr(change)[:40]):
                with self.assertRaises(ValueError) as caught:
                    P.ResourceKind("plugin-lock", False, "06", "x", **change)
                self.assertNotIsInstance(caught.exception, P.ProtocolError)
        kind = P.ResourceKind("plugin-lock", False, "06", "x", schema_ref="urn:codekit:plugin-lock:1",
                              payload_representations=["json", "text", "json"], payload_validator=len)
        self.assertEqual(kind.schema_ref, "urn:codekit:plugin-lock:1")
        self.assertEqual(kind.payload_representations, frozenset({"json", "text"}))
        self.assertIs(kind.payload_validator, len)
        P.ResourceKind("plugin-lock", False, "06", "x", schema_ref="x" * 256)

    def test_A04_r_p10_validate_resource_payload_representations(self):
        """裁决 R-P10：validate_resource_payload 先按 verify_resource_bytes 核验引用与字节，再检查载荷表示：
        binary 接受任何字节；json 须通过 strict_json_loads（报其原错误码）；text 与 markdown 须是 UTF-8（否则
        E_JSON_ENCODING，reason=payload_not_utf8_text）；json 与 text 或 markdown 并存时，不是 JSON 的 UTF-8 文本按 text/markdown
        接受。
        返回检查报告：没有校验器时 payload_validated=false，payload_validator 列入 skipped；schema_ref 非 None 时
        resource_schema 列入 skipped（01 不加载 Schema 文件）。"""
        def kind(name, reps, schema_ref=None):
            return make_kind(name, False, "06", "测试", payload_representations=reps, schema_ref=schema_ref)

        # 收尾轮返工（复审 tests-mutation 视角）：另登记 json 与 markdown 并存的类型，固定“text 与 markdown 的字节检查
        # 相同、JSON 解析失败时回退到 UTF-8 文本”对 markdown 同样成立（此前只覆盖 json+text）。
        reg = self.reg.extended([kind("note-json", ("json",)), kind("note-text", ("text",)),
                                 kind("note-markdown", ("markdown",)), kind("note-mixed", ("json", "text")),
                                 kind("note-json-markdown", ("json", "markdown")),
                                 kind("note-binary", ("binary",), schema_ref="urn:codekit:note:1")])
        accepted = [("note-json", b'{"a":1}\n'), ("note-text", "中文\n".encode("utf-8")),
                    ("note-markdown", b"# title\n"), ("note-mixed", b'{"a":1}'), ("note-mixed", b"plain text"),
                    ("note-json-markdown", b'{"a":1}'), ("note-json-markdown", b"# title\n"),
                    ("note-json-markdown", "中文\n".encode("utf-8")),
                    ("note-binary", b"\xff\x00\xfe"), ("note-text", b"")]
        for name, raw in accepted:
            with self.subTest(accepted=name, raw=raw[:10]):
                report = P.validate_resource_payload(self._payload_ref(name, raw), raw, reg)
                self.assertEqual(set(report), {"kind", "payload_validated", "semantic_checks",
                                               "semantic_checks_skipped"})
                self.assertEqual(report["kind"], name)
                self.assertIs(report["payload_validated"], False)
                self.assertIn("payload_representation", report["semantic_checks"])
                self.assertIn("resource_bytes_digest", report["semantic_checks"])
                self.assertIn("payload_validator", report["semantic_checks_skipped"])
                self.assertIs("resource_schema" in report["semantic_checks_skipped"], name == "note-binary")
        rejected = [("note-json", b'{"a":', "E_JSON_SYNTAX"), ("note-json", b'\xef\xbb\xbf{}', "E_JSON_BOM"),
                    ("note-json", b'{"a":1,"a":2}', "E_JSON_DUPLICATE_KEY"), ("note-json", b"", "E_JSON_LIMIT"),
                    ("note-json", b"plain text", "E_JSON_SYNTAX"), ("note-text", b"\xff", "E_JSON_ENCODING"),
                    ("note-markdown", b"\xc3", "E_JSON_ENCODING"), ("note-mixed", b"\xff", "E_JSON_ENCODING"),
                    ("note-json-markdown", b"\xff", "E_JSON_ENCODING")]
        for name, raw, code in rejected:
            with self.subTest(rejected=name, raw=raw[:10]):
                exc = self.assertCode(code, P.validate_resource_payload, self._payload_ref(name, raw), raw, reg)
                if name in ("note-text", "note-markdown"):
                    self.assertEqual(exc.reason, "payload_not_utf8_text")
        # 引用与字节先于载荷表示核验：摘要不符、未登记类型、非 bytes、文件型缺 path。
        raw = b"\xff"
        self.assertCode("E_RESOURCE_HASH_MISMATCH", P.validate_resource_payload,
                        {**self._payload_ref("note-json", raw), "sha256": sha(b"{}")}, raw, reg)
        self.assertCode("E_RESOURCE_KIND", P.validate_resource_payload, self._payload_ref("contract", raw), raw, reg)
        self.assertCode("E_RESOURCE_BYTES", P.validate_resource_payload, self._payload_ref("note-binary", raw),
                        bytearray(raw), reg)
        self.assertCode("E_RESOURCE_PATH_REQUIRED", P.validate_resource_payload, self._payload_ref("fixture", raw),
                        raw, reg)
        with self.assertRaises(TypeError):
            P.validate_resource_payload(self._payload_ref("note-binary", raw), raw, {"note-binary": None})
        # 默认类型：fixture 与 baseline-evidence、raw-segment 接受任意字节（含 binary），没有校验器。
        for name in ("fixture", "baseline-evidence", "raw-segment"):
            with self.subTest(default_kind=name):
                ref = self._payload_ref(name, raw, path="tests/fixtures/codekit01/any.bin")
                report = P.validate_resource_payload(ref, raw, self.reg)
                self.assertIs(report["payload_validated"], False)
                self.assertIn("business_path_lexical", report["semantic_checks"])

    def test_A12_r_p10_fixture_manifest_payload_validator(self):
        """裁决 R-P10、附录 C.1：fixture-manifest 只接受 json，校验器为严格解析加 validate_fixture_manifest_set。整份
        清单通过时 payload_validated=true；清单中的来源违规（E_PROVENANCE_CLAIM）、条目缺 R-P11 字段（E_SCHEMA_FIELDS）、
        清单级重复 fixture_id 都由校验器原样报出（ProtocolError 不被包装）；不是 JSON 的字节先在载荷表示一步报
        E_JSON_SYNTAX。"""
        path = "tests/fixtures/codekit01/manifest.json"

        def manifest_bytes(entries):
            doc = {"schema_version": 1, "record_type": "fixture-manifest-set", "entries": entries}
            return json.dumps(doc, ensure_ascii=False).encode("utf-8")

        good = manifest_bytes([make_manifest_entry()])
        report = P.validate_resource_payload(self._payload_ref("fixture-manifest", good, path=path), good, self.reg)
        self.assertIs(report["payload_validated"], True)
        self.assertIn("payload_validator", report["semantic_checks"])
        self.assertNotIn("payload_validator", report["semantic_checks_skipped"])
        claiming = make_manifest_entry(proves=["real_cli_compatibility"], does_not_prove=[])
        old_shape = make_manifest_entry()
        del old_shape["integrity"]
        second = make_manifest_entry(resource={"id": "synthetic-protocol-sample-2",
                                               "path": "tests/fixtures/codekit01/synthetic/sample-2.json"})
        cases = [([claiming], "E_PROVENANCE_CLAIM", "/entries/0/proves", "synthetic_cannot_prove_real_compatibility"),
                 ([old_shape], "E_SCHEMA_FIELDS", "/entries/0/integrity", "missing_field"),
                 ([make_manifest_entry(), second], "E_SCHEMA_FIELDS", "/entries/1/fixture_id", "duplicate_fixture_id")]
        for entries, code, pointer, reason in cases:
            with self.subTest(reason=reason):
                raw = manifest_bytes(entries)
                exc = self.assertCode(code, P.validate_resource_payload,
                                      self._payload_ref("fixture-manifest", raw, path=path), raw, self.reg,
                                      expect_field=pointer)
                self.assertEqual(exc.reason, reason)
        for raw, code in ((b"not json", "E_JSON_SYNTAX"), (b'{"a":1,"a":1}', "E_JSON_DUPLICATE_KEY"),
                          (b"[]", "E_SCHEMA_TYPE")):
            with self.subTest(raw=raw):
                self.assertCode(code, P.validate_resource_payload,
                                self._payload_ref("fixture-manifest", raw, path=path), raw, self.reg)

    def test_A04_r_p10_public_schema_payload_validator(self):
        """裁决 R-P10：public-schema 只接受 json，校验器为严格解析加 "$id" 核对。本地 Schema 文件
        （schemas/codekit-public-v1.schema.json）通过；"$id" 不同、缺失或不是字符串报 E_SCHEMA_FIELDS（/$id，
        reason=public_schema_id_mismatch）；根不是对象报 E_SCHEMA_TYPE。只核对身份，不做元校验。"""
        path = "schemas/codekit-public-v1.schema.json"
        report = P.validate_resource_payload(self._payload_ref("public-schema", SCHEMA_BYTES, path=path),
                                             SCHEMA_BYTES, self.reg)
        self.assertIs(report["payload_validated"], True)
        for doc in ({**SCHEMA, "$id": "urn:codekit:public-protocol:2"},
                    {k: v for k, v in SCHEMA.items() if k != "$id"}, {**SCHEMA, "$id": 1}):
            raw = json.dumps(doc).encode("utf-8")
            with self.subTest(schema_id=doc.get("$id")):
                exc = self.assertCode("E_SCHEMA_FIELDS", P.validate_resource_payload,
                                      self._payload_ref("public-schema", raw, path=path), raw, self.reg,
                                      expect_field="/$id")
                self.assertEqual(exc.reason, "public_schema_id_mismatch")
        raw = b'["urn:codekit:public-protocol:1"]'
        self.assertCode("E_SCHEMA_TYPE", P.validate_resource_payload,
                        self._payload_ref("public-schema", raw, path=path), raw, self.reg)
        raw = b"# not json\n"
        self.assertCode("E_JSON_SYNTAX", P.validate_resource_payload,
                        self._payload_ref("public-schema", raw, path=path), raw, self.reg)

    def test_A04_r_p10_validator_exceptions_are_wrapped(self):
        """裁决 R-P10：校验器以 (raw, registry) 调用一次；抛出的 ProtocolError 原样传出；抛出其他异常时包装为
        E_SCHEMA_FIELDS（reason=payload_validator_unexpected_exception，phase=resource，field 为 None），错误的
        文字与 to_record() 都不含异常消息中的输入内容，也不链接原异常（__cause__ 与 __context__ 为 None）。"""
        secret = "sk-secret-token-value-123"
        calls = []

        def raising(exc):
            def validator(raw, registry):
                calls.append((raw, registry))
                raise exc
            return validator

        raw = b"payload " + secret.encode("ascii")
        for error in (RuntimeError(secret), KeyError(secret), TypeError(secret), ValueError(secret),
                      RecursionError(secret)):
            with self.subTest(error=type(error).__name__):
                calls.clear()
                reg = self.reg.extended([make_kind("note-checked", False, "06", "测试",
                                                   payload_validator=raising(error))])
                exc = self.assertCode("E_SCHEMA_FIELDS", P.validate_resource_payload,
                                      self._payload_ref("note-checked", raw), raw, reg)
                self.assertEqual(exc.reason, "payload_validator_unexpected_exception")
                self.assertEqual(exc.phase, "resource")
                self.assertIsNone(exc.field)
                self.assertIsNone(exc.__cause__)
                self.assertIsNone(exc.__context__)
                for text in (str(exc), repr(exc), json.dumps(exc.to_record(), ensure_ascii=False)):
                    self.assertNotIn(secret, text)
                self.assertEqual(len(calls), 1)
                self.assertIs(calls[0][0], raw)
                self.assertIs(calls[0][1], reg)
        original = P.ProtocolError("E_USAGE_VALUE", field="/x", reason="custom_reason")
        reg = self.reg.extended([make_kind("note-checked", False, "06", "测试", payload_validator=raising(original))])
        exc = self.assertCode("E_USAGE_VALUE", P.validate_resource_payload, self._payload_ref("note-checked", raw),
                              raw, reg, expect_field="/x")
        self.assertIs(exc, original)
        passing = self.reg.extended([make_kind("note-checked", False, "06", "测试",
                                               payload_validator=lambda raw, registry: None)])
        report = P.validate_resource_payload(self._payload_ref("note-checked", raw), raw, passing)
        self.assertIs(report["payload_validated"], True)

    def test_A04_resource_ref_type_and_fields(self):
        """4.2.1、附录 A resourceRef：非对象 → E_SCHEMA_TYPE；缺必需字段或有未知字段 → E_SCHEMA_FIELDS。"""
        for value in ([], None, "fixture", 1):
            with self.subTest(value=value):
                self.assertCode("E_SCHEMA_TYPE", P.validate_resource_ref, value, self.reg)
        for name in ("kind", "id", "sha256"):
            ref = self._ref()
            del ref[name]
            with self.subTest(missing=name):
                self.assertCode("E_SCHEMA_FIELDS", P.validate_resource_ref, ref, self.reg)

    def test_F031_file_resource_requires_path(self):
        """01-F031：文件资源缺 path → E_RESOURCE_PATH_REQUIRED。"""
        ref = self._ref()
        del ref["path"]
        self.assertCode("E_RESOURCE_PATH_REQUIRED", P.validate_resource_ref, ref, self.reg)

    def test_F032_unknown_kind_and_unknown_field(self):
        """01-F032：未登记 kind → E_RESOURCE_KIND；未知顶层字段 → E_SCHEMA_FIELDS；不静默丢字段。"""
        unknown_kind = self._ref(kind="unregistered")
        self.assertCode("E_RESOURCE_KIND", P.validate_resource_ref, unknown_kind, self.reg,
                        expect_field="/kind")
        extra = self._ref(approved=True)
        before = copy.deepcopy(extra)
        self.assertCode("E_SCHEMA_FIELDS", P.validate_resource_ref, extra, self.reg)
        self.assertUnchanged(before, extra)

    def test_A04_resource_field_syntax(self):
        """4.2.1：kind/id/sha256 语法错误 → E_RESOURCE_FIELD，field 指向字段；path 按业务路径规则。"""
        cases = [
            ({"kind": "Fixture"}, "/kind"), ({"kind": "fixture\n"}, "/kind"), ({"kind": 1}, "/kind"),
            ({"id": "-bad"}, "/id"), ({"id": "Bad"}, "/id"), ({"id": "a" * 129}, "/id"),
            ({"sha256": "A" * 64}, "/sha256"), ({"sha256": "0" * 63}, "/sha256"),
            ({"sha256": "sha256:" + "0" * 64}, "/sha256"), ({"sha256": "0" * 64 + "\n"}, "/sha256"),
            ({"sha256": "placeholder"}, "/sha256"),
        ]
        for change, pointer in cases:
            with self.subTest(change=change):
                self.assertCode("E_RESOURCE_FIELD", P.validate_resource_ref, self._ref(**change),
                                self.reg, expect_field=pointer)
        self.assertCode("E_PATH_SYNTAX", P.validate_resource_ref, self._ref(path="../x"), self.reg)
        self.assertCode("E_PATH_RESERVED", P.validate_resource_ref, self._ref(path="NUL.txt"),
                        self.reg)

    def test_F033_crlf_changes_hash(self):
        """01-F033 / 4.2.4：只把 LF 改成 CRLF → E_RESOURCE_HASH_MISMATCH；引用中的期望摘要不被重算。"""
        raw = b"line one\nline two\n"
        ref = self._ref(id="sample-crlf", sha256=sha(raw), path="fixtures/sample.txt")
        before = copy.deepcopy(ref)
        P.verify_resource_bytes(ref, raw, self.reg)
        self.assertCode("E_RESOURCE_HASH_MISMATCH", P.verify_resource_bytes, ref,
                        raw.replace(b"\n", b"\r\n"), self.reg, expect_field="/sha256")
        self.assertUnchanged(before, ref)

    def test_F034_sha_format_vs_content_mismatch(self):
        """01-F034：摘要大写或截断是格式错误（E_RESOURCE_FIELD）；长度正确但值不符是内容错误
        （E_RESOURCE_HASH_MISMATCH）。"""
        raw = b"payload\n"
        good = self._ref(id="sample-1", sha256=sha(raw), path="fixtures/sample.txt")
        self.assertCode("E_RESOURCE_FIELD", P.verify_resource_bytes,
                        {**good, "sha256": good["sha256"].upper()}, raw, self.reg)
        self.assertCode("E_RESOURCE_FIELD", P.verify_resource_bytes,
                        {**good, "sha256": good["sha256"][:16]}, raw, self.reg)
        self.assertCode("E_RESOURCE_HASH_MISMATCH", P.verify_resource_bytes,
                        {**good, "sha256": sha(b"other\n")}, raw, self.reg)

    def test_A04_verify_requires_bytes(self):
        """B.2：待核验内容必须是 bytes；bytearray、str、memoryview → E_RESOURCE_BYTES。"""
        ref = P.strict_json_loads(SAMPLE_RESOURCE_REF.encode())
        for raw in (bytearray(SYNTHETIC_SAMPLE_BYTES), SYNTHETIC_SAMPLE_BYTES.decode(),
                    memoryview(SYNTHETIC_SAMPLE_BYTES), None):
            with self.subTest(raw=type(raw).__name__):
                self.assertCode("E_RESOURCE_BYTES", P.verify_resource_bytes, ref, raw, self.reg)

    def test_F036_resource_dag_order(self):
        """4.2.8：无环依赖返回确定性拓扑序，被引用者在前（配置/合同 → 审核 → 执行 → 集成）。"""
        edges = {
            "integration": ["execution"],
            "execution": ["review"],
            "review": ["contract", "config-snapshot"],
            "contract": [],
            "config-snapshot": [],
        }
        order = P.check_resource_dag(edges)
        self.assertEqual(sorted(order), sorted(edges))
        pos = {name: i for i, name in enumerate(order)}
        for node, deps in edges.items():
            for dep in deps:
                self.assertLess(pos[dep], pos[node], f"{dep} 应排在 {node} 之前")
        self.assertEqual(P.check_resource_dag(edges), order)

    def test_F036_resource_cycles(self):
        """01-F036 / 4.2.8：自环或多节点环 → E_RESOURCE_CYCLE，details 指出环上一个节点。
        P2 调和修正（规格澄清 C-15）：原测试只在 to_record 文本里查找节点名。现固定为
        details.field 是指向环上某个节点的 JSON Pointer "/<节点>"（~ 与 / 按 RFC 6901 转义）。"""
        exc = self.assertCode("E_RESOURCE_CYCLE", P.check_resource_dag, {"node-self": ["node-self"]},
                              expect_field="/node-self")
        self.assertEqual(exc.to_record()["details"]["field"], "/node-self")
        edges = {"node-alpha": ["node-beta"], "node-beta": ["node-gamma"],
                 "node-gamma": ["node-alpha"], "node-delta": ["node-alpha"]}
        exc = self.assertCode("E_RESOURCE_CYCLE", P.check_resource_dag, edges)
        self.assertIn(exc.field, ("/node-alpha", "/node-beta", "/node-gamma"),
                      "错误详情应指出环上的节点")
        exc = self.assertCode("E_RESOURCE_CYCLE", P.check_resource_dag, {"a/b": ["a/b"]})
        self.assertEqual(exc.field, "/a~1b")

    def test_F036_referenced_only_nodes_and_determinism(self):
        """4.2.8：P2 调和新增（规格澄清 C-15）。只作为被引用方出现、自身不是键的节点也进入拓扑序
        （排在引用者之前）；结果与映射的插入次序无关（确定性）。"""
        edges = {"review": ["contract", "config-snapshot"], "execution": ["review"]}
        order = P.check_resource_dag(edges)
        self.assertEqual(sorted(order), ["config-snapshot", "contract", "execution", "review"])
        pos = {name: i for i, name in enumerate(order)}
        self.assertLess(pos["contract"], pos["review"])
        self.assertLess(pos["config-snapshot"], pos["review"])
        self.assertLess(pos["review"], pos["execution"])
        reordered = {"execution": ["review"], "review": ["config-snapshot", "contract"]}
        self.assertEqual(P.check_resource_dag(reordered), order)
        self.assertEqual(P.check_resource_dag({}), [])
        # P2 返工（复审变异 M62）：子节点顺序也不影响结果（原用例只重排了“起点本身先被访问”的情形）。
        self.assertEqual(P.check_resource_dag({"a": ["c", "b"]}), ["b", "c", "a"])
        self.assertEqual(P.check_resource_dag({"a": ["b", "c"]}), ["b", "c", "a"])
        # P4（第 2 轮复审 tests-mutation P105）：彼此独立的节点拓扑序不唯一，结果仍与插入次序无关。
        self.assertEqual(P.check_resource_dag({"b": [], "a": []}), ["a", "b"])
        self.assertEqual(P.check_resource_dag({"b": [], "a": []}), P.check_resource_dag({"a": [], "b": []}))
        self.assertEqual(P.check_resource_dag({"z": ["y"], "b": [], "a": ["y"]}),
                         P.check_resource_dag({"a": ["y"], "b": [], "z": ["y"]}))


# ===========================================================================
# Git OID（4.2.3；01-F035）
# ===========================================================================
class GitOidTests(ProtocolTestCase):
    def test_A04_validate_git_oid(self):
        """4.2.3：sha1 为 40 位、sha256 为 64 位小写十六进制完整 OID。"""
        self.assertEqual(P.validate_git_oid(FULL_SHA1_OID, "sha1"), FULL_SHA1_OID)
        self.assertEqual(P.validate_git_oid("b" * 64, "sha256"), "b" * 64)

    def test_A04_git_oid_rejections(self):
        """4.2.3：分支名、短 OID、大写、revision 表达式、前导 -、长度与格式不符、非 str → E_GIT_OID_SYNTAX。"""
        bad = ["HEAD", "main", FULL_SHA1_OID[:7], FULL_SHA1_OID.upper(), "HEAD^{commit}",
               "-" + "a" * 39, FULL_SHA1_OID + "\n", "a" * 64, "", None, FULL_SHA1_OID.encode(),
               "--output=x"]
        for value in bad:
            with self.subTest(value=value):
                self.assertCode("E_GIT_OID_SYNTAX", P.validate_git_oid, value, "sha1")
        self.assertCode("E_GIT_OID_SYNTAX", P.validate_git_oid, FULL_SHA1_OID, "sha256")

    def test_A04_git_format_unsupported(self):
        """4.2.3：未知对象格式 → E_GIT_FORMAT_UNSUPPORTED，不按长度猜格式。"""
        for fmt in ("sha512", "md5", "SHA1", "", None):
            with self.subTest(fmt=fmt):
                self.assertCode("E_GIT_FORMAT_UNSUPPORTED", P.validate_git_oid, FULL_SHA1_OID, fmt)

    def test_A04_git_cat_file_argv(self):
        """4.2.3：受信 argv 为 git cat-file -t <已校验 OID>，不经 shell；非法 OID 先被拒绝。"""
        self.assertEqual(P.git_cat_file_type_argv(FULL_SHA1_OID, "sha1"),
                         ["git", "cat-file", "-t", FULL_SHA1_OID])
        self.assertCode("E_GIT_OID_SYNTAX", P.git_cat_file_type_argv, "--output=x", "sha1")

    def test_F035_interpret_constructed_output(self):
        """01-F035 / 4.2.3：commit/tree 字段类型错置 → E_GIT_OBJECT_TYPE；对象不存在（非零或无退出码）
        → E_GIT_OBJECT_MISSING。"""
        self.assertIsNone(P.interpret_git_object_type("commit", 0, b"commit\n"))
        self.assertIsNone(P.interpret_git_object_type("tree", 0, b"tree\n"))
        for expected, out in (("tree", b"commit\n"), ("commit", b"tree\n"),
                              ("commit", b"tag\n"), ("commit", b"blob\n")):
            with self.subTest(expected=expected, out=out):
                self.assertCode("E_GIT_OBJECT_TYPE", P.interpret_git_object_type, expected, 0, out)
        for rc in (128, 1, None):
            with self.subTest(rc=rc):
                self.assertCode("E_GIT_OBJECT_MISSING", P.interpret_git_object_type, "commit", rc,
                                b"")
        # P2 调和新增（规格澄清 C-16）：expected_type 只能是 commit/tree，其他 → E_COMPAT_UNSUPPORTED；
        # 输出允许一个结尾 LF 或 CRLF，其他多余内容 → E_GIT_OBJECT_TYPE。
        for expected in ("blob", "tag", "Commit", "", None):
            with self.subTest(expected=expected):
                self.assertCode("E_COMPAT_UNSUPPORTED", P.interpret_git_object_type, expected, 0,
                                b"commit\n")
        self.assertIsNone(P.interpret_git_object_type("commit", 0, b"commit\r\n"))
        self.assertIsNone(P.interpret_git_object_type("tree", 0, b"tree"))
        for out in (b"commit\n\n", b" commit\n", b"commit \n", b"", "commit\n"):
            with self.subTest(out=out):
                self.assertCode("E_GIT_OBJECT_TYPE", P.interpret_git_object_type, "commit", 0, out)

    def test_F035_real_git_temp_repository(self):
        """01-F035 / 4.2.3：在临时仓库真实运行 git cat-file -t，验证解释结果（commit 冒充 tree 等）。"""
        git = shutil.which("git")
        if not git:
            self.skipTest("本机没有 git，只做构造输出的解释测试")
        with tempfile.TemporaryDirectory(prefix="codekit-git-") as td:
            top = Path(td)
            (top / "gitconfig").write_bytes(b"")
            env = minimal_child_env({
                "PATH": os.path.dirname(git), "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": str(top / "gitconfig"), "HOME": str(top),
                "GIT_TERMINAL_PROMPT": "0",
            })

            def run(args, cwd):
                return subprocess.run([git, *args], cwd=cwd, env=env, capture_output=True,
                                      timeout=60)

            repo = top / "repo"
            self.assertEqual(run(["init", "-q", str(repo)], top).returncode, 0)
            fmt = run(["rev-parse", "--show-object-format"], repo).stdout.decode().strip()
            if fmt not in ("sha1", "sha256"):
                self.skipTest(f"无法确定临时仓库对象格式：{fmt!r}")
            tree = run(["write-tree"], repo).stdout.decode().strip()
            commit = run(["-c", "user.name=codekit-test", "-c",
                          "user.email=codekit-test@example.invalid", "commit-tree", tree, "-m",
                          "fixture"], repo).stdout.decode().strip()
            P.validate_git_oid(tree, fmt)
            P.validate_git_oid(commit, fmt)

            def cat(oid):
                argv = P.git_cat_file_type_argv(oid, fmt)
                self.assertEqual(argv[0], "git")
                proc = subprocess.run([git, *argv[1:]], cwd=repo, env=env, capture_output=True,
                                      timeout=60)
                return proc.returncode, proc.stdout

            rc, out = cat(commit)
            P.interpret_git_object_type("commit", rc, out)
            self.assertCode("E_GIT_OBJECT_TYPE", P.interpret_git_object_type, "tree", rc, out)
            rc, out = cat(tree)
            P.interpret_git_object_type("tree", rc, out)
            self.assertCode("E_GIT_OBJECT_TYPE", P.interpret_git_object_type, "commit", rc, out)
            missing = "f" * (40 if fmt == "sha1" else 64)
            rc, out = cat(missing)
            self.assertCode("E_GIT_OBJECT_MISSING", P.interpret_git_object_type, "commit", rc, out)


# ===========================================================================
# 时间（4.3.1、A.2）
# ===========================================================================
class TimeTests(ProtocolTestCase):
    def test_A11_format_observed_at(self):
        """4.3.1：observed_at 为 UTC，格式 YYYY-MM-DDTHH:MM:SS.ffffffZ；带时区的时间先转 UTC。"""
        utc = _dt.timezone.utc
        self.assertEqual(P.format_observed_at(_dt.datetime(2026, 9, 25, tzinfo=utc)),
                         "2026-09-25T00:00:00.000000Z")
        plus8 = _dt.timezone(_dt.timedelta(hours=8))
        self.assertEqual(P.format_observed_at(_dt.datetime(2026, 9, 25, 8, 0, 0, 123456, tzinfo=plus8)),
                         "2026-09-25T00:00:00.123456Z")

    def test_A11_format_rejects_naive(self):
        """4.3.1：不带时区的 datetime 无法确定 UTC → E_TIME_FORMAT。"""
        self.assertCode("E_TIME_FORMAT", P.format_observed_at, _dt.datetime(2026, 9, 25))

    def test_A11_format_utc_conversion_overflow(self):
        """4.3.1：P4 新增（第 2 轮复审 tests-mutation Q022）。转成 UTC 时越出 datetime 可表示的年份范围
        （9999 年末的西五区、0001 年初的东五区）→ E_TIME_FORMAT，不泄漏原生 OverflowError；边界内照常格式化。"""
        west = _dt.timezone(_dt.timedelta(hours=-5))
        east = _dt.timezone(_dt.timedelta(hours=5))
        for value in (_dt.datetime(9999, 12, 31, 23, 0, tzinfo=west), _dt.datetime(1, 1, 1, 0, 0, tzinfo=east)):
            with self.subTest(value=repr(value)):
                exc = self.assertCode("E_TIME_FORMAT", P.format_observed_at, value)
                self.assertEqual(exc.reason, "utc_conversion_failed")
        self.assertEqual(P.format_observed_at(_dt.datetime(9999, 12, 31, 18, 0, tzinfo=west)),
                         "9999-12-31T23:00:00.000000Z")
        self.assertEqual(P.format_observed_at(_dt.datetime(1, 1, 1, 5, 0, tzinfo=east)),
                         "0001-01-01T00:00:00.000000Z")

    def test_A11_parse_observed_at(self):
        """4.3.1、A.2：严格格式且日历有效；解析结果为 UTC 时间并可往返。"""
        value = P.parse_observed_at("2026-09-25T00:00:00.000000Z")
        self.assertEqual(value, _dt.datetime(2026, 9, 25, tzinfo=_dt.timezone.utc))
        self.assertEqual(value.utcoffset(), _dt.timedelta(0))
        self.assertEqual(P.format_observed_at(value), "2026-09-25T00:00:00.000000Z")
        P.parse_observed_at("2024-02-29T23:59:59.999999Z")

    def test_A11_parse_rejections(self):
        """A.2“日历日期确实有效”与附录 A pattern：格式或日历无效 → E_TIME_FORMAT。"""
        bad = ["2026-02-30T00:00:00.000000Z", "2025-02-29T00:00:00.000000Z",
               "2026-13-01T00:00:00.000000Z", "2026-09-25T24:00:00.000000Z",
               "2026-09-25T00:00:00Z", "2026-09-25T00:00:00.000Z", "2026-09-25T00:00:00.000000z",
               "2026-09-25T00:00:00.000000+00:00", "2026-09-25 00:00:00.000000Z",
               "2026-09-25T00:00:00.000000Z\n", "\u0662\u0660\u0662\u0666-09-25T00:00:00.000000Z",
               "", None, 20260925]
        for value in bad:
            with self.subTest(value=value):
                self.assertCode("E_TIME_FORMAT", P.parse_observed_at, value)


# ===========================================================================
# 事件（4.3.1–4.3.5；01-F037–F042，01-A11）
# ===========================================================================
class EventTests(ProtocolTestCase):
    def setUp(self):
        super().setUp()
        self.types = P.build_default_event_types()
        self.vendor_types = self.types.extended([
            P.EventType(name="vendor.message", allowed_sources=frozenset({"vendor"}),
                        payload_validator=None, category="vendor"),
        ])

    def test_A11_doc_sample_4_3_1_run_event(self):
        """4.3.1 样例逐字取出：核心事件通过封装校验；未给类型注册表时 payload 未被验证。"""
        ev = P.strict_json_loads(SAMPLE_RUN_EVENT.encode("utf-8"))
        before = copy.deepcopy(ev)
        result = P.validate_run_event(ev, registry=self.reg)
        self.assertIs(result["payload_validated"], False)
        result = P.validate_run_event(ev, registry=self.reg, event_types=self.types,
                                      context=make_context())
        self.assertIs(result["payload_validated"], True)
        self.assertUnchanged(before, ev)

    def test_A11_event_structure(self):
        """附录 A event：字段封闭；seq 为精确整数且 ≥1；observed_at 严格格式；枚举与长度限制。"""
        self.assertCode("E_SCHEMA_FIELDS", P.validate_run_event, make_event(extra=1),
                        registry=self.reg)
        ev = make_event()
        del ev["adapter_revision"]
        self.assertCode("E_SCHEMA_FIELDS", P.validate_run_event, ev, registry=self.reg)
        self.assertCode("E_INTEGER_RANGE", P.validate_run_event, make_event(seq=0), registry=self.reg)
        self.assertCode("E_INTEGER_RANGE", P.validate_run_event, make_event(seq=2**53),
                        registry=self.reg)
        for seq in (True, 1.0, "1"):
            with self.subTest(seq=seq):
                self.assertCode("E_SCHEMA_TYPE", P.validate_run_event, make_event(seq=seq),
                                registry=self.reg)
        self.assertCode("E_TIME_FORMAT", P.validate_run_event,
                        make_event(observed_at="2026-09-25T00:00:00Z"), registry=self.reg)
        self.assertCode("E_ID_SYNTAX", P.validate_run_event, make_event(request_id="req-1"),
                        registry=self.reg)
        # P2 调和（规格澄清 C-03）：原测试只断言“被拒绝”。枚举外的值、字符串长度越界、数组超过上限
        # → E_SCHEMA_FIELDS；payload 不是对象 → E_SCHEMA_TYPE；field 指向出错字段。
        for change, code, pointer in (({"role": "admin"}, "E_SCHEMA_FIELDS", "/role"),
                                      ({"source_kind": "model"}, "E_SCHEMA_FIELDS", "/source_kind"),
                                      ({"integrity": "done"}, "E_SCHEMA_FIELDS", "/integrity"),
                                      ({"type": ""}, "E_SCHEMA_FIELDS", "/type"),
                                      ({"type": "x" * 97}, "E_SCHEMA_FIELDS", "/type"),
                                      ({"type": 1}, "E_SCHEMA_TYPE", "/type"),
                                      ({"adapter_revision": ""}, "E_SCHEMA_FIELDS",
                                       "/adapter_revision"),
                                      ({"payload": []}, "E_SCHEMA_TYPE", "/payload"),
                                      ({"raw_refs": [make_span()] * 257}, "E_SCHEMA_FIELDS",
                                       "/raw_refs")):
            with self.subTest(change=repr(change)[:60]):
                self.assertCode(code, P.validate_run_event, make_event(**change), registry=self.reg,
                                expect_field=pointer)
        P.validate_run_event(make_event(role=None), registry=self.reg)
        P.validate_run_event(make_event(raw_refs=[make_span()] * 256), registry=self.reg)

    def test_A11_context_binding(self):
        """4.3.1、4.3.5：request/run 由受信上下文绑定，厂商或核心记录都不能改绑定；
        role 非空时必须等于上下文角色 → 否则 E_CONTEXT_BINDING。"""
        ctx = make_context()
        P.validate_run_event(make_event(), registry=self.reg, context=ctx)
        P.validate_run_event(make_event(role=None), registry=self.reg, context=ctx)
        for change in ({"request_id": OTHER_REQ}, {"run_id": OTHER_RUN}, {"role": "executor"}):
            with self.subTest(change=change):
                self.assertCode("E_CONTEXT_BINDING", P.validate_run_event, make_event(**change),
                                registry=self.reg, context=ctx)
                self.assertCode("E_CONTEXT_BINDING", P.validate_run_event,
                                make_vendor_event(**change), registry=self.reg, context=ctx)

    def test_A11_vendor_event_requires_role(self):
        """4.3.1“role：planner/executor/observer；无角色核心事件可为空”、4.3.5：P4 第 3 轮新增（复审 fidelity 与
        events-usage 视角，major）。只有核心事件的 role 可以为 null；vendor 事件把 role 置空就能脱离角色绑定（context
        只在 role 非空时核对），所以 vendor 事件 role=None → E_SCHEMA_FIELDS（/role，
        reason=vendor_event_requires_role），不论是否给出 context、event_types，经公共入口同样如此。
        vendor 事件带 role 时仍须等于 context.role。"""
        ctx = make_context()
        executor_ctx = make_executor_context()
        vendor = make_vendor_event(role=None)
        self.assertEqual(MINI.errors_for_def(vendor, "event"), [], "JSON Schema 允许 null：这是 Schema 之外的领域检查")
        calls = [
            lambda: P.validate_run_event(vendor, registry=self.reg),
            lambda: P.validate_run_event(vendor, registry=self.reg, context=ctx),
            lambda: P.validate_run_event(vendor, registry=self.reg, context=executor_ctx),
            lambda: P.validate_run_event(vendor, registry=self.reg, event_types=self.vendor_types,
                                         context=ctx),
            lambda: P.validate_public_record(vendor, expected_record_type="run-event", registry=self.reg,
                                             context=ctx),
        ]
        for index, call in enumerate(calls):
            with self.subTest(call=index):
                exc = self.assertCode("E_SCHEMA_FIELDS", call, expect_field="/role")
                self.assertEqual(exc.reason, "vendor_event_requires_role")
        # 核心事件的 role 仍可为 null（无角色核心事件），有 context 时同样通过。
        P.validate_run_event(make_event(role=None), registry=self.reg, context=ctx)
        # vendor 事件带 role：必须等于 context.role。
        P.validate_run_event(make_vendor_event(), registry=self.reg, context=ctx)
        P.validate_run_event(make_vendor_event(role="executor"), registry=self.reg, context=executor_ctx)
        self.assertCode("E_CONTEXT_BINDING", P.validate_run_event, make_vendor_event(role="executor"),
                        registry=self.reg, context=ctx, expect_field="/role")

    def test_A11_event_type_registry(self):
        """4.3.1、01-D07：给出事件类型注册表时，type 必须已登记（E_EVENT_TYPE_UNKNOWN）；
        默认只登记 run.prepared（核心类型），其余由 04 登记；注册表不可变，extended() 返回新对象。"""
        P.validate_run_event(make_event(), registry=self.reg, event_types=self.types)
        self.assertCode("E_EVENT_TYPE_UNKNOWN", P.validate_run_event,
                        make_vendor_event(), registry=self.reg, event_types=self.types)
        P.validate_run_event(make_vendor_event(), registry=self.reg, event_types=self.vendor_types)
        self.assertIsNot(self.vendor_types, self.types)

    def test_A11_event_source_kind(self):
        """4.3.1、4.3.5：source_kind 必须在类型允许的来源中 → 否则 E_EVENT_SOURCE
        （核心记录不能冒充厂商类型，厂商记录也不能冒充核心类型）。"""
        core_as_vendor = make_event(type="vendor.message", payload={"text": "hello"})
        self.assertCode("E_EVENT_SOURCE", P.validate_run_event, core_as_vendor,
                        registry=self.reg, event_types=self.vendor_types)
        vendor_as_core = make_vendor_event(type="run.prepared", payload={"example_only": True})
        self.assertCode("E_EVENT_SOURCE", P.validate_run_event, vendor_as_core,
                        registry=self.reg, event_types=self.vendor_types)

    def test_A11_payload_validator_invoked(self):
        """4.3.1“payload 必须按对应类型验证”：类型的 payload_validator 被调用，其错误原样传播；
        run.prepared 的 payload 值必须是 JSON 原生值。"""
        calls = []

        def validator(payload, *args, **kwargs):
            calls.append(copy.deepcopy(payload))
            P.require_int(payload.get("k"), field="/payload/k", minimum=0)

        types = self.types.extended([
            P.EventType(name="demo.strict", allowed_sources=frozenset({"core"}),
                        payload_validator=validator, category="core"),
        ])
        ok = P.validate_run_event(make_event(type="demo.strict", payload={"k": 1}),
                                  registry=self.reg, event_types=types)
        self.assertIs(ok["payload_validated"], True)
        self.assertIn({"k": 1}, calls)
        self.assertCode("E_SCHEMA_TYPE", P.validate_run_event,
                        make_event(type="demo.strict", payload={}), registry=self.reg,
                        event_types=types)
        self.assertCode("E_EVENT_TYPE_UNKNOWN", P.validate_run_event,
                        make_event(type="demo.strict", payload={"k": 1}), registry=self.reg,
                        event_types=self.types)
        # P2 调和（规格澄清 C-03）：非原生载荷值在封装层的 check_json_value 即被拒绝 → E_JSON_VALUE_TYPE。
        self.assertCode("E_JSON_VALUE_TYPE", P.validate_run_event, make_event(payload={"x": (1, 2)}),
                        registry=self.reg, event_types=self.types, expect_field="/payload/x")

    def test_A11_run_prepared_validator_called_directly(self):
        """4.3.1、01-D07：P4 新增（第 2 轮复审 tests-mutation Q012）。04 或其他调用方单独调用 run.prepared 的
        载荷校验器时，它自己拒绝非对象载荷（E_SCHEMA_TYPE，/payload）与非原生值（E_JSON_VALUE_TYPE），
        不依赖 validate_run_event 的前置检查；合法载荷返回 None。"""
        validator = self.types.get("run.prepared").payload_validator
        for bad in ([], "x", None, 1):
            with self.subTest(payload=repr(bad)):
                self.assertCode("E_SCHEMA_TYPE", validator, bad, expect_field="/payload")
        self.assertCode("E_JSON_VALUE_TYPE", validator, {"x": (1,)}, expect_field="/payload/x")
        self.assertIsNone(validator({"example_only": True}))

    def test_A11_vendor_evidence_required(self):
        """A.2 vendor 事件：解析修订必须已知；声称 complete 时必须有可引用来源
        → 否则 E_EVENT_EVIDENCE_MISSING；未声称完整（incomplete/pending）时可无 raw_refs。"""
        P.validate_run_event(make_vendor_event(), registry=self.reg)
        self.assertCode("E_EVENT_EVIDENCE_MISSING", P.validate_run_event,
                        make_vendor_event(adapter_revision=None), registry=self.reg)
        self.assertCode("E_EVENT_EVIDENCE_MISSING", P.validate_run_event,
                        make_vendor_event(raw_refs=[]), registry=self.reg)
        self.assertCode("E_EVENT_EVIDENCE_MISSING", P.validate_run_event,
                        make_vendor_event(raw_refs=[]), registry=self.reg,
                        event_types=self.vendor_types)
        for integrity in ("incomplete", "pending"):
            with self.subTest(integrity=integrity):
                P.validate_run_event(make_vendor_event(raw_refs=[], integrity=integrity),
                                     registry=self.reg)

    def test_A12_raw_span_structure_and_range(self):
        """4.3.3、附录 A rawSpan：字段封闭；stream 合法；精确整数且 0 <= start < end
        → 否则 E_EVENT_RAW_RANGE；ref 按 ResourceRef 校验。"""
        P.validate_raw_span(make_span(), registry=self.reg)
        span = make_span()
        del span["stream"]
        self.assertCode("E_SCHEMA_FIELDS", P.validate_raw_span, span, registry=self.reg)
        self.assertCode("E_SCHEMA_FIELDS", P.validate_raw_span, {**make_span(), "extra": 1},
                        registry=self.reg)
        # P2 调和（规格澄清 C-03）：stream 枚举外 → E_SCHEMA_FIELDS（原为“被拒绝即可”）。
        self.assertCode("E_SCHEMA_FIELDS", P.validate_raw_span, make_span(stream="stdin"),
                        registry=self.reg, expect_field="/stream")
        for start, end in ((5, 5), (6, 5), (-1, 5), (True, 5), (0, 10.0), (0, "10"), (None, 5)):
            with self.subTest(start=start, end=end):
                self.assertCode("E_EVENT_RAW_RANGE", P.validate_raw_span,
                                make_span(start=start, end=end), registry=self.reg)
        bad_ref = {**make_segment_ref(), "sha256": make_segment_ref()["sha256"].upper()}
        self.assertCode("E_RESOURCE_FIELD", P.validate_raw_span, make_span(ref=bad_ref),
                        registry=self.reg)
        self.assertCode("E_RESOURCE_KIND", P.validate_raw_span,
                        make_span(ref={**make_segment_ref(), "kind": "vendor-stream"}),
                        registry=self.reg)

    def test_A12_raw_refs_only_reference_raw_segments(self):
        """4.3.3、A.2 raw_refs：P4（裁决 R-P7）。raw_refs 只能指向已封存的原始证据分段（raw-segment）；已登记
        但不是 raw-segment 的 kind（fixture、baseline-evidence 等，文件型也一样）→ E_RESOURCE_KIND
        （field=/ref/kind，reason=raw_ref_requires_raw_segment）；未登记的 kind 仍按登记规则报
        resource_kind_not_registered。嵌在事件中时 field 为 /raw_refs/<i>/ref/kind。
        P4 第 3 轮（复审 tests-mutation X17）：stream 为 file 时同样只能引用 raw-segment（protocols-api.md 第 11 节），
        单独调用与嵌在事件中两种入口都逐一断言。"""
        for kind in ("fixture", "baseline-evidence", "fixture-manifest", "public-schema"):
            ref = {**make_segment_ref(), "kind": kind}
            for stream in ("stdout", "stderr", "file"):
                with self.subTest(kind=kind, stream=stream):
                    exc = self.assertCode("E_RESOURCE_KIND", P.validate_raw_span,
                                          make_span(ref=ref, stream=stream),
                                          registry=self.reg, expect_field="/ref/kind")
                    self.assertEqual(exc.reason, "raw_ref_requires_raw_segment")
                    exc = self.assertCode("E_RESOURCE_KIND", P.validate_run_event,
                                          make_vendor_event(raw_refs=[make_span(),
                                                                      make_span(ref=ref, stream=stream)]),
                                          registry=self.reg, expect_field="/raw_refs/1/ref/kind")
                    self.assertEqual(exc.reason, "raw_ref_requires_raw_segment")
        self.assertIsNone(P.validate_raw_span(make_span(stream="file"), registry=self.reg))
        note = make_kind(name="note", is_file=False, owner_module="01", description="测试")
        exc = self.assertCode("E_RESOURCE_KIND", P.validate_raw_span,
                              make_span(ref={"kind": "note", "id": "note-1", "sha256": sha(b"x")}),
                              registry=self.reg.extended([note]), expect_field="/ref/kind")
        self.assertEqual(exc.reason, "raw_ref_requires_raw_segment")
        exc = self.assertCode("E_RESOURCE_KIND", P.validate_raw_span,
                              make_span(ref={**make_segment_ref(), "kind": "vendor-stream"}),
                              registry=self.reg, expect_field="/ref/kind")
        self.assertEqual(exc.reason, "resource_kind_not_registered")
        self.assertIsNone(P.validate_raw_span(make_span(), registry=self.reg))

    def test_A12_raw_span_against_sealed_segment_sizes(self):
        """4.3.3：给出已封存段大小时，引用版本必须已知（E_EVENT_RAW_REF_UNKNOWN），
        byte_end 不超过被引用版本大小（E_EVENT_RAW_RANGE）；恰好等于大小可接受。"""
        ref = make_segment_ref()
        size = len(SEGMENT_BYTES)
        sizes = {ref["sha256"]: size}
        P.validate_raw_span(make_span(ref, 0, size), registry=self.reg, segment_sizes=sizes)
        self.assertCode("E_EVENT_RAW_RANGE", P.validate_raw_span, make_span(ref, 0, size + 1),
                        registry=self.reg, segment_sizes=sizes)
        self.assertCode("E_EVENT_RAW_REF_UNKNOWN", P.validate_raw_span, make_span(ref, 0, size),
                        registry=self.reg, segment_sizes={sha(b"other"): 1000})
        event = make_vendor_event(raw_refs=[make_span(ref, 0, size + 1)])
        self.assertCode("E_EVENT_RAW_RANGE", P.validate_run_event, event, registry=self.reg,
                        segment_sizes=sizes)

    def test_F042_redaction_changes_offsets(self):
        """01-F042 / 4.3.3、01-A12：脱敏改变长度后，偏移按被引用版本的字节计；
        旧偏移不能套到新版本，未封存（未知）的旧版本引用也被拒绝。"""
        original = b"key=sk-abcdefghijklmnopqrstuv\nresult=ok\n"
        redacted = b"key=[R]\nresult=ok\n"
        old_start = original.index(b"result=ok")
        old_end = old_start + len(b"result=ok")
        new_start = redacted.index(b"result=ok")
        new_end = new_start + len(b"result=ok")
        self.assertGreater(old_end, len(redacted))
        ref_redacted = make_segment_ref(redacted, "segment-redacted-1",
                                        "runs/sample/redacted/stdout-000001.seg")
        ref_original = make_segment_ref(original, "segment-original-1",
                                        "runs/sample/captured/stdout-000001.seg")
        sizes = {ref_redacted["sha256"]: len(redacted)}
        P.validate_raw_span(make_span(ref_redacted, new_start, new_end), registry=self.reg,
                            segment_sizes=sizes)
        self.assertEqual(redacted[new_start:new_end], b"result=ok")
        self.assertCode("E_EVENT_RAW_RANGE", P.validate_raw_span,
                        make_span(ref_redacted, old_start, old_end), registry=self.reg,
                        segment_sizes=sizes)
        self.assertCode("E_EVENT_RAW_REF_UNKNOWN", P.validate_raw_span,
                        make_span(ref_original, old_start, old_end), registry=self.reg,
                        segment_sizes=sizes)

    def test_A11_stream_integrity_classification(self):
        """4.3.4、01-D07：未登记的内容是 unknown，不能被忽略；已登记为 known_optional 或 ignorable_optional
        的内容出现与否都不影响完整性（两者在 01 中判定相同，见 test_A11_optional_classifications_equivalent）；
        缺少 known_required → incomplete。类型名为合成样例，不代表真实 Pi 协议。
        P4（第 2 轮复审 fidelity 视角）：原 docstring 写“只有 ignorable_optional 可忽略”，与实现和同一用例中
        known_optional 内容不影响 complete 的断言不符，已更正。"""
        classification = {"run.start": "known_required", "run.end": "known_required",
                          "message": "known_optional", "heartbeat": "ignorable_optional"}
        required = ["run.start", "run.end"]
        ok = P.assess_stream_integrity(["run.start", "message", "heartbeat", "run.end"],
                                       classification, required)
        self.assertEqual(ok["integrity"], "complete")
        self.assertEqual(list(ok["unknown"]), [])
        self.assertEqual(list(ok["missing_required"]), [])
        unknown = P.assess_stream_integrity(["run.start", "mystery", "run.end"], classification,
                                            required)
        self.assertEqual(unknown["integrity"], "incomplete")
        # P2 返工（复审变异 M100）：unknown 固定为排序去重后的列表，直接比较，不先 sorted(set())。
        self.assertEqual(unknown["unknown"], ["mystery"])
        self.assertEqual(P.assess_stream_integrity(["x", "x", "a"], {}, [])["unknown"], ["a", "x"])

    def test_A11_known_required_must_appear(self):
        """4.3.4：P2 调和新增（规格澄清 C-06）。known_required 按字面理解为“已知且必须出现”：
        即使调用方的 required_kinds 漏列，缺少 known_required 类型也是 incomplete；
        known_optional 与 ignorable_optional 可以不出现；required_kinds 可再追加必需类型。"""
        classification = {"run.start": "known_required", "run.end": "known_required",
                          "tool.call": "known_optional", "heartbeat": "ignorable_optional"}
        result = P.assess_stream_integrity(["run.start"], classification, [])
        self.assertEqual(result, {"integrity": "incomplete", "unknown": [],
                                  "missing_required": ["run.end"]})
        ok = P.assess_stream_integrity(["run.start", "run.end"], classification, [])
        self.assertEqual(ok, {"integrity": "complete", "unknown": [], "missing_required": []})
        extra = P.assess_stream_integrity(["run.start", "run.end"], classification, ["tool.call"])
        self.assertEqual(extra["missing_required"], ["tool.call"])
        self.assertEqual(extra["integrity"], "incomplete")
        self.assertCode("E_SCHEMA_FIELDS", P.assess_stream_integrity, ["x"], {"x": "critical"}, [])

    def test_A11_optional_classifications_equivalent(self):
        """4.3.4、01-D07：P4 新增（第 2 轮复审 fidelity 视角，按“01 中两者等价、区别由 04 定义”处理）。
        接口只接收类型名，不接收“该条内容是否被理解”，所以 known_optional 与 ignorable_optional 对任何观测
        集合的判定结果都相同；这一等价是 01 的明确约定（protocols-api.md 第 11 节），改动须同步修改文档。"""
        observations = [[], ["a"], ["a", "b"], ["b"], ["x"], ["a", "x"], ["a", "a", "b"]]
        for required in ([], ["b"], ["a"]):
            for observed in observations:
                with self.subTest(observed=observed, required=required):
                    known = P.assess_stream_integrity(observed, {"a": "known_optional", "b": "known_required"},
                                                      required)
                    ignorable = P.assess_stream_integrity(observed, {"a": "ignorable_optional",
                                                                     "b": "known_required"}, required)
                    self.assertEqual(known, ignorable)

    def test_A11_required_kinds_must_be_classified(self):
        """4.3.4、C-06：P4 第 3 轮新增（复审 events-usage 视角）。required_kinds 中没有登记到 classification 的类型
        出现时会被判为 unknown、缺失时判为 missing，流永远不会 complete——这是调用方（04）的配置错误，明确报
        E_SCHEMA_FIELDS（/required_kinds/<i>，reason=required_kind_not_classified），不静默表现为“流永远不完整”。
        已登记为任一分类的必需类型照常判定。"""
        for observed in (["run.end"], []):
            with self.subTest(observed=observed):
                exc = self.assertCode("E_SCHEMA_FIELDS", P.assess_stream_integrity, observed, {}, ["run.end"],
                                      expect_field="/required_kinds/0")
                self.assertEqual(exc.reason, "required_kind_not_classified")
        exc = self.assertCode("E_SCHEMA_FIELDS", P.assess_stream_integrity, ["a"],
                              {"a": "known_required"}, ["a", "b"], expect_field="/required_kinds/1")
        self.assertEqual(exc.reason, "required_kind_not_classified")
        for value in ("known_required", "known_optional", "ignorable_optional"):
            with self.subTest(classified_as=value):
                self.assertEqual(P.assess_stream_integrity(["run.end"], {"run.end": value}, ["run.end"]),
                                 {"integrity": "complete", "unknown": [], "missing_required": []})
                self.assertEqual(P.assess_stream_integrity([], {"run.end": value}, ["run.end"])["missing_required"],
                                 ["run.end"])

    def test_F039_tail_truncation_is_incomplete(self):
        """01-F039 / 4.3.4：尾部截断（缺结束类内容）→ incomplete，不得成功。"""
        classification = {"run.start": "known_required", "run.end": "known_required",
                          "message": "known_optional"}
        result = P.assess_stream_integrity(["run.start", "message"], classification,
                                           ["run.start", "run.end"])
        self.assertEqual(result["integrity"], "incomplete")
        self.assertEqual(sorted(result["missing_required"]), ["run.end"])

    def _log(self, *events):
        return [copy.deepcopy(e) for e in events]

    def test_F037_duplicate_replay_is_idempotent(self):
        """01-F037 / 4.3.2：同 seq 同封存内容重放 → 去重为一次观察，日志仍完整。"""
        e1, e2, e3 = make_event(1), make_event(2, type="run.prepared"), make_event(3)
        records = self._log(e1, e2, e2, e3)
        before = copy.deepcopy(records)
        result = P.assess_event_log(records)
        self.assertEqual([e["seq"] for e in result["events"]], [1, 2, 3])
        # P2 调和（规格澄清 C-10）：duplicates/conflicts/binding_errors 固定为按 seq 列出的列表。
        self.assertEqual(result["duplicates"], [2])
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["binding_errors"], [])
        self.assertEqual(result["invalid"], [])
        self.assertEqual(list(result["gaps"]), [])
        self.assertEqual(result["last_contiguous_seq"], 3)
        self.assertIs(result["complete"], True)
        self.assertUnchanged(before, records)

    def test_F038_same_seq_different_content(self):
        """01-F038 / 4.3.2：同 (run_id, seq) 内容不同 → 冲突，日志不完整。
        P2 调和补充（规格澄清 C-10）：冲突的 seq 被隔离，不进入 events，连续前缀停在冲突之前；
        C.3 要求的错误码 E_EVENT_REPLAY_CONFLICT 由追加与恢复入口给出。"""
        e1, e2 = make_event(1), make_event(2)
        e2b = make_event(2, payload={"example_only": False})
        result = P.assess_event_log(self._log(e1, e2, e2b, make_event(3)))
        self.assertEqual(result["conflicts"], [2])
        self.assertEqual([e["seq"] for e in result["events"]], [1, 3])
        self.assertEqual(result["last_contiguous_seq"], 1)
        self.assertIs(result["complete"], False)
        self.assertCode("E_EVENT_REPLAY_CONFLICT", P.recover_next_seq, self._log(e1, e2, e2b))
        state = {"run_id": RUN, "last_committed_seq": 0, "committed": {}}
        P.append_event(state, e1)
        P.append_event(state, e2)
        self.assertCode("E_EVENT_REPLAY_CONFLICT", P.append_event, state, e2b)

    def test_F038_dict_equal_but_bytes_different_is_conflict(self):
        """01-F038 / 4.3.2、C-10：P4 第 3 轮新增（复审 tests-mutation X23）。重复与冲突按固定快照字节区分，不按
        Python 字典相等：payload {"x":1} 与 {"x":true}、1 与 1.0 在 Python 中相等（==），快照字节却不同，是冲突，
        不能当作重复投递静默丢弃。assess_event_log 列入 conflicts，恢复与追加都报 E_EVENT_REPLAY_CONFLICT。"""
        e1 = make_event(1)
        for first, second in (({"x": 1}, {"x": True}), ({"x": 1}, {"x": 1.0}), ({"x": 0}, {"x": False})):
            original, replay = make_event(2, payload=first), make_event(2, payload=second)
            with self.subTest(first=first, second=second):
                self.assertEqual(original, replay, "前提：两条记录在 Python 中相等")
                self.assertNotEqual(P.stable_snapshot_bytes(original), P.stable_snapshot_bytes(replay))
                result = P.assess_event_log(self._log(e1, original, replay), run_id=RUN)
                self.assertEqual(result["conflicts"], [2])
                self.assertEqual(result["duplicates"], [])
                self.assertIs(result["complete"], False)
                self.assertCode("E_EVENT_REPLAY_CONFLICT", P.recover_next_seq, self._log(e1, original, replay),
                                run_id=RUN)
                self.assertCode("E_EVENT_REPLAY_CONFLICT", P.recover_append_state,
                                self._log(e1, original, replay), run_id=RUN)
                state = P.recover_append_state(self._log(e1, original), run_id=RUN)
                before = copy.deepcopy(state)
                self.assertCode("E_EVENT_REPLAY_CONFLICT", P.append_event, state, replay)
                self.assertEqual(state, before)
                self.assertEqual(P.append_event(state, copy.deepcopy(original)), "duplicate")

    def test_F039_seq_gap(self):
        """01-F039 / 4.3.2：已提交序号出现缺口 → gaps 记录 (期望, 实际)，日志不完整，不静默跳过。"""
        result = P.assess_event_log(self._log(make_event(1), make_event(3)))
        self.assertEqual([tuple(g) for g in result["gaps"]], [(2, 3)])
        self.assertEqual(result["last_contiguous_seq"], 1)
        self.assertIs(result["complete"], False)
        head = P.assess_event_log(self._log(make_event(2), make_event(3)))
        self.assertEqual([tuple(g) for g in head["gaps"]], [(1, 2)])
        self.assertEqual(head["last_contiguous_seq"], 0)
        self.assertIs(head["complete"], False)

    def test_A11_event_log_binding_errors_and_empty(self):
        """4.3.2：同一日志中 run_id 不一致 → binding_errors，日志不完整；空日志没有冲突与缺口。"""
        result = P.assess_event_log(self._log(make_event(1), make_event(2, run_id=OTHER_RUN)))
        self.assertEqual(result["binding_errors"], [2])  # 规格澄清 C-10：按 seq 列出
        self.assertIs(result["complete"], False)
        self.assertCode("E_CONTEXT_BINDING", P.recover_next_seq,
                        self._log(make_event(1), make_event(2, run_id=OTHER_RUN)))
        empty = P.assess_event_log([])
        self.assertEqual(list(empty["events"]), [])
        self.assertEqual(empty["last_contiguous_seq"], 0)
        # P4（裁决 R-P8）：complete 只表示“序列一致”，空日志仍为 True；event_count=0 让调用方看出日志为空
        # （空日志不证明运行产生过事件，协议完整性由 assess_stream_integrity 与 04 判定）。
        self.assertIs(empty["complete"], True)
        self.assertEqual(empty["event_count"], 0)
        # 规格澄清 C-10：纯函数不抛异常；无法读取 seq/run_id 的记录按下标列入 invalid，日志不完整。
        broken = P.assess_event_log([make_event(1), {"seq": "2"}, None])
        self.assertEqual(broken["invalid"], [1, 2])
        self.assertIs(broken["complete"], False)

    def test_A11_event_log_event_count_and_keys(self):
        """4.3.2、protocols-api.md 11 节：P4（裁决 R-P8）。返回值恰好是固定的键集合，新增 event_count
        （events 中的事件数：去重后、不含冲突的 seq）与 record_type_errors；重复投递与冲突不增加计数。"""
        keys = {"events", "event_count", "duplicates", "conflicts", "gaps", "out_of_order", "binding_errors",
                "record_type_errors", "invalid", "last_contiguous_seq", "complete"}
        e1, e2, e3 = make_event(1), make_event(2), make_event(3)
        result = P.assess_event_log(self._log(e1, e2, e2, e3))
        self.assertEqual(set(result), keys)
        self.assertEqual(result["event_count"], 3)
        self.assertEqual(result["event_count"], len(result["events"]))
        conflicted = P.assess_event_log(self._log(e1, e2, make_event(2, payload={"example_only": False}), e3))
        self.assertEqual(conflicted["event_count"], 2)
        self.assertIs(conflicted["complete"], False)
        self.assertEqual(set(P.assess_event_log(None)), keys)  # 纯函数：不可迭代也只报告
        self.assertEqual(P.assess_event_log(None)["event_count"], 0)

    def test_A11_event_log_rejects_non_event_records(self):
        """4.3.2：P4 新增（第 2 轮复审 events-usage 视角）。seq 与 run_id 可读、但 record_type 不是精确的
        "run-event" 的记录（例如带 seq 的 usage-observation、缺 record_type、str 子类）不当作已提交事件：
        列入 record_type_errors（按下标），不进入 events，日志不完整；recover_next_seq / recover_append_state
        → E_SCHEMA_RECORD_TYPE，与 append_event 对同一记录的判断一致。"""

        class Str(str):
            pass

        usage_like = {"record_type": "usage-observation", "run_id": RUN, "seq": 1, "x": 1}
        no_type = {"run_id": RUN, "seq": 1}
        for bad in (usage_like, no_type, make_event(1, record_type=Str("run-event"))):
            with self.subTest(record=repr(bad)[:60]):
                result = P.assess_event_log([bad], run_id=RUN)
                self.assertEqual(result["record_type_errors"], [0])
                self.assertEqual(result["events"], [])
                self.assertIs(result["complete"], False)
                self.assertCode("E_SCHEMA_RECORD_TYPE", P.recover_next_seq, [bad], run_id=RUN)
                self.assertCode("E_SCHEMA_RECORD_TYPE", P.recover_append_state, [bad], run_id=RUN)
                fresh = {"run_id": RUN, "last_committed_seq": 0, "committed": {}}
                self.assertCode("E_SCHEMA_RECORD_TYPE", P.append_event, fresh, bad)
        mixed = P.assess_event_log([make_event(1), usage_like, make_event(2)], run_id=RUN)
        self.assertEqual(mixed["record_type_errors"], [1])
        self.assertEqual([e["seq"] for e in mixed["events"]], [1, 2])

    def test_A11_recovery_error_code_independent_of_position(self):
        """7.4“单一故障输入稳定返回对应码”：P4 新增（第 2 轮复审 events-usage 视角）。他 run 记录、非事件记录
        或不可读记录在日志中间时也会造成缺口；恢复函数先报记录本身的缺陷，所以同一种故障无论在中间还是尾部
        都得到同一个码（E_CONTEXT_BINDING / E_SCHEMA_RECORD_TYPE / E_SCHEMA_TYPE），不再在中间时报 E_EVENT_GAP。"""
        e1, e2, e3 = make_event(1), make_event(2), make_event(3)
        faults = [(make_event(2, run_id=OTHER_RUN), make_event(3, run_id=OTHER_RUN), "E_CONTEXT_BINDING"),
                  ({**e2, "seq": True}, {**e3, "seq": True}, "E_SCHEMA_TYPE"),
                  ({**e2, "record_type": "usage-observation"}, {**e3, "record_type": "usage-observation"},
                   "E_SCHEMA_RECORD_TYPE")]
        for middle, tail, code in faults:
            for records in ([e1, middle, e3], [e1, e2, tail]):
                with self.subTest(code=code, position="middle" if records[1] is middle else "tail"):
                    self.assertCode(code, P.recover_next_seq, self._log(*records), run_id=RUN)
                    self.assertCode(code, P.recover_append_state, self._log(*records), run_id=RUN)
        # 没有记录本身缺陷的缺口仍是 E_EVENT_GAP。
        self.assertCode("E_EVENT_GAP", P.recover_next_seq, self._log(e1, e3), run_id=RUN)

    def test_A11_recovery_multi_fault_order_is_fixed(self):
        """protocols-api.md 第 11 节、recover_next_seq docstring：P4 第 3 轮新增（复审 tests-mutation M27/M30）。恢复
        函数的报错顺序是明确承诺的全序（第 3.2 节“多缺陷不承诺首错”的例外）：绑定 E_CONTEXT_BINDING → 记录类型
        E_SCHEMA_RECORD_TYPE → 不可读 E_SCHEMA_TYPE → 冲突 E_EVENT_REPLAY_CONFLICT → 缺口 E_EVENT_GAP
        （log_contains_gap）→ 乱序 E_EVENT_GAP（log_out_of_order）。同一日志同时含相邻两类缺陷时，无论故障记录
        的先后，都报排在前面的那一类。"""
        e1, e2, e3 = make_event(1), make_event(2), make_event(3)
        foreign = make_event(4, run_id=OTHER_RUN)
        non_event = {**make_event(5), "record_type": "usage-observation"}
        unreadable = {**make_event(6), "seq": True}
        conflict = make_event(2, payload={"example_only": False})
        pairs = [
            ((foreign, non_event), "E_CONTEXT_BINDING", "log_contains_foreign_run"),
            ((non_event, unreadable), "E_SCHEMA_RECORD_TYPE", "log_contains_non_event_record"),
            ((unreadable, conflict), "E_SCHEMA_TYPE", "log_contains_unreadable_record"),
        ]
        for (first, second), code, reason in pairs:
            for extra in ((first, second), (second, first)):
                with self.subTest(code=code, order=[r.get("record_type") for r in extra]):
                    records = self._log(e1, e2, *extra, e3)
                    for recover in (P.recover_next_seq, P.recover_append_state):
                        exc = self.assertCode(code, recover, records, run_id=RUN)
                        self.assertEqual(exc.reason, reason)
        # 冲突先于缺口：日志同时有冲突与缺口（缺 seq 3）。
        for records in ([e1, e2, conflict, make_event(4)], [e1, make_event(4), e2, conflict]):
            with self.subTest(conflict_and_gap=[r["seq"] for r in records]):
                exc = self.assertCode("E_EVENT_REPLAY_CONFLICT", P.recover_next_seq, self._log(*records), run_id=RUN)
                self.assertEqual(exc.reason, "log_contains_conflict")
        # 缺口先于乱序：[1, 4, 2] 既缺 3 又乱序。
        exc = self.assertCode("E_EVENT_GAP", P.recover_next_seq, self._log(e1, make_event(4), e2), run_id=RUN)
        self.assertEqual(exc.reason, "log_contains_gap")
        exc = self.assertCode("E_EVENT_GAP", P.recover_next_seq, self._log(e1, e3, e2), run_id=RUN)
        self.assertEqual(exc.reason, "log_out_of_order")

    def test_A11_append_event_state_invariant_checked_fully(self):
        """4.3.2：P4 新增（第 2 轮复审 events-usage 视角）。state 不变式按键集合完整核对：键必须恰好是
        1..last_committed_seq 的精确 int、值必须是 bytes。从 JSON 读回（键为字符串）的 state 追加下一个 seq、
        键稀疏的 state 追加或重放、bool 键、非 bytes 值 → ValueError（不是 ProtocolError），state 不变，
        不会得到混合键的 state，也不会把从未按序提交的 seq 误判为 duplicate。"""
        one = P.stable_snapshot_bytes(make_event(1))
        two = P.stable_snapshot_bytes(make_event(2))
        three = P.stable_snapshot_bytes(make_event(3))
        broken_states = [
            ({"run_id": RUN, "last_committed_seq": 2, "committed": {"1": one, "2": two}}, make_event(3)),
            ({"run_id": RUN, "last_committed_seq": 2, "committed": {1: one, 3: three}}, make_event(3)),
            ({"run_id": RUN, "last_committed_seq": 2, "committed": {1: one, 3: three}}, make_event(2)),
            ({"run_id": RUN, "last_committed_seq": 1, "committed": {True: one}}, make_event(2)),
            ({"run_id": RUN, "last_committed_seq": 2, "committed": {1: one, 2: two.decode("utf-8")}},
             make_event(3)),
            ({"run_id": RUN, "last_committed_seq": 1, "committed": {1: bytearray(one)}}, make_event(2)),
        ]
        for broken, record in broken_states:
            with self.subTest(keys=[repr(k) for k in broken["committed"]], seq=record["seq"]):
                before = copy.deepcopy(broken)
                with self.assertRaises(ValueError) as caught:
                    P.append_event(broken, record)
                self.assertNotIsInstance(caught.exception, P.ProtocolError)
                self.assertUnchanged(before, broken)
        good = {"run_id": RUN, "last_committed_seq": 2, "committed": {1: one, 2: two}}
        self.assertEqual(P.append_event(good, make_event(3)), "appended")
        self.assertEqual(sorted(good["committed"]), [1, 2, 3])
        self.assertTrue(all(type(key) is int for key in good["committed"]))

    def test_A11_append_event_sequence(self):
        """4.3.2：首条 seq=1；新事件必须 last+1（appended）；重放相同字节 → duplicate 且不改状态
        （不再次计费）；同 seq 不同内容 → E_EVENT_REPLAY_CONFLICT；跳号 → E_EVENT_GAP；
        run_id 不同 → E_CONTEXT_BINDING；失败时状态不变。"""
        state = {"run_id": RUN, "last_committed_seq": 0, "committed": {}}
        empty_state = copy.deepcopy(state)
        self.assertCode("E_EVENT_GAP", P.append_event, state, make_event(2))
        self.assertUnchanged(empty_state, state)
        self.assertEqual(P.append_event(state, make_event(1)), "appended")
        self.assertEqual(state["last_committed_seq"], 1)
        # P2 调和（规格澄清 C-10）：committed 中保存的是该记录的固定快照字节（4.3.2“比较已封存的
        # 标准记录版本/字节”），不是对象或摘要。
        self.assertEqual(state["committed"][1], P.stable_snapshot_bytes(make_event(1)))
        snapshot = copy.deepcopy(state)
        self.assertEqual(P.append_event(state, make_event(1)), "duplicate")
        self.assertUnchanged(snapshot, state)
        exc = self.assertCode("E_EVENT_REPLAY_CONFLICT", P.append_event, state,
                              make_event(1, payload={"example_only": False}))
        self.assertIs(exc.retryable, True)
        self.assertUnchanged(snapshot, state)
        exc = self.assertCode("E_EVENT_GAP", P.append_event, state, make_event(3))
        self.assertIs(exc.retryable, True)
        self.assertUnchanged(snapshot, state)
        self.assertCode("E_CONTEXT_BINDING", P.append_event, state, make_event(2, run_id=OTHER_RUN))
        self.assertUnchanged(snapshot, state)
        self.assertEqual(P.append_event(state, make_event(2)), "appended")
        self.assertEqual(state["last_committed_seq"], 2)

    def test_A11_F037_append_event_replay_of_older_seq_keeps_state(self):
        """4.3.2、01-F037 幂等：P2 返工新增（复审变异 P144）。重放**较早**的 seq（不是最后一条）：字节相同
        → "duplicate" 且 state 完全不变（last_committed_seq 不回退、committed 不改）；内容不同 →
        E_EVENT_REPLAY_CONFLICT 且 state 不变；之后追加下一条照常 appended。"""
        state = {"run_id": RUN, "last_committed_seq": 0, "committed": {}}
        for seq in (1, 2, 3):
            self.assertEqual(P.append_event(state, make_event(seq)), "appended")
        snapshot = copy.deepcopy(state)
        for seq in (1, 2):
            with self.subTest(replayed_seq=seq):
                self.assertEqual(P.append_event(state, make_event(seq)), "duplicate")
                self.assertUnchanged(snapshot, state)
                self.assertEqual(state["last_committed_seq"], 3)
                self.assertCode("E_EVENT_REPLAY_CONFLICT", P.append_event, state,
                                make_event(seq, payload={"example_only": False}))
                self.assertUnchanged(snapshot, state)
        self.assertEqual(P.append_event(state, make_event(4)), "appended")
        self.assertEqual(state["last_committed_seq"], 4)
        self.assertEqual(sorted(state["committed"]), [1, 2, 3, 4])

    def test_A11_recover_next_seq_from_persisted_records(self):
        """4.3.2：崩溃后从持久记录恢复下一个序号（不依赖内存计数）；有冲突或缺口时拒绝恢复。"""
        self.assertEqual(P.recover_next_seq([]), 1)
        self.assertEqual(P.recover_next_seq(self._log(make_event(1), make_event(2))), 3)
        self.assertEqual(P.recover_next_seq(self._log(make_event(1), make_event(2), make_event(2))), 3)
        self.assertCode("E_EVENT_REPLAY_CONFLICT", P.recover_next_seq,
                        self._log(make_event(1), make_event(1, payload={"example_only": False})))
        self.assertCode("E_EVENT_GAP", P.recover_next_seq, self._log(make_event(1), make_event(3)))
        # P2 返工（复审变异 M54，major）：不可读的持久记录不能被忽略，否则恢复出的序号与磁盘上
        # 已有的 seq 重复。
        self.assertCode("E_SCHEMA_TYPE", P.recover_next_seq, [make_event(1), {"seq": 2}])
        self.assertCode("E_SCHEMA_TYPE", P.recover_next_seq, [make_event(1), None])

    def test_A11_event_log_out_of_order(self):
        """4.3.2 单写入方 last+1：P2 返工新增（复审 events-usage 视角）。按持久化顺序 [1, 3, 2]：3 在 2 之前
        写入说明曾经跳号，排序后连续也不能算完整 → out_of_order=[2]、complete=False；恢复时 E_EVENT_GAP。"""
        result = P.assess_event_log(self._log(make_event(1), make_event(3), make_event(2)))
        self.assertEqual(result["gaps"], [])
        self.assertEqual(result["out_of_order"], [2])
        self.assertIs(result["complete"], False)
        self.assertCode("E_EVENT_GAP", P.recover_next_seq,
                        self._log(make_event(1), make_event(3), make_event(2)))
        ordered = P.assess_event_log(self._log(make_event(1), make_event(2), make_event(1)))
        self.assertEqual(ordered["out_of_order"], [])  # 重复投递不是乱序
        self.assertIs(ordered["complete"], True)

    def test_A11_event_log_run_id_parameter(self):
        """4.3.2：P2 返工新增（复审变异 M109 与 events-usage 视角）。assess_event_log 的 run_id 参数用于核对
        整份日志的归属：误读另一个 run 的日志 → binding_errors、不完整；参数不是合法 run id 时每条都
        记为绑定错误，不静默回退到第一条记录。recover_next_seq(run_id=...) → E_CONTEXT_BINDING；
        非法 run_id → E_ID_SYNTAX。"""
        foreign = self._log(make_event(1, run_id=OTHER_RUN), make_event(2, run_id=OTHER_RUN))
        result = P.assess_event_log(foreign, run_id=RUN)
        self.assertEqual(result["binding_errors"], [1, 2])
        self.assertIs(result["complete"], False)
        self.assertEqual(P.assess_event_log(foreign)["binding_errors"], [])
        self.assertEqual(P.assess_event_log(foreign, run_id=123)["binding_errors"], [1, 2])
        # P4 第 3 轮（复审 fidelity 视角）：参照值是 str 但不是合法 run id 时同样每条都记为绑定错误——即使记录
        # 恰好带同一个非法字符串，也不判为一致、不判 complete。
        for bad in ("garbage", "run-x", RUN.upper(), RUN + "\n", ""):
            same = self._log(make_event(1, run_id=bad), make_event(2, run_id=bad))
            with self.subTest(run_id=bad):
                assessed = P.assess_event_log(same, run_id=bad)
                self.assertEqual(assessed["binding_errors"], [1, 2])
                self.assertEqual(assessed["event_count"], 0)
                self.assertIs(assessed["complete"], False)
                self.assertEqual(P.assess_event_log(foreign, run_id=bad)["binding_errors"], [1, 2])
        self.assertEqual(P.recover_next_seq(foreign), 3)
        self.assertCode("E_CONTEXT_BINDING", P.recover_next_seq, foreign, run_id=RUN)
        self.assertEqual(P.recover_next_seq(foreign, run_id=OTHER_RUN), 3)
        self.assertCode("E_ID_SYNTAX", P.recover_next_seq, foreign, run_id="run-x",
                        expect_field="/run_id")

    def test_A11_recover_append_state_after_crash(self):
        """4.3.2 崩溃恢复：P2 返工新增（复审 events-usage 视角）。recover_append_state 从持久记录重建完整
        state：重放已提交的相同事件 → "duplicate"，内容不同 → E_EVENT_REPLAY_CONFLICT，而不是误报
        E_EVENT_GAP。只恢复了 last_committed_seq 的 state、从 JSON 读回（键为字符串）的 state 不满足
        不变式 → ValueError；非 run-event 记录 → E_SCHEMA_RECORD_TYPE。"""
        records = self._log(make_event(1), make_event(2))
        state = P.recover_append_state(records, run_id=RUN)
        self.assertEqual(state["last_committed_seq"], 2)
        self.assertEqual(state["committed"], {1: P.stable_snapshot_bytes(make_event(1)),
                                              2: P.stable_snapshot_bytes(make_event(2))})
        self.assertEqual(P.append_event(state, make_event(2)), "duplicate")
        self.assertCode("E_EVENT_REPLAY_CONFLICT", P.append_event, state,
                        make_event(1, payload={"example_only": False}))
        self.assertEqual(P.append_event(state, make_event(3)), "appended")
        self.assertEqual(P.recover_append_state([], run_id=RUN),
                         {"run_id": RUN, "last_committed_seq": 0, "committed": {}})
        self.assertCode("E_CONTEXT_BINDING", P.recover_append_state, records, run_id=OTHER_RUN)
        self.assertCode("E_ID_SYNTAX", P.recover_append_state, records, run_id=None)
        # state 不满足不变式是调用方错误：抛普通 ValueError（不是 ProtocolError，也不是 E_EVENT_GAP）。
        one = P.stable_snapshot_bytes(make_event(1))
        two = P.stable_snapshot_bytes(make_event(2))
        broken_states = [
            ({"run_id": RUN, "last_committed_seq": 2, "committed": {}}, make_event(2)),
            ({"run_id": RUN, "last_committed_seq": 1, "committed": {"1": one}}, make_event(1)),
            ({"run_id": RUN, "last_committed_seq": 3, "committed": {1: one, 2: two}}, make_event(1)),
            ({"run_id": RUN, "last_committed_seq": 1, "committed": {1: one, 2: two}}, make_event(2)),
        ]
        for broken, record in broken_states:
            with self.subTest(state=broken["last_committed_seq"], keys=list(broken["committed"])):
                before = copy.deepcopy(broken)
                with self.assertRaises(ValueError) as caught:
                    P.append_event(broken, record)
                self.assertNotIsInstance(caught.exception, P.ProtocolError)
                self.assertUnchanged(before, broken)
        fresh = {"run_id": RUN, "last_committed_seq": 0, "committed": {}}
        usage_like = {"record_type": "usage-observation", "run_id": RUN, "seq": 1}
        self.assertCode("E_SCHEMA_RECORD_TYPE", P.append_event, fresh, usage_like,
                        expect_field="/record_type")
        self.assertEqual(fresh, {"run_id": RUN, "last_committed_seq": 0, "committed": {}})

    # -- 收尾轮：M-01（acceptance.md 第 10 节；4.3.1 角色与 run 绑定、4.3.2） --

    def test_A11_m01_event_log_request_and_role_binding(self):
        """M-01：事件日志除 run_id 外，还核对同一 run 内 request_id 一致、非空 role 一致。不一致的记录列入
        binding_errors（按 seq），不进入 events，complete=False；恢复函数报 E_CONTEXT_BINDING（reason 为
        log_request_binding_mismatch / log_role_binding_mismatch）。参照值取日志中第一条通过前一步的记录；role 为 null
        的无角色核心事件不参与比较。此前这类日志判 complete=True 且可以恢复。"""
        e1, e2, e3 = make_event(1), make_event(2), make_event(3)
        cases = [
            ([e1, make_event(2, request_id=OTHER_REQ), e3], [2], [1, 3], "log_request_binding_mismatch"),
            ([e1, e2, make_event(3, request_id=OTHER_REQ)], [3], [1, 2], "log_request_binding_mismatch"),
            ([make_event(1, request_id=OTHER_REQ), e2, e3], [2, 3], [1], "log_request_binding_mismatch"),
            ([e1, make_event(2, role="executor"), e3], [2], [1, 3], "log_role_binding_mismatch"),
            ([make_event(1, role=None), make_event(2, role="executor"), e3], [3], [1, 2],
             "log_role_binding_mismatch"),
            ([e1, e2, make_event(2, request_id=OTHER_REQ)], [2], [1, 2], "log_request_binding_mismatch"),
            ([e1, e2, make_event(2, role="observer")], [2], [1, 2], "log_role_binding_mismatch"),
        ]
        for records, bound, kept, reason in cases:
            with self.subTest(reason=reason, bound=bound, first=records[0]["request_id"][-4:]):
                result = P.assess_event_log(self._log(*records), run_id=RUN)
                self.assertEqual(result["binding_errors"], bound)
                self.assertEqual([e["seq"] for e in result["events"]], kept)
                self.assertEqual(result["event_count"], len(kept))
                self.assertIs(result["complete"], False)
                self.assertEqual(result["duplicates"], [])
                self.assertEqual(result["conflicts"], [])
                for recover in (P.recover_next_seq, P.recover_append_state):
                    exc = self.assertCode("E_CONTEXT_BINDING", recover, self._log(*records), run_id=RUN)
                    self.assertEqual(exc.reason, reason)
                self.assertCode("E_CONTEXT_BINDING", P.recover_next_seq, self._log(*records))
        # 无角色核心事件（role=null）与同一个非空 role 交错：一致，complete=True。
        mixed = self._log(make_event(1, role=None), make_event(2), make_event(3, role=None), make_event(4))
        result = P.assess_event_log(mixed, run_id=RUN)
        self.assertEqual(result["binding_errors"], [])
        self.assertIs(result["complete"], True)
        self.assertEqual(result["event_count"], 4)
        self.assertEqual(P.recover_next_seq(mixed, run_id=RUN), 5)
        all_null = self._log(make_event(1, role=None), make_event(2, role=None))
        self.assertIs(P.assess_event_log(all_null, run_id=RUN)["complete"], True)
        # 被判为他 run 的记录不参与 request/role 的参照（它的 request_id 不会成为参照值）。
        foreign_first = self._log(make_event(1, run_id=OTHER_RUN, request_id=OTHER_REQ, role="executor"), e1, e2)
        result = P.assess_event_log(foreign_first, run_id=RUN)
        self.assertEqual(result["binding_errors"], [1])
        self.assertEqual([e["seq"] for e in result["events"]], [1, 2])
        exc = self.assertCode("E_CONTEXT_BINDING", P.recover_next_seq, foreign_first, run_id=RUN)
        self.assertEqual(exc.reason, "log_contains_foreign_run")

    def test_A11_m01_binding_reason_order_is_fixed(self):
        """M-01、protocols-api.md 第 11 节：绑定错误的 reason 按类别的固定顺序选择：run → request → role；同一日志含
        多类时，与记录的先后无关。绑定仍先于记录类型、不可读、冲突与缺口（P4 第 3 轮的全序不变）。"""
        e1, e2 = make_event(1), make_event(2)
        foreign = make_event(3, run_id=OTHER_RUN)
        request = make_event(4, request_id=OTHER_REQ)
        role = make_event(5, role="observer")
        non_event = {**make_event(6), "record_type": "usage-observation"}
        for pair, reason in (((foreign, request), "log_contains_foreign_run"),
                             ((foreign, role), "log_contains_foreign_run"),
                             ((request, role), "log_request_binding_mismatch")):
            for extra in (pair, pair[::-1]):
                with self.subTest(order=[r["seq"] for r in extra]):
                    for recover in (P.recover_next_seq, P.recover_append_state):
                        exc = self.assertCode("E_CONTEXT_BINDING", recover, self._log(e1, e2, *extra), run_id=RUN)
                        self.assertEqual(exc.reason, reason)
        for extra in ((request, non_event), (non_event, request), (role, non_event), (non_event, role)):
            with self.subTest(with_non_event=[r["seq"] for r in extra]):
                self.assertCode("E_CONTEXT_BINDING", P.recover_next_seq, self._log(e1, e2, *extra), run_id=RUN)
        # 收尾轮返工（复审 tests-mutation 视角）：同一条记录同时改写 request_id 与 role 时，assess 先核对 request，
        # 只记一个 request 类绑定错误，恢复函数报 log_request_binding_mismatch（不是 role 类）。
        both = make_event(3, request_id=OTHER_REQ, role="observer")
        result = P.assess_event_log(self._log(e1, e2, both), run_id=RUN)
        self.assertEqual(result["binding_errors"], [3])
        self.assertEqual([e["seq"] for e in result["events"]], [1, 2])
        for recover in (P.recover_next_seq, P.recover_append_state):
            with self.subTest(single_record_both_changed=recover.__name__):
                exc = self.assertCode("E_CONTEXT_BINDING", recover, self._log(e1, e2, both), run_id=RUN)
                self.assertEqual(exc.reason, "log_request_binding_mismatch")

    def test_A11_m01_unreadable_binding_fields(self):
        """M-01：绑定字段不可读的 run-event 记录（request_id 缺失或不是 str；role 缺失，或既不是 str 也不是 null）与
        seq/run_id 不可读同样列入 invalid（按下标），恢复时报 E_SCHEMA_TYPE（log_contains_unreadable_record）。不是
        run-event 的记录仍先按记录类型报告。"""
        e1 = make_event(1)
        no_request = make_event(2)
        del no_request["request_id"]
        no_role = make_event(2)
        del no_role["role"]
        for bad in (no_request, make_event(2, request_id=None), make_event(2, request_id=123), no_role,
                    make_event(2, role=1), make_event(2, role=["planner"])):
            with self.subTest(record=sorted(k for k in make_event(2) if bad.get(k, "~") != make_event(2)[k])):
                result = P.assess_event_log(self._log(e1, bad), run_id=RUN)
                self.assertEqual(result["invalid"], [1])
                self.assertEqual(result["binding_errors"], [])
                self.assertIs(result["complete"], False)
                exc = self.assertCode("E_SCHEMA_TYPE", P.recover_next_seq, self._log(e1, bad), run_id=RUN)
                self.assertEqual(exc.reason, "log_contains_unreadable_record")
        no_request_non_event = {"record_type": "usage-observation", "run_id": RUN, "seq": 2}
        self.assertEqual(P.assess_event_log(self._log(e1, no_request_non_event), run_id=RUN)["record_type_errors"],
                         [1])

    def test_A11_m01_append_event_request_and_role_binding(self):
        """M-01：append_event 核对 request_id 与已提交记录一致（E_CONTEXT_BINDING，/request_id，
        reason=request_binding_mismatch），非空 role 与已提交记录中第一个非空 role 一致（/role，
        reason=role_binding_mismatch）；绑定先于序号，所以同 seq 改写 request_id 的重放也报绑定错误。request_id 不是
        str、role 缺失或类型不对报 E_SCHEMA_TYPE。任何错误都不改 state；state 的形状不变（参照值从 committed 的快照
        字节读出）。"""
        state = {"run_id": RUN, "last_committed_seq": 0, "committed": {}}
        self.assertEqual(P.append_event(state, make_event(1)), "appended")
        snapshot = copy.deepcopy(state)
        failures = [
            (make_event(2, request_id=OTHER_REQ), "E_CONTEXT_BINDING", "/request_id", "request_binding_mismatch"),
            (make_event(1, request_id=OTHER_REQ), "E_CONTEXT_BINDING", "/request_id", "request_binding_mismatch"),
            (make_event(2, role="executor"), "E_CONTEXT_BINDING", "/role", "role_binding_mismatch"),
            (make_event(1, role="observer"), "E_CONTEXT_BINDING", "/role", "role_binding_mismatch"),
            (make_event(2, request_id=None), "E_SCHEMA_TYPE", "/request_id", "string_required"),
            (make_event(2, role=1), "E_SCHEMA_TYPE", "/role", "string_or_null_required"),
        ]
        no_role = make_event(2)
        del no_role["role"]
        failures.append((no_role, "E_SCHEMA_TYPE", "/role", "string_or_null_required"))
        # 收尾轮返工（复审 tests-mutation 视角）：固定文档写明的检查顺序 run_id → 绑定字段可读 → request_id → role。
        # 同时改写 request_id 与 role 时报 /request_id（request 先于 role）；他 run 的记录即使 request_id 不可读也报
        # E_CONTEXT_BINDING /run_id（run 绑定先于绑定字段的类型检查）。
        failures.append((make_event(2, request_id=OTHER_REQ, role="executor"), "E_CONTEXT_BINDING", "/request_id",
                         "request_binding_mismatch"))
        failures.append((make_event(2, run_id=OTHER_RUN, request_id=None), "E_CONTEXT_BINDING", "/run_id",
                         "run_binding_mismatch"))
        failures.append((make_event(2, run_id=OTHER_RUN, role=1), "E_CONTEXT_BINDING", "/run_id",
                         "run_binding_mismatch"))
        failures.append((make_event(2, request_id=None, role=1), "E_SCHEMA_TYPE", "/request_id", "string_required"))
        for record, code, pointer, reason in failures:
            with self.subTest(seq=record["seq"], reason=reason, field=pointer):
                exc = self.assertCode(code, P.append_event, state, record, expect_field=pointer)
                self.assertEqual(exc.reason, reason)
                self.assertUnchanged(snapshot, state)
        self.assertEqual(P.append_event(state, make_event(2, role=None)), "appended")
        self.assertEqual(P.append_event(state, make_event(3)), "appended")
        self.assertEqual(set(state), {"run_id", "last_committed_seq", "committed"})
        # 第一条是无角色核心事件时，第一个非空 role 成为参照。
        state = {"run_id": RUN, "last_committed_seq": 0, "committed": {}}
        self.assertEqual(P.append_event(state, make_event(1, role=None)), "appended")
        self.assertEqual(P.append_event(state, make_event(2, role="executor")), "appended")
        self.assertCode("E_CONTEXT_BINDING", P.append_event, state, make_event(3, role="planner"),
                        expect_field="/role")
        # 崩溃恢复后的 state 同样核对。
        recovered = P.recover_append_state(self._log(make_event(1, role=None), make_event(2, role="executor")),
                                           run_id=RUN)
        self.assertCode("E_CONTEXT_BINDING", P.append_event, recovered, make_event(3, role="planner"),
                        expect_field="/role")
        self.assertCode("E_CONTEXT_BINDING", P.append_event, recovered,
                        make_event(3, role="executor", request_id=OTHER_REQ), expect_field="/request_id")
        self.assertEqual(P.append_event(recovered, make_event(3, role="executor")), "appended")
        # committed 中的字节不是 run-event 快照（无法读出绑定字段）时，state 不满足不变式 → ValueError。
        no_request = make_event(1)
        del no_request["request_id"]
        for value in (b"not json", "中".encode("utf-8"), b"[]", P.stable_snapshot_bytes(no_request)):
            broken = {"run_id": RUN, "last_committed_seq": 1, "committed": {1: value}}
            with self.subTest(committed=value[:12]):
                before = copy.deepcopy(broken)
                with self.assertRaises(ValueError) as caught:
                    P.append_event(broken, make_event(2))
                self.assertNotIsInstance(caught.exception, P.ProtocolError)
                self.assertUnchanged(before, broken)

    def test_A11_m01_entry_points_agree(self):
        """M-01：同一份日志，assess_event_log 有绑定错误 ⇔ 恢复函数报 E_CONTEXT_BINDING ⇔ 按持久化顺序逐条
        append_event 时在第一条不一致的记录上报 E_CONTEXT_BINDING。"""
        logs = [
            [make_event(1), make_event(2), make_event(3)],
            [make_event(1, role=None), make_event(2), make_event(3, role=None)],
            [make_event(1), make_event(2, request_id=OTHER_REQ)],
            [make_event(1, role=None), make_event(2, role="executor"), make_event(3)],
            [make_event(1), make_event(2, run_id=OTHER_RUN)],
        ]
        for records in logs:
            with self.subTest(records=[(r["seq"], r["request_id"][-2:], r["role"], r["run_id"][-2:]) for r in records]):
                bound = P.assess_event_log(self._log(*records), run_id=RUN)["binding_errors"]
                state = {"run_id": RUN, "last_committed_seq": 0, "committed": {}}
                failed_at = None
                for record in self._log(*records):
                    try:
                        P.append_event(state, record)
                    except P.ProtocolError as exc:
                        self.assertEqual(exc.code, "E_CONTEXT_BINDING")
                        failed_at = record["seq"]
                        break
                if bound:
                    self.assertEqual(failed_at, bound[0])
                    self.assertCode("E_CONTEXT_BINDING", P.recover_next_seq, self._log(*records), run_id=RUN)
                else:
                    self.assertIsNone(failed_at)
                    self.assertEqual(P.recover_next_seq(self._log(*records), run_id=RUN), len(records) + 1)

    def test_A11_context_argument_errors_are_prefixed(self):
        """4.3.1、4.3.7：P2 返工新增（复审 fidelity 视角与变异 M112）。受信 context 参数本身不合法时，
        错误码保持 validate_run_context 的原码，但 field 加前缀 /context、phase 为 context，
        与被校验记录自身字段的错误区分开。"""
        missing_platform = make_context()
        del missing_platform["platform"]
        partial = {"request_id": REQ, "run_id": RUN, "role": "planner"}
        for validator in (lambda ctx: P.validate_run_event(make_event(), registry=self.reg, context=ctx),
                          lambda ctx: P.validate_usage_observation(make_usage(), context=ctx)):
            exc = self.assertCode("E_SCHEMA_FIELDS", validator, missing_platform,
                                  expect_field="/context/platform")
            self.assertEqual(exc.phase, "context")
            self.assertCode("E_SCHEMA_VERSION_TYPE", validator, partial,
                            expect_field="/context/schema_version")
            self.assertCode("E_SCHEMA_TYPE", validator, [], expect_field="/context")

    def test_A11_record_depth_includes_payload(self):
        """01-D04、A.2：P2 返工新增（复审 json 视角）。整条记录（含 payload）共用 64 层上限：payload 自身
        64 层时整条记录 65 层 → E_JSON_LIMIT，与 stable_snapshot_bytes、strict_json_loads、append_event 的
        判断一致；payload 63 层时各处都接受。"""
        def nested(levels):
            value: dict = {}
            for _ in range(levels - 1):
                value = {"a": value}
            return value

        too_deep = make_event(payload=nested(64))
        self.assertCode("E_JSON_LIMIT", P.validate_run_event, too_deep, registry=self.reg,
                        event_types=self.types)
        self.assertCode("E_JSON_LIMIT", P.stable_snapshot_bytes, too_deep)
        self.assertCode("E_JSON_LIMIT", P.strict_json_loads, json.dumps(too_deep).encode())
        ok = make_event(payload=nested(63))
        report = P.validate_run_event(ok, registry=self.reg, event_types=self.types)
        self.assertIs(report["payload_validated"], True)
        self.assertEqual(P.strict_json_loads(P.stable_snapshot_bytes(ok)), ok)

    def test_A11_event_type_allowed_sources_validated(self):
        """4.3.1、protocols-api.md 第 11 节：P2 返工新增（复审变异 M111）。allowed_sources 必须是
        {core, vendor} 的非空子集。"""
        for sources in ({"core", "bogus"}, frozenset(), "core"):
            with self.subTest(sources=sources):
                with self.assertRaises(ValueError):
                    P.EventType("x.bad", sources, None, "core")
        with self.assertRaises(ValueError):
            P.ProtocolError("E_JSON_SYNTAX", source_ref={"kind": "x"})

    def test_A12_segment_sizes_values_validated(self):
        """4.3.3：P2 返工新增（复审 events-usage 视角）。segment_sizes 来自受信封存索引；实际用到的条目值
        不是精确 int → TypeError（不再泄漏未分类的比较错误，也不把 True 当作 1、把 10.5 当作大小），
        越界 → ValueError。"""
        ref = make_segment_ref()
        for bad in ("100", True, 10.5, None):
            with self.subTest(size=bad):
                with self.assertRaises(TypeError):
                    P.validate_raw_span(make_span(ref, 0, 1), registry=self.reg,
                                        segment_sizes={ref["sha256"]: bad})
        with self.assertRaises(ValueError):
            P.validate_raw_span(make_span(ref, 0, 1), registry=self.reg,
                                segment_sizes={ref["sha256"]: -1})


# ===========================================================================
# 分维度状态视图（4.1.4、4.3.4；01-F040、F041，01-A05）
# ===========================================================================
class RunDimensionTests(ProtocolTestCase):
    AGGREGATE_KEYS = {"success", "ok", "passed", "overall"}

    def dims(self, **kw):
        base = dict(process_exited=None, exit_code=None, cancelled_by=None, end_evidence=None,
                    protocol_integrity=None, usage_complete=None, wait_returncode=None,
                    legacy_attempt_state=None, legacy_verdict=None, approval_ref=None,
                    integration_observation=None)
        base.update(kw)
        result = P.build_run_dimensions(**base)
        self.assertEqual(all_keys(result) & self.AGGREGATE_KEYS, set(),
                         "不得提供覆盖所有含义的聚合键（4.1.4）")
        return result

    def test_A05_dimension_keys(self):
        """4.1.4：各维度分开表达；全部未知时各维度保持未知。"""
        result = self.dims()
        for key in ("process_observation", "protocol_observation", "wait_observation",
                    "protocol_complete", "protocol_conflict", "cancelled", "usage_complete",
                    "legacy_attempt_state", "legacy_verdict", "approval_present",
                    "contract_approval_ref", "integration_observation"):
            self.assertIn(key, result)
        self.assertEqual(result["protocol_observation"], {"end_evidence": None, "integrity": None})
        self.assertIsNone(result["protocol_complete"])
        self.assertIsNone(result["usage_complete"])
        self.assertIsNone(result["legacy_verdict"])
        self.assertIsNone(result["process_observation"]["exited"])

    def test_F040_exit_zero_without_end_evidence(self):
        """01-F040 / 4.3.4：退出 0 但缺结束证据 → 进程正常退出，协议不完整；不自动 PASS。"""
        result = self.dims(process_exited=True, exit_code=0, end_evidence=None,
                           protocol_integrity="complete")
        self.assertEqual(result["process_observation"],
                         {"exited": True, "exit_code": 0, "cancelled_by": None})
        self.assertIs(result["protocol_complete"], False)
        self.assertIsNone(result["legacy_verdict"])

    def test_F041_success_claim_with_nonzero_exit(self):
        """01-F041 / 4.3.4：结束事件声称成功但进程非零退出 → protocol_conflict=True，保留退出事实。
        P2 调和修正（规格澄清 C-05）：C.3 要求“保留双方证据”，原测试只核对了退出一方；
        视图的 protocol_observation 必须同时原样保留结束证据与完整性。"""
        result = self.dims(process_exited=True, exit_code=1, end_evidence="success",
                           protocol_integrity="complete")
        self.assertIs(result["protocol_conflict"], True)
        self.assertEqual(result["process_observation"]["exit_code"], 1)
        self.assertEqual(result["protocol_observation"],
                         {"end_evidence": "success", "integrity": "complete"})
        self.assertIsNone(result["legacy_verdict"])
        # 退出非零且没有结束证据：协议同样不完整，冲突未知（缺一方证据时不判冲突）。
        failed = self.dims(process_exited=True, exit_code=1)
        self.assertIs(failed["protocol_complete"], False)
        self.assertIsNone(failed["protocol_conflict"])

    def test_A05_protocol_complete_rules(self):
        """4.3.4：integrity 非 complete → False；未知 → None；退出 0、有结束证据且 integrity complete → True、无冲突。"""
        self.assertIs(self.dims(process_exited=True, exit_code=0, end_evidence="success",
                                protocol_integrity="incomplete")["protocol_complete"], False)
        self.assertIsNone(self.dims(process_exited=True, exit_code=0, end_evidence="success",
                                    protocol_integrity=None)["protocol_complete"])
        full = self.dims(process_exited=True, exit_code=0, end_evidence="success",
                         protocol_integrity="complete")
        self.assertIs(full["protocol_complete"], True)
        self.assertIs(full["protocol_conflict"], False)

    def test_A05_wait_zero_is_only_a_query(self):
        """4.1.4：wait 返回 0 只说明查询/等待动作完成，不说明任务结束、验收通过或已集成。"""
        result = self.dims(wait_returncode=0)
        self.assertEqual(result["wait_observation"],
                         {"returncode": 0, "note": "wait 返回值只说明查询动作"})
        self.assertIsNone(result["process_observation"]["exited"])
        self.assertIsNone(result["protocol_complete"])
        self.assertIsNone(result["legacy_verdict"])
        self.assertIsNone(result["integration_observation"])

    def test_A05_cancel_is_not_success(self):
        """4.3.4：取消后进程退出 → 记录取消来源与退出事实，不归为正常成功。
        P4（第 2 轮复审 events-usage 视角，4.1.4“某维度未知时该维度保持未知”）：cancelled 是三态。没有取消来源
        也没有核对时为 None（不断言“未取消”）；调用方核对过取消来源且没有取消（cancellation_checked=True）
        时为 False；cancelled_by 给出时为 True（空串同样算给出）。"""
        result = self.dims(process_exited=True, exit_code=0, cancelled_by="user")
        self.assertIs(result["cancelled"], True)
        self.assertEqual(result["process_observation"]["cancelled_by"], "user")
        self.assertIsNot(result["protocol_complete"], True)
        self.assertIsNone(self.dims(process_exited=True, exit_code=0)["cancelled"])
        self.assertIsNone(self.dims()["cancelled"])
        self.assertIsNone(self.dims(process_exited=True, exit_code=0, cancellation_checked=False)["cancelled"])
        self.assertIs(self.dims(process_exited=True, exit_code=0, cancellation_checked=True)["cancelled"], False)
        self.assertIs(self.dims(cancelled_by="user", cancellation_checked=True)["cancelled"], True)
        # 第 2 轮复审 tests-mutation P157：按“是否为 None”判断，空串不是“没有取消来源”。
        self.assertIs(self.dims(cancelled_by="")["cancelled"], True)
        for bad in ("yes", 1, 0):
            with self.subTest(cancellation_checked=bad):
                self.assertCode("E_SCHEMA_TYPE", P.build_run_dimensions, cancellation_checked=bad,
                                expect_field="/cancellation_checked")
        self.assertEqual(P.DIMENSIONS_RULE_REVISION, "codekit01-run-dimensions-v2")
        self.assertEqual(self.dims()["rule_revision"], P.DIMENSIONS_RULE_REVISION)

    def test_A05_exit_codes_must_be_exact_int(self):
        """4.3.4、01-A05：P4 新增（第 2 轮复审 tests-mutation Q016）。exit_code 与 wait_returncode 必须是精确
        int：bool（True 会被当成 1、造成虚假冲突）与 1.0、"0" 都 → E_SCHEMA_TYPE；负数（POSIX 信号）接受。"""
        for name, value in (("exit_code", True), ("exit_code", False), ("exit_code", 1.0), ("exit_code", "0"),
                            ("wait_returncode", False), ("wait_returncode", True), ("wait_returncode", 0.0)):
            with self.subTest(name=name, value=value):
                kwargs = {name: value}
                if name == "exit_code":
                    kwargs["end_evidence"] = "success"
                self.assertCode("E_SCHEMA_TYPE", P.build_run_dimensions, expect_field="/" + name, **kwargs)
        self.assertIs(self.dims(exit_code=-15, end_evidence="success")["protocol_conflict"], True)
        self.assertEqual(self.dims(wait_returncode=3)["wait_observation"]["returncode"], 3)

    def test_A05_usage_unknown_separate_from_protocol(self):
        """4.3.4：用量缺失与运行完成分别表达。"""
        result = self.dims(process_exited=True, exit_code=0, end_evidence="success",
                           protocol_integrity="complete", usage_complete=False)
        self.assertIs(result["usage_complete"], False)
        self.assertIs(result["protocol_complete"], True)

    def test_A05_verdict_approval_integration_distinct(self):
        """4.1.4：旧 verdict PASS 不等于已集成；审核记录存在不证明当前字节仍匹配；INTEGRATED 不倒推 PASS；
        旧 attempt 状态原样保留。"""
        passed = self.dims(legacy_verdict="PASS")
        self.assertEqual(passed["legacy_verdict"], "PASS")
        self.assertIsNone(passed["integration_observation"])
        self.assertIs(passed["approval_present"], False)
        integrated = self.dims(integration_observation="INTEGRATED")
        self.assertEqual(integrated["integration_observation"], "INTEGRATED")
        self.assertIsNone(integrated["legacy_verdict"])
        approved = self.dims(approval_ref=copy.deepcopy(CONTRACT_REF))
        self.assertIs(approved["approval_present"], True)
        self.assertIsNone(approved["legacy_verdict"])
        # P4（第 2 轮复审 tests-mutation P156）：按“是否为 None”判断存在，{}、"" 这类假值也算给出了审核引用。
        for falsy in ({}, "", 0, []):
            with self.subTest(approval_ref=repr(falsy)):
                self.assertIs(self.dims(approval_ref=falsy)["approval_present"], True)
                self.assertEqual(self.dims(approval_ref=falsy)["contract_approval_ref"], falsy)
        self.assertEqual(self.dims(legacy_attempt_state="NEEDS_REVIEW")["legacy_attempt_state"],
                         "NEEDS_REVIEW")
        for verdict in P.LEGACY_VERDICTS:
            self.assertEqual(self.dims(legacy_verdict=verdict)["legacy_verdict"], verdict)

    def test_A05_protocol_dimension_branches(self):
        """4.3.4、01-A05：P2 返工新增（复审变异 M31/M32/M33，major）。
        只给 exit_code=0（process_exited 未给）也算已退出，缺结束证据 → protocol_complete=False；
        integrity=pending → False；POSIX 被信号终止的负退出码与 "success" 同时出现 → 冲突 True。"""
        self.assertIs(self.dims(exit_code=0)["protocol_complete"], False)
        self.assertIs(self.dims(process_exited=True, exit_code=0, end_evidence="success",
                                protocol_integrity="pending")["protocol_complete"], False)
        self.assertIs(self.dims(exit_code=-9, end_evidence="success")["protocol_conflict"], True)
        self.assertIs(self.dims(exit_code=0, end_evidence="success")["protocol_conflict"], False)

    def test_A05_conflict_unknown_for_other_end_evidence(self):
        """4.3.4：P2 返工新增（复审 events-usage 视角）。01 只认识结束证据 "success"；其他值（例如
        "failure"，含义由 04 定义）与任何退出码组合时冲突未知（None），不断言“没有冲突”。
        process_exited=False 却给出 exit_code 是自相矛盾的输入 → E_SCHEMA_FIELDS。"""
        for evidence, code in (("failure", 0), ("error", 0), ("failure", 1), ("cancelled", 0)):
            with self.subTest(end_evidence=evidence, exit_code=code):
                result = self.dims(process_exited=True, exit_code=code, end_evidence=evidence,
                                   protocol_integrity="complete")
                self.assertIsNone(result["protocol_conflict"])
                self.assertEqual(result["protocol_observation"]["end_evidence"], evidence)
        self.assertCode("E_SCHEMA_FIELDS", P.build_run_dimensions, process_exited=False, exit_code=0,
                        expect_field="/exit_code")
        self.assertIsNone(self.dims(process_exited=False)["protocol_complete"])

    def test_A05_contract_approval_ref_preserved(self):
        """4.1.4 建议视图提供 contract_approval_ref：P2 返工新增（复审 fidelity 视角）。审核引用原样保留
        （深拷贝）以便追溯；approval_present 与说明文字不变。"""
        ref = copy.deepcopy(CONTRACT_REF)
        result = self.dims(approval_ref=ref)
        self.assertEqual(result["contract_approval_ref"], CONTRACT_REF)
        self.assertIsNot(result["contract_approval_ref"], ref)
        self.assertIs(result["approval_present"], True)
        self.assertIsNone(self.dims()["contract_approval_ref"])

    def test_A05_unknown_legacy_verdict_rejected(self):
        """4.1.4：旧枚举原样保留，不接受新造或改写的 verdict 名称 → E_SCHEMA_FIELDS。"""
        for verdict in ("SUCCESS", "pass", "INTEGRATED", ""):
            with self.subTest(verdict=verdict):
                self.assertCode("E_SCHEMA_FIELDS", P.build_run_dimensions, process_exited=None,
                                exit_code=None, cancelled_by=None, end_evidence=None,
                                protocol_integrity=None, usage_complete=None,
                                wait_returncode=None, legacy_attempt_state=None,
                                legacy_verdict=verdict, approval_ref=None,
                                integration_observation=None)


# ===========================================================================
# 用量观测与观测视图（4.3.7–4.3.9、01-D08；01-F044–F047，01-A06）
# ===========================================================================
class UsageTests(ProtocolTestCase):
    """P2 调和（规格澄清 C-11）：原测试按键名广度优先查找计量与费用桶（规格未固定嵌套位置）。
    现固定为实现与接口说明第 13.2 节的结构：五个计量是视图顶层键，值恰为
    {known_total:int, is_complete:bool, unknown_count:int}；费用在顶层 reported_cost / estimated_cost
    下按币种分组（缺失费用归 "unknown_currency"），每组恰为
    {known_total:十进制字符串, is_complete, unknown_count}；duplicates 为整数计数。"""

    METRIC_KEYS = {"known_total", "is_complete", "unknown_count"}

    def metric(self, view, name):
        self.assertIn(name, P.UNKNOWABLE_USAGE_FIELDS)
        found = view[name]
        self.assertEqual(set(found), self.METRIC_KEYS)
        self.assertIs(type(found["known_total"]), int)
        self.assertIs(type(found["is_complete"]), bool)
        self.assertIs(type(found["unknown_count"]), int)
        return found

    def cost_bucket(self, view, which):
        groups = view[f"{which}_cost"]
        self.assertIsInstance(groups, dict)
        for currency, group in groups.items():
            self.assertTrue(currency == "unknown_currency" or re.fullmatch(r"[A-Z]{3}", currency),
                            currency)
            self.assertEqual(set(group), self.METRIC_KEYS)
            self.assertIsInstance(group["known_total"], str)
            self.assertIs(type(group["is_complete"]), bool)
            self.assertIs(type(group["unknown_count"]), int)
        return groups

    def assertDecimal(self, text, expected):
        self.assertIsInstance(text, str)
        self.assertRegex(text, r"\A(0|[1-9][0-9]*)(\.[0-9]+)?\Z", "金额须为十进制字符串，不用科学计数")
        self.assertEqual(decimal.Decimal(text), decimal.Decimal(expected))

    def test_A06_doc_sample_4_3_9_usage(self):
        """4.3.9 样例逐字取出：全未知用量观测通过校验（null + 原因，不补零）。"""
        obs = P.strict_json_loads(SAMPLE_USAGE.encode("utf-8"))
        before = copy.deepcopy(obs)
        P.validate_usage_observation(obs)
        P.validate_usage_observation(obs, context=make_context())
        self.assertUnchanged(before, obs)

    def test_A06_unknowable_fields_constant(self):
        """4.3.7、4.3.9：可未知字段集合固定。"""
        self.assertEqual(set(P.UNKNOWABLE_USAGE_FIELDS), set(UNKNOWABLE))

    def test_A06_known_observation_and_zero(self):
        """4.3.7：0 表示有证据支持的零，是合法已知值；合法空关联（supersedes/billing_event_id）不需要原因。"""
        P.validate_usage_observation(make_usage())
        P.validate_usage_observation(make_usage(input_tokens=0, output_tokens=0))
        P.validate_usage_observation(make_usage(input_tokens=2**53 - 1))

    def test_F044_missing_values_need_reasons(self):
        """01-F044 / 4.3.7：缺失计量/费用为 null 且必须有原因 → 否则 E_USAGE_UNKNOWN_REASON；
        原因只能给为 null 的可未知字段（observation_kind 以 unknown 表示未知），值为非空短字符串。"""
        P.validate_usage_observation(make_usage(input_tokens=None))
        P.validate_usage_observation(make_usage(reported_cost=None, billing_source="adapter_estimated"))
        cases = [
            make_usage(input_tokens=None, unknown_reasons={}),
            make_usage(reported_cost=None, unknown_reasons={}),
            make_usage(unknown_reasons={"input_tokens": "not_reported"}),
            make_usage(unknown_reasons={"budget_override": "x"}),
            make_usage(unknown_reasons={"usage_id": "x"}),
            make_usage(input_tokens=None, unknown_reasons={"input_tokens": ""}),
            make_usage(input_tokens=None, unknown_reasons={"input_tokens": 1}),
            make_usage(input_tokens=None, unknown_reasons={"input_tokens": "x" * 513}),
            make_usage(unknown_reasons={"observation_kind": "not_reported"}),
            make_usage(observation_kind="unknown", unknown_reasons={}),
        ]
        for obs in cases:
            with self.subTest(reasons=obs["unknown_reasons"], kind=obs["observation_kind"]):
                self.assertCode("E_USAGE_UNKNOWN_REASON", P.validate_usage_observation, obs)

    def test_A06_money_format(self):
        """4.3.7、附录 A money：金额为非负十进制字符串（无符号、千分位、指数、空格，最长 64），
        币种为三位大写字母 → 否则 E_USAGE_VALUE。"""
        for amount in ("0", "0.00", "12.3456", "1" + "0" * 63):
            with self.subTest(amount=amount):
                P.validate_usage_observation(make_usage(reported_cost={"amount": amount,
                                                                       "currency": "USD"}))
        for amount in ("-1", "+1", "1,000", "1e3", " 1", "1 ", "01", "1.", ".5", "1.0.0", "",
                       "\uff11", "1" + "0" * 64, 1, 1.5, None):
            with self.subTest(amount=amount):
                self.assertCode("E_USAGE_VALUE", P.validate_usage_observation,
                                make_usage(reported_cost={"amount": amount, "currency": "USD"}))
        for currency in ("usd", "US", "USDT", "US1", "$", "", None):
            with self.subTest(currency=currency):
                self.assertCode("E_USAGE_VALUE", P.validate_usage_observation,
                                make_usage(estimated_cost={"amount": "1", "currency": currency}))
        # P2 调和（规格澄清 C-03）：money 多出字段也是金额结构错误 → E_USAGE_VALUE（原为“被拒绝即可”）。
        for money in ({"amount": "1", "currency": "USD", "x": 1}, {"amount": "1"}, "1.00 USD",
                      ["1", "USD"]):
            with self.subTest(money=money):
                self.assertCode("E_USAGE_VALUE", P.validate_usage_observation,
                                make_usage(reported_cost=money), expect_field="/reported_cost")

    def test_A06_counter_values(self):
        """4.3.7、4.1.1：计量为精确整数 0..2^53-1 或 null；负数、bool、1.0、字符串、越界被拒绝。
        P2 调和修正（规格澄清 C-09）：原测试接受 E_USAGE_VALUE/E_SCHEMA_TYPE/E_INTEGER_RANGE 任一。
        规格的 E_USAGE_VALUE 只针对 money；计量是新协议整数字段，与 seq、plan_version 等一样按
        require_int：类型不对 → E_SCHEMA_TYPE，越界（含负数）→ E_INTEGER_RANGE。"""
        for value, code in ((-1, "E_INTEGER_RANGE"), (2**53, "E_INTEGER_RANGE"),
                            (True, "E_SCHEMA_TYPE"), (1.0, "E_SCHEMA_TYPE"), ("1", "E_SCHEMA_TYPE")):
            for name in ("input_tokens", "reasoning_tokens"):
                with self.subTest(name=name, value=value):
                    self.assertCode(code, P.validate_usage_observation,
                                    make_usage(**{name: value}), expect_field="/" + name)

    def test_A06_usage_structure_and_enums(self):
        """附录 A usage：字段封闭（E_SCHEMA_FIELDS），枚举字段不接受未登记值。
        P2 调和（规格澄清 C-03）：枚举外 → E_SCHEMA_FIELDS；布尔字段类型不对 → E_SCHEMA_TYPE。"""
        self.assertCode("E_SCHEMA_FIELDS", P.validate_usage_observation, make_usage(extra=1))
        obs = make_usage()
        del obs["evidence_refs"]
        self.assertCode("E_SCHEMA_FIELDS", P.validate_usage_observation, obs)
        for change, code, pointer in (({"billing_source": "free"}, "E_SCHEMA_FIELDS",
                                       "/billing_source"),
                                      ({"observation_kind": "total"}, "E_SCHEMA_FIELDS",
                                       "/observation_kind"),
                                      ({"input_includes_cache": "yes"}, "E_SCHEMA_TYPE",
                                       "/input_includes_cache"),
                                      ({"role": "admin"}, "E_SCHEMA_FIELDS", "/role")):
            with self.subTest(change=change):
                self.assertCode(code, P.validate_usage_observation, make_usage(**change),
                                expect_field=pointer)

    def test_A06_usage_string_length_bounds(self):
        """附录 A usage：P4 新增（第 2 轮复审 tests-mutation Q032）。provider ≤ 128、model ≤ 256、
        billing_event_id ≤ 256 个字符：恰好等于上限接受，多 1 个字符 → E_SCHEMA_FIELDS（field 指向该字段）；
        迷你 Schema 校验器对同一对实例给出相同的接受/拒绝判断。"""
        for name, limit in (("provider", 128), ("model", 256), ("billing_event_id", 256)):
            with self.subTest(field=name):
                at_limit = make_usage(**{name: "p" * limit})
                P.validate_usage_observation(at_limit)
                self.assertEqual(MINI.errors_for_def(at_limit, "usage"), [])
                over = make_usage(**{name: "p" * (limit + 1)})
                exc = self.assertCode("E_SCHEMA_FIELDS", P.validate_usage_observation, over,
                                      expect_field="/" + name)
                self.assertEqual(exc.reason, "string_length_out_of_range")
                self.assertNotEqual(MINI.errors_for_def(over, "usage"), [])

    def test_A06_usage_view_requires_sequence(self):
        """4.3.8、protocols-api.md 13.2：P4 新增（第 2 轮复审 tests-mutation Q017）。usage_view 的参数必须是
        Sequence（可重复读取、长度确定）；迭代器、生成器、str/bytes 与 dict → E_SCHEMA_TYPE。"""
        for value in (iter([make_usage()]), (u for u in [make_usage()]), "usage", b"usage",
                      {"usage-1": make_usage()}, None):
            with self.subTest(value=type(value).__name__):
                self.assertCode("E_SCHEMA_TYPE", P.usage_view, value)
        self.assertEqual(self.metric(P.usage_view((make_usage(),)), "input_tokens")["known_total"], 100)

    def test_A06_billing_event_without_provider_not_summed(self):
        """4.3.8 末行“两个来源范围不明的观测 → E_USAGE_SCOPE_UNKNOWN 或待核对”：P4 新增（第 2 轮复审
        events-usage 视角）。provider 为 null 时账单号的命名空间未知，无法判断同一 billing_event_id 的两条观测
        是重复投递还是两个事件：同一 (request, run, role, billing_event_id) 下有多条可计入的有效观测 →
        E_USAGE_SCOPE_UNKNOWN（reason=billing_event_without_provider_repeated），不再相加成翻倍的 known_total。
        修订链只留链尾、账单号不同、或只有 unknown 观测时不受影响。"""
        def unscoped(usage_id, **kw):
            return make_usage(usage_id, provider=None, billing_event_id="B1", **kw)

        for observations in ([unscoped("d1"), unscoped("d2")],
                             [unscoped("d1"), unscoped("d2", input_tokens=150)],
                             [unscoped("c1", observation_kind="cumulative"),
                              unscoped("c2", observation_kind="cumulative", input_tokens=150)]):
            with self.subTest(ids=[o["usage_id"] for o in observations]):
                exc = self.assertCode("E_USAGE_SCOPE_UNKNOWN", P.usage_view, observations)
                self.assertEqual(exc.reason, "billing_event_without_provider_repeated")
        revised = P.usage_view([unscoped("r1"), unscoped("r2", input_tokens=120, supersedes_usage_id="r1")])
        self.assertEqual(self.metric(revised, "input_tokens")["known_total"], 120)
        self.assertIs(revised["is_complete"], False)  # provider 为 null：范围来源不明
        distinct = P.usage_view([unscoped("d1"), make_usage("d2", provider=None, billing_event_id="B2")])
        self.assertEqual(self.metric(distinct, "input_tokens")["known_total"], 200)
        self.assertIs(self.metric(distinct, "input_tokens")["is_complete"], False)
        with_unknown = P.usage_view([unscoped("d1"), unscoped("u1", observation_kind="unknown")])
        self.assertEqual(self.metric(with_unknown, "input_tokens")["known_total"], 100)
        # P4 第 3 轮（复审 events-usage 视角，minor；tests-mutation X13）：只按 billing_event_id 分组，跨 run、跨 role
        # 同样无法判断是重复投递还是两个事件，不相加（P4 时这里固定为相加得 200）。provider 已知时同样的输入是
        # E_USAGE_CONFLICT，信息更少的 null provider 不能更宽松。
        for change in ({"run_id": OTHER_RUN}, {"role": "executor"}, {"request_id": OTHER_REQ}):
            with self.subTest(cross_scope=change):
                exc = self.assertCode("E_USAGE_SCOPE_UNKNOWN", P.usage_view, [unscoped("d1"), unscoped("d2", **change)])
                self.assertEqual(exc.reason, "billing_event_without_provider_repeated")
                known = [make_usage("d1", billing_event_id="B1"), make_usage("d2", billing_event_id="B1", **change)]
                exc = self.assertCode("E_USAGE_CONFLICT", P.usage_view, known)
                self.assertEqual(exc.reason, "same_billing_event_different_values")

    def test_A06_billing_event_without_provider_uses_whole_revision_chain(self):
        """4.3.8、protocols-api.md 13.2 第 5 步：P4 第 3 轮新增（复审 events-usage 视角，major）。provider 为 null 时，
        第 5b 步与第 5 步同一口径：一条修订链代表链上**全部**成员的账单号，不只看链尾自己的 billing_event_id。
        a(BX,100) 被 b(无账单号,120) 修订后，c(BX,100) 再次投递：provider 已知时 c 随 a 去重（计 120、完整）；
        provider 为 null 时无法去重，修复前把 b 与 c 相加成 220（只标不完整，是高估），现在报
        E_USAGE_SCOPE_UNKNOWN（billing_event_without_provider_repeated）。变体：b 带另一个账单号 BY、c 数值不同。"""
        def obs(usage_id, provider, billing, tokens, supersedes=None):
            return make_usage(usage_id, provider=provider, billing_event_id=billing, input_tokens=tokens,
                              supersedes_usage_id=supersedes)

        for b_billing, c_tokens in ((None, 100), ("BY", 120), (None, 120), ("BY", 100)):
            with self.subTest(b_billing=b_billing, c_tokens=c_tokens):
                unscoped = [obs("a", None, "BX", 100), obs("b", None, b_billing, 120, "a"),
                            obs("c", None, "BX", c_tokens)]
                exc = self.assertCode("E_USAGE_SCOPE_UNKNOWN", P.usage_view, unscoped)
                self.assertEqual(exc.reason, "billing_event_without_provider_repeated")
        known = P.usage_view([obs("a", "synthetic-provider", "BX", 100),
                              obs("b", "synthetic-provider", None, 120, "a"),
                              obs("c", "synthetic-provider", "BX", 100)])
        self.assertEqual(self.metric(known, "input_tokens"), {"known_total": 120, "is_complete": True,
                                                              "unknown_count": 0})
        self.assertEqual(known["superseded"], ["a", "c"])
        # 同一条修订链的多个成员带同一账单号只算一次；c 为 unknown 观测时不计入，也不触发。
        chain = P.usage_view([obs("a", None, "BX", 100), obs("b", None, "BX", 120, "a")])
        self.assertEqual(self.metric(chain, "input_tokens")["known_total"], 120)
        with_unknown = P.usage_view([obs("a", None, "BX", 100), obs("b", None, None, 120, "a"),
                                     make_usage("c", provider=None, billing_event_id="BX",
                                                observation_kind="unknown")])
        self.assertEqual(self.metric(with_unknown, "input_tokens")["known_total"], 120)
        self.assertIs(self.metric(with_unknown, "input_tokens")["is_complete"], False)

    def test_A06_billing_event_null_and_known_provider_not_summed(self):
        """4.3.4、4.3.8 末行、protocols-api.md 13.2 第 5b 步：P4 第 4 轮新增（复审 events-usage 视角，major）。
        provider 为 null 的观测与 provider 已知的观测带同一 billing_event_id 时，同样无法判断是同一账单事件还是
        两个事件，不能相加。修复前第 5b 步只收 provider 为 null 的成员：
        - a(P,BX) 与 b(null,BX) 跨 run、跨 role、跨 request 时直接相加得 200；
        - 修订链变体 a(null,BX,100) ← b(P,无账单号,120)，c(P,BX,100) 是 a 的同号重投：6 种到达顺序都得 220、
          USD 2.20 且标为完整（重复计费）。
        现在都 → E_USAGE_SCOPE_UNKNOWN（billing_event_without_provider_repeated）。同一 (request, run, role) 下先由
        第 6 步的范围歧义判定报 scope_provider_or_model_unknown。对照：provider 全部已知时同样的修订链得 120、
        完整；同一条修订链内 null 与已知成员同号只算一次；provider 为 null 的成员只有 unknown 观测时不触发。"""
        usd = {"1.00": {"amount": "1.00", "currency": "USD"}, "1.20": {"amount": "1.20", "currency": "USD"}}

        def obs(usage_id, provider, billing, tokens, supersedes=None, amount="1.00", **kw):
            kw.setdefault("role", "executor")
            return make_usage(usage_id, provider=provider, billing_event_id=billing, input_tokens=tokens,
                              supersedes_usage_id=supersedes, reported_cost=usd[amount],
                              estimated_cost=usd[amount], **kw)

        for change in ({"run_id": OTHER_RUN}, {"role": "planner"}, {"request_id": OTHER_REQ}):
            pair = [obs("a", "synthetic-provider", "BX", 100), obs("b", None, "BX", 100, **change)]
            for observations in (pair, pair[::-1]):
                with self.subTest(cross_scope=change, order=[o["usage_id"] for o in observations]):
                    exc = self.assertCode("E_USAGE_SCOPE_UNKNOWN", P.usage_view, observations)
                    self.assertEqual(exc.reason, "billing_event_without_provider_repeated")
        exc = self.assertCode("E_USAGE_SCOPE_UNKNOWN", P.usage_view,
                              [obs("a", "synthetic-provider", "BX", 100), obs("b", None, "BX", 100)])
        self.assertEqual(exc.reason, "scope_provider_or_model_unknown")
        for c_tokens in (100, 120):
            chain = [obs("a", None, "BX", 100), obs("b", "synthetic-provider", None, 120, "a", amount="1.20"),
                     obs("c", "synthetic-provider", "BX", c_tokens)]
            for observations in itertools.permutations(chain):
                with self.subTest(c_tokens=c_tokens, order=[o["usage_id"] for o in observations]):
                    exc = self.assertCode("E_USAGE_SCOPE_UNKNOWN", P.usage_view, list(observations))
                    self.assertEqual(exc.reason, "billing_event_without_provider_repeated")
        known_chain = [obs("a", "synthetic-provider", "BX", 100),
                       obs("b", "synthetic-provider", None, 120, "a", amount="1.20"),
                       obs("c", "synthetic-provider", "BX", 100)]
        for observations in itertools.permutations(known_chain):
            with self.subTest(known_order=[o["usage_id"] for o in observations]):
                view = P.usage_view(list(observations))
                self.assertEqual(self.metric(view, "input_tokens"),
                                 {"known_total": 120, "is_complete": True, "unknown_count": 0})
                self.assertDecimal(self.cost_bucket(view, "reported")["USD"]["known_total"], "1.20")
                self.assertEqual(view["superseded"], ["a", "c"])
                self.assertIs(view["is_complete"], True)
        same_chain = P.usage_view([obs("a", None, "BX", 100), obs("b", "synthetic-provider", "BX", 120, "a",
                                                                   amount="1.20")])
        self.assertEqual(self.metric(same_chain, "input_tokens")["known_total"], 120)
        self.assertEqual(same_chain["counted_usage_ids"], ["b"])
        # provider 为 null 的成员只有 unknown 观测（不计入）：不同 provider 的同号观测属于不同的命名空间，照常相加。
        distinct_providers = P.usage_view([make_usage("u", provider=None, billing_event_id="BX",
                                                      observation_kind="unknown"),
                                           obs("p1", "provider-one", "BX", 100),
                                           obs("p2", "provider-two", "BX", 100)])
        self.assertEqual(self.metric(distinct_providers, "input_tokens")["known_total"], 200)
        self.assertIs(self.metric(distinct_providers, "input_tokens")["is_complete"], False)

    def test_A06_billing_event_chain_revised_to_unknown(self):
        """4.3.8、protocols-api.md 13.2 第 5b 步：P4 第 5 轮新增（复审 events-usage 视角，major）。第 5b 步原来只在
        链尾可计入时登记账单号：a(BX,delta,100) 被 r(observation_kind=unknown) 修订后，a 的账单号不再登记。于是只要
        a 或 c 的 provider 为 null，同号的 c 就被单独计入——c=100 是 a 的重投（被替代的值复活），c=150 是冲突值
        （冲突被静默接受）；而 provider 全部已知时，同样的输入随 a 一起被替代（计 0）或报 E_USAGE_CONFLICT。
        现在按成员判定：a 自身是 delta，所以链 a←r 代表 BX；c 另代表 BX 且可计入 → E_USAGE_SCOPE_UNKNOWN
        （billing_event_without_provider_repeated）。覆盖 a、c 的 provider 取 null/已知的四种组合，c 取 100 与 150，
        同 run 与跨 run，全部 6 种到达顺序；provider 全部已知时的 0 / E_USAGE_CONFLICT 作对照。另测：没有 c 时两种
        provider 都计 0、不完整；两条代表链都不可计入（a←r1、b←r2，r1、r2 都是 unknown）时不触发；反方向，成员
        自身是 unknown、所在链的链尾可计入（u(null,BX,unknown) ← b，另有同号的 c）时照常登记并报错，与 provider
        全部已知时的 E_USAGE_CONFLICT 对照（保留 P4 第 4 轮口径，变异抽查 M3）。"""
        def usd(amount):
            return {"amount": amount, "currency": "USD"}

        def delta(usage_id, provider, tokens, amount, supersedes=None, **kw):
            return make_usage(usage_id, provider=provider, billing_event_id="BX", input_tokens=tokens,
                              reported_cost=usd(amount), estimated_cost=usd(amount),
                              supersedes_usage_id=supersedes, **kw)

        def unknown_revision(usage_id, target):
            return make_usage(usage_id, observation_kind="unknown", input_tokens=None, cache_read_tokens=None,
                              cache_write_tokens=None, output_tokens=None, reasoning_tokens=None,
                              reported_cost=None, estimated_cost=None, billing_source="unavailable",
                              supersedes_usage_id=target)

        known = "synthetic-provider"
        for a_provider, c_provider in itertools.product((None, known), repeat=2):
            for c_tokens, c_amount in ((100, "1.00"), (150, "1.50")):
                for c_run in (RUN, OTHER_RUN):
                    chain = [delta("a", a_provider, 100, "1.00"), unknown_revision("r", "a"),
                             delta("c", c_provider, c_tokens, c_amount, run_id=c_run)]
                    for observations in itertools.permutations(chain):
                        with self.subTest(a_provider=a_provider, c_provider=c_provider, c_tokens=c_tokens,
                                          c_run=c_run, order=[o["usage_id"] for o in observations]):
                            if a_provider is None or c_provider is None:
                                exc = self.assertCode("E_USAGE_SCOPE_UNKNOWN", P.usage_view, list(observations))
                                self.assertEqual(exc.reason, "billing_event_without_provider_repeated")
                            elif c_tokens == 100 and c_run == RUN:  # 对照：c 是 a 的重投，随 a 一起被替代
                                view = P.usage_view(list(observations))
                                self.assertEqual(self.metric(view, "input_tokens"),
                                                 {"known_total": 0, "is_complete": False, "unknown_count": 1})
                                self.assertEqual(view["superseded"], ["a", "c"])
                                self.assertEqual(view["counted_usage_ids"], [])
                            else:  # 对照：数值或 run 不同，同一账单事件的有效值冲突
                                exc = self.assertCode("E_USAGE_CONFLICT", P.usage_view, list(observations))
                                self.assertEqual(exc.reason, "same_billing_event_different_values")
        for a_provider in (None, known):
            with self.subTest(without_c=a_provider):
                view = P.usage_view([delta("a", a_provider, 100, "1.00"), unknown_revision("r", "a")])
                self.assertEqual(self.metric(view, "input_tokens"),
                                 {"known_total": 0, "is_complete": False, "unknown_count": 1})
                self.assertEqual(view["superseded"], ["a"])
                self.assertIs(view["is_complete"], False)
        # 两条代表链都不可计入：没有值被计入，不触发（“至少一条可计入”这一条件）。
        both_unknown = P.usage_view([delta("a", None, 100, "1.00"), unknown_revision("r1", "a"),
                                     delta("b", None, 150, "1.50"), unknown_revision("r2", "b")])
        self.assertEqual(self.metric(both_unknown, "input_tokens")["known_total"], 0)
        self.assertEqual(both_unknown["counted_usage_ids"], [])
        self.assertEqual(both_unknown["superseded"], ["a", "b"])
        self.assertIs(both_unknown["is_complete"], False)
        # 反方向：成员自身是 unknown、但所在链的有效链尾可计入时照常登记（P4 第 4 轮口径保留；“只按成员自身的
        # observation_kind 判定”的变异会漏掉这一类）。u(null,BX,unknown) ← b(已知 provider,无账单号,120)，另有
        # c(已知 provider,BX,100)：null provider 时 → E_USAGE_SCOPE_UNKNOWN；provider 全部已知时同样的输入是
        # E_USAGE_CONFLICT（BX 的有效值 120 与 c 的 100 不同）。
        for u_provider in (None, known):
            for c_run in (RUN, OTHER_RUN):
                chain = [make_usage("u", provider=u_provider, billing_event_id="BX", observation_kind="unknown"),
                         make_usage("b", provider=known, input_tokens=120, supersedes_usage_id="u"),
                         make_usage("c", provider=known, billing_event_id="BX", run_id=c_run)]
                for observations in itertools.permutations(chain):
                    with self.subTest(unknown_member=u_provider, c_run=c_run,
                                      order=[o["usage_id"] for o in observations]):
                        if u_provider is None:
                            exc = self.assertCode("E_USAGE_SCOPE_UNKNOWN", P.usage_view, list(observations))
                            self.assertEqual(exc.reason, "billing_event_without_provider_repeated")
                        else:
                            exc = self.assertCode("E_USAGE_CONFLICT", P.usage_view, list(observations))
                            self.assertEqual(exc.reason, "same_billing_event_different_values")

    def test_A06_supersedes_self(self):
        """4.3.8：观测不能修订自身 → E_USAGE_CONFLICT。"""
        self.assertCode("E_USAGE_CONFLICT", P.validate_usage_observation,
                        make_usage("usage-1", supersedes_usage_id="usage-1"))

    def test_A06_usage_context_binding(self):
        """4.3.7：request/run/role 从可信调用上下文绑定 → 不一致时 E_CONTEXT_BINDING。"""
        ctx = make_context()
        P.validate_usage_observation(make_usage(), context=ctx)
        for change in ({"request_id": OTHER_REQ}, {"run_id": OTHER_RUN}, {"role": "executor"}):
            with self.subTest(change=change):
                self.assertCode("E_CONTEXT_BINDING", P.validate_usage_observation,
                                make_usage(**change), context=ctx)

    def test_A06_view_is_not_accounting(self):
        """4.3.7、01-D08：usage_view 只是观测视图，不是记账（07 唯一记账）。"""
        view = P.usage_view([make_usage()])
        self.assertEqual(view["view_kind"], "usage-observation-view")
        self.assertIs(view["is_accounting"], False)
        metric = self.metric(view, "input_tokens")
        self.assertEqual((metric["known_total"], metric["is_complete"], metric["unknown_count"]),
                         (100, True, 0))

    def test_F037_usage_replay_counted_once(self):
        """01-F037 / 4.3.8：同一 usage_id 再次投递（字节相同）→ 只计一次，duplicates+1。"""
        u = make_usage("usage-1")
        view = P.usage_view([u, copy.deepcopy(u)])
        self.assertEqual(self.metric(view, "input_tokens")["known_total"], 100)
        self.assertEqual(view["duplicates"], 1)  # 规格澄清 C-11：整数计数
        self.assertEqual(view["counted_usage_ids"], ["usage-1"])
        self.assertDecimal(self.cost_bucket(view, "reported")["USD"]["known_total"], "0.10")

    def test_A06_same_usage_id_different_content(self):
        """4.3.8：同 usage_id 内容不同 → E_USAGE_CONFLICT。"""
        self.assertCode("E_USAGE_CONFLICT", P.usage_view,
                        [make_usage("usage-1"), make_usage("usage-1", input_tokens=101)])

    def test_A06_billing_event_id_dedup(self):
        """4.3.8：(provider, billing_event_id) 相同而 usage_id 不同：数值相同视为重复，不同 → E_USAGE_CONFLICT。"""
        a = make_usage("usage-1", billing_event_id="bill-1")
        b = make_usage("usage-2", billing_event_id="bill-1")
        view = P.usage_view([a, b])
        self.assertEqual(self.metric(view, "input_tokens")["known_total"], 100)
        self.assertEqual(view["duplicates"], 1)
        c = make_usage("usage-3", billing_event_id="bill-1", input_tokens=150)
        self.assertCode("E_USAGE_CONFLICT", P.usage_view, [a, c])

    def test_F045_cumulative_takes_last(self):
        """01-F045 / 4.3.8：同范围累计 100 后累计 150 → 当前累计 150（不是 250）。"""
        view = P.usage_view([make_usage("usage-1", observation_kind="cumulative", input_tokens=100),
                             make_usage("usage-2", observation_kind="cumulative", input_tokens=150)])
        metric = self.metric(view, "input_tokens")
        self.assertEqual(metric["known_total"], 150)
        self.assertIs(metric["is_complete"], True)

    def test_F045_deltas_add(self):
        """01-F045 / 4.3.8：两条独立 delta 100 与 50 → 合计 150（不是取最大值）。"""
        view = P.usage_view([make_usage("usage-1", input_tokens=100),
                             make_usage("usage-2", input_tokens=50)])
        self.assertEqual(self.metric(view, "input_tokens")["known_total"], 150)

    def test_F045_mixed_kinds_in_same_scope(self):
        """01-F045 / 4.3.8：同范围既有 delta 又有 cumulative/final → E_USAGE_SCOPE_UNKNOWN（不猜口径）。"""
        for other in ("cumulative", "final"):
            with self.subTest(other=other):
                self.assertCode("E_USAGE_SCOPE_UNKNOWN", P.usage_view,
                                [make_usage("usage-1"),
                                 make_usage("usage-2", observation_kind=other)])

    def test_F045_scopes_are_separate(self):
        """4.3.8：范围键 (request, run, role, provider, model) 不同则各自按口径处理后再汇总。"""
        view = P.usage_view([
            make_usage("usage-1", observation_kind="cumulative", input_tokens=100),
            make_usage("usage-2", observation_kind="cumulative", input_tokens=150),
            make_usage("usage-3", model="synthetic-model-b", input_tokens=10),
            make_usage("usage-4", model="synthetic-model-b", input_tokens=20),
        ])
        self.assertEqual(self.metric(view, "input_tokens")["known_total"], 180)

    def test_F045_conflicting_finals(self):
        """4.3.8：同范围多个 final 数值不同且无修订链 → E_USAGE_CONFLICT。"""
        self.assertCode("E_USAGE_CONFLICT", P.usage_view,
                        [make_usage("usage-1", observation_kind="final", input_tokens=100),
                         make_usage("usage-2", observation_kind="final", input_tokens=120)])

    def test_F045_final_revises_previous(self):
        """4.3.8：final 明确修订前一观测 → 按修订链替代，不把旧值与新值加总。"""
        view = P.usage_view([
            make_usage("usage-1", observation_kind="cumulative", input_tokens=100),
            make_usage("usage-2", observation_kind="final", input_tokens=120,
                       supersedes_usage_id="usage-1"),
        ])
        self.assertEqual(self.metric(view, "input_tokens")["known_total"], 120)

    def test_F044_partial_unknown_propagates(self):
        """01-F044 / 4.3.8：部分输入已知 100、另一部分未知 → 显示已知 100 并标记不完整；各计量独立。"""
        view = P.usage_view([make_usage("usage-1", input_tokens=100),
                             make_usage("usage-2", input_tokens=None)])
        metric = self.metric(view, "input_tokens")
        self.assertEqual(metric["known_total"], 100)
        self.assertIs(metric["is_complete"], False)
        self.assertEqual(metric["unknown_count"], 1)
        output = self.metric(view, "output_tokens")
        self.assertEqual(output["known_total"], 20)
        self.assertIs(output["is_complete"], True)

    def test_F044_all_unknown_sample_view(self):
        """01-F044 / 4.3.9：全未知样例 → 各计量 known_total=0、不完整、unknown_count=1；费用未知，不补零。"""
        view = P.usage_view([json.loads(SAMPLE_USAGE)])
        for name in TOKEN_METRICS:
            with self.subTest(metric=name):
                metric = self.metric(view, name)
                self.assertEqual(metric["known_total"], 0)
                self.assertIs(metric["is_complete"], False)
                self.assertEqual(metric["unknown_count"], 1)
        for which in ("reported", "estimated"):
            with self.subTest(cost=which):
                unknown = self.cost_bucket(view, which).get("unknown_currency")
                self.assertIsNotNone(unknown, f"{which} 费用缺失应计入 unknown_currency")
                self.assertEqual(unknown["unknown_count"], 1)
                self.assertIs(unknown["is_complete"], False)

    def test_A06_cumulative_null_field_keeps_known_lower_bound(self):
        """4.3.8“部分未知 → 展示已知部分并标不完整”、protocols-api.md 13.2：P4 第 3 轮新增（复审 events-usage 视角）。
        cumulative/final 只计入最后一条；它的某个字段为 null 时，此前已证明的累计值不能丢：known_total 取序列中此前
        最后一个已知值（序列已校验单调不减，是合法下界），is_complete=false、unknown_count+1；费用按序列已校验的
        唯一币种归组并标为不完整，不再只落入 unknown_currency（修复前分别得 0 与只有 unknown_currency 组，比换成
        observation_kind=unknown 的同样输入还少）。其他计量不受影响。"""
        def cumulative(usage_id, **kw):
            return make_usage(usage_id, observation_kind="cumulative", **kw)

        view = P.usage_view([cumulative("c1", input_tokens=100), cumulative("c2", input_tokens=None)])
        self.assertEqual(self.metric(view, "input_tokens"),
                         {"known_total": 100, "is_complete": False, "unknown_count": 1})
        self.assertEqual(self.metric(view, "output_tokens"),
                         {"known_total": 10, "is_complete": True, "unknown_count": 0})
        self.assertEqual(view["counted_usage_ids"], ["c2"])
        self.assertEqual(view["scopes"][0]["ignored_usage_ids"], ["c1"])
        unknown_kind = P.usage_view([cumulative("c1", input_tokens=100),
                                     make_usage("c2", observation_kind="unknown", input_tokens=None)])
        self.assertEqual(self.metric(unknown_kind, "input_tokens")["known_total"], 100)
        # 取此前**最后一个**已知值（单调不减序列中的最大已知值），跳过中间同为 null 的观测。
        view = P.usage_view([cumulative("c1", input_tokens=100), cumulative("c2", input_tokens=150),
                             cumulative("c3", input_tokens=None), cumulative("c4", input_tokens=None)])
        self.assertEqual(self.metric(view, "input_tokens"),
                         {"known_total": 150, "is_complete": False, "unknown_count": 1})
        # final 同样：final 的 null 字段取此前最后一个已知的累计值。
        view = P.usage_view([cumulative("c1", input_tokens=100),
                             make_usage("f1", observation_kind="final", input_tokens=None)])
        self.assertEqual(self.metric(view, "input_tokens"),
                         {"known_total": 100, "is_complete": False, "unknown_count": 1})
        # 费用：USD 组保留已证明的金额并标为不完整，不生成 unknown_currency 组。
        view = P.usage_view([cumulative("c1", reported_cost={"amount": "1.00", "currency": "USD"}),
                             cumulative("c2", reported_cost=None)])
        self.assertEqual(self.cost_bucket(view, "reported"),
                         {"USD": {"known_total": "1.00", "is_complete": False, "unknown_count": 1}})
        self.assertIs(view["is_complete"], False)
        # 序列中没有任何已知值时，仍是 0 / unknown_currency。
        view = P.usage_view([cumulative("c1", input_tokens=None, reported_cost=None)])
        self.assertEqual(self.metric(view, "input_tokens"),
                         {"known_total": 0, "is_complete": False, "unknown_count": 1})
        self.assertEqual(self.cost_bucket(view, "reported"),
                         {"unknown_currency": {"known_total": "0", "is_complete": False, "unknown_count": 1}})
        # delta 不做下界替代：各条独立相加，null 只计为未知。
        view = P.usage_view([make_usage("d1", input_tokens=100), make_usage("d2", input_tokens=None)])
        self.assertEqual(self.metric(view, "input_tokens"),
                         {"known_total": 100, "is_complete": False, "unknown_count": 1})

    def test_A06_only_unknown_observations_shape(self):
        """protocols-api.md 13.2 返回值：P4 第 3 轮新增（复审 events-usage 视角，文档更正）。只有空输入（没有任何有效
        观测）才得到“各计量 unknown_count=0、两类费用各一个 unknown_count=0 的 unknown_currency 组”；只含 unknown
        观测时，各计量 unknown_count 等于 unknown 观测数，费用按该观测自身的币种（缺失时 unknown_currency）分组，
        都标为不完整，counted_usage_ids 为空。"""
        view = P.usage_view([make_usage("u1", observation_kind="unknown"),
                             make_usage("u2", observation_kind="unknown", reported_cost=None,
                                        billing_source="unavailable")])
        for name in TOKEN_METRICS:
            with self.subTest(metric=name):
                self.assertEqual(self.metric(view, name), {"known_total": 0, "is_complete": False,
                                                           "unknown_count": 2})
        self.assertEqual(self.cost_bucket(view, "reported"),
                         {"USD": {"known_total": "0", "is_complete": False, "unknown_count": 1},
                          "unknown_currency": {"known_total": "0", "is_complete": False, "unknown_count": 1}})
        self.assertEqual(view["counted_usage_ids"], [])
        self.assertIs(view["is_complete"], False)
        self.assertEqual(view["scopes"][0]["mode"], "unknown_only")

    def test_A06_unknown_kind_values_not_counted(self):
        """4.3.8、01-T2：observation_kind=unknown 的数值不计入并使相关计量不完整。"""
        view = P.usage_view([make_usage("usage-1", observation_kind="unknown", input_tokens=100)])
        metric = self.metric(view, "input_tokens")
        self.assertEqual(metric["known_total"], 0)
        self.assertIs(metric["is_complete"], False)
        self.assertEqual(metric["unknown_count"], 1)
        # P2 返工（复审变异 M43，major）：同一范围内 delta 与 unknown 并存时，unknown 的数值不计入。
        view = P.usage_view([make_usage("usage-1", input_tokens=100),
                             make_usage("usage-2", observation_kind="unknown", input_tokens=50)])
        metric = self.metric(view, "input_tokens")
        self.assertEqual((metric["known_total"], metric["is_complete"], metric["unknown_count"]),
                         (100, False, 1))
        self.assertEqual(view["counted_usage_ids"], ["usage-1"])
        self.assertEqual(view["scopes"][0]["unknown_kind_usage_ids"], ["usage-2"])

    def test_F046_cache_and_reasoning_not_added(self):
        """01-F046 / 4.3.8：input=1000 且已包含 cache_read=800 → 输入仍为 1000，缓存细分为 800，不得 1800；
        reasoning 同理。"""
        view = P.usage_view([make_usage("usage-1", input_tokens=1000, cache_read_tokens=800,
                                        input_includes_cache=True, output_tokens=500,
                                        reasoning_tokens=200, output_includes_reasoning=True)])
        self.assertEqual(self.metric(view, "input_tokens")["known_total"], 1000)
        self.assertEqual(self.metric(view, "cache_read_tokens")["known_total"], 800)
        self.assertEqual(self.metric(view, "output_tokens")["known_total"], 500)
        self.assertEqual(self.metric(view, "reasoning_tokens")["known_total"], 200)
        # P4（第 2 轮复审 tests-mutation Q043）：口径标志只记录分布；None 进 unknown 桶，不变成已知的 false。
        view = P.usage_view([
            make_usage("usage-1", input_includes_cache=True, output_includes_reasoning=None),
            make_usage("usage-2", input_includes_cache=None, output_includes_reasoning=False),
            make_usage("usage-3", input_includes_cache=False, output_includes_reasoning=None),
            make_usage("usage-4", input_includes_cache=None, output_includes_reasoning=True)])
        self.assertEqual(view["distributions"],
                         {"input_includes_cache": {"true": 1, "false": 1, "unknown": 2},
                          "output_includes_reasoning": {"true": 1, "false": 1, "unknown": 2}})
        self.assertEqual(P.usage_view([make_usage(input_includes_cache=None)])["distributions"]
                         ["input_includes_cache"], {"true": 0, "false": 0, "unknown": 1})

    def test_A06_estimate_never_counted_as_reported(self):
        """4.3.8：reported_cost 缺失只有 estimated_cost → 实际费用未知（unknown_currency），估算单列。"""
        view = P.usage_view([make_usage("usage-1", reported_cost=None,
                                        estimated_cost={"amount": "0.05", "currency": "USD"},
                                        billing_source="adapter_estimated")])
        reported = self.cost_bucket(view, "reported")
        self.assertEqual(reported["unknown_currency"]["unknown_count"], 1)
        self.assertIs(reported["unknown_currency"]["is_complete"], False)
        # 规格澄清 C-11：估算不会在 reported 下生成任何币种组。
        self.assertEqual(set(reported), {"unknown_currency"})
        estimated = self.cost_bucket(view, "estimated")
        self.assertDecimal(estimated["USD"]["known_total"], "0.05")
        self.assertEqual(set(estimated), {"USD"})

    def test_F047_currencies_not_mixed(self):
        """01-F047 / 4.3.8：USD 与 CNY 分币种汇总，不直接相加。"""
        view = P.usage_view([
            make_usage("usage-1", reported_cost={"amount": "0.10", "currency": "USD"}),
            make_usage("usage-2", reported_cost={"amount": "0.70", "currency": "CNY"},
                       estimated_cost={"amount": "0.60", "currency": "CNY"}),
        ])
        reported = self.cost_bucket(view, "reported")
        self.assertDecimal(reported["USD"]["known_total"], "0.10")
        self.assertDecimal(reported["CNY"]["known_total"], "0.70")
        self.assertEqual(set(reported), {"USD", "CNY"})
        self.assertTrue(all(g["is_complete"] for g in reported.values()))

    def test_A06_unknown_cost_marks_all_currency_groups(self):
        """4.3.8“任何缺失证据都必须向聚合结果传播”：P2 调和新增（规格澄清 C-11）。缺失的
        reported_cost 币种未知，可能属于任何币种，因此同类费用的每个币种组都标为不完整；
        已知金额照常显示，estimated 不受 reported 缺失影响。"""
        view = P.usage_view([
            make_usage("usage-1", reported_cost={"amount": "0.10", "currency": "USD"}),
            make_usage("usage-2", reported_cost=None),
        ])
        reported = self.cost_bucket(view, "reported")
        self.assertDecimal(reported["USD"]["known_total"], "0.10")
        self.assertIs(reported["USD"]["is_complete"], False)
        self.assertEqual(reported["unknown_currency"]["unknown_count"], 1)
        estimated = self.cost_bucket(view, "estimated")
        self.assertDecimal(estimated["USD"]["known_total"], "0.18")
        self.assertIs(estimated["USD"]["is_complete"], True)

    def test_F047_same_currency_revision(self):
        """01-F047 / 4.3.8：同币种修订 → 被替代观测不计入，保留修订后的值。"""
        view = P.usage_view([
            make_usage("usage-1", input_tokens=100),
            make_usage("usage-2", input_tokens=90, supersedes_usage_id="usage-1",
                       reported_cost={"amount": "0.08", "currency": "USD"}),
        ])
        self.assertEqual(self.metric(view, "input_tokens")["known_total"], 90)
        self.assertDecimal(self.cost_bucket(view, "reported")["USD"]["known_total"], "0.08")

    def test_F047_revision_currency_mismatch(self):
        """01-F047 / 4.3.8：修订前后币种不同 → E_USAGE_CURRENCY_MISMATCH。"""
        self.assertCode("E_USAGE_CURRENCY_MISMATCH", P.usage_view, [
            make_usage("usage-1"),
            make_usage("usage-2", supersedes_usage_id="usage-1",
                       reported_cost={"amount": "0.70", "currency": "CNY"}),
        ])

    def test_A06_unresolved_supersedes(self):
        """4.3.8：修订链指向不存在的观测 → unresolved_supersedes 记录，并使视图不完整。
        P2 调和修正（规格澄清 C-11）：原测试两种写法都接受、只要求“某处有 False”。现固定为：
        unresolved_supersedes 列出**发起修订的观测** usage_id（据此可查到它指向的缺失目标）；
        该观测本身仍按口径计入，但五个计量、全部费用组与顶层 is_complete 都为 False。"""
        baseline = P.usage_view([make_usage("usage-1")])
        self.assertTrue(all(all_values_for(baseline, "is_complete")))
        self.assertIs(baseline["is_complete"], True)
        view = P.usage_view([make_usage("usage-2", supersedes_usage_id="usage-missing")])
        self.assertEqual(view["unresolved_supersedes"], ["usage-2"])
        for name in TOKEN_METRICS:
            with self.subTest(metric=name):
                self.assertIs(self.metric(view, name)["is_complete"], False)
        self.assertEqual(self.metric(view, "input_tokens")["known_total"], 100)
        for which in ("reported", "estimated"):
            for group in self.cost_bucket(view, which).values():
                self.assertIs(group["is_complete"], False)
        self.assertIs(view["is_complete"], False)

    def test_A06_empty_view_is_incomplete(self):
        """4.3.8“任何缺失证据都必须向聚合结果传播”：P2 调和新增（规格澄清 C-11）。
        没有任何可计入的观测不等于零用量：各计量 known_total=0 但 is_complete=False。"""
        view = P.usage_view([])
        for name in TOKEN_METRICS:
            with self.subTest(metric=name):
                self.assertEqual(self.metric(view, name),
                                 {"known_total": 0, "is_complete": False, "unknown_count": 0})
        # P4（第 2 轮复审 events-usage 视角）：费用层面同样标为不完整。原来两类费用都是 {}，只读费用分组的
        # 下游会把“没有观测”读成“费用为 0 且没有未知”；现在各有一个 unknown_currency 组（unknown_count=0）。
        for which in ("reported", "estimated"):
            with self.subTest(cost=which):
                self.assertEqual(self.cost_bucket(view, which),
                                 {"unknown_currency": {"known_total": "0", "is_complete": False,
                                                       "unknown_count": 0}})
        self.assertIs(view["is_complete"], False)
        self.assertIs(view["is_accounting"], False)
        # 有有效观测时不额外生成空的 unknown_currency 组。
        self.assertEqual(set(P.usage_view([make_usage()])["reported_cost"]), {"USD"})

    def test_A06_decimal_exact_sum(self):
        """4.3.7：金额不用二进制浮点累计；按十进制精确相加，输出不用科学计数。"""
        view = P.usage_view([
            make_usage("usage-1", reported_cost={"amount": "0.1", "currency": "USD"}),
            make_usage("usage-2", reported_cost={"amount": "0.2", "currency": "USD"}),
        ])
        self.assertDecimal(self.cost_bucket(view, "reported")["USD"]["known_total"], "0.3")
        view = P.usage_view([
            make_usage("usage-1", reported_cost={"amount": "0.0000001", "currency": "USD"}),
            make_usage("usage-2", reported_cost={"amount": "0.0000002", "currency": "USD"}),
        ])
        self.assertDecimal(self.cost_bucket(view, "reported")["USD"]["known_total"], "0.0000003")
        # P2 返工（复审变异 M91）：超过默认 28 位有效数字的金额也精确相加，不静默舍入。
        view = P.usage_view([
            make_usage("usage-1", reported_cost={"amount": "1234567890.123456789012345678901234567890",
                                                 "currency": "USD"}),
            make_usage("usage-2", reported_cost={"amount": "0.000000000000000000000000000001",
                                                 "currency": "USD"}),
        ])
        self.assertEqual(self.cost_bucket(view, "reported")["USD"]["known_total"],
                         "1234567890.123456789012345678901234567891")

    def test_A06_view_does_not_mutate_input(self):
        """4.3.8：视图计算不改写观测（不补零、不覆盖旧观测）。"""
        records = [make_usage("usage-1"), make_usage("usage-2", input_tokens=None)]
        before = copy.deepcopy(records)
        P.usage_view(records)
        self.assertUnchanged(before, records)

    def test_A06_null_provider_or_model_scope_is_ambiguous(self):
        """4.3.8 末行“两个来源范围不明的观测 → E_USAGE_SCOPE_UNKNOWN 或待核对”：P2 返工新增（复审
        fidelity 与 events-usage 视角，major）。provider/model 为 null 的范围来源不明：同一
        (request, run, role) 下还有其他含可计入观测的范围 → E_USAGE_SCOPE_UNKNOWN（不把两个范围相加成
        “完整”的 250）；单独存在时照常解释，但相关计量与费用组都不完整。"""
        known = make_usage("k1", observation_kind="cumulative", input_tokens=100)
        unknown_scope = make_usage("k2", provider=None, model=None, observation_kind="cumulative",
                                   input_tokens=150)
        cases = [[known, unknown_scope],
                 [make_usage("k1"), make_usage("k2", provider=None, model=None)],
                 [make_usage("k1", observation_kind="cumulative", input_tokens=150),
                  make_usage("k2", model=None, observation_kind="cumulative", input_tokens=150)],
                 # 同一 billing_event_id，一边丢了 provider：同样不能相加成 200 并标完整。
                 [make_usage("a1", billing_event_id="e1"),
                  make_usage("b1", provider=None, billing_event_id="e1")]]
        for observations in cases:
            with self.subTest(ids=[o["usage_id"] for o in observations]):
                exc = self.assertCode("E_USAGE_SCOPE_UNKNOWN", P.usage_view, observations)
                self.assertEqual(exc.reason, "scope_provider_or_model_unknown")
        alone = P.usage_view([make_usage("n1", provider=None, model=None, observation_kind="cumulative",
                                         input_tokens=100),
                              make_usage("n2", provider=None, model=None, observation_kind="cumulative",
                                         input_tokens=150)])
        metric = self.metric(alone, "input_tokens")
        self.assertEqual((metric["known_total"], metric["is_complete"]), (150, False))
        self.assertIs(self.cost_bucket(alone, "reported")["USD"]["is_complete"], False)
        self.assertIs(alone["scopes"][0]["ambiguous_scope"], True)
        self.assertIs(alone["is_complete"], False)
        deltas = P.usage_view([make_usage("d1", provider=None, model=None),
                               make_usage("d2", provider=None, model=None)])
        self.assertEqual(self.metric(deltas, "input_tokens")["known_total"], 200)
        self.assertIs(self.metric(deltas, "input_tokens")["is_complete"], False)
        # 来源不明但只有 unknown 观测的范围不参与歧义判断（它本来就不计入，只使结果不完整）。
        mixed = P.usage_view([make_usage("u1"), json.loads(SAMPLE_USAGE)])
        self.assertEqual(self.metric(mixed, "input_tokens")["known_total"], 100)
        self.assertIs(mixed["is_complete"], False)
        self.assertIs(P.usage_view([make_usage("u1")])["scopes"][0]["ambiguous_scope"], False)

    def test_A06_billing_duplicate_superseded_as_class(self):
        """4.3.8：P2 返工新增（复审 events-usage 视角，major）。同一外部账单事件以两个 usage_id 投递
        （Y、Z），修订 X 只指向其中一条且换了/没有 billing_event_id：修订替代整个账单事件等价类，
        不能让另一条失去去重对象后与 X 一起计入（修复前得 220 且标完整）。"""
        y = make_usage("u-y", billing_event_id="e1", reported_cost={"amount": "1.00", "currency": "USD"})
        z = make_usage("u-z", billing_event_id="e1", reported_cost={"amount": "1.00", "currency": "USD"})
        for x_billing in ("e2", None):
            for target in ("u-y", "u-z"):
                with self.subTest(x_billing=x_billing, supersedes=target):
                    x = make_usage("u-x", billing_event_id=x_billing, input_tokens=120,
                                   reported_cost={"amount": "1.00", "currency": "USD"},
                                   supersedes_usage_id=target)
                    view = P.usage_view([y, z, x])
                    metric = self.metric(view, "input_tokens")
                    self.assertEqual((metric["known_total"], metric["is_complete"]), (120, True))
                    self.assertDecimal(self.cost_bucket(view, "reported")["USD"]["known_total"], "1.00")
                    self.assertEqual(view["counted_usage_ids"], ["u-x"])
                    self.assertEqual(view["superseded"], ["u-y", "u-z"])
        # 综合场景：usage_id 重复投递 + 账单重复 + 修订换账单号 + CNY 累计范围 + unknown 观测。
        cny_1 = make_usage("c-1", model="synthetic-model-cny", observation_kind="cumulative",
                           input_tokens=100, reported_cost={"amount": "7.00", "currency": "CNY"},
                           estimated_cost=None)
        cny_2 = make_usage("c-2", model="synthetic-model-cny", observation_kind="cumulative",
                           input_tokens=160, reported_cost={"amount": "8.00", "currency": "CNY"},
                           estimated_cost=None)
        unknown = make_usage("u-unknown", observation_kind="unknown", input_tokens=999)
        x = make_usage("u-x", billing_event_id="e2", input_tokens=120,
                       reported_cost={"amount": "1.00", "currency": "USD"}, supersedes_usage_id="u-y")
        view = P.usage_view([y, copy.deepcopy(y), z, cny_1, x, cny_2, unknown])
        self.assertEqual(self.metric(view, "input_tokens")["known_total"], 280)
        reported = self.cost_bucket(view, "reported")
        self.assertDecimal(reported["USD"]["known_total"], "1.00")
        self.assertDecimal(reported["CNY"]["known_total"], "8.00")
        self.assertEqual(view["duplicates"], 1)
        self.assertIs(view["is_complete"], False)

    def assertUsageView(self, observations, input_total, *, superseded=None, duplicates=None,
                        counted=None, complete=True):
        view = P.usage_view(observations)
        metric = self.metric(view, "input_tokens")
        self.assertEqual((metric["known_total"], metric["is_complete"]), (input_total, complete))
        self.assertIs(view["is_complete"], complete)
        if superseded is not None:
            self.assertEqual(view["superseded"], superseded)
        if duplicates is not None:
            self.assertEqual(view["duplicates"], duplicates)
        if counted is not None:
            self.assertEqual(view["counted_usage_ids"], counted)
        return view

    def test_A06_same_billing_event_revision_chain_takes_tail(self):
        """4.3.8“final 明确修订前一观测 → 保留修订链”、01-T2“被替代的观测不计入”：P2 返工新增（复审
        fidelity 与 events-usage 视角，major）。厂商对同一账单事件多次更正时，各修订沿用原
        billing_event_id（或最后一版不带 billing_event_id）：2 级、3 级修订链取链尾，被替代的全部列入
        superseded，与到达顺序无关；不误报 observation_superseded_twice（修复前 3 级链报
        E_USAGE_CONFLICT，因为处理 r1 时把后到的 r2 也标成了“被 r1 替代”）。"""
        for kind in ("final", "delta"):
            r0 = make_usage("r0", observation_kind=kind, billing_event_id="bx", input_tokens=100)
            r1 = make_usage("r1", observation_kind=kind, billing_event_id="bx", input_tokens=120,
                            supersedes_usage_id="r0")
            with self.subTest(kind=kind, chain=2):
                self.assertUsageView([r0, r1], 120, superseded=["r0"], duplicates=0, counted=["r1"])
            for tail_billing in ("bx", None):
                r2 = make_usage("r2", observation_kind=kind, billing_event_id=tail_billing,
                                input_tokens=150, supersedes_usage_id="r1")
                for order in itertools.permutations([r0, r1, r2]):
                    with self.subTest(kind=kind, chain=3, tail_billing=tail_billing,
                                      order=[o["usage_id"] for o in order]):
                        self.assertUsageView(list(order), 150, superseded=["r0", "r1"], duplicates=0,
                                             counted=["r2"])
        # 更正回原值（100 → 120 → 100）不是“重复投递”，也不成环：取链尾。
        revert = [make_usage("v0", billing_event_id="bx", input_tokens=100),
                  make_usage("v1", billing_event_id="bx", input_tokens=120, supersedes_usage_id="v0"),
                  make_usage("v2", billing_event_id="bx", input_tokens=100, supersedes_usage_id="v1")]
        self.assertUsageView(revert, 100, superseded=["v0", "v1"], duplicates=0, counted=["v2"])
        # 长修订链（同一账单号）：取链尾，不因链长误报冲突。
        chain = [make_usage("n0", billing_event_id="bx", input_tokens=100)]
        for index in range(1, 500):
            chain.append(make_usage(f"n{index}", billing_event_id="bx", input_tokens=100 + index,
                                    supersedes_usage_id=f"n{index - 1}"))
        view = self.assertUsageView(chain, 599, duplicates=0, counted=["n499"])
        self.assertEqual(len(view["superseded"]), 499)

    def test_A06_billing_conflict_not_swallowed_by_revision(self):
        """01-T2“(provider, billing_event_id) 都非 null 且相同但 usage_id 不同：数值相同视为重复，不同 →
        E_USAGE_CONFLICT”、4.3.8“冲突进入核对/拒绝聚合”：P2 返工新增（复审 fidelity 与 events-usage
        视角，major）。修订只替代它明确指向的目标（连同目标的数值相同重复投递），不替代同一账单事件中
        数值不同、也不在这条修订链上的观测。这样的观测无论早于还是晚于修订到达、修订自身带同一账单号、
        另一账单号还是不带 → E_USAGE_CONFLICT（same_billing_event_different_values），不能被一并当作
        已替代吞掉（修复前得 120 且标完整）。"""
        a = make_usage("a", observation_kind="final", billing_event_id="bx", input_tokens=100)
        c = make_usage("c", observation_kind="final", billing_event_id="bx", input_tokens=999)
        for b_billing in ("bx", "by", None):
            b = make_usage("b", observation_kind="final", billing_event_id=b_billing, input_tokens=120,
                           supersedes_usage_id="a")
            for order in itertools.permutations([a, c, b]):
                with self.subTest(b_billing=b_billing, order=[o["usage_id"] for o in order]):
                    exc = self.assertCode("E_USAGE_CONFLICT", P.usage_view, list(order))
                    self.assertEqual(exc.reason, "same_billing_event_different_values")
        r0 = make_usage("r0", billing_event_id="B1", input_tokens=100)
        r1 = make_usage("r1", billing_event_id="B1", input_tokens=120, supersedes_usage_id="r0")
        r2 = make_usage("r2", billing_event_id="B1", input_tokens=150)
        for order in itertools.permutations([r0, r1, r2]):
            with self.subTest(delta_order=[o["usage_id"] for o in order]):
                exc = self.assertCode("E_USAGE_CONFLICT", P.usage_view, list(order))
                self.assertEqual(exc.reason, "same_billing_event_different_values")
        # 对照：另一条投递与修订后的有效值数值相同 → 视为同一账单事件的重复，只计一次。
        same_as_revision = make_usage("c", observation_kind="final", billing_event_id="bx",
                                      input_tokens=120)
        b = make_usage("b", observation_kind="final", billing_event_id="by", input_tokens=120,
                       supersedes_usage_id="a")
        self.assertUsageView([a, same_as_revision, b], 120, superseded=["a"], duplicates=1,
                             counted=["b"])

    def test_A06_duplicate_revision_delivery_counted_once(self):
        """4.3.8“同一账单事件数值相同视为重复”：P2 返工新增（复审 events-usage 视角，major）。同一修订以
        不同 usage_id 重复投递（billing_event_id 相同、数值相同、指向同一目标，或指向目标的重复投递）是
        一次修订的两次投递：只计一次（duplicates+1），不是分叉；重复投递的一方漏掉 supersedes 时同样按
        重复处理。没有 billing_event_id、或账单号不同的两条修订指向同一目标，无法认定为重复，仍是分叉 →
        E_USAGE_CONFLICT（observation_superseded_twice）。"""
        a = make_usage("a", billing_event_id="B1", input_tokens=100)
        c = make_usage("c", billing_event_id="B2", input_tokens=120, supersedes_usage_id="a")
        c2 = make_usage("c2", billing_event_id="B2", input_tokens=120, supersedes_usage_id="a")
        for order in itertools.permutations([a, c, c2]):
            with self.subTest(order=[o["usage_id"] for o in order]):
                self.assertUsageView(list(order), 120, superseded=["a"], duplicates=1)
        c2_without_link = make_usage("c2", billing_event_id="B2", input_tokens=120)
        self.assertUsageView([a, c, c2_without_link], 120, superseded=["a"], duplicates=1,
                             counted=["c"])
        # 整条修订重复投递：y/z 是同一账单事件的两次投递，x 修订 y，x2 是 x 的重复投递但指向 z。
        y = make_usage("y", billing_event_id="e1")
        z = make_usage("z", billing_event_id="e1")
        x = make_usage("x", billing_event_id="e2", input_tokens=120, supersedes_usage_id="y")
        x2 = make_usage("x2", billing_event_id="e2", input_tokens=120, supersedes_usage_id="z")
        self.assertUsageView([y, z, x, x2], 120, superseded=["y", "z"], duplicates=1, counted=["x"])
        forks = {
            "different_billing": [a, c, make_usage("c3", billing_event_id="B3", input_tokens=120,
                                                   supersedes_usage_id="a")],
            "no_billing": [a, make_usage("d1", input_tokens=120, supersedes_usage_id="a"),
                           make_usage("d2", input_tokens=120, supersedes_usage_id="a")],
        }
        for name, observations in forks.items():
            with self.subTest(fork=name):
                exc = self.assertCode("E_USAGE_CONFLICT", P.usage_view, observations)
                self.assertEqual(exc.reason, "observation_superseded_twice")

    def test_A06_revision_conflicts(self):
        """4.3.8、protocols-api.md 13.2：P2 返工新增（复审变异 M39/M40/M41，major）。修订改变 run 或 role、
        同一观测被替代两次（分叉）→ E_USAGE_CONFLICT；不能跨 run 抹掉用量、重复计入或让两条观测静默消失。
        修订成环见 test_A06_revision_cycle_detected_within_timeout（P4 移到带超时的子进程中）。"""
        cases = {
            "cross_run": [make_usage("usage-1"),
                          make_usage("usage-2", run_id=OTHER_RUN, supersedes_usage_id="usage-1")],
            "cross_role": [make_usage("usage-1"),
                           make_usage("usage-2", role="executor", supersedes_usage_id="usage-1")],
            "fork": [make_usage("usage-1"), make_usage("usage-2", supersedes_usage_id="usage-1"),
                     make_usage("usage-3", supersedes_usage_id="usage-1")],
        }
        for name, observations in cases.items():
            with self.subTest(case=name):
                self.assertCode("E_USAGE_CONFLICT", P.usage_view, observations)

    CYCLE_CHILD = r'''
import json, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
from codekit import protocols as P
try:
    P.usage_view(json.loads(sys.stdin.read()))
    print(json.dumps({"code": None, "reason": None}))
except P.ProtocolError as exc:
    print(json.dumps({"code": exc.code, "reason": exc.reason}))
'''

    def test_A06_revision_cycle_detected_within_timeout(self):
        """4.3.8、protocols-api.md 13.2：修订链成环 → E_USAGE_CONFLICT（reason=revision_cycle）。
        P4（第 2 轮复审 tests-mutation P202）：去掉成环检查后求修订深度的循环不终止，测试会一直挂起而不是失败；
        成环用例改在子进程中运行并设 60 秒超时，超时即判为失败（与 A14 的子进程做法相同，只传最小环境）。"""
        cases = {"two": [make_usage("usage-1", supersedes_usage_id="usage-2"),
                         make_usage("usage-2", supersedes_usage_id="usage-1")],
                 "three_cycle": [make_usage("usage-1", supersedes_usage_id="usage-3"),
                                 make_usage("usage-2", supersedes_usage_id="usage-1"),
                                 make_usage("usage-3", supersedes_usage_id="usage-2")],
                 "tail_into_cycle": [make_usage("usage-0"),
                                     make_usage("usage-1", supersedes_usage_id="usage-2"),
                                     make_usage("usage-2", supersedes_usage_id="usage-1"),
                                     make_usage("usage-9", supersedes_usage_id="usage-1")]}
        for name, observations in cases.items():
            with self.subTest(case=name):
                with tempfile.TemporaryDirectory(prefix="codekit-cycle-") as td:
                    try:
                        proc = subprocess.run(
                            [sys.executable, "-B", "-I", "-c", self.CYCLE_CHILD, str(SCRIPTS_DIR)],
                            input=json.dumps(observations).encode("utf-8"), cwd=td,
                            env=minimal_child_env(), capture_output=True, timeout=60)
                    except subprocess.TimeoutExpired:
                        self.fail("usage_view 对成环修订链 60 秒内没有返回（成环检查失效会导致不终止）")
                self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[-2000:])
                self.assertEqual(json.loads(proc.stdout.decode("utf-8")),
                                 {"code": "E_USAGE_CONFLICT", "reason": "revision_cycle"})

    def test_F047_revision_chain_currency_through_null(self):
        """01-F047 / 4.3.8：P2 返工新增（复审 events-usage 视角）。币种一致性按整条修订链检查：经过一个
        reported_cost 为 null 的中间版本把 USD 换成 CNY，同样 → E_USAGE_CURRENCY_MISMATCH。"""
        self.assertCode("E_USAGE_CURRENCY_MISMATCH", P.usage_view, [
            make_usage("usage-a"),
            make_usage("usage-b", reported_cost=None, supersedes_usage_id="usage-a"),
            make_usage("usage-c", reported_cost={"amount": "7.00", "currency": "CNY"},
                       supersedes_usage_id="usage-b"),
        ])

    def test_F045_revision_keeps_logical_position(self):
        """01-F045 / 4.3.8：P2 返工新增（复审 events-usage 视角）。修订继承被替代观测的逻辑位置：对较早
        累计值的更正晚到时，不能覆盖更新的累计值（c1=100、c2=150、c3 更正 c1 为 120 → 当前累计 150）。"""
        view = P.usage_view([
            make_usage("c1", observation_kind="cumulative", input_tokens=100),
            make_usage("c2", observation_kind="cumulative", input_tokens=150),
            make_usage("c3", observation_kind="cumulative", input_tokens=120, supersedes_usage_id="c1"),
        ])
        self.assertEqual(self.metric(view, "input_tokens")["known_total"], 150)
        self.assertEqual(view["counted_usage_ids"], ["c2"])
        self.assertEqual(view["scopes"][0]["ignored_usage_ids"], ["c3"])

    def test_F045_cumulative_and_final_consistency(self):
        """01-F045 / 4.3.4、4.3.8：P2 返工新增（复审 fidelity、events-usage 与变异 M59）。同范围
        cumulative/final 序列必须自洽：累计值回退、final 之后又出现 cumulative（终止后的新内容）
        → E_USAGE_CONFLICT；无修订链的累计序列换币种 → E_USAGE_CURRENCY_MISMATCH。
        自洽时取最后的 cumulative 或 final，没计入的观测列在 ignored_usage_ids 中，不静默丢弃。"""
        cum = "cumulative"
        conflicts = [
            [make_usage("c1", observation_kind=cum, input_tokens=150),
             make_usage("c2", observation_kind=cum, input_tokens=100)],
            [make_usage("f1", observation_kind="final", input_tokens=100),
             make_usage("c2", observation_kind=cum, input_tokens=150)],
            [make_usage("f1", observation_kind="final", input_tokens=100),
             make_usage("c2", observation_kind=cum, input_tokens=200)],
            [make_usage("c1", observation_kind=cum, input_tokens=150),
             make_usage("f2", observation_kind="final", input_tokens=120)],
        ]
        for observations in conflicts:
            with self.subTest(ids=[o["usage_id"] for o in observations]):
                self.assertCode("E_USAGE_CONFLICT", P.usage_view, observations)
        self.assertCode("E_USAGE_CURRENCY_MISMATCH", P.usage_view, [
            make_usage("c1", observation_kind=cum, reported_cost={"amount": "1.00", "currency": "USD"}),
            make_usage("c2", observation_kind=cum, reported_cost={"amount": "7.00", "currency": "CNY"}),
        ])
        view = P.usage_view([make_usage("c1", observation_kind=cum, input_tokens=100),
                             make_usage("f2", observation_kind="final", input_tokens=120)])
        self.assertEqual(self.metric(view, "input_tokens")["known_total"], 120)
        self.assertEqual(view["scopes"][0]["counted_usage_ids"], ["f2"])
        self.assertEqual(view["scopes"][0]["ignored_usage_ids"], ["c1"])
        view = P.usage_view([make_usage("c1", observation_kind=cum, input_tokens=100),
                             make_usage("c2", observation_kind=cum, input_tokens=150)])
        self.assertEqual(view["scopes"][0]["ignored_usage_ids"], ["c1"])

    def test_A06_estimate_cannot_pose_as_reported(self):
        """4.3.7“estimated_cost 不能冒充 reported”：P2 返工新增（复审 events-usage 视角，major）。
        billing_source 为 adapter_estimated/unavailable 时 reported_cost 必须为 null → 否则 E_USAGE_VALUE；
        同一账单事件的厂商报告与另一来源不是“重复” → E_USAGE_CONFLICT（与到达顺序无关）。"""
        for source in ("adapter_estimated", "unavailable"):
            with self.subTest(billing_source=source):
                self.assertCode("E_USAGE_VALUE", P.validate_usage_observation,
                                make_usage(billing_source=source), expect_field="/reported_cost")
                P.validate_usage_observation(make_usage(billing_source=source, reported_cost=None))
        P.validate_usage_observation(make_usage(billing_source="provider_invoice"))
        vendor = make_usage("s1", billing_event_id="e1")
        invoice = make_usage("s2", billing_event_id="e1", billing_source="provider_invoice")
        self.assertCode("E_USAGE_CONFLICT", P.usage_view, [vendor, invoice])
        self.assertCode("E_USAGE_CONFLICT", P.usage_view, [invoice, vendor])

    def test_A06_view_totals_stay_within_safe_integer(self):
        """4.1.1、01-D04：P2 返工新增（复审 events-usage 视角）。计量合计超过 2^53-1 → E_INTEGER_RANGE，
        视图本身不输出越界整数。"""
        self.assertCode("E_INTEGER_RANGE", P.usage_view,
                        [make_usage("usage-1", input_tokens=2**53 - 1),
                         make_usage("usage-2", input_tokens=2**53 - 1)])
        view = P.usage_view([make_usage("usage-1", input_tokens=2**53 - 2),
                             make_usage("usage-2", input_tokens=1)])
        self.assertEqual(self.metric(view, "input_tokens")["known_total"], 2**53 - 1)
        P.check_json_value(view)


# ===========================================================================
# 来源与表示（4.3.3、5.3、C.1；01-F043，01-A12）
# ===========================================================================
class ProvenanceTests(ProtocolTestCase):
    def captured(self, origin=None, redaction=None, **overrides):
        """captured 正例；origin/redaction 覆盖项与 captured 默认值合并，保证单一故障。
        收尾轮（裁决 R-P11）：captured 必须 traceable=true 且带 capture（采集环境引用与截取范围）。"""
        o = {"class": "captured", "source_revision": FULL_SHA1_OID, "source_test_id": None,
             "generator_revision": None, "description": "受控采集样本（测试构造）", "traceable": True}
        o.update(origin or {})
        r = {"applied": False, "rule_revision": None, "length_changed": None,
             "reason": "采集内容不含凭据", "protocol_structure_preserved": None}
        r.update(redaction or {})
        base = dict(origin=o, representation="captured_raw", redaction=r,
                    proves=["exact_byte_digest"], does_not_prove=[],
                    capture={"environment_ref": copy.deepcopy(CAPTURE_ENV_REF),
                             "range": "stdout 全部字节（测试构造）"})
        base.update(overrides)
        return make_manifest_entry(fixture_id="captured-sample-1", **base)

    def test_A12_synthetic_entry_accepted(self):
        """C.1、5.3：合成样本条目（synthetic + synthetic_fixture，声明不证明真实兼容）通过。"""
        entry = make_manifest_entry()
        before = copy.deepcopy(entry)
        P.validate_fixture_manifest_entry(entry, self.reg)
        self.assertUnchanged(before, entry)

    def test_F043_synthetic_cannot_claim_captured(self):
        """01-F043 / 4.3.3、8.1：合成样本不能标成采集表示，也不能声称真实兼容 → E_PROVENANCE_CLAIM。"""
        # 14.2 的检查顺序：脱敏元数据（第 2 步）先于来源类别（第 3 步），所以 redacted_raw 先因 applied=false 被拒绝。
        for representation, pointer, reason in (
                ("captured_raw", "/representation", "synthetic_requires_synthetic_fixture"),
                ("redacted_raw", "/redaction/applied", "redacted_raw_requires_applied_redaction"),
                ("normalized_event", "/representation", "synthetic_requires_synthetic_fixture")):
            with self.subTest(representation=representation):
                exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                                      make_manifest_entry(representation=representation), self.reg,
                                      expect_field=pointer)
                self.assertEqual(exc.reason, reason)
        # P4 第 3 轮（复审 tests-mutation X19/P12）：synthetic 的声明由合成样本专用规则拒绝，reason 固定为
        # synthetic_cannot_prove_real_compatibility（不是全体条目的声明循环给出的 reason）。
        for claim in ("real_cli_compatibility", "legacy_dispatch_behavior", "vendor_protocol"):
            with self.subTest(claim=claim):
                entry = make_manifest_entry(proves=["exact_byte_digest", claim],
                                            does_not_prove=[])
                exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, entry,
                                      self.reg, expect_field="/proves")
                self.assertEqual(exc.reason, "synthetic_cannot_prove_real_compatibility")

    def test_A12_captured_and_redacted_entries(self):
        """4.3.3：captured 只能配 captured_raw/redacted_raw，且须有 source_revision 或 source_test_id；
        redacted_raw 必须 applied=true 且有规则修订。"""
        P.validate_fixture_manifest_entry(self.captured(), self.reg)
        P.validate_fixture_manifest_entry(
            self.captured(origin={"source_revision": None,
                                  "source_test_id": "tests/test_dispatch.py::test_happy"}),
            self.reg)
        redacted = self.captured(representation="redacted_raw",
                                 redaction={"applied": True, "rule_revision": "redact-rules-r1",
                                            "length_changed": True, "reason": "替换令牌"})
        P.validate_fixture_manifest_entry(redacted, self.reg)
        # P4 第 3 轮（复审 tests-mutation P13）：每个负例都断言 field 与 reason；只有 source_path 不算来源——
        # captured 必须有 source_revision 或 source_test_id（source_path 只说明位置，不说明采集来源）。
        negatives = (
            (self.captured(representation="synthetic_fixture"), "/representation",
             "captured_requires_captured_redacted_or_normalized"),
            (self.captured(origin={"source_revision": None, "source_test_id": None}),
             "/origin/source_revision", "captured_requires_source"),
            (self.captured(origin={"source_revision": None, "source_test_id": None,
                                   "source_path": "captures/x.jsonl"}),
             "/origin/source_revision", "captured_requires_source"),
            (self.captured(representation="redacted_raw",
                           redaction={"applied": False, "rule_revision": "r1", "length_changed": True,
                                      "reason": "x"}),
             "/redaction/applied", "redacted_raw_requires_applied_redaction"),
            (self.captured(representation="redacted_raw",
                           redaction={"applied": True, "rule_revision": None, "length_changed": True,
                                      "reason": "x"}),
             "/redaction/rule_revision", "redaction_requires_rule_revision"),
        )
        for entry, pointer, reason in negatives:
            with self.subTest(reason=reason, origin=entry["origin"]["source_path"]):
                exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, entry,
                                      self.reg, expect_field=pointer)
                self.assertEqual(exc.reason, reason)
        # 对照：source_path 与 source_test_id 同时给出时通过。
        P.validate_fixture_manifest_entry(
            self.captured(origin={"source_revision": None, "source_test_id": "capture-session-1",
                                  "source_path": "captures/x.jsonl"}), self.reg)

    def test_A12_legacy_and_negative_entries(self):
        """5.3、7.4：legacy 需要完整 OID 的 source_revision 与 source_path 或 source_test_id；
        negative 需要 derived_from 与 fault。"""
        legacy = make_manifest_entry(
            fixture_id="legacy-contract-1",
            origin={"class": "legacy", "source_revision": FULL_SHA1_OID,
                    "source_path": "tests/test_dispatch.py", "generator_revision": None,
                    "description": "来自既有测试的旧字节"},
            representation="captured_raw", proves=["legacy_dispatch_behavior"], does_not_prove=[],
            expected={"outcome": "legacy-judgment", "code": None, "entry": "pi_dispatch"})
        P.validate_fixture_manifest_entry(legacy, self.reg)
        for origin in ({"source_revision": None}, {"source_path": None},):
            with self.subTest(origin=origin):
                bad = copy.deepcopy(legacy)
                bad["origin"].update(origin)
                self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, bad,
                                self.reg)
        short = copy.deepcopy(legacy)
        short["origin"]["source_revision"] = FULL_SHA1_OID[:7]
        # P2 调和修正（规格澄清 C-12）：原测试两码都接受。条目结构规定 source_revision 为
        # “完整 OID 或 null”，短 OID 是结构层的 OID 语法错误，对任何来源类别都先报 E_GIT_OID_SYNTAX；
        # E_PROVENANCE_CLAIM 只用于结构合法但来源/表示/声明不一致的情形（例如 legacy 缺 source_revision）。
        self.assertCode("E_GIT_OID_SYNTAX", P.validate_fixture_manifest_entry, short, self.reg,
                        expect_field="/origin/source_revision")
        for bad_oid in (FULL_SHA1_OID.upper(), FULL_SHA1_OID + "\n", "HEAD", "a" * 41):
            with self.subTest(source_revision=bad_oid):
                other = copy.deepcopy(legacy)
                other["origin"]["source_revision"] = bad_oid
                self.assertCode("E_GIT_OID_SYNTAX", P.validate_fixture_manifest_entry, other,
                                self.reg)

        negative = make_manifest_entry(
            fixture_id="negative-duplicate-key-1",
            origin={"class": "negative", "derived_from": "synthetic-protocol-sample-1",
                    "fault": "top-level-duplicate-key"},
            expected={"outcome": "reject", "code": "E_JSON_DUPLICATE_KEY"})
        P.validate_fixture_manifest_entry(negative, self.reg)
        for field in ("derived_from", "fault"):
            with self.subTest(missing=field):
                bad = copy.deepcopy(negative)
                bad["origin"][field] = None
                self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, bad,
                                self.reg)

    def test_A12_manifest_entry_structure(self):
        """01-T2 规格：条目字段封闭（E_SCHEMA_FIELDS）；资源为带 path 的 fixture 引用；枚举值受限。"""
        self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_entry,
                        make_manifest_entry(extra=1), self.reg)
        entry = make_manifest_entry()
        del entry["does_not_prove"]
        self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_entry, entry, self.reg)
        self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_entry,
                        make_manifest_entry(origin={"extra": 1}), self.reg)
        no_path = make_manifest_entry()
        del no_path["resource"]["path"]
        self.assertCode("E_RESOURCE_PATH_REQUIRED", P.validate_fixture_manifest_entry, no_path,
                        self.reg)
        # P2 调和（规格澄清 C-03、C-12）：原测试只断言“被拒绝”，现固定错误码与字段指针。
        for change, code, pointer in (
                ({"representation": "raw"}, "E_SCHEMA_FIELDS", "/representation"),
                ({"origin": {"class": "real"}}, "E_SCHEMA_FIELDS", "/origin/class"),
                ({"expected": {"outcome": "maybe"}}, "E_SCHEMA_FIELDS", "/expected/outcome"),
                ({"fixture_id": "Bad ID"}, "E_ID_SYNTAX", "/fixture_id"),
                ({"resource": {"kind": "public-schema"}}, "E_RESOURCE_KIND", "/resource/kind"),
                ({"expected": {"outcome": "reject", "code": None}}, "E_SCHEMA_FIELDS",
                 "/expected/code"),
                ({"expected": {"outcome": "accept", "code": "E_JSON_SYNTAX"}}, "E_SCHEMA_FIELDS",
                 "/expected/code"),
                # P2 返工（复审变异 Q025、Q027）：expected.expected_ref 按 ResourceRef 校验，
                # origin.source_path 按业务路径校验（路径安全：不能静默接受 ../ 与反斜杠）。
                ({"expected": {"expected_ref": {"kind": "fixture", "id": "BAD ID", "sha256": "x"}}},
                 "E_RESOURCE_FIELD", "/expected/expected_ref/id"),
                ({"expected": {"expected_ref": {"kind": "unregistered-kind", "id": "ref-1",
                                                "sha256": SYNTHETIC_SAMPLE_SHA256,
                                                "path": "tests/x.json"}}},
                 "E_RESOURCE_KIND", "/expected/expected_ref/kind"),
                ({"expected": {"expected_ref": "tests/x.json"}}, "E_SCHEMA_TYPE",
                 "/expected/expected_ref"),
                ({"origin": {"source_path": "../outside\\x.py"}}, "E_PATH_SYNTAX",
                 "/origin/source_path"),
                ({"origin": {"source_path": "../x"}}, "E_PATH_SYNTAX", "/origin/source_path"),
                ({"origin": {"source_path": "tests\\x.py"}}, "E_PATH_SYNTAX", "/origin/source_path")):
            with self.subTest(change=change):
                self.assertCode(code, P.validate_fixture_manifest_entry,
                                make_manifest_entry(**change), self.reg, expect_field=pointer)
        # 正例：合法的 expected_ref（kind=fixture 且带 path）被接受，条目不被修改。
        with_ref = make_manifest_entry(expected={"expected_ref": {
            "kind": "fixture", "id": "synthetic-protocol-sample-1-expected",
            "sha256": SYNTHETIC_SAMPLE_SHA256,
            "path": "tests/fixtures/codekit01/synthetic/synthetic-protocol-sample-1.expected.json"}})
        before = copy.deepcopy(with_ref)
        P.validate_fixture_manifest_entry(with_ref, self.reg)
        self.assertUnchanged(before, with_ref)
        # 同一声明既写在 proves 又写在 does_not_prove：来源声明自相矛盾 → E_PROVENANCE_CLAIM。
        self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                        make_manifest_entry(proves=["exact_byte_digest"],
                                            does_not_prove=["exact_byte_digest"]), self.reg)

    def test_A12_manifest_set(self):
        """5.3、C.1：Manifest 文件逐条校验；fixture_id 不重复；resource.path 不得碰撞；不含自身摘要。"""
        a = make_manifest_entry()
        b = make_manifest_entry(fixture_id="synthetic-protocol-sample-2",
                                resource={"id": "synthetic-protocol-sample-2",
                                          "path": "tests/fixtures/codekit01/synthetic/sample-2.json"})
        doc = {"schema_version": 1, "record_type": "fixture-manifest-set", "entries": [a, b]}
        P.validate_fixture_manifest_set(doc, self.reg)
        same_id = make_manifest_entry(
            resource={"id": "synthetic-protocol-sample-9",
                      "path": "tests/fixtures/codekit01/synthetic/sample-9.json"})
        # P2 调和（规格澄清 C-12）：重复 fixture_id 固定为 E_SCHEMA_FIELDS，field 指向后一条的 fixture_id。
        self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_set,
                        {**doc, "entries": [a, same_id]}, self.reg,
                        expect_field="/entries/1/fixture_id")
        colliding = make_manifest_entry(
            fixture_id="synthetic-protocol-sample-3",
            resource={"id": "synthetic-protocol-sample-3",
                      "path": a["resource"]["path"].replace("synthetic-protocol", "Synthetic-Protocol")})
        self.assertCode("E_PATH_COLLISION", P.validate_fixture_manifest_set,
                        {**doc, "entries": [a, colliding]}, self.reg)
        self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_set,
                        {**doc, "sha256": "0" * 64}, self.reg)
        self.assertCode("E_SCHEMA_RECORD_TYPE", P.validate_fixture_manifest_set,
                        {**doc, "record_type": "fixture-manifest"}, self.reg)
        # 规格澄清 C-12：同一拼写的路径指向不同摘要也是碰撞；negative 的 derived_from 必须在本清单内。
        same_path = make_manifest_entry(
            fixture_id="synthetic-protocol-sample-5",
            resource={"id": "synthetic-protocol-sample-5", "sha256": "0" * 64})
        self.assertCode("E_PATH_COLLISION", P.validate_fixture_manifest_set,
                        {**doc, "entries": [a, same_path]}, self.reg)
        orphan = make_manifest_entry(
            fixture_id="negative-orphan-1",
            origin={"class": "negative", "derived_from": "not-in-this-manifest",
                    "fault": "top-level-duplicate-key"},
            resource={"id": "negative-orphan-1",
                      "path": "tests/fixtures/codekit01/negative/orphan-1.json"},
            expected={"outcome": "reject", "code": "E_JSON_DUPLICATE_KEY"})
        P.validate_fixture_manifest_entry(orphan, self.reg)
        self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_set,
                        {**doc, "entries": [a, orphan]}, self.reg,
                        expect_field="/entries/1/origin/derived_from")
        bad_claim = make_manifest_entry(
            fixture_id="synthetic-protocol-sample-4", representation="captured_raw",
            resource={"id": "synthetic-protocol-sample-4",
                      "path": "tests/fixtures/codekit01/synthetic/sample-4.json"})
        self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_set,
                        {**doc, "entries": [a, bad_claim]}, self.reg)
        # P2 返工（复审 paths 视角）：目录前缀大小写碰撞同样阻断（Windows/macOS 上落进同一目录）。
        prefix = make_manifest_entry(
            fixture_id="synthetic-protocol-sample-6",
            resource={"id": "synthetic-protocol-sample-6",
                      "path": "tests/fixtures/codekit01/Synthetic/sample-6.json"})
        exc = self.assertCode("E_PATH_COLLISION", P.validate_fixture_manifest_set,
                              {**doc, "entries": [a, prefix]}, self.reg)
        self.assertEqual(exc.reason, "directory_prefix_collision")

    def test_A12_provenance_rule_details(self):
        """4.3.3、5.3：P2 返工新增（复审变异 M54b/M49/M48/M50）。合成样本声称前缀型真实能力
        （real_/vendor_/legacy_）、negative 自引用 → E_PROVENANCE_CLAIM；legacy 只有 source_test_id（没有
        source_path）是合法来源。
        P4（第 2 轮复审 fidelity 视角，4.3.3“标准化事件保留其来源”）：captured 可以配 normalized_event，但必须
        写明解释它的 generator_revision，否则 E_PROVENANCE_CLAIM（/origin/generator_revision）；captured 配
        synthetic_fixture 仍被拒绝（/representation）。"""
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                              self.captured(representation="normalized_event"), self.reg,
                              expect_field="/origin/generator_revision")
        self.assertEqual(exc.reason, "normalized_event_requires_generator_revision")
        P.validate_fixture_manifest_entry(
            self.captured(representation="normalized_event", origin={"generator_revision": "adapter-r1"}),
            self.reg)
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                              self.captured(representation="synthetic_fixture"), self.reg,
                              expect_field="/representation")
        self.assertEqual(exc.reason, "captured_requires_captured_redacted_or_normalized")
        for claim in ("real_pi_stream", "vendor_usage_totals", "legacy_exit_codes"):
            with self.subTest(claim=claim):
                exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                                      make_manifest_entry(proves=[claim], does_not_prove=[]), self.reg,
                                      expect_field="/proves")
                # P4 第 3 轮（复审 tests-mutation X19/P12）：synthetic 专用规则的 reason，不是声明循环的兜底 reason。
                self.assertEqual(exc.reason, "synthetic_cannot_prove_real_compatibility")
        legacy_by_test = make_manifest_entry(
            fixture_id="legacy-by-test-1",
            origin={"class": "legacy", "source_revision": FULL_SHA1_OID, "source_path": None,
                    "source_test_id": "tests/test_dispatch.py::test_x", "generator_revision": None,
                    "description": "来自既有测试"},
            representation="captured_raw", proves=["legacy_dispatch_behavior"], does_not_prove=[],
            expected={"outcome": "legacy-judgment", "code": None, "entry": "pi_dispatch"})
        P.validate_fixture_manifest_entry(legacy_by_test, self.reg)
        self_ref = make_manifest_entry(
            fixture_id="negative-self-1",
            origin={"class": "negative", "derived_from": "negative-self-1", "fault": "self-reference"},
            resource={"id": "negative-self-1", "path": "tests/fixtures/codekit01/negative/self-1.json"},
            expected={"outcome": "reject", "code": "E_JSON_SYNTAX"})
        self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, self_ref, self.reg,
                        expect_field="/origin/derived_from")
        doc = {"schema_version": 1, "record_type": "fixture-manifest-set",
               "entries": [make_manifest_entry(), self_ref]}
        self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_set, doc, self.reg,
                        expect_field="/entries/1/origin/derived_from")

    def _legacy_stub_like(self, **overrides):
        """legacy 类、synthetic_fixture 表示、legacy-judgment 的条目（形如 stub 生成的旧事件流）。"""
        entry = make_manifest_entry(
            fixture_id="legacy-stub-like-1",
            origin={"class": "legacy", "source_revision": FULL_SHA1_OID, "source_path": "tests/stub_pi.py",
                    "source_test_id": "tests/stub_pi.py STUB_SCENARIO=ok", "generator_revision": None,
                    "description": "stub 生成的流（测试构造）"},
            proves=["exact_byte_digest", "legacy_event_summary_judgment"],
            does_not_prove=["real_cli_compatibility", "vendor_protocol"],
            resource={"id": "legacy-stub-like-1", "path": "tests/fixtures/codekit01/legacy/stub-like-1.jsonl"},
            expected={"outcome": "legacy-judgment", "code": None, "entry": "summarize_events"})
        for key, value in overrides.items():
            if key in ("origin", "redaction", "resource", "expected") and isinstance(value, dict):
                entry[key] = {**entry[key], **value}
            else:
                entry[key] = value
        return entry

    def test_A12_real_compatibility_claims_by_origin_and_representation(self):
        """4.3.3“synthetic_fixture……无真实厂商来源声明”、01-A12：P4（fixtures 复审 major 的协议层根因）。能力
        声明的来源规则作用于**全部**条目，不再只看 origin.class=synthetic：
        - real_cli_compatibility、vendor_protocol 与 real_/vendor_ 前缀的声明只允许 origin.class=captured 且
          representation 为 captured_raw/redacted_raw；legacy 类的 stub 流、negative 类、captured 的
          normalized_event 声称它们 → E_PROVENANCE_CLAIM（/proves，reason=real_compatibility_claim_requires_captured_raw）；
        - legacy_dispatch_behavior 只允许 origin.class=legacy 且 expected.outcome=legacy-judgment
          （reason=legacy_dispatch_claim_requires_legacy_judgment）；
        - 其他 legacy_ 前缀只允许 legacy 或 negative（reason=legacy_claim_requires_legacy_or_negative_origin）；
        - synthetic 仍先按原规则报 synthetic_cannot_prove_real_compatibility。"""
        def claiming(entry, claim):
            changed = copy.deepcopy(entry)
            changed["proves"] = changed["proves"] + [claim]
            changed["does_not_prove"] = [c for c in changed["does_not_prove"] if c != claim]
            return changed

        stub = self._legacy_stub_like()
        negative = make_manifest_entry(
            fixture_id="negative-sample-1",
            origin={"class": "negative", "derived_from": "synthetic-protocol-sample-1", "fault": "x"},
            does_not_prove=[], expected={"outcome": "reject", "code": "E_JSON_SYNTAX"})
        normalized = self.captured(representation="normalized_event", origin={"generator_revision": "adapter-r1"})
        for base in (stub, negative, normalized):
            P.validate_fixture_manifest_entry(base, self.reg)
        real = ("real_cli_compatibility", "vendor_protocol", "real_pi_stream", "vendor_usage_totals")
        for base in (stub, negative, normalized):
            for claim in real:
                with self.subTest(fixture_id=base["fixture_id"], claim=claim):
                    exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                                          claiming(base, claim), self.reg, expect_field="/proves")
                    self.assertEqual(exc.reason, "real_compatibility_claim_requires_captured_raw")
        # 采集原件（captured_raw、redacted_raw）可以声明真实兼容。
        redacted = self.captured(representation="redacted_raw",
                                 redaction={"applied": True, "rule_revision": "redact-r1",
                                            "length_changed": False, "reason": "替换令牌"})
        for base in (self.captured(), redacted):
            for claim in real:
                with self.subTest(representation=base["representation"], claim=claim):
                    P.validate_fixture_manifest_entry(claiming(base, claim), self.reg)
        # P4 第 3 轮（复审 tests-mutation P06/X25）：origin.class=captured 这一条件本身要被固定——legacy 类的表示不受
        # 限制（C-12），legacy + captured_raw/redacted_raw 也不能声称真实或厂商兼容。
        legacy_raw = self._legacy_stub_like(representation="captured_raw")
        legacy_redacted = self._legacy_stub_like(
            representation="redacted_raw",
            redaction={"applied": True, "rule_revision": "redact-r1", "length_changed": True, "reason": "替换令牌"})
        for base in (legacy_raw, legacy_redacted):
            P.validate_fixture_manifest_entry(base, self.reg)
            for claim in real + ("real_x", "vendor_x"):
                with self.subTest(legacy_representation=base["representation"], claim=claim):
                    exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                                          claiming(base, claim), self.reg, expect_field="/proves")
                    self.assertEqual(exc.reason, "real_compatibility_claim_requires_captured_raw")
        # 合成样本：原规则先生效。
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                              make_manifest_entry(proves=["real_cli_compatibility"], does_not_prove=[]),
                              self.reg, expect_field="/proves")
        self.assertEqual(exc.reason, "synthetic_cannot_prove_real_compatibility")
        # legacy_dispatch_behavior：只有 legacy + legacy-judgment。
        P.validate_fixture_manifest_entry(claiming(stub, "legacy_dispatch_behavior"), self.reg)
        not_judgment = claiming(self._legacy_stub_like(expected={"outcome": "accept"}), "legacy_dispatch_behavior")
        for entry in (not_judgment, claiming(negative, "legacy_dispatch_behavior"),
                      claiming(self.captured(), "legacy_dispatch_behavior")):
            with self.subTest(fixture_id=entry["fixture_id"], outcome=entry["expected"]["outcome"]):
                exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, entry, self.reg,
                                      expect_field="/proves")
                self.assertEqual(exc.reason, "legacy_dispatch_claim_requires_legacy_judgment")
        # 其他 legacy_ 前缀：legacy 与 negative 可以（负例的来源另由清单级规则核对），captured 不可以。
        P.validate_fixture_manifest_entry(claiming(stub, "legacy_contract_judgment"), self.reg)
        P.validate_fixture_manifest_entry(claiming(negative, "legacy_contract_judgment"), self.reg)
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                              claiming(self.captured(), "legacy_contract_judgment"), self.reg,
                              expect_field="/proves")
        self.assertEqual(exc.reason, "legacy_claim_requires_legacy_or_negative_origin")

    def test_A12_negative_legacy_claims_require_legacy_base(self):
        """01-A12、5.3：P4（fixtures 复审 major 的清单层部分）。声明 legacy_ 前缀能力的负例必须从 legacy 条目
        派生：从合成样本派生的负例不能声称旧实现的判断 → validate_fixture_manifest_set 报 E_PROVENANCE_CLAIM
        （field=/entries/<i>/proves，reason=negative_legacy_claim_requires_legacy_base）。"""
        stub = self._legacy_stub_like()
        synthetic = make_manifest_entry()

        def negative(derived_from, fixture_id):
            return make_manifest_entry(
                fixture_id=fixture_id,
                origin={"class": "negative", "derived_from": derived_from, "fault": "x"},
                proves=["exact_byte_digest", "legacy_event_summary_judgment"], does_not_prove=[],
                resource={"id": fixture_id, "path": "tests/fixtures/codekit01/negative/%s.json" % fixture_id},
                expected={"outcome": "legacy-judgment", "code": None})

        ok = {"schema_version": 1, "record_type": "fixture-manifest-set",
              "entries": [stub, synthetic, negative("legacy-stub-like-1", "negative-from-legacy-1")]}
        P.validate_fixture_manifest_set(ok, self.reg)
        bad = {**ok, "entries": [stub, synthetic, negative("synthetic-protocol-sample-1", "negative-from-synth-1")]}
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_set, bad, self.reg,
                              expect_field="/entries/2/proves")
        self.assertEqual(exc.reason, "negative_legacy_claim_requires_legacy_base")
        # P4 第 3 轮（复审 tests-mutation P10）：legacy → negative → negative 的链式派生（后者声称 legacy_ 能力）。
        # 负例不能从另一个负例派生（7.4），先由派生规则拒绝，field 指向 derived_from。
        chained = {**ok, "entries": [stub, synthetic, negative("legacy-stub-like-1", "negative-from-legacy-1"),
                                     negative("negative-from-legacy-1", "negative-from-negative-1")]}
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_set, chained, self.reg,
                              expect_field="/entries/3/origin/derived_from")
        self.assertEqual(exc.reason, "negative_must_derive_from_valid_sample")

    def test_A12_negative_cannot_derive_from_negative(self):
        """7.4“每个负例从一份通过该层全部前置校验的有效样本复制”、14.3：P4 第 3 轮新增（复审 tests-mutation 视角）。
        产品入口原来只拒绝负例自引用；从另一个负例派生（链式）与负例之间的二元派生环都能绕过。现在清单级规则要求
        negative 的 derived_from 目标不是 negative → E_PROVENANCE_CLAIM（/entries/<i>/origin/derived_from，
        reason=negative_must_derive_from_valid_sample）。从 synthetic 或 legacy 条目派生照常接受。"""
        def negative(fixture_id, derived_from):
            return make_manifest_entry(
                fixture_id=fixture_id,
                origin={"class": "negative", "derived_from": derived_from, "fault": "f"},
                resource={"id": fixture_id, "path": "tests/fixtures/codekit01/negative/%s.json" % fixture_id},
                does_not_prove=[], expected={"outcome": "reject", "code": "E_JSON_SYNTAX"})

        synthetic = make_manifest_entry()
        doc = {"schema_version": 1, "record_type": "fixture-manifest-set"}
        P.validate_fixture_manifest_set({**doc, "entries": [synthetic, negative("neg-a", synthetic["fixture_id"])]},
                                        self.reg)
        cases = (
            ([negative("neg-a", "neg-b"), negative("neg-b", "neg-a")], "/entries/0/origin/derived_from"),
            ([synthetic, negative("neg-a", synthetic["fixture_id"]), negative("neg-b", "neg-a")],
             "/entries/2/origin/derived_from"),
            ([synthetic, negative("neg-b", "neg-a"), negative("neg-a", synthetic["fixture_id"])],
             "/entries/1/origin/derived_from"),
        )
        for entries, pointer in cases:
            with self.subTest(ids=[e["fixture_id"] for e in entries]):
                for entry in entries:
                    P.validate_fixture_manifest_entry(entry, self.reg)  # 单条目看不到派生目标
                exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_set,
                                      {**doc, "entries": entries}, self.reg, expect_field=pointer)
                self.assertEqual(exc.reason, "negative_must_derive_from_valid_sample")

    def test_A12_claim_lexicon(self):
        """4.3.3、14.2：P4 第 3 轮新增（复审 tests-mutation 视角，major）。能力声明是封闭词法
        [a-z][a-z0-9_]{0,127}：大小写变体（REAL_CLI_COMPATIBILITY、Vendor_Protocol、Legacy_dispatch_behavior）与
        连字符变体（vendor-protocol）原来能绕过按精确名称与前缀判定的来源规则，现在在结构层 → E_SCHEMA_FIELDS
        （/proves/<i> 或 /does_not_prove/<i>，reason=claim_syntax），对 stub（legacy）、negative、synthetic、captured
        条目都一样。长度 128 可以，129 拒绝。"""
        stub = self._legacy_stub_like()
        negative = make_manifest_entry(
            fixture_id="negative-sample-1",
            origin={"class": "negative", "derived_from": "synthetic-protocol-sample-1", "fault": "x"},
            does_not_prove=[], expected={"outcome": "reject", "code": "E_JSON_SYNTAX"})
        bases = (stub, negative, make_manifest_entry(does_not_prove=[]), self.captured())
        variants = ("REAL_CLI_COMPATIBILITY", "Vendor_Protocol", "vendor-protocol", "Legacy_dispatch_behavior",
                    "real-cli-compatibility", "1st_claim", "_real", "real cli", "réal_x", "a" * 129)
        for base in bases:
            P.validate_fixture_manifest_entry(base, self.reg)
            for claim in variants:
                with self.subTest(fixture_id=base["fixture_id"], claim=claim[:20]):
                    changed = copy.deepcopy(base)
                    changed["proves"] = changed["proves"] + [claim]
                    index = len(changed["proves"]) - 1
                    exc = self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_entry, changed, self.reg,
                                          expect_field="/proves/%d" % index)
                    self.assertIn(exc.reason, ("claim_syntax", "string_length_out_of_range"))
                    if len(claim) <= 128:
                        self.assertEqual(exc.reason, "claim_syntax")
                    listed = copy.deepcopy(base)
                    listed["does_not_prove"] = listed["does_not_prove"] + [claim]
                    self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_entry, listed, self.reg,
                                    expect_field="/does_not_prove/%d" % (len(listed["does_not_prove"]) - 1))
        longest = make_manifest_entry(proves=["exact_byte_digest", "a" * 128])
        P.validate_fixture_manifest_entry(longest, self.reg)
        doc = {"schema_version": 1, "record_type": "fixture-manifest-set",
               "entries": [{**stub, "proves": stub["proves"] + ["REAL_CLI_COMPATIBILITY"]}]}
        self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_set, doc, self.reg,
                        expect_field="/entries/0/proves/2")

    def test_A12_redaction_metadata_and_representation_rules(self):
        """4.3.3“避免‘原始’一词掩盖内容已变换”“脱敏元数据至少记录……是否改变字节长度”：P4 新增（第 2 轮复审
        fidelity 视角）。redaction.applied=true 时 length_changed 必须非空；captured_raw 不能是脱敏过的字节；
        negative（注入故障后的字节）不能标为 captured_raw/redacted_raw。都报 E_PROVENANCE_CLAIM。"""
        redacted = {"applied": True, "rule_revision": "redact-r1", "length_changed": None, "reason": "替换令牌",
                    "protocol_structure_preserved": True}
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                              self.captured(representation="redacted_raw", redaction=redacted), self.reg,
                              expect_field="/redaction/length_changed")
        self.assertEqual(exc.reason, "redaction_requires_length_changed")
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                              self.captured(redaction={**redacted, "length_changed": True}), self.reg,
                              expect_field="/redaction/applied")
        self.assertEqual(exc.reason, "captured_raw_must_not_be_redacted")
        for representation, redaction in (("captured_raw", None), ("redacted_raw", {**redacted,
                                                                                    "length_changed": False})):
            entry = make_manifest_entry(
                fixture_id="negative-sample-2",
                origin={"class": "negative", "derived_from": "synthetic-protocol-sample-1", "fault": "x"},
                representation=representation, does_not_prove=[],
                expected={"outcome": "reject", "code": "E_JSON_SYNTAX"})
            if redaction is not None:
                entry["redaction"] = redaction
            with self.subTest(representation=representation):
                exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, entry, self.reg,
                                      expect_field="/representation")
                self.assertEqual(exc.reason, "negative_cannot_use_captured_representation")
        # stub 流的形态：synthetic_fixture + applied=true + length_changed 已写明，照常接受。
        P.validate_fixture_manifest_entry(
            self._legacy_stub_like(redaction={"applied": True, "rule_revision": "stub-cwd-r1",
                                              "length_changed": True, "reason": "cwd 占位"}), self.reg)

    def test_A12_appendix_c1_example_needs_completion(self):
        """附录 C.1、protocols-api.md 14.1：P2 返工新增（复审 fidelity 视角）。C.1 只是建议稿，缺 expected、
        origin.source_path/derived_from/fault、redaction.rule_revision/length_changed，按 01-T2 的封闭结构
        会被拒绝（E_SCHEMA_FIELDS /expected）；按接口说明补齐这些字段后通过。
        收尾轮（裁决 R-P11）：还要补齐 integrity、platform_scope、capture、origin.traceable 与
        redaction.protocol_structure_preserved；新字段排在 expected 之后，C.1 示例仍先报 /expected。补齐后逐项
        去掉一个新字段，都报 E_SCHEMA_FIELDS（missing_field），field 指向该字段。"""
        docs = sorted(DOC_DIR.glob("01-baseline-and-protocols-*.md"))
        if not docs:
            self.skipTest("未找到 01 设计文档，无法取出附录 C.1 示例")
        text = docs[0].read_bytes().decode("utf-8").replace("\r\n", "\n")
        section = text[text.index("### C.1"):]
        example = json.loads(re.search(r"```json\n(.*?)```", section, re.S).group(1))
        self.assertEqual(example["record_type"], "fixture-manifest")
        self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_entry, example, self.reg,
                        expect_field="/expected")
        completed = copy.deepcopy(example)
        completed["origin"].update({"source_path": None, "derived_from": None, "fault": None, "traceable": True})
        completed["redaction"].update({"rule_revision": None, "length_changed": None,
                                       "protocol_structure_preserved": None})
        completed["expected"] = {"outcome": "accept", "code": None, "entry": "strict_json_loads",
                                 "expected_ref": None}
        completed.update({"integrity": "complete", "platform_scope": ["any"], "capture": None})
        P.validate_fixture_manifest_entry(completed, self.reg)
        for path in (("integrity",), ("platform_scope",), ("capture",), ("origin", "traceable"),
                     ("redaction", "protocol_structure_preserved")):
            with self.subTest(missing="/".join(path)):
                partial = copy.deepcopy(completed)
                holder = partial if len(path) == 1 else partial[path[0]]
                del holder[path[-1]]
                exc = self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_entry, partial, self.reg,
                                      expect_field="/" + "/".join(path))
                self.assertEqual(exc.reason, "missing_field")

    # -- 收尾轮：裁决 R-P11（文档 1.1 平台适用性、4.3.3、6.6“封存”、附录 C.1；acceptance.md M-03） --

    def test_A12_r_p11_new_fields_structure(self):
        """裁决 R-P11 的结构层（字段仍封闭）：integrity 取 complete/partial/truncated/corrupted；platform_scope 为
        ["any"] 或 PLATFORMS 的非空无重复子集（不是数组 E_SCHEMA_TYPE；空数组、"any" 与平台并列、重复、未知平台都是
        E_SCHEMA_FIELDS）；capture 为 null 或封闭对象 {environment_ref: ResourceRef, range: 1–512 字符}；
        origin.traceable 为布尔；redaction.protocol_structure_preserved 为布尔或 null。"""
        for value in P.FIXTURE_INTEGRITY_VALUES:
            with self.subTest(integrity=value):
                P.validate_fixture_manifest_entry(make_manifest_entry(integrity=value), self.reg)
        self.assertEqual(P.FIXTURE_INTEGRITY_VALUES, ("complete", "partial", "truncated", "corrupted"))
        for value in ("full", "COMPLETE", None, 1, ["complete"]):
            with self.subTest(integrity=value):
                exc = self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_entry,
                                      make_manifest_entry(integrity=value), self.reg, expect_field="/integrity")
                self.assertEqual(exc.reason, "value_not_in_enum")
        for scope in (["any"], ["windows"], ["linux", "macos", "windows"], ["macos", "linux"]):
            with self.subTest(platform_scope=scope):
                P.validate_fixture_manifest_entry(make_manifest_entry(platform_scope=scope), self.reg)
        bad_scopes = [
            ("any", "E_SCHEMA_TYPE", "/platform_scope", "array_required"),
            (None, "E_SCHEMA_TYPE", "/platform_scope", "array_required"),
            ([], "E_SCHEMA_FIELDS", "/platform_scope", "platform_scope_empty"),
            (["any", "windows"], "E_SCHEMA_FIELDS", "/platform_scope/0", "platform_scope_any_must_be_alone"),
            (["windows", "any"], "E_SCHEMA_FIELDS", "/platform_scope/1", "platform_scope_any_must_be_alone"),
            (["any", "any"], "E_SCHEMA_FIELDS", "/platform_scope/0", "platform_scope_any_must_be_alone"),
            (["windows", "windows"], "E_SCHEMA_FIELDS", "/platform_scope/1", "duplicate_platform"),
            (["Windows"], "E_SCHEMA_FIELDS", "/platform_scope/0", "value_not_in_enum"),
            (["linux", "darwin"], "E_SCHEMA_FIELDS", "/platform_scope/1", "value_not_in_enum"),
            ([1], "E_SCHEMA_FIELDS", "/platform_scope/0", "value_not_in_enum"),
            (["ANY"], "E_SCHEMA_FIELDS", "/platform_scope/0", "value_not_in_enum"),
        ]
        for scope, code, pointer, reason in bad_scopes:
            with self.subTest(platform_scope=scope):
                exc = self.assertCode(code, P.validate_fixture_manifest_entry,
                                      make_manifest_entry(platform_scope=scope), self.reg, expect_field=pointer)
                self.assertEqual(exc.reason, reason)
        env = copy.deepcopy(CAPTURE_ENV_REF)
        bad_captures = [
            ("x", "E_SCHEMA_TYPE", "/capture"),
            ({"environment_ref": env}, "E_SCHEMA_FIELDS", "/capture/range"),
            ({"range": "r"}, "E_SCHEMA_FIELDS", "/capture/environment_ref"),
            ({"environment_ref": env, "range": "r", "host": "x"}, "E_SCHEMA_FIELDS", "/capture/host"),
            ({"environment_ref": {**env, "kind": "unregistered-kind"}, "range": "r"}, "E_RESOURCE_KIND",
             "/capture/environment_ref/kind"),
            ({"environment_ref": {k: v for k, v in env.items() if k != "path"}, "range": "r"},
             "E_RESOURCE_PATH_REQUIRED", "/capture/environment_ref/path"),
            ({"environment_ref": {**env, "path": "../env.json"}, "range": "r"}, "E_PATH_SYNTAX",
             "/capture/environment_ref/path"),
            ({"environment_ref": None, "range": "r"}, "E_SCHEMA_TYPE", "/capture/environment_ref"),
            ({"environment_ref": env, "range": ""}, "E_SCHEMA_FIELDS", "/capture/range"),
            ({"environment_ref": env, "range": "r" * 513}, "E_SCHEMA_FIELDS", "/capture/range"),
            ({"environment_ref": env, "range": None}, "E_SCHEMA_TYPE", "/capture/range"),
        ]
        for capture, code, pointer in bad_captures:
            with self.subTest(capture=repr(capture)[:50]):
                self.assertCode(code, P.validate_fixture_manifest_entry, self.captured(capture=capture), self.reg,
                                expect_field=pointer)
        P.validate_fixture_manifest_entry(self.captured(capture={"environment_ref": env, "range": "r" * 512}),
                                          self.reg)
        for value in (None, "true", 1):
            with self.subTest(traceable=value):
                self.assertCode("E_SCHEMA_TYPE", P.validate_fixture_manifest_entry,
                                make_manifest_entry(origin={"traceable": value}), self.reg,
                                expect_field="/origin/traceable")
        for value in ("yes", 0):
            with self.subTest(protocol_structure_preserved=value):
                self.assertCode("E_SCHEMA_TYPE", P.validate_fixture_manifest_entry,
                                make_manifest_entry(redaction={"protocol_structure_preserved": value}), self.reg,
                                expect_field="/redaction/protocol_structure_preserved")
        for value in (True, False, None):
            with self.subTest(protocol_structure_preserved=value):
                P.validate_fixture_manifest_entry(make_manifest_entry(redaction={"protocol_structure_preserved": value}),
                                                  self.reg)
        self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_entry,
                        make_manifest_entry(redaction={"structure_preserved": True}), self.reg,
                        expect_field="/redaction/structure_preserved")
        self.assertCode("E_SCHEMA_FIELDS", P.validate_fixture_manifest_entry,
                        make_manifest_entry(platform="windows"), self.reg, expect_field="/platform")

    def test_A12_r_p11_traceable_and_capture_rules(self):
        """裁决 R-P11：legacy 与 captured 的 origin.traceable 必须为 true（E_PROVENANCE_CLAIM，/origin/traceable，
        reason=traceable_required_for_legacy_or_captured）；synthetic 与 negative 可以为 false。captured 必须有 capture
        （/capture，reason=captured_requires_capture）；其他来源类别 capture 必须为 null（/capture，
        reason=capture_only_for_captured）。"""
        negative = make_manifest_entry(
            fixture_id="negative-sample-1",
            origin={"class": "negative", "derived_from": "synthetic-protocol-sample-1", "fault": "x"},
            does_not_prove=[], expected={"outcome": "reject", "code": "E_JSON_SYNTAX"})
        legacy = self._legacy_stub_like()
        captured = self.captured()
        for entry in (make_manifest_entry(), negative, legacy, captured):
            P.validate_fixture_manifest_entry(entry, self.reg)
        for entry in (legacy, captured):
            changed = copy.deepcopy(entry)
            changed["origin"]["traceable"] = False
            with self.subTest(untraceable=entry["origin"]["class"]):
                exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, changed, self.reg,
                                      expect_field="/origin/traceable")
                self.assertEqual(exc.reason, "traceable_required_for_legacy_or_captured")
        for entry in (make_manifest_entry(), negative):
            changed = copy.deepcopy(entry)
            changed["origin"]["traceable"] = False
            with self.subTest(untraceable_allowed=entry["origin"]["class"]):
                P.validate_fixture_manifest_entry(changed, self.reg)
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, self.captured(capture=None),
                              self.reg, expect_field="/capture")
        self.assertEqual(exc.reason, "captured_requires_capture")
        for representation, redaction in (("normalized_event", None), ("redacted_raw", {
                "applied": True, "rule_revision": "redact-r1", "length_changed": False, "reason": "替换令牌"})):
            with self.subTest(captured_representation=representation):
                origin = {"generator_revision": "adapter-r1"} if representation == "normalized_event" else None
                entry = self.captured(representation=representation, origin=origin, redaction=redaction)
                P.validate_fixture_manifest_entry(entry, self.reg)
                exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                                      {**entry, "capture": None}, self.reg, expect_field="/capture")
                self.assertEqual(exc.reason, "captured_requires_capture")
        capture = {"environment_ref": copy.deepcopy(CAPTURE_ENV_REF), "range": "stdout 全部字节"}
        for entry in (make_manifest_entry(), negative, legacy):
            with self.subTest(capture_on=entry["origin"]["class"]):
                exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                                      {**entry, "capture": capture}, self.reg, expect_field="/capture")
                self.assertEqual(exc.reason, "capture_only_for_captured")
        # 顺序：来源类别本身的规则（legacy 缺 source_revision）先于 traceable；traceable 先于 capture。
        both = copy.deepcopy(legacy)
        both["origin"].update({"source_revision": None, "traceable": False})
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, both, self.reg)
        self.assertEqual(exc.reason, "legacy_requires_source_revision")
        untraceable_no_capture = self.captured(origin={"traceable": False}, capture=None)
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, untraceable_no_capture,
                              self.reg)
        self.assertEqual(exc.reason, "traceable_required_for_legacy_or_captured")

    def test_A12_r_p11_integrity_limits_complete_stream_claims(self):
        """裁决 R-P11、文档 6.6“封存”：integrity 不是 complete 的条目，proves 不得含完整运行流一类的声明
        （E_PROVENANCE_CLAIM，/proves，reason=incomplete_fixture_cannot_prove_complete_stream），对各来源类别都一样；
        integrity=complete 时可以声明；写在 does_not_prove 中不受限制。收尾轮返工（复审 fidelity 视角 major）：判定按
        受控词表，不只看 complete_run_stream、full_run 两个前缀，complete_run、run_stream_complete、fullrun、
        complete_event_stream、full_event_log、entire_run_stream 等同义名称同样拒绝；词表之外的名称（partial_*、
        incomplete_*、truncation_*，以及只是含有 full 子串的 successfully_*）不受影响。"""
        self.assertEqual(P.COMPLETE_STREAM_CLAIM_PREFIXES, ("complete_run_stream", "full_run"))
        self.assertEqual(P.COMPLETENESS_CLAIM_STEMS, ("complet", "full", "entire", "whole", "intact", "untruncat",
                                                      "unabridg", "endtoend", "e2e"))
        self.assertEqual(P.COMPLETENESS_CLAIM_PHRASES, (("end", "to", "end"),))
        self.assertEqual(P.COMPLETENESS_CLAIM_QUANTIFIERS, ("all", "every"))
        self.assertEqual(P.STREAM_SUBJECT_STEMS, ("run", "stream", "event", "log", "record", "line", "message",
                                                  "transcript", "session", "output", "trace", "segment"))
        claims = ("complete_run_stream", "complete_run_stream_v2", "full_run", "full_run_events", "full_runtime",
                  # 收尾轮返工：同义名称（复审实测能绕过前缀规则的 6 个，另加各词干、词组与量词的代表）。
                  "complete_run", "run_stream_complete", "fullrun", "complete_event_stream", "full_event_log",
                  "entire_run_stream", "completed_run", "run_completeness", "stream_completion", "fully_replayed",
                  "whole_transcript", "intact_event_log", "untruncated_output", "unabridged_log", "endtoend_run",
                  "e2e_replay", "end_to_end_run", "all_events_present", "every_line_parsed", "all_run_records")
        bases = (make_manifest_entry(does_not_prove=[]), self._legacy_stub_like(does_not_prove=[]), self.captured())
        for base in bases:
            for claim in claims:
                with self.subTest(origin=base["origin"]["class"], claim=claim):
                    P.validate_fixture_manifest_entry({**base, "proves": base["proves"] + [claim]}, self.reg)
                    for integrity in ("partial", "truncated", "corrupted"):
                        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                                              {**base, "integrity": integrity, "proves": base["proves"] + [claim]},
                                              self.reg, expect_field="/proves")
                        self.assertEqual(exc.reason, "incomplete_fixture_cannot_prove_complete_stream")
                        P.validate_fixture_manifest_entry(
                            {**base, "integrity": integrity, "does_not_prove": base["does_not_prove"] + [claim]},
                            self.reg)
        # 词表之外：按词元开头匹配，不做子串匹配（incomplete、successfully 不算）；all/every 必须配运行流对象词干。
        for claim in ("partial_run_stream", "incomplete_stream_detected", "truncation_detected",
                      "successfully_parsed", "all_fields_typed", "end_marker_missing"):
            with self.subTest(outside_vocabulary=claim):
                P.validate_fixture_manifest_entry(
                    make_manifest_entry(integrity="truncated", proves=["exact_byte_digest", claim]), self.reg)
        # 顺序：来源规则（第 4 步）先于完整性规则。
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                              make_manifest_entry(integrity="partial", does_not_prove=[],
                                                  proves=["complete_run_stream", "real_cli_compatibility"]),
                              self.reg, expect_field="/proves")
        self.assertEqual(exc.reason, "synthetic_cannot_prove_real_compatibility")

    def test_A12_r_p11_structure_preservation_limits_field_semantics_claims(self):
        """裁决 R-P11、文档 4.3.3“无法保证语义字段未被脱敏破坏时，该 fixture 不能证明该字段的真实协议兼容性”：
        redaction.protocol_structure_preserved=false 的条目，proves 不得含以 protocol_field_semantics 开头的声明
        （reason=structure_not_preserved_cannot_prove_field_semantics）；脱敏过（applied=true）却没有记录（null）时同样
        不得声称（reason=structure_preservation_unrecorded_cannot_prove_field_semantics，收尾轮的保守补充，null 本身
        仍合法）。true，或没有脱敏且为 null 时可以声明。收尾轮返工（复审 fidelity 视角 major）：判定按受控词表，
        不只看 protocol_field_semantics 前缀：含以 semantic、meaning 开头的词元，或同时含以 protocol/wire 与 field
        开头的词元的声明（field_semantics、protocol_fields 等）同样拒绝。"""
        self.assertEqual(P.PROTOCOL_FIELD_SEMANTICS_CLAIM, "protocol_field_semantics")
        self.assertEqual(P.FIELD_SEMANTICS_CLAIM_STEMS, ("semantic", "meaning"))
        self.assertEqual(P.PROTOCOL_SUBJECT_STEMS, ("protocol", "wire"))
        self.assertEqual(P.FIELD_SUBJECT_STEMS, ("field",))
        applied = {"applied": True, "rule_revision": "redact-r1", "length_changed": False, "reason": "替换令牌"}
        not_applied = {"applied": False, "rule_revision": None, "length_changed": None, "reason": "未脱敏"}
        cases = [
            (not_applied, None, None),
            (not_applied, True, None),
            (not_applied, False, "structure_not_preserved_cannot_prove_field_semantics"),
            (applied, True, None),
            (applied, False, "structure_not_preserved_cannot_prove_field_semantics"),
            (applied, None, "structure_preservation_unrecorded_cannot_prove_field_semantics"),
        ]
        for claim in ("protocol_field_semantics", "protocol_field_semantics_usage", "field_semantics",
                      "protocol_fields"):
            for redaction, preserved, reason in cases:
                representation = "redacted_raw" if redaction["applied"] else "captured_raw"
                entry = self.captured(representation=representation,
                                      redaction={**redaction, "protocol_structure_preserved": preserved},
                                      proves=["exact_byte_digest", claim])
                with self.subTest(claim=claim, applied=redaction["applied"], preserved=preserved):
                    # 不声明时这些组合都合法。
                    P.validate_fixture_manifest_entry({**entry, "proves": ["exact_byte_digest"]}, self.reg)
                    if reason is None:
                        P.validate_fixture_manifest_entry(entry, self.reg)
                    else:
                        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, entry,
                                              self.reg, expect_field="/proves")
                        self.assertEqual(exc.reason, reason)
                        P.validate_fixture_manifest_entry({**entry, "proves": ["exact_byte_digest"],
                                                           "does_not_prove": [claim]}, self.reg)
        # legacy 的 stub 流（synthetic_fixture + applied=true）同样适用。
        stub = self._legacy_stub_like(redaction={"applied": True, "rule_revision": "stub-cwd-r1", "length_changed": True,
                                       "reason": "cwd 占位", "protocol_structure_preserved": False})
        P.validate_fixture_manifest_entry(stub, self.reg)
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                              {**stub, "proves": stub["proves"] + ["protocol_field_semantics"]}, self.reg,
                              expect_field="/proves")
        self.assertEqual(exc.reason, "structure_not_preserved_cannot_prove_field_semantics")
        # 收尾轮返工：同义名称同样拒绝（此前 field_semantics、protocol_fields 被当作无关名称接受）。
        for claim in ("field_semantics", "protocol_fields", "semantic_equivalence", "header_field_meaning",
                      "wire_field_types", "session_header_semantics", "protocol_header_field_order"):
            with self.subTest(synonym=claim):
                exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                                      {**stub, "proves": stub["proves"] + [claim]}, self.reg, expect_field="/proves")
                self.assertEqual(exc.reason, "structure_not_preserved_cannot_prove_field_semantics")
        # 词表之外：只有 field、只有 protocol、或词干不在词元开头的名称不受影响。
        for claim in ("field_order", "protocol_version_string", "nonsemantic_bytes_equal", "legacy_source_bytes",
                      "stub_output_at_source_revision"):
            with self.subTest(outside_vocabulary=claim):
                P.validate_fixture_manifest_entry({**stub, "proves": stub["proves"] + [claim]}, self.reg)

    def test_A12_r_p11_check_order_structure_then_steps(self):
        """protocols-api.md 14.2 的检查顺序（收尾轮返工，复审 tests-mutation 视角）：收尾轮新增字段的结构检查先于全部
        来源规则；第 4 步（能力声明的来源规则）先于第 5 步（完整性与协议结构）。用同时违反两处的条目固定：
        - synthetic 条目带结构非法的 capture：报结构错误，不报第 3b 步的 capture_only_for_captured；
        - synthetic 条目 platform_scope=[] 或 integrity 非法、同时带 capture：报结构错误；
        - negative 条目 integrity=truncated，同时声称 vendor_protocol 与 full_run：报第 4 步；
        - negative 条目协议结构为 false，同时声称 legacy_dispatch_behavior 与 protocol_field_semantics：报第 4 步。"""
        env = copy.deepcopy(CAPTURE_ENV_REF)
        good_capture = {"environment_ref": env, "range": "r"}
        # 单独一处时的结论（对照）：合法 capture 放在 synthetic 条目上报第 3b 步。
        exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry,
                              make_manifest_entry(capture=good_capture), self.reg, expect_field="/capture")
        self.assertEqual(exc.reason, "capture_only_for_captured")
        structural = [
            ({"capture": {"environment_ref": env, "range": ""}}, "E_SCHEMA_FIELDS", "/capture/range", None),
            ({"capture": "x"}, "E_SCHEMA_TYPE", "/capture", None),
            ({"capture": {"environment_ref": {**env, "kind": "unregistered-kind"}, "range": "r"}}, "E_RESOURCE_KIND",
             "/capture/environment_ref/kind", None),
            ({"capture": {"environment_ref": env, "range": "r", "host": "x"}}, "E_SCHEMA_FIELDS", "/capture/host",
             None),
            ({"platform_scope": [], "capture": good_capture}, "E_SCHEMA_FIELDS", "/platform_scope",
             "platform_scope_empty"),
            ({"platform_scope": ["windows", "windows"], "capture": good_capture}, "E_SCHEMA_FIELDS",
             "/platform_scope/1", "duplicate_platform"),
            ({"integrity": "full", "capture": good_capture}, "E_SCHEMA_FIELDS", "/integrity", "value_not_in_enum"),
            ({"origin": {"traceable": None}, "capture": good_capture}, "E_SCHEMA_TYPE", "/origin/traceable", None),
        ]
        for change, code, pointer, reason in structural:
            with self.subTest(structure_before_provenance=repr(change)[:60]):
                exc = self.assertCode(code, P.validate_fixture_manifest_entry, make_manifest_entry(**change),
                                      self.reg, expect_field=pointer)
                if reason is not None:
                    self.assertEqual(exc.reason, reason)
        negative = dict(fixture_id="negative-sample-1",
                        origin={"class": "negative", "derived_from": "synthetic-protocol-sample-1", "fault": "x"},
                        does_not_prove=[], expected={"outcome": "reject", "code": "E_JSON_SYNTAX"})
        # 对照：各自单独出现时分别由第 4 步、第 5 步报告。
        for proves, integrity, preserved, reason in (
                (["vendor_protocol"], "complete", None, "real_compatibility_claim_requires_captured_raw"),
                (["full_run"], "truncated", None, "incomplete_fixture_cannot_prove_complete_stream"),
                (["legacy_dispatch_behavior"], "complete", None, "legacy_dispatch_claim_requires_legacy_judgment"),
                (["protocol_field_semantics"], "complete", False,
                 "structure_not_preserved_cannot_prove_field_semantics"),
                (["vendor_protocol", "full_run"], "truncated", None, "real_compatibility_claim_requires_captured_raw"),
                (["full_run", "vendor_protocol"], "truncated", None, "real_compatibility_claim_requires_captured_raw"),
                (["protocol_field_semantics", "legacy_dispatch_behavior"], "complete", False,
                 "legacy_dispatch_claim_requires_legacy_judgment")):
            entry = make_manifest_entry(**negative, integrity=integrity, proves=proves,
                                        redaction={"protocol_structure_preserved": preserved})
            with self.subTest(step_4_before_step_5=proves, integrity=integrity, preserved=preserved):
                exc = self.assertCode("E_PROVENANCE_CLAIM", P.validate_fixture_manifest_entry, entry, self.reg,
                                      expect_field="/proves")
                self.assertEqual(exc.reason, reason)

    def test_A12_r_p11_manifest_set_reports_entry_pointer(self):
        """裁决 R-P11：整份清单逐条按新结构校验，新字段的错误 field 带 /entries/<i> 前缀；新字段不参与清单级的
        派生与碰撞规则（负例从 captured 以外的条目派生时 capture 为 null）。"""
        a = make_manifest_entry()
        b = make_manifest_entry(fixture_id="negative-sample-1",
                                origin={"class": "negative", "derived_from": a["fixture_id"], "fault": "x"},
                                resource={"id": "negative-sample-1",
                                          "path": "tests/fixtures/codekit01/negative/sample-1.json"},
                                does_not_prove=[], expected={"outcome": "reject", "code": "E_JSON_SYNTAX"},
                                integrity="corrupted", platform_scope=["windows"])
        doc = {"schema_version": 1, "record_type": "fixture-manifest-set", "entries": [a, b]}
        self.assertEqual(P.validate_fixture_manifest_set(doc, self.reg)["entries"], 2)
        for change, code, pointer in (({"platform_scope": []}, "E_SCHEMA_FIELDS", "/entries/1/platform_scope"),
                                      ({"integrity": "full"}, "E_SCHEMA_FIELDS", "/entries/1/integrity"),
                                      ({"capture": {"environment_ref": copy.deepcopy(CAPTURE_ENV_REF), "range": "r"}},
                                       "E_PROVENANCE_CLAIM", "/entries/1/capture")):
            with self.subTest(change=change):
                self.assertCode(code, P.validate_fixture_manifest_set, {**doc, "entries": [a, {**b, **change}]},
                                self.reg, expect_field=pointer)


# ===========================================================================
# 不可变发布（4.2.8、8.3、01-D06；01-F048，01-A13）
# ===========================================================================
def sealed_ref(result):
    """规格说 seal_bytes 返回 dict 并以 ResourceRef 调用 index_commit。
    P2 调和修正（规格澄清 C-13）：原辅助函数也接受 {"ref": ...} 包装。现固定为：返回值与交给
    index_commit 的参数都**恰好**是 ResourceRef 的四个字段 {kind, id, sha256, path}，
    可直接交给 read_sealed；平台限制（Windows 不 fsync 目录）写在模块常量与接口说明中。"""
    if set(result) != {"kind", "id", "sha256", "path"}:
        raise AssertionError(f"seal_bytes 返回值应恰为 ResourceRef 四个字段，实际键：{sorted(result)}")
    return dict(result)


class IndexRecorder:
    def __init__(self, store: Path, fail: bool = False):
        self.store = store
        self.fail = fail
        self.calls = []
        self.visible = []

    def __call__(self, ref):
        self.calls.append(copy.deepcopy(ref))
        final = self.store / ref["path"]
        self.visible.append(final.is_file() and sha(final.read_bytes()) == ref["sha256"])
        if self.fail:
            raise RuntimeError("simulated index failure")


class SealingTests(ProtocolTestCase):
    RAW = b'{"sealed":true}\n'

    @classmethod
    def setUpClass(cls):
        if _SEALING_IMPORT_ERROR is not None:
            raise _SEALING_IMPORT_ERROR

    def setUp(self):
        super().setUp()
        self._td = tempfile.TemporaryDirectory(prefix="codekit-seal-")
        self.addCleanup(self._td.cleanup)
        self.top = Path(self._td.name)
        self.store = self.top / "store"
        (self.store / "evidence").mkdir(parents=True)
        self.outside = self.top / "outside"
        self.outside.mkdir()

    def seal(self, business_path="evidence/sample-1.json", raw=None, *, kind="baseline-evidence",
             resource_id="sample-1", index=None, registry=None):
        index = index if index is not None else IndexRecorder(self.store)
        return S.seal_bytes(self.store, business_path, self.RAW if raw is None else raw, kind=kind,
                            resource_id=resource_id,
                            registry=self.reg if registry is None else registry,
                            index_commit=index), index

    def listing(self, directory: Path):
        return sorted(p.name for p in directory.iterdir())

    def make_dir_link(self, link: Path, target: Path):
        if IS_WINDOWS:
            import _winapi
            _winapi.CreateJunction(str(target), str(link))
            self.addCleanup(os.rmdir, link)
        else:
            try:
                os.symlink(target, link, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"无法创建目录符号链接（{type(exc).__name__}）")

    def test_A13_seal_publishes_then_indexes(self):
        """4.2.8：写入并核验后发布不可变文件，再以 ResourceRef 提交索引；索引看到的文件已可读、摘要一致。"""
        result, index = self.seal()
        ref = sealed_ref(result)
        self.assertEqual(ref, {"kind": "baseline-evidence", "id": "sample-1",
                               "sha256": sha(self.RAW), "path": "evidence/sample-1.json"})
        P.validate_resource_ref(ref, self.reg)
        self.assertEqual(len(index.calls), 1)
        self.assertEqual(sealed_ref(index.calls[0]), ref)
        self.assertEqual(index.visible, [True], "索引不能先于可读的发布文件")
        self.assertEqual((self.store / "evidence" / "sample-1.json").read_bytes(), self.RAW)
        self.assertEqual(self.listing(self.store / "evidence"), ["sample-1.json"],
                         "不应残留临时文件")

    def test_A13_seal_idempotent_same_bytes(self):
        """4.2.8、8.3：同一路径同一字节再次封存是幂等的：返回同一引用、文件不变、无临时残留。"""
        first, _ = self.seal()
        second, index = self.seal()
        self.assertEqual(sealed_ref(first), sealed_ref(second))
        self.assertEqual(len(index.calls), 1)
        self.assertEqual((self.store / "evidence" / "sample-1.json").read_bytes(), self.RAW)
        self.assertEqual(self.listing(self.store / "evidence"), ["sample-1.json"])

    def test_A13_seal_conflict_does_not_overwrite(self):
        """4.2.8：最终名已存在且字节不同 → E_RESOURCE_CONFLICT；不覆盖、不调用索引、不返回引用、无残留。"""
        existing = self.store / "evidence" / "sample-1.json"
        existing.write_bytes(b"different\n")
        index = IndexRecorder(self.store)
        self.assertCode("E_RESOURCE_CONFLICT", self.seal, index=index)
        self.assertEqual(existing.read_bytes(), b"different\n")
        self.assertEqual(index.calls, [])
        self.assertEqual(self.listing(self.store / "evidence"), ["sample-1.json"])

    def test_F048_index_failure_leaves_unreferenced_candidate(self):
        """01-F048 / 4.2.8、8.3：文件已发布但索引提交失败 → E_RESOURCE_INDEX_FAILED（retryable），
        不返回引用；文件作为未引用候选保留；同字节重新封存可幂等补录索引。"""
        failing = IndexRecorder(self.store, fail=True)
        exc = self.assertCode("E_RESOURCE_INDEX_FAILED", self.seal, index=failing)
        self.assertIs(exc.retryable, True)
        self.assertEqual(len(failing.calls), 1)
        self.assertEqual(failing.visible, [True])
        final = self.store / "evidence" / "sample-1.json"
        self.assertEqual(final.read_bytes(), self.RAW)
        self.assertEqual(self.listing(self.store / "evidence"), ["sample-1.json"])
        result, index = self.seal()
        self.assertEqual(len(index.calls), 1)
        self.assertEqual(sealed_ref(result)["sha256"], sha(self.RAW))
        self.assertEqual(final.read_bytes(), self.RAW)

    def test_F048_index_failure_any_exception(self):
        """01-F048 / 4.2.8：P2 返工新增（复审变异 S15）。index_commit 抛出 RuntimeError 以外的任何异常
        （ValueError、OSError 等）同样 → E_RESOURCE_INDEX_FAILED（retryable），不泄漏原异常、不返回引用。"""
        for error in (ValueError("index rejected"), OSError("index store unavailable"),
                      KeyError("x")):
            with self.subTest(error=type(error).__name__):
                calls = []

                def failing(ref, _error=error):
                    calls.append(ref)
                    raise _error

                exc = self.assertCode("E_RESOURCE_INDEX_FAILED", self.seal, index=failing)
                self.assertIs(exc.retryable, True)
                self.assertEqual(len(calls), 1)
        self.assertEqual((self.store / "evidence" / "sample-1.json").read_bytes(), self.RAW)

    def test_A13_seal_rejects_invalid_path_without_writing(self):
        """4.1.5、7.4：业务路径词法非法 → E_PATH_SYNTAX / E_PATH_RESERVED，存储区不产生任何文件。"""
        for path, code in (("../outside/x.json", "E_PATH_SYNTAX"), ("/abs.json", "E_PATH_SYNTAX"),
                           ("evidence\\x.json", "E_PATH_SYNTAX"), ("evidence/NUL.txt", "E_PATH_RESERVED")):
            with self.subTest(path=path):
                index = IndexRecorder(self.store)
                self.assertCode(code, self.seal, path, index=index)
                self.assertEqual(index.calls, [])
        self.assertEqual(self.listing(self.store / "evidence"), [])
        self.assertEqual(self.listing(self.outside), [])
        self.assertEqual(self.listing(self.store), ["evidence"])

    def test_A13_seal_rejects_unregistered_or_non_file_kind(self):
        """4.2.1、4.2.8：kind 未登记 → E_RESOURCE_KIND；非文件型 kind 不能封存为文件；都不写入。"""
        index = IndexRecorder(self.store)
        self.assertCode("E_RESOURCE_KIND", self.seal, kind="plugin-lock", index=index)
        note = make_kind(name="note", is_file=False, owner_module="01", description="测试")
        # P2 调和（规格澄清 C-13）：原测试只断言“被拒绝”，现固定错误码。
        self.assertCode("E_RESOURCE_KIND", self.seal, kind="note", index=index,
                        registry=self.reg.extended([note]), expect_field="/kind")
        self.assertCode("E_RESOURCE_FIELD", self.seal, resource_id="Bad ID", index=index,
                        expect_field="/id")
        self.assertCode("E_RESOURCE_BYTES", self.seal, raw=bytearray(self.RAW), index=index)
        self.assertEqual(index.calls, [])
        self.assertEqual(self.listing(self.store / "evidence"), [])
        # 存储根不存在或不是目录 → E_PATH_ROOT，且不会创建根目录。
        missing_root = self.top / "no-store"
        with self.assertRaises(P.ProtocolError) as caught:
            S.seal_bytes(missing_root, "evidence/x.json", self.RAW, kind="baseline-evidence",
                         resource_id="x-1", registry=self.reg, index_commit=index)
        self.assertEqual(caught.exception.code, "E_PATH_ROOT")
        self.assertFalse(missing_root.exists())
        self.assertEqual(index.calls, [])

    def test_A13_seal_readback_mismatch_publishes_nothing(self):
        """01-A13“摘要不符……不发布可用假引用”：P2 调和新增（白盒注入）。临时文件读回的字节与
        调用方字节不一致时 → E_RESOURCE_HASH_MISMATCH；不发布最终文件、不留临时文件、
        不调用 index_commit、不返回引用。注入点是 sealing 内部的读回函数 _read_all，
        仅在本用例内替换并恢复（黑盒无法制造写入后读回不一致）。"""
        original = S._read_all

        def corrupting_read(p, path, phase):
            data = original(p, path, phase)
            if Path(path).name.startswith(".codekit-seal-"):
                return data[:-1] + bytes([data[-1] ^ 0x01])
            return data

        index = IndexRecorder(self.store)
        S._read_all = corrupting_read
        try:
            self.assertCode("E_RESOURCE_HASH_MISMATCH", self.seal, index=index)
        finally:
            S._read_all = original
        self.assertEqual(index.calls, [])
        self.assertEqual(self.listing(self.store / "evidence"), [], "不得发布最终文件或残留临时文件")

    def test_A13_seal_escape_via_directory_link(self):
        """4.1.6、4.2.8：最终路径经链接（Windows 为 junction）解析到存储根外 → E_PATH_ESCAPE，根外不写入。"""
        self.make_dir_link(self.store / "escape", self.outside)
        index = IndexRecorder(self.store)
        self.assertCode("E_PATH_ESCAPE", self.seal, "escape/x.json", index=index)
        self.assertEqual(self.listing(self.outside), [])
        self.assertEqual(index.calls, [])

    def test_A13_seal_and_read_reject_kelvin_sign_sibling(self):
        """4.1.6、4.2.8、01-A13：P2 返工新增（复审 paths 视角，blocker）。存储根 Kit-store 与兄弟目录
        \\u212Ait-store（U+212A 开尔文符号）在 str.lower() 后相同、在 NTFS 上是两个目录。经根内链接
        （Windows 为 junction；另试文件 symlink）指向兄弟目录时：seal_bytes → E_PATH_ESCAPE 且根外没有
        任何写入、不调用索引；read_sealed → E_PATH_ESCAPE，不返回根外字节（修复前两者都成功）。"""
        store = self.top / "Kit-store"
        store.mkdir()
        sibling = self.top / "Kit-store"
        try:
            sibling.mkdir()
        except FileExistsError:
            self.skipTest("本文件系统把 U+212A 与 K 视为同一名称，不存在该别名问题，未实测")
        if os.path.samefile(store, sibling):
            self.skipTest("两个名称解析到同一目录，不存在该别名问题，未实测")
        secret = b"outside secret\n"
        (sibling / "secret.txt").write_bytes(secret)
        self.make_dir_link(store / "jn", sibling)
        index = IndexRecorder(store)
        with self.assertRaises(P.ProtocolError) as caught:
            S.seal_bytes(store, "jn/new.json", self.RAW, kind="baseline-evidence",
                         resource_id="new-1", registry=self.reg, index_commit=index)
        self.assertEqual(caught.exception.code, "E_PATH_ESCAPE")
        self.assertEqual(self.listing(sibling), ["secret.txt"], "根外不得创建任何文件")
        self.assertEqual(index.calls, [])
        with self.assertRaises(P.ProtocolError) as caught:
            S.seal_bytes(store, "jn/deeper/new.json", self.RAW, kind="baseline-evidence",
                         resource_id="new-2", registry=self.reg, index_commit=index)
        self.assertEqual(caught.exception.code, "E_PATH_ESCAPE")
        self.assertEqual(self.listing(sibling), ["secret.txt"], "根外不得创建目录")
        ref = {"kind": "baseline-evidence", "id": "secret-1", "sha256": sha(secret),
               "path": "jn/secret.txt"}
        self.assertCode("E_PATH_ESCAPE", S.read_sealed, store, ref, self.reg)
        try:
            os.symlink(sibling / "secret.txt", store / "x.txt")
        except (OSError, NotImplementedError):
            pass  # 缺少创建符号链接的权限时只实测 junction/目录链接部分
        else:
            self.assertCode("E_PATH_ESCAPE", S.read_sealed, store, {**ref, "path": "x.txt"}, self.reg)
        # 正例不受影响：根内照常封存与读取。
        result = S.seal_bytes(store, "evidence/ok.json", self.RAW, kind="baseline-evidence",
                              resource_id="ok-1", registry=self.reg, index_commit=index)
        self.assertEqual(S.read_sealed(store, sealed_ref(result), self.reg), self.RAW)

    def test_A13_read_sealed_reads_once_returns_verified_bytes(self):
        """4.2.8“核验后消费同一字节”、01-A13：P2 返工新增（复审变异 S021，白盒注入）。read_sealed 只读
        一次字节，核验摘要后返回**这同一份**字节，不在核验后重新读取（否则返回的不是核验过的字节，
        TOCTOU 回归）。注入点是 sealing 内部读取函数 _read_all：第 1 次返回真实字节，之后返回不同字节；
        仅在本用例内替换并恢复。"""
        result, _ = self.seal()
        ref = sealed_ref(result)
        original = S._read_all
        calls = []

        def swapping_read(p, path, phase):
            calls.append(phase)
            data = original(p, path, phase)
            return data if len(calls) == 1 else b"EVIL" + data

        S._read_all = swapping_read
        try:
            data = S.read_sealed(self.store, ref, self.reg)
        finally:
            S._read_all = original
        self.assertEqual(calls, ["read"], "read_sealed 必须恰好读取一次")
        self.assertEqual(data, self.RAW)
        self.assertEqual(sha(data), ref["sha256"])

    def test_A13_seal_final_name_occupied_by_directory(self):
        """4.2.8“最终名已存在：不同 → E_RESOURCE_CONFLICT，不覆盖”：P2 返工新增（复审 fidelity/paths 视角）。
        最终名被目录（Windows 上还有指向根内目录的 junction）占用 → E_RESOURCE_CONFLICT
        （reason=immutable_path_occupied_by_non_file），不是“资源缺失”；不调用索引、不留临时文件。"""
        (self.store / "evidence" / "taken").mkdir()
        index = IndexRecorder(self.store)
        exc = self.assertCode("E_RESOURCE_CONFLICT", self.seal, "evidence/taken", index=index,
                              expect_field="/path")
        self.assertEqual(exc.reason, "immutable_path_occupied_by_non_file")
        self.assertEqual(index.calls, [])
        self.assertEqual(self.listing(self.store / "evidence"), ["taken"])
        self.assertEqual(self.listing(self.store / "evidence" / "taken"), [])
        if IS_WINDOWS:
            self.make_dir_link(self.store / "evidence" / "jtaken", self.store / "evidence" / "taken")
            self.assertCode("E_RESOURCE_CONFLICT", self.seal, "evidence/jtaken", index=index)
            self.assertEqual(index.calls, [])

    def test_A13_seal_final_name_symlink_outside(self):
        """4.1.6、4.2.8：P2 返工新增（复审 paths 视角）。最终名本身是指向根外文件的 symlink → E_PATH_ESCAPE；
        同字节与异字节都一样，根外文件不被读取比较或改写，也不调用索引。"""
        outside_file = self.outside / "victim.json"
        outside_file.write_bytes(self.RAW)
        try:
            os.symlink(outside_file, self.store / "evidence" / "link.json")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"无法创建符号链接（{type(exc).__name__}），未实测该项")
        index = IndexRecorder(self.store)
        for raw in (self.RAW, b"different\n"):
            with self.subTest(raw=raw):
                self.assertCode("E_PATH_ESCAPE", self.seal, "evidence/link.json", raw, index=index)
        self.assertEqual(outside_file.read_bytes(), self.RAW)
        self.assertEqual(index.calls, [])
        self.assertEqual(self.listing(self.outside), ["victim.json"])

    def test_A13_seal_rejects_filesystem_aliases(self):
        """4.1.5、4.2.8：P2 返工新增（复审 paths 视角，major）。每一级拼写必须是磁盘上登记的真实名称：
        大小写别名（已有 Sample.json 时封存 sample.json、已有 Fixtures/ 时封存 fixtures/b.json）在大小写不敏感的
        文件系统上 → E_PATH_COLLISION；否则返回的 path 拼写在磁盘上并不存在，Linux/macOS 上无法解析。
        P4（裁决 R-P3）起，经自动生成的 8.3 短名写进另一个名字的目录在词法层即 → E_PATH_RESERVED（下方断言，
        不访问存储区）；P4 第 3 轮更正本 docstring（原写“经 8.3 短名 → E_PATH_RESOLUTION_FAILED”，与断言不符）。
        物理层对手工设置、不含 "~" 的短名的兜底（E_PATH_RESOLUTION_FAILED）见
        test_A13_short_name_aliases_rejected_by_all_entries。"""
        (self.store / "Sample.json").write_bytes(self.RAW)
        index = IndexRecorder(self.store)
        case_insensitive = (self.store / "sample.json").exists()
        if case_insensitive:
            self.assertCode("E_PATH_COLLISION", self.seal, "sample.json", index=index)
            self.seal("Fixtures/a.json", index=index)
            self.assertCode("E_PATH_COLLISION", self.seal, "fixtures/b.json", index=index)
            self.assertEqual(self.listing(self.store / "Fixtures"), ["a.json"])
            ref = {"kind": "baseline-evidence", "id": "sample-1", "sha256": sha(self.RAW),
                   "path": "SAMPLE.json"}
            self.assertCode("E_PATH_COLLISION", S.read_sealed, self.store, ref, self.reg)
        self.assertEqual(len(index.calls), 1 if case_insensitive else 0)
        agent = self.store / ".agent-longname"
        agent.mkdir()
        (agent / "cfg.json").write_bytes(b"{}")
        short = windows_short_name(agent)
        if short is None:
            self.skipTest("本卷没有 8.3 短名（或不是 Windows），8.3 别名部分未实测")
        calls_before = len(index.calls)
        # P4（裁决 R-P3）：8.3 短名形态在词法层即 → E_PATH_RESERVED，不访问存储区；物理层的兜底核对
        # （E_PATH_RESOLUTION_FAILED）见 PhysicalPathTests.test_A10_filesystem_aliases_rejected。
        exc = self.assertCode("E_PATH_RESERVED", self.seal, f"{short}/new.json", index=index)
        self.assertEqual(exc.reason, "windows_short_name_form")
        self.assertEqual(self.listing(agent), ["cfg.json"])
        self.assertEqual(len(index.calls), calls_before)
        ref = {"kind": "baseline-evidence", "id": "cfg-1", "sha256": sha(b"{}"),
               "path": f"{short}/cfg.json"}
        self.assertCode("E_PATH_RESERVED", S.read_sealed, self.store, ref, self.reg)
        self.assertEqual(S.read_sealed(self.store, {**ref, "path": ".agent-longname/cfg.json"},
                                       self.reg), b"{}")

    def test_A13_short_name_aliases_rejected_by_all_entries(self):
        """4.1.5、4.1.6、4.2.8、裁决 R-P3：P4 第 3 轮新增（复审 paths 视角，major）。
        - 目录 .~agentconfig 的自动短名 ~AGENT~1（前缀含 "~"，修复前词法层漏掉）：seal_bytes、read_sealed、
          resolve_existing_path_for_review 都在词法层 → E_PATH_RESERVED，不访问存储区；
        - 手工设置、不含 "~" 的短名（fsutil file setshortname）不是 8.3 形态，词法层接受；三个入口在物理层都 →
          E_PATH_RESOLUTION_FAILED（noncanonical_filesystem_alias），根内没有写入，也不调用索引。
        卷没有 8.3 短名或 fsutil 不可用时，对应部分 skip 并写明原因。"""
        agent = self.store / ".~agentconfig"
        agent.mkdir()
        (agent / "cfg.json").write_bytes(b"{}")
        index = IndexRecorder(self.store)
        ref = {"kind": "baseline-evidence", "id": "cfg-1", "sha256": sha(b"{}"), "path": ".~agentconfig/cfg.json"}
        self.assertEqual(S.read_sealed(self.store, ref, self.reg), b"{}")
        short = windows_short_name(agent)
        if short is not None:
            self.assertEqual(short.rsplit("~", 1)[0][:1], "~", "前提：自动短名的前缀含 ~")
            for call in (lambda: self.seal(f"{short}/new.json", index=index),
                         lambda: S.read_sealed(self.store, {**ref, "path": f"{short}/cfg.json"}, self.reg),
                         lambda: P.resolve_existing_path_for_review(self.store, f"{short}/cfg.json")):
                with self.subTest(generated_short=short):
                    exc = self.assertCode("E_PATH_RESERVED", call, expect_field="/path")
                    self.assertEqual(exc.reason, "windows_short_name_form")
            self.assertEqual(self.listing(agent), ["cfg.json"])
        reason = set_manual_short_name(agent, "AGCFGX")
        if reason is not None:
            self.skipTest(reason + "，手工短名的物理层部分未实测")
        self.assertEqual(P.validate_business_path("AGCFGX/new.json"), "AGCFGX/new.json")
        for name, call in (("seal_bytes", lambda: self.seal("AGCFGX/new.json", index=index)),
                           ("read_sealed", lambda: S.read_sealed(self.store, {**ref, "path": "AGCFGX/cfg.json"},
                                                                 self.reg)),
                           ("resolve", lambda: P.resolve_existing_path_for_review(self.store, "AGCFGX/cfg.json"))):
            with self.subTest(manual_short=name):
                exc = self.assertCode("E_PATH_RESOLUTION_FAILED", call, expect_field="/path")
                self.assertEqual(exc.reason, "noncanonical_filesystem_alias")
        self.assertEqual(self.listing(agent), ["cfg.json"])
        self.assertEqual(index.calls, [])

    def test_A13_seal_and_read_reject_link_chain_through_outside(self):
        """4.1.6、4.2.8、01-A13：P4 第 3 轮新增（复审 fidelity 视角，major）。同一分段内的链接链经根外绕回根内：
        store/hop → outside/hop2 → store/evidence/x.json、store/dhop → outside/dhop2 → store/evidence。修复前 read_sealed
        返回字节、seal_bytes 经这条链把文件写进 store/evidence。现在两者都 → E_PATH_ESCAPE
        （reason=link_hop_outside_trusted_root），不读取、不写入、不调用索引；根内的链接链照常可用。"""
        target = self.store / "evidence" / "x.json"
        target.write_bytes(self.RAW)
        try:
            os.symlink(target, self.outside / "hop2")
            os.symlink(self.outside / "hop2", self.store / "hop")
            os.symlink(self.store / "evidence", self.outside / "dhop2", target_is_directory=True)
            os.symlink(self.outside / "dhop2", self.store / "dhop", target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"无法创建符号链接（{type(exc).__name__}），未实测该项")
        index = IndexRecorder(self.store)
        ref = {"kind": "baseline-evidence", "id": "x-1", "sha256": sha(self.RAW), "path": "hop"}
        for path in ("hop", "dhop/x.json"):
            with self.subTest(read=path):
                exc = self.assertCode("E_PATH_ESCAPE", S.read_sealed, self.store, {**ref, "path": path}, self.reg,
                                      expect_field="/path")
                self.assertEqual(exc.reason, "link_hop_outside_trusted_root")
        for path in ("dhop/new.json", "dhop/x.json", "hop"):
            with self.subTest(seal=path):
                exc = self.assertCode("E_PATH_ESCAPE", self.seal, path, index=index, expect_field="/path")
                self.assertEqual(exc.reason, "link_hop_outside_trusted_root")
        self.assertEqual(self.listing(self.store / "evidence"), ["x.json"])
        self.assertEqual(self.listing(self.outside), ["dhop2", "hop2"])
        self.assertEqual(index.calls, [])
        # 根内的链接链照常可用。
        os.symlink(self.store / "evidence", self.store / "in-dir", target_is_directory=True)
        self.assertEqual(S.read_sealed(self.store, {**ref, "path": "in-dir/x.json"}, self.reg), self.RAW)
        result, _ = self.seal("in-dir/y.json")
        self.assertEqual(sealed_ref(result)["path"], "in-dir/y.json")
        self.assertEqual((self.store / "evidence" / "y.json").read_bytes(), self.RAW)

    def _link_or_skip(self, target, link, is_dir: bool = False):
        try:
            os.symlink(target, link, target_is_directory=is_dir)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"无法创建符号链接（{type(exc).__name__}），未实测该项")
        if isinstance(link, str):  # 逐字路径创建的名称要按逐字路径删除（先于临时目录的清理执行）
            self.addCleanup(os.rmdir if is_dir else os.unlink, link)

    def _assert_all_entries_escape(self, read_paths, seal_paths, index, evidence_listing=("x.json",)):
        ref = {"kind": "baseline-evidence", "id": "x-1", "sha256": sha(self.RAW), "path": "x"}
        for path in read_paths:
            with self.subTest(read=path):
                exc = self.assertCode("E_PATH_ESCAPE", S.read_sealed, self.store, {**ref, "path": path}, self.reg,
                                      expect_field="/path")
                self.assertEqual(exc.reason, "link_hop_outside_trusted_root")
        for path in seal_paths:
            with self.subTest(seal=path):
                exc = self.assertCode("E_PATH_ESCAPE", self.seal, path, index=index, expect_field="/path")
                self.assertEqual(exc.reason, "link_hop_outside_trusted_root")
        self.assertEqual(self.listing(self.store / "evidence"), sorted(evidence_listing))
        self.assertEqual(index.calls, [])

    def test_A13_seal_and_read_reject_relative_link_chain_through_outside(self):
        """4.1.6、4.2.8、01-A13：P4 第 4 轮新增（复审 tests-mutation 视角，major）。经根外绕回根内的链以**相对**目标
        开头：store/relhop → "hop2"、store/evidence/up → "..\\hop2"（hop2 → outside/hop3 → evidence/x.json），目录链
        store/reld → "dhop2"（dhop2 → outside/dhop3 → evidence）。read_sealed 与 seal_bytes 都 → E_PATH_ESCAPE
        （link_hop_outside_trusted_root），不读取、不写入、不调用索引；此前相对目标的越界分支没有拒绝用例。"""
        target = self.store / "evidence" / "x.json"
        target.write_bytes(self.RAW)
        self._link_or_skip(target, self.outside / "hop3")
        self._link_or_skip(self.outside / "hop3", self.store / "hop2")
        self._link_or_skip("hop2", self.store / "relhop")
        self._link_or_skip(os.path.join("..", "hop2"), self.store / "evidence" / "up")
        self._link_or_skip(self.store / "evidence", self.outside / "dhop3", is_dir=True)
        self._link_or_skip(self.outside / "dhop3", self.store / "dhop2", is_dir=True)
        self._link_or_skip("dhop2", self.store / "reld", is_dir=True)
        self.assertEqual((self.store / "reld" / "x.json").resolve(strict=True), target.resolve(strict=True))
        index = IndexRecorder(self.store)
        self._assert_all_entries_escape(("relhop", "evidence/up", "reld/x.json"),
                                        ("reld/new.json", "reld/x.json", "relhop", "evidence/up"), index,
                                        evidence_listing=("up", "x.json"))
        self.assertEqual(self.listing(self.outside), ["dhop3", "hop3"])

    @unittest.skipUnless(IS_WINDOWS, "按词法折叠 \"..\"、名称末尾的点与空格被 Win32 规范化去掉，都是 Windows 特有的情形")
    def test_A13_seal_and_read_windows_lexical_and_trailing_dot_chains(self):
        """4.1.6、4.2.8、01-A13：P4 第 4 轮新增（复审 fidelity 与 paths 视角，major）。Windows 上两类此前能绕过逐跳
        核对的链，read_sealed 与 seal_bytes 现在都 → E_PATH_ESCAPE，不读取、不写入、不调用索引：
        - 目标文本 "L\\..\\y"：OS 按词法折叠为 store/y（→ outside/hop → evidence/x.json），修复前逐跳核对先跟随
          L 再取上一级，走到不存在的 a/y 就静默结束；目录链 segd → "L\\..\\yd"（yd → outside/dhop → evidence）
          曾让 seal_bytes 把文件写进 evidence；
        - 目标文本 "hop."、"hop "、"dhop."：这些名称本身是指向根外的链接，Win32 路径去掉末尾的点与空格后看不到它们。
        根内的同类链照常可用：segok → "L\\..\\evidence\\x.json" 可读，segdok → "L\\..\\evidence" 下可封存。"""
        target = self.store / "evidence" / "x.json"
        target.write_bytes(self.RAW)
        (self.store / "a" / "b").mkdir(parents=True)
        self._link_or_skip(self.store / "a" / "b", self.store / "L", is_dir=True)
        self._link_or_skip(target, self.outside / "hop")
        self._link_or_skip(self.outside / "hop", self.store / "y")
        self._link_or_skip("L\\..\\y", self.store / "seg")
        self._link_or_skip(self.store / "evidence", self.outside / "dhop", is_dir=True)
        self._link_or_skip(self.outside / "dhop", self.store / "yd", is_dir=True)
        self._link_or_skip("L\\..\\yd", self.store / "segd", is_dir=True)
        prefix = verbatim(self.store) + "\\"
        self._link_or_skip(verbatim(self.outside / "hop"), prefix + "hop.")
        self._link_or_skip(verbatim(self.outside / "hop"), prefix + "hop ")
        self._link_or_skip(verbatim(self.outside / "dhop"), prefix + "dhop.", is_dir=True)
        self._link_or_skip("hop.", self.store / "segdot")
        self._link_or_skip("hop ", self.store / "segsp")
        self._link_or_skip("dhop.", self.store / "segd2", is_dir=True)
        # 前提：OS 解析都经过根外的 hop/dhop（它们被删除后这些路径都无法解析，见复审证据）。
        for name in ("seg", "segdot", "segsp"):
            self.assertEqual((self.store / name).resolve(strict=True), target.resolve(strict=True))
        index = IndexRecorder(self.store)
        self._assert_all_entries_escape(("seg", "segd/x.json", "segdot", "segsp", "segd2/x.json"),
                                        ("segd/new.json", "segd2/new.json", "seg", "segdot"), index)
        self.assertEqual(sorted(os.listdir(self.outside)), ["dhop", "hop"])
        self._link_or_skip("L\\..\\evidence\\x.json", self.store / "segok")
        self._link_or_skip("L\\..\\evidence", self.store / "segdok", is_dir=True)
        ref = {"kind": "baseline-evidence", "id": "x-1", "sha256": sha(self.RAW), "path": "segok"}
        self.assertEqual(S.read_sealed(self.store, ref, self.reg), self.RAW)
        result, accepted_index = self.seal("segdok/z.json")
        self.assertEqual(sealed_ref(result)["path"], "segdok/z.json")
        self.assertEqual((self.store / "evidence" / "z.json").read_bytes(), self.RAW)
        self.assertEqual(len(accepted_index.calls), 1)

    def test_A13_link_walk_divergence_rejected_by_seal_and_read(self):
        """4.1.6、4.2.8、01-A13：P4 第 4 轮新增（白盒注入，复审 tests-mutation 视角）。seal_bytes 与 read_sealed 同样把
        每一级 resolve 的结果交给逐跳核对：替换 protocols._link_target_text，让逐跳展开读到 "."（终点变成链接所在
        的 store 本身，而 OS 解析到 evidence 下）时 → E_PATH_RESOLUTION_FAILED（link_walk_diverged），不读取、不写入、
        不调用索引。用后恢复；真实文本下照常可用。"""
        target = self.store / "evidence" / "x.json"
        target.write_bytes(self.RAW)
        self._link_or_skip(target, self.store / "alias")
        self._link_or_skip(self.store / "evidence", self.store / "aliasdir", is_dir=True)
        ref = {"kind": "baseline-evidence", "id": "x-1", "sha256": sha(self.RAW), "path": "alias"}
        index = IndexRecorder(self.store)
        real = P._link_target_text

        def patched(path):
            return "." if path.name in ("alias", "aliasdir") else real(path)

        P._link_target_text = patched
        try:
            for call in (lambda: S.read_sealed(self.store, ref, self.reg),
                         lambda: S.read_sealed(self.store, {**ref, "path": "aliasdir/x.json"}, self.reg),
                         lambda: self.seal("aliasdir/new.json", index=index)):
                exc = self.assertCode("E_PATH_RESOLUTION_FAILED", call, expect_field="/path")
                self.assertEqual(exc.reason, "link_walk_diverged")
        finally:
            P._link_target_text = real
        self.assertEqual(self.listing(self.store / "evidence"), ["x.json"])
        self.assertEqual(index.calls, [])
        self.assertEqual(S.read_sealed(self.store, ref, self.reg), self.RAW)
        result, _ = self.seal("aliasdir/new.json")
        self.assertEqual(sealed_ref(result)["path"], "aliasdir/new.json")

    def test_A13_unrecognized_name_surrogate_rejected_by_seal_and_read(self):
        """4.1.6、4.2.8、01-A13：P4 第 5 轮新增（裁决 R-P9 (1)，复审 fidelity 视角 major；白盒注入）。seal_bytes 与
        read_sealed 经 _check_link_hops 共用“未识别的名称代理类重解析点失败关闭”这条规则：替换 protocols 模块内的 os，
        让 os.lstat 对 store/hop（→ outside/hop2 → evidence/x.json）与 store/dhop（→ outside/dhop2 → evidence）报告
        S_IFREG/S_IFDIR 与标签 0xA0000019（GLOBAL_REPARSE）。修复前逐跳核对把它们当作普通名称：read_sealed 返回字节，
        seal_bytes 经 dhop 把文件写进 evidence。现在 read_sealed（文件链接、目录分段）、seal_bytes（目录分段、已存在的
        最终名）都 → E_PATH_RESOLUTION_FAILED（link_kind_unsupported），不读取、不写入、不调用索引。对照：不注入时
        同样的链 → E_PATH_ESCAPE。用后恢复。"""
        import stat as stat_module

        target = self.store / "evidence" / "x.json"
        target.write_bytes(self.RAW)
        self._link_or_skip(target, self.outside / "hop2")
        self._link_or_skip(self.outside / "hop2", self.store / "hop")
        self._link_or_skip(self.store / "evidence", self.outside / "dhop2", is_dir=True)
        self._link_or_skip(self.outside / "dhop2", self.store / "dhop", is_dir=True)
        index = IndexRecorder(self.store)
        self._assert_all_entries_escape(("hop", "dhop/x.json"), ("dhop/new.json", "hop"), index)
        ref = {"kind": "baseline-evidence", "id": "x-1", "sha256": sha(self.RAW), "path": "hop"}
        restore = fake_reparse_tags({"hop": (stat_module.S_IFREG | 0o644, 0xA0000019),
                                     "dhop": (stat_module.S_IFDIR | 0o755, 0xA0000019)})
        try:
            calls = [("read", "hop", lambda: S.read_sealed(self.store, ref, self.reg)),
                     ("read", "dhop/x.json",
                      lambda: S.read_sealed(self.store, {**ref, "path": "dhop/x.json"}, self.reg)),
                     ("seal", "dhop/new.json", lambda: self.seal("dhop/new.json", index=index)),
                     ("seal", "hop", lambda: self.seal("hop", index=index))]
            for entry, path, call in calls:
                with self.subTest(entry=entry, path=path):
                    exc = self.assertCode("E_PATH_RESOLUTION_FAILED", call, expect_field="/path")
                    self.assertEqual(exc.reason, "link_kind_unsupported")
        finally:
            restore()
        self.assertEqual(self.listing(self.store / "evidence"), ["x.json"])
        self.assertEqual(self.listing(self.outside), ["dhop2", "hop2"])
        self.assertEqual(index.calls, [])

    def test_A13_hard_link_alias_is_known_not_detected(self):
        """01-A13、R-P9“已知不检测”清单：P4 第 5 轮新增（复审 fidelity 视角）。**这不是安全性测试，也不证明 01-F030**
        （F030 仍按 01-D06 skip）：它固定一项已写明的限制，使文档清单与实际行为一致。存储根中已有一个与根外文件共享
        数据的硬链接 store/evidence/h.json 时，路径层面它与普通文件无法区分：resolve_existing_path_for_review 接受，
        read_sealed 返回根外文件的字节，seal_bytes 以相同字节按幂等成功并调用一次 index_commit；根外改写之后，只有
        摘要核验能在读取时发现（E_RESOURCE_HASH_MISMATCH）。所以 sealing 要求存储根由可信核心独占控制（R-P9），
        PATH_REVIEW_LIMITATIONS 与 SEALING_LIMITATIONS 都列出硬链接。文件系统不支持硬链接时 skip。"""
        outside_file = self.outside / "secret.json"
        outside_file.write_bytes(b"outside-bytes\n")
        alias = self.store / "evidence" / "h.json"
        try:
            os.link(outside_file, alias)
        except (OSError, NotImplementedError, AttributeError) as exc:
            self.skipTest(f"无法创建硬链接（{type(exc).__name__}），未实测该项")
        self.assertEqual(P.resolve_existing_path_for_review(self.store, "evidence/h.json"),
                         self.store.resolve(strict=True) / "evidence" / "h.json")
        ref = {"kind": "baseline-evidence", "id": "h-1", "sha256": sha(b"outside-bytes\n"),
               "path": "evidence/h.json"}
        self.assertEqual(S.read_sealed(self.store, ref, self.reg), b"outside-bytes\n")
        result, index = self.seal("evidence/h.json", b"outside-bytes\n", resource_id="h-1")
        self.assertEqual(sealed_ref(result), ref)
        self.assertEqual(len(index.calls), 1)
        outside_file.write_bytes(b"rewritten-outside\n")
        exc = self.assertCode("E_RESOURCE_HASH_MISMATCH", S.read_sealed, self.store, ref, self.reg)
        self.assertEqual(exc.reason, "stored_bytes_digest_mismatch")
        self.assertTrue(any(item.startswith("硬链接不检测") for item in P.PATH_REVIEW_LIMITATIONS))
        self.assertTrue(any(item.startswith("硬链接不检测") for item in S.SEALING_LIMITATIONS))
        self.assertTrue(any("可信核心独占控制" in item for item in S.SEALING_LIMITATIONS))

    def test_A13_seal_post_publish_escape_is_reported(self):
        """4.2.8 第 6 步“发布后再次确认最终路径解析后仍在根内”：P4 第 3 轮新增（复审 tests-mutation S01）。
        白盒注入：替换 sealing 模块内的 os 引用，让“发布”（os.link）改为在最终名处创建指向根外文件的 symlink
        （模拟发布与复查之间被替换）。seal_bytes 必须 → E_PATH_ESCAPE，且不调用 index_commit、不返回引用；已创建的
        链接不删除（无法确认它仍是本次创建的对象，01-D06）。用后恢复。无法创建符号链接时 skip。"""
        outside_file = self.outside / "victim.json"
        outside_file.write_bytes(self.RAW)
        probe = self.top / "probe-link"
        try:
            os.symlink(outside_file, probe)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"无法创建符号链接（{type(exc).__name__}），未实测该项")
        probe.unlink()
        real_os = S.os

        class LinkBecomesEscape:
            def __getattr__(self, name):
                return getattr(real_os, name)

            @staticmethod
            def link(src, dst):
                real_os.symlink(outside_file, dst)

        index = IndexRecorder(self.store)
        S.os = LinkBecomesEscape()
        try:
            exc = self.assertCode("E_PATH_ESCAPE", self.seal, "evidence/post.json", index=index,
                                  expect_field="/path")
        finally:
            S.os = real_os
        self.assertEqual(exc.reason, "resolved_outside_store_root")
        self.assertEqual(index.calls, [])
        final = self.store / "evidence" / "post.json"
        self.assertTrue(final.is_symlink(), "事后报告：已创建的链接不删除")
        self.assertEqual(outside_file.read_bytes(), self.RAW)
        self.assertEqual([p.name for p in (self.store / "evidence").iterdir()
                          if p.name.startswith(".codekit-seal-")], [], "临时文件已删除")

    def test_A13_seal_temp_file_is_exclusive_and_fsynced(self):
        """4.2.8“独占创建临时文件，写完 flush+fsync”：P2 返工新增（复审变异 S10/S11/S18，白盒）。
        把临时名的随机部分固定并预置同名文件：独占创建必须失败，不能截断或删除其他写入者的文件，
        也不返回引用；正常封存时对临时文件至少调用一次 os.fsync。
        白盒原因：黑盒无法让随机临时名与已有文件相撞，也无法观察 fsync 调用。只替换 sealing 模块内的
        secrets 与 os 引用，用后恢复，不修改全局 os 模块。"""
        fixed = "0" * 32
        victim = self.store / "evidence" / (".codekit-seal-" + fixed + ".tmp")
        victim.write_bytes(b"OTHER WRITER")
        real_secrets, real_os = S.secrets, S.os
        fsync_calls = []

        class FixedSecrets:
            @staticmethod
            def token_hex(nbytes=None):
                return fixed

        class OsProxy:
            def __getattr__(self, name):
                return getattr(real_os, name)

            @staticmethod
            def fsync(fd):
                fsync_calls.append(fd)
                return real_os.fsync(fd)

        index = IndexRecorder(self.store)
        S.secrets = FixedSecrets()
        try:
            with self.assertRaises(FileExistsError):
                self.seal(index=index)
        finally:
            S.secrets = real_secrets
        self.assertEqual(victim.read_bytes(), b"OTHER WRITER")
        self.assertEqual(index.calls, [])
        self.assertFalse((self.store / "evidence" / "sample-1.json").exists())
        S.os = OsProxy()
        try:
            self.seal(index=index)
        finally:
            S.os = real_os
        self.assertGreaterEqual(len(fsync_calls), 1)
        self.assertEqual(len(index.calls), 1)

    def test_A13_seal_and_read_error_mapping(self):
        """4.2.8、01-A13：P2 返工新增（复审变异 S14/S19）。read_sealed 读非文件型 kind → E_RESOURCE_KIND；
        存储根是普通文件时 seal_bytes 与 read_sealed 都 → E_PATH_ROOT，且不创建任何文件。"""
        note = make_kind(name="note", is_file=False, owner_module="01", description="测试")
        registry = self.reg.extended([note])
        ref = {"kind": "note", "id": "note-1", "sha256": sha(self.RAW), "path": "evidence/sample-1.json"}
        self.assertCode("E_RESOURCE_KIND", S.read_sealed, self.store, ref, registry,
                        expect_field="/kind")
        root_file = self.top / "root-is-file"
        root_file.write_bytes(b"x")
        index = IndexRecorder(self.store)
        with self.assertRaises(P.ProtocolError) as caught:
            S.seal_bytes(root_file, "evidence/x.json", self.RAW, kind="baseline-evidence",
                         resource_id="x-1", registry=self.reg, index_commit=index)
        self.assertEqual(caught.exception.code, "E_PATH_ROOT")
        good_ref = {"kind": "baseline-evidence", "id": "x-1", "sha256": sha(self.RAW),
                    "path": "evidence/x.json"}
        self.assertCode("E_PATH_ROOT", S.read_sealed, root_file, good_ref, self.reg)
        self.assertEqual(root_file.read_bytes(), b"x")
        self.assertEqual(index.calls, [])
        self.assertEqual(sorted(p.name for p in self.top.iterdir()),
                         ["outside", "root-is-file", "store"])

    def test_A13_seal_temp_short_name_is_lexically_reserved(self):
        """4.2.8、01-A13：P4（第 2 轮复审 paths 视角；由裁决 R-P3 解决）。临时文件 .codekit-seal-<hex>.tmp
        在启用 8.3 短名的卷上自动得到 CODEKI~1.TMP 这类短名；以它为业务名封存时，原来 os.link 会命中临时文件
        自己的短名，合法请求以 E_PATH_RESOLUTION_FAILED 失败。现在这类名称在写入任何东西之前就以
        E_PATH_RESERVED 拒绝：不产生文件、不调用索引。"""
        for name in ("CODEKI~1.TMP", "evidence/codeki~1.tmp", "CODEKI~2.TMP"):
            with self.subTest(path=name):
                index = IndexRecorder(self.store)
                exc = self.assertCode("E_PATH_RESERVED", self.seal, name, index=index, expect_field="/path")
                self.assertEqual(exc.reason, "windows_short_name_form")
                self.assertEqual(index.calls, [])
        self.assertEqual(self.listing(self.store), ["evidence"])
        self.assertEqual(self.listing(self.store / "evidence"), [])

    def test_A13_seal_index_commit_argument_checks(self):
        """4.2.8：P4 新增（第 2 轮复审 tests-mutation S102/S105）。index_commit 不可调用 → 写入任何东西之前抛
        TypeError（不发布、不留临时文件）；index_commit 收到的是引用的副本，它修改参数不影响返回的引用。"""
        for bad in (None, 1, "commit"):
            with self.subTest(index_commit=repr(bad)):
                with self.assertRaises(TypeError):
                    S.seal_bytes(self.store, "evidence/sample-1.json", self.RAW, kind="baseline-evidence",
                                 resource_id="sample-1", registry=self.reg, index_commit=bad)
                self.assertEqual(self.listing(self.store / "evidence"), [])
        seen = []

        def tampering(ref):
            seen.append(dict(ref))
            ref["id"] = "tampered-1"
            ref["sha256"] = "0" * 64

        result, _ = self.seal(index=tampering)
        expected = {"kind": "baseline-evidence", "id": "sample-1", "sha256": sha(self.RAW),
                    "path": "evidence/sample-1.json"}
        self.assertEqual(sealed_ref(result), expected)
        self.assertEqual(seen, [expected])

    def test_A13_seal_and_read_non_directory_ancestor_and_directory_target(self):
        """4.2.8、01-A13：P4 新增（第 2 轮复审 tests-mutation S027/S028）。祖先分段是已存在的普通文件 →
        E_PATH_RESOLUTION_FAILED（reason=ancestor_not_directory），不新增文件、不调用索引；read_sealed 的 path
        指向目录 → E_RESOURCE_MISSING（reason=not_regular_file）。两处都不泄漏原生 OSError。"""
        blocker = self.store / "evidence" / "f.json"
        blocker.write_bytes(b"file\n")
        index = IndexRecorder(self.store)
        exc = self.assertCode("E_PATH_RESOLUTION_FAILED", self.seal, "evidence/f.json/x.json", index=index,
                              expect_field="/path")
        self.assertEqual(exc.reason, "ancestor_not_directory")
        self.assertEqual(index.calls, [])
        self.assertEqual(self.listing(self.store / "evidence"), ["f.json"])
        self.assertEqual(blocker.read_bytes(), b"file\n")
        (self.store / "evidence" / "d").mkdir()
        ref = {"kind": "baseline-evidence", "id": "d-1", "sha256": sha(self.RAW), "path": "evidence/d"}
        exc = self.assertCode("E_RESOURCE_MISSING", S.read_sealed, self.store, ref, self.reg,
                              expect_field="/path")
        self.assertEqual(exc.reason, "not_regular_file")

    def test_A13_seal_failure_leaves_only_empty_new_parents(self):
        """4.2.8、8.4：P4 新增（第 2 轮复审 paths 视角，按“写明语义”处理）。发布之前失败（读回摘要不符、
        os.link 抛环境类 OSError）时不残留文件；本次按需新建的父目录不回滚——并发写入者可能正要使用同一目录，
        8.4 不允许在不确定时清理——但它们只会是空目录。白盒注入：替换 sealing 内部的 _read_all 与模块内的 os
        引用，用后恢复（黑盒无法制造读回不一致或 link 失败）。"""
        original = S._read_all

        def corrupting_read(p, path, phase):
            data = original(p, path, phase)
            if Path(path).name.startswith(".codekit-seal-"):
                return data[:-1] + bytes([data[-1] ^ 0x01])
            return data

        index = IndexRecorder(self.store)
        S._read_all = corrupting_read
        try:
            self.assertCode("E_RESOURCE_HASH_MISMATCH", self.seal, "newA/newB/x.json", index=index)
        finally:
            S._read_all = original
        self.assertEqual(sorted(p.relative_to(self.store).as_posix() for p in self.store.rglob("*")),
                         ["evidence", "newA", "newA/newB"])
        real_os = S.os

        class LinkFails:
            def __getattr__(self, name):
                return getattr(real_os, name)

            @staticmethod
            def link(src, dst):
                raise PermissionError("simulated: hard links not supported")

        S.os = LinkFails()
        try:
            with self.assertRaises(PermissionError):
                self.seal("newC/x.json", index=index)
        finally:
            S.os = real_os
        self.assertEqual(self.listing(self.store / "newC"), [])
        self.assertEqual(index.calls, [])
        self.assertIn("发布之前失败时可能残留本次新建的空父目录（不回滚，8.4）", S.SEALING_LIMITATIONS)

    def test_A13_read_sealed_roundtrip(self):
        """4.2.8：读取已封存资源一次并核验摘要，返回的正是核验过的字节。"""
        result, _ = self.seal()
        ref = sealed_ref(result)
        data = S.read_sealed(self.store, ref, self.reg)
        self.assertIs(type(data), bytes)
        self.assertEqual(data, self.RAW)
        self.assertEqual(sha(data), ref["sha256"])

    def test_A13_read_sealed_missing_and_tampered(self):
        """8.3：引用的文件不存在 → E_RESOURCE_MISSING；内容被改（含 LF→CRLF）→ E_RESOURCE_HASH_MISMATCH，
        期望摘要不被更新。"""
        result, _ = self.seal()
        ref = sealed_ref(result)
        missing = {**ref, "path": "evidence/absent.json"}
        self.assertCode("E_RESOURCE_MISSING", S.read_sealed, self.store, missing, self.reg)
        final = self.store / "evidence" / "sample-1.json"
        final.write_bytes(self.RAW.replace(b"\n", b"\r\n"))
        before = copy.deepcopy(ref)
        self.assertCode("E_RESOURCE_HASH_MISMATCH", S.read_sealed, self.store, ref, self.reg)
        self.assertUnchanged(before, ref)

    def test_A13_read_sealed_escape_and_invalid_ref(self):
        """4.1.6、4.2.1：引用路径经链接越出存储根 → E_PATH_ESCAPE（即使字节匹配）；引用形状非法先拒绝。"""
        self.make_dir_link(self.store / "escape", self.outside)
        (self.outside / "x.json").write_bytes(self.RAW)
        ref = {"kind": "baseline-evidence", "id": "x-1", "sha256": sha(self.RAW),
               "path": "escape/x.json"}
        self.assertCode("E_PATH_ESCAPE", S.read_sealed, self.store, ref, self.reg)
        bad = {**ref, "path": "evidence/x.json", "sha256": sha(self.RAW).upper()}
        self.assertCode("E_RESOURCE_FIELD", S.read_sealed, self.store, bad, self.reg)


# ===========================================================================
# 无副作用导入（4.4.3；01-F049，01-A14）
# ===========================================================================
CHILD_PROBE_PRELUDE = r'''
import json, os, sys

records = []
env_reads = []
active = [True]
PREFIXES = (
    "socket.", "subprocess.", "os.system", "os.exec", "os.spawn", "os.posix_spawn",
    "os.startfile", "os.fork", "os.forkpty", "os.remove", "os.unlink", "os.rename",
    "os.replace", "os.mkdir", "os.makedirs", "os.rmdir", "os.link", "os.symlink",
    "os.truncate", "os.chmod", "os.chown", "os.utime", "os.putenv", "os.unsetenv",
    "shutil.", "tempfile.", "urllib.", "http.client.", "ftplib.", "smtplib.",
)


def describe(path):
    if isinstance(path, str):
        return path
    if isinstance(path, bytes):
        return os.fsdecode(path)
    return "<%s>" % type(path).__name__


def hook(event, args):
    if not active[0]:
        return
    if event == "open":
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else None
        records.append({"event": "open", "path": describe(args[0] if args else None),
                        "mode": mode if isinstance(mode, str) else None,
                        "flags": flags if isinstance(flags, int) else None})
    elif event.startswith(PREFIXES):
        records.append({"event": event})


class RecordingEnviron:
    """记录读取的环境变量映射包装。读取环境变量没有审计事件，所以在导入前替换 os.environ
    （os.getenv 在调用时查 os 模块的全局 environ，也会被记录）；直接访问 nt/posix.environ 的写法
    另由源码 AST 检查覆盖。"""

    def __init__(self, real):
        self._real = real

    def _note(self, key):
        if active[0]:
            env_reads.append(str(key))

    def __getitem__(self, key):
        self._note(key)
        return self._real[key]

    def get(self, key, default=None):
        self._note(key)
        return self._real.get(key, default)

    def __contains__(self, key):
        self._note(key)
        return key in self._real

    def __iter__(self):
        self._note("<iter>")
        return iter(self._real)

    def __len__(self):
        self._note("<len>")
        return len(self._real)

    def keys(self):
        self._note("<keys>")
        return self._real.keys()

    def items(self):
        self._note("<items>")
        return self._real.items()

    def values(self):
        self._note("<values>")
        return self._real.values()

    def copy(self):
        self._note("<copy>")
        return self._real.copy()

    def __getattr__(self, name):
        self._note("<%s>" % name)
        return getattr(self._real, name)


os.environ = RecordingEnviron(os.environ)
if hasattr(os, "environb"):
    os.environb = RecordingEnviron(os.environb)
sys.addaudithook(hook)


def emit(extra):
    active[0] = False
    report = {"records": records, "env_reads": env_reads}
    report.update(extra)
    sys.stdout.write(json.dumps(report))
'''

CHILD_IMPORT_PAYLOAD = r'''
stages = {}
before = set(sys.modules)
sys.path.insert(0, sys.argv[1])
import codekit  # noqa
import codekit.protocols  # noqa
stages["protocols"] = sorted(set(sys.modules) - before)
import codekit.sealing  # noqa
stages["sealing"] = sorted(set(sys.modules) - before)
import codekit.baseline  # noqa
nonstd = {}
for stage, names in stages.items():
    tops = sorted({n.split(".")[0] for n in names} - set(sys.stdlib_module_names) - {"codekit"})
    nonstd[stage] = tops
emit({"nonstdlib": nonstd})
'''

# 反例载荷：在子进程的临时工作目录里故意做一次写模式 open、建目录、起进程与读环境变量，
# 用来证明同一套钩子与判定规则真能捕获这些违规（01-A14 的最小反例）。
CHILD_VIOLATION_PAYLOAD = r'''
import subprocess  # noqa
with open("written.txt", "w") as handle:
    handle.write("x")
os.mkdir("made-dir")
subprocess.run([sys.executable, "-c", "pass"], check=True)
os.environ.get("PATH")
os.getenv("CODEKIT_PROBE_UNSET")
emit({"nonstdlib": {}})
'''

CHILD_IMPORT_PROBE = CHILD_PROBE_PRELUDE + CHILD_IMPORT_PAYLOAD
ENV_ACCESS_NAMES = frozenset({"environ", "environb", "getenv", "getenvb", "putenv", "unsetenv"})


class ImportSideEffectTests(unittest.TestCase):
    ALLOWED_SUFFIXES = (".py", ".pyc", ".pyd")

    def _run_probe(self, script):
        with tempfile.TemporaryDirectory(prefix="codekit-import-") as td:
            proc = subprocess.run(
                [sys.executable, "-B", "-I", "-c", script, str(SCRIPTS_DIR)],
                cwd=td, env=minimal_child_env(), capture_output=True, timeout=120)
            self.assertEqual(proc.returncode, 0,
                             proc.stderr.decode("utf-8", "replace")[-2000:])
            leftovers = sorted(os.listdir(td))
        return json.loads(proc.stdout.decode("utf-8")), leftovers

    def _violations(self, report):
        write_flags = 0
        for name in ("O_WRONLY", "O_RDWR", "O_APPEND", "O_CREAT", "O_TRUNC", "O_EXCL"):
            write_flags |= getattr(os, name, 0)
        violations = []
        for rec in report["records"]:
            if rec["event"] != "open":
                violations.append(rec["event"])
                continue
            mode = rec.get("mode") or ""
            flags = rec.get("flags") or 0
            if any(c in mode for c in "wax+") or (flags & write_flags):
                violations.append(f"write-open {rec['path']}")
            if not rec["path"].lower().endswith(self.ALLOWED_SUFFIXES):
                violations.append(f"open non-module {rec['path']}")
        return violations

    def test_F049_import_has_no_side_effects(self):
        """01-F049 / 4.4.3、01-A14：在最小环境的子进程中导入 codekit、protocols、sealing、baseline，
        审计钩子不应看到网络、进程、删除/改名/建目录、写模式打开或打开 .py/.pyc/.pyd 以外的文件；
        protocols 与 sealing 只引入标准库模块。
        P2 返工（复审变异 M69）：导入前把 os.environ 换成记录读取的包装，断言导入期间没有读取任何
        环境变量（原先只能靠代码审阅）。"""
        report, leftovers = self._run_probe(CHILD_IMPORT_PROBE)
        self.assertEqual(leftovers, [], "导入不得在当前目录写文件")
        self.assertEqual(self._violations(report), [])
        self.assertEqual(report["env_reads"], [], "导入期间不得读取环境变量（01-A14）")
        self.assertEqual(report["nonstdlib"]["protocols"], [], "protocols 只能依赖标准库（01-L01）")
        self.assertEqual(report["nonstdlib"]["sealing"], [], "sealing 导入不应引入第三方依赖")

    def test_A14_probe_detects_violations(self):
        """01-A14 最小反例：P2 返工新增（复审 fidelity 视角）。用同一套钩子与判定规则运行一段故意违规的
        代码（写模式 open、os.mkdir、启动子进程、读环境变量），证明探针真能捕获违规，
        而不是因前缀表或 open 事件解析有误而静默通过。"""
        report, leftovers = self._run_probe(CHILD_PROBE_PRELUDE + CHILD_VIOLATION_PAYLOAD)
        self.assertEqual(leftovers, ["made-dir", "written.txt"])
        violations = self._violations(report)
        self.assertIn("write-open written.txt", violations)
        self.assertIn("open non-module written.txt", violations)
        self.assertIn("os.mkdir", violations)
        self.assertIn("subprocess.Popen", violations)
        self.assertIn("PATH", report["env_reads"])
        self.assertIn("CODEKIT_PROBE_UNSET", report["env_reads"])

    def test_A14_sources_do_not_touch_environment(self):
        """01-A14：P2 返工新增（复审变异 M69）。静态检查 protocols.py 与 sealing.py 的源码：任何位置
        都不出现 environ/environb/getenv/putenv/unsetenv 等名称（覆盖直接访问 nt/posix.environ 这类
        运行时包装拦不住的写法）。"""
        for name in ("protocols.py", "sealing.py"):
            source = (SCRIPTS_DIR / "codekit" / name).read_text(encoding="utf-8")
            found = set()
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, ast.Name) and node.id in ENV_ACCESS_NAMES:
                    found.add(node.id)
                elif isinstance(node, ast.Attribute) and node.attr in ENV_ACCESS_NAMES:
                    found.add(node.attr)
                elif isinstance(node, ast.alias) and node.name.split(".")[-1] in ENV_ACCESS_NAMES:
                    found.add(node.name)
            with self.subTest(module=name):
                self.assertEqual(found, set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
