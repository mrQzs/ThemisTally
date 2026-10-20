"""T005 战前门禁：桌面端前端表单与数据原子（第四片）的黑盒基准测试（合同 t005-desktop-forms，plan_version 1）。

被测对象是 ``desktop/web/``：12 个新组件（分段选择、开关、复选框、页签、输入框、下拉、表格、键值列表、空状态、骨架屏、
连接胶囊、面包屑）与各自的 CSS、4 个新图标、T004 留下的四处修补（对话框遮罩、轻提示关闭钮的工具提示、两处 16px、
基础重置的特异性）、陈列页追加的 11 节演示。
基线（T004 结项）上这些都还没有，所以本文件的“失败”断言落在目标文件不存在或内容不符上，不是导入、收集或语法错误：
模块级只导入标准库，用到被测文件的地方都在用例函数里读；候选还没有任何新组件时，``pipeline`` 夹具不跑 npm
（没有东西可测，也省掉联网的 ``npm ci``），用到它的用例以断言失败写明原因。

结构（编号对应规划 §7.3 的 S1–S5、P1–P13；门禁端加了若干静态守卫和自检）：

- 静态断言（S 系列，不用流水线，全量 pytest 也跑）：读组件 CSS、``components/index.ts``、``icons/index.tsx``、``base.css``、
  组件源码；S2 用 Python 版特异性计算器（按顶层逗号切选择器列表，``:where(button, input)`` 里的逗号不切）。
- 流水线断言（P 系列）：会话级夹具 ``pipeline`` 在 ``desktop/web`` 下按顺序跑 ``npm ci``、``npm run build``、
  ``npm test``、``npm run check:contract``，再把探针逐份写成 ``gate-probe/probe-<唯一标识>-<编号>.test.tsx``，
  各用 ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除；前后各取一次 ``git status``。
  现在只有组件探针（P2–P11）；原来分开写、分开跑的陈列页探针（P12）随 P12 一起退役了（见下面的“过渡断言”）。
  全量 pytest 默认跳过用到它的用例（``tests/conftest.py``），点名运行本文件时才跑。
- 门禁自检（``test_gate_selfcheck_*``，不依赖候选）：把各检查函数喂给正确样本和若干改坏的样本，证明门禁自己
  放得过正确实现、拦得住常见错误；特异性计算器按规划 §2.2 的样本自检。

DoD 对应：

- D01：S1、S5、P4；D02：S1、S5、P5；D03：S1、S5、P6；D04：S1、S4、S5、P7；D05：S1、S5、P8；
- D06：S1、S4、S5、P9；D07：S1、S5、P10；D08：S1、S5、P11；
- D09：S2、S3、P1（dist 里的 ``:where(``）、P2、P3、执行端的两份新测试在位（V02 另证 T001–T004 门禁）；
- D10：原来是 P12（过渡），已退役，本文件不再覆盖（见下一段）；D11：P1、P13（V02、V03 另证）；
- D12：新增测试不用 skip、only、todo 由 V02 里 T002 的 ``test_d03_new_tests_not_skipped`` 机械检查，本文件的
  ``test_d12_*`` 补上新组件源码的守卫；改动范围由调度器的范围门禁证明（这里不写相对基线的范围断言）。

过渡断言（``test_transitional_`` 开头）：原来只有 P12（``test_transitional_d10_showcase_form_demos``，探针渲染根 ``App``
核对陈列页追加的 11 节表单与数据演示，另查 ``src/showcase/*.css`` 里表格演示容器的限高），只在陈列页是根 ``App`` 时成立，
站主在登记 T006（应用框架与夹具数据层）之前退役了，连同它的探针 ``PROBE_P12``、``PROBE_SPECS`` 与 ``PROBE_ORDER`` 里的
``p12``、只供它用的 ``NEW_DEMOS`` 与 ``showcase_table_limit_problems``。T006 把根 ``App`` 改成应用框架、把陈列页移出根路由，
这条在根 ``App`` 上不再成立；11 节演示（含表格演示的限高）在新位置上的覆盖由 T006 自己的门禁重新负责。
其余（组件行为、CSS 取值、基础重置、T004 修补）都是长期断言，照旧保留。

写法约定：CSS 比较先归一空白（``calc(…)`` 里的也一样）；jsdom 不排版、不算层叠，宽、高、位置、层级、色调读 CSS
文件的文本，探针只看结构、焦点、计时与属性；合同没有定类名的组件，CSS 断言用“有一条规则声明了某值”的写法，
不依赖类名；悬停与聚焦的探针从 ``@testing-library/react`` 导入 ``fireEvent``（它给 React 打了补丁）；
不写 skip、xfail、only、todo。

门禁做不到、留给人的项（合同 H1–H8）：
H1 视觉（暗色、亮色各一次）；H2 真浏览器键盘与鼠标（StrictMode 的 dev 服务器与 vite preview）；
H3 DevTools 的 computed 值与 ``:where()`` 生效；H4 表格吸顶与横向滚动；H5 减少动态效果；
H6 Windows 高对比度；H7 读屏抽查；H8 1024 × 640 与缩放。
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
SRC = REPO_ROOT / "desktop" / "web" / "src"
COMP_REL = f"{SRC_REL}/components"
CANVAS_COMPONENTS = REPO_ROOT / "docs" / "ui-design" / "pages" / "02-基础组件-Themis-Tally.html"

NEW_COMPONENTS = ("SegmentedControl", "Switch", "Checkbox", "Tabs", "TextField", "Select", "Table",
                  "KeyValueList", "EmptyState", "Skeleton", "ConnectionPill", "Breadcrumb")
OLD_COMPONENTS = ("Button", "Tag", "StatusTag", "Card", "Banner",
                  "IconButton", "Tooltip", "Menu", "Dialog", "Drawer", "Toast")

# 夹具总预算留出余量给其余快测试（合同检查项 V01 的 timeout 是 600s）。
PIPELINE_BUDGET = 480
STEP_CAPS = {
    "npm ci": 200,
    "npm run build": 100,
    "npm test": 120,
    "npm run check:contract": 40,
    "probe": 60,
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
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:30])


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


# ---------------------------------------------------------------------------
# CSS 小解析器：规则、声明；选择器列表按顶层逗号切
# ---------------------------------------------------------------------------

def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def split_top(text, sep=","):
    """按顶层 sep 切（圆括号、方括号、引号里的不算）；``:where(button, input)`` 里的逗号不切。"""
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
    """把声明块按分号切开（引号和括号里的分号不算），返回 [(小写名, 值)]，保持源码顺序。"""
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


def class_decls(css, cls):
    """所有选择器列表里有一项的最后一个复合选择器带 .cls 的规则的声明，按源码顺序拼起来。"""
    out = []
    for selector, decls in parse_rules(css):
        for item in split_top(selector):
            compound = re.split(r"[\s>+~]+", item)[-1]
            if cls in re.findall(r"\.([\w-]+)", compound):
                out.extend(decls)
                break
    return out


def cv(value):
    """归一值：去 !important，所有空白去掉（calc(…) 里的也一样），小写。"""
    return re.sub(r"\s+", "", re.sub(r"!important", "", value or "", flags=re.I)).lower()


def last_value(decls, *names):
    got = None
    for name, value in decls:
        if name in names:
            got = cv(value)
    return got


def is_zero(value):
    return value in ("0", "0px", "0%")


def has_decl(css, names, eq=None, has=(), sel=None, zero=False, custom=False):
    """有一条规则（选择器匹配正则 sel，缺省不限）声明了 names 里的某个属性，且归一后的值满足：
    等于 eq；或包含 has 里的每一段；zero=True 时值是 0 / 0px；custom=True 时 names 之外以 -- 开头的自定义属性也算。"""
    for selector, decls in parse_rules(css):
        if sel and not re.search(sel, selector):
            continue
        for name, value in decls:
            if not (name in names or (custom and name.startswith("--"))):
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


def spec_problems(css, label, specs):
    """specs: [(说明, 属性名元组, 关键字参数字典)]；每条都要有规则满足，缺的列成问题。"""
    problems = []
    for desc, names, kwargs in specs:
        if not has_decl(css, names, **kwargs):
            wanted = kwargs.get("eq") or "、".join(kwargs.get("has", ())) or ("0" if kwargs.get("zero") else "")
            where = f"（选择器含 {kwargs['sel']}）" if kwargs.get("sel") else ""
            problems.append(f"{label}：{desc}——没有规则声明 {'/'.join(names)}: {wanted}{where}")
    return problems


def px_literal_problems(label, css_raw):
    """合同公共约定：尺寸字面量同一行带出处注释。除 0 与 1px 外的 px 字面量，所在行（去掉注释后）有 px，
    该行又没有注释，就记一条问题。"""
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


# ---------------------------------------------------------------------------
# 选择器特异性计算器（规划 §2.2；合同 7.4）
# #id 记 a；类、属性、伪类记 b；元素名与伪元素记 c；:where() 记 0；:is()/:not()/:has() 取参数里最大的；
# 选择器列表按顶层逗号切。
# ---------------------------------------------------------------------------

_NAME = re.compile(r"-?[A-Za-z_\u0080-￿][\w\-\u0080-￿]*")
_LEGACY_ELEMENTS = ("before", "after", "first-line", "first-letter")


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


def _strip_leading_combinator(text):
    return re.sub(r"^[\s>+~]+", "", text)


def specificity(selector):
    """单个复杂选择器（不含顶层逗号）的特异性 (a, b, c)。"""
    a = b = c = 0
    i, n = 0, len(selector)
    while i < n:
        ch = selector[i]
        if ch == "#":
            m = _NAME.match(selector, i + 1) or re.compile(r"[\w\-]+").match(selector, i + 1)
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
                if i < n and selector[i] == "(":
                    i = _matching_paren(selector, i) + 1
                continue
            m = _NAME.match(selector, i + 1)
            name = m.group(0).lower() if m else ""
            i = m.end() if m else i + 1
            if name in _LEGACY_ELEMENTS:
                c += 1
            elif i < n and selector[i] == "(":
                j = _matching_paren(selector, i)
                arg = selector[i + 1:j]
                i = j + 1
                if name == "where":
                    pass
                elif name in ("is", "not", "has", "matches", "any", "-webkit-any", "-moz-any"):
                    inner = [specificity(_strip_leading_combinator(p)) for p in split_top(arg) if p.strip()]
                    best = max(inner) if inner else (0, 0, 0)
                    a, b, c = a + best[0], b + best[1], c + best[2]
                elif name in ("nth-child", "nth-last-child"):
                    b += 1
                    tail = re.search(r"\bof\b(.*)$", arg)
                    if tail:
                        inner = [specificity(p) for p in split_top(tail.group(1)) if p.strip()]
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


def selector_subject(selector):
    """最右的复合选择器（按顶层的空白、>、+、~ 切；括号、方括号里的不算）。"""
    tokens, buf, depth, quote = [], [], 0, None
    for ch in selector:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if depth == 0 and ch in " \t\r\n>+~":
            if buf:
                tokens.append("".join(buf))
                buf = []
            continue
        buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens[-1] if tokens else ""


RESET_ELEMENTS = ("button", "input", "select", "textarea", "a", "table")


def subject_elements(selector):
    """选择器主体（最右的复合选择器，连同其中 :where()、:is() 的参数）里出现的 button、input、select、textarea、a、table。"""
    flat = re.sub(r"\[[^\]]*\]", "", selector_subject(selector))
    found = {m.group(1).lower() for m in re.finditer(r"(?<![\w\-.#:\\])([A-Za-z][\w-]*)", flat)}
    return found & set(RESET_ELEMENTS)


# ---------------------------------------------------------------------------
# S2：base.css 的元素重置
# ---------------------------------------------------------------------------

def base_reset_rules(css):
    """base.css 里主体是 button/input/select/textarea/a/table 且不含 :focus-visible 的选择器：[(选择器, 元素集合, 特异性, 声明)]。"""
    out = []
    for selector, decls in parse_rules(css):
        for item in split_top(selector):
            if ":focus-visible" in item:
                continue
            els = subject_elements(item)
            if els:
                out.append((item, els, specificity(item), decls))
    return out


def base_reset_problems(css):
    problems = []
    resets = base_reset_rules(css)
    for item, _els, spec, _decls in resets:
        if spec >= (0, 1, 0):
            problems.append(f"base.css 的元素重置 {item!r} 特异性是 {spec}，应低于 (0,1,0)（合同 7.4：包进 :where()）")
    covered = set()
    core = False
    for selector, decls in parse_rules(css):
        els = set()
        for item in split_top(selector):
            if ":focus-visible" not in item:
                els |= subject_elements(item)
        covered |= els
        if {"button", "input", "select", "textarea"} <= els and last_value(decls, "font") == "inherit" \
                and last_value(decls, "color") == "inherit" and is_zero(last_value(decls, "margin") or ""):
            core = True
    if not core:
        problems.append("base.css 里没有一条规则同时声明 font: inherit、color: inherit、margin: 0 并覆盖 button、input、select、textarea")

    def exists(pred):
        return any(pred(item, els, decls) for item, els, _s, decls in resets)

    if not exists(lambda i, e, d: "button" in e and ":disabled" not in i and last_value(d, "cursor") == "pointer"):
        problems.append("base.css 里没有 button 的 cursor: pointer 重置")
    if not exists(lambda i, e, d: "button" in e and ":disabled" in i and last_value(d, "cursor") == "not-allowed"):
        problems.append("base.css 里没有 button:disabled 的 cursor: not-allowed 重置")
    if not exists(lambda i, e, d: "a" in e and last_value(d, "color") == "var(--tt-link)"):
        problems.append("base.css 里没有 a 的 color: var(--tt-link) 重置")
    if not exists(lambda i, e, d: "table" in e and last_value(d, "border-collapse") == "collapse"):
        problems.append("base.css 里没有 table 的 border-collapse: collapse 重置")
    if not exists(lambda i, e, d: "input" in e and "::placeholder" in i and last_value(d, "color") == "var(--tt-text-3)"):
        problems.append("base.css 里没有 input::placeholder 的 color: var(--tt-text-3) 重置")
    # 焦点规则与减少动效规则不动（合同 7.4：第 12–17 行以外的规则不改）
    focus_ok = any(split_top(sel) == [".tt-app :focus-visible"] and last_value(d, "outline") == "2pxsolidvar(--tt-focus)"
                   and last_value(d, "outline-offset") == "2px" for sel, d in parse_rules(css))
    if not focus_ok:
        problems.append("base.css 的 .tt-app :focus-visible 焦点环规则（outline: 2px solid var(--tt-focus)、外偏 2px）不见了或被改了")
    input_focus = any(":focus-visible" in sel and "input" in sel and last_value(d, "border-color") == "var(--tt-focus)"
                      and last_value(d, "outline-offset") == "1px" for sel, d in parse_rules(css))
    if not input_focus:
        problems.append("base.css 的输入控件焦点规则（border-color: var(--tt-focus)、外偏 1px）不见了或被改了")
    if not re.search(r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{[^{}]*\.tt-skel\b[^{}]*\{[^}]*animation\s*:\s*none",
                     strip_comments(css)):
        problems.append("base.css 的减少动效规则里没有 .tt-skel（animation: none）")
    return problems


# 与组件单类规则交叉核对：(文件, 类名, 属性)——这些规则的特异性是 (0,1,0)，必须高于 base.css 里声明同一属性的元素重置。
CROSS_CHECKS = (
    ("Button.css", "tt-btn--primary", "color"),
    ("Button.css", "tt-btn--sm", "font"),
    ("Button.css", "tt-btn--md", "font"),
    ("Button.css", "tt-btn--lg", "font"),
    ("IconButton.css", "tt-icon-btn", "color"),
    ("Toast.css", "tt-toast__close", "color"),
)


def cross_check_problems(base_css, comp_css_by_file):
    problems = []
    resets = base_reset_rules(base_css)
    for fname, cls, prop in CROSS_CHECKS:
        css = comp_css_by_file[fname]
        found = None
        for selector, decls in parse_rules(css):
            if split_top(selector) == [f".{cls}"] and any(n == prop for n, _v in decls):
                found = specificity(f".{cls}")
        if found is None:
            problems.append(f"{fname} 里没有单类规则 .{cls} 声明 {prop}")
            continue
        for item, _els, spec, decls in resets:
            if any(n == prop for n, _v in decls) and not found > spec:
                problems.append(f"{fname} 的 .{cls}（{found}）压不过 base.css 的 {item!r}（{spec}）对 {prop} 的重置")
    return problems


# ---------------------------------------------------------------------------
# 源码侧的检查函数（返回问题列表；空表示通过）
# ---------------------------------------------------------------------------

def strip_ts_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(^|[^:'\"`])//[^\n]*", r"\1", text)


def index_exports(text):
    """components/index.ts 导出的名字集合（含 export type 与 as 改名；export * from './X' 记作 X 与 XProps）。"""
    text = strip_ts_comments(text)
    names = set()
    for m in re.finditer(r"export\s+(?:type\s+)?\{([^}]*)\}", text):
        for part in m.group(1).split(","):
            part = re.sub(r"^\s*type\s+", "", part.strip())
            if part:
                names.add(part.split(" as ")[-1].strip())
    for m in re.finditer(r"export\s*\*\s*from\s*['\"]\./(\w+)['\"]", text):
        names.update({m.group(1), m.group(1) + "Props"})
    return names


def index_problems(text):
    names = index_exports(text)
    problems = []
    for comp in NEW_COMPONENTS + OLD_COMPONENTS:
        if comp not in names:
            problems.append(f"components/index.ts 没有导出 {comp}")
        if f"{comp}Props" not in names:
            problems.append(f"components/index.ts 没有导出 {comp}Props 类型")
    if re.search(r"overlay", strip_ts_comments(text)):
        problems.append("components/index.ts 不该导出内部模块 overlay/")
    return problems


def icon_component_ds(text, name):
    """icons/index.tsx 里 ``export const <name>`` 那一块的 path d 列表；没有这个导出返回 None。"""
    m = re.search(rf"export\s+(?:const|function)\s+{name}\b", text)
    if not m:
        return None
    nxt = re.search(r"\nexport\s+(?:const|function|type|interface)\b", text[m.end():])
    block = text[m.start(): m.end() + (nxt.start() if nxt else len(text))]
    return re.findall(r"""\bd\s*=\s*["']([^"']*)["']""", block)


def canvas_line_icon_ds(lineno):
    """组件板（02-基础组件）第 lineno 行里第一个 svg 的 path d 列表。"""
    lines = _read(CANVAS_COMPONENTS).split("\n")
    line = lines[lineno - 1]
    svg = re.search(r"<svg\b.*?</svg>", line, re.S)
    assert svg, f"组件板 :{lineno} 里没有 svg"
    return re.findall(r'\bd="([^"]*)"', svg.group(0))


# 合同第 5 步：新增 4 个图标，路径只从画布拷（组件板行号）。
ICON_SPECS = (
    ("ChevronDownIcon", 360, ["m6 9 6 6 6-6"]),
    ("ChevronRightIcon", 449, ["m9 18 6-6-6-6"]),
    ("CheckIcon", 378, ["M20 6 9 17l-5-5"]),
    ("ListChecksIcon", 466, ["m3 17 2 2 4-4", "m3 7 2 2 4-4", "M13 6h8", "M13 12h8", "M13 18h8"]),
)


def icon_problems(icons_text):
    problems = []
    for name, lineno, literal in ICON_SPECS:
        got = icon_component_ds(icons_text, name)
        want = canvas_line_icon_ds(lineno)
        if want != literal:
            problems.append(f"（门禁自身）组件板 :{lineno} 的路径 {want} 与合同写的 {literal} 不同")
        if got is None:
            problems.append(f"icons/index.tsx 没有 export const {name}")
        elif got != want:
            problems.append(f"{name} 的 path d 应等于组件板 :{lineno} 的 {want}，实际 {got}")
    return problems


# ---- S3：两处 16px ----

def sixteen_px_problems(icon_button_css, toast_css):
    problems = []
    lines = [ln for ln in icon_button_css.split("\n") if re.search(r"svg", ln) and re.search(r"16px", ln)]
    if not lines:
        problems.append("IconButton.css 里没有 svg 的 16px 规则（应保留，只加出处注释）")
    elif not any(re.search(r"/\*[^*]*\*/", ln) for ln in lines):
        problems.append("IconButton.css 里 svg 16px 那一行没有同一行的出处注释（合同 7.3：组件板 :340，图标 16）")
    elif not any(re.search(r"/\*[^*]*(?:340|组件板)[^*]*\*/", ln) for ln in lines):
        problems.append("IconButton.css 里 svg 16px 那一行的注释没写出处（组件板 :340）")
    for selector, decls in parse_rules(toast_css):
        for item in split_top(selector):
            if re.search(r"\bsvg\b", item) and any(n in ("width", "height") for n, _v in decls):
                problems.append(f"Toast.css 里还有给 svg 定宽高的规则：{item}（合同 7.3：删掉）")
    return problems


# ---- S5：各组件 CSS 的取值（合同行为细则第 1–12 条；不依赖类名） ----

BG = ("background", "background-color")
BORDER_W = ("border", "border-width", "border-top", "border-right", "border-bottom", "border-left")
BORDER_C = ("border", "border-color", "border-top", "border-right", "border-bottom", "border-left")
PAD = ("padding", "padding-inline", "padding-left", "padding-right", "padding-inline-start", "padding-inline-end")
GAP = ("gap", "row-gap", "column-gap")
SEL_ON = r"checked|selected|active|current"


def D(desc, names, **kw):
    return (desc, tuple(names), kw)


FIELD_SPECS = [
    D("高 32", ("height", "min-height"), eq="32px"),
    D("边框 1px", BORDER_W, has=("1px",)),
    D("边框色 --tt-border-strong", BORDER_C, has=("var(--tt-border-strong)",)),
    D("圆角 --tt-radius-md", ("border-radius",), eq="var(--tt-radius-md)"),
    D("底 --tt-surface-1", BG, eq="var(--tt-surface-1)"),
    D("字色 --tt-text-1", ("color",), eq="var(--tt-text-1)"),
    D("字体 --tt-text-md", ("font",), eq="var(--tt-text-md)"),
    D("等宽字体 --tt-mono-md", ("font",), eq="var(--tt-mono-md)"),
    D("左右内边距 --tt-space-2", PAD, has=("var(--tt-space-2)",)),
    D("出错边框 --tt-danger-text", BORDER_C, has=("var(--tt-danger-text)",), sel=r"error|invalid|danger"),
    D("出错文字色 --tt-danger-text", ("color",), eq="var(--tt-danger-text)", sel=r"error|invalid|danger"),
    D("出错文字 --tt-text-sm", ("font",), eq="var(--tt-text-sm)"),
    D("帮助文字 --tt-text-caption", ("font",), eq="var(--tt-text-caption)"),
    D("帮助文字色 --tt-text-3", ("color",), eq="var(--tt-text-3)"),
    D("标签 --tt-text-caption-strong", ("font",), eq="var(--tt-text-caption-strong)"),
    D("标签与控件间距 --tt-space-1", GAP + ("margin-bottom", "margin-top", "margin", "margin-block-end", "padding-bottom"),
      has=("var(--tt-space-1)",)),
    D("禁用底 --tt-surface-2", BG, eq="var(--tt-surface-2)", sel=r"disabled"),
    D("禁用字 --tt-text-disabled", ("color",), eq="var(--tt-text-disabled)", sel=r"disabled"),
    D("禁用边框 --tt-border", BORDER_C, has=("var(--tt-border)",), sel=r"disabled"),
]

SELECT_ONLY_SPECS = [
    D("appearance: none", ("appearance", "-webkit-appearance", "-moz-appearance"), eq="none"),
    D("右内边距 32（--tt-space-8）", ("padding-right", "padding-inline-end", "padding"), has=("var(--tt-space-8)",)),
    D("箭头 pointer-events: none", ("pointer-events",), eq="none"),
    D("箭头色 --tt-text-3", ("color",), eq="var(--tt-text-3)"),
    D("箭头右边距 --tt-space-2", ("right", "inset-inline-end"), eq="var(--tt-space-2)"),
]

SEGMENTED_SPECS = [
    D("轨道底 --tt-surface-2", BG, eq="var(--tt-surface-2)"),
    D("轨道边框 1px", BORDER_W, has=("1px",)),
    D("轨道边框色 --tt-border", BORDER_C, has=("var(--tt-border)",)),
    D("轨道圆角 --tt-radius-md", ("border-radius",), eq="var(--tt-radius-md)"),
    D("轨道内边距 --tt-space-0_5", PAD, eq="var(--tt-space-0_5)"),
    D("段高 28", ("height", "min-height"), eq="28px"),
    D("段左右 --tt-space-3", PAD, has=("var(--tt-space-3)",)),
    D("段圆角 --tt-radius-sm", ("border-radius",), eq="var(--tt-radius-sm)"),
    D("段字体 --tt-text-sm-medium", ("font",), eq="var(--tt-text-sm-medium)"),
    D("段字色 --tt-text-2", ("color",), eq="var(--tt-text-2)"),
    D("段底透明", BG, eq="transparent"),
    D("选中段底 --tt-surface-1", BG, eq="var(--tt-surface-1)", sel=SEL_ON),
    D("选中段阴影 --tt-shadow-1", ("box-shadow",), eq="var(--tt-shadow-1)", sel=SEL_ON),
    D("选中段字色 --tt-text-1", ("color",), eq="var(--tt-text-1)", sel=SEL_ON),
]

SWITCH_SPECS = [
    D("轨道宽 32", ("width", "min-width"), eq="32px"),
    D("轨道高 18", ("height", "min-height"), eq="18px"),
    D("轨道圆角 --tt-radius-full", ("border-radius",), eq="var(--tt-radius-full)"),
    D("关：底 --tt-surface-2", BG, eq="var(--tt-surface-2)"),
    D("关：边框 1px", BORDER_W, has=("1px",)),
    D("关：边框色 --tt-border-strong", BORDER_C, has=("var(--tt-border-strong)",)),
    D("关：圆点 --tt-border-strong", BG, eq="var(--tt-border-strong)"),
    D("开：底 --tt-primary", BG, eq="var(--tt-primary)", sel=SEL_ON),
    D("开：边框 --tt-primary", BORDER_C, has=("var(--tt-primary)",), sel=SEL_ON),
    D("开：圆点 --tt-on-primary", BG, eq="var(--tt-on-primary)"),
    D("圆点宽 12", ("width",), eq="12px"),
    D("圆点高 12", ("height",), eq="12px"),
    D("圆点上 2", ("top", "inset-block-start"), eq="2px"),
    D("关时圆点左 2", ("left", "inset-inline-start"), eq="2px"),
    D("开时圆点左 16", ("left", "inset-inline-start"), eq="16px"),
    D("禁用：底 --tt-surface-2", BG, eq="var(--tt-surface-2)", sel=r"disabled"),
    D("禁用：边框 --tt-border", BORDER_C, has=("var(--tt-border)",), sel=r"disabled"),
    D("禁用：圆点 --tt-text-disabled", BG, eq="var(--tt-text-disabled)", sel=r"disabled"),
    D("禁用：文字 --tt-text-disabled", ("color",), eq="var(--tt-text-disabled)", sel=r"disabled"),
    D("文字 --tt-text-sm", ("font",), eq="var(--tt-text-sm)"),
    D("与轨道间距 --tt-space-2", GAP + ("margin-left", "margin-right", "margin-inline-start", "margin-inline-end"),
      has=("var(--tt-space-2)",)),
]

CHECKBOX_SPECS = [
    D("框宽 16", ("width", "min-width"), eq="16px"),
    D("框高 16", ("height", "min-height"), eq="16px"),
    D("框圆角 --tt-radius-sm", ("border-radius",), eq="var(--tt-radius-sm)"),
    D("未选：边框 1px", BORDER_W, has=("1px",)),
    D("未选：边框色 --tt-border-strong", BORDER_C, has=("var(--tt-border-strong)",)),
    D("未选：底 --tt-surface-1", BG, eq="var(--tt-surface-1)"),
    D("已选：底 --tt-primary", BG, eq="var(--tt-primary)", sel=SEL_ON),
    D("勾的颜色 --tt-on-primary", ("color",), eq="var(--tt-on-primary)"),
    D("文字 --tt-text-sm", ("font",), eq="var(--tt-text-sm)"),
    D("与框间距 --tt-space-2", GAP + ("margin-left", "margin-right", "margin-inline-start", "margin-inline-end"),
      has=("var(--tt-space-2)",)),
]

TABS_SPECS = [
    D("列表下边框 1px --tt-border", ("border-bottom",), has=("1px", "var(--tt-border)")),
    D("页签间距 --tt-space-1", GAP, eq="var(--tt-space-1)"),
    D("页签高 38", ("height", "min-height"), eq="38px"),
    D("页签左右 --tt-space-3", PAD, has=("var(--tt-space-3)",)),
    D("页签字体 --tt-text-md-medium", ("font",), eq="var(--tt-text-md-medium)"),
    D("页签字色 --tt-text-2", ("color",), eq="var(--tt-text-2)"),
    D("当前页签字色 --tt-text-1", ("color",), eq="var(--tt-text-1)", sel=SEL_ON),
    D("当前页签下边 2px --tt-primary", ("border-bottom", "box-shadow", "border-bottom-color"),
      has=("var(--tt-primary)",), sel=SEL_ON),
    D("当前页签下边 2px", ("border-bottom", "border-bottom-width", "box-shadow"), has=("2px",)),
    D("当前页签 margin-bottom: -1px", ("margin-bottom",), eq="-1px"),
    D("悬停底 --tt-surface-3", BG, eq="var(--tt-surface-3)", sel=r"hover"),
    D("悬停上两角 --tt-radius-md", ("border-radius", "border-top-left-radius"), has=("var(--tt-radius-md)",)),
]

TABLE_SPECS = [
    D("容器 overflow: auto", ("overflow",), eq="auto"),
    D("容器底 --tt-surface-1", BG, eq="var(--tt-surface-1)"),
    D("容器边框 1px --tt-border", ("border",), has=("1px", "var(--tt-border)")),
    D("容器圆角 --tt-radius-lg", ("border-radius",), eq="var(--tt-radius-lg)"),
    D("表头高 32", ("height", "min-height"), eq="32px"),
    D("表头 position: sticky", ("position",), eq="sticky"),
    D("表头 top: 0", ("top",), zero=True),
    D("表头 z-index: var(--tt-z-sticky)", ("z-index",), eq="var(--tt-z-sticky)"),
    D("表头底 --tt-surface-2", BG, eq="var(--tt-surface-2)"),
    D("表头字体 --tt-title-sm", ("font",), eq="var(--tt-title-sm)"),
    D("表头字色 --tt-text-2", ("color",), eq="var(--tt-text-2)"),
    D("表头左右 --tt-space-3", PAD, has=("var(--tt-space-3)",)),
    D("单元格不换行", ("white-space",), eq="nowrap"),
    D("行高 40", ("height", "min-height"), eq="40px", custom=True),
    D("行高 44（选择器带 44）", ("height", "min-height"), eq="44px", custom=True, sel=r"(?<!\d)44(?!\d)"),
    D("行高 52（选择器带 52）", ("height", "min-height"), eq="52px", custom=True, sel=r"(?<!\d)52(?!\d)"),
    D("行上边框 1px --tt-border", ("border-top",), has=("1px", "var(--tt-border)")),
    D("行字体 --tt-text-sm", ("font",), eq="var(--tt-text-sm)"),
    D("悬停底 --tt-surface-3", BG, eq="var(--tt-surface-3)", sel=r"hover"),
    D("选中行底 --tt-surface-selected", BG, eq="var(--tt-surface-selected)", sel=r"selected"),
    D("选中行左条 2px --tt-primary（inset 阴影）", ("box-shadow",), has=("inset", "2px", "var(--tt-primary)"), sel=r"selected"),
    D("数字列右对齐", ("text-align",), eq="right"),
    D("mono 列 --tt-mono-sm", ("font",), eq="var(--tt-mono-sm)"),
]

KEYVALUE_SPECS = [
    D("两列网格", ("display",), eq="grid"),
    D("列宽 minmax(96px, max-content) 与 minmax(0, 1fr)", ("grid-template-columns",),
      has=("minmax(96px,max-content)", "minmax(0,1fr)")),
    D("行距 --tt-space-1", GAP, has=("var(--tt-space-1)",)),
    D("列距 --tt-space-3", GAP, has=("var(--tt-space-3)",)),
    D("字体 --tt-text-sm", ("font",), eq="var(--tt-text-sm)"),
    D("标签色 --tt-text-3", ("color",), eq="var(--tt-text-3)"),
    D("值色 --tt-text-1", ("color",), eq="var(--tt-text-1)"),
    D("等宽值 --tt-mono-sm", ("font",), eq="var(--tt-mono-sm)"),
    D("等宽值行高 20", ("line-height",), eq="20px"),
]

EMPTY_SPECS = [
    D("文字居中", ("text-align",), eq="center"),
    D("间距 --tt-space-1", GAP, has=("var(--tt-space-1)",)),
    D("内边距 --tt-space-6", PAD, has=("var(--tt-space-6)",)),
    D("内边距 --tt-space-4", PAD, has=("var(--tt-space-4)",)),
    D("边框 1px --tt-border", ("border",), has=("1px", "var(--tt-border)")),
    D("圆角 --tt-radius-lg", ("border-radius",), eq="var(--tt-radius-lg)"),
    D("图标宽 32（CSS 给 svg 定尺寸）", ("width",), eq="32px", sel=r"svg|icon"),
    D("图标高 32", ("height",), eq="32px", sel=r"svg|icon"),
    D("图标色 --tt-text-3", ("color",), eq="var(--tt-text-3)"),
    D("标题 --tt-title-sm", ("font",), eq="var(--tt-title-sm)"),
    D("说明 --tt-text-sm", ("font",), eq="var(--tt-text-sm)"),
    D("说明色 --tt-text-2", ("color",), eq="var(--tt-text-2)"),
    D("操作区上边距 --tt-space-1", ("margin-top", "padding-top", "margin-block-start", "margin"), has=("var(--tt-space-1)",)),
]

SKELETON_SPECS = [
    D("纵向间距 --tt-space-2", GAP, has=("var(--tt-space-2)",)),
    D("内边距 --tt-space-4", PAD, eq="var(--tt-space-4)"),
    D("边框 1px --tt-border", ("border",), has=("1px", "var(--tt-border)")),
    D("圆角 --tt-radius-lg", ("border-radius",), eq="var(--tt-radius-lg)"),
    D("条底 --tt-surface-3", BG, eq="var(--tt-surface-3)"),
    D("条圆角 --tt-radius-sm", ("border-radius",), eq="var(--tt-radius-sm)"),
]

PILL_SPECS = [
    D("高 24", ("height", "min-height"), eq="24px"),
    D("左右 --tt-space-2", PAD, has=("var(--tt-space-2)",)),
    D("间距 --tt-space-1", GAP, has=("var(--tt-space-1)",)),
    D("边框 1px --tt-border", ("border",), has=("1px", "var(--tt-border)")),
    D("圆角 --tt-radius-full", ("border-radius",), eq="var(--tt-radius-full)"),
    D("底 --tt-surface-1", BG, eq="var(--tt-surface-1)"),
    D("字体 --tt-text-caption", ("font",), eq="var(--tt-text-caption)"),
    D("悬停底 --tt-surface-3", BG, eq="var(--tt-surface-3)", sel=r"hover"),
    D("圆点宽 8", ("width",), eq="8px"),
    D("圆点高 8", ("height",), eq="8px"),
    D("浮层绝对定位", ("position",), eq="absolute"),
    D("浮层右对齐", ("right", "inset-inline-end"), zero=True),
    D("浮层在胶囊下方", ("top", "inset-block-start"), has=("100%",)),
    D("浮层宽 240", ("width",), eq="240px"),
    D("浮层内边距 --tt-space-2", PAD, has=("var(--tt-space-2)",)),
    D("浮层内边距 --tt-space-3", PAD, has=("var(--tt-space-3)",)),
    D("浮层边框 1px --tt-border", ("border",), has=("1px", "var(--tt-border)")),
    D("浮层圆角 --tt-radius-lg", ("border-radius",), eq="var(--tt-radius-lg)"),
    D("浮层阴影 --tt-shadow-2", ("box-shadow",), eq="var(--tt-shadow-2)"),
    D("浮层层级 --tt-z-popover", ("z-index",), eq="var(--tt-z-popover)"),
    D("浮层标签列 64", ("grid-template-columns", "width", "min-width", "flex-basis"), has=("64px",)),
    D("浮层字体 --tt-text-sm", ("font",), eq="var(--tt-text-sm)"),
    D("pid --tt-mono-sm", ("font",), eq="var(--tt-mono-sm)"),
]

BREADCRUMB_SPECS = [
    D("字体 --tt-text-sm", ("font",), eq="var(--tt-text-sm)"),
    D("字色 --tt-text-3", ("color",), eq="var(--tt-text-3)"),
    D("间距 --tt-space-1", GAP, has=("var(--tt-space-1)",)),
    D("链接色 --tt-link", ("color",), eq="var(--tt-link)"),
    D("链接不加下划线", ("text-decoration", "text-decoration-line"), eq="none"),
    D("当前项色 --tt-text-2", ("color",), eq="var(--tt-text-2)", sel=r"current"),
]


def pill_tone_problems(css):
    """连接胶囊三态的色调（组件板 :435–437、断线页 :449–450）：选择器提到该状态的规则里要有对应令牌。"""
    problems = []
    props = ("background", "background-color", "color", "fill", "border-color")

    # 已连接是缺省态，可以不带选择器；其余两态要在提到该状态的规则里（data-state 或类名后缀都行）。
    if not has_decl(css, props, has=("var(--tt-tone-success-fg)",)):
        problems.append("ConnectionPill.css：已连接的圆点色 var(--tt-tone-success-fg) 没有")
    for state, tokens in (("reconnecting", ("var(--tt-tone-warning-fg)",)),
                          ("disconnected", ("var(--tt-tone-danger-fg)", "var(--tt-danger-text)"))):
        pattern = rf"(?<![A-Za-z]){state}(?![A-Za-z])"
        for token in tokens:
            if not has_decl(css, props, has=(token,), sel=pattern):
                problems.append(f"ConnectionPill.css：选择器提到 {state} 的规则里没有 {token}")
    if not has_decl(css, ("color",), eq="var(--tt-text-2)"):
        problems.append("ConnectionPill.css：文字色 var(--tt-text-2) 没有")
    return problems


def size_in_source_or_css(tsx, css, size):
    """尺寸 size 写在 tsx 的 width/height/size 属性里，或写在 css 的 width 里。"""
    in_tsx = re.search(rf"\b(?:width|height|size)\s*=\s*(?:\{{\s*{size}\s*\}}|[\"']{size}[\"'])", strip_ts_comments(tsx))
    return bool(in_tsx or has_decl(css, ("width", "height"), eq=f"{size}px"))


def checkbox_icon_problems(tsx, css):
    problems = []
    if "CheckIcon" not in strip_ts_comments(tsx):
        problems.append("Checkbox.tsx 没有用 CheckIcon")
    if not size_in_source_or_css(tsx, css, 12):
        problems.append("Checkbox 的勾没有 12（tsx 的 width/height 属性或 css 的 width）")
    stroke_tsx = re.search(r"strokeWidth\s*=\s*(?:\{\s*3\s*\}|[\"']3[\"'])", strip_ts_comments(tsx))
    if not (stroke_tsx or has_decl(css, ("stroke-width",), eq="3")):
        problems.append("Checkbox 的勾没有描边 3（tsx 的 strokeWidth 或 css 的 stroke-width）")
    return problems


def breadcrumb_icon_problems(tsx, css):
    problems = []
    if "ChevronRightIcon" not in strip_ts_comments(tsx):
        problems.append("Breadcrumb.tsx 没有用 ChevronRightIcon")
    if not size_in_source_or_css(tsx, css, 14):
        problems.append("Breadcrumb 的分隔图标没有 14（tsx 的 width/height 属性或 css 的 width）")
    return problems


def select_icon_problems(tsx, css):
    problems = []
    if "ChevronDownIcon" not in strip_ts_comments(tsx):
        problems.append("Select.tsx 没有用 ChevronDownIcon")
    if not size_in_source_or_css(tsx, css, 16):
        problems.append("Select 的箭头没有 16（tsx 的 width/height 属性或 css 的 width）")
    return problems


def skeleton_problems(tsx, css):
    """骨架屏：条高 14/20/20/20、宽 40%/100%/82%/64%（写在 css 或 tsx 里都行）；不写动画、过渡、渐变；用 tt-skel；
    setTimeout 加具名常量 300；不用 rAF、performance。"""
    problems = spec_problems(css, "Skeleton.css", SKELETON_SPECS)
    code_tsx = strip_ts_comments(tsx)
    union = strip_comments(css) + "\n" + code_tsx
    for height in ("14", "20"):
        if not re.search(rf"(?<![\w.]){height}(?:px)?(?![\w%])", union):
            problems.append(f"Skeleton：条高 {height} 没有出现在 css 或 tsx 里")
    for width in ("40%", "100%", "82%", "64%"):
        if width not in union.replace(" ", ""):
            problems.append(f"Skeleton：条宽 {width} 没有出现在 css 或 tsx 里")
    plain = strip_comments(css)
    for word in ("animation", "transition", "gradient", "@keyframes"):
        if word in plain:
            problems.append(f"Skeleton.css 不该写 {word}（合同 10：不写动画、过渡、渐变；用 base.css 现成的 tt-pulse）")
    if "tt-skel" not in code_tsx:
        problems.append("Skeleton.tsx 的条没有用 tt-skel 类")
    if "setTimeout" not in code_tsx or "clearTimeout" not in code_tsx:
        problems.append("Skeleton.tsx 要用 setTimeout 计时并在卸载时 clearTimeout")
    if not re.search(r"\bconst\s+[A-Z][A-Z0-9_]*\s*(?::\s*number\s*)?=\s*300\b", code_tsx):
        problems.append("Skeleton.tsx 没有把 300 写成具名常量（const NAME = 300）")
    for word in ("requestAnimationFrame", "performance"):
        if re.search(rf"\b{word}\b", code_tsx):
            problems.append(f"Skeleton.tsx 不能用 {word}（fake timers 推不动）")
    return problems


FORBIDDEN_CALLS = ("matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver")


def source_rule_problems(label, text):
    """新组件与陈列页源码的守卫：不渲染 role=status；不调用 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver。"""
    code = strip_ts_comments(text)
    problems = []
    if re.search(r"""role\s*[=:]\s*\{?\s*["']status["']""", code):
        problems.append(f"{label}：新组件与新演示不能渲染 role=status")
    for name in FORBIDDEN_CALLS:
        if re.search(rf"\b{name}\b", code):
            problems.append(f"{label}：不能用 {name}")
    return problems


def new_source_files():
    """12 个新组件的 tsx、field/*.tsx、showcase/*.tsx（存在的）。"""
    files = [comp_path(name, "tsx") for name in NEW_COMPONENTS]
    for sub in (SRC / "components" / "field", SRC / "showcase"):
        if sub.is_dir():
            files += sorted(sub.glob("*.tsx"))
    return [p for p in files if p.is_file()]


# ---------------------------------------------------------------------------
# 探针（Vitest + jsdom）：每份一个 describe，用例数必须全部通过
# ---------------------------------------------------------------------------

PRELUDE = r"""
import * as React from 'react';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function advance(ms: number) {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}
function focusOn(el: HTMLElement) {
  act(() => {
    el.focus();
  });
}
function key(k: string, init: any = {}, target: Element | null = document.activeElement) {
  return fireEvent.keyDown(target as Element, { key: k, ...init });
}
function textOf(el: Element | null): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function escapeCalls(spy: any): number {
  return spy.mock.calls.filter((c: any[]) => c[0] && c[0].key === 'Escape').length;
}
function noStatusRole() {
  expect(document.querySelector('[role="status"]'), '新组件不能渲染 role=status').toBeNull();
}
"""

# P2：对话框遮罩只在点到自身时 preventDefault（合同 7.1）
PROBE_P2 = PRELUDE + r"""
let Dialog: any;

beforeAll(async () => {
  Dialog = (await import('../src/components/Dialog')).Dialog;
});

function Harness({ onClose }: { onClose: () => void }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div>
      <button type="button" id="gate-trigger" onClick={() => setOpen(true)}>
        打开对话框
      </button>
      <Dialog
        open={open}
        onClose={() => {
          onClose();
          setOpen(false);
        }}
        title="表单"
        footer={
          <>
            <button type="button">取消</button>
            <button type="button">确定</button>
          </>
        }
      >
        <p id="gate-text">说明文字</p>
        <input id="gate-input" aria-label="名称" />
      </Dialog>
    </div>
  );
}

function openIt() {
  const onClose = vi.fn();
  const r = render(<Harness onClose={onClose} />);
  const trigger = r.container.querySelector('#gate-trigger') as HTMLButtonElement;
  focusOn(trigger);
  fireEvent.click(trigger);
  const dialog = document.querySelector('[role="dialog"]') as HTMLElement;
  const scrim = document.querySelector('.tt-dialog-scrim') as HTMLElement;
  return { ...r, trigger, dialog, scrim, onClose };
}

describe('对话框遮罩（合同 7.1）', () => {
  it('在框内输入框上 mousedown 不被阻止，输入框能聚焦', () => {
    const { dialog } = openIt();
    expect(dialog, '应出现对话框').not.toBeNull();
    const input = dialog.querySelector('#gate-input') as HTMLInputElement;
    expect(fireEvent.mouseDown(input), '框内输入框上的 mousedown 不该被 preventDefault').toBe(true);
    focusOn(input);
    expect(document.activeElement).toBe(input);
  });

  it('在框内其他位置（正文、标题、对话框根、正文容器、底栏按钮）mousedown 都不被阻止', () => {
    const { dialog } = openIt();
    const targets: Element[] = [
      dialog,
      dialog.querySelector('#gate-text') as Element,
      dialog.querySelector('h2') as Element,
      dialog.querySelector('.tt-dialog__body') as Element,
      Array.from(dialog.querySelectorAll('button')).find((b) => textOf(b) === '确定') as Element,
    ];
    for (const el of targets) {
      expect(el, '找不到要测的元素').toBeTruthy();
      expect(fireEvent.mouseDown(el), '框内 ' + el.tagName + ' 上的 mousedown 不该被阻止').toBe(true);
    }
  });

  it('在遮罩本身上 mousedown 仍被阻止默认，点遮罩不关闭', () => {
    const { dialog, scrim, onClose } = openIt();
    expect(scrim, '应有遮罩 tt-dialog-scrim').not.toBeNull();
    expect(fireEvent.mouseDown(scrim), '遮罩本身的 mousedown 应被 preventDefault').toBe(false);
    fireEvent.click(scrim);
    expect(onClose).not.toHaveBeenCalled();
    expect(document.querySelector('[role="dialog"]')).toBe(dialog);
  });
});
"""

# P3：轻提示关闭钮外包工具提示；5000ms 计时照旧（合同 7.2）
PROBE_P3 = PRELUDE + r"""
let Toast: any;

beforeAll(async () => {
  Toast = (await import('../src/components/Toast')).Toast;
});

function tipEl(): HTMLElement | null {
  return document.querySelector('[role="tooltip"]');
}
function closeBtn(): HTMLButtonElement {
  return document.querySelector('button[aria-label="关闭提示"]') as HTMLButtonElement;
}
function mount(onClose: any = vi.fn()) {
  const r = render(
    <Toast open onClose={onClose}>
      已复制
    </Toast>,
  );
  return { ...r, onClose };
}

describe('轻提示关闭钮的工具提示', () => {
  it('悬停 399ms 没有提示，400ms 出现「关闭提示」，aria-describedby 指向它，移开立即消失', () => {
    mount();
    const btn = closeBtn();
    expect(btn, '应有名称为「关闭提示」的关闭钮').not.toBeNull();
    expect(tipEl()).toBeNull();
    fireEvent.mouseEnter(btn);
    advance(399);
    expect(tipEl(), '399ms 时还不该出现').toBeNull();
    advance(1);
    const tip = tipEl();
    expect(tip, '400ms 时应出现 role=tooltip').not.toBeNull();
    expect(textOf(tip)).toBe('关闭提示');
    expect(tip!.id).not.toBe('');
    expect(btn.getAttribute('aria-describedby')).toBe(tip!.id);
    fireEvent.mouseLeave(btn);
    expect(tipEl(), '移开应立即消失').toBeNull();
    expect(btn.hasAttribute('aria-describedby')).toBe(false);
  });

  it('聚焦同样 400ms 出现（399ms 没有），失焦立即消失', () => {
    mount();
    const btn = closeBtn();
    fireEvent.focus(btn);
    advance(399);
    expect(tipEl(), '聚焦 399ms 时还不该出现').toBeNull();
    advance(1);
    expect(tipEl(), '聚焦 400ms 时应出现').not.toBeNull();
    expect(textOf(tipEl())).toBe('关闭提示');
    fireEvent.blur(btn);
    expect(tipEl(), '失焦应立即消失').toBeNull();
  });

  it('关闭钮的名称仍是「关闭提示」、里面没有文字，点一下立即调一次 onClose', () => {
    const { onClose } = mount();
    const btn = closeBtn();
    expect(btn.getAttribute('type')).toBe('button');
    expect(textOf(btn)).toBe('');
    fireEvent.click(btn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('5000ms 的自动关闭照旧：4999ms 没调，5000ms 调一次', () => {
    const { onClose } = mount();
    advance(4999);
    expect(onClose).not.toHaveBeenCalled();
    advance(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
"""

# P4：分段选择（D01）
PROBE_P4 = PRELUDE + r"""
let SegmentedControl: any;

beforeAll(async () => {
  const mod: any = await import('../src/components/SegmentedControl');
  SegmentedControl = mod.SegmentedControl ?? mod.default;
});

const OPTIONS = [
  { value: 'a', label: '甲' },
  { value: 'b', label: '乙' },
  { value: 'c', label: '丙' },
];

function Shell({ initial, onChange }: { initial: string; onChange: (v: string) => void }) {
  const [value, setValue] = React.useState(initial);
  return (
    <SegmentedControl
      aria-label="分段"
      options={OPTIONS}
      value={value}
      onChange={(next: string) => {
        onChange(next);
        setValue(next);
      }}
    />
  );
}

function mount(initial = 'a') {
  const onChange = vi.fn();
  const r = render(<Shell initial={initial} onChange={onChange} />);
  const group = r.container.querySelector('[role="radiogroup"]') as HTMLElement;
  const radios = () => Array.from(group.querySelectorAll<HTMLElement>('[role="radio"]'));
  return { ...r, group, radios, onChange };
}
function checkedOf(list: HTMLElement[]) {
  return list.map((el) => el.getAttribute('aria-checked'));
}
function tabIndexOf(list: HTMLElement[]) {
  return list.map((el) => el.getAttribute('tabindex'));
}

describe('分段选择', () => {
  it('radiogroup 带 aria-label；段是 button type=button role=radio；aria-checked 只有选中段为 true，只有选中段 tabIndex=0', () => {
    const { group, radios } = mount('b');
    expect(group, '应有 role=radiogroup').not.toBeNull();
    expect(group.getAttribute('aria-label')).toBe('分段');
    const list = radios();
    expect(list.map((el) => textOf(el))).toEqual(['甲', '乙', '丙']);
    for (const el of list) {
      expect(el.tagName).toBe('BUTTON');
      expect(el.getAttribute('type')).toBe('button');
    }
    expect(checkedOf(list)).toEqual(['false', 'true', 'false']);
    expect(tabIndexOf(list)).toEqual(['-1', '0', '-1']);
    noStatusRole();
  });

  it('ArrowRight 选中下一段并移焦点：keydown 被 preventDefault，onChange 收到新值一次，tabIndex 随之移动', () => {
    const { radios, onChange } = mount('a');
    focusOn(radios()[0]);
    const notPrevented = key('ArrowRight');
    expect(notPrevented, 'ArrowRight 应被 preventDefault').toBe(false);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith('b');
    expect(checkedOf(radios())).toEqual(['false', 'true', 'false']);
    expect(tabIndexOf(radios())).toEqual(['-1', '0', '-1']);
    expect(document.activeElement).toBe(radios()[1]);
  });

  it('ArrowLeft 选中上一段并移焦点', () => {
    const { radios, onChange } = mount('c');
    focusOn(radios()[2]);
    expect(key('ArrowLeft'), 'ArrowLeft 应被 preventDefault').toBe(false);
    expect(onChange).toHaveBeenCalledWith('b');
    expect(checkedOf(radios())).toEqual(['false', 'true', 'false']);
    expect(document.activeElement).toBe(radios()[1]);
  });

  it('到头循环：末段按 ArrowRight 回第一段，首段按 ArrowLeft 到末段', () => {
    const { radios, onChange } = mount('c');
    focusOn(radios()[2]);
    key('ArrowRight');
    expect(onChange).toHaveBeenLastCalledWith('a');
    expect(checkedOf(radios())).toEqual(['true', 'false', 'false']);
    expect(document.activeElement).toBe(radios()[0]);
    key('ArrowLeft');
    expect(onChange).toHaveBeenLastCalledWith('c');
    expect(checkedOf(radios())).toEqual(['false', 'false', 'true']);
    expect(document.activeElement).toBe(radios()[2]);
  });

  it('只处理左右键：ArrowUp、ArrowDown、Home、End 不改选中', () => {
    const { radios, onChange } = mount('b');
    focusOn(radios()[1]);
    for (const k of ['ArrowUp', 'ArrowDown', 'Home', 'End']) {
      key(k);
    }
    expect(onChange).not.toHaveBeenCalled();
    expect(checkedOf(radios())).toEqual(['false', 'true', 'false']);
  });

  it('点击选中：onChange 收到该段的值，aria-checked 与 tabIndex 随之变', () => {
    const { radios, onChange } = mount('a');
    fireEvent.click(radios()[2]);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith('c');
    expect(checkedOf(radios())).toEqual(['false', 'false', 'true']);
    expect(tabIndexOf(radios())).toEqual(['-1', '-1', '0']);
  });
});
"""

# P5：开关与复选框（D02）
PROBE_P5 = PRELUDE + r"""
let Switch: any;
let Checkbox: any;

beforeAll(async () => {
  const s: any = await import('../src/components/Switch');
  Switch = s.Switch ?? s.default;
  const c: any = await import('../src/components/Checkbox');
  Checkbox = c.Checkbox ?? c.default;
});

function Shell({ Comp, initial, disabled, onChange }: any) {
  const [on, setOn] = React.useState(!!initial);
  return (
    <Comp
      label="自动刷新"
      checked={on}
      disabled={!!disabled}
      onChange={(next: any) => {
        onChange(next);
        setOn(typeof next === 'boolean' ? next : !on);
      }}
    />
  );
}

function mount(Comp: any, role: string, props: any = {}) {
  const onChange = vi.fn();
  const r = render(<Shell Comp={Comp} onChange={onChange} {...props} />);
  const el = r.getByRole(role, { name: /自动刷新/ }) as HTMLElement;
  return { ...r, el, onChange };
}

function structureCase(Comp: any, role: string) {
  const { el } = mount(Comp, role);
  expect(el.tagName, role + ' 应是 span，不是 button').toBe('SPAN');
  expect(el.getAttribute('aria-checked')).toBe('false');
  expect(el.getAttribute('tabindex'), '可用时 tabIndex=0').toBe('0');
  expect(el.querySelector('button, input'), '里面不能有 button 或 input').toBeNull();
  expect(textOf(el), '名称来自可见文字').toBe('自动刷新');
  noStatusRole();
}
function initialOnCase(Comp: any, role: string) {
  const { el } = mount(Comp, role, { initial: true });
  expect(el.getAttribute('aria-checked')).toBe('true');
}
function spaceCase(Comp: any, role: string, strictNext: boolean) {
  const { el, onChange } = mount(Comp, role);
  focusOn(el);
  expect(document.activeElement).toBe(el);
  const notPrevented = key(' ');
  expect(notPrevented, '空格的 keydown 应被 preventDefault').toBe(false);
  expect(onChange).toHaveBeenCalledTimes(1);
  if (strictNext) expect(onChange).toHaveBeenLastCalledWith(true);
  expect(el.getAttribute('aria-checked')).toBe('true');
  key(' ');
  expect(onChange).toHaveBeenCalledTimes(2);
  if (strictNext) expect(onChange).toHaveBeenLastCalledWith(false);
  expect(el.getAttribute('aria-checked')).toBe('false');
}
function repeatCase(Comp: any, role: string) {
  const { el, onChange } = mount(Comp, role);
  focusOn(el);
  key(' ', { repeat: true });
  expect(onChange, 'event.repeat 为真时不切换').not.toHaveBeenCalled();
  expect(el.getAttribute('aria-checked')).toBe('false');
}
function clickCase(Comp: any, role: string, strictNext: boolean) {
  const { el, onChange } = mount(Comp, role);
  fireEvent.click(el);
  expect(onChange).toHaveBeenCalledTimes(1);
  if (strictNext) expect(onChange).toHaveBeenLastCalledWith(true);
  expect(el.getAttribute('aria-checked')).toBe('true');
  const kids = Array.from(el.children);
  for (const child of kids) {
    fireEvent.click(child);
  }
  expect(onChange, '点击整个控件（轨道、文字）都切换，每次一次').toHaveBeenCalledTimes(1 + kids.length);
}
function disabledCase(Comp: any, role: string) {
  const { el, onChange } = mount(Comp, role, { disabled: true });
  expect(el.getAttribute('aria-disabled')).toBe('true');
  focusOn(el);
  expect(document.activeElement, '禁用时不可聚焦').not.toBe(el);
  fireEvent.click(el);
  key(' ', {}, el);
  expect(onChange).not.toHaveBeenCalled();
  expect(el.getAttribute('aria-checked')).toBe('false');
}

describe('开关与复选框', () => {
  it('开关：role=switch 的 span，aria-checked=false，tabIndex=0，名称来自可见文字', () => {
    structureCase(Switch, 'switch');
  });

  it('复选框：role=checkbox 的 span，aria-checked=false，tabIndex=0，名称来自可见文字', () => {
    structureCase(Checkbox, 'checkbox');
  });

  it('开关：checked 为真时 aria-checked=true', () => {
    initialOnCase(Switch, 'switch');
  });

  it('复选框：checked 为真时 aria-checked=true', () => {
    initialOnCase(Checkbox, 'checkbox');
  });

  it('开关：空格切换一次（onChange 收到下一个值），keydown 被 preventDefault', () => {
    spaceCase(Switch, 'switch', true);
  });

  it('复选框：空格切换一次，keydown 被 preventDefault', () => {
    spaceCase(Checkbox, 'checkbox', false);
  });

  it('开关：event.repeat 为真时空格不切换', () => {
    repeatCase(Switch, 'switch');
  });

  it('复选框：event.repeat 为真时空格不切换', () => {
    repeatCase(Checkbox, 'checkbox');
  });

  it('开关：点击整个控件切换', () => {
    clickCase(Switch, 'switch', true);
  });

  it('复选框：点击整个控件切换', () => {
    clickCase(Checkbox, 'checkbox', false);
  });

  it('开关：禁用时 aria-disabled=true、不可聚焦，点击与空格都不切换', () => {
    disabledCase(Switch, 'switch');
  });

  it('复选框：禁用时 aria-disabled=true、不可聚焦，点击与空格都不切换', () => {
    disabledCase(Checkbox, 'checkbox');
  });

  it('复选框只认空格，不认 Enter', () => {
    const { el, onChange } = mount(Checkbox, 'checkbox');
    focusOn(el);
    key('Enter');
    expect(onChange).not.toHaveBeenCalled();
    expect(el.getAttribute('aria-checked')).toBe('false');
  });
});
"""

# P6：页签（D03）
PROBE_P6 = PRELUDE + r"""
let Tabs: any;

beforeAll(async () => {
  const mod: any = await import('../src/components/Tabs');
  Tabs = mod.Tabs ?? mod.default;
});

const ITEMS = [
  { id: 't1', label: '概览' },
  { id: 't2', label: '日志' },
  { id: 't3', label: '设置' },
];

function Shell({ initial, onChange }: { initial: string; onChange: (id: string) => void }) {
  const [value, setValue] = React.useState(initial);
  return (
    <Tabs
      aria-label="页签"
      items={ITEMS}
      value={value}
      onChange={(id: string) => {
        onChange(id);
        setValue(id);
      }}
    >
      <p data-gate-panel={value}>面板 {value}</p>
    </Tabs>
  );
}

function mount(initial = 't1') {
  const onChange = vi.fn();
  const r = render(<Shell initial={initial} onChange={onChange} />);
  const list = r.container.querySelector('[role="tablist"]') as HTMLElement;
  const tabs = () => Array.from(list.querySelectorAll<HTMLElement>('[role="tab"]'));
  const panel = () => r.container.querySelector('[role="tabpanel"]') as HTMLElement;
  return { ...r, list, tabs, panel, onChange };
}
function selectedOf(list: HTMLElement[]) {
  return list.map((el) => el.getAttribute('aria-selected'));
}
function tabIndexOf(list: HTMLElement[]) {
  return list.map((el) => el.getAttribute('tabindex'));
}
function linkCheck(tabs: HTMLElement[], panel: HTMLElement, currentIndex: number) {
  const current = tabs[currentIndex];
  expect(current.id, '页签要有 id').not.toBe('');
  expect(panel.id, '面板要有 id').not.toBe('');
  expect(current.getAttribute('aria-controls'), '当前页签的 aria-controls 指向面板').toBe(panel.id);
  expect(panel.getAttribute('aria-labelledby'), '面板的 aria-labelledby 指向当前页签').toBe(current.id);
}

describe('页签', () => {
  it('tablist 带 aria-label；页签是 button type=button role=tab；只有当前页签 aria-selected=true 且 tabIndex=0；面板关联当前页签', () => {
    const { list, tabs, panel, container } = mount('t2');
    expect(list, '应有 role=tablist').not.toBeNull();
    expect(list.getAttribute('aria-label')).toBe('页签');
    const all = tabs();
    expect(all.map((el) => textOf(el))).toEqual(['概览', '日志', '设置']);
    for (const el of all) {
      expect(el.tagName).toBe('BUTTON');
      expect(el.getAttribute('type')).toBe('button');
    }
    expect(selectedOf(all)).toEqual(['false', 'true', 'false']);
    expect(tabIndexOf(all)).toEqual(['-1', '0', '-1']);
    expect(container.querySelectorAll('[role="tabpanel"]').length, '只渲染当前面板').toBe(1);
    expect(textOf(panel())).toContain('面板 t2');
    linkCheck(all, panel(), 1);
    noStatusRole();
  });

  it('ArrowRight 切到下一个页签并移焦点（自动激活）：keydown 被 preventDefault，onChange 收到 id 一次，面板跟着变', () => {
    const { tabs, panel, onChange } = mount('t1');
    focusOn(tabs()[0]);
    expect(key('ArrowRight'), 'ArrowRight 应被 preventDefault').toBe(false);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith('t2');
    expect(selectedOf(tabs())).toEqual(['false', 'true', 'false']);
    expect(tabIndexOf(tabs())).toEqual(['-1', '0', '-1']);
    expect(document.activeElement).toBe(tabs()[1]);
    expect(textOf(panel())).toContain('面板 t2');
    linkCheck(tabs(), panel(), 1);
  });

  it('ArrowLeft 切到上一个页签并移焦点', () => {
    const { tabs, onChange } = mount('t3');
    focusOn(tabs()[2]);
    expect(key('ArrowLeft'), 'ArrowLeft 应被 preventDefault').toBe(false);
    expect(onChange).toHaveBeenCalledWith('t2');
    expect(selectedOf(tabs())).toEqual(['false', 'true', 'false']);
    expect(document.activeElement).toBe(tabs()[1]);
  });

  it('到头循环：末页签按 ArrowRight 回第一个，首页签按 ArrowLeft 到末个', () => {
    const { tabs, panel, onChange } = mount('t3');
    focusOn(tabs()[2]);
    key('ArrowRight');
    expect(onChange).toHaveBeenLastCalledWith('t1');
    expect(selectedOf(tabs())).toEqual(['true', 'false', 'false']);
    expect(document.activeElement).toBe(tabs()[0]);
    expect(textOf(panel())).toContain('面板 t1');
    key('ArrowLeft');
    expect(onChange).toHaveBeenLastCalledWith('t3');
    expect(selectedOf(tabs())).toEqual(['false', 'false', 'true']);
    expect(document.activeElement).toBe(tabs()[2]);
  });

  it('Home 到首个、End 到末个，焦点跟着走，keydown 被 preventDefault', () => {
    const { tabs, panel, onChange } = mount('t2');
    focusOn(tabs()[1]);
    expect(key('End'), 'End 应被 preventDefault').toBe(false);
    expect(onChange).toHaveBeenLastCalledWith('t3');
    expect(document.activeElement).toBe(tabs()[2]);
    expect(selectedOf(tabs())).toEqual(['false', 'false', 'true']);
    linkCheck(tabs(), panel(), 2);
    expect(key('Home'), 'Home 应被 preventDefault').toBe(false);
    expect(onChange).toHaveBeenLastCalledWith('t1');
    expect(document.activeElement).toBe(tabs()[0]);
    expect(selectedOf(tabs())).toEqual(['true', 'false', 'false']);
    linkCheck(tabs(), panel(), 0);
  });

  it('点击页签选中它：onChange 收到 id，tabIndex 与面板随之变', () => {
    const { tabs, panel, onChange } = mount('t1');
    fireEvent.click(tabs()[2]);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith('t3');
    expect(selectedOf(tabs())).toEqual(['false', 'false', 'true']);
    expect(tabIndexOf(tabs())).toEqual(['-1', '-1', '0']);
    expect(textOf(panel())).toContain('面板 t3');
  });
});
"""

# P7：输入框与下拉（D04）
PROBE_P7 = PRELUDE + r"""
let TextField: any;
let Select: any;

beforeAll(async () => {
  const t: any = await import('../src/components/TextField');
  TextField = t.TextField ?? t.default;
  const s: any = await import('../src/components/Select');
  Select = s.Select ?? s.default;
});

const OPTIONS = [
  { value: 'dev', label: '开发' },
  { value: 'prod', label: '生产' },
  { value: 'test', label: '测试' },
];

function describedTexts(el: HTMLElement): string[] {
  const ids = (el.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
  return ids.map((id) => {
    const target = document.getElementById(id);
    expect(target, 'aria-describedby 里的 id ' + id + ' 应指向存在的元素').not.toBeNull();
    return textOf(target);
  });
}
function signature(container: Element): string {
  return container.innerHTML.replace(/\s(?:id|for|aria-describedby)="[^"]*"/g, '');
}
function mountField(props: any = {}) {
  const r = render(<TextField label="用户名" value="" onChange={() => {}} {...props} />);
  const input = r.container.querySelector('input') as HTMLInputElement;
  const label = r.container.querySelector('label') as HTMLLabelElement;
  return { ...r, input, label };
}
function SelectShell({ onChange, ...rest }: any) {
  const [v, setV] = React.useState('dev');
  return (
    <Select
      label="环境"
      options={OPTIONS}
      value={v}
      onChange={(arg: any) => {
        onChange(arg);
        setV(typeof arg === 'string' ? arg : arg.target.value);
      }}
      {...rest}
    />
  );
}
function mountSelect(props: any = {}) {
  const onChange = vi.fn();
  const r = render(<SelectShell onChange={onChange} {...props} />);
  const select = r.container.querySelector('select') as HTMLSelectElement;
  const label = r.container.querySelector('label') as HTMLLabelElement;
  return { ...r, select, label, onChange };
}

describe('输入框', () => {
  it('label 用 htmlFor 关联 input；placeholder 透传；没有 role=status', () => {
    const { input, label } = mountField({ placeholder: '输入名称' });
    expect(input, '应有 input').not.toBeNull();
    expect(textOf(label)).toBe('用户名');
    expect(input.id).not.toBe('');
    expect(label.htmlFor).toBe(input.id);
    expect(document.getElementById(input.id)).toBe(input);
    expect(input.getAttribute('placeholder')).toBe('输入名称');
    noStatusRole();
  });

  it('value、disabled 透传给 input，onChange 在输入时被调用', () => {
    const onChange = vi.fn();
    const { input } = mountField({ value: 'abc', disabled: true, onChange });
    expect(input.value).toBe('abc');
    expect(input.disabled).toBe(true);
    const r2 = mountField({ onChange });
    fireEvent.change(r2.input, { target: { value: 'x' } });
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it('只给帮助文字：aria-describedby 只含帮助文字的 id，没有 aria-invalid=true', () => {
    const { input } = mountField({ help: '三到十六个字符' });
    expect(describedTexts(input)).toEqual(['三到十六个字符']);
    expect(input.getAttribute('aria-invalid')).not.toBe('true');
  });

  it('只给出错文字：aria-describedby 只含出错文字的 id，aria-invalid=true', () => {
    const { input } = mountField({ error: '名称已被占用' });
    expect(describedTexts(input)).toEqual(['名称已被占用']);
    expect(input.getAttribute('aria-invalid')).toBe('true');
  });

  it('两者都给：都显示，aria-describedby 依次放出错、帮助的 id，aria-invalid=true', () => {
    const { input, container } = mountField({ help: '三到十六个字符', error: '名称已被占用' });
    expect(describedTexts(input)).toEqual(['名称已被占用', '三到十六个字符']);
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(textOf(container)).toContain('名称已被占用');
    expect(textOf(container)).toContain('三到十六个字符');
  });

  it('两者都不给：没有 aria-describedby，没有 aria-invalid=true', () => {
    const { input } = mountField();
    expect((input.getAttribute('aria-describedby') || '').trim()).toBe('');
    expect(input.getAttribute('aria-invalid')).not.toBe('true');
  });

  it('mono 的结构与非 mono 不同（值用等宽）', () => {
    const a = mountField();
    const plain = signature(a.container);
    a.unmount();
    const b = mountField({ mono: true });
    expect(signature(b.container)).not.toBe(plain);
  });
});

describe('下拉', () => {
  it('原生 select，label 关联，选项与值对得上，右侧箭头图标 aria-hidden 且不在 select 里', () => {
    const { select, label, container } = mountSelect();
    expect(select, '应有原生 select').not.toBeNull();
    expect(textOf(label)).toBe('环境');
    expect(select.id).not.toBe('');
    expect(label.htmlFor).toBe(select.id);
    const options = Array.from(select.querySelectorAll('option'));
    expect(options.map((o) => o.getAttribute('value'))).toEqual(['dev', 'prod', 'test']);
    expect(options.map((o) => textOf(o))).toEqual(['开发', '生产', '测试']);
    expect(select.value).toBe('dev');
    const chevron = container.querySelector('svg[aria-hidden="true"]');
    expect(chevron, '应有 aria-hidden 的箭头图标').not.toBeNull();
    expect(select.contains(chevron), '箭头图标不能放进 select').toBe(false);
    noStatusRole();
  });

  it('选择另一项：onChange 被调用一次，select 的值随之变', () => {
    const { select, onChange } = mountSelect();
    fireEvent.change(select, { target: { value: 'prod' } });
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(select.value).toBe('prod');
  });

  it('帮助与出错：aria-describedby 依次放出错、帮助的 id，aria-invalid=true', () => {
    const { select } = mountSelect({ help: '决定部署位置', error: '请选择生产以外的环境' });
    expect(describedTexts(select)).toEqual(['请选择生产以外的环境', '决定部署位置']);
    expect(select.getAttribute('aria-invalid')).toBe('true');
  });

  it('只给帮助：只含帮助的 id；都不给：没有 aria-describedby', () => {
    const a = mountSelect({ help: '决定部署位置' });
    expect(describedTexts(a.select)).toEqual(['决定部署位置']);
    expect(a.select.getAttribute('aria-invalid')).not.toBe('true');
    a.unmount();
    const b = mountSelect();
    expect((b.select.getAttribute('aria-describedby') || '').trim()).toBe('');
  });

  it('disabled 透传给 select', () => {
    const { select } = mountSelect({ disabled: true });
    expect(select.disabled).toBe(true);
  });
});
"""

# P8：表格（D05）
PROBE_P8 = PRELUDE + r"""
let Table: any;

beforeAll(async () => {
  const mod: any = await import('../src/components/Table');
  Table = mod.Table ?? mod.default;
});

const COLUMNS = [
  { key: 'name', header: '任务' },
  { key: 'dur', header: '用时', numeric: true },
  { key: 'tok', header: 'token', numeric: true },
  { key: 'id', header: '编号', mono: true },
];
const ROWS = [
  { id: 'r1', name: '甲任务', dur: '12.5', tok: '1200' },
  { id: 'r2', name: '乙任务', dur: '8.0', tok: '640' },
  { id: 'r3', name: '丙任务', dur: '31.2', tok: '5120' },
  { id: 'r4', name: '丁任务', dur: '4.4', tok: '300' },
  { id: 'r5', name: '戊任务', dur: '19.9', tok: '2048' },
];

function mount(props: any = {}) {
  const onRowOpen = vi.fn();
  const r = render(
    <Table
      aria-label="任务表"
      className="gate-limit"
      columns={COLUMNS}
      rows={ROWS}
      rowKey={(row: any) => row.id}
      onRowOpen={onRowOpen}
      {...props}
    />,
  );
  const table = r.container.querySelector('table') as HTMLTableElement;
  const rows = () => Array.from(table.querySelectorAll<HTMLElement>('tbody tr'));
  return { ...r, table, rows, onRowOpen };
}
function zeroIndexes(rows: HTMLElement[]) {
  return rows.map((r, i) => (r.getAttribute('tabindex') === '0' ? i : -1)).filter((i) => i >= 0);
}
function isSelected(el: HTMLElement) {
  return el.hasAttribute('data-selected') && el.getAttribute('data-selected') !== 'false';
}

describe('表格', () => {
  it('滚动容器 div 带调用方的 className 并包着原生 table；表头 th scope=col；aria-label；缺省 data-row-height=40', () => {
    const { table, rows, container } = mount();
    expect(table, '应有原生 table').not.toBeNull();
    const box = table.closest('div.gate-limit');
    expect(box, 'className 应加在包着 table 的滚动容器 div 上').not.toBeNull();
    expect(container.querySelector('[aria-label="任务表"]'), '应有 aria-label').not.toBeNull();
    const ths = Array.from(table.querySelectorAll('th'));
    expect(ths.map((th) => textOf(th))).toEqual(['任务', '用时', 'token', '编号']);
    for (const th of ths) expect(th.getAttribute('scope')).toBe('col');
    expect(rows().length).toBe(5);
    expect(table.getAttribute('data-row-height')).toBe('40');
    noStatusRole();
  });

  it('rowHeight 44、52 反映在 table 的 data-row-height 上', () => {
    const a = mount({ rowHeight: 44 });
    expect(a.table.getAttribute('data-row-height')).toBe('44');
    a.unmount();
    const b = mount({ rowHeight: 52 });
    expect(b.table.getAttribute('data-row-height')).toBe('52');
    b.unmount();
    const c = mount({ rowHeight: 40 });
    expect(c.table.getAttribute('data-row-height')).toBe('40');
  });

  it('数字列的单元格带 tt-num，其余列不带', () => {
    const { rows } = mount();
    for (const tr of rows()) {
      const cells = Array.from(tr.children);
      expect(cells.length).toBe(4);
      expect(cells[1].classList.contains('tt-num'), '用时列应带 tt-num').toBe(true);
      expect(cells[2].classList.contains('tt-num'), 'token 列应带 tt-num').toBe(true);
      expect(cells[0].classList.contains('tt-num')).toBe(false);
      expect(cells[3].classList.contains('tt-num')).toBe(false);
    }
    expect(textOf(rows()[0].children[1])).toBe('12.5');
  });

  it('恰一行 tabIndex=0：没有 selectedKey 时是第一行；有 selectedKey 时是选中行，且只有它带 data-selected', () => {
    const a = mount();
    expect(zeroIndexes(a.rows())).toEqual([0]);
    expect(a.table.querySelectorAll('tr[tabindex="0"]').length).toBe(1);
    expect(a.rows().filter(isSelected).length).toBe(0);
    a.unmount();
    const b = mount({ selectedKey: 'r3' });
    expect(zeroIndexes(b.rows())).toEqual([2]);
    expect(b.table.querySelectorAll('tr[tabindex="0"]').length).toBe(1);
    expect(b.rows().map(isSelected)).toEqual([false, false, true, false, false]);
  });

  it('ArrowDown、ArrowUp 逐行移动并移焦点（keydown 被 preventDefault），tabIndex 随之移动', () => {
    const { rows } = mount();
    focusOn(rows()[0]);
    expect(key('ArrowDown'), 'ArrowDown 应被 preventDefault').toBe(false);
    expect(document.activeElement).toBe(rows()[1]);
    expect(zeroIndexes(rows())).toEqual([1]);
    key('ArrowDown');
    expect(document.activeElement).toBe(rows()[2]);
    expect(zeroIndexes(rows())).toEqual([2]);
    expect(key('ArrowUp'), 'ArrowUp 应被 preventDefault').toBe(false);
    expect(document.activeElement).toBe(rows()[1]);
    expect(zeroIndexes(rows())).toEqual([1]);
  });

  it('到头不循环：首行按 ArrowUp、末行按 ArrowDown 都停在原地', () => {
    const { rows } = mount();
    focusOn(rows()[0]);
    key('ArrowUp');
    expect(document.activeElement, '首行 ArrowUp 不循环').toBe(rows()[0]);
    expect(zeroIndexes(rows())).toEqual([0]);
    focusOn(rows()[4]);
    key('ArrowDown');
    expect(document.activeElement, '末行 ArrowDown 不循环').toBe(rows()[4]);
    expect(zeroIndexes(rows())).toEqual([4]);
  });

  it('Home 到首行、End 到末行，keydown 被 preventDefault', () => {
    const { rows } = mount();
    focusOn(rows()[0]);
    key('ArrowDown');
    key('ArrowDown');
    expect(key('End'), 'End 应被 preventDefault').toBe(false);
    expect(document.activeElement).toBe(rows()[4]);
    expect(zeroIndexes(rows())).toEqual([4]);
    expect(key('Home'), 'Home 应被 preventDefault').toBe(false);
    expect(document.activeElement).toBe(rows()[0]);
    expect(zeroIndexes(rows())).toEqual([0]);
  });

  it('起点是选中行：selectedKey=r3 时 ArrowDown 到第四行', () => {
    const { rows } = mount({ selectedKey: 'r3' });
    focusOn(rows()[2]);
    key('ArrowDown');
    expect(document.activeElement).toBe(rows()[3]);
    expect(zeroIndexes(rows())).toEqual([3]);
  });

  it('Enter 调一次 onRowOpen(当前行的 key)，keydown 被 preventDefault；方向键移动本身不调', () => {
    const { rows, onRowOpen } = mount();
    focusOn(rows()[0]);
    key('ArrowDown');
    key('ArrowDown');
    expect(onRowOpen).not.toHaveBeenCalled();
    expect(key('Enter'), 'Enter 应被 preventDefault').toBe(false);
    expect(onRowOpen).toHaveBeenCalledTimes(1);
    expect(onRowOpen).toHaveBeenCalledWith('r3');
  });

  it('点击行等于让它成为当前行并调 onRowOpen(key)', () => {
    const { rows, onRowOpen } = mount();
    fireEvent.click(rows()[3]);
    expect(onRowOpen).toHaveBeenCalledTimes(1);
    expect(onRowOpen).toHaveBeenCalledWith('r4');
    expect(zeroIndexes(rows())).toEqual([3]);
  });

  it('表格与容器本身不进 Tab 序列，单元格里没有可聚焦元素', () => {
    const { table } = mount();
    const box = table.closest('div.gate-limit') as HTMLElement;
    expect(table.getAttribute('tabindex')).not.toBe('0');
    expect(box.getAttribute('tabindex')).not.toBe('0');
    expect(table.querySelectorAll('td a, td button, td input, td select, td textarea, td [tabindex], th [tabindex], th button, th a').length).toBe(0);
    expect(table.querySelectorAll('thead tr[tabindex="0"]').length).toBe(0);
  });
});
"""

# P9：键值列表、空状态、面包屑（D06）
PROBE_P9 = PRELUDE + r"""
let KeyValueList: any;
let EmptyState: any;
let Breadcrumb: any;

const LIST_DS: string[] = __LIST_DS__;

beforeAll(async () => {
  const k: any = await import('../src/components/KeyValueList');
  KeyValueList = k.KeyValueList ?? k.default;
  const e: any = await import('../src/components/EmptyState');
  EmptyState = e.EmptyState ?? e.default;
  const b: any = await import('../src/components/Breadcrumb');
  Breadcrumb = b.Breadcrumb ?? b.default;
});

function shape(el: Element): string {
  return el.outerHTML.replace(el.textContent || '', '');
}

describe('键值列表', () => {
  it('dl 里每项一对 dt、dd，文字与顺序对得上，没有 role=status', () => {
    const { container } = render(
      <KeyValueList
        items={[
          { label: '分支', value: 'main' },
          { label: '提交', value: 'a1b2c3d', mono: true },
          { label: '状态', value: '已通过' },
        ]}
      />,
    );
    const dl = container.querySelector('dl');
    expect(dl, '应有 dl').not.toBeNull();
    const dts = Array.from(dl!.querySelectorAll('dt'));
    const dds = Array.from(dl!.querySelectorAll('dd'));
    expect(dts.map((el) => textOf(el))).toEqual(['分支', '提交', '状态']);
    expect(dds.map((el) => textOf(el))).toEqual(['main', 'a1b2c3d', '已通过']);
    for (const dt of dts) {
      expect(dt.nextElementSibling && dt.nextElementSibling.tagName, 'dt 后面紧跟 dd').toBe('DD');
    }
    noStatusRole();
  });

  it('mono 的值与普通值的结构不同（等宽值）', () => {
    const { container } = render(
      <KeyValueList
        items={[
          { label: '分支', value: 'main' },
          { label: '提交', value: 'a1b2c3d', mono: true },
        ]}
      />,
    );
    const dds = Array.from(container.querySelectorAll('dd'));
    expect(shape(dds[1])).not.toBe(shape(dds[0]).replace('main', 'a1b2c3d'));
    expect(shape(dds[0])).not.toBe(shape(dds[1]));
  });
});

describe('空状态', () => {
  it('缺省图标是 ListChecksIcon（路径等于组件板 :466），aria-hidden；标题、说明、操作区都显示', () => {
    const onClick = vi.fn();
    const { container } = render(
      <EmptyState title="还没有任务" description="创建第一个任务开始" action={<button type="button" onClick={onClick}>新建任务</button>} />,
    );
    const svg = container.querySelector('svg');
    expect(svg, '缺省应有图标').not.toBeNull();
    expect(svg!.getAttribute('aria-hidden')).toBe('true');
    expect(Array.from(svg!.querySelectorAll('path')).map((p) => p.getAttribute('d'))).toEqual(LIST_DS);
    const text = textOf(container);
    expect(text).toContain('还没有任务');
    expect(text).toContain('创建第一个任务开始');
    const btn = container.querySelector('button') as HTMLButtonElement;
    expect(textOf(btn)).toBe('新建任务');
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
    noStatusRole();
  });

  it('没有 action 时不渲染操作区：除图标外没有空元素，也没有按钮', () => {
    const { container } = render(<EmptyState title="还没有任务" description="创建第一个任务开始" />);
    expect(textOf(container)).toContain('还没有任务');
    const empties = Array.from(container.querySelectorAll('*')).filter(
      (el) => !el.closest('svg') && el.children.length === 0 && textOf(el) === '',
    );
    expect(empties.length, '没有 action 就不渲染操作区（也不留空元素）').toBe(0);
    expect(container.querySelectorAll('button').length).toBe(0);
  });
});

describe('面包屑', () => {
  it('nav 的 aria-label 是「面包屑」，里面一个 ol；有 href 的前项是 a，没有的是 button type=button；分隔图标 aria-hidden', () => {
    const onClick = vi.fn();
    const { container } = render(
      <Breadcrumb
        items={[
          { label: '项目', href: 'https://example.invalid/projects' },
          { label: '任务', onClick },
          { label: '详情' },
        ]}
      />,
    );
    const nav = container.querySelector('nav');
    expect(nav, '应有 nav').not.toBeNull();
    expect(nav!.getAttribute('aria-label')).toBe('面包屑');
    expect(nav!.querySelectorAll('ol').length).toBe(1);
    const link = nav!.querySelector('a') as HTMLAnchorElement;
    expect(textOf(link)).toBe('项目');
    expect(link.getAttribute('href')).toBe('https://example.invalid/projects');
    const btn = nav!.querySelector('button') as HTMLButtonElement;
    expect(textOf(btn)).toBe('任务');
    expect(btn.getAttribute('type')).toBe('button');
    fireEvent.click(btn);
    expect(onClick).toHaveBeenCalledTimes(1);
    const svgs = Array.from(nav!.querySelectorAll('svg'));
    expect(svgs.length, '项之间各一个分隔图标').toBe(2);
    for (const svg of svgs) expect(svg.getAttribute('aria-hidden')).toBe('true');
    noStatusRole();
  });

  it('最后一项是带 aria-current=page 的 span，既不是链接也不是按钮，且只有它带 aria-current', () => {
    const { container } = render(
      <Breadcrumb items={[{ label: '项目', href: 'https://example.invalid/projects' }, { label: '任务', onClick: () => {} }, { label: '详情' }]} />,
    );
    const current = container.querySelectorAll('[aria-current]');
    expect(current.length).toBe(1);
    const last = current[0] as HTMLElement;
    expect(last.getAttribute('aria-current')).toBe('page');
    expect(last.tagName).toBe('SPAN');
    expect(textOf(last)).toBe('详情');
    expect(last.closest('a, button'), '当前项不是链接也不是按钮').toBeNull();
  });

  it('末项即使给了 href 也只是 span；只有一项时没有分隔图标', () => {
    const a = render(<Breadcrumb items={[{ label: '项目', href: 'https://example.invalid/p' }, { label: '详情', href: 'https://example.invalid/d' }]} />);
    const last = a.container.querySelector('[aria-current="page"]') as HTMLElement;
    expect(last.tagName).toBe('SPAN');
    expect(last.closest('a, button')).toBeNull();
    a.unmount();
    const b = render(<Breadcrumb items={[{ label: '详情' }]} />);
    expect(b.container.querySelectorAll('svg').length).toBe(0);
    expect(b.container.querySelector('[aria-current="page"]')).not.toBeNull();
  });
});
"""

# P10：骨架屏（D07）
PROBE_P10 = PRELUDE + r"""
let Skeleton: any;

beforeAll(async () => {
  const mod: any = await import('../src/components/Skeleton');
  Skeleton = mod.Skeleton ?? mod.default;
});

function bars(root: Element) {
  return Array.from(root.querySelectorAll('.tt-skel'));
}
function calibrate(): number {
  const r = render(<div />);
  r.unmount();
  return vi.getTimerCount();
}

describe('骨架屏', () => {
  it('挂载后 299ms 什么都不渲染，300ms 出现：4 条 tt-skel（aria-hidden），容器 aria-busy=true', () => {
    const { container } = render(<Skeleton />);
    expect(container.innerHTML, '挂载时不渲染任何骨架元素').toBe('');
    advance(299);
    expect(container.innerHTML, '299ms 时还不该出现').toBe('');
    advance(1);
    const list = bars(container);
    expect(list.length, '300ms 时应出现 4 条骨架条').toBe(4);
    for (const el of list) expect(el.getAttribute('aria-hidden')).toBe('true');
    const busy = container.querySelector('[aria-busy="true"]');
    expect(busy, '容器应带 aria-busy=true').not.toBeNull();
    for (const el of list) expect(busy!.contains(el)).toBe(true);
    noStatusRole();
  });

  it('300ms 前卸载：计时器清掉，什么都不出现', () => {
    const base = calibrate();
    const r = render(<Skeleton />);
    advance(200);
    r.unmount();
    expect(vi.getTimerCount(), '卸载时应清掉计时器').toBe(base);
    advance(1000);
    expect(document.querySelector('.tt-skel')).toBeNull();
    expect(document.querySelector('[aria-busy]')).toBeNull();
  });

  it('StrictMode 下计时幂等：299ms 没有、300ms 恰 4 条，提前卸载也不留计时器', () => {
    const base = calibrate();
    const a = render(
      <React.StrictMode>
        <Skeleton />
      </React.StrictMode>,
    );
    advance(299);
    expect(a.container.innerHTML).toBe('');
    advance(1);
    expect(bars(a.container).length).toBe(4);
    a.unmount();
    const b = render(
      <React.StrictMode>
        <Skeleton />
      </React.StrictMode>,
    );
    advance(100);
    b.unmount();
    expect(vi.getTimerCount()).toBe(base);
  });

  it('每次挂载都重新计时：出现之后卸载再挂载，又是 299ms 没有、300ms 有', () => {
    const a = render(<Skeleton />);
    advance(300);
    expect(bars(a.container).length).toBe(4);
    a.unmount();
    const b = render(<Skeleton />);
    advance(299);
    expect(b.container.innerHTML).toBe('');
    advance(1);
    expect(bars(b.container).length).toBe(4);
  });
});
"""

# P11：连接胶囊（D08）
PROBE_P11 = PRELUDE + r"""
let ConnectionPill: any;

beforeAll(async () => {
  const mod: any = await import('../src/components/ConnectionPill');
  ConnectionPill = mod.ConnectionPill ?? mod.default;
});

function mountPill(props: any = {}, outer?: any) {
  const ui = <ConnectionPill state="connected" {...props} />;
  const r = render(outer ? <div onKeyDown={outer}>{ui}</div> : ui);
  const pill = r.container.querySelector('button[aria-expanded]') as HTMLButtonElement;
  return { ...r, pill };
}
function popoverOf(pill: HTMLElement): HTMLElement | null {
  const id = pill.getAttribute('aria-controls');
  if (!id) return null;
  const el = document.getElementById(id);
  if (!el || (el as HTMLElement).hidden || (el as HTMLElement).style.display === 'none') return null;
  return el as HTMLElement;
}

describe('连接胶囊', () => {
  it('已连接：胶囊是 button type=button，文字「已连接」，根上 data-state=connected，圆点 aria-hidden，文字 aria-live=polite', () => {
    const { pill, container } = mountPill({ state: 'connected' });
    expect(pill, '应有带 aria-expanded 的 button').not.toBeNull();
    expect(pill.getAttribute('type')).toBe('button');
    expect(textOf(pill)).toBe('已连接');
    expect(container.querySelector('[data-state="connected"]'), '根上应带 data-state').not.toBeNull();
    expect(pill.querySelector('[aria-hidden="true"]'), '圆点应 aria-hidden').not.toBeNull();
    const live = pill.querySelector('[aria-live="polite"]');
    expect(live, '状态文字应带 aria-live=polite').not.toBeNull();
    expect(textOf(live)).toBe('已连接');
    noStatusRole();
  });

  it('重连中：文字「重连中（第 N 次）」，data-state=reconnecting；已断开：文字「已断开」，data-state=disconnected', () => {
    const a = mountPill({ state: 'reconnecting', attempt: 3 });
    expect(textOf(a.pill)).toMatch(/^重连中（第\s*3\s*次）$/);
    expect(a.container.querySelector('[data-state="reconnecting"]')).not.toBeNull();
    a.unmount();
    const b = mountPill({ state: 'disconnected' });
    expect(textOf(b.pill)).toBe('已断开');
    expect(b.container.querySelector('[data-state="disconnected"]')).not.toBeNull();
  });

  it('点一下打开浮层、再点关闭：aria-expanded 随之变，打开后 aria-controls 指向浮层，浮层紧跟胶囊', () => {
    const { pill } = mountPill({ pid: 4242, startedAt: '2026-10-20 10:00', stream: '事件流正常' });
    expect(pill.getAttribute('aria-expanded')).toBe('false');
    expect(popoverOf(pill), '关闭时不显示浮层').toBeNull();
    fireEvent.click(pill);
    expect(pill.getAttribute('aria-expanded')).toBe('true');
    const pop = popoverOf(pill);
    expect(pop, '打开后 aria-controls 应指向存在的浮层').not.toBeNull();
    expect(
      pop!.previousElementSibling === pill || (pill.nextElementSibling !== null && pill.nextElementSibling.contains(pop)),
      '浮层在 DOM 里紧跟胶囊',
    ).toBe(true);
    fireEvent.click(pill);
    expect(pill.getAttribute('aria-expanded')).toBe('false');
    expect(popoverOf(pill), '再点一下应关闭').toBeNull();
  });

  it('浮层里是小键值表：pid、启动于、事件流三行标签，值对得上；没有可聚焦元素，焦点不移进去', () => {
    const { pill } = mountPill({ pid: 4242, startedAt: '2026-10-20 10:00', stream: '事件流正常' });
    focusOn(pill);
    fireEvent.click(pill);
    const pop = popoverOf(pill) as HTMLElement;
    const dts = Array.from(pop.querySelectorAll('dt')).map((el) => textOf(el));
    const dds = Array.from(pop.querySelectorAll('dd')).map((el) => textOf(el));
    expect(dts).toEqual(['pid', '启动于', '事件流']);
    expect(dds).toEqual(['4242', '2026-10-20 10:00', '事件流正常']);
    expect(pop.querySelectorAll('a[href], button, input, select, textarea, [tabindex]').length).toBe(0);
    expect(document.activeElement, '焦点留在胶囊上').toBe(pill);
  });

  it('没给的值显示「未知」', () => {
    const { pill } = mountPill({ state: 'connected' });
    fireEvent.click(pill);
    const pop = popoverOf(pill) as HTMLElement;
    const dds = Array.from(pop.querySelectorAll('dd')).map((el) => textOf(el));
    expect(dds).toEqual(['未知', '未知', '未知']);
  });

  it('浮层打开、焦点在胶囊上按 Esc：关闭并 stopPropagation，焦点留在胶囊', () => {
    const outer = vi.fn();
    const { pill } = mountPill({ pid: 1 }, outer);
    focusOn(pill);
    fireEvent.click(pill);
    expect(popoverOf(pill)).not.toBeNull();
    key('Escape');
    expect(popoverOf(pill), 'Esc 后应关闭').toBeNull();
    expect(pill.getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement, '焦点留在胶囊').toBe(pill);
    expect(escapeCalls(outer), 'Esc 由胶囊处理，stopPropagation').toBe(0);
  });

  it('在胶囊与浮层之外按下鼠标：关闭；在浮层或胶囊上按下鼠标不关', () => {
    const { pill } = mountPill({ pid: 1 });
    fireEvent.click(pill);
    const pop = popoverOf(pill) as HTMLElement;
    fireEvent.mouseDown(pop);
    expect(popoverOf(pill), '在浮层里按下鼠标不该关').not.toBeNull();
    fireEvent.mouseDown(pill);
    expect(popoverOf(pill), '在胶囊上按下鼠标不该关').not.toBeNull();
    fireEvent.mouseDown(document.body);
    expect(popoverOf(pill), '在外面按下鼠标应关闭').toBeNull();
    expect(pill.getAttribute('aria-expanded')).toBe('false');
  });
});
"""

# (键, 探针源码, 需要先存在的仓库文件)
PROBE_SPECS = {
    "p2": (PROBE_P2, [f"{COMP_REL}/Dialog.tsx"]),
    "p3": (PROBE_P3, [f"{COMP_REL}/Toast.tsx", f"{COMP_REL}/Tooltip.tsx"]),
    "p4": (PROBE_P4, [f"{COMP_REL}/SegmentedControl.tsx"]),
    "p5": (PROBE_P5, [f"{COMP_REL}/Switch.tsx", f"{COMP_REL}/Checkbox.tsx"]),
    "p6": (PROBE_P6, [f"{COMP_REL}/Tabs.tsx"]),
    "p7": (PROBE_P7, [f"{COMP_REL}/TextField.tsx", f"{COMP_REL}/Select.tsx"]),
    "p8": (PROBE_P8, [f"{COMP_REL}/Table.tsx"]),
    "p9": (PROBE_P9, [f"{COMP_REL}/KeyValueList.tsx", f"{COMP_REL}/EmptyState.tsx", f"{COMP_REL}/Breadcrumb.tsx"]),
    "p10": (PROBE_P10, [f"{COMP_REL}/Skeleton.tsx"]),
    "p11": (PROBE_P11, [f"{COMP_REL}/ConnectionPill.tsx"]),
}
# 组件探针按编号顺序逐份跑（陈列页探针 P12 已退役）
PROBE_ORDER = ("p2", "p3", "p4", "p5", "p6", "p7", "p8", "p9", "p10", "p11")


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


def build_probe_source(key):
    source = PROBE_SPECS[key][0]
    if key == "p9":
        source = source.replace("__LIST_DS__", json.dumps(canvas_line_icon_ds(466), ensure_ascii=False))
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
        self.dist_css = ""


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


def read_dist_css():
    dist = WEB / "dist"
    if not dist.is_dir():
        return ""
    return "\n".join(_read(p) for p in sorted(dist.rglob("*.css")))


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
            pipe.dist_css = read_dist_css()
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
                name = f"probe-{uid}-{key}.test.tsx"
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
    """探针 key 在候选上全部通过：退出码 0、输出里有探针文件名、通过数等于用例数、没有失败跳过待办。"""
    assert pipe.ran, pipe.reason
    assert key not in pipe.probe_skipped, pipe.probe_skipped[key]
    step = assert_step_ok(pipe, f"probe:{key}")
    name = pipe.probe_files.get(key)
    assert name and name in step.out.replace("\\", "/"), \
        f"探针输出里没有探针文件名，可能没被 Vitest 选中：\n{step.tail}"
    want = probe_count(PROBE_SPECS[key][0])
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m and int(m.group(1)) == want, f"探针 {key} 应有 {want} 条通过：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), f"探针 {key} 有失败或跳过：\n{step.tail}"


# ---------------------------------------------------------------------------
# S 系列：静态断言
# ---------------------------------------------------------------------------

def test_d01_components_files_and_exports():
    """S1 / D01–D08：12 个新组件的 .tsx 与 .css 都在；components/index.ts 导出 12 个新组件与它们的 Props 类型、
    原来的 11 个组件与 Props 类型，且不出现 overlay。"""
    need_components(*NEW_COMPONENTS)
    fail_if(index_problems(_read(need_file(f"{COMP_REL}/index.ts"))), "components/index.ts 的导出")


def test_d09_base_reset_specificity():
    """S2 / D09（合同 7.4）：base.css 里主体是 button、input、select、textarea、a、table 且不含 :focus-visible 的选择器，
    特异性都低于 (0,1,0)（按顶层逗号切选择器列表；:where() 记 0）；仍有一条同时声明 font: inherit、color: inherit、margin: 0
    并覆盖四种元素的规则，其余重置（cursor、a 的色、table 的合并边框、占位符色）还在；焦点规则与减少动效里的 .tt-skel 不动；
    Button.css 的 .tt-btn--primary（color）、.tt-btn--sm/md/lg（font）、IconButton.css 的 .tt-icon-btn（color）、
    Toast.css 的 .tt-toast__close（color）这些单类规则的特异性高于 base.css 里声明同一属性的元素重置。"""
    base = _read(need_file(f"{SRC_REL}/styles/base.css"))
    comps = {name: _read(need_file(f"{COMP_REL}/{name}")) for name in ("Button.css", "IconButton.css", "Toast.css")}
    fail_if(base_reset_problems(base) + cross_check_problems(base, comps), "base.css 的元素重置")


def test_d09_icon_button_and_toast_sixteen_px():
    """S3 / D09（合同 7.3）：IconButton.css 里 svg 16px 那一行带同一行的出处注释（组件板 :340）；Toast.css 里没有给 svg 定宽高的规则。"""
    icon_button = _read(need_file(f"{COMP_REL}/IconButton.css"))
    toast = _read(need_file(f"{COMP_REL}/Toast.css"))
    fail_if(sixteen_px_problems(icon_button, toast), "两处 16px")


def test_d04_d06_new_icons_match_canvas():
    """S4 / D04、D06（合同第 5 步）：icons/index.tsx 导出 ChevronDownIcon（组件板 :360）、ChevronRightIcon（:449）、CheckIcon（:378）、
    ListChecksIcon（:466 的五条路径），path d 列表与组件板对应的 svg 逐条相等。"""
    fail_if(icon_problems(_read(need_file(f"{SRC_REL}/icons/index.tsx"))), "新增图标")


def test_d01_segmented_control_css_values():
    """S5 / D01（合同第 3 条）：SegmentedControl.css 的轨道、段、选中段取值（底、边框、圆角、内边距、段高 28、字体、阴影）。"""
    fail_if(spec_problems(comp_css("SegmentedControl"), "SegmentedControl.css", SEGMENTED_SPECS), "SegmentedControl.css")


def test_d02_switch_checkbox_css_values():
    """S5 / D02（合同第 4、5 条）：Switch.css 轨道 32×18、圆点 12、上 2、左 2/16、开关与禁用的底和边框；
    Checkbox.css 框 16、圆角 sm、未选与已选、勾 12（描边 3）、文字与间距。"""
    problems = spec_problems(comp_css("Switch"), "Switch.css", SWITCH_SPECS)
    checkbox_css = comp_css("Checkbox")
    problems += spec_problems(checkbox_css, "Checkbox.css", CHECKBOX_SPECS)
    problems += checkbox_icon_problems(comp_tsx("Checkbox"), checkbox_css)
    fail_if(problems, "Switch.css / Checkbox.css")


def test_d03_tabs_css_values():
    """S5 / D03（合同第 6 条）：Tabs.css 列表下边框 1px、页签间距、页签高 38、字体与色、当前页签 2px --tt-primary 下划线与
    margin-bottom: -1px、悬停底与上两角圆角。"""
    fail_if(spec_problems(comp_css("Tabs"), "Tabs.css", TABS_SPECS), "Tabs.css")


def test_d04_field_css_values():
    """S5 / D04（合同第 1、2 条）：输入框与下拉的样式（TextField.css 与 Select.css 合起来看）：高 32、边框、圆角、底、字体、
    左右内边距、出错边框与文字、帮助文字、标签、禁用态；Select.css 的 appearance: none、右内边距 --tt-space-8、箭头
    pointer-events: none 与色、右边距；箭头用 ChevronDownIcon 16。"""
    need_components("TextField", "Select")
    text_css, select_css = comp_css("TextField"), comp_css("Select")
    problems = spec_problems(text_css + "\n" + select_css, "TextField.css + Select.css", FIELD_SPECS)
    problems += spec_problems(select_css, "Select.css", SELECT_ONLY_SPECS)
    problems += select_icon_problems(comp_tsx("Select"), select_css)
    fail_if(problems, "输入框与下拉的样式")


def test_d05_table_css_values():
    """S5 / D05（合同第 7 条）：Table.css 容器 overflow: auto、底、边框、圆角；表头高 32、position: sticky、top: 0、
    z-index: var(--tt-z-sticky)、底与字体；单元格不换行；行高 40/44/52（44、52 由选择器里的 44、52 区分）；行上边框；
    悬停；选中行底与左侧 2px 主色 inset 阴影；数字列右对齐；mono 列字体。"""
    fail_if(spec_problems(comp_css("Table"), "Table.css", TABLE_SPECS), "Table.css")


def test_d06_data_atom_css_values():
    """S5 / D06（合同第 8、9、12 条）：KeyValueList.css（两列网格 minmax(96px, max-content)/minmax(0, 1fr)、行距列距、字体色）、
    EmptyState.css（居中、间距、内边距、边框圆角、图标 32、标题说明字体色）、Breadcrumb.css（字体色、间距、链接色不加下划线、
    当前项色；分隔图标 ChevronRightIcon 14）。"""
    need_components("KeyValueList", "EmptyState", "Breadcrumb")
    problems = spec_problems(comp_css("KeyValueList"), "KeyValueList.css", KEYVALUE_SPECS)
    problems += spec_problems(comp_css("EmptyState"), "EmptyState.css", EMPTY_SPECS)
    problems += spec_problems(comp_css("Breadcrumb"), "Breadcrumb.css", BREADCRUMB_SPECS)
    problems += breadcrumb_icon_problems(comp_tsx("Breadcrumb"), comp_css("Breadcrumb"))
    empty = strip_ts_comments(comp_tsx("EmptyState"))
    if "ListChecksIcon" not in empty:
        problems.append("EmptyState.tsx 的缺省图标应是 ListChecksIcon")
    fail_if(problems, "键值列表、空状态、面包屑")


def test_d07_skeleton_css_and_source():
    """S5 / D07（合同第 10 条）：Skeleton.css 容器与条的取值（间距、内边距、边框、圆角、条底）；条高 14/20/20/20、宽 40%/100%/82%/64%
    （写在 css 或 tsx 里都行）；不写动画、过渡、渐变、@keyframes；tsx 用 tt-skel、setTimeout 与 clearTimeout、具名常量 300，
    不用 requestAnimationFrame 与 performance；base.css 的减少动效规则含 .tt-skel。"""
    need_components("Skeleton")
    problems = skeleton_problems(comp_tsx("Skeleton"), comp_css("Skeleton"))
    base = _read(need_file(f"{SRC_REL}/styles/base.css"))
    if not re.search(r"@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{[^{}]*\.tt-skel\b[^{}]*\{[^}]*animation\s*:\s*none",
                     strip_comments(base)):
        problems.append("base.css 的减少动效规则里没有 .tt-skel")
    fail_if(problems, "骨架屏")


def test_d08_connection_pill_css_values():
    """S5 / D08（合同第 11 条）：ConnectionPill.css 胶囊高 24、圆点 8、悬停；浮层绝对定位、右对齐、在胶囊下方、宽 240、内边距、
    边框、圆角、阴影 --tt-shadow-2、层级 --tt-z-popover、标签列 64、pid 等宽；三态的色调（已连接 --tt-tone-success-fg，
    重连中 --tt-tone-warning-fg，已断开 --tt-tone-danger-fg 与 --tt-danger-text）；tsx 里浮层带 tt-enter、pid 带 tt-num。"""
    need_components("ConnectionPill")
    css = comp_css("ConnectionPill")
    problems = spec_problems(css, "ConnectionPill.css", PILL_SPECS) + pill_tone_problems(css)
    code = strip_ts_comments(comp_tsx("ConnectionPill"))
    for cls in ("tt-enter", "tt-num"):
        if cls not in code:
            problems.append(f"ConnectionPill.tsx 里没有用 {cls}（浮层入场、pid 等宽数字）")
    fail_if(problems, "ConnectionPill")


def token_only_problems(label, css):
    """合同公共约定：颜色、字体、圆角、阴影、层级只用 --tt-* 令牌（颜色由 W4 另查）。"""
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


def test_d12_new_css_tokens_and_source_comments():
    """D12 守卫（合同公共约定）：12 份新 CSS 里层级、圆角、阴影、字体只用 --tt-* 令牌；除 0 与 1px 外的 px 字面量，
    同一行带出处注释。"""
    need_components(*NEW_COMPONENTS)
    problems = []
    for name in NEW_COMPONENTS:
        raw = _read(comp_path(name, "css"))
        problems += token_only_problems(f"{name}.css", raw)
        problems += px_literal_problems(f"{name}.css", raw)
    fail_if(problems, "新组件 CSS 的令牌与出处注释")


def test_d12_new_sources_forbidden_things():
    """D12 守卫（合同公共约定与禁止的做法）：12 个新组件、field/*.tsx、showcase/*.tsx 里不渲染 role=status，
    不调用 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver。"""
    need_components(*NEW_COMPONENTS)
    problems = []
    for path in new_source_files():
        problems += source_rule_problems(path.relative_to(WEB).as_posix(), _read(path))
    fail_if(problems, "新组件与新演示的源码")


def test_d09_executor_tests_in_place():
    """D09（合同 7.1、7.4）：执行端的 tests/dialog-scrim.test.tsx 至少两条用例（内容上 mousedown 不被阻止、遮罩上被阻止），
    tests/toast-close-tooltip.test.tsx 在，tests/base-reset.test.ts 在且带 :where 的特异性样本。"""
    problems = []
    scrim = WEB / "tests" / "dialog-scrim.test.tsx"
    if not scrim.is_file():
        problems.append(f"{WEB_REL}/tests/dialog-scrim.test.tsx 不存在")
    elif len(re.findall(r"^\s*(?:it|test)\(", _read(scrim), re.M)) < 2:
        problems.append("dialog-scrim.test.tsx 应至少两条用例")
    if not (WEB / "tests" / "toast-close-tooltip.test.tsx").is_file():
        problems.append(f"{WEB_REL}/tests/toast-close-tooltip.test.tsx 不存在")
    reset = WEB / "tests" / "base-reset.test.ts"
    if not reset.is_file():
        problems.append(f"{WEB_REL}/tests/base-reset.test.ts 不存在")
    elif ":where(" not in _read(reset):
        problems.append("base-reset.test.ts 里没有 :where() 的特异性样本")
    fail_if(problems, "执行端的新测试")


# ---------------------------------------------------------------------------
# P 系列：流水线断言
# ---------------------------------------------------------------------------

def test_d11_pipeline_steps_pass(pipeline):
    """P1 / D11（守卫）：npm ci、npm run build、npm test、npm run check:contract 都退出 0；npm test 有通过的用例，没有失败、跳过、待办。"""
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    step = pipeline.steps["npm test"]
    out = step.out
    assert re.search(r"Tests\s+(?:.*\|\s*)?\d+ passed", out), f"npm test 输出里没有 'Tests … N passed'：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", out), f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert re.search(r"Test Files\s+\d+ passed", out) and not re.search(r"Test Files\s+.*\bfailed\b", out), \
        f"npm test 的 Test Files 行异常：\n{step.tail}"


def test_d09_dist_css_keeps_where(pipeline):
    """P1 / D09（合同 7.4）：构建产物 dist 的 CSS 仍含 :where(（构建不改写选择器），且 .tt-app 的元素重置在其中。"""
    assert_step_ok(pipeline, "npm run build")
    css = pipeline.dist_css
    assert css, "构建后 dist 里没有 CSS"
    assert ":where(" in css, "dist 的 CSS 里没有 :where(，元素重置被构建改写或丢了"
    assert re.search(r":where\(\s*\.tt-app\s*\)", css), "dist 的 CSS 里找不到 :where(.tt-app) 的元素重置"


def test_d09_probe_dialog_scrim(pipeline):
    """P2 / D09：探针渲染 Dialog：框内输入框、正文、标题、对话框根、正文容器、底栏按钮上的 mousedown 返回 true（不被阻止），
    输入框能聚焦；遮罩本身上返回 false，点遮罩不关闭。"""
    need_components("Dialog", css=False)
    assert_probe_ok(pipeline, "p2")


def test_d09_probe_toast_close_tooltip(pipeline):
    """P3 / D09：探针渲染 Toast：关闭钮悬停 399ms 没有、400ms 有「关闭提示」的 role=tooltip，aria-describedby 指向它，移开消失；
    聚焦同；关闭钮名称不变、点一下调一次 onClose；5000ms 自动关闭照旧（4999 没调、5000 调一次）。"""
    need_components("Toast", "Tooltip", css=False)
    assert_probe_ok(pipeline, "p3")


def test_d01_probe_segmented_control(pipeline):
    """P4 / D01：radiogroup、radio（button type=button）、aria-checked、恰一个 tabIndex=0；ArrowRight、ArrowLeft 选中下一段、
    上一段并移焦点（keydown 被 preventDefault）、onChange 收到新值；到头循环；只处理左右；点击选中。"""
    need_components("SegmentedControl")
    assert_probe_ok(pipeline, "p4")


def test_d02_probe_switch_checkbox(pipeline):
    """P5 / D02：开关 role=switch、复选框 role=checkbox（都是 span）；aria-checked；名称来自可见文字；可用时 tabIndex=0；
    空格切换一次（keydown 被 preventDefault）、repeat 不切换；点击整个控件切换；禁用时 aria-disabled=true、不可聚焦、不切换；
    复选框不认 Enter。"""
    need_components("Switch", "Checkbox")
    assert_probe_ok(pipeline, "p5")


def test_d03_probe_tabs(pipeline):
    """P6 / D03：tablist、tab（button type=button）、aria-selected、恰一个 tabIndex=0；左右方向键循环切换并移焦点；Home、End 到首尾；
    点击选中；tabpanel 的 aria-labelledby 指向当前页签、当前页签的 aria-controls 指向面板。"""
    need_components("Tabs")
    assert_probe_ok(pipeline, "p6")


def test_d04_probe_text_field_select(pipeline):
    """P7 / D04：输入框与下拉的标签关联（htmlFor）、aria-describedby 依次放出错、帮助的 id（只放渲染了的）、出错时 aria-invalid=true、
    禁用、透传；mono 与普通不同；下拉是原生 select、选项与值对得上、箭头图标 aria-hidden 且不在 select 里。"""
    need_components("TextField", "Select")
    assert_probe_ok(pipeline, "p7")


def test_d05_probe_table(pipeline):
    """P8 / D05：滚动容器带 className 并包着 table；th scope=col；data-row-height 缺省 40、可为 44、52；数字列单元格带 tt-num；
    恰一行 tabIndex=0（起点是选中行，没有就第一行）；上下移动不循环、Home、End 到首尾；Enter 调一次 onRowOpen(key)；点击行同；
    表格与容器不进 Tab 序列，单元格里没有可聚焦元素。"""
    need_components("Table")
    assert_probe_ok(pipeline, "p8")


def test_d06_probe_data_atoms(pipeline):
    """P9 / D06：键值列表 dl 里每项一对 dt、dd，mono 值结构不同；空状态缺省图标路径等于组件板 :466、aria-hidden，
    没有 action 时不渲染操作区（不留空元素）；面包屑 nav 的 aria-label 为「面包屑」、前项 a 或 button、末项 span aria-current=page、
    分隔图标 aria-hidden。"""
    need_components("KeyValueList", "EmptyState", "Breadcrumb")
    assert_probe_ok(pipeline, "p9")


def test_d07_probe_skeleton(pipeline):
    """P10 / D07：Skeleton 挂载后 299ms 什么都没有、300ms 出现 4 条 tt-skel（aria-hidden）与 aria-busy 容器；300ms 前卸载清计时器、
    什么都不出现；StrictMode 下计时幂等；每次挂载重新计时。"""
    need_components("Skeleton")
    assert_probe_ok(pipeline, "p10")


def test_d08_probe_connection_pill(pipeline):
    """P11 / D08：三态的文字与 data-state；button type=button、aria-expanded、aria-controls；点击开合浮层，浮层紧跟胶囊，
    里面是 pid、启动于、事件流三行小键值表，没给的值显示「未知」，没有可聚焦元素；Esc 关闭、焦点留在胶囊、不往外传；
    点外面关闭。"""
    need_components("ConnectionPill")
    assert_probe_ok(pipeline, "p11")


def test_d12_worktree_unchanged_by_pipeline(pipeline):
    """P13 / D12（守卫）：流水线与探针前后 git status 相同；package.json、锁文件、index.html、vite.config.ts、tsconfig.json、
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

SPECIFICITY_SAMPLES = {
    # 规划 §2.2 / 合同 7.4 的自检样本
    ".tt-app button": (0, 1, 1),
    ":where(.tt-app) :where(button, input, select, textarea)": (0, 0, 0),
    ":where(.tt-app) :where(input)::placeholder": (0, 0, 1),
    ".tt-icon-btn:hover:not(:disabled)": (0, 3, 0),
    ".tt-app :focus-visible": (0, 2, 0),
    ".tt-status[data-tone=neutral]": (0, 2, 0),
    "#x .a > b + c ~ d": (1, 1, 3),
    # 门禁端补的样本
    ":is(.a, #b) c": (1, 0, 1),
    ":not(.a, .b)": (0, 1, 0),
    "a:not(:where(.x))": (0, 0, 1),
    ":has(> img)": (0, 0, 1),
    "*": (0, 0, 0),
    ".tt-app input::placeholder": (0, 1, 2),
    ":where(.tt-app) :where(button:disabled)": (0, 0, 0),
    ".a:nth-child(2n+1)": (0, 2, 0),
    "ul li:first-child": (0, 1, 2),
    "button:disabled": (0, 1, 1),
    "a::before": (0, 0, 2),
    'input[type="text"]': (0, 1, 1),
    '.x[data-a="b,c"]': (0, 2, 0),
    ".tt-app button:disabled": (0, 2, 1),
}


def test_gate_selfcheck_specificity_calculator():
    """门禁自检：特异性计算器对规划 §2.2 的样本（.tt-app button 为 (0,1,1)、:where(.tt-app) :where(button, input, select,
    textarea) 为 (0,0,0)、:where(.tt-app) :where(input)::placeholder 为 (0,0,1)、.tt-icon-btn:hover:not(:disabled) 为 (0,3,0)）
    和门禁端补的样本都对；选择器列表按顶层逗号切，:where(button, input) 里的逗号与引号里的逗号不切。"""
    for selector, want in SPECIFICITY_SAMPLES.items():
        assert specificity(selector) == want, (selector, specificity(selector), want)
    assert split_top(":where(button, input), .a, [data-x='a,b']") == [":where(button, input)", ".a", "[data-x='a,b']"]
    assert split_top("a, b") == ["a", "b"]
    rules = parse_rules(":where(.tt-app) :where(button, input) { margin: 0; }\n.a, .b { color: red; }")
    assert [sel for sel, _d in rules] == [":where(.tt-app) :where(button, input)", ".a, .b"]
    assert subject_elements(":where(.tt-app) :where(button, input, select, textarea)") == {"button", "input", "select", "textarea"}
    assert subject_elements(".tt-app a") == {"a"}
    assert subject_elements(".tt-app :focus-visible") == set()
    assert subject_elements(".tt-h-primary:hover:not(:disabled)") == set()
    assert subject_elements(".tt-btn") == set()
    assert subject_elements('.x[data-kind="button"]') == set()
    assert subject_elements(":where(.tt-app) :where(input)::placeholder") == {"input"}
    assert subject_elements(".tt-app button:disabled") == {"button"}


GOOD_BASE = """
.tt-app { font: var(--tt-text-md); color: var(--tt-text-1); }
/* 元素重置包在 :where() 里，特异性为 0 */
:where(.tt-app) :where(button, input, select, textarea) { font: inherit; color: inherit; margin: 0; }
:where(.tt-app) :where(button) { cursor: pointer; }
:where(.tt-app) :where(button:disabled) { cursor: not-allowed; }
:where(.tt-app) :where(a) { color: var(--tt-link); }
:where(.tt-app) :where(table) { border-collapse: collapse; border-spacing: 0; }
:where(.tt-app) :where(input)::placeholder { color: var(--tt-text-3); }
.tt-num { font-variant-numeric: tabular-nums; }
.tt-app :focus-visible { outline: 2px solid var(--tt-focus); outline-offset: 2px; }
.tt-app input:focus-visible, .tt-app select:focus-visible, .tt-app textarea:focus-visible { border-color: var(--tt-focus) !important; outline-offset: 1px; }
.tt-h-primary:hover:not(:disabled) { background: var(--tt-primary-hover) !important; }
@keyframes tt-pulse { 0%, 100% { opacity: 1; } 50% { opacity: .45; } }
.tt-skel { animation: tt-pulse 1.6s var(--tt-ease-standard) infinite; }
@media (prefers-reduced-motion: reduce) {
  .tt-spin, .tt-skel { animation: none; }
}
@media (forced-colors: active) {
  .tt-app :focus-visible { outline-color: Highlight; }
}
"""

BASE_BROKEN = {
    "元素重置回到 (0,1,1)": (":where(.tt-app) :where(button, input, select, textarea) {",
                           ".tt-app button, .tt-app input, .tt-app select, .tt-app textarea {"),
    "只包了后半，仍是 (0,1,0)": (":where(.tt-app) :where(button, input, select, textarea) {",
                             ".tt-app :where(button, input, select, textarea) {"),
    "a 的重置回到 (0,1,1)": (":where(.tt-app) :where(a) {", ".tt-app a {"),
    "table 的重置回到 (0,1,1)": (":where(.tt-app) :where(table) {", ".tt-app table {"),
    "button:disabled 回到 (0,2,1)": (":where(.tt-app) :where(button:disabled) {", ".tt-app button:disabled {"),
    "占位符回到 (0,1,2)": (":where(.tt-app) :where(input)::placeholder {", ".tt-app input::placeholder {"),
    "核心重置少了 color 与 margin": ("font: inherit; color: inherit; margin: 0;", "font: inherit;"),
    "cursor 重置被删": ("cursor: pointer;", ""),
    "焦点环被改": ("outline: 2px solid var(--tt-focus); outline-offset: 2px;", "outline: 1px solid var(--tt-focus); outline-offset: 2px;"),
    "输入控件焦点规则被改": ("border-color: var(--tt-focus) !important; outline-offset: 1px;", "outline-offset: 1px;"),
    "减少动效里没有 .tt-skel": (".tt-spin, .tt-skel { animation: none; }", ".tt-spin { animation: none; }"),
}

BASE_OLD = """
.tt-app button, .tt-app input, .tt-app select, .tt-app textarea { font: inherit; color: inherit; margin: 0; }
.tt-app button { cursor: pointer; }
.tt-app button:disabled { cursor: not-allowed; }
.tt-app a { color: var(--tt-link); }
.tt-app table { border-collapse: collapse; border-spacing: 0; }
.tt-app input::placeholder { color: var(--tt-text-3); }
.tt-app :focus-visible { outline: 2px solid var(--tt-focus); outline-offset: 2px; }
.tt-app input:focus-visible, .tt-app select:focus-visible, .tt-app textarea:focus-visible { border-color: var(--tt-focus) !important; outline-offset: 1px; }
@media (prefers-reduced-motion: reduce) { .tt-spin, .tt-skel { animation: none; } }
"""

GOOD_COMPS = {
    "Button.css": ".tt-btn--primary { background: var(--tt-primary); color: var(--tt-on-primary); }\n"
                  ".tt-btn--sm { height: 28px; font: var(--tt-text-sm-medium); }\n"
                  ".tt-btn--md { height: 32px; font: var(--tt-text-md-medium); }\n"
                  ".tt-btn--lg { height: 36px; font: var(--tt-text-md-medium); }\n",
    "IconButton.css": ".tt-icon-btn { color: var(--tt-text-2); }\n.tt-icon-btn svg { width: 16px; height: 16px; } /* 组件板 :340，图标 16 */\n",
    "Toast.css": ".tt-toast__close { color: var(--tt-text-2); }\n",
}


def test_gate_selfcheck_base_reset_checker():
    """门禁自检：合同 7.4 建议的 base.css 写法通过 S2 的检查；旧写法（.tt-app button…）被抓住；逐项改坏都被抓住；
    与组件单类规则的交叉核对：新写法放过、旧写法抓住。"""
    assert base_reset_problems(GOOD_BASE) == []
    assert cross_check_problems(GOOD_BASE, GOOD_COMPS) == []
    old = base_reset_problems(BASE_OLD)
    assert len(old) >= 6, old
    assert cross_check_problems(BASE_OLD, GOOD_COMPS), "旧写法 (0,1,1) 压住了 .tt-btn--primary 的 color，交叉核对应报"
    for name, (old_text, new_text) in BASE_BROKEN.items():
        assert old_text in GOOD_BASE, f"自检样本没有改坏的位置：{name}"
        assert base_reset_problems(GOOD_BASE.replace(old_text, new_text, 1)), f"没抓住：{name}"
    assert base_reset_problems("")
    # 交叉核对的清单与仓库里这几份 CSS 对得上（基线上 Button.css 等的单类规则就在）
    real = {name: _read(need_file(f"{COMP_REL}/{name}")) for name in ("Button.css", "IconButton.css", "Toast.css")}
    assert cross_check_problems(GOOD_BASE, real) == [], cross_check_problems(GOOD_BASE, real)


def test_gate_selfcheck_css_helpers():
    """门禁自检：has_decl 的 eq/has/sel/zero/custom 各路；px 字面量出处注释的检查；令牌守卫；ConnectionPill 色调检查的样本。"""
    css = (".a { height: 32px; } .b:hover { background: var(--tt-surface-3); } "
           '.c[data-row-height="44"] td { height: 44px; } .d { top: 0px; --row-h: 40px; }')
    assert has_decl(css, ("height",), eq="32px")
    assert not has_decl(css, ("height",), eq="33px")
    assert has_decl(css, BG, eq="var(--tt-surface-3)", sel="hover")
    assert not has_decl(css, BG, eq="var(--tt-surface-3)", sel="focus")
    assert has_decl(css, ("height",), eq="44px", sel=r"(?<!\d)44(?!\d)")
    assert not has_decl(css, ("height",), eq="44px", sel=r"(?<!\d)52(?!\d)")
    assert has_decl(css, ("top",), zero=True)
    assert has_decl(css, ("height",), eq="40px", custom=True) and not has_decl(css, ("height",), eq="40px")
    assert has_decl(".x { border: 1px solid var(--tt-border) }", ("border",), has=("1px", "var(--tt-border)"))
    assert not has_decl(".x { border: 1px solid var(--tt-border-strong) }", ("border",), has=("var(--tt-border)",))
    assert has_decl(".x { height: calc( 100% - 4px ) }", ("height",), eq="calc(100%-4px)")

    assert px_literal_problems("x", ".a { height: 32px; } /* 组件板 :357 */") == []
    assert px_literal_problems("x", ".a {\n  height: 32px; /* 出处 */\n  margin: 1px; width: 0px;\n}") == []
    assert px_literal_problems("x", ".a {\n  height: 32px;\n}")
    assert px_literal_problems("x", "/* 头注释 32px 说明\n   续行 12px */\n.a { margin: 0 var(--tt-space-1); }") == []
    assert px_literal_problems("x", ".a { grid-template-columns: minmax(96px, max-content) 1fr; }")
    assert px_literal_problems("x", ".a { margin-bottom: -1px; }") == []
    assert px_literal_problems("x", ".a { margin-bottom: -2px; }")

    assert token_only_problems("x", ".a { z-index: var(--tt-z-sticky); border-radius: var(--tt-radius-md) var(--tt-radius-md) 0 0; "
                                    "box-shadow: inset 2px 0 0 var(--tt-primary); font: var(--tt-text-sm); }") == []
    assert token_only_problems("x", ".a { z-index: 5; }")
    assert token_only_problems("x", ".a { border-radius: 4px; }")
    assert token_only_problems("x", ".a { box-shadow: 0 1px 2px black; }")
    assert token_only_problems("x", ".a { font: 14px sans-serif; }")
    assert token_only_problems("x", ".a { font: inherit; border-radius: 0; box-shadow: none; }") == []

    assert source_rule_problems("x", '<div role="status">') and source_rule_problems("x", "window.matchMedia('x')")
    assert source_rule_problems("x", "el.scrollIntoView(); new ResizeObserver(f)")
    assert source_rule_problems("x", "// matchMedia 只在注释里\nconst a = 1;") == []
    assert source_rule_problems("x", '<div role="alert">') == []


GOOD_TABLE_CSS = """
.tt-table-wrap { overflow: auto; background: var(--tt-surface-1); border: 1px solid var(--tt-border); border-radius: var(--tt-radius-lg); }
.tt-table th { position: sticky; top: 0; z-index: var(--tt-z-sticky); height: 32px; padding: 0 var(--tt-space-3); background: var(--tt-surface-2); font: var(--tt-title-sm); color: var(--tt-text-2); white-space: nowrap; }
.tt-table td { white-space: nowrap; padding: 0 var(--tt-space-3); border-top: 1px solid var(--tt-border); font: var(--tt-text-sm); }
.tt-table[data-row-height="40"] td { height: 40px; }
.tt-table[data-row-height="44"] td { height: 44px; }
.tt-table[data-row-height="52"] td { height: 52px; }
.tt-table tbody tr:hover { background: var(--tt-surface-3); }
.tt-table tbody tr[data-selected] { background: var(--tt-surface-selected); box-shadow: inset 2px 0 0 var(--tt-primary); }
.tt-table td.tt-num { text-align: right; }
.tt-table td.tt-table__mono { font: var(--tt-mono-sm); }
"""

TABLE_BROKEN = {
    "表头不是 sticky": ("position: sticky", "position: relative"),
    "表头 top 不是 0": ("top: 0;", "top: 4px;"),
    "层级不是令牌": ("z-index: var(--tt-z-sticky)", "z-index: 10"),
    "表头高改了": ("height: 32px", "height: 36px"),
    "44 档没有": ('.tt-table[data-row-height="44"] td { height: 44px; }', ""),
    "52 档没有": ('.tt-table[data-row-height="52"] td { height: 52px; }', ""),
    "40 档没有": ("height: 40px", "height: 41px"),
    "单元格可换行": ("white-space: nowrap;", ""),
    "数字列不右对齐": ("text-align: right", "text-align: left"),
    "选中行条改 3px": ("inset 2px 0 0", "inset 3px 0 0"),
    "容器不是 auto": ("overflow: auto", "overflow: hidden"),
    "悬停底改了": ("background: var(--tt-surface-3)", "background: var(--tt-surface-2)"),
    "mono 列字体改了": ("var(--tt-mono-sm)", "var(--tt-text-sm)"),
}

GOOD_PILL_CSS = """
.tt-pill { display: inline-flex; align-items: center; gap: var(--tt-space-1); height: 24px; padding: 0 var(--tt-space-2); border: 1px solid var(--tt-border); border-radius: var(--tt-radius-full); background: var(--tt-surface-1); font: var(--tt-text-caption); color: var(--tt-text-2); }
.tt-pill:hover { background: var(--tt-surface-3); }
.tt-pill__dot { width: 8px; height: 8px; border-radius: var(--tt-radius-full); background: var(--tt-tone-success-fg); }
.tt-pill[data-state="reconnecting"] { color: var(--tt-tone-warning-fg); }
.tt-pill[data-state="reconnecting"] .tt-pill__dot { background: var(--tt-tone-warning-fg); }
.tt-pill[data-state="disconnected"] { color: var(--tt-danger-text); }
.tt-pill[data-state="disconnected"] .tt-pill__dot { background: var(--tt-tone-danger-fg); }
.tt-pill-pop { position: absolute; top: calc(100% + var(--tt-space-1)); right: 0; width: 240px; padding: var(--tt-space-2) var(--tt-space-3); background: var(--tt-surface-1); border: 1px solid var(--tt-border); border-radius: var(--tt-radius-lg); box-shadow: var(--tt-shadow-2); z-index: var(--tt-z-popover); font: var(--tt-text-sm); }
.tt-pill-pop dl { display: grid; grid-template-columns: 64px minmax(0, 1fr); }
.tt-pill-pop__pid { font: var(--tt-mono-sm); }
"""

PILL_BROKEN = {
    "高改了": ("height: 24px", "height: 28px"),
    "圆点改了": ("width: 8px; height: 8px", "width: 10px; height: 10px"),
    "浮层宽改了": ("width: 240px", "width: 200px"),
    "浮层层级改了": ("z-index: var(--tt-z-popover)", "z-index: var(--tt-z-dialog)"),
    "浮层不右对齐": ("right: 0;", "left: 0;"),
    "浮层不在下方": ("top: calc(100% + var(--tt-space-1))", "bottom: 100%"),
    "阴影改了": ("var(--tt-shadow-2)", "var(--tt-shadow-1)"),
    "标签列改了": ("grid-template-columns: 64px", "grid-template-columns: 80px"),
    "已断开圆点色调改了": ("var(--tt-tone-danger-fg)", "var(--tt-tone-warning-fg)"),
    "已断开文字色调改了": ("var(--tt-danger-text)", "var(--tt-text-2)"),
    "重连中色调改了": ("var(--tt-tone-warning-fg)", "var(--tt-text-2)"),
    "已连接色调改了": ("var(--tt-tone-success-fg)", "var(--tt-text-2)"),
}


def test_gate_selfcheck_table_and_pill_css_checks():
    """门禁自检：按合同写出的 Table.css、ConnectionPill.css 样本通过 S5 的检查；逐项改坏都被抓住；空文件被抓住。"""
    assert spec_problems(GOOD_TABLE_CSS, "t", TABLE_SPECS) == [], spec_problems(GOOD_TABLE_CSS, "t", TABLE_SPECS)
    assert spec_problems(GOOD_PILL_CSS, "p", PILL_SPECS) == [] and pill_tone_problems(GOOD_PILL_CSS) == [], \
        spec_problems(GOOD_PILL_CSS, "p", PILL_SPECS) + pill_tone_problems(GOOD_PILL_CSS)
    for name, (old, new) in TABLE_BROKEN.items():
        assert old in GOOD_TABLE_CSS, f"自检样本没有改坏的位置：{name}"
        assert spec_problems(GOOD_TABLE_CSS.replace(old, new), "t", TABLE_SPECS), f"没抓住（Table）：{name}"
    for name, (old, new) in PILL_BROKEN.items():
        assert old in GOOD_PILL_CSS, f"自检样本没有改坏的位置：{name}"
        broken = GOOD_PILL_CSS.replace(old, new)
        assert spec_problems(broken, "p", PILL_SPECS) + pill_tone_problems(broken), f"没抓住（ConnectionPill）：{name}"
    for specs in (FIELD_SPECS, SELECT_ONLY_SPECS, SEGMENTED_SPECS, SWITCH_SPECS, CHECKBOX_SPECS, TABS_SPECS, TABLE_SPECS,
                  KEYVALUE_SPECS, EMPTY_SPECS, SKELETON_SPECS, PILL_SPECS, BREADCRUMB_SPECS):
        assert spec_problems("", "empty", specs), "空文件应该报问题"
        for desc, names, kwargs in specs:
            assert names and set(kwargs) <= {"eq", "has", "sel", "zero", "custom"}, desc


GOOD_SKELETON_TSX = """
import { useEffect, useState } from 'react';
import './Skeleton.css';
// 挂载后 300ms 才出现（组件板 :474）
const SHOW_DELAY = 300;
const BARS = [{ h: 14, w: '40%' }, { h: 20, w: '100%' }, { h: 20, w: '82%' }, { h: 20, w: '64%' }];
export function Skeleton() {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setShown(true), SHOW_DELAY);
    return () => clearTimeout(t);
  }, []);
  if (!shown) return null;
  return (
    <div className="tt-skeleton" aria-busy="true">
      {BARS.map((b) => <div key={b.w} className="tt-skel" aria-hidden="true" style={{ height: b.h, width: b.w }} />)}
    </div>
  );
}
"""
GOOD_SKELETON_CSS = """
.tt-skeleton { display: flex; flex-direction: column; gap: var(--tt-space-2); padding: var(--tt-space-4); border: 1px solid var(--tt-border); border-radius: var(--tt-radius-lg); }
.tt-skeleton .tt-skel { background: var(--tt-surface-3); border-radius: var(--tt-radius-sm); }
"""


def test_gate_selfcheck_skeleton_source_checks():
    """门禁自检：合同写明的骨架屏源码样本通过检查；动画、过渡、渐变、rAF、performance、没有具名常量 300、不清计时器、
    条宽条高不对都被抓住。"""
    assert skeleton_problems(GOOD_SKELETON_TSX, GOOD_SKELETON_CSS) == []
    broken_css = {
        "写了动画": GOOD_SKELETON_CSS + ".tt-skel { animation: x 1s; }",
        "写了过渡": GOOD_SKELETON_CSS + ".tt-skel { transition: opacity 1s; }",
        "写了渐变": GOOD_SKELETON_CSS.replace("background: var(--tt-surface-3)", "background: linear-gradient(90deg, var(--tt-surface-3), var(--tt-surface-2))"),
        "条底改了": GOOD_SKELETON_CSS.replace("--tt-surface-3", "--tt-surface-2"),
    }
    for name, css in broken_css.items():
        assert skeleton_problems(GOOD_SKELETON_TSX, css), f"没抓住（css）：{name}"
    broken_tsx = {
        "用 rAF": GOOD_SKELETON_TSX.replace("setTimeout(() => setShown(true), SHOW_DELAY)", "requestAnimationFrame(() => setShown(true))"),
        "用 performance": GOOD_SKELETON_TSX.replace("const SHOW_DELAY = 300;", "const SHOW_DELAY = 300; const now = performance.now();"),
        "300 不是具名常量": GOOD_SKELETON_TSX.replace("const SHOW_DELAY = 300;", "").replace("SHOW_DELAY)", "300)"),
        "不清计时器": GOOD_SKELETON_TSX.replace("clearTimeout(t)", "void t"),
        "条类名不对": GOOD_SKELETON_TSX.replace("tt-skel", "tt-bar"),
        "缺 82%": GOOD_SKELETON_TSX.replace("82%", "80%"),
        "缺 14": GOOD_SKELETON_TSX.replace("h: 14", "h: 16"),
    }
    for name, tsx in broken_tsx.items():
        assert skeleton_problems(tsx, GOOD_SKELETON_CSS), f"没抓住（tsx）：{name}"
    assert skeleton_problems("", "")


def test_gate_selfcheck_index_and_icon_parsers():
    """门禁自检：components/index.ts 的导出解析认得 export {…}、export type {…}、as 改名；图标块解析认得 path d；
    合同第 5 步的 4 个图标路径与组件板对应行（:360、:449、:378、:466）逐条相等；仓库里没动的 HourglassIcon 解析得出来。"""
    names = NEW_COMPONENTS + OLD_COMPONENTS
    good = "\n".join([f"export {{ {c} }} from './{c}';\nexport type {{ {c}Props }} from './{c}';" for c in names])
    assert index_problems(good) == []
    assert index_problems(good.replace("export { Toast } from './Toast';", "// export { Toast } from './Toast';"))
    assert index_problems(good.replace("export type { TableProps } from './Table';", ""))
    assert index_problems(good + "\nexport * from './overlay/focus';")
    assert index_problems(good.replace("export { Select }", "export { Select as Dropdown }"))
    star = "\n".join([f"export * from './{c}';" for c in names])
    assert index_problems(star) == []
    assert len(NEW_COMPONENTS) == 12 and len(OLD_COMPONENTS) == 11 and len(set(names)) == 23

    for name, lineno, literal in ICON_SPECS:
        assert canvas_line_icon_ds(lineno) == literal, (name, lineno, canvas_line_icon_ds(lineno))
    icons = _read(need_file(f"{SRC_REL}/icons/index.tsx"))
    assert len(icon_component_ds(icons, "HourglassIcon")) == 4
    assert icon_component_ds(icons, "NoSuchIcon") is None
    sample = ('export const ChevronDownIcon = (p: P) => (\n  <Svg {...p}>\n    <path d="m6 9 6 6 6-6" />\n  </Svg>\n);\n\n'
              'export const Next = () => <path d="zzz" />;\n')
    assert icon_component_ds(sample, "ChevronDownIcon") == ["m6 9 6 6 6-6"]
    good_icons = "\n".join(
        f'export const {name} = (p: P) => (\n  <Svg {{...p}}>\n' + "\n".join(f'    <path d="{d}" />' for d in literal) + "\n  </Svg>\n);\n"
        for name, _line, literal in ICON_SPECS)
    assert icon_problems(good_icons) == []
    assert icon_problems(good_icons.replace("M20 6 9 17l-5-5", "M20 6 9 17l-5-4"))
    assert icon_problems(good_icons.replace("export const CheckIcon", "export const TickIcon"))
    assert icon_problems(good_icons.replace('    <path d="M13 18h8" />\n', ""))


def test_gate_selfcheck_sixteen_px_checker():
    """门禁自检：S3 的检查放得过“保留 svg 16px 并加同一行出处注释、删掉 Toast.css 的 svg 规则”，拦得住没注释、注释没写出处、
    Toast.css 留着 svg 尺寸规则、IconButton.css 把规则删了。"""
    good_icon = ".tt-icon-btn svg { width: 16px; height: 16px; } /* 组件板 :340，图标 16 */\n"
    good_toast = ".tt-toast__close { width: 24px; height: 24px; }\n.tt-toast__close:hover { color: var(--tt-text-1); }\n"
    assert sixteen_px_problems(good_icon, good_toast) == []
    assert sixteen_px_problems(".tt-icon-btn svg { width: 16px; height: 16px; }\n", good_toast)
    assert sixteen_px_problems(".tt-icon-btn svg { width: 16px; height: 16px; } /* 随便写的 */\n", good_toast)
    assert sixteen_px_problems(".tt-icon-btn { color: red; }\n", good_toast)
    assert sixteen_px_problems(good_icon, good_toast + ".tt-toast__close svg { width: 16px; height: 16px; }\n")
    assert sixteen_px_problems(good_icon, good_toast + ".tt-toast__close svg { height: 16px; }\n")
    assert sixteen_px_problems(good_icon, good_toast + ".tt-toast__icon { flex: none; }\n") == []


def test_gate_selfcheck_probe_templates():
    """门禁自检：10 份探针（P2–P11；P12 已退役）的用例数、文件名约定与 vitest 的 include 一致；探针不用 skip、only、todo，
    fireEvent 来自 @testing-library/react（不从 @testing-library/dom 导入）；占位符都能替换掉；括号成对；探针动态导入的模块
    都在各自的“需要先存在的文件”清单里；p2、p3 导入的模块基线上就在。"""
    counts = {key: probe_count(spec[0]) for key, spec in PROBE_SPECS.items()}
    assert counts == {"p2": 3, "p3": 4, "p4": 6, "p5": 13, "p6": 6, "p7": 12, "p8": 11, "p9": 7, "p10": 4, "p11": 7}, counts
    assert set(PROBE_ORDER) == set(PROBE_SPECS) and len(PROBE_ORDER) == len(PROBE_SPECS)
    vite_cfg = _read(need_file(f"{WEB_REL}/vite.config.ts"))
    assert "gate-probe/**/*.test.{ts,tsx}" in vite_cfg
    for key, (source, requires) in PROBE_SPECS.items():
        assert not re.search(r"\b(?:it|test|describe)\.(?:skip|todo|only|skipIf|runIf)\b|\bx(?:it|describe)\(|\.only\(", source), key
        assert "@testing-library/dom" not in source, key
        assert "from '@testing-library/react'" in source, key
        assert "useFakeTimers" in source, key
        built = build_probe_source(key)
        assert not re.search(r"__[A-Z][A-Z_]*__", built), key
        assert built.count("(") == built.count(")"), (key, built.count("("), built.count(")"))
        assert built.count("{") == built.count("}"), (key, built.count("{"), built.count("}"))
        assert built.count("[") == built.count("]"), (key, built.count("["), built.count("]"))
        for mod in re.findall(r"import\('\.\./src/([^']+)'\)", source):
            assert any(req.endswith(f"/{mod}.tsx") for req in requires), (key, mod, requires)
    for key in ("p2", "p3"):
        for rel in PROBE_SPECS[key][1]:
            assert (REPO_ROOT / rel).is_file(), rel
    p9 = build_probe_source("p9")
    assert "m3 17 2 2 4-4" in p9 and "M13 18h8" in p9
