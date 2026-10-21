"""T008 战前门禁：桌面端前端差异视图与日志跟随（第七片）的黑盒基准测试（合同 t008-desktop-diff，plan_version 1）。

被测对象是 ``desktop/web/``：差异视图 DiffView（自带 git 补丁解析 ``components/diff/parseDiff.ts`` 与分屏配对
``components/diff/splitPairs.ts``）、日志跟随 LogFollow（建在 T007 的 TextViewer 上）、3 个新图标（PauseIcon、FilterIcon、
FileDiffIcon）、TextViewer 追加的 6 个可选属性（站主 Q1 选甲：bodyRef、onBodyScroll、bodyClassName、headerExtra、bottomBar、filter）、
新演示 DiffShowcase（不挂到陈列页）。

基线（2b6563ef70，T007 结项）上这些都还没有，所以本文件的“失败”断言落在目标文件不存在或内容不符上，不是导入、收集或语法错误：
模块级只导入标准库，用到被测文件的地方都在用例函数里读；候选里还没有任何新组件文件时，``pipeline`` 夹具不跑 npm（没有东西可测，
也省掉联网的 ``npm ci``），用到它的用例以断言失败写明原因。

结构（编号对应合同“门禁断言”的 S1–S5、P1–P10；门禁端加了若干静态守卫和自检）：

- 静态断言（S 系列，不用流水线，全量 pytest 也跑）：读组件源码、CSS、``components/index.ts``、``icons/index.tsx``、演示的 CSS。
- 流水线断言（P 系列）：会话级夹具 ``pipeline`` 在 ``desktop/web`` 下按顺序跑 ``npm ci``、``npm run build``、``npm test``、
  ``npm run check:contract``，再把探针逐份写成 ``gate-probe/probe-<唯一标识>-t008-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除；前后各取一次 ``git status``。组件探针（parse、view、follow、filter、
  slots）与演示探针（showcase）分开写、分开跑，演示探针最后跑。全量 pytest 默认跳过用到 ``pipeline`` 的用例（``tests/conftest.py``），
  点名运行本文件时才跑。
- 门禁自检（``test_gate_selfcheck_*``，不依赖候选）：把检查函数喂给正确样本和改坏的样本。

DoD 对应（用例名里带 ``dNN``）：

- D01：parse 探针（R1–R10：路径、状态、计数、新文件、删除、改名、二进制两种写法、No newline、CRLF、以 ---、+++ 开头的内容行、
  缺省行数、多片段、乱码、R10 病态输入 2 秒）；
- D02、D04、D06、D03、D05：view 探针（统一视图、分屏配对、文件列表、折叠、二进制、没读完、模式与换行、只按文本显示）与 S4 的 CSS 取值；
- D07：follow 探针（跟随状态机，假计时器，主体打桩 scrollHeight、clientHeight、scrollTop）；D08：filter 探针（过滤）；
- D09：slots 探针（TextViewer 的 6 个可选属性，不传时的 DOM 与基线逐字相同）；
- D10：S1、S2（icons/index.tsx 与 index.ts 只在末尾追加、三个图标、四项新导出）；D11：showcase 探针（P9，过渡）；
- D12：S3、S5 与 W4（check:contract）；D13：P1（npm 四步）、P10（V02、V03 另证 T001–T005、T007 门禁与桌面端状态表）；
- D14：执行端 7 份测试在位且不用 skip、only、todo；改动范围由调度器的范围门禁证明，这里不写相对基线的范围断言。

过渡断言（``test_transitional_`` 开头）：只有 P9 一条，陈列页的演示改版（整理陈列页或换成真实页面）时推翻。其余（解析、组件行为、
CSS 取值、静态检查、图标、导出）都是长期断言。

写法约定：CSS 比较先归一空白；jsdom 不排版、不算层叠，宽、高、位置、色调读 CSS 文件的文本，探针只看结构、焦点、计时与属性；
合同写出的类名与 data-*（tt-diff*、tt-log*、data-mode、data-kind、data-side、data-follow 等）按合同当作约定；合同没有定类名的内部元素，
CSS 断言用“有一条规则同时声明了这几项”的写法；数据形状（parseDiff 返回的字段）采用合同写出的名字；splitPairs 的返回值合同没有定字段，
只从 DOM 与行数验证；悬停与聚焦的探针从 ``@testing-library/react`` 导入 ``fireEvent``；不写 skip、xfail、only、todo。

门禁做不到、留给人的项（合同 H1–H11）：视觉（暗色、亮色各一次）、真浏览器里的滚动手感与粘底、真浏览器里 W1 没有请求也没有 alert、
Windows 高对比度、读屏抽查、大补丁手感。
"""

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_REL = "desktop/web"
WEB = REPO_ROOT / "desktop" / "web"
SRC_REL = f"{WEB_REL}/src"
SRC = WEB / "src"
COMP_REL = f"{SRC_REL}/components"
DIFF_REL = f"{COMP_REL}/diff"
EVID_REL = f"{COMP_REL}/evidence"
SHOW_REL = f"{SRC_REL}/showcase"
TESTS_REL = f"{WEB_REL}/tests"

# 合同 Scope 的新增源码（allowed_new_files 里的非测试文件）。
NEW_SOURCE_FILES = (
    f"{COMP_REL}/DiffView.tsx",
    f"{COMP_REL}/DiffView.css",
    f"{DIFF_REL}/parseDiff.ts",
    f"{DIFF_REL}/splitPairs.ts",
    f"{COMP_REL}/LogFollow.tsx",
    f"{COMP_REL}/LogFollow.css",
    f"{SHOW_REL}/DiffShowcase.tsx",
    f"{SHOW_REL}/showcase-diff.css",
)
# 合同“执行端测试”：本片 7 份（含甲的 text-viewer-slots）。
EXECUTOR_TESTS = ("diff-parse.test.ts", "diff-view.test.tsx", "diff-css.test.ts", "log-follow.test.tsx",
                  "diff-showcase.test.tsx", "diff-static.test.ts", "text-viewer-slots.test.tsx")

# 合同 §6：本片两节的 data-demo；已有的 16 个（T003 的 5 个，T005 的 11 个）与 T007 的 7 个。
DIFF_DEMOS = ("diff-view", "log-follow")
EXISTING_DEMOS = ("icon-button", "menu", "dialog", "drawer", "toast",
                  "text-field", "form-dialog", "segmented", "switch-checkbox", "tabs", "table",
                  "key-value", "empty-state", "skeleton", "connection", "breadcrumb",
                  "text-viewer", "text-viewer-jsonl", "safe-markdown", "effort", "masked-value", "command-line", "next-step")

# 合同 §5：三个新图标（画布：领域板 :381、详情页 :638、:389）。
PAUSE_RECTS = [{"width": "4", "height": "14", "x": "6", "y": "5", "rx": "1"},
               {"width": "4", "height": "14", "x": "14", "y": "5", "rx": "1"}]
FILTER_POINTS = "22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"
FILE_DIFF_DS = [
    "M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z",
    "M9 10h6",
    "M12 13V7",
    "M9 17h6",
]

# 基线 2b6563ef70 的 components/index.ts 与 icons/index.tsx（行尾归一为 LF）：字节数与 sha256，用来证明“只在末尾追加”。
BASELINE_APPEND_ONLY = {
    f"{COMP_REL}/index.ts": (3493, "999aa49e1d934884b4f9a80303361dc7ee123b0a2e76bc66de987faad74a0f67"),
    f"{SRC_REL}/icons/index.tsx": (7479, "05eddd58acd46d94e1258a14e6762d3a677b75fe19b7f9eb9fcc024e363bc52a"),
}
BASELINE_EXPORTS = (
    "Button", "ButtonProps", "Tag", "TagProps", "StatusTag", "StatusTagProps", "Card", "CardProps", "Banner", "BannerProps",
    "IconButton", "IconButtonProps", "Tooltip", "TooltipProps", "Menu", "MenuProps", "Dialog", "DialogProps", "Drawer", "DrawerProps",
    "Toast", "ToastProps", "SegmentedControl", "SegmentedControlProps", "Switch", "SwitchProps", "Checkbox", "CheckboxProps",
    "Tabs", "TabsProps", "TextField", "TextFieldProps", "Select", "SelectProps", "Table", "TableProps", "KeyValueList",
    "KeyValueListProps", "EmptyState", "EmptyStateProps", "Skeleton", "SkeletonProps", "ConnectionPill", "ConnectionPillProps",
    "Breadcrumb", "BreadcrumbProps", "TextViewer", "TextViewerProps", "SafeMarkdown", "SafeMarkdownProps", "EffortPair",
    "EffortPairProps", "MaskedValue", "MaskedValueProps", "isMaskedPlaceholder", "CommandLine", "CommandLineProps", "dispatchCommand",
    "NextStep", "NextStepProps",
)
NEW_EXPORTS = ("DiffView", "DiffViewProps", "LogFollow", "LogFollowProps")

# 合同“公共约定”：静态检查禁用词（扫 desktop/web/src/**/*.{ts,tsx} 全文，含注释与字符串）。
FORBIDDEN_WORDS = ("dangerouslySetInnerHTML", "innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function",
                   "document.write", "srcdoc", "createContextualFragment", "DOMParser")
FORBIDDEN_CALLS = ("matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver")

# 合同检查项 V01 的 timeout 是 600s：夹具总预算压在 570s 以内，用完就停下并在断言里写明，不等调度器来杀。
PIPELINE_BUDGET = 570
STEP_CAPS = {
    "npm ci": 200,
    "npm run build": 120,
    "npm test": 240,
    "npm run check:contract": 40,
    "probe": 120,
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
    """条件：names 里所有声明的值拼起来，含全部 tokens（用来容忍 gap 与 row-gap/column-gap 两种写法）。"""
    names = (names,) if isinstance(names, str) else tuple(names)

    def check(decls):
        joined = "|".join(cv(v) for n, v in decls if n in names)
        return bool(joined) and all(cv(t) in joined for t in tokens)
    return check


def flex_one(decls):
    """条件：flex 写成 1（或 1 1 0 之类以 1 开头的三段写法），或 flex-grow: 1。"""
    for name, value in decls:
        v = value.strip().lower()
        if name == "flex" and re.match(r"^1(\s|$)", v):
            return True
        if name == "flex-grow" and v == "1":
            return True
    return False


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


def group_problems(css, label, specs):
    """specs: [(说明, 选择器正则或 None, [条件…])]；每条都要有一条规则同时满足全部条件。"""
    problems = []
    rules = parse_rules(css)
    for desc, sel, conds in specs:
        hit = False
        for selector, decls in rules:
            if sel and not re.search(sel, selector):
                continue
            if all(cond_ok(decls, c) for c in conds):
                hit = True
                break
        if not hit:
            where = f"（选择器含 {sel}）" if sel else ""
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
            elif name == "border-radius" and not re.fullmatch(r"(?:var\(--tt-radius-[\w-]+\)|0|0px)+|inherit", v):
                problems.append(f"{label}：{selector} 的 border-radius 应取 --tt-radius-* 令牌，实际 {value}")
            elif name == "box-shadow" and v != "none" and "var(--tt-" not in v:
                problems.append(f"{label}：{selector} 的 box-shadow 应取令牌，实际 {value}")
            elif name in ("font", "font-family", "font-size") and not (v.startswith("var(--tt-") or v == "inherit"):
                problems.append(f"{label}：{selector} 的 {name} 应取 --tt-* 字体令牌或 inherit，实际 {value}")
    return problems


# ---------------------------------------------------------------------------
# 选择器特异性计算器（跟随主体的 .tt-log .tt-log__body 要压过 .tt-viewer__body 的单类规则）
# ---------------------------------------------------------------------------

_NAME = re.compile(r"-?[A-Za-z_\u0080-￿][\w\-\u0080-￿]*")


def _matching_paren(text, i):
    depth, quote = 0, None
    for j in range(i, len(text)):
        ch = text[j]
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return j
    raise ValueError(f"括号不配对：{text!r}")


def _matching_bracket(text, i):
    quote = None
    for j in range(i + 1, len(text)):
        ch = text[j]
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "]":
            return j
    raise ValueError(f"方括号不配对：{text!r}")


def specificity(selector):
    """单个复杂选择器（不含顶层逗号）的特异性 (a, b, c)；:where() 记 0，:is()/:not()/:has() 取参数里最大的。"""
    a = b = c = 0
    i, n = 0, len(selector)
    while i < n:
        ch = selector[i]
        if ch == "#":
            m = _NAME.match(selector, i + 1)
            a += 1
            i = m.end() if m else i + 1
        elif ch == ".":
            m = _NAME.match(selector, i + 1)
            b += 1
            i = m.end() if m else i + 1
        elif ch == "[":
            b += 1
            i = _matching_bracket(selector, i) + 1
        elif ch == ":":
            if selector.startswith("::", i):
                m = _NAME.match(selector, i + 2)
                c += 1
                i = m.end() if m else i + 2
                continue
            m = _NAME.match(selector, i + 1)
            name = m.group(0).lower() if m else ""
            i = m.end() if m else i + 1
            if name in ("before", "after", "first-line", "first-letter"):
                c += 1
            elif i < n and selector[i] == "(":
                j = _matching_paren(selector, i)
                arg = selector[i + 1:j]
                i = j + 1
                if name == "where":
                    pass
                elif name in ("is", "not", "has", "matches"):
                    inner = [specificity(re.sub(r"^[\s>+~]+", "", p)) for p in split_top(arg) if p.strip()]
                    best = max(inner) if inner else (0, 0, 0)
                    a, b, c = a + best[0], b + best[1], c + best[2]
                else:
                    b += 1
            else:
                b += 1
        elif ch == "*" or ch in " \t\r\n>+~,|&":
            i += 1
        else:
            m = _NAME.match(selector, i)
            if m:
                c += 1
                i = m.end()
            else:
                i += 1
    return (a, b, c)


def rules_with_specificity_above(css, selector_re, conds, floor):
    """有没有一条选择器含 selector_re、满足 conds、且该选择器列表里匹配的那一项特异性高于 floor 的规则。"""
    for selector, decls in parse_rules(css):
        if not all(cond_ok(decls, c) for c in conds):
            continue
        for part in split_top(selector):
            if re.search(selector_re, part) and specificity(part) > floor:
                return True
    return False


# ---------------------------------------------------------------------------
# 本片 CSS 的取值（合同 §2、§3）
# ---------------------------------------------------------------------------

S0_5 = "var(--tt-space-0_5)"
S1 = "var(--tt-space-1)"
S2 = "var(--tt-space-2)"
S3 = "var(--tt-space-3)"
S4 = "var(--tt-space-4)"
S8 = "var(--tt-space-8)"


def look(*words):
    """选择器同时含这几个词（任意顺序）的正则。"""
    return "".join(f"(?=.*{w})" for w in words)


DIFF_SPECS = [
    ("根 .tt-diff：--tt-surface-1 底、1px --tt-border、--tt-radius-lg、overflow: hidden", r"\.tt-diff(?![\w-])",
     [C(("background", "background-color"), eq="var(--tt-surface-1)"),
      AnyOf(C("border", has=["1px", "var(--tt-border)"]), C("border-width", has=["1px"])),
      C("border-radius", eq="var(--tt-radius-lg)"), C("overflow", eq="hidden")]),
    ("工具栏 .tt-diff__bar：flex、可换行、垂直居中、间距 --tt-space-2 与 --tt-space-3", r"\.tt-diff__bar(?![\w-])",
     [C("display", eq="flex"), C("flex-wrap", eq="wrap"), C("align-items", eq="center"),
      HasAll(("gap", "row-gap", "column-gap"), S2, S3)]),
    ("工具栏：内边距上下 --tt-space-2、左右 --tt-space-3、下边框 1px", r"\.tt-diff__bar(?![\w-])",
     [sides_is("padding", top=S2, bottom=S2, left=S3, right=S3),
      C(("border-bottom", "border-block-end"), has=["1px"])]),
    ("摘要 .tt-diff__summary：--tt-text-sm、--tt-text-2", r"\.tt-diff__summary(?![\w-])",
     [C("font", eq="var(--tt-text-sm)"), C("color", eq="var(--tt-text-2)")]),
    ("标题：--tt-mono-sm", None, [C("font", eq="var(--tt-mono-sm)")]),
    ("加号计数 --tt-tone-success-fg", None, [C("color", eq="var(--tt-tone-success-fg)")]),
    ("减号计数 --tt-tone-danger-fg", None, [C("color", eq="var(--tt-tone-danger-fg)")]),
    ("分段靠右：margin-left: auto", None, [C(("margin-left", "margin-inline-start"), eq="auto")]),
    ("文件列表 .tt-diff__files：宽 260（handoff :149）", r"\.tt-diff__files(?![\w-])",
     [C(("width", "flex-basis", "flex", "min-width"), has=["260px"])]),
    ("文件列表：flex none（不伸缩）", r"\.tt-diff__files(?![\w-])",
     [AnyOf(C("flex", eq="none"), C("flex", has=["0", "0"]), C("flex-shrink", eq="0"))]),
    ("文件列表：右边框、内边距 --tt-space-1、纵向、间距 --tt-space-0_5、无列表符", r"\.tt-diff__files(?![\w-])",
     [C(("border-right", "border-inline-end"), has=["1px"]), C("padding", eq=S1), C("flex-direction", eq="column"),
      C(("gap", "row-gap"), eq=S0_5), AnyOf(C("list-style", eq="none"), C("list-style-type", eq="none"))]),
    ("列表项 .tt-diff__file-item：宽 100%、最小高 32、flex、间距 --tt-space-2", r"\.tt-diff__file-item(?![\w-])",
     [C("width", eq="100%"), C(("min-height", "height"), eq="32px"), C("display", eq="flex"), C(("gap", "column-gap"), eq=S2)]),
    ("列表项：内边距 --tt-space-1 与 --tt-space-2、无边框、--tt-radius-md、透明底、--tt-text-1、左对齐", r"\.tt-diff__file-item(?![\w-])",
     [sides_is("padding", top=S1, bottom=S1, left=S2, right=S2),
      AnyOf(C("border", eq="none"), C("border", zero=True), C("border-width", zero=True)),
      C("border-radius", eq="var(--tt-radius-md)"), C(("background", "background-color"), eq="transparent"),
      C("color", eq="var(--tt-text-1)"), C("text-align", eq="left")]),
    ("当前项：--tt-surface-selected", r"file-item.*aria-current", [C(("background", "background-color"), eq="var(--tt-surface-selected)")]),
    ("悬停项：--tt-surface-3", r"file-item.*:hover", [C(("background", "background-color"), eq="var(--tt-surface-3)")]),
    ("列表路径 .tt-diff__file-path：flex 1、min-width 0、--tt-mono-sm、单行左截断（overflow hidden、ellipsis、nowrap、direction rtl、text-align left）",
     r"\.tt-diff__file-path(?![\w-])",
     [flex_one, C("min-width", zero=True), C("font", eq="var(--tt-mono-sm)"), C("overflow", eq="hidden"),
      C("text-overflow", eq="ellipsis"), C("white-space", eq="nowrap"), C("direction", eq="rtl"), C("text-align", eq="left")]),
    ("列表路径里层 span：direction ltr、unicode-bidi isolate", r"\.tt-diff__file-path\s*>?\s*(span|\*)",
     [C("direction", eq="ltr"), C("unicode-bidi", eq="isolate")]),
    ("「二进制」与注记：--tt-text-caption、--tt-text-3", None,
     [C("font", eq="var(--tt-text-caption)"), C("color", eq="var(--tt-text-3)")]),
    ("文件区：flex 1、min-width 0、纵向、间距与内边距 --tt-space-3", None,
     [flex_one, C("min-width", zero=True), C("flex-direction", eq="column"), C(("gap", "row-gap"), eq=S3),
      C("padding", eq=S3)]),
    ("文件卡片 .tt-diff__file：1px --tt-border、--tt-radius-md、overflow: hidden", r"\.tt-diff__file(?![\w-])",
     [AnyOf(C("border", has=["1px", "var(--tt-border)"]), C("border-width", has=["1px"])),
      C("border-radius", eq="var(--tt-radius-md)"), C("overflow", eq="hidden")]),
    ("文件头 .tt-diff__file-head：flex、垂直居中、间距 --tt-space-2、高 36", r"\.tt-diff__file-head(?![\w-])",
     [C("display", eq="flex"), C("align-items", eq="center"), C(("gap", "column-gap"), eq=S2),
      C(("height", "min-height"), eq="36px")]),
    ("文件头：左内边距 --tt-space-2、右 --tt-space-1、--tt-surface-2、下边框", r"\.tt-diff__file-head(?![\w-])",
     [sides_is("padding", left=S2, right=S1), C(("background", "background-color"), eq="var(--tt-surface-2)"),
      C(("border-bottom", "border-block-end"), has=["1px"])]),
    ("折叠着的文件头没有下边框", r"data-collapsed",
     [AnyOf(C(("border-bottom", "border-block-end"), eq="none"), C(("border-bottom", "border-block-end"), zero=True),
            C(("border-bottom-width", "border-block-end-width"), zero=True),
            C(("border-bottom-color", "border-block-end-color"), eq="transparent"))]),
    ("二进制的文件头：左内边距 40（详情页 :458）", r"data-binary", [sides_is("padding", left="40px")]),
    ("折叠钮 .tt-diff__file-head .tt-icon-btn：24×24、--tt-radius-sm", r"\.tt-diff__file-head\s+\.tt-icon-btn",
     [C(("width", "min-width"), eq="24px"), C(("height", "min-height"), eq="24px"), C("border-radius", eq="var(--tt-radius-sm)")]),
    ("路径 .tt-diff__file-name：--tt-mono-sm、单行右侧省略", r"\.tt-diff__file-name(?![\w-])",
     [C("font", eq="var(--tt-mono-sm)"), C("white-space", eq="nowrap"), C("overflow", eq="hidden"), C("text-overflow", eq="ellipsis")]),
    ("注记 .tt-diff__file-note：--tt-text-caption、--tt-text-3", r"\.tt-diff__file-note(?![\w-])",
     [C("font", eq="var(--tt-text-caption)"), C("color", eq="var(--tt-text-3)")]),
    ("文件主体 .tt-diff__file-body：overflow-x: auto", r"\.tt-diff__file-body(?![\w-])", [C("overflow-x", eq="auto")]),
    ("说明（二进制、没有内容改动、补丁里没有改动）：内边距 --tt-space-3 与 --tt-space-4、--tt-text-sm、--tt-text-3", None,
     [sides_is("padding", top=S3, bottom=S3, left=S4, right=S4), C("font", eq="var(--tt-text-sm)"), C("color", eq="var(--tt-text-3)")]),
    ("行：--tt-mono-md", None, [C("font", eq="var(--tt-mono-md)")]),
    ("统一视图列：44px 44px 18px minmax(0, 1fr)", None, [C("grid-template-columns", eq="44px 44px 18px minmax(0, 1fr)")]),
    ("分屏列：44px 18px minmax(0, 1fr) 44px 18px minmax(0, 1fr)", None,
     [C("grid-template-columns", eq="44px 18px minmax(0, 1fr) 44px 18px minmax(0, 1fr)")]),
    ("统一视图行最小宽 560（handoff :149）", None, [C("min-width", eq="560px")]),
    ("分屏行最小宽 760（handoff :149）", None, [C("min-width", eq="760px")]),
    ("换行关：表格 width: max-content、min-width: 100%", None, [C("width", eq="max-content"), C("min-width", eq="100%")]),
    ("换行关：文字 white-space: pre", None, [C("white-space", eq="pre")]),
    ("换行开：文字 white-space: pre-wrap、word-break: break-all", None,
     [C("white-space", eq="pre-wrap"), C("word-break", eq="break-all")]),
    ("统一视图 add 行底色 --tt-diff-add", look("data-kind.{0,4}add"), [C(("background", "background-color"), eq="var(--tt-diff-add)")]),
    ("统一视图 del 行底色 --tt-diff-del", look("data-kind.{0,4}del"), [C(("background", "background-color"), eq="var(--tt-diff-del)")]),
    ("hunk 行底色 --tt-surface-2、文字 --tt-text-3", look("data-kind.{0,4}hunk"),
     [C(("background", "background-color"), eq="var(--tt-surface-2)"), C("color", eq="var(--tt-text-3)")]),
    ("分屏 empty 格底色 --tt-surface-2", look("data-kind.{0,4}empty"), [C(("background", "background-color"), eq="var(--tt-surface-2)")]),
    ("分屏左侧文字格右边框 1px", look("data-side.{0,4}left"), [C(("border-right", "border-inline-end"), has=["1px"])]),
    ("分屏的 hunk 行：左内边距 --tt-space-3、white-space: pre", look("hunk"),
     [sides_is("padding", left=S3), C("white-space", eq="pre")]),
    ("行号 .tt-diff__no：右对齐、右内边距 --tt-space-2、--tt-text-3、不可选中", r"\.tt-diff__no(?![\w-])",
     [C("text-align", eq="right"), sides_is("padding", right=S2), C("color", eq="var(--tt-text-3)"), C("user-select", eq="none")]),
    ("统一视图的新行号格右边框 1px（详情页 :418）", look(r"\.tt-diff__no"), [C(("border-right", "border-inline-end"), has=["1px"])]),
    ("符号 .tt-diff__sign：居中、字重 600（详情页 :419）、不可选中", r"\.tt-diff__sign(?![\w-])",
     [C("text-align", eq="center"), C("font-weight", eq="600"), C("user-select", eq="none")]),
    ("add 符号 --tt-tone-success-fg", look("add", "sign"), [C("color", eq="var(--tt-tone-success-fg)")]),
    ("del 符号 --tt-tone-danger-fg", look("del", "sign"), [C("color", eq="var(--tt-tone-danger-fg)")]),
    ("统一视图文字右内边距 --tt-space-3", look(r"\.tt-diff__text"), [sides_is("padding", right=S3)]),
    ("分屏文字右内边距 --tt-space-2", look("text|data-side"), [sides_is("padding", right=S2)]),
    ("eof 注记 .tt-diff__eof：--tt-text-3、左外边距 --tt-space-1、不可选中", r"\.tt-diff__eof(?![\w-])",
     [C("color", eq="var(--tt-text-3)"), sides_is("margin", left=S1), C("user-select", eq="none")]),
    ("底部 .tt-diff__foot：--tt-surface-2、上边框、内边距 --tt-space-2 与 --tt-space-3、--tt-text-caption、--tt-text-3",
     r"\.tt-diff__foot(?![\w-])",
     [C(("background", "background-color"), eq="var(--tt-surface-2)"), C(("border-top", "border-block-start"), has=["1px"]),
      sides_is("padding", top=S2, bottom=S2, left=S3, right=S3), C("font", eq="var(--tt-text-caption)"),
      C("color", eq="var(--tt-text-3)")]),
    ("底部按钮靠右", None,
     [AnyOf(C(("margin-left", "margin-inline-start"), eq="auto"), C("justify-content", has=["flex-end"]),
            C("justify-content", has=["space-between"]))]),
]


def diff_css_extra_problems(css):
    """折叠钮的选择器特异性要高于 IconButton 的单类规则；user-select: none 至少覆盖行号、符号、eof。"""
    problems = []
    if not rules_with_specificity_above(css, r"\.tt-diff__file-head\s+\.tt-icon-btn", [C(("width", "min-width"), eq="24px")], (0, 1, 0)):
        problems.append("DiffView.css：折叠钮缩成 24 的规则特异性应高于 IconButton 的单类规则（0,1,0）（合同：.tt-diff__file-head .tt-icon-btn，(0,2,0)）")
    n = sum(1 for _s, d in parse_rules(css) if cond_ok(d, C("user-select", eq="none")))
    if n < 3:
        problems.append(f"DiffView.css：user-select: none 的规则应至少 3 条（行号、符号、eof），实际 {n} 条")
    return problems


LOG_SPECS = [
    ("跟随主体：max-height 480（规划端定）、overflow-y: auto", r"tt-log__body",
     [C("max-height", eq="480px"), C("overflow-y", eq="auto")]),
    ("过滤框外层 .tt-log__filter：position relative、flex 0 1 360px、min-width 200", r"\.tt-log__filter(?![\w-])",
     [C("position", eq="relative"), C(("flex", "flex-basis"), has=["360px"]), C("min-width", eq="200px")]),
    ("过滤框图标：position absolute、left 10、top 9、--tt-text-3（详情页 :638）", look(r"\.tt-log__filter", "svg|\\.tt-i|icon"),
     [C("position", eq="absolute"), C("left", eq="10px"), C("top", eq="9px"), C("color", eq="var(--tt-text-3)")]),
    ("输入框 .tt-log__filter-input：宽 100%、高 32、右内边距 --tt-space-2、左内边距 --tt-space-8", r"\.tt-log__filter-input(?![\w-])",
     [C("width", eq="100%"), C(("height", "min-height"), eq="32px"), sides_is("padding", right=S2, left=S8)]),
    ("输入框：1px --tt-border-strong、--tt-radius-md、--tt-surface-1、--tt-text-1、--tt-text-sm", r"\.tt-log__filter-input(?![\w-])",
     [AnyOf(C("border", has=["1px", "var(--tt-border-strong)"]), C("border-color", eq="var(--tt-border-strong)")),
      C("border-radius", eq="var(--tt-radius-md)"), C(("background", "background-color"), eq="var(--tt-surface-1)"),
      C("color", eq="var(--tt-text-1)"), C("font", eq="var(--tt-text-sm)")]),
    ("跟随 .tt-log__follow：inline-flex", r"\.tt-log__follow(?![\w-])", [C("display", eq="inline-flex")]),
    ("跟随与过滤框间距 --tt-space-2", look("tt-log__follow|tt-log__filter"),
     [HasAll(("margin-left", "margin-inline-start", "gap", "column-gap"), S2)]),
    ("底部状态 .tt-log__status：flex、垂直居中、间距 --tt-space-2、内边距 --tt-space-2 与 --tt-space-3、上边框", r"\.tt-log__status(?![\w-])",
     [C("display", eq="flex"), C("align-items", eq="center"), C(("gap", "column-gap"), eq=S2),
      sides_is("padding", top=S2, bottom=S2, left=S3, right=S3), C(("border-top", "border-block-start"), has=["1px"])]),
    ("following、off、disabled：--tt-surface-2、--tt-text-3、--tt-text-caption", None,
     [C(("background", "background-color"), eq="var(--tt-surface-2)"), C("color", eq="var(--tt-text-3)"),
      C("font", eq="var(--tt-text-caption)")]),
    ("paused：--tt-tone-neutral-bg、--tt-tone-neutral-fg、--tt-text-sm（领域板 :380）", look("paused"),
     [C(("background", "background-color"), eq="var(--tt-tone-neutral-bg)"), C("color", eq="var(--tt-tone-neutral-fg)"),
      C("font", eq="var(--tt-text-sm)")]),
    ("状态里的按钮靠右：margin-left: auto", None, [C(("margin-left", "margin-inline-start"), eq="auto")]),
]


def log_css_extra_problems(css):
    """跟随主体的限高规则要压过 T007 的 .tt-viewer__body（单类，(0,1,0)）。"""
    if rules_with_specificity_above(css, r"tt-log__body", [C("max-height", eq="480px")], (0, 1, 0)):
        return []
    return ["LogFollow.css：max-height 480 的规则特异性应高于 .tt-viewer__body 的 (0,1,0)（合同 C12：.tt-log .tt-log__body，(0,2,0)）"]


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
    code = strip_ts_comments(text)
    if re.search(r"overlay", code):
        problems.append("components/index.ts 去掉注释后不该出现 overlay")
    if re.search(r"evidence/|ansi|viewerLines|from\s+['\"]\./diff|parseDiff|splitPairs", code):
        problems.append("components/index.ts 不该导出 evidence/ 或 diff/ 下的内部纯函数")
    if "共五片" not in text:
        problems.append("components/index.ts 的文件头注释应保持「共五片」（T007 门禁 P1 依赖，合同 C6）")
    tail = text.replace("\r\n", "\n")
    if check_prefix:
        tail = tail.encode("utf-8")[BASELINE_APPEND_ONLY[f"{COMP_REL}/index.ts"][0]:].decode("utf-8", "replace")
    if "第 7 片：差异视图（7.14）与日志跟随（7.15）" not in tail:
        problems.append("components/index.ts 末尾追加的部分应带注释「第 7 片：差异视图（7.14）与日志跟随（7.15）」")
    return problems


def src_ts_files():
    out = []
    for ext in ("ts", "tsx"):
        out += sorted(SRC.rglob(f"*.{ext}"))
    return out


def forbidden_word_problems(files):
    problems = []
    for path in files:
        text = _read(path)
        for word in FORBIDDEN_WORDS:
            if word in text:
                lineno = text[:text.index(word)].count("\n") + 1
                problems.append(f"{path.relative_to(WEB).as_posix()}:{lineno} 出现禁用词 {word}")
    return problems


def diff_component_sources():
    """DiffView.tsx、LogFollow.tsx 与 diff/ 下的源码（合同：不出现 href、src=、target=）。"""
    files = [REPO_ROOT / f"{COMP_REL}/DiffView.tsx", REPO_ROOT / f"{COMP_REL}/LogFollow.tsx"]
    folder = REPO_ROOT / DIFF_REL
    if folder.is_dir():
        files += sorted(folder.glob("*.ts")) + sorted(folder.glob("*.tsx"))
    return [p for p in files if p.is_file()]


def new_source_problems(files):
    """新组件与 diff/ 的源码：不出现 href、src=、target=（全文）；不渲染 role=status、不调四个禁用接口（去注释后）。"""
    problems = []
    for path in files:
        raw = _read(path)
        label = path.relative_to(WEB).as_posix()
        for word in ("href", "src=", "target="):
            if word in raw:
                lineno = raw[:raw.index(word)].count("\n") + 1
                problems.append(f"{label}:{lineno} 出现 {word}（合同：DiffView.tsx、LogFollow.tsx、diff/ 的源码里不出现 href、src=、target=）")
        problems += role_and_interface_problems(label, raw)
    return problems


def role_and_interface_problems(label, raw):
    problems = []
    code = strip_ts_comments(raw)
    if re.search(r"""role\s*[=:]\s*\{?\s*["']status["']""", code):
        problems.append(f"{label}：不能渲染 role=status")
    for name in FORBIDDEN_CALLS:
        if re.search(rf"\b{name}\b", code):
            problems.append(f"{label}：不能用 {name}")
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
    wants = {
        "PauseIcon": {"rects": PAUSE_RECTS, "polygons": [], "paths": []},
        "FilterIcon": {"rects": [], "polygons": [FILTER_POINTS], "paths": []},
        "FileDiffIcon": {"rects": [], "polygons": [], "paths": FILE_DIFF_DS},
    }
    for name, want in wants.items():
        block = icon_block(icons_text, name)
        if block is None:
            problems.append(f"icons/index.tsx 没有 export const {name}")
            continue
        if "<Svg" not in block:
            problems.append(f"{name} 应沿用 Svg 包装")
        rects = [tag_attrs(r) for r in re.findall(r"<rect\b([^>]*)>", block)]
        if rects != want["rects"]:
            problems.append(f"{name} 的 rect 应依次为 {want['rects']}，实际 {rects}")
        polys = [tag_attrs(p).get("points") for p in re.findall(r"<polygon\b([^>]*)>", block)]
        if polys != want["polygons"]:
            problems.append(f"{name} 的 polygon points 应为 {want['polygons']}，实际 {polys}")
        ds = [tag_attrs(p).get("d") for p in re.findall(r"<path\b([^>]*)>", block)]
        if ds != want["paths"]:
            problems.append(f"{name} 的 path d 应依次为 {want['paths']}，实际 {ds}")
        if re.search(r"\b(?:fill|stroke)\s*=", block):
            problems.append(f"{name} 不该自己写 fill、stroke（沿用 Svg 包装；G2 test_g8_icons_dir）")
    tail = icons_text.replace("\r\n", "\n")
    if check_prefix:
        tail = tail.encode("utf-8")[BASELINE_APPEND_ONLY[f"{SRC_REL}/icons/index.tsx"][0]:].decode("utf-8", "replace")
    if "路径照画布" not in tail:
        problems.append("icons/index.tsx 末尾追加的部分应带注释「路径照画布」")
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


SHOWCASE_NOTE = re.compile(r"演示自定|handoff|领域板|组件板|Attempt|UI 文档|写操作页|画布|详情页|规划端定")


def showcase_px_note_problems(label, raw):
    """合同公共约定：每个除 0 与 1px 外的 px 字面量，同一行注释写「演示自定」或出处。"""
    problems = px_literal_problems(label, raw)
    for no, ln in enumerate(raw.splitlines(), 1):
        code = re.sub(r"/\*.*?\*/", "", ln)
        if re.search(r"(?<![\w.#-])(?!1px\b)(?!0px\b)-?\d*\.?\d+px\b", code) and not SHOWCASE_NOTE.search(ln):
            problems.append(f"{label}:{no} 尺寸注释应写出处或「演示自定」：{ln.strip()[:70]}")
    return problems


def component_css_note_problems(label, raw):
    """DiffView.css、LogFollow.css：px 字面量的出处只能是 handoff 行号、画布简称加行号、规划端定（演示自定只给演示）。"""
    problems = px_literal_problems(label, raw)
    for no, ln in enumerate(raw.splitlines(), 1):
        code = re.sub(r"/\*.*?\*/", "", ln)
        if re.search(r"(?<![\w.#-])(?!1px\b)(?!0px\b)-?\d*\.?\d+px\b", code):
            note = "".join(re.findall(r"/\*(.*?)\*/", ln))
            if not re.search(r"handoff\s*:?\s*\d+|:\s*\d+|规划端定|画布|领域板|组件板|详情页|Attempt|UI 文档", note):
                problems.append(f"{label}:{no} 尺寸注释应写出处（handoff 行号、画布简称加行号或规划端定）：{ln.strip()[:70]}")
    return problems


# ---------------------------------------------------------------------------
# 探针（Vitest + jsdom）：每份一个 describe，用例数必须全部通过
# ---------------------------------------------------------------------------

PRELUDE = r"""
import * as React from 'react';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function textOf(el: Element | null): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function squash(s: string | null | undefined): string {
  return (s || '').replace(/\s+/g, '');
}
function advance(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}
function noStatusRole() {
  expect(document.querySelector('[role="status"]'), '新组件不能渲染 role=status').toBeNull();
}
function buttonsByText(root: ParentNode, text: string): HTMLButtonElement[] {
  return Array.from(root.querySelectorAll('button')).filter((b) => textOf(b) === text) as HTMLButtonElement[];
}
function buttonByText(root: ParentNode, text: string): HTMLButtonElement {
  const hits = buttonsByText(root, text);
  expect(hits.length, '找不到文字为「' + text + '」的按钮').toBeGreaterThan(0);
  return hits[0];
}
async function settle(cond: () => boolean, label: string) {
  for (let i = 0; i < 80; i += 1) {
    if (cond()) return;
    await act(async () => {
      await new Promise((r) => setTimeout(r, 25));
    });
  }
  throw new Error('等待超时：' + label);
}
"""

# 补丁样例（parse、view 两份探针共用）：改动文件（两个片段）、新文件、删除的文件（含以 --- 开头的删除行）。
FIXTURES = r"""
const ESC = '\u001b';
const L = (...rows: string[]) => rows.join('\n') + '\n';
const IDX = 'index 1111111111111111111111111111111111111111..2222222222222222222222222222222222222222 100644';

const MOD_FILE = [
  'diff --git a/src/app.ts b/src/app.ts',
  IDX,
  '--- a/src/app.ts',
  '+++ b/src/app.ts',
  '@@ -1,4 +1,5 @@ function main()',
  ' ctx1',
  '-old1',
  '-old2',
  '+new1',
  '+new2',
  '+new3',
  ' ctx2',
  '@@ -20,3 +21,2 @@',
  ' ctx3',
  '-gone',
  ' ctx4',
];
const NEW_FILE = [
  'diff --git a/docs/新文件.md b/docs/新文件.md',
  'new file mode 100644',
  'index 0000000000000000000000000000000000000000..3333333333333333333333333333333333333333',
  '--- /dev/null',
  '+++ b/docs/新文件.md',
  '@@ -0,0 +1,3 @@',
  '+line1',
  '+++ not a header',
  '+line3',
];
const DEL_FILE = [
  'diff --git a/old/removed.txt b/old/removed.txt',
  'deleted file mode 100644',
  'index 4444444444444444444444444444444444444444..0000000000000000000000000000000000000000',
  '--- a/old/removed.txt',
  '+++ /dev/null',
  '@@ -1,3 +0,0 @@',
  '-r1',
  '--- r2 looks like a header',
  '-r3',
];
const P3 = L(...MOD_FILE, ...NEW_FILE, ...DEL_FILE);
"""

# ---- parse：parseDiff 与 splitPairs（D01、D03 的配对行数） ----
PROBE_PARSE = PRELUDE + FIXTURES + r"""
let parseDiff: any;
let splitPairs: any;

beforeAll(async () => {
  const pm: any = await import('../src/components/diff/parseDiff');
  parseDiff = pm.parseDiff ?? pm.default;
  const sm: any = await import('../src/components/diff/splitPairs');
  splitPairs = sm.splitPairs ?? sm.default;
});

const MIB = 1024 * 1024;

function brief(f: any) {
  return { old: f.oldPath, nw: f.newPath, status: f.status, binary: Boolean(f.binary), hunks: f.hunks.length, add: f.additions, del: f.deletions };
}
function rowsOf(h: any) {
  return h.lines.map((l: any) => [l.kind, l.oldNo, l.newNo, l.text, Boolean(l.noNewline)]);
}
function headerOf(h: any) {
  return [h.header, h.oldStart, h.oldLines, h.newStart, h.newLines];
}
function timed(label: string, patch: string) {
  const t0 = Date.now();
  const r = parseDiff(patch);
  const dt = Date.now() - t0;
  expect(dt, label + ' 应在 2 秒内返回，实际 ' + dt + 'ms').toBeLessThan(2000);
  return r;
}

describe('parseDiff', () => {
  it('导出 parseDiff；三个文件的顺序、路径、状态、计数都对（D01）', () => {
    expect(typeof parseDiff).toBe('function');
    const files = parseDiff(P3);
    expect(Array.isArray(files)).toBe(true);
    expect(files.map(brief)).toEqual([
      { old: 'src/app.ts', nw: 'src/app.ts', status: 'modified', binary: false, hunks: 2, add: 3, del: 3 },
      { old: null, nw: 'docs/新文件.md', status: 'added', binary: false, hunks: 1, add: 3, del: 0 },
      { old: 'old/removed.txt', nw: null, status: 'deleted', binary: false, hunks: 1, add: 0, del: 3 },
    ]);
  });

  it('改动文件：两个片段各自从片段头起算行号，行的 kind、oldNo、newNo、text 逐项对（D01）', () => {
    const [f0] = parseDiff(P3);
    expect(f0.hunks.map(headerOf)).toEqual([
      ['@@ -1,4 +1,5 @@ function main()', 1, 4, 1, 5],
      ['@@ -20,3 +21,2 @@', 20, 3, 21, 2],
    ]);
    expect(rowsOf(f0.hunks[0])).toEqual([
      ['context', 1, 1, 'ctx1', false],
      ['del', 2, null, 'old1', false],
      ['del', 3, null, 'old2', false],
      ['add', null, 2, 'new1', false],
      ['add', null, 3, 'new2', false],
      ['add', null, 4, 'new3', false],
      ['context', 4, 5, 'ctx2', false],
    ]);
    expect(rowsOf(f0.hunks[1])).toEqual([
      ['context', 20, 21, 'ctx3', false],
      ['del', 21, null, 'gone', false],
      ['context', 22, 22, 'ctx4', false],
    ]);
  });

  it('新文件：--- /dev/null、@@ -0,0 +1,3 @@，新行号 1 到 3；+++ 开头的内容行算新增（去掉一个加号），不当文件头（D01）', () => {
    const [, f1] = parseDiff(P3);
    expect(f1.hunks.map(headerOf)).toEqual([['@@ -0,0 +1,3 @@', 0, 0, 1, 3]]);
    expect(rowsOf(f1.hunks[0])).toEqual([
      ['add', null, 1, 'line1', false],
      ['add', null, 2, '++ not a header', false],
      ['add', null, 3, 'line3', false],
    ]);
  });

  it('删除的文件：deleted file mode、+++ /dev/null；--- 开头的内容行算删除（去掉一个减号），不当文件头（D01）', () => {
    const [, , f2] = parseDiff(P3);
    expect(f2.hunks.map(headerOf)).toEqual([['@@ -1,3 +0,0 @@', 1, 3, 0, 0]]);
    expect(rowsOf(f2.hunks[0])).toEqual([
      ['del', 1, null, 'r1', false],
      ['del', 2, null, '-- r2 looks like a header', false],
      ['del', 3, null, 'r3', false],
    ]);
  });

  it('CRLF 与 LF 的结果逐项相同，内容里没有回车符；末尾有没有换行结果相同（R1）', () => {
    const lf = parseDiff(P3);
    const crlf = parseDiff(P3.replace(/\n/g, '\r\n'));
    expect(JSON.stringify(crlf)).toBe(JSON.stringify(lf));
    expect(JSON.stringify(crlf).includes('\\r')).toBe(false);
    expect(JSON.stringify(parseDiff(P3.slice(0, -1)))).toBe(JSON.stringify(lf));
    expect(JSON.stringify(parseDiff(P3.slice(0, -1).replace(/\n/g, '\r\n')))).toBe(JSON.stringify(lf));
  });

  it('No newline 标记：记在本片段上一行、不计数、不推进行号；剩余行数用完后的标记也记给上一行（D01）', () => {
    const patch = L(
      'diff --git a/a.txt b/a.txt', IDX, '--- a/a.txt', '+++ b/a.txt', '@@ -1,2 +1,2 @@',
      ' keep', '-last', '\\ No newline at end of file', '+last2', '\\ No newline at end of file',
      'diff --git a/b.txt b/b.txt', IDX, '--- a/b.txt', '+++ b/b.txt', '@@ -1 +1,2 @@',
      '-x', '+x', '+y', '\\ No newline at end of file',
    );
    const [a, b] = parseDiff(patch);
    expect(rowsOf(a.hunks[0])).toEqual([
      ['context', 1, 1, 'keep', false],
      ['del', 2, null, 'last', true],
      ['add', null, 2, 'last2', true],
    ]);
    expect(a.hunks[0].lines.length).toBe(3);
    expect(brief(a).add).toBe(1);
    expect(brief(a).del).toBe(1);
    expect(rowsOf(b.hunks[0])).toEqual([
      ['del', 1, null, 'x', false],
      ['add', null, 1, 'x', false],
      ['add', null, 2, 'y', true],
    ]);
  });

  it('片段头 @@ -1 +1 @@ 行数缺省为 1；片段头后面的文字保留在 header 里；下一个片段从自己的片段头起算（R6）', () => {
    const patch = L(
      'diff --git a/a.txt b/a.txt', IDX, '--- a/a.txt', '+++ b/a.txt',
      '@@ -3 +3 @@ trailing words here', '-a', '+b',
      '@@ -10,2 +12 @@', ' c', '-d', '+e',
    );
    const [f] = parseDiff(patch);
    expect(f.hunks.map(headerOf)).toEqual([
      ['@@ -3 +3 @@ trailing words here', 3, 1, 3, 1],
      ['@@ -10,2 +12 @@', 10, 2, 12, 1],
    ]);
    expect(rowsOf(f.hunks[0])).toEqual([['del', 3, null, 'a', false], ['add', null, 3, 'b', false]]);
    expect(rowsOf(f.hunks[1])).toEqual([['context', 10, 12, 'c', false], ['del', 11, null, 'd', false]]);
  });

  it('不合格的 @@ 行忽略；剩余行数用完后多出来的内容行被忽略；空行算内容为空的 context；片段没写完就遇到 diff --git 时开始下一个文件（R2、R6、R7）', () => {
    const patch = L(
      'diff --git a/a.txt b/a.txt', IDX, '--- a/a.txt', '+++ b/a.txt',
      '@@ garbage @@', '+ignored', '@@ -1,2 +1,2', '+ignored too',
      '@@ -1,3 +1,3 @@', ' a', '', ' c', ' extra after the hunk is full', '-ignored',
      'diff --git a/b.txt b/b.txt', IDX, '--- a/b.txt', '+++ b/b.txt', '@@ -1,5 +1,5 @@', ' only', '-one',
      'diff --git a/c.txt b/c.txt', IDX, '--- a/c.txt', '+++ b/c.txt', '@@ -1 +1 @@', '-p', '+q',
    );
    const files = parseDiff(patch);
    expect(files.map((f: any) => [f.newPath, f.hunks.length])).toEqual([['a.txt', 1], ['b.txt', 1], ['c.txt', 1]]);
    expect(rowsOf(files[0].hunks[0])).toEqual([
      ['context', 1, 1, 'a', false],
      ['context', 2, 2, '', false],
      ['context', 3, 3, 'c', false],
    ]);
    expect(rowsOf(files[1].hunks[0])).toEqual([['context', 1, 1, 'only', false], ['del', 2, null, 'one', false]]);
    expect(rowsOf(files[2].hunks[0])).toEqual([['del', 1, null, 'p', false], ['add', null, 1, 'q', false]]);
  });

  it('改名：纯改名（similarity index、rename from、rename to，没有片段）与带片段的改名都是 renamed，路径不去 a/ b/ 前缀以外的东西（D01、R3、R8）', () => {
    const patch = L(
      'diff --git a/old/a.txt b/new/b.txt', 'similarity index 100%', 'rename from old/a.txt', 'rename to new/b.txt',
      'diff --git a/x.txt b/y.txt', 'similarity index 90%', 'rename from x.txt', 'rename to y.txt',
      'index aaaaaaa..bbbbbbb 100644', '--- a/x.txt', '+++ b/y.txt', '@@ -1 +1 @@', '-a', '+b',
    );
    const files = parseDiff(patch);
    expect(files.map(brief)).toEqual([
      { old: 'old/a.txt', nw: 'new/b.txt', status: 'renamed', binary: false, hunks: 0, add: 0, del: 0 },
      { old: 'x.txt', nw: 'y.txt', status: 'renamed', binary: false, hunks: 1, add: 1, del: 1 },
    ]);
  });

  it('二进制两种写法：Binary files 一行；GIT binary patch 加两个块，整块（含像片段头的行）跳到下一个 diff --git，之后的文件照常解析（F6、R3）', () => {
    const patch = L(
      'diff --git a/img/logo.png b/img/logo.png', 'new file mode 100644',
      'index 0000000000000000000000000000000000000000..5555555555555555555555555555555555555555',
      'GIT binary patch', 'literal 12', 'Tcmb(d$jHrq^!}H5r`c', '--- a/fake', '+++ b/fake', '@@ -1 +1 @@', '+nope', '-nope', '',
      'literal 0', 'HcmV?d00001', '',
      'diff --git a/after.txt b/after.txt', IDX, '--- a/after.txt', '+++ b/after.txt', '@@ -1 +1 @@', '-a', '+b',
      'diff --git a/bin/data.bin b/bin/data.bin', IDX, 'Binary files a/bin/data.bin and b/bin/data.bin differ',
      'diff --git a/n.bin b/n.bin', 'new file mode 100644', IDX, 'Binary files /dev/null and b/n.bin differ',
      'diff --git a/gone.bin b/gone.bin', 'deleted file mode 100644', IDX, 'Binary files a/gone.bin and /dev/null differ',
      'diff --git a/z.txt b/z.txt', IDX, '--- a/z.txt', '+++ b/z.txt', '@@ -1 +1 @@', '-z', '+Z',
    );
    const files = parseDiff(patch);
    // 新增的显示用 newPath、删除的显示用 oldPath（另一侧在没有 ---、+++ 行时是否为 null，合同没有定，不比）
    expect(files.map((f: any) => [f.status === 'deleted' ? f.oldPath : f.newPath, f.status, Boolean(f.binary), f.hunks.length, f.additions, f.deletions])).toEqual([
      ['img/logo.png', 'added', true, 0, 0, 0],
      ['after.txt', 'modified', false, 1, 1, 1],
      ['bin/data.bin', 'modified', true, 0, 0, 0],
      ['n.bin', 'added', true, 0, 0, 0],
      ['gone.bin', 'deleted', true, 0, 0, 0],
      ['z.txt', 'modified', false, 1, 1, 1],
    ]);
    expect([files[2].oldPath, files[2].newPath]).toEqual(['bin/data.bin', 'bin/data.bin']);
  });

  it('路径解码：引号路径按 C 风格还原（\\" \\\\ \\t 与三位八进制 UTF-8，坏字节变替换字符）；不带引号的路径截到第一个制表符；去掉一个 a/ 或 b/ 前缀（R3、R5）', () => {
    const patch = L(
      'diff --git "a/dir/\\344\\270\\255\\346\\226\\207.txt" "b/dir/\\344\\270\\255\\346\\226\\207.txt"', 'old mode 100644', 'new mode 100755',
      'diff --git "a/we\\"ird\\\\name.txt" "b/we\\"ird\\\\name.txt"', IDX, '--- "a/we\\"ird\\\\name.txt"', '+++ "b/we\\"ird\\\\name.txt"',
      '@@ -1 +1 @@', '-a', '+b',
      'diff --git a/with space.txt b/with space.txt', IDX, '--- a/with space.txt\t', '+++ b/with space.txt\t', '@@ -1 +1 @@', '-a', '+b',
      'diff --git "a/bad\\377.txt" "b/bad\\377.txt"', 'old mode 100644', 'new mode 100755',
      'diff --git "a/tab\\there.txt" "b/tab\\there.txt"', 'old mode 100644', 'new mode 100755',
    );
    const files = parseDiff(patch);
    expect(files.map((f: any) => [f.oldPath, f.newPath, f.status])).toEqual([
      ['dir/中文.txt', 'dir/中文.txt', 'modified'],
      ['we"ird\\name.txt', 'we"ird\\name.txt', 'modified'],
      ['with space.txt', 'with space.txt', 'modified'],
      ['bad�.txt', 'bad�.txt', 'modified'],
      ['tab\there.txt', 'tab\there.txt', 'modified'],
    ]);
  });

  it('没有 ---、+++、rename 行时路径取自 diff --git 行：a/P b/P 取 P（含空格）；两段不同时在第一个空格加 b/ 处切开，新旧路径不同算 renamed；只改权限、空文件新增照常（R4、R8）', () => {
    const patch = L(
      'diff --git a/my file.txt b/my file.txt', 'old mode 100644', 'new mode 100755',
      'diff --git a/foo b/bar',
      'diff --git a/empty.txt b/empty.txt', 'new file mode 100644', 'index 0000000..e69de29',
      'diff --git a/gone.txt b/gone.txt', 'deleted file mode 100644', 'index e69de29..0000000',
      'diff --git a/p b/p', '--- a/real.txt', '+++ b/real.txt', '@@ -1 +1 @@', '-a', '+b',
    );
    const files = parseDiff(patch);
    expect(files.length).toBe(5);
    expect(brief(files[0])).toEqual({ old: 'my file.txt', nw: 'my file.txt', status: 'modified', binary: false, hunks: 0, add: 0, del: 0 });
    expect([files[1].oldPath, files[1].newPath, files[1].status]).toEqual(['foo', 'bar', 'renamed']);
    expect([files[2].newPath, files[2].status, files[2].hunks.length]).toEqual(['empty.txt', 'added', 0]);
    expect([files[3].oldPath, files[3].status, files[3].hunks.length]).toEqual(['gone.txt', 'deleted', 0]);
    expect([files[4].oldPath, files[4].newPath]).toEqual(['real.txt', 'real.txt']);
  });

  it('第一个 diff --git 之前的行忽略；index、similarity index、old mode、new mode 等行忽略；空串与乱码返回空列表（R2、R3）', () => {
    expect(parseDiff('')).toEqual([]);
    expect(parseDiff('\n')).toEqual([]);
    expect(parseDiff('hello world\nthis is not a patch\n+++ b/x\n--- a/x\n@@ -1 +1 @@\n-a\n+b\n')).toEqual([]);
    expect(parseDiff('\u0000\u0001\u0002 �\r\r\n\n\n')).toEqual([]);
    expect(parseDiff('From: someone\nSubject: [PATCH] x\n\n' + P3).map(brief)).toEqual(parseDiff(P3).map(brief));
    const files = parseDiff(L('diff --git a/q.txt b/q.txt', 'index 1..2 100644', 'dissimilarity index 5%', '--- a/q.txt', '+++ b/q.txt', '@@ -1 +1 @@', '-a', '+b'));
    expect(files.length).toBe(1);
    expect(brief(files[0]).add).toBe(1);
  });

  it('R10 性能：1 MiB 的病态输入各在 2 秒内返回（长行、长 diff --git 行、长引号路径、片段里的长行、长 @@ 行、反斜杠行）', () => {
    timed('一条 1 MiB 长行', 'x'.repeat(MIB));
    timed('长 diff --git 行', 'diff --git a/' + 'a'.repeat(MIB) + ' b/b\n');
    timed('未闭合的长引号路径', 'diff --git "' + 'a'.repeat(MIB) + '\n');
    timed('长反斜杠引号路径', 'diff --git "' + '\\'.repeat(MIB) + '"\n');
    timed('长 a/ 重复', 'diff --git ' + 'a/a '.repeat(MIB / 4) + '\n');
    timed('长 --- 路径', 'diff --git a/x b/x\n--- a/' + 'p'.repeat(MIB) + '\n+++ b/x\n');
    timed('长 rename 行', 'diff --git a/x b/x\nrename from ' + 'r'.repeat(MIB) + '\n');
    timed('片段里的长行', 'diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-' + 'a'.repeat(MIB) + '\n+' + 'b'.repeat(MIB) + '\n');
    timed('长 @@ 行（数字）', 'diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -' + '1'.repeat(MIB) + ' +1 @@\n');
    timed('长 @@ 行（重复的 -1）', 'diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ ' + '-1 '.repeat(MIB / 3) + '\n');
    timed('1 MiB 的反斜杠行', 'diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1,2 +1,2 @@\n a\n' + '\\'.repeat(MIB) + '\n');
  });

  it('R10 性能：2 万个只有 diff --git 头的文件；很大的行数后面只有几行；成片的反斜杠行与 @@ 行（线性）', () => {
    const many = Array.from({ length: 20000 }, (_, i) => 'diff --git a/f' + i + ' b/f' + i).join('\n') + '\n';
    const files = timed('2 万个文件头', many);
    expect(files.length).toBe(20000);
    expect(files[0].newPath).toBe('f0');
    expect(files[19999].newPath).toBe('f19999');
    const big = timed('很大的行数', 'diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1,999999999 +1,999999999 @@\n a\n-b\n+c\n');
    expect(big[0].hunks[0].lines.length).toBe(3);
    timed('反复的大行数片段头', 'diff --git a/x b/x\n--- a/x\n+++ b/x\n' + '@@ -1,999999999 +1,999999999 @@\n a\n'.repeat(50000));
    timed('1 MiB 的反斜杠行（逐行）', 'diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1,3 +1,3 @@\n a\n' + '\\\n'.repeat(MIB / 2));
    timed('10 万个片段头', 'diff --git a/x b/x\n--- a/x\n+++ b/x\n' + '@@ -1 +1 @@\n'.repeat(100000));
  });
});

describe('splitPairs', () => {
  function linesFor(spec: string): any[] {
    const kinds: any = { c: ' ', d: '-', a: '+' };
    const body = spec.split('').map((ch, i) => kinds[ch] + 'x' + i);
    const oldN = spec.split('').filter((ch) => ch !== 'a').length;
    const newN = spec.split('').filter((ch) => ch !== 'd').length;
    const patch = L('diff --git a/s.txt b/s.txt', '--- a/s.txt', '+++ b/s.txt', '@@ -1,' + oldN + ' +1,' + newN + ' @@', ...body);
    const files = parseDiff(patch);
    return files[0].hunks[0].lines;
  }

  it('导出 splitPairs；返回行的列表：context 一行；一段内第 k 个删配第 k 个增，多出来的一侧为空（D03）', () => {
    expect(typeof splitPairs).toBe('function');
    const cases: Array<[string, number]> = [
      ['cddaaac', 5], ['cdc', 3], ['cac', 3], ['dac', 2], ['ad', 1], ['aad', 2], ['dd', 2], ['aa', 2], ['cc', 2],
      ['dadc', 3], ['dadadc', 4], ['cdacdaac', 6],
    ];
    for (const [spec, rows] of cases) {
      const out = splitPairs(linesFor(spec));
      expect(Array.isArray(out), spec + ' 应返回数组').toBe(true);
      expect(out.length, spec + ' 应得 ' + rows + ' 行').toBe(rows);
    }
    expect(splitPairs([])).toEqual([]);
  });

  it('不改输入的行数组', () => {
    const lines = linesFor('cddaaac');
    const before = JSON.stringify(lines);
    splitPairs(lines);
    expect(JSON.stringify(lines)).toBe(before);
    expect(lines.length).toBe(7);
  });
});
"""

# ---- view：DiffView（D02–D06） ----
PROBE_VIEW = PRELUDE + FIXTURES + r"""
let DiffView: any;

beforeAll(async () => {
  const mod: any = await import('../src/components/DiffView');
  DiffView = mod.DiffView ?? mod.default;
});

function mount(patch: string, props: any = {}) {
  const r = render(<DiffView patch={patch} {...props} />);
  const root = r.container.querySelector('.tt-diff') as HTMLElement;
  expect(root, '应有根元素 div.tt-diff').not.toBeNull();
  expect(root.tagName).toBe('DIV');
  const update = (next: string, extra: any = {}) => r.rerender(<DiffView patch={next} {...props} {...extra} />);
  return { ...r, root, update };
}
const sections = (root: HTMLElement) => Array.from(root.querySelectorAll('section.tt-diff__file')) as HTMLElement[];
const items = (root: HTMLElement) =>
  Array.from(root.querySelectorAll('ul.tt-diff__files > li > button.tt-diff__file-item')) as HTMLButtonElement[];
const headOf = (sec: HTMLElement) => sec.querySelector('.tt-diff__file-head') as HTMLElement;
const bodyOf = (sec: HTMLElement) => sec.querySelector('.tt-diff__file-body') as HTMLElement;
const foldBtn = (sec: HTMLElement) => headOf(sec).querySelector('button') as HTMLButtonElement | null;
const rowsOf = (sec: HTMLElement) => Array.from(bodyOf(sec).querySelectorAll('.tt-diff__row')) as HTMLElement[];
const noteOf = (sec: HTMLElement) => {
  const el = headOf(sec).querySelector('.tt-diff__file-note');
  return el ? textOf(el) : null;
};
const collapsedOf = (root: HTMLElement) => sections(root).map((s) => s.getAttribute('data-collapsed') === 'true');
const currentOf = (root: HTMLElement) => items(root).map((b) => b.getAttribute('aria-current') === 'true');

function unifiedRow(row: HTMLElement) {
  const kind = row.getAttribute('data-kind');
  if (kind === 'hunk') return [kind, textOf(row)];
  const nos = Array.from(row.querySelectorAll('.tt-diff__no')).map((e) => (e.textContent || '').trim());
  const sign = (row.querySelector('.tt-diff__sign')?.textContent || '').trim();
  const text = row.querySelector('.tt-diff__text')?.textContent || '';
  return [kind, nos[0], nos[1], sign, text];
}
function cellsOf(row: HTMLElement, side: string) {
  return Array.from(row.querySelectorAll('[data-side="' + side + '"]')) as HTMLElement[];
}
function sideInfo(row: HTMLElement, side: string) {
  const cs = cellsOf(row, side);
  expect(cs.length, side + ' 侧应有三格（行号、符号、文字）').toBe(3);
  const kinds = new Set(cs.map((c) => c.getAttribute('data-kind')));
  expect(kinds.size, side + ' 侧三格的 data-kind 应相同').toBe(1);
  return [cs[0].getAttribute('data-kind'), (cs[0].textContent || '').trim(), (cs[1].textContent || '').trim(), cs[2].textContent || ''];
}
function pairRow(row: HTMLElement) {
  if (row.getAttribute('data-kind') === 'hunk') return ['hunk', textOf(row)];
  expect(row.getAttribute('data-kind')).toBe('pair');
  expect(row.querySelectorAll('[data-side]').length, '分屏的行应有六格').toBe(6);
  return [...sideInfo(row, 'left'), ...sideInfo(row, 'right')];
}
function radio(root: HTMLElement, label: string) {
  const group = root.querySelector('[role="radiogroup"][aria-label="差异显示方式"]');
  expect(group, '应有 aria-label 为「差异显示方式」的分段选择').not.toBeNull();
  return buttonByText(group as HTMLElement, label);
}
function wrapSwitch(root: HTMLElement) {
  const hits = Array.from(root.querySelectorAll('[role="switch"]')).filter((e) => textOf(e) === '自动换行');
  expect(hits.length, '应有名称为「自动换行」的开关').toBe(1);
  return hits[0] as HTMLElement;
}

const MISC = L(
  'diff --git a/old/a.txt b/new/b.txt', 'similarity index 100%', 'rename from old/a.txt', 'rename to new/b.txt',
  'diff --git a/img/logo.png b/img/logo.png', 'new file mode 100644',
  'index 0000000000000000000000000000000000000000..5555555555555555555555555555555555555555',
  'GIT binary patch', 'literal 0', 'HcmV?d00001', '', 'literal 0', 'HcmV?d00001', '',
  'diff --git a/bin/data.bin b/bin/data.bin', IDX, 'Binary files a/bin/data.bin and b/bin/data.bin differ',
  'diff --git a/run.sh b/run.sh', 'old mode 100644', 'new mode 100755',
  'diff --git a/last.txt b/last.txt', IDX, '--- a/last.txt', '+++ b/last.txt', '@@ -1 +1 @@', '-a', '+b',
);
const NONL = L(
  'diff --git a/a.txt b/a.txt', IDX, '--- a/a.txt', '+++ b/a.txt', '@@ -1,2 +1,2 @@',
  ' keep', '-last', '\\ No newline at end of file', '+last2', '\\ No newline at end of file',
);
const EVIL = L(
  'diff --git a/evil<script>alert(1)</script>.txt b/evil<script>alert(1)</script>.txt', IDX,
  '--- a/evil<script>alert(1)</script>.txt', '+++ b/evil<script>alert(1)</script>.txt',
  '@@ -1,2 +1,5 @@ <img src=x onerror=alert(1)> ' + ESC + '[31mhdr' + ESC + '[0m',
  ' <script>alert(1)</script>', '+<img src=x onerror=alert(1)>', '+' + ESC + '[31mred words' + ESC + '[0m tail',
  '+see https://example.com/a?b=1&c=2 now', '+<a href="javascript:alert(1)">x</a>', '-bye',
  'diff --git a/x<img src=x onerror=alert(1)>.txt b/x<img src=x onerror=alert(1)>.txt', IDX,
  '--- a/x<img src=x onerror=alert(1)>.txt\t', '+++ b/x<img src=x onerror=alert(1)>.txt\t', '@@ -1 +1 @@', '-a', '+b',
);

describe('DiffView 结构与统一视图', () => {
  it('根 div.tt-diff、工具栏、摘要整段文字、分段选择、开关、主区带 tt-stack-narrow、文件列表（D02、D06）', () => {
    const { root } = mount(P3, { title: 'candidate.patch' });
    expect(root.getAttribute('data-mode')).toBe('unified');
    expect(root.getAttribute('data-wrap')).toBe('false');
    const bar = root.querySelector('.tt-diff__bar') as HTMLElement;
    expect(bar, '应有 div.tt-diff__bar').not.toBeNull();
    const summary = bar.querySelector('.tt-diff__summary') as HTMLElement;
    expect(textOf(summary)).toBe('candidate.patch · 3 个文件 · +6 −6');
    expect((summary.textContent || '').includes('−'), '减号是 U+2212').toBe(true);
    const icon = summary.querySelector('svg') as SVGElement;
    expect(icon.getAttribute('width')).toBe('16');
    expect(icon.getAttribute('aria-hidden')).toBe('true');
    expect(bar.contains(radio(root, '统一'))).toBe(true);
    expect(bar.contains(wrapSwitch(root))).toBe(true);
    expect(radio(root, '统一').getAttribute('aria-checked')).toBe('true');
    expect(radio(root, '分屏').getAttribute('aria-checked')).toBe('false');
    expect(wrapSwitch(root).getAttribute('aria-checked')).toBe('false');
    const main = root.querySelector('.tt-diff__main') as HTMLElement;
    expect(main, '应有 div.tt-diff__main').not.toBeNull();
    expect(main.classList.contains('tt-stack-narrow')).toBe(true);
    const list = main.querySelector('ul.tt-diff__files') as HTMLElement;
    expect(list.getAttribute('aria-label')).toBe('文件');
    expect(sections(root).length).toBe(3);
    expect(Array.from(root.children).indexOf(bar)).toBeLessThan(Array.from(root.children).indexOf(main));
    noStatusRole();
    expect(document.querySelectorAll('[role="dialog"], [role="menu"], [aria-modal]').length).toBe(0);
  });

  it('没有 title 时摘要去掉第一段；defaultMode、defaultWrap、className 生效', () => {
    const a = mount(P3);
    expect(textOf(a.root.querySelector('.tt-diff__summary'))).toBe('3 个文件 · +6 −6');
    a.unmount();
    const b = mount(P3, { defaultMode: 'split', defaultWrap: true, className: 'extra-x' });
    expect(b.root.getAttribute('data-mode')).toBe('split');
    expect(b.root.getAttribute('data-wrap')).toBe('true');
    expect(b.root.classList.contains('extra-x')).toBe(true);
    expect(b.root.classList.contains('tt-diff')).toBe(true);
    expect(radio(b.root, '分屏').getAttribute('aria-checked')).toBe('true');
    expect(wrapSwitch(b.root).getAttribute('aria-checked')).toBe('true');
  });

  it('统一视图：行的顺序与 data-kind、两列行号按 kind 有无、加号与 −（U+2212）、片段头整行文字（D02）', () => {
    const { root } = mount(P3);
    const secs = sections(root);
    expect(rowsOf(secs[0]).map(unifiedRow)).toEqual([
      ['hunk', '@@ -1,4 +1,5 @@ function main()'],
      ['context', '1', '1', '', 'ctx1'],
      ['del', '2', '', '−', 'old1'],
      ['del', '3', '', '−', 'old2'],
      ['add', '', '2', '+', 'new1'],
      ['add', '', '3', '+', 'new2'],
      ['add', '', '4', '+', 'new3'],
      ['context', '4', '5', '', 'ctx2'],
      ['hunk', '@@ -20,3 +21,2 @@'],
      ['context', '20', '21', '', 'ctx3'],
      ['del', '21', '', '−', 'gone'],
      ['context', '22', '22', '', 'ctx4'],
    ]);
    const nums = Array.from(secs[0].querySelectorAll('.tt-diff__row:not([data-kind="hunk"]) .tt-diff__no')) as HTMLElement[];
    expect(nums.length, '十个内容行，每行两格行号').toBe(20);
    for (const n of nums) {
      expect(n.getAttribute('aria-hidden')).toBe('true');
      expect(n.classList.contains('tt-num')).toBe(true);
    }
    for (const s of Array.from(secs[0].querySelectorAll('.tt-diff__sign'))) {
      expect(s.hasAttribute('aria-hidden'), '符号格不设 aria-hidden，读屏要能读到增删').toBe(false);
    }
  });

  it('统一视图：新文件展开后只有加行，删除的文件只有删行，--- 开头的内容行的文字保留两个减号（D02）', () => {
    const { root } = mount(P3);
    const secs = sections(root);
    fireEvent.click(foldBtn(secs[1]) as HTMLElement);
    expect(rowsOf(sections(root)[1]).map(unifiedRow)).toEqual([
      ['hunk', '@@ -0,0 +1,3 @@'],
      ['add', '', '1', '+', 'line1'],
      ['add', '', '2', '+', '++ not a header'],
      ['add', '', '3', '+', 'line3'],
    ]);
    expect(rowsOf(secs[2]).map(unifiedRow)).toEqual([
      ['hunk', '@@ -1,3 +0,0 @@'],
      ['del', '1', '', '−', 'r1'],
      ['del', '2', '', '−', '-- r2 looks like a header'],
      ['del', '3', '', '−', 'r3'],
    ]);
  });

  it('文件头的路径、注记、计数；section 的 data-status、data-binary、data-collapsed（D02、D04）', () => {
    const { root } = mount(P3);
    const secs = sections(root);
    expect(secs.map((s) => s.getAttribute('data-status'))).toEqual(['modified', 'added', 'deleted']);
    expect(secs.map((s) => s.getAttribute('data-binary') === 'true')).toEqual([false, false, false]);
    expect(collapsedOf(root)).toEqual([false, true, false]);
    expect(secs.map((s) => squash(textOf(headOf(s))))).toEqual(['src/app.ts+3−3', 'docs/新文件.md新文件·已折叠+3−0', 'old/removed.txt已删除+0−3']);
    expect(secs.map(noteOf)).toEqual([null, '新文件 · 已折叠', '已删除']);
    expect(secs.map((s) => textOf(headOf(s).querySelector('.tt-diff__file-name')))).toEqual(['src/app.ts', 'docs/新文件.md', 'old/removed.txt']);
    expect(secs.map((s) => headOf(s).querySelector('.tt-diff__file-name')!.getAttribute('title'))).toEqual(['src/app.ts', 'docs/新文件.md', 'old/removed.txt']);
    const counts = secs.map((s) => Array.from(headOf(s).querySelectorAll('.tt-num')).map((e) => textOf(e)));
    expect(counts).toEqual([['+3', '−3'], ['+3', '−0'], ['+0', '−3']]);
    expect(headOf(secs[0]).getAttribute('tabindex')).toBe('-1');
  });

  it('文件列表：计数、title、两层 span、type=button、缺省第一个是当前（D04）', () => {
    const { root } = mount(P3);
    const its = items(root);
    expect(its.length).toBe(3);
    expect(its.map((b) => b.getAttribute('type'))).toEqual(['button', 'button', 'button']);
    expect(its.map((b) => b.getAttribute('aria-current'))).toEqual(['true', null, null]);
    const paths = its.map((b) => b.querySelector('.tt-diff__file-path') as HTMLElement);
    expect(paths.map((p) => p.getAttribute('title'))).toEqual(['src/app.ts', 'docs/新文件.md', 'old/removed.txt']);
    for (const p of paths) {
      const inner = p.querySelector(':scope > span') as HTMLElement;
      expect(inner, '路径 span 里再套一层 span 放显示路径').not.toBeNull();
      expect(textOf(inner)).toBe(p.getAttribute('title'));
    }
    expect(its.map((b) => Array.from(b.querySelectorAll('.tt-num')).map((e) => textOf(e)))).toEqual([['+3', '−3'], ['+3', '−0'], ['+0', '−3']]);
  });
});

describe('DiffView 折叠、当前文件与补丁变化', () => {
  it('新文件缺省折叠：aria-expanded=false、主体 hidden 且没有行、注记「新文件 · 已折叠」；点开后有行、注记「新文件」；再点收回（D04）', () => {
    const { root } = mount(P3);
    const sec = sections(root)[1];
    const btn = foldBtn(sec) as HTMLButtonElement;
    expect(btn.getAttribute('aria-expanded')).toBe('false');
    const labelBefore = btn.getAttribute('aria-label') || '';
    expect(['折叠', '展开'], '折叠钮的 label 是「折叠」或「展开」').toContain(labelBefore);
    expect(bodyOf(sec), '折叠时主体元素仍在').not.toBeNull();
    expect(bodyOf(sec).hasAttribute('hidden')).toBe(true);
    expect(rowsOf(sec).length).toBe(0);
    expect(btn.getAttribute('aria-controls')).toBe(bodyOf(sec).id);
    expect(bodyOf(sec).id).not.toBe('');
    fireEvent.click(btn);
    const open = sections(root)[1];
    expect(foldBtn(open)!.getAttribute('aria-expanded')).toBe('true');
    const labelAfter = foldBtn(open)!.getAttribute('aria-label') || '';
    expect(['折叠', '展开']).toContain(labelAfter);
    expect(labelAfter, '展开之后折叠钮的 label 换成另一个').not.toBe(labelBefore);
    expect(bodyOf(open).hasAttribute('hidden')).toBe(false);
    expect(rowsOf(open).length).toBeGreaterThan(0);
    expect(noteOf(open)).toBe('新文件');
    expect(open.getAttribute('data-collapsed')).not.toBe('true');
    fireEvent.click(foldBtn(open) as HTMLElement);
    const shut = sections(root)[1];
    expect(foldBtn(shut)!.getAttribute('aria-expanded')).toBe('false');
    expect(bodyOf(shut).hasAttribute('hidden')).toBe(true);
    expect(rowsOf(shut).length).toBe(0);
    expect(noteOf(shut)).toBe('新文件 · 已折叠');
  });

  it('其他文本文件缺省展开；折叠钮 aria-controls 指向存在的主体，aria-labelledby 含自己的 id 与路径 span 的 id，id 在多个视图里不重复（D04）', () => {
    const a = mount(P3);
    const b = mount(P3);
    const ids: string[] = [];
    for (const root of [a.root, b.root]) {
      for (const sec of sections(root)) {
        const btn = foldBtn(sec) as HTMLButtonElement;
        expect(btn, '文本文件应有折叠钮').not.toBeNull();
        const body = bodyOf(sec);
        expect(document.getElementById(btn.getAttribute('aria-controls') || '')).toBe(body);
        const tokens = (btn.getAttribute('aria-labelledby') || '').split(/\s+/).filter(Boolean);
        const name = headOf(sec).querySelector('.tt-diff__file-name') as HTMLElement;
        expect(tokens).toEqual([btn.id, name.id]);
        expect(btn.id).not.toBe('');
        expect(name.id).not.toBe('');
        ids.push(btn.id, name.id, body.id);
      }
      const expanded = sections(root).map((s) => foldBtn(s)!.getAttribute('aria-expanded'));
      expect(expanded).toEqual(['true', 'false', 'true']);
    }
    expect(new Set(ids).size, '两个视图里的 id 不能重复').toBe(ids.length);
  });

  it('点列表项：设为当前、折叠着就展开、焦点移到这个文件的头；点已展开的文件也设为当前并移焦点（D04）', async () => {
    const { root } = mount(P3);
    fireEvent.click(items(root)[1]);
    expect(currentOf(root)).toEqual([false, true, false]);
    expect(items(root)[1].getAttribute('aria-current')).toBe('true');
    expect(items(root)[0].hasAttribute('aria-current')).toBe(false);
    let sec = sections(root)[1];
    expect(foldBtn(sec)!.getAttribute('aria-expanded')).toBe('true');
    expect(rowsOf(sec).length).toBeGreaterThan(0);
    expect(noteOf(sec)).toBe('新文件');
    await settle(() => document.activeElement === headOf(sections(root)[1]), '焦点到这个文件的头');
    fireEvent.click(items(root)[2]);
    expect(currentOf(root)).toEqual([false, false, true]);
    await settle(() => document.activeElement === headOf(sections(root)[2]), '焦点到第三个文件的头');
    sec = sections(root)[2];
    expect(foldBtn(sec)!.getAttribute('aria-expanded')).toBe('true');
  });

  it('patch 变化：折叠状态按序号加显示路径记（两样都没变的保持，其余按缺省）；当前文件序号越界回到第一个，没越界就保持', () => {
    const m = mount(P3);
    fireEvent.click(foldBtn(sections(m.root)[0]) as HTMLElement);
    fireEvent.click(foldBtn(sections(m.root)[1]) as HTMLElement);
    expect(collapsedOf(m.root)).toEqual([true, false, false]);
    m.update(P3.replace('ctx1', 'ctx1 changed'));
    expect(collapsedOf(m.root)).toEqual([true, false, false]);
    m.update(L(...DEL_FILE, ...NEW_FILE, ...MOD_FILE));
    expect(sections(m.root).map((s) => s.getAttribute('data-status'))).toEqual(['deleted', 'added', 'modified']);
    expect(collapsedOf(m.root), '序号 1 与路径都没变的保持展开；序号 0、2 的路径变了，回到缺省（展开）').toEqual([false, false, false]);

    const n = mount(P3);
    fireEvent.click(items(n.root)[2]);
    expect(currentOf(n.root)).toEqual([false, false, true]);
    n.update(L(...MOD_FILE, ...NEW_FILE));
    expect(currentOf(n.root), '序号越界回到第一个').toEqual([true, false]);
    n.update(P3);
    expect(currentOf(n.root)).toEqual([true, false, false]);
    fireEvent.click(items(n.root)[1]);
    n.update(L(...NEW_FILE, ...MOD_FILE, ...DEL_FILE));
    expect(currentOf(n.root), '序号没越界就保持，哪怕路径变了').toEqual([false, true, false]);
  });

  it('改名无片段、二进制（两种写法）、只改权限、普通文件混在一起：说明文字、折叠钮、注记、列表项（D04）', () => {
    const { root } = mount(MISC, { title: 'misc.patch' });
    expect(textOf(root.querySelector('.tt-diff__summary'))).toBe('misc.patch · 5 个文件 · +1 −1');
    const secs = sections(root);
    expect(secs.map((s) => s.getAttribute('data-status'))).toEqual(['renamed', 'added', 'modified', 'modified', 'modified']);
    expect(secs.map((s) => s.getAttribute('data-binary') === 'true')).toEqual([false, true, true, false, false]);
    // 改名：文件头写「旧 → 新」，没有片段，说明「没有内容改动」，有折叠钮、缺省展开
    expect(squash(textOf(headOf(secs[0])))).toBe('old/a.txt→new/b.txt+0−0');
    expect(textOf(bodyOf(secs[0]))).toBe('没有内容改动');
    expect(foldBtn(secs[0])!.getAttribute('aria-expanded')).toBe('true');
    expect(items(root)[0].querySelector('.tt-diff__file-path')!.getAttribute('title')).toBe('new/b.txt');
    // 二进制：没有折叠钮、有说明文字、列表项写「二进制」没有计数
    for (const i of [1, 2]) {
      expect(foldBtn(secs[i]), '二进制没有折叠钮').toBeNull();
      expect(textOf(bodyOf(secs[i]))).toBe('二进制文件，不显示内容');
      expect(bodyOf(secs[i]).hasAttribute('hidden')).toBe(false);
      expect(rowsOf(secs[i]).length).toBe(0);
      expect(secs[i].getAttribute('data-collapsed')).not.toBe('true');
      expect(textOf(items(root)[i])).toContain('二进制');
      expect(items(root)[i].querySelectorAll('.tt-num').length).toBe(0);
      expect(headOf(secs[i]).querySelectorAll('.tt-num').length).toBe(0);
    }
    expect(squash(textOf(headOf(secs[1])))).toBe('img/logo.png新文件');
    expect(squash(textOf(headOf(secs[2])))).toBe('bin/data.bin');
    expect(items(root)[1].querySelector('.tt-diff__file-path')!.getAttribute('title')).toBe('img/logo.png');
    // 只改权限：文本文件、没有片段
    expect(textOf(bodyOf(secs[3]))).toBe('没有内容改动');
    expect(squash(textOf(headOf(secs[3])))).toBe('run.sh+0−0');
    expect(rowsOf(secs[4]).map(unifiedRow)).toEqual([
      ['hunk', '@@ -1 +1 @@'], ['del', '1', '', '−', 'a'], ['add', '', '1', '+', 'b'],
    ]);
  });

  it('没读完：truncated 时根末尾有 div.tt-diff__foot 与说明，最后一个文件的注记加「未读完」；[继续加载]（secondary、sm）调 onLoadMore；loadingMore 时转圈（D02）', () => {
    const onLoadMore = vi.fn();
    const none = mount(P3, { truncated: true });
    const foot = none.root.lastElementChild as HTMLElement;
    expect(foot.classList.contains('tt-diff__foot')).toBe(true);
    expect(textOf(foot)).toBe('补丁没有读完，只显示了已读到的部分');
    expect(buttonsByText(none.root, '继续加载').length, '没给 onLoadMore 就没有按钮').toBe(0);
    expect(sections(none.root).map(noteOf)).toEqual([null, '新文件 · 已折叠', '已删除 · 未读完']);
    none.unmount();

    const m = mount(P3, { truncated: true, onLoadMore });
    const btn = buttonByText(m.root, '继续加载');
    expect(btn.getAttribute('data-variant')).toBe('secondary');
    expect(btn.getAttribute('data-size')).toBe('sm');
    expect((m.root.lastElementChild as HTMLElement).contains(btn)).toBe(true);
    fireEvent.click(btn);
    expect(onLoadMore).toHaveBeenCalledTimes(1);
    m.update(P3, { truncated: true, onLoadMore, loadingMore: true });
    const busy = buttonByText(m.root, '正在加载…');
    expect(busy.disabled).toBe(true);
    expect(busy.getAttribute('aria-busy')).toBe('true');
    fireEvent.click(busy);
    expect(onLoadMore).toHaveBeenCalledTimes(1);
    m.unmount();

    const full = mount(P3);
    expect(full.root.querySelector('.tt-diff__foot')).toBeNull();
    expect(sections(full.root).map(noteOf)).toEqual([null, '新文件 · 已折叠', '已删除']);
  });

  it('没有文件时只有工具栏与「补丁里没有改动」，不渲染列表；不带 diff --git 的普通 unified diff 与乱码同样处理（D02）', () => {
    const plain = '--- a/x.txt\n+++ b/x.txt\n@@ -1 +1 @@\n-a\n+b\n';
    for (const patch of ['', plain, 'hello\nworld\n']) {
      const { root, unmount } = mount(patch);
      expect(root.querySelector('.tt-diff__bar')).not.toBeNull();
      expect(textOf(root.querySelector('.tt-diff__empty'))).toBe('补丁里没有改动');
      expect(root.querySelector('ul.tt-diff__files')).toBeNull();
      expect(sections(root).length).toBe(0);
      expect(root.querySelectorAll('[role="radiogroup"]').length).toBe(1);
      unmount();
    }
  });
});

describe('DiffView 分屏、换行与 eof', () => {
  it('切到分屏、切换行：只改 data-mode、data-wrap 与行的结构，折叠与当前文件不变（D06）', () => {
    const { root } = mount(P3);
    fireEvent.click(foldBtn(sections(root)[0]) as HTMLElement);
    fireEvent.click(items(root)[2]);
    const collapsed = collapsedOf(root);
    const current = currentOf(root);
    expect(collapsed).toEqual([true, true, false]);
    fireEvent.click(radio(root, '分屏'));
    expect(root.getAttribute('data-mode')).toBe('split');
    expect(root.getAttribute('data-wrap')).toBe('false');
    expect(radio(root, '分屏').getAttribute('aria-checked')).toBe('true');
    expect(collapsedOf(root)).toEqual(collapsed);
    expect(currentOf(root)).toEqual(current);
    fireEvent.click(wrapSwitch(root));
    expect(root.getAttribute('data-wrap')).toBe('true');
    expect(root.getAttribute('data-mode')).toBe('split');
    expect(wrapSwitch(root).getAttribute('aria-checked')).toBe('true');
    expect(collapsedOf(root)).toEqual(collapsed);
    expect(currentOf(root)).toEqual(current);
    fireEvent.click(radio(root, '统一'));
    expect(root.getAttribute('data-mode')).toBe('unified');
    fireEvent.click(wrapSwitch(root));
    expect(root.getAttribute('data-wrap')).toBe('false');
    expect(collapsedOf(root)).toEqual(collapsed);
    expect(currentOf(root)).toEqual(current);
  });

  it('分屏：片段头一格占满；两删三加得三行、第三行左侧 empty；左侧 del、context、empty，右侧 add、context、empty；两侧行号与符号（D03）', () => {
    const { root } = mount(P3, { defaultMode: 'split' });
    const secs = sections(root);
    const rows = rowsOf(secs[0]);
    expect(rows.map((r) => r.getAttribute('data-kind'))).toEqual(['hunk', 'pair', 'pair', 'pair', 'pair', 'pair', 'hunk', 'pair', 'pair', 'pair']);
    expect(rows.map(pairRow)).toEqual([
      ['hunk', '@@ -1,4 +1,5 @@ function main()'],
      ['context', '1', '', 'ctx1', 'context', '1', '', 'ctx1'],
      ['del', '2', '−', 'old1', 'add', '2', '+', 'new1'],
      ['del', '3', '−', 'old2', 'add', '3', '+', 'new2'],
      ['empty', '', '', '', 'add', '4', '+', 'new3'],
      ['context', '4', '', 'ctx2', 'context', '5', '', 'ctx2'],
      ['hunk', '@@ -20,3 +21,2 @@'],
      ['context', '20', '', 'ctx3', 'context', '21', '', 'ctx3'],
      ['del', '21', '−', 'gone', 'empty', '', '', ''],
      ['context', '22', '', 'ctx4', 'context', '22', '', 'ctx4'],
    ]);
    for (const hunk of rows.filter((r) => r.getAttribute('data-kind') === 'hunk')) {
      expect(hunk.querySelectorAll('[data-side]').length, '片段头一格占满，没有左右格').toBe(0);
      expect(hunk.children.length).toBeLessThanOrEqual(1);
    }
    for (const s of Array.from(secs[0].querySelectorAll('.tt-diff__sign'))) {
      expect(s.hasAttribute('aria-hidden')).toBe(false);
    }
    for (const n of Array.from(secs[0].querySelectorAll('.tt-diff__no'))) {
      expect(n.getAttribute('aria-hidden')).toBe('true');
    }
  });

  it('分屏：只有增的片段（新文件）与只有删的片段（删除的文件）各配对成一侧为空的行（D03）', () => {
    const { root } = mount(P3, { defaultMode: 'split' });
    fireEvent.click(foldBtn(sections(root)[1]) as HTMLElement);
    const secs = sections(root);
    expect(rowsOf(secs[1]).map(pairRow)).toEqual([
      ['hunk', '@@ -0,0 +1,3 @@'],
      ['empty', '', '', '', 'add', '1', '+', 'line1'],
      ['empty', '', '', '', 'add', '2', '+', '++ not a header'],
      ['empty', '', '', '', 'add', '3', '+', 'line3'],
    ]);
    expect(rowsOf(secs[2]).map(pairRow)).toEqual([
      ['hunk', '@@ -1,3 +0,0 @@'],
      ['del', '1', '−', 'r1', 'empty', '', '', ''],
      ['del', '2', '−', '-- r2 looks like a header', 'empty', '', '', ''],
      ['del', '3', '−', 'r3', 'empty', '', '', ''],
    ]);
  });

  it('No newline 标记：行文字后有 span.tt-diff__eof「（文件末尾没有换行）」，补丁原文里的反斜杠标记行不出现在 DOM 里（统一与分屏）', () => {
    const { root } = mount(NONL);
    const secs = sections(root);
    const rows = rowsOf(secs[0]);
    expect(rows.map((r) => r.getAttribute('data-kind'))).toEqual(['hunk', 'context', 'del', 'add']);
    expect(rows.map((r) => r.querySelectorAll('.tt-diff__eof').length)).toEqual([0, 0, 1, 1]);
    for (const r of rows.slice(2)) {
      expect(textOf(r.querySelector('.tt-diff__eof'))).toBe('（文件末尾没有换行）');
    }
    expect(squash(rows[2].textContent)).toContain('last（文件末尾没有换行）');
    expect(squash(rows[3].textContent)).toContain('last2（文件末尾没有换行）');
    expect(root.textContent || '').not.toMatch(/No newline/);
    expect(root.textContent || '').not.toContain('\\');
    fireEvent.click(radio(root, '分屏'));
    const pairs = rowsOf(sections(root)[0]);
    expect(pairs.map((r) => r.getAttribute('data-kind'))).toEqual(['hunk', 'pair', 'pair']);
    expect(pairs[2].querySelectorAll('.tt-diff__eof').length, '左右两侧的文字后各有一个 eof 注记').toBe(2);
    expect(squash(cellsOf(pairs[2], 'left').map((c) => c.textContent).join(''))).toContain('last');
    expect(squash(pairs[2].textContent)).toContain('last（文件末尾没有换行）');
    expect(squash(pairs[2].textContent)).toContain('last2（文件末尾没有换行）');
    expect(pairs[1].querySelectorAll('.tt-diff__eof').length).toBe(0);
    expect(root.textContent || '').not.toMatch(/No newline/);
  });

  it('超长行（2500 字符）完整显示，不截断', () => {
    const long = 'x'.repeat(2500);
    const patch = L('diff --git a/l.txt b/l.txt', IDX, '--- a/l.txt', '+++ b/l.txt', '@@ -1 +1 @@', '-' + long, '+' + long + 'y');
    const { root } = mount(patch);
    const texts = Array.from(root.querySelectorAll('.tt-diff__row:not([data-kind="hunk"]) .tt-diff__text')).map((e) => e.textContent || '');
    expect(texts).toEqual([long, long + 'y']);
  });
});

describe('DiffView 只按文本显示（W1、D05）', () => {
  it('行、片段头、路径里的 <script>、<img onerror>、ANSI、网址都只是文字：没有 script、img、a 元素；ESC 与 [31m 不出现；路径除文字外只出现在 title', () => {
    const { root } = mount(EVIL, { title: 'evil.patch' });
    expect(root.querySelectorAll('script, img, a, iframe, object, embed, style, link, form, input[type="image"]').length).toBe(0);
    expect(document.body.querySelectorAll('script, img, a[href]').length).toBe(0);
    expect(root.querySelectorAll('[onerror], [href], [src], [srcdoc]').length).toBe(0);
    const text = root.textContent || '';
    expect(text).toContain('<script>alert(1)</script>');
    expect(text).toContain('<img src=x onerror=alert(1)>');
    expect(text).toContain('red words tail');
    expect(text).toContain('see https://example.com/a?b=1&c=2 now');
    expect(text).toContain('<a href="javascript:alert(1)">x</a>');
    expect(text).toContain('@@ -1,2 +1,5 @@ <img src=x onerror=alert(1)> hdr');
    expect(text.includes(ESC)).toBe(false);
    expect(text.includes('[31m')).toBe(false);
    expect(text.includes('[0m')).toBe(false);
    const names = Array.from(root.querySelectorAll('.tt-diff__file-name')).map((e) => e.textContent);
    expect(names).toEqual(['evil<script>alert(1)</script>.txt', 'x<img src=x onerror=alert(1)>.txt']);
    const all = [root, ...Array.from(root.querySelectorAll('*'))] as Element[];
    for (const el of all) {
      for (const attr of Array.from(el.attributes)) {
        expect(attr.name.startsWith('on'), '不能有事件属性 ' + attr.name).toBe(false);
        if (attr.name === 'title') {
          expect(attr.value.includes(ESC)).toBe(false);
          continue;
        }
        expect(attr.value, '属性 ' + attr.name + ' 里不该出现证据文字').not.toMatch(/script|onerror|alert|example\.com|red words|[<>]/i);
      }
    }
    expect(root.querySelector('.tt-diff__summary')!.textContent).toContain('evil.patch');
  });

  it('展开后统一与分屏两种视图的行都只是文字', () => {
    const { root } = mount(EVIL, { defaultMode: 'split' });
    expect(root.querySelectorAll('script, img, a').length).toBe(0);
    expect(root.textContent || '').toContain('<img src=x onerror=alert(1)>');
    expect((root.textContent || '').includes(ESC)).toBe(false);
    fireEvent.click(radio(root, '统一'));
    expect(root.querySelectorAll('script, img, a').length).toBe(0);
    expect((root.textContent || '').includes(ESC)).toBe(false);
    noStatusRole();
  });
});
"""

# ---- follow：LogFollow 的结构与跟随状态机（D07；假计时器，主体打桩） ----
PROBE_FOLLOW = PRELUDE + r"""
let LogFollow: any;

beforeAll(async () => {
  const mod: any = await import('../src/components/LogFollow');
  LogFollow = mod.LogFollow ?? mod.default;
});

// jsdom 不排版：在 HTMLElement.prototype 上按类名给主体打桩 scrollHeight、clientHeight，scrollTop 夹在 0 与 scrollHeight − clientHeight 之间（像浏览器）。
const BODY_CLASS = 'tt-viewer__body';
let SH = 1000;
let CH = 200;
const TOPS = new WeakMap<object, number>();
function maxTop() {
  return Math.max(0, SH - CH);
}
function installScrollStubs() {
  const proto: any = HTMLElement.prototype;
  Object.defineProperty(proto, 'scrollHeight', {
    configurable: true,
    get() {
      return (this as HTMLElement).classList.contains(BODY_CLASS) ? SH : 0;
    },
  });
  Object.defineProperty(proto, 'clientHeight', {
    configurable: true,
    get() {
      return (this as HTMLElement).classList.contains(BODY_CLASS) ? CH : 0;
    },
  });
  Object.defineProperty(proto, 'scrollTop', {
    configurable: true,
    get() {
      return TOPS.get(this) ?? 0;
    },
    set(v: number) {
      const cap = (this as HTMLElement).classList.contains(BODY_CLASS) ? maxTop() : Infinity;
      TOPS.set(this, Math.max(0, Math.min(Number(v), cap)));
    },
  });
}
function removeScrollStubs() {
  const proto: any = HTMLElement.prototype;
  delete proto.scrollHeight;
  delete proto.clientHeight;
  delete proto.scrollTop;
}
beforeEach(() => {
  SH = 1000;
  CH = 200;
  installScrollStubs();
  vi.useFakeTimers();
});
afterEach(() => {
  removeScrollStubs();
});

function pagesOf(n: number) {
  return Array.from({ length: n }, (_, i) => ({ mode: 'text', text: 'event ' + (i + 1) + '\n' }));
}
function mountLog(props: any = {}) {
  const spies = { onCopy: vi.fn(), onLoadMore: vi.fn(), onReload: vi.fn() };
  let cur: any = { title: 'events.jsonl', pages: pagesOf(1), hasMore: false, ...props };
  const el = () => <LogFollow onCopy={spies.onCopy} onLoadMore={spies.onLoadMore} onReload={spies.onReload} {...cur} />;
  const r = render(el());
  const root = r.container.querySelector('.tt-log') as HTMLElement;
  expect(root, '应有根元素 .tt-log').not.toBeNull();
  return {
    ...r,
    root,
    ...spies,
    update: (patch: any) => {
      cur = { ...cur, ...patch };
      r.rerender(el());
    },
    body: () => root.querySelector('.tt-viewer__body') as HTMLElement,
    status: () => root.querySelector('.tt-log__status') as HTMLElement,
    sw: () => root.querySelector('.tt-log__follow [role="switch"]') as HTMLElement,
    input: () => root.querySelector('.tt-log__filter-input') as HTMLInputElement,
    state: () => (root.querySelector('.tt-log__status') as HTMLElement | null)?.getAttribute('data-follow'),
  };
}
function userScroll(el: HTMLElement, top: number) {
  el.scrollTop = top;
  fireEvent.scroll(el);
}
const REASON = 'attempt 已结束，没有新事件';

describe('LogFollow 结构', () => {
  it('根带 tt-log 与 tt-viewer；主体带 tt-log__body；过滤框与跟随开关在头部复制钮之后；底部状态在主体与底栏之间；不设 role、aria-live', () => {
    const m = mountLog({ className: 'extra-y' });
    expect(m.root.classList.contains('tt-viewer')).toBe(true);
    expect(m.root.classList.contains('extra-y')).toBe(true);
    expect(m.root.className.indexOf('tt-log')).toBeLessThan(m.root.className.indexOf('extra-y'));
    const body = m.body();
    expect(body.classList.contains('tt-log__body')).toBe(true);
    expect(body.classList.contains('tt-viewer__body')).toBe(true);
    expect(textOf(m.root.querySelector('.tt-viewer__title'))).toBe('events.jsonl');
    const filter = m.root.querySelector('label.tt-log__filter') as HTMLElement;
    expect(filter, '应有 label.tt-log__filter').not.toBeNull();
    const icon = filter.querySelector('svg') as SVGElement;
    expect(icon.getAttribute('width')).toBe('14');
    expect(icon.getAttribute('aria-hidden')).toBe('true');
    const input = filter.querySelector('input.tt-log__filter-input') as HTMLInputElement;
    expect(input.getAttribute('type')).toBe('text');
    expect(input.getAttribute('aria-label')).toBe('过滤事件');
    expect(input.getAttribute('placeholder')).toBe('按文字包含过滤…');
    expect(input.value).toBe('');
    const follow = m.root.querySelector('span.tt-log__follow') as HTMLElement;
    expect(follow, '应有 span.tt-log__follow').not.toBeNull();
    expect(textOf(m.sw())).toBe('跟随');
    expect(follow.hasAttribute('title')).toBe(false);
    const head = m.root.querySelector('.tt-viewer__head') as HTMLElement;
    expect(head.contains(filter)).toBe(true);
    expect(head.contains(follow)).toBe(true);
    const copy = head.querySelector('button[aria-label="复制已显示的文字"]') as HTMLElement;
    expect(copy.compareDocumentPosition(filter) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const status = m.status();
    const foot = m.root.querySelector('.tt-viewer__foot') as HTMLElement;
    expect(body.contains(status)).toBe(false);
    expect(body.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(status.compareDocumentPosition(foot) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(status.hasAttribute('role')).toBe(false);
    expect(m.root.querySelectorAll('[aria-live]').length).toBe(0);
    noStatusRole();
  });

  it('TextViewer 的其余属性照常透传：复制交出显示的文字、[继续加载]、已显示 N 页', () => {
    const m = mountLog({ pages: pagesOf(2), hasMore: true });
    fireEvent.click(m.root.querySelector('button[aria-label="复制已显示的文字"]') as HTMLElement);
    expect(m.onCopy).toHaveBeenCalledWith('event 1\nevent 2');
    expect(textOf(m.root.querySelector('.tt-viewer__foot'))).toContain('已显示 2 页');
    fireEvent.click(buttonByText(m.root.querySelector('.tt-viewer__foot') as HTMLElement, '继续加载'));
    expect(m.onLoadMore).toHaveBeenCalledTimes(1);
  });

  it('四种状态的文字与 data-follow：following、paused（暂停图标 16、回到底部钮 secondary sm）、off、disabled（原因文字）', () => {
    const m = mountLog();
    expect(m.state()).toBe('following');
    expect(squash(textOf(m.status()))).toBe('正在跟随最新内容');
    expect(m.sw().getAttribute('aria-checked')).toBe('true');
    userScroll(m.body(), 500);
    expect(m.state()).toBe('paused');
    expect(squash(textOf(m.status()))).toBe('已暂停跟随：你在往上看回到底部');
    const icon = m.status().querySelector('svg') as SVGElement;
    expect(icon.getAttribute('width')).toBe('16');
    expect(icon.getAttribute('aria-hidden')).toBe('true');
    const back = buttonByText(m.status(), '回到底部');
    expect(back.getAttribute('data-variant')).toBe('secondary');
    expect(back.getAttribute('data-size')).toBe('sm');
    expect(m.sw().getAttribute('aria-checked')).toBe('true');
    fireEvent.click(m.sw());
    expect(m.state()).toBe('off');
    expect(squash(textOf(m.status()))).toBe('已关闭跟随');
    expect(m.sw().getAttribute('aria-checked')).toBe('false');
    expect(buttonsByText(m.status(), '回到底部').length).toBe(0);
    m.update({ followDisabledReason: REASON });
    expect(m.state()).toBe('disabled');
    expect(textOf(m.status())).toBe(REASON);
    for (const s of [m.status()]) {
      expect(s.hasAttribute('role')).toBe(false);
      expect(s.hasAttribute('aria-live')).toBe(false);
    }
  });
});

describe('LogFollow 跟随状态机', () => {
  it('挂载后在 following，滚到底；following 中追加页后滚到底（useLayoutEffect，同步）', () => {
    const m = mountLog();
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(800);
    SH = 1500;
    m.update({ pages: pagesOf(2) });
    expect(m.body().scrollTop).toBe(1300);
    SH = 2200;
    m.update({ pages: pagesOf(3) });
    expect(m.body().scrollTop).toBe(2000);
    expect(m.state()).toBe('following');
  });

  it('往上滚且离底超过 40 暂停，并开始计时；暂停中追加页不滚动', () => {
    const m = mountLog();
    const base = vi.getTimerCount();
    userScroll(m.body(), 500);
    expect(m.state()).toBe('paused');
    expect(vi.getTimerCount(), '暂停时开始 150ms 计时').toBeGreaterThan(base);
    SH = 1500;
    m.update({ pages: pagesOf(2) });
    expect(m.body().scrollTop).toBe(500);
    expect(m.state()).toBe('paused');
  });

  it('往上滚但离底不超过 40 不暂停（d=30、d=40），d=41 才暂停；没暂停时追加页仍滚到底', () => {
    const a = mountLog();
    userScroll(a.body(), 770);
    expect(a.state()).toBe('following');
    userScroll(a.body(), 760);
    expect(a.state(), 'd=40 不暂停').toBe('following');
    userScroll(a.body(), 759);
    expect(a.state(), 'd=41 暂停').toBe('paused');
    a.unmount();
    const b = mountLog();
    userScroll(b.body(), 770);
    SH = 1500;
    b.update({ pages: pagesOf(2) });
    expect(b.state()).toBe('following');
    expect(b.body().scrollTop).toBe(1300);
  });

  it('scrollTop 没变小（内容变长）时即使离底超过 40 也不暂停；程序滚到底之后的滚动事件到来时内容又变长，同样不暂停', () => {
    const a = mountLog();
    SH = 2000;
    fireEvent.scroll(a.body());
    expect(a.state()).toBe('following');
    a.unmount();
    const b = mountLog();
    SH = 1500;
    b.update({ pages: pagesOf(2) });
    expect(b.body().scrollTop).toBe(1300);
    SH = 2500;
    fireEvent.scroll(b.body());
    expect(b.state(), '记下的是程序滚动之后实际读回的 scrollTop（1300），不是 scrollHeight').toBe('following');
  });

  it('d 为 40 时 149ms 仍 paused、150ms 恢复 following 并滚到底；d 为 41 时过了 150ms 仍 paused', () => {
    const a = mountLog();
    userScroll(a.body(), 500);
    userScroll(a.body(), 760);
    expect(a.state()).toBe('paused');
    advance(149);
    expect(a.state()).toBe('paused');
    expect(a.body().scrollTop).toBe(760);
    advance(1);
    expect(a.state()).toBe('following');
    expect(a.body().scrollTop).toBe(800);
    expect(squash(textOf(a.status()))).toBe('正在跟随最新内容');
    a.unmount();
    const b = mountLog();
    userScroll(b.body(), 500);
    userScroll(b.body(), 759);
    advance(1000);
    expect(b.state()).toBe('paused');
    expect(b.body().scrollTop).toBe(759);
  });

  it('paused 中每个滚动事件都重新计时 150ms', () => {
    const m = mountLog();
    userScroll(m.body(), 500);
    userScroll(m.body(), 760);
    advance(100);
    userScroll(m.body(), 760);
    advance(100);
    expect(m.state(), '第二次滚动重新计时，t=200 时还不到').toBe('paused');
    advance(49);
    expect(m.state()).toBe('paused');
    advance(1);
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(800);
  });

  it('[回到底部] 立即恢复 following 并滚到底，焦点到「跟随」开关里的 role=switch；之后往上滚仍能再暂停', () => {
    const m = mountLog();
    userScroll(m.body(), 500);
    fireEvent.click(buttonByText(m.status(), '回到底部'));
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(800);
    expect(document.activeElement).toBe(m.sw());
    expect(m.sw().getAttribute('role')).toBe('switch');
    advance(1000);
    expect(m.state()).toBe('following');
    userScroll(m.body(), 600);
    expect(m.state(), '回到底部之后记下的 scrollTop 是 800，往上滚到 600 且离底 200 要暂停').toBe('paused');
  });

  it('开关关→off（追加不滚，往上滚也不暂停，计时器不会把它拉回）；开关开→following 并滚到底；paused 时点开关也是关', () => {
    const m = mountLog();
    fireEvent.click(m.sw());
    expect(m.state()).toBe('off');
    SH = 1500;
    m.update({ pages: pagesOf(2) });
    expect(m.body().scrollTop).toBe(800);
    userScroll(m.body(), 100);
    advance(1000);
    expect(m.state()).toBe('off');
    fireEvent.click(m.sw());
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(1300);
    expect(m.sw().getAttribute('aria-checked')).toBe('true');
    userScroll(m.body(), 500);
    expect(m.state()).toBe('paused');
    userScroll(m.body(), 1260);
    fireEvent.click(m.sw());
    expect(m.state()).toBe('off');
    advance(1000);
    expect(m.state(), '关掉之后，paused 留下的计时到点也不能把它拉回 following').toBe('off');
    fireEvent.click(m.sw());
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(1300);
  });

  it('键盘空格也能切换开关（Switch 自带）；defaultFollow=false 时挂载为 off 且不滚动，打开后滚到底', () => {
    const m = mountLog({ defaultFollow: false });
    expect(m.state()).toBe('off');
    expect(m.body().scrollTop).toBe(0);
    expect(m.sw().getAttribute('aria-checked')).toBe('false');
    fireEvent.keyDown(m.sw(), { key: ' ' });
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(800);
  });

  it('followDisabledReason 非空→disabled：开关 aria-disabled 且不可聚焦、title 与底部文字都是原因、追加不滚；变回空→following 并滚到底', () => {
    const m = mountLog({ followDisabledReason: REASON });
    expect(m.state()).toBe('disabled');
    expect(textOf(m.status())).toBe(REASON);
    expect(m.root.querySelector('.tt-log__follow')!.getAttribute('title')).toBe(REASON);
    const sw = m.sw();
    expect(sw.getAttribute('aria-disabled')).toBe('true');
    expect(sw.hasAttribute('tabindex'), '禁用的开关不可聚焦').toBe(false);
    expect(sw.getAttribute('aria-checked')).toBe('false');
    expect(m.body().scrollTop, '禁用时挂载不滚动').toBe(0);
    act(() => {
      sw.focus();
    });
    expect(document.activeElement).not.toBe(sw);
    fireEvent.click(sw);
    expect(m.state()).toBe('disabled');
    SH = 1500;
    m.update({ pages: pagesOf(2) });
    expect(m.body().scrollTop).toBe(0);
    m.update({ followDisabledReason: '' });
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(1300);
    expect(m.root.querySelector('.tt-log__follow')!.hasAttribute('title')).toBe(false);
    expect(m.sw().hasAttribute('aria-disabled') && m.sw().getAttribute('aria-disabled') === 'true').toBe(false);
  });

  it('paused 或 off 时设了原因再清掉，都回到 following 并滚到底；undefined 也算空', () => {
    const m = mountLog();
    userScroll(m.body(), 500);
    expect(m.state()).toBe('paused');
    m.update({ followDisabledReason: REASON });
    expect(m.state()).toBe('disabled');
    advance(1000);
    expect(m.state()).toBe('disabled');
    m.update({ followDisabledReason: undefined });
    expect(m.state()).toBe('following');
    expect(m.body().scrollTop).toBe(800);
    fireEvent.click(m.sw());
    expect(m.state()).toBe('off');
    m.update({ followDisabledReason: REASON });
    expect(m.state()).toBe('disabled');
    m.update({ followDisabledReason: '' });
    expect(m.state()).toBe('following');
  });

  it('following 中过滤变化后滚到底；paused 中过滤变化不滚动；输入框受控', () => {
    const m = mountLog({ pages: pagesOf(3) });
    m.body().scrollTop = 100;
    fireEvent.change(m.input(), { target: { value: 'event' } });
    expect(m.input().value).toBe('event');
    expect(m.body().scrollTop).toBe(800);
    userScroll(m.body(), 500);
    expect(m.state()).toBe('paused');
    fireEvent.change(m.input(), { target: { value: 'event 2' } });
    expect(m.input().value).toBe('event 2');
    expect(m.body().scrollTop).toBe(500);
  });

  it('只用 setTimeout：暂停后的计时不堆积；卸载后没有挂起的计时器', () => {
    const m = mountLog();
    const base = vi.getTimerCount();
    userScroll(m.body(), 500);
    const paused = vi.getTimerCount();
    expect(paused).toBeGreaterThan(base);
    for (const top of [510, 520, 530, 540]) userScroll(m.body(), top);
    expect(vi.getTimerCount(), '每次滚动重新计时，不堆积').toBeLessThanOrEqual(paused);
    m.unmount();
    expect(vi.getTimerCount(), '卸载时清掉计时器').toBeLessThanOrEqual(base);
    advance(1000);
  });
});
"""

# ---- filter：LogFollow 与 TextViewer 的过滤（D08） ----
PROBE_FILTER = PRELUDE + r"""
let LogFollow: any;

beforeAll(async () => {
  const mod: any = await import('../src/components/LogFollow');
  LogFollow = mod.LogFollow ?? mod.default;
});

const ESC = '\u001b';
const JPAGES: any[] = [
  {
    mode: 'jsonl',
    lines: [
      { n: 1, text: 'Hello World' },
      { n: 2, text: 'second LINE' },
      { n: 3, hidden: 'not_json' },
      { n: 4, text: ESC + '[31mred ERROR' + ESC + '[0m here' },
      { n: 5, text: 'part-A ', part: 1, parts: 2 },
    ],
  },
  {
    mode: 'jsonl',
    lines: [
      { n: 5, text: 'part-B', part: 2, parts: 2 },
      { n: 6, text: 'tail line' },
    ],
  },
];
const TPAGES: any[] = [
  { mode: 'text', text: 'one\ntwo abc' + ESC + '[3' },
  { mode: 'text', text: '1mdef' + ESC + '[0m end\nthree\n' },
];

function mountLog(props: any = {}) {
  const spies = { onCopy: vi.fn(), onLoadMore: vi.fn() };
  let cur: any = { title: 't', pages: JPAGES, hasMore: false, ...props };
  const el = () => <LogFollow onCopy={spies.onCopy} onLoadMore={spies.onLoadMore} {...cur} />;
  const r = render(el());
  const root = r.container.querySelector('.tt-log') as HTMLElement;
  expect(root, '应有根元素 .tt-log').not.toBeNull();
  const input = () => root.querySelector('.tt-log__filter-input') as HTMLInputElement;
  return {
    ...r,
    root,
    ...spies,
    update: (patch: any) => {
      cur = { ...cur, ...patch };
      r.rerender(el());
    },
    type: (value: string) => fireEvent.change(input(), { target: { value } }),
    input,
  };
}
const rowEls = (root: HTMLElement) => Array.from(root.querySelectorAll('.tt-viewer__row')) as HTMLElement[];
function nums(root: HTMLElement) {
  return rowEls(root).map((r) => textOf(r.querySelector('.tt-viewer__num')));
}
function copied(m: any) {
  const before = m.onCopy.mock.calls.length;
  fireEvent.click(m.root.querySelector('button[aria-label="复制已显示的文字"]') as HTMLElement);
  expect(m.onCopy.mock.calls.length).toBe(before + 1);
  return m.onCopy.mock.calls[m.onCopy.mock.calls.length - 1][0];
}

describe('LogFollow 过滤', () => {
  it('空串不过滤；不分大小写的子串包含；行号保持原值；拼好分片后匹配；去掉 ANSI 后匹配', () => {
    const m = mountLog();
    expect(nums(m.root)).toEqual(['1', '2', '3', '4', '5', '6']);
    const cases: Array<[string, string[]]> = [
      ['hello', ['1']],
      ['HELLO WORLD', ['1']],
      ['second line', ['2']],
      ['SECOND LINE', ['2']],
      ['red error', ['4']],
      ['error here', ['4']],
      ['a part-b', ['5']],
      ['PART-A PART-B', ['5']],
      ['line', ['2', '6']],
      [' ', ['1', '2', '4', '5', '6']],
    ];
    for (const [value, want] of cases) {
      m.type(value);
      expect(nums(m.root), '过滤「' + value + '」').toEqual(want);
    }
    m.type('');
    expect(nums(m.root)).toEqual(['1', '2', '3', '4', '5', '6']);
  });

  it('ANSI 在被页边界切开时也先拼好、去掉再匹配；ESC 与 [31m 本身匹配不到', () => {
    const m = mountLog({ pages: TPAGES });
    expect(nums(m.root)).toEqual(['1', '2', '3']);
    m.type('abcdef end');
    expect(nums(m.root)).toEqual(['2']);
    m.type('ABC');
    expect(nums(m.root)).toEqual(['2']);
    m.type('[3');
    expect(nums(m.root)).toEqual([]);
    m.type(ESC);
    expect(nums(m.root)).toEqual([]);
    const j = mountLog();
    j.type('31m');
    expect(nums(j.root)).toEqual([]);
    j.type('[31m');
    expect(nums(j.root)).toEqual([]);
  });

  it('隐藏行（服务只给占位的行）在非空过滤下不显示；清空后还原', () => {
    const m = mountLog();
    expect(textOf(m.root)).toContain('这一行不是合法 JSON，已隐藏');
    m.type(' ');
    expect(textOf(m.root)).not.toContain('这一行不是合法 JSON，已隐藏');
    expect(m.root.querySelectorAll('.tt-viewer__hidden').length).toBe(0);
    m.type('');
    expect(textOf(m.root)).toContain('这一行不是合法 JSON，已隐藏');
    expect(m.root.querySelectorAll('.tt-viewer__hidden').length).toBe(1);
  });

  it('一行也没有时主体显示「没有匹配的行」；「已显示 N 页」不变；清空后提示消失', () => {
    const m = mountLog();
    m.type('zzz-no-such-text');
    expect(nums(m.root)).toEqual([]);
    const body = m.root.querySelector('.tt-viewer__body') as HTMLElement;
    expect(textOf(body)).toContain('没有匹配的行');
    expect(textOf(m.root.querySelector('.tt-viewer__foot'))).toContain('已显示 2 页');
    m.type('');
    expect(textOf(m.root)).not.toContain('没有匹配的行');
    expect(nums(m.root).length).toBe(6);
    expect(textOf(m.root.querySelector('.tt-viewer__foot'))).toContain('已显示 2 页');
  });

  it('复制只含显示的行；pages 更新后新行按过滤显示、行号接着数', () => {
    const m = mountLog();
    expect(copied(m)).toBe('Hello World\nsecond LINE\nred ERROR here\npart-A part-B\ntail line');
    m.type('line');
    expect(copied(m)).toBe('second LINE\ntail line');
    m.update({
      pages: [...JPAGES, { mode: 'jsonl', lines: [{ n: 7, text: 'Another Line' }, { n: 8, text: 'nothing' }] }],
    });
    expect(nums(m.root)).toEqual(['2', '6', '7']);
    expect(copied(m)).toBe('second LINE\ntail line\nAnother Line');
    expect(textOf(m.root.querySelector('.tt-viewer__foot'))).toContain('已显示 3 页');
  });

  it('行尾的 [继续加载] 跟着那一行：那一行被滤掉时不显示，底栏的照常', () => {
    const pages = [{ mode: 'jsonl', lines: [{ n: 1, text: 'alpha' }, { n: 2, text: 'beta start', part: 1, parts: 2 }] }];
    const m = mountLog({ pages, hasMore: true });
    const split = () => {
      const all = buttonsByText(m.root, '继续加载');
      const rs = rowEls(m.root);
      return {
        inRow: all.filter((b) => rs.some((r) => r.contains(b))),
        inFoot: all.filter((b) => !rs.some((r) => r.contains(b))),
      };
    };
    expect(split().inRow.length).toBe(1);
    expect(split().inFoot.length).toBe(1);
    m.type('alpha');
    expect(nums(m.root)).toEqual(['1']);
    expect(split().inRow.length, '最后一行被滤掉，行尾的按钮不显示').toBe(0);
    expect(split().inFoot.length, '底栏的照常').toBe(1);
    m.type('beta');
    expect(nums(m.root)).toEqual(['2']);
    expect(split().inRow.length).toBe(1);
    expect(split().inFoot.length).toBe(1);
    fireEvent.click(split().inRow[0]);
    expect(m.onLoadMore).toHaveBeenCalledTimes(1);
  });
});
"""

# ---- slots：TextViewer 的 6 个可选属性（D09，甲） ----
PROBE_SLOTS = PRELUDE + r"""
let TextViewer: any;

beforeAll(async () => {
  const mod: any = await import('../src/components/TextViewer');
  TextViewer = mod.TextViewer ?? mod.default;
});

const ESC = '\u001b';
const JPAGES: any[] = [
  {
    mode: 'jsonl',
    lines: [
      { n: 1, text: 'Hello World' },
      { n: 2, text: 'second LINE' },
      { n: 3, hidden: 'not_json' },
      { n: 4, text: ESC + '[31mred ERROR' + ESC + '[0m here' },
      { n: 5, text: 'tail line', part: 1, parts: 2 },
    ],
  },
];
const TEXT_PAGES: any[] = [{ mode: 'text', text: 'one\ntwo\nthree\n' }];

function mountTv(props: any = {}) {
  const onCopy = vi.fn();
  const r = render(<TextViewer title="t" pages={TEXT_PAGES} hasMore={false} onCopy={onCopy} {...props} />);
  const root = r.container.querySelector('.tt-viewer') as HTMLElement;
  expect(root, '应有根元素 div.tt-viewer').not.toBeNull();
  return {
    ...r,
    root,
    onCopy,
    head: root.querySelector('.tt-viewer__head') as HTMLElement,
    body: root.querySelector('.tt-viewer__body') as HTMLElement,
    foot: root.querySelector('.tt-viewer__foot') as HTMLElement,
  };
}
const FOLLOWING = Node.DOCUMENT_POSITION_FOLLOWING;
const norm = (html: string) => html.replace(/:r[0-9a-z]+:/g, ':rX:');
function nums(root: HTMLElement) {
  return Array.from(root.querySelectorAll('.tt-viewer__row')).map((r) => textOf(r.querySelector('.tt-viewer__num')));
}

describe('TextViewer 的可选属性', () => {
  it('一个都不传（或都传 undefined）时 DOM 同 T007：根只有 head、body、foot 三个孩子，没有多渲染的包装元素，主体 class 就是 tt-viewer__body', () => {
    const a = mountTv();
    expect(a.root.className).toBe('tt-viewer');
    expect(Array.from(a.root.children).map((c) => c.className)).toEqual(['tt-viewer__head', 'tt-viewer__body', 'tt-viewer__foot']);
    expect(a.body.className).toBe('tt-viewer__body');
    expect(Array.from(a.head.children).map((c) => c.className)).toEqual(['tt-viewer__title', 'tt-viewer__tools']);
    const tools = a.head.querySelector('.tt-viewer__tools') as HTMLElement;
    expect(Array.from(tools.querySelectorAll('button.tt-viewer__toggle')).map((b) => textOf(b))).toEqual(['行号', '换行']);
    expect(tools.querySelectorAll('button[aria-label="复制已显示的文字"]').length).toBe(1);
    expect(Array.from(a.body.children).every((c) => c.className === 'tt-viewer__row')).toBe(true);
    expect(a.body.children.length).toBe(3);
    const htmlA = norm(a.container.innerHTML);
    a.unmount();
    const b = mountTv({
      bodyRef: undefined, onBodyScroll: undefined, bodyClassName: undefined, headerExtra: undefined, bottomBar: undefined, filter: undefined,
    });
    expect(norm(b.container.innerHTML)).toBe(htmlA);
    b.unmount();
    const c = mountTv({ filter: '' });
    expect(norm(c.container.innerHTML), 'filter 为空串等于不过滤').toBe(htmlA);
  });

  it('bodyRef（对象 ref 与回调 ref）指向放行的主体 div.tt-viewer__body', () => {
    const ref = React.createRef<HTMLDivElement>();
    const a = mountTv({ bodyRef: ref });
    expect(ref.current).toBe(a.body);
    expect(ref.current!.tagName).toBe('DIV');
    expect(ref.current!.classList.contains('tt-viewer__body')).toBe(true);
    a.unmount();
    expect(ref.current).toBeNull();
    let got: HTMLElement | null = null;
    const b = mountTv({ bodyRef: (el: HTMLElement | null) => { if (el) got = el; } });
    expect(got).toBe(b.body);
  });

  it('onBodyScroll 收到该元素的 scroll 事件（事件的 currentTarget 是主体）', () => {
    const seen: any[] = [];
    const spy = vi.fn((e: any) => {
      seen.push(e.currentTarget);
    });
    const a = mountTv({ onBodyScroll: spy });
    fireEvent.scroll(a.body);
    expect(spy).toHaveBeenCalledTimes(1);
    expect(seen[0]).toBe(a.body);
    fireEvent.scroll(a.head);
    expect(spy).toHaveBeenCalledTimes(1);
    fireEvent.scroll(a.body);
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it('bodyClassName 加在主体 class 上，不动根与别的元素', () => {
    const a = mountTv({ bodyClassName: 'extra-body second' });
    expect(a.body.classList.contains('tt-viewer__body')).toBe(true);
    expect(a.body.classList.contains('extra-body')).toBe(true);
    expect(a.body.classList.contains('second')).toBe(true);
    expect(a.root.className).toBe('tt-viewer');
    expect(a.head.className).toBe('tt-viewer__head');
  });

  it('headerExtra 在头部最右端，复制钮之后；不在主体里', () => {
    const a = mountTv({ headerExtra: <i data-testid="hx">额外</i> });
    const hx = a.root.querySelector('[data-testid="hx"]') as HTMLElement;
    expect(hx).not.toBeNull();
    expect(a.head.contains(hx)).toBe(true);
    expect(a.body.contains(hx)).toBe(false);
    const copy = a.head.querySelector('button[aria-label="复制已显示的文字"]') as HTMLElement;
    expect(copy.compareDocumentPosition(hx) & FOLLOWING).toBeTruthy();
    const toggles = Array.from(a.head.querySelectorAll('button.tt-viewer__toggle'));
    for (const t of toggles) expect(t.compareDocumentPosition(hx) & FOLLOWING).toBeTruthy();
    expect(a.head.querySelectorAll('[data-testid="hx"]').length).toBe(1);
  });

  it('bottomBar 在主体与底栏之间、不在主体里（不随主体滚动），出现一次', () => {
    const a = mountTv({ bottomBar: <div data-testid="bb">底部条</div>, changed: true });
    const bb = a.root.querySelector('[data-testid="bb"]') as HTMLElement;
    expect(bb).not.toBeNull();
    expect(a.root.querySelectorAll('[data-testid="bb"]').length).toBe(1);
    expect(a.body.contains(bb)).toBe(false);
    expect(a.foot.contains(bb)).toBe(false);
    expect(a.body.compareDocumentPosition(bb) & FOLLOWING).toBeTruthy();
    expect(bb.compareDocumentPosition(a.foot) & FOLLOWING).toBeTruthy();
    const kids = Array.from(a.root.children);
    const holder = kids.find((k) => k === bb || k.contains(bb)) as Element;
    expect(kids.indexOf(holder)).toBe(kids.indexOf(a.body) + 1);
    expect(kids.indexOf(holder)).toBe(kids.indexOf(a.foot) - 1);
  });

  it('filter：不分大小写的子串包含，匹配拼好分片、去掉 ANSI 之后的整行；行号不变；隐藏行不显示；没有匹配时显示「没有匹配的行」；已显示 N 页不变', () => {
    const cases: Array<[string, string[]]> = [
      ['', ['1', '2', '3', '4', '5']],
      ['hello', ['1']],
      ['SECOND line', ['2']],
      ['red error here', ['4']],
      ['LINE', ['2', '5']],
      [' ', ['1', '2', '4', '5']],
    ];
    for (const [value, want] of cases) {
      const a = mountTv({ pages: JPAGES, filter: value });
      expect(nums(a.root), '过滤「' + value + '」').toEqual(want);
      expect(textOf(a.foot)).toContain('已显示 1 页');
      a.unmount();
    }
    const none = mountTv({ pages: JPAGES, filter: '31m' });
    expect(nums(none.root)).toEqual([]);
    expect(textOf(none.body)).toContain('没有匹配的行');
    none.unmount();
    const hidden = mountTv({ pages: JPAGES, filter: 'e' });
    expect(textOf(hidden.root)).not.toContain('这一行不是合法 JSON，已隐藏');
    hidden.unmount();
    const all = mountTv({ pages: JPAGES });
    expect(textOf(all.root)).toContain('这一行不是合法 JSON，已隐藏');
  });

  it('filter：text 模式的行号保持原值；复制只含显示的行；filter 变化后重新过滤、清空后还原', () => {
    const a = mountTv({ pages: TEXT_PAGES, filter: 'T' });
    expect(nums(a.root)).toEqual(['2', '3']);
    fireEvent.click(a.root.querySelector('button[aria-label="复制已显示的文字"]') as HTMLElement);
    expect(a.onCopy).toHaveBeenCalledWith('two\nthree');
    a.rerender(<TextViewer title="t" pages={TEXT_PAGES} hasMore={false} onCopy={a.onCopy} filter="three" />);
    expect(nums(a.root)).toEqual(['3']);
    a.rerender(<TextViewer title="t" pages={TEXT_PAGES} hasMore={false} onCopy={a.onCopy} filter="" />);
    expect(nums(a.root)).toEqual(['1', '2', '3']);
  });

  it('六个属性一起传不互相干扰；已有属性（title、changed 提示条、行号开关）照旧', () => {
    const ref = React.createRef<HTMLDivElement>();
    const onBodyScroll = vi.fn();
    const a = mountTv({
      bodyRef: ref, onBodyScroll, bodyClassName: 'bc', headerExtra: <i data-testid="hx" />, bottomBar: <i data-testid="bb" />, filter: 'o',
      changed: true, onReload: vi.fn(),
    });
    expect(ref.current).toBe(a.body);
    expect(nums(a.root)).toEqual(['1', '2']);
    expect(textOf(a.root.querySelector('.tt-viewer__title'))).toBe('t');
    expect(a.root.querySelector('.tt-banner')).not.toBeNull();
    fireEvent.click(buttonByText(a.head, '行号'));
    expect(a.root.classList.contains('tt-viewer--no-num')).toBe(true);
    fireEvent.scroll(a.body);
    expect(onBodyScroll).toHaveBeenCalledTimes(1);
    noStatusRole();
  });
});
"""

# ---- showcase：DiffShowcase（D11，过渡） ----
PROBE_SHOWCASE = PRELUDE + r"""
let Showcase: any;

beforeAll(async () => {
  Showcase = (await import('../src/showcase/DiffShowcase')).default;
});

const DEMOS: string[] = __DEMOS__;
const EXISTING: string[] = __EXISTING__;
const ESC = '\u001b';

afterEach(() => {
  delete (navigator as any).clipboard;
});

function demo(name: string): HTMLElement {
  const nodes = document.querySelectorAll('[data-demo="' + name + '"]');
  expect(nodes.length, '应恰有一个 data-demo="' + name + '" 的节').toBe(1);
  return nodes[0] as HTMLElement;
}
async function press(btn: HTMLElement) {
  await act(async () => {
    fireEvent.click(btn);
  });
}
const rowCount = (sec: HTMLElement) => sec.querySelectorAll('.tt-viewer__row').length;

async function expandAll(sec: HTMLElement) {
  for (let i = 0; i < 30; i += 1) {
    const closed = Array.from(sec.querySelectorAll('.tt-diff__file-head button[aria-expanded="false"]')) as HTMLElement[];
    if (closed.length === 0) return;
    await press(closed[0]);
  }
}
async function loadAll(sec: HTMLElement) {
  for (let i = 0; i < 12; i += 1) {
    const more = buttonsByText(sec, '继续加载');
    if (more.length === 0) return;
    await press(more[0]);
    await settle(() => buttonsByText(sec, '正在加载…').length === 0, '加载完成');
  }
}

describe('DiffShowcase 演示', () => {
  it('两节，data-demo 依次为 diff-view、log-follow，每节是 section.showcase__section 且有一个 h2.showcase__h2（标题不含 Button）；不与已有的 23 个重复', () => {
    render(<Showcase />);
    const found = Array.from(document.querySelectorAll('[data-demo]')).map((e) => e.getAttribute('data-demo'));
    expect(found).toEqual(DEMOS);
    for (const name of DEMOS) {
      expect(EXISTING, name + ' 不能与已有的 data-demo 重复').not.toContain(name);
      const sec = demo(name);
      expect(sec.tagName).toBe('SECTION');
      expect(sec.classList.contains('showcase__section')).toBe(true);
      const h2s = sec.querySelectorAll('h2.showcase__h2');
      expect(h2s.length, name + ' 应有一个 h2.showcase__h2').toBe(1);
      expect(textOf(h2s[0])).not.toBe('');
      expect(textOf(h2s[0]), '节标题里不写 Button').not.toMatch(/Button/);
    }
  });

  it('不渲染 role=status、对话框、菜单；没有文字的按钮都有 aria-label；按钮文字与全文不含「亮」「暗」「跟随系统」', () => {
    render(<Showcase />);
    noStatusRole();
    expect(document.querySelectorAll('[role="dialog"], [role="alertdialog"], [role="menu"], [aria-modal], dialog').length).toBe(0);
    const bad = Array.from(document.querySelectorAll('button')).filter(
      (b) => textOf(b) === '' && !(b.getAttribute('aria-label') || '').trim(),
    );
    expect(bad.length, '没有文字的按钮要有 aria-label').toBe(0);
    for (const b of Array.from(document.querySelectorAll('button'))) {
      expect(textOf(b)).not.toMatch(/亮|暗|跟随系统/);
    }
    expect(textOf(document.body)).not.toContain('跟随系统');
  });

  it('diff-view 一节：title 为 candidate.patch；有改动文件（两个片段，有上下文、删、加）、新文件（缺省折叠）、删除的文件（含 -- 开头的删除行）、改名、二进制、超长行', async () => {
    render(<Showcase />);
    const sec = demo('diff-view');
    const view = sec.querySelector('.tt-diff') as HTMLElement;
    expect(view, 'diff-view 一节应有 DiffView').not.toBeNull();
    expect(textOf(view.querySelector('.tt-diff__summary'))).toMatch(/^candidate\.patch · \d+ 个文件 · \+\d+ −\d+$/);
    const secs = Array.from(view.querySelectorAll('section.tt-diff__file')) as HTMLElement[];
    const statuses = secs.map((s) => s.getAttribute('data-status'));
    for (const want of ['modified', 'added', 'deleted', 'renamed']) expect(statuses, '应有 ' + want + ' 的文件').toContain(want);
    const added = secs.filter((s) => s.getAttribute('data-status') === 'added' && s.getAttribute('data-binary') !== 'true');
    expect(added.length).toBeGreaterThan(0);
    expect(added.some((s) => s.getAttribute('data-collapsed') === 'true'), '新文件缺省折叠').toBe(true);
    expect(secs.some((s) => s.getAttribute('data-binary') === 'true' && textOf(s).includes('二进制文件，不显示内容'))).toBe(true);
    const renamed = secs.find((s) => s.getAttribute('data-status') === 'renamed') as HTMLElement;
    expect(textOf(renamed.querySelector('.tt-diff__file-body'))).toBe('没有内容改动');
    await expandAll(sec);
    const all = Array.from(view.querySelectorAll('section.tt-diff__file')) as HTMLElement[];
    const modified = all.filter((s) => s.getAttribute('data-status') === 'modified' && s.getAttribute('data-binary') !== 'true');
    expect(modified.some((s) => s.querySelectorAll('.tt-diff__row[data-kind="hunk"]').length >= 2), '改动文件有两个片段').toBe(true);
    const kinds = new Set(Array.from(view.querySelectorAll('.tt-diff__row')).map((r) => r.getAttribute('data-kind')));
    for (const k of ['context', 'del', 'add', 'hunk']) expect(kinds.has(k), '应有 data-kind=' + k + ' 的行').toBe(true);
    const deleted = all.filter((s) => s.getAttribute('data-status') === 'deleted');
    expect(deleted.some((s) => Array.from(s.querySelectorAll('.tt-diff__row[data-kind="del"] .tt-diff__text')).some((t) => (t.textContent || '').startsWith('--'))),
      '删除的文件里有以 -- 开头的删除行').toBe(true);
    const longest = Math.max(...Array.from(view.querySelectorAll('.tt-diff__text')).map((t) => (t.textContent || '').length));
    expect(longest, '应有 2000 字符以上的超长行').toBeGreaterThanOrEqual(2000);
    expect(view.querySelectorAll('.tt-diff__eof').length, '最后一行带 No newline 标记').toBeGreaterThan(0);
  });

  it('W1 样例在 DOM 里只是文字：没有 img、script、a、带 on 或 href 的元素，没有 ESC 字符，也没有 [31m；网址不变链接', async () => {
    render(<Showcase />);
    await expandAll(demo('diff-view'));
    await loadAll(demo('log-follow'));
    expect(document.body.querySelectorAll('img, script, a, iframe, object, embed, style, link').length).toBe(0);
    expect(document.body.querySelectorAll('[onerror], [href], [src], [srcdoc]').length).toBe(0);
    const diffText = demo('diff-view').textContent || '';
    expect(diffText).toContain('<script>alert(1)</script>');
    expect(diffText).toContain('<img src=x onerror=alert(1)>');
    expect(diffText).toMatch(/https?:\/\/\S+/);
    expect(demo('log-follow').textContent || '').toContain('<script>alert(1)</script>');
    expect((document.body.textContent || '').includes(ESC)).toBe(false);
    expect((document.body.textContent || '').includes('[31m')).toBe(false);
  });

  it('log-follow 一节：LogFollow 的标题、隐藏行的两种说明、第 1/2 与 2/2 片、三个按钮；没有轻提示', async () => {
    render(<Showcase />);
    const sec = demo('log-follow');
    expect(sec.querySelector('.tt-log'), 'log-follow 一节应有 LogFollow').not.toBeNull();
    expect(textOf(sec.querySelector('.tt-viewer__title'))).toBe('ui-readonly-api / events.jsonl');
    // 合同 §6：初始页含第 6 行第 1/2 片；TextViewer 对同一个 n 只显示最后加载的一片，所以 1/2 要在加载之前看
    const first = textOf(sec);
    expect(first).toMatch(/第\s*1\/2\s*片/);
    await loadAll(sec);
    const text = textOf(sec);
    expect(text).toContain('这一行不是合法 JSON，已隐藏');
    expect(text).toContain('这一行超过 4 MiB，已隐藏');
    expect(text).toMatch(/第\s*2\/2\s*片/);
    expect(rowCount(sec)).toBeGreaterThanOrEqual(20);
    for (const label of ['开始追加', '停止追加', '模拟 attempt 已结束']) {
      expect(buttonsByText(sec, label).length, '应有按钮「' + label + '」').toBe(1);
    }
    expect(document.querySelectorAll('.tt-toast, [role="status"]').length).toBe(0);
  });

  it('挂载后没有计时器在跑；点 [开始追加] 后每 400ms 追加一行；[停止追加] 停下；卸载后计时器清空', async () => {
    vi.useFakeTimers();
    const r = render(<Showcase />);
    expect(vi.getTimerCount(), '挂载后没有计时器在跑').toBe(0);
    const sec = demo('log-follow');
    const n0 = rowCount(sec);
    await act(async () => {
      fireEvent.click(buttonByText(sec, '开始追加'));
    });
    expect(vi.getTimerCount()).toBeGreaterThan(0);
    advance(400 * 3);
    expect(rowCount(sec), '每 400ms 追加一行').toBe(n0 + 3);
    await act(async () => {
      fireEvent.click(buttonByText(sec, '停止追加'));
    });
    advance(400 * 5);
    expect(rowCount(sec)).toBe(n0 + 3);
    await act(async () => {
      fireEvent.click(buttonByText(sec, '开始追加'));
    });
    advance(400);
    expect(rowCount(sec)).toBe(n0 + 4);
    r.unmount();
    expect(vi.getTimerCount(), '卸载后计时器清空').toBe(0);
  });

  it('追加到 500 行自己停', async () => {
    vi.useFakeTimers();
    render(<Showcase />);
    const sec = demo('log-follow');
    const n0 = rowCount(sec);
    await act(async () => {
      fireEvent.click(buttonByText(sec, '开始追加'));
    });
    let last = n0;
    let stableAt = -1;
    for (let tick = 1; tick <= 700; tick += 1) {
      advance(400);
      const now = rowCount(sec);
      if (now === last) {
        if (stableAt < 0) stableAt = tick;
        if (tick - stableAt >= 5) break;
      } else {
        stableAt = -1;
      }
      last = now;
    }
    expect(stableAt, '追加应当自己停下').toBeGreaterThan(0);
    expect(last).toBeGreaterThan(n0 + 50);
    expect(last).toBeLessThanOrEqual(n0 + 600);
    advance(400 * 10);
    expect(rowCount(sec)).toBe(last);
  }, 120000);

  it('[模拟 attempt 已结束] 切换 followDisabledReason：底部状态 disabled 与原因文字；再点恢复跟随', async () => {
    render(<Showcase />);
    const sec = demo('log-follow');
    const status = () => sec.querySelector('.tt-log__status') as HTMLElement;
    expect(status().getAttribute('data-follow')).toBe('following');
    await press(buttonByText(sec, '模拟 attempt 已结束'));
    expect(status().getAttribute('data-follow')).toBe('disabled');
    expect(textOf(status())).toBe('attempt 已结束，没有新事件');
    expect(sec.querySelector('.tt-log__follow')!.getAttribute('title')).toBe('attempt 已结束，没有新事件');
    await press(buttonByText(sec, '模拟 attempt 已结束'));
    expect(status().getAttribute('data-follow')).toBe('following');
  });

  it('复制：没有 navigator.clipboard 显示「这个环境没有剪贴板接口」；有就写进去并显示「已复制 N 个字符」；写失败显示「复制失败」', async () => {
    const first = render(<Showcase />);
    let sec = demo('log-follow');
    const copyBtn = () => demo('log-follow').querySelector('button[aria-label="复制已显示的文字"]') as HTMLElement;
    await press(copyBtn());
    await settle(() => textOf(sec).includes('这个环境没有剪贴板接口'), '没有剪贴板接口的提示');
    first.unmount();
    const write = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: write }, configurable: true });
    const second = render(<Showcase />);
    sec = demo('log-follow');
    await press(copyBtn());
    await settle(() => /已复制\s*\d+\s*个字符/.test(textOf(sec)), '已复制 N 个字符');
    const n = Number((textOf(sec).match(/已复制\s*(\d+)\s*个字符/) as RegExpMatchArray)[1]);
    expect(write).toHaveBeenCalledTimes(1);
    expect(String(write.mock.calls[0][0]).length).toBe(n);
    second.unmount();
    const bad = vi.fn().mockRejectedValue(new Error('denied'));
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: bad }, configurable: true });
    render(<Showcase />);
    sec = demo('log-follow');
    await press(copyBtn());
    await settle(() => textOf(sec).includes('复制失败'), '复制失败');
    expect(document.querySelectorAll('.tt-toast, [role="status"]').length).toBe(0);
  });
});
"""

# (键, 探针源码, 需要先存在的仓库文件)
PROBE_SPECS = {
    "parse": (PROBE_PARSE, [f"{DIFF_REL}/parseDiff.ts", f"{DIFF_REL}/splitPairs.ts"]),
    "view": (PROBE_VIEW, [f"{COMP_REL}/DiffView.tsx"]),
    "follow": (PROBE_FOLLOW, [f"{COMP_REL}/LogFollow.tsx"]),
    "filter": (PROBE_FILTER, [f"{COMP_REL}/LogFollow.tsx", f"{COMP_REL}/TextViewer.tsx"]),
    "slots": (PROBE_SLOTS, [f"{COMP_REL}/TextViewer.tsx"]),
    "showcase": (PROBE_SHOWCASE, [f"{SHOW_REL}/DiffShowcase.tsx", f"{COMP_REL}/DiffView.tsx", f"{COMP_REL}/LogFollow.tsx"]),
}
# 组件探针先跑，演示探针最后跑
PROBE_ORDER = ("parse", "view", "follow", "filter", "slots", "showcase")


def probe_count(source):
    """探针里 ``it(`` 开头的行数；循环里的 it 一行可能跑多条，所以通过数只要求不少于它。"""
    return len(re.findall(r"^\s*it\(", source, re.M))


def build_probe_source(key):
    source = PROBE_SPECS[key][0]
    if key == "showcase":
        source = source.replace("__DEMOS__", json.dumps(list(DIFF_DEMOS))).replace("__EXISTING__", json.dumps(list(EXISTING_DEMOS)))
    return source


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


# 流水线前后不该变的文件（相对 desktop/web；合同 P10；甲时加 TextViewer.tsx、TextViewer.css）
WATCHED = ("package.json", "package-lock.json", "index.html", "vite.config.ts", "tsconfig.json",
           "src/styles/tokens.css", "src/styles/fonts.css", "src/styles/base.css", "src/main.tsx", "src/App.tsx", "src/App.css",
           "src/components/TextViewer.tsx", "src/components/TextViewer.css")


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
                try:
                    source = build_probe_source(key)
                except AssertionError as exc:
                    pipe.probe_skipped[key] = f"探针 {key} 的输入取不出来，未运行：{exc}"
                    continue
                name = f"probe-{uid}-t008-{key}.test.tsx"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                written.append(path)
                path.write_text(source, encoding="utf-8", newline="\n")
                pipe.probe_files[key] = name
                run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
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
# S 系列：静态断言
# ---------------------------------------------------------------------------

def test_s1_d10_files_and_exports():
    """S1 / D10（合同 §5、门禁断言 S1）：本片的 8 个新源码文件（DiffView.tsx/.css、diff/parseDiff.ts、diff/splitPairs.ts、LogFollow.tsx/.css、
    showcase/DiffShowcase.tsx、showcase/showcase-diff.css）都在；components/index.ts 的基线内容（行尾归一后）是新内容的前缀（只在末尾追加，
    文件头仍是「共五片」），末尾追加注释「第 7 片：差异视图（7.14）与日志跟随（7.15）」和 DiffView、DiffViewProps、LogFollow、LogFollowProps 四项导出，
    旧导出都在，去掉注释后不出现 overlay，不导出 evidence/ 与 diff/ 的内部函数。"""
    need_new_sources()
    fail_if(index_problems(_read(need_file(f"{COMP_REL}/index.ts"))), "components/index.ts 的导出")


def test_s1_d01_d02_d07_module_exports():
    """S1 / D01、D02、D07（合同 §1–§3）：diff/parseDiff.ts 导出 parseDiff、diff/splitPairs.ts 导出 splitPairs，两个模块是纯函数（不引入 React）；
    DiffView.tsx 导出 DiffView 与 DiffViewProps 并从 ./diff/ 取解析与配对；LogFollow.tsx 导出 LogFollow 与 LogFollowProps，建在 TextViewer 上。"""
    need_new_sources()
    problems = []
    for rel, name in ((f"{DIFF_REL}/parseDiff.ts", "parseDiff"), (f"{DIFF_REL}/splitPairs.ts", "splitPairs")):
        code = strip_ts_comments(_read(REPO_ROOT / rel))
        if not re.search(rf"export\s+(?:function|const)\s+{name}\b|export\s*\{{[^}}]*\b{name}\b|export\s+default\s+(?:function\s+)?{name}\b", code):
            problems.append(f"{rel} 应导出 {name}")
        if re.search(r"""from\s+['"]react(?:-dom)?(?:/[^'"]*)?['"]""", code):
            problems.append(f"{rel} 是纯函数模块，不该引入 React")
    view = strip_ts_comments(_read(REPO_ROOT / f"{COMP_REL}/DiffView.tsx"))
    if not re.search(r"export\s+(?:function|const)\s+DiffView\b|export\s*\{[^}]*\bDiffView\b", view):
        problems.append("DiffView.tsx 应导出 DiffView")
    if not re.search(r"export\s+(?:interface|type)\s+DiffViewProps\b|export\s+type\s*\{[^}]*\bDiffViewProps\b", view):
        problems.append("DiffView.tsx 应导出 DiffViewProps")
    if "./diff/parseDiff" not in view or "./diff/splitPairs" not in view:
        problems.append("DiffView.tsx 应从 ./diff/parseDiff 与 ./diff/splitPairs 取解析与配对")
    log = strip_ts_comments(_read(REPO_ROOT / f"{COMP_REL}/LogFollow.tsx"))
    if not re.search(r"export\s+(?:function|const)\s+LogFollow\b|export\s*\{[^}]*\bLogFollow\b", log):
        problems.append("LogFollow.tsx 应导出 LogFollow")
    if not re.search(r"export\s+(?:interface|type)\s+LogFollowProps\b|export\s+type\s*\{[^}]*\bLogFollowProps\b", log):
        problems.append("LogFollow.tsx 应导出 LogFollowProps")
    if not re.search(r"""from\s+['"]\./TextViewer['"]""", log):
        problems.append("LogFollow.tsx 应建在 ./TextViewer 上")
    if not re.search(r"""from\s+['"]\./evidence/ansi['"]""", _read(REPO_ROOT / f"{COMP_REL}/DiffView.tsx")) and \
            not any(re.search(r"""from\s+['"]\.\./evidence/ansi['"]""", _read(p)) for p in (REPO_ROOT / DIFF_REL).glob("*.ts")):
        problems.append("来自补丁的文字要用 T007 的 stripAnsi（evidence/ansi），DiffView.tsx 或 diff/ 里没有引用它")
    fail_if(problems, "新模块的导出与依赖")


def test_s2_d10_new_icons_match_contract():
    """S2 / D10（合同 §5）：icons/index.tsx 的基线内容（行尾归一后）是新内容的前缀；末尾追加的 PauseIcon（两个 rect：width 4 height 14 x 6 y 5 rx 1；
    width 4 height 14 x 14 y 5 rx 1，领域板 :381）、FilterIcon（polygon points=22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3，详情页 :638）、
    FileDiffIcon（四条 path，详情页 :389）沿用 Svg 包装、不自己写 fill 与 stroke；追加的那一段注释写「路径照画布」。"""
    fail_if(icon_problems(_read(need_file(f"{SRC_REL}/icons/index.tsx"))), "新增图标")


def test_s3_d12_no_forbidden_words_in_src():
    """S3 / D12（合同公共约定）：desktop/web/src/**/*.{ts,tsx} 全文（含注释与字符串）里没有 dangerouslySetInnerHTML、innerHTML、
    outerHTML、insertAdjacentHTML、eval(、new Function、document.write、srcdoc、createContextualFragment、DOMParser。
    先要求新代码已经存在（基线上这些词本来就一个都没有，空过没有意义）。"""
    need_new_sources()
    fail_if(forbidden_word_problems(src_ts_files()), "src 里的禁用词")


def test_s3_d12_new_sources_rules():
    """S3 / D12（合同公共约定、门禁断言 S3）：DiffView.tsx、LogFollow.tsx 与 diff/ 下的源码里不出现 href、src=、target=（全文），
    不渲染 role=status（去注释后），不调用 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver；
    DiffShowcase 没有 role 等于 status 的写法与四个接口名。"""
    need_new_sources()
    fail_if(new_source_problems(diff_component_sources()), "新组件与 diff/ 的源码")
    show = REPO_ROOT / f"{SHOW_REL}/DiffShowcase.tsx"
    fail_if(role_and_interface_problems("showcase/DiffShowcase.tsx", _read(show)), "DiffShowcase 的源码")


def test_s3_d07_log_follow_source_rules():
    """S3 / D07（合同 §3）：LogFollow.tsx 的计时只用 setTimeout 并在卸载时 clearTimeout，不用 requestAnimationFrame 与 performance.now，
    滚到底用 useLayoutEffect；常量 40 与 150 写在 LogFollow.tsx，同一行注释「UI 文档 7.15 :910」；不设 aria-live。"""
    need_new_sources()
    raw = _read(REPO_ROOT / f"{COMP_REL}/LogFollow.tsx")
    code = strip_ts_comments(raw)
    problems = []
    for word in ("requestAnimationFrame", "performance.now", "setInterval"):
        if word in code:
            problems.append(f"LogFollow.tsx 不该用 {word}（合同：计时只用 setTimeout）")
    for word in ("setTimeout", "clearTimeout", "useLayoutEffect"):
        if word not in code:
            problems.append(f"LogFollow.tsx 应使用 {word}")
    for n in (40, 150):
        if not re.search(rf"\b{n}\b[^\n]*(?://|/\*)[^\n]*7\.15[^\n]*910", raw):
            problems.append(f"LogFollow.tsx 里常量 {n} 的那一行应带注释「UI 文档 7.15 :910」")
    if "aria-live" in code:
        problems.append("LogFollow.tsx 不设 aria-live")
    fail_if(problems, "LogFollow.tsx 的源码规则")


def test_s3_d05_diff_text_goes_through_strip_ansi_only():
    """S3 / D05（合同公共约定）：来自补丁的文字显示前用 T007 的 stripAnsi（evidence/ansi），不自己再写一份：DiffView.tsx 与 diff/ 下的源码里
    不出现 ESC 的正则或字面量（\\u001b、\\x1b、\\u009b）；不新增 evidence/ 下的文件由范围门禁证明。"""
    need_new_sources()
    problems = []
    for path in diff_component_sources():
        code = strip_ts_comments(_read(path))
        if re.search(r"\\u001b|\\x1b|\\u009b|\\x9b|\\033", code, re.I):
            problems.append(f"{path.relative_to(WEB).as_posix()} 自己写了 ANSI 转义的处理，应复用 evidence/ansi 的 stripAnsi")
    fail_if(problems, "stripAnsi 的复用")


def test_s3_d04_diff_view_source_rules():
    """S3 / D04（合同公共约定）：DiffView.tsx 的 id 用 React 18 的 useId；折叠时主体用 hidden 属性（元素始终在）；
    不可信文字不进 dangerouslySetInnerHTML 之类（禁用词另查）；不调用 Math.random 或 Date 拼 id。"""
    need_new_sources()
    code = strip_ts_comments(_read(REPO_ROOT / f"{COMP_REL}/DiffView.tsx"))
    problems = []
    if "useId" not in code:
        problems.append("DiffView.tsx 的 id 应用 useId")
    if not re.search(r"\bhidden\b", code):
        problems.append("DiffView.tsx 折叠时主体应带 hidden 属性")
    if re.search(r"Math\.random|Date\.now|new Date", code):
        problems.append("DiffView.tsx 不该用 Math.random 或 Date 拼 id")
    fail_if(problems, "DiffView.tsx 的源码规则")


def test_s4_d02_d03_d06_diff_view_css_values():
    """S4 / D02、D03、D06（合同 §2 样式）：DiffView.css 的取值——根 --tt-surface-1、1px --tt-border、--tt-radius-lg、overflow hidden；
    工具栏 flex 可换行居中、间距与内边距 --tt-space-2 与 --tt-space-3、下边框；摘要 --tt-text-sm、--tt-text-2；计数 success-fg 与 danger-fg；
    文件列表宽 260、flex none、右边框、内边距 --tt-space-1、纵向、间距 --tt-space-0_5、无列表符；列表项宽 100%、最小高 32、当前项 --tt-surface-selected、
    悬停 --tt-surface-3；路径 rtl 与里层 ltr + unicode-bidi isolate；文件区；文件卡片；文件头高 36、内边距、折叠时无下边框、二进制左内边距 40；
    折叠钮 24（特异性高于 IconButton 单类规则）；说明文字内边距；行 --tt-mono-md；统一 44px 44px 18px minmax(0, 1fr) 与最小宽 560；
    分屏 44px 18px minmax(0, 1fr) 44px 18px minmax(0, 1fr) 与最小宽 760；换行关 white-space pre 与表格 width max-content、min-width 100%，
    换行开 pre-wrap 与 word-break break-all；add、del、hunk、empty 的底色令牌；hunk 文字 --tt-text-3；行号、符号（居中、字重 600）、eof；底部条。"""
    need_new_sources()
    css = _read(REPO_ROOT / f"{COMP_REL}/DiffView.css")
    fail_if(group_problems(css, "DiffView.css", DIFF_SPECS) + diff_css_extra_problems(css), "DiffView.css")


def test_s4_d07_log_follow_css_values():
    """S4 / D07（合同 §3 样式）：LogFollow.css 的取值——跟随主体 max-height 480、overflow-y auto，选择器特异性高于 .tt-viewer__body 的 (0,1,0)
    （.tt-log .tt-log__body）；过滤框外层 position relative、flex 0 1 360px、min-width 200；图标 absolute、left 10、top 9、--tt-text-3；
    输入框宽 100%、高 32、内边距右 --tt-space-2 左 --tt-space-8、1px --tt-border-strong、--tt-radius-md、--tt-surface-1、--tt-text-1、--tt-text-sm；
    跟随 inline-flex、与过滤框间距 --tt-space-2；底部状态 flex 居中、间距 --tt-space-2、内边距、上边框；following、off、disabled 用 --tt-surface-2、
    --tt-text-3、--tt-text-caption；paused 用 --tt-tone-neutral-bg、--tt-tone-neutral-fg、--tt-text-sm；按钮靠右。"""
    need_new_sources()
    css = _read(REPO_ROOT / f"{COMP_REL}/LogFollow.css")
    fail_if(group_problems(css, "LogFollow.css", LOG_SPECS) + log_css_extra_problems(css), "LogFollow.css")


def test_s5_d12_new_css_tokens_and_px_comments():
    """S5 / D12（合同公共约定）：DiffView.css、LogFollow.css、showcase-diff.css 里层级、圆角、阴影、字体只用 --tt-* 令牌；
    除 0 与 1px 外的 px 字面量同一行带出处注释（组件 CSS 写 handoff 行号、画布简称加行号或规划端定；演示 CSS 写「演示自定」或出处）。"""
    need_new_sources()
    problems = []
    for rel in (f"{COMP_REL}/DiffView.css", f"{COMP_REL}/LogFollow.css"):
        raw = _read(REPO_ROOT / rel)
        problems += token_only_problems(rel.rsplit("/", 1)[-1], raw)
        problems += component_css_note_problems(rel.rsplit("/", 1)[-1], raw)
    show = _read(REPO_ROOT / f"{SHOW_REL}/showcase-diff.css")
    problems += token_only_problems("showcase-diff.css", show) + showcase_px_note_problems("showcase-diff.css", show)
    fail_if(problems, "新 CSS 的令牌与出处注释")


def test_s5_d12_w4_pitfalls_in_new_sources():
    """S5 / D12（合同公共约定 W4 的坑）：本片所有新源码与 CSS 里不出现井号加 3/4/6/8 位十六进制字符、rgb( 之类颜色函数名加括号，
    不拼接 --tt- 令牌名（token-contract.mjs 只剥块注释、字符串也扫）。流水线里的 check:contract 另跑真实检查。"""
    need_new_sources()
    fail_if(w4_pitfall_problems([REPO_ROOT / rel for rel in NEW_SOURCE_FILES]), "W4 的坑")


def test_s6_d09_text_viewer_declares_six_optional_props():
    """S6 / D09（合同 §4，站主 Q1 选甲）：TextViewer.tsx 的 TextViewerProps 里有 6 个可选属性 bodyRef、onBodyScroll、bodyClassName、
    headerExtra、bottomBar、filter（都带问号）；已有属性仍在；LogFollow.tsx 用这 6 个属性中的 bodyRef、onBodyScroll、bodyClassName、
    headerExtra、bottomBar、filter 接自己的处理。"""
    need_new_sources()
    tv = strip_ts_comments(_read(need_file(f"{COMP_REL}/TextViewer.tsx")))
    props = re.search(r"export\s+interface\s+TextViewerProps\s*\{(.*?)\n\}", tv, re.S)
    assert props, "TextViewer.tsx 里找不到 export interface TextViewerProps"
    body = props.group(1)
    problems = []
    for name in ("bodyRef", "onBodyScroll", "bodyClassName", "headerExtra", "bottomBar", "filter"):
        if not re.search(rf"\b{name}\?\s*:", body):
            problems.append(f"TextViewerProps 里应有可选属性 {name}?")
    for name in ("title", "pages", "hasMore", "onLoadMore", "loadingMore", "changed", "onReload", "onCopy",
                 "defaultLineNumbers", "defaultWrap", "className"):
        if not re.search(rf"\b{name}\??\s*:", body):
            problems.append(f"TextViewerProps 里原有的 {name} 不见了")
    log = strip_ts_comments(_read(REPO_ROOT / f"{COMP_REL}/LogFollow.tsx"))
    for name in ("bodyRef", "onBodyScroll", "bodyClassName", "headerExtra", "bottomBar", "filter"):
        if not re.search(rf"\b{name}\b", log):
            problems.append(f"LogFollow.tsx 没有用到 TextViewer 的 {name}")
    fail_if(problems, "TextViewer 的可选属性")


def test_s6_q2_diff_showcase_conventions():
    """S6 / D11（合同 §6，站主 Q2）：DiffShowcase.tsx 默认导出一个组件，复用 App.css 的 showcase__section 与 showcase__h2 类，两节的 data-demo 是
    diff-view 与 log-follow，引入 ./showcase-diff.css；不引用 App.css；陈列页收进的名单不写死（不 import 其他演示）；
    定时追加用 setInterval 且卸载时 clearInterval；演示文字里不出现主题按钮的字样（亮、暗、跟随系统）作为按钮文字的由 P9 探针查。"""
    need_new_sources()
    raw = _read(REPO_ROOT / f"{SHOW_REL}/DiffShowcase.tsx")
    code = strip_ts_comments(raw)
    problems = []
    if not re.search(r"export\s+default\b", code):
        problems.append("DiffShowcase.tsx 应默认导出一个组件")
    for word in ("showcase__section", "showcase__h2", 'data-demo="diff-view"', 'data-demo="log-follow"'):
        if word not in code and word.replace('"', "'") not in code:
            problems.append(f"DiffShowcase.tsx 里没有 {word}")
    if not re.search(r"""import\s+['"]\./showcase-diff\.css['"]""", code):
        problems.append("DiffShowcase.tsx 应 import './showcase-diff.css'")
    if re.search(r"""App\.css|FormsShowcase|EvidenceShowcase""", code):
        problems.append("DiffShowcase.tsx 不该引用 App.css 或别的演示（陈列页收进的名单不写死）")
    if "setInterval" not in code or "clearInterval" not in code:
        problems.append("DiffShowcase.tsx 的定时追加应用 setInterval，并在卸载与停止时 clearInterval")
    fail_if(problems, "DiffShowcase 的约定")


def test_d14_executor_tests_in_place():
    """D14（合同“执行端测试”）：7 份执行端测试都在（diff-parse、diff-view、diff-css、log-follow、diff-showcase、diff-static、text-viewer-slots），
    各至少一条用例，不出现 skip、only、todo、fails。"""
    fail_if(executor_test_problems(), "执行端的测试文件")


# ---------------------------------------------------------------------------
# P 系列：流水线断言
# ---------------------------------------------------------------------------

def test_d13_p1_pipeline_steps_pass(pipeline):
    """P1 / D13（守卫）：npm ci、npm run build、npm test、npm run check:contract（W4）都退出 0；npm test 有通过的用例，
    没有失败、跳过、待办；Test Files 行没有失败。"""
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    step = pipeline.steps["npm test"]
    out = step.out
    assert re.search(r"Tests\s+(?:.*\|\s*)?\d+ passed", out), f"npm test 输出里没有 'Tests … N passed'：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", out), f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert re.search(r"Test Files\s+\d+ passed", out) and not re.search(r"Test Files\s+.*\bfailed\b", out), \
        f"npm test 的 Test Files 行异常：\n{step.tail}"


def test_d01_probe_parse_diff(pipeline):
    """parse 探针 / D01、D03（P2）：三个文件的顺序、路径、状态、计数、片段头、行的 kind 与行号逐项对；新文件 added（--- /dev/null、@@ -0,0 +1,3 @@、
    新行号 1 到 3），删除 deleted，改名 renamed（纯改名与带片段），二进制两种写法（Binary files；GIT binary patch 加 literal 块，整块含像片段头的行都跳过，
    后面的文件照常）；No newline 标记不计数、不推进行号、记在上一行；CRLF 与 LF 结果逐项相同；以 ---、+++ 开头的内容行分别算删除、新增；
    @@ -1 +1 @@ 行数缺省为 1，多个片段各自从片段头起算；引号路径的 C 风格还原与八进制 UTF-8；R4 的路径回退；空串与乱码返回空列表；
    R10 的病态输入各在 2 秒内；splitPairs 的配对行数。"""
    assert_probe_ok(pipeline, "parse")


def test_d02_d04_d06_probe_diff_view(pipeline):
    """view 探针 / D02–D06（P3、P4、P5）：根、工具栏、摘要整段文字、分段选择、开关、tt-stack-narrow、文件列表；统一视图的行序、data-kind、两列行号、加号与 −、
    片段头整行文字；文件头的路径、注记、计数；文件列表的计数、title、两层 span、当前项；折叠（新文件缺省折叠、主体 hidden、注记）、aria-controls、
    aria-labelledby、id 不重复；点列表项设为当前、展开、焦点到头；patch 变化后折叠按序号加路径保持、当前文件越界回第一个；改名、二进制、只改权限；
    没读完与 [继续加载]；没有文件；切模式与换行不重置折叠与当前文件；分屏配对（两删三加得三行、左 empty）、两侧行号、片段头一格占满；
    No newline 的 eof 注记；W1 同款：脚本、图片、ANSI、网址只是文字，路径除文字外只在 title。"""
    assert_probe_ok(pipeline, "view")


def test_d07_probe_log_follow_state_machine(pipeline):
    """follow 探针 / D07（P6，假计时器，主体打桩 scrollHeight、clientHeight、scrollTop）：挂载与 following 中追加页后滚到底；往上滚且 d > 40 暂停；
    往上滚但 d ≤ 40 不暂停；scrollTop 没变小（内容变长）时不暂停；paused 中追加页不滚动；d 为 40 时 149ms 仍 paused、150ms 恢复并滚到底；
    d 为 41 时仍 paused；第二次滚动重新计时；[回到底部] 立即恢复、焦点到开关；开关关 off、开 following；原因非空 disabled（开关 aria-disabled 不可聚焦、
    title 与底部文字都是原因、追加不滚），变回空 following；四种状态的文字与 data-follow；过滤变化后滚到底；卸载后没有挂起的计时器。"""
    assert_probe_ok(pipeline, "follow")


def test_d08_probe_log_filter(pipeline):
    """filter 探针 / D08（P7）：不分大小写；拼好分片、去掉 ANSI（含被页边界切开的）后匹配；隐藏行不显示；行号不变；没有匹配时的提示；清空后还原；
    复制只含显示的行；「已显示 N 页」不变；行尾 [继续加载] 跟着那一行，那一行被滤掉时不显示，底栏的照常。"""
    assert_probe_ok(pipeline, "filter")


def test_d09_probe_text_viewer_slots(pipeline):
    """slots 探针 / D09（P8，甲）：不传 6 个属性时 DOM 结构同 T007（三个孩子、class 不变、与全传 undefined 逐字相同）；bodyRef（对象与回调）指向
    div.tt-viewer__body；onBodyScroll 收到该元素的 scroll；bodyClassName 在该元素上；headerExtra 在头部、复制钮之后；bottomBar 在主体与底栏之间、
    不在主体里；filter 按规则过滤且不改行号；六个一起传不互相干扰。"""
    assert_probe_ok(pipeline, "slots")


def test_transitional_p9_diff_showcase_probe(pipeline):
    """陈列页的演示改版（整理陈列页或换成真实页面）时推翻。

    P9 / D11：探针直接渲染 DiffShowcase（不依赖根 App）：两节 data-demo 依次为 diff-view、log-follow，不与已有的 23 个重复，每节一个 h2.showcase__h2
    （标题不含 Button）；没有 role=status、对话框、菜单；没有文字的按钮都有 aria-label，按钮文字不含「亮」「暗」「跟随系统」；diff-view 一节有改动文件
    （两个片段）、新文件（缺省折叠）、删除的文件（含 -- 开头的删除行）、改名、二进制、2000 字符以上的超长行、No newline 标记；W1 样例在 DOM 里只是文字；
    log-follow 一节有 LogFollow、隐藏行说明、第 1/2 与 2/2 片；挂载后没有计时器，[开始追加] 每 400ms 追加一行，[停止追加] 停下，追加到上限自己停，
    卸载后计时器清空；[模拟 attempt 已结束] 切换 disabled 与原因；复制的三种结果文字，不用轻提示。
    另外 App.tsx 现在不引用 DiffShowcase（演示不挂到陈列页，T006 落地后才自动收进）。"""
    need_new_sources()
    app = _read(need_file(f"{SRC_REL}/App.tsx"))
    assert "DiffShowcase" not in app, "App.tsx 不该引用 DiffShowcase（合同：不挂到陈列页）"
    assert_probe_ok(pipeline, "showcase")


def test_p10_d13_worktree_unchanged_by_pipeline(pipeline):
    """P10 / D13（守卫）：流水线与探针前后 git status 相同；package.json、锁文件、index.html、vite.config.ts、tsconfig.json、tokens.css、
    fonts.css、base.css、main.tsx、App.tsx、App.css、TextViewer.tsx、TextViewer.css 的摘要不变；gate-probe/ 没有留下。"""
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

GOOD_DIFF_CSS = """
/* 差异视图 */
.tt-diff { background: var(--tt-surface-1); border: 1px solid var(--tt-border); border-radius: var(--tt-radius-lg); overflow: hidden; }
.tt-diff__bar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--tt-space-2) var(--tt-space-3); padding: var(--tt-space-2) var(--tt-space-3); border-bottom: 1px solid var(--tt-border); }
.tt-diff__summary { display: inline-flex; align-items: center; gap: var(--tt-space-2); font: var(--tt-text-sm); color: var(--tt-text-2); }
.tt-diff__summary-title { font: var(--tt-mono-sm); }
.tt-diff__plus { color: var(--tt-tone-success-fg); }
.tt-diff__minus { color: var(--tt-tone-danger-fg); }
.tt-diff__bar .tt-seg { margin-left: auto; }
.tt-diff__main { display: flex; }
.tt-diff__files { flex: none; width: 260px; /* handoff :149 */ margin: 0; padding: var(--tt-space-1); border-right: 1px solid var(--tt-border); display: flex; flex-direction: column; gap: var(--tt-space-0_5); list-style: none; }
.tt-diff__file-item { width: 100%; min-height: 32px; /* 详情页 :401 */ display: flex; align-items: center; gap: var(--tt-space-2); padding: var(--tt-space-1) var(--tt-space-2); border: none; border-radius: var(--tt-radius-md); background: transparent; color: var(--tt-text-1); text-align: left; }
.tt-diff__file-item[aria-current="true"] { background: var(--tt-surface-selected); }
.tt-diff__file-item:hover { background: var(--tt-surface-3); }
.tt-diff__file-path { flex: 1; min-width: 0; font: var(--tt-mono-sm); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; direction: rtl; text-align: left; }
.tt-diff__file-path > span { direction: ltr; unicode-bidi: isolate; }
.tt-diff__binary-tag { font: var(--tt-text-caption); color: var(--tt-text-3); }
.tt-diff__content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: var(--tt-space-3); padding: var(--tt-space-3); }
.tt-diff__file { border: 1px solid var(--tt-border); border-radius: var(--tt-radius-md); overflow: hidden; }
.tt-diff__file-head { display: flex; align-items: center; gap: var(--tt-space-2); height: 36px; /* 规划端定 */ padding: 0 var(--tt-space-1) 0 var(--tt-space-2); background: var(--tt-surface-2); border-bottom: 1px solid var(--tt-border); }
.tt-diff__file[data-collapsed="true"] .tt-diff__file-head { border-bottom: none; }
.tt-diff__file[data-binary="true"] .tt-diff__file-head { padding-left: 40px; /* 详情页 :458 */ }
.tt-diff__file-head .tt-icon-btn { width: 24px; height: 24px; /* 详情页 :408 */ border-radius: var(--tt-radius-sm); }
.tt-diff__file-name { flex: 1; min-width: 0; font: var(--tt-mono-sm); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tt-diff__file-note { font: var(--tt-text-caption); color: var(--tt-text-3); }
.tt-diff__file-body { overflow-x: auto; }
.tt-diff__placeholder, .tt-diff__empty { padding: var(--tt-space-3) var(--tt-space-4); font: var(--tt-text-sm); color: var(--tt-text-3); }
.tt-diff__table { width: max-content; min-width: 100%; }
.tt-diff__row { font: var(--tt-mono-md); }
.tt-diff[data-mode="unified"] .tt-diff__row { display: grid; grid-template-columns: 44px 44px 18px minmax(0, 1fr); min-width: 560px; /* handoff :149 */ }
.tt-diff[data-mode="split"] .tt-diff__row { display: grid; grid-template-columns: 44px 18px minmax(0, 1fr) 44px 18px minmax(0, 1fr); min-width: 760px; /* handoff :149 */ }
.tt-diff__text { white-space: pre; padding-right: var(--tt-space-3); }
.tt-diff[data-mode="split"] .tt-diff__text { padding-right: var(--tt-space-2); }
.tt-diff[data-wrap="true"] .tt-diff__text { white-space: pre-wrap; word-break: break-all; }
.tt-diff__row[data-kind="add"] { background: var(--tt-diff-add); }
.tt-diff__row[data-kind="del"] { background: var(--tt-diff-del); }
.tt-diff__row[data-kind="hunk"] { background: var(--tt-surface-2); color: var(--tt-text-3); }
.tt-diff[data-mode="split"] .tt-diff__row[data-kind="hunk"] { padding-left: var(--tt-space-3); white-space: pre; }
.tt-diff__row [data-kind="add"] { background: var(--tt-diff-add); }
.tt-diff__row [data-kind="del"] { background: var(--tt-diff-del); }
.tt-diff__row [data-kind="empty"] { background: var(--tt-surface-2); }
.tt-diff__row [data-side="left"].tt-diff__text { border-right: 1px solid var(--tt-border); }
.tt-diff__no { text-align: right; padding-right: var(--tt-space-2); color: var(--tt-text-3); user-select: none; }
.tt-diff[data-mode="unified"] .tt-diff__no:nth-child(2) { border-right: 1px solid var(--tt-border); }
.tt-diff__sign { text-align: center; font-weight: 600; user-select: none; }
.tt-diff__row[data-kind="add"] .tt-diff__sign { color: var(--tt-tone-success-fg); }
.tt-diff__row[data-kind="del"] .tt-diff__sign { color: var(--tt-tone-danger-fg); }
.tt-diff__eof { color: var(--tt-text-3); margin-left: var(--tt-space-1); user-select: none; }
.tt-diff__foot { display: flex; align-items: center; background: var(--tt-surface-2); border-top: 1px solid var(--tt-border); padding: var(--tt-space-2) var(--tt-space-3); font: var(--tt-text-caption); color: var(--tt-text-3); }
.tt-diff__foot .tt-btn { margin-left: auto; }
"""

GOOD_LOG_CSS = """
.tt-log .tt-log__body { max-height: 480px; /* 规划端定 */ overflow-y: auto; }
.tt-log__filter { position: relative; flex: 0 1 360px; /* 详情页 :636 */ min-width: 200px; /* 详情页 :636 */ }
.tt-log__filter svg { position: absolute; left: 10px; top: 9px; /* 详情页 :638 */ color: var(--tt-text-3); }
.tt-log__filter-input { width: 100%; height: 32px; /* 详情页 :639 */ padding: 0 var(--tt-space-2) 0 var(--tt-space-8); border: 1px solid var(--tt-border-strong); border-radius: var(--tt-radius-md); background: var(--tt-surface-1); color: var(--tt-text-1); font: var(--tt-text-sm); }
.tt-log__follow { display: inline-flex; margin-left: var(--tt-space-2); }
.tt-log__status { display: flex; align-items: center; gap: var(--tt-space-2); padding: var(--tt-space-2) var(--tt-space-3); border-top: 1px solid var(--tt-border); background: var(--tt-surface-2); color: var(--tt-text-3); font: var(--tt-text-caption); }
.tt-log__status[data-follow="paused"] { background: var(--tt-tone-neutral-bg); color: var(--tt-tone-neutral-fg); font: var(--tt-text-sm); }
.tt-log__status .tt-btn { margin-left: auto; }
"""

GOOD_ICONS = """import type { ReactNode, SVGProps } from 'react';
function Svg() {}
export const EyeOffIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="m2 2 20 20" />
  </Svg>
);

// 第 7 片（T008）新增的三个图标，路径照画布。
export const PauseIcon = (props: IconProps) => (
  <Svg {...props}>
    <rect width="4" height="14" x="6" y="5" rx="1" />
    <rect width="4" height="14" x="14" y="5" rx="1" />
  </Svg>
);

export const FilterIcon = (props: IconProps) => (
  <Svg {...props}>
    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
  </Svg>
);

export const FileDiffIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
    <path d="M9 10h6" />
    <path d="M12 13V7" />
    <path d="M9 17h6" />
  </Svg>
);
"""

GOOD_INDEX = """// 统一导出组件，共五片：
""" + "\n".join(
    f"export {{ {n} }} from './{n}';\nexport type {{ {n}Props }} from './{n}';"
    for n in ("Button", "Tag", "StatusTag", "Card", "Banner", "IconButton", "Tooltip", "Menu", "Dialog", "Drawer", "Toast",
              "SegmentedControl", "Switch", "Checkbox", "Tabs", "TextField", "Select", "Table", "KeyValueList", "EmptyState",
              "Skeleton", "ConnectionPill", "Breadcrumb", "TextViewer", "SafeMarkdown", "EffortPair", "MaskedValue", "CommandLine",
              "NextStep")
) + """
export { isMaskedPlaceholder } from './MaskedValue';
export { dispatchCommand } from './CommandLine';
// 第 7 片：差异视图（7.14）与日志跟随（7.15）
export { DiffView } from './DiffView';
export type { DiffViewProps } from './DiffView';
export { LogFollow } from './LogFollow';
export type { LogFollowProps } from './LogFollow';
"""


def test_gate_selfcheck_css_samples_pass_and_mutants_fail():
    """门禁自检：按合同写出的参考 CSS（DiffView、LogFollow）通过全部 CSS 检查；把关键取值改坏后检查会报问题。"""
    assert group_problems(GOOD_DIFF_CSS, "d", DIFF_SPECS) == []
    assert diff_css_extra_problems(GOOD_DIFF_CSS) == []
    assert group_problems(GOOD_LOG_CSS, "l", LOG_SPECS) == []
    assert log_css_extra_problems(GOOD_LOG_CSS) == []
    assert component_css_note_problems("d", GOOD_DIFF_CSS) == []
    assert component_css_note_problems("l", GOOD_LOG_CSS) == []
    assert token_only_problems("d", GOOD_DIFF_CSS) == [] and token_only_problems("l", GOOD_LOG_CSS) == []
    mutants = [
        ("width: 260px;", "width: 240px;"),
        ("direction: rtl;", ""),
        ("unicode-bidi: isolate;", ""),
        ("height: 36px;", "height: 40px;"),
        ("width: 24px; height: 24px;", "width: 28px; height: 28px;"),
        ("grid-template-columns: 44px 44px 18px minmax(0, 1fr); min-width: 560px;", "grid-template-columns: 44px 44px 18px 1fr; min-width: 560px;"),
        ("min-width: 760px;", "min-width: 720px;"),
        ("min-width: 560px;", "min-width: 500px;"),
        ("word-break: break-all;", ""),
        ("white-space: pre-wrap;", "white-space: normal;"),
        ("width: max-content; min-width: 100%;", "width: 100%;"),
        (".tt-diff__row[data-kind=\"hunk\"] { background: var(--tt-surface-2); color: var(--tt-text-3); }",
         ".tt-diff__row[data-kind=\"hunk\"] { background: var(--tt-surface-2); color: var(--tt-text-2); }"),
        ("font-weight: 600;", "font-weight: 700;"),
        (".tt-diff__row [data-kind=\"empty\"] { background: var(--tt-surface-2); }", ".tt-diff__row [data-kind=\"empty\"] { background: transparent; }"),
        (".tt-diff__file-item[aria-current=\"true\"] { background: var(--tt-surface-selected); }",
         ".tt-diff__file-item[aria-current=\"true\"] { background: var(--tt-surface-3); }"),
        ("border-bottom: none; }", "border-bottom: 1px solid var(--tt-border); }"),
        (".tt-diff__file-head .tt-icon-btn {", ".tt-icon-btn.x {"),
        ("padding-left: 40px;", "padding-left: 36px;"),
        ("min-height: 32px;", "min-height: 28px;"),
        ("padding-right: var(--tt-space-2); color: var(--tt-text-3); user-select: none;", "padding-right: var(--tt-space-3); color: var(--tt-text-3); user-select: none;"),
        ("overflow: hidden; }\n.tt-diff__bar", "overflow: visible; }\n.tt-diff__bar"),
    ]
    for old, new in mutants:
        assert old in GOOD_DIFF_CSS, old
        bad = GOOD_DIFF_CSS.replace(old, new, 1)
        assert group_problems(bad, "d", DIFF_SPECS) + diff_css_extra_problems(bad), f"改坏后没被发现：{old!r} → {new!r}"
    for token in ("var(--tt-diff-add)", "var(--tt-diff-del)", "var(--tt-tone-success-fg)", "var(--tt-tone-danger-fg)"):
        bad = GOOD_DIFF_CSS.replace(token, "var(--tt-text-1)")
        assert group_problems(bad, "d", DIFF_SPECS), f"{token} 全部换掉后没被发现"
    log_mutants = [
        (".tt-log .tt-log__body {", ".tt-log__body {"),
        ("max-height: 480px;", "max-height: 400px;"),
        ("overflow-y: auto;", ""),
        ("flex: 0 1 360px;", "flex: 0 1 300px;"),
        ("left: 10px;", "left: 12px;"),
        ("padding: 0 var(--tt-space-2) 0 var(--tt-space-8);", "padding: 0 var(--tt-space-2);"),
        ("var(--tt-tone-neutral-bg)", "var(--tt-tone-info-bg)"),
        ("font: var(--tt-text-caption); }", "font: var(--tt-text-sm); }"),
        ("margin-left: var(--tt-space-2); }", "}"),
    ]
    for old, new in log_mutants:
        assert old in GOOD_LOG_CSS, old
        bad = GOOD_LOG_CSS.replace(old, new, 1)
        assert group_problems(bad, "l", LOG_SPECS) + log_css_extra_problems(bad), f"改坏后没被发现：{old!r} → {new!r}"
    assert component_css_note_problems("d", ".a { width: 20px; }")
    assert component_css_note_problems("d", ".a { width: 20px; } /* 演示自定 */")
    assert component_css_note_problems("d", ".a { width: 20px; } /* 规划端定 */") == []
    assert showcase_px_note_problems("s", ".a { width: 240px; } /* 演示自定 */") == []
    assert showcase_px_note_problems("s", ".a { width: 240px; }")
    assert showcase_px_note_problems("s", ".a { width: 240px; } /* 随便写写 */")


def test_gate_selfcheck_helpers():
    """门禁自检：特异性计算器、padding 四边解析、px 注释检查、令牌检查、W4 的坑、禁用词、HasAll、look。"""
    assert specificity(".tt-log .tt-log__body") == (0, 2, 0)
    assert specificity(".tt-viewer__body") == (0, 1, 0)
    assert specificity(".tt-diff__file-head .tt-icon-btn") == (0, 2, 0)
    assert specificity(".tt-icon-btn") == (0, 1, 0)
    assert specificity(".tt-diff[data-mode=\"split\"] .tt-diff__row[data-kind=\"hunk\"]") == (0, 4, 0)
    assert specificity(":where(.a) b") == (0, 0, 1)
    sides = box_sides([("padding", "0 var(--tt-space-2) 0 var(--tt-space-3)")], "padding")
    assert sides == {"top": "0", "right": "var(--tt-space-2)", "bottom": "0", "left": "var(--tt-space-3)"}
    assert box_sides([("padding", "1px var(--tt-space-1)")], "padding")["left"] == "var(--tt-space-1)"
    assert box_sides([("padding", "4px"), ("padding-left", "9px")], "padding")["left"] == "9px"
    assert px_literal_problems("x", ".a { width: 20px; } /* 出处 */") == []
    assert px_literal_problems("x", ".a { width: 20px; }")
    assert px_literal_problems("x", ".a { width: 1px; margin: 0; }") == []
    assert token_only_problems("x", ".a { border-radius: var(--tt-radius-md); font: var(--tt-text-sm); z-index: var(--tt-z-popover); }") == []
    assert token_only_problems("x", ".a { border-radius: 4px; }")
    assert token_only_problems("x", ".a { font: 13px/20px sans-serif; }")
    assert token_only_problems("x", ".a { box-shadow: 0 1px 2px black; }")
    assert forbidden_word_problems([]) == []
    assert [m.group(0) for m in HEX_RE.finditer("a #fff b #abcd c #12345 d #1234567 e #12345678")] == ["#fff", "#abcd", "#12345678"]
    assert COLOR_FUNC_RE.search("x rgb(1,2,3)") and COLOR_FUNC_RE.search("color (srgb)") and not COLOR_FUNC_RE.search("a color\n(b)")
    decls = [("gap", "var(--tt-space-2) var(--tt-space-3)")]
    assert HasAll("gap", S2, S3)(decls) and not HasAll("gap", S2, S4)(decls) and HasAll(("row-gap", "column-gap"), S2, S3)(
        [("row-gap", S2), ("column-gap", S3)])
    assert re.search(look("data-kind.{0,4}add"), '.tt-diff__row[data-kind="add"]')
    assert not re.search(look("data-kind.{0,4}add"), '.tt-diff__row[data-kind="del"]')
    assert re.search(look("add", "sign"), '.tt-diff__row[data-kind="add"] .tt-diff__sign')
    assert not re.search(look("add", "sign"), '.tt-diff__row[data-kind="add"] .tt-diff__text')
    assert re.search(look("text|data-side"), '.tt-diff[data-mode="split"] .tt-diff__text')
    assert rules_with_specificity_above(".tt-log .tt-log__body { max-height: 480px; }", r"tt-log__body", [C("max-height", eq="480px")], (0, 1, 0))
    assert not rules_with_specificity_above(".tt-log__body { max-height: 480px; }", r"tt-log__body", [C("max-height", eq="480px")], (0, 1, 0))
    assert [m.group(0) for m in re.finditer(r"\bdata-demo\b", "data-demo x")] == ["data-demo"]


def test_gate_selfcheck_baseline_constants_match_the_baseline_commit():
    """门禁自检：components/index.ts 与 icons/index.tsx 的基线字节数与 sha256 常量，和基线提交 2b6563ef70 里的内容一致（该提交取得到时才核对）；
    append_only_problems 放得过“基线加末尾追加”、拦得住改动已有行和变短。"""
    for rel, (size, digest) in BASELINE_APPEND_ONLY.items():
        proc = git("cat-file", "-p", f"2b6563ef706ab0d926f304d2e030ee59d739a342:{rel}")
        if proc.returncode != 0:
            continue
        data = proc.stdout.replace(b"\r\n", b"\n")
        assert len(data) == size and hashlib.sha256(data).hexdigest() == digest, f"{rel} 的基线常量与提交里的内容不一致"
        text = data.decode("utf-8")
        assert append_only_problems(rel, text + "// x\n") == []
        assert append_only_problems(rel, (text + "// x\n").replace("\n", "\r\n")) == []
        assert append_only_problems(rel, text)
        assert append_only_problems(rel, "// 改了文件头\n" + text + "// x\n")
        assert append_only_problems(rel, text[:-20] + "// x\n")
    assert append_only_problems(f"{COMP_REL}/index.ts", "短")


def test_gate_selfcheck_icon_index_and_source_checks():
    """门禁自检：图标解析放得过合同写明的写法，拦得住路径写错、rect 属性写错、points 写错、自己写 fill；index.ts 参考样本通过，
    漏导出、写 overlay、导出内部函数、改了文件头都会报；LogFollow 常量注释与 stripAnsi 规则、role 与接口检查拦得住常见错误。"""
    assert icon_problems(GOOD_ICONS, check_prefix=False) == []
    assert icon_problems(GOOD_ICONS.replace("M12 13V7", "M12 13V8"), check_prefix=False)
    assert icon_problems(GOOD_ICONS.replace('width="4" height="14" x="14"', 'width="4" height="14" x="15"'), check_prefix=False)
    assert icon_problems(GOOD_ICONS.replace("22 3 2 3 10", "22 3 2 4 10"), check_prefix=False)
    assert icon_problems(GOOD_ICONS.replace("export const FilterIcon", "export const FilterIcom"), check_prefix=False)
    assert icon_problems(GOOD_ICONS.replace('<polygon points', '<polygon fill="none" points'), check_prefix=False)
    assert icon_problems(GOOD_ICONS.replace("路径照画布", "路径取自"), check_prefix=False)
    assert icon_problems(GOOD_ICONS.replace("<rect width=\"4\" height=\"14\" x=\"14\" y=\"5\" rx=\"1\" />", ""), check_prefix=False)
    assert index_problems(GOOD_INDEX, check_prefix=False) == []
    assert index_problems(GOOD_INDEX.replace("export { DiffView } from './DiffView';", ""), check_prefix=False)
    assert index_problems(GOOD_INDEX.replace("export type { LogFollowProps } from './LogFollow';", ""), check_prefix=False)
    assert index_problems(GOOD_INDEX.replace("export { TextViewer } from './TextViewer';", ""), check_prefix=False)
    assert index_problems(GOOD_INDEX + "export { Dialog as D } from './overlay/MountLayer';\n", check_prefix=False)
    assert index_problems(GOOD_INDEX + "export { parseDiff } from './diff/parseDiff';\n", check_prefix=False)
    assert index_problems(GOOD_INDEX.replace("共五片", "共七片"), check_prefix=False)
    assert index_problems(GOOD_INDEX.replace("第 7 片：差异视图（7.14）与日志跟随（7.15）", "第 7 片"), check_prefix=False)
    assert new_source_problems([]) == []
    assert role_and_interface_problems("x", "const a = <div role=\"status\" />;")
    assert role_and_interface_problems("x", "window.matchMedia('(x)')")
    assert role_and_interface_problems("x", "// matchMedia 只在注释里\nconst a = 1;") == []
    assert re.search(r"\b40\b[^\n]*(?://|/\*)[^\n]*7\.15[^\n]*910", "const NEAR_BOTTOM = 40; // 贴底阈值，UI 文档 7.15 :910")
    assert not re.search(r"\b40\b[^\n]*(?://|/\*)[^\n]*7\.15[^\n]*910", "const NEAR_BOTTOM = 40;\n// UI 文档 7.15 :910")
    assert not re.search(r"\b150\b[^\n]*(?://|/\*)[^\n]*7\.15[^\n]*910", "const T = 150; // 随便")


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


def test_gate_selfcheck_probe_templates():
    """门禁自检：每份探针都有用例，占位符都被替换；PROBE_ORDER 与 PROBE_SPECS 对得上，演示探针最后跑；探针里不写 skip、only、todo；
    括号配对；演示的 data-demo 常量与合同一致（本片 2 个，已有 23 个不重复）。"""
    assert set(PROBE_ORDER) == set(PROBE_SPECS) and PROBE_ORDER[-1] == "showcase"
    for key in PROBE_ORDER:
        source = build_probe_source(key)
        assert not re.search(r"__[A-Z_]+__", source), f"探针 {key} 里还有没替换的占位符"
        assert probe_count(source) >= 1, key
        assert not re.search(r"\.(skip|only|todo)\b|\bxit\(|\bxdescribe\(", source), key
        assert js_bracket_problems(source) == [], f"探针 {key} 的括号：{js_bracket_problems(source)}"
    assert js_bracket_problems("a(b[c{d}])") == [] and js_bracket_problems("a(b]") and js_bracket_problems("f('x)")
    assert js_bracket_problems("f('(' + \"]\" + `{`)") == []
    show = build_probe_source("showcase")
    for demo in DIFF_DEMOS:
        assert f'"{demo}"' in show
    assert len(EXISTING_DEMOS) == 23 and not set(DIFF_DEMOS) & set(EXISTING_DEMOS)
    assert sum(1 for name in dir(sys.modules[__name__]) if name.startswith("test_transitional_")) == 1


def test_gate_selfcheck_executor_test_checker(tmp_path, monkeypatch):
    """门禁自检：执行端测试检查对全部在位、无 skip 的样本通过；缺文件、没有用例、写了 skip / only / todo 都会报。"""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    for name in EXECUTOR_TESTS:
        (tests_dir / name).write_text("it('x', () => {});\n", encoding="utf-8")
    monkeypatch.setitem(globals(), "WEB", tmp_path)
    assert executor_test_problems() == []
    (tests_dir / EXECUTOR_TESTS[0]).write_text("it.skip('x', () => {});\n", encoding="utf-8")
    assert executor_test_problems()
    (tests_dir / EXECUTOR_TESTS[0]).write_text("describe('x', () => { it.only('y', () => {}); });\n", encoding="utf-8")
    assert executor_test_problems()
    (tests_dir / EXECUTOR_TESTS[0]).write_text("it.todo('x');\n", encoding="utf-8")
    assert executor_test_problems()
    (tests_dir / EXECUTOR_TESTS[0]).write_text("// 没有用例\n", encoding="utf-8")
    assert executor_test_problems()
    (tests_dir / EXECUTOR_TESTS[0]).unlink()
    assert executor_test_problems()
