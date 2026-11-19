"""T059 战前门禁：桌面端前端「日志页的检索在真实模式下走服务的 search 作业」的黑盒基准测试
（合同 t059-desktop-web-logs-search-job.v1，基线 492c643f67afae43ead09125172355b390fd7eb5）。

被测对象是 ``desktop/web/`` 前端与旧门禁的四处退役：

- ``src/pages/readonly2/common-readers.ts``：``searchLogs(q, task, max)`` 真实模式那一支（``liveClient()``
  不为 null 时）不再回「ERROR: 检索尚未接通」，改成：``postRaw('/api/v1/jobs', body, 15)`` 建
  ``kind: 'search'`` 作业（正文键恰好 ``{ kind, pattern, max }``，task 不为 null 才加 ``task`` 键，
  max 传数字）；201 之后 1000 毫秒起每 1000 毫秒 ``getRaw('/api/v1/jobs/<id>', undefined, 15)`` 查一次
  （setTimeout 链、id 用 ``encodeURIComponent(String(id))`` 编码、不设次数上限），作业 ``state`` 到
  ``succeeded`` / ``failed`` / ``cancelled`` / ``timed_out`` 后停：``envelope`` 是合法七字段信封就原样
  交回，为 null 或不合法就交固定文案的报错信封（已取消 / 超时 / 失败 / 没有交回结果四句逐字）；
  建作业非 201、查询非 200（含 503、401、404）立即交报错信封并停（messages 取回应信封的 messages，
  正文不是信封时是「ERROR: 服务返回 HTTP <状态码>」）；``postRaw`` / ``getRaw`` reject 时
  ``searchLogs`` 跟着 reject。全程不取消、不调 ``client.get``；``isEnvelope`` 从
  ``'../../live/transport'`` 运行时引入；夹具分支与七个 helper 逐字不动；导出仍是三个、对
  ``../../api`` 只许 import type。
- ``tests/live-readers.test.ts``：真实模式的用例换成真检索（假客户端写全四个方法、假计时器用
  ``advanceTimersByTimeAsync`` 推进），记号 ``searchLogs``、``/api/v1/jobs``、``夹具里没有这份数据``
  都在，夹具那一个 describe 原样保留，不许 skip/only/todo。
- ``tests/test_gate_t027_baseline.py``：四处按合同逐处退役（:111 换记号、S07 删一行与 docstring
  半句、s33 整条退役、PROBE_UNWIRED 整份退役且 SPECS/ORDER 去掉 "unwired"），退役注记写
  「（站主 2026-11-19 为 T059 退役）」。

基线（492c643f）上 common-readers.ts 的真实分支还是固定信封「ERROR: 检索尚未接通」，所以失败都落在
断言上（静态 S01–S04；流水线在候选里还没有 T059 的标记——common-readers.ts 运行时引入 isEnvelope——
时不起 npm，P/D 用例以「流水线未运行」的断言失败），不是收集失败：模块级只导入标准库，仓库文件的
读取都发生在用例函数里；流水线（npm、Vitest、探针）放在 ``pipeline`` 会话级夹具里（全量 pytest 默认
跳过，点名运行本文件才跑；照 T049/T057/T058 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线）：common-readers.ts 的真实分支写法与禁字（S01）、夹具分支与
  helper 逐字保留（S02）；live-readers.test.ts 的记号、假计时器与禁 skip/only/todo（S03）；
  t027 门禁四处退役逐处核对（S04）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、
  ``npm test`` 全绿（含执行端改写的 live-readers.test.ts，旧断言没改掉会在这里红）；探针
  ``gate-probe/probe-<uid>-t059-search.test.ts`` 注入写全四个方法的假客户端，直接调 ``searchLogs``
  钉行为（D01–D05）：建作业正文/时限、1000 毫秒轮询节奏与计时器归零、终态信封原样交回、四句固定
  文案、建作业/查询各档非 2xx 的报错信封与立即停、reject 往外抛、全程没有取消与 ``client.get``。

门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：见文件末尾 ``ASSUMPTIONS``。
"""

import hashlib
import os
import re
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB = REPO_ROOT / "desktop" / "web"

READERS_REL = "desktop/web/src/pages/readonly2/common-readers.ts"
READERS_TEST_REL = "desktop/web/tests/live-readers.test.ts"
T027_GATE_REL = "tests/test_gate_t027_baseline.py"

# 合同写死的四句固定文案（D03，逐字）
MSG_CANCELLED = "ERROR: 检索作业已取消"
MSG_TIMED_OUT = "ERROR: 检索作业超时"
MSG_FAILED = "ERROR: 检索作业失败"
MSG_NO_RESULT = "ERROR: 检索作业没有交回结果"
# 合同写死的轮询节奏与请求路径
POLL_MS = "1000"
JOBS_PATH = "/api/v1/jobs"
QUERY_PREFIX = "/api/v1/jobs/"
REQUEST_TIMEOUT = 15
SEARCH_PATTERN = "logs[_ ]cat"

# 合同「写法钉死」的 isEnvelope 运行时引入（照 api.ts:46 的先例；不是 import type）
ISENVELOPE_IMPORT_RE = re.compile(
    r"import\s*\{\s*isEnvelope\s*\}\s*from\s+['\"]\.\./\.\./live/transport['\"]\s*;")
# 转出语句（逐字保留）
REEXPORT_RE = re.compile(
    r"""export\s*\{\s*getHistoryEntry\s*,\s*getPlugin\s*\}\s*from\s+['"]\.\./\.\./api['"]\s*;""")
# 对 ../../api 只许 import type（T010/T027/readonly2-static 三处同一口径）
API_RUNTIME_IMPORT_RE = re.compile(r"import\s+([^;]*?)\s+from\s+['\"](?:\.\./)+api['\"]")

# 禁字（合同 D06：全文原文扫，注释与字符串都算）——与 T010/T023 同一张表
NETWORK_RE = re.compile(r"\b(?:fetch|XMLHttpRequest|EventSource|WebSocket)\b")
HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])")
COLOR_FUNC_RE = re.compile(r"\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(", re.I)
FORBIDDEN_WORDS = ("dangerouslySetInnerHTML", "innerHTML", "outerHTML", "insertAdjacentHTML", "eval(",
                   "new Function", "document.write", "srcdoc", "createContextualFragment", "DOMParser")
FORBIDDEN_CALLS = ("matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver")
BAD_ENTRY_FRAGMENTS = ("删除方案", "删除 profile", "删除运行时", "回滚配置", "已删除", "已回滚",
                       "先改这些绑定或方案", "先改或删这些 profile", "config unset active_preset")

# 夹具分支与七个 helper 里逐字保留的记号（合同 D06：一个字不改）
FIXTURE_KEEP_MARKS = (
    "const ERROR_MESSAGE = 'ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied';",
    "function clone<T>(value: T): T {",
    "function okEnvelope<T>(command: string[], data: T): Envelope<T> {",
    "function missingEnvelope(command: string[], detail: string): Envelope<never> {",
    "function errorEnvelope<T>(command: string[]): Envelope<T> {",
    "function pending<T>(): Promise<Envelope<T>> {",
    "function read<T>(command: string[], produce: (mode: MockMode) => Envelope<T>): Promise<Envelope<T>> {",
    "function searchCommand(q: string, task: string | null, max: number): string[] {",
    "if (q !== SEARCH_PATTERN) return missingEnvelope(command, q);",
    "const matches = filtered.slice(0, Math.max(0, max));",
    "read(command, (mode) => {",
    "return okEnvelope(command, { matches: [], truncated: false, skipped_links: 0, skipped_large: 0 });",
)

# 执行端改写的 live-readers.test.ts 里应出现的记号（合同 D07 与 t027 :111 改后的口径）
EXECUTOR_TEST_TOKENS = (
    "searchLogs", JOBS_PATH, "夹具里没有这份数据",
    "setLiveClientForTests", "postRaw", "getRaw",
    "useFakeTimers", "advanceTimersByTimeAsync", "getTimerCount",
    MSG_CANCELLED, MSG_TIMED_OUT, MSG_NO_RESULT, "ERROR: 没有这个作业",
)

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T049/T057/T058 门禁），用完就停下并在断言里写明。
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 120}

ASSUMPTIONS = (
    "静态只钉合同「写法钉死」的那几处：isEnvelope 的运行时引入与分号、转出语句与它前一条语句的分号、"
    "setTimeout 链与 1000、encodeURIComponent(String(、四个终态字面量与四句固定文案；body 怎么拼、"
    "helper 怎么排不钉，行为由探针钉（时限 15、正文恰好几个键、轮询节奏都从假客户端的记录里读）",
    "「不调 client.get、不发取消」不做成静态断言（实现里局部变量名不保证叫 client），由探针的假客户端"
    "记数钉死：全程 get 调用数为 0、post 调用数为 0",
    "t027 的退役核对不逐字钉整段 docstring（:48-49 与 :60 的新行里带着 SSE 片将来会改的 p7 提法），"
    "只钉：旧断言/常量/函数确实没了、:111 新记号行逐字在、PROBE_ORDER 那一行里没有 unwired、"
    "s33 那条 docstring 的退役注记在、「为 T059 退役」出现至少 3 次",
    "探针直接调 searchLogs、注入写全四个方法的假客户端（不挂整页）：本片的行为都在这一个函数里，"
    "SearchPanel 的 .catch 与 reqRef 不在本片改动范围，界面行为由既有包内测试覆盖",
    "流水线预算 580 秒（G01 的 600 秒减去静态用例与 pytest 自身开销）：候选里 common-readers.ts 还没"
    "运行时引入 isEnvelope 时不起 npm（基线上必然没有）；node_modules 已在（执行端 Setup 装过）就重装跳过",
)


# ---------------------------------------------------------------------------
# 通用小工具（只读仓库文件；模块级不做任何仓库 IO）
# ---------------------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def read_rel(rel):
    return _read(REPO_ROOT / rel)


def need_file(rel):
    """断言仓库里的文件存在，返回相对路径。基线上到这里就以断言失败。"""
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return rel


def file_digest(path):
    path = Path(path)
    if not path.is_file():
        return None
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return len(data), hashlib.sha256(data).hexdigest()


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:40])


def tail_text(text, max_chars=3500, max_lines=45):
    text = _ANSI.sub("", text)
    lines = text.splitlines()[-max_lines:]
    joined = "\n".join(lines)
    return joined[-max_chars:]


def network_hint(text):
    if re.search(r"ENOTFOUND|ETIMEDOUT|ECONNRESET|ECONNREFUSED|EAI_AGAIN|ENETUNREACH|network|socket hang up|E40[134]|E50\d",
                 text, re.I):
        return "（输出里有网络或 registry 错误的迹象，多半是网络故障，不是代码问题）"
    return ""


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043/T049/T058 的同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def _no_skip_marks(text):
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
        if re.search(bad, text):
            problems.append(f"出现 {bad}（不许 skip、only、todo）")
    return problems


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_common_readers_real_branch():
    """S01 / D01–D05：common-readers.ts 的真实分支换成建 search 作业 + 1000 毫秒轮询——
    isEnvelope 从 ../../live/transport 运行时引入（以分号结尾）；postRaw/getRaw、/api/v1/jobs、
    encodeURIComponent(String(、setTimeout 链（不用 setInterval）、1000、四个终态与四句固定文案
    都在；「检索尚未接通」与「还没接通」没了；导出仍只有三个；对 ../../api 只许 import type；
    全文避开禁字（网络整词、FORBIDDEN_WORDS/CALLS、井号十六进制、颜色函数、BAD_ENTRY_FRAGMENTS）。"""
    need_file(READERS_REL)
    text = read_rel(READERS_REL)
    code = strip_ts_comments(text)
    problems = []
    # 旧文案与旧注释没了（文件头注释与真实分支注释都改写）
    for needle, why in (
        ("ERROR: 检索尚未接通", "真实模式不再回「ERROR: 检索尚未接通」"),
        ("还没接通", "文件头注释与真实分支注释不再说「还没接通」"),
    ):
        if needle in text:
            problems.append(why)
    # isEnvelope 运行时引入（照 api.ts:46 的先例；正则不匹配 import type）
    if not ISENVELOPE_IMPORT_RE.search(text):
        problems.append("应有运行时引入 import { isEnvelope } from '../../live/transport';（以分号结尾）")
    if not re.search(r"\bisEnvelope\s*\(", code):
        problems.append("代码里应调用 isEnvelope( 判终态信封")
    # 建作业、查询与路径拼接
    for needle, why in (
        ("postRaw", "真实分支应经 client.postRaw 建作业"),
        ("getRaw", "轮询应经 client.getRaw 查作业"),
        (JOBS_PATH, "应有路径 /api/v1/jobs（建作业与查询共用的前缀）"),
        ("encodeURIComponent(String(", "查询路径应按 encodeURIComponent(String(id)) 拼接（合同写法钉死）"),
    ):
        if needle not in code:
            problems.append(f"{why}：找不到 {needle}")
    # 轮询节奏：setTimeout 链，不用 setInterval
    if "setTimeout" not in code:
        problems.append("轮询应是 setTimeout 链")
    if re.search(r"\bsetInterval\b", code):
        problems.append("轮询不应使用 setInterval")
    if POLL_MS not in code:
        problems.append("轮询间隔应是 1000 毫秒（照 jobStore 的节奏）")
    # 四个终态与四句固定文案
    for state in ("succeeded", "failed", "cancelled", "timed_out"):
        if state not in code:
            problems.append(f"终态判定应覆盖 {state}")
    for msg in (MSG_CANCELLED, MSG_TIMED_OUT, MSG_FAILED, MSG_NO_RESULT):
        if msg not in code:
            problems.append(f"固定报错文案应包含「{msg}」（逐字）")
    # 导出仍是三个：转出语句 + export function searchLogs，此外不许有别的 export
    exports = [ln.strip() for ln in re.findall(r"^export[^\n]*", code, re.M)]
    if len(exports) != 2:
        problems.append(f"模块应仍只有两个 export 语句（转出 + searchLogs），实际 {len(exports)} 个：{exports}")
    else:
        if not REEXPORT_RE.fullmatch(exports[0]):
            problems.append(f"转出语句应逐字是 export {{ getHistoryEntry, getPlugin }} from '../../api';：{exports[0]}")
        if not exports[1].startswith("export function searchLogs("):
            problems.append(f"另一个导出应仍是 export function searchLogs(：{exports[1]}")
    # 转出语句的前一条语句以分号结尾（T010 的正则会一路匹配到下一个分号为止）
    cm = REEXPORT_RE.search(code)
    if cm is None:
        problems.append("找不到转出语句")
    else:
        before = code[:cm.start()].rstrip()
        if before and not before.endswith(";"):
            problems.append("转出语句的前一条语句应以分号结尾")
    # 对 ../../api 只许 import type
    for m in API_RUNTIME_IMPORT_RE.finditer(code):
        if not m.group(1).strip().startswith("type "):
            problems.append(f"对 ../../api 只许 import type（T010/T027/readonly2-static 的口径）：{m.group(0)}")
    # 禁字按全文原文扫（注释与字符串都算）
    for m in NETWORK_RE.finditer(text):
        problems.append(f"出现网络整词 {m.group(0)}（四个整词都不许出现）")
    for frag in FORBIDDEN_WORDS:
        if frag in text:
            problems.append(f"出现 FORBIDDEN_WORDS 里的「{frag}」")
    for frag in FORBIDDEN_CALLS:
        if frag in text:
            problems.append(f"出现 FORBIDDEN_CALLS 里的「{frag}」")
    for m in HEX_RE.finditer(text):
        problems.append(f"出现井号十六进制 {m.group(0)}（注释里写也不行）")
    for m in COLOR_FUNC_RE.finditer(text):
        problems.append(f"出现颜色函数名加括号 {m.group(0)}")
    for frag in BAD_ENTRY_FRAGMENTS:
        if frag in text:
            problems.append(f"出现 BAD_ENTRY_FRAGMENTS 里的「{frag}」")
    fail_if(problems, "common-readers.ts 的真实分支（S01）")


def test_s02_common_readers_fixture_branch_kept():
    """S02 / D06：夹具模式那一支逐字不动——ERROR_MESSAGE 的原句、clone/okEnvelope/missingEnvelope/
    errorEnvelope/pending/read/searchCommand 七个 helper 的签名、夹具分支的报缺与截断写法都照旧；
    SEARCH_PATTERN/SEARCH_FIXTURE 的接线还在。"""
    need_file(READERS_REL)
    text = read_rel(READERS_REL)
    code = strip_ts_comments(text)
    problems = [f"夹具分支应保留记号（逐字）：{mark}" for mark in FIXTURE_KEEP_MARKS if mark not in code]
    for needle in ("SEARCH_PATTERN", "SEARCH_FIXTURE", "currentMock"):
        if needle not in code:
            problems.append(f"夹具分支的接线应保留 {needle}")
    fail_if(problems, "common-readers.ts 的夹具分支逐字保留（S02）")


def test_s03_live_readers_test_updated():
    """S03 / D07：live-readers.test.ts 的真实模式用例换成真检索——记号（searchLogs、/api/v1/jobs、
    夹具里没有这份数据，与 t027 :111 改后的三项一致）、假客户端写全四个方法（postRaw/getRaw 在）、
    假计时器（useFakeTimers/advanceTimersByTimeAsync/getTimerCount）、四句固定文案里的三句与
    「ERROR: 没有这个作业」、旧文案「检索尚未接通」没了、夹具那一个 describe 还在
    （getHistoryEntry 记号）、没有 skip/only/todo。"""
    need_file(READERS_TEST_REL)
    fresh = read_rel(READERS_TEST_REL)
    problems = [f"live-readers.test.ts 应覆盖记号 {token}" for token in EXECUTOR_TEST_TOKENS if token not in fresh]
    if "检索尚未接通" in fresh:
        problems.append("live-readers.test.ts 不应再出现「检索尚未接通」（真实模式用例整块换掉）")
    if "getHistoryEntry" not in fresh:
        problems.append("夹具那一个 describe（getHistoryEntry/getPlugin 夹具分支逐字一致）应原样保留")
    problems += _no_skip_marks(strip_ts_comments(fresh))
    fail_if(problems, "执行端真检索测试（S03）")


def test_s04_t027_gate_retired_four_places():
    """S04 / D08：t027 门禁四处逐处退役——:111 的记号换成三项（searchLogs、/api/v1/jobs、
    夹具里没有这份数据），旧的「检索尚未接通」记号项没了；S07 那一行断言与 docstring 半句删掉；
    test_transitional_s33_searchlogs_unwired_message 与 test_transitional_p6_probe_unwired 两条
    整条删掉；PROBE_UNWIRED 常量与 SPECS/ORDER 里的 "unwired" 没了（ORDER 仍按合同留着 tasks，
    SSE 片退役时再改）；退役注记「（站主 2026-11-19 为 T059 退役）」至少三处。"""
    need_file(T027_GATE_REL)
    gate = read_rel(T027_GATE_REL)
    problems = []
    # 第 1 处：:111 的记号三项
    new_token = '"live-readers.test.ts": ("searchLogs", "/api/v1/jobs", "夹具里没有这份数据"),'
    if new_token not in gate:
        problems.append(f":111 应换成 {new_token}")
    if '("searchLogs", "检索尚未接通"' in gate:
        problems.append(":111 旧的「检索尚未接通」记号项应去掉")
    # 第 2 处：S07 删 :433 那一行与 docstring 半句
    if 'assert "ERROR: 检索尚未接通"' in gate:
        problems.append("S07 里断言「ERROR: 检索尚未接通」在的那一行应删掉")
    if "、searchLogs 保留并回「检索尚未接通」" in gate:
        problems.append("S07 的 docstring 里「、searchLogs 保留并回「检索尚未接通」」半句应删掉")
    # 第 3 处：s33 整条退役
    if re.search(r"^def test_transitional_s33_", gate, re.M):
        problems.append("test_transitional_s33_searchlogs_unwired_message 应整条删掉")
    if "作业/检索片推翻（站主 2026-11-19 为 T059 退役）" not in gate:
        problems.append("模块 docstring 里 s33 那条应改成「……作业/检索片推翻（站主 2026-11-19 为 T059 退役）。」")
    # 第 4 处：探针整份退役
    if "PROBE_UNWIRED" in gate:
        problems.append("PROBE_UNWIRED 常量（连同它前面的空行）应整份删掉")
    if re.search(r"['\"]unwired['\"]\s*:", gate):
        problems.append("PROBE_SPECS 里的 \"unwired\" 那一项应删掉")
    m = re.search(r"^PROBE_ORDER\s*=\s*\(([^)]*)\)", gate, re.M)
    if m is None:
        problems.append("应仍有 PROBE_ORDER = (…) 一行")
    elif "unwired" in m.group(1):
        problems.append("PROBE_ORDER 里应去掉 \"unwired\"")
    if re.search(r"^def test_transitional_p6_probe_unwired", gate, re.M):
        problems.append("test_transitional_p6_probe_unwired 应整条删掉")
    # 退役注记的写法（照 :55/:57 已退役条目的先例）
    if gate.count("为 T059 退役") < 3:
        problems.append("退役注记「（站主 2026-11-19 为 T059 退役）」应至少出现 3 次（docstring 三处）")
    fail_if(problems, "t027 门禁四处退役（S04）")


# ---------------------------------------------------------------------------
# 探针源码（自包含：辅助函数不跨文件共享；不挂整页，直接调 searchLogs + 注入假客户端）
# ---------------------------------------------------------------------------

PROBE_SEARCH = r"""// T059 门禁探针：searchLogs 真实模式走服务的 search 作业（不挂整页，直接调函数）。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { searchLogs } from '../src/pages/readonly2/common-readers';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

interface RawReply {
  status: number;
  body: unknown;
}
interface Script {
  create?: RawReply | Error;
  polls?: Array<RawReply | Error>;
}

const log = {
  post: 0,
  get: 0,
  postRaw: [] as Array<{ path: string; body: unknown; timeout?: number }>,
  getRaw: [] as Array<{ path: string; query?: unknown; timeout?: number }>,
};

function envelopeOf(messages: string[]): unknown {
  return { ok: false, exit_code: null, data: null, output: [], messages, command: [], elapsed_ms: 0 };
}

function jobOf(state: string, envelope: unknown, id = 'j1'): unknown {
  return { id, kind: 'search', state, reason: null, created_ms: 1, started_ms: null, finished_ms: null, envelope };
}

function inject(script: Script): void {
  const client = {
    get() {
      log.get += 1;
      return Promise.reject(new Error('client.get 不应被调用'));
    },
    post() {
      log.post += 1;
      return Promise.reject(new Error('client.post 不应被调用'));
    },
    postRaw(path: string, body: unknown, timeoutSeconds?: number) {
      log.postRaw.push({ path, body, timeout: timeoutSeconds });
      const reply = script.create;
      if (reply instanceof Error) return Promise.reject(reply);
      return Promise.resolve(reply);
    },
    getRaw(path: string, query?: unknown, timeoutSeconds?: number) {
      log.getRaw.push({ path, query, timeout: timeoutSeconds });
      const queue = script.polls || [];
      const next = queue.length > 0 ? queue.shift() : undefined;
      if (next instanceof Error) return Promise.reject(next);
      if (!next) return Promise.reject(new Error('脚本里没有更多的查询回应'));
      return Promise.resolve(next);
    },
  };
  setLiveClientForTests(client as unknown as LiveClient);
}

async function drain(): Promise<void> {
  for (let i = 0; i < 12; i += 1) await Promise.resolve();
}

beforeEach(() => {
  log.post = 0;
  log.get = 0;
  log.postRaw = [];
  log.getRaw = [];
  vi.useFakeTimers();
});

afterEach(() => {
  setLiveClientForTests(undefined);
  vi.useRealTimers();
});

describe('T059 searchLogs 真实模式：建作业与轮询节奏', () => {
  it('带 task 与 max：正文恰好四键、时限 15；201 之后 1000 毫秒首查（999 毫秒时不查）；queued→running→succeeded；原样交回信封；终态后计时器归零；全程没有取消、没有 client.get', async () => {
    const kernel = {
      ok: true,
      exit_code: 0,
      data: { matches: [], truncated: false, skipped_links: 0, skipped_large: 0 },
      output: [],
      messages: [],
      command: ['logs', 'search', 'logs[_ ]cat', '--task', 't1', '--max', '5'],
      elapsed_ms: 33,
    };
    inject({
      create: { status: 201, body: jobOf('queued', null) },
      polls: [
        { status: 200, body: jobOf('queued', null) },
        { status: 200, body: jobOf('running', null) },
        { status: 200, body: jobOf('succeeded', kernel) },
      ],
    });
    const pending = searchLogs('logs[_ ]cat', 't1', 5);
    await drain();
    expect(log.postRaw.length).toBe(1);
    expect(log.postRaw[0]).toEqual({
      path: '/api/v1/jobs',
      body: { kind: 'search', pattern: 'logs[_ ]cat', max: 5, task: 't1' },
      timeout: 15,
    });
    expect(log.getRaw.length, '201 之后、到 1000 毫秒之前不应查询').toBe(0);
    expect(vi.getTimerCount(), '首次查询应排在 201 之后 1000 毫秒').toBe(1);
    await vi.advanceTimersByTimeAsync(999);
    expect(log.getRaw.length, '999 毫秒时还没有到首查时刻').toBe(0);
    await vi.advanceTimersByTimeAsync(1);
    expect(log.getRaw.length).toBe(1);
    expect(log.getRaw[0]).toEqual({ path: '/api/v1/jobs/j1', query: undefined, timeout: 15 });
    expect(vi.getTimerCount(), 'queued 不是终态，应再排一次 1000 毫秒').toBe(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(log.getRaw.length, 'running 也不是终态，继续查').toBe(2);
    expect(vi.getTimerCount()).toBe(1);
    await vi.advanceTimersByTimeAsync(1000);
    expect(log.getRaw.length).toBe(3);
    const env = await pending;
    expect(env, 'succeeded 且信封合法：原样交回作业的信封').toEqual(kernel);
    expect(vi.getTimerCount(), '终态之后不再排计时器').toBe(0);
    expect(log.post, '全程没有 client.post（不取消）').toBe(0);
    expect(log.get, '全程没有 client.get').toBe(0);
  });

  it('task 为 null：正文恰好三键、没有 task 键；轮询与交回照常', async () => {
    const kernel = {
      ok: true,
      exit_code: 0,
      data: { matches: [], truncated: false, skipped_links: 0, skipped_large: 0 },
      output: [],
      messages: [],
      command: ['logs', 'search', 'q1', '--max', '3'],
      elapsed_ms: 7,
    };
    inject({
      create: { status: 201, body: jobOf('running', null, 'zz 9') },
      polls: [{ status: 200, body: jobOf('succeeded', kernel, 'zz 9') }],
    });
    const pending = searchLogs('q1', null, 3);
    await drain();
    expect(log.postRaw[0]).toEqual({
      path: '/api/v1/jobs',
      body: { kind: 'search', pattern: 'q1', max: 3 },
      timeout: 15,
    });
    await vi.advanceTimersByTimeAsync(1000);
    const env = await pending;
    expect(env).toEqual(kernel);
    expect(log.getRaw[0].path, 'id 应经 encodeURIComponent 编码（空格变 %20）').toBe('/api/v1/jobs/zz%209');
  });
});

describe('T059 searchLogs 真实模式：终态交回', () => {
  it('failed 且信封合法：原样交回内核信封（不拷贝、不改字段）', async () => {
    const kernel = {
      ok: false,
      exit_code: 1,
      data: null,
      output: ['boom'],
      messages: ['ERROR: 检索失败'],
      command: ['logs', 'search', 'q1', '--max', '3'],
      elapsed_ms: 9,
    };
    inject({
      create: { status: 201, body: jobOf('running', null) },
      polls: [{ status: 200, body: jobOf('failed', kernel) }],
    });
    const pending = searchLogs('q1', null, 3);
    await drain();
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toEqual(kernel);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('cancelled 且 envelope 为 null：整个固定信封逐字（command 是 searchCommand 的数组）', async () => {
    inject({
      create: { status: 201, body: jobOf('queued', null) },
      polls: [{ status: 200, body: jobOf('cancelled', null) }],
    });
    const pending = searchLogs('logs[_ ]cat', 't1', 5);
    await drain();
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toEqual({
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 检索作业已取消'],
      command: ['logs', 'search', 'logs[_ ]cat', '--task', 't1', '--max', '5'],
      elapsed_ms: 0,
    });
    expect(vi.getTimerCount()).toBe(0);
  });

  it('timed_out 且 envelope 为 null：固定信封「ERROR: 检索作业超时」', async () => {
    inject({
      create: { status: 201, body: jobOf('running', null) },
      polls: [{ status: 200, body: jobOf('timed_out', null) }],
    });
    const pending = searchLogs('q1', null, 3);
    await drain();
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toEqual({
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 检索作业超时'],
      command: ['logs', 'search', 'q1', '--max', '3'],
      elapsed_ms: 0,
    });
  });

  it('succeeded 但 envelope 不合法：固定信封「ERROR: 检索作业没有交回结果」', async () => {
    inject({
      create: { status: 201, body: jobOf('running', null) },
      polls: [{ status: 200, body: jobOf('succeeded', { ok: 1 }) }],
    });
    const pending = searchLogs('q1', null, 3);
    await drain();
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toEqual({
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 检索作业没有交回结果'],
      command: ['logs', 'search', 'q1', '--max', '3'],
      elapsed_ms: 0,
    });
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe('T059 searchLogs 真实模式：错误与断线', () => {
  it('建作业回 400（正文是信封）：messages 取服务那句，没有查询、没有计时器', async () => {
    inject({ create: { status: 400, body: envelopeOf(['ERROR: task 不合法']) } });
    const env = await searchLogs('q1', 't9', 5);
    expect(env).toEqual({
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: task 不合法'],
      command: ['logs', 'search', 'q1', '--task', 't9', '--max', '5'],
      elapsed_ms: 0,
    });
    expect(log.getRaw.length, '建作业不是 201 就不该有查询').toBe(0);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('建作业回 503（正文是信封）：同上，messages 取回应信封的 messages', async () => {
    inject({ create: { status: 503, body: envelopeOf(['ERROR: 服务繁忙（排队过长），请 4 秒后重试']) } });
    const env = await searchLogs('q1', null, 3);
    expect(env.ok).toBe(false);
    expect(env.messages).toEqual(['ERROR: 服务繁忙（排队过长），请 4 秒后重试']);
    expect(env.command).toEqual(['logs', 'search', 'q1', '--max', '3']);
    expect(env.elapsed_ms).toBe(0);
    expect(log.getRaw.length).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('建作业回 500（正文不是信封）：messages 是「ERROR: 服务返回 HTTP 500」', async () => {
    inject({ create: { status: 500, body: { note: 'boom' } } });
    const env = await searchLogs('q1', 't1', 5);
    expect(env).toEqual({
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 服务返回 HTTP 500'],
      command: ['logs', 'search', 'q1', '--task', 't1', '--max', '5'],
      elapsed_ms: 0,
    });
    expect(log.getRaw.length).toBe(0);
  });

  it('查询回 404：报错信封带「ERROR: 没有这个作业」，之后不再查（再推进时间也没有新查询）', async () => {
    inject({
      create: { status: 201, body: jobOf('queued', null) },
      polls: [{ status: 404, body: envelopeOf(['ERROR: 没有这个作业']) }],
    });
    const pending = searchLogs('q1', null, 3);
    await drain();
    await vi.advanceTimersByTimeAsync(1000);
    expect(await pending).toEqual({
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 没有这个作业'],
      command: ['logs', 'search', 'q1', '--max', '3'],
      elapsed_ms: 0,
    });
    await vi.advanceTimersByTimeAsync(5000);
    expect(log.getRaw.length, '查询不是 200 就立即停，不再查').toBe(1);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('getRaw reject：searchLogs 跟着 reject，不留计时器、不再排下一次查询', async () => {
    inject({
      create: { status: 201, body: jobOf('queued', null) },
      polls: [new Error('查询断线')],
    });
    const pending = searchLogs('q1', null, 3);
    const assertion = expect(pending).rejects.toThrow('查询断线');
    await drain();
    await vi.advanceTimersByTimeAsync(1000);
    await assertion;
    expect(vi.getTimerCount()).toBe(0);
    await vi.advanceTimersByTimeAsync(5000);
    expect(log.getRaw.length).toBe(1);
  });

  it('postRaw reject：searchLogs 跟着 reject（不重试、不吞、不发查询）', async () => {
    inject({ create: new Error('建作业断线') });
    await expect(searchLogs('q1', null, 3)).rejects.toThrow('建作业断线');
    expect(log.getRaw.length).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
  });
});
"""

PROBE_SPECS = {
    "search": PROBE_SEARCH,
}
PROBE_ORDER = ("search",)


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 t049/t057/t058 门禁的写法）
# ---------------------------------------------------------------------------

class Step:
    def __init__(self, name, argv, code, timed_out, out, seconds):
        self.name = name
        self.argv = argv
        self.code = code
        self.timed_out = timed_out
        self.out = _ANSI.sub("", out)
        self.seconds = seconds

    @property
    def tail(self):
        return tail_text(self.out)


class Pipeline:
    def __init__(self):
        self.ran = False
        self.reason = ""
        self.steps = {}
        self.status_before = None
        self.status_after = None
        self.digests_before = {}
        self.digests_after = {}
        self.stopped_reason = ""
        self.probe_files = {}
        self.probe_skipped = {}
        self.gate_probe_left = None


def _kill_tree(proc):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=60)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        proc.kill()


def run_capture(argv, cwd, timeout, env):
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    start = time.monotonic()
    proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode, False, out.decode("utf-8", "replace"), time.monotonic() - start
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, _ = proc.communicate(timeout=30)
        except Exception:
            out = b""
        return None, True, out.decode("utf-8", "replace"), time.monotonic() - start


def _make_env():
    env = dict(os.environ)
    env.update({
        "CI": "true",
        "NO_COLOR": "1",
        "npm_config_fund": "false",
        "npm_config_audit": "false",
        "npm_config_update_notifier": "false",
    })
    env.pop("FORCE_COLOR", None)
    # 这台机器上线用的 QUIZS_* 不进 vitest 子进程（与 tests/conftest.py 的 no_ambient_quizs 同一口径）。
    for name in ("QUIZS_CMD", "QUIZS_LIVE_PLAN", "QUIZS_PROVIDER_PROFILE", "QUIZS_QUALIFICATION"):
        env.pop(name, None)
    return env


def git_status_set():
    proc = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
                          cwd=REPO_ROOT, capture_output=True, timeout=120)
    assert proc.returncode == 0, f"git status 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


def t059_marker_present():
    """候选里是否已有 T059 的标记（common-readers.ts 运行时引入 isEnvelope）：没有就不起 npm。
    正则与 S01 同款：import type 不算（合同要求运行时引入）。"""
    path = REPO_ROOT / READERS_REL
    if not path.is_file():
        return False
    return ISENVELOPE_IMPORT_RE.search(_read(path)) is not None


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"desktop/web/package.json 不存在，未调用 npm"
        return pipe
    if not t059_marker_present():
        pipe.reason = ("候选里还没有 T059 的标记（common-readers.ts 运行时引入 isEnvelope），"
                       "没有东西可测，未调用 npm；执行端把真实分支换成建 search 作业之后，"
                       "流水线才会运行 npm ci、Vitest 与探针")
        return pipe
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        pipe.reason = f"找不到 npm 或 node（shutil.which：npm={npm}，node={node})"
        return pipe
    pipe.ran = True
    env = _make_env()
    deadline = time.monotonic() + PIPELINE_BUDGET
    pipe.status_before = git_status_set()
    pipe.digests_before = {name: file_digest(WEB / name) for name in WATCHED}

    def run_step(name, argv, label=None):
        remaining = deadline - time.monotonic()
        if remaining <= 5:
            pipe.stopped_reason = f"{label or name} 之前整体预算 {PIPELINE_BUDGET}s 已用完，未运行"
            return None
        timeout = min(STEP_CAPS[name], remaining)
        code, timed_out, out, seconds = run_capture(argv, WEB, timeout, env)
        step = Step(label or name, argv, code, timed_out, out, seconds)
        pipe.steps[label or name] = step
        return step

    probe_dir = WEB / "gate-probe"
    written = []
    try:
        # 依赖已在（执行端 Setup 装过）就不重装：省下的时间留给 Vitest 与探针。
        if (WEB / "node_modules" / "vitest").is_dir():
            pipe.steps["npm ci"] = Step("npm ci", [], 0, False, "node_modules 已在，未重装依赖", 0.0)
        else:
            ci = run_step("npm ci", [npm, "ci"])
            if ci is not None and ci.code != 0:
                run_step("npm ci --offline", [npm, "ci", "--offline"])
        ci_ok = any(pipe.steps.get(k) is not None and pipe.steps[k].code == 0
                    for k in ("npm ci", "npm ci --offline"))
        if ci_ok:
            run_step("npm test", [npm, "test"])
            if pipe.steps.get("npm test") is not None and pipe.steps["npm test"].code == 0:
                uid = uuid.uuid4().hex[:12]
                for key in PROBE_ORDER:
                    name = f"probe-{uid}-t059-{key}.test.ts"
                    probe_dir.mkdir(exist_ok=True)
                    path = probe_dir / name
                    written.append(path)
                    path.write_text(PROBE_SPECS[key], encoding="utf-8", newline="\n")
                    pipe.probe_files[key] = name
                    run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        else:
            pipe.stopped_reason = "npm ci（含 --offline 兑底）失败，后续步骤未运行"
    finally:
        for path in written:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        try:
            probe_dir.rmdir()
        except OSError:
            pass
        pipe.gate_probe_left = probe_dir.exists()
        pipe.status_after = git_status_set()
        pipe.digests_after = {name: file_digest(WEB / name) for name in WATCHED}
    return pipe


def assert_step_ok(pipe, name):
    assert pipe.ran, pipe.reason
    step = pipe.steps.get(name)
    assert step is not None, f"{name} 未运行：{pipe.stopped_reason or '前置步骤失败'}"
    assert step.code == 0, (
        f"{name} 退出码 {step.code}{'（超时被杀）' if step.timed_out else ''}，用时 {step.seconds:.0f}s"
        f"{network_hint(step.out)}\n--- 输出尾部 ---\n{step.tail}")
    return step


def assert_probe_ok(pipe, key):
    """探针 key 在候选上全部通过：退出码 0、输出里有探针文件名、通过数不少于 it( 行数、没有失败跳过待办。"""
    assert pipe.ran, pipe.reason
    assert key not in pipe.probe_skipped, pipe.probe_skipped[key]
    step = assert_step_ok(pipe, f"probe:{key}")
    name = pipe.probe_files.get(key)
    assert name and name in step.out.replace("\\", "/"), \
        f"探针输出里没有探针文件名，可能没被 Vitest 选中：\n{step.tail}"
    want = probe_count(PROBE_SPECS[key])
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m and int(m.group(1)) >= want, f"探针 {key} 应至少有 {want} 条通过：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), f"探针 {key} 有失败或跳过：\n{step.tail}"


# ---------------------------------------------------------------------------
# P / D 系列：流水线断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、V02、D10：npm 依赖（已在就跳过重装）、npm test（全绿，含执行端改写的
    live-readers.test.ts——旧断言没改掉会在这里红）都退出 0；依赖文件一个字节没动；
    gate-probe/ 没有留下。"""
    assert any(pipeline.steps.get(k) is not None and pipeline.steps[k].code == 0
               for k in ("npm ci", "npm ci --offline")), \
        f"npm ci（含 --offline 兑底）未成功：{pipeline.stopped_reason or pipeline.reason}"
    step = assert_step_ok(pipeline, "npm test")
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m, f"npm test 输出里没有通过计数：\n{step.tail}"
    assert int(m.group(1)) > 0
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), \
        f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert pipeline.digests_before == pipeline.digests_after, \
        "npm 流水线不许改动 desktop/web/package.json 与 package-lock.json"
    assert not pipeline.gate_probe_left, "gate-probe/ 目录在探针后应清掉"


def test_p2_worktree_unchanged_by_pipeline(pipeline):
    """P2（守卫）：流水线与探针前后 git status 相同；gate-probe/ 没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"


def test_d01_d05_probe_search(pipeline):
    """search 探针 / D01–D05：建作业（路径 /api/v1/jobs、正文恰好几个键、时限 15、task 不为 null
    才加 task 键）；201 之后 1000 毫秒首查、id 经 encodeURIComponent 编码、非终态继续查、
    终态之后计时器归零、全程没有取消与 client.get；终态信封合法就原样交回，为 null 或不合法就
    四句固定文案逐字；建作业非 201、查询非 200 一律报错信封并立即停（messages 取回应信封的
    messages，正文不是信封时是「ERROR: 服务返回 HTTP <状态码>」）；postRaw/getRaw reject 时
    searchLogs 跟着 reject。"""
    assert_probe_ok(pipeline, "search")
