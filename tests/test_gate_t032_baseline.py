"""T032 战前门禁：桌面端前端外壳页接外壳接口（D3 之七）——shellBridge 与四条取实例路径的黑盒基准测试
（合同 t032-desktop-shellpages-live v2，基线 344b5d0）。

被测对象是 ``desktop/web/``：新增 ``src/shellpages/shellBridge.ts``（唯一的 ``window.themisShell`` 读取点与全局声明、
十成员核对、WeakMap 包装缓存、``cancelled`` 当正常结束、「没有连上外壳」单例）；``src/shellpages/shellContext.tsx`` 的
``useThemisShell`` 改成四条路径（Provider 注入 → bridge 真实例 → 夹具模式内存桩 → 真实模式「外壳不可用」实例）；
``src/pages/SettingsPage.tsx`` 本片一个字不改（合同 v2：getState 被拒照旧冒给 PageFrame，显示通用出错块
「没有收到服务的回应」）；``FirstRunView.tsx`` 加错误块
（``tt-fr__err`` + role=alert）并接住所有外壳调用的拒绝；``ServiceStatusView.tsx`` 在说明行位置显示错误、
``restartService`` 被拒时复位「正在重启…」；执行端另写两份测试 ``tests/shellpages-live-bridge.test.tsx``（行为）与
``tests/shellpages-live-bridge-static.test.ts``（静态）。

基线（344b5d0）上 ``shellBridge.ts`` 与两份新测试不存在，``shellContext.tsx`` 只有两条路径，两个视图没有出错分支，
所以本文件的失败落在「文件不存在」「记号不在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，
所有仓库文件的读取都发生在用例函数里；流水线（装依赖之后起 build、Vitest 与探针）放在 ``pipeline`` 会话级夹具里，
候选里没有 ``src/shellpages/shellBridge.ts`` 时不装依赖、不起 Vitest。

结构（编号对应合同 DoD 的 D01–D13）：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：三个新文件在位（D01、D13）；shellBridge 的导出、十成员
  逐字、全局声明形状、WeakMap、错误文案与静态禁词（D01、D02、D05、D10）；唯一读取点与声明点剥注释扫整个 src（D01）；
  shellContext 的四条路径顺序与「判定不在模块加载时缓存」（D04）；两个视图的
  出错记号与不加 role=status（D07）；执行端两份测试在位、不用 skip/only/todo、记号齐（D10、D13）；门禁自检。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：npm ci、npm test（全绿，现有
  shellpages-*.test.* 一条不改全过，D09）、npm run build（含 tsc --noEmit，D11）、
  ``node scripts/check-live-build.mjs``（三种 NODE_ENV 取值、LIVE_BUILD_OK 3/3，D11）、``npm run check:contract``（D11），
  再把三份探针写成 ``gate-probe/probe-<唯一标识>-t032-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，
  ``finally`` 里删除；依赖文件（package.json、package-lock.json）前后 digest 一致（D13）。

探针（Vitest + jsdom，全部自包含，辅助函数不跨文件共享）：

- bridge：D02（十成员核对：缺成员、非函数、非对象都当作没有）、D03（同一对象同一包装引用、不同对象不同引用、
  冻结对象可当 WeakMap 键、不在原对象上挂属性、九个方法原样转发且返回同一个 Promise、resetShellBridge 清缓存）、
  D05（「外壳不可用」九个方法被拒 message 逐字、on 同步返回空退订不抛不调 listener、模块级单例）、
  cancelled 当正常结束、on 的退订转发。
- context：D04（假外壳优先于桩且不创建桩——vi.mock 包住 createShellStub 计调用次数；成员不全回到桩；
  Provider 注入最优先；真实模式（vi.mock 局部替换 liveModeIsReal）首启页与服务状态页显示「没有连上外壳」、
  不创建桩、shell= 不起作用，设置页照旧走 PageFrame 通用出错块（合同 v2：设置页不在断言面内）；引用稳定）。
- views：D06（Provider 注入被拒的 shell 渲染 SettingsPage，断言现状：PageFrame 通用出错块「没有收到服务的回应」，
  不显示「没有连上外壳」也不做信封）、D07（首启页错误块的位置、role=alert、无 data-step-error、
  空步骤列表、自动启动与「更换…」的失败也接住；服务状态页说明行显示错误、不加 role=alert、restartService 被拒
  复位「正在重启…」）、D08（假 on 的退订函数在卸载时被调一次）。

过渡断言（``test_transitional_`` 开头，docstring 写明哪一片推翻，站主按名字退役）：

- ``test_transitional_s06_settings_page_untouched``：SettingsPage.tsx 与基线 344b5d0 逐字一致（合同 v2：本片
  一个字不改，getState 被拒照旧冒给 PageFrame 显示通用出错块）——主窗口经 host.openSettings() 打开设置窗口的
  那一片合法改动它时按名字退役。
- ``test_transitional_s09_baseline_files_untouched``：本片禁改的文件（themisShell.ts、shellStub.ts、ShellWindow.tsx、
  SettingsView.tsx、PageFrame.tsx、App.tsx、vite.config.ts、check-live-build.mjs、src/live/**、两份静态扫描测试、
  现有 8 份 shellpages-*.test.*、场景夹具）与基线 344b5d0 逐字一致——后续片（连接状态片 T029、SSE 片、host 接口片、
  作业/检索片）合法改动这些文件时按名字退役。
- ``test_transitional_p2/p3/p4``：探针版断言里钉着「夹具模式下桩从不 reject」「真实模式判定只看构建期常量」的现状，
  行为被后续片合法改变时同样按名字退役（探针文件是门禁自带的，探针用例随本文件一起退役）。

合同没有写死、门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出）：「声明点」的检测是剥注释后
``declare global`` 块内出现 ``themisShell`` 后跟可选问号再加冒号的成员形态（live/transport.ts 里给 themisHost 的声明
不算误伤）；
``liveModeIsReal`` 「不在模块加载时缓存」的静态检测是它所有调用行都有缩进（不在模块顶层）；探针里假外壳的
getState 数据用最小形状（service idle、空仓库表），不断言页面渲染出它的内容。
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
SP_REL = f"{SRC_REL}/shellpages"
TESTS_REL = f"{WEB_REL}/tests"
BASE_SHA = "344b5d09d69e47e7a29d4833bb65c2e1fab00332"

# 合同 Scope：新增源码与测试（allowed_new_files）
BRIDGE_REL = f"{SP_REL}/shellBridge.ts"
CONTEXT_REL = f"{SP_REL}/shellContext.tsx"
SETTINGS_PAGE_REL = f"{SRC_REL}/pages/SettingsPage.tsx"
FIRST_RUN_REL = f"{SP_REL}/FirstRunView.tsx"
SERVICE_VIEW_REL = f"{SP_REL}/ServiceStatusView.tsx"
EXECUTOR_TESTS = ("shellpages-live-bridge.test.tsx", "shellpages-live-bridge-static.test.ts")

# 合同第二节：SHELL_MEMBERS 十个成员名逐字
SHELL_MEMBERS = ("getState", "pickRepo", "pickPython", "pickKit", "pickTranscriptDir", "saveSettings", "startService",
                 "restartService", "openExternal", "on")
NINE_METHODS = tuple(m for m in SHELL_MEMBERS if m != "on")

MSG_NO_SHELL = "没有连上外壳"
MSG_FALLBACK = "操作失败"
CANCELLED = "cancelled"

NETWORK_WORDS = ("fetch", "XMLHttpRequest", "EventSource", "WebSocket")
NETWORK_RE = re.compile(r"(?<![A-Za-z0-9_$])(?:fetch|XMLHttpRequest|EventSource|WebSocket)(?![A-Za-z0-9_$])")
API_IMPORT_RE = re.compile(r"from\s+['\"]([^'\"]+)['\"]")
API_SPECIFIER_RE = re.compile(r"(^|/)api(\.ts)?$")
# 读取 window.themisShell / globalThis.themisShell（剥注释后；字符串也算）
READ_SHELL_RE = re.compile(r"(?:window|globalThis)\s*\.\s*themisShell")
DECLARE_GLOBAL_RE = re.compile(r"declare\s+global")
# 五个点名文件（D01）：代码与字符串里不许出现这四类词（剥注释，字符串也算）
POINTED_FILES = (CONTEXT_REL, f"{SP_REL}/ShellWindow.tsx", SETTINGS_PAGE_REL, FIRST_RUN_REL, SERVICE_VIEW_REL)
POINTED_FORBIDDEN = ("window.themisShell", "globalThis.themisShell", "declare global", "themisHost")

_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)

# 基线 344b5d0 上一个字不许动的文件（本片 forbidden_paths 里与前端相关的部分；后续片合法改动时按名字退役）
# 站主 2026-11-13 按名字退掉：App.tsx、shell/PageFrame.tsx、live/transport.ts（T034 连接状态片要改）、live/connection.ts（T036 事件流片）、
# live/mode.ts（T037 写操作片）
# 站主 2026-11-14 按名字退掉：shellpages/themisShell.ts、mock/shellpages-scenarios.ts、tests/shellpages-service-status.test.tsx
# （T039 服务状态页说明片：exited 状态带上“跑起来之后才退出”，补场景与退出码 1 两种情形的用例）
UNTOUCHED_REL = (
    f"{SP_REL}/shellStub.ts",
    f"{SP_REL}/ShellWindow.tsx",
    f"{SP_REL}/SettingsView.tsx",
    f"{SP_REL}/shellWindowRoute.ts",
    f"{WEB_REL}/vite.config.ts",
    f"{WEB_REL}/scripts/check-live-build.mjs",
    f"{TESTS_REL}/shellpages-static.test.ts",
    f"{TESTS_REL}/cleanup2-static.test.ts",
) + tuple(f"{TESTS_REL}/shellpages-{name}" for name in (
    "stub.test.ts", "route.test.ts", "first-run.test.tsx", "settings.test.tsx",
    "app.test.tsx", "isolation.test.tsx", "static.test.ts"))


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

def _norm(text):
    return text.replace("\r\n", "\n")


def read_rel(rel):
    return _norm((REPO_ROOT / rel).read_text(encoding="utf-8"))


def need_file(rel):
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return path


def need_text(rel):
    need_file(rel)
    return read_rel(rel)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def fail_if(problems, title):
    assert not problems, f"{title}：" + "；".join(problems)


def net_word_hits(text):
    return [w for w in NETWORK_WORDS if re.search(rf"(?<![A-Za-z0-9_$]){w}(?![A-Za-z0-9_$])", text)]


def api_import_problems(text):
    """直接导入说明符以 api.ts / api / …/api 结尾（合同第八节：src/shellpages/** 不导入 api 模块）。"""
    out = []
    for m in API_IMPORT_RE.finditer(text):
        spec = m.group(1)
        if API_SPECIFIER_RE.search(spec):
            out.append(f"导入了 api 模块（{spec}）")
    return out


def shell_read_or_declare_hits(text):
    """剥注释后的文本里对 themisShell 的读取与全局声明（合同 D01：只许出现在 shellBridge.ts）。

    读取：window.themisShell / globalThis.themisShell。声明：declare global 起到其后第一个 `}` 的块内出现
    `themisShell :` / `themisShell?:` 成员形态（live/transport.ts 里给 themisHost 的声明不含 themisShell 成员，
    不会误伤；'themisShell.getState' 这类 command 字符串、'./themisShell' 导入说明符后面跟的不是冒号，
    同样不会误伤）。
    """
    hits = []
    if READ_SHELL_RE.search(text):
        hits.append("读取 window/globalThis.themisShell")
    for m in DECLARE_GLOBAL_RE.finditer(text):
        block_end = text.find("}", m.end())
        block = text[m.end():block_end if block_end >= 0 else m.end() + 300]
        if re.search(r"\bthemisShell\s*\??\s*:", block):
            hits.append("themisShell 的全局声明")
    return hits


def src_ts_files():
    """desktop/web/src 下全部 .ts/.tsx（D01 的唯一读取点扫描面，与执行端静态测试第十节一致）。"""
    return sorted(p for p in SRC.rglob("*") if p.suffix in (".ts", ".tsx") and p.is_file())


def git_show_base(rel):
    """基线 BASE_SHA 里该文件的内容（行尾归一 LF）；文件不在基线里返回 None。"""
    proc = subprocess.run(["git", "show", f"{BASE_SHA}:{rel}"], cwd=REPO_ROOT, capture_output=True, timeout=120)
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n")


def file_digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def git_status_set():
    proc = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, timeout=120)
    out = proc.stdout.decode("utf-8", "replace")
    return {line.strip() for line in out.splitlines() if line.strip()}


def tail_text(text, max_chars=3500, max_lines=45):
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    text = "\n".join(lines)
    return text[-max_chars:]


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_new_files_present():
    """D01、D13：合同 allowed_new_files 的三个文件都在（shellBridge.ts 与两份执行端测试）。"""
    for rel in (BRIDGE_REL,) + tuple(f"{TESTS_REL}/{name}" for name in EXECUTOR_TESTS):
        need_file(rel)


def test_s02_shell_bridge_exports_and_shape():
    """D01、D02、D03、D05：shellBridge.ts 的导出名、SHELL_MEMBERS 十成员逐字、全局声明形状、
    WeakMap 缓存、错误文案与 cancelled 的处理记号。"""
    text = need_text(BRIDGE_REL)
    assert "SHELL_MEMBERS" in text, "应导出 SHELL_MEMBERS"
    for name in SHELL_MEMBERS:
        assert f"'{name}'" in text or f'"{name}"' in text, f"SHELL_MEMBERS 应含成员名 {name}（带引号逐字）"
    for fn in ("shellBridgeInstance", "unavailableShell", "resetShellBridge"):
        assert re.search(rf"export\s+(?:function|const)\s+{fn}\b", text), f"应导出 {fn}"
    assert re.search(r"themisShell\s*\?:\s*unknown", text), \
        "全局声明应是 interface Window 里的 themisShell?: unknown（可选、类型 unknown）"
    assert "WeakMap" in text, "包装缓存应使用 WeakMap（原对象可能被冻结，不能挂属性）"
    assert MSG_NO_SHELL in text, f"「外壳不可用」实例的错误文案应逐字出现：{MSG_NO_SHELL}"
    assert CANCELLED in text, "openExternal 的 cancelled 应当作正常结束（文件里应有 cancelled 记号）"
    assert "interface Window" in text and "declare global" in text, "全局声明就地写在 shellBridge.ts 里"


def test_s03_shell_bridge_static_rules():
    """D10：shellBridge.ts 连注释里都没有四个网络词整词；不导入 api 模块；剥注释后没有 themisHost。"""
    raw = need_text(BRIDGE_REL)
    fail_if(net_word_hits(raw), "shellBridge.ts 里不许出现网络词（逐行扫原文、不剥注释，注释与字符串都算）")
    fail_if(api_import_problems(raw), "shellBridge.ts 不许导入 api 模块")
    stripped = strip_ts_comments(raw)
    assert "themisHost" not in stripped, "shellBridge.ts（剥注释后）不应出现 themisHost"


def test_s04_unique_read_point():
    """D01：整个 desktop/web/src 里，window.themisShell / globalThis.themisShell 的读取与 themisShell 的
    全局声明只出现在 shellBridge.ts；五个点名文件的代码与字符串里不出现那四类词。"""
    bridge_text = need_text(BRIDGE_REL)
    bridge_stripped = strip_ts_comments(bridge_text)
    hits = shell_read_or_declare_hits(bridge_stripped)
    assert "读取 window/globalThis.themisShell" in hits, "shellBridge.ts 应当是读取 window.themisShell 的那一个文件"
    assert "themisShell 的全局声明" in hits, "shellBridge.ts 应当就地声明全局 themisShell"
    problems = []
    for path in src_ts_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel == BRIDGE_REL:
            continue
        stripped = strip_ts_comments(_norm(path.read_text(encoding="utf-8")))
        for hit in shell_read_or_declare_hits(stripped):
            problems.append(f"{rel}：{hit}")
    fail_if(problems, "themisShell 的读取与全局声明只许出现在 src/shellpages/shellBridge.ts")
    # 五个点名文件（D01）：剥注释后不出现 window.themisShell / globalThis.themisShell / declare global / themisHost
    pointed = []
    for rel in POINTED_FILES:
        path = REPO_ROOT / rel
        if not path.is_file():
            pointed.append(f"{rel} 不存在")
            continue
        stripped = strip_ts_comments(_norm(path.read_text(encoding="utf-8")))
        for word in POINTED_FORBIDDEN:
            if word in stripped:
                pointed.append(f"{rel} 的代码或字符串里出现了 {word}")
    fail_if(pointed, "点名的五个文件里不许出现这四类词（剥注释，字符串也算）")


def test_s05_shell_context_four_paths():
    """D04：shellContext.tsx 从 ../live/mode 引入 liveModeIsReal、从 ./shellBridge 引入
    shellBridgeInstance 与 unavailableShell；useThemisShell 的四条路径按合同顺序；liveModeIsReal
    的调用不在模块加载时缓存（调用行都有缩进，不在模块顶层）；导出三件套照旧。"""
    text = need_text(CONTEXT_REL)
    m = re.search(r"from\s+['\"]([^'\"]*live/mode[^'\"]*)['\"]", text)
    assert m, "shellContext.tsx 应从 ../live/mode 引入判定"
    assert not API_SPECIFIER_RE.search(m.group(1)), "引入 live/mode 的路径不许以 /api 结尾"
    assert "liveModeIsReal" in text, "应引入 liveModeIsReal"
    bridge_import = re.search(r"from\s+['\"]([^'\"]*shellBridge[^'\"]*)['\"]", text)
    assert bridge_import, "shellContext.tsx 应从 ./shellBridge 引入 bridge 实例"
    assert "shellBridgeInstance" in text and "unavailableShell" in text, "应引入 shellBridgeInstance 与 unavailableShell"
    for export in ("ThemisShellProvider", "useThemisShell", "resetShellStubs"):
        assert re.search(rf"export\s+(?:function|const|interface)\s+{export}\b", text), f"导出名 {export} 应照旧"
    # 四条路径的顺序：useThemisShell 函数体内 provided → shellBridgeInstance( → liveModeIsReal( → stubFor( → unavailableShell(
    fn = re.search(r"export function useThemisShell[^{]*\{", text)
    assert fn, "找不到 useThemisShell 的函数体"
    body_start = fn.end()
    next_export = re.search(r"\nexport ", text[body_start:])
    body = text[body_start:body_start + next_export.start()] if next_export else text[body_start:]
    order = {}
    for token, label in (("provided", "Provider 注入"), ("shellBridgeInstance(", "bridge 真实例"),
                         ("liveModeIsReal(", "模式判定"), ("stubFor(", "夹具桩"), ("unavailableShell(", "外壳不可用")):
        idx = body.find(token)
        assert idx >= 0, f"useThemisShell 里应出现 {label}（{token}）"
        order[label] = idx
    labels = ("Provider 注入", "bridge 真实例", "模式判定", "夹具桩", "外壳不可用")
    for a, b in zip(labels, labels[1:]):
        assert order[a] < order[b], f"useThemisShell 里 {a} 应排在 {b} 之前（合同第三节逐条顺序）"
    # 判定不在模块加载时缓存：liveModeIsReal( 的调用行都有缩进（模块顶层的 const X = liveModeIsReal() 行首无缩进）
    top_level = [
        line.strip() for line in text.splitlines()
        if "liveModeIsReal(" in line and not line.startswith((" ", "\t", "//", "*"))
        and "import" not in line and "from" not in line
    ]
    fail_if(top_level, "liveModeIsReal() 不许在模块顶层调用（判定结果不在模块加载时缓存，vi.mock 局部替换才生效）")


def test_transitional_s06_settings_page_untouched():
    """过渡 / D06、D13（合同 v2）：SettingsPage.tsx 本片一个字不改——与基线 344b5d0 逐字一致。
    现状：load 是 useCallback 包的 getState().then(...)（依赖 [shell]、无 async/await、不传 isEmpty、
    command 是 'themisShell.getState'），reject 不接住、冒给 PageFrame 显示通用出错块「没有收到服务的回应」
    （desktop/web/tests/shellpages-settings.test.tsx 与 T012 门禁逐字断言的就是这个）。

    主窗口经 host.openSettings() 打开设置窗口的那一片（合同 Non-goals 的已知不足）合法改动本文件时，
    按名字退役本条。
    """
    path = need_file(SETTINGS_PAGE_REL)
    base = git_show_base(SETTINGS_PAGE_REL)
    assert base is not None, f"{SETTINGS_PAGE_REL} 应在基线 {BASE_SHA[:8]} 里（它是既有文件，本片不改）"
    assert _norm(path.read_text(encoding="utf-8")) == base,         f"{SETTINGS_PAGE_REL} 与基线 {BASE_SHA[:8]} 不一致（合同 v2：本片一个字不改它，getState 被拒照旧冒给 PageFrame）"


def test_s07_views_error_copies():
    """D07：两个视图里出现「操作失败」兜底与既有出错位置；不新增 role=status；服务状态页不加 role=alert。"""
    first = strip_ts_comments(need_text(FIRST_RUN_REL))
    assert MSG_FALLBACK in first, f"FirstRunView 应有兜底文案 {MSG_FALLBACK}"
    assert 'role="alert"' in first, "FirstRunView 既有 role=alert 记号应在（错误块复用它）"
    assert 'role="status"' not in first, "FirstRunView 不许出现 role=status"
    service = strip_ts_comments(need_text(SERVICE_VIEW_REL))
    assert MSG_FALLBACK in service, f"ServiceStatusView 应有兜底文案 {MSG_FALLBACK}"
    assert "tt-ss__note" in service, "错误消息应显示在说明行位置（复用 tt-ss__note）"
    assert 'role="alert"' not in service, "ServiceStatusView 不加 role=alert（照它的头注释）"
    assert 'role="status"' not in service, "ServiceStatusView 不许出现 role=status"


def test_s08_executor_tests_present():
    """D13、D10：执行端两份新测试在位、不用 skip/only/todo、记号齐（行为测试包 createShellStub 计数与
    「没有连上外壳」；静态测试断言 shellBridge 的唯一读取点）。"""
    for name, tokens in (
        ("shellpages-live-bridge.test.tsx", ("createShellStub", MSG_NO_SHELL, "themisShell")),
        ("shellpages-live-bridge-static.test.ts", ("shellBridge", "themisShell")),
    ):
        rel = f"{TESTS_REL}/{name}"
        text = need_text(rel)
        for token in tokens:
            assert token in text, f"{rel} 里应出现记号 {token}"
        assert not re.search(r"\.(skip|only|todo)\s*\(", text), f"{rel} 不许用 skip/only/todo"
        assert not re.search(r"\b(?:it|describe|test)\.(?:skip|only|todo)\b", text), f"{rel} 不许用 it.skip 之类"


def test_transitional_s09_baseline_files_untouched():
    """过渡 / D09、D11、D13：本片禁改的文件与基线 344b5d0 逐字一致（themisShell 接口、桩、外壳窗口、
    设置视图、PageFrame、App、src/live/**、vite.config.ts、构建核对脚本、两份静态扫描测试、现有 8 份
    shellpages-*.test.*、场景夹具）。

    后续片（连接状态片 T029、SSE 片、host 接口片、作业/检索片、再动 App 的片）合法改动其中任何一个文件时，
    按名字退役本条。
    """
    problems = []
    for rel in UNTOUCHED_REL:
        path = REPO_ROOT / rel
        if not path.is_file():
            problems.append(f"{rel} 不存在（本片不许删它）")
            continue
        base = git_show_base(rel)
        if base is None:
            problems.append(f"{rel} 不在基线 {BASE_SHA[:8]} 里（不该有新文件出现在禁改名单）")
            continue
        if _norm(path.read_text(encoding="utf-8")) != base:
            problems.append(f"{rel} 与基线 {BASE_SHA[:8]} 不一致（本片一个字不许动它）")
    fail_if(problems, "禁改文件被动了")


def test_gate_selfcheck_read_scan():
    """门禁自检：读取/声明检测对正负样本都判对。"""
    good_bridge = "declare global { interface Window { themisShell?: unknown } } " \
                  "export function shellBridgeInstance() { return window.themisShell ? 1 : null; }"
    assert shell_read_or_declare_hits(good_bridge) == ["读取 window/globalThis.themisShell", "themisShell 的全局声明"]
    bad_read = "export function useThemisShell() { return window.themisShell.getState(); }"
    assert "读取 window/globalThis.themisShell" in shell_read_or_declare_hits(bad_read)
    bad_declare = "declare global { interface Window { themisShell?: unknown } } export const x = 1;"
    assert "themisShell 的全局声明" in shell_read_or_declare_hits(bad_declare)
    # 不误伤：themisHost 的声明、'themisShell.getState' 的 command 字符串、导入说明符
    ok = "declare global { interface Window { themisHost?: unknown } } const c = ['themisShell.getState']; " \
         "import type { ShellState } from './themisShell';"
    assert shell_read_or_declare_hits(ok) == []


def test_gate_selfcheck_net_and_api_scan():
    """门禁自检：网络词整词与 api 导入检测对正负样本都判对。"""
    assert net_word_hits("const x = fetch('/x')") == ["fetch"]
    assert net_word_hits("prefetched") == []
    assert api_import_problems("import { x } from '../api'") == ["导入了 api 模块（../api）"]
    assert api_import_problems("import { x } from '../api.ts'") != []
    assert api_import_problems("import { liveModeIsReal } from '../live/mode'") == []


# ---------------------------------------------------------------------------
# 探针源码（Vitest + jsdom，自包含）
# ---------------------------------------------------------------------------

PROBE_PRELUDE = r"""
import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

async function drainNav() {
  for (let i = 0; i < 2; i += 1) {
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  }
}
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) {
      await Promise.resolve();
    }
  });
}
function textOf(el: Element | null): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function btn(root: ParentNode, text: string): HTMLButtonElement {
  const hit = (Array.from(root.querySelectorAll('button')) as HTMLButtonElement[])
    .filter((b) => textOf(b) === text)[0];
  expect(hit, '找不到文字为「' + text + '」的按钮').toBeTruthy();
  return hit;
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  const mod: any = await import('../src/App');
  const App = mod.default ?? mod.App;
  expect(App, 'src/App.tsx 应导出 App').toBeTruthy();
  const out = render(<App />);
  await settle();
  return out;
}
"""

PROBE_BRIDGE = PROBE_PRELUDE + r"""
const MEMBERS = ['getState', 'pickRepo', 'pickPython', 'pickKit', 'pickTranscriptDir', 'saveSettings', 'startService', 'restartService', 'openExternal', 'on'];
const NINE = MEMBERS.filter((m) => m !== 'on');

async function bridge(): Promise<any> {
  return await import('../src/shellpages/shellBridge');
}
function fakeShell(overrides?: Record<string, unknown>): any {
  const shell: Record<string, unknown> = {
    getState: vi.fn(() => Promise.resolve({ service: { kind: 'idle' } })),
    pickRepo: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickPython: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickKit: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickTranscriptDir: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    saveSettings: vi.fn(() => Promise.resolve({ service: { kind: 'idle' } })),
    startService: vi.fn(() => Promise.resolve(undefined)),
    restartService: vi.fn(() => Promise.resolve(undefined)),
    openExternal: vi.fn(() => Promise.resolve(undefined)),
    on: vi.fn(() => vi.fn()),
  };
  return Object.assign(shell, overrides ?? {});
}
function put(shell: unknown) {
  (window as any).themisShell = shell;
}
afterEach(() => {
  delete (window as any).themisShell;
});

describe('D02 十成员核对', () => {
  it('SHELL_MEMBERS 是十个成员名的只读数组，逐字对得上', async () => {
    const m = await bridge();
    expect(Array.isArray(m.SHELL_MEMBERS)).toBe(true);
    expect(m.SHELL_MEMBERS.length).toBe(10);
    expect([...m.SHELL_MEMBERS].sort()).toEqual([...MEMBERS].sort());
  });

  it('十成员齐全时返回可用实例；读不到、非对象、缺一个成员、某个成员不是函数都当作没有（null）', async () => {
    const m = await bridge();
    delete (window as any).themisShell;
    expect(m.shellBridgeInstance(), '没有 themisShell').toBeNull();
    put(undefined);
    expect(m.shellBridgeInstance(), 'undefined').toBeNull();
    put(null);
    expect(m.shellBridgeInstance(), 'null').toBeNull();
    put(42);
    expect(m.shellBridgeInstance(), '数字').toBeNull();
    put('shell');
    expect(m.shellBridgeInstance(), '字符串').toBeNull();
    for (const missing of MEMBERS) {
      const fake = fakeShell();
      delete fake[missing];
      put(fake);
      expect(m.shellBridgeInstance(), `缺 ${missing} 应当作没有`).toBeNull();
    }
    for (const broken of MEMBERS) {
      const fake = fakeShell();
      fake[broken] = 'not-a-function';
      put(fake);
      expect(m.shellBridgeInstance(), `${broken} 不是函数应当作没有`).toBeNull();
    }
    put(fakeShell());
    const got = m.shellBridgeInstance();
    expect(got, '十成员齐全给实例').not.toBeNull();
    expect(typeof got.getState).toBe('function');
  });
});

describe('D03 WeakMap 包装缓存与引用稳定', () => {
  it('同一个原对象两次取到同一个包装引用；不同的原对象取到不同包装；不在原对象上挂任何属性', async () => {
    const m = await bridge();
    const fake = fakeShell();
    put(fake);
    const before = Object.getOwnPropertyNames(fake).slice().sort();
    const w1 = m.shellBridgeInstance();
    const w2 = m.shellBridgeInstance();
    expect(w1).toBe(w2);
    const after = Object.getOwnPropertyNames(fake).slice().sort();
    expect(after, '不许在原对象上挂缓存属性').toEqual(before);
    const other = fakeShell();
    put(other);
    const w3 = m.shellBridgeInstance();
    expect(w3).not.toBe(w1);
  });

  it('冻结的原对象也能当键：返回实例且引用稳定（真外壳的对象是被冻结的）', async () => {
    const m = await bridge();
    const frozen = Object.freeze(fakeShell());
    put(frozen);
    const w1 = m.shellBridgeInstance();
    expect(w1).not.toBeNull();
    put(frozen);
    expect(m.shellBridgeInstance()).toBe(w1);
  });

  it('包装只做转发：九个方法原样调用原对象的同名方法，参数透传，返回的 Promise 原样交出去（同一个 Promise 对象）', async () => {
    const m = await bridge();
    const fixed = Promise.resolve({ service: { kind: 'idle' } });
    const fixedSave = Promise.resolve({ service: { kind: 'idle' } });
    const fake = fakeShell({ getState: vi.fn(() => fixed), saveSettings: vi.fn(() => fixedSave) });
    put(fake);
    const w = m.shellBridgeInstance();
    expect(w.getState()).toBe(fixed);
    expect(w.saveSettings({ theme: 'dark' })).toBe(fixedSave);
    expect((fake.saveSettings as any).mock.calls).toEqual([[{ theme: 'dark' }]]);
    await w.startService('repo-1');
    expect((fake.startService as any).mock.calls).toEqual([['repo-1']]);
  });

  it('resetShellBridge 清掉包装缓存：同一对象重新取到的是新的包装；不影响「外壳不可用」单例', async () => {
    const m = await bridge();
    const fake = fakeShell();
    put(fake);
    const w1 = m.shellBridgeInstance();
    const u1 = m.unavailableShell();
    m.resetShellBridge();
    const w2 = m.shellBridgeInstance();
    expect(w2).not.toBe(w1);
    expect(m.unavailableShell()).toBe(u1);
  });
});

describe('D05 外壳不可用实例与 on/openExternal 语义', () => {
  it('九个方法都返回被拒的 Promise，message 逐字「没有连上外壳」；on 同步返回空退订函数：不抛错、不调 listener、不是 Promise；模块级单例', async () => {
    const m = await bridge();
    const inst = m.unavailableShell();
    expect(m.unavailableShell(), '模块级单例').toBe(inst);
    for (const name of NINE) {
      const p = inst[name]();
      expect(p instanceof Promise, `${name} 返回 Promise`).toBe(true);
      await expect(p).rejects.toMatchObject({ message: '没有连上外壳' });
    }
    const listener = vi.fn();
    let off: any = null;
    expect(() => {
      off = inst.on('service-state', listener);
    }, 'on 同步返回、不抛错').not.toThrow();
    expect(typeof off).toBe('function');
    expect(typeof (off as any).then, '不返回 Promise').toBe('undefined');
    expect(() => (off as any)(), '调用空退订不抛').not.toThrow();
    expect(listener).not.toHaveBeenCalled();
  });

  it('openExternal 被拒且 message 逐字是 cancelled 时当作正常结束；其它错误原样 reject（只留 message）', async () => {
    const m = await bridge();
    const fake = fakeShell({
      openExternal: vi.fn(() => Promise.reject(new Error('cancelled'))),
    });
    put(fake);
    const w = m.shellBridgeInstance();
    await expect(w.openExternal('https://example.com/'), 'cancelled 当正常结束').resolves.toBeUndefined();
    const fake2 = fakeShell({
      openExternal: vi.fn(() => Promise.reject(new Error('用户拒绝了'))),
    });
    put(fake2);
    const w2 = m.shellBridgeInstance();
    await expect(w2.openExternal('https://example.com/')).rejects.toMatchObject({ message: '用户拒绝了' });
  });

  it('on 的转发：listener 原样传给原对象；退订函数包一层，调用它即调用原对象返回的退订；原对象返回的不是函数时给空退订', async () => {
    const m = await bridge();
    const offSpy = vi.fn();
    const fake = fakeShell({ on: vi.fn((_e: unknown, _l: unknown) => offSpy) });
    put(fake);
    const w = m.shellBridgeInstance();
    const listener = () => {};
    const off = w.on('service-state', listener);
    expect((fake.on as any).mock.calls[0]).toEqual(['service-state', listener]);
    expect(typeof off).toBe('function');
    expect(offSpy).not.toHaveBeenCalled();
    (off as any)();
    expect(offSpy, '调用包装的退订会退订').toHaveBeenCalledTimes(1);
    const fake2 = fakeShell({ on: vi.fn(() => 123) });
    put(fake2);
    const w2 = m.shellBridgeInstance();
    const off2 = w2.on('service-state', listener);
    expect(typeof off2, '返回的不是函数时给空退订函数').toBe('function');
    expect(() => (off2 as any)(), '空退订不抛').not.toThrow();
  });
});
"""

PROBE_CONTEXT = PROBE_PRELUDE + r"""
const modeState = vi.hoisted(() => ({ real: false }));
const stubCalls = vi.hoisted(() => ({ count: 0 }));

vi.mock('../src/live/mode', async (importOriginal) => {
  const actual: any = await importOriginal();
  return { ...actual, liveModeIsReal: () => modeState.real, liveClient: () => null };
});
vi.mock('../src/shellpages/shellStub', async (importOriginal) => {
  const actual: any = await importOriginal();
  const orig = actual.createShellStub;
  return {
    ...actual,
    createShellStub: (scenario: string) => {
      stubCalls.count += 1;
      return orig(scenario);
    },
  };
});

const MEMBERS = ['getState', 'pickRepo', 'pickPython', 'pickKit', 'pickTranscriptDir', 'saveSettings', 'startService', 'restartService', 'openExternal', 'on'];
const MIN_STATE = {
  app: { version: '0.0.0', homepage: 'https://example.com/' },
  settings: { repos: [], currentRepo: null, transcriptDirs: [], theme: 'system', density: 'standard' },
  currentRepoCheck: null,
  python: { status: 'ok', source: 'auto', path: 'C:/Python313/python.exe', version: '3.13.1' },
  kit: { status: 'ok', source: 'repo', path: 'C:/kit', version: '2.12.0' },
  service: { kind: 'idle' },
};

function fakeShell(overrides?: Record<string, unknown>): any {
  const shell: Record<string, unknown> = {
    getState: vi.fn(() => Promise.resolve(JSON.parse(JSON.stringify(MIN_STATE)))),
    pickRepo: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickPython: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickKit: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickTranscriptDir: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    saveSettings: vi.fn(() => Promise.resolve(JSON.parse(JSON.stringify(MIN_STATE)))),
    startService: vi.fn(() => Promise.resolve(undefined)),
    restartService: vi.fn(() => Promise.resolve(undefined)),
    openExternal: vi.fn(() => Promise.resolve(undefined)),
    on: vi.fn(() => () => {}),
  };
  return Object.assign(shell, overrides ?? {});
}
function fullShell(): any {
  const shell = fakeShell();
  expect(MEMBERS.every((m) => typeof shell[m] === 'function'), '假外壳十成员齐全').toBe(true);
  return shell;
}
async function ctx(): Promise<any> {
  return await import('../src/shellpages/shellContext');
}
async function grabVia(context: any): Promise<any> {
  let got: any = null;
  function Grab() {
    got = context.useThemisShell('ready');
    return null;
  }
  const r = render(<Grab />);
  r.unmount();
  expect(got, 'useThemisShell 应返回实例').toBeTruthy();
  return got;
}

beforeEach(async () => {
  modeState.real = false;
  stubCalls.count = 0;
  window.location.hash = '';
  await drainNav();
});
afterEach(async () => {
  cleanup();
  delete (window as any).themisShell;
  modeState.real = false;
  stubCalls.count = 0;
  try {
    const sc: any = await import('../src/shellpages/shellContext');
    sc.resetShellStubs();
  } catch (e) {
    // 模块不在时，用例本身已经失败
  }
  try {
    const sb: any = await import('../src/shellpages/shellBridge');
    sb.resetShellBridge();
  } catch (e) {
    // 同上
  }
  vi.useRealTimers();
  window.location.hash = '';
  await drainNav();
});

describe('D04 取实例的顺序', () => {
  it('假外壳优先于桩：window 上放十成员齐全的假 themisShell，经 App 打开首启页与服务状态页、单独渲染 SettingsPage，都调到假对象，createShellStub 一次都没被调', async () => {
    vi.useFakeTimers();
    const fake = fullShell();
    (window as any).themisShell = fake;
    let r = await mountApp('#/first-run?shell=crash');
    expect((fake.getState as any).mock.calls.length, '首启页调的是假对象').toBeGreaterThanOrEqual(1);
    expect(stubCalls.count, '真实例优先，不创建桩').toBe(0);
    expect(document.querySelector('.tt-fr__err[role="alert"]'), '假数据没有错误块').toBeNull();
    r.unmount();
    r = await mountApp('#/service-status?shell=exit-1');
    expect((fake.getState as any).mock.calls.length, '服务状态页也调假对象').toBeGreaterThanOrEqual(2);
    expect(stubCalls.count).toBe(0);
    r.unmount();
    const page: any = await import('../src/pages/SettingsPage');
    const r3 = render(<page.default />);
    await settle();
    expect((fake.getState as any).mock.calls.length, '设置页也调假对象').toBeGreaterThanOrEqual(3);
    expect(stubCalls.count).toBe(0);
    r3.unmount();
  });

  it('成员不全当作没有：缺 on、或 saveSettings 不是函数，都回到夹具桩（createShellStub 被调用），页面显示桩的内容', async () => {
    vi.useFakeTimers();
    const bad1 = fullShell();
    delete bad1.on;
    (window as any).themisShell = bad1;
    let r = await mountApp('#/first-run?shell=exit-2');
    expect(stubCalls.count, '缺成员回到桩').toBeGreaterThanOrEqual(1);
    expect(textOf(document.querySelector('h1'))).toContain('欢迎使用 Themis Tally');
    r.unmount();
    const bad2 = fullShell();
    bad2.saveSettings = 'not-a-function';
    (window as any).themisShell = bad2;
    stubCalls.count = 0;
    r = await mountApp('#/service-status?shell=crash');
    expect(stubCalls.count, '非函数成员也回到桩').toBeGreaterThanOrEqual(1);
    expect(textOf(document.querySelector('[data-exit-code]'))).toBe('3');
    r.unmount();
  });

  it('Provider 注入最优先：window 上有假对象时，注入的实例照样赢', async () => {
    const fake = fullShell();
    (window as any).themisShell = fake;
    const context = await ctx();
    const injected = fullShell();
    let got: any = null;
    function Grab() {
      got = context.useThemisShell('ready');
      return null;
    }
    render(<context.ThemisShellProvider shell={injected}><Grab /></context.ThemisShellProvider>);
    expect(got).toBe(injected);
    expect(stubCalls.count, 'Provider 注入时不创建桩').toBe(0);
  });

  it('真实模式下没有外壳：不创建桩（createShellStub 0 次）、地址里的 shell= 不起作用，首启页与服务状态页显示「没有连上外壳」，设置页照旧走通用出错块', async () => {
    vi.useFakeTimers();
    modeState.real = true;
    delete (window as any).themisShell;
    let r = await mountApp('#/first-run?shell=crash');
    expect(stubCalls.count, '真实模式不创建桩').toBe(0);
    const err = document.querySelector('.tt-fr__err[role="alert"]');
    expect(err, '首启页显示错误块').not.toBeNull();
    expect(textOf(err)).toBe('没有连上外壳');
    expect(document.querySelector('[data-step]'), '桩的步骤列表不渲染').toBeNull();
    r.unmount();
    r = await mountApp('#/service-status?shell=exit-1');
    expect(stubCalls.count).toBe(0);
    expect(textOf(document.querySelector('.tt-ss__note')), '说明行位置显示错误').toContain('没有连上外壳');
    expect(textOf(document.querySelector('[data-exit-code]')), 'shell= 不起作用，不是 exit-1 场景').toBe('—');
    r.unmount();
    const page: any = await import('../src/pages/SettingsPage');
    const r3 = render(<page.default />);
    await settle();
    expect(stubCalls.count).toBe(0);
    const body = (document.body.textContent || '').replace(/\s+/g, ' ');
    expect(body, '设置页照旧走 PageFrame 通用出错块（合同 v2：设置页不在本片断言面内）').toContain('没有收到服务的回应');
    expect(body, '设置页不显示「没有连上外壳」').not.toContain('没有连上外壳');
    r3.unmount();
  });

  it('引用稳定：同一个假对象两次取到同一引用，换对象换引用；真实模式下「外壳不可用」两次取到也是同一引用', async () => {
    const context = await ctx();
    const fake = fullShell();
    (window as any).themisShell = fake;
    const a = await grabVia(context);
    const b = await grabVia(context);
    expect(a, '同一对象同一包装引用').toBe(b);
    const other = fullShell();
    (window as any).themisShell = other;
    const c = await grabVia(context);
    expect(c, '不同对象不同包装').not.toBe(a);
    modeState.real = true;
    delete (window as any).themisShell;
    const u1 = await grabVia(context);
    const u2 = await grabVia(context);
    expect(u1, '外壳不可用是模块级单例').toBe(u2);
    expect(u1).not.toBe(a);
  });
});
"""

PROBE_VIEWS = PROBE_PRELUDE + r"""
function failingShell(message: string, state?: unknown, offOverride?: () => void): any {
  const reject = () => Promise.reject(new Error(message));
  return {
    getState: vi.fn(() => (state === undefined ? reject() : Promise.resolve(state))),
    pickRepo: vi.fn(reject),
    pickPython: vi.fn(reject),
    pickKit: vi.fn(reject),
    pickTranscriptDir: vi.fn(reject),
    saveSettings: vi.fn(reject),
    startService: vi.fn(reject),
    restartService: vi.fn(reject),
    openExternal: vi.fn(reject),
    on: vi.fn(() => offOverride ?? (() => {})),
  };
}
const noop = () => {};
beforeEach(async () => {
  window.location.hash = '';
  await drainNav();
});
afterEach(async () => {
  cleanup();
  try {
    const sc: any = await import('../src/shellpages/shellContext');
    sc.resetShellStubs();
  } catch (e) {
    // 模块不在时，用例本身已经失败
  }
  vi.useRealTimers();
  window.location.hash = '';
  await drainNav();
});

describe('D07 首次启动页的出错状态', () => {
  it('getState 被拒：步骤列表为空，错误块在步骤列表之后、底栏之前，role=alert、不带 data-step-error，文字是错误消息', async () => {
    const { FirstRunView } = await import('../src/shellpages/FirstRunView');
    const shell = failingShell('读取失败');
    render(<FirstRunView shell={shell} navigate={noop} />);
    await settle();
    expect(document.querySelectorAll('[data-step]').length, 'state 为 null，步骤列表为空').toBe(0);
    const alerts = document.querySelectorAll('.tt-fr__err[role="alert"]');
    expect(alerts.length).toBe(1);
    const err = alerts[0];
    expect(err.getAttribute('data-step-error'), '错误块不加 data-step-error').toBeNull();
    expect(textOf(err)).toBe('读取失败');
    const steps = document.querySelector('ol.tt-fr__steps');
    const foot = document.querySelector('.tt-fr__foot');
    expect(steps).not.toBeNull();
    expect(foot).not.toBeNull();
    expect(!!(steps!.compareDocumentPosition(err) & Node.DOCUMENT_POSITION_FOLLOWING), '错误块在步骤列表之后').toBe(true);
    expect(!!(err.compareDocumentPosition(foot!) & Node.DOCUMENT_POSITION_FOLLOWING), '错误块在底栏之前').toBe(true);
    expect(document.querySelectorAll('[role="status"]').length, '不加 role=status').toBe(0);
  });

  it('外壳不可用时错误块逐字显示「没有连上外壳」；空 message 用「操作失败」兜底', async () => {
    const { FirstRunView } = await import('../src/shellpages/FirstRunView');
    const r1 = render(<FirstRunView shell={failingShell('没有连上外壳')} navigate={noop} />);
    await settle();
    expect(textOf(document.querySelector('.tt-fr__err[role="alert"]'))).toBe('没有连上外壳');
    r1.unmount();
    const r2 = render(<FirstRunView shell={failingShell('')} navigate={noop} />);
    await settle();
    expect(textOf(document.querySelector('.tt-fr__err[role="alert"]'))).toBe('操作失败');
    r2.unmount();
  });

  it('所有外壳调用都接住拒绝：自动启动失败与「更换…」选择失败都显示在同一个错误块位置，不崩', async () => {
    const stubMod: any = await import('../src/shellpages/shellStub');
    const stub = stubMod.createShellStub('ready');
    const readyState = await stub.getState();
    const { FirstRunView } = await import('../src/shellpages/FirstRunView');
    const shell = failingShell('启动失败', readyState);
    const r = render(<FirstRunView shell={shell} navigate={noop} />);
    await settle();
    expect((shell.startService as any).mock.calls.length, '自动启动被触发').toBeGreaterThanOrEqual(1);
    let err = document.querySelector('.tt-fr__err[role="alert"]');
    expect(err, '自动启动失败也显示错误块').not.toBeNull();
    expect(textOf(err)).toBe('启动失败');
    fireEvent.click(btn(document, '更换…'));
    await settle();
    expect((shell.pickRepo as any).mock.calls.length).toBeGreaterThanOrEqual(1);
    err = document.querySelector('.tt-fr__err[role="alert"]');
    expect(err, '选择失败也显示错误块').not.toBeNull();
    expect(textOf(err)).toBe('启动失败');
    r.unmount();
    stub.dispose();
  });
});

describe('D07 服务状态页的出错状态', () => {
  it('getState 被拒：错误消息显示在说明行位置（tt-ss__note），不加 role=alert、不加 role=status；空 message 用「操作失败」', async () => {
    const { ServiceStatusView } = await import('../src/shellpages/ServiceStatusView');
    const r1 = render(<ServiceStatusView shell={failingShell('状态读不到')} navigate={noop} />);
    await settle();
    expect(textOf(document.querySelector('.tt-ss__note'))).toContain('状态读不到');
    expect(document.querySelector('[role="alert"]'), '不加 role=alert').toBeNull();
    expect(document.querySelector('[role="status"]'), '不加 role=status').toBeNull();
    expect(document.querySelector('[data-exit-code]'), '退出码行还在').not.toBeNull();
    r1.unmount();
    const r2 = render(<ServiceStatusView shell={failingShell('')} navigate={noop} />);
    await settle();
    expect(textOf(document.querySelector('.tt-ss__note'))).toBe('操作失败');
    r2.unmount();
  });

  it('restartService 被拒时复位「正在重启…」：按钮不再 loading、可以再点，错误消息显示在说明行位置', async () => {
    const stubMod: any = await import('../src/shellpages/shellStub');
    const stub = stubMod.createShellStub('crash');
    const crashed = await stub.getState();
    const { ServiceStatusView } = await import('../src/shellpages/ServiceStatusView');
    const shell = failingShell('重启失败', crashed);
    const r = render(<ServiceStatusView shell={shell} navigate={noop} />);
    await settle();
    fireEvent.click(btn(document, '重启服务'));
    await settle();
    expect((shell.restartService as any).mock.calls.length).toBeGreaterThanOrEqual(1);
    expect((document.body.textContent || ''), '复位「正在重启…」').not.toContain('正在重启…');
    const restartBtn = btn(document, '重启服务');
    expect(restartBtn.disabled, '复位后按钮可再点').toBe(false);
    expect(textOf(document.querySelector('.tt-ss__note'))).toContain('重启失败');
    r.unmount();
    stub.dispose();
  });
});

describe('D06 设置页的出错状态（断言现状：合同 v2 本片不改设置页）', () => {
  it('getState 被拒照旧冒给 PageFrame：页面处于 error 态，显示通用出错块「没有收到服务的回应」，不做信封、不显示「没有连上外壳」', async () => {
    const ctx: any = await import('../src/shellpages/shellContext');
    const page: any = await import('../src/pages/SettingsPage');
    const r = render(
      <ctx.ThemisShellProvider shell={failingShell('没有连上外壳')}>
        <page.default />
      </ctx.ThemisShellProvider>,
    );
    await settle();
    const body = (document.body.textContent || '').replace(/\s+/g, ' ');
    expect(body, 'PageFrame 通用出错块').toContain('没有收到服务的回应');
    expect(document.querySelector('[data-page-state]')?.getAttribute('data-page-state'), '页面处于 error 态').toBe('error');
    expect(body, '不做 ok:false 信封（无命令与退出码文字）').not.toContain('返回退出码');
    expect(body, '不让设置页显示「没有连上外壳」（合同 Non-goals 的已知不足）').not.toContain('没有连上外壳');
    expect(body, '不做设置页侧的「操作失败」兜底').not.toContain('操作失败');
    r.unmount();
  });
});

describe('D08 卸载时退订', () => {
  it('首启页与服务状态页卸载时，假 on 返回的退订函数各被调用一次', async () => {
    const { FirstRunView } = await import('../src/shellpages/FirstRunView');
    const { ServiceStatusView } = await import('../src/shellpages/ServiceStatusView');
    const off1 = vi.fn();
    const r1 = render(<FirstRunView shell={failingShell('x', undefined, off1)} navigate={noop} />);
    await settle();
    r1.unmount();
    expect(off1, '首启页卸载退订一次').toHaveBeenCalledTimes(1);
    const off2 = vi.fn();
    const r2 = render(<ServiceStatusView shell={failingShell('x', undefined, off2)} navigate={noop} />);
    await settle();
    r2.unmount();
    expect(off2, '服务状态页卸载退订一次').toHaveBeenCalledTimes(1);
  });
});
"""

PROBE_SPECS = {
    "bridge": (PROBE_BRIDGE, (BRIDGE_REL,)),
    "context": (PROBE_CONTEXT, (BRIDGE_REL, CONTEXT_REL, f"{SRC_REL}/live/mode.ts")),
    "views": (PROBE_VIEWS, (FIRST_RUN_REL, SERVICE_VIEW_REL, SETTINGS_PAGE_REL)),
}
PROBE_ORDER = ("bridge", "context", "views")


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针
# ---------------------------------------------------------------------------

PIPELINE_BUDGET = 1800
STEP_CAPS = {
    "npm ci": 300,
    "npm test": 300,
    "npm run build": 240,
    "check-live-build": 480,
    "check:contract": 180,
    "probe": 120,
}
WATCHED = ("package.json", "package-lock.json")


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


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not (REPO_ROOT / BRIDGE_REL).is_file():
        pipe.reason = (f"候选里还没有 {BRIDGE_REL}（基线），没有东西可测，未调用 npm；"
                       "候选写出 shellBridge.ts 后，流水线才会运行 npm ci、Vitest、构建、三取值检查、契约检查与探针")
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
            if (REPO_ROOT / f"{WEB_REL}/scripts/check-live-build.mjs").is_file():
                run_step("check-live-build", [node, "scripts/check-live-build.mjs"])
            else:
                pipe.stopped_reason = "scripts/check-live-build.mjs 不存在，三取值构建检查未运行"
            run_step("check:contract", [npm, "run", "check:contract"])
            uid = uuid.uuid4().hex[:12]
            for key in PROBE_ORDER:
                missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                name = f"probe-{uid}-t032-{key}.test.tsx"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                written.append(path)
                path.write_text(PROBE_SPECS[key][0], encoding="utf-8", newline="\n")
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
        f"\n--- 输出尾部 ---\n{step.tail}")
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
    """P1 / V01–V04、D09、D11、D12、D13：npm ci、npm test（全绿，现有 shellpages-*.test.* 与执行端新测试
    一起全过）、npm run build（tsc --noEmit + vite build）、node scripts/check-live-build.mjs（三种 NODE_ENV
    取值、LIVE_BUILD_OK 3/3）、npm run check:contract（契约检查：通过）都退出 0；依赖文件一个字节没动。"""
    for name in ("npm ci", "npm test", "npm run build", "check-live-build", "check:contract"):
        step = assert_step_ok(pipeline, name)
        if name == "npm test":
            m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
            assert m, f"npm test 输出里没有通过计数：\n{step.tail}"
            assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), \
                f"npm test 有失败或跳过：\n{step.tail}"
        if name == "check-live-build":
            assert "LIVE_BUILD_OK 3/3" in step.out, f"三取值构建检查应打印 LIVE_BUILD_OK 3/3：\n{step.tail}"
        if name == "check:contract":
            assert "契约检查：通过" in step.out, f"契约检查应通过：\n{step.tail}"
    assert pipeline.digests_before == pipeline.digests_after, \
        "npm 流水线不许改动 desktop/web/package.json 与 package-lock.json"
    assert not pipeline.gate_probe_left, "gate-probe/ 目录在探针后应清掉"


def test_transitional_p2_probe_bridge(pipeline):
    """过渡 / D02、D03、D05：bridge 探针全绿。真实外壳约定（preload 拆信封、cancelled 文案）被 T030 或
    后续片改变时，按名字退役或改本条。"""
    assert_probe_ok(pipeline, "bridge")


def test_transitional_p3_probe_context(pipeline):
    """过渡 / D04：context 探针全绿。真实模式判定、桩场景取值被后续片（SSE 片、作业/检索片）合法改变时，
    按名字退役或改本条。"""
    assert_probe_ok(pipeline, "context")


def test_transitional_p4_probe_views(pipeline):
    """过渡 / D06、D07、D08：views 探针全绿。两个视图与设置页的出错文案、PageFrame 的出错块写法被
    后续片（连接状态片 T029）改变时，按名字退役或改本条。"""
    assert_probe_ok(pipeline, "views")


def test_gate_selfcheck_probes_wellformed():
    """门禁自检：PROBE_ORDER 与 PROBE_SPECS 对得上；探针里不写 skip、only、todo；括号配对。"""
    assert set(PROBE_ORDER) == set(PROBE_SPECS) and len(PROBE_ORDER) == 3
    for key in PROBE_ORDER:
        source = PROBE_SPECS[key][0]
        assert probe_count(source) >= 3, f"探针 {key} 的 it() 数应不少于 3"
        assert not re.search(r"\.(skip|only|todo)\s*\(", source), f"探针 {key} 不许用 skip/only/todo"
        for a, b in ("{", "}"), ("(", ")"), ("[", "]"):
            assert source.count(a) >= source.count(b) and source.count(a) - source.count(b) <= 4, \
                f"探针 {key} 的 {a}{b} 括号不配对（{source.count(a)} vs {source.count(b)}）"
