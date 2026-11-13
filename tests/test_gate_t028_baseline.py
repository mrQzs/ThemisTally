"""T028 战前门禁：桌面端外壳第 3 片「外壳页数据层」的黑盒基准测试
（合同 t028-desktop-shell-pages v1，基线 0592200dd4——``desktop/shell/src`` 只有 T025/T026 的模块，
settings.js / detect.js / shellapi.js 与四个新测试文件都还不存在）。

被测对象是外壳页的数据层：``src/settings.js``（设置文件 ``<userData>/settings.json`` 的读、坏文件
另存副本、原子写、补丁校验与应用、仓库与会话目录的去重与唯一 id）、``src/detect.js``（三项校验与
自动检测：仓库只看文件系统、Python ≥ 3.10、kit 跑 ``pi_dispatch.py --version``；子进程 10 秒时限、
不经 shell）、``src/shellapi.js``（``createShellApi`` 十个成员：getState、四个选择器、saveSettings、
openExternal 与三个占位），以及 ``package.json``/``README.md`` 的只增改。

基线（0592200dd4）上这些文件与符号都不存在，所以失败都落在「文件不存在」「标记不在」与探针子进程
退出码非 0 这类断言上，不是收集失败：模块级只导入标准库，仓库文件的读取与探针的运行都发生在用例
函数里。探针是自包含的 ``node --test`` 文件（Node 24 自带，不需要 npm ci，不 require electron）。
Python 把探针源码写进系统临时目录、以仓库根为 cwd 运行、用完即删；探针里的被测模块用绝对路径
require（``@SHELL@`` 占位符替换），类型文件用 ``@THEMIS_TS@`` 占位符替换。

结构（编号对应合同 DoD 的 D01–D10）：

- 静态断言（``test_s*``，不需要任何依赖）：
  - S01/D08：合同 Scope 点名的 7 个新文件都在位（只断言「在位」，不断言「只有这些」）。
  - S02/D07/D09：``package.json`` 只动 ``scripts.test``——tap 开关仍在文件清单之前、显式列出
    ``tests/`` 下每一个 ``*.test.js``（数据驱动）且本片四个新测试点名在列、``tests/fixtures/`` 下
    没有 ``*.test.js``；devDependencies 仍是 ``{"electron": "44.9.0"}``、锁文件两处 44.9.0 不动。
  - S03/D03/D06/D08：静态禁令按站主收窄后的规矩——``src/settings.js`` 里只许
    writeFileSync/renameSync/mkdirSync/unlinkSync 四个写函数，其余写函数（含 rmSync(、mkdir(、
    异步 fs.promises.writeFile(）照旧不许；detect.js 与 shellapi.js 一个写函数都不许；T025 的 7 条
    禁令（persist:/shell: true/写函数/fetch(/net.request/autoUpdater/crashReporter）在 main.js 与
    src/** 照旧；dialog、shell.openExternal、showItemInFolder、Notification 只许 main.js。接线断言：
    detect.js 必须 require ``./python.js``（DEFAULT_PYTHON_CANDIDATES 只读引用），shellapi.js 必须
    require ``./settings.js``、``./detect.js``、``./hostcheck.js``（isExternalUrl 复用）——否则纯模块
    成了没人用的死代码。
  - S04（过渡，T028b 会推翻）：``require('electron')`` 只许 main.js/preload.js、ipcMain.on 与
    ipcRenderer.send 在 desktop/shell 下全禁（与 T026 门禁同款；T028b 要加带 electron 的
    shell-preload.js 与 IPC 接线，届时由站主按名字退役本用例）。
  - S05/D09：README 新增「设置与校验」一节（settings.json、坏文件副本、.git 与 .agent、3.10、
    pi_dispatch.py、10 秒时限、不存凭据与控制令牌），T025 的既有字样全部保留。
  - S06/D07：T025/T026 已有的 12 份测试文件一条没删没改名，且仍被 scripts.test 点名。
- 探针断言（``test_p*``，跑 node --test）：
  - P01/D01：settings 存盘——常量逐字（DEFAULT_SETTINGS 冻结、四张键表/取值表）、文件不存在用
    缺省的深拷贝、坏 JSON/顶层不是对象/已知键非法走缺省并另存带 UTC 时刻的副本（副本是原始字节、
    同名不覆盖依次 -2/-3）、未知键忽略且写盘后消失、写盘内容是 JSON.stringify(obj, null, 2)+"\\n"
    且键按 SETTINGS_FILE_KEYS 顺序、目录不存在也能写、成功后没有 .tmp 残留、写临时文件失败抛错且
    原文件不动、rename 失败时临时文件被清掉。
  - P02/D02：applyPatch 六键白名单与三类拒绝（bad-patch/unknown-id/current-repo）及校验顺序、
    拒绝与成功都不改入参、整包应用；normalizeSettings；addRepo/addTranscriptDir 的路径去重
    （resolve、Windows 不分大小写）、id 生成（basename、-2/-3、空基名用 "repo"）、currentRepo 只在
    为空时设置。
  - P03/D03：runProcess（参数原样到达证明不经 shell、shell:false/windowsHide:true/stdio 三管、
    超时 timedOut:true、起不来回 error:ENOENT）；checkRepo 三种结果（.git 目录、.git 文件、
    缺 .git、.agent 不是目录、路径不存在）；probePython（两行 ok、一行/空 bad-output、退出码非 0
    version-too-old、超时、起不来）；probeKit（stdout/stderr 取版本、无版本、非 0、超时、没有
    pythonPath）；detectPython 按 python3 → python → py -3 顺序首胜、全失败 missing；detectKit 的
    external/repo/missing。
  - P04/D04/D02/D07：createShellApi——四个选择器各自的取消/保存/被拒与「只有保存才写盘」（字节级
    比对）、pickRepo 只在 currentRepo 为空时设当前、pickKit 无可用 Python 回 python-unusable、
    pickTranscriptDir 不回 rejected、pickPython/pickKit 的 saved 无 id 字段；saveSettings 的拒绝
    表与字节不变、成功整包应用；检测缓存（getState 不重复探测、pickPython/pickKit/saveSettings
    之后刷新）；写盘失败回 write-failed 且内存回滚；三个占位成员的形状；垃圾输入不抛错。
  - P05/D05：形状比对——读 ``desktop/web/src/shellpages/themisShell.ts``，按合同钉死的规则解析出
    ThemisShell/ShellState/ShellSettings/RepoEntry/TranscriptDirEntry/SettingsPatch 的字段名与
    RepoCheck/PickProblem/ServiceState/theme/density 的字面量，与真实返回值、settings.js 的键表
    逐项比对（测试里不另抄键表，解析不到就断言失败）。
  - P06/D06：openExternal——bad-url 的判定与 hostcheck.js 的 isExternalUrl 逐项等价、确认取消
    cancelled、打开失败 open-failed、确认框抛错 internal、成功 {ok:true, value:null}。
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

# 合同 Scope 点名的新文件（只断言「在位」，不断言「只有这些」——后面的片会继续往 desktop/shell 加文件）
CONTRACT_FILES = (
    "src/settings.js", "src/detect.js", "src/shellapi.js",
    "tests/settings.test.js", "tests/detect.test.js", "tests/shellapi.test.js", "tests/shellshape.test.js",
)

# 本片新增的四份测试文件：scripts.test 必须显式点名（D07/D09）
NEW_TEST_FILES = (
    "tests/settings.test.js", "tests/detect.test.js", "tests/shellapi.test.js", "tests/shellshape.test.js",
)

# T025/T026 已有的测试文件：一条也没删（D07）
PREEXISTING_TEST_FILES = (
    "tests/args.test.js", "tests/package.test.js", "tests/python.test.js", "tests/handshake.test.js",
    "tests/service.test.js", "tests/window.test.js", "tests/core.test.js", "tests/control.test.js",
    "tests/host.test.js", "tests/hostcheck.test.js", "tests/ipc.test.js", "tests/preload.test.js",
)

REQUIRE_ELECTRON_RE = re.compile(r"require\(\s*['\"]electron['\"]\s*\)")

# T025 的 7 条禁令（站主 0592200 收窄后）：src/** 与 main.js 里不许出现，注释也不行
SRC_FORBIDDEN = (
    (re.compile(r"persist:"), "persist: 前缀"),
    (re.compile(r"shell\s*:\s*true"), "shell: true"),
    (re.compile(r"\b(writeFile|writeFileSync|appendFile|appendFileSync|mkdir|mkdirSync|rm|rmSync|unlink|unlinkSync|rename|renameSync)\s*\("), "fs 写函数"),
    (re.compile(r"\bfetch\s*\("), "fetch"),
    (re.compile(r"\bnet\.request\b"), "net.request"),
    (re.compile(r"\bautoUpdater\b"), "autoUpdater"),
    (re.compile(r"\bcrashReporter\b"), "crashReporter"),
)

# 站主 2026-11-12 拍板的收窄：src/settings.js 里许用 writeFileSync、renameSync、mkdirSync、unlinkSync 四个；
# 别的写函数（writeFile、appendFile、appendFileSync、mkdir、rm、rmSync、unlink、rename，异步的
# fs.promises.writeFile 也命中）在它里面照旧不许，别的文件一个都不许
SETTINGS_JS_REL = "src/settings.js"
NARROWED_WRITE_RE = re.compile(r"\b(writeFile|appendFile|appendFileSync|mkdir|rm|rmSync|unlink|rename)\s*\(")

# 「只在 X」的词面规则：scope=="product" 只扫 main.js 与 src/**（与 T025/T026 门禁一致，tests/** 的
# 注释文字不误伤）；scope=="all" 扫 desktop/shell 下全部 .js
WORD_RULES = (
    (re.compile(r"\bhttp\s*\.\s*request\b"), "http.request", ("src/control.js",), "product"),
    (re.compile(r"\bshell\s*\.\s*openExternal\b"), "shell.openExternal", ("main.js",), "product"),
    (re.compile(r"\bshowItemInFolder\b"), "showItemInFolder", ("main.js",), "product"),
    (re.compile(r"\bdialog\b"), "dialog", ("main.js",), "product"),
    (re.compile(r"\bNotification\b"), "Notification", ("main.js",), "product"),
)

ALL_RULES = (
    (REQUIRE_ELECTRON_RE, "require('electron')", ("main.js", "preload.js")),
    (re.compile(r"\bipcMain\s*\.\s*on\b"), "ipcMain.on", ()),
    (re.compile(r"\bipcRenderer\s*\.\s*send\b"), "ipcRenderer.send", ()),
)

# 接线断言：被测纯模块必须真的被 require（容忍省略 .js 后缀），否则文本标记凑得齐、模块却是死代码
REQUIRE_RULES = (
    ("src/detect.js", re.compile(r"""require\(\s*['"]\.\/python(\.js)?['"]\s*\)"""), "./python.js（DEFAULT_PYTHON_CANDIDATES 的只读引用）"),
    ("src/shellapi.js", re.compile(r"""require\(\s*['"]\.\/settings(\.js)?['"]\s*\)"""), "./settings.js（applyPatch/addRepo/addTranscriptDir 的来源）"),
    ("src/shellapi.js", re.compile(r"""require\(\s*['"]\.\/detect(\.js)?['"]\s*\)"""), "./detect.js（checkRepo 与探测函数的来源）"),
    ("src/shellapi.js", re.compile(r"""require\(\s*['"]\.\/hostcheck(\.js)?['"]\s*\)"""), "./hostcheck.js（isExternalUrl 的来源）"),
)

# README：本片新增「设置与校验」一节的要点（D09）；T025 的要点也要全保留
README_T028_NEEDLES = (
    "设置与校验", "settings.json", "userData", "副本", ".git", ".agent", "3.10",
    "pi_dispatch.py", "凭据", "控制令牌",
)
README_T025_NEEDLES = (
    "npm ci", "npm start", "--repo", "--kit", "--assets", "退出码", "install.js",
    "node_modules/electron", "冒烟",
)


def _shell_read(rel: str) -> str:
    p = SHELL / rel
    assert p.is_file(), f"desktop/shell/{rel} 不存在"
    return p.read_text(encoding="utf-8")


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


def _run_probe(name: str, source: str, timeout: float = 300.0) -> subprocess.CompletedProcess:
    node = shutil.which("node")
    assert node, "本机没有 node，无法运行门禁探针"
    with tempfile.TemporaryDirectory(prefix="t028-gate-") as td:
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
    proc = _run_probe(name, source)
    assert proc.returncode == 0, (
        f"探针 {name} 没有全绿（退出码 {proc.returncode}）：\n"
        f"--- stdout 末尾 ---\n{proc.stdout[-5000:]}\n--- stderr 末尾 ---\n{proc.stderr[-2000:]}"
    )


# --------------------------------------------------------------------------- 静态断言

def test_s01_contract_files():
    """D08/Scope：合同点名的 7 个新文件都在位。"""
    for rel in CONTRACT_FILES:
        assert (SHELL / rel).is_file(), f"desktop/shell/{rel} 不存在"


def test_s02_package_json_and_lock():
    """D07/D09：package.json 只动 scripts.test（tap 开关、点名四个新测试、数据驱动全量点名），
    依赖与锁文件不动；夹具目录里不许有 *.test.js。"""
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


def test_s03_static_bans():
    """D03/D06/D08：写函数禁令按站主收窄后的规矩生效；敏感词只许 main.js；
    三个新模块必须真的 require 它们该复用的模块。"""
    # 三个新文件必须在位才能扫（S01 负责在位断言，这里拿到文件对象逐个扫）
    for rel in ("src/settings.js", "src/detect.js", "src/shellapi.js"):
        assert (SHELL / rel).is_file(), f"desktop/shell/{rel} 不存在"
    files = _js_files()
    assert files, "desktop/shell 扫描范围内没有 .js 文件"
    for f in files:
        rel = str(f.relative_to(SHELL)).replace("\\", "/")
        text = f.read_text(encoding="utf-8")
        in_product = rel == "main.js" or rel.startswith("src/")
        for pat, what, allowed, scope in WORD_RULES:
            if scope == "product" and not in_product:
                continue
            m = pat.search(text)
            if m and rel not in allowed:
                raise AssertionError(
                    f"desktop/shell/{rel} 出现只许在 {list(allowed) or '任何文件都不许'} 的「{what}」："
                    f"…{text[max(0, m.start() - 40):m.end() + 40]}…"
                )
        # detect.js 与 shellapi.js 一个写函数都不许（合同：不写任何文件）
        if rel in ("src/detect.js", "src/shellapi.js"):
            m = SRC_FORBIDDEN[2][0].search(text)
            assert m is None, (
                f"desktop/shell/{rel} 不许出现任何写文件函数："
                f"…{text[max(0, m.start() - 40):m.end() + 40]}…"
            )
    for f in [SHELL / "main.js"] + sorted((SHELL / "src").rglob("*.js")):
        text = f.read_text(encoding="utf-8")
        rel = str(f.relative_to(SHELL)).replace("\\", "/")
        for pat, what in SRC_FORBIDDEN:
            if what == "fs 写函数" and rel == SETTINGS_JS_REL:
                pat = NARROWED_WRITE_RE
            m = pat.search(text)
            assert m is None, (
                f"desktop/shell/{rel} 出现禁令「{what}」：…{text[max(0, m.start() - 40):m.end() + 40]}…"
            )
    for rel, pat, what in REQUIRE_RULES:
        text = _shell_read(rel)
        assert pat.search(text), f"desktop/shell/{rel} 没有 require {what}"


# test_transitional_s04_electron_and_ipc_scan（require('electron') 只许 main.js 与 preload.js、两条 IPC 禁令）由站主退役
# （2026-11-13）：它的说明写着“T028b 落地时由站主按名字退役”。T030 已落地，顶层多了 shell-preload.js；
# 接替它的扫描在 T030 门禁的 test_s03_static_scan 里（三个文件许 require electron，两条 IPC 禁令照旧）。


def test_s05_readme():
    """D09：README 新增「设置与校验」一节且要点齐全；T025 的既有字样全保留。"""
    text = _shell_read("README.md")
    for needle in README_T028_NEEDLES:
        assert needle in text, f"README 缺本片要点「{needle}」"
    assert re.search(r"10\s*(秒|s|S)", text), "README 缺 10 秒的时限说明（设置与校验一节）"
    for needle in README_T025_NEEDLES:
        assert needle in text, f"README 缺 T025 要点「{needle}」"
    assert re.search(r"30\s*(秒|s|S)", text), "README 缺 30 秒的时限说明"
    # T026 的要点由 test_gate_t026_baseline.py::test_s05_readme 继续钉住，这里不重复抄清单


def test_s06_preexisting_tests_kept():
    """D07：T025/T026 已有的 12 份测试文件一条没删没改名，且仍被 scripts.test 点名。"""
    pkg = json.loads(_shell_read("package.json"))
    test_cmd = pkg["scripts"]["test"]
    for rel in PREEXISTING_TEST_FILES:
        assert (SHELL / rel).is_file(), f"既有测试被删了：desktop/shell/{rel}"
        assert rel in test_cmd, f"scripts.test 不再点名既有测试 {rel}：{test_cmd!r}"


# --------------------------------------------------------------------------- 探针断言（node --test）

PROBE_SETTINGS = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const settings = require("@SHELL@/src/settings.js");

const DEFAULTS = {
  version: 1, repos: [], currentRepo: null, transcriptDirs: [],
  theme: "system", density: "standard", pythonPath: null, kitPath: null,
};

function base() {
  return fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t028-settings-")));
}
function stampOf(d) {
  const p = (n, w) => String(n).padStart(w, "0");
  return p(d.getUTCFullYear(), 4) + p(d.getUTCMonth() + 1, 2) + p(d.getUTCDate(), 2) + "T"
    + p(d.getUTCHours(), 2) + p(d.getUTCMinutes(), 2) + p(d.getUTCSeconds(), 2)
    + p(d.getUTCMilliseconds(), 3) + "Z";
}
const NOW = new Date(Date.UTC(2026, 0, 2, 3, 4, 5, 678));
const STAMP = stampOf(NOW);

test("导出：合同点名的十个名字都在", () => {
  for (const name of ["DEFAULT_SETTINGS", "SETTINGS_FILE_KEYS", "THEME_VALUES", "DENSITY_VALUES",
    "PATCH_KEYS", "createSettingsStore", "normalizeSettings", "applyPatch", "addRepo", "addTranscriptDir"]) {
    assert.ok(name in settings, "settings.js 缺导出 " + name);
  }
});

test("常量：DEFAULT_SETTINGS 冻结且值恰为合同那份；四张表逐字", () => {
  assert.ok(Object.isFrozen(settings.DEFAULT_SETTINGS), "DEFAULT_SETTINGS 必须冻结");
  assert.deepEqual(settings.DEFAULT_SETTINGS, DEFAULTS);
  assert.deepEqual(settings.SETTINGS_FILE_KEYS,
    ["version", "repos", "currentRepo", "transcriptDirs", "theme", "density", "pythonPath", "kitPath"]);
  assert.deepEqual(settings.THEME_VALUES, ["system", "light", "dark"]);
  assert.deepEqual(settings.DENSITY_VALUES, ["standard", "compact"]);
  assert.deepEqual(settings.PATCH_KEYS,
    ["theme", "density", "removeRepo", "removeTranscriptDir", "resetPython", "resetKit"]);
});

test("createSettingsStore：dir 与 filePath", () => {
  const b = base();
  const store = settings.createSettingsStore({ dir: b });
  assert.equal(store.dir, b);
  assert.equal(store.filePath, path.join(b, "settings.json"));
});

test("文件不存在：缺省设置的深拷贝、badCopy 为 null", () => {
  const b = base();
  const store = settings.createSettingsStore({ dir: b, now: () => NOW });
  const r = store.load();
  assert.deepEqual(Object.keys(r).sort(), ["badCopy", "settings"]);
  assert.equal(r.badCopy, null);
  assert.deepEqual(r.settings, DEFAULTS);
  assert.notEqual(r.settings, settings.DEFAULT_SETTINGS, "不许直接返回 DEFAULT_SETTINGS");
  assert.notEqual(r.settings.repos, settings.DEFAULT_SETTINGS.repos, "必须是深拷贝");
});

const BAD_FILES = [
  ["坏 JSON", "{not json"],
  ["顶层是数组", "[1, 2]"],
  ["顶层是字符串", "\"hello\""],
  ["顶层是数字", "123"],
  ["theme 取值非法", JSON.stringify(Object.assign({}, DEFAULTS, { theme: "neon" }))],
  ["version 不是 1", JSON.stringify(Object.assign({}, DEFAULTS, { version: 2 }))],
  ["repos 不是数组", JSON.stringify(Object.assign({}, DEFAULTS, { repos: "x" }))],
  ["repos 条目缺字段", JSON.stringify(Object.assign({}, DEFAULTS, { repos: [{ id: "r" }] }))],
  ["currentRepo 类型不对", JSON.stringify(Object.assign({}, DEFAULTS, { currentRepo: 5 }))],
  ["pythonPath 类型不对", JSON.stringify(Object.assign({}, DEFAULTS, { pythonPath: 5 }))],
];

for (const [name, text] of BAD_FILES) {
  test("坏文件（" + name + "）：用缺省设置、另存带 UTC 时刻的副本、副本是原始字节", () => {
    const b = base();
    const raw = Buffer.from(text, "utf8");
    fs.writeFileSync(path.join(b, "settings.json"), raw);
    const store = settings.createSettingsStore({ dir: b, now: () => NOW });
    const r = store.load();
    assert.deepEqual(r.settings, DEFAULTS, name);
    assert.equal(r.badCopy, path.join(b, "settings.bad-" + STAMP + ".json"), name);
    assert.ok(fs.existsSync(r.badCopy), name);
    assert.deepEqual(fs.readFileSync(r.badCopy), raw, name + "：副本内容必须是坏文件的原始字节");
  });
}

test("坏文件副本名带 UTC 时刻（缺省 now）：格式 YYYYMMDDTHHMMSSmmmZ", () => {
  const b = base();
  fs.writeFileSync(path.join(b, "settings.json"), "oops");
  const r = settings.createSettingsStore({ dir: b }).load();
  assert.ok(/settings\.bad-\d{8}T\d{9}Z\.json$/.test(path.basename(r.badCopy)), r.badCopy);
});

test("副本不覆盖已有同名文件：依次试 -2、-3", () => {
  const b = base();
  const raw = Buffer.from("{bad", "utf8");
  fs.writeFileSync(path.join(b, "settings.json"), raw);
  const first = path.join(b, "settings.bad-" + STAMP + ".json");
  fs.writeFileSync(first, "PRE-EXISTING");
  const store = settings.createSettingsStore({ dir: b, now: () => NOW });
  const r1 = store.load();
  assert.equal(r1.badCopy, path.join(b, "settings.bad-" + STAMP + "-2.json"), "已存在同名副本时要用 -2");
  assert.deepEqual(fs.readFileSync(r1.badCopy), raw, "-2 副本的内容是坏文件的原始字节");
  assert.equal(fs.readFileSync(first, "utf8"), "PRE-EXISTING", "已存在的副本一个字节都不许动");
  const r2 = store.load();
  assert.equal(r2.badCopy, path.join(b, "settings.bad-" + STAMP + "-3.json"), "再撞就试 -3");
});

test("未知键：读出来没有它（不产副本）、写盘后消失", () => {
  const b = base();
  const withUnknown = Object.assign({}, DEFAULTS, { theme: "dark", density: "compact", futureKey: { a: 1 }, another: "x" });
  fs.writeFileSync(path.join(b, "settings.json"), JSON.stringify(withUnknown, null, 2) + "\n");
  const store = settings.createSettingsStore({ dir: b, now: () => NOW });
  const r = store.load();
  assert.equal(r.badCopy, null, "未知键不算坏文件");
  assert.deepEqual(r.settings, Object.assign({}, DEFAULTS, { theme: "dark", density: "compact" }));
  store.save(r.settings);
  const written = JSON.parse(fs.readFileSync(path.join(b, "settings.json"), "utf8"));
  assert.deepEqual(Object.keys(written), settings.SETTINGS_FILE_KEYS);
  assert.equal("futureKey" in written, false);
  assert.equal("another" in written, false);
});

test("save：内容是 JSON.stringify(obj, null, 2)+换行、键按 SETTINGS_FILE_KEYS 顺序、只保留这些键", () => {
  const b = base();
  const store = settings.createSettingsStore({ dir: b });
  const s = Object.assign({}, DEFAULTS, { theme: "light" }, { junk: "should-not-write" });
  store.save(s);
  const expected = {};
  for (const k of settings.SETTINGS_FILE_KEYS) expected[k] = s[k];
  const text = fs.readFileSync(path.join(b, "settings.json"), "utf8");
  assert.equal(text, JSON.stringify(expected, null, 2) + "\n");
});

test("save：目录不存在也能写（mkdirSync recursive），成功后没有 .tmp 残留", () => {
  const b = base();
  const dir = path.join(b, "nested", "userData");
  const store = settings.createSettingsStore({ dir });
  store.save(Object.assign({}, DEFAULTS));
  assert.ok(fs.existsSync(path.join(dir, "settings.json")));
  assert.equal(fs.existsSync(path.join(dir, "settings.json.tmp")), false, "rename 之后不许留下临时文件");
});

test("写临时文件失败：抛错、原文件不动；临时路径就是 settings.json.tmp", () => {
  const b = base();
  const store = settings.createSettingsStore({ dir: b });
  store.save(Object.assign({}, DEFAULTS, { theme: "dark" }));
  const before = fs.readFileSync(path.join(b, "settings.json"));
  fs.mkdirSync(path.join(b, "settings.json.tmp"));
  assert.throws(() => store.save(Object.assign({}, DEFAULTS, { theme: "light" })));
  assert.deepEqual(fs.readFileSync(path.join(b, "settings.json")), before, "写失败不许动原文件");
  assert.ok(fs.statSync(path.join(b, "settings.json.tmp")).isDirectory(), "tmp 在（对目录的删除失败被忽略，但仍要抛错）");
});

test("rename 失败：抛错、临时文件被清掉", () => {
  const b = base();
  fs.mkdirSync(path.join(b, "settings.json")); // 正式文件是目录 → rename 到它必失败
  const store = settings.createSettingsStore({ dir: b });
  assert.throws(() => store.save(Object.assign({}, DEFAULTS)));
  assert.equal(fs.existsSync(path.join(b, "settings.json.tmp")), false, "写失败的临时文件要被删掉");
  assert.ok(fs.statSync(path.join(b, "settings.json")).isDirectory());
});
'''


PROBE_PATCH = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const settings = require("@SHELL@/src/settings.js");

function clone(x) { return JSON.parse(JSON.stringify(x)); }
function withRepos() {
  const s = clone(settings.DEFAULT_SETTINGS);
  s.repos = [
    { id: "r1", name: "alpha", path: "C:/nowhere/alpha", lastOpened: null },
    { id: "r2", name: "beta", path: "C:/nowhere/beta", lastOpened: "2026-01-01T00:00:00.000Z" },
  ];
  s.transcriptDirs = [{ id: "d1", path: "C:/nowhere/d1" }];
  s.pythonPath = "C:/py/python.exe";
  s.kitPath = "C:/kit";
  s.currentRepo = "r1";
  return s;
}

test("normalizeSettings：合法整包 ok、未知键被丢掉、已知键非法 ok:false", () => {
  assert.equal(settings.normalizeSettings(withRepos()).ok, true);
  const withExtra = Object.assign(withRepos(), { future: 1 });
  const nr = settings.normalizeSettings(withExtra);
  assert.equal(nr.ok, true);
  assert.equal("future" in nr.settings, false);
  for (const pair of [["theme", "neon"], ["version", 2], ["currentRepo", 5], ["kitPath", 7], ["density", "cozy"]]) {
    const bad = Object.assign(withRepos(), { [pair[0]]: pair[1] });
    assert.equal(settings.normalizeSettings(bad).ok, false, pair[0] + "=" + JSON.stringify(pair[1]));
  }
});

const REJECTS = [
  ["null", null, "bad-patch"],
  ["数组", [1], "bad-patch"],
  ["字符串", "theme=dark", "bad-patch"],
  ["数字", 42, "bad-patch"],
  ["布尔", true, "bad-patch"],
  ["未知键", { foo: "x" }, "bad-patch"],
  ["theme 非法", { theme: "neon" }, "bad-patch"],
  ["theme 非字符串", { theme: 3 }, "bad-patch"],
  ["theme null", { theme: null }, "bad-patch"],
  ["density 非法", { density: "cozy" }, "bad-patch"],
  ["resetPython 不严格 true（字符串）", { resetPython: "true" }, "bad-patch"],
  ["resetPython false", { resetPython: false }, "bad-patch"],
  ["resetKit 不严格 true（数字）", { resetKit: 1 }, "bad-patch"],
  ["removeRepo 非字符串", { removeRepo: 12 }, "bad-patch"],
  ["removeTranscriptDir 非字符串", { removeTranscriptDir: {} }, "bad-patch"],
  ["removeRepo 指向不存在的 id", { removeRepo: "ghost" }, "unknown-id"],
  ["removeTranscriptDir 指向不存在的 id", { removeTranscriptDir: "ghost" }, "unknown-id"],
  ["removeRepo 指向当前仓库", { removeRepo: "r1" }, "current-repo"],
  ["路径值当 removeRepo（没有这个 id）", { removeRepo: "C:/nowhere/alpha" }, "unknown-id"],
];

for (const [name, patch, reason] of REJECTS) {
  test("applyPatch 拒绝：" + name + " → " + reason, () => {
    const r = settings.applyPatch(withRepos(), patch);
    assert.equal(r.ok, false, name);
    assert.equal(r.reason, reason, name + "：" + JSON.stringify(r));
  });
}

test("applyPatch 校验顺序：bad-patch → unknown-id → current-repo", () => {
  const s = withRepos();
  assert.equal(settings.applyPatch(s, { removeRepo: "ghost", theme: "neon" }).reason, "bad-patch", "形状在 id 之前");
  assert.equal(settings.applyPatch(s, { removeRepo: "r1", density: "cozy" }).reason, "bad-patch", "形状在当前仓库之前");
  assert.equal(settings.applyPatch(s, { removeTranscriptDir: "ghost", removeRepo: "r1" }).reason, "unknown-id", "id 在当前仓库之前");
});

test("applyPatch：拒绝与成功都不改入参；成功返回新对象", () => {
  const s = withRepos();
  const snap = clone(s);
  for (const patch of [{ foo: 1 }, { removeRepo: "r1" }, { removeRepo: "ghost" }]) {
    const r = settings.applyPatch(s, patch);
    assert.equal(r.ok, false);
    assert.deepEqual(s, snap, "入参被改了：" + JSON.stringify(patch));
  }
  const ok = settings.applyPatch(s, {
    theme: "dark", density: "compact", removeRepo: "r2", removeTranscriptDir: "d1", resetPython: true, resetKit: true,
  });
  assert.equal(ok.ok, true, JSON.stringify(ok));
  assert.notEqual(ok.settings, s);
  assert.deepEqual(s, snap, "成功的应用也不许改入参");
  assert.equal(ok.settings.theme, "dark");
  assert.equal(ok.settings.density, "compact");
  assert.deepEqual(ok.settings.repos.map((x) => x.id), ["r1"]);
  assert.deepEqual(ok.settings.transcriptDirs, []);
  assert.equal(ok.settings.pythonPath, null);
  assert.equal(ok.settings.kitPath, null);
  assert.equal(ok.settings.currentRepo, "r1");
});

test("applyPatch：removeRepo 移除非当前仓库合法", () => {
  const r = settings.applyPatch(withRepos(), { removeRepo: "r2" });
  assert.equal(r.ok, true);
  assert.deepEqual(r.settings.repos.map((x) => x.id), ["r1"]);
});

test("applyPatch：空补丁 {} 合格，设置原样（新对象）", () => {
  const s = withRepos();
  const r = settings.applyPatch(s, {});
  assert.equal(r.ok, true);
  assert.deepEqual(r.settings, s);
  assert.notEqual(r.settings, s);
});

function dirs() {
  return fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t028-add-")));
}

test("addRepo：新条目 id 取目录名、lastOpened null、currentRepo 为空时设当前", () => {
  const b = dirs();
  const repo = path.join(b, "alpha");
  fs.mkdirSync(repo);
  const s = clone(settings.DEFAULT_SETTINGS);
  const r = settings.addRepo(s, repo);
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.id, "alpha");
  assert.equal(r.reused, false);
  assert.deepEqual(r.settings.repos, [{ id: "alpha", name: "alpha", path: repo, lastOpened: null }]);
  assert.equal(r.settings.currentRepo, "alpha", "currentRepo 为空时新仓库成为当前仓库");
  assert.deepEqual(s, clone(settings.DEFAULT_SETTINGS), "入参不许被改");
});

test("addRepo：相同路径 reused 沿用原 id、条目不增；Windows 下不分大小写", () => {
  const b = dirs();
  const repo = path.join(b, "alpha");
  fs.mkdirSync(repo);
  let s = clone(settings.DEFAULT_SETTINGS);
  s = settings.addRepo(s, repo).settings;
  const variant = process.platform === "win32" ? repo.split(path.sep).join("/") : repo;
  const r2 = settings.addRepo(s, variant);
  assert.equal(r2.reused, true, JSON.stringify(r2));
  assert.equal(r2.id, "alpha");
  assert.equal(r2.settings.repos.length, 1);
  if (process.platform === "win32") {
    const r3 = settings.addRepo(s, repo.toUpperCase());
    assert.equal(r3.reused, true, "Windows 下路径比较要转小写");
    assert.equal(r3.settings.repos.length, 1);
  }
});

test("addRepo：id 撞了依次 -2、-3", () => {
  const b = dirs();
  const a1 = path.join(b, "one", "alpha");
  const a2 = path.join(b, "two", "alpha");
  const a3 = path.join(b, "three", "alpha");
  fs.mkdirSync(a1, { recursive: true });
  fs.mkdirSync(a2, { recursive: true });
  fs.mkdirSync(a3, { recursive: true });
  let s = clone(settings.DEFAULT_SETTINGS);
  s = settings.addRepo(s, a1).settings;
  const r2 = settings.addRepo(s, a2);
  assert.equal(r2.id, "alpha-2");
  const r3 = settings.addRepo(r2.settings, a3);
  assert.equal(r3.id, "alpha-3");
  assert.equal(r3.settings.repos.length, 3);
});

test("addRepo：currentRepo 已有时不换", () => {
  const b = dirs();
  const a = path.join(b, "alpha");
  const beta = path.join(b, "beta");
  fs.mkdirSync(a);
  fs.mkdirSync(beta);
  let s = clone(settings.DEFAULT_SETTINGS);
  s = settings.addRepo(s, a).settings;
  const r2 = settings.addRepo(s, beta);
  assert.equal(r2.id, "beta");
  assert.equal(r2.settings.currentRepo, "alpha", "已有当前仓库时不许换");
});

test("addRepo：basename 为空（根目录）时 name 用 \"repo\"", () => {
  const root = path.parse(process.cwd()).root;
  const r = settings.addRepo(clone(settings.DEFAULT_SETTINGS), root);
  assert.equal(r.ok, true);
  assert.equal(r.id, "repo");
});

test("addTranscriptDir：id 基名 dir、撞了 -2、同路径 reused", () => {
  const b = dirs();
  const d1 = path.join(b, "logs1");
  const d2 = path.join(b, "logs2");
  fs.mkdirSync(d1);
  fs.mkdirSync(d2);
  let s = clone(settings.DEFAULT_SETTINGS);
  const r1 = settings.addTranscriptDir(s, d1);
  assert.equal(r1.ok, true, JSON.stringify(r1));
  assert.equal(r1.id, "dir");
  assert.equal(r1.reused, false);
  assert.deepEqual(r1.settings.transcriptDirs, [{ id: "dir", path: d1 }]);
  const r2 = settings.addTranscriptDir(r1.settings, d2);
  assert.equal(r2.id, "dir-2");
  const r3 = settings.addTranscriptDir(r2.settings, d1);
  assert.equal(r3.reused, true);
  assert.equal(r3.id, "dir");
  assert.equal(r3.settings.transcriptDirs.length, 2);
});
'''


PROBE_DETECT = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const cp = require("node:child_process");

// 在 require detect.js 之前换掉 child_process.spawn：记录每次调用的形状（shell/windowsHide/stdio），
// 并允许测试给指定命令改道到假脚本（观察自动检测的候选顺序）。passthrough 仍然真起进程。
const realSpawn = cp.spawn;
let spawnPlan = null;
const spawnCalls = [];
cp.spawn = function gateSpawn(command, args, options) {
  spawnCalls.push({ command, args: Array.isArray(args) ? args.slice() : args, options });
  if (spawnPlan) {
    const alt = spawnPlan(command, args);
    if (alt) return realSpawn.call(cp, alt[0], alt[1], options);
  }
  return realSpawn.apply(cp, arguments);
};
// spawnPlan 返回 [command, argsArray]（第二个元素必须是数组，spawn 的第二参是 argv）

const detect = require("@SHELL@/src/detect.js");

const B = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t028-detect-")));

function fixture(name, source) {
  const p = path.join(B, name);
  fs.writeFileSync(p, source);
  return p;
}
const F = {
  infoOk: fixture("fake-py-ok.js", 'process.stdout.write("3.12.9\\n/fake/python-exe\\n");\n'),
  infoOneLine: fixture("fake-py-oneline.js", 'process.stdout.write("3.12.9\\n");\n'),
  infoEmpty: fixture("fake-py-empty.js", ""),
  exit1: fixture("fake-exit1.js", "process.exit(1);\n"),
  hang: fixture("fake-hang.js", "setInterval(() => {}, 1000);\n"),
  echo: fixture("fake-echo-argv.js",
    'process.stdout.write(JSON.stringify(process.argv.slice(2)) + "\\n"); process.stderr.write("err-line\\n");\n'),
};
function makeKit(name, script) {
  const kit = path.join(B, name);
  fs.mkdirSync(path.join(kit, "scripts"), { recursive: true });
  fs.writeFileSync(path.join(kit, "scripts", "pi_dispatch.py"), script);
  return kit;
}
function base() {
  return fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t028-checkrepo-")));
}

test("导出：合同点名的八个名字都在", () => {
  for (const name of ["PYTHON_INFO_CODE", "KIT_VERSION_RE", "runProcess", "checkRepo",
    "probePython", "probeKit", "detectPython", "detectKit"]) {
    assert.ok(name in detect, "detect.js 缺导出 " + name);
  }
});

test("常量：PYTHON_INFO_CODE 逐字；KIT_VERSION_RE 取 x.y.z", () => {
  assert.equal(detect.PYTHON_INFO_CODE,
    "import sys; print(sys.version.split()[0]); print(sys.executable); sys.exit(0 if sys.version_info >= (3, 10) else 1)");
  assert.equal(detect.KIT_VERSION_RE.exec("pi_dispatch 2.12.0")[0], "2.12.0");
  assert.equal(detect.KIT_VERSION_RE.test("no digits here"), false);
});

test("runProcess：正常结束带回 code/stdout/stderr/timedOut，参数原样到达（不经 shell）", async () => {
  spawnCalls.length = 0;
  spawnPlan = null;
  const args = ["带空格 & echo hacked", "C:/path with space/x.js", "<>|"];
  const r = await detect.runProcess(process.execPath, [F.echo].concat(args), { timeoutMs: 15000 });
  assert.equal(r.code, 0, JSON.stringify(r));
  assert.equal(r.timedOut, false);
  assert.deepEqual(JSON.parse(r.stdout), args, "参数必须原样到达——经 shell 会被解释");
  assert.equal(r.stderr, "err-line\n");
  assert.equal(spawnCalls.length, 1);
  const opts = spawnCalls[0].options || {};
  assert.equal(opts.shell, false, "spawn 必须 shell:false");
  assert.equal(opts.windowsHide, true, "spawn 必须 windowsHide:true");
  assert.deepEqual(opts.stdio, ["ignore", "pipe", "pipe"]);
});

test("runProcess：超时杀进程、回 timedOut:true 与 code:null", async () => {
  spawnPlan = null;
  const t0 = Date.now();
  const r = await detect.runProcess(process.execPath, [F.hang], { timeoutMs: 400 });
  assert.equal(r.timedOut, true);
  assert.equal(r.code, null);
  assert.ok(Date.now() - t0 < 8000, "超时要按时限返回，不许挂住");
});

test("runProcess：进程起不来回 error 错误码（ENOENT）", async () => {
  spawnPlan = null;
  const r = await detect.runProcess("t028-no-such-cmd-xyz", [], { timeoutMs: 8000 });
  assert.equal(r.code, null);
  assert.equal(r.timedOut, false);
  assert.equal(r.stdout, "");
  assert.equal(r.stderr, "");
  assert.equal(r.error, "ENOENT");
});

test("checkRepo：.git 目录 + .agent 目录 → ok", () => {
  const b = base();
  const d = path.join(b, "r1");
  fs.mkdirSync(path.join(d, ".git"), { recursive: true });
  fs.mkdirSync(path.join(d, ".agent"), { recursive: true });
  assert.equal(detect.checkRepo(d), "ok");
});

test("checkRepo：.git 是文件（worktree）也算 → ok", () => {
  const b = base();
  const d = path.join(b, "r2");
  fs.mkdirSync(d);
  fs.writeFileSync(path.join(d, ".git"), "gitdir: ../elsewhere\n");
  fs.mkdirSync(path.join(d, ".agent"));
  assert.equal(detect.checkRepo(d), "ok");
});

test("checkRepo：缺 .git → not-git；路径不存在 → not-git", () => {
  const b = base();
  const d = path.join(b, "r3");
  fs.mkdirSync(path.join(d, ".agent"), { recursive: true });
  assert.equal(detect.checkRepo(d), "not-git");
  assert.equal(detect.checkRepo(path.join(b, "no-such-dir")), "not-git");
});

test("checkRepo：.agent 缺失或是文件 → no-agent", () => {
  const b = base();
  const d1 = path.join(b, "r4");
  fs.mkdirSync(path.join(d1, ".git"), { recursive: true });
  assert.equal(detect.checkRepo(d1), "no-agent");
  const d2 = path.join(b, "r5");
  fs.mkdirSync(d2);
  fs.writeFileSync(path.join(d2, ".git"), "gitdir: x\n");
  fs.writeFileSync(path.join(d2, ".agent"), "not a dir");
  assert.equal(detect.checkRepo(d2), "no-agent");
});

test("probePython：退出码 0 且至少两行 → ok（version 第一行、path 第二行）", async () => {
  spawnPlan = null;
  const r = await detect.probePython([process.execPath, F.infoOk], { timeoutMs: 15000 });
  assert.deepEqual(r, { ok: true, version: "3.12.9", path: "/fake/python-exe" });
});

test("probePython：退出码 0 但行数不够 → bad-output", async () => {
  spawnPlan = null;
  const one = await detect.probePython([process.execPath, F.infoOneLine], { timeoutMs: 15000 });
  assert.deepEqual(one, { ok: false, reason: "bad-output" });
  const empty = await detect.probePython([process.execPath, F.infoEmpty], { timeoutMs: 15000 });
  assert.deepEqual(empty, { ok: false, reason: "bad-output" });
});

test("probePython：退出码非 0 → version-too-old；超时 → timeout；起不来 → no-command", async () => {
  spawnPlan = null;
  const old = await detect.probePython([process.execPath, F.exit1], { timeoutMs: 15000 });
  assert.deepEqual(old, { ok: false, reason: "version-too-old" });
  const timedOut = await detect.probePython([process.execPath, F.hang], { timeoutMs: 400 });
  assert.deepEqual(timedOut, { ok: false, reason: "timeout" });
  const nc = await detect.probePython(["t028-no-such-cmd-xyz"], { timeoutMs: 8000 });
  assert.deepEqual(nc, { ok: false, reason: "no-command" });
});

test("probeKit：stdout 取版本 → ok", async () => {
  spawnPlan = null;
  const kit = makeKit("kit-ok", 'process.stdout.write("pi_dispatch 2.12.0\\n");\n');
  const r = await detect.probeKit(process.execPath, kit, { timeoutMs: 15000 });
  assert.deepEqual(r, { ok: true, version: "2.12.0" });
});

test("probeKit：版本只在 stderr 也认", async () => {
  spawnPlan = null;
  const kit = makeKit("kit-err", 'process.stderr.write("v=9.9.9\\n");\n');
  const r = await detect.probeKit(process.execPath, kit, { timeoutMs: 15000 });
  assert.deepEqual(r, { ok: true, version: "9.9.9" });
});

test("probeKit：退出码 0 但没有版本号 → kit-unusable", async () => {
  spawnPlan = null;
  const kit = makeKit("kit-noversion", 'process.stdout.write("no version here\\n");\n');
  const r = await detect.probeKit(process.execPath, kit, { timeoutMs: 15000 });
  assert.deepEqual(r, { ok: false, reason: "kit-unusable" });
});

test("probeKit：退出码非 0 → kit-unusable；超时 → timeout", async () => {
  spawnPlan = null;
  const kitFail = makeKit("kit-fail", "process.exit(3);\n");
  const kitHang = makeKit("kit-hang", "setInterval(() => {}, 1000);\n");
  assert.deepEqual(await detect.probeKit(process.execPath, kitFail, { timeoutMs: 15000 }), { ok: false, reason: "kit-unusable" });
  assert.deepEqual(await detect.probeKit(process.execPath, kitHang, { timeoutMs: 400 }), { ok: false, reason: "timeout" });
});

test("probeKit：没有 pythonPath → python-unusable，不起子进程", async () => {
  spawnCalls.length = 0;
  spawnPlan = null;
  const r = await detect.probeKit(null, path.join(B, "kit-ok"), { timeoutMs: 15000 });
  assert.deepEqual(r, { ok: false, reason: "python-unusable" });
  assert.equal(spawnCalls.length, 0);
});

test("detectPython：按 python3 → python → py -3 的顺序，第一个成功即停", async () => {
  spawnCalls.length = 0;
  spawnPlan = (command, args) => {
    assert.equal(args[0], "-c", "探测代码必须以 -c 传给解释器");
    assert.equal(args[1], detect.PYTHON_INFO_CODE, "缺省探测代码就是 PYTHON_INFO_CODE");
    if (command === "python3") return [process.execPath, [F.exit1]];
    if (command === "python") return [process.execPath, [F.infoOk]];
    if (command === "py") return [process.execPath, [F.infoOk]];
    return null;
  };
  const r = await detect.detectPython({ timeoutMs: 15000 });
  assert.deepEqual(r, { status: "ok", source: "auto", path: "/fake/python-exe", version: "3.12.9" });
  assert.deepEqual(spawnCalls.map((c) => c.command), ["python3", "python"]);
});

test("detectPython：全失败 → missing、path/version 为空，三个候选都试过", async () => {
  spawnCalls.length = 0;
  spawnPlan = () => [process.execPath, [F.exit1]];
  const r = await detect.detectPython({ timeoutMs: 15000 });
  assert.deepEqual(r, { status: "missing", source: "auto", path: "", version: "" });
  assert.deepEqual(spawnCalls.map((c) => c.command), ["python3", "python", "py"]);
});

test("detectKit：kitPath 优先（external），path 是被验证的 pi_dispatch.py 绝对路径", async () => {
  spawnPlan = null;
  const ext = makeKit("kit-ext", 'process.stdout.write("pi_dispatch 2.12.0\\n");\n');
  const repo = makeKit("kit-repo", 'process.stdout.write("pi_dispatch 1.2.3\\n");\n');
  const r = await detect.detectKit({ pythonPath: process.execPath, kitPath: ext, repoPath: repo, timeoutMs: 15000 });
  assert.equal(r.status, "ok", JSON.stringify(r));
  assert.equal(r.source, "external");
  assert.equal(r.version, "2.12.0");
  assert.equal(path.resolve(r.path), path.resolve(path.join(ext, "scripts", "pi_dispatch.py")));
});

test("detectKit：没有 kitPath 时按 repo 探测（source repo）", async () => {
  spawnPlan = null;
  const repo = makeKit("kit-repo2", 'process.stdout.write("pi_dispatch 1.2.3\\n");\n');
  const r = await detect.detectKit({ pythonPath: process.execPath, repoPath: repo, timeoutMs: 15000 });
  assert.equal(r.status, "ok", JSON.stringify(r));
  assert.equal(r.source, "repo");
  assert.equal(r.version, "1.2.3");
  assert.equal(path.resolve(r.path), path.resolve(path.join(repo, "scripts", "pi_dispatch.py")));
});

test("detectKit：探测失败 → missing、path/version 为空", async () => {
  spawnPlan = null;
  const empty = path.join(B, "kit-empty");
  fs.mkdirSync(empty);
  const r = await detect.detectKit({ pythonPath: process.execPath, repoPath: empty, timeoutMs: 15000 });
  assert.deepEqual(r, { status: "missing", source: "repo", path: "", version: "" });
});

test("detectKit：kitPath 与 repoPath 都没有 → missing，不起子进程", async () => {
  spawnCalls.length = 0;
  spawnPlan = null;
  const r = await detect.detectKit({ pythonPath: process.execPath, timeoutMs: 15000 });
  assert.equal(r.status, "missing");
  assert.equal(spawnCalls.length, 0);
});
'''


PROBE_API = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { createSettingsStore, DEFAULT_SETTINGS } = require("@SHELL@/src/settings.js");
const { createShellApi } = require("@SHELL@/src/shellapi.js");

const HOMEPAGE = "https://github.com/mrQzs/ThemisTally";

function makeHarness(over) {
  const opts = Object.assign({}, over || {});
  const failingSave = opts.failingSave;
  delete opts.failingSave;
  const b = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t028-api-")));
  const userData = path.join(b, "userData");
  fs.mkdirSync(userData);
  let store = createSettingsStore({ dir: userData });
  if (failingSave) {
    store = {
      dir: store.dir,
      filePath: store.filePath,
      load: store.load.bind(store),
      save: () => { throw new Error("disk full"); },
    };
  }
  const chooser = { dir: null, file: null, dirCalls: 0, fileCalls: 0 };
  const confirm = { answer: true, throwIt: false, calls: [] };
  const opener = { throwIt: false, calls: [] };
  const probeState = {
    probePythonResult: { ok: true, version: "3.12.9", path: "/fake/python-exe" },
    probeKitResult: { ok: true, version: "2.12.0" },
    detectPythonResult: { status: "ok", source: "auto", path: "/auto/py", version: "3.13.1" },
    probePythonCalls: [], probeKitCalls: [], detectPythonCalls: [], detectKitCalls: [],
  };
  const probe = {
    async probePython(commandArgs, options) {
      probeState.probePythonCalls.push([commandArgs, options]);
      return JSON.parse(JSON.stringify(probeState.probePythonResult));
    },
    async probeKit(pythonPath, kitDir, options) {
      probeState.probeKitCalls.push([pythonPath, kitDir, options]);
      return JSON.parse(JSON.stringify(probeState.probeKitResult));
    },
    async detectPython(options) {
      probeState.detectPythonCalls.push([options]);
      return JSON.parse(JSON.stringify(probeState.detectPythonResult));
    },
    async detectKit(options) {
      probeState.detectKitCalls.push([options]);
      const kitDir = (options && (options.kitPath || options.repoPath)) || null;
      if (!kitDir) return { status: "missing", source: "repo", path: "", version: "" };
      return {
        status: "ok",
        source: options.kitPath ? "external" : "repo",
        path: path.join(kitDir, "scripts", "pi_dispatch.py"),
        version: "2.12.0",
      };
    },
  };
  const api = createShellApi(Object.assign({
    store,
    chooseDirectory: async () => { chooser.dirCalls += 1; return chooser.dir; },
    chooseFile: async () => { chooser.fileCalls += 1; return chooser.file; },
    confirmExternal: async (u) => { confirm.calls.push(u); if (confirm.throwIt) throw new Error("确认框坏了"); return confirm.answer; },
    openExternal: async (u) => { opener.calls.push(u); if (opener.throwIt) throw new Error("打不开"); },
    appVersion: "9.9.9",
    probe,
  }, opts));
  function gitRepo(name) {
    const d = path.join(b, name);
    fs.mkdirSync(path.join(d, ".git"), { recursive: true });
    fs.mkdirSync(path.join(d, ".agent"), { recursive: true });
    return d;
  }
  function plainDir(name) {
    const d = path.join(b, name);
    fs.mkdirSync(d, { recursive: true });
    return d;
  }
  function bytes() {
    return fs.existsSync(store.filePath) ? fs.readFileSync(store.filePath) : null;
  }
  function writeSettings(mutate) {
    const s = JSON.parse(JSON.stringify(DEFAULT_SETTINGS));
    mutate(s);
    store.save(s);
  }
  return { b, api, store, chooser, confirm, opener, probeState, gitRepo, plainDir, bytes, writeSettings };
}

test("getState：信封 {ok:true,value}；缺省设置只含五个字段；app 与 service", async () => {
  const h = makeHarness();
  const r = await h.api.getState();
  assert.deepEqual(Object.keys(r).sort(), ["ok", "value"]);
  assert.equal(r.ok, true);
  const st = r.value;
  assert.deepEqual(st.app, { version: "9.9.9", homepage: HOMEPAGE });
  assert.deepEqual(Object.keys(st.settings).sort(), ["currentRepo", "density", "repos", "theme", "transcriptDirs"]);
  assert.deepEqual(st.settings, { repos: [], currentRepo: null, transcriptDirs: [], theme: "system", density: "standard" });
  assert.equal(st.currentRepoCheck, null);
  assert.deepEqual(st.service, { kind: "idle" });
});

test("getState：appVersion 与 homepage 的缺省值", async () => {
  const h = makeHarness({ appVersion: undefined, homepage: undefined });
  const st = (await h.api.getState()).value;
  assert.deepEqual(st.app, { version: "", homepage: HOMEPAGE });
});

test("getState：pythonPath 非空 → probePython([该路径])、source custom；kit 走 external", async () => {
  const h = makeHarness();
  const kitDir = h.plainDir("mykit");
  h.writeSettings((s) => { s.pythonPath = process.execPath; s.kitPath = kitDir; });
  const st = (await h.api.getState()).value;
  assert.deepEqual(h.probeState.probePythonCalls.map((c) => c[0]), [[process.execPath]]);
  assert.deepEqual(st.python, { status: "ok", source: "custom", path: "/fake/python-exe", version: "3.12.9" });
  assert.equal(st.kit.status, "ok");
  assert.equal(st.kit.source, "external");
  assert.equal(st.kit.version, "2.12.0");
  assert.equal(path.resolve(st.kit.path), path.resolve(path.join(kitDir, "scripts", "pi_dispatch.py")));
  const targets = h.probeState.probeKitCalls.map((c) => c[1])
    .concat(h.probeState.detectKitCalls.map((c) => (c[0] && (c[0].kitPath || c[0].repoPath)) || null));
  assert.ok(targets.length >= 1, "kit 探测必须真的发生");
  for (const t of targets) assert.equal(t, kitDir, "kit 探测的目标必须是设置里的 kitPath");
  if (h.probeState.probeKitCalls.length > 0) {
    assert.equal(h.probeState.probeKitCalls[0][0], "/fake/python-exe", "probeKit 要用 python.path（探测到的解释器）");
  }
});

test("getState：pythonPath 为空 → detectPython 直通（source auto）", async () => {
  const h = makeHarness();
  const st = (await h.api.getState()).value;
  assert.equal(h.probeState.detectPythonCalls.length, 1);
  assert.equal(h.probeState.probePythonCalls.length, 0);
  assert.deepEqual(st.python, { status: "ok", source: "auto", path: "/auto/py", version: "3.13.1" });
  assert.equal(st.kit.status, "missing", "既没有 kitPath 也没有当前仓库时 kit 必须是 missing");
});

test("getState：自定义 Python 失败 → missing(custom)；kit external 没有可用 Python → missing", async () => {
  const h = makeHarness();
  h.writeSettings((s) => { s.pythonPath = process.execPath; s.kitPath = h.plainDir("k"); });
  h.probeState.probePythonResult = { ok: false, reason: "version-too-old" };
  h.probeState.detectPythonResult = { status: "missing", source: "auto", path: "", version: "" };
  const st = (await h.api.getState()).value;
  assert.deepEqual(st.python, { status: "missing", source: "custom", path: "", version: "" });
  assert.equal(st.kit.status, "missing");
  assert.equal(st.kit.source, "external");
});

test("getState：currentRepoCheck 按 checkRepo 判（ok / not-git / no-agent）", async () => {
  const mk = async (make) => {
    const h = makeHarness();
    const repo = make(h);
    h.writeSettings((s) => {
      s.repos = [{ id: "r", name: "r", path: repo, lastOpened: null }];
      s.currentRepo = "r";
    });
    return (await h.api.getState()).value.currentRepoCheck;
  };
  assert.equal(await mk((h) => h.gitRepo("good")), "ok");
  assert.equal(await mk((h) => h.plainDir("plain")), "not-git");
  assert.equal(await mk((h) => {
    const d = path.join(h.b, "noagent");
    fs.mkdirSync(path.join(d, ".git"), { recursive: true });
    return d;
  }), "no-agent");
});

test("getState：currentRepo 指向不存在的 id → currentRepoCheck 为 null", async () => {
  const h = makeHarness();
  h.writeSettings((s) => { s.repos = []; s.currentRepo = "ghost"; });
  assert.equal((await h.api.getState()).value.currentRepoCheck, null);
});

test("pickRepo：取消 → cancelled，不写盘", async () => {
  const h = makeHarness();
  h.chooser.dir = null;
  const r = await h.api.pickRepo();
  assert.deepEqual(r, { ok: true, value: { kind: "cancelled" } });
  assert.equal(h.bytes(), null);
});

test("pickRepo：不是 Git 仓库 → rejected(not-git)，不写盘", async () => {
  const h = makeHarness();
  const d = h.plainDir("plain");
  h.chooser.dir = d;
  const r = await h.api.pickRepo();
  assert.deepEqual(r, { ok: true, value: { kind: "rejected", problem: "not-git", path: d } });
  assert.equal(h.bytes(), null);
});

test("pickRepo：没有 .agent 目录 → rejected(no-agent)，不写盘", async () => {
  const h = makeHarness();
  const d = path.join(h.b, "noagent");
  fs.mkdirSync(path.join(d, ".git"), { recursive: true });
  h.chooser.dir = d;
  const r = await h.api.pickRepo();
  assert.deepEqual(r, { ok: true, value: { kind: "rejected", problem: "no-agent", path: d } });
  assert.equal(h.bytes(), null);
});

test("pickRepo：合法仓库 → saved（id 与 state）、写盘、currentRepo 为空时设当前", async () => {
  const h = makeHarness();
  const d = h.gitRepo("alpha");
  h.chooser.dir = d;
  const r = await h.api.pickRepo();
  assert.equal(r.ok, true, JSON.stringify(r));
  const v = r.value;
  assert.equal(v.kind, "saved");
  assert.equal(v.path, d);
  assert.equal(v.id, "alpha");
  assert.deepEqual(v.state.settings.repos, [{ id: "alpha", name: "alpha", path: d, lastOpened: null }]);
  assert.equal(v.state.settings.currentRepo, "alpha");
  const onDisk = JSON.parse(fs.readFileSync(h.store.filePath, "utf8"));
  assert.equal(onDisk.currentRepo, "alpha");
  assert.deepEqual(onDisk.repos.map((x) => x.id), ["alpha"]);
});

test("pickRepo：currentRepo 已有时不换；同一路径沿用原 id、条目不增", async () => {
  const h = makeHarness();
  const a = h.gitRepo("alpha");
  const beta = h.gitRepo("beta");
  h.chooser.dir = a;
  await h.api.pickRepo();
  h.chooser.dir = beta;
  const r2 = await h.api.pickRepo();
  assert.equal(r2.value.id, "beta");
  assert.equal(r2.value.state.settings.currentRepo, "alpha", "已有当前仓库时不许换");
  h.chooser.dir = a;
  const r3 = await h.api.pickRepo();
  assert.equal(r3.value.kind, "saved");
  assert.equal(r3.value.id, "alpha", "同一路径要沿用原 id");
  assert.equal(r3.value.state.settings.repos.length, 2, "同一路径不许新增条目");
  assert.equal(r3.value.state.settings.currentRepo, "alpha");
});

test("pickPython：取消 → cancelled，不写盘", async () => {
  const h = makeHarness();
  h.chooser.file = null;
  const r = await h.api.pickPython();
  assert.deepEqual(r, { ok: true, value: { kind: "cancelled" } });
  assert.equal(h.bytes(), null);
});

test("pickPython：探测失败 → rejected(python-unusable)，不写盘", async () => {
  const h = makeHarness();
  h.chooser.file = "C:/nowhere/py.exe";
  h.probeState.probePythonResult = { ok: false, reason: "version-too-old" };
  const r = await h.api.pickPython();
  assert.deepEqual(r, { ok: true, value: { kind: "rejected", problem: "python-unusable", path: "C:/nowhere/py.exe" } });
  assert.equal(h.bytes(), null);
  assert.deepEqual(h.probeState.probePythonCalls.map((c) => c[0]), [["C:/nowhere/py.exe"]]);
});

test("pickPython：成功 → saved（没有 id 字段）、pythonPath 写盘", async () => {
  const h = makeHarness();
  h.chooser.file = process.execPath;
  const r = await h.api.pickPython();
  assert.equal(r.ok, true, JSON.stringify(r));
  const v = r.value;
  assert.equal(v.kind, "saved");
  assert.equal(v.path, process.execPath);
  assert.equal("id" in v, false, "pickPython 的 saved 没有 id 字段");
  assert.equal(v.state.python.status, "ok");
  const onDisk = JSON.parse(fs.readFileSync(h.store.filePath, "utf8"));
  assert.equal(onDisk.pythonPath, process.execPath);
});

test("pickKit：取消 → cancelled，不写盘", async () => {
  const h = makeHarness();
  h.chooser.dir = null;
  const r = await h.api.pickKit();
  assert.deepEqual(r, { ok: true, value: { kind: "cancelled" } });
  assert.equal(h.bytes(), null);
});

test("pickKit：没有可用 Python → rejected(python-unusable)，不写盘", async () => {
  const h = makeHarness();
  const kitDir = h.plainDir("kit1");
  h.chooser.dir = kitDir;
  h.probeState.detectPythonResult = { status: "missing", source: "auto", path: "", version: "" };
  const r = await h.api.pickKit();
  assert.deepEqual(r, { ok: true, value: { kind: "rejected", problem: "python-unusable", path: kitDir } });
  assert.equal(h.bytes(), null);
});

test("pickKit：探测失败 → rejected(kit-unusable)，文件字节不变", async () => {
  const h = makeHarness();
  const kitDir = h.plainDir("kit2");
  h.chooser.dir = kitDir;
  h.writeSettings((s) => { s.pythonPath = process.execPath; });
  const before = h.bytes();
  h.probeState.probeKitResult = { ok: false, reason: "kit-unusable" };
  const r = await h.api.pickKit();
  assert.deepEqual(r, { ok: true, value: { kind: "rejected", problem: "kit-unusable", path: kitDir } });
  assert.deepEqual(h.bytes(), before, "被拒不许写盘");
});

test("pickKit：成功 → saved（没有 id 字段）、kitPath 写盘", async () => {
  const h = makeHarness();
  const kitDir = h.plainDir("kit3");
  h.chooser.dir = kitDir;
  h.writeSettings((s) => { s.pythonPath = process.execPath; });
  const r = await h.api.pickKit();
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.kind, "saved");
  assert.equal(r.value.path, kitDir);
  assert.equal("id" in r.value, false, "pickKit 的 saved 没有 id 字段");
  assert.equal(JSON.parse(fs.readFileSync(h.store.filePath, "utf8")).kitPath, kitDir);
});

test("pickTranscriptDir：取消 → cancelled，不写盘", async () => {
  const h = makeHarness();
  h.chooser.dir = null;
  const r = await h.api.pickTranscriptDir();
  assert.deepEqual(r, { ok: true, value: { kind: "cancelled" } });
  assert.equal(h.bytes(), null);
});

test("pickTranscriptDir：保存 → saved（id 与 state）、写盘；同路径沿用 id 不重复", async () => {
  const h = makeHarness();
  const d1 = h.plainDir("logs");
  const d2 = h.plainDir("other");
  h.chooser.dir = d1;
  const r1 = await h.api.pickTranscriptDir();
  assert.equal(r1.value.kind, "saved");
  assert.equal(r1.value.id, "dir");
  assert.deepEqual(r1.value.state.settings.transcriptDirs, [{ id: "dir", path: d1 }]);
  h.chooser.dir = d2;
  const r2 = await h.api.pickTranscriptDir();
  assert.equal(r2.value.id, "dir-2");
  h.chooser.dir = d1;
  const r3 = await h.api.pickTranscriptDir();
  assert.equal(r3.value.kind, "saved", "pickTranscriptDir 不回 rejected");
  assert.equal(r3.value.id, "dir", "同一路径沿用原 id");
  assert.equal(r3.value.state.settings.transcriptDirs.length, 2);
});

test("缓存：getState 不重复探测；pickPython / saveSettings(resetPython) 之后刷新", async () => {
  const h = makeHarness();
  await h.api.getState();
  await h.api.getState();
  assert.equal(h.probeState.detectPythonCalls.length, 1, "两次 getState 只许探测一次 Python");
  h.chooser.file = null;
  await h.api.pickPython();
  await h.api.getState();
  assert.equal(h.probeState.detectPythonCalls.length, 2, "pickPython 之后要重新探测（取消也算）");
  await h.api.getState();
  assert.equal(h.probeState.detectPythonCalls.length, 2);
  const r = await h.api.saveSettings({ resetPython: true });
  assert.equal(r.ok, true, JSON.stringify(r));
  await h.api.getState();
  assert.equal(h.probeState.detectPythonCalls.length, 3, "saveSettings(resetPython) 之后要重新探测");
});

test("缓存：有当前仓库时 pickKit 之后 kit 缓存刷新", async () => {
  const h = makeHarness();
  h.writeSettings((s) => {
    s.pythonPath = process.execPath;
    s.repos = [{ id: "r", name: "rr", path: h.gitRepo("rr"), lastOpened: null }];
    s.currentRepo = "r";
  });
  await h.api.getState();
  await h.api.getState();
  const kitProbes = () => h.probeState.probeKitCalls.length + h.probeState.detectKitCalls.length;
  assert.equal(kitProbes(), 1, "两次 getState 只许探测一次 kit");
  h.chooser.dir = null;
  await h.api.pickKit();
  await h.api.getState();
  assert.equal(kitProbes(), 2, "pickKit 之后要重新探测（取消也算）");
});

test("saveSettings：垃圾输入与各类拒绝都回信封、文件字节不变", async () => {
  const h = makeHarness();
  h.chooser.dir = h.gitRepo("alpha");
  await h.api.pickRepo();
  h.chooser.dir = h.plainDir("logs");
  await h.api.pickTranscriptDir();
  const before = h.bytes();
  const pathLikeId = "C:" + path.sep + "some" + path.sep + "path";
  const CASES = [
    [null, "bad-patch"], [undefined, "bad-patch"], [123, "bad-patch"], ["theme=dark", "bad-patch"],
    [[], "bad-patch"], [true, "bad-patch"], [false, "bad-patch"],
    [{ theme: "dark", extra: 1 }, "bad-patch"],
    [{ theme: "neon" }, "bad-patch"],
    [{ density: "cozy" }, "bad-patch"],
    [{ resetPython: "yes" }, "bad-patch"],
    [{ removeRepo: 5 }, "bad-patch"],
    [{ removeRepo: "ghost" }, "unknown-id"],
    [{ removeTranscriptDir: "ghost" }, "unknown-id"],
    [{ removeRepo: "alpha" }, "current-repo"],
    [{ removeRepo: pathLikeId }, "unknown-id"],
  ];
  for (const pair of CASES) {
    const r = await h.api.saveSettings(pair[0]);
    assert.deepEqual(r, { ok: false, reason: pair[1] }, "patch=" + JSON.stringify(pair[0]));
    assert.deepEqual(h.bytes(), before, "拒绝后文件字节必须不变");
  }
  assert.equal((await h.api.getState()).value.settings.repos.length, 1, "拒绝后内存状态也不变");
});

test("saveSettings：校验顺序 bad-patch → unknown-id → current-repo", async () => {
  const h = makeHarness();
  h.chooser.dir = h.gitRepo("alpha");
  await h.api.pickRepo();
  h.chooser.dir = h.plainDir("logs");
  await h.api.pickTranscriptDir();
  assert.deepEqual(await h.api.saveSettings({ removeRepo: "ghost", theme: "neon" }), { ok: false, reason: "bad-patch" });
  assert.deepEqual(await h.api.saveSettings({ removeTranscriptDir: "ghost", removeRepo: "alpha" }), { ok: false, reason: "unknown-id" });
});

test("saveSettings：整包合格才应用并写盘，回新的 ShellState", async () => {
  const h = makeHarness();
  h.chooser.dir = h.gitRepo("alpha");
  await h.api.pickRepo();
  h.chooser.dir = h.gitRepo("beta");
  await h.api.pickRepo();
  h.chooser.dir = h.plainDir("logs");
  await h.api.pickTranscriptDir();
  h.chooser.file = process.execPath;
  await h.api.pickPython();
  const r = await h.api.saveSettings({
    theme: "dark", density: "compact", removeRepo: "beta", removeTranscriptDir: "dir", resetPython: true,
  });
  assert.deepEqual(Object.keys(r).sort(), ["ok", "value"]);
  assert.equal(r.ok, true, JSON.stringify(r));
  assert.equal(r.value.settings.theme, "dark");
  assert.equal(r.value.settings.density, "compact");
  assert.deepEqual(r.value.settings.repos.map((x) => x.id), ["alpha"]);
  assert.deepEqual(r.value.settings.transcriptDirs, []);
  assert.equal(r.value.settings.currentRepo, "alpha");
  const onDisk = JSON.parse(fs.readFileSync(h.store.filePath, "utf8"));
  assert.equal(onDisk.theme, "dark");
  assert.equal(onDisk.pythonPath, null);
  assert.deepEqual(onDisk.repos.map((x) => x.id), ["alpha"]);
});

test("写盘失败 → write-failed、内存状态回滚（pickRepo 与 saveSettings 都不抛错）", async () => {
  const h = makeHarness({ failingSave: true });
  h.chooser.dir = h.gitRepo("alpha");
  const r = await h.api.pickRepo();
  assert.deepEqual(r, { ok: false, reason: "write-failed" });
  assert.equal((await h.api.getState()).value.settings.repos.length, 0, "写盘失败不许改内存状态");
  const r2 = await h.api.saveSettings({ theme: "dark" });
  assert.deepEqual(r2, { ok: false, reason: "write-failed" });
  assert.equal((await h.api.getState()).value.settings.theme, "system", "写盘失败后内存要回滚成补丁前的值");
});

// 站主 2026-11-13（T033 规划第 3 节）退役了“占位：startService/restartService 回 not-implemented；on 同步返回退订函数且不抛错”一条：
// T033 起真的服务、发 service-state 事件，占位行为不再成立；新行为由 T033 的门禁钉。
'''


PROBE_SHAPE = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { createSettingsStore } = require("@SHELL@/src/settings.js");
const { createShellApi } = require("@SHELL@/src/shellapi.js");

const TS = fs.readFileSync("@THEMIS_TS@", "utf8");

function must(cond, msg) { if (!cond) throw new Error(msg); }

// 解析规则（合同钉死）：接口块从 export interface <名字> { 到行首 }；逐行取 ^\s*(\w+)(\?)?\s*: 的字段名，
// 方法行（名字后是左括号）也算成员；内联对象类型在该行再取一次 (\w+)\s*:（去掉外层字段名）；
// 类型别名从 export type <名字> = 到语句终止分号（大括号配平后的第一个 ;），取其中所有 '…' 字面量。解析不到就断言失败，不许静默通过。
function interfaceBlock(name) {
  const m = TS.match(new RegExp("export interface " + name + " \\{"));
  must(m !== null, "themisShell.ts 里找不到 export interface " + name);
  const rest = TS.slice(m.index + m[0].length);
  const end = rest.search(/\n\}/);
  must(end !== -1, "interface " + name + " 没有行首 } 的结束");
  return rest.slice(0, end);
}
function interfaceNames(name) {
  const block = interfaceBlock(name);
  const names = [];
  for (const line of block.split("\n")) {
    let m = line.match(/^\s*(\w+)(\?)?\s*:/);
    if (m === null) m = line.match(/^\s*(\w+)\s*\(/);
    if (m !== null) names.push(m[1]);
  }
  must(names.length > 0, "interface " + name + " 解析不出成员——类型文件的格式变了，要报警");
  return names;
}
function inlineFields(owner, field) {
  const block = interfaceBlock(owner);
  let line = null;
  for (const l of block.split("\n")) {
    if (new RegExp("^\\s*" + field + "\\s*:\\s*\\{").test(l)) { line = l; break; }
  }
  must(line !== null, owner + " 里找不到内联字段 " + field);
  const inner = line.slice(line.indexOf("{") + 1); // 只取大括号里的字段名，外层字段名不算
  const names = [...inner.matchAll(/(\w+)\s*:/g)].map((m) => m[1]);
  must(names.length > 0, owner + "." + field + " 的内联字段解析失败");
  return names;
}
function typeLiterals(name) {
  const m = TS.match(new RegExp("export type " + name + " ="));
  must(m !== null, "themisShell.ts 里找不到 export type " + name);
  const rest = TS.slice(m.index);
  // 终止分号是大括号配平后的第一个 ";"：多行 union 里 {} 内的分号不是语句结尾
  let depth = 0;
  let semi = -1;
  for (let i = 0; i < rest.length; i++) {
    const c = rest[i];
    if (c === "{") depth += 1;
    else if (c === "}") depth -= 1;
    else if (c === ";" && depth === 0) { semi = i; break; }
  }
  must(semi !== -1, "type " + name + " 没有分号结束");
  const lits = [];
  const re = /'([^']*)'/g;
  let mm;
  while ((mm = re.exec(rest.slice(0, semi))) !== null) lits.push(mm[1]);
  must(lits.length > 0, "type " + name + " 解析不出字面量");
  return lits;
}
function fieldLiterals(owner, field) {
  const block = interfaceBlock(owner);
  for (const l of block.split("\n")) {
    if (new RegExp("^\\s*" + field + "\\??\\s*:").test(l)) {
      const lits = [];
      const re = /'([^']*)'/g;
      let m;
      while ((m = re.exec(l)) !== null) lits.push(m[1]);
      must(lits.length > 0, owner + "." + field + " 解析不出字面量");
      return lits;
    }
  }
  must(false, owner + " 里找不到字段 " + field);
}

function makeApi() {
  const b = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t028-shape-")));
  const userData = path.join(b, "userData");
  fs.mkdirSync(userData);
  const chooser = { dir: null, file: null };
  const probeState = {
    probePythonResult: { ok: true, version: "3.12.9", path: "/fake/python-exe" },
    probeKitResult: { ok: true, version: "2.12.0" },
    detectPythonResult: { status: "missing", source: "auto", path: "", version: "" },
  };
  const probe = {
    async probePython() { return JSON.parse(JSON.stringify(probeState.probePythonResult)); },
    async probeKit(pythonPath, kitDir) { probeState.kitDir = kitDir; return JSON.parse(JSON.stringify(probeState.probeKitResult)); },
    async detectPython() { return JSON.parse(JSON.stringify(probeState.detectPythonResult)); },
    async detectKit(opts) {
      const kitDir = (opts && (opts.kitPath || opts.repoPath)) || null;
      if (!kitDir) return { status: "missing", source: "repo", path: "", version: "" };
      return { status: "ok", source: opts.kitPath ? "external" : "repo", path: path.join(kitDir, "scripts", "pi_dispatch.py"), version: "2.12.0" };
    },
  };
  const api = createShellApi({
    store: createSettingsStore({ dir: userData }),
    chooseDirectory: async () => chooser.dir,
    chooseFile: async () => chooser.file,
    confirmExternal: async () => true,
    openExternal: async () => {},
    appVersion: "9.9.9",
    probe,
  });
  return { b, api, chooser };
}
const keys = (o) => Object.keys(o).sort();

test("成员名与键表：createShellApi 的十个成员、settings.js 的四张表都逐项来自 themisShell.ts", () => {
  const h = makeApi();
  assert.deepEqual(keys(h.api), [...interfaceNames("ThemisShell")].sort(),
    "createShellApi 返回对象的成员名必须与 interface ThemisShell 逐名相等");
  const settings = require("@SHELL@/src/settings.js");
  assert.deepEqual([...settings.PATCH_KEYS].sort(), [...interfaceNames("SettingsPatch")].sort(),
    "PATCH_KEYS 必须与 SettingsPatch 的字段名一致");
  assert.deepEqual([...settings.THEME_VALUES].sort(), [...fieldLiterals("ShellSettings", "theme")].sort(),
    "THEME_VALUES 必须与类型文件里 theme 的字面量一致");
  assert.deepEqual([...settings.DENSITY_VALUES].sort(), [...fieldLiterals("ShellSettings", "density")].sort(),
    "DENSITY_VALUES 必须与类型文件里 density 的字面量一致");
  for (const f of interfaceNames("ShellSettings")) {
    assert.ok(settings.SETTINGS_FILE_KEYS.includes(f), "SETTINGS_FILE_KEYS 缺 ShellSettings 的字段 " + f);
  }
});

test("返回值形状：ShellState 各层键、枚举取值逐项来自 themisShell.ts", async () => {
  const h = makeApi();
  const repoDir = path.join(h.b, "arepo");
  fs.mkdirSync(path.join(repoDir, ".git"), { recursive: true });
  fs.mkdirSync(path.join(repoDir, ".agent"), { recursive: true });
  h.chooser.dir = repoDir;
  const picked = await h.api.pickRepo();
  assert.equal(picked.ok, true, JSON.stringify(picked));
  assert.equal(picked.value.kind, "saved", JSON.stringify(picked));
  const logsDir = path.join(h.b, "logs");
  fs.mkdirSync(logsDir);
  h.chooser.dir = logsDir;
  const pickedDir = await h.api.pickTranscriptDir();
  assert.equal(pickedDir.value.kind, "saved", JSON.stringify(pickedDir));

  const r = await h.api.getState();
  assert.deepEqual(keys(r), ["ok", "value"]);
  const st = r.value;
  assert.deepEqual(keys(st), [...interfaceNames("ShellState")].sort(), "ShellState 的键必须与类型文件一致");
  assert.deepEqual(keys(st.app), [...inlineFields("ShellState", "app")].sort());
  assert.deepEqual(keys(st.settings), [...interfaceNames("ShellSettings")].sort());
  must(st.settings.repos.length >= 1, "要有一个仓库条目才能比对 RepoEntry");
  assert.deepEqual(keys(st.settings.repos[0]), [...interfaceNames("RepoEntry")].sort());
  must(st.settings.transcriptDirs.length >= 1, "要有一个会话目录条目才能比对 TranscriptDirEntry");
  assert.deepEqual(keys(st.settings.transcriptDirs[0]), [...interfaceNames("TranscriptDirEntry")].sort());
  assert.deepEqual(keys(st.python), [...inlineFields("ShellState", "python")].sort());
  assert.deepEqual(keys(st.kit), [...inlineFields("ShellState", "kit")].sort());
  assert.ok(typeLiterals("ServiceState").includes(st.service.kind), "service.kind 必须是 ServiceState 的取值");
  assert.ok(typeLiterals("RepoCheck").includes(st.currentRepoCheck),
    "合法仓库的 currentRepoCheck 必须是 RepoCheck 里的取值：" + JSON.stringify(st.currentRepoCheck));
  assert.ok(fieldLiterals("ShellSettings", "theme").includes(st.settings.theme));
  assert.ok(fieldLiterals("ShellSettings", "density").includes(st.settings.density));

  const plain = path.join(h.b, "plain");
  fs.mkdirSync(plain);
  h.chooser.dir = plain;
  const rej = await h.api.pickRepo();
  assert.equal(rej.value.kind, "rejected", JSON.stringify(rej));
  assert.ok(typeLiterals("PickProblem").includes(rej.value.problem), "被拒的 problem 必须是 PickProblem 的取值");
});
'''


PROBE_EXTERNAL = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { createSettingsStore } = require("@SHELL@/src/settings.js");
const { createShellApi } = require("@SHELL@/src/shellapi.js");
const { isExternalUrl } = require("@SHELL@/src/hostcheck.js");

function makeApi() {
  const b = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), "t028-ext-")));
  const dir = path.join(b, "userData");
  fs.mkdirSync(dir);
  const confirm = { answer: true, throwIt: false, calls: [] };
  const opener = { throwIt: false, calls: [] };
  const api = createShellApi({
    store: createSettingsStore({ dir }),
    chooseDirectory: async () => null,
    chooseFile: async () => null,
    confirmExternal: async (u) => { confirm.calls.push(u); if (confirm.throwIt) throw new Error("确认框坏了"); return confirm.answer; },
    openExternal: async (u) => { opener.calls.push(u); if (opener.throwIt) throw new Error("打不开"); },
  });
  return { api, confirm, opener };
}

const URLS = [
  "javascript:alert(1)", "file:///C:/x", "data:text/html,hi", "ftp://x.example/",
  " http://x.example/", "http://x.example/ ", "http://x.exa\nmple/", "http:\\\\x.example/",
  "//x.example/", "x.example/", "", 123, null, undefined,
  "http://x.example/", "https://X.EXAMPLE/a?q=1#h",
];

test("bad-url 的判定与 hostcheck.js 的 isExternalUrl 逐项等价（复用同一判据）", async () => {
  const h = makeApi();
  for (const u of URLS) {
    const r = await h.api.openExternal(u);
    const judgedBad = !(r.ok === true);
    assert.equal(judgedBad, isExternalUrl(u) === false,
      "bad-url 的判定必须与 isExternalUrl 一致：" + JSON.stringify(u));
    if (judgedBad) assert.equal(r.reason, "bad-url", JSON.stringify([u, r]));
  }
  h.confirm.answer = false; // 合法地址走确认分支，非法地址根本不许弹确认框
  h.confirm.calls.length = 0;
  h.opener.calls.length = 0;
  for (const u of ["javascript:alert(1)", " http://x.example/", 123]) {
    h.confirm.calls.length = 0;
    const r = await h.api.openExternal(u);
    assert.deepEqual(r, { ok: false, reason: "bad-url" }, JSON.stringify(u));
    assert.deepEqual(h.confirm.calls, [], "校验不过不许弹确认框：" + JSON.stringify(u));
    assert.deepEqual(h.opener.calls, []);
  }
});

test("确认取消 → cancelled、不打开；url 原样传给确认框", async () => {
  const h = makeApi();
  h.confirm.answer = false;
  const r = await h.api.openExternal("https://x.example/a?q=1#h");
  assert.deepEqual(r, { ok: false, reason: "cancelled" });
  assert.deepEqual(h.confirm.calls, ["https://x.example/a?q=1#h"]);
  assert.deepEqual(h.opener.calls, []);
});

test("确认放行 → {ok:true, value:null}，打开函数收到原 url", async () => {
  const h = makeApi();
  const r = await h.api.openExternal("https://x.example/a");
  assert.deepEqual(r, { ok: true, value: null });
  assert.deepEqual(h.confirm.calls, ["https://x.example/a"]);
  assert.deepEqual(h.opener.calls, ["https://x.example/a"]);
});

test("打开失败 → open-failed；确认框抛错 → internal", async () => {
  const h = makeApi();
  h.opener.throwIt = true;
  assert.deepEqual(await h.api.openExternal("https://x.example/"), { ok: false, reason: "open-failed" });
  const h2 = makeApi();
  h2.confirm.throwIt = true;
  assert.deepEqual(await h2.api.openExternal("https://x.example/"), { ok: false, reason: "internal" });
});
'''


# --------------------------------------------------------------------------- 探针包装

def test_p01_probe_settings():
    """D01：设置存盘——缺省、坏文件副本、未知键、原子写与临时文件（node --test 探针）。"""
    _expect_probe_pass("t028-settings", PROBE_SETTINGS)


def test_p02_probe_patch():
    """D02：applyPatch 六键白名单与三类拒绝、addRepo/addTranscriptDir 的去重与 id（node --test 探针）。"""
    _expect_probe_pass("t028-patch", PROBE_PATCH)


def test_p03_probe_detect():
    """D03：三项校验与自动检测、子进程形状与时限（node --test 探针）。"""
    _expect_probe_pass("t028-detect", PROBE_DETECT)


def test_p04_probe_shellapi():
    """D04：四个选择器三态与写盘边界、缓存、写盘失败回滚、占位成员（node --test 探针）。"""
    _expect_probe_pass("t028-api", PROBE_API)


def test_p05_probe_shape():
    """D05：返回值形状与 themisShell.ts 逐字段一致（读类型文件比对，不另抄键表）。"""
    _expect_probe_pass("t028-shape", PROBE_SHAPE)


def test_p06_probe_openexternal():
    """D06：openExternal 复用 isExternalUrl 与确认框，三种失败原因（node --test 探针）。"""
    _expect_probe_pass("t028-external", PROBE_EXTERNAL)
