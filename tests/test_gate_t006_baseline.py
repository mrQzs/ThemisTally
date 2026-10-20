"""T006 战前门禁：桌面端前端应用框架与夹具数据层（第六片）的黑盒基准测试（合同 t006-desktop-shell，plan_version 1）。

被测对象是 ``desktop/web/``：hash 路由、标题栏、底部 Tab 栏、快捷键、主题切换、页面框架与五态、9 个页面占位、
``src/api.ts`` 与 ``src/mock/`` 夹具数据层，以及搬到 ``#/showcase`` 的陈列页（按文件名自动收集 ``src/showcase/*Showcase.tsx``）。
基线（e4be51f，T005 结项后站主退役 G2 两条 App 陈列页用例）上这些都还没有，所以本文件的“失败”断言落在目标文件不存在
或内容不符上，不是导入、收集或语法错误：模块级只导入标准库，用到被测文件的地方都在用例函数里读；候选里还没有 ``api.ts`` 与
``src/shell/`` 时，``pipeline`` 夹具不跑 npm（没有东西可测，也省掉联网的 ``npm ci``），用到它的用例以断言失败写明原因。

结构（编号对应规划 §7.3 的 S1–S7、P1–P13；门禁端加了若干静态守卫和自检）：

- 静态断言（S 系列，不用流水线，全量 pytest 也跑）：文件在位、api 导出、夹具 JSON 与 UI 文档第 9 节逐值相等（门禁自己解析
  Markdown 的 json 代码块）、不连服务的整词扫描（Python 版）、Logo 与图标、框架 CSS 的取值、README、陈列页收集写法、
  既有 3 份测试只改挂载（标题清单与断言条数取自基线，见 ``EXISTING_TEST_TITLES``、``EXISTING_TEST_EXPECTS``）。
- 流水线断言（P 系列）：会话级夹具 ``pipeline`` 在 ``desktop/web`` 下按顺序跑 ``npm ci``、``npm run build``、``npm test``、
  ``npm run check:contract``，再把探针逐份写成 ``gate-probe/probe-t006-<唯一标识>-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名> --reporter=json`` 跑，``finally`` 里删除；前后各取一次 ``git status``。探针里每个
  ``describe`` 的名字以 D 编号开头，Python 用例按名字分组核对（一组里有一条红，这组对应的 Python 用例就红）。
  全量 pytest 默认跳过用到它的用例（``tests/conftest.py``），点名运行本文件时才跑。
- 门禁自检（``test_gate_selfcheck_*``，不依赖候选）：把各检查函数喂给正确样本和若干改坏的样本，证明门禁自己放得过
  正确实现、拦得住常见错误。

DoD 对应（括号里是探针键与 describe 名前缀）：

- D01：S1、``test_d01_*``、路由探针（route/D01）；D02：S3、``test_d02_*``、标题栏探针（titlebar/D02、S3）；
- D03：S4、Tab 栏探针（tabbar/D03）与状态分组（pages/S7）；D04：快捷键探针（route/D04）；D05：主题探针（titlebar/D05）；
- D06、D07：S2 与数据层探针（api/D06、api/D07，P9，过渡）；D08：S1 的整词扫描与不连服务探针（nonet/D08，P12）；
- D09：页面框架探针（frame/D09）；D10：页面占位探针（pages/D10，过渡）；D11：禁用入口探针（frame/D11）；
- D12：S6、陈列页探针（showcase/D12 收集与排序，showcase/P11 内容，过渡）；
- D13：P1（四步 npm）、P13（流水线前后工作区不变）；V02、V03 由合同另证；
- D14：既有 3 份测试只改挂载、新测试不用 skip、源码守卫（禁用词、W4、role=status、四个浏览器接口）；改动范围由调度器的范围门禁证明
  （这里不写相对基线的范围断言）。

过渡断言（``test_transitional_`` 开头，docstring 第一行写明哪一片会推翻）：P9 的数据层与 ``?mock=`` 开关（接本机服务那一片）、
P10 的 App 级五态与连接胶囊的值、``src/mock/shell.ts`` 的值（同上）、页面占位的文字与空态（各页面那一片）、P11 的陈列页内容与
BaseShowcase、ShellShowcase、showcase.css 的搬家（陈列页演示改版那一片）、api.ts 只有 13 个函数（后面的片按需补读函数与写函数）。
其余（路由、Tab 栏、快捷键、计数规则、状态段、主题、标题栏结构、页面框架五态、禁用入口、不连服务、夹具 JSON、陈列页收集与排序）
是长期断言。要注意：Tab 栏、路由里“保留 ?mock=”以及状态段的几个用例用 ``?mock=`` 与 api 替身来制造各种状态，夹具开关换掉时
这些用例的“布置”要跟着改（断言的规则本身是长期的）。

写法约定：CSS 比较先归一空白；jsdom 不排版、不算层叠，宽、高、位置、层级、色调读 CSS 文件的文本，探针只看结构、焦点、计时与属性；
合同没有定类名的地方，CSS 断言用“有一条规则声明了某值”的写法，不依赖类名（合同定了的类名 ``tt-shell-menu*``、``tt-hide-narrow``
除外）；探针里按名字取模块时，组件既认命名导出也认默认导出（合同没有规定导出方式）；不写 skip、xfail、only、todo。
探针里需要替换的浏览器网络接口名，用字符串拼接写出（整词扫描会扫 src 下全部文件，拼接后门禁自己的源码也不含那四个词）。

门禁做不到、留给人的项（合同 H1–H10）：
H1 视觉对照；H2 1024 × 640 与缩放；H3 窗口宽 1179 与 1180 两侧；H4 暗/亮/跟随系统；H5 真浏览器（StrictMode 的 dev 服务器与
vite preview）；H6 浮层盖在内容之上；H7 禁用入口悬停；H8 读屏；H9 五态在真实框架里各看一次；H10 更纱 11–12px 清晰度。

合同没有写死、门禁端按最合理读法定下的地方（交付信“需协调人决定”里逐条列出，终审可改）：见 ``ASSUMPTIONS``。
"""

import json
import os
import re
import shutil
import signal
import subprocess
import time
import uuid
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_REL = "desktop/web"
WEB = REPO_ROOT / "desktop" / "web"
SRC_REL = f"{WEB_REL}/src"
SRC = WEB / "src"
UI_DOC = REPO_ROOT / "docs" / "themis-tally-3.0-桌面端-UI设计.md"
MAIN_CANVAS = REPO_ROOT / "docs" / "ui-design" / "screens" / "Main.dc.html"
COMPONENTS_CANVAS = REPO_ROOT / "docs" / "ui-design" / "pages" / "02-基础组件-Themis-Tally.html"

ASSUMPTIONS = (
    "PageFrame 的 empty 属性形状合同没定（只写“empty（空态标题与说明）”）：探针依次传 既带 title、description 又可渲染的混合对象、React 元素、{title, description} 对象，任一种能渲染出标题与说明即算满足",
    "PageFrame、DisabledAction 在 src/shell/ 下按文件名导入，命名导出或默认导出都认",
    "页面标题（h1）等于 Tab 标题，document.title 为“标题 · Themis Tally”",
    "状态段“需要你判断 N”与 Tab 计数同口径（待验收 + 要你决定两组），“运行中 N”是运行中一组",
    "连接胶囊点开后启动时间写 2026-10-18 09:41:07、pid 18244（合同第 2 条的值）",
    "仓库菜单 aria-label 为“仓库”，主题菜单为“主题”",
    "api 夹具之外参数的 messages[0] 以 ERROR 开头并含“夹具里没有这份数据：”",
    "getMeta、listSecrets 的 command 只查是字符串数组、不含 --json（合同只说“写第一条命令”）",
    "TabBar 不单测属性（合同没定）：计数、状态段、上次更新都经 App 与 ?mock=、api 替身验证",
)

# 夹具文件名 → UI 文档第 9 节（小节, 该节第几个 json 代码块）
FIXTURE_SOURCES = {
    "meta": ("9.1", 0),
    "status": ("9.2", 0),
    "attempt": ("9.3", 0),
    "file-executor-report": ("9.4", 0),
    "file-events": ("9.4", 1),
    "roles": ("9.5", 0),
    "profiles": ("9.6", 0),
    "presets": ("9.6", 1),
    "preset-diff": ("9.6", 2),
    "runtimes": ("9.7", 0),
    "plugins": ("9.9", 0),
    "history": ("9.10", 0),
    "usage": ("9.11", 0),
    "secrets": ("9.12", 0),
}

API_FUNCTIONS = ("getMeta", "getStatus", "getAttempt", "readFile", "getRoles", "getProfiles", "getPresets",
                 "diffPresets", "getRuntimes", "getPlugins", "getHistory", "getUsage", "listSecrets")
# 合同“非目标”：后面的片按需补的读函数、订阅、作业与写函数
LATER_API = ("listAttempts", "getConfig", "validateConfig", "getHistoryEntry", "getPlugin", "checkSecret",
             "subscribeEvents", "search", "startJob", "getJob", "cancelJob", "preview", "getOperation",
             "startSecretEntry", "setRole", "usePreset", "savePreset", "removePreset", "saveProfile",
             "removeProfile", "addRuntime", "removeRuntime", "setPluginEnabled", "rollback")

TAB_IDS = ("overview", "tasks", "roles", "runtimes", "secrets", "logs", "plugins", "history", "settings")
SHELL_FILES = ("router.ts", "routes.ts", "shortcuts.ts", "theme.ts", "ShellMenu.tsx", "TitleBar.tsx", "Logo.tsx",
               "TabBar.tsx", "PageFrame.tsx", "DisabledAction.tsx", "attemptGroups.ts", "relativeTime.ts")
MOCK_TS = ("scenario.ts", "empty.ts", "shell.ts")
ICON_NAMES = ("FolderOpenIcon", "FolderPlusIcon", "MoonIcon", "SunIcon", "MonitorIcon", "RefreshCwIcon")

BASE_DEMOS = ("button", "tag", "status-tag", "card", "banner", "icon-button", "menu", "dialog", "drawer", "toast")
FORMS_DEMOS = ("text-field", "form-dialog", "segmented", "switch-checkbox", "tabs", "table",
               "key-value", "empty-state", "skeleton", "connection", "breadcrumb")
SHELL_DEMOS = ("page-states", "disabled-action")
T007_DEMOS = ("text-viewer", "text-viewer-jsonl", "safe-markdown", "effort", "masked-value", "command-line", "next-step")

# 站主 Q2 批准改挂载的 3 份既有测试：it 标题与 expect( 条数取自基线 e4be51f（门禁不改它们）
EXISTING_TESTS = ("font-specimen", "showcase-overlays", "showcase-forms")
EXISTING_TEST_TITLES = {
    "font-specimen": [
        "节根带 data-font-specimen 属性",
        "400、500、600 三组字重都存在，组旁标签符合约定",
        "每组四行，每行去两端 | 后都是 26 列，且含汉字行与 ASCII 行",
        "三组样张文字与约定一致",
    ],
    "showcase-overlays": [
        "5 个 data-demo 节都在，顺序是图标按钮、菜单、对话框、抽屉、轻提示",
        "图标按钮演示有 3 个只有图标的按钮、其一禁用；页面上无文字的按钮都有 aria-label",
        "菜单演示：「更多操作」打开菜单，Enter 选中后「上次选择：」变化",
        "对话框演示：「打开对话框」出现模态框，取消后焦点回触发按钮",
        "抽屉演示：「打开抽屉」出现非模态，Esc 关闭并回触发按钮",
        "轻提示演示：「弹出轻提示」后 role=status 出现文字与关闭钮，点关闭清空",
    ],
    "showcase-forms": [
        "11 个 data-demo 节都在、顺序对、都在轻提示之后，复用 showcase__section/h2",
        "整页只有轻提示一个 role=status；新演示无主题字样按钮；文字按钮都有 aria-label",
        "表单对话框：输入框与下拉有 label、mousedown 不被阻止、能聚焦；遮罩仍被阻止",
        "表格：切 40/44/52；用时/token 数字列；Enter/点击后「上次打开」变化",
        "骨架屏：加载 2 秒 299ms 无、300ms 有、2 秒后消失；加载 0.2 秒全程不出现",
        "连接胶囊三态并排、各能点开浮层（含 pid 与启动于）",
    ],
}
EXISTING_TEST_EXPECTS = {"font-specimen": 11, "showcase-overlays": 21, "showcase-forms": 36}

# 基线 App.tsx 里搬进 BaseShowcase.tsx 的原文片段（样张、五个原子、五节浮层演示的文字）
BASE_LITERALS = (
    "字体 · 等距更纱黑体 SC", "Regular 400", "500 按 Regular", "SemiBold 600",
    "一个汉字正好两个英文字符宽", "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "12345678901234567890123456", "日志 attempt-001 已通过 OK",
    "Button 按钮", "主按钮", "次按钮", "幽灵按钮", "危险按钮", "小 28", "中 32", "大 36", "加载 / 禁用", "正在切换…",
    "Tag 标签", "色调", "等宽", "active_preset", "agent:planning_review", "undeclared",
    "StatusTag 状态标签", "17 个状态", "小号 / 未知", "FUTURE_STATE", "WEIRD_CODE",
    "Card 卡片", "卡片标题", "卡头操作", "仅标题", "Banner 提示条", "info：只有 info 可以关掉。", "历史里有 2 行读不出来。",
    "与本机服务的连接断开。", "重新显示 info 提示条",
    "图标按钮 · 工具提示", "只用图标的按钮都带 aria-label 与工具提示",
    "更多操作", "重新运行", "退回返工", "放弃", "上次选择：", "打开对话框", "确认操作", "打开抽屉", "第二行说明文字",
    "弹出轻提示", "已复制到剪贴板",
)
# 基线 App.css 里的 showcase 规则选择器（搬到 src/showcase/showcase.css）
SHOWCASE_SELECTORS = (
    ".showcase", ".showcase__head", ".showcase__title", ".showcase__section", ".showcase__h2", ".showcase__row",
    ".showcase__label", ".showcase__wrap", ".showcase__stack", ".showcase__cards", ".showcase__muted",
    ".showcase__specimen-group", ".showcase__specimen", ".showcase__specimen-row",
)

STATE_GROUPS = {
    "running": ("PREPARING", "RUNNING", "COLLECTING"),
    "review": ("NEEDS_REVIEW", "TIMEOUT", "CANCELLED", "INFRA_FAILURE"),
    "decide": ("ESCALATE", "BLOCKED"),
    "integrate": ("PASS", "ACCEPTED_WITH_EXCEPTION"),
    "done": ("INTEGRATED", "REVISE", "ABANDONED", "SUPERSEDED", "PREPARE_FAILED"),
}

# 夹具总预算：合同检查项 V01 的 timeout 是 1200s，留出余量给其余快测试
PIPELINE_BUDGET = 1000
STEP_CAPS = {
    "npm ci": 300,
    "npm run build": 150,
    "npm test": 250,
    "npm run check:contract": 60,
    "probe": 100,
}


def _join(*parts):
    return "".join(parts)


# 四个浏览器网络词（整词扫描、探针替身用）与 T007 禁用词。拼接写出，使本文件与探针源码自己不含这些词。
NET_WORDS = (_join("fe", "tch"), _join("XMLHttp", "Request"), _join("Event", "Source"), _join("Web", "Socket"))
SINK_WORDS = (_join("dangerously", "SetInner", "HTML"), _join("inner", "HTML"), _join("outer", "HTML"),
              _join("insertAdjacent", "HTML"), _join("ev", "al("), _join("new ", "Function"),
              _join("document", ".write"), _join("src", "doc"), _join("createContextual", "Fragment"),
              _join("DOM", "Parser"))
FORBIDDEN_CALLS = ("matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver")

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


def need_dir(rel):
    path = REPO_ROOT / rel
    assert path.is_dir(), f"{rel} 不存在（基线上还没有实现）"
    return path


def file_digest(path):
    import hashlib

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


def src_files(*subdirs, exts=(".ts", ".tsx", ".css")):
    """src 下（或其子目录）的文件，按路径排序。"""
    roots = [SRC / s for s in subdirs] if subdirs else [SRC]
    out = []
    for root in roots:
        if root.is_dir():
            out += [p for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in exts]
    return out


def shell_css_files():
    folder = SRC / "shell"
    return sorted(folder.glob("*.css")) if folder.is_dir() else []


def shell_css_text():
    return "\n".join(_read(p) for p in shell_css_files())


# ---------------------------------------------------------------------------
# 源码文本小工具
# ---------------------------------------------------------------------------

def strip_ts_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(^|[^:'\"`])//[^\n]*", r"\1", text)


def exported_names(text):
    code = strip_ts_comments(text)
    names = set(re.findall(r"export\s+(?:async\s+)?function\s+(\w+)", code))
    names |= set(re.findall(r"export\s+(?:const|let|var)\s+(\w+)", code))
    for group in re.findall(r"export\s*\{([^}]*)\}", code):
        names |= {part.split(" as ")[-1].strip() for part in group.split(",") if part.strip()}
    return names


def source_rule_problems(label, text):
    """源码守卫：不渲染 role=status；不调用 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver。"""
    code = strip_ts_comments(text)
    problems = []
    if re.search(r"""role\s*[=:]\s*\{?\s*["']status["']""", code):
        problems.append(f"{label}：框架、页面占位与新演示都不能渲染 role=status")
    for name in FORBIDDEN_CALLS:
        if re.search(rf"\b{name}\b", code):
            problems.append(f"{label}：不能用 {name}")
    return problems


def word_hits(text, words):
    """整词（前后不是字母、数字、下划线或美元符）命中的 (行号, 词)；注释与字符串都算。"""
    hits = []
    for no, line in enumerate(text.splitlines(), 1):
        for word in words:
            if re.search(rf"(?<![A-Za-z0-9_$]){re.escape(word)}(?![A-Za-z0-9_$])", line):
                hits.append((no, word))
    return hits


def scan_src_words(words, whole_word=True):
    """递归读 src 下全部文件（不论扩展名），返回“路径:行号: 词”。"""
    found = []
    if not SRC.is_dir():
        return found
    for path in sorted(SRC.rglob("*")):
        if not path.is_file():
            continue
        text = _norm(path.read_text(encoding="utf-8", errors="replace"))
        rel = path.relative_to(WEB).as_posix()
        if whole_word:
            found += [f"{rel}:{no}: {word}" for no, word in word_hits(text, words)]
        else:
            for no, line in enumerate(text.splitlines(), 1):
                found += [f"{rel}:{no}: {word}" for word in words if word in line]
    return found


HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])")
COLOR_FUNC_RE = re.compile(r"\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(", re.I)


def w4_literal_problems(label, text):
    """W4 的坑：只剥块注释，十六进制颜色与颜色函数名加括号（行注释、字符串里的也算）。"""
    body = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
    problems = []
    for no, line in enumerate(body.splitlines(), 1):
        for m in HEX_RE.finditer(line):
            problems.append(f"{label}:{no}: 写死颜色 {m.group(0)}")
        for m in COLOR_FUNC_RE.finditer(line):
            problems.append(f"{label}:{no}: 颜色函数 {m.group(0)}")
    return problems


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
    """返回 [(选择器, [(名, 值)…])]；@media 等包裹块里的规则展平，@keyframes、@font-face 不展开。"""
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
    """归一值：去 !important，所有空白去掉（calc(…) 里的也一样），小写。"""
    return re.sub(r"\s+", "", re.sub(r"!important", "", value or "", flags=re.I)).lower()


def is_zero(value):
    return value in ("0", "0px", "0%")


def decl_matches(decls, names, eq=None, has=(), zero=False):
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


def has_decl(css, names, eq=None, has=(), sel=None, zero=False):
    """有一条规则（选择器匹配正则 sel，缺省不限）声明了 names 里的某个属性，且归一后的值满足条件。"""
    for selector, decls in parse_rules(css):
        if sel and not re.search(sel, selector):
            continue
        if decl_matches(decls, names, eq=eq, has=has, zero=zero):
            return True
    return False


def rule_has_all(css, conds, sel=None):
    """有一条规则同时满足 conds 里每一项：[(属性名元组, 关键字参数字典)]。"""
    for selector, decls in parse_rules(css):
        if sel and not re.search(sel, selector):
            continue
        if all(decl_matches(decls, names, **kw) for names, kw in conds):
            return True
    return False


_BOX_TOKEN = re.compile(r"(?:var|calc)\((?:[^()]|\([^()]*\))*\)|\S+")


def box_sides(decls, prefix="padding"):
    """按源码顺序算 padding / margin 的四边（归一后的字符串）；没写的边是 None。"""
    sides = {"top": None, "right": None, "bottom": None, "left": None}
    for name, value in decls:
        toks = [cv(t) for t in _BOX_TOKEN.findall(value)]
        if name == prefix and toks:
            if len(toks) == 1:
                sides.update(top=toks[0], right=toks[0], bottom=toks[0], left=toks[0])
            elif len(toks) == 2:
                sides.update(top=toks[0], right=toks[1], bottom=toks[0], left=toks[1])
            elif len(toks) == 3:
                sides.update(top=toks[0], right=toks[1], bottom=toks[2], left=toks[1])
            else:
                sides.update(top=toks[0], right=toks[1], bottom=toks[2], left=toks[3])
        elif name in (f"{prefix}-left", f"{prefix}-inline-start") and toks:
            sides["left"] = toks[0]
        elif name in (f"{prefix}-right", f"{prefix}-inline-end") and toks:
            sides["right"] = toks[0]
        elif name == f"{prefix}-inline" and toks:
            sides["left"] = toks[0]
            sides["right"] = toks[-1]
    return sides


def rule_sides(css, sel=None, **want):
    """有一条规则（选择器匹配正则 sel，缺省不限）的 padding 四边满足 want（如 right='140px', left='var(--tt-space-3)'）。"""
    for selector, decls in parse_rules(css):
        if sel and not re.search(sel, selector):
            continue
        sides = box_sides(decls)
        if all(sides.get(k) == cv(v) for k, v in want.items()):
            return True
    return False


BG = ("background", "background-color")
PX_COMMENT = re.compile(r"/\*")


def px_literal_problems(label, css_raw, need_text=None):
    """合同公共约定：尺寸字面量同一行带出处注释。除 0 与 1px 外的 px 字面量，所在行（去掉注释后）有 px，
    该行又没有注释（need_text 给定时，注释里还要含这段文字），就记一条问题。"""
    problems = []
    in_comment = False
    for no, line in enumerate(css_raw.splitlines(), 1):
        code, i, n, comment_text = [], 0, len(line), ""
        saw_comment = in_comment
        while i < n:
            if in_comment:
                end = line.find("*/", i)
                if end < 0:
                    comment_text += line[i:]
                    i = n
                else:
                    comment_text += line[i:end]
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
            if not saw_comment or (need_text and need_text not in comment_text):
                extra = f"（注释里要写“{need_text}”）" if need_text else ""
                problems.append(f"{label}:{no}: {m.group(0)} 没有同一行的出处注释{extra}：{line.strip()[:80]}")
    return problems


def token_only_problems(label, css):
    """合同公共约定：层级、圆角、阴影、字体只用 --tt-* 令牌（颜色由 W4 另查）。"""
    problems = []
    for selector, decls in parse_rules(css):
        for name, value in decls:
            v = cv(value)
            if name == "z-index" and not v.startswith("var(--tt-z-"):
                problems.append(f"{label}：{selector} 的 z-index 应取 --tt-z-* 令牌，实际 {value}")
            elif name == "border-radius" and not re.fullmatch(r"(?:var\(--tt-radius-[\w-]+\)|0|0px)+|inherit", v):
                problems.append(f"{label}：{selector} 的 border-radius 应取 --tt-radius-* 令牌，实际 {value}")
            elif name == "box-shadow" and v != "none" and "var(--tt-" not in v:
                problems.append(f"{label}：{selector} 的 box-shadow 应取令牌，实际 {value}")
            elif name in ("font", "font-family", "font-size") and not (v.startswith("var(--tt-") or v == "inherit"):
                problems.append(f"{label}：{selector} 的 {name} 应取 --tt-* 字体令牌或 inherit，实际 {value}")
    return problems


def undefined_token_problems(label, css, tokens_css):
    defined = set(re.findall(r"(--tt-[\w-]+)\s*:", strip_comments(tokens_css)))
    used = set(re.findall(r"var\(\s*(--tt-[\w-]+)", strip_comments(css)))
    return [f"{label}：用了令牌库里没有的 {name}" for name in sorted(used - defined)]


def new_css_files():
    """本片新增或搬动的 CSS：shell/*.css、showcase/showcase.css、showcase/showcase-shell.css、App.css。"""
    files = list(shell_css_files())
    for rel in ("showcase/showcase.css", "showcase/showcase-shell.css", "App.css"):
        path = SRC / rel
        if path.is_file():
            files.append(path)
    return files


# ---------------------------------------------------------------------------
# 夹具与画布解析
# ---------------------------------------------------------------------------

def doc_json_blocks(md):
    """UI 文档第 9 节：{小节号: [json 代码块…]}。"""
    heads = [(m.start(), m.group(1)) for m in re.finditer(r"^### (9\.\d+) ", md, re.M)]
    ends = [m.start() for m in re.finditer(r"^## ", md, re.M)]
    out = {}
    for idx, (pos, num) in enumerate(heads):
        stop = min([p for p, _ in heads[idx + 1:idx + 2]] + [e for e in ends if e > pos] + [len(md)])
        out[num] = re.findall(r"```json\n(.*?)\n```", md[pos:stop], re.S)
    return out


def doc_fixture(name):
    section, index = FIXTURE_SOURCES[name]
    blocks = doc_json_blocks(_read(UI_DOC)).get(section, [])
    assert len(blocks) > index, f"UI 文档 {section} 节找不到第 {index + 1} 个 json 代码块"
    return json.loads(blocks[index])


def strict_diff(a, b, path="$"):
    """逐值比较 JSON：布尔与数字不混；整数与浮点按数值比；返回第一处不同的说明，相同返回 None。"""
    if isinstance(a, bool) or isinstance(b, bool):
        return None if (isinstance(a, bool) and isinstance(b, bool) and a == b) else f"{path}: {a!r} != {b!r}"
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return None if a == b else f"{path}: {a!r} != {b!r}"
    if type(a) is not type(b):
        return f"{path}: 类型 {type(a).__name__} != {type(b).__name__}"
    if isinstance(a, dict):
        if set(a) != set(b):
            return f"{path}: 键不同 {sorted(set(a) ^ set(b))}"
        for key in a:
            diff = strict_diff(a[key], b[key], f"{path}.{key}")
            if diff:
                return diff
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: 长度 {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            diff = strict_diff(x, y, f"{path}[{i}]")
            if diff:
                return diff
        return None
    return None if a == b else f"{path}: {a!r} != {b!r}"


def fixture_problems():
    problems = []
    folder = SRC / "mock"
    if not folder.is_dir():
        return [f"{SRC_REL}/mock/ 不存在（基线上还没有实现）"]
    have = {p.stem for p in folder.glob("*.json")}
    want = set(FIXTURE_SOURCES)
    if have != want:
        problems.append(f"src/mock/*.json 应恰是 {sorted(want)}，实际多了 {sorted(have - want)}、缺了 {sorted(want - have)}")
    for name in sorted(want & have):
        try:
            got = json.loads(_read(folder / f"{name}.json"))
        except ValueError as exc:
            problems.append(f"{name}.json 不是合法 JSON：{exc}")
            continue
        diff = strict_diff(got, doc_fixture(name))
        if diff:
            problems.append(f"{name}.json 与 UI 文档第 {FIXTURE_SOURCES[name][0]} 节不相等：{diff}")
    return problems


class _SvgParser(HTMLParser):
    """把一段 HTML 里的 <svg>…</svg> 解析成 {width, height, viewBox, children:[{tag, attrs}]}（只取直接子元素）。"""

    SKIP_PREFIX = ("aria-", "sc-", "data-")
    SKIP_NAMES = ("class", "style")

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.shapes = []
        self.depth = 0
        self.current = None

    @staticmethod
    def _num(value):
        if re.fullmatch(r"-?(?:\d+\.?\d*|\.\d+)", value):
            return "%g" % float(value)
        return value

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "svg" and self.depth == 0:
            view = attrs.get("viewbox") or attrs.get("sc-camel-view-box") or ""
            self.current = {"width": self._num(attrs.get("width", "")), "height": self._num(attrs.get("height", "")),
                            "viewBox": view, "children": []}
            self.depth = 1
        elif self.current is not None:
            if self.depth == 1:
                kept = {k: self._num(v or "") for k, v in attrs.items()
                        if k not in self.SKIP_NAMES and not k.startswith(self.SKIP_PREFIX)}
                self.current["children"].append({"tag": tag, "attrs": kept})
            self.depth += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.current is None:
            return
        self.depth -= 1
        if self.depth == 0:
            self.shapes.append(self.current)
            self.current = None


def svg_shapes(html_fragment):
    parser = _SvgParser()
    parser.feed(html_fragment)
    return parser.shapes


def canvas_line(path, lineno):
    return _read(path).split("\n")[lineno - 1]


def canvas_icon_shapes():
    """Main 画布与组件板上本片用到的图标：名字 → 结构。"""
    main = MAIN_CANVAS
    shapes = {}
    tab_lines = {"overview": 41, "tasks": 42, "roles": 43, "runtimes": 44, "secrets": 45,
                 "logs": 46, "plugins": 47, "history": 48, "settings": 50}
    for tab, lineno in tab_lines.items():
        found = svg_shapes(canvas_line(main, lineno))
        shapes[f"tab:{tab}"] = found[0]
    folder_line = svg_shapes(canvas_line(main, 23))
    shapes["folder-open"], shapes["chevron-down"] = folder_line[0], folder_line[1]
    theme_line = svg_shapes(canvas_line(main, 31))
    shapes["moon"], shapes["sun"], shapes["monitor"] = theme_line[0], theme_line[1], theme_line[2]
    shapes["refresh"] = svg_shapes(canvas_line(main, 73))[0]
    shapes["folder-plus"] = svg_shapes(canvas_line(COMPONENTS_CANVAS, 460))[0]
    return shapes


def canvas_logo():
    paths = re.findall(r'<path\b[^>]*?\bd="([^"]+)"', canvas_line(MAIN_CANVAS, 20))
    assert len(paths) == 2, paths
    line = canvas_line(MAIN_CANVAS, 20)
    mark = re.search(r'<path fill-rule="evenodd"[^>]*?\bd="([^"]+)"', line).group(1)
    tally = [p for p in paths if p != mark][0]
    return {"mark": mark, "tally": tally}


# ---------------------------------------------------------------------------
# 探针（Vitest + jsdom）：每份若干 describe，describe 名以 D 编号开头；Python 用例按名字分组核对
# ---------------------------------------------------------------------------

PRELUDE = r"""
import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

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
  document.documentElement.removeAttribute('data-theme');
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
async function advanceAsync(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
function textOf(el: Element | null): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function focusOn(el: HTMLElement) {
  act(() => {
    el.focus();
  });
}
function key(k: string, init: any = {}, target: Element | null = document.activeElement) {
  return fireEvent.keyDown((target || document.body) as Element, { key: k, ...init });
}
function ctrl(k: string, init: any = {}) {
  return fireEvent.keyDown(window, { key: k, ctrlKey: true, ...init });
}
async function mountApp(hash: string, wrap = false) {
  window.location.hash = hash;
  const mod: any = await import('../src/App');
  const App = mod.default ?? mod.App;
  expect(App, 'src/App.tsx 应导出 App').toBeTruthy();
  const out = render(
    wrap ? (
      <React.StrictMode>
        <App />
      </React.StrictMode>
    ) : (
      <App />
    ),
  );
  await settle();
  return out;
}
function nav(): HTMLElement {
  const el = document.querySelector('nav[aria-label="主导航"]');
  expect(el, '应有 nav[aria-label=主导航]').not.toBeNull();
  return el as HTMLElement;
}
function tabLinks(): HTMLAnchorElement[] {
  return Array.from(nav().querySelectorAll('a[data-tab]')) as HTMLAnchorElement[];
}
function tab(id: string): HTMLAnchorElement {
  const el = nav().querySelector('a[data-tab="' + id + '"]');
  expect(el, '找不到 Tab ' + id).not.toBeNull();
  return el as HTMLAnchorElement;
}
function currentIds(): string[] {
  return tabLinks()
    .filter((a) => a.getAttribute('aria-current') === 'page')
    .map((a) => a.getAttribute('data-tab') as string);
}
function labelOf(a: Element): string {
  const clone = a.cloneNode(true) as Element;
  clone.querySelectorAll('[data-tab-count], [aria-hidden="true"], svg').forEach((n) => n.remove());
  return textOf(clone);
}
function header(): HTMLElement {
  const el = document.querySelector('header');
  expect(el, '应有标题栏 header').not.toBeNull();
  return el as HTMLElement;
}
function segment(): HTMLElement {
  const el = nav().querySelector('[aria-live="polite"]');
  expect(el, '状态段应是 aria-live=polite 的容器').not.toBeNull();
  return el as HTMLElement;
}
function segLink(prefix: string): HTMLElement {
  const hit = Array.from(segment().querySelectorAll('a')).find((a) => textOf(a).startsWith(prefix));
  expect(hit, '状态段里找不到以「' + prefix + '」开头的链接').toBeTruthy();
  return hit as HTMLElement;
}
function segCount(prefix: string): string {
  return textOf(segLink(prefix)).slice(prefix.length).trim();
}
function badge(): HTMLElement | null {
  return nav().querySelector('[data-tab-count]');
}
function updateEl(): HTMLElement | null {
  return nav().querySelector('[aria-live="off"]');
}
function pageRoot(): HTMLElement {
  const nodes = document.querySelectorAll('[data-page-state]');
  expect(nodes.length, '应恰有一个带 data-page-state 的页面根').toBe(1);
  return nodes[0] as HTMLElement;
}
function buttonByText(root: Element, text: string): HTMLButtonElement {
  const hit = Array.from(root.querySelectorAll('button')).find((b) => textOf(b) === text);
  expect(hit, '找不到文字为「' + text + '」的按钮').toBeTruthy();
  return hit as HTMLButtonElement;
}
function maybeButton(root: Element, text: string): HTMLButtonElement | null {
  return (Array.from(root.querySelectorAll('button')).find((b) => textOf(b) === text) as HTMLButtonElement) || null;
}
function deferred<T = any>() {
  let resolve!: (v: T) => void;
  let reject!: (e: any) => void;
  const promise = new Promise<T>((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
}
const TABS = [
  { id: 'overview', title: '总览', hint: 'Ctrl+1' },
  { id: 'tasks', title: '任务', hint: 'Ctrl+2' },
  { id: 'roles', title: '角色与模型', hint: 'Ctrl+3' },
  { id: 'runtimes', title: 'CLI 运行时', hint: 'Ctrl+4' },
  { id: 'secrets', title: '凭据', hint: 'Ctrl+5' },
  { id: 'logs', title: '日志与用量', hint: 'Ctrl+6' },
  { id: 'plugins', title: '插件', hint: 'Ctrl+7' },
  { id: 'history', title: '历史与审计', hint: 'Ctrl+8' },
  { id: 'settings', title: '设置', hint: 'Ctrl+,' },
];
"""

# 路由与快捷键（P2、P3；D01、D04）
PROBE_ROUTE = PRELUDE + r"""
describe('D01 路由与 Tab 栏', () => {
  it('空 hash 显示总览：h1、当前项、document.title，地址不被改写', async () => {
    await mountApp('');
    expect(document.querySelectorAll('h1').length, '页面上应恰有一个 h1').toBe(1);
    expect(textOf(document.querySelector('h1'))).toBe('总览');
    expect(currentIds()).toEqual(['overview']);
    expect(document.title).toBe('总览 · Themis Tally');
    expect(window.location.hash).toBe('');
  });

  it('9 个 Tab 的顺序、文字、href、title，历史与审计和设置之间有一条分隔线，导航在内容区之前', async () => {
    await mountApp('');
    const links = tabLinks();
    expect(links.map((a) => a.getAttribute('data-tab'))).toEqual(TABS.map((t) => t.id));
    TABS.forEach((t, i) => {
      expect(labelOf(links[i]), 'Tab ' + t.id + ' 的文字').toBe(t.title);
      expect(links[i].getAttribute('href'), 'Tab ' + t.id + ' 的 href').toBe('#/' + t.id);
      expect(links[i].getAttribute('title'), 'Tab ' + t.id + ' 的 title').toBe(t.title + '（' + t.hint + '）');
    });
    const dividers = nav().querySelectorAll('[data-tab-divider]');
    expect(dividers.length, '应恰有一条分隔线').toBe(1);
    const divider = dividers[0];
    expect(divider.getAttribute('aria-hidden')).toBe('true');
    expect(links[7].compareDocumentPosition(divider) & Node.DOCUMENT_POSITION_FOLLOWING, '分隔线在历史与审计之后').toBeTruthy();
    expect(divider.compareDocumentPosition(links[8]) & Node.DOCUMENT_POSITION_FOLLOWING, '分隔线在设置之前').toBeTruthy();
    const h1 = document.querySelector('h1') as Element;
    expect(nav().compareDocumentPosition(h1) & Node.DOCUMENT_POSITION_FOLLOWING, 'DOM 里 nav 在内容区之前（用 order 排到最下面）').toBeTruthy();
  });

  it('只有当前项有 aria-current=page 与顶部金条（aria-hidden 的空 span）', async () => {
    await mountApp('#/roles');
    expect(currentIds()).toEqual(['roles']);
    for (const a of tabLinks()) {
      const id = a.getAttribute('data-tab');
      const bars = Array.from(a.children).filter(
        (c) =>
          c.tagName.toLowerCase() === 'span' &&
          c.getAttribute('aria-hidden') === 'true' &&
          !c.hasAttribute('data-tab-count') &&
          !c.querySelector('svg') &&
          textOf(c) === '',
      );
      expect(bars.length, 'Tab ' + id + ' 的金条个数').toBe(id === 'roles' ? 1 : 0);
      if (id !== 'roles') {
        expect(a.hasAttribute('aria-current'), 'Tab ' + id + ' 不是当前项，不该有 aria-current').toBe(false);
      }
    }
  });

  it('点击 Tab 切页：事件被 preventDefault，地址、当前项、h1 与 document.title 同步变', async () => {
    await mountApp('#/overview');
    const order = TABS.slice(1).concat(TABS[0]);
    for (const t of order) {
      const notPrevented = fireEvent.click(tab(t.id));
      expect(notPrevented, '无修饰键的左键点击应先 preventDefault').toBe(false);
      expect(window.location.hash, '点 ' + t.id + ' 后的地址').toBe('#/' + t.id);
      expect(currentIds(), '点 ' + t.id + ' 后的当前项').toEqual([t.id]);
      expect(textOf(document.querySelector('h1')), '点 ' + t.id + ' 后的 h1').toBe(t.title);
      expect(document.title).toBe(t.title + ' · Themis Tally');
      await settle();
    }
  });

  it('带修饰键的点击走默认行为：不拦截、不导航', async () => {
    await mountApp('#/overview');
    for (const mod of ['ctrlKey', 'shiftKey', 'metaKey', 'altKey']) {
      const appPrevented = clickKeepUrl(tab('tasks'), { [mod]: true });
      expect(appPrevented, mod + ' 点击不该被 preventDefault').toBe(false);
      expect(window.location.hash, mod + ' 点击不该导航').toBe('#/overview');
      expect(currentIds()).toEqual(['overview']);
    }
  });

  it('未知路由、#、#/ 都显示总览，且不改写地址', async () => {
    for (const hash of ['#/nope', '#', '#/', '#/nope/deeper?mock=data']) {
      const r = await mountApp(hash);
      expect(textOf(document.querySelector('h1')), hash + ' 的 h1').toBe('总览');
      expect(currentIds(), hash + ' 的当前项').toEqual(['overview']);
      expect(window.location.href.endsWith(hash), hash + ' 的地址不该被改写，实际 ' + window.location.href).toBe(true);
      r.unmount();
    }
  });

  it('路径第一段决定页面：#/tasks/x/y 归任务', async () => {
    await mountApp('#/tasks/x/y');
    expect(currentIds()).toEqual(['tasks']);
    expect(textOf(document.querySelector('h1'))).toBe('任务');
    expect(window.location.hash).toBe('#/tasks/x/y');
    expect(document.title).toBe('任务 · Themis Tally');
  });

  it('#/showcase 没有当前项，渲染陈列页，标题是组件陈列', async () => {
    await mountApp('#/showcase');
    expect(currentIds()).toEqual([]);
    expect(tabLinks().length, 'Tab 栏照常在').toBe(9);
    expect(document.querySelectorAll('h1').length).toBe(1);
    expect(textOf(document.querySelector('h1'))).toBe('组件陈列');
    expect(document.title).toBe('组件陈列 · Themis Tally');
    expect(document.querySelectorAll('[data-showcase]').length, '陈列页的节').toBeGreaterThan(0);
    expect(document.querySelector('[data-page-state]'), '陈列页不用 PageFrame').toBeNull();
  });

  it('从陈列页点 Tab 回到应用页', async () => {
    await mountApp('#/showcase');
    fireEvent.click(tab('plugins'));
    expect(window.location.hash).toBe('#/plugins');
    expect(currentIds()).toEqual(['plugins']);
    expect(document.querySelector('[data-showcase]'), '离开陈列页后不再渲染它').toBeNull();
  });

  it('后退、前进与手改地址：hashchange 带动页面', async () => {
    await mountApp('#/overview');
    window.location.hash = '#/plugins';
    await act(async () => {
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    expect(currentIds()).toEqual(['plugins']);
    expect(textOf(document.querySelector('h1'))).toBe('插件');
    window.location.hash = '#/runtimes/abc';
    await act(async () => {
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    expect(currentIds()).toEqual(['runtimes']);
    expect(document.title).toBe('CLI 运行时 · Themis Tally');
    window.location.hash = '#/showcase';
    await act(async () => {
      window.dispatchEvent(new HashChangeEvent('hashchange'));
    });
    expect(currentIds()).toEqual([]);
    await settle();
  });

  it('Tab 链接与状态段链接保留当前 ?mock=，没有 mock 时不带查询', async () => {
    const r = await mountApp('#/overview?mock=empty');
    for (const t of TABS) {
      expect(tab(t.id).getAttribute('href'), 'Tab ' + t.id).toBe('#/' + t.id + '?mock=empty');
    }
    expect(segLink('运行中').getAttribute('href')).toBe('#/tasks?mock=empty');
    fireEvent.click(tab('roles'));
    expect(window.location.hash).toBe('#/roles?mock=empty');
    r.unmount();
    await mountApp('#/overview');
    for (const t of TABS) {
      expect(tab(t.id).getAttribute('href'), 'Tab ' + t.id).toBe('#/' + t.id);
    }
    expect(segLink('运行中').getAttribute('href')).toBe('#/tasks');
  });

  it('换路由时内容区重新挂载（按路由加 key，滚回顶部）', async () => {
    await mountApp('#/overview');
    const before = document.querySelector('h1') as Element;
    fireEvent.click(tab('tasks'));
    const after = document.querySelector('h1') as Element;
    expect(after, '换路由后 h1 应是新节点').not.toBe(before);
    expect(before.isConnected, '旧页面的 h1 应已卸载').toBe(false);
    await settle();
  });
});

describe('D04 快捷键', () => {
  it('Ctrl+1…8 依次切前 8 个 Tab，Ctrl+, 切设置，处理了就 preventDefault', async () => {
    await mountApp('#/overview');
    const keys = ['2', '3', '4', '5', '6', '7', '8', '1'];
    const ids = ['tasks', 'roles', 'runtimes', 'secrets', 'logs', 'plugins', 'history', 'overview'];
    keys.forEach((k, i) => {
      const notPrevented = ctrl(k);
      expect(notPrevented, 'Ctrl+' + k + ' 应被 preventDefault').toBe(false);
      expect(window.location.hash, 'Ctrl+' + k + ' 后的地址').toBe('#/' + ids[i]);
      expect(currentIds()).toEqual([ids[i]]);
    });
    expect(ctrl(',')).toBe(false);
    expect(window.location.hash).toBe('#/settings');
    expect(currentIds()).toEqual(['settings']);
    expect(textOf(document.querySelector('h1'))).toBe('设置');
    await settle();
  });

  it('带 Alt、Shift 或 Meta 不切，也不 preventDefault', async () => {
    await mountApp('#/overview');
    for (const mod of ['altKey', 'shiftKey', 'metaKey']) {
      expect(ctrl('2', { [mod]: true }), 'Ctrl+' + mod + '+2 不该被拦').toBe(true);
      expect(window.location.hash).toBe('#/overview');
      expect(ctrl(',', { [mod]: true })).toBe(true);
      expect(window.location.hash).toBe('#/overview');
    }
  });

  it('Ctrl+9、Ctrl+0、Ctrl+字母、Ctrl+Esc、不带 Ctrl 的数字都不管', async () => {
    await mountApp('#/overview');
    for (const k of ['9', '0', 'a', 'Escape', 'ArrowRight']) {
      expect(ctrl(k), 'Ctrl+' + k + ' 不该被拦').toBe(true);
      expect(window.location.hash).toBe('#/overview');
    }
    expect(fireEvent.keyDown(window, { key: '2' }), '不带 Ctrl 的 2 不该被拦').toBe(true);
    expect(window.location.hash).toBe('#/overview');
  });

  it('输入法组合中不处理；事件已被别处 preventDefault 时不处理', async () => {
    await mountApp('#/overview');
    expect(ctrl('2', { isComposing: true })).toBe(true);
    expect(window.location.hash).toBe('#/overview');
    const early = (e: Event) => e.preventDefault();
    window.addEventListener('keydown', early, true);
    try {
      ctrl('2');
      expect(window.location.hash, '已被 preventDefault 的事件不该再切页').toBe('#/overview');
    } finally {
      window.removeEventListener('keydown', early, true);
    }
    expect(ctrl('2')).toBe(false);
    expect(window.location.hash).toBe('#/tasks');
  });

  it('模态对话框（role=dialog 且 aria-modal=true）打开时不切；非模态抽屉不挡', async () => {
    await mountApp('#/overview');
    const modal = document.createElement('div');
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    document.body.appendChild(modal);
    try {
      expect(ctrl('3'), '模态框打开时 Ctrl+3 不该被拦').toBe(true);
      expect(window.location.hash).toBe('#/overview');
    } finally {
      modal.remove();
    }
    const drawer = document.createElement('div');
    drawer.setAttribute('role', 'dialog');
    drawer.setAttribute('aria-modal', 'false');
    document.body.appendChild(drawer);
    try {
      expect(ctrl('3'), '非模态抽屉不挡快捷键').toBe(false);
      expect(window.location.hash).toBe('#/roles');
    } finally {
      drawer.remove();
    }
  });

  it('在 window 上监听：从 body 冒泡上来的按键也处理；导航保留 ?mock=；陈列页上也能切', async () => {
    await mountApp('#/overview?mock=empty');
    expect(fireEvent.keyDown(document.body, { key: '2', ctrlKey: true })).toBe(false);
    expect(window.location.hash).toBe('#/tasks?mock=empty');
    await settle();
  });

  it('从陈列页按 Ctrl+1 回到总览', async () => {
    await mountApp('#/showcase');
    expect(ctrl('1')).toBe(false);
    expect(window.location.hash).toBe('#/overview');
    expect(currentIds()).toEqual(['overview']);
    await settle();
  });

  it('卸载后不再监听', async () => {
    const r = await mountApp('#/overview');
    r.unmount();
    expect(ctrl('2'), '卸载后的按键不该被拦').toBe(true);
    expect(window.location.hash).toBe('#/overview');
  });
});
"""

# 标题栏、两个菜单、主题、Logo 与图标（P5、P6；D02、D05、S3）
PROBE_TITLEBAR = PRELUDE + r"""
const LOGO: any = __LOGO__;
const SHAPES: any = __ICON_SHAPES__;

function repoTrigger(): HTMLElement {
  const el = header().querySelector('button[title="切换仓库"]');
  expect(el, '标题栏里应有 title=切换仓库 的按钮').not.toBeNull();
  return el as HTMLElement;
}
function themeTrigger(): HTMLElement {
  const el = header().querySelector('button[aria-haspopup="menu"][aria-label^="主题："]');
  expect(el, '标题栏里应有名称以「主题：」开头的菜单触发钮').not.toBeNull();
  return el as HTMLElement;
}
function menuItems(menu: Element): HTMLElement[] {
  return Array.from(menu.querySelectorAll('[role="menuitem"], [role="menuitemradio"]')) as HTMLElement[];
}
function openMenu(trigger: HTMLElement): HTMLElement {
  focusOn(trigger);
  fireEvent.click(trigger);
  const menu = document.querySelector('[role="menu"]');
  expect(menu, '点触发钮后应出现 role=menu').not.toBeNull();
  return menu as HTMLElement;
}
function noMenu() {
  expect(document.querySelector('[role="menu"]'), '菜单应已关闭').toBeNull();
}
function attrsOf(el: Element): Record<string, string> {
  const out: Record<string, string> = {};
  Array.from(el.attributes).forEach((a) => {
    if (a.name !== 'data-theme') out[a.name] = a.value;
  });
  return out;
}
const NUM = /^-?(\d+\.?\d*|\.\d+)$/;
function nv(v: string): string {
  return NUM.test(v) ? String(parseFloat(v)) : v;
}
function shapeOf(svg: Element) {
  return {
    width: nv(svg.getAttribute('width') || ''),
    height: nv(svg.getAttribute('height') || ''),
    viewBox: svg.getAttribute('viewBox') || '',
    children: Array.from(svg.children).map((c) => ({
      tag: c.tagName.toLowerCase(),
      attrs: Object.fromEntries(
        Array.from(c.attributes)
          .filter((a) => !['class', 'style'].includes(a.name) && !/^(aria-|sc-|data-)/.test(a.name))
          .map((a) => [a.name, nv(a.value)]),
      ),
    })),
  };
}
function sameShape(svg: Element | null, name: string) {
  expect(svg, '找不到图标 ' + name).not.toBeNull();
  expect(shapeOf(svg as Element), '图标 ' + name + ' 应与画布一致').toEqual(SHAPES[name]);
}

describe('D02 标题栏', () => {
  it('Logo、产品名与连接胶囊都在标题栏里', async () => {
    await mountApp('#/overview');
    const h = header();
    expect(h.querySelector('svg[role="img"][aria-label="Themis Tally 标识"]'), 'Logo').not.toBeNull();
    expect(textOf(h)).toContain('Themis Tally');
    expect(h.querySelector('h1'), '产品名不是 h1').toBeNull();
    const pill = h.querySelector('button[data-state="connected"]') as HTMLElement;
    expect(pill, '标题栏里应有 data-state=connected 的连接胶囊').not.toBeNull();
    expect(textOf(pill)).toContain('已连接');
    fireEvent.click(pill);
    expect(pill.getAttribute('aria-expanded')).toBe('true');
    const pop = document.getElementById(pill.getAttribute('aria-controls') || '');
    expect(pop, '点开胶囊后应有浮层').not.toBeNull();
    expect(textOf(pop)).toContain('pid');
    expect(textOf(pop)).toContain('启动于');
    expect(textOf(pop)).toContain('事件流');
  });

  it('仓库菜单：触发钮、面板结构、分组标题与分隔线、初始焦点', async () => {
    await mountApp('#/overview');
    const trigger = repoTrigger();
    expect(trigger.getAttribute('aria-haspopup')).toBe('menu');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(trigger.id, '触发钮要有 id').not.toBe('');
    expect(textOf(trigger)).toContain('demo-repo');
    expect(trigger.getAttribute('data-variant')).toBe('ghost');
    expect(trigger.getAttribute('data-size')).toBe('sm');
    noMenu();
    const menu = openMenu(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    expect(menu.id).not.toBe('');
    expect(trigger.getAttribute('aria-controls')).toBe(menu.id);
    expect(menu.getAttribute('aria-label')).toBe('仓库');
    const its = menuItems(menu);
    expect(its.length).toBe(3);
    expect(its.map((i) => i.getAttribute('role'))).toEqual(['menuitemradio', 'menuitemradio', 'menuitem']);
    expect(textOf(its[0])).toContain('demo-repo');
    expect(textOf(its[1])).toContain('docs-site');
    expect(textOf(its[2])).toContain('添加仓库…');
    expect(textOf(its[2])).toContain('第二阶段接入');
    expect(its[0].getAttribute('aria-checked'), '当前仓库带勾').toBe('true');
    expect(its[1].getAttribute('aria-checked')).toBe('false');
    expect(its[2].getAttribute('aria-disabled'), '添加仓库禁用').toBe('true');
    expect(its[0].getAttribute('aria-disabled')).not.toBe('true');
    expect(document.activeElement, '打开后焦点到第一项').toBe(its[0]);
    const heading = Array.from(menu.querySelectorAll('*')).find((e) => e.children.length === 0 && textOf(e) === '最近的仓库');
    expect(heading, '应有分组标题「最近的仓库」').toBeTruthy();
    let node: Element | null = heading as Element;
    while (node && node !== menu) {
      expect(node.hasAttribute('tabindex'), '分组标题不可聚焦').toBe(false);
      expect(node.getAttribute('role') || '').not.toMatch(/^menuitem/);
      node = node.parentElement;
    }
    const seps = menu.querySelectorAll('[role="separator"]');
    expect(seps.length, '应有一条分隔线').toBe(1);
    expect(seps[0].hasAttribute('tabindex'), '分隔线不可聚焦').toBe(false);
    expect(its[1].compareDocumentPosition(seps[0]) & Node.DOCUMENT_POSITION_FOLLOWING, '分隔线在两个仓库之后').toBeTruthy();
    expect(seps[0].compareDocumentPosition(its[2]) & Node.DOCUMENT_POSITION_FOLLOWING, '分隔线在添加仓库之前').toBeTruthy();
    expect((heading as Element).compareDocumentPosition(its[0]) & Node.DOCUMENT_POSITION_FOLLOWING, '标题在第一项之前').toBeTruthy();
  });

  it('仓库菜单键盘：ArrowDown/ArrowUp 移动并循环（禁用项可聚焦），Home/End 到首尾，处理的键都 preventDefault', async () => {
    await mountApp('#/overview');
    const menu = openMenu(repoTrigger());
    const its = menuItems(menu);
    expect(key('ArrowDown'), 'ArrowDown 应 preventDefault').toBe(false);
    expect(document.activeElement).toBe(its[1]);
    key('ArrowDown');
    expect(document.activeElement, '禁用项照 WAI-ARIA 可以聚焦').toBe(its[2]);
    key('ArrowDown');
    expect(document.activeElement, '循环回第一项').toBe(its[0]);
    expect(key('ArrowUp'), 'ArrowUp 应 preventDefault').toBe(false);
    expect(document.activeElement, '第一项再向上循环到末项').toBe(its[2]);
    expect(key('Home'), 'Home 应 preventDefault').toBe(false);
    expect(document.activeElement).toBe(its[0]);
    expect(key('End'), 'End 应 preventDefault').toBe(false);
    expect(document.activeElement).toBe(its[2]);
  });

  it('仓库菜单：禁用项上 Enter 与点击都选不了，菜单也不关', async () => {
    await mountApp('#/overview');
    const trigger = repoTrigger();
    const menu = openMenu(trigger);
    const its = menuItems(menu);
    key('End');
    expect(document.activeElement).toBe(its[2]);
    key('Enter');
    expect(document.querySelector('[role="menu"]'), 'Enter 选不了禁用项，菜单不关').not.toBeNull();
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    fireEvent.click(its[2]);
    expect(document.querySelector('[role="menu"]'), '点击禁用项，菜单不关').not.toBeNull();
    expect(textOf(trigger)).toContain('demo-repo');
  });

  it('仓库菜单：选别的仓库只关菜单、焦点回触发钮、界面不变（Enter 与点击都一样）', async () => {
    await mountApp('#/overview');
    const trigger = repoTrigger();
    let menu = openMenu(trigger);
    key('ArrowDown');
    key('Enter');
    noMenu();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement, 'Enter 选中后焦点回触发钮').toBe(trigger);
    expect(textOf(trigger)).toContain('demo-repo');
    expect(textOf(trigger)).not.toContain('docs-site');
    menu = openMenu(trigger);
    let its = menuItems(menu);
    expect(its[0].getAttribute('aria-checked'), '当前仓库仍是 demo-repo').toBe('true');
    expect(its[1].getAttribute('aria-checked')).toBe('false');
    fireEvent.click(its[1]);
    noMenu();
    expect(document.activeElement, '点击选中后焦点回触发钮').toBe(trigger);
    expect(textOf(trigger)).toContain('demo-repo');
    expect(textOf(document.querySelector('h1'))).toBe('总览');
  });

  it('仓库菜单：Esc 关闭、焦点回触发钮、不冒泡；Tab 关闭；在菜单与触发钮之外按下鼠标关闭', async () => {
    await mountApp('#/overview');
    const trigger = repoTrigger();
    openMenu(trigger);
    const spy = vi.fn();
    document.addEventListener('keydown', spy);
    try {
      key('Escape');
    } finally {
      document.removeEventListener('keydown', spy);
    }
    noMenu();
    expect(document.activeElement, 'Esc 后焦点回触发钮').toBe(trigger);
    expect(spy.mock.calls.filter((c: any[]) => c[0] && c[0].key === 'Escape').length, 'Esc 要 stopPropagation').toBe(0);
    openMenu(trigger);
    key('Tab');
    noMenu();
    const menu = openMenu(trigger);
    fireEvent.mouseDown(menu);
    expect(document.querySelector('[role="menu"]'), '在菜单里按下鼠标不关').not.toBeNull();
    fireEvent.mouseDown(document.body);
    noMenu();
  });

  it('主题菜单：触发钮名称、面板 aria-label、三个单选项的顺序与勾、方向键、Esc', async () => {
    await mountApp('#/overview');
    const trigger = themeTrigger();
    expect(trigger.getAttribute('aria-label')).toBe('主题：暗');
    expect(trigger.getAttribute('aria-haspopup')).toBe('menu');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(trigger.id).not.toBe('');
    const menu = openMenu(trigger);
    expect(menu.getAttribute('aria-label')).toBe('主题');
    expect(trigger.getAttribute('aria-controls')).toBe(menu.id);
    const its = menuItems(menu);
    expect(its.map((i) => i.getAttribute('role'))).toEqual(['menuitemradio', 'menuitemradio', 'menuitemradio']);
    expect(its.map((i) => textOf(i))).toEqual(['跟随系统', '亮', '暗']);
    expect(its.map((i) => i.getAttribute('aria-checked'))).toEqual(['false', 'false', 'true']);
    expect(document.activeElement).toBe(its[0]);
    key('ArrowDown');
    key('ArrowDown');
    expect(document.activeElement).toBe(its[2]);
    key('ArrowDown');
    expect(document.activeElement, '循环').toBe(its[0]);
    key('ArrowUp');
    expect(document.activeElement).toBe(its[2]);
    key('Home');
    expect(document.activeElement).toBe(its[0]);
    key('End');
    expect(document.activeElement).toBe(its[2]);
    key('Escape');
    noMenu();
    expect(document.activeElement, 'Esc 后焦点回触发钮').toBe(trigger);
    expect(document.documentElement.hasAttribute('data-theme'), 'Esc 不选中').toBe(false);
  });
});

describe('D05 主题', () => {
  it('缺省无 data-theme，触发钮名称是主题：暗', async () => {
    await mountApp('#/overview');
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
    expect(themeTrigger().getAttribute('aria-label')).toBe('主题：暗');
  });

  it('经菜单依次选亮、跟随系统、暗：data-theme 依次是 light、system、去掉，触发钮名称与勾随之变', async () => {
    await mountApp('#/overview');
    const steps = [
      { pick: '亮', theme: 'light', label: '主题：亮', checked: 1 },
      { pick: '跟随系统', theme: 'system', label: '主题：跟随系统', checked: 0 },
      { pick: '暗', theme: null, label: '主题：暗', checked: 2 },
    ];
    for (const step of steps) {
      const trigger = themeTrigger();
      const menu = openMenu(trigger);
      const its = menuItems(menu);
      const target = its.find((i) => textOf(i) === step.pick) as HTMLElement;
      fireEvent.click(target);
      noMenu();
      expect(document.documentElement.getAttribute('data-theme'), '选 ' + step.pick + ' 后的 data-theme').toBe(step.theme);
      const after = themeTrigger();
      expect(after.getAttribute('aria-label')).toBe(step.label);
      expect(document.activeElement, '选中后焦点回触发钮').toBe(after);
      const again = menuItems(openMenu(after));
      expect(again.map((i) => i.getAttribute('aria-checked')).indexOf('true'), '当前偏好带勾').toBe(step.checked);
      key('Escape');
    }
  });

  it('键盘选中也一样：方向键移到亮，Enter 选中', async () => {
    await mountApp('#/overview');
    openMenu(themeTrigger());
    key('ArrowDown');
    key('Enter');
    noMenu();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(themeTrigger().getAttribute('aria-label')).toBe('主题：亮');
  });

  it('html 与 body 其余属性不变、没有内联样式、不写存储', async () => {
    await mountApp('#/overview');
    const htmlBefore = attrsOf(document.documentElement);
    const bodyBefore = attrsOf(document.body);
    expect(htmlBefore.style, 'html 无内联样式').toBeUndefined();
    expect(bodyBefore.style, 'body 无内联样式').toBeUndefined();
    for (const pick of ['亮', '跟随系统', '暗']) {
      const menu = openMenu(themeTrigger());
      fireEvent.click(menuItems(menu).find((i) => textOf(i) === pick) as HTMLElement);
      expect(attrsOf(document.documentElement), '选 ' + pick + ' 后 html 的其余属性').toEqual(htmlBefore);
      expect(attrsOf(document.body), '选 ' + pick + ' 后 body 的属性').toEqual(bodyBefore);
      expect(document.documentElement.hasAttribute('style')).toBe(false);
      expect(document.body.hasAttribute('style')).toBe(false);
    }
    expect(window.localStorage.length, '偏好只存内存').toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it('applyTheme 是唯一写 data-theme 的函数：亮 light、跟随系统 system、暗去掉', async () => {
    const mod: any = await import('../src/shell/theme');
    expect(typeof mod.applyTheme, 'src/shell/theme.ts 应导出 applyTheme').toBe('function');
    const html = document.documentElement;
    const before = attrsOf(html);
    mod.applyTheme('light');
    expect(html.getAttribute('data-theme')).toBe('light');
    mod.applyTheme('system');
    expect(html.getAttribute('data-theme')).toBe('system');
    mod.applyTheme('dark');
    expect(html.hasAttribute('data-theme')).toBe(false);
    expect(attrsOf(html)).toEqual(before);
    expect(html.hasAttribute('style')).toBe(false);
    expect(document.body.hasAttribute('class') && document.body.className !== '').toBe(false);
  });

  it('偏好跨路由保持（App 里的内存状态）', async () => {
    await mountApp('#/overview');
    fireEvent.click(menuItems(openMenu(themeTrigger())).find((i) => textOf(i) === '亮') as HTMLElement);
    expect(ctrl('2')).toBe(false);
    expect(currentIds()).toEqual(['tasks']);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(themeTrigger().getAttribute('aria-label')).toBe('主题：亮');
    await settle();
  });

  it('触发钮悬停 400ms 后出现名称相同的工具提示', async () => {
    vi.useFakeTimers();
    await mountApp('#/overview');
    const wrap = themeTrigger().parentElement as HTMLElement;
    fireEvent.mouseEnter(wrap);
    advance(399);
    expect(document.querySelector('[role="tooltip"]'), '399ms 时还没有提示').toBeNull();
    advance(1);
    const tip = document.querySelector('[role="tooltip"]');
    expect(tip, '400ms 时出现提示').not.toBeNull();
    expect(textOf(tip)).toBe('主题：暗');
  });
});

describe('S3 Logo 与图标', () => {
  it('Logo：内联 svg，viewBox、尺寸、两条 path 的 d 逐字取自画布，填色不在内联样式里', async () => {
    await mountApp('#/overview');
    const svg = header().querySelector('svg[role="img"]') as Element;
    expect(svg, '标题栏里应有 role=img 的 Logo').not.toBeNull();
    expect(svg.getAttribute('aria-label')).toBe('Themis Tally 标识');
    expect(svg.getAttribute('viewBox')).toBe('0 0 937 1079');
    expect(svg.getAttribute('width')).toBe('18');
    expect(svg.getAttribute('height')).toBe('20');
    const paths = Array.from(svg.querySelectorAll('path'));
    expect(paths.length).toBe(2);
    const mark = paths.find((p) => p.getAttribute('fill-rule') === 'evenodd') as Element;
    expect(mark, '盾与天平那条 path 带 fill-rule evenodd').toBeTruthy();
    const tally = paths.find((p) => p !== mark) as Element;
    expect(mark.getAttribute('d')).toBe(LOGO.mark);
    expect(tally.getAttribute('d')).toBe(LOGO.tally);
    paths.forEach((p) => expect(p.hasAttribute('style'), '填色写在 CSS 类里，不写内联样式').toBe(false));
    expect(svg.classList.contains('tt-i'), 'Logo 不用 tt-i 类').toBe(false);
  });

  it('图标与画布一致：9 个 Tab、仓库切换、主题三态、刷新、添加仓库', async () => {
    await mountApp('#/overview?mock=data');
    for (const id of ['overview', 'tasks', 'roles', 'runtimes', 'secrets', 'logs', 'plugins', 'history', 'settings']) {
      sameShape(tab(id).querySelector('svg'), 'tab:' + id);
    }
    const folderSvgs = repoTrigger().querySelectorAll('svg');
    expect(folderSvgs.length, '仓库切换钮里有两个图标').toBe(2);
    sameShape(folderSvgs[0], 'folder-open');
    sameShape(folderSvgs[1], 'chevron-down');
    sameShape(themeTrigger().querySelector('svg'), 'moon');
    const menu = openMenu(repoTrigger());
    sameShape(menuItems(menu)[2].querySelector('svg'), 'folder-plus');
    key('Escape');
    for (const [pick, name] of [['亮', 'sun'], ['跟随系统', 'monitor']]) {
      fireEvent.click(menuItems(openMenu(themeTrigger())).find((i) => textOf(i) === pick) as HTMLElement);
      sameShape(themeTrigger().querySelector('svg'), name);
    }
    const refresh = buttonByText(document.body, '刷新');
    sameShape(refresh.querySelector('svg'), 'refresh');
  });
});
"""

# Tab 栏、计数与状态段（P4；D03）
PROBE_TABBAR = PRELUDE + r"""
describe('D03 Tab 栏与状态段', () => {
  it('计数：夹具里待验收 2 加要你决定 1，Tab 上显示 3，链接 aria-label 写明数量，别的 Tab 没有计数', async () => {
    await mountApp('#/overview?mock=data');
    const all = nav().querySelectorAll('[data-tab-count]');
    expect(all.length, '恰有一个计数胶囊').toBe(1);
    const tasks = tab('tasks');
    expect(tasks.contains(all[0]), '计数在任务 Tab 里').toBe(true);
    expect(textOf(all[0])).toBe('3');
    expect(tasks.getAttribute('aria-label')).toBe('任务（3 项需要你判断）');
    expect(document.querySelectorAll('[data-tab-count]').length).toBe(1);
  });

  it('没有 mock 参数时同样读到夹具，计数是 3', async () => {
    await mountApp('#/overview');
    expect(textOf(badge())).toBe('3');
    expect(segCount('运行中')).toBe('1');
    expect(segCount('需要你判断')).toBe('3');
  });

  it('计数为 0（empty）或未读到（loading、error）时不渲染计数胶囊', async () => {
    for (const mock of ['empty', 'loading', 'error']) {
      const r = await mountApp('#/overview?mock=' + mock);
      expect(badge(), 'mock=' + mock + ' 时不该有计数胶囊').toBeNull();
      expect(document.querySelector('[data-tab-count]')).toBeNull();
      r.unmount();
    }
  });

  it('状态段：aria-live=polite，title 含 kit 版本与仓库名；上次更新与 kit 版本带 tt-hide-narrow，两个计数链接不带', async () => {
    await mountApp('#/overview');
    const seg = segment();
    expect(seg.getAttribute('title') || '').toContain('2.12.0');
    expect(seg.getAttribute('title') || '').toContain('demo-repo');
    const upd = updateEl() as HTMLElement;
    expect(upd, '应有 aria-live=off 的上次更新').not.toBeNull();
    expect(seg.contains(upd), '上次更新在状态段里').toBe(true);
    expect(upd.classList.contains('tt-hide-narrow')).toBe(true);
    expect(upd.getAttribute('aria-live')).toBe('off');
    const kit = Array.from(seg.querySelectorAll('*')).find((e) => e.children.length === 0 && textOf(e) === 'kit 2.12.0');
    expect(kit, '应有文字为 kit 2.12.0 的 kit 版本').toBeTruthy();
    expect((kit as Element).closest('.tt-hide-narrow'), 'kit 版本带 tt-hide-narrow').not.toBeNull();
    for (const prefix of ['运行中', '需要你判断']) {
      const link = segLink(prefix);
      expect(link.tagName.toLowerCase()).toBe('a');
      expect(link.getAttribute('href')).toBe('#/tasks');
      expect(link.closest('.tt-hide-narrow'), prefix + ' 计数不带 tt-hide-narrow').toBeNull();
    }
    expect(updateEl()!.closest('a'), '上次更新不是链接').toBeNull();
  });

  it('点状态段的计数链接：无修饰键拦下并跳到任务', async () => {
    await mountApp('#/overview');
    expect(fireEvent.click(segLink('运行中'))).toBe(false);
    expect(window.location.hash).toBe('#/tasks');
    expect(currentIds()).toEqual(['tasks']);
    await settle();
    expect(clickKeepUrl(segLink('需要你判断'), { ctrlKey: true }), '带修饰键走默认行为，应用不拦截').toBe(false);
    expect(window.location.hash).toBe('#/tasks');
  });

  it('上次更新：有数据时是「上次更新 … 前」，随假计时器变化', async () => {
    vi.useFakeTimers();
    await mountApp('#/overview?mock=data');
    const t0 = textOf(updateEl());
    expect(t0).toMatch(/^上次更新/);
    expect(t0).toMatch(/前$/);
    await advanceAsync(125000);
    const t1 = textOf(updateEl());
    expect(t1, '过了两分多钟，文字应变化').not.toBe(t0);
    expect(t1).toMatch(/^上次更新/);
    expect(t1).toMatch(/前$/);
  });

  it('loading：上次更新写「正在读取…」，两个计数显示 —', async () => {
    await mountApp('#/overview?mock=loading');
    expect(textOf(updateEl())).toBe('正在读取…');
    expect(segCount('运行中')).toBe('—');
    expect(segCount('需要你判断')).toBe('—');
  });

  it('error：上次更新写「读取失败 · 时:分:秒」，两个计数显示 —', async () => {
    await mountApp('#/overview?mock=error');
    expect(textOf(updateEl())).toMatch(/^读取失败 · \d{2}:\d{2}:\d{2}$/);
    expect(segCount('运行中')).toBe('—');
    expect(segCount('需要你判断')).toBe('—');
  });

  it('empty：计数为 0；offline：数据照常，上次更新后接「· 可能已过期」', async () => {
    const r = await mountApp('#/overview?mock=empty');
    expect(segCount('运行中')).toBe('0');
    expect(segCount('需要你判断')).toBe('0');
    r.unmount();
    await mountApp('#/overview?mock=offline');
    expect(textOf(updateEl())).toMatch(/^上次更新.*前 · 可能已过期$/);
    expect(segCount('运行中')).toBe('1');
    expect(segCount('需要你判断')).toBe('3');
    expect(textOf(badge())).toBe('3');
  });

  it('不在页面框架里的路由（陈列页）不渲染上次更新，状态段与 Tab 栏仍在', async () => {
    await mountApp('#/showcase');
    expect(updateEl(), '陈列页没有页面状态，不渲染上次更新').toBeNull();
    expect(segment()).toBeTruthy();
    expect(tabLinks().length).toBe(9);
  });
});
"""

# 页面框架与禁用入口（P7、P8；D09、D11）
PROBE_FRAME = PRELUDE + r"""
const NO_POINTER: string[] = __NO_POINTER__;

const ok = (data: any) => ({ ok: true, exit_code: 0, data, output: [], messages: [], command: ['demo', 'cmd'], elapsed_ms: 0 });
const bad = (messages: string[]) => ({ ok: false, exit_code: 2, data: null, output: [], messages, command: ['status', '--x'], elapsed_ms: 0 });

async function frameComponent() {
  const mod: any = await import('../src/shell/PageFrame');
  const F = mod.PageFrame ?? mod.default;
  expect(F, 'src/shell/PageFrame.tsx 应导出 PageFrame').toBeTruthy();
  return F;
}
function makeEmptyElement() {
  return (
    <>
      <h3>空空如也</h3>
      <p>没有任何东西</p>
    </>
  );
}
// 合同只写「empty（空态标题与说明）」，没定形状：默认传既带 title、description 又是可渲染元素的混合对象，
// 读成 {title, description} 或读成 ReactNode 的实现都能用它
function makeEmptyProp() {
  return Object.assign(Object.create(makeEmptyElement()), { title: '空空如也', description: '没有任何东西' });
}
async function mountFrame(load: any, extra: any = {}, strict = false) {
  const F = await frameComponent();
  const { children: kids, ...rest } = extra;
  const el = (
    <F
      title="测试页"
      description="说明文字"
      load={load}
      isEmpty={(d: any) => Array.isArray(d) && d.length === 0}
      empty={makeEmptyProp()}
      {...rest}
    >
      {kids ?? ((d: any) => <div id="gate-body">{JSON.stringify(d)}</div>)}
    </F>
  );
  const out = render(strict ? <React.StrictMode>{el}</React.StrictMode> : el);
  await settle();
  return out;
}
function body(): HTMLElement | null {
  return document.getElementById('gate-body');
}
function controlled() {
  const ds: any[] = [];
  const load = vi.fn(() => {
    const d = deferred();
    ds.push(d);
    return d.promise;
  });
  return { ds, load };
}
async function finish(d: any, value: any) {
  await act(async () => {
    d.resolve(value);
  });
  await settle();
}

describe('D09 页面框架', () => {
  it('首次加载：299ms 无骨架，300ms 出现骨架；根元素 data-page-state=loading', async () => {
    vi.useFakeTimers();
    const load = vi.fn(() => new Promise(() => {}));
    await mountFrame(load);
    expect(load).toHaveBeenCalledTimes(1);
    expect(pageRoot().getAttribute('data-page-state')).toBe('loading');
    advance(299);
    expect(document.querySelector('.tt-skel'), '299ms 时还没有骨架').toBeNull();
    advance(1);
    expect(document.querySelectorAll('.tt-skel').length, '300ms 时出现骨架').toBeGreaterThan(0);
    expect(body()).toBeNull();
  });

  it('页面头：h1 标题、说明、操作、刷新钮（缺省「刷新」，可改文字）', async () => {
    const load = vi.fn(async () => ok(['A']));
    await mountFrame(load, { actions: <button type="button" id="gate-action">操作甲</button> });
    expect(textOf(document.querySelector('h1'))).toBe('测试页');
    expect(textOf(document.body)).toContain('说明文字');
    expect(document.getElementById('gate-action')).not.toBeNull();
    expect(maybeButton(document.body, '刷新'), '缺省刷新钮文字是「刷新」').not.toBeNull();
    cleanup();
    await mountFrame(load, { refreshLabel: '重新检查' });
    expect(maybeButton(document.body, '重新检查')).not.toBeNull();
    expect(maybeButton(document.body, '刷新')).toBeNull();
  });

  it('有数据：data-page-state=data，渲染 children(data)，没有骨架，没有 role=status', async () => {
    const load = vi.fn(async () => ok(['A', 'B']));
    await mountFrame(load);
    expect(pageRoot().getAttribute('data-page-state')).toBe('data');
    expect(textOf(body())).toBe('["A","B"]');
    expect(document.querySelector('.tt-skel')).toBeNull();
    expect(pageRoot().getAttribute('data-stale')).not.toBe('true');
    expect(document.querySelector('[role="status"]'), '页面框架不渲染 role=status').toBeNull();
  });

  it('空：isEmpty 为真时渲染空态标题与说明，不调用 children', async () => {
    // 合同只写「empty（空态标题与说明）」，没定形状：依次试 既带 title、description 又是可渲染元素的混合对象、
    // 纯元素、{title, description} 对象，任何一种能把标题与说明渲染出来就算满足；三种都渲染不出才红
    const load = vi.fn(async () => ok([]));
    const children = vi.fn((d: any) => <div id="gate-body">{JSON.stringify(d)}</div>);
    const shapes: any[] = [makeEmptyProp(), makeEmptyElement(), { title: '空空如也', description: '没有任何东西' }];
    let shown = false;
    for (const empty of shapes) {
      try {
        await mountFrame(load, { empty, children });
      } catch (e) {
        cleanup();
        continue;
      }
      const text = textOf(document.body);
      if (text.includes('空空如也') && text.includes('没有任何东西')) {
        shown = true;
        break;
      }
      cleanup();
    }
    expect(shown, '空态的标题与说明应出现在页面里（empty 按混合对象、元素、{title, description} 任一种形状传入）').toBe(true);
    expect(pageRoot().getAttribute('data-page-state')).toBe('empty');
    expect(children, '空态不调用 children').not.toHaveBeenCalled();
    expect(body()).toBeNull();
  });

  it('命令失败：命令、退出码、报错原文都是纯文本；点重试再调一次加载函数', async () => {
    const load = vi.fn(async () => bad(['ERROR <img src=x onerror=alert(1)> 坏了', 'ERROR 第二行']));
    await mountFrame(load);
    expect(pageRoot().getAttribute('data-page-state')).toBe('error');
    const root = document.body;
    const text = textOf(root);
    expect(text).toContain('没能读到数据');
    expect(text).toContain('status --x');
    expect(text).toMatch(/返回退出码\s*2/);
    expect(text).toContain('内核报错如下（纯文本，已脱敏）：');
    const pre = root.querySelector('pre');
    expect(pre, '报错放在 pre 里').not.toBeNull();
    expect((pre as Element).textContent, 'messages 用换行连起来，按纯文本显示').toBe('ERROR <img src=x onerror=alert(1)> 坏了\nERROR 第二行');
    expect(root.querySelector('img'), '报错原文不能被当成 HTML').toBeNull();
    expect(body()).toBeNull();
    const retry = buttonByText(root, '重试');
    expect(retry.getAttribute('data-variant')).toBe('primary');
    fireEvent.click(retry);
    await settle();
    expect(load, '点重试再调一次').toHaveBeenCalledTimes(2);
  });

  it('Promise 被拒：出错块只写「没有收到服务的回应」', async () => {
    const load = vi.fn(() => Promise.reject(new Error('boom')));
    await mountFrame(load);
    expect(pageRoot().getAttribute('data-page-state')).toBe('error');
    expect(textOf(document.body)).toContain('没有收到服务的回应');
    expect(textOf(document.body)).not.toMatch(/退出码/);
    expect(document.querySelector('pre'), '没有内核报错可放').toBeNull();
  });

  it('重试成功后回到数据态', async () => {
    let n = 0;
    const load = vi.fn(async () => (n++ === 0 ? bad(['ERROR x']) : ok(['OK'])));
    await mountFrame(load);
    fireEvent.click(buttonByText(document.body, '重试'));
    await settle();
    expect(pageRoot().getAttribute('data-page-state')).toBe('data');
    expect(textOf(body())).toBe('["OK"]');
  });

  it('刷新：已有数据时保留数据、不出骨架，刷新钮 aria-busy 且禁用，结果回来后更新', async () => {
    vi.useFakeTimers();
    const { ds, load } = controlled();
    await mountFrame(load);
    await finish(ds[0], ok(['A']));
    expect(textOf(body())).toBe('["A"]');
    fireEvent.click(buttonByText(document.body, '刷新'));
    expect(load).toHaveBeenCalledTimes(2);
    expect(textOf(body()), '刷新时保留旧数据').toBe('["A"]');
    const busy = document.querySelector('button[aria-busy="true"]') as HTMLButtonElement;
    expect(busy, '刷新钮进入加载态（aria-busy）').not.toBeNull();
    expect(busy.disabled, '加载态按钮禁用').toBe(true);
    advance(600);
    expect(document.querySelector('.tt-skel'), '刷新时不出骨架').toBeNull();
    expect(textOf(body())).toBe('["A"]');
    await finish(ds[1], ok(['B']));
    expect(textOf(body())).toBe('["B"]');
    expect(document.querySelector('button[aria-busy="true"]'), '结果回来后退出加载态').toBeNull();
    expect(pageRoot().getAttribute('data-page-state')).toBe('data');
  });

  it('刷新后按新结果重新判断：数据变空则显示空态', async () => {
    const { ds, load } = controlled();
    await mountFrame(load);
    await finish(ds[0], ok(['A']));
    fireEvent.click(buttonByText(document.body, '刷新'));
    await finish(ds[1], ok([]));
    expect(pageRoot().getAttribute('data-page-state')).toBe('empty');
    expect(body()).toBeNull();
  });

  it('只认最近一次请求：StrictMode 下先发的请求后回来，结果被丢弃', async () => {
    const { ds, load } = controlled();
    await mountFrame(load, {}, true);
    expect(ds.length).toBeGreaterThanOrEqual(1);
    await finish(ds[ds.length - 1], ok(['NEW']));
    for (let i = 0; i < ds.length - 1; i += 1) {
      await finish(ds[i], ok(['OLD']));
    }
    expect(textOf(body()), '过期的回应不能覆盖最近一次请求的结果').toBe('["NEW"]');
  });

  it('只认最近一次请求：出错后连续触发重试与刷新，旧回应后到也被丢弃', async () => {
    const ds: any[] = [];
    let first = true;
    const load = vi.fn(() => {
      if (first) {
        first = false;
        return Promise.resolve(bad(['ERROR x']));
      }
      const d = deferred();
      ds.push(d);
      return d.promise;
    });
    await mountFrame(load);
    for (const label of ['重试', '刷新']) {
      const b = maybeButton(document.body, label);
      if (b && !b.disabled) fireEvent.click(b);
    }
    expect(ds.length, '至少发出一次新请求').toBeGreaterThanOrEqual(1);
    await finish(ds[ds.length - 1], ok(['NEW']));
    for (let i = 0; i < ds.length - 1; i += 1) {
      await finish(ds[i], ok(['OLD']));
    }
    expect(textOf(body())).toBe('["NEW"]');
  });

  it('卸载后回应到达不再写状态（没有 console.error）', async () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      const { ds, load } = controlled();
      const r = await mountFrame(load);
      r.unmount();
      await finish(ds[0], ok(['LATE']));
      expect(spy).not.toHaveBeenCalled();
    } finally {
      spy.mockRestore();
    }
  });
});

describe('D11 禁用的写操作入口', () => {
  async function actionComponent() {
    const mod: any = await import('../src/shell/DisabledAction');
    const DA = mod.DisabledAction ?? mod.default;
    expect(DA, 'src/shell/DisabledAction.tsx 应导出 DisabledAction').toBeTruthy();
    return DA;
  }

  it('Tooltip 包 disabled Button，Button 带 pointer-events:none 的类；399ms 无提示，400ms 出现「第二阶段接入」', async () => {
    vi.useFakeTimers();
    const DA = await actionComponent();
    render(<DA label="删除" variant="danger" size="sm" />);
    const btn = document.querySelector('button') as HTMLButtonElement;
    expect(btn).not.toBeNull();
    expect(btn.disabled, '原生 disabled').toBe(true);
    expect(textOf(btn)).toBe('删除');
    expect(btn.getAttribute('data-variant')).toBe('danger');
    expect(btn.getAttribute('data-size')).toBe('sm');
    const wrap = btn.parentElement as HTMLElement;
    expect(wrap.classList.contains('tt-tooltip-wrap'), 'Button 外面是 Tooltip 的包裹 span').toBe(true);
    expect(NO_POINTER.length, 'src/shell/*.css 里应有声明 pointer-events:none 的类').toBeGreaterThan(0);
    expect(Array.from(btn.classList).some((c) => NO_POINTER.includes(c)), 'Button 应带一个 pointer-events:none 的类，实际 ' + btn.className).toBe(true);
    fireEvent.mouseEnter(wrap);
    advance(399);
    expect(document.querySelector('[role="tooltip"]'), '399ms 时还没有提示').toBeNull();
    advance(1);
    const tip = document.querySelector('[role="tooltip"]');
    expect(tip, '400ms 时出现提示').not.toBeNull();
    expect(textOf(tip)).toBe('第二阶段接入');
    fireEvent.mouseLeave(wrap);
    expect(document.querySelector('[role="tooltip"]'), '移开后提示消失').toBeNull();
  });

  it('reason 可改；icon 渲染在按钮里；variant 与 size 透传', async () => {
    vi.useFakeTimers();
    const DA = await actionComponent();
    render(<DA label="更改…" reason="接入本机服务后可用" variant="secondary" size="md" icon={<svg id="gate-icon" />} />);
    const btn = document.querySelector('button') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect(btn.querySelector('#gate-icon'), 'icon 在按钮里').not.toBeNull();
    expect(textOf(btn)).toContain('更改…');
    expect(btn.getAttribute('data-variant')).toBe('secondary');
    fireEvent.mouseEnter(btn.parentElement as HTMLElement);
    advance(400);
    expect(textOf(document.querySelector('[role="tooltip"]'))).toBe('接入本机服务后可用');
  });
});
"""
# 页面占位、App 级五态、状态分组（P10、S7；D10、D07 的 App 级、D03 的计数口径）。用 api 替身记录各页调用的函数
PROBE_PAGES = PRELUDE + r"""
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

const PAGES = [
  { id: 'overview', title: '总览', fn: 'getStatus' },
  { id: 'tasks', title: '任务', fn: 'getStatus' },
  { id: 'roles', title: '角色与模型', fn: 'getRoles' },
  { id: 'runtimes', title: 'CLI 运行时', fn: 'getRuntimes' },
  { id: 'secrets', title: '凭据', fn: 'listSecrets' },
  { id: 'logs', title: '日志与用量', fn: 'getUsage' },
  { id: 'plugins', title: '插件', fn: 'getPlugins' },
  { id: 'history', title: '历史与审计', fn: 'getHistory' },
  { id: 'settings', title: '设置', fn: 'getMeta' },
];
const EMPTIES = [
  { id: 'overview', title: '还没有 attempt', desc: '在规划端用 /dispatch-pi 派遣第一个任务' },
  { id: 'tasks', title: '还没有 attempt', desc: '在规划端用 /dispatch-pi 派遣第一个任务' },
  { id: 'runtimes', title: '还没有登记的 runtime', desc: '' },
  { id: 'secrets', title: '还没有要检查的凭据变量', desc: '' },
  { id: 'plugins', title: '还没有插件', desc: '' },
  { id: 'history', title: '还没有配置历史', desc: '' },
];
const ALL_STATES = [
  'PREPARING', 'PREPARED', 'PREPARE_FAILED', 'RUNNING', 'COLLECTING', 'NEEDS_REVIEW', 'PASS', 'ACCEPTED_WITH_EXCEPTION',
  'REVISE', 'BLOCKED', 'ESCALATE', 'INFRA_FAILURE', 'TIMEOUT', 'CANCELLED', 'INTEGRATED', 'ABANDONED', 'SUPERSEDED',
];
const RUNNING = ['PREPARING', 'RUNNING', 'COLLECTING'];
const NEEDS = ['NEEDS_REVIEW', 'TIMEOUT', 'CANCELLED', 'INFRA_FAILURE', 'ESCALATE', 'BLOCKED'];

function statusRow(state: string, n: number) {
  return {
    attempt: 'task-' + n + '/attempt-001', task_id: 'task-' + n, plan_version: 1, attempt_no: 1, state, started: true,
    exit_code: 0, wall_seconds: 1.5, events_ok: true, violations: 0, checks: '-', check_mode: null, verdict: null,
    failure_class: null, human_minutes: null, tokens: null, cost: null, cost_status: 'unknown',
  };
}
function statusEnvelope(rows: any[]) {
  return { ok: true, exit_code: 0, data: rows, output: [], messages: [], command: ['status'], elapsed_ms: 0 };
}
function bodyText(): string {
  return textOf(document.body);
}

describe('D10 页面占位', () => {
  it('9 页各用自己的加载函数；有数据时显示「夹具数据已读到」加函数名；h1 是页面标题', async () => {
    for (const p of PAGES) {
      Object.values(hoisted.spies).forEach((s: any) => s.mockClear());
      const r = await mountApp('#/' + p.id + '?mock=data');
      expect(hoisted.spies[p.fn], p.id + ' 页应调用 ' + p.fn).toHaveBeenCalled();
      expect(pageRoot().getAttribute('data-page-state'), p.id).toBe('data');
      expect(textOf(document.querySelector('h1')), p.id).toBe(p.title);
      expect(bodyText(), p.id + ' 页应显示「夹具数据已读到」').toContain('夹具数据已读到');
      expect(bodyText(), p.id + ' 页应写出函数名 ' + p.fn).toContain(p.fn);
      r.unmount();
    }
  });

  it('列表数据写条数：状态页读到 7 行', async () => {
    for (const id of ['overview', 'tasks']) {
      const r = await mountApp('#/' + id + '?mock=data');
      expect(bodyText(), id).toMatch(/7/);
      r.unmount();
    }
  });

  it('总览说明是「仓库名 · kit 版本」（来自 getMeta）；角色与凭据页的说明；凭据页刷新钮叫「重新检查」', async () => {
    let r = await mountApp('#/overview?mock=data');
    expect(hoisted.spies.getMeta, '总览要读 getMeta').toHaveBeenCalled();
    const lines = Array.from(document.querySelectorAll('*')).filter((e) => e.children.length === 0).map((e) => textOf(e));
    expect(lines.some((t) => /^demo-repo · .*2\.12\.0$/.test(t)), '总览说明应形如「demo-repo · kit 2.12.0」，实际有：' + lines.filter((t) => t.includes('demo-repo')).join(' | ')).toBe(true);
    expect(maybeButton(document.body, '刷新')).not.toBeNull();
    r.unmount();
    r = await mountApp('#/roles?mock=data');
    expect(bodyText()).toContain('四个角色各用哪个 CLI 与模型；方案可以一键切换');
    r.unmount();
    r = await mountApp('#/secrets?mock=data');
    expect(bodyText()).toContain('这里只显示每个环境变量在哪一层找到，从不显示值');
    expect(maybeButton(document.body, '重新检查'), '凭据页刷新钮叫「重新检查」').not.toBeNull();
    expect(maybeButton(document.body, '刷新')).toBeNull();
  });

  it('?mock=empty：5 个列表资源的页面显示各自的空态标题与说明；没写空态的页照常显示数据', async () => {
    for (const e of EMPTIES) {
      const r = await mountApp('#/' + e.id + '?mock=empty');
      expect(pageRoot().getAttribute('data-page-state'), e.id).toBe('empty');
      expect(bodyText(), e.id).toContain(e.title);
      if (e.desc) expect(bodyText(), e.id).toContain(e.desc);
      expect(bodyText(), e.id + ' 空态里不该再有「夹具数据已读到」').not.toContain('夹具数据已读到');
      r.unmount();
    }
    for (const id of ['roles', 'logs', 'settings']) {
      const r = await mountApp('#/' + id + '?mock=empty');
      expect(pageRoot().getAttribute('data-page-state'), id + ' 没有空态，empty 开关对它不生效').toBe('data');
      r.unmount();
    }
  });
});

describe('P10 App 级五态（经 ?mock= 演示）', () => {
  it('data：数据态，Tab 计数 3，运行中 1，需要你判断 3，没有断线提示', async () => {
    await mountApp('#/overview?mock=data');
    expect(pageRoot().getAttribute('data-page-state')).toBe('data');
    expect(textOf(badge())).toBe('3');
    expect(segCount('运行中')).toBe('1');
    expect(segCount('需要你判断')).toBe('3');
    expect(document.querySelector('[data-stale="true"]')).toBeNull();
    expect(document.querySelector('[role="alert"]')).toBeNull();
  });

  it('loading：骨架 299ms 无、300ms 有，数据不出现，计数 —，没有计数胶囊', async () => {
    vi.useFakeTimers();
    await mountApp('#/overview?mock=loading');
    expect(pageRoot().getAttribute('data-page-state')).toBe('loading');
    advance(299);
    expect(document.querySelector('.tt-skel')).toBeNull();
    advance(1);
    expect(document.querySelectorAll('.tt-skel').length).toBeGreaterThan(0);
    expect(bodyText()).not.toContain('夹具数据已读到');
    expect(segCount('运行中')).toBe('—');
    expect(badge()).toBeNull();
  });

  it('empty：空态，没有计数胶囊', async () => {
    await mountApp('#/overview?mock=empty');
    expect(pageRoot().getAttribute('data-page-state')).toBe('empty');
    expect(badge()).toBeNull();
  });

  it('连接胶囊：offline 以外的开关都是 connected，值取自 src/mock/shell.ts（pid 18244、启动于 2026-10-18 09:41:07、事件流）；offline 是 disconnected 已断开', async () => {
    for (const mock of ['data', 'loading', 'empty', 'error']) {
      const r = await mountApp('#/overview?mock=' + mock);
      expect(header().querySelector('button[data-state="connected"]'), 'mock=' + mock).not.toBeNull();
      if (mock === 'data') {
        const pill = header().querySelector('button[data-state="connected"]') as HTMLElement;
        fireEvent.click(pill);
        const text = textOf(document.getElementById(pill.getAttribute('aria-controls') || ''));
        expect(text).toContain('18244');
        expect(text).toContain('2026-10-18 09:41:07');
        expect(text).toContain('已订阅 /api/v1/events');
      }
      r.unmount();
    }
    await mountApp('#/overview?mock=offline');
    const pill = header().querySelector('button[data-state="disconnected"]') as HTMLElement;
    expect(pill, 'offline 时应是 disconnected').not.toBeNull();
    expect(textOf(pill)).toContain('已断开');
    fireEvent.click(pill);
    const text = textOf(document.getElementById(pill.getAttribute('aria-controls') || ''));
    expect(text).toContain('18244');
    expect(text).toContain('已断开');
    expect(text).not.toContain('已订阅');
  });

  it('error：出错块（纯文本报错、退出码 2、命令），点重试再读一次，计数 —', async () => {
    await mountApp('#/overview?mock=error');
    const root = document.body;
    expect(pageRoot().getAttribute('data-page-state')).toBe('error');
    expect(textOf(root)).toContain('没能读到数据');
    expect(textOf(root)).toMatch(/status/);
    expect(textOf(root)).toMatch(/返回退出码\s*2/);
    const pre = root.querySelector('pre') as Element;
    expect(pre, '报错放在 pre 里').not.toBeNull();
    expect(pre.textContent).toBe('ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied');
    expect(segCount('需要你判断')).toBe('—');
    const before = hoisted.spies.getStatus.mock.calls.length;
    fireEvent.click(buttonByText(root, '重试'));
    await settle();
    expect(hoisted.spies.getStatus.mock.calls.length, '点重试要再调一次加载函数').toBeGreaterThan(before);
  });

  it('offline：数据照常显示，danger 提示条（role=alert）、可能已过期标签、data-stale=true、禁用的重新连接，胶囊已断开', async () => {
    vi.useFakeTimers();
    await mountApp('#/overview?mock=offline');
    const root = pageRoot();
    expect(root.getAttribute('data-page-state')).toBe('data');
    expect(root.getAttribute('data-stale')).toBe('true');
    expect(bodyText()).toContain('夹具数据已读到');
    const alerts = document.querySelectorAll('[role="alert"]');
    expect(alerts.length, '页面头下方一条 role=alert 的提示条').toBe(1);
    expect(textOf(alerts[0])).toContain('与本机服务的连接断开。下面是断开前的数据，可能已过期。');
    expect(alerts[0].getAttribute('data-tone')).toBe('danger');
    const reconnect = buttonByText(alerts[0], '重新连接');
    expect(reconnect.disabled, '重新连接是禁用的写操作入口').toBe(true);
    fireEvent.mouseEnter(reconnect.parentElement as HTMLElement);
    advance(400);
    expect(textOf(document.querySelector('[role="tooltip"]'))).toBe('接入本机服务后可用');
    const tag = Array.from(document.querySelectorAll('[data-tone="neutral"]')).find((e) => textOf(e) === '可能已过期');
    expect(tag, '标题旁有 neutral Tag「可能已过期」').toBeTruthy();
    expect(header().querySelector('button[data-state="disconnected"]')).not.toBeNull();
  });
});

describe('S7 状态分组（待验收与要你决定计入 Tab 计数，运行中单独数）', () => {
  it('17 个状态与一个未知状态各自单独出现一行时，计数落在 UI 文档 3.4 的分组里', async () => {
    for (const state of ALL_STATES.concat(['FUTURE_STATE'])) {
      hoisted.overrides.getStatus = () => Promise.resolve(statusEnvelope([statusRow(state, 1)]));
      const r = await mountApp('#/overview');
      const needs = NEEDS.includes(state);
      const running = RUNNING.includes(state);
      if (needs) {
        expect(textOf(badge()), state + ' 属于待验收或要你决定，Tab 计数应是 1').toBe('1');
      } else {
        expect(badge(), state + ' 不属于这两组，不该有计数胶囊').toBeNull();
      }
      expect(segCount('需要你判断'), state + ' 的需要你判断').toBe(needs ? '1' : '0');
      expect(segCount('运行中'), state + ' 的运行中').toBe(running ? '1' : '0');
      r.unmount();
    }
  });

  it('混合行数：计数按行数算', async () => {
    const states = ['NEEDS_REVIEW', 'NEEDS_REVIEW', 'ESCALATE', 'BLOCKED', 'TIMEOUT', 'PASS', 'PASS', 'RUNNING', 'COLLECTING', 'INTEGRATED'];
    hoisted.overrides.getStatus = () => Promise.resolve(statusEnvelope(states.map((s, i) => statusRow(s, i + 1))));
    await mountApp('#/tasks');
    expect(textOf(badge())).toBe('5');
    expect(tab('tasks').getAttribute('aria-label')).toBe('任务（5 项需要你判断）');
    expect(segCount('需要你判断')).toBe('5');
    expect(segCount('运行中')).toBe('2');
  });
});
"""

# 陈列页：收集与排序（D12），内容（P11）
PROBE_SHOWCASE = PRELUDE + r"""
const NAMES: string[] = __SHOWCASE_NAMES__;
const BASE = ['button', 'tag', 'status-tag', 'card', 'banner', 'icon-button', 'menu', 'dialog', 'drawer', 'toast'];
const FORMS = ['text-field', 'form-dialog', 'segmented', 'switch-checkbox', 'tabs', 'table', 'key-value', 'empty-state', 'skeleton', 'connection', 'breadcrumb'];
const SHELL = ['page-states', 'disabled-action'];
const STATES = [
  'PREPARING', 'PREPARED', 'PREPARE_FAILED', 'RUNNING', 'COLLECTING', 'NEEDS_REVIEW', 'PASS', 'ACCEPTED_WITH_EXCEPTION',
  'REVISE', 'BLOCKED', 'ESCALATE', 'INFRA_FAILURE', 'TIMEOUT', 'CANCELLED', 'INTEGRATED', 'ABANDONED', 'SUPERSEDED',
];
const TONES = ['neutral', 'info', 'attention', 'success', 'warning', 'danger', 'escalate', 'brand'];
const VARIANTS = ['primary', 'secondary', 'ghost', 'danger'];
const SIZES = ['sm', 'md', 'lg'];
const SPECIMENS = ['一个汉字正好两个英文字符宽', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', '12345678901234567890123456', '日志 attempt-001 已通过 OK'];

beforeEach(() => {
  vi.useFakeTimers();
});

async function mountShowcase() {
  return mountApp('#/showcase');
}
function demo(name: string): HTMLElement {
  const nodes = document.querySelectorAll('[data-demo="' + name + '"]');
  expect(nodes.length, '应恰有一个 data-demo="' + name + '" 的节').toBe(1);
  return nodes[0] as HTMLElement;
}
function demoValues(root: ParentNode = document): string[] {
  return Array.from(root.querySelectorAll('[data-demo]')).map((e) => e.getAttribute('data-demo') as string);
}
function wrapper(name: string): HTMLElement {
  const el = document.querySelector('[data-showcase="' + name + '"]');
  expect(el, '找不到 data-showcase="' + name + '"').not.toBeNull();
  return el as HTMLElement;
}
function press(btn: HTMLElement) {
  focusOn(btn);
  fireEvent.click(btn);
}
function columns(text: string): number {
  let n = 0;
  for (const ch of Array.from(text)) {
    n += /[一-鿿]/.test(ch) ? 2 : 1;
  }
  return n;
}
function checkedIndex(radios: HTMLElement[]) {
  return radios.findIndex((r) => r.getAttribute('aria-checked') === 'true');
}

describe('D12 陈列页收集与排序', () => {
  it('data-showcase 的值与顺序等于目录里 *Showcase.tsx 文件名的排序结果（门禁每次现读目录）', async () => {
    await mountShowcase();
    const got = Array.from(document.querySelectorAll('[data-showcase]')).map((e) => e.getAttribute('data-showcase'));
    expect(got).toEqual(NAMES);
    expect(new Set(got).size, '每个模块只收一次').toBe(got.length);
    for (const el of Array.from(document.querySelectorAll('[data-showcase]'))) {
      expect(el.parentElement && el.parentElement.closest('[data-showcase]'), '各节互不嵌套').toBeNull();
      expect(el.children.length, 'data-showcase=' + el.getAttribute('data-showcase') + ' 里应有内容').toBeGreaterThan(0);
    }
  });

  it('ShowcasePage 的根是 div.showcase，页头 h1 组件陈列加说明；不放主题按钮，不用 PageFrame', async () => {
    await mountShowcase();
    const root = document.querySelector('.showcase') as HTMLElement;
    expect(root, '应有 .showcase 根').not.toBeNull();
    expect(root.tagName.toLowerCase()).toBe('div');
    const h1 = root.querySelector('h1') as Element;
    expect(h1, '陈列页根里应有 h1').not.toBeNull();
    expect(textOf(h1)).toBe('组件陈列');
    expect(document.querySelectorAll('h1').length).toBe(1);
    expect(textOf(root).length, '页头还有一行说明').toBeGreaterThan('组件陈列'.length);
    const themed = Array.from(root.querySelectorAll('button')).filter((b) => ['亮', '暗', '跟随系统'].includes(textOf(b)));
    expect(themed.length, '主题改由标题栏的菜单切换，陈列页不放主题按钮').toBe(0);
    expect(root.querySelector('[aria-pressed]'), '陈列页不放按下态的主题按钮').toBeNull();
    expect(document.querySelector('[data-page-state]')).toBeNull();
  });

  it('data-demo 的顺序：已知三组（基础 10 节、表单 11 节、外壳 2 节）按此相对顺序出现，其余取值放行；各节落在各自的模块里', async () => {
    await mountShowcase();
    const all = demoValues();
    const known = new Set(BASE.concat(FORMS, SHELL));
    expect(all.filter((v) => known.has(v)), '已知三组的取值按 基础、表单、外壳 的相对顺序出现').toEqual(BASE.concat(FORMS, SHELL));
    expect(demoValues(wrapper('BaseShowcase'))).toEqual(BASE);
    expect(demoValues(wrapper('FormsShowcase'))).toEqual(FORMS);
    expect(demoValues(wrapper('ShellShowcase'))).toEqual(SHELL);
    expect(new Set(all).size, 'data-demo 的取值不能重复').toBe(all.length);
  });

  it('整页只有一个 role=status（轻提示常驻的那一个）；没有文字的按钮都有 aria-label；框架不多渲染 role=status', async () => {
    await mountShowcase();
    expect(document.querySelectorAll('[role="status"]').length).toBe(1);
    expect(textOf(document.querySelector('[role="status"]'))).toBe('');
    const bad = Array.from(document.querySelectorAll('button'))
      .filter((b) => textOf(b) === '')
      .filter((b) => !(b.getAttribute('aria-label') || '').trim());
    expect(bad.length, '没有文字又没有 aria-label 的按钮').toBe(0);
  });
});

describe('P11 陈列页内容（基础组件与样张）', () => {
  it('BaseShowcase 列出 17 个状态的 title、8 种色调、4 种按钮变体与 3 种尺寸、加载按钮、role=alert、关闭提示', async () => {
    await mountShowcase();
    const base = wrapper('BaseShowcase');
    for (const code of STATES) {
      expect(base.querySelector('[title="' + code + '"]'), '状态 ' + code).not.toBeNull();
    }
    for (const tone of TONES) {
      expect(base.querySelector('[data-tone="' + tone + '"]'), '色调 ' + tone).not.toBeNull();
    }
    for (const v of VARIANTS) {
      expect(base.querySelector('button[data-variant="' + v + '"]'), '按钮变体 ' + v).not.toBeNull();
    }
    for (const s of SIZES) {
      expect(base.querySelector('button[data-size="' + s + '"]'), '按钮尺寸 ' + s).not.toBeNull();
    }
    expect(base.querySelector('button[aria-busy="true"]'), '加载态按钮').not.toBeNull();
    expect(base.querySelector('[role="alert"]'), 'danger 提示条').not.toBeNull();
    expect(base.querySelector('[aria-label="关闭提示"]'), 'info 提示条的关闭按钮').not.toBeNull();
  });

  it('五节原子带 data-demo，顺序是 button、tag、status-tag、card、banner，各节有 showcase__h2 标题', async () => {
    await mountShowcase();
    const secs = BASE.slice(0, 5).map(demo);
    for (let i = 1; i < secs.length; i += 1) {
      expect(secs[i - 1].compareDocumentPosition(secs[i]) & Node.DOCUMENT_POSITION_FOLLOWING, BASE[i] + ' 应在 ' + BASE[i - 1] + ' 之后').toBeTruthy();
    }
    expect(textOf(secs[0].querySelector('.showcase__h2'))).toBe('Button 按钮');
    expect(textOf(secs[1].querySelector('.showcase__h2'))).toBe('Tag 标签');
    expect(textOf(secs[2].querySelector('.showcase__h2'))).toBe('StatusTag 状态标签');
    expect(textOf(secs[3].querySelector('.showcase__h2'))).toBe('Card 卡片');
    expect(textOf(secs[4].querySelector('.showcase__h2'))).toBe('Banner 提示条');
  });

  it('字体样张：三组 400、500、600，每组 4 行、每行去两端 | 后 26 列，文字与约定一致，不含可交互元素', async () => {
    await mountShowcase();
    const specimens = document.querySelectorAll('[data-font-specimen]');
    expect(specimens.length, '应恰有一个样张节').toBe(1);
    const root = specimens[0] as HTMLElement;
    expect(wrapper('BaseShowcase').contains(root), '样张在 BaseShowcase 里').toBe(true);
    expect(textOf(root.querySelector('.showcase__h2'))).toBe('字体 · 等距更纱黑体 SC');
    const groups = Array.from(root.querySelectorAll('[data-font-weight]')) as HTMLElement[];
    expect(groups.map((g) => g.getAttribute('data-font-weight'))).toEqual(['400', '500', '600']);
    expect(Array.from(root.querySelectorAll('.showcase__label')).map((e) => textOf(e))).toEqual(['Regular 400', '500 按 Regular', 'SemiBold 600']);
    for (const group of groups) {
      const rows = Array.from(group.querySelectorAll('[data-specimen-row]')).map((r) => r.textContent || '');
      expect(rows.length, group.getAttribute('data-font-weight') + ' 组应有 4 行').toBe(4);
      for (const row of rows) {
        expect(row.startsWith('|') && row.endsWith('|'), '行首尾各有一个 |：' + row).toBe(true);
        expect(columns(row.slice(1, -1)), '每行 26 列：' + row).toBe(26);
      }
      expect(rows.map((r) => r.slice(1, -1))).toEqual(SPECIMENS);
    }
    expect(root.querySelectorAll('button, a, input, select, textarea, [tabindex], [role="button"]').length).toBe(0);
    const buttonH2 = Array.from(document.querySelectorAll('.showcase__h2')).find((h) => /Button/.test(textOf(h))) as Element;
    expect(root.compareDocumentPosition(buttonH2) & Node.DOCUMENT_POSITION_FOLLOWING, '样张在 Button 一节之前').toBeTruthy();
  });
});

describe('P11 陈列页内容（浮层演示）', () => {
  it('图标按钮：至少三个只有图标的按钮，其一禁用；整页没有文字的按钮都有 aria-label', async () => {
    await mountShowcase();
    const sec = demo('icon-button');
    const iconOnly = Array.from(sec.querySelectorAll('button')).filter((b) => textOf(b) === '');
    expect(iconOnly.length).toBeGreaterThanOrEqual(3);
    expect(iconOnly.some((b) => (b as HTMLButtonElement).disabled)).toBe(true);
    const bad = Array.from(document.querySelectorAll('button'))
      .filter((b) => textOf(b) === '')
      .filter((b) => !(b.getAttribute('aria-label') || '').trim());
    expect(bad.length).toBe(0);
  });

  it('菜单：「更多操作」打开菜单，Enter 选中第一项后「上次选择：…」随之变化', async () => {
    await mountShowcase();
    const sec = demo('menu');
    const last = () => textOf(sec).split('上次选择：')[1];
    const before = last();
    expect(before).not.toBeUndefined();
    press(buttonByText(sec, '更多操作'));
    const menu = document.querySelector('[role="menu"]');
    expect(menu, '点「更多操作」后应出现菜单').not.toBeNull();
    expect(document.activeElement).toBe((menu as Element).querySelector('[role="menuitem"]'));
    key('Enter');
    expect(document.querySelector('[role="menu"]')).toBeNull();
    expect(last()).not.toBe('');
    expect(last()).not.toBe(before);
  });

  it('对话框：「打开对话框」出现模态框，底栏有「取消」「确定」，取消后焦点回触发按钮', async () => {
    await mountShowcase();
    const trigger = buttonByText(demo('dialog'), '打开对话框');
    press(trigger);
    const dialog = document.querySelector('[role="dialog"]') as HTMLElement;
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    buttonByText(dialog, '确定');
    fireEvent.click(buttonByText(dialog, '取消'));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('抽屉：「打开抽屉」出现非模态抽屉，Esc 关闭并回到触发按钮', async () => {
    await mountShowcase();
    const trigger = buttonByText(demo('drawer'), '打开抽屉');
    press(trigger);
    const drawer = document.querySelector('[role="dialog"]') as HTMLElement;
    expect(drawer.getAttribute('aria-modal')).toBe('false');
    expect(drawer.querySelectorAll('button').length).toBeGreaterThanOrEqual(2);
    key('Escape');
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('轻提示：「弹出轻提示」后 role=status 里出现文字和关闭钮，点关闭钮后清空', async () => {
    await mountShowcase();
    const status = document.querySelector('[role="status"]') as HTMLElement;
    expect(textOf(status)).toBe('');
    press(buttonByText(demo('toast'), '弹出轻提示'));
    expect(textOf(status)).not.toBe('');
    fireEvent.click(status.querySelector('button[aria-label="关闭提示"]') as HTMLElement);
    expect(textOf(status)).toBe('');
  });

  it('模态对话框打开时 Ctrl+数字快捷键不切页', async () => {
    await mountShowcase();
    press(buttonByText(demo('dialog'), '打开对话框'));
    expect(ctrl('2'), '模态框打开时不拦').toBe(true);
    expect(window.location.hash).toBe('#/showcase');
  });
});

describe('P11 陈列页内容（表单与数据演示）', () => {
  it('11 节表单演示各恰一个、顺序对、都在轻提示之后，复用 showcase__section 与 showcase__h2', async () => {
    await mountShowcase();
    const toast = demo('toast');
    const secs = FORMS.map(demo);
    for (let i = 0; i < secs.length; i += 1) {
      const before = i === 0 ? toast : secs[i - 1];
      expect(before.compareDocumentPosition(secs[i]) & Node.DOCUMENT_POSITION_FOLLOWING, FORMS[i] + ' 应在上一节之后').toBeTruthy();
      expect(secs[i].classList.contains('showcase__section')).toBe(true);
      const h2 = secs[i].querySelector('h2.showcase__h2');
      expect(h2, FORMS[i] + ' 应有 showcase__h2 标题').not.toBeNull();
      expect(textOf(h2)).not.toMatch(/Button/);
    }
  });

  it('新演示里没有主题字样的按钮', async () => {
    await mountShowcase();
    for (const name of FORMS.concat(SHELL)) {
      const sec = demo(name);
      const themed = Array.from(sec.querySelectorAll('button')).filter((b) => ['亮', '暗', '跟随系统'].includes(textOf(b)));
      expect(themed.length, name + ' 里不该有主题字样的按钮').toBe(0);
    }
  });

  it('输入框一节：默认、带帮助、出错、禁用的输入框和一个下拉，都有 label', async () => {
    await mountShowcase();
    const sec = demo('text-field');
    const inputs = Array.from(sec.querySelectorAll('input')) as HTMLInputElement[];
    const selects = Array.from(sec.querySelectorAll('select')) as HTMLSelectElement[];
    expect(inputs.length).toBeGreaterThanOrEqual(4);
    expect(selects.length).toBeGreaterThanOrEqual(1);
    expect(inputs.some((i) => i.disabled)).toBe(true);
    expect(inputs.some((i) => i.getAttribute('aria-invalid') === 'true')).toBe(true);
    for (const el of [...inputs, ...selects]) {
      expect(el.labels && el.labels.length, '每个控件都有 label').toBeGreaterThan(0);
    }
  });

  it('表单对话框：框里有输入框与下拉、取消与确定；输入框上 mousedown 不被阻止、能聚焦；遮罩上仍被阻止', async () => {
    await mountShowcase();
    press(buttonByText(demo('form-dialog'), '打开表单对话框'));
    const dialog = document.querySelector('[role="dialog"]') as HTMLElement;
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    const input = dialog.querySelector('input') as HTMLInputElement;
    expect(input).not.toBeNull();
    expect(dialog.querySelector('select')).not.toBeNull();
    buttonByText(dialog, '取消');
    buttonByText(dialog, '确定');
    expect(fireEvent.mouseDown(input)).toBe(true);
    focusOn(input);
    expect(document.activeElement).toBe(input);
    expect(fireEvent.mouseDown(document.querySelector('.tt-dialog-scrim') as HTMLElement)).toBe(false);
  });

  it('分段、开关与复选框、页签三节的键盘与点击行为', async () => {
    await mountShowcase();
    const radios = Array.from(demo('segmented').querySelectorAll<HTMLElement>('[role="radiogroup"] [role="radio"]'));
    expect(radios.length).toBeGreaterThanOrEqual(2);
    const at = checkedIndex(radios);
    focusOn(radios[at]);
    key('ArrowRight');
    expect(checkedIndex(radios)).toBe((at + 1) % radios.length);
    const sec = demo('switch-checkbox');
    for (const role of ['switch', 'checkbox']) {
      const el = Array.from(sec.querySelectorAll<HTMLElement>('[role="' + role + '"]')).find((e) => e.getAttribute('aria-disabled') !== 'true') as HTMLElement;
      expect(el, '应有可用的 ' + role).toBeTruthy();
      const before = el.getAttribute('aria-checked');
      fireEvent.click(el);
      expect(el.getAttribute('aria-checked')).not.toBe(before);
      focusOn(el);
      key(' ');
      expect(el.getAttribute('aria-checked')).toBe(before);
    }
    const tabs = Array.from(demo('tabs').querySelectorAll<HTMLElement>('[role="tablist"] [role="tab"]'));
    expect(tabs.length).toBeGreaterThanOrEqual(2);
    const cur = tabs.findIndex((t) => t.getAttribute('aria-selected') === 'true');
    focusOn(tabs[cur]);
    key('ArrowRight');
    const next = (cur + 1) % tabs.length;
    expect(tabs[next].getAttribute('aria-selected')).toBe('true');
    expect(demo('tabs').querySelector('[role="tabpanel"]')!.getAttribute('aria-labelledby')).toBe(tabs[next].id);
  });

  it('表格一节：切 40、44、52 三档；用时与 token 数字列；Enter 或点击行后「上次打开：…」变化', async () => {
    await mountShowcase();
    const sec = demo('table');
    const radios = Array.from(sec.querySelectorAll<HTMLElement>('[role="radiogroup"] [role="radio"]'));
    expect(radios.length).toBe(3);
    ['40', '44', '52'].forEach((n, i) => {
      expect(textOf(radios[i])).toContain(n);
      fireEvent.click(radios[i]);
      expect((sec.querySelector('table') as HTMLElement).getAttribute('data-row-height')).toBe(n);
    });
    const table = sec.querySelector('table') as HTMLElement;
    const heads = Array.from(table.querySelectorAll('th')).map((th) => textOf(th));
    expect(heads.some((h) => h.includes('用时'))).toBe(true);
    expect(heads.some((h) => /token/i.test(h))).toBe(true);
    expect(table.querySelectorAll('td.tt-num').length).toBeGreaterThan(0);
    expect(table.querySelectorAll('tr[tabindex="0"]').length).toBe(1);
    const last = () => textOf(sec).split('上次打开：')[1];
    const rows = () => Array.from(sec.querySelectorAll<HTMLElement>('tbody tr'));
    focusOn(rows().find((r) => r.getAttribute('tabindex') === '0') as HTMLElement);
    key('Enter');
    const afterEnter = last();
    expect((afterEnter || '').trim().length).toBeGreaterThan(0);
    fireEvent.click(rows()[rows().length - 1]);
    expect(last()).not.toBe(afterEnter);
  });

  it('键值列表、空状态、面包屑三节', async () => {
    await mountShowcase();
    const kv = demo('key-value');
    expect(kv.querySelectorAll('dl dt').length).toBeGreaterThanOrEqual(2);
    expect(kv.querySelectorAll('dl dd').length).toBeGreaterThanOrEqual(2);
    const empty = demo('empty-state');
    expect(empty.querySelector('svg[aria-hidden="true"]'), '空状态应有图标').not.toBeNull();
    const nav2 = demo('breadcrumb').querySelector('nav') as HTMLElement;
    expect(nav2.getAttribute('aria-label')).toBe('面包屑');
    const current = nav2.querySelector('[aria-current="page"]') as HTMLElement;
    expect(current).not.toBeNull();
    expect(current.tagName).toBe('SPAN');
  });

  it('骨架屏一节：「加载 2 秒」299ms 无、300ms 有、2 秒后消失；「加载 0.2 秒」全程不出现', async () => {
    await mountShowcase();
    const sec = demo('skeleton');
    const two = buttonByText(sec, '加载 2 秒');
    const fast = buttonByText(sec, '加载 0.2 秒');
    expect(sec.querySelector('.tt-skel')).toBeNull();
    press(two);
    advance(299);
    expect(sec.querySelector('.tt-skel')).toBeNull();
    advance(1);
    expect(sec.querySelectorAll('.tt-skel').length).toBeGreaterThan(0);
    advance(1900);
    expect(sec.querySelector('.tt-skel')).toBeNull();
    press(fast);
    for (let i = 0; i < 20; i += 1) {
      advance(50);
      expect(sec.querySelector('.tt-skel')).toBeNull();
    }
  });

  it('连接胶囊一节：三态并排，各自能点开浮层，浮层里有 pid 与启动于', async () => {
    await mountShowcase();
    const sec = demo('connection');
    const states = Array.from(sec.querySelectorAll('[data-state]')).map((el) => el.getAttribute('data-state'));
    for (const s of ['connected', 'reconnecting', 'disconnected']) {
      expect(states).toContain(s);
    }
    const pills = Array.from(sec.querySelectorAll<HTMLElement>('button[aria-expanded]'));
    expect(pills.length).toBe(3);
    for (const pill of pills) {
      fireEvent.click(pill);
      expect(pill.getAttribute('aria-expanded')).toBe('true');
      const pop = document.getElementById(pill.getAttribute('aria-controls') || '');
      expect(textOf(pop)).toContain('pid');
      expect(textOf(pop)).toContain('启动于');
      fireEvent.click(pill);
    }
  });
});

describe('P11 陈列页内容（外壳演示）', () => {
  it('page-states：五个链接依次打开 #/overview 的 loading、data、empty、error、offline，点击后切到对应五态', async () => {
    await mountShowcase();
    const sec = demo('page-states');
    const links = Array.from(sec.querySelectorAll('a')) as HTMLAnchorElement[];
    expect(links.length).toBe(5);
    expect(links.map((a) => a.getAttribute('href'))).toEqual(
      ['loading', 'data', 'empty', 'error', 'offline'].map((m) => '#/overview?mock=' + m),
    );
    // 合同只要求 Tab 与状态段计数链接拦截点击；这里的朴素 a href 在浏览器里自己会导航，jsdom 里补上同样的默认行为
    const hashBefore = window.location.hash;
    clickKeepUrl(links[3]);
    if (window.location.hash === hashBefore) {
      window.location.hash = links[3].getAttribute('href') as string;
      await act(async () => {
        window.dispatchEvent(new HashChangeEvent('hashchange'));
      });
    }
    expect(window.location.hash).toBe('#/overview?mock=error');
    await settle();
    expect(pageRoot().getAttribute('data-page-state')).toBe('error');
    expect(currentIds()).toEqual(['overview']);
  });

  it('disabled-action：四个禁用的写操作入口 [切换…]、[更改…]、[删除]、[启用…]，悬停出现提示', async () => {
    await mountShowcase();
    const sec = demo('disabled-action');
    const buttons = Array.from(sec.querySelectorAll('button')) as HTMLButtonElement[];
    expect(buttons.map((b) => textOf(b))).toEqual(['切换…', '更改…', '删除', '启用…']);
    buttons.forEach((b) => expect(b.disabled, textOf(b) + ' 应禁用').toBe(true));
    fireEvent.mouseEnter(buttons[0].parentElement as HTMLElement);
    advance(400);
    expect(textOf(document.querySelector('[role="tooltip"]'))).toBe('第二阶段接入');
  });
});
"""

# 数据层与夹具开关（P9；D06、D07）
PROBE_API = PRELUDE + r"""
const FIX: any = __FIXTURES__;

const CALLS: Array<{ name: string; fix: string; run: (a: any) => Promise<any>; command: string[] | null }> = [
  { name: 'getMeta', fix: 'meta', run: (a) => a.getMeta(), command: null },
  { name: 'getStatus', fix: 'status', run: (a) => a.getStatus(), command: ['status'] },
  { name: 'getAttempt', fix: 'attempt', run: (a) => a.getAttempt('logs-cat', 'attempt-002'), command: ['logs', 'show', 'logs-cat/attempt-002'] },
  {
    name: 'readFile', fix: 'file-executor-report',
    run: (a) => a.readFile('logs-cat', 'attempt-002', 'executor-report.md'),
    command: ['logs', 'cat', 'logs-cat/attempt-002', 'executor-report.md'],
  },
  {
    name: 'readFile', fix: 'file-events',
    run: (a) => a.readFile('logs-cat', 'attempt-002', 'events.jsonl'),
    command: ['logs', 'cat', 'logs-cat/attempt-002', 'events.jsonl'],
  },
  { name: 'getRoles', fix: 'roles', run: (a) => a.getRoles(), command: ['config', 'role', 'show'] },
  { name: 'getProfiles', fix: 'profiles', run: (a) => a.getProfiles(), command: ['config', 'profile', 'show'] },
  { name: 'getPresets', fix: 'presets', run: (a) => a.getPresets(), command: ['config', 'preset', 'list'] },
  { name: 'diffPresets', fix: 'preset-diff', run: (a) => a.diffPresets('default', 'economy'), command: ['config', 'preset', 'diff', 'default', 'economy'] },
  { name: 'getRuntimes', fix: 'runtimes', run: (a) => a.getRuntimes(), command: ['config', 'runtime', 'list'] },
  { name: 'getPlugins', fix: 'plugins', run: (a) => a.getPlugins(), command: ['plugins', 'list'] },
  { name: 'getHistory', fix: 'history', run: (a) => a.getHistory(), command: ['config', 'history'] },
  { name: 'getUsage', fix: 'usage', run: (a) => a.getUsage(), command: ['logs', 'usage'] },
  { name: 'listSecrets', fix: 'secrets', run: (a) => a.listSecrets(), command: null },
];
const EMPTY: Record<string, any> = {
  getStatus: [],
  getRuntimes: { runtimes: [] },
  listSecrets: { secrets: [] },
  getPlugins: { plugins_root_link: false, plugins: [], not_installed: [], problems: [] },
  getHistory: { entries: [], broken_lines: [], external_before_first: 0 },
};
const ERROR_TEXT = 'ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied';
const ENVELOPE_KEYS = ['command', 'data', 'elapsed_ms', 'exit_code', 'messages', 'ok', 'output'];

async function loadApi(): Promise<any> {
  return await import('../src/api');
}
function setMock(value: string | null) {
  window.location.hash = value === null ? '#/overview' : '#/overview?mock=' + value;
}
function commandOk(call: { command: string[] | null }, env: any) {
  expect(Array.isArray(env.command), 'command 是数组').toBe(true);
  expect(env.command.length).toBeGreaterThan(0);
  env.command.forEach((c: any) => expect(typeof c).toBe('string'));
  expect(env.command, 'command 不带 --json').not.toContain('--json');
  if (call.command) expect(env.command).toEqual(call.command);
}
async function never(p: Promise<any>): Promise<boolean> {
  let settled = false;
  p.then(
    () => {
      settled = true;
    },
    () => {
      settled = true;
    },
  );
  await new Promise((r) => setTimeout(r, 25));
  return !settled;
}

describe('D06 数据层', () => {
  it('src/api.ts 导出 13 个读函数', async () => {
    const api = await loadApi();
    for (const name of ['getMeta', 'getStatus', 'getAttempt', 'readFile', 'getRoles', 'getProfiles', 'getPresets', 'diffPresets', 'getRuntimes', 'getPlugins', 'getHistory', 'getUsage', 'listSecrets']) {
      expect(typeof api[name], name).toBe('function');
    }
  });

  it('13 个函数的 data 与 UI 文档第 9 节夹具逐值相等，信封字段齐全', async () => {
    setMock(null);
    const api = await loadApi();
    for (const call of CALLS) {
      const env = await call.run(api);
      const label = call.name + '（' + call.fix + '）';
      expect(Object.keys(env).sort(), label + ' 的信封字段').toEqual(ENVELOPE_KEYS);
      expect(env.ok, label).toBe(true);
      expect(env.exit_code, label).toBe(0);
      expect(env.output, label).toEqual([]);
      expect(env.messages, label).toEqual([]);
      expect(env.elapsed_ms, label).toBe(0);
      expect(env.data, label + ' 的 data').toEqual(FIX[call.fix]);
      commandOk(call, env);
    }
  });

  it('返回已兑现的 Promise：开着假计时器也能在微任务里拿到结果', async () => {
    vi.useFakeTimers();
    setMock(null);
    const api = await loadApi();
    for (const call of CALLS) {
      const p = call.run(api);
      expect(p, call.name + ' 应返回 Promise').toBeInstanceOf(Promise);
      const env = await p;
      expect(env.ok).toBe(true);
    }
  });

  it('每次调用返回夹具的新深拷贝：改了返回值不影响下一次', async () => {
    setMock(null);
    const api = await loadApi();
    for (const call of CALLS) {
      const first = await call.run(api);
      const second = await call.run(api);
      expect(first.data, call.name + ' 两次的 data 不能是同一个对象').not.toBe(second.data);
      expect(first.command).not.toBe(second.command);
      first.messages.push('X');
      first.output.push('X');
      first.command.push('X');
      const data = first.data;
      if (Array.isArray(data)) {
        data.length = 0;
      } else if (data && typeof data === 'object') {
        for (const k of Object.keys(data)) delete data[k];
      }
      const third = await call.run(api);
      expect(third.data, call.name + ' 改了返回值之后下一次仍是夹具').toEqual(FIX[call.fix]);
      expect(third.messages).toEqual([]);
      expect(third.output).toEqual([]);
      if (call.command) expect(third.command).toEqual(call.command);
    }
  });

  it('夹具之外的参数一律 ok:false、exit_code 2、data null、一条 ERROR「夹具里没有这份数据：…」', async () => {
    setMock(null);
    const api = await loadApi();
    const outside: Array<[string, () => Promise<any>]> = [
      ['getAttempt 别的 task', () => api.getAttempt('nope', 'attempt-002')],
      ['getAttempt 别的 attempt', () => api.getAttempt('logs-cat', 'attempt-001')],
      ['readFile 别的路径', () => api.readFile('logs-cat', 'attempt-002', 'candidate.patch')],
      ['readFile 带 cursor', () => api.readFile('logs-cat', 'attempt-002', 'events.jsonl', 'c1-0001a2f3')],
      ['readFile 别的 attempt', () => api.readFile('logs-cat', 'attempt-001', 'executor-report.md')],
      ['readFile 别的 task', () => api.readFile('x', 'attempt-002', 'executor-report.md')],
      ['diffPresets 反过来', () => api.diffPresets('economy', 'default')],
      ['diffPresets 同一个', () => api.diffPresets('default', 'default')],
      ['diffPresets 别的方案', () => api.diffPresets('x', 'y')],
    ];
    for (const [label, run] of outside) {
      const env = await run();
      expect(env.ok, label).toBe(false);
      expect(env.exit_code, label).toBe(2);
      expect(env.data, label).toBeNull();
      expect(env.messages.length, label + ' 应恰有一条 messages').toBe(1);
      expect(env.messages[0], label).toMatch(/^ERROR/);
      expect(env.messages[0], label).toContain('夹具里没有这份数据：');
      expect(Array.isArray(env.command), label + ' 的 command 是数组').toBe(true);
    }
  });
});

describe('D07 夹具开关', () => {
  it('data 与 offline 都照夹具返回', async () => {
    const api = await loadApi();
    for (const mock of ['data', 'offline']) {
      setMock(mock);
      for (const call of CALLS) {
        const env = await call.run(api);
        expect(env.ok, 'mock=' + mock + ' ' + call.name).toBe(true);
        expect(env.data, 'mock=' + mock + ' ' + call.name).toEqual(FIX[call.fix]);
      }
    }
  });

  it('loading：除 getMeta 外永不兑现；getMeta 照常返回', async () => {
    const api = await loadApi();
    setMock('loading');
    for (const call of CALLS) {
      const p = call.run(api);
      if (call.name === 'getMeta') {
        const env = await p;
        expect(env.data).toEqual(FIX.meta);
      } else {
        expect(await never(p), call.name + ' 在 loading 下不该兑现').toBe(true);
      }
    }
  });

  it('error：除 getMeta 外 ok:false、exit_code 2、data null、command 照常、messages 是示意的内核报错', async () => {
    const api = await loadApi();
    setMock('error');
    for (const call of CALLS) {
      const env = await call.run(api);
      if (call.name === 'getMeta') {
        expect(env.ok).toBe(true);
        expect(env.data).toEqual(FIX.meta);
        continue;
      }
      const label = call.name + '（' + call.fix + '）';
      expect(env.ok, label).toBe(false);
      expect(env.exit_code, label).toBe(2);
      expect(env.data, label).toBeNull();
      expect(env.messages, label).toEqual([ERROR_TEXT]);
      commandOk(call, env);
    }
  });

  it('empty：只有 5 个列表资源返回空形状，其余照常；getMeta 不受影响', async () => {
    const api = await loadApi();
    setMock('empty');
    for (const call of CALLS) {
      const env = await call.run(api);
      const label = call.name + '（' + call.fix + '）';
      expect(env.ok, label).toBe(true);
      expect(env.exit_code, label).toBe(0);
      if (call.name in EMPTY) {
        expect(env.data, label + ' 应是空形状').toEqual(EMPTY[call.name]);
        commandOk(call, env);
      } else {
        expect(env.data, label + ' 照常').toEqual(FIX[call.fix]);
      }
    }
  });

  it('每次调用时读开关：地址里的 mock 变了，下一次调用就变；查询里只认 mock', async () => {
    const api = await loadApi();
    setMock('error');
    expect((await api.getStatus()).ok).toBe(false);
    setMock('data');
    expect((await api.getStatus()).ok).toBe(true);
    setMock('empty');
    expect((await api.getStatus()).data).toEqual([]);
    window.location.hash = '#/overview?x=1&mock=error&y=2';
    expect((await api.getStatus()).ok, '多个查询参数时仍认 mock').toBe(false);
    window.location.hash = '#/tasks/a/b?mock=empty';
    expect((await api.getStatus()).data, '路径其余段不影响开关').toEqual([]);
    window.location.hash = '#/overview?other=error';
    expect((await api.getStatus()).ok, '别的查询参数不是开关').toBe(true);
  });
});
"""

# 运行时不连服务（P12；D08）。替身的名字用字符串拼接写出，使探针源码自己不含那四个词
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

describe('D08 运行时不连服务', () => {
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
    expect(calls.length).toBeGreaterThan(0);
  });

  it('逐页、逐个开关值渲染 App（含刷新、重试与点 Tab），四个浏览器网络接口与 sendBeacon 的调用次数都是 0', async () => {
    install();
    vi.useFakeTimers();
    const routes = TABS.map((t) => t.id).concat(['showcase']);
    try {
      for (const mock of [null, 'data', 'loading', 'empty', 'error', 'offline']) {
        for (const id of routes) {
          const r = await mountApp('#/' + id + (mock ? '?mock=' + mock : ''));
          await advanceAsync(1500);
          for (const label of ['刷新', '重新检查', '重试']) {
            const b = maybeButton(document.body, label);
            if (b && !b.disabled) {
              fireEvent.click(b);
              await settle();
            }
          }
          if (id === 'overview') {
            for (const t of TABS) {
              fireEvent.click(tab(t.id));
              await settle();
            }
          }
          await advanceAsync(5000);
          r.unmount();
          expect(calls, '路由 ' + id + '、开关 ' + mock + ' 之后调用过网络接口').toEqual([]);
        }
      }
    } finally {
      restore();
    }
  }, 60000);
});
"""

def pointer_classes(css):
    """css 里声明了 pointer-events:none 的规则，选择器（每项的最后一个复合选择器）里的类名。"""
    classes = set()
    for selector, decls in parse_rules(css):
        if decl_matches(decls, ("pointer-events",), eq="none"):
            for item in split_top(selector):
                classes |= set(re.findall(r"\.([A-Za-z_][\w-]*)", re.split(r"[\s>+~]+", item)[-1]))
    return sorted(classes)


def no_pointer_classes():
    """src/shell/*.css 里声明了 pointer-events:none 的类名（禁用入口的 Button 要带其中一个）。"""
    return pointer_classes(shell_css_text())


def showcase_names():
    """陈列页目录里 *Showcase.tsx 的文件名（去掉 .tsx），按 ASCII 编码顺序排序（与 JS 默认 sort 一致）。每次现读，不写名单。"""
    folder = SRC / "showcase"
    return sorted(p.name[:-4] for p in folder.glob("*Showcase.tsx")) if folder.is_dir() else []


PROBE_SPECS = {
    "route": (PROBE_ROUTE, [f"{SRC_REL}/App.tsx", f"{SRC_REL}/shell/router.ts", f"{SRC_REL}/shell/shortcuts.ts"]),
    "titlebar": (PROBE_TITLEBAR, [f"{SRC_REL}/shell/TitleBar.tsx", f"{SRC_REL}/shell/ShellMenu.tsx", f"{SRC_REL}/shell/theme.ts"]),
    "tabbar": (PROBE_TABBAR, [f"{SRC_REL}/shell/TabBar.tsx"]),
    "frame": (PROBE_FRAME, [f"{SRC_REL}/shell/PageFrame.tsx", f"{SRC_REL}/shell/DisabledAction.tsx"]),
    "pages": (PROBE_PAGES, [f"{SRC_REL}/api.ts"]),
    "showcase": (PROBE_SHOWCASE, [f"{SRC_REL}/showcase/ShowcasePage.tsx"]),
    "api": (PROBE_API, [f"{SRC_REL}/api.ts", f"{SRC_REL}/mock/scenario.ts"]),
    "nonet": (PROBE_NONET, [f"{SRC_REL}/App.tsx"]),
}
PROBE_ORDER = ("route", "titlebar", "tabbar", "frame", "pages", "showcase", "api", "nonet")
P11_GROUPS = ("P11 陈列页内容（基础组件与样张）", "P11 陈列页内容（浮层演示）", "P11 陈列页内容（表单与数据演示）",
              "P11 陈列页内容（外壳演示）")

# 候选里出现其中任何一个，流水线才跑 npm（基线上都没有，没有东西可测）
CANDIDATE_MARKERS = (f"{SRC_REL}/api.ts", f"{SRC_REL}/shell/router.ts", f"{SRC_REL}/shell/TabBar.tsx")


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


def build_probe_source(key):
    source = PROBE_SPECS[key][0]
    if "__LOGO__" in source:
        source = source.replace("__LOGO__", json.dumps(canvas_logo(), ensure_ascii=False))
    if "__ICON_SHAPES__" in source:
        source = source.replace("__ICON_SHAPES__", json.dumps(canvas_icon_shapes(), ensure_ascii=False))
    if "__FIXTURES__" in source:
        source = source.replace("__FIXTURES__", json.dumps({n: doc_fixture(n) for n in FIXTURE_SOURCES}, ensure_ascii=False))
    if "__NO_POINTER__" in source:
        source = source.replace("__NO_POINTER__", json.dumps(no_pointer_classes()))
    if "__SHOWCASE_NAMES__" in source:
        source = source.replace("__SHOWCASE_NAMES__", json.dumps(showcase_names()))
    return source


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


# 流水线前后不该变的文件（相对 desktop/web）
WATCHED = ("package.json", "package-lock.json", "index.html", "vite.config.ts", "tsconfig.json",
           "src/styles/tokens.css", "src/styles/fonts.css", "src/styles/base.css", "src/main.tsx", "src/App.css")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not any((REPO_ROOT / rel).is_file() for rel in CANDIDATE_MARKERS):
        pipe.reason = ("候选里还没有 src/api.ts、src/shell/router.ts、src/shell/TabBar.tsx 中的任何一个（基线），没有东西可测，未调用 npm；"
                       "候选写出这些文件后，流水线才会运行 npm ci、构建、Vitest 和探针")
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
                try:
                    source = build_probe_source(key)
                except (AssertionError, IndexError, AttributeError, OSError) as exc:
                    pipe.probe_skipped[key] = f"探针 {key} 的输入取不出来，未运行：{exc!r}"
                    continue
                name = f"probe-t006-{uid}-{key}.test.tsx"
                result_name = f"result-t006-{uid}-{key}.json"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                result_path = probe_dir / result_name
                written += [path, result_path]
                path.write_text(source, encoding="utf-8", newline="\n")
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

def test_d01_files_in_place():
    """S1 / D01：合同要的文件都在位——api.ts、14 份夹具 JSON 与三个夹具脚本、src/shell/ 的路由与外壳文件、
    icons/frame.tsx、陈列页的新文件、执行端的 shell-no-network 测试、9 个页面文件。"""
    need_dir(f"{SRC_REL}/shell")
    problems = []
    wanted = [f"{SRC_REL}/api.ts", f"{SRC_REL}/icons/frame.tsx", f"{SRC_REL}/showcase/ShowcasePage.tsx",
              f"{SRC_REL}/showcase/showcase.css", f"{SRC_REL}/showcase/BaseShowcase.tsx", f"{SRC_REL}/showcase/ShellShowcase.tsx",
              f"{WEB_REL}/tests/shell-no-network.test.ts"]
    wanted += [f"{SRC_REL}/shell/{name}" for name in SHELL_FILES]
    wanted += [f"{SRC_REL}/mock/{name}" for name in MOCK_TS]
    wanted += [f"{SRC_REL}/mock/{name}.json" for name in FIXTURE_SOURCES]
    for rel in wanted:
        if not (REPO_ROOT / rel).is_file():
            problems.append(f"{rel} 不存在")
    pages = sorted((SRC / "pages").glob("*Page.tsx")) if (SRC / "pages").is_dir() else []
    if len(pages) != 9:
        problems.append(f"{SRC_REL}/pages/ 下应恰有 9 个 *Page.tsx（每页一个文件），实际 {len(pages)} 个")
    for path in pages:
        if "PageFrame" not in _read(path):
            problems.append(f"{path.relative_to(REPO_ROOT).as_posix()}：每页都用 PageFrame")
    if not shell_css_files():
        problems.append(f"{SRC_REL}/shell/ 下没有 *.css（ShellMenu、标题栏、Tab 栏的样式）")
    fail_if(problems, "合同要的文件")


def test_transitional_d02_mock_shell_values():
    """接本机服务那一片（连接状态与最近仓库换成外壳与服务的真实值）推翻。

    D02 / 合同第 7 条：src/mock/shell.ts 放连接状态（offline 时 disconnected）与最近仓库列表；胶囊的 pid、启动时间、
    事件流两种文字、最近仓库 demo-repo 与 docs-site 都写在这里（标明是示意）。"""
    text = _read(need_file(f"{SRC_REL}/mock/shell.ts"))
    problems = [f"shell.ts 里没有「{lit}」" for lit in
                ("demo-repo", "docs-site", "18244", "2026-10-18 09:41:07", "已订阅 /api/v1/events", "已断开", "disconnected", "connected", "offline")
                if lit not in text]
    if "示意" not in text:
        problems.append("shell.ts 里没有标明“示意”（这两样不在 8.9 里，是外壳的事）")
    fail_if(problems, "src/mock/shell.ts")


def test_transitional_d06_api_only_thirteen_functions():
    """后面的片按需补读函数、订阅、作业与写函数时推翻（合同非目标：listAttempts、getConfig、subscribeEvents、写函数等）。

    S1 / D06：src/api.ts 导出第 9 节有示例的 13 个读函数，不多声明后面的片才补的函数；不连服务（见 D08）。"""
    text = _read(need_file(f"{SRC_REL}/api.ts"))
    names = exported_names(text)
    missing = [n for n in API_FUNCTIONS if n not in names]
    early = [n for n in LATER_API if n in names]
    fail_if([f"缺少导出：{missing}"] if missing else [], "api.ts 的 13 个读函数")
    fail_if([f"提前声明了后面的片才补的函数：{early}"] if early else [], "api.ts 的范围")


def test_s2_fixtures_equal_ui_doc():
    """S2 / D06：src/mock/ 下恰有 14 份 JSON，内容与 UI 文档第 9 节对应的代码块逐值相等（门禁自己解析 Markdown 的 json 代码块）。"""
    fail_if(fixture_problems(), "夹具 JSON 与 UI 文档")


def test_d08_no_network_words_in_src():
    """S1 / D08：递归扫 desktop/web/src 下全部文件（不论扩展名），按整词找那四个浏览器网络接口名（词表见 NET_WORDS，合同第 12 条；
    注释与字符串都算），一个都没有；执行端的 tests/shell-no-network.test.ts 带自检样本。"""
    need_dir(SRC_REL)
    need_file(f"{SRC_REL}/api.ts")
    hits = scan_src_words(NET_WORDS)
    fail_if([f"{h}" for h in hits], "src 下出现了不该有的网络接口名（路径:行号: 词）")
    test = _read(need_file(f"{WEB_REL}/tests/shell-no-network.test.ts"))
    problems = []
    for sample in ("prefetchAll", "fetchedAt", "globalThis"):
        if sample not in test:
            problems.append(f"shell-no-network.test.ts 的自检样本里没有 {sample}")
    for word in NET_WORDS:
        if word not in test:
            problems.append(f"shell-no-network.test.ts 里没有提到 {word}")
    fail_if(problems, "shell-no-network.test.ts")


def test_d14_forbidden_sink_words_in_src():
    """D14 / 与 T007 的文件边界：T007 的禁用词检查扫 src/**/*.{ts,tsx}（注释与字符串都算），本片源码一个都不写
    （危险的 HTML 写入接口、动态求值、文档写入、srcdoc、DOM 解析器等，词表见 SINK_WORDS）。"""
    need_dir(f"{SRC_REL}/shell")
    hits = [h for h in scan_src_words(SINK_WORDS, whole_word=False)]
    fail_if(hits, "src 下出现了 T007 禁用词（路径:行号: 词）")


def new_source_files():
    """本片新增或改写的源码：api.ts、mock/*.ts、shell/*.ts(x)、pages/*.tsx、icons/frame.tsx、App.tsx、showcase 下的新文件。"""
    files = [SRC / "api.ts", SRC / "App.tsx", SRC / "icons" / "frame.tsx"]
    for sub in ("mock", "shell", "pages"):
        folder = SRC / sub
        if folder.is_dir():
            files += [p for p in sorted(folder.rglob("*")) if p.suffix in (".ts", ".tsx")]
    for name in ("ShowcasePage.tsx", "BaseShowcase.tsx", "ShellShowcase.tsx"):
        files.append(SRC / "showcase" / name)
    return [p for p in files if p.is_file()]


def test_d14_new_sources_guards():
    """D14 / 公共约定：新增与改写的源码不渲染 role=status（整页只留 Toast 的那一个），不调用 matchMedia、scrollIntoView、
    ResizeObserver、IntersectionObserver；字符串与行注释里不写十六进制颜色和颜色函数（W4 的坑，夹具 JSON 不扫）。"""
    need_dir(f"{SRC_REL}/shell")
    problems = []
    for path in new_source_files():
        label = path.relative_to(WEB).as_posix()
        text = _read(path)
        problems += source_rule_problems(label, text)
        problems += w4_literal_problems(label, text)
    fail_if(problems, "新源码的守卫")


def test_d14_existing_tests_only_mount_changed():
    """D14 / 站主 Q2：font-specimen、showcase-overlays、showcase-forms 三份既有测试只许把「渲染根 App」改成先把 location.hash
    设为 #/showcase 再渲染；it 标题清单与 expect( 条数与基线一致（EXISTING_TEST_TITLES、EXISTING_TEST_EXPECTS，取自 e4be51f），
    仍从 ../src/App 导入 App，不跳过、不 only、不 todo。"""
    problems = []
    for name in EXISTING_TESTS:
        path = WEB / "tests" / f"{name}.test.tsx"
        if not path.is_file():
            problems.append(f"{name}.test.tsx 不存在")
            continue
        text = _read(path)
        titles = [m[1] for m in re.findall(r"^\s*it\(\s*(['\"`])(.*?)\1\s*,", text, re.M)]
        if titles != EXISTING_TEST_TITLES[name]:
            problems.append(f"{name}.test.tsx 的 it 标题与基线不同：{titles}")
        count = len(re.findall(r"expect\(", text))
        if count != EXISTING_TEST_EXPECTS[name]:
            problems.append(f"{name}.test.tsx 的 expect( 条数 {count} 与基线 {EXISTING_TEST_EXPECTS[name]} 不同")
        if "#/showcase" not in text:
            problems.append(f"{name}.test.tsx 里没有先把 location.hash 设为 #/showcase")
        if not re.search(r"location\.hash\s*=", text):
            problems.append(f"{name}.test.tsx 里没有给 location.hash 赋值")
        if not re.search(r"import\s+App\s+from\s+['\"]\.\./src/App['\"]", text):
            problems.append(f"{name}.test.tsx 不再从 ../src/App 导入 App")
        if re.search(r"\b(?:it|test|describe)\.(?:skip|todo|only)\b|\bx(?:it|describe)\(", text):
            problems.append(f"{name}.test.tsx 里有 skip、only 或 todo")
    fail_if(problems, "既有 3 份测试")


def test_d14_new_tests_not_skipped():
    """D14：新测试 desktop/web/tests/shell-*.test.ts(x) 不用 skip、only、todo，至少有 tests/shell-no-network.test.ts。"""
    need_file(f"{WEB_REL}/tests/shell-no-network.test.ts")
    problems = []
    files = sorted((WEB / "tests").glob("shell-*.test.ts")) + sorted((WEB / "tests").glob("shell-*.test.tsx"))
    for path in files:
        text = _read(path)
        if re.search(r"\b(?:it|test|describe)\.(?:skip|todo|only|skipIf|runIf)\b|\bx(?:it|describe)\(|\.only\(|\btodo\(", text):
            problems.append(f"{path.name} 里有 skip、only 或 todo")
        if not re.search(r"^\s*(?:it|test)\(", text, re.M):
            problems.append(f"{path.name} 里没有用例")
    fail_if(problems, "新测试")


def test_d02_logo_and_frame_icons_static():
    """S3 / D02：Logo.tsx 内联 svg（viewBox 0 0 937 1079、18×20、role=img、aria-label），两条 path 的 d 逐字取自 Main 画布 :20，
    盾与天平那条带 fill-rule evenodd，填色写在 CSS 类里（用 logo 令牌），不用 tt-i 类；Logo 不放进 src/icons/；
    icons/frame.tsx 导出合同点名的 6 个图标，fill 与 stroke 只能 none 或 currentColor。"""
    logo = canvas_logo()
    text = _read(need_file(f"{SRC_REL}/shell/Logo.tsx"))
    problems = []
    for key in ("mark", "tally"):
        if logo[key] not in text:
            problems.append(f"Logo.tsx 里没有逐字照抄画布的 {key} 那条 path 的 d")
    for lit in ("937", "1079", "Themis Tally 标识", "evenodd"):
        if lit not in text:
            problems.append(f"Logo.tsx 里没有 {lit}")
    if not re.search(r"""role\s*=\s*["']img["']""", text):
        problems.append("Logo.tsx 没有 role=img")
    if re.search(r"\btt-i\b", text):
        problems.append("Logo.tsx 不能用 tt-i 类")
    if re.search(r"""style\s*=\s*\{\{?[^}]*fill""", text):
        problems.append("Logo.tsx 的填色不能写内联样式")
    css = shell_css_text()
    for token in ("var(--tt-logo-mark)", "var(--tt-logo-tally)"):
        if token not in css:
            problems.append(f"src/shell/*.css 里没有用 {token} 填 Logo")
    icons_dir = SRC / "icons"
    if (icons_dir / "index.tsx").is_file() and "Logo" in _read(icons_dir / "index.tsx"):
        problems.append("Logo 不放进 src/icons/index.tsx")
    frame = _read(need_file(f"{SRC_REL}/icons/frame.tsx"))
    names = exported_names(frame)
    for name in ICON_NAMES:
        if name not in names:
            problems.append(f"icons/frame.tsx 没有导出 {name}")
    for attr, value in re.findall(r"""\b(fill|stroke)\s*=\s*["']([^"']*)["']""", frame):
        if value not in ("none", "currentColor"):
            problems.append(f"icons/frame.tsx 里 {attr}=\"{value}\"：fill 与 stroke 只能 none 或 currentColor")
    fail_if(problems, "Logo 与 frame 图标")


def test_d06_theme_single_writer():
    """D05 / 合同第 6 条：applyTheme(pref) 是唯一写 data-theme 的地方——theme.ts 导出 applyTheme，别的源码（去掉注释）不出现
    data-theme；应用主题不加类、不写内联样式、不动 body、不用 matchMedia。"""
    theme = _read(need_file(f"{SRC_REL}/shell/theme.ts"))
    problems = []
    if "applyTheme" not in exported_names(theme):
        problems.append("theme.ts 没有导出 applyTheme")
    code = strip_ts_comments(theme)
    if "data-theme" not in code:
        problems.append("theme.ts 里没有写 data-theme")
    for pat, why in ((r"classList|className", "不加类"), (r"\.style\b", "不写内联样式"), (r"document\.body", "不动 body"),
                     (r"localStorage|sessionStorage", "偏好只存内存")):
        if re.search(pat, code):
            problems.append(f"theme.ts：{why}")
    for path in new_source_files():
        if path.name == "theme.ts":
            continue
        if "data-theme" in strip_ts_comments(_read(path)):
            problems.append(f"{path.relative_to(WEB).as_posix()}：别的文件不该写 data-theme（唯一写的地方是 applyTheme）")
    fail_if(problems, "主题的单一写入口")


# ---------------------------------------------------------------------------
# S4：框架 CSS 的取值
# ---------------------------------------------------------------------------

def comments_of(css):
    return re.findall(r"/\*(.*?)\*/", css, re.S)


def last_classes(selector_item):
    return set(re.findall(r"\.([\w-]+)", re.split(r"[\s>+~]+", selector_item.strip())[-1]))


def anchor_union(css, names, eq):
    """找声明了 names: eq 的“锚点规则”，返回这些规则以及与它们共用同一个类的所有规则的声明（按源码顺序）；没有锚点返回 None。
    合同没定类名，所以用“同一个类上的几条规则合起来”来判断同一个元素的样式。"""
    classes, anchors = set(), []
    for selector, decls in parse_rules(css):
        if decl_matches(decls, names, eq=eq):
            anchors.append(decls)
            for item in split_top(selector):
                classes |= last_classes(item)
    if not anchors:
        return None
    if not classes:
        return [d for decls in anchors for d in decls]
    out = []
    for selector, decls in parse_rules(css):
        if any(classes & last_classes(item) for item in split_top(selector)):
            out.extend(decls)
    return out


def border_side_ok(decls, side, color):
    return decl_matches(decls, (f"border-{side}",), has=("1px", color)) or (
        decl_matches(decls, (f"border-{side}-width",), eq="1px") and decl_matches(decls, (f"border-{side}-color",), eq=color))


def titlebar_css_problems(css):
    problems = []
    union = anchor_union(css, BG, "var(--tt-titlebar)")
    if union is None:
        return ["标题栏底色：没有规则声明 background: var(--tt-titlebar)"]
    if not decl_matches(union, ("height",), eq="40px"):
        problems.append("标题栏高 40px：承载底色的元素没有 height: 40px")
    if not border_side_ok(union, "bottom", "var(--tt-border)"):
        problems.append("标题栏下边框：承载底色的元素没有 border-bottom: 1px solid var(--tt-border)")
    sides = box_sides(union)
    if sides["right"] != "140px" or sides["left"] != "var(--tt-space-3)":
        problems.append(f"标题栏内边距：承载底色的元素应左 var(--tt-space-3)、右 140px（UI 文档 5.2 :352），实际左 {sides['left']}、右 {sides['right']}")
    if not decl_matches(union, ("gap", "column-gap"), eq="var(--tt-space-2)"):
        problems.append("标题栏元素间距：承载底色的元素没有 gap: var(--tt-space-2)")
    for name, value in union:
        if name in ("overflow", "overflow-x", "overflow-y") and cv(value) in ("hidden", "clip", "auto", "scroll"):
            problems.append(f"标题栏不能设 {name}: {value}（胶囊浮层与两个菜单要盖在内容之上）")
        if name in ("isolation", "transform", "filter", "contain", "will-change", "backdrop-filter", "perspective"):
            problems.append(f"标题栏不能建层叠上下文：{name}")
    return problems


def order_problems(css):
    for _selector, decls in parse_rules(css):
        for name, value in decls:
            if name == "order" and re.fullmatch(r"[1-9]\d*", cv(value)):
                return []
    return ["Tab 栏用 order 排到最下面：没有规则声明 order 为正整数"]


def dot_rule_ok(css, color):
    """8px 圆点：有一条规则声明 background: color，且承载它的元素有 width 与 height 8px。
    尺寸与颜色可以写在同一条规则里，也可以公共类写尺寸、修饰类写颜色（合并共用同一个类的规则，
    或类名以公共类名加 -、_ 为前缀的修饰类，如 .x 与 .x--info、.x-info）。"""
    rules = parse_rules(css)
    size = [(("width",), {"eq": "8px"}), (("height",), {"eq": "8px"})]
    for selector, decls in rules:
        if not decl_matches(decls, BG, eq=color):
            continue
        classes = set()
        for item in split_top(selector):
            classes |= last_classes(item)
        merged = list(decls)
        for other_selector, other_decls in rules:
            if other_decls is decls:
                continue
            for item in split_top(other_selector):
                if any(c in classes or any(k.startswith(c) and k[len(c):len(c) + 1] in ("-", "_") for k in classes) for c in last_classes(item)):
                    merged.extend(other_decls)
                    break
        if all(decl_matches(merged, names, **kw) for names, kw in size):
            return True
    return False


def tabbar_css_problems(css):
    problems = []
    union = anchor_union(css, ("height",), "var(--tt-tabbar-height)")
    if union is None:
        problems.append("Tab 栏高：没有规则声明 height: var(--tt-tabbar-height)")
    else:
        if not decl_matches(union, BG, eq="var(--tt-sidebar)"):
            problems.append("Tab 栏底色：Tab 栏元素没有 background: var(--tt-sidebar)")
        if not border_side_ok(union, "top", "var(--tt-sidebar-hover)"):
            problems.append("Tab 栏上边框：Tab 栏元素没有 border-top: 1px solid var(--tt-sidebar-hover)")
        sides = box_sides(union)
        if sides["left"] != "var(--tt-space-2)" or sides["right"] != "var(--tt-space-2)":
            problems.append(f"Tab 栏左右内边距：应都是 var(--tt-space-2)，实际左 {sides['left']}、右 {sides['right']}")
    problems += order_problems(css)
    if not has_decl(css, ("min-width",), eq="72px"):
        problems.append("Tab 项最小宽：没有规则声明 min-width: 72px")
    if not has_decl(css, ("color",), eq="var(--tt-sidebar-text)"):
        problems.append("Tab 项文字：没有规则声明 color: var(--tt-sidebar-text)")
    if not has_decl(css, ("font",), eq="var(--tt-text-caption)"):
        problems.append("Tab 项字：没有规则声明 font: var(--tt-text-caption)")
    if not has_decl(css, BG, eq="var(--tt-sidebar-hover)", sel=r":hover"):
        problems.append("Tab 项悬停：没有 :hover 规则声明 background: var(--tt-sidebar-hover)")
    if not has_decl(css, BG, eq="var(--tt-sidebar-hover)", sel=r"current"):
        problems.append("当前项底色：没有 aria-current 相关规则声明 background: var(--tt-sidebar-hover)")
    if not has_decl(css, ("color",), eq="var(--tt-sidebar-text-active)", sel=r"current"):
        problems.append("当前项文字：没有 aria-current 相关规则声明 color: var(--tt-sidebar-text-active)")
    if not has_decl(css, ("font",), eq="var(--tt-text-caption-strong)", sel=r"current"):
        problems.append("当前项字：没有 aria-current 相关规则声明 font: var(--tt-text-caption-strong)")
    bar = [(("height",), {"eq": "3px"}), (BG, {"eq": "var(--tt-accent)"}), (("border-radius",), {"has": ("var(--tt-radius-sm)",)}),
           (("left", "right", "inset", "inset-inline"), {"has": ("10px",)})]
    if not rule_has_all(css, bar):
        problems.append("金条：没有一条规则同时有 height 3px、background var(--tt-accent)、border-radius 含 var(--tt-radius-sm)、左右缩进 10px")
    if not rule_has_all(css, [(("width",), {"eq": "1px"}), (BG, {"eq": "var(--tt-sidebar-hover)"})]):
        problems.append("分隔线：没有一条规则同时有 width 1px 与 background var(--tt-sidebar-hover)")
    pill = [(("height",), {"eq": "16px"}), (("min-width",), {"eq": "18px"}), (BG, {"eq": "var(--tt-accent)"}),
            (("color",), {"eq": "var(--tt-on-accent)"}), (("font",), {"eq": "var(--tt-text-caption-strong)"}),
            (("border-radius",), {"eq": "var(--tt-radius-full)"}), (("box-shadow",), {"eq": "0 0 0 2px var(--tt-sidebar)"})]
    if not rule_has_all(css, pill):
        problems.append("计数胶囊：没有一条规则同时有 height 16px、min-width 18px、背景 accent、字色 on-accent、"
                        "font caption-strong、圆角 radius-full、阴影 0 0 0 2px var(--tt-sidebar)")
    if not rule_sides(css, left="var(--tt-space-1)", right="var(--tt-space-1)"):
        problems.append("计数胶囊左右内边距：没有规则声明左右都是 var(--tt-space-1)")
    if not has_decl(css, ("top",), eq="5px"):
        problems.append("计数胶囊位置：没有规则声明 top: 5px")
    if not has_decl(css, ("left",), eq="calc(50% + 5px)"):
        problems.append("计数胶囊位置：没有规则声明 left: calc(50% + 5px)")
    notes = [c for c in comments_of(css) if "画布" in c]
    if not any(re.search(r"600", c) and re.search(r"(?<![\w.])11(?![\w.])", c) for c in notes):
        problems.append("Q3：计数胶囊的字缺一行注释写明画布原值（600 11/16）")
    if not any(re.search(r"(?<![\w.])2(?:px)?(?![\w.])", c) and not re.search(r"600", c) for c in notes):
        problems.append("Q3：金条下方两角的圆角缺一行注释写明画布原值（2）")
    if not dot_rule_ok(css, "var(--tt-sidebar-dot-info)"):
        problems.append("状态段：运行中的 8px 圆点（background var(--tt-sidebar-dot-info)）没有规则")
    if not dot_rule_ok(css, "var(--tt-accent)"):
        problems.append("状态段：需要你判断的 8px 圆点（background var(--tt-accent)）没有规则")
    if not has_decl(css, ("color",), eq="var(--tt-sidebar-text-muted)"):
        problems.append("状态段文字：没有规则声明 color: var(--tt-sidebar-text-muted)")
    if not has_decl(css, ("text-decoration", "text-decoration-line"), has=("underline",), sel=r":hover"):
        problems.append("计数链接悬停：没有 :hover 规则声明 text-decoration: underline")
    return problems


def shell_menu_css_problems(css):
    problems = []
    sel = r"tt-shell-menu"
    checks = [
        ("面板宽 240", ("width",), {"eq": "240px"}),
        ("面板内边距 --tt-space-1", ("padding",), {"eq": "var(--tt-space-1)"}),
        ("面板底 --tt-surface-1", BG, {"eq": "var(--tt-surface-1)"}),
        ("面板 1px --tt-border 边", ("border", "border-width", "border-color"), {"has": ("var(--tt-border)",)}),
        ("面板圆角 --tt-radius-lg", ("border-radius",), {"eq": "var(--tt-radius-lg)"}),
        ("面板阴影 --tt-shadow-2", ("box-shadow",), {"eq": "var(--tt-shadow-2)"}),
        ("面板层级 --tt-z-popover", ("z-index",), {"eq": "var(--tt-z-popover)"}),
        ("面板在触发钮下方 --tt-space-1", ("top", "margin-top", "inset-block-start"), {"has": ("var(--tt-space-1)",)}),
        ("项高 32", ("height", "min-height"), {"eq": "32px"}),
        ("项圆角 --tt-radius-md", ("border-radius",), {"eq": "var(--tt-radius-md)"}),
        ("项字 --tt-text-sm", ("font",), {"eq": "var(--tt-text-sm)"}),
        ("分组标题字 --tt-text-caption", ("font",), {"eq": "var(--tt-text-caption)"}),
        ("分组标题色 --tt-text-3", ("color",), {"eq": "var(--tt-text-3)"}),
        ("右对齐 right: 0", ("right", "inset-inline-end"), {"zero": True}),
        ("左对齐 left: 0", ("left", "inset-inline-start"), {"zero": True}),
    ]
    for desc, names, kw in checks:
        if not has_decl(css, names, sel=sel, **kw):
            problems.append(f"ShellMenu 样式：{desc}——没有 tt-shell-menu* 规则声明 {'/'.join(names)}")
    if not rule_sides(css, sel=sel, left="var(--tt-space-2)", right="var(--tt-space-2)"):
        problems.append("ShellMenu 样式：项左右内边距 --tt-space-2——没有 tt-shell-menu* 规则")
    if not has_decl(css, BG, eq="var(--tt-surface-3)", sel=r"tt-shell-menu.*(?::hover|:focus|focus-visible)"):
        problems.append("ShellMenu 样式：悬停与聚焦底 --tt-surface-3——没有对应规则")
    if not has_decl(css, BG, eq="var(--tt-surface-selected)", sel=r"tt-shell-menu.*(?:checked|selected|active)"):
        problems.append("ShellMenu 样式：选中的单选项底 --tt-surface-selected——没有对应规则")
    if not has_decl(css, ("color",), eq="var(--tt-text-disabled)", sel=r"tt-shell-menu.*disabled"):
        problems.append("ShellMenu 样式：禁用项 --tt-text-disabled——没有对应规则")
    if not has_decl(css, ("color",), eq="var(--tt-tone-success-fg)"):
        problems.append("ShellMenu 样式：勾的颜色 --tt-tone-success-fg——没有规则")
    return problems


def page_frame_css_problems(css):
    problems = []
    for desc, names, kw in (
        ("页面标题 h1 字 --tt-title-lg", ("font",), {"eq": "var(--tt-title-lg)"}),
        ("页面说明字 --tt-text-sm", ("font",), {"eq": "var(--tt-text-sm)"}),
        ("页面说明色 --tt-text-2", ("color",), {"eq": "var(--tt-text-2)"}),
        ("出错块标题色 --tt-danger-text", ("color",), {"eq": "var(--tt-danger-text)"}),
        ("禁用入口的 Button 带 pointer-events:none 的类", ("pointer-events",), {"eq": "none"}),
    ):
        if not has_decl(css, names, **kw):
            problems.append(f"页面框架样式：{desc}——没有规则声明 {'/'.join(names)}")
    return problems


def test_s4_titlebar_css():
    """S4 / D02：标题栏 CSS——高 40px、底 --tt-titlebar、下边框 1px --tt-border、左内边距 --tt-space-3 与右内边距 140px 在同一条规则里、
    元素间距 --tt-space-2；承载底色的规则不设 overflow:hidden，不建层叠上下文。"""
    need_dir(f"{SRC_REL}/shell")
    css = shell_css_text()
    assert css, f"{SRC_REL}/shell/ 下没有 *.css"
    fail_if(titlebar_css_problems(css), "标题栏 CSS")


def test_s4_tabbar_css():
    """S4 / D03：Tab 栏 CSS——高 --tt-tabbar-height、底 --tt-sidebar、上边框、order 排到最下面、项最小宽 72、当前项三样、3px 金条、
    分隔线、计数胶囊（高 16、最小宽 18、accent 底、on-accent 字、caption-strong、radius-full、2px 外圈、距顶 5、水平 50% + 5）、
    Q3 的两行画布原值注释、状态段的圆点与字色。"""
    need_dir(f"{SRC_REL}/shell")
    css = shell_css_text()
    assert css, f"{SRC_REL}/shell/ 下没有 *.css"
    fail_if(tabbar_css_problems(css), "Tab 栏 CSS")


def test_s4_shell_menu_css():
    """S4 / D02：ShellMenu 的 tt-shell-menu* 样式照组件板 :455–460（宽 240、内边距、底、边、圆角、阴影、层级、位置、项高 32 等）；
    ShellMenu.tsx 不复用 tt-menu* 类名。"""
    need_dir(f"{SRC_REL}/shell")
    css = shell_css_text()
    assert css, f"{SRC_REL}/shell/ 下没有 *.css"
    problems = shell_menu_css_problems(css)
    menu = _read(need_file(f"{SRC_REL}/shell/ShellMenu.tsx"))
    if "tt-shell-menu" not in menu:
        problems.append("ShellMenu.tsx 里没有 tt-shell-menu 类名")
    if re.search(r"(?<![\w-])tt-menu(?:__|--|\b)", menu):
        problems.append("ShellMenu.tsx 不复用 tt-menu* 类名")
    fail_if(problems, "ShellMenu")


def test_s4_page_frame_css():
    """S4 / D09、D11：页面框架与禁用入口的 CSS——h1 字 --tt-title-lg、说明字色、出错块标题色、pointer-events:none 的类。"""
    need_dir(f"{SRC_REL}/shell")
    css = shell_css_text()
    assert css, f"{SRC_REL}/shell/ 下没有 *.css"
    fail_if(page_frame_css_problems(css), "页面框架 CSS")


def test_s4_new_css_tokens_and_px_comments():
    """S4 / D14（公共约定）：新增与搬动的 CSS（shell/*.css、showcase/showcase.css、showcase-shell.css、App.css）里层级、圆角、阴影、
    字体只用 --tt-* 令牌，用到的令牌在 tokens.css 里都有；除 0 与 1px 外的 px 字面量，同一行带出处注释（演示用的尺寸写「演示自定」）。"""
    need_dir(f"{SRC_REL}/shell")
    files = new_css_files()
    assert any(p.parent.name == "shell" for p in files), f"{SRC_REL}/shell/ 下没有 *.css"
    tokens = _read(need_file(f"{SRC_REL}/styles/tokens.css"))
    problems = []
    for path in files:
        raw = _read(path)
        label = path.relative_to(WEB).as_posix()
        problems += token_only_problems(label, raw)
        problems += px_literal_problems(label, raw)
        problems += undefined_token_problems(label, raw, tokens)
        problems += w4_literal_problems(label, raw)
    fail_if(problems, "新 CSS 的令牌与 px 注释")


def test_s5_base_css_keeps_hide_narrow():
    """S5：base.css 里仍有 @media (max-width: 1179px) 下 .tt-hide-narrow { display: none }（Tab 栏窄窗口靠它隐藏）。"""
    css = _read(need_file(f"{SRC_REL}/styles/base.css"))
    assert re.search(r"@media\s*\(\s*max-width\s*:\s*1179px\s*\)", css), "base.css 里没有 max-width: 1179px 的媒体查询"
    assert has_decl(css, ("display",), eq="none", sel=r"\.tt-hide-narrow"), "base.css 里 .tt-hide-narrow 不再 display:none"


# ---------------------------------------------------------------------------
# S6 / D12：陈列页的收集写法与搬家
# ---------------------------------------------------------------------------

def showcase_page_problems(text):
    code = strip_ts_comments(text)
    problems = []
    if not re.search(r"import\.meta\.glob\s*(?:<[^>]*>)?\s*\(\s*['\"]\./\*Showcase\.tsx['\"]", code):
        problems.append("没有用 import.meta.glob('./*Showcase.tsx', …) 收集（只同一目录、不含子目录）")
    if not re.search(r"eager\s*:\s*true", code):
        problems.append("import.meta.glob 没有 eager: true（急切导入）")
    if re.search(r"from\s+['\"]\./\w*Showcase['\"]", code) or re.search(r"import\(\s*['\"]\./\w*Showcase", code):
        problems.append("按名字静态导入了某个 *Showcase 模块（应只靠 glob 收集）")
    if not re.search(r"\.sort\(", code):
        problems.append("没有对文件名排序（JS 默认 sort，按 ASCII 编码顺序）")
    if "data-showcase" not in code:
        problems.append("没有给各节包 data-showcase 属性")
    if "default" not in code:
        problems.append("没有取各模块的默认导出")
    if "showcase.css" not in code:
        problems.append("ShowcasePage 没有引入 showcase.css")
    if re.search(r"\bPageFrame\b", code):
        problems.append("ShowcasePage 不用 PageFrame")
    return problems


def test_s6_showcase_page_collects_by_glob():
    """S6 / D12：ShowcasePage.tsx 用 import.meta.glob 急切导入 ./*Showcase.tsx，按文件名排序，每节包 data-showcase，引入 showcase.css，
    不按名字静态导入任何 *Showcase 模块；自己的文件名不以 Showcase.tsx 结尾；showcase.css 给 [data-showcase] 设 display: contents。"""
    text = _read(need_file(f"{SRC_REL}/showcase/ShowcasePage.tsx"))
    problems = showcase_page_problems(text)
    css = _read(need_file(f"{SRC_REL}/showcase/showcase.css"))
    if not has_decl(css, ("display",), eq="contents", sel=r"data-showcase"):
        problems.append("showcase.css 里没有 [data-showcase] 的 display: contents 规则")
    if not showcase_names():
        problems.append("src/showcase/ 下没有 *Showcase.tsx")
    fail_if(problems, "ShowcasePage")


def test_s6_readme_documents_shell():
    """S6 / 合同第 13 条：README 增补目录约定（shell/、pages/、mock/、api.ts、icons/frame.tsx）、showcase/ 的收集与排序规则和怎样加一节演示、
    路由表与 #/showcase、?mock= 的五个取值、不连服务的检查、主题改由标题栏的菜单切换；「## 命令」一节仍在。"""
    text = _read(need_file(f"{WEB_REL}/README.md"))
    wanted = ["## 命令", "shell/", "pages/", "mock/", "api.ts", "icons/frame.tsx", "*Showcase.tsx", "排序", "#/showcase", "?mock=",
              "data", "loading", "empty", "error", "offline", "标题栏"]
    wanted += [f"#/{tab_id}" for tab_id in TAB_IDS]
    problems = [f"README 里没有「{lit}」" for lit in wanted if lit not in text]
    if not re.search(r"不连服务|shell-no-network", text):
        problems.append("README 里没有写不连服务的检查（不连服务 或 shell-no-network）")
    if not re.search(r"主题", text):
        problems.append("README 里没有写主题")
    fail_if(problems, "README")


def weight_rule_problems(css, tokens_css):
    """showcase.css：按 [data-font-weight="…"] 选中的规则用 font: var(令牌)，令牌的字重与组一致。"""
    specs = {"400": "--tt-text-md", "500": "--tt-text-md-medium", "600": "--tt-title-sm"}
    problems = []
    resolved = dict(re.findall(r"(--tt-[\w-]+)\s*:\s*([^;]+);", strip_comments(tokens_css)))
    for weight, token in specs.items():
        fonts = []
        for selector, decls in parse_rules(css):
            if not any(re.findall(r"""\[\s*data-font-weight\s*=\s*["']?(\d+)["']?\s*\]""", part) == [weight] for part in split_top(selector)):
                continue
            for name, value in decls:
                if name == "font":
                    fonts.append(cv(value))
                elif name in ("font-weight", "font-family"):
                    problems.append(f'[data-font-weight="{weight}"] 的规则里不应单独写 {name}')
        if not fonts:
            problems.append(f'showcase.css 里没有按 [data-font-weight="{weight}"] 选中、并用 font: var({token}) 的规则')
        for value in fonts:
            if value != f"var({token})":
                problems.append(f'[data-font-weight="{weight}"] 的 font 应为 var({token})，实际 {value}')
        m = re.match(r"(\d+)\s", resolved.get(token, ""))
        if not m or m.group(1) != weight:
            problems.append(f"tokens.css 里 {token} 的字重应为 {weight}")
    return problems


def row_style_problems(css):
    decls = [d for _sel, ds in parse_rules(css) for d in ds]
    problems = []
    if not any(n == "white-space" and cv(v) == "pre" for n, v in decls):
        problems.append("没有 white-space: pre 的声明")
    if not any(n == "font-variant-ligatures" and cv(v) == "none" for n, v in decls):
        problems.append("没有 font-variant-ligatures: none 的声明")
    if any(n == "letter-spacing" for n, _v in decls):
        problems.append("不应设 letter-spacing")
    if not any(n == "border" and cv(v) == cv("1px solid var(--tt-border)") for n, v in decls):
        problems.append("没有 border: 1px solid var(--tt-border) 的声明")
    if not any(n in BG and cv(v) == "var(--tt-surface-1)" for n, v in decls):
        problems.append("没有底色 var(--tt-surface-1) 的声明")
    return problems


def test_transitional_d12_showcase_css_moved():
    """陈列页的演示改版那一片推翻（样张规则、showcase__* 规则的位置与写法）。

    D12 / 合同第 11 条：App.css 里 showcase__* 规则搬到 src/showcase/showcase.css（App.css 不再有 .showcase* 规则，也不出现
    letter-spacing 与 [data-font-weight] 选择器）；showcase.css 带全部原选择器，去掉 .showcase 的 min-height:100vh，样张字重规则与
    行样式不变，除 0 与 1px 外的 px 字面量补注释「演示自定」。"""
    app_css = _read(need_file(f"{SRC_REL}/App.css"))
    css = _read(need_file(f"{SRC_REL}/showcase/showcase.css"))
    tokens = _read(need_file(f"{SRC_REL}/styles/tokens.css"))
    problems = []
    for selector, _decls in parse_rules(app_css):
        if "showcase" in selector:
            problems.append(f"App.css 里还有陈列页的规则 {selector}（应搬到 showcase.css）")
    if "letter-spacing" in strip_comments(app_css):
        problems.append("App.css 不出现 letter-spacing")
    if "data-font-weight" in strip_comments(app_css):
        problems.append("App.css 不用 [data-font-weight] 选择器")
    items = {item for selector, _d in parse_rules(css) for item in split_top(selector)}
    for sel in SHOWCASE_SELECTORS:
        if not any(item == sel or item.endswith(" " + sel) for item in items):
            problems.append(f"showcase.css 里缺少选择器 {sel}")
    for selector, decls in parse_rules(css):
        if selector == ".showcase" and decl_matches(decls, ("min-height",), has=("100vh",)):
            problems.append(".showcase 要去掉 min-height: 100vh")
    problems += weight_rule_problems(css, tokens)
    problems += row_style_problems(css)
    problems += px_literal_problems("showcase/showcase.css", _read(SRC / "showcase" / "showcase.css"), need_text="演示自定")
    fail_if(problems, "showcase.css")


def demo_values(path):
    return re.findall(r"""data-demo\s*=\s*["']([^"']+)["']""", strip_ts_comments(_read(path)))


def test_transitional_d12_base_and_shell_showcase_sources():
    """陈列页的演示改版那一片推翻（BaseShowcase 的原样搬运与 data-demo 取值、ShellShowcase 的两节）。

    D12 / 合同第 11 条：App.tsx 里不再有陈列页内容；BaseShowcase.tsx 带基线 App.tsx 的全部原文片段，五节原子依次带 data-demo
    button、tag、status-tag、card、banner，后面五节浮层演示的 data-demo 不变，页头三个主题按钮去掉；ShellShowcase.tsx 有
    page-states 与 disabled-action 两节；各文件默认导出；data-demo 取值不重复、不与 T007 的 7 个重复。"""
    app = _read(need_file(f"{SRC_REL}/App.tsx"))
    base_path = need_file(f"{SRC_REL}/showcase/BaseShowcase.tsx")
    shell_path = need_file(f"{SRC_REL}/showcase/ShellShowcase.tsx")
    base = _read(base_path)
    problems = []
    for lit in BASE_LITERALS:
        if lit not in base:
            problems.append(f"BaseShowcase.tsx 里缺基线 App.tsx 的原文「{lit}」")
    for lit in ("字体 · 等距更纱黑体 SC", "Button 按钮", "Banner 提示条", "弹出轻提示", "已复制到剪贴板"):
        if lit in app:
            problems.append(f"App.tsx 里还留着陈列页的原文「{lit}」")
    if "showcase__" in app:
        problems.append("App.tsx 里还有 showcase__* 类名")
    if demo_values(base_path) != list(BASE_DEMOS):
        problems.append(f"BaseShowcase.tsx 的 data-demo 应依次为 {list(BASE_DEMOS)}，实际 {demo_values(base_path)}")
    for lit in ("aria-pressed", "切换主题", "ThemeButton"):
        if lit in base:
            problems.append(f"BaseShowcase.tsx 里不该有主题按钮（{lit}）")
    if "FormsShowcase" in base or "FormsShowcase" in app:
        problems.append("FormsShowcase 由 ShowcasePage 自动收集，BaseShowcase 与 App 都不导入它")
    if demo_values(shell_path) != list(SHELL_DEMOS):
        problems.append(f"ShellShowcase.tsx 的 data-demo 应依次为 {list(SHELL_DEMOS)}，实际 {demo_values(shell_path)}")
    for path in (base_path, shell_path):
        if not re.search(r"export\s+default\b", strip_ts_comments(_read(path))):
            problems.append(f"{path.name} 没有默认导出")
    taken = set(FORMS_DEMOS) | set(T007_DEMOS) | {"icon-button", "menu", "dialog", "drawer", "toast"}
    for name in ("button", "tag", "status-tag", "card", "banner") + SHELL_DEMOS:
        if name in taken:
            problems.append(f"新 data-demo「{name}」与已有的重复")
    fail_if(problems, "BaseShowcase 与 ShellShowcase")


# ---------------------------------------------------------------------------
# P 系列：流水线断言
# ---------------------------------------------------------------------------

def test_d13_pipeline_steps_pass(pipeline):
    """P1 / D13（守卫）：npm ci、npm run build、npm test、npm run check:contract 都退出 0；npm test 有通过的用例，没有失败、跳过、待办。"""
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    step = pipeline.steps["npm test"]
    out = step.out
    assert re.search(r"Tests\s+(?:.*\|\s*)?\d+ passed", out), f"npm test 输出里没有 'Tests … N passed'：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", out), f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert re.search(r"Test Files\s+\d+ passed", out) and not re.search(r"Test Files\s+.*\bfailed\b", out), \
        f"npm test 的 Test Files 行异常：\n{step.tail}"


def test_d01_probe_routes_and_tabs(pipeline):
    """P2 / D01：空 hash 是总览；9 个 Tab 的顺序、文字、title、分隔线；只有当前项有 aria-current 与金条；点击切页后地址、当前项、h1、
    document.title 同步变；修饰键点击不拦；未知路由回总览且不改写地址；#/tasks/x/y 归任务；#/showcase 没有当前项并渲染陈列页；
    hashchange；?mock= 保留；内容区按路由重新挂载。"""
    assert_probe_group(pipeline, "route", "D01 路由与 Tab 栏")


def test_d04_probe_shortcuts(pipeline):
    """P3 / D04：Ctrl+1…8 与 Ctrl+, 切页且 keydown 被 preventDefault；带 Alt/Shift/Meta 不切；Ctrl+9 不切；输入法组合中与已被
    preventDefault 的事件不处理；模态对话框打开时不切；监听在 window 上；卸载后不再监听。"""
    assert_probe_group(pipeline, "route", "D04 快捷键")


def test_d02_probe_titlebar_and_menus(pipeline):
    """P6 / D02：Logo、产品名、连接胶囊都在；仓库菜单当前项 aria-checked=true、禁用项 aria-disabled=true 且选不了、分组标题与分隔线
    不可聚焦；两个菜单的方向键、Home/End、Enter、点击、Esc（焦点回触发钮、stopPropagation）、Tab、菜单外按下鼠标。"""
    assert_probe_group(pipeline, "titlebar", "D02 标题栏")


def test_d05_probe_theme(pipeline):
    """P5 / D05：缺省无 data-theme；经菜单选亮、跟随系统、暗，data-theme 依次 light、system、去掉；html 与 body 其余属性不变、无内联样式、
    不写存储；触发钮名称随偏好变；applyTheme 是写入口；偏好跨路由保持。"""
    assert_probe_group(pipeline, "titlebar", "D05 主题")


def test_d02_probe_logo_and_icons(pipeline):
    """S3（渲染级）/ D02：Logo 的 path 与画布逐字相同；9 个 Tab 图标、仓库切换的两个图标、主题三态图标、刷新图标、添加仓库图标
    的元素与属性和 Main 画布、组件板一致。"""
    assert_probe_group(pipeline, "titlebar", "S3 Logo 与图标")


def test_d03_probe_tabbar(pipeline):
    """P4 / D03：计数为 0 或未读到时不渲染、为 3 时有 data-tab-count 且文字是 3、链接 aria-label 写明数量；状态段 aria-live=polite，
    上次更新与 kit 版本带 tt-hide-narrow 且上次更新 aria-live=off，两个计数链接不带；上次更新随假计时器变化；
    loading、error 时计数显示 —；offline 时后面接「· 可能已过期」；陈列页不渲染上次更新。"""
    assert_probe_group(pipeline, "tabbar", "D03 Tab 栏与状态段")


def test_d03_probe_status_groups(pipeline):
    """S7（行为级）/ D03：用 api 替身给出单行与混合行的状态，Tab 计数与状态段的两个计数落在 UI 文档 3.4 的分组里（待验收 + 要你决定
    计入 Tab 计数，运行中单独数；未知状态不计入）。"""
    assert_probe_group(pipeline, "pages", "S7 状态分组（待验收与要你决定计入 Tab 计数，运行中单独数）")


def test_d09_probe_page_frame(pipeline):
    """P7 / D09：299ms 无骨架、300ms 有；有数据、空两态；出错块的命令、退出码、报错原文都是纯文本，点重试再调一次；Promise 被拒只写
    「没有收到服务的回应」；刷新保留数据、按钮 aria-busy；先发后回的结果被丢弃；卸载后不再写状态。"""
    assert_probe_group(pipeline, "frame", "D09 页面框架")


def test_d11_probe_disabled_action(pipeline):
    """P8 / D11：Tooltip 包 disabled Button，Button 带 pointer-events:none 的类；悬停包裹元素 399ms 无提示、400ms 出现 role=tooltip；
    reason 可改。"""
    assert_probe_group(pipeline, "frame", "D11 禁用的写操作入口")


def test_transitional_d10_probe_page_placeholders(pipeline):
    """各页面那一片（把页面占位换成真实页面内容）推翻。

    D10：9 页各自的加载函数、说明与空态；有数据时显示「夹具数据已读到」加函数名（状态页写条数）；总览说明是「仓库名 · kit 版本」；
    凭据页刷新钮叫「重新检查」；?mock=empty 只对 5 个列表资源的页面生效。"""
    assert_probe_group(pipeline, "pages", "D10 页面占位")


def test_transitional_p10_probe_five_states(pipeline):
    """接本机服务那一片（把 ?mock= 夹具开关换成真实服务）推翻。

    P10：经 ?mock= 渲染 App，五态与 data-page-state 对得上；data 时需要你判断 3、运行中 1；empty 时没有计数胶囊；loading、error 时计数
    显示 —；offline 时胶囊显示已断开、有 role=alert 提示条、可能已过期标签、data-stale=true、禁用的重新连接。"""
    assert_probe_group(pipeline, "pages", "P10 App 级五态（经 ?mock= 演示）")


def test_transitional_d06_probe_api_fixtures(pipeline):
    """接本机服务那一片（api.ts 换成真实请求）推翻。

    P9 / D06：13 个函数的 data 与 UI 文档第 9 节 JSON 逐值相等，信封字段齐全，command 照架构文档 5.2；返回已兑现的 Promise；
    改了返回值不影响下一次调用；夹具之外的参数返回 ok:false。"""
    assert_probe_group(pipeline, "api", "D06 数据层")


def test_transitional_d07_probe_mock_switch(pipeline):
    """接本机服务那一片（api.ts 换成真实请求）推翻。

    P9 / D07：data、loading、empty、error、offline 五个开关值的效果都对；getMeta 不受开关影响；empty 只对 5 个列表资源生效；
    每次调用时读地址里的 mock。"""
    assert_probe_group(pipeline, "api", "D07 夹具开关")


def test_d08_probe_no_network(pipeline):
    """P12 / D08：探针把浏览器的四个网络接口和 navigator.sendBeacon 换成记录调用的替身，逐页（9 页加陈列页）、逐个开关值渲染 App
    （含刷新、重试、点 Tab），调用次数都是 0；替身自检会记录调用。"""
    assert_probe_group(pipeline, "nonet", "D08 运行时不连服务")


def test_d12_probe_showcase_collection(pipeline):
    """P11 / D12：data-showcase 的值与顺序等于目录里 *Showcase.tsx 文件名的排序结果（门禁每次现读目录）；ShowcasePage 根是 div.showcase、
    h1 组件陈列、无主题按钮；data-demo 的顺序与归属；整页只有一个 role=status，无文字按钮都有 aria-label。"""
    assert_probe_group(pipeline, "showcase", "D12 陈列页收集与排序")


def test_transitional_p11_probe_showcase_content(pipeline):
    """陈列页的演示改版那一片推翻。

    P11 / 站主 Q1 接手原 G2 两条 App 陈列页用例及原 G3 P8、G4 P8、G5 P12：在 #/showcase 上验陈列页内容——17 个状态的 title、8 种色调、
    4 种按钮变体与 3 种尺寸、加载按钮、role=alert、关闭提示；样张三组 400、500、600 每组 4 行每行 26 列；5 节浮层演示及其行为；
    11 节表单演示及其行为；ShellShowcase 的 page-states 与 disabled-action 两节。"""
    for group in P11_GROUPS:
        assert_probe_group(pipeline, "showcase", group)


def test_d13_worktree_unchanged_by_pipeline(pipeline):
    """P13 / D13（守卫）：流水线与探针前后 git status 相同；package.json、锁文件、index.html、vite.config.ts、tsconfig.json、
    tokens.css、fonts.css、base.css、main.tsx、App.css 的摘要不变；gate-probe/ 没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"
    changed = sorted(n for n in WATCHED if pipeline.digests_before.get(n) != pipeline.digests_after.get(n))
    assert not changed, f"流水线改动了不该动的文件：{changed}"
    assert not pipeline.gate_probe_left, "desktop/web/gate-probe/ 在探针结束后没有清掉"


# ---------------------------------------------------------------------------
# 门禁自检（不依赖候选）：检查函数放得过合同写明的正确样本，拦得住常见错误
# ---------------------------------------------------------------------------

GOOD_SHELL_CSS = """
.tt-titlebar {
  height: 40px; /* UI 文档 5.2 */
  display: flex;
  align-items: center;
  gap: var(--tt-space-2);
  padding: 0 140px 0 var(--tt-space-3); /* 右 140：UI 文档 5.2 :352 */
  background: var(--tt-titlebar);
  border-bottom: 1px solid var(--tt-border);
}
.tt-tabbar {
  order: 2;
  height: var(--tt-tabbar-height);
  display: flex;
  padding: 0 var(--tt-space-2);
  background: var(--tt-sidebar);
  color: var(--tt-sidebar-text);
  border-top: 1px solid var(--tt-sidebar-hover);
}
.tt-tab { position: relative; min-width: 72px; /* handoff :66 */ color: var(--tt-sidebar-text); font: var(--tt-text-caption); }
.tt-tab:hover { background: var(--tt-sidebar-hover); }
.tt-tab[aria-current="page"] { background: var(--tt-sidebar-hover); color: var(--tt-sidebar-text-active); font: var(--tt-text-caption-strong); }
.tt-tab__bar {
  position: absolute; top: 0; left: 10px; right: 10px; /* handoff :67 */
  height: 3px; /* handoff :67 */
  background: var(--tt-accent);
  border-radius: 0 0 var(--tt-radius-sm) var(--tt-radius-sm); /* 画布原值 2 */
}
.tt-tab-divider { width: 1px; background: var(--tt-sidebar-hover); }
.tt-tab__count {
  position: absolute; top: 5px; left: calc(50% + 5px); /* handoff :68 */
  height: 16px; min-width: 18px; /* handoff :68 */
  padding: 0 var(--tt-space-1);
  background: var(--tt-accent);
  color: var(--tt-on-accent);
  font: var(--tt-text-caption-strong); /* 画布原值 600 11/16 */
  border-radius: var(--tt-radius-full);
  box-shadow: 0 0 0 2px var(--tt-sidebar);
}
.tt-status { color: var(--tt-sidebar-text-muted); font: var(--tt-text-caption); }
.tt-status__link { color: var(--tt-sidebar-text); }
.tt-status__link:hover { text-decoration: underline; }
.tt-status__dot--info { width: 8px; height: 8px; /* handoff :69 */ background: var(--tt-sidebar-dot-info); }
.tt-status__dot--attn { width: 8px; height: 8px; /* handoff :69 */ background: var(--tt-accent); }
.tt-shell-menu {
  position: absolute; top: calc(100% + var(--tt-space-1)); left: 0;
  width: 240px; /* 组件板 :455 */
  padding: var(--tt-space-1);
  background: var(--tt-surface-1);
  border: 1px solid var(--tt-border);
  border-radius: var(--tt-radius-lg);
  box-shadow: var(--tt-shadow-2);
  z-index: var(--tt-z-popover);
}
.tt-shell-menu--right { left: auto; right: 0; }
.tt-shell-menu__item { height: 32px; /* 组件板 :457 */ padding: 0 var(--tt-space-2); border-radius: var(--tt-radius-md); font: var(--tt-text-sm); }
.tt-shell-menu__item:hover, .tt-shell-menu__item:focus { background: var(--tt-surface-3); }
.tt-shell-menu__item[aria-checked="true"] { background: var(--tt-surface-selected); }
.tt-shell-menu__item[aria-disabled="true"] { color: var(--tt-text-disabled); }
.tt-shell-menu__check { color: var(--tt-tone-success-fg); }
.tt-shell-menu__heading { font: var(--tt-text-caption); color: var(--tt-text-3); }
.tt-page__title { font: var(--tt-title-lg); }
.tt-page__desc { font: var(--tt-text-sm); color: var(--tt-text-2); }
.tt-page__error-title { color: var(--tt-danger-text); }
.tt-action-disabled { pointer-events: none; }
"""

SHELL_CSS_BROKEN = {
    "titlebar": (titlebar_css_problems, {
        "高 44": ("height: 40px;", "height: 44px;"),
        "右内边距 100": ("0 140px 0", "0 100px 0"),
        "没有下边框": ("border-bottom: 1px solid var(--tt-border);", ""),
        "底色写成别的令牌": ("background: var(--tt-titlebar);", "background: var(--tt-surface-1);"),
        "设了 overflow:hidden": ("display: flex;\n  align-items: center;\n  gap: var(--tt-space-2);",
                                 "display: flex;\n  align-items: center;\n  overflow: hidden;\n  gap: var(--tt-space-2);"),
        "建了层叠上下文": ("display: flex;\n  align-items: center;\n  gap: var(--tt-space-2);",
                          "display: flex;\n  align-items: center;\n  transform: translateZ(0);\n  gap: var(--tt-space-2);"),
    }),
    "tabbar": (tabbar_css_problems, {
        "Tab 栏高写死": ("height: var(--tt-tabbar-height);", "height: 56px;"),
        "没有 order": ("  order: 2;\n", ""),
        "最小宽 64": ("min-width: 72px;", "min-width: 64px;"),
        "没有当前项规则": ('.tt-tab[aria-current="page"]', ".tt-tab.x"),
        "金条高 4": ("height: 3px;", "height: 4px;"),
        "金条圆角写死": ("0 0 var(--tt-radius-sm) var(--tt-radius-sm)", "0 0 2px 2px"),
        "计数胶囊高 18": ("height: 16px;", "height: 18px;"),
        "计数没有外圈": ("box-shadow: 0 0 0 2px var(--tt-sidebar);", ""),
        "计数字色错": ("color: var(--tt-on-accent);", "color: var(--tt-text-1);"),
        "计数位置错": ("left: calc(50% + 5px);", "left: 50%;"),
        "缺 Q3 字体注释": ("/* 画布原值 600 11/16 */", ""),
        "缺 Q3 圆角注释": ("/* 画布原值 2 */", ""),
        "分隔线颜色错": (".tt-tab-divider { width: 1px; background: var(--tt-sidebar-hover); }",
                    ".tt-tab-divider { width: 1px; background: var(--tt-border); }"),
        "运行中圆点颜色错": ("background: var(--tt-sidebar-dot-info);", "background: var(--tt-accent);"),
        "计数链接悬停没有下划线": (".tt-status__link:hover { text-decoration: underline; }", ".tt-status__link:hover { opacity: 0.8; }"),
    }),
    "menu": (shell_menu_css_problems, {
        "面板宽 200": ("width: 240px;", "width: 200px;"),
        "层级写死": ("z-index: var(--tt-z-popover);", "z-index: 10;"),
        "项高 28": ("height: 32px;", "height: 28px;"),
        "禁用项颜色错": ("color: var(--tt-text-disabled);", "color: var(--tt-text-3);"),
        "选中底错": ("background: var(--tt-surface-selected);", "background: var(--tt-surface-3);"),
        "类名没有 tt-shell-menu": (".tt-shell-menu__item:hover, .tt-shell-menu__item:focus {", ".tt-m__item:hover, .tt-m__item:focus {"),
    }),
    "frame": (page_frame_css_problems, {
        "没有 pointer-events": ("pointer-events: none;", ""),
        "h1 字错": ("font: var(--tt-title-lg);", "font: var(--tt-title-md);"),
    }),
}


def test_gate_selfcheck_shell_css_checks():
    """门禁自检：一份写法合理的框架 CSS 通过 S4 的各检查，逐项改坏后都被抓住（证明检查放得过正确实现、拦得住常见错误）。"""
    for name, (check, broken) in SHELL_CSS_BROKEN.items():
        assert check(GOOD_SHELL_CSS) == [], (name, check(GOOD_SHELL_CSS))
        for label, (old, new) in broken.items():
            assert old in GOOD_SHELL_CSS, (name, label, "样本里没有要替换的片段")
            assert check(GOOD_SHELL_CSS.replace(old, new, 1)), f"{name}：没抓住 {label}"
    # 公共类写尺寸、修饰类写颜色（常规写法）也要放过；尺寸不对或没有尺寸仍要抓住
    one_line_info = ".tt-status__dot--info { width: 8px; height: 8px; /* handoff :69 */ background: var(--tt-sidebar-dot-info); }"
    one_line_attn = ".tt-status__dot--attn { width: 8px; height: 8px; /* handoff :69 */ background: var(--tt-accent); }"
    assert one_line_info in GOOD_SHELL_CSS and one_line_attn in GOOD_SHELL_CSS
    split_dot = GOOD_SHELL_CSS.replace(one_line_info, ".tt-status__dot { width: 8px; height: 8px; border-radius: 50%; }\n"
                                       ".tt-status__dot--info { background: var(--tt-sidebar-dot-info); }", 1)
    split_dot = split_dot.replace(one_line_attn, ".tt-status__dot--attn { background: var(--tt-accent); }", 1)
    assert tabbar_css_problems(split_dot) == [], tabbar_css_problems(split_dot)
    assert tabbar_css_problems(split_dot.replace(".tt-status__dot { width: 8px; height: 8px;", ".tt-status__dot { width: 6px; height: 8px;", 1))
    assert tabbar_css_problems(split_dot.replace(".tt-status__dot { width: 8px; height: 8px; border-radius: 50%; }", "", 1))
    assert pointer_classes(GOOD_SHELL_CSS) == ["tt-action-disabled"]
    assert pointer_classes(".a .b, .c:hover { pointer-events: none; } .d { pointer-events: auto; }") == ["b", "c"]


def test_gate_selfcheck_css_helpers():
    """门禁自检：padding 简写、令牌与 px 注释检查、未定义令牌检查。"""
    sides = box_sides(split_decls("padding: 0 140px 0 var(--tt-space-3)"))
    assert sides == {"top": "0", "right": "140px", "bottom": "0", "left": "var(--tt-space-3)"}
    assert box_sides(split_decls("padding: 0 var(--tt-space-2)"))["left"] == "var(--tt-space-2)"
    assert box_sides(split_decls("padding: 0 calc(1px + 2px) 3px"))["right"] == "calc(1px+2px)"
    assert box_sides(split_decls("padding: 4px; padding-right: 9px"))["right"] == "9px"
    assert rule_sides(".a { padding: 0 140px 0 var(--tt-space-3); }", right="140px", left="var(--tt-space-3)")
    assert not rule_sides(".a { padding: 0 100px; }", right="140px")
    assert px_literal_problems("x", ".a { width: 8px; } /* 注 */") == []
    assert px_literal_problems("x", ".a { width: 8px; /* 注 */ }") == []
    assert px_literal_problems("x", ".a { width: 8px; }")
    assert px_literal_problems("x", ".a { border: 1px solid; margin: 0px; }") == []
    assert px_literal_problems("x", ".a { width: 8px; /* 注 */ }", need_text="演示自定")
    assert px_literal_problems("x", ".a { width: 8px; /* 演示自定 */ }", need_text="演示自定") == []
    assert token_only_problems("x", ".a { z-index: 5; }")
    assert token_only_problems("x", ".a { border-radius: 50%; }")
    assert token_only_problems("x", ".a { border-radius: 0 0 var(--tt-radius-sm) var(--tt-radius-sm); }") == []
    assert token_only_problems("x", ".a { font: 12px/16px sans-serif; }")
    assert undefined_token_problems("x", ".a { color: var(--tt-nope); }", ".r { --tt-yes: 1; }") == ["x：用了令牌库里没有的 --tt-nope"]
    assert undefined_token_problems("x", ".a { color: var(--tt-yes); }", ".r { --tt-yes: 1; }") == []
    assert rule_has_all(".a { height: 3px; background: var(--tt-accent); }", [(("height",), {"eq": "3px"}), (BG, {"eq": "var(--tt-accent)"})])
    assert not rule_has_all(".a { height: 3px; } .b { background: var(--tt-accent); }",
                            [(("height",), {"eq": "3px"}), (BG, {"eq": "var(--tt-accent)"})])
    assert has_decl("@media (max-width: 1px) { .a { display: none !important; } }", ("display",), eq="none", sel=r"\.a")
    assert order_problems(".a { order: 2; }") == []
    assert order_problems(".a { order: 0; }")


def test_gate_selfcheck_source_helpers():
    """门禁自检：整词扫描（自检样本照合同第 12 条：报 window 上调用、new 构造、globalThis 上用方括号与字符串取，不报前缀拼接和
    后缀拼接的普通标识符）、导出名解析、源码守卫、W4 字面量检查。"""
    word_a, word_b, word_c, word_d = NET_WORDS
    assert word_hits(f"window.{word_a}(url)", NET_WORDS) == [(1, word_a)]
    assert word_hits(f"const s = new {word_d}(url)", NET_WORDS) == [(1, word_d)]
    assert word_hits(f"globalThis['{word_a}'](x)", NET_WORDS) == [(1, word_a)]
    assert word_hits(f"// 注释里也算 {word_c}", NET_WORDS) == [(1, word_c)]
    assert word_hits(f'const s = "{word_b}";\nok', NET_WORDS) == [(1, word_b)]
    assert word_hits(f"pre{word_a}All(); const {word_a}edAt = 1; ${word_a}; _{word_a}; {word_a}2; x{word_a}", NET_WORDS) == []
    assert word_hits(f"a\nb\n{word_a}", NET_WORDS) == [(3, word_a)]
    exports = exported_names("export async function a() {}\nexport const b = 1;\nexport { c, d as e };\n// export function z() {}\n")
    assert exports == {"a", "b", "c", "e"}
    assert source_rule_problems("f", "<div role=\"status\" />")
    assert source_rule_problems("f", "x.matchMedia('q')")
    assert source_rule_problems("f", "// role=\"status\" in a comment\nconst a = 1;") == []
    assert w4_literal_problems("f", "const a = '#" + "abc';")
    assert w4_literal_problems("f", "// color: " + "rgb" + "(1,2,3)")
    assert w4_literal_problems("f", "/* #" + "abc */ const a = '#/overview';") == []
    assert w4_literal_problems("f", "const a = '#/tasks?mock=data'; // 井号加路由") == []


def test_gate_selfcheck_strict_diff_and_doc_blocks():
    """门禁自检：逐值比较（布尔与数字不混、整数浮点按数值比、键与长度必须一致）；UI 文档第 9 节的 14 个代码块都解析得出，内容符合预期。"""
    assert strict_diff({"a": [1, 2.0, None]}, {"a": [1.0, 2, None]}) is None
    assert strict_diff(True, 1)
    assert strict_diff({"a": 1}, {"a": 1, "b": 2})
    assert strict_diff([1, 2], [1, 2, 3])
    assert strict_diff("a", "b")
    assert strict_diff({"a": {"b": [1]}}, {"a": {"b": [2]}}) == "$.a.b[0]: 1 != 2"
    blocks = doc_json_blocks(_read(UI_DOC))
    assert {k: len(v) for k, v in blocks.items() if k in ("9.1", "9.2", "9.3", "9.4", "9.5", "9.6", "9.7", "9.9", "9.10", "9.11", "9.12")} == {
        "9.1": 1, "9.2": 1, "9.3": 1, "9.4": 2, "9.5": 1, "9.6": 3, "9.7": 1, "9.9": 1, "9.10": 1, "9.11": 1, "9.12": 1}
    assert set(FIXTURE_SOURCES) == {"meta", "status", "attempt", "file-executor-report", "file-events", "roles", "profiles", "presets",
                                    "preset-diff", "runtimes", "plugins", "history", "usage", "secrets"}
    assert doc_fixture("meta") == {"kit_version": "2.12.0", "repo_name": "demo-repo"}
    status = doc_fixture("status")
    assert len(status) == 7
    review = set(STATE_GROUPS["review"]) | set(STATE_GROUPS["decide"])
    assert sum(1 for row in status if row["state"] in review) == 3, "夹具里待验收 + 要你决定应是 3 行"
    assert sum(1 for row in status if row["state"] in STATE_GROUPS["running"]) == 1
    assert doc_fixture("attempt")["task"] == "logs-cat"
    assert doc_fixture("file-executor-report")["mode"] == "text" and doc_fixture("file-events")["mode"] == "jsonl"
    assert len(doc_fixture("file-events")["lines"]) == 6
    assert doc_fixture("preset-diff")["a"] == "default" and doc_fixture("preset-diff")["b"] == "economy"
    assert len(doc_fixture("roles")["roles"]) == 4 and len(doc_fixture("runtimes")["runtimes"]) == 3
    assert len(doc_fixture("plugins")["plugins"]) == 3 and len(doc_fixture("history")["entries"]) == 3
    assert len(doc_fixture("secrets")["secrets"]) == 2
    assert doc_fixture("usage")["planner"] is None
    for name in FIXTURE_SOURCES:
        assert strict_diff(json.loads(json.dumps(doc_fixture(name))), doc_fixture(name)) is None


def test_gate_selfcheck_canvas_parsers():
    """门禁自检：Main 画布与组件板的图标、Logo 解析出预期的结构。"""
    shapes = canvas_icon_shapes()
    assert len(shapes) == 16 and set(shapes) >= {f"tab:{t}" for t in TAB_IDS}
    for tab_id in TAB_IDS:
        assert (shapes[f"tab:{tab_id}"]["width"], shapes[f"tab:{tab_id}"]["height"], shapes[f"tab:{tab_id}"]["viewBox"]) == ("18", "18", "0 0 24 24")
    assert len(shapes["tab:overview"]["children"]) == 4 and shapes["tab:overview"]["children"][0]["tag"] == "rect"
    assert len(shapes["tab:tasks"]["children"]) == 5 and shapes["tab:tasks"]["children"][0]["attrs"] == {"d": "m3 17 2 2 4-4"}
    secrets = shapes["tab:secrets"]["children"]
    assert secrets[1]["tag"] == "circle" and secrets[1]["attrs"] == {"cx": "16.5", "cy": "7.5", "r": "0.5", "fill": "currentColor"}
    assert (shapes["folder-open"]["width"], shapes["chevron-down"]["width"], shapes["moon"]["height"]) == ("16", "14", "16")
    assert shapes["sun"]["children"][0]["tag"] == "circle" and len(shapes["sun"]["children"]) == 9
    assert shapes["monitor"]["children"][0]["tag"] == "rect" and len(shapes["monitor"]["children"]) == 3
    assert len(shapes["refresh"]["children"]) == 4
    assert (shapes["folder-plus"]["width"], shapes["folder-plus"]["viewBox"]) == ("14", "0 0 24 24")
    assert shapes["folder-plus"]["children"][0]["attrs"] == {"d": "M12 10v6"}
    logo = canvas_logo()
    assert logo["mark"].startswith("M75 689") and logo["tally"].startswith("M698 482") and logo["mark"] != logo["tally"]
    parsed = svg_shapes('<svg width="10" height="10" viewBox="0 0 10 10"><path d="M0 5.5h10" stroke="currentColor"></path></svg>')
    assert parsed == [{"width": "10", "height": "10", "viewBox": "0 0 10 10",
                       "children": [{"tag": "path", "attrs": {"d": "M0 5.5h10", "stroke": "currentColor"}}]}]


def test_gate_selfcheck_showcase_helpers():
    """门禁自检：陈列页文件名按 ASCII 编码顺序排序（大写在前，与 JS 默认 sort 一致）；ShowcasePage 收集写法的检查；
    样张规则与行样式的检查；基线的 3 份既有测试常量自洽。"""
    assert sorted(["FormsShowcase", "BaseShowcase", "aShowcase", "EvidenceShowcase", "ShellShowcase"]) == [
        "BaseShowcase", "EvidenceShowcase", "FormsShowcase", "ShellShowcase", "aShowcase"]
    good = ("import './showcase.css';\nconst modules = import.meta.glob('./*Showcase.tsx', { eager: true });\n"
            "export default function ShowcasePage() {\n  const names = Object.keys(modules).sort();\n"
            "  return <div className=\"showcase\">{names.map((n) => <div key={n} data-showcase={n}>{(modules[n] as any).default}</div>)}</div>;\n}\n")
    assert showcase_page_problems(good) == []
    broken = {
        "静态导入": good.replace("import './showcase.css';", "import './showcase.css';\nimport FormsShowcase from './FormsShowcase';"),
        "不急切": good.replace("{ eager: true }", "{}"),
        "不排序": good.replace(".sort()", ""),
        "没有 data-showcase": good.replace("data-showcase", "data-x"),
        "收错目录": good.replace("./*Showcase.tsx", "./**/*Showcase.tsx"),
        "不引 css": good.replace("import './showcase.css';", ""),
    }
    for label, text in broken.items():
        assert showcase_page_problems(text), f"没抓住：{label}"
    tokens = "--tt-text-md: 400 14px/20px x;\n--tt-text-md-medium: 500 14px/20px x;\n--tt-title-sm: 600 14px/20px x;\n"
    good_css = (
        '.showcase__specimen { border: 1px solid var(--tt-border); background: var(--tt-surface-1); }\n'
        '[data-font-weight="400"] .showcase__specimen-row { font: var(--tt-text-md); white-space: pre; font-variant-ligatures: none; }\n'
        "[data-font-weight='500'] .showcase__specimen-row { font: var(--tt-text-md-medium); }\n"
        '[data-font-weight=600] .showcase__specimen-row { font: var(--tt-title-sm); }\n')
    assert weight_rule_problems(good_css, tokens) == [] and row_style_problems(good_css) == []
    assert weight_rule_problems(good_css.replace("var(--tt-title-sm)", "var(--tt-text-md)"), tokens)
    assert weight_rule_problems(good_css.replace('[data-font-weight="400"]', ".x"), tokens)
    assert weight_rule_problems(good_css.replace("font: var(--tt-title-sm);", "font: var(--tt-title-sm); font-weight: 700;"), tokens)
    assert row_style_problems(good_css.replace("white-space: pre;", ""))
    assert row_style_problems(good_css.replace("font-variant-ligatures: none;", ""))
    assert row_style_problems(good_css + ".a { letter-spacing: 1px; }")
    assert {n: len(t) for n, t in EXISTING_TEST_TITLES.items()} == {"font-specimen": 4, "showcase-overlays": 6, "showcase-forms": 6}
    assert sum(EXISTING_TEST_EXPECTS.values()) == 68
    assert len(BASE_DEMOS) == 10 and len(FORMS_DEMOS) == 11 and len(SHELL_DEMOS) == 2 and len(T007_DEMOS) == 7
    assert not set(BASE_DEMOS[:5]) & (set(FORMS_DEMOS) | set(T007_DEMOS) | set(BASE_DEMOS[5:]))


VITEST_SAMPLE = """
> themistally-desktop-web@0.0.0 test
> vitest run gate-probe/x.test.tsx --reporter=json

{
  "numTotalTestSuites": 2,
  "numPassedTests": 2,
  "testResults": [
    {"status": "failed", "assertionResults": [
      {"ancestorTitles": ["D01 甲"], "title": "a", "status": "passed", "failureMessages": []},
      {"ancestorTitles": ["D01 甲"], "title": "b", "status": "failed", "failureMessages": ["boom"]},
      {"ancestorTitles": ["D02 乙", "内层"], "title": "c", "status": "skipped", "failureMessages": []}
    ]},
    {"status": "failed", "message": "import error", "assertionResults": []}
  ]
}
(node:1) Warning: trailing noise }
"""


def test_gate_selfcheck_vitest_json_parser():
    """门禁自检：从带 npm 横幅和尾部噪声的输出里取出 Vitest 的 JSON，按最外层 describe 分组，跳过与失败都算没通过。"""
    data = parse_vitest_json(VITEST_SAMPLE)
    assert data and data["numTotalTestSuites"] == 2
    groups, errors = summarize_vitest(data)
    assert groups["D01 甲"]["passed"] == 1 and groups["D01 甲"]["bad"] == [("b", "failed", "boom")]
    assert groups["D02 乙"]["passed"] == 0 and groups["D02 乙"]["bad"][0][1] == "skipped"
    assert errors == ["import error"]
    assert parse_vitest_json("no json here") is None
    assert parse_vitest_json('{"numTotalTestSuites": ') is None


def test_gate_selfcheck_probe_templates():
    """门禁自检：8 份探针的分组与用例数、文件名约定与 vitest 的 include 一致；探针不用 skip、only、todo；fireEvent 来自
    @testing-library/react；占位符都能替换掉；括号成对；探针源码自己不含那四个网络词、T007 禁用词、十六进制颜色和颜色函数；
    Python 用例引用的分组名在探针里都找得到；写进探针的夹具、图标结构、Logo 的 d 取自 UI 文档与画布。"""
    expected = {
        "route": {"D01 路由与 Tab 栏": 12, "D04 快捷键": 8},
        "titlebar": {"D02 标题栏": 7, "D05 主题": 7, "S3 Logo 与图标": 2},
        "tabbar": {"D03 Tab 栏与状态段": 10},
        "frame": {"D09 页面框架": 12, "D11 禁用的写操作入口": 2},
        "pages": {"D10 页面占位": 4, "P10 App 级五态（经 ?mock= 演示）": 6,
                  "S7 状态分组（待验收与要你决定计入 Tab 计数，运行中单独数）": 2},
        "showcase": {"D12 陈列页收集与排序": 4, "P11 陈列页内容（基础组件与样张）": 3, "P11 陈列页内容（浮层演示）": 6,
                     "P11 陈列页内容（表单与数据演示）": 9, "P11 陈列页内容（外壳演示）": 2},
        "api": {"D06 数据层": 5, "D07 夹具开关": 5},
        "nonet": {"D08 运行时不连服务": 2},
    }
    assert {key: probe_groups(spec[0]) for key, spec in PROBE_SPECS.items()} == expected
    assert set(PROBE_ORDER) == set(PROBE_SPECS) and len(PROBE_ORDER) == len(PROBE_SPECS)
    assert set(P11_GROUPS) == {g for g in expected["showcase"] if g.startswith("P11")}
    vite_cfg = _read(need_file(f"{WEB_REL}/vite.config.ts"))
    assert "gate-probe/**/*.test.{ts,tsx}" in vite_cfg
    for key, (source, requires) in PROBE_SPECS.items():
        assert not re.search(r"\b(?:it|test|describe)\.(?:skip|todo|only|skipIf|runIf)\b|\bx(?:it|describe)\(|\.only\(", source), key
        assert "@testing-library/dom" not in source, key
        assert "from '@testing-library/react'" in source, key
        assert not [w for w in NET_WORDS + SINK_WORDS if w in source], (key, [w for w in NET_WORDS + SINK_WORDS if w in source])
        assert w4_literal_problems(key, source) == [], key
        built = build_probe_source(key)
        assert not re.search(r"__[A-Z][A-Z_]*__", built), key
        # 括号成对只查模板本身：注入的夹具文字里有不成对的括号（比如被截断的一行 JSON）
        assert source.count("(") == source.count(")"), (key, source.count("("), source.count(")"))
        assert source.count("{") == source.count("}"), (key, source.count("{"), source.count("}"))
        assert source.count("[") == source.count("]"), (key, source.count("["), source.count("]"))
        for mod in re.findall(r"import\('\.\./src/([^']+)'\)", source):
            assert any(req.endswith(f"/{mod}.tsx") or req.endswith(f"/{mod}.ts") for req in requires) or mod == "App", (key, mod, requires)
    test_source = Path(__file__).read_text(encoding="utf-8")
    for key, group in re.findall(r'assert_probe_group\(pipeline,\s*"(\w+)",\s*"([^"]+)"\)', test_source):
        assert group in probe_groups(PROBE_SPECS[key][0]), (key, group)
    used = {(key, group) for key, group in re.findall(r'assert_probe_group\(pipeline,\s*"(\w+)",\s*"([^"]+)"\)', test_source)}
    used |= {("showcase", g) for g in P11_GROUPS}
    every = {(key, g) for key, spec in PROBE_SPECS.items() for g in probe_groups(spec[0])}
    assert used == every, f"有探针分组没有 Python 用例核对：{sorted(every - used)}；或用例引用了不存在的分组：{sorted(used - every)}"
    assert canvas_logo()["mark"] in build_probe_source("titlebar")
    api_source = build_probe_source("api")
    assert "logs-cat" in api_source and "<img src=x onerror=alert(1)>" in api_source


def test_gate_selfcheck_run_capture():
    """门禁自检：run_capture 合并 stdout 与 stderr、返回退出码；超时会杀掉进程并标记超时。"""
    env = _make_env()
    py = shutil.which("python") or "python"
    code, timed_out, out, _seconds = run_capture([py, "--version"], REPO_ROOT, 60, env)
    assert code == 0 and not timed_out and "Python" in out
    code, timed_out, out, seconds = run_capture([py, "-m", "this_module_does_not_exist_t006"], REPO_ROOT, 60, env)
    assert code not in (0, None) and not timed_out and "No module named" in out
    assert STEP_CAPS["probe"] >= 30 and seconds < 30


def test_gate_selfcheck_pipeline_constants():
    """门禁自检：流水线预算与合同 V01 的超时（1200s）相容；每个探针有“需要先存在的文件”；基线上没有候选标记文件时夹具不跑 npm。"""
    assert PIPELINE_BUDGET + 120 <= 1200
    assert STEP_CAPS["npm ci"] + STEP_CAPS["npm run build"] + STEP_CAPS["npm test"] + STEP_CAPS["npm run check:contract"] >= 400
    assert all(spec[1] for spec in PROBE_SPECS.values())
    assert len(PROBE_SPECS) * STEP_CAPS["probe"] >= 400
    assert set(SHELL_FILES) >= {"router.ts", "routes.ts", "shortcuts.ts", "theme.ts"}
    assert ASSUMPTIONS and all(isinstance(a, str) for a in ASSUMPTIONS)
