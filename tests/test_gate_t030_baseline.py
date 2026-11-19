"""T030 战前门禁：桌面端外壳第 4 片「外壳页窗口、专用 preload 与无参数启动」的黑盒基准测试
（合同 t030-desktop-shell-window v1，基线 0af7a5e——shell-preload.js、src/launch.js、src/shellprotocol.js、
src/shellipc.js 与四份新测试文件、tests/fixtures/fake-late-output.js 都还不存在，main.js 没有外壳分支）。

被测对象：``src/launch.js``（launchMode 的启动分支判定）、``src/shellprotocol.js``（``themis-shell://app/``
协议：常量、isShellPageUrl、resolveShellAsset 的定位与拒绝规则、MIME 表、CSP 与 nosniff 头）、
``src/shellipc.js``（SHELL_CHANNELS 恰好九个、registerShellIpc 只用 handle、来源三条件、
forbidden/internal 信封、多余实参丢弃）、顶层 ``shell-preload.js``（只暴露 ``window.themisShell`` 十个成员、
拆信封、reject 只进 Error.message）、``src/detect.js`` 的两处修复（相对 kitPath 回绝对路径、runProcess 在
close 取输出）与 ``main.js`` 的外壳分支接线（协议特权、分区 session 上的 handler、registerShellIpc、
launchMode 在 runShell 之前）。

基线（0af7a5e）上这些文件与符号都不存在，所以失败都落在「文件不存在」「标记不在」与探针子进程退出码非 0
这类断言上，不是收集失败：模块级只导入标准库，仓库文件的读取与探针的运行都发生在用例函数里。探针是
自包含的 ``node --test`` 文件（Node 24 自带，不需要 npm ci，也不 require electron——electron 44.9.0 没有
postinstall，本片门禁与执行端都不下载本体）。Python 把探针源码写进系统临时目录、以仓库根为 cwd 运行、
用完即删；探针里的被测模块用绝对路径 require（``@SHELL@`` 占位符替换），类型文件用 ``@THEMIS_TS@``、
``@HEADERS_TS@`` 占位符替换。

结构（编号对应合同 DoD 的 D01–D11）：

- 静态断言（``test_s*``，不需要任何依赖）：
  - S01/D10：合同 Scope 点名的 9 个新文件都在位（只断言「在位」，不断言「只有这些」）。
  - S02/D08/D09/D11：``package.json`` 只许改 ``scripts.test``——tap 开关仍在文件清单之前、显式列出
    ``tests/`` 下每一个 ``*.test.js``（数据驱动）且本片四个新测试点名在列、16 份既有测试一条没删没改名、
    ``tests/fixtures/`` 下没有 ``*.test.js``；其余字段（name/main/version/type/start）与依赖、锁文件不动。
  - S03/D07：静态扫描（把顶层 ``shell-preload.js`` 纳入扫描范围，接替 T028 的 test_transitional_s04）——
    ``require('electron')`` 只许 main.js、preload.js、shell-preload.js 三个文件；``ipcMain.on`` 与
    ``ipcRenderer.send`` 在 desktop/shell 下全禁（任何 .js、包括测试与夹具）；两个 preload 都不许 require
    相对路径或 ``node:`` 模块；shell-preload.js 必须 require electron、``exposeInMainWorld`` 恰好一次且名字
    ``themisShell``、不出现 ``themisHost``；``main.js`` 与 ``src/**`` 里不许出现 ``fetch(``（含 ``net.fetch(``）、
    ``net.request``、``persist:``、``shell: true``、写文件函数（注释也算；src/settings.js 的既有豁免不动），
    detect.js 与 shellapi.js 一个写函数都不许）、autoUpdater、crashReporter；dialog、shell.openExternal、
    showItemInFolder、Notification 只许 main.js。
  - S04/D06：main.js 接线——``registerSchemesAsPrivileged`` 恰好一次、在 ``app.whenReady`` 之前、
    privileges 只含 standard/secure（不许 supportFetchAPI/corsEnabled）；``new BrowserWindow`` 恰好一处；
    裸的模块级 ``protocol.handle(`` 禁止、每一处 ``.protocol.handle(`` 附近要有 ``fromPartition``（协议
    handler 必须注册在分区 session 的 protocol 上）；T025/T026 钉住的接线标记一个不能丢；外壳分支的新接线
    （launchMode 在 runShell 调用之前、require 三个新模块、registerShellIpc、isShellPageUrl、
    resolveShellAsset、new Response、shell-preload.js、SHELL_START_URL、trackWindow、app.exit(1)、ERROR）；
    服务分支的 runShell 调用形状（argv/io/openWindow/onServiceReady/env）不变。
  - S05/D08：README 新增「## 外壳页」一节（起步地址、产物目录、构建命令、themisShell、桩数据说明、
    standard/secure、404、通道表、「外壳页在本片就位」那句改写）；T025/T026/T028 的既有字样由各自的
    门禁在 R01 里继续钉住，这里不重复抄清单。
- 探针断言（``test_p*``，跑 node --test）：
  - P01/D01：launchMode——空数组/非数组 → shell；``--repo``（含 ``--repo=…``、任意位置、不带值）→ service；
    只有别的参数（``--kit x``、``--repox``）→ shell。
  - P02/D02：shellprotocol——常量逐字（SHELL_SCHEME/SHELL_HOST/SHELL_START_URL）；isShellPageUrl 的正例与
    反例（javascript:、http/https、file:、别的主机、带端口、带 userinfo、反斜杠主机、空串）；resolveShellAsset
    的 200 用例（九种扩展名的 Content-Type 逐字、CSP 逐字等于 headers.ts 的 CSP 常量、nosniff、body 是
    Buffer 且逐字节相等、path 是 root 内的绝对路径）；404 用例（未知扩展名、目录、不存在、协议/主机/端口/
    userinfo 不合格、反斜杠、NUL、冒号、``%252e`` 解码后仍含 %）；越界用例按站主实测结论写成性质断言
    （回 200 的读到的文件都在 root 之内，不断言「因含 .. 而 404」）；junction 目录链接指向 root 外 → 404
    （系统不给建链接就跳过该条）。
  - P03/D03：shellipc——SHELL_CHANNELS 冻结、恰好九个、名字与顺序逐字；注册只用 handle、恰好九个通道；
    来源不对回 forbidden 且不进 api；每个通道转交的方法名与实参个数、多余实参丢弃；api 同步/异步抛错都回
    internal 且不带错误消息；成功原样回 ``{ok:true,value}``；shellSenderAllowed 的三条件（sender 一致、
    frame 非空、frame 地址是外壳页）与四种反例。
  - P04/D04：shell-preload（vm 加假 electron，测试文件里不出现 require electron 字面串）——只 require
    electron；恰好一次 expose 且名字 themisShell；成员名集合等于从 themisShell.ts 解析出的
    ``interface ThemisShell`` 成员（从 .ts 解析，不另抄键表）；九个方法各用一条通道、合起来恰好等于
    SHELL_CHANNELS；每个方法只转发声明的实参；信封 ok 时 resolve value、否则以带 reason 的 Error reject
    （reason 只进 Error.message，不挂别的属性）；on 同步返回退订函数、不发 IPC、不注册监听；源文本没有
    ipcRenderer.send、ipcRenderer.on、相对路径或 node: 的 require。
  - P05/D05：detect 两处修复——相对 kitPath 的 detectKit 回绝对路径且等于 path.resolve(kitDir, scripts,
    pi_dispatch.py)；「输出在退出之后才到」用真夹具（孙进程 detached）验证 runProcess 要在 close 里取输出；
    ENOENT 与超时两条既有路径照旧。

合同没有写死、门禁端按最合理读法定下的地方（交付信「下游须知」逐条列出）：响应头名比较大小写不敏感
（合同只钉了三个头的名字与取值，没钉大小写）；README 的断言只落在本片新增的「外壳页」内容上（那句
「没有外壳页」的改写按「新句子在位」断言，不断言旧句子不存在）；main.js 的「handler 注册在分区 session
上」用文本近似（禁裸 ``protocol.handle(``、每处 ``.protocol.handle(`` 前 160 字符内要有 fromPartition）；
「launchMode 判定在 runShell 之前」同样用首次出现位置近似。
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL = REPO_ROOT / "desktop" / "shell"
THEMIS_TS = REPO_ROOT / "desktop" / "web" / "src" / "shellpages" / "themisShell.ts"
HEADERS_TS = REPO_ROOT / "ts" / "packages" / "ui" / "src" / "localhttp" / "headers.ts"

# 合同 Scope 点名的新文件（只断言「在位」，不断言「只有这些」——后面的片会继续往 desktop/shell 加文件）
CONTRACT_FILES = (
    "shell-preload.js",
    "src/launch.js", "src/shellprotocol.js", "src/shellipc.js",
    "tests/launch.test.js", "tests/shellprotocol.test.js", "tests/shellipc.test.js", "tests/shellpreload.test.js",
    "tests/fixtures/fake-late-output.js",
)

# 本片新增的四份测试文件：scripts.test 必须显式点名（D08）
NEW_TEST_FILES = (
    "tests/launch.test.js", "tests/shellprotocol.test.js", "tests/shellipc.test.js", "tests/shellpreload.test.js",
)

# T025/T026/T028 已有的 16 份测试文件：一条也没删没改名（D09/D11）
PREEXISTING_TEST_FILES = (
    "tests/args.test.js", "tests/package.test.js", "tests/python.test.js", "tests/handshake.test.js",
    "tests/service.test.js", "tests/window.test.js", "tests/core.test.js", "tests/control.test.js",
    "tests/host.test.js", "tests/hostcheck.test.js", "tests/ipc.test.js", "tests/preload.test.js",
    "tests/settings.test.js", "tests/detect.test.js", "tests/shellapi.test.js", "tests/shellshape.test.js",
)

REQUIRE_ELECTRON_RE = re.compile(r"require\(\s*['\"]electron['\"]\s*\)")
REQUIRE_RELATIVE_RE = re.compile(r"""require\(\s*['"]\.""")
REQUIRE_NODE_RE = re.compile(r"""require\(\s*['"]node:""")

# T025 的 7 条禁令（站主收窄后）：src/** 与 main.js 里不许出现，注释也不行；src/settings.js 只许
# writeFileSync/renameSync/mkdirSync/unlinkSync 四个（T028 起的豁免），detect.js 与 shellapi.js 一个都不许
SRC_FORBIDDEN = (
    (re.compile(r"persist:"), "persist: 前缀"),
    (re.compile(r"shell\s*:\s*true"), "shell: true"),
    (re.compile(r"\b(writeFile|writeFileSync|appendFile|appendFileSync|mkdir|mkdirSync|rm|rmSync|unlink|unlinkSync|rename|renameSync)\s*\("), "fs 写函数"),
    (re.compile(r"\bfetch\s*\("), "fetch"),
    (re.compile(r"\bnet\.request\b"), "net.request"),
    (re.compile(r"\bautoUpdater\b"), "autoUpdater"),
    (re.compile(r"\bcrashReporter\b"), "crashReporter"),
)
SETTINGS_JS_REL = "src/settings.js"
NARROWED_WRITE_RE = re.compile(r"\b(writeFile|appendFile|appendFileSync|mkdir|rm|rmSync|unlink|rename)\s*\(")

# 「只在 X」的词面规则（合同第七节）：只扫 main.js 与 src/**（tests/** 的注释文字不误伤）
WORD_RULES = (
    (re.compile(r"\bshell\s*\.\s*openExternal\b"), "shell.openExternal", ("main.js",)),
    (re.compile(r"\bshowItemInFolder\b"), "showItemInFolder", ("main.js",)),
    (re.compile(r"\bdialog\b"), "dialog", ("main.js",)),
    (re.compile(r"\bNotification\b"), "Notification", ("main.js",)),
)

# require('electron') 的三个文件白名单（合同第七节：T030 起 shell-preload.js 进白名单）
ELECTRON_ALLOWED = ("main.js", "preload.js", "shell-preload.js")
IPC_BANS = (
    (re.compile(r"\bipcRenderer\s*\.\s*send\b"), "ipcRenderer.send"),
)

# ipcMain.on：片 A（T061）起只许出现在 main.js，且注册的通道只许那两个外观读取字面量（T061 放开的口）
IPC_MAIN_ON_RE = re.compile(r"\bipcMain\s*\.\s*on\s*\(")
ALLOWED_SYNC_CHANNEL_ARGS = (
    "HOST_APPEARANCE_CHANNEL",
    '"themis-host:get-appearance"',
    "SHELL_APPEARANCE_CHANNEL",
    '"themis-shell:get-appearance"',
)

# main.js 的既有接线标记（合同第六节：T025/T026 钉住的一个都不能丢）
MAIN_WIRING_MARKERS = (
    (r"setApplicationMenu\s*\(\s*null\s*\)", "setApplicationMenu(null)"),
    (r"session\.fromPartition", "session.fromPartition"),
    (r"webPreferences\s*\(", "webPreferences("),
    (r"\bmainWebPreferences\b", "mainWebPreferences"),
    (r"\bipcMain\b", "ipcMain"),
    (r"\bsenderAllowed\b", "senderAllowed"),
    (r"\bisServiceUrl\b", "isServiceUrl"),
    (r"\bloadURL\b", "loadURL"),
    (r"will-navigate", "will-navigate"),
    (r"['\"]deny['\"]", "deny"),
    (r"shell\s*\.\s*openExternal", "shell.openExternal"),
    (r"\bshowItemInFolder\b", "showItemInFolder"),
    (r"\bshowMessageBox\b", "showMessageBox"),
    (r"\bNotification\b", "Notification"),
    (r"preload\.js", "preload.js"),
    (r"__dirname", "__dirname"),
    (r"app\.isPackaged", "app.isPackaged"),
    (r"slice\(1\)", "slice(1)"),
    (r"slice\(2\)", "slice(2)"),
    (r"\bapp\.exit\b", "app.exit"),
    (r"\brunShell\b", "runShell"),
    (r"\btrackWindow\s*\(", "trackWindow("),
)

# 服务分支的既有 require（T025/T026 同款，容忍省略 .js 后缀）
MAIN_IMPORT_PATTERNS = (
    (re.compile(r"""require\(\s*['"]\.\/src\/core(\.js)?['"]\s*\)"""), "./src/core.js（runShell 的来源）"),
    (re.compile(r"""require\(\s*['"]\.\/src\/window(\.js)?['"]\s*\)"""), "./src/window.js（webPreferences 的来源）"),
)

# 外壳分支的新接线（合同第六节）：三个新模块必须真的被 require，否则纯模块成了死代码
SHELL_IMPORT_PATTERNS = (
    (re.compile(r"""require\(\s*['"]\.\/src\/launch(\.js)?['"]\s*\)"""), "./src/launch.js（launchMode 的来源）"),
    (re.compile(r"""require\(\s*['"]\.\/src\/shellprotocol(\.js)?['"]\s*\)"""), "./src/shellprotocol.js（resolveShellAsset/isShellPageUrl 的来源）"),
    (re.compile(r"""require\(\s*['"]\.\/src\/shellipc(\.js)?['"]\s*\)"""), "./src/shellipc.js（registerShellIpc 的来源）"),
)
SHELL_WIRING_MARKERS = (
    (r"\blaunchMode\s*\(", "launchMode("),
    (r"\bregisterShellIpc\s*\(", "registerShellIpc("),
    (r"\bisShellPageUrl\b", "isShellPageUrl"),
    (r"\bresolveShellAsset\s*\(", "resolveShellAsset("),
    (r"new\s+Response\s*\(", "new Response("),
    (r"shell-preload\.js", "shell-preload.js"),
    (r"SHELL_START_URL|themis-shell://app/index\.html#/first-run", "SHELL_START_URL（或起步地址字面量）"),
    (r"app\.exit\(1\)", "app.exit(1)（外壳产物缺失以 1 退出）"),
    (r"ERROR", "ERROR（外壳产物缺失往 stderr 写一行 ERROR）"),
)

# README：本片新增「外壳页」一节的要点（D08）
README_T030_NEEDLES = (
    "## 外壳页",
    "themis-shell://app/index.html#/first-run",
    "desktop/web/dist",
    "npm --prefix ../web run build",
    "themisShell",
    "桩数据",
    "standard",
    "secure",
    "404",
    "themis-shell:get-state",
    "外壳页在本片就位",
)


def _shell_read(rel: str) -> str:
    p = SHELL / rel
    assert p.is_file(), f"desktop/shell/{rel} 不存在"
    return p.read_text(encoding="utf-8")


def _scan_files():
    """扫描范围：顶层 main.js / preload.js / shell-preload.js + src/** + tests/**（与 T025/T026/T028 相比
    只多了顶层 shell-preload.js——这正是本片接替 T028 过渡扫描的地方）。"""
    files = []
    for rel in ELECTRON_ALLOWED:
        p = SHELL / rel
        if p.is_file():
            files.append(p)
    if (SHELL / "src").is_dir():
        files += sorted((SHELL / "src").rglob("*.js"))
    if (SHELL / "tests").is_dir():
        files += sorted((SHELL / "tests").rglob("*.js"))
    return files


def _run_probe(name: str, source: str, timeout: float = 300.0) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    assert node, "本机没有 node，无法运行门禁探针"
    with tempfile.TemporaryDirectory(prefix="t030-gate-") as td:
        probe = Path(td) / f"{name}.test.js"
        probe.write_text(source, encoding="utf-8")
        return subprocess.run(
            [node, "--test", str(probe)],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )


def _expect_probe_pass(name: str, template: str) -> None:
    source = template.replace("@SHELL@", json.dumps(str(SHELL))[1:-1])
    source = source.replace("@THEMIS_TS@", json.dumps(str(THEMIS_TS))[1:-1])
    source = source.replace("@HEADERS_TS@", json.dumps(str(HEADERS_TS))[1:-1])
    proc = _run_probe(name, source)
    assert proc.returncode == 0, (
        f"探针 {name} 没有全绿（退出码 {proc.returncode}）：\n"
        f"--- stdout 末尾 ---\n{proc.stdout[-5000:]}\n--- stderr 末尾 ---\n{proc.stderr[-2000:]}"
    )


def _call_arg_text(text: str, pos: int) -> str:
    """从 pos 起截取第一个 ``f(...)`` 调用的括号内文本（深度配平；这里扫描的调用里不会出现括号字符串）。"""
    start = text.find("(", pos)
    assert start != -1, "调用后面没有左括号"
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    raise AssertionError("括号没有配平")


# --------------------------------------------------------------------------- 静态断言

def test_s01_contract_files():
    """D10/Scope：合同点名的 9 个新文件都在位。"""
    for rel in CONTRACT_FILES:
        assert (SHELL / rel).is_file(), f"desktop/shell/{rel} 不存在"


def test_s02_package_json_and_lock():
    """D08/D09/D11：package.json 只许改 scripts.test（tap 开关、点名四个新测试、数据驱动全量点名、
    既有 16 份一条没删），其余字段、依赖与锁文件不动；夹具目录里不许有 *.test.js。"""
    pkg = json.loads(_shell_read("package.json"))
    assert pkg.get("name") == "themistally-desktop-shell"
    assert pkg.get("private") is True
    assert pkg.get("version") == "0.0.0"
    assert pkg.get("type") == "commonjs"
    assert pkg.get("main") == "main.js"
    assert pkg["scripts"].get("start") == "electron ."
    assert pkg.get("devDependencies") == {"electron": "44.9.0"}, (
        f"devDependencies 必须仍是 {{\"electron\": \"44.9.0\"}}：{pkg.get('devDependencies')}"
    )
    assert pkg.get("dependencies") in (None, {}), "dependencies 必须为空"
    lock = json.loads(_shell_read("package-lock.json"))
    assert lock["packages"][""]["devDependencies"]["electron"] == "44.9.0"
    assert lock["packages"]["node_modules/electron"]["version"] == "44.9.0"
    test_cmd = pkg["scripts"]["test"]
    tap_at = test_cmd.find("--test-reporter=tap")
    files_at = test_cmd.find("tests/")
    assert tap_at != -1, f"scripts.test 必须带 --test-reporter=tap：{test_cmd!r}"
    assert files_at == -1 or tap_at < files_at, f"--test-reporter=tap 要写在文件清单之前：{test_cmd!r}"
    listed = set(re.findall(r"tests[/\\][\w.-]+\.test\.js", test_cmd))
    actual = {f"tests/{p.name}" for p in (SHELL / "tests").glob("*.test.js")}
    assert actual, "tests/ 下没有 *.test.js"
    missing = actual - listed
    assert not missing, f"scripts.test 没有显式列出：{sorted(missing)}"
    for rel in NEW_TEST_FILES:
        assert rel in listed, f"scripts.test 必须显式列出本片新增的{rel}：{test_cmd!r}"
    for rel in PREEXISTING_TEST_FILES:
        assert (SHELL / rel).is_file(), f"既有测试被删了：desktop/shell/{rel}"
        assert rel in listed, f"scripts.test 不再点名既有测试 {rel}：{test_cmd!r}"
    for p in (SHELL / "tests" / "fixtures").glob("*.test.js"):
        assert False, f"夹具不能叫 *.test.js：{p.name}"


def test_s03_static_scan():
    """D07（含接替 T028 的 test_transitional_s04 的扫描）：require('electron') 只许 main.js、preload.js、
    shell-preload.js 三个文件（顶层 shell-preload.js 从本片起进扫描范围）；ipcMain.on 与 ipcRenderer.send
    在 desktop/shell 下全禁；两个 preload 自包含（不 require 相对路径或 node: 模块）；shell-preload.js
    恰好一次 exposeInMainWorld 且名字 themisShell、不出现 themisHost；main.js 与 src/** 里没有
    fetch(/net.request/persist:/shell: true/写函数/autoUpdater/crashReporter（注释也算；src/settings.js
    只保留既有豁免）；dialog、shell.openExternal、showItemInFolder、Notification 只许 main.js。"""

    shell_preload = _shell_read("shell-preload.js")  # 基线上还不存在 → 本条先红
    files = _scan_files()
    assert files, "desktop/shell 扫描范围内没有 .js 文件"
    for f in files:
        rel = str(f.relative_to(SHELL)).replace("\\", "/")
        text = f.read_text(encoding="utf-8")
        m = REQUIRE_ELECTRON_RE.search(text)
        if m and rel not in ELECTRON_ALLOWED:
            raise AssertionError(
                f"desktop/shell/{rel} 出现 require('electron')，只许 {list(ELECTRON_ALLOWED)}："
                f"…{text[max(0, m.start() - 40):m.end() + 40]}…"
            )
        for pat, what in IPC_BANS:
            m = pat.search(text)
            if m:
                raise AssertionError(
                    f"desktop/shell/{rel} 出现全禁的「{what}」："
                    f"…{text[max(0, m.start() - 40):m.end() + 40]}…"
                )
        # ipcMain.on 只许 main.js 有，且注册的通道只许那两个外观读取字面量
        for m in IPC_MAIN_ON_RE.finditer(text):
            if rel != "main.js":
                raise AssertionError(
                    f"desktop/shell/{rel} 不许出现 ipcMain.on（只许 main.js 的外观读取）："
                    f"…{text[max(0, m.start() - 40):m.end() + 40]}…"
                )
            open_at = text.find("(", m.start())
            first_arg = text[open_at + 1:].split(",")[0].strip()
            if first_arg not in ALLOWED_SYNC_CHANNEL_ARGS:
                raise AssertionError(
                    f"main.js 的 ipcMain.on 通道只许那两个外观读取字面量，却见到：{first_arg}"
                )

    product_files = [SHELL / "main.js"] + sorted((SHELL / "src").rglob("*.js"))
    assert product_files, "desktop/shell 的 main.js 或 src/** 不存在"
    for f in product_files:
        rel = str(f.relative_to(SHELL)).replace("\\", "/")
        text = f.read_text(encoding="utf-8")
        for pat, what in SRC_FORBIDDEN:
            if what == "fs 写函数" and rel == SETTINGS_JS_REL:
                pat = NARROWED_WRITE_RE
            m = pat.search(text)
            assert m is None, (
                f"desktop/shell/{rel} 出现禁令「{what}」：…{text[max(0, m.start() - 40):m.end() + 40]}…"
            )
        for pat, what, allowed in WORD_RULES:
            m = pat.search(text)
            if m and rel not in allowed:
                raise AssertionError(
                    f"desktop/shell/{rel} 出现只许在 {list(allowed)} 的「{what}」："
                    f"…{text[max(0, m.start() - 40):m.end() + 40]}…"
                )

    # 两个 preload 的自包含与暴露面
    for rel in ("preload.js", "shell-preload.js"):
        text = _shell_read(rel)
        assert REQUIRE_ELECTRON_RE.search(text), f"desktop/shell/{rel} 必须 require('electron')"
        assert not REQUIRE_RELATIVE_RE.search(text), f"desktop/shell/{rel} 不许 require 相对路径（自包含）"
        assert not REQUIRE_NODE_RE.search(text), f"desktop/shell/{rel} 不许 require node: 模块"
    assert len(re.findall(r"exposeInMainWorld", shell_preload)) == 1, (
        "shell-preload.js 的 exposeInMainWorld 只许出现一次"
    )
    assert re.search(r"""exposeInMainWorld\s*\(\s*['"]themisShell['"]""", shell_preload), (
        "shell-preload.js 的 exposeInMainWorld 名字必须是 themisShell"
    )
    assert "themisHost" not in shell_preload, "shell-preload.js 不许暴露 themisHost"


def test_s04_main_js_wiring():
    """D06：main.js 接线——协议特权只注册一次且在 whenReady 之前、privileges 只 standard/secure、
    new BrowserWindow 恰好一处、协议 handler 注册在分区 session 上、launchMode 判定在 runShell 之前、
    既有标记一个不丢、服务分支的 runShell 调用形状不变。"""
    text = _shell_read("main.js")

    # 协议特权：恰好一次、在 whenReady 之前、privileges 只 standard/secure
    calls = list(re.finditer(r"registerSchemesAsPrivileged\s*\(", text))
    assert len(calls) == 1, f"registerSchemesAsPrivileged 必须恰好调用一次：找到 {len(calls)} 处"
    arg = _call_arg_text(text, calls[0].start())
    ready_at = text.find("whenReady")
    assert ready_at != -1, "main.js 缺 app.whenReady"
    assert calls[0].start() < ready_at, "registerSchemesAsPrivileged 必须在 app.whenReady 之前（顶层）"
    assert re.search(r"""['"]themis-shell['"]""", arg), "registerSchemesAsPrivileged 的 scheme 必须是 themis-shell"
    assert "supportFetchAPI" not in arg and "corsEnabled" not in arg, "privileges 不许加 supportFetchAPI/corsEnabled"
    pm = re.search(r"privileges\s*:\s*\{([^{}]*)\}", arg)
    assert pm is not None, "registerSchemesAsPrivileged 里找不到 privileges 对象"
    keys = set(re.findall(r"(\w+)\s*:", pm.group(1)))
    assert keys == {"standard", "secure"}, f"privileges 只许 standard/secure：{sorted(keys)}"

    # new BrowserWindow 恰好一处（T026 同款）
    assert len(re.findall(r"new\s+BrowserWindow", text)) == 1, "main.js 的 new BrowserWindow 必须恰好一处"

    # 协议 handler：不许注册在模块级 protocol 上（裸 protocol.handle(），必须挂在 fromPartition 的 session 上
    assert not re.search(r"(?<![.\w])protocol\s*\.\s*handle\s*\(", text), (
        "protocol.handle 不许注册在模块级 protocol 上（会 ERR_FAILED）——要注册在 session.fromPartition 的"
        " session.protocol 上"
    )
    chained = list(re.finditer(r"\.\s*protocol\s*\.\s*handle\s*\(", text))
    assert chained, "main.js 没有把协议 handler 注册在任何 session 的 protocol 上"
    for m in chained:
        window = text[max(0, m.start() - 160) : m.start()]
        assert "fromPartition" in window, (
            "协议 handler 必须注册在 session.fromPartition 得到的 session 的 protocol 上，"
            f"这一处的前文里没有 fromPartition：…{window[-80:]}"
        )

    # T025/T026 的既有标记一个不能丢
    for pattern, what in MAIN_WIRING_MARKERS:
        assert re.search(pattern, text), f"main.js 缺接线标记：{what}"
    for pat, what in MAIN_IMPORT_PATTERNS:
        assert pat.search(text), f"main.js 没有 require {what}"

    # 外壳分支的新接线
    for pattern, what in SHELL_WIRING_MARKERS:
        assert re.search(pattern, text), f"main.js 缺外壳分支的接线标记：{what}"
    for pat, what in SHELL_IMPORT_PATTERNS:
        assert pat.search(text), f"main.js 没有 require {what}，src 的纯模块成了死代码"
    launch_at = text.find("launchMode(")
    run_at = text.find("runShell(")
    assert launch_at != -1 and run_at != -1, "main.js 缺 launchMode( 或 runShell( 的调用"
    assert launch_at < run_at, "launchMode 的判定必须发生在调用 runShell 之前"

    # 服务分支的调用形状：runShell({...}) 仍收这五个键
    run_arg = _call_arg_text(text, run_at)
    for key in ("argv", "io", "openWindow", "onServiceReady", "env"):
        assert re.search(rf"\b{key}\b", run_arg), f"runShell 的调用仍要收 {key}：{run_arg[:200]!r}"


def test_s05_readme_shell_page():
    """D08：README 新增「外壳页」一节且要点齐全（起步地址、产物目录与构建命令、themisShell 与桩数据、
    privileges、404、通道表、开头那句改写）。T025/T026/T028 的既有字样由各自门禁在 R01 里继续钉住。"""
    text = _shell_read("README.md")
    for needle in README_T030_NEEDLES:
        assert needle in text, f"README 缺本片要点「{needle}」"


# --------------------------------------------------------------------------- 探针断言（node --test）

PROBE_LAUNCH = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { launchMode } = require("@SHELL@/src/launch.js");

test("空数组 → shell", () => {
  assert.equal(launchMode([]), "shell");
});

test("带齐三项 → service", () => {
  assert.equal(launchMode(["--repo", "r", "--kit", "k", "--assets", "a"]), "service");
});

test("--repo=… → service", () => {
  assert.equal(launchMode(["--repo=x"]), "service");
});

test("--repo 在任意位置（含前面有 electron 与 . 的真实形状）→ service", () => {
  assert.equal(launchMode(["electron.exe", ".", "--repo", "r"]), "service");
  assert.equal(launchMode(["--kit", "k", "--repo"]), "service");
});

test("只有别的参数 → shell", () => {
  assert.equal(launchMode(["--kit", "k"]), "shell");
  assert.equal(launchMode(["--assets", "a", "--python", "py"]), "shell");
  assert.equal(launchMode(["--repox"]), "shell");
  assert.equal(launchMode(["--repo-x", "1"]), "shell");
});

test("非数组按空数组处理 → shell", () => {
  for (const v of [null, undefined, "x", 123, {}]) {
    assert.equal(launchMode(v), "shell", JSON.stringify(v));
  }
});
'''


PROBE_PROTOCOL = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const proto = require("@SHELL@/src/shellprotocol.js");

// CSP 的唯一出处是 ts/packages/ui/src/localhttp/headers.ts 的 CSP 常量（逐字相等，不另抄一份）
const headersTs = fs.readFileSync("@HEADERS_TS@", "utf8");
const cpm = headersTs.match(/export const CSP =\s*"([^"]+)"/);
assert.ok(cpm, "headers.ts 里解析不出 CSP 常量");
const CSP = cpm[1];

function makeRoot() {
  const base = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t030-proto-")));
  const root = path.join(base, "root");
  fs.mkdirSync(path.join(root, "assets"), { recursive: true });
  fs.mkdirSync(path.join(root, "licenses"), { recursive: true });
  fs.writeFileSync(path.join(root, "index.html"), "<!doctype html><html>shell-index</html>\n");
  fs.writeFileSync(path.join(root, "assets", "app.js"), "console.log(1);\n");
  fs.writeFileSync(path.join(root, "assets", "app.css"), "body{color:red}\n");
  fs.writeFileSync(path.join(root, "assets", "f.woff2"), Buffer.from([0, 0, 1, 2]));
  fs.writeFileSync(path.join(root, "assets", "i.svg"), "<svg/>");
  fs.writeFileSync(path.join(root, "assets", "l.png"), Buffer.from([137, 80, 78, 71]));
  fs.writeFileSync(path.join(root, "assets", "fav.ico"), Buffer.from([0, 1, 2]));
  fs.writeFileSync(path.join(root, "data.json"), "{}\n");
  fs.writeFileSync(path.join(root, "licenses", "readme.txt"), "license text\n");
  // 越界目标：root 外的同名内容，读得到就算越界
  fs.writeFileSync(path.join(base, "secret.txt"), "SECRET-OUTSIDE");
  return { base, root };
}

function headerOf(headers, name) {
  const target = name.toLowerCase();
  for (const k of Object.keys(headers || {})) {
    if (k.toLowerCase() === target) return headers[k];
  }
  return undefined;
}

function assertInside(rootReal, p) {
  assert.ok(typeof p === "string" && path.isAbsolute(p), "200 的 path 必须是绝对路径：" + JSON.stringify(p));
  const rel = path.relative(rootReal, p);
  assert.ok(rel !== "" && rel !== ".." && !rel.startsWith(".." + path.sep) && !path.isAbsolute(rel),
    "读到的文件要在 root 之内：" + p + "（root=" + rootReal + "）");
}

test("常量逐字：SHELL_SCHEME / SHELL_HOST / SHELL_START_URL", () => {
  assert.equal(proto.SHELL_SCHEME, "themis-shell");
  assert.equal(proto.SHELL_HOST, "app");
  assert.equal(proto.SHELL_START_URL, "themis-shell://app/index.html#/first-run");
  assert.equal(proto.isShellPageUrl(proto.SHELL_START_URL), true);
});

test("isShellPageUrl 正例", () => {
  for (const u of ["themis-shell://app/", "themis-shell://app/index.html", "themis-shell://app/index.html#/first-run",
    "themis-shell://app/assets/app.js"]) {
    assert.equal(proto.isShellPageUrl(u), true, u);
  }
});

test("isShellPageUrl 反例（协议/主机/端口/userinfo/抛错的输入）", () => {
  for (const u of ["", "javascript:alert(1)", "http://app/", "https://app/", "file:///C:/x/index.html",
    "themis-shell://other/index.html", "themis-shell://app:8080/index.html", "themis-shell://user@app/index.html",
    "themis-shell://user:pass@app/index.html", "themis-shell://app\\@evil/"]) {
    assert.equal(proto.isShellPageUrl(u), false, u);
  }
});

test("200 用例：九种扩展名的 Content-Type、CSP 逐字、nosniff、body 逐字节、path 在 root 内", () => {
  const { root } = makeRoot();
  const rootReal = fs.realpathSync(root);
  const mime = [
    ["index.html", "text/html"],
    ["assets/app.js", "text/javascript"],
    ["assets/app.css", "text/css"],
    ["assets/f.woff2", "font/woff2"],
    ["assets/i.svg", "image/svg+xml"],
    ["assets/l.png", "image/png"],
    ["assets/fav.ico", "image/x-icon"],
    ["data.json", "application/json"],
    ["licenses/readme.txt", "text/plain"],
  ];
  for (const [rel, contentType] of mime) {
    const r = proto.resolveShellAsset(root, "themis-shell://app/" + rel);
    assert.equal(r.status, 200, rel + " → " + JSON.stringify(r.status));
    assert.equal(typeof r.status, "number", "status 要是数字");
    assert.ok(r.headers && typeof r.headers === "object" && !Array.isArray(r.headers), "headers 要是普通对象");
    assert.equal(headerOf(r.headers, "Content-Type"), contentType, rel);
    assert.equal(headerOf(r.headers, "Content-Security-Policy"), CSP, rel + " 的 CSP 要逐字等于 headers.ts");
    assert.equal(headerOf(r.headers, "X-Content-Type-Options"), "nosniff", rel);
    assert.ok(Buffer.isBuffer(r.body), rel + " 的 body 要是 Buffer");
    assert.deepEqual(r.body, fs.readFileSync(path.join(root, rel)), rel + " 的 body 逐字节相等");
    assertInside(rootReal, r.path);
    assert.equal(r.path, path.join(rootReal, ...rel.split("/")), rel);
  }
  // 起步地址（带 #/first-run）也要拿得到 index.html
  const start = proto.resolveShellAsset(root, proto.SHELL_START_URL);
  assert.equal(start.status, 200, JSON.stringify(start.status));
  assert.equal(headerOf(start.headers, "Content-Type"), "text/html");
});

test("404 用例：一律 404、无正文细节、path 为 null", () => {
  const { root } = makeRoot();
  const cases = [
    ["未知扩展名", "themis-shell://app/notes.xyz"],
    ["目录（不带斜杠）", "themis-shell://app/assets"],
    ["目录（带尾斜杠）", "themis-shell://app/assets/"],
    ["不存在的文件", "themis-shell://app/missing.js"],
    ["http 协议", "http://app/index.html"],
    ["别的主机", "themis-shell://other/index.html"],
    ["带端口", "themis-shell://app:8080/index.html"],
    ["带 userinfo", "themis-shell://user@app/index.html"],
    ["反斜杠（%5c）", "themis-shell://app/a%5cb.js"],
    ["NUL（%00）", "themis-shell://app/a%00b.js"],
    ["解码后的冒号（%3a）", "themis-shell://app/a%3ab.js"],
    ["裸冒号", "themis-shell://app/C:/x.js"],
    ["%252e（解码一次后仍含 %）", "themis-shell://app/%252e.js"],
    ["%252e%252e（二次解码防护）", "themis-shell://app/%252e%252e/secret.txt"],
  ];
  for (const [what, url] of cases) {
    const r = proto.resolveShellAsset(root, url);
    assert.equal(r.status, 404, what + " → " + JSON.stringify(r.status));
    assert.equal(r.path, null, what + " 的 path 要是 null");
    assert.ok(r.body === null || r.body === undefined || (Buffer.isBuffer(r.body) && r.body.length === 0),
      what + " 不许带正文细节");
  }
});

test("越界用例按性质断言：回 200 的读到的文件都在 root 之内", () => {
  const { root } = makeRoot();
  const rootReal = fs.realpathSync(root);
  const urls = [
    "themis-shell://app/../secret.txt",
    "themis-shell://app/%2e%2e/secret.txt",
    "themis-shell://app/a/../../secret.txt",
    "themis-shell://app/assets/../index.html",
    "themis-shell://app/./index.html",
  ];
  for (const url of urls) {
    const r = proto.resolveShellAsset(root, url);
    if (r.status === 200) {
      assertInside(rootReal, r.path);
      assert.notEqual(String(r.body), "SECRET-OUTSIDE", url + " 不许读到 root 外的 secret.txt");
    } else {
      assert.equal(r.status, 404, url);
      assert.equal(r.path, null, url);
    }
  }
});

test("目录链接（junction）指向 root 外 → 404（系统不给建链接就跳过）", () => {
  const { base, root } = makeRoot();
  const outside = path.join(base, "outside");
  fs.mkdirSync(outside);
  fs.writeFileSync(path.join(outside, "leak.txt"), "LEAK");
  let linked = false;
  try {
    fs.symlinkSync(outside, path.join(root, "linked"), "junction");
    linked = true;
  } catch {
    linked = false;
  }
  if (linked) {
    const r = proto.resolveShellAsset(root, "themis-shell://app/linked/leak.txt");
    assert.equal(r.status, 404, "链接越出 root 的文件必须 404：" + JSON.stringify(r.status));
    assert.equal(r.path, null);
  }
});
'''


PROBE_SHELLIPC = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const shellipc = require("@SHELL@/src/shellipc.js");
const { SHELL_CHANNELS, registerShellIpc, shellSenderAllowed } = shellipc;

const CHANNELS = [
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
const SPEC = {
  "themis-shell:get-state": ["getState", 0],
  "themis-shell:pick-repo": ["pickRepo", 0],
  "themis-shell:pick-python": ["pickPython", 0],
  "themis-shell:pick-kit": ["pickKit", 0],
  "themis-shell:pick-transcript-dir": ["pickTranscriptDir", 0],
  "themis-shell:save-settings": ["saveSettings", 1],
  "themis-shell:start-service": ["startService", 1],
  "themis-shell:restart-service": ["restartService", 0],
  "themis-shell:open-external": ["openExternal", 1],
};

test("SHELL_CHANNELS 冻结、恰好九个、名字与顺序逐字", () => {
  assert.ok(Object.isFrozen(SHELL_CHANNELS), "SHELL_CHANNELS 必须冻结");
  assert.deepEqual([...SHELL_CHANNELS], CHANNELS);
});

function makeIpcMain() {
  const handlers = new Map();
  const onCalls = [];
  return {
    handlers,
    onCalls,
    handle: (ch, fn) => {
      if (handlers.has(ch)) throw new Error("通道被重复注册：" + ch);
      handlers.set(ch, fn);
    },
    on: (ch, fn) => onCalls.push([ch, fn]),
  };
}

function makeApi() {
  const calls = [];
  const behavior = {};
  const api = {};
  for (const [ch, [name]] of Object.entries(SPEC)) {
    api[name] = (...args) => {
      calls.push([name, args]);
      const b = behavior[name];
      if (b && b.throwSync) throw new Error("sync-boom-" + name);
      return Promise.resolve().then(() => {
        const b2 = behavior[name];
        if (b2 && b2.reject) throw new Error("async-boom-" + name);
        return (b2 && b2.result) || { ok: true, value: "value-of-" + name };
      });
    };
  }
  return { api, calls, behavior };
}

test("注册只用 handle：恰好九个通道，一次 ipcMain.on 都没有", () => {
  const im = makeIpcMain();
  const { api } = makeApi();
  registerShellIpc(im, api, () => true);
  assert.deepEqual([...im.handlers.keys()].sort(), [...CHANNELS].sort());
  assert.equal(im.onCalls.length, 0, "不许用 ipcMain.on：" + JSON.stringify(im.onCalls));
});

test("来源不对 → {ok:false,reason:forbidden}，一个 api 方法都不进", async () => {
  const im = makeIpcMain();
  const h = makeApi();
  registerShellIpc(im, h.api, () => false);
  for (const ch of CHANNELS) {
    assert.deepEqual(await im.handlers.get(ch)({ marker: "event" }, "x"), { ok: false, reason: "forbidden" }, ch);
  }
  assert.equal(h.calls.length, 0, "被拒的请求不许进 api");
});

test("每个通道转交的方法与实参个数正确，多余实参丢掉", async () => {
  const im = makeIpcMain();
  const h = makeApi();
  registerShellIpc(im, h.api, () => true);
  const payload = { theme: "dark" };
  for (const ch of CHANNELS) {
    const arity = SPEC[ch][1];
    const args = ["A0", "A1", "A2"];
    const r = await im.handlers.get(ch)({ marker: "event" }, ...args);
    assert.equal(r.ok, true, ch);
    const [name, got] = h.calls[h.calls.length - 1];
    assert.equal(name, SPEC[ch][0], ch + " 要转交给 " + SPEC[ch][0] + "，却调了 " + name);
    assert.equal(got.length, arity, ch + " 只许转交 " + arity + " 个实参，得到 " + got.length);
    for (let i = 0; i < arity; i += 1) assert.equal(got[i], "A" + i, ch);
  }
  assert.equal(h.calls.length, CHANNELS.length);
  // 0 实参的通道多给实参也不许透传（不进 api）
  h.calls.length = 0;
  await im.handlers.get("themis-shell:save-settings")({}, payload, "EXTRA");
  assert.deepEqual(h.calls[0][1], [payload]);
});

test("api 抛错（同步与异步）→ {ok:false,reason:internal}，不带错误消息", async () => {
  const im = makeIpcMain();
  const h = makeApi();
  registerShellIpc(im, h.api, () => true);
  h.behavior.getState = { throwSync: true };
  assert.deepEqual(await im.handlers.get("themis-shell:get-state")({}), { ok: false, reason: "internal" });
  h.behavior.getState = { reject: true };
  assert.deepEqual(await im.handlers.get("themis-shell:get-state")({}), { ok: false, reason: "internal" });
  const raw = await im.handlers.get("themis-shell:get-state")({});
  assert.ok(!JSON.stringify(raw).includes("boom"), "错误消息不许外传：" + JSON.stringify(raw));
});

test("成功原样回 api 的 {ok:true,value}", async () => {
  const im = makeIpcMain();
  const h = makeApi();
  registerShellIpc(im, h.api, () => true);
  const deep = { ok: true, value: { nested: [1, 2, { k: "v" }] } };
  h.behavior.getState = { result: deep };
  assert.deepEqual(await im.handlers.get("themis-shell:get-state")({}), deep);
});

test("shellSenderAllowed：三条件都满足才放行", () => {
  const wc = { id: 7 };
  const frame = { url: "themis-shell://app/index.html#/first-run" };
  assert.equal(shellSenderAllowed({ sender: wc, senderFrame: frame }, wc), true);
});

test("shellSenderAllowed 四种反例", () => {
  const wc = { id: 7 };
  const other = { id: 8 };
  const frame = { url: "themis-shell://app/index.html#/first-run" };
  assert.equal(shellSenderAllowed({ sender: other, senderFrame: frame }, wc), false, "webContents 不对");
  assert.equal(shellSenderAllowed({ sender: wc, senderFrame: null }, wc), false, "frame 为 null");
  assert.equal(shellSenderAllowed({ sender: wc, senderFrame: undefined }, wc), false, "frame 为 undefined");
  assert.equal(shellSenderAllowed({ sender: wc, senderFrame: { url: "javascript:alert(1)" } }, wc), false, "javascript: 地址");
  assert.equal(shellSenderAllowed({ sender: wc, senderFrame: { url: "http://127.0.0.1:8123/page" } }, wc), false, "服务 origin 地址");
});
'''


PROBE_SHELLPRELOAD = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { SHELL_CHANNELS } = require("@SHELL@/src/shellipc.js");

// 期望成员只来自类型文件 desktop/web/src/shellpages/themisShell.ts（照 tests/shellshape.test.js 的解析写法，
// 这里不另抄一份键表）
const TS = fs.readFileSync("@THEMIS_TS@", "utf8");

function must(condition, message) {
  if (!condition) throw new Error(message);
}

function interfaceBlock(name) {
  const start = TS.match(new RegExp(`export interface ${name} \\{`));
  must(start !== null, `themisShell.ts 里找不到 export interface ${name}`);
  const rest = TS.slice(start.index + start[0].length);
  const end = rest.search(/\n\}/);
  must(end !== -1, `interface ${name} 没有行首 } 的结束`);
  return rest.slice(0, end);
}

function interfaceNames(name) {
  const names = [];
  for (const line of interfaceBlock(name).split("\n")) {
    let m = line.match(/^\s*(\w+)(\?)?\s*:/);
    if (m === null) m = line.match(/^\s*(\w+)\s*\(/);
    if (m !== null) names.push(m[1]);
  }
  must(names.length > 0, `interface ${name} 解析不出成员——类型文件的格式变了，要报警`);
  return names;
}

// shell-preload 跑在沙箱里，只能用注入的 require 载入 electron；测试里不出现「require electron」这个
// 字面串（T025 门禁 S03 扫 tests/**）
function runShellPreload() {
  const source = fs.readFileSync("@SHELL@/shell-preload.js", "utf8");
  const requires = [];
  const exposes = [];
  const invokes = [];
  const listeners = [];
  const sends = [];
  const state = { envelope: { ok: true, value: 42 } };
  const fakeRequire = (name) => {
    requires.push(name);
    if (name !== "electron") throw new Error("shell-preload 只许 require electron，却 require 了 " + name);
    return {
      contextBridge: {
        exposeInMainWorld: (apiName, api) => exposes.push([apiName, api]),
      },
      ipcRenderer: {
        invoke: async (...args) => {
          invokes.push(args);
          return state.envelope;
        },
        on: (...args) => listeners.push(args),
        removeListener: () => {},
        off: () => {},
        send: (...args) => sends.push(args),
      },
    };
  };
  vm.runInNewContext(source, { require: fakeRequire, module: { exports: {} }, exports: {} });
  return { source, requires, exposes, invokes, listeners, sends, state };
}

test("只 require electron；恰好一次 exposeInMainWorld 且名字 themisShell", () => {
  const p = runShellPreload();
  assert.deepEqual(p.requires, ["electron"]);
  assert.equal(p.exposes.length, 1, JSON.stringify(p.exposes.map((e) => e[0])));
  assert.equal(p.exposes[0][0], "themisShell");
  assert.equal((p.source.match(/exposeInMainWorld/g) || []).length, 1, "exposeInMainWorld 只许出现一次");
});

test("成员名集合等于 themisShell.ts 的 interface ThemisShell 加 getAppearance（从 .ts 解析）", () => {
  const p = runShellPreload();
  const expected = interfaceNames("ThemisShell");
  assert.equal(expected.length, 10, "类型文件解析出的成员应当是十个：" + JSON.stringify(expected));
  // 本片外壳侧暴露面十一个：原十个 + getAppearance；T063 片 B 起 themisShell.ts 加 getAppearance 后恢复逐字相等
  assert.deepEqual(Object.keys(p.exposes[0][1]).sort(), [...expected, "getAppearance"].sort());
  assert.equal("themisHost" in p.exposes[0][1], false, "不许暴露 themisHost");
});

test("九个方法各用一条通道，合起来恰好等于 SHELL_CHANNELS；实参只转发声明的个数", () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  const patch = { theme: "dark" };
  api.getState("EXTRA");
  api.pickRepo("EXTRA");
  api.pickPython("EXTRA");
  api.pickKit("EXTRA");
  api.pickTranscriptDir("EXTRA");
  api.saveSettings(patch, "EXTRA");
  api.startService("repo-x", "EXTRA");
  api.restartService("EXTRA");
  api.openExternal("https://x.example/", "EXTRA");
  const expected = [
    ["themis-shell:get-state"],
    ["themis-shell:pick-repo"],
    ["themis-shell:pick-python"],
    ["themis-shell:pick-kit"],
    ["themis-shell:pick-transcript-dir"],
    ["themis-shell:save-settings", patch],
    ["themis-shell:start-service", "repo-x"],
    ["themis-shell:restart-service"],
    ["themis-shell:open-external", "https://x.example/"],
  ];
  assert.deepEqual(p.invokes, expected);
  const used = p.invokes.map((a) => a[0]).sort();
  assert.deepEqual(used, [...SHELL_CHANNELS].sort());
});

test("信封 ok → resolve value；不 ok → 以带 reason 的 Error reject（reason 只进 message）", async () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  p.state.envelope = { ok: true, value: { a: 1, b: ["deep"] } };
  assert.deepEqual(await api.getState(), { a: 1, b: ["deep"] });
  p.state.envelope = { ok: false, reason: "bad-patch" };
  await assert.rejects(
    api.saveSettings({}),
    (err) => err.message === "bad-patch"
      && err.reason === undefined
      && Object.prototype.toString.call(err) === "[object Error]",
  );
});

// 站主 2026-11-13（T033 规划第 3 节）：T033 的 preload 要订阅主进程发来的 service-state，“不注册监听”一条退役；
// 留下的是：on 同步返回函数，on 与退订都不发 invoke。
test("on 同步返回退订函数；on 与退订都不发 invoke", () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  const before = p.invokes.length;
  const off = api.on("service-state", () => {});
  assert.equal(typeof off, "function", "on 要同步返回一个函数");
  off();
  assert.equal(p.invokes.length, before, "on/退订都不许发 invoke");
});

// 站主 2026-11-13（T033 规划第 3 节）：ipcRenderer.on 的两处断言退役（同上）；send 禁令、相对路径与 node: 禁令照留。
test("自包含：没有 ipcRenderer.send 的调用、不 require 相对路径或 node: 模块", () => {
  const p = runShellPreload();
  assert.equal(p.sends.length, 0);
  assert.ok(!/ipcRenderer\s*\.\s*send\s*\(/.test(p.source), "不许有 ipcRenderer 的发送");
  assert.ok(!/require\(\s*['"]\./.test(p.source), "不许 require 相对路径");
  assert.ok(!/require\(\s*['"]node:/.test(p.source), "不许 require node: 模块");
});
'''


PROBE_DETECT = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { detectKit, runProcess } = require("@SHELL@/src/detect.js");

function makeKit(dir, script) {
  fs.mkdirSync(path.join(dir, "scripts"), { recursive: true });
  fs.writeFileSync(path.join(dir, "scripts", "pi_dispatch.py"), script);
}

test("detectKit：相对 kitPath → 返回绝对路径（path.resolve(kitDir, scripts, pi_dispatch.py)）", async () => {
  const base = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t030-detect-")));
  makeKit(path.join(base, "kit"), 'process.stdout.write("pi_dispatch 2.12.0\\n");\n');
  const prev = process.cwd();
  process.chdir(base);
  try {
    const r = await detectKit({ pythonPath: process.execPath, kitPath: "kit", timeoutMs: 15000 });
    assert.equal(r.status, "ok", JSON.stringify(r));
    assert.equal(r.source, "external");
    assert.ok(path.isAbsolute(r.path), "kit 路径必须是绝对路径：" + JSON.stringify(r.path));
    assert.equal(r.path, path.resolve(base, "kit", "scripts", "pi_dispatch.py"));
  } finally {
    process.chdir(prev);
  }
});

test("runProcess：输出在退出之后才到（要在 close 事件里取输出）", async () => {
  const fixture = path.join("@SHELL@", "tests", "fixtures", "fake-late-output.js");
  assert.ok(fs.existsSync(fixture), "夹具不存在：" + fixture);
  const r = await runProcess(process.execPath, [fixture], { timeoutMs: 20000 });
  assert.equal(r.error, undefined, JSON.stringify(r));
  assert.equal(r.timedOut, false, JSON.stringify(r));
  assert.equal(r.code, 0, JSON.stringify(r));
  assert.ok(String(r.stdout).trim().length > 0,
    "孙进程迟到的那行输出没有被收进来（exit 事件取输出会拿到空 stdout）：" + JSON.stringify(r));
});

test("runProcess：起不来的命令照旧回 error=ENOENT", async () => {
  const r = await runProcess("themistally-no-such-command-xyz", ["--version"], { timeoutMs: 15000 });
  assert.equal(r.error, "ENOENT", JSON.stringify(r));
  assert.equal(r.timedOut, false);
});

test("runProcess：超时照旧立刻给结果并算 timedOut", async () => {
  const r = await runProcess(process.execPath, ["-e", "setTimeout(() => {}, 8000)"], { timeoutMs: 250 });
  assert.equal(r.timedOut, true, JSON.stringify(r));
  assert.equal(r.code, null);
});
'''


# --------------------------------------------------------------------------- 探针包装

def test_p01_probe_launch():
    """D01：launchMode 的分支判定（node --test 探针）。"""
    _expect_probe_pass("t030-launch", PROBE_LAUNCH)


def test_p02_probe_shellprotocol():
    """D02：themis-shell 协议的常量、URL 判定、定位与拒绝规则、MIME/CSP/nosniff（node --test 探针）。"""
    _expect_probe_pass("t030-proto", PROBE_PROTOCOL)


def test_p03_probe_shellipc():
    """D03：九个通道、只用 handle、来源检查、forbidden/internal 信封、多余实参丢弃（node --test 探针）。"""
    _expect_probe_pass("t030-shellipc", PROBE_SHELLIPC)


def test_p04_probe_shellpreload():
    """D04：shell-preload 的暴露面与 themisShell.ts 逐字一致、拆信封、on 不发 IPC（node --test 探针）。"""
    _expect_probe_pass("t030-shellpreload", PROBE_SHELLPRELOAD)


def test_p05_probe_detect():
    """D05：detect 两处修复——相对 kitPath 绝对路径、close 取迟到输出；ENOENT 与超时照旧（node --test 探针）。"""
    _expect_probe_pass("t030-detect", PROBE_DETECT)
