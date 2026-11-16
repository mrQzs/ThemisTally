"""T044 战前门禁：桌面端前端第 10 片「七端岗位一组改绑定与恢复缺省（A 片）」的黑盒基准测试
（合同 t044-desktop-web-hub-bind.v1，基线 185d077722609384f479a9b981fec6fc18ee8a68）。

被测对象是 ``desktop/web/`` 前端的写流程：

- ``src/api.ts``：``PreviewData`` 加两个必填字段 ``hub_changes`` 与 ``running_turns``；新增三个导出类型
  （HubChange/HubChangeSide/HubChangeFallback）；``toPreviewData`` 照服务形状映射（post 非字符串跳过该项、
  侧与字段缺键或类型不对归 null、替补不是对象归 null、非数组当空数组）；``unreadable`` 照旧并进 ``notes``；
  既有字段与既有导出一个不改（setHubRole/unsetHubRole/getHubRoles 已在基线里）。
- ``src/writes/snapshots.ts``：加 ``hubSnapshot(hub: HubRolesData)``——投影只有
  ``post/source/profile/fallback_profile`` 四个字段，按 ``post`` 排序（既有 ``byKey`` 口径）。
- ``src/writes/useWriteFlow.ts``：``readSnapshot`` 的 ``hub.set``/``hub.unset`` 分支读 ``getHubRoles``；
  ``confirm`` 分支链在 ``runtime.add`` 之后、``setPluginEnabled`` 之前加 ``setHubRole``/``unsetHubRole``
  （不再误落到插件启停）；``titleOf``/``successTextOf``/``changeSummaryOf`` 补两条逐字文案；``content``
  加 ``hubChanges``/``runningTurns``；原因句条件放宽成「没有在跑的 attempt 且没有在跑的回合」，原因句
  一字不改。
- ``src/writes/hubChangeLines.ts``（新）：``hubChangeLines(change)`` 恰好四行（运行时/模型/思考档位/替补）、
  ``hubPostLabel(post)`` 六个岗位中文名（含括号里的岗位码）；纯函数、只 import type。
- ``src/writes/WriteConfirmDialog.tsx``：``ConfirmContent`` 加必填 ``hubChanges``/``runningTurns``；「变化」
  一节按岗位渲染前后对比（``changes`` 空且 ``hubChanges`` 非空时不显示「预览没有列出变化」）；「影响与风险」
  逐行显示在跑的回合；``hasRisk`` 算上 ``runningTurns``；``有 attempt 正在运行：…`` 一字不改。
- ``src/writes/write-flow.css``：只在末尾追加 ``.wf-hub``/``.wf-hub__post``/``.wf-hub__line`` 三条规则。
- ``src/mock/writes.ts``：``WriteScenario``/``SCENARIOS`` 加 ``hub-ok``/``hub-warn``/``hub-running``/
  ``hub-unset`` 四个取值（既有 23 个一个不改）；``hub.set``/``hub.unset`` 的预览按夹具算 ``hub_changes``
  （before 取 mock/hub-roles.ts 该行、after 取 profiles.json 的 step-high 或内核缺省表）；新写的岗位桩
  数据不引入 ``step-low``，既有 6 处演示字面量保留不动。
- 执行端测试：三个新文件（writes-hub-api.test.ts、writes-hub-logic.test.ts、writes-hub-flow.test.tsx），
  三处既有夹具（writes-flow.test.tsx、writes-profile-form.test.tsx 的预览 data 与 writes-dialog.test.tsx
  的 ConfirmContent）补 ``hub_changes``/``running_turns``（合同 v2：第三处漏了它确认框会读
  ``content.runningTurns.length`` 抛 ``undefined.length``）。

基线（185d0777）上新类型、``hub_changes`` 映射、``hubSnapshot``、``hubChangeLines``、四个岗位情景、
确认框的岗位块与在跑回合都不存在，所以本文件的失败落在「记号不在」「文件不存在」这类断言上，不是导入、
收集或语法错误：模块级只导入标准库，所有仓库文件的读取都发生在用例函数里；流水线（npm、Vitest、探针）
放在 ``pipeline`` 会话级夹具里（全量 pytest 默认跳过，点名运行本文件才跑；候选里 api.ts 还没有
``hub_changes`` 时夹具不调 npm——基线上没有新东西可跑，照 T024/T040/T041/T043 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：api.ts 的类型与映射记号（S01）；snapshots 的
  hubSnapshot（S02）；useWriteFlow 的分支、文案与原因句条件（S03）；hubChangeLines 新文件（S04）；
  确认框的接线与逐字文案（S05）；CSS 只在末尾追加（S06）；桩的情景与夹具计算（S07）；执行端测试文件
  在位且要点齐备（S08）；共享面——mock JSON 仍 14 份、顶层页面仍 9 个、依赖冻结、既有测试的记号仍在
  （S09）；新文件的源码规矩（S10）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、
  ``npm test`` 全绿（含执行端三个新测试与补过字段的既有测试）；两份探针逐份写成
  ``gate-probe/probe-<uid>-t044-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，``finally``
  里删除。探针用 ``setLiveClientForTests`` 注入假服务（照 tests/writes-live-flow.test.tsx 的写法），不
  mock 被测组件；每份自带全部辅助函数，不跨文件共享作用域。
  - unit：``hubChangeLines`` 的四行文案与「默认」标记/替补文字/兜底、``hubPostLabel`` 的六个中文名与
    未知码、``hubSnapshot`` 的投影与排序、api 真实模式的 ``hub_changes``/``running_turns`` 映射兜底与
    ``unreadable`` 并入、``setHubRole``/``unsetHubRole`` 的路由与正文、桩四个岗位情景的取值。
  - flow：挂载真实 useWriteFlow + WriteConfirmDialog（自带的按钮触发 hub.set/hub.unset），确认发的是
    岗位路由且没有 /api/v1/plugins/...（D11）；变化区四行前后对比与「默认」标记（D05）；needs_yes 的
    两种说法（D04）。

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

API_REL = f"{SRC_REL}/api.ts"
SNAPSHOTS_REL = f"{WRITES_REL}/snapshots.ts"
USEWRITEFLOW_REL = f"{WRITES_REL}/useWriteFlow.ts"
DIALOG_REL = f"{WRITES_REL}/WriteConfirmDialog.tsx"
HUBLINES_REL = f"{WRITES_REL}/hubChangeLines.ts"
WF_CSS_REL = f"{WRITES_REL}/write-flow.css"
MOCK_WRITES_REL = f"{SRC_REL}/mock/writes.ts"
MOCK_HUB_ROLES_REL = f"{SRC_REL}/mock/hub-roles.ts"
MOCK_PROFILES_REL = f"{SRC_REL}/mock/profiles.json"
KIT_ROLES_REL = "scripts/kit_roles.py"

WRITES_FLOW_TEST_REL = f"{TESTS_REL}/writes-flow.test.tsx"
PROFILE_FORM_TEST_REL = f"{TESTS_REL}/writes-profile-form.test.tsx"
WRITES_DIALOG_TEST_REL = f"{TESTS_REL}/writes-dialog.test.tsx"
LIVE_FLOW_TEST_REL = f"{TESTS_REL}/writes-live-flow.test.tsx"
LIVE_API_TEST_REL = f"{TESTS_REL}/live-api.test.ts"
EXEC_API_TEST_REL = f"{TESTS_REL}/writes-hub-api.test.ts"
EXEC_LOGIC_TEST_REL = f"{TESTS_REL}/writes-hub-logic.test.ts"
EXEC_FLOW_TEST_REL = f"{TESTS_REL}/writes-hub-flow.test.tsx"

# 基线名单：src/mock 恰 14 份 JSON、src/pages 顶层恰 9 个 *Page.tsx（不新增 JSON、不新增页面文件）
BASELINE_MOCK_JSON_COUNT = 14
BASELINE_PAGE_COUNT = 9

# 依赖冻结（合同兼容性：package.json 与锁文件不变；行尾归一为 LF 后的字节数与 sha256）
BASELINE_DIGESTS = {
    f"{WEB_REL}/package.json": (820, "094d3622e54097e0f50f0ab2a71a5caa22491dba9d3ac6ef83047426f8c57f5a"),
    f"{WEB_REL}/package-lock.json": (108793, "1bc4e1fbfeb02a17280d0de1d98a5f3b2721fa91229c271c66d590d059d82d28"),
}

# write-flow.css 的基线冻结（合同第 7 步：只在末尾追加）：候选文件的前 N 字节必须仍是基线原文。
BASELINE_WF_CSS = (1597, "504880a886b662607a026bb00567cb644bceabcccbb3e4bfedb51ab7380e5edd")

# api.ts 既有的全部导出函数（合同兼容性：既有导出与签名一个不改，本片只新增类型；函数不新增）
OLD_API_EXPORTS = (
    "getMeta", "getMetaNow", "getStatus", "getAttempt", "readFile", "getRoles", "getProfiles", "getPresets",
    "getHubRoles", "diffPresets", "getRuntimes", "getPlugins", "getHistory", "getUsage", "listSecrets",
    "getHistoryEntry", "getPlugin", "preview", "getOperation", "usePreset", "setPluginEnabled", "removePreset",
    "removeProfile", "removeRuntime", "rollback", "addProfile", "editProfile", "setHubRole", "unsetHubRole",
    "addRuntime",
)
# WriteAction 既有的 12 个成员（合同 Repository facts；本片不动这个联合类型）
OLD_WRITE_ACTIONS = (
    "preset.use", "plugin.enable", "plugin.disable", "preset.remove", "profile.remove", "runtime.remove",
    "config.rollback", "profile.add", "profile.edit", "hub.set", "hub.unset", "runtime.add",
)
# 合同 Behavior contract 的三个新类型
HUB_CHANGE_TYPES = ("HubChangeFallback", "HubChangeSide", "HubChange")
# PreviewData 既有的八个字段（合同 Repository facts：本片只加两个，不改既有字段）
OLD_PREVIEW_FIELDS = (
    "binding_changes", "resources", "notes", "warnings", "running_attempts", "needs_yes", "command",
    "confirmation",
)

# T040 锁定的原因句（合同：一字不改，只放宽出现条件）
REASON = "有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。"
# 在跑的回合那一行的后半句（合同 Behavior contract 逐字）
TURNS_NOTE = "在跑的回合照旧用原来的绑定，下一个回合起用新的；这次改动需要你确认。"
# 既有 attempt 说法的前缀（合同：那一行一字不改）
ATTEMPT_PREFIX = "有 attempt 正在运行："
# 桩的同模型警告与在跑回合（合同边界输入逐字）
HUB_WARN_TEXT = "合同端与审核端用的是同一个模型（bb/step-5-preview）：审核少一层独立性；照样生效"
HUB_RUNNING_TURN = "审核端（audit）：2 个回合在跑"

# mock/writes.ts 既有的 23 个情景值（合同：一个不改，只加四个）
OLD_SCENARIOS = (
    "ok", "warn", "exit1", "exit2", "exit3", "stale", "expired", "busy", "closing", "spawn", "toolarge",
    "timeout", "drop-done", "drop-lost", "drop-hang", "preview-fail", "preview-busy", "reread-fail",
    "reread-fail-exit1", "in-use", "preview-warn", "preview-invalid", "preview-registered",
)
NEW_SCENARIOS = ("hub-ok", "hub-warn", "hub-running", "hub-unset")
# 基线 mock/writes.ts 里既有演示文案的 step-low 处数（合同 v2：保留不动，新桩数据不引入；注释剥离后计）
BASELINE_STEP_LOW_COUNT = 6

# 岗位中文名（合同 Behavior contract：中文名 + 括号里的岗位码；未知码原样返回）
HUB_POST_LABELS = {
    "coordinator": "协调人",
    "planner": "规划端",
    "contract": "合同端",
    "gate": "门禁端",
    "audit": "审核端",
    "exec": "执行端",
}

# useWriteFlow 三个表的新文案（合同 Behavior contract 逐字）——模板里的 ${…} 按源码字面查：

TITLE_SET = "改绑定 ${args.post}？"
TITLE_UNSET = "恢复缺省 ${args.post}？"
SUCCESS_SET = "已改绑定 ${args.post}"
SUCCESS_UNSET = "已恢复缺省 ${args.post}"
SUMMARY_SET_MAIN = "岗位 ${args.post} 的主绑定改成 ${args.profile}"
SUMMARY_SET_FALLBACK = "，替补 ${args.fallback}"
SUMMARY_SET_NOFALLBACK = "，没有替补"
SUMMARY_UNSET = "岗位 ${args.post} 回到内核缺省"

# 执行端三个新测试文件的最小覆盖记号（合同第 10 步）
EXECUTOR_TEST_TOKENS = {
    "writes-hub-api.test.ts": (
        "setLiveClientForTests", "hub_changes", "running_turns", "/api/v1/hub/roles/", "/unset", "confirmation",
        "setHubRole", "unsetHubRole",
    ),
    "writes-hub-logic.test.ts": (
        "hubSnapshot", "fallback_profile", "hubChangeLines", "hubPostLabel", "排序",
    ),
    "writes-hub-flow.test.tsx": (
        "useWriteFlow", "hub.set", "hub.unset", "plugins", REASON, "在跑的回合",
    ),
}

# 新源码的禁词（page-static.test.ts 的口径 + T006/T009 的 matchMedia 一类 + 「（UTC 」单一来源）
FORBIDDEN_SOURCE_MARKS = (
    "XMLHttpRequest", "EventSource", "WebSocket", "dangerouslySetInnerHTML", "innerHTML", "outerHTML",
    "insertAdjacentHTML", "eval(", "new Function", "document.write", "srcdoc", "DOMParser",
    "matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver", "role=\"status\"",
    "（UTC ",
)
# 颜色字面量与颜色函数（T006/T009 的口径；CSS 与源码都查）
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_COLOR_FUNCS = ("rgb(", "rgba(", "hsl(", "hsla(", "color-mix(", "oklch(", "lab(", "hwb(")

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T024/T041/T043 门禁），用完就停下并在断言里写明。
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 120}

ASSUMPTIONS = (
    "「（默认）」标记按侧生效、该侧四行（含替补行）都加（合同 v2 已写进 Behavior contract 与 D06，"
    "门禁探针照同一口径断言）；「（默认）」紧贴该侧值的末尾（例：`pi · pi（默认）`），不插在两个字段中间",
    "mock 的 hub.unset 预览不筛「前后相同」的岗位（合同 v2 已照本门禁的假设写明）；门禁只对配置行"
    "（contract）断言，缺省行的 hub.unset 不出 hub_changes 这一情形不在本合同里",
    "D12 的 step-low 检查按「注释剥离后处数恰为基线的 6 处」实现（合同 v2：既有演示字面量一个不改、"
    "新写的岗位桩数据不引入这个 id——处数变大=新数据引入，变小=改了既有文案，两个方向都红；"
    "注释里说明性的 step-low 字样被剥离不算）",
    "write-flow.css 的基线内容按字节前缀冻结（合同「只在末尾追加」）；候选把基线 1597 字节原样保留后，"
    "末尾追加了什么由三条 .wf-hub 规则的记号断言",
    "package.json 与 package-lock.json 按基线字节冻结（行尾归一 LF）；依赖变更由每一份合同的 "
    "dependency_changes: forbidden 背书",
    "执行端测试文件的覆盖记号是最低要求（有这些记号才说明测到了合同点名的那几件事），用例数与写法不设"
    "上限；运行时行为由两份探针独立钉住",
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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043 的同一口径）：行注释与块注释在同一次从左往右的扫描里认。
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


def _statement(text, start_marker):
    """从 start_marker 起取「一条声明」：到第一个分号，或到下一条 const/function/export 声明为止。"""
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

def test_s01_api_hub_types_and_mapping():
    """S01 / D01、兼容性：api.ts 导出三个新类型（HubChangeFallback/HubChangeSide/HubChange），PreviewData
    加必填的 hub_changes: HubChange[] 与 running_turns: string[]；toPreviewData 映射 hub_changes（逐项映射、
    映不出 post 的跳过）与 running_turns（stringsOf）；unreadable 照旧并入 notes；既有导出函数、
    WriteAction 成员与 PreviewData 既有八个字段一个不改。"""
    need_file(API_REL)
    text = read_rel(API_REL)
    code = strip_ts_comments(text)
    problems = []
    for tname in HUB_CHANGE_TYPES:
        if not re.search(rf"export interface {tname}\b", code):
            problems.append(f"api.ts 应以 export interface 导出类型 {tname}（写法钉死第 1 条）")
    preview = _block(code, "export interface PreviewData")
    if not preview:
        problems.append("api.ts 应保留 export interface PreviewData")
    else:
        if not re.search(r"^\s*hub_changes\s*:\s*HubChange\[\]", preview, re.M):
            problems.append("PreviewData 应加必填字段 hub_changes: HubChange[]（不是可选）")
        if re.search(r"hub_changes\?\s*:", preview):
            problems.append("hub_changes 应是必填（不能 hub_changes?:）")
        if not re.search(r"^\s*running_turns\s*:\s*string\[\]", preview, re.M):
            problems.append("PreviewData 应加必填字段 running_turns: string[]（不是可选）")
        if re.search(r"running_turns\?\s*:", preview):
            problems.append("running_turns 应是必填（不能 running_turns?:）")
        for field in OLD_PREVIEW_FIELDS:
            if not re.search(rf"^\s*{field}\s*:", preview, re.M):
                problems.append(f"PreviewData 既有字段 {field} 应保留")
    mapping = _block(code, "function toPreviewData")
    if not mapping:
        problems.append("api.ts 应保留 toPreviewData")
    else:
        if "hub_changes" not in mapping:
            problems.append("toPreviewData 应映射 hub_changes")
        if "running_turns" not in mapping or "stringsOf(preview.running_turns)" not in mapping:
            problems.append("toPreviewData 的 running_turns 应用 stringsOf(preview.running_turns)")
        for helper in ("hubChangeOf", "hubSideOf"):
            if helper not in code:
                problems.append(f"api.ts 应有映射辅助函数 {helper}（缺键与类型不对的兑底）")
        if "stringsOf(preview.unreadable)" not in mapping:
            problems.append("unreadable 照旧并入 notes（字符串清法不变）")
        if "needs_yes: preview.needs_yes === true" not in mapping:
            problems.append("needs_yes 的映射一个不改")
    for name in OLD_API_EXPORTS:
        if not re.search(rf"export function {name}\(", code):
            problems.append(f"api.ts 既有导出 {name} 应保留（只增不改）")
    for member in OLD_WRITE_ACTIONS:
        if f"'{member}'" not in code:
            problems.append(f"WriteAction 的既有成员 '{member}' 应保留")
    fail_if(problems, "api.ts 的三个新类型与映射（S01）")


def test_s02_snapshots_hub():
    """S02 / D02：snapshots.ts 加 hubSnapshot（HubRolesData 用 import type 从 ../api 引）；投影只有
    post/source/profile/fallback_profile 四个字段、按 post 排序（既有 byKey）、fallback_profile 取
    row.fallback?.profile ?? null；既有七个快照导出一个不改。"""
    need_file(SNAPSHOTS_REL)
    text = read_rel(SNAPSHOTS_REL)
    code = strip_ts_comments(text)
    problems = []
    if not re.search(r"export function hubSnapshot\(", code):
        problems.append("snapshots.ts 应导出 hubSnapshot(hub: HubRolesData)")
    hub_type = _block(code, "export interface HubSnapshot")
    if not hub_type:
        problems.append("snapshots.ts 应导出 HubSnapshot 类型")
    else:
        for field in ("post", "source", "profile", "fallback_profile"):
            if not re.search(rf"^\s*{field}\s*:", hub_type, re.M):
                problems.append(f"HubSnapshot 的 posts 应只有 post/source/profile/fallback_profile 四字段（看不到 {field}）")
    hub_fn = _block(code, "export function hubSnapshot")
    if hub_fn:
        if "byKey" not in hub_fn:
            problems.append("hubSnapshot 应用文件里既有的 byKey 按 post 排序")
        if "fallback?.profile ?? null" not in hub_fn.replace("row.fallback", "fallback"):
            if "fallback?.profile ?? null" not in hub_fn:
                problems.append("fallback_profile 应取 row.fallback?.profile ?? null")
    else:
        problems.append("找不到 hubSnapshot 的函数体")
    # import type（HubRolesData 是纯类型引入，不产生运行时依赖）
    api_imports = re.findall(r"import[^;]*?from\s*['\"]\.\./api['\"]", text, re.S)
    if not api_imports or not any("HubRolesData" in stmt and stmt.lstrip().startswith("import type") for stmt in api_imports):
        problems.append("snapshots.ts 应以 import type 从 ../api 引入 HubRolesData")
    for name in ("presetSnapshot", "pluginSnapshot", "presetRemoveSnapshot", "profileRemoveSnapshot",
                 "runtimeRemoveSnapshot", "profileSnapshot", "rollbackSnapshot", "sameSnapshot"):
        if not re.search(rf"export function {name}\(", code):
            problems.append(f"既有快照导出 {name} 应保留")
    fail_if(problems, "snapshots.ts 的 hubSnapshot（S02）")


def test_s03_usewriteflow_hub_branches():
    """S03 / D03、D04：useWriteFlow 的 readSnapshot 给 hub.set/hub.unset 读 getHubRoles（不再落到
    getPlugins 兑底，分支写法照合同 v2「写法钉死」第 3 条）；confirm 分支链加 setHubRole/unsetHubRole 且
    排在 setPluginEnabled 之前；三个表（titleOf/successTextOf/changeSummaryOf）的逐字文案；content 加
    hubChanges/runningTurns；原因句与三个条件片段同一物理行（合同 v2 钉死）、原文一字不改；
    contentOf 缺省补两个空数组。"""
    need_file(USEWRITEFLOW_REL)
    text = read_rel(USEWRITEFLOW_REL)
    code = strip_ts_comments(text)
    problems = []
    # readSnapshot 的 hub 分支：读 getHubRoles，且在 getPlugins 兑底分支之前
    snap = _block(code, "async function readSnapshot")
    if not snap:
        problems.append("useWriteFlow 应保留 readSnapshot")
    else:
        hub_branch = re.search(r"if \(action === 'hub\.set' \|\| action === 'hub\.unset'\) \{", snap)
        if not hub_branch:
            problems.append("readSnapshot 应照「写法钉死」第 3 条写 if (action === 'hub.set' || action === 'hub.unset') {")
        else:
            seg = snap[hub_branch.start():]
            if "getHubRoles()" not in seg[:600]:
                problems.append("hub 分支应读 getHubRoles()")
            if "hubSnapshot" not in seg[:800]:
                problems.append("hub 分支成功时应回 hubSnapshot(...)（不是 pluginSnapshot）")
        if snap.find("getHubRoles()") > snap.find("getPlugins()") >= 0:
            problems.append("hub 分支应排在 getPlugins 兑底分支之前（hub 动作不再落到插件快照）")
    # confirm 分支链：setHubRole/unsetHubRole 在 setPluginEnabled 之前
    confirm = _block(code, "const confirm = useCallback")
    if not confirm:
        problems.append("useWriteFlow 应保留 confirm")
    else:
        for call in ("setHubRole(", "unsetHubRole("):
            if call not in confirm:
                problems.append(f"confirm 的分支链应有 {call[:-1]}")
        idx_set = confirm.find("setHubRole(")
        idx_unset = confirm.find("unsetHubRole(")
        idx_plugin = confirm.find("setPluginEnabled(")
        if -1 < idx_plugin < max(idx_set, idx_unset):
            problems.append("setHubRole/unsetHubRole 应排在 setPluginEnabled 之前（hub 动作不再误调插件启停）")
    # 三个表的逐字文案（模板字面量按片段查）
    title_fn = _block(code, "function titleOf")
    if not title_fn or "改绑定" not in title_fn or "恢复缺省" not in title_fn:
        problems.append("titleOf 应补 hub.set（改绑定 …？）与 hub.unset（恢复缺省 …？）")
    success_fn = _block(code, "function successTextOf")
    if not success_fn or "已改绑定" not in success_fn or "已恢复缺省" not in success_fn:
        problems.append("successTextOf 应补已改绑定 …/已恢复缺省 …")
    summary_fn = _block(code, "function changeSummaryOf")
    for token in ("的主绑定改成", "没有替补", "，替补 ", "回到内核缺省"):
        if not summary_fn or token not in summary_fn:
            problems.append(f"changeSummaryOf 应含逐字文案「{token}」")
    # content 加两个字段；原因句条件与原文
    run_preview = _block(code, "const runPreview = useCallback")
    if not run_preview:
        problems.append("useWriteFlow 应保留 runPreview")
    else:
        if "hubChanges: data.hub_changes" not in run_preview:
            problems.append("content 应加 hubChanges: data.hub_changes")
        if "runningTurns: data.running_turns" not in run_preview:
            problems.append("content 应加 runningTurns: data.running_turns")
        cond_line = ""
        for line in run_preview.splitlines():
            if REASON in line:
                cond_line = line
                break
        if not cond_line:
            cond_line = run_preview
        for frag in ("needs_yes === true", "running_attempts.length === 0", "running_turns.length === 0"):
            if frag not in cond_line:
                problems.append(f"原因句条件应同时含 {frag}（D04：attempt 与回合都空才出）")
                break
        if REASON not in text:
            problems.append("原因句原文应一字不改地保留")
    content_of = _block(code, "const contentOf = useCallback")
    if not content_of:
        problems.append("useWriteFlow 应保留 contentOf")
    else:
        if "hubChanges: []" not in content_of or "runningTurns: []" not in content_of:
            problems.append("contentOf 的缺省 ConfirmContent 应补 hubChanges: [] 与 runningTurns: []")
    # 引入：读与写的新名字
    for name in ("getHubRoles", "setHubRole", "unsetHubRole", "hubSnapshot"):
        if not re.search(rf"\b{name}\b", code):
            problems.append(f"useWriteFlow 应引入并使用 {name}")
    fail_if(problems, "useWriteFlow 的 hub 分支与文案（S03）")


def test_s04_hubchangelines_file():
    """S04 / D06：新文件 src/writes/hubChangeLines.ts——导出 hubChangeLines 与 hubPostLabel；只 import type
    自 ../api（不跨层引 src/pages、不引运行时 api）；六个岗位中文名（含括号里的岗位码）逐字在位；
    四行的字段名（运行时/模型/思考档位/替补）与「默认」标记、「—」兑底、替补文字的规则记号都在；
    文件注释写明中文名表另维护一份的理由（T038 钉了 roles-logic，不跨层）。"""
    need_file(HUBLINES_REL)
    text = read_rel(HUBLINES_REL)
    code = strip_ts_comments(text)
    problems = []
    if not re.search(r"export function hubChangeLines\(", code):
        problems.append("hubChangeLines.ts 应导出 hubChangeLines(change: HubChange): string[]")
    if not re.search(r"export function hubPostLabel\(", code):
        problems.append("hubChangeLines.ts 应导出 hubPostLabel(post: string): string")
    imports = re.findall(r"import[^;]*?from\s*['\"][^'\"]+['\"]", text)
    api_imports = [s for s in imports if "../api" in s]
    if not api_imports or any(not s.lstrip().startswith("import type") for s in api_imports):
        problems.append("hubChangeLines.ts 从 ../api 只许 import type（纯函数不引运行时 api）")
    if any("pages" in s for s in imports):
        problems.append("hubChangeLines.ts 不应跨层引 src/pages（roles-logic 的 hubPostName 不动）")
    for post, label in HUB_POST_LABELS.items():
        if f"{label}（{post}）" not in text:
            problems.append(f"hubPostLabel 应含「{label}（{post}）」")
    for token in ("运行时：", "模型：", "思考档位：", "替补："):
        if token not in code:
            problems.append(f"四行文案应含前缀「{token}」")
    if "（默认）" not in code:
        problems.append("「默认」标记的文案（默认）应在位")
    if "'—'" not in code and '"—"' not in code:
        problems.append("兑底占位符 — 应在位")
    # 纯函数：不碰 DOM、不取时钟
    for bad in ("document.", "window.", "Date.now", "performance.", "setTimeout", "setInterval"):
        if bad in code:
            problems.append(f"hubChangeLines 是纯函数，不应出现 {bad}")
    # 另维护一份的理由写进注释（合同第 5 步）
    if not re.search(r"roles-logic|hubPostName", text):
        problems.append("文件注释应写明中文名表另维护一份的理由（roles-logic 的 hubPostName 被 T038 钉住）")
    fail_if(problems, "hubChangeLines 新文件（S04）")


def test_s05_dialog_hub_sections():
    """S05 / D04、D05：WriteConfirmDialog 的 ConfirmContent 加必填 hubChanges: HubChange[] 与
    runningTurns: string[]；「变化」一节渲染岗位块（hubPostLabel 小标题 + hubChangeLines 四行，wf-hub 类）；
    changes 空且 hubChanges 非空时不显示「预览没有列出变化」也不显示 summary；「影响与风险」逐行渲染
    runningTurns（逐字后半句）且 hasRisk 算上 runningTurns；「有 attempt 正在运行：…」那行一字不改。"""
    need_file(DIALOG_REL)
    text = read_rel(DIALOG_REL)
    code = strip_ts_comments(text)
    problems = []
    content = _block(code, "export interface ConfirmContent")
    if not content:
        problems.append("WriteConfirmDialog 应保留 ConfirmContent")
    else:
        if not re.search(r"^\s*hubChanges\s*:\s*HubChange\[\]", content, re.M):
            problems.append("ConfirmContent 应加必填字段 hubChanges: HubChange[]")
        if re.search(r"hubChanges\?\s*:", content):
            problems.append("hubChanges 应是必填（不能 hubChanges?:）")
        if not re.search(r"^\s*runningTurns\s*:\s*string\[\]", content, re.M):
            problems.append("ConfirmContent 应加必填字段 runningTurns: string[]")
        if re.search(r"runningTurns\?\s*:", content):
            problems.append("runningTurns 应是必填（不能 runningTurns?:）")
        for field in ("command", "changes", "warnings", "running", "notes"):
            if not re.search(rf"^\s*{field}\s*:", content, re.M):
                problems.append(f"ConfirmContent 既有字段 {field} 应保留")
    # 引入：写法钉死第 4 条的两条 import（api 那条同时带 BindingChange 与 HubChange）
    api_import = re.search(r"import type\s*\{[^}]*\}\s*from\s*['\"]\.\./api['\"]", text, re.S)
    if not api_import or "BindingChange" not in api_import.group(0) or "HubChange" not in api_import.group(0):
        problems.append("WriteConfirmDialog 应照写法钉死写 import type { BindingChange, HubChange } from '../api'")
    hub_import = re.search(r"import\s*\{[^}]*\}\s*from\s*['\"]\./hubChangeLines['\"]", text, re.S)
    if not hub_import or "hubChangeLines" not in hub_import.group(0) or "hubPostLabel" not in hub_import.group(0):
        problems.append("WriteConfirmDialog 应照写法钉死写 import { hubChangeLines, hubPostLabel } from './hubChangeLines'")
    if "hubPostLabel" not in code or "hubChangeLines" not in code:
        problems.append("岗位块的小标题应用 hubPostLabel、四行应用 hubChangeLines（共用同一份纯逻辑）")
    if "wf-hub" not in code:
        problems.append("岗位块的类名应用 wf-hub 前缀（与 CSS 三条新规则对上）")
    # 变化区的空态：changes 空且 hubChanges 非空时不显示空态文案（Changes 组件同时收两个数组）
    changes_fn = _block(code, "function Changes")
    if not changes_fn:
        problems.append("WriteConfirmDialog 应保留 Changes 组件")
    else:
        if "hubChanges" not in changes_fn:
            problems.append("Changes 应同时收 hubChanges（changes 空且 hubChanges 非空时不出「预览没有列出变化」）")
    # 影响与风险：runningTurns 逐行 + hasRisk
    risks_fn = _block(code, "function Risks")
    if not risks_fn:
        problems.append("WriteConfirmDialog 应保留 Risks 组件")
    else:
        if "runningTurns" not in risks_fn:
            problems.append("Risks 应逐行渲染 runningTurns")
        if TURNS_NOTE not in risks_fn:
            problems.append("在跑的回合那行应含逐字后半句「在跑的回合照旧用原来的绑定，下一个回合起用新的；这次改动需要你确认。」")
        if not re.search(r"runningTurns\.length\s*>\s*0", risks_fn):
            problems.append("hasRisk 应算上 content.runningTurns.length > 0")
        if ATTEMPT_PREFIX not in risks_fn:
            problems.append("「有 attempt 正在运行：…」那行应一字不改")
    fail_if(problems, "WriteConfirmDialog 的岗位块与在跑回合（S05）")


def test_s06_css_append_only():
    """S06 / D10：write-flow.css 只在末尾追加——基线 1597 字节（行尾归一 LF）原样保留为前缀，末尾新增
    .wf-hub、.wf-hub__post、.wf-hub__line 三条规则；只用 --tt-* 令牌、不声明令牌、不写死颜色；
    px 字面量除 0 与 1px 外要带出处注释。"""
    need_file(WF_CSS_REL)
    path = REPO_ROOT / WF_CSS_REL
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    baseline_len, baseline_sha = BASELINE_WF_CSS
    problems = []
    if hashlib.sha256(raw[:baseline_len]).hexdigest() != baseline_sha:
        problems.append("write-flow.css 的基线 1597 字节应原样保留（只在末尾追加，不改既有规则）")
    text = raw.decode("utf-8")
    appended = raw[baseline_len:].decode("utf-8")
    if not appended.strip():
        problems.append("write-flow.css 末尾应追加岗位块的规则")
    for rule in (".wf-hub", ".wf-hub__post", ".wf-hub__line"):
        if rule + " {" not in appended and rule + "{" not in appended:
            problems.append(f"末尾应追加规则 {rule}")
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in appended:
            problems.append(f"新增 CSS 里不应出现 {bad}")
    if _HEX_COLOR.search(appended) or any(fn in appended for fn in _COLOR_FUNCS):
        problems.append("新增 CSS 不应写死颜色（只用 --tt-* 令牌）")
    if "--tt-" not in appended and appended.strip():
        problems.append("新增 CSS 应使用 --tt-* 令牌")
    for m in re.finditer(r"(\d+(?:\.\d+)?)px", appended):
        value = m.group(1)
        if value in ("0", "1"):
            continue
        line_start = appended.rfind("\n", 0, m.start()) + 1
        line_end = appended.find("\n", m.end())
        line = appended[line_start:line_end]
        if not re.search(r"出处|照 .*的写法|与 .*同口径", line):
            problems.append(f"px 字面量 {value}px 所在行要带出处注释：{line.strip()[:60]}")
    fail_if(problems, "write-flow.css 只在末尾追加（S06）")


def test_s07_mock_writes_hub_scenarios():
    """S07 / D07、D12：mock/writes.ts 的 WriteScenario 与 SCENARIOS 加四个取值（共 27 个，既有 23 个
    一个不改）；hub.set/hub.unset 的预览按夹具算 hub_changes（引入 HUB_ROLES_POSTS 与 profiles.json，
    缺省表注释写明出自 scripts/kit_roles.py）；四个情景的逐字取值在位；新写的岗位桩数据不引入
    step-low（既有 6 处演示字面量保留不动）；previewData 的 6 处 PreviewData 字面量都补了两个字段；
    既有 23 个情景的写函数与确认号核对一个不改。"""
    need_file(MOCK_WRITES_REL)
    text = read_rel(MOCK_WRITES_REL)
    code = strip_ts_comments(text)
    problems = []
    union = re.search(r"export type WriteScenario\s*=([\s\S]*?);", code)
    if not union:
        problems.append("mock/writes.ts 应保留 WriteScenario 类型")
    else:
        members = set(re.findall(r"'([a-z0-9-]+)'", union.group(1)))
        for value in NEW_SCENARIOS:
            if value not in members:
                problems.append(f"WriteScenario 应加新取值 '{value}'")
        for value in OLD_SCENARIOS:
            if value not in members:
                problems.append(f"既有情景值 '{value}' 一个不改")
        extra = members - set(OLD_SCENARIOS) - set(NEW_SCENARIOS)
        if extra:
            problems.append(f"情景里出现了名单之外的取值：{sorted(extra)}")
    scenarios_list = _block(code, "const SCENARIOS")
    for value in NEW_SCENARIOS:
        if value not in scenarios_list:
            problems.append(f"SCENARIOS 里应有 '{value}'")
    # 夹具来源：引入 hub-roles 与 profiles.json
    if "from './hub-roles'" not in text:
        problems.append("mock/writes.ts 应引入 './hub-roles' 的 HUB_ROLES_POSTS（before 取夹具该行）")
    if "profiles.json" not in text:
        problems.append("mock/writes.ts 应引入 './profiles.json'（after 取所选 profile）")
    if "HUB_ROLES_POSTS" not in code:
        problems.append("before 应从 HUB_ROLES_POSTS 取该岗位的一行")
    # 缺省表：注释写明出自 kit_roles.py（另放一份）
    if "kit_roles" not in text:
        problems.append("缺省表（HUB_DEFAULTS）的注释应写明出自 scripts/kit_roles.py")
    # hub 预览不再是空壳：按夹具算 hub_changes
    preview_fn = _block(code, "function previewData")
    hub_branch = re.search(r"action === 'hub\.set'\s*\|\|\s*action === 'hub\.unset'", preview_fn or "")
    if not hub_branch:
        problems.append("previewData 的 hub.set/hub.unset 分支应在位")
    else:
        seg = preview_fn[hub_branch.start():hub_branch.start() + 1400]
        if "hub_changes" not in seg:
            problems.append("hub 分支的预览应算 hub_changes（不再是空壳）")
    # 情景取值逐字
    for token in (HUB_WARN_TEXT, HUB_RUNNING_TURN):
        if token not in text:
            problems.append(f"桩里应逐字出现「{token}」（hub-warn/hub-running 的取值）")
    if "hub-unset" not in code or "hub-ok" not in code:
        problems.append("四个岗位情景都应在位（hub-ok/hub-warn/hub-running/hub-unset）")
    # D12（v2）：新写的岗位桩数据不引入 step-low，既有 6 处演示字面量保留不动——注释剥离后处数应恰为 6
    # （基线：binding_changes 两处、in-use 一处、错误文案三处；都在既有演示代码里，新桩数据里多出任何
    # 一处都会让计数变大，删改既有文案会让计数变小，两个方向都红）。
    step_low_count = code.count("step-low")
    if step_low_count != BASELINE_STEP_LOW_COUNT:
        problems.append(
            f"注释剥离后 step-low 应恰为基线的 {BASELINE_STEP_LOW_COUNT} 处（D12 v2：既有演示字面量一个不改、"
            f"新写的岗位桩数据不引入这个 id），实际 {step_low_count} 处"
        )
    # 写法钉死第 6 条与步骤 8：PreviewData 变必填后，previewData 里 6 处字面量每处都补两个字段
    # （hub 分支算真值，其余 5 处补空数组；未知岗位的空数组也在 hub 分支里，故下限 5）。
    if code.count("hub_changes: []") < 5:
        problems.append("previewData 的 6 处 PreviewData 字面量应每处补 hub_changes（非 hub 分支为空数组）")
    if code.count("running_turns: []") < 5:
        problems.append("previewData 的 6 处 PreviewData 字面量应每处补 running_turns（非 hub 分支为空数组）")
    # 既有写函数与确认号核对不改
    for fn in ("mockPreview", "mockSetHubRole", "mockUnsetHubRole", "confirmWrite", "mockGetOperation"):
        if not re.search(rf"function {fn}\(", code):
            problems.append(f"既有函数 {fn} 应保留")
    fail_if(problems, "mock/writes.ts 的四个岗位情景（S07）")


def test_s08_executor_tests():
    """S08 / D01、D03–D08、D11：三个新测试文件在位且覆盖记号齐备；三处自己造数据的既有夹具（
    writes-flow/writes-profile-form 的预览 data + writes-dialog 的 ConfirmContent）补了两个新字段；
    都不许 skip/only/todo。"""
    problems = []
    for rel, tokens in (
        (EXEC_API_TEST_REL, EXECUTOR_TEST_TOKENS["writes-hub-api.test.ts"]),
        (EXEC_LOGIC_TEST_REL, EXECUTOR_TEST_TOKENS["writes-hub-logic.test.ts"]),
        (EXEC_FLOW_TEST_REL, EXECUTOR_TEST_TOKENS["writes-hub-flow.test.tsx"]),
    ):
        need_file(rel)
        text = read_rel(rel)
        for token in tokens:
            if token not in text:
                problems.append(f"{rel} 应含记号「{token}」（合同第 10 步点名的覆盖点）")
        problems.extend(f"{rel}: {p}" for p in _no_skip_marks(text))
    # 两处既有预览夹具补字段（writes-flow.test.tsx 与 writes-profile-form.test.tsx 的预览 data）
    for rel in (WRITES_FLOW_TEST_REL, PROFILE_FORM_TEST_REL):
        need_file(rel)
        text = read_rel(rel)
        if "hub_changes" not in text:
            problems.append(f"{rel} 自造的预览 data 应补 hub_changes 字段（PreviewData 加了必填字段）")
        if "running_turns" not in text:
            problems.append(f"{rel} 自造的预览 data 应补 running_turns 字段")
        problems.extend(f"{rel}: {p}" for p in _no_skip_marks(text))
    # 第三处夹具（合同 v2 新增）：writes-dialog.test.tsx 的 CONTENT（ConfirmContent）补两个字段——
    # 漏了它确认框读 content.runningTurns.length 会抛 undefined.length，V01 直接挂
    need_file(WRITES_DIALOG_TEST_REL)
    dialog_text = read_rel(WRITES_DIALOG_TEST_REL)
    if "hubChanges" not in dialog_text:
        problems.append(f"{WRITES_DIALOG_TEST_REL} 的 CONTENT 夹具应补 hubChanges（ConfirmContent 加了必填字段）")
    if "runningTurns" not in dialog_text:
        problems.append(f"{WRITES_DIALOG_TEST_REL} 的 CONTENT 夹具应补 runningTurns（漏了它会读 undefined.length 抛错）")
    problems.extend(f"{WRITES_DIALOG_TEST_REL}: {p}" for p in _no_skip_marks(dialog_text))
    fail_if(problems, "执行端测试文件与三处既有夹具补字段（S08）")


def test_s09_shared_surfaces():
    """S09 / D07–D10：共享面——src/mock 仍恰 14 份 JSON、src/pages 顶层仍 9 个 *Page.tsx；package.json 与
    锁文件字节冻结；禁改的两份既有测试（writes-live-flow/live-api）仍在、无 skip/only/todo，且 T040/T037
    的既有记号仍在（不被删、不被弱化）；scripts/kit_roles.py 的 HUB_DEFAULTS 没被动。"""
    problems = []
    mock_jsons = sorted(p.name for p in (REPO_ROOT / SRC_REL / "mock").glob("*.json"))
    if len(mock_jsons) != BASELINE_MOCK_JSON_COUNT:
        problems.append(f"src/mock 应仍恰 {BASELINE_MOCK_JSON_COUNT} 份 JSON，实际 {len(mock_jsons)}：{mock_jsons}")
    pages = sorted(p.name for p in (REPO_ROOT / SRC_REL / "pages").glob("*Page.tsx"))
    if len(pages) != BASELINE_PAGE_COUNT:
        problems.append(f"src/pages 顶层应仍恰 {BASELINE_PAGE_COUNT} 个 *Page.tsx，实际 {len(pages)}：{pages}")
    for rel, digest in BASELINE_DIGESTS.items():
        got = file_digest(REPO_ROOT / rel)
        if got != digest:
            problems.append(f"{rel} 应字节冻结（行尾归一 LF 后 {digest[0]} 字节），实际 {got}")
    # 禁改的既有测试仍在且没被弱化
    live_flow = read_rel(need_file(LIVE_FLOW_TEST_REL))
    if REASON not in live_flow or ATTEMPT_PREFIX not in live_flow:
        problems.append("writes-live-flow.test.tsx 里 T040 锁定的原因句/attempt 说法记号应仍在")
    problems.extend("writes-live-flow.test.tsx: " + p for p in _no_skip_marks(live_flow))
    live_api = read_rel(need_file(LIVE_API_TEST_REL))
    if "running_attempts" not in live_api or "unreadable" not in live_api:
        problems.append("live-api.test.tsx 里 T037 的预览映射记号应仍在")
    problems.extend("live-api.test.ts: " + p for p in _no_skip_marks(live_api))
    # 内核缺省表没被动（本片不改 scripts/）
    kit = read_rel(need_file(KIT_ROLES_REL))
    if '"audit": {"adapter": "pi", "provider": "minimax", "model": "MiniMax-M3.1-Flash", "thinking": "max"' not in kit:
        problems.append("scripts/kit_roles.py 的 HUB_DEFAULTS 不应被动过（只读引用）")
    fail_if(problems, "共享面与禁改面（S09）")


def test_s10_new_files_source_rules():
    """S10 / D10：新源码守既有规矩——hubChangeLines.ts 与 mock/writes.ts 的改动不出现网络词、危险写入、
    matchMedia 一类、role=status、「（UTC 」字面量；岗位中文名表只在 hubChangeLines 里另维护（不跨层引
    src/pages/readonly1）。"""
    problems = []
    hub_lines_path = REPO_ROOT / HUBLINES_REL
    if hub_lines_path.is_file():
        text = read_rel(HUBLINES_REL)
        for bad in FORBIDDEN_SOURCE_MARKS:
            if bad in text:
                problems.append(f"hubChangeLines.ts 不应出现 {bad}")
        if _HEX_COLOR.search(text) or any(fn in text for fn in _COLOR_FUNCS):
            problems.append("hubChangeLines.ts 不应写死颜色")
    mock_text = read_rel(need_file(MOCK_WRITES_REL))
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in mock_text:
            problems.append(f"mock/writes.ts 不应出现 {bad}（page-static.test.ts 的口径）")
    # 确认框与写流程的改动面：不新增禁词（这两个文件是改，不是新）
    for rel in (DIALOG_REL, USEWRITEFLOW_REL):
        text = read_rel(need_file(rel))
        for bad in ("matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver", "role=\"status\"", "（UTC "):
            if bad in text:
                problems.append(f"{rel} 不应出现 {bad}")
    fail_if(problems, "新源码的规矩（S10）")


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 T043 门禁的写法）
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


def t044_marker_present():
    """候选里 api.ts 是否已有 T044 的标记（hub_changes）：没有就不起 npm（基线上必然没有）。"""
    path = REPO_ROOT / API_REL
    if not path.is_file():
        return False
    try:
        return "hub_changes" in _read(path)
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
    if not t044_marker_present():
        pipe.reason = ("候选里 api.ts 还没有 T044 的标记（hub_changes），没有东西可测，未调用 npm；"
                       "候选把映射、快照与岗位块接上之后，流水线才会运行 npm ci、Vitest 与探针")
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
                    name = f"probe-{uid}-t044-{key}.test.tsx"
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
# 探针（黑盒 Vitest 用例，临时写进 desktop/web/gate-probe/，跑完即删；每份自带全部辅助函数）
# ---------------------------------------------------------------------------

UNIT_PROBE = r'''// T044 门禁 unit 探针：hubChangeLines/hubPostLabel/hubSnapshot 的纯函数、api 真实模式的映射与写路由、
// 桩的四个岗位情景。不 mock 被测模块，只注入假服务（照 tests/writes-live-flow.test.tsx 的写法）。
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { preview, setHubRole, unsetHubRole, type Envelope, type HubChange, type HubChangeFallback, type HubChangeSide, type PreviewData } from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { hubChangeLines, hubPostLabel } from '../src/writes/hubChangeLines';
import { hubSnapshot } from '../src/writes/snapshots';
import { HUB_ROLES_POSTS } from '../src/mock/hub-roles';

const CONF = 'conf-unit-1';
const RUNNING_TURN = '审核端（audit）：2 个回合在跑';
const WARN_TEXT = '合同端与审核端用的是同一个模型（bb/step-5-preview）：审核少一层独立性；照样生效';

function envelope<T>(data: T, command: string[] = []): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 3 };
}

let previewJson: Record<string, unknown> = {};
const posts: Array<{ path: string; body: unknown }> = [];

const fake: LiveClient = {
  get: () => Promise.reject(new Error('unit 探针没有编排 get')),
  post<T>(path: string, body: unknown): Promise<{ status: number; body: Envelope<T> }> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      return Promise.resolve({ status: 200, body: envelope({ preview: previewJson, confirmation: CONF }) as unknown as Envelope<T> });
    }
    return Promise.resolve({ status: 200, body: envelope(null) as unknown as Envelope<T> });
  },
  getRaw: () => Promise.reject(new Error('unit 探针没有编排 getRaw')),
};

async function readData(action: 'hub.set' | 'hub.unset', args: Record<string, string>): Promise<PreviewData> {
  const r = await preview(action, args);
  expect(r.status).toBe(200);
  expect(r.body.ok).toBe(true);
  expect(r.body.data).not.toBeNull();
  return r.body.data as PreviewData;
}

const side = (o: Partial<HubChangeSide> = {}): HubChangeSide => ({
  source: 'config', profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null, fallback: null, ...o,
});
const fb = (o: Partial<HubChangeFallback> = {}): HubChangeFallback => ({
  profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null, ...o,
});
const fixtureBefore = side({
  source: 'config', profile: 'quizs-m3', runtime: 'quizs', adapter: 'quizs',
  provider: 'minimax', model: 'MiniMax-M3.1-Flash', thinking: 'high',
  fallback: fb({ profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' }),
});
const fixtureAfter = side({
  source: 'config', profile: 'step-high', runtime: 'pi', adapter: 'pi',
  provider: 'bb', model: 'step-5-preview', thinking: 'high',
});

describe('hubChangeLines 与 hubPostLabel（D06）', () => {
  it('恰好四行、次序固定：运行时/模型/思考档位/替补，无替补显示 —', () => {
    const lines = hubChangeLines({ post: 'contract', before: fixtureBefore, after: fixtureAfter });
    expect(lines).toEqual([
      '运行时：quizs · quizs → pi · pi',
      '模型：minimax/MiniMax-M3.1-Flash → bb/step-5-preview',
      '思考档位：high → high',
      '替补：step-high → —',
    ]);
  });
  it('缺省一侧标（默认），标在该侧每个值的后面（含替补行）', () => {
    const lines = hubChangeLines({
      post: 'exec',
      before: side({ source: 'config', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' }),
      after: { source: 'default', profile: null, runtime: null, adapter: 'pi', provider: 'cc-switch-step-fun', model: 'step-5-preview', thinking: 'high', fallback: null },
    });
    expect(lines[0]).toBe('运行时：pi · pi → — · pi（默认）');
    expect(lines[1]).toBe('模型：bb/step-5-preview → cc-switch-step-fun/step-5-preview（默认）');
    expect(lines[2]).toBe('思考档位：high → high（默认）');
    expect(lines[3]).toBe('替补：— → —（默认）');
  });
  it('一侧为 null：全是 —，不标（默认）', () => {
    const lines = hubChangeLines({
      post: 'gate',
      before: null,
      after: side({ runtime: 'pi', adapter: 'pi', provider: 'cc-switch-zhipu-glm', model: 'glm-5.3', thinking: 'high' }),
    });
    expect(lines).toEqual([
      '运行时：— · — → pi · pi',
      '模型：—/— → cc-switch-zhipu-glm/glm-5.3',
      '思考档位：— → high',
      '替补：— → —',
    ]);
  });
  it('替补没有 profile 时按 runtime · provider/model 拼，各字段兑 —', () => {
    const lines = hubChangeLines({
      post: 'coordinator',
      before: side({ fallback: fb({ runtime: 'pi', provider: 'dsf', model: 'deepseek-flash' }) }),
      after: side({ fallback: fb({ profile: 'step-high' }) }),
    });
    expect(lines[3]).toBe('替补：pi · dsf/deepseek-flash → step-high');
  });
  it('hubPostLabel：六个中文名带岗位码，未知码原样', () => {
    expect(hubPostLabel('coordinator')).toBe('协调人（coordinator）');
    expect(hubPostLabel('planner')).toBe('规划端（planner）');
    expect(hubPostLabel('contract')).toBe('合同端（contract）');
    expect(hubPostLabel('gate')).toBe('门禁端（gate）');
    expect(hubPostLabel('audit')).toBe('审核端（audit）');
    expect(hubPostLabel('exec')).toBe('执行端（exec）');
    expect(hubPostLabel('zz-9')).toBe('zz-9');
  });
});

describe('hubSnapshot（D02）', () => {
  it('投影只有四字段、按 post 排序、替补的 profile 缺省为 null', () => {
    const snap = hubSnapshot(HUB_ROLES_POSTS);
    expect(snap.posts.map((p) => p.post)).toEqual(['audit', 'contract', 'coordinator', 'exec', 'gate', 'planner']);
    const byPost = Object.fromEntries(snap.posts.map((p) => [p.post, p]));
    expect(Object.keys(byPost.contract).sort()).toEqual(['fallback_profile', 'post', 'profile', 'source']);
    expect(byPost.contract.profile).toBe('quizs-m3');
    expect(byPost.contract.fallback_profile).toBe('step-high');
    expect(byPost.coordinator.fallback_profile).toBeNull();
    expect(byPost.exec.source).toBe('config');
  });
});

describe('api 真实模式的映射与写路由（D01、D11）', () => {
  beforeEach(() => {
    posts.length = 0;
    previewJson = {};
    setLiveClientForTests(fake);
  });
  afterEach(() => setLiveClientForTests(undefined));
  it('hub_changes 逐字段映射；post 非字符串跳过；侧与替补形状不对归 null；running_turns 只留字符串', async () => {
    previewJson = {
      binding_changes: [], resources: [{ resource: 'hub' }], notes: ['note-1'], unreadable: ['path/x'],
      warnings: [], running_attempts: [], needs_yes: true,
      hub_changes: [
        { post: 'contract', before: fixtureBefore, after: fixtureAfter },
        { post: 7, before: null, after: null },
        { post: 'gate', before: 'not-object', after: { source: 'weird', profile: 1, runtime: 'pi', adapter: 'pi', provider: null, model: null, thinking: null, fallback: 'not-object' } },
      ],
      running_turns: [RUNNING_TURN, 5, null],
    };
    const d = await readData('hub.set', { post: 'contract', profile: 'step-high' });
    expect(d.hub_changes).toHaveLength(2);
    expect(d.hub_changes[0]).toEqual({ post: 'contract', before: fixtureBefore, after: fixtureAfter });
    expect(d.hub_changes[1]).toEqual({
      post: 'gate',
      before: null,
      after: { source: null, profile: null, runtime: 'pi', adapter: 'pi', provider: null, model: null, thinking: null, fallback: null },
    });
    expect(d.running_turns).toEqual([RUNNING_TURN]);
    expect(d.notes).toEqual(['note-1', 'path/x']);
    expect(d.needs_yes).toBe(true);
  });
  it('缺 hub_changes/running_turns 键时两个字段是空数组，不抛错', async () => {
    previewJson = { binding_changes: [], resources: [], notes: [], warnings: [], running_attempts: [], needs_yes: false };
    const d = await readData('hub.set', { post: 'contract', profile: 'step-high' });
    expect(d.hub_changes).toEqual([]);
    expect(d.running_turns).toEqual([]);
  });
  it('setHubRole/unsetHubRole 的路由与正文；fallback 缺省或空串都不带这个键（D11）', async () => {
    await setHubRole({ post: 'contract', profile: 'step-high', fallback: 'step-high' }, 'c1');
    expect(posts[posts.length - 1].path).toBe('/api/v1/hub/roles/contract');
    expect(posts[posts.length - 1].body).toEqual({ profile: 'step-high', fallback: 'step-high', confirmation: 'c1' });
    await setHubRole({ post: 'audit', profile: 'step-high' }, 'c2');
    expect(posts[posts.length - 1].path).toBe('/api/v1/hub/roles/audit');
    expect(posts[posts.length - 1].body).toEqual({ profile: 'step-high', confirmation: 'c2' });
    await setHubRole({ post: 'gate', profile: 'step-high', fallback: '' }, 'c4');
    expect(posts[posts.length - 1].body).toEqual({ profile: 'step-high', confirmation: 'c4' });
    await unsetHubRole('contract', 'c3');
    expect(posts[posts.length - 1].path).toBe('/api/v1/hub/roles/contract/unset');
    expect(posts[posts.length - 1].body).toEqual({ confirmation: 'c3' });
  });
});

describe('桩的四个岗位情景（D07、D12）', () => {
  beforeEach(() => {
    setLiveClientForTests(undefined);
    window.location.hash = '';
  });
  afterEach(() => {
    window.location.hash = '';
  });
  it('hub-warn：同模型警告逐字在 warnings，前后对比按夹具算', async () => {
    window.location.hash = '#/p?write=hub-warn';
    const d = await readData('hub.set', { post: 'contract', profile: 'step-high' });
    expect(d.warnings).toContain(WARN_TEXT);
    expect(d.hub_changes).toHaveLength(1);
    expect(d.hub_changes[0].post).toBe('contract');
    expect(d.hub_changes[0].before?.profile).toBe('quizs-m3');
    expect(d.hub_changes[0].after?.profile).toBe('step-high');
    expect(d.hub_changes[0].after?.source).toBe('config');
    expect(d.hub_changes[0].after?.provider).toBe('bb');
  });
  it('hub-running：running_turns 有一句且 needs_yes 为真', async () => {
    window.location.hash = '#/p?write=hub-running';
    const d = await readData('hub.set', { post: 'contract', profile: 'step-high' });
    expect(d.running_turns).toEqual([RUNNING_TURN]);
    expect(d.needs_yes).toBe(true);
  });
  it('hub-unset：before 取夹具该行，after 是内核缺省（source default、profile null）', async () => {
    window.location.hash = '#/p?write=hub-unset';
    const d = await readData('hub.unset', { post: 'contract' });
    expect(d.hub_changes).toHaveLength(1);
    const change = d.hub_changes[0];
    expect(change.before?.profile).toBe('quizs-m3');
    expect(change.after?.source).toBe('default');
    expect(change.after?.profile).toBeNull();
    expect(change.after?.adapter).toBe('pi');
    expect(change.after?.model).toBe('MiniMax-M3.1-Flash');
    expect(d.needs_yes).toBe(false);
  });
  it('ok 情景下 hub.set 带 fallback：after 的替补取该 profile 的字段（不出现 step-low）', async () => {
    window.location.hash = '#/p';
    const d = await readData('hub.set', { post: 'contract', profile: 'quizs-m3', fallback: 'step-high' });
    const after = d.hub_changes[0].after;
    expect(after?.profile).toBe('quizs-m3');
    expect(after?.fallback?.profile).toBe('step-high');
    expect(JSON.stringify(d)).not.toContain('step-low');
  });
  it('岗位不在夹具六行里 → hub_changes 是空数组（不崩）', async () => {
    window.location.hash = '#/p';
    const d = await readData('hub.set', { post: 'nope', profile: 'step-high' });
    expect(d.hub_changes).toEqual([]);
  });
  it('profile 不在 profiles.json 里：after.profile 照取、其余字段全 null、替补取不到为 null（v2 边界）', async () => {
    window.location.hash = '#/p';
    const d = await readData('hub.set', { post: 'contract', profile: 'zz-none', fallback: 'zz-none' });
    const after = d.hub_changes[0].after;
    expect(after?.source).toBe('config');
    expect(after?.profile).toBe('zz-none');
    expect(after?.runtime).toBeNull();
    expect(after?.adapter).toBeNull();
    expect(after?.provider).toBeNull();
    expect(after?.model).toBeNull();
    expect(after?.thinking).toBeNull();
    expect(after?.fallback).toBeNull();
  });
});
'''


FLOW_PROBE = r'''// T044 门禁 flow 探针：真实模式（注入假服务）挂真实的 useWriteFlow + WriteConfirmDialog，自带的按钮
// 触发 hub.set/hub.unset（入口表单是 B 片 T045 的活，这里只测写流程本身）。覆盖：确认发岗位路由且
// 不发 /api/v1/plugins/...（D11）、变化区四行前后对比与「默认」标记（D05）、needs_yes 的两种说法（D04）。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { useWriteFlow, type WriteSpec } from '../src/writes/useWriteFlow';
import { WriteFlow } from '../src/writes/WriteConfirmDialog';
import { HUB_ROLES_POSTS } from '../src/mock/hub-roles';
import type { Envelope, HubChangeFallback, HubChangeSide } from '../src/api';

const CONF = 'conf-flow-1';
const REASON = '有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。';
const TURNS_NOTE = '在跑的回合照旧用原来的绑定，下一个回合起用新的；这次改动需要你确认。';
const RUNNING_TURN = '审核端（audit）：2 个回合在跑';

let spec: WriteSpec = { action: 'hub.set', args: { post: 'contract', profile: 'step-high' } };

function Harness() {
  const { start, flow } = useWriteFlow();
  return (
    <>
      <button onClick={() => start(spec)}>go</button>
      <WriteFlow flow={flow} />
    </>
  );
}

function envelope<T>(data: T, command: string[] = []): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 3 };
}
function failEnvelope(messages: string[]): Envelope<null> {
  return { ok: false, exit_code: null, data: null, output: [], messages, command: [], elapsed_ms: 0 };
}

const side = (o: Partial<HubChangeSide> = {}): HubChangeSide => ({
  source: 'config', profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null, fallback: null, ...o,
});
const fb = (o: Partial<HubChangeFallback> = {}): HubChangeFallback => ({
  profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null, ...o,
});
const contractBefore = side({
  source: 'config', profile: 'quizs-m3', runtime: 'quizs', adapter: 'quizs',
  provider: 'minimax', model: 'MiniMax-M3.1-Flash', thinking: 'high',
  fallback: fb({ profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' }),
});
const stepHighAfter = side({
  source: 'config', profile: 'step-high', runtime: 'pi', adapter: 'pi',
  provider: 'bb', model: 'step-5-preview', thinking: 'high',
});
const execDefaultAfter: HubChangeSide = {
  source: 'default', profile: null, runtime: null, adapter: 'pi',
  provider: 'cc-switch-step-fun', model: 'step-5-preview', thinking: 'high', fallback: null,
};

function basePreview(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    binding_changes: [], resources: [{ resource: 'hub' }], notes: [], unreadable: [], warnings: [],
    running_attempts: [], running_turns: [], needs_yes: false,
    hub_changes: [{ post: 'contract', before: contractBefore, after: stepHighAfter }],
    ...over,
  };
}

const gets: string[] = [];
const posts: Array<{ path: string; body: unknown }> = [];
let previewJson: Record<string, unknown> = basePreview();
let execPlan: { status: number; body: Envelope<null> } | null = null;

const fake: LiveClient = {
  get<T>(path: string): Promise<Envelope<T>> {
    gets.push(path);
    if (path === '/api/v1/hub/roles') return Promise.resolve(envelope(HUB_ROLES_POSTS) as unknown as Envelope<T>);
    return Promise.resolve(failEnvelope([`flow 探针没有编排 ${path} 的应答`]) as unknown as Envelope<T>);
  },
  post<T>(path: string, body: unknown): Promise<{ status: number; body: Envelope<T> }> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      const command = spec.action === 'hub.set'
        ? ['config', 'hub', 'set', (spec.args as Record<string, string>).post, (spec.args as Record<string, string>).profile]
        : ['config', 'hub', 'unset', (spec.args as Record<string, string>).post];
      return Promise.resolve({ status: 200, body: envelope({ preview: previewJson, confirmation: CONF }, command) as unknown as Envelope<T> });
    }
    if (execPlan) return Promise.resolve({ status: execPlan.status, body: execPlan.body as unknown as Envelope<T> });
    return Promise.resolve({ status: 500, body: failEnvelope(['flow 探针没有编排执行应答']) as unknown as Envelope<T> });
  },
  getRaw<T>(): Promise<{ status: number; body: T }> {
    return Promise.resolve({ status: 404, body: null as unknown as T });
  },
};

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const dlg = () => document.querySelector('[role="dialog"][aria-modal="true"]') as HTMLElement | null;
const dlgText = () => {
  const d = dlg();
  expect(d, '写确认框应开着').not.toBeNull();
  return text(d as HTMLElement);
};
const bodyText = () => text(document.body);
const btn = (root: ParentNode, label: string) =>
  Array.from(root.querySelectorAll('button')).find((b) => text(b) === label) as HTMLButtonElement | undefined;

async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

async function openFlow() {
  render(<Harness />);
  await settle();
  fireEvent.click(btn(document.body, 'go') as HTMLButtonElement);
  await settle();
  dlgText();
}
async function confirmNow() {
  fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
  await settle();
  await advance(30);
  await settle();
}

beforeEach(() => {
  vi.useFakeTimers();
  window.location.hash = '';
  gets.length = 0;
  posts.length = 0;
  execPlan = null;
  previewJson = basePreview();
  spec = { action: 'hub.set', args: { post: 'contract', profile: 'step-high' } };
  setLiveClientForTests(fake);
});
afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  vi.useRealTimers();
  window.location.hash = '';
});

describe('岗位写路由（D03、D11）', () => {
  it('hub.set：预览与快照读走 getHubRoles，确认发 POST /api/v1/hub/roles/<post>，没有 /api/v1/plugins/...', async () => {
    execPlan = { status: 200, body: envelope(null, ['config', 'hub', 'set', 'contract', 'step-high']) };
    await openFlow();
    expect(gets).toContain('/api/v1/hub/roles');
    expect(gets).not.toContain('/api/v1/plugins');
    expect(dlgText()).toContain('改绑定 contract？');
    await confirmNow();
    const paths = posts.map((p) => p.path);
    expect(paths.filter((p) => p !== '/api/v1/preview')).toEqual(['/api/v1/hub/roles/contract']);
    expect(paths.some((p) => p.startsWith('/api/v1/plugins/'))).toBe(false);
    expect(posts[posts.length - 1].body).toEqual({ profile: 'step-high', confirmation: CONF });
    expect(bodyText()).toContain('已改绑定 contract');
  });
  it('hub.unset：确认发 POST /api/v1/hub/roles/<post>/unset，正文只有确认号', async () => {
    spec = { action: 'hub.unset', args: { post: 'contract' } };
    execPlan = { status: 200, body: envelope(null, ['config', 'hub', 'unset', 'contract']) };
    await openFlow();
    expect(dlgText()).toContain('恢复缺省 contract？');
    await confirmNow();
    const paths = posts.map((p) => p.path);
    expect(paths.filter((p) => p !== '/api/v1/preview')).toEqual(['/api/v1/hub/roles/contract/unset']);
    expect(posts[posts.length - 1].body).toEqual({ confirmation: CONF });
    expect(bodyText()).toContain('已恢复缺省 contract');
  });
});

describe('变化一节的岗位前后对比（D05）', () => {
  it('小标题 + 四行对比，changes 空且 hubChanges 非空时不显示「预览没有列出变化」', async () => {
    await openFlow();
    const t = dlgText();
    expect(t).toContain('合同端（contract）');
    expect(t).toContain('运行时：quizs · quizs → pi · pi');
    expect(t).toContain('模型：minimax/MiniMax-M3.1-Flash → bb/step-5-preview');
    expect(t).toContain('思考档位：high → high');
    expect(t).toContain('替补：step-high → —');
    expect(t).not.toContain('预览没有列出变化');
  });
  it('缺省一侧标（默认）', async () => {
    previewJson = basePreview({ hub_changes: [{ post: 'exec', before: stepHighAfter, after: execDefaultAfter }] });
    await openFlow();
    const t = dlgText();
    expect(t).toContain('执行端（exec）');
    expect(t).toContain('运行时：pi · pi → — · pi（默认）');
    expect(t).toContain('模型：bb/step-5-preview → cc-switch-step-fun/step-5-preview（默认）');
    expect(t).toContain('思考档位：high → high（默认）');
    expect(t).toContain('替补：— → —（默认）');
  });
});

describe('needs_yes 的两种说法（D04）', () => {
  it('unreadable 有值：原因句逐字排在 notes 第一条', async () => {
    previewJson = basePreview({ needs_yes: true, unreadable: ['状态/attempt-9'], notes: ['另一条说明'] });
    await openFlow();
    const notes = Array.from(document.querySelectorAll('.wf-note')).map((el) => text(el));
    expect(notes.length).toBeGreaterThan(0);
    expect(notes[0]).toBe(REASON);
    expect(dlgText()).toContain('影响与风险');
  });
  it('running_turns 有值：不出原因句，影响与风险逐行显示那句确认话', async () => {
    previewJson = basePreview({ needs_yes: true, running_turns: [RUNNING_TURN] });
    await openFlow();
    const t = dlgText();
    expect(t).not.toContain(REASON);
    expect(t).toContain(`${RUNNING_TURN}。${TURNS_NOTE}`);
    expect(t).toContain('影响与风险');
  });
});
'''

PROBE_SPECS = {
    "unit": (UNIT_PROBE, (API_REL, HUBLINES_REL, SNAPSHOTS_REL, MOCK_HUB_ROLES_REL, MOCK_PROFILES_REL, MOCK_WRITES_REL)),
    "flow": (FLOW_PROBE, (API_REL, USEWRITEFLOW_REL, DIALOG_REL, MOCK_HUB_ROLES_REL)),
}
PROBE_ORDER = ("unit", "flow")

# ---------------------------------------------------------------------------
# P 系列：流水线断言；D 系列：探针断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、D08：npm 依赖（已在就跳过）、npm test（全绿，含执行端三个新测试与补过字段的既有
    测试，T040/T037 的既有断言照旧通过）都退出 0；依赖文件一个字节没动；gate-probe/ 没有留下。"""
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


def test_d01_d02_d06_d07_d11_probe_unit(pipeline):
    """unit 探针 / D01、D02、D06、D07、D11：hubChangeLines 四行与「默认」标记、hubPostLabel 六名、
    hubSnapshot 投影排序、api 真实模式的映射兑底与写路由、桩四个岗位情景的取值与 step-low 不出现。"""
    assert_probe_ok(pipeline, "unit")


def test_d03_d04_d05_d11_probe_flow(pipeline):
    """flow 探针 / D03、D04、D05、D11：真实模式下确认发岗位路由且没有 /api/v1/plugins/...、变化区
    四行前后对比与缺省标记、needs_yes 的两种说法（原因句与在跑回合）。"""
    assert_probe_ok(pipeline, "flow")
