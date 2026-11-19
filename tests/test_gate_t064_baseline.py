"""T064 战前门禁（外壳侧）：仓库切换与单实例——同一 userData 只开一份（拿不到锁以 0 退出、
持锁那份先 restore 再 focus）、宿主接口 ``window.themisHost`` 多 ``listRepos`` / ``switchRepo`` /
``addRepo`` 三个函数（12 个成员）、切换不退出应用（存盘 → ``relay.clear()`` → ``flow.stop()`` →
``flow.reset()`` → 开首次启动页 → 关旧窗口），外加 ``settings.selectRepo`` 纯函数、``shellapi``
两个经注入回调交出去的内部函数、``serviceflow.reset()``、选目录对话框父窗口补 ``serviceWindow``
一级（合同 t064-desktop-repo-switch-shell.v1，基线 9da7f2a3——宿主九个成员、没有单实例、没有
切换编排）。

被测对象（只钉本片带来的行为；外壳 IPC 仍九条、``createShellApi`` 仍十个成员、``desktop/web/**``
与 ``ts/**`` 一个不碰，归 T030/T028/T032/T033 的门禁照旧管）：

- ``src/settings.js``：导出纯函数 ``selectRepo(settings, id, at)``——只改 ``currentRepo`` 与目标条目的
  ``lastOpened``（``new Date(at).toISOString()``），入参不变，未知 id / 非字符串 id 回
  ``{ok:false, reason:"unknown-repo"}``；``PATCH_KEYS`` 与 ``SETTINGS_FILE_KEYS`` 一字不动。
- ``src/shellapi.js``：``createShellApi`` 的可选注入 ``onRepoOps``（建好时同步调一次，交出
  ``{listRepos, selectRepo}``）；``listRepos(runningId)`` 回 ``[{id,name,current}]`` 不带 ``path``；
  ``selectRepo(id, runningId, at)`` 依次 ``bad-args`` → ``unknown-repo`` → ``current-repo`` →
  存盘（失败 ``write-failed`` 且内存不变）；``at`` 不是有限数字用 ``Date.now()`` 兜底；返回对象
  仍十个成员、这两个函数不进外壳 IPC。
- ``src/serviceflow.js``：``reset()`` 只在 ``exited`` 时置 ``{kind:"idle"}`` 并以 ``{byShell:false}``
  通知；``idle``/``starting``/``running`` 下什么都不做；不经 ``moveTo``；全文件不许出现
  ``afterRunning: false``（T039 S01）；reset 之后能再 start 一个新 run。
- ``src/host.js``：``createHost`` 返回十个成员（旧七项之后依次 ``listRepos`` / ``switchRepo`` /
  ``addRepo``）；``listRepos`` 剥掉 ``path`` 只取三键；``switchRepo`` 的 ``bad-args`` 不进注入项、
  其余原样转交；``addRepo`` 把外壳信封的四种内层形状映射成宿主信封（``cancelled`` /
  ``not-git`` / ``no-agent`` / ``write-failed`` / ``{ok:true,id}``），结果不带 ``path`` 与 ``state``。
- 接线：三条新通道 ``themis-host:list-repos``（0 实参）/ ``themis-host:switch-repo``（1 实参）/
  ``themis-host:add-repo``（0 实参）接在 T061 表尾；``HOST_CHANNELS`` / ``HOST_METHOD`` /
  ``HOST_ARITY`` / ``HOST_METHODS`` 各十项；preload 十二个成员（注释「十二个函数」）、写法与
  既有成员同款；hostrelay 没有当前 host 回 ``forbidden``。
- ``main.js``：``runShellPage`` 开头（``root`` 之前）拿单实例锁，拿不到 ``app.exit(0); return;``；
  拿到注册 ``second-instance``（优先活的 ``serviceWindow``，其次活的 ``shellWin``；先 ``restore``
  再 ``focus``）；带参数分支不拿锁。``createShellApi`` 注入 ``onRepoOps``（存进 ``repoOps``）；
  外壳分支的第一次 ``createHost(`` 注入三个实现（``addRepo`` 先拆外壳信封），第二次不注入；切换
  入口是 ``runShellPage`` 里的独立函数（不写进发 ``SERVICE_STATE_CHANNEL`` 的订阅回调、不写进
  服务窗口 ``tracked.closed.then(async`` 的收尾），次序固定「存盘 → ``relay.clear()`` 且
  ``serviceWindow = null`` → ``flow.stop()`` → ``flow.reset()`` → 开 ``SHELL_START_URL`` → 关设置
  窗口与旧服务窗口」，首次启动页开不出来写一行 ``ERROR:`` 并以 1 退出；``chooseDirectory`` 的
  父窗口补 ``serviceWindow`` 一级（``chooseFile`` / ``confirmExternal`` 不动）。
- ``desktop/shell/README.md``：第 5 行不再把单实例与多仓库切换列进「仍没有」（「托盘」与「外壳页
  在本片就位」留着）；宿主接口一节首句「十二个函数」并加三行；``createHost`` 建的改成「十个函数」；
  退出码表补 0/1 两种新情形；冒烟加单实例与切换两条。

基线（9da7f2a3）上这些记号与行为都不存在，所以失败落在「记号不在」「探针子进程退出码非 0」这类
断言上，不是收集失败：模块级只导入标准库，仓库文件的读取与探针的运行都发生在用例函数里。外壳
探针是自包含的 ``node --test`` 文件（Node 自带；``desktop/shell`` 的纯逻辑模块不需要 Electron
本体，不需要 npm ci），Python 把探针源码写进系统临时目录、以仓库根为 cwd 运行、用完即删；
preload 探针用 ``vm.runInNewContext`` 真跑一遍源码，注入假 require 与假 ipcRenderer。本片不碰
``desktop/web``，没有 npm 流水线用例。

结构：

- 静态断言（``test_s*``，不用流水线）：settings 的导出与冻结键（S01）；ipc 三张表与外壳表不动
  （S02）；hostrelay 的 ``HOST_METHODS``（S03）；preload 的形状与三个新成员写法（S04）；host 的
  注入项改名与文件头注释（S05）；serviceflow 的 ``reset`` 记号（S06）；main.js 单实例（S07）；
  main.js 注入与选目录父窗口（S08）；main.js 切换编排的次序（S09）；README（S10）。
- 外壳探针断言（``test_p01`` … ``test_p07``，跑 node --test，不需要依赖）：
  - P01 / D02：settings 的 ``selectRepo`` 纯函数（未知/命中/ISO 时刻/入参不变）。
  - P02 / D03：shellapi 的 ``onRepoOps`` 与两个内部函数（十成员、listRepos 不带 path、
    selectRepo 四种拒绝与成功、写盘失败内存不变、缓存已清、``at`` 兜底）。
  - P03 / D05：host 的三个新成员（十键序、unavailable、bad-args、addRepo 四种映射、结果不带
    路径与 state）。
  - P04：hostrelay 十项与 forbidden 兜底。
  - P05 / D01：ipc 十通道的注册、转交与丢参、来源不对 forbidden、host 抛错 internal；外壳通道
    仍九条。
  - P06 / D01：preload 真跑——十二键、三个新成员转交固定通道、模块级仍恰好一个 on。
  - P07 / D04：serviceflow 的 ``reset``（exited→idle 带 ``byShell:false`` 通知；idle/starting/
    running 不动；reset 之后能再 start 新 run）。
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL = REPO_ROOT / "desktop" / "shell"

# HOST_CHANNELS 的最终形状：旧七项 + 三条新通道（本片接在 T061 表尾）
HOST_CHANNELS_FINAL = (
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
)
# HOST_METHODS 的最终形状：旧七项 + 三个新函数
HOST_METHODS_FINAL = (
    "reauth",
    "openSecretWindow",
    "openExternal",
    "reveal",
    "notify",
    "openSettings",
    "saveTheme",
    "listRepos",
    "switchRepo",
    "addRepo",
)
# Object.keys(window.themisHost).sort() 之后的逐字键表（JS 默认排序，UTF-16 码元序）
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
# createShellApi 的返回成员仍十个（一个不加；T028 :1499-1502 钉着）
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

EXPOSE_RE = re.compile(r"exposeInMainWorld\s*\(")
IPC_RENDERER_ON_RE = re.compile(r"ipcRenderer\s*\.\s*on\s*\(")
IPC_RENDERER_SEND_RE = re.compile(r"ipcRenderer\s*\.\s*send\s*\(")
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
    """open_at 处是 '('、'{' 或 '['：返回与之配平的闭括号下标；配不上回 -1。跳过 // 与 /* */ 注释和字符串。"""
    opener = text[open_at]
    closer = {"(": ")", "{": "}", "[": "]"}[opener]
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
    """token 形如 "module.exports = {"：返回那个块（含花括号）的文本；找不到回 None。"""
    at = text.find(token)
    if at < 0:
        return None
    open_at = text.find("{", at)
    end = _match_bracket(text, open_at)
    return None if end < 0 else text[at:end + 1]


def _prop_body(text: str, prop: str):
    """对象属性 prop 形如 "chooseDirectory:"：值是箭头函数时返回它的函数体文本；找不到回 None。"""
    at = text.find(prop)
    if at < 0:
        return None
    arrow = text.find("=>", at)
    if arrow < 0:
        return None
    open_at = text.find("{", arrow)
    end = _match_bracket(text, open_at)
    return None if end < 0 else text[open_at:end + 1]


def _strip_js_comments(text: str) -> str:
    """删掉 // 与 /* */ 注释，字符串照抄；每个被删字符换成空格，长度不变（下标仍可用）。"""
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
    """main.js 剥注释之后的文本（形状扫描用它）。"""
    return _strip_js_comments(_shell_read("main.js"))


def _run_shell_page_body(code: str) -> str:
    """runShellPage 的函数体文本（含函数头；code 是剥过注释的 main.js）。"""
    at = code.find("async function runShellPage(")
    assert at >= 0, "main.js 缺 runShellPage"
    open_at = code.find("{", at)
    end = _match_bracket(code, open_at)
    assert end > 0, "runShellPage 的括号配不平"
    return code[at:end + 1]


# ---------------------------------------------------------------------------
# 外壳探针：node --test（Node 自带，desktop/shell 的纯逻辑模块不需要依赖，不需要 npm ci）
# ---------------------------------------------------------------------------

def _run_probe(name: str, source: str, timeout: float = 300.0) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    assert node, "本机没有 node，无法运行门禁探针"
    with tempfile.TemporaryDirectory(prefix="t064-gate-") as td:
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

def test_s01_settings_select_repo_static():
    """S01 / D02：settings.js 导出纯函数 selectRepo；PATCH_KEYS 与 SETTINGS_FILE_KEYS 不动。"""
    text = _shell_read("src/settings.js")
    assert "selectRepo" in text, "src/settings.js 要加纯函数 selectRepo(settings, id, at)"
    exports = _block_span(text, "module.exports = {")
    assert exports and "selectRepo" in exports, "module.exports 里要有 selectRepo"
    assert 'const PATCH_KEYS = ["theme", "density", "removeRepo", "removeTranscriptDir", "resetPython", "resetKit"];' in text, \
        "PATCH_KEYS 一字不动（T028 钉着它与 themisShell.ts 一致）"
    assert 'const SETTINGS_FILE_KEYS = [' in text, "SETTINGS_FILE_KEYS 一字不动"
    assert '"version"' in text and '"kitPath"' in text, "SETTINGS_FILE_KEYS 的键一个不少"


def test_s02_ipc_tables():
    """S02 / D01：ipc 三张表各加三项（通道接在 T061 表尾、实参 0/1/0）；外壳表仍九条不许混进新通道。"""
    ipc = _shell_read("src/ipc.js")
    block = _call_span(ipc, "const HOST_CHANNELS = Object.freeze(")
    assert block, "src/ipc.js 缺 HOST_CHANNELS"
    for ch in HOST_CHANNELS_FINAL:
        assert f'"{ch}"' in block, f"HOST_CHANNELS 要含 {ch}"
    order = [block.index(f'"{ch}"') for ch in HOST_CHANNELS_FINAL]
    assert order == sorted(order), "HOST_CHANNELS 要是旧七项 + 新三项（新三条接在 T061 表尾）"
    assert '"themis-host:list-repos": "listRepos"' in ipc, "HOST_METHOD 要把 list-repos 映到 listRepos"
    assert '"themis-host:switch-repo": "switchRepo"' in ipc, "HOST_METHOD 要把 switch-repo 映到 switchRepo"
    assert '"themis-host:add-repo": "addRepo"' in ipc, "HOST_METHOD 要把 add-repo 映到 addRepo"
    assert '"themis-host:list-repos": 0' in ipc, "list-repos 的实参个数是 0"
    assert '"themis-host:switch-repo": 1' in ipc, "switch-repo 的实参个数是 1"
    assert '"themis-host:add-repo": 0' in ipc, "add-repo 的实参个数是 0"
    shell = _shell_read("src/shellipc.js")
    shell_block = _call_span(shell, "const SHELL_CHANNELS = Object.freeze(")
    assert shell_block, "src/shellipc.js 缺 SHELL_CHANNELS"
    for ch in HOST_CHANNELS_FINAL[7:]:
        assert ch not in shell_block, f"{ch} 不是外壳通道，不许进 SHELL_CHANNELS"


def test_s03_hostrelay_methods():
    """S03 / D01：hostrelay 的 HOST_METHODS 十项，新三项在表尾（行为在 P04 里真跑）。"""
    relay = _shell_read("src/hostrelay.js")
    at = relay.find("const HOST_METHODS = [")
    assert at >= 0, "src/hostrelay.js 缺 HOST_METHODS"
    open_at = relay.find("[", at)
    end = _match_bracket(relay, open_at)
    assert end > 0, "HOST_METHODS 的括号配不平"
    block = relay[at:end + 1]
    for name in HOST_METHODS_FINAL:
        assert f'"{name}"' in block, f"HOST_METHODS 要含 {name}"
    order = [block.index(f'"{name}"') for name in HOST_METHODS_FINAL]
    assert order == sorted(order), "HOST_METHODS 要是旧七项 + 新三项（顺序照此）"


def test_s04_preload_shape():
    """S04 / D01：preload 十二个成员——三个新成员与既有成员同款写法、注释「十二个函数」、
    仍恰好一次 exposeInMainWorld、一个 ipcRenderer.on、没有 ipcRenderer.send、自包含。"""
    preload = _shell_read("preload.js")
    assert "十二个函数" in preload, "preload.js 的注释要从「九个函数」改成「十二个函数」"
    assert len(EXPOSE_RE.findall(preload)) == 1, "preload.js 仍恰好一次 exposeInMainWorld"
    for pattern in (
        r'listRepos:\s*\(\)\s*=>\s*ipcRenderer\.invoke\("themis-host:list-repos"\)',
        r'switchRepo:\s*\(id\)\s*=>\s*ipcRenderer\.invoke\("themis-host:switch-repo",\s*id\)',
        r'addRepo:\s*\(\)\s*=>\s*ipcRenderer\.invoke\("themis-host:add-repo"\)',
    ):
        assert re.search(pattern, preload), f"preload 的新成员写法要与既有成员同款：{pattern}"
    assert len(IPC_RENDERER_ON_RE.findall(preload)) == 1, "preload.js 仍恰好一个 ipcRenderer.on（外观事件分发）"
    assert not IPC_RENDERER_SEND_RE.search(preload), "preload 仍不许有 ipcRenderer.send"
    assert not REQUIRE_BEYOND_ELECTRON_RE.search(preload), "preload 仍只许 require electron（自包含）"


def test_s05_host_markers():
    """S05 / D05：host 的三个新注入项（解构时照既有写法改名）与文件头注释「十个宿主函数」。"""
    host = _shell_read("src/host.js")
    assert "十个宿主函数" in host, "文件头注释要从「六个宿主函数」改成「十个宿主函数」"
    for marker in ("listReposImpl", "switchRepoImpl", "addRepoImpl"):
        assert marker in host, f"createHost 的解构要照既有写法（saveTheme: saveThemeImpl）改名注入项：{marker}"


def test_s06_serviceflow_reset_static():
    """S06 / D04：serviceflow 的 reset 记号——不经 moveTo、全文件无 afterRunning: false、
    「只前进不后退」那段注释写明 reset 是第二个例外。"""
    text = _shell_read("src/serviceflow.js")
    assert re.search(r"function\s+reset\s*\(|\breset\s*=", text), \
        "src/serviceflow.js 要实现 reset()（不经 moveTo；函数声明或箭头函数都行，行为在 P07 里真跑）"
    assert "afterRunning: false" not in text, "全文件不许出现 afterRunning: false（T039 S01）"
    idxs = [m.start() for m in re.finditer("只前进不后退", text)]
    assert idxs, "「只前进不后退」那段注释要还在"
    assert any("reset" in text[max(0, i - 120):i + 700] for i in idxs), \
        "「只前进不后退」那段注释要写明 reset 是第二个例外（exited → idle）"


def test_s07_main_single_instance():
    """S07 / D06：单实例——runShellPage 开头（root 之前）拿锁，拿不到 app.exit(0); return；
    拿到注册 second-instance（先 restore 再 focus）；带参数分支不拿锁（全文件只有这一处）。"""
    code = _main_code()
    assert code.count("requestSingleInstanceLock") == 1, \
        "requestSingleInstanceLock 只许出现一次（只在外壳分支；带参数分支一字不改）"
    rsp = _run_shell_page_body(code)
    lock = rsp.find("requestSingleInstanceLock")
    assert lock >= 0, "单实例锁要写在 runShellPage 里"
    root = rsp.find("const root")
    assert root > lock, "锁要在 root 计算与 index.html 检查之前"
    between = rsp[lock:root]
    assert "app.exit(0)" in between, "拿不到锁就以 0 退出"
    assert "return" in between, "拿不到锁就直接 return"
    for early in ("createSettingsStore", "createHostRelay", "registerHostIpc", "openShellWindow", "new BrowserWindow"):
        assert early not in between, f"拿不到锁的分支里不许建窗、不起子进程（却见到 {early}）"
    assert code.count("second-instance") == 1, "恰好注册一个 second-instance"
    si = code.find("second-instance")
    seg = code[si:si + 1800]
    assert "restore" in seg and "focus" in seg, "second-instance 里要 restore（最小化时）再 focus"
    assert seg.index("restore") < seg.index("focus"), "先 restore 再 focus"
    assert "serviceWindow" in seg and "shellWin" in seg, \
        "second-instance 优先取还活着的 serviceWindow，没有就取还活着的 shellWin"


def test_s08_main_wiring_and_dialog_parent():
    """S08 / D08：createShellApi 注入 onRepoOps；外壳分支的第一次 createHost 注入三个实现
    （第二次不注入）；chooseDirectory 的父窗口补 serviceWindow 一级（chooseFile/confirmExternal 不动）。"""
    code = _main_code()
    api_span = _call_span(code, "createShellApi(")
    assert api_span, "main.js 缺 createShellApi 调用"
    assert "onRepoOps" in api_span, "createShellApi 要注入 onRepoOps（建好时交出 {listRepos, selectRepo}）"
    assert "repoOps" in code, "runShellPage 要持 repoOps 变量"
    host_calls = _call_spans(code, "createHost(")
    assert len(host_calls) == 2, f"createHost( 应仍恰好两次（现在是 {len(host_calls)} 次）"
    for mark in ("listRepos", "switchRepo", "addRepo", "pickRepo"):
        assert mark in host_calls[0], f"外壳分支的 createHost 要注入 {mark}"
    for mark in ("listRepos", "switchRepo", "addRepo"):
        assert mark not in host_calls[1], f"带参数分支的 createHost 不注入 {mark}（那里回 unavailable）"
    for prop, want in (("chooseDirectory:", True), ("chooseFile:", False), ("confirmExternal:", False)):
        body = _prop_body(api_span, prop)
        assert body, f"createShellApi 的实参里缺 {prop}"
        has = "serviceWindow" in body
        assert has == want, \
            f"{prop} 的父窗口取法不对：chooseDirectory 依次取 shellWin → settingsWin → serviceWindow → 不带窗口，" \
            "chooseFile 与 confirmExternal 不动（serviceWindow " + ("不许在" if not want else "要在") + "里面）"


def test_s09_main_switch_orchestration():
    """S09 / D07：切换编排——独立函数（不进订阅回调、不进服务窗口收尾）；次序固定
    存盘 → relay.clear() 且 serviceWindow = null → flow.stop() → flow.reset() →
    开 SHELL_START_URL → 关设置窗口与旧服务窗口；首次启动页开不出来写一行 ERROR 并以 1 退出。"""
    code = _main_code()
    rsp = _run_shell_page_body(code)
    si = rsp.find(".selectRepo(")
    assert si >= 0, "切换入口要调 repoOps.selectRepo(…)（先存盘）"
    sub = _call_span(rsp, "flow.subscribe(")
    assert sub, "runShellPage 里仍要有发 SERVICE_STATE_CHANNEL 的订阅"
    assert "selectRepo" not in sub and "flow.reset" not in sub, \
        "切换编排不许写进发 SERVICE_STATE_CHANNEL 的订阅回调"
    closed = rsp.find("tracked.closed.then(async")
    assert closed >= 0, "服务窗口的 tracked.closed.then(async 收尾要还在（T060 S05 取第一处）"
    open_at = rsp.find("(", closed + len("tracked.closed.then"))
    end = _match_bracket(rsp, open_at)
    assert end > 0, "tracked.closed.then( 的括号配不平"
    tail = rsp[closed:end + 1]
    assert "selectRepo" not in tail and "flow.reset" not in tail, \
        "切换编排不许写进服务窗口 tracked.closed.then(async 的收尾"
    c1 = rsp.find("relay.clear()", si)
    assert c1 > si, "存盘过了才 relay.clear()"
    n1 = rsp.find("serviceWindow = null", c1)
    assert n1 > c1, "relay.clear() 之后置 serviceWindow = null"
    s1 = rsp.find("flow.stop()", n1)
    assert s1 > n1, "收尾先 flow.stop()"
    r1 = rsp.find("flow.reset()", s1)
    assert r1 > s1, "stop 之后 reset 回 idle（不经 moveTo）"
    o1 = rsp.find("openShellWindow(", r1)
    assert o1 > r1, "reset 之后才开首次启动页"
    assert "SHELL_START_URL" in rsp[o1:o1 + 220], "切换收尾开的是 SHELL_START_URL（首次启动页）"
    e1 = rsp.find("app.exit(1)", o1)
    assert e1 > o1, "首次启动页开不出来要以 1 退出"
    assert "ERROR" in rsp[o1:e1], "以 1 退出前要往 stderr 写一行 ERROR:"


def test_s10_readme():
    """S10 / D09：README——第 5 行不再把单实例与多仓库切换列进「仍没有」（托盘与「外壳页在本片
    就位」留着）；宿主接口首句「十二个函数」并加三行；createHost 一节「十个函数」；退出码表补
    0/1 两种新情形；冒烟加单实例与切换两条。"""
    text = _shell_read("README.md")
    lines = text.split("\n")
    frame = [line for line in lines if "外壳页在本片就位" in line]
    assert frame, "「外壳页在本片就位」那句要留着（T030/T035/T039/T060 的 needle）"
    assert len(frame) == 1, "「外壳页在本片就位」只在一句里"
    frame_line = frame[0]
    assert "托盘" in frame_line, "「托盘」仍要列在「仍没有」里"
    assert "单实例" not in frame_line, "本片做了单实例，不许再列进「仍没有」"
    assert "多仓库切换" not in frame_line, "本片做了多仓库切换，不许再列进「仍没有」"
    assert "十二个函数" in text, "宿主接口一节的首句要改成「十二个函数」"
    for fn in ("listRepos", "switchRepo", "addRepo"):
        assert f"`{fn}(" in text, f"宿主接口表要加一行 {fn}"
    assert "createHost` 建的十个函数" in text, "「createHost 建的五个函数」要改成「十个函数」"
    zero = one = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("| **0**"):
            zero = stripped
        elif stripped.startswith("| **1**"):
            one = stripped
    assert zero and "第二份" in zero, "退出码表的 0 那行要写「同一 userData 下起的第二份以 0 退出」"
    assert one and "切换" in one, "退出码表的 1 那行要写「切换仓库时首次启动页开不出来」"
    smoke_at = text.find("手工冒烟")
    assert smoke_at >= 0, "「手工冒烟」一节要还在"
    next_head = text.find("\n## ", smoke_at)
    smoke = text[smoke_at:next_head if next_head > 0 else len(text)]
    assert "单实例" in smoke, "冒烟要加一条单实例（同一 userData 再起一份 → 以 0 退出）"
    assert "切换" in smoke, "冒烟要加一条切换（switchRepo → 首次启动页 → 新服务窗口）"


# ---------------------------------------------------------------------------
# P 系列：外壳探针（node --test，被测模块只在探针里 require；行为断言都在探针里）
# ---------------------------------------------------------------------------

PROBE_SETTINGS = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const settings = require("@SHELL@/src/settings.js");

function base() {
  return {
    version: 1,
    repos: [
      { id: "a", name: "a", path: "C:/tmp/a", lastOpened: null },
      { id: "b", name: "b", path: "C:/tmp/b", lastOpened: "2026-01-01T00:00:00.000Z" },
    ],
    currentRepo: "a",
    transcriptDirs: [{ id: "d1", path: "C:/tmp/logs" }],
    theme: "dark",
    density: "standard",
    pythonPath: null,
    kitPath: null,
  };
}
const snap = (value) => JSON.stringify(value);

test("selectRepo 是导出的函数", () => {
  assert.equal(typeof settings.selectRepo, "function", "settings 要导出 selectRepo");
});

test("未知 id 与非字符串 id → {ok:false, reason:\"unknown-repo\"}，入参一个字节不动（D02）", () => {
  for (const bad of ["nope", "", 123, null, undefined, {}, ["a"]]) {
    const src = base();
    const before = snap(src);
    assert.deepEqual(settings.selectRepo(src, bad, 1700000000000),
      { ok: false, reason: "unknown-repo" }, "不认识的 id：" + JSON.stringify(bad));
    assert.equal(snap(src), before, "拒绝时入参不被修改");
  }
});

test("命中：只改 currentRepo 与目标条目的 lastOpened，其余条目与键一字不动，入参不变（D02）", () => {
  const src = base();
  const before = snap(src);
  const at = 1765830000123;
  const r = settings.selectRepo(src, "b", at);
  assert.equal(r.ok, true);
  const next = r.settings;
  assert.equal(next.currentRepo, "b");
  assert.equal(next.repos.find((e) => e.id === "b").lastOpened, new Date(at).toISOString());
  assert.equal(next.repos.find((e) => e.id === "a").lastOpened, null, "别的条目的 lastOpened 不动");
  assert.equal(next.repos.find((e) => e.id === "a").path, "C:/tmp/a", "别的条目的其他字段不动");
  assert.equal(next.theme, "dark");
  assert.equal(next.density, "standard");
  assert.deepEqual(next.transcriptDirs, [{ id: "d1", path: "C:/tmp/logs" }]);
  assert.equal(next.pythonPath, null);
  assert.equal(next.kitPath, null);
  assert.equal(next.version, 1);
  assert.equal(snap(src), before, "入参不被修改");
  assert.notEqual(next, src, "返回的是新对象，不是入参本身");
});

test("lastOpened 是 UTC ISO 串：new Date(at).toISOString()，不读当前时间（at 由参数注入）", () => {
  const r = settings.selectRepo(base(), "a", 0);
  assert.equal(r.settings.repos.find((e) => e.id === "a").lastOpened, "1970-01-01T00:00:00.000Z");
});
'''


def test_p01_settings_select_repo_probe():
    """P01 / D02：settings.selectRepo 纯函数——拒绝不动入参、命中只改两处、ISO 时刻。"""
    _expect_probe_pass("t064-settings-select-repo", PROBE_SETTINGS)


PROBE_SHELLAPI = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { createShellApi } = require("@SHELL@/src/shellapi.js");

function baseSettings() {
  return {
    version: 1,
    repos: [
      { id: "a", name: "a", path: "C:/tmp/a", lastOpened: null },
      { id: "b", name: "b", path: "C:/tmp/b", lastOpened: null },
    ],
    currentRepo: "a",
    transcriptDirs: [],
    theme: "dark",
    density: "standard",
    pythonPath: null,
    kitPath: null,
  };
}

function makeApi(over) {
  const state = { mem: baseSettings(), fail: false, saved: null, detects: 0 };
  const store = {
    load: () => ({ settings: JSON.parse(JSON.stringify(state.mem)), badCopy: null }),
    save: (next) => {
      if (state.fail) throw new Error("disk full");
      state.saved = JSON.parse(JSON.stringify(next));
      state.mem = JSON.parse(JSON.stringify(next));
    },
  };
  const ops = { captured: null };
  const opts = Object.assign({
    store,
    onRepoOps: (handed) => { ops.captured = handed; },
    probe: {
      probePython: async () => null,
      probeKit: async () => null,
      detectPython: async () => { state.detects += 1; return { status: "missing", path: "", version: "" }; },
      detectKit: async () => null,
    },
  }, over || {});
  return { api: createShellApi(opts), state, ops };
}

test("返回成员仍是十个（listRepos/selectRepo 经注入回调交出去，不挂在返回对象上；D03）", () => {
  const { api } = makeApi();
  assert.deepEqual(Object.keys(api).sort(), [
    "getState", "on", "openExternal", "pickKit", "pickPython", "pickRepo",
    "pickTranscriptDir", "restartService", "saveSettings", "startService",
  ]);
});

test("onRepoOps：建好时同步调一次、恰好一次，交出两个函数（D03）", () => {
  const seen = [];
  makeApi({ onRepoOps: (handed) => seen.push(handed) });
  assert.equal(seen.length, 1, "createShellApi 建好时同步调一次（还没 return 就调）");
  assert.deepEqual(Object.keys(seen[0]).sort(), ["listRepos", "selectRepo"]);
  for (const name of Object.keys(seen[0])) assert.equal(typeof seen[0][name], "function", name + " 必须是函数");
});

test("不注入 onRepoOps 也不炸（可选注入）", () => {
  const api = createShellApi({
    store: { load: () => ({ settings: baseSettings(), badCopy: null }), save: () => {} },
    probe: {
      probePython: async () => null,
      probeKit: async () => null,
      detectPython: async () => ({ status: "missing", path: "", version: "" }),
      detectKit: async () => null,
    },
  });
  assert.equal(typeof api.getState, "function");
});

test("listRepos(runningId)：只回 {id,name,current}、不带 path，只有 runningId 那一条 current 为 true（D01）", async () => {
  const { ops } = makeApi();
  const repos = await ops.captured.listRepos("a");
  assert.deepEqual(repos, [
    { id: "a", name: "a", current: true },
    { id: "b", name: "b", current: false },
  ]);
  assert.ok(!repos.some((entry) => "path" in entry), "不许带 path");
  const flipped = await ops.captured.listRepos("b");
  assert.equal(flipped.find((e) => e.id === "b").current, true);
  assert.equal(flipped.find((e) => e.id === "a").current, false);
});

test("listRepos：runningId 不是字符串 → 没有哪一条 current 为 true（没有正在跑的服务）", async () => {
  const { ops } = makeApi();
  for (const weird of [null, undefined, 123, {}, ""]) {
    const repos = await ops.captured.listRepos(weird);
    assert.ok(repos.every((entry) => entry.current === false), "runningId=" + JSON.stringify(weird));
  }
});

test("selectRepo 依次拒：bad-args → unknown-repo → current-repo，都不写盘（D03）", async () => {
  const { ops, state } = makeApi();
  assert.deepEqual(await ops.captured.selectRepo(undefined, "a", 1), { ok: false, reason: "bad-args" });
  assert.deepEqual(await ops.captured.selectRepo("", "a", 1), { ok: false, reason: "bad-args" });
  assert.deepEqual(await ops.captured.selectRepo(123, "a", 1), { ok: false, reason: "bad-args" });
  assert.deepEqual(await ops.captured.selectRepo({}, "a", 1), { ok: false, reason: "bad-args" });
  assert.deepEqual(await ops.captured.selectRepo("nope", "a", 1), { ok: false, reason: "unknown-repo" });
  assert.deepEqual(await ops.captured.selectRepo("a", "a", 1), { ok: false, reason: "current-repo" });
  assert.equal(state.saved, null, "拒绝时一个字节都不写");
});

test("selectRepo 成功：存盘 currentRepo 与 lastOpened，回 {ok:true}，缓存已清（D03）", async () => {
  const { api, ops, state } = makeApi();
  await api.getState();
  assert.equal(state.detects, 1, "夹具本身要先探一次");
  const at = 1765830000456;
  assert.deepEqual(await ops.captured.selectRepo("b", "a", at), { ok: true });
  assert.equal(state.saved.currentRepo, "b", "存盘写的是新 currentRepo");
  assert.equal(state.saved.repos.find((e) => e.id === "b").lastOpened, new Date(at).toISOString());
  const after = await api.getState();
  assert.equal(after.value.settings.currentRepo, "b", "内存设置也换成新的");
  assert.equal(state.detects, 2, "成功之后下一次 getState 要重新探测（dropCache）");
});

test("selectRepo 写盘失败：回 write-failed，内存设置保持原样（D03）", async () => {
  const { api, ops, state } = makeApi();
  state.fail = true;
  assert.deepEqual(await ops.captured.selectRepo("b", "a", 1765830000456), { ok: false, reason: "write-failed" });
  state.fail = false;
  const after = await api.getState();
  assert.equal(after.value.settings.currentRepo, "a", "内存里还是旧值");
});

test("selectRepo 的 at 不是有限数字 → 用 Date.now() 兑底（D03）", async () => {
  const realNow = Date.now;
  const fixed = 1765840000789;
  Date.now = () => fixed;
  try {
    const pair = makeApi();
    for (const weird of [null, "not-a-number", NaN, Infinity]) {
      const r = await pair.ops.captured.selectRepo("b", "a", weird);
      assert.equal(r.ok, true, "at=" + JSON.stringify(weird));
    }
    assert.equal(pair.state.saved.repos.find((e) => e.id === "b").lastOpened,
      new Date(fixed).toISOString(), "兑底的时刻是 Date.now()：" + JSON.stringify(pair.state.saved.repos.find((e) => e.id === "b").lastOpened));
  } finally {
    Date.now = realNow;
  }
});
'''


def test_p02_shellapi_repo_ops_probe():
    """P02 / D03：onRepoOps 同步交出两个函数；listRepos 不带 path；selectRepo 四种拒绝与成功、
    写盘失败内存不变、缓存已清、at 兑底 Date.now()。"""
    _expect_probe_pass("t064-shellapi-repo-ops", PROBE_SHELLAPI)


PROBE_HOST = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { createHost } = require("@SHELL@/src/host.js");

function makeHost(over) {
  return createHost(Object.assign({
    origin: "http://127.0.0.1:1",
    control: "ctrl-tok-t064abc",
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

test("暴露面：十个函数，新三个依次在末尾，前七个照旧（D05）", () => {
  const host = makeHost({
    listRepos: async () => ({ ok: true, repos: [] }),
    switchRepo: async () => ({ ok: true }),
    addRepo: async () => ({ kind: "cancelled" }),
  });
  assert.deepEqual(Object.keys(host), [
    "reauth", "openSecretWindow", "openExternal", "reveal", "notify", "openSettings", "saveTheme",
    "listRepos", "switchRepo", "addRepo",
  ]);
  for (const name of Object.keys(host)) {
    assert.equal(typeof host[name], "function", name + " 必须是函数");
  }
});

test("三个函数没注入 → unavailable（带参数起服务那条分支就是这样；D05）", async () => {
  const host = makeHost();
  assert.deepEqual(await host.listRepos(), { ok: false, reason: "unavailable" });
  assert.deepEqual(await host.switchRepo("b"), { ok: false, reason: "unavailable" });
  assert.deepEqual(await host.addRepo(), { ok: false, reason: "unavailable" });
});

test("listRepos：只取 {id,name,current} 三键，注入物带了 path 也剥掉（D05）", async () => {
  const host = makeHost({ listRepos: async () => ({ ok: true, repos: [
    { id: "a", name: "a", current: true, path: "C:/secret/a" },
    { id: "b", name: "b", current: false, path: "C:/secret/b" },
  ] }) });
  const r = await host.listRepos();
  assert.deepEqual(r, { ok: true, repos: [
    { id: "a", name: "a", current: true },
    { id: "b", name: "b", current: false },
  ] });
  assert.ok(!JSON.stringify(r).includes("C:/secret"), "结果里不许带路径");
});

test("switchRepo：bad-args（undefined/空串/数字/对象）→ 不进注入项（D05）", async () => {
  const calls = [];
  const host = makeHost({ switchRepo: async (...args) => { calls.push(args); return { ok: true }; } });
  for (const bad of [undefined, "", 123, {}]) {
    assert.deepEqual(await host.switchRepo(bad), { ok: false, reason: "bad-args" }, JSON.stringify(bad));
  }
  assert.deepEqual(calls, [], "bad-args 根本不进注入项");
});

test("switchRepo：注入了 → 结果原样回（{ok:true} 与 {ok:false,reason} 两种）", async () => {
  let answer = { ok: true };
  const seen = [];
  const host = makeHost({ switchRepo: async (id) => { seen.push(id); return answer; } });
  assert.deepEqual(await host.switchRepo("b"), { ok: true });
  answer = { ok: false, reason: "current-repo" };
  assert.deepEqual(await host.switchRepo("b"), { ok: false, reason: "current-repo" });
  answer = { ok: false, reason: "write-failed" };
  assert.deepEqual(await host.switchRepo("b"), { ok: false, reason: "write-failed" });
  assert.deepEqual(seen, ["b", "b", "b"], "只转交 id 这一个实参");
});

test("addRepo：外壳信封四种内层形状逐一映射成宿主信封（D05）", async () => {
  let answer;
  const host = makeHost({ addRepo: async () => answer });
  answer = { kind: "cancelled" };
  assert.deepEqual(await host.addRepo(), { ok: false, reason: "cancelled" });
  answer = { kind: "rejected", problem: "not-git" };
  assert.deepEqual(await host.addRepo(), { ok: false, reason: "not-git" });
  answer = { kind: "rejected", problem: "no-agent" };
  assert.deepEqual(await host.addRepo(), { ok: false, reason: "no-agent" });
  answer = { ok: false, reason: "write-failed" };
  assert.deepEqual(await host.addRepo(), { ok: false, reason: "write-failed" });
  answer = { kind: "saved", id: "repo-2" };
  assert.deepEqual(await host.addRepo(), { ok: true, id: "repo-2" });
  answer = { kind: "mystery" };
  assert.deepEqual(await host.addRepo(), { ok: false, reason: "internal" }, "不认识的形状回 internal");
});

test("addRepo：结果不带 path、不带 state（注入物带了也剥掉；D05）", async () => {
  const host = makeHost({ addRepo: async () => ({
    kind: "saved",
    id: "repo-3",
    path: "C:/secret/repo",
    state: { settings: { repos: [{ id: "a", path: "C:/other" }] } },
  }) });
  const r = await host.addRepo();
  const text = JSON.stringify(r);
  assert.ok(!text.includes("C:/secret") && !text.includes("C:/other"), "成功的结果里不许带路径与 state");
  assert.deepEqual(r, { ok: true, id: "repo-3" });
});
'''


def test_p03_host_three_members_probe():
    """P03 / D05：host 的三个新成员——十键序、unavailable、bad-args 不进注入项、
    addRepo 四种映射、结果不带路径与 state。"""
    _expect_probe_pass("t064-host-three-members", PROBE_HOST)


PROBE_HOSTRELAY = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { createHostRelay, HOST_METHODS } = require("@SHELL@/src/hostrelay.js");

test("HOST_METHODS 恰好十项，新三项在末尾（D01）", () => {
  assert.deepEqual([...HOST_METHODS], [
    "reauth", "openSecretWindow", "openExternal", "reveal", "notify", "openSettings", "saveTheme",
    "listRepos", "switchRepo", "addRepo",
  ]);
});

test("三个新函数转给当前 host、实参照传；没有当前 host 回 forbidden（D01）", async () => {
  const relay = createHostRelay();
  assert.deepEqual(await relay.host.listRepos(), { ok: false, reason: "forbidden" }, "没有当前 host 不抛错");
  assert.deepEqual(await relay.host.switchRepo("b"), { ok: false, reason: "forbidden" });
  assert.deepEqual(await relay.host.addRepo(), { ok: false, reason: "forbidden" });
  const calls = [];
  relay.use({
    listRepos: async () => { calls.push("listRepos"); return { ok: true, repos: [{ id: "a", name: "a", current: true }] }; },
    switchRepo: async (id) => { calls.push(["switch", id]); return { ok: true }; },
    addRepo: async () => { calls.push("addRepo"); return { ok: false, reason: "cancelled" }; },
  }, () => true);
  assert.deepEqual(await relay.host.listRepos(),
    { ok: true, repos: [{ id: "a", name: "a", current: true }] });
  assert.deepEqual(await relay.host.switchRepo("b"), { ok: true });
  assert.deepEqual(await relay.host.addRepo(), { ok: false, reason: "cancelled" });
  assert.deepEqual(calls, ["listRepos", ["switch", "b"], "addRepo"]);
  relay.clear();
  assert.deepEqual(await relay.host.switchRepo("b"), { ok: false, reason: "forbidden" }, "clear 之后回到没有 host");
});
'''


def test_p04_hostrelay_probe():
    """P04 / D01：HOST_METHODS 十项、三个新函数的转交与没有 host 的 forbidden 兑底。"""
    _expect_probe_pass("t064-hostrelay-methods", PROBE_HOSTRELAY)


PROBE_IPC = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { HOST_CHANNELS, registerHostIpc } = require("@SHELL@/src/ipc.js");
const { SHELL_CHANNELS } = require("@SHELL@/src/shellipc.js");

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

test("HOST_CHANNELS 恰好十条、冻结、顺序固定（新三条接在 T061 表尾；D01）", () => {
  assert.ok(Object.isFrozen(HOST_CHANNELS), "HOST_CHANNELS 必须冻结");
  assert.deepEqual([...HOST_CHANNELS], HOST_LIST);
});

test("registerHostIpc：十个通道都注册；新三条转交给对应宿主函数、多余实参丢掉（D01）", async () => {
  const handlers = {};
  const registered = [];
  const ipcMain = { handle: (ch, fn) => { handlers[ch] = fn; registered.push(ch); } };
  const calls = [];
  const impl = {
    reauth: async (...a) => { calls.push(["reauth", a]); return { ok: true, via: "reauth" }; },
    openSecretWindow: async (...a) => { calls.push(["openSecretWindow", a]); return { ok: true }; },
    openExternal: async (...a) => { calls.push(["openExternal", a]); return { ok: true }; },
    reveal: async (...a) => { calls.push(["reveal", a]); return { ok: true }; },
    notify: async (...a) => { calls.push(["notify", a]); return { ok: true }; },
    openSettings: async (...a) => { calls.push(["openSettings", a]); return { ok: true }; },
    saveTheme: async (...a) => { calls.push(["saveTheme", a]); return { ok: true }; },
    listRepos: async (...a) => { calls.push(["listRepos", a]); return { ok: true, repos: [{ id: "a", name: "a", current: true }] }; },
    switchRepo: async (...a) => { calls.push(["switchRepo", a]); return { ok: true }; },
    addRepo: async (...a) => { calls.push(["addRepo", a]); return { ok: false, reason: "cancelled" }; },
  };
  let allowed = true;
  registerHostIpc(ipcMain, impl, () => allowed);
  assert.deepEqual(registered, HOST_LIST, "只许注册这十个通道、顺序照表");
  const EV = { sender: {}, senderFrame: { url: "http://127.0.0.1:1/x" } };
  assert.deepEqual(await handlers["themis-host:list-repos"](EV, "EXTRA"),
    { ok: true, repos: [{ id: "a", name: "a", current: true }] });
  assert.deepEqual(calls[calls.length - 1], ["listRepos", []], "list-repos 零实参（多余实参丢掉）");
  assert.deepEqual(await handlers["themis-host:switch-repo"](EV, "b", "EXTRA"), { ok: true });
  assert.deepEqual(calls[calls.length - 1], ["switchRepo", ["b"]], "switch-repo 只转交一个实参");
  assert.deepEqual(await handlers["themis-host:add-repo"](EV, "EXTRA"), { ok: false, reason: "cancelled" });
  assert.deepEqual(calls[calls.length - 1], ["addRepo", []], "add-repo 零实参");
  assert.deepEqual(await handlers["themis-host:reauth"](EV), { ok: true, via: "reauth" }, "既有七条照旧");
  allowed = false;
  calls.length = 0;
  assert.deepEqual(await handlers["themis-host:switch-repo"](EV, "b"), { ok: false, reason: "forbidden" }, "来源不对回 forbidden");
  assert.deepEqual(calls, [], "来源不对根本不进 host");
});

test("host 抛错 → internal，不外传异常（新通道同样适用）", async () => {
  const handlers = {};
  const throwing = {
    reauth: async () => ({}), openSecretWindow: async () => ({}), openExternal: async () => ({}),
    reveal: async () => ({}), notify: async () => ({}), openSettings: async () => ({}), saveTheme: async () => ({}),
    listRepos: async () => { throw new Error("boom"); },
    switchRepo: async () => { throw new Error("boom"); },
    addRepo: async () => { throw new Error("boom"); },
  };
  registerHostIpc({ handle: (ch, fn) => { handlers[ch] = fn; } }, throwing, () => true);
  const EV = { sender: {}, senderFrame: { url: "http://127.0.0.1:1/x" } };
  for (const ch of ["themis-host:list-repos", "themis-host:switch-repo", "themis-host:add-repo"]) {
    assert.deepEqual(await handlers[ch](EV, "b"), { ok: false, reason: "internal" }, ch);
  }
});

test("SHELL_CHANNELS 仍恰好九条、冻结、顺序不变（新三条不进外壳 IPC）", () => {
  assert.ok(Object.isFrozen(SHELL_CHANNELS), "SHELL_CHANNELS 必须冻结");
  assert.deepEqual([...SHELL_CHANNELS], SHELL_LIST);
  for (const ch of ["themis-host:list-repos", "themis-host:switch-repo", "themis-host:add-repo"]) {
    assert.ok(!SHELL_CHANNELS.includes(ch), ch + " 不是外壳通道");
  }
});
'''


def test_p05_ipc_channels_probe():
    """P05 / D01：ipc 十通道的注册、新三条的转交与丢参、来源不对 forbidden、host 抛错 internal；
    外壳通道仍九条。"""
    _expect_probe_pass("t064-ipc-channels", PROBE_IPC)


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
        invoke: async (...args) => { invokes.push(args); return { ok: true, value: { stub: true } }; },
        sendSync: (...args) => { syncs.push(args); return { theme: "light", density: "compact" }; },
        on: (ch, fn) => { (listeners[ch] = listeners[ch] || []).push(fn); },
      },
    };
  };
  const source = fs.readFileSync(path.join(SHELL, "preload.js"), "utf8");
  vm.runInNewContext(source, { require: fakeRequire, module: { exports: {} }, exports: {} });
  return { source, requires, exposes, invokes, syncs, listeners };
}

test("真跑一遍：恰好一次 exposeInMainWorld(themisHost)、键恰好十二个（D01）", () => {
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

test("三个新成员：只把声明的实参转交固定通道，返回信封不拆（D01）", async () => {
  const run = runPreload();
  const api = run.exposes[0][1];
  await api.listRepos();
  await api.switchRepo("repo-b");
  await api.addRepo();
  assert.deepEqual(run.invokes.slice(-3), [
    ["themis-host:list-repos"],
    ["themis-host:switch-repo", "repo-b"],
    ["themis-host:add-repo"],
  ], "实参个数照声明：0 / 1 / 0");
});

test("既有成员照旧：saveTheme 单实参转交、getAppearance 走 sendSync、onAppearance 可订阅退订", async () => {
  const run = runPreload();
  const api = run.exposes[0][1];
  await api.saveTheme("dark");
  assert.deepEqual(run.invokes.slice(-1), [["themis-host:save-theme", "dark"]]);
  const got = api.getAppearance();
  assert.deepEqual(run.syncs, [["themis-host:get-appearance"]]);
  assert.deepEqual(got, { theme: "light", density: "compact" });
  const seen = [];
  const off = api.onAppearance((...args) => seen.push(args));
  run.listeners["themis-host:appearance"][0]({ sender: {} }, { theme: "dark", density: "standard" });
  assert.deepEqual(seen, [[{ theme: "dark", density: "standard" }]]);
  off();
});

test("preload 源码形状：模块级仍恰好一个 ipcRenderer.on、没有 ipcRenderer.send、自包含、注释十二个函数", () => {
  const run = runPreload();
  assert.equal((run.source.match(/ipcRenderer\s*\.\s*on\s*\(/g) || []).length, 1);
  assert.equal((run.source.match(/exposeInMainWorld\s*\(/g) || []).length, 1);
  assert.ok(!/ipcRenderer\s*\.\s*send\s*\(/.test(run.source), "仍不许有 ipcRenderer.send");
  assert.ok(!/require\(\s*['"](\.|node:)/.test(run.source), "仍只 require electron");
  assert.ok(run.source.includes("十二个函数"), "注释要写「十二个函数」");
});
'''


def test_p06_preload_probe():
    """P06 / D01：preload 真跑——十二键、三个新成员转交固定通道（实参 0/1/0）、
    既有成员照旧、模块级仍恰好一个 on、注释十二个函数。"""
    _expect_probe_pass("t064-preload", PROBE_PRELOAD)


PROBE_SERVICEFLOW = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { createServiceFlow } = require("@SHELL@/src/serviceflow.js");

const FAKE = path.join("@SHELL@", "tests", "fixtures", "fake-service.js");

function recordingSpawn() {
  const children = [];
  const fn = (command, args, options) => {
    const child = spawn(command[0], command.slice(1), options);
    children.push(child);
    return child;
  };
  return { fn, children };
}

function envWith(extra) {
  return Object.assign({}, process.env, extra);
}

async function waitFor(what, predicate, timeoutMs) {
  const deadline = Date.now() + (timeoutMs || 8000);
  for (;;) {
    if (predicate()) return;
    if (Date.now() > deadline) throw new Error("等不到：" + what);
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}

function collect() {
  const states = [];
  const infos = [];
  const subscribe = (flow) => flow.subscribe((state, info) => {
    states.push(JSON.parse(JSON.stringify(state)));
    infos.push(info);
  });
  return { states, infos, subscribe };
}

const startArg = (repo) => ({
  repo,
  command: [process.execPath, FAKE],
  env: envWith({ FAKE_SERVICE_MODE: "ok" }),
});

test("reset 是返回对象上的函数", () => {
  const flow = createServiceFlow({});
  assert.equal(typeof flow.reset, "function", "createServiceFlow 要返回 reset");
});

test("idle 下 reset：状态不变、不发通知（D04）", () => {
  const seen = collect();
  const flow = createServiceFlow({});
  seen.subscribe(flow);
  flow.reset();
  assert.deepEqual(flow.state(), { kind: "idle" });
  assert.deepEqual(seen.states, [], "idle 下不许发通知");
});

test("running 下 reset：状态不变、不发通知（D04）", async () => {
  const rec = recordingSpawn();
  const seen = collect();
  const flow = createServiceFlow({ spawn: rec.fn });
  seen.subscribe(flow);
  await flow.start(startArg("r-run"));
  const running = flow.state();
  assert.equal(running.kind, "running");
  const before = seen.states.length;
  flow.reset();
  assert.equal(flow.state(), running, "running 下状态不变");
  assert.equal(seen.states.length, before, "running 下不发通知");
  await flow.stop();
});

test("starting 下 reset：状态不变、不发通知（D04）", async () => {
  const seen = collect();
  const flow = createServiceFlow({ timeoutMs: 400 });
  seen.subscribe(flow);
  const pending = flow.start({
    repo: "r-start",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "silent" }),
  });
  await waitFor("starting", () => flow.state().kind === "starting");
  flow.reset();
  assert.equal(flow.state().kind, "starting", "starting 下状态不变");
  assert.equal(seen.states.filter((s) => s.kind === "idle").length, 0, "starting 下不发通知");
  await pending; // silent + 短超时 → handshake-failed → exited（收尾）
  await waitFor("exited", () => flow.state().kind === "exited");
});

test("exited 下 reset：置 {kind:\"idle\"}，订阅者收 idle 与 info.byShell === false（D04）", async () => {
  const rec = recordingSpawn();
  const seen = collect();
  const flow = createServiceFlow({ spawn: rec.fn });
  seen.subscribe(flow);
  await flow.start(startArg("r-exit"));
  await flow.stop();
  await waitFor("exited", () => flow.state().kind === "exited");
  const before = seen.states.length;
  flow.reset();
  assert.deepEqual(flow.state(), { kind: "idle" }, "exited 是唯一能回 idle 的状态");
  assert.equal(seen.states.length, before + 1, "reset 要通知订阅者");
  assert.deepEqual(seen.states[before], { kind: "idle" });
  assert.equal(seen.infos[before].byShell, false, "reset 的通知带 {byShell:false}");
});

test("reset 之后能再 start 一个新 run（exited → idle → starting → running；D04）", async () => {
  const rec = recordingSpawn();
  const seen = collect();
  const flow = createServiceFlow({ spawn: rec.fn });
  seen.subscribe(flow);
  await flow.start(startArg("first"));
  await flow.stop();
  await waitFor("exited", () => flow.state().kind === "exited");
  flow.reset();
  assert.equal(flow.state().kind, "idle");
  const again = await flow.start(startArg("second"));
  assert.deepEqual(again, { ok: true, value: null });
  assert.equal(flow.state().kind, "running");
  assert.equal(flow.state().repo, "second");
  await flow.stop();
});
'''


def test_p07_serviceflow_reset_probe():
    """P07 / D04：reset 只在 exited 时回 idle（以 {byShell:false} 通知）；idle/starting/running
    下不动不发；reset 之后能再 start 新 run（用 tests/fixtures/fake-service.js）。"""
    _expect_probe_pass("t064-serviceflow-reset", PROBE_SERVICEFLOW)
