"""T035 战前门禁：桌面端外壳第 6 片「服务意外退出回服务状态页、restartService、第二次起服务的接线」
的黑盒基准测试（合同 t035-desktop-shell-service-b v1，基线 bdee39f8be——src/hostrelay.js、
tests/hostrelay.test.js 都还不存在，serviceflow 还不按 run 记状态（exited 之后再 start 回 busy），
restartService 仍回 not-implemented，shellprotocol 没有 SHELL_STATUS_URL，main.js 的意外退出还是
A 片过渡写法：写一行 ERROR、以 1 退出）。

被测对象：``src/serviceflow.js``（按 run 记状态：exited 之后可再 start、旧 run 的回调只在仍是
当前 run 时改状态、byShell 按 run 算）、``src/shellapi.js`` 的 ``restartService``（idle/无控制器 →
no-previous；starting/running 幂等回 ok；exited → 走 startService(state.repo) 按当前设置重启）、
新增纯模块 ``src/hostrelay.js``（createHostRelay() → {host, senderAllowed, use, clear}，宿主 IPC
只注册一次、调用转给当前 host）、``src/shellprotocol.js`` 的新常量 ``SHELL_STATUS_URL``、
``main.js`` 外壳分支的接线（宿主 relay、外壳窗口 helper 每次新分区并在该 session 上注册一次
protocol handler、registerShellIpc/registerHostIpc 各只调一次、选择框挂当前外壳窗口、意外退出
三分支：已有外壳窗口不另开 / 先开服务状态页开好才关服务窗口 / 开不出来才 ERROR+1）、README 的
新退出码表与冒烟步骤、package.json 的 scripts.test。

基线（bdee39f8be）上这些符号与行为都不存在，所以失败都落在「文件不存在」「标记不在」「探针子进程
退出码非 0」与探针内的具体断言上，不是收集失败：模块级只导入标准库，仓库文件的读取与探针的运行
都发生在用例函数里。探针是自包含的 ``node --test`` 文件（Node 24 自带，不需要 npm ci，也不
require electron 本体）。Python 把探针源码写进系统临时目录、以仓库根为 cwd 运行、用完即删；探针
里的被测模块用绝对路径 require（``@SHELL@`` 占位符替换）。P01/P03 探针真起子进程（现有的
``tests/fixtures/fake-service.js`` 与 ``tests/fixtures/fake-service-exit.js``），不 mock
child_process。

结构（编号大致对应合同 DoD 的 D01–D09）：

- 静态断言（``test_s*``，不需要任何依赖）：
  - S01/D08：合同 Scope 点名的 2 个新文件都在位。
  - S02/D09：package.json 只许改 scripts.test——tap 开关仍在文件清单之前、显式列出 tests/ 下
    每一个 *.test.js（数据驱动）且本片新增的 tests/hostrelay.test.js 点名在列、21 份既有测试
    一条没删没改名、依赖与锁文件不动。
  - S03/D03/D08：新纯模块 src/hostrelay.js 在位、不 require electron、没有 src/** 的词面禁词；
    新测试 tests/hostrelay.test.js 不出现 require('electron') 字面串、假 ipcMain 的变量名用 im；
    ipcMain.on 与 ipcRenderer.send 在 desktop/shell 下全禁（重扫一遍，覆盖新文件）。
  - S04/D03/D04/D05/D06：main.js 外壳分支的接线——require 并调用 createHostRelay；
    registerHostIpc 在 runShellPage 体内恰好一次、实参是 relay.host/relay.senderAllowed；
    relay.use(…) 在 runShellPage 体内且第一个实参真是 createHost( 建的新 host（不挂 use
    的话宿主接口会全回 forbidden）；relay.clear() 收紧成 relay 的方法调用；
    registerShellIpc 恰好一次、来源检查读当前外壳窗口（isDestroyed）；选择框与确认框挂当前
    外壳窗口变量；.protocol.handle( 全文恰好一处、前 160 字内有 fromPartition、前 600 字内取
    新分区（站主实测：新分区新 session 才能重复开窗，同一 session 二次注册抛错
    Failed to register protocol: themis-shell——这三条把「每次新分区、每 session 一次」钉死）；
    SHELL_STATUS_URL 被 main.js 引用且用在意外退出分支（订阅回调里）；兜底 ERROR 行与
    app.exit(1) 仍在；relay.clear() 在外壳分支里；用户关窗的收尾（abort/stop/退出码文案）不变；
    既有形状（new BrowserWindow 恰好一处、runShell( 恰好一处且在 launchMode( 之后、五键）不破。
  - S05/D07：README——退出码 1 那行去掉「服务意外退出」、写「服务状态页」兜底；restartService
    写真行为与 reason 词表（no-previous；含 restartService 的行里不再有 not-implemented/
    仍是占位——定点否定，README 别处留给别的片写自己的占位说明，不整篇否定）；意外退出写回服务
    状态页（「服务状态页」至少两处）；冒烟写「重启服务」；既有 needle 抽样还在。
  - S06/D09/D02：包内测试不再断言占位行为（shellapi.test.js 无 not-implemented）；包内测试
    没有 skip（.skip( / skip: true）。
- 探针断言（``test_p*``，跑 node --test）：
  - P01/D01：serviceflow 按 run 记状态——run1 意外退出（码 3）后 run2 能再 start
    （starting → running）；byShell 按 run 算（run1 被 stop、run2 意外退出仍 false）；run1
    握手超时被 kill 之后旧子进程的退出不许把 run2 改成 exited；starting/running 时再 start 仍
    busy 且不起第二个进程。
  - P02/D02：restartService——idle/没控制器 → no-previous 且不起进程；starting/running →
    {ok:true,value:null} 且不起进程；exited → 走 startService(exited 里的 repo，不是
    currentRepo)、命令按当前设置算（先经 pickKit 换 kitPath，重启的命令跟着变）、失败 reason
    与 startService 一致（unknown-repo/python-missing/kit-missing/no-service）；控制器的
    失败信封原样回传。
  - P03/D03：hostrelay——形状 {host, senderAllowed, use, clear}；没有当前 host 时五个方法回
    forbidden 不抛错、senderAllowed 为 false；use 替换不叠加、实参原样转发；clear 之后回到
    forbidden；检查抛错按 false；重入用例（真 createServiceFlow + 假 im）：第一次意外退出、
    第二次起服务成功，registerHostIpc 的注册次数仍是 5、第二次 start 回 ok、调用进第二个 host。
  - P04/D05：SHELL_STATUS_URL 值逐字等于 themis-shell://app/index.html#/service-status、
    isShellPageUrl 对它为真、既有常量不变。

合同没写死、门禁端按最合理读法定下的地方（写进交付信「下游须知」）：main.js 的断言取「正文出现
次数与相对顺序」，不锁定变量名（外壳窗口变量从 shellSenderAllowed(event, X.webContents) 的形态
里提取）；选择框挂当前窗口断言为「createShellApi 实参引用该变量或含 isDestroyed」；「先开新窗口
再关旧窗口」的次序与「已有外壳窗口时不另开」的条件逻辑属运行时行为，由审核端 review 与 README
冒烟覆盖（合同 D06 的证据栏本就是 G01、review）。
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL = REPO_ROOT / "desktop" / "shell"

# 合同 Scope 点名的新文件（只断言「在位」，不断言「只有这些」）
CONTRACT_FILES = (
    "src/hostrelay.js",
    "tests/hostrelay.test.js",
)

NEW_TEST_FILES = ("tests/hostrelay.test.js",)

# 既有 21 份测试文件（T033 交付后）：一条也没删没改名（D09）
PREEXISTING_TEST_FILES = (
    "tests/args.test.js", "tests/package.test.js", "tests/python.test.js", "tests/handshake.test.js",
    "tests/service.test.js", "tests/window.test.js", "tests/core.test.js", "tests/control.test.js",
    "tests/host.test.js", "tests/hostcheck.test.js", "tests/ipc.test.js", "tests/preload.test.js",
    "tests/settings.test.js", "tests/detect.test.js", "tests/shellapi.test.js", "tests/shellshape.test.js",
    "tests/launch.test.js", "tests/shellprotocol.test.js", "tests/shellipc.test.js", "tests/shellpreload.test.js",
    "tests/serviceflow.test.js",
)

REQUIRE_ELECTRON_RE = re.compile(r"require\(\s*['\"]electron['\"]\s*\)")

# src/** 与 main.js 的词面禁令（T025 起沿用）：本片的新纯模块也要过同一套
SRC_FORBIDDEN = (
    (re.compile(r"persist:"), "persist: 前缀"),
    (re.compile(r"shell\s*:\s*true"), "shell: true"),
    (re.compile(r"\b(writeFile|writeFileSync|appendFile|appendFileSync|mkdir|mkdirSync|rm|rmSync|unlink|unlinkSync|rename|renameSync)\s*\("), "fs 写函数"),
    (re.compile(r"\bfetch\s*\("), "fetch"),
    (re.compile(r"\bnet\.request\b"), "net.request"),
    (re.compile(r"\bautoUpdater\b"), "autoUpdater"),
    (re.compile(r"\bcrashReporter\b"), "crashReporter"),
    (re.compile(r"\bdialog\b"), "dialog"),
    (re.compile(r"\bNotification\b"), "Notification"),
    (re.compile(r"\bshowItemInFolder\b"), "showItemInFolder"),
    (re.compile(r"\bshell\s*\.\s*openExternal\b"), "shell.openExternal"),
)

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

ELECTRON_ALLOWED = ("main.js", "preload.js", "shell-preload.js")

# host 的七个方法名（合同 Behavior contract；片 A 末尾加 saveTheme）
HOST_METHODS = ("reauth", "openSecretWindow", "openExternal", "reveal", "notify", "openSettings", "saveTheme")


def _shell_read(rel: str) -> str:
    p = SHELL / rel
    assert p.is_file(), f"desktop/shell/{rel} 不存在"
    return p.read_text(encoding="utf-8")


def _scan_files():
    """扫描范围：顶层 main.js / preload.js / shell-preload.js + src/** + tests/**。"""
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
    with tempfile.TemporaryDirectory(prefix="t035-gate-") as td:
        probe = Path(td) / f"{name}.test.js"
        probe.write_text(source, encoding="utf-8")
        return subprocess.run(
            [node, "--test", str(probe)],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )


def _expect_probe_pass(name: str, template: str, timeout: float = 300.0) -> None:
    source = template.replace("@SHELL@", json.dumps(str(SHELL))[1:-1])
    proc = _run_probe(name, source, timeout=timeout)
    assert proc.returncode == 0, (
        f"探针 {name} 没有全绿（退出码 {proc.returncode}）：\n"
        f"--- stdout 末尾 ---\n{proc.stdout[-6000:]}\n--- stderr 末尾 ---\n{proc.stderr[-2000:]}"
    )


def _call_arg_text(text: str, pos: int) -> str:
    """从 pos 起截取第一个 ``f(...)`` 调用的括号内文本（深度配平）。"""
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


def _first_arg(arg_text: str) -> str:
    """取 ``f(a, b, …)`` 括号内文本的第一个实参（在深度为 0 的逗号处截断）。"""
    depth = 0
    for i, c in enumerate(arg_text):
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            return arg_text[:i]
    return arg_text


def _brace_body(text: str, name: str) -> str:
    """取 ``async function name(...) {...}`` 的函数体文本（大括号配平；模板串里的 ${...} 成对，不影响配平）。"""
    at = text.find(f"function {name}(")
    assert at != -1, f"main.js 缺 function {name}( 的定义（合同 Repository facts：外壳页分支就是 {name}）"
    start = text.find("{", at)
    assert start != -1
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
    raise AssertionError("大括号没有配平")


# --------------------------------------------------------------------------- 静态断言

def test_s01_contract_files():
    """D08/Scope：合同点名的 2 个新文件都在位。"""
    for rel in CONTRACT_FILES:
        assert (SHELL / rel).is_file(), f"desktop/shell/{rel} 不存在"
    # 既有夹具原样在位（本片不改 fixtures/**）
    assert (SHELL / "tests" / "fixtures" / "fake-service.js").is_file()
    assert (SHELL / "tests" / "fixtures" / "fake-service-exit.js").is_file()


def test_s02_package_json_and_lock():
    """D09：package.json 只许改 scripts.test（tap 开关、点出新测试、数据驱动全量点名、既有
    21 份一条没删），其余字段、依赖与锁文件不动。"""
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
    """D03/D08：新纯模块不 require electron、没有词面禁词；新测试不出现 require('electron')
    字面串、假 ipcMain 变量名用 im；ipcMain.on 与 ipcRenderer.send 在 desktop/shell 下全禁
    （重扫一遍，覆盖本片新增的两个文件）。"""
    relay_path = SHELL / "src" / "hostrelay.js"
    assert relay_path.is_file(), "desktop/shell/src/hostrelay.js 不存在"
    relay_text = relay_path.read_text(encoding="utf-8")
    assert not REQUIRE_ELECTRON_RE.search(relay_text), "src/hostrelay.js 不许 require electron（纯模块）"
    for pat, what in SRC_FORBIDDEN:
        m = pat.search(relay_text)
        assert m is None, (
            f"src/hostrelay.js 出现禁令「{what}」：…{relay_text[max(0, m.start() - 40):m.end() + 40]}…"
        )

    relay_test_path = SHELL / "tests" / "hostrelay.test.js"
    assert relay_test_path.is_file(), "desktop/shell/tests/hostrelay.test.js 不存在"
    relay_test = relay_test_path.read_text(encoding="utf-8")
    assert not REQUIRE_ELECTRON_RE.search(relay_test), (
        "tests/hostrelay.test.js 不许出现 require('electron') 字面串（假 electron 要经注入/沙箱给）"
    )
    assert re.search(r"\bim\b", relay_test), (
        "tests/hostrelay.test.js 里假 ipcMain 的变量名要用 im（合同词面禁令）"
    )

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


def test_s04_main_js_wiring():
    """D03/D04/D05/D06：main.js 外壳分支的接线——宿主 relay 只注册一次且每次服务起来把新 host
    挂进去（use 的实参核过、clear 是 relay 的方法调用）、外壳 IPC 与选择框读当前外壳窗口、
    protocol.handle 单点且就近取新分区、意外退出三分支（SHELL_STATUS_URL 换页 +
    兜底 ERROR/1）、用户关窗收尾不变、既有形状不破。"""
    text = _shell_read("main.js")

    # D03：新纯模块被 require 并实例化；宿主 IPC 经 relay 注册、整个外壳分支恰好一次
    assert re.search(r"""require\(\s*['"]\.\/src\/hostrelay(\.js)?['"]\s*\)""", text), (
        "main.js 没有 require ./src/hostrelay.js"
    )
    assert re.search(r"\bcreateHostRelay\s*\(", text), "main.js 没有调 createHostRelay("
    page = _brace_body(text, "runShellPage")
    assert page.count("registerHostIpc(") == 1, (
        f"runShellPage 里 registerHostIpc( 必须恰好一次（现在是 {page.count('registerHostIpc(')} 次）"
    )
    hostipc_arg = _call_arg_text(page, page.find("registerHostIpc("))
    assert re.search(r"\.\s*host\b", hostipc_arg), (
        f"registerHostIpc 的第二个实参要是 relay.host：{hostipc_arg[:160]!r}"
    )
    assert re.search(r"\.\s*senderAllowed\b", hostipc_arg), (
        f"registerHostIpc 的第三个实参要是 relay.senderAllowed：{hostipc_arg[:160]!r}"
    )
    # 每次服务起来把新 host 挂进 relay：use(host, 来源检查) 的第一个实参要真是 createHost(
    # 建的那个 host——不挂 use 的话宿主接口会全回 forbidden，而上面「只注册一次」的断言照样绿
    m_relay = re.search(r"([A-Za-z_$][\w$]*)\s*=\s*createHostRelay\s*\(", text)
    assert m_relay, "main.js 里 createHostRelay( 的返回值要存进一个变量（relay）"
    relay_var = m_relay.group(1)
    host_vars = set(re.findall(r"([A-Za-z_$][\w$]*)\s*=\s*createHost\s*\(", page))
    use_calls = list(re.finditer(rf"\b{re.escape(relay_var)}\s*\.\s*use\s*\(", page))
    assert use_calls, f"runShellPage 里要调 {relay_var}.use(host, 来源检查)，把新 host 挂进 relay"
    first_args = [_first_arg(_call_arg_text(page, m.start())).strip() for m in use_calls]
    assert any(a in host_vars or "createHost(" in a for a in first_args), (
        f"{relay_var}.use(…) 的第一个实参要是 createHost( 建的新 host（现在 {first_args!r}，"
        f"createHost 建的是 {sorted(host_vars)}）"
    )
    # 服务窗口被外壳关掉时清掉当前 host（relay 自己的方法调用，不是随便哪个 clear()）
    assert re.search(rf"\b{re.escape(relay_var)}\s*\.\s*clear\s*\(", page), (
        f"外壳分支要在服务窗口被外壳关掉时调 {relay_var}.clear()"
    )

    # D04：registerShellIpc 恰好一次；来源检查读当前外壳窗口（isDestroyed + webContents）
    assert page.count("registerShellIpc(") == 1, (
        f"runShellPage 里 registerShellIpc( 必须恰好一次（现在是 {page.count('registerShellIpc(')} 次）"
    )
    shellipc_arg = _call_arg_text(page, page.find("registerShellIpc("))
    assert "shellSenderAllowed" in shellipc_arg, f"来源检查要经 shellSenderAllowed：{shellipc_arg[:160]!r}"
    assert "isDestroyed" in shellipc_arg, (
        f"来源检查要先看当前外壳窗口是否还在（isDestroyed）：{shellipc_arg[:160]!r}"
    )
    m = re.search(r"shellSenderAllowed\s*\(\s*[\w$]+\s*,\s*([\w$]+)\s*\.\s*webContents\s*\)", shellipc_arg)
    assert m, f"来源检查要读当前外壳窗口的 webContents（shellSenderAllowed(event, X.webContents)）：{shellipc_arg[:200]!r}"
    win_var = m.group(1)
    # 选择框与外部链接确认框挂在当前外壳窗口上（引用同一变量，或经 isDestroyed 判断）
    assert re.search(r"\bcreateShellApi\s*\(", page), "runShellPage 里要建 createShellApi"
    api_arg = _call_arg_text(page, page.find("createShellApi("))
    assert re.search(rf"\b{re.escape(win_var)}\b", api_arg) or ("isDestroyed" in api_arg), (
        f"选择框与确认框要挂当前外壳窗口（{win_var} 或经 isDestroyed 判断）：{api_arg[:200]!r}"
    )
    for key in ("service:", "assets:"):
        assert re.search(rf"\b{key[:-1]}\s*:", api_arg), f"createShellApi 的注入项里要有 {key}{api_arg[:160]!r}"

    # D05：.protocol.handle( 全文恰好一处（helper 是唯一注册点）；前 160 字内有 fromPartition
    #（合同硬要求）；前 600 字内取新分区（站主实测：新分区才有新 session，同一 session 二次注册
    # 抛错 Failed to register protocol: themis-shell——所以每次开窗都必须现取 partitionName）
    handles = re.findall(r"\.protocol\.handle\s*\(", text)
    assert len(handles) == 1, f"main.js 里 .protocol.handle( 必须恰好一处（现在是 {len(handles)} 处）"
    pos = text.find(".protocol.handle(")
    assert "fromPartition" in text[max(0, pos - 160):pos], (
        "协议 handler 必须挂在 session.fromPartition(...) 的 session 上（前 160 字内要有 fromPartition）"
    )
    assert re.search(r"partitionName\s*\(", text[max(0, pos - 600):pos]), (
        "开外壳窗口取新分区的 partitionName() 要与协议注册在同一个 helper 里（注册点前 600 字内）"
    )
    # 起步地址与意外退出换页地址都走这一个 helper
    assert "SHELL_START_URL" in page, "外壳分支起步仍要加载 SHELL_START_URL"
    assert "SHELL_STATUS_URL" in text, "main.js 没有引用 SHELL_STATUS_URL（意外退出回服务状态页要用它）"

    # D06：意外退出的三条分支都钉在发 SERVICE_STATE_CHANNEL 的那个订阅回调里
    sub_args = []
    for msub in re.finditer(r"\.\s*subscribe\s*\(", page):
        arg = _call_arg_text(page, msub.end() - 1)
        if "SERVICE_STATE_CHANNEL" in arg:
            sub_args.append(arg)
    assert len(sub_args) == 1, "runShellPage 里发 SERVICE_STATE_CHANNEL 的订阅回调要恰好一个"
    sub = sub_args[0]
    assert "byShell" in sub, "意外退出的判定要看 info.byShell"
    assert "SHELL_STATUS_URL" in sub, (
        f"意外退出分支要开服务状态页（SHELL_STATUS_URL）：{sub[:200]!r}"
    )
    assert "服务意外退出（退出码" in sub, "服务状态页开不出来时的兜底 ERROR 行不许丢"
    assert "app.exit(1)" in sub, "兜底分支的 app.exit(1) 不许丢"
    assert "webContents.send(" in sub, "服务状态事件仍要经 webContents.send 发给外壳页"

    # 用户关窗的收尾不变（D06 后半句）
    for needle in (".abort()", ".stop()", "服务没有以 0 正常退出", "app.exit(0)"):
        assert needle in page, f"外壳分支要保留「{needle}」（用户关窗的收尾）"

    # 既有形状不破：new BrowserWindow 恰好一处；runShell( 恰好一处且在 launchMode( 之后、五键
    assert len(re.findall(r"new\s+BrowserWindow", text)) == 1, "main.js 的 new BrowserWindow 必须恰好一处"
    assert len(re.findall(r"runShell\s*\(", text)) == 1, (
        "main.js 里 runShell( 的写法只许出现一次（服务分支那一处；新代码与注释里不许再写它）"
    )
    launch_at = text.find("launchMode(")
    run_at = text.find("runShell(")
    assert launch_at != -1 and run_at != -1, "main.js 缺 launchMode( 或 runShell( 的调用"
    assert launch_at < run_at, "launchMode 的判定必须发生在调用 runShell 之前"
    run_arg = _call_arg_text(text, run_at)
    for key in ("argv", "io", "openWindow", "onServiceReady", "env"):
        assert re.search(rf"\b{key}\b", run_arg), f"runShell 的调用仍要收 {key}：{run_arg[:200]!r}"
    # 外壳分支仍然 require 并实例化 serviceflow、createHost（控制令牌的来路）
    assert re.search(r"""require\(\s*['"]\.\/src\/serviceflow(\.js)?['"]\s*\)""", text), (
        "main.js 没有 require ./src/serviceflow.js"
    )
    assert re.search(r"\bcreateServiceFlow\s*\(", text), "main.js 没有调 createServiceFlow("
    assert re.search(r"\bcreateHost\s*\(", page), "runShellPage 里仍要 createHost(（服务窗口的宿主接口）"


def test_s05_readme():
    """D07：README 写清新退出码表（码 1 去掉「服务意外退出」、写服务状态页兜底）、restartService
    真行为与 reason 词表（no-previous；含 restartService 的行里不再有 not-implemented/仍是占位——定点否定，README 别处留给别的片）、意外退出回服务状态页
    （「服务状态页」至少出现在退出码表与外壳页两处）、冒烟含「重启服务」；既有 needle 抽样还在
    （全清单由各片门禁在 R01 里钉住）。"""
    text = _shell_read("README.md")

    # 退出码表：码 1 那行去掉「服务意外退出」、写「服务状态页」兜底；0 与 2 的行照旧在
    rows1 = [ln for ln in text.splitlines() if re.match(r"^\|\s*\*\*1\*\*\s*\|", ln)]
    assert rows1, "README 的退出码表缺「| **1** |」这一行"
    for ln in rows1:
        assert "服务意外退出" not in ln, f"退出码 1 的含义里要去掉「服务意外退出」：{ln!r}"
        assert "服务状态页" in ln, f"退出码 1 的含义里要写「服务状态页开不出来」这一条兜底：{ln!r}"
    assert any(re.match(r"^\|\s*\*\*0\*\*\s*\|", ln) for ln in text.splitlines()), "退出码 0 的行不许删"
    assert any(re.match(r"^\|\s*\*\*2\*\*\s*\|", ln) for ln in text.splitlines()), "退出码 2 的行不许删"

    # restartService 真行为与 reason 词表：定点否定——只钉含 restartService 的行（README 是
    # 各片共用的文档，别的片可能在别处写自己的占位说明，整篇否定会误伤别的片）
    assert "no-previous" in text, "README 要写 restartService 的 reason「no-previous」"
    restart_lines = [ln for ln in text.splitlines() if "restartService" in ln]
    assert restart_lines, "README 要写到 restartService 的行为"
    for ln in restart_lines:
        assert "not-implemented" not in ln, (
            f"含 restartService 的行不许再写占位 reason（not-implemented）：{ln!r}"
        )
        assert "仍是占位" not in ln, f"含 restartService 的行不许再说「仍是占位」：{ln!r}"

    # 意外退出回服务状态页：退出码表与外壳页两处都要写到「服务状态页」
    assert text.count("服务状态页") >= 2, (
        f"「服务状态页」至少要出现在退出码表与外壳页两节（现在 {text.count('服务状态页')} 处）"
    )

    # 手工冒烟：意外退出 → 服务状态页 → 重启服务
    assert "重启服务" in text, "手工冒烟要写到点「重启服务」这一步"

    # 既有 needle 抽样（防执行端顺手删了别片的钉子；全量由 R01 的各片门禁守）
    for needle in (
        "T032", "on('service-state'", "桩数据", "外壳页在本片就位",
        "npm --prefix ../web run build", "themis-shell://app/index.html#/first-run",
        "desktop/web/dist", "themisShell",
    ):
        assert needle in text, f"README 缺既有 needle「{needle}」"


def test_s06_no_placeholder_no_skip():
    """D09/D02：包内测试不再断言占位行为（:750-754 的占位断言要换成真行为断言）；包内测试
    不许 skip。"""
    t = _shell_read("tests/shellapi.test.js")
    assert "not-implemented" not in t, (
        "tests/shellapi.test.js 里 restartService 的占位断言（not-implemented）要换成真行为断言"
    )
    for p in sorted((SHELL / "tests").glob("*.test.js")):
        text = p.read_text(encoding="utf-8")
        assert not re.search(r"\.\s*skip\s*\(", text), f"{p.name} 里不许出现 .skip("
        assert not re.search(r"\bskip\s*:\s*true", text), f"{p.name} 里不许出现 skip: true"


# --------------------------------------------------------------------------- 探针断言（node --test）

PROBE_SERVICEFLOW = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { createServiceFlow } = require("@SHELL@/src/serviceflow.js");

const FAKE = path.join("@SHELL@", "tests", "fixtures", "fake-service.js");
const FAKE_EXIT = path.join("@SHELL@", "tests", "fixtures", "fake-service-exit.js");

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
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
}

test("D01-a exited 之后能再 start：run1 意外退出（码 3）→ run2 起来（starting → running）；running 时再 start 仍 busy", async () => {
  const flow = createServiceFlow({});
  const events = [];
  flow.subscribe((state) => events.push(JSON.parse(JSON.stringify(state))));
  // run1：握手成功后 60ms 以码 3 自己退出（不是外壳停的）
  assert.deepEqual(
    await flow.start({ repo: "run-1", command: [process.execPath, FAKE_EXIT] }),
    { ok: true, value: null },
  );
  await waitFor("run1 exited", () => flow.state().kind === "exited", 8000);
  assert.equal(flow.state().exitCode, 3);
  assert.equal(events.length, 3, JSON.stringify(events));
  // run2：exited 之后还能再 start（状态不被旧 run 卡住）
  assert.deepEqual(
    await flow.start({ repo: "run-2", command: [process.execPath, FAKE], env: envWith({ FAKE_SERVICE_MODE: "ok" }) }),
    { ok: true, value: null },
  );
  assert.equal(events.length, 5, JSON.stringify(events));
  assert.deepEqual(events[3], { kind: "starting", repo: "run-2" }, JSON.stringify(events));
  assert.equal(events[4].kind, "running");
  assert.equal(events[4].repo, "run-2");
  assert.deepEqual(flow.state(), events[4]);
  // running 期间再 start 仍回 busy、不起第二个进程
  assert.deepEqual(
    await flow.start({ repo: "run-2b", command: [process.execPath, FAKE], env: envWith({ FAKE_SERVICE_MODE: "ok" }) }),
    { ok: false, reason: "busy" },
  );
  const stopResult = await flow.stop();
  assert.equal(stopResult.exited, true, JSON.stringify(stopResult));
  await waitFor("run2 exited", () => events.length >= 6 && events[5].kind === "exited", 8000);
  assert.equal(events[5].exitCode, 0);
});

test("D01-b byShell 按 run 算：run1 被 stop（true），run2 意外退出仍是 false", async () => {
  const flow = createServiceFlow({});
  const events = [];
  const infos = [];
  flow.subscribe((state, info) => {
    events.push(state);
    infos.push(info);
  });
  // run1：被外壳 stop（byShell=true）
  assert.deepEqual(
    await flow.start({ repo: "s-1", command: [process.execPath, FAKE], env: envWith({ FAKE_SERVICE_MODE: "ok" }) }),
    { ok: true, value: null },
  );
  await flow.stop();
  await waitFor("run1 exited", () => flow.state().kind === "exited", 8000);
  assert.equal(infos[2].byShell, true, "run1 是外壳停的");
  // run2：服务自己退出 → byShell 必须是 false（上一 run 的 stopping 不许继承）
  assert.deepEqual(
    await flow.start({ repo: "s-2", command: [process.execPath, FAKE_EXIT] }),
    { ok: true, value: null },
  );
  await waitFor("run2 exited", () => events.length >= 6 && events[5].kind === "exited", 8000);
  assert.equal(events[5].exitCode, 3);
  assert.equal(infos[5].byShell, false, "run2 的意外退出不是外壳结束的，标志不许继承上一 run");
});

test("D01-c 旧 run 的子进程退出不许把新 run 改成 exited", async () => {
  const rec = recordingSpawn();
  const flow = createServiceFlow({ spawn: rec.fn, timeoutMs: 700 });
  const events = [];
  flow.subscribe((state) => events.push(state));
  // run1：握手超时 → exited(-1)、handshake-failed；子进程已被 kill，但它的 exit 事件什么时候派发不定
  assert.deepEqual(
    await flow.start({ repo: "old-1", command: [process.execPath, FAKE], env: envWith({ FAKE_SERVICE_MODE: "silent" }) }),
    { ok: false, reason: "handshake-failed" },
  );
  assert.equal(flow.state().kind, "exited");
  assert.equal(rec.children.length, 1);
  // run2：立刻再起，握手成功
  assert.deepEqual(
    await flow.start({ repo: "new-2", command: [process.execPath, FAKE], env: envWith({ FAKE_SERVICE_MODE: "ok" }) }),
    { ok: true, value: null },
  );
  assert.equal(flow.state().kind, "running");
  // run1 的子进程真的退出之后（旧 exit 监听随时可能派发），run2 仍要是 running
  await waitFor(
    "旧子进程退出",
    () => rec.children[0].exitCode !== null || rec.children[0].signalCode !== null,
    5000,
  );
  await new Promise((resolve) => setTimeout(resolve, 250));
  assert.equal(flow.state().kind, "running", "旧 run 的 exit 回调不许把新 run 改成 exited");
  assert.equal(events.length, 4, JSON.stringify(events));
  await flow.stop();
  await waitFor("run2 exited", () => flow.state().kind === "exited", 8000);
});

test("D01-d starting 期间再 start 仍回 busy 且不起第二个进程", async () => {
  const rec = recordingSpawn();
  const flow = createServiceFlow({ spawn: rec.fn, timeoutMs: 8000 });
  const events = [];
  flow.subscribe((state) => events.push(state));
  const startPromise = flow.start({
    repo: "busy-1",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "silent" }),
  });
  await waitFor("starting", () => events.length >= 1 && events[0].kind === "starting");
  assert.deepEqual(
    await flow.start({ repo: "busy-2", command: [process.execPath, FAKE] }),
    { ok: false, reason: "busy" },
  );
  assert.equal(rec.children.length, 1, "busy 不许起第二个进程");
  await flow.abort();
  await waitFor("abort 后 exited", () => flow.state().kind === "exited", 8000);
  await startPromise;
});
'''


PROBE_RESTART = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { createSettingsStore, DEFAULT_SETTINGS } = require("@SHELL@/src/settings.js");
const { createShellApi } = require("@SHELL@/src/shellapi.js");
const { serviceCommand } = require("@SHELL@/src/service.js");

function makeController() {
  const listeners = new Set();
  const ctl = {
    starts: [],
    currentState: { kind: "idle" },
    nextStart: { ok: true, value: null },
    async start(arg) {
      ctl.starts.push(JSON.parse(JSON.stringify(arg)));
      return ctl.nextStart;
    },
    async stop() {
      return { exited: true, code: 0, signal: null };
    },
    async abort() {},
    state() {
      return ctl.currentState;
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
  return ctl;
}

function makeHarness(opts) {
  const o = opts || {};
  const b = fs.mkdtempSync(path.join(os.tmpdir(), "t035-gate-api-"));
  const userData = path.join(b, "userData");
  fs.mkdirSync(userData);
  const store = createSettingsStore({ dir: userData });
  const alphaDir = path.join(b, "alpha");
  const betaDir = path.join(b, "beta");
  const kitDir1 = path.join(b, "kit1");
  fs.mkdirSync(alphaDir);
  fs.mkdirSync(betaDir);
  fs.mkdirSync(kitDir1);
  const t1 = path.join(b, "t1");
  const t2 = path.join(b, "t2");
  const s = JSON.parse(JSON.stringify(DEFAULT_SETTINGS));
  s.repos = [
    { id: "repo-alpha", name: "alpha", path: alphaDir, lastOpened: null },
    { id: "repo-beta", name: "beta", path: betaDir, lastOpened: null },
  ];
  s.currentRepo = "repo-alpha";
  s.transcriptDirs = [
    { id: "dir-1", path: t1 },
    { id: "dir-2", path: t2 },
  ];
  if (o.kitPath) s.kitPath = kitDir1;
  store.save(s);

  const pythonPath = "/auto/python-exe";
  const kitCalls = [];
  const state = { kitFailDirs: new Set(), chooseDir: null };
  const probe = {
    async probePython(commandArgs) {
      return { ok: true, version: "3.12.9", path: "/custom/python-exe" };
    },
    async probeKit(p, dir) {
      kitCalls.push([p, dir]);
      if (state.kitFailDirs.has(dir)) return { ok: false };
      return { ok: true, version: "2.12.0" };
    },
    async detectPython() {
      if (o.pythonMissing) return { status: "missing", source: "auto", path: "", version: "" };
      return { status: "ok", source: "auto", path: pythonPath, version: "3.13.1" };
    },
    async detectKit() {
      return { status: "missing", source: "repo", path: "", version: "" };
    },
  };
  const ctl = o.noController ? null : makeController();
  const inject = {
    store,
    appVersion: "9.9.9",
    probe,
    chooseDirectory: async () => state.chooseDir,
  };
  if (ctl !== null) {
    inject.service = ctl;
    if (!o.noAssets) inject.assets = "/assets/root";
  }
  const api = createShellApi(inject);
  return { b, api, store, ctl, probe, kitCalls, alphaDir, betaDir, kitDir1, t1, t2, state };
}

test("idle → no-previous 且不起进程", async () => {
  const h = makeHarness({ kitPath: true });
  h.ctl.currentState = { kind: "idle" };
  assert.deepEqual(await h.api.restartService(), { ok: false, reason: "no-previous" });
  assert.equal(h.ctl.starts.length, 0, "不许起进程");
});

test("没注入控制器 → no-previous 且不抛错", async () => {
  const h = makeHarness({ noController: true, kitPath: true });
  assert.deepEqual(await h.api.restartService(), { ok: false, reason: "no-previous" });
});

test("starting → 幂等回 ok 且不起进程", async () => {
  const h = makeHarness({ kitPath: true });
  h.ctl.currentState = { kind: "starting", repo: "repo-beta" };
  assert.deepEqual(await h.api.restartService(), { ok: true, value: null });
  assert.equal(h.ctl.starts.length, 0, "starting 期间不许再起进程");
});

test("running → 幂等回 ok 且不起进程", async () => {
  const h = makeHarness({ kitPath: true });
  h.ctl.currentState = { kind: "running", repo: "repo-beta", pid: 9, startedAt: "t" };
  assert.deepEqual(await h.api.restartService(), { ok: true, value: null });
  assert.equal(h.ctl.starts.length, 0, "running 期间不许再起进程");
});

test("exited 且仓库已从设置里移除 → unknown-repo 且不起进程", async () => {
  const h = makeHarness({ kitPath: true });
  const r = await h.api.saveSettings({ removeRepo: "repo-beta" });
  assert.equal(r.ok, true, JSON.stringify(r));
  h.ctl.currentState = { kind: "exited", repo: "repo-beta", exitCode: 3, at: 1 };
  assert.deepEqual(await h.api.restartService(), { ok: false, reason: "unknown-repo" });
  assert.equal(h.ctl.starts.length, 0);
});

test("exited 且 Python 不可用 → python-missing 且不起进程", async () => {
  const h = makeHarness({ pythonMissing: true, kitPath: true });
  h.ctl.currentState = { kind: "exited", repo: "repo-beta", exitCode: 3, at: 1 };
  assert.deepEqual(await h.api.restartService(), { ok: false, reason: "python-missing" });
  assert.equal(h.ctl.starts.length, 0);
});

test("exited 且 kit 按目标仓库算不可用 → kit-missing 且不起进程", async () => {
  const h = makeHarness();
  h.state.kitFailDirs.add(h.betaDir);
  h.ctl.currentState = { kind: "exited", repo: "repo-beta", exitCode: 3, at: 1 };
  assert.deepEqual(await h.api.restartService(), { ok: false, reason: "kit-missing" });
  assert.equal(h.ctl.starts.length, 0);
  assert.ok(h.kitCalls.length >= 1, "现场探测要被调用");
  for (const [p, dir] of h.kitCalls) {
    assert.equal(dir, h.betaDir, "kit 只许按目标仓库的目录探测：" + dir);
  }
});

test("exited 且没有产物根 → no-service 且不起进程", async () => {
  const h = makeHarness({ noAssets: true, kitPath: true });
  h.ctl.currentState = { kind: "exited", repo: "repo-beta", exitCode: 3, at: 1 };
  assert.deepEqual(await h.api.restartService(), { ok: false, reason: "no-service" });
  assert.equal(h.ctl.starts.length, 0);
});

test("exited 条件齐 → 走 startService(exited 里那个 repo，不是 currentRepo)，命令按当前设置算", async () => {
  const h = makeHarness({ kitPath: true });
  // 夹具自检：当前仓库是 alpha；起过服务的是 beta
  assert.equal(h.store.load().settings.currentRepo, "repo-alpha");
  // 先经 pickKit 把 kitPath 换成 kit2（选择框给什么存什么），重启的命令要跟着变
  const kitDir2 = path.join(h.b, "kit2");
  fs.mkdirSync(kitDir2);
  h.state.chooseDir = kitDir2;
  const picked = await h.api.pickKit();
  assert.equal(picked.ok, true, JSON.stringify(picked));
  assert.equal(h.store.load().settings.kitPath, kitDir2, "夹具自检：kitPath 真的换成 kit2");

  h.ctl.currentState = { kind: "exited", repo: "repo-beta", exitCode: 3, at: 1 };
  assert.deepEqual(await h.api.restartService(), { ok: true, value: null });
  assert.equal(h.ctl.starts.length, 1, "要真的起一次进程");
  const arg = h.ctl.starts[0];
  assert.equal(arg.repo, "repo-beta", "重启的是 exited 状态里那个 repo id");
  const expected = serviceCommand({
    python: ["/auto/python-exe"],
    kit: kitDir2,
    repo: h.betaDir,
    assets: "/assets/root",
    transcripts: [h.t1, h.t2],
  });
  assert.deepEqual(arg.command, expected);
  const env = arg.env;
  assert.ok(
    env === process.env || JSON.stringify(env) === JSON.stringify(process.env),
    "env 用 process.env",
  );
});

test("exited 且控制器失败 → 信封原样回传（handshake-failed / start-failed）", async () => {
  const h1 = makeHarness({ kitPath: true });
  h1.ctl.currentState = { kind: "exited", repo: "repo-beta", exitCode: 3, at: 1 };
  h1.ctl.nextStart = { ok: false, reason: "handshake-failed" };
  assert.deepEqual(await h1.api.restartService(), { ok: false, reason: "handshake-failed" });
  assert.equal(h1.ctl.starts.length, 1, "控制器的信封要原样回传，不是替它编一个 reason");
  const h2 = makeHarness({ kitPath: true });
  h2.ctl.currentState = { kind: "exited", repo: "repo-beta", exitCode: 3, at: 1 };
  h2.ctl.nextStart = { ok: false, reason: "start-failed" };
  assert.deepEqual(await h2.api.restartService(), { ok: false, reason: "start-failed" });
});
'''


PROBE_HOSTRELAY = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { createHostRelay } = require("@SHELL@/src/hostrelay.js");
const { registerHostIpc } = require("@SHELL@/src/ipc.js");
const { createServiceFlow } = require("@SHELL@/src/serviceflow.js");

const FAKE = path.join("@SHELL@", "tests", "fixtures", "fake-service.js");
const FAKE_EXIT = path.join("@SHELL@", "tests", "fixtures", "fake-service-exit.js");

const METHODS = ["reauth", "openSecretWindow", "openExternal", "reveal", "notify", "openSettings", "saveTheme"];

function makeHost(tag) {
  const calls = {};
  const host = {};
  for (const name of METHODS) {
    calls[name] = [];
    host[name] = async (...args) => {
      calls[name].push(args);
      return { ok: true, value: tag + ":" + name };
    };
  }
  return { host, calls };
}

function envWith(extra) {
  return Object.assign({}, process.env, extra);
}

async function waitFor(what, predicate, timeoutMs) {
  const deadline = Date.now() + (timeoutMs || 8000);
  for (;;) {
    if (predicate()) return;
    if (Date.now() > deadline) throw new Error("等不到：" + what);
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
}

test("形状：{host, senderAllowed, use, clear}，host 是那七个方法", () => {
  const relay = createHostRelay();
  assert.deepEqual(Object.keys(relay).sort(), ["clear", "host", "senderAllowed", "use"]);
  assert.deepEqual(Object.keys(relay.host).sort(), [...METHODS].sort());
});

test("没有当前 host：七个方法都回 forbidden 不抛错；senderAllowed 为 false", async () => {
  const relay = createHostRelay();
  for (const name of METHODS) {
    assert.deepEqual(await relay.host[name]("a", 2), { ok: false, reason: "forbidden" }, name + " 不许抛错");
  }
  assert.equal(relay.senderAllowed({}), false);
});

test("use 替换不叠加：实参原样转给当前 host；clear 之后回到 forbidden", async () => {
  const relay = createHostRelay();
  const a = makeHost("A");
  const b = makeHost("B");
  relay.use(a.host, (ev) => ev.tag === "a");
  assert.deepEqual(await relay.host.reveal("p/q"), { ok: true, value: "A:reveal" });
  assert.deepEqual(a.calls.reveal[0], ["p/q"], "实参要原样转发");
  assert.equal(relay.senderAllowed({ tag: "a" }), true);
  assert.equal(relay.senderAllowed({ tag: "b" }), false);
  relay.use(b.host, (ev) => ev.tag === "b");
  assert.deepEqual(await relay.host.reveal("x"), { ok: true, value: "B:reveal" });
  assert.equal(a.calls.reveal.length, 1, "换成新 host 之后旧 host 不再被调");
  assert.equal(b.calls.reveal.length, 1);
  assert.equal(relay.senderAllowed({ tag: "a" }), false, "来源检查也要换成新的");
  // 实参个数不丢：openSecretWindow 收两个、notify 收一个
  await relay.host.openSecretWindow("http://x/y", "job-7");
  await relay.host.notify("attempt-finished");
  assert.deepEqual(b.calls.openSecretWindow[0], ["http://x/y", "job-7"]);
  assert.deepEqual(b.calls.notify[0], ["attempt-finished"]);
  relay.clear();
  assert.deepEqual(await relay.host.notify("attempt-finished"), { ok: false, reason: "forbidden" });
  assert.equal(relay.senderAllowed({ tag: "b" }), false);
  assert.equal(a.calls.notify.length, 0);
  assert.equal(b.calls.notify.length, 1, "clear 之后调用不再进 host：计数停在 clear 前的那一次");
});

test("senderAllowed 的检查抛错按 false", () => {
  const relay = createHostRelay();
  relay.use(makeHost("C").host, () => {
    throw new Error("boom");
  });
  assert.equal(relay.senderAllowed({}), false);
});

test("重入：第一次意外退出、第二次起服务成功，注册次数仍是 7、调用进第二个 host", async () => {
  const handlers = new Map();
  let registrations = 0;
  const im = {
    handle: (ch, fn) => {
      if (handlers.has(ch)) throw new Error("通道被重复注册：" + ch);
      handlers.set(ch, fn);
      registrations += 1;
    },
  };
  const relay = createHostRelay();
  registerHostIpc(im, relay.host, relay.senderAllowed);
  assert.equal(registrations, 7, "registerHostIpc 注册七条通道");
  assert.equal(handlers.size, 7);
  // 还没有当前 host：调用经来源检查回 forbidden
  assert.deepEqual(
    await handlers.get("themis-host:notify")({ tag: "x" }, "attempt-finished"),
    { ok: false, reason: "forbidden" },
  );

  const first = makeHost("host1");
  const second = makeHost("host2");
  let runCount = 0;
  const flow = createServiceFlow({
    onRunning: async () => {
      runCount += 1;
      if (runCount === 1) relay.use(first.host, () => true);
      else relay.use(second.host, () => true);
    },
  });

  // 第一次：握手成功后服务自己退出（意外退出）
  assert.deepEqual(
    await flow.start({ repo: "r1", command: [process.execPath, FAKE_EXIT] }),
    { ok: true, value: null },
  );
  await waitFor("run1 exited", () => flow.state().kind === "exited", 8000);
  assert.equal(flow.state().exitCode, 3);
  const ev = { tag: "run1" };
  assert.deepEqual(
    await handlers.get("themis-host:notify")(ev, "attempt-finished"),
    { ok: true, value: "host1:notify" },
    "第一次起服务后调用要进第一个 host（经 relay 转给当前 host）",
  );

  // 第二次：真起服务成功（exited 之后能再 start）
  assert.deepEqual(
    await flow.start({ repo: "r2", command: [process.execPath, FAKE], env: envWith({ FAKE_SERVICE_MODE: "ok" }) }),
    { ok: true, value: null },
  );
  assert.equal(flow.state().kind, "running");
  // registerHostIpc 没有被第二次调用（否则 im.handle 早就抛错了）
  assert.equal(registrations, 7, "第二次起服务不许再注册宿主 IPC");
  assert.equal(handlers.size, 7);
  assert.deepEqual(
    await handlers.get("themis-host:reveal")(ev, "runs/x/summary.md"),
    { ok: true, value: "host2:reveal" },
    "第二次起服务后调用要进第二个 host",
  );
  assert.equal(second.calls.reveal.length, 1);
  assert.deepEqual(second.calls.reveal[0], ["runs/x/summary.md"]);
  assert.equal(first.calls.reveal.length, 0, "旧 host 不再被调");
  assert.equal(relay.senderAllowed(ev), true, "来源检查转给当前那份");
  await flow.stop();
  await waitFor("run2 exited", () => flow.state().kind === "exited" && flow.state().exitCode === 0, 8000);
});
'''


PROBE_SHELLPROTOCOL = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const proto = require("@SHELL@/src/shellprotocol.js");

test("SHELL_STATUS_URL 逐字且 isShellPageUrl 认它；既有常量不变", () => {
  assert.equal(proto.SHELL_STATUS_URL, "themis-shell://app/index.html#/service-status");
  assert.equal(proto.isShellPageUrl(proto.SHELL_STATUS_URL), true);
  assert.equal(proto.SHELL_SCHEME, "themis-shell");
  assert.equal(proto.SHELL_HOST, "app");
  assert.equal(proto.SHELL_START_URL, "themis-shell://app/index.html#/first-run");
});
'''


# --------------------------------------------------------------------------- 探针包装

def test_p01_probe_serviceflow_runs():
    """D01：serviceflow 按 run 记状态（node --test 探针，真起子进程）——exited 之后能再 start、
    byShell 按 run 算、旧 run 的子进程退出不污染新 run、starting/running 时再 start 回 busy。"""
    _expect_probe_pass("t035-serviceflow-runs", PROBE_SERVICEFLOW, timeout=300.0)


def test_p02_probe_restart_service():
    """D02：restartService 按 serviceState() 决定（node --test 探针，假控制器 + 假 probe）——
    no-previous/幂等/按当前设置重启/失败 reason 与 startService 一致/信封原样回传。"""
    _expect_probe_pass("t035-restart-service", PROBE_RESTART)


def test_p03_probe_hostrelay():
    """D03：hostrelay 纯模块 + 重入（node --test 探针）——接口形状、forbidden 兜底、use/clear
    语义、检查抛错按 false；真 createServiceFlow 重入：注册次数仍是 5、第二次 start 成功、
    调用进第二个 host。"""
    _expect_probe_pass("t035-hostrelay", PROBE_HOSTRELAY, timeout=300.0)


def test_p04_probe_shellprotocol_status_url():
    """D05 配套：SHELL_STATUS_URL 的值与 isShellPageUrl（node --test 探针）。"""
    _expect_probe_pass("t035-shellprotocol", PROBE_SHELLPROTOCOL)
