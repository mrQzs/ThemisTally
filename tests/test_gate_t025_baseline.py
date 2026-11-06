"""T025 战前门禁：桌面端外壳第 1 片「Electron 最小骨架」的黑盒基准测试
（合同 t025-desktop-shell v1，基线 a7bd592——``desktop/shell`` 整个目录还不存在）。

被测对象是新建的 npm 包 ``desktop/shell``：``package.json``/``package-lock.json``（devDependencies 只有
electron@44.9.0，scripts.test 显式列出 ``tests/`` 下每一个 ``*.test.js``）、六个纯模块（``src/args.js`` 的
parseShellArgs 与七条中文错误文案、``src/python.js`` 的探测代码/默认候选/findPython、``src/handshake.js`` 的
parseHandshake 与不回显字段值的七条错误、``src/service.js`` 的 serviceCommand/startService/stopService、
``src/window.js`` 的 partitionName/webPreferences 十键/isServiceUrl、``src/core.js`` 的 runShell 编排与
0/1/2 退出码）、唯一允许 ``require('electron')`` 的 ``main.js`` 与 README。

基线（a7bd592）上 ``desktop/shell`` 不存在，所以失败都落在「文件不存在」「标记不在」与探针子进程退出码非 0
这类断言上，不是收集失败：模块级只导入标准库，仓库文件的读取与探针的运行都发生在用例函数里。

探针是自包含的 ``node --test`` 文件（Node 24 自带，不需要 npm ci，不 ``require('electron')``——electron 44.9.0
没有 postinstall，npm ci 不下载本体）。Python 把探针源码写进系统临时目录、以仓库根为 cwd 运行、用完即删；
探针里的被测模块用绝对路径 require（``@SHELL@`` 占位符替换）。探针自己的夹具（假服务、假 python）也是临时目录里
的 Node 脚本，以 ``[process.execPath, 脚本]`` 当命令前缀（Windows 上不经 shell 起不了 .cmd/.bat）。

结构（编号对应合同 DoD 的 D01–D14）：

- 静态断言（``test_s*``，不需要任何依赖）：package.json 的字段与精确依赖、锁文件里 electron 的两处 44.9.0、
  scripts.test 带 ``--test-reporter=tap`` 且开关在文件清单之前（v2 第一节：Node 24 默认 spec reporter 不输出
  ``# pass``，V01 判不过）、scripts.test 显式列出每个 ``*.test.js``（数据驱动：实际文件集合 ⊆ 命令里列出的文件，
  不写死七个名字，以后加测试文件自动要求同步）与合同点名的新文件都在位（S01/D01）；静态禁令——扫描范围 ``main.js`` + ``src/**`` +
  ``tests/**``：``require('electron')`` 只许出现在 main.js，``persist:``、``shell: true``、fs 写函数、``fetch``、
  ``net.request``、``http(s).request``、``autoUpdater``、``crashReporter``、``openExternal`` 不许出现在
  ``src/**`` 与 ``main.js``（S03/D11）；main.js 的接线标记（菜单置空、分区与两个权限处理器、新窗口拒绝、
  will-navigate 用 isServiceUrl、loadURL、isPackaged 取参、app.exit，S04/D11）——外加一条把入口与被测模块连起来的
  断言：main.js 确实 require 了 ``src/core.js`` 与 ``src/window.js`` 且文本里用了 runShell（审核 B1：否则 main.js
  另写一套编排时 src/*.js 成死代码，D09/D10 落在没人走过的代码上；合同第七节「runShell 兑现退出码后
  app.exit(code)」「webPreferences 用第六节的结果」）；README 的要点与 package.json 的
  scripts 一致（S05/D12）；.gitignore 仍包含 ``desktop/**/node_modules/`` 与 ``desktop/**/dist/``（共享文件只断言
  「包含这几行」）。
- 探针断言（``test_p*``，跑 node --test）：args 的七条错误文案、绝对路径、--python 原样、transcripts 保序
  （P01/D02）；python 的探测代码与默认候选逐字、注入 probe 的顺序与首胜、真起进程的 ENOENT/退出码/超时
  （P02/D03）；handshake 的正例、只认第一行、七类错误文案且不回显 control/bootstrap 的值（P03/D04）；
  webPreferences 恰好十键 deepStrictEqual、partitionName 不带 persist: 前缀且两次不同、isServiceUrl 的正反例
  （P04/D08）；python 选项只试一个、失败不回退到默认候选、错误文案含「指定的 Python 不可用」与命令本身（P02/D03，v2 第三节）；
  serviceCommand 的参数列表（空格、&、" 、% 原样到达）、startService 只认第一行/分两段写/超时/
  握手前退出、stdin 一个字节都不写（假服务收到数据就以 9 退出）、stopService 的干净退出/忽略 EOF 被结束/EOF 后
  非 0 退出（P05/D05–D07）；注入 spawn 的调用形状固定 ``spawn(command, [], …)``（首参是完整 argv、第二参恒为
  []，P06，v2 第五节）、core 的三种退出码、openWindow 只收 {bootstrap, origin}、所有输出不含控制令牌与
  nonce（P06/D09、D10）。

合同没有写死、门禁端按最合理读法定下的地方（交付信「下游须知」逐条列出）：findPython 全失败的总结错误按合同
原文逐字断言，单个候选的 reason 只断言包含「存在/退出码/超时」字样；v2 第三节的 python 选项错误文案
``指定的 Python 不可用：<command>`` 只断言含该前缀与命令字符串（``<command>`` 的渲染方式——原样、join 或 JSON——
合同没写死）；startService 兑现的 ``handshake`` 形状
（``{ok, value}`` 信封还是裸 value）两种都接受；stopService 被 kill 时的 ``signal`` 不断言（Windows 信号语义）；
transcripts 没给时接受空数组或 undefined；核心探针用 ``--python python`` 走真探测（runShell 的签名没有注入
findPython 的口子），机器上 Python ≥ 3.10 本来就有。
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL = REPO_ROOT / "desktop" / "shell"

# 合同 Scope 点名的新文件（只断言「在位」，不断言「只有这些」——后面的片会继续往 desktop/shell 加文件）
CONTRACT_FILES = (
    "main.js", "README.md",
    "src/args.js", "src/python.js", "src/handshake.js", "src/service.js", "src/window.js", "src/core.js",
    "tests/args.test.js", "tests/package.test.js", "tests/python.test.js", "tests/handshake.test.js",
    "tests/service.test.js", "tests/window.test.js", "tests/core.test.js",
    "tests/fixtures/fake-python-ok.js", "tests/fixtures/fake-python-old.js", "tests/fixtures/fake-python-fail.js",
    "tests/fixtures/fake-python-hang.js", "tests/fixtures/fake-service.js",
)

# 静态禁令（合同第七节）：src/** 与 main.js 里不许出现；tests/** 只查 require('electron')
REQUIRE_ELECTRON_RE = re.compile(r"require\(\s*['\"]electron['\"]\s*\)")
# T026（服务页的宿主接口）起删掉 http(s).request 与 openExternal 两条：它们只在 T025 不做宿主接口时成立，T026 要带控制令牌
# POST /control/*、要确认后交给系统浏览器。两处调用改由 T026 的门禁按文件收紧（站主 2026-11-06 拍板，T026 规划第 10 节）
SRC_FORBIDDEN = (
    (re.compile(r"persist:"), "persist: 前缀"),
    (re.compile(r"shell\s*:\s*true"), "shell: true"),
    (re.compile(r"\b(writeFile|writeFileSync|appendFile|appendFileSync|mkdir|mkdirSync|rm|rmSync|unlink|unlinkSync|rename|renameSync)\s*\("), "fs 写函数"),
    (re.compile(r"\bfetch\s*\("), "fetch"),
    (re.compile(r"\bnet\.request\b"), "net.request"),
    (re.compile(r"\bautoUpdater\b"), "autoUpdater"),
    (re.compile(r"\bcrashReporter\b"), "crashReporter"),
)

# main.js 的接线标记（D11）：菜单、分区与权限、新窗口拒绝、导航判定、取参与退出
MAIN_MARKERS = (
    r"setApplicationMenu\s*\(\s*null\s*\)", "setPermissionRequestHandler", "setPermissionCheckHandler",
    "setWindowOpenHandler", r"['\"]deny['\"]", "will-navigate", "isServiceUrl", "loadURL",
    "session.fromPartition", "new BrowserWindow", "webPreferences", "app.isPackaged",
    "slice(2)", "slice(1)", "app.exit",
)

# 入口与被测模块的接线（审核 B1）：main.js 必须真的 require 这两个 src 模块（容忍省略 .js 后缀），
# 否则 15 个文本标记照样能凑齐、src/*.js 却是没人调用的死代码（D09/D10 就落在没被测过的代码上）
MAIN_IMPORT_PATTERNS = (
    (re.compile(r"""require\(\s*['"]\.\/src\/core(\.js)?['"]\s*\)"""), "src/core.js（runShell 的来源）"),
    (re.compile(r"""require\(\s*['"]\.\/src\/window(\.js)?['"]\s*\)"""), "src/window.js（webPreferences 的来源）"),
)


def _shell_read(rel: str) -> str:
    p = SHELL / rel
    assert p.is_file(), f"desktop/shell/{rel} 不存在"
    return p.read_text(encoding="utf-8")


def _run_probe(name: str, source: str, timeout: float = 180.0) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    assert node, "本机没有 node，无法运行门禁探针"
    with tempfile.TemporaryDirectory(prefix="t025-gate-") as td:
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
        f"--- stdout 末尾 ---\n{proc.stdout[-4000:]}\n--- stderr 末尾 ---\n{proc.stderr[-2000:]}"
    )


# --------------------------------------------------------------------------- 静态断言

def test_s01_package_and_lock():
    """D01：package.json 的字段、精确依赖与锁文件（.gitignore 仍忽略 desktop 的产物）。"""
    pkg = json.loads(_shell_read("package.json"))
    assert pkg.get("name") == "themistally-desktop-shell"
    assert pkg.get("private") is True
    assert pkg.get("version") == "0.0.0"
    assert pkg.get("type") == "commonjs"
    assert pkg.get("main") == "main.js"
    scripts = pkg.get("scripts") or {}
    assert scripts.get("start") == "electron ."
    assert "node --test" in scripts.get("test", "")
    # v2 合同第一节：必须带 --test-reporter=tap（Node 24 默认 spec reporter 只输出「ℹ pass N」、不含
    # 「# pass」，V01 判不过），开关写在文件清单之前
    test_cmd = scripts.get("test", "")
    tap_at = test_cmd.find("--test-reporter=tap")
    assert tap_at != -1, f"scripts.test 必须带 --test-reporter=tap：{test_cmd!r}"
    files_at = test_cmd.find("tests/")
    assert files_at == -1 or tap_at < files_at, f"--test-reporter=tap 要写在文件清单之前：{test_cmd!r}"
    assert pkg.get("dependencies") in (None, {},), f"dependencies 必须为空：{pkg.get('dependencies')}"
    assert pkg.get("devDependencies") == {"electron": "44.9.0"}, (
        f"devDependencies 只有 electron 且恰好 44.9.0：{pkg.get('devDependencies')}"
    )
    lock = json.loads(_shell_read("package-lock.json"))
    assert lock["packages"][""]["devDependencies"]["electron"] == "44.9.0"
    assert lock["packages"]["node_modules/electron"]["version"] == "44.9.0"
    # 共享文件只断言「包含这几行」（合同 Repository facts：node_modules 与 dist 不提交）
    gi = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "desktop/**/node_modules/" in gi
    assert "desktop/**/dist/" in gi


def test_s02_layout_and_scripts_test_listing():
    """D01：合同点名的新文件都在位；scripts.test 显式列出 tests/ 下每个 *.test.js。"""
    for rel in CONTRACT_FILES:
        assert (SHELL / rel).is_file(), f"desktop/shell/{rel} 不存在"
    pkg = json.loads(_shell_read("package.json"))
    test_cmd = pkg["scripts"]["test"]
    listed = set(re.findall(r"tests[/\\][\w.-]+\.test\.js", test_cmd))
    actual = {f"tests/{p.name}" for p in (SHELL / "tests").glob("*.test.js")}
    assert actual, "tests/ 下没有 *.test.js"
    missing = actual - listed
    assert not missing, f"scripts.test 没有显式列出：{sorted(missing)}"
    # 夹具目录不会被当成测试文件跑（夹具文件名不以 .test.js 结尾）
    for p in (SHELL / "tests" / "fixtures").glob("*.test.js"):
        assert False, f"夹具不能叫 *.test.js：{p.name}"


def test_s03_static_scan():
    """D11：require('electron') 只许在 main.js；src/** 与 main.js 里没有改松的字样。"""
    files = [SHELL / "main.js"]
    files += sorted((SHELL / "src").rglob("*.js"))
    files += sorted((SHELL / "tests").rglob("*.js"))
    assert SHELL.is_dir() and files, "desktop/shell 还不存在或扫描范围内没有 .js 文件"
    offenders_electron = [
        str(f.relative_to(REPO_ROOT)) for f in files
        if REQUIRE_ELECTRON_RE.search(f.read_text(encoding="utf-8")) and f.name != "main.js"
    ]
    assert not offenders_electron, f"只有 main.js 可以 require('electron')：{offenders_electron}"
    src_and_main = [SHELL / "main.js"] + sorted((SHELL / "src").rglob("*.js"))
    for f in src_and_main:
        text = f.read_text(encoding="utf-8")
        for pat, what in SRC_FORBIDDEN:
            m = pat.search(text)
            assert not m, f"{f.relative_to(REPO_ROOT)} 出现禁令「{what}」：…{text[max(0, m.start() - 40):m.end() + 40]}…"


def test_s04_main_js_wiring():
    """D11：main.js 的菜单、分区与权限、新窗口拒绝、导航判定、取参与退出的接线标记；
    以及它确实 require 并使用了被测模块（runShell 来自 src/core.js，窗口设置来自 src/window.js）。"""
    text = _shell_read("main.js")
    for marker in MAIN_MARKERS:
        if marker.startswith("setApplicationMenu") or marker == r"['\"]deny['\"]":
            assert re.search(marker, text), f"main.js 缺接线标记：{marker}"
        else:
            assert marker in text, f"main.js 缺接线标记：{marker}"
    # 审核退回项 B1：静态标记与探针之间要有一条断言把「Electron 入口」和「被测模块」连起来——
    # 合同第七节要求「runShell 兑现退出码后 app.exit(code)」「webPreferences 用第六节的结果」。
    assert "runShell" in text, "main.js 没有使用 runShell（合同第七节），src/core.js 的编排成了死代码"
    for pat, what in MAIN_IMPORT_PATTERNS:
        assert pat.search(text), f"main.js 没有 require {what}，src 的纯模块成了死代码"


def test_s05_readme():
    """D12：README 写清装法、跑法、参数、退出码、时限、本体下载与手工冒烟，命令与 scripts 一致。"""
    text = _shell_read("README.md")
    pkg = json.loads(_shell_read("package.json"))
    for needle in ("npm ci", "npm start", "--repo", "--kit", "--assets", "退出码", "install.js",
                   "node_modules/electron", "冒烟"):
        assert needle in text, f"README 缺「{needle}」"
    assert re.search(r"10\s*(秒|s|S)", text), "README 缺 10 秒的时限说明"
    assert re.search(r"30\s*(秒|s|S)", text), "README 缺 30 秒的时限说明"
    assert pkg["scripts"]["start"] == "electron ."


# --------------------------------------------------------------------------- 探针断言（node --test）

PROBE_ARGS = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { parseShellArgs } = require("@SHELL@/src/args.js");

function makeDirs() {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "t025-args-"));
  const repo = path.join(base, "repo");
  const kit = path.join(base, "kit");
  const assets = path.join(base, "assets");
  fs.mkdirSync(repo); fs.mkdirSync(kit); fs.mkdirSync(assets);
  fs.mkdirSync(path.join(kit, "scripts"));
  fs.writeFileSync(path.join(kit, "scripts", "pi_dispatch.py"), "");
  fs.writeFileSync(path.join(assets, "index.html"), "");
  return { base, repo, kit, assets };
}

test("缺必需项：三个按次序用「、」连接", () => {
  const r = parseShellArgs([]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "缺少必需参数：--repo、--kit、--assets");
});

test("缺两个必需项", () => {
  const d = makeDirs();
  const r = parseShellArgs(["--repo", d.repo]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "缺少必需参数：--kit、--assets");
});

test("未知选项", () => {
  const d = makeDirs();
  const r = parseShellArgs(["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--foo", "1"]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "未知参数：--foo");
});

test("多余的位置参数", () => {
  const d = makeDirs();
  const r = parseShellArgs(["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "extra-arg"]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "不接受位置参数：extra-arg");
});

test("--repo 不是目录（不存在的路径）", () => {
  const d = makeDirs();
  const nope = path.join(d.base, "nope");
  const r = parseShellArgs(["--repo", nope, "--kit", d.kit, "--assets", d.assets]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "--repo 不是目录：" + nope);
});

test("--repo 指向文件也算不是目录", () => {
  const d = makeDirs();
  const file = path.join(d.base, "afile");
  fs.writeFileSync(file, "x");
  const r = parseShellArgs(["--repo", file, "--kit", d.kit, "--assets", d.assets]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "--repo 不是目录：" + file);
});

test("--kit 不是目录", () => {
  const d = makeDirs();
  const nope = path.join(d.base, "nok");
  const r = parseShellArgs(["--repo", d.repo, "--kit", nope, "--assets", d.assets]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "--kit 不是目录：" + nope);
});

test("--kit 下没有 scripts/pi_dispatch.py", () => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "t025-args-"));
  const repo = path.join(base, "repo");
  const kit = path.join(base, "kit");
  const assets = path.join(base, "assets");
  fs.mkdirSync(repo); fs.mkdirSync(kit); fs.mkdirSync(assets);
  fs.writeFileSync(path.join(assets, "index.html"), "");
  const r = parseShellArgs(["--repo", repo, "--kit", kit, "--assets", assets]);
  assert.equal(r.ok, false);
  assert.equal(r.error, "--kit 下没有 scripts/pi_dispatch.py：" + kit);
});

test("--assets 不是目录 / 缺 index.html", () => {
  const d = makeDirs();
  const nope = path.join(d.base, "noa");
  const r1 = parseShellArgs(["--repo", d.repo, "--kit", d.kit, "--assets", nope]);
  assert.equal(r1.ok, false);
  assert.equal(r1.error, "--assets 不是目录：" + nope);
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "t025-args-"));
  const repo = path.join(base, "repo"); const kit = path.join(base, "kit"); const assets = path.join(base, "assets");
  fs.mkdirSync(repo); fs.mkdirSync(kit); fs.mkdirSync(assets);
  fs.mkdirSync(path.join(kit, "scripts"));
  fs.writeFileSync(path.join(kit, "scripts", "pi_dispatch.py"), "");
  const r2 = parseShellArgs(["--repo", repo, "--kit", kit, "--assets", assets]);
  assert.equal(r2.ok, false);
  assert.equal(r2.error, "--assets 下没有 index.html：" + assets);
});

test("成功：绝对路径、--python 原样、transcripts 保序", () => {
  const d = makeDirs();
  const r = parseShellArgs([
    "--repo", d.repo, "--kit", d.kit, "--assets", d.assets,
    "--python", "C:/Tools/py 3.exe",
    "--transcript", "t one", "--transcript", "t&two", "--transcript", "q\"uote%",
  ]);
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.repo, path.resolve(d.repo));
  assert.equal(r.value.kit, path.resolve(d.kit));
  assert.equal(r.value.assets, path.resolve(d.assets));
  assert.equal(r.value.python, "C:/Tools/py 3.exe");
  assert.deepEqual(r.value.transcripts, ["t one", "t&two", "q\"uote%"]);
});

test("相对路径转绝对；--python 没给是 null；transcripts 没给是空", () => {
  const d = makeDirs();
  const r = parseShellArgs(["--repo", ".", "--kit", d.kit, "--assets", d.assets]);
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.repo, path.resolve("."));
  assert.equal(r.value.python, null);
  assert.deepEqual(r.value.transcripts ?? [], []);
});
'''


PROBE_PYTHON = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { PYTHON_PROBE_CODE, DEFAULT_PYTHON_CANDIDATES, findPython } = require("@SHELL@/src/python.js");

const td = fs.mkdtempSync(path.join(os.tmpdir(), "t025-py-"));
const exit0 = path.join(td, "exit0.js"); fs.writeFileSync(exit0, "process.exit(0);\n");
const exit1 = path.join(td, "exit1.js"); fs.writeFileSync(exit1, "process.exit(1);\n");
const hang = path.join(td, "hang.js"); fs.writeFileSync(hang, "setInterval(() => {}, 1000);\n");

test("探测代码与默认候选逐字照合同", () => {
  assert.equal(PYTHON_PROBE_CODE, "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)");
  assert.deepEqual(DEFAULT_PYTHON_CANDIDATES, [["python3"], ["python"], ["py", "-3"]]);
});

test("注入 probe：按候选次序试、第一个可用即赢、时限参数传到 probe", async () => {
  const calls = [];
  const probe = async (command, timeoutMs) => {
    calls.push([command, timeoutMs]);
    return command[0] === "python"
      ? { ok: true, reason: "" }
      : { ok: false, reason: "命令不存在" };
  };
  const r = await findPython({ probe, timeoutMs: 123 });
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.deepEqual(r.command, ["python"]);
  assert.equal(calls.length, 2, JSON.stringify(calls));
  assert.deepEqual(calls[0][0], ["python3"]);
  assert.deepEqual(calls[1][0], ["python"]);
  assert.equal(calls[1][1], 123);
});

test("注入 probe：全失败给 tried 与总结错误", async () => {
  const probe = async (command) => ({ ok: false, reason: "退出码 1" });
  const r = await findPython({ probe });
  assert.equal(r.ok, false);
  assert.equal(r.error, "找不到可用的 Python（要求 ≥ 3.10）");
  assert.equal(r.tried.length, 3);
  assert.deepEqual(r.tried.map((t) => t.command), [["python3"], ["python"], ["py", "-3"]]);
  for (const t of r.tried) {
    assert.equal(typeof t.reason, "string");
    assert.ok(t.reason.length > 0);
  }
});

test("v2 §三：给了 python 选项就只试它一个、失败不回退到默认候选", async () => {
  const calls = [];
  const probe = async (command) => { calls.push(command); return { ok: false, reason: "退出码 1" }; };
  const r = await findPython({ python: "my-py 3", probe, timeoutMs: 500 });
  assert.equal(r.ok, false, JSON.stringify(r));
  assert.ok(r.error.includes("指定的 Python 不可用"), JSON.stringify(r));
  assert.ok(r.error.includes("my-py 3"), JSON.stringify(r));
  assert.equal(calls.length, 1, JSON.stringify(calls));
  assert.deepEqual(calls[0], ["my-py 3"]);
  assert.equal(r.tried.length, 1, JSON.stringify(r));
  assert.deepEqual(r.tried[0].command, ["my-py 3"]);
});

test("v2 §三：python 选项可用时也只试它一个", async () => {
  const calls = [];
  const probe = async (command) => { calls.push(command); return { ok: true, reason: "" }; };
  const r = await findPython({ python: "py9", probe });
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.deepEqual(r.command, ["py9"]);
  assert.equal(calls.length, 1, JSON.stringify(calls));
});

test("v2 §三：python 为 null 时走默认候选", async () => {
  const probe = async () => ({ ok: true, reason: "" });
  const r = await findPython({ python: null, probe });
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.deepEqual(r.command, ["python3"]);
});

test("注入 probe：单个候选失败不回退到别的候选", async () => {
  const probe = async () => ({ ok: false, reason: "命令不存在" });
  const r = await findPython({ candidates: [["my-python"]], probe });
  assert.equal(r.ok, false);
  assert.equal(r.tried.length, 1);
});

test("真起进程：退出码非 0 跳过、下一个赢", async () => {
  const r = await findPython({
    candidates: [[process.execPath, exit1], [process.execPath, exit0]],
    timeoutMs: 8000,
  });
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.deepEqual(r.command, [process.execPath, exit0]);
});

test("真起进程：退出码非 0 算不可用", async () => {
  const r = await findPython({ candidates: [[process.execPath, exit1]], timeoutMs: 8000 });
  assert.equal(r.ok, false);
  assert.equal(r.tried.length, 1);
  assert.ok(r.tried[0].reason.includes("退出码"), JSON.stringify(r.tried));
});

test("真起进程：命令不存在被跳过", async () => {
  const r = await findPython({ candidates: [["t025-no-such-cmd-xyz"]], timeoutMs: 8000 });
  assert.equal(r.ok, false);
  assert.equal(r.tried.length, 1);
  assert.ok(r.tried[0].reason.includes("存在"), JSON.stringify(r.tried));
});

test("真起进程：超时算不可用", async () => {
  const r = await findPython({ candidates: [[process.execPath, hang]], timeoutMs: 400 });
  assert.equal(r.ok, false);
  assert.equal(r.tried.length, 1);
  assert.ok(r.tried[0].reason.includes("超时"), JSON.stringify(r.tried));
});
'''


PROBE_HANDSHAKE = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { parseHandshake } = require("@SHELL@/src/handshake.js");

const TOKEN = "ctrl-tok-XYZ";
const NONCE = "nonceABC";
const ORIGIN = "http://127.0.0.1:8123";
function okLine(over) {
  const obj = Object.assign({
    themis_ui: 1,
    bootstrap: ORIGIN + "/bootstrap/" + NONCE,
    origin: ORIGIN,
    control: TOKEN,
    pid: 4242,
  }, over || {});
  for (const k of Object.keys(over || {})) if (over[k] === undefined) delete obj[k];
  return JSON.stringify(obj);
}

async function expectError(line, msg) {
  const r = await Promise.resolve().then(() => parseHandshake(line));
  assert.equal(r.ok, false, JSON.stringify(r));
  assert.equal(r.error, msg, JSON.stringify(r));
  // 错误不回显任何字段的值（D04）
  assert.ok(!r.error.includes(TOKEN), "错误回显了 control：" + r.error);
  assert.ok(!r.error.includes(NONCE), "错误回显了 nonce：" + r.error);
  assert.ok(!r.error.includes("4242"), "错误回显了 pid：" + r.error);
}

test("正例：合法握手（含行尾 \\r）", async () => {
  const r = await Promise.resolve().then(() => parseHandshake(okLine() + "\r"));
  assert.equal(r.ok, true, JSON.stringify(r));
  const v = r.value;
  assert.equal(v.themis_ui, 1);
  assert.equal(v.bootstrap, ORIGIN + "/bootstrap/" + NONCE);
  assert.equal(v.origin, ORIGIN);
  assert.equal(v.control, TOKEN);
  assert.equal(v.pid, 4242);
});

test("多行输入只认第一行", async () => {
  const r = await Promise.resolve().then(() => parseHandshake(okLine() + "\n" + okLine({ themis_ui: 2, pid: 1 })));
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.themis_ui, 1);
  assert.equal(r.value.pid, 4242);
});

test("不是 JSON / 不是对象", async () => {
  await expectError("not json at all", "握手行不是 JSON 对象");
  await expectError("[1, 2]", "握手行不是 JSON 对象");
  await expectError("\"a string\"", "握手行不是 JSON 对象");
  await expectError("123", "握手行不是 JSON 对象");
});

test("缺字段：按 themis_ui、bootstrap、origin、control、pid 的次序", async () => {
  await expectError("{}", "握手缺字段：themis_ui、bootstrap、origin、control、pid");
  await expectError(okLine({ themis_ui: undefined, bootstrap: undefined }), "握手缺字段：themis_ui、bootstrap");
  await expectError(okLine({ control: undefined, pid: undefined }), "握手缺字段：control、pid");
});

test("协议版本不对", async () => {
  await expectError(okLine({ themis_ui: 2 }), "握手的协议版本不对");
  await expectError(okLine({ themis_ui: "1" }), "握手的协议版本不对");
});

test("origin 不严格匹配", async () => {
  await expectError(okLine({ origin: "http://localhost:8123" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
  await expectError(okLine({ origin: "https://127.0.0.1:8123" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
  await expectError(okLine({ origin: "http://127.0.0.1" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
  await expectError(okLine({ origin: "http://127.0.0.1:8123/x" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
  await expectError(okLine({ origin: "http://127.0.0.1:0" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
  await expectError(okLine({ origin: "http://127.0.0.1:65536" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
  await expectError(okLine({ origin: "http://127.0.0.1:99999" }), "握手的 origin 不是 http://127.0.0.1:<端口>");
});

test("bootstrap 不在服务 origin 下", async () => {
  await expectError(okLine({ bootstrap: "http://127.0.0.1:9999/bootstrap/x" }), "握手的 bootstrap 不在服务 origin 下");
  await expectError(okLine({ bootstrap: "http://evil.example/bootstrap/x" }), "握手的 bootstrap 不在服务 origin 下");
  await expectError(okLine({ bootstrap: "not a url" }), "握手的 bootstrap 不在服务 origin 下");
});

test("control 不是非空字符串", async () => {
  await expectError(okLine({ control: "" }), "握手的 control 不是非空字符串");
  await expectError(okLine({ control: 123 }), "握手的 control 不是非空字符串");
});

test("pid 不是正整数", async () => {
  await expectError(okLine({ pid: 0 }), "握手的 pid 不是正整数");
  await expectError(okLine({ pid: -5 }), "握手的 pid 不是正整数");
  await expectError(okLine({ pid: 1.5 }), "握手的 pid 不是正整数");
  await expectError(okLine({ pid: "4242" }), "握手的 pid 不是正整数");
});

test("边界端口照常通过", async () => {
  const r = await Promise.resolve().then(() => parseHandshake(okLine({ origin: "http://127.0.0.1:1", bootstrap: "http://127.0.0.1:1/bootstrap/x" })));
  assert.equal(r.ok, true, JSON.stringify(r));
});
'''


PROBE_WINDOW = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const { partitionName, webPreferences, isServiceUrl } = require("@SHELL@/src/window.js");

test("webPreferences 恰好合同那十个键，没有 preload", () => {
  assert.deepEqual(webPreferences("sess-abc"), {
    contextIsolation: true,
    sandbox: true,
    nodeIntegration: false,
    webSecurity: true,
    allowRunningInsecureContent: false,
    webviewTag: false,
    nodeIntegrationInWorker: false,
    nodeIntegrationInSubFrames: false,
    spellcheck: false,
    partition: "sess-abc",
  });
});

test("partitionName：非空、不带 persist: 前缀、两次不同", () => {
  const a = partitionName();
  const b = partitionName();
  assert.equal(typeof a, "string");
  assert.ok(a.length > 0);
  assert.ok(!a.startsWith("persist:"), a);
  assert.notEqual(a, b);
});

test("isServiceUrl 正例", () => {
  assert.equal(isServiceUrl("http://127.0.0.1:8080/", "http://127.0.0.1:8080"), true);
  assert.equal(isServiceUrl("http://127.0.0.1:8080/app?x=1#h", "http://127.0.0.1:8080"), true);
});

test("isServiceUrl 反例：别的端口、localhost、https、userinfo、子域、特殊协议、非法串", () => {
  const origin = "http://127.0.0.1:8080";
  assert.equal(isServiceUrl("http://127.0.0.1:8081/", origin), false);
  assert.equal(isServiceUrl("http://localhost:8080/", origin), false);
  assert.equal(isServiceUrl("https://127.0.0.1:8080/", origin), false);
  assert.equal(isServiceUrl("http://127.0.0.1:8080@evil.example/", origin), false);
  assert.equal(isServiceUrl("http://127.0.0.1:8080.evil.example/", origin), false);
  assert.equal(isServiceUrl("javascript:alert(1)", origin), false);
  assert.equal(isServiceUrl("file:///C:/x", origin), false);
  assert.equal(isServiceUrl("data:text/html,hi", origin), false);
  assert.equal(isServiceUrl("about:blank", origin), false);
  assert.equal(isServiceUrl("not a url at all", origin), false);
});
'''


PROBE_SERVICE = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { serviceCommand, startService, stopService } = require("@SHELL@/src/service.js");

const td = fs.mkdtempSync(path.join(os.tmpdir(), "t025-svc-"));
const SVC = path.join(td, "fake-service.js");
// 假服务：FAKE_SERVICE_MODE 切换行为；ok 模式下 stdin 若收到任何数据就以 9 退出（外壳的 stdin 一个字节都不写）
fs.writeFileSync(SVC, [
  "const mode = process.env.FAKE_SERVICE_MODE || 'ok';",
  "const line = JSON.stringify({ themis_ui: 1, bootstrap: 'http://127.0.0.1:8123/bootstrap/nonceABC', origin: 'http://127.0.0.1:8123', control: 'ctrl-tok-XYZ', pid: 4242 }) + '\\n';",
  "let gotData = false;",
  "if (mode === 'bad') process.stdout.write('not-json\\n');",
  "else if (mode !== 'silent' && mode !== 'exit2') {",
  "  if (mode === 'split') { process.stdout.write(line.slice(0, 20)); setTimeout(() => process.stdout.write(line.slice(20)), 60); }",
  "  else process.stdout.write(line);",
  "}",
  "if (mode === 'exit2') process.exit(2);",
  "if (mode === 'ignore-eof') setInterval(() => {}, 1000);",
  "process.stdin.on('data', () => { gotData = true; });",
  "process.stdin.on('end', () => { if (mode === 'ignore-eof') return; process.exit(mode === 'exit7' ? 7 : (gotData ? 9 : 0)); });",
  "process.stdin.on('error', () => {});",
  "process.stdin.resume();",
  "setTimeout(() => process.exit(0), 8000).unref();",
].join("\n"));

function cmd(mode) {
  return {
    command: [process.execPath, SVC],
    timeoutMs: 5000,
    env: Object.assign({}, process.env, { FAKE_SERVICE_MODE: mode }),
  };
}

test("serviceCommand：参数列表、空格 & \" % 原样到达、--repo 在 ui 之前", () => {
  const python = ["py", "-3"];
  const kit = "C:/Kit Dir";
  const repo = "C:/My Repo&a";
  const assets = "C:/As\"sets%";
  const argv = serviceCommand({ python, kit, repo, assets, transcripts: ["t one", "t&two", "q\"uote%"] });
  assert.ok(Array.isArray(argv));
  assert.deepEqual(argv.slice(0, 2), python);
  assert.equal(path.normalize(argv[2]), path.normalize(path.join(kit, "scripts", "pi_dispatch.py")));
  assert.equal(argv[3], "--repo");
  assert.equal(argv[4], repo);
  assert.equal(argv[5], "ui");
  assert.equal(argv[6], "--desktop");
  assert.equal(argv[7], "--assets");
  assert.equal(argv[8], assets);
  assert.deepEqual(argv.slice(9), ["--transcript", "t one", "--transcript", "t&two", "--transcript", "q\"uote%"]);
});

test("serviceCommand：没有 transcripts 就没有 --transcript 项", () => {
  const argv = serviceCommand({ python: ["python"], kit: "K", repo: "R", assets: "A", transcripts: [] });
  assert.ok(!argv.includes("--transcript"));
});

test("正常握手与干净关停（stdin 一个字节都不写）", async () => {
  process.env.FAKE_SERVICE_MODE = "ok";
  const { child, handshake } = await startService(cmd("ok"));
  const hs = handshake.value ?? handshake;
  assert.equal(hs.control, "ctrl-tok-XYZ");
  assert.equal(hs.origin, "http://127.0.0.1:8123");
  const r = await stopService(child, { graceMs: 4000 });
  assert.equal(r.exited, true, JSON.stringify(r));
  assert.equal(r.code, 0, JSON.stringify(r));
  assert.equal(r.killed, false, JSON.stringify(r));
});

test("握手分两段写也能拼成一行", async () => {
  process.env.FAKE_SERVICE_MODE = "split";
  const { child, handshake } = await startService(cmd("split"));
  const hs = handshake.value ?? handshake;
  assert.equal(hs.control, "ctrl-tok-XYZ");
  await stopService(child, { graceMs: 4000 });
});

test("握手行不合法被拒", async () => {
  process.env.FAKE_SERVICE_MODE = "bad";
  await assert.rejects(
    () => startService(cmd("bad")),
    (e) => String(e).includes("握手行不是 JSON 对象"),
  );
});

test("不写握手：超时被拒", async () => {
  process.env.FAKE_SERVICE_MODE = "silent";
  await assert.rejects(
    () => startService(Object.assign(cmd("silent"), { timeoutMs: 700 })),
    (e) => String(e).includes("握手超时"),
  );
});

test("握手前以 2 退出：错误里有退出码", async () => {
  process.env.FAKE_SERVICE_MODE = "exit2";
  await assert.rejects(
    () => startService(cmd("exit2")),
    (e) => String(e).includes("服务在握手前退出（退出码 2）"),
  );
});

test("服务忽略 EOF：宽限期一到被结束", async () => {
  process.env.FAKE_SERVICE_MODE = "ignore-eof";
  const { child } = await startService(cmd("ignore-eof"));
  const r = await stopService(child, { graceMs: 500 });
  assert.equal(r.killed, true, JSON.stringify(r));
  assert.equal(r.exited, false, JSON.stringify(r));
  assert.equal(r.code, null, JSON.stringify(r));
});

test("EOF 后服务以 7 退出：exited 与 code 如实报告", async () => {
  process.env.FAKE_SERVICE_MODE = "exit7";
  const { child } = await startService(cmd("exit7"));
  const r = await stopService(child, { graceMs: 4000 });
  assert.equal(r.exited, true, JSON.stringify(r));
  assert.equal(r.code, 7, JSON.stringify(r));
  assert.equal(r.killed, false, JSON.stringify(r));
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
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "t025-core-"));
  const repo = path.join(base, "repo");
  const kit = path.join(base, "kit");
  const assets = path.join(base, "assets");
  fs.mkdirSync(repo); fs.mkdirSync(kit); fs.mkdirSync(assets);
  fs.mkdirSync(path.join(kit, "scripts"));
  fs.writeFileSync(path.join(kit, "scripts", "pi_dispatch.py"), "");
  fs.writeFileSync(path.join(assets, "index.html"), "");
  return { repo, kit, assets };
}

// 假 spawn：返回一个行为可配置的假子进程（握手行 + 可选的握手后退出 / stdin 关闭后退出）
function fakeSpawn(opts) {
  const calls = [];
  const fn = (command, args, options) => {
    // v2 §五：调用形状固定为 spawn(command, [], options)——command 是完整 argv 数组、第二个参数恒为 []
    assert.ok(Array.isArray(command), "spawn 的第一个参数必须是完整 argv 数组，收到：" + String(command));
    assert.deepEqual(args, [], "spawn 的第二个参数必须恒为 []，收到：" + JSON.stringify(args));
    calls.push(command);
    const child = new EventEmitter();
    child.stdout = new PassThrough();
    child.stdin = new PassThrough();
    child.pid = 424242;
    child.spawnargs = command;
    child.kill = () => {
      child.killed = true;
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
    if (opts.exitAfter !== undefined) {
      setTimeout(() => {
        child.exitCode = opts.exitAfter;
        child.emit("exit", opts.exitAfter, null);
        child.emit("close", opts.exitAfter, null);
      }, 80);
    }
    return child;
  };
  fn.calls = calls;
  return fn;
}

function makeIo() {
  const out = [];
  const err = [];
  return {
    io: {
      stdout: { write: (c) => out.push(String(c)) },
      stderr: { write: (c) => err.push(String(c)) },
    },
    all: () => out.join("") + err.join(""),
    errors: () => err.join(""),
  };
}

function makeWindow(opts) {
  const w = {
    calls: [],
    closeCalled: false,
    openWindow: async (arg) => {
      w.calls.push(arg);
      return {
        closed: opts && opts.closed ? opts.closed : new Promise(() => {}),
        close: () => { w.closeCalled = true; },
      };
    },
  };
  return w;
}

function assertNoSecrets(io, w) {
  const text = io.all();
  assert.ok(!text.includes(TOKEN), "输出里出现了控制令牌：" + text);
  assert.ok(!text.includes(NONCE), "输出里出现了 nonce：" + text);
  for (const arg of w.calls) {
    assert.ok(!JSON.stringify(arg).includes(TOKEN), "openWindow 的参数里出现了控制令牌");
  }
}

test("参数错：退出码 2、不开窗口、stderr 有 ERROR:", async () => {
  const d = makeDirs();
  const io = makeIo();
  const w = makeWindow();
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow: w.openWindow, spawn, env: process.env,
  });
  assert.equal(code, 2);
  assert.equal(w.calls.length, 0);
  assert.equal(spawn.calls.length, 0);
  assert.ok(io.errors().includes("ERROR: "), io.errors());
});

test("指定的 Python 不可用：退出码 1、不起服务、不开窗口", async () => {
  const d = makeDirs();
  const io = makeIo();
  const w = makeWindow();
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "t025-no-such-python-xyz"],
    io: io.io, openWindow: w.openWindow, spawn, env: process.env,
  });
  assert.equal(code, 1);
  assert.equal(spawn.calls.length, 0);
  assert.equal(w.calls.length, 0);
  assert.ok(io.errors().includes("ERROR: "), io.errors());
});

test("正常流程：关窗口、服务以 0 退出 → 0；openWindow 只收 bootstrap 与 origin", async () => {
  const d = makeDirs();
  const io = makeIo();
  const w = makeWindow({ closed: Promise.resolve() });
  const spawn = fakeSpawn({ exitOnStdinEnd: 0 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow: w.openWindow, spawn, env: process.env,
  });
  assert.equal(code, 0, io.all());
  assert.equal(w.calls.length, 1);
  assert.deepEqual(Object.keys(w.calls[0]).sort(), ["bootstrap", "origin"]);
  assert.equal(w.calls[0].origin, ORIGIN);
  assertNoSecrets(io, w);
});

test("服务意外退出：退出码 1、stderr 有退出码、窗口被关掉", async () => {
  const d = makeDirs();
  const io = makeIo();
  const w = makeWindow();
  const spawn = fakeSpawn({ exitAfter: 3 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow: w.openWindow, spawn, env: process.env,
  });
  assert.equal(code, 1);
  assert.ok(io.errors().includes("服务意外退出（退出码 3）"), io.errors());
  assert.equal(w.closeCalled, true);
  assertNoSecrets(io, w);
});

test("关窗口后服务以 7 退出：退出码 1", async () => {
  const d = makeDirs();
  const io = makeIo();
  const w = makeWindow({ closed: Promise.resolve() });
  const spawn = fakeSpawn({ exitOnStdinEnd: 7 });
  const code = await runShell({
    argv: ["--repo", d.repo, "--kit", d.kit, "--assets", d.assets, "--python", "python"],
    io: io.io, openWindow: w.openWindow, spawn, env: process.env,
  });
  assert.equal(code, 1);
  assert.ok(io.errors().includes("服务没有以 0 正常退出"), io.errors());
  assertNoSecrets(io, w);
});
'''


def test_p01_probe_args():
    """D02：parseShellArgs 的错误文案、路径校验与成功形状（node --test 探针）。"""
    _expect_probe_pass("t025-args", PROBE_ARGS)


def test_p02_probe_python():
    """D03：探测代码、默认候选、findPython 的顺序/首胜/失败收集（node --test 探针）。"""
    _expect_probe_pass("t025-python", PROBE_PYTHON)


def test_p03_probe_handshake():
    """D04：parseHandshake 的正例、七类错误与不回显字段值（node --test 探针）。"""
    _expect_probe_pass("t025-handshake", PROBE_HANDSHAKE)


def test_p04_probe_window():
    """D08：webPreferences 十键、partitionName、isServiceUrl 正反例（node --test 探针）。"""
    _expect_probe_pass("t025-window", PROBE_WINDOW)


def test_p05_probe_service():
    """D05–D07：serviceCommand 参数列表与 startService/stopService 的真实子进程行为（node --test 探针）。"""
    _expect_probe_pass("t025-service", PROBE_SERVICE)


def test_p06_probe_core():
    """D09、D10：runShell 的退出码编排、openWindow 只收引导地址与 origin、输出无令牌（node --test 探针）。"""
    _expect_probe_pass("t025-core", PROBE_CORE)
