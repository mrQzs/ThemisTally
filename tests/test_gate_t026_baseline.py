"""T026 战前门禁：桌面端外壳第 2 片「服务页的宿主接口」的黑盒基准测试
（合同 t026-desktop-shell-host v1，基线 4357dca——``desktop/shell`` 只有 T025 的骨架，宿主接口尚未存在）。

被测对象是 ``window.themisHost`` 的五个函数（``reauth``、``openSecretWindow``、``openExternal``、
``reveal``、``notify``）：自包含的 ``desktop/shell/preload.js``（只 require electron 的 contextBridge 与
ipcRenderer，恰好一次 ``exposeInMainWorld``，五个固定通道）、纯校验 ``src/hostcheck.js``（页面地址 /
作业号 / 外链 / relPath 字面检查、realpath 判界、通知文案表、滑动窗口限速）、带控制令牌的
``src/control.js``（只连 127.0.0.1 的 http.request POST）、编排 ``src/host.js``（依赖全注入，令牌不外泄）、
通道白名单 ``src/ipc.js``（只 ``ipcMain.handle``、来源检查、不抛错）；外加 T025 终审留下的三处修复
（``window.js`` 的 ``mainWebPreferences``/``trackWindow``、``service.js`` 的 ``stopService`` 先查退出态、
``core.js`` 的可选 ``onServiceReady`` 与 ``tests/core.test.js`` 三条补时限）。

基线（4357dca）上这些文件与符号都不存在，所以失败都落在「文件不存在」「标记不在」与探针子进程退出码
非 0 这类断言上，不是收集失败：模块级只导入标准库，仓库文件的读取与探针的运行都发生在用例函数里。

探针是自包含的 ``node --test`` 文件（Node 24 自带，不需要 npm ci，不 require electron——electron 44.9.0
没有 postinstall）。Python 把探针源码写进系统临时目录、以仓库根为 cwd 运行、用完即删；探针里的被测模块
用 ``@SHELL@`` 占位符替换成绝对路径。preload 的探针用 ``vm.runInNewContext`` 真跑一遍源码，注入假
require（模块名字面量写成 ``"electron"``，测试文件里不出现 ``require('electron')`` 这个字面串——T025 门禁
S03 扫 ``tests/**``）。

结构（编号对应合同 DoD 的 D01–D17 与「变异对照」M1–M20）：

- 静态断言（``test_s*``，不需要任何依赖）：
  - S01/D16：合同 Scope 点名的新文件都在位；服务一侧的「出处」字面量还在（secretentry.ts 的页面地址
    正则、jobs.ts 的作业号正则、control.ts 的头名——服务改了，外壳的校验就该跟着红）。
  - S02/D16：``package.json`` 只改 ``scripts.test``（tap 开关仍在文件清单之前、显式列出 ``tests/`` 下每个
    ``*.test.js``、五个新测试文件点名在列）、devDependencies 与锁文件的 electron 44.9.0 不动。
  - S03/D15：静态禁令按文件收紧——``require('electron')`` 只许在 main.js 与 preload.js（合同明写 src/** 与
    tests/** 都不许）；``http.request`` 只许在 src/control.js；``shell.openExternal``、``showItemInFolder``、
    ``dialog``、``Notification`` 只许在 main.js——这五条「只在 X」的规则按审核 B2 的裁定只扫 main.js 与
    src/**（与 SRC_FORBIDDEN 一致），tests/** 里的裸词（注释、说明文字）不误伤；``ipcMain.on``、
    ``ipcRenderer.send`` 合同写的是「不出现」、没有文件限定，仍扫 desktop/shell 全部 .js；main.js 与 src/**
    里（注释也不行）没有 T025 的 7 条禁令；preload 自包含（五通道字面量在）、control.js 只连 127.0.0.1。
  - S04/D06/D14：main.js 的接线——恰好一处 ``new BrowserWindow``（一个建窗工厂）、主窗口
    ``mainWebPreferences`` + preload.js（由 ``__dirname`` 拼绝对路径）、凭据窗口仍用 ``webPreferences``、
    ``createHost``/``registerHostIpc`` 必须是调用形态（带左括号，注释里留字样不算——审核 B1）、
    ``ipcMain``/``senderAllowed``、``shell.openExternal``/``showItemInFolder``/``showMessageBox``/
    ``Notification``、四个 require（core/window/host/ipc）与 runShell 仍在。
  - S05/D16：README 只增改——T025 的要点还在，新增五个函数与 reason 词表、凭据窗口上限、通知类型与
    文案、relPath 基准、真 Electron 的已知缺口与手工冒烟（Ctrl+V）。
  - S06/D13：``tests/core.test.js`` 的「窗口在 openWindow 返回前就关了」「服务在开窗口之前就已经没了」
    「不传 io」三条补了 ``{ timeout: 5000 }``（按用例名找，不按行号；实现回退时这三条会挂住而不是变红）。
- 探针断言（``test_p*``，跑 node --test）：
  - P01/D01（M3）：preload 真跑——只 require electron、恰好一次 exposeInMainWorld("themisHost")、键
    恰好五个、每个函数把声明的实参原样转交固定通道（多余实参丢掉）、没有 ipcRenderer.on/send；
    HOST_CHANNELS 冻结且与五个通道逐字一致。
  - P02/D05/D09/D11（M7、M12、M13、M15、M16）：hostcheck——页面地址正反例（端口 0/65536、令牌
    31/33 位、localhost、https、多余路径、查询串、末尾换行）、作业号 42/44 位、外链协议与空白与
    ``http:\\x``、relPath 字面检查各类、resolveReveal 的注入 realpath/stat（跑出去、落在 root 本身、
    ``..foo`` 不误判、非文件非目录、抛错）、限速（被拒不计数、正好 60000ms 放行）。
  - P03/D03：control——POST 形状（方法、路径、x-themis-control 头、无 Origin 无 Cookie、不发正文、
    Connection: close 即 agent:false 的可观侧表现）、状态与正文原样带回、连不上与超时 reject 且错误里
    没有令牌。
  - P04/D03–D12（M5、M6、M8–M11、M14、M17）：host 编排——reauth 的五种 bad-response、限速、60000ms
    放行、连不上、加载失败（拒绝消息里带着 nonce 也不外传）；openSecretWindow 的 bad-args、同作业
    聚焦回 ok、别的作业 busy、占位在第一个 await 之前、关窗恰好取消一次（once）、404/409/500/断连都
    吞掉、loadURL 失败关窗并发取消、关掉后能再开；openExternal 的校验先于确认框、取消不打、失败
    open-failed；reveal 的 junction（指到外面、经它、指到里面、root 本身）与 ``..foo``；notify 两类文案
    逐字、坏类型不发、额外参数不进文案；控制令牌与 nonce 不进任何返回值。
  - P05/D02（M4）：ipc——只 handle、恰好五通道、来源不对回 forbidden 且不进 host、host 抛错/拒绝回
    internal 且错误消息不外传、多余实参丢掉。
  - P06/D14（M1、M18）：window——mainWebPreferences 是十键加 preload、webPreferences 仍恰好十键、
    trackWindow 的四种情形（closed 先挂、isDestroyed、closed 已触发而 isDestroyed 仍假、窗口还在才重抛）。
  - P07/D13（M19）：service——真子进程已退出时 stopService 立即兑现（带时限）、假子进程 stdin 发
    EPIPE 不抛。
  - P08/D14（M20）：core——onServiceReady 在 openWindow 之前、收到恰好 origin/control/repo 三键、
    抛错时一行 ERROR、收服务、退出码 1；不传时一切照旧。

合同没写死、门禁端按最合理读法定下的地方（详见交付信「下游须知」）：resolveReveal 拒绝时只断言
返回假值（合同没定返回形状）；notify 的文案表通过 host 行为断言（不要求 NOTIFY_TEXT 导出）；
``agent: false`` 用响应头 ``Connection: close`` 断言（本机 Node 24 实测，站主环境锁定）；cancelStatus
各情形在同一个用例里循环并各自重置；S06 按用例名而不是行号找那三条。
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
    "preload.js",
    "src/control.js", "src/host.js", "src/hostcheck.js", "src/ipc.js",
    "tests/control.test.js", "tests/host.test.js", "tests/hostcheck.test.js",
    "tests/ipc.test.js", "tests/preload.test.js",
    "tests/fixtures/fake-control-server.js",
)

# 本片新增的五份测试文件：scripts.test 必须显式点名（D16）
NEW_TEST_FILES = (
    "tests/control.test.js", "tests/host.test.js", "tests/hostcheck.test.js",
    "tests/ipc.test.js", "tests/preload.test.js",
)

HOST_CHANNELS = (
    "themis-host:reauth",
    "themis-host:open-secret-window",
    "themis-host:open-external",
    "themis-host:reveal",
    "themis-host:notify",
)

REQUIRE_ELECTRON_RE = re.compile(r"require\(\s*['\"]electron['\"]\s*\)")

# T025 的 7 条禁令（站主 4357dca 收窄后）：src/** 与 main.js 里不许出现，注释也不行
SRC_FORBIDDEN = (
    (re.compile(r"persist:"), "persist: 前缀"),
    (re.compile(r"shell\s*:\s*true"), "shell: true"),
    (re.compile(r"\b(writeFile|writeFileSync|appendFile|appendFileSync|mkdir|mkdirSync|rm|rmSync|unlink|unlinkSync|rename|renameSync)\s*\("), "fs 写函数"),
    (re.compile(r"\bfetch\s*\("), "fetch"),
    (re.compile(r"\bnet\.request\b"), "net.request"),
    (re.compile(r"\bautoUpdater\b"), "autoUpdater"),
    (re.compile(r"\bcrashReporter\b"), "crashReporter"),
)

# D15 的「按文件收紧」：token 只许出现在 allowed 列出的文件里（相对 desktop/shell 的正斜杠路径）。
# scope=="product" 的五条按审核 B2 的裁定只扫 main.js 与 src/**（与 SRC_FORBIDDEN 的范围一致）：合同 D15
# 对它们只写「只在 <文件>」，没把 tests/** 写进扫描范围，执行端测试里的注释/说明文字不该因此误红；
# scope=="all" 的两条合同没有文件限定（require('electron') 明写 src/** 与 tests/** 都不许；ipcMain.on、
# ipcRenderer.send 写的是「不出现」），照字面扫 desktop/shell 下全部 .js。
LOCATION_RULES = (
    (REQUIRE_ELECTRON_RE, "require('electron')", ("main.js", "preload.js"), "all"),
    (re.compile(r"\bhttp\s*\.\s*request\b"), "http.request", ("src/control.js",), "product"),
    (re.compile(r"\bshell\s*\.\s*openExternal\b"), "shell.openExternal", ("main.js",), "product"),
    (re.compile(r"\bshowItemInFolder\b"), "showItemInFolder", ("main.js",), "product"),
    (re.compile(r"\bdialog\b"), "dialog", ("main.js",), "product"),
    (re.compile(r"\bNotification\b"), "Notification", ("main.js",), "product"),
    (re.compile(r"\bipcMain\s*\.\s*on\b"), "ipcMain.on", (), "all"),
    (re.compile(r"\bipcRenderer\s*\.\s*send\b"), "ipcRenderer.send", (), "all"),
)

# main.js 的 T026 接线标记（T025 的 15 个标记由 T025 门禁 S04 继续钉住）。createHost/registerHostIpc
# 按审核 B1 收紧成调用形态（带左括号）：只查字样的话，把名字留在注释里就能骗过，模块在产品里
# 可以根本没接线。
MAIN_T026_MARKERS = (
    "mainWebPreferences", "ipcMain", "senderAllowed",
    "shell.openExternal", "showItemInFolder", "showMessageBox", "Notification",
    "preload.js", "__dirname", "isServiceUrl", "loadURL", "webPreferences(",
)
MAIN_T026_CALL_MARKERS = (
    (re.compile(r"\bcreateHost\s*\("), "createHost("),
    (re.compile(r"\bregisterHostIpc\s*\("), "registerHostIpc("),
)

MAIN_IMPORT_PATTERNS = (
    (re.compile(r"""require\(\s*['"]\.\/src\/core(\.js)?['"]\s*\)"""), "src/core.js（runShell 的来源）"),
    (re.compile(r"""require\(\s*['"]\.\/src\/window(\.js)?['"]\s*\)"""), "src/window.js（webPreferences 的来源）"),
    (re.compile(r"""require\(\s*['"]\.\/src\/host(\.js)?['"]\s*\)"""), "src/host.js（createHost 的来源）"),
    (re.compile(r"""require\(\s*['"]\.\/src\/ipc(\.js)?['"]\s*\)"""), "src/ipc.js（registerHostIpc 的来源）"),
)

# D13 之一：tests/core.test.js 里这三条用例原本没有时限（按名字找，不按行号）
CORE_TIMEOUT_CASES = (
    "窗口在 openWindow 返回前就关了",
    "服务在开窗口之前就已经没了",
    "不传 io",
)

# README 的 T026 新增要点（D16）；T025 的要点在 T025 门禁 S05 与本文件 S05 的前半各钉一遍
README_T026_NEEDLES = (
    "themisHost", "reauth", "openSecretWindow", "openExternal", "reveal", "notify",
    "forbidden", "internal", "rate-limited", "request-failed", "bad-response", "load-failed",
    "bad-args", "busy", "bad-url", "cancelled", "open-failed", "bad-path", "bad-kind",
    "attempt-finished", "awaiting-review", "attempt 已结束", "有 attempt 等待验收",
    ".agent", "Ctrl+V", "真 Electron",
)


def _shell_read(rel: str) -> str:
    p = SHELL / rel
    assert p.is_file(), f"desktop/shell/{rel} 不存在"
    return p.read_text(encoding="utf-8")


def _run_probe(name: str, source: str, timeout: float = 300.0) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    assert node, "本机没有 node，无法运行门禁探针"
    with tempfile.TemporaryDirectory(prefix="t026-gate-") as td:
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
        f"--- stdout 末尾 ---\n{proc.stdout[-5000:]}\n--- stderr 末尾 ---\n{proc.stderr[-2000:]}"
    )


def _js_files():
    files = []
    for rel in ("main.js", "preload.js"):
        p = SHELL / rel
        if p.is_file():
            files.append(p)
    if (SHELL / "src").is_dir():
        files += sorted((SHELL / "src").rglob("*.js"))
    if (SHELL / "tests").is_dir():
        files += sorted((SHELL / "tests").rglob("*.js"))
    return files


# --------------------------------------------------------------------------- 静态断言

def test_s01_contract_files_and_sources():
    """D16/Scope：合同点名的 11 个新文件都在位；服务一侧的出处字面量还在。"""
    for rel in CONTRACT_FILES:
        assert (SHELL / rel).is_file(), f"desktop/shell/{rel} 不存在"
    # 出处对齐（D05：服务改了正则/头名，外壳的校验就该跟着红）
    secret = (REPO_ROOT / "ts" / "packages" / "ui" / "src" / "secretentry.ts").read_text(encoding="utf-8")
    assert r"127\.0\.0\.1:(\d{1,5})\/([A-Za-z0-9_-]{32})$" in secret, "secretentry.ts 的页面地址正则变了"
    jobs = (REPO_ROOT / "ts" / "packages" / "ui" / "src" / "jobs.ts").read_text(encoding="utf-8")
    assert r"[A-Za-z0-9_-]{43}$" in jobs, "jobs.ts 的作业号正则变了"
    control = (REPO_ROOT / "ts" / "packages" / "ui" / "src" / "localhttp" / "control.ts").read_text(encoding="utf-8")
    assert '"x-themis-control"' in control, "control.ts 的控制令牌头名变了"


def test_s02_package_json_and_lock():
    """D16：package.json 只改 scripts.test（五份新测试点名在列），依赖与锁文件不动。"""
    pkg = json.loads(_shell_read("package.json"))
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
        assert rel in listed, f"scripts.test 必须显式列出本片新增的 {rel}：{test_cmd!r}"
    for p in (SHELL / "tests" / "fixtures").glob("*.test.js"):
        assert False, f"夹具不能叫 *.test.js：{p.name}"


def test_s03_static_scan():
    """D15：静态禁令按文件收紧（「只在 X」的五条只扫 main.js 与 src/**）；preload 自包含；control 只连 127.0.0.1。"""
    preload = _shell_read("preload.js")
    assert REQUIRE_ELECTRON_RE.search(preload), "preload.js 必须 require('electron')"
    assert "contextBridge" in preload, "preload.js 要用 contextBridge"
    assert "ipcRenderer" in preload, "preload.js 要用 ipcRenderer"
    for ch in HOST_CHANNELS:
        assert f'"{ch}"' in preload or f"'{ch}'" in preload, f"preload.js 缺通道字面量 {ch}"
    assert not re.search(r"""require\(\s*['"]\.""", preload), "preload 不许 require 相对路径（自包含）"
    control = _shell_read("src/control.js")
    assert re.search(r"\bhttp\s*\.\s*request\b", control), "src/control.js 必须用 node:http 的 http.request"
    assert "127.0.0.1" in control, "src/control.js 只许连 127.0.0.1"
    files = _js_files()
    assert files, "desktop/shell 扫描范围内没有 .js 文件"
    for f in files:
        rel = str(f.relative_to(SHELL)).replace("\\", "/")
        text = f.read_text(encoding="utf-8")
        in_product = rel == "main.js" or rel.startswith("src/")
        for pat, what, allowed, scope in LOCATION_RULES:
            if scope == "product" and not in_product:
                continue
            m = pat.search(text)
            if m and rel not in allowed:
                raise AssertionError(
                    f"desktop/shell/{rel} 出现只许在 {list(allowed) or '任何文件都不许'} 的「{what}」："
                    f"…{text[max(0, m.start() - 40):m.end() + 40]}…"
                )
    for f in [SHELL / "main.js"] + sorted((SHELL / "src").rglob("*.js")):
        text = f.read_text(encoding="utf-8")
        for pat, what in SRC_FORBIDDEN:
            m = pat.search(text)
            assert not m, (
                f"{f.relative_to(REPO_ROOT)} 出现禁令「{what}」：…{text[max(0, m.start() - 40):m.end() + 40]}…"
            )


def test_s04_main_js_wiring():
    """D06/D14：一个建窗工厂、主窗口带 preload、凭据窗口不带、IPC 与系统能力接线（host/ipc 真 require、真调用）。"""
    text = _shell_read("main.js")
    for marker in MAIN_T026_MARKERS:
        assert marker in text, f"main.js 缺接线标记：{marker}"
    for pat, what in MAIN_T026_CALL_MARKERS:
        assert pat.search(text), f"main.js 缺调用形态的接线标记：{what}（写在注释里的字样不算接线）"
    assert len(re.findall(r"new\s+BrowserWindow", text)) == 1, (
        "main.js 的 new BrowserWindow 必须恰好一处（一个建窗工厂，两种窗口共用，D06）"
    )
    assert "runShell" in text, "main.js 没有使用 runShell，src/core.js 的编排成了死代码"
    for pat, what in MAIN_IMPORT_PATTERNS:
        assert pat.search(text), f"main.js 没有 require {what}"


def test_s05_readme():
    """D16：README 只增改——T025 的要点还在，T026 的新增要点都在。"""
    text = _shell_read("README.md")
    for needle in ("npm ci", "npm start", "--repo", "--kit", "--assets", "退出码", "install.js",
                   "node_modules/electron", "冒烟"):
        assert needle in text, f"README 缺 T025 要点「{needle}」"
    assert re.search(r"10\s*(秒|s|S)", text), "README 缺 10 秒的时限说明"
    assert re.search(r"30\s*(秒|s|S)", text), "README 缺 30 秒的时限说明"
    for needle in README_T026_NEEDLES:
        assert needle in text, f"README 缺 T026 要点「{needle}」"


def test_s06_core_test_timeouts():
    """D13 之一：core.test.js 的三条会挂住的用例补了 { timeout: 5000 }（按用例名找）。"""
    text = _shell_read("tests/core.test.js")
    for name in CORE_TIMEOUT_CASES:
        m = re.search(r"test\(\s*(['\"])" + re.escape(name) + r"[^'\"]*\1", text)
        assert m, f"tests/core.test.js 找不到用例「{name}」"
        nxt = text.find("\ntest(", m.start() + 1)
        block = text[m.start(): nxt if nxt != -1 else len(text)]
        assert "{ timeout: 5000 }" in block, (
            f"「{name}」没有 { '{ timeout: 5000 }' }——实现回退时它会挂住而不是变红（D13）"
        )
    # 已带时限的三条照旧（240/292/315）
    assert text.count("{ timeout: 5000 }") >= 6, "core.test.js 的时限选项少于六处"


# --------------------------------------------------------------------------- 探针断言（node --test）

PROBE_PRELOAD = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const SHELL = "@SHELL@";
const { HOST_CHANNELS } = require(path.join(SHELL, "src", "ipc.js"));

const CHANNELS = [
  "themis-host:reauth",
  "themis-host:open-secret-window",
  "themis-host:open-external",
  "themis-host:reveal",
  "themis-host:notify",
];

test("HOST_CHANNELS 恰好五个通道、冻结", () => {
  assert.ok(Object.isFrozen(HOST_CHANNELS), "HOST_CHANNELS 必须冻结");
  assert.deepEqual([...HOST_CHANNELS], CHANNELS);
});

test("preload 真跑一遍：只 require electron、恰好一次 exposeInMainWorld、键恰好五个", () => {
  const source = fs.readFileSync(path.join(SHELL, "preload.js"), "utf8");
  const requires = [];
  const exposes = [];
  const invokes = [];
  const fakeRequire = (name) => {
    requires.push(name);
    assert.equal(name, "electron", "preload 只许 require electron，却 require 了 " + name);
    return {
      contextBridge: { exposeInMainWorld: (n, o) => exposes.push([n, o]) },
      ipcRenderer: { invoke: async (...args) => { invokes.push(args); return { ok: true }; } },
    };
  };
  vm.runInNewContext(source, { require: fakeRequire, module: { exports: {} }, exports: {} });
  assert.deepEqual(requires, ["electron"]);
  assert.equal(exposes.length, 1, "exposeInMainWorld 必须恰好调一次：" + JSON.stringify(exposes.map((e) => e[0])));
  const [name, api] = exposes[0];
  assert.equal(name, "themisHost");
  assert.deepEqual(Object.keys(api).sort(), ["notify", "openExternal", "openSecretWindow", "reauth", "reveal"]);
  assert.equal("openSettings" in api, false, "不许有 openSettings（留给外壳页那一片）");
  const u = "http://127.0.0.1:8123/abcdefghijklmnopqrstuv";
  const j = "0123456789".repeat(4) + "012";
  api.reauth();
  api.reauth("EXTRA");
  api.openSecretWindow(u, j);
  api.openSecretWindow(u, j, "EXTRA");
  api.openExternal("https://x.example/a");
  api.reveal("a/b.txt");
  api.notify("attempt-finished");
  assert.deepEqual(invokes, [
    ["themis-host:reauth"],
    ["themis-host:reauth"],
    ["themis-host:open-secret-window", u, j],
    ["themis-host:open-secret-window", u, j],
    ["themis-host:open-external", "https://x.example/a"],
    ["themis-host:reveal", "a/b.txt"],
    ["themis-host:notify", "attempt-finished"],
  ]);
  assert.ok(!/ipcRenderer\s*\.\s*on\s*\(/.test(source), "preload 不许有 ipcRenderer.on");
  assert.ok(!/ipcRenderer\s*\.\s*send\s*\(/.test(source), "preload 不许有 ipcRenderer.send");
});
'''


PROBE_HOSTCHECK = r'''
const { test, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { isSecretPageUrl, isJobId, isExternalUrl, isRevealLiteralOk, resolveReveal, createRateLimiter } = require("@SHELL@/src/hostcheck.js");

const T31 = "AbCdEfGhIjKlMnOpQrStUvWxYz01234";
const T32 = "AbCdEfGhIjKlMnOpQrStUvWxYz012345";
const T33 = T32 + "6";
const TMIX = "abcdefghij" + "-" + "klmnopqrst" + "_" + "uvwxyz0123";
const J43 = "0123456789".repeat(4) + "012";

const REPO = fs.mkdtempSync(path.join(os.tmpdir(), "t026-hc-"));
const ROOT = path.join(REPO, ".agent");
after(() => fs.rmSync(REPO, { recursive: true, force: true }));

test("isSecretPageUrl 正例：端口边界 1 与 65535、大小写与 -_ 令牌", () => {
  assert.equal(isSecretPageUrl("http://127.0.0.1:8080/" + T32), true);
  assert.equal(isSecretPageUrl("http://127.0.0.1:1/" + T32), true);
  assert.equal(isSecretPageUrl("http://127.0.0.1:65535/" + TMIX), true);
});

test("isSecretPageUrl 反例", () => {
  const bad = [
    "http://127.0.0.1:8080/" + T31,
    "http://127.0.0.1:8080/" + T33,
    "http://127.0.0.1:0/" + T32,
    "http://127.0.0.1:65536/" + T32,
    "http://127.0.0.1:8080/",
    "http://127.0.0.1:8080/" + T32 + "/x",
    "http://127.0.0.1:8080/" + T32 + "?q=1",
    "http://127.0.0.1:8080/" + T32 + "\n",
    "http://localhost:8080/" + T32,
    "https://127.0.0.1:8080/" + T32,
    "HTTP://127.0.0.1:8080/" + T32,
    "not a url",
    "",
    123,
    null,
  ];
  for (const u of bad) {
    assert.equal(isSecretPageUrl(u), false, "不该放行：" + JSON.stringify(u));
  }
});

test("isJobId：恰好 43 个 base64url 字符", () => {
  assert.equal(isJobId(J43), true);
  assert.equal(isJobId("0123456789".repeat(4) + "01"), false, "42 位");
  assert.equal(isJobId(J43 + "3"), false, "44 位");
  assert.equal(isJobId(J43.replace("0", "+")), false, "+ 不在字母表");
  assert.equal(isJobId(J43.replace("0", "=")), false, "= 不在字母表");
  assert.equal(isJobId(123), false);
  assert.equal(isJobId(null), false);
});

test("isExternalUrl 正例", () => {
  assert.equal(isExternalUrl("http://x.example/"), true);
  assert.equal(isExternalUrl("https://x.example/a?b=1#c"), true);
  assert.equal(isExternalUrl("HTTPS://X.EXAMPLE/"), true);
});

test("isExternalUrl 反例：协议、空白换行、反斜杠与单斜杠写法、非字符串", () => {
  const bad = [
    "javascript:alert(1)",
    "file:///C:/x",
    "data:text/html,hi",
    "ftp://x.example/",
    "mailto:a@b.example",
    " http://x.example/",
    "http://x.example/ ",
    "http://x.exa\nmple/",
    "http:\\\\x.example/",
    "http:/x.example/",
    "//x.example/",
    "x.example/",
    "",
    123,
    null,
  ];
  for (const u of bad) {
    assert.equal(isExternalUrl(u), false, "不该放行：" + JSON.stringify(u));
  }
});

test("isRevealLiteralOk 正例：普通段、..foo 文件名、点与空格在段中间", () => {
  assert.equal(isRevealLiteralOk("a"), true);
  assert.equal(isRevealLiteralOk("a/b.txt"), true);
  assert.equal(isRevealLiteralOk("..foo"), true);
  assert.equal(isRevealLiteralOk("a.b"), true);
  assert.equal(isRevealLiteralOk("x y"), true);
  assert.equal(isRevealLiteralOk("a b/c"), true);
});

test("isRevealLiteralOk 反例：绝对、盘符、UNC、单点段、反斜杠、冒号、段尾点或空格、空段、控制字符", () => {
  const bad = [
    "",
    "/a",
    "a/",
    "a//b",
    ".",
    "..",
    "a/..",
    "../a",
    "a/./b",
    "C:/x",
    "C:\\x",
    "\\\\srv\\s",
    "a:b",
    "a\\b",
    "a.",
    "a..",
    "a ",
    "a\u0000b",
    "a\u001fb",
    "a\nb",
    "a\tb",
    123,
    null,
  ];
  for (const p of bad) {
    assert.equal(isRevealLiteralOk(p), false, "不该放行：" + JSON.stringify(p));
  }
});

test("resolveReveal：字面检查不过时根本不碰 realpath", () => {
  const calls = [];
  const r = resolveReveal({
    repo: REPO, relPath: "..",
    realpath: (p) => { calls.push(p); return p; },
    stat: () => ({ isFile: () => true, isDirectory: () => false }),
  });
  assert.ok(!r, "拒绝时必须返回假值：" + JSON.stringify(r));
  assert.deepEqual(calls, [], "字面检查不过就不许碰文件系统");
});

test("resolveReveal：通过时返回 realpath 之后的完整路径；目录放行", () => {
  const full = path.join(ROOT, "a.txt");
  const map = {};
  map[path.join(REPO, ".agent")] = ROOT;
  map[full] = full;
  map[path.join(ROOT, "d")] = path.join(ROOT, "d");
  const realpath = (p) => { if (map[p] !== undefined) return map[p]; throw new Error("unexpected realpath " + p); };
  const file = resolveReveal({
    repo: REPO, relPath: "a.txt", realpath,
    stat: () => ({ isFile: () => true, isDirectory: () => false }),
  });
  assert.equal(file, full);
  const dir = resolveReveal({
    repo: REPO, relPath: "d", realpath,
    stat: () => ({ isFile: () => false, isDirectory: () => true }),
  });
  assert.equal(dir, path.join(ROOT, "d"));
});

test("resolveReveal：经 realpath 跑出 root、落在 root 本身、..foo 不被误判", () => {
  const esc = path.join(REPO, "elsewhere");
  const foo = path.join(ROOT, "..foo");
  const map = {};
  map[path.join(REPO, ".agent")] = ROOT;
  map[path.join(ROOT, "esc")] = esc;
  map[path.join(ROOT, "self")] = ROOT;
  map[foo] = foo;
  const realpath = (p) => { if (map[p] !== undefined) return map[p]; throw new Error("unexpected realpath " + p); };
  const stat = () => ({ isFile: () => true, isDirectory: () => false });
  const out = resolveReveal({ repo: REPO, relPath: "esc", realpath, stat });
  assert.ok(!out, "解析到 .agent 之外必须拒绝：" + JSON.stringify(out));
  const selfR = resolveReveal({ repo: REPO, relPath: "self", realpath, stat });
  assert.ok(!selfR, "落在 root 本身必须拒绝：" + JSON.stringify(selfR));
  const fooR = resolveReveal({ repo: REPO, relPath: "..foo", realpath, stat });
  assert.equal(fooR, foo, "..foo 是合法文件名，不许按 .. 误判");
});

test("resolveReveal：stat 只认文件或目录、stat 抛错、realpath 抛错都拒绝", () => {
  const map = {};
  map[path.join(REPO, ".agent")] = ROOT;
  map[path.join(ROOT, "x")] = path.join(ROOT, "x");
  const realpath = (p) => { if (map[p] !== undefined) return map[p]; throw new Error("unexpected realpath " + p); };
  const neither = resolveReveal({ repo: REPO, relPath: "x", realpath, stat: () => ({ isFile: () => false, isDirectory: () => false }) });
  assert.ok(!neither, "设备/管道等不该放行");
  const statThrow = resolveReveal({ repo: REPO, relPath: "x", realpath, stat: () => { throw new Error("no"); } });
  assert.ok(!statThrow);
  const rpThrow = resolveReveal({ repo: REPO, relPath: "gone", realpath: () => { throw new Error("ENOENT"); }, stat: () => ({ isFile: () => true, isDirectory: () => false }) });
  assert.ok(!rpThrow);
});

test("createRateLimiter：窗口内 max 次、被拒的调用不计数", () => {
  let t = 0;
  const rl = createRateLimiter({ max: 3, windowMs: 60000, now: () => t });
  assert.equal(rl.take(), true);
  assert.equal(rl.take(), true);
  assert.equal(rl.take(), true);
  t = 1;
  assert.equal(rl.take(), false, "第 4 次必须被拒");
  t = 60000;
  assert.equal(rl.take(), true);
  assert.equal(rl.take(), true);
  assert.equal(rl.take(), true, "被拒的那次不许占名额");
  assert.equal(rl.take(), false);
});

test("createRateLimiter：第 1 次之后正好 60000 毫秒放行", () => {
  let t = 0;
  const rl = createRateLimiter({ max: 1, windowMs: 60000, now: () => t });
  assert.equal(rl.take(), true);
  t = 59999;
  assert.equal(rl.take(), false, "差 1 毫秒也不放行");
  t = 60000;
  assert.equal(rl.take(), true, "正好 60000 毫秒必须放行");
});
'''


PROBE_CONTROL = r'''
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const http = require("node:http");
const { postControl } = require("@SHELL@/src/control.js");

const TOKEN = "ctrl-tok-9f31c2abc";
const hits = [];
let mode = { status: 200, body: "{}", hang: false };
const sockets = new Set();
const srv = http.createServer((req, res) => {
  const chunks = [];
  req.on("data", (c) => chunks.push(c));
  req.on("end", () => {
    hits.push({ method: req.method, url: req.url, headers: req.headers, body: Buffer.concat(chunks).toString("utf8") });
    if (mode.hang) return;
    res.writeHead(mode.status, { "content-type": "application/json" });
    res.end(mode.body);
  });
});
srv.on("connection", (s) => { sockets.add(s); s.on("close", () => sockets.delete(s)); });
let ORIGIN = "";
before(async () => {
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  ORIGIN = "http://127.0.0.1:" + srv.address().port;
});
after(async () => {
  for (const s of Array.from(sockets)) s.destroy();
  await new Promise((r) => srv.close(() => r()));
});

test("请求形状：POST、路径、令牌头、无 Origin 无 Cookie、不发正文、不留长连接；状态与正文原样带回", async () => {
  mode = { status: 201, body: "raw-body-XYZ", hang: false };
  const r = await postControl({ origin: ORIGIN, control: TOKEN, path: "/control/bootstrap", timeoutMs: 5000 });
  assert.equal(r.status, 201);
  assert.equal(r.body, "raw-body-XYZ");
  assert.equal(hits.length, 1, JSON.stringify(hits));
  const h = hits[0];
  assert.equal(h.method, "POST");
  assert.equal(h.url, "/control/bootstrap");
  assert.equal(h.headers["x-themis-control"], TOKEN);
  assert.equal(h.headers.origin, undefined, "不许带 Origin 头：" + JSON.stringify(h.headers));
  assert.equal(h.headers.cookie, undefined, "不许带 Cookie");
  assert.equal(h.body, "", "控制路由不读正文，客户端也不许写正文");
  assert.equal(h.headers.host, "127.0.0.1:" + srv.address().port);
  assert.equal(h.headers.connection, "close", "agent:false 的可观侧表现是 Connection: close");
});

test("连不上：reject，错误里没有令牌", async () => {
  const tmp = http.createServer(() => {});
  const port = await new Promise((resolve) => tmp.listen(0, "127.0.0.1", () => resolve(tmp.address().port)));
  await new Promise((r) => tmp.close(r));
  await assert.rejects(
    () => postControl({ origin: "http://127.0.0.1:" + port, control: TOKEN, path: "/x", timeoutMs: 3000 }),
    (err) => {
      const text = String(err && err.message ? err.message : err);
      assert.ok(!text.includes(TOKEN), "错误消息带令牌：" + text);
      return true;
    },
  );
});

test("超时：reject，错误里没有令牌", async () => {
  mode = { status: 200, body: "", hang: true };
  const t0 = Date.now();
  await assert.rejects(
    () => postControl({ origin: ORIGIN, control: TOKEN, path: "/control/bootstrap", timeoutMs: 300 }),
    (err) => {
      const text = String(err && err.message ? err.message : err);
      assert.ok(!text.includes(TOKEN), "错误消息带令牌：" + text);
      return true;
    },
  );
  assert.ok(Date.now() - t0 < 3000, "超时要按 timeoutMs 提前返回，不是等系统超时");
});
'''


PROBE_HOST = r'''
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const http = require("node:http");
const crypto = require("node:crypto");
const { EventEmitter } = require("node:events");
const { createHost } = require("@SHELL@/src/host.js");

const TOKEN = "ctrl-tok-" + crypto.randomBytes(12).toString("hex");
const NONCE = crypto.randomBytes(16).toString("hex");
const PAGE_TOK = crypto.randomBytes(24).toString("base64url"); // 恰好 32 个 base64url 字符

let ORIGIN = "";
const hits = [];
let bootstrapStatus = 200;
let bootstrapBody = null; // null → 正确信封
let bootstrapHang = false;
let cancelStatus = 200;
let cancelDestroy = false;
const sockets = new Set();
const srv = http.createServer((req, res) => {
  const chunks = [];
  req.on("data", (c) => chunks.push(c));
  req.on("end", () => {
    hits.push({ method: req.method, url: req.url, headers: req.headers, body: Buffer.concat(chunks).toString("utf8") });
    if (req.url === "/control/bootstrap") {
      if (bootstrapHang) return;
      const text = bootstrapBody !== null ? bootstrapBody
        : JSON.stringify({ ok: true, data: { bootstrap: ORIGIN + "/bootstrap/" + NONCE } });
      res.writeHead(bootstrapStatus, { "content-type": "application/json" });
      res.end(text);
      return;
    }
    if (cancelDestroy) { res.destroy(); return; }
    res.writeHead(cancelStatus, { "content-type": "text/plain" });
    res.end("cancel-done");
  });
});
srv.on("connection", (s) => { sockets.add(s); s.on("close", () => sockets.delete(s)); });

// 仓库夹具：.agent 里的普通文件/目录、..foo 文件名、指里/指外/指 root 本身的 junction、没有 .agent 的仓库
const BASE = fs.mkdtempSync(path.join(os.tmpdir(), "t026-host-"));
const REPO = path.join(BASE, "repo");
const AGENT = path.join(REPO, ".agent");
fs.mkdirSync(path.join(AGENT, "a"), { recursive: true });
fs.writeFileSync(path.join(AGENT, "a", "b.txt"), "x");
fs.mkdirSync(path.join(AGENT, "dir"));
fs.writeFileSync(path.join(AGENT, "..foo"), "y");
const OUTSIDE = path.join(BASE, "outside");
fs.mkdirSync(OUTSIDE);
fs.writeFileSync(path.join(OUTSIDE, "x.txt"), "z");
fs.symlinkSync(path.join(AGENT, "dir"), path.join(AGENT, "in-link"), "junction");
fs.symlinkSync(OUTSIDE, path.join(AGENT, "out-link"), "junction");
fs.symlinkSync(AGENT, path.join(AGENT, "self"), "junction");
const REPO_NOAGENT = path.join(BASE, "repo-no-agent");
fs.mkdirSync(REPO_NOAGENT);

before(async () => {
  await new Promise((r) => srv.listen(0, "127.0.0.1", r));
  ORIGIN = "http://127.0.0.1:" + srv.address().port;
});
after(async () => {
  for (const s of Array.from(sockets)) s.destroy();
  await new Promise((r) => srv.close(() => r()));
  fs.rmSync(BASE, { recursive: true, force: true });
});

// ---- 注入物与可重置的状态 ----
const clock = { t: 0 };
const winCfg = { failLoad: false, hangLoad: false };
const wins = [];
const winArgs = [];

function fakeWindow() {
  const win = new EventEmitter();
  win.focusCalls = 0;
  win.closedByHost = false;
  win.loadCalls = [];
  win.destroyed = false;
  win.isDestroyed = () => win.destroyed;
  win.focus = () => { win.focusCalls += 1; };
  win.close = () => { win.closedByHost = true; setImmediate(() => win.emit("closed")); };
  win.loadURL = (u) => {
    win.loadCalls.push(u);
    if (winCfg.failLoad) return Promise.reject(new Error("加载失败，地址 " + u));
    if (winCfg.hangLoad) return new Promise(() => {});
    return Promise.resolve();
  };
  return win;
}
const createSecretWindow = (arg) => { winArgs.push(arg); const w = fakeWindow(); wins.push(w); return w; };
const loadedMain = [];
const loadMain = async (u) => { loadedMain.push(u); };
const confirmCalls = [];
let confirmAnswer = true;
const confirmExternal = async (u) => { confirmCalls.push(u); return confirmAnswer; };
const openedExternal = [];
let openExternalMode = "ok";
const openExternalFn = async (u) => { openedExternal.push(u); if (openExternalMode === "fail") throw new Error("打不开"); };
const shownItems = [];
const showItem = (p) => { shownItems.push(p); };
const shownNotes = [];
const showNotification = (n) => { shownNotes.push(n); };

function resetAll() {
  bootstrapStatus = 200; bootstrapBody = null; bootstrapHang = false;
  cancelStatus = 200; cancelDestroy = false;
  winCfg.failLoad = false; winCfg.hangLoad = false;
  wins.length = 0; winArgs.length = 0; loadedMain.length = 0; confirmCalls.length = 0;
  openedExternal.length = 0; shownItems.length = 0; shownNotes.length = 0;
  confirmAnswer = true; openExternalMode = "ok"; clock.t = 0; hits.length = 0;
}
function makeHost(over) {
  return createHost(Object.assign({
    origin: ORIGIN, control: TOKEN, repo: REPO,
    loadMain, createSecretWindow, confirmExternal,
    openExternal: openExternalFn, showItem, showNotification,
    now: () => clock.t, controlTimeoutMs: 5000,
  }, over || {}));
}
function secretUrl(port) { return "http://127.0.0.1:" + (port || 8123) + "/" + PAGE_TOK; }
function jobId(ch) { return ch.repeat(43); }
function cancels() { return hits.filter((h) => h.url.indexOf("/cancel") !== -1); }
async function untilCancel(n) {
  for (let i = 0; i < 200; i += 1) {
    if (cancels().length >= n) return;
    await new Promise((r) => setTimeout(r, 10));
  }
}

// ---- reauth ----

test("reauth 成功：恰好 {ok:true}、只加载一次、请求带令牌头且无 Origin 无 Cookie", async () => {
  resetAll();
  const host = makeHost();
  const r = await host.reauth();
  assert.deepEqual(r, { ok: true }, JSON.stringify(r));
  assert.equal(hits.length, 1, JSON.stringify(hits));
  assert.equal(hits[0].method, "POST");
  assert.equal(hits[0].url, "/control/bootstrap");
  assert.equal(hits[0].headers["x-themis-control"], TOKEN);
  assert.equal(hits[0].headers.origin, undefined);
  assert.equal(hits[0].headers.cookie, undefined);
  assert.equal(hits[0].body, "");
  assert.deepEqual(loadedMain, [ORIGIN + "/bootstrap/" + NONCE]);
  assert.ok(!JSON.stringify(r).includes(TOKEN));
  assert.ok(!JSON.stringify(r).includes(NONCE));
});

test("reauth 限速：60 秒内最多 3 次，第 4 次不发请求不加载；窗口滑过去就放行", async () => {
  resetAll();
  const host = makeHost();
  assert.deepEqual(await host.reauth(), { ok: true });
  clock.t = 1000;
  assert.deepEqual(await host.reauth(), { ok: true });
  clock.t = 2000;
  assert.deepEqual(await host.reauth(), { ok: true });
  clock.t = 3000;
  assert.deepEqual(await host.reauth(), { ok: false, reason: "rate-limited" });
  assert.equal(hits.length, 3, JSON.stringify(hits));
  assert.equal(loadedMain.length, 3);
  clock.t = 61000;
  assert.deepEqual(await host.reauth(), { ok: true });
  assert.equal(hits.length, 4);
});

test("reauth 失败也占名额：三次 bad-response 之后第 4 次是 rate-limited，服务只收到 3 个请求", async () => {
  resetAll();
  bootstrapStatus = 500;
  const host = makeHost();
  for (let i = 0; i < 3; i += 1) {
    assert.deepEqual(await host.reauth(), { ok: false, reason: "bad-response" });
  }
  assert.deepEqual(await host.reauth(), { ok: false, reason: "rate-limited" });
  assert.equal(hits.length, 3, JSON.stringify(hits));
  assert.equal(loadedMain.length, 0);
});

test("reauth 连不上：request-failed，不加载", async () => {
  resetAll();
  const tmp = http.createServer(() => {});
  const port = await new Promise((resolve) => tmp.listen(0, "127.0.0.1", () => resolve(tmp.address().port)));
  await new Promise((r) => tmp.close(r));
  const host = makeHost({ origin: "http://127.0.0.1:" + port });
  const r = await host.reauth();
  assert.deepEqual(r, { ok: false, reason: "request-failed" });
  assert.equal(loadedMain.length, 0);
  assert.ok(!JSON.stringify(r).includes(TOKEN));
});

const BAD_RESPONSES = [
  ["状态码 500", () => { bootstrapStatus = 500; }],
  ["非 JSON 正文", () => { bootstrapStatus = 200; bootstrapBody = "not json <script>"; }],
  ["ok 不是 true", () => { bootstrapStatus = 200; bootstrapBody = JSON.stringify({ ok: false }); }],
  ["data.bootstrap 不是字符串", () => { bootstrapStatus = 200; bootstrapBody = JSON.stringify({ ok: true, data: { bootstrap: 123 } }); }],
  ["data.bootstrap 在别的 origin", () => { bootstrapStatus = 200; bootstrapBody = JSON.stringify({ ok: true, data: { bootstrap: "http://127.0.0.1:9/bootstrap/other" } }); }],
];
for (const [name, set] of BAD_RESPONSES) {
  test("reauth bad-response：" + name + "，不加载、不外泄", async () => {
    resetAll();
    set();
    const host = makeHost();
    const r = await host.reauth();
    assert.deepEqual(r, { ok: false, reason: "bad-response" }, name + "：" + JSON.stringify(r));
    assert.equal(loadedMain.length, 0, name);
    assert.ok(!JSON.stringify(r).includes(TOKEN), name);
    assert.ok(!JSON.stringify(r).includes(NONCE), name);
  });
}

test("reauth 加载失败：load-failed，拒绝消息里的 nonce 不外传", async () => {
  resetAll();
  const host = makeHost({ loadMain: async (u) => { throw new Error("加载失败 " + u); } });
  const r = await host.reauth();
  assert.deepEqual(r, { ok: false, reason: "load-failed" });
  assert.ok(!JSON.stringify(r).includes(NONCE));
  assert.ok(!JSON.stringify(r).includes(TOKEN));
});

// ---- openSecretWindow ----

test("openSecretWindow 参数不合格：bad-args，不开窗、不发取消", async () => {
  resetAll();
  const host = makeHost();
  const j = jobId("a");
  const badUrls = [
    "http://127.0.0.1:8123/" + PAGE_TOK.slice(0, 31),
    "http://127.0.0.1:8123/" + PAGE_TOK + "x",
    "http://127.0.0.1:0/" + PAGE_TOK,
    "http://127.0.0.1:65536/" + PAGE_TOK,
    "http://127.0.0.1:8123/",
    "http://127.0.0.1:8123/" + PAGE_TOK + "/x",
    "http://127.0.0.1:8123/" + PAGE_TOK + "?q=1",
    "http://127.0.0.1:8123/" + PAGE_TOK + "\n",
    "http://localhost:8123/" + PAGE_TOK,
    "https://127.0.0.1:8123/" + PAGE_TOK,
    "not a url",
    123,
    null,
  ];
  for (const u of badUrls) {
    const r = await host.openSecretWindow(u, j);
    assert.deepEqual(r, { ok: false, reason: "bad-args" }, "url=" + JSON.stringify(u));
  }
  const badJobs = ["a".repeat(42), "a".repeat(44), "a".repeat(43) + "!", 5, null];
  for (const jb of badJobs) {
    const r = await host.openSecretWindow(secretUrl(), jb);
    assert.deepEqual(r, { ok: false, reason: "bad-args" }, "jobId=" + JSON.stringify(jb));
  }
  assert.equal(wins.length, 0);
  assert.equal(hits.length, 0);
});

test("openSecretWindow 正常：开窗，origin 是该 url 自己的，loadURL 收到原 url", async () => {
  resetAll();
  const host = makeHost();
  const j = jobId("b");
  const u = "http://127.0.0.1:8123/" + PAGE_TOK;
  const r = await host.openSecretWindow(u, j);
  assert.deepEqual(r, { ok: true }, JSON.stringify(r));
  assert.equal(wins.length, 1);
  assert.equal(winArgs.length, 1);
  assert.equal(winArgs[0] && winArgs[0].origin, "http://127.0.0.1:8123");
  assert.deepEqual(wins[0].loadCalls, [u]);
  assert.equal(hits.length, 0);
});

test("同一 jobId 再调：{ok:true} 且聚焦，不开新窗、不发取消", async () => {
  resetAll();
  const host = makeHost();
  const j = jobId("c");
  await host.openSecretWindow(secretUrl(), j);
  const r = await host.openSecretWindow(secretUrl(), j);
  assert.deepEqual(r, { ok: true });
  assert.equal(wins.length, 1);
  assert.equal(wins[0].focusCalls, 1);
  assert.equal(hits.length, 0);
});

test("别的 jobId：busy 且聚焦，不开新窗、不发取消", async () => {
  resetAll();
  const host = makeHost();
  await host.openSecretWindow(secretUrl(), jobId("d"));
  const r = await host.openSecretWindow("http://127.0.0.1:9999/" + PAGE_TOK, jobId("e"));
  assert.deepEqual(r, { ok: false, reason: "busy" });
  assert.equal(wins.length, 1);
  assert.equal(wins[0].focusCalls, 1);
  assert.equal(hits.length, 0);
});

test("占位在第一个 await 之前：第一个窗口还没加载完，并发调用就被拒/聚焦", async () => {
  resetAll();
  winCfg.hangLoad = true;
  const host = makeHost();
  const jf = jobId("f");
  const pending = host.openSecretWindow(secretUrl(), jf); // 不 await：loadURL 永远挂起
  const r = await host.openSecretWindow(secretUrl(), jobId("g"));
  assert.deepEqual(r, { ok: false, reason: "busy" });
  assert.equal(wins.length, 1, "不许开出第二个窗口");
  const same = await host.openSecretWindow(secretUrl(), jf);
  assert.deepEqual(same, { ok: true });
  assert.equal(wins[0].focusCalls, 2, "两种被拒/复用都要聚焦：busy 一次 + 同 jobId 一次");
  wins[0].emit("closed");
  await untilCancel(1);
  void pending;
});

test("关窗取消：恰好一次、路径与头都对；再触发 closed 不重发；关掉后能再开", async () => {
  resetAll();
  const host = makeHost();
  const j = jobId("h");
  const u = "http://127.0.0.1:8123/" + PAGE_TOK;
  await host.openSecretWindow(u, j);
  wins[0].emit("closed");
  await untilCancel(1);
  assert.equal(cancels().length, 1, JSON.stringify(hits));
  assert.equal(cancels()[0].method, "POST");
  assert.equal(cancels()[0].url, "/control/jobs/" + j + "/cancel");
  assert.equal(cancels()[0].headers["x-themis-control"], TOKEN);
  wins[0].emit("closed");
  await new Promise((r) => setTimeout(r, 60));
  assert.equal(cancels().length, 1, "once 不许重复发取消");
  const again = await host.openSecretWindow(u, j);
  assert.deepEqual(again, { ok: true });
  assert.equal(wins.length, 2, "关掉之后要能再开");
});

test("取消的结果一律吞掉：404 / 409 / 500 / 断连，不崩、没有未处理的拒绝", async () => {
  for (const cfg of [404, 409, 500, "destroy"]) {
    resetAll();
    if (cfg === "destroy") cancelDestroy = true; else cancelStatus = cfg;
    const host = makeHost();
    await host.openSecretWindow(secretUrl(), jobId("i"));
    wins[0].emit("closed");
    await new Promise((r) => setTimeout(r, 150));
    assert.equal(cancels().length, 1, "cfg=" + String(cfg) + "：" + JSON.stringify(hits));
  }
});

test("loadURL 失败：load-failed、关窗，closed 照常触发取消；页面令牌不外泄", async () => {
  resetAll();
  winCfg.failLoad = true;
  const host = makeHost();
  const j = jobId("j");
  const r = await host.openSecretWindow("http://127.0.0.1:8123/" + PAGE_TOK, j);
  assert.deepEqual(r, { ok: false, reason: "load-failed" });
  assert.ok(!JSON.stringify(r).includes(PAGE_TOK));
  assert.equal(wins[0].closedByHost, true, "失败时窗口还在就要 close()");
  await untilCancel(1);
  assert.equal(cancels().length, 1);
  assert.equal(cancels()[0].url, "/control/jobs/" + j + "/cancel");
});

// ---- openExternal ----

test("openExternal 非法地址：bad-url 且确认框不弹", async () => {
  resetAll();
  const host = makeHost();
  const bad = [
    "javascript:alert(1)",
    "file:///C:/x",
    "data:text/html,hi",
    "ftp://x.example/",
    "mailto:a@b.example",
    " http://x.example/",
    "http://x.example/ ",
    "http://x.exa\nmple/",
    "http:\\\\x.example/",
    "http:/x.example/",
    "//x.example/",
    "x.example/",
    "",
    123,
    null,
  ];
  for (const u of bad) {
    const r = await host.openExternal(u);
    assert.deepEqual(r, { ok: false, reason: "bad-url" }, "url=" + JSON.stringify(u));
  }
  assert.equal(confirmCalls.length, 0, "校验不过不许弹确认框");
  assert.equal(openedExternal.length, 0);
});

test("openExternal 确认取消：cancelled 且打开函数没被调用", async () => {
  resetAll();
  confirmAnswer = false;
  const host = makeHost();
  const r = await host.openExternal("https://x.example/page");
  assert.deepEqual(r, { ok: false, reason: "cancelled" });
  assert.deepEqual(confirmCalls, ["https://x.example/page"]);
  assert.equal(openedExternal.length, 0);
});

test("openExternal 确认打开：参数原样传一次，{ok:true}", async () => {
  resetAll();
  const host = makeHost();
  const u = "https://x.example/a?q=1#h";
  const r = await host.openExternal(u);
  assert.deepEqual(r, { ok: true });
  assert.deepEqual(confirmCalls, [u]);
  assert.deepEqual(openedExternal, [u]);
});

test("openExternal 打开失败：open-failed", async () => {
  resetAll();
  openExternalMode = "fail";
  const host = makeHost();
  const r = await host.openExternal("https://x.example/");
  assert.deepEqual(r, { ok: false, reason: "open-failed" });
});

// ---- reveal ----

test("reveal 字面不合格：bad-path 且不调显示函数", async () => {
  resetAll();
  const host = makeHost();
  const bad = [
    "", "/a", "a/", "a//b", ".", "..", "a/..", "../a", "a/./b",
    "C:/x", "C:\\x", "\\\\srv\\s", "a:b", "a\\b", "a.", "a..", "a ",
    "a\u0000b", "a\u001fb", "a\nb", "a\tb",
    123, null,
  ];
  for (const p of bad) {
    const r = await host.reveal(p);
    assert.deepEqual(r, { ok: false, reason: "bad-path" }, "relPath=" + JSON.stringify(p));
  }
  assert.equal(shownItems.length, 0);
});

test("reveal 通过：显示函数被调一次，参数是 realpath 之后的绝对路径", async () => {
  resetAll();
  const host = makeHost();
  const r = await host.reveal("a/b.txt");
  assert.deepEqual(r, { ok: true });
  assert.equal(shownItems.length, 1);
  assert.equal(shownItems[0], fs.realpathSync.native(path.join(AGENT, "a", "b.txt")));
});

test("reveal 目录放行；..foo 文件名不被误判", async () => {
  resetAll();
  const host = makeHost();
  assert.deepEqual(await host.reveal("dir"), { ok: true });
  assert.deepEqual(await host.reveal("..foo"), { ok: true });
  assert.equal(shownItems.length, 2);
  assert.equal(shownItems[1], fs.realpathSync.native(path.join(AGENT, "..foo")));
});

test("reveal 指到 .agent 之外的 junction：它本身与经它的路径都拒绝", async () => {
  resetAll();
  const host = makeHost();
  assert.deepEqual(await host.reveal("out-link"), { ok: false, reason: "bad-path" });
  assert.deepEqual(await host.reveal("out-link/x.txt"), { ok: false, reason: "bad-path" });
  assert.equal(shownItems.length, 0);
});

test("reveal 指到 .agent 内部的 junction 放行；解析到 root 本身拒绝", async () => {
  resetAll();
  const host = makeHost();
  const r = await host.reveal("in-link");
  assert.deepEqual(r, { ok: true });
  assert.equal(shownItems.length, 1);
  assert.equal(shownItems[0], fs.realpathSync.native(path.join(AGENT, "dir")));
  assert.deepEqual(await host.reveal("self"), { ok: false, reason: "bad-path" });
  assert.equal(shownItems.length, 1);
});

test("reveal 不存在、.agent 缺失：bad-path", async () => {
  resetAll();
  const host = makeHost();
  assert.deepEqual(await host.reveal("nope.txt"), { ok: false, reason: "bad-path" });
  const host2 = makeHost({ repo: REPO_NOAGENT });
  assert.deepEqual(await host2.reveal("a/b.txt"), { ok: false, reason: "bad-path" });
  assert.equal(shownItems.length, 0);
});

// ---- notify ----

test("notify 两类：标题与正文逐字写死", async () => {
  resetAll();
  const host = makeHost();
  assert.deepEqual(await host.notify("attempt-finished"), { ok: true });
  assert.deepEqual(await host.notify("awaiting-review"), { ok: true });
  assert.deepEqual(shownNotes, [
    { title: "ThemisTally", body: "attempt 已结束" },
    { title: "ThemisTally", body: "有 attempt 等待验收" },
  ]);
});

test("notify 其余类型：bad-kind 且不发通知；渲染进程给的额外参数不进文案", async () => {
  resetAll();
  const host = makeHost();
  for (const k of ["constructor", "__proto__", "toString", "", "other", 123, null, {}]) {
    const r = await host.notify(k);
    assert.deepEqual(r, { ok: false, reason: "bad-kind" }, "kind=" + JSON.stringify(k));
  }
  assert.equal(shownNotes.length, 0);
  assert.deepEqual(await host.notify("attempt-finished", "额外参数"), { ok: true });
  assert.deepEqual(shownNotes, [{ title: "ThemisTally", body: "attempt 已结束" }]);
});

// ---- 令牌不外泄 ----

test("控制令牌与 nonce 不进宿主对象的 JSON", () => {
  resetAll();
  const host = makeHost();
  assert.ok(!JSON.stringify(host).includes(TOKEN), JSON.stringify(host));
  assert.ok(!JSON.stringify(host).includes(NONCE));
});
'''


PROBE_IPC = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const { HOST_CHANNELS, registerHostIpc } = require("@SHELL@/src/ipc.js");

const CHANNELS = [
  "themis-host:reauth",
  "themis-host:open-secret-window",
  "themis-host:open-external",
  "themis-host:reveal",
  "themis-host:notify",
];
const SECRET = "ipc-secret-" + crypto.randomBytes(8).toString("hex");
const EV = { sender: {}, senderFrame: { url: "http://127.0.0.1:8123/app" } };

test("HOST_CHANNELS 冻结且恰好五个", () => {
  assert.ok(Object.isFrozen(HOST_CHANNELS));
  assert.deepEqual([...HOST_CHANNELS], CHANNELS);
});

test("只用 ipcMain.handle 注册五个通道；来源不对回 forbidden 且不进 host", async () => {
  const handlers = {};
  let onCalled = 0;
  const ipcMain = {
    handle: (n, fn) => { assert.ok(!(n in handlers), "重复注册通道 " + n); handlers[n] = fn; },
    on: () => { onCalled += 1; },
  };
  const calls = [];
  const host = {
    reauth: async () => { calls.push(["reauth", []]); return { ok: true }; },
    openSecretWindow: async (url, jobId) => { calls.push(["openSecretWindow", [url, jobId]]); return { ok: true }; },
    openExternal: async (url) => { calls.push(["openExternal", [url]]); return { ok: true }; },
    reveal: async (relPath) => { calls.push(["reveal", [relPath]]); return { ok: true }; },
    notify: async (kind) => { calls.push(["notify", [kind]]); return { ok: true }; },
  };
  let allowed = false;
  registerHostIpc(ipcMain, host, (event) => allowed && event === EV);
  assert.equal(onCalled, 0, "不许用 ipcMain.on");
  assert.deepEqual(Object.keys(handlers).sort(), CHANNELS.slice().sort());
  for (const ch of CHANNELS) {
    const r = await handlers[ch](EV);
    assert.deepEqual(r, { ok: false, reason: "forbidden" }, ch);
  }
  assert.equal(calls.length, 0, "来源不对不许进 host");
  allowed = true;
  assert.deepEqual(await handlers["themis-host:reauth"](EV), { ok: true });
  assert.deepEqual(calls, [["reauth", []]]);
});

test("来源对：转交 host，多余的实参丢掉", async () => {
  const handlers = {};
  const ipcMain = { handle: (n, fn) => { handlers[n] = fn; } };
  const calls = [];
  const host = {
    reauth: async () => { calls.push(["reauth", []]); return { ok: true }; },
    openSecretWindow: async (a, b) => { calls.push(["openSecretWindow", [a, b]]); return { ok: true }; },
    openExternal: async (a) => { calls.push(["openExternal", [a]]); return { ok: true }; },
    reveal: async (a) => { calls.push(["reveal", [a]]); return { ok: true }; },
    notify: async (a) => { calls.push(["notify", [a]]); return { ok: true }; },
  };
  registerHostIpc(ipcMain, host, () => true);
  assert.deepEqual(await handlers["themis-host:open-secret-window"](EV, "u", "j", "EXTRA"), { ok: true });
  assert.deepEqual(calls, [["openSecretWindow", ["u", "j"]]], "多余的实参要丢掉");
  assert.deepEqual(await handlers["themis-host:reveal"](EV, "a/b.txt", "EXTRA"), { ok: true });
  assert.deepEqual(calls[1], ["reveal", ["a/b.txt"]]);
});

test("host 抛错（同步与异步）：回 internal，错误消息不外传", async () => {
  const handlers = {};
  const ipcMain = { handle: (n, fn) => { handlers[n] = fn; } };
  const host = {
    reauth: () => { throw new Error("同步炸了 " + SECRET); },
    openSecretWindow: async () => { throw new Error("异步炸了 " + SECRET); },
    openExternal: async () => ({ ok: true }),
    reveal: async () => ({ ok: true }),
    notify: async () => ({ ok: true }),
  };
  registerHostIpc(ipcMain, host, () => true);
  const r1 = await handlers["themis-host:reauth"](EV);
  assert.deepEqual(r1, { ok: false, reason: "internal" });
  const r2 = await handlers["themis-host:open-secret-window"](EV, "u", "j");
  assert.deepEqual(r2, { ok: false, reason: "internal" });
  assert.ok(!JSON.stringify(r1).includes(SECRET));
  assert.ok(!JSON.stringify(r2).includes(SECRET));
});
'''


PROBE_WINDOW = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const { partitionName, webPreferences, mainWebPreferences, isServiceUrl, trackWindow } = require("@SHELL@/src/window.js");

const TEN = {
  contextIsolation: true,
  sandbox: true,
  nodeIntegration: false,
  webSecurity: true,
  allowRunningInsecureContent: false,
  webviewTag: false,
  nodeIntegrationInWorker: false,
  nodeIntegrationInSubFrames: false,
  spellcheck: false,
};

test("webPreferences 仍恰好十键、没有 preload（T025 门禁 P04 钉的那份）", () => {
  const p = webPreferences("sess-cred");
  assert.deepEqual(p, Object.assign({}, TEN, { partition: "sess-cred" }));
  assert.equal(Object.keys(p).length, 10);
  assert.equal("preload" in p, false);
});

test("mainWebPreferences = 十键加 preload，其余不变", () => {
  const p = mainWebPreferences("sess-main", "C:/abs/path/preload.js");
  assert.deepEqual(p, Object.assign({}, TEN, { partition: "sess-main", preload: "C:/abs/path/preload.js" }));
  assert.equal(Object.keys(p).length, 11);
  assert.equal(p.preload, "C:/abs/path/preload.js");
});

function fakeWin() {
  const win = new EventEmitter();
  win.destroyed = false;
  win.isDestroyed = () => win.destroyed;
  return win;
}

test("trackWindow：closed 在 load 之前就挂好", async () => {
  const win = fakeWin();
  await trackWindow(win, () => {
    assert.equal(win.listenerCount("closed"), 1, "load 运行时 closed 必须已挂上");
    return Promise.resolve();
  });
});

test("trackWindow：load 正常，返回 {closed, close}", async () => {
  const win = fakeWin();
  const tracked = await trackWindow(win, () => Promise.resolve());
  assert.equal(typeof tracked.closed.then, "function");
  assert.equal(typeof tracked.close, "function");
});

test("trackWindow：load 拒绝且 isDestroyed 为真 → 按窗口已关吞掉", async () => {
  const win = fakeWin();
  win.destroyed = true;
  await trackWindow(win, () => Promise.reject(new Error("boom")));
});

test("trackWindow：load 拒绝、closed 已触发而 isDestroyed 仍假 → 也吞掉（T025 终审新情形）", async () => {
  const win = fakeWin();
  await trackWindow(win, async () => {
    win.emit("closed");
    throw new Error("boom");
  });
});

test("trackWindow：load 拒绝、窗口还在且 closed 没触发 → 重新抛出同一个错误", async () => {
  const win = fakeWin();
  const boom = new Error("real-load-failure");
  await assert.rejects(
    () => trackWindow(win, () => Promise.reject(boom)),
    (err) => err === boom,
  );
});
'''


PROBE_SERVICE = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const { EventEmitter } = require("node:events");
const { stopService } = require("@SHELL@/src/service.js");

const TIMEOUT = Symbol("timeout");
function withTimeout(p, ms) {
  return Promise.race([p, new Promise((r) => setTimeout(() => r(TIMEOUT), ms))]);
}

test("真子进程已经退出：stopService 立即兑现，不等宽限期", async () => {
  const child = spawn(process.execPath, ["-e", "process.exit(3)"], { stdio: ["pipe", "pipe", "inherit"] });
  await new Promise((r) => child.on("exit", r));
  const r = await withTimeout(stopService(child, { graceMs: 10000 }), 3000);
  assert.notEqual(r, TIMEOUT, "已退出的子进程上 stopService 挂住了（旧实现的毛病）");
  assert.equal(r.exited, true, JSON.stringify(r));
  assert.equal(r.killed, false, JSON.stringify(r));
  assert.equal(r.code, 3, JSON.stringify(r));
});

test("假子进程的 stdin 发 EPIPE：不抛、照常等退出", async () => {
  const child = new EventEmitter();
  child.stdin = new EventEmitter();
  child.stdin.end = () => {
    setImmediate(() => child.stdin.emit("error", Object.assign(new Error("write EPIPE"), { code: "EPIPE" })));
  };
  setTimeout(() => {
    child.exitCode = 0;
    child.emit("exit", 0, null);
    child.emit("close", 0, null);
  }, 50);
  const r = await withTimeout(stopService(child, { graceMs: 8000 }), 3000);
  assert.notEqual(r, TIMEOUT, "EPIPE 把 stopService 搞挂了");
  assert.equal(r.exited, true, JSON.stringify(r));
  assert.equal(r.killed, false, JSON.stringify(r));
  assert.equal(r.code, 0, JSON.stringify(r));
});
'''


PROBE_CORE = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { EventEmitter, PassThrough } = require("node:stream");
const { runShell } = require("@SHELL@/src/core.js");

const ORIGIN = "http://127.0.0.1:8123";
const TOKEN = "ctrl-tok-XYZ";
const NONCE = "nonceABC";
const HS = JSON.stringify({
  themis_ui: 1,
  bootstrap: ORIGIN + "/bootstrap/" + NONCE,
  origin: ORIGIN,
  control: TOKEN,
  pid: 4242,
}) + "\n";

function makeDirs() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "t026-core-"));
  const repo = path.join(base, "repo");
  const kit = path.join(base, "kit");
  const assets = path.join(base, "assets");
  fs.mkdirSync(repo); fs.mkdirSync(kit); fs.mkdirSync(assets);
  fs.mkdirSync(path.join(kit, "scripts"));
  fs.writeFileSync(path.join(kit, "scripts", "pi_dispatch.py"), "");
  fs.writeFileSync(path.join(assets, "index.html"), "");
  return { base, repo, kit, assets };
}

// 假 spawn：握手行 + stdin 关闭后退出；记录每个子进程的 stdin 是否被结束（收服务的可观侧）
function fakeSpawn(opts) {
  const children = [];
  const fn = (command, args) => {
    assert.ok(Array.isArray(command), "spawn 的第一个参数必须是完整 argv 数组");
    assert.deepEqual(args, []);
    const child = new EventEmitter();
    child.stdout = new PassThrough();
    child.stdin = new PassThrough();
    child.pid = 424242;
    child.stdinEnded = false;
    child.stdin.on("finish", () => { child.stdinEnded = true; });
    child.stdin.on("close", () => { child.stdinEnded = true; });
    child.kill = () => {
      setImmediate(() => { child.emit("exit", null, "SIGTERM"); child.emit("close", null, "SIGTERM"); });
    };
    let ended = false;
    const onEnd = () => {
      if (ended || opts.exitOnStdinEnd === undefined) return;
      ended = true;
      setTimeout(() => {
        child.exitCode = opts.exitOnStdinEnd;
        child.emit("exit", opts.exitOnStdinEnd, null);
        child.emit("close", opts.exitOnStdinEnd, null);
      }, 30);
    };
    child.stdin.on("finish", onEnd);
    child.stdin.on("close", onEnd);
    child.stdout.write(HS);
    children.push(child);
    return child;
  };
  fn.children = children;
  return fn;
}

function makeIo() {
  const out = [];
  const err = [];
  return {
    io: { stdout: { write: (c) => out.push(String(c)) }, stderr: { write: (c) => err.push(String(c)) } },
    all: () => out.join("") + err.join(""),
    errors: () => err.join(""),
  };
}

test("onServiceReady 在 openWindow 之前调用，收到恰好 origin、control、repo 三键", async () => {
  const d = makeDirs();
  const io = makeIo();
  const events = [];
  const openWindow = async (arg) => {
    events.push(["openWindow", arg]);
    return { closed: Promise.resolve(), close: () => {} };
  };
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow, spawn, env: process.env,
    onServiceReady: (arg) => { events.push(["onServiceReady", arg]); },
  });
  assert.equal(code, 0, io.all());
  assert.equal(events.length, 2, JSON.stringify(events.map((e) => e[0])));
  assert.equal(events[0][0], "onServiceReady", "onServiceReady 必须在 openWindow 之前");
  assert.equal(events[1][0], "openWindow");
  assert.deepEqual(Object.keys(events[0][1]).sort(), ["control", "origin", "repo"]);
  assert.equal(events[0][1].origin, ORIGIN);
  assert.equal(events[0][1].control, TOKEN);
  assert.equal(events[0][1].repo, path.resolve(d.repo));
  // 令牌绝不进 openWindow
  assert.ok(!JSON.stringify(events[1][1]).includes(TOKEN));
  await new Promise((r) => setTimeout(r, 150));
  assert.equal(spawn.children[0].stdinEnded, true, "关窗后要收服务（stdin 结束）");
});

test("onServiceReady 抛错：一行 ERROR、不开窗口、收服务、退出码 1", async () => {
  const d = makeDirs();
  const io = makeIo();
  const openCalls = [];
  const openWindow = async (arg) => { openCalls.push(arg); return { closed: Promise.resolve(), close: () => {} }; };
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow, spawn, env: process.env,
    onServiceReady: () => { throw new Error("令牌侧出问题"); },
  });
  assert.equal(code, 1);
  assert.equal(openCalls.length, 0);
  const lines = io.errors().split("\n").filter((l) => l.trim().length > 0);
  assert.equal(lines.length, 1, "必须只写一行 ERROR：" + JSON.stringify(lines));
  assert.ok(lines[0].startsWith("ERROR: "), JSON.stringify(lines));
  await new Promise((r) => setTimeout(r, 150));
  assert.equal(spawn.children[0].stdinEnded, true, "抛错也要收服务");
});

test("不传 onServiceReady：一切照旧，openWindow 仍只收 bootstrap 与 origin", async () => {
  const d = makeDirs();
  const io = makeIo();
  const calls = [];
  const openWindow = async (arg) => {
    calls.push(arg);
    return { closed: Promise.resolve(), close: () => {} };
  };
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow, spawn, env: process.env,
  });
  assert.equal(code, 0, io.all());
  assert.equal(calls.length, 1);
  assert.deepEqual(Object.keys(calls[0]).sort(), ["bootstrap", "origin"]);
  assert.equal(calls[0].origin, ORIGIN);
  assert.ok(!io.all().includes(TOKEN));
  assert.ok(!io.all().includes(NONCE));
});
'''


# --------------------------------------------------------------------------- 探针包装

def test_p01_probe_preload():
    """D01（M3）：preload 自包含、恰好五个函数、通道逐字一致、实参原样转交。"""
    _expect_probe_pass("t026-preload", PROBE_PRELOAD)


def test_p02_probe_hostcheck():
    """D05/D09/D11（M7、M12、M13、M15、M16）：hostcheck 的正反例、resolveReveal 注入、限速。"""
    _expect_probe_pass("t026-hostcheck", PROBE_HOSTCHECK)


def test_p03_probe_control():
    """D03：postControl 的请求形状、原样带回、连不上与超时 reject 且不泄令牌。"""
    _expect_probe_pass("t026-control", PROBE_CONTROL)


def test_p04_probe_host():
    """D03–D12（M5、M6、M8–M11、M14、M17）：五个函数的编排、取消、限速、令牌不外泄。"""
    _expect_probe_pass("t026-host", PROBE_HOST)


def test_p05_probe_ipc():
    """D02（M4）：只 handle、来源检查、不抛错、多余实参丢掉。"""
    _expect_probe_pass("t026-ipc", PROBE_IPC)


def test_p06_probe_window():
    """D14（M1、M18）：mainWebPreferences 十键加 preload；trackWindow 四种情形。"""
    _expect_probe_pass("t026-window", PROBE_WINDOW)


def test_p07_probe_service():
    """D13（M19）：stopService 对已退出的子进程立即兑现；stdin EPIPE 不抛。"""
    _expect_probe_pass("t026-service", PROBE_SERVICE)


def test_p08_probe_core():
    """D14（M20）：onServiceReady 的次序、三键、抛错路径与可选性。"""
    _expect_probe_pass("t026-core", PROBE_CORE)
