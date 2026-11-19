"""T045 战前门禁：桌面端前端第 11 片「七端岗位一组的『改绑定…』『恢复缺省…』入口与表单」（B 片）的黑盒基准测试
（合同 t045-desktop-web-hub-bind-entry.v2，基线 5ac97d851a586be26fff13c518910c091834542e；v2 与 v1 的前端断言面相同，
T024 的「角色页禁用数 6→11」放宽由执行端在候选里做，本文件不断言 t024 的文本）。

被测对象是 ``desktop/web/`` 前端的「七端岗位」一组写入口（A 片 T044 已把 useWriteFlow、确认框、
hubChangeLines 与桩的岗位情景接好；本片只做入口与表单）：

- ``src/pages/readonly1/roles-logic.ts``：新增导出 ``hubFallbackCandidates(profiles, allowedAdapters,
  mainProfileId)``——主选 profile 查到的 adapter 是 'quizs' 时返回 ``allowedProfiles(profiles, 允许名单
  去掉 'quizs')``，否则（非 quizs、查不到、adapter 非字符串、名单为空）返回空数组；三个既有导出
  （hubPostName/allowedProfiles/normalizeHubPost）一字不动，该文件仍只 ``import type``。
- ``src/writes/useLivePreview.ts``：``LivePreview`` 只加 ``hubChanges: HubChange[]`` 与
  ``runningTurns: string[]`` 两个字段（fromReply 映射、失败分支字面量补空数组）；开头两行注释与
  ``const DEBOUNCE_MS = 300;`` 一字不动，防抖与序号丢弃逻辑不动。
- ``src/writes/HubBindForm.tsx``（新）+ ``src/writes/hub-bind-form.css``（新）：表单（主选/替补两个 Select、
  底部 useLivePreview 实时预览：命令 + 本岗位前后对比四行（复用 A 片 hubChangeLines，不许抄第二份）+
  warnings + running_turns + 报错原文）与两个入口组件 HubBindAction/HubUnsetAction；两个禁用原因句常量
  逐字在位；按钮 textContent 恰为「改绑定…」「恢复缺省…」（U+2026），按钮里不放岗位名，不加 aria-label。
- ``src/pages/readonly1/roles-HubPosts.tsx``：加第七列「操作」与 props ``profiles``/``reload``；组内一个
  ``useWriteFlow(reload)``；读成功分支渲染 ``<WriteFlow flow={flow} />``；读失败分支照旧零按钮；T038 S10
  的静态形状（title/aria-label/rowHeight/rl-hub/hubPostName/data-post，不出现 data-role）一个不少。
- ``src/pages/readonly1/roles-RolesView.tsx``：``<HubPosts hub={data.hub} profiles={data.profiles.profiles}
  reload={reload} />``（位置不动）。
- 包内测试两处照新行为改：page-hub.test.tsx 列头十列（T047 三列插在「替补」与「操作」之间，末尾仍是「操作」）并补操作列用例；page-app.test.tsx
  角色页禁用数 6→11；两个 describe 标题（「七端岗位（桩模式渲染 #/roles）」「写入口个数（过渡）」）一字不动。
- 执行端两个新测试文件：roles-hub-candidates.test.ts（hubFallbackCandidates 边界）与
  writes-hub-bind.test.tsx（入口与表单的组件测试）。

基线（5ac97d85）上 hubFallbackCandidates、两个字段、HubBindForm.tsx、操作列与 11 个禁用按钮都不存在，
所以本文件的失败落在「记号不在」「文件不存在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，
所有仓库文件的读取都发生在用例函数里；流水线（npm、Vitest、探针）放在 ``pipeline`` 会话级夹具里（全量
pytest 默认跳过，点名运行本文件才跑；候选里还没有本片的文件时夹具不调 npm——照 T024/T040/T041/T043/
T044 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：roles-logic 的新纯函数与既有导出（S01）；
  useLivePreview 的两个字段与钉住项（S02）；HubBindForm 新文件（S03）；hub-bind-form.css 的令牌规矩（S04）；
  HubPosts 的操作列与 T038 形状（S05）；RolesView 的 prop（S06）；两处包内测试照新行为改（S07）；执行端
  两个新测试文件在位且要点齐备（S08）；共享面——mock 仍 14 份 JSON、顶层页面仍 9 个、依赖与禁改文件字节
  冻结（S09）；新源码的规矩（S10）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、npm test
  全绿；两份探针逐份写成 ``gate-probe/probe-<uid>-t045-<键>.test.tsx``，各用 ``npm test -- gate-probe/
  <文件名>`` 跑，``finally`` 里删除。探针用 ``setLiveClientForTests`` 注入假服务（照
  tests/writes-live-flow.test.tsx 的写法），不 mock 被测组件；每份自带全部辅助函数，不跨文件共享作用域。
  - unit：hubFallbackCandidates 的边界、allowedProfiles/hubPostName 既有行为、useLivePreview 两个新字段
    （真实模式注入假服务）。
  - page：桩模式挂 App——操作列与两个按钮的 textContent、planner 无候选禁用、缺省行恢复缺省…禁用、
    角色页禁用数 11、对话框关着不渲染候选（step-low 不出现在七端岗位组）；表单预填与替补联动、底部命令
    与前后对比四行；真实模式（注入假服务）确认发岗位路由（带/不带 fallback）与 reload。

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

ROLES_LOGIC_REL = f"{PAGES_RO}/roles-logic.ts"
HUBPOSTS_REL = f"{PAGES_RO}/roles-HubPosts.tsx"
ROLESVIEW_REL = f"{PAGES_RO}/roles-RolesView.tsx"
ROLES_STYLES_REL = f"{PAGES_RO}/roles-styles.css"
LIVEPREVIEW_REL = f"{WRITES_REL}/useLivePreview.ts"
HUBBINDFORM_REL = f"{WRITES_REL}/HubBindForm.tsx"
HUBBIND_CSS_REL = f"{WRITES_REL}/hub-bind-form.css"
HUBLINES_REL = f"{WRITES_REL}/hubChangeLines.ts"
MOCK_HUB_ROLES_REL = f"{SRC_REL}/mock/hub-roles.ts"
MOCK_PROFILES_REL = f"{SRC_REL}/mock/profiles.json"

PAGE_HUB_TEST_REL = f"{TESTS_REL}/page-hub.test.tsx"
PAGE_APP_TEST_REL = f"{TESTS_REL}/page-app.test.tsx"
EXEC_LOGIC_TEST_REL = f"{TESTS_REL}/roles-hub-candidates.test.ts"
EXEC_COMP_TEST_REL = f"{TESTS_REL}/writes-hub-bind.test.tsx"

# 基线名单：src/mock 恰 14 份 JSON、src/pages 顶层恰 9 个 *Page.tsx（不新增 JSON、不新增页面文件）
BASELINE_MOCK_JSON_COUNT = 14
BASELINE_PAGE_COUNT = 9

# 禁改文件的基线冻结（行尾归一 LF 后的字节数与 sha256；合同 forbidden_paths：依赖、roles-styles.css、
# mock/profiles.json、hubChangeLines.ts 一个字节都不许动——桩的禁用数 11 与探针的期望值都依赖这些夹具；
# mock/hub-roles.ts 由 T047 放开字节冻结：桩的每行加了 turn、last_turn，改成结构钉住，见 _mock_stub_problems）
BASELINE_DIGESTS = {
    f"{WEB_REL}/package.json": (820, "094d3622e54097e0f50f0ab2a71a5caa22491dba9d3ac6ef83047426f8c57f5a"),
    f"{WEB_REL}/package-lock.json": (108793, "1bc4e1fbfeb02a17280d0de1d98a5f3b2721fa91229c271c66d590d059d82d28"),
    ROLES_STYLES_REL: (4282, "a81ce331e93a3ef9b06f44c76ee3c72d75c0a52f965169437bf9e9f8bd338d06"),
    MOCK_PROFILES_REL: (359, "594431a2f72bd63755c5bef2af9af126b1679917b6be3a66e8e0064907197297"),
    HUBLINES_REL: (2866, "8828b71b4451e9c8e3338b7e92534e4094fc3bbc79e4e45d902d2e99dfb90ba3"),
}

# roles-logic.ts 既有的三个导出（合同兼容性：签名与行为不变，只新增 hubFallbackCandidates）
OLD_LOGIC_EXPORTS = ("hubPostName", "allowedProfiles", "normalizeHubPost")

# useLivePreview.ts 开头两行注释（T040 S04 钉住第 2 行；合同：一字不动）
PREVIEW_LINE_1 = "// 表单底部的实时内核预览（合同第三节）：表单合法才在 300ms 防抖后调 preview；迟到的回应按序号丢弃。"
PREVIEW_LINE_2 = "// 夹具模式下读演示数据，真实模式下走服务的预览。"
# LivePreview 既有的五个字段（合同：只加两个，不改既有字段语义）
OLD_PREVIEW_FIELDS = ("key", "ok", "command", "warnings", "error")

# 两个按钮的 textContent（合同：恰为这两个字，U+2026 的省略号；按钮里不放岗位名）
BUTTON_BIND = "改绑定…"
BUTTON_UNSET = "恢复缺省…"
# 两个禁用原因句（合同 Behavior contract 逐字）
REASON_NO_CANDIDATES = "没有能用在这个岗位的 profile：先在「CLI 运行时」页登记运行时，再新建 profile"
REASON_UNSET_DEFAULT = "这个岗位现在用的是内核缺省，没有要恢复的配置"

# 七端岗位的列头：前六个一字不改，第七列是「操作」
HUB_HEADERS = ("岗位", "运行时", "模型", "思考档位", "来源", "替补", "操作")

# 桩下角色页禁用按钮数（page-app 的口径）：方案条的「切换…」1 个 +
# planner 的「改绑定…」1 个 + 四个缺省行的「恢复缺省…」4 个 = 6
ROLES_PAGE_DISABLED = 6

# 执行端两个新测试文件的最小覆盖记号（合同第 8 步）
EXECUTOR_TEST_TOKENS = {
    "roles-hub-candidates.test.ts": (
        "hubFallbackCandidates", "allowedProfiles", "hubPostName", "quizs", "不设替补",
    ),
    "writes-hub-bind.test.tsx": (
        "setLiveClientForTests", "hub.set", "hub.unset", "/api/v1/hub/roles/", "主绑定", "不设替补",
        BUTTON_BIND, BUTTON_UNSET, "reload",
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

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T024/T041/T043/T044 门禁），用完就停下并在断言里写明。
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 150}

ASSUMPTIONS = (
    "「确认…」先关表单再 start 的次序按行为断言（点表单的 [确认…] 后表单对话框关上、写确认框开上），"
    "不静态钉源码里的调用次序",
    "探针断言底部命令用「去掉 --dry-run/--json 后的 argv 空格连接」的子串（不钉 bash scripts/dispatch-pi.sh "
    "前缀：表单照 RuntimeForm 用 dispatchCommand 渲染，前缀在不在都算过）",
    "禁改文件按字节冻结（行尾归一 LF）：依赖两份、roles-styles.css、mock/profiles.json、"
    "hubChangeLines.ts——都在合同 forbidden_paths 里，桩的禁用数 11 与探针期望值依赖这些夹具；"
    "mock/hub-roles.ts 由 T047 放开字节冻结：桩的每行加了 turn、last_turn，改成结构钉住"
    "（六个岗位名与行序、十个绑定字段的值逐字不变，见 _mock_stub_problems）",
    "page-hub.test.tsx 的「补一条用例」与 page-app.test.tsx 的标题改动按记号断言（列头十列数组、按钮两个"
    "字、planner 禁用、禁用数 11、两个 describe 标题逐字），用例数与写法不设上限；运行时行为由 page 探针"
    "独立钉住",
    "执行端测试文件的覆盖记号是最低要求（有这些记号才说明测到了合同点名的那几件事）；运行时行为由两份"
    "探针独立钉住",
    "S05 对「WriteFlow 只在读成功分支」按记号次序断言（<WriteFlow 出现在 hub.ok && hub.data 之后）；失败"
    "分支零按钮由 page-hub.test.tsx 的既有断言（记号）与 R01 里 T038/T045 探针共同背书",
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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043/T044 的同一口径）：行注释与块注释在同一次从左往右的扫描里认。
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

def test_s01_roles_logic_fallback_candidates():
    """S01 / D01、兼容性、写法钉死第 1 条：roles-logic.ts 新导出 hubFallbackCandidates(profiles,
    allowedAdapters, mainProfileId)——函数体里用 allowedProfiles( 与 'quizs' 字面量比较；三个既有导出
    一字不动；该文件仍只 import type。"""
    need_file(ROLES_LOGIC_REL)
    text = read_rel(ROLES_LOGIC_REL)
    code = strip_ts_comments(text)
    problems = []
    signature = re.search(r"export function hubFallbackCandidates\(([^)]*)\)", code, re.S)
    if not signature:
        problems.append("roles-logic.ts 应导出 export function hubFallbackCandidates(（写法钉死第 1 条）")
    else:
        params = signature.group(1)
        for param in ("profiles", "allowedAdapters", "mainProfileId"):
            if param not in params:
                problems.append(f"hubFallbackCandidates 的签名应有参数 {param}")
    fn = _block(code, "export function hubFallbackCandidates")
    if fn:
        if "allowedProfiles(" not in fn:
            problems.append("hubFallbackCandidates 应复用 allowedProfiles(（不抄第二份筛选逻辑）")
        if "'quizs'" not in fn:
            problems.append("hubFallbackCandidates 应有 'quizs' 的字面量比较（写法钉死第 1 条）")
    else:
        problems.append("找不到 hubFallbackCandidates 的函数体")
    for name in OLD_LOGIC_EXPORTS:
        if not re.search(rf"export function {name}\(", code):
            problems.append(f"既有导出 {name} 应保留（签名与行为不变）")
    imports = re.findall(r"import[^;]*?from\s*['\"][^'\"]+['\"]", text)
    for stmt in imports:
        if not stmt.lstrip().startswith("import type"):
            problems.append(f"roles-logic.ts 只许 import type（T038 S07）：{stmt.strip()[:60]}")
    fail_if(problems, "roles-logic.ts 的 hubFallbackCandidates（S01）")


def test_s02_live_preview_fields():
    """S02 / D02、写法钉死第 2 条：useLivePreview.ts 只加两个字段——LivePreview 接口里
    hubChanges: HubChange[] 与 runningTurns: string[]（各占一行、行首是字段名）；import 行扩成含
    type HubChange；fromReply 写 hubChanges: data?.hub_changes ?? [] 与 runningTurns: data?.
    running_turns ?? []；useEffect 失败分支的字面量补两个空数组；开头两行注释与 DEBOUNCE_MS = 300
    一字不动，防抖与序号丢弃逻辑不动。"""
    need_file(LIVEPREVIEW_REL)
    text = read_rel(LIVEPREVIEW_REL)
    code = strip_ts_comments(text)
    problems = []
    lines = text.split("\n")
    if len(lines) < 2 or lines[0] != PREVIEW_LINE_1:
        problems.append("useLivePreview.ts 第 1 行注释应一字不动（T040/合同兼容性）")
    if len(lines) < 3 or lines[1] != PREVIEW_LINE_2:
        problems.append("useLivePreview.ts 第 2 行注释应一字不动（T040 S04 钉住）")
    if "const DEBOUNCE_MS = 300;" not in code:
        problems.append("const DEBOUNCE_MS = 300; 应在位（T024 S14/T040 S04）")
    api_imports = re.findall(r"import[^;]*?from\s*['\"]\.\./api['\"]", text, re.S)
    if not api_imports or not any("type HubChange" in stmt for stmt in api_imports):
        problems.append("import 那行应扩成含 type HubChange（写法钉死第 2 条）")
    interface = _block(code, "export interface LivePreview")
    if not interface:
        problems.append("useLivePreview.ts 应保留 export interface LivePreview")
    else:
        for field, decl in (("hubChanges", r"^\s*hubChanges\s*:\s*HubChange\[\]\s*;?$"),
                            ("runningTurns", r"^\s*runningTurns\s*:\s*string\[\]\s*;?$")):
            if not re.search(decl, interface, re.M):
                problems.append(f"LivePreview 应加字段 {field}（各占一行、行首是字段名；不是可选）")
        for field in OLD_PREVIEW_FIELDS:
            if not re.search(rf"^\s*{field}\s*:", interface, re.M):
                problems.append(f"LivePreview 既有字段 {field} 应保留")
    from_reply = _block(code, "function fromReply")
    if not from_reply:
        problems.append("useLivePreview.ts 应保留 fromReply")
    else:
        if "hubChanges: data?.hub_changes ?? []" not in from_reply:
            problems.append("fromReply 应写 hubChanges: data?.hub_changes ?? []（缺键按空数组）")
        if "runningTurns: data?.running_turns ?? []" not in from_reply:
            problems.append("fromReply 应写 runningTurns: data?.running_turns ?? []（缺键按空数组）")
    effect = _block(code, "useEffect(() => {")
    if not effect:
        problems.append("useLivePreview.ts 应保留 useEffect（防抖与序号逻辑）")
    else:
        fail_branch = re.search(r"setResult\(\{[^}]*预览失败：服务没有回应", effect, re.S)
        if not fail_branch:
            problems.append("useEffect 的失败分支字面量应在位")
        else:
            literal = effect[fail_branch.start():effect.find("}", fail_branch.start())]
            if "hubChanges: []" not in literal or "runningTurns: []" not in literal:
                problems.append("useEffect 失败分支的字面量应补 hubChanges: [] 与 runningTurns: []（写法钉死第 2 条）")
    for token in ("seqRef.current += 1", "setTimeout(", "clearTimeout(timer)", "my === seqRef.current"):
        if token not in code:
            problems.append(f"防抖与序号丢弃逻辑应原样保留（看不到 {token}）")
    fail_if(problems, "useLivePreview.ts 的两个字段（S02）")


def test_s03_hub_bind_form_file():
    """S03 / D03、D04、写法钉死第 3 条：新文件 src/writes/HubBindForm.tsx——从 ../api 只 import type；
    运行时引 hubChangeLines（复用 A 片，不抄第二份）；import './hub-bind-form.css' 放在组件 import
    之后；导出 HubBindAction 与 HubUnsetAction 两个入口组件与两个禁用原因句常量（逐字）；表单的
    Select 标签「主绑定」「替补」与空值选项「不设替补」；useLivePreview('hub.set')；两个 action；
    <WriteFlow flow={flow} /> 放在表单里；按钮文字恰为「改绑定…」「恢复缺省…」；不加 aria-label；
    不跨层引 src/pages；不出现 step-low。"""
    need_file(HUBBINDFORM_REL)
    text = read_rel(HUBBINDFORM_REL)
    code = strip_ts_comments(text)
    problems = []
    for stmt in re.findall(r"import[^;]*?from\s*['\"]\.\./api['\"]", text, re.S):
        if not stmt.lstrip().startswith("import type"):
            problems.append(f"HubBindForm.tsx 从 ../api 只许 import type：{stmt.strip()[:60]}")
    hub_import = re.search(r"import\s*\{[^}]*\}\s*from\s*['\"]\./hubChangeLines['\"]", text, re.S)
    if not hub_import or "hubChangeLines" not in hub_import.group(0):
        problems.append("HubBindForm.tsx 应运行时 import { hubChangeLines } from './hubChangeLines'（复用 A 片）")
    css_pos = text.find("import './hub-bind-form.css';")
    if css_pos < 0:
        problems.append("HubBindForm.tsx 应 import './hub-bind-form.css'（样式表放组件 import 之后）")
    else:
        for stmt in re.findall(r"import[^;]*?from\s*['\"]\./[^'\"]+['\"]", text, re.S):
            if text.find(stmt) > css_pos:
                problems.append("import './hub-bind-form.css' 应放在组件 import 之后")
                break
    for token in ("export function HubBindAction(", "export function HubUnsetAction("):
        if token not in code:
            problems.append(f"HubBindForm.tsx 应导出 {token[:-1]})")
    if REASON_NO_CANDIDATES not in text:
        problems.append("改绑定没有候选的原因句应逐字在位（合同 Behavior contract）")
    if REASON_UNSET_DEFAULT not in text:
        problems.append("恢复缺省不可用的原因句应逐字在位（合同 Behavior contract）")
    for token in (BUTTON_BIND, BUTTON_UNSET):
        if token not in code:
            problems.append(f"按钮文字应恰为「{token}」（U+2026）")
    if "aria-label" in text:
        problems.append("本片不给按钮加 aria-label（DisabledAction 不接受该 prop）")
    if "改绑定：" not in code:
        problems.append("对话框标题应由本文件拼：改绑定：<岗位中文名>（写法钉死第 3 条的标题）")
    for token in ("主绑定", "替补", "不设替补"):
        if token not in code:
            problems.append(f"表单的 Select 标签/空值选项应含「{token}」")
    if "useLivePreview(" not in code:
        problems.append("表单底部应用 useLivePreview('hub.set', args, enabled)（照 RuntimeForm 的写法）")
    if "'hub.set'" not in code:
        problems.append("表单确认应 start({ action: 'hub.set', args })")
    if "'hub.unset'" not in code:
        problems.append("恢复缺省…应 start({ action: 'hub.unset', args: { post } })")
    if "<WriteFlow flow={flow} />" not in code:
        problems.append("表单里应放 <WriteFlow flow={flow} />")
    for token in ("current", "result.ok", "onClose"):
        if token not in code:
            problems.append(f"[确认…] 的门控/次序应能看到 {token}（照 RuntimeForm 的写法）")
    if re.search(r"from\s*['\"]\.\./pages|from\s*['\"]\./roles-", text):
        problems.append("src/writes 不跨层引 src/pages（岗位中文名由入口文件当 prop 传进来）")
    if "step-low" in code:
        problems.append("HubBindForm.tsx 不应写死 step-low（页面文字不许出现）")
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"HubBindForm.tsx 不应出现 {bad}")
    if _HEX_COLOR.search(code) or any(fn in code for fn in _COLOR_FUNCS):
        problems.append("HubBindForm.tsx 不应写死颜色")
    fail_if(problems, "HubBindForm.tsx 新文件（S03）")


def test_s04_hub_bind_form_css():
    """S04 / D10、写法钉死第 6 条：新文件 src/writes/hub-bind-form.css——只用 --tt-* 令牌、不声明令牌、
    不写死颜色；类名一律 hb- 前缀；px 字面量除 0 与 1px 外要带出处注释。"""
    need_file(HUBBIND_CSS_REL)
    text = read_rel(HUBBIND_CSS_REL)
    code = strip_ts_comments(text)
    problems = []
    selectors = re.findall(r"([^{}]+)\{", code)
    if not selectors:
        problems.append("hub-bind-form.css 应有规则")
    for sel in selectors:
        for cls in re.findall(r"\.[A-Za-z][\w-]*", sel):
            if not cls.startswith(".hb-"):
                problems.append(f"类名应一律 hb- 前缀（写法钉死第 6 条）：{cls}")
    if re.search(r"^\s*--tt-[\w-]+\s*:", code, re.M):
        problems.append("hub-bind-form.css 不应声明令牌（只用 src/styles/tokens.css 里已定义的）")
    if "--tt-" not in code:
        problems.append("hub-bind-form.css 应使用 --tt-* 令牌")
    if _HEX_COLOR.search(code) or any(fn in code for fn in _COLOR_FUNCS):
        problems.append("hub-bind-form.css 不应写死颜色（只用 --tt-* 令牌）")
    for m in re.finditer(r"(\d+(?:\.\d+)?)px", code):
        value = m.group(1)
        if value in ("0", "1"):
            continue
        line_start = code.rfind("\n", 0, m.start()) + 1
        line_end = code.find("\n", m.end())
        line = code[line_start:line_end if line_end >= 0 else len(code)]
        if not re.search(r"出处|照 .*的写法|与 .*同口径", line):
            problems.append(f"px 字面量 {value}px 所在行要带出处注释：{line.strip()[:60]}")
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"hub-bind-form.css 不应出现 {bad}")
    fail_if(problems, "hub-bind-form.css 新文件（S04）")


def test_s05_hub_posts_operation_column():
    """S05 / D05、D11、写法钉死第 4 条：roles-HubPosts.tsx 加第七列「操作」（key 与 header 都写
    「操作」）与 props profiles/reload（profiles 缺省空数组）；组内一个 useWriteFlow(reload)；
    「操作」格放 HubBindAction/HubUnsetAction（从 src/writes 引）；<WriteFlow flow={flow} /> 只在
    读成功分支；T038 S10 的静态形状一个不少（title/aria-label/rowHeight/rl-hub/hubPostName/
    data-post），不出现 data-role。"""
    need_file(HUBPOSTS_REL)
    text = read_rel(HUBPOSTS_REL)
    code = strip_ts_comments(text)
    problems = []
    if "{ key: '操作', header: '操作' }" not in code:
        problems.append("第七列的 key 与 header 都应写「操作」（照 profile 表的写法）")
    for header in HUB_HEADERS[:-1]:
        if f"header: '{header}'" not in code:
            problems.append(f"前六个列头一字不改（看不到 {header}）")
    for token in ('Section title="七端岗位"', 'aria-label="七端岗位"', "rowHeight={40}",
                  "rl-table rl-hub", "hubPostName", "rowAttrs", "'data-post'"):
        if token not in code:
            problems.append(f"T038 S10 的静态形状应保留（看不到 {token}）")
    if "data-role" in code:
        problems.append("七端岗位一组不出现 data-role（行属性用 data-post）")
    props = _block(code, "export interface HubPostsProps")
    if not props:
        problems.append("roles-HubPosts.tsx 应保留 HubPostsProps")
    else:
        for prop in ("hub", "profiles", "reload"):
            if not re.search(rf"^\s*{prop}\s*\??\s*:", props, re.M):
                problems.append(f"HubPostsProps 应有 {prop}（profiles 与 reload 可空）")
    if "useWriteFlow(" not in code:
        problems.append("组内应有一个 useWriteFlow(reload)（照 roles-ProfilesTable 的写法）")
    if not re.search(r"import\s*\{[^}]*HubBindAction[^}]*\}\s*from\s*['\"]\.\./\.\./writes/HubBindForm['\"]", text, re.S) \
            and "HubBindAction" not in code:
        problems.append("「操作」格应放 HubBindAction（从 src/writes 引）")
    if "HubBindAction" not in code or "HubUnsetAction" not in code:
        problems.append("「操作」格应放 HubBindAction 与 HubUnsetAction（两个组件都在 src/writes 里）")
    if not re.search(r"from\s*['\"]\.\./\.\./writes/HubBindForm['\"]", text):
        problems.append("入口组件应从 '../../writes/HubBindForm' 引（入口文件不写逐字句子）")
    ok_branch = code.find("hub.ok && hub.data")
    wf_pos = code.find("<WriteFlow flow={flow} />")
    if wf_pos < 0:
        problems.append("读成功的分支里应渲染 <WriteFlow flow={flow} />")
    elif ok_branch >= 0 and wf_pos < ok_branch:
        problems.append("<WriteFlow flow={flow} /> 应只在读成功的分支里（不在失败分支）")
    if re.search(r"export function HubBindAction|export function HubUnsetAction", code):
        problems.append("入口组件应在 src/writes 里，入口文件只放按钮")
    if REASON_NO_CANDIDATES in text or REASON_UNSET_DEFAULT in text:
        problems.append("禁用原因句应在 src/writes 里，入口文件不写逐字句子")
    if "profiles=[]" not in code.replace(" ", ""):
        problems.append("profiles 缺省应是空数组（合同兼容性：profiles 缺省空数组）")
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"roles-HubPosts.tsx 不应出现 {bad}")
    if "step-low" in code:
        problems.append("roles-HubPosts.tsx 不应写死 step-low")
    fail_if(problems, "roles-HubPosts.tsx 的操作列（S05）")


def test_s06_rolesview_props():
    """S06 / 写法钉死第 5 条：roles-RolesView.tsx 改成 <HubPosts hub={data.hub} profiles=
    {data.profiles.profiles} reload={reload} />（位置不动：角色卡网格之后、ProfilesTable 之前）；
    从 '../../api' 只 import type。"""
    need_file(ROLESVIEW_REL)
    text = read_rel(ROLESVIEW_REL)
    code = strip_ts_comments(text)
    problems = []
    # 站主门禁准备（2026-11-17）：T048 在 reload 之后追加 live={live}，只钉开头这三个 prop，后面容许追加
    if not re.search(
        r"<HubPosts\s+hub=\{data\.hub\}\s+profiles=\{data\.profiles\.profiles\}\s+reload=\{reload\}(?:\s+\w+=\{[^{}]*\})*\s*/>",
        code,
    ):
        problems.append("RolesView 应写 <HubPosts hub={data.hub} profiles={data.profiles.profiles} reload={reload} … />（写法钉死第 5 条，之后可以追加 prop）")
    grid_pos = code.find('className="rl-grid tt-grid-2"')
    hub_pos = code.find("<HubPosts ")
    prof_pos = code.find("<ProfilesTable ")
    if not (0 <= grid_pos < hub_pos < prof_pos):
        problems.append("HubPosts 的位置不动：角色卡网格之后、ProfilesTable 之前")
    for stmt in re.findall(r"import[^;]*?from\s*['\"]\.\./\.\./api['\"]", text, re.S):
        if not stmt.lstrip().startswith("import type"):
            problems.append(f"roles-RolesView.tsx 从 '../../api' 只许 import type：{stmt.strip()[:60]}")
    fail_if(problems, "roles-RolesView.tsx 的 prop（S06）")


def test_s07_package_tests_updated():
    """S07 / D07：两处包内测试照新行为改——page-hub.test.tsx 列头十列（T047 三列插在「替补」与「操作」之间，末尾仍是「操作」）、
    it 标题跟着改、补操作列用例（两个按钮的 textContent、planner 禁用、contract/exec 可点其余禁用）；
    page-app.test.tsx 角色页禁用数 6→11、it 标题跟着改；两个 describe 标题一字不动；
    读失败分支零按钮的既有断言照旧；都不许 skip/only/todo。"""
    problems = []
    hub_text = read_rel(need_file(PAGE_HUB_TEST_REL))
    # 站主门禁准备（2026-11-17）：T048 在「最近一回合」与「操作」之间加「证书」，十列、十一列都认
    if not any(line in hub_text for line in (
            "['岗位', '运行时', '模型', '思考档位', '来源', '替补', '时限与工具', '预算', '最近一回合', '操作']",
            "['岗位', '运行时', '模型', '思考档位', '来源', '替补', '时限与工具', '预算', '最近一回合', '证书', '操作']")):
        problems.append("page-hub.test.tsx 的列头断言应改成十列（T047 三列插在「替补」与「操作」之间，末尾仍是「操作」；"
                        "T048 起十一列，「证书」在「最近一回合」与「操作」之间）")
    if "describe('七端岗位（桩模式渲染 #/roles）'" not in hub_text:
        problems.append("page-hub.test.tsx 的 describe 标题「七端岗位（桩模式渲染 #/roles）」一字不动")
    for token in (BUTTON_BIND, BUTTON_UNSET, "planner"):
        if token not in hub_text:
            problems.append(f"page-hub.test.tsx 应补操作列用例（应含记号「{token}」）")
    if "失败时不出重试钮" not in hub_text:
        problems.append("page-hub.test.tsx 读失败分支零按钮的既有断言应照旧（「失败时不出重试钮」）")
    if "失败时这一组不渲染表格行" not in hub_text:
        problems.append("page-hub.test.tsx 失败分支不渲染表格行的既有断言应照旧")
    problems.extend("page-hub.test.tsx: " + p for p in _no_skip_marks(hub_text))
    app_text = read_rel(need_file(PAGE_APP_TEST_REL))
    if "describe('写入口个数（过渡）'" not in app_text:
        problems.append("page-app.test.tsx 的 describe 标题「写入口个数（过渡）」一字不动（T037 S06 要认它）")
    roles_line = re.search(r"expect\(disabled\(\)\.length, '角色页'\)\.toBe\((\d+)\)", app_text)
    if not roles_line:
        problems.append("page-app.test.tsx 的角色页禁用数断言应在位")
    elif roles_line.group(1) != str(ROLES_PAGE_DISABLED):
        problems.append(f"page-app.test.tsx 的角色页禁用数应是 {ROLES_PAGE_DISABLED}（桩下 2+1+4）")
    if not re.search(r"it\('角色页 \d+（[^']*）?、运行时页 0、总览 0'", app_text) and "'角色页 11'" not in app_text:
        if "'角色页 11'" not in app_text:
            problems.append("page-app.test.tsx 的 it 标题应跟着改成 11（照新行为改标题）")
    for token, pat in (("运行时页 0", r"toBe\(0\)"), ("总览 0", r"toBe\(0\)")):
        if not re.search(pat, app_text):
            problems.append(f"page-app.test.tsx 的 {token} 断言应照旧")
    problems.extend("page-app.test.tsx: " + p for p in _no_skip_marks(app_text))
    fail_if(problems, "两处包内测试照新行为改（S07）")


def test_s08_executor_tests():
    """S08 / D08：两个新测试文件在位且覆盖记号齐备（roles-hub-candidates.test.ts 的纯函数边界与
    writes-hub-bind.test.tsx 的组件测试），都不许 skip/only/todo。"""
    problems = []
    for rel, tokens in (
        (EXEC_LOGIC_TEST_REL, EXECUTOR_TEST_TOKENS["roles-hub-candidates.test.ts"]),
        (EXEC_COMP_TEST_REL, EXECUTOR_TEST_TOKENS["writes-hub-bind.test.tsx"]),
    ):
        need_file(rel)
        text = read_rel(rel)
        for token in tokens:
            if token not in text:
                problems.append(f"{rel} 应含记号「{token}」（合同第 8 步点名的覆盖点）")
        problems.extend(f"{rel}: {p}" for p in _no_skip_marks(text))
    fail_if(problems, "执行端两个新测试文件（S08）")


# ---------------------------------------------------------------------------
# T047 门禁准备：桩的每行加了 turn、last_turn，mock/hub-roles.ts 的字节冻结改成结构钉住
# （六个岗位名与行序不变、十个绑定字段的值逐字不变、仍是普通 TS 字面量）。期望值对照
# tests/test_gate_t038_baseline.py 的 SIX_ROWS_TS；只比字面量的值（去空白与尾逗号），
# 不按当前文件重算字节再冻结。
# ---------------------------------------------------------------------------
BINDING_FIELDS = ("post", "source", "allowed_adapters", "adapter", "provider", "model",
                  "thinking", "profile", "runtime", "fallback")


def _WS(text):
    """TS 字面量归一：去掉所有空白与尾逗号，只比值不后排版。"""
    return re.sub(r",([}\]])", r"\1", re.sub(r"\s+", "", text))


def _skip_string(text, i):
    """从单引号处跳过一段字符串，返回结束后的下标。"""
    j = i + 1
    while j < len(text):
        if text[j] == "\\":
            j += 2
            continue
        if text[j] == "'":
            return j + 1
        j += 1
    return j


def _stub_rows(text, start=0):
    """取对象数组里每个对象的原文：按 post: 'name' 的出现顺序，往前找最近的 '{'，
    再按花括号配平取到对应的 '}'。"""
    rows = []
    for match in re.finditer(r"post:\s*'([a-z]+)'", text[start:]):
        at = start + match.start()
        open_at = text.rfind("{", start, at)
        if open_at < 0:
            continue
        depth = 0
        i = open_at
        while i < len(text):
            ch = text[i]
            if ch == "'":
                i = _skip_string(text, i)
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        rows.append((match.group(1), text[open_at:i + 1]))
    return rows


def _binding_value(row_text, field):
    """取一行里某个顶层字段的原文值（只认该行的直接成员，嵌套里的同名键不算）；没有就 None。"""
    body = row_text[1:-1] if row_text.startswith("{") else row_text
    depth = 0
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if ch == "'":
            i = _skip_string(body, i)
            continue
        if ch in "{[":
            depth += 1
            i += 1
            continue
        if ch in "}]":
            depth -= 1
            i += 1
            continue
        if depth == 0:
            match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*:", body[i:])
            if match:
                if match.group(1) == field:
                    j = i + match.end()
                    k = j
                    inner = 0
                    while k < n:
                        c2 = body[k]
                        if c2 == "'":
                            k = _skip_string(body, k)
                            continue
                        if c2 in "{[":
                            inner += 1
                        elif c2 in "}]":
                            if inner == 0:
                                break
                            inner -= 1
                        elif c2 == "," and inner == 0:
                            break
                        k += 1
                    return body[j:k]
                i += 1
                continue
        i += 1
    return None


def _six_rows_ts():
    """tests/test_gate_t038_baseline.py 的 SIX_ROWS_TS 原文（桩的六行绑定字段的期望值）。"""
    text = read_rel("tests/test_gate_t038_baseline.py")
    match = re.search(r'SIX_ROWS_TS = """(.*?)"""', text, re.S)
    assert match, "test_gate_t038_baseline.py 里应有 SIX_ROWS_TS"
    return match.group(1)


def _mock_stub_problems():
    """桩的结构钉住：六个岗位名与行序不变、十个绑定字段的值逐字不变、仍是普通 TS 字面量。"""
    problems = []
    actual_text = read_rel(need_file(MOCK_HUB_ROLES_REL))
    expected_rows = _stub_rows(_six_rows_ts(), 0)
    start = actual_text.find("posts:")
    if start < 0:
        problems.append("桩里应有 posts: [ … ] 数组")
        return problems
    actual_rows = _stub_rows(actual_text, start)
    if [name for name, _ in actual_rows] != [name for name, _ in expected_rows]:
        problems.append("桩的六个岗位名与行序应照旧（coordinator、planner、contract、gate、audit、exec）")
        return problems
    for (name, row), (_, want_row) in zip(actual_rows, expected_rows):
        for field in BINDING_FIELDS:
            got = _binding_value(row, field)
            want = _binding_value(want_row, field)
            if got is None or want is None or _WS(got) != _WS(want):
                problems.append(f"桩 {name} 行的 {field} 应逐字不变（期望 {_WS(want or '')}）")
    if not re.search(r"export const HUB_ROLES_POSTS: HubRolesData = \{", actual_text):
        problems.append("桩仍应是普通 TS 字面量：export const HUB_ROLES_POSTS: HubRolesData = { posts: [ … ] }")
    return problems


def test_s09_shared_surfaces():
    """S09 / D09、兼容性：共享面——src/mock 仍恰 14 份 JSON、src/pages 顶层仍 9 个 *Page.tsx；
    依赖与禁改文件字节冻结（package.json/package-lock.json、roles-styles.css、mock/profiles.json、
    hubChangeLines.ts——桩的禁用数 11 与探针期望值都依赖这些夹具）；mock/hub-roles.ts 由 T047 放开字节
    冻结，改成结构钉住：六个岗位名与行序不变、十个绑定字段的值逐字不变、仍是普通 TS 字面量。"""
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
    problems.extend(_mock_stub_problems())
    fail_if(problems, "共享面与禁改面（S09）")


def test_s10_new_source_rules():
    """S10 / D10：新代码守既有规矩——HubBindForm.tsx 与 hub-bind-form.css 不出现网络词、危险写入、
    matchMedia 一类、role=status、「（UTC 」字面量；roles-* 三个文件不出现网络词、T007 禁用词、
    role=status、内联 style；新写的文件不写死颜色、不出现 step-low。"""
    problems = []
    for rel in (HUBBINDFORM_REL, HUBBIND_CSS_REL):
        if not (REPO_ROOT / rel).is_file():
            problems.append(f"{rel} 不存在（基线上还没有实现）")
            continue
        text = read_rel(rel)
        for bad in FORBIDDEN_SOURCE_MARKS:
            if bad in text:
                problems.append(f"{rel} 不应出现 {bad}")
        if _HEX_COLOR.search(strip_ts_comments(text)) or any(fn in text for fn in _COLOR_FUNCS):
            problems.append(f"{rel} 不应写死颜色")
    for rel in (HUBPOSTS_REL, ROLESVIEW_REL, ROLES_LOGIC_REL):
        text = read_rel(need_file(rel))
        for bad in ("XMLHttpRequest", "EventSource", "WebSocket", "dangerouslySetInnerHTML", "innerHTML",
                    "insertAdjacentHTML", "eval(", "new Function", "document.write", "srcdoc", "DOMParser",
                    "matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver",
                    "role=\"status\"", "（UTC ", "style={{"):
            if bad in text:
                problems.append(f"{rel} 不应出现 {bad}")
        if "step-low" in strip_ts_comments(text):
            problems.append(f"{rel} 不应写死 step-low（页面文字不许出现）")
    fail_if(problems, "新源码的规矩（S10）")


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 T044 门禁的写法）
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


def t045_marker_present():
    """候选里是否已有 T045 的标记（HubBindForm.tsx 与 roles-logic 的 hubFallbackCandidates）：
    没有就不起 npm（基线上必然没有）。"""
    form = REPO_ROOT / HUBBINDFORM_REL
    if not form.is_file():
        return False
    logic = REPO_ROOT / ROLES_LOGIC_REL
    try:
        return "hubFallbackCandidates" in _read(logic)
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
    if not t045_marker_present():
        pipe.reason = ("候选里还没有 T045 的标记（HubBindForm.tsx 或 roles-logic 的 hubFallbackCandidates），"
                       "没有东西可测，未调用 npm；候选把纯函数、两个字段与入口接上之后，流水线才会运行"
                       " npm ci、Vitest 与探针")
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
                    name = f"probe-{uid}-t045-{key}.test.tsx"
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

UNIT_PROBE = r'''// T045 门禁 unit 探针：hubFallbackCandidates 的边界、allowedProfiles/hubPostName 的既有行为、
// useLivePreview 的两个新字段（真实模式注入假服务）。不 mock 被测模块。
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Envelope } from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { useLivePreview } from '../src/writes/useLivePreview';
import { allowedProfiles, hubFallbackCandidates, hubPostName } from '../src/pages/readonly1/roles-logic';

const PROFILES: any[] = [
  { id: 'q1', adapter: 'quizs' },
  { id: 'p1', adapter: 'pi' },
  { id: 'q2', adapter: 'quizs' },
  { id: 'p2', adapter: 'pi' },
  { id: 'x1', adapter: 'codex' },
  { id: 'n1', adapter: null },
  { id: 'm1' },
];

describe('hubFallbackCandidates（D01）', () => {
  it('主选是 quizs：候选是允许名单去掉 quizs 的那几个（按输入顺序），不含 quizs、不出允许名单', () => {
    expect(hubFallbackCandidates(PROFILES, ['quizs', 'pi', 'codex'], 'q2')).toEqual(['p1', 'p2', 'x1']);
  });
  it('主选不是 quizs（pi）时为空', () => {
    expect(hubFallbackCandidates(PROFILES, ['pi', 'quizs'], 'p1')).toEqual([]);
  });
  it('主选查不到时为空', () => {
    expect(hubFallbackCandidates(PROFILES, ['pi', 'quizs'], 'zz-none')).toEqual([]);
  });
  it('主选的 adapter 不是字符串（null 或缺键）时为空', () => {
    expect(hubFallbackCandidates(PROFILES, ['pi'], 'n1')).toEqual([]);
    expect(hubFallbackCandidates(PROFILES, ['pi'], 'm1')).toEqual([]);
  });
  it('允许名单为空时为空；名单去掉 quizs 后没有候选时也为空', () => {
    expect(hubFallbackCandidates(PROFILES, [], 'q1')).toEqual([]);
    expect(hubFallbackCandidates(PROFILES, ['quizs'], 'q1')).toEqual([]);
  });
});

describe('allowedProfiles 与 hubPostName 的既有行为（D01）', () => {
  it('allowedProfiles 只留 adapter 非空且在名单里的，按输入顺序', () => {
    expect(allowedProfiles(PROFILES, ['pi'])).toEqual(['p1', 'p2']);
    expect(allowedProfiles(PROFILES, [])).toEqual([]);
  });
  it('hubPostName：六个中文名，未知码原样', () => {
    expect(hubPostName('coordinator')).toBe('协调人');
    expect(hubPostName('planner')).toBe('规划端');
    expect(hubPostName('contract')).toBe('合同端');
    expect(hubPostName('gate')).toBe('门禁端');
    expect(hubPostName('audit')).toBe('审核端');
    expect(hubPostName('exec')).toBe('执行端');
    expect(hubPostName('zz-9')).toBe('zz-9');
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

const ARGS = { post: 'contract', profile: 'step-high' };
const TURN = '审核端（audit）：2 个回合在跑';

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

describe('useLivePreview 的两个新字段（D02）', () => {
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
  it('hub_changes/running_turns 原样出现在结果里（hubChanges/runningTurns）', async () => {
    postReply = {
      status: 200,
      body: envelope(
        {
          preview: previewJson({
            hub_changes: [{ post: 'contract', before: null, after: null }],
            running_turns: [TURN, 5],
          }),
          confirmation: 'c1',
        },
        ['config', 'hub', 'set', 'contract', 'step-high', '--dry-run', '--json'],
      ),
    };
    const { result } = renderHook(() => useLivePreview('hub.set', ARGS, true));
    await settlePreview();
    expect(result.current.result?.hubChanges).toEqual([{ post: 'contract', before: null, after: null }]);
    expect(result.current.result?.runningTurns).toEqual([TURN]);
    expect(result.current.result?.command).toEqual(['config', 'hub', 'set', 'contract', 'step-high']);
  });
  it('缺 hub_changes/running_turns 键时是空数组，不抛错', async () => {
    postReply = {
      status: 200,
      body: envelope({ preview: previewJson(), confirmation: 'c2' }, ['config', 'hub', 'set', 'contract', 'step-high', '--dry-run', '--json']),
    };
    const { result } = renderHook(() => useLivePreview('hub.set', ARGS, true));
    await settlePreview();
    expect(result.current.result?.hubChanges).toEqual([]);
    expect(result.current.result?.runningTurns).toEqual([]);
  });
  it('post reject：错误行照旧，hubChanges/runningTurns 是空数组', async () => {
    postError = new Error('连不上');
    const { result } = renderHook(() => useLivePreview('hub.set', ARGS, true));
    await settlePreview();
    expect(result.current.result?.error).toBe('预览失败：服务没有回应');
    expect(result.current.result?.hubChanges).toEqual([]);
    expect(result.current.result?.runningTurns).toEqual([]);
  });
});
'''


PAGE_PROBE = r'''// T045 门禁 page 探针：桩模式挂 App 核对操作列与两个入口（按钮文字、禁用规则、禁用数 11、
// 对话框关着不渲染候选）与表单（预填、替补联动、底部预览）；真实模式（注入假服务）核对确认发
// 岗位路由与 reload。不用假计时器（真实计时器等防抖/悬停）。每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import App from '../src/App';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { setConnectionState } from '../src/live/connection';
import { HUB_ROLES_POSTS } from '../src/mock/hub-roles';
import type { Envelope, HubChangeFallback, HubChangeSide } from '../src/api';

const BIND = '改绑定…';
const UNSET = '恢复缺省…';
const POSTS = ['coordinator', 'planner', 'contract', 'gate', 'audit', 'exec'];

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 12; i += 1) await act(async () => { await Promise.resolve(); });
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
function hubSec(): any {
  return qa(document, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    return id ? text(document.getElementById(id)) === '七端岗位' : false;
  }) || null;
}
function hubRow(post: string): any {
  const sec = hubSec();
  expect(sec, '应有「七端岗位」区块').toBeTruthy();
  const row = qa(sec, 'tbody tr').find((tr: any) => tr.getAttribute('data-post') === post);
  expect(row, '应有 data-post=' + post + ' 的行').toBeTruthy();
  return row;
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

describe('桩模式：操作列与两个入口（D05、D11）', () => {
  it('列头前六列一字不改、第七至九列是 T047 的三列、末尾是「操作」；每行两个按钮的 textContent 恰是「改绑定…」「恢复缺省…」（按钮里不藏岗位名）', async () => {
    await mountApp('#/roles');
    const table = hubSec().querySelector('table[aria-label="七端岗位"]');
    const headers = qa(table, 'thead th').map(text);
    expect(headers.slice(0, 6)).toEqual(['岗位', '运行时', '模型', '思考档位', '来源', '替补']);
    expect(headers.slice(6, 9)).toEqual(['时限与工具', '预算', '最近一回合']);
    expect(headers[headers.length - 1]).toBe('操作');
    for (const post of POSTS) {
      const row = hubRow(post);
      const buttons = qa(row, 'button');
      expect(buttons.length, post + ' 行有两个入口').toBe(2);
      expect(buttons[0].textContent, post + ' 主入口恰为「改绑定…」').toBe(BIND);
      expect(buttons[1].textContent, post + ' 次入口恰为「恢复缺省…」').toBe(UNSET);
    }
  });
  it('planner 无候选 → 改绑定…禁用；其余五行可点', async () => {
    await mountApp('#/roles');
    for (const post of ['coordinator', 'contract', 'gate', 'audit', 'exec']) {
      expect(btnIn(hubRow(post), BIND).disabled, post + ' 改绑定…可点').toBe(false);
    }
    expect(btnIn(hubRow('planner'), BIND).disabled, 'planner 的允许名单里没有任何 profile → 禁用').toBe(true);
  });
  it('contract/exec 配置行恢复缺省…可点；coordinator/planner/gate/audit 缺省行禁用', async () => {
    await mountApp('#/roles');
    expect(btnIn(hubRow('contract'), UNSET).disabled).toBe(false);
    expect(btnIn(hubRow('exec'), UNSET).disabled).toBe(false);
    for (const post of ['coordinator', 'planner', 'gate', 'audit']) {
      expect(btnIn(hubRow(post), UNSET).disabled, post + ' 缺省行 → 恢复缺省…禁用').toBe(true);
    }
  });
  it('角色页禁用按钮数 6（page-app 的口径：方案条 切换… 1 + planner 改绑定… 1 + 4 个缺省行恢复缺省…）', async () => {
    await mountApp('#/roles');
    expect(qa(frame(), 'button').filter((b: any) => b.disabled).length).toBe(6);
  });
  it('对话框关着时：七端岗位一组只有 12 个入口按钮，没有下拉与候选文字（step-low 不出现）', async () => {
    await mountApp('#/roles');
    const sec = hubSec();
    expect(qa(sec, 'button').length, '这一组只有 6×2 个入口按钮').toBe(12);
    expect(qa(sec, 'select').length, '对话框关着时不渲染表单字段').toBe(0);
    expect(text(sec)).not.toContain('step-low');
  });
});

describe('桩模式：改绑定表单（D03、D04）', () => {
  it('contract 行：标题「改绑定：合同端」；quizs-m3 不在候选 → 主选预填第一个候选；主选非 quizs → 替补禁用且只有「不设替补」；底部命令与前后对比四行；确认走桩的写流程', async () => {
    await mountApp('#/roles');
    fireEvent.click(btnIn(hubRow('contract'), BIND));
    await flush();
    const d = needDlg();
    expect(text(d)).toContain('改绑定：合同端');
    const main = selectByLabel(d, '主绑定');
    expect(qa(main, 'option').map((o: any) => o.value)).toEqual(['step-high', 'step-low']);
    expect(main.value, '现有主绑定 quizs-m3 不在候选 → 预填第一个候选').toBe('step-high');
    const fb = selectByLabel(d, '替补');
    expect(fb.disabled, '主选是 pi → 替补下拉禁用').toBe(true);
    expect(qa(fb, 'option').map(text)).toEqual(['不设替补']);
    await sleep(450);
    await flush();
    const t = text(needDlg());
    expect(t).toContain('config hub set contract step-high');
    expect(t).toContain('运行时：quizs · quizs → pi · pi');
    expect(t).toContain('模型：minimax/MiniMax-M3.1-Flash → bb/step-5-preview');
    expect(t).toContain('思考档位：high → high');
    expect(t).toContain('替补：step-high → —');
    const confirm = btnIn(needDlg(), '确认…');
    expect(confirm.disabled, '预览 ok 且对应当前取值 → 可确认').toBe(false);
    fireEvent.click(confirm);
    await flush();
    const cd = needDlg();
    expect(text(cd), '表单关上后开写确认框（先关表单再 start）').toContain('改绑定 contract？');
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(80);
    await flush();
    expect(text(document.body)).toContain('已改绑定 contract');
  });
  it('exec 行：现有主绑定 step-high 在候选里 → 预填它；取消后对话框关上', async () => {
    await mountApp('#/roles');
    fireEvent.click(btnIn(hubRow('exec'), BIND));
    await flush();
    const d = needDlg();
    expect(selectByLabel(d, '主绑定').value, '现有主绑定在候选里 → 预填它').toBe('step-high');
    expect(selectByLabel(d, '替补').disabled).toBe(true);
    fireEvent.click(btnIn(d, '取消'));
    await flush();
    expect(dlg(), '取消后表单对话框应关上').toBeNull();
  });
  it('预览失败（write=preview-fail）：底部显示错误原文，确认…不可点', async () => {
    await mountApp('#/roles?write=preview-fail');
    fireEvent.click(btnIn(hubRow('contract'), BIND));
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

const ROLES = { active_preset: 'default', roles: [
  { role: 'contract', explicit: false, binding: { mode: 'manual' }, differs_from_preset: false },
  { role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' }, differs_from_preset: false, profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, effort_effective: 'high' },
] };
const PRESETS = { active_preset: 'default', presets: [
  { name: 'default', description: '日常', roles: ['execution'], active: true },
] };
const REAL_PROFILES = { profiles: [
  { id: 'quizs-m9', runtime: 'quizs', adapter: 'quizs', provider: 'minimax', model: 'MiniMax-M3.1-Flash', options: { thinking: 'high' }, credential_env: [] },
  { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: [] },
  { id: 'step-low', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini', options: { thinking: 'low' }, credential_env: [] },
] };

const side = (o: Partial<HubChangeSide> = {}): HubChangeSide => ({
  source: 'config', profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null, fallback: null, ...o,
});
const fbSide = (o: Partial<HubChangeFallback> = {}): HubChangeFallback => ({
  profile: null, runtime: null, adapter: null, provider: null, model: null, thinking: null, ...o,
});
const contractBefore = side({
  source: 'config', profile: 'quizs-m3', runtime: 'quizs', adapter: 'quizs',
  provider: 'minimax', model: 'MiniMax-M3.1-Flash', thinking: 'high',
  fallback: fbSide({ profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' }),
});
const quizsAfter = side({
  source: 'config', profile: 'quizs-m9', runtime: 'quizs', adapter: 'quizs',
  provider: 'minimax', model: 'MiniMax-M3.1-Flash', thinking: 'high',
  fallback: fbSide({ profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' }),
});

let gets: string[] = [];
let posts: Array<{ path: string; body: any }> = [];
let previewJson: Record<string, unknown> = {};

function basePreview(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    binding_changes: [], resources: [{ resource: 'hub' }], notes: [], unreadable: [], warnings: [],
    running_attempts: [], running_turns: [], needs_yes: false,
    hub_changes: [{ post: 'contract', before: contractBefore, after: quizsAfter }],
    ...over,
  };
}

const fake: LiveClient = {
  get<T>(path: string): Promise<Envelope<T>> {
    gets.push(path);
    if (path === '/api/v1/hub/roles') return Promise.resolve(okEnv(HUB_ROLES_POSTS, ['config', 'hub', 'show', '--json']) as unknown as Envelope<T>);
    if (path === '/api/v1/roles') return Promise.resolve(okEnv(ROLES) as unknown as Envelope<T>);
    if (path === '/api/v1/profiles') return Promise.resolve(okEnv(REAL_PROFILES) as unknown as Envelope<T>);
    if (path === '/api/v1/presets') return Promise.resolve(okEnv(PRESETS) as unknown as Envelope<T>);
    if (path === '/api/v1/meta') return Promise.resolve(okEnv({ version: 'pi_dispatch 1.0.0', repo_name: 'r' }) as unknown as Envelope<T>);
    return Promise.resolve(okEnv(null) as unknown as Envelope<T>);
  },
  post<T>(path: string, body: unknown): Promise<{ status: number; body: Envelope<T> }> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      return Promise.resolve({
        status: 200,
        body: okEnv({ preview: previewJson, confirmation: 'c-real-1' }, ['config', 'hub', 'set', 'contract', 'quizs-m9', '--fallback=step-high', '--dry-run', '--json']) as unknown as Envelope<T>,
      });
    }
    return Promise.resolve({ status: 200, body: okEnv(null, ['config', 'hub', 'set', 'contract']) as unknown as Envelope<T> });
  },
  getRaw<T>(): Promise<{ status: number; body: T }> {
    return Promise.resolve({ status: 404, body: null as unknown as T });
  },
};

describe('真实模式：表单候选与预填（D03）', () => {
  beforeEach(() => {
    gets = [];
    posts = [];
    previewJson = basePreview();
  });
  it('主选候选含 quizs；主选是 quizs → 替补候选去掉 quizs 且预填现有替补；换主选为非 quizs → 替补清空并禁用', async () => {
    setLiveClientForTests(fake);
    await mountApp('#/roles');
    fireEvent.click(btnIn(hubRow('contract'), BIND));
    await flush();
    const d = needDlg();
    const main = selectByLabel(d, '主绑定');
    expect(qa(main, 'option').map((o: any) => o.value)).toEqual(['quizs-m9', 'step-high', 'step-low']);
    expect(main.value, 'quizs-m3 不在候选 → 预填第一个候选（quizs 的）').toBe('quizs-m9');
    const fb = selectByLabel(d, '替补');
    expect(fb.disabled, '主选是 quizs → 替补可选').toBe(false);
    expect(qa(fb, 'option').map((o: any) => o.value)).toEqual(['', 'step-high', 'step-low']);
    expect(fb.value, '现有替补 step-high 在替补候选里 → 预填它').toBe('step-high');
    fireEvent.change(main, { target: { value: 'step-high' } });
    await flush();
    expect(fb.disabled, '主选换成 pi → 替补禁用').toBe(true);
    expect(fb.value, '替补清空').toBe('');
  });
  it('底部只显示本岗位的前后对比：预览里没有本岗位的项时不显示这一节', async () => {
    previewJson = basePreview({ hub_changes: [{ post: 'gate', before: null, after: null }] });
    setLiveClientForTests(fake);
    await mountApp('#/roles');
    fireEvent.click(btnIn(hubRow('contract'), BIND));
    await flush();
    await sleep(450);
    await flush();
    const t = text(needDlg());
    expect(t).toContain('config hub set contract quizs-m9 --fallback=step-high');
    expect(t).not.toContain('运行时：');
  });
});

describe('真实模式：确认发岗位路由与 reload（D06）', () => {
  beforeEach(() => {
    gets = [];
    posts = [];
    previewJson = basePreview();
  });
  it('改绑定：底部命令带 --fallback；确认发 POST /api/v1/hub/roles/contract（正文带 profile 与 fallback），成功后 reload', async () => {
    setLiveClientForTests(fake);
    await mountApp('#/roles');
    const rolesBefore = gets.filter((p) => p === '/api/v1/roles').length;
    fireEvent.click(btnIn(hubRow('contract'), BIND));
    await flush();
    await sleep(450);
    await flush();
    const d = needDlg();
    const t = text(d);
    expect(t).toContain('config hub set contract quizs-m9 --fallback=step-high');
    expect(t).toContain('运行时：quizs · quizs → quizs · quizs');
    expect(t).toContain('替补：step-high → step-high');
    fireEvent.click(btnIn(d, '确认…'));
    await flush();
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    await sleep(120);
    await flush();
    const hubPosts = posts.filter((p) => p.path.indexOf('/api/v1/hub/roles/') === 0);
    expect(hubPosts.length, '只发一次岗位写路由').toBe(1);
    expect(hubPosts[0].path).toBe('/api/v1/hub/roles/contract');
    expect(hubPosts[0].body.profile).toBe('quizs-m9');
    expect(hubPosts[0].body.fallback).toBe('step-high');
    expect(typeof hubPosts[0].body.confirmation).toBe('string');
    expect(hubPosts[0].body.confirmation.length).toBeGreaterThan(0);
    expect(text(document.body)).toContain('已改绑定 contract');
    expect(gets.filter((p) => p === '/api/v1/roles').length, '成功之后 reload（页面重新读了 roles）').toBeGreaterThan(rolesBefore);
  });
  it('恢复缺省…（exec 配置行）：确认发 POST /api/v1/hub/roles/exec/unset，正文只有确认号；成功后 reload', async () => {
    setLiveClientForTests(fake);
    await mountApp('#/roles');
    const rolesBefore = gets.filter((p) => p === '/api/v1/roles').length;
    fireEvent.click(btnIn(hubRow('exec'), UNSET));
    await flush();
    const cd = needDlg();
    expect(text(cd)).toContain('恢复缺省 exec？');
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(120);
    await flush();
    const unsetPosts = posts.filter((p) => p.path === '/api/v1/hub/roles/exec/unset');
    expect(unsetPosts.length).toBe(1);
    expect(Object.keys(unsetPosts[0].body).sort()).toEqual(['confirmation']);
    expect(text(document.body)).toContain('已恢复缺省 exec');
    expect(gets.filter((p) => p === '/api/v1/roles').length, '成功之后 reload').toBeGreaterThan(rolesBefore);
  });
});
'''


PROBE_SPECS = {
    "unit": (UNIT_PROBE, (ROLES_LOGIC_REL, LIVEPREVIEW_REL)),
    "page": (PAGE_PROBE, (HUBPOSTS_REL, HUBBINDFORM_REL, HUBBIND_CSS_REL, ROLESVIEW_REL, ROLES_LOGIC_REL, MOCK_HUB_ROLES_REL, MOCK_PROFILES_REL)),
}
PROBE_ORDER = ("unit", "page")


# ---------------------------------------------------------------------------
# P 系列：流水线断言；D 系列：探针断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、D07、D08：npm 依赖（已在就跳过）、npm test（全绿，含执行端两个新测试与改过断言的
    两处包内测试）都退出 0；依赖文件一个字节没动；gate-probe/ 没有留下。"""
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


def test_d01_d02_probe_unit(pipeline):
    """unit 探针 / D01、D02：hubFallbackCandidates 的五种边界（quizs 主选去 quizs、非 quizs、查不到、
    adapter 非字符串、名单为空）、allowedProfiles/hubPostName 的既有行为、useLivePreview 两个新字段
    （原样出现、缺键空数组、reject 时不抛错）。"""
    assert_probe_ok(pipeline, "unit")


def test_d03_d04_d05_d06_d11_probe_page(pipeline):
    """page 探针 / D03–D06、D11：桩模式下操作列与两个按钮的 textContent、planner 无候选禁用、缺省行
    恢复缺省…禁用、角色页禁用数 11、对话框关着不渲染候选；表单预填与替补联动、底部命令与前后对比四行、
    预览失败时确认不可点；真实模式确认发岗位路由（带/不带 fallback）与成功后 reload。"""
    assert_probe_ok(pipeline, "page")
