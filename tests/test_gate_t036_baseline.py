"""T036 战前门禁：桌面端前端第 3 片——实时状态、作业与日志跟随（A 片：事件流客户端与页面实时覆盖）的
黑盒基准测试（合同 t036-desktop-web-live.v1，基线 d4d740dbb7）。

被测对象是 ``desktop/web/``：新增 ``src/live/events.ts``（事件流客户端）、``src/live/useLiveStatus.ts``
（实时 status 钩子）与执行端测试 ``tests/live-events.test.ts``、``tests/live-events-hook.test.tsx``、
``tests/live-pages-live.test.tsx``；改 ``src/live/connection.ts``（union 末尾追加 ``| 'reconnecting'``、
新增重连次数的读取导出）、``src/pages/OverviewPage.tsx``、``src/pages/TasksPage.tsx``（实时覆盖接线）。

基线（d4d740dbb7）上 ``events.ts``、``useLiveStatus.ts`` 与三份执行端测试不存在、connection.ts 仍只有
两个连接取值且没有重连次数导出、两个页面还没有 ``useLiveStatus`` 接线，所以本文件的失败落在
「文件不存在」「导出不在」「记号不在」「探针断言红」上，不是导入、收集或语法错误：模块级只导入标准库，
所有仓库文件的读取都发生在用例函数里；流水线（npm ci、npm test、npm run build、check:contract、探针）
放在 ``pipeline`` 会话级夹具里（全量 pytest 默认跳过，点名运行本文件才跑）。

结构（编号大致对应合同 DoD 的 D01–D14）：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：新文件在位（D01）；connection.ts 三取值与
  重连次数导出（D07）；events.ts 对外接口与默认建流路径（D01–D06）；useLiveStatus 形状（D08）；
  两个页面的接线记号与 api 白名单（D09、D10）；禁词扫描（D12）；执行端测试的最小覆盖（D13）；
  非目标静态项：tasks/ 仍 17 个文件、mock 仍 14 份 JSON、顶层仍 9 个 *Page.tsx、mode.ts 导出仍四个、
  重连次数不经 useShellConnection/App（D11 的静态面）。
- 流水线断言（``test_p*``，``pipeline`` 会话级夹具）：npm ci（node_modules 已在时跳过重装；失败再试
  --offline）、npm test（全绿）、npm run build、npm run check:contract；再把探针逐份写成
  ``gate-probe/probe-<唯一标识>-t036-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，
  ``finally`` 里删除。

探针（Vitest + jsdom，全部自包含，辅助函数不跨文件共享；只许用注入口
``setEventStreamFactoryForTests``、``setConnectionState``/``setReconnectCount`` 与假流，不 mock 被测
模块本身；真实模式的开关用 ``vi.mock('../src/live/mode')`` 把 ``liveModeIsReal`` 置真、``liveClient``
置 null（api 走夹具分支），与合同第 7 步给执行端规定的口径一致）：

- events：``createLiveEvents`` 纯逻辑——序号去重与过期丢弃、没 snapshot 时 update 丢弃、服务重启后
  snapshot 变小整份替换、序号解析不出非负整数丢弃、data 非法 JSON 丢弃、非七字段信封按 ok:false
  处理、ok:false 不覆盖且序号照常推进、error 后关原生流并按退避自己重连（下限 3000、指数增长、
  上限 30000、抖动只往后加）、重连后靠 snapshot 重建、多订阅者一条流且最后一个离开关流清计时器
  清次数（D01–D06）。
- default：默认实例 ``liveEvents``——第一个订阅者建流、最后一个离开关流；出错排重连期间
  connection.ts 读到 ``reconnecting`` 与次数 1、收到 snapshot 清零并写 ``connected``；最后一个订阅者
  离开清掉待跑的重连计时器、``reconnecting`` 时写 ``disconnected``；connection.ts 新导出值没变不通知；
  ``setEventStreamFactoryForTests(undefined)`` 恢复默认建流（真原生类连 ``/api/v1/events``）（D05、D07）。
- fixture：夹具模式（vitest 天然为假）——订阅是空操作：不建流、不排计时器、getStatus 为空、退订可
  重复调用；``useLiveStatus`` 原样返回 initial 且不订阅（D01、D08）。
- hooklive：``useLiveStatus`` 真实模式——还没推送时返回 initial 且 rerender 换 initial 用最新值；
  ok:true 推送后返回最新、ok:false 与重复/过期不动；卸载后最后一个订阅者离开流被关掉（D08）。
- pages：页面接线——总览页首屏一次性读、收到 snapshot/update 后运行中的「工具调用 / 已用」跟着变、
  过期与 ok:false 不动；任务页列表的用时跟着变；详情页有同 attempt 的行时覆盖、没有时保留首屏行
  （D09、D10）。

本片不写任何退役要求（站主 2026-11-13 已按名字退役 T027 s30 与 T032 s09 的 connection.ts 项；
T027 S05 与 T034 过渡 s13 的正则无尾锚，union 末尾追加仍匹配）。

合同没写死、门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：
connection.ts 的重连次数由 events.ts 的默认实例写入（「重连次数只在这里读」指 UI 只从 connection.ts
读，写入方是事件流），探针按此断言；页面探针里跨用例共享的默认实例状态只做相对变化断言，
不依赖单例的初值。
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
TESTS_REL = f"{WEB_REL}/tests"

# 合同 Scope 的新增非测试源码（allowed_new_files）
NEW_SOURCE_FILES = (f"{SRC_REL}/live/events.ts", f"{SRC_REL}/live/useLiveStatus.ts")
# 合同 Scope 的新增执行端测试
EXECUTOR_TESTS = (
    f"{TESTS_REL}/live-events.test.ts",
    f"{TESTS_REL}/live-events-hook.test.tsx",
    f"{TESTS_REL}/live-pages-live.test.tsx",
)

EVENTS_REL = f"{SRC_REL}/live/events.ts"
USE_LIVE_STATUS_REL = f"{SRC_REL}/live/useLiveStatus.ts"
CONNECTION_REL = f"{SRC_REL}/live/connection.ts"
MODE_REL = f"{SRC_REL}/live/mode.ts"
API_REL = f"{SRC_REL}/api.ts"
APP_REL = f"{SRC_REL}/App.tsx"
SHELL_HOOK_REL = f"{SRC_REL}/shell/useShellConnection.ts"
OVERVIEW_REL = f"{SRC_REL}/pages/OverviewPage.tsx"
TASKS_PAGE_REL = f"{SRC_REL}/pages/TasksPage.tsx"
TASKS_DATA_REL = f"{SRC_REL}/pages/tasks/tasks-data.ts"
TASKS_LIVE_MOCK_REL = f"{SRC_REL}/mock/tasks-live.ts"

# T009 钉住的三页可读函数白名单（本片两个页面只许从这里引值）
READERS_WHITELIST = ("getStatus", "getHistory", "getMeta", "getMetaNow")

NETWORK_RE = re.compile(r"(?<![A-Za-z0-9_$])(?:fetch|XMLHttpRequest|EventSource|WebSocket)(?![A-Za-z0-9_$])")
SINK_WORDS = ("dangerouslySetInnerHTML", "innerHTML", "outerHTML", "insertAdjacentHTML", "eval(",
              "new Function", "document.write", "srcdoc", "createContextualFragment", "DOMParser")
HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b(?![-\w])")

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


# TS 注释剥离（与 T010/T034 的 _TS_COMMENT 同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def comment_texts(text):
    return [m.group(0) for m in _TS_COMMENT.finditer(text)]


def blank_ts_comments(text):
    return _TS_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_new_files_present():
    """S01 / D01、第 2 步：新源码文件 events.ts、useLiveStatus.ts 与三份执行端测试都在（基线上没有，本条先红）。"""
    need_new_sources()
    for rel in EXECUTOR_TESTS:
        need_file(rel)


def test_s02_connection_three_states_and_reconnect_count():
    """S02 / D07、兼容性：connection.ts——ConnectionState 三取值且 ``'reconnecting'`` 追加在 union 同一行的
    末尾（顺序仍是 connected、disconnected 在前）；四个原有导出与 useSyncExternalStore 保留；新增
    getReconnectCount / setReconnectCount / subscribeReconnectCount。"""
    need_file(CONNECTION_REL)
    text = read_rel(CONNECTION_REL)
    m = re.search(r"export type ConnectionState = ([^\n]*)", text)
    assert m, "connection.ts 应有 export type ConnectionState = …"
    assert re.fullmatch(r"['\"]connected['\"]\s*\|\s*['\"]disconnected['\"]\s*\|\s*['\"]reconnecting['\"]\s*;?",
                        m.group(1).strip()), (
        "ConnectionState 的三个取值应写在同一行，顺序为 'connected' | 'disconnected' | 'reconnecting'，"
        "不许加别的取值（T027 S05 与 T034 过渡 s13 的无尾锚正则靠这个形状继续匹配）")
    for name in ("getConnectionState", "subscribeConnectionState", "useConnectionState", "setConnectionState"):
        assert re.search(rf"export function {name}\(", text), f"connection.ts 应保留导出函数 {name}"
    assert "useSyncExternalStore" in text, "useConnectionState 应仍基于 useSyncExternalStore"
    for name in ("getReconnectCount", "setReconnectCount", "subscribeReconnectCount"):
        assert re.search(rf"export function {name}\(", text), f"connection.ts 应新增导出函数 {name}"


def test_s03_events_module_shape():
    """S03 / D01–D06、第一节：events.ts 的对外接口——四个 interface、createLiveEvents、liveEvents、
    setEventStreamFactoryForTests；收事件只用 addEventListener（不用 onmessage）；默认建流连
    /api/v1/events；开关只用 liveModeIsReal（不认 liveClient）；退避常量 3000 与上限 30000 在。"""
    need_file(EVENTS_REL)
    code = strip_ts_comments(read_rel(EVENTS_REL))
    for name in ("LiveStreamEvent", "LiveStreamHandle", "LiveEventsOptions", "LiveEvents"):
        assert re.search(rf"export interface {name}\b", code), f"events.ts 应导出 interface {name}"
    assert re.search(r"export function createLiveEvents\(", code), "events.ts 应导出 createLiveEvents()"
    assert re.search(r"export const liveEvents\b", code), "events.ts 应导出默认实例 liveEvents"
    assert re.search(r"export function setEventStreamFactoryForTests\(", code), \
        "events.ts 应导出 setEventStreamFactoryForTests()"
    assert "addEventListener" in code, "收事件应用 addEventListener('snapshot' | 'update')"
    assert "onmessage" not in code, "onmessage 收不到带名字的事件，不许用"
    assert "'snapshot'" in code and "'update'" in code, "事件名 snapshot 与 update 应照服务端写"
    assert re.search(r"new EventSource\(", code), "默认建流应用原生类（探针里验证 URL）"
    assert re.search(r"['\"]/api/v1/events['\"]", code), "默认建流应连同源相对路径 /api/v1/events"
    assert "liveModeIsReal" in code, "默认实例的开关只应是 liveModeIsReal()"
    assert not re.search(r"\bliveClient\b", code), "events.ts 不许用 liveClient 判定开关（测试注入不算真实模式）"
    assert re.search(r"\b3000\b", code), "退避下限常量 3000ms 应在（对齐服务端 retry）"
    assert re.search(r"\b30000\b", code), "退避上限 30000ms 应在"


def test_s04_use_live_status_shape():
    """S04 / D08、第一节：useLiveStatus——签名 useLiveStatus(initial: StatusData): StatusData；
    用 useSyncExternalStore 订阅 liveEvents；夹具模式判定用 liveModeIsReal。"""
    need_file(USE_LIVE_STATUS_REL)
    code = strip_ts_comments(read_rel(USE_LIVE_STATUS_REL))
    assert re.search(r"export function useLiveStatus\(\s*initial:\s*StatusData\s*\)\s*:\s*StatusData", code, re.S), \
        "useLiveStatus 的签名应是 (initial: StatusData): StatusData"
    assert "useSyncExternalStore" in code, "useLiveStatus 应基于 useSyncExternalStore"
    assert "liveEvents" in code, "useLiveStatus 应订阅 liveEvents 的稳定引用"
    assert "liveModeIsReal" in code, "夹具模式应原样返回 initial（判定只用 liveModeIsReal）"
    assert re.search(r"['\"]\.\./api['\"]", code) and "StatusData" in code, "StatusData 类型应从 ../api 引"


def test_s05_overview_wiring():
    """S05 / D09、第一节：OverviewPage——loadOverview / isOverviewEmpty 仍是模块级命名函数；api 只引
    白名单读函数；T034 s08 的记号（'—'、· kit 、getMetaNow、useShellConnection()）保留；
    实时覆盖由本文件内调 useLiveStatus 的小组件承载；不出现带引号的状态码字面量。"""
    need_file(OVERVIEW_REL)
    code = strip_ts_comments(read_rel(OVERVIEW_REL))
    assert re.search(r"const loadOverview", code), "load 应仍是模块级命名函数（T009 page_wiring_problems）"
    assert re.search(r"const isOverviewEmpty", code), "isEmpty 应仍是模块级命名函数（T009）"
    assert re.search(r"['\"]—['\"]", code), "真实模式的占位「—」应保留"
    assert "· kit " in code, "「仓库名 · kit 版本」的模板应保留"
    assert "getMetaNow" in code, "夹具模式的初值应仍来自 getMetaNow()"
    assert re.search(r"useShellConnection\(", code), "useShellConnection() 的调用应保留（T034 s08）"
    assert re.search(r"useLiveStatus\(", code), "实时覆盖应由本文件内调 useLiveStatus 的小组件承载"
    assert re.search(r"from\s+['\"]\.\./live/[^'\"]*['\"]", code), "useLiveStatus 应从 ../live/ 引入"
    problems = []
    for m in re.finditer(r"""import\s+([^;]*?)\s+from\s+['"]\.\./api['"]""", code, re.S):
        for item in m.group(1).strip().lstrip("{").rstrip("}").split(","):
            item = item.strip()
            if not item or item.startswith("type "):
                continue
            if item not in READERS_WHITELIST:
                problems.append(f"OverviewPage 从 ../api 引了白名单外的值：{item}（import：{m.group(0).strip()}）")
    fail_if(problems, "OverviewPage 的 api 导入应在读函数白名单内")
    assert not re.search(r"['\"]\d{3}['\"]", code), "OverviewPage 不许出现带引号的状态码字面量"


def test_s06_tasks_wiring():
    """S06 / D10、第一节：TasksPage——PageFrame、from './tasks/'、默认导出保留；实时覆盖接 useLiveStatus；
    api 只引白名单读函数；不出现带引号的状态码字面量。"""
    need_file(TASKS_PAGE_REL)
    code = strip_ts_comments(read_rel(TASKS_PAGE_REL))
    assert "PageFrame" in code, "PageFrame 应保留（tasks-static 钉着）"
    assert re.search(r"""from\s+['"]\.\/tasks\/""", code), "from './tasks/' 应保留（tasks-static 钉着）"
    assert re.search(r"export default", code), "默认导出应保留（tasks-static 钉着）"
    assert re.search(r"useLiveStatus\(", code), "列表与详情的实时覆盖应经 useLiveStatus"
    assert re.search(r"from\s+['\"]\.\./live/[^'\"]*['\"]", code), "useLiveStatus 应从 ../live/ 引入"
    problems = []
    for m in re.finditer(r"""import\s+([^;]*?)\s+from\s+['"]\.\./api['"]""", code, re.S):
        for item in m.group(1).strip().lstrip("{").rstrip("}").split(","):
            item = item.strip()
            if not item or item.startswith("type "):
                continue
            if item not in READERS_WHITELIST:
                problems.append(f"TasksPage 从 ../api 引了白名单外的值：{item}（import：{m.group(0).strip()}）")
    fail_if(problems, "TasksPage 的 api 导入应在读函数白名单内")
    assert not re.search(r"['\"]\d{3}['\"]", code), "TasksPage 不许出现带引号的状态码字面量"


def test_s07_forbidden_words_scan():
    """S07 / D12、兼容性：两个页面文件里四个网络接口名与注入词一处都不许出现（连注释都不许）、
    没有 role=status、没有内联 style、没有十六进制颜色；两个新 src/live/ 文件里网络接口名只许出现在
    代码里（注释里不写），注入词与 role=status / 内联 style / 十六进制颜色一处都不许出现。"""
    need_file(EVENTS_REL)
    need_file(USE_LIVE_STATUS_REL)
    problems = []
    for rel in (OVERVIEW_REL, TASKS_PAGE_REL):
        raw = read_rel(rel)
        code = strip_ts_comments(raw)
        for m in NETWORK_RE.finditer(raw):
            problems.append(f"{rel} 出现网络接口名 {m.group(0)}（连注释都不许）")
        for word in SINK_WORDS:
            if word in raw:
                problems.append(f"{rel} 出现注入词 {word}")
        if re.search(r"role\s*=\s*['\"]status['\"]", code):
            problems.append(f"{rel} 出现 role=status")
        if re.search(r"\bstyle\s*=\s*[{\"']", code):
            problems.append(f"{rel} 出现内联 style")
        for m in HEX_COLOR_RE.finditer(blank_ts_comments(raw)):
            problems.append(f"{rel} 出现十六进制颜色 {m.group(0)}")
    for rel in (EVENTS_REL, USE_LIVE_STATUS_REL):
        raw = read_rel(rel)
        code = strip_ts_comments(raw)
        for word in SINK_WORDS:
            if word in raw:
                problems.append(f"{rel} 出现注入词 {word}（连注释都不许）")
        for chunk in comment_texts(raw):
            for m in NETWORK_RE.finditer(chunk):
                problems.append(f"{rel} 的注释里出现网络接口名 {m.group(0)}（代码里可以，注释里不写）")
        if re.search(r"role\s*=\s*['\"]status['\"]", code):
            problems.append(f"{rel} 出现 role=status")
        if re.search(r"\bstyle\s*=\s*[{\"']", code):
            problems.append(f"{rel} 出现内联 style")
        for m in HEX_COLOR_RE.finditer(blank_ts_comments(raw)):
            problems.append(f"{rel} 出现十六进制颜色 {m.group(0)}")
    fail_if(problems, "本片文件的源码守卫扫描")


def test_s08_executor_tests_coverage():
    """S08 / D13、第 7 步：三份执行端测试在位、不用 skip/only/todo；最小覆盖记号与用例数
    （live-events 至少 7 条、hook 与页面各至少 2 条，对应合同第 7 步列的用例）。"""
    need_file(EVENTS_REL)
    specs = {
        "live-events.test.ts": (("createLiveEvents",), 7),
        "live-events-hook.test.tsx": (("useLiveStatus", "liveModeIsReal"), 2),
        "live-pages-live.test.tsx": (("setEventStreamFactoryForTests", "liveModeIsReal"), 2),
    }
    for name, (tokens, least) in specs.items():
        rel = f"{TESTS_REL}/{name}"
        need_file(rel)
        text = read_rel(rel)
        missing = [t for t in tokens if t not in text]
        assert not missing, f"{rel} 里缺少记号 {missing}（合同第 7 步要求的最小覆盖）"
        count = len(re.findall(r"^\s*it\(", text, re.M))
        assert count >= least, f"{rel} 应至少有 {least} 条 it（现 {count} 条）"
        bad = [pat for pat in (r"\.skip\s*\(", r"\.only\s*\(", r"\.todo\s*\(", r"\bxit\s*\(", r"describe\.only")
               if re.search(pat, text)]
        assert not bad, f"{rel} 里出现了 {bad}（合同 D13：不删用例、不削弱断言）"


def test_s09_non_goals_statics():
    """S09 / D11、Non-goals：tasks/ 仍恰好 17 个文件；mock 仍恰 14 份 JSON；src/pages 顶层仍 9 个
    *Page.tsx；mode.ts 导出集合仍四个；tasks-data.ts 与 mock/tasks-live.ts 不引 events.ts；
    重连次数不经 useShellConnection / App 往胶囊传。"""
    tasks_dir = SRC / "pages" / "tasks"
    need_file(f"{SRC_REL}/pages/tasks/tasks-data.ts")
    files = sorted(p.name for p in tasks_dir.iterdir() if p.is_file())
    assert len(files) == 17, f"src/pages/tasks/ 应仍恰好 17 个文件（现 {len(files)}：{files}）"
    jsons = sorted(p.name for p in (SRC / "mock").glob("*.json"))
    assert len(jsons) == 14, f"src/mock/ 应仍恰 14 份 JSON（现 {len(jsons)}）"
    pages = sorted(p.name for p in (SRC / "pages").glob("*Page.tsx"))
    assert len(pages) == 9, f"src/pages/ 顶层应仍恰 9 个 *Page.tsx（现 {len(pages)}：{pages}）"

    mode = read_rel(MODE_REL)
    code = strip_ts_comments(mode)
    names = set()
    for pattern in (r"export\s+(?:async\s+)?function\s+(\w+)",
                    r"export\s+(?:const|let|var)\s+(\w+)",
                    r"export\s+(?:type|interface)\s+(\w+)"):
        names.update(mm.group(1) for mm in re.finditer(pattern, code))
    for em in re.finditer(r"export\s*\{([^}]*)\}", code):
        for item in em.group(1).split(","):
            name = item.strip()
            if name.startswith("type "):
                name = name[5:].strip()
            name = name.split(" as ")[-1].strip()
            if name:
                names.add(name)
    extra = names - {"liveModeIsReal", "liveClient", "setLiveClientForTests", "LiveClient"}
    assert not extra, f"mode.ts 的导出集合仍应只有四个，多出了 {sorted(extra)}"

    for rel in (TASKS_DATA_REL, TASKS_LIVE_MOCK_REL):
        text = read_rel(rel)
        assert not re.search(r"""from\s+['"][^'"]*live/events['"]""", text), \
            f"{rel} 不许引 events.ts（夹具兜底记号保留，属后续片）"
    for rel in (SHELL_HOOK_REL, APP_REL):
        assert "ReconnectCount" not in read_rel(rel), \
            f"{rel} 不许接重连次数（重连次数不经 useShellConnection 传给胶囊）"


# ---------------------------------------------------------------------------
# 探针源码（每份自包含：辅助函数不跨文件共享）
# ---------------------------------------------------------------------------

PROBE_EVENTS = r"""
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import statusJson from '../src/mock/status.json';
import { createLiveEvents } from '../src/live/events';

vi.setConfig({ testTimeout: 60000 });

class FakeStream {
  listeners = new Map<string, Set<(e: unknown) => void>>();
  closed = false;
  addEventListener(type: any, listener: any): void {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }
  removeEventListener(type: any, listener: any): void {
    this.listeners.get(type)?.delete(listener);
  }
  close(): void { this.closed = true; }
  emit(type: string, lastEventId: string, data: string): void {
    for (const l of this.listeners.get(type) ?? []) l({ type, lastEventId, data });
  }
}

function env(rows: unknown, ok = true): string {
  return JSON.stringify({
    ok, exit_code: ok ? 0 : null, data: ok ? rows : null, output: [],
    messages: ok ? [] : ['ERROR: 读 status 超时'], command: ['status'], elapsed_ms: 3,
  });
}

function rows(toolCalls: number, elapsedSeconds = 1146): any[] {
  return (statusJson as any[]).map((r) =>
    r.attempt === 'ui-readonly-api/attempt-001'
      ? { ...r, live: { tool_calls: toolCalls, elapsed_seconds: elapsedSeconds, deltas_since_last_tool: 0, long_idle: false } }
      : r);
}

function toolCallsOf(status: any): unknown {
  const row = status?.find?.((r: any) => r.attempt === 'ui-readonly-api/attempt-001');
  return row?.live?.tool_calls ?? 'none';
}

const delays: number[] = [];

function make(randomValue: number) {
  const streams: FakeStream[] = [];
  const options = {
    createStream: () => { const s = new FakeStream(); streams.push(s); return s as any; },
    setTimer: (fn: () => void, delayMs: number) => { delays.push(delayMs); return setTimeout(fn, delayMs); },
    clearTimer: (handle: unknown) => { clearTimeout(handle as any); },
    random: () => randomValue,
  };
  return { streams, options };
}

beforeEach(() => { delays.length = 0; vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); });

describe('createLiveEvents 纯逻辑（T036 合同第一节）', () => {
  it('snapshot 整份替换并重置基线；update 序号不大于基线或还没 snapshot 时丢弃', () => {
    const { streams, options } = make(0.5);
    const ev = createLiveEvents(options as any);
    let notified = 0;
    const off = ev.subscribe(() => { notified += 1; });
    const stream = streams[0]!;
    stream.emit('snapshot', '5', env(rows(37)));
    expect(toolCallsOf(ev.getStatus())).toBe(37);
    expect(notified).toBe(1);
    stream.emit('update', '5', env(rows(99)));
    expect(toolCallsOf(ev.getStatus())).toBe(37);
    stream.emit('update', '3', env(rows(98)));
    expect(toolCallsOf(ev.getStatus())).toBe(37);
    expect(notified).toBe(1);
    stream.emit('update', '6', env(rows(41)));
    expect(toolCallsOf(ev.getStatus())).toBe(41);
    expect(notified).toBe(2);
    off();

    const fresh = make(0.5);
    const ev2 = createLiveEvents(fresh.options as any);
    let notified2 = 0;
    ev2.subscribe(() => { notified2 += 1; });
    fresh.streams[0]!.emit('update', '9', env(rows(77)));
    expect(ev2.getStatus()).toBeNull();
    expect(notified2).toBe(0);
  });

  it('服务重启后 snapshot 序号变小：照样整份替换并把基线重置', () => {
    const { streams, options } = make(0.5);
    const ev = createLiveEvents(options as any);
    ev.subscribe(() => {});
    const stream = streams[0]!;
    stream.emit('snapshot', '100', env(rows(37)));
    stream.emit('snapshot', '2', env(rows(41)));
    expect(toolCallsOf(ev.getStatus())).toBe(41);
    stream.emit('update', '3', env(rows(45)));
    expect(toolCallsOf(ev.getStatus())).toBe(45);
    stream.emit('update', '2', env(rows(99)));
    expect(toolCallsOf(ev.getStatus())).toBe(45);
  });

  it('序号解析不出非负整数：丢弃（不改数据、不推进基线、不通知）', () => {
    const { streams, options } = make(0.5);
    const ev = createLiveEvents(options as any);
    let notified = 0;
    ev.subscribe(() => { notified += 1; });
    const stream = streams[0]!;
    stream.emit('snapshot', '5', env(rows(37)));
    stream.emit('update', 'abc', env(rows(50)));
    stream.emit('update', '-1', env(rows(51)));
    stream.emit('update', '', env(rows(52)));
    expect(toolCallsOf(ev.getStatus())).toBe(37);
    expect(notified).toBe(1);
    stream.emit('update', '6', env(rows(53)));
    expect(toolCallsOf(ev.getStatus())).toBe(53);
  });

  it('data 不是合法 JSON：丢弃；不是七字段信封：按 ok:false 处理（不覆盖、序号照常推进）', () => {
    const { streams, options } = make(0.5);
    const ev = createLiveEvents(options as any);
    let notified = 0;
    ev.subscribe(() => { notified += 1; });
    const stream = streams[0]!;
    stream.emit('snapshot', '5', env(rows(37)));
    stream.emit('update', '6', '{not json');
    expect(toolCallsOf(ev.getStatus())).toBe(37);
    stream.emit('update', '6', JSON.stringify({ foo: 1 }));
    expect(toolCallsOf(ev.getStatus())).toBe(37);
    expect(notified).toBe(1);
    stream.emit('update', '6', env(rows(60)));
    expect(toolCallsOf(ev.getStatus())).toBe(37);
    stream.emit('update', '7', env(rows(61)));
    expect(toolCallsOf(ev.getStatus())).toBe(61);
    expect(notified).toBe(2);
  });

  it('ok:false 的推送不覆盖已显示的数据，也不通知订阅者', () => {
    const { streams, options } = make(0.5);
    const ev = createLiveEvents(options as any);
    let notified = 0;
    ev.subscribe(() => { notified += 1; });
    const stream = streams[0]!;
    stream.emit('snapshot', '5', env(rows(37)));
    const seen = ev.getStatus();
    stream.emit('update', '6', env(null, false));
    expect(ev.getStatus()).toBe(seen);
    expect(notified).toBe(1);
  });

  it('error 后关掉原生流并自己排重连：下限 3000、指数增长、上限 30000、抖动只往后加', () => {
    const { streams, options } = make(0);
    const ev = createLiveEvents(options as any);
    ev.subscribe(() => {});
    const first = streams[0]!;
    first.emit('snapshot', '5', env(rows(37)));
    first.emit('error', '', '');
    expect(first.closed).toBe(true);
    expect(delays[0]).toBe(3000);
    expect(ev.getReconnectCount()).toBe(1);
    vi.advanceTimersByTime(3000);
    expect(streams.length).toBe(2);
    streams[1]!.emit('error', '', '');
    expect(delays[1]).toBe(6000);
    expect(ev.getReconnectCount()).toBe(2);
    vi.advanceTimersByTime(6000);
    streams[2]!.emit('error', '', '');
    expect(delays[2]).toBe(12000);
    vi.advanceTimersByTime(12000);
    streams[3]!.emit('error', '', '');
    expect(delays[3]).toBe(24000);
    vi.advanceTimersByTime(24000);
    streams[4]!.emit('error', '', '');
    expect(delays[4]).toBe(30000);
    vi.advanceTimersByTime(30000);
    streams[5]!.emit('error', '', '');
    expect(delays[5]).toBe(30000);

    const jittered = make(0.9999);
    const ev2 = createLiveEvents(jittered.options as any);
    ev2.subscribe(() => {});
    jittered.streams[0]!.emit('error', '', '');
    expect(delays.at(-1)).toBe(3999);
  });

  it('重连后靠 snapshot 重建（整份替换，不合并旧数据），次数清零', () => {
    const { streams, options } = make(0);
    const ev = createLiveEvents(options as any);
    ev.subscribe(() => {});
    streams[0]!.emit('snapshot', '5', env(rows(37)));
    streams[0]!.emit('error', '', '');
    expect(ev.getReconnectCount()).toBe(1);
    vi.advanceTimersByTime(3000);
    streams[1]!.emit('snapshot', '9', env(rows(41)));
    expect(toolCallsOf(ev.getStatus())).toBe(41);
    expect(ev.getReconnectCount()).toBe(0);
  });

  it('多订阅者只一条流；最后一个离开关流、清掉待跑的重连计时器、次数清零；退订可重复调用', () => {
    const { streams, options } = make(0);
    const ev = createLiveEvents(options as any);
    const off1 = ev.subscribe(() => {});
    const off2 = ev.subscribe(() => {});
    expect(streams.length).toBe(1);
    streams[0]!.emit('snapshot', '5', env(rows(37)));
    streams[0]!.emit('error', '', '');
    off1();
    expect(vi.getTimerCount()).toBeGreaterThanOrEqual(1);
    vi.advanceTimersByTime(31000);
    expect(streams.length).toBe(2);
    streams[1]!.emit('error', '', '');
    off2();
    expect(streams[1]!.closed).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
    expect(ev.getReconnectCount()).toBe(0);
    const before = streams.length;
    vi.advanceTimersByTime(61000);
    expect(streams.length).toBe(before);
    expect(() => { off2(); off2(); }).not.toThrow();
  });
});
"""

PROBE_DEFAULT = r"""
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../src/live/mode', () => ({
  liveModeIsReal: () => true,
  liveClient: () => null,
  setLiveClientForTests: () => {},
}));

import statusJson from '../src/mock/status.json';
import { liveEvents, setEventStreamFactoryForTests } from '../src/live/events';
import {
  getConnectionState,
  getReconnectCount,
  setConnectionState,
  setReconnectCount,
  subscribeReconnectCount,
} from '../src/live/connection';

vi.setConfig({ testTimeout: 60000 });

class FakeStream {
  listeners = new Map<string, Set<(e: unknown) => void>>();
  closed = false;
  addEventListener(type: any, listener: any): void {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }
  removeEventListener(type: any, listener: any): void {
    this.listeners.get(type)?.delete(listener);
  }
  close(): void { this.closed = true; }
  emit(type: string, lastEventId: string, data: string): void {
    for (const l of this.listeners.get(type) ?? []) l({ type, lastEventId, data });
  }
}

function env(rows: unknown, ok = true): string {
  return JSON.stringify({
    ok, exit_code: ok ? 0 : null, data: ok ? rows : null, output: [],
    messages: ok ? [] : ['ERROR: 读 status 超时'], command: ['status'], elapsed_ms: 3,
  });
}

function rows(toolCalls: number): any[] {
  return (statusJson as any[]).map((r) =>
    r.attempt === 'ui-readonly-api/attempt-001'
      ? { ...r, live: { tool_calls: toolCalls, elapsed_seconds: 1146, deltas_since_last_tool: 0, long_idle: false } }
      : r);
}

const offs: Array<() => void> = [];

function install() {
  setEventStreamFactoryForTests(() => new FakeStream() as any);
}

beforeEach(() => {
  vi.useFakeTimers();
  setConnectionState('connected');
  setReconnectCount(0);
  install();
});
afterEach(() => {
  for (const off of offs.splice(0)) off();
  setEventStreamFactoryForTests(undefined);
  setConnectionState('connected');
  setReconnectCount(0);
  vi.useRealTimers();
});

describe('liveEvents 默认实例（真实模式判定 + connection.ts 接线）', () => {
  it('第一个订阅者建流、多订阅者一条流、最后一个离开才关流', () => {
    const made: FakeStream[] = [];
    setEventStreamFactoryForTests(() => { const s = new FakeStream(); made.push(s); return s as any; });
    expect(made.length).toBe(0);
    const off1 = liveEvents.subscribe(() => {});
    offs.push(off1);
    expect(made.length).toBe(1);
    const off2 = liveEvents.subscribe(() => {});
    offs.push(off2);
    expect(made.length).toBe(1);
    off1();
    expect(made[0]!.closed).toBe(false);
    off2();
    expect(made[0]!.closed).toBe(true);
  });

  it('出错排重连：等待期 connection.ts 读到 reconnecting 与次数 1；重连后收到 snapshot 清零并写 connected', () => {
    const made: FakeStream[] = [];
    setEventStreamFactoryForTests(() => { const s = new FakeStream(); made.push(s); return s as any; });
    const off = liveEvents.subscribe(() => {});
    offs.push(off);
    made[0]!.emit('snapshot', '5', env(rows(37)));
    expect(getConnectionState()).toBe('connected');
    made[0]!.emit('error', '', '');
    expect(getConnectionState()).toBe('reconnecting');
    expect(getReconnectCount()).toBe(1);
    vi.advanceTimersByTime(4000);
    expect(made.length).toBe(2);
    made[1]!.emit('snapshot', '9', env(rows(41)));
    expect(getConnectionState()).toBe('connected');
    expect(getReconnectCount()).toBe(0);
  });

  it('最后一个订阅者离开：清掉待跑的重连计时器；状态是 reconnecting 时写 disconnected、次数清零', () => {
    const made: FakeStream[] = [];
    setEventStreamFactoryForTests(() => { const s = new FakeStream(); made.push(s); return s as any; });
    const off = liveEvents.subscribe(() => {});
    made[0]!.emit('snapshot', '5', env(rows(37)));
    made[0]!.emit('error', '', '');
    expect(getConnectionState()).toBe('reconnecting');
    off();
    expect(vi.getTimerCount()).toBe(0);
    expect(getConnectionState()).toBe('disconnected');
    expect(getReconnectCount()).toBe(0);
  });

  it('connection.ts 新导出 subscribeReconnectCount：值没变不通知、退订后不再通知', () => {
    let calls = 0;
    const off = subscribeReconnectCount(() => { calls += 1; });
    setReconnectCount(3);
    expect(calls).toBe(1);
    expect(getReconnectCount()).toBe(3);
    setReconnectCount(3);
    expect(calls).toBe(1);
    setReconnectCount(0);
    expect(calls).toBe(2);
    off();
    setReconnectCount(7);
    setReconnectCount(0);
    expect(calls).toBe(2);
  });

  it('setEventStreamFactoryForTests(undefined) 恢复默认建流：真实路径用原生类连 /api/v1/events', () => {
    class NativeStub {
      static urls: string[] = [];
      constructor(public url: string) { NativeStub.urls.push(url); }
      addEventListener(): void {}
      removeEventListener(): void {}
      close(): void {}
    }
    const g = globalThis as any;
    const prev = g.EventSource;
    g.EventSource = NativeStub;
    try {
      setEventStreamFactoryForTests(undefined);
      const off = liveEvents.subscribe(() => {});
      offs.push(off);
      expect(NativeStub.urls).toEqual(['/api/v1/events']);
      off();
    } finally {
      if (prev === undefined) delete g.EventSource;
      else g.EventSource = prev;
    }
  });
});
"""

PROBE_FIXTURE = r"""
import * as React from 'react';
import { cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import statusJson from '../src/mock/status.json';
import { liveEvents, setEventStreamFactoryForTests } from '../src/live/events';
import { useLiveStatus } from '../src/live/useLiveStatus';

vi.setConfig({ testTimeout: 60000 });

let created = 0;

class NoopStream {
  addEventListener(): void {}
  removeEventListener(): void {}
  close(): void {}
}

function installCounter() {
  created = 0;
  setEventStreamFactoryForTests(() => { created += 1; return new NoopStream() as any; });
}

function rows(toolCalls: number): any[] {
  return (statusJson as any[]).map((r) =>
    r.attempt === 'ui-readonly-api/attempt-001'
      ? { ...r, live: { tool_calls: toolCalls, elapsed_seconds: 1146, deltas_since_last_tool: 0, long_idle: false } }
      : r);
}

function HookProbe({ initial }: { initial: any[] }) {
  const status = useLiveStatus(initial);
  const row = status.find((r: any) => r.attempt === 'ui-readonly-api/attempt-001');
  return <span data-testid="tt-fix">{String(row?.live?.tool_calls ?? 'none')}</span>;
}

beforeEach(() => {
  vi.useFakeTimers();
  installCounter();
});
afterEach(() => {
  cleanup();
  setEventStreamFactoryForTests(undefined);
  vi.useRealTimers();
});

describe('夹具模式（liveModeIsReal 为假）', () => {
  it('订阅是空操作：不建流、不排计时器、getStatus 为空；退订可重复调用', () => {
    const off = liveEvents.subscribe(() => {});
    expect(created).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
    expect(liveEvents.getStatus()).toBeNull();
    expect(typeof off).toBe('function');
    off();
    expect(() => off()).not.toThrow();
    expect(created).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('useLiveStatus 原样返回 initial 且不订阅：换 initial 用新值', () => {
    const first = render(<HookProbe initial={rows(99)} />);
    expect(first.getByTestId('tt-fix').textContent).toBe('99');
    first.rerender(<HookProbe initial={rows(77)} />);
    expect(first.getByTestId('tt-fix').textContent).toBe('77');
    expect(created).toBe(0);
    expect(vi.getTimerCount()).toBe(0);
  });
});
"""

PROBE_HOOKLIVE = r"""
import * as React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../src/live/mode', () => ({
  liveModeIsReal: () => true,
  liveClient: () => null,
  setLiveClientForTests: () => {},
}));

import statusJson from '../src/mock/status.json';
import { setEventStreamFactoryForTests } from '../src/live/events';
import { useLiveStatus } from '../src/live/useLiveStatus';

vi.setConfig({ testTimeout: 60000 });

class FakeStream {
  listeners = new Map<string, Set<(e: unknown) => void>>();
  closed = false;
  addEventListener(type: any, listener: any): void {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }
  removeEventListener(type: any, listener: any): void {
    this.listeners.get(type)?.delete(listener);
  }
  close(): void { this.closed = true; }
  emit(type: string, lastEventId: string, data: string): void {
    for (const l of this.listeners.get(type) ?? []) l({ type, lastEventId, data });
  }
}

function env(rows: unknown, ok = true): string {
  return JSON.stringify({
    ok, exit_code: ok ? 0 : null, data: ok ? rows : null, output: [],
    messages: ok ? [] : ['ERROR: 读 status 超时'], command: ['status'], elapsed_ms: 3,
  });
}

function rows(toolCalls: number): any[] {
  return (statusJson as any[]).map((r) =>
    r.attempt === 'ui-readonly-api/attempt-001'
      ? { ...r, live: { tool_calls: toolCalls, elapsed_seconds: 1146, deltas_since_last_tool: 0, long_idle: false } }
      : r);
}

let stream: FakeStream | null = null;

function install() {
  stream = null;
  setEventStreamFactoryForTests(() => { stream = new FakeStream(); return stream as any; });
}

function push(type: 'snapshot' | 'update', id: string, data: string) {
  act(() => { stream?.emit(type, id, data); });
}

function HookProbe({ initial }: { initial: any[] }) {
  const status = useLiveStatus(initial);
  const row = status.find((r: any) => r.attempt === 'ui-readonly-api/attempt-001');
  return <span data-testid="tt-live">{String(row?.live?.tool_calls ?? 'none')}</span>;
}

beforeEach(() => {
  vi.useFakeTimers();
  install();
});
afterEach(() => {
  cleanup();
  setEventStreamFactoryForTests(undefined);
  vi.useRealTimers();
});

describe('useLiveStatus（真实模式）', () => {
  it('还没推送时返回 initial；rerender 换 initial 用最新值（不缓存旧值）', () => {
    const first = render(<HookProbe initial={rows(99)} />);
    expect(first.getByTestId('tt-live').textContent).toBe('99');
    first.rerender(<HookProbe initial={rows(77)} />);
    expect(first.getByTestId('tt-live').textContent).toBe('77');
  });

  it('收到 ok:true 推送返回最新；ok:false 不覆盖；重复与过期丢弃', () => {
    const r = render(<HookProbe initial={rows(99)} />);
    push('snapshot', '5', env(rows(41)));
    expect(r.getByTestId('tt-live').textContent).toBe('41');
    push('update', '6', env(null, false));
    expect(r.getByTestId('tt-live').textContent).toBe('41');
    push('update', '6', env(rows(60)));
    expect(r.getByTestId('tt-live').textContent).toBe('41');
    push('update', '7', env(rows(50)));
    expect(r.getByTestId('tt-live').textContent).toBe('50');
  });

  it('卸载后最后一个订阅者离开：流被关掉', () => {
    const r = render(<HookProbe initial={rows(99)} />);
    expect(stream).not.toBeNull();
    r.unmount();
    expect((stream as FakeStream).closed).toBe(true);
  });
});
"""

PROBE_PAGES = r"""
import * as React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../src/live/mode', () => ({
  liveModeIsReal: () => true,
  liveClient: () => null,
  setLiveClientForTests: () => {},
}));

import App from '../src/App';
import statusJson from '../src/mock/status.json';
import { setEventStreamFactoryForTests } from '../src/live/events';
import { setConnectionState } from '../src/live/connection';

vi.setConfig({ testTimeout: 60000 });

class FakeStream {
  listeners = new Map<string, Set<(e: unknown) => void>>();
  closed = false;
  addEventListener(type: any, listener: any): void {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type)!.add(listener);
  }
  removeEventListener(type: any, listener: any): void {
    this.listeners.get(type)?.delete(listener);
  }
  close(): void { this.closed = true; }
  emit(type: string, lastEventId: string, data: string): void {
    for (const l of this.listeners.get(type) ?? []) l({ type, lastEventId, data });
  }
}

function env(rows: unknown, ok = true): string {
  return JSON.stringify({
    ok, exit_code: ok ? 0 : null, data: ok ? rows : null, output: [],
    messages: ok ? [] : ['ERROR: 读 status 超时'], command: ['status'], elapsed_ms: 3,
  });
}

const RUNNING = 'ui-readonly-api/attempt-001';

function rows(patch: Record<string, unknown>): any[] {
  return (statusJson as any[]).map((r) => (r.attempt === RUNNING ? { ...r, ...patch } : r));
}

function livePatch(toolCalls: number, elapsedSeconds: number): Record<string, unknown> {
  return { live: { tool_calls: toolCalls, elapsed_seconds: elapsedSeconds, deltas_since_last_tool: 0, long_idle: false } };
}

let stream: FakeStream | null = null;

function install() {
  stream = null;
  setEventStreamFactoryForTests(() => { stream = new FakeStream(); return stream as any; });
}

function push(type: 'snapshot' | 'update', id: string, data: string) {
  act(() => { stream?.emit(type, id, data); });
}

function text(): string {
  return (document.body.textContent || '').replace(/\s+/g, ' ');
}

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}

beforeEach(() => {
  setConnectionState('connected');
  window.location.hash = '';
  install();
});
afterEach(async () => {
  cleanup();
  setEventStreamFactoryForTests(undefined);
  setConnectionState('connected');
  window.location.hash = '';
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
});

describe('页面实时接线（T036 合同第一节）', () => {
  it('总览页：首屏一次性读；snapshot/update 后运行中的数字跟着变；过期与 ok:false 不动', async () => {
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(text()).toContain('工具调用 37 次');
    expect(text()).toContain('已用 19 分 6 秒');
    push('snapshot', '1', env(rows(livePatch(41, 1200))));
    expect(text()).toContain('工具调用 41 次');
    expect(text()).toContain('已用 20 分 0 秒');
    push('update', '1', env(rows(livePatch(99, 1))));
    expect(text()).toContain('工具调用 41 次');
    push('update', '2', env(null, false));
    expect(text()).toContain('工具调用 41 次');
    push('update', '3', env(rows(livePatch(45, 1300))));
    expect(text()).toContain('工具调用 45 次');
    expect(text()).toContain('已用 21 分 40 秒');
    expect(text()).not.toContain('工具调用 41 次');
  });

  it('任务页列表：rows 用实时 status 覆盖（运行中的用时跟着变）', async () => {
    window.location.hash = '#/tasks';
    render(<App />);
    await settle();
    expect(text()).toContain('已用');
    push('snapshot', '10', env(rows(livePatch(41, 7777))));
    expect(text()).toContain('已用 2 小时 9 分');
    push('update', '11', env(rows(livePatch(41, 61))));
    expect(text()).toContain('已用 1 分 1 秒');
    expect(text()).not.toContain('已用 2 小时 9 分');
  });

  it('任务页详情：实时 status 里有同 attempt 的行时覆盖；没有时保留首屏读到的行', async () => {
    window.location.hash = '#/tasks/ui-readonly-api/attempt-001';
    render(<App />);
    await settle();
    expect(text()).not.toContain('5,632,345');
    push('snapshot', '20', env(rows({ tokens: 5632345 })));
    expect(text()).toContain('5,632,345');
    push('update', '21', env((statusJson as any[]).filter((r: any) => r.attempt !== RUNNING)));
    expect(text()).not.toContain('5,632,345');
  });
});
"""

PROBE_SPECS = {
    "events": (PROBE_EVENTS, (EVENTS_REL,)),
    "default": (PROBE_DEFAULT, (EVENTS_REL, CONNECTION_REL)),
    "fixture": (PROBE_FIXTURE, (EVENTS_REL, USE_LIVE_STATUS_REL)),
    "hooklive": (PROBE_HOOKLIVE, (EVENTS_REL, USE_LIVE_STATUS_REL)),
    "pages": (PROBE_PAGES, (EVENTS_REL, USE_LIVE_STATUS_REL, APP_REL, OVERVIEW_REL, TASKS_PAGE_REL)),
}
PROBE_ORDER = ("events", "default", "fixture", "hooklive", "pages")


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针
# ---------------------------------------------------------------------------

# G01 的超时是 600s：夹具总预算压在 540s 以内，用完就停下并在断言里写明，不等调度器来杀。
PIPELINE_BUDGET = 540
STEP_CAPS = {
    "npm ci": 240,
    "npm ci --offline": 240,
    "npm test": 240,
    "npm run build": 180,
    "npm run check:contract": 60,
    "probe": 110,
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
        # 依赖已在（执行端 Setup 装过）就不重装：省下的时间留给 Vitest 与探针。
        if (WEB / "node_modules" / "vitest").is_dir():
            pipe.steps["npm ci"] = Step("npm ci", [], 0, False, "node_modules 已在，未重装依赖", 0.0)
        else:
            ci = run_step("npm ci", [npm, "ci"])
            if ci is not None and ci.code != 0:
                # 合同 Setup 的兜底：网络不可用时改用本机 npm 缓存再试一次
                run_step("npm ci --offline", [npm, "ci", "--offline"])
        ci_ok = any(pipe.steps.get(k) is not None and pipe.steps[k].code == 0
                    for k in ("npm ci", "npm ci --offline"))
        if ci_ok:
            run_step("npm test", [npm, "test"])
            run_step("npm run build", [npm, "run", "build"])
            run_step("npm run check:contract", [node, "scripts/token-contract.mjs"])
            uid = uuid.uuid4().hex[:12]
            for key in PROBE_ORDER:
                missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                name = f"probe-{uid}-t036-{key}.test.tsx"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                written.append(path)
                path.write_text(PROBE_SPECS[key][0], encoding="utf-8", newline="\n")
                pipe.probe_files[key] = name
                run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        else:
            pipe.stopped_reason = "npm ci（含 --offline 兜底）失败，后续步骤未运行"
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
    """P1 / V01、V02、D14：npm ci（或已在的依赖）、npm test（全绿）、npm run build（tsc --noEmit +
    vite build）、npm run check:contract 都退出 0；依赖文件一个字节没动。"""
    assert any(pipeline.steps.get(k) is not None and pipeline.steps[k].code == 0
               for k in ("npm ci", "npm ci --offline")), \
        f"npm ci 未成功：{pipeline.stopped_reason or pipeline.reason}"
    for name in ("npm test", "npm run build", "npm run check:contract"):
        step = assert_step_ok(pipeline, name)
        if name == "npm test":
            m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
            assert m, f"npm test 输出里没有通过计数：\n{step.tail}"
            assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), \
                f"npm test 有失败或跳过：\n{step.tail}"
        if name == "npm run build":
            assert "built in" in step.out, f"vite build 应打印 built in：\n{step.tail}"
        if name == "npm run check:contract":
            assert "契约检查：通过" in step.out, f"契约检查应通过：\n{step.tail}"
    assert pipeline.digests_before == pipeline.digests_after, \
        "npm 流水线不许改动 desktop/web/package.json 与 package-lock.json"
    assert not pipeline.gate_probe_left, "gate-probe/ 目录在探针后应清掉"


def test_p2_probe_events(pipeline):
    """P2 / D01–D06：createLiveEvents 纯逻辑探针全绿（序号、退避、引用计数、ok:false）。"""
    assert_probe_ok(pipeline, "events")


def test_p3_probe_default(pipeline):
    """P3 / D05、D07：默认实例与 connection.ts 接线探针全绿（真实模式建流、重连状态与次数、
    恢复默认建流）。"""
    assert_probe_ok(pipeline, "default")


def test_p4_probe_fixture(pipeline):
    """P4 / D01、D08：夹具模式探针全绿（订阅空操作、不建流不排计时器、钩子原样返回）。"""
    assert_probe_ok(pipeline, "fixture")


def test_p5_probe_hooklive(pipeline):
    """P5 / D08：useLiveStatus 真实模式探针全绿（initial 取最新值、推送覆盖、卸载关流）。"""
    assert_probe_ok(pipeline, "hooklive")


def test_p6_probe_pages(pipeline):
    """P6 / D09、D10：总览页与任务页的实时接线探针全绿（推送后数字跟着变、详情行覆盖与回退）。"""
    assert_probe_ok(pipeline, "pages")
