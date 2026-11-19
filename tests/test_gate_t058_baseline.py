"""T058 战前门禁：桌面端前端「运行时页的空态只替换「已登记」表：就绪检查与 Quizs 一块照常显示」
的黑盒基准测试（合同 t058-desktop-web-runtimes-empty-state.v1，基线 26651c5e00bcc9abd1fba85802afc6680b72c348）。

被测对象是 ``desktop/web/`` 前端：

- ``src/pages/RuntimesPage.tsx``：入口页回到「只管读数据与页头」——children 一律只有
  ``<RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />``
  那一行（逐字不变），整页空态那一支（三元表达式）与 ``EmptyState`` / ``QuizsBlock`` 两个 import 删掉；
  ``isEmpty={isRuntimesEmpty}``、一行式 ``const isRuntimesEmpty = …;``、``'../api'`` 那组 import、
  ``loadRuntimes``、页头两钮照旧，页面状态在没登记时仍是 ``empty``。
- ``src/pages/readonly1/runtimes-RuntimesView.tsx``：``<Section title="已登记">`` 里按
  runtimes 是否为空二选一——空时渲染 ``EmptyState``（标题「还没有登记的 runtime」与说明原文逐字）替换那张
  「已登记的 runtime」表，非空时照旧那张表；EmptyState 从 ``'../../components'`` 引，
  ``import './runtimes-styles.css';`` 仍是最后一行 import；「就绪检查」一节、QuizsBlock、WriteFlow 不动。

行为面（D01–D05）：一个 runtime 都没登记时 ``data-page-state="empty"``、视图根 ``data-page="runtimes"``
在，「已登记」一节里是空态（该节里没有那张表），「就绪检查」一节照常（[运行就绪检查] 与 [核验] 都
disabled === false、「按版本记录核验」文本框在），Quizs 一块在视图根里（两张表各 2 行，读失败只写在区块里）；
Quizs 读坏不影响页面状态、没有页面级出错块；先空后有点 [刷新] 之后 data 态、「已登记」一节里出现一张有一行
的表、空态消失；有 runtime 时页面照旧（三节次序、表在、页头三钮、禁用按钮数 0）；loading / error 照旧
（视图根不渲染）。真实模式（注入 ``setLiveClientForTests`` 替身）与桩模式（``?mock=empty``）行为一致。

基线（26651c5e）上 RuntimesPage 还有整页空态那一支、RuntimesView 还没有 EmptyState，所以失败都落在断言上
（静态 S01/S02；流水线在候选里还没有 T058 的标记——RuntimesView 从 ``../../components`` 引 EmptyState——
时不起 npm，P/D 用例以「流水线未运行」的断言失败），不是收集失败：模块级只导入标准库，仓库文件的读取都
发生在用例函数里；流水线（npm、Vitest、探针）放在 ``pipeline`` 会话级夹具里（全量 pytest 默认跳过，
点名运行本文件才跑；照 T049/T057 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：RuntimesPage 的「children 只渲染视图那一行」与
  长期红线（S01）；RuntimesView 的空态写法（EmptyState 从 '../../components' 引、两段文案逐字、样式表
  import 仍在最后）与既有记号 / 禁字（S02）；执行端改过的 page-runtimes-empty.test.tsx 记号齐备、
  无 skip/only/todo、空态断言落到「已登记」一节（S03）；page-quizs.test.tsx 保留的三件事（S04）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、``npm test``
  全绿（含执行端改过的两份包内测试，旧断言没改掉会在这里红）；两份探针逐份写成
  ``gate-probe/probe-<uid>-t058-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，``finally``
  里删除。探针挂整个 App（不 mock 组件、不 mock api）：桩模式用 ``?mock=``/``?quizs=`` 选情景，注入用
  ``setLiveClientForTests``（应用自己的测试缝，page-quizs.test.tsx 同款）。
  - empty（D01–D04、D08）：?mock=empty（状态 empty、视图根在、空态在「已登记」一节里且该节里没有那张表、
    就绪检查一节照常、Quizs 一块在视图根里、页头三钮）；?mock=empty&quizs=broken（失败只写在区块里）；
    注入替身（runtimes 空数组 + providers 失败，真实模式与桩模式一致）；先空后有（点 [刷新] 之后
    「已登记」一节里出现一张有一行的表、空态消失）。
  - states（D05、D10）：?mock=loading / ?mock=error 照旧（视图根不渲染）；有 runtime 时页面照旧
    （三节次序、那张表在、页头三钮、禁用按钮数 0）。

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
RUNTIMESVIEW_REL = f"{SRC_REL}/pages/readonly1/runtimes-RuntimesView.tsx"
EMPTY_TEST_REL = f"{TESTS_REL}/page-runtimes-empty.test.tsx"
PAGE_QUIZS_TEST_REL = f"{TESTS_REL}/page-quizs.test.tsx"

# T041 定下的两段空态文字（t041 S05 / t043 S03 按本文件文本查；T058 合同 D01——一个字都不许改）
EMPTY_TITLE = "还没有登记的 runtime"
EMPTY_DESC = "用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）"

# 入口页 children 里那一行（t054 :141 钉着逐字不变；合同「写法钉死」）
VIEW_LINE = "<RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />"

# 视图的既有记号（合同「写法钉死」；t043 S04 / t055 S05 / t056 S05 认的口径照旧）
VIEW_KEEP_MARKS = (
    'title="已登记"', 'title="就绪检查"', 'aria-label="已登记的 runtime"', 'rt-table',
    'RuntimeDoctor', 'runtime.remove', 'useWriteFlow', "import './runtimes-styles.css'",
    "版本: '—'", 'rt-ready-area',
)
# 视图代码里不许出现的写法（t055 S05 / t056 S05 / t009 D11）
VIEW_FORBIDDEN_CODE = ('DisabledAction', 'PlayIcon', 'role="status"', 'style=')
# 视图全文（注释也算）不许出现的文字：包内三份扫描（page-static 的 fetch、writes-remove 的「删除运行时」
# 「已删除」、cleanup1-static 的「登记 runtime」「删除 runtime」）加上 t041/t049 的 BAD_ENTRY_TEXTS
# （T058 新增的文件头注释也要避开这些）
BAD_ENTRY_TEXTS = (
    "已登记运行时", "已登记表里加上", "；命令写进本机文件", "已登记为",
    "ERROR: runtime", "改 adapter 要加",
    "只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符",
    "命令要写成 JSON 字符串数组",
    "JSON 字符串数组，第一项写命令的绝对路径",
    "登记运行时 ${",
)
VIEW_FORBIDDEN_TEXTS = ('fetch', '删除运行时', '已删除', '登记 runtime', '删除 runtime') + BAD_ENTRY_TEXTS
# 入口页全文（注释也算）不许出现的文字：BAD_ENTRY_TEXTS、「登记 runtime」（t041 :331 / t049 :278）、
# 「仍禁用」（t054 :834）——改写文件头注释时也要避开
PAGE_FORBIDDEN_TEXTS = BAD_ENTRY_TEXTS + ('登记 runtime', '仍禁用')

# 执行端改过的 page-runtimes-empty.test.tsx 必须留着的 15 个记号（t049 S04 的口径，T058 合同「写法钉死」）
EXECUTOR_TEST_TOKENS = (
    "mock=empty", "quizs=broken", EMPTY_TITLE, EMPTY_DESC,
    "Quizs 提供方档案", "Quizs live 套", "Quizs 跑不起来", "读不出",
    "setLiveClientForTests", "刷新", "mock=loading", "mock=error",
    "readFileSync", "Themis Tally", 'data-page="runtimes"',
)

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T049/T057 门禁），用完就停下并在断言里写明。
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 120}

ASSUMPTIONS = (
    "「替换掉那张表」钉成：空态时「已登记」一节里没有 table[aria-label=\"已登记的 runtime\"]（那一节是那张表"
    "唯一的家，不查整页）；非空态由 states 探针反钉（那张表在、行数 > 0，确切行数留给包内测试）",
    "[运行就绪检查] / [核验] 的可点按 disabled === false 判（t057 的口径）；探针只看属性、不点按钮、不起作业",
    "「禁用按钮数 0」只在 data 态断言（page-app.test.tsx:91 的口径）；空态下只钉点名的按钮（页头三钮与就绪"
    "检查两钮），不数整页",
    "空态断言一律限定在 sectionNamed(pageRoot(), '已登记') 里找 .tt-empty：Quizs 区块在别的情景下自己也有"
    "空态文案（T058 规划报告 A9），在整个 frame 里找第一个 .tt-empty 会误伤",
    "静态锚点只按合同「写法钉死」那一节：runtimes.length === 0 的逐字条件不钉（写法留给执行端，行为由探针钉）",
    "流水线预算 580 秒（G01 的 600 秒减去静态用例与 pytest 自身开销）：候选里 RuntimesView 还没从 "
    "../../components 引 EmptyState 时不起 npm（基线上必然没有；G01 在基线上以静态断言与「流水线未运行」"
    "失败）；node_modules 已在（执行端 Setup 装过）就不重装",
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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043/T049 的同一口径）。
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

def test_s01_runtimes_page_children_only_view():
    """S01 / D04、D06、D10：RuntimesPage 的 children 只渲染 RuntimesView 那一行（逐字），整页空态那一支
    与 EmptyState / QuizsBlock 两个 import 删掉；isEmpty={isRuntimesEmpty}、一行式 isRuntimesEmpty、
    loadRuntimes、'{(data, reload) =>' 前缀、页头两钮与 title="CLI 运行时" 照旧；全文避开禁字。"""
    need_file(RUNTIMESPAGE_REL)
    text = read_rel(RUNTIMESPAGE_REL)
    code = strip_ts_comments(text)
    problems = []
    # 整页空态那一支删掉（合同行为面：children 一律只有 RuntimesView 那一行）
    if re.search(r"\bempty\s*=\s*[<{\"']", code):
        problems.append("RuntimesPage 不应给 PageFrame 传 empty 属性（PageFrame 在 empty 阶段渲染 children）")
    if "isRuntimesEmpty(data)" in code:
        problems.append("children 不应再按 isRuntimesEmpty(data) 分支（整页空态那一支删掉，t049 S02 的旧口径）")
    for needle, why in (
        ("<EmptyState", "入口页不应再摆 EmptyState（空态由视图在「已登记」一节里显示）"),
        ("<QuizsBlock", "入口页不应再摆 QuizsBlock（Quizs 一块在视图里）"),
    ):
        if needle in code:
            problems.append(f"{why}（仍看得到 {needle}）")
    if re.search(r"import\s*\{[^}]*\bEmptyState\b[^}]*\}", code):
        problems.append("RuntimesPage 不应再引入 EmptyState（写法钉死：没有 import { EmptyState } from '../components';）")
    if re.search(r"import\s*\{[^}]*\bQuizsBlock\b[^}]*\}", code):
        problems.append("RuntimesPage 不应再引入 QuizsBlock（写法钉死：没有 import { QuizsBlock } from './readonly1/runtimes-QuizsBlock';）")
    # 长期红线照旧（t049 S02 :230-246 / t054 S06 的保留项）
    if "isEmpty={isRuntimesEmpty}" not in code:
        problems.append("仍应照传 isEmpty={isRuntimesEmpty}（空态下 data-page-state 仍是 empty，D04）")
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
    if not re.search(r"\{\(data, reload\)\s*=>", code):
        problems.append("children 应逐字以 {(data, reload) => 开头（t043 :463 的正则）")
    if VIEW_LINE not in code:
        problems.append(f"children 里应有 RuntimesView 那一行（逐字，t054 :141）：{VIEW_LINE}")
    if 'title="CLI 运行时"' not in code:
        problems.append("页头标题应照旧 title=\"CLI 运行时\"")
    if "ScanRuntimesAction" not in code:
        problems.append("[扫描 PATH] 应由 src/writes 的 ScanRuntimesAction 渲染")
    if "<AddRuntimeAction reload={reload}" not in code:
        problems.append("页头 [手动登记…]（AddRuntimeAction reload={reload}）应保留")
    if ".css" in code:
        problems.append("RuntimesPage 不应引 CSS（代码里不出现 .css）")
    # 禁字按全文原文扫（注释也算）：新页头注释也要避开
    for frag in PAGE_FORBIDDEN_TEXTS:
        if frag in text:
            problems.append(f"RuntimesPage.tsx 出现「{frag}」（禁字表，注释也算）")
    fail_if(problems, "RuntimesPage 的 children 只渲染视图那一行（S01）")


def test_s02_runtimes_view_empty_state_in_section():
    """S02 / D01、D02、D10：RuntimesView 的「已登记」一节按空不空二选一——EmptyState 从 '../../components'
    引、两段文案逐字落在视图里；既有记号（两节标题、那张表的 aria-label、rt-table、RuntimeDoctor、
    runtime.remove、useWriteFlow、版本: '—'、rt-ready-area、样式表 import 仍在最后一行）一条不破；
    禁写法（DisabledAction、PlayIcon、role="status"、内联 style=）与新注释的禁字一条不沾。"""
    need_file(RUNTIMESVIEW_REL)
    text = read_rel(RUNTIMESVIEW_REL)
    code = strip_ts_comments(text)
    problems = []
    # EmptyState 从 '../../components' 引（写法钉死：并进现有那一行 import；不逐字钉并法）
    if not re.search(r"import\s*\{[^}]*\bEmptyState\b[^}]*\}\s*from\s*['\"]\.\./\.\./components['\"]", code):
        problems.append("EmptyState 应从 '../../components' 引入（写法钉死）")
    if "<EmptyState" not in code:
        problems.append("「已登记」一节的空态应由 <EmptyState … /> 渲染")
    if f'title="{EMPTY_TITLE}"' not in code:
        problems.append(f"视图里应有 title=\"{EMPTY_TITLE}\"（两段文案逐字照旧）")
    if f'description="{EMPTY_DESC}"' not in code:
        problems.append(f"视图里应有 description=\"{EMPTY_DESC}\"（两段文案逐字照旧）")
    # 既有记号照旧（t043 S04 / t055 S05 / t056 S05）
    for mark in VIEW_KEEP_MARKS:
        if mark not in code:
            problems.append(f"视图应保留记号 {mark}")
    # 样式表 import 仍是最后一行 import（合同行为面）
    imports = re.findall(r"^import\b[^\n]*$", code, re.M)
    if not imports or imports[-1].strip() != "import './runtimes-styles.css';":
        problems.append("import './runtimes-styles.css'; 应仍是视图的最后一行 import")
    # 禁写法（t055 S05 / t056 S05 / t009 D11）
    for bad in VIEW_FORBIDDEN_CODE:
        if bad in code:
            problems.append(f"视图代码里不应出现 {bad}")
    # 不加新样式表：.css 只许出现在 runtimes-styles.css 那一处
    if ".css" in re.sub(r"runtimes-styles\.css", "", code):
        problems.append("视图不应新增 CSS（.css 只许出现在 runtimes-styles.css 那一处）")
    # 禁字按全文原文扫（注释也算）：新加的文件头注释也要避开
    for frag in VIEW_FORBIDDEN_TEXTS:
        if frag in text:
            problems.append(f"RuntimesView.tsx 出现「{frag}」（禁字表，注释也算）")
    fail_if(problems, "RuntimesView 的「已登记」一节空态（S02）")


def test_s03_executor_empty_test_updated():
    """S03 / D08：page-runtimes-empty.test.tsx 留着 t049 S04 的 15 个记号、没有 skip/only/todo，
    空态断言落到「已登记」一节里（不再是「视图根为 null」的旧口径），桩模式与真实模式各测一遍空态
    （mock=empty 与 setLiveClientForTests 两个记号）。"""
    need_file(EMPTY_TEST_REL)
    fresh = read_rel(EMPTY_TEST_REL)
    problems = [f"page-runtimes-empty.test.tsx 应覆盖 {token}" for token in EXECUTOR_TEST_TOKENS if token not in fresh]
    if "已登记" not in fresh:
        problems.append("page-runtimes-empty.test.tsx 应把空态断言落到「已登记」那一节里（合同第 4 步）")
    if "空态不渲染视图根" in fresh:
        problems.append("page-runtimes-empty.test.tsx 的旧提示语「空态不渲染视图根」应随新行为改写")
    problems += _no_skip_marks(strip_ts_comments(fresh))
    fail_if(problems, "执行端空态测试（S03）")


def test_s04_page_quizs_test_kept():
    """S04 / D08：page-quizs.test.tsx 那个 it 改成新行为后仍留着三件事——sectionNamed(frame(), 'Quizs')、
    mock=loading、mock=empty；与新行为相反的提示语「Quizs 一块也就看不到」不在；没有 skip/only/todo。"""
    need_file(PAGE_QUIZS_TEST_REL)
    quizs = read_rel(PAGE_QUIZS_TEST_REL)
    problems = []
    if "sectionNamed(frame(), 'Quizs')" not in quizs:
        problems.append("page-quizs.test.tsx 应留着 sectionNamed(frame(), 'Quizs') 的断言（t049 S04）")
    for token in ("mock=loading", "mock=empty"):
        if token not in quizs:
            problems.append(f"page-quizs.test.tsx 的既有两半（{token}）应保留")
    if "Quizs 一块也就看不到" in quizs:
        problems.append("page-quizs.test.tsx 的提示语「Quizs 一块也就看不到」与新行为相反，应改写")
    problems += _no_skip_marks(strip_ts_comments(quizs))
    fail_if(problems, "page-quizs 测试（S04）")


# ---------------------------------------------------------------------------
# 探针源码（每份自包含：辅助函数不跨文件共享；照 t049 PRELUDE 与 page-quizs.test.tsx 的已知好写法）
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
function needRoot(): HTMLElement {
  const r = pageRoot();
  expect(r, '空态下视图根 data-page="runtimes" 也应渲染（页面状态仍是 empty）').toBeTruthy();
  return r as HTMLElement;
}
function needSection(root: ParentNode, title: string): Element {
  const sec = sectionNamed(root, title);
  expect(sec, '应有「' + title + '」一节').toBeTruthy();
  return sec as Element;
}
function btnIn(root: ParentNode, label: string): HTMLButtonElement | null {
  const hit = qa(root, 'button').find((b) => textOf(b) === label);
  return (hit as HTMLButtonElement) || null;
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
"""

# empty 探针：空态只替换「已登记」表（D01–D04、D08）；真实模式与桩模式各测一遍
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

describe('T058 空态只替换「已登记」表：?mock=empty', () => {
  it('空态：页面状态仍 empty、视图根在；「已登记」一节里是空态（标题与说明原文），该节里没有那张表', async () => {
    await mountApp('#/runtimes?mock=empty');
    const f = needFrame();
    expect(f.getAttribute('data-page-state'), '页面状态仍是 empty（isEmpty 照传）').toBe('empty');
    const root = needRoot();
    expect(qa(root, 'section').map(sectionTitle).slice(0, 2)).toEqual(['已登记', '就绪检查']);
    const sec = needSection(root, '已登记');
    const empty = sec.querySelector('.tt-empty');
    expect(empty, '「已登记」一节里应有 .tt-empty（空态替换那张表）').toBeTruthy();
    expect(textOf((empty as Element).querySelector('.tt-empty__title'))).toBe(EMPTY_TITLE);
    expect(textOf((empty as Element).querySelector('.tt-empty__desc'))).toBe(EMPTY_DESC);
    expect(sec.querySelector('table[aria-label="已登记的 runtime"]'), '空态时「已登记」一节里没有那张表').toBeNull();
    expect(f.querySelector('.tt-page__error'), '空态不应有页面级出错块').toBeNull();
  });

  it('「就绪检查」一节照常：[运行就绪检查] 与 [核验] 都可点、「按版本记录核验」文本框在、该节没有被空态替换', async () => {
    await mountApp('#/runtimes?mock=empty');
    const root = needRoot();
    const sec = needSection(root, '就绪检查');
    const run = btnIn(sec, '运行就绪检查');
    expect(run, '应有 [运行就绪检查]').toBeTruthy();
    expect((run as HTMLButtonElement).disabled, '空闲时 [运行就绪检查] 可点（disabled === false）').toBe(false);
    const verify = btnIn(sec, '核验');
    expect(verify, '应有 [核验]').toBeTruthy();
    expect((verify as HTMLButtonElement).disabled, '空闲时 [核验] 可点（disabled === false）').toBe(false);
    expect(qa(sec, 'label').map(textOf), '「按版本记录核验」的可见 label 在').toContain('按版本记录核验');
    expect(sec.querySelector('input.tt-field__input'), '「按版本记录核验」的文本框在').toBeTruthy();
    expect(sec.querySelector('.tt-empty'), '「就绪检查」一节没有被空态替换').toBeNull();
  });

  it('Quizs 一块在视图根里（两张表各 2 行）；页头三钮照旧、空态下 [手动登记…] 可点', async () => {
    await mountApp('#/runtimes?mock=empty');
    const f = needFrame();
    const root = needRoot();
    const sec = needSection(root, 'Quizs');
    expect(sec.closest('[data-page="runtimes"]'), 'Quizs 一块在视图根里').toBe(root);
    const pt = tableOf(sec, 'Quizs 提供方档案');
    expect(rowsOf(pt).length, '提供方档案表两行（ok 情景）').toBe(2);
    expect(textOf(pt)).toContain('stepfun');
    const lt = tableOf(sec, 'Quizs live 套');
    expect(rowsOf(lt).length, 'live 套表两行（ok 情景）').toBe(2);
    expect(textOf(lt)).toContain('就绪');
    const buttons = headerButtons(f);
    expect(buttons.map(textOf)).toEqual(['扫描 PATH', '手动登记…', '刷新']);
    expect((buttons[1] as HTMLButtonElement).disabled, '空态下 [手动登记…] 可点').toBe(false);
    expect(buttons[1].getAttribute('data-variant')).toBe('primary');
  });
});

describe('T058 Quizs 读失败只写在区块里', () => {
  it('?mock=empty&quizs=broken：状态仍 empty、空态仍在「已登记」一节里；区块写「Quizs 跑不起来」、live 逐套「读不出」；没有页面级出错块', async () => {
    await mountApp('#/runtimes?mock=empty&quizs=broken');
    const f = needFrame();
    expect(f.getAttribute('data-page-state'), 'Quizs 坏不影响页面状态').toBe('empty');
    const root = needRoot();
    const sec = needSection(root, '已登记');
    expect(textOf(sec.querySelector('.tt-empty__title'))).toBe(EMPTY_TITLE);
    expect(sec.querySelector('table[aria-label="已登记的 runtime"]'), '空态时「已登记」一节里没有那张表').toBeNull();
    const quizsSec = needSection(root, 'Quizs');
    expect(quizsSec.closest('[data-page="runtimes"]'), 'Quizs 一块仍在视图根里').toBe(root);
    expect(textOf(quizsSec), 'providers 失败只写在区块里').toContain('Quizs 跑不起来');
    const rows = rowsOf(tableOf(quizsSec, 'Quizs live 套'));
    expect(rows.length).toBe(2);
    rows.forEach((row) => {
      expect(textOf(row['状态']), 'live 每套读不出').toBe('读不出');
    });
    expect(f.querySelector('.tt-page__error'), '读失败只写在区块里，没有页面级出错块').toBeNull();
  });

  it('注入替身（真实模式）：runtimes 空数组 + providers 失败，与桩模式一致（状态 empty、视图根在、空态在「已登记」一节、就绪检查两钮可点、Quizs 在视图根里）', async () => {
    injectLive({
      '/api/v1/runtimes': () => Promise.resolve(envelope({ runtimes: [] }, ['config', 'runtime', 'list'])),
      '/api/v1/quizs/providers': () =>
        Promise.resolve(envelope(null, ['config', 'quizs', 'providers', '--json'], false, 3, ['E-GATE'])),
    });
    await mountApp('#/runtimes');
    const f = needFrame();
    expect(f.getAttribute('data-page-state')).toBe('empty');
    const root = needRoot();
    const sec = needSection(root, '已登记');
    expect(textOf(sec.querySelector('.tt-empty__title'))).toBe(EMPTY_TITLE);
    expect(sec.querySelector('table[aria-label="已登记的 runtime"]'), '空态时「已登记」一节里没有那张表').toBeNull();
    const ready = needSection(root, '就绪检查');
    const run = btnIn(ready, '运行就绪检查');
    const verify = btnIn(ready, '核验');
    expect(run && verify, '真实模式下「就绪检查」一节照常').toBeTruthy();
    expect((run as HTMLButtonElement).disabled, '空闲时 [运行就绪检查] 可点').toBe(false);
    expect((verify as HTMLButtonElement).disabled, '空闲时 [核验] 可点').toBe(false);
    const quizsSec = needSection(root, 'Quizs');
    expect(quizsSec.closest('[data-page="runtimes"]'), 'Quizs 一块在视图根里').toBe(root);
    expect(textOf(quizsSec)).toContain('Quizs 跑不起来');
    expect(textOf(quizsSec)).toContain('E-GATE');
    expect(f.querySelector('.tt-page__error'), 'providers 失败不整页出错').toBeNull();
  });
});

describe('T058 空态不是死路：重读之后按有运行时的样子显示', () => {
  it('点 [刷新]：状态 empty→data，「已登记」一节里出现一张有一行的表、空态消失，Quizs 仍在视图根里', async () => {
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
    const root0 = needRoot();
    const sec0 = needSection(root0, '已登记');
    expect(sec0.querySelector('.tt-empty'), '刷新前「已登记」一节里是空态').toBeTruthy();
    const refresh = headerButtons(f).find((b) => textOf(b) === '刷新');
    expect(refresh, '应有 [刷新] 钮').toBeTruthy();
    await act(async () => {
      fireEvent.click(refresh as Element);
    });
    await settle();
    expect(f.getAttribute('data-page-state'), '重读后按有运行时的样子显示').toBe('data');
    const root = needRoot();
    const sec = needSection(root, '已登记');
    expect(sec.querySelector('.tt-empty'), '重读后空态消失').toBeNull();
    const table = tableOf(sec, '已登记的 runtime');
    expect(rowsOf(table).length, '重读后「已登记」一节里是一张有一行的表').toBe(1);
    const quizsSec = needSection(root, 'Quizs');
    expect(quizsSec.closest('[data-page="runtimes"]'), '重读后 Quizs 一块仍在视图根里').toBe(root);
  });
});
"""

# states 探针：loading / error 照旧；有 runtime 时页面照旧（D05、D10）
PROBE_STATES = PRELUDE + r"""
describe('T058 loading / error 照旧', () => {
  it('?mock=loading：整页挂起，视图根不渲染，没有 Quizs 一块', async () => {
    await mountApp('#/runtimes?mock=loading');
    const f = needFrame();
    expect(f.getAttribute('data-page-state')).toBe('loading');
    expect(pageRoot(), 'loading 态视图根不渲染').toBeNull();
    expect(sectionNamed(f, 'Quizs'), 'loading 态不应有 Quizs 一块').toBeNull();
  });

  it('?mock=error：整页出错（页面级出错块），视图根不渲染，没有 Quizs 一块', async () => {
    await mountApp('#/runtimes?mock=error');
    const f = needFrame();
    expect(f.getAttribute('data-page-state')).toBe('error');
    expect(f.querySelector('.tt-page__error'), '应有页面级出错块').toBeTruthy();
    expect(textOf(f)).toContain('没能读到数据');
    expect(pageRoot(), 'error 态视图根不渲染').toBeNull();
    expect(sectionNamed(f, 'Quizs'), 'error 态不应有 Quizs 一块').toBeNull();
  });
});

describe('T058 有 runtime 时页面照旧', () => {
  it('data 态：三节次序、「已登记」一节里是那张表（没有空态）、Quizs 在视图根里、页头三钮、禁用按钮数 0', async () => {
    await mountApp('#/runtimes');
    const f = needFrame();
    expect(f.getAttribute('data-page-state')).toBe('data');
    const root = needRoot();
    const titles = qa(root, 'section').map(sectionTitle);
    expect(titles.slice(0, 2)).toEqual(['已登记', '就绪检查']);
    expect(titles.indexOf('Quizs')).toBeGreaterThan(titles.indexOf('就绪检查'));
    const sec = needSection(root, '已登记');
    expect(sec.querySelector('.tt-empty'), '有 runtime 时没有空态').toBeNull();
    const table = tableOf(sec, '已登记的 runtime');
    expect(rowsOf(table).length, '那张表照旧在（确切行数留给包内测试）').toBeGreaterThan(0);
    const quizsSec = sectionNamed(root, 'Quizs');
    expect(quizsSec, '应有「Quizs」一块').toBeTruthy();
    expect((quizsSec as Element).closest('[data-page="runtimes"]'), '有 runtime 时 Quizs 一块在视图根内').toBe(root);
    const buttons = headerButtons(f);
    expect(buttons.map(textOf)).toEqual(['扫描 PATH', '手动登记…', '刷新']);
    const disabled = qa(f, 'button').filter((b) => (b as HTMLButtonElement).disabled);
    expect(disabled.length, '有 runtime 时运行时页上禁用按钮数照旧是 0（page-app 的口径）').toBe(0);
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
# 会话级夹具：npm 流水线 + 探针（照 t049/t057 门禁的写法）
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


def t058_marker_present():
    """候选里是否已有 T058 的标记（RuntimesView 从 '../../components' 引 EmptyState）：
    没有就不起 npm（基线上必然没有）。"""
    path = REPO_ROOT / RUNTIMESVIEW_REL
    if not path.is_file():
        return False
    return re.search(r"import\s*\{[^}]*\bEmptyState\b[^}]*\}\s*from\s*['\"]\.\./\.\./components['\"]",
                     _read(path)) is not None


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t058_marker_present():
        pipe.reason = ("候选里还没有 T058 的标记（runtimes-RuntimesView.tsx 从 '../../components' 引 "
                       "EmptyState），没有东西可测，未调用 npm；执行端把「已登记」一节的空态接上之后，"
                       "流水线才会运行 npm ci、Vitest 与探针")
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
                    name = f"probe-{uid}-t058-{key}.test.tsx"
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
    """P1 / V01、V02、D08、D10：npm 依赖（已在就跳过）、npm test（全绿，含执行端改过的两份包内测试——
    旧断言没改掉会在这里红）都退出 0；依赖文件一个字节没动；gate-probe/ 没有留下。"""
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


def test_d01_d02_d03_d04_probe_empty(pipeline):
    """empty 探针 / D01–D04、D08：?mock=empty 空态（状态仍 empty、视图根在、空态在「已登记」一节里且该节
    里没有那张表、「就绪检查」一节照常两钮可点、Quizs 一块在视图根里两张表各 2 行、页头三钮）；
    ?mock=empty&quizs=broken 与注入 providers 失败（失败只写在区块里，真实模式与桩模式一致）；
    先空后有（点 [刷新] 之后「已登记」一节里出现一张有一行的表、空态消失、Quizs 仍在视图根里）。"""
    assert_probe_ok(pipeline, "empty")


def test_d05_d10_probe_states(pipeline):
    """states 探针 / D05、D10：?mock=loading / ?mock=error 照旧（视图根不渲染、没有 Quizs 一块）；
    有 runtime 时页面照旧（三节次序、「已登记」一节里是那张表、Quizs 在视图根里、页头三钮、
    禁用按钮数 0）。"""
    assert_probe_ok(pipeline, "states")
