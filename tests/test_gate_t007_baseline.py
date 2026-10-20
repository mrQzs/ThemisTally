"""T007 战前门禁：桌面端前端证据组件（第五片）的黑盒基准测试（合同 t007-desktop-evidence，plan_version 1）。

被测对象是 ``desktop/web/``：6 个新组件（文本查看器 TextViewer、安全 Markdown SafeMarkdown、思考档位 EffortPair、遮蔽值
MaskedValue、命令行 CommandLine、下一步 NextStep）与各自的 CSS、``components/evidence/`` 下 3 个内部纯函数模块（ansi.ts、
viewerLines.ts、markdown.ts）、3 个新图标（LockIcon、CopyIcon、EyeOffIcon）、Banner 的可选 action、T005 终审 S1–S6 与三处合同缺口
的修补、新演示 EvidenceShowcase（不挂到陈列页）。

基线（40ed8f5，T005 结项）上这些都还没有，所以本文件的“失败”断言落在目标文件不存在或内容不符上，不是导入、收集或语法错误：
模块级只导入标准库，用到被测文件的地方都在用例函数里读；候选里还没有任何新组件文件时，``pipeline`` 夹具不跑 npm（没有东西可测，
也省掉联网的 ``npm ci``），用到它的用例以断言失败写明原因。

结构（编号对应规划 §7.3 的 S1–S8、P1–P10；门禁端加了若干静态守卫和自检）：

- 静态断言（S 系列，不用流水线，全量 pytest 也跑）：读组件源码、CSS、``components/index.ts``、``icons/index.tsx``、演示的 CSS。
- 流水线断言（P 系列）：会话级夹具 ``pipeline`` 在 ``desktop/web`` 下按顺序跑 ``npm ci``、``npm run build``、``npm test``、
  ``npm run check:contract``，再把探针逐份写成 ``gate-probe/probe-<唯一标识>-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除；前后各取一次 ``git status``。组件探针（ansi、w1、pages、md、
  mdperf、effort、atoms、table、gaps）与演示探针（showcase）分开写、分开跑，演示探针最后跑。全量 pytest 默认跳过用到
  ``pipeline`` 的用例（``tests/conftest.py``），点名运行本文件时才跑。
- 门禁自检（``test_gate_selfcheck_*``，不依赖候选）：把检查函数喂给正确样本和改坏的样本。

DoD 对应（用例名里带 ``dNN``）：

- D01：S1、S5、ansi 探针、w1 探针；D02：pages 探针（分页、分片、隐藏行、409）；D03：md、mdperf 探针、S2、S3；
- D04：effort 探针、S5；D05、D06、D07：atoms 探针、S4、S5；D08：table 探针、S6；D09：gaps 探针；
- D10：S7（过渡）、S8；D11：showcase 探针（P9，过渡）；D12：S2、S3、S5、S8 与 W4（check:contract）；
- D13：P1（npm 四步）、P10（V02、V03 另证 T001–T005 门禁与桌面端状态表）；
- D14：执行端 8 份测试在位且不用 skip、only、todo；改动范围由调度器的范围门禁证明，这里不写相对基线的范围断言。

过渡断言（``test_transitional_`` 开头）：S7 与 P9 两条按任务书命名，陈列页的演示改版（整理陈列页或换成真实页面）时推翻；
除此之外不再有过渡断言（``test_transitional_`` 恰好两条）；showcase-evidence.css 的 px 注释、令牌、880px 的出处并入长期的 S8。
基线上仍存在的 5 条旧过渡断言（T003:945/:956/:1024、T004:1885、T005:3057）本文件既不改也不推翻。
其余（组件行为、CSS 取值、静态检查、S1–S3、S5、三处缺口、S6 的注释规则）都是长期断言。

写法约定：CSS 比较先归一空白；jsdom 不排版、不算层叠，宽、高、位置、层级、色调读 CSS 文件的文本，探针只看结构、焦点、
计时与属性；合同没有定类名的内部元素，CSS 断言用“有一条规则同时声明了这几项”的写法，不依赖类名（合同定了名字的
``tt-viewer``、``tt-effort``、``tt-cmd--sm``、``tt-banner__action`` 除外）；探针找行时从行号元素往上爬，不依赖行的类名；
悬停与聚焦的探针从 ``@testing-library/react`` 导入 ``fireEvent``；不写 skip、xfail、only、todo。

门禁做不到、留给人的项（合同 H1–H9）：H1 视觉（暗色、亮色各一次）；H2 真浏览器（复制进剪贴板、256 KiB 长行切换换行、
鼠标选中多行复制不带行号）；H3 表格吸顶下的焦点滚动与焦点环四边；H4 胶囊浮层不被裁；H5 Windows 高对比度；H6 读屏抽查；
H7 外壳接入后的链接确认与剪贴板；H8 大文档手感；H9 真浏览器里 W1 没有请求也没有 alert。
"""

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
EVID_REL = f"{COMP_REL}/evidence"
SHOW_REL = f"{SRC_REL}/showcase"
CANVAS_DOMAIN = REPO_ROOT / "docs" / "ui-design" / "pages" / "02-领域组件-Themis-Tally.html"

NEW_COMPONENTS = ("TextViewer", "SafeMarkdown", "EffortPair", "MaskedValue", "CommandLine", "NextStep")
EVIDENCE_MODULES = ("ansi", "viewerLines", "markdown")
OLD_COMPONENTS = ("Button", "Tag", "StatusTag", "Card", "Banner", "IconButton", "Tooltip", "Menu", "Dialog", "Drawer", "Toast",
                  "SegmentedControl", "Switch", "Checkbox", "Tabs", "TextField", "Select", "Table", "KeyValueList",
                  "EmptyState", "Skeleton", "ConnectionPill", "Breadcrumb")

# 合同第 13 条：七节的 data-demo（依次）；已有的 16 个（T003 的 5 个，T005 的 11 个）。
EVIDENCE_DEMOS = ("text-viewer", "text-viewer-jsonl", "safe-markdown", "effort", "masked-value", "command-line", "next-step")
EXISTING_DEMOS = ("icon-button", "menu", "dialog", "drawer", "toast",
                  "text-field", "form-dialog", "segmented", "switch-checkbox", "tabs", "table",
                  "key-value", "empty-state", "skeleton", "connection", "breadcrumb")

# 合同第 1 条：EyeOffIcon 四条 path（站主核实，与 Lucide 1.59.0 eye-off 一致）。
EYE_OFF_DS = [
    "M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49",
    "M14.084 14.158a3 3 0 0 1-4.242-4.242",
    "M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143",
    "m2 2 20 20",
]
LOCK_CONTRACT = {"rect": {"width": "18", "height": "11", "x": "3", "y": "11", "rx": "2", "ry": "2"},
                 "paths": ["M7 11V7a5 5 0 0 1 10 0v4"]}
COPY_CONTRACT = {"rect": {"width": "14", "height": "14", "x": "8", "y": "8", "rx": "2", "ry": "2"},
                 "paths": ["M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"]}

# 合同“公共约定”：静态检查禁用词（扫 desktop/web/src/**/*.{ts,tsx} 全文，含注释与字符串）。
FORBIDDEN_WORDS = ("dangerouslySetInnerHTML", "innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function",
                   "document.write", "srcdoc", "createContextualFragment", "DOMParser")
FORBIDDEN_CALLS = ("matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver")

# 执行端测试（合同“执行端测试”一节）。
EXECUTOR_TESTS = ("evidence-text-viewer.test.tsx", "evidence-markdown.test.tsx", "evidence-effort.test.tsx",
                  "evidence-atoms.test.tsx", "evidence-showcase.test.tsx", "evidence-static.test.ts",
                  "forms-patches.test.tsx", "forms-patches-css.test.ts")

# 夹具总预算留出余量给其余快测试（合同检查项 V01 的 timeout 是 2400s）。
PIPELINE_BUDGET = 1800
STEP_CAPS = {
    "npm ci": 300,
    "npm run build": 150,
    "npm test": 300,
    "npm run check:contract": 60,
    "probe": 150,
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


def comp_path(name, ext):
    return REPO_ROOT / COMP_REL / f"{name}.{ext}"


def need_components(*names, css=True):
    """用例开头先查组件文件在不在；缺哪个就以断言失败写明（基线上组件还不存在）。"""
    missing = []
    for name in names:
        for ext in (("tsx", "css") if css else ("tsx",)):
            if not comp_path(name, ext).is_file():
                missing.append(f"{COMP_REL}/{name}.{ext}")
    assert not missing, f"缺少组件文件（基线上还没有实现）：{missing}"


def comp_css(name):
    need_components(name)
    return _read(comp_path(name, "css"))


def comp_tsx(name):
    need_components(name)
    return _read(comp_path(name, "tsx"))


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


def values_of(decls, names):
    return [cv(v) for n, v in decls if n in names]


def C(names, eq=None, has=(), zero=False):
    """一条声明条件：names 里的某个属性，归一后的值等于 eq / 含 has 里每一段 / 是 0。"""
    if isinstance(names, str):
        names = (names,)
    return ("decl", tuple(names), eq, tuple(has), zero)


def AnyOf(*conds):
    return ("any", conds)


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
# 选择器特异性计算器（只为“.tt-cmd--sm .tt-icon-btn 压过 IconButton 单类规则”这一条用）
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


# ---------------------------------------------------------------------------
# 阴影解析（S6：表格行焦点环的单元格 inset 阴影）
# ---------------------------------------------------------------------------

def focus_shadow_edges(value):
    """一个 box-shadow 值里，颜色是 var(--tt-focus)、inset、无模糊的 2px 阴影各画哪条边：top/bottom/left/right/all。"""
    edges = set()
    for part in split_top(value, ","):
        toks = [t for t in split_top(part, " ") if t]
        if "inset" not in [t.lower() for t in toks]:
            continue
        if not any(cv(t) == "var(--tt-focus)" for t in toks):
            continue
        nums = []
        for t in toks:
            m = re.fullmatch(r"(-?\d*\.?\d+)(px)?", t.lower())
            if m:
                nums.append(float(m.group(1)))
        if len(nums) < 2:
            continue
        x, y = nums[0], nums[1]
        blur = nums[2] if len(nums) > 2 else 0.0
        spread = nums[3] if len(nums) > 3 else 0.0
        if blur != 0:
            continue
        if spread == 0:
            if x == 0 and y == 2:
                edges.add("top")
            elif x == 0 and y == -2:
                edges.add("bottom")
            elif y == 0 and x == 2:
                edges.add("left")
            elif y == 0 and x == -2:
                edges.add("right")
        elif x == 0 and y == 0 and spread == 2:
            edges.add("all")
    return edges


def table_focus_problems(css):
    problems = []
    rules = parse_rules(css)

    def edges_of(selector_pred):
        out = set()
        for selector, decls in rules:
            if ":focus-visible" in selector and re.search(r"\btd\b", selector) and selector_pred(selector):
                for name, value in decls:
                    if name == "box-shadow":
                        out |= focus_shadow_edges(value)
        return out

    def only(sel):
        return ":only-child" in sel or (":first-child" in sel and ":last-child" in sel)

    def first(sel):
        return ":first-child" in sel and ":last-child" not in sel and ":only-child" not in sel

    def last(sel):
        return ":last-child" in sel and ":first-child" not in sel and ":only-child" not in sel

    def plain(sel):
        return not any(k in sel for k in (":first-child", ":last-child", ":only-child"))

    base = edges_of(plain)
    if "all" not in base and not {"top", "bottom"} <= base:
        problems.append(f"tbody tr:focus-visible 下的单元格没有画上下两条 2px --tt-focus inset 阴影（实际 {sorted(base)}）")
    f_edges = edges_of(first)
    if not ({"left"} & f_edges or "all" in f_edges):
        problems.append(f"首格（:first-child）没有加左边的 2px --tt-focus inset 阴影（实际 {sorted(f_edges)}）")
    l_edges = edges_of(last)
    if not ({"right"} & l_edges or "all" in l_edges):
        problems.append(f"末格（:last-child）没有加右边的 2px --tt-focus inset 阴影（实际 {sorted(l_edges)}）")
    o_edges = edges_of(only)
    if "all" not in o_edges and not {"top", "bottom", "left", "right"} <= o_edges:
        problems.append(f"只有一格时（:only-child）没有画四边的 2px --tt-focus inset 阴影（实际 {sorted(o_edges)}）")
    return problems


def table_css_problems(raw):
    """S6：Table.css（合同第 3 条）。"""
    problems = []
    rules = parse_rules(raw)
    code = strip_comments(raw)

    def has_rule(sel_pred, *conds):
        return any(sel_pred(sel) and all(cond_ok(d, c) for c in conds) for sel, d in rules)

    if not has_rule(lambda s: re.search(r"th\.tt-num", s), C("text-align", eq="right")):
        problems.append("Table.css 没有 `.tt-table th.tt-num { text-align: right; }`（数字列表头右对齐）")
    else:
        for sel, d in rules:
            if re.search(r"th\.tt-num", sel) and cond_ok(d, C("text-align", eq="right")):
                spec = max(specificity(p) for p in split_top(sel) if "th.tt-num" in p.replace(" ", "") or "th.tt-num" in p)
                if spec <= (0, 1, 1):
                    problems.append(f"th.tt-num 的特异性 {spec} 压不过 `.tt-table th`（0,1,1）")
    if not has_rule(lambda s: re.fullmatch(r"\.tt-table-wrap", s.strip()), C("scroll-padding-top", eq="32px")):
        problems.append("Table.css 的 `.tt-table-wrap` 没有 `scroll-padding-top: 32px`")
    line = [ln for ln in raw.splitlines() if "scroll-padding-top" in ln]
    if line and not re.search(r"/\*[^*]*表头高\s*32[^*]*\*/", line[0]):
        problems.append("scroll-padding-top 那一行没有同一行注释「表头高 32（组件板 :411）」")
    if not has_rule(lambda s: re.search(r"tbody\s+tr:focus-visible$", s.strip()) is not None, C("outline", eq="none")):
        problems.append("Table.css 没有 `.tt-table tbody tr:focus-visible { outline: none; }`")
    problems += table_focus_problems(raw)
    if not re.search(r"@media\s*\(\s*forced-colors\s*:\s*active\s*\)\s*\{[^{}]*tr:focus-visible[^{}]*\{[^}]*"
                     r"outline\s*:\s*2px\s+solid\s+Highlight[^}]*outline-offset\s*:\s*-2px", code):
        problems.append("Table.css 没有 forced-colors 兜底：`@media (forced-colors: active) { .tt-table tbody tr:focus-visible "
                        "{ outline: 2px solid Highlight; outline-offset: -2px; } }`")
    if not has_rule(lambda s: "data-selected" in s, C("box-shadow", eq="inset 2px 0 0 var(--tt-primary)")):
        problems.append("选中行的 `inset 2px 0 0 var(--tt-primary)` 应留在 tr[data-selected] 上")
    problems += px_literal_problems("Table.css", raw)
    return problems


# ---------------------------------------------------------------------------
# 新组件 CSS 的取值（合同第 8–12 条、Banner 的 action）
# ---------------------------------------------------------------------------

S3 = "var(--tt-space-3)"
S2 = "var(--tt-space-2)"
S1 = "var(--tt-space-1)"

VIEWER_SPECS = [
    ("根：--tt-surface-1 底、1px --tt-border 边、--tt-radius-lg、overflow: hidden", r"\.tt-viewer(?![\w-])",
     [C(("background", "background-color"), eq="var(--tt-surface-1)"),
      C(("border", "border-width"), has=["1px"]),
      C(("border", "border-color"), has=["var(--tt-border)"]),
      C("border-radius", eq="var(--tt-radius-lg)"), C("overflow", eq="hidden")]),
    ("头：高 40，左 --tt-space-3、右 --tt-space-2", None,
     [C(("height", "min-height"), eq="40px"), sides_is("padding", left=S3, right=S2)]),
    ("头：下边框 1px --tt-border", None,
     [C(("height", "min-height"), eq="40px"), C(("border-bottom", "border-block-end"), has=["1px", "var(--tt-border)"])]),
    ("标题：--tt-mono-sm、单行省略（white-space: nowrap、overflow: hidden、text-overflow: ellipsis）", None,
     [C("font", eq="var(--tt-mono-sm)"), C("white-space", eq="nowrap"), C("overflow", eq="hidden"), C("text-overflow", eq="ellipsis")]),
    ("切换钮：高 28、左右 --tt-space-2、--tt-radius-md、透明底、--tt-text-2、--tt-text-sm", None,
     [C(("height", "min-height"), eq="28px"), sides_is("padding", left=S2, right=S2), C("border-radius", eq="var(--tt-radius-md)"),
      C(("background", "background-color"), eq="transparent"), C("color", eq="var(--tt-text-2)"), C("font", eq="var(--tt-text-sm)")]),
    ("按下态：底 --tt-surface-3", None, [C(("background", "background-color"), eq="var(--tt-surface-3)")]),
    ("主体：上下 --tt-space-2", None, [sides_is("padding", top=S2, bottom=S2)]),
    ("主体：换行关时 overflow-x: auto（只在查看器里横向滚动）", None, [C("overflow-x", eq="auto")]),
    ("行：--tt-mono-md", None, [C("font", eq="var(--tt-mono-md)")]),
    ("行号列：宽 44、右对齐", None,
     [C(("width", "min-width", "flex-basis", "flex"), has=["44px"]), C("text-align", eq="right")]),
    ("行号：右内边距 --tt-space-3、--tt-text-3", None,
     [C("text-align", eq="right"), sides_is("padding", right=S3), C("color", eq="var(--tt-text-3)")]),
    ("文字：最小高 20、右内边距 --tt-space-3", None,
     [C(("min-height", "height"), eq="20px"), sides_is("padding", right=S3)]),
    ("换行关：white-space: pre", None, [C("white-space", eq="pre")]),
    ("换行开：white-space: pre-wrap 与 word-break: break-all", None,
     [C("white-space", eq="pre-wrap"), C("word-break", eq="break-all")]),
    ("隐藏行说明：--tt-text-3 斜体", None, [C("font-style", eq="italic"), C("color", eq="var(--tt-text-3)")]),
    ("隐藏行：图标与说明间距 --tt-space-1", None,
     [C(("gap", "column-gap", "margin-left", "margin-right", "margin-inline-start", "margin-inline-end"), eq=S1)]),
    ("分片提示：--tt-text-caption、--tt-text-3、user-select: none", None,
     [C("user-select", eq="none"), C("font", eq="var(--tt-text-caption)"), C("color", eq="var(--tt-text-3)")]),
    ("底栏：--tt-surface-2 底、上边框、内边距 --tt-space-2 与 --tt-space-3、--tt-text-caption、--tt-text-3", None,
     [C(("background", "background-color"), eq="var(--tt-surface-2)"), C(("border-top", "border-block-start"), has=["1px", "var(--tt-border)"]),
      sides_is("padding", top=S2, bottom=S2, left=S3, right=S3), C("font", eq="var(--tt-text-caption)"), C("color", eq="var(--tt-text-3)")]),
    ("底栏按钮靠右（margin-left: auto 或 justify-content）", None,
     [AnyOf(C(("margin-left", "margin-inline-start"), eq="auto"), C("justify-content", has=["flex-end"]),
            C("justify-content", has=["space-between"]))]),
    ("提示条：外边距 --tt-space-2 与 --tt-space-3", r"banner",
     [sides_is("margin", top=S2, bottom=S2, left=S3, right=S3)]),
]


def viewer_extra_problems(css):
    """user-select: none 至少两条规则（行号、分片提示）；行号开着时 tt-num 的数字类要在源码里（探针另查）。"""
    n = sum(1 for _s, d in parse_rules(css) if cond_ok(d, C("user-select", eq="none")))
    return [] if n >= 2 else [f"TextViewer.css 里 user-select: none 的规则应至少 2 条（行号、分片提示），实际 {n} 条"]


MD_SPECS = [
    ("根：--tt-text-md、--tt-text-1", None, [C("font", eq="var(--tt-text-md)"), C("color", eq="var(--tt-text-1)")]),
    ("块间距 --tt-space-2", None,
     [C(("gap", "row-gap", "margin", "margin-top", "margin-bottom", "margin-block-start", "margin-block-end"), has=[S2])]),
    ("一级标题 h2：--tt-title-lg、外边距 0", r"\bh2\b", [C("font", eq="var(--tt-title-lg)")]),
    ("二级标题 h3：--tt-title-md", r"\bh3\b", [C("font", eq="var(--tt-title-md)")]),
    ("三级以下 h4：--tt-title-sm", r"\bh4\b", [C("font", eq="var(--tt-title-sm)")]),
    ("三级以下 h5：--tt-title-sm", r"\bh5\b", [C("font", eq="var(--tt-title-sm)")]),
    ("三级以下 h6：--tt-title-sm", r"\bh6\b", [C("font", eq="var(--tt-title-sm)")]),
    ("标题外边距 0", r"\bh[2-6]\b", [C("margin", zero=True)]),
    ("列表：左内边距 --tt-space-5", r"\b(ul|ol)\b|list", [sides_is("padding", left="var(--tt-space-5)")]),
    ("列表项间距 --tt-space-1", r"\b(li|ul|ol)\b|list|item",
     [C(("gap", "row-gap", "margin", "margin-top", "margin-bottom", "padding-top", "padding-bottom"), has=[S1])]),
    ("项里的段落外边距 0", r"\bli\b.*\bp\b|li\s*>\s*p", [C("margin", zero=True)]),
    ("段落保留换行：white-space: pre-wrap", r"\bp\b|para", [C("white-space", eq="pre-wrap")]),
    ("行内代码：--tt-mono-sm、内边距 1px 与 --tt-space-1、--tt-radius-sm、--tt-surface-2 底、1px --tt-border", None,
     [C("font", eq="var(--tt-mono-sm)"), sides_is("padding", top="1px", bottom="1px", left=S1, right=S1),
      C("border-radius", eq="var(--tt-radius-sm)"), C(("background", "background-color"), eq="var(--tt-surface-2)"),
      C(("border",), has=["1px", "var(--tt-border)"])]),
    ("代码块：--tt-mono-md、--tt-surface-2 底、1px --tt-border、--tt-radius-md、内边距 --tt-space-2、overflow-x: auto、white-space: pre", r"\bpre\b",
     [C("font", eq="var(--tt-mono-md)"), C(("background", "background-color"), eq="var(--tt-surface-2)"),
      C(("border",), has=["1px", "var(--tt-border)"]), C("border-radius", eq="var(--tt-radius-md)"),
      sides_is("padding", top=S2, right=S2, bottom=S2, left=S2), C("overflow-x", eq="auto"), C("white-space", eq="pre")]),
    ("表格外套的横向滚动容器：overflow-x: auto", None, [C("overflow-x", eq="auto")]),
    ("表格：--tt-text-sm", r"table", [C("font", eq="var(--tt-text-sm)")]),
    ("格：内边距 --tt-space-1 与 --tt-space-3、1px --tt-border", r"\bt[dh]\b|cell",
     [sides_is("padding", top=S1, bottom=S1, left=S3, right=S3), C(("border",), has=["1px", "var(--tt-border)"])]),
    ("表头：--tt-surface-2、--tt-title-sm、--tt-text-2", r"\bth\b|head",
     [C(("background", "background-color"), eq="var(--tt-surface-2)"), C("font", eq="var(--tt-title-sm)"), C("color", eq="var(--tt-text-2)")]),
    ("对齐用类：text-align: right", None, [C("text-align", eq="right")]),
    ("对齐用类：text-align: center", None, [C("text-align", eq="center")]),
    ("链接钮：--tt-link、透明底、无边框、无内边距、继承字体", r"button|link",
     [C("color", eq="var(--tt-link)"), C(("background", "background-color"), eq="transparent"),
      AnyOf(C("border", eq="0"), C("border", eq="none"), C("border", zero=True)), C("padding", zero=True), C("font", eq="inherit")]),
    ("链接钮悬停：下划线", r":hover", [C(("text-decoration", "text-decoration-line"), has=["underline"])]),
    ("网址：--tt-mono-sm、--tt-text-3、左外边距 --tt-space-1", None,
     [C("font", eq="var(--tt-mono-sm)"), C("color", eq="var(--tt-text-3)"), sides_is("margin", left=S1)]),
]

EFFORT_SPECS = [
    ("根 .tt-effort：inline-flex、居中、间距 --tt-space-1、--tt-text-sm、可换行", r"\.tt-effort(?![\w-])",
     [C("display", eq="inline-flex"), C("align-items", eq="center"), C(("gap", "column-gap"), eq=S1),
      C("font", eq="var(--tt-text-sm)"), C("flex-wrap", eq="wrap")]),
    ("标签与「未知」「—」：--tt-text-3", None, [C("color", eq="var(--tt-text-3)")]),
    ("档位名：--tt-mono-sm", None, [C("font", eq="var(--tt-mono-sm)")]),
]

MASKED_SPECS = [
    ("遮蔽值：inline-flex、居中、间距 --tt-space-1、--tt-text-3", None,
     [C("display", eq="inline-flex"), C("align-items", eq="center"), C(("gap", "column-gap"), eq=S1), C("color", eq="var(--tt-text-3)")]),
]

CMD_SPECS = [
    ("md：flex、居中、间距 --tt-space-1、最小高 36", None,
     [C("display", eq="flex"), C("align-items", eq="center"), C(("gap", "column-gap"), eq=S1), C("min-height", eq="36px")]),
    ("md：内边距 --tt-space-1、左 --tt-space-2", None,
     [C("min-height", eq="36px"), sides_is("padding", top=S1, right=S1, bottom=S1, left=S2)]),
    ("md：--tt-radius-md、--tt-surface-2 底、1px --tt-border", None,
     [C("border-radius", eq="var(--tt-radius-md)"), C(("background", "background-color"), eq="var(--tt-surface-2)"),
      C(("border",), has=["1px", "var(--tt-border)"])]),
    ("md 的 code：--tt-mono-md、--tt-text-1、flex: 1、min-width: 0、white-space: pre-wrap、word-break: break-all", r"code",
     [C("font", eq="var(--tt-mono-md)"), C("color", eq="var(--tt-text-1)"), C("flex", eq="1"), C("min-width", zero=True),
      C("white-space", eq="pre-wrap"), C("word-break", eq="break-all")]),
    ("sm：inline-flex、高 28、间距 --tt-space-0_5", r"\.tt-cmd--sm(?![\w-])",
     [C("display", eq="inline-flex"), C(("height", "min-height"), eq="28px"), C(("gap", "column-gap"), eq="var(--tt-space-0_5)")]),
    ("sm：内边距上下 0、右 --tt-space-0_5、左 --tt-space-2", r"\.tt-cmd--sm(?![\w-])",
     [sides_is("padding", top="0", right="var(--tt-space-0_5)", bottom="0", left=S2)]),
    ("sm 的 code：--tt-mono-sm", r"\.tt-cmd--sm[^,{]*\bcode\b", [C("font", eq="var(--tt-mono-sm)")]),
    ("sm 的复制钮：24×24、--tt-radius-sm", r"\.tt-cmd--sm\s+\.tt-icon-btn(?![\w-])",
     [C("width", eq="24px"), C("height", eq="24px"), C("border-radius", eq="var(--tt-radius-sm)")]),
    ("sm 的复制钮图标：14×14", r"\.tt-cmd--sm[^,{]*(svg|\.tt-i)\b",
     [C("width", eq="14px"), C("height", eq="14px")]),
]

NEXT_SPECS = [
    ("flex、居中、可换行、间距 --tt-space-2", None,
     [C("display", eq="flex"), C("align-items", eq="center"), C("flex-wrap", eq="wrap"), C(("gap", "column-gap"), eq=S2)]),
    ("内边距 --tt-space-2、左 --tt-space-3；--tt-radius-md", None,
     [sides_is("padding", top=S2, right=S2, bottom=S2, left=S3), C("border-radius", eq="var(--tt-radius-md)")]),
    ("--tt-tone-info-bg、--tt-tone-info-fg、--tt-text-sm", None,
     [C(("background", "background-color"), eq="var(--tt-tone-info-bg)"), C("color", eq="var(--tt-tone-info-fg)"),
      C("font", eq="var(--tt-text-sm)")]),
    ("标题：--tt-title-sm", None, [C("font", eq="var(--tt-title-sm)")]),
]

BANNER_ACTION_SPECS = [
    ("Banner.css：.tt-banner__action { flex: none; }", r"\.tt-banner__action(?![\w-])", [C("flex", eq="none")]),
]


def css_spec_problems(css, label, specs):
    return group_problems(css, label, specs)


def new_css_files():
    return [(f"{n}.css", comp_path(n, "css")) for n in NEW_COMPONENTS]


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


def index_problems(text):
    names = index_exports(text)
    problems = []
    for comp in OLD_COMPONENTS + NEW_COMPONENTS:
        if comp not in names:
            problems.append(f"components/index.ts 没有导出 {comp}")
        if f"{comp}Props" not in names:
            problems.append(f"components/index.ts 没有导出 {comp}Props 类型")
    for fn in ("isMaskedPlaceholder", "dispatchCommand"):
        if fn not in names:
            problems.append(f"components/index.ts 没有导出函数 {fn}")
    code = strip_ts_comments(text)
    if re.search(r"overlay", code):
        problems.append("components/index.ts 不该导出内部模块 overlay/")
    if re.search(r"evidence/|ansi|viewerLines|from\s+['\"]\./evidence", code):
        problems.append("components/index.ts 不该导出 evidence/ 下的内部纯函数")
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


def evidence_source_files():
    files = [comp_path(n, "tsx") for n in NEW_COMPONENTS]
    folder = REPO_ROOT / EVID_REL
    if folder.is_dir():
        files += sorted(folder.glob("*.ts")) + sorted(folder.glob("*.tsx"))
    return [p for p in files if p.is_file()]


def new_source_problems(files):
    """六个新组件与 evidence/ 的源码：不出现 href、src=、target=（全文）；不渲染 role=status、不调四个禁用接口（去注释后）。"""
    problems = []
    for path in files:
        raw = _read(path)
        label = path.relative_to(WEB).as_posix()
        for word in ("href", "src=", "target="):
            if word in raw:
                lineno = raw[:raw.index(word)].count("\n") + 1
                problems.append(f"{label}:{lineno} 出现 {word}（合同：六个新组件源码里不出现 href、src=、target=）")
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


def canvas_icon(lineno):
    """领域板第 lineno 行第一个 svg：{rect: 属性字典 或 None, paths: [d…]}。"""
    lines = _read(CANVAS_DOMAIN).split("\n")
    svg = re.search(r"<svg\b.*?</svg>", lines[lineno - 1], re.S)
    assert svg, f"领域板 :{lineno} 里没有 svg"
    rect = re.search(r"<rect\b([^>]*)>", svg.group(0))
    attrs = dict(re.findall(r'\b(\w+)="([^"]*)"', rect.group(1))) if rect else None
    return {"rect": attrs, "paths": re.findall(r'\bd="([^"]*)"', svg.group(0))}


def icon_problems(icons_text):
    problems = []
    for name, lineno, contract in (("LockIcon", 404, LOCK_CONTRACT), ("CopyIcon", 409, COPY_CONTRACT)):
        want = canvas_icon(lineno)
        if want != contract:
            problems.append(f"（门禁自身）领域板 :{lineno} 的 {want} 与合同写的 {contract} 不同")
    for name in ("LockIcon", "CopyIcon", "EyeOffIcon"):
        block = icon_block(icons_text, name)
        if block is None:
            problems.append(f"icons/index.tsx 没有 export const {name}")
            continue
        ds = re.findall(r"""<path\b[^>]*?\bd\s*=\s*["']([^"']*)["']""", block)
        want_ds = {"LockIcon": LOCK_CONTRACT["paths"], "CopyIcon": COPY_CONTRACT["paths"], "EyeOffIcon": EYE_OFF_DS}[name]
        if ds != want_ds:
            problems.append(f"{name} 的 path d 应依次为 {want_ds}，实际 {ds}")
        if "<Svg" not in block:
            problems.append(f"{name} 应沿用 Svg 包装")
        rect_want = {"LockIcon": LOCK_CONTRACT["rect"], "CopyIcon": COPY_CONTRACT["rect"], "EyeOffIcon": None}[name]
        rects = re.findall(r"<rect\b([^>]*)>", block)
        if rect_want is None:
            if rects:
                problems.append(f"{name} 不该有 rect（四条 path）")
        elif len(rects) != 1:
            problems.append(f"{name} 应恰有一个 rect，实际 {len(rects)} 个")
        else:
            got = {}
            for m in re.finditer(r"""(\w+)\s*=\s*(?:"([^"]*)"|'([^']*)'|\{\s*["']?([\d.]+)["']?\s*\})""", rects[0]):
                got[m.group(1)] = m.group(2) or m.group(3) or m.group(4)
            if got != rect_want:
                problems.append(f"{name} 的 rect 属性应为 {rect_want}，实际 {got}")
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


# ---------------------------------------------------------------------------
# 探针（Vitest + jsdom）：每份一个 describe，用例数必须全部通过
# ---------------------------------------------------------------------------

PRELUDE = r"""
import * as React from 'react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function textOf(el: Element | null): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function focusOn(el: HTMLElement) {
  act(() => {
    el.focus();
  });
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
function tipEl(): HTMLElement | null {
  return document.querySelector('[role="tooltip"]');
}
"""

# ---- ansi：stripAnsi 与性能（合同第 7 条；D01） ----
PROBE_ANSI = PRELUDE + r"""
let stripAnsi: any;

beforeAll(async () => {
  stripAnsi = (await import('../src/components/evidence/ansi')).stripAnsi;
});

const ESC = '\u001b';

describe('stripAnsi', () => {
  it('去 CSI：颜色、光标、私有参数 ?、带中间字节的序列；0x9B 开头的 CSI 同样去掉', () => {
    expect(stripAnsi(ESC + '[31m红' + ESC + '[0m')).toBe('红');
    expect(stripAnsi('a' + ESC + '[1;38;5;200mb' + ESC + '[0m')).toBe('ab');
    expect(stripAnsi('x' + ESC + '[?25ly')).toBe('xy');
    expect(stripAnsi('x' + ESC + '[2Ky' + ESC + '[10;20Hz')).toBe('xyz');
    expect(stripAnsi('x' + ESC + '[ qy')).toBe('xy');
    expect(stripAnsi('a\u009b31mb\u009b0m')).toBe('ab');
  });

  it('去 OSC：到 BEL 为止，或到 ESC 加反斜杠为止', () => {
    expect(stripAnsi('a' + ESC + ']0;窗口标题\u0007b')).toBe('ab');
    expect(stripAnsi('a' + ESC + ']8;;https://x.example' + ESC + '\\链接' + ESC + ']8;;' + ESC + '\\')).toBe('a链接');
  });

  it('去其余 ESC 双字符序列；最后剩下的 ESC 与 U+009B 一律去掉', () => {
    expect(stripAnsi('a' + ESC + 'Mb')).toBe('ab');
    expect(stripAnsi(ESC + 'cX')).toBe('X');
    expect(stripAnsi('a' + ESC)).toBe('a');
    expect(stripAnsi('a\u009b')).toBe('a');
    for (const junk of [ESC + '[', ESC + '[31', ESC + ']0;abc', '\u009b', ESC + '\\', ESC + ESC, 'x' + ESC + '[;']) {
      const out = stripAnsi(junk);
      expect(out.includes(ESC), JSON.stringify(junk) + ' 处理后不该剩 ESC').toBe(false);
      expect(out.includes('\u009b'), JSON.stringify(junk) + ' 处理后不该剩 U+009B').toBe(false);
    }
  });

  it('不动普通文字：没有 ESC 的「[31m」、制表符、换行、回车、中文原样保留', () => {
    expect(stripAnsi('普通 [31m 文字 [0m')).toBe('普通 [31m 文字 [0m');
    expect(stripAnsi('a\tb\r\nc\n')).toBe('a\tb\r\nc\n');
    expect(stripAnsi('')).toBe('');
  });

  it('256 KiB 的病态输入都在 1 秒内完成（无嵌套量词）', () => {
    const size = 256 * 1024;
    const inputs: Record<string, string> = {
      'ESC[ 重复': (ESC + '[').repeat(size / 2),
      'CSI 参数无结束字节': ESC + '[' + '1;'.repeat(size / 2 - 1),
      'OSC 无终止': ESC + ']' + 'x'.repeat(size - 2),
      '全是 ESC': ESC.repeat(size),
      'OSC 重复无终止': (ESC + ']x').repeat(Math.floor(size / 3)),
      '只有中间字节': ESC + '[' + ' '.repeat(size - 2),
      'CSI 参数重复': (ESC + '[0').repeat(Math.floor(size / 3)),
      '0x9B 加参数重复': '\u009b0'.repeat(size / 2),
    };
    for (const [name, input] of Object.entries(inputs)) {
      const t0 = Date.now();
      const out = stripAnsi(input);
      const used = Date.now() - t0;
      expect(used, name + ' 用时 ' + used + 'ms，应在 1000ms 内').toBeLessThan(1000);
      expect(typeof out).toBe('string');
      expect(out.includes(ESC), name + ' 处理后不该剩 ESC').toBe(false);
    }
  }, 60000);
});
"""

VIEWER_HELPERS = r"""
let TextViewer: any;

beforeAll(async () => {
  const mod: any = await import('../src/components/TextViewer');
  TextViewer = mod.TextViewer ?? mod.default;
});

const ESC = '\u001b';

function mountViewer(initial: any = {}, withLoad = true, withReload = true) {
  const spies: any = {
    onCopy: vi.fn(),
    onLoadMore: withLoad ? vi.fn() : undefined,
    onReload: withReload ? vi.fn() : undefined,
  };
  let cur: any = { pages: [], hasMore: false, ...initial };
  const el = () => <TextViewer onCopy={spies.onCopy} onLoadMore={spies.onLoadMore} onReload={spies.onReload} {...cur} />;
  const r = render(el());
  const root = r.container.querySelector('.tt-viewer') as HTMLElement;
  expect(root, '应有根元素 div.tt-viewer').not.toBeNull();
  expect(root.tagName).toBe('DIV');
  const update = (patch: any) => {
    cur = { ...cur, ...patch };
    r.rerender(el());
  };
  return { ...r, root, ...spies, update };
}
function numEls(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll('.tt-num[aria-hidden="true"]')) as HTMLElement[];
}
function numbers(root: HTMLElement): string[] {
  return numEls(root).map((e) => textOf(e));
}
function rowOf(root: HTMLElement, num: HTMLElement): HTMLElement {
  let el: HTMLElement = num;
  while (el.parentElement && el.parentElement !== root) {
    const p = el.parentElement;
    if (p.querySelectorAll('.tt-num[aria-hidden="true"]').length !== 1) break;
    if (p.querySelector('button[aria-pressed], .tt-banner')) break;
    if ((p.textContent || '').includes('已显示')) break;
    el = p;
  }
  return el;
}
function rows(root: HTMLElement): HTMLElement[] {
  return numEls(root).map((n) => rowOf(root, n));
}
function rowByNumber(root: HTMLElement, n: number): HTMLElement {
  const i = numbers(root).indexOf(String(n));
  expect(i, '找不到行号 ' + n + '，现有行号 ' + JSON.stringify(numbers(root))).toBeGreaterThanOrEqual(0);
  return rows(root)[i];
}
function copyBtn(root: HTMLElement): HTMLButtonElement {
  const b = root.querySelector('button[aria-label="复制已显示的文字"]');
  expect(b, '应有名称为「复制已显示的文字」的复制钮').not.toBeNull();
  return b as HTMLButtonElement;
}
function copiedText(root: HTMLElement, spy: any): string {
  const before = spy.mock.calls.length;
  fireEvent.click(copyBtn(root));
  expect(spy.mock.calls.length, '点复制钮应调一次 onCopy').toBe(before + 1);
  return spy.mock.calls[spy.mock.calls.length - 1][0];
}
function loadButtons(root: HTMLElement) {
  const all = buttonsByText(root, '继续加载');
  const rs = rows(root);
  return {
    all,
    inRows: all.filter((b) => rs.some((r) => r.contains(b))),
    inFooter: all.filter((b) => !rs.some((r) => r.contains(b))),
  };
}
const tp = (text: string, part?: number, parts?: number) => ({ mode: 'text', text, part, parts });
"""

# ---- w1：W1 只按文本显示（D01） ----
PROBE_W1 = PRELUDE + VIEWER_HELPERS + r"""
const W1_LINES = [
  '## 执行报告',
  '',
  '<img src=x onerror=alert(1)> ← 这一行必须原样显示为文字',
  '<script>alert(1)</script>',
  ESC + '[31m红色文字' + ESC + '[0m 尾部',
  'https://example.com/a?b=1&c=2',
  '<a href="https://x.example">链接</a><style>body{display:none}</style>',
  'a' + ESC + ']0;窗口标题\u0007b',
  'z',
];
const W1_SHOWN = [
  '## 执行报告',
  '',
  '<img src=x onerror=alert(1)> ← 这一行必须原样显示为文字',
  '<script>alert(1)</script>',
  '红色文字 尾部',
  'https://example.com/a?b=1&c=2',
  '<a href="https://x.example">链接</a><style>body{display:none}</style>',
  'ab',
  'z',
];
const W1_PAGES = [tp(W1_LINES.join('\n') + '\n')];

describe('W1 文本查看器只按文本显示', () => {
  it('DOM 里没有 img、script、a 等元素；行里没有 style 属性；文字原样出现；ESC 与 [31m 都不出现', () => {
    const { root } = mountViewer({ pages: W1_PAGES });
    expect(document.body.querySelectorAll('img, script, a, style, iframe, object, embed, link').length).toBe(0);
    expect(root.querySelectorAll('[onerror], [href], [src]').length).toBe(0);
    const text = root.textContent || '';
    for (const line of W1_SHOWN) {
      if (line) expect(text, '应原样出现：' + line).toContain(line);
    }
    expect(text.includes(ESC), '不该剩 ESC 字符').toBe(false);
    expect(text.includes('[31m')).toBe(false);
    expect(text.includes('[0m')).toBe(false);
    expect(text.includes('\u0007')).toBe(false);
    expect(text.includes('窗口标题')).toBe(false);
    const rs = rows(root);
    expect(rs.length, '9 行文字应有 9 个行元素').toBe(9);
    for (const row of rs) {
      expect(row.hasAttribute('style'), '行元素不该带 style 属性').toBe(false);
      expect(row.querySelector('[style]'), '行里不该有带 style 属性的元素').toBeNull();
    }
    noStatusRole();
  });

  it('网址不自动变链接：包着网址文字的祖先里没有 a、button、role=link', () => {
    const { root } = mountViewer({ pages: W1_PAGES });
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node: Node | null;
    let seen = 0;
    while ((node = walker.nextNode())) {
      if ((node.textContent || '').includes('https://example.com')) {
        seen += 1;
        for (let el = node.parentElement; el && el !== root; el = el.parentElement) {
          expect(['A', 'BUTTON']).not.toContain(el.tagName);
          expect(el.getAttribute('role')).not.toBe('link');
        }
      }
    }
    expect(seen, '网址文字应作为文本节点出现').toBeGreaterThan(0);
  });

  it('行号：每行一个，aria-hidden、tt-num，数字 1 到 9', () => {
    const { root } = mountViewer({ pages: W1_PAGES });
    expect(numbers(root)).toEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9']);
    for (const n of numEls(root)) expect(n.getAttribute('aria-hidden')).toBe('true');
  });

  it('行号与换行两个文字按钮：type=button、aria-pressed 缺省 true / false；点一下翻转并改变样式钩子，再点一下恢复', () => {
    const { root } = mountViewer({ pages: W1_PAGES });
    const lineBtn = buttonByText(root, '行号');
    const wrapBtn = buttonByText(root, '换行');
    expect(lineBtn.getAttribute('type')).toBe('button');
    expect(wrapBtn.getAttribute('type')).toBe('button');
    expect(lineBtn.getAttribute('aria-pressed')).toBe('true');
    expect(wrapBtn.getAttribute('aria-pressed')).toBe('false');
    expect(lineBtn.querySelector('svg'), '「行号」是文字按钮，不加图标').toBeNull();
    expect(wrapBtn.querySelector('svg'), '「换行」是文字按钮，不加图标').toBeNull();
    const hooks = () =>
      [root, ...Array.from(root.querySelectorAll('*'))]
        .map((e) => e.tagName + '|' + e.getAttribute('class') + '|' + e.getAttribute('style') + '|' +
          Array.from(e.attributes).filter((a) => a.name.startsWith('data-')).map((a) => a.name + '=' + a.value).join(','))
        .join('\n');
    const before = hooks();
    fireEvent.click(wrapBtn);
    expect(wrapBtn.getAttribute('aria-pressed')).toBe('true');
    const wrapped = hooks();
    expect(wrapped, '换行打开后应有类名或 data-* 之类的样式钩子变化').not.toBe(before);
    fireEvent.click(wrapBtn);
    expect(wrapBtn.getAttribute('aria-pressed')).toBe('false');
    expect(hooks(), '换行关回去后应恢复原样').toBe(before);
    fireEvent.click(lineBtn);
    expect(lineBtn.getAttribute('aria-pressed')).toBe('false');
    expect(numEls(root).length, '行号关掉后不再显示行号').toBe(0);
    expect(textOf(root)).toContain('红色文字 尾部');
    fireEvent.click(lineBtn);
    expect(lineBtn.getAttribute('aria-pressed')).toBe('true');
    expect(numEls(root).length).toBe(9);
  });

  it('开关状态在换页（重新渲染）后保持', () => {
    const { root, update } = mountViewer({ pages: W1_PAGES });
    fireEvent.click(buttonByText(root, '换行'));
    fireEvent.click(buttonByText(root, '行号'));
    update({ pages: [...W1_PAGES, tp('more\n')], hasMore: true });
    expect(buttonByText(root, '换行').getAttribute('aria-pressed')).toBe('true');
    expect(buttonByText(root, '行号').getAttribute('aria-pressed')).toBe('false');
    expect(numEls(root).length).toBe(0);
  });

  it('复制：回调收到的字符串逐字等于各文字行（ANSI 已去、隐藏行跳过）用换行连接，末尾不加换行', () => {
    const { root, onCopy } = mountViewer({ pages: W1_PAGES });
    expect(copiedText(root, onCopy)).toBe(W1_SHOWN.join('\n'));
    expect(onCopy).toHaveBeenCalledTimes(1);
  });

  it('复制钮：IconButton，名称「复制已显示的文字」，里面有 CopyIcon（rect 14），悬停 400ms 提示「复制」', () => {
    vi.useFakeTimers();
    const { root } = mountViewer({ pages: W1_PAGES });
    const btn = copyBtn(root);
    expect(btn.getAttribute('type')).toBe('button');
    expect(btn.classList.contains('tt-icon-btn')).toBe(true);
    expect(btn.classList.contains('tt-icon-btn--sm'), '复制钮是 IconButton size sm').toBe(true);
    expect(btn.querySelector('svg rect[width="14"][height="14"]'), '应是 CopyIcon').not.toBeNull();
    fireEvent.mouseEnter(btn);
    advance(399);
    expect(tipEl()).toBeNull();
    advance(1);
    expect(textOf(tipEl())).toBe('复制');
  });

  it('页里先接后切：ANSI 序列被页边界切开时仍能去掉', () => {
    const { root, onCopy } = mountViewer({ pages: [tp('前' + ESC + '[3'), tp('1m红' + ESC + '[0m后\n')], hasMore: false });
    expect(copiedText(root, onCopy)).toBe('前红后');
    expect((root.textContent || '').includes(ESC)).toBe(false);
  });
});
"""

# ---- pages：分页、分片、隐藏行、409（D02） ----
PROBE_PAGES = PRELUDE + VIEWER_HELPERS + r"""
describe('分页与底栏', () => {
  it('已显示 N 页；hasMore 为假时另显示「已到末尾」；hasMore 为真时没有；0 页也对', () => {
    const { root, update } = mountViewer({ pages: [tp('a\nb\n'), tp('c\n')], hasMore: true });
    expect(textOf(root)).toMatch(/已显示\s*2\s*页/);
    expect(textOf(root)).not.toContain('已到末尾');
    update({ hasMore: false });
    expect(textOf(root)).toMatch(/已显示\s*2\s*页/);
    expect(textOf(root)).toContain('已到末尾');
    update({ pages: [], hasMore: false });
    expect(textOf(root)).toMatch(/已显示\s*0\s*页/);
    update({ pages: [tp('a\n')], hasMore: true });
    expect(textOf(root)).toMatch(/已显示\s*1\s*页/);
    noStatusRole();
  });

  it('hasMore 为真且给了 onLoadMore 时底栏有 [继续加载]，点一下调一次；hasMore 为假或没给 onLoadMore 时没有', () => {
    const a = mountViewer({ pages: [tp('a\nb\n')], hasMore: true });
    const lb = loadButtons(a.root);
    expect(lb.all.length).toBe(1);
    expect(lb.inFooter.length).toBe(1);
    fireEvent.click(lb.all[0]);
    expect(a.onLoadMore).toHaveBeenCalledTimes(1);
    a.update({ hasMore: false });
    expect(loadButtons(a.root).all.length, 'hasMore 为假不显示 [继续加载]').toBe(0);
    a.unmount();
    const b = mountViewer({ pages: [tp('a\nb\n')], hasMore: true }, false);
    expect(loadButtons(b.root).all.length, '没给 onLoadMore 不显示 [继续加载]').toBe(0);
  });

  it('loadingMore：底栏按钮用 Button 的 loading（文字「正在加载…」、禁用、aria-busy），点了不调 onLoadMore', () => {
    const { root, onLoadMore } = mountViewer({ pages: [tp('a\n')], hasMore: true, loadingMore: true });
    const btn = buttonByText(root, '正在加载…');
    expect((btn as HTMLButtonElement).disabled).toBe(true);
    expect(btn.getAttribute('aria-busy')).toBe('true');
    expect(buttonsByText(root, '继续加载').length).toBe(0);
    fireEvent.click(btn);
    expect(onLoadMore).not.toHaveBeenCalled();
  });
});

describe('text 模式：页转行', () => {
  it('各页 text 先接起来再按换行切行：前一页不以换行结束时与下一页首行拼成一行', () => {
    const { root, onCopy } = mountViewer({ pages: [tp('a\nb'), tp('c\nd\n')] });
    expect(numbers(root)).toEqual(['1', '2', '3']);
    expect(copiedText(root, onCopy)).toBe('a\nbc\nd');
    expect(textOf(rowByNumber(root, 2))).toContain('bc');
  });

  it('文本以换行结束时末尾空串不算一行；连续两个换行结尾则多一个空行', () => {
    const a = mountViewer({ pages: [tp('x\ny\n')] });
    expect(numbers(a.root)).toEqual(['1', '2']);
    a.unmount();
    const b = mountViewer({ pages: [tp('x\n\n')] });
    expect(numbers(b.root)).toEqual(['1', '2']);
    expect(copiedText(b.root, b.onCopy)).toBe('x\n');
  });

  it('以换行开头的页不多出空行：上一页停在长行末尾，下一页以换行开头', () => {
    const { root, onCopy } = mountViewer({ pages: [tp('first\nlong-tail'), tp('\nsecond\n')] });
    expect(numbers(root)).toEqual(['1', '2', '3']);
    expect(copiedText(root, onCopy)).toBe('first\nlong-tail\nsecond');
  });

  it('每行去掉末尾回车：CRLF 文本不剩 \\r', () => {
    const { root, onCopy } = mountViewer({ pages: [tp('a\r\nb\r\n')] });
    expect(numbers(root)).toEqual(['1', '2']);
    expect(copiedText(root, onCopy)).toBe('a\nb');
    expect((root.textContent || '').includes('\r')).toBe(false);
  });

  it('第一页以换行开头时第一行是真的空行', () => {
    const { root, onCopy } = mountViewer({ pages: [tp('\nx\n')] });
    expect(numbers(root)).toEqual(['1', '2']);
    expect(copiedText(root, onCopy)).toBe('\nx');
  });
});

describe('text 模式：分片', () => {
  it('每页开头落在第几行，就把这页的 part、parts 记到那一行，后来的页覆盖先前的；第 k/n 片显示在文字前', () => {
    const { root } = mountViewer({
      pages: [tp('AAAA', 1, 3), tp('BBBB', 2, 3)],
      hasMore: true,
    });
    expect(numbers(root)).toEqual(['1']);
    const row = rowByNumber(root, 1);
    const text = row.textContent || '';
    expect(text).toContain('AAAABBBB');
    expect(textOf(row)).toMatch(/第\s*2\/3\s*片/);
    expect(text.search(/第\s*2\/3\s*片/), '「第 k/n 片」应在文字之前').toBeLessThan(text.indexOf('AAAABBBB'));
  });

  it('加载完仍显示第 n/n 片，下一行没有分片提示', () => {
    const { root } = mountViewer({
      pages: [tp('AAAA', 1, 3), tp('BBBB', 2, 3), tp('CCCC\nnext\n', 3, 3)],
      hasMore: false,
    });
    expect(numbers(root)).toEqual(['1', '2']);
    expect(textOf(rowByNumber(root, 1))).toMatch(/第\s*3\/3\s*片/);
    expect(textOf(rowByNumber(root, 1))).toContain('AAAABBBBCCCC');
    expect(textOf(rowByNumber(root, 2))).not.toMatch(/第\s*\d+\/\d+\s*片/);
  });

  it('分片提示：user-select 之类的样式靠 CSS；元素本身不是按钮、不可聚焦', () => {
    const { root } = mountViewer({ pages: [tp('AAAA', 1, 2)], hasMore: true });
    const row = rowByNumber(root, 1);
    const cap = Array.from(row.querySelectorAll('*')).find((e) => /^第\s*1\/2\s*片$/.test(textOf(e)));
    expect(cap, '应有只含「第 1/2 片」的元素').toBeTruthy();
    expect((cap as Element).closest('button')).toBeNull();
    expect((cap as Element).hasAttribute('tabindex')).toBe(false);
  });
});

describe('text 模式：行尾 [继续加载]', () => {
  it('最后一行没加载完（k<n）且还有下一页时，行尾有 Button（secondary、sm、文字「继续加载」），点一下调 onLoadMore；底栏另有一个', () => {
    const { root, onLoadMore } = mountViewer({ pages: [tp('AAAA', 1, 2)], hasMore: true });
    const lb = loadButtons(root);
    expect(lb.inRows.length, '行尾应有一个 [继续加载]').toBe(1);
    expect(lb.inFooter.length, '底栏应有一个 [继续加载]').toBe(1);
    const btn = lb.inRows[0];
    expect(btn.classList.contains('tt-btn')).toBe(true);
    expect(btn.classList.contains('tt-btn--secondary')).toBe(true);
    expect(btn.classList.contains('tt-btn--sm')).toBe(true);
    expect(rowByNumber(root, 1).contains(btn)).toBe(true);
    fireEvent.click(btn);
    expect(onLoadMore).toHaveBeenCalledTimes(1);
  });

  it('三片的第二片：k=2<3，行尾仍有；加载到第三片后行尾没有', () => {
    const a = mountViewer({ pages: [tp('aa', 1, 3), tp('bb', 2, 3)], hasMore: true });
    expect(loadButtons(a.root).inRows.length).toBe(1);
    a.update({ pages: [tp('aa', 1, 3), tp('bb', 2, 3), tp('cc\n', 3, 3)] });
    expect(loadButtons(a.root).inRows.length, 'k=n 后行尾不再有').toBe(0);
    expect(textOf(rowByNumber(a.root, 1))).toMatch(/第\s*3\/3\s*片/);
  });

  it('没有下一页（hasMore 为假）时行尾没有，即使最后一行没加载完', () => {
    const { root } = mountViewer({ pages: [tp('AAAA', 1, 2)], hasMore: false });
    expect(loadButtons(root).inRows.length).toBe(0);
    expect(loadButtons(root).all.length).toBe(0);
  });

  it('分片行不是最后一行时行尾没有（只有底栏一个）', () => {
    const { root } = mountViewer({ pages: [tp('A\nB\n', 1, 2)], hasMore: true });
    expect(textOf(rowByNumber(root, 1))).toMatch(/第\s*1\/2\s*片/);
    const lb = loadButtons(root);
    expect(lb.inRows.length).toBe(0);
    expect(lb.inFooter.length).toBe(1);
  });

  it('普通的最后一行（没有 part）行尾没有', () => {
    const { root } = mountViewer({ pages: [tp('A\nB\n')], hasMore: true });
    expect(loadButtons(root).inRows.length).toBe(0);
    expect(loadButtons(root).inFooter.length).toBe(1);
  });
});

describe('jsonl 模式', () => {
  const jp = (lines: any[]) => ({ mode: 'jsonl', lines });
  const P1 = jp([
    { n: 1, text: '{"a":1}' },
    { n: 2, hidden: 'not_json' },
    { n: 5, text: '{"b":', part: 1, parts: 3 },
  ]);
  const P2 = jp([{ n: 5, text: '2,', part: 2, parts: 3 }]);
  const P3 = jp([
    { n: 5, text: '3}', part: 3, parts: 3 },
    { n: 6, text: '{"c":3}' },
  ]);

  it('行号用 n；同一个 n 的分片按到达顺序拼接，记最后一片的 part/parts；最后一行没加载完时行尾有 [继续加载]', () => {
    const { root, onLoadMore } = mountViewer({ pages: [P1, P2], hasMore: true });
    expect(numbers(root)).toEqual(['1', '2', '5']);
    const row5 = rowByNumber(root, 5);
    expect(row5.textContent).toContain('{"b":2,');
    expect(textOf(row5)).toMatch(/第\s*2\/3\s*片/);
    const lb = loadButtons(root);
    expect(lb.inRows.length).toBe(1);
    expect(row5.contains(lb.inRows[0])).toBe(true);
    fireEvent.click(lb.inRows[0]);
    expect(onLoadMore).toHaveBeenCalledTimes(1);
  });

  it('三片到齐后：整行 {"b":2,3}，第 3/3 片，行尾没有 [继续加载]；复制跳过隐藏行', () => {
    const { root, onCopy } = mountViewer({ pages: [P1, P2, P3], hasMore: false });
    expect(numbers(root)).toEqual(['1', '2', '5', '6']);
    const row5 = rowByNumber(root, 5);
    expect(row5.textContent).toContain('{"b":2,3}');
    expect(textOf(row5)).toMatch(/第\s*3\/3\s*片/);
    expect(loadButtons(root).all.length).toBe(0);
    expect(copiedText(root, onCopy)).toBe('{"a":1}\n{"b":2,3}\n{"c":3}');
    expect(textOf(root)).toMatch(/已显示\s*3\s*页/);
    expect(textOf(root)).toContain('已到末尾');
  });

  it('隐藏行：not_json、too_long 的固定说明，其他值显示「这一行已隐藏：<原值>」；EyeOffIcon 14 带 aria-hidden；行号照常', () => {
    const { root } = mountViewer({
      pages: [jp([
        { n: 1, text: 'ok' },
        { n: 2, hidden: 'not_json' },
        { n: 3, hidden: 'too_long' },
        { n: 4, hidden: '<b>weird</b>' },
      ])],
    });
    expect(numbers(root)).toEqual(['1', '2', '3', '4']);
    expect(textOf(rowByNumber(root, 2))).toContain('这一行不是合法 JSON，已隐藏');
    expect(textOf(rowByNumber(root, 3))).toContain('这一行超过 4 MiB，已隐藏');
    expect(textOf(rowByNumber(root, 4))).toContain('这一行已隐藏：<b>weird</b>');
    expect(textOf(rowByNumber(root, 2))).not.toContain('超过 4 MiB');
    expect(textOf(rowByNumber(root, 3))).not.toContain('不是合法 JSON');
    expect(root.querySelectorAll('b').length, '隐藏原值只当文字').toBe(0);
    for (const n of [2, 3, 4]) {
      const svg = rowByNumber(root, n).querySelector('svg');
      expect(svg, '隐藏行 ' + n + ' 应有 EyeOffIcon').not.toBeNull();
      expect((svg as Element).getAttribute('width')).toBe('14');
      expect((svg as Element).getAttribute('height')).toBe('14');
      expect((svg as Element).getAttribute('aria-hidden')).toBe('true');
      const ds = Array.from((svg as Element).querySelectorAll('path')).map((p) => p.getAttribute('d'));
      expect(ds).toContain('m2 2 20 20');
      expect(ds).toContain('M14.084 14.158a3 3 0 0 1-4.242-4.242');
    }
  });

  it('隐藏行不能展开：没有按钮、链接、tabindex；点击无反应', () => {
    const { root, onCopy, onLoadMore } = mountViewer({
      pages: [jp([{ n: 1, text: 'ok' }, { n: 2, hidden: 'not_json' }])],
      hasMore: false,
    });
    const row = rowByNumber(root, 2);
    expect(row.querySelector('button, a, [tabindex], input, [role="button"], [role="link"]')).toBeNull();
    const before = root.innerHTML;
    fireEvent.click(row);
    fireEvent.doubleClick(row);
    const desc = Array.from(row.querySelectorAll('*')).find((e) => textOf(e).includes('不是合法 JSON'));
    if (desc) fireEvent.click(desc);
    expect(root.innerHTML, '点击隐藏行不该改变任何东西').toBe(before);
    expect(onCopy).not.toHaveBeenCalled();
    expect(onLoadMore).not.toHaveBeenCalled();
  });
});

describe('文件已变化（409）', () => {
  it('changed 为真时头部与行之间有 info 提示条「文件已变化」，action 是 [从头读取]，点一下调 onReload', () => {
    const { root, onReload } = mountViewer({ pages: [tp('a\nb\n')], changed: true });
    const banner = root.querySelector('.tt-banner') as HTMLElement;
    expect(banner, '应有提示条').not.toBeNull();
    expect(banner.getAttribute('data-tone')).toBe('info');
    expect(textOf(banner)).toContain('文件已变化');
    const action = banner.querySelector('.tt-banner__action') as HTMLElement;
    expect(action, '提示条应有 .tt-banner__action').not.toBeNull();
    const btn = buttonByText(action, '从头读取');
    fireEvent.click(btn);
    expect(onReload).toHaveBeenCalledTimes(1);
    const head = buttonByText(root, '行号');
    expect(head.compareDocumentPosition(banner) & Node.DOCUMENT_POSITION_FOLLOWING, '提示条在头部之后').toBeTruthy();
    expect(banner.compareDocumentPosition(numEls(root)[0]) & Node.DOCUMENT_POSITION_FOLLOWING, '提示条在行之前').toBeTruthy();
    noStatusRole();
  });

  it('没给 onReload 时没有 [从头读取]；没 changed 时没有提示条', () => {
    const a = mountViewer({ pages: [tp('a\n')], changed: true }, true, false);
    expect(buttonsByText(a.root, '从头读取').length).toBe(0);
    expect(textOf(a.root)).toContain('文件已变化');
    a.unmount();
    const b = mountViewer({ pages: [tp('a\n')], changed: false });
    expect(b.root.querySelector('.tt-banner')).toBeNull();
    expect(textOf(b.root)).not.toContain('文件已变化');
  });

  it('点关闭先藏起来；changed 仍为真时不重新出现；变假再变真时重新出现', () => {
    const { root, update } = mountViewer({ pages: [tp('a\n')], changed: true });
    const banner = root.querySelector('.tt-banner') as HTMLElement;
    const close = banner.querySelector('button[aria-label="关闭提示"]') as HTMLElement;
    expect(close, 'info 提示条总有关闭钮').not.toBeNull();
    fireEvent.click(close);
    expect(root.querySelector('.tt-banner'), '关闭后藏起来').toBeNull();
    update({ pages: [tp('a\n'), tp('b\n')] });
    expect(root.querySelector('.tt-banner'), 'changed 仍为真，不重新出现').toBeNull();
    update({ changed: false });
    expect(root.querySelector('.tt-banner')).toBeNull();
    update({ changed: true });
    expect(root.querySelector('.tt-banner'), 'changed 从假再变真，重新出现').not.toBeNull();
    expect(textOf(root)).toContain('文件已变化');
  });

  it('changed 为真时底栏与行尾的 [继续加载] 都禁用，点了不调 onLoadMore', () => {
    const { root, onLoadMore } = mountViewer({ pages: [tp('AAAA', 1, 2)], hasMore: true, changed: true });
    const lb = loadButtons(root);
    expect(lb.inRows.length).toBe(1);
    expect(lb.inFooter.length).toBe(1);
    for (const b of lb.all) {
      expect(b.disabled, '[继续加载] 应禁用').toBe(true);
      fireEvent.click(b);
    }
    expect(onLoadMore).not.toHaveBeenCalled();
  });
});

describe('属性与缺省', () => {
  it('defaultLineNumbers=false：行号关、aria-pressed=false、不显示行号；defaultWrap=true：换行 aria-pressed=true', () => {
    const { root } = mountViewer({ pages: [tp('a\nb\n')], defaultLineNumbers: false, defaultWrap: true });
    expect(buttonByText(root, '行号').getAttribute('aria-pressed')).toBe('false');
    expect(buttonByText(root, '换行').getAttribute('aria-pressed')).toBe('true');
    expect(numEls(root).length).toBe(0);
    expect(textOf(root)).toContain('a');
  });

  it('title 显示在头部；className 加在根上；根还是 div.tt-viewer', () => {
    const { root } = mountViewer({ pages: [tp('a\n')], title: 'executor-report.md', className: 'gate-extra' });
    expect(root.classList.contains('gate-extra')).toBe(true);
    expect(textOf(root)).toContain('executor-report.md');
  });

  it('文字行只作文本子节点：行元素里没有带 on 开头的属性或 style', () => {
    const { root } = mountViewer({ pages: [tp('<b onclick=x>t</b>\n')] });
    expect(root.querySelectorAll('b').length).toBe(0);
    expect(textOf(rowByNumber(root, 1))).toContain('<b onclick=x>t</b>');
  });
});
"""

MD_HELPERS = r"""
let SafeMarkdown: any;

beforeAll(async () => {
  const mod: any = await import('../src/components/SafeMarkdown');
  SafeMarkdown = mod.SafeMarkdown ?? mod.default;
});

function md(source: string, extra: any = {}) {
  const onOpenLink = vi.fn();
  const r = render(<SafeMarkdown source={source} onOpenLink={onOpenLink} {...extra} />);
  const root = r.container.firstElementChild as HTMLElement;
  expect(root, 'SafeMarkdown 应渲染出一个根元素').not.toBeNull();
  return { ...r, root, onOpenLink };
}
function tags(root: Element, selector: string): string[] {
  return Array.from(root.querySelectorAll(selector)).map((e) => e.tagName.toLowerCase());
}
function texts(root: Element, selector: string): string[] {
  return Array.from(root.querySelectorAll(selector)).map((e) => e.textContent || '');
}
function topLists(root: Element): Element[] {
  return Array.from(root.querySelectorAll('ul, ol')).filter((l) => !(l.parentElement && l.parentElement.closest('li')));
}
function listShape(list: Element): any[] {
  return Array.from(list.children).map((li) => {
    const kids = Array.from(li.children);
    const p = kids.find((c) => c.tagName === 'P');
    const subs = kids.filter((c) => c.tagName === 'UL' || c.tagName === 'OL');
    const label = (p ? p.textContent : li.textContent) || '';
    return subs.length ? [label, ...subs.map(listShape)] : label;
  });
}
const ALLOWED_TAGS = new Set(['div', 'span', 'p', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'pre', 'code', 'strong', 'em',
  'table', 'thead', 'tbody', 'tr', 'th', 'td', 'button']);
function audit(root: Element): string[] {
  const bad: string[] = [];
  for (const el of [root, ...Array.from(root.querySelectorAll('*'))]) {
    const tag = el.tagName.toLowerCase();
    if (!ALLOWED_TAGS.has(tag)) bad.push('不许的元素 ' + tag);
    for (const a of Array.from(el.attributes)) {
      const n = a.name.toLowerCase();
      if (!(n === 'class' || n === 'type' || n === 'start' || n === 'scope' || n.startsWith('aria-') || n.startsWith('data-'))) {
        bad.push(tag + ' 上不许的属性 ' + n);
      }
    }
  }
  return bad;
}
"""

# ---- md：安全 Markdown 的结构与安全（D03） ----
PROBE_MD = PRELUDE + MD_HELPERS + r"""
describe('块：标题与段落', () => {
  it('标题：1–6 级渲染成 h2–h6（h6 封顶）；去结尾空格加井号', () => {
    const { root } = md('# A\n## B ##  \n### C\n#### D\n##### E\n###### F');
    expect(tags(root, 'h1,h2,h3,h4,h5,h6')).toEqual(['h2', 'h3', 'h4', 'h5', 'h6', 'h6']);
    expect(texts(root, 'h2,h3,h4,h5,h6').map((t) => t.trim())).toEqual(['A', 'B', 'C', 'D', 'E', 'F']);
    expect(root.querySelectorAll('h1').length).toBe(0);
  });

  it('井号后不是空格、七个井号、行首空格过多都不是标题，原样当文字', () => {
    const { root } = md('#5 不是标题\n\n####### 七个井号\n\n#没有空格');
    expect(root.querySelectorAll('h1,h2,h3,h4,h5,h6').length).toBe(0);
    const t = root.textContent || '';
    expect(t).toContain('#5 不是标题');
    expect(t).toContain('####### 七个井号');
    expect(t).toContain('#没有空格');
  });

  it('段落：连续非空行，每行去首尾空白后用换行连接；空行分段', () => {
    const { root } = md('line1\n   line2   \n\nnext');
    const ps = Array.from(root.querySelectorAll('p'));
    expect(ps.map((p) => p.textContent)).toEqual(['line1\nline2', 'next']);
  });

  it('标题、围栏、列表项、表格都能打断段落', () => {
    const a = md('para\n# H\nmore');
    expect(tags(a.root, 'p,h2')).toEqual(['p', 'h2', 'p']);
    const b = md('para\n```\ncode\n```\nafter');
    expect(tags(b.root, 'p,pre')).toEqual(['p', 'pre', 'p']);
    const c = md('para\n- a\n- b');
    expect(c.root.querySelectorAll('ul > li').length).toBe(2);
    expect(Array.from(c.root.querySelectorAll('p')).map((p) => p.textContent)).toEqual(['para', 'a', 'b']);
    const d = md('para\n| a | b |\n|---|---|\n| 1 | 2 |');
    expect(d.root.querySelectorAll('table').length).toBe(1);
    expect(d.root.querySelector('p')!.textContent).toBe('para');
  });

  it('CRLF、单独的 CR 都按换行处理', () => {
    const a = md('a\r\nb\r\n\r\n- x\r\n- y');
    expect(Array.from(a.root.querySelectorAll('p')).map((p) => p.textContent)).toEqual(['a\nb', 'x', 'y']);
    const b = md('a\rb');
    expect(b.root.querySelector('p')!.textContent).toBe('a\nb');
    expect((a.root.textContent || '').includes('\r')).toBe(false);
  });
});

describe('块：列表', () => {
  it('无序列表：-、*、+ 混用算同一个列表；项里的段落也是 p', () => {
    const { root } = md('- a\n* b\n+ c');
    const lists = topLists(root);
    expect(lists.length).toBe(1);
    expect(lists[0].tagName).toBe('UL');
    expect(listShape(lists[0])).toEqual(['a', 'b', 'c']);
    expect(Array.from(lists[0].children).filter((li) => li.tagName === 'LI' && Array.from(li.children).some((c) => c.tagName === 'P')).length).toBe(3);
  });

  it('有序列表：. 与 ) 都行；首数字不是 1 带 start，是 1 不带', () => {
    const a = md('3. x\n4. y');
    expect(a.root.querySelector('ol')!.getAttribute('start')).toBe('3');
    expect(listShape(a.root.querySelector('ol')!)).toEqual(['x', 'y']);
    const b = md('1. x\n2. y');
    expect(b.root.querySelector('ol')!.hasAttribute('start')).toBe(false);
    const c = md('2) x');
    expect(c.root.querySelector('ol')!.getAttribute('start')).toBe('2');
    const d = md('0. z');
    expect(d.root.querySelector('ol')!.getAttribute('start')).toBe('0');
  });

  it('同一层有序、无序换了就另起一个列表', () => {
    const { root } = md('- a\n1. b');
    expect(topLists(root).map((l) => l.tagName)).toEqual(['UL', 'OL']);
  });

  it('嵌套：缩进不小于当前项文字起始列的是子列表，同缩进是兄弟，更小退回上一层', () => {
    const { root } = md('- a\n  - b\n    - c\n  - d\n- e');
    const lists = topLists(root);
    expect(lists.length).toBe(1);
    expect(listShape(lists[0])).toEqual([['a', [['b', ['c']], 'd']], 'e']);
  });

  it('缩进不够（1 个空格）不是子列表；有序项文字列为 3，缩进 2 是兄弟（另起无序列表），缩进 3 是子列表', () => {
    const a = md('- a\n - b');
    expect(topLists(a.root).length).toBe(1);
    expect(listShape(topLists(a.root)[0])).toEqual(['a', 'b']);
    const b = md('1. a\n  - b');
    expect(topLists(b.root).map((l) => l.tagName)).toEqual(['OL', 'UL']);
    const c = md('1. a\n   - b');
    expect(topLists(c.root).length).toBe(1);
    expect(listShape(topLists(c.root)[0])).toEqual([['a', ['b']]]);
  });

  it('行首制表符按 4 个空格缩进', () => {
    const { root } = md('- a\n\t- b');
    expect(listShape(topLists(root)[0])).toEqual([['a', ['b']]]);
  });

  it('不缩进的惰性续行接到当前项的段落里', () => {
    const { root } = md('- a\ncontinued');
    const lists = topLists(root);
    expect(lists.length).toBe(1);
    expect(listShape(lists[0])).toEqual(['a\ncontinued']);
  });

  it('空行之后若是列表项，列表继续；否则列表结束', () => {
    const a = md('- a\n\n- b');
    expect(topLists(a.root).length).toBe(1);
    expect(listShape(topLists(a.root)[0])).toEqual(['a', 'b']);
    const b = md('- a\n\nplain');
    expect(topLists(b.root).length).toBe(1);
    expect(topLists(b.root)[0].textContent).not.toContain('plain');
    expect(b.root.textContent).toContain('plain');
    const c = md('- a\n\n  more');
    expect(topLists(c.root).length).toBe(1);
    expect(topLists(c.root)[0].textContent).toContain('more');
  });

  it('最多 8 层，更深的项当作第 8 层的兄弟', () => {
    const lines: string[] = [];
    for (let i = 1; i <= 10; i += 1) lines.push('  '.repeat(i - 1) + '- L' + i);
    const { root } = md(lines.join('\n'));
    let maxDepth = 0;
    for (const ul of Array.from(root.querySelectorAll('ul'))) {
      let d = 0;
      for (let e: Element | null = ul; e; e = e.parentElement) if (e.tagName === 'UL') d += 1;
      maxDepth = Math.max(maxDepth, d);
    }
    expect(maxDepth, '列表最多 8 层').toBe(8);
    const lis = Array.from(root.querySelectorAll('li'));
    const ownText = (li: Element) => (Array.from(li.children).find((c) => c.tagName === 'P')?.textContent || '');
    const l8 = lis.find((li) => ownText(li) === 'L8')!;
    const sibs = Array.from(l8.parentElement!.children).map(ownText);
    expect(sibs).toEqual(['L8', 'L9', 'L10']);
  });
});

describe('块：围栏代码块', () => {
  it('反引号围栏：内容原样（包括 < 和 ** 和缩进），信息串忽略；渲染成 pre > code', () => {
    const { root } = md('```js title="x"\nconst a = 1 < 2;\n  **not bold**\n```\n');
    const code = root.querySelector('pre > code') as HTMLElement;
    expect(code).not.toBeNull();
    expect((code.textContent || '').replace(/\n$/, '')).toBe('const a = 1 < 2;\n  **not bold**');
    expect(root.querySelectorAll('strong').length).toBe(0);
    expect(root.textContent).not.toContain('title=');
  });

  it('波浪号围栏；闭合行长度不短于开头；更长的围栏里可以放短围栏；没有闭合行就到文末', () => {
    const a = md('~~~\ntilde\n~~~');
    expect((a.root.querySelector('pre code')!.textContent || '').replace(/\n$/, '')).toBe('tilde');
    const b = md('````\n```\ninner\n```\n````');
    expect((b.root.querySelector('pre code')!.textContent || '').replace(/\n$/, '')).toBe('```\ninner\n```');
    const c = md('```\na\nb');
    expect((c.root.querySelector('pre code')!.textContent || '').replace(/\n$/, '')).toBe('a\nb');
  });

  it('反引号围栏的信息串里有反引号时不是围栏', () => {
    const { root } = md('``` a`b\nx');
    expect(root.querySelectorAll('pre').length).toBe(0);
  });
});

describe('块：表格', () => {
  const TABLE = [
    '| 左 | 右 | 中 | 无 |',
    '|:---|---:|:--:|----|',
    '| a | b | c | d |',
    '| 1 \\| 2 | x |',
    '| p | q | r | s | extra |',
  ].join('\n');

  it('结构：外套横向滚动 div，table > thead > tr > th[scope=col]，tbody > tr > td；多的格丢掉、少的补空；\\| 是字面竖线', () => {
    const { root } = md(TABLE);
    const table = root.querySelector('table') as HTMLElement;
    expect(table).not.toBeNull();
    const wrap = table.parentElement as HTMLElement;
    expect(wrap.tagName).toBe('DIV');
    expect(wrap, '表格外应套一个滚动容器 div').not.toBe(root);
    const ths = Array.from(table.querySelectorAll('thead > tr > th'));
    expect(ths.map((t) => t.textContent)).toEqual(['左', '右', '中', '无']);
    for (const th of ths) expect(th.getAttribute('scope')).toBe('col');
    const trs = Array.from(table.querySelectorAll('tbody > tr'));
    expect(trs.length).toBe(3);
    expect(trs.map((tr) => Array.from(tr.children).map((td) => td.tagName + ':' + td.textContent))).toEqual([
      ['TD:a', 'TD:b', 'TD:c', 'TD:d'],
      ['TD:1 | 2', 'TD:x', 'TD:', 'TD:'],
      ['TD:p', 'TD:q', 'TD:r', 'TD:s'],
    ]);
  });

  it('对齐用类不用内联样式：左、右、居中的类互不相同，不设对齐的列不带这些类', () => {
    const { root } = md(TABLE);
    const ths = Array.from(root.querySelectorAll('thead th'));
    const cls = ths.map((t) => t.getAttribute('class') || '');
    expect(new Set(cls.slice(0, 3)).size, '左、右、居中三列的类应各不相同：' + JSON.stringify(cls)).toBe(3);
    expect(cls[3], '「-」不设对齐').not.toBe(cls[0]);
    expect(cls[3]).not.toBe(cls[1]);
    expect(cls[3]).not.toBe(cls[2]);
    const tds = Array.from(root.querySelector('tbody tr')!.children);
    const tcls = tds.map((t) => t.getAttribute('class') || '');
    expect(new Set(tcls.slice(0, 3)).size, '单元格也带对齐类：' + JSON.stringify(tcls)).toBe(3);
    expect(root.querySelectorAll('[style], [align]').length).toBe(0);
  });

  it('不是表格的写法：格数不同、没有对齐行；表头不带行也算表格', () => {
    const a = md('| a | b |\n|---|');
    expect(a.root.querySelectorAll('table').length).toBe(0);
    const b = md('| a | b |\n|---|---|---|');
    expect(b.root.querySelectorAll('table').length).toBe(0);
    const d = md('| a | b |\n|---|---|');
    expect(d.root.querySelectorAll('th').length).toBe(2);
    expect(d.root.querySelectorAll('td').length).toBe(0);
  });

  it('格里可以有行内格式', () => {
    const { root } = md('| **x** | `y` |\n|---|---|\n| *z* | w |');
    expect(root.querySelectorAll('thead th strong').length).toBe(1);
    expect(root.querySelectorAll('thead th code').length).toBe(1);
    expect(root.querySelectorAll('tbody td em').length).toBe(1);
  });
});

describe('行内', () => {
  it('粗体、斜体、行内代码的基本写法（星号与下划线两种）', () => {
    const { root } = md('**粗** *斜* `码` __粗2__ _斜2_');
    expect(texts(root, 'strong')).toEqual(['粗', '粗2']);
    expect(texts(root, 'em')).toEqual(['斜', '斜2']);
    expect(texts(root, 'code')).toEqual(['码']);
  });

  it('蛇形名不变斜体：下划线开头前、结尾后是字母或数字时不配对', () => {
    const src = 'effort_requested 和 a_b_c 以及 x_1 与 y_2 还有 snake_case_name';
    const { root } = md(src);
    expect(root.querySelectorAll('em, strong').length).toBe(0);
    expect(root.textContent).toBe(src);
  });

  it('星号不受字母数字限制：foo*bar*baz 中间是斜体', () => {
    const { root } = md('foo*bar*baz');
    expect(texts(root, 'em')).toEqual(['bar']);
  });

  it('定界符后是空白、或结尾前是空白时不配对，当字面字符', () => {
    for (const src of ['2 * 3 * 4', '**a **', '** a**', '文 * a * 文']) {
      const { root } = md(src);
      expect(root.querySelectorAll('em, strong').length, src).toBe(0);
      expect(root.textContent, src).toBe(src);
    }
  });

  it('配不上的定界符与反引号当字面字符', () => {
    for (const src of ['**abc', '*abc', '`abc', 'a `b`` c', 'x_y']) {
      const { root } = md(src);
      expect(root.querySelectorAll('em, strong, code').length, src).toBe(0);
      expect(root.textContent, src).toBe(src);
    }
  });

  it('粗体里可以套斜体', () => {
    const { root } = md('**粗 *斜* 粗**');
    expect(root.querySelectorAll('strong').length).toBe(1);
    expect(texts(root, 'strong em')).toEqual(['斜']);
  });

  it('反斜杠加 ASCII 标点是字面字符；反斜杠加字母原样保留', () => {
    const { root } = md('\\*字面\\* 和 C:\\dir 与 \\\\');
    expect(root.querySelectorAll('em').length).toBe(0);
    expect(root.textContent).toBe('*字面* 和 C:\\dir 与 \\');
  });

  it('代码段：反引号串配同长度串，内容原样；两头有空格且不全是空格时各去一个空格', () => {
    const { root } = md('``a`b`` 和 `  x  ` 和 `   ` 和 `` `y` ``');
    expect(texts(root, 'code')).toEqual(['a`b', ' x ', '   ', '`y`']);
  });

  it('代码段里的星号、尖括号都是文字', () => {
    const { root } = md('`**x**` 与 `<b>`');
    expect(root.querySelectorAll('strong, b').length).toBe(0);
    expect(texts(root, 'code')).toEqual(['**x**', '<b>']);
  });
});

describe('链接', () => {
  it('http(s) 放行：渲染成 button type=button（文字为链接文字）加紧跟的 span（网址），没有 a、没有 href；点击调一次 onOpenLink(原网址)', () => {
    const url = 'https://example.com/a?b=1&c=2';
    const { root, onOpenLink } = md('看 [官网](' + url + ') 吧');
    expect(root.querySelectorAll('a, [href]').length).toBe(0);
    const btns = Array.from(root.querySelectorAll('button'));
    expect(btns.length).toBe(1);
    expect(btns[0].getAttribute('type')).toBe('button');
    expect(btns[0].textContent).toBe('官网');
    const next = btns[0].nextElementSibling as HTMLElement;
    expect(next && next.tagName).toBe('SPAN');
    expect(next.textContent).toBe(url);
    fireEvent.click(btns[0]);
    expect(onOpenLink).toHaveBeenCalledTimes(1);
    expect(onOpenLink).toHaveBeenCalledWith(url);
  });

  it('协议不分大小写，网址原样传回；不解码实体', () => {
    const a = md('[a](HtTpS://X.example/Path)');
    fireEvent.click(a.root.querySelector('button')!);
    expect(a.onOpenLink).toHaveBeenCalledWith('HtTpS://X.example/Path');
    const b = md('[a](http://x.example/?a=1&amp;b=2)');
    fireEvent.click(b.root.querySelector('button')!);
    expect(b.onOpenLink).toHaveBeenCalledWith('http://x.example/?a=1&amp;b=2');
    expect(b.root.querySelector('button + span')!.textContent).toBe('http://x.example/?a=1&amp;b=2');
  });

  it('被拒的（javascript:、data:、mailto:、相对地址、//host、ftp:、单斜杠、只有协议）只渲染链接文字，网址不出现，没有按钮', () => {
    const bad = ['javascript:alert', 'JAVASCRIPT:alert', 'data:text/plain,hi', 'mailto:a@b.example', '/rel/path', '../x', '//evil.example/x',
      'ftp://x.example', 'http:/x.example', 'https://', 'http://', '#frag', 'vbscript:x'];
    for (const url of bad) {
      const { root, onOpenLink } = md('[文字](' + url + ')');
      expect(root.querySelectorAll('button, a').length, url).toBe(0);
      expect(root.textContent, url + ' 应只剩链接文字').toBe('文字');
      expect(onOpenLink).not.toHaveBeenCalled();
    }
  });

  it('链接文字为空、![…](…) 形式、带标题的链接都不算链接，整段当文字', () => {
    const cases = ['[](https://x.example)', '![alt](https://x.example/a.png)', '[a](https://x.example "title")'];
    for (const src of cases) {
      const { root } = md(src);
      expect(root.querySelectorAll('button, a, img').length, src).toBe(0);
      expect(root.textContent, src).toBe(src);
    }
  });

  it('尖括号自动链接、裸网址都不变链接', () => {
    const { root } = md('<https://auto.example> 与 https://bare.example/x');
    expect(root.querySelectorAll('button, a').length).toBe(0);
    expect(root.textContent).toBe('<https://auto.example> 与 https://bare.example/x');
  });
});

describe('原始 HTML 与不支持的语法', () => {
  it('原始 HTML 原样当文字，不解码实体', () => {
    const src = '<img src=x onerror=alert(1)>\n\n<script>alert(1)</script>\n\n<b>bold</b> &amp; &lt;i&gt; &copy;\n\n<div style="x">y</div>';
    const { root } = md(src);
    expect(root.querySelectorAll('img, script, b, i, style, iframe').length).toBe(0);
    expect(root.querySelectorAll('[style], [onerror]').length).toBe(0);
    const t = root.textContent || '';
    expect(t).toContain('<img src=x onerror=alert(1)>');
    expect(t).toContain('<script>alert(1)</script>');
    expect(t).toContain('<b>bold</b> &amp; &lt;i&gt; &copy;');
    expect(t).toContain('<div style="x">y</div>');
  });

  it('引用块、分隔线、Setext 标题、缩进代码、删除线、任务列表、脚注都原样当文字', () => {
    const a = md('> quote\n> more');
    expect(a.root.querySelectorAll('blockquote').length).toBe(0);
    expect(a.root.querySelector('p')!.textContent).toBe('> quote\n> more');
    const b = md('---');
    expect(b.root.querySelectorAll('hr').length).toBe(0);
    expect(b.root.textContent).toBe('---');
    const c = md('Title\n===');
    expect(c.root.querySelectorAll('h1,h2,h3').length).toBe(0);
    expect(c.root.querySelector('p')!.textContent).toBe('Title\n===');
    const d = md('    indented');
    expect(d.root.querySelectorAll('pre').length).toBe(0);
    expect(d.root.textContent).toBe('indented');
    const e = md('~~del~~ [^1]');
    expect(e.root.querySelectorAll('del, s').length).toBe(0);
    expect(e.root.textContent).toBe('~~del~~ [^1]');
    const f = md('- [ ] t');
    expect(f.root.querySelectorAll('input').length).toBe(0);
    expect(listShape(topLists(f.root)[0])).toEqual(['[ ] t']);
  });
});

describe('元素与属性的允许集合', () => {
  it('一份混合文档：元素都在允许集合里，属性只有 class、type、start、scope、aria-*、data-*；没有 style、href、src、on 开头属性', () => {
    const big = [
      '# T', '',
      '段落 **b** *i* `c` [ok](https://x.example) [bad](javascript:alert) <img src=x onerror=alert(1)>', '',
      '- a', '  - b', '3. c', '',
      '```', '<script>alert(1)</script>', '```', '',
      '| h | i |', '|:--|--:|', '| 1 | 2 |', '',
      '> q', '---', '[](https://x.example)',
    ].join('\n');
    const { root } = md(big);
    expect(audit(root)).toEqual([]);
    const all = [root, ...Array.from(root.querySelectorAll('*'))];
    expect(all.filter((e) => e.hasAttribute('href') || e.hasAttribute('onerror')).length, '不应有 href、onerror 属性').toBe(0);
    expect(root.querySelectorAll('img, script, a').length, '原始 HTML 只是文字，不应生成元素').toBe(0);
    noStatusRole();
  });

  it('className 加在根上；空文档渲染不报错', () => {
    const { root } = md('x', { className: 'gate-md' });
    expect(root.classList.contains('gate-md')).toBe(true);
    const e = md('');
    expect(e.root).not.toBeNull();
  });
});
"""

# ---- mdperf：parseMarkdown 的性能（D03） ----
PROBE_MDPERF = PRELUDE + MD_HELPERS + r"""
let parseMarkdown: any;

beforeAll(async () => {
  parseMarkdown = (await import('../src/components/evidence/markdown')).parseMarkdown;
});

const SIZE = 256 * 1024;

function timed(name: string, source: string) {
  const t0 = Date.now();
  const out = parseMarkdown(source);
  const used = Date.now() - t0;
  expect(used, name + ' 用时 ' + used + 'ms，应在 2000ms 内').toBeLessThan(2000);
  expect(out, name + ' 应返回解析结果').toBeDefined();
}

describe('parseMarkdown 的性能：256 KiB 病态输入 2 秒内返回', () => {
  it('全是 *', () => {
    timed('全是 *', '*'.repeat(SIZE));
  }, 30000);

  it('全是 _', () => {
    timed('全是 _', '_'.repeat(SIZE));
  }, 30000);

  it('全是 [', () => {
    timed('全是 [', '['.repeat(SIZE));
  }, 30000);

  it('全是反引号', () => {
    timed('全是反引号', '`'.repeat(SIZE));
  }, 30000);

  it('[a]( 重复', () => {
    timed('[a]( 重复', '[a]('.repeat(SIZE / 4));
  }, 30000);

  it('**a 重复', () => {
    timed('**a 重复', '**a'.repeat(Math.floor(SIZE / 3)));
  }, 30000);

  it('每行多缩进两格的 - x 共 2000 行', () => {
    const lines: string[] = [];
    for (let i = 0; i < 2000; i += 1) lines.push(' '.repeat(2 * i) + '- x');
    timed('逐行缩进的列表', lines.join('\n'));
  }, 30000);

  it('混合的标点与反引号、竖线、井号', () => {
    timed('混合', '*_`[]()!\\<>|-# '.repeat(Math.floor(SIZE / 15)));
    timed('竖线表头重复', '| a '.repeat(Math.floor(SIZE / 4)));
    timed('围栏不闭合', '```\n' + 'x\n'.repeat(SIZE / 2));
  }, 60000);

  it('经 SafeMarkdown 渲染 64 KiB 的病态输入也不卡死（5 秒内）', () => {
    for (const src of ['*'.repeat(64 * 1024), '[a]('.repeat(16 * 1024), '`a'.repeat(32 * 1024)]) {
      const t0 = Date.now();
      const { unmount } = md(src);
      const used = Date.now() - t0;
      unmount();
      expect(used, '渲染用时 ' + used + 'ms').toBeLessThan(5000);
    }
  }, 60000);
});
"""

# ---- effort：思考档位（D04） ----
PROBE_EFFORT = PRELUDE + r"""
let EffortPair: any;

beforeAll(async () => {
  const mod: any = await import('../src/components/EffortPair');
  EffortPair = mod.EffortPair ?? mod.default;
});

function mount(props: any) {
  const r = render(<EffortPair {...props} />);
  const root = r.container.querySelector('.tt-effort') as HTMLElement;
  expect(root, '应有根元素 span.tt-effort').not.toBeNull();
  expect(root.tagName).toBe('SPAN');
  return { ...r, root };
}
function warnTag(root: HTMLElement): HTMLElement | null {
  return root.querySelector('.tt-tag[data-tone="warning"]');
}

describe('思考档位 EffortPair', () => {
  it('一致：「要求 high · 生效 high」，data-state=same，没有警告标签', () => {
    const { root } = mount({ requested: 'high', effective: 'high' });
    expect(textOf(root)).toBe('要求 high · 生效 high');
    expect(root.getAttribute('data-state')).toBe('same');
    expect(warnTag(root)).toBeNull();
    expect(root.querySelectorAll('[title]').length).toBe(0);
    noStatusRole();
  });

  it('不同：「要求 max · 生效 high 与要求不同」，data-state=differs，warning 色调的 Tag 带 title「内核记下的生效档位与要求不同」', () => {
    const { root } = mount({ requested: 'max', effective: 'high' });
    expect(textOf(root)).toBe('要求 max · 生效 high 与要求不同');
    expect(root.getAttribute('data-state')).toBe('differs');
    const tag = warnTag(root) as HTMLElement;
    expect(tag, '应有 warning 色调的 Tag').not.toBeNull();
    expect(textOf(tag)).toBe('与要求不同');
    expect(tag.getAttribute('title')).toBe('内核记下的生效档位与要求不同');
    expect(root.querySelectorAll('.tt-tag--attention, .tt-tag--brand, [data-tone="attention"], [data-tone="brand"]').length, '不用金色').toBe(0);
  });

  it('未知：生效缺失（null、undefined、空数组、空串）→「要求 high · 生效 未知」，data-state=unknown，不显示成要求的档位', () => {
    for (const eff of [null, undefined, [], '']) {
      const { root, unmount } = mount({ requested: 'high', effective: eff });
      expect(textOf(root), JSON.stringify(eff)).toBe('要求 high · 生效 未知');
      expect(root.getAttribute('data-state'), JSON.stringify(eff)).toBe('unknown');
      expect(warnTag(root)).toBeNull();
      unmount();
    }
    const { root } = mount({ requested: 'high' });
    expect(textOf(root), '不传 effective').toBe('要求 high · 生效 未知');
  });

  it('没有要求（null、undefined、空串）：整格只显示「—」，data-state=none，生效有值也不显示', () => {
    for (const req of [null, undefined, '']) {
      for (const eff of ['high', null, ['a', 'b']]) {
        const { root, unmount } = mount({ requested: req, effective: eff });
        expect(textOf(root), JSON.stringify([req, eff])).toBe('—');
        expect(root.getAttribute('data-state')).toBe('none');
        expect(warnTag(root)).toBeNull();
        unmount();
      }
    }
    const { root } = mount({});
    expect(textOf(root)).toBe('—');
  });

  it('生效有多个：原样列出（顿号连接），任一不同即不一致', () => {
    const { root } = mount({ requested: 'max', effective: ['high', 'max'] });
    expect(textOf(root)).toBe('要求 max · 生效 high、max 与要求不同');
    expect(root.getAttribute('data-state')).toBe('differs');
    expect(warnTag(root)).not.toBeNull();
  });

  it('生效有多个且都相同：「要求 high · 生效 high、high」，不加标签，data-state=same', () => {
    const { root } = mount({ requested: 'high', effective: ['high', 'high'] });
    expect(textOf(root)).toBe('要求 high · 生效 high、high');
    expect(root.getAttribute('data-state')).toBe('same');
    expect(warnTag(root)).toBeNull();
  });

  it('逐字相同才算一致：大小写不同算不同；单元素数组与字符串等价', () => {
    const a = mount({ requested: 'High', effective: 'high' });
    expect(textOf(a.root)).toBe('要求 High · 生效 high 与要求不同');
    expect(a.root.getAttribute('data-state')).toBe('differs');
    a.unmount();
    const b = mount({ requested: 'high', effective: ['high'] });
    expect(textOf(b.root)).toBe('要求 high · 生效 high');
    expect(b.root.getAttribute('data-state')).toBe('same');
  });

  it('「要求」「生效」是标签文字，档位名各自成元素（不与标签粘在一个文本节点里）', () => {
    const { root } = mount({ requested: 'high', effective: 'high' });
    const leaves = Array.from(root.querySelectorAll('*')).filter((e) => e.children.length === 0).map((e) => textOf(e));
    expect(leaves).toContain('要求');
    expect(leaves).toContain('生效');
    expect(leaves.filter((t) => t === 'high').length).toBe(2);
  });
});
"""

# ---- atoms：遮蔽值、命令行、下一步、提示条 action、图标、导出（D05–D07） ----
PROBE_ATOMS = PRELUDE + r"""
const ICON_SPECS: any = __ICON_SPECS__;
const PLACEHOLDERS = ['（含疑似凭据，不显示）', '（值不显示）', '<redacted>', '（疑似凭据的键名）'];

describe('图标', () => {
  for (const name of ['LockIcon', 'CopyIcon', 'EyeOffIcon']) {
    it(name + '：沿用 Svg 包装（tt-i、aria-hidden、24 视窗），rect 属性与 path d 逐条等于合同', async () => {
      const icons: any = await import('../src/icons');
      const Icon = icons[name];
      expect(typeof Icon, name + ' 应是导出的组件').toBe('function');
      const { container } = render(<Icon width={14} height={14} />);
      const svg = container.querySelector('svg') as SVGElement;
      expect(svg).not.toBeNull();
      expect(svg.getAttribute('aria-hidden')).toBe('true');
      expect(svg.classList.contains('tt-i')).toBe(true);
      expect(svg.getAttribute('viewBox')).toBe('0 0 24 24');
      expect(svg.getAttribute('width')).toBe('14');
      expect(svg.getAttribute('height')).toBe('14');
      const spec = ICON_SPECS[name];
      const rects = Array.from(svg.querySelectorAll('rect'));
      if (spec.rect) {
        expect(rects.length).toBe(1);
        const got: any = {};
        for (const a of Array.from(rects[0].attributes)) got[a.name] = a.value;
        expect(got).toEqual(spec.rect);
      } else {
        expect(rects.length).toBe(0);
      }
      const ds = Array.from(svg.querySelectorAll('path')).map((p) => p.getAttribute('d'));
      expect(ds).toEqual(spec.paths);
      expect(svg.children.length).toBe(rects.length + ds.length);
    });
  }
});

describe('Banner 的可选 action', () => {
  let Banner: any;
  beforeAll(async () => {
    Banner = (await import('../src/components/Banner')).Banner;
  });
  const classes = (el: Element) => Array.from(el.children).map((c) => c.getAttribute('class'));

  it('不传 action 时结构与以前完全相同：图标、文字、关闭钮三格，没有 .tt-banner__action', () => {
    const onClose = vi.fn();
    const { container } = render(<Banner tone="info" onClose={onClose}>提示内容</Banner>);
    const banner = container.querySelector('.tt-banner') as HTMLElement;
    expect(classes(banner)).toEqual(['tt-i tt-banner__icon', 'tt-banner__text', 'tt-banner__close']);
    expect(banner.querySelector('.tt-banner__action')).toBeNull();
    fireEvent.click(banner.querySelector('.tt-banner__close')!);
    expect(onClose).toHaveBeenCalledTimes(1);
    const w = render(<Banner tone="warning">注意</Banner>);
    expect(classes(w.container.querySelector('.tt-banner')!)).toEqual(['tt-i tt-banner__icon', 'tt-banner__text']);
  });

  it('传了 action：span.tt-banner__action 在文字之后、关闭钮之前；info 仍有关闭钮；点操作钮不触发关闭', () => {
    const onClose = vi.fn();
    const onAct = vi.fn();
    const { container } = render(
      <Banner tone="info" onClose={onClose} action={<button type="button" onClick={onAct}>从头读取</button>}>
        文件已变化
      </Banner>,
    );
    const banner = container.querySelector('.tt-banner') as HTMLElement;
    const kids = Array.from(banner.children);
    expect(kids.length).toBe(4);
    expect(kids[1].classList.contains('tt-banner__text')).toBe(true);
    expect(kids[2].tagName).toBe('SPAN');
    expect(kids[2].classList.contains('tt-banner__action')).toBe(true);
    expect(kids[3].classList.contains('tt-banner__close')).toBe(true);
    fireEvent.click(buttonByText(kids[2], '从头读取'));
    expect(onAct).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
    const w = render(<Banner tone="warning" action={<button type="button">x</button>}>注意</Banner>);
    expect(classes(w.container.querySelector('.tt-banner')!)).toEqual(['tt-i tt-banner__icon', 'tt-banner__text', 'tt-banner__action']);
  });
});

describe('MaskedValue 遮蔽值', () => {
  let MaskedValue: any;
  let isMaskedPlaceholder: any;
  beforeAll(async () => {
    const mod: any = await import('../src/components/MaskedValue');
    MaskedValue = mod.MaskedValue ?? mod.default;
    isMaskedPlaceholder = mod.isMaskedPlaceholder;
  });

  it('结构：span，title=内核已遮蔽，LockIcon 14（aria-hidden）在前，后面是原样的占位文字', () => {
    for (const value of PLACEHOLDERS) {
      const { container, unmount } = render(<MaskedValue>{value}</MaskedValue>);
      const root = container.firstElementChild as HTMLElement;
      expect(root.tagName).toBe('SPAN');
      expect(root.getAttribute('title')).toBe('内核已遮蔽');
      expect(root.textContent).toBe(value);
      const svg = root.firstElementChild as SVGElement;
      expect(svg && svg.tagName.toLowerCase()).toBe('svg');
      expect(svg.getAttribute('width')).toBe('14');
      expect(svg.getAttribute('height')).toBe('14');
      expect(svg.getAttribute('aria-hidden')).toBe('true');
      expect(svg.querySelector('rect[width="18"][height="11"]'), '应是 LockIcon').not.toBeNull();
      expect(root.querySelectorAll('[title]').length, '只有根上有 title，里面的元素没有').toBe(0);
      unmount();
    }
    noStatusRole();
  });

  it('isMaskedPlaceholder：四种占位逐字比较为真，其余为假（括号是全角）', () => {
    for (const v of PLACEHOLDERS) expect(isMaskedPlaceholder(v), v).toBe(true);
    for (const v of ['(值不显示)', '（值不显示） ', ' <redacted>', '<REDACTED>', '', 'abc', '（含疑似凭据，不显示', '值不显示', '（疑似凭据的键名）。']) {
      expect(isMaskedPlaceholder(v), JSON.stringify(v)).toBe(false);
    }
  });
});

describe('CommandLine 命令行', () => {
  let CommandLine: any;
  let dispatchCommand: any;
  beforeAll(async () => {
    const mod: any = await import('../src/components/CommandLine');
    CommandLine = mod.CommandLine ?? mod.default;
    dispatchCommand = mod.dispatchCommand;
  });

  it('dispatchCommand：bash scripts/dispatch-pi.sh 加空格连接的参数；无参数时末尾没有空格；参数原样不加引号不转义', () => {
    expect(dispatchCommand([])).toBe('bash scripts/dispatch-pi.sh');
    expect(dispatchCommand(['logs', 'cat'])).toBe('bash scripts/dispatch-pi.sh logs cat');
    expect(dispatchCommand(['config', 'preset', 'use', 'economy'])).toBe('bash scripts/dispatch-pi.sh config preset use economy');
    expect(dispatchCommand(['a b', '"c"', "d'e", '$X;y'])).toBe('bash scripts/dispatch-pi.sh a b "c" d\'e $X;y');
    expect(dispatchCommand(['one'])).toBe('bash scripts/dispatch-pi.sh one');
  });

  it('md（缺省）：code 里是命令文字，复制钮名称「复制命令」，点击调 onCopy(command)；根上没有 tt-cmd--sm', () => {
    const onCopy = vi.fn();
    const command = 'bash scripts/dispatch-pi.sh config rollback 42 <x> & "y"';
    const { container } = render(<CommandLine command={command} onCopy={onCopy} />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.classList.contains('tt-cmd--sm')).toBe(false);
    const code = root.querySelector('code') as HTMLElement;
    expect(code.textContent).toBe(command);
    const btn = root.querySelector('button[aria-label="复制命令"]') as HTMLButtonElement;
    expect(btn, '应有名称为「复制命令」的复制钮').not.toBeNull();
    expect(btn.getAttribute('type')).toBe('button');
    expect(btn.classList.contains('tt-icon-btn')).toBe(true);
    expect(btn.classList.contains('tt-icon-btn--sm')).toBe(true);
    expect(btn.querySelector('svg rect[width="14"][height="14"]'), '应是 CopyIcon').not.toBeNull();
    expect(root.querySelectorAll('button').length).toBe(1);
    fireEvent.click(btn);
    expect(onCopy).toHaveBeenCalledTimes(1);
    expect(onCopy).toHaveBeenCalledWith(command);
    noStatusRole();
  });

  it('sm：根上带 tt-cmd--sm，结构与行为同 md；复制钮悬停 400ms 提示「复制」', () => {
    vi.useFakeTimers();
    const onCopy = vi.fn();
    const { container } = render(<CommandLine size="sm" command="/plan-task logs-cat" onCopy={onCopy} />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.classList.contains('tt-cmd--sm')).toBe(true);
    expect(root.querySelector('code')!.textContent).toBe('/plan-task logs-cat');
    const btn = root.querySelector('button[aria-label="复制命令"]') as HTMLButtonElement;
    fireEvent.click(btn);
    expect(onCopy).toHaveBeenCalledWith('/plan-task logs-cat');
    fireEvent.mouseEnter(btn);
    advance(399);
    expect(tipEl()).toBeNull();
    advance(1);
    expect(textOf(tipEl())).toBe('复制');
  });
});

describe('NextStep 下一步', () => {
  let NextStep: any;
  beforeAll(async () => {
    NextStep = (await import('../src/components/NextStep')).NextStep;
  });

  it('不带命令：InfoIcon 16（aria-hidden）、strong 标题、说明文字；不设 role，不是提示条，没有按钮和 code', () => {
    const { container } = render(<NextStep title="下一步">需要出新版本合同返工。</NextStep>);
    const root = container.firstElementChild as HTMLElement;
    expect(root.hasAttribute('role')).toBe(false);
    expect(root.querySelector('.tt-banner, [role]')).toBeNull();
    const svg = root.firstElementChild as SVGElement;
    expect(svg && svg.tagName.toLowerCase()).toBe('svg');
    expect(svg.getAttribute('width')).toBe('16');
    expect(svg.getAttribute('height')).toBe('16');
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(Array.from(svg.querySelectorAll('path')).map((p) => p.getAttribute('d'))).toContain('M12 16v-4');
    const strong = root.querySelector('strong') as HTMLElement;
    expect(strong && strong.textContent).toBe('下一步');
    expect(textOf(root)).toContain('需要出新版本合同返工。');
    expect(root.querySelectorAll('button, code').length).toBe(0);
    noStatusRole();
  });

  it('没有 title 时没有 strong', () => {
    const { container } = render(<NextStep>只有说明</NextStep>);
    expect(container.querySelector('strong')).toBeNull();
    expect(textOf(container)).toBe('只有说明');
  });

  it('带命令：末尾是 CommandLine size=sm（tt-cmd--sm），复制钮调 onCopy(command)', () => {
    const onCopy = vi.fn();
    const { container } = render(
      <NextStep title="下一步" command="/plan-task logs-cat" onCopy={onCopy}>
        在规划端会话里进行：
      </NextStep>,
    );
    const root = container.firstElementChild as HTMLElement;
    const cmd = root.querySelector('.tt-cmd--sm') as HTMLElement;
    expect(cmd, '应有 CommandLine size=sm').not.toBeNull();
    expect(cmd.querySelector('code')!.textContent).toBe('/plan-task logs-cat');
    const last = root.lastElementChild as HTMLElement;
    expect(last === cmd || last.contains(cmd), '命令行是下一步里最后一块').toBe(true);
    fireEvent.click(cmd.querySelector('button[aria-label="复制命令"]')!);
    expect(onCopy).toHaveBeenCalledWith('/plan-task logs-cat');
    expect(root.hasAttribute('role')).toBe(false);
  });
});

describe('components/index 的运行时导出', () => {
  it('六个新组件与两个函数都从 index 导出，原来的组件仍在', async () => {
    const idx: any = await import('../src/components');
    for (const name of ['TextViewer', 'SafeMarkdown', 'EffortPair', 'MaskedValue', 'CommandLine', 'NextStep', 'isMaskedPlaceholder', 'dispatchCommand',
      'Button', 'Tag', 'StatusTag', 'Card', 'Banner', 'IconButton', 'Tooltip', 'Menu', 'Dialog', 'Drawer', 'Toast', 'SegmentedControl', 'Switch',
      'Checkbox', 'Tabs', 'TextField', 'Select', 'Table', 'KeyValueList', 'EmptyState', 'Skeleton', 'ConnectionPill', 'Breadcrumb']) {
      expect(typeof idx[name], name + ' 应从 components/index 导出').toBe('function');
    }
    for (const hidden of ['stripAnsi', 'parseMarkdown']) {
      expect(idx[hidden], hidden + ' 是内部纯函数，不从 index 导出').toBeUndefined();
    }
  });
});
"""

# ---- table：S1、S2（D08） ----
PROBE_TABLE = PRELUDE + r"""
let Table: any;

beforeAll(async () => {
  Table = (await import('../src/components/Table')).Table;
});

const COLUMNS = [
  { key: 'name', header: '名称' },
  { key: 'n', header: '数量', numeric: true },
  { key: 'id', header: '编号', mono: true },
];
const mk = (keys: string[]) => keys.map((k) => ({ id: k, name: '行' + k, n: 1 }));

function mount(keys: string[], props: any = {}) {
  const onRowOpen = vi.fn();
  let cur = { ...props };
  const el = (ks: string[]) => (
    <Table aria-label="表" columns={COLUMNS} rows={mk(ks)} rowKey={(r: any) => r.id} onRowOpen={onRowOpen} {...cur} />
  );
  const r = render(el(keys));
  const trs = () => Array.from(r.container.querySelectorAll('tbody tr')) as HTMLElement[];
  const zero = () => trs().filter((t) => t.getAttribute('tabindex') === '0').map((t) => textOf(t.children[2]));
  const rowFor = (k: string) => trs().find((t) => textOf(t.children[2]) === k) as HTMLElement;
  const set = (ks: string[], patch: any = {}) => {
    cur = { ...cur, ...patch };
    r.rerender(el(ks));
  };
  return { ...r, trs, zero, rowFor, set, onRowOpen };
}

describe('S2 数字列表头', () => {
  it('数字列的 th 也带 tt-num，其余列的 th 不带；td 的规则照旧', () => {
    const { container } = mount(['a', 'b']);
    const ths = Array.from(container.querySelectorAll('thead th'));
    expect(ths.map((t) => t.classList.contains('tt-num'))).toEqual([false, true, false]);
    expect(ths.map((t) => t.getAttribute('scope'))).toEqual(['col', 'col', 'col']);
    for (const tr of Array.from(container.querySelectorAll('tbody tr'))) {
      expect(Array.from(tr.children).map((td) => td.classList.contains('tt-num'))).toEqual([false, true, false]);
    }
  });
});

describe('S1 当前行按 key 记', () => {
  it('缺省第一行；有 selectedKey 时是选中行；selectedKey 不在 rows 里时回到第一行；恰一行 tabIndex=0', () => {
    expect(mount(['a', 'b', 'c']).zero()).toEqual(['a']);
    const b = mount(['a', 'b', 'c'], { selectedKey: 'c' });
    expect(b.zero()).toEqual(['c']);
    b.unmount();
    expect(mount(['a', 'b'], { selectedKey: 'zz' }).zero()).toEqual(['a']);
  });

  it('rows 变少：当前行没了，回到选中行；没有选中行回到第一行', () => {
    const a = mount(['a', 'b', 'c', 'd']);
    focusOn(a.rowFor('d'));
    expect(a.zero()).toEqual(['d']);
    a.set(['a', 'b']);
    expect(a.zero()).toEqual(['a']);
    a.unmount();
    const b = mount(['a', 'b', 'c', 'd'], { selectedKey: 'b' });
    focusOn(b.rowFor('d'));
    expect(b.zero()).toEqual(['d']);
    b.set(['a', 'b']);
    expect(b.zero()).toEqual(['b']);
  });

  it('rows 晚于 selectedKey 到达：先是空表（没有行），rows 到了之后选中行是当前行', () => {
    const { trs, zero, set, container } = mount([], { selectedKey: 'c' });
    expect(trs().length).toBe(0);
    expect(zero()).toEqual([]);
    expect(container.querySelectorAll('thead th').length).toBe(3);
    set(['a', 'b', 'c']);
    expect(zero()).toEqual(['c']);
    expect(trs().length).toBe(3);
  });

  it('排序或插入：当前行跟着 key 走，不跟下标走', () => {
    const { zero, set, rowFor } = mount(['a', 'b', 'c']);
    focusOn(rowFor('c'));
    expect(zero()).toEqual(['c']);
    set(['c', 'b', 'a']);
    expect(zero()).toEqual(['c']);
    set(['x', 'c', 'b', 'a']);
    expect(zero()).toEqual(['c']);
    set(['x', 'y', 'c', 'b', 'a']);
    expect(zero()).toEqual(['c']);
    set(['x', 'b', 'a']);
    expect(zero(), '当前行没了，没有选中行，回到第一行').toEqual(['x']);
  });

  it('selectedKey 变化时清掉当前 key：当前行回到新的选中行；变成 undefined 回到第一行', () => {
    const { zero, set, rowFor } = mount(['a', 'b', 'c']);
    focusOn(rowFor('c'));
    expect(zero()).toEqual(['c']);
    set(['a', 'b', 'c'], { selectedKey: 'b' });
    expect(zero()).toEqual(['b']);
    focusOn(rowFor('c'));
    expect(zero()).toEqual(['c']);
    set(['a', 'b', 'c'], { selectedKey: undefined });
    expect(zero()).toEqual(['a']);
  });

  it('键盘按 key 走：重新排序之后 ArrowDown 去新顺序里的下一行', () => {
    const { zero, set, rowFor } = mount(['a', 'b', 'c']);
    focusOn(rowFor('b'));
    set(['c', 'b', 'a']);
    expect(zero()).toEqual(['b']);
    const notPrevented = fireEvent.keyDown(rowFor('b'), { key: 'ArrowDown' });
    expect(notPrevented, 'ArrowDown 应被 preventDefault').toBe(false);
    expect(zero()).toEqual(['a']);
    expect(document.activeElement).toBe(rowFor('a'));
  });

  it('点击行：调 onRowOpen(key)，被点的行成为当前行；Enter 同样', () => {
    const { zero, rowFor, onRowOpen } = mount(['a', 'b', 'c']);
    fireEvent.click(rowFor('c'));
    expect(onRowOpen).toHaveBeenCalledTimes(1);
    expect(onRowOpen).toHaveBeenCalledWith('c');
    expect(zero()).toEqual(['c']);
    focusOn(rowFor('b'));
    fireEvent.keyDown(rowFor('b'), { key: 'Enter' });
    expect(onRowOpen).toHaveBeenCalledTimes(2);
    expect(onRowOpen).toHaveBeenLastCalledWith('b');
  });

  it('rows 为空时没有行，也不抛错', () => {
    const { trs, zero } = mount([]);
    expect(trs().length).toBe(0);
    expect(zero()).toEqual([]);
  });
});
"""

# ---- gaps：S5 与三处缺口（D09） ----
PROBE_GAPS = PRELUDE + r"""
describe('S5 value 无效时第一项可 Tab 到', () => {
  it('SegmentedControl：value 不在选项里 → 恰一个 tabIndex=0 且是第一项，aria-checked 全为 false；value 有效时只有选中项', async () => {
    const { SegmentedControl } = await import('../src/components/SegmentedControl');
    const options = [{ value: 'a', label: '甲' }, { value: 'b', label: '乙' }, { value: 'c', label: '丙' }];
    const mk = (value: string) => render(<SegmentedControl aria-label="分段" options={options} value={value} onChange={() => {}} />);
    const a = mk('zz');
    const radios = () => Array.from(document.querySelectorAll('[role="radio"]')) as HTMLElement[];
    expect(radios().map((r) => r.getAttribute('tabindex'))).toEqual(['0', '-1', '-1']);
    expect(radios().map((r) => r.getAttribute('aria-checked'))).toEqual(['false', 'false', 'false']);
    a.unmount();
    const b = mk('b');
    expect(radios().map((r) => r.getAttribute('tabindex'))).toEqual(['-1', '0', '-1']);
    expect(radios().map((r) => r.getAttribute('aria-checked'))).toEqual(['false', 'true', 'false']);
    b.unmount();
    const empty = render(<SegmentedControl aria-label="空" options={[]} value="" onChange={() => {}} />);
    expect(empty.container.querySelectorAll('[role="radio"]').length).toBe(0);
  });

  it('Tabs：value 不在页签里 → 恰一个 tabIndex=0 且是第一个页签，aria-selected 全为 false；value 有效时只有当前页签', async () => {
    const { Tabs } = await import('../src/components/Tabs');
    const items = [{ id: 't1', label: '一' }, { id: 't2', label: '二' }, { id: 't3', label: '三' }];
    const mk = (value: string) => render(<Tabs aria-label="页签" items={items} value={value} onChange={() => {}}>内容</Tabs>);
    const tabs = () => Array.from(document.querySelectorAll('[role="tab"]')) as HTMLElement[];
    const a = mk('nope');
    expect(tabs().map((t) => t.getAttribute('tabindex'))).toEqual(['0', '-1', '-1']);
    expect(tabs().map((t) => t.getAttribute('aria-selected'))).toEqual(['false', 'false', 'false']);
    a.unmount();
    const b = mk('t2');
    expect(tabs().map((t) => t.getAttribute('tabindex'))).toEqual(['-1', '0', '-1']);
    expect(tabs().map((t) => t.getAttribute('aria-selected'))).toEqual(['false', 'true', 'false']);
  });
});

describe('缺口 1：每个页签的 aria-controls 都指向同一个面板', () => {
  it('value 有效与无效两种情形下，每个页签的 aria-controls 都等于面板的 id，面板存在', async () => {
    const { Tabs } = await import('../src/components/Tabs');
    const items = [{ id: 't1', label: '一' }, { id: 't2', label: '二' }, { id: 't3', label: '三' }];
    for (const value of ['t1', 't3', 'nope']) {
      const { unmount } = render(<Tabs aria-label="页签" items={items} value={value} onChange={() => {}}>内容</Tabs>);
      const panel = document.querySelector('[role="tabpanel"]') as HTMLElement;
      expect(panel, value).not.toBeNull();
      expect(panel.id).not.toBe('');
      const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
      expect(tabs.length).toBe(3);
      for (const t of tabs) expect(t.getAttribute('aria-controls'), value + ' 的每个页签').toBe(panel.id);
      expect(document.getElementById(panel.getAttribute('aria-labelledby') || '')).not.toBeNull();
      unmount();
    }
  });
});

describe('缺口 2：空格带 repeat', () => {
  it('Switch：repeat 的空格照样 preventDefault 但不切换；普通空格切换一次；别的键不处理', async () => {
    const { Switch } = await import('../src/components/Switch');
    const onChange = vi.fn();
    const { container } = render(<Switch checked={false} onChange={onChange} label="开关" />);
    const el = container.querySelector('[role="switch"]') as HTMLElement;
    focusOn(el);
    const rep = fireEvent.keyDown(el, { key: ' ', repeat: true });
    expect(rep, 'repeat 的空格应被 preventDefault').toBe(false);
    expect(onChange).not.toHaveBeenCalled();
    const once = fireEvent.keyDown(el, { key: ' ' });
    expect(once, '空格应被 preventDefault').toBe(false);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(true);
    const other = fireEvent.keyDown(el, { key: 'Enter' });
    expect(other, 'Enter 不处理').toBe(true);
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it('Checkbox：同上', async () => {
    const { Checkbox } = await import('../src/components/Checkbox');
    const onChange = vi.fn();
    const { container } = render(<Checkbox checked={true} onChange={onChange} label="复选" />);
    const el = container.querySelector('[role="checkbox"]') as HTMLElement;
    focusOn(el);
    expect(fireEvent.keyDown(el, { key: ' ', repeat: true })).toBe(false);
    expect(onChange).not.toHaveBeenCalled();
    expect(fireEvent.keyDown(el, { key: ' ' })).toBe(false);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(false);
    expect(fireEvent.keyDown(el, { key: 'Enter' })).toBe(true);
    expect(onChange).toHaveBeenCalledTimes(1);
  });
});

describe('缺口 3：关闭态胶囊按 Esc 放过', () => {
  it('关着时 Esc 既不 stopPropagation 也不 preventDefault；打开时关闭、不往外传、焦点留在胶囊', async () => {
    const { ConnectionPill } = await import('../src/components/ConnectionPill');
    const outer = vi.fn();
    const doc = vi.fn();
    document.addEventListener('keydown', doc);
    try {
      const { container } = render(
        <div onKeyDown={outer}>
          <ConnectionPill state="connected" pid={1} startedAt="2026-10-20" stream="正常" />
        </div>,
      );
      const btn = container.querySelector('button.tt-pill') as HTMLElement;
      focusOn(btn);
      expect(btn.getAttribute('aria-expanded')).toBe('false');
      const notPrevented = fireEvent.keyDown(btn, { key: 'Escape' });
      expect(notPrevented, '关着时 Esc 不该被 preventDefault').toBe(true);
      expect(outer, '关着时 Esc 应往外传（React 处理器）').toHaveBeenCalledTimes(1);
      expect(doc, '关着时 Esc 应一路传到 document').toHaveBeenCalledTimes(1);
      fireEvent.click(btn);
      expect(btn.getAttribute('aria-expanded')).toBe('true');
      fireEvent.keyDown(btn, { key: 'Escape' });
      expect(btn.getAttribute('aria-expanded'), '打开时 Esc 关闭').toBe('false');
      expect(outer, '打开时 Esc 不往外传').toHaveBeenCalledTimes(1);
      expect(doc).toHaveBeenCalledTimes(1);
      expect(document.activeElement).toBe(btn);
    } finally {
      document.removeEventListener('keydown', doc);
    }
  });
});
"""

# ---- showcase：EvidenceShowcase（D11，过渡） ----
PROBE_SHOWCASE = PRELUDE + r"""
let Showcase: any;
let FormsShowcase: any;

beforeAll(async () => {
  Showcase = (await import('../src/showcase/EvidenceShowcase')).default;
  FormsShowcase = (await import('../src/showcase/FormsShowcase')).default;
});

const DEMOS: string[] = __DEMOS__;
const EXISTING: string[] = __EXISTING__;
const ESC = '\u001b';

function demo(name: string): HTMLElement {
  const nodes = document.querySelectorAll('[data-demo="' + name + '"]');
  expect(nodes.length, '应恰有一个 data-demo="' + name + '" 的节').toBe(1);
  return nodes[0] as HTMLElement;
}
async function settle(cond: () => boolean, label: string) {
  for (let i = 0; i < 120; i += 1) {
    if (cond()) return;
    await act(async () => {
      await new Promise((r) => setTimeout(r, 25));
    });
  }
  throw new Error('等待超时：' + label);
}
async function press(btn: HTMLElement) {
  await act(async () => {
    fireEvent.click(btn);
  });
}
function shown(sec: HTMLElement, n: number) {
  return new RegExp('已显示\\s*' + n + '\\s*页').test(textOf(sec));
}

describe('EvidenceShowcase 演示', () => {
  it('七节，data-demo 依次为约定值，每节是 section.showcase__section 且有一个 h2.showcase__h2（标题不含 Button）；不与已有的 16 个重复', () => {
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

  it('不渲染 role=status、对话框、菜单；没有文字的按钮都有 aria-label；按钮文字与节文字不含「亮」「暗」「跟随系统」', () => {
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

  it('W1 样例在 DOM 里只是文字：没有 img、script、a、带 on 或 href 的元素，没有 ESC 字符，也没有 [31m', () => {
    render(<Showcase />);
    expect(document.body.querySelectorAll('img, script, a, iframe, object, embed, style, link').length).toBe(0);
    expect(document.body.querySelectorAll('[onerror], [href], [src], [srcdoc]').length).toBe(0);
    const sec = demo('text-viewer');
    const text = sec.textContent || '';
    expect(text).toContain('<img src=x onerror=alert(1)>');
    expect(text).toContain('<script>alert(1)</script>');
    expect(text).toContain('已按合同实现 logs cat。');
    expect(text).toContain('- self_checks: V01–V08 通过');
    expect(text).toMatch(/https?:\/\/\S+/);
    expect((document.body.textContent || '').includes(ESC)).toBe(false);
    expect((document.body.textContent || '').includes('[31m')).toBe(false);
    expect(sec.querySelector('.tt-viewer')).not.toBeNull();
  });

  it('text-viewer 一节：[继续加载] 依次加到三页、到末尾；分片显示第 2/2 片；模拟文件已变化出提示条，[从头读取] 回第 1 页', async () => {
    render(<Showcase />);
    const sec = demo('text-viewer');
    expect(shown(sec, 1), '初始显示 1 页').toBe(true);
    for (let i = 0; i < 6 && !textOf(sec).includes('已到末尾'); i += 1) {
      const btns = buttonsByText(sec, '继续加载');
      expect(btns.length, '还没到末尾时应有 [继续加载]').toBeGreaterThan(0);
      await press(btns[0]);
      await settle(() => buttonsByText(sec, '正在加载…').length === 0, '加载完成');
    }
    expect(shown(sec, 3), '加载完应是 3 页').toBe(true);
    expect(textOf(sec)).toContain('已到末尾');
    expect(textOf(sec)).toMatch(/第\s*2\/2\s*片/);
    expect(buttonsByText(sec, '继续加载').length).toBe(0);
    await press(buttonByText(sec, '模拟文件已变化'));
    await settle(() => sec.querySelector('.tt-banner') !== null, '提示条出现');
    const banner = sec.querySelector('.tt-banner') as HTMLElement;
    expect(textOf(banner)).toContain('文件已变化');
    await press(buttonByText(banner, '从头读取'));
    await settle(() => shown(sec, 1), '回到第 1 页');
    expect(sec.querySelector('.tt-banner'), '重新读取后提示条消失').toBeNull();
  });

  it('text-viewer-jsonl 一节：隐藏行的两种说明、第 1/2 片；[继续加载] 给第 2/2 片，最后一页到末尾', async () => {
    render(<Showcase />);
    const sec = demo('text-viewer-jsonl');
    const t0 = textOf(sec);
    expect(t0).toContain('这一行不是合法 JSON，已隐藏');
    expect(t0).toContain('这一行超过 4 MiB，已隐藏');
    expect(t0).toMatch(/第\s*1\/2\s*片/);
    expect(t0).toContain('agent_start');
    for (let i = 0; i < 6 && !textOf(sec).includes('已到末尾'); i += 1) {
      const btns = buttonsByText(sec, '继续加载');
      expect(btns.length).toBeGreaterThan(0);
      await press(btns[0]);
      await settle(() => buttonsByText(sec, '正在加载…').length === 0, '加载完成');
    }
    expect(textOf(sec)).toContain('已到末尾');
    expect(textOf(sec)).toMatch(/第\s*2\/2\s*片/);
  });

  it('safe-markdown 一节：摘要原文（标题、列表）、表、代码块、粗斜体、蛇形名；https 链接渲染成按钮加网址，点了只在旁边显示「上次请求打开：…」；javascript: 链接没有按钮和网址', async () => {
    render(<Showcase />);
    const sec = demo('safe-markdown');
    const h2s = Array.from(sec.querySelectorAll('h2:not(.showcase__h2)')).map((e) => textOf(e));
    expect(h2s).toContain('logs-cat.v2 / attempt-002');
    expect(Array.from(sec.querySelectorAll('h3')).map((e) => textOf(e))).toContain('复审需要关注');
    expect(Array.from(sec.querySelectorAll('li')).some((li) => textOf(li).includes('基线：9461d31'))).toBe(true);
    expect(sec.querySelector('table th')).not.toBeNull();
    const ths = Array.from(sec.querySelectorAll('table th')).map((t) => t.getAttribute('class') || '');
    expect(new Set(ths).size, '表里有带对齐的列').toBeGreaterThan(1);
    expect(sec.querySelector('pre code')).not.toBeNull();
    expect(sec.querySelector('strong')).not.toBeNull();
    expect(sec.querySelector('em')).not.toBeNull();
    expect(textOf(sec)).toMatch(/[A-Za-z]+_[A-Za-z_]+/);
    expect(sec.querySelectorAll('img, script, a, iframe, b, i, u, blockquote, hr, del, object, embed, style, link, form, input, details, summary').length).toBe(0);
    const links = Array.from(sec.querySelectorAll('button')).filter((b) => b.nextElementSibling && b.nextElementSibling.tagName === 'SPAN' && /^https?:\/\//.test(textOf(b.nextElementSibling)));
    expect(links.length, '应有 https 链接（按钮加紧跟的网址 span）').toBeGreaterThan(0);
    for (const el of Array.from(sec.querySelectorAll('button, span'))) {
      expect(textOf(el), '被拒的 javascript: 链接不渲染网址或按钮').not.toMatch(/^javascript:/i);
    }
    const url = textOf(links[0].nextElementSibling);
    await press(links[0] as HTMLElement);
    await settle(() => /上次请求打开：\s*https?:\/\/\S+/.test(textOf(sec)), '上次请求打开');
    expect(textOf(sec).replace(/：\s+/g, '：')).toContain('上次请求打开：' + url);
    expect(document.querySelectorAll('[role="dialog"], [role="alertdialog"]').length).toBe(0);
  });

  it('effort 一节：六种情形的 data-state 与整段文字；masked-value 一节：四种占位', () => {
    render(<Showcase />);
    const eff = Array.from(demo('effort').querySelectorAll('.tt-effort')) as HTMLElement[];
    expect(eff.length).toBe(6);
    expect(eff.map((e) => e.getAttribute('data-state')).sort()).toEqual(['differs', 'differs', 'none', 'same', 'same', 'unknown']);
    const texts = eff.map((e) => textOf(e));
    expect(texts).toContain('—');
    expect(texts.filter((t) => /^要求 \S+ · 生效 未知$/.test(t)).length).toBe(1);
    expect(texts.filter((t) => /与要求不同$/.test(t)).length).toBe(2);
    expect(texts.some((t) => /^要求 \S+ · 生效 \S+、\S+$/.test(t))).toBe(true);
    const masked = Array.from(demo('masked-value').querySelectorAll('span[title="内核已遮蔽"]')).map((e) => e.textContent);
    expect(masked.slice().sort()).toEqual(['（含疑似凭据，不显示）', '（值不显示）', '<redacted>', '（疑似凭据的键名）'].sort());
  });

  it('command-line 一节：md 用 dispatchCommand(config preset use economy)，sm 用 /plan-task logs-cat；next-step 一节：带命令与不带命令各一个', () => {
    render(<Showcase />);
    const cmd = demo('command-line');
    const codes = Array.from(cmd.querySelectorAll('code')).map((c) => c.textContent);
    expect(codes).toContain('bash scripts/dispatch-pi.sh config preset use economy');
    expect(codes).toContain('/plan-task logs-cat');
    const sm = cmd.querySelector('.tt-cmd--sm') as HTMLElement;
    expect(sm && sm.querySelector('code')!.textContent).toBe('/plan-task logs-cat');
    expect(cmd.querySelectorAll('button[aria-label="复制命令"]').length).toBe(2);
    const next = demo('next-step');
    expect(next.querySelectorAll('.tt-cmd--sm').length, '带命令的下一步里有一个 sm 命令行').toBe(1);
    expect(next.querySelectorAll('svg').length, '两个下一步各有一个信息图标（加上命令行的复制图标）').toBeGreaterThanOrEqual(2);
    expect(next.querySelector('[role]')).toBeNull();
  });

  it('FormsShowcase：连接胶囊那一行加了类 showcase-pill-row，仍是 showcase__row，三个胶囊都在里面（S4b）', () => {
    render(<FormsShowcase />);
    const sec = demo('connection');
    const row = sec.querySelector('.showcase-pill-row') as HTMLElement;
    expect(row, '胶囊行应带 showcase-pill-row').not.toBeNull();
    expect(row.classList.contains('showcase__row')).toBe(true);
    expect(row.querySelectorAll('button.tt-pill').length).toBe(3);
    expect(sec.querySelectorAll('.showcase-pill-row').length).toBe(1);
  });
});
"""

# (键, 探针源码, 需要先存在的仓库文件)
PROBE_SPECS = {
    "ansi": (PROBE_ANSI, [f"{EVID_REL}/ansi.ts"]),
    "w1": (PROBE_W1, [f"{COMP_REL}/TextViewer.tsx"]),
    "pages": (PROBE_PAGES, [f"{COMP_REL}/TextViewer.tsx"]),
    "md": (PROBE_MD, [f"{COMP_REL}/SafeMarkdown.tsx"]),
    "mdperf": (PROBE_MDPERF, [f"{COMP_REL}/SafeMarkdown.tsx", f"{EVID_REL}/markdown.ts"]),
    "effort": (PROBE_EFFORT, [f"{COMP_REL}/EffortPair.tsx"]),
    "atoms": (PROBE_ATOMS, [f"{COMP_REL}/MaskedValue.tsx", f"{COMP_REL}/CommandLine.tsx", f"{COMP_REL}/NextStep.tsx",
                            f"{SRC_REL}/icons/index.tsx", f"{COMP_REL}/Banner.tsx", f"{COMP_REL}/index.ts"]),
    "table": (PROBE_TABLE, [f"{COMP_REL}/Table.tsx"]),
    "gaps": (PROBE_GAPS, [f"{COMP_REL}/SegmentedControl.tsx", f"{COMP_REL}/Tabs.tsx", f"{COMP_REL}/Switch.tsx",
                          f"{COMP_REL}/Checkbox.tsx", f"{COMP_REL}/ConnectionPill.tsx"]),
    "showcase": (PROBE_SHOWCASE, [f"{SHOW_REL}/EvidenceShowcase.tsx", f"{SHOW_REL}/FormsShowcase.tsx"]),
}
# 组件探针先跑，演示探针最后跑
PROBE_ORDER = ("ansi", "w1", "pages", "md", "mdperf", "effort", "atoms", "table", "gaps", "showcase")


def probe_count(source):
    """探针里 ``it(`` 开头的行数；循环里的 it 一行可能跑多条，所以通过数只要求不少于它。"""
    return len(re.findall(r"^\s*it\(", source, re.M))


def build_probe_source(key):
    source = PROBE_SPECS[key][0]
    if key == "atoms":
        specs = {"LockIcon": canvas_icon(404), "CopyIcon": canvas_icon(409), "EyeOffIcon": {"rect": None, "paths": EYE_OFF_DS}}
        assert specs["LockIcon"] == LOCK_CONTRACT and specs["CopyIcon"] == COPY_CONTRACT, "（门禁自身）领域板的图标与合同不一致"
        source = source.replace("__ICON_SPECS__", json.dumps(specs, ensure_ascii=False))
    if key == "showcase":
        source = source.replace("__DEMOS__", json.dumps(list(EVIDENCE_DEMOS))).replace("__EXISTING__", json.dumps(list(EXISTING_DEMOS)))
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


# 流水线前后不该变的文件（相对 desktop/web；合同 P10）
WATCHED = ("package.json", "package-lock.json", "index.html", "vite.config.ts", "tsconfig.json",
           "src/styles/tokens.css", "src/styles/fonts.css", "src/styles/base.css", "src/main.tsx", "src/App.tsx", "src/App.css")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not any(comp_path(name, "tsx").is_file() for name in NEW_COMPONENTS):
        pipe.reason = ("候选里还没有任何新组件文件（基线），没有东西可测，未调用 npm；"
                       "候选写出新组件后，流水线才会运行 npm ci、构建、Vitest 和探针")
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
                name = f"probe-{uid}-t007-{key}.test.tsx"
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

def test_s1_d12_files_and_exports():
    """S1 / D12（合同第 6、7 条）：6 个新组件的 .tsx 与 .css、components/evidence/ 下 ansi.ts、viewerLines.ts、markdown.ts 都在；
    components/index.ts 导出 6 个组件、它们的 Props 类型与 isMaskedPlaceholder、dispatchCommand，原来的 23 个组件与 Props 类型仍在，
    去掉注释后不出现 overlay，不导出 evidence/ 里的内部函数。"""
    need_components(*NEW_COMPONENTS)
    for mod in EVIDENCE_MODULES:
        need_file(f"{EVID_REL}/{mod}.ts")
    fail_if(index_problems(_read(need_file(f"{COMP_REL}/index.ts"))), "components/index.ts 的导出")


def test_s2_d12_no_forbidden_words_in_src():
    """S2 / D12（合同公共约定）：desktop/web/src/**/*.{ts,tsx} 全文（含注释与字符串）里没有 dangerouslySetInnerHTML、innerHTML、
    outerHTML、insertAdjacentHTML、eval(、new Function、document.write、srcdoc、createContextualFragment、DOMParser。
    先要求新代码已经存在（基线上这些词本来就一个都没有，空过没有意义）。"""
    need_components(*NEW_COMPONENTS)
    fail_if(forbidden_word_problems(src_ts_files()), "src 里的禁用词")


def test_s3_d12_new_sources_rules():
    """S3 / D12（合同公共约定）：6 个新组件与 components/evidence/ 下的源码里不出现 href、src=、target=（全文），不渲染 role=status
    （去注释后），不调用 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver。"""
    need_components(*NEW_COMPONENTS)
    for mod in EVIDENCE_MODULES:
        need_file(f"{EVID_REL}/{mod}.ts")
    fail_if(new_source_problems(evidence_source_files()), "新组件与 evidence/ 的源码")


def test_s3_d03_markdown_module_is_pure():
    """S3 / D03（合同第 7 条）：evidence/markdown.ts 是纯函数模块，不引入 React，导出 parseMarkdown；ansi.ts 导出 stripAnsi。"""
    md = strip_ts_comments(_read(need_file(f"{EVID_REL}/markdown.ts")))
    problems = []
    if re.search(r"""from\s+['"]react(?:-dom)?(?:/[^'"]*)?['"]|require\(\s*['"]react""", md):
        problems.append("markdown.ts 不该引入 React")
    if not re.search(r"export\s+(?:function|const)\s+parseMarkdown\b|export\s*\{[^}]*\bparseMarkdown\b", md):
        problems.append("markdown.ts 应导出 parseMarkdown")
    ansi = strip_ts_comments(_read(need_file(f"{EVID_REL}/ansi.ts")))
    if not re.search(r"export\s+(?:function|const)\s+stripAnsi\b|export\s*\{[^}]*\bstripAnsi\b", ansi):
        problems.append("ansi.ts 应导出 stripAnsi")
    fail_if(problems, "evidence/ 的纯函数模块")


def test_s4_d07_new_icons_match_contract():
    """S4 / D07（合同第 1 条）：icons/index.tsx 末尾追加 LockIcon（rect 18×11 x3 y11 rx2 ry2 加 path M7 11V7a5 5 0 0 1 10 0v4，领域板 :404）、
    CopyIcon（rect 14×14 x8 y8 rx2 ry2 加 path M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2，领域板 :409）、EyeOffIcon
    （站主核实的四条 path，依次 M10.733…、M14.084…、M17.479…、m2 2 20 20），都沿用 Svg 包装；领域板的 :404、:409 与合同写的一致。"""
    fail_if(icon_problems(_read(need_file(f"{SRC_REL}/icons/index.tsx"))), "新增图标")


def test_s5_d01_text_viewer_css_values():
    """S5 / D01、D02（合同第 8 条）：TextViewer.css 的取值——根 --tt-surface-1、1px --tt-border、--tt-radius-lg、overflow: hidden；
    头高 40、左 --tt-space-3 右 --tt-space-2、下边框；标题 --tt-mono-sm 单行省略；切换钮高 28、左右 --tt-space-2、--tt-radius-md、透明底、
    --tt-text-2、--tt-text-sm，按下态底 --tt-surface-3；主体上下 --tt-space-2、overflow-x: auto；行 --tt-mono-md；行号列 44 右对齐、
    右内边距 --tt-space-3、--tt-text-3；文字最小高 20、右内边距 --tt-space-3；white-space: pre 与 pre-wrap + word-break: break-all；
    隐藏行说明 --tt-text-3 斜体、与图标间距 --tt-space-1；分片提示 --tt-text-caption、--tt-text-3、user-select: none（行号也要 user-select: none）；
    底栏 --tt-surface-2、上边框、内边距 --tt-space-2 与 --tt-space-3、--tt-text-caption、--tt-text-3、按钮靠右；提示条外边距。"""
    css = comp_css("TextViewer")
    fail_if(css_spec_problems(css, "TextViewer.css", VIEWER_SPECS) + viewer_extra_problems(css), "TextViewer.css")


def test_s5_d03_safe_markdown_css_values():
    """S5 / D03（合同第 9 条）：SafeMarkdown.css 的取值——根 --tt-text-md/--tt-text-1、块间距 --tt-space-2、标题外边距 0 与三档标题字体、
    列表左内边距 --tt-space-5 与项间距、项里的 p 外边距 0、段落 pre-wrap、行内代码与代码块的取值、表格（--tt-text-sm、格内边距、
    表头 --tt-surface-2/--tt-title-sm/--tt-text-2、右对齐与居中的类、外套 overflow-x: auto）、链接钮（--tt-link、透明底、无边框、
    无内边距、继承字体、悬停下划线）、网址（--tt-mono-sm、--tt-text-3、左外边距 --tt-space-1）。"""
    fail_if(css_spec_problems(comp_css("SafeMarkdown"), "SafeMarkdown.css", MD_SPECS), "SafeMarkdown.css")


def test_s5_d04_effort_pair_css_values():
    """S5 / D04（合同第 10 条）：EffortPair.css 根 .tt-effort 是 inline-flex、居中、间距 --tt-space-1、--tt-text-sm、可换行；
    标签与「未知」「—」用 --tt-text-3，档位名 --tt-mono-sm；EffortPair.tsx 里的警告标签用 Tag tone=warning，不用金色色调。"""
    css = comp_css("EffortPair")
    problems = css_spec_problems(css, "EffortPair.css", EFFORT_SPECS)
    code = strip_ts_comments(comp_tsx("EffortPair"))
    if not re.search(r"""tone\s*=\s*\{?\s*["']warning["']""", code):
        problems.append("EffortPair.tsx 的警告标签应是 Tag tone=\"warning\"")
    if re.search(r"""["'](?:attention|brand)["']|--tt-gold|--tt-accent""", code + css):
        problems.append("EffortPair 不用金色（attention、brand 色调与 --tt-gold、--tt-accent 令牌）")
    fail_if(problems, "EffortPair")


def masked_order_problems(css):
    for _sel, decls in parse_rules(css):
        names = [n for n, _v in decls]
        if "font-style" in names and "font" in names:
            if names.index("font") > names.index("font-style"):
                return ["MaskedValue.css 里 font 简写写在了 font-style 之后（font 简写会重置字形，应先写 font: var(--tt-text-sm) 再写 font-style: italic）"]
            font = [v for n, v in decls if n == "font"][-1]
            style = [v for n, v in decls if n == "font-style"][-1]
            problems = []
            if cv(font) != "var(--tt-text-sm)":
                problems.append(f"MaskedValue.css 的 font 应是 var(--tt-text-sm)，实际 {font}")
            if cv(style) != "italic":
                problems.append(f"MaskedValue.css 的 font-style 应是 italic，实际 {style}")
            return problems
    return ["MaskedValue.css 里没有一条规则同时写 font 与 font-style: italic"]


def test_s5_d05_d06_atom_css_values():
    """S5 / D05、D06（合同第 11、12 条）：MaskedValue.css（inline-flex、间距 --tt-space-1、--tt-text-3；先写 font: var(--tt-text-sm) 再写
    font-style: italic）；CommandLine.css（md：flex 居中、间距 --tt-space-1、最小高 36、内边距 --tt-space-1 左 --tt-space-2、--tt-radius-md、
    --tt-surface-2、1px --tt-border，code 的字体色与换行；sm：inline-flex、高 28、间距 --tt-space-0_5、内边距上下 0 右 --tt-space-0_5
    左 --tt-space-2，code --tt-mono-sm，复制钮缩成 24、圆角 sm、图标 14，选择器 .tt-cmd--sm .tt-icon-btn 的特异性不低于 (0,2,0)）；
    NextStep.css（flex 居中可换行、间距 --tt-space-2、内边距、--tt-radius-md、info 色调、--tt-text-sm、标题 --tt-title-sm）；
    Banner.css 的 .tt-banner__action { flex: none }。"""
    need_components("MaskedValue", "CommandLine", "NextStep")
    problems = css_spec_problems(comp_css("MaskedValue"), "MaskedValue.css", MASKED_SPECS) + masked_order_problems(comp_css("MaskedValue"))
    cmd = comp_css("CommandLine")
    problems += css_spec_problems(cmd, "CommandLine.css", CMD_SPECS)
    for selector, _decls in parse_rules(cmd):
        for item in split_top(selector):
            if re.search(r"\.tt-cmd--sm\s+\.tt-icon-btn(?![\w-])", item) and specificity(item) < (0, 2, 0):
                problems.append(f"CommandLine.css 的 {item!r} 特异性 {specificity(item)} 低于 IconButton 单类规则（0,1,0）加一")
    problems += css_spec_problems(comp_css("NextStep"), "NextStep.css", NEXT_SPECS)
    problems += css_spec_problems(_read(need_file(f"{COMP_REL}/Banner.css")), "Banner.css", BANNER_ACTION_SPECS)
    fail_if(problems, "遮蔽值、命令行、下一步、提示条的样式")


def test_s5_d12_new_css_tokens_and_px_comments():
    """S5 / D12（合同公共约定）：6 份新组件 CSS 里层级、圆角、阴影、字体只用 --tt-* 令牌；除 0 与 1px 外的
    px 字面量同一行带出处注释（Table.css 的 px 注释由 S6 查；Banner.css 是 T002 的旧文件，里面旧的 px 没有注释，不在这里查）。"""
    need_components(*NEW_COMPONENTS)
    problems = []
    for label, path in new_css_files():
        assert path.is_file(), f"{path.relative_to(REPO_ROOT).as_posix()} 不存在（基线上还没有实现）"
        raw = _read(path)
        problems += token_only_problems(label, raw)
        problems += px_literal_problems(label, raw)
    fail_if(problems, "新 CSS 的令牌与出处注释")


def test_s5_d12_w4_pitfalls_in_new_sources():
    """S5 / D12（合同公共约定 W4 的坑）：新组件、evidence/ 模块、新 CSS 里不出现井号加 3/4/6/8 位十六进制字符、
    rgb( 之类颜色函数名加括号，不拼接 --tt- 令牌名（token-contract.mjs 只剥块注释、字符串也扫）。流水线里的 check:contract 另跑真实检查。"""
    need_components(*NEW_COMPONENTS)
    files = [comp_path(n, ext) for n in NEW_COMPONENTS for ext in ("tsx", "css")]
    folder = REPO_ROOT / EVID_REL
    files += sorted(folder.glob("*.ts")) if folder.is_dir() else []
    for mod in EVIDENCE_MODULES:
        need_file(f"{EVID_REL}/{mod}.ts")
    fail_if(w4_pitfall_problems(files), "W4 的坑")


def test_s6_d08_table_css():
    """S6 / D08（合同第 3 条）：Table.css 有 `.tt-table th.tt-num { text-align: right }`（特异性高于 `.tt-table th`）；`.tt-table-wrap` 的
    scroll-padding-top: 32px 且同一行注释「表头高 32（组件板 :411）」；`.tt-table tbody tr:focus-visible { outline: none }`；单元格画 2px
    --tt-focus inset 阴影（每格上下两条，首格加左边，末格加右边，只有一格时画四边）；`@media (forced-colors: active)` 里
    `tr:focus-visible { outline: 2px solid Highlight; outline-offset: -2px }`；选中行的 inset 2px 0 0 var(--tt-primary) 留在 tr 上；
    带 px 的每一行都有同一行注释。"""
    fail_if(table_css_problems(_read(need_file(f"{COMP_REL}/Table.css"))), "Table.css")


def test_s6_d08_table_tsx_no_scroll_into_view():
    """S6 / D08（合同第 3 条）：焦点环只用 CSS，Table.tsx 不调 scrollIntoView（基线上本来没有；要求 Table.tsx 已按 S1 改成按 key 记当前行：
    源码里不再有 `useState(selectedIndex` 这类下标 state）。"""
    code = strip_ts_comments(_read(need_file(f"{COMP_REL}/Table.tsx")))
    problems = []
    if re.search(r"\bscrollIntoView\b", code):
        problems.append("Table.tsx 不能调 scrollIntoView（只用 CSS 的 scroll-padding-top）")
    if re.search(r"useState\(\s*selectedIndex", code):
        problems.append("Table.tsx 仍用下标 state 记当前行（S1：应存当前行的 key）")
    fail_if(problems, "Table.tsx")


def test_transitional_s7_showcase_forms_css_and_pill_row():
    """陈列页的演示改版（整理陈列页或换成真实页面）时推翻。

    S7 / D10（合同第 5 条）：showcase-forms.css 里 `.showcase-table` 的 max-width 是 280px、max-height 仍是限高值（240px），两项同一行
    注释「演示自定」，280 那一行写明小于表的自然宽度（约 330）；`.showcase-field` 的 240px 带注释；`.showcase-pill-row { justify-content:
    flex-end }`；FormsShowcase.tsx 里连接胶囊那一行带类 showcase-pill-row（只加类，仍是 showcase__row）；EvidenceShowcase 不挂到陈列页
    （App.tsx 不引用它）。"""
    raw = _read(need_file(f"{SHOW_REL}/showcase-forms.css"))
    problems = []
    rules = parse_rules(raw)

    def decl(selector_re, name):
        for sel, decls in rules:
            if re.search(selector_re, sel):
                for n, v in decls:
                    if n == name:
                        return cv(v)
        return None

    table_sel = r"\.showcase-table(?![\w-])"
    got_width = decl(table_sel, "max-width")
    if got_width != "280px":
        problems.append(f".showcase-table 的 max-width 应是 280px，实际 {got_width}")
    if decl(table_sel, "max-height") != "240px":
        problems.append("`.showcase-table` 的 max-height 应仍是 240px（限高仍在）")
    lines = raw.splitlines()
    w_line = [ln for ln in lines if re.search(r"max-width\s*:\s*280px", ln)]
    h_line = [ln for ln in lines if re.search(r"max-height\s*:\s*240px", ln)]
    for kind, found in (("max-width: 280px", w_line), ("max-height: 240px", h_line)):
        if found and "演示自定" not in found[0]:
            problems.append(f"{kind} 那一行的注释应写「演示自定」")
    if w_line and not re.search(r"330", w_line[0]):
        problems.append("max-width: 280px 那一行的注释应写明小于表的自然宽度（约 330）")
    field = [ln for ln in lines if re.search(r"width\s*:\s*240px", ln)]
    if not field:
        problems.append("`.showcase-field` 的 width: 240px 不见了")
    elif not re.search(r"/\*.*(演示自定|画布|组件板|领域板|handoff|UI 文档).*\*/", field[0]):
        problems.append("`.showcase-field` 的 240px 应带同一行注释（演示自定或出处）")
    if decl(r"\.showcase-pill-row(?![\w-])", "justify-content") != "flex-end":
        problems.append(".showcase-pill-row 应有 justify-content: flex-end")
    tsx = strip_ts_comments(_read(need_file(f"{SHOW_REL}/FormsShowcase.tsx")))
    m = re.search(r"""className\s*=\s*["']([^"']*)["'][^>]*>\s*<ConnectionPill\b""", tsx)
    if not m:
        problems.append("FormsShowcase.tsx 里找不到连接胶囊那一行（包着第一个 ConnectionPill 的带 className 的元素）")
    else:
        classes = m.group(1).split()
        if "showcase-pill-row" not in classes or "showcase__row" not in classes:
            problems.append(f"胶囊行的类应同时有 showcase__row 与 showcase-pill-row，实际 {classes}")
    app = _read(need_file(f"{SRC_REL}/App.tsx"))
    if "EvidenceShowcase" in app:
        problems.append("App.tsx 不该引用 EvidenceShowcase（演示不挂到陈列页）")
    fail_if(problems, "陈列页修补")


SHOWCASE_NOTE = re.compile(r"演示自定|handoff|领域板|组件板|Attempt|UI 文档|写操作页|画布")


def showcase_px_note_problems(label, raw):
    """合同第 5 条 S6：每个除 0 与 1px 外的 px 字面量，同一行注释写「演示自定」或出处。"""
    problems = px_literal_problems(label, raw)
    for no, ln in enumerate(raw.splitlines(), 1):
        code = re.sub(r"/\*.*?\*/", "", ln)
        if re.search(r"(?<![\w.#-])(?!1px\b)(?!0px\b)-?\d*\.?\d+px\b", code) and not SHOWCASE_NOTE.search(ln):
            problems.append(f"{label}:{no} 尺寸注释应写「演示自定」或出处：{ln.strip()[:70]}")
    return problems


def test_s8_d10_showcase_forms_css_px_comments():
    """S8 / D10、D11（合同第 5、13 条）：showcase-forms.css 里除 0 与 1px 外的 px 字面量（240px、280px、240px 限高）同一行带注释
    （「演示自定」或出处）；showcase-evidence.css 同样（每个 px 字面量同一行注释），摘要最大宽 880px 的注释写 handoff :165；
    两份 CSS 的颜色、字体、圆角、阴影、层级只用令牌。"""
    forms = _read(need_file(f"{SHOW_REL}/showcase-forms.css"))
    evid = _read(need_file(f"{SHOW_REL}/showcase-evidence.css"))
    problems = showcase_px_note_problems("showcase-forms.css", forms) + token_only_problems("showcase-forms.css", forms)
    problems += showcase_px_note_problems("showcase-evidence.css", evid) + token_only_problems("showcase-evidence.css", evid)
    lines = [ln for ln in evid.splitlines() if re.search(r"\b880px\b", ln)]
    if not lines:
        problems.append("showcase-evidence.css 里没有摘要最大宽 880px")
    elif not re.search(r"handoff\s*:?\s*165", lines[0]):
        problems.append("880px 那一行的注释应写 handoff :165")
    fail_if(problems, "showcase-forms.css 与 showcase-evidence.css")


def test_d14_executor_tests_in_place():
    """D14（合同“执行端测试”）：8 份执行端测试都在（evidence-text-viewer、evidence-markdown、evidence-effort、evidence-atoms、
    evidence-showcase、evidence-static、forms-patches、forms-patches-css），各至少一条用例，不出现 skip、only、todo、fails。"""
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


def test_d01_probe_strip_ansi(pipeline):
    """ansi 探针 / D01（合同第 7 条）：stripAnsi 去 CSI（ESC[ 与 0x9B 开头，含私有参数、中间字节）、去 OSC（到 BEL 或 ESC 加反斜杠）、
    去其余 ESC 双字符序列，最后剩下的 ESC 与 U+009B 一律去掉；普通文字（含没有 ESC 的 [31m）原样；256 KiB 的八种病态输入各在 1 秒内完成。"""
    assert_probe_ok(pipeline, "ansi")


def test_d01_probe_w1_text_only(pipeline):
    """w1 探针 / D01（W1）：输入含 <img src=x onerror=alert(1)>、<script>alert(1)</script>、<a href> 与 <style>、带 ESC[31m 与 ESC[0m 的红色文字、
    OSC 序列、一个网址；DOM 里没有 img、script、a、style 等元素，行里没有带 style 属性的元素，文字原样出现，ESC 与 [31m 都不出现，
    网址不自动变链接；行号 1–9 带 aria-hidden；「行号」「换行」两个文字按钮 type=button、aria-pressed 缺省 true / false，点一下翻转并
    改变样式钩子、再点恢复，行号关掉后不再显示，状态在重新渲染后保持；复制回调收到的字符串逐字等于各行（ANSI 已去）用换行连接；
    复制钮是 IconButton sm、名称「复制已显示的文字」、CopyIcon、悬停 400ms 提示「复制」；被页边界切开的 ANSI 序列也能去掉。"""
    assert_probe_ok(pipeline, "w1")


def test_d02_probe_pages_pieces_and_conflict(pipeline):
    """pages 探针 / D02：已显示 N 页、已到末尾、[继续加载] 调 onLoadMore、loadingMore 的「正在加载…」；text 模式先接后切、末尾换行不多空行、
    以换行开头的页不多出空行、CRLF；分片后来的页覆盖先前的、第 k/n 片在文字前、加载完仍显示 n/n 片；行尾 [继续加载]（Button secondary sm）
    只在最后一行没加载完且还有下一页时出现；jsonl 模式行号用 n、同一 n 的分片按到达顺序拼接、复制跳过隐藏行；隐藏行三种说明、
    EyeOffIcon 14、没有按钮链接 tabindex、点击无反应；changed 时头部与行之间有 info 提示条与 [从头读取]，关闭后能再出现，
    两处 [继续加载] 禁用；defaultLineNumbers、defaultWrap、title、className。"""
    assert_probe_ok(pipeline, "pages")


def test_d03_probe_safe_markdown(pipeline):
    """md 探针 / D03（W2）：标题 h2–h6（h6 封顶）；段落；列表（无序有序、start、嵌套、缩进阈值、制表符、惰性续行、空行、8 层封顶）；
    围栏代码块；GFM 表格（对齐用类、转义竖线、补空丢多）；行内（粗体斜体、蛇形名不变斜体、转义、代码段）；链接（http(s) 放行成 button 加
    span、点击调一次 onOpenLink(原网址)，被拒的只剩文字，空文字、图片、带标题的不算链接）；原始 HTML 当文字；不支持的语法当文字；
    元素与属性都在允许集合里（没有 style、href、src、on*）。"""
    assert_probe_ok(pipeline, "md")


def test_d03_probe_markdown_performance(pipeline):
    """mdperf 探针 / D03：parseMarkdown 对 256 KiB 的全 *、全 _、全 [、全反引号、[a]( 重复、**a 重复、2000 行逐行缩进的 - x，
    以及混合标点、竖线、不闭合围栏，各在 2 秒内返回；经 SafeMarkdown 渲染 64 KiB 的病态输入 5 秒内完成。"""
    assert_probe_ok(pipeline, "mdperf")


def test_d04_probe_effort_pair(pipeline):
    """effort 探针 / D04（W7）：六种情形的整段文字与 data-state——一致、不同（warning 标签、title）、未知（null、undefined、空数组、空串）、
    没有要求（只有「—」）、多个有不同、多个都相同；逐字比较（大小写不同算不同）；标签与档位名各自成元素。"""
    assert_probe_ok(pipeline, "effort")


def test_d05_d06_d07_probe_atoms(pipeline):
    """atoms 探针 / D05–D07：三个图标的 rect 属性与 path d 逐条等于合同；Banner 不传 action 时结构不变、传了时操作钮在文字与关闭钮之间；
    MaskedValue 的结构、title、LockIcon 14 与 isMaskedPlaceholder；dispatchCommand 的拼法；CommandLine md、sm 两种尺寸与复制钮名称、回调、提示；
    NextStep 的结构与可选命令；components/index 的运行时导出。"""
    assert_probe_ok(pipeline, "atoms")


def test_d08_probe_table_keyed_current_row(pipeline):
    """table 探针 / D08（S1、S2）：数字列的 th 带 tt-num；rows 变少、rows 晚于 selectedKey 到达、排序或插入之后恰一行 tabIndex=0 且是约定那一行
    （当前 key → 选中行 → 第一行）；selectedKey 变化时当前行回到选中行；排序后 ArrowDown 去新顺序里的下一行；点击与 Enter 调 onRowOpen(key)；
    rows 为空时没有行。"""
    assert_probe_ok(pipeline, "table")


def test_d09_probe_s5_and_gaps(pipeline):
    """gaps 探针 / D09：SegmentedControl、Tabs 在 value 无效时恰一个 tabIndex=0 且是第一项（aria-checked、aria-selected 仍全为 false，value 有效时
    与现状相同）；每个页签的 aria-controls 都指向同一个面板；Switch、Checkbox 的空格带 repeat 时 preventDefault 但不切换；关闭态胶囊按 Esc
    既不 stopPropagation 也不 preventDefault，打开时关闭、不往外传、焦点留在胶囊。"""
    assert_probe_ok(pipeline, "gaps")


def test_transitional_p9_evidence_showcase_probe(pipeline):
    """陈列页的演示改版（整理陈列页或换成真实页面）时推翻。

    P9 / D11：探针直接渲染 EvidenceShowcase（不依赖根 App）：七节 data-demo 依次为 text-viewer、text-viewer-jsonl、safe-markdown、effort、
    masked-value、command-line、next-step，不与已有的 16 个重复，每节一个 h2.showcase__h2（标题不含 Button）；没有 role=status、对话框、菜单；
    没有文字的按钮都有 aria-label，按钮文字不含「亮」「暗」「跟随系统」；W1 样例在 DOM 里只是文字；text-viewer 一节能依次加到三页、
    显示第 2/2 片、复制显示结果文字、模拟文件已变化后出提示条并能从头读取；jsonl 一节有两种隐藏行说明与第 1/2、2/2 片；safe-markdown 一节
    有摘要原文、表、代码块、链接按钮加网址，点链接只显示「上次请求打开：…」；effort 六种情形、遮蔽值四种占位、命令行两种尺寸、下一步各一个；
    另渲染 FormsShowcase，连接胶囊那一行带类 showcase-pill-row。"""
    assert_probe_ok(pipeline, "showcase")


def test_p10_d13_worktree_unchanged_by_pipeline(pipeline):
    """P10 / D13（守卫）：流水线与探针前后 git status 相同；package.json、锁文件、index.html、vite.config.ts、tsconfig.json、tokens.css、
    fonts.css、base.css、main.tsx、App.tsx、App.css 的摘要不变；gate-probe/ 没有留下。"""
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

GOOD_TABLE_CSS = """
/* 表格 */
.tt-table-wrap {
  overflow: auto;
  background: var(--tt-surface-1);
  border: 1px solid var(--tt-border);
  border-radius: var(--tt-radius-lg);
  scroll-padding-top: 32px; /* 表头高 32（组件板 :411） */
}
.tt-table { width: 100%; border-collapse: collapse; }
.tt-table th {
  position: sticky;
  top: 0;
  height: 32px; /* 组件板 :411 表头高 32 */
  text-align: left;
}
.tt-table th.tt-num { text-align: right; }
.tt-table td.tt-num { text-align: right; }
.tt-table tbody tr[data-selected] {
  box-shadow: inset 2px 0 0 var(--tt-primary); /* 组件板 :415 选中行左 2px 主色 */
}
.tt-table tbody tr:focus-visible { outline: none; }
.tt-table tbody tr:focus-visible td {
  box-shadow: inset 0 2px 0 var(--tt-focus), inset 0 -2px 0 var(--tt-focus); /* 焦点环 2px */
}
.tt-table tbody tr:focus-visible td:first-child {
  box-shadow: inset 0 2px 0 var(--tt-focus), inset 0 -2px 0 var(--tt-focus), inset 2px 0 0 var(--tt-focus); /* 焦点环 2px */
}
.tt-table tbody tr:focus-visible td:last-child {
  box-shadow: inset 0 2px 0 var(--tt-focus), inset 0 -2px 0 var(--tt-focus), inset -2px 0 0 var(--tt-focus); /* 焦点环 2px */
}
.tt-table tbody tr:focus-visible td:only-child {
  box-shadow: inset 0 0 0 2px var(--tt-focus); /* 焦点环 2px */
}
@media (forced-colors: active) {
  .tt-table tbody tr:focus-visible {
    outline: 2px solid Highlight; /* 强制颜色模式的兜底 2px */
    outline-offset: -2px; /* 向内 2px */
  }
}
"""

GOOD_VIEWER_CSS = """
.tt-viewer { background: var(--tt-surface-1); border: 1px solid var(--tt-border); border-radius: var(--tt-radius-lg); overflow: hidden; }
.tt-viewer__head { display: flex; align-items: center; height: 40px; /* 领域板 :352 */ padding: 0 var(--tt-space-2) 0 var(--tt-space-3); border-bottom: 1px solid var(--tt-border); }
.tt-viewer__title { font: var(--tt-mono-sm); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tt-viewer__toggle { height: 28px; /* 领域板 :353 */ padding: 0 var(--tt-space-2); border-radius: var(--tt-radius-md); background: transparent; color: var(--tt-text-2); font: var(--tt-text-sm); }
.tt-viewer__toggle[aria-pressed="true"] { background: var(--tt-surface-3); }
.tt-viewer__body { padding: var(--tt-space-2) 0; overflow-x: auto; font: var(--tt-mono-md); }
.tt-viewer__num { width: 44px; /* 领域板 :355 */ text-align: right; padding-right: var(--tt-space-3); color: var(--tt-text-3); user-select: none; }
.tt-viewer__text { min-height: 20px; /* 领域板 :356 */ padding-right: var(--tt-space-3); white-space: pre; }
.tt-viewer--wrap .tt-viewer__text { white-space: pre-wrap; word-break: break-all; }
.tt-viewer__part { font: var(--tt-text-caption); color: var(--tt-text-3); user-select: none; }
.tt-viewer__hidden { display: inline-flex; gap: var(--tt-space-1); color: var(--tt-text-3); font-style: italic; }
.tt-viewer__foot { display: flex; background: var(--tt-surface-2); border-top: 1px solid var(--tt-border); padding: var(--tt-space-2) var(--tt-space-3); font: var(--tt-text-caption); color: var(--tt-text-3); }
.tt-viewer__foot .tt-btn { margin-left: auto; }
.tt-viewer .tt-banner { margin: var(--tt-space-2) var(--tt-space-3); }
"""

GOOD_MD_CSS = """
.tt-md { font: var(--tt-text-md); color: var(--tt-text-1); display: flex; flex-direction: column; gap: var(--tt-space-2); }
.tt-md h2, .tt-md h3, .tt-md h4, .tt-md h5, .tt-md h6 { margin: 0; }
.tt-md h2 { font: var(--tt-title-lg); }
.tt-md h3 { font: var(--tt-title-md); }
.tt-md h4, .tt-md h5, .tt-md h6 { font: var(--tt-title-sm); }
.tt-md ul, .tt-md ol { margin: 0; padding-left: var(--tt-space-5); display: flex; flex-direction: column; gap: var(--tt-space-1); }
.tt-md li p { margin: 0; }
.tt-md p { margin: 0; white-space: pre-wrap; }
.tt-md code { font: var(--tt-mono-sm); padding: 1px var(--tt-space-1); border-radius: var(--tt-radius-sm); background: var(--tt-surface-2); border: 1px solid var(--tt-border); }
.tt-md pre { margin: 0; font: var(--tt-mono-md); background: var(--tt-surface-2); border: 1px solid var(--tt-border); border-radius: var(--tt-radius-md); padding: var(--tt-space-2); overflow-x: auto; white-space: pre; }
.tt-md__scroll { overflow-x: auto; }
.tt-md table { font: var(--tt-text-sm); border-collapse: collapse; }
.tt-md th, .tt-md td { padding: var(--tt-space-1) var(--tt-space-3); border: 1px solid var(--tt-border); }
.tt-md th { background: var(--tt-surface-2); font: var(--tt-title-sm); color: var(--tt-text-2); }
.tt-md__right { text-align: right; }
.tt-md__center { text-align: center; }
.tt-md__link { color: var(--tt-link); background: transparent; border: 0; padding: 0; font: inherit; }
.tt-md__link:hover { text-decoration: underline; }
.tt-md__url { font: var(--tt-mono-sm); color: var(--tt-text-3); margin-left: var(--tt-space-1); }
"""

GOOD_ATOM_CSS = {
    "effort": """
.tt-effort { display: inline-flex; align-items: center; flex-wrap: wrap; gap: var(--tt-space-1); font: var(--tt-text-sm); }
.tt-effort__label { color: var(--tt-text-3); }
.tt-effort__level { font: var(--tt-mono-sm); }
""",
    "masked": """
.tt-masked { display: inline-flex; align-items: center; gap: var(--tt-space-1); font: var(--tt-text-sm); font-style: italic; color: var(--tt-text-3); }
""",
    "cmd": """
.tt-cmd { display: flex; align-items: center; gap: var(--tt-space-1); min-height: 36px; /* 领域板 :409 */ padding: var(--tt-space-1) var(--tt-space-1) var(--tt-space-1) var(--tt-space-2); border-radius: var(--tt-radius-md); background: var(--tt-surface-2); border: 1px solid var(--tt-border); }
.tt-cmd code { font: var(--tt-mono-md); color: var(--tt-text-1); flex: 1; min-width: 0; white-space: pre-wrap; word-break: break-all; }
.tt-cmd--sm { display: inline-flex; height: 28px; /* 领域板 :410 */ min-height: 0; gap: var(--tt-space-0_5); padding: 0 var(--tt-space-0_5) 0 var(--tt-space-2); }
.tt-cmd--sm code { font: var(--tt-mono-sm); }
.tt-cmd--sm .tt-icon-btn { width: 24px; height: 24px; /* 领域板 :410 */ border-radius: var(--tt-radius-sm); }
.tt-cmd--sm .tt-icon-btn svg { width: 14px; height: 14px; /* 领域板 :410 */ }
""",
    "next": """
.tt-next { display: flex; align-items: center; flex-wrap: wrap; gap: var(--tt-space-2); padding: var(--tt-space-2) var(--tt-space-2) var(--tt-space-2) var(--tt-space-3); border-radius: var(--tt-radius-md); background: var(--tt-tone-info-bg); color: var(--tt-tone-info-fg); font: var(--tt-text-sm); }
.tt-next strong { font: var(--tt-title-sm); }
""",
    "banner": ".tt-banner__action { flex: none; }",
}

GOOD_ICONS = """
export const LockIcon = (props: IconProps) => (
  <Svg {...props}>
    <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </Svg>
);

export const CopyIcon = (props: IconProps) => (
  <Svg {...props}>
    <rect width={14} height={14} x={8} y={8} rx={2} ry={2} />
    <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
  </Svg>
);

export const EyeOffIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49" />
    <path d="M14.084 14.158a3 3 0 0 1-4.242-4.242" />
    <path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143" />
    <path d="m2 2 20 20" />
  </Svg>
);
"""

GOOD_INDEX = """// 统一导出组件，共五片：
//   第 1 片 5 个原子组件；第 3 片 6 个浮层组件；第 4 片 12 个表单与数据原子；第 5 片 6 个证据组件。
// 浮层共用的内部模块不从本文件导出。
""" + "\n".join(
    f"export {{ {n} }} from './{n}';\nexport type {{ {n}Props }} from './{n}';" for n in OLD_COMPONENTS + NEW_COMPONENTS
) + "\nexport { isMaskedPlaceholder } from './MaskedValue';\nexport { dispatchCommand } from './CommandLine';\n"


def test_gate_selfcheck_css_samples_pass_and_mutants_fail():
    """门禁自检：按合同写出的参考 CSS（Table、TextViewer、SafeMarkdown、EffortPair、MaskedValue、CommandLine、NextStep、Banner action）
    通过全部 CSS 检查；把关键取值改坏后检查会报问题。"""
    assert table_css_problems(GOOD_TABLE_CSS) == []
    assert css_spec_problems(GOOD_VIEWER_CSS, "v", VIEWER_SPECS) == []
    assert viewer_extra_problems(GOOD_VIEWER_CSS) == []
    assert css_spec_problems(GOOD_MD_CSS, "m", MD_SPECS) == []
    assert css_spec_problems(GOOD_ATOM_CSS["effort"], "e", EFFORT_SPECS) == []
    assert css_spec_problems(GOOD_ATOM_CSS["masked"], "k", MASKED_SPECS) == []
    assert masked_order_problems(GOOD_ATOM_CSS["masked"]) == []
    assert css_spec_problems(GOOD_ATOM_CSS["cmd"], "c", CMD_SPECS) == []
    assert css_spec_problems(GOOD_ATOM_CSS["next"], "n", NEXT_SPECS) == []
    assert css_spec_problems(GOOD_ATOM_CSS["banner"], "b", BANNER_ACTION_SPECS) == []
    # 改坏的样本
    assert table_css_problems(GOOD_TABLE_CSS.replace("scroll-padding-top: 32px;", "scroll-padding-top: 30px;"))
    assert table_css_problems(GOOD_TABLE_CSS.replace(".tt-table th.tt-num { text-align: right; }", ""))
    assert table_css_problems(GOOD_TABLE_CSS.replace("/* 表头高 32（组件板 :411） */", ""))
    assert table_css_problems(GOOD_TABLE_CSS.replace("tr:focus-visible { outline: none; }", "tr:focus-visible { outline: 0 solid; }"))
    assert table_css_problems(GOOD_TABLE_CSS.replace("td:only-child", "td:nth-child(9)"))
    assert table_css_problems(GOOD_TABLE_CSS.replace("td:last-child", "td:nth-child(8)"))
    assert table_css_problems(GOOD_TABLE_CSS.replace("forced-colors", "prefers-contrast"))
    assert table_css_problems(GOOD_TABLE_CSS.replace("var(--tt-focus)", "var(--tt-primary)"))
    assert table_css_problems(GOOD_TABLE_CSS.replace("outline-offset: -2px; /* 向内 2px */", "outline-offset: -2px;"))
    assert css_spec_problems(GOOD_VIEWER_CSS.replace("height: 28px;", "height: 30px;"), "v", VIEWER_SPECS)
    assert css_spec_problems(GOOD_VIEWER_CSS.replace("font-style: italic;", ""), "v", VIEWER_SPECS)
    assert css_spec_problems(GOOD_VIEWER_CSS.replace("word-break: break-all;", ""), "v", VIEWER_SPECS)
    assert viewer_extra_problems(GOOD_VIEWER_CSS.replace("user-select: none;", ""))
    assert css_spec_problems(GOOD_MD_CSS.replace("--tt-title-lg", "--tt-title-md"), "m", MD_SPECS)
    assert css_spec_problems(GOOD_MD_CSS.replace("padding: 0; font: inherit;", "padding: 0;"), "m", MD_SPECS)
    assert css_spec_problems(GOOD_ATOM_CSS["cmd"].replace("width: 24px;", "width: 28px;"), "c", CMD_SPECS)
    assert css_spec_problems(GOOD_ATOM_CSS["next"].replace("--tt-tone-info-fg", "--tt-text-1"), "n", NEXT_SPECS)
    assert css_spec_problems(GOOD_ATOM_CSS["banner"].replace("none", "1"), "b", BANNER_ACTION_SPECS)
    swapped = GOOD_ATOM_CSS["masked"].replace("font: var(--tt-text-sm); font-style: italic;", "font-style: italic; font: var(--tt-text-sm);")
    assert masked_order_problems(swapped)


def test_gate_selfcheck_helpers():
    """门禁自检：特异性计算器、padding 四边解析、焦点环阴影解析、px 注释检查、令牌检查、W4 的坑、禁用词。"""
    assert specificity(".tt-table th.tt-num") == (0, 2, 1)
    assert specificity(".tt-table th") == (0, 1, 1)
    assert specificity(".tt-cmd--sm .tt-icon-btn") == (0, 2, 0)
    assert specificity(".tt-icon-btn") == (0, 1, 0)
    assert specificity(".tt-table tbody tr:focus-visible") == (0, 2, 2)
    assert specificity(":where(.a) b") == (0, 0, 1)
    sides = box_sides([("padding", "0 var(--tt-space-2) 0 var(--tt-space-3)")], "padding")
    assert sides == {"top": "0", "right": "var(--tt-space-2)", "bottom": "0", "left": "var(--tt-space-3)"}
    assert box_sides([("padding", "1px var(--tt-space-1)")], "padding")["left"] == "var(--tt-space-1)"
    assert box_sides([("padding", "1px 2px 3px")], "padding") == {"top": "1px", "right": "2px", "bottom": "3px", "left": "2px"}
    assert box_sides([("padding", "4px"), ("padding-left", "9px")], "padding")["left"] == "9px"
    assert box_sides([("margin-inline", "1px 2px")], "margin")["right"] == "2px"
    assert focus_shadow_edges("inset 0 2px 0 var(--tt-focus), inset 0 -2px 0 var(--tt-focus)") == {"top", "bottom"}
    assert focus_shadow_edges("inset 2px 0 0 0 var(--tt-focus)") == {"left"}
    assert focus_shadow_edges("inset -2px 0 0 var(--tt-focus)") == {"right"}
    assert focus_shadow_edges("inset 0 0 0 2px var(--tt-focus)") == {"all"}
    assert focus_shadow_edges("0 2px 0 var(--tt-focus)") == set()
    assert focus_shadow_edges("inset 0 2px 0 var(--tt-primary)") == set()
    assert focus_shadow_edges("inset 0 2px 4px var(--tt-focus)") == set()
    assert px_literal_problems("x", ".a { width: 20px; } /* 出处 */") == []
    assert px_literal_problems("x", ".a { width: 20px; }")
    assert px_literal_problems("x", ".a { width: 1px; margin: 0; }") == []
    assert token_only_problems("x", ".a { border-radius: var(--tt-radius-md); font: var(--tt-text-sm); z-index: var(--tt-z-popover); }") == []
    assert token_only_problems("x", ".a { border-radius: 4px; }")
    assert token_only_problems("x", ".a { font: 13px/20px sans-serif; }")
    assert token_only_problems("x", ".a { box-shadow: 0 1px 2px black; }")
    assert forbidden_word_problems([]) == []
    assert all(w in " ".join(FORBIDDEN_WORDS) for w in ("eval(", "new Function", "innerHTML", "srcdoc"))
    assert [m.group(0) for m in HEX_RE.finditer("a #fff b #abcd c #12345 d #1234567 e #12345678")] == ["#fff", "#abcd", "#12345678"]
    assert COLOR_FUNC_RE.search("x rgb(1,2,3)") and COLOR_FUNC_RE.search("color (srgb)") and not COLOR_FUNC_RE.search("a color\n(b)")


def test_gate_selfcheck_icon_index_and_source_checks():
    """门禁自检：图标解析放得过合同写明的写法（字符串或花括号数字的 rect 属性），拦得住路径写错、rect 属性写错；index.ts 参考样本通过，
    漏导出、写 overlay、导出内部函数都会报；执行端测试检查拦得住 skip、only、todo。"""
    assert icon_problems(GOOD_ICONS) == []
    assert icon_problems(GOOD_ICONS.replace("m2 2 20 20", "m2 2 20 21"))
    assert icon_problems(GOOD_ICONS.replace('width="18"', 'width="17"'))
    assert icon_problems(GOOD_ICONS.replace("export const CopyIcon", "export const CopyIcom"))
    assert icon_problems(GOOD_ICONS.replace("EyeOffIcon = (props: IconProps) => (\n  <Svg {...props}>", "EyeOffIcon = (props: IconProps) => (\n  <svg>"))
    assert index_problems(GOOD_INDEX) == []
    assert index_problems(GOOD_INDEX.replace("export { TextViewer } from './TextViewer';", ""))
    assert index_problems(GOOD_INDEX.replace("export { isMaskedPlaceholder } from './MaskedValue';", ""))
    assert index_problems(GOOD_INDEX + "export { Dialog as D } from './overlay/MountLayer';\n")
    assert index_problems(GOOD_INDEX + "export { stripAnsi } from './evidence/ansi';\n")
    assert new_source_problems([]) == []
    assert showcase_px_note_problems("x", ".a { width: 240px; } /* 演示自定 */") == []
    assert showcase_px_note_problems("x", ".a { width: 880px; } /* handoff :165 */") == []
    assert showcase_px_note_problems("x", ".a { width: 240px; }")
    assert showcase_px_note_problems("x", ".a { width: 240px; } /* 随便写写 */")
    assert showcase_px_note_problems("x", ".a { border: 1px solid; margin: 0; }") == []


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
    """门禁自检：每份探针都有用例，占位符都被替换；图标规格与领域板、合同一致；PROBE_ORDER 与 PROBE_SPECS 对得上，演示探针最后跑；
    探针里不写 skip、only、todo。"""
    assert set(PROBE_ORDER) == set(PROBE_SPECS) and PROBE_ORDER[-1] == "showcase"
    for key in PROBE_ORDER:
        source = build_probe_source(key)
        assert not re.search(r"__[A-Z_]+__", source), f"探针 {key} 里还有没替换的占位符"
        assert probe_count(source) >= 1, key
        assert not re.search(r"\.(skip|only|todo)\b|\bxit\(|\bxdescribe\(", source), key
        assert js_bracket_problems(source) == [], f"探针 {key} 的括号：{js_bracket_problems(source)}"
    assert js_bracket_problems("a(b[c{d}])") == [] and js_bracket_problems("a(b]") and js_bracket_problems("f('x)")
    assert js_bracket_problems("f('(' + \"]\" + `{`)") == []
    atoms = build_probe_source("atoms")
    assert json.dumps(EYE_OFF_DS[3]) in atoms and '"M7 11V7a5 5 0 0 1 10 0v4"' in atoms
    show = build_probe_source("showcase")
    for demo in EVIDENCE_DEMOS:
        assert f'"{demo}"' in show
    assert len(EXISTING_DEMOS) == 16 and len(set(EXISTING_DEMOS) | set(EVIDENCE_DEMOS)) == 23
    assert canvas_icon(404) == LOCK_CONTRACT and canvas_icon(409) == COPY_CONTRACT


def test_gate_selfcheck_executor_test_checker(tmp_path, monkeypatch):
    """门禁自检：执行端测试检查对全部在位、无 skip 的样本通过；缺文件、没有用例、写了 skip / only / todo 都会报。"""
    import types

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    for name in EXECUTOR_TESTS:
        (tests_dir / name).write_text("it('x', () => {});\n", encoding="utf-8")
    fake_web = tmp_path
    monkeypatch.setitem(globals(), "WEB", fake_web)
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
    assert types is not None
