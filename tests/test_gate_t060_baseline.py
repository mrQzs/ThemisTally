"""T060 战前门禁：宿主接口第六个函数 ``openSettings()``——服务窗口的「设置」页签经它打开唯一一个设置外壳窗口
（合同 t060-desktop-shell-open-settings.v1，基线 492c643——宿主接口只有五个函数、没有设置窗口）。

被测对象：

- 宿主接口四处接线：``desktop/shell/preload.js``（暴露面恰好六个函数，``openSettings`` 无参转交
  ``themis-host:open-settings``）、``src/ipc.js``（三张表各加第六项，arity 0，多余实参丢掉）、
  ``src/hostrelay.js``（``HOST_METHODS`` 六项，openSettings 在末尾）、``src/host.js``（``createHost``
  新增可选注入项 ``createSettingsWindow`` 与 ``openSettings`` 编排：不可用回 ``unavailable``、
  占位在第一个 await 之前、已开 restore+focus、closed 清占位、加载失败关窗回 ``load-failed``）。
- ``src/shellprotocol.js`` 的 ``SHELL_SETTINGS_URL = "themis-shell://app/index.html#/settings"``。
- ``main.js``：建窗 helper 拆两层（``createShellPageWindow`` 与 ``openShellWindow``）；设置窗口只此一个
  （标题「设置」、拦 ``page-title-updated`` 并 ``preventDefault``、不设 parent、关掉清占位并把焦点还给
  服务窗口、不兑现 ``userClosedShell``）；外壳分支注入建窗函数而带参数分支不注入；外壳 IPC 的来源检查
  与对话框父窗口都认还活着的设置窗口；用户关服务窗口先关设置窗口，意外退出的三条分支都关设置窗口。
- 前端：新文件 ``desktop/web/src/live/hostSettings.ts``（``hostOpenSettings``，themisHost 的读取点）、
  ``SettingsPage.tsx`` 的新分支（挂载调一次、[打开设置] 再调一次、不调 ``getState``、失败 ``role="alert"``
  带 reason、没有「没有收到服务的回应」），没有宿主接口时旧分支照旧；执行端新测试
  ``desktop/web/tests/host-settings-open.test.tsx`` 在位。
- ``desktop/shell/README.md``：宿主接口表加 ``openSettings()`` 行，第 5 行不再把它列进「仍没有」。

基线（492c643）上这些记号与行为都不存在，所以失败落在「文件不存在」「记号不在」「探针子进程退出码非 0」
这类断言上，不是收集失败：模块级只导入标准库，仓库文件的读取与探针的运行都发生在用例函数里。外壳探针是
自包含的 ``node --test`` 文件（Node 24 自带，不需要 npm ci，不 require electron），Python 把探针源码写进
系统临时目录、以仓库根为 cwd 运行、用完即删；preload 的探针用 ``vm.runInNewContext`` 真跑一遍源码，注入假
require（模块名字面量写成 ``"electron"``，测试文件里不出现 ``require('electron')`` 这个字面串——T025 门禁
S03 扫 ``tests/**``）。前端流水线（npm 依赖、Vitest、探针）放在 ``pipeline`` 会话级夹具里：全量 pytest 默认
跳过用到它的用例（点名运行本文件才跑）；候选里还没有本片的标记时夹具不调 npm（照 T057 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线）：接口接线记号（S01）；SHELL_SETTINGS_URL 常量（S02）；main.js 的
  两个建窗函数与「不许 parent / 不兑现 userClosedShell」（S03）；注入与来源检查（S04）；生命周期——
  先关设置窗口再停服务、意外退出三条分支都关设置窗口、零窗口（S05）；前端三份文件（S06）；README（S07）。
- 外壳探针断言（``test_p01`` / ``test_p02``，跑 node --test，不需要依赖）：
  - P01 / D02、D06：host.openSettings——暴露面六个函数、没注入回 unavailable、首次建窗并加载设置地址、
    已开 restore+focus 不开第二个、并发只建一个、关掉再开且旧窗迟到的 closed 不误伤、加载失败关窗。
  - P02 / D01：SHELL_SETTINGS_URL 与 isShellPageUrl；HOST_CHANNELS 恰好六条冻结；ipc 的转交与丢参；
    hostrelay 六项与 forbidden 兜底；preload 真跑（键恰好六个、openSettings 无参转交、无 on/send）。
- 流水线断言（``test_q*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、npm test
  全绿（含执行端新测试与冻结的 shellpages-settings）；一份 Vitest 探针逐条核对 SettingsPage 的新分支
  （挂载一次、按钮再调一次、不调 getState、失败 alert 带 reason、无宿主接口照旧渲染旧设置页）。

门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：

- main.js 的区域断言用配平扫描（跳过字符串与注释）取函数体/调用实参文本，不按行号——执行端重排空行不改语义。
- main.js 的形状扫描（parent、userClosedShell、createHost 计数）先过 ``_strip_js_comments``（保长、字符串照抄）
  再按形状匹配：注释里提一句「不兑现 userClosedShell」「不设 options.parent」不算违规（审核 B2）；只有
  ``parent:`` 选项、``options.parent`` 引用、``userClosedShell(`` 调用、剥注释后的 ``createHost(`` 调用计数。
- 「三条分支都关设置窗口」按 ``settingsWin.close()`` 在订阅回调里的出现次数与相对位置断言（≥3 处，且每处
  ``relay.clear()`` 之后、关服务窗口之前各有一处、兜底分支在 ``app.exit(1)`` 之前），不钉整段逐字。
- Vitest 探针的 [打开设置] 按钮按「以『打开设置』开头」找（审核 B3）：执行端照仓库习惯写「打开设置…」也认；
  探针代码只在这份门禁里（VITEST_PROBE_HOST），热修补时改它即可。
- README 只钉本片新增的记号与「不许再把 openSettings 列进仍没有」，既有 needle 由 T026/T035/T039 的门禁照旧管。
- 执行端新测试只钉「在位 + 不用 skip/only/todo + 含 themisHost 与 打开设置」，覆盖点由 V02 与复审管。
"""

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL = REPO_ROOT / "desktop" / "shell"
WEB = REPO_ROOT / "desktop" / "web"

HOSTSETTINGS_REL = "desktop/web/src/live/hostSettings.ts"
PAGE_REL = "desktop/web/src/pages/SettingsPage.tsx"
EXEC_TEST_REL = "desktop/web/tests/host-settings-open.test.tsx"

HOST_CHANNELS = (
    "themis-host:reauth",
    "themis-host:open-secret-window",
    "themis-host:open-external",
    "themis-host:reveal",
    "themis-host:notify",
    "themis-host:open-settings",
)
HOST_METHODS = ("reauth", "openSecretWindow", "openExternal", "reveal", "notify", "openSettings")
SETTINGS_URL = "themis-shell://app/index.html#/settings"
OLD_PAGE_DESC = "设置保存在桌面应用自己的用户数据目录里，不写进仓库的配置"

REQUIRE_ELECTRON_RE = re.compile(r"require\(\s*['\"]electron['\"]\s*\)")


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


def _shell_read(rel: str) -> str:
    p = SHELL / rel
    assert p.is_file(), f"desktop/shell/{rel} 不存在"
    return _norm(p.read_text(encoding="utf-8"))


def file_digest(path):
    path = Path(path)
    if not path.is_file():
        return None
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return len(data), hashlib.sha256(data).hexdigest()


def tail_text(text, max_chars=3500, max_lines=45):
    text = _ANSI.sub("", text)
    lines = text.splitlines()[-max_lines:]
    joined = "\n".join(lines)
    return joined[-max_chars:]


# ---------------------------------------------------------------------------
# JS 源码的区域提取：配平扫描（跳过字符串与注释），不按行号
# ---------------------------------------------------------------------------

def _match_bracket(text: str, open_at: int) -> int:
    """open_at 处是 '(' 或 '{'：返回与之配平的闭括号下标；配不上回 -1。跳过 // 与 /* */ 注释和字符串。"""
    opener = text[open_at]
    closer = {"(": ")", "{": "}"}[opener]
    depth = 0
    i = open_at
    n = len(text)
    while i < n:
        c = text[i]
        if c == "/" and text[i + 1:i + 2] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if c == "/" and text[i + 1:i + 2] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "'\"`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _call_span(text: str, token: str):
    """token 形如 "createHost("：返回那次调用（含括号）的文本；找不到回 None。"""
    at = text.find(token)
    if at < 0:
        return None
    open_at = text.find("(", at)
    end = _match_bracket(text, open_at)
    return None if end < 0 else text[at:end + 1]


def _call_spans(text: str, token: str):
    """同名调用的全部文本，按出现顺序。"""
    spans = []
    start = 0
    while True:
        at = text.find(token, start)
        if at < 0:
            return spans
        open_at = text.find("(", at)
        end = _match_bracket(text, open_at)
        if end < 0:
            return spans
        spans.append(text[at:end + 1])
        start = end + 1


def _block_span(text: str, token: str):
    """token 形如 "function createSettingsWindow("：返回那个函数（含函数体）的文本；找不到回 None。"""
    at = text.find(token)
    if at < 0:
        return None
    open_at = text.find("{", at)
    end = _match_bracket(text, open_at)
    return None if end < 0 else text[at:end + 1]


def _strip_js_comments(text: str) -> str:
    """删掉 // 与 /* */ 注释，字符串照抄；每个被删字符换成空格，长度不变（下标仍可用）。
    形状扫描（parent、userClosedShell、createHost 的计数）先过这一遍：合同 v2 第 6 步的正文正引导
    执行端写「这里不兑现 userClosedShell」「不设 options.parent」这两句注释，只按词匹配会把
    行为正确的实现判红（审核 B2）。"""
    out = list(text)
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "/" and text[i + 1:i + 2] == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        if c == "/" and text[i + 1:i + 2] == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
            continue
        if c in "'\"`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# 外壳探针：node --test（Node 24 自带，不需要 npm ci）
# ---------------------------------------------------------------------------

def _run_probe(name: str, source: str, timeout: float = 300.0) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    assert node, "本机没有 node，无法运行门禁探针"
    with tempfile.TemporaryDirectory(prefix="t060-gate-") as td:
        probe = Path(td) / f"{name}.test.js"
        probe.write_text(source, encoding="utf-8")
        return subprocess.run(
            [node, "--test", str(probe)],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )


def _expect_probe_pass(name: str, template: str) -> None:
    source = template.replace("@SHELL@", json.dumps(str(SHELL))[1:-1])
    proc = _run_probe(name, source)
    assert proc.returncode == 0, (
        f"探针 {name} 没有全绿（退出码 {proc.returncode}）：\n"
        f"--- stdout 末尾 ---\n{proc.stdout[-6000:]}\n--- stderr 末尾 ---\n{proc.stderr[-2000:]}"
    )


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def _requires_beyond_electron(text: str) -> bool:
    """preload.js 自包含：不 require 相对路径或 node: 模块（照 T026 门禁 S03 的口径）。"""
    return bool(re.search(r"""require\(\s*['"](\.|node:)""", text))


def test_s01_host_interface_wiring():
    """S01 / D01：宿主接口四处接线的静态记号——preload 第六个函数、ipc 三张表、hostrelay 六项、host 的编排。"""
    preload = _shell_read("preload.js")
    assert "openSettings" in preload, "preload.js 要暴露 openSettings"
    assert '"themis-host:open-settings"' in preload, "preload.js 缺通道字面量 themis-host:open-settings"
    assert "九个函数" in preload, "preload.js 的注释要写「九个函数」（第六个扩成第九个）"
    assert not _requires_beyond_electron(preload), "preload.js 仍只许 require electron（T025 门禁 S03）"
    ipc = _shell_read("src/ipc.js")
    assert '"themis-host:open-settings"' in ipc, "src/ipc.js 的 HOST_CHANNELS 要加新通道"
    assert '"themis-host:open-settings": "openSettings"' in ipc, "HOST_METHOD 要把新通道映到 openSettings"
    assert '"themis-host:open-settings": 0' in ipc, "HOST_ARITY 里新通道的实参个数要是 0"
    relay = _shell_read("src/hostrelay.js")
    assert '"openSettings"' in relay, "src/hostrelay.js 的 HOST_METHODS 要加 openSettings"
    host = _shell_read("src/host.js")
    assert "openSettings" in host, "src/host.js 要有 openSettings 编排"
    assert "createSettingsWindow" in host, "src/host.js 的 createHost 要有可选注入项 createSettingsWindow"
    assert "SHELL_SETTINGS_URL" in host, "src/host.js 要用 SHELL_SETTINGS_URL 加载设置页"



def test_s02_shell_settings_url():
    """S02 / D02：SHELL_SETTINGS_URL 常量逐字在位、加在 SHELL_STATUS_URL 之后并进导出。"""
    text = _shell_read("src/shellprotocol.js")
    line = f'const SHELL_SETTINGS_URL = "{SETTINGS_URL}";'
    assert line in text, "src/shellprotocol.js 缺常量行（合同第 2 步逐字）"
    assert text.index("SHELL_STATUS_URL") < text.index("SHELL_SETTINGS_URL"), \
        "SHELL_SETTINGS_URL 要加在 SHELL_STATUS_URL 之后"
    exports = _block_span(text, "module.exports = {")
    assert exports, "src/shellprotocol.js 缺 module.exports"
    assert "SHELL_SETTINGS_URL" in exports, "module.exports 里要有 SHELL_SETTINGS_URL"
    assert exports.index("SHELL_STATUS_URL") < exports.index("SHELL_SETTINGS_URL"), \
        "导出里 SHELL_SETTINGS_URL 也要在 SHELL_STATUS_URL 之后"


def test_s03_main_window_factories():
    """S03 / D02、D03：建窗 helper 拆两层；设置窗口只此一个、标题「设置」、拦 page-title-updated、不设 parent。
    先剥注释再扫形状（审核 B2）：注释里提一句 userClosedShell / options.parent 不算违规，
    只有 parent: 选项、options.parent 引用、userClosedShell( 调用才算。"""
    text = _shell_read("main.js")
    code = _strip_js_comments(text)
    assert code.count(".protocol.handle(") == 1, \
        "main.js 的 .protocol.handle( 仍必须恰好一处（两种窗口共用同一个底层 helper）"
    assert len(re.findall(r"new\s+BrowserWindow", code)) == 1, "new BrowserWindow 仍必须恰好一处"
    helper = _block_span(code, "function createShellPageWindow(")
    assert helper, "main.js 缺 createShellPageWindow（外壳页窗口的底层建窗 helper，合同第 5 步：必须在 runShellPage 内部）"
    for mark in ("partitionName(", "fromPartition", ".protocol.handle(", "guardedWindow",
                 "shell-preload.js", "isShellPageUrl"):
        assert mark in helper, f"createShellPageWindow 里缺「{mark}」"
    handle_at = helper.find(".protocol.handle(")
    assert "fromPartition" in helper[max(0, handle_at - 160):handle_at], \
        "协议 handler 必须挂在 session.fromPartition(...) 得到的 session 上（注册点前 160 字内）"
    assert "resolveShellAsset" in helper, "协议 handler 要用 resolveShellAsset 解析产物（root 局部变量，helper 只能在 runShellPage 内）"
    opened = _block_span(code, "async function openShellWindow(")
    assert opened, "main.js 缺 openShellWindow"
    assert "createShellPageWindow(" in opened, "openShellWindow 要改用底层 helper 建窗"
    assert "ThemisTally" in opened, "外壳页窗口的标题仍是 ThemisTally"
    assert "userClosedShell" in opened, "openShellWindow 对 userClosedShell 的兑现语义要保留"
    settings = _block_span(code, "function createSettingsWindow(")
    assert settings, "main.js 缺 createSettingsWindow（设置窗口的建窗函数，合同第 6 步）"
    assert 'createShellPageWindow("设置")' in settings, "设置窗口走同一个 helper，标题「设置」"
    assert "page-title-updated" in settings and "preventDefault" in settings, \
        "设置窗口要拦 page-title-updated 并 preventDefault（窗口标题保持「设置」，D03）"
    assert 'once("closed"' in settings, "设置窗口关掉时清自己的占位（once）"
    assert re.search(r"serviceWindow\s*\.\s*focus\s*\(", settings), "关掉设置窗口要把焦点还给服务窗口"
    assert not re.search(r"\bparent\s*:", settings), "设置窗口不许设 parent 选项（parent: 的形状）"
    assert not re.search(r"options\s*\.\s*parent\b", settings), "设置窗口不许设 options.parent"
    assert not re.search(r"\buserClosedShell\s*\(", settings), \
        "设置窗口不是外壳页窗口：关掉它不许兑现 userClosedShell（调用的形状）"
    assert "let settingsWin = null;" in code, "runShellPage 里要有设置窗口的占位变量 settingsWin"


def test_s04_main_injection_and_sources():
    """S04 / D04、D06：外壳分支注入建窗函数、带参数分支不注入；外壳 IPC 与对话框父窗口也认设置窗口。
    先剥注释再计数与取调用点（审核 B2：注释里的 createHost( 不算一处）。"""
    text = _shell_read("main.js")
    code = _strip_js_comments(text)
    calls = _call_spans(code, "createHost(")
    assert len(calls) == 2, f"main.js 的 createHost( 应仍恰好两次（现在是 {len(calls)} 次）"
    assert "createSettingsWindow" in calls[0], \
        "外壳分支（runShellPage 的 onRunning）要给 createHost 注入 createSettingsWindow"
    assert "createSettingsWindow" not in calls[1], \
        "带参数起服务的那条分支不许注入建窗函数（openSettings 只能回 unavailable，D06）"
    reg = _call_span(code, "registerShellIpc(")
    assert reg, "main.js 缺 registerShellIpc 调用"
    assert "shellSenderAllowed(event, shellWin.webContents)" in reg, \
        "第一段来源检查要逐字保留 shellSenderAllowed(event, shellWin.webContents)（T035 S04 的正则钉着它）"
    assert "isDestroyed" in reg, "来源检查要先看窗口是否还在（isDestroyed）"
    assert "shellSenderAllowed(event, settingsWin.webContents)" in reg, \
        "来源检查还要接受还活着的设置窗口（按同样的三条件判，D04）"
    api = _call_span(code, "createShellApi(")
    assert api, "main.js 缺 createShellApi 调用"
    assert "settingsWin" in api, "选择框与确认框的父窗口在设置窗口开着时要挂它（D04）"
    assert not re.search(r"settingsWin\s*\.\s*webContents\s*\.\s*send\s*\(\s*SERVICE_STATE_CHANNEL", code), \
        "服务状态事件照旧只发给外壳页窗口（shellWin），不发设置窗口（外观事件发设置窗口是允许的）"


def test_s05_main_lifecycle():
    """S05 / D05：用户关服务窗口先关设置窗口再停服务；意外退出的三条分支都关设置窗口；不出现零窗口。
    区域提取与定位都在剥过注释的文本上做（审核 B2 的口径：注释里的字样不参与计数）。"""
    text = _shell_read("main.js")
    code = _strip_js_comments(text)
    at = code.find("tracked.closed.then(async")
    assert at != -1, "main.js 缺服务窗口的 closed 收尾（tracked.closed.then(async …)）"
    open_at = code.find("(", code.find("then", at))
    end = _match_bracket(code, open_at)
    assert end > 0, "服务窗口 closed 收尾的括号配不平"
    handler = code[at:end + 1]
    m = re.search(r"settingsWin\s*\.\s*close\s*\(\s*\)", handler)
    stop = handler.find("flow.stop()")
    assert m and stop != -1 and m.start() < stop, \
        "用户关服务窗口要先关设置窗口，再 flow.stop()（服务窗口没了，设置窗口跟着关）"
    subs = []
    for mm in re.finditer(r"subscribe\s*\(", code):
        open_at = code.find("(", mm.start())
        end2 = _match_bracket(code, open_at)
        if end2 < 0:
            continue
        span = code[mm.start():end2 + 1]
        if "SERVICE_STATE_CHANNEL" in span:
            subs.append(span)
    assert len(subs) == 1, "发 SERVICE_STATE_CHANNEL 的订阅回调要恰好一个"
    sub = subs[0]
    closes = list(re.finditer(r"settingsWin\s*\.\s*close\s*\(\s*\)", sub))
    assert len(closes) >= 3, \
        f"意外退出的三条分支都要关设置窗口（订阅回调里现在是 {len(closes)} 处 settingsWin.close()）"
    for mclear in re.finditer(r"relay\s*\.\s*clear\s*\(\s*\)", sub):
        nxt = sub.find("serviceWindow", mclear.end())
        between = sub[mclear.end(): nxt if nxt != -1 else len(sub)]
        assert re.search(r"settingsWin\s*\.\s*close\s*\(\s*\)", between), \
            "relay.clear() 之后、关服务窗口之前要先关设置窗口（换页成功的分支：新窗口开好之后才关旧窗口）"
    err = sub.find("服务意外退出（退出码")
    exit1 = sub.find("app.exit(1)", err)
    assert err != -1 and exit1 != -1, "意外退出的兜底分支要照旧（ERROR 行 + app.exit(1)）"
    assert re.search(r"settingsWin\s*\.\s*close\s*\(\s*\)", sub[err:exit1]), \
        "兜底分支要在 app.exit(1) 之前把设置窗口关掉"
    assert "openShellWindow(SHELL_STATUS_URL)" in sub, "意外退出仍要开服务状态页（SHELL_STATUS_URL）"


def test_s06_frontend_files():
    """S06 / D07、D08、D11：hostSettings.ts 新文件、SettingsPage 的新分支与禁令、执行端新测试在位。"""
    need_file(HOSTSETTINGS_REL)
    hs = read_rel(HOSTSETTINGS_REL)
    assert "hostOpenSettings" in hs, "hostSettings.ts 要导出 hostOpenSettings"
    assert "themisHost" in hs, "hostSettings.ts 就是 themisHost 的读取点（SettingsPage.tsx 里不许出现它）"
    assert "openSettings" in hs
    assert re.search(r"typeof\s+\w+\s*!==\s*['\"]function['\"]", hs), \
        "openSettings 不是函数时 hostOpenSettings 要回 null"
    assert "declare global" not in hs, "不许 declare global（不改 transport.ts 的全局声明）"
    assert not re.search(r"window\s*\.\s*themisShell", hs), "hostSettings.ts 不许读 window.themisShell"
    assert not re.search(r"from\s+['\"][^'\"]*api['\"]", hs), "hostSettings.ts 不许 import api"
    page = read_rel(PAGE_REL)
    assert "hostOpenSettings" in page, "SettingsPage 要经 hostOpenSettings 判定与调用（不直接读 themisHost）"
    assert "themisHost" not in page, \
        "SettingsPage.tsx 里不许出现 themisHost 字样（T032 的静态断言点名这个文件：字符串与类型标注都算）"
    assert not re.search(r"window\s*\.\s*themisShell", page), "SettingsPage 不许读 window.themisShell"
    assert not re.search(r"from\s+['\"][^'\"]*api['\"]", page), "SettingsPage 不许 import api"
    assert "打开设置" in page, "新分支要有 [打开设置] 按钮"
    assert "host.openSettings" in page, "新分支 load 信封的 command 写 host.openSettings（不许带 themisHost 字样）"
    assert 'role="alert"' in page, "新分支失败时要有一行 role=\"alert\""
    assert OLD_PAGE_DESC in page, "PageFrame 的 description 那句要照旧保留"
    need_file(EXEC_TEST_REL)
    et = read_rel(EXEC_TEST_REL)
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\.fails\b"):
        if re.search(bad, et):
            problems.append(f"{EXEC_TEST_REL} 出现 {bad}（不许 skip、only、todo）")
    for mark in ("themisHost", "打开设置"):
        if mark not in et:
            problems.append(f"{EXEC_TEST_REL} 缺「{mark}」")
    assert not problems, "执行端新测试的形状：" + "; ".join(problems)


def test_s07_readme():
    """S07 / D12：README 的宿主接口表加 openSettings 行；「仍没有」那句删掉但「外壳页在本片就位」留着。"""
    text = _shell_read("README.md")
    assert "openSettings" in text, "README 要写 openSettings()"
    for needle in ("unavailable", "load-failed", SETTINGS_URL, "不重启服务", "密度"):
        assert needle in text, f"README 缺「{needle}」（宿主接口新行 / 设置窗口的行为与冒烟）"
    assert "外壳页在本片就位" in text, "「外壳页在本片就位」必须留着（T035/T039 的 needle）"
    for line in text.splitlines():
        if "openSettings" in line and "仍没有" in line:
            raise AssertionError(f"README 不许再把 openSettings 列进「仍没有」：{line.strip()}")


# ---------------------------------------------------------------------------
# P01 / P02：外壳探针（node --test，被测模块只在探针里 require）
# ---------------------------------------------------------------------------

PROBE_HOST = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const { createHost } = require("@SHELL@/src/host.js");

const SETTINGS_URL = "themis-shell://app/index.html#/settings";

function fakeWindow() {
  const win = new EventEmitter();
  win.minimized = false;
  win.focusCalls = 0;
  win.restoreCalls = 0;
  win.closeCalls = 0;
  win.destroyed = false;
  win.loadCalls = [];
  win.failLoad = false;
  win.hangLoad = false;
  win.isDestroyed = () => win.destroyed;
  win.isMinimized = () => win.minimized;
  win.restore = () => { win.restoreCalls += 1; };
  win.focus = () => { win.focusCalls += 1; };
  win.close = () => {
    win.closeCalls += 1;
    setImmediate(() => { win.destroyed = true; win.emit("closed"); });
  };
  win.loadURL = (u) => {
    win.loadCalls.push(u);
    if (win.failLoad) return Promise.reject(new Error("加载失败 " + u));
    if (win.hangLoad) return new Promise(() => {});
    return Promise.resolve();
  };
  return win;
}

let wins = [];
const mode = { failLoad: false, hangLoad: false };
function createSettingsWindow() {
  const w = fakeWindow();
  w.failLoad = mode.failLoad;
  w.hangLoad = mode.hangLoad;
  wins.push(w);
  return w;
}

function makeHost(over) {
  return createHost(Object.assign({
    origin: "http://127.0.0.1:1",
    control: "ctrl-tok-9f31c2abc",
    repo: "/tmp/repo",
    loadMain: async () => {},
    createSecretWindow: () => fakeWindow(),
    confirmExternal: async () => true,
    openExternal: async () => {},
    showItem: () => {},
    showNotification: () => {},
    now: () => 0,
    controlTimeoutMs: 1000,
  }, over || {}));
}
function reset() {
  wins.length = 0;
  mode.failLoad = false;
  mode.hangLoad = false;
}

const tick = () => new Promise((r) => setImmediate(r));


test("暴露面：七个函数，saveTheme 排在最后，前六个照旧", () => {
  const host = makeHost({ createSettingsWindow });
  assert.deepEqual(
    Object.keys(host),
    ["reauth", "openSecretWindow", "openExternal", "reveal", "notify", "openSettings", "saveTheme"],
  );
  for (const name of Object.keys(host)) {
    assert.equal(typeof host[name], "function", name + " 必须是函数");
  }
});

test("没注入建窗函数：openSettings 回 unavailable，不抛错", async () => {
  const host = makeHost(); // 不带 createSettingsWindow（带参数起服务的那条分支就是这样）
  assert.deepEqual(await host.openSettings(), { ok: false, reason: "unavailable" });
  assert.deepEqual(await host.openSettings("EXTRA"), { ok: false, reason: "unavailable" });
});

test("首次调用：建一个窗、加载 themis-shell://app/index.html#/settings、回 {ok:true}", async () => {
  reset();
  const host = makeHost({ createSettingsWindow });
  const r = await host.openSettings();
  assert.deepEqual(r, { ok: true });
  assert.equal(wins.length, 1, "只建一个窗口");
  assert.deepEqual(wins[0].loadCalls, [SETTINGS_URL]);
  assert.ok(!JSON.stringify(r).includes("ctrl-tok-9f31c2abc"), "返回值里不许有控制令牌");
});

test("已开着：最小化先 restore 再 focus，仍回 {ok:true}，不开第二个窗；没最小化不 restore", async () => {
  reset();
  const host = makeHost({ createSettingsWindow });
  await host.openSettings();
  wins[0].minimized = true;
  assert.deepEqual(await host.openSettings(), { ok: true });
  assert.equal(wins.length, 1);
  assert.equal(wins[0].restoreCalls, 1, "最小化时要先 restore");
  assert.equal(wins[0].focusCalls, 1);
  wins[0].minimized = false;
  assert.deepEqual(await host.openSettings(), { ok: true });
  assert.equal(wins[0].restoreCalls, 1, "没最小化就不该 restore");
  assert.equal(wins[0].focusCalls, 2);
  assert.equal(wins.length, 1, "已开着就聚焦，不另开第二个窗口");
});

test("并发两次只建一个窗（占位在第一个 await 之前同步记下）", async () => {
  reset();
  mode.hangLoad = true;
  const host = makeHost({ createSettingsWindow });
  const pending = host.openSettings(); // loadURL 永远挂起，不 await
  const second = await host.openSettings();
  assert.deepEqual(second, { ok: true }, "第二个调用看到占位就 restore+focus 后回 ok");
  assert.equal(wins.length, 1, "不许开出第二个窗口");
  assert.equal(wins[0].focusCalls, 1);
  void pending;
});

test("关掉之后能再开一个新窗；旧窗口迟到的 closed 不清掉新窗口的占位", async () => {
  reset();
  const host = makeHost({ createSettingsWindow });
  await host.openSettings();
  wins[0].emit("closed"); // 用户关掉设置窗口
  await tick();
  assert.deepEqual(await host.openSettings(), { ok: true });
  assert.equal(wins.length, 2, "占位清掉之后要能重新开");
  wins[0].emit("closed"); // 旧窗口迟到的 closed
  await tick();
  assert.deepEqual(await host.openSettings(), { ok: true });
  assert.equal(wins.length, 2, "迟到的 closed 不许清掉新窗口的占位（否则会开第三个）");
  assert.equal(wins[1].focusCalls, 1, "新窗口被聚焦");
});

test("加载失败：关掉那个窗口并回 load-failed，不抛错；之后能再开", async () => {
  reset();
  mode.failLoad = true;
  const host = makeHost({ createSettingsWindow });
  const r = await host.openSettings();
  assert.deepEqual(r, { ok: false, reason: "load-failed" });
  assert.equal(wins[0].closeCalls, 1, "加载失败要把那个窗口关掉");
  await tick();
  mode.failLoad = false;
  assert.deepEqual(await host.openSettings(), { ok: true });
  assert.equal(wins.length, 2, "失败清掉占位后能再开");
});
'''

PROBE_WIRING = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SHELL = "@SHELL@";
const protocol = require(path.join(SHELL, "src", "shellprotocol.js"));
const { HOST_CHANNELS, registerHostIpc } = require(path.join(SHELL, "src", "ipc.js"));
const { createHostRelay, HOST_METHODS } = require(path.join(SHELL, "src", "hostrelay.js"));

const CHANNELS = [
  "themis-host:reauth",
  "themis-host:open-secret-window",
  "themis-host:open-external",
  "themis-host:reveal",
  "themis-host:notify",
  "themis-host:open-settings",
  "themis-host:save-theme",
];
const SETTINGS_URL = "themis-shell://app/index.html#/settings";

test("SHELL_SETTINGS_URL：常量逐字、isShellPageUrl 认它、加在 SHELL_STATUS_URL 之后", () => {
  assert.equal(protocol.SHELL_SETTINGS_URL, SETTINGS_URL);
  assert.equal(protocol.isShellPageUrl(protocol.SHELL_SETTINGS_URL), true, "设置地址要是合法的外壳页地址");
  assert.equal(protocol.isShellPageUrl("themis-shell://evil/index.html#/settings"), false, "别的 host 不认");
  const src = fs.readFileSync(path.join(SHELL, "src", "shellprotocol.js"), "utf8");
  assert.ok(src.indexOf("SHELL_STATUS_URL") < src.indexOf("SHELL_SETTINGS_URL"), "常量要加在 SHELL_STATUS_URL 之后");
});

test("HOST_CHANNELS 恰好七条、冻结、顺序固定（save-theme 在末尾）", () => {
  assert.ok(Object.isFrozen(HOST_CHANNELS), "HOST_CHANNELS 必须冻结");
  assert.deepEqual([...HOST_CHANNELS], CHANNELS);
});

test("ipc：七个通道都注册；新通道转交 openSettings、多余实参丢掉；来源不对回 forbidden 不进 host", async () => {
  const handlers = {};
  const calls = [];
  const host = {
    reauth: async () => ({ ok: true }),
    openSecretWindow: async () => ({ ok: true }),
    openExternal: async () => ({ ok: true }),
    reveal: async () => ({ ok: true }),
    notify: async () => ({ ok: true }),
    openSettings: async (...args) => { calls.push(args); return { ok: true }; },
    saveTheme: async () => ({ ok: true }),
  };
  const ipcMain = { handle: (ch, fn) => { handlers[ch] = fn; } };
  let allowed = true;
  registerHostIpc(ipcMain, host, () => allowed);
  for (const ch of CHANNELS) {
    assert.equal(typeof handlers[ch], "function", "通道没注册：" + ch);
  }
  assert.equal(Object.keys(handlers).length, CHANNELS.length, "只许注册这七个通道");
  const EV = { sender: {}, senderFrame: { url: "http://127.0.0.1:1/x" } };
  assert.deepEqual(await handlers["themis-host:open-settings"](EV), { ok: true });
  assert.deepEqual(await handlers["themis-host:open-settings"](EV, "EXTRA", "MORE"), { ok: true });
  assert.deepEqual(calls, [[], []], "多余的实参要丢掉（HOST_ARITY 是 0）：" + JSON.stringify(calls));
  allowed = false;
  calls.length = 0;
  assert.deepEqual(await handlers["themis-host:open-settings"](EV, "EXTRA"), { ok: false, reason: "forbidden" });
  assert.deepEqual(calls, [], "来源不对根本不进 host");
});

test("hostrelay：HOST_METHODS 恰好七项（saveTheme 在末尾）；openSettings 转给当前 host、没有 host 回 forbidden", async () => {
  assert.deepEqual([...HOST_METHODS], [
    "reauth", "openSecretWindow", "openExternal", "reveal", "notify", "openSettings", "saveTheme",
  ]);
  const relay = createHostRelay();
  assert.deepEqual(await relay.host.openSettings(), { ok: false, reason: "forbidden" }, "没有当前 host 不抛错");
  const calls = [];
  relay.use({ openSettings: async (...args) => { calls.push(args); return { ok: true, via: "relay" }; } }, () => true);
  assert.deepEqual(await relay.host.openSettings(), { ok: true, via: "relay" });
  assert.deepEqual(calls, [[]]);
  relay.clear();
  assert.deepEqual(await relay.host.openSettings(), { ok: false, reason: "forbidden" }, "clear 之后回到没有 host");
});

test("preload 真跑一遍：恰好一次 exposeInMainWorld(themisHost)、键恰好九个、openSettings 无参转交、恰好一个 on", () => {
  const source = fs.readFileSync(path.join(SHELL, "preload.js"), "utf8");
  const requires = [];
  const exposes = [];
  const invokes = [];
  const listeners = [];
  const fakeRequire = (name) => {
    requires.push(name);
    assert.equal(name, "electron", "preload 只许 require electron，却 require 了 " + name);
    return {
      contextBridge: { exposeInMainWorld: (n, o) => exposes.push([n, o]) },
      ipcRenderer: {
        invoke: async (...args) => { invokes.push(args); return { ok: true }; },
        sendSync: () => ({ theme: "dark", density: "standard" }),
        on: (...args) => listeners.push(args),
      },
    };
  };
  vm.runInNewContext(source, { require: fakeRequire, module: { exports: {} }, exports: {} });
  assert.deepEqual(requires, ["electron"]);
  assert.equal(exposes.length, 1, "exposeInMainWorld 必须恰好调一次");
  const [name, api] = exposes[0];
  assert.equal(name, "themisHost");
  assert.deepEqual(Object.keys(api).sort(), [
    "getAppearance", "notify", "onAppearance", "openExternal", "openSecretWindow",
    "openSettings", "reauth", "reveal", "saveTheme",
  ]);
  assert.equal(typeof api.openSettings, "function", "openSettings 必须是函数");
  api.openSettings();
  api.openSettings("EXTRA");
  assert.deepEqual(invokes.slice(-2), [["themis-host:open-settings"], ["themis-host:open-settings"]],
    "openSettings 无参转交固定通道（多余实参丢掉）：" + JSON.stringify(invokes));
  assert.equal(listeners.length, 1, "模块级恰好一个 ipcRenderer.on（外观事件分发）");
  assert.equal(listeners[0][0], "themis-host:appearance");
  assert.ok(!/ipcRenderer\s*\.\s*send\s*\(/.test(source), "preload 不许有 ipcRenderer.send");
});
'''


def test_p01_host_open_settings_probe():
    """P01 / D02、D06：host.openSettings 的行为——不可用、首次建窗、已开 restore+focus、并发只建一个、
    关掉再开（迟到的 closed 不误伤）、加载失败关窗回 load-failed。"""
    _expect_probe_pass("t060-host-open-settings", PROBE_HOST)


def test_p02_interface_wiring_probe():
    """P02 / D01：SHELL_SETTINGS_URL 与 isShellPageUrl；HOST_CHANNELS 恰好六条冻结；ipc 的转交与丢参与
    forbidden；hostrelay 六项与兜底；preload 真跑（键恰好六个、openSettings 无参转交）。"""
    _expect_probe_pass("t060-interface-wiring", PROBE_WIRING)


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + Vitest 探针（照 T057 门禁的写法；候选里还没有本片标记时不调 npm）
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
    return env


def git_status_set():
    proc = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
                          cwd=REPO_ROOT, capture_output=True, timeout=120)
    assert proc.returncode == 0, f"git status 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


def t060_marker_present():
    """候选里是否已有 T060 的标记（hostSettings.ts 与 SettingsPage 的新分支）：没有就不起 npm。"""
    try:
        hs_path = WEB / "src" / "live" / "hostSettings.ts"
        page_path = WEB / "src" / "pages" / "SettingsPage.tsx"
        hs = _read(hs_path) if hs_path.is_file() else ""
        page = _read(page_path) if page_path.is_file() else ""
    except OSError:
        return False
    return "hostOpenSettings" in hs and "hostOpenSettings" in page


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T057 门禁）
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 150}


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = "desktop/web/package.json 不存在，未调用 npm"
        return pipe
    if not t060_marker_present():
        pipe.reason = ("候选里还没有 T060 的标记（src/live/hostSettings.ts 的 hostOpenSettings、"
                       "SettingsPage.tsx 的新分支），没有东西可测，未调用 npm；候选把入口与接线都放进去"
                       "之后，流水线才会运行 npm ci、Vitest 与探针")
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
                run_step("npm ci --offline", [npm, "ci", "--offline"])
        ci_ok = any(pipe.steps.get(k) is not None and pipe.steps[k].code == 0
                    for k in ("npm ci", "npm ci --offline"))
        if ci_ok:
            run_step("npm test", [npm, "test"])
            if pipe.steps.get("npm test") is not None and pipe.steps["npm test"].code == 0:
                uid = uuid.uuid4().hex[:12]
                missing = [rel for rel in (HOSTSETTINGS_REL, PAGE_REL) if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped["host"] = f"探针 host 要用的文件不存在，未运行：{missing}"
                else:
                    name = f"probe-{uid}-t060-host.test.tsx"
                    probe_dir.mkdir(exist_ok=True)
                    path = probe_dir / name
                    written.append(path)
                    path.write_text(VITEST_PROBE_HOST, encoding="utf-8", newline="\n")
                    pipe.probe_files["host"] = name
                    run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label="probe:host")
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
    want = probe_count(VITEST_PROBE_HOST)
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m and int(m.group(1)) >= want, f"探针 {key} 应至少有 {want} 条通过：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), f"探针 {key} 有失败或跳过：\n{step.tail}"


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


# ---------------------------------------------------------------------------
# Q / D 系列：流水线断言与 Vitest 探针
# ---------------------------------------------------------------------------

VITEST_PROBE_HOST = r'''// T060 门禁探针：SettingsPage 在有/没有宿主接口时的两个分支（照 shellpages-settings.test.tsx 的既有写法，
// 不 mock 被测组件；探针自带全部辅助函数，测完把 window.themisHost 删掉）。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

let hostCalls = 0;
let hostAnswer: any = { ok: true };

function installHost() {
  (window as any).themisHost = {
    openSettings: async () => {
      hostCalls += 1;
      return hostAnswer;
    },
  };
}
function dropHost() {
  delete (window as any).themisHost;
}

beforeEach(async () => {
  window.location.hash = '';
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
  hostCalls = 0;
  hostAnswer = { ok: true };
});
afterEach(async () => {
  cleanup();
  const sc: any = await import('../src/shellpages/shellContext');
  sc.resetShellStubs();
  dropHost();
  window.location.hash = '';
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
});

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
function textOf(el: Element | null): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function openSettingsBtn(): HTMLButtonElement {
  // 按「以『打开设置』开头」找按钮：执行端照仓库习惯把按钮写成「打开设置…」也算（审核 B3）
  const hit = (Array.from(document.querySelectorAll('button')) as HTMLButtonElement[])
    .filter((b) => textOf(b).indexOf('打开设置') === 0)[0];
  expect(hit, '找不到以「打开设置」开头的按钮').toBeTruthy();
  return hit as HTMLButtonElement;
}

async function renderSettingsPage() {
  const hash = '#/settings?shell=ready';
  window.location.hash = hash;
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
  const ctx: any = await import('../src/shellpages/shellContext');
  let shell: any = null;
  function Grab() {
    shell = ctx.useThemisShell('ready');
    return null;
  }
  const g = render(<Grab />);
  g.unmount();
  const getState = vi.spyOn(shell, 'getState');
  window.location.hash = hash;
  const mod: any = await import('../src/pages/SettingsPage');
  const r = render(<mod.default />);
  await settle();
  return { getState, unmount: r.unmount };
}

describe('T060 有宿主接口：设置页签走新分支', () => {
  it('挂载调一次 openSettings；getState 一次不调；页面没有「没有收到服务的回应」', async () => {
    installHost();
    const { getState } = await renderSettingsPage();
    expect(hostCalls, '挂载时要调一次 openSettings').toBe(1);
    expect(getState.mock.calls.length, '新分支不调 getState').toBe(0);
    expect(document.body.textContent || '', '新分支不出现旧分支的通用出错块').not.toContain('没有收到服务的回应');
  });

  it('h1 仍是「设置」；点 [打开设置] 再调一次', async () => {
    installHost();
    await renderSettingsPage();
    expect(textOf(document.querySelector('h1'))).toBe('设置');
    fireEvent.click(openSettingsBtn());
    await settle();
    expect(hostCalls).toBe(2);
  });

  it('返回 { ok: false, reason: "unavailable" }：一行 role=alert 带 reason，getState 仍不调', async () => {
    hostAnswer = { ok: false, reason: 'unavailable' };
    installHost();
    const { getState } = await renderSettingsPage();
    const alerts = Array.from(document.querySelectorAll('[role="alert"]')) as HTMLElement[];
    const hit = alerts.filter((a) => (a.textContent || '').indexOf('unavailable') !== -1);
    expect(hit.length, '要有带 reason 的 alert').toBeGreaterThanOrEqual(1);
    expect(getState.mock.calls.length).toBe(0);
    expect(document.body.textContent || '').not.toContain('没有收到服务的回应');
  });
});

describe('T060 没有宿主接口：照旧渲染旧设置页', () => {
  it('h1「设置」、五组 data-settings-group、getState 调一次', async () => {
    dropHost();
    const { getState } = await renderSettingsPage();
    expect(textOf(document.querySelector('h1'))).toBe('设置');
    const groups = Array.from(document.querySelectorAll('[data-settings-group]'))
      .map((g) => g.getAttribute('data-settings-group'));
    expect(groups).toEqual(['repos', 'runtime', 'usage', 'appearance', 'about']);
    expect(getState.mock.calls.length).toBe(1);
  });
});
'''


def test_q1_pipeline_steps_pass(pipeline):
    """Q1 / V02、D13：npm 依赖（已在就跳过重装）、npm test 全绿（含执行端新测试与冻结的既有测试）都退出 0；
    依赖文件一个字节没动；gate-probe/ 没有留下。"""
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


def test_q2_worktree_unchanged_by_pipeline(pipeline):
    """Q2（守卫）：流水线与探针前后 git status 相同；gate-probe/ 没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"


def test_d01_settings_page_probe(pipeline):
    """D 探针 / D07、D08：SettingsPage 的新分支（挂载调一次、点 [打开设置] 再调一次、不调 getState、
    失败 alert 带 reason、无「没有收到服务的回应」）；没有宿主接口时照旧渲染旧设置页（h1、五组、getState 一次）。"""
    assert_probe_ok(pipeline, "host")
