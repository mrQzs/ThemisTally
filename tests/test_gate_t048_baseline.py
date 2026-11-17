"""T048 战前门禁：桌面端前端第 13 片「七端岗位」表加一列「证书」（模型配置 §6 第二条的界面一半之二、
T047 拆出来的片二）的黑盒基准测试（合同 t048-desktop-web-hub-live.v1，基线 22ca3413）。

被测对象（合同 Behavior contract）：

- ``RolesPage``：``useState`` + ``useEffect`` 单独读一次 ``getQuizsLive``（不进 ``Promise.all`` 四读、
  不改 ``load={loadRoles}``、不改前三个读的失败判定），``live`` 传给 ``RolesView``。
- ``roles-RolesView.tsx``：``RolesViewProps`` 加必填 ``live``，``<HubPosts … live={live} />`` 透传。
- ``roles-logic.ts``（只在文件末尾追加）：``matchLiveRow``、``HubCertInfo``、``hubCertInfo`` 三个导出
  （签名与行为照合同第 4、5 节），整份文件仍只 ``import type``。
- ``roles-HubPosts.tsx``：``COLUMNS`` 十列变十一列（「证书」插在「最近一回合」与「操作」之间）、
  ``HubRow`` 加 ``证书``、``HubPostsProps`` 加 ``live?``、证书格函数用 ``hubCertInfo`` +
  ``liveStateLabel``、值 import ``liveStateLabel`` 写在 ``import './roles-hub-turns.css';`` 之前。
- 包内测试：``page-hub.test.tsx`` 只改列头那一条的期望数组（十一列）；新文件 ``roles-hub-cert.test.ts``
  （纯逻辑）与 ``page-hub-cert.test.tsx``（页面）。

基线（22ca3413）上 matchLiveRow/hubCertInfo、证书列、live 单独读与新测试文件都不存在，所以本文件的
失败落在「记号不在」「文件不存在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有仓库
文件的读取都发生在用例函数里；流水线（npm、Vitest、探针）放在 ``pipeline`` 会话级夹具里（全量 pytest
默认跳过，点名运行本文件才跑；候选里还没有本片的文件时夹具不调 npm——照 T024/T040/T041/T043/T044/
T045/T047 门禁的写法）。本片不动 ts 侧，流水线没有 ts 步骤。

结构：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：RolesPage 的 live 单独读与并行四读不动（S01）；
  RolesView 透传（S02）；roles-logic 三个新导出与 import type（S03）；HubPosts 十一列与证书格（S04）；
  三份包内测试（S05）；禁改文件字节冻结与共享面（S06）。
- 流水线断言（``test_p*``/``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、npm test
  全绿；两份探针逐份写成 ``gate-probe/probe-<uid>-t048-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除。
  - unit（desktop/web）：``matchLiveRow`` 的对上/兜底/不兜底/空数组与 ``hubCertInfo`` 的逐情形
    （非 quizs、live null、信封失败、data null、live 不是数组、对不上、status null、五个 state、
    未知 state、title 取值顺序），期望值全是字面量。
  - page（desktop/web）：桩模式 ok/expired/missing/broken/empty 五个情景的证书格（Tag 文字、色调、
  title；纯文字格没有 .tt-tag）；真实模式（注入假 client）失败信封、一直挂起、带记号的行与
  「只请求一次」；hub 读失败时没有证书列头也没有证书格。

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
PAGES_RO = f"{SRC_REL}/pages/readonly1"
TESTS_REL = f"{WEB_REL}/tests"

ROLESPAGE_REL = f"{SRC_REL}/pages/RolesPage.tsx"
ROLESVIEW_REL = f"{PAGES_RO}/roles-RolesView.tsx"
HUBPOSTS_REL = f"{PAGES_RO}/roles-HubPosts.tsx"
ROLES_LOGIC_REL = f"{PAGES_RO}/roles-logic.ts"
HUB_TURNS_CSS_REL = f"{PAGES_RO}/roles-hub-turns.css"
RUNTIMES_LOGIC_REL = f"{PAGES_RO}/runtimes-quizs-logic.ts"
MOCK_QUIZS_REL = f"{SRC_REL}/mock/quizs.ts"
MOCK_HUB_ROLES_REL = f"{SRC_REL}/mock/hub-roles.ts"
API_REL = f"{SRC_REL}/api.ts"
PAGE_HUB_TEST_REL = f"{TESTS_REL}/page-hub.test.tsx"
CERT_LOGIC_TEST_REL = f"{TESTS_REL}/roles-hub-cert.test.ts"
CERT_PAGE_TEST_REL = f"{TESTS_REL}/page-hub-cert.test.tsx"

# 基线名单：src/mock 仍恰 14 份 JSON、src/pages 顶层仍恰 9 个 *Page.tsx（合同兼容性）
BASELINE_MOCK_JSON_COUNT = 14
BASELINE_PAGE_COUNT = 9

# 七端岗位的十一列（「证书」插在「最近一回合」与「操作」之间；前六列与「操作」一字不改）
HUB_HEADERS_T048 = ("岗位", "运行时", "模型", "思考档位", "来源", "替补", "时限与工具", "预算", "最近一回合", "证书", "操作")
PAGE_HUB_HEADERS_LINE_T048 = "['岗位', '运行时', '模型', '思考档位', '来源', '替补', '时限与工具', '预算', '最近一回合', '证书', '操作']"
PAGE_HUB_HEADERS_LINE_TEN = "['岗位', '运行时', '模型', '思考档位', '来源', '替补', '时限与工具', '预算', '最近一回合', '操作']"

# T009 的三页读函数白名单（:138–139 已含 getQuizsLive）：RolesPage 从 '../api' 引入的值只许是这些
ALLOWED_API_READS = ("getStatus", "getHistory", "getMeta", "getMetaNow", "getRoles", "getProfiles", "getPresets",
                     "diffPresets", "getRuntimes", "getHubRoles", "getQuizsProviders", "getQuizsLive")

# roles-logic.ts 的既有导出（一个都不许动；签名与口径由 T047 S06 逐字钉住，R01 全量跑）
OLD_LOGIC_EXPORTS = ("hubPostName", "allowedProfiles", "normalizeHubPost", "hubFallbackCandidates",
                     "hubTimeoutText", "hubBudgetText", "hubMib", "hubEffortTriple", "hubEffortDiffers",
                     "hubEffortState", "hubLastTurnText", "hubLastTurnMark", "hubFallbackExcerpt")

# RolesPage 原文（注释也算）不许出现的四个词（T038 S02 的口径，合同第 2 节）
ROLESPAGE_BAN_WORDS = ("preview", "getOperation", "usePreset", "setPluginEnabled")

# page-hub.test.tsx 既有断言的记号（合同第 7 节：只改列头那一条，其余用例与断言一个字都不许动）
PAGE_HUB_KEEP_TOKENS = (
    "describe('七端岗位（桩模式渲染 #/roles）'",
    "操作列每行两个入口：改绑定…/恢复缺省…",
    "六行的 data-post 依次是",
    "逐行核对字段格式",
    "三个新列的逐格文字",
    "位置：这一组在角色卡网格之后、profile 表之前",
    "?mock=empty 仍是六行",
    "describe('hub 读失败只影响本组'",
    "失败时不出重试钮",
    "describe('四个读并行发出'",
    "'/api/v1/hub/roles'",
)

# 执行端新测试文件的覆盖记号（合同第 7 节点名的用例与期望值，全是字面量）
CERT_LOGIC_TEST_TOKENS = (
    "matchLiveRow", "hubCertInfo", "读取中", "读不出", "没有 live 文件", "缺 qualification.json",
    "ready", "expired", "build_mismatch", "invalid", "missing",
)
CERT_PAGE_TEST_TOKENS = (
    "#/roles", "/api/v1/quizs/live", "就绪", "已过期", "缺文件", "读不出", "读取中", "没有 live 文件",
    "quizs=expired", "quizs=missing", "quizs=broken",
)

# 新源码的禁词（page-static 的口径 + T006/T009 的 matchMedia 一类，照 T047 门禁的同一张表）
FORBIDDEN_SOURCE_MARKS = (
    "XMLHttpRequest", "EventSource", "WebSocket", "dangerouslySetInnerHTML", "innerHTML", "outerHTML",
    "insertAdjacentHTML", "eval(", "new Function", "document.write", "srcdoc", "DOMParser",
    "matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver", "role=\"status\"",
)
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_COLOR_FUNCS = ("rgb(", "rgba(", "hsl(", "hsla(", "color-mix(", "oklch(", "lab(", "hwb(")

# 禁改文件的基线冻结（行尾归一 LF 后的字节数与 sha256；全部在合同 forbidden_paths 里：api.ts 与两份桩、
# runtimes-quizs-logic.ts、roles-styles.css、三份既有包内测试、两份依赖文件）
BASELINE_DIGESTS = {
    API_REL: (36065, "f12707a3f00d94355d74058053b9f9307cd01c970ef193da05f75529957e69ce"),
    MOCK_QUIZS_REL: (5806, "cc9b0720fe104902a0511414c3cd5ee37c0b6823799a66809605858b65d9f07f"),
    MOCK_HUB_ROLES_REL: (4414, "f5fe004b8e2a8f8d3c72f2d1f06b26c2a0cbff50b33480779039db57f5a0a320"),
    RUNTIMES_LOGIC_REL: (4401, "203845eaeb026767cc7f683572734caf6d691eebebcaeaf322b23e587f33347f"),
    f"{PAGES_RO}/roles-styles.css": (4282, "a81ce331e93a3ef9b06f44c76ee3c72d75c0a52f965169437bf9e9f8bd338d06"),
    f"{TESTS_REL}/roles-hub-logic.test.ts": (3724, "039a63b960171c919681cd66ac6b59583326afda6e7d861e74aee40c6dd4bf26"),
    f"{TESTS_REL}/page-app.test.tsx": (4005, "a8986dee7f02a1f43579ae8249a9f51ab0158c873e5b7525fda31edd458698e9"),
    f"{TESTS_REL}/roles-hub-turns.test.ts": (13207, "3926d74cbe24c0ff3bd9dd80d669c36f45bd998f8c51194a2a7db660ae3f6245"),
    f"{TESTS_REL}/live-api.test.ts": (23661, "70beb945988f954135fc24299bcc01bd73fe68f146d094756bb263f5b2eeb84f"),
    f"{WEB_REL}/package.json": (820, "094d3622e54097e0f50f0ab2a71a5caa22491dba9d3ac6ef83047426f8c57f5a"),
    f"{WEB_REL}/package-lock.json": (108793, "1bc4e1fbfeb02a17280d0de1d98a5f3b2721fa91229c271c66d590d059d82d28"),
}

# G01 的超时是 600s：夹具总预算压在 575s 以内，用完就停下并在断言里写明
PIPELINE_BUDGET = 575
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 150}

ASSUMPTIONS = (
    "RolesView 透传与 RolesPage 传下去的 JSX 按合同第 2、3 节逐字钉（<RolesView data={data} "
    "onDiff={diffPresets} reload={reload} live={live} /> 与 <HubPosts hub={data.hub} "
    "profiles={data.profiles.profiles} reload={reload} live={live} />，空白不敏感）：T045 S06 只钉前三个 "
    "prop，这里钉到第四个，prop 的书写次序本身是合同写死的",
    "「证书」格函数的名字合同没钉（写的是「例如 certCell(p, live)」）：静态断言只查 rows 映射里「证书: "
    "某函数(p, live)」的形状与 hubCertInfo/liveStateLabel 的接线，行为由 page 探针逐格钉住",
    "roles-logic「只在末尾追加」按位置断言：三个新导出都在基线最后一个既有导出（hubFallbackExcerpt）之后",
    "禁改文件按字节冻结（行尾归一 LF）：api.ts、两份桩、runtimes-quizs-logic.ts、roles-styles.css、三份既有"
    "包内测试与两份依赖文件——全在合同 forbidden_paths 里；page-hub.test.tsx 在允许集合里，不冻结，"
    "只钉列头那一行改成十一列与其余断言的记号",
    "流水线预算 575 秒（G01 的 600 秒减去静态用例与 pytest 自身开销）：node_modules 已在（执行端 Setup 装过）"
    "就不重装；npm ci 只在依赖不齐时跑；探针在 npm test 之后照跑（红候选也能拿到探针诊断）",
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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043/T044/T045/T047 的同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def _block(text, start_marker, end_marker="\n};"):
    start = text.find(start_marker)
    if start < 0:
        return ""
    end = text.find(end_marker, start)
    return text[start:end if end >= 0 else len(text)]


def _squish(text):
    return re.sub(r"\s+", "", text)


def _no_skip_marks(text):
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
        if re.search(bad, text):
            problems.append(f"出现 {bad}（不许 skip、only、todo）")
    return problems


def _value_imports_from(text, module):
    """从 module 引入的所有 import 语句里，不是 `import type`/内联 type 的具名值。"""
    values = []
    for stmt in re.findall(r"import\s+([^;]*?)\s*from\s*['\"]" + re.escape(module) + r"['\"]", text, re.S):
        if stmt.strip().startswith("type "):
            continue
        for name in stmt.split(","):
            name = name.strip().replace("{", "").replace("}", "").strip()
            if not name or name.startswith("type "):
                continue
            values.append(name)
    return values


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_roles_page_live_read():
    """S01 / D02：RolesPage 用 useState + useEffect 单独读一次 getQuizsLive（null 表示读取中、
    卸载后不写状态、不写 catch）；并行四读、失败判定、load={loadRoles}、页头与 children 的既有面
    一字不改；从 '../api' 引入的值只许是 T009 白名单里的读函数；四个禁词与网络词都不出现。"""
    need_file(ROLESPAGE_REL)
    text = read_rel(ROLESPAGE_REL)
    code = strip_ts_comments(text)
    squished = _squish(text)
    problems = []
    # 单独读一次 live（合同第 2 节逐字钉的写法；空白不敏感）
    if "useState<Envelope<QuizsLiveData> | null>(null)" not in code:
        problems.append("RolesPage 应写 const [live, setLive] = useState<Envelope<QuizsLiveData> | null>(null);")
    if "useEffect" not in code:
        problems.append("RolesPage 应用 useEffect 在挂载时读一次 getQuizsLive")
    for mark in ("getQuizsLive().then((env)", "if(on)setLive(env);", "on=false;", "},[]);"):
        if mark not in squished:
            problems.append(f"useEffect 应照合同第 2 节的写法（看不到记号「{mark}」：只在挂载时读一次、"
                            "卸载后不写状态；get 不 reject，不写 catch）")
    if re.search(r"\.catch\(", code):
        problems.append("getQuizsLive 不 reject（transport 一律 resolve），不应写 catch")
    # 既有面一字不改（T038 S04、T047 S10 也钉，这里在 G01 里就能红）
    if "Promise.all([getRoles(),getProfiles(),getPresets(),getHubRoles()])" not in squished:
        problems.append("RolesPage 的并行四读一字不改（getQuizsLive 不许加进 Promise.all）")
    if "[roles,profiles,presets].find((e)=>!e.ok||e.data==null)" not in squished:
        problems.append("失败判定一字不改：[roles, profiles, presets].find((e) => !e.ok || e.data == null)")
    if "load={loadRoles}" not in squished:
        problems.append("RolesPage 仍把 loadRoles 交给 PageFrame（load={loadRoles} 一字不改）")
    if "<RolesViewdata={data}onDiff={diffPresets}reload={reload}live={live}/>" not in squished:
        problems.append("children 应写 <RolesView data={data} onDiff={diffPresets} reload={reload} live={live} />")
    for token in ('description="四个角色各用哪个 CLI 与模型；方案可以一键切换"',
                  '<DisabledAction label="保存当前为方案…" />', "<NewProfileAction reload={reload} />"):
        if _squish(token) not in squished:
            problems.append(f"页头说明与两个页头按钮一字不改（看不到 {token}）")
    if "type QuizsLiveData" not in text:
        problems.append("RolesPage 应用 type QuizsLiveData 引类型（值 import 只有 getQuizsLive）")
    values = _value_imports_from(text, "../api")
    for name in values:
        if name not in ALLOWED_API_READS:
            problems.append(f"RolesPage 从 '../api' 引入的值只许是白名单里的读函数（T009）：{name}")
    if "getQuizsLive" not in values:
        problems.append("RolesPage 应值 import getQuizsLive（useState/useEffect 单独读一次）")
    for bad in ROLESPAGE_BAN_WORDS:
        if bad in text:
            problems.append(f"RolesPage 原文（注释也算）不许出现 {bad}")
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"RolesPage 不应出现 {bad}")
    if "style={{" in text:
        problems.append("RolesPage 不出现内联 style")
    fail_if(problems, "RolesPage 的 live 单独读（S01）")


def test_s02_roles_view_passthrough():
    """S02 / D02：RolesView 透传——RolesViewProps 加必填 live: Envelope<QuizsLiveData> | null；
    <HubPosts hub={data.hub} profiles={data.profiles.profiles} reload={reload} live={live} />（位置不动）；
    从 '../../api' 只 import type，类型里补 QuizsLiveData。"""
    need_file(ROLESVIEW_REL)
    text = read_rel(ROLESVIEW_REL)
    code = strip_ts_comments(text)
    squished = _squish(text)
    problems = []
    props = _block(code, "export interface RolesViewProps", "\n}")
    if not props:
        problems.append("RolesView 应保留 export interface RolesViewProps")
    else:
        if "live: Envelope<QuizsLiveData> | null;" not in props:
            problems.append("RolesViewProps 应加必填 live: Envelope<QuizsLiveData> | null;（不加问号，"
                            "null 表示读取中）")
        for decl in ("data: RolesViewData;", "reload?: () => Promise<void>;"):
            if decl not in props:
                problems.append(f"RolesViewProps 的既有 prop 一字不改（看不到 {decl.strip()}）")
        if "onDiff:" not in props:
            problems.append("RolesViewProps 的既有 onDiff 一字不改")
    if "<HubPostshub={data.hub}profiles={data.profiles.profiles}reload={reload}live={live}/>" not in squished:
        problems.append("RolesView 应写 <HubPosts hub={data.hub} profiles={data.profiles.profiles} "
                        "reload={reload} live={live} />（T045 S06 只钉前三个 prop，本片钉到 live）")
    grid_pos = code.find('className="rl-grid tt-grid-2"')
    hub_pos = code.find("<HubPosts ")
    prof_pos = code.find("<ProfilesTable ")
    if not (0 <= grid_pos < hub_pos < prof_pos):
        problems.append("HubPosts 的位置不动：角色卡网格之后、ProfilesTable 之前")
    api_imports = re.findall(r"import[^;]*?from\s*['\"]\.\./\.\./api['\"]", text, re.S)
    for stmt in api_imports:
        if not stmt.lstrip().startswith("import type"):
            problems.append(f"roles-RolesView.tsx 从 '../../api' 只许 import type：{stmt.strip()[:60]}")
    if not any("QuizsLiveData" in stmt for stmt in api_imports):
        problems.append("RolesView 的 import type 里应补 QuizsLiveData")
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"roles-RolesView.tsx 不应出现 {bad}")
    if "style={{" in text:
        problems.append("roles-RolesView.tsx 不出现内联 style")
    fail_if(problems, "RolesView 的透传（S02）")


def test_s03_roles_logic_cert_functions():
    """S03 / D06：roles-logic.ts 只在文件末尾追加——matchLiveRow（签名逐字）、HubCertInfo（四个字段
    逐字）与 hubCertInfo（签名逐字）；函数体里的口径记号（对上规则、五种纯文字、title 取值顺序）；
    既有导出一个不少、仍只 import type、类型里补 Envelope/QuizsLiveData/QuizsLiveRow。"""
    need_file(ROLES_LOGIC_REL)
    text = read_rel(ROLES_LOGIC_REL)
    code = strip_ts_comments(text)
    problems = []
    if not re.search(r"export function matchLiveRow\(\s*rows:\s*readonly QuizsLiveRow\[\],\s*"
                     r"provider:\s*string \| null\s*\):\s*QuizsLiveRow \| null", code):
        problems.append("roles-logic.ts 应导出 export function matchLiveRow(rows: readonly QuizsLiveRow[], "
                        "provider: string | null): QuizsLiveRow | null（签名逐字照合同第 4 节）")
    iface = _block(code, "export interface HubCertInfo", "\n}")
    if not iface:
        problems.append("roles-logic.ts 应导出 export interface HubCertInfo（名字逐字照合同）")
    else:
        for decl in ("text: string;", "state: string | null;", "tagged: boolean;", "title: string | null;"):
            if decl not in iface:
                problems.append(f"HubCertInfo 应有 {decl}（四个字段逐字照合同）")
    if not re.search(r"export function hubCertInfo\(\s*post:\s*HubPostInfo,\s*"
                     r"live:\s*Envelope<QuizsLiveData> \| null\s*\):\s*HubCertInfo", code):
        problems.append("roles-logic.ts 应导出 export function hubCertInfo(post: HubPostInfo, "
                        "live: Envelope<QuizsLiveData> | null): HubCertInfo（签名逐字照合同）")
    match_body = _block(code, "export function matchLiveRow", "\n}")
    if not match_body:
        problems.append("找不到 matchLiveRow 的函数体")
    else:
        for mark in ("row.provider === provider", "row.source === 'env'", "row.provider === null"):
            if mark not in match_body:
                problems.append(f"matchLiveRow 的函数体里应有记号「{mark}」（先按 provider 精确对上第一条，"
                                "再用 source==='env' 且 provider 为 null 的那条兑底）")
    cert_body = _block(code, "export function hubCertInfo", "\n}")
    if not cert_body:
        problems.append("找不到 hubCertInfo 的函数体")
    else:
        for mark in ("'读取中'", "'读不出'", "'没有 live 文件'", "'缺 '", "join('、')"):
            if mark not in cert_body:
                problems.append(f"hubCertInfo 的函数体里应有记号「{mark}」（合同第 5 节的表：读取中/读不出/"
                                "没有 live 文件；title 的「缺 」）")
        if "join('\\n')" not in cert_body:
            problems.append("hubCertInfo 的 title 应用 join('\\n') 把 messages 连起来（信封失败的「读不出」）")
        if "matchLiveRow(" not in cert_body:
            problems.append("hubCertInfo 应经 matchLiveRow 找对上的那一套")
        if "adapter !== 'quizs'" not in cert_body and "adapter === 'quizs'" not in cert_body:
            problems.append("hubCertInfo 应先看岗位的 adapter 是不是 quizs（不是就纯文字「—」）")
        if "Array.isArray" not in cert_body:
            problems.append("hubCertInfo 应判 data.live 是不是数组（不是数组按「读不出」处理）")
    # 只在末尾追加：三个新导出都在基线最后一个既有导出（hubFallbackExcerpt）之后
    last_old = code.find("export function hubFallbackExcerpt")
    if last_old >= 0:
        for marker in ("export function matchLiveRow", "export interface HubCertInfo",
                       "export function hubCertInfo"):
            pos = code.find(marker)
            if 0 <= pos < last_old:
                problems.append(f"{marker.split()[-1]} 应追加在文件末尾（基线最后一个既有导出之后），"
                                "不是插在中间")
    imports = re.findall(r"import[^;]*?from\s*['\"][^'\"]+['\"]", text)
    for stmt in imports:
        if not stmt.lstrip().startswith("import type"):
            problems.append(f"roles-logic.ts 只许 import type（T038 S07）：{stmt.strip()[:60]}")
    api_type = [stmt for stmt in imports if "../../api" in stmt]
    if not api_type or not all(t in api_type[0] for t in ("Envelope", "QuizsLiveData", "QuizsLiveRow")):
        problems.append("roles-logic.ts 的 import type 里应补 Envelope、QuizsLiveData、QuizsLiveRow（从 ../../api）")
    for name in OLD_LOGIC_EXPORTS:
        if f"export function {name}(" not in code:
            problems.append(f"既有导出 {name} 应保留（签名与行为不变）")
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"roles-logic.ts 不应出现 {bad}")
    if _HEX_COLOR.search(code) or any(fn in code for fn in _COLOR_FUNCS):
        problems.append("roles-logic.ts 不应写死颜色")
    if "liveStateLabel" in code:
        problems.append("roles-logic.ts 只许 import type，不能引 liveStateLabel（它只能在 roles-HubPosts.tsx 里调用）")
    fail_if(problems, "roles-logic.ts 的三个新导出（S03）")


def test_s04_hub_posts_cert_column():
    """S04 / D01、D04、D07：roles-HubPosts.tsx 十列变十一列（次序逐字，「证书」在「最近一回合」与
    「操作」之间）；HubRow 加证书字段、HubPostsProps 加 live?；证书格函数用 hubCertInfo + liveStateLabel
    （Tag 的文字与色调一律取 liveStateLabel(info.state)，title 透传）；值 import liveStateLabel 写在
    css import 之前；静态形状与读失败分支一个不少。"""
    need_file(HUBPOSTS_REL)
    text = read_rel(HUBPOSTS_REL)
    code = strip_ts_comments(text)
    squished = _squish(text)
    problems = []
    cols = _block(code, "const COLUMNS", "\n];")
    headers = re.findall(r"header: '([^']+)'", cols)
    if tuple(headers) != HUB_HEADERS_T048:
        problems.append(f"列头应恰为十一列 {list(HUB_HEADERS_T048)}（「证书」在「最近一回合」与「操作」之间），"
                        f"实际 {headers}")
    for col in ("岗位", "运行时", "模型", "思考档位", "来源", "替补", "操作"):
        entry = _squish(f"{{ key: '{col}', header: '{col}'")
        if entry not in squished:
            problems.append(f"前六列与「操作」列的 COLUMNS 条目一字不改（看不到 {entry}）")
    row_iface = _block(code, "interface HubRow", "\n}")
    if not row_iface:
        problems.append("roles-HubPosts.tsx 应保留 interface HubRow")
    else:
        cert_decl = [line for line in row_iface.splitlines() if "证书:" in line]
        if not cert_decl or "ReactNode" not in cert_decl[0]:
            problems.append("HubRow 应加字段 证书: ReactNode;（类型是 ReactNode）")
        p_turn = row_iface.find("最近一回合")
        p_cert = row_iface.find("证书")
        p_act = row_iface.find("操作")
        if not (0 <= p_turn < p_cert < p_act):
            problems.append("HubRow 的「证书」字段应在「最近一回合」之后、「操作」之前")
    props = _block(code, "export interface HubPostsProps", "\n}")
    if not props:
        problems.append("roles-HubPosts.tsx 应保留 export interface HubPostsProps")
    else:
        if "live?: Envelope<QuizsLiveData> | null;" not in props:
            problems.append("HubPostsProps 应加 live?: Envelope<QuizsLiveData> | null;（可空，缺省 null）")
        for decl in ("hub: Envelope<HubRolesData>;", "profiles?: ProfilesData['profiles'];",
                     "reload?: () => Promise<void>;"):
            if decl not in props:
                problems.append(f"HubPostsProps 的既有 prop 一字不改（看不到 {decl.strip()}）")
    # 值 import liveStateLabel：写在 css import 之前（站主决定；T047 S07 也查 css 之后不许再有 ./ 相对 import）
    css_pos = text.find("import './roles-hub-turns.css';")
    if css_pos < 0:
        problems.append("roles-HubPosts.tsx 应保留 import './roles-hub-turns.css'（样式表接进产品）")
    m = re.search(r"import \{ liveStateLabel \} from '\./runtimes-quizs-logic';", text)
    if not m:
        problems.append("roles-HubPosts.tsx 应加值 import：import { liveStateLabel } from './runtimes-quizs-logic';")
    elif css_pos >= 0 and m.start() > css_pos:
        problems.append("import { liveStateLabel } … 必须写在 import './roles-hub-turns.css'; 之前（站主决定）")
    # 证书格函数的接线（名字不钉，合同写的是「例如 certCell(p, live)」）
    if "hubCertInfo(" not in code:
        problems.append("证书格应经 hubCertInfo(p, live) 拿到要显示的东西")
    for mark in ("liveStateLabel(info.state).tone", "liveStateLabel(info.state).label", "info.title ?? undefined"):
        if mark not in code:
            problems.append(f"证书格的 Tag 应照合同第 6 节的写法（看不到记号「{mark}」）")
    if "{info.text}" not in code:
        problems.append("纯文字情形应渲染 <span …>{info.text}</span>")
    if not re.search(r"证书:\s*\w+\(p,\s*live", code):
        problems.append("rows 映射里「证书」列应调一个收 (p, live…) 的格函数")
    for stmt in re.findall(r"import[^;]*?from\s*['\"]\.\./\.\./api['\"]", text, re.S):
        if not stmt.lstrip().startswith("import type"):
            problems.append(f"roles-HubPosts.tsx 从 '../../api' 只许 import type：{stmt.strip()[:60]}")
    if not any("QuizsLiveData" in stmt for stmt in re.findall(r"import[^;]*?from\s*['\"]\.\./\.\./api['\"]", text, re.S)):
        problems.append("roles-HubPosts.tsx 的 import type 里应补 QuizsLiveData")
    # 静态形状与读失败分支（T038/T045/T047 的面一个不少）
    for token in ('Section title="七端岗位"', 'aria-label="七端岗位"', "rowHeight={40}",
                  "rl-table rl-hub", "hubPostName", "rowAttrs", "'data-post'", "<WriteFlow flow={flow} />",
                  "rl-hub-err", "rl-hub-msg", "没能读到七端岗位",
                  "<EffortPair requested={p.thinking} effective={null} />"):
        if token not in code:
            problems.append(f"既有静态形状应保留（看不到 {token}）")
    if "data-role" in code:
        problems.append("七端岗位一组不出现 data-role（行属性用 data-post）")
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"roles-HubPosts.tsx 不应出现 {bad}")
    if "style={{" in text:
        problems.append("roles-HubPosts.tsx 不出现内联 style")
    if _HEX_COLOR.search(code) or any(fn in code for fn in _COLOR_FUNCS):
        problems.append("roles-HubPosts.tsx 不应写死颜色")
    fail_if(problems, "roles-HubPosts.tsx 的十一列与证书格（S04）")


def test_s05_package_tests():
    """S05 / D08：page-hub.test.tsx 只改列头那一条的期望数组（十一列；旧的十列数组应已改掉），
    其余用例与断言的记号一个不少；新文件 roles-hub-cert.test.ts 与 page-hub-cert.test.tsx 在位、
    覆盖记号齐备；三份都不许 skip/only/todo。"""
    problems = []
    hub_text = read_rel(need_file(PAGE_HUB_TEST_REL))
    if PAGE_HUB_HEADERS_LINE_T048 not in hub_text:
        problems.append("page-hub.test.tsx 的列头断言应改成十一列（「证书」在「最近一回合」与「操作」之间）")
    if PAGE_HUB_HEADERS_LINE_TEN in hub_text:
        problems.append("page-hub.test.tsx 里旧的十列期望数组应已改成十一列（只改那一条）")
    for token in PAGE_HUB_KEEP_TOKENS:
        if token not in hub_text:
            problems.append(f"page-hub.test.tsx 的既有断言应照旧（看不到 {token}）")
    problems.extend("page-hub.test.tsx: " + p for p in _no_skip_marks(hub_text))
    cert_logic_text = read_rel(need_file(CERT_LOGIC_TEST_REL))
    for token in CERT_LOGIC_TEST_TOKENS:
        if token not in cert_logic_text:
            problems.append(f"roles-hub-cert.test.ts 应含记号「{token}」（合同第 7 节点名的覆盖点与字面量）")
    problems.extend("roles-hub-cert.test.ts: " + p for p in _no_skip_marks(cert_logic_text))
    cert_page_text = read_rel(need_file(CERT_PAGE_TEST_REL))
    for token in CERT_PAGE_TEST_TOKENS:
        if token not in cert_page_text:
            problems.append(f"page-hub-cert.test.tsx 应含记号「{token}」（合同第 7 节点名的覆盖点与字面量）")
    problems.extend("page-hub-cert.test.tsx: " + p for p in _no_skip_marks(cert_page_text))
    fail_if(problems, "三份包内测试（S05）")


def test_s06_shared_surfaces():
    """S06 / D10、兼容性：禁改文件字节冻结（api.ts、两份桩、runtimes-quizs-logic.ts、roles-styles.css、
    三份既有包内测试与两份依赖文件）；src/mock 仍恰 14 份 JSON、src/pages 顶层仍恰 9 个 *Page.tsx。"""
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
    fail_if(problems, "共享面与禁改面（S06）")


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 T045/T047 门禁的写法；本片不动 ts 侧，没有 ts 步骤）
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
        self.stopped_reason = ""
        self.steps = {}
        self.status_before = None
        self.status_after = None
        self.digests_before = {}
        self.digests_after = {}
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


def run_capture(argv, cwd, timeout, env=None):
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    start = time.monotonic()
    proc = subprocess.Popen(argv, cwd=str(cwd), env=env or dict(os.environ),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
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
    for name in ("QUIZS_CMD", "QUIZS_LIVE_PLAN", "QUIZS_PROVIDER_PROFILE", "QUIZS_QUALIFICATION"):
        env.pop(name, None)
    return env


def git_status_set():
    proc = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
                          cwd=REPO_ROOT, capture_output=True, timeout=120)
    assert proc.returncode == 0, f"git status 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


def t048_marker_present():
    """候选里是否已有 T048 的标记（roles-logic 的 matchLiveRow 或新页面测试文件）：没有就不起 npm（基线上必然没有）。"""
    try:
        return ("matchLiveRow" in _read(REPO_ROOT / ROLES_LOGIC_REL)
                or (REPO_ROOT / CERT_PAGE_TEST_REL).is_file())
    except OSError:
        return (REPO_ROOT / CERT_PAGE_TEST_REL).is_file()


#: 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")
PROBE_SPECS = {
    "unit": (None, (ROLES_LOGIC_REL,)),
    "page": (None, (HUBPOSTS_REL, ROLESPAGE_REL, ROLESVIEW_REL)),
}
PROBE_ORDER = ("unit", "page")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    PROBE_SPECS["unit"] = (UNIT_PROBE, PROBE_SPECS["unit"][1])
    PROBE_SPECS["page"] = (PAGE_PROBE, PROBE_SPECS["page"][1])
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t048_marker_present():
        pipe.reason = ("候选里还没有 T048 的标记（roles-logic 的 matchLiveRow 或新测试文件 page-hub-cert.test.tsx），"
                       "没有东西可测，未调用 npm；候选把纯函数、证书列与 live 单独读接上之后，流水线才会"
                       "运行 npm ci、Vitest 与探针")
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
        if not ci_ok:
            pipe.stopped_reason = "npm ci（含 --offline 兑底）失败，后续步骤未运行"
            return pipe
        # npm test 的结果照记；探针照跑（红候选也能拿到探针诊断，照 T047 的下游须知）
        run_step("npm test", [npm, "test"])
        if (WEB / "node_modules" / "vitest").is_dir():
            uid = uuid.uuid4().hex[:12]
            for key in PROBE_ORDER:
                missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                name = f"probe-{uid}-t048-{key}.test.tsx"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                written.append(path)
                path.write_text(PROBE_SPECS[key][0], encoding="utf-8", newline="\n")
                pipe.probe_files[key] = name
                run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        else:
            for key in PROBE_ORDER:
                pipe.probe_skipped[key] = "node_modules 不齐，探针未运行"
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

UNIT_PROBE = r'''// T048 门禁 unit 探针：roles-logic 的 matchLiveRow 与 hubCertInfo（合同第 4、5 节的表逐条）。
// 期望值全是字面量；不 mock 被测模块。
import { describe, expect, it } from 'vitest';
import { hubCertInfo, matchLiveRow, type HubPostInfo } from '../src/pages/readonly1/roles-logic';
import type { Envelope, QuizsLiveData, QuizsLiveRow } from '../src/api';

const row = (o: Partial<QuizsLiveRow>): QuizsLiveRow => ({ source: 'mailbox', provider: null, problem: null, status: null, ...o });
const status = (state: string | null, o: Partial<NonNullable<QuizsLiveRow['status']>> = {}): QuizsLiveRow['status'] =>
  state === null ? null : { state, problem: null, missing: [], certificate: null, profile: null, ...o } as QuizsLiveRow['status'];
const okEnv = (data: unknown): Envelope<QuizsLiveData> =>
  ({ ok: true, exit_code: 0, data, output: [], messages: [], command: [], elapsed_ms: 0 } as Envelope<QuizsLiveData>);
const failEnv = (messages: string[]): Envelope<QuizsLiveData> =>
  ({ ok: false, exit_code: 1, data: null, output: [], messages, command: ['config', 'quizs', 'live', '--json'], elapsed_ms: 0 } as Envelope<QuizsLiveData>);
const post = (adapter: string | null, provider: string | null): HubPostInfo => ({
  post: 'coordinator', source: 'default', allowedAdapters: [], adapter, provider, model: null, thinking: null,
  profile: null, runtime: null, fallback: null, turn: null, lastTurn: null,
});
const quizsPost = post('quizs', 'deepseek');

describe('matchLiveRow（合同第 4 节）', () => {
  it('provider 精确对上：取第一条 provider 相同的行（信箱在前，同名时信箱优先）', () => {
    const rows = [row({ source: 'mailbox', provider: 'deepseek' }), row({ source: 'env', provider: 'deepseek' })];
    expect(matchLiveRow(rows, 'deepseek')).toBe(rows[0]);
  });
  it('对不上时用 source===env 且 provider 为 null 的那条兑底', () => {
    const rows = [row({ source: 'mailbox', provider: 'minimax' }), row({ source: 'env', provider: null })];
    expect(matchLiveRow(rows, 'deepseek')).toBe(rows[1]);
  });
  it('env 那条 provider 不是 null 时不兑底（结果是 null）', () => {
    const rows = [row({ source: 'env', provider: 'deepseek' })];
    expect(matchLiveRow(rows, 'minimax')).toBe(null);
  });
  it('岗位 provider 为 null 时直接走 env 兑底', () => {
    const rows = [row({ source: 'mailbox', provider: 'deepseek' }), row({ source: 'env', provider: null })];
    expect(matchLiveRow(rows, null)).toBe(rows[1]);
  });
  it('rows 是空数组时 null', () => {
    expect(matchLiveRow([], 'deepseek')).toBe(null);
  });
});

describe('hubCertInfo 的纯文字情形（合同第 5 节的表）', () => {
  it('adapter 不是 quizs → 纯文字「—」，无 title', () => {
    expect(hubCertInfo(post('pi', null), okEnv({ live: [] })))
      .toEqual({ text: '—', state: null, tagged: false, title: null });
  });
  it('live 为 null（还没回来）→ 纯文字「读取中」', () => {
    expect(hubCertInfo(quizsPost, null)).toEqual({ text: '读取中', state: null, tagged: false, title: null });
  });
  it('信封 ok:false → 纯文字「读不出」，title 是 messages 用换行连起来', () => {
    expect(hubCertInfo(quizsPost, failEnv(['读不到 live', '第二行'])))
      .toEqual({ text: '读不出', state: null, tagged: false, title: '读不到 live\n第二行' });
  });
  it('messages 为空的失败信封 → 「读不出」不带 title', () => {
    expect(hubCertInfo(quizsPost, failEnv([])))
      .toEqual({ text: '读不出', state: null, tagged: false, title: null });
  });
  it('ok:true 但 data 为 null → 纯文字「读不出」', () => {
    const env = { ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0 } as unknown as Envelope<QuizsLiveData>;
    expect(hubCertInfo(quizsPost, env)).toEqual({ text: '读不出', state: null, tagged: false, title: null });
  });
  it('data.live 不是数组 → 纯文字「读不出」', () => {
    expect(hubCertInfo(quizsPost, okEnv({ live: 'x' } as unknown as QuizsLiveData)))
      .toEqual({ text: '读不出', state: null, tagged: false, title: null });
  });
  it('对不上任何一套 → 纯文字「没有 live 文件」，无 title', () => {
    expect(hubCertInfo(quizsPost, okEnv({ live: [] })))
      .toEqual({ text: '没有 live 文件', state: null, tagged: false, title: null });
  });
});

describe('hubCertInfo 的 Tag 情形（对上的那一套）', () => {
  it('status 为 null → tagged、state 为 null、title 取 row.problem', () => {
    const live = okEnv({ live: [row({ source: 'mailbox', provider: 'deepseek', problem: '某一套自己的问题' })] });
    expect(hubCertInfo(quizsPost, live))
      .toEqual({ text: '', state: null, tagged: true, title: '某一套自己的问题' });
  });
  it('五个 state 原样透传（ready/expired/build_mismatch/invalid/missing）', () => {
    for (const state of ['ready', 'expired', 'build_mismatch', 'invalid', 'missing']) {
      const live = okEnv({ live: [row({ source: 'env', provider: null, status: status(state) })] });
      const info = hubCertInfo(post('quizs', 'deepseek'), live);
      expect(info.tagged, state + ' 应是 Tag').toBe(true);
      expect(info.state, state + ' 原样透传').toBe(state);
    }
  });
  it('认不出的 state 也原样透传（色调由界面的 liveStateLabel 判）', () => {
    const live = okEnv({ live: [row({ provider: 'deepseek', status: status('weird-state') })] });
    expect(hubCertInfo(quizsPost, live)).toEqual({ text: '', state: 'weird-state', tagged: true, title: null });
  });
  it('missing 且缺文件 → title 是「缺 a.json、b.json」', () => {
    const live = okEnv({ live: [row({ provider: 'deepseek', status: status('missing', { missing: ['a.json', 'b.json'] }) })] });
    expect(hubCertInfo(quizsPost, live).title).toBe('缺 a.json、b.json');
  });
  it('title 取值顺序：row.problem → 「缺 …」 → status.problem，三个都没有则 null', () => {
    const both = okEnv({ live: [row({ provider: 'deepseek', problem: '甲', status: status('missing', { missing: ['a.json'], problem: '乙' }) })] });
    expect(hubCertInfo(quizsPost, both).title).toBe('甲');
    const onlyMissing = okEnv({ live: [row({ provider: 'deepseek', status: status('missing', { missing: ['a.json'], problem: '乙' }) })] });
    expect(hubCertInfo(quizsPost, onlyMissing).title).toBe('缺 a.json');
    const onlyStatus = okEnv({ live: [row({ provider: 'deepseek', status: status('expired', { problem: '乙' }) })] });
    expect(hubCertInfo(quizsPost, onlyStatus).title).toBe('乙');
    const none = okEnv({ live: [row({ provider: 'deepseek', status: status('ready') })] });
    expect(hubCertInfo(quizsPost, none).title).toBe(null);
  });
  it('env 兑底那一条用得上：minimax 的岗位对不上时用 env（provider null）那套', () => {
    const live = okEnv({ live: [row({ source: 'env', provider: null, status: status('expired') })] });
    expect(hubCertInfo(post('quizs', 'minimax'), live))
      .toEqual({ text: '', state: 'expired', tagged: true, title: null });
  });
});
'''


PAGE_PROBE = r'''// T048 门禁 page 探针：桩模式五个情景的证书格（Tag 文字/色调/title、纯文字格没有 .tt-tag）；
// 真实模式（注入假 client）失败信封、一直挂起、带记号的行与「只请求一次」；hub 读失败时没有证书列。
// 不用假计时器；每份探针自带全部辅助函数。
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import App from '../src/App';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { setConnectionState } from '../src/live/connection';
import type { Envelope } from '../src/api';

const HEADERS = ['岗位', '运行时', '模型', '思考档位', '来源', '替补', '时限与工具', '预算', '最近一回合', '证书', '操作'];
const POSTS = ['coordinator', 'planner', 'contract', 'gate', 'audit', 'exec'];
const NON_QUIZ = ['planner', 'gate', 'audit', 'exec'];
const LIVE_PROBLEM = 'quizs live status 失败（退出码 127）：本机 PATH 上没有 quizs';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
async function flush() {
  for (let i = 0; i < 12; i += 1) await act(async () => { await Promise.resolve(); });
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  await flush();
  render(<App />);
  await flush();
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
function cell(row: any, header: string): any {
  const hit = qa(row, 'td')[HEADERS.indexOf(header)];
  expect(hit, '应有「' + header + '」那一格').toBeTruthy();
  return hit;
}
function cert(row: any): any { return cell(row, '证书'); }
function tagIn(el: any): any { return el.querySelector('.tt-tag') || null; }

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

describe('桩模式：证书列的逐格（D01、D03、D04）', () => {
  it('列头恰是十一列，「证书」在「最近一回合」与「操作」之间；coordinator 是 Tag「就绪」（success）、contract 是纯文字「没有 live 文件」、其余四行「—」', async () => {
    await mountApp('#/roles');
    const table = hubSec().querySelector('table[aria-label="七端岗位"]');
    expect(qa(table, 'thead th').map(text), '列头是十一列').toEqual(HEADERS);
    const c = cert(hubRow('coordinator'));
    const tag = tagIn(c);
    expect(tag, 'coordinator 的证书应是 Tag').toBeTruthy();
    expect(text(tag)).toBe('就绪');
    expect(tag.getAttribute('data-tone')).toBe('success');
    const k = cert(hubRow('contract'));
    expect(text(k), 'contract 的证书是纯文字').toBe('没有 live 文件');
    expect(tagIn(k), '纯文字格没有 .tt-tag').toBe(null);
    expect(qa(k, '[title]').length, '「没有 live 文件」不带 title').toBe(0);
    for (const post of NON_QUIZ) {
      const e = cert(hubRow(post));
      expect(text(e), post + ' 非 quizs 岗位是「—」').toBe('—');
      expect(tagIn(e), post + ' 没有 Tag').toBe(null);
    }
  });
  it('?quizs=expired：coordinator 是 Tag「已过期」（danger）；contract 仍是「没有 live 文件」', async () => {
    await mountApp('#/roles?quizs=expired');
    const tag = tagIn(cert(hubRow('coordinator')));
    expect(tag, 'coordinator 应是 Tag').toBeTruthy();
    expect(text(tag)).toBe('已过期');
    expect(tag.getAttribute('data-tone')).toBe('danger');
    expect(text(cert(hubRow('contract')))).toBe('没有 live 文件');
  });
  it('?quizs=missing：coordinator 是 Tag「缺文件」（warning）且 title 是「缺 qualification.json」', async () => {
    await mountApp('#/roles?quizs=missing');
    const tag = tagIn(cert(hubRow('coordinator')));
    expect(tag, 'coordinator 应是 Tag').toBeTruthy();
    expect(text(tag)).toBe('缺文件');
    expect(tag.getAttribute('data-tone')).toBe('warning');
    expect(tag.getAttribute('title')).toBe('缺 qualification.json');
    expect(text(cert(hubRow('contract')))).toBe('没有 live 文件');
  });
  it('?quizs=broken：coordinator 是 Tag「读不出」（danger），title 是 problem 原文；contract 仍是「没有 live 文件」（站主 A2）', async () => {
    await mountApp('#/roles?quizs=broken');
    const tag = tagIn(cert(hubRow('coordinator')));
    expect(tag, 'coordinator 对上的那一套 status 为 null，应是 Tag').toBeTruthy();
    expect(text(tag)).toBe('读不出');
    expect(tag.getAttribute('data-tone')).toBe('danger');
    expect(tag.getAttribute('title')).toBe(LIVE_PROBLEM);
    expect(text(cert(hubRow('contract')))).toBe('没有 live 文件');
  });
  it('?quizs=empty：两套都没有，coordinator 与 contract 都是纯文字「没有 live 文件」', async () => {
    await mountApp('#/roles?quizs=empty');
    for (const post of ['coordinator', 'contract']) {
      const e = cert(hubRow(post));
      expect(text(e), post + ' 没有任何一套对得上').toBe('没有 live 文件');
      expect(tagIn(e)).toBe(null);
    }
  });
  it('证书格里没有可聚焦元素、没有 role 属性（D07）', async () => {
    await mountApp('#/roles');
    for (const post of POSTS) {
      const e = cert(hubRow(post));
      expect(qa(e, 'button, a, [tabindex]').length, post + ' 证书格不该有可聚焦元素').toBe(0);
      expect(qa(e, '[role]').length, post + ' 证书格不该有 role 属性').toBe(0);
    }
  });
});

// ---- 真实模式（注入假服务）----

function okEnv<T>(data: T, command: string[] = []): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}
function failEnv<T>(messages: string[]): Envelope<T> {
  return { ok: false, exit_code: 2, data: null, output: [], messages, command: ['config', 'quizs', 'live', '--json'], elapsed_ms: 0 };
}
const ROLES = { active_preset: 'default', roles: [
  { role: 'planning_review', explicit: true, binding: { mode: 'interactive_host', host: 'claude-code' }, differs_from_preset: false },
  { role: 'contract', explicit: false, binding: { mode: 'manual' }, differs_from_preset: false },
  { role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' }, differs_from_preset: false, profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, effort_effective: 'high' },
  { role: 'scheduler_agent', explicit: false, binding: { mode: 'disabled' }, differs_from_preset: false },
] };
const PRESETS = { active_preset: 'default', presets: [
  { name: 'default', description: '日常', roles: ['execution'], active: true },
] };
const REAL_PROFILES = { profiles: [
  { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: [] },
] };
const REAL_ROWS: any[] = [
  { post: 'coordinator', source: 'default', allowed_adapters: ['quizs'], adapter: 'quizs', provider: 'deepseek', model: null, thinking: 'high', profile: null, runtime: null, fallback: null },
  { post: 'planner', source: 'default', allowed_adapters: ['claude-code'], adapter: 'claude-code', provider: null, model: null, thinking: 'max', profile: null, runtime: null, fallback: null },
  { post: 'contract', source: 'config', allowed_adapters: ['pi', 'quizs'], adapter: 'quizs', provider: 'minimax', model: null, thinking: 'high', profile: 'quizs-m3', runtime: 'quizs', fallback: null },
  { post: 'gate', source: 'default', allowed_adapters: ['pi'], adapter: 'pi', provider: null, model: null, thinking: 'high', profile: null, runtime: null, fallback: null },
  { post: 'audit', source: 'default', allowed_adapters: ['pi'], adapter: 'pi', provider: null, model: null, thinking: 'max', profile: null, runtime: null, fallback: null },
  { post: 'exec', source: 'config', allowed_adapters: ['pi'], adapter: 'pi', provider: 'bb', model: null, thinking: 'high', profile: 'step-high', runtime: 'pi', fallback: null },
];
function makeFake(live: (path: string) => Promise<Envelope<unknown>>, calls: string[] = []): LiveClient {
  return {
    get<T>(path: string): Promise<Envelope<T>> {
      calls.push(path);
      if (path === '/api/v1/quizs/live') return live(path) as unknown as Promise<Envelope<T>>;
      if (path === '/api/v1/hub/roles') return Promise.resolve(okEnv({ posts: REAL_ROWS }, ['config', 'hub', 'show', '--json']) as unknown as Envelope<T>);
      if (path === '/api/v1/roles') return Promise.resolve(okEnv(ROLES) as unknown as Envelope<T>);
      if (path === '/api/v1/profiles') return Promise.resolve(okEnv(REAL_PROFILES) as unknown as Envelope<T>);
      if (path === '/api/v1/presets') return Promise.resolve(okEnv(PRESETS) as unknown as Envelope<T>);
      if (path === '/api/v1/meta') return Promise.resolve(okEnv({ version: 'pi_dispatch 1.0.0', repo_name: 'r' }) as unknown as Envelope<T>);
      return Promise.resolve(okEnv(null) as unknown as Envelope<T>);
    },
    post<T>(): Promise<{ status: number; body: Envelope<T> }> {
      return Promise.resolve({ status: 200, body: okEnv(null) as unknown as Envelope<T> });
    },
    getRaw<T>(): Promise<{ status: number; body: T }> {
      return Promise.resolve({ status: 404, body: null as unknown as T });
    },
  };
}

describe('真实模式：证书格照 live 的实况（D03、D09）', () => {
  it('失败信封 → 两个 quizs 格都是纯文字「读不出」，title 是 messages；整表六行、四张角色卡、profile 表照常，整页 data 态', async () => {
    setLiveClientForTests(makeFake(() => Promise.resolve(failEnv(['读不到 live', '第二行']))));
    await mountApp('#/roles');
    for (const post of ['coordinator', 'contract']) {
      const e = cert(hubRow(post));
      expect(text(e), post + ' 失败信封是纯文字').toBe('读不出');
      expect(tagIn(e), post + ' 没有 Tag').toBe(null);
      const titled = e.querySelector('[title]');
      expect(titled, post + ' 应带 title').toBeTruthy();
      expect(titled.getAttribute('title')).toBe('读不到 live\n第二行');
    }
    for (const post of NON_QUIZ) {
      expect(text(cert(hubRow(post))), post + ' 非 quizs 岗位仍是「—」').toBe('—');
    }
    expect(qa(hubSec(), 'tbody tr').length, '六行照常').toBe(6);
    expect(qa(document, 'article[data-role]').length, '四张角色卡照常').toBe(4);
    expect(qa(document, '[data-page-state]')[0].getAttribute('data-page-state'), '整页 data 态').toBe('data');
  });
  it('一直挂起 → 两个 quizs 格都是「读取中」，表照常渲染', async () => {
    setLiveClientForTests(makeFake(() => new Promise<Envelope<unknown>>(() => {})));
    await mountApp('#/roles');
    expect(text(cert(hubRow('coordinator')))).toBe('读取中');
    expect(text(cert(hubRow('contract')))).toBe('读取中');
    expect(qa(hubSec(), 'tbody tr').length, '六行照常').toBe(6);
  });
  it('带记号的行 → coordinator Tag「就绪」、contract（minimax）用 env 兑底是 Tag「已过期」、其余「—」；/api/v1/quizs/live 只请求一次', async () => {
    const calls: string[] = [];
    const rows = { live: [
      { source: 'mailbox', provider: 'deepseek', problem: null, status: { state: 'ready', problem: null, missing: [], certificate: null, profile: null } },
      { source: 'env', provider: null, problem: null, status: { state: 'expired', problem: null, missing: [], certificate: null, profile: null } },
    ] };
    setLiveClientForTests(makeFake(() => Promise.resolve(okEnv(rows)), calls));
    await mountApp('#/roles');
    const tagC = tagIn(cert(hubRow('coordinator')));
    expect(tagC, 'coordinator 应是 Tag').toBeTruthy();
    expect(text(tagC)).toBe('就绪');
    expect(tagC.getAttribute('data-tone')).toBe('success');
    const tagK = tagIn(cert(hubRow('contract')));
    expect(tagK, 'contract 用 env 兑底，应是 Tag').toBeTruthy();
    expect(text(tagK)).toBe('已过期');
    expect(tagK.getAttribute('data-tone')).toBe('danger');
    for (const post of NON_QUIZ) {
      expect(text(cert(hubRow(post))), post + ' 非 quizs 岗位是「—」').toBe('—');
    }
    expect(calls.filter((p) => p === '/api/v1/quizs/live').length, 'live 只在挂载时读一次').toBe(1);
  });
  it('hub 读失败 → 照旧失败块，没有「证书」列头也没有证书格；零按钮、没有 role 属性', async () => {
    const client = makeFake(() => Promise.resolve(okEnv({ live: [] })));
    const orig = client.get.bind(client);
    (client as any).get = (path: string) => path === '/api/v1/hub/roles'
      ? Promise.resolve(failEnv(['内核没有 config hub']))
      : (orig as any)(path);
    setLiveClientForTests(client);
    await mountApp('#/roles');
    const sec = hubSec();
    expect(text(sec)).toContain('没能读到七端岗位');
    expect(qa(sec, 'table').length, '失败时不出表').toBe(0);
    expect(text(sec)).not.toContain('证书');
    expect(qa(sec, 'tbody tr').length, '失败时这一组不渲染表格行').toBe(0);
    expect(qa(sec, 'button').length, '失败时不出重试钮').toBe(0);
    expect(qa(sec, '[role="status"]').length, '不用 role=status').toBe(0);
    expect(qa(document, '[data-page-state]')[0].getAttribute('data-page-state'), '整页仍是 data 态').toBe('data');
  });
});
'''


# ---------------------------------------------------------------------------
# P 系列：流水线断言；D 系列：探针断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01：npm 依赖（已在就跳过）、npm test 全绿（含改过的 page-hub 列头断言、两份新测试
    文件）；依赖文件一个字节没动；gate-probe/ 没有留下。"""
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
    """P2（守卫）：流水线与探针前后 git status 相同；探针目录没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"
    assert not (WEB / "gate-probe").exists(), "desktop/web/gate-probe 应已删除"


def test_d06_probe_unit(pipeline):
    """unit 探针 / D06：matchLiveRow 的对上/兑底/不兑底/空数组与 hubCertInfo 的逐情形（非 quizs、
    live null、信封失败、data null、live 不是数组、对不上、status null、五个 state、未知 state、
    title 取值顺序），期望值全是字面量。"""
    assert_probe_ok(pipeline, "unit")


def test_d03_probe_page(pipeline):
    """page 探针 / D03、D07：桩模式 ok/expired/missing/broken/empty 五个情景的证书格
    （Tag 文字/色调/title、纯文字格没有 .tt-tag）；真实模式失败信封、挂起、带记号的行与
    「只请求一次」；hub 读失败时没有证书列头也没有证书格。"""
    assert_probe_ok(pipeline, "page")
