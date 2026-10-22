"""T011 战前门禁：桌面端前端任务列表与 attempt 详情页（第十片）的黑盒基准测试（合同 t011-desktop-tasks，plan_version 1，基线 5d57833）。

被测对象是 ``desktop/web/``：任务页 ``src/pages/TasksPage.tsx`` 从占位换成真页面（左侧任务列表 + 右侧 attempt 详情，两页五态）、
新目录 ``src/pages/tasks/`` 下 20 个文件（tasks-/tab-/common- 前缀的纯函数、数据层、视图、样式与图标）、``src/mock/tasks-*.ts`` 三份夹具，
以及执行端 8 份 ``tests/tasks-*.test.ts(x)``。数据只读 api.ts 的 getStatus、getAttempt、readFile；缺的夹具经 tasks-data.ts 只读包装取
src/mock/tasks-*.ts。分组用 T009 的 attemptGroups.ts（ATTEMPT_GROUPS、groupOfState），跨视图跳转用 T009 的 useAppNavigate，
页内状态（页签、分组胶囊、选中任务）用 history.replaceState 同步地址。

基线（5d57833，T009 结项）上这些都还没有，所以本文件的“失败”断言落在目标文件不存在或内容不符上，不是导入、收集或语法错误：
模块级只导入标准库，用到被测文件的地方都在用例函数里读；候选里还没有 ``src/pages/tasks/`` 与 ``src/mock/tasks-*.ts`` 时，
``pipeline`` 夹具不跑 npm（没有东西可测，也省掉联网的 ``npm ci``），用到它的用例以断言失败写明原因。

结构（编号对应合同 DoD 的 D01–D14；门禁端另加若干静态守卫和自检）：

- 静态断言（不用流水线，全量 pytest 也跑）：合同 Scope 的文件都在位（tasks/ 下不多不少）、页面文件结构（PageFrame、默认导出、
  从 ./tasks/ 引入、不再有占位行）、src/mock 仍恰 14 份 JSON 与 src/pages 顶层仍恰 9 个 *Page.tsx、源码与夹具过 §1.3 的扫描
  （四个网络词、T007 禁用词、字体词、ServerIcon、role=status、四个禁用接口、W4 的十六进制与颜色函数）、没有内联 style、
  分组表与 UI 文档 3.4 逐个核对（17 个状态，PREPARED 与未知状态为 null）、新图标路径等于画布对应行、§8 的 CSS 取值、
  令牌与 px 注释、三份 CSS 都接进了应用、执行端 8 份测试在位且不用 skip、only、todo。
- 流水线断言（全量 pytest 默认跳过，点名运行本文件才跑）：会话级夹具 ``pipeline`` 在 ``desktop/web`` 下按顺序跑 ``npm ci``、
  ``npm run build``、``npm test``、``npm run check:contract``，再把探针逐份写成 ``gate-probe/probe-t011-<唯一标识>-<键>.test.ts``，
  各用 ``npm test -- gate-probe/<文件名> --reporter=json`` 跑，``finally`` 里删除；前后各取一次 ``git status``。探针不写 JSX
  （用 ``React.createElement``），这样门禁自检能用 ``node --check`` 先查语法。探针经 ``vi.mock('../src/api')`` 替换读函数注入数据，
  挂载整个 App、读页面 DOM 与地址；合同没写死的内部名字（视图属性、纯函数导出名）一律不碰，只认合同写定的 DOM 约定
  （data-page-state、aria-label、按钮文字、标签文字、.tt-* 类名、表格 aria-label）。
- 门禁自检（``test_gate_selfcheck_*``，不依赖候选）：把检查函数喂给正确样本和若干改坏的样本；探针源码查分组、语法与禁用词。

DoD 对应：D01 逻辑与地址（logic 探针）、D02 数据层（data 探针，直接调合同写定的 readAttempt/readAttemptFile/loadAttemptDetail）、
D03 列表视图（list 探针）、D04 任务页 App 级（app 探针，过渡）、D05/D06 详情页头与五态（detail 探针）、D07 页签与地址（tabs 探针）、
D08–D11 六个页签（tabs 探针）、D12 不可信内容与写入口（app 探针）、D13 样式与源码规则（静态断言 + 构建产物里的样式表）、
D14 回归与范围（npm 四步、执行端测试在位、流水线不改工作区；V02、V03 由合同另证）。改动范围由调度器的范围门禁证明，这里不写相对基线的范围断言。

过渡断言（``test_transitional_`` 开头，docstring 第一行写明哪项后续工作推翻它）：经 ``?mock=`` 渲染 App 两页的五态、由夹具得到的具体值
（6 个任务、胶囊计数 1/2/1/1/1、logs-cat 两行、5 个禁用入口、T009 四个指标卡地址下的任务列表与计数）、tasks-data 取本片夹具的那几条、
运行中 attempt 的跟随模拟。其余（分组与地址规则、列表与详情视图、页签同步、六个页签内容、不可信内容、写入口白名单、指标卡导航、
CSS 取值、源码扫描）是长期断言。

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
BASE_SHA = "5d578333f126825d777725eb865bae9c2ce04a50"
WEB_REL = "desktop/web"
WEB = REPO_ROOT / "desktop" / "web"
SRC_REL = f"{WEB_REL}/src"
SRC = WEB / "src"
TASKS_REL = f"{SRC_REL}/pages/tasks"
TASKS = SRC / "pages" / "tasks"
MOCK_REL = f"{SRC_REL}/mock"
PAGES_REL = f"{SRC_REL}/pages"
TESTS_REL = f"{WEB_REL}/tests"

ASSUMPTIONS = (
    "合同没写视图组件与纯函数的导出名：探针只经 App 挂载读 DOM 与地址；data 探针直接 import 的只有合同写定名字的 readAttempt、readAttemptFile、loadAttemptDetail",
    "tasks-groups.ts 的标签写法合同没定：按“分组 ID 作键、中文标签作值的对象字面量”解析（running: '运行中' 等），探针再在 DOM 上核对五颗胶囊的文字",
    "attempt 表 11 列的表头文字取合同列名（attempt、版本、状态、用时、检查、结论、失败分类、越界、token、费用、思考档位）",
    "时长按 8.8 的“38 秒 / 18 分 22 秒 / 1 小时 12 分”取整到秒（小时档只写到分）；字节按 8.8 的一位小数（512 B、17.9 KB、2.7 MB）；断言用子串，容忍 1 小时 2 分 5 秒 这类多写秒的写法",
    "本地时间（详情页状态时间）在探针里用同一个 Date 的 getFullYear…getMinutes 现算，不写死时区；title 是 UTC 原值",
    "越界大于 0 的 danger 类名执行端自定：门禁从本片 CSS 里解析出引用了 var(--tt-danger-text) 的类名，再要求单元格带上其中之一",
    "“检查表、文件表最小宽 560”合同合成一句：CSS 上只要求至少一条规则声明 min-width 560px（执行端可以用一条共享规则盖两张表）",
    "选中竖条合同写“左侧 2px --tt-primary 竖条”，没定写法：CSS 上接受 border-left/inline-start 2px solid var(--tt-primary) 或含 var(--tt-primary) 的 inset box-shadow",
    "?mock=empty 时 status 为空：合同 §3 写“logs-cat/attempt-002 仍有 logs show 照常显示，其他 attempt 进空态”，§5 又写 empty 下包装照样处理夹具；门禁只验 logs-cat/attempt-002 照常显示与夹具里都没有的 x/y 进空态，不断言 ui-readonly-api/attempt-001 在 empty 下的归属（两处措辞有歧义，交终审裁定）",
    "点行进详情时地址里受管参数的写法合同只举例“进详情写 ?tab=summary”：门禁只验解析后的视图、tab 与 mock，不断言 group 是否从详情地址里消失",
    "复制结果行合同没定挂在哪个元素下：探针只在页面文字里找「已复制」「复制失败」「这个环境没有剪贴板接口」",
)

# 合同 Scope 的新增源码（allowed_new_files 里的非测试文件）：src/pages/tasks/ 下 20 个，src/mock/ 下 3 个。
# T014（收尾二）把 tasks-copy.ts、tasks-icons.tsx、common-CopyNote.tsx 并进 src/components 与 src/icons/index.tsx、删掉这三份
# （站主按 T014 规划 Q1、Q3 选 A 退役）：下面的清单只列另外 17 个；这三份在 T014 合入之前还在，合入之后没有，两样都算对。
TASKS_MERGED = ("tasks-copy.ts", "tasks-icons.tsx", "common-CopyNote.tsx")
TASKS_FILES = (
    "tasks-groups.ts", "tasks-format.ts", "tasks-route.ts", "tasks-model.ts", "tasks-data.ts",
    "TaskListView.tsx", "tasks-list.css", "AttemptDetailView.tsx", "tasks-detail.css",
    "tab-Summary.tsx", "tab-Patch.tsx", "tab-Checks.tsx", "tab-Report.tsx", "tab-Events.tsx", "tab-Files.tsx",
    "tasks-tabs.css", "common-FileReader.tsx",
)
MOCK_FILES = ("tasks-files.ts", "tasks-attempts.ts", "tasks-live.ts")
NEW_SOURCE_FILES = tuple(f"{TASKS_REL}/{n}" for n in TASKS_FILES) + tuple(f"{MOCK_REL}/{n}" for n in MOCK_FILES)
PAGE_FILE = f"{PAGES_REL}/TasksPage.tsx"
CSS_FILES = {
    "list": f"{TASKS_REL}/tasks-list.css",
    "detail": f"{TASKS_REL}/tasks-detail.css",
    "tabs": f"{TASKS_REL}/tasks-tabs.css",
}
# 合同“执行端测试”：八份。
EXECUTOR_TESTS = ("tasks-logic.test.ts", "tasks-data.test.ts", "tasks-list.test.tsx", "tasks-detail.test.tsx",
                  "tasks-tabs.test.tsx", "tasks-app.test.tsx", "tasks-css.test.ts", "tasks-static.test.ts")
# 基线：src/mock/ 恰有 14 份 JSON、3 份 .ts；src/pages/ 顶层恰有 9 个 *Page.tsx。
BASELINE_JSON = ("attempt", "file-events", "file-executor-report", "history", "meta", "plugins", "preset-diff", "presets",
                 "profiles", "roles", "runtimes", "secrets", "status", "usage")
BASELINE_MOCK_TS = ("scenario.ts", "empty.ts", "shell.ts")
BASELINE_PAGES = ("OverviewPage.tsx", "TasksPage.tsx", "RolesPage.tsx", "RuntimesPage.tsx", "SecretsPage.tsx", "LogsPage.tsx",
                  "PluginsPage.tsx", "HistoryPage.tsx", "SettingsPage.tsx")
# 合同“公共约定”：静态检查禁用词（扫本片源码与夹具全文，含注释与字符串；网络词与注入词另对整个 src 扫）。
NET_WORDS = ("fetch", "XMLHttpRequest", "EventSource", "WebSocket")
SINK_WORDS = ("dangerouslySetInnerHTML", "innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function",
              "document.write", "srcdoc", "createContextualFragment", "DOMParser")
FONT_WORDS = ("@font-face", "FontFace", ".woff", ".ttf", ".otf", ".eot", "sarasa-mono-sc-")
FORBIDDEN_CALLS = ("matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver")
# 3.4 的 17 个状态码里进分组的 16 个（PREPARED 不在任何组）：用于识别“状态到分组的映射”，本片源码不另写这种映射。
GROUPED_STATE_CODES = ("PREPARING", "RUNNING", "COLLECTING", "NEEDS_REVIEW", "TIMEOUT", "CANCELLED", "INFRA_FAILURE",
                       "ESCALATE", "BLOCKED", "PASS", "ACCEPTED_WITH_EXCEPTION", "INTEGRATED", "REVISE", "ABANDONED",
                       "SUPERSEDED", "PREPARE_FAILED")
ALL_STATE_CODES = GROUPED_STATE_CODES + ("PREPARED",)
# 3.4 的分组中文名 → T009 的分组 ID（合同 §1 地址约定、§2 列表页）。
GROUP_LABELS = (("running", "运行中"), ("review", "待验收"), ("decide", "要你决定"), ("integrate", "待集成"), ("ended", "已结束"))
TAB_IDS = ("summary", "patch", "checks", "report", "events", "files")
TAB_LABELS = ("摘要", "补丁", "检查", "执行报告", "事件", "全部文件")

# 合同检查项 V01 的 timeout 是 600s：夹具总预算压在 570s 以内，用完就停下并在断言里写明，不等调度器来杀。
PIPELINE_BUDGET = 570
STEP_CAPS = {
    "npm ci": 200,
    "npm run build": 120,
    "npm test": 240,
    "npm run check:contract": 40,
    "probe": 90,
}


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

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


_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def tail_text(text, max_chars=3500, max_lines=45):
    text = _ANSI.sub("", text)
    lines = text.splitlines()[-max_lines:]
    return "\n".join(lines)[-max_chars:]


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


HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])")
COLOR_FUNC_RE = re.compile(r"\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(", re.I)


def w4_pitfall_problems(files):
    """W4 的坑（合同公共约定）：只剥块注释，字符串也扫；不出现井号加 3/4/6/8 位十六进制、颜色函数名加括号、拼接 --tt- 前缀。"""
    problems = []
    for path in files:
        text = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), _read(path), flags=re.S)
        label = label_of(path)
        for m in HEX_RE.finditer(text):
            problems.append(f"{label}:{text[:m.start()].count(chr(10)) + 1} 出现十六进制颜色形态 {m.group(0)}")
        for m in COLOR_FUNC_RE.finditer(text):
            problems.append(f"{label}:{text[:m.start()].count(chr(10)) + 1} 出现颜色函数形态 {m.group(0)}")
        for m in re.finditer(r"""[`'"][^`'"\n]*--tt-[^`'"\n]*\$\{""", text):
            problems.append(f"{label}:{text[:m.start()].count(chr(10)) + 1} 拼接了 --tt- 令牌名")
    return problems


# ---------------------------------------------------------------------------
# 合同 §8 的 CSS 取值（不依赖合同没定的类名：每条是“有一条规则同时声明了这几项”）
# ---------------------------------------------------------------------------

def tok(name):
    return f"var(--tt-{name})"


def bg(value):
    return C(("background", "background-color"), eq=value)


TABLE_WRAP = lambda selector: ".tt-table-wrap" in selector and selector.count(".") >= 2
CRUMB_SEL = r"crumb"

LIST_SPECS = [
    ("两栏：flex、间距 --tt-space-4、align-items flex-start", None,
     [C("display", eq="flex"), HasAll(("gap", "column-gap"), tok("space-4")), C("align-items", eq="flex-start")]),
    ("左栏：宽 320、不伸缩、surface-1、1px --tt-border、--tt-radius-lg", None,
     [C("width", eq="320px"), AnyOf(C("flex", eq="none"), C("flex", eq="0 0 auto")), bg(tok("surface-1")),
      C("border", eq="1px solid var(--tt-border)"), C("border-radius", eq=tok("radius-lg"))]),
    ("左栏头：纵向、间距 --tt-space-2、内边距 --tt-space-3", None,
     [C("display", eq="flex"), C("flex-direction", eq="column"), HasAll(("gap", "row-gap"), tok("space-2")),
      C("padding", eq=tok("space-3"))]),
    ("搜索框：高 32、内边距左 --tt-space-8 右 --tt-space-2、1px --tt-border-strong、--tt-radius-md、--tt-text-md", None,
     [C(("height", "min-height"), eq="32px"), sides_is("padding", left=tok("space-8"), right=tok("space-2")),
      C("border", eq="1px solid var(--tt-border-strong)"), C("border-radius", eq=tok("radius-md")),
      C("font", eq=tok("text-md"))]),
    ("胶囊：高 28、左右 --tt-space-2、--tt-radius-full、--tt-text-sm-medium", None,
     [C(("height", "min-height"), eq="28px"), sides_is("padding", left=tok("space-2"), right=tok("space-2")),
      C("border-radius", eq=tok("radius-full")), C("font", eq=tok("text-sm-medium"))]),
    ("胶囊按下：--tt-surface-selected 底、1px --tt-primary 边、--tt-text-1 字", r"aria-pressed",
     [bg(tok("surface-selected")), C("border", eq="1px solid var(--tt-primary)"), C("color", eq=tok("text-1"))]),
    ("胶囊平时：--tt-surface-1 底、1px --tt-border-strong 边、--tt-text-2 字", None,
     [bg(tok("surface-1")), C("border", eq="1px solid var(--tt-border-strong)"), C("color", eq=tok("text-2"))]),
    ("胶囊之间 gap --tt-space-1", None, [HasAll(("gap", "row-gap", "column-gap"), tok("space-1"))]),
    ("任务项：最小高 52、内边距 --tt-space-2 --tt-space-3、有下边框", None,
     [C(("min-height", "height"), eq="52px"),
      sides_is("padding", top=tok("space-2"), bottom=tok("space-2"), left=tok("space-3"), right=tok("space-3")),
      AnyOf(C("border-bottom", has=("1px",)), C("border-bottom-width", eq="1px"))]),
    ("任务项选中：--tt-surface-selected 底", r"selected", [bg(tok("surface-selected"))]),
    ("选中竖条：左侧 2px --tt-primary", None,
     [AnyOf(C(("border-left", "border-inline-start"), eq="2px solid var(--tt-primary)"),
            C("box-shadow", has=("inset", "var(--tt-primary)")))]),
    ("任务项悬停 --tt-surface-3", r":hover", [bg(tok("surface-3"))]),
    ("右栏头内边距 --tt-space-3 --tt-space-4", None,
     [sides_is("padding", top=tok("space-3"), bottom=tok("space-3"), left=tok("space-4"), right=tok("space-4"))]),
    ("attempt 表容器压过 .tt-table-wrap：无外框无圆角、只留上边框 1px --tt-border", TABLE_WRAP,
     [AnyOf(C("border", eq="0"), C("border", eq="none"), C("border-width", eq="0")), C("border-radius", zero=True),
      C("border-top", eq="1px solid var(--tt-border)")]),
    ("attempt 表最小宽 1040", None, [C("min-width", eq="1040px")]),
    ("下一步区外边距 --tt-space-4", None,
     [AnyOf(C("margin", eq=tok("space-4")),
            sides_is("margin", top=tok("space-4"), bottom=tok("space-4"), left=tok("space-4"), right=tok("space-4")))]),
]
DETAIL_SPECS = [
    ("面包屑条内边距 --tt-space-5 --tt-space-6 0", None,
     [sides_is("padding", top=tok("space-5"), left=tok("space-6"), right=tok("space-6"), bottom="0")]),
    ("窄内容区下面包屑内边距 --tt-space-4", CRUMB_SEL,
     [AnyOf(C("padding", eq=tok("space-4")),
            sides_is("padding", top=tok("space-4"), bottom=tok("space-4"), left=tok("space-4"), right=tok("space-4")))]),
    ("页头：可换行、间距 --tt-space-2", None,
     [C("display", eq="flex"), C("flex-wrap", eq="wrap"), HasAll(("gap", "row-gap", "column-gap"), tok("space-2"))]),
    ("dl：可换行、行距 --tt-space-0_5、列距 --tt-space-3", None,
     [C("flex-wrap", eq="wrap"), HasAll(("gap", "row-gap"), tok("space-0_5")), HasAll(("gap", "column-gap"), tok("space-3"))]),
    ("页签列表 overflow-x auto", None, [C("overflow-x", eq="auto")]),
    ("摘要：最大宽 880、内边距 --tt-space-5 --tt-space-6、surface-1、1px --tt-border、--tt-radius-lg", None,
     [C("max-width", eq="880px"),
      sides_is("padding", top=tok("space-5"), bottom=tok("space-5"), left=tok("space-6"), right=tok("space-6")),
      bg(tok("surface-1")), C("border", eq="1px solid var(--tt-border)"), C("border-radius", eq=tok("radius-lg"))]),
    ("检查表、文件表最小宽 560", None, [C("min-width", eq="560px")]),
]
GENERAL_SPECS = [
    ("至少一条规则给 flex 子项设 min-width: 0", None, [C("min-width", zero=True)]),
]
# 合同 §8 没规定哪条规则写在哪份文件：三份 CSS 合并成一个规则集后逐条求值（px 注释、令牌、W4 仍逐文件查）
ALL_SPECS = LIST_SPECS + DETAIL_SPECS + GENERAL_SPECS


def css_text(key):
    return _read(REPO_ROOT / CSS_FILES[key])


def css_value_problems():
    return group_problems("\n".join(css_text(key) for key in CSS_FILES), "tasks 的三份 CSS 合并", ALL_SPECS)


def bare_onefr_problems(css, label):
    """合同通用约定：宽于内容区的宽度只能出现在横向滚动的容器里；grid 里不写裸的 1fr（要 minmax(0, 1fr)）。"""
    problems = []
    for selector, decls in parse_rules(css):
        for name, value in decls:
            if name in ("grid-template-columns", "grid-auto-columns") and re.search(r"(?<![\w(])1fr", re.sub(r"minmax\([^)]*\)", "", cv(value))):
                problems.append(f"{label}：{selector} 的 {name} 出现裸的 1fr（应写 minmax(0, 1fr)）：{value}")
    return problems


def danger_classes(css):
    """本片 CSS 里引用了 var(--tt-danger-text) 的类名（越界大于 0 的单元格要带上其中之一）。"""
    out = set()
    for selector, decls in parse_rules(css):
        values = " ".join(v for _n, v in decls)
        if "var(--tt-danger-text)" in values:
            out |= set(re.findall(r"\.([A-Za-z_][\w-]*)", re.sub(r"\"[^\"]*\"|'[^']*'", "", selector)))
    return out


# ---------------------------------------------------------------------------
# 源码侧的检查函数
# ---------------------------------------------------------------------------

def word_hit(text, word):
    if word.startswith(".") or "(" in word or " " in word or "@" in word:
        return word in text
    return re.search(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])", text) is not None


def slice_code_files():
    """本片的 ts、tsx（tasks/ 全部 + src/mock/tasks-*.ts）。"""
    out = [REPO_ROOT / rel for rel in NEW_SOURCE_FILES if rel.endswith((".ts", ".tsx"))]
    return [p for p in out if p.is_file()]


def slice_css_files():
    return [REPO_ROOT / rel for rel in CSS_FILES.values() if (REPO_ROOT / rel).is_file()]


def src_ts_files():
    out = []
    for ext in ("ts", "tsx"):
        out += sorted(SRC.rglob(f"*.{ext}"))
    return out


def label_of(path):
    path = Path(path)
    try:
        return path.relative_to(WEB).as_posix()
    except ValueError:
        return path.name


def source_guard_problems(label, raw):
    """合同公共约定与 §1.3：禁用词（注释与字符串都算）、role=status、四个禁用接口、内联 style。"""
    problems = []
    for word in NET_WORDS + SINK_WORDS + FONT_WORDS:
        if word_hit(raw, word):
            problems.append(f"{label} 出现禁用词 {word}")
    if word_hit(raw, "ServerIcon"):
        problems.append(f"{label} 出现 ServerIcon")
    code = strip_ts_comments(raw)
    if re.search(r"""role\s*[=:]\s*\{?\s*["']status["']""", code):
        problems.append(f"{label}：不能渲染 role=status")
    for name in FORBIDDEN_CALLS:
        if re.search(rf"\b{name}\b", code):
            problems.append(f"{label}：不能用 {name}")
    if re.search(r"""\bstyle\s*=\s*(?:\{|["'])""", code):
        problems.append(f"{label}：不写内联 style")
    return problems


# 状态到分组的映射只查两种“映射”写法：group 键→状态数组（attemptGroups 的 GROUP_OF_STATE 原样）
# 与状态键→group 值（反向）。合同 §3 的下一步规则必须写 state==='REVISE'（REVISE 与 ended 组其它状态
# 只能靠状态码区分，不能靠 groupOfState），§5 的夹具必须写 state:'RUNNING'；这些单值比较与数据值都放行。
_GROUP_IDS = tuple(g for g, _ in GROUP_LABELS)
_STATE_TO_GROUP_MAP = re.compile(
    r"\b(?:" + "|".join(ALL_STATE_CODES) + r")\s*:\s*[\"'`](?:" + "|".join(_GROUP_IDS) + r")[\"'`]")
_GROUP_TO_STATES_MAP = re.compile(
    r"\b(?:" + "|".join(_GROUP_IDS) + r")\s*:\s*\[\s*[\"'`][A-Z][A-Z_]*[\"'`]")


def state_literal_problems(files):
    """合同 §1：分组只来自 attemptGroups，本片源码不另写状态到分组的映射。
    只查映射结构（group 键→状态数组，或状态键→group 值），不拦单值比较与数据值：下一步规则可写
    state==='REVISE'（合同 §3：REVISE 不能用 groupOfState 与 ended 组区分），夹具可写 state:'RUNNING'（§5）。"""
    problems = []
    for path in files:
        code = strip_ts_comments(_read(path))
        label = label_of(path)
        if _GROUP_TO_STATES_MAP.search(code):
            problems.append(f"{label}：自己写了状态到分组的映射（group→状态数组，分组只来自 attemptGroups）")
        if _STATE_TO_GROUP_MAP.search(code):
            problems.append(f"{label}：自己写了状态到分组的映射（状态→group，分组只来自 attemptGroups）")
    return problems


# ---- 分组表与 UI 文档 3.4（合同 D01、§5.5 S5） ----

def ui_doc_states_and_groups():
    """从 UI 文档 3.4 解析 17 个状态码与五组的状态清单（门禁自己解析，不写死）。"""
    text = _read(REPO_ROOT / "docs" / "themis-tally-3.0-桌面端-UI设计.md")
    start = text.index("### 3.4")
    end = text.index("### 3.5", start)
    section = text[start:end]
    states = re.findall(r"^\|\s*`([A-Z_]+)`\s*\|", section, re.M)
    groups = {}
    for m in re.finditer(r"^\|\s*(运行中|待验收|要你决定|待集成|已结束)\s*\|([^|]*)\|", section, re.M):
        groups[m.group(1)] = [c for c in re.findall(r"[A-Z][A-Z_]+", m.group(2)) if c in states]
    return states, groups


def attempt_groups_code():
    return strip_ts_comments(_read(need_file(f"{SRC_REL}/shell/attemptGroups.ts")))


def attempt_groups_problems():
    """T009 的 attemptGroups.ts：GROUP_OF_STATE 与 UI 文档 3.4 逐个状态相同；PREPARED 与未知状态不在任何组。"""
    problems = []
    states, doc_groups = ui_doc_states_and_groups()
    if len(states) != 17:
        problems.append(f"UI 文档 3.4 应解析出 17 个状态码，实际 {len(states)}：{states}")
    if len(doc_groups) != 5:
        problems.append(f"UI 文档 3.4 应解析出 5 个分组，实际 {sorted(doc_groups)}")
    code = attempt_groups_code()
    m = re.search(r"GROUP_OF_STATE[^=]*=\s*\{(.*?)\n\};", code, re.S)
    if not m:
        problems.append("attemptGroups.ts 里找不到 GROUP_OF_STATE 映射表")
        return problems
    got = {}
    for gm in re.finditer(r"(\w+)\s*:\s*\[([^\]]*)\]", m.group(1)):
        got[gm.group(1)] = re.findall(r"'([^']+)'", gm.group(2))
    want = {}
    for group, label in GROUP_LABELS:
        want[group] = doc_groups.get(label, [])
    if got != want:
        problems.append(f"GROUP_OF_STATE 与 UI 文档 3.4 不一致：文档 {want}，代码 {got}")
    flat = [s for codes in got.values() for s in codes]
    if len(flat) != len(set(flat)):
        problems.append(f"有状态码出现在多个分组里：{flat}")
    for state in states:
        if state not in flat and state != "PREPARED":
            problems.append(f"3.4 的状态 {state} 不在任何分组里（应只在 PREPARED 之外都进组）")
    if "PREPARED" in flat:
        problems.append("PREPARED 不应进任何分组（3.4 没有它）")
    return problems


def tasks_groups_problems():
    """本片 tasks-groups.ts：只加五组中文标签，ID、顺序与状态到分组都从 attemptGroups 导入，不另写映射。"""
    problems = []
    code = strip_ts_comments(_read(need_file(f"{TASKS_REL}/tasks-groups.ts")))
    labels = dict(re.findall(r"\b(running|review|decide|integrate|ended)\s*:\s*['\"]([^'\"]+)['\"]", code))
    for group, want in GROUP_LABELS:
        if labels.get(group) != want:
            problems.append(f"tasks-groups.ts 里 {group} 的标签应是「{want}」，实际 {labels.get(group)!r}")
    if not re.search(r"from\s+['\"][^'\"]*shell/attemptGroups['\"]", code):
        problems.append("tasks-groups.ts 应从 shell/attemptGroups 导入（分组不另起）")
    for name in ("ATTEMPT_GROUPS", "groupOfState"):
        if not re.search(rf"\b{name}\b", code):
            problems.append(f"tasks-groups.ts 应导入 {name}")
    if re.search(r"export\s+(?:function|const)\s+groupOfState\b", code):
        problems.append("tasks-groups.ts 不许自己定义 groupOfState（分组只来自 attemptGroups）")
    if re.search(r"Record\s*<\s*AttemptGroup", code) and "GROUP_OF_STATE" in code:
        problems.append("tasks-groups.ts 看起来自己写了状态到分组的映射")
    return problems


# ---- 新图标与画布（合同 §5.5 S6、K17） ----

def canvas_svg(rel, anchor):
    """画布文件里 anchor 之前最后一个 <svg>…</svg>：路径 d 的有序列表与 circle 属性列表。"""
    html = _read(REPO_ROOT / rel)
    i = html.index(anchor)
    j = html[:i].rfind("<svg")
    assert j >= 0, f"{rel} 里 {anchor} 之前找不到 <svg>"
    k = html.index("</svg>", j)
    block = html[j:k]
    paths = re.findall(r"<path\b[^>]*?\bd=\"([^\"]+)\"", block)
    circles = [dict(re.findall(r"([\w-]+)=\"([^\"]*)\"", c)) for c in re.findall(r"<circle\b([^>]*)>", block)]
    return paths, circles


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


def icon_shape_problems(block, name, want_paths, want_circles, label):
    problems = []
    if "<Svg" not in block:
        problems.append(f"{label}：{name} 应沿用 Svg 包装")
    paths = [tag_attrs(p).get("d") for p in re.findall(r"<path\b([^>]*)>", block)]
    if paths != want_paths:
        problems.append(f"{label}：{name} 的 path d 应依次为 {want_paths}，实际 {paths}")
    circles = [tag_attrs(c) for c in re.findall(r"<circle\b([^>]*)>", block)]
    if circles != want_circles:
        problems.append(f"{label}：{name} 的 circle 应依次为 {want_circles}，实际 {circles}")
    for attr in re.findall(r"\b(?:fill|stroke)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|\{[^}]*\})", block):
        value = attr[0] or attr[1]
        if value not in ("none", "currentColor"):
            problems.append(f"{label}：{name} 的 fill/stroke 只许 none 或 currentColor，实际 {value!r}")
    return problems


def icons_problems():
    """FileTextIcon 写在本片 tasks-icons.tsx（T014 之后在 src/icons/index.tsx），路径等于详情页画布对应行；SearchIcon 用 T009 的导出（K17 的主路径），本片不重写。"""
    problems = []
    task_canvas = "docs/ui-design/pages/05-任务-Themis-Tally.html"
    detail_canvas = "docs/ui-design/pages/05-attempt-详情-Themis-Tally.html"
    search_paths, search_circles = canvas_svg(task_canvas, 'placeholder="搜索任务…"')
    file_paths, file_circles = canvas_svg(detail_canvas, ">summary.md</span>")
    if not search_paths or not search_circles:
        problems.append(f"任务页画布里没有解析到搜索图标的 circle/path：{search_circles} {search_paths}")
    if not file_paths:
        problems.append(f"详情页画布里没有解析到文件图标的 path：{file_paths}")

    shared = strip_ts_comments(_read(need_file(f"{SRC_REL}/icons/index.tsx")))
    # T014 把 FileTextIcon 并进 src/icons/index.tsx、删掉 tasks-icons.tsx（站主按 T014 规划 Q3 退役）：共用件里有就查那一份
    if icon_block(shared, "FileTextIcon") is not None:
        icons_label, icons_text = "icons/index.tsx", shared
    else:
        icons_label, icons_text = "tasks-icons.tsx", _read(need_file(f"{TASKS_REL}/tasks-icons.tsx"))
        if re.search(r"export\s+(?:const|function)\s+SearchIcon\b", icons_text):
            problems.append("tasks-icons.tsx 不应自己写 SearchIcon：src/icons/index.tsx 已有该导出（K17 主路径），本片直接导入")
    block = icon_block(icons_text, "FileTextIcon")
    if block is None:
        problems.append(f"{icons_label} 没有 export const FileTextIcon")
    else:
        problems += icon_shape_problems(block, "FileTextIcon", file_paths, file_circles, icons_label)

    sblock = icon_block(shared, "SearchIcon")
    if sblock is None:
        problems.append("src/icons/index.tsx 没有 export const SearchIcon（T009 的导出）")
    else:
        problems += icon_shape_problems(sblock, "SearchIcon", search_paths, search_circles, "icons/index.tsx")

    list_view = _read(need_file(f"{TASKS_REL}/TaskListView.tsx"))
    if not re.search(r"import\s*\{[^}]*\bSearchIcon\b[^}]*\}\s*from\s*['\"][^'\"]*icons['\"]", strip_ts_comments(list_view)):
        problems.append("TaskListView.tsx 应从 icons 导入 SearchIcon（src/icons/index.tsx 的导出）")
    return problems


# ---- 执行端测试 ----

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
        for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
            if re.search(bad, text):
                problems.append(f"{name} 里出现 {bad}（不许 skip、only、todo）")
    return problems


# ---- 样式表接线（合同 §5.5：读 CSS 文本还要证明它接进了产品） ----

IMPORT_RE = re.compile(r"""\bimport\s+(?P<head>[^;]*?)\s+from\s+(?P<from>['"](?P<spec>[^'"]+)['"])"""
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
            specs.append(m.group("spec"))
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


def src_files_by_rel():
    files = {}
    for path in sorted(SRC.rglob("*")):
        if path.suffix in (".ts", ".tsx", ".css") and path.is_file():
            files[path.relative_to(REPO_ROOT).as_posix()] = _read(path)
    return files


def css_wiring_problems(files, css_rels, entry=f"{SRC_REL}/main.tsx"):
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


# ---------------------------------------------------------------------------
# 探针（Vitest + jsdom）：每份若干 describe，名字以 D 编号 / P 编号 / TRANS 开头，Python 用例按名字分组核对。
# 不写 JSX（React.createElement），探针源码是纯 TS，门禁自检用 node --check 查语法。
# ---------------------------------------------------------------------------

PRELUDE = r"""
import * as React from 'react';
import * as fs from 'node:fs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

const h: any = React.createElement;

// 循环里多次挂载 App 的用例慢于 Vitest 默认的 5 秒；下面几条再各自写显式超时
vi.setConfig({ testTimeout: 60000 });

// 排空 jsdom 里待决的导航与 hashchange（它们在宏任务里触发），使用例之间不互相泄漏
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
    // 没有定义过就算了
  }
  await drainNav();
});
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) {
      await Promise.resolve();
    }
  });
}
function advance(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}
function textOf(el: any): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function squash(s: any): string {
  return String(s || '').replace(/\s+/g, '');
}
function qa(rootEl: any, sel: string): any[] {
  return Array.from((rootEl || document).querySelectorAll(sel));
}
function btn(rootEl: any, label: string): any {
  return qa(rootEl, 'button').filter((b) => textOf(b) === label)[0] || null;
}
function hashParts(): { path: string; params: Record<string, string>; multi: Array<[string, string]>; raw: string } {
  const raw = window.location.hash.replace(/^#/, '');
  const q = raw.indexOf('?');
  const search = q < 0 ? '' : raw.slice(q + 1);
  const params: Record<string, string> = {};
  const multi: Array<[string, string]> = [];
  new URLSearchParams(search).forEach((v, k) => {
    params[k] = v;
    multi.push([k, v]);
  });
  return { path: q < 0 ? raw : raw.slice(0, q), params, multi, raw };
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  const App: any = (await import('../src/App')).default;
  const r = render(h(App));
  await settle();
  return r;
}
function frame(): any {
  return document.querySelector('[data-page-state]');
}
function pageText(): string {
  return textOf(frame() || document.body);
}
function h1El(): any {
  return document.querySelector('h1');
}
function localTime(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, '0');
  return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
}
function stubClipboard(impl: any) {
  Object.defineProperty(window.navigator, 'clipboard', { value: impl, configurable: true });
}
// 点击后由本门禁自己取消默认行为：返回「应用自己有没有 preventDefault」
function clickKeepUrl(el: any, init: any = {}): boolean {
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
function tabs(): any[] {
  return qa(document, '[role="tab"]');
}
function tabByLabel(label: string): any {
  return tabs().filter((t) => textOf(t) === label)[0] || null;
}
function selectedTabLabel(): string {
  const t = tabs().filter((x) => x.getAttribute('aria-selected') === 'true')[0];
  return t ? textOf(t) : '';
}
function panel(): any {
  return document.querySelector('[role="tabpanel"]');
}
function options(): any[] {
  return qa(document, 'li[role="option"]');
}
// 任务选项第一行是 task_id（第二行是最新 attempt 段）：取第一行的文字
function optionTask(el: any): string {
  return textOf(el).replace(/\s+attempt-[\s\S]*$/, '').trim();
}
function mainRoot(): any {
  return document.querySelector('main') || document.body;
}
function capsules(): any[] {
  const g = qa(document, '[role="group"][aria-label="按状态分组筛选"]');
  return g.length ? qa(g[0], 'button') : [];
}
function capsuleByGroup(group: string): any {
  return capsules().filter((b) => b.getAttribute('data-group') === group)[0] || null;
}
// 按下的分组胶囊：每份探针都要用，所以定义在前言里（探针之间不共享作用域，T011 返工：pressedGroups 原先只在
// PROBE_LOGIC 里定义，PROBE_APP 直接调用报 ReferenceError）。
function pressedGroups(): string[] {
  return capsules().filter((b) => b.getAttribute('aria-pressed') === 'true').map((b) => b.getAttribute('data-group'));
}
// 属性选择器匹配不了含 <、> 的取值（jsdom 实测：aria-label 是「<script>alert(1)</script> 的 attempt」时
// table[aria-label="…"] 返回 null，「logs-cat 的 attempt」能找到），所以改成遍历 table 比较属性值。
function attemptTable(task: string): any {
  const want = task + ' 的 attempt';
  return qa(document, 'table').filter((t) => t.getAttribute('aria-label') === want)[0] || null;
}
function tableRows(table: any): any[] {
  return qa(table, 'tbody tr');
}
function cellsOf(row: any): any[] {
  return qa(row, 'td');
}
function headersOf(table: any): string[] {
  return qa(table, 'thead th').map(textOf);
}
function cellText(table: any, rowIndex: number, header: string): string {
  const heads = headersOf(table);
  const at = heads.indexOf(header);
  expect(at, '表头里没有「' + header + '」：' + heads.join('、')).toBeGreaterThanOrEqual(0);
  return textOf(cellsOf(tableRows(table)[rowIndex])[at]);
}
"""

# 替换 api.ts 读函数的替身：默认转调原函数，用例用 set() 换成任意信封、出错、挂起或受控的延迟
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
"""

# 列表与逻辑探针共用的数据：8 个任务、10 行 status，覆盖 11 列的取值与五组计数（1/2/1/1/2，PREPARED 不进组）
TASKS_DATA = r"""
function rowOf(over: any): any {
  return Object.assign({
    attempt: 't/attempt-001', task_id: 't', plan_version: 1, attempt_no: 1, state: 'RUNNING', started: true,
    exit_code: null, wall_seconds: null, events_ok: true, violations: null, checks: '-', check_mode: null,
    verdict: null, failure_class: null, human_minutes: null, tokens: null, cost: null, cost_status: 'unknown',
  }, over);
}
function logicRows(): any[] {
  const alphaOld = rowOf({ attempt: 'alpha/attempt-001', task_id: 'alpha', attempt_no: 1, state: 'RUNNING',
    checks: '-', live: { tool_calls: 37, elapsed_seconds: 1146, deltas_since_last_tool: 6420, long_idle: true },
    cost: '12.5' });
  delete alphaOld.plan_version;
  return [
    rowOf({ attempt: 'alpha/attempt-003', task_id: 'alpha', plan_version: 2, attempt_no: 3, state: 'NEEDS_REVIEW',
      wall_seconds: 1719.4, checks: '8/8', check_mode: 'fresh', violations: 0, tokens: 4210385,
      effort_requested: 'max', effort_effective: 'high' }),
    rowOf({ attempt: 'alpha/attempt-002', task_id: 'alpha', plan_version: 1, attempt_no: 2, state: 'REVISE',
      wall_seconds: 1102.4, checks: '6/8', check_mode: 'fresh', verdict: 'REVISE', failure_class: 'EXECUTION_ERROR',
      violations: 0, tokens: 5637968 }),
    alphaOld,
    rowOf({ attempt: 'beta/attempt-001', task_id: 'beta', plan_version: 3, attempt_no: 1, state: 'PASS',
      wall_seconds: 954.0, checks: '5/5', check_mode: 'fresh', verdict: 'PASS', violations: 2, tokens: 2981204 }),
    rowOf({ attempt: 'can a/attempt-001', task_id: 'can a', attempt_no: 1, state: 'CANCELLED', wall_seconds: 59.9 }),
    rowOf({ attempt: 'run me/attempt-001', task_id: 'run me', attempt_no: 1, state: 'RUNNING',
      live: { tool_calls: 1, elapsed_seconds: 60 } }),
    rowOf({ attempt: 'z-last/attempt-001', task_id: 'z-last', attempt_no: 1, state: 'ESCALATE', checks: '3/4',
      check_mode: 'fresh', verdict: 'ESCALATE', failure_class: 'REQUIREMENT_BLOCKED', tokens: 1504288 }),
    rowOf({ attempt: 'redo/attempt-001', task_id: 'redo', attempt_no: 1, state: 'REVISE', wall_seconds: 100 }),
    rowOf({ attempt: 'gone/attempt-001', task_id: 'gone', attempt_no: 1, state: 'INTEGRATED', wall_seconds: 3725,
      tokens: 2981204 }),
    rowOf({ attempt: 'prep only/attempt-001', task_id: 'prep only', attempt_no: 1, state: 'PREPARED' }),
  ];
}
function setLogic() {
  set('getStatus', env(logicRows(), ['status']));
}
function logsCatRow(over: any = {}): any {
  return rowOf(Object.assign({ attempt: 'logs-cat/attempt-002', task_id: 'logs-cat', plan_version: 2, attempt_no: 2,
    state: 'NEEDS_REVIEW', wall_seconds: 1719.4, events_ok: true, violations: 0, checks: '8/8', check_mode: 'fresh',
    verdict: null, failure_class: null, human_minutes: 0.0, tokens: 4210385, cost: null, cost_status: 'unknown',
    effort_requested: 'max', effort_effective: 'high', exit_code: 0 }, over));
}
function attemptEnv(over: any = {}): any {
  return env(Object.assign({
    task: 'logs-cat', attempt: 'attempt-002', state: 'NEEDS_REVIEW', state_at: '2026-10-18T06:21:40Z',
    summary: { bytes: 512, truncated: false, text: '# logs-cat.v2 / attempt-002\n\n<img src=x onerror=alert(1)> 探针\n' },
    evidence: [{ path: 'summary.md', bytes: 512 }, { path: 'candidate.patch', bytes: 18342 },
      { path: 'events.jsonl', bytes: 2841107 }, { path: 'executor-report.md', bytes: 3920 },
      { path: 'checks/01/V01.log', bytes: 1844 }],
    skipped_links: 0,
  }, over), ['logs', 'show', 'logs-cat/attempt-002']);
}
"""

# ---- logic：D01 分组、地址与选中（长期） ----
PROBE_LOGIC = PRELUDE + API_MOCK + TASKS_DATA + r"""
function setDetail() {
  set('getStatus', env([logsCatRow()], ['status']));
  set('getAttempt', attemptEnv());
}
function optionLabels(): string[] {
  return options().map(optionTask);
}

describe('D01 分组与地址', () => {
  it('五颗胶囊：顺序与 data-group 取 ATTEMPT_GROUPS，文字是五组中文名，初值都不按下', async () => {
    setLogic();
    await mountApp('#/tasks');
    const want = [['running', '运行中'], ['review', '待验收'], ['decide', '要你决定'], ['integrate', '待集成'], ['ended', '已结束']];
    const got = capsules().map((b) => [b.getAttribute('data-group'), textOf(b).replace(/\d+$/, '').trim()]);
    expect(got).toEqual(want);
    capsules().forEach((b) => expect(b.getAttribute('aria-pressed'), textOf(b)).toBe('false'));
  });

  it('PREPARED 的任务不进任何组：没有按下胶囊时在列表里，按下任一胶囊就消失', async () => {
    setLogic();
    await mountApp('#/tasks');
    expect(optionLabels().some((t) => t.indexOf('prep only') >= 0)).toBe(true);
    fireEvent.click(capsuleByGroup('running'));
    await settle();
    expect(pressedGroups()).toEqual(['running']);
    expect(optionLabels().some((t) => t.indexOf('prep only') >= 0)).toBe(false);
    expect(optionLabels()).toEqual(['run me']);
  });

  it('点胶囊：aria-pressed 切换、只改受管的 group 参数（mock 与其他参数保留）、不加历史项、页面不重挂载', async () => {
    setLogic();
    await mountApp('#/tasks?mock=offline&keep=1');
    const h1Before = h1El();
    const len = window.history.length;
    fireEvent.click(capsuleByGroup('review'));
    await settle();
    expect(pressedGroups()).toEqual(['review']);
    const p = hashParts();
    expect(p.path).toBe('/tasks');
    expect(p.params).toEqual({ mock: 'offline', keep: '1', group: 'review' });
    expect((p.raw.match(/group=/g) || []).length, 'group 只出现一次：' + p.raw).toBe(1);
    expect(window.history.length, 'replaceState 不加历史项').toBe(len);
    expect(h1El(), '页内改地址不重挂载').toBe(h1Before);
    fireEvent.click(capsuleByGroup('review'));
    await settle();
    expect(pressedGroups()).toEqual([]);
    const p2 = hashParts();
    expect(p2.params).toEqual({ mock: 'offline', keep: '1' });
    expect(p2.raw.indexOf('group')).toBe(-1);
  });

  it('group 多值：逗号分隔按 ATTEMPT_GROUPS 的顺序写，读时两颗都按下', async () => {
    setLogic();
    await mountApp('#/tasks?group=review,ended&mock=data');
    expect(pressedGroups()).toEqual(['review', 'ended']);
    expect(optionLabels().slice().sort()).toEqual(['alpha', 'can a', 'gone', 'redo']);
  });

  it('重复的 group 参数取并集；认不出的 ID 忽略；都不按时不过滤', async () => {
    setLogic();
    await mountApp('#/tasks?group=review&group=decide');
    expect(pressedGroups()).toEqual(['review', 'decide']);
    cleanup();
    await mountApp('#/tasks?group=zzz&mock=data');
    expect(pressedGroups()).toEqual([]);
    expect(options().length).toBe(8);
  });

  it('计数按每个任务的最新 attempt，不受搜索与选中的影响', async () => {
    setLogic();
    await mountApp('#/tasks');
    const counts = capsules().map((b) => textOf(b).replace(/[^\d]/g, ''));
    expect(counts).toEqual(['1', '2', '1', '1', '2']);
    const search = qa(document, 'input[type="search"]')[0];
    fireEvent.change(search, { target: { value: 'alpha' } });
    await settle();
    fireEvent.click(options()[0]);
    await settle();
    expect(capsules().map((b) => textOf(b).replace(/[^\d]/g, ''))).toEqual(['1', '2', '1', '1', '2']);
  });

  it('地址里的任务经编码；不在筛选结果里时选筛选结果的第一个且不改写地址', async () => {
    setLogic();
    await mountApp('#/tasks/can%20a');
    const sel = options().filter((o) => o.getAttribute('aria-selected') === 'true');
    expect(sel.length).toBe(1);
    expect(optionTask(sel[0])).toBe('can a');
    cleanup();
    await mountApp('#/tasks?group=running&mock=data');
    window.location.hash = '#/tasks/zzz-not-here?group=running&mock=data';
    fireEvent(window, new HashChangeEvent('hashchange'));
    await settle();
    expect(textOf(options().filter((o) => o.getAttribute('aria-selected') === 'true')[0]).indexOf('run me')).toBe(0);
    expect(window.location.hash, '不改写地址').toBe('#/tasks/zzz-not-here?group=running&mock=data');
  });

  it('tab 的解析：六个取值各自选中，缺省与认不出都是摘要', async () => {
    setDetail();
    const want: Record<string, string> = { summary: '摘要', patch: '补丁', checks: '检查', report: '执行报告',
      events: '事件', files: '全部文件' };
    for (const id of Object.keys(want)) {
      cleanup();
      await mountApp('#/tasks/logs-cat/attempt-002?tab=' + id);
      expect(selectedTabLabel(), 'tab=' + id).toBe(want[id]);
    }
    cleanup();
    await mountApp('#/tasks/logs-cat/attempt-002');
    expect(selectedTabLabel()).toBe('摘要');
    cleanup();
    await mountApp('#/tasks/logs-cat/attempt-002?tab=zzz');
    expect(selectedTabLabel(), '认不出的 tab 回落摘要').toBe('摘要');
  });

  it('详情路径多于两段时只取前两段', async () => {
    setDetail();
    await mountApp('#/tasks/logs-cat/attempt-002/extra/more?mock=data');
    expect(textOf(h1El())).toBe('logs-cat · attempt-002');
  });

  it('点行进详情：受管参数写成缺省值，mock 保留，页签是 summary', async () => {
    setLogic();
    await mountApp('#/tasks?group=review&mock=data');
    const table = attemptTable('alpha');
    expect(table, '右栏 attempt 表').not.toBeNull();
    fireEvent.click(tableRows(table)[0]);
    await settle();
    const p = hashParts();
    expect(p.path).toBe('/tasks/alpha/attempt-003');
    expect(p.params.mock).toBe('data');
    expect(p.params.tab).toBe('summary');
    expect(textOf(h1El())).toBe('alpha · attempt-003');
  });
});

describe('D01 选中与筛选', () => {
  it('左栏选中写进地址（replace）：只改路径段，mock 与其他参数保留，不加历史项', async () => {
    setLogic();
    await mountApp('#/tasks?mock=offline&keep=1');
    const len = window.history.length;
    fireEvent.click(options()[2]);
    await settle();
    const p = hashParts();
    expect(p.path).toBe('/tasks/can a'.replace(' ', '%20'));
    expect(p.params).toEqual({ mock: 'offline', keep: '1' });
    expect(window.history.length).toBe(len);
    const sel = options().filter((o) => o.getAttribute('aria-selected') === 'true');
    expect(optionTask(sel[0])).toBe('can a');
  });

  it('跨视图链接只带 mock：点面包屑回列表不过滤，点任务项回到选中任务', async () => {
    setDetail();
    await mountApp('#/tasks/logs-cat/attempt-002?mock=offline&keep=1');
    const crumb = qa(document, 'nav[aria-label="面包屑"] a');
    const taskLink = crumb.filter((a) => textOf(a) === 'logs-cat')[0];
    expect(taskLink.getAttribute('href'), '面包屑第二项只带 mock').toBe('#/tasks/logs-cat?mock=offline');
    const prevented = clickKeepUrl(taskLink);
    expect(prevented, '无修饰键左键应被应用拦下').toBe(true);
    await settle();
    let p = hashParts();
    expect(p.path).toBe('/tasks/logs-cat');
    expect(p.params).toEqual({ mock: 'offline', keep: '1' });
    expect(pressedGroups()).toEqual([]);
    expect(options().length).toBe(1);
    const back = qa(document, 'nav[aria-label="面包屑"] a').filter((a) => textOf(a) === '任务')[0];
    expect(back.getAttribute('href')).toBe('#/tasks?mock=offline');
    expect(clickKeepUrl(back)).toBe(true);
    await settle();
    p = hashParts();
    expect(p.path).toBe('/tasks');
    expect(p.params).toEqual({ mock: 'offline', keep: '1' });
  });

  it('带修饰键点面包屑走默认行为，不被应用拦下', async () => {
    setDetail();
    await mountApp('#/tasks/logs-cat/attempt-002?mock=data');
    const taskLink = qa(document, 'nav[aria-label="面包屑"] a').filter((a) => textOf(a) === 'logs-cat')[0];
    expect(clickKeepUrl(taskLink, { metaKey: true })).toBe(false);
    await settle();
  });
});
"""

# ---- list：D03 列表视图（长期） ----
PROBE_LIST = PRELUDE + API_MOCK + TASKS_DATA + r"""
const COLUMN_HEADERS = ['attempt', '版本', '状态', '用时', '检查', '结论', '失败分类', '越界', 'token', '费用', '思考档位'];

describe('D03 列表视图', () => {
  it('页面框架：h1 与说明、load 就是 getStatus、空态沿用 T006 的文字', async () => {
    setLogic();
    await mountApp('#/tasks');
    expect(textOf(h1El())).toBe('任务');
    expect(pageText()).toContain('每个任务由多个版本的合同组成，每个版本可以有多个 attempt');
    expect((hoisted.spies.getStatus as any).mock.calls.length).toBeGreaterThan(0);
    cleanup();
    set('getStatus', env([], ['status']));
    await mountApp('#/tasks');
    expect(frame().getAttribute('data-page-state')).toBe('empty');
    expect(pageText()).toContain('还没有 attempt');
    expect(pageText()).toContain('在规划端用 /dispatch-pi 派遣第一个任务');
    expect(document.querySelector('[data-page]'), '空态没有视图').toBeNull();
  });

  it('两栏与搜索框：左栏 section、右栏 section、input type=search、视觉隐藏的标签、占位、左侧 SearchIcon 16', async () => {
    setLogic();
    await mountApp('#/tasks');
    const left = qa(document, 'section[aria-label="任务列表"]');
    expect(left.length, '左栏 section aria-label').toBe(1);
    const sections = qa(frame(), 'section');
    expect(sections.length).toBe(2);
    const input = qa(document, 'input[type="search"]')[0];
    expect(input, '搜索框').toBeTruthy();
    expect(input.getAttribute('placeholder')).toBe('搜索任务…');
    const named = input.getAttribute('aria-label') === '搜索任务'
      || qa(left[0], 'label').some((l) => textOf(l) === '搜索任务');
    expect(named, '搜索框有名为「搜索任务」的标签').toBe(true);
    expect(qa(left[0], 'svg').some((s) => s.getAttribute('width') === '16'), '左侧 SearchIcon 16').toBe(true);
  });

  it('任务列表：listbox 与 option、顺序按 getStatus 首次出现、每行两行、右侧 StatusTag sm、roving tabindex', async () => {
    setLogic();
    await mountApp('#/tasks');
    const list = qa(document, 'ul[role="listbox"][aria-label="任务"]');
    expect(list.length).toBe(1);
    const opts = options();
    expect(opts.length).toBe(8);
    expect(opts.map(optionTask)).toEqual(
      ['alpha', 'beta', 'can a', 'run me', 'z-last', 'redo', 'gone', 'prep only']);
    const selected = opts.filter((o) => o.getAttribute('aria-selected') === 'true');
    expect(selected.length).toBe(1);
    expect(textOf(selected[0]).indexOf('alpha')).toBe(0);
    expect(selected[0].getAttribute('tabindex')).toBe('0');
    expect(opts.filter((o) => o !== selected[0]).every((o) => o.getAttribute('tabindex') === '-1')).toBe(true);
    const tag = qa(opts[0], '[data-size="sm"]');
    expect(tag.length, '行右侧 StatusTag sm').toBeGreaterThan(0);
    expect(textOf(opts[0]).replace(/\s+/g, ' ')).toContain('attempt-003');
  });

  it('搜索：按 task_id 不分大小写子串、先去首尾空白；没有匹配时写一行且右栏不渲染', async () => {
    setLogic();
    await mountApp('#/tasks');
    const input = qa(document, 'input[type="search"]')[0];
    fireEvent.change(input, { target: { value: 'ALPHA' } });
    await settle();
    expect(options().map(optionTask)).toEqual(['alpha']);
    fireEvent.change(input, { target: { value: '  can a  ' } });
    await settle();
    expect(options().map(optionTask)).toEqual(['can a']);
    fireEvent.change(input, { target: { value: 'zzz' } });
    await settle();
    expect(options().length).toBe(0);
    expect(pageText()).toContain('没有符合条件的任务');
    expect(attemptTable('alpha'), '右栏不渲染').toBeNull();
    expect(qa(frame(), 'h2').length).toBe(0);
  });

  it('方向键与 Home/End 移动并选中，点击也选中；选中只改地址不重挂载', async () => {
    setLogic();
    await mountApp('#/tasks');
    const sel = () => options().filter((o) => o.getAttribute('aria-selected') === 'true')[0];
    sel().focus();
    fireEvent.keyDown(sel(), { key: 'ArrowDown' });
    await settle();
    expect(optionTask(sel())).toBe('beta');
    expect(hashParts().path).toBe('/tasks/beta');
    fireEvent.keyDown(sel(), { key: 'End' });
    await settle();
    expect(optionTask(sel())).toBe('prep only');
    fireEvent.keyDown(sel(), { key: 'Home' });
    await settle();
    expect(optionTask(sel())).toBe('alpha');
    fireEvent.click(options()[3]);
    await settle();
    expect(optionTask(sel())).toBe('run me');
    expect(hashParts().path).toBe('/tasks/run%20me');
  });

  it('attempt 表：aria-label、行高 40、按 attempt_no 倒序、11 列表头', async () => {
    setLogic();
    await mountApp('#/tasks');
    const table = attemptTable('alpha');
    expect(table).not.toBeNull();
    expect(table.getAttribute('data-row-height')).toBe('40');
    expect(headersOf(table)).toEqual(COLUMN_HEADERS);
    expect(tableRows(table).map((r) => textOf(cellsOf(r)[0]))).toEqual(['attempt-003', 'attempt-002', 'attempt-001']);
  });

  it('attempt 表 11 列取值：版本、状态、用时（wall / live / —）、检查、结论、失败分类、越界、token、费用、思考档位', async () => {
    setLogic();
    await mountApp('#/tasks');
    const table = attemptTable('alpha');
    expect(cellText(table, 0, '版本')).toBe('v2');
    expect(cellText(table, 2, '版本')).toBe('—');
    expect(cellText(table, 0, '用时')).toBe('28 分 39 秒');
    expect(cellText(table, 1, '用时')).toBe('18 分 22 秒');
    expect(cellText(table, 2, '用时')).toMatch(/^已用\s*19 分 6 秒$/);
    expect(cellText(table, 0, '检查')).toBe('8/8 fresh');
    expect(cellText(table, 2, '检查')).toBe('—');
    expect(cellText(table, 0, '结论')).toBe('—');
    expect(qa(cellsOf(tableRows(table)[1])[headersOf(table).indexOf('结论')], '[data-size="sm"]').length,
      '结论是 StatusTag sm').toBeGreaterThan(0);
    expect(cellText(table, 1, '失败分类')).toBe('EXECUTION_ERROR');
    expect(cellText(table, 0, '失败分类')).toBe('—');
    expect(cellText(table, 0, '越界')).toBe('0');
    expect(cellText(table, 2, '越界')).toBe('—');
    expect(cellText(table, 0, 'token')).toBe('4,210,385');
    expect(cellText(table, 2, 'token')).toBe('未知');
    expect(cellText(table, 0, '费用')).toBe('未知');
    expect(cellText(table, 2, '费用')).toBe('12.5');
    const effort = cellsOf(tableRows(table)[0])[headersOf(table).indexOf('思考档位')];
    expect(qa(effort, '.tt-effort').length, '有思考档位字段时交给 EffortPair').toBe(1);
    expect(textOf(effort)).toContain('max');
    expect(textOf(effort)).toContain('high');
    expect(cellText(table, 2, '思考档位')).toBe('未知');
    cleanup();
    await mountApp('#/tasks');
    fireEvent.click(options()[1]);
    await settle();
    const beta = attemptTable('beta');
    const viol = cellsOf(tableRows(beta)[0])[headersOf(beta).indexOf('越界')];
    expect(textOf(viol)).toBe('2');
    const css = fs.readFileSync(process.cwd() + '/src/pages/tasks/tasks-list.css', 'utf8')
      + fs.readFileSync(process.cwd() + '/src/pages/tasks/tasks-detail.css', 'utf8')
      + fs.readFileSync(process.cwd() + '/src/pages/tasks/tasks-tabs.css', 'utf8');
    const danger: string[] = [];
    css.split('}').forEach((block) => {
      if (block.indexOf('var(--tt-danger-text)') < 0) return;
      const at = block.indexOf('{');
      const head = at < 0 ? block : block.slice(0, at);
      const names = head.match(/\.([A-Za-z_][\w-]*)/g) || [];
      names.forEach((n) => danger.push(n.slice(1)));
    });
    expect(danger.length, '本片 CSS 里应引用了 var(--tt-danger-text)').toBeGreaterThan(0);
    const hit = qa(viol, '*').some((e) => danger.some((c) => e.classList.contains(c))) || viol.classList.contains(danger[0]);
    expect(hit, '越界大于 0 的单元格应带 danger 类：' + viol.className).toBe(true);
  });

  it('点行与行上按 Enter 都打开这个 attempt 的详情', async () => {
    setLogic();
    await mountApp('#/tasks?mock=data');
    const table = attemptTable('alpha');
    fireEvent.click(tableRows(table)[1]);
    await settle();
    expect(hashParts().path).toBe('/tasks/alpha/attempt-002');
    expect(textOf(h1El())).toBe('alpha · attempt-002');
    cleanup();
    await mountApp('#/tasks?mock=data');
    const table2 = attemptTable('alpha');
    const row = tableRows(table2)[2];
    row.focus();
    fireEvent.keyDown(row, { key: 'Enter' });
    await settle();
    expect(hashParts().path).toBe('/tasks/alpha/attempt-001');
    expect(textOf(h1El())).toBe('alpha · attempt-001');
  });

  it('表下下一步与复制：四种状态各显示对应文字，复制有三种结果', async () => {
    setLogic();
    await mountApp('#/tasks');
    const next = () => qa(document, '.tt-next')[0] || null;
    expect(textOf(next())).toContain('这个 attempt 等你验收。验收在规划端会话里进行。');
    expect(textOf(next())).toContain('/review-pi .agent/runs/alpha/attempt-003');
    expect(textOf(next())).toContain('下一步');
    fireEvent.click(qa(next(), '[aria-label="复制命令"]')[0]);
    await settle();
    expect(pageText()).toContain('这个环境没有剪贴板接口');
    stubClipboard({ writeText: () => Promise.resolve() });
    fireEvent.click(qa(next(), '[aria-label="复制命令"]')[0]);
    await settle();
    expect(pageText()).toContain('已复制');
    stubClipboard({ writeText: () => Promise.reject(new Error('no')) });
    fireEvent.click(qa(next(), '[aria-label="复制命令"]')[0]);
    await settle();
    expect(pageText()).toContain('复制失败');
    const cases: Array<[string, string, string]> = [
      ['beta', '已通过，等待集成。集成在规划端会话里进行。', '/review-pi .agent/runs/beta/attempt-001'],
      ['redo', '需要出新版本合同返工。', '/plan-task redo'],
      ['z-last', '需要你做决定，见摘要里的阻塞点。', ''],
    ];
    for (const [task, want, command] of cases) {
      cleanup();
      await mountApp('#/tasks');
      fireEvent.click(options().filter((o) => optionTask(o) === task)[0]);
      await settle();
      expect(textOf(next()), task).toContain(want);
      if (command) {
        expect(textOf(next()), task).toContain(command);
      } else {
        expect(qa(next(), '.tt-cmd').length, '升级与阻塞不带命令').toBe(0);
      }
    }
    cleanup();
    await mountApp('#/tasks');
    fireEvent.click(options().filter((o) => optionTask(o) === 'run me')[0]);
    await settle();
    expect(qa(document, '.tt-next').length, '运行中不显示下一步').toBe(0);
  });

  it('右栏：h2 是 task_id、旁边「N 个 attempt」、最下面一行说明', async () => {
    setLogic();
    await mountApp('#/tasks');
    expect(textOf(qa(frame(), 'h2')[0])).toBe('alpha');
    expect(pageText()).toContain('3 个 attempt');
    expect(pageText()).toContain('费用为空时显示');
  });
});
"""

# ---- detail：D05 详情页头、D06 详情五态（长期） ----
PROBE_DETAIL = PRELUDE + API_MOCK + TASKS_DATA + r"""
function sparseRow(): any {
  const row = logsCatRow({ state: 'PASS', tokens: null, cost: null, cost_status: 'unknown', plan_version: 1,
    wall_seconds: null, violations: null, checks: null, check_mode: null, effort_requested: null, effort_effective: null });
  delete row.effort_requested;
  return row;
}
function dlOf(rootEl: any): Record<string, string> {
  const out: Record<string, string> = {};
  qa(rootEl, 'dt').forEach((dt) => {
    const dd = dt.nextElementSibling;
    out[textOf(dt)] = dd ? textOf(dd) : '';
  });
  return out;
}

describe('D05 详情页头', () => {
  it('面包屑三项与 href：只带 mock，末项是当前项', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?mock=offline&keep=1');
    const nav = qa(document, 'nav[aria-label="面包屑"]');
    expect(nav.length).toBe(1);
    const links = qa(nav[0], 'a');
    expect(links.map(textOf)).toEqual(['任务', 'logs-cat']);
    expect(links[0].getAttribute('href')).toBe('#/tasks?mock=offline');
    expect(links[1].getAttribute('href')).toBe('#/tasks/logs-cat?mock=offline');
    const current = qa(nav[0], '[aria-current="page"]');
    expect(current.length).toBe(1);
    expect(textOf(current[0])).toBe('attempt-002');
  });

  it('h1 读到 attempt 之后是「<task> · <attempt>」', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002');
    expect(textOf(h1El())).toBe('logs-cat · attempt-002');
  });

  it('状态标签与思考档位：StatusTag md 加 EffortPair', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002');
    const tags = qa(document, '.tt-status[data-size="md"]');
    expect(tags.length).toBeGreaterThan(0);
    expect(textOf(tags[0])).toBe('待验收');
    const head = tags[0].parentElement;
    const effort = qa(head, '.tt-effort')[0];
    expect(effort, '页头第一行有思考档位').toBeTruthy();
    expect(textOf(effort)).toContain('max');
    expect(textOf(effort)).toContain('high');
  });

  it('dl 元信息：版本、状态时间（本地时间 + UTC 原值 title）、用时、token、费用、检查、越界', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002');
    const dl = dlOf(document);
    expect(dl['版本']).toBe('v2');
    expect(dl['用时']).toBe('28 分 39 秒');
    expect(dl['token']).toBe('4,210,385');
    expect(dl['费用']).toBe('未知（只报 token）');
    expect(dl['检查']).toBe('8/8（fresh）');
    expect(dl['越界']).toBe('0');
    const at = qa(document, 'dt').filter((dt) => textOf(dt) === '状态时间')[0].nextElementSibling;
    expect(textOf(at)).toBe(localTime('2026-10-18T06:21:40Z'));
    expect(at.getAttribute('title')).toBe('2026-10-18T06:21:40Z');
  });

  it('取不到的写「—」；没有思考档位字段时写未知', async () => {
    set('getStatus', env([sparseRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002');
    const dl = dlOf(document);
    expect(dl['用时']).toBe('—');
    expect(dl['token']).toBe('未知');
    expect(dl['检查']).toBe('—');
    expect(dl['越界']).toBe('—');
    const head2 = qa(document, '.tt-status[data-size="md"]')[0].parentElement;
    expect(textOf(head2), '没有 effort_requested 字段时写未知').toContain('未知');
  });

  it('下一步：四种文字与命令、其余状态不显示', async () => {
    const cases: Array<[string, string, string]> = [
      ['NEEDS_REVIEW', '这个 attempt 等你验收。验收在规划端会话里进行。', '/review-pi .agent/runs/logs-cat/attempt-002'],
      ['PASS', '已通过，等待集成。集成在规划端会话里进行。', '/review-pi .agent/runs/logs-cat/attempt-002'],
      ['REVISE', '需要出新版本合同返工。', '/plan-task logs-cat'],
      ['ESCALATE', '需要你做决定，见摘要里的阻塞点。', ''],
      ['RUNNING', '', ''],
    ];
    for (const [state, want, command] of cases) {
      cleanup();
      set('getStatus', env([logsCatRow({ state })], ['status']));
      set('getAttempt', attemptEnv({ state }));
      await mountApp('#/tasks/logs-cat/attempt-002');
      const next = qa(document, '.tt-next');
      if (!want) {
        expect(next.length, state + ' 不显示下一步').toBe(0);
        continue;
      }
      expect(next.length, state + ' 应显示下一步').toBe(1);
      expect(textOf(next[0])).toContain(want);
      expect(textOf(next[0])).toContain('下一步');
      if (command) {
        expect(textOf(next[0])).toContain(command);
      } else {
        expect(qa(next[0], '.tt-cmd').length, '升级与阻塞不带命令').toBe(0);
      }
    }
  });

  it('复制结果：三种文字', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002');
    const copy = () => qa(document, '[aria-label="复制命令"]')[0];
    expect(copy(), '页头下一步带复制钮').toBeTruthy();
    fireEvent.click(copy());
    await settle();
    expect(pageText()).toContain('这个环境没有剪贴板接口');
    stubClipboard({ writeText: () => Promise.resolve() });
    fireEvent.click(copy());
    await settle();
    expect(pageText()).toContain('已复制');
    stubClipboard({ writeText: () => Promise.reject(new Error('x')) });
    fireEvent.click(copy());
    await settle();
    expect(pageText()).toContain('复制失败');
  });
});

describe('D06 详情五态', () => {
  it('读取中：骨架 299ms 没有、300ms 有；整页恰一个 data-page-state', async () => {
    vi.useFakeTimers();
    set('getStatus', () => new Promise(() => {}));
    set('getAttempt', () => new Promise(() => {}));
    await mountApp('#/tasks/logs-cat/attempt-002?mock=loading');
    expect(frame().getAttribute('data-page-state')).toBe('loading');
    expect(qa(document, '[data-page-state]').length).toBe(1);
    advance(299);
    expect(qa(document, '.tt-skel').length, '299ms 没有骨架').toBe(0);
    advance(1);
    expect(qa(document, '.tt-skel').length, '300ms 有骨架').toBeGreaterThan(0);
    expect(qa(document, '[data-page]').length, '读取中没有视图').toBe(0);
    vi.useRealTimers();
  });

  it('有数据：视图在、data-page-state 是 data', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(qa(document, '[data-page-state]').length).toBe(1);
    expect(qa(document, '[role="tablist"]').length).toBe(1);
  });

  it('找不到：标题「找不到这个 attempt」与说明，h1 仍是「任务」，地址不变', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', bad(['logs', 'show', 'x/y'], 2, ['ERROR 夹具里没有这份数据：x/y']));
    await mountApp('#/tasks/x/y?mock=data');
    expect(frame().getAttribute('data-page-state')).toBe('empty');
    expect(textOf(h1El())).toBe('任务');
    expect(pageText()).toContain('找不到这个 attempt');
    expect(pageText()).toContain('x/y 不在 status 里，logs show 也没有读到。回到任务列表重新选一个。');
    expect(window.location.hash, '挂载时不改写地址').toBe('#/tasks/x/y?mock=data');
  });

  it('出错：getStatus 失败时页面级出错块写 status 的命令、退出码与报错原文', async () => {
    set('getStatus', bad(['status'], 2, ['ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?mock=error');
    expect(frame().getAttribute('data-page-state')).toBe('error');
    expect(textOf(h1El())).toBe('任务');
    expect(pageText()).toContain('没能读到数据');
    expect(pageText()).toContain('命令（status）返回退出码 2');
    expect(textOf(qa(document, 'pre')[0])).toContain('Permission denied');
    expect(btn(document.body, '重试')).not.toBeNull();
  });

  it('断线：数据照常、一条 role=alert、「可能已过期」、data-stale、禁用的重新连接', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?mock=offline');
    const root = frame();
    expect(root.getAttribute('data-page-state')).toBe('data');
    expect(root.getAttribute('data-stale')).toBe('true');
    expect(qa(document, '[role="alert"]').length).toBe(1);
    expect(pageText()).toContain('可能已过期');
    const reconnect = qa(document, 'button').filter((b) => textOf(b) === '重新连接')[0];
    expect(reconnect, '禁用的重新连接').toBeTruthy();
    expect(reconnect.disabled).toBe(true);
  });

  it('?mock=empty 时 status 为空：logs-cat/attempt-002 仍有 logs show，照常显示，取自 status 的字段写「—」', async () => {
    set('getStatus', env([], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?mock=empty');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(textOf(h1El())).toBe('logs-cat · attempt-002');
    const dl = dlOf(document);
    expect(dl['版本']).toBe('—');
    expect(dl['用时']).toBe('—');
    expect(dl['token']).toBe('—');
    expect(dl['越界']).toBe('—');
  });

  it('status 有这一行、logs show 读不到：页头照常，摘要、检查、全部文件三个页签显示行内出错块', async () => {
    set('getStatus', env([rowOf({ attempt: 'status-live-json/attempt-001', task_id: 'status-live-json',
      plan_version: 1, attempt_no: 1, state: 'PASS', wall_seconds: 954.0, checks: '5/5', check_mode: 'fresh',
      verdict: 'PASS', violations: 0, tokens: 2981204, cost: null, cost_status: 'unknown' })], ['status']));
    set('getAttempt', bad(['logs', 'show', 'status-live-json/attempt-001'], 2, ['ERROR 夹具里没有这份数据']));
    set('readFile', (task: string, attempt: string, path: string) =>
      Promise.resolve(bad(['logs', 'cat', task + '/' + attempt, path], 2, ['ERROR 夹具里没有这份数据：' + path])));
    await mountApp('#/tasks/status-live-json/attempt-001?mock=data');
    expect(frame().getAttribute('data-page-state')).toBe('data');
    expect(textOf(h1El())).toBe('status-live-json · attempt-001');
    for (const tab of ['摘要', '检查', '全部文件']) {
      fireEvent.click(tabByLabel(tab));
      await settle();
      const t = textOf(panel());
      expect(t, tab + ' 页签行内出错').toContain('没能读到 ');
      expect(t, tab + ' 页签行内出错').toContain('返回退出码 2');
      const pre = qa(panel(), 'pre')[0];
      expect(pre, tab + ' 的 messages 在 pre 里').toBeTruthy();
      expect(textOf(pre)).toContain('ERROR 夹具里没有这份数据');
      expect(qa(panel(), '[role="tabpanel"]').length, '页签内不嵌套 PageFrame').toBe(0);
    }
  });
});
"""

# ---- tabs：D07 页签与地址、D08–D11 六个页签（长期） ----
PROBE_TABS = PRELUDE + API_MOCK + TASKS_DATA + r"""
function openTab(label: string) {
  fireEvent.click(tabByLabel(label));
  return settle();
}

describe('D07 页签与地址', () => {
  it('六个页签依次是摘要、补丁、检查、执行报告、事件、全部文件；aria-label 是「证据」', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002');
    const list = qa(document, '[role="tablist"]');
    expect(list.length).toBe(1);
    expect(list[0].getAttribute('aria-label')).toBe('证据');
    expect(tabs().map(textOf)).toEqual(['摘要', '补丁', '检查', '执行报告', '事件', '全部文件']);
    expect(selectedTabLabel()).toBe('摘要');
  });

  it('点页签：tab 变了、mock 与其他参数不变、路径不变、页签与 h1 还是原来的节点（没有重挂载）', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?mock=offline&keep=1');
    const tabBefore = tabByLabel('补丁');
    const h1Before = h1El();
    await openTab('补丁');
    expect(selectedTabLabel()).toBe('补丁');
    const p = hashParts();
    expect(p.path).toBe('/tasks/logs-cat/attempt-002');
    expect(p.params).toEqual({ mock: 'offline', keep: '1', tab: 'patch' });
    expect(tabByLabel('补丁'), '页签节点不变').toBe(tabBefore);
    expect(h1El(), 'h1 节点不变').toBe(h1Before);
    await openTab('摘要');
    expect(hashParts().params.tab, '值为缺省时删掉参数').toBeUndefined();
  });

  it('方向键切页签：先改本地状态与地址，焦点留在页签上', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?mock=data');
    const first = tabByLabel('摘要');
    first.focus();
    fireEvent.keyDown(first, { key: 'ArrowRight' });
    await settle();
    expect(selectedTabLabel()).toBe('补丁');
    expect(hashParts().params.tab).toBe('patch');
    expect(document.activeElement, '焦点在页签上').toBe(tabByLabel('补丁'));
    fireEvent.keyDown(document.activeElement as Element, { key: 'End' });
    await settle();
    expect(selectedTabLabel()).toBe('全部文件');
    expect(hashParts().params.tab).toBe('files');
    expect(hashParts().params.mock).toBe('data');
  });

  it('手改地址并派发 hashchange 之后，页签跟着变', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?mock=data');
    window.location.hash = '#/tasks/logs-cat/attempt-002?tab=files&mock=data';
    fireEvent(window, new HashChangeEvent('hashchange'));
    await settle();
    expect(selectedTabLabel()).toBe('全部文件');
    window.location.hash = '#/tasks/logs-cat/attempt-002?tab=events&mock=data';
    fireEvent(window, new HashChangeEvent('hashchange'));
    await settle();
    expect(selectedTabLabel()).toBe('事件');
  });
});

describe('D08 摘要与执行报告', () => {
  it('摘要：文件行（FileTextIcon 14、summary.md、512 B、安全 Markdown 说明）与 tt-md 内容原样', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?mock=data');
    const md = qa(panel(), '.tt-md');
    expect(md.length, '摘要是 SafeMarkdown').toBe(1);
    const t = textOf(panel());
    expect(t).toContain('summary.md');
    expect(t).toContain('512 B');
    expect(t).toContain('安全 Markdown：原始 HTML 当文字显示');
    expect(qa(panel(), 'svg').some((s) => s.getAttribute('width') === '14'), '文件行 FileTextIcon 14').toBe(true);
    expect(t).toContain('logs-cat.v2 / attempt-002');
    expect(t).toContain('<img src=x onerror=alert(1)> 探针');
    expect(qa(panel(), 'img, script').length, '不可信内容只按文本显示').toBe(0);
  });

  it('摘要被截断：内容上方 info「摘要较长，只显示前 N KB」与 [查看全文]；点了在下方用查看器打开', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv({ summary: { bytes: 3000, truncated: true, text: 'x'.repeat(3000) } }));
    await mountApp('#/tasks/logs-cat/attempt-002?mock=data');
    const p0 = textOf(panel());
    expect(p0).toContain('摘要较长，只显示前 2 KB');
    const full = btn(panel(), '查看全文');
    expect(full, '[查看全文]').toBeTruthy();
    fireEvent.click(full);
    await settle();
    const viewer = qa(panel(), '.tt-viewer');
    expect(viewer.length, '查看全文打开文本查看器').toBeGreaterThan(0);
    expect(textOf(qa(viewer[0], '.tt-viewer__title')[0])).toBe('summary.md');
  });

  it('没有摘要时写「还没有摘要：attempt 结束后才有 summary.md」', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv({ summary: null }));
    await mountApp('#/tasks/logs-cat/attempt-002?mock=data');
    expect(textOf(panel())).toContain('还没有摘要：attempt 结束后才有 summary.md');
  });

  it('onOpenLink：内容下方写「打开外部链接在第二阶段接入：<网址>」', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv({ summary: { bytes: 30, truncated: false,
      text: '看 [官网](https://example.com/a?b=1) 与 <script>alert(1)</script>' } }));
    await mountApp('#/tasks/logs-cat/attempt-002?mock=data');
    const link = qa(panel(), '.tt-md__link')[0];
    expect(link, '摘要里的放行链接').toBeTruthy();
    fireEvent.click(link);
    await settle();
    expect(textOf(panel())).toContain('打开外部链接在第二阶段接入：https://example.com/a?b=1');
    expect(qa(panel(), 'a').length, '页签面板里没有 a 元素').toBe(0);
  });

  it('执行报告：warning 提示条「以下是执行器的自述，不是证据。」加文本查看器，内容原样', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?tab=report&mock=data');
    const banner = qa(panel(), '.tt-banner')[0];
    expect(banner, '执行报告顶部提示条').toBeTruthy();
    expect(banner.getAttribute('data-tone')).toBe('warning');
    expect(textOf(banner)).toBe('以下是执行器的自述，不是证据。');
    const viewer = qa(panel(), '.tt-viewer');
    expect(viewer.length, '执行报告用文本查看器').toBeGreaterThan(0);
    expect(textOf(qa(viewer[0], '.tt-viewer__title')[0])).toBe('executor-report.md');
    const t = textOf(viewer[0]);
    expect(t).toContain('<img src=x onerror=alert(1)> ← 这一行必须原样显示为文字');
    expect(qa(viewer[0], 'img, script').length).toBe(0);
    expect(t.indexOf('\u001b')).toBe(-1);
    expect(t.indexOf('[31m')).toBe(-1);
  });
});

describe('D09 补丁与检查', () => {
  it('补丁：DiffView 收到拼好的补丁，title 是 candidate.patch；ANSI 与标签只按文本显示', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    set('readFile', (task: string, attempt: string, path: string) => Promise.resolve(env({
      path, mode: 'text', done: true, next_cursor: null,
      text: 'diff --git a/src/x.ts b/src/x.ts\n--- a/src/x.ts\n+++ b/src/x.ts\n@@ -1,2 +1,2 @@\n'
        + '-const a = 1;\n+const a = 2; // \u001b[31mRED\u001b[0m <script>alert(1)</script>\n',
    }, ['logs', 'cat', task + '/' + attempt, path])));
    await mountApp('#/tasks/logs-cat/attempt-002?tab=patch&mock=data');
    const diff = qa(panel(), '.tt-diff');
    expect(diff.length, '补丁页签是差异视图').toBe(1);
    expect(textOf(qa(diff[0], '.tt-diff__summary-title')[0])).toBe('candidate.patch');
    const t = textOf(diff[0]);
    expect(t).toContain('src/x.ts');
    expect(t).toContain('RED');
    expect(t).toContain('<script>alert(1)</script>');
    expect(t.indexOf('\u001b')).toBe(-1);
    expect(t.indexOf('[31m')).toBe(-1);
    expect(qa(diff[0], 'script, img').length).toBe(0);
  });

  it('补丁没读完：[继续加载] 带游标再读一页，接在后面', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    let calls = 0;
    set('readFile', (task: string, attempt: string, path: string, cursor?: string) => {
      calls += 1;
      const first = calls === 1;
      return Promise.resolve(env({
        path, mode: 'text', done: !first, next_cursor: first ? 'c1-next' : null,
        text: first ? 'diff --git a/src/a.ts b/src/a.ts\n--- a/src/a.ts\n+++ b/src/a.ts\n@@ -1 +1 @@\n-a\n+b\n' : 'diff --git a/src/b.ts b/src/b.ts\n--- a/src/b.ts\n+++ b/src/b.ts\n@@ -1 +1 @@\n-c\n+d\n',
      }, ['logs', 'cat', task + '/' + attempt, path]));
    });
    await mountApp('#/tasks/logs-cat/attempt-002?tab=patch&mock=data');
    const diff = qa(panel(), '.tt-diff')[0];
    expect(textOf(diff)).toContain('src/a.ts');
    const more = btn(diff, '继续加载');
    expect(more, '没读完时有 [继续加载]').toBeTruthy();
    fireEvent.click(more);
    await settle();
    expect(calls).toBe(2);
    expect(textOf(qa(panel(), '.tt-diff')[0])).toContain('src/b.ts');
  });

  it('检查：汇总行取自 status 行，日志表列 checks/NN/<ID>.log，点一行在表下打开；有说明行', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?tab=checks&mock=data');
    const t = textOf(panel());
    expect(t).toContain('检查 8/8（fresh）');
    expect(t).toContain('每条检查的结果要等 logs show 给出');
    const table = qa(panel(), 'table[aria-label="检查日志"]');
    expect(table.length, '检查日志表').toBe(1);
    const rows = tableRows(table[0]);
    expect(rows.length).toBe(1);
    expect(textOf(cellsOf(rows[0])[0])).toBe('checks/01/V01.log');
    expect(textOf(cellsOf(rows[0])[headersOf(table[0]).length - 1])).toMatch(/1\.8\s*KB/);
    fireEvent.click(rows[0]);
    await settle();
    const viewer = qa(panel(), '.tt-viewer');
    expect(viewer.length, '点一行在表下用文本查看器打开').toBeGreaterThan(0);
    expect(textOf(qa(viewer[0], '.tt-viewer__title')[0])).toBe('checks/01/V01.log');
    const vt = textOf(viewer[0]);
    expect(vt.indexOf('\u001b')).toBe(-1);
    expect(vt.indexOf('[31m')).toBe(-1);
  });

  it('检查：checks 为「-」时写「还没有检查结果」；证据里没有检查日志时写「这个 attempt 没有检查日志」', async () => {
    set('getStatus', env([logsCatRow({ checks: '-', check_mode: null })], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?tab=checks&mock=data');
    expect(textOf(panel())).toContain('还没有检查结果');
    cleanup();
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv({ evidence: [{ path: 'summary.md', bytes: 512 }] }));
    await mountApp('#/tasks/logs-cat/attempt-002?tab=checks&mock=data');
    expect(textOf(panel())).toContain('这个 attempt 没有检查日志');
  });
});

describe('D10 事件', () => {
  it('已结束的 attempt：跟随开关禁用，原因文字是「attempt 已结束，没有新事件」', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?tab=events&mock=data');
    const log = qa(panel(), '.tt-log');
    expect(log.length, '事件页签是日志跟随').toBe(1);
    const sw = qa(log[0], '[role="switch"]')[0];
    expect(sw, '跟随开关').toBeTruthy();
    expect(sw.getAttribute('aria-disabled') === 'true' || sw.hasAttribute('disabled')).toBe(true);
    expect(textOf(qa(log[0], '.tt-log__status')[0])).toContain('attempt 已结束，没有新事件');
    expect(qa(log[0], 'input[aria-label="过滤事件"]').length, '自带过滤框').toBe(1);
  });
});

describe('TRANS 事件跟随模拟', () => {
  it('运行中的 attempt：假计时器每 1000ms 多一行，到上限停；切走页签不再追加；卸载后没有挂起的计时器', async () => {
    vi.useFakeTimers();
    const r = await mountApp('#/tasks/ui-readonly-api/attempt-001?tab=events&mock=data');
    const log = qa(panel(), '.tt-log')[0];
    expect(log, '运行中 attempt 的事件页签').toBeTruthy();
    const sw = qa(log, '[role="switch"]')[0];
    expect(sw.getAttribute('aria-disabled') === 'true' || sw.hasAttribute('disabled')).toBe(false);
    const count = () => qa(qa(panel(), '.tt-log')[0], '.tt-viewer__row').length;
    const base = count();
    expect(base, '夹具第 1 页有行').toBeGreaterThan(0);
    advance(1000);
    expect(count(), '推进 1000ms 多一行').toBe(base + 1);
    advance(4000);
    expect(count(), '按 1000ms 的节奏追加').toBe(base + 5);
    advance(120000);
    const capped = count();
    advance(10000);
    expect(count(), '到上限后不再追加').toBe(capped);
    await openTabSafe('摘要');
    const away = count();
    advance(30000);
    expect(count(), '切走页签之后不再追加').toBe(away);
    advance(0);
    r.unmount();
    expect(vi.getTimerCount(), '卸载后没有挂起的计时器').toBe(0);
    vi.useRealTimers();
  }, 60000);
});

async function openTabSafe(label: string) {
  const t = tabByLabel(label);
  if (t) fireEvent.click(t);
  await settle();
}

describe('D11 全部文件', () => {
  it('三列与大小格式、每行「在资源管理器中显示」禁用、整行打开文本查看器、caption 写跳过的链接数', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?tab=files&mock=data');
    const table = qa(panel(), 'table[aria-label="证据文件"]');
    expect(table.length, '证据文件表').toBe(1);
    expect(headersOf(table[0]).length).toBe(3);
    const rows = tableRows(table[0]);
    expect(rows.length).toBe(5);
    const paths = rows.map((r) => textOf(cellsOf(r)[0]));
    expect(paths.slice().sort()).toEqual(['candidate.patch', 'checks/01/V01.log', 'events.jsonl',
      'executor-report.md', 'summary.md']);
    const sizeAt = headersOf(table[0]).length - 2;
    expect(textOf(cellsOf(rows[0])[sizeAt])).toBe('512 B');
    expect(textOf(cellsOf(rows[1])[sizeAt])).toMatch(/17\.9\s*KB/);
    expect(textOf(cellsOf(rows[2])[sizeAt])).toBe('2.7 MB');
    const reveals = qa(table[0], 'button').filter((b) => textOf(b) === '在资源管理器中显示');
    expect(reveals.length, '每行一个禁用入口').toBe(5);
    reveals.forEach((b) => expect(b.disabled, '在资源管理器中显示应禁用').toBe(true));
    fireEvent.click(rows[2]);
    await settle();
    const viewer = qa(panel(), '.tt-viewer');
    expect(viewer.length, '点一行按段打开').toBeGreaterThan(0);
    expect(textOf(qa(viewer[0], '.tt-viewer__title')[0])).toBe('events.jsonl');
    expect(textOf(viewer[0])).toContain('这一行不是合法 JSON，已隐藏');
    expect(textOf(viewer[0])).toContain('这一行超过 4 MiB，已隐藏');
    expect(textOf(panel())).toContain('点一行按段打开');
    expect(textOf(panel())).toContain('跳过的链接 0 个');
  });

  it('「在资源管理器中显示」悬停 400ms 出现提示「第二阶段接入」', async () => {
    vi.useFakeTimers();
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?tab=files&mock=data');
    const b = qa(panel(), 'button').filter((x) => textOf(x) === '在资源管理器中显示')[0];
    fireEvent.mouseEnter(b.parentElement);
    advance(399);
    expect(qa(document, '[role="tooltip"]').length, '399ms 没有提示').toBe(0);
    advance(1);
    const tip = qa(document, '[role="tooltip"]')[0];
    expect(tip, '400ms 出现提示').toBeTruthy();
    expect(textOf(tip)).toBe('第二阶段接入');
    vi.useRealTimers();
  });
});
"""

# ---- data：D02 数据层五个开关（长期；直接调合同写定的三个导出） ----
PROBE_DATA = PRELUDE + r"""
function at(mock: string) {
  window.location.hash = '#/tasks?mock=' + mock;
}

describe('D02 数据层五个开关', () => {
  it('data（缺省）：api.ts 有的原样返回，command 沿用 api.ts，每次都深拷贝', async () => {
    at('data');
    const m: any = await import('../src/pages/tasks/tasks-data');
    const first: any = await m.readAttempt('logs-cat', 'attempt-002');
    expect(first.ok).toBe(true);
    expect(first.command).toEqual(['logs', 'show', 'logs-cat/attempt-002']);
    expect(first.data.state).toBe('NEEDS_REVIEW');
    first.data.state = '已改坏';
    const second: any = await m.readAttempt('logs-cat', 'attempt-002');
    expect(second.data.state, '每次都深拷贝').toBe('NEEDS_REVIEW');
    const report: any = await m.readAttemptFile('logs-cat', 'attempt-002', 'executor-report.md');
    expect(report.ok).toBe(true);
    expect(report.command).toEqual(['logs', 'cat', 'logs-cat/attempt-002', 'executor-report.md']);
    expect(report.data.text).toContain('执行报告');
  });

  it('loading：api.ts 永不兑现，包装也一直等着', async () => {
    at('loading');
    const m: any = await import('../src/pages/tasks/tasks-data');
    let done = 0;
    m.readAttempt('logs-cat', 'attempt-002').then(() => { done += 1; }, () => { done += 1; });
    m.readAttemptFile('logs-cat', 'attempt-002', 'candidate.patch').then(() => { done += 1; }, () => { done += 1; });
    await new Promise((r) => setTimeout(r, 50));
    expect(done, 'loading 下一直挂起').toBe(0);
  });

  it('error：返回内核报错原文，不被本片夹具盖住', async () => {
    at('error');
    const m: any = await import('../src/pages/tasks/tasks-data');
    const a: any = await m.readAttempt('logs-cat', 'attempt-002');
    expect(a.ok).toBe(false);
    expect(a.command).toEqual(['logs', 'show', 'logs-cat/attempt-002']);
    expect(a.messages.join('')).toContain('Permission denied');
    const b: any = await m.readAttempt('ui-readonly-api', 'attempt-001');
    expect(b.ok, 'error 开关不去取夹具').toBe(false);
    expect(b.messages.join('')).toContain('Permission denied');
    const c: any = await m.readAttemptFile('logs-cat', 'attempt-002', 'candidate.patch');
    expect(c.ok).toBe(false);
    expect(c.messages.join('')).toContain('Permission denied');
  });

  it('offline 与 empty：api.ts 有的照常返回', async () => {
    at('offline');
    const m: any = await import('../src/pages/tasks/tasks-data');
    const a: any = await m.readAttempt('logs-cat', 'attempt-002');
    expect(a.ok, 'offline 同 data').toBe(true);
    at('empty');
    const b: any = await m.readAttempt('logs-cat', 'attempt-002');
    expect(b.ok, 'empty 时 logs show 照常').toBe(true);
  });

  it('loadAttemptDetail：并行读 getStatus 与 readAttempt；getStatus 失败返回它的信封；row 与 attemptEnv；找不到时 row 为 null 且 attemptEnv 不 ok', async () => {
    at('data');
    const m: any = await import('../src/pages/tasks/tasks-data');
    const d: any = await m.loadAttemptDetail('logs-cat', 'attempt-002');
    expect(d.ok).toBe(true);
    expect(d.data.task).toBe('logs-cat');
    expect(d.data.attempt).toBe('attempt-002');
    expect(d.data.row && d.data.row.state).toBe('NEEDS_REVIEW');
    expect(d.data.attemptEnv && d.data.attemptEnv.ok).toBe(true);
    const miss: any = await m.loadAttemptDetail('x', 'y');
    expect(miss.ok, 'getStatus 没失败就还是 ok 信封').toBe(true);
    expect(miss.data.row).toBeNull();
    expect(miss.data.attemptEnv.ok).toBe(false);
    at('error');
    const e: any = await m.loadAttemptDetail('logs-cat', 'attempt-002');
    expect(e.ok, 'getStatus 失败返回它的信封').toBe(false);
    expect(e.command).toEqual(['status']);
  });
});

describe('TRANS 数据层取本片夹具', () => {
  it('data：api.ts 报缺时才取本片夹具（运行中的 attempt 与补丁、检查日志、事件第 2 页）', async () => {
    at('data');
    const m: any = await import('../src/pages/tasks/tasks-data');
    const live: any = await m.readAttempt('ui-readonly-api', 'attempt-001');
    expect(live.ok, '夹具里有这个 attempt').toBe(true);
    expect(live.command).toEqual(['logs', 'show', 'ui-readonly-api/attempt-001']);
    expect(live.data.state).toBe('RUNNING');
    expect(live.data.summary).toBeNull();
    const patch: any = await m.readAttemptFile('logs-cat', 'attempt-002', 'candidate.patch');
    expect(patch.ok, '补丁在本片夹具里').toBe(true);
    expect(patch.data.text).toContain('diff --git');
    const log: any = await m.readAttemptFile('logs-cat', 'attempt-002', 'checks/01/V01.log');
    expect(log.ok, '检查日志在本片夹具里').toBe(true);
    const page2: any = await m.readAttemptFile('logs-cat', 'attempt-002', 'events.jsonl', 'c1-0001a2f3');
    expect(page2.ok, '事件第 2 页按游标取自本片夹具').toBe(true);
    expect(page2.data.mode).toBe('jsonl');
    expect(Array.isArray(page2.data.lines)).toBe(true);
    const liveEvents: any = await m.readAttemptFile('ui-readonly-api', 'attempt-001', 'events.jsonl');
    expect(liveEvents.ok, '运行中 attempt 的事件第 1 页在本片夹具里').toBe(true);
    const missing: any = await m.readAttemptFile('logs-cat', 'attempt-002', 'no-such.file');
    expect(missing.ok, '夹具里也没有的返回 api.ts 的原信封').toBe(false);
    expect(missing.messages.join('')).toContain('夹具里没有这份数据');
  });

  it('offline 与 empty 下照样取本片夹具', async () => {
    at('offline');
    const m: any = await import('../src/pages/tasks/tasks-data');
    const a: any = await m.readAttempt('ui-readonly-api', 'attempt-001');
    expect(a.ok, 'offline 下照样取夹具').toBe(true);
    at('empty');
    const c: any = await m.readAttempt('ui-readonly-api', 'attempt-001');
    expect(c.ok, 'empty 下包装照样处理夹具').toBe(true);
  });
});
"""

# ---- app：任务页 App 级五态（过渡）、TRANS 夹具值、P6 分组地址导航（长期）与 TRANS 夹具列表、D12 不可信内容与写入口 ----
PROBE_APP = PRELUDE + API_MOCK + TASKS_DATA + r"""
const MOCKS = ['data', 'loading', 'empty', 'error', 'offline'];

describe('TRANS 任务页 App 级五态', () => {
  it('列表页：五态逐个渲染（骨架 299ms 无 300ms 有、空态文字、出错块、断线条）', async () => {
    for (const mock of MOCKS) {
      vi.useFakeTimers();
      await mountApp('#/tasks?mock=' + mock);
      const state = frame().getAttribute('data-page-state');
      if (mock === 'loading') {
        expect(state).toBe('loading');
        advance(299);
        expect(qa(document, '.tt-skel').length, 'loading 299ms').toBe(0);
        advance(1);
        expect(qa(document, '.tt-skel').length, 'loading 300ms').toBeGreaterThan(0);
      } else if (mock === 'empty') {
        expect(state).toBe('empty');
        expect(pageText()).toContain('还没有 attempt');
      } else if (mock === 'error') {
        expect(state).toBe('error');
        expect(pageText()).toContain('命令（status）返回退出码 2');
      } else if (mock === 'offline') {
        expect(state).toBe('data');
        expect(frame().getAttribute('data-stale')).toBe('true');
        expect(pageText()).toContain('可能已过期');
      } else {
        expect(state).toBe('data');
        expect(textOf(h1El())).toBe('任务');
        expect(qa(document, '[data-page]').length).toBe(1);
      }
      expect(qa(document, '[data-page-state]').length, '整页恰一个页面根').toBe(1);
      cleanup();
      vi.useRealTimers();
    }
  }, 60000);

  it('详情页：五态逐个渲染（含 #/tasks/x/y 的空态与地址不变）', async () => {
    for (const mock of MOCKS) {
      vi.useFakeTimers();
      await mountApp('#/tasks/logs-cat/attempt-002?mock=' + mock);
      const state = frame().getAttribute('data-page-state');
      if (mock === 'loading') {
        expect(state).toBe('loading');
        advance(300);
        expect(qa(document, '.tt-skel').length).toBeGreaterThan(0);
        expect(textOf(h1El())).toBe('任务');
      } else if (mock === 'empty') {
        expect(state, 'empty 时 logs-cat/attempt-002 仍有 logs show').toBe('data');
        expect(textOf(h1El())).toBe('logs-cat · attempt-002');
      } else if (mock === 'error') {
        expect(state).toBe('error');
        expect(pageText()).toContain('命令（status）返回退出码 2');
      } else if (mock === 'offline') {
        expect(state).toBe('data');
        expect(frame().getAttribute('data-stale')).toBe('true');
      } else {
        expect(state).toBe('data');
        expect(textOf(h1El())).toBe('logs-cat · attempt-002');
      }
      cleanup();
      vi.useRealTimers();
    }
    await mountApp('#/tasks/x/y?mock=data');
    expect(frame().getAttribute('data-page-state')).toBe('empty');
    expect(textOf(h1El())).toBe('任务');
    expect(window.location.hash).toBe('#/tasks/x/y?mock=data');
  }, 60000);
});

describe('TRANS 夹具下的具体值', () => {
  it('列表：6 个任务、胶囊计数 1/2/1/1/1、缺省选中 ui-readonly-api、logs-cat 两行倒序', async () => {
    await mountApp('#/tasks?mock=data');
    expect(options().length).toBe(6);
    expect(capsules().map((b) => textOf(b).replace(/[^\d]/g, ''))).toEqual(['1', '2', '1', '1', '1']);
    const sel = options().filter((o) => o.getAttribute('aria-selected') === 'true');
    expect(optionTask(sel[0])).toBe('ui-readonly-api');
    // 合同「右栏」只有一张 Table，aria-label 是「<选中的 task> 的 attempt」；上面断言的是缺省选中
    // ui-readonly-api，此时页面上没有「logs-cat 的 attempt」表，attemptTable 会返回 null、tableRows 退回到
    // 整个 document 读到别处的行（T011 返工：原写法要求选中 ui-readonly-api 的同时有 logs-cat 的表，
    // 与合同互斥，任何实现都过不了）。要看 logs-cat 的表，先点选它。
    const logsCat = options().filter((o) => optionTask(o) === 'logs-cat')[0];
    expect(logsCat, '列表里有 logs-cat 选项').toBeTruthy();
    fireEvent.click(logsCat);
    await settle();
    expect(logsCat.getAttribute('aria-selected'), '点选后 logs-cat 是选中项').toBe('true');
    const table = attemptTable('logs-cat');
    expect(table, '右栏是 logs-cat 的 attempt 表（不要再退回 document）').toBeTruthy();
    expect(tableRows(table).map((r) => textOf(cellsOf(r)[0]))).toEqual(['attempt-002', 'attempt-001']);
    expect(cellText(table, 0, 'token')).toBe('4,210,385');
    expect(cellText(table, 1, '费用')).toBe('未知');
  });

  it('详情：页头与 attempt 表外的夹具值；全部文件页签 5 个禁用入口', async () => {
    await mountApp('#/tasks/logs-cat/attempt-002?mock=data');
    expect(textOf(h1El())).toBe('logs-cat · attempt-002');
    const dl: Record<string, string> = {};
    qa(document, 'dt').forEach((dt) => { dl[textOf(dt)] = textOf(dt.nextElementSibling); });
    expect(dl['版本']).toBe('v2');
    expect(dl['用时']).toBe('28 分 39 秒');
    expect(dl['token']).toBe('4,210,385');
    expect(dl['检查']).toBe('8/8（fresh）');
    expect(dl['越界']).toBe('0');
    fireEvent.click(tabByLabel('全部文件'));
    await settle();
    const table = qa(panel(), 'table[aria-label="证据文件"]')[0];
    expect(tableRows(table).length).toBe(5);
    expect(qa(table, 'button').filter((b) => textOf(b) === '在资源管理器中显示').length).toBe(5);
    fireEvent.click(tabByLabel('补丁'));
    await settle();
    expect(qa(panel(), '.tt-diff').length, '补丁取自本片夹具').toBe(1);
  });
});

describe('P6 分组地址导航', () => {
  it('点 T009 指标卡：同步换路由到 #/tasks?group=<组>、对应胶囊按下、mock 与其他参数保留；指标卡只有前四个分组', async () => {
    set('getStatus', env([
      rowOf({ attempt: 'alpha/attempt-001', task_id: 'alpha', attempt_no: 1, state: 'RUNNING' }),
      rowOf({ attempt: 'beta/attempt-001', task_id: 'beta', attempt_no: 1, state: 'NEEDS_REVIEW' }),
      rowOf({ attempt: 'gamma/attempt-001', task_id: 'gamma', attempt_no: 1, state: 'ESCALATE' }),
      rowOf({ attempt: 'delta/attempt-001', task_id: 'delta', attempt_no: 1, state: 'PASS' }),
    ], ['status']));
    for (const group of ['running', 'review', 'decide', 'integrate']) {
      cleanup();
      await mountApp('#/overview?mock=offline&keep=1');
      const card = qa(document, 'a[data-metric="' + group + '"]')[0];
      expect(card, '指标卡 ' + group).toBeTruthy();
      expect(clickKeepUrl(card), '无修饰键左键被应用拦下').toBe(true);
      await settle();
      const p = hashParts();
      expect(p.path).toBe('/tasks');
      expect(p.params.group).toBe(group);
      expect(p.params.mock).toBe('offline');
      expect(p.params.keep).toBe('1');
      expect(pressedGroups()).toEqual([group]);
    }
    expect(qa(document, 'a[data-metric="ended"]').length, '指标卡只有前四个分组').toBe(0);
  }, 60000);
});

describe('TRANS 分组地址夹具列表', () => {
  it('T009 指标卡的四个地址选中对应胶囊、列表恰是该组、计数 1/2/1/1；ended 没有指标卡，只查解析与计数', async () => {
    await mountApp('#/overview?mock=data');
    const want: Record<string, string[]> = {
      running: ['ui-readonly-api'], review: ['logs-cat', 'plugin-verify-json'],
      decide: ['secret-check-json'], integrate: ['status-live-json'],
    };
    for (const group of ['running', 'review', 'decide', 'integrate']) {
      cleanup();
      await mountApp('#/overview?mock=data');
      const card = qa(document, 'a[data-metric="' + group + '"]')[0];
      expect(card, '指标卡 ' + group).toBeTruthy();
      expect(clickKeepUrl(card), '无修饰键左键被应用拦下').toBe(true);
      await settle();
      const p = hashParts();
      expect(p.path, group).toBe('/tasks');
      expect(p.params.group).toBe(group);
      expect(p.params.mock).toBe('data');
      expect(pressedGroups()).toEqual([group]);
      expect(options().map(optionTask)).toEqual(want[group]);
      expect(textOf(capsuleByGroup(group)).replace(/[^\d]/g, '')).toBe(String(want[group].length));
    }
    expect(qa(document, 'a[data-metric="ended"]').length, '指标卡只有前四个分组').toBe(0);
    cleanup();
    await mountApp('#/tasks?group=ended&mock=data');
    expect(pressedGroups()).toEqual(['ended']);
    expect(textOf(capsuleByGroup('ended')).replace(/[^\d]/g, '')).toBe('1');
    expect(options().map(optionTask)).toEqual(['roles-dry-run']);
  }, 60000);
});

describe('D12 不可信内容', () => {
  it('任务名、失败分类里的探针：DOM 里没有 script/img，文字原样出现，地址里的 task 经过编码', async () => {
    set('getStatus', env([{
      attempt: '<script>alert(1)</script>/attempt-001', task_id: '<script>alert(1)</script>', plan_version: 1,
      attempt_no: 1, state: 'NEEDS_REVIEW', started: true, exit_code: null, wall_seconds: 61, events_ok: true,
      violations: 0, checks: '8/8', check_mode: 'fresh', verdict: null, failure_class: 'FAILED-<i>x</i>',
      human_minutes: null, tokens: 1000, cost: null, cost_status: 'unknown',
    }], ['status']));
    await mountApp('#/tasks');
    expect(qa(document.body, 'script, img').length, '页面上没有 script、img 元素').toBe(0);
    expect(pageText()).toContain('<script>alert(1)</script>');
    fireEvent.click(options()[0]);
    await settle();
    expect(window.location.hash, '地址里的 task 经过编码').toContain('%3Cscript%3Ealert(1)%3C%2Fscript%3E');
    const table = attemptTable('<script>alert(1)</script>');
    expect(table, '右栏表照常渲染').toBeTruthy();
    expect(cellText(table, 0, '失败分类')).toBe('FAILED-<i>x</i>');
    expect(qa(document.body, 'script, img, i').length, '失败分类只按文本显示').toBe(0);
    expect(cellText(table, 0, '用时')).toMatch(/^1 分 1 秒$/);
  });

  it('查看器、差异视图、跟随里没有 ESC 字符与 [31m；页签面板里没有 a 元素', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    set('readFile', (task: string, attempt: string, path: string) => {
      const probe = '第一行 \u001b[31mRED\u001b[0m <script>alert(1)</script>';
      const cmd = ['logs', 'cat', task + '/' + attempt, path];
      if (path === 'candidate.patch') {
        return Promise.resolve(env({ path, mode: 'text', done: true, next_cursor: null,
          text: 'diff --git a/src/p.ts b/src/p.ts\n--- a/src/p.ts\n+++ b/src/p.ts\n@@ -1 +1 @@\n-a\n+b ' + probe + '\n' }, cmd));
      }
      if (path === 'events.jsonl') {
        return Promise.resolve(env({ path, mode: 'jsonl', done: true, next_cursor: null,
          lines: [{ n: 1, text: probe }] }, cmd));
      }
      return Promise.resolve(env({ path, mode: 'text', done: true, next_cursor: null, text: probe }, cmd));
    });
    for (const [tab, root] of [['执行报告', '.tt-viewer'], ['补丁', '.tt-diff'], ['事件', '.tt-log']]) {
      cleanup();
      const q = tab === '执行报告' ? 'report' : tab === '补丁' ? 'patch' : 'events';
      await mountApp('#/tasks/logs-cat/attempt-002?tab=' + q + '&mock=data');
      const el = qa(panel(), root)[0];
      expect(el, tab + ' 的容器').toBeTruthy();
      const t = textOf(el);
      expect(t, tab + ' 原样显示探针').toContain('<script>alert(1)</script>');
      expect(t.indexOf('\u001b'), tab + ' 没有 ESC 字符').toBe(-1);
      expect(t.indexOf('[31m'), tab + ' 没有 [31m').toBe(-1);
      expect(qa(panel(), 'script, img').length, tab + ' 没有 script/img').toBe(0);
      expect(qa(panel(), 'a').length, tab + ' 面板里没有 a 元素').toBe(0);
    }
  });
});

describe('D12 写入口与白名单', () => {
  const BUTTON_OK = ['刷新', '重试', '继续加载', '从头读取', '回到底部', '行号', '换行', '查看全文', '统一', '分屏',
    '复制已显示的文字', '复制命令', '折叠', '展开', '关闭提示'];
  function allowed(b: any): boolean {
    if (b.disabled) return true;
    if ((b.className || '').indexOf('tt-diff__file-item') >= 0) return true;
    const role = b.getAttribute('role');
    if (role === 'tab' || role === 'option' || role === 'radio') return true;
    if (b.hasAttribute('aria-pressed')) return true;
    return BUTTON_OK.indexOf(b.getAttribute('aria-label') || textOf(b)) >= 0;
  }
  function problems(rootEl: any, label: string): string[] {
    const out: string[] = [];
    qa(rootEl, 'button').forEach((b) => {
      const name = b.getAttribute('role') === 'tab' || b.getAttribute('role') === 'option'
        || b.getAttribute('role') === 'radio' || b.hasAttribute('aria-pressed')
        ? '(role:' + (b.getAttribute('role') || 'capsule') + ')'
        : (b.getAttribute('aria-label') || textOf(b));
      if (b.disabled) {
        if (['在资源管理器中显示', '重新连接'].indexOf(textOf(b)) < 0) {
          out.push(label + '：不在写入口清单里的禁用按钮「' + textOf(b) + '」');
        }
        return;
      }
      if (!allowed(b)) out.push(label + '：可用按钮「' + name + '」不在白名单里');
      if (!b.hasAttribute('aria-pressed') && ['派遣', '验收', '合并', '试跑'].some((w) => textOf(b).indexOf(w) >= 0)) {
        out.push(label + '：出现写操作字样的按钮「' + textOf(b) + '」');
      }
    });
    qa(rootEl, 'a[href]').forEach((a) => {
      const inCrumb = a.closest('nav[aria-label="面包屑"]') !== null;
      if (!inCrumb) out.push(label + '：不在白名单里的链接「' + textOf(a) + '」');
    });
    return out;
  }

  it('两页逐个页签：可用按钮与链接只在白名单里；没有派遣、验收、合并、试跑按钮', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    const found: string[] = [];
    const scope = () => document.querySelector('main');
    for (const mock of ['data', 'offline']) {
      await mountApp('#/tasks?mock=' + mock);
      found.push(...problems(scope(), '列表 ' + mock));
      cleanup();
      await mountApp('#/tasks/logs-cat/attempt-002?mock=' + mock);
      for (const label of ['摘要', '补丁', '检查', '执行报告', '事件', '全部文件']) {
        fireEvent.click(tabByLabel(label));
        await settle();
        found.push(...problems(scope(), '详情 ' + mock + ' ' + label));
        if (label === '检查' || label === '全部文件') {
          const table = qa(panel(), 'table')[0];
          if (table) {
            fireEvent.click(tableRows(table)[0]);
            await settle();
            found.push(...problems(scope(), '详情 ' + mock + ' ' + label + ' 打开文件'));
          }
        }
      }
      cleanup();
    }
    expect(found).toEqual([]);
  }, 60000);

  it('每个「在资源管理器中显示」都 disabled；两页上没有别的写入口按钮', async () => {
    set('getStatus', env([logsCatRow()], ['status']));
    set('getAttempt', attemptEnv());
    await mountApp('#/tasks/logs-cat/attempt-002?tab=files&mock=data');
    const table = qa(panel(), 'table[aria-label="证据文件"]')[0];
    const reveals = qa(table, 'button').filter((b) => textOf(b) === '在资源管理器中显示');
    expect(reveals.length).toBe(5);
    reveals.forEach((b) => expect(b.disabled).toBe(true));
    const others = qa(document.querySelector('main'), 'button')
      .filter((b) => b.disabled && textOf(b) !== '在资源管理器中显示');
    expect(others.map(textOf), '两页上没有别的写入口').toEqual([]);
  });
});
"""

# ---- nonet：P11 运行时不连服务（长期） ----
PROBE_NONET = PRELUDE + r"""
const NAMES = ['fe' + 'tch', 'XMLHttp' + 'Request', 'Event' + 'Source', 'Web' + 'Socket'];
const calls: string[] = [];
const saved: Array<[any, string, PropertyDescriptor | undefined]> = [];

function stubAt(target: any, name: string, value: any) {
  saved.push([target, name, Object.getOwnPropertyDescriptor(target, name)]);
  Object.defineProperty(target, name, { value, configurable: true, writable: true });
}
function install() {
  calls.length = 0;
  for (const n of NAMES) {
    const stub: any = function (this: any) {
      calls.push(n);
      return n === NAMES[0] ? new Promise(() => {}) : undefined;
    };
    ['addEventListener', 'removeEventListener', 'close', 'open', 'send', 'setRequestHeader', 'abort'].forEach((m) => {
      stub.prototype[m] = () => {};
    });
    stubAt(globalThis, n, stub);
    if (typeof window !== 'undefined' && (window as any) !== globalThis) stubAt(window, n, stub);
  }
  stubAt(navigator, 'sendBeacon', () => {
    calls.push('sendBeacon');
    return false;
  });
}
function restore() {
  while (saved.length > 0) {
    const [target, name, desc] = saved.pop() as [any, string, PropertyDescriptor | undefined];
    if (desc) Object.defineProperty(target, name, desc);
    else delete target[name];
  }
}

describe('P11 运行时不连服务', () => {
  it('自检：替身真的会记录调用（探针不是空转）', () => {
    install();
    try {
      (globalThis as any)[NAMES[0]]('x');
      new (globalThis as any)[NAMES[1]]();
      new (globalThis as any)[NAMES[2]]('x');
      new (globalThis as any)[NAMES[3]]('ws://x');
      navigator.sendBeacon('x');
      expect(calls.length).toBe(5);
    } finally {
      restore();
    }
  });

  it('逐个 ?mock= 取值渲染两页（含刷新、重试、胶囊、页签、搜索、行进详情），四个网络接口与 sendBeacon 的调用次数都是 0', async () => {
    install();
    vi.useFakeTimers();
    try {
      for (const mock of [null, 'data', 'loading', 'empty', 'error', 'offline']) {
        const q = mock ? '?mock=' + mock : '';
        let r = await mountApp('#/tasks' + q);
        await settle();
        advance(1500);
        for (const label of ['刷新', '重试']) {
          const b = btn(document.body, label);
          if (b && !b.disabled) {
            fireEvent.click(b);
            await settle();
          }
        }
        const cap = capsuleByGroup('review');
        if (cap) {
          fireEvent.click(cap);
          await settle();
        }
        const search = qa(document, 'input[type="search"]')[0];
        if (search) {
          fireEvent.change(search, { target: { value: 'logs' } });
          await settle();
        }
        const table = attemptTable('logs-cat');
        if (table) {
          fireEvent.click(tableRows(table)[0]);
          await settle();
          advance(1000);
          for (const label of ['补丁', '检查', '执行报告', '事件', '全部文件', '摘要']) {
            const t = tabByLabel(label);
            if (t) {
              fireEvent.click(t);
              await settle();
            }
          }
        }
        r.unmount();
        expect(calls, '#/tasks ' + mock + ' 之后调用过网络接口').toEqual([]);
        r = await mountApp('#/tasks/logs-cat/attempt-002' + q);
        await settle();
        advance(1500);
        const refresh = btn(document.body, '刷新');
        if (refresh && !refresh.disabled) {
          fireEvent.click(refresh);
          await settle();
        }
        r.unmount();
        expect(calls, '#/tasks/logs-cat/attempt-002 ' + mock + ' 之后调用过网络接口').toEqual([]);
      }
    } finally {
      restore();
      vi.useRealTimers();
    }
  }, 60000);
});
"""

PROBE_SPECS = {
    "logic": (PROBE_LOGIC, [f"{TASKS_REL}/TaskListView.tsx", f"{TASKS_REL}/AttemptDetailView.tsx",
                            f"{PAGE_FILE}"]),
    "data": (PROBE_DATA, [f"{TASKS_REL}/tasks-data.ts"] + [f"{MOCK_REL}/{n}" for n in MOCK_FILES]),
    "list": (PROBE_LIST, [f"{TASKS_REL}/TaskListView.tsx", f"{TASKS_REL}/tasks-list.css", f"{PAGE_FILE}"]),
    "detail": (PROBE_DETAIL, [f"{TASKS_REL}/AttemptDetailView.tsx", f"{TASKS_REL}/tasks-detail.css", f"{PAGE_FILE}"]),
    "tabs": (PROBE_TABS, [f"{TASKS_REL}/AttemptDetailView.tsx", f"{TASKS_REL}/tab-Summary.tsx", f"{TASKS_REL}/tab-Patch.tsx",
                          f"{TASKS_REL}/tab-Checks.tsx", f"{TASKS_REL}/tab-Report.tsx", f"{TASKS_REL}/tab-Events.tsx",
                          f"{TASKS_REL}/tab-Files.tsx", f"{TASKS_REL}/common-FileReader.tsx", f"{TASKS_REL}/tasks-tabs.css",
                          f"{MOCK_REL}/tasks-files.ts", f"{MOCK_REL}/tasks-attempts.ts", f"{MOCK_REL}/tasks-live.ts"]),
    "app": (PROBE_APP, [f"{PAGE_FILE}"] + [f"{TASKS_REL}/{n}" for n in TASKS_FILES] + [f"{MOCK_REL}/{n}" for n in MOCK_FILES]),
    "nonet": (PROBE_NONET, [f"{PAGE_FILE}", f"{TASKS_REL}/TaskListView.tsx", f"{TASKS_REL}/AttemptDetailView.tsx"]),
}
PROBE_ORDER = ("logic", "data", "list", "detail", "tabs", "app", "nonet")


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
    return PROBE_SPECS[key][0]


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
        self.probe_errors = {}
        self.probe_unparsed = {}
        self.probe_groups = {}
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
           "src/styles/tokens.css", "src/styles/fonts.css", "src/styles/base.css", "src/main.tsx", "src/App.tsx",
           "src/App.css", "src/api.ts", "src/shell/PageFrame.tsx", "src/shell/DisabledAction.tsx",
           "src/shell/router.ts", "src/shell/attemptGroups.ts", "src/mock/scenario.ts", "src/mock/shell.ts",
           "src/mock/status.json", "src/mock/attempt.json", "src/mock/file-events.json", "src/mock/file-executor-report.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not any((REPO_ROOT / rel).is_file() for rel in NEW_SOURCE_FILES if rel.endswith((".ts", ".tsx"))):
        pipe.reason = ("候选里还没有 src/pages/tasks/ 与 src/mock/tasks-*.ts 的任何源码文件（基线），没有东西可测，未调用 npm；"
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
                name = f"probe-t011-{uid}-{key}.test.ts"
                result_name = f"result-t011-{uid}-{key}.json"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                result_path = probe_dir / result_name
                written += [path, result_path]
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
# 静态断言（S 系列）
# ---------------------------------------------------------------------------

def test_s1_files_in_place():
    """S1 / D14（合同 Scope、§1 文件边界）：tasks/ 下 20 个新文件与 src/mock 下 3 份夹具都在，tasks/ 下不多不少、不分子目录、
    没有 *Page.tsx；TasksPage.tsx 用 PageFrame 并从 ./tasks/ 引入视图、不再有占位行；src/mock 仍恰 14 份 JSON、src/pages 顶层仍恰 9 个 *Page.tsx。"""
    need_new_sources()
    stray_dirs = [p.name for p in TASKS.iterdir() if p.is_dir()]
    assert not stray_dirs, f"src/pages/tasks/ 下不分子目录：{stray_dirs}"
    got = sorted(p.name for p in TASKS.iterdir() if p.is_file() and p.name not in TASKS_MERGED)  # T014 并走的三份在不在都行
    assert got == sorted(TASKS_FILES), f"src/pages/tasks/ 应恰是合同清单里的 17 个文件（T014 并走的三份不算），多出 {sorted(set(got) - set(TASKS_FILES))}，缺少 {sorted(set(TASKS_FILES) - set(got))}"
    page_like = [n for n in got if n.endswith("Page.tsx")]
    assert not page_like, f"tasks/ 里的文件名不以 Page.tsx 结尾：{page_like}"

    text = _read(need_file(PAGE_FILE))
    if "PageFrame" not in text:
        raise AssertionError("TasksPage.tsx 应使用 PageFrame（两页五态）")
    if not re.search(r"from\s+['\"]\./tasks/", text):
        raise AssertionError("TasksPage.tsx 应从 ./tasks/ 引入视图")
    if "夹具数据已读到" in text:
        raise AssertionError("TasksPage.tsx 仍是占位页（含「夹具数据已读到」）")
    if not re.search(r"export\s+default\s+function\b|export\s+default\b", text):
        raise AssertionError("TasksPage.tsx 没有默认导出（routes.ts 按默认导出引入）")

    jsons = sorted(p.stem for p in (SRC / "mock").glob("*.json"))
    assert jsons == sorted(BASELINE_JSON), f"src/mock/ 应恰有基线的 14 份 JSON，实际 {jsons}"
    ts = {p.name for p in (SRC / "mock").glob("*.ts")}
    assert set(BASELINE_MOCK_TS + MOCK_FILES) <= ts, f"src/mock/ 的 .ts 应含基线 3 份和本片 3 份夹具，实际 {sorted(ts)}"
    pages = sorted(p.name for p in (SRC / "pages").glob("*Page.tsx"))
    assert pages == sorted(BASELINE_PAGES), f"src/pages/ 顶层应恰有 9 个 *Page.tsx，实际 {pages}"


def test_s2_source_scan():
    """S2 / D13（合同公共约定与 §1.3）：本片 ts、tsx、css 与 src/mock/tasks-*.ts——注释与夹具字符串也算——不出现四个网络词、
    T007 禁用词、字体词、ServerIcon；不渲染 role=status；不用 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver；
    没有井号加十六进制与颜色函数；网络词与注入词对整个 src 再扫一遍。"""
    need_new_sources()
    problems = []
    for path in slice_code_files() + slice_css_files() + [REPO_ROOT / PAGE_FILE]:
        problems += source_guard_problems(label_of(path), _read(path))
    problems += w4_pitfall_problems(slice_code_files() + slice_css_files())
    for path in src_ts_files():
        raw = _read(path)
        for word in NET_WORDS + SINK_WORDS:
            if word_hit(raw, word):
                problems.append(f"{label_of(path)} 出现禁用词 {word}")
    fail_if(problems, "源码与夹具扫描")


def test_s3_no_inline_style_and_no_state_literals():
    """S3 / D13（合同公共约定、§1）：本片源码与 TasksPage.tsx 不写内联 style；分组只来自 attemptGroups，不另写状态到分组的映射。"""
    need_new_sources()
    problems = []
    for path in slice_code_files() + [REPO_ROOT / PAGE_FILE]:
        code = strip_ts_comments(_read(path))
        if re.search(r"""\bstyle\s*=\s*(?:\{|["'])""", code):
            problems.append(f"{label_of(path)}：不写内联 style")
    problems += state_literal_problems(slice_code_files())
    fail_if(problems, "内联 style 与状态到分组映射")


def test_s4_groups_match_ui_doc():
    """S4 / D01（合同 §5.5 S5）：门禁自己解析 UI 文档 3.4 的表格——17 个状态、五组的状态清单——逐个核对 T009 的 GROUP_OF_STATE
    （PREPARED 与未知状态不在任何组），并核对本片 tasks-groups.ts 的标签、导入来源与“不另写映射”。"""
    fail_if(attempt_groups_problems(), "attemptGroups.ts 与 UI 文档 3.4")
    need_new_sources()
    fail_if(tasks_groups_problems(), "tasks-groups.ts")


def test_s5_new_icons_match_canvas():
    """S5 / D13（合同 §5.5 S6、K17）：FileTextIcon 写在本片 tasks-icons.tsx（T014 之后在 src/icons/index.tsx），路径等于详情页画布对应行；SearchIcon 用 src/icons/index.tsx
    的导出（路径等于任务页画布对应行），本片不重写、TaskListView 从 icons 导入。"""
    fail_if(icons_problems(), "新图标")


def test_s6_css_values():
    """S6 / D13（合同 §8 样式取值）：三份 CSS 合并后逐条求值——两栏、左栏、左栏头、搜索框、胶囊（按下/平时/间距）、任务项（选中/竖条/悬停）、
    右栏头、attempt 表（无框只留上边框、最小宽 1040）、下一步区、面包屑条（含窄内容区）、页头、dl、页签列表、摘要、检查与文件表、min-width: 0；
    grid 里不写裸的 1fr。"""
    need_new_sources()
    fail_if(css_value_problems(), "tasks 样式取值")
    problems = []
    for key in CSS_FILES:
        problems += bare_onefr_problems(css_text(key), CSS_FILES[key].rsplit("/", 1)[-1])
    fail_if(problems, "grid 宽度")


def test_s7_css_tokens_px_comments_and_w4():
    """S7 / D13（合同公共约定）：三份 CSS 的层级、圆角、阴影、字体只用 --tt-* 令牌；除 0 与 1px 外的 px 字面量同一行带出处注释；
    样式里不写死颜色与颜色函数。"""
    need_new_sources()
    problems = []
    for key, rel in CSS_FILES.items():
        raw = _read(REPO_ROOT / rel)
        problems += token_only_problems(rel.rsplit("/", 1)[-1], raw)
        problems += px_literal_problems(rel.rsplit("/", 1)[-1], raw)
    problems += w4_pitfall_problems(slice_css_files())
    fail_if(problems, "令牌、px 注释与 W4")


def test_s8_css_files_are_imported_into_app():
    """S8 / D13 / D01（终审 B2）：三份 CSS 都被应用用上——从 src/main.tsx 顺着 import 能到达每一份（光写 CSS 文件、没人 import，页面不套用它）。"""
    need_new_sources()
    fail_if(css_wiring_problems(src_files_by_rel(), list(CSS_FILES.values())), "样式表接线")


def test_d14_executor_tests_in_place():
    """D14（合同“执行端测试”）：八份 tasks-* 测试都在（logic、data、list、detail、tabs、app、css、static），各至少一条用例，不出现 skip、only、todo。"""
    fail_if(executor_test_problems(), "执行端测试文件")


# ---------------------------------------------------------------------------
# P 系列：流水线断言
# ---------------------------------------------------------------------------

def test_p1_d14_pipeline_steps_pass(pipeline):
    """P1 / D14（守卫）：npm ci、npm run build、npm test、npm run check:contract（W4）都退出 0；npm test 有通过的用例，没有失败、跳过、待办。"""
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    step = pipeline.steps["npm test"]
    out = step.out
    assert re.search(r"Tests\s+(?:.*\|\s*)?\d+ passed", out), f"npm test 输出里没有 'Tests … N passed'：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", out), f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert re.search(r"Test Files\s+\d+ passed", out) and not re.search(r"Test Files\s+.*\bfailed\b", out), \
        f"npm test 的 Test Files 行异常：\n{step.tail}"


def test_d13_css_classes_in_built_bundle(pipeline):
    """D13 / D01（终审 B2）：npm run build 之后 dist/assets/*.css 含三份 CSS 各自一个独有的类选择器（从文件里解析，不写死）。"""
    assert_step_ok(pipeline, "npm run build")
    assets = sorted((WEB / "dist" / "assets").glob("*.css"))
    assert assets, f"{WEB_REL}/dist/assets 下没有 CSS 产物"
    built = "\n".join(_read(path) for path in assets)
    fail_if(built_css_problems(built, {key: css_text(key) for key in CSS_FILES}), "构建产物里的样式表")


def test_d01_probe_groups_and_address(pipeline):
    """D01（长期）：logic 探针——五颗胶囊的顺序、data-group 与文字、aria-pressed；PREPARED 不进任何组；点胶囊只改受管的 group 参数
    （mock 与其他参数保留、值为缺省时删掉、不加历史项、不重挂载）；多值与重复 group 参数取并集、未知 ID 忽略；计数按最新 attempt 且不受搜索选中影响；
    地址里的任务经编码、不在筛选结果里时选第一个且不改写地址；tab 六值与缺省；详情路径取前两段；点行进详情写缺省值并保留 mock。"""
    assert_probe_group(pipeline, "logic", "D01 分组与地址")


def test_d01_probe_selection_and_cross_view(pipeline):
    """D01（长期）：logic 探针——选中写进地址（replace，mock 保留，不加历史项）；跨视图链接只带 mock，面包屑回列表不过滤、回选中任务；
    无修饰键左键被应用拦下并同步换路由，带修饰键走默认行为。"""
    assert_probe_group(pipeline, "logic", "D01 选中与筛选")


def test_d02_probe_data_layer(pipeline):
    """D02（长期）：data 探针——五个开关下 readAttempt、readAttemptFile 对 api.ts 数据的包装；error 不被夹具盖住；
    loading 一直挂起；command 沿用 api.ts 的；每次都深拷贝；loadAttemptDetail 的并行、失败顺序、row 与 attemptEnv。"""
    assert_probe_group(pipeline, "data", "D02 数据层五个开关")


def test_transitional_data_probe_fixture_fallback(pipeline):
    """接本机服务那一片推翻（tasks-data 的本片夹具兜底去掉，改成直连服务）

    data 探针：api.ts 报缺时才取 src/mock/tasks-*.ts 的运行中 attempt、补丁、检查日志、事件第 2 页与运行中事件第 1 页；offline 与 empty 下照样取夹具。"""
    assert_probe_group(pipeline, "data", "TRANS 数据层取本片夹具")


def test_d03_probe_list_view(pipeline):
    """D03（长期）：list 探针——页面框架与空态；两栏与搜索框（隐藏标签、占位、SearchIcon 16）；任务列表（listbox/option、顺序、两行、StatusTag sm、
    roving tabindex）与方向键、Home/End、点击选中；搜索过滤与无匹配；attempt 表 11 列表头、行高 40、倒序与 11 列取值（版本/用时/检查/结论/失败分类/
    越界 danger/token/费用/思考档位）；点行与 Enter 打开详情；下一步四种规则与复制三种结果；右栏 h2 与计数。"""
    assert_probe_group(pipeline, "list", "D03 列表视图")


def test_d05_probe_detail_header(pipeline):
    """D05（长期）：detail 探针——面包屑三项与 href（只带 mock）、h1 规则（Q5）、状态标签与思考档位、dl 元信息各项与「—」、状态时间的本地时间与
    UTC 原值 title、下一步四种文字与命令及不显示的情形、复制三种结果。"""
    assert_probe_group(pipeline, "detail", "D05 详情页头")


def test_d06_probe_detail_states(pipeline):
    """D06（长期）：detail 探针——读取中（骨架 300ms）、有数据、找不到（标题/说明/h1 任务/地址不变）、出错（getStatus 失败）、断线（横幅/可能已过期/
    data-stale）；?mock=empty 时 logs-cat/attempt-002 照常显示而取自 status 的字段写「—」；status 有行而 logs show 读不到时页头照常、三个页签行内出错。"""
    assert_probe_group(pipeline, "detail", "D06 详情五态")


def test_d07_probe_tabs_address(pipeline):
    """D07（长期）：tabs 探针——六个页签与 aria-label；挂载读 ?tab=；点页签与方向键之后 tab 变了、mock 与其他参数不变、路径不变、节点不变（不重挂载）、
    焦点在页签上；手改地址并派发 hashchange 之后页签跟着变。"""
    assert_probe_group(pipeline, "tabs", "D07 页签与地址")


def test_d08_probe_summary_report(pipeline):
    """D08（长期）：tabs 探针——摘要的文件行（FileTextIcon 14、summary.md、大小、安全 Markdown 说明）与 tt-md 内容原样；截断提示与 [查看全文]；
    没有摘要时的文字；onOpenLink 的第二阶段接入提示；执行报告的 warning 提示条与文本查看器。"""
    assert_probe_group(pipeline, "tabs", "D08 摘要与执行报告")


def test_d09_probe_patch_checks(pipeline):
    """D09（长期）：tabs 探针——补丁的 DiffView 与 title、ANSI 与标签只按文本、没读完时 [继续加载] 带游标；检查的汇总、日志表与整行打开、说明行、
    checks 为「-」与没有检查日志两种文字。"""
    assert_probe_group(pipeline, "tabs", "D09 补丁与检查")


def test_d10_probe_events(pipeline):
    """D10（长期）：tabs 探针——日志跟随的容器与过滤框；已结束时跟随禁用与原因文字。"""
    assert_probe_group(pipeline, "tabs", "D10 事件")


def test_transitional_events_probe_follow(pipeline):
    """接本机服务那一片推翻（tasks-live 的跟随模拟换成 subscribeEvents）

    tabs 探针：运行中的 attempt 用假计时器每 1000ms 多一行、到上限停、切走页签不再追加、卸载后没有挂起的计时器（夹具 ui-readonly-api/attempt-001）。"""
    assert_probe_group(pipeline, "tabs", "TRANS 事件跟随模拟")


def test_d11_probe_files(pipeline):
    """D11（长期）：tabs 探针——证据文件表三列与大小格式、每行「在资源管理器中显示」禁用、整行按段打开（jsonl 的隐藏行占位）、caption 的跳过链接数、悬停 400ms 出「第二阶段接入」。"""
    assert_probe_group(pipeline, "tabs", "D11 全部文件")


def test_transitional_app_probe_five_states(pipeline):
    """接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据）

    app 探针：经 ?mock= 渲染 App 两页的五态（列表与详情各自 loading/data/empty/error/offline、骨架 300ms、整页恰一个 data-page-state）。"""
    assert_probe_group(pipeline, "app", "TRANS 任务页 App 级五态")


def test_transitional_app_probe_fixture_values(pipeline):
    """接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据；tasks-data 的夹具兜底去掉）

    app 探针：夹具下的具体值——列表 6 个任务、胶囊计数 1/2/1/1/1、缺省选中 ui-readonly-api、logs-cat 两行倒序与 token 千分位；详情页头与全部文件页签 5 个禁用入口；补丁页签取自本片夹具。"""
    assert_probe_group(pipeline, "app", "TRANS 夹具下的具体值")


def test_p6_probe_group_addresses(pipeline):
    """P6（长期）：app 探针——点 T009 指标卡同步换路由到 #/tasks?group=<组>、对应胶囊按下、mock 与其他参数保留；指标卡只有前四个分组（注入数据，不依赖夹具）。"""
    assert_probe_group(pipeline, "app", "P6 分组地址导航")


def test_transitional_group_addresses_fixture_lists(pipeline):
    """接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据）

    app 探针：夹具下 T009 指标卡的四个地址选中对应胶囊、列表恰是该组、计数 1/2/1/1；ended 没有指标卡，只查 group=ended 的解析与胶囊计数。"""
    assert_probe_group(pipeline, "app", "TRANS 分组地址夹具列表")


def test_d12_probe_untrusted_content(pipeline):
    """D12（长期）：app 探针——任务名、失败分类、摘要、补丁、检查日志、执行报告、事件里的探针：页面上没有 script、img 元素，页签面板里没有 a 元素，
    文字原样出现，查看器、差异视图、跟随里没有 ESC 字符与 [31m，地址里的 task 经过编码。"""
    assert_probe_group(pipeline, "app", "D12 不可信内容")


def test_d12_probe_write_entries(pipeline):
    """D12（长期）：app 探针——两页逐个页签：可用按钮与链接只在白名单里，没有派遣、验收、合并、试跑字样的按钮，每个「在资源管理器中显示」都 disabled，
    两页上没有别的写入口。"""
    assert_probe_group(pipeline, "app", "D12 写入口与白名单")


def test_p11_probe_no_network(pipeline):
    """P11 / D12（守卫）：nonet 探针——逐个 ?mock= 取值渲染两页，含刷新、重试、分组胶囊、搜索、行进详情与逐个页签，fetch、XMLHttpRequest、EventSource、
    WebSocket、sendBeacon 的调用次数都是 0。"""
    assert_probe_group(pipeline, "nonet", "P11 运行时不连服务")


def test_p12_d14_worktree_unchanged_by_pipeline(pipeline):
    """P12 / D14（守卫）：流水线与探针前后 git status 相同；package.json、锁文件、index.html、vite.config.ts、tsconfig.json、tokens.css、fonts.css、
    base.css、main.tsx、App.tsx、App.css、api.ts、PageFrame、DisabledAction、router、attemptGroups、scenario、shell 与四份夹具 JSON 的摘要不变；
    gate-probe/ 没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"
    changed = sorted(n for n in WATCHED if pipeline.digests_before.get(n) != pipeline.digests_after.get(n))
    assert not changed, f"流水线改动了不该动的文件：{changed}"
    assert not pipeline.gate_probe_left, "desktop/web/gate-probe/ 在探针结束后没有清掉"


# ---------------------------------------------------------------------------
# 门禁自检（不依赖候选）：检查函数放得过正确样本，拦得住常见错误
# ---------------------------------------------------------------------------

GOOD_CSS = """
/* 任务列表样式样本：左栏 320（任务页画布 :332） */
.tasks-cols { display: flex; gap: var(--tt-space-4); align-items: flex-start; }
.tasks-cols__left { width: 320px; flex: none; background: var(--tt-surface-1); border: 1px solid var(--tt-border); border-radius: var(--tt-radius-lg); }
.tasks-cols__right { flex: 1; min-width: 0; }
.tasks-search { height: 32px; padding-left: var(--tt-space-8); padding-right: var(--tt-space-2); border: 1px solid var(--tt-border-strong); border-radius: var(--tt-radius-md); font: var(--tt-text-md); }
.tasks-chip { height: 28px; padding-left: var(--tt-space-2); padding-right: var(--tt-space-2); border-radius: var(--tt-radius-full); font: var(--tt-text-sm-medium); background: var(--tt-surface-1); border: 1px solid var(--tt-border-strong); color: var(--tt-text-2); }
.tasks-chips { display: flex; gap: var(--tt-space-1); }
.tasks-chip[aria-pressed="true"] { background: var(--tt-surface-selected); border: 1px solid var(--tt-primary); color: var(--tt-text-1); }
.tasks-item { min-height: 52px; padding: var(--tt-space-2) var(--tt-space-3); border-bottom: 1px solid var(--tt-border); }
.tasks-item[aria-selected="true"] { background: var(--tt-surface-selected); border-left: 2px solid var(--tt-primary); }
.tasks-item:hover { background: var(--tt-surface-3); }
.tasks-head { display: flex; flex-direction: column; gap: var(--tt-space-2); padding: var(--tt-space-3); }
.tasks-right-head { padding: var(--tt-space-3) var(--tt-space-4); }
.tasks-table .tt-table-wrap { border: 0; border-radius: 0; border-top: 1px solid var(--tt-border); }
.tasks-table-wrap { min-width: 1040px; }
.tasks-next { margin: var(--tt-space-4); }
.tasks-crumb { padding: var(--tt-space-5) var(--tt-space-6) 0; }
@container (max-width: 808px) { .tasks-crumb { padding: var(--tt-space-4); } }
.tasks-detail-head { display: flex; flex-wrap: wrap; gap: var(--tt-space-2); }
.tasks-detail dl { display: flex; flex-wrap: wrap; gap: var(--tt-space-0_5) var(--tt-space-3); }
.tasks-tabs__list { overflow-x: auto; }
.tasks-summary { max-width: 880px; padding: var(--tt-space-5) var(--tt-space-6); background: var(--tt-surface-1); border: 1px solid var(--tt-border); border-radius: var(--tt-radius-lg); }
.tasks-min-table { min-width: 560px; }
.tasks-danger { color: var(--tt-danger-text); }
.tasks-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
"""


def test_gate_selfcheck_css_checks(tmp_path):
    """自检：CSS 取值检查放过正确样本，拦得住改坏取值、裸 1fr、缺 px 注释、非令牌圆角/字体、W4 的十六进制与颜色函数。"""
    problems = group_problems(GOOD_CSS, "样本", ALL_SPECS)
    assert not problems, "正确样本应通过：\n" + "\n".join(problems[:10])
    bad_css = GOOD_CSS.replace("width: 320px", "width: 300px").replace("gap: var(--tt-space-4)", "gap: var(--tt-space-2)")
    assert group_problems(bad_css, "改坏", ALL_SPECS), "改坏左栏宽与两栏间距应被抓出"
    no_bar = GOOD_CSS.replace("border-left: 2px solid var(--tt-primary);", "")
    assert any("竖条" in p for p in group_problems(no_bar, "改坏", ALL_SPECS)), "去掉选中竖条应被抓出"
    assert bare_onefr_problems(".x { grid-template-columns: 1fr 1fr; }", "样本"), "裸 1fr 应被抓出"
    assert not bare_onefr_problems(".x { grid-template-columns: minmax(0, 1fr) auto; }", "样本")
    assert px_literal_problems("样本", ".a { width: 320px; }"), "px 没有出处注释应被抓出"
    assert not px_literal_problems("样本", ".a { width: 320px; /* 画布 :332 */ }")
    assert not px_literal_problems("样本", ".a { width: 0; height: 1px; }")
    assert token_only_problems("样本", ".a { border-radius: 6px; }"), "非令牌圆角应被抓出"
    assert token_only_problems("样本", ".a { font-size: 13px; }"), "非令牌字号应被抓出"
    assert not token_only_problems("样本", ".a { font: var(--tt-text-sm); border-radius: var(--tt-radius-md); }")
    assert danger_classes(GOOD_CSS) == {"tasks-danger"}
    clean_css = tmp_path / "clean.css"
    clean_css.write_text(".a { color: var(--tt-text-1); }\n", encoding="utf-8")
    assert w4_pitfall_problems([clean_css]) == []
    hexed = tmp_path / "hexed.css"
    hexed.write_text(".a { color: #FCE4E4; }\n", encoding="utf-8")
    assert any("十六进制" in p for p in w4_pitfall_problems([hexed])), "十六进制颜色应被抓出"


def test_gate_selfcheck_source_guards(tmp_path):
    """自检：源码守卫放过干净样本，拦得住网络词、注入词、role=status、禁用接口、内联 style、状态到分组映射。"""
    clean = tmp_path / "clean.ts"
    clean.write_text("const a = 1; // 普通源码\nimport { groupOfState } from '../../shell/attemptGroups';\n", encoding="utf-8")
    assert source_guard_problems("干净", _read(clean)) == []
    for word, sample in (
        ("fetch", "const f = () => window.fetch('/x');"),
        ("XMLHttpRequest", "const x = new XMLHttpRequest();"),
        ("innerHTML", "el.innerHTML = 'x';"),
        ("eval(", "eval('1');"),
        ("ServerIcon", "const I = ServerIcon;"),
        (".woff", "src: url('/f.woff2');"),
    ):
        assert any(word in p for p in source_guard_problems("坏", sample)), f"{word} 应被抓出"
    assert any("role=status" in p for p in source_guard_problems("坏", "const r = { role: 'status' };"))
    assert any("matchMedia" in p for p in source_guard_problems("坏", "window.matchMedia('(max-width: 1px)');"))
    assert any("内联 style" in p for p in source_guard_problems("坏", "const s = <div style={{ color: 'red' }} />;"))
    assert source_guard_problems("坏", "const ok = style; const ref = useRef();") == []
    own_map = tmp_path / "own-map.ts"
    own_map.write_text("const MAP: Record<string, readonly string[]> = { running: ['PREPARING', 'RUNNING'] };\n", encoding="utf-8")
    assert any("状态到分组的映射" in p for p in state_literal_problems([own_map])), "自己写 group→状态 的分组映射应被抓出"
    rev_map = tmp_path / "rev-map.ts"
    rev_map.write_text("const M: Record<string, string> = { PREPARING: 'running', REVISE: 'ended' };\n", encoding="utf-8")
    assert any("状态到分组的映射" in p for p in state_literal_problems([rev_map])), "自己写 状态→group 的反向映射应被抓出"
    assert state_literal_problems([clean]) == []
    # 收窄（一审返工）：下一步规则的 state==='REVISE' 与夹具的 state:'RUNNING' 不再误报
    next_rule = tmp_path / "tasks-model.ts"
    next_rule.write_text(
        "import { groupOfState } from '../../shell/attemptGroups';\n"
        "export function nextStep(state: string) {\n"
        "  const g = groupOfState(state);\n"
        "  if (g === 'review') return { text: '等你验收', command: '/review-pi .agent/runs/x/y' };\n"
        "  if (g === 'integrate') return { text: '已通过', command: '/review-pi .agent/runs/x/y' };\n"
        "  if (g === 'decide') return { text: '要你决定' };\n"
        "  if (state === 'REVISE') return { text: '返工', command: '/plan-task x' };\n"
        "  return null;\n"
        "}\n",
        encoding="utf-8")
    assert state_literal_problems([next_rule]) == [], "下一步规则用 groupOfState + state==='REVISE'，不应误报"
    fixture = tmp_path / "tasks-attempts.ts"
    fixture.write_text("export const A1 = { task: 'ui-readonly-api', attempt: 'attempt-001', state: 'RUNNING', summary: null };\n", encoding="utf-8")
    assert state_literal_problems([fixture]) == [], "夹具里的 state:'RUNNING' 数据值不应误报"
    assert w4_pitfall_problems([clean]) == []


def _tasks_groups_problems_on(text):
    """把 tasks_groups_problems 的读取目标换成一个临时文件（自检用）。"""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tasks-groups.ts"
        path.write_text(text, encoding="utf-8")
        old = need_file

        def fake_need_file(rel, _p=path):
            return _p if rel.endswith("tasks-groups.ts") else old(rel)
        globals()["need_file"] = fake_need_file
        try:
            return tasks_groups_problems()
        finally:
            globals()["need_file"] = old


def test_gate_selfcheck_groups_parsing():
    """自检：UI 文档 3.4 解析出 17 个状态与五组；attemptGroups 的映射与文档一致；tasks-groups 的标签检查放过正确样本、拦得住改标签与自写映射。"""
    states, groups = ui_doc_states_and_groups()
    assert len(states) == 17, states
    assert set(groups) == {"运行中", "待验收", "要你决定", "待集成", "已结束"}, sorted(groups)
    assert groups["已结束"] == ["INTEGRATED", "REVISE", "ABANDONED", "SUPERSEDED", "PREPARE_FAILED"]
    assert "PREPARED" not in [s for codes in groups.values() for s in codes]
    assert attempt_groups_problems() == []
    good = "import { ATTEMPT_GROUPS, groupOfState } from '../../shell/attemptGroups';\n"
    good += "export const GROUP_LABEL: Record<string, string> = {\n"
    good += "  running: '运行中', review: '待验收', decide: '要你决定', integrate: '待集成', ended: '已结束',\n};\n"
    assert _tasks_groups_problems_on(good) == [], _tasks_groups_problems_on(good)
    bad_labels = good.replace("decide: '要你决定'", "decide: '要你定夺'")
    assert any("要你决定" in p for p in _tasks_groups_problems_on(bad_labels))
    no_import = good.replace("from '../../shell/attemptGroups'", "from './map'")
    assert any("attemptGroups" in p for p in _tasks_groups_problems_on(no_import))


def test_gate_selfcheck_icon_parsing():
    """自检：画布 svg 解析出搜索图标与文件图标的形状；图标形状检查放过正确样本、拦得住改路径。"""
    search_paths, search_circles = canvas_svg("docs/ui-design/pages/05-任务-Themis-Tally.html", 'placeholder="搜索任务…"')
    assert search_paths == ["m21 21-4.3-4.3"], search_paths
    assert search_circles == [{"cx": "11", "cy": "11", "r": "8"}], search_circles
    file_paths, file_circles = canvas_svg("docs/ui-design/pages/05-attempt-详情-Themis-Tally.html", ">summary.md</span>")
    assert len(file_paths) == 5 and file_circles == [], (file_paths, file_circles)
    good = ("import { Svg } from '../../icons/frame';\n"
            "export const FileTextIcon = (props: IconProps) => (\n  <Svg {...props}>\n"
            + "".join(f'    <path d="{p}" />\n' for p in file_paths)
            + "  </Svg>\n);\n")
    assert icon_shape_problems(good, "FileTextIcon", file_paths, [], "样本") == []
    wrong = good.replace(f'd="{file_paths[0]}"', 'd="M0 0h1v1H0z"')
    assert icon_shape_problems(wrong, "FileTextIcon", file_paths, [], "样本"), "改路径应被抓出"


def node_strips_types(node, tmp_path):
    """node --check 查 .mts 要靠 Node 的类型剥离（Node 24 默认开）；先拿一行带类型标注的样本探测，不可用就不做语法检查，不让自检误红。"""
    sample = tmp_path / "typed-sample.mts"
    sample.write_text("const x: number = 1;\nexport { x };\n", encoding="utf-8")
    try:
        proc = subprocess.run([node, "--check", str(sample)], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def js_bracket_problems(source):
    """粗查探针源码的括号：跳过字符串、模板字符串与注释，圆括号、方括号、花括号必须按顺序配对。不是完整的语法检查。"""
    problems, stack, i, n = [], [], 0, len(source)
    pairs = {")": "(", "]": "[", "}": "{"}
    line = 1
    while i < n:
        ch = source[i]
        if ch == "\n":
            line += 1
        if ch in "'\"`":
            quote = ch
            i += 1
            while i < n and source[i] != quote:
                if source[i] == "\\":
                    i += 1
                if i < n and source[i] == "\n":
                    line += 1
                    if quote != "`":
                        problems.append(f"第 {line - 1} 行字符串没有结束")
                        break
                i += 1
        elif ch == "\\":
            i += 2  # 正则字面量或转义里的反斜杠：连同下一个字符一起跳过
            continue
        elif source.startswith("//", i):
            while i < n and source[i] != "\n":
                i += 1
            continue
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            if end < 0:
                problems.append("块注释没有结束")
                break
            line += source.count("\n", i, end)
            i = end + 1
        elif ch in "([{":
            stack.append((ch, line))
        elif ch in ")]}":
            if not stack or stack[-1][0] != pairs[ch]:
                problems.append(f"第 {line} 行的 {ch} 配不上" + (f"（栈顶 {stack[-1]}）" if stack else ""))
                break
            stack.pop()
        i += 1
    if stack and not problems:
        problems.append(f"括号没有闭合：{stack[-3:]}")
    return problems


def test_gate_selfcheck_probe_templates(tmp_path):
    """自检：探针源码——每个 Python 用例点名的分组都存在且有用例；每个分组都有 Python 用例；没有 skip、only、todo；不含网络词与注入词；
    node --check 查语法。"""
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
        assert not re.search(r"\.(skip|only|todo)\b|\bxit\(|\bxdescribe\(", source), f"探针 {key} 里不许 skip、only、todo"
        for word in NET_WORDS + SINK_WORDS:
            assert word not in source, f"探针 {key} 自己不该含禁用词 {word}"
        assert not js_bracket_problems(source), f"探针 {key} 括号配对有问题：{js_bracket_problems(source)[:3]}"
        assert source.count("describe('") == len(probe_groups(source)), f"探针 {key} 的 describe 与分组数不符"
    node = shutil.which("node")
    if node and node_strips_types(node, tmp_path):
        for key in PROBE_ORDER:
            path = tmp_path / f"probe-{key}.mts"
            path.write_text(build_probe_source(key), encoding="utf-8", newline="\n")
            proc = subprocess.run([node, "--check", str(path)], capture_output=True, timeout=60)
            assert proc.returncode == 0, f"探针 {key} 语法有误：\n{proc.stderr.decode('utf-8', 'replace')[-1500:]}"


def test_gate_selfcheck_constants():
    """自检：常量与合同 Scope 对得上（文件数、CSS、执行端测试、预算）。"""
    assert len(TASKS_FILES) == len(set(TASKS_FILES)) == 17  # T014 并走三份
    assert len(TASKS_MERGED) == 3 and not set(TASKS_MERGED) & set(TASKS_FILES)
    assert len(MOCK_FILES) == 3
    assert len(NEW_SOURCE_FILES) == 20
    assert set(CSS_FILES.values()) <= set(NEW_SOURCE_FILES)
    assert len(EXECUTOR_TESTS) == 8
    assert [g for g, _ in GROUP_LABELS] == ["running", "review", "decide", "integrate", "ended"]
    assert set(TAB_IDS) == {"summary", "patch", "checks", "report", "events", "files"}
    assert len(ALL_STATE_CODES) == 17 and "PREPARED" in ALL_STATE_CODES
    assert PIPELINE_BUDGET < 600, "合同 V01 的超时是 600s，夹具预算要留余量给其余用例"
    assert max(STEP_CAPS.values()) <= PIPELINE_BUDGET
    assert BASE_SHA.startswith("5d57833")


def test_gate_selfcheck_executor_test_checker(tmp_path, monkeypatch):
    """自检：执行端测试检查放过合规样本，拦得住缺文件、没有用例、出现 skip/only/todo。"""
    folder = tmp_path / "tests"
    folder.mkdir()
    for name in EXECUTOR_TESTS:
        (folder / name).write_text("import { it, expect } from 'vitest';\nit('有用例', () => { expect(1).toBe(1); });\n",
                                   encoding="utf-8")
    monkeypatch.setattr("pathlib.Path.glob", lambda *a, **k: [], raising=False)
    orig = executor_test_problems

    def run():
        real_web = globals()["WEB"]
        globals()["WEB"] = tmp_path
        try:
            return orig()
        finally:
            globals()["WEB"] = real_web
    assert run() == [], run()
    (folder / "tasks-css.test.ts").write_text("it.only('x', () => {});\n", encoding="utf-8")
    assert any("only" in p for p in run())
    (folder / "tasks-css.test.ts").write_text("const a = 1;\n", encoding="utf-8")
    assert any("没有用例" in p for p in run())
