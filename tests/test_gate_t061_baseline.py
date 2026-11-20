"""T061 战前门禁（片 A，外壳侧）：外观设置生效——缺省主题改暗、窗口启动即用已保存的 ``{ theme, density }``
（主进程同步应答）、保存改了主题或密度就当场广播给所有还开着的窗口、宿主新增 ``saveTheme``、建窗按当前
外观设背景色（合同 t061-desktop-appearance-settings.v1，基线 2488d36b——缺省主题还是 ``"system"``、
没有外观通道、没有广播、没有背景色）。

被测对象（只钉片 A 带来的行为；``desktop/web/**`` 归片 B（T063），本门禁不碰它）：

- 缺省值：``src/settings.js`` 的 ``DEFAULT_SETTINGS.theme`` 改 ``"dark"``（density 仍 ``"standard"``）；
  另导出纯函数 ``appearanceOf(settings)``（返回 ``{ theme, density }`` 的新对象）。已存 ``"system"`` 的
  旧文件照旧读出（不迁移）。
- 通道字面量（五个）：``themis-host:save-theme``（invoke，进 ``HOST_CHANNELS`` 末尾第七项）、
  ``themis-host:get-appearance`` / ``themis-shell:get-appearance``（同步读，``ipcMain.on``，不进
  ``SHELL_CHANNELS``/``HOST_CHANNELS`` 的 invoke 表）、``themis-host:appearance`` /
  ``themis-shell:appearance``（主进程 → 页面推送）。
- 宿主接口：``preload.js`` 的 ``window.themisHost`` 九个成员（原六个 + ``saveTheme`` / ``getAppearance`` /
  ``onAppearance``）；``getAppearance`` 走 ``sendSync``、调用时才取；模块级恰好一个
  ``ipcRenderer.on("themis-host:appearance")``，监听只收外观对象一个实参，退订只删自己那条。
- 外壳接口：``shell-preload.js`` 的 ``window.themisShell`` 十一个成员（原十个 + ``getAppearance``）；
  ``on`` 认 ``"service-state"`` 与 ``"appearance"`` 两个事件名，别的事件名回空退订函数；模块级恰好两个
  ``ipcRenderer.on``。
- 宿主编排：``src/host.js`` 的 ``saveTheme(pref)`` 顺序固定（不在 ``THEME_VALUES`` → ``bad-args``；没注入
  → ``unavailable``；否则转交注入实现；注入抛错 → ``internal``），返回成员变七个；``src/hostrelay.js`` 的
  ``HOST_METHODS`` 七项，没有当前 host 回 ``forbidden``。
- 广播：``src/shellapi.js`` 的可选注入 ``onAppearanceChange`` 与 ``initialSettings``（返回成员仍是十个，
  不加 ``appearance()`` 之类新成员）；``saveSettings`` 整包合格且写盘成功、``theme``/``density`` 与写之前
  不同才回调一次 ``onAppearanceChange({ theme, density })``；写盘失败、外观没变、只改仓库一律不调；回调
  抛错不影响返回值。
- 建窗：``src/window.js`` 的纯函数 ``backgroundFor(theme, systemDark)``（暗 ``#0C111A``、亮 ``#F3F5F9``、
  ``"system"`` 与任何别的值按 ``systemDark`` 取）；``main.js`` 的外壳页窗口（``createShellPageWindow``）与
  两个分支的服务窗口建窗 ``options`` 里设 ``backgroundColor``，凭据窗口不设；``new BrowserWindow`` 与
  ``.protocol.handle(`` 仍各恰好一处。
- ``main.js`` 接线：electron 解构加 ``nativeTheme``；外壳分支启动时 ``const initialSettings =
  store.load().settings;``（只读这一次）并传给 ``createShellApi``；主进程持 ``currentAppearance``（只在
  ``onAppearanceChange`` 回调里更新）；广播给服务窗口（``HOST_APPEARANCE_EVENT``）与 ``shellWin`` /
  ``settingsWin``（``SHELL_APPEARANCE_EVENT``），每个窗口发之前查 ``isDestroyed()``；``saveTheme`` 只在
  外壳分支的 ``createHost`` 注入（实现是 ``api.saveSettings({ theme: pref })`` 转成信封），带参数分支不
  注入；两个分支各注册同步外观读取——外壳分支两个（宿主 + 外壳通道）、带参数分支一个（宿主通道，恒答
  ``null``）——共三处 ``ipcMain.on``，通道只许那两个读取字面量，每个处理函数先设
  ``event.returnValue = null`` 再 ``try/catch``，每条路径都设过 ``returnValue``；``desktop/shell`` 下除
  ``main.js`` 外任何 ``.js``（含 tests/**）都不许出现 ``ipcMain.on``。
- ``desktop/shell/README.md``：新增「外观」相关段落（缺省暗、外观对象、五个通道字面量、``saveTheme`` 的
  信封与 ``reason`` 词表、同步读取「没有可读的外观就是 ``null``」、背景色取值）；既有 needle 由
  T026/T028/T030/T035/T039/T060 的门禁照旧管，这里只钉新增记号。

基线（2488d36b）上这些记号与行为都不存在，所以失败落在「记号不在」「探针子进程退出码非 0」这类断言上，
不是收集失败：模块级只导入标准库，仓库文件的读取与探针的运行都发生在用例函数里。外壳探针是自包含的
``node --test`` 文件（Node 24 自带；``desktop/shell`` 没有运行时依赖，不需要 npm ci），Python 把探针源码
写进系统临时目录、以仓库根为 cwd 运行、用完即删；两份 preload 的探针用 ``vm.runInNewContext`` 真跑一遍
源码，注入假 require 与假 ipcRenderer（补 ``sendSync`` / ``on``）。本片不碰 ``desktop/web``，没有 npm
流水线用例。

结构：

- 静态断言（``test_s*``，不用流水线）：settings 缺省值与 ``appearanceOf``（S01）；``backgroundFor``
  导出（S02）；ipc/shellipc 的通道表与新常量（S03）；host 与 hostrelay 的记号（S04）；shellapi 的注入项
  （S05）；两份 preload 的形状（恰好一次 exposeInMainWorld、``ipcRenderer.on`` 的个数与频道、sendSync、
  自包含）（S06）；main.js 的同步读取（三处、通道白名单、每条路径都设 returnValue、ipcMain.on 只许
  main.js）（S07）；main.js 的外观接线（initialSettings / currentAppearance / 广播 / saveTheme 注入）
  （S08）；建窗背景色与形状计数（S09）；README 外观段（S10）。
- 外壳探针断言（``test_p01`` … ``test_p07``，跑 node --test，不需要依赖）：
  - P01 / D01、D05：settings 缺省值与 ``appearanceOf``；``backgroundFor`` 的纯函数取值。
  - P02 / D03：shellapi 的 ``onAppearanceChange``——改 theme/density 且写盘成功回调一次；写盘失败、
    外观没变、只改仓库都不调；回调抛错不影响返回值；``initialSettings`` 当内存初值（不再 store.load、
    深拷贝）；返回成员仍是十个。
  - P03 / D04：host 的 ``saveTheme`` 四种结局与七个成员。
  - P04：hostrelay 七项与 forbidden 兜底。
  - P05：ipc 七通道的转交与丢参、新常量逐字且不进 invoke 表；shellipc 仍九通道、新常量逐字。
  - P06：preload 真跑——九键、saveTheme 单实参转交、getAppearance 走 sendSync、onAppearance 订阅/
    退订/单实参、模块级恰好一个 on。
  - P07：shell-preload 真跑——十一键、getAppearance 走 sendSync、on('appearance') 订阅/退订/单实参、
    别的事件名回空退订、模块级恰好两个 on。
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL = REPO_ROOT / "desktop" / "shell"

HOST_CHANNELS = (
    "themis-host:reauth",
    "themis-host:open-secret-window",
    "themis-host:open-external",
    "themis-host:reveal",
    "themis-host:notify",
    "themis-host:open-settings",
    "themis-host:save-theme",
)
HOST_APPEARANCE_CHANNEL = "themis-host:get-appearance"
HOST_APPEARANCE_EVENT = "themis-host:appearance"
SHELL_APPEARANCE_CHANNEL = "themis-shell:get-appearance"
SHELL_APPEARANCE_EVENT = "themis-shell:appearance"
SHELL_CHANNELS = (
    "themis-shell:get-state",
    "themis-shell:pick-repo",
    "themis-shell:pick-python",
    "themis-shell:pick-kit",
    "themis-shell:pick-transcript-dir",
    "themis-shell:save-settings",
    "themis-shell:start-service",
    "themis-shell:restart-service",
    "themis-shell:open-external",
)
HOST_METHODS = ("reauth", "openSecretWindow", "openExternal", "reveal", "notify", "openSettings", "saveTheme", "listRepos", "switchRepo", "addRepo")
# Object.keys(...).sort() 之后的逐字键表（JS 默认排序，UTF-16 码元序）
HOST_KEYS_SORTED = [
    "addRepo",
    "getAppearance",
    "listRepos",
    "notify",
    "onAppearance",
    "openExternal",
    "openSecretWindow",
    "openSettings",
    "reauth",
    "reveal",
    "saveTheme",
    "switchRepo",
]
SHELL_KEYS_SORTED = [
    "getAppearance",
    "getState",
    "on",
    "openExternal",
    "pickKit",
    "pickPython",
    "pickRepo",
    "pickTranscriptDir",
    "restartService",
    "saveSettings",
    "startService",
]
API_KEYS_SORTED = [
    "getState",
    "on",
    "openExternal",
    "pickKit",
    "pickPython",
    "pickRepo",
    "pickTranscriptDir",
    "restartService",
    "saveSettings",
    "startService",
]

IPC_MAIN_ON_RE = re.compile(r"ipcMain\s*\.\s*on\s*\(")
IPC_MAIN_ON_WORD_RE = re.compile(r"\bipcMain\s*\.\s*on\b")
IPC_RENDERER_ON_RE = re.compile(r"ipcRenderer\s*\.\s*on\s*\(")
IPC_RENDERER_SEND_RE = re.compile(r"ipcRenderer\s*\.\s*send\s*\(")
EXPOSE_RE = re.compile(r"exposeInMainWorld\s*\(")
RETURN_VALUE_NULL_RE = re.compile(r"event\s*\.\s*returnValue\s*=\s*null")
RETURN_VALUE_NON_NULL_RE = re.compile(r"event\s*\.\s*returnValue\s*=\s*(?!\s*null\b)")
REQUIRE_BEYOND_ELECTRON_RE = re.compile(r"""require\(\s*['"](\.|node:)""")


# ---------------------------------------------------------------------------
# 通用小工具（只读仓库文件；模块级不做任何仓库 IO）
# ---------------------------------------------------------------------------

def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def _shell_read(rel: str) -> str:
    p = SHELL / rel
    assert p.is_file(), f"desktop/shell/{rel} 不存在"
    return _norm(p.read_text(encoding="utf-8"))


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
    main.js 的形状扫描（ipcMain.on、backgroundColor、createHost 的计数与定位）先过这一遍：
    注释里提一句不算违规，只有代码里的形状才算。"""
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


def _main_code() -> str:
    """main.js 剥注释之后的文本（形状扫描用它；断言失败信息里引用的片段照此）。"""
    return _strip_js_comments(_shell_read("main.js"))


# ---------------------------------------------------------------------------
# 外壳探针：node --test（Node 24 自带，desktop/shell 没有依赖，不需要 npm ci）
# ---------------------------------------------------------------------------

def _run_probe(name: str, source: str, timeout: float = 300.0) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    assert node, "本机没有 node，无法运行门禁探针"
    with tempfile.TemporaryDirectory(prefix="t061-gate-") as td:
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

def test_s01_settings_default_dark():
    """S01 / D01：缺省主题改暗——DEFAULT_SETTINGS.theme 是 "dark"、density 仍 "standard"，
    并导出纯函数 appearanceOf；THEME_VALUES/DENSITY_VALUES 不动。"""
    text = _shell_read("src/settings.js")
    block = _block_span(text, "const DEFAULT_SETTINGS = Object.freeze(")
    assert block, "src/settings.js 缺 DEFAULT_SETTINGS 块"
    assert 'theme: "dark"' in block, "DEFAULT_SETTINGS.theme 要改成 \"dark\"（缺省暗）"
    assert 'density: "standard"' in block, "DEFAULT_SETTINGS.density 仍是 \"standard\""
    assert "appearanceOf" in text, "src/settings.js 要导出纯函数 appearanceOf(settings)"
    exports = _block_span(text, "module.exports = {")
    assert exports and "appearanceOf" in exports, "module.exports 里要有 appearanceOf"
    assert 'const THEME_VALUES = ["system", "light", "dark"];' in text, "THEME_VALUES 不许动"
    assert 'const DENSITY_VALUES = ["standard", "compact"];' in text, "DENSITY_VALUES 不许动"


def test_s02_window_background_for():
    """S02 / D05：window.js 新增并导出纯函数 backgroundFor(theme, systemDark)。"""
    text = _shell_read("src/window.js")
    assert "backgroundFor" in text, "src/window.js 要新增纯函数 backgroundFor(theme, systemDark)"
    exports = _block_span(text, "module.exports = {")
    assert exports and "backgroundFor" in exports, "module.exports 里要有 backgroundFor"
    assert "#0C111A" in text and "#F3F5F9" in text, "backgroundFor 的两个背景色字面量要在 window.js 里"


def test_s03_channel_tables():
    """S03：ipc 的通道表与新常量、shellipc 的新常量——save-theme 进 HOST_CHANNELS 末尾，
    外观读取/事件通道不进任何 invoke 表。"""
    ipc = _shell_read("src/ipc.js")
    block = _call_span(ipc, "const HOST_CHANNELS = Object.freeze(")
    assert block, "src/ipc.js 缺 HOST_CHANNELS"
    assert '"themis-host:save-theme"' in block, "HOST_CHANNELS 要加第七项 themis-host:save-theme"
    assert block.index('"themis-host:open-settings"') < block.index('"themis-host:save-theme"'), \
        "themis-host:save-theme 要加在 HOST_CHANNELS 末尾（其余顺序不变）"
    assert '"themis-host:save-theme": "saveTheme"' in ipc, "HOST_METHOD 要把新通道映到 saveTheme"
    assert '"themis-host:save-theme": 1' in ipc, "HOST_ARITY 里新通道的实参个数要是 1"
    exports = _block_span(ipc, "module.exports = {")
    assert exports, "src/ipc.js 缺 module.exports"
    for name in ("HOST_APPEARANCE_CHANNEL", "HOST_APPEARANCE_EVENT"):
        assert name in ipc, f"src/ipc.js 要导出 {name}"
        assert name in exports, f"module.exports 里要有 {name}"
    assert f'HOST_APPEARANCE_CHANNEL = "{HOST_APPEARANCE_CHANNEL}"' in ipc, \
        "HOST_APPEARANCE_CHANNEL 的字面量要是 themis-host:get-appearance"
    assert f'HOST_APPEARANCE_EVENT = "{HOST_APPEARANCE_EVENT}"' in ipc, \
        "HOST_APPEARANCE_EVENT 的字面量要是 themis-host:appearance"
    shell = _shell_read("src/shellipc.js")
    shell_exports = _block_span(shell, "module.exports = {")
    assert shell_exports, "src/shellipc.js 缺 module.exports"
    for name in ("SHELL_APPEARANCE_CHANNEL", "SHELL_APPEARANCE_EVENT"):
        assert name in shell, f"src/shellipc.js 要导出 {name}"
        assert name in shell_exports, f"module.exports 里要有 {name}"
    assert f'SHELL_APPEARANCE_CHANNEL = "{SHELL_APPEARANCE_CHANNEL}"' in shell, \
        "SHELL_APPEARANCE_CHANNEL 的字面量要是 themis-shell:get-appearance"
    assert f'SHELL_APPEARANCE_EVENT = "{SHELL_APPEARANCE_EVENT}"' in shell, \
        "SHELL_APPEARANCE_EVENT 的字面量要是 themis-shell:appearance"
    shell_block = _call_span(shell, "const SHELL_CHANNELS = Object.freeze(")
    assert shell_block, "src/shellipc.js 缺 SHELL_CHANNELS"
    for literal in (SHELL_APPEARANCE_CHANNEL, SHELL_APPEARANCE_EVENT):
        assert f'"{literal}"' not in shell_block, f"{literal} 不是 invoke 通道，不许进 SHELL_CHANNELS"


def test_s04_host_and_relay_markers():
    """S04 / D04：host 的 saveTheme 编排记号与 hostrelay 的第七项（行为在 P03/P04 里真跑）。"""
    host = _shell_read("src/host.js")
    assert "saveTheme" in host, "src/host.js 要有 saveTheme 编排"
    assert "THEME_VALUES" in host, "saveTheme 要用 THEME_VALUES 判 bad-args"
    relay = _shell_read("src/hostrelay.js")
    assert '"saveTheme"' in relay, "src/hostrelay.js 的 HOST_METHODS 要加 saveTheme"


def test_s05_shellapi_injections():
    """S05 / D03：shellapi 的两个新可选注入项记号（行为在 P02 里真跑；返回成员仍是十个也在 P02 里逐字比对）。"""
    text = _shell_read("src/shellapi.js")
    assert "onAppearanceChange" in text, "createShellApi 要有可选注入项 onAppearanceChange(appearance)"
    assert "initialSettings" in text, "createShellApi 要有可选注入项 initialSettings（已读出的设置）"
    assert "store.load()" in text or "store.load(" in text, "没给 initialSettings 时仍照旧 store.load()"


def test_s06_preloads_shape():
    """S06：两份 preload 的形状——恰好一次 exposeInMainWorld、自包含、on 的个数与频道、sendSync 在位。"""
    preload = _shell_read("preload.js")
    assert len(EXPOSE_RE.findall(preload)) == 1, "preload.js 仍恰好一次 exposeInMainWorld"
    assert not REQUIRE_BEYOND_ELECTRON_RE.search(preload), "preload.js 仍只许 require electron（T025 门禁 S03）"
    for mark in ("saveTheme:", "getAppearance:", "onAppearance:"):
        assert mark in preload, f"preload.js 的 themisHost 要加成员 {mark[:-1]}"
    assert "sendSync" in preload, "getAppearance 要用 ipcRenderer.sendSync 同步取"
    assert len(IPC_RENDERER_ON_RE.findall(preload)) == 1, \
        "preload.js 模块级恰好一个 ipcRenderer.on（外观事件分发）"
    assert '"themis-host:appearance"' in preload, "那个 on 的频道字面量要是 themis-host:appearance"
    assert '"themis-host:save-theme"' in preload, "saveTheme 要转交固定通道 themis-host:save-theme"
    assert '"themis-host:get-appearance"' in preload, "getAppearance 的同步通道字面量要在 preload 里"
    assert not IPC_RENDERER_SEND_RE.search(preload), "preload 仍不许有 ipcRenderer.send"
    shell = _shell_read("shell-preload.js")
    assert len(EXPOSE_RE.findall(shell)) == 1, "shell-preload.js 仍恰好一次 exposeInMainWorld"
    assert not REQUIRE_BEYOND_ELECTRON_RE.search(shell), "shell-preload.js 仍只许 require electron"
    assert "getAppearance:" in shell, "themisShell 要加成员 getAppearance（sendSync 同步取）"
    assert "sendSync" in shell, "getAppearance 要用 ipcRenderer.sendSync 同步取"
    assert len(IPC_RENDERER_ON_RE.findall(shell)) == 2, \
        "shell-preload.js 模块级恰好两个 ipcRenderer.on（service-state 与 appearance）"
    assert '"themis-shell:service-state"' in shell, "service-state 那条订阅照旧"
    assert '"themis-shell:appearance"' in shell, "新事件订阅的频道字面量要是 themis-shell:appearance"
    assert '"themis-shell:get-appearance"' in shell, "getAppearance 的同步通道字面量要在 shell-preload 里"
    assert '"appearance"' in shell, "on 要认 appearance 这个事件名"
    assert not IPC_RENDERER_SEND_RE.search(shell), "shell-preload 仍不许有 ipcRenderer.send"


def _ipc_main_on_calls(code: str):
    """main.js 里每次 ipcMain.on( 调用的（文本，首参）列表；首参取到第一层逗号为止。"""
    calls = []
    for m in IPC_MAIN_ON_RE.finditer(code):
        open_at = code.find("(", m.start())
        end = _match_bracket(code, open_at)
        assert end > 0, "main.js 里 ipcMain.on( 的括号配不平"
        span = code[m.start():end + 1]
        head = span[span.find("(") + 1:]
        first_arg = head.split(",")[0].strip()
        calls.append((span, first_arg))
    return calls


ALLOWED_SYNC_CHANNEL_ARGS = (
    "HOST_APPEARANCE_CHANNEL",
    '"themis-host:get-appearance"',
    "SHELL_APPEARANCE_CHANNEL",
    '"themis-shell:get-appearance"',
)


def test_s07_main_sync_reads():
    """S07 / D02：main.js 的同步外观读取——恰好三处 ipcMain.on、通道只许那两个读取字面量、
    每个处理函数先设 event.returnValue = null 再 try/catch 且 catch 里也设 null；
    带参数分支那一处一律答 null；desktop/shell 下别的 .js 一处 ipcMain.on 都不许有。"""
    code = _main_code()
    calls = _ipc_main_on_calls(code)
    assert len(calls) == 3, \
        f"main.js 的同步外观读取要恰好三处 ipcMain.on（现在是 {len(calls)} 处：两处在 runShellPage、" \
        "一处在带参数起服务分支）"
    for span, first_arg in calls:
        assert first_arg in ALLOWED_SYNC_CHANNEL_ARGS, \
            f"ipcMain.on 的通道只许那两个外观读取字面量，却见到：{first_arg}"
    host_reads = [c for c in calls if c[1] in ("HOST_APPEARANCE_CHANNEL", '"themis-host:get-appearance"')]
    shell_reads = [c for c in calls if c[1] in ("SHELL_APPEARANCE_CHANNEL", '"themis-shell:get-appearance"')]
    assert len(host_reads) == 2, "宿主同步读取要注册两处（外壳分支 + 带参数分支）"
    assert len(shell_reads) == 1, "外壳同步读取只在外壳分支注册一处"
    for span, _ in calls:
        assert RETURN_VALUE_NULL_RE.search(span), "处理函数要先把 event.returnValue 设成 null（缺省）"
        assert len(RETURN_VALUE_NULL_RE.findall(span)) >= 2, \
            "catch 里也要把 event.returnValue 设回 null（每条路径都设过 returnValue）"
        assert "try" in span and "catch" in span, "处理函数要先设缺省再 try/catch"
    answering = [span for span, _ in calls if RETURN_VALUE_NON_NULL_RE.search(span)]
    always_null = [span for span, _ in calls if not RETURN_VALUE_NON_NULL_RE.search(span)]
    assert len(answering) == 2, \
        "外壳分支的两处：来源被认时把 event.returnValue 覆盖成当前外观对象"
    for span in answering:
        assert "isDestroyed" in span, "来源检查要先看窗口是否还在（窗口为 null 或已销毁一律不认）"
    assert len(always_null) == 1, "带参数起服务分支没有设置存储，一律答 null"
    always_null_span = always_null[0]
    assert always_null_span in [span for span, arg in calls
                                if arg in ("HOST_APPEARANCE_CHANNEL", '"themis-host:get-appearance"')], \
        "恒答 null 的那一处是带参数分支的宿主同步读取（HOST 通道）"
    # ipcMain.on 只许 main.js 有：desktop/shell 下其他 .js（含 tests/**、src/**、两份 preload）一处都不许有
    offenders = []
    for js in sorted(SHELL.rglob("*.js")):
        rel = js.relative_to(SHELL).as_posix()
        if rel == "main.js" or "node_modules" in rel:
            continue
        if IPC_MAIN_ON_WORD_RE.search(_read(js)):
            offenders.append(rel)
    assert not offenders, f"desktop/shell 下除 main.js 外不许出现 ipcMain.on：{offenders}"


def test_s08_main_appearance_wiring():
    """S08 / D03、D04：main.js 的外观接线——nativeTheme、initialSettings 只读一次传给 createShellApi、
    currentAppearance 只在回调里更新、广播给四类窗口（每个发前查 isDestroyed）、saveTheme 只注入外壳分支。"""
    code = _main_code()
    m = re.search(r"const\s*\{([^}]*)\}\s*=\s*require\(\"electron\"\)", code)
    assert m, "main.js 要从 electron 解构导入"
    assert "nativeTheme" in m.group(1), "electron 的解构里要加 nativeTheme"
    assert re.search(r"const\s+initialSettings\s*=\s*store\.load\(\)\.settings\s*;", code), \
        "外壳分支启动时要 const initialSettings = store.load().settings;（只读这一次，坏文件最多写一份副本）"
    api_span = _call_span(code, "createShellApi(")
    assert api_span, "main.js 缺 createShellApi 调用"
    assert "initialSettings" in api_span, "createShellApi 要传 initialSettings（不再自己 store.load 起步）"
    assert "onAppearanceChange" in api_span, "createShellApi 要注入 onAppearanceChange（广播的接点）"
    assert "currentAppearance" in code, "主进程要持 currentAppearance（初值 appearanceOf(initialSettings)）"
    assert "appearanceOf" in code, "currentAppearance 的初值用 appearanceOf"
    # 广播：服务窗口发 HOST_APPEARANCE_EVENT，shellWin 与 settingsWin 发 SHELL_APPEARANCE_EVENT，
    # 每个发送点之前要有 isDestroyed 检查（窗口为 null 或已销毁就跳过）
    host_sends = []
    shell_sends = []
    for m2 in re.finditer(r"webContents\s*\.\s*send\s*\(", code):
        open_at = code.find("(", m2.start())
        end = _match_bracket(code, open_at)
        assert end > 0, "webContents.send( 的括号配不平"
        span = code[m2.start():end + 1]
        channel = span[span.find("(") + 1:].split(",")[0].strip()
        if "HOST_APPEARANCE_EVENT" in channel or '"' + HOST_APPEARANCE_EVENT + '"' in channel:
            host_sends.append((m2.start(), span))
        elif "SHELL_APPEARANCE_EVENT" in channel or '"' + SHELL_APPEARANCE_EVENT + '"' in channel:
            shell_sends.append((m2.start(), span))
    assert len(host_sends) >= 1, "服务窗口要收到 HOST_APPEARANCE_EVENT"
    assert len(shell_sends) >= 2, "外壳页窗口与设置窗口要各收到 SHELL_APPEARANCE_EVENT"
    for at, span in host_sends + shell_sends:
        before = code[max(0, at - 260):at]
        assert "isDestroyed" in before, f"每个窗口发之前要查 isDestroyed()：{span[:80]}"
    # saveTheme 只注入外壳分支的 createHost（实现是 api.saveSettings({ theme: pref }) 转成信封）
    host_calls = _call_spans(code, "createHost(")
    assert len(host_calls) == 2, f"main.js 的 createHost( 应仍恰好两次（现在是 {len(host_calls)} 次）"
    assert "saveTheme" in host_calls[0], "外壳分支的 createHost 要注入 saveTheme"
    assert re.search(r"api\s*\.\s*saveSettings\(\s*\{\s*theme\s*:\s*pref\s*\}\s*\)", host_calls[0]), \
        "注入的实现要调 api.saveSettings({ theme: pref })"
    assert "saveTheme" not in host_calls[1], "带参数起服务分支不注入 saveTheme（那里回 unavailable）"


def test_s09_main_window_backgrounds():
    """S09 / D05：建窗背景色——外壳页窗口与两个分支的服务窗口都在 options 里设
    backgroundColor: backgroundFor(theme, nativeTheme.shouldUseDarkColors)，凭据窗口不设；
    new BrowserWindow 与 .protocol.handle( 仍各恰好一处。"""
    code = _main_code()
    assert len(re.findall(r"new\s+BrowserWindow", code)) == 1, "new BrowserWindow 仍必须恰好一处"
    assert code.count(".protocol.handle(") == 1, ".protocol.handle( 仍必须恰好一处"
    spans = []
    start = 0
    while True:
        at = code.find("guardedWindow(", start)
        if at < 0:
            break
        open_at = code.find("(", at)
        end = _match_bracket(code, open_at)
        assert end > 0, "guardedWindow( 的括号配不平"
        if not code[:at].rstrip().endswith("function"):
            spans.append(code[at:end + 1])
        start = end + 1
    helper, secrets, services = [], [], []
    for span in spans:
        if "shell-preload.js" in span:
            helper.append(span)
        elif "credentialPartition" in span:
            secrets.append(span)
        elif '"preload.js"' in span or "preloadPath" in span:
            services.append(span)
    assert len(spans) == 5, f"guardedWindow 应仍恰好五处（现在是 {len(spans)} 处）"
    assert len(helper) == 1, "createShellPageWindow 里一处（外壳页窗口与设置窗口共用）"
    assert len(secrets) == 2, "两个分支的凭据窗口各一处"
    assert len(services) == 2, "两个分支的服务窗口各一处"
    for span in helper + services:
        assert "backgroundColor" in span, "建窗 options 要设 backgroundColor"
        assert re.search(r"backgroundFor\s*\(", span), "背景色要用 backgroundFor(theme, …) 取"
        assert "shouldUseDarkColors" in span, "theme 为 system 时按 nativeTheme.shouldUseDarkColors 取"
    for span in secrets:
        assert "backgroundColor" not in span, "凭据窗口不设背景色"


def test_s10_readme_appearance():
    """S10 / D10：README 写清外观段——缺省暗、五个通道字面量、saveTheme 的信封与 reason 词表、
    同步读取回 null 的语义、背景色取值；既有 needle 由旧门禁照旧管，这里只钉新增记号。"""
    text = _shell_read("README.md")
    for literal in ("themis-host:save-theme", HOST_APPEARANCE_CHANNEL, HOST_APPEARANCE_EVENT,
                    SHELL_APPEARANCE_CHANNEL, SHELL_APPEARANCE_EVENT):
        assert literal in text, f"README 要写通道字面量 {literal}"
    for needle in ("saveTheme", "getAppearance", "onAppearance", "appearanceOf", "backgroundFor",
                   "#0C111A", "#F3F5F9", "bad-args", "unavailable", "forbidden", "write-failed",
                   "internal", "null", "dark"):
        assert needle in text, f"README 缺「{needle}」（外观段：信封、reason 词表、同步读取语义、背景色）"
    assert "theme" in text and "density" in text, "README 要写外观对象 { theme, density } 的两个字段"


# ---------------------------------------------------------------------------
# P 系列：外壳探针（node --test，被测模块只在探针里 require；行为断言都在探针里）
# ---------------------------------------------------------------------------

PROBE_SETTINGS = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const settings = require("@SHELL@/src/settings.js");
const windowMod = require("@SHELL@/src/window.js");

const { DEFAULT_SETTINGS, THEME_VALUES, DENSITY_VALUES, createSettingsStore, appearanceOf } = settings;

test("DEFAULT_SETTINGS：theme 是 dark、density 仍 standard；THEME_VALUES/DENSITY_VALUES 不动", () => {
  assert.equal(DEFAULT_SETTINGS.theme, "dark");
  assert.equal(DEFAULT_SETTINGS.density, "standard");
  assert.deepEqual([...THEME_VALUES], ["system", "light", "dark"]);
  assert.deepEqual([...DENSITY_VALUES], ["standard", "compact"]);
});

test("没有 settings.json 时 load() 读出 dark/standard（D01）", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "t061-settings-"));
  const first = createSettingsStore({ dir }).load();
  assert.equal(first.settings.theme, "dark");
  assert.equal(first.settings.density, "standard");
  assert.equal(first.badCopy, null, "没有文件是常态，不留副本");
});

test("已存成 system 的旧文件照旧读出 system（不迁移，站主已接受）", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "t061-system-"));
  const saved = {
    version: 1, repos: [], currentRepo: null, transcriptDirs: [],
    theme: "system", density: "compact", pythonPath: null, kitPath: null,
  };
  fs.writeFileSync(path.join(dir, "settings.json"), JSON.stringify(saved, null, 2) + "\n");
  const loaded = createSettingsStore({ dir }).load();
  assert.equal(loaded.settings.theme, "system");
  assert.equal(loaded.settings.density, "compact");
});

test("appearanceOf：返回 {theme,density} 的新对象，不带别的键，改它不动入参", () => {
  const src = {
    version: 1, repos: [], currentRepo: null, transcriptDirs: [],
    theme: "light", density: "compact", pythonPath: null, kitPath: null,
  };
  const view = appearanceOf(src);
  assert.deepEqual(Object.keys(view).sort(), ["density", "theme"]);
  assert.deepEqual(view, { theme: "light", density: "compact" });
  assert.notEqual(view, src, "不许返回入参本身");
  view.theme = "dark";
  assert.equal(src.theme, "light", "改返回值不许改到入参");
});

test("backgroundFor：暗 #0C111A、亮 #F3F5F9、system 与非法值按 systemDark（D05）", () => {
  const backgroundFor = windowMod.backgroundFor;
  assert.equal(typeof backgroundFor, "function", "window.js 要导出 backgroundFor");
  assert.equal(backgroundFor("dark", false), "#0C111A");
  assert.equal(backgroundFor("dark", true), "#0C111A");
  assert.equal(backgroundFor("light", true), "#F3F5F9");
  assert.equal(backgroundFor("light", false), "#F3F5F9");
  assert.equal(backgroundFor("system", true), "#0C111A");
  assert.equal(backgroundFor("system", false), "#F3F5F9");
  assert.equal(backgroundFor("neon", false), "#F3F5F9", "非法值当 system 对待");
  assert.equal(backgroundFor("neon", true), "#0C111A");
  assert.equal(backgroundFor(undefined, true), "#0C111A", "没有外观时（null 的 theme）也当 system");
});
'''


def test_p01_settings_and_window_probe():
    """P01 / D01、D05：缺省暗、旧文件不迁移、appearanceOf 的新对象、backgroundFor 的全部取值。"""
    _expect_probe_pass("t061-settings-window", PROBE_SETTINGS)


PROBE_SHELLAPI = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { createShellApi } = require("@SHELL@/src/shellapi.js");

function baseSettings(over) {
  return Object.assign({
    version: 1, repos: [], currentRepo: null, transcriptDirs: [],
    theme: "dark", density: "standard", pythonPath: null, kitPath: null,
  }, over || {});
}

function makeApi(over) {
  const state = { mem: null, loads: 0, fail: false };
  const store = {
    load: () => {
      state.loads += 1;
      return { settings: state.mem || baseSettings(), badCopy: null };
    },
    save: (next) => {
      if (state.fail) throw new Error("disk full");
      state.mem = next;
    },
  };
  const opts = Object.assign({
    store,
    chooseDirectory: async () => null,
    chooseFile: async () => null,
    confirmExternal: async () => false,
    openExternal: async () => {},
    probe: {
      probePython: async () => null,
      probeKit: async () => null,
      detectPython: async () => ({ status: "missing", path: "", version: "" }),
      detectKit: async () => null,
    },
  }, over || {});
  return { api: createShellApi(opts), state };
}

test("返回成员仍是十个（不加 appearance() 之类新成员；与 themisShell.ts 逐名相等归 T030 P04 与 shellshape）", () => {
  const { api } = makeApi();
  assert.deepEqual(Object.keys(api).sort(), [
    "getState", "on", "openExternal", "pickKit", "pickPython", "pickRepo",
    "pickTranscriptDir", "restartService", "saveSettings", "startService",
  ]);
});

test("改 theme 且写盘成功 → onAppearanceChange 恰好一次、实参是只含新值的 {theme,density}（D03）", async () => {
  const seen = [];
  const { api } = makeApi({ onAppearanceChange: (a) => seen.push(a) });
  const r = await api.saveSettings({ theme: "light" });
  assert.equal(r.ok, true);
  assert.deepEqual(seen, [{ theme: "light", density: "standard" }], "一次、两个字段都是新值");
});

test("一次保存同时改 theme 与 density → 仍只回调一次，两字段都是新值", async () => {
  const seen = [];
  const { api } = makeApi({ onAppearanceChange: (a) => seen.push(a) });
  await api.saveSettings({ theme: "system", density: "compact" });
  assert.deepEqual(seen, [{ theme: "system", density: "compact" }]);
});

test("写盘失败 → 不回调、回 write-failed、内存回滚到原值", async () => {
  const seen = [];
  const { api, state } = makeApi({ onAppearanceChange: (a) => seen.push(a) });
  state.fail = true;
  const r = await api.saveSettings({ theme: "light" });
  assert.deepEqual(r, { ok: false, reason: "write-failed" });
  assert.deepEqual(seen, [], "写盘失败不广播");
  state.fail = false;
  const after = await api.getState();
  assert.equal(after.value.settings.theme, "dark", "内存回滚：还是写之前的值");
});

test("外观没变（同值重写、空补丁）→ 不回调", async () => {
  const seen = [];
  const { api } = makeApi({ onAppearanceChange: (a) => seen.push(a) });
  assert.equal((await api.saveSettings({ theme: "dark" })).ok, true);
  assert.equal((await api.saveSettings({})).ok, true);
  assert.equal((await api.saveSettings({ theme: "dark", density: "standard" })).ok, true);
  assert.deepEqual(seen, []);
});

test("只改仓库（pickTranscriptDir 加目录）→ 不回调", async () => {
  const seen = [];
  const { api } = makeApi({
    chooseDirectory: async () => "C:/tmp/records",
    onAppearanceChange: (a) => seen.push(a),
  });
  const r = await api.pickTranscriptDir();
  assert.equal(r.ok, true, "夹具本身要成功：" + JSON.stringify(r));
  assert.deepEqual(seen, []);
});

test("回调抛错 → 不影响 saveSettings 的返回值（吞掉异常，仍回 {ok:true,value}）", async () => {
  const { api } = makeApi({ onAppearanceChange: () => { throw new Error("boom"); } });
  const r = await api.saveSettings({ theme: "light" });
  assert.equal(r.ok, true);
  assert.equal(r.value.settings.theme, "light");
});

test("initialSettings：当内存初值（深拷贝、不与入参共用同一份）、不再 store.load 起步", async () => {
  const initial = baseSettings({ theme: "light", density: "compact" });
  const state = { loads: 0 };
  const api = createShellApi({
    store: {
      load: () => { state.loads += 1; return { settings: baseSettings(), badCopy: null }; },
      save: () => {},
    },
    probe: {
      probePython: async () => null,
      probeKit: async () => null,
      detectPython: async () => ({ status: "missing", path: "", version: "" }),
      detectKit: async () => null,
    },
    initialSettings: initial,
  });
  const r = await api.getState();
  assert.equal(r.value.settings.theme, "light", "用注入值当内存初值");
  assert.equal(r.value.settings.density, "compact");
  initial.theme = "dark"; // 深拷贝：api 的内存与注入的对象不共用同一份
  const again = await api.getState();
  assert.equal(again.value.settings.theme, "light", "改注入的对象不许影响 api 的内存");
  assert.equal(state.loads, 0, "给了 initialSettings 就不该 store.load()");
});
'''


def test_p02_shellapi_appearance_change_probe():
    """P02 / D03：onAppearanceChange 的五种不调与一次调、回调抛错、initialSettings 注入、返回十个成员。"""
    _expect_probe_pass("t061-shellapi-appearance", PROBE_SHELLAPI)


PROBE_HOST = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { createHost } = require("@SHELL@/src/host.js");

function makeHost(over) {
  return createHost(Object.assign({
    origin: "http://127.0.0.1:1",
    control: "ctrl-tok-t061abc",
    repo: "/tmp/repo",
    loadMain: async () => {},
    createSecretWindow: () => { throw new Error("不该开凭据窗口"); },
    confirmExternal: async () => true,
    openExternal: async () => {},
    showItem: () => {},
    showNotification: () => {},
    now: () => 0,
    controlTimeoutMs: 1000,
  }, over || {}));
}

test("暴露面：十个函数，listRepos/switchRepo/addRepo 依次在旧七项之后", () => {
  const host = makeHost({ saveTheme: async () => ({ ok: true }) });
  assert.deepEqual(Object.keys(host), [
    "reauth", "openSecretWindow", "openExternal", "reveal", "notify", "openSettings", "saveTheme",
    "listRepos", "switchRepo", "addRepo",
  ]);
  for (const name of Object.keys(host)) {
    assert.equal(typeof host[name], "function", name + " 必须是函数");
  }
});

test("bad-args：pref 不在 THEME_VALUES（neon/null/数字）→ 不进注入实现（D04）", async () => {
  const calls = [];
  const host = makeHost({ saveTheme: async (pref) => { calls.push(pref); return { ok: true }; } });
  assert.deepEqual(await host.saveTheme("neon"), { ok: false, reason: "bad-args" });
  assert.deepEqual(await host.saveTheme(null), { ok: false, reason: "bad-args" });
  assert.deepEqual(await host.saveTheme(123), { ok: false, reason: "bad-args" });
  assert.deepEqual(calls, [], "bad-args 根本不进注入实现");
});

test("bad-args 优先于 unavailable：没注入实现且 pref 非法 → 仍回 bad-args", async () => {
  const host = makeHost(); // 不带 saveTheme（带参数起服务的那条分支就是这样）
  assert.deepEqual(await host.saveTheme("neon"), { ok: false, reason: "bad-args" });
});

test("unavailable：没注入实现、pref 合法 → unavailable", async () => {
  const host = makeHost();
  assert.deepEqual(await host.saveTheme("dark"), { ok: false, reason: "unavailable" });
  assert.deepEqual(await host.saveTheme("system"), { ok: false, reason: "unavailable" });
});

test("转交：把 pref 原样交给注入实现，注入回的信封原样返回（成功与失败两种）", async () => {
  const calls = [];
  let answer = { ok: true, value: { theme: "light", density: "compact" } };
  const host = makeHost({ saveTheme: async (pref) => { calls.push(pref); return answer; } });
  assert.deepEqual(await host.saveTheme("light"), { ok: true, value: { theme: "light", density: "compact" } });
  answer = { ok: false, reason: "write-failed" };
  assert.deepEqual(await host.saveTheme("dark"), { ok: false, reason: "write-failed" });
  assert.deepEqual(calls, ["light", "dark"], "只转交这一个实参");
});

test("internal：注入实现抛错 → internal，不外传异常", async () => {
  const host = makeHost({ saveTheme: async () => { throw new Error("boom"); } });
  assert.deepEqual(await host.saveTheme("dark"), { ok: false, reason: "internal" });
});
'''


PROBE_HOSTRELAY = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { createHostRelay, HOST_METHODS } = require("@SHELL@/src/hostrelay.js");

test("HOST_METHODS 恰好十项，addRepo 在末尾", () => {
  assert.deepEqual([...HOST_METHODS], [
    "reauth", "openSecretWindow", "openExternal", "reveal", "notify", "openSettings", "saveTheme",
    "listRepos", "switchRepo", "addRepo",
  ]);
});

test("saveTheme 转给当前 host、实参照传；没有当前 host 回 forbidden（D04）", async () => {
  const relay = createHostRelay();
  assert.deepEqual(await relay.host.saveTheme("dark"), { ok: false, reason: "forbidden" }, "没有当前 host 不抛错");
  const calls = [];
  relay.use({ saveTheme: async (...args) => { calls.push(args); return { ok: true, value: { theme: args[0], density: "standard" } }; } }, () => true);
  assert.deepEqual(await relay.host.saveTheme("light"), { ok: true, value: { theme: "light", density: "standard" } });
  assert.deepEqual(calls, [["light"]]);
  relay.clear();
  assert.deepEqual(await relay.host.saveTheme("dark"), { ok: false, reason: "forbidden" }, "clear 之后回到没有 host");
});
'''


def test_p03_host_save_theme_probe():
    """P03 / D04：host.saveTheme 的四种结局（bad-args/unavailable/转交/internal）与七个成员。"""
    _expect_probe_pass("t061-host-save-theme", PROBE_HOST)


def test_p04_hostrelay_save_theme_probe():
    """P04 / D04：HOST_METHODS 七项、saveTheme 转交与没有 host 的 forbidden 兑底。"""
    _expect_probe_pass("t061-hostrelay-save-theme", PROBE_HOSTRELAY)


PROBE_IPC = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const ipcMod = require("@SHELL@/src/ipc.js");
const shellIpc = require("@SHELL@/src/shellipc.js");
const { HOST_CHANNELS, HOST_APPEARANCE_CHANNEL, HOST_APPEARANCE_EVENT, registerHostIpc } = ipcMod;
const {
  SHELL_CHANNELS, SERVICE_STATE_CHANNEL, SHELL_APPEARANCE_CHANNEL, SHELL_APPEARANCE_EVENT,
  registerShellIpc,
} = shellIpc;

const HOST_LIST = [
  "themis-host:reauth",
  "themis-host:open-secret-window",
  "themis-host:open-external",
  "themis-host:reveal",
  "themis-host:notify",
  "themis-host:open-settings",
  "themis-host:save-theme",
  "themis-host:list-repos",
  "themis-host:switch-repo",
  "themis-host:add-repo",
];
const SHELL_LIST = [
  "themis-shell:get-state",
  "themis-shell:pick-repo",
  "themis-shell:pick-python",
  "themis-shell:pick-kit",
  "themis-shell:pick-transcript-dir",
  "themis-shell:save-settings",
  "themis-shell:start-service",
  "themis-shell:restart-service",
  "themis-shell:open-external",
];

test("HOST_CHANNELS 恰好十条、冻结、顺序固定（add-repo 在末尾）", () => {
  assert.ok(Object.isFrozen(HOST_CHANNELS), "HOST_CHANNELS 必须冻结");
  assert.deepEqual([...HOST_CHANNELS], HOST_LIST);
});

test("宿主外观常量逐字，且不进 HOST_CHANNELS（同步读不是 invoke，事件是推送）", () => {
  assert.equal(HOST_APPEARANCE_CHANNEL, "themis-host:get-appearance");
  assert.equal(HOST_APPEARANCE_EVENT, "themis-host:appearance");
  assert.ok(!HOST_CHANNELS.includes(HOST_APPEARANCE_CHANNEL), "同步读取不进 invoke 表");
  assert.ok(!HOST_CHANNELS.includes(HOST_APPEARANCE_EVENT), "事件推送不进 invoke 表");
});

test("registerHostIpc：十个通道都用 handle 注册；save-theme 转交 saveTheme、多余实参丢掉；来源不对回 forbidden；host 抛错回 internal", async () => {
  const handlers = {};
  const registered = [];
  const ipcMain = {
    handle: (ch, fn) => { handlers[ch] = fn; registered.push(ch); },
    on: (ch) => { throw new Error("不许用 ipcMain.on：" + ch); },
  };
  const calls = [];
  const host = {
    reauth: async () => ({ ok: true, via: "reauth" }),
    openSecretWindow: async () => ({ ok: true }),
    openExternal: async () => ({ ok: true }),
    reveal: async () => ({ ok: true }),
    notify: async () => ({ ok: true }),
    openSettings: async () => ({ ok: true }),
    saveTheme: async (...args) => { calls.push(args); return { ok: true, value: { theme: args[0], density: "standard" } }; },
  };
  let allowed = true;
  registerHostIpc(ipcMain, host, () => allowed);
  assert.deepEqual(registered, HOST_LIST, "只许注册这十个通道、顺序照表");
  const EV = { sender: {}, senderFrame: { url: "http://127.0.0.1:1/x" } };
  assert.deepEqual(await handlers["themis-host:save-theme"](EV, "dark"),
    { ok: true, value: { theme: "dark", density: "standard" } });
  assert.deepEqual(await handlers["themis-host:save-theme"](EV, "light", "EXTRA"),
    { ok: true, value: { theme: "light", density: "standard" } });
  assert.deepEqual(calls, [["dark"], ["light"]], "多余实参丢掉（HOST_ARITY 是 1）：" + JSON.stringify(calls));
  assert.deepEqual(await handlers["themis-host:reauth"](EV), { ok: true, via: "reauth" }, "既有六条照旧");
  allowed = false;
  calls.length = 0;
  assert.deepEqual(await handlers["themis-host:save-theme"](EV, "dark"), { ok: false, reason: "forbidden" });
  assert.deepEqual(calls, [], "来源不对根本不进 host");
  allowed = true;
  const throwing = Object.assign({}, host, { saveTheme: async () => { throw new Error("boom"); } });
  const handlers2 = {};
  registerHostIpc({ handle: (ch, fn) => { handlers2[ch] = fn; } }, throwing, () => true);
  assert.deepEqual(await handlers2["themis-host:save-theme"](EV, "dark"), { ok: false, reason: "internal" });
});

test("SHELL_CHANNELS 仍恰好九条、冻结、顺序不变；外壳外观常量逐字且不进表", () => {
  assert.ok(Object.isFrozen(SHELL_CHANNELS), "SHELL_CHANNELS 必须冻结");
  assert.deepEqual([...SHELL_CHANNELS], SHELL_LIST);
  assert.equal(SERVICE_STATE_CHANNEL, "themis-shell:service-state");
  assert.equal(SHELL_APPEARANCE_CHANNEL, "themis-shell:get-appearance");
  assert.equal(SHELL_APPEARANCE_EVENT, "themis-shell:appearance");
  assert.ok(!SHELL_CHANNELS.includes(SHELL_APPEARANCE_CHANNEL), "同步读取不进 invoke 表");
  assert.ok(!SHELL_CHANNELS.includes(SHELL_APPEARANCE_EVENT), "事件推送不进 invoke 表");
});

test("registerShellIpc 仍只注册九个 handle（外观读取不在这里，也不许有一次 ipcMain.on）", () => {
  const registered = [];
  const ipcMain = {
    handle: (ch) => { registered.push(ch); },
    on: (ch) => { throw new Error("registerShellIpc 不许用 ipcMain.on：" + ch); },
  };
  const api = {};
  for (const name of ["getState", "pickRepo", "pickPython", "pickKit", "pickTranscriptDir",
    "saveSettings", "startService", "restartService", "openExternal"]) {
    api[name] = async () => ({ ok: true });
  }
  registerShellIpc(ipcMain, api, () => false);
  assert.deepEqual(registered, SHELL_LIST);
});
'''


def test_p05_ipc_channels_probe():
    """P05：ipc 七通道的转交与丢参、新常量逐字不进表；shellipc 仍九通道、两个新常量逐字不进表。"""
    _expect_probe_pass("t061-ipc-channels", PROBE_IPC)


PROBE_PRELOAD = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SHELL = "@SHELL@";

function runPreload() {
  const requires = [];
  const exposes = [];
  const invokes = [];
  const syncs = [];
  const listeners = {};
  const fakeRequire = (name) => {
    requires.push(name);
    assert.equal(name, "electron", "preload 只许 require electron，却 require 了 " + name);
    return {
      contextBridge: { exposeInMainWorld: (n, o) => exposes.push([n, o]) },
      ipcRenderer: {
        invoke: async (...args) => { invokes.push(args); return { ok: true }; },
        sendSync: (...args) => { syncs.push(args); return { theme: "light", density: "compact" }; },
        on: (ch, fn) => { (listeners[ch] = listeners[ch] || []).push(fn); },
      },
    };
  };
  const source = fs.readFileSync(path.join(SHELL, "preload.js"), "utf8");
  vm.runInNewContext(source, { require: fakeRequire, module: { exports: {} }, exports: {} });
  return { source, requires, exposes, invokes, syncs, listeners };
}

test("真跑一遍：恰好一次 exposeInMainWorld(themisHost)、键恰好十二个（原九个 + 三个新成员）", () => {
  const run = runPreload();
  assert.deepEqual(run.requires, ["electron"]);
  assert.equal(run.exposes.length, 1, "exposeInMainWorld 必须恰好调一次");
  const [name, api] = run.exposes[0];
  assert.equal(name, "themisHost");
  assert.deepEqual(Object.keys(api).sort(), [
    "addRepo", "getAppearance", "listRepos", "notify", "onAppearance", "openExternal",
    "openSecretWindow", "openSettings", "reauth", "reveal", "saveTheme", "switchRepo",
  ]);
  for (const key of Object.keys(api)) {
    assert.equal(typeof api[key], "function", key + " 必须是函数");
  }
});

test("saveTheme：只转交这一个实参到固定通道，返回信封不拆", async () => {
  const run = runPreload();
  const api = run.exposes[0][1];
  const r = await api.saveTheme("dark");
  assert.deepEqual(r, { ok: true }, "与既有六函数同款：不拆信封");
  assert.deepEqual(run.invokes.slice(-1), [["themis-host:save-theme", "dark"]],
    "只转交一个实参：" + JSON.stringify(run.invokes));
});

test("getAppearance：sendSync 同步取、调用时才取（载入时不发）、回值原样返回", () => {
  const run = runPreload();
  const api = run.exposes[0][1];
  assert.deepEqual(run.syncs, [], "preload 载入时不许发 sendSync");
  const got = api.getAppearance();
  assert.deepEqual(run.syncs, [["themis-host:get-appearance"]]);
  assert.deepEqual(got, { theme: "light", density: "compact" }, "回值原样返回（对象或 null 都照转）");
});

test("onAppearance：模块级恰好一个 ipcRenderer.on(频道 themis-host:appearance)；监听只收外观一个实参；退订只删自己那条", () => {
  const run = runPreload();
  const api = run.exposes[0][1];
  const channels = Object.keys(run.listeners);
  assert.deepEqual(channels.sort(), ["themis-host:appearance"], "模块级只注册这一个频道");
  assert.equal(run.listeners["themis-host:appearance"].length, 1, "恰好一个 ipcRenderer.on");
  const fire = run.listeners["themis-host:appearance"][0];
  const seen1 = [];
  const seen2 = [];
  const off1 = api.onAppearance((...args) => seen1.push(args));
  assert.equal(typeof off1, "function", "onAppearance 同步返回退订函数");
  api.onAppearance((...args) => seen2.push(args));
  fire({ sender: {} }, { theme: "dark", density: "standard" });
  assert.deepEqual(seen1, [[{ theme: "dark", density: "standard" }]], "监听只收外观对象一个实参");
  assert.deepEqual(seen2, [[{ theme: "dark", density: "standard" }]]);
  off1();
  fire({ sender: {} }, { theme: "light", density: "compact" });
  assert.equal(seen1.length, 1, "退订之后不再收");
  assert.equal(seen2.length, 2, "另一条订阅不受影响");
  assert.ok(!/removeListener|\.off\(/.test(run.source), "不依赖 removeListener/off");
});

test("preload 源码形状：恰好一个 ipcRenderer.on、没有 ipcRenderer.send、自包含", () => {
  const run = runPreload();
  assert.equal((run.source.match(/ipcRenderer\s*\.\s*on\s*\(/g) || []).length, 1);
  assert.equal((run.source.match(/exposeInMainWorld\s*\(/g) || []).length, 1);
  assert.ok(!/ipcRenderer\s*\.\s*send\s*\(/.test(run.source), "仍不许有 ipcRenderer.send");
  assert.ok(!/require\(\s*['"](\.|node:)/.test(run.source), "仍只 require electron");
});
'''


PROBE_SHELLPRELOAD = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SHELL = "@SHELL@";

function runShellPreload() {
  const requires = [];
  const exposes = [];
  const invokes = [];
  const syncs = [];
  const listeners = {};
  const fakeRequire = (name) => {
    requires.push(name);
    assert.equal(name, "electron", "shell-preload 只许 require electron，却 require 了 " + name);
    return {
      contextBridge: { exposeInMainWorld: (n, o) => exposes.push([n, o]) },
      ipcRenderer: {
        invoke: (...args) => { invokes.push(args); return Promise.resolve({ ok: true, value: 1 }); },
        sendSync: (...args) => { syncs.push(args); return { theme: "dark", density: "compact" }; },
        on: (ch, fn) => { (listeners[ch] = listeners[ch] || []).push(fn); },
      },
    };
  };
  const source = fs.readFileSync(path.join(SHELL, "shell-preload.js"), "utf8");
  vm.runInNewContext(source, { require: fakeRequire, module: { exports: {} }, exports: {} });
  return { source, requires, exposes, invokes, syncs, listeners };
}

test("真跑一遍：恰好一次 exposeInMainWorld(themisShell)、键恰好十一个（原十个 + getAppearance）", () => {
  const run = runShellPreload();
  assert.deepEqual(run.requires, ["electron"]);
  assert.equal(run.exposes.length, 1, "exposeInMainWorld 必须恰好调一次");
  const [name, api] = run.exposes[0];
  assert.equal(name, "themisShell");
  assert.deepEqual(Object.keys(api).sort(), [
    "getAppearance", "getState", "on", "openExternal", "pickKit", "pickPython",
    "pickRepo", "pickTranscriptDir", "restartService", "saveSettings", "startService",
  ]);
});

test("getAppearance：sendSync 同步取 themis-shell:get-appearance、调用时才取、回值原样返回", () => {
  const run = runShellPreload();
  const api = run.exposes[0][1];
  assert.deepEqual(run.syncs, [], "载入时不许发 sendSync");
  const got = api.getAppearance();
  assert.deepEqual(run.syncs, [["themis-shell:get-appearance"]]);
  assert.deepEqual(got, { theme: "dark", density: "compact" });
});

test("on('appearance')：模块级恰好两个 ipcRenderer.on（service-state 与 appearance 各一）；监听只收外观一个实参；退订只删自己那条", () => {
  const run = runShellPreload();
  const api = run.exposes[0][1];
  const channels = Object.keys(run.listeners).sort();
  assert.deepEqual(channels, ["themis-shell:appearance", "themis-shell:service-state"],
    "模块级恰好两个频道");
  for (const ch of channels) {
    assert.equal(run.listeners[ch].length, 1, ch + " 只注册一个 ipcRenderer.on");
  }
  const fire = run.listeners["themis-shell:appearance"][0];
  const seen1 = [];
  const seen2 = [];
  const off1 = api.on("appearance", (...args) => seen1.push(args));
  assert.equal(typeof off1, "function", "同步返回退订函数");
  api.on("appearance", (...args) => seen2.push(args));
  fire({ sender: {} }, { theme: "light", density: "standard" });
  assert.deepEqual(seen1, [[{ theme: "light", density: "standard" }]], "监听只收外观对象一个实参");
  assert.deepEqual(seen2, [[{ theme: "light", density: "standard" }]]);
  off1();
  fire({ sender: {} }, { theme: "dark", density: "compact" });
  assert.equal(seen1.length, 1, "退订之后不再收");
  assert.equal(seen2.length, 2, "另一条订阅不受影响");
});

test("service-state 那条照旧：只收 state 一个实参；别的事件名同步回空退订函数、不注册", () => {
  const run = runShellPreload();
  const api = run.exposes[0][1];
  const seen = [];
  const off = api.on("service-state", (...args) => seen.push(args));
  run.listeners["themis-shell:service-state"][0]({ sender: {} }, { kind: "idle" });
  assert.deepEqual(seen, [[{ kind: "idle" }]], "service-state 仍只收 state 一个实参");
  off();
  const before = JSON.stringify(Object.keys(run.listeners).map((ch) => run.listeners[ch].length));
  const noop = api.on("other-event", () => {});
  assert.equal(typeof noop, "function", "别的事件名同步回空退订函数");
  assert.doesNotThrow(() => noop());
  assert.equal(JSON.stringify(Object.keys(run.listeners).map((ch) => run.listeners[ch].length)), before,
    "别的事件名不注册新订阅");
});

test("shell-preload 源码形状：恰好两个 ipcRenderer.on、没有 ipcRenderer.send、自包含", () => {
  const run = runShellPreload();
  assert.equal((run.source.match(/ipcRenderer\s*\.\s*on\s*\(/g) || []).length, 2);
  assert.equal((run.source.match(/exposeInMainWorld\s*\(/g) || []).length, 1);
  assert.ok(!/ipcRenderer\s*\.\s*send\s*\(/.test(run.source), "仍不许有 ipcRenderer.send");
  assert.ok(!/require\(\s*['"](\.|node:)/.test(run.source), "仍只 require electron");
});
'''


def test_p06_preload_probe():
    """P06：preload 真跑——九键、saveTheme 单实参转交、getAppearance 走 sendSync、onAppearance 订阅/
    退订/单实参、模块级恰好一个 on、自包含。"""
    _expect_probe_pass("t061-preload", PROBE_PRELOAD)


def test_p07_shellpreload_probe():
    """P07：shell-preload 真跑——十一键、getAppearance 走 sendSync、on('appearance') 订阅/退订/单实参、
    service-state 照旧、别的事件名回空退订、模块级恰好两个 on。"""
    _expect_probe_pass("t061-shellpreload", PROBE_SHELLPRELOAD)
