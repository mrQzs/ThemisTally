"""T039 战前门禁：桌面端外壳第 7 片「服务状态页按『跑起来之后才退出』写说明（D3 收尾）」的黑盒基准测试
（合同 t039-desktop-exit-note v1，基线 b71819d——serviceflow 的 moveTo 还不写 afterRunning，
exitCodes.stoppedNote 只收一个实参，ServiceState 的 exited 分支没有可选键，夹具没有 crash-1 场景、
crash 的 base 不带键，服务状态页的说明只按退出码取，README 冒烟第 4 条与状态说明都没写约定）。

被测对象：``desktop/shell/src/serviceflow.js`` 的 ``moveTo``（进过 running 之后的退出带
``afterRunning: true``；启动阶段的 exited 不带这个键；键按 run 算；``info.byShell`` 与其余语义一字不动）、
``desktop/web/src/shellpages/themisShell.ts`` 的 ``ServiceState``（exited 分支加可选键，类型体里不写注释）、
``exitCodes.ts`` 的 ``stoppedNote(code, afterRunning = false)``（为真一律「本机服务意外退出」，三句常量
与 ``firstRunHeadline`` 一字不改）、``ServiceStatusView.tsx``（说明那一行传第二实参，退出码行与其余 DOM
不变）、``mock/shellpages-scenarios.ts``（新场景 crash-1；crash 的 base 补键；11 个旧场景名一个不删）、
``desktop/shell/README.md``（冒烟第 4 条补半句、状态说明补约定并改掉「多一个键就与类型不符」那句）。

结构（编号大致对应合同 DoD 的 D01–D05）：

- 静态断言（``test_s*``，不需要任何依赖；全部在基线上红在 afterRunning 约定缺失上）：
  - S01/D01：serviceflow.js——moveTo 里写 afterRunning: true、判据是赋值前那一刻的 current.kind ===
    "running"、不许写 afterRunning: false；byShell 取值与判定次序不钉写法（语义由 P01 的行为断言钉住）。
  - S02/D01：themisShell.ts——exited 分支加 afterRunning?: boolean、类型体里不写注释、说明写在上方
    注释里、其余三个分支一字不动。
  - S03/D02/D03：exitCodes.ts——stoppedNote 第二实参（为真一律意外退出；判定次序不钉写法）、三句常量
    与 firstRunHeadline 不改、
    文件头「再定退出码 1 的两种含义」那句要改成已定的说法；首启两个文件不读 afterRunning。
  - S04/D02：ServiceStatusView.tsx——说明那一行传 ``exited && service.afterRunning === true``；
    退出码行、h1、两个按钮、title 照旧；视图里不另写那三句。
  - S05/D04：scenarios——crash-1（base exited 1 + afterRunning: true、start 是 exited 1 不带键）、
    crash 的 base 补键且退出码 3 与 start running 不动、11 个旧场景名都在、exit-1/exit-2 的 start
    不带键。
  - S06/D05：README——冒烟第 4 条在「并显示退出码」之后补「本机服务意外退出」那半句、状态说明写
    afterRunning 约定并删「页面负载多一个键就与类型不符」、``| **1** |`` 行与既有 needle 不动。
- 探针断言（``test_p*``，``node --test``，不需要 npm 依赖；基线上红在 afterRunning 缺失的断言上）：
  - P01/D01：serviceflow 真起子进程——跑起来之后 stop / 服务自己退出（码 1 与缺省 3）/ onRunning
    失败后的收服务都带 afterRunning: true；启动阶段的四处退出（exit2、坏握手、握手超时、spawn 失败）
    与 starting 期间 abort 一律不带键；握手失败的 exited 仍只认 4 个键（T033 :465 的 deepEqual）；
    键按 run 算；byShell 取值照旧。
- 流水线断言（``test_f*``，``pipeline`` 会话级夹具）：页面行为在 Vitest 探针里测（stoppedNote 第二
  实参、crash-1 初始说明、exit-1 启动阶段说明、crash-1 点重启 1500ms 后换说明）。**基线自检不装
  依赖**：``desktop/web/node_modules`` 里没有 vitest 时夹具不调 npm，给出说明后由各用例开头那条
  静态前置断言（合同行为在基线上还不存在）先红；执行端按合同 Setup（S01 npm ci）装好依赖后，
  探针才真正跑。全量 pytest 默认跳过用到 ``pipeline`` 的用例（tests/conftest.py），点名运行本文件
  时照常执行。

门禁端按最合理读法定下的地方（有合理默认，不拦流程）：「意外退出」那半句在冒烟第 4 条里的措辞合同
只给了示例，S06 只断言「并显示退出码」之后出现「本机服务意外退出」；crash-1 的 repo/python/kit/
transcriptDir 队列字段按合同「与 crash 一样」断言为 ALL_SAVED；afterRunning 键写成 ``false`` 视为
违反「启动阶段不带这个键」（S01 与 P01 都盯）。
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL = REPO_ROOT / "desktop" / "shell"
WEB = REPO_ROOT / "desktop" / "web"
SP_REL = "desktop/web/src/shellpages"
SCENARIOS_REL = "desktop/web/src/mock/shellpages-scenarios.ts"

SERVICEFLOW_REL = "desktop/shell/src/serviceflow.js"
THEMIS_SHELL_REL = f"{SP_REL}/themisShell.ts"
EXITCODES_REL = f"{SP_REL}/exitCodes.ts"
SERVICE_VIEW_REL = f"{SP_REL}/ServiceStatusView.tsx"
README_REL = "desktop/shell/README.md"

ALREADY_OPEN = "这个仓库已经在另一个窗口里打开了。"
INCOMPLETE = "应用文件不完整，请重新安装。"
UNEXPECTED = "本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。"

OLD_SCENARIOS = ("ready", "checking", "first-launch", "not-git", "no-agent", "no-python",
                 "no-kit", "exit-1", "exit-2", "crash", "custom")


# ---------------------------------------------------------------------------
# 通用小工具（文件读取都发生在用例函数里）
# ---------------------------------------------------------------------------

def _norm(text):
    return text.replace("\r\n", "\n")


def _need_file(rel):
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return path


def _need_text(rel):
    return _norm(_need_file(rel).read_text(encoding="utf-8"))


def fail_if(problems, where):
    assert not problems, f"{where} 的问题：\n" + "\n".join(f"- {p}" for p in problems)


def _balanced_from(text, open_idx):
    """从第 open_idx 个 ``{`` 起截取配平的花括号块。"""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx:i + 1]
    raise AssertionError("花括号不配平")


def _sub_block(block, key):
    m = re.search(rf"{key}:\s*\{{", block)
    assert m, f"块里没有字段 {key}"
    return _balanced_from(block, block.find("{", m.start()))


def _scenario_block(text, name):
    m = re.search(rf"'{re.escape(name)}':\s*\{{", text)
    assert m, f"夹具里没有场景「{name}」"
    return _balanced_from(text, text.find("{", m.start()))


# ---------------------------------------------------------------------------
# 静态断言（S01–S06）
# ---------------------------------------------------------------------------

def test_s01_serviceflow_after_running_wiring():
    """S01/D01：afterRunning 只加不改——moveTo 里写 afterRunning: true、判据是赋值前那一刻的
    current.kind === "running"、不许写 afterRunning: false。byShell 的取值与判定次序都不钉写法
    （语义由 P01 的行为断言钉住：启动阶段的退出不带键、跑起来之后的退出带键、byShell true/false）。"""
    text = _need_text(SERVICEFLOW_REL)
    problems = []
    if "afterRunning" not in text:
        problems.append("src/serviceflow.js 里没有 afterRunning（moveTo 要在 running→exited 时带 afterRunning: true）")
    if re.search(r"afterRunning\s*:\s*false", text):
        problems.append("不许写 afterRunning: false——启动阶段的退出不带这个键（不是 false，也不是显式 undefined 键）")
    m = re.search(r"function\s+moveTo\s*\(", text)
    if not m:
        problems.append("找不到 moveTo 函数（moveTo 的形状与合同不符，见 Stop conditions）")
    else:
        body = _balanced_from(text, text.find("{", m.end()))
        if not re.search(r"afterRunning:\s*true", body):
            problems.append("moveTo 里没有写 afterRunning: true")
        flat = body.replace("'", '"')
        if 'current.kind === "running"' not in flat:
            problems.append('moveTo 里的判据是赋值前那一刻的 current.kind === "running"（启动阶段不带键）')
    fail_if(problems, "src/serviceflow.js")


def test_s02_servicestate_exited_after_running():
    """S02/D01：ServiceState 的 exited 分支加可选键 afterRunning?: boolean；类型体里不写注释
    （shellshape 的 typeLiterals 按单引号与顶层分号解析）；说明写在类型上方的注释里；其余分支一字不动。"""
    text = _need_text(THEMIS_SHELL_REL)
    problems = []
    if not re.search(r"\{\s*kind:\s*'exited';\s*repo:\s*string;\s*exitCode:\s*number;\s*at:\s*number;\s*afterRunning\?:\s*boolean\s*\}", text):
        problems.append("ServiceState 的 exited 分支要加可选键：{ kind: 'exited'; repo: string; exitCode: number; at: number; afterRunning?: boolean }")
    m = re.search(r"export\s+type\s+ServiceState\s*=", text)
    if m:
        end = text.find("};", m.start())
        block = text[m.start():end]
        if "//" in block or "/*" in block:
            problems.append("ServiceState 的类型体里不许写注释（说明写在类型上方的注释里）")
        for keep in ("{ kind: 'idle' }", "{ kind: 'starting'; repo: string }",
                     "{ kind: 'running'; repo: string; pid: number; startedAt: string }"):
            if keep not in block:
                problems.append(f"ServiceState 其余分支不许动：缺 {keep}")
        lines = text[:m.start()].splitlines()
        comments = []
        for ln in reversed(lines):
            s = ln.strip()
            if s.startswith("//") or s.startswith("/*") or s.startswith("*"):
                comments.append(s)
            else:
                break
        if not any("afterRunning" in c for c in comments):
            problems.append("ServiceState 上方的注释要写清 afterRunning 的约定（跑起来之后才退出的另带这个键）")
    fail_if(problems, "themisShell.ts")


def test_s03_stopped_note_second_param():
    """S03/D02/D03：stoppedNote(code: number, afterRunning = false)——为真一律「本机服务意外退出」
    （与 code 的先后次序不钉写法，语义由 F01 的行为断言钉住）；三句常量与 firstRunHeadline 一字
    不改；文件头「再定退出码 1 的两种含义」那句改成已定的说法；首启两个文件不读 afterRunning。"""
    text = _need_text(EXITCODES_REL)
    problems = []
    if not re.search(r"export\s+function\s+stoppedNote\s*\(\s*code:\s*number\s*,\s*afterRunning\s*=\s*false\s*\)\s*:\s*string", text):
        problems.append("stoppedNote 要改成 stoppedNote(code: number, afterRunning = false): string（默认参数让既有调用点照旧成立）")
    m = re.search(r"export\s+function\s+stoppedNote[^{]*\{", text)
    if m:
        body = _balanced_from(text, m.end() - 1)
        if "afterRunning" not in body:
            problems.append("stoppedNote 的函数体里没用到 afterRunning")
    for s in (ALREADY_OPEN, INCOMPLETE, UNEXPECTED):
        if s not in text:
            problems.append(f"三句说明常量一字不改：缺「{s}」")
    if not re.search(r"export\s+function\s+firstRunHeadline\s*\(\s*code:\s*number\s*\)\s*:\s*string", text):
        problems.append("firstRunHeadline 只收 code（首启第 4 步不读 afterRunning）")
    if "接真实外壳那一片再定退出码 1 的两种含义" in text:
        problems.append("文件头注释里「接真实外壳那一片再定退出码 1 的两种含义」要改成已定的说法（两种含义已由 afterRunning 分开）")
    for rel in ("FirstRunView.tsx", "firstRunModel.ts"):
        t = _need_text(f"{SP_REL}/{rel}")
        if "afterRunning" in t:
            problems.append(f"{rel} 不读 afterRunning（首启第 4 步只有启动阶段的失败，一个字不改）")
    fail_if(problems, "exitCodes.ts")


def test_s04_service_status_note_call():
    """S04/D02：说明那一行传第二实参 stoppedNote(exited ? service.exitCode : 0, exited &&
    service.afterRunning === true)；退出码行、h1、两个按钮、title、不设 role=alert 照旧；视图里
    不另写那三句文案。"""
    text = _need_text(SERVICE_VIEW_REL)
    problems = []
    if not re.search(r"stoppedNote\(\s*exited\s*\?\s*service\.exitCode\s*:\s*0\s*,\s*exited\s*&&\s*service\.afterRunning\s*===\s*true\s*\)", text):
        problems.append("说明那一行要传第二实参：stoppedNote(exited ? service.exitCode : 0, exited && service.afterRunning === true)")
    for needle in ("data-exit-code", "重启后会重新读取数据。", "本机服务已停止", "重启服务", "打开设置", "document.title"):
        if needle not in text:
            problems.append(f"退出码行与其余 DOM 不许改：缺「{needle}」")
    if not re.search(r"from\s+'\./exitCodes'", text):
        problems.append("ServiceStatusView 仍要从 ./exitCodes 导入 stoppedNote")
    for s in (ALREADY_OPEN, INCOMPLETE, UNEXPECTED):
        if s in text:
            problems.append(f"视图里不许另写那三句文案（只放 exitCodes.ts）：出现了「{s[:12]}…」")
    fail_if(problems, "ServiceStatusView.tsx")


def test_s05_scenarios_crash1_and_crash_key():
    """S05/D04：新场景 crash-1（base 是 exited 1 + afterRunning: true、其余队列字段与 crash 一样、
    start 是 exited 1 不带键）；crash 的 base 补 afterRunning: true 且退出码 3 与 start running 一字
    不动；11 个旧场景名一个不删；exit-1/exit-2 的 start 不带键；SHELLPAGE_SCENARIO_NAMES 仍是
    Object.keys；文件头「示意」保留。"""
    text = _need_text(SCENARIOS_REL)
    problems = []
    if not re.search(r"'crash-1':\s*\{", text):
        problems.append("夹具缺新场景 crash-1（base 是 exited 1 + afterRunning: true；start 是 exited 1 不带键）")
    else:
        blk = _scenario_block(text, "crash-1")
        svc = _sub_block(blk, "service")
        for needle, what in (("kind: 'exited'", "exited"), ("repo: 'demo-repo'", "repo demo-repo"),
                             ("exitCode: 1", "退出码 1"), ("at: Date.parse('2026-10-18T09:41:07')", "at 取 crash 同一时刻"),
                             ("afterRunning: true", "afterRunning: true")):
            if needle not in svc:
                problems.append(f"crash-1 的 base.service 缺 {what}")
        st = _sub_block(blk, "start")
        if "kind: 'exited'" not in st or "exitCode: 1" not in st:
            problems.append("crash-1 的 start 是 { kind: 'exited', exitCode: 1 }（不带键：同一页演示重启后换说明）")
        if "afterRunning" in st:
            problems.append("crash-1 的 start（启动阶段的退出）不许带 afterRunning 键")
        for q in ("repo: ALL_SAVED", "python: ALL_SAVED", "kit: ALL_SAVED", "transcriptDir: ALL_SAVED"):
            if q not in blk:
                problems.append(f"crash-1 的其余队列字段与 crash 一样：缺 {q}")
    if re.search(r"'crash':\s*\{", text):
        blk = _scenario_block(text, "crash")
        svc = _sub_block(blk, "service")
        if "afterRunning: true" not in svc:
            problems.append("crash 的 base.service（跑起来之后崩的）要补 afterRunning: true")
        if "exitCode: 3" not in svc:
            problems.append("crash 的退出码 3 一字不改（T012 的 d02、d06 过渡探针靠它）")
        st = _sub_block(blk, "start")
        if "kind: 'running'" not in st or "exitCode" in st:
            problems.append("crash 的 start 仍是 { kind: 'running' }，一字不改")
    else:
        problems.append("夹具缺既有场景 crash")
    for name in OLD_SCENARIOS:
        if not re.search(rf"'{re.escape(name)}':\s*\{{", text):
            problems.append(f"旧场景名 {name} 不许删、不许改名")
    if "Object.keys(SHELLPAGE_SCENARIOS)" not in text:
        problems.append("SHELLPAGE_SCENARIO_NAMES 仍是 Object.keys(SHELLPAGE_SCENARIOS)（新场景名自动进名单，?shell=crash-1 能打开）")
    if "示意" not in "\n".join(text.split("\n")[:15]):
        problems.append("文件头前 15 行的「示意」标注保留")
    for name, code in (("exit-1", 1), ("exit-2", 2)):
        if re.search(rf"'{re.escape(name)}':\s*\{{", text):
            st = _sub_block(_scenario_block(text, name), "start")
            if "kind: 'exited'" not in st or f"exitCode: {code}" not in st:
                problems.append(f"{name} 的 start 仍是 {{ kind: 'exited', exitCode: {code} }}")
            if "afterRunning" in st:
                problems.append(f"{name} 的 start（启动阶段）不许带 afterRunning 键")
    fail_if(problems, "src/mock/shellpages-scenarios.ts")


def test_s06_readme_after_running_and_smoke_note():
    """S06/D05：README 两处——冒烟第 4 条在「并显示退出码」之后补上说明是「本机服务意外退出」那句
    （既有字样一个不删）；状态说明写 afterRunning 的约定，并把「页面负载多一个键就与类型不符」那句
    改成只说 byShell 不外传；``| **1** |`` 那一行与既有 needle 不动。"""
    text = _need_text(README_REL)
    problems = []
    lines = text.splitlines()
    smoke = [ln for ln in lines if re.match(r"^\s*4\.\s", ln) and "并显示退出码" in ln]
    if not smoke:
        problems.append("README 手工冒烟第 4 条（以「4. 」开头的列表项）里要有「并显示退出码」那半句")
    for ln in smoke:
        rest = ln[ln.find("并显示退出码"):]
        if "本机服务意外退出" not in rest:
            problems.append("冒烟第 4 条要在「并显示退出码」之后补上说明是「本机服务意外退出」那一句")
        for needle in ("themis-shell://app/index.html#/service-status", "重启服务", "T032 已落地，页面点得动"):
            if needle not in ln:
                problems.append(f"冒烟第 4 条的既有字样不许删：{needle}")
    if "afterRunning" not in text:
        problems.append("README 状态说明要写 afterRunning 的约定（跑起来之后才退出的 exited 另带 true，启动阶段不带这个键）")
    if "多一个键就与类型不符" in text:
        problems.append("「ServiceState 被 themisShell.ts 钉死，页面负载多一个键就与类型不符」要改成只说 byShell 不外传（类型里现在多了可选键）")
    if "byShell" not in text:
        problems.append("状态说明里 byShell 的说法保留（只在主进程、不进事件负载、不进 getState().service）")
    rows1 = [ln for ln in lines if re.match(r"^\|\s*\*\*1\*\*\s*\|", ln)]
    if not rows1:
        problems.append("退出码表缺 | **1** | 这一行")
    for ln in rows1:
        if "服务意外退出" in ln:
            problems.append("| **1** | 那一行不许出现「服务意外退出」（T035 test_s05_readme）")
    for needle in ("T032", "on('service-state'", "桩数据", "外壳页在本片就位", "npm --prefix ../web run build",
                   "themis-shell://app/index.html#/first-run", "desktop/web/dist", "themisShell"):
        if needle not in text:
            problems.append(f"README 缺既有 needle「{needle}」")
    if text.count("服务状态页") < 2:
        problems.append("「服务状态页」在 README 里至少 2 处")
    fail_if(problems, "desktop/shell/README.md")


# ---------------------------------------------------------------------------
# 探针断言（node --test，不需要 npm 依赖）
# ---------------------------------------------------------------------------

PROBE_SERVICEFLOW = r'''
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { createServiceFlow } = require("@SHELL@/src/serviceflow.js");

const FAKE = path.join("@SHELL@", "tests", "fixtures", "fake-service.js");
const FAKE_EXIT = path.join("@SHELL@", "tests", "fixtures", "fake-service-exit.js");

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

test("跑起来之后外壳自己 stop() → exited 带 afterRunning: true、byShell=true、starting/running 不带键", async () => {
  const flow = createServiceFlow({});
  const events = [];
  const infos = [];
  flow.subscribe((state, info) => {
    events.push(state);
    infos.push(info);
  });
  const envelope = await flow.start({
    repo: "r-stop",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "ok" }),
  });
  assert.deepEqual(envelope, { ok: true, value: null });
  assert.equal(events[1].kind, "running");
  assert.equal("afterRunning" in events[0], false, "starting 状态不带键");
  assert.equal("afterRunning" in events[1], false, "running 状态不带键");
  const stopResult = await flow.stop();
  assert.equal(stopResult.exited, true, JSON.stringify(stopResult));
  await waitFor("stop 之后的 exited", () => events.length >= 3 && events[2].kind === "exited", 8000);
  assert.equal(events[2].exitCode, 0);
  assert.equal(events[2].afterRunning, true, "跑起来之后 stop 的 exited 要带 afterRunning: true");
  assert.equal(infos[2].byShell, true, "外壳 stop 的 byShell 照旧是 true");
  assert.equal(flow.state().afterRunning, true, "state() 与事件负载给的是同一个约定");
});

test("握手成功后服务自己退出（FAKE_SERVICE_EXIT_CODE=1）→ exited 带 afterRunning: true、byShell=false", async () => {
  const flow = createServiceFlow({});
  const events = [];
  const infos = [];
  flow.subscribe((state, info) => {
    events.push(state);
    infos.push(info);
  });
  const envelope = await flow.start({
    repo: "r-self-1",
    command: [process.execPath, FAKE_EXIT],
    env: envWith({ FAKE_SERVICE_EXIT_CODE: "1" }),
  });
  assert.deepEqual(envelope, { ok: true, value: null });
  assert.equal(events[1].kind, "running");
  await waitFor("服务自己退出", () => events.length >= 3 && events[2].kind === "exited", 8000);
  assert.equal(events[2].exitCode, 1, "跑起来之后的退出码 1 也要原样给出");
  assert.equal(events[2].afterRunning, true, "跑起来之后服务自己退出的 exited 要带 afterRunning: true");
  assert.equal(infos[2].byShell, false, "服务自己退出的 byShell 照旧是 false");
});

test("握手成功后服务自己退出（缺省码 3）→ exited 带 afterRunning: true", async () => {
  const flow = createServiceFlow({});
  const events = [];
  flow.subscribe((state) => events.push(state));
  await flow.start({ repo: "r-self-3", command: [process.execPath, FAKE_EXIT] });
  assert.equal(events[1].kind, "running");
  await waitFor("服务自己退出", () => events.length >= 3 && events[2].kind === "exited", 8000);
  assert.equal(events[2].exitCode, 3);
  assert.equal(events[2].afterRunning, true, "跑起来之后退出的 exited 要带 afterRunning: true（与退出码无关）");
});

test("onRunning 抛错 → 收服务（stop 语义）之后的 exited 也带 afterRunning: true", async () => {
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
  assert.equal(events[2].afterRunning, true, "跑起来之后收服务的 exited 也带 afterRunning: true");
});

test("启动阶段的 exited 一律不带键：exit2（4 键 deepEqual）、坏握手、握手超时、spawn 失败", async () => {
  {
    const flow = createServiceFlow({});
    const events = [];
    const infos = [];
    flow.subscribe((state, info) => {
      events.push(state);
      infos.push(info);
    });
    const envelope = await flow.start({
      repo: "r-exit2",
      command: [process.execPath, FAKE],
      env: envWith({ FAKE_SERVICE_MODE: "exit2" }),
    });
    assert.deepEqual(envelope, { ok: false, reason: "handshake-failed" });
    assert.equal(events[1].kind, "exited", "起进程之后的失败要先发 exited 再回信封");
    assert.equal(events[1].exitCode, 2);
    assert.equal("afterRunning" in events[1], false, "握手前退出（启动阶段）不许带 afterRunning 键");
    assert.equal(infos[1].byShell, false);
    assert.deepEqual(flow.state(), { kind: "exited", repo: "r-exit2", exitCode: 2, at: events[1].at }, "启动失败的 exited 仍只认 4 个键（T033 :465 与 serviceflow.test.js :118-121）");
  }
  {
    const flow = createServiceFlow({});
    const events = [];
    flow.subscribe((state) => events.push(state));
    const envelope = await flow.start({
      repo: "r-bad",
      command: [process.execPath, FAKE],
      env: envWith({ FAKE_SERVICE_MODE: "bad" }),
    });
    assert.deepEqual(envelope, { ok: false, reason: "handshake-failed" });
    assert.equal(flow.state().kind, "exited");
    assert.equal(flow.state().exitCode, -1);
    assert.equal("afterRunning" in flow.state(), false, "坏握手（启动阶段）不许带 afterRunning 键");
  }
  {
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
    assert.equal(flow.state().exitCode, -1);
    assert.equal("afterRunning" in flow.state(), false, "握手超时（启动阶段）不许带 afterRunning 键");
  }
  {
    const flow = createServiceFlow({});
    const events = [];
    flow.subscribe((state) => events.push(state));
    const envelope = await flow.start({ repo: "r-enoent", command: ["themistally-no-such-bin-xyz", "arg"] });
    assert.deepEqual(envelope, { ok: false, reason: "start-failed" });
    assert.equal(flow.state().kind, "exited");
    assert.equal(flow.state().exitCode, -1);
    assert.equal("afterRunning" in flow.state(), false, "spawn 失败（启动阶段）不许带 afterRunning 键");
  }
});

test("starting 期间 abort() 的 exited 不带键（此刻 current.kind 是 starting）", async () => {
  const flow = createServiceFlow({ timeoutMs: 8000 });
  const events = [];
  flow.subscribe((state) => events.push(state));
  const startPromise = flow.start({
    repo: "r-abort",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "silent" }),
  });
  await waitFor("starting 状态", () => events.length >= 1 && events[0].kind === "starting");
  await flow.abort();
  await waitFor("abort 之后的 exited", () => events.length >= 2 && events[1].kind === "exited", 5000);
  assert.equal(events[1].exitCode, -1);
  assert.equal("afterRunning" in events[1], false, "starting 期间 abort（启动阶段）不许带 afterRunning 键");
  const settled = await Promise.race([
    startPromise,
    new Promise((_, reject) => setTimeout(() => reject(new Error("abort 之后 start 的信封没有兑现")), 8000)),
  ]);
  assert.equal(typeof settled.ok, "boolean", "start 的信封要兑现（不 reject）");
});

test("键按 run 算：run1 跑起来之后退出（带键），run2 启动阶段失败（不带键）", async () => {
  const flow = createServiceFlow({});
  const events = [];
  flow.subscribe((state) => events.push(state));
  await flow.start({
    repo: "r-run1",
    command: [process.execPath, FAKE_EXIT],
    env: envWith({ FAKE_SERVICE_EXIT_CODE: "1" }),
  });
  await waitFor("run1 服务自己退出", () => events.length >= 3 && events[2].kind === "exited", 8000);
  assert.equal(events[2].afterRunning, true, "run1：跑起来之后退出要带键");
  assert.equal(events.length, 3, JSON.stringify(events.map((e) => e.kind)));
  const envelope2 = await flow.start({
    repo: "r-run2",
    command: [process.execPath, FAKE],
    env: envWith({ FAKE_SERVICE_MODE: "exit2" }),
  });
  assert.deepEqual(envelope2, { ok: false, reason: "handshake-failed" });
  const run2 = events.slice(3);
  assert.equal(run2.length, 2, JSON.stringify(events.map((e) => e.kind)));
  assert.equal(run2[0].kind, "starting", "新 run 先进 starting");
  assert.equal(run2[1].kind, "exited");
  assert.equal(run2[1].exitCode, 2);
  assert.equal("afterRunning" in run2[1], false, "run2：启动阶段的退出不许带键（不继承上一 run 的键）");
});
'''


def test_p01_serviceflow_after_running():
    """P01/D01：serviceflow 真起子进程——running→exited 的三类路径（stop、服务自己退出、onRunning
    失败后的收服务）都带 afterRunning: true；启动阶段的退出（exit2、坏握手、握手超时、spawn 失败、
    starting 期间 abort）一律不带键且仍是 4 键形状；键按 run 算；byShell 照旧。"""
    node = shutil.which("node")
    assert node, "本机没有 node，无法运行门禁探针"
    source = PROBE_SERVICEFLOW.replace("@SHELL@", json.dumps(str(SHELL))[1:-1])
    with tempfile.TemporaryDirectory(prefix="t039-gate-") as td:
        probe = Path(td) / "t039-serviceflow.test.js"
        probe.write_text(source, encoding="utf-8")
        proc = subprocess.run(
            [node, "--test", str(probe)],
            cwd=str(REPO_ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300,
        )
    assert proc.returncode == 0, (
        f"serviceflow 探针没有全绿（退出码 {proc.returncode}）：\n"
        f"--- stdout 末尾 ---\n{proc.stdout[-6000:]}\n--- stderr 末尾 ---\n{proc.stderr[-1500:]}"
    )


# ---------------------------------------------------------------------------
# 流水线断言（Vitest 探针；基线自检不装依赖，见模块 docstring）
# ---------------------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def tail_text(text, max_chars=3500, max_lines=45):
    text = _ANSI.sub("", text)
    lines = text.splitlines()[-max_lines:]
    joined = "\n".join(lines)
    return joined[-max_chars:]


def probe_groups(source):
    """{describe 名: 用例数}：描述块写在行首 ``describe('名字'``，用例写成行首缩进的 ``it(``。"""
    groups, current = {}, None
    for line in source.splitlines():
        m = re.match(r"describe\('([^']+)'", line)
        if m:
            current = m.group(1)
            groups[current] = 0
        elif current and re.match(r"\s+it\(", line):
            groups[current] += 1
    return groups


def parse_vitest_json(text):
    """从 ``npm test -- … --reporter=json`` 的输出里取出 JSON（前面有 npm 的横幅行）。"""
    m = re.search(r"\{\s*\"numTotalTestSuites\"", text)
    if not m:
        return None
    try:
        data, _end = json.JSONDecoder().raw_decode(text[m.start():])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def summarize_vitest(data):
    """{文件名: ({分组名: {passed, bad}}, 收集错误)}，分组名是最外层 describe 的名字。"""
    files = {}
    for result in data.get("testResults", []):
        name = Path(str(result.get("name", ""))).name
        groups, errors = {}, []
        items = result.get("assertionResults") or []
        if not items and result.get("status") == "failed":
            errors.append((result.get("message") or "")[:1500])
        for item in items:
            ancestors = item.get("ancestorTitles") or []
            group = groups.setdefault(ancestors[0] if ancestors else "", {"passed": 0, "bad": []})
            if item.get("status") == "passed":
                group["passed"] += 1
            else:
                group["bad"].append((item.get("title"), item.get("status"),
                                     "\n".join(item.get("failureMessages") or [])[:700]))
        files[name] = (groups, errors)
    return files


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
        self.stopped_reason = ""
        self.probe_file = ""
        self.probe_summary = {}
        self.probe_unparsed = ""
        self.gate_probe_left = None


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


def _run_capture(argv, cwd, timeout, env):
    start = time.monotonic()
    try:
        proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout)
        out = (proc.stdout or b"") + (proc.stderr or b"")
        return proc.returncode, False, out.decode("utf-8", "replace"), time.monotonic() - start
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"") + (exc.stderr or b"")
        return 124, True, out.decode("utf-8", "replace"), time.monotonic() - start


PROBE_PAGE = r"""
import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

// 每个用例之间清场：地址、挂载、桩缓存、假计时器（探针自带全部辅助函数）
async function drainNav() {
  for (let i = 0; i < 2; i += 1) {
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  }
}
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
  }
  vi.useRealTimers();
  window.location.hash = '';
  document.documentElement.removeAttribute('data-theme');
  await drainNav();
});

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) {
      await Promise.resolve();
    }
  });
}
function advance(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}
function textOf(el: Element | null): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function allBtns(root: ParentNode = document): HTMLButtonElement[] {
  return Array.from(root.querySelectorAll('button')) as HTMLButtonElement[];
}
function btns(root: ParentNode, text: string): HTMLButtonElement[] {
  return allBtns(root).filter((b) => textOf(b) === text);
}
function btn(root: ParentNode, text: string): HTMLButtonElement {
  const hit = btns(root, text)[0];
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
function pathOf(hash: string): string {
  const i = hash.indexOf('?');
  return i < 0 ? hash : hash.slice(0, i);
}
async function grabShell(hash: string, def: string = 'ready'): Promise<any> {
  window.location.hash = hash;
  const ctx: any = await import('../src/shellpages/shellContext');
  let got: any = null;
  function Grab() {
    got = ctx.useThemisShell(def);
    return null;
  }
  const r = render(<Grab />);
  r.unmount();
  expect(got, 'useThemisShell 应返回桩实例').toBeTruthy();
  return got;
}
const METHODS = ['getState', 'pickRepo', 'pickPython', 'pickKit', 'pickTranscriptDir', 'saveSettings', 'startService', 'restartService', 'openExternal', 'on'];
function spyAll(shell: any): Record<string, any> {
  const out: Record<string, any> = {};
  for (const m of METHODS) {
    out[m] = vi.spyOn(shell, m);
  }
  return out;
}
function origOf(shell: any): Record<string, any> {
  const out: Record<string, any> = {};
  for (const m of METHODS) {
    out[m] = shell[m].bind(shell);
  }
  return out;
}
function svcOf(p: any): any {
  return p && p.service && typeof p.service === 'object' ? p.service : p;
}
const SVC = ['idle', 'starting', 'running', 'exited'];
function kindOf(p: any): string {
  const s = svcOf(p);
  if (!s || typeof s !== 'object') return '';
  for (const k of ['kind', 'status', 'state', 'phase', 'type']) {
    if (typeof s[k] === 'string' && SVC.includes(s[k])) return s[k];
  }
  return '';
}
function pad(n: number): string {
  return String(n).padStart(2, '0');
}
function clock(at: any): string {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? '' : pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
}
function exitCodeEl(): HTMLElement {
  const el = document.querySelector('[data-exit-code]');
  expect(el, '应有带 data-exit-code 的元素').not.toBeNull();
  return el as HTMLElement;
}
function body(): string {
  return textOf(document.body);
}
function h1s(): string[] {
  return Array.from(document.querySelectorAll('h1')).map((h) => textOf(h));
}
// 打开服务状态页；exit-N 场景若缺省不是 exited，先用 restartService 把桩推到 exited（再挂载）
async function openService(scn: string, extra: string = '', prepare?: (shell: any, spies: Record<string, any>, orig: Record<string, any>) => void) {
  vi.useFakeTimers();
  const hash = '#/service-status?shell=' + scn + extra;
  const shell = await grabShell(hash);
  let state = await shell.getState();
  if (kindOf(state) !== 'exited' && scn !== 'ready') {
    await shell.restartService();
    vi.advanceTimersByTime(1500);
    state = await shell.getState();
  }
  const orig = origOf(shell);
  const spies = spyAll(shell);
  if (prepare) prepare(shell, spies, orig);
  const r = await mountApp(hash);
  return { shell, spies, state, unmount: r.unmount };
}

describe('T039 stoppedNote 的第二实参', () => {
  it('afterRunning 为真一律「本机服务意外退出」，为假照旧按码：1 已经打开、2 文件不完整、其他意外退出', async () => {
    const codes: any = await import('../src/shellpages/exitCodes');
    expect(codes.stoppedNote(1)).toBe('这个仓库已经在另一个窗口里打开了。');
    expect(codes.stoppedNote(2)).toBe('应用文件不完整，请重新安装。');
    expect(codes.stoppedNote(0)).toBe('本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。');
    expect(codes.stoppedNote(3)).toBe('本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。');
    expect(codes.stoppedNote(1, true)).toBe('本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。');
    expect(codes.stoppedNote(2, true)).toBe('本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。');
    expect(codes.stoppedNote(3, true)).toBe('本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。');
  });

  it('firstRunHeadline 照旧只按码（首启第 4 步不读 afterRunning）', async () => {
    const codes: any = await import('../src/shellpages/exitCodes');
    expect(codes.firstRunHeadline(1)).toBe('这个仓库已经在另一个窗口里打开了。');
    expect(codes.firstRunHeadline(2)).toBe('应用文件不完整，请重新安装。');
    expect(codes.firstRunHeadline(3)).toBe('本机服务没能启动（退出码 3）。');
  });
});

describe('T039 crash-1 初始说明', () => {
  it('crash-1：h1、data-exit-code=1、退出码行照旧；说明是「本机服务意外退出」且不含「已经在另一个窗口里打开」；按钮照旧、不设 role=alert', async () => {
    const { state, unmount } = await openService('crash-1');
    const svc = svcOf(state);
    expect(kindOf(state), '夹具自检：crash-1 的 base 是 exited').toBe('exited');
    expect(svc.exitCode, '夹具自检：退出码 1').toBe(1);
    expect(svc.afterRunning, '夹具自检：带 afterRunning: true').toBe(true);
    expect(h1s()).toEqual(['本机服务已停止']);
    expect(textOf(exitCodeEl())).toBe('1');
    expect(exitCodeEl().tagName.toLowerCase(), '退出码放在 code 元素里').toBe('code');
    const at = svc.at;
    const clk = clock(at);
    if (clk) {
      expect(body()).toContain('退出码 1 · ' + clk + '。重启后会重新读取数据。');
    } else {
      expect(body()).toMatch(new RegExp('退出码 1 · \\d\\d:\\d\\d:\\d\\d。重启后会重新读取数据。'));
    }
    expect(body(), '跑起来之后才退出的退出码 1：说明是意外退出').toContain('本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。');
    expect(body(), '不许再按码套「已经打开」').not.toContain('这个仓库已经在另一个窗口里打开了。');
    expect(document.querySelector('svg[width="32"][aria-hidden="true"]'), 'ServerCrashIcon 32，aria-hidden').not.toBeNull();
    expect(btns(document, '重启服务').length).toBe(1);
    expect(btns(document, '打开设置').length).toBe(1);
    expect(btn(document, '重启服务').disabled).toBe(false);
    expect(document.querySelectorAll('[role="alert"]').length, '不设 role=alert').toBe(0);
    expect(document.title).toBe('本机服务已停止 · Themis Tally');
    unmount();
  });
});

describe('T039 exit-1 启动阶段说明', () => {
  it('exit-1（重启之后的启动阶段退出 1，不带键）：说明仍是「这个仓库已经在另一个窗口里打开了。」', async () => {
    const { state, unmount } = await openService('exit-1');
    const svc = svcOf(state);
    expect(kindOf(state)).toBe('exited');
    expect(svc.exitCode).toBe(1);
    expect('afterRunning' in svc, '桩在重启之后发的 exited 不带键（shellStub 一个字不改）').toBe(false);
    expect(textOf(exitCodeEl())).toBe('1');
    expect(body(), '不带键的退出码 1 照旧是「已经打开」').toContain('这个仓库已经在另一个窗口里打开了。');
    expect(body()).not.toContain('本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。');
    unmount();
  });
});

describe('T039 crash-1 重启后换说明', () => {
  it('点「重启服务」：1500ms 后说明换成「已经在另一个窗口里打开」，退出码仍是 1、地址仍在 #/service-status、按钮恢复', async () => {
    const { spies, unmount } = await openService('crash-1');
    expect(body()).toContain('本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。');
    fireEvent.click(btn(document, '重启服务'));
    await settle();
    expect(spies.restartService.mock.calls.length, '只调一次 restartService').toBe(1);
    advance(1499);
    await settle();
    expect(body(), '1499ms 时说明还没换').not.toContain('这个仓库已经在另一个窗口里打开了。');
    advance(1);
    await settle();
    expect(body(), '1500ms 收到不带键的 exited 1：说明换成「已经打开」').toContain('这个仓库已经在另一个窗口里打开了。');
    expect(body()).not.toContain('本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。');
    expect(textOf(exitCodeEl()), '退出码仍是真实的 1').toBe('1');
    expect(body()).toMatch(new RegExp('退出码 1 · \\d\\d:\\d\\d:\\d\\d。重启后会重新读取数据。'));
    expect(pathOf(window.location.hash), '没收到 running 之前不跳走').toBe('#/service-status');
    expect(btn(document, '重启服务').disabled, '按钮恢复可用').toBe(false);
    expect(spies.restartService.mock.calls.length, '重启后不自动再点').toBe(1);
    unmount();
  });
});
"""


@pytest.fixture(scope="session")
def pipeline():
    """页面探针的流水线：只写一份探针文件并跑 ``npm test -- <探针>``。

    基线自检（门禁战前回合）**不装依赖**：``desktop/web/node_modules`` 里没有 vitest 时直接给
    说明返回，不调 npm；执行端按合同 Setup（S01 npm ci）装好依赖后本夹具才真正跑探针。探针
    文件写在 ``desktop/web/gate-probe/`` 下（vite.config.ts 的 vitest include 覆盖它），
    ``finally`` 里删除。
    """
    pipe = Pipeline()
    npm = shutil.which("npm")
    if not npm:
        pipe.reason = "找不到 npm（shutil.which）"
        return pipe
    if not (WEB / "node_modules" / "vitest").is_dir():
        pipe.reason = ("desktop/web/node_modules 里没有 vitest（依赖未装）：战前门禁自检不装依赖；"
                       "执行端按合同 Setup（S01 npm ci）装好依赖后，本组用例才运行页面探针")
        return pipe
    pipe.ran = True
    env = _make_env()
    probe_dir = WEB / "gate-probe"
    written = []
    try:
        uid = uuid.uuid4().hex[:12]
        probe_dir.mkdir(exist_ok=True)
        probe_name = f"probe-t039-{uid}.test.tsx"
        result_name = f"result-t039-{uid}.json"
        probe_path = probe_dir / probe_name
        result_path = probe_dir / result_name
        written += [probe_path, result_path]
        probe_path.write_text(PROBE_PAGE, encoding="utf-8", newline="\n")
        code, timed_out, out, seconds = _run_capture(
            [npm, "test", "--", f"gate-probe/{probe_name}", "--reporter=json",
             f"--outputFile=gate-probe/{result_name}", "--testTimeout=60000"],
            str(WEB), 300, env)
        pipe.steps["probe"] = Step("probe", ["npm", "test", "--", f"gate-probe/{probe_name}"], code, timed_out, out, seconds)
        pipe.probe_file = probe_name
        data = None
        if result_path.is_file():
            try:
                data = json.loads(result_path.read_text(encoding="utf-8"))
            except ValueError:
                data = None
        if data is None:
            data = parse_vitest_json(out)
        if data is None:
            pipe.probe_unparsed = tail_text(out)
        else:
            pipe.probe_summary = summarize_vitest(data)
    finally:
        for p in written:
            try:
                p.unlink()
            except FileNotFoundError:
                pass
        try:
            probe_dir.rmdir()
        except OSError:
            pass
        pipe.gate_probe_left = probe_dir.exists()
    return pipe


def _assert_probe_group(pipe, group):
    assert pipe.ran, pipe.reason
    step = pipe.steps.get("probe")
    assert step is not None, f"探针未运行：{pipe.stopped_reason or pipe.reason}"
    assert not step.timed_out, f"探针超时被杀，用时 {step.seconds:.0f}s\n{step.tail}"
    assert pipe.probe_summary, f"探针的输出里找不到 Vitest 的 JSON：\n{pipe.probe_unparsed or step.tail}"
    assert pipe.probe_file in pipe.probe_summary, (
        f"Vitest 的结果里没有探针文件 {pipe.probe_file}：{sorted(pipe.probe_summary)}\n{step.tail}")
    groups, errors = pipe.probe_summary[pipe.probe_file]
    assert not errors, "探针收集失败（导入或语法错误）：\n" + "\n".join(errors)
    want = probe_groups(PROBE_PAGE)[group]
    got = groups.get(group)
    assert got is not None, f"探针的输出里没有分组「{group}」：{sorted(groups)}"
    assert not got["bad"], f"「{group}」有 {len(got['bad'])} 条没通过：\n" + "\n".join(
        f"- [{status}] {title}\n{msg}" for title, status, msg in got["bad"][:6])
    assert got["passed"] == want, f"「{group}」应有 {want} 条通过，实际 {got['passed']}"


def _stopped_note_has_second_param():
    text = _need_text(EXITCODES_REL)
    return re.search(r"export\s+function\s+stoppedNote\s*\(\s*code:\s*number\s*,\s*afterRunning\s*=\s*false\s*\)\s*:\s*string", text)


def test_f01_stopped_note_after_running(pipeline):
    """F01/D02：stoppedNote(code, afterRunning)——为真一律「本机服务意外退出」，为假照旧按码；
    firstRunHeadline 只按码（首启第 4 步不变）。"""
    assert _stopped_note_has_second_param(), (
        "基线上 stoppedNote 还没有第二实参（合同三：跑起来之后的退出码 1 要给「意外退出」那句）"
    )
    _assert_probe_group(pipeline, "T039 stoppedNote 的第二实参")


def test_f02_crash1_initial_note(pipeline):
    """F02/D02/D04：crash-1 初始说明——退出码 1 + afterRunning: true 时一律「本机服务意外退出」，
    不含「已经在另一个窗口里打开」；退出码行、h1、按钮、title、不设 role=alert 照旧。"""
    text = _need_text(SCENARIOS_REL)
    assert re.search(r"'crash-1':\s*\{", text), (
        "基线上夹具还没有 crash-1 场景（合同六：跑起来之后退出、退出码 1 的演示场景）"
    )
    assert "afterRunning: true" in _sub_block(_scenario_block(text, "crash-1"), "service"), (
        "crash-1 的 base.service 要带 afterRunning: true"
    )
    _assert_probe_group(pipeline, "T039 crash-1 初始说明")


def test_f03_exit1_startup_phase_note(pipeline):
    """F03/D04：exit-1（不带键的退出码 1）说明仍是「已经在另一个窗口里打开了。」——退出码 1 的
    另一种含义不许被本片误伤。"""
    assert _stopped_note_has_second_param(), (
        "基线上 stoppedNote 还没有第二实参（不带键的退出码 1 要照旧给「已经打开」，先看合同三落地）"
    )
    _assert_probe_group(pipeline, "T039 exit-1 启动阶段说明")


def test_f04_crash1_restart_switches_note(pipeline):
    """F04/D04：crash-1 点「重启服务」——1500ms 后（不带键的 exited 1）说明换成「已经打开」，
    退出码仍是 1、地址仍在 #/service-status、按钮恢复可用。"""
    text = _need_text(SCENARIOS_REL)
    assert re.search(r"'crash-1':\s*\{", text), "基线上夹具还没有 crash-1 场景"
    st = _sub_block(_scenario_block(text, "crash-1"), "start")
    assert "exitCode: 1" in st and "afterRunning" not in st, (
        "crash-1 的 start 是 exited 1 不带键（同一页演示重启 1500ms 后换说明）"
    )
    _assert_probe_group(pipeline, "T039 crash-1 重启后换说明")
