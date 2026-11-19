"""T043 战前门禁：桌面端前端第 9 片「CLI 运行时页的 Quizs 一块」（模型配置 M4 之三）的黑盒基准测试
（合同 t043-desktop-web-quizs-block.v1，基线 282f9229364bcaccf0e2e11c2f496d06850b0854）。

被测对象是 ``desktop/web/`` 前端：

- ``src/api.ts``：只新增导出——五个类型（QuizsProviderRow/QuizsProvidersData/QuizsLiveStatus/QuizsLiveRow/
  QuizsLiveData，字段只用 T042 白名单登记的）与两个读函数 ``getQuizsProviders``/``getQuizsLive``
  （真实模式分别 ``GET /api/v1/quizs/providers`` 60 秒、``GET /api/v1/quizs/live`` 150 秒，不回落桩；
  桩模式命令 ``config quizs providers --json`` / ``config quizs live --json``，``?mock=loading/error`` 照
  ``read()`` 既有行为，情景由 ``?quizs=`` 选）。
- ``src/mock/quizs.ts``（新，只能 .ts）：``QuizsScenario`` 五值（ok/expired/missing/broken/empty）、
  ``quizsScenario()`` 只认 ``quizs`` 键（缺省或认不出按 ok）、两个信封函数按情景给出；形状只写真内核
  交得出的字段。
- ``src/pages/RuntimesPage.tsx``：``loadRuntimes`` 用 ``Promise.all`` 并行读三条，只有 runtimes 失败才
  整页失败，两个 Quizs 信封整个放进 ``data.quizs``；``isEmpty`` 仍只看 runtimes；load/isEmpty 仍是
  命名的模块级函数；页头与 children 签名不动。
- ``src/pages/readonly1/runtimes-RuntimesView.tsx``：``RuntimesViewProps`` 加必填 ``quizs`` 属性；
  「就绪检查」之后渲染 ``QuizsBlock``；既有两节一字不改；视图仍不调 api（只 import type）。
- ``src/pages/readonly1/runtimes-QuizsBlock.tsx``（新）：``Section title="Quizs"``、两张 ``Table``
  （提供方档案四列、live 套六列，``rt-quizs-table`` 类、不用 ``rt-table``）、逐字表文案、时刻经
  ``formatLocalUtc``、区块里没有任何按钮/role=status/内联 style。
- ``src/pages/readonly1/runtimes-quizs-logic.ts``（新，纯函数）：billingLabel/liveStateLabel/
  liveSourceLabel/liveNextStep/nextStepCell/formatMsUtc/formatIsoUtc/providersUnavailable/liveUnavailable
  （nextStepCell 是「下一步」列的拼接：下一步文本在前、问题文字在后，中间「；」）。
- ``runtimes-styles.css``：只在末尾追加 ``.rt-quizs*`` 规则（只用令牌；px 字面量带出处注释；
  不复用 ``rt-table``）。
- 既有测试只按合同补：live-api.test.ts 的 ROWS 加两行、描述标题 16→18；page-runtimes.test.tsx 四处与
  writes-remove.test.tsx 一处直接渲染补 ``quizs`` 属性；新测试 page-quizs.test.tsx 与 quizs-logic.test.ts。

基线（282f9229）上两个读函数、mock/quizs.ts、QuizsBlock、纯函数文件、两个新测试与 CSS 的 quizs 规则都
不存在，所以本文件的失败落在「记号不在」「文件不存在」这类断言上，不是导入、收集或语法错误：模块级只
导入标准库，所有仓库文件的读取都发生在用例函数里；流水线（npm、Vitest、探针）放在 ``pipeline`` 会话级
夹具里（全量 pytest 默认跳过，点名运行本文件才跑；候选里 api.ts 还没有 getQuizsProviders 时夹具不调
npm——基线上没有新东西可跑，也避免联网装依赖，照 T024/T040/T041 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：api.ts 的类型与读函数（S01）；mock/quizs.ts 的
  情景、夹具取值与白名单外的字段（S02）；RuntimesPage 的并行读与不变面（S03）；RuntimesView 的接线与
  既有两节（S04）；QuizsBlock 的区块规矩与逐字文案（S05）；纯函数文件（S06）；CSS 的 quizs 规则（S07）；
  执行端测试文件在位且要点齐备（S08）；共享面——mock JSON 仍 14 份、顶层页面仍 9 个、package.json 与
  锁文件的字节冻结（S09）；新文件的源码规矩（role=status、网络词、危险写入、matchMedia 一类、
  「（UTC 」字面量）（S10）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、
  ``npm test``（全绿，含执行端两个新测试与照新行为补过参数的既有测试）；两份探针逐份写成
  ``gate-probe/probe-<uid>-t043-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，``finally``
  里删除。探针用 ``vi.mock('../src/api')`` 的替身（默认转调真实现、可注入任意信封）挂载整个 App，不
  mock 被测组件；每份自带全部辅助函数，不跨文件共享作用域。
  - page：五个情景（ok 四列两行逐字与六列两套就绪、expired、missing、empty、broken 的「Quizs 跑不
    起来」与逐套「读不出」）、区块里没有按钮/role=status/内联 style、注入 providers/live/runtimes
    三种失败、``?mock=`` 五态的页面状态、时刻与 formatLocalUtc 的输出一致。
  - unit：两个读函数的桩模式命令与情景、broken 信封形状、``?mock=`` 优先于情景、挂起、真实模式的
    路径/时限/透传、深拷贝；QuizsBlock 直挂兜底——五种状态与认不出的标签色调下一步、缺的文件「、」
    连接且其它状态不显示、problem 与 status.problem 的「；」拼接、时刻的 null/非法值「—」、空数组
    思考档位「—」。

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
RO_REL = f"{SRC_REL}/pages/readonly1"

API_REL = f"{SRC_REL}/api.ts"
QUIZS_MOCK_REL = f"{SRC_REL}/mock/quizs.ts"
RUNTIMESPAGE_REL = f"{SRC_REL}/pages/RuntimesPage.tsx"
VIEW_REL = f"{RO_REL}/runtimes-RuntimesView.tsx"
QUIZSBLOCK_REL = f"{RO_REL}/runtimes-QuizsBlock.tsx"
QUIZSLOGIC_REL = f"{RO_REL}/runtimes-quizs-logic.ts"
CSS_REL = f"{RO_REL}/runtimes-styles.css"
RELATIVETIME_REL = f"{SRC_REL}/components/RelativeTime.tsx"

LIVEAPI_TEST_REL = f"{TESTS_REL}/live-api.test.ts"
PAGE_RUNTIMES_TEST_REL = f"{TESTS_REL}/page-runtimes.test.tsx"
WRITES_REMOVE_TEST_REL = f"{TESTS_REL}/writes-remove.test.tsx"
PAGE_APP_TEST_REL = f"{TESTS_REL}/page-app.test.tsx"
READONLY2_APP_TEST_REL = f"{TESTS_REL}/readonly2-app.test.tsx"
PAGE_QUIZS_TEST_REL = f"{TESTS_REL}/page-quizs.test.tsx"
QUIZS_LOGIC_TEST_REL = f"{TESTS_REL}/quizs-logic.test.ts"

# 基线名单：src/mock 恰 14 份 JSON、src/pages 顶层恰 9 个 *Page.tsx（不新增 JSON、不新增页面文件）
BASELINE_MOCK_JSON_COUNT = 14
BASELINE_PAGE_COUNT = 9

# 依赖冻结（合同 D10：package.json 与锁文件不变；行尾归一为 LF 后的字节数与 sha256）
BASELINE_DIGESTS = {
    f"{WEB_REL}/package.json": (820, "094d3622e54097e0f50f0ab2a71a5caa22491dba9d3ac6ef83047426f8c57f5a"),
    f"{WEB_REL}/package-lock.json": (108793, "1bc4e1fbfeb02a17280d0de1d98a5f3b2721fa91229c271c66d590d059d82d28"),
}

# api.ts 既有的全部导出函数（合同兼容性：既有导出与签名一个不改，本片只新增）
OLD_API_EXPORTS = (
    "getMeta", "getMetaNow", "getStatus", "getAttempt", "readFile", "getRoles", "getProfiles", "getPresets",
    "getHubRoles", "diffPresets", "getRuntimes", "getPlugins", "getHistory", "getUsage", "listSecrets",
    "getHistoryEntry", "getPlugin", "preview", "getOperation", "usePreset", "setPluginEnabled", "removePreset",
    "removeProfile", "removeRuntime", "rollback", "addProfile", "editProfile", "setHubRole", "unsetHubRole",
    "addRuntime",
)
# WriteAction 既有的 12 个成员（合同 Repository facts；本片不动写侧）
OLD_WRITE_ACTIONS = (
    "preset.use", "plugin.enable", "plugin.disable", "preset.remove", "profile.remove", "runtime.remove",
    "config.rollback", "profile.add", "profile.edit", "hub.set", "hub.unset", "runtime.add",
)
# 合同 Behavior contract 的五个新类型
QUIZS_TYPES = ("QuizsProviderRow", "QuizsProvidersData", "QuizsLiveStatus", "QuizsLiveRow", "QuizsLiveData")

# 夹具取值（合同第 3 步逐字：取值出处是站主核实的 Quizs 输出形状）
FIXTURE_TOKENS = (
    "stepfun", "step-5-preview", "deepseek", "deepseek-chat", "step_plan_credits", "deepseek_prepaid_balance",
    "1790000000000", "1700000000000", "2026-11-20T08:00:00.000Z", "qualification.json",
    "quizs live status 失败（退出码 127）：", "ERROR: ", "mailbox", "env", "ready",
)
# T042 白名单之外的字段：夹具与类型都不许带（D02）
FORBIDDEN_FIELDS = ("live_dir", "build_id", "issued_at_ms", "capabilities", "credential")

# 逐字表的文案（合同 Behavior contract；S05/S06 在对应文件里按包含查）
BLOCK_TEXTS = (
    "Quizs 跑不起来", "没能读到 Quizs 的 live 套", "还没有 Quizs 提供方档案", "还没有 Quizs live 套",
    "返回退出码", "没有返回退出码",
)
LOGIC_TEXTS = (
    "仅测试", "套餐额度", "预付余额",
    "就绪", "已过期", "构建不一致", "无效", "缺文件", "读不出", "未知",
    "信箱", "环境变量",
    "不用动", "续期后再看", "重新构建这一套", "换一套能用的", "补齐缺的文件", "看这一套自己的问题",
    "按这一套的说明处理",
)

# 表列（合同「区块与 DOM」：恰好四列 / 恰好六列）
PROVIDERS_COLUMNS = ["提供方", "模型", "思考档位", "计费"]
LIVE_COLUMNS = ["提供方", "来源", "状态", "证书到期", "档案有效期", "下一步"]

# 执行端两个新测试文件的最小覆盖记号（合同第 9 步）
EXECUTOR_TEST_TOKENS = {
    "page-quizs.test.tsx": (
        "Quizs 提供方档案", "Quizs live 套", "Quizs 跑不起来", "读不出", "quizs live status 失败（退出码 127）",
        "看这一套自己的问题", "已过期", "缺 qualification.json", "还没有 Quizs", "button", "quizs=", "getRuntimes",
    ),
    "quizs-logic.test.ts": (
        "billingLabel", "liveStateLabel", "liveSourceLabel", "liveNextStep", "nextStepCell", "formatMsUtc",
        "formatIsoUtc", "providersUnavailable", "liveUnavailable", "<redacted>", "null",
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

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T024/T041 门禁），用完就停下并在断言里写明。
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 120}

ASSUMPTIONS = (
    "合同 v1 对 live 表「恰好六列」与「问题列」两处说法合不上，v2 已把方向定死：live 套表仍恰六列、不设第七"
    "列，问题文字并入「下一步」列——列内容 = 下一步文本 + 「；」 + 问题文字，问题文字内部 problem 在前、"
    "status.problem 在后彼此也用「；」，某段为空只写另一段。门禁的表头断言按六列逐字钉；有问题的行对"
    "「下一步」单元格按拼接后的整串断言（broken 情景钉到「看这一套自己的问题；quizs live status 失败"
    "（退出码 127）：」前缀）；「读不出」不解析 problem 文字照钉",
    "时刻断言全部用 components/RelativeTime.tsx 的 formatLocalUtc 现算期望值（不写死本地时间）；"
    "「（UTC 」字面量只由 T013 的单一来源断言负责，本门禁静态复查一遍新文件",
    "区块在三节里的位置只钉「Quizs 在『就绪检查』之后」，不钉它是不是最后一节（后续片可能合法地再加节）",
    "live 两套的行序、提供方档案两行的行序合同没写死：探针按列值找行（如来源=信箱），不按行号",
    "页面级错误块的文案是 PageFrame 既有格式（命令带全角括号），Quizs 区块内部的错误文案是合同逐字"
    "（命令不带括号、按空格连接）——两处格式不同是合同原文，不是笔误",
    "package.json 与 package-lock.json 按基线字节冻结（行尾归一 LF）；依赖变更由每一份合同的 "
    "dependency_changes: forbidden 背书",
    "page-app.test.tsx 与 readonly2-app.test.tsx 不改由调度器的范围门禁证明（禁改文件），门禁只钉它们"
    "仍在、没有 skip/only/todo；运行时页禁用钮仍是 5 个这一行为面由「区块里没有按钮」的探针钉住",
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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041 的同一口径）：行注释与块注释在同一次从左往右的扫描里认。
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


def _argv_written(code, *parts):
    """argv 模板片段在不在：连写（``config quizs providers``）或相邻的数组元素都算。"""
    if " ".join(parts) in code:
        return True
    for quote in ('"', "'"):
        elems = ("," + r"\s*").join(quote + re.escape(part) + quote for part in parts)
        if re.search(elems, code) is not None:
            return True
    return False


def _statement(text, start_marker):
    """从 start_marker 起取「一条声明」：到第一个分号，或到下一条 const/function/export 声明为止。
    一行式箭头函数后面没有行首 "}"，按声明边界截，避免一路吃到文件尾（B3：那样会把组件 JSX 里的
    quizs={data.quizs} 吞进 isRuntimesEmpty 的切片而误报）。"""
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


def _api_imports_type_only(text):
    """从 ../../api 引入的每一条 import 语句都只能是 import type（视图不调 api，T009 的口径；
    多行 import 按整条语句看，import { type X } 的写法也算只引类型）。"""
    problems = []
    for m in re.finditer(r"import[^;]*?from\s*['\"]\.\./\.\./api['\"]", text, re.S):
        stmt = m.group(0)
        if not (stmt.lstrip().startswith("import type") or re.search(r"import\s*\{\s*type\b", stmt)):
            problems.append(f"api 引入不是 import type：{stmt.splitlines()[0][:70]}")
    return problems


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_api_quizs_read_functions():
    """S01 / D01、兼容性：api.ts 加 getQuizsProviders/getQuizsLive（真实分支的路径与时限逐字、桩分支的
    命令逐字、夹具来自 mock/quizs），五个新类型导出；既有的导出函数、WriteAction 成员与 Envelope 七字段
    一个不改（只新增，不改签名）。"""
    need_file(API_REL)
    text = read_rel(API_REL)
    code = strip_ts_comments(text)
    problems = []
    # 两个读函数
    for name in ("getQuizsProviders", "getQuizsLive"):
        if not re.search(rf"export function {name}\(", code):
            problems.append(f"api.ts 应导出 export function {name}")
    providers_fn = _block(code, "export function getQuizsProviders")
    live_fn = _block(code, "export function getQuizsLive")
    if not providers_fn:
        problems.append("找不到 getQuizsProviders 的函数体")
    else:
        if not re.search(r"get<QuizsProvidersData>\(\s*'/api/v1/quizs/providers'\s*,\s*undefined\s*,\s*60\s*\)",
                         providers_fn):
            problems.append("真实分支应是 client.get<QuizsProvidersData>('/api/v1/quizs/providers', undefined, 60)")
        if not _argv_written(providers_fn, "config", "quizs", "providers", "--json"):
            problems.append("桩分支的命令应恰为 ['config','quizs','providers','--json']")
        if "read(" not in providers_fn:
            problems.append("桩分支应走 read()（?mock= 的 loading/error 先于情景）")
    if not live_fn:
        problems.append("找不到 getQuizsLive 的函数体")
    else:
        if not re.search(r"get<QuizsLiveData>\(\s*'/api/v1/quizs/live'\s*,\s*undefined\s*,\s*150\s*\)", live_fn):
            problems.append("真实分支应是 client.get<QuizsLiveData>('/api/v1/quizs/live', undefined, 150)")
        if not _argv_written(live_fn, "config", "quizs", "live", "--json"):
            problems.append("桩分支的命令应恰为 ['config','quizs','live','--json']")
        if "read(" not in live_fn:
            problems.append("桩分支应走 read()")
    # 夹具来自 mock/quizs（按情景取信封的写法）
    if "from './mock/quizs'" not in text and "from \"./mock/quizs\"" not in text:
        problems.append("api.ts 应从 './mock/quizs' 引入情景信封（按情景取信封的写法）")
    if "quizsProvidersEnvelope" not in code or "quizsLiveEnvelope" not in code:
        problems.append("桩分支应转 quizsProvidersEnvelope()/quizsLiveEnvelope()（?quizs= 选情景）")
    # 五个新类型
    for tname in QUIZS_TYPES:
        if not re.search(rf"export (interface|type) {tname}\b", code):
            problems.append(f"api.ts 应导出类型 {tname}")
    # 既有导出一个不改
    for name in OLD_API_EXPORTS:
        if not re.search(rf"export function {name}\(", code):
            problems.append(f"api.ts 既有导出 {name} 应保留（只新增，不改）")
    for member in OLD_WRITE_ACTIONS:
        if f"'{member}'" not in code:
            problems.append(f"WriteAction 的既有成员 '{member}' 应保留")
    envelope = _block(code, "export interface Envelope")
    for field in ("ok", "exit_code", "data", "output", "messages", "command", "elapsed_ms"):
        if field not in envelope:
            problems.append(f"Envelope 的七字段应保留（看不到 {field}）")
    fail_if(problems, "api.ts 的两个 Quizs 读函数（S01）")


def test_s02_mock_quizs_fixture():
    """S02 / D02、第 3 步：mock/quizs.ts 只能是 .ts——纯类型引入、QuizsScenario 五值、quizsScenario 只认
    quizs 键（缺省 ok）、两个信封函数按情景给出；夹具取值逐字（两个提供方、证书毫秒数、valid_until、
    qualification.json、broken 的 ERROR: 前缀与「quizs live status 失败（退出码 127）：」前缀）；
    白名单外的字段（live_dir、build_id、id、issued_at_ms、capabilities、credential_*）一个不带。"""
    need_file(QUIZS_MOCK_REL)
    text = read_rel(QUIZS_MOCK_REL)
    code = strip_ts_comments(text)
    problems = []
    # 纯类型引入
    if "import type" not in text or "from '../api'" not in text:
        problems.append("mock/quizs.ts 应纯类型引入（import type { … } from '../api'）")
    # 情景类型与解析
    union = re.search(r"export type QuizsScenario\s*=([\s\S]*?);", code)
    if not union:
        problems.append("mock/quizs.ts 应导出 QuizsScenario 类型")
    else:
        members = re.findall(r"'([a-z0-9-]+)'", union.group(1))
        want = {"ok", "expired", "missing", "broken", "empty"}
        if set(members) != want:
            problems.append(f"QuizsScenario 应恰为五个值 {sorted(want)}，实际 {sorted(set(members))}")
    scenario_fn = _block(code, "export function quizsScenario")
    if not scenario_fn:
        problems.append("mock/quizs.ts 应导出 quizsScenario()")
    else:
        if "location.hash" not in scenario_fn:
            problems.append("quizsScenario 应读 location.hash 的查询串（照 writeScenario 的写法）")
        if "'quizs'" not in scenario_fn and '"quizs"' not in scenario_fn:
            problems.append("quizsScenario 只认 quizs 这一个键")
    for fn in ("quizsProvidersEnvelope", "quizsLiveEnvelope"):
        if not re.search(rf"export function {fn}\(", code):
            problems.append(f"mock/quizs.ts 应导出 {fn}()")
    # 夹具取值
    for token in FIXTURE_TOKENS:
        if token not in text:
            problems.append(f"夹具里应出现「{token}」（合同第 3 步的取值出处）")
    # 白名单外的字段
    for field in FORBIDDEN_FIELDS:
        if field in code:
            problems.append(f"夹具/类型里不应出现「{field}」（T042 白名单未登记）")
    if re.search(r"\bid\s*:", code):
        problems.append("夹具里不应出现 id:（providers 的 id 未登记，没有「档案 id」列）")
    fail_if(problems, "mock/quizs.ts 的情景与夹具（S02）")


def test_s03_runtimes_page_parallel():
    """S03 / D03：RuntimesPage 用 Promise.all 并行读三条（getRuntimes/getQuizsProviders/getQuizsLive），
    两个 Quizs 信封整个放进 data.quizs（providers/live 两个键）；load 与 isEmpty 仍是命名的模块级函数；
    isEmpty 仍只看 runtimes 的长度；页头两钮、页头说明与 children 签名不动。"""
    need_file(RUNTIMESPAGE_REL)
    text = read_rel(RUNTIMESPAGE_REL)
    code = strip_ts_comments(text)
    problems = []
    load = _block(code, "const loadRuntimes")
    if not load:
        load = _block(code, "function loadRuntimes")
    if not load:
        problems.append("RuntimesPage 应保留命名的模块级 loadRuntimes")
    else:
        if "Promise.all" not in load:
            problems.append("loadRuntimes 应用 Promise.all 并行读")
        for call in ("getRuntimes(", "getQuizsProviders(", "getQuizsLive("):
            if call not in load:
                problems.append(f"loadRuntimes 应并行调 {call[:-1]}")
        if not re.search(r"quizs\s*:\s*\{\s*providers", load) or "live" not in load:
            problems.append("成功信封的 data 里应整个放进 quizs: { providers, live }（两个信封不拆开）")
    empty_fn = _statement(code, "const isRuntimesEmpty")
    if not empty_fn:
        empty_fn = _statement(code, "function isRuntimesEmpty")
    if not empty_fn:
        problems.append("RuntimesPage 应保留命名的模块级 isRuntimesEmpty")
    else:
        if "runtimes.length" not in empty_fn:
            problems.append("isRuntimesEmpty 仍只看 runtimes.length === 0")
        if "quizs" in empty_fn:
            problems.append("isRuntimesEmpty 不应掺入 quizs（Quizs 失败不影响空态判定）")
    # 引入白名单内的读函数（T009 的 ALLOWED_API_READS 已含两个新名字；多行 import 按整条语句看）
    m = re.search(r"import\s*\{[^}]*\}\s*from\s*['\"]\.\./api['\"]", code, re.S)
    if not m:
        problems.append("RuntimesPage 应从 '../api' 命名引入读函数")
    else:
        for name in ("getRuntimes", "getQuizsProviders", "getQuizsLive"):
            if not re.search(rf"\b{name}\b", m.group(0)):
                problems.append(f"api 引入里应有 {name}")
    # 页头与 children 不动（「还没有登记的 runtime」那段空态文案随 T058 搬进 RuntimesView）
    for needle in ('title="CLI 运行时"', 'ScanRuntimesAction', "AddRuntimeAction"):
        if needle not in text:
            problems.append(f"页头/空态的既有内容应保留（看不到 {needle}）")
    if not re.search(r"\{\(data, reload\)\s*=>", code):
        problems.append("children 应仍是 (data, reload) => …")
    fail_if(problems, "RuntimesPage 的并行读（S03）")


def test_s04_runtimes_view_wiring():
    """S04 / D03、D04：RuntimesView 的 props 加必填 quizs（两个信封的形状）、「就绪检查」之后渲染
    QuizsBlock；既有两节一字不改（已登记表仍是 rt-table、就绪检查空框原文、[删除…] 仍走 runtime.remove）；
    视图仍不调 api（../../api 只许 import type）；样式表仍被本文件引入。"""
    need_file(VIEW_REL)
    text = read_rel(VIEW_REL)
    code = strip_ts_comments(text)
    problems = []
    props = _block(code, "export interface RuntimesViewProps")
    if not props:
        problems.append("RuntimesView 应保留 RuntimesViewProps")
    else:
        if not re.search(r"^\s*quizs\s*:", props, re.M):
            problems.append("RuntimesViewProps 应加 quizs 属性")
        if re.search(r"quizs\?\s*:", props):
            problems.append("quizs 属性应是必填（照 T038 的 hub 口径），不是 quizs?:")
        if "providers" not in props or "live" not in props:
            problems.append("quizs 属性应是 { providers: Envelope<QuizsProvidersData>; live: Envelope<QuizsLiveData> }")
    if "<QuizsBlock" not in code:
        problems.append("视图应渲染 <QuizsBlock … />（在「就绪检查」之后）")
    if "from './runtimes-QuizsBlock'" not in text:
        problems.append("QuizsBlock 应从 './runtimes-QuizsBlock' 引入")
    # 既有两节不动
    for needle in ('title="已登记"', 'title="就绪检查"', 'aria-label="已登记的 runtime"', "rt-table",
                   "RuntimeDoctor", "runtime.remove", "useWriteFlow"):
        if needle not in text:
            problems.append(f"「已登记」「就绪检查」两节的既有内容应一字不改（看不到 {needle}）")
    if "import './runtimes-styles.css'" not in text:
        problems.append("视图仍应引入 './runtimes-styles.css'（quizs 规则接进产品）")
    problems += _api_imports_type_only(text)
    fail_if(problems, "RuntimesView 的接线（S04）")


def test_s05_quizs_block_static():
    """S05 / D04–D07：QuizsBlock 导出（Section 标题 Quizs、两张表的 aria-label、rt-quizs-table 类且不用
    rt-table）；逐字表的区块文案在位；从 ../../api 只许 import type；区块里没有任何按钮/复制入口/
    role=status/内联 style；纯逻辑放 runtimes-quizs-logic。"""
    need_file(QUIZSBLOCK_REL)
    text = read_rel(QUIZSBLOCK_REL)
    code = strip_ts_comments(text)
    problems = []
    if not re.search(r"export function QuizsBlock\b", code):
        problems.append("runtimes-QuizsBlock.tsx 应导出 QuizsBlock")
    if 'title="Quizs"' not in code:
        problems.append("区块应是 Section title=\"Quizs\"")
    for label in ('"Quizs 提供方档案"', '"Quizs live 套"'):
        if label not in code:
            problems.append(f"两张表应各有 aria-label={label}")
    if "rt-quizs-table" not in code:
        problems.append("两张表的容器类应是 rt-quizs-table")
    if "rt-table" in code:
        problems.append("Quizs 的表不应复用 rt-table 类（最后列右对齐、最小宽 900px）")
    if "from './runtimes-quizs-logic'" not in text:
        problems.append("文案与时刻的纯函数应放 runtimes-quizs-logic（区块只负责摆）")
    if "from './common-Section'" not in text:
        problems.append("区块应复用 Section（section + aria-labelledby 指 h2）")
    for bad, why in (("<button", "区块里不放按钮"), ("Button", "区块里不放按钮"), ("DisabledAction", "区块里不放按钮"),
                     ("clipboard", "不给复制入口"), ("复制", "不给可复制的续期命令"),
                     ("role=\"status\"", "不渲染 role=status"), ("style={{", "不写内联 style")):
        if bad in code:
            problems.append(f"QuizsBlock 里不应出现 {bad}（{why}）")
    if "messages" not in code:
        problems.append("失败信封的 messages 应逐行原样写出")
    problems += _api_imports_type_only(text)
    # 逐字表的区块文案（QuizsBlock 或纯函数文件里都算）
    logic_text = read_rel(QUIZSLOGIC_REL) if (REPO_ROOT / QUIZSLOGIC_REL).is_file() else ""
    pool = text + "\n" + logic_text
    for t in BLOCK_TEXTS:
        if t not in pool:
            problems.append(f"逐字表的文案「{t}」应出现在 QuizsBlock 或纯函数文件里")
    fail_if(problems, "QuizsBlock 的区块规矩（S05）")


def test_s06_quizs_logic_pure():
    """S06 / D05、D11：runtimes-quizs-logic.ts 导出九个纯函数（billingLabel/liveStateLabel/liveSourceLabel/
    liveNextStep/nextStepCell/formatMsUtc/formatIsoUtc/providersUnavailable/liveUnavailable）；逐字表的文案全在；
    时刻经
    formatLocalUtc（不出现「（UTC 」字面量）；纯函数不碰 DOM、不引计时器；从 ../../api 只 import type。"""
    need_file(QUIZSLOGIC_REL)
    text = read_rel(QUIZSLOGIC_REL)
    code = strip_ts_comments(text)
    problems = []
    for fn in ("billingLabel", "liveStateLabel", "liveSourceLabel", "liveNextStep", "nextStepCell", "formatMsUtc",
               "formatIsoUtc", "providersUnavailable", "liveUnavailable"):
        if not re.search(rf"export function {fn}\(", code):
            problems.append(f"runtimes-quizs-logic.ts 应导出 export function {fn}")
    for t in LOGIC_TEXTS:
        if t not in code:
            problems.append(f"逐字表的文案「{t}」应出现在纯函数文件里")
    if "formatLocalUtc" not in code or "RelativeTime" not in text:
        problems.append("时刻应经 components/RelativeTime.tsx 的 formatLocalUtc（import 它，不自己拼）")
    for tone in ("success", "danger", "warning", "neutral"):
        if tone not in code:
            problems.append(f"状态色调表应含 {tone}")
    if "、" not in code:
        problems.append("思考档位与缺的文件用「、」连接（合同逐字）")
    if "；" not in code:
        problems.append("「下一步」列的拼接用「；」（下一步文本与问题文字之间、问题文字内部都是，合同 v2 逐字）")
    for bad in ("document.", "window.", "setTimeout", "setInterval"):
        if bad in code:
            problems.append(f"纯函数文件里不应出现 {bad}（不碰 DOM、不引计时器）")
    problems += _api_imports_type_only(text)
    fail_if(problems, "runtimes-quizs-logic 的纯函数（S06）")


def test_s07_css_quizs_rules():
    """S07 / D04、D08：runtimes-styles.css 末尾追加 .rt-quizs* 规则——.rt-quizs-table 在（照 .rt-table 的
    容器覆盖但不带 min-width 900px 与最后列右对齐）、除表之外至少两处文字/提示类；只用令牌（不写十六进制
    颜色与颜色函数、border-radius 只用 var()）；除 0 与 1px 外的 px 字面量所在行带出处注释。"""
    need_file(CSS_REL)
    text = read_rel(CSS_REL)
    at = text.find(".rt-quizs")
    assert at >= 0, "runtimes-styles.css 应在末尾追加 .rt-quizs* 规则"
    region = text[at:]
    code = strip_ts_comments(region)
    problems = []
    selectors = set(re.findall(r"\.rt-quizs[A-Za-z0-9_-]*", region))
    if ".rt-quizs-table" not in selectors:
        problems.append("应有 .rt-quizs-table（表的容器覆盖）")
    if len(selectors) < 3:
        problems.append(f"除表之外应至少再有两处 .rt-quizs* 类（文字/提示），现在只有 {sorted(selectors)}")
    if "900px" in code:
        problems.append(".rt-quizs 表不应有 min-width: 900px（那是 rt-table 的规矩）")
    if "text-align: right" in code:
        problems.append(".rt-quizs 表不应右对齐最后一列")
    if _HEX_COLOR.search(code):
        problems.append("quizs 规则里不应写十六进制颜色（只用令牌）")
    for fn in _COLOR_FUNCS:
        if fn in code:
            problems.append(f"quizs 规则里不应出现颜色函数 {fn}")
    for m in re.finditer(r"border-radius\s*:\s*([^;]+);", code):
        if not m.group(1).strip().startswith("var("):
            problems.append(f"border-radius 只能用令牌：border-radius: {m.group(1).strip()}")
    # px 字面量：除 0 与 1px 外，所在行要带出处注释（在原文行上查，注释才在）
    for line in region.splitlines():
        for m in re.finditer(r"(\d+(?:\.\d+)?)px", line):
            if m.group(1) in ("0", "1"):
                continue
            if "/*" not in line:
                problems.append(f"px 字面量所在行要带出处注释：{line.strip()}")
                break
    fail_if(problems, "runtimes-styles.css 的 quizs 规则（S07）")


def test_s08_executor_tests():
    """S08 / D09、第 9 步：两个新测试文件在位、不用 skip/only/todo、带最小覆盖记号；live-api.test.ts 的
    ROWS 恰加两行（16→18，两条新行逐字）且既有行不删；page-runtimes.test.tsx 四处与 writes-remove.test.tsx
    一处直接渲染都补了 quizs 属性、既有断言锚点仍在；page-app.test.tsx 与 readonly2-app.test.tsx 仍在且
    没有 skip/only/todo（不改由范围门禁证明）。"""
    problems = []
    for name in ("page-quizs.test.tsx", "quizs-logic.test.ts"):
        rel = f"{TESTS_REL}/{name}"
        need_file(rel)
        text = read_rel(rel)
        problems += _no_skip_marks(strip_ts_comments(text))
        missing = [t for t in EXECUTOR_TEST_TOKENS[name] if t not in text]
        if name == "page-quizs.test.tsx" and "formatLocalUtc" not in text and "UTC" not in text:
            # 时刻断言两种写法都算（合同：只比 UTC 那一段，或用 formatLocalUtc 算期望值；tests/ 不受
            # 「（UTC 」单一来源限制——cleanup1-shared.test.ts 就写着期望模板）
            missing.append("formatLocalUtc（或 UTC 段比法）")
        if missing:
            problems.append(f"{rel} 里缺少记号 {missing}（合同第 9 步的最小覆盖）")
    # live-api.test.ts：ROWS 恰 19 行（基线 17 行——16 个读函数，readFile 本来就占两行——加两条新行）、
    # 两条新行逐字、标题 18（读函数个数）、既有行不删（B2：18 是读函数个数不是行数）
    need_file(LIVEAPI_TEST_REL)
    live = read_rel(LIVEAPI_TEST_REL)
    rows_block = _block(live, "const ROWS", "\n];")
    if not rows_block:
        problems.append("live-api.test.ts 应保留 const ROWS")
    else:
        names = re.findall(r"name:\s*'([^']+)'", rows_block)
        if len(names) != 19:
            problems.append(f"ROWS 应恰为 19 行（基线 17 行加两条新行；readFile 占两行），实际 {len(names)}")
        if "18 个读函数" not in live:
            problems.append("describe 标题应改成「api.ts 的 18 个读函数…」")
        for name in ("getQuizsProviders", "getQuizsLive"):
            if name not in names:
                problems.append(f"ROWS 应加一行 {name}")
        for frag in ("'/api/v1/quizs/providers'", "timeout: 60", "'/api/v1/quizs/live'", "timeout: 150"):
            if frag not in rows_block:
                problems.append(f"ROWS 新行应含 {frag}")
        for old in ("getMeta", "getRuntimes", "readFile(不带 cursor)", "getHistoryEntry"):
            if old not in names:
                problems.append(f"ROWS 的既有行「{old}」应保留（一条不删）")
    problems += _no_skip_marks(strip_ts_comments(live))
    # page-runtimes.test.tsx：四处直接渲染都补 quizs
    need_file(PAGE_RUNTIMES_TEST_REL)
    pr = read_rel(PAGE_RUNTIMES_TEST_REL)
    uses = re.findall(r"<RuntimesView[^>]*>", pr, re.S)
    if len(uses) != 4:
        problems.append(f"page-runtimes.test.tsx 应仍恰有 4 处 <RuntimesView …>，实际 {len(uses)}")
    for use in uses:
        if "quizs=" not in use:
            problems.append(f"每处直接渲染都应补 quizs 属性：{use[:80]}")
    for anchor in ("'ID', '适配器', '能担任', '命令来源', '命令', '版本', '操作'",
                   "'pi', 'claude-code', 'codex', 'opencode', 'custom'"):
        if anchor not in pr:
            problems.append(f"page-runtimes.test.tsx 的既有断言锚点应保留（看不到 {anchor[:40]}）")
    problems += _no_skip_marks(strip_ts_comments(pr))
    # writes-remove.test.tsx：一处直接渲染补 quizs
    need_file(WRITES_REMOVE_TEST_REL)
    wr = read_rel(WRITES_REMOVE_TEST_REL)
    uses = re.findall(r"<RuntimesView[^>]*>", wr, re.S)
    if len(uses) != 1:
        problems.append(f"writes-remove.test.tsx 应仍恰有 1 处 <RuntimesView …>，实际 {len(uses)}")
    for use in uses:
        if "quizs=" not in use:
            problems.append(f"这一处直接渲染也应补 quizs 属性：{use[:80]}")
    if "删除运行时 opencode？" not in wr:
        problems.append("writes-remove.test.tsx 的既有断言锚点应保留（删除运行时 opencode？）")
    problems += _no_skip_marks(strip_ts_comments(wr))
    # 两个禁改的既有测试仍在、没有被削弱
    for rel in (PAGE_APP_TEST_REL, READONLY2_APP_TEST_REL):
        need_file(rel)
        problems += _no_skip_marks(strip_ts_comments(read_rel(rel)))
    fail_if(problems, "执行端测试与既有测试（S08）")


def test_s09_shared_surfaces():
    """S09 / D10：src/mock 仍恰 14 份 JSON（quizs 的夹具只能是 .ts）、src/pages 顶层仍恰 9 个 *Page.tsx；
    package.json 与 package-lock.json 按基线字节冻结（依赖不增不减）。"""
    jsons = sorted(p.name for p in (REPO_ROOT / f"{SRC_REL}/mock").glob("*.json"))
    assert len(jsons) == BASELINE_MOCK_JSON_COUNT, \
        f"src/mock 应仍恰 {BASELINE_MOCK_JSON_COUNT} 份 JSON，现在有 {jsons}"
    pages = sorted(p.name for p in (REPO_ROOT / f"{SRC_REL}/pages").glob("*Page.tsx"))
    assert len(pages) == BASELINE_PAGE_COUNT, \
        f"src/pages 顶层应仍恰 {BASELINE_PAGE_COUNT} 个 *Page.tsx，现在有 {pages}"
    for rel, want in BASELINE_DIGESTS.items():
        got = file_digest(REPO_ROOT / rel)
        assert got == want, f"{rel} 与基线不一致（依赖文件不许动）：基线 {want}，实际 {got}"


def test_s10_new_files_source_rules():
    """S10 / D07、D08：三个新文件（mock/quizs.ts、runtimes-QuizsBlock.tsx、runtimes-quizs-logic.ts）守
    既有源码规矩——不渲染 role=status、不调 matchMedia/scrollIntoView/ResizeObserver/IntersectionObserver、
    不出现网络词与危险 HTML 写入/动态求值类词（page-static.test.ts 按子串查的口径）、不写十六进制颜色与
    颜色函数、「（UTC 」字面量不许出现（只能经 formatLocalUtc）。改动的视图与页面文件同样复查。"""
    rels = (QUIZS_MOCK_REL, QUIZSBLOCK_REL, QUIZSLOGIC_REL, VIEW_REL, RUNTIMESPAGE_REL)
    problems = []
    for rel in rels:
        need_file(rel)
        text = read_rel(rel)
        code = strip_ts_comments(text)
        for mark in FORBIDDEN_SOURCE_MARKS:
            if mark == 'role="status"':
                if re.search(r"role\s*=\s*['\"]status['\"]", code):
                    problems.append(f"{rel} 里不应渲染 role=status")
                continue
            if mark in code:
                problems.append(f"{rel} 里不应出现「{mark}」")
        if "fetch" in code:
            problems.append(f"{rel} 里不应出现 fetch（按子串查，命名也要避开）")
        if _HEX_COLOR.search(code):
            problems.append(f"{rel} 里不应写十六进制颜色")
        for fn in _COLOR_FUNCS:
            if fn in code:
                problems.append(f"{rel} 里不应出现颜色函数 {fn}")
    # 「（UTC 」只许出现在 RelativeTime.tsx（T013 D02）；本片文件复查一遍
    for rel in rels:
        assert "（UTC " not in read_rel(rel), f"{rel} 里不应出现「（UTC 」字面量（只能经 formatLocalUtc）"
    assert "export function formatLocalUtc" in read_rel(RELATIVETIME_REL), \
        "components/RelativeTime.tsx 的 formatLocalUtc 应原样保留（本片不动它）"
    fail_if(problems, "新文件的源码规矩（S10）")


# ---------------------------------------------------------------------------
# 探针源码（每份自包含：辅助函数不跨文件共享）
# ---------------------------------------------------------------------------

PRELUDE = r"""
import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
function expectSectionsTitled(root: ParentNode) {
  qa(root, 'section').forEach((s) => {
    const id = s.getAttribute('aria-labelledby');
    const head = id ? document.getElementById(id) : null;
    expect(head && head.tagName, '有一个 section 没有 aria-labelledby 指向的 h2：' + textOf(s).slice(0, 40)).toBe('H2');
  });
}
function frame(): HTMLElement | null {
  return document.querySelector('[data-page-state]');
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
"""

# 替身 api.ts（T009/T041 探针同款）：默认转调真实现，用 set() 换成任意信封
API_MOCK = r"""
import * as api from '../src/api';

const hoisted = vi.hoisted(() => ({ spies: {} as Record<string, any>, overrides: {} as Record<string, any> }));
vi.mock('../src/api', async (importOriginal) => {
  const actual: any = await importOriginal();
  const out: any = { ...actual };
  for (const [name, fn] of Object.entries(actual)) {
    if (typeof fn === 'function') {
      const spy = vi.fn((...args: any[]) => (hoisted.overrides[name] ? hoisted.overrides[name](...args) : (fn as any)(...args)));
      hoisted.spies[name] = spy;
      out[name] = spy;
    }
  }
  return out;
});
beforeEach(() => {
  Object.keys(hoisted.overrides).forEach((k) => delete hoisted.overrides[k]);
  Object.values(hoisted.spies).forEach((s: any) => s.mockClear());
});
function set(name: string, value: any) {
  hoisted.overrides[name] = typeof value === 'function' ? value : () => Promise.resolve(value);
}
function env(data: any, command: string[] = ['gate']): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}
function bad(command: string[], code: number | null, messages: string[]): any {
  return { ok: false, exit_code: code, data: null, output: [], messages, command, elapsed_ms: 0 };
}
"""

# page 探针：五个情景、区块规矩、三种注入失败与 ?mock= 五态（合同 Behavior contract；D01–D07 的行为面）
PROBE_PAGE = PRELUDE + API_MOCK + r"""
import { formatLocalUtc } from '../src/components/RelativeTime';

function pageRoot(): HTMLElement | null {
  return document.querySelector('[data-page="runtimes"]');
}
function needPageRoot(): HTMLElement {
  const r = pageRoot();
  expect(r, '运行时页视图应已渲染（data 态）').toBeTruthy();
  return r as HTMLElement;
}
function quizsSection(): HTMLElement {
  const sec = sectionNamed(needPageRoot(), 'Quizs');
  expect(sec, '应有「Quizs」区块').toBeTruthy();
  return sec as HTMLElement;
}
function tableOf(root: ParentNode, label: string): HTMLTableElement {
  const t = root.querySelector('table[aria-label="' + label + '"]');
  expect(t, '应有表 aria-label=' + label).toBeTruthy();
  return t as HTMLTableElement;
}
function providersTable(): HTMLTableElement {
  return tableOf(quizsSection(), 'Quizs 提供方档案');
}
function liveTable(): HTMLTableElement {
  return tableOf(quizsSection(), 'Quizs live 套');
}
function headsOf(table: Element): string[] {
  return qa(table, 'thead th').map(textOf);
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
function rowByColumn(table: Element, column: string, value: string): Record<string, Element> {
  const hit = rowsOf(table).find((r) => textOf(r[column]) === value);
  expect(hit, '应有一行 ' + column + '=' + value).toBeTruthy();
  return hit as Record<string, Element>;
}
function toneOf(cell: Element): string | null {
  const tag = cell.querySelector('[data-tone]');
  return tag ? tag.getAttribute('data-tone') : null;
}
function wrapClassOf(table: Element): string {
  const wrap = table.closest('.tt-table-wrap');
  expect(wrap, '表应在 .tt-table-wrap 滚动容器里').toBeTruthy();
  return (wrap as HTMLElement).className;
}

describe('T043 Quizs 一块：ok 情景', () => {
  it('三节都在、每个 section 带 h2、Quizs 在「就绪检查」之后；提供方档案表恰四列两行逐字；live 表恰六列两套就绪；两表容器是 rt-quizs-table 不是 rt-table', async () => {
    await mountApp('#/runtimes');
    expect(frame()!.getAttribute('data-page-state')).toBe('data');
    const r = needPageRoot();
    const titles = qa(r, 'section').map(sectionTitle);
    expect(titles.slice(0, 2)).toEqual(['已登记', '就绪检查']);
    expect(titles.indexOf('Quizs'), 'Quizs 应在「就绪检查」之后').toBeGreaterThan(titles.indexOf('就绪检查'));
    expectSectionsTitled(r);
    const pt = providersTable();
    expect(headsOf(pt), '提供方档案表恰好四列').toEqual(['提供方', '模型', '思考档位', '计费']);
    const stepfun = rowByColumn(pt, '提供方', 'stepfun');
    expect(textOf(stepfun['模型'])).toBe('step-5-preview');
    expect(textOf(stepfun['思考档位'])).toBe('low、medium、high');
    expect(textOf(stepfun['计费'])).toBe('套餐额度');
    const deepseek = rowByColumn(pt, '提供方', 'deepseek');
    expect(textOf(deepseek['模型'])).toBe('deepseek-chat');
    expect(textOf(deepseek['思考档位'])).toBe('low、high');
    expect(textOf(deepseek['计费'])).toBe('预付余额');
    expect(rowsOf(pt).length).toBe(2);
    const lt = liveTable();
    expect(headsOf(lt), 'live 套表恰好六列').toEqual(['提供方', '来源', '状态', '证书到期', '档案有效期', '下一步']);
    const mailbox = rowByColumn(lt, '来源', '信箱');
    const fromEnv = rowByColumn(lt, '来源', '环境变量');
    for (const row of [mailbox, fromEnv]) {
      expect(textOf(row['提供方'])).toBe('deepseek');
      expect(textOf(row['状态'])).toBe('就绪');
      expect(toneOf(row['状态']), '只有「就绪」是 success').toBe('success');
      expect(textOf(row['下一步'])).toBe('不用动');
    }
    expect(textOf(mailbox['证书到期']), '时刻与 formatLocalUtc 的输出一致（不写死本地时间）')
      .toBe(formatLocalUtc(new Date(1790000000000).toISOString()));
    expect(textOf(mailbox['档案有效期'])).toBe(formatLocalUtc('2026-11-20T08:00:00.000Z'));
    expect(textOf(fromEnv['证书到期'])).not.toBe('—');
    expect(textOf(fromEnv['档案有效期'])).not.toBe('—');
    for (const t of [pt, lt]) {
      expect(wrapClassOf(t)).toContain('rt-quizs-table');
      expect(wrapClassOf(t), 'Quizs 的表不加 rt-table（最后列右对齐、最小宽 900px）').not.toContain('rt-table');
    }
  });

  it('区块里没有任何按钮、没有 role=status、没有内联 style；嵌进的 section 都带 h2', async () => {
    for (const hash of ['#/runtimes', '#/runtimes?quizs=broken']) {
      await mountApp(hash);
      const sec = quizsSection();
      expect(qa(sec, 'button'), '区块里不放任何按钮（' + hash + '）').toEqual([]);
      expect(qa(sec, '[role="status"]')).toEqual([]);
      expect(qa(sec, '[style]')).toEqual([]);
      expectSectionsTitled(sec);
      cleanup();
    }
  });
});

describe('T043 Quizs 一块：expired / missing / empty 情景', () => {
  it('expired：信箱那套「已过期」（danger）、「续期后再看」；环境变量那套仍就绪；到期列是过去的毫秒数', async () => {
    await mountApp('#/runtimes?quizs=expired');
    const lt = liveTable();
    const mailbox = rowByColumn(lt, '来源', '信箱');
    expect(textOf(mailbox['状态'])).toBe('已过期');
    expect(toneOf(mailbox['状态'])).toBe('danger');
    expect(textOf(mailbox['下一步'])).toBe('续期后再看');
    expect(textOf(mailbox['证书到期'])).toBe(formatLocalUtc(new Date(1700000000000).toISOString()));
    const fromEnv = rowByColumn(lt, '来源', '环境变量');
    expect(textOf(fromEnv['状态'])).toBe('就绪');
    expect(textOf(fromEnv['下一步'])).toBe('不用动');
    expect(rowsOf(providersTable()).length, '提供方档案照常（两行）').toBe(2);
  });

  it('missing：信箱那套「缺文件」（warning）、下一步含「补齐缺的文件」与「缺 qualification.json」；环境变量那套不显示缺的文件', async () => {
    await mountApp('#/runtimes?quizs=missing');
    const lt = liveTable();
    const mailbox = rowByColumn(lt, '来源', '信箱');
    expect(textOf(mailbox['状态'])).toBe('缺文件');
    expect(toneOf(mailbox['状态'])).toBe('warning');
    expect(textOf(mailbox['下一步'])).toContain('补齐缺的文件');
    expect(textOf(mailbox['下一步'])).toContain('缺 qualification.json');
    const fromEnv = rowByColumn(lt, '来源', '环境变量');
    expect(textOf(fromEnv['下一步']), '其它状态不显示 missing 列表').not.toContain('缺 ');
  });

  it('empty：两张空态文案', async () => {
    await mountApp('#/runtimes?quizs=empty');
    const t = textOf(quizsSection());
    expect(t).toContain('还没有 Quizs 提供方档案');
    expect(t).toContain('还没有 Quizs live 套');
  });
});

describe('T043 Quizs 一块：broken 情景与错误路径', () => {
  it('broken：区块顶部「Quizs 跑不起来」+ 命令与退出码 1 + providers 的 messages 原样；live 表两套「读不出」（danger）且各自 problem 出现在表里；已登记与就绪检查照常、整页仍是 data 态', async () => {
    await mountApp('#/runtimes?quizs=broken');
    const sec = quizsSection();
    const t = textOf(sec);
    expect(t).toContain('Quizs 跑不起来');
    expect(t).toContain('命令 config quizs providers --json 返回退出码 1');
    const providersEnv = await api.getQuizsProviders();
    expect(providersEnv.ok, '替身转调真实现，此时 hash 仍是 broken').toBe(false);
    providersEnv.messages.forEach((m) => expect(t, 'messages 逐行原样').toContain(m));
    const lt = liveTable();
    const lrows = rowsOf(lt);
    expect(lrows.length).toBe(2);
    lrows.forEach((row) => {
      expect(textOf(row['状态'])).toBe('读不出');
      expect(toneOf(row['状态'])).toBe('danger');
      expect(textOf(row['下一步']), '下一步列按 v2 拼接规则写出它自己的 problem（下一步文本在前）')
        .toContain('看这一套自己的问题；quizs live status 失败（退出码 127）：');
    });
    const problem = 'quizs live status 失败（退出码 127）';
    expect(textOf(lt).match(new RegExp(problem, 'g'))?.length, '每一套都写自己的 problem').toBe(2);
    expect(sectionNamed(needPageRoot(), '已登记'), '已登记照常').toBeTruthy();
    expect(sectionNamed(needPageRoot(), '就绪检查'), '就绪检查照常').toBeTruthy();
    expect(rowsOf(tableOf(sectionNamed(needPageRoot(), '已登记')!, '已登记的 runtime')).length)
      .toBeGreaterThan(0);
    expect(frame()!.getAttribute('data-page-state'), 'Quizs 坏不影响整页').toBe('data');
  });

  it('注入 providers 失败（退出码 3、两行 messages）：只有 Quizs 一块显示失败，已登记表与就绪检查照常，整页 data', async () => {
    set('getQuizsProviders', bad(['config', 'quizs', 'providers', '--json'], 3, ['E-ONE', 'E-TWO']));
    await mountApp('#/runtimes');
    const t = textOf(quizsSection());
    expect(t).toContain('Quizs 跑不起来');
    expect(t).toContain('命令 config quizs providers --json 返回退出码 3');
    expect(t).toContain('E-ONE');
    expect(t).toContain('E-TWO');
    const lrows = rowsOf(liveTable());
    expect(lrows.map((r) => textOf(r['状态'])), 'live 表照它自己的信封显示（两套就绪）').toEqual(['就绪', '就绪']);
    expect(sectionNamed(needPageRoot(), '已登记')).toBeTruthy();
    expect(sectionNamed(needPageRoot(), '就绪检查')).toBeTruthy();
    expect(frame()!.getAttribute('data-page-state')).toBe('data');
  });

  it('注入 providers 失败且退出码 null：「没有返回退出码」的写法', async () => {
    set('getQuizsProviders', bad(['config', 'quizs', 'providers', '--json'], null, ['E-NULL']));
    await mountApp('#/runtimes');
    const t = textOf(quizsSection());
    expect(t).toContain('命令 config quizs providers --json 没有返回退出码');
    expect(t).toContain('E-NULL');
  });

  it('注入 live 失败（退出码 4）：只在 live 表位置写读失败与 messages；提供方档案照常；不出现「Quizs 跑不起来」', async () => {
    set('getQuizsLive', bad(['config', 'quizs', 'live', '--json'], 4, ['E-LIVE']));
    await mountApp('#/runtimes');
    const sec = quizsSection();
    const t = textOf(sec);
    expect(t).toContain('没能读到 Quizs 的 live 套');
    expect(t).toContain('命令 config quizs live --json 返回退出码 4');
    expect(t).toContain('E-LIVE');
    expect(t, 'providers 没坏就不写「Quizs 跑不起来」').not.toContain('Quizs 跑不起来');
    expect(rowsOf(providersTable()).length, '提供方档案表照常').toBe(2);
    expect(frame()!.getAttribute('data-page-state')).toBe('data');
  });

  it('注入 live 失败且退出码 null：「没有返回退出码」的写法', async () => {
    set('getQuizsLive', bad(['config', 'quizs', 'live', '--json'], null, ['E-LN']));
    await mountApp('#/runtimes');
    expect(textOf(quizsSection())).toContain('命令 config quizs live --json 没有返回退出码');
  });

  it('注入 runtimes 失败：整页出错（页面级错误块写命令与退出码），视图不渲染', async () => {
    set('getRuntimes', bad(['config', 'runtime', 'list'], 6, ['E-RT']));
    await mountApp('#/runtimes');
    expect(frame()!.getAttribute('data-page-state')).toBe('error');
    expect(textOf(frame())).toContain('命令（config runtime list）返回退出码 6');
    expect(pageRoot()).toBeNull();
  });
});

describe('T043 ?mock= 五态的页面状态照旧', () => {
  it('loading 挂起（三个读一起等）；error 整页出错；empty 空态下视图根照常渲染；offline 仍是 data 且 Quizs 一块照常', async () => {
    await mountApp('#/runtimes?mock=loading');
    expect(frame()!.getAttribute('data-page-state')).toBe('loading');
    expect(pageRoot()).toBeNull();
    cleanup();
    await mountApp('#/runtimes?mock=error');
    expect(frame()!.getAttribute('data-page-state')).toBe('error');
    expect(pageRoot()).toBeNull();
    cleanup();
    await mountApp('#/runtimes?mock=empty');
    expect(frame()!.getAttribute('data-page-state')).toBe('empty');
    expect(pageRoot(), '空态下视图根照常渲染（T058：空态只替换「已登记」那一节）').not.toBeNull();
    expect(quizsSection(), '空态下 Quizs 一块在视图根里').toBeTruthy();
    expect((quizsSection() as Element).closest('[data-page="runtimes"]'), '空态下 Quizs 一块在视图根里').toBe(pageRoot());
    cleanup();
    await mountApp('#/runtimes?mock=offline');
    expect(frame()!.getAttribute('data-page-state')).toBe('data');
    expect(quizsSection(), 'offline（data 带 stale）下 Quizs 一块照常').toBeTruthy();
  });
});
"""

# unit 探针：两个读函数的分支与情景、深拷贝；QuizsBlock 直挂兜底（D01、D02、D05、D07、D11）
PROBE_UNIT = PRELUDE + r"""
import * as api from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { QuizsBlock } from '../src/pages/readonly1/runtimes-QuizsBlock';

afterEach(() => {
  setLiveClientForTests(undefined);
});

function okEnv(data: any, command: string[] = ['gate']): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}
function blockOf(quizs: any): HTMLElement {
  return render(<QuizsBlock quizs={quizs} />).container;
}
function unitTable(root: ParentNode, label: string): HTMLTableElement {
  const t = root.querySelector('table[aria-label="' + label + '"]');
  expect(t, '应有表 ' + label).toBeTruthy();
  return t as HTMLTableElement;
}
function unitRows(table: Element): Array<Record<string, Element>> {
  const heads = qa(table, 'thead th').map(textOf);
  return qa(table, 'tbody tr').map((tr) => {
    const o: Record<string, Element> = {};
    qa(tr, 'td').forEach((td, i) => {
      o[heads[i] as string] = td;
    });
    return o;
  });
}
function unitRow(table: Element, column: string, value: string): Record<string, Element> {
  const hit = unitRows(table).find((r) => textOf(r[column]) === value);
  expect(hit, '应有一行 ' + column + '=' + value).toBeTruthy();
  return hit as Record<string, Element>;
}
function liveStatusRow(state: any, over: Record<string, any> = {}): any {
  return {
    source: 'mailbox',
    provider: 'deepseek',
    problem: null,
    status: { state, problem: null, missing: [], certificate: null, profile: null, ...over },
  };
}

describe('T043 api：两个 Quizs 读函数', () => {
  it('桩模式缺省 ok：providers 的命令与两行档案；live 的命令与两套就绪', async () => {
    window.location.hash = '#/runtimes';
    const p = await api.getQuizsProviders();
    expect(p.ok).toBe(true);
    expect(p.exit_code).toBe(0);
    expect(p.command).toEqual(['config', 'quizs', 'providers', '--json']);
    expect(p.data?.providers.length).toBe(2);
    expect(p.data?.providers.map((r) => r.provider)).toEqual(expect.arrayContaining(['stepfun', 'deepseek']));
    const l = await api.getQuizsLive();
    expect(l.ok).toBe(true);
    expect(l.command).toEqual(['config', 'quizs', 'live', '--json']);
    expect(l.data?.live.length).toBe(2);
    expect(l.data?.live.every((r) => r.status?.state === 'ready')).toBe(true);
  });

  it('?quizs=expired / missing / empty / 认不出的值按 ok', async () => {
    window.location.hash = '#/runtimes?quizs=expired';
    const l1 = await api.getQuizsLive();
    const expired = l1.data?.live.find((r) => r.status?.state === 'expired');
    expect(expired?.status?.certificate?.expires_at_ms).toBe(1700000000000);
    window.location.hash = '#/runtimes?quizs=missing';
    const l2 = await api.getQuizsLive();
    expect(l2.data?.live.some((r) => r.status?.state === 'missing' && r.status.missing.includes('qualification.json')))
      .toBe(true);
    window.location.hash = '#/runtimes?quizs=empty';
    const p3 = await api.getQuizsProviders();
    const l3 = await api.getQuizsLive();
    expect(p3.data?.providers).toEqual([]);
    expect(l3.data?.live).toEqual([]);
    window.location.hash = '#/runtimes?quizs=nonsense';
    const p4 = await api.getQuizsProviders();
    expect(p4.ok).toBe(true);
    expect(p4.data?.providers.length, '认不出的值按 ok').toBe(2);
  });

  it('?quizs=broken：providers 回 ok:false、退出码 1、data null、恰一行以 ERROR: 开头；live 照常 ok、每套 status null 且 problem 以 127 那句开头', async () => {
    window.location.hash = '#/runtimes?quizs=broken';
    const p = await api.getQuizsProviders();
    expect(p.ok).toBe(false);
    expect(p.exit_code).toBe(1);
    expect(p.data).toBeNull();
    expect(p.messages.length).toBe(1);
    expect(p.messages[0].startsWith('ERROR: ')).toBe(true);
    const l = await api.getQuizsLive();
    expect(l.ok).toBe(true);
    expect(l.exit_code).toBe(0);
    expect(l.data?.live.length).toBe(2);
    l.data?.live.forEach((row) => {
      expect(row.status).toBeNull();
      expect(row.problem?.startsWith('quizs live status 失败（退出码 127）：')).toBe(true);
    });
  });

  it('?mock=error 先于情景：providers 回错误信封（命令原样）；?mock=loading 挂起', async () => {
    window.location.hash = '#/runtimes?quizs=ok&mock=error';
    const p = await api.getQuizsProviders();
    expect(p.ok).toBe(false);
    expect(p.command).toEqual(['config', 'quizs', 'providers', '--json']);
    window.location.hash = '#/runtimes?quizs=ok&mock=loading';
    const marker = 'still-pending';
    const r1 = await Promise.race([api.getQuizsProviders().then(() => 'resolved'), Promise.resolve(marker)]);
    expect(r1, '?mock=loading 下读应挂起').toBe(marker);
    const r2 = await Promise.race([api.getQuizsLive().then(() => 'resolved'), Promise.resolve(marker)]);
    expect(r2).toBe(marker);
  });

  it('真实模式：GET /api/v1/quizs/providers（60 秒）与 /api/v1/quizs/live（150 秒），query 不带；服务的信封原样透传、不回落桩', async () => {
    const gets: Array<{ path: string; query: any; timeoutSeconds: number | undefined }> = [];
    const serviceEnvelope = {
      ok: false, exit_code: 7, data: null, output: [], messages: ['ERROR live-side'],
      command: ['config', 'quizs', 'live', '--json'], elapsed_ms: 0,
    };
    const fake = {
      get(path: string, query?: any, timeoutSeconds?: number) {
        gets.push({ path, query, timeoutSeconds });
        return Promise.resolve(serviceEnvelope);
      },
      post() {
        return Promise.resolve({ status: 200, body: serviceEnvelope });
      },
      getRaw() {
        return Promise.resolve({ status: 404, body: null });
      },
    } as unknown as LiveClient;
    setLiveClientForTests(fake);
    const p = await api.getQuizsProviders();
    const l = await api.getQuizsLive();
    expect(gets.length).toBe(2);
    expect(gets[0].path).toBe('/api/v1/quizs/providers');
    expect(gets[0].timeoutSeconds).toBe(60);
    expect(gets[0].query == null || Object.keys(gets[0].query).length === 0).toBe(true);
    expect(gets[1].path).toBe('/api/v1/quizs/live');
    expect(gets[1].timeoutSeconds).toBe(150);
    expect(p).toEqual(serviceEnvelope);
    expect(l, '真实分支失败也不回落桩').toEqual(serviceEnvelope);
  });

  it('桩模式每次读都给新拷贝：改上一份不影响下一份', async () => {
    window.location.hash = '#/runtimes';
    const a = await api.getQuizsProviders();
    a.data?.providers.push({ provider: 'x', model: null, thinking: [], billing: 'none_test_only' } as any);
    if (a.data) a.data.providers.forEach((r) => (r.model = 'MUTATED'));
    const b = await api.getQuizsProviders();
    expect(b.data?.providers.length).toBe(2);
    expect(b.data?.providers.some((r) => r.model === 'MUTATED'), '每次读都给新拷贝').toBe(false);
    expect(b.data?.providers.find((r) => r.provider === 'stepfun')?.model).toBe('step-5-preview');
  });
});

describe('T043 QuizsBlock 直挂：逐字表与兜底', () => {
  it('构建不一致 / 无效 / 认不出的状态：标签、色调与下一步逐字；认不出的状态不显示缺的文件', () => {
    const container = blockOf({
      providers: okEnv({ providers: [] }),
      live: okEnv({ live: [
        liveStatusRow('build_mismatch'),
        liveStatusRow('invalid'),
        Object.assign(liveStatusRow('weird'), { status: { state: 'weird', problem: null, missing: ['plan.json'], certificate: null, profile: null } }),
      ] }),
    });
    const lt = unitTable(container, 'Quizs live 套');
    const bm = unitRows(lt)[0];
    expect(textOf(bm['状态'])).toBe('构建不一致');
    expect(bm['状态'].querySelector('[data-tone]')?.getAttribute('data-tone')).toBe('warning');
    expect(textOf(bm['下一步'])).toBe('重新构建这一套');
    const inv = unitRows(lt)[1];
    expect(textOf(inv['状态'])).toBe('无效');
    expect(inv['状态'].querySelector('[data-tone]')?.getAttribute('data-tone')).toBe('danger');
    expect(textOf(inv['下一步'])).toBe('换一套能用的');
    const unk = unitRows(lt)[2];
    expect(textOf(unk['状态'])).toBe('未知');
    expect(unk['状态'].querySelector('[data-tone]')?.getAttribute('data-tone')).toBe('neutral');
    expect(textOf(unk['下一步'])).toBe('按这一套的说明处理');
    expect(textOf(unk['下一步']), '认不出的状态不显示 missing 列表').not.toContain('plan.json');
    expect(qa(container, 'button'), '区块里没有按钮').toEqual([]);
  });

  it('status 为 null 的套：「读不出」（danger）；「下一步」列 = 下一步文本；问题文字（v2 拼接规则）；provider 为 null 也不崩', () => {
    const container = blockOf({
      providers: okEnv({ providers: [{ provider: null, model: null, thinking: [], billing: 'none_test_only' }] }),
      live: okEnv({ live: [{ source: 'env', provider: null, problem: 'PP', status: null }] }),
    });
    const lt = unitTable(container, 'Quizs live 套');
    const rows = unitRows(lt);
    expect(rows.length).toBe(1);
    expect(textOf(rows[0]['状态'])).toBe('读不出');
    expect(rows[0]['状态'].querySelector('[data-tone]')?.getAttribute('data-tone')).toBe('danger');
    expect(textOf(rows[0]['下一步']), '下一步文本在前、问题文字在后，中间「；」').toBe('看这一套自己的问题；PP');
    const pt = unitTable(container, 'Quizs 提供方档案');
    expect(unitRows(pt).length, 'provider 为 null 的一行照常渲染（不崩）').toBe(1);
    expect(textOf(unitRows(pt)[0]['计费'])).toBe('仅测试');
  });

  it('「下一步」列的拼接：两个问题先 problem 后 status.problem 用「；」连，再接在下一步文本后面；只有其一时只写那一个', () => {
    const container = blockOf({
      providers: okEnv({ providers: [] }),
      live: okEnv({ live: [
        { source: 'env', provider: 'a', problem: 'P1', status: { state: 'ready', problem: 'S1', missing: [], certificate: null, profile: null } },
        { source: 'env', provider: 'b', problem: 'P2', status: { state: 'ready', problem: null, missing: [], certificate: null, profile: null } },
        { source: 'env', provider: 'c', problem: null, status: { state: 'ready', problem: 'S2', missing: [], certificate: null, profile: null } },
      ] }),
    });
    const lt = unitTable(container, 'Quizs live 套');
    expect(textOf(unitRow(lt, '提供方', 'a')['下一步']), '两个问题：problem 在前、status.problem 在后').toBe('不用动；P1；S1');
    expect(textOf(unitRow(lt, '提供方', 'b')['下一步']), '只有 problem').toBe('不用动；P2');
    expect(textOf(unitRow(lt, '提供方', 'c')['下一步']), '只有 status.problem').toBe('不用动；S2');
  });

  it('missing 的文件用「、」连接；时刻兜底：null 证书、null valid_until、不是数的毫秒、解析不了的 ISO 都显示「—」；空数组思考档位「—」', () => {
    const container = blockOf({
      providers: okEnv({ providers: [{ provider: 'x', model: 'm', thinking: [], billing: 'none_test_only' }] }),
      live: okEnv({ live: [
        liveStatusRow('missing', { missing: ['plan.json', 'profile.json'], certificate: { expires_at_ms: null }, profile: { valid_until: null } }),
        liveStatusRow('ready', { certificate: { expires_at_ms: 'not-a-number' as any }, profile: { valid_until: 'not-a-date' } }),
      ] }),
    });
    const lt = unitTable(container, 'Quizs live 套');
    const miss = unitRows(lt)[0];
    expect(textOf(miss['下一步'])).toContain('缺 plan.json、profile.json');
    expect(textOf(miss['证书到期'])).toBe('—');
    expect(textOf(miss['档案有效期'])).toBe('—');
    const rd = unitRows(lt)[1];
    expect(textOf(rd['证书到期']), '不是数的毫秒显示「—」').toBe('—');
    expect(textOf(rd['档案有效期']), '解析不了的 ISO 显示「—」').toBe('—');
    const pt = unitTable(container, 'Quizs 提供方档案');
    expect(textOf(unitRows(pt)[0]['思考档位']), '空数组思考档位显示「—」').toBe('—');
  });

  it('providers / live 信封失败：区块文案与 messages（直挂）；两个信封都坏时 live 行照自己的数据渲染', () => {
    const badProviders = { ok: false, exit_code: 1, data: null, output: [], messages: ['ERROR: gate-1'], command: ['config', 'quizs', 'providers', '--json'], elapsed_ms: 0 };
    const container = blockOf({ providers: badProviders, live: okEnv({ live: [{ source: 'env', provider: 'a', problem: 'PB', status: null }] }) });
    const t = textOf(container);
    expect(t).toContain('Quizs 跑不起来');
    expect(t).toContain('命令 config quizs providers --json 返回退出码 1');
    expect(t).toContain('ERROR: gate-1');
    const lt = unitTable(container, 'Quizs live 套');
    expect(textOf(unitRows(lt)[0]['状态']), 'providers 坏不影响 live 表').toBe('读不出');
    expect(textOf(lt)).toContain('PB');
    const container2 = blockOf({ providers: okEnv({ providers: [] }), live: { ok: false, exit_code: null, data: null, output: [], messages: ['E-L'], command: ['config', 'quizs', 'live', '--json'], elapsed_ms: 0 } });
    const t2 = textOf(container2);
    expect(t2).toContain('没能读到 Quizs 的 live 套');
    expect(t2).toContain('命令 config quizs live --json 没有返回退出码');
    expect(t2).toContain('E-L');
  });
});
"""

PROBE_SPECS = {
    "page": (PROBE_PAGE, (API_REL, RUNTIMESPAGE_REL, QUIZSBLOCK_REL, QUIZS_MOCK_REL)),
    "unit": (PROBE_UNIT, (API_REL, QUIZSBLOCK_REL, QUIZS_MOCK_REL, QUIZSLOGIC_REL)),
}
PROBE_ORDER = ("page", "unit")


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针
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


def t043_marker_present():
    """候选里 api.ts 是否已有 T043 的标记（getQuizsProviders）：没有就不起 npm（基线上必然没有）。"""
    path = REPO_ROOT / API_REL
    if not path.is_file():
        return False
    try:
        return "getQuizsProviders" in _read(path)
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
    if not t043_marker_present():
        pipe.reason = ("候选里 api.ts 还没有 T043 的标记（getQuizsProviders），没有东西可测，未调用 npm；"
                       "候选把读函数、夹具与区块接上之后，流水线才会运行 npm ci、Vitest 与探针")
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
                    name = f"probe-{uid}-t043-{key}.test.tsx"
                    probe_dir.mkdir(exist_ok=True)
                    path = probe_dir / name
                    written.append(path)
                    path.write_text(PROBE_SPECS[key][0], encoding="utf-8", newline="\n")
                    pipe.probe_files[key] = name
                    run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        else:
            pipe.stopped_reason = "npm ci（含 --offline 兜底）失败，后续步骤未运行"
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


# ---------------------------------------------------------------------------
# P 系列：流水线断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、D09：npm 依赖（已在就跳过）、npm test（全绿，含执行端两个新测试与照新行为补过参数的
    既有测试）都退出 0；依赖文件一个字节没动；gate-probe/ 没有留下。"""
    assert any(pipeline.steps.get(k) is not None and pipeline.steps[k].code == 0
               for k in ("npm ci", "npm ci --offline")), \
        f"npm ci（含 --offline 兜底）未成功：{pipeline.stopped_reason or pipeline.reason}"
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


def test_d01_d07_probe_page(pipeline):
    """page 探针 / D01–D07：五个情景（ok 的四列两行逐字与六列两套就绪、expired、missing、empty、broken）、
    区块里没有按钮/role=status/内联 style、注入 providers/live/runtimes 三种失败、?mock= 五态的页面状态、
    时刻与 formatLocalUtc 的输出一致。"""
    assert_probe_ok(pipeline, "page")


def test_d01_d11_probe_unit(pipeline):
    """unit 探针 / D01、D02、D05、D07、D11：两个读函数的桩模式命令与情景、broken 信封形状、?mock= 优先
    于情景、挂起、真实模式的路径/时限/透传、深拷贝；QuizsBlock 直挂的逐字表与兜底。"""
    assert_probe_ok(pipeline, "unit")
