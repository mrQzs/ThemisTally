"""T027 战前门禁：桌面端前端接真实服务 A 片（D3 之三）——传输层与只读数据的黑盒基准测试
（合同 t027-desktop-web-live v1，基线 c1192f0）。

被测对象是 ``desktop/web/``：新增 ``src/live/{mode,transport,connection}.ts`` 三个模块与
``scripts/check-live-build.mjs``（三取值构建检查），``vite.config.ts`` 改函数形式按 ``command === 'build'``
定义 ``__THEMIS_LIVE_MODE__``（标记串逐字 ``themis-live-real`` / ``themis-live-fixture``），
``api.ts`` 的 13 个读函数加真实分支并并入 ``getHistoryEntry``/``getPlugin``（夹具分支逐字保留），
写函数与 ``getOperation`` 真实模式回 501「写操作尚未接通」，``common-readers.ts`` 改转出写法且
``searchLogs`` 回「检索尚未接通」，``tasks-data.ts`` 与 ``mock/tasks-live.ts`` 真实模式不落夹具/不模拟，
``tests/shell-no-network.test.ts`` 放行 ``src/live/`` 并补成对自检样本；执行端另写五份
``tests/live-*.test.ts``（allowed_new_files）。

基线（c1192f0）上 ``src/live/``、``scripts/check-live-build.mjs``、五份 ``live-*.test.ts`` 都不存在，
``vite.config.ts`` 还是对象形式，``api.ts`` 没有 ``liveClient`` 分支，所以本文件的失败落在「文件不存在」
「标记不在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有仓库文件的读取都发生在用例
函数里；流水线（装依赖之后起 build、Vitest 与探针）放在 ``pipeline`` 会话级夹具里，候选里没有任何
``src/live/*.ts`` 时不装依赖、不起 Vitest。

结构（编号对应合同 DoD 的 D01–D14）：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：新文件在位（D01）；vite.config 的模式开关与
  NODE_ENV 无关（D01）；mode/transport/connection 的导出与定稿文案（D02–D06）；
  mode.ts 运行时引入 createLiveClient、导出集合固定四个、transport 反向只许 type 导入（B1/D02）；api.ts 的 15 个读函数、
  夹具分支记号、写函数 501、路由前缀（D07–D09）；common-readers 的转出与 T010 只许 type 导入的口径
  （D10）；tasks-data/tasks-live 的真实模式门槛（D11）；网络扫描放行 live/ 与成对样本（D12）；
  执行端五份测试在位、不用 skip/only/todo（D14）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：npm ci、npm test、
  npm run build（之后扫 dist 产物含 ``themis-live-real`` 与传输层特征串 ``same-origin``，B1）、
  ``node scripts/check-live-build.mjs``（V01–V03），再把探针逐份写成
  ``gate-probe/probe-<唯一标识>-t027-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，
  ``finally`` 里删除。

探针（Vitest + jsdom，全部自包含，辅助函数不跨文件共享）：

- mode：测试环境缺省 ``liveModeIsReal()`` 假、``liveClient()`` null；注入 fake/null/undefined 的语义，
  显式注入优先于构建模式（D02）。
- transport：成功路径的请求形状（同源相对路径、GET、same-origin、signal、不带凭据头）、查询用
  URLSearchParams 拼（undefined 键不拼、空格成 +）、时限 = 路由时限 + 5 秒与 timeoutMs 选项、断线、
  401（并发去重、没有宿主、reauth 抛错/ok:false）、503（Retry-After / 缺失 N=2）、其他 4xx/5xx 带信封
  原样返回、不带信封、200 且 ok:false、坏 JSON 与非七字段 JSON、七字段校验严格——每条都断言返回的是
  七字段信封而不是 reject，成功与超时后不留守计时器，连接状态置位（D03–D06）。
- connection：初值 connected、变化通知、没变不通知、退订后不通知、useConnectionState 钩子随状态重渲染
  （D06）。
- api：注入 fake client 后 15 个读函数逐个断言路径/查询/时限（getAttempt('a/b','x?y') 的编码、readFile
  的 path 与 cursor 进查询、cursor 不带不拼）；getMeta 的 kit_version 映射两种；getHistoryEntry 的
  resource/diff 归一化；getPlugin 的 allowed_permissions null → []；真实模式 ?mock= 不生效；夹具分支与
  error 开关照旧、getHistoryEntry/getPlugin 的 command/报错原文/深拷贝（D07、D08、D10）。
- unwired（过渡）：searchLogs「检索尚未接通」的探针整份随 T059 退役（站主 2026-11-19 为 T059 退役）；写函数与 getOperation 真实模式回 501 固定信封那一半站主 2026-11-13 为 T037 退役。
- tasks（过渡）：真实模式下 tasks-data 不取夹具兜底（先证明夹具键存在）、subscribeMockEvents 不模拟
  事件行（D11）。

过渡断言（函数名带 ``test_transitional_``，docstring 写明哪一片推翻，站主按名字退役）：

- ``test_transitional_s30_*``：connection 只有 connected/disconnected 两个取值——SSE 片会加 reconnecting（站主 2026-11-13 为 T036 退役）。
- ``test_transitional_s31_*``：getMetaNow 纯夹具同步——B 片第 8 步（首屏异步 meta）推翻。
- ``test_transitional_s32_*``：api.ts 的写函数 501「写操作尚未接通」——写操作接通的片推翻（站主 2026-11-13 为 T037 退役）。
- ``test_transitional_s33_*``：searchLogs「检索尚未接通」——作业/检索片推翻（站主 2026-11-19 为 T059 退役）。
- ``test_transitional_s34_*``：subscribeMockEvents 真实模式不模拟——SSE 片（subscribeEvents）推翻。
- ``test_transitional_p6_probe_unwired``：searchLogs 探针，随 T059 退役（站主 2026-11-19 为 T059 退役）；``test_transitional_p7_probe_tasks``：SSE 片会推翻。

合同没有写死、门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：超时文案里
N 用整秒数（timeoutMs 2000 → 「2 秒」）；「下一波 401 再起一次 reauth」按一次在途去重理解；URLSearchParams
对空格编码成 +；api.ts 传给 client.get 的时限是服务端时限（15/30/60/120），+5 秒在传输层做；
transport 探针的假响应自带 headers.get，不依赖宿主 Response。
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
WEB_REL = "desktop/web"
WEB = REPO_ROOT / "desktop" / "web"
SRC_REL = f"{WEB_REL}/src"
SRC = WEB / "src"
LIVE_REL = f"{SRC_REL}/live"
TESTS_REL = f"{WEB_REL}/tests"

# 合同 Scope 的新增非测试源码（allowed_new_files）
NEW_SOURCE_FILES = (
    f"{LIVE_REL}/mode.ts",
    f"{LIVE_REL}/transport.ts",
    f"{LIVE_REL}/connection.ts",
    f"{WEB_REL}/scripts/check-live-build.mjs",
)
# 合同 Scope 的新增执行端测试
EXECUTOR_TESTS = (
    "live-mode.test.ts",
    "live-transport.test.ts",
    "live-connection.test.ts",
    "live-api.test.ts",
    "live-readers.test.ts",
)
# 执行端五份测试里应出现的记号（合同第 8 步的最小覆盖证据）
EXECUTOR_TEST_TOKENS = {
    "live-mode.test.ts": ("liveModeIsReal", "liveClient", "setLiveClientForTests"),
    "live-transport.test.ts": ("createLiveClient", "Retry-After", "会话已失效", "请求超时", "same-origin"),
    "live-connection.test.ts": ("getConnectionState", "subscribeConnectionState", "useConnectionState",
                                "setConnectionState"),
    "live-api.test.ts": ("/api/v1/meta", "/api/v1/attempts", "kit_version",  # “写操作尚未接通”站主 2026-11-13 为 T037 退役
                         "allowed_permissions"),
    "live-readers.test.ts": ("searchLogs", "/api/v1/jobs", "夹具里没有这份数据"),
}

API_REL = f"{SRC_REL}/api.ts"
VITE_REL = f"{WEB_REL}/vite.config.ts"
MODE_REL = f"{LIVE_REL}/mode.ts"
TRANSPORT_REL = f"{LIVE_REL}/transport.ts"
CONNECTION_REL = f"{LIVE_REL}/connection.ts"
READERS_REL = f"{SRC_REL}/pages/readonly2/common-readers.ts"
TASKS_DATA_REL = f"{SRC_REL}/pages/tasks/tasks-data.ts"
TASKS_LIVE_REL = f"{SRC_REL}/mock/tasks-live.ts"
NONET_REL = f"{TESTS_REL}/shell-no-network.test.ts"
CHECK_BUILD_REL = f"{WEB_REL}/scripts/check-live-build.mjs"

# T022 :117-118 钉死的 13 个读函数（:236 的正则逐个查「原样保留」）
API_READS = ("getMeta", "getStatus", "getAttempt", "readFile", "getRoles", "getProfiles", "getPresets",
             "diffPresets", "getRuntimes", "getPlugins", "getHistory", "getUsage", "listSecrets")
# 本片新并入 api.ts 的两个读函数（合同第四节表格最后两行）
API_NEW_READS = ("getHistoryEntry", "getPlugin")
# 真实模式回 501 的写函数与 getOperation（合同第四节）
API_WRITES_501 = ("preview", "getOperation", "usePreset", "setPluginEnabled", "removePreset", "removeProfile",
                  "removeRuntime", "rollback", "addProfile", "editProfile")
# api.ts 里应出现的路由前缀（合同第四节表格）
API_ROUTES = (
    "/api/v1/meta", "/api/v1/status", "/api/v1/attempts", "/api/v1/roles", "/api/v1/profiles",
    "/api/v1/presets", "/api/v1/runtimes", "/api/v1/plugins", "/api/v1/config/history", "/api/v1/usage",
    "/api/v1/secrets",
)

NETWORK_WORDS = ("fetch", "XMLHttpRequest", "EventSource", "WebSocket")
NETWORK_RE = re.compile(r"(?<![A-Za-z0-9_$])(?:fetch|XMLHttpRequest|EventSource|WebSocket)(?![A-Za-z0-9_$])")
# T011 S2 的注入词对 src/live/ 照旧有效（规划下游须知第 3 条）
SINK_WORDS = ("dangerouslySetInnerHTML", "innerHTML", "outerHTML", "insertAdjacentHTML", "eval(",
              "new Function", "document.write", "srcdoc", "createContextualFragment", "DOMParser")

# transport 失败分类的定稿文案（合同第二节，逐字）
MSG_TIMEOUT_PREFIX = "ERROR: 请求超时（"
MSG_TIMEOUT_SUFFIX = "秒），没有收到服务的回应"
MSG_DISCONNECT = "ERROR: 连不上本机服务（请求没有到达服务）"
MSG_401 = "ERROR: 会话已失效"
MSG_503_PREFIX = "ERROR: 服务繁忙（排队过长），请 "
MSG_503_SUFFIX = "秒后重试"
MSG_HTTP_PREFIX = "ERROR: 服务返回 HTTP "
MSG_BAD_JSON_PREFIX = "ERROR: 服务的响应不是合法的 JSON（HTTP "
MSG_BAD_JSON_SUFFIX = "）"

ERROR_MESSAGE = "ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied"


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def read_rel(rel):
    return _read(REPO_ROOT / rel)


def need_file(rel):
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return path


def need_new_sources():
    missing = [rel for rel in NEW_SOURCE_FILES if not (REPO_ROOT / rel).is_file()]
    assert not missing, f"缺少本片的新文件（基线上还没有实现）：{missing}"


def need_live_dir():
    assert (REPO_ROOT / LIVE_REL).is_dir(), f"{LIVE_REL}/ 不存在（基线上还没有实现）"


def file_digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def git(*args, check=False):
    proc = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, timeout=120)
    if check:
        assert proc.returncode == 0, f"git {' '.join(args)} 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return proc


def git_status_set():
    proc = git("status", "--porcelain=v1", "--untracked-files=all", "-z", check=True)
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


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


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:40])


# TS 注释剥离（与 T010 的 _TS_COMMENT 同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def api_import_problems(rel):
    """T010 :544-549 的口径：对 ``../…/api`` 的引入只许 import type（转出语句不以 import 开头不算）。

    合同第五节要求 common-readers 的转出语句「前一条语句以分号结尾」，本质就是让这条正则的
    ``[^;]*?`` 跨不过去；这里直接复刻这条检查，比数分号更接近真实不变量。"""
    code = strip_ts_comments(read_rel(rel))
    problems = []
    for m in re.finditer(r"""import\s+([^;]*?)\s+from\s+['"]((?:\.\./)+api)['"]""", code, re.S):
        spec = m.group(1).strip()
        items = [s.strip() for s in spec.strip("{} \n").split(",") if s.strip()] if spec.startswith("{") else []
        type_only = spec.startswith("type ") or (items and all(s.startswith("type ") for s in items))
        if not type_only:
            problems.append(f"{rel}：对 {m.group(2)} 只许 import type，实际 {m.group(0)[:80]}")
    return problems


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_new_source_files_present():
    """S01 / D01：allowed_new_files 的三个 src/live 模块与 check-live-build.mjs 都在（基线上没有，本条先红）。"""
    need_new_sources()


def test_s01b_executor_test_files_present():
    """S01b / D14、第 8 步：五份执行端测试都在，且不用 skip/only/todo。"""
    for name in EXECUTOR_TESTS:
        rel = f"{TESTS_REL}/{name}"
        need_file(rel)
        text = read_rel(rel)
        bad = [pat for pat in (r"\.skip\s*\(", r"\.only\s*\(", r"\.todo\s*\(", r"\bxit\s*\(", r"\bdescribe\.only")
               if re.search(pat, text)]
        assert not bad, f"{rel} 里出现了 {bad}（合同 D14：不删用例、不削弱断言）"


def test_s01c_executor_test_tokens():
    """S01c / 第 8 步：五份执行端测试里应出现的记号（各自主题的最小覆盖）。"""
    for name, tokens in EXECUTOR_TEST_TOKENS.items():
        rel = f"{TESTS_REL}/{name}"
        need_file(rel)
        text = read_rel(rel)
        missing = [t for t in tokens if t not in text]
        assert not missing, f"{rel} 里缺少记号 {missing}（合同第 8 步要求的最小覆盖）"


def test_s02_vite_config_mode_switch():
    """S02 / D01：vite.config.ts 是函数形式，按 command === 'build' 定义 __THEMIS_LIVE_MODE__，
    两个标记串逐字在，不跟任何环境变量走；base/react()/jsdom/gate-probe 照旧。"""
    need_file(VITE_REL)
    text = read_rel(VITE_REL)
    assert re.search(r"defineConfig\s*\(\s*\(\s*\{?\s*command", text), \
        "vite.config.ts 应是 defineConfig(({ command }) => ({ … })) 的函数形式"
    assert re.search(r"__THEMIS_LIVE_MODE__\s*:\s*JSON\.stringify\(", text), \
        "define 里应有 __THEMIS_LIVE_MODE__: JSON.stringify(…)"
    assert "command === 'build'" in text or 'command === "build"' in text, \
        "模式开关应按 command === 'build' 判（与 NODE_ENV 无关）"
    assert "'themis-live-real'" in text, "标记串 'themis-live-real' 应逐字出现在 vite.config.ts"
    assert "'themis-live-fixture'" in text, "标记串 'themis-live-fixture' 应逐字出现在 vite.config.ts"
    assert not re.search(r"import\.meta\.env", text), "vite.config.ts 不许用 import.meta.env 当判据"
    assert not re.search(r"process\.env", text), "vite.config.ts 不许用 process.env（含 NODE_ENV）当判据"
    # 既有配置原样保留
    assert re.search(r"base:\s*['\"]\./['\"]", text), "base: './' 应保留"
    assert "react()" in text, "plugins: [react()] 应保留"
    assert re.search(r"environment:\s*['\"]jsdom['\"]", text), "test.environment: 'jsdom' 应保留"
    assert "gate-probe" in text, "test.include 里的 gate-probe 模式应保留"


def test_s03_live_mode_module():
    """S03 / D01、D02：src/live/mode.ts 的形状——declare const、兜底 'unknown'、四个导出、Envelope 只许 type 导入（B1：运行时引入 createLiveClient）。"""
    need_file(MODE_REL)
    text = read_rel(MODE_REL)
    assert re.search(r"declare const __THEMIS_LIVE_MODE__", text), \
        "mode.ts 应有 declare const __THEMIS_LIVE_MODE__（本工程没有 vite/client 类型）"
    assert re.search(r"typeof __THEMIS_LIVE_MODE__\s*===\s*['\"]string['\"]", text), \
        "BUILD_MODE 应按 typeof __THEMIS_LIVE_MODE__ === 'string' 求值"
    assert "'unknown'" in text, "没有注入定义时的兜底值应是 'unknown'（不许是 themis-live-fixture）"
    assert not re.search(r"__THEMIS_LIVE_MODE__\s*:\s*['\"]themis-live-fixture['\"]", text), \
        "BUILD_MODE 的兜底分支不许是 'themis-live-fixture'（否则三取值构建检查分不出真伪）"
    assert "'themis-live-real'" in text, "liveModeIsReal 应比对 'themis-live-real'"
    for name in ("liveModeIsReal", "liveClient", "setLiveClientForTests"):
        assert re.search(rf"export function {name}\(", text), f"mode.ts 应导出函数 {name}"
    assert re.search(r"export (?:type|interface) LiveClient\b", text), "mode.ts 应导出 LiveClient 类型"
    # B1 / 合同 v2 第一节：真实模式的缺省客户端由 createLiveClient() 创建——运行时引入，不是 import type
    assert re.search(r"import\s*\{[^}]*\bcreateLiveClient\b[^}]*\}\s*from\s*['\"]\./transport['\"]", text), \
        "mode.ts 应运行时 import { createLiveClient } from './transport'（不是 import type：否则传输层不进产物，真实模式没接上）"
    assert re.search(r"\bcreateLiveClient\s*\(", text), "mode.ts 里应真的调 createLiveClient() 建缺省客户端"
    # 合同 v2 第一节：导出集合固定为四个，不许多导出（tasks 探针会 mock 掉整个模块，多导出会让它的 mock 工厂缺符号）
    code = strip_ts_comments(text)
    assert not re.search(r"export\s*\*", code), "mode.ts 不许 export *（导出集合固定为四个）"
    names = set()
    for pattern in (r"export\s+(?:async\s+)?function\s+(\w+)",
                    r"export\s+(?:const|let|var)\s+(\w+)",
                    r"export\s+(?:type|interface)\s+(\w+)"):
        names.update(mm.group(1) for mm in re.finditer(pattern, code))
    for em in re.finditer(r"export\s*\{([^}]*)\}", code):
        for item in em.group(1).split(","):
            name = item.strip()
            if not name:
                continue
            if name.startswith("type "):
                name = name[5:].strip()
            name = name.split(" as ")[-1].strip()
            if name:
                names.add(name)
    extra = names - {"liveModeIsReal", "liveClient", "setLiveClientForTests", "LiveClient"}
    assert not extra, f"mode.ts 的导出集合应只有四个固定符号，多出了 {sorted(extra)}"
    # Envelope 只许 type 导入（避免运行时循环依赖）
    for m in re.finditer(r"""import\s+([^;\n]*)\s+from\s+['"]\.\./api['"];?""", text):
        assert m.group(1).strip().startswith("type"), \
            f"mode.ts 对 ../api 只许 import type（合同第一节），实际 {m.group(0)}"


def test_s04_live_transport_module():
    """S04 / D03–D05：src/live/transport.ts 的形状——createLiveClient 的选项、定稿文案、请求形状与信封校验；
    对 './mode' 只许 type 导入（反向依赖只许走类型，避免运行时循环）。"""
    need_file(TRANSPORT_REL)
    text = read_rel(TRANSPORT_REL)
    assert re.search(r"export (?:function|const) createLiveClient\b", text), \
        "transport.ts 应导出 createLiveClient"
    for word in ("fetch", "host", "timeoutMs", "reauth"):
        assert re.search(rf"\b{word}\b", text), f"createLiveClient 的选项里应有 {word}"
    assert "URLSearchParams" in text, "查询应使用 URLSearchParams 拼"
    assert "AbortController" in text, "时限应使用 AbortController"
    assert re.search(r"credentials:\s*['\"]same-origin['\"]", text), "请求应带 credentials: 'same-origin'"
    assert "Retry-After" in text, "503 应读 Retry-After 响应头"
    assert re.search(r"\bsetConnectionState\b", text), "传输层应把状态报给 connection 的 setConnectionState"
    assert "'connected'" in text and "'disconnected'" in text, "状态取值应出现在 transport.ts"
    messages = {
        "超时": MSG_TIMEOUT_PREFIX,
        "断线": MSG_DISCONNECT,
        "401": MSG_401,
        "503": MSG_503_PREFIX,
        "其他状态码": MSG_HTTP_PREFIX,
        "坏 JSON": MSG_BAD_JSON_PREFIX,
    }
    for label, msg in messages.items():
        assert msg in text, f"transport.ts 缺少{label}的定稿文案 {msg!r}"
    assert "exit_code: null" in text, "合成信封的 exit_code 应是 null"
    # 合同 v2 第一节：反向依赖只许走类型（LiveClient 用 import type 从 './mode' 拿）
    for m in re.finditer(r"""import\s+([^;\n]*)\s+from\s+['\"]\./mode['\"]""", text):
        spec = m.group(1).strip()
        items = [s.strip() for s in spec.strip("{} \n").split(",") if s.strip()] if spec.startswith("{") else []
        type_only = spec.startswith("type ") or (items and all(s.startswith("type ") for s in items))
        assert type_only, f"transport.ts 对 ./mode 只许 import type（运行时循环），实际 {m.group(0)}"


def test_s05_live_connection_module():
    """S05 / D06：src/live/connection.ts 的形状——四个导出、useSyncExternalStore、ConnectionState 两取值。"""
    need_file(CONNECTION_REL)
    text = read_rel(CONNECTION_REL)
    for name in ("getConnectionState", "subscribeConnectionState", "useConnectionState", "setConnectionState"):
        assert re.search(rf"export function {name}\(", text), f"connection.ts 应导出函数 {name}"
    assert "useSyncExternalStore" in text, "useConnectionState 应基于 useSyncExternalStore"
    assert re.search(r"export type ConnectionState = ['\"]connected['\"]\s*\|\s*['\"]disconnected['\"]", text), \
        "ConnectionState 应只有 'connected' | 'disconnected'"


def test_s06_api_reads_writes_and_routes():
    """S06 / D07–D09、D13：api.ts 的 13 个读函数原样保留写法、两个新读函数并入、liveClient 分支、
    写函数 501 的固定信封、路由前缀、夹具机制仍在。"""
    need_file(API_REL)
    text = read_rel(API_REL)
    for name in API_READS:
        assert re.search(rf"export function {name}\(", text), f"api.ts 的读函数 {name} 应保持 export function 原样"
    for name in API_NEW_READS:
        assert re.search(rf"export (?:async )?function {name}\(", text), \
            f"api.ts 应导出并入的读函数 {name}"
    for name in API_WRITES_501:
        assert re.search(rf"export (?:async )?function {name}\(", text), f"api.ts 应保留写函数 {name}"
    assert re.search(r"""from ['"]\.\/live\/mode['"]""", text) and re.search(r"\bliveClient\b", text), \
        "api.ts 应从 ./live/mode 引入 liveClient 并在函数体里用"
    # 写函数 501 的报错原文与状态码两行：站主 2026-11-13 为 T037（写操作接真实路由）退役
    for route in API_ROUTES:
        assert route in text, f"api.ts 应出现路由 {route}"
    assert re.search(r"export function getMetaNow\(", text), "getMetaNow 应仍是同步的 export function"
    assert "currentMock" in text, "夹具分支的 currentMock 机制应保留"
    assert re.search(r"export interface Envelope\b", text), "Envelope 类型应照旧导出"


def test_s07_common_readers_reexport():
    """S07 / D10、第五节：common-readers.ts 改成转出写法、searchLogs 保留、
    对 ../api 只许 import type（T010 :544 的口径）。"""
    need_file(READERS_REL)
    text = read_rel(READERS_REL)
    m = re.search(r"""export\s*\{\s*getHistoryEntry\s*,\s*getPlugin\s*\}\s*from\s*['"]\.\./\.\./api['"]\s*;""", text)
    assert m, "common-readers.ts 应有 export { getHistoryEntry, getPlugin } from '../../api';"
    # 前一条语句以分号结尾（让 T010 的 [^;]*? 跨不过去）；若转出是第一条代码语句则无前一条
    code = strip_ts_comments(text)
    cm = re.search(r"""export\s*\{\s*getHistoryEntry\s*,\s*getPlugin\s*\}\s*from""", code)
    before = code[:cm.start()].rstrip()
    if before:
        assert before.endswith(";"), \
            "转出语句的前一条语句应以分号结尾（T010 的正则会一路匹配到下一个分号为止）"
    assert not api_import_problems(READERS_REL), api_import_problems(READERS_REL)
    assert re.search(r"export function searchLogs\(", text), "searchLogs 应保留在 common-readers.ts"
    assert "夹具里没有这份数据" in text, "searchLogs 的夹具分支（报缺文案）应保留"
    assert ERROR_MESSAGE in text, "error 开关的报错原文应保留"
    assert "SEARCH_PATTERN" in text, "检索夹具的接线应保留"


def test_s08_tasks_data_real_mode_gate():
    """S08 / D11、第六节：tasks-data.ts 引入 liveModeIsReal，夹具兜底的查找仍在（夹具模式逐字不动）。"""
    need_file(TASKS_DATA_REL)
    text = read_rel(TASKS_DATA_REL)
    assert re.search(r"""from ['"]\.\./\.\./live\/mode['"]""", text), \
        "tasks-data.ts 应从 ../../live/mode 引入 liveModeIsReal"
    assert re.search(r"\bliveModeIsReal\b", text), "tasks-data.ts 应调用 liveModeIsReal 判真实模式"
    for token in ("findAttemptFixture", "findFileFixture", "currentMock"):
        assert token in text, f"tasks-data.ts 的夹具兜底机制应保留（{token}）"


def test_s09_shell_no_network_rule():
    """S09 / D12、第七节：shell-no-network.test.ts 放行 src/live/、有成对自检样本，保留 T006 d08 的样本与四个词。"""
    need_file(NONET_REL)
    text = read_rel(NONET_REL)
    assert re.search(r"['\"]live['\"]|src/live|live/", text), \
        "扫描规则应放行 src/live/（文件里应出现 live 的路径或目录名）"
    # 成对样本：同一段带网络词的文本，live/ 下不报、别处照报
    paired_clean = [line for line in text.splitlines()
                    if re.search(r"live", line) and re.search(r"toBe\(false\)", line)]
    assert paired_clean, "应有放在 live/ 路径下、期望不报的自检样本"
    assert re.search(r"RE\.test\([^\n]*\)\.toBe\(true\)|\.toBe\(true\)[^\n]*RE\.test", text) or \
        "toBe(true)" in text, "自检样本应仍证明别处照报"
    # 基线的五个「报」样本与三个「不报」样本
    for sample in ("window.fetch(", "new WebSocket(", "globalThis['fetch']", "new EventSource(", "new XMLHttpRequest"):
        assert sample in text, f"自检样本 {sample!r} 应保留"
    for sample in ("prefetchAll", "fetchedAt", "globalThis"):
        assert sample in text, f"自检样本 {sample!r} 应保留（T006 d08）"
    for word in NETWORK_WORDS:
        assert re.search(rf"\b{word}\b", text), f"四个网络接口名里的 {word} 应仍在文件里（T006 d08）"


def test_s10_network_and_sink_scan():
    """S10 / D12：src 下（除 live/）没有任何文件出现四个网络整词（注释与字符串都算）；
    src/live/ 下不出现注入词（T011 S2 对 live/ 照旧有效）。"""
    need_live_dir()
    problems = []
    for path in sorted(SRC.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = _read(path)
        if not rel.startswith(f"{SRC_REL}/live/"):
            for m in NETWORK_RE.finditer(text):
                problems.append(f"{rel} 出现 {m.group(0)}")
        else:
            for word in SINK_WORDS:
                if word in text:
                    problems.append(f"{rel} 出现注入词 {word}")
    fail_if(problems, "src 的网络词/注入词扫描")


def test_s12_check_live_build_script():
    """S12 / D01、第 9 步：check-live-build.mjs 用本地 vite 按三种 NODE_ENV 取值各构建一次，
    判定产物里的两个标记串，成功打印 LIVE_BUILD_OK。"""
    need_file(CHECK_BUILD_REL)
    text = read_rel(CHECK_BUILD_REL)
    assert "'themis-live-real'" in text or '"themis-live-real"' in text, \
        "check-live-build.mjs 应判定产物含 themis-live-real"
    assert "'themis-live-fixture'" in text or '"themis-live-fixture"' in text, \
        "check-live-build.mjs 应判定产物不含 themis-live-fixture"
    assert "LIVE_BUILD_OK" in text, "三种取值都过时应打印 LIVE_BUILD_OK"
    assert "NODE_ENV" in text, "应依次用三种 NODE_ENV 取值构建（未设、development、test）"
    assert "development" in text and "test" in text, "三种取值里的 development 与 test 应出现在脚本里"
    assert "vite.js" in text and "node_modules" in text, \
        "应使用本地 vite 构建（node node_modules/vite/bin/vite.js build，不由全局/远程拿 vite）"
    assert "dist" in text, "应读取 dist 下的构建产物做判定"


# ---------------------------------------------------------------------------
# 过渡断言（后续片会推翻；站主按 test_transitional_ 前缀退役）
# ---------------------------------------------------------------------------

def test_transitional_s31_getmetanow_pure_fixture():
    """过渡 / D08：getMetaNow 一字未改（同步、纯夹具）——B 片第 8 步（首屏异步 meta）会推翻，届时退役本条。"""
    need_file(API_REL)
    text = read_rel(API_REL)
    m = re.search(r"export function getMetaNow\([^)]*\)\s*(?::[^{]{0,80})?\s*\{([^{}]*)\}", text, re.S)
    assert m, "getMetaNow 应仍是同步的 export function（签名原样）"
    assert "clone(metaJson)" in m.group(1), "getMetaNow 的函数体应仍是 clone(metaJson)"


def test_transitional_s34_tasks_live_real_mode_gate():
    """过渡 / D11：subscribeMockEvents 真实模式不模拟事件行——SSE 片（subscribeEvents）会推翻。"""
    need_file(TASKS_LIVE_REL)
    text = read_rel(TASKS_LIVE_REL)
    assert re.search(r"""from ['"]\.\./live\/mode['"]""", text) or re.search(r"\bliveModeIsReal\b", text), \
        "mock/tasks-live.ts 应引入 liveModeIsReal，真实模式不模拟事件行"
    assert re.search(r"export function subscribeMockEvents\(", text), "subscribeMockEvents 应保留导出"
    for token in ("ui-readonly-api", "attempt-001", "currentMock"):
        assert token in text, f"夹具模式的行为记号 {token} 应保留"


# ---------------------------------------------------------------------------
# 探针源码（每份自包含：辅助函数不跨文件共享）
# ---------------------------------------------------------------------------

PROBE_MODE = r"""
import { afterEach, describe, expect, it, vi } from 'vitest';
import { liveClient, liveModeIsReal, setLiveClientForTests } from '../src/live/mode';

vi.setConfig({ testTimeout: 60000 });

const fakeClient: any = {
  get: () => Promise.resolve({ ok: true, exit_code: 0, data: {}, output: [], messages: [], command: [], elapsed_ms: 0 }),
};

afterEach(() => {
  setLiveClientForTests(undefined);
});

describe('live/mode：模式与注入', () => {
  it('测试环境缺省：liveModeIsReal() 为假、liveClient() 为 null（零请求）', () => {
    expect(liveModeIsReal()).toBe(false);
    expect(liveClient()).toBe(null);
  });

  it('setLiveClientForTests(fake) 后 liveClient() 返回 fake（显式注入优先于构建模式）', () => {
    setLiveClientForTests(fakeClient);
    expect(liveClient()).toBe(fakeClient);
    expect(liveModeIsReal()).toBe(false);
  });

  it('setLiveClientForTests(null) 表示「不发请求」：liveClient() 是 null', () => {
    setLiveClientForTests(fakeClient);
    setLiveClientForTests(null);
    expect(liveClient()).toBe(null);
  });

  it('setLiveClientForTests(undefined) 清除注入，回到缺省 null', () => {
    setLiveClientForTests(fakeClient);
    setLiveClientForTests(undefined);
    expect(liveClient()).toBe(null);
  });
});
"""

PROBE_TRANSPORT = r"""
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getConnectionState, setConnectionState } from '../src/live/connection';
import { createLiveClient } from '../src/live/transport';

vi.setConfig({ testTimeout: 60000 });

function envelope(data: unknown) {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command: [], elapsed_ms: 4 };
}
function failureEnvelope(messages: string[]) {
  return { ok: false, exit_code: null, data: null, output: [], messages, command: [], elapsed_ms: 0 };
}
function textResponse(status: number, body: string, headers: Record<string, string> = {}) {
  const lower: Record<string, string> = {};
  Object.keys(headers).forEach((k) => { lower[k.toLowerCase()] = headers[k]; });
  return {
    status,
    ok: status >= 200 && status < 300,
    text: async () => body,
    headers: {
      get: (name: string) => (Object.prototype.hasOwnProperty.call(lower, name.toLowerCase())
        ? lower[name.toLowerCase()] : null),
    },
  };
}
function jsonResponse(status: number, body: unknown, headers?: Record<string, string>) {
  return textResponse(status, JSON.stringify(body), headers);
}
function abortError(): Error {
  return Object.assign(new Error('The operation was aborted'), { name: 'AbortError' });
}
type Seen = { input: string; init: any };
function recorder(responder: (seen: Seen) => unknown) {
  const seen: Seen[] = [];
  const fn = (input: any, init?: any) => {
    seen.push({ input: String(input), init: init || {} });
    return Promise.resolve(responder(seen[seen.length - 1]));
  };
  return { seen, fn };
}
function hanging() {
  const seen: Seen[] = [];
  const fn = (input: any, init?: any) => {
    seen.push({ input: String(input), init: init || {} });
    return new Promise((_resolve, reject) => {
      const sig = init && init.signal;
      if (!sig) return;
      if (sig.aborted) reject(abortError());
      else sig.addEventListener('abort', () => reject(abortError()));
    });
  };
  return { seen, fn };
}

beforeEach(() => {
  setConnectionState('connected');
});
afterEach(() => {
  vi.useRealTimers();
  setConnectionState('connected');
});

describe('live/transport：成功路径与请求形状', () => {
  it('200 + 合法信封原样返回；同源相对路径、GET、same-origin、带 signal、不拼凭据头', async () => {
    const rec = recorder(() => jsonResponse(200, envelope({ v: 7 })));
    const client = createLiveClient({ fetch: rec.fn as any });
    const env = await client.get('/api/v1/meta');
    expect(env).toEqual(envelope({ v: 7 }));
    expect(rec.seen.length).toBe(1);
    expect(rec.seen[0].input).toBe('/api/v1/meta');
    expect(rec.seen[0].init.method).toBe('GET');
    expect(rec.seen[0].init.credentials).toBe('same-origin');
    const sig = rec.seen[0].init.signal;
    expect(sig && typeof sig.aborted === 'boolean').toBe(true);
    const h = rec.seen[0].init.headers;
    const keys = h == null ? [] : typeof h.keys === 'function' ? Array.from(h.keys()) : Object.keys(h);
    const bad = keys.filter((k: any) => {
      const name = String(k).toLowerCase();
      return name === 'authorization' || name.startsWith('x-');
    });
    expect(bad).toEqual([]);
    expect(getConnectionState()).toBe('connected');
  });

  it('查询用 URLSearchParams 拼：undefined 的键不拼，空格成 +，无查询不带 ?', async () => {
    const rec = recorder(() => jsonResponse(200, envelope(null)));
    const client = createLiveClient({ fetch: rec.fn as any });
    await client.get('/api/v1/attempts/t1/a1/file', { path: 'a b', cursor: undefined });
    expect(rec.seen[0].input).toBe('/api/v1/attempts/t1/a1/file?path=a+b');
    await client.get('/api/v1/roles');
    expect(rec.seen[1].input).toBe('/api/v1/roles');
  });

  it('成功请求结束后不留守计时器', async () => {
    vi.useFakeTimers();
    const rec = recorder(() => jsonResponse(200, envelope({})));
    const client = createLiveClient({ fetch: rec.fn as any });
    await client.get('/api/v1/roles');
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe('live/transport：失败分类', () => {
  it('超时：中止时刻 = 路由时限 + 5 秒；文案带秒数；状态 disconnected；定时器清掉', async () => {
    vi.useFakeTimers();
    const hang = hanging();
    const client = createLiveClient({ fetch: hang.fn as any });
    const p = client.get('/api/v1/status', undefined, 30);
    let settled = false;
    p.then(() => { settled = true; }, () => { settled = true; });
    await vi.advanceTimersByTimeAsync(34999);
    expect(settled).toBe(false);
    expect(hang.seen[0].init.signal.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    const env = await p;
    expect(env).toEqual(failureEnvelope(['ERROR: 请求超时（35 秒），没有收到服务的回应']));
    expect(hang.seen[0].init.signal.aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
    expect(getConnectionState()).toBe('disconnected');
  });

  it('timeoutMs 选项：本次请求用它当中止时限（文案的秒数跟着它走）', async () => {
    vi.useFakeTimers();
    const hang = hanging();
    const client = createLiveClient({ fetch: hang.fn as any, timeoutMs: 2000 });
    const p = client.get('/api/v1/status', undefined, 30);
    const env = await vi.advanceTimersByTimeAsync(2000).then(() => p);
    expect(env.messages).toEqual(['ERROR: 请求超时（2 秒），没有收到服务的回应']);
  });

  it('断线：fetch 抛错且非我方中止 → 固定文案，状态 disconnected', async () => {
    const client = createLiveClient({ fetch: (() => Promise.reject(new TypeError('Failed to fetch'))) as any });
    const env = await client.get('/api/v1/roles');
    expect(env).toEqual(failureEnvelope(['ERROR: 连不上本机服务（请求没有到达服务）']));
    expect(getConnectionState()).toBe('disconnected');
  });

  it('401：并发两个只调一次 reauth，两个都回同一句；下一波 401 再起一次新的', async () => {
    let reauthCalls = 0;
    const rec = recorder(() => jsonResponse(401, { some: 'body' }));
    const client = createLiveClient({
      fetch: rec.fn as any,
      host: { reauth: () => { reauthCalls += 1; return Promise.resolve({ ok: true }); } },
    });
    const [a, b] = await Promise.all([client.get('/x'), client.get('/y')]);
    expect(reauthCalls).toBe(1);
    expect(a).toEqual(failureEnvelope(['ERROR: 会话已失效']));
    expect(b).toEqual(failureEnvelope(['ERROR: 会话已失效']));
    await client.get('/z');
    expect(reauthCalls).toBe(2);
    expect(getConnectionState()).toBe('connected');
  });

  it('401：没有宿主 / reauth 抛错 / reauth 回 ok:false，都回同一句且不冒泡', async () => {
    const respond401 = recorder(() => jsonResponse(401, {}));
    const noHost = createLiveClient({ fetch: respond401.fn as any });
    expect((await noHost.get('/x')).messages).toEqual(['ERROR: 会话已失效']);
    const throws = createLiveClient({
      fetch: respond401.fn as any,
      host: { reauth: () => { throw new Error('boom'); } },
    });
    expect((await throws.get('/x')).messages).toEqual(['ERROR: 会话已失效']);
    const notOk = createLiveClient({
      fetch: respond401.fn as any,
      host: { reauth: () => Promise.resolve({ ok: false }) },
    });
    expect((await notOk.get('/x')).messages).toEqual(['ERROR: 会话已失效']);
  });

  it('503：读 Retry-After；缺失或不是非负整数时 N=2；不自动重试', async () => {
    const withHeader = recorder(() => jsonResponse(503, {}, { 'Retry-After': '7' }));
    const a = createLiveClient({ fetch: withHeader.fn as any });
    expect((await a.get('/x')).messages).toEqual(['ERROR: 服务繁忙（排队过长），请 7 秒后重试']);
    expect(withHeader.seen.length).toBe(1);
    const missing = recorder(() => jsonResponse(503, {}));
    const b = createLiveClient({ fetch: missing.fn as any });
    expect((await b.get('/x')).messages).toEqual(['ERROR: 服务繁忙（排队过长），请 2 秒后重试']);
    const invalid = recorder(() => jsonResponse(503, {}, { 'Retry-After': 'soon' }));
    const c = createLiveClient({ fetch: invalid.fn as any });
    expect((await c.get('/x')).messages).toEqual(['ERROR: 服务繁忙（排队过长），请 2 秒后重试']);
  });

  it('其他 4xx/5xx：正文是合法七字段信封就原样返回（服务自己的提示）', async () => {
    const serverEnvelope = {
      ok: false, exit_code: null, data: null, output: [],
      messages: ['ERROR: 上游超时'], command: ['status'], elapsed_ms: 1200,
    };
    const rec = recorder(() => jsonResponse(504, serverEnvelope));
    const client = createLiveClient({ fetch: rec.fn as any });
    const env = await client.get('/api/v1/status', undefined, 30);
    expect(env).toEqual(serverEnvelope);
    expect(getConnectionState()).toBe('connected');
  });

  it('其他 4xx/5xx：正文不是合法信封 → ERROR: 服务返回 HTTP <状态码>', async () => {
    const rec500 = recorder(() => textResponse(500, 'internal error'));
    const c500 = createLiveClient({ fetch: rec500.fn as any });
    expect((await c500.get('/x')).messages).toEqual(['ERROR: 服务返回 HTTP 500']);
    const rec404 = recorder(() => textResponse(404, 'nope'));
    const c404 = createLiveClient({ fetch: rec404.fn as any });
    expect((await c404.get('/x')).messages).toEqual(['ERROR: 服务返回 HTTP 404']);
  });

  it('200 且 ok:false：原样返回（内核报错原文）', async () => {
    const kernelEnvelope = {
      ok: false, exit_code: 2, data: null, output: [],
      messages: ['ERROR 用法错误'], command: ['status'], elapsed_ms: 9,
    };
    const rec = recorder(() => jsonResponse(200, kernelEnvelope));
    const client = createLiveClient({ fetch: rec.fn as any });
    expect(await client.get('/x')).toEqual(kernelEnvelope);
  });

  it('坏 JSON / JSON 但不是七字段信封 → ERROR: 服务的响应不是合法的 JSON（HTTP <状态码>）', async () => {
    const bad = recorder(() => textResponse(200, 'not-json{'));
    const a = createLiveClient({ fetch: bad.fn as any });
    expect((await a.get('/x')).messages).toEqual(['ERROR: 服务的响应不是合法的 JSON（HTTP 200）']);
    const notEnvelope = recorder(() => jsonResponse(200, { ok: true }));
    const b = createLiveClient({ fetch: notEnvelope.fn as any });
    expect((await b.get('/x')).messages).toEqual(['ERROR: 服务的响应不是合法的 JSON（HTTP 200）']);
  });

  it('信封校验严格：七字段缺一个或类型不对，都按非信封处理', async () => {
    const full = { ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 1 };
    const bads: Array<Record<string, unknown>> = [];
    const missingCommand: Record<string, unknown> = { ...full };
    delete missingCommand.command;
    bads.push(missingCommand);
    bads.push({ ...full, ok: 'yes' });
    bads.push({ ...full, exit_code: '2' });
    bads.push({ ...full, messages: 'x' });
    bads.push({ ...full, output: [1] });
    bads.push({ ...full, elapsed_ms: '3' });
    let i = 0;
    const fn = () => {
      const body = JSON.stringify(bads[i]);
      i += 1;
      return Promise.resolve(textResponse(500, body));
    };
    const client = createLiveClient({ fetch: fn as any });
    for (let k = 0; k < bads.length; k += 1) {
      const env = await client.get('/x');
      expect(env.messages).toEqual(['ERROR: 服务返回 HTTP 500']);
    }
  });

  it('连接状态：断线置 disconnected，收到任何 HTTP 响应（哪怕 500）恢复 connected', async () => {
    const dead = createLiveClient({ fetch: (() => Promise.reject(new TypeError('net down'))) as any });
    await dead.get('/x');
    expect(getConnectionState()).toBe('disconnected');
    const rec500 = recorder(() => jsonResponse(500, 'oops'));
    const c500 = createLiveClient({ fetch: rec500.fn as any });
    await c500.get('/x');
    expect(getConnectionState()).toBe('connected');
    setConnectionState('disconnected');
    const rec200 = recorder(() => jsonResponse(200, envelope({})));
    const c200 = createLiveClient({ fetch: rec200.fn as any });
    await c200.get('/x');
    expect(getConnectionState()).toBe('connected');
  });
});
"""

PROBE_CONNECTION = r"""
import * as React from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import {
  getConnectionState,
  setConnectionState,
  subscribeConnectionState,
  useConnectionState,
} from '../src/live/connection';

vi.setConfig({ testTimeout: 60000 });

function Probe() {
  const state = useConnectionState();
  return <span data-testid="tt-live-conn">{state}</span>;
}

describe('live/connection', () => {
  it('初值是 connected', () => {
    setConnectionState('connected');
    expect(getConnectionState()).toBe('connected');
  });

  it('订阅者：变化时被通知、值没变时不通知、退订后不再通知', () => {
    setConnectionState('connected');
    let calls = 0;
    const off = subscribeConnectionState(() => { calls += 1; });
    setConnectionState('disconnected');
    expect(calls).toBe(1);
    expect(getConnectionState()).toBe('disconnected');
    setConnectionState('disconnected');
    expect(calls).toBe(1);
    setConnectionState('connected');
    expect(calls).toBe(2);
    off();
    setConnectionState('disconnected');
    expect(calls).toBe(2);
    setConnectionState('connected');
  });

  it('useConnectionState：状态变化时组件跟着重渲染', () => {
    setConnectionState('connected');
    cleanup();
    render(<Probe />);
    expect(screen.getByTestId('tt-live-conn').textContent).toBe('connected');
    act(() => { setConnectionState('disconnected'); });
    expect(screen.getByTestId('tt-live-conn').textContent).toBe('disconnected');
    act(() => { setConnectionState('connected'); });
    expect(screen.getByTestId('tt-live-conn').textContent).toBe('connected');
    cleanup();
  });
});
"""

PROBE_API = r"""
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '../src/api';
import { setLiveClientForTests } from '../src/live/mode';

vi.setConfig({ testTimeout: 60000 });

type Call = { path: string; query: Record<string, string | undefined> | undefined; timeoutSeconds: number | undefined };
const calls: Call[] = [];
let nextData: any = { v: 0 };
const fakeClient = {
  get(path: string, query?: Record<string, string | undefined>, timeoutSeconds?: number) {
    calls.push({ path, query, timeoutSeconds });
    return Promise.resolve({
      ok: true, exit_code: 0, data: nextData, output: [], messages: [], command: [], elapsed_ms: 3,
    });
  },
};

beforeEach(() => {
  calls.length = 0;
  nextData = { v: 0 };
  window.location.hash = '';
  setLiveClientForTests(fakeClient as any);
});
afterEach(() => {
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

const ROWS = [
  { name: 'getMeta', run: () => api.getMeta(), path: '/api/v1/meta', timeout: 15 },
  { name: 'getStatus', run: () => api.getStatus(), path: '/api/v1/status', timeout: 30 },
  { name: 'getAttempt', run: () => api.getAttempt('a/b', 'x?y'), path: '/api/v1/attempts/a%2Fb/x%3Fy', timeout: 30 },
  { name: 'readFile(不带 cursor)', run: () => api.readFile('t1', 'a1', 'p.md'),
    path: '/api/v1/attempts/t1/a1/file', query: { path: 'p.md' }, timeout: 60 },
  { name: 'readFile(带 cursor)', run: () => api.readFile('t1', 'a1', 'p.md', 'c-1'),
    path: '/api/v1/attempts/t1/a1/file', query: { path: 'p.md', cursor: 'c-1' }, timeout: 60 },
  { name: 'getRoles', run: () => api.getRoles(), path: '/api/v1/roles', timeout: 30 },
  { name: 'getProfiles', run: () => api.getProfiles(), path: '/api/v1/profiles', timeout: 30 },
  { name: 'getPresets', run: () => api.getPresets(), path: '/api/v1/presets', timeout: 30 },
  { name: 'diffPresets', run: () => api.diffPresets('x y', 'z'), path: '/api/v1/presets/x%20y/diff/z', timeout: 30 },
  { name: 'getRuntimes', run: () => api.getRuntimes(), path: '/api/v1/runtimes', timeout: 30 },
  { name: 'getPlugins', run: () => api.getPlugins(), path: '/api/v1/plugins', timeout: 30 },
  { name: 'getHistory', run: () => api.getHistory(), path: '/api/v1/config/history', timeout: 30 },
  { name: 'getUsage', run: () => api.getUsage(), path: '/api/v1/usage', timeout: 120 },
  { name: 'listSecrets', run: () => api.listSecrets(), path: '/api/v1/secrets', timeout: 120 },
  { name: 'getHistoryEntry', run: () => api.getHistoryEntry(41), path: '/api/v1/config/history/41', timeout: 30 },
  { name: 'getPlugin', run: () => api.getPlugin('docs-checks'), path: '/api/v1/plugins/docs-checks', timeout: 30 },
];

describe('api.ts 的 15 个读函数（注入 fake client）', () => {
  for (const row of ROWS) {
    it(row.name + ' → GET ' + row.path + '，时限 ' + row.timeout, async () => {
      const env = await row.run();
      expect(calls.length).toBe(1);
      expect(calls[0].path).toBe(row.path);
      expect(calls[0].timeoutSeconds).toBe(row.timeout);
      if (row.query) {
        expect(calls[0].query).toEqual(row.query);
      } else {
        const q = calls[0].query;
        expect(q == null || Object.keys(q).length === 0).toBe(true);
      }
      if (row.name === 'readFile(不带 cursor)') {
        expect(calls[0].query && calls[0].query.cursor).toBeUndefined();
      }
      expect(env.ok).toBe(true);
    });
  }

  it('getMeta：version 带 pi_dispatch 前缀 → kit_version 去掉前缀', async () => {
    nextData = { version: 'pi_dispatch 2.12.0', repo_name: 'demo-repo' };
    const env = await api.getMeta();
    expect(env.ok).toBe(true);
    expect(env.data).toEqual({ kit_version: '2.12.0', repo_name: 'demo-repo' });
  });

  it('getMeta：对不上 pi_dispatch 前缀就原样放进 kit_version', async () => {
    nextData = { version: '3.1', repo_name: 'r' };
    const env = await api.getMeta();
    expect(env.data).toEqual({ kit_version: '3.1', repo_name: 'r' });
  });

  it('getHistoryEntry：resource 缺省 config、diff 缺省 null；本机文件条目带 sha', async () => {
    nextData = { number: 7, state: 'published', note: 'n1' };
    const a = await api.getHistoryEntry(7);
    expect(a.data).toEqual({ number: 7, resource: 'config', state: 'published', note: 'n1', diff: null });
    nextData = {
      number: 8, resource: 'local', state: 'published', note: null, diff: null,
      before_sha256: 'A', after_sha256: 'B',
    };
    const b = await api.getHistoryEntry(8);
    expect(b.data).toEqual({
      number: 8, resource: 'local', state: 'published', note: null, diff: null,
      before_sha256: 'A', after_sha256: 'B',
    });
  });

  it('getPlugin：allowed_permissions 为 null 时归一化成 []', async () => {
    nextData = { plugin_id: 'x', config: { enabled: null, allowed_permissions: null, missing_permissions: [] } };
    const env = await api.getPlugin('x');
    expect((env.data as any).config).toEqual({ enabled: null, allowed_permissions: [], missing_permissions: [] });
  });

  it('真实模式下 ?mock= 的取值一律不生效（注入优先，不读夹具）', async () => {
    window.location.hash = '#/status?mock=error';
    const env = await api.getStatus();
    expect(env.ok).toBe(true);
    expect(calls.length).toBe(1);
    window.location.hash = '#/status?mock=empty';
    const env2 = await api.getStatus();
    expect(env2.ok).toBe(true);
    expect(env2.data).toEqual({ v: 0 });
  });
});

describe('api.ts 的夹具分支保持原样（未注入）', () => {
  it('getAttempt 命中夹具；getHistoryEntry/getPlugin 的 command、报错原文与深拷贝', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '';
    const a = await api.getAttempt('logs-cat', 'attempt-002');
    expect(a.ok).toBe(true);
    const m = await api.getMeta();
    expect(m.ok).toBe(true);
    expect(m.command).toEqual(['--version']);
    const e = await api.getHistoryEntry(42);
    expect(e.ok).toBe(true);
    expect(e.command).toEqual(['config', 'history', 'show', '42']);
    expect((e.data as any).resource).toBe('config');
    expect((e.data as any).diff.length).toBe(2);
    (e.data as any).diff.push({ key: 'x', old: 1, new: 2 });
    const e2 = await api.getHistoryEntry(42);
    expect((e2.data as any).diff.length).toBe(2);
    const miss = await api.getHistoryEntry(7);
    expect(miss.ok).toBe(false);
    expect(miss.exit_code).toBe(2);
    expect(miss.messages).toEqual(['ERROR 夹具里没有这份数据：7']);
    expect(miss.command).toEqual(['config', 'history', 'show', '7']);
    const p = await api.getPlugin('decisions');
    expect(p.ok).toBe(true);
    expect(p.command).toEqual(['plugins', 'show', 'decisions']);
    const pmiss = await api.getPlugin('nope');
    expect(pmiss.messages).toEqual(['ERROR 夹具里没有这份数据：nope']);
    expect(pmiss.command).toEqual(['plugins', 'show', 'nope']);
  });

  it('error 开关照旧：报错原文信封', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/status?mock=error';
    const env = await api.getStatus();
    expect(env.ok).toBe(false);
    expect(env.exit_code).toBe(2);
    expect(env.messages).toEqual(['ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied']);
    expect(env.command).toEqual(['status']);
  });

  it('getMetaNow 一字未改：同步返回夹具，不受注入影响', () => {
    const before = api.getMetaNow();
    setLiveClientForTests(fakeClient as any);
    const after = api.getMetaNow();
    expect(after).toEqual({ kit_version: '2.12.0', repo_name: 'demo-repo' });
    expect(after).toEqual(before);
  });
});
"""

PROBE_TASKS = r"""
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { findAttemptFixture } from '../src/mock/tasks-attempts';
import { findFileFixture } from '../src/mock/tasks-files';
import { subscribeMockEvents } from '../src/mock/tasks-live';

vi.setConfig({ testTimeout: 60000 });

const hoisted = vi.hoisted(() => ({ calls: [] as any[] }));
vi.mock('../src/live/mode', () => ({
  liveModeIsReal: () => true,
  liveClient: () => ({
    get(path: string, query?: any, timeoutSeconds?: number) {
      hoisted.calls.push({ path, query, timeoutSeconds });
      return Promise.resolve({
        ok: false, exit_code: 2, data: null, output: [],
        messages: ['ERROR 夹具里没有这份数据：x/y'], command: ['logs', 'show', 'x/y'], elapsed_ms: 0,
      });
    },
  }),
  setLiveClientForTests: () => {},
}));

import { readAttempt, readAttemptFile } from '../src/pages/tasks/tasks-data';

beforeEach(() => {
  hoisted.calls.length = 0;
  window.location.hash = '';
});

describe('真实模式下 tasks-data 不取夹具兜底', () => {
  it('先证明夹具键存在（ui-readonly-api/attempt-001 与它的事件页在夹具里）', () => {
    expect(findAttemptFixture('ui-readonly-api', 'attempt-001')).not.toBeNull();
    expect(findFileFixture('ui-readonly-api', 'attempt-001', 'events.jsonl')).not.toBeNull();
  });

  it('readAttempt：api 报缺就原样返回它的信封，不落回夹具', async () => {
    const env = await readAttempt('ui-readonly-api', 'attempt-001');
    expect(env.ok).toBe(false);
    expect(env.messages).toEqual(['ERROR 夹具里没有这份数据：x/y']);
    expect(hoisted.calls.length).toBe(1);
    expect(hoisted.calls[0].path).toBe('/api/v1/attempts/ui-readonly-api/attempt-001');
    expect(hoisted.calls[0].timeoutSeconds).toBe(30);
  });

  it('readAttemptFile：同上，路径进查询', async () => {
    const env = await readAttemptFile('ui-readonly-api', 'attempt-001', 'events.jsonl');
    expect(env.ok).toBe(false);
    expect(env.messages).toEqual(['ERROR 夹具里没有这份数据：x/y']);
    expect(hoisted.calls.length).toBe(1);
    expect(hoisted.calls[0].path).toBe('/api/v1/attempts/ui-readonly-api/attempt-001/file');
    expect(hoisted.calls[0].query).toEqual({ path: 'events.jsonl' });
    expect(hoisted.calls[0].timeoutSeconds).toBe(60);
  });
});

describe('真实模式下 subscribeMockEvents 不模拟事件行（SSE 片会推翻）', () => {
  it('返回退订函数；3.5 秒后没有任何事件行、没有挂起的计时器', async () => {
    vi.useFakeTimers();
    try {
      const lines: any[] = [];
      const stop = subscribeMockEvents('ui-readonly-api', 'attempt-001', (batch) => {
        lines.push(...batch);
      });
      expect(typeof stop).toBe('function');
      await vi.advanceTimersByTimeAsync(3500);
      expect(lines.length).toBe(0);
      expect(vi.getTimerCount()).toBe(0);
      stop();
    } finally {
      vi.useRealTimers();
    }
  });
});
"""

PROBE_SPECS = {
    "mode": (PROBE_MODE, (MODE_REL,)),
    "transport": (PROBE_TRANSPORT, (TRANSPORT_REL, CONNECTION_REL)),
    "connection": (PROBE_CONNECTION, (CONNECTION_REL,)),
    "api": (PROBE_API, (MODE_REL, API_REL)),
    "tasks": (PROBE_TASKS, (TASKS_DATA_REL, TASKS_LIVE_REL)),
}
PROBE_ORDER = ("mode", "transport", "connection", "api", "tasks")


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


def build_probe_source(key):
    return PROBE_SPECS[key][0]


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针
# ---------------------------------------------------------------------------

PIPELINE_BUDGET = 1500
STEP_CAPS = {
    "npm ci": 300,
    "npm test": 300,
    "npm run build": 200,
    "check-live-build": 480,
    "probe": 120,
}


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
        self.dist_scan = None


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
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
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
    return env


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not any((REPO_ROOT / LIVE_REL).glob("*.ts")):
        pipe.reason = ("候选里还没有 src/live/*.ts 的任何源码文件（基线），没有东西可测，未调用 npm；"
                       "候选写出 src/live/ 后，流水线才会运行 npm ci、Vitest、构建、三取值检查和探针")
        return pipe
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        pipe.reason = f"找不到 npm 或 node（shutil.which：npm={npm}，node={node}）"
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
        ci = run_step("npm ci", [npm, "ci"])
        if ci is not None and ci.code == 0:
            test = run_step("npm test", [npm, "test"])
            run_step("npm run build", [npm, "run", "build"])
            # B1 / D01–D03：build 一完就扫 dist 产物——真实模式标记串与传输层特征串都得在（此时 dist 还没被
            # check-live-build 的三次构建覆盖）
            dist = WEB / "dist"
            dist_files = [p for p in dist.rglob("*") if p.is_file()] if dist.is_dir() else []
            scan = {"ran": bool(dist_files), "themis-live-real": False, "same-origin": False}
            for path in dist_files:
                try:
                    blob = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if "themis-live-real" in blob:
                    scan["themis-live-real"] = True
                if "same-origin" in blob:
                    scan["same-origin"] = True
            pipe.dist_scan = scan
            if (REPO_ROOT / CHECK_BUILD_REL).is_file():
                run_step("check-live-build", [node, "scripts/check-live-build.mjs"])
            else:
                pipe.stopped_reason = f"{CHECK_BUILD_REL} 不存在，三取值构建检查未运行"
            uid = uuid.uuid4().hex[:12]
            for key in PROBE_ORDER:
                missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                name = f"probe-{uid}-t027-{key}.test.tsx"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                written.append(path)
                path.write_text(build_probe_source(key), encoding="utf-8", newline="\n")
                pipe.probe_files[key] = name
                run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        elif ci is not None:
            pipe.stopped_reason = "npm ci 失败，后续步骤未运行"
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
    want = probe_count(PROBE_SPECS[key][0])
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m and int(m.group(1)) >= want, f"探针 {key} 应至少有 {want} 条通过：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), f"探针 {key} 有失败或跳过：\n{step.tail}"


# ---------------------------------------------------------------------------
# P 系列：流水线断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01–V03、D13：npm ci、npm test（全绿）、npm run build（tsc --noEmit + vite build）、
    node scripts/check-live-build.mjs（三种 NODE_ENV 取值、产物含真实标记）都退出 0；
    依赖文件一个字节没动。"""
    for name in ("npm ci", "npm test", "npm run build", "check-live-build"):
        step = assert_step_ok(pipeline, name)
        if name == "npm test":
            m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
            assert m, f"npm test 输出里没有通过计数：\n{step.tail}"
            assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), \
                f"npm test 有失败或跳过：\n{step.tail}"
    assert pipeline.digests_before == pipeline.digests_after, \
        "npm 流水线不许改动 desktop/web/package.json 与 package-lock.json"
    assert not pipeline.gate_probe_left, "gate-probe/ 目录在探针后应清掉"


def test_p1b_build_dist_has_transport_markers(pipeline):
    """P1b / D01、D02、D03（B1）：npm run build 的产物里既有真实模式标记串，也有传输层特征串
    same-origin——证明 transport 真进了生产产物，不是只有 mode.ts 的标记串在（否则 liveClient()
    恒为 null、transport 是死代码，生产构建里 15 个读函数仍走夹具，本片 Goal 第一句落空）。"""
    assert pipeline.ran, pipeline.reason
    scan = pipeline.dist_scan
    assert scan and scan["ran"], "npm run build 之后没有可扫描的 dist 产物"
    assert scan["themis-live-real"], "dist 产物里没有 'themis-live-real'（真实模式标记没进产物）"
    assert scan["same-origin"], "dist 产物里没有 'same-origin'（传输层没进产物）"


def test_p2_probe_mode(pipeline):
    """P2a / D02：mode 探针全绿。"""
    assert_probe_ok(pipeline, "mode")


def test_p3_probe_transport(pipeline):
    """P2b / D03–D05：transport 探针全绿。"""
    assert_probe_ok(pipeline, "transport")


def test_p4_probe_connection(pipeline):
    """P2c / D06：connection 探针全绿。"""
    assert_probe_ok(pipeline, "connection")


def test_p5_probe_api(pipeline):
    """P2d / D07、D08、D10：api 探针全绿。"""
    assert_probe_ok(pipeline, "api")


def test_transitional_p7_probe_tasks(pipeline):
    """过渡 / D11：tasks-data 不落夹具与 subscribeMockEvents 不模拟的探针——SSE 片会推翻后半。"""
    assert_probe_ok(pipeline, "tasks")
