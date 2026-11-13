"""T033 战前门禁：桌面端外壳第 5 片「从外壳页起服务、service-state 事件、starting 期间中止、
意外退出以 1 退出（A 片过渡）」的黑盒基准测试（合同 t033-desktop-shell-service v1，基线 a8a4924——
src/serviceflow.js、tests/serviceflow.test.js、tests/fixtures/fake-service-exit.js 都还不存在，
shellipc 没有 SERVICE_STATE_CHANNEL，shell-preload 的 on 不注册监听，shellapi 的 startService 还是
占位）。

被测对象：``src/serviceflow.js``（服务状态机 idle→starting→running/exited、退出码映射、订阅、
start/stop/abort/state、控制令牌只进 onRunning 实参）、``src/shellipc.js`` 的新常量
``SERVICE_STATE_CHANNEL``（不进 SHELL_CHANNELS，九个 invoke 通道原样不动）、``shell-preload.js``
的 ``on``（只注册一个 ipcRenderer.on、独立订阅、监听函数只收 state 一个实参）、``src/shellapi.js``
的 ``startService``（按仓库 id 查设置、python/kit 按目标仓库算、命令形状与带参数那条路同一个
``serviceCommand``、busy/幂等、reason 词表）与 ``on`` 的真订阅，``main.js`` 外壳分支的接线
（控制器注入、事件经 webContents.send 只发 state、abort/stop、退出码文案），``package.json`` 的
``scripts.test`` 与 README 的新内容。

基线（a8a4924）上这些符号与文件都不存在，所以失败都落在「文件不存在」「标记不在」与探针子进程
退出码非 0 这类断言上，不是收集失败：模块级只导入标准库，仓库文件的读取与探针的运行都发生在
用例函数里。探针是自包含的 ``node --test`` 文件（Node 24 自带，不需要 npm ci，也不 require
electron 本体）。Python 把探针源码写进系统临时目录、以仓库根为 cwd 运行、用完即删；探针里的
被测模块用绝对路径 require（``@SHELL@`` 占位符替换）。serviceflow 探针真起子进程（现有的
``tests/fixtures/fake-service.js`` 与本片新增的 ``tests/fixtures/fake-service-exit.js``），
不 mock child_process。

结构（编号大致对应合同 DoD 的 D01–D11）：

- 静态断言（``test_s*``，不需要任何依赖）：
  - S01/D10：合同 Scope 点名的 3 个新文件都在位。
  - S02/D09/D10：``package.json`` 只许改 ``scripts.test``——tap 开关仍在文件清单之前、显式列出
    ``tests/`` 下每一个 ``*.test.js``（数据驱动）且本片新增的 ``tests/serviceflow.test.js`` 点名
    在列、20 份既有测试一条没删没改名、``tests/fixtures/`` 下没有 ``*.test.js``；依赖与锁文件不动。
  - S03/D07：静态扫描——``require('electron')`` 只许 main.js、preload.js、shell-preload.js；
    新纯模块 ``src/serviceflow.js`` 在位且不 require electron；``ipcMain.on`` 与
    ``ipcRenderer.send`` 在 desktop/shell 下全禁（任何 .js、包括测试与夹具）；main.js 与 src/**
    的词面禁令照 T025/T026/T030；shell-preload.js 仍自包含、恰好一次 exposeInMainWorld 且名字
    themisShell、通道名字面量写在文件里。
  - S04/D02/D03/D06/D07：main.js 外壳分支的接线——require 并调用 createServiceFlow、事件经
    SERVICE_STATE_CHANNEL 用 webContents.send 发出且发前查 isDestroyed、createShellApi 多注入
    service 与 assets、byShell 区分意外退出、starting 期间 abort、用户关服务窗口 stop、「服务
    没有以 0 正常退出」同句文案；既有形状（new BrowserWindow 恰好一处、launchMode 早于
    runShell、runShell 五键）不破。
  - S05（过渡）/D06：A 片的过渡行为——服务意外退出写一行 ``ERROR: 服务意外退出（退出码 N）``
    并以 1 退出。站主 2026-11-13 为 T035（意外退出回服务状态页）退役了这条。
  - S06/D11：README 外壳页一节写清新行为（on('service-state') 真订阅、手工冒烟注明点「启动」
    要等 T032）。
- 探针断言（``test_p*``，跑 node --test）：
  - P01/D02/D05/D07/D08：serviceflow——真起子进程：成功路 starting→running（pid/startedAt）、
    onRunning 拿到令牌而状态与事件里没有令牌、stop 以 0 收服务且 byShell=true、exit2 握手前退出
    exitCode=2、坏握手与握手超时 exitCode=-1 回 handshake-failed、spawn 失败回 start-failed、
    握手成功后服务自己退出（fake-service-exit）exitCode=3 且 byShell=false、starting 期间
    abort() 子进程真的退出、订阅相互独立且退订只删自己那条、onRunning 抛错收服务回 start-failed。
  - P02/D01：shellapi——unknown-repo 不起进程、python-missing、kit-missing（kit 按目标仓库现场
    探测，不读当前仓库缓存）、命令形状与 serviceCommand 逐字一致（python=[python.path]、
    transcripts 各条 path）、控制器的信封原样回传、同仓库幂等 ok、别的仓库 busy、
    getState().service 取控制器状态（没注入时 idle）、on 的真订阅与退订、no-service 兜底。
  - P03/D03：SERVICE_STATE_CHANNEL 值逐字、不在 SHELL_CHANNELS、九个通道名字与顺序不变、
    registerShellIpc 仍只注册九个 handle、preload 源码里的字面量与常量一致。
  - P04/D04：shell-preload 的 on——模块加载时只注册一个 ipcRenderer.on（频道是那个字面量）、
    监听函数只收 state 一个实参（不把事件对象交给页面）、两个订阅都收到、退订只删自己那条、
    重复退订与再发收不到、别的事件名同步回空退订函数、on 与退订都不发 IPC；假 electron 不提供
    removeListener/off（不许依赖它们）。
  - P05（过渡）：restartService 在 A 片仍回 not-implemented、不进控制器。站主 2026-11-13 为 T035 退役了这条与它的探针。

合同没写死、门禁端按最合理读法定下的地方（交付信「下游须知」逐条列出）：onRunning 经
createServiceFlow 的注入项给出（实参至少含 origin/control/repo）；stop() 的返回值只断言
exited/code/signal 三个字段，不断言键集合恰好三个；起进程后的失败按「信封兑现时状态已是
exited」断言次序；README 的 needle 只取合同点名的 T032 与 on('service-state'。
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
    "src/serviceflow.js",
    "tests/serviceflow.test.js",
    "tests/fixtures/fake-service-exit.js",
)

NEW_TEST_FILES = ("tests/serviceflow.test.js",)

# T025/T026/T028/T030 已有的 20 份测试文件：一条也没删没改名（D10）
PREEXISTING_TEST_FILES = (
    "tests/args.test.js", "tests/package.test.js", "tests/python.test.js", "tests/handshake.test.js",
    "tests/service.test.js", "tests/window.test.js", "tests/core.test.js", "tests/control.test.js",
    "tests/host.test.js", "tests/hostcheck.test.js", "tests/ipc.test.js", "tests/preload.test.js",
    "tests/settings.test.js", "tests/detect.test.js", "tests/shellapi.test.js", "tests/shellshape.test.js",
    "tests/launch.test.js", "tests/shellprotocol.test.js", "tests/shellipc.test.js", "tests/shellpreload.test.js",
)

REQUIRE_ELECTRON_RE = re.compile(r"require\(\s*['\"]electron['\"]\s*\)")
REQUIRE_RELATIVE_RE = re.compile(r"""require\(\s*['"]\.""")
REQUIRE_NODE_RE = re.compile(r"""require\(\s*['"]node:""")

# T025 的词面禁令（站主收窄后）：src/** 与 main.js 里不许出现，注释也不行；src/settings.js 只许
# writeFileSync/renameSync/mkdirSync/unlinkSync 四个（T028 起的豁免）
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

WORD_RULES = (
    (re.compile(r"\bshell\s*\.\s*openExternal\b"), "shell.openExternal", ("main.js",)),
    (re.compile(r"\bshowItemInFolder\b"), "showItemInFolder", ("main.js",)),
    (re.compile(r"\bdialog\b"), "dialog", ("main.js",)),
    (re.compile(r"\bNotification\b"), "Notification", ("main.js",)),
)

ELECTRON_ALLOWED = ("main.js", "preload.js", "shell-preload.js")
IPC_BANS = (
    (re.compile(r"\bipcMain\s*\.\s*on\b"), "ipcMain.on"),
    (re.compile(r"\bipcRenderer\s*\.\s*send\b"), "ipcRenderer.send"),
)


def _shell_read(rel: str) -> str:
    p = SHELL / rel
    assert p.is_file(), f"desktop/shell/{rel} 不存在"
    return p.read_text(encoding="utf-8")


def _scan_files():
    """扫描范围：顶层 main.js / preload.js / shell-preload.js + src/** + tests/**（与 T030 相同）。"""
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
    with tempfile.TemporaryDirectory(prefix="t033-gate-") as td:
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


# --------------------------------------------------------------------------- 静态断言

def test_s01_contract_files():
    """D10/Scope：合同点名的 3 个新文件都在位。"""
    for rel in CONTRACT_FILES:
        assert (SHELL / rel).is_file(), f"desktop/shell/{rel} 不存在"
    # 夹具文件名不以 .test.js 结尾（合同第 8 节）
    assert (SHELL / "tests" / "fixtures" / "fake-service-exit.js").name.endswith(".js")
    assert not (SHELL / "tests" / "fixtures" / "fake-service-exit.js").name.endswith(".test.js")


def test_s02_package_json_and_lock():
    """D09/D10：package.json 只许改 scripts.test（tap 开关、点出新测试、数据驱动全量点名、既有
    20 份一条没删），其余字段、依赖与锁文件不动；夹具目录里不许有 *.test.js。"""
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
    """D07：require('electron') 只许三个文件；新纯模块 src/serviceflow.js 在位且不 require
    electron；ipcMain.on 与 ipcRenderer.send 在 desktop/shell 下全禁（包括新文件与测试）；main.js
    与 src/** 的词面禁令照 T025/T026/T030；shell-preload.js 仍自包含、恰好一次 exposeInMainWorld
    且名字 themisShell、通道名字面量写在文件里。"""

    # 本片的新纯模块（不 require electron——它要能被包内测试直接加载）
    flow_path = SHELL / "src" / "serviceflow.js"
    assert flow_path.is_file(), "desktop/shell/src/serviceflow.js 不存在"
    flow_text = flow_path.read_text(encoding="utf-8")
    assert not REQUIRE_ELECTRON_RE.search(flow_text), "src/serviceflow.js 不许 require electron"

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

    # shell-preload 的自包含、暴露面与通道字面量
    shell_preload = _shell_read("shell-preload.js")
    assert REQUIRE_ELECTRON_RE.search(shell_preload), "shell-preload.js 必须 require('electron')"
    assert not REQUIRE_RELATIVE_RE.search(shell_preload), "shell-preload.js 不许 require 相对路径（自包含）"
    assert not REQUIRE_NODE_RE.search(shell_preload), "shell-preload.js 不许 require node: 模块"
    assert len(re.findall(r"exposeInMainWorld", shell_preload)) == 1, (
        "shell-preload.js 的 exposeInMainWorld 只许出现一次"
    )
    assert re.search(r"""exposeInMainWorld\s*\(\s*['"]themisShell['"]""", shell_preload), (
        "shell-preload.js 的 exposeInMainWorld 名字必须是 themisShell"
    )
    assert "themisHost" not in shell_preload, "shell-preload.js 不许暴露 themisHost"
    assert '"themis-shell:service-state"' in shell_preload, (
        "shell-preload.js 里通道名要写字面量 \"themis-shell:service-state\"（preload 不能 require 相对路径）"
    )


def test_s04_main_js_service_wiring():
    """D02/D03/D06/D07：main.js 外壳分支的接线——新纯模块被 require 并实例化、事件经
    SERVICE_STATE_CHANNEL 用 webContents.send 只发 state（发前查窗口销毁）、createShellApi 多注入
    service 与 assets、byShell 区分意外退出、starting 期间先 abort 再退、用户关服务窗口先 stop、
    退出码文案与带参数那条路同句；既有形状（new BrowserWindow 恰好一处、launchMode 早于
    runShell、runShell 五键）不破。"""
    text = _shell_read("main.js")

    # 新纯模块必须真的被 require 并实例化（否则成了死代码）
    assert re.search(r"""require\(\s*['"]\.\/src\/serviceflow(\.js)?['"]\s*\)""", text), (
        "main.js 没有 require ./src/serviceflow.js"
    )
    assert re.search(r"\bcreateServiceFlow\s*\(", text), "main.js 没有调 createServiceFlow("

    # 事件：SERVICE_STATE_CHANNEL + webContents.send，只发 state 一个实参，发前查窗口销毁
    assert "SERVICE_STATE_CHANNEL" in text, "main.js 没有引用 SERVICE_STATE_CHANNEL"
    assert re.search(r"webContents\s*\.\s*send\s*\(", text), (
        "main.js 没有 webContents.send（service-state 事件只经它发给外壳页窗口）"
    )
    assert re.search(r"\bisDestroyed\s*\(\s*\)", text), "发送前要查 win.isDestroyed()，窗口销毁就跳过"

    # createShellApi 的注入项多了 service（控制器）与 assets（产物根）
    m = re.search(r"\bcreateShellApi\s*\(", text)
    assert m, "main.js 没有 createShellApi( 调用"
    arg = _call_arg_text(text, m.start())
    assert re.search(r"\bservice\s*:", arg), f"createShellApi 的注入项里要有 service（控制器）：{arg[:160]!r}"
    assert re.search(r"\bassets\s*:", arg), f"createShellApi 的注入项里要有 assets（产物根）：{arg[:160]!r}"

    # 意外退出的判定看 byShell（第 6 节），不看退出码
    assert "byShell" in text, "main.js 要用 info.byShell 区分外壳自己结束的与服务自己退出的"

    # starting 期间用户关外壳页 → 先中止子进程；用户关服务窗口 → 先收服务
    assert re.search(r"\.\s*abort\s*\(\s*\)", text), "main.js 要在 starting 期间关外壳页时先中止子进程（flow.abort()）"
    assert re.search(r"\.\s*stop\s*\(\s*\)", text), "main.js 要在用户关服务窗口时先收服务（flow.stop()）"

    # 用户关服务窗口后服务不以 0 退出：与带参数那条路同一句文案
    assert "服务没有以 0 正常退出" in text, "外壳分支要写同一句 ERROR：服务没有以 0 正常退出"

    # 既有形状不破：new BrowserWindow 恰好一处；launchMode 在 runShell 之前；runShell 五键不变
    assert len(re.findall(r"new\s+BrowserWindow", text)) == 1, "main.js 的 new BrowserWindow 必须恰好一处"
    launch_at = text.find("launchMode(")
    run_at = text.find("runShell(")
    assert launch_at != -1 and run_at != -1, "main.js 缺 launchMode( 或 runShell( 的调用"
    assert launch_at < run_at, "launchMode 的判定必须发生在调用 runShell 之前"
    run_arg = _call_arg_text(text, run_at)
    for key in ("argv", "io", "openWindow", "onServiceReady", "env"):
        assert re.search(rf"\b{key}\b", run_arg), f"runShell 的调用仍要收 {key}：{run_arg[:200]!r}"


def test_s06_readme_shell_service():
    """D11：README 的「外壳页」一节写清本片新行为——on('service-state', listener) 真订阅主进程
    发来的状态、手工冒烟的新条目注明页面上点「启动」要等 T032 落地。既有 needle 由 T025/T026/
    T028/T030 的门禁在 R01 里继续钉住，这里不重复抄清单。"""
    text = _shell_read("README.md")
    for needle in ("on('service-state'", "T032"):
        assert needle in text, f"README 缺本片要点「{needle}」"


# --------------------------------------------------------------------------- 探针断言（node --test）

PROBE_SERVICEFLOW = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { createServiceFlow } = require("@SHELL@/src/serviceflow.js");

const FAKE = path.join("@SHELL@", "tests", "fixtures", "fake-service.js");
const FAKE_EXIT = path.join("@SHELL@", "tests", "fixtures", "fake-service-exit.js");

// 借 spawn 选项拿到子进程的引用：createServiceFlow 会把它包一层再传给 service.startService，
// 我们在外面再包一层只为了记录 child（与被测的包装层互不干扰）
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

function noToken(value) {
  return !JSON.stringify(value).includes("ctrl-tok");
}

test("成功路：starting → running（pid/startedAt）、onRunning 拿到令牌、stop 以 0 收服务、byShell=true", async () => {
  const rec = recordingSpawn();
  let onRunningArg = null;
  const flow = createServiceFlow({
    spawn: rec.fn,
    onRunning: (arg) => {
      onRunningArg = arg;
    },
  });
  const events = [];
  const infos = [];
  flow.subscribe((state, info) => {
    events.push(JSON.parse(JSON.stringify(state)));
    infos.push(info);
  });
  assert.deepEqual(flow.state(), { kind: "idle" }, "初始状态是 idle");
  const envelope = await flow.start({
    repo: "repo-id-1",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "ok" }),
  });
  assert.deepEqual(envelope, { ok: true, value: null });
  assert.notEqual(onRunningArg, null, "成功时 onRunning 要被调用");
  assert.equal(onRunningArg.control, "ctrl-tok-XYZ", "控制令牌只进 onRunning 的实参");
  assert.equal(onRunningArg.repo, "repo-id-1");
  assert.equal(typeof onRunningArg.origin, "string", "onRunning 要带 origin（createHost 要用）");
  assert.equal(events.length, 2, JSON.stringify(events));
  assert.deepEqual(events[0], { kind: "starting", repo: "repo-id-1" });
  assert.equal(events[1].kind, "running");
  assert.equal(events[1].repo, "repo-id-1");
  assert.equal(events[1].pid, 4242, "pid 取握手里的 pid");
  assert.ok(Number.isFinite(Date.parse(events[1].startedAt)), "startedAt 要是 ISO 串");
  assert.deepEqual(flow.state(), events[1]);
  const stopResult = await flow.stop();
  assert.equal(stopResult.exited, true, JSON.stringify(stopResult));
  assert.equal(stopResult.code, 0, JSON.stringify(stopResult));
  assert.equal(stopResult.signal, null, JSON.stringify(stopResult));
  await waitFor("stop 之后的 exited 状态", () => events.length >= 3 && events[2].kind === "exited");
  assert.equal(events[2].repo, "repo-id-1");
  assert.equal(events[2].exitCode, 0);
  assert.equal(typeof events[2].at, "number", "at 是数字毫秒");
  assert.equal(infos[2].byShell, true, "外壳 stop 触发的 exited，byShell 要是 true");
  assert.equal(flow.state().kind, "exited");
  // 控制令牌不进任何状态
  for (const s of events) assert.ok(noToken(s), JSON.stringify(s));
  assert.ok(noToken(flow.state()));
});

test("握手前退出（exit2）→ exited 带数字码 2、回 handshake-failed、信封兑现时状态已是 exited", async () => {
  const flow = createServiceFlow({});
  const events = [];
  flow.subscribe((state) => events.push(state));
  const envelope = await flow.start({
    repo: "r-exit2",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "exit2" }),
  });
  assert.deepEqual(envelope, { ok: false, reason: "handshake-failed" });
  assert.equal(events.length, 2, JSON.stringify(events));
  assert.deepEqual(events[0], { kind: "starting", repo: "r-exit2" });
  assert.equal(events[1].kind, "exited", "起进程之后的失败要先发 exited 再回信封");
  assert.equal(events[1].repo, "r-exit2");
  assert.equal(events[1].exitCode, 2);
  assert.equal(typeof events[1].at, "number");
  assert.deepEqual(flow.state(), { kind: "exited", repo: "r-exit2", exitCode: 2, at: events[1].at });
});

test("坏握手（bad）→ exited exitCode=-1、handshake-failed", async () => {
  const flow = createServiceFlow({});
  const events = [];
  flow.subscribe((state) => events.push(state));
  const envelope = await flow.start({
    repo: "r-bad",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "bad" }),
  });
  assert.deepEqual(envelope, { ok: false, reason: "handshake-failed" });
  const exited = events.find((s, i) => i > 0 && s.kind === "exited");
  assert.ok(exited, JSON.stringify(events));
  assert.equal(exited.exitCode, -1, "被 kill 的进程没有数字码 → -1");
  assert.equal(flow.state().kind, "exited");
  assert.equal(flow.state().exitCode, -1);
});

test("握手超时（silent + 短 timeoutMs）→ exited exitCode=-1、handshake-failed", async () => {
  const flow = createServiceFlow({ timeoutMs: 700 });
  const events = [];
  flow.subscribe((state) => events.push(state));
  const envelope = await flow.start({
    repo: "r-silent",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "silent" }),
  });
  assert.deepEqual(envelope, { ok: false, reason: "handshake-failed" });
  assert.equal(flow.state().kind, "exited");
  assert.equal(flow.state().exitCode, -1, "超时被 kill 的进程没有数字码 → -1");
});

test("spawn 失败（ENOENT）→ exited exitCode=-1、回 start-failed", async () => {
  const flow = createServiceFlow({});
  const events = [];
  flow.subscribe((state) => events.push(state));
  const envelope = await flow.start({
    repo: "r-enoent",
    command: ["themistally-no-such-bin-xyz", "arg"],
  });
  assert.deepEqual(envelope, { ok: false, reason: "start-failed" });
  assert.equal(flow.state().kind, "exited");
  assert.equal(flow.state().exitCode, -1);
});

test("握手成功后服务自己退出（fake-service-exit）→ exited 带数字码 3、byShell=false", async () => {
  const flow = createServiceFlow({});
  const events = [];
  const infos = [];
  flow.subscribe((state, info) => {
    events.push(state);
    infos.push(info);
  });
  const envelope = await flow.start({ repo: "r-self-exit", command: [process.execPath, FAKE_EXIT] });
  assert.deepEqual(envelope, { ok: true, value: null });
  assert.equal(events[1].kind, "running");
  await waitFor("服务自己退出", () => events.length >= 3 && events[2].kind === "exited", 8000);
  assert.equal(events[2].repo, "r-self-exit");
  assert.equal(events[2].exitCode, 3, "FAKE_SERVICE_EXIT_CODE 缺省 3");
  assert.equal(infos[2].byShell, false, "服务自己退出的 byShell 要是 false");
  assert.equal(flow.state().kind, "exited");
  for (const s of events) assert.ok(noToken(s), JSON.stringify(s));
});

test("starting 期间 abort()：子进程真的退出（不留孤儿）、状态 exited、byShell=true", async () => {
  const rec = recordingSpawn();
  const flow = createServiceFlow({ spawn: rec.fn, timeoutMs: 8000 });
  const events = [];
  const infos = [];
  flow.subscribe((state, info) => {
    events.push(state);
    infos.push(info);
  });
  const startPromise = flow.start({
    repo: "r-abort",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "silent" }),
  });
  await waitFor("starting 状态", () => events.length >= 1 && events[0].kind === "starting");
  await flow.abort();
  // 子进程真的没了：exitCode 或 signalCode 至少一个非空（不是固定等几百毫秒）
  assert.equal(rec.children.length, 1, "spawn 要被调用一次");
  const child = rec.children[0];
  await waitFor(
    "子进程退出",
    () => child.exitCode !== null || child.signalCode !== null,
    5000,
  );
  await waitFor("abort 之后的 exited 状态", () => events.length >= 2 && events[1].kind === "exited", 5000);
  assert.equal(events[1].exitCode, -1, "kill 的进程没有数字码 → -1");
  assert.equal(infos[1].byShell, true, "外壳中止的退出 byShell 要是 true");
  assert.equal(flow.state().kind, "exited");
  const settled = await Promise.race([
    startPromise,
    new Promise((_, reject) => setTimeout(() => reject(new Error("abort 之后 start 的信封没有兑现")), 8000)),
  ]);
  assert.equal(typeof settled.ok, "boolean", "start 的信封要兑现（不 reject）");
});

test("订阅相互独立：退订只删自己那条、可重复退订、别的订阅还收得到", async () => {
  const flow = createServiceFlow({});
  const a = [];
  const b = [];
  const offA = flow.subscribe((state) => a.push(state));
  const offB = flow.subscribe((state) => b.push(state));
  await flow.start({
    repo: "r-sub",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "ok" }),
  });
  assert.equal(a.length, 2);
  assert.equal(b.length, 2);
  offA();
  assert.doesNotThrow(() => offA(), "重复退订不抛错");
  await flow.stop();
  await waitFor("stop 之后的 exited", () => b.length >= 3, 8000);
  assert.equal(a.length, 2, "退订之后不再收到");
  assert.equal(b.length, 3, "别的订阅照常收到");
  assert.equal(b[2].kind, "exited");
});

test("onRunning 抛错 → 收服务、状态置 exited、回 start-failed", async () => {
  const flow = createServiceFlow({
    onRunning: () => {
      throw new Error("窗口开不了");
    },
  });
  const events = [];
  flow.subscribe((state) => events.push(state));
  const envelope = await flow.start({
    repo: "r-onrun-fail",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "ok" }),
  });
  assert.deepEqual(envelope, { ok: false, reason: "start-failed" });
  assert.equal(events[1].kind, "running", "running 先发，onRunning 之后才轮到失败处理");
  await waitFor("收服务之后的 exited", () => events.length >= 3 && events[2].kind === "exited", 8000);
  assert.equal(events[2].exitCode, 0, "收服务走 stop 的语义（stdin EOF），假服务以 0 退出");
  assert.equal(flow.state().kind, "exited");
});
'''


PROBE_SHELLAPI = r'''
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
    stopCalls: 0,
    currentState: { kind: "idle" },
    nextStart: { ok: true, value: null },
    async start(arg) {
      ctl.starts.push(JSON.parse(JSON.stringify(arg)));
      return ctl.nextStart;
    },
    async stop() {
      ctl.stopCalls += 1;
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
    emit(state) {
      for (const fn of [...listeners]) fn(state, { byShell: false });
    },
  };
  return ctl;
}

function makeHarness(opts) {
  const o = opts || {};
  const b = fs.mkdtempSync(path.join(os.tmpdir(), "t033-gate-api-"));
  const userData = path.join(b, "userData");
  fs.mkdirSync(userData);
  const store = createSettingsStore({ dir: userData });
  const alphaDir = path.join(b, "alpha");
  const betaDir = path.join(b, "beta");
  const kitDir = path.join(b, "mykit");
  fs.mkdirSync(alphaDir);
  fs.mkdirSync(betaDir);
  fs.mkdirSync(kitDir);
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
  if (o.kitPath) s.kitPath = kitDir;
  store.save(s);

  const pythonPath = "/auto/python-exe";
  const kitCalls = [];
  const pythonCalls = [];
  const state = { kitFailDirs: new Set() };
  const probe = {
    async probePython(commandArgs) {
      pythonCalls.push(commandArgs);
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
  const inject = { store, appVersion: "9.9.9", probe };
  if (ctl !== null) {
    inject.service = ctl;
    inject.assets = "/assets/root";
  }
  const api = createShellApi(inject);
  return { b, api, store, ctl, probe, kitCalls, pythonCalls, alphaDir, betaDir, kitDir, t1, t2, state };
}

test("unknown-repo：id 不在设置列表 → 不起进程、不改状态", async () => {
  const h = makeHarness();
  const r = await h.api.startService("no-such-repo");
  assert.deepEqual(r, { ok: false, reason: "unknown-repo" });
  assert.equal(h.ctl.starts.length, 0, "控制器没被调用（没起进程）");
  const st = await h.api.getState();
  assert.deepEqual(st.value.service, { kind: "idle" });
});

test("python-missing：Python 不可用 → 不起进程", async () => {
  const h = makeHarness({ pythonMissing: true });
  const r = await h.api.startService("repo-beta");
  assert.deepEqual(r, { ok: false, reason: "python-missing" });
  assert.equal(h.ctl.starts.length, 0);
});

test("kit-missing：kit 按目标仓库算（不读当前仓库的缓存）→ 不起进程", async () => {
  const h = makeHarness();
  h.state.kitFailDirs.add(h.betaDir);
  const r = await h.api.startService("repo-beta");
  assert.deepEqual(r, { ok: false, reason: "kit-missing" });
  assert.equal(h.ctl.starts.length, 0);
  assert.ok(h.kitCalls.length >= 1, "现场探测要被调用");
  for (const [p, dir] of h.kitCalls) {
    assert.ok(dir === h.betaDir, "kit 只许按目标仓库的目录探测：" + dir);
  }
});

test("成功：命令形状与带参数那条路同一个 serviceCommand；控制器的信封原样回传", async () => {
  const h = makeHarness({ kitPath: true });
  h.ctl.nextStart = { ok: true, value: null };
  const r = await h.api.startService("repo-beta");
  assert.deepEqual(r, { ok: true, value: null });
  assert.equal(h.ctl.starts.length, 1);
  const arg = h.ctl.starts[0];
  assert.equal(arg.repo, "repo-beta", "交给控制器的是目标仓库的 id");
  const expected = serviceCommand({
    python: ["/auto/python-exe"],
    kit: h.kitDir,
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
  // 控制器的失败信封也原样回传
  const h2 = makeHarness({ kitPath: true });
  h2.ctl.nextStart = { ok: false, reason: "handshake-failed" };
  assert.deepEqual(await h2.api.startService("repo-beta"), { ok: false, reason: "handshake-failed" });
});

test("幂等与忙：同仓库 starting/running → ok 且什么也不做；别的仓库正忙 → busy", async () => {
  const h = makeHarness({ kitPath: true });
  h.ctl.currentState = { kind: "starting", repo: "repo-beta" };
  assert.deepEqual(await h.api.startService("repo-beta"), { ok: true, value: null });
  h.ctl.currentState = { kind: "running", repo: "repo-beta", pid: 10, startedAt: "2026-01-01T00:00:00.000Z" };
  assert.deepEqual(await h.api.startService("repo-beta"), { ok: true, value: null });
  h.ctl.currentState = { kind: "starting", repo: "repo-alpha" };
  assert.deepEqual(await h.api.startService("repo-beta"), { ok: false, reason: "busy" });
  assert.equal(h.ctl.starts.length, 0, "幂等与忙都不许再起进程");
});

test("getState().service 取控制器的当前状态；没注入控制器时是 idle", async () => {
  const h = makeHarness();
  h.ctl.currentState = { kind: "exited", repo: "repo-beta", exitCode: 3, at: 12345 };
  const st = await h.api.getState();
  assert.deepEqual(st.value.service, { kind: "exited", repo: "repo-beta", exitCode: 3, at: 12345 });
  const h2 = makeHarness({ noController: true });
  const st2 = await h2.api.getState();
  assert.deepEqual(st2.value.service, { kind: "idle" });
});

test("no-service：没注入控制器 → 兜底 reason，不抛错", async () => {
  const h = makeHarness({ noController: true });
  const r = await h.api.startService("repo-beta");
  assert.deepEqual(r, { ok: false, reason: "no-service" });
});

test("on：有控制器时订阅状态变化、只传 state 一个实参、退订后不再收到；别的事件名回空退订函数", async () => {
  const h = makeHarness();
  const got = [];
  const off = h.api.on("service-state", (...args) => got.push(args));
  assert.equal(typeof off, "function", "on 要同步返回退订函数");
  h.ctl.emit({ kind: "running", repo: "repo-beta", pid: 5, startedAt: "t" });
  assert.equal(got.length, 1);
  assert.equal(got[0].length, 1, "页面监听只收到 state 一个实参（info 不外传）");
  assert.deepEqual(got[0][0], { kind: "running", repo: "repo-beta", pid: 5, startedAt: "t" });
  assert.ok(!JSON.stringify(got[0]).includes("byShell"), "byShell 不许外传");
  h.ctl.emit({ kind: "exited", repo: "repo-beta", exitCode: 0, at: 1 });
  assert.equal(got.length, 2);
  off();
  h.ctl.emit({ kind: "idle" });
  assert.equal(got.length, 2, "退订后不再收到");
  let other = 0;
  const off2 = h.api.on("whatever", () => {
    other += 1;
  });
  assert.equal(typeof off2, "function");
  assert.doesNotThrow(() => off2());
  assert.equal(other, 0);
  // 没控制器时也同步回空退订函数
  const h2 = makeHarness({ noController: true });
  let fired = 0;
  const off3 = h2.api.on("service-state", () => {
    fired += 1;
  });
  assert.equal(typeof off3, "function");
  assert.doesNotThrow(() => off3());
  assert.equal(fired, 0);
});
'''


PROBE_SHELLIPC = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const shellipc = require("@SHELL@/src/shellipc.js");
const { SHELL_CHANNELS, SERVICE_STATE_CHANNEL, registerShellIpc } = shellipc;

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
  "themis-shell:get-state": "getState",
  "themis-shell:pick-repo": "pickRepo",
  "themis-shell:pick-python": "pickPython",
  "themis-shell:pick-kit": "pickKit",
  "themis-shell:pick-transcript-dir": "pickTranscriptDir",
  "themis-shell:save-settings": "saveSettings",
  "themis-shell:start-service": "startService",
  "themis-shell:restart-service": "restartService",
  "themis-shell:open-external": "openExternal",
};

test("SERVICE_STATE_CHANNEL：值逐字、不进 SHELL_CHANNELS；SHELL_CHANNELS 仍恰好九个且顺序不变", () => {
  assert.equal(SERVICE_STATE_CHANNEL, "themis-shell:service-state");
  assert.ok(Object.isFrozen(SHELL_CHANNELS), "SHELL_CHANNELS 必须冻结");
  assert.ok(!SHELL_CHANNELS.includes(SERVICE_STATE_CHANNEL), "事件通道不进 SHELL_CHANNELS");
  assert.deepEqual([...SHELL_CHANNELS], CHANNELS);
});

test("preload 源码里的通道字面量与常量一致（preload 不能 require 相对路径，只能写字面量）", () => {
  const src = fs.readFileSync("@SHELL@/shell-preload.js", "utf8");
  assert.ok(src.includes('"themis-shell:service-state"'), "preload 里要写字面量通道名");
});

test("registerShellIpc 仍只注册九个 handle，没有给事件通道注册，也没有 ipcMain.on", () => {
  const handlers = new Map();
  const onCalls = [];
  const im = {
    handle: (ch, fn) => {
      if (handlers.has(ch)) throw new Error("通道被重复注册：" + ch);
      handlers.set(ch, fn);
    },
    on: (...a) => onCalls.push(a),
  };
  const api = {};
  for (const [ch, name] of Object.entries(SPEC)) api[name] = async () => ({ ok: true, value: null });
  registerShellIpc(im, api, () => true);
  assert.deepEqual([...handlers.keys()].sort(), [...CHANNELS].sort());
  assert.ok(!handlers.has(SERVICE_STATE_CHANNEL), "事件通道是单向推送，不许注册 handle");
  assert.equal(onCalls.length, 0);
});
'''


PROBE_SHELLPRELOAD = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

// shell-preload 跑在沙箱里，只能用注入的 require 载入 electron；测试里不出现「require electron」
// 字面串（T025/T030 门禁扫 tests/**）。假 electron 故意不提供 removeListener/off：preload 的订阅
// 退订不许依赖它们（合同第 4 节：用 Set 方案）。
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
        send: (...args) => sends.push(args),
      },
    };
  };
  vm.runInNewContext(source, { require: fakeRequire, module: { exports: {} }, exports: {} });
  return { source, requires, exposes, invokes, listeners, sends, state };
}

function internalListener(p) {
  assert.equal(p.listeners.length, 1, "模块加载时只注册一个 ipcRenderer.on：" + JSON.stringify(p.listeners.map((a) => a[0])));
  const [channel, fn] = p.listeners[0];
  assert.equal(channel, "themis-shell:service-state");
  assert.equal(typeof fn, "function");
  return fn;
}

test("模块加载时只注册一个 ipcRenderer.on，频道是那个字面量；仍是十个成员、恰好一次 expose", () => {
  const p = runShellPreload();
  internalListener(p);
  assert.equal(p.requires.length, 1, JSON.stringify(p.requires));
  assert.equal(p.exposes.length, 1, JSON.stringify(p.exposes.map((e) => e[0])));
  assert.equal(p.exposes[0][0], "themisShell");
  assert.equal((p.source.match(/exposeInMainWorld/g) || []).length, 1, "exposeInMainWorld 只许出现一次");
  assert.equal(Object.keys(p.exposes[0][1]).length, 10, "暴露面仍是十个成员");
});

test("页面监听只收到 state 一个实参（不把事件对象交给页面）；两个订阅都收到", () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  const internal = internalListener(p);
  const a = [];
  const b = [];
  api.on("service-state", (...args) => a.push(args));
  api.on("service-state", (...args) => b.push(args));
  const payload = { kind: "running", repo: "repo-x", pid: 7, startedAt: "2026-01-01T00:00:00.000Z" };
  // Electron 会把事件对象作为第一个实参传给监听函数，state 在第二个
  internal({ marker: "electron-event" }, payload);
  assert.equal(a.length, 1);
  assert.equal(b.length, 1);
  assert.equal(a[0].length, 1, "只传 state 一个实参");
  assert.equal(b[0].length, 1, "只传 state 一个实参");
  assert.deepEqual(a[0][0], payload);
  assert.deepEqual(b[0][0], payload);
  assert.ok(!JSON.stringify(a[0]).includes("electron-event"), "不许把事件对象交给页面");
});

test("退订只删自己那条、可重复退订；退订之后再发收不到", () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  const internal = internalListener(p);
  const a = [];
  const b = [];
  const offA = api.on("service-state", (...args) => a.push(args));
  const offB = api.on("service-state", (...args) => b.push(args));
  internal({}, { kind: "starting", repo: "r" });
  assert.equal(a.length, 1);
  assert.equal(b.length, 1);
  offA();
  assert.doesNotThrow(() => offA(), "重复退订不抛错");
  internal({}, { kind: "running", repo: "r", pid: 1, startedAt: "t" });
  assert.equal(a.length, 1, "退订之后不再收到");
  assert.equal(b.length, 2, "别的订阅照常收到");
  offB();
  internal({}, { kind: "idle" });
  assert.equal(a.length, 1);
  assert.equal(b.length, 2, "全部退订之后再发谁都不收");
});

test("别的事件名同步回空退订函数：不注册、不抛错、listener 不被调", () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  const before = p.listeners.length;
  let fired = 0;
  const off = api.on("other-event", () => {
    fired += 1;
  });
  assert.equal(typeof off, "function", "要同步返回函数");
  assert.doesNotThrow(() => off());
  assert.equal(fired, 0);
  assert.equal(p.listeners.length, before, "别的事件名不许再注册监听");
});

test("on 与退订都不发 IPC（不发 invoke，也不发 send）；源文本没有 ipcRenderer.send", () => {
  const p = runShellPreload();
  const api = p.exposes[0][1];
  const invBefore = p.invokes.length;
  const sendBefore = p.sends.length;
  const off = api.on("service-state", () => {});
  off();
  assert.equal(p.invokes.length, invBefore, "on/退订不许发 invoke");
  assert.equal(p.sends.length, sendBefore, "on/退订不许发 send");
  assert.equal(p.sends.length, 0);
  assert.ok(!/ipcRenderer\s*\.\s*send\s*\(/.test(p.source), "源文本不许有 ipcRenderer 的发送");
  assert.ok(!/require\(\s*['"]\./.test(p.source), "不许 require 相对路径");
  assert.ok(!/require\(\s*['"]node:/.test(p.source), "不许 require node: 模块");
});
'''


# --------------------------------------------------------------------------- 探针包装

def test_p01_probe_serviceflow():
    """D02/D05/D07/D08：serviceflow 的状态机、退出码映射、abort、订阅与令牌隔离（node --test 探针，
    真起子进程）。"""
    _expect_probe_pass("t033-serviceflow", PROBE_SERVICEFLOW, timeout=300.0)


def test_p02_probe_shellapi():
    """D01：startService 按仓库 id 查、python/kit 按目标仓库算、命令形状、busy/幂等、getState().service、
    on 的真订阅、no-service 兜底（node --test 探针，注入假控制器与假 probe）。"""
    _expect_probe_pass("t033-shellapi", PROBE_SHELLAPI)


def test_p03_probe_shellipc_channel():
    """D03：SERVICE_STATE_CHANNEL 的值、不进 SHELL_CHANNELS、九通道原样、preload 字面量一致、
    registerShellIpc 不给事件通道注册（node --test 探针）。"""
    _expect_probe_pass("t033-shellipc", PROBE_SHELLIPC)


def test_p04_probe_shellpreload_on():
    """D04：shell-preload 的 on——一个 ipcRenderer.on、单实参转发、独立订阅与退订、别的
    事件名回空退订函数、不发 IPC（node --test 探针，假 electron 不提供 removeListener/off）。"""
    _expect_probe_pass("t033-shellpreload", PROBE_SHELLPRELOAD)
