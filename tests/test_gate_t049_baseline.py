"""T049 战前门禁：桌面端前端第 13 片「CLI 运行时页没登记运行时也显示 Quizs 一块；初始窗口标题改成应用名」
的黑盒基准测试（合同 t049-desktop-web-runtimes-empty-quizs.v1，基线 618196a2ef607174e4a242fbb422b73d49a9aa91）。

被测对象是 ``desktop/web/`` 前端：

- ``src/pages/RuntimesPage.tsx``：仍照传 ``isEmpty={isRuntimesEmpty}``（空态下 ``data-page-state`` 仍是
  ``empty``），但不再给 PageFrame 传 ``empty`` 属性——空态由 children 自己摆：``isRuntimesEmpty(data)``
  真时先 ``EmptyState``（标题「还没有登记的 runtime」与 T041 的说明原文）再 ``QuizsBlock``（直接挂在
  ``.tt-page`` 下、在视图根之外），假时照旧 ``RuntimesView``。children 仍逐字以 ``{(data, reload) =>`` 开头、
  ``reload={reload}`` 仍在、load/isEmpty 仍是命名的模块级函数、``isRuntimesEmpty`` 仍是一行只看 runtimes
  长度、不掺 quizs。
- ``index.html``：初始标题逐字 ``<title>Themis Tally</title>``（文件里不再有「组件陈列」）；其余一个字不动。
- 执行端新测试 ``tests/page-runtimes-empty.test.tsx`` 按合同第 4 步覆盖 (a)–(f)；``tests/page-quizs.test.tsx``
  只改「?mock=loading / ?mock=empty」那一个 it（去掉与新行为相反的提示语、加 frame 里有 Quizs 区块的断言）。

基线（618196a2）上标题还是「Themis Tally · 组件陈列」、RuntimesPage 还传着 ``empty={{…}}``、空态没有 Quizs
一块、新测试文件不存在，所以失败都落在断言上（静态 S01/S02/S04；流水线候选里还没有新测试文件时不调 npm，
P/D 用例以「流水线未运行」的断言失败），不是收集失败：模块级只导入标准库，仓库文件的读取都发生在用例函数
里；流水线（npm、Vitest、探针）放在 ``pipeline`` 会话级夹具里（全量 pytest 默认跳过，点名运行本文件才跑；
照 T024/T040/T041/T043 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：index.html 的标题与不动面（S01）；RuntimesPage 的
  空态接法与长期红线（S02）；package.json 与锁文件按基线字节冻结（S03）；执行端新测试在位且要点齐备、
  page-quizs 只改那一个 it（S04）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、``npm test``
  全绿（含执行端新测试）；两份探针逐份写成 ``gate-probe/probe-<uid>-t049-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除。探针挂整个 App（不 mock 组件、不 mock api）：
  桩模式用 ``?mock=``/``?quizs=`` 选情景，注入用 ``setLiveClientForTests``（应用自己的测试缝，
  page-quizs.test.tsx 同款）。
  - empty（D01、D02、D04、D05、D08）：?mock=empty 空态（页面状态 empty、标题与说明原文、EmptyState 与
    Quizs 区块都直接挂在 .tt-page 下、两张表各 2 行、没有页面级出错块、页头三钮次序与 [手动登记…] 可点）；
    ?mock=empty&quizs=broken（状态仍 empty、区块里「Quizs 跑不起来」与逐套「读不出」、页面级不出错块）；
    注入替身（runtimes 空数组 + providers 失败）；先空后有（点 [刷新] 之后 data 态、视图根出现、Quizs
    区块进视图根内）。
  - states（D03、D06、D08）：?mock=loading / ?mock=error 没有 Quizs 区块；有 runtime 时页面照旧（视图根内
    三节次序、Quizs 区块在视图根内、页头三钮）；挂载后 document.title 仍由 App 按页面改写。

门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：见文件末尾 ``ASSUMPTIONS``。
"""

import hashlib
import os
import re
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB = REPO_ROOT / "desktop" / "web"
WEB_REL = "desktop/web"
SRC_REL = f"{WEB_REL}/src"
TESTS_REL = f"{WEB_REL}/tests"

RUNTIMESPAGE_REL = f"{SRC_REL}/pages/RuntimesPage.tsx"
INDEX_HTML_REL = f"{WEB_REL}/index.html"
PAGE_QUIZS_TEST_REL = f"{TESTS_REL}/page-quizs.test.tsx"
EMPTY_TEST_REL = f"{TESTS_REL}/page-runtimes-empty.test.tsx"

# T041 定下的两段空态文字（t041 S05 / t043 S03 按本文件文本查；合同 D01、D07）
EMPTY_TITLE = "还没有登记的 runtime"
EMPTY_DESC = "用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）"

# 入口文件（RuntimesPage.tsx）不许出现的文字（t041 :127-134 的 BAD_ENTRY_TEXTS；本片照抄，D07）
BAD_ENTRY_TEXTS = (
    "已登记运行时", "已登记表里加上", "；命令写进本机文件", "已登记为",
    "ERROR: runtime", "改 adapter 要加",
    "只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符",
    "命令要写成 JSON 字符串数组",
    "JSON 字符串数组，第一项写命令的绝对路径",
    "登记运行时 ${",
)

# 依赖冻结（合同 D10：package.json 与锁文件不变；行尾归一 LF 后的字节数与 sha256，与 t043 S09 同一基线值）
BASELINE_DIGESTS = {
    f"{WEB_REL}/package.json": (820, "094d3622e54097e0f50f0ab2a71a5caa22491dba9d3ac6ef83047426f8c57f5a"),
    f"{WEB_REL}/package-lock.json": (108793, "1bc4e1fbfeb02a17280d0de1d98a5f3b2721fa91229c271c66d590d059d82d28"),
}

# 执行端新测试 page-runtimes-empty.test.tsx 的最小覆盖记号（合同第 4 步 (a)–(f)）
EXECUTOR_TEST_TOKENS = (
    "mock=empty", "quizs=broken", EMPTY_TITLE, EMPTY_DESC,
    "Quizs 提供方档案", "Quizs live 套", "Quizs 跑不起来", "读不出",
    "setLiveClientForTests", "刷新", "mock=loading", "mock=error",
    "readFileSync", "Themis Tally", 'data-page="runtimes"',
)

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T024/T041/T043 门禁），用完就停下并在断言里写明。
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 120}

ASSUMPTIONS = (
    "「Quizs 区块直接挂在 .tt-page 下」按最直接的 DOM 关系断言：区块与 EmptyState 的 parentElement 就是"
    " .tt-page 那一层（合同第 4 步 (a) 的「直接挂在 .tt-page 下面」）；候选若在空态包了别的容器，视为不合规",
    "「有 runtime 时页面逐字不变」在行为面钉：data 态、视图根内三节次序（已登记、就绪检查在前，Quizs 在"
    " 就绪检查之后）、页头三钮文案与 [扫描 PATH] 禁用；逐字的 DOM 快照没法在探针里写，静态字面由 t009/t041/"
    "t043 的既有门禁继续负责",
    "index.html 的标题断言逐字钉 <title>Themis Tally</title> 且全文无「组件陈列」；document.title 的运行时"
    "改写（「CLI 运行时 · Themis Tally」）由 states 探针钉住",
    "page-quizs.test.tsx 只要求两件事：与新行为相反的提示语「Quizs 一块也就看不到」不在了、frame 里有"
    " Quizs 区块的新断言在（sectionNamed(frame(), 'Quizs')，合同第 5 步）；loading/empty 两半的既有记号"
    " 仍在；其余由 t043 S08 的记号表继续负责",
    "流水线预算 580 秒（G01 的 600 秒减去静态用例与 pytest 自身开销）：node_modules 已在（执行端 Setup "
    "装过）就不重装；npm ci 只在依赖不齐时跑",
)


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


def file_digest(path):
    path = Path(path)
    if not path.is_file():
        return None
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return len(data), hashlib.sha256(data).hexdigest()


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:40])


def tail_text(text, max_chars=3500, max_lines=45):
    text = _ANSI.sub("", text)
    lines = text.splitlines()[-max_lines:]
    joined = "\n".join(lines)
    return joined[-max_chars:]


def network_hint(text):
    if re.search(r"ENOTFOUND|ETIMEDOUT|ECONNRESET|ECONNREFUSED|EAI_AGAIN|ENETUNREACH|network|socket hang up|E40[134]|E50\d",
                 text, re.I):
        return "（输出里有网络或 registry 错误的迹象，多半是网络故障，不是代码问题）"
    return ""


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043 的同一口径）。
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def _statement(text, start_marker):
    """从 start_marker 起取「一条声明」：到第一个分号，或到下一条 const/function/export 声明为止
    （t043 :276-292 的切片口径：isRuntimesEmpty 必须是一行并以 ; 收尾，否则会误吞 JSX）。"""
    start = text.find(start_marker)
    if start < 0:
        return ""
    rest = text[start:]
    cut = len(rest)
    semicolon = rest.find(";")
    if 0 <= semicolon < cut:
        cut = semicolon + 1
    for marker in ("\nconst ", "\nfunction ", "\nexport ", "\nlet "):
        at = rest.find(marker, len(start_marker))
        if 0 <= at < cut:
            cut = at
    return rest[:cut]


def _no_skip_marks(text):
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
        if re.search(bad, text):
            problems.append(f"出现 {bad}（不许 skip、only、todo）")
    return problems


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_index_html_title():
    """S01 / D06：index.html 的初始标题逐字是 <title>Themis Tally</title>，文件里不再有「组件陈列」；
    其余（lang、charset、viewport、#root、入口脚本）一个字不动。"""
    need_file(INDEX_HTML_REL)
    text = read_rel(INDEX_HTML_REL)
    assert "<title>Themis Tally</title>" in text, \
        "index.html 的初始标题应逐字是 <title>Themis Tally</title>（基线上还是「Themis Tally · 组件陈列」）"
    assert "组件陈列" not in text, "index.html 里不应再有「组件陈列」（加载那一下不再闪出陈列页标题）"
    for anchor in ('<html lang="zh-CN">', '<meta charset="UTF-8" />',
                   '<meta name="viewport" content="width=device-width, initial-scale=1.0" />',
                   '<div id="root"></div>', '<script type="module" src="/src/main.tsx"></script>'):
        assert anchor in text, f"index.html 的既有行应一字不动（看不到 {anchor}）"


def test_s02_runtimes_page_empty_branch():
    """S02 / D01、D04、D05、D07：RuntimesPage 仍照传 isEmpty（空态 data-page-state 仍是 empty）但不再给
    PageFrame 传 empty 属性；children 在空时自己摆 EmptyState（两段文字逐字）与 QuizsBlock（EmptyState 在前）；
    长期红线（命名的模块级 load/isEmpty、一行式 isRuntimesEmpty 只看长度不掺 quizs、children 前缀、
    reload={reload}、页头两钮、t041 禁字表）一条不破。"""
    need_file(RUNTIMESPAGE_REL)
    text = read_rel(RUNTIMESPAGE_REL)
    code = strip_ts_comments(text)
    problems = []
    # 不再传 empty 属性（PageFrame 在 empty 态没接到 empty 就渲染 children——这条分支由探针在 App 级钉住）
    if re.search(r"\bempty\s*=\s*[<{\"']", code):
        problems.append("RuntimesPage 不应再给 PageFrame 传 empty 属性（空态由 children 自己摆）")
    if "isEmpty={isRuntimesEmpty}" not in code:
        problems.append("仍应照传 isEmpty={isRuntimesEmpty}（空态下 data-page-state 仍是 empty）")
    for name in ("loadRuntimes", "isRuntimesEmpty"):
        if not re.search(rf"^const {name} = ", code, re.M):
            problems.append(f"{name} 应仍是命名的模块级 const（t009 :876-883）")
    empty_fn = _statement(code, "const isRuntimesEmpty")
    if not empty_fn:
        problems.append("找不到 isRuntimesEmpty 的声明")
    else:
        if "runtimes.length" not in empty_fn:
            problems.append("isRuntimesEmpty 仍只看 runtimes.length")
        if "quizs" in empty_fn:
            problems.append("isRuntimesEmpty 不应掺 quizs（t043 S03）")
        if not empty_fn.rstrip().endswith(";"):
            problems.append("isRuntimesEmpty 应仍以 ; 收尾（t043 _statement 的切片口径）")
        if "\n" in empty_fn.strip():
            problems.append("isRuntimesEmpty 应仍是一行 const（t043 S03）")
    # children 前缀与两支
    if not re.search(r"\{\(data, reload\)\s*=>", code):
        problems.append("children 应逐字以 {(data, reload) => 开头（t043 :463 的正则）")
    for needle, why in (
        ("isRuntimesEmpty(data)", "children 应按 isRuntimesEmpty(data) 分空态与 data 态"),
        ("<EmptyState", "空态应由本页自己摆 EmptyState"),
        (f'title="{EMPTY_TITLE}"', "EmptyState 的标题逐字"),
        (f'description="{EMPTY_DESC}"', "EmptyState 的说明逐字（T041 的原文）"),
        ("<QuizsBlock", "空态应摆 QuizsBlock（Quizs 一块）"),
        ("quizs={data.quizs}", "QuizsBlock 应收 data.quizs"),
        ("<RuntimesView", "非空态照旧渲染 RuntimesView"),
        ("reload={reload}", "reload={reload} 应保留（t023 :328）"),
    ):
        if needle not in code:
            problems.append(f"{why}（看不到 {needle[:44]}）")
    if "<EmptyState" in code and "<QuizsBlock" in code and code.index("<EmptyState") > code.index("<QuizsBlock"):
        problems.append("空态里 EmptyState 应在 QuizsBlock 之前（合同：EmptyState → Quizs）")
    # 引入（EmptyState 照 PageFrame.tsx:6 的引法；QuizsBlock 从 readonly1）
    if not re.search(r"import\s*\{[^}]*EmptyState[^}]*\}\s*from\s*['\"]\.\./components['\"]", code):
        problems.append("EmptyState 应从 '../components' 引入")
    if "from './readonly1/runtimes-QuizsBlock'" not in code and 'from "./readonly1/runtimes-QuizsBlock"' not in code:
        problems.append("QuizsBlock 应从 './readonly1/runtimes-QuizsBlock' 引入")
    # 页头两钮仍在（空态下 [手动登记…] 照样能用）
    if '<DisabledAction label="扫描 PATH"' not in code:
        problems.append("[扫描 PATH] 应照旧是 DisabledAction")
    if "<AddRuntimeAction reload={reload}" not in code:
        problems.append("页头 [手动登记…]（AddRuntimeAction reload={reload}）应保留")
    # 禁字表（t041）与「登记 runtime」
    for frag in BAD_ENTRY_TEXTS:
        if frag in text:
            problems.append(f"RuntimesPage.tsx 出现「{frag}」（t041 的禁字表）")
    if "登记 runtime" in text:
        problems.append("RuntimesPage.tsx 出现「登记 runtime」（T013 D02）")
    # 不加 CSS（间距靠 .tt-page 自己的 gap）
    if ".css" in code:
        problems.append("RuntimesPage 不应引新的 CSS（空态不加任何样式）")
    fail_if(problems, "RuntimesPage 的空态接法（S02）")


def test_s03_dependency_freeze():
    """S03 / D10：package.json 与 package-lock.json 按基线字节冻结（依赖不增不减；与 t043 S09 同一基线值）。"""
    for rel, want in BASELINE_DIGESTS.items():
        got = file_digest(REPO_ROOT / rel)
        assert got == want, f"{rel} 与基线不一致（依赖文件不许动）：基线 {want}，实际 {got}"


def test_s04_executor_tests():
    """S04 / D08、D09：新测试 page-runtimes-empty.test.tsx 在位且覆盖记号齐备（?mock=empty、
    ?quizs=broken、注入替身、先空后有、loading/error、读 index.html 的标题）；page-quizs.test.tsx 只改那
    一个 it——与新行为相反的提示语「Quizs 一块也就看不到」不在了、加上了 frame 里有 Quizs 区块的断言；
    两个文件都没有 skip/only/todo。"""
    need_file(EMPTY_TEST_REL)
    fresh = read_rel(EMPTY_TEST_REL)
    problems = [f"page-runtimes-empty.test.tsx 应覆盖 {token}" for token in EXECUTOR_TEST_TOKENS if token not in fresh]
    problems += _no_skip_marks(strip_ts_comments(fresh))
    need_file(PAGE_QUIZS_TEST_REL)
    quizs = read_rel(PAGE_QUIZS_TEST_REL)
    if "Quizs 一块也就看不到" in quizs:
        problems.append("page-quizs.test.tsx 的提示语「Quizs 一块也就看不到」与新行为相反，应改写")
    if "sectionNamed(frame(), 'Quizs')" not in quizs:
        problems.append("page-quizs.test.tsx 那个 it 应加 frame 里有 Quizs 区块的断言（sectionNamed(frame(), 'Quizs')）")
    for token in ("mock=loading", "mock=empty"):
        if token not in quizs:
            problems.append(f"page-quizs.test.tsx 的既有两半（{token}）应保留")
    problems += _no_skip_marks(strip_ts_comments(quizs))
    fail_if(problems, "执行端测试（S04）")


# ---------------------------------------------------------------------------
# 探针源码（每份自包含：辅助函数不跨文件共享；照 t043 PRELUDE 与 page-quizs.test.tsx 的已知好写法）
# ---------------------------------------------------------------------------

PRELUDE = r"""
import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

async function drain() {
  for (let i = 0; i < 2; i += 1) {
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  }
}
beforeEach(async () => {
  window.location.hash = '';
  await drain();
});
afterEach(async () => {
  cleanup();
  window.location.hash = '';
  await drain();
});
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) {
      await Promise.resolve();
    }
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    for (let i = 0; i < 12; i += 1) {
      await Promise.resolve();
    }
  });
}
function textOf(el: Element | null | undefined): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function qa(root: ParentNode, sel: string): Element[] {
  return Array.from(root.querySelectorAll(sel));
}
function sectionTitle(sec: Element): string {
  const id = sec.getAttribute('aria-labelledby');
  return textOf(id ? document.getElementById(id) : null);
}
function sectionNamed(root: ParentNode, title: string): Element | null {
  return qa(root, 'section').find((s) => sectionTitle(s) === title) || null;
}
function frame(): HTMLElement | null {
  return document.querySelector('[data-page-state]');
}
function needFrame(): HTMLElement {
  const f = frame();
  expect(f, '应有 [data-page-state] 的页面框架').toBeTruthy();
  return f as HTMLElement;
}
function pageRoot(): HTMLElement | null {
  return document.querySelector('[data-page="runtimes"]');
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
function tableOf(root: ParentNode, label: string): HTMLTableElement {
  const t = root.querySelector('table[aria-label="' + label + '"]');
  expect(t, '应有表 aria-label=' + label).toBeTruthy();
  return t as HTMLTableElement;
}
function rowsOf(table: Element): Array<Record<string, Element>> {
  const heads = qa(table, 'thead th').map(textOf);
  return qa(table, 'tbody tr').map((tr) => {
    const o: Record<string, Element> = {};
    qa(tr, 'td').forEach((td, i) => {
      o[heads[i] as string] = td;
    });
    return o;
  });
}
function headerButtons(root: ParentNode): Element[] {
  const bar = root.querySelector('.tt-page__actions');
  expect(bar, '应有 .tt-page__actions 页头操作区').toBeTruthy();
  return qa(bar as ParentNode, 'button');
}
function quizsSectionIn(root: ParentNode): Element {
  const sec = sectionNamed(root, 'Quizs');
  expect(sec, '应有「Quizs」区块').toBeTruthy();
  return sec as Element;
}
"""

# empty 探针：空态也摆 Quizs 一块；失败只写在区块里；空态不是死路（合同 D01、D02、D04、D05、D08）
PROBE_EMPTY = PRELUDE + r"""
import { setLiveClientForTests } from '../src/live/mode';

afterEach(() => {
  setLiveClientForTests(undefined);
});

const EMPTY_TITLE = '还没有登记的 runtime';
const EMPTY_DESC = '用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）';
const RUNTIMES_ONE = { runtimes: [{ id: 'pi', adapter: 'pi', source: 'env', command: ['pi'], notes: [] }] };

function envelope(data: unknown, command: string[], ok = true, exitCode: number | null = 0, messages: string[] = []): any {
  return { ok, exit_code: exitCode, data, output: [], messages, command, elapsed_ms: 0 };
}
// 替身 client：page-quizs.test.tsx 的 clientWith 同款——注入后真实模式生效，?mock= 与 ?quizs= 都不再起作用。
function injectLive(over: Record<string, () => Promise<any>>) {
  const client = {
    get(path: string) {
      const hit = over[path];
      if (hit) return hit();
      return Promise.resolve(envelope(null, []));
    },
    post() { return Promise.resolve({ status: 200, body: envelope(null, []) }); },
    getRaw() { return Promise.resolve({ status: 200, body: null }); },
  };
  setLiveClientForTests(client as any);
}

describe('T049 空态也摆 Quizs 一块：?mock=empty', () => {
  it('空态：页面状态 empty、标题与说明原文、EmptyState 直接挂 .tt-page 下、没有页面级出错块', async () => {
    await mountApp('#/runtimes?mock=empty');
    const f = needFrame();
    expect(f.getAttribute('data-page-state')).toBe('empty');
    expect(pageRoot(), '空态不渲染视图根').toBeNull();
    expect(textOf(f.querySelector('.tt-empty__title'))).toBe(EMPTY_TITLE);
    expect(textOf(f.querySelector('.tt-empty__desc'))).toBe(EMPTY_DESC);
    const empty = f.querySelector('.tt-empty');
    expect(empty, 'EmptyState 的根 .tt-empty 应在').toBeTruthy();
    expect((empty as Element).parentElement === f, 'EmptyState 直接挂在 .tt-page 下（视图根之外）').toBe(true);
    expect(f.querySelector('.tt-page__error'), '空态不应有页面级出错块').toBeNull();
  });

  it('Quizs 一块在 frame 里、不在视图根内、直接挂 .tt-page 下；两张表各 2 行', async () => {
    await mountApp('#/runtimes?mock=empty');
    const f = needFrame();
    expect(f.getAttribute('data-page-state')).toBe('empty');
    const sec = quizsSectionIn(f);
    expect(sec.closest('[data-page="runtimes"]'), 'Quizs 区块不在视图根内（空态视图根是 null）').toBeNull();
    expect(sec.parentElement === f, 'Quizs 区块直接挂在 .tt-page 下').toBe(true);
    const pt = tableOf(sec, 'Quizs 提供方档案');
    expect(rowsOf(pt).length, '提供方档案表两行（ok 情景）').toBe(2);
    expect(textOf(pt)).toContain('stepfun');
    const lt = tableOf(sec, 'Quizs live 套');
    expect(rowsOf(lt).length, 'live 套表两行（ok 情景）').toBe(2);
    expect(textOf(lt)).toContain('就绪');
  });

  it('页头动作次序 [扫描 PATH][手动登记…][刷新]；空态下 [手动登记…] 可点', async () => {
    await mountApp('#/runtimes?mock=empty');
    const f = needFrame();
    const buttons = headerButtons(f);
    expect(buttons.map(textOf)).toEqual(['扫描 PATH', '手动登记…', '刷新']);
    expect((buttons[0] as HTMLButtonElement).disabled, '[扫描 PATH] 照旧禁用').toBe(true);
    expect((buttons[1] as HTMLButtonElement).disabled, '空态下 [手动登记…] 可点').toBe(false);
    expect(buttons[1].getAttribute('data-variant')).toBe('primary');
  });
});

describe('T049 空态下的 Quizs 失败只写在区块里', () => {
  it('?mock=empty&quizs=broken：状态仍 empty、标题与说明仍在；区块写「Quizs 跑不起来」，live 逐套「读不出」；没有页面级出错块', async () => {
    await mountApp('#/runtimes?mock=empty&quizs=broken');
    const f = needFrame();
    expect(f.getAttribute('data-page-state'), 'Quizs 坏不影响页面状态').toBe('empty');
    expect(pageRoot()).toBeNull();
    expect(textOf(f.querySelector('.tt-empty__title'))).toBe(EMPTY_TITLE);
    const sec = quizsSectionIn(f);
    const t = textOf(sec);
    expect(t).toContain('Quizs 跑不起来');
    expect(t).toContain('命令 config quizs providers --json 返回退出码 1');
    const lt = tableOf(sec, 'Quizs live 套');
    const rows = rowsOf(lt);
    expect(rows.length).toBe(2);
    rows.forEach((row) => {
      expect(textOf(row['状态'])).toBe('读不出');
      expect(textOf(row['下一步'])).toContain('看这一套自己的问题；quizs live status 失败（退出码 127）：');
    });
    expect(f.querySelector('.tt-page__error'), '读失败只写在区块里').toBeNull();
  });

  it('注入替身（runtimes 空数组、providers 失败退出码 3）：页面状态 empty，失败只在区块里', async () => {
    injectLive({
      '/api/v1/runtimes': () => Promise.resolve(envelope({ runtimes: [] }, ['config', 'runtime', 'list'])),
      '/api/v1/quizs/providers': () =>
        Promise.resolve(envelope(null, ['config', 'quizs', 'providers', '--json'], false, 3, ['E-GATE'])),
    });
    await mountApp('#/runtimes');
    const f = needFrame();
    expect(f.getAttribute('data-page-state')).toBe('empty');
    expect(pageRoot()).toBeNull();
    const sec = quizsSectionIn(f);
    expect(textOf(sec)).toContain('Quizs 跑不起来');
    expect(textOf(sec)).toContain('E-GATE');
    expect(f.querySelector('.tt-page__error'), 'providers 失败不整页出错').toBeNull();
  });
});

describe('T049 空态不是死路：重读之后按有运行时的样子显示', () => {
  it('runtimes 第一次空、第二次有一条：点 [刷新] 之后 data 态、视图根出现、Quizs 区块进视图根内', async () => {
    let reads = 0;
    injectLive({
      '/api/v1/runtimes': () => {
        reads += 1;
        return Promise.resolve(
          reads === 1
            ? envelope({ runtimes: [] }, ['config', 'runtime', 'list'])
            : envelope(RUNTIMES_ONE, ['config', 'runtime', 'list']),
        );
      },
    });
    await mountApp('#/runtimes');
    const f = needFrame();
    expect(f.getAttribute('data-page-state')).toBe('empty');
    expect(pageRoot()).toBeNull();
    quizsSectionIn(f);
    const refresh = headerButtons(f).find((b) => textOf(b) === '刷新');
    expect(refresh, '应有 [刷新] 钮').toBeTruthy();
    await act(async () => {
      fireEvent.click(refresh as Element);
    });
    await settle();
    expect(f.getAttribute('data-page-state'), '重读后按有运行时的样子显示').toBe('data');
    const root = pageRoot();
    expect(root, '重读后视图根出现').toBeTruthy();
    const sec = quizsSectionIn(root as ParentNode);
    expect(sec.closest('[data-page="runtimes"]'), '重读后 Quizs 区块在视图根内').toBe(root);
  });
});
"""

# states 探针：loading/error 没有 Quizs 一块；有 runtime 时页面照旧；document.title 的运行时改写（D03、D06、D08）
PROBE_STATES = PRELUDE + r"""
describe('T049 loading / error 态没有 Quizs 一块', () => {
  it('?mock=loading：整页挂起，没有 Quizs 一块', async () => {
    await mountApp('#/runtimes?mock=loading');
    const f = needFrame();
    expect(f.getAttribute('data-page-state')).toBe('loading');
    expect(pageRoot()).toBeNull();
    expect(sectionNamed(f, 'Quizs'), 'loading 态不应有 Quizs 一块').toBeNull();
  });

  it('?mock=error：整页出错（页面级出错块），没有 Quizs 一块', async () => {
    await mountApp('#/runtimes?mock=error');
    const f = needFrame();
    expect(f.getAttribute('data-page-state')).toBe('error');
    expect(f.querySelector('.tt-page__error'), '应有页面级出错块').toBeTruthy();
    expect(textOf(f)).toContain('没能读到数据');
    expect(pageRoot()).toBeNull();
    expect(sectionNamed(f, 'Quizs'), 'error 态不应有 Quizs 一块').toBeNull();
  });
});

describe('T049 有 runtime 时页面照旧', () => {
  it('data 态：视图根内「已登记」「就绪检查」在前、Quizs 在其后且在视图根内；页头三钮', async () => {
    await mountApp('#/runtimes');
    const f = needFrame();
    expect(f.getAttribute('data-page-state')).toBe('data');
    const root = pageRoot();
    expect(root, '有 runtime 时视图根应渲染').toBeTruthy();
    const titles = qa(root as ParentNode, 'section').map(sectionTitle);
    expect(titles.slice(0, 2)).toEqual(['已登记', '就绪检查']);
    expect(titles.indexOf('Quizs')).toBeGreaterThan(titles.indexOf('就绪检查'));
    const sec = sectionNamed(root as ParentNode, 'Quizs');
    expect(sec, '应有「Quizs」一块').toBeTruthy();
    expect((sec as Element).closest('[data-page="runtimes"]'), '有 runtime 时 Quizs 一块在视图根内').toBe(root);
    const buttons = headerButtons(f);
    expect(buttons.map(textOf)).toEqual(['扫描 PATH', '手动登记…', '刷新']);
    expect((buttons[0] as HTMLButtonElement).disabled, '[扫描 PATH] 照旧禁用').toBe(true);
  });
});

describe('T049 初始标题与运行时改写', () => {
  it('挂载后 document.title 仍由 App 按页面改写（「CLI 运行时 · Themis Tally」），空态也一样', async () => {
    await mountApp('#/runtimes?mock=empty');
    expect(document.title).toBe('CLI 运行时 · Themis Tally');
  });
});
"""

PROBE_SPECS = {
    "empty": PROBE_EMPTY,
    "states": PROBE_STATES,
}
PROBE_ORDER = ("empty", "states")


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 t043 门禁的写法）
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
    # 这台机器上线用的 QUIZS_* 不进 vitest 子进程（与 tests/conftest.py 的 no_ambient_quizs 同一口径）：
    # 探针自己用 ?quizs= 选情景，环境里带着用户级的那几套只会让结果随机器变。
    for name in ("QUIZS_CMD", "QUIZS_LIVE_PLAN", "QUIZS_PROVIDER_PROFILE", "QUIZS_QUALIFICATION"):
        env.pop(name, None)
    return env


def git_status_set():
    proc = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
                          cwd=REPO_ROOT, capture_output=True, timeout=120)
    assert proc.returncode == 0, f"git status 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


def t049_marker_present():
    """候选里是否有 T049 的标记（执行端的新测试文件）：没有就不起 npm（基线上必然没有）。"""
    return (REPO_ROOT / EMPTY_TEST_REL).is_file()


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t049_marker_present():
        pipe.reason = ("候选里还没有 T049 的标记（tests/page-runtimes-empty.test.tsx），没有东西可测，未调用 npm；"
                       "执行端把空态的 Quizs 一块与新测试接上之后，流水线才会运行 npm ci、Vitest 与探针")
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
                for key in PROBE_ORDER:
                    name = f"probe-{uid}-t049-{key}.test.tsx"
                    probe_dir.mkdir(exist_ok=True)
                    path = probe_dir / name
                    written.append(path)
                    path.write_text(PROBE_SPECS[key], encoding="utf-8", newline="\n")
                    pipe.probe_files[key] = name
                    run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
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
        f"{network_hint(step.out)}\n--- 输出尾部 ---\n{step.tail}")
    return step


def assert_probe_ok(pipe, key):
    """探针 key 在候选上全部通过：退出码 0、输出里有探针文件名、通过数不少于 it( 行数、没有失败跳过待办。"""
    assert pipe.ran, pipe.reason
    assert key not in pipe.probe_skipped, pipe.probe_skipped[key]
    step = assert_step_ok(pipe, f"probe:{key}")
    name = pipe.probe_files.get(key)
    assert name and name in step.out.replace("\\", "/"), \
        f"探针输出里没有探针文件名，可能没被 Vitest 选中：\n{step.tail}"
    want = probe_count(PROBE_SPECS[key])
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m and int(m.group(1)) >= want, f"探针 {key} 应至少有 {want} 条通过：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), f"探针 {key} 有失败或跳过：\n{step.tail}"


# ---------------------------------------------------------------------------
# P / D 系列：流水线断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、D09：npm 依赖（已在就跳过）、npm test（全绿，含执行端新测试与改过的 page-quizs）
    都退出 0；依赖文件一个字节没动；gate-probe/ 没有留下。"""
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


def test_p2_worktree_unchanged_by_pipeline(pipeline):
    """P2（守卫）：流水线与探针前后 git status 相同；gate-probe/ 没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"


def test_d01_d02_d04_d05_probe_empty(pipeline):
    """empty 探针 / D01、D02、D04、D05、D08：?mock=empty 空态（标题与说明原文、EmptyState 与 Quizs
    一块都直接挂 .tt-page 下、两张表各 2 行、无页面级出错块、页头三钮与 [手动登记…] 可点）；
    ?mock=empty&quizs=broken 与注入 providers 失败（失败只写在区块里）；先空后有（点 [刷新] 之后
    data 态、视图根出现、Quizs 一块进视图根内）。"""
    assert_probe_ok(pipeline, "empty")


def test_d03_d06_d08_probe_states(pipeline):
    """states 探针 / D03、D06、D08：?mock=loading / ?mock=error 没有 Quizs 一块；有 runtime 时页面照旧
    （data 态、视图根内三节次序、Quizs 一块在视图根内、页头三钮）；挂载后 document.title 仍由 App
    按页面改写。"""
    assert_probe_ok(pipeline, "states")
