"""T046 战前门禁：桌面端前端第 12 片「profile 表单接 quizs 运行时」（模型配置 M4 之六）的黑盒基准测试
（合同 t046-desktop-web-quizs-profile.v2，基线 185d077722609384f479a9b981fec6fc18ee8a68；
v2 在 v1 上把 quizs 档位的传法写死为口径 (a)「点过即算改动」）。

被测对象是 ``desktop/web/`` 前端的 profile 新建/编辑表单对话框：

- ``src/writes/quizsProfile.ts``（新，纯函数）：``QUIZS_LEVELS`` 六值 off/low/medium/high/xhigh/max（照
  ``ts/packages/ui/src/redaction.ts`` 的 ``QUIZS_THINKING_ENUM``，没有 minimal）、``QuizsProviderOption``、
  ``isQuizsRuntime``（按所选 id 找行看 adapter，不看 id 本身）、``quizsProviderOptions``（provider/model
  拼一段；非字符串、空串、``<redacted>``、过不了 ``validModel`` 的行跳过；同 value 只留第一项；档位按
  六值过滤保序去重；thinking 非数组时为空）、``thinkingLevelsFor``、``thinkingAllowed``、
  ``modelInArchive``；从 ``../api`` 只 import type，不碰 DOM/计时器/window。
- ``src/writes/ProfileForm.tsx``（改）：runtime 行留适配器；对话框打开且所选运行时是 quizs 时读一次
  ``getQuizsProviders``（非 quizs 一次都不调；迟到结果按 alive 丢弃）；模型控件三形态（档案 Select /
  读不出退回手填 TextField / 读取中与非 quizs 照旧手填）；档位 SegmentedControl 的 options 按档案给、
  从不自动改（不在范围内一个段都不选 + 提示 + 不调预览 + [确认…] 不可点）；quizs 不显示凭据输入、
  ``buildArgs`` 不交 ``credential_env``；非 quizs 分支一字不改。
- ``src/writes/profile-form.css``（改）：只在末尾追加新规则（只用 ``--tt-*`` 令牌；px 字面量带出处注释；
  新类名在组件里真的用到）。
- 新测试 ``tests/writes-profile-quizs-logic.test.ts`` 与 ``tests/writes-profile-quizs.test.tsx``；
  既有 ``tests/writes-profile-form.test.tsx`` 一个字不改。

基线（185d0777）上 quizsProfile.ts 与两个新测试不存在，ProfileForm 也没有 quizs 的接线与文案，所以本
文件的失败落在「文件不存在」「记号不在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有
仓库文件的读取都发生在用例函数里；流水线（npm、Vitest、探针）放在 ``pipeline`` 会话级夹具里（全量
pytest 默认跳过，点名运行本文件才跑；候选里还没有 T046 的标记时夹具不调 npm——基线上没有新东西可
跑，也避免联网装依赖，照 T040/T041/T043 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：quizsProfile.ts 的导出与纯度（S01）；
  ProfileForm 的接线、逐字文案与不变面（S02）；CSS 追加规则与类名接线（S03）；执行端两个新测试在位
  且要点齐备、既有 writes-profile-form.test.tsx 的钉子仍在（S04）；共享面——mock JSON 仍 14 份、
  顶层页面仍 9 个、package.json 与锁文件字节冻结、api.ts 兼容（S05）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、
  ``npm test``（全绿，含执行端两个新测试与一个字没改的既有测试）；两份探针逐份写成
  ``gate-probe/probe-<uid>-t046-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，``finally``
  里删除。探针照 ``writes-profile-form.test.tsx`` 的 ``vi.mock('../src/api')`` 转调写法（默认转调真
  实现、可注入任意信封），用 ``?quizs=`` 选情景，不 mock 被测组件；每份自带全部辅助函数，不跨文件共享
  作用域。
  - logic：quizsProfile 六个纯函数的规则（认适配器不认 id、跳过 <redacted>/非字符串/空串/过不了
    validModel、同 value 留第一项、档位六值过滤保序去重、非数组档位为空、档案外给六值）。
  - form：ok 新建（Select 两项自动选第一项、档位 low/medium/high、无手填提示、凭据说明与
    role=group、命令 --runtime=quizs-cli --model=stepfun/step-5-preview、无 --credential-env）、
    pi 下加过凭据再切 quizs（pi 段先自证命令带 --credential-env=OK_KEY，切过去后 Tag 隐藏、不上命令）、
    换档案（档位不在范围一个段都不选 + 提示 + 不调预览 + 不可点，点 high 恢复）、编辑档案外模型
    （额外第一项选中、aria-invalid、不调预览，选回档案项只传 --model）、broken（信封失败一行原文、
    退回手填与 MODEL_HELP、六段无 minimal、手填后照常预览）、empty（无可选项文案、退回手填、六值）、
    选 pi（getQuizsProviders 调用 0 次、凭据输入恰一个）、真实模式（setLiveClientForTests 注入后读
    服务回的信封，桩档案不出现）。

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
WRITES_REL = f"{SRC_REL}/writes"

PROFILEFORM_REL = f"{WRITES_REL}/ProfileForm.tsx"
PROFILE_CSS_REL = f"{WRITES_REL}/profile-form.css"
QUIZSPROFILE_REL = f"{WRITES_REL}/quizsProfile.ts"
API_REL = f"{SRC_REL}/api.ts"
MOCK_DIR_REL = f"{SRC_REL}/mock"
PAGES_DIR_REL = f"{SRC_REL}/pages"

LOGIC_TEST_REL = f"{TESTS_REL}/writes-profile-quizs-logic.test.ts"
FORM_TEST_REL = f"{TESTS_REL}/writes-profile-quizs.test.tsx"
OLD_FORM_TEST_REL = f"{TESTS_REL}/writes-profile-form.test.tsx"

# 基线名单：src/mock 恰 14 份 JSON、src/pages 顶层恰 9 个 *Page.tsx（T024 的共享面，不新增 JSON、页面）
BASELINE_MOCK_JSON_COUNT = 14
BASELINE_PAGE_COUNT = 9

# 依赖冻结（合同 D11：package.json 与锁文件不变；行尾归一为 LF 后的字节数与 sha256，值与 T043 门禁一致）
BASELINE_DIGESTS = {
    f"{WEB_REL}/package.json": (820, "094d3622e54097e0f50f0ab2a71a5caa22491dba9d3ac6ef83047426f8c57f5a"),
    f"{WEB_REL}/package-lock.json": (108793, "1bc4e1fbfeb02a17280d0de1d98a5f3b2721fa91229c271c66d590d059d82d28"),
}

# 档位的六值（合同 Repository facts：照 QUIZS_THINKING_ENUM，没有 minimal）
QUIZS_LEVELS = ("off", "low", "medium", "high", "xhigh", "max")
# 非 quizs 的七段（现状 THINKING_OPTIONS，一个字不改）
SEVEN_OPTIONS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")

# 桩档案 ok 情景的两行（src/mock/quizs.ts 的 PROVIDER_ROWS，合同 Repository facts）
OK_OPTIONS = ("stepfun/step-5-preview", "deepseek/deepseek-chat")

# quizsProfile.ts 必须导出的纯函数与类型（合同第 2 步）
QUIZSPROFILE_EXPORTS = (
    "QUIZS_LEVELS", "QuizsProviderOption", "isQuizsRuntime", "quizsProviderOptions", "thinkingLevelsFor",
    "thinkingAllowed", "modelInArchive",
)

# ProfileForm 既有逐字文案（合同兼容性：一个都不删不改；WRITES_TEXTS 的 T024 口径之外本片再钉这几个）
KEPT_FORM_TEXTS = (
    "手填的模型没有核实", "模型要写成 provider/model", "先登记 runtime", "还没有改动",
    "内核没有清空凭据变量的写法", "值在‘凭据’页录入", "新建 profile",
)
# ProfileForm 本片新增的逐字文案（合同 Behavior contract）
NEW_FORM_TEXTS = (
    "正在读 Quizs 的提供方档案…", "读不出 Quizs 的提供方档案", "Quizs 没有列出可用的提供方档案",
    "不在 Quizs 已批准的档案里", "凭据由 Quizs 保管", "不在这个档案允许的档位里",
)
# 凭据说明的外层（合同：role="group"、aria-label="凭据变量"，保留无障碍名称）
CRED_GROUP_MARK = 'aria-label="凭据变量"'

# 执行端两个新测试文件的最小覆盖记号（合同第 9、10 步）
EXECUTOR_TEST_TOKENS = {
    "writes-profile-quizs-logic.test.ts": (
        "isQuizsRuntime", "quizsProviderOptions", "thinkingLevelsFor", "thinkingAllowed", "modelInArchive",
        "<redacted>",
    ),
    "writes-profile-quizs.test.tsx": (
        "quizs-cli", "stepfun/step-5-preview", "deepseek/deepseek-chat", "quizs=", "凭据由 Quizs 保管",
        "不在 Quizs 已批准的档案里", "setLiveClientForTests", "credential", "--thinking=high",
    ),
}
# 既有 writes-profile-form.test.tsx 钉着的行为（本片一字不改；后来片要动它得先退役这里的相关断言）
OLD_FORM_TEST_PINS = (
    "['pi', 'claude-code', 'opencode']",
    "'off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'",
    "手填的模型没有核实",
)

# 颜色字面量与颜色函数（T006/T009 的口径；CSS 全文件查——基线文件本来就没有）
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_COLOR_FUNCS = ("rgb(", "rgba(", "hsl(", "hsla(", "color-mix(", "oklch(", "lab(", "hwb(")

# G01 的超时是 600s：夹具总预算压在 550s 以内（不能贴齐 600s——pytest 启动、静态用例与子进程收拾
# 的开销都在预算外，审核 O4），用完就停下并在断言里写明。
PIPELINE_BUDGET = 550
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 120}

ASSUMPTIONS = (
    "合同 v2 把 quizs 档位的传法写死为口径 (a)「点过即算改动」：用户点过档位段就一律传 --thinking=<当前档位>，"
    "即使点回初值 high 也照传；非 quizs 分支仍只传与初值不同的字段。form 探针「换档案」收尾的 --thinking=high "
    "断言按这条口径保留（审核 B3）；S04 给执行端测试加的记号 --thinking=high 也是合同第 10 步点名的用例",
    "logic 探针的 validModel 反例取值用 'p!/m' 与 'p/m!'（'!' 不在 MODEL_SEGMENT_RE 的段字符类里）："
    "'p/no-slash' 两段都合法（'-' 合法），正确实现会保留它，不能拿来当反例（审核 B1；profileRules.ts "
    "在禁改路径，本门禁不改它）",
    "「档案读到且有选项」的判定按合同原文：转出的选项数组非空才算「有档案可选」，空数组按「无可选项」"
    "（Quizs 没有列出可用的提供方档案）走——合同把它列为读不出档案的第三种情形",
    "「读不出档案」三种情形退回手填后的 thinking 七段之说是非 quizs 现状；quizs 读不出时给六值"
    "（QUIZS_LEVELS，无 minimal）——合同 Behavior contract 明写「档位给六值」",
    "读取中的门控按合同「档案不在读取中」：canPreview 对 quizs 加「不在读取中」条件，读不出（失败/无可"
    "选项）不算读取中，预览照常可用；探针只按合同钉「读取中不调预览」，不额外钉读取中的底部文案次序",
    "真实模式探针的假客户端按 desktop/web/tests/writes-runtime-api.test.ts 的 LiveClient 形状写，"
    "get 回一仓名单外的档案（qwen/qwen-max），断言它顶替桩档案出现——这同时证明「读的是服务回的信封」"
    "与「桩的 stepfun/step-5-preview 不出现」",
    "既有 writes-profile-form.test.tsx 不做字节冻结（后来片可能按自己的合同改它），改钉三条行为"
    "锚点（三运行时、七段、常显手填提示）+ 无 skip/only/todo；package.json 与锁文件按基线字节冻结"
    "（行尾归一 LF），依赖变更由每一份合同的 dependency_changes: forbidden 背书",
    "api.ts 不做字节冻结（后来片会合法地加导出），只钉本片要用的 getQuizsProviders、"
    "QuizsProviderRow/QuizsProvidersData 与 getRuntimes 仍在",
    "流水线预算 550 秒（审核 O4：不能与 G01 的 600 秒贴齐——pytest 启动、静态用例与子进程收拾的开销都"
    "在预算外）：node_modules 已在（执行端 Setup 装过）就不重装；npm ci 只在依赖不齐时跑；预算用完时"
    "未跑的步骤在断言里写明，不算夹具错",
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
    """从 start_marker 起到 end_marker 止的一段（函数体/接口/常量切片用）。"""
    start = text.find(start_marker)
    if start < 0:
        return ""
    end = text.find(end_marker, start)
    return text[start:end if end >= 0 else len(text)]


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线；基线上在这里红）
# ---------------------------------------------------------------------------

def test_s01_quizsprofile_exports():
    """S01 / D02、D03、第 2 步：quizsProfile.ts 在位，导出齐备（六值 QUIZS_LEVELS 无 minimal、六个
    纯函数与 QuizsProviderOption），从 ../api 只 import type，纯函数不碰 DOM、计时器与 window。"""
    need_file(QUIZSPROFILE_REL)
    code = read_rel(QUIZSPROFILE_REL)
    problems = []
    for name in QUIZSPROFILE_EXPORTS:
        if name not in code:
            problems.append(f"看不到导出「{name}」")
    levels = _block(code, "export const QUIZS_LEVELS")
    if not levels:
        problems.append("看不到 export const QUIZS_LEVELS")
    else:
        for value in QUIZS_LEVELS:
            if f"'{value}'" not in levels:
                problems.append(f"QUIZS_LEVELS 缺「{value}」")
        if "'minimal'" in levels:
            problems.append("QUIZS_LEVELS 不该有 minimal（QUIZS_THINKING_ENUM 六值之外）")
    # 含 ../api 的注释行不算导入：先剥注释再扫（审核 O3）
    stripped = strip_ts_comments(code)
    imports_api = [line for line in stripped.splitlines() if "../api" in line]
    if not imports_api:
        problems.append("应从 ../api import type QuizsProviderRow（档案行的类型）")
    for line in imports_api:
        if "type" not in line:
            problems.append(f"从 ../api 的导入只能是类型导入（import type 或逐项 type）：{line.strip()}")
    # 纯度：不碰 DOM、计时器与 window（quizs.ts 的桩类型导入在编译后擦除，运行时无循环）
    for mark in ("window", "document", "setTimeout", "setInterval", "requestAnimationFrame"):
        if re.search(rf"\b{mark}\b", stripped):
            problems.append(f"纯函数文件不该出现「{mark}」")
    if "from '../mock" in code or 'from "../mock' in code:
        problems.append("不该 import src/mock/*（档案信封走 getQuizsProviders）")
    fail_if(problems, "quizsProfile.ts 的导出与纯度（S01）")


def test_s02_profileform_wiring_and_texts():
    """S02 / D01、D04、D05、D07、D08：ProfileForm 接上 getQuizsProviders 与 quizsProfile 的纯函数；
    本片的逐字文案都在；既有文案与七段 THINKING_OPTIONS 一个不删；凭据说明带 role=group 的无障碍名称。"""
    need_file(PROFILEFORM_REL)
    code = read_rel(PROFILEFORM_REL)
    problems = []
    # 接线：读档案靠 getQuizsProviders（api.ts 的真函数，不 import 桩）；认 quizs 靠 quizsProfile
    if "getQuizsProviders" not in code:
        problems.append("ProfileForm 应调 getQuizsProviders（对话框打开且所选运行时是 quizs 时读一次）")
    for name in ("isQuizsRuntime", "quizsProviderOptions", "thinkingLevelsFor", "modelInArchive"):
        if name not in code:
            problems.append(f"ProfileForm 应使用 quizsProfile 的「{name}」")
    if "from '../mock" in code or 'from "../mock' in code:
        problems.append("ProfileForm 不该 import src/mock/*")
    # 本片新增的逐字文案
    for text in NEW_FORM_TEXTS:
        if text not in code:
            problems.append(f"看不到逐字文案「{text}」")
    if CRED_GROUP_MARK not in code:
        problems.append(f"凭据说明的外层应带 {CRED_GROUP_MARK}（保留无障碍名称）")
    if 'role="group"' not in code:
        problems.append("凭据说明的外层应是 role=\"group\"")
    # 既有文案与七段档位一个不删（非 quizs 分支一字不改）
    for text in KEPT_FORM_TEXTS:
        if text not in code:
            problems.append(f"既有文案「{text}」不见了（非 quizs 分支一字不改）")
    seven = _block(code, "const THINKING_OPTIONS")
    if not seven:
        problems.append("看不到 const THINKING_OPTIONS（现状七段，一个字不改）")
    else:
        for value in SEVEN_OPTIONS:
            if f"value: '{value}'" not in seven:
                problems.append(f"THINKING_OPTIONS 缺「{value}」（非 quizs 仍是七段）")
    # 认 quizs 看适配器：runtime 行要留 adapter（getRuntimes 的结果不再只存 id）
    if "adapter" not in code:
        problems.append("runtime 行应留 adapter（认 quizs 靠适配器，不靠 id）")
    # 门禁红线（T041 S06 的口径，只落在改动的这个文件上）：除「先登记 runtime」外不许有「登记 runtime」
    hits = [m.start() for m in re.finditer("登记 runtime", code)]
    stray = [i for i in hits if code[max(0, i - 1):i] != "先"]
    if stray:
        problems.append(f"除「先登记 runtime」外不许出现「登记 runtime」（T041 S06）：{len(stray)} 处")
    fail_if(problems, "ProfileForm 的接线与文案（S02）")


#: profile-form.css 基线里的全部选择器（185d0777；本片只追加，一个都不许丢）
_BASELINE_PF_SELECTORS = (
    "pf-form", "pf-field", "pf-field__label", "pf-env", "pf-env__tags", "pf-env__tag",
    "pf-env__remove", "pf-bottom", "pf-msg", "pf-msg--muted", "pf-preview", "pf-preview__cmd",
    "pf-preview__warn", "pf-preview__error",
)


def test_s03_css_appended_and_wired():
    """S03 / D10、第 8 步：profile-form.css 只追加——基线选择器都在、至少一个新选择器；只用令牌
    （无十六进制颜色、无颜色函数）；除 0/1px 外的 px 字面量所在行带出处注释；每个选择器都在
    ProfileForm 里真的用到，且样式表仍被 import（接进产品，T009 的教训）。"""
    need_file(PROFILE_CSS_REL)
    css = read_rel(PROFILE_CSS_REL)
    form = read_rel(PROFILEFORM_REL)
    problems = []
    selectors = set(re.findall(r"(?m)^\s*\.([a-z][a-z0-9_-]*)", css))
    for name in _BASELINE_PF_SELECTORS:
        if name not in selectors:
            problems.append(f"基线选择器 .{name} 不见了（只追加，不改现有规则）")
    if selectors <= set(_BASELINE_PF_SELECTORS):
        problems.append("应至少追加一个新选择器（说明行/提示行的类名，样式写进这份样式表）")
    if _HEX_COLOR.search(css):
        problems.append("样式表里不应有十六进制颜色（只用 --tt-* 令牌）")
    for fn in _COLOR_FUNCS:
        if fn in css:
            problems.append(f"样式表里不应出现颜色函数 {fn}")
    for line in css.splitlines():
        for m in re.finditer(r"(\d+(?:\.\d+)?)px", line):
            if m.group(1) in ("0", "1"):
                continue
            if "/*" not in line:
                problems.append(f"px 字面量所在行要带出处注释：{line.strip()}")
                break
    # 接线（T009 的教训）：样式表被 ProfileForm import，选择器都在组件里用到
    if "import './profile-form.css'" not in form:
        problems.append("ProfileForm 应 import './profile-form.css'（样式表要接进产品）")
    for name in sorted(selectors):
        if name not in form:
            problems.append(f"选择器 .{name} 没在 ProfileForm 里用到（新类名要在组件里真的用到）")
    fail_if(problems, "profile-form.css 的追加规则与接线（S03）")


def test_s04_executor_tests():
    """S04 / D12、第 9、10 步：执行端两个新测试文件在位、不用 skip/only/todo、带最小覆盖记号；
    既有 writes-profile-form.test.tsx 一个字没改（钉着三运行时、七段与常显手填提示，也无 skip/only/todo）。"""
    problems = []
    for rel, key in ((LOGIC_TEST_REL, "writes-profile-quizs-logic.test.ts"),
                     (FORM_TEST_REL, "writes-profile-quizs.test.tsx")):
        need_file(rel)
        code = read_rel(rel)
        for mark in (".skip", ".only", ".todo", "xit(", "xdescribe("):
            if mark in code:
                problems.append(f"{rel} 不该用「{mark}」")
        for token in EXECUTOR_TEST_TOKENS[key]:
            if token not in code:
                problems.append(f"{rel} 看不到记号「{token}」")
    need_file(OLD_FORM_TEST_REL)
    old = read_rel(OLD_FORM_TEST_REL)
    for mark in (".skip", ".only", ".todo", "xit(", "xdescribe("):
        if mark in old:
            problems.append(f"既有 {OLD_FORM_TEST_REL} 不该被改成「{mark}」")
    for pin in OLD_FORM_TEST_PINS:
        if pin not in old:
            problems.append(f"既有测试钉的行为不见了：「{pin}」（一字不改）")
    fail_if(problems, "执行端测试文件与既有钉子（S04）")


def test_s05_shared_surfaces():
    """S05 / D01、D10、D11、兼容性：mock 仍恰 14 份 JSON、顶层页面仍恰 9 个 *Page.tsx；
    package.json 与锁文件按基线字节冻结；api.ts 里本片要用的导出都在（不冻结字节，后来片可加）。"""
    problems = []
    mock_jsons = sorted(p.name for p in (REPO_ROOT / MOCK_DIR_REL).glob("*.json"))
    if len(mock_jsons) != BASELINE_MOCK_JSON_COUNT:
        problems.append(f"src/mock 应仍恰 {BASELINE_MOCK_JSON_COUNT} 份 JSON，现在 {len(mock_jsons)}：{mock_jsons}")
    pages = sorted(p.name for p in (REPO_ROOT / PAGES_DIR_REL).glob("*Page.tsx"))
    if len(pages) != BASELINE_PAGE_COUNT:
        problems.append(f"src/pages 顶层应仍恰 {BASELINE_PAGE_COUNT} 个 *Page.tsx，现在 {len(pages)}：{pages}")
    for rel, want in BASELINE_DIGESTS.items():
        got = file_digest(REPO_ROOT / rel)
        if got != want:
            problems.append(f"{rel} 应按基线字节冻结（行尾归一 LF）：{got} != {want}")
    api = read_rel(API_REL)
    for name in ("getQuizsProviders", "getRuntimes", "QuizsProviderRow", "QuizsProvidersData"):
        if name not in api:
            problems.append(f"api.ts 缺「{name}」（本片要用的数据层，T043 已合入）")
    fail_if(problems, "共享面（S05）")


# ---------------------------------------------------------------------------
# 探针（写在 desktop/web/gate-probe/ 下，各用 npm test -- <文件> 跑；每份自带全部辅助函数）
# ---------------------------------------------------------------------------

PROBE_LOGIC = r'''// T046 门禁 logic 探针：quizsProfile 六个纯函数的规则（合同第 2 步、D02、D03）。
import { describe, expect, it } from 'vitest';
import {
  QUIZS_LEVELS, isQuizsRuntime, quizsProviderOptions, thinkingLevelsFor, thinkingAllowed, modelInArchive,
  type QuizsProviderOption,
} from '../src/writes/quizsProfile';
import type { QuizsProviderRow } from '../src/api';

const ROWS = [
  { id: 'pi', adapter: 'pi' },
  { id: 'quizs-cli', adapter: 'quizs' },
];
const OK_ROWS: QuizsProviderRow[] = [
  { provider: 'stepfun', model: 'step-5-preview', thinking: ['low', 'medium', 'high'], billing: 'step_plan_credits' },
  { provider: 'deepseek', model: 'deepseek-chat', thinking: ['low', 'high'], billing: 'deepseek_prepaid_balance' },
];

describe('T046 纯逻辑：isQuizsRuntime（认适配器不认 id）', () => {
  it('所选 runtime 的 adapter 是 quizs 才算；id 叫 quizs 而 adapter 是 pi 的不算', () => {
    expect(isQuizsRuntime('quizs-cli', ROWS)).toBe(true);
    expect(isQuizsRuntime('pi', ROWS)).toBe(false);
    expect(isQuizsRuntime('quizs', [{ id: 'quizs', adapter: 'pi' }])).toBe(false);
  });
  it('列表里找不到所选 runtime 时按非 quizs 走；空列表也是 false', () => {
    expect(isQuizsRuntime('nope', ROWS)).toBe(false);
    expect(isQuizsRuntime('quizs-cli', [])).toBe(false);
  });
});

describe('T046 纯逻辑：QUIZS_LEVELS 六值无 minimal', () => {
  it('恰好 off/low/medium/high/xhigh/max', () => {
    expect([...QUIZS_LEVELS]).toEqual(['off', 'low', 'medium', 'high', 'xhigh', 'max']);
  });
});

describe('T046 纯逻辑：quizsProviderOptions（档案转选项）', () => {
  it('ok 两行：value 与 label 都是 provider/model；档位按原顺序跟随', () => {
    const options = quizsProviderOptions(OK_ROWS);
    expect(options.map((o) => o.value)).toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(options[0].label).toBe('stepfun/step-5-preview');
    expect(options[0].thinking).toEqual(['low', 'medium', 'high']);
    expect(options[1].thinking).toEqual(['low', 'high']);
  });
  it('<redacted>、null、空串与非字符串的 provider/model 不进选项', () => {
    const rows: QuizsProviderRow[] = [
      { provider: '<redacted>', model: 'm', thinking: ['low'], billing: 'b' },
      { provider: 'p', model: '<redacted>', thinking: ['low'], billing: 'b' },
      { provider: null, model: 'm', thinking: [], billing: 'b' },
      { provider: 'p', model: null, thinking: [], billing: 'b' },
      { provider: '', model: 'm', thinking: [], billing: 'b' },
      { provider: 'p', model: '', thinking: [], billing: 'b' },
    ];
    expect(quizsProviderOptions(rows)).toEqual([]);
  });
  it('拼起来过不了 validModel 的不进（provider/model 段含非法字符）', () => {
    // 取值要真过不了 MODEL_SEGMENT_RE（段内只能字母数字与 . _ : / @ + -）：'!' 不在字符类里；
    // 'p/no-slash' 这种两段都合法（'-' 合法），正确实现会保留它，不能拿来当反例（审核 B1）。
    const rows: QuizsProviderRow[] = [
      { provider: 'p!', model: 'm', thinking: [], billing: 'b' },
      { provider: 'p', model: 'm!', thinking: [], billing: 'b' },
    ];
    expect(quizsProviderOptions(rows)).toEqual([]);
  });
  it('同 value 只留第一项；档位按六值过滤、保序、去重；minimal 与枚举外的不进', () => {
    const rows: QuizsProviderRow[] = [
      { provider: 'p', model: 'm', thinking: ['high', 'low', 'high', 'bogus', 'minimal', 'off'], billing: 'b' },
      { provider: 'p', model: 'm', thinking: ['max'], billing: 'b2' },
    ];
    const options = quizsProviderOptions(rows);
    expect(options.length).toBe(1);
    expect(options[0].thinking).toEqual(['high', 'low', 'off']);
  });
  it('thinking 不是数组时档位为空，但选项仍在', () => {
    const rows = [
      { provider: 'p', model: 'm', thinking: 'low', billing: 'b' },
      { provider: 'q', model: 'n', thinking: null, billing: 'b' },
    ] as unknown as QuizsProviderRow[];
    const options = quizsProviderOptions(rows);
    expect(options.map((o) => o.value)).toEqual(['p/m', 'q/n']);
    expect(options[0].thinking).toEqual([]);
    expect(options[1].thinking).toEqual([]);
  });
});

describe('T046 纯逻辑：thinkingLevelsFor / thinkingAllowed / modelInArchive', () => {
  it('有档案项给它的档位；没有（模型不在档案里或档案不明）给六值', () => {
    const options = quizsProviderOptions(OK_ROWS);
    expect(thinkingLevelsFor(options[1])).toEqual(['low', 'high']);
    expect([...thinkingLevelsFor(null)]).toEqual(['off', 'low', 'medium', 'high', 'xhigh', 'max']);
  });
  it('档位在不在允许范围；模型在不在档案里', () => {
    const options = quizsProviderOptions(OK_ROWS);
    expect(thinkingAllowed('high', ['low', 'high'])).toBe(true);
    expect(thinkingAllowed('medium', ['low', 'high'])).toBe(false);
    expect(modelInArchive('deepseek/deepseek-chat', options)).toBe(true);
    expect(modelInArchive('stepfun/step-4', options)).toBe(false);
  });
});
'''

PROBE_FORM = r'''// T046 门禁 form 探针：ProfileForm 接 quizs 运行时的分支（合同 Behavior contract、D01、D04–D09）。
// 写法照 tests/writes-profile-form.test.tsx：vi.mock('../src/api') 的替身默认转调真实现，
// 用 ?quizs= 选情景、?write=ok 选预览；不 mock 被测组件。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const hoisted = vi.hoisted(() => ({
  spies: {} as Record<string, { mock: { calls: unknown[] }; mockClear: () => void }>,
  overrides: {} as Record<string, (...args: unknown[]) => Promise<unknown>>,
}));
vi.mock('../src/api', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  const out: Record<string, unknown> = { ...actual };
  for (const [name, fn] of Object.entries(actual)) {
    if (typeof fn === 'function') {
      const spy = vi.fn((...args: unknown[]) =>
        hoisted.overrides[name] ? hoisted.overrides[name](...args) : (fn as (...a: unknown[]) => unknown)(...args),
      );
      hoisted.spies[name] = spy;
      out[name] = spy;
    }
  }
  return out;
});

const { NewProfileAction, EditProfileAction } = await import('../src/writes/ProfileForm');

const QUIZS_PROFILE = { id: 'step-old', runtime: 'quizs-cli', provider: 'stepfun', model: 'step-4', options: { thinking: 'high' }, credential_env: ['OLD_KEY'] };
const SIX = ['off', 'low', 'medium', 'high', 'xhigh', 'max'];

function runtimesEnv(): Promise<unknown> {
  return Promise.resolve({
    ok: true, exit_code: 0,
    data: {
      runtimes: [
        { id: 'pi', adapter: 'pi', source: 'env', command: ['pi'], notes: '' },
        { id: 'quizs-cli', adapter: 'quizs', source: 'env', command: ['quizs'], notes: '' },
      ],
    },
    output: [], messages: [], command: ['config', 'runtime', 'list'], elapsed_ms: 0,
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  window.location.hash = '';
  Object.keys(hoisted.overrides).forEach((k) => delete hoisted.overrides[k]);
  Object.values(hoisted.spies).forEach((s) => s.mockClear());
  set('getRuntimes', runtimesEnv);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  window.location.hash = '';
  setLiveClientForTests(undefined);
});

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const modalDialogs = () => Array.from(document.querySelectorAll('[role="dialog"][aria-modal="true"]')) as HTMLElement[];
const hasIdLabel = (d: Element) => Array.from(d.querySelectorAll('label')).some((l) => text(l) === 'ID');
const formDialog = () => modalDialogs().find(hasIdLabel) ?? null;
const needFormDialog = () => {
  const d = formDialog();
  expect(d, '表单对话框应开着').not.toBeNull();
  return d as HTMLElement;
};
const buttonByText = (root: ParentNode, label: string) =>
  Array.from(root.querySelectorAll('button')).find((b) => text(b) === label) as HTMLButtonElement | undefined;
function controlByLabel(d: HTMLElement, labelText: string): HTMLInputElement | HTMLSelectElement {
  const label = Array.from(d.querySelectorAll('label')).find((l) => text(l) === labelText) as HTMLElement | undefined;
  expect(label, `应有 label「${labelText}」`).toBeTruthy();
  const forId = label!.getAttribute('for');
  const hit = Array.from(d.querySelectorAll('input, select')).find((el) => el.id === forId) as HTMLInputElement | HTMLSelectElement;
  expect(hit, `label 关联的控件「${labelText}」应在`).toBeTruthy();
  return hit;
}
const thinkingGroup = (d: HTMLElement) => d.querySelector('[role="radiogroup"][aria-label="thinking"]') as HTMLElement;
const segTexts = (g: HTMLElement) => Array.from(g.querySelectorAll('[role="radio"]')).map((b) => text(b as HTMLElement));
const checkedSeg = (g: HTMLElement) =>
  text(Array.from(g.querySelectorAll('[role="radio"]')).find((b) => b.getAttribute('aria-checked') === 'true') as HTMLElement);
const formConfirm = (d: HTMLElement) => buttonByText(d, '确认…') as HTMLButtonElement;
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
function set(name: string, value: (...args: unknown[]) => Promise<unknown>) {
  hoisted.overrides[name] = value;
}
const spyCalls = (name: string) => hoisted.spies[name]?.mock.calls.length ?? 0;
async function openNew() {
  render(<NewProfileAction />);
  fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
  await settle();
  return needFormDialog();
}
async function openQuizsNew(id: string) {
  const d = await openNew();
  fireEvent.change(controlByLabel(d, 'ID'), { target: { value: id } });
  fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'quizs-cli' } });
  await settle();
  return d;
}

it('ok 新建：模型是 Select 两项自动选第一项；档位 low/medium/high；无手填提示；凭据换成说明；命令带 provider/model，无 credential-env；每次打开只读一次档案', async () => {
  window.location.hash = '#/roles?write=ok&quizs=ok';
  const d = await openQuizsNew('gate-x');
  const rtOpts = Array.from((controlByLabel(d, 'runtime') as HTMLSelectElement).querySelectorAll('option')).map((o) => (o as HTMLOptionElement).value);
  expect(rtOpts, '夹具自证：运行时列表里有 quizs-cli').toEqual(['pi', 'quizs-cli']);
  const model = controlByLabel(d, '模型');
  expect(model.tagName, '有档案时模型是 Select').toBe('SELECT');
  const opts = Array.from((model as HTMLSelectElement).querySelectorAll('option')).map((o) => (o as HTMLOptionElement).value);
  expect(opts).toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
  expect((model as HTMLSelectElement).value, '新建自动选档案第一项').toBe('stepfun/step-5-preview');
  const g = thinkingGroup(d);
  expect(segTexts(g), '档位按档案给').toEqual(['low', 'medium', 'high']);
  expect(checkedSeg(g)).toBe('high');
  expect(text(d), '有档案可选时不显示手填提示').not.toContain('手填的模型没有核实');
  expect(Array.from(d.querySelectorAll('label')).some((l) => text(l) === '凭据变量'), 'quizs 不显示凭据输入框').toBe(false);
  const group = d.querySelector('[role="group"][aria-label="凭据变量"]') as HTMLElement | null;
  expect(group, '凭据说明外层是 role=group 且保留无障碍名称').toBeTruthy();
  expect(text(group)).toContain('凭据由 Quizs 保管');
  expect(buttonByText(d, '添加'), 'quizs 不显示 [添加]').toBeUndefined();
  expect(spyCalls('getQuizsProviders'), '选了 quizs 运行时读一次档案').toBe(1);
  await advance(350);
  expect(text(d), '命令带 --runtime=quizs-cli --model=<provider>/<model>').toContain('--runtime=quizs-cli --model=stepfun/step-5-preview');
  expect(text(d), 'quizs 不交 credential_env').not.toContain('--credential-env');
  fireEvent.click(buttonByText(d, '取消') as HTMLButtonElement);
  await settle();
  fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
  await settle();
  expect(spyCalls('getQuizsProviders'), '重新打开对话框会重读').toBe(2);
});

it('ok 新建：先在 pi 下加过凭据再切到 quizs，命令里没有 --credential-env（合同第 10 步场景）', async () => {
  window.location.hash = '#/roles?write=ok&quizs=ok';
  const d = await openNew();
  fireEvent.change(controlByLabel(d, 'ID'), { target: { value: 'gate-x' } });
  fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/m1' } });
  const idEl = controlByLabel(d, 'ID');
  const modelEl = controlByLabel(d, '模型');
  const env = (Array.from(d.querySelectorAll('input')) as HTMLInputElement[]).find(
    (i) => i !== idEl && i !== modelEl && i.type !== 'hidden');
  expect(env, 'pi 下凭据输入在').toBeTruthy();
  fireEvent.change(env!, { target: { value: 'OK_KEY' } });
  fireEvent.click(buttonByText(d, '添加') as HTMLButtonElement);
  await settle();
  expect(Array.from(d.querySelectorAll('.tt-tag')).map(text), '夹具自证：凭据加成了 Tag').toEqual(['OK_KEY']);
  await advance(350);
  expect(text(d), '夹具自证：pi 的命令带 --credential-env（mock 按项展开）').toContain('--runtime=pi --model=bb/m1');
  expect(text(d)).toContain('--credential-env=OK_KEY');
  fireEvent.change(modelEl, { target: { value: '' } });
  fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'quizs-cli' } });
  await settle();
  expect((controlByLabel(d, '模型') as HTMLSelectElement).value, '模型为空切到 quizs 后自动选档案第一项').toBe('stepfun/step-5-preview');
  expect(d.querySelectorAll('.tt-tag').length, 'quizs 不显示已加的凭据 Tag').toBe(0);
  await advance(350);
  expect(text(d)).toContain('--runtime=quizs-cli --model=stepfun/step-5-preview');
  expect(text(d), 'quizs 一律不交 credential_env（之前在 pi 下加的不许悄悄交上去）').not.toContain('--credential-env');
});

it('ok 换档案：新档案不含当前档位 → 一个段都不选、有提示、不调预览、不可点；点允许的档位后恢复', async () => {
  window.location.hash = '#/roles?write=ok&quizs=ok';
  const d = await openQuizsNew('gate-x');
  fireEvent.click(Array.from(thinkingGroup(d).querySelectorAll('[role="radio"]')).find((b) => text(b as HTMLElement) === 'medium') as HTMLElement);
  await settle();
  fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'deepseek/deepseek-chat' } });
  await settle();
  const g = thinkingGroup(d);
  expect(checkedSeg(g), 'medium 不在 deepseek 档案允许的档位里，一个段都不选').toBe('');
  expect(text(d)).toContain('medium 不在这个档案允许的档位里');
  await advance(1000);
  expect(spyCalls('preview'), '档位不在范围内不调预览').toBe(0);
  expect(formConfirm(d).disabled, '[确认…] 不可点').toBe(true);
  fireEvent.click(Array.from(g.querySelectorAll('[role="radio"]')).find((b) => text(b as HTMLElement) === 'high') as HTMLElement);
  await advance(350);
  // 合同 v2 写死了口径 (a)「点过即算改动」：quizs 分支里用户点过档位段就一律传
  // --thinking=<当前档位>，即使点回初值 high 也照传（审核 B3 按裁定 (a) 保留这条断言）。
  expect(text(d), '点允许的档位之后恢复，点过即算改动照传 --thinking=').toContain('--thinking=high');
  expect(formConfirm(d).disabled).toBe(false);
});

it('ok 编辑档案外模型：原值作额外第一项选中、aria-invalid、档位给六值、不调预览；选回档案项后命令只含 --model', async () => {
  window.location.hash = '#/roles?write=ok&quizs=ok';
  render(<EditProfileAction profile={QUIZS_PROFILE} />);
  fireEvent.click(buttonByText(document.body, '编辑') as HTMLButtonElement);
  await settle();
  const d = needFormDialog();
  const model = controlByLabel(d, '模型') as HTMLSelectElement;
  const opts = Array.from(model.querySelectorAll('option')).map((o) => (o as HTMLOptionElement).value);
  expect(opts, '档案外原值作额外第一项').toEqual(['stepfun/step-4', 'stepfun/step-5-preview', 'deepseek/deepseek-chat']);
  expect(model.value, '原值照样选中').toBe('stepfun/step-4');
  expect(model.getAttribute('aria-invalid'), '标「不在档案里」带 aria-invalid').toBe('true');
  expect(text(d)).toContain('不在 Quizs 已批准的档案里');
  expect(segTexts(thinkingGroup(d)), '档案不明时档位给六值').toEqual(SIX);
  expect(checkedSeg(thinkingGroup(d))).toBe('high');
  expect(d.querySelectorAll('.tt-tag').length, 'quizs 不显示凭据 Tag').toBe(0);
  await advance(1000);
  expect(spyCalls('preview'), '档案外模型不调预览').toBe(0);
  fireEvent.change(model, { target: { value: 'deepseek/deepseek-chat' } });
  await settle();
  expect(model.getAttribute('aria-invalid'), '从档案里选一项之后 error 消失').toBe(null);
  await advance(350);
  expect(text(d), '从档案里选一项之后命令只含 --model').toContain('config profile edit step-old --model=deepseek/deepseek-chat');
  expect(text(d)).not.toContain('--thinking=');
  expect(text(d), 'quizs 一律不交 credential_env').not.toContain('--credential-env');
});

it('ok 编辑档案内 profile：全都没改写「还没有改动」', async () => {
  window.location.hash = '#/roles?write=ok&quizs=ok';
  const inside = { ...QUIZS_PROFILE, provider: 'stepfun', model: 'step-5-preview' };
  render(<EditProfileAction profile={inside} />);
  fireEvent.click(buttonByText(document.body, '编辑') as HTMLButtonElement);
  await settle();
  const d = needFormDialog();
  expect((controlByLabel(d, '模型') as HTMLSelectElement).value, '档案内初值照旧选中').toBe('stepfun/step-5-preview');
  expect(segTexts(thinkingGroup(d))).toEqual(['low', 'medium', 'high']);
  expect(text(d), '全都没改写「还没有改动」').toContain('还没有改动');
});

it('broken：写明原因退回手填、常显手填提示；档位六段无 minimal；手填之后照常预览', async () => {
  window.location.hash = '#/roles?write=ok&quizs=broken';
  const d = await openQuizsNew('gate-x');
  expect(text(d), '信封失败写明原因（messages 第一行）').toContain('读不出 Quizs 的提供方档案：ERROR: 没有设置 QUIZS_CMD，读不到 Quizs 提供方档案');
  const model = controlByLabel(d, '模型');
  expect(model.tagName, '读不出档案退回手填文本框').toBe('INPUT');
  expect(text(d), '照旧提示手填').toContain('手填的模型没有核实');
  expect(segTexts(thinkingGroup(d)), '档位给六值（无 minimal）').toEqual(SIX);
  fireEvent.change(model, { target: { value: 'bb/m1' } });
  await advance(350);
  expect(text(d), '读不出档案预览照常可用').toContain('--runtime=quizs-cli --model=bb/m1');
});

it('empty：写「Quizs 没有列出可用的提供方档案」，模型退回手填、档位六值', async () => {
  window.location.hash = '#/roles?write=ok&quizs=empty';
  const d = await openQuizsNew('gate-x');
  expect(text(d)).toContain('Quizs 没有列出可用的提供方档案');
  expect(controlByLabel(d, '模型').tagName).toBe('INPUT');
  expect(segTexts(thinkingGroup(d))).toEqual(SIX);
});

it('选 pi：getQuizsProviders 调用次数 0；凭据输入仍恰一个；七段档位照旧；命令照旧', async () => {
  window.location.hash = '#/roles?write=ok&quizs=ok';
  const d = await openNew();
  fireEvent.change(controlByLabel(d, 'ID'), { target: { value: 'gate-x' } });
  fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'pi' } });
  fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/m1' } });
  await settle();
  await advance(350);
  expect(spyCalls('getQuizsProviders'), '非 quizs 一次都不调').toBe(0);
  expect(text(d)).toContain('--runtime=pi --model=bb/m1');
  expect(text(d), '非 quizs 常显手填提示').toContain('手填的模型没有核实');
  const envControls = Array.from(d.querySelectorAll('label')).filter((l) => text(l) === '凭据变量');
  expect(envControls.length, '非 quizs 凭据输入仍恰一个').toBe(1);
  expect(segTexts(thinkingGroup(d)), '非 quizs 七段照旧').toEqual(['off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']);
});

it('真实模式：注入 live 客户端后读服务回的信封，桩的档案不出现', async () => {
  const fakeClient: LiveClient = {
    get<T>(): Promise<import('../src/api').Envelope<T>> {
      return Promise.resolve({
        ok: true, exit_code: 0,
        data: { providers: [{ provider: 'qwen', model: 'qwen-max', thinking: ['high'], billing: 'qwen_credits' }] } as T,
        output: [], messages: [], command: ['config', 'quizs', 'providers', '--json'], elapsed_ms: 0,
      }) as Promise<import('../src/api').Envelope<T>>;
    },
    post<T>(): Promise<{ status: number; body: import('../src/api').Envelope<T> }> {
      return Promise.resolve({ status: 200, body: { ok: true, exit_code: 0, data: null as T, output: [], messages: [], command: [], elapsed_ms: 0 } });
    },
    getRaw<T>(): Promise<{ status: number; body: T }> {
      return Promise.resolve({ status: 404, body: null as T });
    },
  };
  setLiveClientForTests(fakeClient);
  window.location.hash = '#/roles?write=ok&quizs=ok';
  const d = await openQuizsNew('gate-x');
  const model = controlByLabel(d, '模型') as HTMLSelectElement;
  const opts = Array.from(model.querySelectorAll('option')).map((o) => (o as HTMLOptionElement).value);
  expect(opts, '读的是服务回的信封').toEqual(['qwen/qwen-max']);
  expect(opts.join(' '), '桩的档案不出现').not.toContain('stepfun/step-5-preview');
});

it('读取中：写「正在读…」，不调预览；非 quizs 分支照旧', async () => {
  window.location.hash = '#/roles?write=ok&quizs=ok';
  set('getQuizsProviders', () => new Promise(() => {}));
  const d = await openQuizsNew('gate-x');
  expect(text(d)).toContain('正在读 Quizs 的提供方档案…');
  expect(controlByLabel(d, '模型').tagName, '读取中与非 quizs 同形态手填').toBe('INPUT');
  fireEvent.change(controlByLabel(d, '模型'), { target: { value: 'bb/m1' } });
  await advance(1000);
  expect(spyCalls('preview'), '档案不在读取中才许调预览').toBe(0);
});
'''

PROBE_SPECS = {
    "logic": (PROBE_LOGIC, (QUIZSPROFILE_REL,)),
    "form": (PROBE_FORM, (QUIZSPROFILE_REL, PROFILEFORM_REL)),
}
PROBE_ORDER = ("logic", "form")


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


def t046_marker_present():
    """候选里是否有 T046 的标记（quizsProfile.ts 在位且 ProfileForm 接了 getQuizsProviders）：
    没有就不起 npm（基线上必然没有）。"""
    quizs = REPO_ROOT / QUIZSPROFILE_REL
    if not quizs.is_file():
        return False
    try:
        return "getQuizsProviders" in _read(REPO_ROOT / PROFILEFORM_REL)
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
    if not t046_marker_present():
        pipe.reason = ("候选里还没有 T046 的标记（quizsProfile.ts 或 ProfileForm 的 getQuizsProviders 接线），"
                       "没有东西可测，未调用 npm；候选把纯函数与表单接上之后，流水线才会运行 npm ci、"
                       "Vitest 与探针")
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
                    name = f"probe-{uid}-t046-{key}.test.tsx"
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


# ---------------------------------------------------------------------------
# P / D 系列：流水线断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、D12：npm 依赖（已在就跳过）、npm test（全绿，含执行端两个新测试与一个字没改的
    既有测试）都退出 0；依赖文件一个字节没动；gate-probe/ 没有留下。"""
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


def test_d02_d03_probe_logic(pipeline):
    """logic 探针 / D02、D03：认适配器不认 id；选项与档位的规则（<redacted>/非字符串/空串/
    validModel 不让进、同 value 留第一项、六值过滤保序去重、非数组档位为空、档案外给六值）。"""
    assert_probe_ok(pipeline, "logic")


def test_d01_d04_d09_probe_form(pipeline):
    """form 探针 / D01、D04–D09：ok 新建与换档案、编辑档案内外模型、broken、empty、选 pi 零调用、
    真实模式读服务回的信封、读取中不调预览。"""
    assert_probe_ok(pipeline, "form")
