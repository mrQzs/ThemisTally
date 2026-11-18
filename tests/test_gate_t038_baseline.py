"""T038 战前门禁：桌面端前端第 5 片——「角色与模型」页加只读的「七端岗位」一组（模型配置 M4 之一）的
黑盒基准测试（合同 t038-desktop-web-hub-posts.v1，基线 e390582d）。

被测对象是 ``desktop/web/``：``src/api.ts`` 新增读函数 ``getHubRoles``（真实模式 ``GET /api/v1/hub/roles``、
时限 30 秒、不回落桩；桩模式 ``config hub show --json``）、新桩 ``src/mock/hub-roles.ts``（六行名册）、
``RolesPage`` 的 ``loadRoles`` 并行读四个（hub 的信封整个放进 ``RolesViewData.hub``，不参与整页失败判定）、
新视图 ``readonly1/roles-HubPosts.tsx``（六行只读表：岗位、运行时、模型、思考档位、来源、替补）、
``components/Table.tsx`` 的加法式 prop ``rowAttrs``、``roles-logic.ts`` 的三个纯函数、
``roles-styles.css`` 追加样式，以及执行端测试 ``live-api.test.ts``（只加一行）与两份新测试。

基线（e390582d）上这些都不存在，所以本文件的失败落在「文件不在」「记号不在」「导出不在」上，不是导入、收集
或语法错误：模块级只导入标准库，所有仓库文件的读取都发生在用例函数里；流水线（npm、Vitest、探针）放在
``pipeline`` 会话级夹具里（全量 pytest 默认跳过，点名运行本文件才跑；候选里还没有本片的新源码文件时，
夹具不调 npm——基线上没有东西可测，也避免联网装依赖）。

结构：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：新文件在位与夹具数量约定（S01）；api.ts 的
  ``getHubRoles`` 形状、类型导出与既有导出保全（S02）；桩文件只做纯类型导入（S03）；RolesPage 的并行四读、
  失败顺序与禁词（S04）；RolesViewData 的 hub 字段与渲染位置（S05）；Table 的 ``rowAttrs``（S06）；
  roles-logic 的三个纯函数（S07）；roles-styles.css 只追加且令牌/px 规矩（S08）；执行端测试在位
  （live-api 加一行、两份新测试不用 skip）（S09）；roles-HubPosts 的静态形状（S10）。
- 流水线断言（``test_p*``，``pipeline`` 夹具）：npm 依赖（已在就跳过重装）、npm test、npm run build；
  探针逐份写成 ``gate-probe/probe-<uid>-t038-<键>.test.ts``，各用 ``npm test -- gate-probe/<文件名>`` 跑，
  ``finally`` 里删除。探针不写 JSX（React.createElement），自带全部辅助函数，不跨文件共享作用域。
  - lib：桩的六行逐字段等于合同；三个纯函数的边界（hubPostName、allowedProfiles、normalizeHubPost）。
  - page：挂载整个 App（vi.mock 替换 api.ts 的读函数，注入任意信封）——区块与表结构、六行字段格式、
    hub 读失败只影响本组、四个读并行与前三个读的失败顺序、``?mock=empty`` 仍是六行、真实模式的
    getHubRoles（路径/时限/错误信封原样透传、成功不换桩）。
  - trans（过渡）：列头恰好六列没有「操作」、整组没有按钮——站主 2026-11-15 为 T045（“七端岗位”一组加“改绑定…”“恢复缺省…”）退役。

门禁做不到、留给人的项：视觉对照（暗/亮主题、窄窗口）、悬停手感、读屏、真浏览器里的点击与导航。

合同没写死、门禁端按最合理读法定下的地方（见 ``ASSUMPTIONS``，交付信「下游须知」里也写）。

合同事实（门禁自守）：``ALLOWED_API_READS``（T009）已含 ``getHubRoles``；七端岗位的行用 ``data-post``
（不占 ``article[data-role]``）；标题「七端岗位」不含「profile」「方案」，不会被按标题选区块的探针误选。
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
WEB_REL = "desktop/web"
WEB = REPO_ROOT / "desktop" / "web"
SRC_REL = f"{WEB_REL}/src"
SRC = WEB / "src"
RO_REL = f"{SRC_REL}/pages/readonly1"
TESTS_REL = f"{WEB_REL}/tests"

API_REL = f"{SRC_REL}/api.ts"
ROLES_PAGE_REL = f"{SRC_REL}/pages/RolesPage.tsx"
ROLES_VIEW_REL = f"{RO_REL}/roles-RolesView.tsx"
ROLES_LOGIC_REL = f"{RO_REL}/roles-logic.ts"
ROLES_CSS_REL = f"{RO_REL}/roles-styles.css"
TABLE_REL = f"{SRC_REL}/components/Table.tsx"
HUB_MOCK_REL = f"{SRC_REL}/mock/hub-roles.ts"
HUB_POSTS_REL = f"{RO_REL}/roles-HubPosts.tsx"
LIVE_API_TEST_REL = f"{TESTS_REL}/live-api.test.ts"
PAGE_HUB_TEST_REL = f"{TESTS_REL}/page-hub.test.tsx"
ROLES_HUB_LOGIC_TEST_REL = f"{TESTS_REL}/roles-hub-logic.test.ts"
NEW_SOURCE_FILES = (HUB_MOCK_REL, HUB_POSTS_REL)
NEW_TEST_FILES = (PAGE_HUB_TEST_REL, ROLES_HUB_LOGIC_TEST_REL)

ASSUMPTIONS = (
    "roles-styles.css 追加的 .rl-hub 规则按合同第 9 步的「建议」核对（.rl-hub 与 .tt-table 同一条规则、min-width 760px）："
    "建议是合理缺省，执行端要换写法就走「偏离」渠道",
    "hub 读失败时这一组不渲染表格行、失败命令在整页只出现一次：合同写了「这一组显示失败信封」，替换语义按 ConfigChanges 的写法读",
    "allowedProfiles 的结果顺序按输入顺序（filter 语义）：合同没写顺序，探针的数据按输入顺序断言",
    "normalizeHubPost 的字段名按合同第 8 步写的（post、source、allowedAdapters、adapter、provider、model、thinking、profile、runtime、fallback）",
    "桩六行照合同 v3 第 3 步逐行写出的原文（只写真内核交得出的形状）：coordinator 的替补恰四个键"
    "（adapter、provider、model、thinking，不写 profile、不写 runtime），contract 配置行的主绑定在 quizs 上"
    "（profile 是 quizs-m3）、替补六个键；toStrictEqual 逐字段核对、多键少键都算不对；"
    "桩与页面文字不出现 profiles.json 里档位为 low 的那条 profile 的 id（D11：T009 的 D09 拿它当晚到回应独有的串）",
)

# 基线事实（e390582d 上核对）
# roles-styles.css 的基线前缀（行尾归一 LF 的字节数与 sha256）：证明本片「只加不改」
ROLES_CSS_BASELINE = (3779, "952a5d3871ffa697397132c59613060a688a628e078cd82a3a0ed1c19accf138")
# api.ts 的基线导出（一个都不许丢；按包含不卡恰好，本片新增 HubPostRow/HubPostFallback/HubRolesData/getHubRoles）
API_EXPORT_BASELINE = frozenset({
    "getMeta", "getStatus", "getAttempt", "readFile", "getRoles", "getProfiles", "getPresets",
    "diffPresets", "getRuntimes", "getPlugins", "getHistory", "getUsage", "listSecrets",
    "getHistoryEntry", "getPlugin", "getMetaNow", "preview", "getOperation", "usePreset",
    "setPluginEnabled", "removePreset", "removeProfile", "removeRuntime", "rollback", "addProfile",
    "editProfile", "setHubRole", "unsetHubRole", "Envelope", "HttpReply", "BindingChange", "PreviewData",
    "OperationView", "WriteAction", "WriteArgs", "MetaData", "StatusRow", "StatusData", "AttemptData",
    "FileData", "RolesData", "ProfilesData", "PresetsData", "PresetDiffData", "RuntimesData", "PluginsData",
    "HistoryData", "UsageData", "SecretsData",
})
API_NEW_EXPORTS = ("HubPostRow", "HubPostFallback", "HubRolesData", "getHubRoles")
# live-api.test.ts 里本就该在的读函数名（T037 基线 16 个）+ 本片新增 getHubRoles
API_READ_NAMES = (
    "getMeta", "getStatus", "getAttempt", "readFile", "getRoles", "getProfiles", "getPresets",
    "diffPresets", "getRuntimes", "getPlugins", "getHistory", "getUsage", "listSecrets",
    "getHistoryEntry", "getPlugin", "getMetaNow", "getHubRoles",
)
# RolesPage 的页头说明（一字不改）与两个页头按钮之一；四个禁词（T024 S07）
PAGE_DESC = "四个角色各用哪个 CLI 与模型；方案可以一键切换"
PAGE_HEAD_DISABLED = 'PresetSaveAction'
ROLES_PAGE_FORBIDDEN = ("preview", "getOperation", "usePreset", "setPluginEnabled")
# 仓库约定：src/mock 恰 14 份 JSON（桩只能是 .ts）；src/pages 顶层恰 9 个 *Page.tsx
MOCK_JSON_COUNT = 14
PAGES_TSX_COUNT = 9
# 合同第 3 步的六行桩（lib 探针逐字段核对的期望值，也供静态自检）
HUB_POST_CODES = ("coordinator", "planner", "contract", "gate", "audit", "exec")

# 四个浏览器网络词与 T007 禁用词（拼接写出，使本文件与探针源码自己不含这些词）
NET_WORDS = ("".join(("fe", "tch")), "".join(("XMLHttp", "Request")), "".join(("Event", "Source")),
             "".join(("Web", "Socket")))
SINK_WORDS = ("".join(("dangerously", "SetInner", "HTML")), "".join(("inner", "HTML")),
              "".join(("outer", "HTML")), "".join(("insertAdjacent", "HTML")), "".join(("ev", "al(")),
              "".join(("new ", "Function")), "".join(("document", ".write")), "".join(("src", "doc")),
              "".join(("createContextual", "Fragment")), "".join(("DOM", "Parser")))

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def need_file(rel):
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return path


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:40])


def tail_text(text, max_chars=3500, max_lines=45):
    text = _ANSI.sub("", text)
    lines = text.splitlines()[-max_lines:]
    return "\n".join(lines)[-max_chars:]


def network_hint(text):
    if re.search(r"ENOTFOUND|ETIMEDOUT|ECONNRESET|ECONNREFUSED|EAI_AGAIN|ENETUNREACH|network|socket hang up|E40[134]|E50\d",
                 text, re.I):
        return "（输出里有网络或 registry 错误的迹象，多半是网络故障，不是代码问题）"
    return ""


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def collapse(text):
    """去掉全部空白（比对代码形状用；字符串字面量另用原文比对）。"""
    return re.sub(r"\s+", "", text)


def sha_prefix_ok(data, size, digest):
    return len(data) >= size and hashlib.sha256(data[:size]).hexdigest() == digest


def file_digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def git(*args, check=False):
    proc = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, timeout=120)
    if check:
        assert proc.returncode == 0, f"git {' '.join(args)} 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return proc


def git_status_set():
    proc = git("status", "--porcelain=v1", "--untracked-files=all", "-z", check=True)
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


def exported_names(code):
    names = set(re.findall(r"\bexport\s+(?:async\s+)?(?:function|const|let|var|interface|type|class)\s+"
                           r"([A-Za-z_$][\w$]*)", code))
    for body in re.findall(r"\bexport\s*\{([^}]*)\}", code):
        for part in body.split(","):
            part = part.strip()
            if part:
                names.add(re.split(r"\s+as\s+", part)[-1].strip())
    return names


def value_import_problems(text, spec, label):
    """从 spec 引入的 import 必须都是 import type（视图不调 api 的静态面）。"""
    problems = []
    for m in re.finditer(r"import\s[^;]*?from\s*'" + re.escape(spec) + "'", text):
        if not re.match(r"import\s+type\b", m.group(0)):
            problems.append(f"{label}：从 {spec} 只许 import type，实际有值导入：{m.group(0)[:90]}")
    return problems


def skip_marker_problems(text, label):
    problems = []
    for pat, what in ((r"\.\s*skip\s*\(", ".skip("), (r"\.\s*only\s*\(", ".only("), (r"\.\s*todo\s*\(", ".todo("),
                      (r"\bxit\s*\(", "xit("), (r"\bxdescribe\s*\(", "xdescribe(")):
        if re.search(pat, text):
            problems.append(f"{label}：新测试不许用 {what}")
    return problems


# ---------------------------------------------------------------------------
# CSS 小解析器（只解析追加部分；选择器列表按顶层逗号切）
# ---------------------------------------------------------------------------

def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def split_top(text, sep=","):
    parts, buf, depth, quote = [], [], 0, None
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts]


def parse_rules(css):
    """[(选择器, [(名, 值)…])]；@media 等包裹块里的规则展平，@keyframes 不展开。"""
    css = strip_comments(css)
    out = []

    def walk(text):
        i, n = 0, len(text)
        while i < n:
            j = text.find("{", i)
            if j < 0:
                break
            prelude = text[i:j].strip()
            depth, k = 1, j + 1
            while k < n and depth:
                if text[k] == "{":
                    depth += 1
                elif text[k] == "}":
                    depth -= 1
                k += 1
            body = text[j + 1:k - 1]
            if prelude.startswith("@"):
                if re.match(r"@(?:media|supports|container|layer|document)\b", prelude, re.I):
                    walk(body)
            else:
                decls = []
                for part in split_top(body, ";"):
                    if not part:
                        continue
                    name, _sep, value = part.partition(":")
                    decls.append((name.strip().lower(), value.strip()))
                out.append((re.sub(r"\s+", " ", prelude), decls))
            i = k

    walk(css)
    return out


def css_tail_problems(css_text):
    """roles-styles.css 只追加，且追加部分守令牌/px/出处注释规矩；按合同第 9 步的建议核对 .rl-hub。"""
    data = css_text.encode("utf-8")
    if not sha_prefix_ok(data, *ROLES_CSS_BASELINE):
        return ["不是只追加：基线前缀（字节与 sha256）对不上——合同第 9 步要求不改现有规则"]
    tail = data[ROLES_CSS_BASELINE[0]:].decode("utf-8")
    problems = []
    rules = parse_rules(tail)
    # .rl-hub 与 .tt-table 同一条规则里 min-width 760px（合同第 9 步的建议写法）
    hit = any(".rl-hub" in sel and ".tt-table" in sel
              and any(n == "min-width" and re.sub(r"\s+", "", v) == "760px" for n, v in decls)
              for sel, decls in rules)
    if not hit:
        problems.append("追加部分没有一条 .rl-hub 与 .tt-table 同在的选择器声明 min-width: 760px（合同第 9 步的建议）")
    for selector, decls in rules:
        for name, value in decls:
            if re.search(r"#[0-9a-f]{3,8}\b", value, re.I):
                problems.append(f"追加部分 {selector} 的 {name} 用了十六进制颜色：{value}")
            if re.search(r"\b(?:rgb|rgba|hsl|hsla|color-mix|oklch|oklab|lab)\(", value, re.I):
                problems.append(f"追加部分 {selector} 的 {name} 用了颜色函数：{value}")
    # --tt- 令牌名不许拼接：去掉所有 var(--tt-…) 之后不该再出现 --tt-
    leftover = re.sub(r"var\(--tt-[^)]*\)", "", strip_comments(tail))
    if "--tt-" in leftover:
        problems.append("追加部分出现了 var() 之外的 --tt-（拼接令牌名是 W 系禁写法）")
    # px 字面量同一行带出处注释（0 与 1px 除外）
    in_comment = False
    for no, line in enumerate(tail.splitlines(), 1):
        code, i, n, saw_comment = [], 0, len(line), in_comment
        while i < n:
            if in_comment:
                end = line.find("*/", i)
                if end < 0:
                    i = n
                else:
                    in_comment = False
                    i = end + 2
                continue
            if line.startswith("/*", i):
                in_comment = True
                saw_comment = True
                i += 2
                continue
            code.append(line[i])
            i += 1
        text = "".join(code)
        for m in re.finditer(r"(?<![\w.#-])(-?\d*\.?\d+)px\b", text):
            if abs(float(m.group(1))) in (0.0, 1.0):
                continue
            if not saw_comment:
                problems.append(f"追加部分第 {no} 行：{m.group(0)} 没有同一行的出处注释：{line.strip()[:80]}")
    return problems


# ---------------------------------------------------------------------------
# 静态检查函数（自检与用例共用）
# ---------------------------------------------------------------------------

def api_shape_problems(api_text):
    """getHubRoles 的形状（合同第 2 步的写法，照 getRoles）：真实分支路径/时限、桩分支命令与深拷贝、类型与导入。"""
    code = collapse(strip_ts_comments(api_text))
    problems = []
    checks = (
        ("exportfunctiongetHubRoles():Promise<Envelope<HubRolesData>>", "导出 getHubRoles(): Promise<Envelope<HubRolesData>>"),
        ("client.get<HubRolesData>('/api/v1/hub/roles',undefined,30)", "真实分支 GET /api/v1/hub/roles、时限 30 秒"),
        ("read(['config','hub','show','--json'],", "桩分支 read(['config','hub','show','--json'], …)"),
        ("okEnvelope(['config','hub','show','--json'],clone(HUB_ROLES_POSTS))", "桩分支 okEnvelope + clone(HUB_ROLES_POSTS)"),
    )
    for needle, what in checks:
        if needle not in code:
            problems.append(f"api.ts 缺少：{what}")
    if "HUB_ROLES_POSTS" not in collapse(api_text) or "from'./mock/hub-roles'" not in code:
        problems.append("api.ts 应 import HUB_ROLES_POSTS from './mock/hub-roles'（照其它夹具的 import 写法）")
    for name in ("HubPostFallback", "HubPostRow", "HubRolesData"):
        if f"exportinterface{name}" not in code:
            problems.append(f"api.ts 缺少类型导出 interface {name}")
    row_block = re.search(r"exportinterfaceHubPostRow\{(.*?)\}", code)
    if row_block:
        for field in ("post:", "source:", "allowed_adapters:", "adapter:", "provider:", "model:", "thinking:",
                      "profile:", "runtime:", "fallback:"):
            if field not in row_block.group(1):
                problems.append(f"HubPostRow 缺字段 {field[:-1]}")
    else:
        problems.append("读不到 HubPostRow 的接口体")
    fallback_block = re.search(r"exportinterfaceHubPostFallback\{(.*?)\}", code)
    if fallback_block:
        for field in ("adapter:", "provider:", "model:", "thinking:"):
            if field not in fallback_block.group(1):
                problems.append(f"HubPostFallback 缺字段 {field[:-1]}")
        # 合同 v3 第 2 步：profile 与 runtime 是可选键——写成必填会让四键替补的字面量过不了 tsc --noEmit
        for field in ("profile", "runtime"):
            if field + "?:" not in fallback_block.group(1):
                problems.append(f"HubPostFallback 的 {field} 应是可选键 {field}?:")
    else:
        problems.append("读不到 HubPostFallback 的接口体")
    if "posts:HubPostRow[]" not in code:
        problems.append("HubRolesData 应是 posts: HubPostRow[]")
    return problems


def api_exports_problems(api_text):
    names = exported_names(strip_ts_comments(api_text))
    problems = [f"api.ts 丢了既有导出：{sorted(API_EXPORT_BASELINE - names)}"] if not API_EXPORT_BASELINE <= names else []
    missing_new = [n for n in API_NEW_EXPORTS if n not in names]
    if missing_new:
        problems.append(f"api.ts 缺本片新导出：{missing_new}")
    return problems


def rolespage_problems(text):
    """RolesPage：并行四读、失败判定仍是前三个、hub 进 data、页头说明与按钮不动、四个禁词不出现（合同第 4 步）。"""
    code = collapse(strip_ts_comments(text))
    problems = []
    if "Promise.all([getRoles(),getProfiles(),getPresets(),getHubRoles()])" not in code:
        problems.append("loadRoles 应 Promise.all([getRoles(), getProfiles(), getPresets(), getHubRoles()]) 并行四个读")
    if "[roles,profiles,presets].find((e)=>!e.ok||e.data==null)" not in code:
        problems.append("失败判定仍应只看前三个：[roles, profiles, presets].find((e) => !e.ok || e.data == null)")
    if not re.search(r"\[roles,\s*profiles,\s*presets,\s*hub\]", strip_ts_comments(text)) and not re.search(r"\bhub\s*:\s*", code):
        problems.append("成功时的 data 里应带 hub（解构出 hub 或显式 hub: …）")
    if PAGE_DESC not in text:
        problems.append("页头说明应一字不改")
    if PAGE_HEAD_DISABLED not in text or "NewProfileAction" not in text:
        problems.append("页头两个按钮（PresetSaveAction、NewProfileAction）应照旧")
    if "getHubRoles" not in text:
        problems.append("RolesPage 应引用 getHubRoles")
    for word in ROLES_PAGE_FORBIDDEN:
        if word in text:
            problems.append(f"RolesPage 原文（注释也算）不许出现 {word}（T024 S07）")
    return problems


def rolesview_problems(text):
    code = collapse(strip_ts_comments(text))
    problems = []
    if "hub:Envelope<HubRolesData>" not in code:
        problems.append("RolesViewData 应加 hub: Envelope<HubRolesData>")
    # 站主门禁准备（2026-11-15）：T045 给 HubPosts 加 profiles、reload 两个 prop，只认开头（原来逐字钉 <HubPosts hub={data.hub} />）
    if "<HubPostshub={data.hub}" not in code:
        problems.append("应渲染 <HubPosts hub={data.hub} …>")
    raw = strip_ts_comments(text)
    # 网格锚点取前缀：基线写法是 className="rl-grid tt-grid-2"，带收尾引号会恒判找不到（T038-4 审核 B1）
    grid_cls = 'className="rl-grid'
    pos = {key: raw.find(key) for key in (grid_cls, "<HubPosts", "<ProfilesTable")}
    if pos[grid_cls] < 0 or pos["<HubPosts"] < 0 or pos["<ProfilesTable"] < 0 \
            or not (pos[grid_cls] < pos["<HubPosts"] < pos["<ProfilesTable"]):
        problems.append("HubPosts 应在角色卡网格之后、ProfilesTable 之前")
    problems += value_import_problems(text, "../../api", "roles-RolesView.tsx")
    return problems


def table_problems(text):
    code = collapse(strip_ts_comments(text))
    problems = []
    if "rowAttrs?:(row:Row)=>Record<string,string>" not in code:
        problems.append("TableProps 应加可选 prop rowAttrs?: (row: Row) => Record<string, string>")
    if not re.search(r"rowAttrs\?\.\s*\(row\)", strip_ts_comments(text)):
        problems.append("<tr> 上应展开 rowAttrs?.(row) 给出的属性")
    if code.count("rowAttrs") < 3:
        problems.append("rowAttrs 应同时出现在接口、参数解构与 <tr> 展开处")
    for needle, what in (("rowKey", "rowKey"), ("selectedKey", "selectedKey"), ("onRowOpen", "onRowOpen"),
                         ("rowHeight", "rowHeight"), ("className", "className"), ("'aria-label'", "aria-label"),
                         ("columns", "columns"), ("rows", "rows")):
        if needle not in code:
            problems.append(f"Table 应保留既有 prop {what}")
    return problems


def roleslogic_problems(text):
    code = collapse(strip_ts_comments(text))
    problems = []
    for fn in ("hubPostName", "allowedProfiles", "normalizeHubPost"):
        if f"exportfunction{fn}" not in code:
            problems.append(f"roles-logic.ts 应导出 {fn}")
    problems += value_import_problems(text, "../../api", "roles-logic.ts")
    return problems


def hubposts_problems(text):
    code = collapse(strip_ts_comments(text))
    problems = []
    if 'title="七端岗位"' not in text:
        problems.append('roles-HubPosts.tsx 的 Section 标题应是「七端岗位」')
    if 'aria-label="七端岗位"' not in text:
        problems.append('表的 aria-label 应是「七端岗位」')
    for needle, what in (("rowHeight={40}", "rowHeight={40}"), ("rl-hub", "className 带 rl-hub"),
                         ("hubPostName", "岗位列用 hubPostName")):
        if needle not in text:
            problems.append(f"roles-HubPosts.tsx 缺少 {what}")
    if "data-role" in strip_ts_comments(text):
        problems.append("七端岗位的行不要用 data-role（那是 T009 数角色卡的钩子），应经 rowAttrs 给 data-post")
    problems += value_import_problems(text, "../../api", "roles-HubPosts.tsx")
    return problems


def liveapi_problems(text):
    code = collapse(strip_ts_comments(text))
    problems = []
    for needle, what in (("name:'getHubRoles'", "读函数表加 getHubRoles 一行"),
                         ("path:'/api/v1/hub/roles'", "getHubRoles 行的路径"),
                         ("api.getHubRoles()", "getHubRoles 行的 run")):
        if needle not in code:
            problems.append(f"live-api.test.ts 缺少：{what}")
    if not re.search(r"getHubRoles'[^}]*timeout:\s*30", strip_ts_comments(text)):
        problems.append("getHubRoles 行的服务端时限应是 30")
    if "16 个读函数" not in text:
        problems.append("describe 标题里的读函数个数应按实际改成 16")
    for name in API_READ_NAMES:
        if f"api.{name}" not in text:
            problems.append(f"live-api.test.ts 丢了既有读函数 {name}（只加不改）")
    return problems


def stub_problems(text):
    code = collapse(strip_ts_comments(text))
    problems = []
    if "exportconstHUB_ROLES_POSTS:HubRolesData" not in code:
        problems.append("hub-roles.ts 应导出 export const HUB_ROLES_POSTS: HubRolesData")
    problems += value_import_problems(text, "../api", "hub-roles.ts")
    return problems


# ---------------------------------------------------------------------------
# 静态断言
# ---------------------------------------------------------------------------

def test_s01_new_files_in_place():
    """S01 / D02：两个新源码文件在位；src/mock 仍恰 14 份 JSON（桩只能是 .ts）；src/pages 顶层仍恰 9 个 *Page.tsx。"""
    missing = [rel for rel in NEW_SOURCE_FILES if not (REPO_ROOT / rel).is_file()]
    assert not missing, f"缺少本片的新文件（基线上还没有实现）：{missing}"
    mock_json = sorted(p.name for p in (SRC / "mock").glob("*.json"))
    assert len(mock_json) == MOCK_JSON_COUNT, f"src/mock 应恰 {MOCK_JSON_COUNT} 份 JSON，实际 {len(mock_json)}：{mock_json}"
    pages = sorted(p.name for p in (SRC / "pages").glob("*Page.tsx"))
    assert len(pages) == PAGES_TSX_COUNT, f"src/pages 顶层应恰 {PAGES_TSX_COUNT} 个 *Page.tsx，实际 {len(pages)}：{pages}"
    assert not (SRC / "mock" / "hub-roles.json").is_file(), "七端岗位的桩只能是 .ts（src/mock 不加 JSON）"


def test_s02_api_read_shape():
    """S02 / D01：api.ts 的 getHubRoles 两条分支、类型与 import（形状层面；行为在 page 探针）。"""
    fail_if(api_shape_problems(_read(need_file(API_REL))), "api.ts 的 getHubRoles 形状")
    fail_if(api_exports_problems(_read(API_REL)), "api.ts 的导出集合")


def test_s03_stub_types_only():
    """S03 / D02：桩是 .ts 且只从 api 做纯类型导入（编译后擦除，不产生运行时循环）。"""
    fail_if(stub_problems(_read(need_file(HUB_MOCK_REL))), "hub-roles.ts")


def test_s04_rolespage_wiring():
    """S04 / D03：并行四读、失败顺序仍是 roles→profiles→presets、hub 整个信封进 data；页头与禁词规矩不动。"""
    fail_if(rolespage_problems(_read(need_file(ROLES_PAGE_REL))), "RolesPage 的接线")


def test_s05_rolesview_hub():
    """S05 / D03、D04：RolesViewData.hub 的类型、import type、HubPosts 在角色卡与 profile 表之间。"""
    fail_if(rolesview_problems(_read(need_file(ROLES_VIEW_REL))), "roles-RolesView.tsx")


def test_s06_table_rowattrs():
    """S06 / D04：Table 加可选 rowAttrs（不传时行为不变），既有 prop 一个不丢。"""
    fail_if(table_problems(_read(need_file(TABLE_REL))), "Table 的加法式 prop")


def test_s07_roles_logic_pure_fns():
    """S07 / D06：roles-logic 导出三个纯函数，且只 import type（纯函数文件不碰运行时 api）。"""
    fail_if(roleslogic_problems(_read(need_file(ROLES_LOGIC_REL))), "roles-logic.ts")


def test_s08_roles_css_append_only():
    """S08 / D07：roles-styles.css 只追加；追加部分守令牌、px 出处注释与 .rl-hub 的建议写法。"""
    fail_if(css_tail_problems(_read(need_file(ROLES_CSS_REL))), "roles-styles.css")


def test_s09_executor_tests_in_place():
    """S09 / D08：live-api.test.ts 只加一行（16 个读名都在）；两份新测试在位且不用 skip/only/todo。"""
    live = _read(need_file(LIVE_API_TEST_REL))
    fail_if(liveapi_problems(live), "live-api.test.ts")
    for rel in NEW_TEST_FILES:
        text = _read(need_file(rel))
        fail_if(skip_marker_problems(text, rel), rel)


def test_s10_hubposts_static():
    """S10 / D04：roles-HubPosts 的静态形状——标题、aria-label、rowHeight、rl-hub、hubPostName、data-post 而非 data-role。"""
    fail_if(hubposts_problems(_read(need_file(HUB_POSTS_REL))), "roles-HubPosts.tsx")


def test_s11_new_sources_no_forbidden_words():
    """S11 / D07：本片新增源码（含改动面）不出现网络词与 T007 禁用词（注释也算）。"""
    for rel in (HUB_MOCK_REL, HUB_POSTS_REL, ROLES_PAGE_REL, ROLES_VIEW_REL, ROLES_LOGIC_REL, TABLE_REL):
        text = _read(need_file(rel))
        hits = [w[:6] + "…" for w in NET_WORDS + SINK_WORDS if w in text]
        fail_if([f"{rel} 出现禁用词 {h}" for h in hits], "禁用词")
        if rel.endswith((".ts", ".tsx")):
            code = strip_ts_comments(text)
            problems = []
            if re.search(r"role\s*=\s*['\"]status['\"]", code):
                problems.append(f"{rel} 渲染了 role=status")
            if re.search(r"\bstyle\s*=", code):
                problems.append(f"{rel} 写了内联 style")
            fail_if(problems, "新源码规则")


# ---------------------------------------------------------------------------
# 探针（Vitest + jsdom）：自带全部辅助函数，不写 JSX
# ---------------------------------------------------------------------------

# 合同 v3 第 3 步的六行（lib 探针逐字段 toStrictEqual 的期望值）：只写真内核交得出的形状
# （scripts/kit_roles.py）——coordinator 的替补恰四键（不写 profile、不写 runtime），
# contract 配置行的主绑定在 quizs 上（profile 是 quizs-m3）、替补六键（profile 是 step-high）。
SIX_ROWS_TS = """
const ROWS = [
  { post: 'coordinator', source: 'default', allowed_adapters: ['quizs', 'pi'], adapter: 'quizs', provider: 'deepseek',
    model: 'deepseek-flash', thinking: 'high', profile: null, runtime: null,
    fallback: { adapter: 'pi', provider: 'dsf', model: 'deepseek-flash', thinking: 'high' } },
  { post: 'planner', source: 'default', allowed_adapters: ['claude-code'], adapter: 'claude-code', provider: null,
    model: 'claude-opus-5-5', thinking: 'max', profile: null, runtime: null, fallback: null },
  { post: 'contract', source: 'config', allowed_adapters: ['pi', 'quizs'], adapter: 'quizs', provider: 'minimax',
    model: 'MiniMax-M3.1-Flash', thinking: 'high', profile: 'quizs-m3', runtime: 'quizs',
    fallback: { profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' } },
  { post: 'gate', source: 'default', allowed_adapters: ['pi'], adapter: 'pi', provider: 'cc-switch-zhipu-glm',
    model: 'glm-5.3', thinking: 'high', profile: null, runtime: null, fallback: null },
  { post: 'audit', source: 'default', allowed_adapters: ['pi', 'quizs'], adapter: 'pi', provider: 'minimax',
    model: 'MiniMax-M3.1-Flash', thinking: 'max', profile: null, runtime: null, fallback: null },
  { post: 'exec', source: 'config', allowed_adapters: ['pi'], adapter: 'pi', provider: 'bb', model: 'step-5-preview',
    thinking: 'high', profile: 'step-high', runtime: 'pi', fallback: null },
];
"""

PROBE_LIB = r"""
import { describe, expect, it } from 'vitest';
import { HUB_ROLES_POSTS } from '../src/mock/hub-roles';
import { hubPostName, allowedProfiles, normalizeHubPost } from '../src/pages/readonly1/roles-logic';
""" + SIX_ROWS_TS + r"""

describe('L1 桩的六行', () => {
  it('六行按 coordinator、planner、contract、gate、audit、exec 排，十个绑定字段逐字段等于合同第 3 步', () => {
    expect(HUB_ROLES_POSTS.posts.length).toBe(6);
    expect(HUB_ROLES_POSTS.posts.map((p: any) => p.post)).toEqual(
      ['coordinator', 'planner', 'contract', 'gate', 'audit', 'exec']);
    // T047 门禁准备：桩的每行加了 turn、last_turn（config hub show 第 168 轮），这里只比十个绑定字段
    const BINDING = ['post', 'source', 'allowed_adapters', 'adapter', 'provider', 'model', 'thinking', 'profile', 'runtime', 'fallback'];
    ROWS.forEach((want, i) => {
      const got: any = HUB_ROLES_POSTS.posts[i];
      const picked = Object.fromEntries(BINDING.filter((key) => key in got).map((key) => [key, got[key]]));
      expect(picked, '第 ' + (i + 1) + ' 行（' + want.post + '）').toStrictEqual(want);
    });
  });
  it('覆盖面：来源是配置与缺省、带与不带替补、主绑定 quizs 与 pi、provider 为 null、替补四键与六键两种形状', () => {
    const posts = HUB_ROLES_POSTS.posts;
    expect(posts.filter((p: any) => p.source === 'config').map((p: any) => p.post)).toEqual(['contract', 'exec']);
    expect(posts.filter((p: any) => p.fallback != null).map((p: any) => p.post)).toEqual(['coordinator', 'contract']);
    expect(posts.filter((p: any) => p.adapter === 'quizs').map((p: any) => p.post)).toEqual(['coordinator', 'contract']);
    expect(posts.filter((p: any) => p.provider === null).map((p: any) => p.post)).toEqual(['planner']);
    // 合同 v3 第 3 步：coordinator 的替补恰四个键（不写 profile/runtime）；contract 配置行的替补六个键
    const fbKeys = posts.filter((p: any) => p.fallback != null).map((p: any) => Object.keys(p.fallback).sort());
    expect(fbKeys).toEqual([
      ['adapter', 'model', 'provider', 'thinking'],
      ['adapter', 'model', 'profile', 'provider', 'runtime', 'thinking'],
    ]);
  });
});

describe('L2 纯函数', () => {
  it('hubPostName：六个中文名，未知岗位码原样', () => {
    expect(hubPostName('coordinator')).toBe('协调人');
    expect(hubPostName('planner')).toBe('规划端');
    expect(hubPostName('contract')).toBe('合同端');
    expect(hubPostName('gate')).toBe('门禁端');
    expect(hubPostName('audit')).toBe('审核端');
    expect(hubPostName('exec')).toBe('执行端');
    expect(hubPostName('unknown-post')).toBe('unknown-post');
  });
  it('allowedProfiles：adapter 为 null 不算、不在允许名单不算、空名单为空、coordinator 许 quizs 与 pi、planner 只许 claude-code', () => {
    const profiles: any[] = [
      { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: {}, credential_env: [] },
      { id: 'quiz-one', runtime: 'quizs', adapter: 'quizs', provider: 'deepseek', model: 'deepseek-flash', options: {}, credential_env: [] },
      { id: 'no-adapter', runtime: 'ghost', adapter: null, provider: 'x', model: 'y', options: {}, credential_env: [] },
      { id: 'cc-one', runtime: 'cc', adapter: 'claude-code', provider: 'z', model: 'w', options: {}, credential_env: [] },
    ];
    expect(allowedProfiles(profiles, ['pi', 'quizs'])).toEqual(['step-high', 'quiz-one']);
    expect(allowedProfiles(profiles, ['claude-code'])).toEqual(['cc-one']);
    expect(allowedProfiles(profiles, [])).toEqual([]);
    expect(allowedProfiles(profiles, ['codex'])).toEqual([]);
  });
  it('normalizeHubPost：缺键按 null 归一，替补缺 profile/runtime 键也归 null、对象原样、缺失为 null', () => {
    const n: any = normalizeHubPost({ post: 'gate', source: 'default', allowed_adapters: ['pi'] } as any);
    expect(n.post).toBe('gate');
    expect(n.source).toBe('default');
    expect(n.allowedAdapters).toEqual(['pi']);
    ['adapter', 'provider', 'model', 'thinking', 'profile', 'runtime', 'fallback'].forEach((k) => {
      expect(n[k], k + ' 缺键应归 null').toBeNull();
    });
    // coordinator 的替补只有四键：归一后补出 profile/runtime 两个 null（合同 v3 第 8 步）
    const four: any = normalizeHubPost(ROWS[0] as any);
    expect(four.fallback).toEqual({ adapter: 'pi', provider: 'dsf', model: 'deepseek-flash', thinking: 'high',
      profile: null, runtime: null });
    const full: any = normalizeHubPost(ROWS[2] as any);
    expect(full.post).toBe('contract');
    expect(full.source).toBe('config');
    expect(full.allowedAdapters).toEqual(['pi', 'quizs']);
    expect(full.adapter).toBe('quizs');
    expect(full.provider).toBe('minimax');
    expect(full.model).toBe('MiniMax-M3.1-Flash');
    expect(full.thinking).toBe('high');
    expect(full.profile).toBe('quizs-m3');
    expect(full.runtime).toBe('quizs');
    expect(full.fallback).toEqual(ROWS[2].fallback);
  });
});
"""

PAGE_PRELUDE = r"""
import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

const h: any = React.createElement;

vi.setConfig({ testTimeout: 60000 });

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
  window.location.hash = '';
  await drainNav();
});

function textOf(el: any): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function qa(rootEl: any, sel: string): any[] {
  return Array.from(rootEl.querySelectorAll(sel));
}
function tagWith(rootEl: any, text: string): any {
  return qa(rootEl, '.tt-tag').find((t) => textOf(t) === text) || null;
}
function isMono(td: any): boolean {
  if (/mono/.test(td.className || '')) return true;
  return qa(td, '*').some((e) => /mono/.test(e.className || '') || e.tagName === 'CODE');
}
async function flush() {
  for (let i = 0; i < 12; i += 1) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  const App: any = (await import('../src/App')).default;
  const r = render(h(App));
  await flush();
  return r;
}
function root(page: string): any {
  return document.querySelector('[data-page="' + page + '"]');
}
function frame(): any {
  return document.querySelector('[data-page-state]');
}
function pageText(): string {
  const f = frame();
  return textOf(f || document.body);
}
function sectionTitle(sec: any): string {
  const id = sec.getAttribute('aria-labelledby');
  return textOf(id ? document.getElementById(id) : null);
}
function sectionNamed(rootEl: any, title: string): any {
  return qa(rootEl, 'section').find((s) => sectionTitle(s) === title) || null;
}
function tableRows(table: any): Array<Record<string, any>> {
  const heads = qa(table, 'thead th').map(textOf);
  return qa(table, 'tbody tr').map((tr) => {
    const o: Record<string, any> = {};
    qa(tr, 'td').forEach((td, i) => {
      o[heads[i]] = td;
    });
    return o;
  });
}
"""

PAGE_API_MOCK = r"""
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

function env(data: any, command: string[] = ['gate']): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}
function bad(command: string[], code: number, messages: string[]): any {
  return { ok: false, exit_code: code, data: null, output: [], messages, command, elapsed_ms: 0 };
}
function set(name: string, value: any) {
  hoisted.overrides[name] = typeof value === 'function' ? value : () => Promise.resolve(value);
}
function headless(role: string, over: any = {}): any {
  return Object.assign({
    role, explicit: true, binding: { mode: 'headless', profile: 'step-high' }, differs_from_preset: false, profile: 'step-high',
    runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, effort_effective: 'high',
  }, over);
}
function rolesMain(): any {
  return env({ active_preset: 'default', roles: [
    { role: 'planning_review', explicit: true, binding: { mode: 'interactive_host', host: 'claude-code' }, differs_from_preset: false },
    { role: 'contract', explicit: false, binding: { mode: 'manual' }, differs_from_preset: true },
    headless('execution', { effort_effective: 'low' }),
    { role: 'scheduler_agent', explicit: false, binding: { mode: 'disabled' }, differs_from_preset: false },
  ] }, ['config', 'role', 'show']);
}
function profilesMain(): any {
  return env({ profiles: [
    { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: ['STEP_API_KEY'] },
    { id: 'bare', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini', options: {}, credential_env: [] },
  ] }, ['config', 'profile', 'show']);
}
function presetsMain(): any {
  return env({ active_preset: 'default', presets: [
    { name: 'default', description: '日常', roles: ['contract', 'execution', 'planning_review', 'scheduler_agent'], active: true },
    { name: 'economy', description: '省钱', roles: ['execution'], active: false },
  ] }, ['config', 'preset', 'show']);
}
function setRoles(roles: any, profiles: any, presets: any) {
  set('getRoles', roles);
  set('getProfiles', profiles);
  set('getPresets', presets);
}
async function mountRoles(roles: any = rolesMain(), profiles: any = profilesMain(), presets: any = presetsMain()) {
  setRoles(roles, profiles, presets);
  return mountApp('#/roles');
}
function hubSec(): any {
  return sectionNamed(root('roles'), '七端岗位');
}
function hubTable(): any {
  const sec = hubSec();
  return sec ? sec.querySelector('table[aria-label="七端岗位"]') : null;
}
function hubRows(): Array<Record<string, any>> {
  const t = hubTable();
  return t ? tableRows(t) : [];
}
const POSTS = ['coordinator', 'planner', 'contract', 'gate', 'audit', 'exec'];
const SIX = ['岗位', '运行时', '模型', '思考档位', '来源', '替补'];
"""

PROBE_PAGE = PAGE_PRELUDE + PAGE_API_MOCK + r"""

describe('P1 区块与表', () => {
  it('区块存在：h2 标题恰是「七端岗位」，不带说明文字，不影响角色页其余区块', async () => {
    await mountRoles();
    const r = root('roles');
    expect(r, '视图根带 data-page=roles').not.toBeNull();
    const sec = hubSec();
    expect(sec, '应有标题为「七端岗位」的 section').not.toBeNull();
    expect(sec.querySelector('h2')).toBeTruthy();
    expect(qa(sec, '.common-section__desc').length, '不加次级说明').toBe(0);
    expect(sectionNamed(r, 'profile'), 'profile 表区块照常').not.toBeNull();
    expect(sectionNamed(r, '方案'), '方案表区块照常').not.toBeNull();
  });
  it('表 aria-label 是「七端岗位」；前六个列头恰是 岗位、运行时、模型、思考档位、来源、替补；每行带 data-post', async () => {
    await mountRoles();
    const table = hubTable();
    expect(table, '表应带 aria-label="七端岗位"').not.toBeNull();
    expect(qa(table, 'thead th').map(textOf).slice(0, 6)).toEqual(SIX);
    const trs = qa(table, 'tbody tr');
    expect(trs.length).toBe(6);
    // jsdom 的属性选择器对特殊值不可靠：遍历比对 getAttribute
    expect(trs.map((tr) => tr.getAttribute('data-post'))).toEqual(POSTS);
  });
  it('位置：这一组在角色卡网格之后、profile 表之前；滚动容器带 rl-hub 类', async () => {
    await mountRoles();
    const r = root('roles');
    const grid = r.querySelector('.rl-grid');
    const sec = hubSec();
    const prof = sectionNamed(r, 'profile');
    expect(grid && sec && prof).toBeTruthy();
    expect(grid.compareDocumentPosition(sec) & Node.DOCUMENT_POSITION_FOLLOWING,
      '七端岗位在角色卡网格之后').toBeTruthy();
    expect(sec.compareDocumentPosition(prof) & Node.DOCUMENT_POSITION_FOLLOWING,
      '七端岗位在 profile 表之前').toBeTruthy();
    const wrap = hubTable().closest('.tt-table-wrap');
    expect(wrap, '表在 .tt-table-wrap 里').not.toBeNull();
    expect(wrap.className).toContain('rl-hub');
  });
});

describe('P2 六行字段', () => {
  it('岗位、运行时、模型、替补逐格对上（null 显示 —；替补带与不带 profile 两种形状）', async () => {
    await mountRoles();
    const rows = hubRows();
    expect(rows.length).toBe(6);
    const names = ['协调人', '规划端', '合同端', '门禁端', '审核端', '执行端'];
    // 合同 v3 第 3 步：gate/audit 的 runtime 是 null → 「—（pi）」；contract 行 runtime/adapter 都是 quizs → 「quizs（quizs）」
    const runtimes = ['—（quizs）', '—（claude-code）', 'quizs（quizs）', '—（pi）', '—（pi）', 'pi（pi）'];
    const models = ['deepseek/deepseek-flash', '—/claude-opus-5-5', 'minimax/MiniMax-M3.1-Flash',
      'cc-switch-zhipu-glm/glm-5.3', 'minimax/MiniMax-M3.1-Flash', 'bb/step-5-preview'];
    const fallbacks = ['—（pi） · dsf/deepseek-flash', '—', 'step-high · pi（pi） · bb/step-5-preview', '—', '—', '—'];
    POSTS.forEach((post, i) => {
      const row = rows[i];
      expect(row['岗位'] ? textOf(row['岗位']) : null, post + ' 的岗位名').toBe(names[i]);
      expect(row['运行时'] ? textOf(row['运行时']) : null, post + ' 的运行时').toBe(runtimes[i]);
      expect(row['模型'] ? textOf(row['模型']) : null, post + ' 的模型').toBe(models[i]);
      expect(row['替补'] ? textOf(row['替补']) : null, post + ' 的替补').toBe(fallbacks[i]);
    });
  });
  it('没有最近一回合的 audit、exec 两行，思考档位经 EffortPair（effective 传 null）：data-state unknown、文字「要求 X · 生效 未知」', async () => {
    await mountRoles();
    const think = ['high', 'max', 'high', 'high', 'max', 'high'];
    // T047 门禁准备：桩里有最近一回合的四行改显示档位三值，只核没有最近一回合的 audit、exec
    hubRows().forEach((row, i) => {
      if (!['audit', 'exec'].includes(POSTS[i])) return;
      const effort = row['思考档位'].querySelector('.tt-effort');
      expect(effort, POSTS[i] + ' 的思考档位经 EffortPair').not.toBeNull();
      expect(effort.getAttribute('data-state'), POSTS[i] + ' 的 data-state').toBe('unknown');
      expect(textOf(effort), POSTS[i] + ' 的文字').toBe('要求 ' + think[i] + ' · 生效 未知');
    });
  });
  it('来源列：缺省行是 neutral Tag「默认」，配置行是该行的 profile id（等宽）且不是 Tag', async () => {
    await mountRoles();
    hubRows().forEach((row, i) => {
      const cell = row['来源'];
      if (i === 2 || i === 5) {
        expect(qa(cell, '.tt-tag').length, POSTS[i] + ' 配置行来源不是 Tag').toBe(0);
        expect(textOf(cell)).toBe(i === 2 ? 'quizs-m3' : 'step-high');
        expect(isMono(cell), POSTS[i] + ' 的 profile id 等宽').toBe(true);
      } else {
        const tag = cell.querySelector('.tt-tag');
        expect(tag, POSTS[i] + ' 缺省行来源是 Tag「默认」').not.toBeNull();
        expect(textOf(tag)).toBe('默认');
        expect(tag.getAttribute('data-tone')).toBe('neutral');
      }
    });
  });
});

describe('P3 hub 读失败只影响本组', () => {
  it('只有七端岗位这一组显示失败信封与 messages 的 pre；四个角色卡、profile 表、方案表照常；整页仍是 data 态', async () => {
    setRoles(rolesMain(), profilesMain(), presetsMain());
    set('getHubRoles', bad(['config', 'hub', 'show', '--json'], 2, ['内核没有 config hub', '第二行']));
    await mountApp('#/roles');
    expect(frame().getAttribute('data-page-state'), 'hub 失败不改整页状态').toBe('data');
    const r = root('roles');
    expect(qa(r, 'article[data-role]').length, '四张角色卡照常').toBe(4);
    expect(sectionNamed(r, 'profile'), 'profile 表照常').not.toBeNull();
    expect(sectionNamed(r, '方案'), '方案表照常').not.toBeNull();
    const sec = hubSec();
    expect(textOf(sec)).toContain('没能读到七端岗位：命令 config hub show --json 返回退出码 2。');
    const pre = sec.querySelector('pre');
    expect(pre, 'messages 放进 pre').not.toBeNull();
    expect(textOf(pre)).toContain('内核没有 config hub');
  });
  it('失败组里不渲染表格行；失败命令在整页只出现一次', async () => {
    setRoles(rolesMain(), profilesMain(), presetsMain());
    set('getHubRoles', bad(['config', 'hub', 'show', '--json'], 3, ['x']));
    await mountApp('#/roles');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(qa(hubSec(), 'tbody tr').length, '失败时这一组不渲染表格行').toBe(0);
    const hits = pageText().split('config hub show --json').length - 1;
    expect(hits, 'hub 的失败命令只在七端岗位这一组出现').toBe(1);
  });
});

describe('P4 四个读并行与整页失败顺序', () => {
  it('getRoles 挂起时 getProfiles、getPresets、getHubRoles 也都已发出（一次一个）', async () => {
    set('getRoles', () => new Promise(() => {}));
    set('getProfiles', profilesMain());
    set('getPresets', presetsMain());
    await mountApp('#/roles');
    expect((hoisted.spies.getProfiles as any).mock.calls.length).toBe(1);
    expect((hoisted.spies.getPresets as any).mock.calls.length).toBe(1);
    expect((hoisted.spies.getHubRoles as any).mock.calls.length, '七端岗位的读也并行发出').toBe(1);
    expect(frame().getAttribute('data-page-state')).toBe('loading');
  });
  it('前三个读失败仍按 roles→profiles→presets：整页 error 显示第一个坏信封（hub 不参与整页失败判定）', async () => {
    const R = bad(['config', 'role', 'show'], 7, ['E-ROLES']);
    const P = bad(['config', 'profile', 'show'], 8, ['E-PROFILES']);
    const S = bad(['config', 'preset', 'list'], 9, ['E-PRESETS']);
    const cases: Array<[any, any, any, string, string[]]> = [
      [R, P, S, 'config role show', ['命令（config profile show', '命令（config preset list']],
      [rolesMain(), P, S, 'config profile show', ['命令（config role show', '命令（config preset list']],
      [rolesMain(), profilesMain(), S, 'config preset list', ['命令（config role show']],
    ];
    for (const [roles, profiles, presets, want, notWant] of cases) {
      cleanup();
      setRoles(roles, profiles, presets);
      await mountApp('#/roles');
      expect(frame().getAttribute('data-page-state'), want).toBe('error');
      expect(pageText(), want).toContain('命令（' + want + '）');
      notWant.forEach((w) => expect(pageText(), '不该出现 ' + w).not.toContain(w));
      expect(root('roles')).toBeNull();
    }
  });
});

describe('P5 夹具与空模式', () => {
  it('?mock=empty 时角色页仍是 data 态，七端岗位仍给六行', async () => {
    await mountApp('#/roles?mock=empty');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(qa(hubTable(), 'tbody tr').map((tr: any) => tr.getAttribute('data-post'))).toEqual(POSTS);
  });
  it('缺省 mock（data 模式）下七端岗位是六行（桩经 getHubRoles 正常出数）', async () => {
    await mountApp('#/roles');
    expect(qa(hubTable(), 'tbody tr').length).toBe(6);
    expect((hoisted.spies.getHubRoles as any).mock.calls.length).toBe(1);
  });
});

describe('P6 真实模式的读函数', () => {
  it('getHubRoles 真实分支：GET /api/v1/hub/roles、时限 30 秒、无查询参数', async () => {
    const { setLiveClientForTests } = await import('../src/live/mode');
    const calls: any[] = [];
    let next: any = null;
    const fake: any = {
      get(_path: string, query?: any, timeoutSeconds?: number) {
        calls.push({ _path, query, timeoutSeconds });
        return Promise.resolve(next);
      },
    };
    setLiveClientForTests(fake);
    try {
      next = env({ posts: [] }, []);
      const api: any = await import('../src/api');
      await api.getHubRoles();
      expect(calls.length).toBe(1);
      expect(calls[0]._path).toBe('/api/v1/hub/roles');
      expect(calls[0].timeoutSeconds).toBe(30);
      const q = calls[0].query;
      expect(q == null || Object.keys(q).length === 0).toBe(true);
    } finally {
      setLiveClientForTests(undefined);
    }
  });
  it('真实分支不回落桩：服务回错误信封时原样透传（data null、退出码原样）', async () => {
    const { setLiveClientForTests } = await import('../src/live/mode');
    const badEnv = bad(['config', 'hub', 'show', '--json'], 3, ['内核没这个命令']);
    const fake: any = { get: () => Promise.resolve(badEnv) };
    setLiveClientForTests(fake);
    try {
      const api: any = await import('../src/api');
      const got = await api.getHubRoles();
      expect(got).toBe(badEnv);
      expect(got.ok).toBe(false);
      expect(got.data).toBeNull();
      expect(got.exit_code).toBe(3);
    } finally {
      setLiveClientForTests(undefined);
    }
  });
  it('真实分支成功：data 原样（不换成桩里的六行名册）', async () => {
    const { setLiveClientForTests } = await import('../src/live/mode');
    const marker = env({ posts: [{ post: 'marker', source: 'default', allowed_adapters: [], adapter: null,
      provider: null, model: null, thinking: null, profile: null, runtime: null, fallback: null }] }, []);
    const fake: any = { get: () => Promise.resolve(marker) };
    setLiveClientForTests(fake);
    try {
      const api: any = await import('../src/api');
      const got = await api.getHubRoles();
      expect(got.data.posts[0].post).toBe('marker');
      expect(got.data.posts.length).toBe(1);
    } finally {
      setLiveClientForTests(undefined);
    }
  });
});
"""

# PROBE_TRANS（TRANS 没有写入口：列头恰好六列、整组没有按钮）：站主 2026-11-15 为 T045（“七端岗位”一组加“改绑定…”“恢复缺省…”）退役

PROBE_SPECS = {
    "lib": (PROBE_LIB, (HUB_MOCK_REL, ROLES_LOGIC_REL)),
    "page": (PROBE_PAGE, (HUB_MOCK_REL, HUB_POSTS_REL, ROLES_PAGE_REL, ROLES_VIEW_REL, TABLE_REL)),
}
PROBE_ORDER = ("lib", "page")


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


def probe_groups(source):
    groups, current = {}, None
    for line in source.splitlines():
        m = re.match(r"describe\('([^']+)'", line)
        if m:
            current = m.group(1)
            groups[current] = 0
        elif current and re.match(r"\s+it\(", line):
            groups[current] += 1
    return groups


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针
# ---------------------------------------------------------------------------

# G01 的超时是 600s：夹具总预算压在 540s 以内，用完就停下并在断言里写明，不等调度器来杀。
PIPELINE_BUDGET = 540
STEP_CAPS = {
    "npm ci": 240,
    "npm ci --offline": 240,
    "npm test": 240,
    "npm run build": 180,
    "probe": 110,
}

WATCHED = ("package.json", "package-lock.json")


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
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
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


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not any((REPO_ROOT / rel).is_file() for rel in NEW_SOURCE_FILES):
        pipe.reason = ("候选里还没有本片的新源码文件（基线），没有东西可测，未调用 npm；"
                       "候选写出新文件后，流水线才会运行 npm（依赖已在就跳过重装）、Vitest 与探针")
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
        # 依赖已在（执行端 Setup 装过）就不重装：省下的时间留给 Vitest 与探针
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
            run_step("npm run build", [npm, "run", "build"])
            uid = uuid.uuid4().hex[:12]
            for key in PROBE_ORDER:
                missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                name = f"probe-{uid}-t038-{key}.test.ts"
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
    """P1 / V01、V02：npm 依赖（已在就跳过重装）、npm test（全绿）、npm run build 都退出 0；依赖文件一个字节没动。"""
    assert any(pipeline.steps.get(k) is not None and pipeline.steps[k].code == 0
               for k in ("npm ci", "npm ci --offline")), \
        f"npm ci 未成功：{pipeline.stopped_reason or pipeline.reason}"
    for name in ("npm test", "npm run build"):
        step = assert_step_ok(pipeline, name)
        if name == "npm test":
            m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
            assert m, f"npm test 输出里没有通过计数：\n{step.tail}"
            assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), \
                f"npm test 有失败或跳过：\n{step.tail}"
        if name == "npm run build":
            assert "built in" in step.out, f"vite build 应打印 built in：\n{step.tail}"
    assert pipeline.digests_before == pipeline.digests_after, \
        "npm 流水线不许改动 desktop/web/package.json 与 package-lock.json"
    assert not pipeline.gate_probe_left, "gate-probe/ 目录在探针后应清掉"


def test_p2_probe_lib(pipeline):
    """P2 / D01、D02、D06：桩的六行逐字段等于合同；三个纯函数的边界全绿。"""
    assert_probe_ok(pipeline, "lib")


def test_p3_probe_page(pipeline):
    """P3 / D01、D03–D05：页面探针全绿（区块与表、六行字段、hub 失败隔离、并行与失败顺序、空模式、真实模式读函数）。"""
    assert_probe_ok(pipeline, "page")


# test_transitional_probe_no_write_entries：站主 2026-11-15 为 T045（“七端岗位”一组加“改绑定…”“恢复缺省…”）退役


# ---------------------------------------------------------------------------
# 门禁自检（不依赖候选：检查函数喂正确样本与改坏样本；探针源码查配对与语法形状）
# ---------------------------------------------------------------------------

def test_gate_selfcheck_api_shape():
    """api_shape_problems 对合同 v3 第 2 步的正样通过，对改坏样（时限、命令、回落桩、缺类型、替补键写成必填）各抓一条。"""
    good = """
import { HUB_ROLES_POSTS } from './mock/hub-roles';

export interface HubPostFallback {
  adapter: string | null;
  provider: string | null;
  model: string | null;
  thinking: string | null;
  profile?: string | null;
  runtime?: string | null;
}
export interface HubPostRow {
  post: string;
  source: 'default' | 'config';
  allowed_adapters: string[];
  adapter: string | null;
  provider: string | null;
  model: string | null;
  thinking: string | null;
  profile: string | null;
  runtime: string | null;
  fallback: HubPostFallback | null;
}
export interface HubRolesData {
  posts: HubPostRow[];
}
export function getHubRoles(): Promise<Envelope<HubRolesData>> {
  const client = liveClient();
  if (client) return client.get<HubRolesData>('/api/v1/hub/roles', undefined, 30);
  return read(['config', 'hub', 'show', '--json'], () =>
    okEnvelope(['config', 'hub', 'show', '--json'], clone(HUB_ROLES_POSTS)),
  );
}
"""
    assert api_shape_problems(good) == [], api_shape_problems(good)
    mutations = {
        "时限改成 60": good.replace("undefined, 30)", "undefined, 60)"),
        "桩命令丢了 --json": good.replace("'show', '--json'], () =>", "'show'], () =>")
                                  .replace("'show', '--json'], clone", "'show'], clone"),
        "真实分支回落桩": good.replace("if (client) return client.get<HubRolesData>('/api/v1/hub/roles', undefined, 30);",
                                       "if (client) return read(['config', 'hub', 'show', '--json'], () => okEnvelope(['config', 'hub', 'show', '--json'], clone(HUB_ROLES_POSTS)));"),
        "缺 HubRolesData 类型": good.replace("export interface HubRolesData {\n  posts: HubPostRow[];\n}\n", ""),
        "HubPostRow 缺 fallback 字段": good.replace("  fallback: HubPostFallback | null;\n", ""),
        "替补 profile 写成必填": good.replace("profile?: string | null;", "profile: string | null;"),
        "替补丢了可选的 runtime 键": good.replace("  runtime?: string | null;\n", ""),
    }
    for label, text in mutations.items():
        problems = api_shape_problems(text)
        assert problems, f"改坏样「{label}」应当被抓到"


def test_gate_selfcheck_css_tail():
    """css_tail_problems 对合同建议的正样通过，对十六进制颜色、缺注释的 px、拼接令牌、改基线各抓一条。
    样本取锁定的基线前缀（活文件被正确追加不影响本自检；前缀对不上时先红在这里，指向 S08）。"""
    data = _read(REPO_ROOT / ROLES_CSS_REL).encode("utf-8")
    assert sha_prefix_ok(data, *ROLES_CSS_BASELINE), "roles-styles.css 的基线前缀对不上：活文件被改过（看 S08 的报告）"
    baseline = data[:ROLES_CSS_BASELINE[0]].decode("utf-8")
    assert css_tail_problems(baseline + "\n.rl-hub .tt-table { min-width: 760px; } /* 画布：七端岗位表最小宽 */\n") == []
    mutations = {
        "没有追加 .rl-hub 规则": baseline,
        "十六进制颜色": baseline + "\n.rl-hub .tt-table { min-width: 760px; background: #ff0000; } /* 画布 */\n",
        "px 没有出处注释": baseline + "\n.rl-hub .tt-table { min-width: 760px; }\n",
        "拼接令牌名": baseline + "\n.rl-hub .tt-table { min-width: 760px; color: var('--tt-' + n); } /* 画布 */\n",
        "改了基线部分": "/* 动了 */\n" + baseline[6:],
    }
    for label, text in mutations.items():
        problems = css_tail_problems(text)
        assert problems, f"改坏样「{label}」应当被抓到"


def test_gate_selfcheck_probe_sources():
    """探针（trans 已退役）：括号配对、每个 describe 至少一条用例、describe 名单与 PROBE_ORDER 对得上、不含禁用词。"""
    assert set(PROBE_ORDER) == set(PROBE_SPECS)
    for key in PROBE_ORDER:
        source = PROBE_SPECS[key][0]
        for op, cl in (("(", ")"), ("[", "]"), ("{", "}")):
            assert source.count(op) == source.count(cl), f"探针 {key} 的 {op}{cl} 不配对"
        groups = probe_groups(source)
        assert groups and all(n > 0 for n in groups.values()), f"探针 {key} 有空的 describe：{groups}"
        assert sum(groups.values()) == probe_count(source), f"探针 {key} 的用例没都落在 describe 里"
        for word in NET_WORDS + SINK_WORDS:
            assert word not in source, f"探针 {key} 自己不该含禁用词 {word[:4]}…"
        for line in source.splitlines():
            stripped = line.strip()
            assert not re.match(r"^(it|describe)\(\s*$", stripped), f"探针 {key} 的 it/describe 名字要与调用同行"
