"""T034 战前门禁：桌面端前端接真实服务第 2 片——连接状态与页面接线（D3 之五，T029 的重新登记）的
黑盒基准测试（合同 t034-desktop-web-connection-b.v1，基线 a8a4924）。

被测对象是 ``desktop/web/``：新增 ``src/shell/useShellConnection.ts``（连接状态钩子）与执行端测试
``tests/live-app.test.tsx``；改 ``src/App.tsx``（meta 异步化、offline 取钩子）、
``src/shell/TitleBar.tsx``（胶囊取 live 状态、真实模式三行「—」、仓库菜单只列当前仓库）、
``src/shell/PageFrame.tsx``（真实模式 [重新连接] 可点、合成失败信封只列 messages、断线时保留旧数据）、
``src/components/ConnectionPill.tsx``（pid 放宽成 number | string）、
``src/pages/OverviewPage.tsx``（说明初值按模式分）、``src/live/transport.ts``（宿主接口改成调用时取）、
``tests/live-transport.test.ts``（只追加一条「先建客户端、后设 window.themisHost」的用例）。

基线（a8a4924）上 ``useShellConnection.ts`` 与 ``live-app.test.tsx`` 不存在、六个改动文件还是夹具写法、
live-transport.test.ts 只有 18 条用例，所以本文件的失败落在「文件不存在」「记号不在」「探针断言红」上，
不是导入、收集或语法错误：模块级只导入标准库，所有仓库文件的读取都发生在用例函数里；流水线
（npm ci、npm test、npm run build、check:contract、探针）放在 ``pipeline`` 会话级夹具里。

结构（编号对应合同 DoD 的 D01–D12）：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：钩子文件在位与形状（D02）；三个消费方共用钩子
  （D02）；App 的占位与 getMeta/getMetaNow 接线、根组件不碰 liveClient（D03）；TitleBar 与胶囊（D05）；
  PageFrame 的记号（D06）；总览页（D03/D06）；transport 的宿主接口与两处中止标志（D08）；live-transport.test.ts
  追加第 19 条（D08）；执行端 live-app.test.tsx 在位、不用 skip/only/todo（D01–D08 的证据）；本片文件的禁词扫描
  （D09）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：npm ci（node_modules
  已在时跳过重装；失败再试 --offline）、npm test（全绿）、npm run build、npm run check:contract（V01–V03），
  依赖文件一个字节不许动；再把探针逐份写成 ``gate-probe/probe-<唯一标识>-t034-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除。

探针（Vitest + jsdom，全部自包含，辅助函数不跨文件共享；只许用 T027 留下的注入口
``setLiveClientForTests``、``setConnectionState`` 与假客户端，不 mock 被测模块）：

- hook：夹具/真实两模式的 live 与 state、live 从假翻真不丢 hook（守 hooks 规则）（D02）。
- app：真实模式首屏 meta 占位「—」后由 getMeta() 填、失败保持占位；夹具模式首屏照旧；
  外壳页路由（#/first-run、#/service-status）零调用零横幅（D03、D04、D07）。
- states：真实模式四种页面状态（加载、出错、离线、空）、总览说明初值「—」后填、
  [重新连接] 可点并重跑 load、断线时刷新失败保留旧数据（D06、D03、D01）。
- frame：PageFrame 直测——合成失败信封只列 messages 不写「命令（…）返回退出码」（两种模式都适用）、
  夹具形状的信封照旧、夹具模式横幅里 [重新连接] 仍禁用、真实模式可点且断线刷新失败保留旧数据、
  不向 Tab 栏上报 error（D06、D04）。
- shell：TitleBar 仓库菜单——真实模式只列当前仓库名一项（radio 选中）、夹具模式照旧列 SHELL_RECENT_REPOS、
  「添加仓库…」两模式都保留禁用（D05、D04）。
- pillrows（过渡）：真实模式胶囊浮层三行（pid、启动于、事件流）都是「—」、夹具模式照旧——
  SSE 片（事件流）会推翻「事件流=—」，届时退役本条。
- transport：先建客户端、后设 window.themisHost 时 reauth 恰好被调 1 次且信封是「ERROR: 会话已失效」、
  显式 options.host 仍优先（D08）。

过渡断言（函数名带 ``test_transitional_``，docstring 写明哪一片推翻，站主按名字退役）：
``test_transitional_p7_probe_pillrows``——真实模式胶囊浮层三行「—」（SSE 片接事件流后推翻）。

合同没有写死、门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：
横幅里的 [重新连接] 在真实模式下只断言「可点 + 重跑 load」，不断言按钮变体与文案；真实模式仓库菜单
只断言 menuitemradio 恰好一项且选中，不断言分组标题「最近的仓库」的有无；探针里的状态翻转一律用
``setConnectionState`` 注入（注入的假客户端不经传输层，不会自己报状态）。
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
NEW_SOURCE_FILES = (f"{SRC_REL}/shell/useShellConnection.ts",)
# 合同 Scope 的新增执行端测试（live-shell.test.tsx 可选，不查）
EXECUTOR_TESTS = (f"{TESTS_REL}/live-app.test.tsx",)

HOOK_REL = f"{SRC_REL}/shell/useShellConnection.ts"
APP_REL = f"{SRC_REL}/App.tsx"
TITLEBAR_REL = f"{SRC_REL}/shell/TitleBar.tsx"
PAGEFRAME_REL = f"{SRC_REL}/shell/PageFrame.tsx"
PILL_REL = f"{SRC_REL}/components/ConnectionPill.tsx"
OVERVIEW_REL = f"{SRC_REL}/pages/OverviewPage.tsx"
TRANSPORT_REL = f"{SRC_REL}/live/transport.ts"
MODE_REL = f"{SRC_REL}/live/mode.ts"
API_REL = f"{SRC_REL}/api.ts"
LIVE_TRANSPORT_TEST_REL = f"{TESTS_REL}/live-transport.test.ts"
LIVE_APP_TEST_REL = f"{TESTS_REL}/live-app.test.tsx"

# 执行端测试里应出现的记号（合同第 8 步的最小覆盖证据）
EXECUTOR_TEST_TOKENS = {
    "live-app.test.tsx": ("setLiveClientForTests", "setConnectionState", "first-run", "service-status",
                          "重新连接", "已断开"),
}
# live-transport.test.ts 基线上是 18 条 it(（合同第七节：只追加一条）
LIVE_TRANSPORT_CASES_BASELINE = 18

NETWORK_WORDS = ("fetch", "XMLHttpRequest", "EventSource", "WebSocket")
NETWORK_RE = re.compile(r"(?<![A-Za-z0-9_$])(?:fetch|XMLHttpRequest|EventSource|WebSocket)(?![A-Za-z0-9_$])")
SINK_WORDS = ("dangerouslySetInnerHTML", "innerHTML", "outerHTML", "insertAdjacentHTML", "eval(",
              "new Function", "document.write", "srcdoc", "createContextualFragment", "DOMParser")
HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b(?![-\w])")
# App.tsx 的禁词（T012 forbidden_api_problems 的口径 + 本片合同 Non-goals/Forbidden）
APP_FORBIDDEN = (r"\bthemisHost\b", r"\bdeclare\s+global\b", r"\blocalStorage\b", r"\bsessionStorage\b",
                 r"\bwindow\s*\.\s*open\b", r"\bwindow\s*\.\s*confirm\b", r"themisShell", r"\bServerIcon\b")

# App.tsx 的禁词（T012 的口径，见 APP_FORBIDDEN）

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


# TS 注释剥离（与 T010 的 _TS_COMMENT 同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_new_files_present():
    """S01 / D01、第 3 步：新文件 useShellConnection.ts 与执行端 live-app.test.tsx 都在（基线上没有，本条先红）。"""
    need_new_sources()
    for rel in EXECUTOR_TESTS:
        need_file(rel)


def test_s02_hook_shape():
    """S02 / D02、第一节：useShellConnection 的形状——返回 { live, state }；live 用 liveClient() 判定；
    两个状态源无条件都取（useConnectionState() 与 shellConnectionState(currentMock()) 都在）；
    不用 liveModeIsReal（不认测试注入）；从 ../live/mode 只许引 liveClient。"""
    need_file(HOOK_REL)
    code = strip_ts_comments(read_rel(HOOK_REL))
    assert re.search(r"export function useShellConnection\(", code), "应导出 useShellConnection()"
    assert re.search(r"\bliveClient\(\)", code), "live 应来自 liveClient()（测试注入也算真实模式）"
    assert re.search(r"\buseConnectionState\(\)", code), "应无条件调用 useConnectionState()（守 hooks 规则）"
    assert re.search(r"shellConnectionState\(currentMock\(\)\)", code), "夹具分支应取 shellConnectionState(currentMock())"
    assert re.search(r"\blive\s*[:,}]", code) and re.search(r"\bstate\s*[:,}]", code), \
        "返回值应含 live 与 state 两个键（显式键或属性简写均可）"
    assert "liveModeIsReal" not in code, "钩子不许用 liveModeIsReal 判定（它不认测试注入）"
    assert "setLiveClientForTests" not in code, "钩子不碰测试注入口"
    for m in re.finditer(r"""import\s+([^;\n]*?)\s+from\s+['"]\.\./live/mode['"]""", code):
        items = [s.strip() for s in m.group(1).strip().strip("{}").split(",") if s.strip()]
        bad = [s for s in items if s not in ("liveClient", "type LiveClient")]
        assert not bad, f"从 ../live/mode 只许引 liveClient，实际 {m.group(0)}"
    for m in re.finditer(r"""import\s+([^;\n]*?)\s+from\s+['"]\.\./live/connection['"]""", code):
        items = [s.strip() for s in m.group(1).strip().strip("{}").split(",") if s.strip()]
        bad = [s for s in items if s not in ("useConnectionState", "type ConnectionState", "ConnectionState")]
        assert not bad, f"从 ../live/connection 只许引 useConnectionState（与类型），实际 {m.group(0)}"


def test_s03_hook_consumers():
    """S03 / D02：App.tsx、TitleBar.tsx、PageFrame.tsx 三处共用同一个钩子（不许各写一份判定逻辑）。"""
    for rel in (APP_REL, TITLEBAR_REL, PAGEFRAME_REL):
        code = strip_ts_comments(read_rel(rel))
        assert re.search(r"""useShellConnection\(\)""", code), f"{rel} 应调用 useShellConnection()"
        assert "liveModeIsReal" not in code, f"{rel} 不许用 liveModeIsReal 判定界面行为"
        assert "setLiveClientForTests" not in code, f"{rel} 是产品代码，不碰测试注入口"


def test_s04_app_wiring():
    """S04 / D03、第二节：App.tsx——meta 从同步值改成 state（夹具仍是 getMetaNow() 打底、真实模式占位「—」、
    挂载后 getMeta() 一次）；根组件不碰 liveClient；TitleBar/TabBar 的 props 还在。"""
    need_file(APP_REL)
    code = strip_ts_comments(read_rel(APP_REL))
    assert "useShellConnection" in code, "ServiceApp 应经 useShellConnection 取连接状态"
    assert not re.search(r"\bliveClient\b", code), "App.tsx 里不许出现 liveClient（一切模式判定都在钩子里）"
    assert "getMetaNow" in code, "夹具模式的初值应仍是 getMetaNow()（同步、逐字照旧）"
    assert re.search(r"\bgetMeta\(\)", code), "真实模式的 meta 应走 getMeta()"
    assert re.search(r"['\"]—['\"]", code), "真实模式的 meta 占位应是「—」"
    assert re.search(r"repoName=\{", code), "TitleBar 的 repoName 应照旧传"
    assert "kitVersion" in code and "offline" in code, "TabBar 的 kitVersion/offline 应照旧传"
    assert "TitleBar" in code and "TabBar" in code, "标题栏与 Tab 栏的装配应保留"


def test_s05_titlebar_wiring():
    """S05 / D05、第三节：TitleBar——胶囊状态取钩子；夹具三行的来源（SHELL_PID、SHELL_STARTED_AT、
    shellStreamText）与 SHELL_RECENT_REPOS 保留（夹具分支一字不变）；真实模式三行传「—」；
    「添加仓库…」与「第二阶段接入」保留。"""
    need_file(TITLEBAR_REL)
    code = strip_ts_comments(read_rel(TITLEBAR_REL))
    assert re.search(r"""useShellConnection\(\)""", code), "胶囊状态应取 useShellConnection()"
    for token in ("SHELL_PID", "SHELL_STARTED_AT", "shellStreamText", "SHELL_RECENT_REPOS"):
        assert token in code, f"夹具分支的来源 {token} 应保留"
    assert re.search(r"['\"]—['\"]", code), "真实模式浮层三行应传「—」"
    assert "添加仓库" in code, "「添加仓库…」项应保留"
    assert "第二阶段接入" in code, "「添加仓库…」的 trailing 文案「第二阶段接入」应保留"
    assert re.search(r"disabled:\s*true", code), "「添加仓库…」应保持禁用"


def test_s06_connection_pill_pid_type():
    """S06 / D05、第三节：ConnectionPill 只放宽 pid 的类型成 number | string；「未知」兜底不动（T005 钉着）。"""
    need_file(PILL_REL)
    text = read_rel(PILL_REL)
    assert re.search(r"pid\?\s*:\s*number\s*\|\s*string", text), "pid 的类型应放宽成 number | string"
    assert "未知" in text, "没给的值仍显示「未知」（T005 :2258 钉着）"
    assert re.search(r"'connected'\s*\|\s*'reconnecting'\s*\|\s*'disconnected'", text), \
        "ConnectionState 的三个取值不许改"
    for token in ("attempt", "startedAt", "stream", "aria-expanded", "aria-controls"):
        assert token in text, f"胶囊的公开结构应保留（{token}）"


def test_s07_pageframe_wiring():
    """S07 / D06、第四节：PageFrame——offline 取钩子；夹具模式的 DisabledAction 禁用入口仍在；
    「重新连接」与「返回退出码」的记号都在（(b) 按信封形状分支，探针逐字验证）。"""
    need_file(PAGEFRAME_REL)
    code = strip_ts_comments(read_rel(PAGEFRAME_REL))
    assert re.search(r"""useShellConnection\(\)""", code), "offline 应取 useShellConnection()"
    assert "DisabledAction" in code, "夹具模式的横幅仍应是 DisabledAction（T006/T010/T011 钉着）"
    assert "重新连接" in code, "横幅里的 [重新连接] 应保留"
    assert "返回退出码" in code, "夹具形状的信封仍写「命令（…）返回退出码 …」（探针逐字验证）"
    assert "接入本机服务后可用" in code, "夹具模式的禁用 reason 应保留"
    assert re.search(r"data-stale", code), "data-stale 约定应保留"
    assert "可能已过期" in code, "「可能已过期」Tag 应保留"


def test_s08_overview_wiring():
    """S08 / D03、第五节：总览页——说明初值按模式分（真实模式占位「—」）；「· kit 」模板与 getMetaNow
    保留；模式判定用 liveClient()/钩子；load 仍是模块级命名函数（T009 钉着）。"""
    need_file(OVERVIEW_REL)
    code = strip_ts_comments(read_rel(OVERVIEW_REL))
    assert re.search(r"['\"]—['\"]", code), "真实模式的说明初值应是占位「—」"
    assert "· kit " in code, "「仓库名 · kit 版本」的模板应保留"
    assert "getMetaNow" in code, "夹具模式的初值应仍来自 getMetaNow()"
    assert re.search(r"\bliveClient\(|useShellConnection\(", code), "总览页应能判定模式（liveClient 或钩子）"
    assert re.search(r"const loadOverview", code), "load 应仍是模块级命名函数（T009 page_wiring_problems）"
    assert re.search(r"const isOverviewEmpty", code), "isEmpty 应仍是模块级命名函数（T009）"


def test_s09_transport_host_at_call_time():
    """S09 / D08、第六节：transport.ts——window.themisHost 改成调用时取（显式 options.host 仍优先）；
    与中止时限有关的两处判定原样保留（T027 的变异锚点 transport-abort-flag 在本文件里出现两处；
    SSE 片若另加超时路径需同步放宽本条的数量断言）。"""
    need_file(TRANSPORT_REL)
    text = read_rel(TRANSPORT_REL)
    assert "window.themisHost" in text, "宿主接口仍应读 window.themisHost（时机由探针验证）"
    assert "options.host" in text, "显式 options.host 应仍优先"
    assert "typeof window" in text, "没有 window 时（非浏览器）应按没有宿主处理"
    # 两处中止标志的判定原样保留（T027 终审意见 3：变异锚点不许被本片改动挪位或复制）
    abort_checks = text.count("timedOut || (error as Error)?.name === 'AbortError'")
    assert abort_checks == 2, f"中止标志的两处判定应原样保留（现剩 {abort_checks} 处）"
    assert "setTimeout" in text and "clearTimeout" in text, "时限机制应保留"


def test_s10_live_transport_test_appended():
    """S10 / D08、第 3 步：live-transport.test.ts 只追加一条「先建客户端、后设 window.themisHost」的用例
    （it 数从 18 变 19+），不用 skip/only/todo。"""
    need_file(LIVE_TRANSPORT_TEST_REL)
    text = read_rel(LIVE_TRANSPORT_TEST_REL)
    count = len(re.findall(r"^\s*it\(", text, re.M))
    assert count >= LIVE_TRANSPORT_CASES_BASELINE + 1, \
        f"live-transport.test.ts 应追加到至少 {LIVE_TRANSPORT_CASES_BASELINE + 1} 条 it（现 {count} 条）"
    assert "window.themisHost" in text, "新用例应设 window.themisHost（旧的 18 条不碰它）"
    bad = [pat for pat in (r"\.skip\s*\(", r"\.only\s*\(", r"\.todo\s*\(", r"\bxit\s*\(", r"\bdescribe\.only")
           if re.search(pat, text)]
    assert not bad, f"live-transport.test.ts 里出现了 {bad}（不许削弱用例）"


def test_s11_executor_test_coverage_tokens():
    """S11 / D01–D08 的证据、第七节：执行端 live-app.test.tsx 在位，含最小覆盖记号，不用 skip/only/todo。"""
    for name, tokens in EXECUTOR_TEST_TOKENS.items():
        rel = f"{TESTS_REL}/{name}"
        need_file(rel)
        text = read_rel(rel)
        missing = [t for t in tokens if t not in text]
        assert not missing, f"{rel} 里缺少记号 {missing}（合同第 8 步要求的最小覆盖）"
        bad = [pat for pat in (r"\.skip\s*\(", r"\.only\s*\(", r"\.todo\s*\(", r"\bxit\s*\(", r"\bdescribe\.only")
               if re.search(pat, text)]
        assert not bad, f"{rel} 里出现了 {bad}（合同 D13：不删用例、不削弱断言）"


def test_s12_forbidden_words_scan():
    """S12 / D09、Non-goals 与 Forbidden：本片涉及的产品文件里没有四个浏览器网络接口名（src/live/ 除外，连注释都不许）、
    注入词、role=status、内联 style、十六进制颜色；App.tsx 里没有 themisHost/declare global/localStorage/
    sessionStorage/window.open/window.confirm/themisShell/ServerIcon。"""
    need_file(HOOK_REL)
    targets = [HOOK_REL, APP_REL, TITLEBAR_REL, PAGEFRAME_REL, PILL_REL, OVERVIEW_REL]
    problems = []
    for rel in targets:
        code = strip_ts_comments(read_rel(rel))
        for m in NETWORK_RE.finditer(code):
            problems.append(f"{rel} 出现网络接口名 {m.group(0)}")
        for word in SINK_WORDS:
            if word in code:
                problems.append(f"{rel} 出现注入词 {word}")
        if re.search(r"role\s*=\s*['\"]status['\"]", code):
            problems.append(f"{rel} 出现 role=status")
        if re.search(r"\bstyle\s*=\s*[{\"']", code):
            problems.append(f"{rel} 出现内联 style")
        for m in HEX_COLOR_RE.finditer(code):
            problems.append(f"{rel} 出现十六进制颜色 {m.group(0)}")
    app_code = strip_ts_comments(read_rel(APP_REL))
    for pat in APP_FORBIDDEN:
        if re.search(pat, app_code):
            problems.append(f"{APP_REL} 出现禁词 {pat}")
    fail_if(problems, "本片文件的源码守卫扫描")


def test_s13_live_mode_and_api_untouched():
    """S13 / D12、Non-goals：mode.ts 一字不改（导出集合仍是四个）；getMetaNow 仍是同步的 clone(metaJson)
    （T027 s31 钉着，本片不推翻——T027 的 test_transitional_s31_getmetanow_pure_fixture 不要退役）。connection.ts 的取值集合交给下一条过渡断言与 T027 的 s30。"""
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
    api_text = read_rel(API_REL)
    m = re.search(r"export function getMetaNow\([^)]*\)\s*(?::[^{]{0,80})?\s*\{([^{}]*)\}", api_text, re.S)
    assert m, "getMetaNow 应仍是同步的 export function（一字不改）"
    assert "clone(metaJson)" in m.group(1), "getMetaNow 的函数体应仍是 clone(metaJson)"


# test_transitional_s13_connection_two_states：站主 2026-11-13 为 T036（事件流片加 reconnecting）退役


# ---------------------------------------------------------------------------
# 探针源码（每份自包含：辅助函数不跨文件共享）
# ---------------------------------------------------------------------------

PROBE_HOOK = r"""
import * as React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setConnectionState } from '../src/live/connection';
import { setLiveClientForTests } from '../src/live/mode';
import { useShellConnection } from '../src/shell/useShellConnection';

vi.setConfig({ testTimeout: 60000 });

const fakeClient: any = {
  get: () => Promise.resolve({ ok: true, exit_code: 0, data: {}, output: [], messages: [], command: [], elapsed_ms: 0 }),
};

function Probe() {
  const { live, state } = useShellConnection();
  return <span data-testid="tt-hook" data-live={String(live)} data-state={state} />;
}

function read(container: HTMLElement) {
  const el = container.querySelector('[data-testid="tt-hook"]') as HTMLElement;
  return { live: el.getAttribute('data-live'), state: el.getAttribute('data-state') };
}

beforeEach(() => {
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
});
afterEach(() => {
  cleanup();
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('useShellConnection（T034 第一节）', () => {
  it('夹具模式：live 假；state 取 shellConnectionState(currentMock())（offline 时 disconnected）', () => {
    window.location.hash = '#/overview';
    const first = render(<Probe />);
    expect(read(first.container)).toEqual({ live: 'false', state: 'connected' });
    cleanup();
    window.location.hash = '#/overview?mock=offline';
    const second = render(<Probe />);
    expect(read(second.container)).toEqual({ live: 'false', state: 'disconnected' });
  });

  it('真实模式（注入）：live 真；state 取 live 的连接状态，随 setConnectionState 重渲染', () => {
    setLiveClientForTests(fakeClient);
    const { container } = render(<Probe />);
    expect(read(container)).toEqual({ live: 'true', state: 'connected' });
    act(() => { setConnectionState('disconnected'); });
    expect(read(container).state).toBe('disconnected');
    act(() => { setConnectionState('connected'); });
    expect(read(container).state).toBe('connected');
  });

  it('live 从假翻真（重渲染）不丢 hook：两个状态源无条件都取（守 hooks 规则）', () => {
    const { container } = render(<Probe />);
    expect(read(container).live).toBe('false');
    setLiveClientForTests(fakeClient);
    act(() => { setConnectionState('disconnected'); });
    const after = read(container);
    expect(after.live).toBe('true');
    expect(after.state).toBe('disconnected');
  });
});
"""

PROBE_APP = r"""
import * as React from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';
import { getMetaNow } from '../src/api';
import { setConnectionState } from '../src/live/connection';
import { setLiveClientForTests } from '../src/live/mode';

vi.setConfig({ testTimeout: 60000 });

function okEnv(data: unknown) {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command: ['status'], elapsed_ms: 3 };
}
function failEnv(messages: string[]) {
  return { ok: false, exit_code: null, data: null, output: [], messages, command: [], elapsed_ms: 0 };
}

const calls: string[] = [];
let responders: Record<string, () => unknown> = {};

function install(overrides: Record<string, () => unknown> = {}) {
  calls.length = 0;
  responders = {
    '/api/v1/meta': () => okEnv({ version: 'pi_dispatch 9.9.9', repo_name: 'live-repo' }),
    '/api/v1/status': () => okEnv([]),
    '/api/v1/config/history': () => okEnv({ entries: [], broken_lines: 0, external_before_first: 0 }),
    ...overrides,
  };
  const client = {
    get(path: string) {
      calls.push(path);
      const respond = responders[path] ?? (() => okEnv(null));
      return Promise.resolve(respond() as any);
    },
  };
  setLiveClientForTests(client as any);
}

function repoButton(): HTMLElement {
  return document.querySelector('button[title="切换仓库"]') as HTMLElement;
}
function statusText(): string {
  const el = document.querySelector('.tt-tabbar__status');
  return ((el && el.textContent) || '').replace(/\s+/g, ' ');
}
function pillState(): string | null {
  const el = document.querySelector('.tt-pill');
  return el ? el.getAttribute('data-state') : null;
}

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}

beforeEach(() => {
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
});
afterEach(async () => {
  cleanup();
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
});

describe('App 级真实模式（T034 第二节）', () => {
  it('meta 先占位「—」后由 getMeta() 填成服务给的值（首屏不出现夹具值）', async () => {
    const pending: Array<(v: any) => void> = [];
    install({ '/api/v1/meta': () => new Promise((res) => { pending.push(res); }) });
    window.location.hash = '#/overview';
    render(<App />);
    expect((repoButton().textContent || '')).toContain('—');
    expect(statusText()).toContain('kit —');
    expect(document.body.textContent || '').not.toContain('demo-repo');
    expect(document.body.textContent || '').not.toContain('kit 2.12.0');
    await act(async () => {
      pending.forEach((res) => res(okEnv({ version: 'pi_dispatch 9.9.9', repo_name: 'live-repo' })));
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });
    expect((repoButton().textContent || '')).toContain('live-repo');
    expect(statusText()).toContain('kit 9.9.9');
  });

  it('meta 失败保持占位「—」，不报错、不闪红', async () => {
    install({ '/api/v1/meta': () => failEnv(['ERROR: 连不上本机服务（请求没有到达服务）']) });
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect((repoButton().textContent || '')).toContain('—');
    expect(statusText()).toContain('kit —');
  });

  it('夹具模式（不注入）：首屏照旧是夹具 meta，胶囊 connected，没有离线横幅', async () => {
    setLiveClientForTests(undefined);
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    const meta = getMetaNow();
    expect((repoButton().textContent || '')).toContain(meta.repo_name);
    expect(statusText()).toContain(`kit ${meta.kit_version}`);
    expect(pillState()).toBe('connected');
    expect(document.body.textContent || '').not.toContain('与本机服务的连接断开');
  });

  it('外壳页路由（#/first-run、#/service-status）：假客户端 0 次调用、没有离线横幅、没有胶囊', async () => {
    install();
    setConnectionState('disconnected');
    for (const win of ['first-run', 'service-status']) {
      cleanup();
      window.location.hash = '#/' + win;
      render(<App />);
      await settle();
      expect(calls.length, win).toBe(0);
      expect(document.body.textContent || '', win).not.toContain('与本机服务的连接断开');
      expect(document.querySelector('.tt-pill'), win).toBeNull();
    }
  });
});
"""

PROBE_STATES = r"""
import * as React from 'react';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';
import statusJson from '../src/mock/status.json';
import { setConnectionState } from '../src/live/connection';
import { setLiveClientForTests } from '../src/live/mode';

vi.setConfig({ testTimeout: 60000 });

function okEnv(data: unknown) {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command: ['status'], elapsed_ms: 3 };
}
function failEnv(messages: string[]) {
  return { ok: false, exit_code: null, data: null, output: [], messages, command: [], elapsed_ms: 0 };
}

const calls: string[] = [];
let responders: Record<string, () => unknown> = {};

function install(overrides: Record<string, () => unknown> = {}) {
  calls.length = 0;
  responders = {
    '/api/v1/meta': () => okEnv({ version: 'pi_dispatch 9.9.9', repo_name: 'live-repo' }),
    '/api/v1/status': () => okEnv(statusJson),
    '/api/v1/config/history': () => okEnv({ entries: [], broken_lines: 0, external_before_first: 0 }),
    ...overrides,
  };
  const client = {
    get(path: string) {
      calls.push(path);
      const respond = responders[path] ?? (() => okEnv(null));
      return Promise.resolve(respond() as any);
    },
  };
  setLiveClientForTests(client as any);
}

function bodyText(): string {
  return (document.body.textContent || '').replace(/\s+/g, ' ');
}
function pillState(): string | null {
  const el = document.querySelector('.tt-pill');
  return el ? el.getAttribute('data-state') : null;
}
function pillText(): string {
  const el = document.querySelector('.tt-pill__text');
  return (el && el.textContent) || '';
}
function pageState(): string | null {
  const el = document.querySelector('[data-page-state]');
  return el ? el.getAttribute('data-page-state') : null;
}
function reconnectButton(): HTMLButtonElement | undefined {
  return (Array.from(document.querySelectorAll('button')) as HTMLButtonElement[])
    .find((b) => (b.textContent || '').trim() === '重新连接');
}
function count(path: string): number {
  return calls.filter((p) => p === path).length;
}

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}

beforeEach(() => {
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
});
afterEach(async () => {
  cleanup();
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
});

describe('真实模式下的四种页面状态与接线（T034 第四、五、八节）', () => {
  it('加载：请求未兑现时显示骨架', async () => {
    install({ '/api/v1/status': () => new Promise(() => undefined) });
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(pageState()).toBe('loading');
  });

  it('出错：合成失败信封（command 空、exit_code null）只列 messages，不写「命令（…）返回退出码」', async () => {
    install({ '/api/v1/status': () => failEnv(['ERROR: 连不上本机服务（请求没有到达服务）']) });
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(pageState()).toBe('error');
    expect(bodyText()).toContain('没能读到数据');
    expect(bodyText()).toContain('ERROR: 连不上本机服务（请求没有到达服务）');
    expect(bodyText()).not.toContain('返回退出码');
  });

  it('空：信封 ok 且 isEmpty → 空态', async () => {
    install({ '/api/v1/status': () => okEnv([]) });
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(pageState()).toBe('empty');
    expect(bodyText()).toContain('还没有 attempt');
  });

  it('离线：disconnected → danger 横幅、「可能已过期」、data-stale、胶囊「已断开」；恢复后横幅消失', async () => {
    setConnectionState('disconnected');
    install();
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(bodyText()).toContain('与本机服务的连接断开');
    expect(bodyText()).toContain('可能已过期');
    expect(document.querySelector('[data-stale]')).not.toBeNull();
    expect(pillState()).toBe('disconnected');
    expect(pillText()).toBe('已断开');
    act(() => { setConnectionState('connected'); });
    expect(bodyText()).not.toContain('与本机服务的连接断开');
    expect(pillState()).toBe('connected');
    expect(pillText()).toBe('已连接');
  });

  it('总览说明：真实模式初值是占位「—」，getMeta() 兑现后是「仓库名 · kit 版本」', async () => {
    const pending: Array<(v: any) => void> = [];
    install({ '/api/v1/meta': () => new Promise((res) => { pending.push(res); }) });
    window.location.hash = '#/overview';
    render(<App />);
    const desc = document.querySelector('.tt-page__desc') as HTMLElement;
    expect((desc.textContent || '').trim()).toBe('—');
    await act(async () => {
      pending.forEach((res) => res(okEnv({ version: 'pi_dispatch 9.9.9', repo_name: 'live-repo' })));
      for (let i = 0; i < 6; i += 1) await Promise.resolve();
    });
    const after = document.querySelector('.tt-page__desc') as HTMLElement;
    expect((after.textContent || '').trim()).toBe('live-repo · kit 9.9.9');
  });

  it('[重新连接] 在真实模式可点并重跑本页 load', async () => {
    install();
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    act(() => { setConnectionState('disconnected'); });
    const btn = reconnectButton();
    expect(btn, '横幅里应有 [重新连接] 按钮').toBeTruthy();
    expect(btn!.disabled).toBe(false);
    const before = count('/api/v1/status');
    await act(async () => { fireEvent.click(btn!); });
    await settle();
    expect(count('/api/v1/status')).toBeGreaterThan(before);
  });

  it('已有数据时刷新失败且已断开：保留旧数据与原 phase、不出错块、不上报 error', async () => {
    install();
    window.location.hash = '#/overview';
    render(<App />);
    await settle();
    expect(pageState()).toBe('data');
    act(() => { setConnectionState('disconnected'); });
    responders['/api/v1/status'] = () => failEnv(['ERROR: 连不上本机服务（请求没有到达服务）']);
    const btn = reconnectButton();
    expect(btn, '横幅里应有 [重新连接] 按钮').toBeTruthy();
    await act(async () => { fireEvent.click(btn!); });
    await settle();
    expect(pageState()).toBe('data');
    expect(document.querySelector('[data-page="overview"]')).not.toBeNull();
    expect(bodyText()).not.toContain('没能读到数据');
    expect(bodyText()).not.toContain('读取失败');
  });
});
"""

PROBE_FRAME = r"""
import * as React from 'react';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PageFrame } from '../src/shell/PageFrame';
import { ShellStatusProvider, type PageReport } from '../src/shell/ShellStatusContext';
import { setConnectionState } from '../src/live/connection';
import { setLiveClientForTests } from '../src/live/mode';

vi.setConfig({ testTimeout: 60000 });

const fakeClient: any = {
  get: () => Promise.resolve({ ok: true, exit_code: 0, data: {}, output: [], messages: [], command: [], elapsed_ms: 0 }),
};

function okEnv(data: unknown) {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command: ['status'], elapsed_ms: 3 };
}
function syntheticFail(messages: string[]) {
  return { ok: false, exit_code: null, data: null, output: [], messages, command: [], elapsed_ms: 0 };
}
function fixtureFail() {
  return {
    ok: false, exit_code: 2, data: null, output: [],
    messages: ['ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied'],
    command: ['status'], elapsed_ms: 0,
  };
}

function Harness({ load, isEmpty }: { load: () => Promise<any>; isEmpty: (d: any) => boolean }) {
  const [reports, setReports] = React.useState<string[]>([]);
  const report = React.useCallback((r: PageReport) => setReports((xs) => [...xs, r.phase]), []);
  return (
    <ShellStatusProvider value={report}>
      <PageFrame title="示例页" load={load} isEmpty={isEmpty}>
        {(data: any) => <p data-testid="tt-frame-row">{data.name}</p>}
      </PageFrame>
      <p data-testid="tt-frame-reports">{reports.join(',')}</p>
    </ShellStatusProvider>
  );
}

function bodyText(): string {
  return (document.body.textContent || '').replace(/\s+/g, ' ');
}
function pageState(): string | null {
  const el = document.querySelector('[data-page-state]');
  return el ? el.getAttribute('data-page-state') : null;
}
function reconnectButton(): HTMLButtonElement | undefined {
  return (Array.from(document.querySelectorAll('button')) as HTMLButtonElement[])
    .find((b) => (b.textContent || '').trim() === '重新连接');
}
function reports(): string {
  const el = document.querySelector('[data-testid="tt-frame-reports"]');
  return (el && el.textContent) || '';
}

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}

beforeEach(() => {
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
});
afterEach(async () => {
  cleanup();
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
});

describe('PageFrame 的错误文案按信封形状判定（T034 第四节 (b)，两种模式都适用）', () => {
  it('合成失败信封（command 空数组、exit_code null）只列 messages 原文，不写「命令（…）返回退出码」', async () => {
    const load = () => Promise.resolve(syntheticFail(['ERROR: 连不上本机服务（请求没有到达服务）']));
    render(<Harness load={load} isEmpty={() => false} />);
    await settle();
    expect(pageState()).toBe('error');
    expect(bodyText()).toContain('没能读到数据');
    expect(bodyText()).toContain('ERROR: 连不上本机服务（请求没有到达服务）');
    expect(bodyText()).not.toContain('返回退出码');
  });

  it('夹具形状的信封（command 非空、exit_code 数字）照旧写「命令（status）返回退出码 2」', async () => {
    const load = () => Promise.resolve(fixtureFail());
    render(<Harness load={load} isEmpty={() => false} />);
    await settle();
    expect(bodyText()).toContain('命令（status）返回退出码 2');
    expect(bodyText()).toContain('ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied');
  });
});

describe('PageFrame 的离线与 [重新连接]（T034 第四节 (a)(c)）', () => {
  it('夹具模式（?mock=offline）：横幅在、[重新连接] 仍是禁用入口', async () => {
    window.location.hash = '#/x?mock=offline';
    const load = () => Promise.resolve(okEnv({ name: 'row-1' }));
    render(<Harness load={load} isEmpty={() => false} />);
    await settle();
    expect(bodyText()).toContain('与本机服务的连接断开');
    const btn = reconnectButton();
    expect(btn, '横幅里应有 [重新连接]').toBeTruthy();
    expect(btn!.disabled).toBe(true);
    expect(pageState()).toBe('data');
  });

  it('真实模式：断线出横幅、[重新连接] 可点并重跑 load；成功后数据仍在', async () => {
    setLiveClientForTests(fakeClient);
    let calls = 0;
    const load = () => { calls += 1; return Promise.resolve(okEnv({ name: 'row-1' })); };
    render(<Harness load={load} isEmpty={() => false} />);
    await settle();
    expect(calls).toBe(1);
    act(() => { setConnectionState('disconnected'); });
    expect(bodyText()).toContain('与本机服务的连接断开');
    expect(bodyText()).toContain('可能已过期');
    const btn = reconnectButton();
    expect(btn!.disabled).toBe(false);
    await act(async () => { fireEvent.click(btn!); });
    await settle();
    expect(calls).toBe(2);
    expect(pageState()).toBe('data');
    expect((document.querySelector('[data-testid="tt-frame-row"]') as HTMLElement).textContent).toBe('row-1');
  });

  it('真实模式：已有数据时刷新失败（信封 ok:false）且已断开 → 保留旧数据与原 phase、不上报 error', async () => {
    setLiveClientForTests(fakeClient);
    let fail = false;
    const load = () => (fail
      ? Promise.resolve(syntheticFail(['ERROR: 连不上本机服务（请求没有到达服务）']))
      : Promise.resolve(okEnv({ name: 'row-1' })));
    render(<Harness load={load} isEmpty={() => false} />);
    await settle();
    expect(pageState()).toBe('data');
    act(() => { setConnectionState('disconnected'); });
    fail = true;
    const btn = reconnectButton();
    expect(btn, '横幅里应有 [重新连接] 按钮').toBeTruthy();
    await act(async () => { fireEvent.click(btn!); });
    await settle();
    expect(pageState()).toBe('data');
    expect((document.querySelector('[data-testid="tt-frame-row"]') as HTMLElement).textContent).toBe('row-1');
    expect(bodyText()).not.toContain('没能读到数据');
    expect(reports()).not.toContain('error');
  });

  it('真实模式：已有数据时刷新被拒（Promise 被拒）且已断开 → 同样保留旧数据', async () => {
    setLiveClientForTests(fakeClient);
    let reject = false;
    const load = () => (reject
      ? Promise.reject(new TypeError('net down'))
      : Promise.resolve(okEnv({ name: 'row-1' })));
    render(<Harness load={load} isEmpty={() => false} />);
    await settle();
    act(() => { setConnectionState('disconnected'); });
    reject = true;
    const btn = reconnectButton();
    expect(btn, '横幅里应有 [重新连接] 按钮').toBeTruthy();
    await act(async () => { fireEvent.click(btn!); });
    await settle();
    expect(pageState()).toBe('data');
    expect((document.querySelector('[data-testid="tt-frame-row"]') as HTMLElement).textContent).toBe('row-1');
    expect(bodyText()).not.toContain('没有收到服务的回应');
    expect(bodyText()).not.toContain('没能读到数据');
  });

  it('没有旧数据时失败照旧进 error 态（真实模式）', async () => {
    setLiveClientForTests(fakeClient);
    const load = () => Promise.resolve(syntheticFail(['ERROR: 连不上本机服务（请求没有到达服务）']));
    render(<Harness load={load} isEmpty={() => false} />);
    await settle();
    expect(pageState()).toBe('error');
    expect(bodyText()).toContain('没能读到数据');
  });
});
"""

PROBE_SHELL = r"""
import * as React from 'react';
import { cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TitleBar } from '../src/shell/TitleBar';
import { SHELL_RECENT_REPOS } from '../src/mock/shell';
import { setConnectionState } from '../src/live/connection';
import { setLiveClientForTests } from '../src/live/mode';

vi.setConfig({ testTimeout: 60000 });

const fakeClient: any = {
  get: () => Promise.resolve({ ok: true, exit_code: 0, data: {}, output: [], messages: [], command: [], elapsed_ms: 0 }),
};

function radios(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll('[role="menuitemradio"]')) as HTMLElement[];
}
function openRepoMenu(container: HTMLElement) {
  fireEvent.click(container.querySelector('button[title="切换仓库"]') as HTMLElement);
  return container.querySelector('[role="menu"]') as HTMLElement;
}

beforeEach(() => {
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
});
afterEach(() => {
  cleanup();
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('标题栏的仓库菜单（T034 第三节）', () => {
  it('夹具模式照旧：列 SHELL_RECENT_REPOS，当前项选中，「添加仓库…」禁用', () => {
    window.location.hash = '#/overview';
    const { container } = render(
      <TitleBar theme="dark" onThemeChange={() => undefined} repoName="demo-repo" />,
    );
    const menu = openRepoMenu(container);
    const texts = radios(container).map((el) => (el.textContent || '').trim());
    expect(texts).toEqual([...SHELL_RECENT_REPOS]);
    const checked = radios(container).find((el) => el.getAttribute('aria-checked') === 'true');
    expect((checked && checked.textContent) || '').toContain('demo-repo');
    const disabled = menu.querySelector('[aria-disabled="true"]') as HTMLElement;
    expect((disabled && disabled.textContent) || '').toContain('添加仓库');
    expect((disabled && disabled.textContent) || '').toContain('第二阶段接入');
  });

  it('真实模式：只列当前仓库名一项（radio 且选中），「添加仓库…」照旧禁用', () => {
    setLiveClientForTests(fakeClient);
    const { container } = render(
      <TitleBar theme="dark" onThemeChange={() => undefined} repoName="live-repo" />,
    );
    const menu = openRepoMenu(container);
    const items = radios(container);
    expect(items.length).toBe(1);
    expect((items[0].textContent || '')).toContain('live-repo');
    expect(items[0].getAttribute('aria-checked')).toBe('true');
    const disabled = menu.querySelector('[aria-disabled="true"]') as HTMLElement;
    expect((disabled && disabled.textContent) || '').toContain('添加仓库');
    expect((disabled && disabled.textContent) || '').toContain('第二阶段接入');
  });
});
"""

# 过渡探针：SSE 片（事件流）接通后，「事件流=—」会被推翻，届时按 test_transitional_ 前缀退役本条。
PROBE_PILLROWS = r"""
import * as React from 'react';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TitleBar } from '../src/shell/TitleBar';
import { SHELL_PID, SHELL_STARTED_AT, SHELL_STREAM_SUBSCRIBED } from '../src/mock/shell';
import { setConnectionState } from '../src/live/connection';
import { setLiveClientForTests } from '../src/live/mode';

vi.setConfig({ testTimeout: 60000 });

const fakeClient: any = {
  get: () => Promise.resolve({ ok: true, exit_code: 0, data: {}, output: [], messages: [], command: [], elapsed_ms: 0 }),
};

function pillState(): string | null {
  const el = document.querySelector('.tt-pill');
  return el ? el.getAttribute('data-state') : null;
}
function pillText(): string {
  const el = document.querySelector('.tt-pill__text');
  return (el && el.textContent) || '';
}
function openPill(container: HTMLElement) {
  fireEvent.click(container.querySelector('.tt-pill') as HTMLElement);
  return container.querySelector('.tt-pill-pop') as HTMLElement;
}
function popValues(pop: HTMLElement): string[] {
  return Array.from(pop.querySelectorAll('dd')).map((dd) => (dd.textContent || '').trim());
}

beforeEach(() => {
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
});
afterEach(() => {
  cleanup();
  setConnectionState('connected');
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('胶囊浮层的三行（T034 第三节；SSE 片接事件流后本组退役）', () => {
  it('真实模式：pid、启动于、事件流都显示「—」；胶囊状态取 live（断线「已断开」）', () => {
    setLiveClientForTests(fakeClient);
    const { container } = render(
      <TitleBar theme="dark" onThemeChange={() => undefined} repoName="live-repo" />,
    );
    expect(pillState()).toBe('connected');
    const pop = openPill(container);
    expect(popValues(pop)).toEqual(['—', '—', '—']);
    act(() => { setConnectionState('disconnected'); });
    expect(pillState()).toBe('disconnected');
    expect(pillText()).toBe('已断开');
  });

  it('夹具模式照旧：pid=18244、启动于、事件流=已订阅 /api/v1/events', () => {
    window.location.hash = '#/overview';
    const { container } = render(
      <TitleBar theme="dark" onThemeChange={() => undefined} repoName="demo-repo" />,
    );
    const pop = openPill(container);
    expect(popValues(pop)).toEqual([String(SHELL_PID), SHELL_STARTED_AT, SHELL_STREAM_SUBSCRIBED]);
  });
});
"""

PROBE_TRANSPORT = r"""
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getConnectionState, setConnectionState } from '../src/live/connection';
import { createLiveClient } from '../src/live/transport';

vi.setConfig({ testTimeout: 60000 });

function textResponse(status: number, body: string) {
  return {
    status,
    ok: status >= 200 && status < 300,
    text: async () => body,
    headers: { get: () => null },
  };
}
function jsonResponse(status: number, body: unknown) {
  return textResponse(status, JSON.stringify(body));
}
function respond401() {
  return Promise.resolve(textResponse(401, JSON.stringify({ some: 'body' })));
}

beforeEach(() => {
  setConnectionState('connected');
  delete (window as any).themisHost;
});
afterEach(() => {
  setConnectionState('connected');
  delete (window as any).themisHost;
});

describe('live/transport：宿主接口改成调用时取（T034 第六节）', () => {
  it('先建客户端、后设 window.themisHost：reauth 恰好被调 1 次，信封是 ERROR: 会话已失效', async () => {
    const client = createLiveClient({ fetch: respond401 as any });
    const reauth = vi.fn(() => Promise.resolve({ ok: true }));
    (window as any).themisHost = { reauth };
    const env = await client.get('/x');
    expect(reauth).toHaveBeenCalledTimes(1);
    expect(env.messages).toEqual(['ERROR: 会话已失效']);
    expect(getConnectionState()).toBe('connected');
  });

  it('显式 options.host 仍优先：window.themisHost 出现也不改用', async () => {
    const optionSpy = vi.fn(() => Promise.resolve({ ok: true }));
    const windowSpy = vi.fn(() => Promise.resolve({ ok: true }));
    const client = createLiveClient({ fetch: respond401 as any, host: { reauth: optionSpy } });
    (window as any).themisHost = { reauth: windowSpy };
    const env = await client.get('/x');
    expect(optionSpy).toHaveBeenCalledTimes(1);
    expect(windowSpy).toHaveBeenCalledTimes(0);
    expect(env.messages).toEqual(['ERROR: 会话已失效']);
  });

  it('没给 options.host 且调用时也没有 window.themisHost：不抛错，仍回同一句', async () => {
    const client = createLiveClient({ fetch: respond401 as any });
    const env = await client.get('/x');
    expect(env.messages).toEqual(['ERROR: 会话已失效']);
  });
});
"""

PROBE_SPECS = {
    "hook": (PROBE_HOOK, (HOOK_REL,)),
    "app": (PROBE_APP, (APP_REL,)),
    "states": (PROBE_STATES, (APP_REL, OVERVIEW_REL)),
    "frame": (PROBE_FRAME, (PAGEFRAME_REL,)),
    "shell": (PROBE_SHELL, (TITLEBAR_REL,)),
    "pillrows": (PROBE_PILLROWS, (TITLEBAR_REL, PILL_REL)),
    "transport": (PROBE_TRANSPORT, (TRANSPORT_REL,)),
}
PROBE_ORDER = ("hook", "app", "states", "frame", "shell", "pillrows", "transport")


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
                name = f"probe-{uid}-t034-{key}.test.tsx"
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
    """P1 / V01–V03、D10：npm ci（或已在的依赖）、npm test（全绿）、npm run build（tsc --noEmit + vite build）、
    npm run check:contract 都退出 0；依赖文件一个字节没动。"""
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


def test_p2_probe_hook(pipeline):
    """P2 / D02：useShellConnection 探针全绿。"""
    assert_probe_ok(pipeline, "hook")


def test_p3_probe_app(pipeline):
    """P3 / D03、D04、D07：App 级真实模式探针全绿。"""
    assert_probe_ok(pipeline, "app")


def test_p4_probe_states(pipeline):
    """P4 / D06、D03、D01：四种页面状态与总览说明探针全绿。"""
    assert_probe_ok(pipeline, "states")


def test_p5_probe_frame(pipeline):
    """P5 / D06、D04：PageFrame 直测探针全绿。"""
    assert_probe_ok(pipeline, "frame")


def test_p6_probe_shell(pipeline):
    """P6 / D05、D04：标题栏仓库菜单探针全绿。"""
    assert_probe_ok(pipeline, "shell")


def test_transitional_p7_probe_pillrows(pipeline):
    """过渡 / D03：真实模式胶囊浮层三行「—」——SSE 片（事件流接通）会推翻「事件流=—」，届时退役本条。"""
    assert_probe_ok(pipeline, "pillrows")


def test_p8_probe_transport(pipeline):
    """P8 / D08：宿主接口调用时取的探针全绿。"""
    assert_probe_ok(pipeline, "transport")
