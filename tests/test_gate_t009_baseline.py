"""T009 战前门禁：桌面端前端只读页面一（总览、角色与模型、CLI 运行时，第八片）的黑盒基准测试（合同 t009-desktop-pages-a，plan_version 1）。

被测对象是 ``desktop/web/``：三个真页面（``src/pages/{Overview,Roles,Runtimes}Page.tsx``）、``src/pages/readonly1/`` 下的视图与纯函数、
两个通用组件（RelativeTime、ActorTag）、四个新图标（PlusIcon、SearchIcon、PlayIcon、ArrowRightIcon）、
T006 的两处加法改动（``shell/router.ts`` 的 navigate 合并查询参数与 ``useAppNavigate``；``shell/attemptGroups.ts`` 的分组 ID 与
``groupOfState``），以及 ``tests/shell-app.test.tsx`` 里站主 Q2 批准改的那一条。

基线（6ec75f1，T006 结项加 T008 登记）上这些都还没有，所以本文件的“失败”断言落在目标文件不存在或内容不符上，不是导入、收集或语法错误：
模块级只导入标准库，用到被测文件的地方都在用例函数里读；候选里还没有任何本片的新源码文件时，``pipeline`` 夹具不跑 npm
（没有东西可测，也省掉联网的 ``npm ci``），用到它的用例以断言失败写明原因。

结构（编号对应合同 DoD 的 D01–D14；门禁端加了若干静态守卫和自检）：

- 静态断言（不用流水线，全量 pytest 也跑）：文件在位、router.ts 与 attemptGroups.ts 的加法形状、``components/index.ts`` 与
  ``icons/index.tsx`` 只在末尾追加、四个图标的形状、禁用词与源码规则、CSS 取值（合同 §8，用“有一条规则同时声明了这几项”的写法，
  不依赖合同没定的类名）、px 出处注释、W4、三页的接线写法（稳定的 load、isEmpty）、视图不调 api、执行端 8 份测试在位且不用 skip、
  ``shell-app.test.tsx`` 只改了那一条。
- 流水线断言（全量 pytest 默认跳过，点名运行本文件才跑）：会话级夹具 ``pipeline`` 在 ``desktop/web`` 下按顺序跑 ``npm ci``、
  ``npm run build``、``npm test``、``npm run check:contract``，再把探针逐份写成 ``gate-probe/probe-t009-<唯一标识>-<键>.test.ts``，各用
  ``npm test -- gate-probe/<文件名> --reporter=json --outputFile=…`` 跑，``finally`` 里删除；前后各取一次 ``git status``。探针里每个
  ``describe`` 的名字以 D 编号或 TRANS 开头，Python 用例按名字分组核对（一组里有一条红，这组对应的 Python 用例就红）。
  探针不写 JSX（用 ``React.createElement``），这样门禁自检能用 ``node --check`` 先查语法。
- 门禁自检（``test_gate_selfcheck_*``，不依赖候选）：把检查函数喂给正确样本和若干改坏的样本；探针源码查括号配对和语法。

探针怎么取数：三页都只调 ``src/api.ts`` 的读函数，所以探针用 ``vi.mock('../src/api')`` 替换读函数（可注入任意数据、出错、挂起、
受控的延迟），然后挂载整个 App、读页面 DOM。合同没有写视图组件的属性名，门禁不碰视图的内部接口，只认合同写定的 DOM
约定（``data-page``、``data-metric``、``data-role``、``data-source``、``data-long-idle``、aria-label、按钮文字、标签文字）。
真夹具（``?mock=``）只在 TRANS 开头的探针组里用。

DoD 对应：

- D01：``test_d01_*`` 与 shell 探针（T2 导航合并、T3 分组函数）、overview 探针的指标卡与链接点击；
- D02、D03：overview 探针（需要你判断、运行中、待集成、复制三态）与 copyText 单测；D04：overview 探针的配置变更；
- D05：overview 探针的五态（注入数据）与 TRANS 探针（夹具）；
- D06–D09：roles 探针（角色卡、当前方案、profile 表、方案表、差异面板）；D10：runtimes 探针；
- D11：pages 探针（写入口全部禁用、悬停出提示、可用按钮白名单；夹具下的个数 13 与 9 是过渡断言）；
- D12：common 探针（RelativeTime、ActorTag、导出、图标）与 ``test_d12_*``；
- D13：CSS 取值、源码规则、W4、px 注释；D14：回归（npm 四步、执行端测试在位、shell-app 只改一条、流水线不改工作区）。
  V02、V03 由合同另证；改动范围由调度器的范围门禁证明（这里不写相对基线的范围断言）。

过渡断言（``test_transitional_`` 开头，docstring 第一行写明哪项后续工作会推翻）：经 ``?mock=`` 渲染 App 三页的五态与夹具具体值
（指标 1/2/1/1、写入口个数 13 与 9）；``shell-app.test.tsx`` 只改那一条（后续任何再改这份测试的片推翻）。其余（视图行为、纯函数、
通用组件、图标、CSS 取值、源码规则、写入口全部禁用这条规则）是长期断言。

门禁做不到、留给人的项：视觉对照（暗/亮主题、1024 窄窗口）、悬停手感、读屏、真浏览器里的点击与导航。

合同没有写死、门禁端按最合理读法定下的地方（交付信“需协调人决定”里逐条列出，终审可改）：见 ``ASSUMPTIONS``。
"""

import hashlib
import json
import os
import posixpath
import re
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "6ec75f1f6970d0bf45ff8ee91f1a61ef3f6cd785"
WEB_REL = "desktop/web"
WEB = REPO_ROOT / "desktop" / "web"
SRC_REL = f"{WEB_REL}/src"
SRC = WEB / "src"
COMP_REL = f"{SRC_REL}/components"
RO_REL = f"{SRC_REL}/pages/readonly1"
TESTS_REL = f"{WEB_REL}/tests"

ASSUMPTIONS = (
    "合同没写视图组件（OverviewView 等）的属性名：门禁不直接渲染视图，经 vi.mock 替换 api.ts 的读函数、挂载整个 App 来注入数据",
    "合同 v2 §3 定了 ActorTag 的属性（actor: string 必填，className? 可选）与 RelativeTime 的 now?: number（毫秒）：探针只用这些名字与类型",
    "RelativeTime 的 title（合同 v2 §3）：说明文字写“title 为「本地时间 YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）」”，同一条又写“前面不带「本地」二字”并给了恰为 `2026-10-18 10:02:11（UTC 02:02:11）` 的例子；门禁按例子读：无前缀。这一处措辞有歧义，交一审裁定",
    "运行中行的“已用 … 与工具调用 N 次”之间的连接符合同没定：只查两段文字都在（忽略空白）",
    "data-long-idle 的取值形式合同没定：long_idle 真的行属性存在且不是 \"false\"，假的行属性不存在或为 \"false\"",
    "角色表“能担任”按 runtime id 对应（夹具里 id 与 adapter 同名）；探针只用 id 与 adapter 相同的行，不碰两者不同的情形",
    "方案表当前行是否也带 [查看差异] 合同没定：只验非当前行的 [查看差异] 可用，当前行只验“当前方案不能删”且没有 [使用]、[删除…]",
    "差异面板里的“→”可能是文字也可能是 ArrowRightIcon：探针把它当可有可无，只查角色名、减号绑定、加号绑定的先后",
    "checks 为 \"-\"、null 或空串都算“没有检查”，不显示“检查 …”；wall_seconds 为 null 不显示用时",
    "动作的中文说明：config.set=设置配置键、preset.use=切换方案、runtime.add=登记 runtime（History 画布原文）、config.rollback=回滚配置、role.set=修改角色绑定、external=检测到界面与命令之外的改动 逐字验；其余成对的写法（unset、save、remove、profile.*、runtime.remove）只验动词与名词都在",
    "href 精确值只在地址里没有查询串时验（挂载在 #/overview、#/roles、#/runtimes）；带 ?mock= 时只验点击后的路由",
    "指标卡色调条的颜色：读 CSS 文件，用探针导出的每张卡独有的类名与 data-* 当钩子，要求钩子所在规则引用对应令牌（info、accent、escalate、brand），不引用另外三种",
)

# 合同 Scope 的新增源码（allowed_new_files 里的非测试文件）。common-copyText.ts 不再列：T013 把它并进
# src/components/copyText.ts、删掉这一份（站主按 T013 规划 §8.1 R1 退役）
NEW_SOURCE_FILES = (
    f"{RO_REL}/common-Section.tsx",
    f"{RO_REL}/common-section.css",
    f"{RO_REL}/common-links.ts",
    f"{RO_REL}/common-CopyNote.tsx",
    f"{RO_REL}/overview-OverviewView.tsx",
    f"{RO_REL}/overview-MetricCard.tsx",
    f"{RO_REL}/overview-AttemptList.tsx",
    f"{RO_REL}/overview-ConfigChanges.tsx",
    f"{RO_REL}/overview-logic.ts",
    f"{RO_REL}/overview-styles.css",
    f"{RO_REL}/roles-RolesView.tsx",
    f"{RO_REL}/roles-RoleCard.tsx",
    f"{RO_REL}/roles-PresetBar.tsx",
    f"{RO_REL}/roles-ProfilesTable.tsx",
    f"{RO_REL}/roles-PresetsTable.tsx",
    f"{RO_REL}/roles-PresetDiff.tsx",
    f"{RO_REL}/roles-logic.ts",
    f"{RO_REL}/roles-styles.css",
    f"{RO_REL}/runtimes-RuntimesView.tsx",
    f"{RO_REL}/runtimes-logic.ts",
    f"{RO_REL}/runtimes-styles.css",
    f"{COMP_REL}/RelativeTime.tsx",
    f"{COMP_REL}/ActorTag.tsx",
)
# copyText 在哪一份就测哪一份：T013 之前在 readonly1，之后在 src/components（T013 规划 §8.1 R2、R3）
COPY_TEXT_REL = next((rel for rel in (f"{COMP_REL}/copyText.ts", f"{RO_REL}/common-copyText.ts")
                      if (REPO_ROOT / rel).is_file()), f"{RO_REL}/common-copyText.ts")
COPY_TEXT_MODULE = "../" + COPY_TEXT_REL[len(WEB_REL) + 1:-len(".ts")]
PAGE_FILES = {
    "overview": f"{SRC_REL}/pages/OverviewPage.tsx",
    "roles": f"{SRC_REL}/pages/RolesPage.tsx",
    "runtimes": f"{SRC_REL}/pages/RuntimesPage.tsx",
}
CSS_FILES = {
    "common": f"{RO_REL}/common-section.css",
    "overview": f"{RO_REL}/overview-styles.css",
    "roles": f"{RO_REL}/roles-styles.css",
    "runtimes": f"{RO_REL}/runtimes-styles.css",
}
# 合同第 9 节：执行端 8 份测试
EXECUTOR_TESTS = ("page-logic.test.ts", "page-common.test.tsx", "page-overview.test.tsx", "page-roles.test.tsx",
                  "page-runtimes.test.tsx", "page-app.test.tsx", "page-css.test.ts", "page-static.test.ts")

# 三页可以从 api.ts 取的读函数（合同第 2 条）
ALLOWED_API_READS = ("getStatus", "getHistory", "getMeta", "getMetaNow", "getRoles", "getProfiles", "getPresets",
                     "diffPresets", "getRuntimes")

# 合同 §3.4 的分组状态码（分组只来自 attemptGroups，页面源码里不得自己写）
STATE_CODES = ("PREPARING", "RUNNING", "COLLECTING", "NEEDS_REVIEW", "TIMEOUT", "CANCELLED", "INFRA_FAILURE", "ESCALATE",
               "BLOCKED", "PASS", "ACCEPTED_WITH_EXCEPTION", "INTEGRATED", "REVISE", "ABANDONED", "SUPERSEDED", "PREPARE_FAILED")

# 合同第 3 节：四个新图标
ICON_SHAPES = {
    "PlusIcon": {"paths": ["M5 12h14", "M12 5v14"], "circles": [], "polygons": []},
    "SearchIcon": {"paths": ["m21 21-4.3-4.3"], "circles": [{"cx": "11", "cy": "11", "r": "8"}], "polygons": []},
    "PlayIcon": {"paths": [], "circles": [], "polygons": ["6 3 20 12 6 21 6 3"]},
    "ArrowRightIcon": {"paths": ["M5 12h14", "m12 5 7 7-7 7"], "circles": [], "polygons": []},
}
NEW_EXPORTS = ("RelativeTime", "RelativeTimeProps", "ActorTag", "ActorTagProps")
# 基线（6ec75f1）components/index.ts 与 icons/index.tsx 的字节数与 sha256（行尾归一为 LF）：证明“只在末尾追加”
BASELINE_APPEND_ONLY = {
    f"{COMP_REL}/index.ts": (3737, "7feb56bd4bf1bd011330f8e93d36eafa026d12adda1a1e83da6ce04b8ac2226c"),
    f"{SRC_REL}/icons/index.tsx": (8167, "3f92cc6b8ac03896429e01be00f7cf2bdf36d6b267780787f83548e5eac3ffef"),
}
BASELINE_EXPORTS = (
    "Button", "ButtonProps", "Tag", "TagProps", "StatusTag", "StatusTagProps", "Card", "CardProps", "Banner", "BannerProps",
    "IconButton", "IconButtonProps", "Tooltip", "TooltipProps", "Menu", "MenuProps", "Dialog", "DialogProps", "Drawer", "DrawerProps",
    "Toast", "ToastProps", "SegmentedControl", "SegmentedControlProps", "Switch", "SwitchProps", "Checkbox", "CheckboxProps",
    "Tabs", "TabsProps", "TextField", "TextFieldProps", "Select", "SelectProps", "Table", "TableProps", "KeyValueList",
    "KeyValueListProps", "EmptyState", "EmptyStateProps", "Skeleton", "SkeletonProps", "ConnectionPill", "ConnectionPillProps",
    "Breadcrumb", "BreadcrumbProps", "TextViewer", "TextViewerProps", "SafeMarkdown", "SafeMarkdownProps", "EffortPair",
    "EffortPairProps", "MaskedValue", "MaskedValueProps", "isMaskedPlaceholder", "CommandLine", "CommandLineProps", "dispatchCommand",
    "NextStep", "NextStepProps", "DiffView", "DiffViewProps", "LogFollow", "LogFollowProps",
)
# 基线 tests/shell-app.test.tsx：第 1–31 行与第 38 行起（第 32–37 行是站主 Q2 批准改的那一条），行尾归一为 LF
SHELL_APP_PREFIX = (1308, "be1b2d2a9806001e193f5ed3a845f751fe8bb0bcaf6a39e97592840bc7787177")
SHELL_APP_SUFFIX = (2246, "55949b3e9f074580747dd0be2a9b614638d8019643e822567ed29b00c6b6fe08")


def _join(*parts):
    return "".join(parts)


# 四个浏览器网络词（T006）与 T007 禁用词。拼接写出，使本文件与探针源码自己不含这些词。
NET_WORDS = (_join("fe", "tch"), _join("XMLHttp", "Request"), _join("Event", "Source"), _join("Web", "Socket"))
SINK_WORDS = (_join("dangerously", "SetInner", "HTML"), _join("inner", "HTML"), _join("outer", "HTML"),
              _join("insertAdjacent", "HTML"), _join("ev", "al("), _join("new ", "Function"),
              _join("document", ".write"), _join("src", "doc"), _join("createContextual", "Fragment"),
              _join("DOM", "Parser"))
FONT_WORDS = (_join("@font", "-face"), _join("Font", "Face"), ".woff", ".ttf", ".otf", ".eot")
FORBIDDEN_CALLS = ("matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver")

# 合同 v2 检查项 V01 的 timeout 是 600s（v1 是 2400s）：夹具总预算压在 560s 以内，用完就停下并在断言里写明，不等调度器来杀。
# 各步上限之和大于总预算，总预算在后面的步骤上起作用：流水线整体跑不进 560s 时，靠后的探针以“未运行”失败。
PIPELINE_BUDGET = 560
STEP_CAPS = {
    "npm ci": 180,
    "npm run build": 100,
    "npm test": 200,
    "npm run check:contract": 30,
    "probe": 100,
}

# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def need_file(rel):
    """断言仓库里的文件存在，返回路径。基线上到这里就以断言失败。"""
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return path


def need_new_sources():
    missing = [rel for rel in NEW_SOURCE_FILES if not (REPO_ROOT / rel).is_file()]
    assert not missing, f"缺少本片的新文件（基线上还没有实现）：{missing}"


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


def norm_ws(value):
    return re.sub(r"\s+", " ", value.strip())


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:40])


def strip_ts_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(^|[^:'\"`])//[^\n]*", r"\1", text)


def sha_prefix_ok(data, size, digest):
    return len(data) >= size and hashlib.sha256(data[:size]).hexdigest() == digest


# ---------------------------------------------------------------------------
# CSS 小解析器：规则、声明；选择器列表按顶层逗号切
# ---------------------------------------------------------------------------

def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def split_top(text, sep=","):
    """按顶层 sep 切（圆括号、方括号、引号里的不算）。"""
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


def split_decls(body):
    decls = []
    for part in split_top(body, ";"):
        if not part:
            continue
        name, _sep, value = part.partition(":")
        decls.append((name.strip().lower(), value.strip()))
    return decls


NESTING_AT_RULES = re.compile(r"@(?:media|supports|container|layer|document)\b", re.I)


def parse_rules(css):
    """返回 [(选择器, [(名, 值)…])]；@media、@container 等包裹块里的规则展平，@keyframes 不展开。"""
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
                if NESTING_AT_RULES.match(prelude):
                    walk(body)
            else:
                out.append((norm_ws(prelude), split_decls(body)))
            i = k

    walk(css)
    return out


def cv(value):
    """归一值：去 !important，所有空白去掉，小写。"""
    return re.sub(r"\s+", "", re.sub(r"!important", "", value or "", flags=re.I)).lower()


def is_zero(value):
    return value in ("0", "0px", "0%")


def C(names, eq=None, has=(), zero=False):
    """一条声明条件：names 里的某个属性，归一后的值等于 eq / 含 has 里每一段 / 是 0。"""
    if isinstance(names, str):
        names = (names,)
    return ("decl", tuple(names), eq, tuple(has), zero)


def AnyOf(*conds):
    return ("any", conds)


def HasAll(names, *tokens):
    """条件：names 里所有声明的值拼起来，含全部 tokens（容忍 gap 与 row-gap/column-gap 两种写法）。"""
    names = (names,) if isinstance(names, str) else tuple(names)

    def check(decls):
        joined = "|".join(cv(v) for n, v in decls if n in names)
        return bool(joined) and all(cv(t) in joined for t in tokens)
    return check


def cond_ok(decls, cond):
    if callable(cond):
        return bool(cond(decls))
    if cond[0] == "any":
        return any(cond_ok(decls, c) for c in cond[1])
    _tag, names, eq, has, zero = cond
    for name, value in decls:
        if name not in names:
            continue
        v = cv(value)
        if zero:
            if is_zero(v):
                return True
            continue
        if eq is not None and v != cv(eq):
            continue
        if any(cv(h) not in v for h in has):
            continue
        return True
    return False


def sel_ok(selector, sel):
    if sel is None:
        return True
    if callable(sel):
        return bool(sel(selector))
    return bool(re.search(sel, selector))


def group_problems(css, label, specs):
    """specs: [(说明, 选择器正则/函数或 None, [条件…])]；每条都要有一条规则同时满足全部条件。"""
    problems = []
    rules = parse_rules(css)
    for desc, sel, conds in specs:
        hit = False
        for selector, decls in rules:
            if not sel_ok(selector, sel):
                continue
            if all(cond_ok(decls, c) for c in conds):
                hit = True
                break
        if not hit:
            where = "（带选择器条件）" if sel else ""
            problems.append(f"{label}：{desc}——没有一条规则同时满足{where}")
    return problems


def box_sides(decls, prop):
    """padding / margin 的四边（归一值；0 记 '0'）：shorthand 与 -top 等长写法按源码顺序叠加。"""
    sides = {"top": None, "right": None, "bottom": None, "left": None}

    def norm(v):
        v = cv(v)
        return "0" if is_zero(v) else v

    for name, value in decls:
        parts = [p for p in split_top(value.strip(), " ") if p]
        if name == prop and parts:
            if len(parts) == 1:
                t = r = b = l = parts[0]
            elif len(parts) == 2:
                t = b = parts[0]
                r = l = parts[1]
            elif len(parts) == 3:
                t, r, l, b = parts[0], parts[1], parts[1], parts[2]
            else:
                t, r, b, l = parts[:4]
            sides.update(top=norm(t), right=norm(r), bottom=norm(b), left=norm(l))
        elif name in (f"{prop}-top", f"{prop}-block-start") and parts:
            sides["top"] = norm(parts[0])
        elif name in (f"{prop}-bottom", f"{prop}-block-end") and parts:
            sides["bottom"] = norm(parts[0])
        elif name in (f"{prop}-left", f"{prop}-inline-start") and parts:
            sides["left"] = norm(parts[0])
        elif name in (f"{prop}-right", f"{prop}-inline-end") and parts:
            sides["right"] = norm(parts[0])
        elif name == f"{prop}-inline" and parts:
            sides["left"] = norm(parts[0])
            sides["right"] = norm(parts[-1])
        elif name == f"{prop}-block" and parts:
            sides["top"] = norm(parts[0])
            sides["bottom"] = norm(parts[-1])
    return sides


def sides_is(prop, **want):
    def check(decls):
        got = box_sides(decls, prop)
        return all(got.get(side) == ("0" if is_zero(cv(v)) else cv(v)) for side, v in want.items())
    return check


def px_literal_problems(label, css_raw):
    """合同公共约定：尺寸字面量同一行带出处注释。除 0 与 1px 外的 px 字面量，所在行（去掉注释后）有 px，该行又没有注释，就记一条问题。"""
    problems = []
    in_comment = False
    for no, line in enumerate(css_raw.splitlines(), 1):
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
                problems.append(f"{label}:{no}: {m.group(0)} 没有同一行的出处注释：{line.strip()[:80]}")
    return problems


def token_only_problems(label, css):
    """合同公共约定：层级、圆角、阴影、字体只用 --tt-* 令牌（颜色由 W4 另查）。"""
    problems = []
    for selector, decls in parse_rules(css):
        for name, value in decls:
            v = cv(value)
            if name == "z-index" and not v.startswith("var(--tt-z-"):
                problems.append(f"{label}：{selector} 的 z-index 应取 --tt-z-* 令牌，实际 {value}")
            elif name == "border-radius" and not re.fullmatch(r"(?:var\(--tt-radius-[\w-]+\)|0|0px|inherit)+", v):
                problems.append(f"{label}：{selector} 的 border-radius 应取 --tt-radius-* 令牌，实际 {value}")
            elif name == "box-shadow" and v != "none" and "var(--tt-" not in v:
                problems.append(f"{label}：{selector} 的 box-shadow 应取令牌，实际 {value}")
            elif name in ("font", "font-family", "font-size") and not (v.startswith("var(--tt-") or v == "inherit"):
                problems.append(f"{label}：{selector} 的 {name} 应取 --tt-* 字体令牌或 inherit，实际 {value}")
    return problems


# ---------------------------------------------------------------------------
# 合同 §8 的 CSS 取值（不依赖合同没定的类名：每条是“有一条规则同时声明了这几项”）
# ---------------------------------------------------------------------------

def tok(name):
    return f"var(--tt-{name})"


def bg(value):
    return C(("background", "background-color"), eq=value)


def look(*words):
    return lambda selector: any(w in selector for w in words)


# 区块卡、头部、说明、右侧链接（common-section.css）；指标卡、attempt 行、配置变更行、下一步与复制结果、计数胶囊（overview-styles.css）
COMMON_SPECS = [
    ("区块卡：背景 surface-1、1px --tt-border 边框、--tt-radius-lg 圆角", None,
     [bg(tok("surface-1")), C("border", eq="1px solid var(--tt-border)"), C("border-radius", eq=tok("radius-lg"))]),
    ("区块头部内边距 --tt-space-3 --tt-space-4", None, [sides_is("padding", top=tok("space-3"), bottom=tok("space-3"), left=tok("space-4"), right=tok("space-4"))]),
    ("h2 用 --tt-title-sm", None, [C("font", eq=tok("title-sm"))]),
    ("说明文字用 --tt-text-caption、--tt-text-3", None, [C("font", eq=tok("text-caption")), C("color", eq=tok("text-3"))]),
    ("右侧链接用 --tt-text-sm、--tt-link、无下划线", None,
     [C("font", eq=tok("text-sm")), C("color", eq=tok("link")), C("text-decoration", eq="none")]),
]
OVERVIEW_SPECS = [
    ("指标卡网格四列 minmax(0,1fr)、间距 --tt-space-4", None,
     [C("grid-template-columns", eq="repeat(4, minmax(0, 1fr))"), HasAll(("gap", "column-gap"), tok("space-4"))]),
    ("指标卡：surface-1 背景、1px --tt-border 边框、--tt-radius-lg", None,
     [bg(tok("surface-1")), C("border", eq="1px solid var(--tt-border)"), C("border-radius", eq=tok("radius-lg"))]),
    ("指标卡 overflow hidden", None, [C("overflow", eq="hidden")]),
    ("指标卡无下划线", None, [C("text-decoration", eq="none")]),
    ("指标卡内边距 --tt-space-3 --tt-space-4 --tt-space-3 --tt-space-5", None,
     [sides_is("padding", top=tok("space-3"), right=tok("space-4"), bottom=tok("space-3"), left=tok("space-5"))]),
    ("指标卡悬停 --tt-surface-2", ":hover", [bg(tok("surface-2"))]),
    ("色调条宽 3px", None, [AnyOf(C("width", eq="3px"), C("height", eq="3px"), C("flex-basis", eq="3px"))]),
    ("指标数字用 --tt-display", None, [C("font", eq=tok("display"))]),
    ("需要你判断：左边框 3px solid --tt-accent", None, [C(("border-left", "border-inline-start"), eq="3px solid var(--tt-accent)")]),
    ("计数胶囊：最小宽 20、高 18、--tt-radius-full、--tt-accent 底、--tt-on-accent 字、--tt-text-caption-strong", None,
     [C("min-width", eq="20px"), C(("height", "min-height"), eq="18px"), C("border-radius", eq=tok("radius-full")),
      bg(tok("accent")), C("color", eq=tok("on-accent")), C("font", eq=tok("text-caption-strong"))]),
    ("attempt 行四列 104px minmax(0,1fr) auto auto、间距 --tt-space-3", None,
     [C("grid-template-columns", eq="104px minmax(0, 1fr) auto auto"), HasAll(("gap", "column-gap"), tok("space-3"))]),
    ("attempt 行最小高 44、左右 --tt-space-4、上边框 1px --tt-border", None,
     [C(("min-height", "height"), eq="44px"), sides_is("padding", left=tok("space-4"), right=tok("space-4")),
      C("border-top", eq="1px solid var(--tt-border)")]),
    ("attempt 行悬停 --tt-surface-3", ":hover", [bg(tok("surface-3"))]),
    ("行内链接：高 28、左右 --tt-space-2、--tt-radius-md、--tt-text-sm-medium、无下划线", None,
     [C(("height", "min-height"), eq="28px"), sides_is("padding", left=tok("space-2"), right=tok("space-2")),
      C("border-radius", eq=tok("radius-md")), C("font", eq=tok("text-sm-medium")), C("text-decoration", eq="none")]),
    ("信息文字 --tt-text-sm / --tt-text-2", None, [C("font", eq=tok("text-sm")), C("color", eq=tok("text-2"))]),
    ("配置变更行五列 48px 92px 120px minmax(0,1fr) auto、间距 --tt-space-3", None,
     [C("grid-template-columns", eq="48px 92px 120px minmax(0, 1fr) auto"), HasAll(("gap", "column-gap"), tok("space-3"))]),
    ("配置变更行高 36、左右 --tt-space-4", None,
     [C(("height", "min-height"), eq="36px"), sides_is("padding", left=tok("space-4"), right=tok("space-4"))]),
    ("下一步与复制结果外边距 --tt-space-3 --tt-space-4 --tt-space-4", None,
     [sides_is("margin", top=tok("space-3"), right=tok("space-4"), bottom=tok("space-4"), left=tok("space-4"))]),
    ("复制结果行 --tt-text-caption / --tt-text-3", None, [C("font", eq=tok("text-caption")), C("color", eq=tok("text-3"))]),
]
LAST_COL = look(":last-child", ":last-of-type", ":nth-last-child(1)")
TABLE_WRAP = lambda selector: ".tt-table-wrap" in selector and selector.count(".") >= 2
ROLES_SPECS = [
    ("当前方案区块：flex 可换行、间距 --tt-space-3 --tt-space-4、内边距 --tt-space-3 --tt-space-4", None,
     [C("display", eq="flex"), C("flex-wrap", eq="wrap"), HasAll("gap", tok("space-3"), tok("space-4")),
      sides_is("padding", top=tok("space-3"), bottom=tok("space-3"), left=tok("space-4"), right=tok("space-4"))]),
    ("角色卡网格两列 minmax(0,1fr)、间距 --tt-space-4", None,
     [C("grid-template-columns", eq="repeat(2, minmax(0, 1fr))"), HasAll(("gap", "column-gap"), tok("space-4"))]),
    ("角色卡内边距 --tt-space-4", None, [C("padding", eq=tok("space-4"))]),
    ("角色卡纵向间距 --tt-space-2", None, [HasAll(("gap", "row-gap"), tok("space-2"))]),
    ("键值两列 64px minmax(0,1fr)", None, [C("grid-template-columns", eq="64px minmax(0, 1fr)")]),
    ("表格容器压过 .tt-table-wrap：无边框无圆角、上边框 1px --tt-border", TABLE_WRAP,
     [AnyOf(C("border", eq="0"), C("border", eq="none"), C("border-width", eq="0")), C("border-radius", zero=True),
      C("border-top", eq="1px solid var(--tt-border)")]),
    ("profile 表最小宽 860", None, [C("min-width", eq="860px")]),
    ("方案表最小宽 760", None, [C("min-width", eq="760px")]),
    ("最后一列靠右", LAST_COL, [C("text-align", eq="right")]),
    ("差异面板：--tt-space-3 内边距、--tt-radius-md、--tt-surface-2、1px --tt-border", None,
     [C("padding", eq=tok("space-3")), C("border-radius", eq=tok("radius-md")), bg(tok("surface-2")),
      C("border", eq="1px solid var(--tt-border)")]),
    ("差异行四列 96px minmax(0,1fr) 24px minmax(0,1fr)", None,
     [C("grid-template-columns", eq="96px minmax(0, 1fr) 24px minmax(0, 1fr)")]),
    ("差异旧值底 --tt-diff-del", None, [bg(tok("diff-del"))]),
    ("差异新值底 --tt-diff-add", None, [bg(tok("diff-add"))]),
    ("差异值块：内边距 --tt-space-0_5 --tt-space-1、--tt-radius-sm、--tt-mono-sm", None,
     [sides_is("padding", top=tok("space-0_5"), bottom=tok("space-0_5"), left=tok("space-1"), right=tok("space-1")),
      C("border-radius", eq=tok("radius-sm")), C("font", eq=tok("mono-sm"))]),
]
RUNTIMES_SPECS = [
    ("表格容器压过 .tt-table-wrap：无边框无圆角、上边框 1px --tt-border", TABLE_WRAP,
     [AnyOf(C("border", eq="0"), C("border", eq="none"), C("border-width", eq="0")), C("border-radius", zero=True),
      C("border-top", eq="1px solid var(--tt-border)")]),
    ("运行时表最小宽 900", None, [C("min-width", eq="900px")]),
    ("最后一列靠右", LAST_COL, [C("text-align", eq="right")]),
    ("命令单元格：最大宽 280、等宽、单行、超出隐藏", None,
     [C("max-width", eq="280px"), C("overflow", eq="hidden"), C("white-space", eq="nowrap")]),
    ("就绪检查空框：内边距 --tt-space-5、居中", None, [C("padding", eq=tok("space-5")), C("text-align", eq="center")]),
    ("就绪检查空框：1px dashed --tt-border-strong、--tt-radius-md", None,
     [C("border", eq="1px dashed var(--tt-border-strong)"), C("border-radius", eq=tok("radius-md"))]),
    ("就绪检查空框文字 --tt-text-sm / --tt-text-3", None, [C("font", eq=tok("text-sm")), C("color", eq=tok("text-3"))]),
]
# 合同 §8 没规定哪条规则写在哪份文件：四份 CSS 合并成一个规则集后逐条求值（px 注释、令牌、W4 仍逐文件查）
ALL_SPECS = COMMON_SPECS + OVERVIEW_SPECS + ROLES_SPECS + RUNTIMES_SPECS


def css_text(key):
    return _read(REPO_ROOT / CSS_FILES[key])


def css_value_problems(texts=None):
    """texts: {键: CSS 文本}，缺省读四份真文件；把它们拼成一个规则集后求值 §8 的每一条。"""
    texts = {key: css_text(key) for key in CSS_FILES} if texts is None else texts
    return group_problems("\n".join(texts[key] for key in CSS_FILES if key in texts), "readonly1 的四份 CSS 合并", ALL_SPECS)


# 指标卡色调条：钩子（每张卡独有的类名与 data-*）所在规则要引用对应令牌
TONE_TOKENS = {"running": "tone-info-fg", "review": "accent", "decide": "tone-escalate-fg", "integrate": "tone-brand-fg"}


def tone_problems(css, metrics):
    """metrics: [{"metric": id, "hooks": [".cls", "[data-x=v]", …]}]；返回问题列表。"""
    problems = []
    rules = parse_rules(css)
    hooks = {m["metric"]: set(m.get("hooks", [])) for m in metrics}
    for metric, token in TONE_TOKENS.items():
        if metric not in hooks:
            problems.append(f"没有读到指标卡 {metric} 的钩子数据")
            continue
        others = set().union(*(h for k, h in hooks.items() if k != metric))
        mine = {h for h in hooks[metric] if h not in others}
        if not mine:
            problems.append(f"指标卡 {metric} 没有独有的类名或 data-* 可以挂色调")
            continue
        wanted = re.compile(rf"var\(--tt-{re.escape(token)}\)")
        wrong = [re.compile(rf"var\(--tt-{re.escape(t)}\)") for k, t in TONE_TOKENS.items() if k != metric]
        found = False
        for selector, decls in rules:
            sel = selector.replace('"', "").replace("'", "")
            if not any(h in sel for h in mine):
                continue
            values = " ".join(v for _n, v in decls)
            if wanted.search(values):
                found = True
            for w in wrong:
                if w.search(values):
                    problems.append(f"指标卡 {metric} 的规则 {selector} 引用了别的卡的色调令牌：{values[:60]}")
        if not found:
            problems.append(f"指标卡 {metric} 的独有钩子 {sorted(mine)[:4]} 所在规则没有引用 var(--tt-{token})")
    return problems


# ---------------------------------------------------------------------------
# 源码侧的检查函数
# ---------------------------------------------------------------------------

def index_exports(text):
    """components/index.ts 导出的名字集合（含 export type 与 as 改名）。"""
    text = strip_ts_comments(text)
    names = set()
    for m in re.finditer(r"export\s+(?:type\s+)?\{([^}]*)\}", text):
        for part in m.group(1).split(","):
            part = re.sub(r"^\s*type\s+", "", part.strip())
            if part:
                names.add(part.split(" as ")[-1].strip())
    return names


def append_only_problems(rel, new_text):
    """基线内容（行尾归一后）是新内容的前缀：按字节数与 sha256 核对。"""
    size, digest = BASELINE_APPEND_ONLY[rel]
    data = new_text.replace("\r\n", "\n").encode("utf-8")
    if len(data) <= size:
        return [f"{rel}：新内容（{len(data)} 字节）应比基线（{size} 字节）长，本片要在末尾追加"]
    if hashlib.sha256(data[:size]).hexdigest() != digest:
        return [f"{rel}：基线内容不是新内容的前缀（只许在末尾追加，不许改已有的行、不许改文件头）"]
    return []


def index_problems(text, check_prefix=True):
    problems = append_only_problems(f"{COMP_REL}/index.ts", text) if check_prefix else []
    names = index_exports(text)
    for name in BASELINE_EXPORTS + NEW_EXPORTS:
        if name not in names:
            problems.append(f"components/index.ts 没有导出 {name}")
    if re.search(r"overlay", strip_ts_comments(text)):
        problems.append("components/index.ts 去掉注释后不该出现 overlay")
    if "共五片" not in text:
        problems.append("components/index.ts 的文件头注释应保持「共五片」（T007 门禁依赖）")
    return problems


def icon_block(text, name):
    m = re.search(rf"export\s+(?:const|function)\s+{name}\b", text)
    if not m:
        return None
    nxt = re.search(r"\nexport\s+(?:const|function|type|interface)\b", text[m.end():])
    return text[m.start(): m.end() + (nxt.start() if nxt else len(text))]


def tag_attrs(tag_text):
    got = {}
    for m in re.finditer(r"""(\w+)\s*=\s*(?:"([^"]*)"|'([^']*)'|\{\s*["']?([\d.]+)["']?\s*\})""", tag_text):
        got[m.group(1)] = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4))
    return got


def icon_problems(icons_text, check_prefix=True):
    problems = append_only_problems(f"{SRC_REL}/icons/index.tsx", icons_text) if check_prefix else []
    for name, want in ICON_SHAPES.items():
        if len(re.findall(rf"export\s+(?:const|function)\s+{name}\b", icons_text)) != 1:
            problems.append(f"icons/index.tsx 里 {name} 应恰好定义一份（开工先查重，同名只留一份）")
        block = icon_block(icons_text, name)
        if block is None:
            problems.append(f"icons/index.tsx 没有 export const {name}")
            continue
        if "<Svg" not in block:
            problems.append(f"{name} 应沿用 Svg 包装")
        paths = [tag_attrs(p).get("d") for p in re.findall(r"<path\b([^>]*)>", block)]
        if paths != want["paths"]:
            problems.append(f"{name} 的 path d 应依次为 {want['paths']}，实际 {paths}")
        circles = [tag_attrs(c) for c in re.findall(r"<circle\b([^>]*)>", block)]
        if circles != want["circles"]:
            problems.append(f"{name} 的 circle 应依次为 {want['circles']}，实际 {circles}")
        polys = [tag_attrs(p).get("points") for p in re.findall(r"<polygon\b([^>]*)>", block)]
        if polys != want["polygons"]:
            problems.append(f"{name} 的 polygon points 应为 {want['polygons']}，实际 {polys}")
        for attr in re.findall(r"\b(fill|stroke)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|\{[^}]*\})", block):
            value = attr[1] or attr[2]
            if value not in ("none", "currentColor"):
                problems.append(f"{name} 的 {attr[0]} 只许 none 或 currentColor，实际 {value!r}")
    return problems


def word_hit(text, word):
    if word.startswith(".") or "(" in word or " " in word or "@" in word:
        return word in text
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])", text) is not None


def src_ts_files():
    out = []
    for ext in ("ts", "tsx"):
        out += sorted(SRC.rglob(f"*.{ext}"))
    return out


def new_ts_sources():
    return [REPO_ROOT / rel for rel in NEW_SOURCE_FILES if rel.endswith((".ts", ".tsx")) and (REPO_ROOT / rel).is_file()]


def new_css_sources():
    return [REPO_ROOT / rel for rel in NEW_SOURCE_FILES if rel.endswith(".css") and (REPO_ROOT / rel).is_file()]


def page_sources():
    return [REPO_ROOT / rel for rel in PAGE_FILES.values() if (REPO_ROOT / rel).is_file()]


def forbidden_word_problems(files, words):
    problems = []
    for path in files:
        text = _read(path)
        label = path.relative_to(WEB).as_posix()
        for word in words:
            if word_hit(text, word):
                problems.append(f"{label} 出现禁用词 {word}")
        if word_hit(text, "ServerIcon"):
            problems.append(f"{label} 出现 ServerIcon")
    return problems


def role_and_interface_problems(label, raw):
    problems = []
    code = strip_ts_comments(raw)
    if re.search(r"""role\s*[=:]\s*\{?\s*["']status["']""", code):
        problems.append(f"{label}：不能渲染 role=status")
    for name in FORBIDDEN_CALLS:
        if re.search(rf"\b{name}\b", code):
            problems.append(f"{label}：不能用 {name}")
    if re.search(r"""\bstyle\s*=\s*(?:\{|["'])""", code):
        problems.append(f"{label}：不写内联 style")
    return problems


def state_literal_problems(files):
    """合同 D13：不另写 3.4 分组表。页面与视图源码里不出现分组状态码的字符串字面量。"""
    problems = []
    for path in files:
        code = strip_ts_comments(_read(path))
        label = path.relative_to(WEB).as_posix()
        for state in STATE_CODES:
            if re.search(rf"""["'`]{state}["'`]""", code):
                problems.append(f"{label}：出现状态码字面量 {state}（分组只来自 attemptGroups）")
    return problems


HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])")
COLOR_FUNC_RE = re.compile(r"\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(", re.I)


def w4_pitfall_problems(files):
    """W4 的坑（合同公共约定）：只剥块注释，字符串也扫；不出现井号加 3/4/6/8 位十六进制、颜色函数名加括号、拼接 --tt- 前缀。"""
    problems = []
    for path in files:
        text = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), _read(path), flags=re.S)
        label = path.relative_to(WEB).as_posix()
        for m in HEX_RE.finditer(text):
            problems.append(f"{label}:{text[:m.start()].count(chr(10)) + 1} 出现十六进制颜色形态 {m.group(0)}")
        for m in COLOR_FUNC_RE.finditer(text):
            problems.append(f"{label}:{text[:m.start()].count(chr(10)) + 1} 出现颜色函数形态 {m.group(0)}")
        for m in re.finditer(r"""[`'"][^`'"\n]*--tt-[^`'"\n]*\$\{""", text):
            problems.append(f"{label}:{text[:m.start()].count(chr(10)) + 1} 拼接了 --tt- 令牌名")
    return problems


def view_api_problems(files):
    """合同第 2 条：readonly1 的视图只收数据与回调，不调 api：从 ../../api 只能 import type。"""
    problems = []
    for path in files:
        code = strip_ts_comments(_read(path))
        label = path.relative_to(WEB).as_posix()
        for m in re.finditer(r"import\s+(type\s+)?([^;]*?)\s+from\s+['\"]((?:\.\./)+api)['\"]", code):
            if m.group(1):
                continue
            braces = re.fullmatch(r"\{([^}]*)\}", m.group(2).strip())
            if braces:
                specs = [s.strip() for s in braces.group(1).split(",") if s.strip()]
                if specs and all(re.match(r"type\s+\w", s) for s in specs):
                    continue  # import { type A, type B }：纯类型导入，不调 api
            problems.append(f"{label}：从 api 只许 import type，实际 import {m.group(2)[:60]}")
    return problems


def page_wiring_problems(page, text):
    """三页只取数并用 PageFrame；load、isEmpty 是模块级稳定函数（不内联）；只调读函数。"""
    problems = []
    code = strip_ts_comments(text)
    label = PAGE_FILES[page].rsplit("/", 1)[-1]
    if "PageFrame" not in code:
        problems.append(f"{label}：应使用 PageFrame")
    if "readonly1/" not in code:
        problems.append(f"{label}：应从 pages/readonly1/ 引入视图")
    if not re.search(r"load\s*=\s*\{\s*[A-Za-z_$][\w$]*\s*\}", code):
        problems.append(f"{label}：PageFrame 的 load 应是命名的模块级函数，不内联箭头函数")
    empty_attr = re.search(r"isEmpty\s*=\s*\{([^}]*)\}", code)
    if page == "roles":
        if empty_attr:
            problems.append(f"{label}：角色页不传 isEmpty（?mock=empty 时仍是 data）")
    else:
        if not empty_attr or not re.fullmatch(r"\s*[A-Za-z_$][\w$]*\s*", empty_attr.group(1)):
            problems.append(f"{label}：isEmpty 应是命名的模块级函数")
    for m in re.finditer(r"import\s+(type\s+)?\{([^}]*)\}\s*from\s*['\"]\.\./api['\"]", code):
        if m.group(1):
            continue
        for name in [n.strip() for n in m.group(2).split(",") if n.strip()]:
            name = re.sub(r"^type\s+", "", name).split(" as ")[0].strip()
            if name and name[0].islower() and name not in ALLOWED_API_READS:
                problems.append(f"{label}：只许调读函数 {ALLOWED_API_READS}，实际引入 {name}")
    return problems


def executor_test_problems():
    problems = []
    folder = WEB / "tests"
    for name in EXECUTOR_TESTS:
        path = folder / name
        if not path.is_file():
            problems.append(f"{WEB_REL}/tests/{name} 不存在（执行端要写的测试）")
            continue
        text = _read(path)
        if not re.search(r"^\s*(?:it|test)(?:\.each\([^)]*\))?\(", text, re.M):
            problems.append(f"{name} 里没有用例")
        for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b", r"\bit\.skipIf\b"):
            if re.search(bad, text):
                problems.append(f"{name} 里出现 {bad}（不许 skip、only、todo）")
    return problems


def shell_app_problems(text):
    """tests/shell-app.test.tsx 只改第 32–37 行那一条：前后两段与基线逐字相同，中间换成真页面断言。"""
    text = _norm(text)
    p_size, p_digest = SHELL_APP_PREFIX
    s_size, s_digest = SHELL_APP_SUFFIX
    data = text.encode("utf-8")
    problems = []
    if not sha_prefix_ok(data, p_size, p_digest):
        problems.append("shell-app.test.tsx 前 31 行（文件头、前三条用例）与基线不同；站主 Q2 只许改「总览占位显示夹具数据与条数」这一条")
    if len(data) < s_size or hashlib.sha256(data[len(data) - s_size:]).hexdigest() != s_digest:
        problems.append("shell-app.test.tsx 从「Ctrl+2 切到任务页」起的后面各条与基线不同；站主 Q2 只许改总览那一条")
    if len(data) <= p_size + s_size:
        problems.append("shell-app.test.tsx 中间那一条被删光了；应改成断言真页面")
        return problems
    middle = data[p_size:len(data) - s_size].decode("utf-8", "replace")
    if "夹具数据已读到" in middle:
        problems.append("总览那一条仍在断言占位文字「夹具数据已读到」；应改为断言真页面")
    if not re.search(r"^\s*it\(", middle, re.M):
        problems.append("总览那一条不见了（中间没有 it(）")
    if "data-page" not in middle or "overview" not in middle:
        problems.append("总览那一条应断言真页面（例如存在 [data-page=overview]）")
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\("):
        if re.search(bad, middle):
            problems.append(f"总览那一条里出现 {bad}")
    return problems


# ---------------------------------------------------------------------------
# 探针（Vitest + jsdom）：每份若干 describe，名字以 D 编号或 TRANS 开头，Python 用例按名字分组核对。
# 不写 JSX（React.createElement），探针源码是纯 TS，门禁自检用 node --check 查语法。
# ---------------------------------------------------------------------------

PRELUDE = r"""
import * as React from 'react';
import * as fs from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

const h: any = React.createElement;

// 排空 jsdom 里待决的导航与 hashchange（它们在宏任务里触发），使用例之间不互相泄漏（T006 门禁同款）
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
  vi.useRealTimers();
  window.location.hash = '';
  try {
    delete (window.navigator as any).clipboard;
  } catch (e) {
    // 没有就算了
  }
  await drainNav();
});

// 点击后由本门禁自己取消默认行为：返回「应用自己有没有 preventDefault」，且 jsdom 不会再对 a href 做待决导航
function clickKeepUrl(el: Element, init: any = {}): boolean {
  let appPrevented = false;
  const listener = (e: Event) => {
    appPrevented = e.defaultPrevented;
    e.preventDefault();
  };
  document.addEventListener('click', listener);
  try {
    fireEvent.click(el, init);
  } finally {
    document.removeEventListener('click', listener);
  }
  return appPrevented;
}

function textOf(el: any): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function squash(s: any): string {
  return String(s || '').replace(/\s+/g, '');
}
function qa(rootEl: any, sel: string): any[] {
  return Array.from(rootEl.querySelectorAll(sel));
}
function btns(rootEl: any, label: string): any[] {
  return qa(rootEl, 'button').filter((b) => textOf(b) === label);
}
function btn(rootEl: any, label: string): any {
  return btns(rootEl, label)[0] || null;
}
function tagWith(rootEl: any, text: string): any {
  return qa(rootEl, '.tt-tag').find((t) => textOf(t) === text) || null;
}
function svgWidth(el: any): string | null {
  const s = el && el.querySelector('svg');
  return s ? s.getAttribute('width') : null;
}
function advance(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}
async function flush() {
  for (let i = 0; i < 12; i += 1) {
    await act(async () => {
      await Promise.resolve();
    });
  }
}
function hashParts(): { path: string; params: Record<string, string>; raw: string } {
  const raw = window.location.hash.replace(/^#/, '');
  const q = raw.indexOf('?');
  const params: Record<string, string> = {};
  new URLSearchParams(q < 0 ? '' : raw.slice(q + 1)).forEach((v, k) => {
    params[k] = v;
  });
  return { path: q < 0 ? raw : raw.slice(0, q), params, raw };
}
const NOW = '2026-10-18T03:00:00.000Z';
function freeze() {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(NOW));
}
function pad2(n: number): string {
  return String(n).padStart(2, '0');
}
function titleOf(iso: string): string {
  const d = new Date(iso);
  return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()) + ' ' + pad2(d.getHours()) + ':'
    + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds()) + '（UTC ' + pad2(d.getUTCHours()) + ':' + pad2(d.getUTCMinutes())
    + ':' + pad2(d.getUTCSeconds()) + '）';
}
function stubClipboard(impl: any) {
  Object.defineProperty(window.navigator, 'clipboard', { value: impl, configurable: true });
}
"""

# 替换 api.ts 读函数的替身（T006 探针同款）：默认转调原函数，用例用 set() 换成任意信封、出错、挂起或受控的延迟
API_MOCK = r"""
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
function deferred(): { promise: Promise<any>; resolve: (v: any) => void } {
  let resolve: any = null;
  const promise = new Promise<any>((r) => {
    resolve = r;
  });
  return { promise, resolve };
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
// 总览与运行时页的 section 都是带 h2 的区块（合同：区块 section + aria-labelledby 指 h2）；出现没有标题的 section 时给出明确提示。
// 角色页的「当前方案」条合同没写标题，所以角色页不用这个检查。
function expectAllSectionsTitled(rootEl: any) {
  qa(rootEl, 'section').forEach((s) => {
    const id = s.getAttribute('aria-labelledby');
    const head = id ? document.getElementById(id) : null;
    expect(head && head.tagName, '有一个 section 没有 aria-labelledby 指向的 h2：' + textOf(s).slice(0, 40)).toBe('H2');
  });
}
function sectionNamed(rootEl: any, title: string): any {
  return qa(rootEl, 'section').find((s) => sectionTitle(s) === title) || null;
}
function rowsOf(sec: any): any[] {
  return qa(sec, 'ul > li');
}
function isMono(td: any): boolean {
  if (/mono/.test(td.className || '')) return true;
  return qa(td, '*').some((e) => /mono/.test(e.className || '') || e.tagName === 'CODE');
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
// 合同 §8：className 加在 Table 的滚动容器上（复合选择器盖过 .tt-table-wrap）；DOM 上证明类名真的传给了 Table
function expectWrapClass(table: any, label: string) {
  const wrap = table.closest('.tt-table-wrap');
  expect(wrap, label + ' 的表应在 .tt-table-wrap 里').not.toBeNull();
  expect(wrap.classList.length, label + ' 的滚动容器应带额外类名：' + wrap.className).toBeGreaterThan(1);
}
function titleAttr(el: any): string | null {
  if (!el) return null;
  if (el.getAttribute('title')) return el.getAttribute('title');
  const inner = el.querySelector('[title]');
  return inner ? inner.getAttribute('title') : null;
}
function titleUp(el: any, stop: any): string | null {
  let node = el;
  while (node && node !== stop) {
    if (node.getAttribute && node.getAttribute('title')) return node.getAttribute('title');
    node = node.parentElement;
  }
  return null;
}
function kv(card: any): Record<string, any> {
  const out: Record<string, any> = {};
  qa(card, 'dt').forEach((dt) => {
    out[textOf(dt)] = dt.nextElementSibling;
  });
  return out;
}
"""

# 三页共用的数据（总览、角色、运行时各取所需）
DATA = r"""
function rowOf(over: any): any {
  return Object.assign({
    attempt: 't/attempt-001', task_id: 't', plan_version: 1, attempt_no: 1, state: 'RUNNING', started: true,
    exit_code: null, wall_seconds: null, events_ok: true, violations: 0, checks: '-', check_mode: null, verdict: null,
    failure_class: null, human_minutes: null, tokens: null, cost: null, cost_status: 'unknown',
  }, over);
}
function statusRows(): any[] {
  const runB = rowOf({ attempt: 'run-b/attempt-001', task_id: 'run-b', state: 'RUNNING',
    live: { tool_calls: 3, elapsed_seconds: 45.9, deltas_since_last_tool: 2, long_idle: false } });
  delete runB.plan_version;
  return [
    rowOf({ attempt: 'esc-task/attempt-001', task_id: 'esc-task', state: 'ESCALATE', wall_seconds: 640.2, checks: '3/4' }),
    rowOf({ attempt: 'run-a/attempt-003', task_id: 'run-a', plan_version: 2, state: 'RUNNING',
      live: { tool_calls: 37, elapsed_seconds: 1146, deltas_since_last_tool: 6420, long_idle: true } }),
    rowOf({ attempt: 'rev-a/attempt-002', task_id: 'rev-a', plan_version: 2, state: 'NEEDS_REVIEW', wall_seconds: 1719.4, checks: '8/8' }),
    rowOf({ attempt: 'pass-a/attempt-001', task_id: 'pass-a', state: 'PASS', wall_seconds: 954.0, checks: '5/5' }),
    runB,
    rowOf({ attempt: 'time-a/attempt-001', task_id: 'time-a', state: 'TIMEOUT', wall_seconds: 1800, checks: '-' }),
    rowOf({ attempt: 'blk-a/attempt-002', task_id: 'blk-a', plan_version: 3, state: 'BLOCKED', wall_seconds: null, checks: '-' }),
    rowOf({ attempt: 'done-a/attempt-001', task_id: 'done-a', state: 'INTEGRATED', wall_seconds: 100, checks: '1/1' }),
    rowOf({ attempt: 'prep-a/attempt-001', task_id: 'prep-a', state: 'PREPARED' }),
    rowOf({ attempt: 'exc-a/attempt-001', task_id: 'exc-a', state: 'ACCEPTED_WITH_EXCEPTION', wall_seconds: 3725, checks: '6/6' }),
    rowOf({ attempt: 'can a/attempt-001', task_id: 'can a', state: 'CANCELLED', wall_seconds: 59.9, checks: '-' }),
    rowOf({ attempt: 'nest/x/attempt-007', task_id: 'nest', state: 'RUNNING', live: { tool_calls: 0, elapsed_seconds: 0, long_idle: true } }),
  ];
}
function entry(number: number, at: string, over: any = {}): any {
  return Object.assign({ number, resource: 'config', at, action: 'config.set', target: 'pricing', actor: 'user',
    confirmation: 'none', state: 'published', resolved: false, changed_keys: null, note: null, external_changes: 0 }, over);
}
function histEnv(entries: any[]): any {
  return env({ entries, broken_lines: [], external_before_first: 0 }, ['config', 'history', '--json']);
}
function histMain(): any {
  return histEnv([
    entry(3, '2026-10-10T00:00:00Z', { action: 'config.unset' }),
    entry(9, '2026-10-17T13:20:45Z', { action: 'runtime.add', target: 'pi', actor: 'undeclared' }),
    entry(1, '2026-10-01T00:00:00Z'),
    entry(12, '2026-10-18T02:59:30.000Z', { action: 'config.set', target: 'pricing', actor: 'user-ui' }),
    entry(7, '2026-10-15T03:00:00Z', { action: 'role.set', target: 'execution', actor: 'user' }),
    entry(11, '2026-10-18T02:02:11Z', { action: 'preset.use', target: 'default', actor: 'agent:planning_review', external_changes: 2 }),
    entry(5, '2026-10-18T02:59:59.000Z', { action: 'zzz.unknown', target: 'misc', actor: 'weird' }),
  ]);
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
    { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: ['STEP_API_KEY', 'OTHER_KEY'] },
    { id: 'bare', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini', options: {}, credential_env: [] },
  ] }, ['config', 'profile', 'show']);
}
function presetsMain(): any {
  return env({ active_preset: 'default', presets: [
    { name: 'default', description: '日常：执行端用 step-5-preview（high）', roles: ['contract', 'execution', 'planning_review', 'scheduler_agent'], active: true },
    { name: 'economy', description: '省钱：执行端用 step-5-mini（low）', roles: ['execution'], active: false },
    { name: 'third', description: '第三个', roles: ['contract', 'execution'], active: false },
  ] }, ['config', 'preset', 'show']);
}
function runtimesMain(): any {
  return env({ runtimes: [
    { id: 'pi', adapter: 'pi', source: 'env', command: ['C:/tools/node/node.exe', 'C:/tools/pi/dist/cli.js', '--flag-with-a-rather-long-name', '--another'], notes: ['环境变量 THEMIS_PI 已设置', '另一行'] },
    { id: 'claude-code', adapter: 'claude-code', source: 'local', command: ['C:/tools/npm/claude.cmd'], notes: [] },
    { id: 'codex', adapter: 'codex', source: 'path', command: ['codex'], notes: [] },
    { id: 'opencode', adapter: 'opencode', source: 'missing', command: null, notes: [] },
    { id: 'custom', adapter: 'custom', source: 'zzz', command: ['custom-cli', '--x'], notes: ['n'] },
  ] }, ['config', 'runtime', 'show']);
}
function setOverview(rows: any[], hist: any) {
  set('getStatus', env(rows, ['status']));
  set('getHistory', hist);
}
function setRoles(roles: any, profiles: any, presets: any) {
  set('getRoles', roles);
  set('getProfiles', profiles);
  set('getPresets', presets);
}
"""

# ---- shell：T2 导航合并、T3 分组函数（D01） ----
PROBE_SHELL = PRELUDE + r"""
const probeState: any = { navigate: null, navs: [], route: null };
function makeHarness(router: any) {
  function Child() {
    const nav = router.useAppNavigate();
    probeState.navs.push(nav);
    return h('i', { id: 'gate-child' });
  }
  return function Harness() {
    const r = router.useHashRoute();
    probeState.navigate = r.navigate;
    probeState.route = r.route;
    return h('div', null, h('span', { id: 'gate-q' }, r.route.query), h(Child));
  };
}
beforeEach(() => {
  probeState.navs = [];
  probeState.navigate = null;
  probeState.route = null;
});

describe('D01 T3 分组函数', () => {
  it('ATTEMPT_GROUPS 依次是 running、review、decide、integrate、ended', async () => {
    const m: any = await import('../src/shell/attemptGroups');
    expect(Array.from(m.ATTEMPT_GROUPS)).toEqual(['running', 'review', 'decide', 'integrate', 'ended']);
  });

  it('groupOfState 按合同映射：每个状态进对的分组，其他返回 null', async () => {
    const m: any = await import('../src/shell/attemptGroups');
    const want: Record<string, string[]> = {
      running: ['PREPARING', 'RUNNING', 'COLLECTING'],
      review: ['NEEDS_REVIEW', 'TIMEOUT', 'CANCELLED', 'INFRA_FAILURE'],
      decide: ['ESCALATE', 'BLOCKED'],
      integrate: ['PASS', 'ACCEPTED_WITH_EXCEPTION'],
      ended: ['INTEGRATED', 'REVISE', 'ABANDONED', 'SUPERSEDED', 'PREPARE_FAILED'],
    };
    Object.keys(want).forEach((group) => {
      want[group].forEach((state) => {
        expect(m.groupOfState(state), state).toBe(group);
      });
    });
    ['PREPARED', 'FUTURE_STATE', '', 'running', 'Running'].forEach((state) => {
      expect(m.groupOfState(state), '「' + state + '」不在映射里').toBeNull();
    });
  });

  it('countByGroup 的行为与签名不变：running 与 needJudge（待验收加要你决定）', async () => {
    const m: any = await import('../src/shell/attemptGroups');
    const states = ['PREPARING', 'PREPARED', 'PREPARE_FAILED', 'RUNNING', 'COLLECTING', 'NEEDS_REVIEW', 'PASS', 'ACCEPTED_WITH_EXCEPTION',
      'REVISE', 'BLOCKED', 'ESCALATE', 'INFRA_FAILURE', 'TIMEOUT', 'CANCELLED', 'INTEGRATED', 'ABANDONED', 'SUPERSEDED', 'WEIRD'];
    const counts = m.countByGroup(states.map((state) => ({ state })));
    expect(Object.keys(counts).sort()).toEqual(['needJudge', 'running']);
    expect(counts.running).toBe(3);
    expect(counts.needJudge).toBe(6);
    expect(m.countByGroup([])).toEqual({ running: 0, needJudge: 0 });
  });
});

describe('D01 T2 导航合并查询', () => {
  it('path 自带查询时合并当前查询：保留 mock 与其他参数，path 的查询覆盖同名，只有一个问号', async () => {
    window.location.hash = '#/overview?mock=offline&keep=1&group=old';
    const router: any = await import('../src/shell/router');
    const Harness = makeHarness(router);
    render(h(Harness));
    await flush();
    act(() => {
      probeState.navigate('/tasks?group=review&tab=events');
    });
    const p = hashParts();
    expect(p.path).toBe('/tasks');
    expect(p.params).toEqual({ mock: 'offline', keep: '1', group: 'review', tab: 'events' });
    expect((p.raw.match(/\?/g) || []).length, '地址里只该有一个 ?：' + p.raw).toBe(1);
    expect((p.raw.match(/group=/g) || []).length, 'group 只该出现一次：' + p.raw).toBe(1);
    expect(probeState.route.pageId).toBe('tasks');
    const q = new URLSearchParams(probeState.route.query);
    expect(q.get('group')).toBe('review');
    expect(q.get('mock')).toBe('offline');
  });

  it('当前没有查询时，path 的查询原样成为地址的查询', async () => {
    window.location.hash = '#/overview';
    const router: any = await import('../src/shell/router');
    const Harness = makeHarness(router);
    render(h(Harness));
    await flush();
    act(() => {
      probeState.navigate('/tasks?group=decide');
    });
    const p = hashParts();
    expect(p.path).toBe('/tasks');
    expect(p.params).toEqual({ group: 'decide' });
  });

  it('path 没有查询时行为与现状完全相同：整段当前查询原样保留，没有查询就不加问号', async () => {
    window.location.hash = '#/overview?mock=error&x=a%20b';
    const router: any = await import('../src/shell/router');
    const Harness = makeHarness(router);
    render(h(Harness));
    await flush();
    act(() => {
      probeState.navigate('/history');
    });
    expect(window.location.hash).toBe('#/history?mock=error&x=a%20b');
    cleanup();
    window.location.hash = '';
    const Harness2 = makeHarness(router);
    render(h(Harness2));
    await flush();
    act(() => {
      probeState.navigate('/tasks');
    });
    expect(window.location.hash).toBe('#/tasks');
    expect(probeState.route.pageId).toBe('tasks');
  });

  it('useAppNavigate 返回稳定回调，委托当前挂载路由的 navigate（同步换路由）', async () => {
    window.location.hash = '#/overview?mock=offline';
    const router: any = await import('../src/shell/router');
    expect(typeof router.useAppNavigate).toBe('function');
    const Harness = makeHarness(router);
    render(h(Harness));
    await flush();
    const first = probeState.navs[probeState.navs.length - 1];
    expect(typeof first).toBe('function');
    act(() => {
      first('/roles?x=1');
    });
    const p = hashParts();
    expect(p.path).toBe('/roles');
    expect(p.params).toEqual({ mock: 'offline', x: '1' });
    expect(probeState.route.pageId, '同步更新路由状态').toBe('roles');
    expect(probeState.navs.length, '路由换了以后子组件应已重渲染过').toBeGreaterThan(1);
    expect(new Set(probeState.navs).size, '回调在重渲染之间应保持同一个引用').toBe(1);
  });

  it('useHashRoute、parseHash、mockOfQuery 的签名与行为不变', async () => {
    const router: any = await import('../src/shell/router');
    expect(typeof router.useHashRoute).toBe('function');
    expect(router.SHOWCASE_ID).toBe('showcase');
    expect(router.parseHash('')).toEqual({ tabId: 'overview', pageId: 'overview', segments: [], query: '' });
    expect(router.parseHash('#/tasks/a/b?x=1&mock=error')).toEqual({ tabId: 'tasks', pageId: 'tasks', segments: ['a', 'b'], query: 'x=1&mock=error' });
    expect(router.parseHash('#/showcase/x')).toEqual({ tabId: null, pageId: 'showcase', segments: ['x'], query: '' });
    expect(router.parseHash('#/nonsense?mock=empty')).toEqual({ tabId: 'overview', pageId: 'overview', segments: [], query: 'mock=empty' });
    expect(router.mockOfQuery('a=1&mock=error')).toBe('error');
    expect(router.mockOfQuery('')).toBe('');
    window.location.hash = '#/runtimes?mock=data';
    const Harness = makeHarness(router);
    render(h(Harness));
    await flush();
    expect(probeState.route).toEqual({ tabId: 'runtimes', pageId: 'runtimes', segments: [], query: 'mock=data' });
  });
});
"""

# ---- common：RelativeTime、ActorTag、导出、图标、copyText（D12、D02 的复制） ----
PROBE_COMMON = PRELUDE + r"""
const ICON_SHAPES: any = __ICON_SHAPES__;

async function relModule(): Promise<any> {
  const m: any = await import('../src/components/RelativeTime');
  return m.RelativeTime || m.default;
}
function isoAgo(sec: number): string {
  return new Date(Date.parse(NOW) - sec * 1000).toISOString();
}
function relText(RelativeTime: any, iso: string, extra: any = {}): string {
  cleanup();
  const r = render(h(RelativeTime, Object.assign({ iso }, extra)));
  return textOf(r.container);
}

describe('D12 RelativeTime', () => {
  it('四档与边界：59/60 秒、59/60 分钟、23/24 小时；差值向下取整到秒', async () => {
    freeze();
    const RelativeTime = await relModule();
    expect(typeof RelativeTime).toBe('function');
    const cases: Array<[number, string]> = [
      [0, '0 秒前'], [1, '1 秒前'], [59, '59 秒前'], [59.9, '59 秒前'], [60, '1 分钟前'], [119, '1 分钟前'], [120, '2 分钟前'],
      [59 * 60 + 59, '59 分钟前'], [3600, '1 小时前'], [23 * 3600 + 3599, '23 小时前'], [24 * 3600, '1 天前'], [48 * 3600, '2 天前'],
      [10 * 86400, '10 天前'],
    ];
    cases.forEach(([sec, want]) => {
      expect(relText(RelativeTime, isoAgo(sec)), sec + ' 秒前的时间').toBe(want);
    });
  });

  it('未来的时间按 0 秒算（差值取 max(0, now - t)）', async () => {
    freeze();
    const RelativeTime = await relModule();
    expect(relText(RelativeTime, isoAgo(-5))).toBe('0 秒前');
    expect(relText(RelativeTime, isoAgo(-86400 * 3))).toBe('0 秒前');
  });

  it('渲染 time 元素：dateTime 是原文，title 是本地时间加全角括号里的 UTC', async () => {
    freeze();
    const RelativeTime = await relModule();
    const iso = '2026-10-18T02:02:11Z';
    cleanup();
    const r = render(h(RelativeTime, { iso, className: 'gate-extra' }));
    const el = r.container.querySelector('time') as any;
    expect(el, '应渲染 <time>').not.toBeNull();
    expect(el.getAttribute('datetime')).toBe(iso);
    expect(el.getAttribute('title')).toBe(titleOf(iso));
    expect(el.classList.contains('gate-extra'), 'className 应落在 time 上').toBe(true);
    expect(textOf(el)).toBe('57 分钟前');
  });

  it('解析不了的原文原样显示，不带 title 和 dateTime', async () => {
    freeze();
    const RelativeTime = await relModule();
    cleanup();
    const r = render(h(RelativeTime, { iso: 'not-a-date' }));
    expect(textOf(r.container)).toBe('not-a-date');
    const el = (r.container.querySelector('time') || r.container.firstElementChild) as any;
    expect(el.getAttribute('title')).toBeNull();
    expect(el.getAttribute('datetime')).toBeNull();
  });

  it('不每秒更新：没有计时器，时间走了十秒文字也不变', async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW));
    const RelativeTime = await relModule();
    cleanup();
    const r = render(h(RelativeTime, { iso: isoAgo(30) }));
    expect(textOf(r.container)).toBe('30 秒前');
    expect(vi.getTimerCount(), '渲染后不该留着计时器').toBe(0);
    advance(10000);
    expect(textOf(r.container)).toBe('30 秒前');
  });

  it('now 属性（合同 v2：now?: number，毫秒时间戳）：按 now 算而不是按系统时间', async () => {
    freeze();
    const RelativeTime = await relModule();
    const later = Date.parse(NOW) + 2 * 3600 * 1000;
    expect(relText(RelativeTime, isoAgo(30), { now: later })).toBe('2 小时前');
    expect(relText(RelativeTime, isoAgo(30), { now: Date.parse(NOW) })).toBe('30 秒前');
    expect(relText(RelativeTime, isoAgo(30))).toBe('30 秒前');
  });

  it('title 的字面形式：YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss），全角括号，前面不加任何前缀（合同 v2 的例子）', async () => {
    freeze();
    const RelativeTime = await relModule();
    const iso = '2026-10-18T02:02:11Z';
    cleanup();
    const r = render(h(RelativeTime, { iso }));
    const title = (r.container.querySelector('time') as any).getAttribute('title') as string;
    expect(title).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}（UTC \d{2}:\d{2}:\d{2}）$/);
    expect(title.indexOf('本地'), '不带「本地」二字').toBe(-1);
    expect(title.endsWith('（UTC 02:02:11）'), 'UTC 部分').toBe(true);
    expect(title).toBe(titleOf(iso));
  });
});

describe('D12 ActorTag', () => {
  async function actorModule(): Promise<any> {
    const m: any = await import('../src/components/ActorTag');
    return m.ActorTag || m.default;
  }
  // 合同 v2：属性 actor: string（必填，要显示的 actor 原文）与可选 className
  function renderActor(Comp: any, actor: string, extra: any = {}): any {
    cleanup();
    const r = render(h(Comp, Object.assign({ actor }, extra)));
    const tag = r.container.querySelector('.tt-tag');
    expect(tag, 'ActorTag 应渲染一个 Tag').not.toBeNull();
    expect(textOf(tag), 'ActorTag 显示 actor 原文').toBe(actor);
    return tag;
  }

  it('色调：user-ui=brand、user=neutral、agent:<角色>=info、undeclared=warning、其他=neutral，都是等宽标签', async () => {
    const ActorTag = await actorModule();
    expect(typeof ActorTag).toBe('function');
    const cases: Array<[string, string]> = [
      ['user-ui', 'brand'], ['user', 'neutral'], ['agent:planning_review', 'info'], ['agent:contract', 'info'],
      ['undeclared', 'warning'], ['whoever', 'neutral'],
    ];
    cases.forEach(([actor, tone]) => {
      const tag = renderActor(ActorTag, actor);
      expect(tag.getAttribute('data-tone'), actor).toBe(tone);
      expect(tag.classList.contains('tt-tag--mono'), actor + ' 应是等宽').toBe(true);
    });
  });

  it('可选 className 落在标签上', async () => {
    const ActorTag = await actorModule();
    const tag = renderActor(ActorTag, 'user', { className: 'gate-extra' });
    expect(tag.classList.contains('gate-extra'), 'className 应落在 Tag 上').toBe(true);
    expect(tag.getAttribute('data-tone')).toBe('neutral');
  });
});

describe('D12 导出与图标', () => {
  it('components/index.ts 追加导出 RelativeTime 与 ActorTag，已有导出仍在', async () => {
    const idx: any = await import('../src/components');
    expect(typeof idx.RelativeTime).toBe('function');
    expect(typeof idx.ActorTag).toBe('function');
    ['Button', 'Tag', 'StatusTag', 'Table', 'NextStep', 'EffortPair', 'SegmentedControl', 'EmptyState', 'Tooltip', 'DiffView', 'LogFollow'].forEach((name) => {
      expect(typeof idx[name], name).toBe('function');
    });
    expect(Object.keys(idx).filter((k) => /overlay/i.test(k))).toEqual([]);
  });

  it('四个新图标：路径、圆、多边形等于合同；沿用 Svg 包装（24 画布、currentColor、aria-hidden）', async () => {
    const icons: any = await import('../src/icons');
    Object.keys(ICON_SHAPES).forEach((name) => {
      expect(typeof icons[name], name + ' 应从 icons/index.tsx 导出').toBe('function');
      cleanup();
      const r = render(h(icons[name]));
      const svg = r.container.querySelector('svg') as any;
      expect(svg, name).not.toBeNull();
      expect(svg.getAttribute('viewBox'), name).toBe('0 0 24 24');
      expect(svg.getAttribute('width'), name).toBe('24');
      expect(svg.getAttribute('stroke'), name).toBe('currentColor');
      expect(svg.getAttribute('fill'), name).toBe('none');
      expect(svg.getAttribute('aria-hidden'), name).toBe('true');
      expect(svg.classList.contains('tt-i'), name).toBe(true);
      const spec = ICON_SHAPES[name];
      expect(qa(svg, 'path').map((p) => p.getAttribute('d')), name + ' 的 path').toEqual(spec.paths);
      expect(qa(svg, 'polygon').map((p) => p.getAttribute('points')), name + ' 的 polygon').toEqual(spec.polygons);
      expect(qa(svg, 'circle').map((c) => ({ cx: c.getAttribute('cx'), cy: c.getAttribute('cy'), r: c.getAttribute('r') })), name + ' 的 circle').toEqual(spec.circles);
      cleanup();
      const r2 = render(h(icons[name], { width: 16, height: 16, className: 'gate-x' }));
      const svg2 = r2.container.querySelector('svg') as any;
      expect(svg2.getAttribute('width'), name).toBe('16');
      expect(svg2.classList.contains('gate-x'), name).toBe(true);
    });
  });

  it('已有图标仍在', async () => {
    const icons: any = await import('../src/icons');
    ['LoaderCircleIcon', 'ScaleIcon', 'CircleArrowUpIcon', 'GitMergeIcon', 'CircleCheckIcon', 'TriangleAlertIcon', 'ChevronRightIcon',
      'CheckIcon', 'CircleXIcon', 'ListChecksIcon', 'InfoIcon', 'LockIcon', 'CopyIcon', 'EyeOffIcon', 'PauseIcon', 'FilterIcon', 'FileDiffIcon'].forEach((name) => {
      expect(typeof icons[name], name).toBe('function');
    });
  });
});

describe('D02 copyText', () => {
  it('copyText(text, clipboard?)：成功 copied、没有 writeText 返回 unavailable、抛错或拒绝 failed', async () => {
    const m: any = await import('__COPY_TEXT_MODULE__');
    expect(typeof m.copyText).toBe('function');
    const writeText = vi.fn(() => Promise.resolve());
    expect(await m.copyText('abc', { writeText })).toBe('copied');
    expect(writeText).toHaveBeenCalledWith('abc');
    expect(await m.copyText('abc', {})).toBe('unavailable');
    expect(await m.copyText('abc', { writeText: vi.fn(() => Promise.reject(new Error('no'))) })).toBe('failed');
    expect(await m.copyText('abc', { writeText: vi.fn(() => { throw new Error('boom'); }) })).toBe('failed');
  });

  it('clipboard 缺省取 navigator.clipboard：没有就 unavailable，有就用它', async () => {
    const m: any = await import('__COPY_TEXT_MODULE__');
    expect((window.navigator as any).clipboard, 'jsdom 里没有剪贴板接口').toBeUndefined();
    expect(await m.copyText('x')).toBe('unavailable');
    const writeText = vi.fn(() => Promise.resolve());
    stubClipboard({ writeText });
    expect(await m.copyText('hello')).toBe('copied');
    expect(writeText).toHaveBeenCalledWith('hello');
  });
});
"""

# ---- overview：指标卡、需要你判断、运行中、待集成、配置变更、五态（D01–D05） ----
PROBE_OVERVIEW = PRELUDE + API_MOCK + DATA + r"""
async function mountOverview(rows: any[], hist: any, hash: string = '#/overview') {
  setOverview(rows, hist);
  return mountApp(hash);
}
function metricCards(): any[] {
  return qa(document, '[data-metric]');
}
function idleAttr(li: any): string | null {
  const el = li.hasAttribute('data-long-idle') ? li : li.querySelector('[data-long-idle]');
  return el ? el.getAttribute('data-long-idle') : null;
}
function hooksOf(el: any): string[] {
  const out: string[] = [];
  [el].concat(qa(el, '*')).forEach((e: any) => {
    Array.from(e.classList).forEach((c: any) => out.push('.' + c));
    Array.from(e.attributes).forEach((a: any) => {
      if (a.name.indexOf('data-') === 0) out.push('[' + a.name + '=' + a.value + ']');
    });
  });
  return Array.from(new Set(out));
}
const GROUP_IDS = ['running', 'review', 'decide', 'integrate'];

describe('D01 指标卡与链接', () => {
  it('四张卡依次 运行中/待验收/要你决定/待集成：data-metric 顺序对、整张是 a 链接、计数按分组逐行统计（不在分组里的状态不计）', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const cards = metricCards();
    expect(cards.map((c) => c.getAttribute('data-metric'))).toEqual(GROUP_IDS);
    const labels = ['运行中', '待验收', '要你决定', '待集成'];
    const counts = [3, 3, 2, 2];
    cards.forEach((c, i) => {
      expect(c.tagName, GROUP_IDS[i] + ' 整张卡应是 a 链接').toBe('A');
      expect(textOf(c), GROUP_IDS[i]).toContain(labels[i]);
      expect(textOf(c).match(/\d+/g), GROUP_IDS[i] + ' 卡上只该有计数这一个数字').toEqual([String(counts[i])]);
      expect(c.getAttribute('href'), GROUP_IDS[i]).toBe('#/tasks?group=' + GROUP_IDS[i]);
      const num = c.querySelector('.tt-num');
      expect(textOf(num), GROUP_IDS[i] + ' 的数字应带 tt-num').toBe(String(counts[i]));
      expect(c.closest('.tt-grid-4'), GROUP_IDS[i] + ' 应在 tt-grid-4 网格里').not.toBeNull();
    });
  });

  it('0 也显示 0；只有结束的 attempt 时四张卡都是 0', async () => {
    freeze();
    await mountOverview([rowOf({ attempt: 'done-a/attempt-001', task_id: 'done-a', state: 'INTEGRATED' }), rowOf({ attempt: 'p/attempt-001', task_id: 'p', state: 'PREPARED' })], histMain());
    expect(frame().getAttribute('data-page-state')).toBe('data');
    const cards = metricCards();
    expect(cards.length).toBe(4);
    cards.forEach((c) => {
      expect(textOf(c).match(/\d+/g)).toEqual(['0']);
    });
  });

  it('区块顺序：指标卡、需要你判断、运行中、待集成、最近的配置变更；区块是 section 加 aria-labelledby 指向 h2', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const r = root('overview');
    const secs = qa(r, 'section');
    expectAllSectionsTitled(r);
    expect(secs.map(sectionTitle)).toEqual(['需要你判断', '运行中', '待集成', '最近的配置变更']);
    secs.forEach((s) => {
      const id = s.getAttribute('aria-labelledby');
      expect(id, '区块应有 aria-labelledby').toBeTruthy();
      const head = document.getElementById(id as string);
      expect(head && head.tagName, 'aria-labelledby 应指向 h2').toBe('H2');
      expect(s.contains(head), 'h2 应在区块里').toBe(true);
    });
    const firstCard = metricCards()[0];
    expect(firstCard.compareDocumentPosition(secs[0]) & Node.DOCUMENT_POSITION_FOLLOWING, '指标卡在第一个区块之前').toBeTruthy();
    const ids = qa(r, '[id]').map((e) => e.id);
    expect(ids.length, '区块标题都带 id').toBeGreaterThanOrEqual(secs.length);
    expect(new Set(ids).size, 'id 不重复').toBe(ids.length);
  });

  it('点击指标卡：同步换到任务页，group 是分组 ID，当前 mock 保留；不弹轻提示', async () => {
    freeze();
    await mountOverview(statusRows(), histMain(), '#/overview?mock=offline');
    const card = metricCards()[1];
    expect(card.getAttribute('href')).toContain('group=review');
    const appPrevented = clickKeepUrl(card);
    expect(appPrevented, '无修饰键左键应 preventDefault').toBe(true);
    const p = hashParts();
    expect(p.path).toBe('/tasks');
    expect(p.params).toEqual({ mock: 'offline', group: 'review' });
    expect(textOf(document.querySelector('h1'))).toBe('任务');
  });

  it('带 metaKey、ctrlKey、shiftKey、altKey 或非左键的点击不拦截', async () => {
    const variants: any[] = [{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }];
    for (const init of variants) {
      cleanup();
      await drainNav();
      freeze();
      await mountOverview(statusRows(), histMain(), '#/overview?mock=offline');
      const appPrevented = clickKeepUrl(metricCards()[0], init);
      expect(appPrevented, JSON.stringify(init) + ' 应走默认行为（应用不 preventDefault）').toBe(false);
      expect(hashParts().path, JSON.stringify(init) + ' 应用不该自己换路由').toBe('/overview');
    }
  });

  it('各指标卡的 group 与卡对应（运行中、要你决定、待集成）', async () => {
    const wants: Array<[number, string]> = [[0, 'running'], [2, 'decide'], [3, 'integrate']];
    for (const [idx, group] of wants) {
      cleanup();
      await drainNav();
      freeze();
      await mountOverview(statusRows(), histMain(), '#/overview?mock=offline');
      clickKeepUrl(metricCards()[idx]);
      expect(hashParts().params).toEqual({ mock: 'offline', group });
    }
  });

  it('色调条：导出每张卡独有的类名与 data-*，给 CSS 检查用', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const metrics = metricCards().map((c) => ({ metric: c.getAttribute('data-metric'), hooks: hooksOf(c) }));
    fs.writeFileSync('__DATA_FILE__', JSON.stringify({ metrics }));
    expect(metrics.length).toBe(4);
  });
});

describe('D02 需要你判断', () => {
  it('只含待验收与要你决定两组、保持 getStatus 顺序；名称、用时、检查、状态标签、[查看证据] 地址', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const sec = sectionNamed(root('overview'), '需要你判断');
    expect(sec, '应有「需要你判断」区块').not.toBeNull();
    const lis = rowsOf(sec);
    expect(lis.length).toBe(5);
    const names = ['esc-task.v1 · attempt-001', 'rev-a.v2 · attempt-002', 'time-a.v1 · attempt-001', 'blk-a.v3 · attempt-002', 'can a.v1 · attempt-001'];
    names.forEach((n, i) => {
      expect(textOf(lis[i]), '第 ' + (i + 1) + ' 行').toContain(n);
    });
    expect(textOf(lis[0])).toContain('10 分 40 秒 · 检查 3/4');
    expect(textOf(lis[1])).toContain('28 分 39 秒 · 检查 8/8');
    expect(textOf(lis[2])).toContain('30 分 0 秒');
    expect(textOf(lis[2]), '没有检查就不写「检查」').not.toContain('检查');
    expect(textOf(lis[3]), '用时和检查都没有就留空').not.toMatch(/\d+ 秒|\d+ 分|检查/);
    expect(textOf(lis[4])).toContain('59 秒');
    expect(textOf(lis[4])).not.toContain('检查');
    const states = ['ESCALATE', 'NEEDS_REVIEW', 'TIMEOUT', 'BLOCKED', 'CANCELLED'];
    lis.forEach((li, i) => {
      const tag = li.querySelector('.tt-status');
      expect(tag && tag.getAttribute('title'), '状态标签').toBe(states[i]);
      expect(tag && tag.getAttribute('data-size'), '状态标签 md').toBe('md');
    });
    const hrefs = lis.map((li) => {
      const a = qa(li, 'a').find((x) => textOf(x) === '查看证据');
      return a ? a.getAttribute('href') : null;
    });
    expect(hrefs).toEqual(['#/tasks/esc-task/attempt-001', '#/tasks/rev-a/attempt-002', '#/tasks/time-a/attempt-001',
      '#/tasks/blk-a/attempt-002', '#/tasks/can%20a/attempt-001']);
    lis.forEach((li) => {
      const a = qa(li, 'a').find((x) => textOf(x) === '查看证据');
      expect(svgWidth(a), '[查看证据] 带 ChevronRight 14').toBe('14');
    });
  });

  it('计数胶囊：h2 之后的金色胶囊，aria-label 为「N 项」', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const sec = sectionNamed(root('overview'), '需要你判断');
    const pill = sec.querySelector('[aria-label="5 项"]');
    expect(pill, '应有 aria-label=「5 项」的计数胶囊').not.toBeNull();
    expect(textOf(pill)).toBe('5');
  });

  it('下一步（有待验收行）：文字「验收在规划端会话里进行：」，命令取待验收组显示顺序第一行的 attempt 原文，不带 title', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const sec = sectionNamed(root('overview'), '需要你判断');
    const next = sec.querySelector('.tt-next');
    expect(next, '应有 NextStep').not.toBeNull();
    expect(textOf(next)).toContain('验收在规划端会话里进行：');
    expect(textOf(next.querySelector('code'))).toBe('/review-pi .agent/runs/rev-a/attempt-002');
    expect(next.querySelector('strong'), '不带 title').toBeNull();
  });

  it('下一步（只有要你决定的行）：「需要你做决定，见摘要里的阻塞点。」不带命令', async () => {
    freeze();
    await mountOverview([rowOf({ attempt: 'esc-task/attempt-001', task_id: 'esc-task', state: 'ESCALATE', wall_seconds: 640.2, checks: '3/4' })], histMain());
    const sec = sectionNamed(root('overview'), '需要你判断');
    expect(sec).not.toBeNull();
    expect(rowsOf(sec).length).toBe(1);
    expect(sec.querySelector('[aria-label="1 项"]')).not.toBeNull();
    const next = sec.querySelector('.tt-next');
    expect(next).not.toBeNull();
    expect(textOf(next)).toContain('需要你做决定，见摘要里的阻塞点。');
    expect(next.querySelector('code'), '没有命令').toBeNull();
    expect(qa(next, 'button').length, '没有复制钮').toBe(0);
  });

  it('命令取待验收组里显示顺序的第一行，不是区块里的第一行', async () => {
    freeze();
    await mountOverview([
      rowOf({ attempt: 'b-task/attempt-001', task_id: 'b-task', state: 'BLOCKED' }),
      rowOf({ attempt: 'i-task/attempt-004', task_id: 'i-task', state: 'INFRA_FAILURE' }),
      rowOf({ attempt: 'n-task/attempt-002', task_id: 'n-task', state: 'NEEDS_REVIEW' }),
    ], histMain());
    const sec = sectionNamed(root('overview'), '需要你判断');
    expect(textOf(sec.querySelector('.tt-next code'))).toBe('/review-pi .agent/runs/i-task/attempt-004');
  });

  it('待验收与要你决定两组都没有行时，整块不渲染', async () => {
    freeze();
    await mountOverview([statusRows()[1], statusRows()[3]], histMain());
    expect(sectionNamed(root('overview'), '需要你判断')).toBeNull();
    expectAllSectionsTitled(root('overview'));
    expect(qa(root('overview'), 'section').map(sectionTitle)).toEqual(['运行中', '待集成', '最近的配置变更']);
  });

  it('复制三态：已复制、复制失败、这个环境没有剪贴板接口；不弹轻提示、不渲染 role=status', async () => {
    freeze();
    const command = '/review-pi .agent/runs/rev-a/attempt-002';
    const texts = ['已复制', '复制失败', '这个环境没有剪贴板接口'];
    // 成功
    await mountOverview(statusRows(), histMain());
    let sec = sectionNamed(root('overview'), '需要你判断');
    texts.forEach((t) => expect(textOf(sec), '点复制前不该有「' + t + '」').not.toContain(t));
    const writeText = vi.fn(() => Promise.resolve());
    stubClipboard({ writeText });
    fireEvent.click(sec.querySelector('button[aria-label="复制命令"]'));
    await flush();
    expect(writeText).toHaveBeenCalledWith(command);
    expect(textOf(sec)).toContain('已复制');
    expect(root('overview').querySelector('[role="status"]'), '视图里不渲染 role=status').toBeNull();
    // 拒绝
    cleanup();
    await mountOverview(statusRows(), histMain());
    sec = sectionNamed(root('overview'), '需要你判断');
    stubClipboard({ writeText: vi.fn(() => Promise.reject(new Error('denied'))) });
    fireEvent.click(sec.querySelector('button[aria-label="复制命令"]'));
    await flush();
    expect(textOf(sec)).toContain('复制失败');
    expect(textOf(sec)).not.toContain('已复制');
    // 同步抛错
    cleanup();
    await mountOverview(statusRows(), histMain());
    sec = sectionNamed(root('overview'), '需要你判断');
    stubClipboard({ writeText: vi.fn(() => { throw new Error('boom'); }) });
    fireEvent.click(sec.querySelector('button[aria-label="复制命令"]'));
    await flush();
    expect(textOf(sec)).toContain('复制失败');
    // 没有剪贴板
    cleanup();
    delete (window.navigator as any).clipboard;
    await mountOverview(statusRows(), histMain());
    sec = sectionNamed(root('overview'), '需要你判断');
    fireEvent.click(sec.querySelector('button[aria-label="复制命令"]'));
    await flush();
    expect(textOf(sec)).toContain('这个环境没有剪贴板接口');
    expect(root('overview').querySelector('[role="status"]'), '视图里不渲染 role=status').toBeNull();
  });

  it('点 [查看证据]：同步换到 attempt 详情路径，当前 mock 保留；带修饰键不拦截', async () => {
    freeze();
    await mountOverview(statusRows(), histMain(), '#/overview?mock=offline');
    const sec = sectionNamed(root('overview'), '需要你判断');
    const link = qa(rowsOf(sec)[1], 'a').find((x) => textOf(x) === '查看证据');
    expect(clickKeepUrl(link, { ctrlKey: true }), '带 ctrl 不拦截').toBe(false);
    cleanup();
    await drainNav();
    await mountOverview(statusRows(), histMain(), '#/overview?mock=offline');
    const sec2 = sectionNamed(root('overview'), '需要你判断');
    const link2 = qa(rowsOf(sec2)[1], 'a').find((x) => textOf(x) === '查看证据');
    expect(clickKeepUrl(link2), '左键应 preventDefault').toBe(true);
    const p = hashParts();
    expect(p.path).toBe('/tasks/rev-a/attempt-002');
    expect(p.params).toEqual({ mock: 'offline' });
  });
});

describe('D03 运行中与待集成', () => {
  it('运行中：名称（缺 plan_version 只写 task_id）、已用时间、工具调用次数、状态标签；attempt 段取最后一个斜杠之后', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const sec = sectionNamed(root('overview'), '运行中');
    expect(sec, '应有「运行中」区块').not.toBeNull();
    const lis = rowsOf(sec);
    expect(lis.length).toBe(3);
    expect(textOf(lis[0])).toContain('run-a.v2 · attempt-003');
    expect(textOf(lis[1])).toContain('run-b · attempt-001');
    expect(textOf(lis[1]), '缺 plan_version 不写 .v').not.toContain('run-b.v');
    expect(textOf(lis[2])).toContain('nest.v1 · attempt-007');
    expect(squash(lis[0].textContent)).toContain('已用19分6秒');
    expect(squash(lis[0].textContent)).toContain('工具调用37次');
    expect(squash(lis[1].textContent)).toContain('已用45秒');
    expect(squash(lis[1].textContent)).toContain('工具调用3次');
    expect(squash(lis[2].textContent)).toContain('已用0秒');
    expect(squash(lis[2].textContent)).toContain('工具调用0次');
    lis.forEach((li) => {
      const tag = li.querySelector('.tt-status');
      expect(tag && tag.getAttribute('title')).toBe('RUNNING');
    });
  });

  it('long_idle 真才有 warning 标签且带增量数；无增量数只写「长时间没有工具调用」；行带 data-long-idle', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const lis = rowsOf(sectionNamed(root('overview'), '运行中'));
    const tag0 = tagWith(lis[0], '长时间没有工具调用（6420 个增量）');
    expect(tag0, 'long_idle 真应有带增量数的标签').not.toBeNull();
    expect(tag0.getAttribute('data-tone')).toBe('warning');
    expect(svgWidth(tag0), 'TriangleAlert 12').toBe('12');
    expect(textOf(tag0.querySelector('.tt-num'))).toBe('6420');
    expect(qa(lis[1], '.tt-tag').some((t) => /长时间没有工具调用/.test(textOf(t))), 'long_idle 假不该有标签').toBe(false);
    const tag2 = tagWith(lis[2], '长时间没有工具调用');
    expect(tag2, '无 deltas_since_last_tool 时只写「长时间没有工具调用」').not.toBeNull();
    expect(tag2.getAttribute('data-tone')).toBe('warning');
    const flags = lis.map(idleAttr);
    expect(flags[0] !== null && flags[0] !== 'false', 'long_idle 真的行带 data-long-idle').toBe(true);
    expect(flags[1] === null || flags[1] === 'false', 'long_idle 假的行不带或为 false').toBe(true);
    expect(flags[2] !== null && flags[2] !== 'false').toBe(true);
  });

  it('[跟随事件] 地址带 tab=events；点击后路由与查询保留 mock', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const lis = rowsOf(sectionNamed(root('overview'), '运行中'));
    const hrefs = lis.map((li) => {
      const a = qa(li, 'a').find((x) => textOf(x) === '跟随事件');
      expect(svgWidth(a), '[跟随事件] 带 ChevronRight 14').toBe('14');
      return a.getAttribute('href');
    });
    expect(hrefs).toEqual(['#/tasks/run-a/attempt-003?tab=events', '#/tasks/run-b/attempt-001?tab=events', '#/tasks/nest/attempt-007?tab=events']);
    cleanup();
    await mountOverview(statusRows(), histMain(), '#/overview?mock=offline');
    const a = qa(rowsOf(sectionNamed(root('overview'), '运行中'))[0], 'a').find((x) => textOf(x) === '跟随事件');
    expect(clickKeepUrl(a), '左键应 preventDefault').toBe(true);
    const p = hashParts();
    expect(p.path).toBe('/tasks/run-a/attempt-003');
    expect(p.params).toEqual({ mock: 'offline', tab: 'events' });
  });

  it('待集成：行同需要你判断（用时 · 检查），[查看证据]；下一步「集成在规划端会话里进行：」命令取待集成组第一行', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const sec = sectionNamed(root('overview'), '待集成');
    expect(sec, '应有「待集成」区块').not.toBeNull();
    const lis = rowsOf(sec);
    expect(lis.length).toBe(2);
    expect(textOf(lis[0])).toContain('pass-a.v1 · attempt-001');
    expect(textOf(lis[0])).toContain('15 分 54 秒 · 检查 5/5');
    expect(textOf(lis[1])).toContain('exc-a.v1 · attempt-001');
    expect(textOf(lis[1])).toContain('1 小时 2 分 · 检查 6/6');
    const hrefs = lis.map((li) => qa(li, 'a').find((x) => textOf(x) === '查看证据').getAttribute('href'));
    expect(hrefs).toEqual(['#/tasks/pass-a/attempt-001', '#/tasks/exc-a/attempt-001']);
    const next = sec.querySelector('.tt-next');
    expect(next).not.toBeNull();
    expect(textOf(next)).toContain('集成在规划端会话里进行：');
    expect(textOf(next.querySelector('code'))).toBe('/review-pi .agent/runs/pass-a/attempt-001');
  });

  it('运行中、待集成没有行时整块不渲染', async () => {
    freeze();
    await mountOverview([statusRows()[0]], histMain());
    expectAllSectionsTitled(root('overview'));
    expect(qa(root('overview'), 'section').map(sectionTitle)).toEqual(['需要你判断', '最近的配置变更']);
  });

  it('时长格式化：秒向下取整；不足 1 分钟写 N 秒，不足 1 小时写 M 分 S 秒，否则 H 小时 M 分；非数或负数不显示', async () => {
    freeze();
    const mk = (state: string, wall: any) => rowOf({ attempt: 'w-task/attempt-001', task_id: 'w-task', state, wall_seconds: wall });
    const cases: Array<[any, RegExp | string]> = [
      [1719.4, '28 分 39 秒'], [1800, '30 分 0 秒'], [640.2, '10 分 40 秒'], [59.99, '59 秒'], [0, '0 秒'], [3599, '59 分 59 秒'],
      [3600, '1 小时 0 分'], [3725, '1 小时 2 分'], [90061, '25 小时 1 分'],
    ];
    for (const [wall, want] of cases) {
      cleanup();
      await mountOverview([mk('NEEDS_REVIEW', wall)], histMain());
      const li = rowsOf(sectionNamed(root('overview'), '需要你判断'))[0];
      expect(textOf(li), 'wall_seconds=' + wall).toContain(want as string);
    }
    for (const wall of [-5, null, 'abc', NaN]) {
      cleanup();
      await mountOverview([mk('NEEDS_REVIEW', wall)], histMain());
      const li = rowsOf(sectionNamed(root('overview'), '需要你判断'))[0];
      expect(textOf(li), 'wall_seconds=' + String(wall) + ' 不显示用时').not.toMatch(/\d+ 秒|\d+ 分|NaN|-5/);
    }
  });
});

describe('D04 最近的配置变更', () => {
  it('最多 5 条、按编号倒序；每行 编号、相对时间、动作、对象；右侧有「查看全部历史」链接指向 #/history', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const sec = sectionNamed(root('overview'), '最近的配置变更');
    expect(sec, '配置变更总渲染').not.toBeNull();
    const lis = rowsOf(sec);
    expect(lis.map((li) => (textOf(li).match(/#(\d+)/) || [])[1])).toEqual(['12', '11', '9', '7', '5']);
    const wantTime = ['30 秒前', '57 分钟前', '13 小时前', '3 天前', '1 秒前'];
    const ats = ['2026-10-18T02:59:30.000Z', '2026-10-18T02:02:11Z', '2026-10-17T13:20:45Z', '2026-10-15T03:00:00Z', '2026-10-18T02:59:59.000Z'];
    lis.forEach((li, i) => {
      const time = li.querySelector('time');
      expect(time, '第 ' + (i + 1) + ' 行应有 RelativeTime').not.toBeNull();
      expect(textOf(time)).toBe(wantTime[i]);
      expect(time.getAttribute('datetime')).toBe(ats[i]);
      expect(time.getAttribute('title')).toBe(titleOf(ats[i]));
    });
    const targets = ['pricing', 'default', 'pi', 'execution', 'misc'];
    lis.forEach((li, i) => {
      expect(textOf(li), '对象').toContain(targets[i]);
    });
    const link = qa(sec, 'a').find((a) => textOf(a) === '查看全部历史');
    expect(link, '应有「查看全部历史」').not.toBeNull();
    expect(link.getAttribute('href')).toBe('#/history');
  });

  it('点「查看全部历史」：换到历史页并保留 mock', async () => {
    freeze();
    await mountOverview(statusRows(), histMain(), '#/overview?mock=offline');
    const link = qa(sectionNamed(root('overview'), '最近的配置变更'), 'a').find((a) => textOf(a) === '查看全部历史');
    expect(clickKeepUrl(link), '左键应 preventDefault').toBe(true);
    const p = hashParts();
    expect(p.path).toBe('/history');
    expect(p.params).toEqual({ mock: 'offline' });
  });

  it('动作的中文说明作 title；没有对应说明的不带 title', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const lis = rowsOf(sectionNamed(root('overview'), '最近的配置变更'));
    function actionEl(li: any, action: string): any {
      return qa(li, '*').find((e) => e.children.length === 0 && textOf(e) === action) || null;
    }
    const wants: Array<[number, string, string | null]> = [[0, 'config.set', '设置配置键'], [1, 'preset.use', '切换方案'], [2, 'runtime.add', '登记 runtime'],
      [3, 'role.set', '修改角色绑定'], [4, 'zzz.unknown', null]];
    wants.forEach(([i, action, title]) => {
      const el = actionEl(lis[i], action);
      expect(el, '第 ' + (i + 1) + ' 行应显示动作 ' + action).not.toBeNull();
      const got = titleUp(el, lis[i]);
      if (title === null) expect(got, action + ' 没有说明就不带 title').toBeNull();
      else expect(got, action).toBe(title);
    });
  });

  it('其余动作的说明含动词与名词（unset、save、remove、profile.*、runtime.remove、config.rollback、external）', async () => {
    freeze();
    const actions: Array<[string, string[]]> = [
      ['config.unset', ['删除', '配置键']], ['config.rollback', ['回滚配置']], ['preset.save', ['保存', '方案']], ['preset.remove', ['删除', '方案']],
      ['profile.add', ['新建', 'profile']], ['profile.edit', ['修改', 'profile']], ['profile.remove', ['删除', 'profile']],
      ['runtime.remove', ['删除', 'runtime']], ['external', ['检测到界面与命令之外的改动']],
    ];
    const entries = actions.map(([action], i) => entry(100 + i, '2026-10-18T02:00:00Z', { action }));
    for (let start = 0; start < actions.length; start += 5) {
      cleanup();
      const slice = entries.slice(start, start + 5);
      await mountOverview(statusRows(), histEnv(slice));
      const lis = rowsOf(sectionNamed(root('overview'), '最近的配置变更'));
      slice.forEach((e) => {
        const li = lis.find((x) => textOf(x).indexOf('#' + e.number) >= 0);
        const el = qa(li, '*').find((x) => x.children.length === 0 && textOf(x) === e.action);
        expect(el, e.action + ' 应显示').toBeTruthy();
        const title = titleUp(el, li) || '';
        const want = actions.find((a) => a[0] === e.action) as [string, string[]];
        want[1].forEach((w) => expect(title, e.action + ' 的 title').toContain(w));
      });
    }
  });

  it('external_changes 大于 0 时有 warning 标签「检测到外部改动」（TriangleAlert 12）；执行者用 ActorTag 的色调', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    const lis = rowsOf(sectionNamed(root('overview'), '最近的配置变更'));
    const ext = tagWith(lis[1], '检测到外部改动');
    expect(ext, '#11 的 external_changes 是 2').not.toBeNull();
    expect(ext.getAttribute('data-tone')).toBe('warning');
    expect(svgWidth(ext)).toBe('12');
    [0, 2, 3, 4].forEach((i) => expect(tagWith(lis[i], '检测到外部改动'), '第 ' + (i + 1) + ' 行不该有').toBeNull());
    const tones: Array<[number, string, string]> = [[0, 'user-ui', 'brand'], [1, 'agent:planning_review', 'info'], [2, 'undeclared', 'warning'],
      [3, 'user', 'neutral'], [4, 'weird', 'neutral']];
    tones.forEach(([i, actor, tone]) => {
      const tag = tagWith(lis[i], actor);
      expect(tag, actor + ' 应是标签').not.toBeNull();
      expect(tag.getAttribute('data-tone'), actor).toBe(tone);
      expect(tag.classList.contains('tt-tag--mono'), actor + ' 等宽').toBe(true);
    });
  });

  it('不足 5 条时全部显示；entries 空显示「还没有配置历史」', async () => {
    freeze();
    await mountOverview(statusRows(), histEnv([entry(2, '2026-10-18T02:00:00Z'), entry(8, '2026-10-18T02:30:00Z')]));
    expect(rowsOf(sectionNamed(root('overview'), '最近的配置变更')).map((li) => (textOf(li).match(/#(\d+)/) || [])[1])).toEqual(['8', '2']);
    cleanup();
    await mountOverview(statusRows(), histEnv([]));
    const sec = sectionNamed(root('overview'), '最近的配置变更');
    expect(sec).not.toBeNull();
    expect(textOf(sec)).toContain('还没有配置历史');
    expect(rowsOf(sec).length).toBe(0);
  });

  it('history 读不出：区块里写「没能读到配置历史：命令 … 返回退出码 N。」加 messages（pre 纯文本），页面其余部分照常', async () => {
    freeze();
    await mountOverview(statusRows(), bad(['config', 'history', '--json'], 3, ['ERROR <b>坏了</b>', '第二行']));
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(metricCards().length).toBe(4);
    const sec = sectionNamed(root('overview'), '最近的配置变更');
    expect(textOf(sec)).toContain('没能读到配置历史：命令 config history --json 返回退出码 3。');
    const pre = sec.querySelector('pre');
    expect(pre, 'messages 放进 pre').not.toBeNull();
    expect(pre.textContent).toBe('ERROR <b>坏了</b>\n第二行');
    expect(pre.querySelector('b'), '纯文本，不解析标签').toBeNull();
    expect(qa(sec, 'a').some((a) => textOf(a) === '查看全部历史'), '出错时仍有「查看全部历史」').toBe(true);
  });
});

describe('D05 总览读取与五态', () => {
  it('并行读取：getStatus 挂起时 getHistory 照样已发出', async () => {
    set('getStatus', () => new Promise(() => {}));
    set('getHistory', histMain());
    await mountApp('#/overview');
    const calls = (hoisted.spies.getHistory as any).mock.calls.length;
    expect(calls, '页面不该等 getStatus 回来才读 getHistory').toBeGreaterThan(0);
    expect(frame().getAttribute('data-page-state')).toBe('loading');
  });

  it('status 出错：页面级出错块显示 status 命令与内核报错；history 的结果不影响', async () => {
    set('getStatus', bad(['status'], 2, ['ERROR 读 status 失败']));
    set('getHistory', histMain());
    await mountApp('#/overview');
    expect(frame().getAttribute('data-page-state')).toBe('error');
    expect(pageText()).toContain('命令（status）返回退出码 2');
    expect(pageText()).toContain('ERROR 读 status 失败');
    expect(root('overview')).toBeNull();
  });

  it('history 出错只在区块里显示：页面状态仍是 data', async () => {
    set('getStatus', env(statusRows(), ['status']));
    set('getHistory', bad(['config', 'history', '--json'], 2, ['ERROR h']));
    await mountApp('#/overview');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(pageText()).not.toContain('命令（status）');
    expect(textOf(sectionNamed(root('overview'), '最近的配置变更'))).toContain('没能读到配置历史');
  });

  it('status 为空数组：空态标题与说明，不渲染总览视图', async () => {
    setOverview([], histMain());
    await mountApp('#/overview');
    expect(frame().getAttribute('data-page-state')).toBe('empty');
    expect(pageText()).toContain('还没有 attempt');
    expect(pageText()).toContain('在规划端用 /dispatch-pi 派遣第一个任务');
    expect(root('overview')).toBeNull();
  });

  it('首次加载：status 还没回来时是加载态，没有总览视图', async () => {
    set('getStatus', () => new Promise(() => {}));
    set('getHistory', () => new Promise(() => {}));
    await mountApp('#/overview');
    expect(frame().getAttribute('data-page-state')).toBe('loading');
    expect(root('overview')).toBeNull();
  });

  it('页头说明是「仓库名 · kit 版本」，来自 getMeta / getMetaNow', async () => {
    const meta = { repo_name: 'zz-repo', kit_version: '9.9.9' };
    set('getMeta', env(meta, ['--version']));
    set('getMetaNow', () => meta);
    await mountOverview(statusRows(), histMain());
    expect(textOf(document.querySelector('.tt-page__desc'))).toBe('zz-repo · kit 9.9.9');
  });

  it('视图根带 data-page=overview；页面标题 h1 是「总览」', async () => {
    await mountOverview(statusRows(), histMain());
    expect(root('overview')).not.toBeNull();
    expect(textOf(document.querySelector('h1'))).toBe('总览');
  });

  it('总览上可用的链接只有指标卡、[查看证据]、[跟随事件]、[查看全部历史]', async () => {
    freeze();
    await mountOverview(statusRows(), histMain());
    qa(root('overview'), 'a').forEach((a) => {
      const ok = a.hasAttribute('data-metric') || ['查看证据', '跟随事件', '查看全部历史'].indexOf(textOf(a)) >= 0;
      expect(ok, '不在白名单里的链接：' + textOf(a) + ' ' + a.getAttribute('href')).toBe(true);
    });
  });
});
"""

# ---- roles：角色卡、当前方案、profile 表、方案表、差异面板（D06–D09） ----
PROBE_ROLES = PRELUDE + API_MOCK + DATA + r"""
async function mountRoles(roles: any = rolesMain(), profiles: any = profilesMain(), presets: any = presetsMain(), hash: string = '#/roles') {
  setRoles(roles, profiles, presets);
  return mountApp(hash);
}
function card(role: string): any {
  return document.querySelector('article[data-role="' + role + '"]');
}
function presetRow(name: string): any {
  const sec = sectionNamed(root('roles'), '方案');
  return qa(sec, 'tbody tr').find((tr) => textOf(tr.querySelector('td')) === name) || null;
}
function diffBtn(name: string): any {
  return btn(presetRow(name), '查看差异');
}
function panelOf(b: any): any {
  const id = b.getAttribute('aria-controls');
  return id ? document.getElementById(id) : null;
}
function diffEnv(a: string, b: string, roles: any[]): any {
  return env({ a, b, roles }, ['config', 'preset', 'diff', a, b]);
}
const EXEC_DIFF = { role: 'execution', a: { mode: 'headless', profile: 'step-high' }, b: { mode: 'headless', profile: 'step-low' }, same: false };
function rolesRefs(): any {
  const contract = headless('contract', { binding: { mode: 'headless', profile: 'step-high' } });
  delete contract.profile;
  return env({ active_preset: 'default', roles: [
    { role: 'planning_review', explicit: true, binding: { mode: 'interactive_host', host: 'claude-code' }, differs_from_preset: false },
    contract,
    headless('execution'),
    headless('scheduler_agent', { binding: { mode: 'headless', profile: 'step-low' }, profile: 'step-low', thinking: 'low', effort_effective: 'low' }),
  ] }, ['config', 'role', 'show']);
}
function profilesRefs(): any {
  return env({ profiles: [
    { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: ['STEP_API_KEY', 'OTHER_KEY'] },
    { id: 'step-low', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini', options: { thinking: 'low' }, credential_env: ['STEP_API_KEY'] },
    { id: 'bare', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini', options: {}, credential_env: [] },
  ] }, ['config', 'profile', 'show']);
}

describe('D06 角色卡', () => {
  it('四张卡（article 加 aria-labelledby 指向 h3），两列网格，角色名与角色码对应', async () => {
    await mountRoles();
    const r = root('roles');
    expect(r, '视图根带 data-page=roles').not.toBeNull();
    const cards = qa(r, 'article[data-role]');
    expect(cards.map((c) => c.getAttribute('data-role'))).toEqual(['planning_review', 'contract', 'execution', 'scheduler_agent']);
    const names = ['规划审核端', '合同端', '执行端', '调度代理'];
    cards.forEach((c, i) => {
      const id = c.getAttribute('aria-labelledby');
      expect(id, '角色卡应有 aria-labelledby').toBeTruthy();
      const head = document.getElementById(id as string);
      expect(head && head.tagName, 'aria-labelledby 应指向 h3').toBe('H3');
      expect(textOf(head)).toBe(names[i]);
      expect(c.closest('.tt-grid-2'), '角色卡在 tt-grid-2 网格里').not.toBeNull();
    });
    const ids = qa(r, '[id]').map((e) => e.id);
    expect(ids.length, '角色名标题都带 id').toBeGreaterThanOrEqual(cards.length);
    expect(new Set(ids).size, 'id 不重复').toBe(ids.length);
  });

  it('交互式宿主：模式标签、宿主与思考档位两项、说明；没有接通标签', async () => {
    await mountRoles();
    const c = card('planning_review');
    const mode = tagWith(c, '交互式宿主');
    expect(mode, '模式标签').not.toBeNull();
    expect(mode.getAttribute('data-tone')).toBe('neutral');
    expect(tagWith(c, '默认'), 'explicit 真不写「默认」').toBeNull();
    expect(qa(c, '.tt-tag').some((t) => /不一致/.test(textOf(t)))).toBe(false);
    expect(tagWith(c, '已接通')).toBeNull();
    expect(tagWith(c, '本轮未接通')).toBeNull();
    const pairs = kv(c);
    expect(Object.keys(pairs)).toEqual(['宿主', '思考档位']);
    expect(textOf(pairs['宿主'])).toBe('claude-code');
    const effort = pairs['思考档位'].querySelector('.tt-effort');
    expect(effort, '思考档位经 EffortPair').not.toBeNull();
    expect(effort.getAttribute('data-state')).toBe('none');
    expect(textOf(effort)).toBe('—');
    expect(textOf(c)).toContain('模型由宿主决定，Themis 不切换。');
  });

  it('手工与关闭：只有思考档位（—），各自的说明；explicit 假写「默认」，differs_from_preset 真写「与方案 default 不一致」', async () => {
    await mountRoles();
    const manual = card('contract');
    expect(tagWith(manual, '手工').getAttribute('data-tone')).toBe('neutral');
    expect(tagWith(manual, '默认').getAttribute('data-tone')).toBe('neutral');
    const differs = tagWith(manual, '与方案 default 不一致');
    expect(differs, 'differs_from_preset 真').not.toBeNull();
    expect(differs.getAttribute('data-tone')).toBe('attention');
    expect(Object.keys(kv(manual))).toEqual(['思考档位']);
    expect(kv(manual)['思考档位'].querySelector('.tt-effort').getAttribute('data-state')).toBe('none');
    expect(textOf(manual)).toContain('规划端亲自写合同');
    const off = card('scheduler_agent');
    expect(tagWith(off, '关闭').getAttribute('data-tone')).toBe('neutral');
    expect(tagWith(off, '默认')).not.toBeNull();
    expect(qa(off, '.tt-tag').some((t) => /不一致/.test(textOf(t))), 'differs 假不写').toBe(false);
    expect(Object.keys(kv(off))).toEqual(['思考档位']);
    expect(textOf(off)).toContain('本轮没有实现');
    expect(textOf(off)).not.toContain('规划端亲自写合同');
  });

  it('无头：profile、runtime（<runtime>（<adapter>））、模型（<provider>/<model>）、思考档位；已接通 success 带 CircleCheck 12；无说明', async () => {
    await mountRoles();
    const c = card('execution');
    const mode = tagWith(c, '无头');
    expect(mode.getAttribute('data-tone')).toBe('neutral');
    expect(tagWith(c, '默认'), 'explicit 真').toBeNull();
    const ok = tagWith(c, '已接通');
    expect(ok, 'connected 真').not.toBeNull();
    expect(ok.getAttribute('data-tone')).toBe('success');
    expect(svgWidth(ok)).toBe('12');
    expect(tagWith(c, '本轮未接通')).toBeNull();
    const pairs = kv(c);
    expect(Object.keys(pairs)).toEqual(['profile', 'runtime', '模型', '思考档位']);
    expect(textOf(pairs['profile'])).toBe('step-high');
    expect(textOf(pairs['runtime'])).toBe('pi（pi）');
    expect(textOf(pairs['模型'])).toBe('bb/step-5-preview');
    const effort = pairs['思考档位'].querySelector('.tt-effort');
    expect(effort.getAttribute('data-state'), 'high 对 low').toBe('differs');
    expect(textOf(effort)).toContain('与要求不同');
    expect(textOf(c)).not.toContain('模型由宿主决定');
    expect(textOf(c)).not.toContain('规划端亲自写合同');
    expect(textOf(c)).not.toContain('本轮没有实现');
  });

  it('无头的另外几种情形：未接通、生效未知、profile 取 binding.profile、一致；未知角色码与未知模式原样显示且没有说明', async () => {
    const execution = headless('execution', { connected: false, effort_effective: null });
    const contract = headless('contract', { binding: { mode: 'headless', profile: 'p2' }, explicit: false, differs_from_preset: true });
    delete contract.profile;
    const roles = env({ active_preset: 'default', roles: [
      execution, contract,
      { role: 'custom_role', explicit: true, binding: { mode: 'weird_mode' }, differs_from_preset: false },
      { role: 'scheduler_agent', explicit: true, binding: { mode: 'interactive_host', host: 'codex' }, differs_from_preset: false },
    ] }, ['config', 'role', 'show']);
    await mountRoles(roles);
    const ex = card('execution');
    const lost = tagWith(ex, '本轮未接通');
    expect(lost, 'connected 假').not.toBeNull();
    expect(lost.getAttribute('data-tone')).toBe('warning');
    expect(svgWidth(lost), 'TriangleAlert 12').toBe('12');
    expect(tagWith(ex, '已接通')).toBeNull();
    const unknown = kv(ex)['思考档位'].querySelector('.tt-effort');
    expect(unknown.getAttribute('data-state')).toBe('unknown');
    expect(textOf(unknown)).toContain('未知');
    const co = card('contract');
    expect(textOf(kv(co)['profile']), 'role.profile 缺失时取 binding.profile').toBe('p2');
    expect(kv(co)['思考档位'].querySelector('.tt-effort').getAttribute('data-state')).toBe('same');
    expect(tagWith(co, '默认')).not.toBeNull();
    expect(tagWith(co, '与方案 default 不一致')).not.toBeNull();
    const cu = card('custom_role');
    expect(cu, '未知角色码原样显示').not.toBeNull();
    expect(textOf(document.getElementById(cu.getAttribute('aria-labelledby')))).toBe('custom_role');
    expect(tagWith(cu, 'weird_mode'), '未知模式原样').not.toBeNull();
    expect(Object.keys(kv(cu))).toEqual(['思考档位']);
    ['模型由宿主决定', '规划端亲自写合同', '本轮没有实现'].forEach((t) => expect(textOf(cu)).not.toContain(t));
    const sched = card('scheduler_agent');
    expect(textOf(kv(sched)['宿主'])).toBe('codex');
  });

  it('[更改…] 是禁用的 secondary sm，悬停出「第二阶段接入」', async () => {
    await mountRoles();
    qa(root('roles'), 'article[data-role]').forEach((c) => {
      const b = btn(c, '更改…');
      expect(b, c.getAttribute('data-role') + ' 应有 [更改…]').not.toBeNull();
      expect(b.disabled).toBe(true);
      expect(b.getAttribute('data-variant')).toBe('secondary');
      expect(b.getAttribute('data-size')).toBe('sm');
    });
    vi.useFakeTimers();
    const b = btn(card('execution'), '更改…');
    fireEvent.mouseEnter(b.parentElement);
    advance(400);
    expect(textOf(document.querySelector('[role="tooltip"]'))).toBe('第二阶段接入');
  });

  it('页头 actions：[保存当前为方案…]、[新建 profile] 禁用，排在刷新钮之前', async () => {
    await mountRoles();
    const actions = document.querySelector('.tt-page__actions') as any;
    const buttons = qa(actions, 'button');
    expect(buttons.map(textOf)).toEqual(['保存当前为方案…', '新建 profile', '刷新']);
    expect(buttons[0].disabled).toBe(true);
    expect(buttons[1].disabled).toBe(true);
    expect(buttons[2].disabled).toBe(false);
  });

  it('页头说明原文；h1 是「角色与模型」', async () => {
    await mountRoles();
    expect(textOf(document.querySelector('h1'))).toBe('角色与模型');
    expect(textOf(document.querySelector('.tt-page__desc'))).toBe('四个角色各用哪个 CLI 与模型；方案可以一键切换');
  });
});

describe('D06 角色页组合读取', () => {
  it('三个读函数并行发出：getRoles 挂起时 getProfiles、getPresets 也已发出', async () => {
    set('getRoles', () => new Promise(() => {}));
    set('getProfiles', profilesMain());
    set('getPresets', presetsMain());
    await mountApp('#/roles');
    expect((hoisted.spies.getProfiles as any).mock.calls.length).toBeGreaterThan(0);
    expect((hoisted.spies.getPresets as any).mock.calls.length).toBeGreaterThan(0);
    expect(frame().getAttribute('data-page-state')).toBe('loading');
  });

  it('任一失败按 roles、profiles、presets 的顺序返回第一个失败信封', async () => {
    const R = bad(['gate', 'roles'], 7, ['E-ROLES']);
    const P = bad(['gate', 'profiles'], 8, ['E-PROFILES']);
    const S = bad(['gate', 'presets'], 9, ['E-PRESETS']);
    const cases: Array<[any, any, any, string, string[]]> = [
      [R, P, S, 'gate roles', ['gate profiles', 'gate presets']],
      [rolesMain(), P, S, 'gate profiles', ['gate roles', 'gate presets']],
      [rolesMain(), profilesMain(), S, 'gate presets', ['gate roles', 'gate profiles']],
      [R, profilesMain(), presetsMain(), 'gate roles', ['gate profiles']],
    ];
    for (const [roles, profiles, presets, want, notWant] of cases) {
      cleanup();
      await mountRoles(roles, profiles, presets);
      expect(frame().getAttribute('data-page-state'), want).toBe('error');
      expect(pageText(), want).toContain('命令（' + want + '）');
      notWant.forEach((w) => expect(pageText()).not.toContain(w));
      expect(root('roles')).toBeNull();
    }
  });

  it('角色页不传 isEmpty：roles 数组为空时仍是 data', async () => {
    await mountRoles(env({ active_preset: 'default', roles: [] }, ['config', 'role', 'show']));
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(root('roles')).not.toBeNull();
    expect(qa(root('roles'), 'article[data-role]').length).toBe(0);
  });
});

describe('D07 当前方案', () => {
  it('分段选项是方案名、初值是 active_preset；说明「当前：<active> · N 个角色」；改选只改本地并换说明', async () => {
    await mountRoles();
    const r = root('roles');
    const group = r.querySelector('[role="radiogroup"]');
    expect(group, '应有分段选择').not.toBeNull();
    const radios = qa(group, '[role="radio"]');
    expect(radios.map(textOf)).toEqual(['default', 'economy', 'third']);
    const checked = () => qa(group, '[role="radio"]').filter((x) => x.getAttribute('aria-checked') === 'true').map(textOf);
    expect(checked()).toEqual(['default']);
    expect(textOf(r)).toContain('当前：default · 4 个角色');
    fireEvent.click(radios[1]);
    expect(checked()).toEqual(['economy']);
    expect(textOf(r)).toContain('已选 economy · 切换在第二阶段接入');
    expect(textOf(r)).not.toContain('当前：default · 4 个角色');
    fireEvent.click(radios[0]);
    expect(checked()).toEqual(['default']);
    expect(textOf(r)).toContain('当前：default · 4 个角色');
    expect((hoisted.spies.diffPresets as any).mock.calls.length, '改选不读差异').toBe(0);
  });

  it('[切换…] 是禁用的 primary md，改选前后都禁用，悬停有提示', async () => {
    await mountRoles();
    const r = root('roles');
    const b = btn(r, '切换…');
    expect(b, '应有 [切换…]').not.toBeNull();
    expect(b.disabled).toBe(true);
    expect(b.getAttribute('data-variant')).toBe('primary');
    expect(b.getAttribute('data-size')).toBe('md');
    fireEvent.click(qa(r, '[role="radio"]')[2]);
    expect(btn(r, '切换…').disabled).toBe(true);
    vi.useFakeTimers();
    fireEvent.mouseEnter(btn(r, '切换…').parentElement);
    advance(400);
    expect(textOf(document.querySelector('[role="tooltip"]'))).toBe('第二阶段接入');
  });

  it('选中的方案角色数取该方案的 roles 长度', async () => {
    await mountRoles();
    const r = root('roles');
    fireEvent.click(qa(r, '[role="radio"]')[0]);
    expect(textOf(r)).toContain('当前：default · 4 个角色');
  });

  it('没有方案时只写提示，不渲染分段、[切换…] 与方案表', async () => {
    await mountRoles(rolesMain(), profilesMain(), env({ active_preset: 'default', presets: [] }, ['config', 'preset', 'show']));
    const r = root('roles');
    expect(textOf(r)).toContain('还没有方案：把当前的角色绑定存成方案，之后就能一键切换');
    expect(r.querySelector('[role="radiogroup"]')).toBeNull();
    expect(btn(r, '切换…')).toBeNull();
    const presetSec = sectionNamed(r, '方案');
    expect(presetSec ? qa(presetSec, 'table').length : 0, '方案表不渲染').toBe(0);
    expect(sectionNamed(r, 'profile'), 'profile 表照常').not.toBeNull();
  });
});

describe('D08 profile 表', () => {
  it('各列：ID、runtime、模型（provider/model）、thinking（缺省）、凭据变量标签、被引用的无头角色名、操作', async () => {
    await mountRoles(rolesRefs(), profilesRefs(), presetsMain());
    const sec = sectionNamed(root('roles'), 'profile');
    expect(sec, '应有 h2「profile」的区块').not.toBeNull();
    expect(textOf(sec)).toContain('一个 CLI、一个模型与选项的组合');
    const table = sec.querySelector('table[aria-label="profile"]');
    expect(table, 'Table aria-label=「profile」').not.toBeNull();
    expect(table.getAttribute('data-row-height')).toBe('40');
    expectWrapClass(table, 'profile');
    expect(qa(table, 'thead th').map(textOf)).toEqual(['ID', 'runtime', '模型', 'thinking', '凭据变量', '被引用', '操作']);
    const rows = tableRows(table);
    expect(rows.length).toBe(3);
    const r0 = rows[0];
    expect(textOf(r0['ID'])).toBe('step-high');
    expect(textOf(r0['runtime'])).toBe('pi');
    expect(textOf(r0['模型'])).toBe('bb/step-5-preview');
    expect(textOf(r0['thinking'])).toBe('high');
    ['ID', 'runtime', '模型', 'thinking'].forEach((k) => expect(isMono(r0[k]), k + ' 等宽').toBe(true));
    const creds = qa(r0['凭据变量'], '.tt-tag');
    expect(creds.map(textOf)).toEqual(['STEP_API_KEY', 'OTHER_KEY']);
    creds.forEach((t) => {
      expect(t.getAttribute('data-tone')).toBe('neutral');
      expect(t.classList.contains('tt-tag--mono')).toBe(true);
    });
    expect(textOf(r0['被引用']), 'role.profile 缺失时用 binding.profile，按角色顺序用、连').toBe('合同端、执行端');
    expect(textOf(rows[1]['thinking'])).toBe('low');
    expect(textOf(rows[1]['被引用'])).toBe('调度代理');
    expect(textOf(rows[2]['thinking']), 'options.thinking 缺失').toBe('缺省');
    expect(textOf(rows[2]['凭据变量']), '没有凭据变量').toBe('—');
    expect(textOf(rows[2]['被引用']), '没有人引用').toBe('—');
    rows.forEach((row) => {
      const ops = qa(row['操作'], 'button');
      expect(ops.map(textOf)).toEqual(['编辑', '删除']);
      ops.forEach((b) => {
        expect(b.disabled).toBe(true);
        expect(b.getAttribute('data-variant')).toBe('ghost');
        expect(b.getAttribute('data-size')).toBe('sm');
      });
    });
  });

  it('只有当前无头的角色算引用：交互式宿主、手工的角色即使 binding 里带 profile 也不算', async () => {
    const roles = env({ active_preset: 'default', roles: [
      { role: 'planning_review', explicit: true, binding: { mode: 'interactive_host', host: 'claude-code', profile: 'step-high' }, differs_from_preset: false },
      { role: 'contract', explicit: false, binding: { mode: 'manual', profile: 'step-high' }, differs_from_preset: false },
    ] }, ['config', 'role', 'show']);
    await mountRoles(roles, profilesRefs(), presetsMain());
    const rows = tableRows(sectionNamed(root('roles'), 'profile').querySelector('table'));
    rows.forEach((row) => expect(textOf(row['被引用'])).toBe('—'));
  });

  it('profiles 为空：写「还没有 profile」，没有数据行', async () => {
    await mountRoles(rolesMain(), env({ profiles: [] }, ['config', 'profile', 'show']), presetsMain());
    const sec = sectionNamed(root('roles'), 'profile');
    expect(sec).not.toBeNull();
    expect(textOf(sec)).toContain('还没有 profile');
    expect(qa(sec, 'tbody tr').length, '合同只要求写出这行文字，表是否渲染不定；有表也不该有数据行').toBe(0);
  });
});

describe('D09 方案表', () => {
  it('各列：名称、说明、「N 个角色」（title 中文角色名）、当前标签、操作', async () => {
    await mountRoles();
    const sec = sectionNamed(root('roles'), '方案');
    expect(sec, '应有 h2「方案」的区块').not.toBeNull();
    expect(textOf(sec)).toContain('一组角色绑定，可以一键切换');
    const table = sec.querySelector('table');
    expectWrapClass(table, '方案');
    expect(qa(table, 'thead th').map(textOf)).toEqual(['名称', '说明', '包含的角色', '当前', '操作']);
    const rows = tableRows(table);
    expect(rows.map((r) => textOf(r['名称']))).toEqual(['default', 'economy', 'third']);
    expect(isMono(rows[0]['名称'])).toBe(true);
    expect(textOf(rows[0]['说明'])).toBe('日常：执行端用 step-5-preview（high）');
    expect(textOf(rows[0]['包含的角色'])).toContain('4 个角色');
    expect(titleAttr(rows[0]['包含的角色'])).toBe('合同端、执行端、规划审核端、调度代理');
    expect(textOf(rows[1]['包含的角色'])).toContain('1 个角色');
    expect(titleAttr(rows[1]['包含的角色'])).toBe('执行端');
    expect(titleAttr(rows[2]['包含的角色'])).toBe('合同端、执行端');
    const now = tagWith(rows[0]['当前'], '当前');
    expect(now, 'active 真的行有「当前」标签').not.toBeNull();
    expect(now.getAttribute('data-tone')).toBe('brand');
    expect(svgWidth(now), 'Check 12').toBe('12');
    expect(textOf(rows[1]['当前'])).toBe('—');
    expect(qa(rows[1]['当前'], '.tt-tag').length).toBe(0);
  });

  it('当前行写「当前方案不能删」且没有 [使用]、[删除…]；其余行 [使用]、[删除…] 禁用的 ghost sm，[查看差异] 可用', async () => {
    await mountRoles();
    const rows = tableRows(sectionNamed(root('roles'), '方案').querySelector('table'));
    expect(textOf(rows[0]['操作'])).toContain('当前方案不能删');
    expect(btn(rows[0]['操作'], '使用')).toBeNull();
    expect(btn(rows[0]['操作'], '删除…')).toBeNull();
    [1, 2].forEach((i) => {
      ['使用', '删除…'].forEach((label) => {
        const b = btn(rows[i]['操作'], label);
        expect(b, '第 ' + (i + 1) + ' 行应有 [' + label + ']').not.toBeNull();
        expect(b.disabled).toBe(true);
        expect(b.getAttribute('data-variant')).toBe('ghost');
        expect(b.getAttribute('data-size')).toBe('sm');
      });
      const d = btn(rows[i]['操作'], '查看差异');
      expect(d, '[查看差异]').not.toBeNull();
      expect(d.disabled, '[查看差异] 可用').toBe(false);
      expect(d.getAttribute('aria-expanded')).toBe('false');
    });
  });
});

describe('D09 差异面板', () => {
  it('展开：调一次 diffPresets(active, 方案名)，读取中，再显示头与差异行；面板在方案表下方，按钮带 aria-expanded、aria-controls', async () => {
    const calls: any[] = [];
    set('diffPresets', (a: string, b: string) => {
      const d = deferred();
      calls.push({ a, b, d });
      return d.promise;
    });
    await mountRoles();
    const b = diffBtn('economy');
    expect(b.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(qa(root('roles'), '[role="radio"]')[2]);
    fireEvent.click(b);
    await flush();
    expect(calls.length).toBe(1);
    expect([calls[0].a, calls[0].b], '用 active_preset，不是本地选中的方案').toEqual(['default', 'economy']);
    expect(b.getAttribute('aria-expanded')).toBe('true');
    const id = b.getAttribute('aria-controls');
    expect(id, 'aria-controls').toBeTruthy();
    expect(textOf(document.getElementById(id as string))).toContain('正在读取…');
    const table = sectionNamed(root('roles'), '方案').querySelector('table');
    expect(table.compareDocumentPosition(document.getElementById(id as string)) & Node.DOCUMENT_POSITION_FOLLOWING, '面板在方案表下方').toBeTruthy();
    await act(async () => {
      calls[0].d.resolve(diffEnv('default', 'economy', [EXEC_DIFF]));
    });
    await flush();
    const panel = document.getElementById(id as string) as any;
    expect(panel, '面板还在').not.toBeNull();
    expect(textOf(panel)).not.toContain('正在读取…');
    expect(textOf(panel)).toContain('default 与 economy 的差异 ·');
    const cmd = qa(panel, '*').find((e) => e.children.length === 0 && textOf(e) === 'config preset diff default economy');
    expect(cmd, '头里接等宽的 config preset diff default economy').toBeTruthy();
    expect(isMono(cmd.parentElement) || /mono/.test(cmd.className) || cmd.tagName === 'CODE').toBe(true);
    const sq = squash(panel.textContent);
    expect(sq).toMatch(/执行端−无头·step-high→?\+无头·step-low/);
    expect(sq).not.toContain('-无头');
    expect(sq, '总共 4 个角色、差异 1 行').toContain('其余3个角色相同');
  });

  it('再点一次收起；收起后面板不在', async () => {
    set('diffPresets', (a: string, b: string) => Promise.resolve(diffEnv(a, b, [EXEC_DIFF])));
    await mountRoles();
    const b = diffBtn('economy');
    fireEvent.click(b);
    await flush();
    const id = b.getAttribute('aria-controls') as string;
    expect(document.getElementById(id)).not.toBeNull();
    fireEvent.click(b);
    await flush();
    expect(b.getAttribute('aria-expanded')).toBe('false');
    const gone = document.getElementById(id);
    expect(!gone || (gone as any).hidden, '收起后面板应不在或隐藏').toBeTruthy();
    if (!gone) expect(textOf(root('roles'))).not.toContain('config preset diff default economy');
  });

  it('同时只开一个：开第二个时第一个收起；每个都按自己的方案名读', async () => {
    const calls: any[] = [];
    set('diffPresets', (a: string, b: string) => {
      calls.push([a, b]);
      return Promise.resolve(diffEnv(a, b, [{ role: 'contract', a: { mode: 'manual' }, b: { mode: 'disabled' }, same: false }]));
    });
    await mountRoles();
    fireEvent.click(diffBtn('economy'));
    await flush();
    const econId = diffBtn('economy').getAttribute('aria-controls') as string;
    fireEvent.click(diffBtn('third'));
    await flush();
    expect(calls).toEqual([['default', 'economy'], ['default', 'third']]);
    const econPanel = document.getElementById(econId);
    expect(!econPanel || (econPanel as any).hidden, 'economy 的面板应不在或隐藏').toBeTruthy();
    expect(diffBtn('economy').getAttribute('aria-expanded')).toBe('false');
    expect(diffBtn('third').getAttribute('aria-expanded')).toBe('true');
    const open = qa(root('roles'), 'button[aria-expanded="true"]').filter((x) => textOf(x) === '查看差异');
    expect(open.length).toBe(1);
    const panel = panelOf(diffBtn('third'));
    expect(textOf(panel)).toContain('default 与 third 的差异');
    expect(squash(panel.textContent)).toMatch(/合同端−手工→?\+关闭/);
  });

  it('过期回应丢弃：先开 economy 再开 third，economy 的回应晚到也不覆盖；收起后晚到的回应也不再出现', async () => {
    const calls: any[] = [];
    set('diffPresets', (a: string, b: string) => {
      const d = deferred();
      calls.push({ a, b, d });
      return d.promise;
    });
    await mountRoles();
    fireEvent.click(diffBtn('economy'));
    await flush();
    fireEvent.click(diffBtn('third'));
    await flush();
    expect(calls.length).toBe(2);
    await act(async () => {
      calls[1].d.resolve(diffEnv('default', 'third', [{ role: 'contract', a: { mode: 'manual' }, b: { mode: 'disabled' }, same: false }]));
    });
    await flush();
    await act(async () => {
      calls[0].d.resolve(diffEnv('default', 'economy', [EXEC_DIFF]));
    });
    await flush();
    const panel = panelOf(diffBtn('third'));
    expect(textOf(panel)).toContain('default 与 third 的差异');
    expect(squash(panel.textContent)).toContain('合同端');
    expect(squash(panel.textContent), '过期的 economy 回应不该出现').not.toContain('step-high');
    expect(textOf(panel), '开着的面板头只该是 third 的').not.toContain('default 与 economy 的差异');
    // 收起后回应才到
    cleanup();
    calls.length = 0;
    await mountRoles();
    const b = diffBtn('economy');
    fireEvent.click(b);
    await flush();
    const id = b.getAttribute('aria-controls') as string;
    fireEvent.click(b);
    await flush();
    await act(async () => {
      calls[0].d.resolve(diffEnv('default', 'economy', [EXEC_DIFF]));
    });
    await flush();
    const gone = document.getElementById(id);
    expect(!gone || (gone as any).hidden, '收起后面板不在或隐藏').toBeTruthy();
    if (!gone) {
      // 晚到回应独有的串是 EXEC_DIFF 的 b 侧 step-low（默认数据里没有）；面板不在时整页文字里不该出现
      expect(textOf(root('roles'))).not.toContain('step-low');
      expect(textOf(root('roles'))).not.toContain('default 与 economy 的差异');
    }
  });

  it('出错：「没能读到差异：命令 … 返回退出码 N。」加 messages（pre 纯文本）', async () => {
    set('diffPresets', () => Promise.resolve(bad(['config', 'preset', 'diff', 'default', 'economy'], 2, ['ERROR <i>boom</i>'])));
    await mountRoles();
    const b = diffBtn('economy');
    fireEvent.click(b);
    await flush();
    const panel = panelOf(b);
    expect(textOf(panel)).toContain('没能读到差异：命令 config preset diff default economy 返回退出码 2。');
    expect(textOf(panel)).not.toContain('正在读取…');
    const pre = panel.querySelector('pre');
    expect(pre).not.toBeNull();
    expect(pre.textContent).toBe('ERROR <i>boom</i>');
    expect(pre.querySelector('i')).toBeNull();
  });

  it('绑定文字：无头 · profile、交互式宿主 · host、手工、关闭、未知原样、缺失「—」；same 真写「相同」；角色全列出时没有「其余」行', async () => {
    set('diffPresets', (a: string, b: string) => Promise.resolve(diffEnv(a, b, [
      { role: 'planning_review', a: { mode: 'interactive_host', host: 'claude-code' }, b: { mode: 'manual' }, same: false },
      { role: 'contract', a: { mode: 'disabled' }, b: { mode: 'zzz' }, same: false },
      { role: 'scheduler_agent', a: null, b: { mode: 'headless', profile: 'p' }, same: false },
      { role: 'execution', a: { mode: 'headless', profile: 'step-high' }, b: { mode: 'headless', profile: 'step-high' }, same: true },
    ])));
    await mountRoles();
    const b = diffBtn('economy');
    fireEvent.click(b);
    await flush();
    const sq = squash(panelOf(b).textContent);
    expect(sq).toMatch(/规划审核端−交互式宿主·claude-code→?\+手工/);
    expect(sq).toMatch(/合同端−关闭→?\+zzz/);
    expect(sq).toMatch(/调度代理−—→?\+无头·p/);
    expect(sq).toContain('执行端相同');
    expect(sq).not.toContain('其余');
  });
});
"""

# ---- runtimes：CLI 运行时（D10） ----
PROBE_RUNTIMES = PRELUDE + API_MOCK + DATA + r"""
async function mountRuntimes(runtimes: any = runtimesMain(), hash: string = '#/runtimes') {
  set('getRuntimes', runtimes);
  return mountApp(hash);
}
function runtimeTable(): any {
  const sec = sectionNamed(root('runtimes'), '已登记');
  return sec ? sec.querySelector('table[aria-label="已登记的 runtime"]') : null;
}
function shortCommand(full: string): string {
  const cps = Array.from(full);
  return cps.length > 40 ? cps.slice(0, 22).join('') + ' … ' + cps.slice(-15).join('') : full;
}
function rt(id: string, source: string, command: any, notes: string[] = [], adapter: string | null = null): any {
  return { id, adapter: adapter || id, source, command, notes };
}

describe('D10 CLI 运行时表', () => {
  it('已登记区块：Table 行高 40、aria-label「已登记的 runtime」，七列，行按数据顺序', async () => {
    await mountRuntimes();
    const r = root('runtimes');
    expect(r, '视图根带 data-page=runtimes').not.toBeNull();
    expect(textOf(document.querySelector('h1'))).toBe('CLI 运行时');
    const table = runtimeTable();
    expect(table, '应有 h2「已登记」区块里的表').not.toBeNull();
    expect(table.getAttribute('data-row-height')).toBe('40');
    expectWrapClass(table, '已登记的 runtime');
    expect(qa(table, 'thead th').map(textOf)).toEqual(['ID', '适配器', '能担任', '命令来源', '命令', '版本', '操作']);
    const rows = tableRows(table);
    expect(rows.map((x) => textOf(x['ID']))).toEqual(['pi', 'claude-code', 'codex', 'opencode', 'custom']);
    expect(rows.map((x) => textOf(x['适配器']))).toEqual(['pi', 'claude-code', 'codex', 'opencode', 'custom']);
    rows.forEach((x) => {
      expect(isMono(x['ID']), 'ID 等宽').toBe(true);
      expect(textOf(x['版本']), '版本一律「—」').toBe('—');
    });
  });

  it('能担任：pi=执行端、合同端；claude-code、codex=交互式宿主；opencode=未接通；其他「—」', async () => {
    await mountRuntimes();
    const rows = tableRows(runtimeTable());
    expect(rows.map((x) => textOf(x['能担任']))).toEqual(['执行端、合同端', '交互式宿主', '交互式宿主', '未接通', '—']);
  });

  it('命令来源：env=环境变量、local=本机文件、path=PATH（neutral），missing=找不到（danger，CircleX 12），其他原样 neutral；带 data-source', async () => {
    await mountRuntimes();
    const rows = tableRows(runtimeTable());
    const want: Array<[string, string, string]> = [['env', '环境变量', 'neutral'], ['local', '本机文件', 'neutral'], ['path', 'PATH', 'neutral'],
      ['missing', '找不到', 'danger'], ['zzz', 'zzz', 'neutral']];
    rows.forEach((x, i) => {
      const el = x['命令来源'].querySelector('[data-source]');
      expect(el, '第 ' + (i + 1) + ' 行来源标签应带 data-source').not.toBeNull();
      expect(el.getAttribute('data-source')).toBe(want[i][0]);
      expect(textOf(el)).toBe(want[i][1]);
      expect(el.getAttribute('data-tone')).toBe(want[i][2]);
    });
    expect(svgWidth(rows[3]['命令来源'].querySelector('[data-source]')), 'missing 带 CircleX 12').toBe('12');
  });

  it('notes 非空：用换行连起来放进来源标签的 title；空则没有 title', async () => {
    await mountRuntimes();
    const rows = tableRows(runtimeTable());
    const titles = rows.map((x) => x['命令来源'].querySelector('[data-source]').getAttribute('title'));
    expect(titles[0]).toBe('环境变量 THEMIS_PI 已设置\n另一行');
    expect(titles[4]).toBe('n');
    [1, 2, 3].forEach((i) => expect(titles[i] || null, '第 ' + (i + 1) + ' 行没有 notes').toBeNull());
  });

  it('命令：null 显示「—」；空格连接；超过 40 个字符显示前 22、「 … 」、后 15，title 是全文', async () => {
    await mountRuntimes();
    const rows = tableRows(runtimeTable());
    const full = 'C:/tools/node/node.exe C:/tools/pi/dist/cli.js --flag-with-a-rather-long-name --another';
    expect(textOf(rows[0]['命令'])).toBe(shortCommand(full));
    expect(textOf(rows[0]['命令'])).toContain(' … ');
    expect(titleAttr(rows[0]['命令'])).toBe(full);
    expect(textOf(rows[1]['命令'])).toBe('C:/tools/npm/claude.cmd');
    expect(textOf(rows[2]['命令'])).toBe('codex');
    expect(textOf(rows[3]['命令']), 'command 为 null').toBe('—');
    expect(textOf(rows[4]['命令'])).toBe('custom-cli --x');
    expect(isMono(rows[0]['命令']), '命令等宽').toBe(true);
  });

  it('截断按码点算：恰好 40 个码点不截断，41 个截断（含一个码点占两个 UTF-16 单元的字符）', async () => {
    const emoji = '\u{1F600}';
    const c40 = emoji.repeat(20) + 'abcdefghijklmnopqrst';
    const c41 = emoji.repeat(21) + 'abcdefghijklmnopqrst';
    expect(Array.from(c40).length).toBe(40);
    expect(Array.from(c41).length).toBe(41);
    await mountRuntimes(env({ runtimes: [rt('cp40', 'path', [c40]), rt('cp41', 'path', [c41])] }, ['config', 'runtime', 'show']));
    const rows = tableRows(runtimeTable());
    expect(textOf(rows[0]['命令'])).toBe(c40);
    expect(textOf(rows[1]['命令'])).toBe(emoji.repeat(21) + 'a' + ' … ' + 'fghijklmnopqrst');
    expect(titleAttr(rows[1]['命令'])).toBe(c41);
  });

  it('操作：[探测]（来源不是 missing）、[模型]（adapter 是 pi 且来源不是 missing）、[删除…]（总有）；都禁用', async () => {
    await mountRuntimes();
    const rows = tableRows(runtimeTable());
    const want = [['探测', '模型', '删除…'], ['探测', '删除…'], ['探测', '删除…'], ['删除…'], ['探测', '删除…']];
    rows.forEach((x, i) => {
      const ops = qa(x['操作'], 'button');
      expect(ops.map(textOf), '第 ' + (i + 1) + ' 行的操作').toEqual(want[i]);
      ops.forEach((b) => expect(b.disabled, textOf(b) + ' 应禁用').toBe(true));
    });
    await (async () => {
      cleanup();
      await mountRuntimes(env({ runtimes: [rt('pi', 'missing', null), rt('claude-code', 'missing', null)] }, ['config', 'runtime', 'show']));
      const missing = tableRows(runtimeTable());
      missing.forEach((x) => expect(qa(x['操作'], 'button').map(textOf), 'missing 只有 [删除…]').toEqual(['删除…']));
      cleanup();
      await mountRuntimes(env({ runtimes: [rt('pi', 'path', ['pi'])] }, ['config', 'runtime', 'show']));
      tableRows(runtimeTable()).forEach((x) => expect(qa(x['操作'], 'button').map(textOf)).toEqual(['探测', '模型', '删除…']));
      cleanup();
      await mountRuntimes(env({ runtimes: [rt('pi', 'local', ['pi'])] }, ['config', 'runtime', 'show']));
      tableRows(runtimeTable()).forEach((x) => expect(qa(x['操作'], 'button').map(textOf)).toEqual(['探测', '模型', '删除…']));
    })();
  });

  it('页头 actions：[扫描 PATH]（SearchIcon）、[手动登记…]（PlusIcon，primary）都禁用，排在刷新钮之前', async () => {
    await mountRuntimes();
    const buttons = qa(document.querySelector('.tt-page__actions'), 'button');
    expect(buttons.map(textOf)).toEqual(['扫描 PATH', '手动登记…', '刷新']);
    expect(buttons[0].disabled).toBe(true);
    expect(buttons[1].disabled).toBe(true);
    expect(buttons[0].querySelector('svg'), '[扫描 PATH] 带 SearchIcon').not.toBeNull();
    expect(buttons[1].querySelector('svg'), '[手动登记…] 带 PlusIcon').not.toBeNull();
    expect(buttons[1].getAttribute('data-variant')).toBe('primary');
  });

  it('页头说明原文', async () => {
    await mountRuntimes();
    expect(textOf(document.querySelector('.tt-page__desc'))).toBe('每个 runtime 是一个 CLI 的一份安装；命令来源依次是环境变量（只对 pi）、本机文件、PATH');
  });
});

describe('D10 就绪检查区与空态', () => {
  it('就绪检查：h2 加禁用的 [运行就绪检查]（PlayIcon，secondary），虚线空框原文；没有按版本核验的下拉与 [核验]', async () => {
    await mountRuntimes();
    const r = root('runtimes');
    expectAllSectionsTitled(r);
    expect(qa(r, 'section').map(sectionTitle)).toEqual(['已登记', '就绪检查']);
    const sec = sectionNamed(r, '就绪检查');
    const b = btn(sec, '运行就绪检查');
    expect(b, '应有 [运行就绪检查]').not.toBeNull();
    expect(b.disabled).toBe(true);
    expect(b.getAttribute('data-variant')).toBe('secondary');
    expect(b.querySelector('svg'), 'PlayIcon').not.toBeNull();
    expect(textOf(sec)).toContain('还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据；运行入口在第二阶段接入。');
    expect(sec.querySelector('select, [role="combobox"], [role="listbox"]'), '不放按版本核验的下拉').toBeNull();
    expect(btn(r, '核验')).toBeNull();
  });

  it('runtimes 为空数组：空态「还没有登记的 runtime」加说明，不渲染视图', async () => {
    await mountRuntimes(env({ runtimes: [] }, ['config', 'runtime', 'show']));
    expect(frame().getAttribute('data-page-state')).toBe('empty');
    expect(pageText()).toContain('还没有登记的 runtime');
    expect(pageText()).toContain('在命令行里用 config runtime scan --add 登记；界面上的登记入口在第二阶段接入');
    expect(root('runtimes')).toBeNull();
  });

  it('读取失败：页面级出错块写命令与退出码', async () => {
    await mountRuntimes(bad(['gate', 'runtimes'], 6, ['E-RT']));
    expect(frame().getAttribute('data-page-state')).toBe('error');
    expect(pageText()).toContain('命令（gate runtimes）返回退出码 6');
    expect(root('runtimes')).toBeNull();
  });
});
"""

# ---- pages：写入口与可用按钮白名单（D11，长期）；TRANS：经 ?mock= 渲染 App 三页的五态与夹具值（过渡） ----
PROBE_PAGES = PRELUDE + API_MOCK + DATA + r"""
const WHITELIST_LINKS = ['查看证据', '跟随事件', '查看全部历史'];
function outsideWhitelist(): string[] {
  return qa(frame(), 'button').filter((b) => !b.disabled).filter((b) => !(
    textOf(b) === '刷新' || b.getAttribute('role') === 'radio' || textOf(b) === '查看差异' || b.getAttribute('aria-label') === '复制命令'
  )).map((b) => textOf(b) || b.getAttribute('aria-label') || '?');
}
function disabledButtons(): any[] {
  return qa(frame(), 'button').filter((b) => b.disabled);
}
function tooltipTexts(): string[] {
  vi.useFakeTimers();
  const out: string[] = [];
  disabledButtons().forEach((b) => {
    fireEvent.mouseEnter(b.parentElement);
    advance(400);
    const tip = document.querySelector('[role="tooltip"]');
    out.push(textOf(b) + '=' + (tip ? textOf(tip) : '（没有提示）'));
    fireEvent.mouseLeave(b.parentElement);
    advance(10);
  });
  return out;
}

describe('D11 写入口全部禁用', () => {
  it('角色页：写入口全部禁用且悬停出「第二阶段接入」；可用按钮只在白名单里（刷新、分段选择段、[查看差异]）', async () => {
    set('getRoles', rolesMain());
    set('getProfiles', profilesMain());
    set('getPresets', presetsMain());
    await mountApp('#/roles');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(outsideWhitelist()).toEqual([]);
    expect(disabledButtons().length).toBeGreaterThan(0);
    const tips = tooltipTexts();
    tips.forEach((t) => expect(t.split('=')[1], t).toBe('第二阶段接入'));
  });

  it('运行时页：写入口全部禁用且悬停出「第二阶段接入」；可用按钮只有刷新', async () => {
    set('getRuntimes', runtimesMain());
    await mountApp('#/runtimes');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(outsideWhitelist()).toEqual([]);
    expect(disabledButtons().length).toBeGreaterThan(0);
    tooltipTexts().forEach((t) => expect(t.split('=')[1], t).toBe('第二阶段接入'));
  });

  it('总览页：没有写入口；可用按钮只有刷新与下一步的复制钮，可用链接只有指标卡、[查看证据]、[跟随事件]、[查看全部历史]', async () => {
    freeze();
    setOverview(statusRows(), histMain());
    await mountApp('#/overview');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(outsideWhitelist()).toEqual([]);
    expect(disabledButtons().map(textOf), '总览页没有写入口').toEqual([]);
    qa(frame(), 'a[href]').forEach((a) => {
      const ok = a.hasAttribute('data-metric') || WHITELIST_LINKS.indexOf(textOf(a)) >= 0;
      expect(ok, '不在白名单里的链接：' + textOf(a)).toBe(true);
    });
  });

  it('三页的视图里不渲染 role=status，也没有内联 style', async () => {
    freeze();
    setOverview(statusRows(), histMain());
    set('getRoles', rolesMain());
    set('getProfiles', profilesMain());
    set('getPresets', presetsMain());
    set('getRuntimes', runtimesMain());
    const pages = ['overview', 'roles', 'runtimes'];
    for (const page of pages) {
      cleanup();
      await mountApp('#/' + page);
      const r = root(page);
      expect(r, page + ' 视图根').not.toBeNull();
      expect(r.querySelector('[role="status"]'), page + ' 不渲染 role=status').toBeNull();
      expect(qa(r, '[style]').length, page + ' 视图里不写内联 style').toBe(0);
      expect(r.hasAttribute('style')).toBe(false);
    }
  });
});

describe('TRANS1 经 ?mock= 渲染三页的五态', () => {
  it('data、offline、loading、error、empty 五态：页面状态、视图根、离线标记；角色页空数据仍是 data', async () => {
    const wantState: Record<string, Record<string, string>> = {
      overview: { data: 'data', offline: 'data', loading: 'loading', error: 'error', empty: 'empty' },
      roles: { data: 'data', offline: 'data', loading: 'loading', error: 'error', empty: 'data' },
      runtimes: { data: 'data', offline: 'data', loading: 'loading', error: 'error', empty: 'empty' },
    };
    const titles: Record<string, string> = { overview: '总览', roles: '角色与模型', runtimes: 'CLI 运行时' };
    for (const page of Object.keys(wantState)) {
      for (const mock of Object.keys(wantState[page])) {
        cleanup();
        await mountApp('#/' + page + '?mock=' + mock);
        const state = wantState[page][mock];
        expect(frame().getAttribute('data-page-state'), page + ' ?mock=' + mock).toBe(state);
        expect(textOf(document.querySelector('h1'))).toBe(titles[page]);
        expect(root(page) !== null, page + ' ?mock=' + mock + ' 视图根').toBe(state === 'data');
        if (mock === 'offline') expect(frame().hasAttribute('data-stale'), page + ' 断线时标「可能已过期」').toBe(true);
      }
    }
    cleanup();
    await mountApp('#/overview?mock=empty');
    expect(pageText()).toContain('还没有 attempt');
    cleanup();
    await mountApp('#/runtimes?mock=empty');
    expect(pageText()).toContain('还没有登记的 runtime');
  });
});

describe('TRANS2 夹具里的具体值', () => {
  it('总览：指标 1/2/1/1、需要你判断三行与命令、运行中一行、待集成一行、配置变更三条、说明 demo-repo · kit 2.12.0', async () => {
    await mountApp('#/overview');
    const r = root('overview');
    expect(qa(r, '[data-metric]').map((c) => (textOf(c).match(/\d+/g) || []).join(','))).toEqual(['1', '2', '1', '1']);
    expect(textOf(document.querySelector('.tt-page__desc'))).toBe('demo-repo · kit 2.12.0');
    const judge = sectionNamed(r, '需要你判断');
    expect(rowsOf(judge).length).toBe(3);
    const names = ['logs-cat.v2 · attempt-002', 'plugin-verify-json.v1 · attempt-001', 'secret-check-json.v1 · attempt-001'];
    names.forEach((n, i) => expect(textOf(rowsOf(judge)[i])).toContain(n));
    expect(textOf(rowsOf(judge)[0])).toContain('28 分 39 秒 · 检查 8/8');
    expect(textOf(rowsOf(judge)[2])).toContain('10 分 40 秒 · 检查 3/4');
    expect(judge.querySelector('[aria-label="3 项"]')).not.toBeNull();
    expect(textOf(judge.querySelector('.tt-next code'))).toBe('/review-pi .agent/runs/logs-cat/attempt-002');
    const running = sectionNamed(r, '运行中');
    expect(rowsOf(running).length).toBe(1);
    expect(textOf(rowsOf(running)[0])).toContain('ui-readonly-api.v1 · attempt-001');
    expect(tagWith(rowsOf(running)[0], '长时间没有工具调用（6420 个增量）')).not.toBeNull();
    expect(squash(rowsOf(running)[0].textContent)).toContain('已用19分6秒');
    expect(squash(rowsOf(running)[0].textContent)).toContain('工具调用37次');
    const integrate = sectionNamed(r, '待集成');
    expect(rowsOf(integrate).length).toBe(1);
    expect(textOf(rowsOf(integrate)[0])).toContain('status-live-json.v1 · attempt-001');
    expect(textOf(rowsOf(integrate)[0])).toContain('15 分 54 秒 · 检查 5/5');
    expect(textOf(integrate.querySelector('.tt-next code'))).toBe('/review-pi .agent/runs/status-live-json/attempt-001');
    const changes = sectionNamed(r, '最近的配置变更');
    expect(rowsOf(changes).map((li) => (textOf(li).match(/#(\d+)/) || [])[1])).toEqual(['42', '41', '40']);
    expect(tagWith(rowsOf(changes)[2], '检测到外部改动')).not.toBeNull();
    expect(tagWith(rowsOf(changes)[0], '检测到外部改动')).toBeNull();
  });

  it('角色页：四张卡、执行端的值、profile 两行、方案两行，查看差异读夹具', async () => {
    await mountApp('#/roles');
    const r = root('roles');
    expect(qa(r, 'article[data-role]').length).toBe(4);
    const ex = r.querySelector('article[data-role="execution"]');
    expect(textOf(kv(ex)['profile'])).toBe('step-high');
    expect(textOf(kv(ex)['runtime'])).toBe('pi（pi）');
    expect(textOf(kv(ex)['模型'])).toBe('bb/step-5-preview');
    expect(kv(ex)['思考档位'].querySelector('.tt-effort').getAttribute('data-state')).toBe('unknown');
    expect(tagWith(ex, '已接通')).not.toBeNull();
    expect(textOf(r)).toContain('当前：default · 4 个角色');
    const profiles = tableRows(sectionNamed(r, 'profile').querySelector('table'));
    expect(profiles.map((x) => textOf(x['ID']))).toEqual(['step-high', 'step-low']);
    expect(profiles.map((x) => textOf(x['被引用']))).toEqual(['执行端', '—']);
    const presets = tableRows(sectionNamed(r, '方案').querySelector('table'));
    expect(presets.map((x) => textOf(x['名称']))).toEqual(['default', 'economy']);
    const b = btn(presets[1]['操作'], '查看差异');
    fireEvent.click(b);
    await flush();
    const panel = document.getElementById(b.getAttribute('aria-controls') as string) as any;
    const sq = squash(panel.textContent);
    expect(sq).toMatch(/执行端\u2212无头·step-high→?\+无头·step-low/);
    expect(sq).toContain('其余3个角色相同');
  });

  it('运行时页：三行（本机文件、PATH、找不到），能担任、命令截断、版本', async () => {
    await mountApp('#/runtimes');
    const rows = tableRows(runtimeTable());
    expect(rows.map((x) => textOf(x['ID']))).toEqual(['pi', 'claude-code', 'opencode']);
    expect(rows.map((x) => textOf(x['命令来源']))).toEqual(['本机文件', 'PATH', '找不到']);
    expect(rows.map((x) => textOf(x['能担任']))).toEqual(['执行端、合同端', '交互式宿主', '未接通']);
    expect(textOf(rows[0]['命令'])).toBe(shortCommand('C:/tools/node/node.exe C:/tools/pi/dist/cli.js'));
    expect(textOf(rows[1]['命令'])).toBe('C:/tools/npm/claude.cmd');
    expect(textOf(rows[2]['命令'])).toBe('—');
    rows.forEach((x) => expect(textOf(x['版本'])).toBe('—'));
  });
});

describe('TRANS3 夹具下写入口的个数', () => {
  it('角色页 13 个、运行时页 9 个、总览 0 个禁用按钮（页头加视图）', async () => {
    await mountApp('#/roles');
    expect(disabledButtons().length, '角色页').toBe(13);
    cleanup();
    await mountApp('#/runtimes');
    expect(disabledButtons().length, '运行时页').toBe(9);
    cleanup();
    await mountApp('#/overview');
    expect(disabledButtons().length, '总览页').toBe(0);
  });
});

function runtimeTable(): any {
  const sec = sectionNamed(root('runtimes'), '已登记');
  return sec ? sec.querySelector('table[aria-label="已登记的 runtime"]') : null;
}
function shortCommand(full: string): string {
  const cps = Array.from(full);
  return cps.length > 40 ? cps.slice(0, 22).join('') + ' … ' + cps.slice(-15).join('') : full;
}
"""

PROBE_SPECS = {
    "shell": (PROBE_SHELL, [f"{SRC_REL}/shell/router.ts", f"{SRC_REL}/shell/attemptGroups.ts"]),
    "common": (PROBE_COMMON, [f"{COMP_REL}/RelativeTime.tsx", f"{COMP_REL}/ActorTag.tsx", COPY_TEXT_REL]),
    "overview": (PROBE_OVERVIEW, [PAGE_FILES["overview"], f"{RO_REL}/overview-OverviewView.tsx"]),
    "roles": (PROBE_ROLES, [PAGE_FILES["roles"], f"{RO_REL}/roles-RolesView.tsx"]),
    "runtimes": (PROBE_RUNTIMES, [PAGE_FILES["runtimes"], f"{RO_REL}/runtimes-RuntimesView.tsx"]),
    "pages": (PROBE_PAGES, [f"{RO_REL}/overview-OverviewView.tsx", f"{RO_REL}/roles-RolesView.tsx", f"{RO_REL}/runtimes-RuntimesView.tsx"]),
}
PROBE_ORDER = ("shell", "common", "overview", "roles", "runtimes", "pages")
DATA_PROBES = ("overview",)

def probe_groups(source):
    """{describe 名: 用例数}：描述块写在行首 ``describe('名字'``，用例写成行首缩进的 ``it(``。"""
    groups, current = {}, None
    for line in source.splitlines():
        m = re.match(r"describe\('([^']+)'", line)
        if m:
            current = m.group(1)
            groups[current] = 0
        elif current and re.match(r"\s+it\(", line):
            groups[current] += 1
    return groups


def build_probe_source(key, uid="selfcheck"):
    source = PROBE_SPECS[key][0]
    source = source.replace("__ICON_SHAPES__", json.dumps(ICON_SHAPES, ensure_ascii=False))
    source = source.replace("__DATA_FILE__", f"gate-probe/{data_file_name(uid, key)}")
    source = source.replace("__COPY_TEXT_MODULE__", COPY_TEXT_MODULE)
    return source


def data_file_name(uid, key):
    return f"data-t009-{uid}-{key}.json"


def parse_vitest_json(text):
    """从 ``npm test -- … --reporter=json`` 的输出里取出 JSON（前面有 npm 的横幅行）。"""
    m = re.search(r"\{\s*\"numTotalTestSuites\"", text)
    if not m:
        return None
    try:
        data, _end = json.JSONDecoder().raw_decode(text[m.start():])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def summarize_vitest(data):
    """{分组名: {"passed": n, "bad": [(标题, 状态, 失败信息)]}}，分组名是最外层 describe 的名字；另返回收集阶段的错误信息。"""
    groups, collect_errors = {}, []
    for result in data.get("testResults", []):
        items = result.get("assertionResults") or []
        if not items and result.get("status") == "failed":
            collect_errors.append((result.get("message") or "")[:1500])
        for item in items:
            ancestors = item.get("ancestorTitles") or []
            group = groups.setdefault(ancestors[0] if ancestors else "", {"passed": 0, "bad": []})
            if item.get("status") == "passed":
                group["passed"] += 1
            else:
                group["bad"].append((item.get("title"), item.get("status"), "\n".join(item.get("failureMessages") or [])[:700]))
    return groups, collect_errors


# ---------------------------------------------------------------------------
# 会话级夹具：四步 npm + 探针
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
        self.probe_groups = {}
        self.probe_errors = {}
        self.probe_unparsed = {}
        self.probe_data = {}
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
    """跑一条命令，合并 stdout/stderr；超时时连子进程一起杀掉。不用 shell。"""
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


# 流水线前后不该变的文件（相对 desktop/web）：本片不许改的依赖、令牌与 T006 框架文件
WATCHED = ("package.json", "package-lock.json", "index.html", "vite.config.ts", "tsconfig.json",
           "src/styles/tokens.css", "src/styles/fonts.css", "src/styles/base.css", "src/main.tsx", "src/App.tsx", "src/App.css",
           "src/api.ts", "src/shell/PageFrame.tsx", "src/shell/DisabledAction.tsx")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    tsx_files = [rel for rel in NEW_SOURCE_FILES if rel.endswith((".tsx", ".ts"))]
    if not any((REPO_ROOT / rel).is_file() for rel in tsx_files):
        pipe.reason = ("候选里还没有任何本片的新源码文件（基线），没有东西可测，未调用 npm；"
                       "候选写出新文件后，流水线才会运行 npm ci、构建、Vitest 和探针")
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
        ci = run_step("npm ci", [npm, "ci"])
        if ci is not None and ci.code == 0:
            run_step("npm run build", [npm, "run", "build"])
            run_step("npm test", [npm, "test"])
            run_step("npm run check:contract", [npm, "run", "check:contract"])
            uid = uuid.uuid4().hex[:12]
            for key in PROBE_ORDER:
                missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                name = f"probe-t009-{uid}-{key}.test.ts"
                result_name = f"result-t009-{uid}-{key}.json"
                data_name = data_file_name(uid, key)
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                result_path = probe_dir / result_name
                data_path = probe_dir / data_name
                written += [path, result_path, data_path]
                path.write_text(build_probe_source(key, uid), encoding="utf-8", newline="\n")
                pipe.probe_files[key] = name
                step = run_step("probe", [npm, "test", "--", f"gate-probe/{name}", "--reporter=json",
                                          f"--outputFile=gate-probe/{result_name}"], label=f"probe:{key}")
                if step is None:
                    continue
                data = None
                if result_path.is_file():
                    try:
                        data = json.loads(result_path.read_text(encoding="utf-8"))
                    except ValueError:
                        data = None
                if data is None:
                    data = parse_vitest_json(step.out)
                if data_path.is_file():
                    try:
                        pipe.probe_data[key] = json.loads(data_path.read_text(encoding="utf-8"))
                    except ValueError:
                        pass
                if data is None:
                    pipe.probe_unparsed[key] = step.tail
                    continue
                pipe.probe_groups[key], pipe.probe_errors[key] = summarize_vitest(data)
        elif ci is not None:
            pipe.stopped_reason = "npm ci 失败，后续步骤未运行"
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


def assert_probe_group(pipe, key, group):
    """探针 key 里 describe 名为 group 的一组在候选上全部通过：个数等于源码里的用例数，没有失败、跳过、待办。"""
    assert pipe.ran, pipe.reason
    assert key not in pipe.probe_skipped, pipe.probe_skipped[key]
    step = pipe.steps.get(f"probe:{key}")
    assert step is not None, f"探针 {key} 未运行：{pipe.stopped_reason or '前置步骤失败'}"
    assert not step.timed_out, f"探针 {key} 超时被杀，用时 {step.seconds:.0f}s\n{step.tail}"
    assert key not in pipe.probe_unparsed, f"探针 {key} 的输出里找不到 Vitest 的 JSON：\n{pipe.probe_unparsed.get(key)}"
    assert not pipe.probe_errors.get(key), f"探针 {key} 收集失败（导入或语法错误）：\n" + "\n".join(pipe.probe_errors[key])
    want = probe_groups(PROBE_SPECS[key][0])[group]
    got = pipe.probe_groups.get(key, {}).get(group)
    assert got is not None, f"探针 {key} 的输出里没有分组「{group}」"
    assert not got["bad"], f"探针 {key}「{group}」有 {len(got['bad'])} 条没通过：\n" + "\n".join(
        f"- [{status}] {title}\n{msg}" for title, status, msg in got["bad"][:6])
    assert got["passed"] == want, f"探针 {key}「{group}」应有 {want} 条通过，实际 {got['passed']}"


# ---------------------------------------------------------------------------
# 静态断言
# ---------------------------------------------------------------------------

def test_d01_files_in_place():
    """D01 / D02 / D03：合同要的新文件都在位，三个页面文件还在且用 PageFrame 与 readonly1 下的视图。"""
    need_new_sources()
    problems = []
    for page, rel in PAGE_FILES.items():
        path = REPO_ROOT / rel
        if not path.is_file():
            problems.append(f"{rel} 不存在")
            continue
        text = _read(path)
        if "PageFrame" not in text or "readonly1/" not in text:
            problems.append(f"{rel} 应使用 PageFrame 并从 pages/readonly1/ 引入视图（现在还是占位）")
        if "夹具数据已读到" in text:
            problems.append(f"{rel} 仍是占位页（含「夹具数据已读到」）")
    fail_if(problems, "合同要的文件")


def test_d01_t2_router_additions_static():
    """D01 / T2：router.ts 新增导出 useAppNavigate，原有导出与 parseHash、useHashRoute 的签名不变。"""
    text = _read(need_file(f"{SRC_REL}/shell/router.ts"))
    code = strip_ts_comments(text)
    problems = []
    if not re.search(r"export\s+(?:function|const)\s+useAppNavigate\b", code) and not re.search(r"export\s*\{[^}]*\buseAppNavigate\b", code):
        problems.append("router.ts 没有导出 useAppNavigate")
    for pat, what in (
        (r"export\s+function\s+useHashRoute\s*\(\s*\)", "useHashRoute()"),
        (r"export\s+function\s+parseHash\s*\(\s*hash\s*:\s*string\s*\)\s*:\s*Route\b", "parseHash(hash: string): Route"),
        (r"export\s+const\s+SHOWCASE_ID\b", "SHOWCASE_ID"),
        (r"export\s+interface\s+Route\b", "interface Route"),
        (r"export\s*\{\s*mockOfQuery\s*\}", "export { mockOfQuery }"),
    ):
        if not re.search(pat, code):
            problems.append(f"router.ts 应保留 {what}")
    for field in ("tabId", "pageId", "segments", "query"):
        if not re.search(rf"\b{field}\s*:", code):
            problems.append(f"Route 应保留字段 {field}")
    fail_if(problems, "router.ts 的加法改动")


def test_d01_t3_attempt_groups_static():
    """D01 / T3：attemptGroups.ts 新增 AttemptGroup、ATTEMPT_GROUPS、groupOfState，countByGroup 与 StatusCounts 的签名不变。"""
    code = strip_ts_comments(_read(need_file(f"{SRC_REL}/shell/attemptGroups.ts")))
    problems = []
    for pat, what in (
        (r"export\s+type\s+AttemptGroup\b", "export type AttemptGroup"),
        (r"export\s+const\s+ATTEMPT_GROUPS\b", "export const ATTEMPT_GROUPS"),
        (r"export\s+function\s+groupOfState\s*\(\s*state\s*:\s*string\s*\)\s*:\s*AttemptGroup\s*\|\s*null", "export function groupOfState(state: string): AttemptGroup | null"),
        (r"export\s+function\s+countByGroup\s*\(\s*rows\s*:\s*StatusRow\[\]\s*\)\s*:\s*StatusCounts", "export function countByGroup(rows: StatusRow[]): StatusCounts"),
        (r"export\s+interface\s+StatusCounts\b", "export interface StatusCounts"),
    ):
        if not re.search(pat, code):
            problems.append(f"attemptGroups.ts 应有 {what}")
    for g in ("running", "review", "decide", "integrate", "ended"):
        if f"'{g}'" not in code and f'"{g}"' not in code:
            problems.append(f"attemptGroups.ts 应写出分组 ID {g}")
    fail_if(problems, "attemptGroups.ts 的加法改动")


def test_d12_index_exports_append_only():
    """D12：components/index.ts 只在末尾追加 RelativeTime、RelativeTimeProps、ActorTag、ActorTagProps，不出现 overlay，已有导出不变。"""
    text = _read(need_file(f"{COMP_REL}/index.ts"))
    fail_if(index_problems(text), "components/index.ts")


def test_d12_icons_match_contract():
    """D12：icons/index.tsx 末尾追加 4 个图标，路径等于合同，沿用 Svg 包装，同名只留一份，已有图标不变。"""
    text = _read(need_file(f"{SRC_REL}/icons/index.tsx"))
    fail_if(icon_problems(text), "icons/index.tsx")


def test_d13_no_forbidden_words_in_new_sources():
    """D13：本片新增源码里没有四个网络词、T007 禁用词、ServerIcon、@font-face 与字体文件扩展名（注释也算）。"""
    need_new_sources()
    files = new_ts_sources() + new_css_sources() + page_sources()
    fail_if(forbidden_word_problems(files, NET_WORDS + SINK_WORDS + FONT_WORDS), "禁用词")
    fail_if(forbidden_word_problems(src_ts_files(), NET_WORDS + SINK_WORDS), "src 下的禁用词（T006/T007 的规则对整个 src 有效）")


def test_d13_new_sources_rules():
    """D13：本片 ts/tsx 不渲染 role=status、不写内联 style、不调四个禁用接口、不自己写 3.4 分组状态码；进地址的部分经 encodeURIComponent。"""
    need_new_sources()
    problems = []
    files = new_ts_sources() + page_sources()
    for path in files:
        problems += role_and_interface_problems(path.relative_to(WEB).as_posix(), _read(path))
    problems += state_literal_problems(files)
    links = _read(REPO_ROOT / f"{RO_REL}/common-links.ts")
    if "encodeURIComponent" not in links:
        problems.append("common-links.ts 里没有 encodeURIComponent（进地址的部分要编码）")
    fail_if(problems, "新源码规则")


def test_d13_page_files_wiring():
    """D13 / 合同第 2 条：三页只取数并用 PageFrame；load、isEmpty 是模块级稳定函数；角色页不传 isEmpty；只调读函数。"""
    problems = []
    for page, rel in PAGE_FILES.items():
        problems += page_wiring_problems(page, _read(need_file(rel)))
    fail_if(problems, "三页的接线")


def test_d13_views_do_not_call_api():
    """D13 / 合同第 2 条：readonly1 下的视图只收数据与回调，从 api 只许 import type。"""
    need_new_sources()
    fail_if(view_api_problems(new_ts_sources()), "视图不调 api")


# 样式表接线：CSS 取值检查只读文件文本，证明不了样式表被应用；这里查 import 图与构建产物（终审 B2）
ENTRY_REL = f"{SRC_REL}/main.tsx"
IMPORT_RE = re.compile(r"""(?:\bimport|\bexport)\s*(?P<head>[^'"`;()]*?)\bfrom\s*['"](?P<from>[^'"]+)['"]"""
                       r"""|\bimport\s*['"](?P<bare>[^'"]+)['"]"""
                       r"""|\bimport\s*\(\s*['"](?P<dyn>[^'"]+)['"]\s*\)""")
RESOLVE_SUFFIXES = ("", ".ts", ".tsx", ".css", "/index.ts", "/index.tsx")


def import_specs(text):
    """返回源码里会生效的相对 import 说明符：不含 import type，不含带 ?inline、?raw、?url 等查询的。"""
    specs = []
    for m in IMPORT_RE.finditer(strip_ts_comments(text)):
        if m.group("from") is not None:
            if re.match(r"\s*(?:type\b|\{\s*\}\s*$)", m.group("head")):
                continue
            specs.append(m.group("from"))
        else:
            specs.append(m.group("bare") or m.group("dyn"))
    return [s for s in specs if s.startswith(".") and "?" not in s]


def resolve_import(files, current, spec):
    base = posixpath.normpath(posixpath.join(posixpath.dirname(current), spec))
    for suffix in RESOLVE_SUFFIXES:
        if base + suffix in files:
            return base + suffix
    return None


def reachable_from(files, entry):
    """files: {仓库相对路径: 文本}；从入口顺着 import 能到的文件集合。"""
    seen, todo = set(), [entry] if entry in files else []
    while todo:
        cur = todo.pop()
        if cur in seen:
            continue
        seen.add(cur)
        if cur.endswith(".css"):
            continue
        for spec in import_specs(files[cur]):
            nxt = resolve_import(files, cur, spec)
            if nxt is not None and nxt not in seen:
                todo.append(nxt)
    return seen


def css_wiring_problems(files, css_rels, entry=ENTRY_REL):
    problems = []
    if entry not in files:
        return [f"{entry} 不存在"]
    reached = reachable_from(files, entry)
    for rel in css_rels:
        if rel not in files:
            problems.append(f"{rel} 不存在")
            continue
        if rel in reached:
            continue
        importers = sorted(cur for cur, text in files.items()
                           if not cur.endswith(".css") and any(resolve_import(files, cur, s) == rel for s in import_specs(text)))
        if importers:
            problems.append(f"{rel} 只被 {importers} 引入，而它们从 {entry} 出发到不了：样式表没进应用")
        else:
            problems.append(f"{rel} 没有任何 .ts/.tsx 以 import 引入（样式表没接线，页面不会套用它）")
    return problems


def src_files_by_rel():
    files = {}
    for path in sorted(SRC.rglob("*")):
        if path.suffix in (".ts", ".tsx", ".css") and path.is_file():
            files[path.relative_to(REPO_ROOT).as_posix()] = _read(path)
    return files


def test_d13_css_files_are_imported_into_app():
    """D13 / D01 / 终审 B2：四份 CSS 都被应用用上——从 src/main.tsx 顺着 import 能到达每一份（光写 CSS 文件、没人 import，页面不套用它）。"""
    need_new_sources()
    fail_if(css_wiring_problems(src_files_by_rel(), list(CSS_FILES.values())), "样式表接线")


CLASS_RE = re.compile(r"\.(-?[_a-zA-Z][\w-]*)")


def css_classes(css):
    out = set()
    for selector, _decls in parse_rules(css):
        out |= set(CLASS_RE.findall(re.sub(r"\"[^\"]*\"|'[^']*'", "", selector)))
    return out


def built_css_problems(built, texts):
    """built: dist/assets 下 CSS 的合并文本；texts: {键: 源 CSS 文本}。每份源 CSS 至少一个独有的类选择器要出现在构建产物里。"""
    problems = []
    classes = {key: css_classes(text) for key, text in texts.items()}
    for key, own in classes.items():
        others = set().union(*(c for k, c in classes.items() if k != key))
        pool = sorted(own - others)
        if not pool:
            problems.append(f"{key}：没有这份 CSS 独有的类选择器可核对（请换一个有独有类的写法）")
        elif not any(re.search(rf"\.{re.escape(name)}(?![\w-])", built) for name in pool):
            problems.append(f"{key}：构建产物 dist/assets/*.css 里找不到它独有的类（如 .{pool[0]}），样式表没被打进构建")
    return problems


def test_d13_css_values_match_section_8():
    """D13 / §8：四份 CSS 合并后的取值——每条是“有一条规则同时声明了这几项”（合同没规定规则写在哪份文件）。"""
    need_new_sources()
    fail_if(css_value_problems(), "CSS 取值")


def test_d13_css_tokens_px_comments_and_w4():
    """D13：层级、圆角、阴影、字体只用令牌；除 0 与 1px 外的 px 字面量同一行带出处注释；W4 的坑（颜色字面量、颜色函数、拼接令牌名）。"""
    need_new_sources()
    problems = []
    for key, rel in CSS_FILES.items():
        raw = _read(REPO_ROOT / rel)
        problems += token_only_problems(rel.rsplit("/", 1)[-1], raw)
        problems += px_literal_problems(rel.rsplit("/", 1)[-1], raw)
    problems += w4_pitfall_problems(new_ts_sources() + new_css_sources() + page_sources())
    fail_if(problems, "令牌、px 注释与 W4")


def test_d14_executor_tests_in_place():
    """D14：执行端的 8 份测试在位、有用例、不用 skip、only、todo。"""
    fail_if(executor_test_problems(), "执行端测试")


def test_transitional_shell_app_only_overview_case_changed():
    """后续任务若再改 tests/shell-app.test.tsx（例如任务页那一片调整总览以外的断言）就推翻它，站主在后续任务开工合同之前退役。

    D14 / 站主 Q2：tests/shell-app.test.tsx 只改第 32–37 行「总览占位显示夹具数据与条数」这一条：
    前 31 行与后面各条逐字同基线，中间换成断言真页面。"""
    text = _read(need_file(f"{WEB_REL}/tests/shell-app.test.tsx"))
    fail_if(shell_app_problems(text), "shell-app.test.tsx")


# ---------------------------------------------------------------------------
# 流水线断言
# ---------------------------------------------------------------------------

def test_d14_npm_steps_pass(pipeline):
    """D14：npm ci、构建、Vitest（含执行端 8 份新测试与改过的 shell-app）、W4 契约检查都通过。"""
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    out = pipeline.steps["npm test"].out
    assert not re.search(r"Tests\s+.*\b(skipped|todo)\b", out), f"npm test 里有跳过或待办：\n{pipeline.steps['npm test'].tail}"
    for name in EXECUTOR_TESTS:
        assert name in out.replace("\\", "/"), f"npm test 的输出里没有 {name}，可能没被 Vitest 选中：\n{pipeline.steps['npm test'].tail}"


def test_d01_probe_t3_attempt_groups(pipeline):
    """D01 / T3：ATTEMPT_GROUPS、groupOfState 的映射、countByGroup 不变（Vitest 探针 shell）。"""
    assert_probe_group(pipeline, "shell", "D01 T3 分组函数")


def test_d01_probe_t2_navigate_merges_query(pipeline):
    """D01 / T2：navigate 合并查询参数、path 无查询时行为不变、useAppNavigate 稳定且同步、parseHash 不变（Vitest 探针 shell）。"""
    assert_probe_group(pipeline, "shell", "D01 T2 导航合并查询")


def test_d12_probe_relative_time(pipeline):
    """D12：RelativeTime 四档、边界、title 格式、解析不了、不每秒更新、now 属性（Vitest 探针 common）。"""
    assert_probe_group(pipeline, "common", "D12 RelativeTime")


def test_d12_probe_actor_tag(pipeline):
    """D12：ActorTag 五种色调、等宽（Vitest 探针 common）。"""
    assert_probe_group(pipeline, "common", "D12 ActorTag")


def test_d12_probe_exports_and_icons(pipeline):
    """D12：index 追加导出、四个新图标的渲染形状、已有图标仍在（Vitest 探针 common）。"""
    assert_probe_group(pipeline, "common", "D12 导出与图标")


def test_d02_probe_copy_text(pipeline):
    """D02：copyText 三态与缺省取 navigator.clipboard（Vitest 探针 common）。"""
    assert_probe_group(pipeline, "common", "D02 copyText")


def test_d01_probe_metric_cards_and_links(pipeline):
    """D01：四张指标卡、计数、链接地址、点击后的路由、修饰键不拦截（Vitest 探针 overview）。"""
    assert_probe_group(pipeline, "overview", "D01 指标卡与链接")


def test_d01_tone_stripe_colors(pipeline):
    """D01：指标卡色调条的四种颜色令牌挂在对应卡独有的钩子上（探针导出钩子，这里读 CSS）。"""
    assert pipeline.ran, pipeline.reason
    data = pipeline.probe_data.get("overview")
    assert data, f"探针 overview 没有导出指标卡的钩子数据：{pipeline.probe_skipped.get('overview') or pipeline.probe_unparsed.get('overview') or '探针未能写出数据'}"
    css = "\n".join(css_text(key) for key in CSS_FILES)
    fail_if(tone_problems(css, data["metrics"]), "色调条")


def test_d13_css_classes_in_built_bundle(pipeline):
    """D13 / D01 / 终审 B2：npm run build 之后 dist/assets/*.css 含四份 CSS 各自一个独有的类选择器（从文件里解析）。"""
    assert_step_ok(pipeline, "npm run build")
    assets = sorted((WEB / "dist" / "assets").glob("*.css"))
    assert assets, f"{WEB_REL}/dist/assets 下没有 CSS 产物"
    built = "\n".join(_read(path) for path in assets)
    fail_if(built_css_problems(built, {key: css_text(key) for key in CSS_FILES}), "构建产物里的样式表")


def test_d02_probe_need_judge(pipeline):
    """D02：需要你判断的行、顺序、用时、检查、证据地址、计数胶囊、下一步、复制三态（Vitest 探针 overview）。"""
    assert_probe_group(pipeline, "overview", "D02 需要你判断")


def test_d03_probe_running_and_integrate(pipeline):
    """D03：运行中与待集成的行、long_idle 标签、跟随事件地址、下一步、无行不渲染、时长格式化（Vitest 探针 overview）。"""
    assert_probe_group(pipeline, "overview", "D03 运行中与待集成")


def test_d04_probe_config_changes(pipeline):
    """D04：最近的配置变更——5 条上限倒序、相对时间与 title、动作说明、外部改动、执行者色调、空与出错（Vitest 探针 overview）。"""
    assert_probe_group(pipeline, "overview", "D04 最近的配置变更")


def test_d05_probe_overview_states(pipeline):
    """D05：总览组合读取与五态（注入数据）：并行、status 出错、history 出错、空、加载、说明（Vitest 探针 overview）。"""
    assert_probe_group(pipeline, "overview", "D05 总览读取与五态")


def test_d06_probe_role_cards(pipeline):
    """D06：四种模式的角色卡——标签、键值、说明、EffortPair 四种情形、[更改…]、页头入口（Vitest 探针 roles）。"""
    assert_probe_group(pipeline, "roles", "D06 角色卡")


def test_d06_probe_roles_combined_read(pipeline):
    """D06：角色页组合读取——并行、第一个失败信封的顺序、不传 isEmpty（Vitest 探针 roles）。"""
    assert_probe_group(pipeline, "roles", "D06 角色页组合读取")


def test_d07_probe_preset_bar(pipeline):
    """D07：当前方案——分段选项与初值、两种说明、[切换…] 始终禁用、无方案时的文字（Vitest 探针 roles）。"""
    assert_probe_group(pipeline, "roles", "D07 当前方案")


def test_d08_probe_profiles_table(pipeline):
    """D08：profile 表——各列、thinking 缺省、凭据标签、被引用、操作禁用、空时文字（Vitest 探针 roles）。"""
    assert_probe_group(pipeline, "roles", "D08 profile 表")


def test_d09_probe_presets_table(pipeline):
    """D09：方案表——各列、当前行、[使用][删除…] 禁用、[查看差异] 可用（Vitest 探针 roles）。"""
    assert_probe_group(pipeline, "roles", "D09 方案表")


def test_d09_probe_preset_diff(pipeline):
    """D09：差异面板——一次调用、读取中/出错/有数据、收起、只开一个、过期回应丢弃、绑定文字与减号（Vitest 探针 roles）。"""
    assert_probe_group(pipeline, "roles", "D09 差异面板")


def test_d10_probe_runtimes_table(pipeline):
    """D10：CLI 运行时表——各列、能担任、来源标签、notes、命令截断、版本、操作规则、页头入口（Vitest 探针 runtimes）。"""
    assert_probe_group(pipeline, "runtimes", "D10 CLI 运行时表")


def test_d10_probe_readiness_and_empty(pipeline):
    """D10：就绪检查区、空态、读取失败（Vitest 探针 runtimes）。"""
    assert_probe_group(pipeline, "runtimes", "D10 就绪检查区与空态")


def test_d11_probe_write_entries_disabled(pipeline):
    """D11：三页写入口全部禁用且悬停出提示，可用按钮与链接只在白名单里，不渲染 role=status、没有内联 style（Vitest 探针 pages，注入数据）。"""
    assert_probe_group(pipeline, "pages", "D11 写入口全部禁用")


def test_transitional_trans1_three_pages_five_states_via_mock(pipeline):
    """接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据）。

    D05 / D10：经 ?mock= 渲染 App 三页的五态（data、offline、loading、error、empty）。"""
    assert_probe_group(pipeline, "pages", "TRANS1 经 ?mock= 渲染三页的五态")


def test_transitional_trans2_fixture_values(pipeline):
    """接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据）。

    D01–D10：夹具里的具体值——指标 1/2/1/1、各行文字、角色卡与两张表、运行时三行。"""
    assert_probe_group(pipeline, "pages", "TRANS2 夹具里的具体值")


def test_transitional_trans3_write_entry_counts(pipeline):
    """接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据）。

    D11：夹具下写入口个数——角色页 13、运行时页 9、总览 0。"""
    assert_probe_group(pipeline, "pages", "TRANS3 夹具下写入口的个数")


def test_d14_worktree_unchanged_by_pipeline(pipeline):
    """D14：流水线前后 git status 不变，gate-probe 目录已清理，不许改的依赖与框架文件逐字节不变。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.gate_probe_left is False, "gate-probe 目录没有清理干净"
    added = sorted(pipeline.status_after - pipeline.status_before)
    removed = sorted(pipeline.status_before - pipeline.status_after)
    assert not added and not removed, f"流水线改动了工作区：新增 {added[:10]}，消失 {removed[:10]}"
    changed = [n for n in WATCHED if pipeline.digests_before.get(n) != pipeline.digests_after.get(n)]
    assert not changed, f"流水线改动了不该动的文件：{changed}"


# ---------------------------------------------------------------------------
# 门禁自检（不依赖候选）：把检查函数喂给正确样本和改坏的样本
# ---------------------------------------------------------------------------

GOOD_COMMON_CSS = """
.ro-section { background: var(--tt-surface-1); border: 1px solid var(--tt-border); border-radius: var(--tt-radius-lg); }
.ro-section__head { padding: var(--tt-space-3) var(--tt-space-4); }
.ro-section__title { font: var(--tt-title-sm); }
.ro-section__desc { font: var(--tt-text-caption); color: var(--tt-text-3); }
.ro-section__link { font: var(--tt-text-sm); color: var(--tt-link); text-decoration: none; }
"""
GOOD_OVERVIEW_CSS = """
.ov-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--tt-space-4); }
.ov-metric { background: var(--tt-surface-1); border: 1px solid var(--tt-border); border-radius: var(--tt-radius-lg); overflow: hidden; text-decoration: none; padding: var(--tt-space-3) var(--tt-space-4) var(--tt-space-3) var(--tt-space-5); }
.ov-metric:hover { background: var(--tt-surface-2); }
.ov-metric__bar { width: 3px; } /* 画布 */
.ov-metric__num { font: var(--tt-display); }
.ov-metric[data-metric="running"] .ov-metric__bar { background: var(--tt-tone-info-fg); }
.ov-metric[data-metric="review"] .ov-metric__bar { background: var(--tt-accent); }
.ov-metric[data-metric="decide"] .ov-metric__bar { background: var(--tt-tone-escalate-fg); }
.ov-metric[data-metric="integrate"] .ov-metric__bar { background: var(--tt-tone-brand-fg); }
.ov-judge { border-left: 3px solid var(--tt-accent); }
.ov-pill { min-width: 20px; height: 18px; border-radius: var(--tt-radius-full); background: var(--tt-accent); color: var(--tt-on-accent); font: var(--tt-text-caption-strong); }
.ov-row { display: grid; grid-template-columns: 104px minmax(0, 1fr) auto auto; gap: var(--tt-space-3); min-height: 44px; padding: 0 var(--tt-space-4); border-top: 1px solid var(--tt-border); }
.ov-row:hover { background: var(--tt-surface-3); }
.ov-row__link { height: 28px; padding: 0 var(--tt-space-2); border-radius: var(--tt-radius-md); font: var(--tt-text-sm-medium); text-decoration: none; }
.ov-row__info { font: var(--tt-text-sm); color: var(--tt-text-2); }
.ov-change { display: grid; grid-template-columns: 48px 92px 120px minmax(0, 1fr) auto; gap: var(--tt-space-3); height: 36px; padding: 0 var(--tt-space-4); }
.ov-note { margin: var(--tt-space-3) var(--tt-space-4) var(--tt-space-4); font: var(--tt-text-caption); color: var(--tt-text-3); }
"""
GOOD_ROLES_CSS = """
.rl-bar { display: flex; flex-wrap: wrap; gap: var(--tt-space-3) var(--tt-space-4); padding: var(--tt-space-3) var(--tt-space-4); }
.rl-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--tt-space-4); }
.rl-card { display: flex; flex-direction: column; gap: var(--tt-space-2); padding: var(--tt-space-4); }
.rl-kv { display: grid; grid-template-columns: 64px minmax(0, 1fr); }
.rl-table.tt-table-wrap { border: 0; border-radius: 0; border-top: 1px solid var(--tt-border); }
.rl-profile .tt-table { min-width: 860px; }
.rl-preset .tt-table { min-width: 760px; }
.rl-table td:last-child, .rl-table th:last-child { text-align: right; }
.rl-diff { padding: var(--tt-space-3); border-radius: var(--tt-radius-md); background: var(--tt-surface-2); border: 1px solid var(--tt-border); }
.rl-diff__row { display: grid; grid-template-columns: 96px minmax(0, 1fr) 24px minmax(0, 1fr); }
.rl-diff__del { background: var(--tt-diff-del); }
.rl-diff__add { background: var(--tt-diff-add); }
.rl-diff__val { padding: var(--tt-space-0_5) var(--tt-space-1); border-radius: var(--tt-radius-sm); font: var(--tt-mono-sm); }
"""
GOOD_RUNTIMES_CSS = """
.rt-table.tt-table-wrap { border: 0; border-radius: 0; border-top: 1px solid var(--tt-border); }
.rt-table .tt-table { min-width: 900px; }
.rt-table td:last-child { text-align: right; }
.rt-cmd { max-width: 280px; overflow: hidden; white-space: nowrap; font: var(--tt-mono-sm); }
.rt-ready { padding: var(--tt-space-5); text-align: center; border: 1px dashed var(--tt-border-strong); border-radius: var(--tt-radius-md); font: var(--tt-text-sm); color: var(--tt-text-3); }
"""
GOOD_CSS = {"common": GOOD_COMMON_CSS, "overview": GOOD_OVERVIEW_CSS, "roles": GOOD_ROLES_CSS, "runtimes": GOOD_RUNTIMES_CSS}
CSS_MUTANTS = {
    "common": [("var(--tt-surface-1)", "var(--tt-surface-2)"), ("var(--tt-title-sm)", "var(--tt-text-sm)"), ("text-decoration: none", "text-decoration: underline"),
               ("padding: var(--tt-space-3) var(--tt-space-4)", "padding: var(--tt-space-2) var(--tt-space-4)")],
    "overview": [("repeat(4, minmax(0, 1fr))", "repeat(3, minmax(0, 1fr))"), ("104px", "100px"), ("overflow: hidden", "overflow: visible"),
                 ("3px solid var(--tt-accent)", "2px solid var(--tt-accent)"), ("min-width: 20px", "min-width: 18px"), ("height: 36px", "height: 32px"),
                 ("48px 92px 120px", "48px 92px 100px"), ("var(--tt-space-3) var(--tt-space-4) var(--tt-space-3) var(--tt-space-5)", "var(--tt-space-3) var(--tt-space-4)"),
                 ("background: var(--tt-surface-3)", "background: var(--tt-surface-2)"), ("width: 3px", "width: 4px"), ("min-height: 44px", "min-height: 40px"),
                 ("margin: var(--tt-space-3) var(--tt-space-4) var(--tt-space-4)", "margin: var(--tt-space-3) var(--tt-space-4)")],
    "roles": [("repeat(2, minmax(0, 1fr))", "repeat(3, minmax(0, 1fr))"), ("min-width: 860px", "min-width: 800px"), ("min-width: 760px", "min-width: 700px"),
              ("flex-wrap: wrap", "flex-wrap: nowrap"), ("64px minmax", "60px minmax"), ("96px minmax", "90px minmax"), ("var(--tt-diff-del)", "var(--tt-diff-add)"),
              ("text-align: right", "text-align: left"), ("border-radius: 0;", "border-radius: 8px;"), ("padding: var(--tt-space-4);", "padding: var(--tt-space-3);")],
    "runtimes": [("min-width: 900px", "min-width: 800px"), ("max-width: 280px", "max-width: 260px"), ("1px dashed", "1px solid"), ("text-align: center", "text-align: left"),
                 ("white-space: nowrap", "white-space: normal"), ("border-top: 1px solid var(--tt-border);", "border-top: 0;")],
}


def test_gate_selfcheck_css_samples_pass_and_mutants_fail():
    assert css_value_problems(GOOD_CSS) == [], f"正确样本应通过：{css_value_problems(GOOD_CSS)}"
    for key, mutants in CSS_MUTANTS.items():
        for old, new in mutants:
            assert old in GOOD_CSS[key], f"{key}：变异的原文不在样本里：{old}"
            # 合并求值后，几份文件里同形的规则会互相掩护：把变异施加到每份文件的所有出现处
            mutated = {k: text.replace(old, new) for k, text in GOOD_CSS.items()}
            assert css_value_problems(mutated), f"{key}：变异没被抓住：{old!r} -> {new!r}"


def test_gate_selfcheck_css_rules_may_live_in_any_file():
    """合同 §8 没规定规则写在哪份文件：把表格覆盖、最后一列靠右、复制结果行挪到 common 里仍应通过；全删则应被抓住。"""
    moved = dict(GOOD_CSS)
    lines_roles = GOOD_ROLES_CSS.strip().splitlines()
    shared = [ln for ln in lines_roles if "tt-table-wrap" in ln or "td:last-child" in ln]
    assert len(shared) == 2
    moved["roles"] = "\n".join(ln for ln in lines_roles if ln not in shared)
    moved["runtimes"] = "\n".join(ln for ln in GOOD_RUNTIMES_CSS.strip().splitlines() if "tt-table-wrap" not in ln and "td:last-child" not in ln)
    moved["common"] = GOOD_COMMON_CSS + "\n".join(shared) + "\n"
    note = [ln for ln in GOOD_OVERVIEW_CSS.splitlines() if ".ov-note" in ln]
    assert len(note) == 1
    moved["overview"] = GOOD_OVERVIEW_CSS.replace(note[0], "")
    moved["common"] += note[0] + "\n"
    assert css_value_problems(moved) == [], css_value_problems(moved)
    none = dict(moved)
    none["common"] = GOOD_COMMON_CSS
    assert css_value_problems(none), "把共享规则全删应被抓住"


def test_gate_selfcheck_tone_problems():
    css = GOOD_OVERVIEW_CSS
    metrics = [{"metric": m, "hooks": [".ov-metric", ".ov-metric__bar", f"[data-metric={m}]"]} for m in TONE_TOKENS]
    assert tone_problems(css, metrics) == []
    swapped = css.replace("var(--tt-tone-info-fg)", "var(--tt-tone-brand-fg)", 1)
    assert tone_problems(swapped, metrics), "色调条互换没被抓住"
    missing = css.replace('.ov-metric[data-metric="decide"] .ov-metric__bar { background: var(--tt-tone-escalate-fg); }', "")
    assert tone_problems(missing, metrics), "缺一张卡的色调没被抓住"
    shared = [{"metric": m, "hooks": [".ov-metric"]} for m in TONE_TOKENS]
    assert tone_problems(css, shared), "各卡没有独有钩子没被抓住"
    assert tone_problems(css, metrics[:3]), "少一张卡的数据没被抓住"


def _wiring_files():
    ro = RO_REL
    return {
        ENTRY_REL: "import App from './App';\nimport './styles/base.css';\n",
        f"{SRC_REL}/App.tsx": "import { TABS } from './shell/routes';\nimport './App.css';\n",
        f"{SRC_REL}/App.css": ".app {}",
        f"{SRC_REL}/styles/base.css": "body {}",
        f"{SRC_REL}/shell/routes.ts": "import OverviewPage from '../pages/OverviewPage';\nimport RolesPage from '../pages/RolesPage';\n"
                                      "import RuntimesPage from '../pages/RuntimesPage';\n",
        f"{SRC_REL}/pages/OverviewPage.tsx": "import { OverviewView } from './readonly1/overview-OverviewView';\n",
        f"{SRC_REL}/pages/RolesPage.tsx": "import { RolesView } from './readonly1/roles-RolesView';\n",
        f"{SRC_REL}/pages/RuntimesPage.tsx": "import { RuntimesView } from './readonly1/runtimes-RuntimesView';\n",
        f"{ro}/overview-OverviewView.tsx": "import { Section } from './common-Section';\nimport './overview-styles.css';\n",
        f"{ro}/roles-RolesView.tsx": "import { Section } from './common-Section';\nimport './roles-styles.css';\n",
        f"{ro}/runtimes-RuntimesView.tsx": "import { Section } from './common-Section';\nimport './runtimes-styles.css';\n",
        f"{ro}/common-Section.tsx": "import './common-section.css';\n",
        f"{ro}/overview-styles.css": ".ov-a {}",
        f"{ro}/roles-styles.css": ".ro-a {}",
        f"{ro}/runtimes-styles.css": ".rt-a {}",
        f"{ro}/common-section.css": ".ro-section {}",
    }


def test_gate_selfcheck_css_wiring():
    css_rels = list(CSS_FILES.values())
    good = _wiring_files()
    assert css_wiring_problems(good, css_rels) == [], css_wiring_problems(good, css_rels)
    # 去掉某条 import：对应那份 CSS 必须报问题，且只报它
    for importer, line in ((f"{RO_REL}/overview-OverviewView.tsx", "import './overview-styles.css';\n"),
                           (f"{RO_REL}/roles-RolesView.tsx", "import './roles-styles.css';\n"),
                           (f"{RO_REL}/runtimes-RuntimesView.tsx", "import './runtimes-styles.css';\n"),
                           (f"{RO_REL}/common-Section.tsx", "import './common-section.css';\n")):
        assert line in good[importer]
        mutated = dict(good)
        mutated[importer] = good[importer].replace(line, "")
        problems = css_wiring_problems(mutated, css_rels)
        assert len(problems) == 1 and line.split("/")[-1].split("'")[0] in problems[0], (line, problems)
    # 去掉三页样式表的 import（当前候选的状况）：三份都报
    mutated = dict(good)
    for importer in (f"{RO_REL}/overview-OverviewView.tsx", f"{RO_REL}/roles-RolesView.tsx", f"{RO_REL}/runtimes-RuntimesView.tsx"):
        mutated[importer] = re.sub(r"import '\./[a-z]+-styles\.css';\n", "", good[importer])
    assert len(css_wiring_problems(mutated, css_rels)) == 3
    # 视图被页面用着才算：切断页面到视图的 import，视图里的 CSS import 就不生效
    mutated = dict(good)
    mutated[f"{SRC_REL}/pages/RolesPage.tsx"] = ""
    problems = css_wiring_problems(mutated, css_rels)
    assert len(problems) == 1 and "roles-styles.css" in problems[0] and "到不了" in problems[0], problems
    # 切断路由到页面的 import
    mutated = dict(good)
    mutated[f"{SRC_REL}/shell/routes.ts"] = ""
    assert len(css_wiring_problems(mutated, css_rels)) == 4  # 公共节样式也只经视图到达
    # 只有 import type、带 ?inline 的 import、被注释掉的 import 都不算
    for fake in ("import type { X } from './overview-styles.css';\n", "import s from './overview-styles.css?inline';\n",
                 "// import './overview-styles.css';\n", "/* import './overview-styles.css'; */\n"):
        mutated = dict(good)
        mutated[f"{RO_REL}/overview-OverviewView.tsx"] = "import { Section } from './common-Section';\n" + fake
        assert css_wiring_problems(mutated, css_rels), fake
    # 动态 import、绑定形式的 import、目录 index 都算接线
    mutated = dict(good)
    mutated[f"{RO_REL}/overview-OverviewView.tsx"] = "import { Section } from './common-Section';\nconst p = import('./overview-styles.css');\n"
    assert css_wiring_problems(mutated, css_rels) == []
    mutated[f"{RO_REL}/overview-OverviewView.tsx"] = "import { Section } from './common-Section';\nimport s from './overview-styles.css';\n"
    assert css_wiring_problems(mutated, css_rels) == []
    assert css_wiring_problems({k: v for k, v in good.items() if k != ENTRY_REL}, css_rels)
    assert css_wiring_problems({k: v for k, v in good.items() if k != f"{RO_REL}/roles-styles.css"}, css_rels)


def test_gate_selfcheck_built_css_problems():
    texts = {"common": ".ro-section { color: red } .tt-x { margin: 0 }", "overview": ".ov-a { color: red } .tt-x { margin: 0 }",
             "roles": '.ro-a, [data-k="v.w"] .ro-b { color: red }', "runtimes": "@media (min-width: 1px) { .rt-a { color: red } }"}
    assert css_classes(texts["roles"]) == {"ro-a", "ro-b"}
    built = ".ro-section{color:red}.ov-a{color:red}.ro-b{color:red}.rt-a{color:red}.tt-x{margin:0}"
    assert built_css_problems(built, texts) == []
    for gone, part in ((".ro-section{color:red}", "common"), (".ov-a{color:red}", "overview"), (".ro-b{color:red}", "roles"), (".rt-a{color:red}", "runtimes")):
        problems = built_css_problems(built.replace(gone, ""), texts)
        assert len(problems) == 1 and problems[0].startswith(part), (part, problems)
    # 共享的类（两份都有 .tt-x）和前缀相同的别的类都不能顶替
    assert built_css_problems(built.replace(".ov-a{color:red}", ".ov-abc{color:red}"), texts)
    assert built_css_problems(".tt-x{margin:0}", texts)
    assert built_css_problems(built, {**texts, "roles": ".tt-x { margin: 0 }"}), "没有独有类可核对应报问题"


def test_gate_selfcheck_css_helpers():
    assert px_literal_problems("x", ".a { width: 7px; } /* 出处 */\n.b { height: 1px; width: 0px; }\n") == []
    assert px_literal_problems("x", ".a { width: 7px; }\n"), "没有注释的 px 应被抓住"
    assert px_literal_problems("x", "/* 出处 */\n.a { width: 7px; }\n"), "注释在上一行不算同一行"
    assert token_only_problems("x", ".a { border-radius: var(--tt-radius-md); z-index: var(--tt-z-menu); font: var(--tt-text-sm); }") == []
    assert token_only_problems("x", ".a { border-radius: 8px; }")
    assert token_only_problems("x", ".a { font-family: sans-serif; }")
    assert token_only_problems("x", ".a { box-shadow: 0 1px 2px black; }")
    assert box_sides([("padding", "0 var(--tt-space-4)")], "padding")["left"] == "var(--tt-space-4)"
    assert box_sides([("margin", "1px 2px 3px")], "margin") == {"top": "1px", "right": "2px", "bottom": "3px", "left": "2px"}
    assert cv(" Var(--X)  !important ") == "var(--x)"
    rules = parse_rules("@container (min-width: 1px) { .a { color: red; } } .b { color: blue; } @keyframes k { from { color: red; } }")
    assert [sel for sel, _ in rules] == [".a", ".b"]


def test_gate_selfcheck_source_checks(tmp_path, monkeypatch):
    p = tmp_path / "x.tsx"
    p.write_text("const a = <div style={{ color: 'x' }} />;\n", encoding="utf-8")
    monkeypatch.setitem(globals(), "WEB", tmp_path)
    assert role_and_interface_problems("x", _read(p)), "内联 style 应被抓住"
    assert role_and_interface_problems("x", "const a = <div role=\"status\" />;")
    assert role_and_interface_problems("x", "window.matchMedia('x');")
    assert role_and_interface_problems("x", "// role=\"status\" 只在注释里\nconst a = 1;") == []
    assert w4_pitfall_problems([p]) == []
    p.write_text("const c = '#fff';\n", encoding="utf-8")
    assert w4_pitfall_problems([p]), "十六进制颜色应被抓住"
    p.write_text("const c = 'rgb(1,2,3)';\n", encoding="utf-8")
    assert w4_pitfall_problems([p])
    p.write_text("const c = `--tt-${name}`;\n", encoding="utf-8")
    assert w4_pitfall_problems([p])
    p.write_text("const s = 'RUNNING';\n// 'PASS' 在注释里\n", encoding="utf-8")
    assert len(state_literal_problems([p])) == 1
    p.write_text("import type { StatusRow } from '../../api';\nimport { getStatus } from '../../api';\n", encoding="utf-8")
    assert len(view_api_problems([p])) == 1
    p.write_text("import type { StatusRow } from '../../api';\n", encoding="utf-8")
    assert view_api_problems([p]) == []
    p.write_text("import { type StatusRow, type HistoryData } from '../../api';\n", encoding="utf-8")
    assert view_api_problems([p]) == [], "纯类型的 import { type A } 不调 api，应放行"
    p.write_text("import { getStatus, type StatusRow } from '../../api';\n", encoding="utf-8")
    assert len(view_api_problems([p])) == 1, "混了值导入应被抓住"
    assert word_hit("a fetch(b)", NET_WORDS[0])
    assert not word_hit("prefetchAll()", NET_WORDS[0])
    assert word_hit("x.innerHTML = 1", SINK_WORDS[1])
    assert word_hit("run eval(x)", SINK_WORDS[4])


def test_gate_selfcheck_src_scan_has_no_false_positive_on_existing_sources():
    """整个 src 的禁用词扫描在已有源码上不误报（T006、T007 已保证它们干净）；任何后续片都该保持干净。"""
    assert src_ts_files(), "src 下应有 ts/tsx"
    assert forbidden_word_problems(src_ts_files(), NET_WORDS + SINK_WORDS) == []


GOOD_PAGE = """
import { PageFrame } from '../shell/PageFrame';
import { getStatus, getHistory, getMetaNow, getMeta, type StatusData } from '../api';
import { OverviewView } from './readonly1/overview-OverviewView';
const loadOverview = () => Promise.all([getStatus(), getHistory()]);
const isOverviewEmpty = (d: any) => d.status.length === 0;
export default function OverviewPage() {
  return <PageFrame title="总览" load={loadOverview} isEmpty={isOverviewEmpty}>{(d) => <OverviewView {...d} />}</PageFrame>;
}
"""


def test_gate_selfcheck_page_wiring():
    assert page_wiring_problems("overview", GOOD_PAGE) == []
    assert page_wiring_problems("overview", GOOD_PAGE.replace("load={loadOverview}", "load={() => getStatus()}")), "内联 load 应被抓住"
    assert page_wiring_problems("overview", GOOD_PAGE.replace("isEmpty={isOverviewEmpty}", "isEmpty={(d) => !d}")), "内联 isEmpty 应被抓住"
    assert page_wiring_problems("overview", GOOD_PAGE.replace("isEmpty={isOverviewEmpty}", "")), "缺 isEmpty 应被抓住"
    assert page_wiring_problems("overview", GOOD_PAGE.replace("getMeta,", "getMeta, setRole,")), "写函数应被抓住"
    assert page_wiring_problems("overview", GOOD_PAGE.replace("PageFrame", "Frame")), "不用 PageFrame 应被抓住"
    roles = GOOD_PAGE.replace("isEmpty={isOverviewEmpty}", "")
    assert page_wiring_problems("roles", roles) == []
    assert page_wiring_problems("roles", GOOD_PAGE), "角色页传 isEmpty 应被抓住"


GOOD_INDEX_TAIL = """
// 第 8 片：相对时间与执行者标签
export { RelativeTime } from './RelativeTime';
export type { RelativeTimeProps } from './RelativeTime';
export { ActorTag } from './ActorTag';
export type { ActorTagProps } from './ActorTag';
"""
GOOD_ICON_TAIL = """
// 第 8 片新增的四个图标
export const PlusIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M5 12h14" />
    <path d="M12 5v14" />
  </Svg>
);

export const SearchIcon = (props: IconProps) => (
  <Svg {...props}>
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.3-4.3" />
  </Svg>
);

export const PlayIcon = (props: IconProps) => (
  <Svg {...props}>
    <polygon points="6 3 20 12 6 21 6 3" />
  </Svg>
);

export const ArrowRightIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M5 12h14" />
    <path d="m12 5 7 7-7 7" />
  </Svg>
);
"""


def test_gate_selfcheck_icon_and_index_checks():
    assert icon_problems(GOOD_ICON_TAIL, check_prefix=False) == []
    for old, new in (("M12 5v14", "M12 5v13"), ('r="8"', 'r="9"'), ("6 3 20 12 6 21 6 3", "6 3 20 12 6 21"), ("m12 5 7 7-7 7", "m12 5 7 7-7 8"),
                     ("<Svg {...props}>\n    <polygon", "<g {...props}>\n    <polygon")):
        assert icon_problems(GOOD_ICON_TAIL.replace(old, new, 1), check_prefix=False), f"图标变异没被抓住：{old}"
    assert icon_problems(GOOD_ICON_TAIL + "export const PlusIcon = (p: IconProps) => <Svg {...p} />;\n", check_prefix=False), "同名两份应被抓住"
    assert icon_problems(GOOD_ICON_TAIL.replace("<path d=\"M5 12h14\" />", "<path d=\"M5 12h14\" stroke=\"red\" />", 1), check_prefix=False)
    head = "// 统一导出组件，共五片：\n" + "".join(f"export {{ {n} }} from './{n}';\n" for n in BASELINE_EXPORTS if not n.endswith("Props") and n not in ("isMaskedPlaceholder", "dispatchCommand"))
    head += "".join(f"export type {{ {n} }} from './x';\n" for n in BASELINE_EXPORTS if n.endswith("Props"))
    head += "export { isMaskedPlaceholder } from './M';\nexport { dispatchCommand } from './C';\n"
    assert index_problems(head + GOOD_INDEX_TAIL, check_prefix=False) == []
    assert index_problems(head, check_prefix=False), "没追加 RelativeTime 等应被抓住"
    assert index_problems(head + GOOD_INDEX_TAIL + "export * from './overlay/MountLayer';\n", check_prefix=False), "overlay 应被抓住"
    assert index_problems(head.replace("共五片", "共六片") + GOOD_INDEX_TAIL, check_prefix=False)
    assert index_problems(head.replace("export { Button } from './Button';\n", "") + GOOD_INDEX_TAIL, check_prefix=False), "丢了已有导出应被抓住"
    assert append_only_problems(f"{COMP_REL}/index.ts", "x" * 10), "比基线短应被抓住"


def test_gate_selfcheck_baseline_constants_match_the_baseline_commit():
    """索引文件与 shell-app.test.tsx 的基线常量对得上 6ec75f1 里的原文（仓库里没有这个提交时，退化成只验常量自身的形状）。"""
    for rel, (size, digest) in BASELINE_APPEND_ONLY.items():
        assert size > 0 and re.fullmatch(r"[0-9a-f]{64}", digest)
    proc = git("show", f"{BASE_SHA}:{WEB_REL}/tests/shell-app.test.tsx")
    if proc.returncode != 0:
        return
    base = _norm(proc.stdout.decode("utf-8"))
    for rel, (size, digest) in BASELINE_APPEND_ONLY.items():
        shown = git("show", f"{BASE_SHA}:{rel}")
        assert shown.returncode == 0, f"{rel} 在 {BASE_SHA[:7]} 里读不出来"
        data = _norm(shown.stdout.decode("utf-8")).encode("utf-8")
        assert (len(data), hashlib.sha256(data).hexdigest()) == (size, digest), f"{rel} 的基线常量与 {BASE_SHA[:7]} 不符"
    lines = base.split("\n")
    prefix = "\n".join(lines[:31]) + "\n"
    suffix = "\n".join(lines[37:])
    assert (len(prefix.encode()), hashlib.sha256(prefix.encode()).hexdigest()) == SHELL_APP_PREFIX
    assert (len(suffix.encode()), hashlib.sha256(suffix.encode()).hexdigest()) == SHELL_APP_SUFFIX
    assert lines[31].lstrip().startswith("it('总览占位显示夹具数据与条数'") and lines[36] == "  });"
    assert shell_app_problems(base), "基线原文（还是占位断言）应被判不通过"
    new_case = ("  it('总览页渲染真页面', async () => {\n    location.hash = '#/overview';\n    render(<App />);\n    await flush();\n"
                "    expect(document.querySelector('[data-page=\"overview\"]')).not.toBeNull();\n"
                "    expect(document.querySelectorAll('[data-metric]').length).toBe(4);\n  });")
    good = "\n".join(lines[:31] + new_case.split("\n") + lines[37:])
    assert shell_app_problems(good) == [], shell_app_problems(good)
    assert shell_app_problems(good.replace("expect(h1()).toBe('任务');", "expect(h1()).toBe('任务页');", 1)), "改了别的条应被抓住"
    assert shell_app_problems(good.replace("beforeEach(() => { location.hash = ''; });", "beforeEach(() => { location.hash = '#/x'; });")), "改了文件头应被抓住"
    assert shell_app_problems(good.replace("expect(document.querySelectorAll('[data-metric]').length).toBe(4);", "expect(document.body.textContent).toContain('夹具数据已读到');")), "仍断言占位文字应被抓住"
    assert shell_app_problems(good.replace("  it('总览页渲染真页面'", "  it.skip('总览页渲染真页面'")), "skip 应被抓住"
    assert shell_app_problems("\n".join(lines[:31] + lines[37:])), "把那一条删掉应被抓住"


def test_gate_selfcheck_executor_test_checker(tmp_path, monkeypatch):
    tests = tmp_path / "tests"
    tests.mkdir()
    monkeypatch.setitem(globals(), "WEB", tmp_path)
    assert len(executor_test_problems()) == len(EXECUTOR_TESTS), "文件都不在时每份记一条"
    for name in EXECUTOR_TESTS:
        (tests / name).write_text("import { it } from 'vitest';\nit('x', () => {});\n", encoding="utf-8")
    assert executor_test_problems() == []
    (tests / EXECUTOR_TESTS[0]).write_text("import { it } from 'vitest';\nit.skip('x', () => {});\n", encoding="utf-8")
    assert executor_test_problems()
    (tests / EXECUTOR_TESTS[0]).write_text("// 没有用例\n", encoding="utf-8")
    assert executor_test_problems()


def test_gate_selfcheck_vitest_json_helpers():
    sample = {"numTotalTestSuites": 2, "testResults": [
        {"status": "failed", "assertionResults": [
            {"ancestorTitles": ["D01 甲"], "title": "a", "status": "passed", "failureMessages": []},
            {"ancestorTitles": ["D01 甲"], "title": "b", "status": "failed", "failureMessages": ["boom"]},
            {"ancestorTitles": ["D02 乙", "内层"], "title": "c", "status": "skipped", "failureMessages": []}]},
        {"status": "failed", "message": "import error", "assertionResults": []}]}
    text = "> vitest run\n" + json.dumps(sample, ensure_ascii=False) + "\n"
    parsed = parse_vitest_json(text)
    assert parsed and parsed["numTotalTestSuites"] == 2
    groups, errors = summarize_vitest(parsed)
    assert groups["D01 甲"]["passed"] == 1 and len(groups["D01 甲"]["bad"]) == 1
    assert groups["D02 乙"]["bad"][0][1] == "skipped"
    assert errors == ["import error"]
    assert parse_vitest_json("no json here") is None


def node_strips_types(node, tmp_path):
    """node --check 查 .mts 要靠 Node 的类型剥离（Node 24 默认开）；先拿一行带类型标注的样本探测，不可用就不做语法检查，不让自检误红。"""
    sample = tmp_path / "typed-sample.mts"
    sample.write_text("const x: number = 1;\nexport { x };\n", encoding="utf-8")
    try:
        proc = subprocess.run([node, "--check", str(sample)], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def test_gate_selfcheck_probe_templates(tmp_path):
    """探针源码：每个 Python 用例点名的分组都存在且有用例；每个分组都有 Python 用例；node --check 查语法。"""
    here = Path(__file__).read_text(encoding="utf-8")
    named = re.findall(r'assert_probe_group\(pipeline, "(\w+)", "([^"]+)"\)', here)
    assert named, "没找到 assert_probe_group 调用"
    for key, group in named:
        groups = probe_groups(PROBE_SPECS[key][0])
        assert group in groups, f"探针 {key} 里没有分组「{group}」"
        assert groups[group] >= 1, f"探针 {key} 的分组「{group}」没有用例"
    for key in PROBE_ORDER:
        for group in probe_groups(PROBE_SPECS[key][0]):
            assert (key, group) in named, f"探针 {key} 的分组「{group}」没有对应的 Python 用例"
    assert set(PROBE_ORDER) == set(PROBE_SPECS)
    for key in PROBE_ORDER:
        source = build_probe_source(key)
        assert "__ICON_SHAPES__" not in source and "__DATA_FILE__" not in source
        assert not re.search(r"\.(skip|only|todo)\b|\bxit\(|\bxdescribe\(", source), f"探针 {key} 里不许 skip、only、todo"
        for word in NET_WORDS + SINK_WORDS:
            assert word not in source, f"探针 {key} 自己不该含禁用词 {word}"
    node = shutil.which("node")
    if node and node_strips_types(node, tmp_path):
        for key in PROBE_ORDER:
            path = tmp_path / f"probe-{key}.mts"
            path.write_text(build_probe_source(key), encoding="utf-8", newline="\n")
            proc = subprocess.run([node, "--check", str(path)], capture_output=True, timeout=60)
            assert proc.returncode == 0, f"探针 {key} 语法有误：\n{proc.stderr.decode('utf-8', 'replace')[-1500:]}"


def test_gate_selfcheck_constants():
    assert len(NEW_SOURCE_FILES) == len(set(NEW_SOURCE_FILES)) == 23
    assert COPY_TEXT_MODULE in ("../src/components/copyText", "../src/pages/readonly1/common-copyText")
    assert set(CSS_FILES.values()) <= set(NEW_SOURCE_FILES)
    assert set(PAGE_FILES) == {"overview", "roles", "runtimes"}
    assert len(EXECUTOR_TESTS) == 8
    assert set(TONE_TOKENS) == {"running", "review", "decide", "integrate"}
    assert STATE_CODES == tuple(dict.fromkeys(STATE_CODES))
    assert PIPELINE_BUDGET < 600, "合同 v2 V01 的超时是 600s，夹具预算要留余量给其余用例"
    assert max(STEP_CAPS.values()) <= PIPELINE_BUDGET
