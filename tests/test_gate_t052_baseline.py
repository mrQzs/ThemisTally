"""T052 战前门禁：桌面端前端「改绑定的两个表单每次打开都按当时的绑定预填」的黑盒基准测试
（合同 t052-desktop-web-bind-form-reopen.v1，基线 25012c98）。

被测对象是 ``desktop/web/src/writes/HubBindForm.tsx`` 与 ``RoleBindForm.tsx`` 两个改绑定表单的
拆内外层改法（其余行为一个字不变）：

- 外层 ``HubBindDialog`` / ``RoleBindDialog``（名字照旧，不导出）只做三件事——
  ``const { start, flow } = useWriteFlow(reload);``、渲染 ``{open && <内层 … />}``、
  渲染 ``<WriteFlow flow={flow} />``（写流程留在外层，表单关掉也照常走完）。
- 内层 ``HubBindFormDialog`` / ``RoleBindFormDialog``（新名字，不导出）只在打开时挂载：预填计算、
  两个 ``useState``、候选联动、参数组装、``useLivePreview``、门控、底部渲染与 ``<Dialog open …>``
  都搬进来；``canPreview`` 去掉 ``open &&``。每次打开都按**当时**的 props 重新预填（三条情形：
  改字段取消后再开回到现有绑定；外部改了绑定重读后 props 变了再开按新绑定预填；新增候选后再开
  按当时的候选预填）。
- 有意的行为变化（合同钉死）：再打开时底部先「预览中…」、[确认…] 灰到新预览回来才可点。
- 两个文件都不新增 import（既有 import 行一行不动）；门禁字面量（T045 S03/S10 与 T051 S07 的
  逐条）一个不少；文字、样式与导出形态一个字不变。
- 执行端新测试文件 ``desktop/web/tests/writes-bind-reopen.test.tsx`` 覆盖合同第 4 步点名的每一项。

基线（25012c98）上 ``HubBindFormDialog`` / ``RoleBindFormDialog`` 与新测试文件都不存在，两个
源文件也还是单层组件，所以本文件的失败落在「记号不在」「文件不存在」「流水线没跑」这类断言上，
不是导入、收集或语法错误：模块级只导入标准库，所有仓库文件的读取都发生在用例函数里；流水线
（npm、Vitest、探针）放在 ``pipeline`` 会话级夹具里（全量 pytest 默认跳过，点名运行本文件才跑；
候选里还没有本片的标记时夹具不调 npm——照 T024/T040/T041/T043/T044/T045/T051 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线）：HubBindForm 的拆分与门禁字面量（S01）；RoleBindForm 的
  拆分与门禁字面量（S02）；执行端新测试文件在位且要点齐备（S03）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、
  npm test 全绿；两份探针逐份写成 ``gate-probe/probe-<uid>-t052-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除。探针直接渲染
  ``HubBindAction`` / ``RoleBindAction``（照合同第 4 步给执行端规定的写法），用 RTL 的
  ``rerender`` 模拟「重读之后 props 变了」，用 ``setLiveClientForTests`` 注入假服务记录预览与写
  请求，不 mock 被测组件；每份自带全部辅助函数，不跨文件共享作用域；等防抖用真实计时器
  ``sleep(450)``（不用假计时器）。
  - hub：改主选/取消/再开回到现有绑定（a）；rerender 换主绑定再开按新绑定预填且预览 args 是新
    绑定（b）；现有主绑定进了新增候选再开预填它、预览 args 与 [确认…] 可点（c，不能只看
    select.value——react-dom 会把第一个未禁用 option 设成 selected）；确认先关表单再开写确认框、
    发 ``POST /api/v1/hub/roles/<post>``、成功轻提示与 reload、写完再开按新绑定预填（d）；再开先
    「预览中…」[确认…] 灰着、新预览回来才可点且预览请求多一次（e）；表单开着时 props 变了不重置
    用户正在改的字段（守卫）。
  - role：execution 改 profile/取消/再开回到现有 profile 与 planning_review 切无头/取消/再开回到
    交互式宿主（a/a2）；rerender 换 binding.profile 再开按新绑定预填且预览 target 是新 profile
    （b）；planning_review 起初没有候选（无头拿掉、help 是原因句）给候选后再开选无头、预览 target
    是第一个候选且 [确认…] 可点（c）；确认先关表单再开写确认框、发 ``POST /api/v1/roles/<role>``、
    成功轻提示与 reload、写完再开按新绑定预填（d）；（e）与守卫同 hub。

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
WRITES_REL = f"{SRC_REL}/writes"
TESTS_REL = f"{WEB_REL}/tests"

HUBBINDFORM_REL = f"{WRITES_REL}/HubBindForm.tsx"
ROLEBINDFORM_REL = f"{WRITES_REL}/RoleBindForm.tsx"
EXEC_TEST_REL = f"{TESTS_REL}/writes-bind-reopen.test.tsx"

# 两个原因句常量（合同 Behavior contract 与写法钉死，逐字；基线上就在，本片不许动）
HUB_REASON_NO_CANDIDATES = "没有能用在这个岗位的 profile：先在「CLI 运行时」页登记运行时，再新建 profile"
HUB_REASON_UNSET_DEFAULT = "这个岗位现在用的是内核缺省，没有要恢复的配置"
ROLE_REASON_NO_PROFILES = "没有已登记的 profile，无头不可选：先在「CLI 运行时」页登记运行时，再新建 profile"

# 基线（25012c98）上两个文件的 import 行（写法钉死第 3 条：一行不动、不新增；含 css 的副作用 import）
HUB_BASELINE_IMPORTS = (
    "import { useState, type ReactNode } from 'react';",
    "import { Button, Dialog, Select, dispatchCommand } from '../components';",
    "import { DisabledAction } from '../shell/DisabledAction';",
    "import type { HubChange, WriteArgs } from '../api';",
    "import { hubChangeLines } from './hubChangeLines';",
    "import { useWriteFlow, type WriteSpec } from './useWriteFlow';",
    "import { WriteFlow } from './WriteConfirmDialog';",
    "import { useLivePreview } from './useLivePreview';",
    "import './hub-bind-form.css';",
)
ROLE_BASELINE_IMPORTS = (
    "import { useState, type ReactNode } from 'react';",
    "import { Button, Dialog, Select, dispatchCommand, type SelectOption } from '../components';",
    "import { DisabledAction } from '../shell/DisabledAction';",
    "import type { BindingChange, WriteArgs } from '../api';",
    "import { useWriteFlow, type WriteSpec } from './useWriteFlow';",
    "import { WriteFlow } from './WriteConfirmDialog';",
    "import { useLivePreview } from './useLivePreview';",
    "import './hub-bind-form.css';",
)

# 外层保留的写流程调用（写法钉死第 5 条：useWriteFlow 必须在外层）
OUTER_WRITEFLOW_LINE = "const { start, flow } = useWriteFlow(reload);"

# 执行端新测试文件的最小覆盖记号（合同第 4 步点名的覆盖点）
EXECUTOR_TEST_TOKENS = (
    "HubBindAction", "RoleBindAction", "setLiveClientForTests", "rerender",
    "取消", "预览中…", "/api/v1/hub/roles/", "/api/v1/roles/", "450",
)

# 新源码的禁词（page-static.test.ts 的口径 + T006/T009 的 matchMedia 一类 + 「（UTC 」单一来源）
FORBIDDEN_SOURCE_MARKS = (
    "XMLHttpRequest", "EventSource", "WebSocket", "dangerouslySetInnerHTML", "innerHTML", "outerHTML",
    "insertAdjacentHTML", "eval(", "new Function", "document.write", "srcdoc", "DOMParser",
    "matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver", 'role="status"',
    "（UTC ",
)
# 颜色字面量与颜色函数（T006/T009 的口径）
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_COLOR_FUNCS = ("rgb(", "rgba(", "hsl(", "hsla(", "color-mix(", "oklch(", "lab(", "hwb(")

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T024/T041/T043/T044/T045/T051 门禁）
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 150}

ASSUMPTIONS = (
    "「确认…」先关表单再 start 的次序按行为断言（点表单的 [确认…] 后表单对话框关上、写确认框开上），"
    "不静态钉源码里的调用次序；useWriteFlow 留在外层也由同一条行为断言把关（搬进内层则表单一关写流程"
    "跟着卸载，写确认框不会出现）",
    "写法钉死第 5 条的 ``{open && <内层 … />}`` 按正则 ``open && \\(?\\s*<内层名`` 认（单行与换行两种"
    "排法都算）；外层/内层的定义按行首 ``function`` 认模块级声明",
    "import 行「一行不动」按逐字比较（含 ``import './hub-bind-form.css';`` 的副作用 import，顺序也照旧）"
    "——拆内外层不需要任何新 import，这是合同写法钉死第 3 条的直接读法",
    "``canPreview`` 去掉 ``open &&`` 按禁令 ``canPreview = open`` 不出现来认（其余条件照旧，不钉整行写法）",
    "探针直接渲染 HubBindAction / RoleBindAction（照合同第 4 步给执行端新测试规定的写法），用 rerender "
    "模拟「重读之后 props 变了」；不挂整页 App，断言只落在这两个组件自己身上",
    "情形 (c) 不断言 select.value 就算数：必须断言预览请求的 args 与 [确认…] 可点（react-dom 会把第一个"
    "未禁用 option 设成 selected，旧代码只看 select.value 也过得去）——合同「测试陷阱」一节的要求",
    "(e) 的「预览请求次数比上次多一次」在旧代码上也成立（表单关了再开，enabled 翻转同样触发一次预览）；"
    "区分新旧代码的是「再开先显示预览中…、[确认…] 灰着」这两条（旧代码立刻显示上一次的预览结果）",
    "「表单开着时 props 变了不重置用户正在改的字段」两条守卫在基线上也通过（与今天行为一致），放进探针"
    "是为了防候选用「props 一变就重挂内层」的写法把它弄坏；文件整体仍在基线上红（(a)–(e) 各有基线必红"
    "的断言）",
    "执行端测试文件的覆盖记号是最低要求（有这些记号才说明测到了合同点名的那几件事）；运行时行为由两份"
    "探针独立钉住",
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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043/T044/T045/T051 的同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def import_lines(text):
    """文件里以行首 ``import `` 开头的行（CRLF 已归一），用来逐字比对「一行不动」。"""
    return tuple(line for line in text.split("\n") if line.startswith("import "))


def _no_skip_marks(text):
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
        if re.search(bad, text):
            problems.append(f"出现 {bad}（不许 skip、only、todo）")
    return problems


def _forbidden_marks(rel, text, code):
    """禁词、写死颜色与跨层引用的公共核对（T045 S10 / T051 S07 的口径）。"""
    problems = []
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"{rel} 不应出现 {bad}")
    if _HEX_COLOR.search(code) or any(fn in code for fn in _COLOR_FUNCS):
        problems.append(f"{rel} 不应写死颜色")
    if "style={{" in code:
        problems.append(f"{rel} 不应写内联 style")
    if re.search(r"from\s*['\"]\.\./pages|from\s*['\"]\./roles-", text):
        problems.append(f"{rel} 不应跨层引 src/pages（中文名由入口文件当 prop 传进来）")
    return problems


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_hub_bind_form_split():
    """S01 / D01、D04、写法钉死第 1、3、4、5 条：HubBindForm.tsx 拆内外层——内层
    HubBindFormDialog（不导出）只在打开时挂载（{open && <HubBindFormDialog … />}），外层
    HubBindDialog（照旧不导出）保留 const { start, flow } = useWriteFlow(reload); 与
    <WriteFlow flow={flow} />；canPreview 去掉 open &&；既有 import 行一行不动、不新增；
    T045 S03 的门禁字面量一个不少（导出、原因句、标题、标签、空值选项、useLivePreview(
    与 'hub.set'/'hub.unset'、门控记号、css import 之后不再有 './' 的 import、不出现
    aria-label、代码里不出现 step-low、不写死颜色、不出现禁词、不跨层引 src/pages）。"""
    need_file(HUBBINDFORM_REL)
    text = read_rel(HUBBINDFORM_REL)
    code = strip_ts_comments(text)
    problems = []
    # --- 内外层拆分（写法钉死第 4、5 条；基线上单层组件，这里以断言失败）---
    if code.count("HubBindFormDialog") < 2:
        problems.append("应定义内层组件 HubBindFormDialog 并在外层渲染它（写法钉死第 4 条；基线上还没有）")
    for line in code.split("\n"):
        if "HubBindFormDialog" in line and line.lstrip().startswith("export"):
            problems.append("内层组件 HubBindFormDialog 不应导出（写法钉死第 4 条）")
            break
    if not re.search(r"^function HubBindDialog\(", code, re.M):
        problems.append("外层组件应仍叫 HubBindDialog（模块级 function，写法钉死第 4 条）")
    if not re.search(r"open\s*&&\s*\(?\s*<HubBindFormDialog", code):
        problems.append("外层应渲染 {open && <HubBindFormDialog … />}（只在打开时挂载，写法钉死第 5 条）")
    if OUTER_WRITEFLOW_LINE not in code:
        problems.append(f"外层应保留 {OUTER_WRITEFLOW_LINE}（useWriteFlow 必须在外层，写法钉死第 5 条）")
    elif code.count("useWriteFlow(reload)") != 1:
        problems.append("useWriteFlow(reload) 应只在外层出现一次")
    if "canPreview = open" in code:
        problems.append("canPreview 应去掉 open &&（内层存在即表示表单开着，写法钉死第 5 条）")
    # --- import 行一行不动、不新增（写法钉死第 3 条）---
    if import_lines(text) != HUB_BASELINE_IMPORTS:
        problems.append("import 行应与基线一字不差（一行不动、不新增，含 css 的副作用 import；写法钉死第 3 条）")
    # --- T045 S03 的门禁字面量（包含式核对，一个不少）---
    if "export function HubBindAction(" not in code:
        problems.append("应保留导出 export function HubBindAction(")
    if "export function HubUnsetAction(" not in code:
        problems.append("应保留导出 export function HubUnsetAction(")
    for reason in (HUB_REASON_NO_CANDIDATES, HUB_REASON_UNSET_DEFAULT):
        if reason not in text:
            problems.append(f"原因句应逐字在位：{reason[:18]}…")
    if "改绑定：${postLabel}" not in text:
        problems.append("对话框标题应仍是 改绑定：${postLabel}（变量名 postLabel 不改）")
    if 'label="主绑定"' not in code:
        problems.append("主选 Select 的 label 应恰为「主绑定」")
    if 'label="替补"' not in code:
        problems.append("替补 Select 的 label 应恰为「替补」")
    if "不设替补" not in code:
        problems.append("空值选项「不设替补」应在位")
    if "useLivePreview(" not in code:
        problems.append("表单底部应用 useLivePreview('hub.set', args, enabled)")
    if "'hub.set'" not in code:
        problems.append("表单确认应走 'hub.set'")
    if "'hub.unset'" not in code:
        problems.append("恢复缺省应走 'hub.unset'")
    if "<WriteFlow flow={flow} />" not in code:
        problems.append("文件里应放 <WriteFlow flow={flow} />（写流程在外层照常渲染）")
    for token in ("current", "result.ok", "onClose", "onConfirm"):
        if token not in code:
            problems.append(f"[确认…] 的门控/次序应能看到 {token}（照 HubBindForm 的既有写法）")
    if "import { hubChangeLines } from './hubChangeLines';" not in text:
        problems.append("运行时应引 { hubChangeLines } from './hubChangeLines'")
    for stmt in re.findall(r"import[^;]*?from\s*['\"]\.\./api['\"]", text, re.S):
        if not stmt.lstrip().startswith("import type"):
            problems.append(f"从 ../api 只许 import type：{stmt.strip()[:60]}")
    css_pos = text.find("import './hub-bind-form.css';")
    if css_pos < 0:
        problems.append("应保留 import './hub-bind-form.css'（复用 .hb-* 类，不新建 CSS）")
    else:
        for stmt in re.findall(r"import[^;]*?from\s*['\"]\./[^'\"]+['\"]", text, re.S):
            if text.find(stmt) > css_pos:
                problems.append("import './hub-bind-form.css' 之后不应再有 './…' 的 import")
                break
    if "aria-label" in text:
        problems.append("HubBindForm.tsx 不应出现 aria-label（T045 S03）")
    if "step-low" in code:
        problems.append("代码（去注释）里不应出现 step-low（T045 S03）")
    problems.extend(_forbidden_marks("HubBindForm.tsx", text, code))
    fail_if(problems, "HubBindForm.tsx 的内外层拆分（S01）")


def test_s02_role_bind_form_split():
    """S02 / D01、D04、写法钉死第 2、3、4、5 条：RoleBindForm.tsx 同样拆内外层——内层
    RoleBindFormDialog（不导出）只在打开时挂载，外层 RoleBindDialog（照旧不导出）保留
    useWriteFlow(reload) 与 <WriteFlow flow={flow} />；canPreview 去掉 open &&；
    modeOptionsOf 留在模块层；既有 import 行一行不动、不新增；T051 S07 的门禁字面量
    一个不少（导出、原因句、标题字面量 改绑定：${roleLabel}、label=「模式」/「profile」、
    按钮恰为「更改…」（secondary/sm）、DisabledAction、useLivePreview( 与 'role.set'、门控
    记号、css import 之后不再有 '../' 的 import、只引 hub-bind-form.css、不写 style={{、
    不写死颜色、不出现禁词、不跨层引 src/pages）。"""
    need_file(ROLEBINDFORM_REL)
    text = read_rel(ROLEBINDFORM_REL)
    code = strip_ts_comments(text)
    problems = []
    # --- 内外层拆分（写法钉死第 4、5 条；基线上单层组件，这里以断言失败）---
    if code.count("RoleBindFormDialog") < 2:
        problems.append("应定义内层组件 RoleBindFormDialog 并在外层渲染它（写法钉死第 4 条；基线上还没有）")
    for line in code.split("\n"):
        if "RoleBindFormDialog" in line and line.lstrip().startswith("export"):
            problems.append("内层组件 RoleBindFormDialog 不应导出（写法钉死第 4 条）")
            break
    if not re.search(r"^function RoleBindDialog\(", code, re.M):
        problems.append("外层组件应仍叫 RoleBindDialog（模块级 function，写法钉死第 4 条）")
    if not re.search(r"open\s*&&\s*\(?\s*<RoleBindFormDialog", code):
        problems.append("外层应渲染 {open && <RoleBindFormDialog … />}（只在打开时挂载，写法钉死第 5 条）")
    if OUTER_WRITEFLOW_LINE not in code:
        problems.append(f"外层应保留 {OUTER_WRITEFLOW_LINE}（useWriteFlow 必须在外层，写法钉死第 5 条）")
    elif code.count("useWriteFlow(reload)") != 1:
        problems.append("useWriteFlow(reload) 应只在外层出现一次")
    if "canPreview = open" in code:
        problems.append("canPreview 应去掉 open &&（内层存在即表示表单开着，写法钉死第 5 条）")
    if not re.search(r"^(export )?function modeOptionsOf\(", code, re.M):
        problems.append("modeOptionsOf 应留在模块层（RoleBindAction 判禁用时也要用，写法钉死第 5 条）")
    # --- import 行一行不动、不新增（写法钉死第 3 条）---
    if import_lines(text) != ROLE_BASELINE_IMPORTS:
        problems.append("import 行应与基线一字不差（一行不动、不新增，含 css 的副作用 import；写法钉死第 3 条）")
    # --- T051 S07 的门禁字面量（包含式核对，一个不少）---
    if "export function RoleBindAction(" not in code:
        problems.append("应保留导出 export function RoleBindAction(")
    if "export interface RoleBinding" not in code:
        problems.append("应保留导出 export interface RoleBinding")
    if ROLE_REASON_NO_PROFILES not in text:
        problems.append("没有已登记 profile 的原因句应逐字在位")
    if "改绑定：${roleLabel}" not in text:
        problems.append("对话框标题应仍是字面量 改绑定：${roleLabel}（变量名 roleLabel 不改）")
    if 'label="模式"' not in code:
        problems.append("模式 Select 的 label 应恰为「模式」")
    if 'label="profile"' not in code:
        problems.append("profile Select 的 label 应恰为「profile」")
    if "更改…" not in code:
        problems.append("按钮文字应恰为「更改…」（U+2026）")
    if 'variant="secondary"' not in code or 'size="sm"' not in code:
        problems.append("入口按钮应写 variant=\"secondary\" 与 size=\"sm\"")
    if "DisabledAction" not in code:
        problems.append("可选模式为空时入口应是 DisabledAction")
    if "useLivePreview(" not in code:
        problems.append("表单底部应用 useLivePreview('role.set', args, enabled)")
    if "'role.set'" not in code:
        problems.append("表单确认应走 'role.set'")
    if "<WriteFlow flow={flow} />" not in code:
        problems.append("文件里应放 <WriteFlow flow={flow} />（写流程在外层照常渲染）")
    for token in ("current", "result.ok", "onClose", "onConfirm"):
        if token not in code:
            problems.append(f"[确认…] 的门控/次序应能看到 {token}（照 RoleBindForm 的既有写法）")
    css_pos = text.find("import './hub-bind-form.css';")
    if css_pos < 0:
        problems.append("应保留 import './hub-bind-form.css'（复用 .hb-* 类，不新建 CSS）")
    else:
        for stmt in re.findall(r"import[^;]*?from\s*['\"]\.\./[^'\"]+['\"]", text, re.S):
            if text.find(stmt) > css_pos:
                problems.append("import './hub-bind-form.css' 之后不应再有 '../…' 的 import")
                break
    for other_css in re.findall(r"import\s*['\"]([^'\"]+\.css)['\"]", text):
        if other_css != "./hub-bind-form.css":
            problems.append(f"不应引别的样式表（{other_css}；样式只复用 hub-bind-form.css）")
    problems.extend(_forbidden_marks("RoleBindForm.tsx", text, code))
    fail_if(problems, "RoleBindForm.tsx 的内外层拆分（S02）")


def test_s03_executor_test_file():
    """S03 / D06：执行端新测试文件 desktop/web/tests/writes-bind-reopen.test.tsx 在位且覆盖
    记号齐备（合同第 4 步点名的覆盖点：两个入口组件、setLiveClientForTests 注入假服务、
    rerender 模拟重读、取消后再开、再开先「预览中…」、两条写路由、真实计时器 450ms 等
    防抖），不许 skip/only/todo（T002 会扫全部 *.test.*）。"""
    need_file(EXEC_TEST_REL)
    text = read_rel(EXEC_TEST_REL)
    problems = []
    for token in EXECUTOR_TEST_TOKENS:
        if token not in text:
            problems.append(f"writes-bind-reopen.test.tsx 应含记号「{token}」（合同第 4 步点名的覆盖点）")
    problems.extend(_no_skip_marks(text))
    fail_if(problems, "执行端新测试文件（S03）")


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 T044/T045/T051 门禁的写法）
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
    return env


def git_status_set():
    proc = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
                          cwd=REPO_ROOT, capture_output=True, timeout=120)
    assert proc.returncode == 0, f"git status 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


def t052_marker_present():
    """候选里是否已有 T052 的标记（两个源文件的内层组件名）：没有就不起 npm（基线上必然没有）。"""
    try:
        hub = _read(REPO_ROOT / HUBBINDFORM_REL) if (REPO_ROOT / HUBBINDFORM_REL).is_file() else ""
        role = _read(REPO_ROOT / ROLEBINDFORM_REL) if (REPO_ROOT / ROLEBINDFORM_REL).is_file() else ""
    except OSError:
        return False
    return "HubBindFormDialog" in hub and "RoleBindFormDialog" in role


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t052_marker_present():
        pipe.reason = ("候选里还没有 T052 的标记（HubBindForm.tsx 的 HubBindFormDialog 或 RoleBindForm.tsx 的 "
                       "RoleBindFormDialog），没有东西可测，未调用 npm；候选把两个表单拆成内外层之后，"
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
                    missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                    if missing:
                        pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                        continue
                    name = f"probe-{uid}-t052-{key}.test.tsx"
                    probe_dir.mkdir(exist_ok=True)
                    path = probe_dir / name
                    written.append(path)
                    path.write_text(PROBE_SPECS[key][0], encoding="utf-8", newline="\n")
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
    want = probe_count(PROBE_SPECS[key][0])
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m and int(m.group(1)) >= want, f"探针 {key} 应至少有 {want} 条通过：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), f"探针 {key} 有失败或跳过：\n{step.tail}"


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


# ---------------------------------------------------------------------------
# 探针（黑盒 Vitest 用例，临时写进 desktop/web/gate-probe/，跑完即刪；每份自带全部辅助函数）
# ---------------------------------------------------------------------------

HUB_PROBE = r'''// T052 门禁 hub 探针：HubBindAction 的表单每次打开都按当时的 props 重新预填。直接渲染入口组件
// （照合同第 4 步的写法），用 rerender 模拟「重读之后 props 变了」，setLiveClientForTests 注入假服务
// 记录预览与写请求；不 mock 被测组件；真实计时器等防抖（sleep 450）。每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { HubBindAction } from '../src/writes/HubBindForm';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const BIND = '改绑定…';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
}
function btnIn(root: any, label: string): HTMLButtonElement {
  const hit = qa(root, 'button').find((b: any) => text(b) === label);
  expect(hit, '应有按钮「' + label + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}
function selectByLabel(d: HTMLElement, labelText: string): HTMLSelectElement {
  const label = qa(d, 'label').find((l: any) => text(l) === labelText);
  expect(label, '表单里应有 label「' + labelText + '」').toBeTruthy();
  const hit = qa(d, 'select').find((el: any) => el.id === (label as any).getAttribute('for'));
  expect(hit, 'label 关联的 select 应在表单里').toBeTruthy();
  return hit as HTMLSelectElement;
}

function okEnv<T>(data: T, command: string[] = []): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

let posts: Array<{ path: string; body: any }> = [];

const PREVIEW_COMMAND = ['config', 'hub', 'set', 'contract', 'quizs-m9', '--fallback=step-high', '--dry-run', '--json'];

// 写流程写前写后各读一次快照（useWriteFlow → getHubRoles → client.get('/api/v1/hub/roles')）：按路径返回
// 同一份常量，get 拿到数据才算 ok；写前写后快照没变 → 终态 done → 成功轻提示（照 T051 门禁的写法）。
const HUB_ROLES = { posts: [{ post: 'contract', source: 'config', profile: 'quizs-m9', fallback: { profile: 'step-high' } }] };

const fake: LiveClient = {
  get(path: string): Promise<any> {
    if (path === '/api/v1/hub/roles') return Promise.resolve(okEnv(HUB_ROLES));
    return Promise.resolve(okEnv(null));
  },
  post(path: string, body: unknown): Promise<any> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      const preview = {
        binding_changes: [], resources: [], notes: [], warnings: [], running_attempts: [],
        running_turns: [], needs_yes: false, hub_changes: [],
      };
      return Promise.resolve({ status: 200, body: okEnv({ preview, confirmation: 'c-real-1' }, PREVIEW_COMMAND) });
    }
    return Promise.resolve({ status: 200, body: okEnv(null, ['config', 'hub', 'set']) });
  },
  getRaw(): Promise<any> {
    return Promise.resolve({ status: 404, body: null });
  },
};

function props(over: Record<string, unknown> = {}): any {
  return {
    post: 'contract',
    postLabel: '合同端',
    mainCandidates: ['quizs-m9', 'step-high', 'step-low'],
    fallbackCandidatesFor: (m: string) => (m === 'quizs-m9' ? ['step-high', 'step-low'] : []),
    source: 'config',
    mainProfile: 'quizs-m9',
    fallbackProfile: 'step-high',
    reload: vi.fn(() => Promise.resolve()),
    ...over,
  };
}

beforeEach(() => {
  posts = [];
  setLiveClientForTests(fake);
  window.location.hash = '';
});
afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('HubBindForm：每次打开都按当时的绑定预填（D01、D03）', () => {
  it('(a) 改主选为非 quizs、点取消、再开 → 主选与替补回到现有绑定，替补可选', async () => {
    const r = render(<HubBindAction {...props()} />);
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    const main = selectByLabel(needDlg(), '主绑定');
    expect(main.value, '预填现有主绑定').toBe('quizs-m9');
    fireEvent.change(main, { target: { value: 'step-high' } });
    await flush();
    const fb = selectByLabel(needDlg(), '替补');
    expect(fb.disabled, '主选非 quizs → 替补禁用（既有行为）').toBe(true);
    expect(fb.value, '替补清空（既有行为）').toBe('');
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单对话框应关上').toBeNull();
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    const d = needDlg();
    expect(selectByLabel(d, '主绑定').value, '再开 → 主选回到现有绑定（丢弃未保存取值）').toBe('quizs-m9');
    const fb2 = selectByLabel(d, '替补');
    expect(fb2.disabled, '主选 quizs → 替补可选').toBe(false);
    expect(fb2.value, '再开 → 替补回到现有绑定').toBe('step-high');
  });

  it('(b) rerender 换了主绑定再开 → 按新绑定预填，预览请求的 args 是新绑定', async () => {
    const p = props();
    const r = render(<HubBindAction {...p} />);
    r.rerender(<HubBindAction {...p} mainProfile="step-high" fallbackProfile={null} />);
    await flush();
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    const d = needDlg();
    expect(selectByLabel(d, '主绑定').value, 'props 变了再开 → 预填新主绑定').toBe('step-high');
    expect(selectByLabel(d, '替补').value, '新绑定没有替补 → 空').toBe('');
    await sleep(450);
    await flush();
    const prev = posts.filter((x) => x.path === '/api/v1/preview').pop();
    expect(prev, '应发过预览').toBeTruthy();
    expect((prev!.body as any).args.profile, '预览请求的 args 按新绑定').toBe('step-high');
    expect((prev!.body as any).args.fallback, '替补为空不带 fallback').toBeUndefined();
  });

  it('(c) 现有主绑定不在候选里（预填第一个），rerender 加进候选后再开 → 预填现有主绑定；预览 args 与确认…可点', async () => {
    const p = props({ mainCandidates: ['step-high', 'step-low'], fallbackProfile: null });
    const r = render(<HubBindAction {...p} />);
    r.rerender(<HubBindAction {...p} mainCandidates={['quizs-m9', 'step-high', 'step-low']} />);
    await flush();
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    expect(selectByLabel(needDlg(), '主绑定').value, '现有主绑定进了候选 → 预填它').toBe('quizs-m9');
    await sleep(450);
    await flush();
    const prev = posts.filter((x) => x.path === '/api/v1/preview').pop();
    expect(prev, '应发过预览（不能只看 select.value：react-dom 会把第一个未禁用 option 设成 selected）').toBeTruthy();
    expect((prev!.body as any).args.profile, '预览请求的 args 是现有主绑定').toBe('quizs-m9');
    expect(btnIn(needDlg(), '确认…').disabled, '预览 ok 且对应当前取值 → 可确认').toBe(false);
  });

  it('(d) 确认：先关表单再开写确认框，发 POST /api/v1/hub/roles/contract，成功轻提示与 reload；再开按新绑定预填', async () => {
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<HubBindAction {...props({ reload })} />);
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '写确认框标题（表单已关上）').toContain('改绑定 contract？');
    expect(qa(cd, 'select').length, '写确认框里没有表单字段').toBe(0);
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(120);
    await flush();
    const writes = posts.filter((x) => x.path.indexOf('/api/v1/hub/roles/') === 0);
    expect(writes.length, '只发一次岗位写路由').toBe(1);
    expect(writes[0].path).toBe('/api/v1/hub/roles/contract');
    expect(writes[0].body.profile).toBe('quizs-m9');
    expect(writes[0].body.fallback).toBe('step-high');
    expect(typeof writes[0].body.confirmation).toBe('string');
    expect(text(document.body), '成功轻提示').toContain('已改绑定 contract');
    expect(reload, '成功后 reload').toHaveBeenCalled();
    r.rerender(<HubBindAction {...props({ reload, mainProfile: 'step-low', fallbackProfile: null })} />);
    await flush();
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    expect(selectByLabel(needDlg(), '主绑定').value, '写完重读后再开 → 按新绑定预填').toBe('step-low');
  });

  it('(e) 再开时底部先「预览中…」、确认… 灰着；新预览回来才可点；预览请求多一次', async () => {
    const r = render(<HubBindAction {...props()} />);
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    const before = posts.filter((x) => x.path === '/api/v1/preview').length;
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单对话框应关上').toBeNull();
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    const d = needDlg();
    expect(text(d), '再开先显示预览中…（不显示上一次的预览）').toContain('预览中…');
    expect(btnIn(d, '确认…').disabled, '新预览回来之前确认… 灰着').toBe(true);
    await sleep(450);
    await flush();
    expect(text(needDlg()), '新预览回来').toContain('config hub set contract quizs-m9 --fallback=step-high');
    expect(btnIn(needDlg(), '确认…').disabled, '新预览回来后可点').toBe(false);
    expect(posts.filter((x) => x.path === '/api/v1/preview').length, '再开又发一次预览').toBe(before + 1);
  });

  it('表单开着时 props 变了：不重置用户正在改的字段', async () => {
    const p = props();
    const r = render(<HubBindAction {...p} />);
    fireEvent.click(btnIn(r.container, BIND));
    await flush();
    const main = selectByLabel(needDlg(), '主绑定');
    fireEvent.change(main, { target: { value: 'step-low' } });
    await flush();
    r.rerender(<HubBindAction {...p} mainProfile="step-high" />);
    await flush();
    expect(selectByLabel(needDlg(), '主绑定').value, '用户正在改的主选不被重置').toBe('step-low');
  });
});
'''


ROLE_PROBE = r'''// T052 门禁 role 探针：RoleBindAction 的表单每次打开都按当时的 props 重新预填（与 hub 探针同形）。
// 直接渲染入口组件，用 rerender 模拟「重读之后 props 变了」，setLiveClientForTests 注入假服务记录预览
// 与写请求；不 mock 被测组件；真实计时器等防抖（sleep 450）。每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RoleBindAction } from '../src/writes/RoleBindForm';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const CHANGE = '更改…';
const REASON = '没有已登记的 profile，无头不可选：先在「CLI 运行时」页登记运行时，再新建 profile';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
}
function btnIn(root: any, label: string): HTMLButtonElement {
  const hit = qa(root, 'button').find((b: any) => text(b) === label);
  expect(hit, '应有按钮「' + label + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}
function selectByLabel(d: HTMLElement, labelText: string): HTMLSelectElement {
  const label = qa(d, 'label').find((l: any) => text(l) === labelText);
  expect(label, '表单里应有 label「' + labelText + '」').toBeTruthy();
  const hit = qa(d, 'select').find((el: any) => el.id === (label as any).getAttribute('for'));
  expect(hit, 'label 关联的 select 应在表单里').toBeTruthy();
  return hit as HTMLSelectElement;
}

function okEnv<T>(data: T, command: string[] = []): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

let posts: Array<{ path: string; body: any }> = [];

const PREVIEW_COMMAND = ['config', 'role', 'set', 'execution', 'step-high', '--dry-run', '--json'];

// 写流程写前写后各读一次快照（useWriteFlow → getRoles → client.get('/api/v1/roles')）：按路径返回同一份
// 常量，写前写后快照没变 → 终态 done → 成功轻提示（照 T051 门禁的写法）。
const ROLES_DATA = { roles: [{ role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' } }] };

const fake: LiveClient = {
  get(path: string): Promise<any> {
    if (path === '/api/v1/roles') return Promise.resolve(okEnv(ROLES_DATA));
    return Promise.resolve(okEnv(null));
  },
  post(path: string, body: unknown): Promise<any> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      const preview = {
        binding_changes: [], resources: [{ resource: 'roles' }], notes: [], warnings: [],
        running_attempts: [], running_turns: [], needs_yes: false, hub_changes: [],
      };
      return Promise.resolve({ status: 200, body: okEnv({ preview, confirmation: 'c-real-1' }, PREVIEW_COMMAND) });
    }
    return Promise.resolve({ status: 200, body: okEnv(null, ['config', 'role', 'set']) });
  },
  getRaw(): Promise<any> {
    return Promise.resolve({ status: 404, body: null });
  },
};

function roleProps(over: Record<string, unknown> = {}): any {
  return {
    role: 'execution',
    roleLabel: '执行端',
    modes: [{ value: 'headless', label: '无头' }],
    candidates: ['step-high', 'step-low'],
    binding: { mode: 'headless', profile: 'step-high', host: null, cadenceSeconds: null },
    reload: vi.fn(() => Promise.resolve()),
    ...over,
  };
}

function planningProps(over: Record<string, unknown> = {}): any {
  return {
    role: 'planning_review',
    roleLabel: '规划审核端',
    modes: [{ value: 'interactive_host', label: '交互式宿主' }, { value: 'headless', label: '无头' }],
    candidates: [],
    binding: { mode: 'interactive_host', profile: null, host: 'claude-code', cadenceSeconds: null },
    reload: vi.fn(() => Promise.resolve()),
    ...over,
  };
}

beforeEach(() => {
  posts = [];
  setLiveClientForTests(fake);
  window.location.hash = '';
});
afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('RoleBindForm：每次打开都按当时的绑定预填（D01、D03）', () => {
  it('(a) execution 改 profile、点取消、再开 → 回到现有 profile', async () => {
    const r = render(<RoleBindAction {...roleProps()} />);
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const d = needDlg();
    expect(text(d), '对话框标题').toContain('改绑定：执行端');
    const profile = selectByLabel(d, 'profile');
    expect(profile.value, '预填现有 profile').toBe('step-high');
    fireEvent.change(profile, { target: { value: 'step-low' } });
    await flush();
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单对话框应关上').toBeNull();
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    expect(selectByLabel(needDlg(), 'profile').value, '再开 → 回到现有 profile（丢弃未保存取值）').toBe('step-high');
  });

  it('(a2) planning_review 切无头、点取消、再开 → 回到交互式宿主（没有 profile 下拉）', async () => {
    const p = planningProps({ candidates: ['step-high', 'step-low'] });
    const r = render(<RoleBindAction {...p} />);
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const mode = selectByLabel(needDlg(), '模式');
    expect(mode.value, '预填现有模式').toBe('interactive_host');
    fireEvent.change(mode, { target: { value: 'headless' } });
    await flush();
    expect(qa(needDlg(), 'select').length, '无头 → 有 profile 下拉').toBe(2);
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单对话框应关上').toBeNull();
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const d = needDlg();
    expect(selectByLabel(d, '模式').value, '再开 → 回到交互式宿主').toBe('interactive_host');
    expect(qa(d, 'select').length, '不是无头 → 没有 profile 下拉').toBe(1);
  });

  it('(b) rerender 换了 binding.profile 再开 → 按新绑定预填，预览请求的 target 是新 profile', async () => {
    const p = roleProps();
    const r = render(<RoleBindAction {...p} />);
    r.rerender(<RoleBindAction {...p} binding={{ mode: 'headless', profile: 'step-low', host: null, cadenceSeconds: null }} />);
    await flush();
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    expect(selectByLabel(needDlg(), 'profile').value, 'props 变了再开 → 预填新 profile').toBe('step-low');
    await sleep(450);
    await flush();
    const prev = posts.filter((x) => x.path === '/api/v1/preview').pop();
    expect(prev, '应发过预览').toBeTruthy();
    expect((prev!.body as any).args.target, '预览请求的 target 是新 profile').toBe('step-low');
    expect((prev!.body as any).args.role).toBe('execution');
    expect((prev!.body as any).args.host, '现有绑定 host 为 null → 不带 host').toBeUndefined();
  });

  it('(c) planning_review 起初没有候选（无头拿掉、help 是原因句）；给候选后再开选无头 → target 是第一个候选，确认…可点', async () => {
    const p = planningProps();
    const r = render(<RoleBindAction {...p} />);
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const first = needDlg();
    expect(qa(selectByLabel(first, '模式'), 'option').map((o: any) => o.value), '没有候选 → 无头拿掉').toEqual(['interactive_host']);
    expect(text(first), '原因句在 Select 的 help 里').toContain(REASON);
    fireEvent.click(btnIn(first, '取消'));
    await flush();
    r.rerender(<RoleBindAction {...p} candidates={['quizs-m9', 'step-high']} />);
    await flush();
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const mode = selectByLabel(needDlg(), '模式');
    expect(mode.value, '再开仍预填现有模式').toBe('interactive_host');
    expect(qa(mode, 'option').map((o: any) => o.value), '有候选 → 无头回来了').toEqual(['interactive_host', 'headless']);
    fireEvent.change(mode, { target: { value: 'headless' } });
    await flush();
    const profile = selectByLabel(needDlg(), 'profile');
    expect(profile.value, 'profile 预填第一个候选').toBe('quizs-m9');
    await sleep(450);
    await flush();
    const prev = posts.filter((x) => x.path === '/api/v1/preview').pop();
    expect(prev, '应发过预览（不能只看 select.value：react-dom 会把第一个未禁用 option 设成 selected）').toBeTruthy();
    expect((prev!.body as any).args.target, '预览的 target 是第一个候选').toBe('quizs-m9');
    expect(btnIn(needDlg(), '确认…').disabled, '预览 ok 且对应当前取值 → 可确认').toBe(false);
  });

  it('(d) 确认：先关表单再开写确认框，发 POST /api/v1/roles/execution，成功轻提示与 reload；再开按新绑定预填', async () => {
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<RoleBindAction {...roleProps({ reload })} />);
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '写确认框标题（表单已关上）').toContain('改角色绑定 execution？');
    expect(qa(cd, 'select').length, '写确认框里没有表单字段').toBe(0);
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(120);
    await flush();
    const writes = posts.filter((x) => x.path === '/api/v1/roles/execution');
    expect(writes.length, '只发一次角色写路由').toBe(1);
    expect(writes[0].body, '正文恰好 target + confirmation').toEqual({ target: 'step-high', confirmation: 'c-real-1' });
    expect(text(document.body), '成功轻提示').toContain('已改角色绑定 execution');
    expect(reload, '成功后 reload').toHaveBeenCalled();
    r.rerender(<RoleBindAction {...roleProps({ reload, binding: { mode: 'headless', profile: 'step-low', host: null, cadenceSeconds: null } })} />);
    await flush();
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    expect(selectByLabel(needDlg(), 'profile').value, '写完重读后再开 → 按新绑定预填').toBe('step-low');
  });

  it('(e) 再开时底部先「预览中…」、确认… 灰着；新预览回来才可点；预览请求多一次', async () => {
    const r = render(<RoleBindAction {...roleProps()} />);
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    const before = posts.filter((x) => x.path === '/api/v1/preview').length;
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单对话框应关上').toBeNull();
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const d = needDlg();
    expect(text(d), '再开先显示预览中…（不显示上一次的预览）').toContain('预览中…');
    expect(btnIn(d, '确认…').disabled, '新预览回来之前确认… 灰着').toBe(true);
    await sleep(450);
    await flush();
    expect(text(needDlg()), '新预览回来').toContain('config role set execution step-high');
    expect(btnIn(needDlg(), '确认…').disabled, '新预览回来后可点').toBe(false);
    expect(posts.filter((x) => x.path === '/api/v1/preview').length, '再开又发一次预览').toBe(before + 1);
  });

  it('表单开着时 props 变了：不重置用户正在改的字段', async () => {
    const p = roleProps();
    const r = render(<RoleBindAction {...p} />);
    fireEvent.click(btnIn(r.container, CHANGE));
    await flush();
    const profile = selectByLabel(needDlg(), 'profile');
    fireEvent.change(profile, { target: { value: 'step-low' } });
    await flush();
    r.rerender(<RoleBindAction {...p} candidates={['quizs-m9', 'step-high', 'step-low']} />);
    await flush();
    expect(selectByLabel(needDlg(), 'profile').value, '用户正在改的 profile 不被重置').toBe('step-low');
  });
});
'''


PROBE_SPECS = {
    "hub": (HUB_PROBE, (HUBBINDFORM_REL,)),
    "role": (ROLE_PROBE, (ROLEBINDFORM_REL,)),
}
PROBE_ORDER = ("hub", "role")


# ---------------------------------------------------------------------------
# P 系列：流水线断言；D 系列：探针断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、D08：npm 依赖（已在就跳过重装）、npm test（全绿，含执行端新测试与既有包内测试）
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


def test_d01_hub_probe(pipeline):
    """hub 探针 / D01–D03：HubBindAction 的表单每次打开都按当时的 props 重新预填——改主选取消后再
    开回到现有绑定（替补可选）；rerender 换主绑定再开按新绑定预填且预览 args 是新绑定；现有主绑定
    进了新增候选再开预填它（预览 args 与 [确认…] 可点，不能只看 select.value）；确认先关表单再开
    写确认框、发 POST /api/v1/hub/roles/<post>、成功轻提示与 reload、写完再开按新绑定预填；再开先
    「预览中…」[确认…] 灰到新预览回来且预览请求多一次；表单开着时 props 变了不重置用户正在改的
    字段（写流程留在外层也由 (d) 把关：搬进内层则表单一关写确认框不会出现）。"""
    assert_probe_ok(pipeline, "hub")


def test_d02_role_probe(pipeline):
    """role 探针 / D01–D03：RoleBindAction 的表单每次打开都按当时的 props 重新预填——execution 改
    profile 取消后再开回到现有 profile、planning_review 切无头取消后再开回到交互式宿主（没有
    profile 下拉）；rerender 换 binding.profile 再开按新绑定预填且预览 target 是新 profile；
    planning_review 起初没有候选（无头拿掉、help 是原因句）给候选后再开选无头、预览 target 是第一
    个候选且 [确认…] 可点；确认先关表单再开写确认框、发 POST /api/v1/roles/<role>、成功轻提示与
    reload、写完再开按新绑定预填；（e）与表单开着不重置同 hub。"""
    assert_probe_ok(pipeline, "role")
