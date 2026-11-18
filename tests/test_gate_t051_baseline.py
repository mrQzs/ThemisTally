"""T051 战前门禁：桌面端前端「角色卡的 [更改…]——四个派遣角色在界面里换绑定」的黑盒基准测试
（合同 t051-desktop-web-role-bind.v1，基线 65c2e3bf）。

被测对象是 ``desktop/web/`` 前端「角色与模型」页四张角色卡的换绑定写入口（写动作 ``role.set``、
执行打 ``POST /api/v1/roles/<role>``）：

- ``src/api.ts``：``WriteAction`` 加 ``'role.set'``（既有 12 个成员一个不丢）；``writeArgs`` 把
  ``cadence_seconds`` 与 ``number`` 键同一条规则转成 JSON 数字（预览与执行共用）；新导出
  ``setRoleBinding``（真实模式 ``POST /api/v1/roles/<encodeURIComponent(role)>``，正文是
  ``target`` + 可选 ``host`` + 可选 ``cadence_seconds`` + ``confirmation``，role 不进正文；
  桩模式走 ``mockSetRoleBinding``）。
- ``src/mock/writes.ts``：``baseArgv`` 加 ``role.set`` 分支（``config role set <role> <target>``
  加 ``--host=``/``--cadence-seconds=``）；``NEW_ACTIONS`` 加 ``role.set``；``previewData`` 加
  ``role.set`` 分支（``binding_changes`` 至多一项，from 取夹具当前绑定的显示值、to 取 target，
  两者相同不给；``resources: ['roles']``）；新导出 ``mockSetRoleBinding``；**``WriteScenario``
  一个值都不加（仍 27 个）**。
- ``src/writes/useLivePreview.ts``：只加 ``bindingChanges: BindingChange[]`` 一个字段
  （LivePreview、fromReply、失败分支字面量三处）；开头两行注释与 ``DEBOUNCE_MS = 300`` 不动。
- ``src/writes/snapshots.ts``：只加 ``RoleSnapshot`` 与 ``roleSnapshot(roles)``（投影
  ``roles[].{role, explicit, binding}``，按 role 排序）；既有导出不变。
- ``src/writes/useWriteFlow.ts``：``role.set`` 的三条文字（``改角色绑定 <role>？`` /
  ``已改角色绑定 <role>`` / ``角色 <role> 的绑定改成 <target>``，带 host/cadence 追加）、
  快照分支（``getRoles()`` + ``roleSnapshot``）、执行分派（``setRoleBinding``，排在
  ``setPluginEnabled`` 兜底之前）；既有动作的文字与分支不变；``role.set`` 不是危险动作。
- ``src/pages/readonly1/roles-logic.ts``：新导出 ``allowedModes``（四个角色各自的允许模式、
  未知角色给 []）、``profileIds``（按输入顺序、滤掉 ``_`` 开头的 id）与 ``ROLE_MODES`` 表；
  ``RoleInfo`` 加 ``cadenceSeconds``（整数才给数，其余 null）；该文件仍只 ``import type``。
- ``src/writes/RoleBindForm.tsx``（新）：入口组件 ``RoleBindAction`` 与「改绑定」表单（模式 /
  profile 两个 Select、底部 ``useLivePreview('role.set')`` 实时预览、``[确认…]`` 门控、
  ``<WriteFlow flow={flow} />``）；原因句常量逐字在位；按钮 textContent 恰为「更改…」
  （secondary/sm）；样式复用 ``hub-bind-form.css``；不跨层引 ``src/pages``。
- ``src/pages/readonly1/roles-RoleCard.tsx``：卡底换成 ``<RoleBindAction … />``；新 props
  ``candidates?`` 与 ``reload?`` 都可选（两 prop 写法照旧编译）；只读部分一个字不改。
- ``src/pages/readonly1/roles-RolesView.tsx``：给每张卡传 ``candidates`` 与 ``reload``。
- 执行端新测试文件 ``desktop/web/tests/writes-role-bind.test.tsx`` 覆盖合同第 11 步点名的每一项。

基线（65c2e3bf）上 ``role.set``、``allowedModes``、``bindingChanges``、``roleSnapshot``、
``RoleBindForm.tsx`` 与可点的 [更改…] 都不存在，所以本文件的失败落在「记号不在」「文件不存在」
这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有仓库文件的读取都发生在用例
函数里；流水线（npm、Vitest、探针）放在 ``pipeline`` 会话级夹具里（全量 pytest 默认跳过，
点名运行本文件才跑；候选里还没有本片的文件时夹具不调 npm——照 T024/T040/T041/T043/T044/
T045 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线）：api.ts 的 role.set 与 setRoleBinding（S01）；mock/writes.ts
  的四处与 WriteScenario 恰 27（S02）；useLivePreview 的 bindingChanges 与钉住项（S03）；
  snapshots 的 roleSnapshot（S04）；useWriteFlow 的三条文字与两个分支（S05）；roles-logic 的
  两个新导出与 cadenceSeconds（S06）；RoleBindForm 新文件（S07）；RoleCard/RolesView 接线
  （S08）；执行端新测试文件在位且要点齐备（S09）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、
  npm test 全绿；两份探针逐份写成 ``gate-probe/probe-<uid>-t051-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除。探针用 ``setLiveClientForTests``
  注入假服务（照 tests/writes-hub-bind.test.tsx 的写法），不 mock 被测组件；每份自带全部辅助
  函数，不跨文件共享作用域。
  - unit：allowedModes/profileIds 的边界、normalizeRole 的 cadenceSeconds、mockPreview 的
    role.set 分支（命令与 binding_changes）、useLivePreview 的 bindingChanges、roleSnapshot、
    setRoleBinding 的正文（键恰好、cadence 是 JSON 数字）。
  - page：桩模式挂 App——四张卡的 [更改…] 可点（secondary/sm）、角色页禁用数 7、四个角色各自
    的模式选项与预填、无头时 profile 下拉、底部命令与前后对比、确认先关表单再开写确认框、成功
    轻提示、预览失败时确认不可点、对话框关着不渲染候选；真实模式（注入假服务）——确认发
    ``POST /api/v1/roles/<role>``（正文的键恰好、host/cadence 的原样传回、cadence 是数字）、
    写完重读、没有 profile 时 execution 入口禁用（悬停出原因句）与其余三个角色模式下拉没有
    「无头」（原因句在 Select 的 help 里）、未知角色码入口禁用（缺省原因句）。

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
PAGES_RO = f"{SRC_REL}/pages/readonly1"
TESTS_REL = f"{WEB_REL}/tests"

API_REL = f"{SRC_REL}/api.ts"
MOCK_WRITES_REL = f"{SRC_REL}/mock/writes.ts"
LIVEPREVIEW_REL = f"{WRITES_REL}/useLivePreview.ts"
SNAPSHOTS_REL = f"{WRITES_REL}/snapshots.ts"
USEWRITEFLOW_REL = f"{WRITES_REL}/useWriteFlow.ts"
ROLEBINDFORM_REL = f"{WRITES_REL}/RoleBindForm.tsx"
ROLES_LOGIC_REL = f"{PAGES_RO}/roles-logic.ts"
ROLECARD_REL = f"{PAGES_RO}/roles-RoleCard.tsx"
ROLESVIEW_REL = f"{PAGES_RO}/roles-RolesView.tsx"
MOCK_ROLES_REL = f"{SRC_REL}/mock/roles.json"
MOCK_PROFILES_REL = f"{SRC_REL}/mock/profiles.json"
EXEC_COMP_TEST_REL = f"{TESTS_REL}/writes-role-bind.test.tsx"

# api.ts 既有的 12 个 WriteAction 成员（合同兼容性：一个不许丢；t041/t043/t044 是包含式核对）
OLD_WRITE_ACTIONS = (
    "preset.use", "plugin.enable", "plugin.disable", "preset.remove", "profile.remove",
    "runtime.remove", "config.rollback", "profile.add", "profile.edit", "hub.set", "hub.unset",
    "runtime.add",
)

# useLivePreview.ts 开头两行注释（T040/T045 钉住；合同：一字不动）
PREVIEW_LINE_1 = "// 表单底部的实时内核预览（合同第三节）：表单合法才在 300ms 防抖后调 preview；迟到的回应按序号丢弃。"
PREVIEW_LINE_2 = "// 夹具模式下读演示数据，真实模式下走服务的预览。"
# LivePreview 既有的七个字段（合同：只加 bindingChanges 一个，不改既有字段语义）
OLD_PREVIEW_FIELDS = ("key", "ok", "command", "warnings", "error", "hubChanges", "runningTurns")

# snapshots.ts 既有的导出（合同：只加 RoleSnapshot 与 roleSnapshot）
OLD_SNAPSHOT_EXPORTS = (
    "presetSnapshot", "pluginSnapshot", "presetRemoveSnapshot", "profileRemoveSnapshot",
    "runtimeRemoveSnapshot", "profileSnapshot", "rollbackSnapshot", "hubSnapshot", "sameSnapshot",
)

# roles-logic.ts 既有的导出（合同：签名与行为不变，只加新导出与 RoleInfo.cadenceSeconds）
OLD_LOGIC_EXPORTS = (
    "roleName", "modeName", "normalizeRole", "resolvedProfile", "profileRefs", "presetRoleTitle",
    "bindingText", "hubPostName", "allowedProfiles", "normalizeHubPost", "hubFallbackCandidates",
)

# 四个派遣角色（mock/roles.json 与 scripts/kit_roles.py 的 ROLE_MODES 同一张表）
ROLE_CODES = ("planning_review", "contract", "execution", "scheduler_agent")
ROLE_LABELS = {
    "planning_review": "规划审核端",
    "contract": "合同端",
    "execution": "执行端",
    "scheduler_agent": "调度代理",
}
MODE_LABELS = {
    "headless": "无头",
    "interactive_host": "交互式宿主",
    "manual": "手工",
    "disabled": "关闭",
}
ALLOWED_MODES = {
    "planning_review": ["interactive_host", "headless"],
    "contract": ["manual", "headless"],
    "execution": ["headless"],
    "scheduler_agent": ["disabled", "headless"],
}

# 入口按钮（合同：textContent 恰为这两个字，U+2026；secondary/sm）
BUTTON_CHANGE = "更改…"
# 禁用原因句（合同 Behavior contract 与写法钉死第 4 条，逐字；与 HubBindForm 的那句逐字不同）
REASON_NO_PROFILES = "没有已登记的 profile，无头不可选：先在「CLI 运行时」页登记运行时，再新建 profile"
# 未知角色码走 DisabledAction 缺省的 reason（合同边界输入：不传 reason）
REASON_DEFAULT = "第二阶段接入"

# useWriteFlow 的三条文字（合同写法钉死第 8 条，逐字）
WF_TITLE = "`改角色绑定 ${args.role}？`"
WF_SUCCESS = "`已改角色绑定 ${args.role}`"
WF_SUMMARY = "`角色 ${args.role} 的绑定改成 ${args.target}`"

# 桩下角色页禁用按钮数（page-app 的口径，T053 之后）：方案条「切换…」1 +
# planner 无候选的「改绑定…」1 + 四个缺省行的「恢复缺省…」4 = 6（[保存当前为方案…] 变可点）
ROLES_PAGE_DISABLED = 6

# mock/writes.ts 的 WriteScenario 恰 27 个值（T044 S07 钉死；本片一个都不许加）
WRITE_SCENARIO_COUNT = 27

# 执行端新测试文件的最小覆盖记号（合同第 11 步点名的覆盖点）
EXECUTOR_TEST_TOKENS = (
    "allowedModes", "profileIds", "setLiveClientForTests", "/api/v1/roles/", "cadence_seconds",
    "host", "reload", "无头", BUTTON_CHANGE, REASON_NO_PROFILES,
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

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T024/T041/T043/T044/T045 门禁）
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 150}

ASSUMPTIONS = (
    "「确认…」先关表单再 start 的次序按行为断言（点表单的 [确认…] 后表单对话框关上、写确认框开上），"
    "不静态钉源码里的调用次序",
    "探针断言底部命令用「去掉 --dry-run/--json 后的 argv 空格连接」的子串（dispatchCommand 的输出），"
    "不钉 bash scripts/dispatch-pi.sh 前缀",
    "「模式」Select 只钉选项的 label（照 modeName 的中文名）与次序，不钉 option 的 value 写法；"
    "「profile」Select 的选项 value 与 label 都是 profile id（target 要原样进 WriteArgs）",
    "表单的取消钮照 HubBindForm 的既有形状（取消），写流程终态的确认钮照 WriteConfirmDialog 的既有形状"
    "（知道了）——本片不改这两个共享形状，探针直接用这两个字样",
    "执行端测试文件的覆盖记号是最低要求（有这些记号才说明测到了合同点名的那几件事）；运行时行为由两份"
    "探针独立钉住",
    "六个旧断言（t009/t024/t045、page-roles、page-app、writes-hub-bind）由执行端照合同 Steps 第 10 步"
    "逐字改；本文件不断言它们的文本——改完的 t009/t024/t045 自己在 R01 里把关，两处包内测试的数字"
    "由本文件流水线的 npm test（V01）把关",
    "悬停原因句用真实计时器（mouseEnter 后等 500ms）核对 Tooltip 文本，照 t009 的行为断言口径",
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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043/T044/T045 的同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def _block(text, start_marker, end_marker="\n}"):
    """从 start_marker 起到 end_marker 止的一段（函数体/接口切片用）。"""
    start = text.find(start_marker)
    if start < 0:
        return ""
    end = text.find(end_marker, start)
    return text[start:end if end >= 0 else len(text)]


def _no_skip_marks(text):
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
        if re.search(bad, text):
            problems.append(f"出现 {bad}（不许 skip、only、todo）")
    return problems


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_api_role_set():
    """S01 / D01、写法钉死第 1 条：api.ts 的 WriteAction 联合类型加 ``  | 'role.set'``（既有 12 个
    成员一个不丢）；writeArgs 把 cadence_seconds 与 number 键同一条规则转成 JSON 数字；新导出
    setRoleBinding（签名照写法钉死；真实模式 POST /api/v1/roles/<encodeURIComponent(role)>，
    正文 { ...writeArgs(w), confirmation }；桩模式 mockSetRoleBinding）。"""
    need_file(API_REL)
    text = read_rel(API_REL)
    code = strip_ts_comments(text)
    problems = []
    if "\n  | 'role.set'" not in text:
        problems.append("WriteAction 联合类型应加一行 `  | 'role.set'`（写法钉死第 1 条）")
    for member in OLD_WRITE_ACTIONS:
        if f"| '{member}'" not in code:
            problems.append(f"WriteAction 既有成员 '{member}' 应保留（一个不许丢）")
    wa = _block(code, "function writeArgs")
    if not wa:
        problems.append("api.ts 应保留 writeArgs")
    else:
        if "'cadence_seconds'" not in wa:
            problems.append("writeArgs 应把 cadence_seconds 纳入转 JSON 数字的规则（与 number 键同一条）")
        if "asNumber(" not in wa:
            problems.append("writeArgs 应沿用 asNumber 转数字（既有规则不变）")
    if "export function setRoleBinding(" not in code:
        problems.append("api.ts 应导出 export function setRoleBinding(（写法钉死第 1 条）")
    else:
        fn = _block(code, "export function setRoleBinding(")
        for token in ("role: string", "target: string", "host?", "cadence_seconds?", "confirmation: string"):
            if token not in fn:
                problems.append(f"setRoleBinding 的签名应含 {token}（写法钉死第 1 条）")
        if "/api/v1/roles/${encodeURIComponent(args.role)}" not in fn:
            problems.append("真实模式的路径应写成 `/api/v1/roles/${encodeURIComponent(args.role)}`")
        if "{ ...writeArgs(w), confirmation }" not in fn:
            problems.append("正文应恰是 { ...writeArgs(w), confirmation }（role 不进正文）")
        if "mockSetRoleBinding(" not in fn:
            problems.append("桩模式应调 mockSetRoleBinding")
    fail_if(problems, "api.ts 的 role.set 与 setRoleBinding（S01）")


def test_s02_mock_writes_role_set():
    """S02 / D02、写法钉死第 2 条：mock/writes.ts 认 role.set——baseArgv 分支
    （['config','role','set',s.role,s.target] 加 --host=/--cadence-seconds=）；NEW_ACTIONS 加
    'role.set'；previewData 加 role.set 分支（resources: ['roles']）；新导出 mockSetRoleBinding
    （内部 confirmWrite('role.set', …)）；WriteScenario 一个值都不加（仍恰 27 个）。"""
    need_file(MOCK_WRITES_REL)
    text = read_rel(MOCK_WRITES_REL)
    code = strip_ts_comments(text)
    problems = []
    base = _block(code, "function baseArgv")
    if not base:
        problems.append("mock/writes.ts 应保留 baseArgv")
    else:
        if "['config', 'role', 'set', s.role, s.target]" not in base:
            problems.append("baseArgv 应加 role.set 分支 ['config', 'role', 'set', s.role, s.target]（逐字照服务侧）")
        if "'--host=' + s.host" not in base:
            problems.append("baseArgv 的 role.set 分支有 host 时应追加 '--host=' + s.host")
        if "'--cadence-seconds=' + s.cadence_seconds" not in base:
            problems.append("baseArgv 的 role.set 分支有 cadence_seconds 时应追加 '--cadence-seconds=' + s.cadence_seconds")
    new_actions = re.search(r"const NEW_ACTIONS = new Set<string>\(\[(.*?)\]\)", code, re.S)
    if not new_actions:
        problems.append("mock/writes.ts 应保留 NEW_ACTIONS")
    elif "'role.set'" not in new_actions.group(1):
        problems.append("NEW_ACTIONS 应加 'role.set'（写函数核对确认号与参数）")
    prev = _block(code, "function previewData")
    if not prev:
        problems.append("mock/writes.ts 应保留 previewData")
    else:
        role_set_at = prev.find("'role.set'")
        if role_set_at < 0:
            problems.append("previewData 应加 role.set 分支（binding_changes 至多一项、resources 是 roles）")
        else:
            branch = prev[role_set_at:role_set_at + 700]
            if "binding_changes" not in branch:
                problems.append("previewData 的 role.set 分支应算 binding_changes（其余动作都不动）")
            if "resources: ['roles']" not in branch:
                problems.append("previewData 的 role.set 分支应写 resources: ['roles']")
    fn = _block(code, "export function mockSetRoleBinding")
    if not fn:
        problems.append("mock/writes.ts 应导出 export function mockSetRoleBinding(")
    elif "confirmWrite('role.set'" not in fn:
        problems.append("mockSetRoleBinding 应走既有 confirmWrite('role.set', …)（确认号与参数核对与其余动作同款）")
    scenario_type = re.search(r"export type WriteScenario\s*=([^;]*);", text, re.S)
    if not scenario_type:
        problems.append("mock/writes.ts 应保留 export type WriteScenario")
    else:
        values = re.findall(r"\|\s*'([a-z0-9-]+)'", scenario_type.group(1))
        if len(values) != WRITE_SCENARIO_COUNT or len(set(values)) != len(values):
            problems.append(f"WriteScenario 应仍恰 {WRITE_SCENARIO_COUNT} 个值一个不加（T044 S07），实际 {len(values)}")
    fail_if(problems, "mock/writes.ts 的 role.set（S02）")


def test_s03_live_preview_binding_changes():
    """S03 / D03、写法钉死第 3 条：useLivePreview.ts 只加一个字段 bindingChanges——LivePreview
    接口里 ``bindingChanges: BindingChange[];``（占一行）；import 行扩成含 type BindingChange；
    fromReply 写 ``bindingChanges: data?.binding_changes ?? []``；useEffect 失败分支的字面量补
    ``bindingChanges: [],``；开头两行注释与 DEBOUNCE_MS = 300 一字不动，防抖与序号丢弃逻辑
    不动；既有七个字段保留。"""
    need_file(LIVEPREVIEW_REL)
    text = read_rel(LIVEPREVIEW_REL)
    code = strip_ts_comments(text)
    problems = []
    lines = text.split("\n")
    if len(lines) < 2 or lines[0] != PREVIEW_LINE_1:
        problems.append("useLivePreview.ts 第 1 行注释应一字不动（T040/T045 钉住）")
    if len(lines) < 3 or lines[1] != PREVIEW_LINE_2:
        problems.append("useLivePreview.ts 第 2 行注释应一字不动（T040/T045 钉住）")
    if "const DEBOUNCE_MS = 300;" not in code:
        problems.append("const DEBOUNCE_MS = 300; 应在位（T024/T040/T045 钉住）")
    api_imports = re.findall(r"import[^;]*?from\s*['\"]\.\./api['\"]", text, re.S)
    if not api_imports or not any("type BindingChange" in stmt for stmt in api_imports):
        problems.append("import 那行应扩成含 type BindingChange（写法钉死第 3 条）")
    interface = _block(code, "export interface LivePreview")
    if not interface:
        problems.append("useLivePreview.ts 应保留 export interface LivePreview")
    else:
        if not re.search(r"^\s*bindingChanges\s*:\s*BindingChange\[\]\s*;?$", interface, re.M):
            problems.append("LivePreview 应加字段 bindingChanges: BindingChange[]（占一行；不是可选）")
        for field in OLD_PREVIEW_FIELDS:
            if not re.search(rf"^\s*{field}\s*:", interface, re.M):
                problems.append(f"LivePreview 既有字段 {field} 应保留")
    from_reply = _block(code, "function fromReply")
    if not from_reply:
        problems.append("useLivePreview.ts 应保留 fromReply")
    elif "bindingChanges: data?.binding_changes ?? []" not in from_reply:
        problems.append("fromReply 应写 bindingChanges: data?.binding_changes ?? []（缺键按空数组）")
    effect = _block(code, "useEffect(() => {")
    if not effect:
        problems.append("useLivePreview.ts 应保留 useEffect（防抖与序号逻辑）")
    else:
        fail_branch = re.search(r"setResult\(\{[^}]*预览失败：服务没有回应", effect, re.S)
        if not fail_branch:
            problems.append("useEffect 的失败分支字面量应在位")
        else:
            literal = effect[fail_branch.start():effect.find("}", fail_branch.start())]
            if "bindingChanges: []" not in literal:
                problems.append("useEffect 失败分支的字面量应补 bindingChanges: []（写法钉死第 3 条）")
    for token in ("seqRef.current += 1", "setTimeout(", "clearTimeout(timer)", "my === seqRef.current"):
        if token not in code:
            problems.append(f"防抖与序号丢弃逻辑应原样保留（看不到 {token}）")
    fail_if(problems, "useLivePreview.ts 的 bindingChanges（S03）")


def test_s04_snapshots_role_snapshot():
    """S04 / D03：snapshots.ts 只加 RoleSnapshot 与 roleSnapshot（投影 roles[].{role, explicit,
    binding}，按 role 排序，与 presetSnapshot 的角色投影同口径）；既有导出一个不变。"""
    need_file(SNAPSHOTS_REL)
    text = read_rel(SNAPSHOTS_REL)
    code = strip_ts_comments(text)
    problems = []
    if "export interface RoleSnapshot" not in code:
        problems.append("snapshots.ts 应导出 export interface RoleSnapshot（合同 Steps 第 5 步）")
    fn = _block(code, "export function roleSnapshot")
    if not fn:
        problems.append("snapshots.ts 应导出 export function roleSnapshot(roles: RolesData)")
    else:
        if "RolesData" not in fn:
            problems.append("roleSnapshot 的参数应是 RolesData")
        if not re.search(r"role:\s*r\.role", fn) or not re.search(r"explicit:\s*r\.explicit", fn) \
                or not re.search(r"binding:\s*r\.binding", fn):
            problems.append("roleSnapshot 的投影应只留 role/explicit/binding（照 presetSnapshot 的角色投影）")
    for name in OLD_SNAPSHOT_EXPORTS:
        if f"export function {name}(" not in code:
            problems.append(f"既有导出 {name} 应保留（只加不刪）")
    fail_if(problems, "snapshots.ts 的 roleSnapshot（S04）")


def test_s05_write_flow_role_set():
    """S05 / D04、写法钉死第 8 条：useWriteFlow.ts 认 role.set——三条文字逐字
    （改角色绑定 <role>？ / 已改角色绑定 <role> / 角色 <role> 的绑定改成 <target>，带 host 追加
    （宿主 …），带 cadence 追加（间隔 …秒））；readSnapshot 的 role.set 分支读 getRoles() +
    roleSnapshot；confirm 的分派链里 role.set → setRoleBinding（排在 setPluginEnabled 兜底之前）；
    既有动作的文字与分支不变；role.set 不进危险列表。"""
    need_file(USEWRITEFLOW_REL)
    text = read_rel(USEWRITEFLOW_REL)
    code = strip_ts_comments(text)
    problems = []
    title = _block(code, "function titleOf")
    if not title:
        problems.append("useWriteFlow.ts 应保留 titleOf")
    else:
        if WF_TITLE not in title:
            problems.append(f"titleOf 应加 {WF_TITLE}（逐字，写法钉死第 8 条）")
        if "`改绑定 ${args.post}？`" not in title:
            problems.append("titleOf 既有文字不变（看不到 hub.set 的改绑定标题）")
    success = _block(code, "function successTextOf")
    if not success:
        problems.append("useWriteFlow.ts 应保留 successTextOf")
    else:
        if WF_SUCCESS not in success:
            problems.append(f"successTextOf 应加 {WF_SUCCESS}（逐字）")
        if "`已改绑定 ${args.post}`" not in success:
            problems.append("successTextOf 既有文字不变（看不到 hub.set 的已改绑定）")
    summary = _block(code, "function changeSummaryOf")
    if not summary:
        problems.append("useWriteFlow.ts 应保留 changeSummaryOf")
    else:
        if WF_SUMMARY not in summary:
            problems.append(f"changeSummaryOf 应加 {WF_SUMMARY}（逐字）")
        if "（宿主 " not in summary or "（间隔 " not in summary or "秒）" not in summary:
            problems.append("changeSummaryOf 的 role.set 摘要应按 host/cadence 追加（宿主 …）与（间隔 …秒）")
        if "岗位 ${args.post} 的主绑定改成" not in summary:
            problems.append("changeSummaryOf 既有文字不变（看不到 hub.set 的摘要）")
    read_snap = _block(code, "async function readSnapshot")
    if not read_snap:
        problems.append("useWriteFlow.ts 应保留 readSnapshot")
    else:
        role_set_at = read_snap.find("'role.set'")
        if role_set_at < 0:
            problems.append("readSnapshot 应加 role.set 分支")
        else:
            branch = read_snap[role_set_at:role_set_at + 500]
            if "getRoles()" not in branch:
                problems.append("readSnapshot 的 role.set 分支应读 getRoles()")
            if "roleSnapshot(" not in branch:
                problems.append("readSnapshot 的 role.set 分支应用 roleSnapshot（与 presetSnapshot 的角色投影同口径）")
    imports = re.findall(r"import[^;]*?from\s*['\"]\.\/snapshots['\"]", text, re.S)
    if not any("roleSnapshot" in stmt for stmt in imports):
        problems.append("useWriteFlow.ts 应从 './snapshots' 引 roleSnapshot")
    confirm = _block(code, "const confirm = useCallback")
    if not confirm:
        problems.append("useWriteFlow.ts 应保留 confirm 的分派链")
    else:
        dispatch_at = confirm.find("setRoleBinding(")
        fallback_at = confirm.find("setPluginEnabled(")
        if dispatch_at < 0:
            problems.append("confirm 的分派链应加 role.set → setRoleBinding(…)")
        elif fallback_at >= 0 and dispatch_at > fallback_at:
            problems.append("role.set 分支应排在 setPluginEnabled 兜底之前（否则 role.set 会落进插件启停）")
    danger = _block(code, "function dangerOf")
    if danger and "'role.set'" in danger:
        problems.append("role.set 不是危险动作（确认钮 primary，与 hub.set 同款；不应进危险列表）")
    fail_if(problems, "useWriteFlow.ts 的 role.set（S05）")


def test_s06_roles_logic_new_exports():
    """S06 / D05、写法钉死第 5 条：roles-logic.ts 加 ROLE_MODES 表（注释写明出自
    scripts/kit_roles.py）、allowedModes(code: string): string[]（未知角色给 []）、
    profileIds（按输入顺序返回 id，滤掉 _ 开头）；RoleInfo 加 cadenceSeconds: number | null；
    RawRole 的 binding 收 cadence_seconds；既有导出一个不变；该文件仍只 import type。"""
    need_file(ROLES_LOGIC_REL)
    text = read_rel(ROLES_LOGIC_REL)
    code = strip_ts_comments(text)
    problems = []
    if "ROLE_MODES" not in code:
        problems.append("roles-logic.ts 应加 ROLE_MODES 表（合同 Steps 第 7 步）")
    if "kit_roles.py" not in text:
        problems.append("ROLE_MODES 表的注释应写明出自 scripts/kit_roles.py（合同 Steps 第 7 步）")
    allowed = re.search(r"export function allowedModes\(([^)]*)\)\s*:\s*string\[\]", code)
    if not allowed:
        problems.append("roles-logic.ts 应导出 export function allowedModes(code: string): string[]（写法钉死第 5 条）")
    elif "code" not in allowed.group(1):
        problems.append("allowedModes 的签名应有参数 code")
    ids = _block(code, "export function profileIds")
    if not ids:
        problems.append("roles-logic.ts 应导出 export function profileIds(（写法钉死第 5 条）")
    else:
        if "ProfilesData" not in ids:
            problems.append("profileIds 的参数应是 ProfilesData 的 profiles 行数组")
        if "'_'" not in ids and '"_"' not in ids:
            problems.append("profileIds 应滤掉以 _ 开头的 id（内核把它们当未登记）")
    interface = _block(code, "export interface RoleInfo")
    if not interface:
        problems.append("roles-logic.ts 应保留 export interface RoleInfo")
    elif not re.search(r"^\s*cadenceSeconds\s*:\s*number \| null\s*;?$", interface, re.M):
        problems.append("RoleInfo 应加字段 cadenceSeconds: number | null（占一行；不是可选）")
    if "cadence_seconds" not in code:
        problems.append("roles-logic.ts 应收 binding 的 cadence_seconds（RawRole/归一）")
    for name in OLD_LOGIC_EXPORTS:
        if not re.search(rf"export function {name}\(", code):
            problems.append(f"既有导出 {name} 应保留（签名与行为不变）")
    imports = re.findall(r"import[^;]*?from\s*['\"][^'\"]+['\"]", text)
    for stmt in imports:
        if not stmt.lstrip().startswith("import type"):
            problems.append(f"roles-logic.ts 只许 import type（T038 S07）：{stmt.strip()[:60]}")
    fail_if(problems, "roles-logic.ts 的新导出（S06）")


def test_s07_role_bind_form_file():
    """S07 / D06、D08、写法钉死第 4 条：新文件 src/writes/RoleBindForm.tsx——从 ../api 只
    import type；导出 export function RoleBindAction(；原因句常量逐字在位；对话框标题
    改绑定：${roleLabel}；两个 Select 的 label 是「模式」与「profile」；按钮文字恰为「更改…」
    （secondary/sm）；样式复用 import './hub-bind-form.css'（放在组件 import 之后）；
    useLivePreview('role.set') 与 <WriteFlow flow={flow} />；无候选时无头从模式列表拿掉、
    execution 无候选时入口是 DisabledAction；不跨层引 src/pages；不写死颜色、不出现网络词
    与 role="status"。"""
    need_file(ROLEBINDFORM_REL)
    text = read_rel(ROLEBINDFORM_REL)
    code = strip_ts_comments(text)
    problems = []
    for stmt in re.findall(r"import[^;]*?from\s*['\"]\.\./api['\"]", text, re.S):
        if not stmt.lstrip().startswith("import type"):
            problems.append(f"RoleBindForm.tsx 从 ../api 只许 import type：{stmt.strip()[:60]}")
    if "export function RoleBindAction(" not in code:
        problems.append("RoleBindForm.tsx 应导出 export function RoleBindAction(（写法钉死第 4 条）")
    if REASON_NO_PROFILES not in text:
        problems.append("没有已登记 profile 的原因句应逐字在位（合同 Behavior contract；只写在 src/writes）")
    if "改绑定：${roleLabel}" not in text:
        problems.append("对话框标题应由本文件拼：改绑定：${roleLabel}（写法钉死第 4 条）")
    if 'label="模式"' not in code:
        problems.append("模式 Select 的 label 应恰为「模式」（写法钉死第 4 条）")
    if 'label="profile"' not in code:
        problems.append("profile Select 的 label 应恰为「profile」（写法钉死第 4 条）")
    if BUTTON_CHANGE not in code:
        problems.append(f"按钮文字应恰为「{BUTTON_CHANGE}」（U+2026）")
    if 'variant="secondary"' not in code or 'size="sm"' not in code:
        problems.append("入口按钮应写 variant=\"secondary\" 与 size=\"sm\"（写法钉死第 4 条）")
    css_pos = text.find("import './hub-bind-form.css';")
    if css_pos < 0:
        problems.append("RoleBindForm.tsx 应 import './hub-bind-form.css'（复用 .hb-* 类，不新建 CSS）")
    else:
        for stmt in re.findall(r"import[^;]*?from\s*['\"]\.\./[^'\"]+['\"]", text, re.S):
            if text.find(stmt) > css_pos:
                problems.append("import './hub-bind-form.css' 应放在组件 import 之后（照 HubBindForm.tsx 的位置）")
                break
    for other_css in re.findall(r"import\s*['\"]([^'\"]+\.css)['\"]", text):
        if other_css != "./hub-bind-form.css":
            problems.append(f"RoleBindForm.tsx 不应引别的样式表（{other_css}；样式只复用 hub-bind-form.css）")
    if "DisabledAction" not in code:
        problems.append("可选模式为空时入口应是 DisabledAction（execution 无候选与未知角色两种）")
    if "useLivePreview(" not in code:
        problems.append("表单底部应用 useLivePreview('role.set', args, enabled)")
    if "'role.set'" not in code:
        problems.append("表单确认应走 role.set（start({ action: 'role.set', args })）")
    if "<WriteFlow flow={flow} />" not in code:
        problems.append("表单里应放 <WriteFlow flow={flow} />")
    for token in ("current", "result.ok", "onClose"):
        if token not in code:
            problems.append(f"[确认…] 的门控/次序应能看到 {token}（照 HubBindForm 的写法）")
    if re.search(r"from\s*['\"]\.\./pages|from\s*['\"]\./roles-", text):
        problems.append("src/writes 不跨层引 src/pages（角色中文名由入口文件当 prop 传进来）")
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"RoleBindForm.tsx 不应出现 {bad}")
    if _HEX_COLOR.search(code) or any(fn in code for fn in _COLOR_FUNCS):
        problems.append("RoleBindForm.tsx 不应写死颜色")
    if "style={{" in code:
        problems.append("RoleBindForm.tsx 不应写内联 style")
    fail_if(problems, "RoleBindForm.tsx 新文件（S07）")


def test_s08_card_and_view_wiring():
    """S08 / D06、D09、写法钉死第 6、7 条：roles-RoleCard.tsx 卡底换成 <RoleBindAction … />
    （新 props candidates? 与 reload? 都可选，两 prop 写法照旧编译；只读部分一个字不改）；
    roles-RolesView.tsx 给每张卡传 candidates={profileIds(data.profiles.profiles)} 与
    reload={reload}，从 '../../api' 只 import type。"""
    need_file(ROLECARD_REL)
    card_text = read_rel(ROLECARD_REL)
    card_code = strip_ts_comments(card_text)
    problems = []
    if "<RoleBindAction" not in card_code:
        problems.append("角色卡卡底应换成 <RoleBindAction … />（写法钉死第 6 条）")
    if not re.search(r"from\s*['\"]\.\.\/\.\.\/writes\/RoleBindForm['\"]", card_text):
        problems.append("RoleBindAction 应从 '../../writes/RoleBindForm' 引（入口组件在 src/writes）")
    props = _block(card_code, "export interface RoleCardProps")
    if not props:
        problems.append("roles-RoleCard.tsx 应保留 RoleCardProps")
    else:
        for prop in ("candidates", "reload"):
            if not re.search(rf"^\s*{prop}\?\s*:", props, re.M):
                problems.append(f"RoleCardProps 应加可选 prop {prop}?（两 prop 写法照旧编译）")
    for token in ("roleName", "modeName", "EffortPair", "rl-kv", "rl-card__note", "rl-card__foot"):
        if token not in card_text:
            problems.append(f"卡片只读部分应一个字不改（看不到 {token}）")
    if REASON_NO_PROFILES in card_text:
        problems.append("禁用原因句应在 src/writes 里，入口文件不写逐字句子")
    need_file(ROLESVIEW_REL)
    view_text = read_rel(ROLESVIEW_REL)
    view_code = strip_ts_comments(view_text)
    if not re.search(
        r"<RoleCard\s+key=\{r\.role\}\s+role=\{r\}\s+activePreset=\{active\}"
        r"\s+candidates=\{profileIds\(data\.profiles\.profiles\)\}\s+reload=\{reload\}(?:\s+\w+=\{[^{}]*\})*\s*/>",
        view_code,
    ):
        problems.append("RolesView 应给每张卡传 candidates={profileIds(data.profiles.profiles)} 与 reload={reload}（写法钉死第 7 条，之后可以追加 prop）")
    if not re.search(r"import\s*\{[^}]*profileIds[^}]*\}\s*from\s*['\"]\.\/roles-logic['\"]", view_text, re.S):
        problems.append("RolesView 应从 './roles-logic' 引 profileIds")
    for stmt in re.findall(r"import[^;]*?from\s*['\"]\.\.\/\.\.\/api['\"]", view_text, re.S):
        if not stmt.lstrip().startswith("import type"):
            problems.append(f"roles-RolesView.tsx 从 '../../api' 只许 import type：{stmt.strip()[:60]}")
    fail_if(problems, "RoleCard 与 RolesView 的接线（S08）")


def test_s09_executor_test_file():
    """S09 / D11：执行端新测试文件 desktop/web/tests/writes-role-bind.test.tsx 在位且覆盖记号
    齐备（合同第 11 步点名的覆盖点），不许 skip/only/todo。"""
    need_file(EXEC_COMP_TEST_REL)
    text = read_rel(EXEC_COMP_TEST_REL)
    problems = []
    for token in EXECUTOR_TEST_TOKENS:
        if token not in text:
            problems.append(f"writes-role-bind.test.tsx 应含记号「{token}」（合同第 11 步点名的覆盖点）")
    problems.extend(_no_skip_marks(text))
    fail_if(problems, "执行端新测试文件（S09）")


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 T044/T045 门禁的写法）
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


def t051_marker_present():
    """候选里是否已有 T051 的标记（RoleBindForm.tsx、roles-logic 的 allowedModes 与 api.ts 的
    role.set）：没有就不起 npm（基线上必然没有）。"""
    if not (REPO_ROOT / ROLEBINDFORM_REL).is_file():
        return False
    try:
        return ("allowedModes" in _read(REPO_ROOT / ROLES_LOGIC_REL)
                and "'role.set'" in _read(REPO_ROOT / API_REL))
    except OSError:
        return False


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t051_marker_present():
        pipe.reason = ("候选里还没有 T051 的标记（RoleBindForm.tsx、roles-logic 的 allowedModes 或 api.ts 的 "
                       "role.set），没有东西可测，未调用 npm；候选把新导出、新写函数与入口接上之后，"
                       "流水线才会运行 npm ci、Vitest 与探针")
        return pipe
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        pipe.reason = f"找不到 npm 或 node（shutil.which：npm={npm}，node={node})"
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
                    name = f"probe-{uid}-t051-{key}.test.tsx"
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

UNIT_PROBE = r'''// T051 门禁 unit 探针：roles-logic 的 allowedModes/profileIds/normalizeRole.cadenceSeconds、
// 桩的 mockPreview role.set 分支（命令与 binding_changes）、useLivePreview 的 bindingChanges、
// snapshots 的 roleSnapshot、api 的 setRoleBinding 正文（注入假服务）。不 mock 被测模块。
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Envelope } from '../src/api';
import { setRoleBinding } from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { mockPreview } from '../src/mock/writes';
import { useLivePreview } from '../src/writes/useLivePreview';
import { roleSnapshot } from '../src/writes/snapshots';
import { allowedModes, normalizeRole, profileIds } from '../src/pages/readonly1/roles-logic';

describe('allowedModes 与 profileIds（D05）', () => {
  it('四个角色各自的允许模式（次序照 ROLE_MODES，出自 kit_roles.py）', () => {
    expect(allowedModes('planning_review')).toEqual(['interactive_host', 'headless']);
    expect(allowedModes('contract')).toEqual(['manual', 'headless']);
    expect(allowedModes('execution')).toEqual(['headless']);
    expect(allowedModes('scheduler_agent')).toEqual(['disabled', 'headless']);
  });
  it('未知角色给 []', () => {
    expect(allowedModes('zz-none')).toEqual([]);
    expect(allowedModes('')).toEqual([]);
  });
  it('profileIds 按输入顺序、滤掉 _ 开头', () => {
    expect(profileIds([{ id: 'b' }, { id: '_x' }, { id: 'a' }, { id: '_y' }] as any)).toEqual(['b', 'a']);
    expect(profileIds([] as any)).toEqual([]);
  });
  it('normalizeRole 的 cadenceSeconds：整数才给数，其余 null', () => {
    const mk = (cadence: unknown) =>
      normalizeRole({ role: 'scheduler_agent', binding: { mode: 'headless', profile: 'p', cadence_seconds: cadence } } as any);
    expect(mk(3600).cadenceSeconds).toBe(3600);
    expect(mk('3600').cadenceSeconds).toBe(null);
    expect(mk(1.5).cadenceSeconds).toBe(null);
    expect(mk(undefined).cadenceSeconds).toBe(null);
  });
});

describe('桩的 role.set 预览（D02）', () => {
  beforeEach(() => {
    setLiveClientForTests(undefined);
    window.location.hash = '';
  });
  afterEach(() => {
    cleanup();
    setLiveClientForTests(undefined);
    window.location.hash = '';
  });
  it('execution 换 profile：命令 config role set execution step-low；binding_changes 恰一项 step-high → step-low', async () => {
    const reply = await mockPreview('role.set', { role: 'execution', target: 'step-low' });
    expect(reply.status).toBe(200);
    expect(reply.body.ok).toBe(true);
    const data = reply.body.data as any;
    expect(data.command).toEqual(['config', 'role', 'set', 'execution', 'step-low', '--dry-run', '--json']);
    expect(data.binding_changes).toEqual([{ role: 'execution', from: 'step-high', to: 'step-low' }]);
    expect(data.resources).toEqual(['roles']);
    expect(data.hub_changes).toEqual([]);
    expect(data.running_turns).toEqual([]);
  });
  it('target 与当前绑定相同：binding_changes 不给这一项', async () => {
    const reply = await mockPreview('role.set', { role: 'execution', target: 'step-high' });
    expect((reply.body.data as any).binding_changes).toEqual([]);
  });
  it('host 与 cadence_seconds 照参数追加 --host= 与 --cadence-seconds=；没传就不加', async () => {
    const a = await mockPreview('role.set', { role: 'planning_review', target: 'interactive_host', host: 'claude-code' });
    expect((a.body.data as any).command).toContain('--host=claude-code');
    const b = await mockPreview('role.set', { role: 'scheduler_agent', target: 'step-high', cadence_seconds: '3600' });
    const cmd = (b.body.data as any).command as string[];
    expect(cmd).toContain('--cadence-seconds=3600');
    expect(cmd).not.toContain('--host=claude-code');
  });
});

const posts: Array<{ path: string; body: unknown }> = [];
let postReply: { status: number; body: Envelope<any> } | null = null;
let postError: Error | null = null;

function envelope<T>(data: T, command: string[]): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 3 };
}

const fake: LiveClient = {
  get: () => Promise.resolve(envelope(null, [])),
  post(path: string, body: unknown) {
    posts.push({ path, body });
    return postError ? Promise.reject(postError) : Promise.resolve(postReply as any);
  },
  getRaw: () => Promise.resolve({ status: 404, body: null }),
};

const ARGS = { role: 'execution', target: 'step-low' };

function previewJson(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    binding_changes: [], resources: [], notes: [], warnings: [], running_attempts: [], needs_yes: false,
    hub_changes: [], running_turns: [], ...over,
  };
}

async function settlePreview() {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(301);
  });
}

describe('useLivePreview 的 bindingChanges（D03）', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.location.hash = '';
    posts.length = 0;
    postReply = null;
    postError = null;
    setLiveClientForTests(fake);
  });
  afterEach(() => {
    cleanup();
    setLiveClientForTests(undefined);
    vi.useRealTimers();
    window.location.hash = '';
  });
  it('binding_changes 映射成 from/to 的显示值（profile 优先）', async () => {
    postReply = {
      status: 200,
      body: envelope(
        {
          preview: previewJson({
            binding_changes: [{
              role: 'execution',
              before: { mode: 'headless', profile: 'step-high', provider: 'bb', model: 'm1' },
              after: { mode: 'headless', profile: 'step-low' },
            }],
          }),
          confirmation: 'c1',
        },
        ['config', 'role', 'set', 'execution', 'step-low', '--dry-run', '--json'],
      ),
    };
    const { result } = renderHook(() => useLivePreview('role.set', ARGS, true));
    await settlePreview();
    expect(result.current.result?.bindingChanges).toEqual([{ role: 'execution', from: 'step-high', to: 'step-low' }]);
    expect(result.current.result?.command).toEqual(['config', 'role', 'set', 'execution', 'step-low']);
  });
  it('缺 binding_changes 键时是空数组，不抛错', async () => {
    postReply = {
      status: 200,
      body: envelope({ preview: {}, confirmation: 'c2' }, ['config', 'role', 'set', 'execution', 'step-low', '--dry-run', '--json']),
    };
    const { result } = renderHook(() => useLivePreview('role.set', ARGS, true));
    await settlePreview();
    expect(result.current.result?.bindingChanges).toEqual([]);
  });
  it('post reject：错误行照旧，bindingChanges 是空数组', async () => {
    postError = new Error('连不上');
    const { result } = renderHook(() => useLivePreview('role.set', ARGS, true));
    await settlePreview();
    expect(result.current.result?.error).toBe('预览失败：服务没有回应');
    expect(result.current.result?.bindingChanges).toEqual([]);
  });
});

describe('roleSnapshot（D03）', () => {
  it('投影 roles[].{role, explicit, binding} 并按 role 排序', () => {
    const roles: any = { active_preset: 'default', roles: [
      { role: 'scheduler_agent', explicit: false, binding: { mode: 'disabled' } },
      { role: 'contract', explicit: true, binding: { mode: 'manual' }, extra: '不进来' },
    ] };
    const snap: any = roleSnapshot(roles);
    expect(snap.roles).toEqual([
      { role: 'contract', explicit: true, binding: { mode: 'manual' } },
      { role: 'scheduler_agent', explicit: false, binding: { mode: 'disabled' } },
    ]);
  });
});

describe('setRoleBinding 的正文（D01）', () => {
  beforeEach(() => {
    posts.length = 0;
    postError = null;
    postReply = { status: 200, body: envelope(null, ['config', 'role', 'set']) };
    setLiveClientForTests(fake);
  });
  afterEach(() => {
    setLiveClientForTests(undefined);
  });
  it('无头换 profile：正文恰好 target + confirmation，role 不进正文', async () => {
    await setRoleBinding({ role: 'execution', target: 'step-low' }, 'conf-1');
    expect(posts.length).toBe(1);
    expect(posts[0].path).toBe('/api/v1/roles/execution');
    expect(posts[0].body).toEqual({ target: 'step-low', confirmation: 'conf-1' });
  });
  it('仍选交互式宿主时 host 原样传回；cadence_seconds 转成 JSON 数字', async () => {
    await setRoleBinding({ role: 'planning_review', target: 'interactive_host', host: 'claude-code' }, 'conf-2');
    expect(posts[0].body).toEqual({ target: 'interactive_host', host: 'claude-code', confirmation: 'conf-2' });
    await setRoleBinding({ role: 'scheduler_agent', target: 'step-high', cadence_seconds: '3600' }, 'conf-3');
    expect(posts[1].path).toBe('/api/v1/roles/scheduler_agent');
    expect(posts[1].body).toEqual({ target: 'step-high', cadence_seconds: 3600, confirmation: 'conf-3' });
    expect(typeof (posts[1].body as any).cadence_seconds).toBe('number');
  });
  it('路径里的角色码过 encodeURIComponent', async () => {
    await setRoleBinding({ role: 'zz 9', target: 'manual' }, 'conf-4');
    expect(posts[0].path).toBe('/api/v1/roles/zz%209');
  });
});
'''


PAGE_PROBE = r'''// T051 门禁 page 探针：桩模式挂 App 核对四张角色卡的 [更改…]（可点、secondary/sm、禁用数 7、
// 四个角色各自的模式选项与预填、无头时 profile 下拉、底部命令与前后对比、确认先关表单再开
// 写确认框、成功轻提示、预览失败时确认不可点、对话框关着不渲染候选）；真实模式（注入假服务）
// 核对确认发 /api/v1/roles/<role>（正文的键恰好、host/cadence 的原样传回、cadence 是数字）、
// 写完重读、没有 profile 时的两种形态（execution 入口禁用悬停原因句；其余三个角色的模式下拉
// 没有无头，原因句在 Select 的 help 里）与未知角色码。不用假计时器（真实计时器等防抖/悬停）。
// 每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import App from '../src/App';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { setConnectionState } from '../src/live/connection';
import { HUB_ROLES_POSTS } from '../src/mock/hub-roles';
import type { Envelope } from '../src/api';

const CHANGE = '更改…';
const REASON = '没有已登记的 profile，无头不可选：先在「CLI 运行时」页登记运行时，再新建 profile';
const ROLES = ['planning_review', 'contract', 'execution', 'scheduler_agent'];
const TITLES: Record<string, string> = {
  planning_review: '规划审核端',
  contract: '合同端',
  execution: '执行端',
  scheduler_agent: '调度代理',
};
const MODE_OPTIONS: Record<string, string[]> = {
  planning_review: ['交互式宿主', '无头'],
  contract: ['手工', '无头'],
  execution: ['无头'],
  scheduler_agent: ['关闭', '无头'],
};
const MODE_PREFILL: Record<string, string> = {
  planning_review: '交互式宿主',
  contract: '手工',
  execution: '无头',
  scheduler_agent: '关闭',
};

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  await flush();
  render(<App />);
  await flush();
}
function frame(): any {
  return document.querySelector('[data-page-state]');
}
function card(role: string): any {
  const hit = document.querySelector(`article[data-role="${role}"]`);
  expect(hit, '应有角色卡 ' + role).toBeTruthy();
  return hit;
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
function optionValueByLabel(sel: HTMLSelectElement, label: string): string {
  const hit = qa(sel, 'option').find((o: any) => text(o) === label);
  expect(hit, '应有选项「' + label + '」').toBeTruthy();
  return (hit as any).value;
}
function selectedLabel(sel: HTMLSelectElement): string {
  const hit = qa(sel, 'option').find((o: any) => (o as any).selected);
  return hit ? text(hit) : '';
}

beforeEach(() => {
  setLiveClientForTests(undefined);
  setConnectionState('connected');
  window.location.hash = '';
});
afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('桩模式：四张角色卡的 [更改…]（D06）', () => {
  it('四张卡的 [更改…] 都可点，是 secondary/sm；角色页禁用按钮数 6；对话框关着时卡片里没有下拉', async () => {
    await mountApp('#/roles');
    for (const role of ROLES) {
      const b = btnIn(card(role), CHANGE);
      expect(b.disabled, role + ' 的 [更改…] 可点').toBe(false);
      expect(b.getAttribute('data-variant'), role + ' secondary').toBe('secondary');
      expect(b.getAttribute('data-size'), role + ' sm').toBe('sm');
      expect(qa(card(role), 'select').length, role + ' 对话框关着不渲染表单字段').toBe(0);
    }
    expect(qa(frame(), 'button').filter((b: any) => b.disabled).length, '角色页禁用按钮数 6（page-app 的口径）').toBe(6);
  });
  it('四个角色各自只列允许的模式（次序照 ROLE_MODES）且预填现有模式；无头时才有 profile 下拉并预填现有 profile', async () => {
    for (const role of ROLES) {
      cleanup();
      await mountApp('#/roles');
      fireEvent.click(btnIn(card(role), CHANGE));
      await flush();
      const d = needDlg();
      expect(text(d), role + ' 对话框标题').toContain('改绑定：' + TITLES[role]);
      const mode = selectByLabel(d, '模式');
      expect(qa(mode, 'option').map(text), role + ' 的模式选项').toEqual(MODE_OPTIONS[role]);
      expect(selectedLabel(mode), role + ' 预填现有模式').toBe(MODE_PREFILL[role]);
      const profileSelects = qa(d, 'select').filter((el: any) => {
        const id = el.id;
        const label = qa(d, 'label').find((l: any) => (l as any).getAttribute('for') === id);
        return label && text(label) === 'profile';
      });
      if (role === 'execution') {
        expect(profileSelects.length, '无头 → 有 profile 下拉').toBe(1);
        const sel = profileSelects[0];
        expect(qa(sel, 'option').map((o: any) => o.value), '候选是全部已登记 profile 的 id').toEqual(['step-high', 'step-low']);
        expect(sel.value, '现有 profile 在候选里 → 预填它').toBe('step-high');
      } else {
        expect(profileSelects.length, role + ' 不是无头 → 没有 profile 下拉').toBe(0);
      }
      fireEvent.click(btnIn(d, '取消'));
      await flush();
      expect(dlg(), '取消后表单对话框应关上').toBeNull();
    }
  });
  it('execution 换 profile：底部命令与前后对比；[确认…] 先关表单再开写确认框；成功轻提示', async () => {
    await mountApp('#/roles');
    fireEvent.click(btnIn(card('execution'), CHANGE));
    await flush();
    const d = needDlg();
    const profile = selectByLabel(d, 'profile');
    fireEvent.change(profile, { target: { value: optionValueByLabel(profile, 'step-low') } });
    await flush();
    await sleep(450);
    await flush();
    const t = text(needDlg());
    expect(t).toContain('config role set execution step-low');
    expect(t.replace(/\s+/g, ''), '本角色的绑定前后一行「from → to」（对空白不敏感：共享 Changes 是三段 span 拼的）').toContain('step-high→step-low');
    const confirm = btnIn(needDlg(), '确认…');
    expect(confirm.disabled, '预览 ok 且对应当前取值 → 可确认').toBe(false);
    fireEvent.click(confirm);
    await flush();
    const cd = needDlg();
    expect(text(cd), '表单关上后开写确认框（先关表单再 start）').toContain('改角色绑定 execution？');
    expect(qa(cd, 'select').length, '写确认框里没有表单字段').toBe(0);
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(80);
    await flush();
    expect(text(document.body)).toContain('已改角色绑定 execution');
  });
  it('planning_review 保持交互式宿主：命令带 --host=claude-code；预览没变化时写确认框回落到变化摘要（宿主 claude-code）', async () => {
    await mountApp('#/roles');
    fireEvent.click(btnIn(card('planning_review'), CHANGE));
    await flush();
    await sleep(450);
    await flush();
    const t = text(needDlg());
    expect(t).toContain('config role set planning_review interactive_host --host=claude-code');
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '改角色绑定标题').toContain('改角色绑定 planning_review？');
    expect(text(cd), '变化摘要带宿主').toContain('角色 planning_review 的绑定改成 interactive_host（宿主 claude-code）');
    fireEvent.click(btnIn(cd, '取消'));
    await flush();
  });
  it('scheduler_agent 切到无头：profile 下拉出现并预填第一个候选；命令的 target 是 profile id', async () => {
    await mountApp('#/roles');
    fireEvent.click(btnIn(card('scheduler_agent'), CHANGE));
    await flush();
    const d = needDlg();
    const mode = selectByLabel(d, '模式');
    fireEvent.change(mode, { target: { value: optionValueByLabel(mode, '无头') } });
    await flush();
    const profile = selectByLabel(needDlg(), 'profile');
    expect(profile.value, '现有绑定没有 profile → 预填第一个候选').toBe('step-high');
    await sleep(450);
    await flush();
    expect(text(needDlg())).toContain('config role set scheduler_agent step-high');
  });
  it('预览失败（write=preview-fail）：底部显示错误原文，确认…不可点', async () => {
    await mountApp('#/roles?write=preview-fail');
    fireEvent.click(btnIn(card('execution'), CHANGE));
    await flush();
    await sleep(450);
    await flush();
    const d = needDlg();
    expect(text(d)).toContain('ERROR 预览不合格：参数不符合组合规则');
    expect(btnIn(d, '确认…').disabled).toBe(true);
  });
});

// ---- 真实模式（注入假服务）----

function okEnv<T>(data: T, command: string[] = []): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

const REAL_ROLES = { active_preset: 'default', roles: [
  { role: 'planning_review', explicit: true, binding: { mode: 'interactive_host', host: 'claude-code' }, differs_from_preset: false },
  { role: 'contract', explicit: false, binding: { mode: 'manual' }, differs_from_preset: false },
  { role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' }, differs_from_preset: false, profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, effort_effective: 'high' },
  { role: 'scheduler_agent', explicit: true, binding: { mode: 'headless', profile: 'step-high', cadence_seconds: 3600 }, differs_from_preset: false, profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, effort_effective: 'high' },
  { role: 'zz_agent', explicit: false, binding: { mode: 'manual' }, differs_from_preset: false },
] };
const PRESETS = { active_preset: 'default', presets: [
  { name: 'default', description: '日常', roles: ['execution'], active: true },
] };
const REAL_PROFILES = { profiles: [
  { id: 'quizs-m9', runtime: 'quizs', adapter: 'quizs', provider: 'minimax', model: 'MiniMax-M3.1-Flash', options: { thinking: 'high' }, credential_env: [] },
  { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: [] },
  { id: 'step-low', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini', options: { thinking: 'low' }, credential_env: [] },
  { id: '_internal', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'm0', options: {}, credential_env: [] },
] };
const EMPTY_PROFILES = { profiles: [] };

let gets: string[] = [];
let posts: Array<{ path: string; body: any }> = [];
let previewJson: Record<string, unknown> = {};
let previewCommand: string[] = [];
let rolesData: any = REAL_ROLES;
let profilesData: any = REAL_PROFILES;

function basePreview(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    binding_changes: [], resources: [{ resource: 'roles' }], notes: [], unreadable: [], warnings: [],
    running_attempts: [], running_turns: [], needs_yes: false, hub_changes: [], ...over,
  };
}

function makeClient(): LiveClient {
  return {
    get<T>(path: string): Promise<Envelope<T>> {
      gets.push(path);
      if (path === '/api/v1/hub/roles') return Promise.resolve(okEnv(HUB_ROLES_POSTS, ['config', 'hub', 'show', '--json']) as unknown as Envelope<T>);
      if (path === '/api/v1/roles') return Promise.resolve(okEnv(rolesData) as unknown as Envelope<T>);
      if (path === '/api/v1/profiles') return Promise.resolve(okEnv(profilesData) as unknown as Envelope<T>);
      if (path === '/api/v1/presets') return Promise.resolve(okEnv(PRESETS) as unknown as Envelope<T>);
      if (path === '/api/v1/meta') return Promise.resolve(okEnv({ version: 'pi_dispatch 1.0.0', repo_name: 'r' }) as unknown as Envelope<T>);
      return Promise.resolve(okEnv(null) as unknown as Envelope<T>);
    },
    post<T>(path: string, body: unknown): Promise<{ status: number; body: Envelope<T> }> {
      posts.push({ path, body });
      if (path === '/api/v1/preview') {
        return Promise.resolve({
          status: 200,
          body: okEnv({ preview: previewJson, confirmation: 'c-real-1' }, previewCommand) as unknown as Envelope<T>,
        });
      }
      return Promise.resolve({ status: 200, body: okEnv(null, ['config', 'role', 'set']) as unknown as Envelope<T> });
    },
    getRaw<T>(): Promise<{ status: number; body: T }> {
      return Promise.resolve({ status: 404, body: null as unknown as T });
    },
  };
}

async function openForm(role: string) {
  fireEvent.click(btnIn(card(role), CHANGE));
  await flush();
  return needDlg();
}

async function confirmWrite(role: string) {
  fireEvent.click(btnIn(needDlg(), '确认…'));
  await flush();
  const cd = needDlg();
  expect(text(cd), '写确认框标题').toContain('改角色绑定 ' + role + '？');
  fireEvent.click(btnIn(cd, '确认…'));
  await flush();
  await sleep(120);
  await flush();
}

describe('真实模式：确认发 POST /api/v1/roles/<role>（D01、D07）', () => {
  beforeEach(() => {
    gets = [];
    posts = [];
    rolesData = REAL_ROLES;
    profilesData = REAL_PROFILES;
    previewJson = basePreview();
    previewCommand = ['config', 'role', 'set', 'scheduler_agent', 'step-high', '--cadence-seconds=3600', '--dry-run', '--json'];
    setLiveClientForTests(makeClient());
  });
  it('scheduler_agent 保持无头：预览与执行的 cadence_seconds 都是 JSON 数字；正文恰好 target+cadence+confirmation；变化摘要带间隔；写完重读；成功轻提示', async () => {
    previewJson = basePreview({
      binding_changes: [{ role: 'scheduler_agent', before: { mode: 'headless', profile: 'step-high' }, after: { mode: 'headless', profile: 'step-low' } }],
    });
    await mountApp('#/roles');
    const rolesBefore = gets.filter((p) => p === '/api/v1/roles').length;
    await openForm('scheduler_agent');
    await sleep(450);
    await flush();
    const t = text(needDlg());
    expect(t).toContain('config role set scheduler_agent step-high --cadence-seconds=3600');
    expect(t.replace(/\s+/g, ''), '底部显示本角色的前后（对空白不敏感）').toContain('step-high→step-low');
    const prev = posts.find((p) => p.path === '/api/v1/preview');
    expect(prev, '应发过预览').toBeTruthy();
    expect(prev.body.args).toEqual({ role: 'scheduler_agent', target: 'step-high', cadence_seconds: 3600 });
    expect(typeof prev.body.args.cadence_seconds, '预览的参数规则与执行同一份').toBe('number');
    await confirmWrite('scheduler_agent');
    const writes = posts.filter((p) => p.path === '/api/v1/roles/scheduler_agent');
    expect(writes.length, '只发一次角色写路由').toBe(1);
    expect(writes[0].body, '正文恰好 target+cadence+confirmation（role 不进正文）').toEqual({
      target: 'step-high', cadence_seconds: 3600, confirmation: 'c-real-1',
    });
    expect(typeof writes[0].body.cadence_seconds).toBe('number');
    expect(text(document.body)).toContain('已改角色绑定 scheduler_agent');
    expect(gets.filter((p) => p === '/api/v1/roles').length, '写完重读（getRoles 次数增加）').toBeGreaterThan(rolesBefore);
  });
  it('scheduler_agent 预览没变化：写确认框回落到变化摘要（间隔 3600 秒）', async () => {
    previewJson = basePreview();
    await mountApp('#/roles');
    await openForm('scheduler_agent');
    await sleep(450);
    await flush();
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '变化区回落到摘要，带 cadence 后缀').toContain('角色 scheduler_agent 的绑定改成 step-high（间隔 3600 秒）');
    fireEvent.click(btnIn(cd, '取消'));
    await flush();
  });
  it('planning_review 保持交互式宿主：host 原样传回；切到无头：不带 host，target 是预填的第一个候选（滤掉 _ 开头）', async () => {
    await mountApp('#/roles');
    await openForm('planning_review');
    await sleep(450);
    await flush();
    await confirmWrite('planning_review');
    let writes = posts.filter((p) => p.path === '/api/v1/roles/planning_review');
    expect(writes[0].body).toEqual({ target: 'interactive_host', host: 'claude-code', confirmation: 'c-real-1' });
    expect(dlg(), '成功写完对话框已关上（无 WARN 行走 done：setToast + resetFlow，不落 doneWithWarning）').toBeNull();
    expect(text(document.body)).toContain('已改角色绑定 planning_review');
    await openForm('planning_review');
    const mode = selectByLabel(needDlg(), '模式');
    fireEvent.change(mode, { target: { value: optionValueByLabel(mode, '无头') } });
    await flush();
    const profile = selectByLabel(needDlg(), 'profile');
    expect(qa(profile, 'option').map((o: any) => o.value), '候选按输入顺序、滤掉 _ 开头').toEqual(['quizs-m9', 'step-high', 'step-low']);
    expect(profile.value, '现有绑定没有 profile → 预填第一个候选').toBe('quizs-m9');
    await sleep(450);
    await flush();
    await confirmWrite('planning_review');
    writes = posts.filter((p) => p.path === '/api/v1/roles/planning_review');
    expect(writes[1].body, '切到无头不带 host，target 是选中的 profile id').toEqual({ target: 'quizs-m9', confirmation: 'c-real-1' });
  });
  it('scheduler_agent 切到关闭：不带 cadence_seconds；未知角色码 zz_agent 的入口禁用（缺省原因句）', async () => {
    await mountApp('#/roles');
    const zz = btnIn(card('zz_agent'), CHANGE);
    expect(zz.disabled, '未知角色码可选模式为空 → 入口禁用').toBe(true);
    fireEvent.mouseEnter(zz.parentElement);
    await sleep(500);
    const tip = document.querySelector('[role="tooltip"]');
    expect(text(tip), '未知角色不传 reason（沿用缺省）').toBe('第二阶段接入');
    await openForm('scheduler_agent');
    const mode = selectByLabel(needDlg(), '模式');
    fireEvent.change(mode, { target: { value: optionValueByLabel(mode, '关闭') } });
    await flush();
    await sleep(450);
    await flush();
    await confirmWrite('scheduler_agent');
    const writes = posts.filter((p) => p.path === '/api/v1/roles/scheduler_agent');
    expect(writes[0].body, '切到别的模式不带 cadence_seconds').toEqual({ target: 'disabled', confirmation: 'c-real-1' });
  });
});

describe('真实模式：没有已登记的 profile（D08）', () => {
  beforeEach(() => {
    gets = [];
    posts = [];
    rolesData = REAL_ROLES;
    profilesData = EMPTY_PROFILES;
    previewJson = basePreview();
    previewCommand = ['config', 'role', 'set', 'planning_review', 'interactive_host', '--dry-run', '--json'];
    setLiveClientForTests(makeClient());
  });
  it('execution 只允许无头 → 入口禁用并悬停出原因句；其余三个角色模式下拉没有无头，原因句在 Select 的 help 里', async () => {
    await mountApp('#/roles');
    const b = btnIn(card('execution'), CHANGE);
    expect(b.disabled, 'execution 只允许无头、无候选 → 入口禁用').toBe(true);
    fireEvent.mouseEnter(b.parentElement);
    await sleep(500);
    const tip = document.querySelector('[role="tooltip"]');
    expect(text(tip), '悬停出原因句（逐字）').toBe(REASON);
    for (const role of ['planning_review', 'contract', 'scheduler_agent']) {
      expect(btnIn(card(role), CHANGE).disabled, role + ' 仍可切到非无头模式 → 入口可点').toBe(false);
      const d = await openForm(role);
      const mode = selectByLabel(d, '模式');
      expect(qa(mode, 'option').map(text), role + ' 的模式下拉没有无头').toEqual(MODE_OPTIONS[role].filter((m) => m !== '无头'));
      expect(text(d), role + ' 原因句可见（Select 的 help）').toContain(REASON);
      expect(mode.getAttribute('aria-describedby'), 'help 接到 aria-describedby').toBeTruthy();
      fireEvent.click(btnIn(d, '取消'));
      await flush();
    }
  });
});
'''


PROBE_SPECS = {
    "unit": (UNIT_PROBE, (ROLES_LOGIC_REL, API_REL, LIVEPREVIEW_REL, SNAPSHOTS_REL, MOCK_WRITES_REL)),
    "page": (PAGE_PROBE, (ROLEBINDFORM_REL, ROLECARD_REL, ROLESVIEW_REL, ROLES_LOGIC_REL,
                          API_REL, MOCK_WRITES_REL, MOCK_ROLES_REL, MOCK_PROFILES_REL)),
}
PROBE_ORDER = ("unit", "page")


# ---------------------------------------------------------------------------
# P 系列：流水线断言；D 系列：探针断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、D11：npm 依赖（已在就跳过重装）、npm test（全绿，含执行端新测试与照新行为改过的
    包内测试）都退出 0；依赖文件一个字节没动；gate-probe/ 没有留下。"""
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


def test_d01_d02_d03_probe_unit(pipeline):
    """unit 探针 / D01–D05：allowedModes/profileIds 的边界、normalizeRole 的 cadenceSeconds、
    桩的 role.set 预览（命令、binding_changes、host/cadence 旗标）、useLivePreview 的
    bindingChanges（映射、缺键空数组、reject）、roleSnapshot 的投影与排序、setRoleBinding 的
    正文（键恰好、cadence 是 JSON 数字、role 不进正文、路径过 encodeURIComponent）。"""
    assert_probe_ok(pipeline, "unit")


def test_d04_d05_d06_d07_d08_d09_probe_page(pipeline):
    """page 探针 / D06–D09：桩模式下四张卡的 [更改…] 可点（secondary/sm）、角色页禁用数 7、
    四个角色各自的模式选项与预填、无头时 profile 下拉、底部命令与前后对比、确认先关表单再开
    写确认框、成功轻提示、预览失败时确认不可点、对话框关着不渲染候选；真实模式下确认发
    POST /api/v1/roles/<role>（正文恰好、host/cadence 的原样传回、cadence 是数字）、变化摘要
    （宿主/间隔后缀）、写完重读、没有 profile 时 execution 入口禁用悬停原因句与其余三个角色
    模式下拉没有无头、未知角色码入口禁用（缺省原因句）。前后对比的渲染断言对空白不敏感
    （共享 WriteConfirmDialog.Changes 是三段 span 拼的，textContent 里箭头两侧没有空格）。"""
    assert_probe_ok(pipeline, "page")
