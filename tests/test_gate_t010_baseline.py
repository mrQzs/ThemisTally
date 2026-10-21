"""T010 战前门禁：桌面端前端只读页面二（凭据、日志与用量、插件、历史与审计，第九片）的黑盒基准测试
（合同 t010-desktop-readonly2，plan_version 1，基线 841e481）。

被测对象是 ``desktop/web/``：四个页面文件（SecretsPage、LogsPage、PluginsPage、HistoryPage）从占位换成真页面，
新增 ``src/pages/readonly2/`` 下的视图与逻辑（common-、secrets-、logs-、plugins-、history- 前缀共 25 个文件；T013 合并重复件后删掉 common-copy.ts 与
history-ActorTag.tsx，下面的文件清单只列另外 23 个）、
``src/mock/readonly2-*.ts`` 三份夹具、九个 ``tests/readonly2-*`` 执行端测试，另改 ``src/components/Drawer.css`` 的 top 与文件头注释（站主 Q3 选 a）。

基线上这些都还没有，所以本文件的“失败”断言落在目标文件不存在或内容不符上，不是导入、收集或语法错误：模块级只导入标准库，
用到被测文件的地方都在用例函数里读；候选里还没有 ``src/pages/readonly2/`` 与 ``src/mock/readonly2-*.ts`` 时，``pipeline`` 夹具不跑 npm
（没有东西可测，也省掉联网的 ``npm ci``），用到它的用例以断言失败写明原因。

结构（编号对应合同的 D01–D12；门禁端另加若干静态守卫和自检）：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：文件在位、页面文件结构（PageFrame、load 与 isEmpty 是模块级标识符）、
  14 份 JSON 与 9 个 ``*Page.tsx`` 不变、源码守卫（禁用词、井号加十六进制、颜色函数名、整词的网络接口、``role=status``、
  ``ServerIcon``、字体引用、``data-page-state``、``h1``）、视图不直接调 api.ts、读取函数与夹具的位置、CSS 取值（最小宽 720/860/900/1000、
  占比条、mark、KeyDiff 的底色令牌、抽屉的 dl 与资源表、``overflow``、``min-width: 0``）、令牌与 px 注释、内联 style 只出现在占比条、
  Drawer.css 的 top、图标 fill 与 stroke、夹具只能是 ``.ts``、执行端 9 份测试在位且不用 skip、only、todo。
- 流水线断言（``pipeline`` 夹具）：在 ``desktop/web`` 下按顺序跑 ``npm ci``、``npm run build``、``npm test``、``npm run check:contract``，
  再把探针逐份写成 ``gate-probe/probe-<唯一标识>-t010-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除；
  前后各取一次 ``git status``。全量 pytest 默认跳过用到 ``pipeline`` 的用例（``tests/conftest.py``），点名运行本文件时才跑。
- 门禁自检（``test_gate_selfcheck_*``，不依赖候选）：把检查函数喂给正确样本和改坏的样本。

探针（Vitest + jsdom）：

- readers：页内读取函数 searchLogs、getHistoryEntry、getPlugin 的五开关、命令数组、夹具规则、深拷贝（过渡）；
- secrets：D01，经 ``vi.mock`` 替换 api.ts 的 listSecrets 给出各种来源与遮蔽值；
- logs：D02（检索）与 D03（用量），替换 getUsage 与 searchLogs；
- plugins：D04（表）与 D05（抽屉、焦点与 Esc、复制、过期回应）；
- history：D06（表）与 D07（差异抽屉、KeyDiff、footer）；
- app：D08（五态，过渡）与 D09（写入口与白名单，个数过渡）；
- nonet：四页逐个渲染、打开抽屉、提交检索，浏览器网络接口调用次数为 0。

DoD 对应：D01–D11 的证据是 V01（本文件）；D12 的证据是改动范围门禁、V02（T001–T008 门禁回归）、V03（桌面端状态表回归）。
改动范围由调度器的范围门禁证明，这里不写相对基线的范围断言。

过渡断言（``test_transitional_`` 开头，docstring 第一行写明哪项后续工作推翻它）：页内读取函数与夹具规则（接本机服务那一片并入 api.ts）、
经 ``?mock=`` 渲染 App 的四页五态与由夹具得到的具体值（行数、数字、写入口个数）。其余（视图、纯函数、CSS 取值、源码规则、
写入口全部禁用这条规则本身、抽屉的焦点与 Esc）是长期断言。

合同（v2）没有写死的地方（组件名、类名）探针只按合同写明的文字、tone、title、``data-page``、``data-drawer``、``data-source``、
``tt-num``、``tt-masked`` 与 Table 的 ``aria-label`` 取元素，不写别的类名；文字断言一律以合同为准，每一条都能在合同 Behavior contract 里找到原文。

门禁做不到、留给人的项（人工验收）：视觉（暗色、浅色各一次）、1024 × 640 与缩放下的整页横向滚动、真浏览器里的抽屉焦点、
禁用入口的悬停提示、原生 title 悬停、真剪贴板、真实正则的高亮退让、forced-colors、四页在真框架里的五态。
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
R2_REL = f"{SRC_REL}/pages/readonly2"
R2 = SRC / "pages" / "readonly2"
MOCK_REL = f"{SRC_REL}/mock"
MOCK = SRC / "mock"
PAGES_REL = f"{SRC_REL}/pages"
TESTS_REL = f"{WEB_REL}/tests"

# 合同 Scope 的新增源码（allowed_new_files 里的非测试文件）：readonly2 下 25 个，mock 下 3 个。
# common-copy.ts 与 history-ActorTag.tsx 不再列：T013 把它们并进 src/components、删掉这两份（站主按 T013 规划 §8.1 R4 退役）
R2_FILES = (
    "common-icons.tsx", "common-format.ts", "common-InfoNote.tsx", "common-styles.css", "common-readers.ts",
    "secrets-SecretsView.tsx", "secrets-logic.ts", "secrets-styles.css",
    "logs-LogsView.tsx", "logs-SearchPanel.tsx", "logs-SearchResults.tsx", "logs-UsagePanel.tsx", "logs-logic.ts", "logs-styles.css",
    "plugins-PluginsView.tsx", "plugins-PluginDrawer.tsx", "plugins-logic.ts", "plugins-styles.css",
    "history-HistoryView.tsx", "history-HistoryDrawer.tsx", "history-KeyDiff.tsx", "history-logic.ts",
    "history-styles.css",
)
MOCK_FILES = ("readonly2-search.ts", "readonly2-history-entries.ts", "readonly2-plugin-show.ts")
NEW_SOURCE_FILES = tuple(f"{R2_REL}/{n}" for n in R2_FILES) + tuple(f"{MOCK_REL}/{n}" for n in MOCK_FILES)
# 合同“执行端测试”：九份。
EXECUTOR_TESTS = ("readonly2-logic.test.ts", "readonly2-readers.test.ts", "readonly2-secrets.test.tsx", "readonly2-logs.test.tsx",
                  "readonly2-plugins.test.tsx", "readonly2-history.test.tsx", "readonly2-app.test.tsx", "readonly2-css.test.ts",
                  "readonly2-static.test.ts")

PAGE_FILES = {
    "secrets": "SecretsPage.tsx",
    "logs": "LogsPage.tsx",
    "plugins": "PluginsPage.tsx",
    "history": "HistoryPage.tsx",
}
# 基线（841e481）：src/mock/ 恰有 14 份 JSON、3 份 .ts；src/pages/ 顶层恰有 9 个 *Page.tsx。
BASELINE_JSON = ("attempt", "file-events", "file-executor-report", "history", "meta", "plugins", "preset-diff", "presets",
                 "profiles", "roles", "runtimes", "secrets", "status", "usage")
BASELINE_MOCK_TS = ("scenario.ts", "empty.ts", "shell.ts")
BASELINE_PAGES = ("OverviewPage.tsx", "TasksPage.tsx", "RolesPage.tsx", "RuntimesPage.tsx", "SecretsPage.tsx", "LogsPage.tsx",
                  "PluginsPage.tsx", "HistoryPage.tsx", "SettingsPage.tsx")

# 合同“公共约定”：静态检查禁用词（扫 desktop/web/src/**/*.{ts,tsx} 全文，含注释与字符串）。
FORBIDDEN_WORDS = ("dangerouslySetInnerHTML", "innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function",
                   "document.write", "srcdoc", "createContextualFragment", "DOMParser")
FORBIDDEN_CALLS = ("matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver")
NETWORK_WORDS = ("fetch", "XMLHttpRequest", "EventSource", "WebSocket")

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
# 源码规则（合同“公共约定”、D11）
# ---------------------------------------------------------------------------

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])")
COLOR_FUNC_RE = re.compile(r"\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(", re.I)
FONT_PATTERNS = {
    "字体文件的扩展名": re.compile(r"\.(?:woff2?|ttf|otf|eot|ttc|otc)\b", re.I),
    "随包字体的文件名": re.compile(r"sarasa-mono-sc-", re.I),
    "@font-face": re.compile(r"@font-face", re.I),
    "FontFace API": re.compile(r"\bFontFace\b|document\.fonts"),
}


def r2_files(*suffixes):
    if not R2.is_dir():
        return []
    return sorted(p for p in R2.rglob("*") if p.is_file() and (not suffixes or p.suffix in suffixes))


def r2_code_files():
    return r2_files(".ts", ".tsx")


def r2_css_files():
    return r2_files(".css")


def mock_new_files():
    return [MOCK / n for n in MOCK_FILES if (MOCK / n).is_file()]


def page_files():
    return [SRC / "pages" / name for name in PAGE_FILES.values() if (SRC / "pages" / name).is_file()]


def scanned_code_files():
    """合同源码守卫的范围：readonly2 的 ts、tsx，src/mock/readonly2-*.ts，四个页面文件（夹具字符串、注释都算）。"""
    return r2_code_files() + mock_new_files() + page_files()


def label_of(path):
    return Path(path).relative_to(WEB).as_posix()


def strip_ts_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(^|[^:'\"`])//[^\n]*", r"\1", text)


def word_hits(text, words):
    return [(text[:m.start()].count("\n") + 1, m.group(0)) for m in re.finditer(r"\b(?:" + "|".join(map(re.escape, words)) + r")\b", text)]


def source_guard_problems(label, raw):
    """合同公共约定的源码守卫，作用在一个文件的全文上。"""
    problems = []
    code = strip_ts_comments(raw)
    for word in FORBIDDEN_WORDS:
        if word in raw:
            problems.append(f"{label}:{raw[:raw.index(word)].count(chr(10)) + 1} 出现禁用词 {word}")
    for no, word in word_hits(raw, NETWORK_WORDS):
        problems.append(f"{label}:{no} 整词出现 {word}（含注释与夹具字符串）")
    if re.search(r"""role\s*[=:]\s*\{?\s*["']status["']""", code):
        problems.append(f"{label}：不能渲染 role=status")
    for name in FORBIDDEN_CALLS:
        if re.search(rf"\b{name}\b", code):
            problems.append(f"{label}：不能用 {name}")
    if "ServerIcon" in raw:
        problems.append(f"{label}：不该出现 ServerIcon")
    for what, pattern in FONT_PATTERNS.items():
        if pattern.search(raw):
            problems.append(f"{label}：出现 {what}（字体只经 fonts.css 引用）")
    body = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), raw, flags=re.S)
    for no, line in enumerate(body.splitlines(), 1):
        for m in HEX_RE.finditer(line):
            problems.append(f"{label}:{no} 出现井号加十六进制 {m.group(0)}（字符串、行注释里也不许）")
        for m in COLOR_FUNC_RE.finditer(line):
            problems.append(f"{label}:{no} 出现颜色函数名加括号 {m.group(0)}")
        if re.search(r"""[`'"][^`'"\n]*--tt-[^`'"\n]*\$\{""", line):
            problems.append(f"{label}:{no} 拼接了 --tt- 令牌名")
    return problems


def readonly2_rule_problems(label, raw):
    """readonly2 里的视图与逻辑：不写 data-page-state、不渲染 h1；数字不用 Intl 与 toLocaleString；对 api.ts 只有 import type。"""
    problems = []
    code = strip_ts_comments(raw)
    if re.search(r"""\bdata-page-state\s*=|["']data-page-state["']\s*:""", code):
        problems.append(f"{label}：视图与抽屉不写 data-page-state（整页恰一个，由 PageFrame 写）")
    if re.search(r"<h1\b", code):
        problems.append(f"{label}：视图不渲染 h1（标题归 PageFrame）")
    if re.search(r"\btoLocaleString\b|\bIntl\.", code):
        problems.append(f"{label}：千分位手写，不用 Intl、toLocaleString")
    for m in re.finditer(r"""import\s+([^;]*?)\s+from\s+['"]((?:\.\./)+api)['"]""", code, re.S):
        spec = m.group(1).strip()
        items = [s.strip() for s in spec.strip("{} \n").split(",") if s.strip()] if spec.startswith("{") else []
        type_only = spec.startswith("type ") or (items and all(s.startswith("type ") for s in items))
        if not type_only:
            problems.append(f"{label}：视图与逻辑不直接调 api.ts（只许 import type）：{m.group(0)[:80]}")
    return problems


def css_w4_problems(label, raw):
    problems = []
    body = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), raw, flags=re.S)
    for no, line in enumerate(body.splitlines(), 1):
        for m in HEX_RE.finditer(line):
            problems.append(f"{label}:{no} 写死颜色 {m.group(0)}")
        for m in COLOR_FUNC_RE.finditer(line):
            problems.append(f"{label}:{no} 颜色函数 {m.group(0)}")
    return problems


def executor_test_problems():
    problems = []
    folder = WEB / "tests"
    for name in EXECUTOR_TESTS:
        path = folder / name
        if not path.is_file():
            problems.append(f"{TESTS_REL}/{name} 不存在（执行端要写的测试）")
            continue
        text = _read(path)
        if not re.search(r"^\s*(?:it|test)(?:\.each\([^)]*\))?\(", text, re.M):
            problems.append(f"{name} 里没有用例")
        for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b", r"\bit\.skipIf\b"):
            if re.search(bad, text):
                problems.append(f"{name} 里出现 {bad}（不许 skip、only、todo）")
    return problems


# ---------------------------------------------------------------------------
# CSS 取值（合同 Behavior contract「样式取值」，D10）：类名不由合同定，所以只问“全部 readonly2 样式里有一条规则同时声明这几项”
# ---------------------------------------------------------------------------

def r2_css_text():
    return "\n".join(_read(p) for p in r2_css_files())


def minmax_problems(css):
    """grid-template-columns 里的 1fr 都要写成 minmax(0, 1fr)（1024 宽前提）。"""
    problems = []
    for selector, decls in parse_rules(css):
        for name, value in decls:
            if name in ("grid-template-columns", "grid-template") and "1fr" in cv(value).replace("minmax(0,1fr)", ""):
                problems.append(f"{selector} 的 {name} 里有裸的 1fr（要写 minmax(0, 1fr)）：{value}")
    return problems


def css_value_problems(css):
    bg = ("background", "background-color")
    specs = []
    for width in (720, 860, 900, 1000):
        specs.append((f"宽表最小宽 {width}px（写在以 .tt-table 为选择器的规则上，不用 .tt-table-wrap）", r"\.tt-table(?![\w-])",
                      [C("min-width", eq=f"{width}px")]))
    specs += [
        ("占比条轨道：高 8、--tt-radius-full、--tt-surface-3 底", None,
         [C("height", eq="8px"), C("border-radius", eq="var(--tt-radius-full)"), C(bg, has=("var(--tt-surface-3)",))]),
        ("占比条填充：--tt-navy-500 底（不用金色）", None, [C(bg, eq="var(--tt-navy-500)")]),
        ("占比条最小宽 60px", None, [C("min-width", eq="60px")]),
        ("百分比文字宽 44px", None, [C("width", eq="44px")]),
        ("检索命中 mark：--tt-highlight 底、--tt-text-1 字、圆角 --tt-radius-sm、内边距 0 1px（以 mark 元素为选择器）", r"(?<![\w.#-])mark(?![\w-])",
         [C(bg, has=("var(--tt-highlight)",)), C("color", eq="var(--tt-text-1)"),
          C("border-radius", eq="var(--tt-radius-sm)"), sides_is("padding", top="0", right="1px")]),
        ("KeyDiff 之前：--tt-diff-del 底", None, [C(bg, has=("var(--tt-diff-del)",))]),
        ("KeyDiff 之后：--tt-diff-add 底", None, [C(bg, has=("var(--tt-diff-add)",))]),
        ("KeyDiff 值块：--tt-mono-sm、圆角 --tt-radius-sm、内边距 1px --tt-space-1", None,
         [C("font", eq="var(--tt-mono-sm)"), C("border-radius", eq="var(--tt-radius-sm)"),
          sides_is("padding", top="1px", right="var(--tt-space-1)")]),
        ("长串换行：word-break break-all（键、lock_sha256）", None, [C("word-break", eq="break-all")]),
        ("抽屉 dl 两列 96px minmax(0, 1fr)，间距 --tt-space-1 --tt-space-3", None,
         [C("grid-template-columns", eq="96px minmax(0, 1fr)"), HasAll(("gap", "row-gap", "column-gap"), "var(--tt-space-1)", "var(--tt-space-3)")]),
        ("资源表三列 minmax(0, 1fr) 120px 64px", None, [C("grid-template-columns", eq="minmax(0, 1fr) 120px 64px")]),
        ("资源表头高 32px", None, [AnyOf(C("height", eq="32px"), C("min-height", eq="32px"))]),
        ("资源表与键级差异行高 36px", None, [AnyOf(C("height", eq="36px"), C("min-height", eq="36px"))]),
        ("小节卡：--tt-surface-1 底、1px --tt-border、圆角 --tt-radius-lg、内边距 --tt-space-3 --tt-space-4", None,
         [C(bg, has=("var(--tt-surface-1)",)), C("border", has=("1px", "var(--tt-border)")),
          C("border-radius", eq="var(--tt-radius-lg)"), sides_is("padding", top="var(--tt-space-3)", right="var(--tt-space-4)")]),
        ("小节标题 h2：--tt-title-sm", None, [C("font", eq="var(--tt-title-sm)")]),
        ("检索表单卡：flex、可换行、间距 --tt-space-3、内边距 --tt-space-3 --tt-space-4", None,
         [C("display", eq="flex"), C("flex-wrap", eq="wrap"), HasAll(("gap",), "var(--tt-space-3)"),
          sides_is("padding", top="var(--tt-space-3)", right="var(--tt-space-4)")]),
        ("检索框 flex 1 1 320px", None, [C("flex", eq="1 1 320px")]),
        ("任务下拉宽 200px", None, [C("width", eq="200px")]),
        ("最多条数宽 96px", None, [C("width", eq="96px")]),
        ("检索结果头部内边距 --tt-space-2 --tt-space-4", None, [sides_is("padding", top="var(--tt-space-2)", right="var(--tt-space-4)")]),
        ("检索结果组头高 32px、--tt-surface-2 底", None,
         [AnyOf(C("height", eq="32px"), C("min-height", eq="32px")), C(bg, has=("var(--tt-surface-2)",))]),
        ("检索摘录：--tt-mono-md、white-space pre", None,
         [C("font", eq="var(--tt-mono-md)"), C("white-space", eq="pre")]),
        ("检索摘录单行省略：text-overflow ellipsis", None, [C("text-overflow", eq="ellipsis")]),
        ("path:line 行：--tt-mono-sm、--tt-text-2", None, [C("font", eq="var(--tt-mono-sm)"), C("color", eq="var(--tt-text-2)")]),
        ("会被压缩的 flex 子元素写 min-width: 0", None, [C("min-width", zero=True)]),
        ("合计数字：--tt-display", None, [C("font", eq="var(--tt-display)")]),
        ("说明条（InfoNote）：--tt-tone-info-bg 底、--tt-tone-info-fg 字、--tt-radius-md", None,
         [C(bg, has=("var(--tt-tone-info-bg)",)), C("color", eq="var(--tt-tone-info-fg)"), C("border-radius", eq="var(--tt-radius-md)")]),
        ("带图标的标签：gap --tt-space-1", None, [C("gap", eq="var(--tt-space-1)")]),
    ]
    return group_problems(css, "readonly2 样式", specs) + minmax_problems(css)


BASELINE_DRAWER_RULES = [
    (".tt-drawer", [("position", "fixed"), ("top", "0"), ("right", "0"), ("bottom", "var(--tt-tabbar-height)"), ("width", "520px"),
                    ("max-width", "60%"), ("z-index", "var(--tt-z-drawer)"), ("background", "var(--tt-surface-1)"),
                    ("border-left", "1px solid var(--tt-border)"), ("border-top-left-radius", "var(--tt-radius-xl)"),
                    ("border-bottom-left-radius", "var(--tt-radius-xl)"), ("box-shadow", "var(--tt-shadow-3)"), ("display", "flex"),
                    ("flex-direction", "column")]),
    (".tt-drawer__head", [("display", "flex"), ("align-items", "center"), ("justify-content", "space-between"),
                          ("gap", "var(--tt-space-4)"), ("padding", "var(--tt-space-4) var(--tt-space-5)"),
                          ("border-bottom", "1px solid var(--tt-border)")]),
    (".tt-drawer__title", [("margin", "0"), ("font", "var(--tt-title-md)")]),
    (".tt-drawer__body", [("padding", "var(--tt-space-5)"), ("overflow", "auto"), ("flex", "1")]),
    (".tt-drawer__footer", [("display", "flex"), ("justify-content", "flex-end"), ("gap", "var(--tt-space-2)"),
                            ("padding", "var(--tt-space-3) var(--tt-space-5)"), ("border-top", "1px solid var(--tt-border)")]),
]


def drawer_css_problems(raw):
    """站主 Q3 选 a：top 0 → 40px（同一行写出处注释），文件头注释写出 40、删掉「顶边取 0」；T004 门禁已管的位置、宽、层级几项仍成立。
    其余规则是否没动、是否只改了 top，交给范围门禁和终审读补丁，这里不冻结共享组件文件。"""
    problems = []
    rule = next((d for s, d in parse_rules(raw) if s == ".tt-drawer"), None)
    if rule is None:
        return ["Drawer.css 里没有 .tt-drawer 规则"]
    got = {n: cv(v) for n, v in rule}
    want = {"top": "40px", "position": "fixed", "right": "0", "bottom": "var(--tt-tabbar-height)", "width": "520px",
            "max-width": "60%", "z-index": "var(--tt-z-drawer)"}
    for name, value in want.items():
        if got.get(name) != value:
            problems.append(f"Drawer.css .tt-drawer 的 {name} 应为 {value}，实际 {got.get(name)}")
    top_line = next((ln for ln in raw.splitlines() if re.match(r"\s*top\s*:", ln)), "")
    if "40px" not in top_line or not re.search(r"/\*.+\*/", top_line):
        problems.append(f"top 那一行应写 40px 并带同一行的出处注释，实际：{top_line.strip()!r}")
    header = re.split(r"(?m)^\.tt-drawer\s*\{", raw, maxsplit=1)[0]
    if "顶边取 0" in header or "本片没有标题栏" in header:
        problems.append("文件头注释还写着「顶边取 0（本片没有标题栏）」，应一并改掉")
    if "40" not in header:
        problems.append("文件头注释应改成顶边让位 40 高的标题栏（写出 40）")
    return problems


# ---------------------------------------------------------------------------
# 静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s1_d11_new_files_and_page_wiring():
    """S1 / D11（合同 Scope、公共约定）：readonly2 下 23 个新源码与样式（T013 并走的两个不算）、src/mock 下 3 个夹具都在；readonly2 里没有子目录，文件名都不以 Page.tsx 结尾；
    四个页面文件各含 PageFrame、默认导出、从 ./readonly2/ 引入视图，不再有占位行「夹具数据已读到」；日志页引入 common-readers（searchLogs），
    插件页引入 getPlugin，历史页引入 getHistoryEntry；视图收数据与读取函数，由页面文件以模块级引用传入。"""
    need_new_sources()
    stray = [p.relative_to(WEB).as_posix() for p in R2.iterdir() if p.is_dir()]
    assert not stray, f"readonly2 下不分子目录：{stray}"
    page_like = [p.name for p in R2.iterdir() if p.name.endswith("Page.tsx")]
    assert not page_like, f"readonly2 里的文件名不以 Page.tsx 结尾：{page_like}"
    problems = []
    needs = {"logs": "searchLogs", "plugins": "getPlugin", "history": "getHistoryEntry"}
    for page, name in PAGE_FILES.items():
        text = _read(need_file(f"{PAGES_REL}/{name}"))
        if "PageFrame" not in text:
            problems.append(f"{name} 不含 PageFrame")
        if not re.search(r"export\s+default\s+function\b|export\s+default\b", text):
            problems.append(f"{name} 没有默认导出（routes.ts 按默认导出引入）")
        if not re.search(r"""from\s+['"]\./readonly2/""", text):
            problems.append(f"{name} 没有从 ./readonly2/ 引入视图")
        if "夹具数据已读到" in text:
            problems.append(f"{name} 里还有占位行「夹具数据已读到」")
        if page in needs and not (needs[page] in text and re.search(r"""['"]\./readonly2/common-readers['"]""", text)):
            problems.append(f"{name} 应从 ./readonly2/common-readers 引入 {needs[page]} 并传给视图（读法 A）")
    fail_if(problems, "页面文件的接线")


def test_s2_d11_page_frame_load_and_is_empty_are_module_level():
    """S2 / D11（合同“页面结构与边界”）：四个页面文件的 PageFrame 的 load 依次是 listSecrets、getUsage、getPlugins、getHistory（模块级引用，不是内联函数）；
    isEmpty 若有，是模块级标识符（不是箭头函数、不是内联）；日志页不传 isEmpty（?mock=empty 下仍是 data）；凭据页 refreshLabel 是「重新检查」。"""
    loads = {"secrets": "listSecrets", "logs": "getUsage", "plugins": "getPlugins", "history": "getHistory"}
    problems = []
    for page, name in PAGE_FILES.items():
        raw = _read(need_file(f"{PAGES_REL}/{name}"))
        code = strip_ts_comments(raw)
        m = re.search(r"\bload=\{\s*(\w+)\s*\}", code)
        if not m or m.group(1) != loads[page]:
            problems.append(f"{name}：load 应是模块级标识符 {loads[page]}，实际 {m.group(0) if m else '（没找到 load={标识符}）'}")
        empty = re.search(r"\bisEmpty=\{([^}]*)\}", code)
        if page == "logs":
            if empty:
                problems.append("LogsPage.tsx 不能传 isEmpty（?mock=empty 下日志与用量页仍是 data）")
            continue
        if not empty:
            problems.append(f"{name}：应传 isEmpty")
            continue
        ident = empty.group(1).strip()
        if not re.fullmatch(r"[A-Za-z_]\w*", ident):
            problems.append(f"{name}：isEmpty 应是模块级标识符，实际 {{{ident}}}")
        elif not (re.search(rf"^(?:export\s+)?(?:const|function)\s+{ident}\b", code, re.M)
                  or re.search(rf"import\s+[^;]*\b{ident}\b[^;]*from", code, re.S)):
            problems.append(f"{name}：isEmpty 的 {ident} 应定义在模块级（或从别处引入），不在组件函数体里")
    secrets = strip_ts_comments(_read(need_file(f"{PAGES_REL}/SecretsPage.tsx")))
    if not re.search(r"refreshLabel=(?:\"重新检查\"|'重新检查'|\{\s*[\"']重新检查[\"']\s*\})", secrets):
        problems.append("SecretsPage.tsx 的 refreshLabel 应是「重新检查」")
    fail_if(problems, "PageFrame 的 load 与 isEmpty")


def test_s3_d11_top_level_counts_unchanged():
    """S3 / D11（合同“页面结构与边界”）：src/mock/ 仍恰有 14 份 JSON（夹具只能是 .ts），.ts 含基线 3 份和 readonly2-search、readonly2-history-entries、
    readonly2-plugin-show 三份；src/pages/ 顶层仍恰有 9 个 *Page.tsx 且都含 PageFrame。"""
    need_new_sources()
    jsons = sorted(p.stem for p in MOCK.glob("*.json"))
    assert jsons == sorted(BASELINE_JSON), f"src/mock/ 应恰有基线的 14 份 JSON，实际 {jsons}"
    ts = {p.name for p in MOCK.glob("*.ts")}
    assert set(BASELINE_MOCK_TS + MOCK_FILES) <= ts, f"src/mock/ 的 .ts 应含基线 3 份和本片 3 份夹具，实际 {sorted(ts)}"
    pages = sorted(p.name for p in (SRC / "pages").glob("*Page.tsx"))
    assert pages == sorted(BASELINE_PAGES), f"src/pages/ 顶层应恰有 9 个 *Page.tsx，实际 {pages}"
    for name in pages:
        assert "PageFrame" in _read(SRC / "pages" / name), f"{name} 不含 PageFrame"


def test_s4_d11_source_guards_cover_fixtures_and_pages():
    """S4 / D11（合同公共约定的源码守卫）：readonly2 的 ts、tsx，src/mock/readonly2-*.ts，四个页面文件——夹具字符串与注释也算——不出现 dangerouslySetInnerHTML、
    innerHTML、outerHTML、insertAdjacentHTML、eval(、new Function、document.write、srcdoc、createContextualFragment、DOMParser；整词不出现 fetch、XMLHttpRequest、
    EventSource、WebSocket；不渲染 role=status；不用 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver；不出现 ServerIcon、字体扩展名、sarasa-mono-sc-、
    @font-face、FontFace、document.fonts；字符串与行注释里不写井号加 3/4/6/8 位十六进制、颜色函数名加括号，不拼接 --tt- 前缀。"""
    need_new_sources()
    problems = []
    for path in scanned_code_files():
        problems += source_guard_problems(label_of(path), _read(path))
    fail_if(problems, "源码守卫")


def test_s5_d11_views_stay_pure_and_have_no_page_state():
    """S5 / D11（合同公共约定、页面结构与边界）：readonly2 的源码不写 data-page-state、不渲染 h1；千分位手写（不用 Intl、toLocaleString）；
    对 api.ts 只有 import type；common-readers.ts 导出 searchLogs、getHistoryEntry、getPlugin；mock 夹具带「示意」二字，来源是 .ts。"""
    need_new_sources()
    problems = []
    for path in r2_code_files():
        problems += readonly2_rule_problems(label_of(path), _read(path))
    readers = strip_ts_comments(_read(R2 / "common-readers.ts"))
    for name in ("searchLogs", "getHistoryEntry", "getPlugin"):
        if not (re.search(rf"export\s+(?:async\s+)?(?:function|const)\s+{name}\b", readers)
                or re.search(rf"export\s*\{{[^}}]*\b{name}\b", readers)):
            problems.append(f"common-readers.ts 没有 export {name}")
    for path in mock_new_files():
        if "示意" not in _read(path):
            problems.append(f"{label_of(path)} 应标「示意」")
    fail_if(problems, "readonly2 的结构规则")


def test_s6_d10_readonly2_css_values():
    """S6 / D10（合同「样式取值」）：宽表最小宽 720/860/900/1000（.tt-table 上）；占比条轨道高 8、--tt-radius-full、--tt-surface-3 底，填充 --tt-navy-500，
    最小宽 60，百分比文字宽 44；检索命中 mark 用 --tt-highlight 底、--tt-text-1 字、圆角 --tt-radius-sm、内边距 0 1px；KeyDiff 之前用 --tt-diff-del、
    之后用 --tt-diff-add，值块 --tt-mono-sm、--tt-radius-sm、内边距 1px --tt-space-1；键与 lock_sha256 word-break break-all；抽屉 dl 两列
    96px minmax(0, 1fr)、间距 --tt-space-1 --tt-space-3；资源表三列 minmax(0, 1fr) 120px 64px，表头 32、行 36；小节卡、检索表单卡、结果头与组头、摘录、
    合计数字、说明条的取值；grid 里没有裸的 1fr；有 min-width: 0 的规则。"""
    need_new_sources()
    css = r2_css_text()
    assert css.strip(), "readonly2 下没有样式文件的内容"
    fail_if(css_value_problems(css), "readonly2 样式取值")


def test_s7_d10_tokens_and_px_notes_in_new_css():
    """S7 / D10（合同公共约定）：readonly2 的每份 CSS——z-index、圆角、阴影、字体只用 --tt-* 令牌；除 0 与 1px 外的 px 字面量同一行带出处注释；
    样式里不写死颜色与颜色函数（W4 在流水线里另查）。"""
    need_new_sources()
    problems = []
    for path in r2_css_files():
        raw = _read(path)
        label = label_of(path)
        problems += token_only_problems(label, raw)
        problems += px_literal_problems(label, raw)
        problems += css_w4_problems(label, raw)
    fail_if(problems, "新样式的令牌与 px 注释")


def test_s8_d10_inline_style_only_on_usage_bar():
    """S8 / D10（合同「样式取值」：内联 style 只用于运行时算出的占比条宽度，只出现在 logs-UsagePanel.tsx）：readonly2 的源码与四个页面文件里，
    style 属性只出现在 logs-UsagePanel.tsx；别的文件没有内联 style。写法不限（style={barStyle} 也行），宽度只在占比条上由 D03 探针在 DOM 层核对。"""
    need_new_sources()
    problems = []
    for path in r2_code_files() + page_files():
        code = strip_ts_comments(_read(path))
        if re.search(r"\bstyle\s*=", code) and path.name != "logs-UsagePanel.tsx":
            problems.append(f"{label_of(path)}：内联 style 只许出现在占比条（logs-UsagePanel.tsx）")
    usage = _read(R2 / "logs-UsagePanel.tsx")
    if not re.search(r"\bstyle\s*=", strip_ts_comments(usage)):
        problems.append("logs-UsagePanel.tsx 里应有占比条的内联 style（宽度用内联 style 的百分比）")
    fail_if(problems, "内联 style")


def test_s9_q3_drawer_css_top_is_40():
    """S9 / Q3（站主选 a）：Drawer.css 的 .tt-drawer 顶边 top 为 40px，同一行带出处注释；文件头注释写出 40、不再写「顶边取 0（本片没有标题栏）」；
    position fixed、right 0、bottom、width 520、max-width 60%、z-index 仍成立（T004 门禁已管的几项）；不冻结其余规则。"""
    raw = _read(need_file(f"{SRC_REL}/components/Drawer.css"))
    fail_if(drawer_css_problems(raw), "Drawer.css")


def test_s10_d11_common_icons_use_only_none_and_current_color():
    """S10 / D11（合同 common-icons）：common-icons.tsx 导出 ExternalLinkIcon；里面的 fill、stroke 只用 none 与 currentColor。"""
    text = _read(need_file(f"{R2_REL}/common-icons.tsx"))
    assert re.search(r"export\s+(?:const|function)\s+ExternalLinkIcon\b", text), "common-icons.tsx 没有 export ExternalLinkIcon"
    bad = [m.group(0) for m in re.finditer(r"""\b(?:fill|stroke)\s*=\s*(?:"([^"]*)"|'([^']*)'|\{\s*["']([^"']*)["']\s*\})""", text)
           if (m.group(1) or m.group(2) or m.group(3)) not in ("none", "currentColor")]
    assert not bad, f"common-icons.tsx 的 fill、stroke 只用 none 与 currentColor：{bad}"


def test_d12_executor_tests_in_place():
    """D12（合同“执行端测试”）：九份 readonly2-* 测试都在（logic、readers、secrets、logs、plugins、history、app、css、static），各至少一条用例，
    不出现 skip、only、todo、fails。"""
    fail_if(executor_test_problems(), "执行端的测试文件")


# ---------------------------------------------------------------------------
# 探针（Vitest + jsdom）：每份若干 describe，describe 名以 D 编号开头
# ---------------------------------------------------------------------------

PRELUDE = r"""
import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { CircleXIcon, CheckIcon, TriangleAlertIcon, LockIcon, RotateCcwIcon, ListChecksIcon } from '../src/icons';
import { SecretsIcon, PluginsIcon } from '../src/icons/frame';

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
  document.documentElement.removeAttribute('data-theme');
  try {
    delete (navigator as any).clipboard;
  } catch (e) {
    // 没定义过就算了
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
async function mountApp(hash: string) {
  window.location.hash = hash;
  const mod: any = await import('../src/App');
  const App = mod.default ?? mod.App;
  expect(App, 'src/App.tsx 应导出 App').toBeTruthy();
  const out = render(<App />);
  await settle();
  return out;
}
function pageRoot(): HTMLElement {
  const nodes = document.querySelectorAll('[data-page-state]');
  expect(nodes.length, '应恰有一个带 data-page-state 的页面根').toBe(1);
  return nodes[0] as HTMLElement;
}
function viewRoot(page: string): HTMLElement {
  const el = document.querySelector('[data-page="' + page + '"]');
  expect(el, '应有视图根 [data-page=' + page + ']').not.toBeNull();
  return el as HTMLElement;
}
function buttonByText(root: ParentNode, text: string): HTMLButtonElement {
  const hit = Array.from(root.querySelectorAll('button')).find((b) => textOf(b) === text);
  expect(hit, '找不到文字为「' + text + '」的按钮').toBeTruthy();
  return hit as HTMLButtonElement;
}
function maybeButton(root: ParentNode, text: string): HTMLButtonElement | null {
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
const ok = (data: any, command: string[] = ['demo']) => ({ ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 });
const bad = (messages: string[], command: string[]) => ({ ok: false, exit_code: 2, data: null, output: [], messages, command, elapsed_ms: 0 });
const ERROR_TEXT = 'ERROR [内核报错原文的示意] 读取 .agent/runs 失败：Permission denied';
const HASH_A = '0123456789abcdef'.repeat(4);
const HASH_B = 'fedcba9876543210'.repeat(4);
const HASH_LOCK = '00112233445566778899aabbccddeeff'.repeat(2);

function tableByLabel(label: string): HTMLTableElement {
  const t = document.querySelector('table[aria-label="' + label + '"]');
  expect(t, '应有 table[aria-label=' + label + ']').not.toBeNull();
  return t as HTMLTableElement;
}
function headersOf(table: Element): string[] {
  return Array.from(table.querySelectorAll('thead th')).map((th) => textOf(th));
}
function tableByHeaders(root: ParentNode, headers: string[]): HTMLTableElement {
  const hit = Array.from(root.querySelectorAll('table')).find((t) => JSON.stringify(headersOf(t)) === JSON.stringify(headers));
  expect(hit, '找不到表头为 ' + headers.join('、') + ' 的表').toBeTruthy();
  return hit as HTMLTableElement;
}
function bodyRows(table: Element): HTMLElement[] {
  return Array.from(table.querySelectorAll('tbody tr')) as HTMLElement[];
}
function cellsOf(row: Element): HTMLElement[] {
  return Array.from(row.querySelectorAll('td')) as HTMLElement[];
}
function rowByFirstCell(table: Element, text: string): HTMLElement {
  const hit = bodyRows(table).find((r) => textOf(cellsOf(r)[0]) === text);
  expect(hit, '找不到首列为「' + text + '」的行').toBeTruthy();
  return hit as HTMLElement;
}
function hasClass(cell: Element, cls: string): boolean {
  return cell.classList.contains(cls) || cell.querySelector('.' + cls) !== null;
}
function tagsIn(el: ParentNode): HTMLElement[] {
  return Array.from(el.querySelectorAll('[data-tone]')) as HTMLElement[];
}
function tagWithText(el: ParentNode, text: string): HTMLElement {
  const hit = tagsIn(el).find((t) => textOf(t) === text);
  expect(hit, '找不到文字为「' + text + '」的标签').toBeTruthy();
  return hit as HTMLElement;
}
function titleOf(el: Element): string | null {
  if (el.hasAttribute('title')) return el.getAttribute('title');
  const inner = el.querySelector('[title]');
  return inner ? inner.getAttribute('title') : null;
}
function leafWithText(root: ParentNode, text: string): HTMLElement | null {
  return (Array.from(root.querySelectorAll('*')).find((e) => e.children.length === 0 && textOf(e) === text) as HTMLElement) || null;
}
// 文字包含 text 的最里层元素（子元素里没有再包含它的）
function smallestWith(root: ParentNode, text: string): HTMLElement | null {
  const hits = Array.from(root.querySelectorAll('*')).filter(
    (e) => textOf(e).includes(text) && !Array.from(e.children).some((c) => textOf(c).includes(text)),
  );
  return (hits[0] as HTMLElement) || null;
}

function sigOf(svg: Element): string {
  const kids = Array.from(svg.children).map(
    (c) => c.tagName.toLowerCase() + JSON.stringify(Array.from(c.attributes).map((a) => [a.name, a.value]).sort()),
  );
  return [svg.getAttribute('width'), svg.getAttribute('height'), ...kids].join('|');
}
function iconSig(Comp: any, size: number): string {
  const holder = document.createElement('div');
  render(<Comp width={size} height={size} />, { container: holder });
  return sigOf(holder.querySelector('svg') as Element);
}
function hasIcon(root: ParentNode, Comp: any, size: number): boolean {
  const want = iconSig(Comp, size);
  return Array.from(root.querySelectorAll('svg')).some((s) => sigOf(s) === want);
}
function tipOf(btn: HTMLElement): string {
  // 需要假计时器：悬停包裹元素 400ms 后出现 role=tooltip
  const wrap = btn.closest('.tt-tooltip-wrap') as HTMLElement;
  expect(wrap, '禁用入口应被 Tooltip 的包裹元素包着').not.toBeNull();
  fireEvent.mouseEnter(wrap);
  advance(400);
  // 页面上可能同时有别的提示（例如抽屉关闭钮的提示）：只读触发元素自己 aria-describedby 指向的那个，不回退到 querySelector
  const trigger = wrap.firstElementChild as HTMLElement;
  const tipId = trigger.getAttribute('aria-describedby');
  expect(tipId, '悬停 400ms 后触发元素应带 aria-describedby').toBeTruthy();
  const tip = document.getElementById(tipId as string);
  expect(tip, 'aria-describedby 指向的提示应在文档里').not.toBeNull();
  const out = textOf(tip);
  fireEvent.mouseLeave(wrap);
  return out;
}
function expectedTitle(iso: string): string {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, '0');
  return (
    d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds()) +
    '（UTC ' + p(d.getUTCHours()) + ':' + p(d.getUTCMinutes()) + ':' + p(d.getUTCSeconds()) + '）'
  );
}
"""

# 替换 api.ts 的读函数与页内读取函数：默认透传到真实现，用例里按函数名给 overrides
HOIST = r"""
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
vi.mock('../src/pages/readonly2/common-readers', async (importOriginal) => {
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
function over(name: string, data: any, command: string[] = ['demo']) {
  hoisted.overrides[name] = () => Promise.resolve(ok(data, command));
}
function callsOf(name: string): any[][] {
  return hoisted.spies[name].mock.calls;
}
const clone = (v: any) => JSON.parse(JSON.stringify(v));
"""

# 抽屉共用的探针件：打开、关闭钮、焦点与 Esc 的套件（插件与历史各调一次）
DRAWER_KIT = r"""
function tbodyRows(): HTMLElement[] {
  return Array.from(document.querySelectorAll('main tbody tr')) as HTMLElement[];
}
function dialog(): HTMLElement | null {
  return document.querySelector('[role="dialog"]') as HTMLElement | null;
}
function closeBtn(): HTMLElement {
  const d = dialog();
  expect(d, '应有抽屉').not.toBeNull();
  const b = (d as HTMLElement).querySelector('button[aria-label="关闭（Esc）"]');
  expect(b, '抽屉头部应有「关闭（Esc）」钮').not.toBeNull();
  return b as HTMLElement;
}
async function openByEnter(row: HTMLElement) {
  focusOn(row);
  key('Enter', {}, row);
  await settle();
}

function drawerBehaviour(label: string, hash: string, rowCount: number, setup: () => void) {
  describe(label + ' 抽屉的焦点与 Esc', () => {
    it('Enter 与点击行都能打开；aria-modal=false、没有遮罩与模态；打开后焦点在头部「关闭（Esc）」钮', async () => {
      setup();
      await mountApp(hash);
      const rs = tbodyRows();
      expect(rs.length).toBe(rowCount);
      expect(dialog(), '没点之前没有抽屉').toBeNull();
      await openByEnter(rs[0]);
      const d = dialog() as HTMLElement;
      expect(d, 'Enter 应打开抽屉').not.toBeNull();
      expect(d.getAttribute('aria-modal')).toBe('false');
      expect(document.querySelectorAll('[aria-modal="true"]').length).toBe(0);
      expect((d.parentElement as HTMLElement).querySelector('[class*="scrim"], [class*="backdrop"]'), '抽屉所在挂载层里没有遮罩').toBeNull();
      expect(document.activeElement).toBe(closeBtn());
      key('Escape');
      expect(dialog()).toBeNull();
      fireEvent.click(rs[1]);
      await settle();
      expect(dialog(), '点击行应打开抽屉').not.toBeNull();
      expect((dialog() as HTMLElement).getAttribute('aria-modal')).toBe('false');
    });

    it('400ms 内在抽屉里按 Esc：抽屉关闭，焦点回到触发行，该行仍是选中行与 Table 的当前行', async () => {
      setup();
      await mountApp(hash);
      const rs = tbodyRows();
      await openByEnter(rs[0]);
      expect(document.activeElement).toBe(closeBtn());
      key('Escape');
      expect(dialog()).toBeNull();
      expect(document.activeElement).toBe(rs[0]);
      expect(rs[0].hasAttribute('data-selected'), '关闭后保留选中行').toBe(true);
      expect(rs[0].getAttribute('tabindex')).toBe('0');
    });

    it('K25：关闭钮的提示出现（400ms）后，第一次 Esc 只关提示、抽屉不关；第二次才关抽屉，焦点回触发行', async () => {
      setup();
      vi.useFakeTimers();
      await mountApp(hash);
      const rs = tbodyRows();
      await openByEnter(rs[0]);
      advance(399);
      expect(document.querySelector('[role="tooltip"]')).toBeNull();
      advance(1);
      const tip = document.querySelector('[role="tooltip"]');
      expect(tip, '400ms 后关闭钮出现工具提示').not.toBeNull();
      expect(textOf(tip)).toBe('关闭（Esc）');
      key('Escape');
      expect(document.querySelector('[role="tooltip"]'), '第一次 Esc 关提示').toBeNull();
      expect(dialog(), '第一次 Esc 不关抽屉').not.toBeNull();
      key('Escape');
      expect(dialog(), '第二次 Esc 关抽屉').toBeNull();
      expect(document.activeElement).toBe(rs[0]);
    });

    it('K6：焦点在抽屉外按 Esc 不关；点抽屉外（页面空白处、表格）也不关', async () => {
      setup();
      await mountApp(hash);
      const rs = tbodyRows();
      await openByEnter(rs[0]);
      focusOn(rs[1]);
      key('Escape', {}, rs[1]);
      expect(dialog(), '焦点在表格上按 Esc 不关').not.toBeNull();
      fireEvent.mouseDown(document.body);
      fireEvent.click(document.body);
      const main = document.querySelector('main') as HTMLElement;
      fireEvent.mouseDown(main);
      fireEvent.click(main);
      expect(dialog(), '点抽屉外不关').not.toBeNull();
    });

    it('K7、K24：开着时点另一行只换内容（始终一个抽屉）；在抽屉里按 Esc 后焦点回到后打开的那一行，选中行是它', async () => {
      setup();
      await mountApp(hash);
      const rs = tbodyRows();
      await openByEnter(rs[0]);
      const first = textOf(dialog());
      fireEvent.click(rs[2]);
      await settle();
      expect(document.querySelectorAll('[role="dialog"]').length).toBe(1);
      expect(textOf(dialog()), '换行后内容变了').not.toBe(first);
      key('Escape');
      expect(dialog()).toBeNull();
      expect(document.activeElement, '焦点回后打开的那一行').toBe(rs[2]);
      expect(rs[2].hasAttribute('data-selected')).toBe(true);
      expect(rs[0].hasAttribute('data-selected')).toBe(false);
      expect(rs[2].getAttribute('tabindex')).toBe('0');
    });

    it('K24：开着时用键盘换行（焦点到另一行按 Enter），再把焦点放回抽屉按 Esc，焦点回到后打开的那一行', async () => {
      setup();
      await mountApp(hash);
      const rs = tbodyRows();
      await openByEnter(rs[0]);
      const first = textOf(dialog());
      focusOn(rs[1]);
      key('Enter', {}, rs[1]);
      await settle();
      expect(document.querySelectorAll('[role="dialog"]').length).toBe(1);
      expect(textOf(dialog())).not.toBe(first);
      focusOn(closeBtn());
      key('Escape');
      expect(dialog()).toBeNull();
      expect(document.activeElement).toBe(rs[1]);
      expect(rs[1].hasAttribute('data-selected')).toBe(true);
    });

    it('切换路由时页面卸载，抽屉随之消失', async () => {
      setup();
      await mountApp(hash);
      const rs = tbodyRows();
      await openByEnter(rs[0]);
      expect(dialog()).not.toBeNull();
      const other = hash.indexOf('/history') >= 0 ? '#/secrets?mock=data' : '#/history?mock=data';
      await act(async () => {
        window.location.hash = other;
        await new Promise<void>((resolve) => setTimeout(resolve, 30));
      });
      await settle();
      expect(dialog(), '路由切走后抽屉应卸载').toBeNull();
    });
  });
}

function ddOf(root: ParentNode, label: string): HTMLElement {
  const dt = Array.from(root.querySelectorAll('dt')).find((d) => textOf(d) === label);
  expect(dt, 'dl 里应有 ' + label).toBeTruthy();
  return (dt as HTMLElement).nextElementSibling as HTMLElement;
}
function isSubsequence(want: string[], got: string[]): boolean {
  let i = 0;
  for (const g of got) if (g === want[i]) i += 1;
  return i === want.length;
}
"""

# ---------------------------------------------------------------------------
# readers 探针（过渡）
# ---------------------------------------------------------------------------

PROBE_READERS = PRELUDE + r"""
const PATTERN = 'logs[_ ]cat';

async function readers(): Promise<any> {
  const mod: any = await import('../src/pages/readonly2/common-readers');
  for (const n of ['searchLogs', 'getHistoryEntry', 'getPlugin']) {
    expect(typeof mod[n], 'common-readers.ts 应导出函数 ' + n).toBe('function');
  }
  return mod;
}
function setMock(v: string | null) {
  window.location.hash = v ? '#/logs?mock=' + v : '#/logs';
}
async function never(p: Promise<any>): Promise<boolean> {
  let done = false;
  p.then(() => { done = true; }, () => { done = true; });
  for (let i = 0; i < 20; i += 1) await Promise.resolve();
  await new Promise<void>((resolve) => setTimeout(resolve, 20));
  return !done;
}
const EXPECT_KEYS = ['command', 'data', 'elapsed_ms', 'exit_code', 'messages', 'ok', 'output'];

describe('读取函数：命令数组与信封', () => {
  it('data：信封七个字段；command 数组依次是 logs search q [--task t] --max N、config history show n、plugins show id', async () => {
    const m = await readers();
    setMock('data');
    const a = await m.searchLogs(PATTERN, null, 50);
    expect(Object.keys(a).sort()).toEqual(EXPECT_KEYS);
    expect(a.ok).toBe(true);
    expect(a.exit_code).toBe(0);
    expect(a.command.map(String)).toEqual(['logs', 'search', PATTERN, '--max', '50']);
    const b = await m.searchLogs(PATTERN, 'logs-cat', 7);
    expect(b.command.map(String)).toEqual(['logs', 'search', PATTERN, '--task', 'logs-cat', '--max', '7']);
    const c = await m.getHistoryEntry(42);
    expect(c.command.map(String)).toEqual(['config', 'history', 'show', '42']);
    const d = await m.getPlugin('docs-checks');
    expect(d.command.map(String)).toEqual(['plugins', 'show', 'docs-checks']);
    const e = await m.searchLogs('zzz-not-in-fixture', null, 50);
    expect(e.command.map(String), '夹具之外的参数，command 数组也照同一写法').toEqual(['logs', 'search', 'zzz-not-in-fixture', '--max', '50']);
  });

  it('返回已兑现的 Promise，不用计时器（假计时器下也能拿到结果）', async () => {
    const m = await readers();
    setMock('data');
    vi.useFakeTimers();
    let got = 0;
    m.searchLogs(PATTERN, null, 50).then(() => { got += 1; });
    m.getHistoryEntry(42).then(() => { got += 1; });
    m.getPlugin('docs-checks').then(() => { got += 1; });
    for (let i = 0; i < 10; i += 1) await Promise.resolve();
    expect(got).toBe(3);
  });
});

describe('读取函数：五个开关', () => {
  it('loading：三个函数都返回永不兑现的 Promise（先于参数校验）', async () => {
    const m = await readers();
    setMock('loading');
    expect(await never(m.searchLogs(PATTERN, null, 50))).toBe(true);
    expect(await never(m.searchLogs('zzz-not-in-fixture', null, 50))).toBe(true);
    expect(await never(m.getHistoryEntry(42))).toBe(true);
    expect(await never(m.getHistoryEntry(7))).toBe(true);
    expect(await never(m.getPlugin('docs-checks'))).toBe(true);
    expect(await never(m.getPlugin('nope'))).toBe(true);
  });

  it('error：ok false、exit_code 2、data null、messages 是报错原文（先于参数校验）', async () => {
    const m = await readers();
    setMock('error');
    for (const r of [await m.searchLogs(PATTERN, null, 50), await m.searchLogs('zzz', null, 50), await m.getHistoryEntry(42),
      await m.getHistoryEntry(7), await m.getPlugin('docs-checks'), await m.getPlugin('nope')]) {
      expect(r.ok).toBe(false);
      expect(r.exit_code).toBe(2);
      expect(r.data).toBeNull();
      expect(r.messages).toEqual([ERROR_TEXT]);
    }
  });

  it('empty：searchLogs 返回空 matches（truncated 假、两个计数 0）；另两个照常', async () => {
    const m = await readers();
    setMock('empty');
    const r = await m.searchLogs(PATTERN, null, 50);
    expect(r.ok).toBe(true);
    expect(r.data.matches).toEqual([]);
    expect(r.data.truncated).toBe(false);
    expect(r.data.skipped_links).toBe(0);
    expect(r.data.skipped_large).toBe(0);
    expect((await m.getHistoryEntry(42)).ok).toBe(true);
    expect((await m.getPlugin('docs-checks')).ok).toBe(true);
  });

  it('offline 与 data 一样返回夹具', async () => {
    const m = await readers();
    setMock('data');
    const a = await m.searchLogs(PATTERN, null, 50);
    const p = await m.getPlugin('docs-checks');
    const h = await m.getHistoryEntry(42);
    setMock('offline');
    expect(await m.searchLogs(PATTERN, null, 50)).toEqual(a);
    expect(await m.getPlugin('docs-checks')).toEqual(p);
    expect(await m.getHistoryEntry(42)).toEqual(h);
  });

  it('没有 ?mock= 与认不出的取值按 data 处理', async () => {
    const m = await readers();
    setMock(null);
    expect((await m.searchLogs(PATTERN, null, 50)).ok).toBe(true);
    window.location.hash = '#/logs?mock=bogus';
    expect((await m.getPlugin('docs-checks')).ok).toBe(true);
  });
});

describe('读取函数：夹具之外的参数', () => {
  it('ok false、exit_code 2、data null、messages 以「ERROR 夹具里没有这份数据：」开头', async () => {
    const m = await readers();
    setMock('data');
    for (const r of [await m.searchLogs('zzz-not-in-fixture', null, 50), await m.getHistoryEntry(7), await m.getHistoryEntry(0),
      await m.getPlugin('nope')]) {
      expect(r.ok).toBe(false);
      expect(r.exit_code).toBe(2);
      expect(r.data).toBeNull();
      expect(r.messages.length).toBeGreaterThan(0);
      expect(r.messages[0].startsWith('ERROR 夹具里没有这份数据：')).toBe(true);
    }
  });
});

describe('读取函数：检索夹具', () => {
  it('固定模式 logs[_ ]cat：两个 attempt 各至少一组，skipped_large ≥ 1，摘录 ≤ 200 字且命中模式，路径只用允许的后缀', async () => {
    const m = await readers();
    setMock('data');
    const r = await m.searchLogs(PATTERN, null, 500);
    expect(r.ok).toBe(true);
    const d = r.data;
    expect(Array.isArray(d.matches)).toBe(true);
    expect(d.truncated).toBe(false);
    expect(d.skipped_large).toBeGreaterThanOrEqual(1);
    expect(typeof d.skipped_links).toBe('number');
    const groups = new Set(d.matches.map((x: any) => x.task + '/' + x.attempt));
    expect(groups.size, '两个 attempt 各至少一组').toBeGreaterThanOrEqual(2);
    for (const x of d.matches) {
      expect(typeof x.task).toBe('string');
      expect(typeof x.attempt).toBe('string');
      expect(typeof x.path).toBe('string');
      expect(/\.(md|txt|log|json|jsonl)$/.test(x.path), '路径只用 .md/.txt/.log/.json/.jsonl：' + x.path).toBe(true);
      expect(Number.isInteger(x.line) && x.line >= 1).toBe(true);
      expect(typeof x.text).toBe('string');
      expect(x.text.length).toBeLessThanOrEqual(200);
      expect(new RegExp(PATTERN).test(x.text), '摘录应命中固定模式：' + x.text).toBe(true);
    }
  });

  it('按 max 截成前 max 条并置 truncated；恰好等于总数时不截断（有第 max+1 条才算）', async () => {
    const m = await readers();
    setMock('data');
    const full = (await m.searchLogs(PATTERN, null, 500)).data;
    const total = full.matches.length;
    expect(total).toBeGreaterThanOrEqual(2);
    const one = (await m.searchLogs(PATTERN, null, 1)).data;
    expect(one.matches).toEqual(full.matches.slice(0, 1));
    expect(one.truncated).toBe(true);
    const exact = (await m.searchLogs(PATTERN, null, total)).data;
    expect(exact.matches.length).toBe(total);
    expect(exact.truncated).toBe(false);
    const less = (await m.searchLogs(PATTERN, null, total - 1)).data;
    expect(less.matches).toEqual(full.matches.slice(0, total - 1));
    expect(less.truncated).toBe(true);
  });

  it('按 task 过滤：只留该任务的命中、保持顺序；过滤后多于 max 才截断', async () => {
    const m = await readers();
    setMock('data');
    const full = (await m.searchLogs(PATTERN, null, 500)).data;
    const tasks = Array.from(new Set(full.matches.map((x: any) => x.task)));
    expect(tasks.length).toBeGreaterThanOrEqual(1);
    for (const t of tasks) {
      const want = full.matches.filter((x: any) => x.task === t);
      const got = await m.searchLogs(PATTERN, t, 500);
      expect(got.ok).toBe(true);
      expect(got.data.matches).toEqual(want);
      expect(got.data.truncated).toBe(false);
      if (want.length >= 2) {
        const cut = (await m.searchLogs(PATTERN, t, 1)).data;
        expect(cut.matches).toEqual(want.slice(0, 1));
        expect(cut.truncated).toBe(true);
      }
    }
  });
});

describe('读取函数：历史一条与插件详情的夹具', () => {
  it('历史 42：两键差异；41：本机文件、两个 64 位十六进制 sha256；40：diff 为 null 且 note 疑似凭据', async () => {
    const m = await readers();
    setMock('data');
    const e42 = (await m.getHistoryEntry(42)).data;
    expect(e42.number).toBe(42);
    expect(Array.isArray(e42.diff)).toBe(true);
    expect(e42.diff.length).toBe(2);
    expect(e42.diff.map((k: any) => k.key)).toEqual(['active_preset', 'roles.execution.profile']);
    for (const k of e42.diff) {
      expect(typeof k.key).toBe('string');
      expect('old' in k && 'new' in k).toBe(true);
    }
    const e41 = (await m.getHistoryEntry(41)).data;
    expect(e41.number).toBe(41);
    expect(e41.resource).toBe('local');
    expect(/^[0-9a-f]{64}$/.test(e41.before_sha256)).toBe(true);
    expect(/^[0-9a-f]{64}$/.test(e41.after_sha256)).toBe(true);
    const e40 = (await m.getHistoryEntry(40)).data;
    expect(e40.number).toBe(40);
    expect(e40.diff).toBeNull();
    expect(String(e40.note)).toContain('疑似凭据');
  });

  it('插件详情：三个插件与 plugins.json 一致；docs-checks 权限含 fs.read、fs.write 缺 fs.write，资源两行一致，锁有 generation 与 64 位 lock_sha256', async () => {
    const m = await readers();
    setMock('data');
    for (const id of ['decisions', 'code-change', 'docs-checks']) {
      const r = await m.getPlugin(id);
      expect(r.ok, id).toBe(true);
      expect(r.data.plugin_id).toBe(id);
      expect(Array.isArray(r.data.resources)).toBe(true);
      expect(r.data.lock).toBeTruthy();
    }
    const d = (await m.getPlugin('docs-checks')).data;
    expect(d.permissions).toContain('fs.read');
    expect(d.permissions).toContain('fs.write');
    expect(d.config.missing_permissions).toEqual(['fs.write']);
    expect(d.resources.length).toBe(2);
    for (const r of d.resources) {
      expect(typeof r.path).toBe('string');
      expect(r.status).toBe('一致');
    }
    expect(d.lock.generation).toBeDefined();
    expect(/^[0-9a-f]{64}$/.test(d.lock.lock_sha256)).toBe(true);
  });
});

describe('读取函数：深拷贝', () => {
  it('改返回值不影响下一次读取', async () => {
    const m = await readers();
    setMock('data');
    const a = await m.searchLogs(PATTERN, null, 50);
    const keep = JSON.parse(JSON.stringify(a.data));
    a.data.matches.length = 0;
    a.data.truncated = !a.data.truncated;
    expect((await m.searchLogs(PATTERN, null, 50)).data).toEqual(keep);
    const p = await m.getPlugin('docs-checks');
    const keepP = JSON.parse(JSON.stringify(p.data));
    p.data.permissions.push('x');
    p.data.resources.length = 0;
    expect((await m.getPlugin('docs-checks')).data).toEqual(keepP);
    const h = await m.getHistoryEntry(42);
    const keepH = JSON.parse(JSON.stringify(h.data));
    h.data.diff.length = 0;
    expect((await m.getHistoryEntry(42)).data).toEqual(keepH);
  });
});
"""

# ---------------------------------------------------------------------------
# secrets 探针（D01，长期）
# ---------------------------------------------------------------------------

PROBE_SECRETS = PRELUDE + HOIST + r"""
const SECRETS: any = {
  secrets: [
    { name: 'A_ENV', used_by: [{ kind: 'profile', id: 'p1' }, { kind: 'profile', id: 'p2' }, { kind: 'decisions' }], source: 'env', value: 'sk-LEAK-CANARY-1' },
    { name: 'B_STORE', used_by: [{ kind: 'decisions' }, { kind: 'profile', id: 'p3' }, { kind: 'weird', id: 'w1' }, { kind: 'weird2' }], source: 'credential_store' },
    { name: 'C_FILE', used_by: [{ kind: 'profile', id: 'p1' }, { kind: 'decisions' }, { kind: 'profile', id: 'p2' }], source: 'file' },
    { name: 'D_NONE', used_by: [], source: 'none' },
    { name: 'E_VAULT', used_by: [{ kind: 'profile', id: '（值不显示）' }], source: 'vault' },
    { name: '（疑似凭据的键名）', used_by: [{ kind: 'profile', id: '<redacted>' }], source: 'env' },
  ],
};

async function mountSecrets() {
  over('listSecrets', SECRETS, ['config', 'show']);
  await mountApp('#/secrets?mock=data');
  return tableByLabel('凭据变量');
}

describe('D01 凭据：表', () => {
  it('四列：变量名、用在哪里、来源、操作；没有「值」表头；rowHeight 44；每个变量一行；夹具之外的值文字不出现', async () => {
    const table = await mountSecrets();
    expect(headersOf(table)).toEqual(['变量名', '用在哪里', '来源', '操作']);
    expect(table.getAttribute('data-row-height')).toBe('44');
    expect(bodyRows(table).length).toBe(6);
    expect(headersOf(table).includes('值')).toBe(false);
    expect(Array.from(document.querySelectorAll('th, td')).some((c) => textOf(c) === '值')).toBe(false);
    expect(textOf(document.body)).not.toContain('sk-LEAK-CANARY-1');
    expect(callsOf('listSecrets').length).toBeGreaterThan(0);
  });

  it('变量名：普通名字原样（等宽列）；用在哪里按出现顺序，相邻 profile 合并，决策模型，未知 kind 原样带 id，各段用「、」连接，不相邻的不合并', async () => {
    const table = await mountSecrets();
    const used = (name: string) => textOf(cellsOf(rowByFirstCell(table, name))[1]);
    expect(used('A_ENV')).toBe('profile p1、p2、决策模型');
    expect(used('B_STORE')).toMatch(/^决策模型、profile p3、weird\s*w1、weird2$/);
    expect(used('C_FILE')).toBe('profile p1、决策模型、profile p2');
    for (const name of ['A_ENV', 'B_STORE', 'C_FILE', 'D_NONE', 'E_VAULT']) {
      const c = cellsOf(rowByFirstCell(table, name))[0];
      expect(c.querySelector('.tt-masked'), name + ' 不是遮蔽占位，不套 MaskedValue').toBeNull();
      expect(c.classList.contains('tt-table__mono') || c.querySelector('[class*="mono"]') !== null, name + ' 的变量名应是等宽').toBe(true);
    }
  });

  it('遮蔽占位（逐字等于 7.13 的四个之一）：变量名与 used_by 的 id 用 span.tt-masked（title「内核已遮蔽」，含 LockIcon 14），其余不用', async () => {
    const table = await mountSecrets();
    const nameCell = cellsOf(bodyRows(table).find((r) => textOf(cellsOf(r)[0]).includes('（疑似凭据的键名）')) as HTMLElement)[0];
    const m1 = nameCell.querySelector('span.tt-masked') as HTMLElement;
    expect(m1, '变量名是占位时用 MaskedValue').not.toBeNull();
    expect(textOf(m1)).toBe('（疑似凭据的键名）');
    expect(m1.getAttribute('title')).toBe('内核已遮蔽');
    expect(hasIcon(m1, LockIcon, 14)).toBe(true);
    const e = cellsOf(rowByFirstCell(table, 'E_VAULT'))[1];
    const m2 = e.querySelector('span.tt-masked') as HTMLElement;
    expect(m2, 'used_by 的 id 是占位时用 MaskedValue').not.toBeNull();
    expect(textOf(m2)).toBe('（值不显示）');
    expect(m2.getAttribute('title')).toBe('内核已遮蔽');
    expect(textOf(e)).toContain('profile');
    const f = bodyRows(table).find((r) => textOf(cellsOf(r)[0]).includes('（疑似凭据的键名）')) as HTMLElement;
    const m3 = cellsOf(f)[1].querySelector('span.tt-masked') as HTMLElement;
    expect(m3).not.toBeNull();
    expect(textOf(m3)).toBe('<redacted>');
    expect(document.querySelectorAll('.tt-masked').length).toBe(3);
  });

  it('来源：env 环境变量 success、credential_store 系统凭据库 success + SecretsIcon 14、file 0600 文件 success、none 没有 danger + CircleXIcon 14、其他原样 neutral；标签带 data-source', async () => {
    const table = await mountSecrets();
    const cases: any[] = [
      ['A_ENV', 'env', '环境变量', 'success', null],
      ['B_STORE', 'credential_store', '系统凭据库', 'success', SecretsIcon],
      ['C_FILE', 'file', '0600 文件', 'success', null],
      ['D_NONE', 'none', '没有', 'danger', CircleXIcon],
      ['E_VAULT', 'vault', 'vault', 'neutral', null],
    ];
    for (const [name, src, label, tone, Icon] of cases) {
      const cell = cellsOf(rowByFirstCell(table, name))[2];
      const tag = cell.querySelector('[data-source]') as HTMLElement;
      expect(tag, name + ' 的来源标签应带 data-source').not.toBeNull();
      expect(tag.getAttribute('data-source')).toBe(src);
      expect(textOf(tag)).toBe(label);
      expect(tag.getAttribute('data-tone')).toBe(tone);
      if (Icon) expect(hasIcon(tag, Icon, 14), name + ' 的图标').toBe(true);
      else expect(tag.querySelector('svg'), name + ' 不带图标').toBeNull();
    }
  });

  it('操作：每行一个 [录入…]，DisabledAction（secondary、sm、带 14 的图标），disabled；单元格里没有可聚焦的元素；没有值列', async () => {
    const table = await mountSecrets();
    const rows = bodyRows(table);
    for (const r of rows) {
      const cell = cellsOf(r)[3];
      const btn = buttonByText(cell, '录入…');
      expect(btn.disabled).toBe(true);
      expect(btn.getAttribute('data-variant')).toBe('secondary');
      expect(btn.getAttribute('data-size')).toBe('sm');
      const svg = btn.querySelector('svg');
      expect(svg, '[录入…] 带 ExternalLinkIcon').not.toBeNull();
      expect((svg as Element).getAttribute('width')).toBe('14');
      expect((svg as Element).getAttribute('height')).toBe('14');
    }
    expect(table.querySelectorAll('tbody td a, tbody td input, tbody td select, tbody td [tabindex]').length).toBe(0);
    expect(table.querySelectorAll('tbody td button:not(:disabled)').length).toBe(0);
    expect(cellsOf(rows[0]).length).toBe(4);
  });
});

describe('D01 凭据：说明、小节与视图结构', () => {
  it('表下一条不可关的 info 说明（不是 Banner，没有关闭钮与 role），表后是「“来源”标签」小节，列出四个标签', async () => {
    const table = await mountSecrets();
    const root = viewRoot('secrets');
    const note = smallestWith(root, '录入只在单独的一次性页面里进行，值直接存进系统凭据库；这个界面拿不到值。') as HTMLElement;
    expect(note, '表下应有说明「录入只在单独的一次性页面里进行，值直接存进系统凭据库；这个界面拿不到值。」').toBeTruthy();
    expect(note.closest('.tt-banner')).toBeNull();
    expect(root.querySelector('button[aria-label="关闭提示"]')).toBeNull();
    expect(root.querySelector('[role="status"], [role="alert"]')).toBeNull();
    expect(table.compareDocumentPosition(note) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const sections = Array.from(root.querySelectorAll('section'));
    const sec = sections.find((s) => {
      const id = s.getAttribute('aria-labelledby');
      const h = id ? document.getElementById(id) : null;
      return !!h && h.tagName === 'H2' && textOf(h).includes('来源') && textOf(h).includes('标签');
    });
    expect(sec, '应有「来源」标签小节：section 的 aria-labelledby 指向含「来源」「标签」的 h2').toBeTruthy();
    const text = textOf(sec as Element);
    for (const label of ['环境变量', '系统凭据库', '0600 文件', '没有']) expect(text).toContain(label);
    expect(table.compareDocumentPosition(sec as Element) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('视图根 data-page=secrets：不写 data-page-state、不渲染 h1、没有内联 style；每个 section 的 aria-labelledby 指向存在的 h2；整页恰一个 data-page-state', async () => {
    await mountSecrets();
    const root = viewRoot('secrets');
    expect(root.hasAttribute('data-page-state')).toBe(false);
    expect(root.querySelector('[data-page-state]')).toBeNull();
    expect(root.querySelector('h1')).toBeNull();
    expect(root.querySelector('[style]')).toBeNull();
    for (const s of Array.from(root.querySelectorAll('section'))) {
      const id = s.getAttribute('aria-labelledby');
      expect(id, 'section 应有 aria-labelledby').toBeTruthy();
      const h = document.getElementById(id as string);
      expect(h && h.tagName).toBe('H2');
    }
    pageRoot();
    expect(textOf(document.querySelector('h1'))).toBe('凭据');
  });

  it('说明原文、刷新钮叫「重新检查」且没有文字恰为「刷新」的按钮', async () => {
    await mountSecrets();
    expect(textOf(document.querySelector('.tt-page__desc') || document.body)).toContain('这里只显示每个环境变量在哪一层找到，从不显示值');
    expect(maybeButton(document.body, '重新检查')).not.toBeNull();
    expect(maybeButton(document.body, '刷新')).toBeNull();
  });
});
"""

# ---------------------------------------------------------------------------
# logs 探针（D02 检索，D03 用量，长期）
# ---------------------------------------------------------------------------

PROBE_LOGS = PRELUDE + HOIST + r"""
const USAGE: any = {
  executor: {
    attempts: [
      { task: 't-one', attempt: 'attempt-001', requested_model: 'm/one', status: 'known', usage: { input: 1234567, output: 7, cacheRead: 1000, cacheWrite: 0, totalTokens: 1235574 } },
      { task: 't-two', attempt: 'attempt-002', requested_model: 'm/two', status: 'partial', usage: { input: 5, output: 6 } },
      { task: 't-one', attempt: 'attempt-003', requested_model: 'm/two', status: 'unknown', usage: null },
      { task: 't-three', attempt: 'attempt-004', requested_model: 'm/zero', status: 'mystery', usage: null },
    ],
    counts: { known: 2, partial: 1, unknown: 3 },
    skipped_links: 2,
    totals: { input: 7654321, output: 123456, cacheRead: 9876, cacheWrite: 543, totalTokens: 1000000 },
    by_model: [
      { requested_model: 'm/one', known: 1, partial: 0, unknown: 0, usage: { input: 1, output: 1, cacheRead: 0, cacheWrite: 0, totalTokens: 250000 } },
      { requested_model: 'm/two', known: 0, partial: 1, unknown: 2, usage: { input: 2, output: 2, cacheRead: 0, cacheWrite: 0, totalTokens: 333333 } },
      { requested_model: 'm/zero', known: 0, partial: 0, unknown: 1, usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0 } },
    ],
  },
  planner: null,
};
const ATTEMPT_HEADERS = ['任务', 'attempt', '模型', '状态', 'input', 'output', 'cacheRead', 'cacheWrite', '合计'];
const MODEL_HEADERS = ['模型', '回报情况', '占比', 'input', 'output', '合计'];

async function mountLogs(hash = '#/logs?mock=data', usage: any = USAGE) {
  over('getUsage', usage, ['logs', 'usage']);
  const r = await mountApp(hash);
  return r;
}
async function openUsageTab(hash = '#/logs?mock=data', usage: any = USAGE) {
  await mountLogs(hash, usage);
  const tab = Array.from(document.querySelectorAll('[role="tab"]')).find((t) => textOf(t) === '用量') as HTMLElement;
  expect(tab, '应有「用量」页签').toBeTruthy();
  fireEvent.click(tab);
  await settle();
  return document.querySelector('[role="tabpanel"]') as HTMLElement;
}

describe('D03 用量：页签', () => {
  it('Tabs（aria-label 日志与用量）两个页签：检索（缺省选中）、用量；切换不改地址、不重挂载页面；各自的内容互相不出现', async () => {
    await mountLogs();
    const list = document.querySelector('[role="tablist"][aria-label="日志与用量"]');
    expect(list, '应有 Tabs，aria-label=日志与用量').not.toBeNull();
    const tabs = Array.from((list as Element).querySelectorAll('[role="tab"]'));
    expect(tabs.map((t) => textOf(t))).toEqual(['检索', '用量']);
    expect(tabs.map((t) => t.getAttribute('aria-selected'))).toEqual(['true', 'false']);
    expect(document.querySelector('[role="tabpanel"] form button[type="submit"]'), '缺省是检索页签，有检索表单').not.toBeNull();
    const before = pageRoot();
    const hash = window.location.hash;
    fireEvent.click(tabs[1]);
    await settle();
    expect(tabs.map((t) => t.getAttribute('aria-selected'))).toEqual(['false', 'true']);
    expect(window.location.hash, '页签不写进地址').toBe(hash);
    expect(pageRoot(), '页签切换不重挂载页面').toBe(before);
    expect(document.querySelector('[role="tabpanel"] form button[type="submit"]')).toBeNull();
    expect(textOf(document.querySelector('[role="tabpanel"]'))).toContain('合计是下界');
    fireEvent.click(tabs[0]);
    await settle();
    expect(document.querySelector('[role="tabpanel"] form button[type="submit"]')).not.toBeNull();
  });

  it('说明「在全部证据里检索；按 attempt 与模型统计 token」；视图根 data-page=logs 不写 data-page-state、不渲染 h1', async () => {
    await mountLogs();
    expect(textOf(document.body)).toContain('在全部证据里检索；按 attempt 与模型统计 token');
    const root = viewRoot('logs');
    expect(root.hasAttribute('data-page-state')).toBe(false);
    expect(root.querySelector('[data-page-state]')).toBeNull();
    expect(root.querySelector('h1')).toBeNull();
    expect(callsOf('getUsage').length).toBeGreaterThan(0);
  });
});

describe('D03 用量：说明与执行端卡', () => {
  it('顶部固定说明（不是 Banner，没有关闭钮）；合计与 token（下界）、四项数字带千分位、三个计数标签（文字、tone、中文 title）、跳过的链接', async () => {
    const panel = await openUsageTab();
    const text = textOf(panel);
    expect(text).toContain('合计是下界：没有回报的记为未知，不计为 0。');
    const note = smallestWith(panel, '合计是下界') as HTMLElement;
    expect(note, '应有固定说明').toBeTruthy();
    expect(note.closest('.tt-banner')).toBeNull();
    expect(panel.querySelector('button[aria-label="关闭提示"]')).toBeNull();
    expect(text).toContain('1,000,000');
    expect(text).toContain('token（下界）');
    expect(Array.from(panel.querySelectorAll('.tt-num')).some((e) => textOf(e).includes('1,000,000')), '合计数字带 tt-num').toBe(true);
    const pairs: Array<[string, string]> = [['input', '7,654,321'], ['output', '123,456'], ['cacheRead', '9,876'], ['cacheWrite', '543']];
    for (const [k, v] of pairs) {
      expect(new RegExp('(' + k + '\\s*' + v + '|' + v + '\\s*' + k + ')').test(text), k + ' ' + v).toBe(true);
    }
    const checks: Array<[string, string, string]> = [['known 2', 'success', '已回报'], ['partial 1', 'warning', '部分回报'], ['unknown 3', 'neutral', '未回报']];
    for (const [t, tone, title] of checks) {
      const tag = tagWithText(panel, t);
      expect(tag.getAttribute('data-tone')).toBe(tone);
      expect(titleOf(tag)).toBe(title);
    }
    expect(text).toContain('跳过的链接：2');
  });

  it('skipped_links 为 0 时不显示「跳过的链接」', async () => {
    const usage = clone(USAGE);
    usage.executor.skipped_links = 0;
    const panel = await openUsageTab('#/logs?mock=data', usage);
    expect(textOf(panel)).not.toContain('跳过的链接');
  });
});

describe('D03 用量：规划端卡', () => {
  it('planner 为 null：空状态「在设置里指定会话记录目录后统计」加链接 [去设置]，href 当前地址有 mock 时带上、没有时不带', async () => {
    for (const [hash, href] of [
      ['#/logs?mock=data', '#/settings?mock=data'],
      ['#/logs?mock=offline', '#/settings?mock=offline'],
      ['#/logs', '#/settings'],
    ]) {
      const panel = await openUsageTab(hash);
      expect(panel.querySelector('.tt-empty'), hash).not.toBeNull();
      expect(textOf(panel)).toContain('在设置里指定会话记录目录后统计');
      const link = Array.from(panel.querySelectorAll('a')).find((a) => textOf(a) === '去设置') as HTMLAnchorElement;
      expect(link, hash + ' 应有链接 [去设置]').toBeTruthy();
      expect(link.getAttribute('href'), hash).toBe(href);
      cleanup();
    }
  }, 30000);

  it('planner 不为 null：只写一行「规划端用量的显示在后续片接入」，没有空状态与 [去设置]', async () => {
    const usage = clone(USAGE);
    usage.planner = { sessions: 3 };
    const panel = await openUsageTab('#/logs?mock=data', usage);
    expect(textOf(panel)).toContain('规划端用量的显示在后续片接入');
    expect(panel.querySelector('.tt-empty')).toBeNull();
    expect(Array.from(panel.querySelectorAll('a')).some((a) => textOf(a) === '去设置')).toBe(false);
  });
});

describe('D03 用量：按 attempt 表', () => {
  it('列、rowHeight 40；状态 Tag 文字原样、tone 与中文 title（未知值 neutral 无 title）；缺键与 null 显示「未知」，0 显示 0；数字带千分位与 tt-num', async () => {
    const panel = await openUsageTab();
    const table = tableByHeaders(panel, ATTEMPT_HEADERS);
    expect(table.getAttribute('data-row-height')).toBe('40');
    const rows = bodyRows(table);
    expect(rows.length).toBe(4);
    const texts = (r: HTMLElement) => cellsOf(r).map((c) => textOf(c));
    const status = (r: HTMLElement) => cellsOf(r)[3].querySelector('[data-tone]') as HTMLElement;
    expect(texts(rows[0]).filter((_t, i) => i !== 3)).toEqual(['t-one', 'attempt-001', 'm/one', '1,234,567', '7', '1,000', '0', '1,235,574']);
    expect(textOf(status(rows[0]))).toBe('known');
    expect(status(rows[0]).getAttribute('data-tone')).toBe('success');
    expect(titleOf(status(rows[0]))).toBe('已回报');
    expect(texts(rows[1]).filter((_t, i) => i !== 3)).toEqual(['t-two', 'attempt-002', 'm/two', '5', '6', '未知', '未知', '未知']);
    expect(textOf(status(rows[1]))).toBe('partial');
    expect(status(rows[1]).getAttribute('data-tone')).toBe('warning');
    expect(titleOf(status(rows[1]))).toBe('部分回报');
    expect(texts(rows[2]).filter((_t, i) => i !== 3)).toEqual(['t-one', 'attempt-003', 'm/two', '未知', '未知', '未知', '未知', '未知']);
    expect(textOf(status(rows[2]))).toBe('unknown');
    expect(status(rows[2]).getAttribute('data-tone')).toBe('neutral');
    expect(titleOf(status(rows[2]))).toBe('未回报');
    expect(textOf(status(rows[3]))).toBe('mystery');
    expect(status(rows[3]).getAttribute('data-tone')).toBe('neutral');
    expect(status(rows[3]).getAttribute('title') || '').toBe('');
    for (const r of rows) {
      for (const i of [4, 5, 6, 7, 8]) expect(hasClass(cellsOf(r)[i], 'tt-num'), '数字列带 tt-num').toBe(true);
    }
  });

  it('attempts 为空：写「还没有执行端的用量记录」', async () => {
    const usage = clone(USAGE);
    usage.executor.attempts = [];
    const panel = await openUsageTab('#/logs?mock=data', usage);
    expect(textOf(panel)).toContain('还没有执行端的用量记录');
  });
});

describe('D03 用量：按模型表', () => {
  it('列；回报情况写成「known a · partial b · unknown c」；占比一位小数加 %；条宽等于占比的内联 style；合计带千分位与 tt-num', async () => {
    const panel = await openUsageTab();
    const table = tableByHeaders(panel, MODEL_HEADERS);
    expect(table.getAttribute('data-row-height')).toBe('40');
    const rows = bodyRows(table);
    expect(rows.length).toBe(3);
    const want: Array<[string, string, string, number, string]> = [
      ['m/one', 'known 1 · partial 0 · unknown 0', '25.0%', 25, '250,000'],
      ['m/two', 'known 0 · partial 1 · unknown 2', '33.3%', 33.3, '333,333'],
      ['m/zero', 'known 0 · partial 0 · unknown 1', '0.0%', 0, '0'],
    ];
    rows.forEach((r, i) => {
      const cells = cellsOf(r);
      expect(textOf(cells[0])).toBe(want[i][0]);
      expect(textOf(cells[1])).toBe(want[i][1]);
      expect(textOf(cells[2])).toContain(want[i][2]);
      const bars = Array.from(r.querySelectorAll('[style]')) as HTMLElement[];
      if (want[i][3] > 0) {
        expect(bars.length, want[i][0] + ' 恰有一个内联 style（占比条）').toBe(1);
        expect(bars[0].style.length, '内联 style 只写宽度').toBe(1);
        const w = bars[0].style.width;
        expect(w.endsWith('%'), '条宽是百分比：' + w).toBe(true);
        expect(Math.abs(parseFloat(w) - want[i][3])).toBeLessThan(0.2);
      } else {
        expect(bars.length, want[i][0] + ' 至多一个内联 style').toBeLessThanOrEqual(1);
      }
      expect(textOf(cells[5])).toBe(want[i][4]);
      for (const k of [3, 4, 5]) expect(hasClass(cells[k], 'tt-num')).toBe(true);
    });
    expect(hasClass(cellsOf(rows[0])[2], 'tt-num')).toBe(true);
  });

  it('分母（totals.totalTokens）为 0 时占比显示「—」；整页内联 style 只出现在按模型表里', async () => {
    const usage = clone(USAGE);
    usage.executor.totals.totalTokens = 0;
    const panel = await openUsageTab('#/logs?mock=data', usage);
    const rows = bodyRows(tableByHeaders(panel, MODEL_HEADERS));
    for (const r of rows) {
      const t = textOf(cellsOf(r)[2]);
      expect(t).toContain('—');
      expect(t).not.toContain('%');
    }
    const root = viewRoot('logs');
    const table = tableByHeaders(panel, MODEL_HEADERS);
    for (const el of Array.from(root.querySelectorAll('[style]'))) expect(table.contains(el), '内联 style 只在占比条上').toBe(true);
  });

  it('by_model 为空：写「还没有按模型的统计」', async () => {
    const usage = clone(USAGE);
    usage.executor.by_model = [];
    const panel = await openUsageTab('#/logs?mock=data', usage);
    expect(textOf(panel)).toContain('还没有按模型的统计');
  });
});

// ---------------------------------------------------------------------------
// 检索
// ---------------------------------------------------------------------------

const RESULT: any = {
  matches: [
    { task: 'ta', attempt: 'attempt-001', path: 'a/x.md', line: 3, text: 'first logs_cat here' },
    { task: 'tb', attempt: 'attempt-009', path: 'b.log', line: 10, text: 'logs cat second' },
    { task: 'ta', attempt: 'attempt-001', path: 'c.txt', line: 4, text: 'third logs_cat and logs cat' },
    { task: 'ta', attempt: 'attempt-002', path: 'd.json', line: 1, text: 'fourth' },
  ],
  truncated: true,
  skipped_links: 2,
  skipped_large: 3,
};
const SEARCH_CMD = ['logs', 'search', 'q'];

function searchForm(): HTMLFormElement {
  const btn = Array.from(document.querySelectorAll('[role="tabpanel"] button[type="submit"]'))[0];
  expect(btn, '检索页签里应有 type=submit 的 [检索]').toBeTruthy();
  const form = (btn as HTMLElement).closest('form');
  expect(form, '[检索] 应在 form 里').not.toBeNull();
  return form as HTMLFormElement;
}
const qBox = (f: HTMLFormElement) => f.querySelector('input:not([type="number"])') as HTMLInputElement;
const maxBox = (f: HTMLFormElement) => f.querySelector('input[type="number"]') as HTMLInputElement;
const taskBox = (f: HTMLFormElement) => f.querySelector('select') as HTMLSelectElement;
const submitBtn = (f: HTMLFormElement) => f.querySelector('button[type="submit"]') as HTMLButtonElement;
function setValue(el: Element, v: string) {
  fireEvent.change(el, { target: { value: v } });
}
async function submit(f: HTMLFormElement) {
  fireEvent.submit(f);
  await settle();
}
async function searchWith(q: string, max: string | null, result: any, cmd: string[] = SEARCH_CMD) {
  hoisted.overrides.searchLogs = () => Promise.resolve(result.ok === false ? result : ok(result, cmd));
  const f = searchForm();
  setValue(qBox(f), q);
  if (max !== null) setValue(maxBox(f), max);
  await submit(f);
}
function panelText(): string {
  return textOf(document.querySelector('[role="tabpanel"]'));
}

describe('D02 检索：表单与校验', () => {
  it('表单：检索词（初值空）、任务（全部任务加按出现顺序去重的任务名）、最多条数（初值 50）、[检索]；检索前的说明', async () => {
    await mountLogs();
    const f = searchForm();
    expect(qBox(f)).not.toBeNull();
    expect(qBox(f).value).toBe('');
    expect(maxBox(f).value).toBe('50');
    expect(maxBox(f).getAttribute('min')).toBe('1');
    const sel = taskBox(f);
    expect(Array.from(sel.options).map((o) => o.textContent)).toEqual(['全部任务', 't-one', 't-two', 't-three']);
    expect(Array.from(sel.options).map((o) => o.value)[0]).toBe('');
    expect(sel.value).toBe('');
    const labels = Array.from(f.querySelectorAll('label')).map((l) => textOf(l));
    for (const l of ['检索', '任务', '最多条数']) expect(labels).toContain(l);
    expect(textOf(submitBtn(f))).toBe('检索');
    expect(panelText()).toContain('输入 Python 正则表达式后检索；全量检索可能要半分钟左右，建议先选任务缩小范围。');
    expect(panelText()).toContain('Python 正则表达式');
    expect(callsOf('searchLogs').length).toBe(0);
  });

  it('空检索词（含只有空白）：不调用读取函数，检索框下显示「先输入要检索的内容」', async () => {
    await mountLogs();
    const f = searchForm();
    for (const v of ['', '   ']) {
      setValue(qBox(f), v);
      await submit(f);
      expect(callsOf('searchLogs').length, '检索词「' + v + '」不该调用读取函数').toBe(0);
      const err = f.querySelector('.tt-field__error');
      expect(err && textOf(err)).toBe('先输入要检索的内容');
      expect(qBox(f).getAttribute('aria-invalid')).toBe('true');
    }
  });

  it('非法最多条数（0、负数、小数、空）：不调用读取函数，显示「最多条数必须是不小于 1 的整数」；改对后恰好调用一次', async () => {
    await mountLogs();
    const f = searchForm();
    setValue(qBox(f), 'logs[_ ]cat');
    for (const v of ['0', '-3', '2.5', '']) {
      setValue(maxBox(f), v);
      await submit(f);
      expect(callsOf('searchLogs').length, '最多条数「' + v + '」不该调用读取函数').toBe(0);
      const err = Array.from(f.querySelectorAll('.tt-field__error')).map((e) => textOf(e));
      expect(err).toContain('最多条数必须是不小于 1 的整数');
    }
    hoisted.overrides.searchLogs = () => Promise.resolve(ok(RESULT, SEARCH_CMD));
    setValue(maxBox(f), '5');
    await submit(f);
    expect(callsOf('searchLogs').length).toBe(1);
  });

  it('提交：读取函数恰好调用一次，参数是（检索词、任务或 null、数字上限）', async () => {
    await mountLogs();
    await searchWith('logs[_ ]cat', null, RESULT);
    expect(callsOf('searchLogs').length).toBe(1);
    expect(callsOf('searchLogs')[0]).toEqual(['logs[_ ]cat', null, 50]);
    const f = searchForm();
    setValue(taskBox(f), 't-two');
    setValue(maxBox(f), '7');
    await submit(f);
    expect(callsOf('searchLogs').length).toBe(2);
    expect(callsOf('searchLogs')[1]).toEqual(['logs[_ ]cat', 't-two', 7]);
  });
});

describe('D02 检索：读取中与过期回应', () => {
  it('读取中 [检索] 转圈（aria-busy、disabled、「正在检索…」、tt-spin），回应到了恢复', async () => {
    await mountLogs();
    const d = deferred();
    hoisted.overrides.searchLogs = () => d.promise;
    const f = searchForm();
    setValue(qBox(f), 'q1');
    await submit(f);
    const btn = submitBtn(f);
    expect(btn.getAttribute('aria-busy')).toBe('true');
    expect(btn.disabled).toBe(true);
    expect(textOf(btn)).toBe('正在检索…');
    expect(btn.querySelector('svg.tt-spin')).not.toBeNull();
    await act(async () => { d.resolve(ok(RESULT, SEARCH_CMD)); });
    expect(submitBtn(f).getAttribute('aria-busy')).toBeNull();
    expect(submitBtn(f).disabled).toBe(false);
    expect(textOf(submitBtn(f))).toBe('检索');
  });

  it('只认最后一次请求：旧回应后到、旧回应先到，都不覆盖新结果', async () => {
    for (const oldFirst of [false, true]) {
      await mountLogs();
      const d1 = deferred();
      const d2 = deferred();
      let n = 0;
      hoisted.overrides.searchLogs = () => (++n === 1 ? d1.promise : d2.promise);
      const f = searchForm();
      setValue(qBox(f), 'first');
      await submit(f);
      setValue(qBox(f), 'second');
      await submit(f);
      const resA = ok({ matches: [{ task: 'ta', attempt: 'attempt-001', path: 'a.md', line: 1, text: 'AAA-OLD' }], truncated: false, skipped_links: 0, skipped_large: 0 }, SEARCH_CMD);
      const resB = ok({ matches: [{ task: 'tb', attempt: 'attempt-002', path: 'b.md', line: 2, text: 'BBB-NEW' }], truncated: false, skipped_links: 0, skipped_large: 0 }, SEARCH_CMD);
      if (oldFirst) {
        await act(async () => { d1.resolve(resA); });
        expect(panelText(), '旧回应先到，不显示').not.toContain('AAA-OLD');
        await act(async () => { d2.resolve(resB); });
      } else {
        await act(async () => { d2.resolve(resB); });
        await act(async () => { d1.resolve(resA); });
      }
      expect(panelText()).toContain('BBB-NEW');
      expect(panelText(), '旧回应不能覆盖新结果').not.toContain('AAA-OLD');
      cleanup();
    }
  }, 30000);

  it('卸载后回应到达：不抛错', async () => {
    const r = await mountLogs();
    const d = deferred();
    hoisted.overrides.searchLogs = () => d.promise;
    const f = searchForm();
    setValue(qBox(f), 'q1');
    await submit(f);
    r.unmount();
    await act(async () => { d.resolve(ok(RESULT, SEARCH_CMD)); });
    expect(document.querySelector('[data-page="logs"]')).toBeNull();
  });
});

describe('D02 检索：结果区', () => {
  it('ok 为假：出错块写命令（参数用空格连接）与退出码，messages 放在 pre 里按纯文本显示', async () => {
    await mountLogs();
    await searchWith('q1', null, bad(['ERROR 坏 <b>x</b>', '第二行'], ['logs', 'search', 'q1']));
    expect(panelText()).toContain('没能检索：命令（logs search q1）返回退出码 2。');
    const pre = document.querySelector('[role="tabpanel"] pre') as HTMLElement;
    expect(pre, 'messages 放在 pre 里').not.toBeNull();
    expect(pre.textContent).toContain('ERROR 坏 <b>x</b>');
    expect(pre.textContent).toContain('第二行');
    expect(pre.querySelector('b')).toBeNull();
    expect(panelText()).not.toContain('摘录取自脱敏之后的文本');
  });

  it('有结果：头部「结果」与「N 条 · 上限 M」（M 是这次提交的上限）；说明行顺序：只显示前 M 条匹配、太大没搜、跳过的链接、固定说明', async () => {
    await mountLogs();
    await searchWith('logs[_ ]cat', '7', RESULT);
    const t = panelText();
    expect(t).toContain('结果');
    expect(t).toContain('4 条 · 上限 7');
    const order = ['只显示前 7 条匹配', '有 3 个文件太大或读不出来，没有搜；请用 CLI 查看', '跳过的链接：2', '摘录取自脱敏之后的文本'].map((s) => t.indexOf(s));
    order.forEach((i, k) => expect(i, '说明行 ' + k).toBeGreaterThanOrEqual(0));
    expect(order[0]).toBeLessThan(order[1]);
    expect(order[1]).toBeLessThan(order[2]);
    expect(order[2]).toBeLessThan(order[3]);
    expect(t).not.toContain('只显示前 4 条匹配');
    expect(t).toContain('被遮蔽的值搜不到是正常的');
  });

  it('没有截断、跳过为 0：不显示三条提示，固定说明照常；空 matches 写「没有匹配的行」且说明行照常', async () => {
    await mountLogs();
    await searchWith('logs[_ ]cat', null, { ...RESULT, truncated: false, skipped_links: 0, skipped_large: 0 });
    let t = panelText();
    expect(t).not.toContain('只显示前');
    expect(t).not.toContain('太大或读不出来');
    expect(t).not.toContain('跳过的链接');
    expect(t).toContain('摘录取自脱敏之后的文本');
    await searchWith('logs[_ ]cat', null, { matches: [], truncated: false, skipped_links: 0, skipped_large: 1 });
    t = panelText();
    expect(t).toContain('没有匹配的行');
    expect(t).toContain('有 1 个文件太大或读不出来，没有搜；请用 CLI 查看');
    expect(t).toContain('摘录取自脱敏之后的文本');
  });

  it('分组：按 (task, attempt) 首次出现的顺序，组头「task · attempt」与「N 处」，每条「path:line」与摘录', async () => {
    await mountLogs();
    await searchWith('logs[_ ]cat', null, RESULT);
    const t = panelText();
    const heads = ['ta · attempt-001', 'tb · attempt-009', 'ta · attempt-002'].map((s) => t.indexOf(s));
    heads.forEach((i, k) => expect(i, '组头 ' + k).toBeGreaterThanOrEqual(0));
    expect(heads[0]).toBeLessThan(heads[1]);
    expect(heads[1]).toBeLessThan(heads[2]);
    expect(/ta · attempt-001\s*2 处/.test(t)).toBe(true);
    expect(/tb · attempt-009\s*1 处/.test(t)).toBe(true);
    expect(/ta · attempt-002\s*1 处/.test(t)).toBe(true);
    const items = ['a/x.md:3', 'c.txt:4', 'b.log:10', 'd.json:1'].map((s) => t.indexOf(s));
    items.forEach((i, k) => expect(i, '条目 ' + k).toBeGreaterThanOrEqual(0));
    for (let k = 1; k < items.length; k += 1) expect(items[k - 1]).toBeLessThan(items[k]);
    expect(leafWithText(document.body, 'a/x.md:3'), 'path:line 单独成行').not.toBeNull();
    expect(Array.from(document.querySelectorAll('*')).some((e) => textOf(e) === 'first logs_cat here'), '摘录整行文字不变').toBe(true);
  });

  it('结果条目不可点（Q4）：结果区没有链接、没有可聚焦元素，页签里只有 [检索] 一个按钮', async () => {
    await mountLogs();
    await searchWith('logs[_ ]cat', null, RESULT);
    const panel = document.querySelector('[role="tabpanel"]') as HTMLElement;
    expect(panel.querySelectorAll('a').length).toBe(0);
    expect(panel.querySelectorAll('[role="button"], [tabindex]').length).toBe(0);
    expect(panel.querySelectorAll('button').length).toBe(1);
  });
});

describe('D02 检索：高亮', () => {
  it('命中段包在 mark 里（全是文本节点），整行文字不变', async () => {
    await mountLogs();
    await searchWith('logs[_ ]cat', null, RESULT);
    const marks = Array.from(document.querySelectorAll('[role="tabpanel"] mark'));
    // 分组顺序：ta·001（第 1、3 条）、tb·009（第 2 条）、ta·002（第 4 条）
    expect(marks.map((m) => textOf(m))).toEqual(['logs_cat', 'logs_cat', 'logs cat', 'logs cat']);
    for (const m of marks) expect(m.children.length).toBe(0);
    expect(Array.from(document.querySelectorAll('*')).some((e) => textOf(e) === 'third logs_cat and logs cat')).toBe(true);
  });

  it('JS 编译失败（Python 独有的语法）与带量词的分组：不高亮，整行照常显示', async () => {
    for (const q of ['(?P<n>logs)', '(logs)+', '(logs)*', '(logs)?', '(logs){1}', '(l|x)+']) {
      await mountLogs();
      await searchWith(q, null, RESULT);
      expect(document.querySelectorAll('[role="tabpanel"] mark').length, q + ' 不高亮').toBe(0);
      expect(panelText(), q + ' 整行照常显示').toContain('first logs_cat here');
      expect(panelText()).toContain('a/x.md:3');
      cleanup();
    }
  }, 60000);

  it('空匹配跳过（不卡死）；带量词的分组遇上会回溯的长行也在 1.5 秒内完成', async () => {
    await mountLogs();
    await searchWith('z*', null, RESULT);
    expect(document.querySelectorAll('[role="tabpanel"] mark').length).toBe(0);
    expect(panelText()).toContain('first logs_cat here');
    cleanup();
    await mountLogs();
    const nasty = { ...RESULT, matches: [{ task: 'ta', attempt: 'attempt-001', path: 'n.md', line: 1, text: 'a'.repeat(60) + '!' }] };
    const t0 = performance.now();
    await searchWith('(a+)+$', null, nasty);
    expect(performance.now() - t0).toBeLessThan(1500);
    expect(document.querySelectorAll('[role="tabpanel"] mark').length).toBe(0);
    expect(panelText()).toContain('a'.repeat(60) + '!');
  }, 30000);

  it('没有带量词分组的正则照常高亮', async () => {
    await mountLogs();
    await searchWith('logs[_ ]cat+', null, RESULT);
    expect(document.querySelectorAll('[role="tabpanel"] mark').length).toBeGreaterThan(0);
  });
});

describe('D02 检索：不可信内容只按文本显示', () => {
  it('摘录、路径、任务名里的 <img src=x onerror=…>、<script> 与标签：DOM 里没有对应元素，字面文字都在', async () => {
    await mountLogs();
    const evil = {
      matches: [
        { task: 'ta', attempt: 'attempt-001', path: 'x.md', line: 1, text: '<img src=x onerror=alert(1)> logs_cat <script>window.__x=1</script>' },
        { task: '<i>t</i>', attempt: '<u>a</u>', path: '<b>p</b>.md', line: 2, text: '<b>bold</b> logs cat' },
      ],
      truncated: false, skipped_links: 0, skipped_large: 0,
    };
    await searchWith('logs[_ ]cat', null, evil);
    const panel = document.querySelector('[role="tabpanel"]') as HTMLElement;
    expect(panel.querySelector('img, script, b, i, u, [onerror]')).toBeNull();
    expect((window as any).__x).toBeUndefined();
    const t = panelText();
    expect(t).toContain('<img src=x onerror=alert(1)>');
    expect(t).toContain('<script>window.__x=1</script>');
    expect(t).toContain('<i>t</i> · <u>a</u>');
    expect(t).toContain('<b>p</b>.md:2');
    expect(t).toContain('<b>bold</b>');
  });
});
"""

# ---------------------------------------------------------------------------
# plugins 探针（D04 表，D05 抽屉）
# ---------------------------------------------------------------------------

PROBE_PLUGINS = PRELUDE + HOIST + DRAWER_KIT + r"""
const LIST: any = {
  plugins_root_link: false,
  plugins: [
    { id: 'alpha', version: '1.2.3', enabled: '启用', lock: '一致', resource: '一致', missing: [], status: 'READY', reason: '' },
    { id: 'beta', version: '0.1.0', enabled: '停用', lock: '漂移', resource: '不一致', missing: ['fs.write', 'net.http'], status: 'DRIFT', reason: '锁与内容不一致' },
    { id: 'gamma', version: '2.0.0', enabled: '不限制', lock: '无效：manifest 读不出来', resource: '-', missing: [], status: 'BLOCKED', reason: '被阻塞' },
    { id: 'delta', version: '3.0.0', enabled: '是', lock: '其他怪值', resource: '一致', missing: [], status: 'WEIRD', reason: '' },
    { id: 'eps', version: '4.0.0', enabled: '否', lock: '一致', resource: '一致', missing: [], status: 'READY', reason: '' },
    { id: 'zeta', version: '5.0.0', enabled: '怪值', lock: '一致', resource: '一致', missing: [], status: 'READY', reason: '' },
  ],
  not_installed: ['ghost-plugin'],
  problems: ['无效：链接 plugins'],
};
function showFor(id: string) {
  const row = LIST.plugins.find((p: any) => p.id === id);
  return {
    plugin_id: id, lock_status: row.lock, resource_status: row.resource, problems: [],
    version: row.version, api_version: '1', capabilities: ['review', 'docs'],
    permissions: ['fs.read', 'fs.write', 'net.http'], platforms: ['windows', 'linux'], depends_on: [], conflicts: ['old-plugin'],
    checks: ['CHECKS-CANARY-1'],
    lock: { generation: 7, lock_sha256: HASH_LOCK },
    resources: [
      { path: 'manifest.json', id: 'manifest', sha256: HASH_A, status: '一致', detail: '' },
      { path: 'checks/headings.py', id: 'headings', sha256: HASH_B, status: '漂移', detail: '内容变了' },
    ],
    config: { enabled: null, allowed_permissions: ['fs.read'], missing_permissions: row.missing },
  };
}
function installPlugins(list: any = LIST) {
  over('getPlugins', list, ['plugins', 'list']);
  hoisted.overrides.getPlugin = (id: string) => Promise.resolve(ok(showFor(id), ['plugins', 'show', id]));
}
async function mountPluginsTable(list: any = LIST) {
  installPlugins(list);
  await mountApp('#/plugins?mock=data');
  return tableByLabel('插件');
}
function rowOf(table: Element, id: string) {
  return rowByFirstCell(table, id);
}
function sectionByTitle(root: ParentNode, title: string): HTMLElement {
  const hit = Array.from(root.querySelectorAll('section')).find((s) => {
    const id = s.getAttribute('aria-labelledby');
    const h = id ? document.getElementById(id) : null;
    return !!h && h.tagName === 'H2' && textOf(h) === title;
  });
  expect(hit, '应有 section，aria-labelledby 指向 h2「' + title + '」').toBeTruthy();
  return hit as HTMLElement;
}
describe('D04 插件表', () => {
  it('表 aria-label=插件、rowHeight 40、八列（ID 版本 启用 锁 资源 缺的权限 状态 操作）；视图根 data-page=plugins；说明原文；[核对全部] 禁用', async () => {
    const table = await mountPluginsTable();
    const h = headersOf(table);
    expect(h.length).toBe(8);
    expect(h[0]).toBe('ID');
    expect(h[1]).toBe('版本');
    ['启用', '锁', '资源', '缺', '状态', '操作'].forEach((s, i) => expect(h[i + 2]).toContain(s));
    expect(table.getAttribute('data-row-height')).toBe('40');
    expect(bodyRows(table).length).toBe(6);
    const root = viewRoot('plugins');
    expect(root.hasAttribute('data-page-state')).toBe(false);
    expect(root.querySelector('h1')).toBeNull();
    expect(textOf(document.body)).toContain('启停前先预览权限变化；锁与资源哈希由内核核对');
    const btn = buttonByText(document.body, '核对全部');
    expect(btn.disabled).toBe(true);
    expect(btn.getAttribute('data-variant')).toBe('secondary');
    expect(btn.getAttribute('data-size')).toBe('md');
    expect(hasIcon(btn, ListChecksIcon, 16)).toBe(true);
  });

  it('ID 与版本：原样，版本带 tt-num', async () => {
    const table = await mountPluginsTable();
    for (const p of LIST.plugins) {
      const cells = cellsOf(rowOf(table, p.id));
      expect(textOf(cells[0])).toBe(p.id);
      expect(textOf(cells[1])).toBe(p.version);
      expect(hasClass(cells[1], 'tt-num'), p.id + ' 版本带 tt-num').toBe(true);
      for (const i of [0, 1]) {
        expect(cells[i].classList.contains('tt-table__mono') || cells[i].querySelector('[class*="mono"]') !== null, p.id + ' 第 ' + i + ' 列等宽').toBe(true);
      }
    }
  });

  it('启用：启用/是 brand、停用/否 neutral、不限制（title「没有配置启用名单」）、其他值原样 neutral', async () => {
    const table = await mountPluginsTable();
    const enable = (id: string) => cellsOf(rowOf(table, id))[2];
    const want: Array<[string, string, string]> = [['alpha', '启用', 'brand'], ['beta', '停用', 'neutral'], ['delta', '是', 'brand'], ['eps', '否', 'neutral'], ['zeta', '怪值', 'neutral']];
    for (const [id, text, tone] of want) {
      const tag = enable(id).querySelector('[data-tone]') as HTMLElement;
      expect(tag, id).not.toBeNull();
      expect(textOf(tag)).toBe(text);
      expect(tag.getAttribute('data-tone'), id).toBe(tone);
    }
    expect(textOf(enable('gamma'))).toBe('不限制');
    expect(titleOf(enable('gamma'))).toBe('没有配置启用名单');
  });

  it('锁与资源：一致 success + CheckIcon 12；漂移/不一致 warning + TriangleAlertIcon 12；以「无效」开头 danger + CircleXIcon 12；「-」显示「—」；其他 warning；非一致时 title 为 reason', async () => {
    const table = await mountPluginsTable();
    const cell = (id: string, i: number) => cellsOf(rowOf(table, id))[i];
    for (const [id, i] of [['alpha', 3], ['alpha', 4], ['eps', 3]] as Array<[string, number]>) {
      const tag = cell(id, i).querySelector('[data-tone]') as HTMLElement;
      expect(textOf(tag)).toBe('一致');
      expect(tag.getAttribute('data-tone')).toBe('success');
      expect(hasIcon(tag, CheckIcon, 12), id + ' 一致带 CheckIcon 12').toBe(true);
    }
    const lock = cell('beta', 3).querySelector('[data-tone]') as HTMLElement;
    expect(textOf(lock)).toBe('漂移');
    expect(lock.getAttribute('data-tone')).toBe('warning');
    expect(hasIcon(lock, TriangleAlertIcon, 12)).toBe(true);
    expect(titleOf(cell('beta', 3))).toBe('锁与内容不一致');
    const res = cell('beta', 4).querySelector('[data-tone]') as HTMLElement;
    expect(textOf(res)).toBe('不一致');
    expect(res.getAttribute('data-tone')).toBe('warning');
    expect(hasIcon(res, TriangleAlertIcon, 12)).toBe(true);
    expect(titleOf(cell('beta', 4))).toBe('锁与内容不一致');
    const inv = cell('gamma', 3).querySelector('[data-tone]') as HTMLElement;
    expect(textOf(inv)).toBe('无效：manifest 读不出来');
    expect(inv.getAttribute('data-tone')).toBe('danger');
    expect(hasIcon(inv, CircleXIcon, 12)).toBe(true);
    expect(titleOf(cell('gamma', 3))).toBe('被阻塞');
    expect(textOf(cell('gamma', 4))).toBe('—');
    expect(cell('gamma', 4).querySelector('[data-tone]')).toBeNull();
    const other = cell('delta', 3).querySelector('[data-tone]') as HTMLElement;
    expect(textOf(other)).toBe('其他怪值');
    expect(other.getAttribute('data-tone')).toBe('warning');
  });

  it('缺的权限：每项一个 danger 的 Tag，没有写「—」', async () => {
    const table = await mountPluginsTable();
    const beta = cellsOf(rowOf(table, 'beta'))[5];
    const tags = tagsIn(beta);
    expect(tags.map((t) => textOf(t))).toEqual(['fs.write', 'net.http']);
    tags.forEach((t) => expect(t.getAttribute('data-tone')).toBe('danger'));
    const alpha = cellsOf(rowOf(table, 'alpha'))[5];
    expect(textOf(alpha)).toBe('—');
    expect(tagsIn(alpha).length).toBe(0);
  });

  it('状态：READY success、DRIFT warning、BLOCKED danger、其他 neutral；reason 非空时接在右侧', async () => {
    const table = await mountPluginsTable();
    const st = (id: string) => cellsOf(rowOf(table, id))[6];
    const want: Array<[string, string, string, string]> = [['alpha', 'READY', 'success', ''], ['beta', 'DRIFT', 'warning', '锁与内容不一致'],
      ['gamma', 'BLOCKED', 'danger', '被阻塞'], ['delta', 'WEIRD', 'neutral', '']];
    for (const [id, text, tone, reason] of want) {
      const tag = st(id).querySelector('[data-tone]') as HTMLElement;
      expect(textOf(tag)).toBe(text);
      expect(tag.getAttribute('data-tone'), id).toBe(tone);
      expect(textOf(st(id)).replace(/\s+/g, ''), id).toBe(text + reason);
    }
  });

  it('操作：启用/是 → [停用…]，停用/否 → [启用…]（ghost、sm、disabled），不限制 → 文字「详情」；单元格里没有可聚焦元素', async () => {
    const table = await mountPluginsTable();
    const act = (id: string) => cellsOf(rowOf(table, id))[7];
    for (const [id, label] of [['alpha', '停用…'], ['delta', '停用…'], ['beta', '启用…'], ['eps', '启用…']]) {
      const btn = buttonByText(act(id), label);
      expect(btn.disabled, id).toBe(true);
      expect(btn.getAttribute('data-variant')).toBe('ghost');
      expect(btn.getAttribute('data-size')).toBe('sm');
    }
    expect(textOf(act('gamma'))).toBe('详情');
    expect(act('gamma').querySelector('button, a, [tabindex]')).toBeNull();
    expect(table.querySelectorAll('tbody td a, tbody td input, tbody td select, tbody td [tabindex]').length).toBe(0);
    expect(table.querySelectorAll('tbody td button:not(:disabled)').length).toBe(0);
  });

  it('表下两个小节：列入但未安装、问题，列出内容；为空写「没有」', async () => {
    await mountPluginsTable();
    const root = viewRoot('plugins');
    expect(textOf(sectionByTitle(root, '列入但未安装'))).toContain('ghost-plugin');
    expect(textOf(sectionByTitle(root, '问题'))).toContain('无效：链接 plugins');
    cleanup();
    await mountPluginsTable({ ...LIST, not_installed: [], problems: [] });
    const root2 = viewRoot('plugins');
    expect(textOf(sectionByTitle(root2, '列入但未安装')).replace('列入但未安装', '').trim()).toBe('没有');
    expect(textOf(sectionByTitle(root2, '问题')).replace('问题', '').trim()).toBe('没有');
  }, 30000);

  it('isEmpty：plugins、not_installed、problems 都为空才算空（空态标题「还没有插件」）；任一非空仍是 data', async () => {
    const empty = { plugins_root_link: false, plugins: [], not_installed: [], problems: [] };
    installPlugins(empty);
    await mountApp('#/plugins?mock=data');
    expect(pageRoot().getAttribute('data-page-state')).toBe('empty');
    expect(textOf(document.body)).toContain('还没有插件');
    cleanup();
    for (const extra of [{ not_installed: ['x'] }, { problems: ['无效：x'] }]) {
      installPlugins({ ...empty, ...extra });
      await mountApp('#/plugins?mock=data');
      expect(pageRoot().getAttribute('data-page-state'), JSON.stringify(extra)).toBe('data');
      cleanup();
    }
  }, 30000);
});

describe('D05 插件抽屉：内容与读取', () => {
  it('点禁用入口不开抽屉（包裹 span 拦下 click 冒泡）；点「详情」那一行（不限制）开抽屉', async () => {
    const table = await mountPluginsTable();
    const btn = buttonByText(cellsOf(rowOf(table, 'alpha'))[7], '停用…');
    fireEvent.click(btn);
    fireEvent.click(btn.closest('.tt-tooltip-wrap') as HTMLElement);
    await settle();
    expect(dialog(), '点禁用钮不该开抽屉').toBeNull();
    expect(callsOf('getPlugin').length).toBe(0);
    fireEvent.click(cellsOf(rowOf(table, 'gamma'))[7]);
    await settle();
    expect(dialog(), '点「详情」所在行应开抽屉').not.toBeNull();
    expect(callsOf('getPlugin').map((c) => c[0])).toEqual(['gamma']);
  });

  it('标题（PluginsIcon 20 + ID + 状态 Tag）、warning 提示条（reason。缺的权限：…。）、READY 时没有提示条；状态非 READY 且 reason 与缺的权限都空时写状态码', async () => {
    const table = await mountPluginsTable();
    await openByEnter(rowOf(table, 'beta'));
    let d = dialog() as HTMLElement;
    const h2 = d.querySelector('h2') as HTMLElement;
    expect(textOf(h2)).toContain('beta');
    expect(hasIcon(h2, PluginsIcon, 20)).toBe(true);
    expect(tagWithText(h2, 'DRIFT').getAttribute('data-tone')).toBe('warning');
    expect(d.querySelector('[data-drawer="plugin"]'), '抽屉内容根 data-drawer=plugin').not.toBeNull();
    expect((d.querySelector('[data-drawer="plugin"]') as HTMLElement).hasAttribute('data-page-state')).toBe(false);
    const banner = d.querySelector('.tt-banner[data-tone="warning"]') as HTMLElement;
    expect(banner, '非 READY 时一条 warning 提示条').not.toBeNull();
    expect(textOf(banner)).toMatch(/锁与内容不一致。\s*缺的权限：fs\.write、net\.http。/);
    key('Escape');
    await openByEnter(rowOf(table, 'alpha'));
    d = dialog() as HTMLElement;
    expect(d.querySelector('.tt-banner'), 'READY 没有提示条').toBeNull();
    key('Escape');
    await openByEnter(rowOf(table, 'delta'));
    d = dialog() as HTMLElement;
    const b2 = d.querySelector('.tt-banner[data-tone="warning"]') as HTMLElement;
    expect(b2).not.toBeNull();
    expect(textOf(b2)).toContain('WEIRD');
  });

  it('manifest 小节：dl 依次 ID/版本/启用/权限/api_version/capabilities/platforms/depends_on/conflicts，checks 不显示；权限缺的 danger 加（缺）；列表用「、」连接，空写（无）；不限制后接（没有配置启用名单）', async () => {
    const table = await mountPluginsTable();
    await openByEnter(rowOf(table, 'beta'));
    const d = dialog() as HTMLElement;
    const dts = Array.from(d.querySelectorAll('dl dt')).map((x) => textOf(x));
    expect(isSubsequence(['ID', '版本', '启用', '权限', 'api_version', 'capabilities', 'platforms', 'depends_on', 'conflicts'], dts), 'dt：' + dts.join('、')).toBe(true);
    expect(dts.includes('checks')).toBe(false);
    expect(textOf(d)).not.toContain('CHECKS-CANARY-1');
    expect(textOf(ddOf(d, 'ID'))).toBe('beta');
    expect(textOf(ddOf(d, '版本'))).toBe('0.1.0');
    expect(textOf(ddOf(d, '启用'))).toBe('停用');
    const perms = tagsIn(ddOf(d, '权限'));
    expect(perms.map((t) => textOf(t))).toEqual(['fs.read', 'fs.write（缺）', 'net.http（缺）']);
    expect(perms.map((t) => t.getAttribute('data-tone') === 'danger')).toEqual([false, true, true]);
    expect(textOf(ddOf(d, 'capabilities'))).toBe('review、docs');
    expect(textOf(ddOf(d, 'platforms'))).toBe('windows、linux');
    expect(textOf(ddOf(d, 'depends_on'))).toBe('（无）');
    expect(textOf(ddOf(d, 'conflicts'))).toBe('old-plugin');
    key('Escape');
    await openByEnter(rowOf(table, 'gamma'));
    expect(textOf(ddOf(dialog() as HTMLElement, '启用'))).toContain('不限制');
    expect(textOf(ddOf(dialog() as HTMLElement, '启用'))).toContain('（没有配置启用名单）');
  });

  it('资源哈希核对：路径、sha256（前 12 位加…，title 全文）、结果（detail 非空时接（detail））', async () => {
    const table = await mountPluginsTable();
    await openByEnter(rowOf(table, 'beta'));
    const d = dialog() as HTMLElement;
    const text = textOf(d);
    for (const s of ['路径', 'sha256', '结果', 'manifest.json', 'checks/headings.py', '内容变了']) expect(text).toContain(s);
    for (const h of [HASH_A, HASH_B]) {
      const el = d.querySelector('[title="' + h + '"]') as HTMLElement;
      expect(el, 'sha256 的 title 是全文').not.toBeNull();
      expect(textOf(el)).toBe(h.slice(0, 12) + '…');
    }
    expect(text).not.toContain(HASH_A);
    expect(text).toContain('漂移');
    expect(text.indexOf('内容变了')).toBeGreaterThan(text.indexOf('漂移'));
  });

  it('锁小节：generation（tt-num）、lock_sha256 全文、[复制 lock_sha256] 与三种结果文字（没有剪贴板接口/已复制/复制失败），不弹轻提示', async () => {
    const table = await mountPluginsTable();
    await openByEnter(rowOf(table, 'beta'));
    const d = dialog() as HTMLElement;
    expect(textOf(d)).toContain('generation');
    expect(Array.from(d.querySelectorAll('.tt-num')).some((e) => textOf(e) === '7')).toBe(true);
    expect(leafWithText(d, HASH_LOCK), 'lock_sha256 全文').not.toBeNull();
    const copy = d.querySelector('button[aria-label="复制 lock_sha256"]') as HTMLButtonElement;
    expect(copy, '应有 IconButton「复制 lock_sha256」').not.toBeNull();
    expect(copy.disabled).toBe(false);
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true });
    fireEvent.click(copy);
    await settle();
    expect(textOf(d)).toContain('这个环境没有剪贴板接口');
    const write = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: write }, configurable: true });
    fireEvent.click(copy);
    await settle();
    expect(write).toHaveBeenCalledWith(HASH_LOCK);
    expect(textOf(d)).toContain('已复制');
    expect(textOf(d)).not.toContain('这个环境没有剪贴板接口');
    const fail = vi.fn().mockRejectedValue(new Error('denied'));
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: fail }, configurable: true });
    fireEvent.click(copy);
    await settle();
    expect(textOf(d)).toContain('复制失败');
    expect(d.querySelector('.tt-toast, [role="status"]'), '抽屉里不弹轻提示、不设 role=status').toBeNull();
    expect(viewRoot('plugins').querySelector('.tt-toast, [role="status"]')).toBeNull();
  });

  it('footer：[重新核对] 禁用（secondary、md）', async () => {
    const table = await mountPluginsTable();
    await openByEnter(rowOf(table, 'alpha'));
    const btn = buttonByText(dialog() as HTMLElement, '重新核对');
    expect(btn.disabled).toBe(true);
    expect(btn.getAttribute('data-variant')).toBe('secondary');
    expect(btn.getAttribute('data-size')).toBe('md');
  });

  it('读取中写「正在读取…」；出错写「没能读到详情：命令（…）返回退出码 N。」且 messages 在 pre 里按纯文本显示', async () => {
    const table = await mountPluginsTable();
    const d1 = deferred();
    hoisted.overrides.getPlugin = () => d1.promise;
    await openByEnter(rowOf(table, 'alpha'));
    expect(textOf(dialog())).toContain('正在读取…');
    await act(async () => { d1.resolve(bad(['ERROR a <i>b</i>', 'ERROR c'], ['plugins', 'show', 'alpha'])); });
    const d = dialog() as HTMLElement;
    expect(textOf(d)).toContain('没能读到详情：命令（plugins show alpha）返回退出码 2。');
    const pre = d.querySelector('pre') as HTMLElement;
    expect(pre, 'messages 放 pre 里').not.toBeNull();
    expect(pre.textContent).toContain('ERROR a <i>b</i>');
    expect(pre.textContent).toContain('ERROR c');
    expect(pre.querySelector('i')).toBeNull();
    expect(textOf(d)).not.toContain('正在读取…');
  });

  it('只认最后一次请求（旧回应先到或后到都丢弃）', async () => {
    for (const oldFirst of [false, true]) {
      const table = await mountPluginsTable();
      hoisted.spies.getPlugin.mockClear();
      const dA = deferred();
      const dB = deferred();
      hoisted.overrides.getPlugin = (id: string) => (id === 'alpha' ? dA.promise : dB.promise);
      await openByEnter(rowOf(table, 'alpha'));
      fireEvent.click(rowOf(table, 'beta'));
      await settle();
      expect(callsOf('getPlugin').map((c) => c[0])).toEqual(['alpha', 'beta']);
      const resA = ok(showFor('alpha'), ['plugins', 'show', 'alpha']);
      const resB = ok(showFor('beta'), ['plugins', 'show', 'beta']);
      if (oldFirst) {
        await act(async () => { dA.resolve(resA); });
        expect(Array.from((dialog() as HTMLElement).querySelectorAll('dd')).some((dd) => textOf(dd) === '1.2.3'), '旧回应先到，不显示').toBe(false);
      } else {
        await act(async () => { dB.resolve(resB); });
        await act(async () => { dA.resolve(resA); });
        expect(textOf(ddOf(dialog() as HTMLElement, 'ID')), '旧回应不能覆盖新内容').toBe('beta');
      }
      cleanup();
    }
  }, 30000);
});

drawerBehaviour('插件', '#/plugins?mock=data', LIST.plugins.length, () => installPlugins());
"""

# ---------------------------------------------------------------------------
# history 探针（D06 表，D07 差异抽屉）
# ---------------------------------------------------------------------------

PROBE_HISTORY = PRELUDE + HOIST + DRAWER_KIT + r"""
const NOW = '2026-10-18T03:00:00Z';
function entry(n: number, o: any) {
  return {
    number: n, resource: 'config', at: '2026-10-18T02:30:00Z', action: 'config.set', target: 'pricing', actor: 'user-ui',
    confirmation: 'none', state: 'published', resolved: false, changed_keys: [], note: null, external_changes: 0, ...o,
  };
}
const HIST: any = {
  entries: [
    entry(1, { resource: 'weird-res', at: '2026-10-18T00:00:00Z', actor: 'something' }),
    entry(2, { at: 'not-a-time', action: 'role.set', target: 'execution', actor: 'undeclared', confirmation: 'flag', state: null, changed_keys: null, note: '疑似凭据，不显示' }),
    entry(3, { at: '2026-10-18T02:59:30Z', action: 'custom.act', target: '', actor: 'agent:planning_review', state: 'unknown', changed_keys: null, note: '（含疑似凭据，不显示）' }),
    entry(4, { resource: 'local', at: '2026-10-17T03:00:00Z', action: 'runtime.add', target: 'pi', actor: 'user', state: 'aborted', changed_keys: null, note: '本机文件不存快照' }),
    entry(5, { at: '2026-10-18T02:02:11Z', action: 'preset.use', target: 'default', actor: 'user-ui', confirmation: 'flag', resolved: true, changed_keys: ['active_preset', 'roles'], external_changes: 2 }),
    entry(6, { at: '2026-10-18T02:30:00Z', action: 'external', target: '', changed_keys: ['k'] }),
    entry(7, { at: '2026-10-18T02:40:00Z', action: 'config.unset', target: 'x', changed_keys: null }),
    entry(8, { at: '2026-10-18T02:50:00Z', action: 'config.set', target: 'pricing', changed_keys: ['pricing', 'roles'], note: '（含疑似凭据，不显示）' }),
  ],
  broken_lines: ['bad1', 'bad2'],
  external_before_first: 3,
};
const DETAIL: any = {
  1: { number: 1, state: 'published', note: null, diff: [] },
  2: { number: 2, state: null, note: '疑似凭据，不显示', diff: null },
  3: { number: 3, state: 'unknown', note: '（含疑似凭据，不显示）', diff: null },
  4: { number: 4, resource: 'local', state: 'aborted', before_sha256: HASH_A, after_sha256: HASH_B, note: '本机文件不存快照' },
  5: { number: 5, state: 'published', note: null, diff: [
    { key: 'active_preset', old: 'default', new: 'economy' },
    { key: 'roles.x', old: null, new: 5 },
    { key: 'enabled_flag', old: true, new: { a: 1 } },
    { key: 'secret.k', old: '<redacted>', new: '（值不显示）' },
  ] },
  6: { number: 6, state: 'published', note: '快照太旧', diff: null },
  7: { number: 7, state: 'published', note: null, diff: null },
  8: { number: 8, state: 'published', note: '（含疑似凭据，不显示）', diff: null },
};
function installHistory(list: any = HIST) {
  over('getHistory', list, ['config', 'history']);
  hoisted.overrides.getHistoryEntry = (n: any) => {
    const cmd = ['config', 'history', 'show', String(n)];
    return Promise.resolve(DETAIL[n] ? ok(clone(DETAIL[n]), cmd) : bad(['ERROR 夹具里没有这份数据：' + n], cmd));
  };
}
async function mountHistory(list: any = HIST, fake = false) {
  if (fake) {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(NOW));
  }
  installHistory(list);
  await mountApp('#/history?mock=data');
  return tableByLabel('配置历史');
}
const rowN = (table: Element, n: number) => rowByFirstCell(table, '#' + n);
const cellN = (table: Element, n: number, i: number) => cellsOf(rowN(table, n))[i];
function keyRow(d: ParentNode, k: string): HTMLElement[] {
  const leaf = leafWithText(d, k);
  expect(leaf, '键级差异里应有键 ' + k).not.toBeNull();
  let el = leaf as HTMLElement;
  while (el.parentElement && el.parentElement.children.length < 3) el = el.parentElement;
  expect(el.parentElement, k + ' 所在行').not.toBeNull();
  return Array.from((el.parentElement as HTMLElement).children) as HTMLElement[];
}
const MINUS = String.fromCharCode(0x2212);

describe('D06 历史表', () => {
  it('表 aria-label=配置历史、rowHeight 40、十列；视图根 data-page=history；说明原文；按编号倒序，编号「#n」带 tt-num', async () => {
    const table = await mountHistory(HIST, true);
    expect(headersOf(table)).toEqual(['编号', '时间', '资源', '动作', '对象', '执行者', '确认', '状态', '改动的键', '外部改动']);
    expect(table.getAttribute('data-row-height')).toBe('40');
    const rows = bodyRows(table);
    expect(rows.map((r) => textOf(cellsOf(r)[0]))).toEqual(['#8', '#7', '#6', '#5', '#4', '#3', '#2', '#1']);
    for (const r of rows) expect(hasClass(cellsOf(r)[0], 'tt-num')).toBe(true);
    const root = viewRoot('history');
    expect(root.hasAttribute('data-page-state')).toBe(false);
    expect(root.querySelector('h1')).toBeNull();
    expect(textOf(document.body)).toContain('每次配置写入都有编号；点一行看前后快照的键级差异，必要时回滚');
  });

  it('时间：相对时间，title 是「YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）」；解析不了原样显示、不带 title', async () => {
    const table = await mountHistory(HIST, true);
    expect(textOf(cellN(table, 5, 1))).toBe('57 分钟前');
    expect(titleOf(cellN(table, 5, 1))).toBe(expectedTitle('2026-10-18T02:02:11Z'));
    expect(textOf(cellN(table, 4, 1))).toBe('1 天前');
    expect(textOf(cellN(table, 3, 1))).toBe('30 秒前');
    expect(textOf(cellN(table, 1, 1))).toBe('3 小时前');
    expect(titleOf(cellN(table, 3, 1))).toBe(expectedTitle('2026-10-18T02:59:30Z'));
    expect(textOf(cellN(table, 2, 1))).toBe('not-a-time');
    expect(titleOf(cellN(table, 2, 1))).toBeNull();
  });

  it('资源（配置/本机文件/其他原样）、动作（title 是中文说明，没有说明就不带）、对象（空写「—」）、确认（原样）', async () => {
    const table = await mountHistory(HIST, true);
    expect(textOf(cellN(table, 5, 2))).toBe('配置');
    expect(textOf(cellN(table, 4, 2))).toBe('本机文件');
    expect(textOf(cellN(table, 1, 2))).toBe('weird-res');
    for (const [n, action] of [[5, 'preset.use'], [4, 'runtime.add'], [6, 'external'], [2, 'role.set'], [7, 'config.unset']] as Array<[number, string]>) {
      const c = cellN(table, n, 3);
      expect(textOf(c)).toBe(action);
      expect(titleOf(c), action + ' 应有中文说明').toMatch(/[一-鿿]/);
    }
    expect(textOf(cellN(table, 3, 3))).toBe('custom.act');
    expect(titleOf(cellN(table, 3, 3)), '没有对应说明就不带 title').toBeNull();
    expect(textOf(cellN(table, 5, 4))).toBe('default');
    expect(textOf(cellN(table, 3, 4))).toBe('—');
    expect(textOf(cellN(table, 5, 6))).toBe('flag');
    expect(textOf(cellN(table, 3, 6))).toBe('none');
  });

  it('执行者：user-ui brand、user neutral、agent: 开头 info、undeclared warning、其他 neutral', async () => {
    const table = await mountHistory(HIST, true);
    const want: Array<[number, string, string]> = [[5, 'user-ui', 'brand'], [4, 'user', 'neutral'], [3, 'agent:planning_review', 'info'], [2, 'undeclared', 'warning'], [1, 'something', 'neutral']];
    for (const [n, text, tone] of want) {
      const tag = cellN(table, n, 5).querySelector('[data-tone]') as HTMLElement;
      expect(tag, '#' + n).not.toBeNull();
      expect(textOf(tag)).toBe(text);
      expect(tag.getAttribute('data-tone'), '#' + n).toBe(tone);
    }
  });

  it('状态：published 已发布、aborted 已中止、unknown 未知、null 进行中或已中断，resolved 后接（补判），title 原状态码', async () => {
    const table = await mountHistory(HIST, true);
    const want: Array<[number, string, string | null]> = [[5, '已发布（补判）', 'published'], [4, '已中止', 'aborted'], [3, '未知', 'unknown'],
      [2, '进行中或已中断', null], [1, '已发布', 'published']];
    for (const [n, text, title] of want) {
      expect(textOf(cellN(table, n, 7)).replace(/\s+/g, ''), '#' + n).toBe(text);
      if (title) expect(titleOf(cellN(table, n, 7)), '#' + n).toBe(title);
    }
  });

  it('改动的键：每个键一个 neutral Tag；null 时显示 note（遮蔽占位用 MaskedValue，其他普通文字）；都没有写「—」', async () => {
    const table = await mountHistory(HIST, true);
    expect(tagsIn(cellN(table, 5, 8)).map((t) => textOf(t))).toEqual(['active_preset', 'roles']);
    tagsIn(cellN(table, 5, 8)).forEach((t) => expect(t.getAttribute('data-tone')).toBe('neutral'));
    expect(tagsIn(cellN(table, 8, 8)).map((t) => textOf(t))).toEqual(['pricing', 'roles']);
    const masked = cellN(table, 3, 8).querySelector('span.tt-masked') as HTMLElement;
    expect(masked, '占位 note 用 MaskedValue').not.toBeNull();
    expect(textOf(masked)).toBe('（含疑似凭据，不显示）');
    expect(masked.getAttribute('title')).toBe('内核已遮蔽');
    expect(textOf(cellN(table, 2, 8))).toBe('疑似凭据，不显示');
    expect(cellN(table, 2, 8).querySelector('.tt-masked'), '不是占位的说明按普通文字').toBeNull();
    expect(textOf(cellN(table, 4, 8))).toBe('本机文件不存快照');
    expect(textOf(cellN(table, 1, 8))).toBe('—');
    expect(textOf(cellN(table, 7, 8))).toBe('—');
  });

  it('外部改动：>0 时 warning Tag「检测到外部改动」（title 说明次数），否则「—」', async () => {
    const table = await mountHistory(HIST, true);
    const tag = cellN(table, 5, 9).querySelector('[data-tone]') as HTMLElement;
    expect(textOf(tag)).toBe('检测到外部改动');
    expect(tag.getAttribute('data-tone')).toBe('warning');
    expect(titleOf(cellN(table, 5, 9)) || '').toContain('2');
    expect(textOf(cellN(table, 4, 9))).toBe('—');
    expect(tagsIn(cellN(table, 4, 9)).length).toBe(0);
  });

  it('表下一行注记；external_before_first>0 时表上方一行注记；broken_lines 非空时顶部 warning 提示条「历史里有 N 行读不出来」', async () => {
    const table = await mountHistory(HIST, true);
    const root = viewRoot('history');
    const below = smallestWith(root, '时间显示相对时间，悬停显示本地时间与 UTC；动作悬停显示中文说明。');
    expect(below, '表下应有注记').toBeTruthy();
    expect((table.compareDocumentPosition(below as Element) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0).toBe(true);
    const above = smallestWith(root, '第 1 条之前：配置中心之外已有的内容（记为基线，发现 3 次）');
    expect(above, '表上方应有注记').toBeTruthy();
    expect((table.compareDocumentPosition(above as Element) & Node.DOCUMENT_POSITION_PRECEDING) !== 0).toBe(true);
    const banner = Array.from(document.querySelectorAll('.tt-banner[data-tone="warning"]')).find((b) => textOf(b).includes('历史里有 2 行读不出来'));
    expect(banner, 'broken_lines 非空时有 warning 提示条').toBeTruthy();
    expect((banner as Element).querySelector('button')).toBeNull();
    cleanup();
    vi.useRealTimers();
    const t2 = await mountHistory({ ...HIST, broken_lines: [], external_before_first: 0 });
    expect(textOf(document.body)).not.toContain('读不出来');
    expect(textOf(document.body)).not.toContain('第 1 条之前');
    expect(textOf(document.body)).toContain('时间显示相对时间');
    expect(bodyRows(t2).length).toBe(8);
  }, 30000);

  it('isEmpty：entries 与 broken_lines 都为空才算空（空态标题「还没有配置历史」）；只有 broken_lines 仍是 data 并显示提示条', async () => {
    installHistory({ entries: [], broken_lines: [], external_before_first: 0 });
    await mountApp('#/history?mock=data');
    expect(pageRoot().getAttribute('data-page-state')).toBe('empty');
    expect(textOf(document.body)).toContain('还没有配置历史');
    cleanup();
    installHistory({ entries: [], broken_lines: ['x'], external_before_first: 0 });
    await mountApp('#/history?mock=data');
    expect(pageRoot().getAttribute('data-page-state')).toBe('data');
    expect(textOf(document.body)).toContain('历史里有 1 行读不出来');
  }, 30000);
});

describe('D07 差异抽屉：头部、dl、键级差异', () => {
  it('标题「#n · action target」；dl 时间/动作/执行者/确认/状态；时间是本地加 UTC 的写法；外部改动>0 时 warning 提示条', async () => {
    const table = await mountHistory();
    await openByEnter(rowN(table, 5));
    let d = dialog() as HTMLElement;
    expect(textOf(d.querySelector('h2'))).toBe('#5 · preset.use default');
    expect(d.querySelector('[data-drawer="history"]'), '抽屉内容根 data-drawer=history').not.toBeNull();
    const dts = Array.from(d.querySelectorAll('dl dt')).map((x) => textOf(x));
    expect(isSubsequence(['时间', '动作', '执行者', '确认', '状态'], dts), 'dt：' + dts.join('、')).toBe(true);
    expect(textOf(ddOf(d, '时间'))).toContain(expectedTitle('2026-10-18T02:02:11Z'));
    expect(textOf(ddOf(d, '动作'))).toContain('preset.use');
    expect(textOf(ddOf(d, '执行者'))).toContain('user-ui');
    expect(textOf(ddOf(d, '确认'))).toContain('flag');
    expect(textOf(ddOf(d, '状态'))).toContain('已发布');
    const banner = Array.from(d.querySelectorAll('.tt-banner[data-tone="warning"]')).find((b) => textOf(b).includes('这条之后检测到 2 次界面与命令之外的改动。'));
    expect(banner, 'external_changes>0 时有 warning 提示条').toBeTruthy();
    key('Escape');
    await openByEnter(rowN(table, 8));
    d = dialog() as HTMLElement;
    expect(textOf(d.querySelector('h2'))).toBe('#8 · config.set pricing');
    expect(d.querySelector('.tt-banner'), 'external_changes 为 0 没有提示条').toBeNull();
  });

  it('情形二：diff 非空数组 → KeyDiff（键、之前、之后三列）；之前「− 值」(U+2212)、之后「+ 值」；null 写「未设置」；对象写 JSON；遮蔽占位用 MaskedValue', async () => {
    const table = await mountHistory();
    await openByEnter(rowN(table, 5));
    const d = dialog() as HTMLElement;
    const text = textOf(d);
    expect(text).toContain('键级差异');
    const hs = ['键', '之前', '之后'].map((s) => text.indexOf(s, text.indexOf('键级差异')));
    hs.forEach((i) => expect(i).toBeGreaterThanOrEqual(0));
    expect(hs[0]).toBeLessThan(hs[1]);
    expect(hs[1]).toBeLessThan(hs[2]);
    const a = keyRow(d, 'active_preset');
    expect(textOf(a[1])[0], '减号是 U+2212').toBe(MINUS);
    expect(textOf(a[1])).toMatch(new RegExp('^' + MINUS + '\\s*default$'));
    expect(textOf(a[2])).toMatch(/^\+\s*economy$/);
    const b = keyRow(d, 'roles.x');
    expect(textOf(b[1])).toBe('未设置');
    expect(textOf(b[2])).toMatch(/^\+\s*5$/);
    const c = keyRow(d, 'enabled_flag');
    expect(textOf(c[1])).toMatch(new RegExp('^' + MINUS + '\\s*true$'));
    expect(JSON.parse(textOf(c[2]).replace(/^\+\s*/, ''))).toEqual({ a: 1 });
    const m = keyRow(d, 'secret.k');
    expect(textOf(m[1].querySelector('.tt-masked'))).toBe('<redacted>');
    expect(textOf(m[2].querySelector('.tt-masked'))).toBe('（值不显示）');
    expect(text).not.toContain('没有改动的键');
    expect(text).not.toContain('快照里有疑似凭据');
  });

  it('情形一与三、五：本机文件说明；diff 为空数组「没有改动的键」；其他显示 note，没有 note 写「快照缺失，没有逐键差异」；本机文件优先于别的情形', async () => {
    const table = await mountHistory();
    const open = async (n: number) => {
      if (dialog()) key('Escape');
      await openByEnter(rowN(table, n));
      return textOf(dialog());
    };
    const t4 = await open(4);
    expect(t4).toContain('本机文件不存快照，这一条只有审计记录，不能回滚。');
    expect(t4).not.toContain('之前');
    expect(await open(1)).toContain('没有改动的键');
    const t6 = await open(6);
    expect(t6).toContain('快照太旧');
    expect(t6).not.toContain('快照里有疑似凭据');
    expect(await open(7)).toContain('快照缺失，没有逐键差异');
  });

  it('情形四：diff 为 null 且 note 疑似凭据——占位 note 加列表有改动的键时逐键两格 MaskedValue；否则只显示 note 原文；两种都加 LockIcon 12 与「快照里有疑似凭据，只存了哈希。」', async () => {
    const table = await mountHistory();
    await openByEnter(rowN(table, 8));
    let d = dialog() as HTMLElement;
    for (const k of ['pricing', 'roles']) {
      const r = keyRow(d, k);
      expect(textOf(r[1].querySelector('.tt-masked')), k + ' 之前').toBe('（含疑似凭据，不显示）');
      expect(textOf(r[2].querySelector('.tt-masked')), k + ' 之后').toBe('（含疑似凭据，不显示）');
    }
    expect(textOf(d)).toContain('快照里有疑似凭据，只存了哈希。');
    expect(hasIcon(d, LockIcon, 12)).toBe(true);
    key('Escape');
    await openByEnter(rowN(table, 2));
    d = dialog() as HTMLElement;
    expect(textOf(d)).toContain('疑似凭据，不显示');
    expect(textOf(d)).toContain('快照里有疑似凭据，只存了哈希。');
    expect(hasIcon(d, LockIcon, 12)).toBe(true);
    expect(textOf(d)).not.toContain('之前');
    key('Escape');
    await openByEnter(rowN(table, 3));
    d = dialog() as HTMLElement;
    expect(textOf(d)).toContain('（含疑似凭据，不显示）');
    expect(textOf(d)).toContain('快照里有疑似凭据，只存了哈希。');
  });

  it('footer：最新一条写「这是最新的一条，回滚后没有变化」，本机文件写「本机文件不存快照，不能回滚」，其余不写；[回滚到这一条之后] 禁用（secondary、md、RotateCcwIcon 16）', async () => {
    const table = await mountHistory();
    const open = async (n: number) => {
      if (dialog()) key('Escape');
      await openByEnter(rowN(table, n));
      return dialog() as HTMLElement;
    };
    let d = await open(8);
    expect(textOf(d)).toContain('这是最新的一条，回滚后没有变化');
    const btn = buttonByText(d, '回滚到这一条之后');
    expect(btn.disabled).toBe(true);
    expect(btn.getAttribute('data-variant')).toBe('secondary');
    expect(btn.getAttribute('data-size')).toBe('md');
    expect(hasIcon(btn, RotateCcwIcon, 16)).toBe(true);
    d = await open(4);
    expect(textOf(d)).toContain('本机文件不存快照，不能回滚');
    expect(textOf(d)).not.toContain('这是最新的一条');
    expect(buttonByText(d, '回滚到这一条之后').disabled).toBe(true);
    d = await open(5);
    expect(textOf(d)).not.toContain('这是最新的一条');
    expect(textOf(d)).not.toContain('本机文件不存快照，不能回滚');
    expect(buttonByText(d, '回滚到这一条之后').disabled).toBe(true);
  });
});

describe('D07 差异抽屉：读取', () => {
  it('读取函数按行的编号调用；读取中写「正在读取…」；出错写「没能读到详情：命令（config history show 5）返回退出码 2。」与 pre', async () => {
    const table = await mountHistory();
    const d1 = deferred();
    hoisted.overrides.getHistoryEntry = () => d1.promise;
    await openByEnter(rowN(table, 5));
    expect(callsOf('getHistoryEntry').map((c) => Number(c[0]))).toEqual([5]);
    expect(textOf(dialog())).toContain('正在读取…');
    await act(async () => { d1.resolve(bad(['ERROR x <b>y</b>', 'ERROR z'], ['config', 'history', 'show', '5'])); });
    const d = dialog() as HTMLElement;
    expect(textOf(d)).toContain('没能读到详情：命令（config history show 5）返回退出码 2。');
    const pre = d.querySelector('pre') as HTMLElement;
    expect(pre).not.toBeNull();
    expect(pre.textContent).toContain('ERROR x <b>y</b>');
    expect(pre.querySelector('b')).toBeNull();
    expect(textOf(d)).not.toContain('正在读取…');
  });

  it('只认最后一次请求（旧回应先到或后到都丢弃）', async () => {
    for (const oldFirst of [false, true]) {
      const table = await mountHistory();
      hoisted.spies.getHistoryEntry.mockClear();
      const dA = deferred();
      const dB = deferred();
      hoisted.overrides.getHistoryEntry = (n: any) => (Number(n) === 5 ? dA.promise : dB.promise);
      await openByEnter(rowN(table, 5));
      fireEvent.click(rowN(table, 6));
      await settle();
      expect(callsOf('getHistoryEntry').map((c) => Number(c[0]))).toEqual([5, 6]);
      const resA = ok(clone(DETAIL[5]), ['config', 'history', 'show', '5']);
      const resB = ok(clone(DETAIL[6]), ['config', 'history', 'show', '6']);
      if (oldFirst) {
        await act(async () => { dA.resolve(resA); });
        expect(textOf(dialog()), '旧回应先到，不显示').not.toContain('active_preset');
      } else {
        await act(async () => { dB.resolve(resB); });
        await act(async () => { dA.resolve(resA); });
        expect(textOf(dialog()), '旧回应不能覆盖新内容').toContain('快照太旧');
        expect(textOf(dialog())).not.toContain('active_preset');
      }
      cleanup();
    }
  }, 30000);
});

drawerBehaviour('历史', '#/history?mock=data', 8, () => installHistory());
"""

# ---------------------------------------------------------------------------
# app 探针（D08 五态、夹具下的具体值、D09 写入口；过渡）
# ---------------------------------------------------------------------------

PROBE_APP = PRELUDE + HOIST + DRAWER_KIT + r"""
const PAGES = [
  { id: 'secrets', title: '凭据', cmd: 'config show', empty: '还没有要检查的凭据变量', refresh: '重新检查' },
  { id: 'logs', title: '日志与用量', cmd: 'logs usage', empty: null, refresh: '刷新' },
  { id: 'plugins', title: '插件', cmd: 'plugins list', empty: '还没有插件', refresh: '刷新' },
  { id: 'history', title: '历史与审计', cmd: 'config history', empty: '还没有配置历史', refresh: '刷新' },
];
const ALLOWED_BUTTONS = ['刷新', '重新检查', '重试', '检索', '关闭（Esc）', '复制 lock_sha256', '(tab)'];

function disabledWrites(): HTMLButtonElement[] {
  const all = Array.from(document.querySelectorAll('main button:disabled, [role="dialog"] button:disabled')) as HTMLButtonElement[];
  return all.filter((b) => textOf(b) !== '重新连接');
}
function enabledNames(): string[] {
  return Array.from(document.querySelectorAll('main button:not(:disabled), [role="dialog"] button:not(:disabled)')).map((b) =>
    b.getAttribute('role') === 'tab' ? '(tab)' : b.getAttribute('aria-label') || textOf(b),
  );
}
function whitelistProblems(label: string): string[] {
  const out: string[] = [];
  for (const n of enabledNames()) if (!ALLOWED_BUTTONS.includes(n)) out.push(label + '：可用按钮「' + n + '」不在白名单里');
  for (const a of Array.from(document.querySelectorAll('main a[href], [role="dialog"] a[href]'))) {
    if (textOf(a) !== '去设置') out.push(label + '：可用链接「' + textOf(a) + '」不在白名单里');
  }
  return out;
}
function searchFormNow(): HTMLFormElement {
  const btn = document.querySelector('[role="tabpanel"] button[type="submit"]') as HTMLElement;
  expect(btn, '检索页签里应有 [检索]').toBeTruthy();
  return btn.closest('form') as HTMLFormElement;
}
async function searchReal(q: string, max: string | null = null, task: string | null = null) {
  const f = searchFormNow();
  fireEvent.change(f.querySelector('input:not([type="number"])') as Element, { target: { value: q } });
  if (max !== null) fireEvent.change(f.querySelector('input[type="number"]') as Element, { target: { value: max } });
  if (task !== null) fireEvent.change(f.querySelector('select') as Element, { target: { value: task } });
  fireEvent.submit(f);
  await settle();
}
function panel(): string {
  return textOf(document.querySelector('[role="tabpanel"]'));
}

describe('D08 五态（经 ?mock=）', () => {
  it('loading：四页 299ms 时没有骨架、300ms 时有；不出现视图', async () => {
    for (const p of PAGES) {
      vi.useFakeTimers();
      await mountApp('#/' + p.id + '?mock=loading');
      expect(pageRoot().getAttribute('data-page-state'), p.id).toBe('loading');
      advance(299);
      expect(document.querySelector('.tt-skel'), p.id + ' 299ms').toBeNull();
      advance(1);
      expect(document.querySelectorAll('.tt-skel').length, p.id + ' 300ms').toBeGreaterThan(0);
      expect(document.querySelector('[data-page]'), p.id).toBeNull();
      cleanup();
      vi.useRealTimers();
    }
  }, 60000);

  it('data：四页都是 data，视图根在；整页恰一个 data-page-state', async () => {
    for (const p of PAGES) {
      await mountApp('#/' + p.id + '?mock=data');
      expect(pageRoot().getAttribute('data-page-state'), p.id).toBe('data');
      expect(textOf(document.querySelector('h1'))).toBe(p.title);
      viewRoot(p.id);
      expect(document.querySelectorAll('[data-page]').length).toBe(1);
      cleanup();
    }
  }, 60000);

  it('empty：凭据、插件、历史显示各自的空态标题；日志与用量仍是 data', async () => {
    for (const p of PAGES) {
      await mountApp('#/' + p.id + '?mock=empty');
      if (p.empty) {
        expect(pageRoot().getAttribute('data-page-state'), p.id).toBe('empty');
        expect(textOf(document.body)).toContain(p.empty);
        expect(document.querySelector('[data-page]'), p.id + ' 空态没有视图').toBeNull();
      } else {
        expect(pageRoot().getAttribute('data-page-state'), p.id + ' 没有空态').toBe('data');
        viewRoot(p.id);
      }
      cleanup();
    }
  }, 60000);

  it('error：出错块写命令（config show / logs usage / plugins list / config history）、退出码 2、报错原文在 pre 里；日志页连检索页签都看不到；点重试再读一次', async () => {
    for (const p of PAGES) {
      await mountApp('#/' + p.id + '?mock=error');
      expect(pageRoot().getAttribute('data-page-state'), p.id).toBe('error');
      const t = textOf(document.body);
      expect(t).toContain('没能读到数据');
      expect(t).toContain(p.cmd);
      expect(t).toMatch(/返回退出码\s*2/);
      expect((document.querySelector('pre') as Element).textContent).toBe(ERROR_TEXT);
      expect(document.querySelector('[data-page]'), p.id).toBeNull();
      expect(document.querySelector('[role="tablist"]'), p.id + ' 出错时没有页签').toBeNull();
      expect(maybeButton(document.body, '重试')).not.toBeNull();
      cleanup();
    }
  }, 60000);

  it('offline：数据照常显示，一条 role=alert 提示条、可能已过期标签、data-stale=true、禁用的重新连接', async () => {
    for (const p of PAGES) {
      await mountApp('#/' + p.id + '?mock=offline');
      const root = pageRoot();
      expect(root.getAttribute('data-page-state'), p.id).toBe('data');
      expect(root.getAttribute('data-stale')).toBe('true');
      expect(document.querySelectorAll('[role="alert"]').length).toBe(1);
      expect(tagWithText(document.body, '可能已过期')).toBeTruthy();
      expect(buttonByText(document.body, '重新连接').disabled).toBe(true);
      viewRoot(p.id);
      cleanup();
    }
  }, 60000);

  it('抽屉打开时整页仍恰有一个 data-page-state（插件、历史）', async () => {
    for (const [id, label] of [['plugins', '插件'], ['history', '历史与审计']]) {
      await mountApp('#/' + id + '?mock=data');
      await openByEnter(tbodyRows()[0]);
      expect(dialog(), label).not.toBeNull();
      pageRoot();
      expect((dialog() as HTMLElement).querySelector('[data-page-state], h1')).toBeNull();
      cleanup();
    }
  }, 60000);
});

describe('夹具下的具体值（过渡）', () => {
  it('凭据：两行——STEP_API_KEY（profile step-high、step-low；系统凭据库）、TYPESAFE_API_KEY（决策模型；没有）', async () => {
    await mountApp('#/secrets?mock=data');
    const table = tableByLabel('凭据变量');
    expect(bodyRows(table).length).toBe(2);
    const a = cellsOf(rowByFirstCell(table, 'STEP_API_KEY'));
    expect(textOf(a[1])).toBe('profile step-high、step-low');
    expect(a[2].querySelector('[data-source]')!.getAttribute('data-source')).toBe('credential_store');
    expect(textOf(a[2])).toBe('系统凭据库');
    const b = cellsOf(rowByFirstCell(table, 'TYPESAFE_API_KEY'));
    expect(textOf(b[1])).toBe('决策模型');
    expect(textOf(b[2])).toBe('没有');
    expect(document.querySelectorAll('.tt-masked').length).toBe(0);
  });

  it('用量：合计 22,031,448；known 5、unknown 1；规划端空状态；一行 attempt 用量加一行未知；按模型占比 100.0%；任务下拉是全部任务、logs-cat、ui-readonly-api', async () => {
    await mountApp('#/logs?mock=data');
    const sel = searchFormNow().querySelector('select') as HTMLSelectElement;
    expect(Array.from(sel.options).map((o) => o.textContent)).toEqual(['全部任务', 'logs-cat', 'ui-readonly-api']);
    const tab = Array.from(document.querySelectorAll('[role="tab"]')).find((t) => textOf(t) === '用量') as HTMLElement;
    fireEvent.click(tab);
    await settle();
    const text = panel();
    expect(text).toContain('22,031,448');
    expect(tagWithText(document.body, 'known 5').getAttribute('data-tone')).toBe('success');
    expect(tagWithText(document.body, 'unknown 1').getAttribute('data-tone')).toBe('neutral');
    expect(document.querySelector('[role="tabpanel"] .tt-empty')).not.toBeNull();
    const at = tableByHeaders(document, ['任务', 'attempt', '模型', '状态', 'input', 'output', 'cacheRead', 'cacheWrite', '合计']);
    const rows = bodyRows(at);
    expect(rows.length).toBe(2);
    expect(textOf(cellsOf(rows[0])[0])).toBe('logs-cat');
    expect(textOf(cellsOf(rows[0])[8])).toBe('4,210,385');
    expect(textOf(cellsOf(rows[1])[0])).toBe('ui-readonly-api');
    expect(textOf(cellsOf(rows[1])[8])).toBe('未知');
    const mt = tableByHeaders(document, ['模型', '回报情况', '占比', 'input', 'output', '合计']);
    expect(bodyRows(mt).length).toBe(1);
    expect(textOf(cellsOf(bodyRows(mt)[0])[2])).toContain('100.0%');
  });

  it('检索（真读取函数）：固定模式有结果且至少两组、有太大没搜的提示；上限 1 时截断提示；未知检索词出错块；empty 开关下「没有匹配的行」；offline 下照常可用', async () => {
    await mountApp('#/logs?mock=data');
    await searchReal('logs[_ ]cat', '50');
    let t = panel();
    expect(t).not.toContain('没能检索');
    expect(t).toContain('结果');
    expect(new Set(t.match(/\S+ · attempt-\d+/g) || []).size).toBeGreaterThanOrEqual(2);
    expect(t).toContain('个文件太大或读不出来，没有搜；请用 CLI 查看');
    expect(t).toContain('摘录取自脱敏之后的文本');
    expect(document.querySelectorAll('[role="tabpanel"] mark').length).toBeGreaterThan(0);
    await searchReal('logs[_ ]cat', '1');
    t = panel();
    expect(t).toContain('只显示前 1 条匹配');
    expect(t).toContain('1 条 · 上限 1');
    await searchReal('zzz-not-in-fixture', '50');
    t = panel();
    expect(t).toContain('没能检索：命令（logs search zzz-not-in-fixture --max 50）返回退出码 2。');
    expect((document.querySelector('[role="tabpanel"] pre') as Element).textContent).toContain('ERROR 夹具里没有这份数据：');
    cleanup();
    await mountApp('#/logs?mock=empty');
    await searchReal('logs[_ ]cat', '50');
    expect(panel()).toContain('没有匹配的行');
    cleanup();
    await mountApp('#/logs?mock=offline');
    await searchReal('logs[_ ]cat', '50');
    expect(panel()).toContain('结果');
    expect(panel()).not.toContain('没能检索');
  }, 60000);

  it('插件：三行；docs-checks 的抽屉——warning 条（锁与内容不一致、fs.write）、缺 fs.write 的 danger 权限、两行资源一致、64 位 lock_sha256；decisions 没有提示条', async () => {
    await mountApp('#/plugins?mock=data');
    const table = tableByLabel('插件');
    expect(bodyRows(table).map((r) => textOf(cellsOf(r)[0]))).toEqual(['decisions', 'code-change', 'docs-checks']);
    await openByEnter(rowByFirstCell(table, 'decisions'));
    expect((dialog() as HTMLElement).querySelector('.tt-banner')).toBeNull();
    key('Escape');
    await openByEnter(rowByFirstCell(table, 'docs-checks'));
    const d = dialog() as HTMLElement;
    const banner = d.querySelector('.tt-banner[data-tone="warning"]') as HTMLElement;
    expect(banner).not.toBeNull();
    expect(textOf(banner)).toContain('锁与内容不一致');
    expect(textOf(banner)).toContain('fs.write');
    const miss = tagsIn(d).find((t) => textOf(t).startsWith('fs.write'));
    expect(miss && miss.getAttribute('data-tone')).toBe('danger');
    expect(tagsIn(d).some((t) => textOf(t) === 'fs.read')).toBe(true);
    expect(/[0-9a-f]{64}/.test(textOf(d))).toBe(true);
    expect(textOf(d)).toContain('manifest.json');
    expect(textOf(d)).toContain('checks/headings.py');
  });

  it('历史：三行 #42、#41、#40；#42 抽屉有键级差异；#41 本机文件；#40 有遮蔽的逐键两格与锁提示、外部改动提示条', async () => {
    await mountApp('#/history?mock=data');
    const table = tableByLabel('配置历史');
    expect(bodyRows(table).map((r) => textOf(cellsOf(r)[0]))).toEqual(['#42', '#41', '#40']);
    expect(textOf(cellsOf(rowByFirstCell(table, '#41'))[8])).toBe('本机文件不存快照');
    await openByEnter(rowByFirstCell(table, '#42'));
    let d = dialog() as HTMLElement;
    expect(textOf(d.querySelector('h2'))).toBe('#42 · preset.use default');
    expect(textOf(d)).toContain('之前');
    expect(textOf(d)).toContain('之后');
    expect(textOf(d)).not.toContain('没有改动的键');
    expect(textOf(d)).not.toContain('快照缺失');
    key('Escape');
    await openByEnter(rowByFirstCell(table, '#41'));
    d = dialog() as HTMLElement;
    expect(textOf(d)).toContain('本机文件不存快照，这一条只有审计记录，不能回滚。');
    expect(textOf(d)).toContain('本机文件不存快照，不能回滚');
    key('Escape');
    await openByEnter(rowByFirstCell(table, '#40'));
    d = dialog() as HTMLElement;
    expect(d.querySelectorAll('.tt-masked').length).toBeGreaterThanOrEqual(2);
    expect(textOf(d)).toContain('快照里有疑似凭据，只存了哈希。');
    expect(textOf(d)).toContain('这条之后检测到 1 次界面与命令之外的改动。');
  });
});

describe('D09 写入口', () => {
  it('夹具下个数（不含 offline 的重新连接）：凭据 2、日志 0、插件 3（抽屉开 4）、历史 0（抽屉开 1）；每个都 disabled，悬停 400ms 出现提示「第二阶段接入」', async () => {
    for (const mock of ['data', 'offline']) {
      vi.useFakeTimers();
      await mountApp('#/secrets?mock=' + mock);
      let w = disabledWrites();
      expect(w.map((b) => textOf(b)), 'secrets ' + mock).toEqual(['录入…', '录入…']);
      for (const b of w) expect(tipOf(b)).toBe('第二阶段接入');
      cleanup();
      await mountApp('#/logs?mock=' + mock);
      expect(disabledWrites().length).toBe(0);
      cleanup();
      await mountApp('#/plugins?mock=' + mock);
      w = disabledWrites();
      expect(w.map((b) => textOf(b)).sort()).toEqual(['停用…', '启用…', '核对全部'].sort());
      for (const b of w) expect(tipOf(b)).toBe('第二阶段接入');
      const rows = tbodyRows();
      await openByEnter(rows[2]);
      w = disabledWrites();
      expect(w.map((b) => textOf(b)).sort()).toEqual(['停用…', '启用…', '核对全部', '重新核对'].sort());
      for (const b of w) expect(tipOf(b)).toBe('第二阶段接入');
      cleanup();
      await mountApp('#/history?mock=' + mock);
      expect(disabledWrites().length).toBe(0);
      await openByEnter(tbodyRows()[0]);
      w = disabledWrites();
      expect(w.map((b) => textOf(b))).toEqual(['回滚到这一条之后']);
      expect(tipOf(w[0])).toBe('第二阶段接入');
      cleanup();
      vi.useRealTimers();
    }
  }, 60000);

  it('各页可用按钮只在白名单内（刷新/重新检查/重试、页签、[检索]、抽屉关闭钮、[复制 lock_sha256]），可用链接只有 [去设置]', async () => {
    const problems: string[] = [];
    for (const mock of ['data', 'offline', 'error', 'loading']) {
      for (const p of PAGES) {
        await mountApp('#/' + p.id + '?mock=' + mock);
        problems.push(...whitelistProblems(p.id + ' ' + mock));
        if (mock === 'data' || mock === 'offline') {
          if (p.id === 'plugins' || p.id === 'history') {
            await openByEnter(tbodyRows()[0]);
            problems.push(...whitelistProblems(p.id + ' ' + mock + ' 抽屉'));
          }
          if (p.id === 'logs') {
            await searchReal('logs[_ ]cat', '50');
            problems.push(...whitelistProblems('logs ' + mock + ' 检索结果'));
            const tab = Array.from(document.querySelectorAll('[role="tab"]')).find((t) => textOf(t) === '用量') as HTMLElement;
            fireEvent.click(tab);
            await settle();
            problems.push(...whitelistProblems('logs ' + mock + ' 用量'));
          }
        }
        cleanup();
      }
    }
    expect(problems).toEqual([]);
  }, 60000);
});
"""

# ---------------------------------------------------------------------------
# nonet 探针（D11）
# ---------------------------------------------------------------------------

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
async function advanceAsync(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe('D11 运行时不连服务', () => {
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

  it('四页逐个开关值渲染（含刷新、重试、打开抽屉、切页签、提交检索），四个浏览器网络接口与 sendBeacon 的调用次数都是 0', async () => {
    install();
    vi.useFakeTimers();
    try {
      for (const mock of [null, 'data', 'loading', 'empty', 'error', 'offline']) {
        for (const id of ['secrets', 'logs', 'plugins', 'history']) {
          const r = await mountApp('#/' + id + (mock ? '?mock=' + mock : ''));
          await advanceAsync(1500);
          for (const label of ['刷新', '重新检查', '重试']) {
            const b = maybeButton(document.body, label);
            if (b && !b.disabled) {
              fireEvent.click(b);
              await settle();
            }
          }
          if (id === 'plugins' || id === 'history') {
            const rows = Array.from(document.querySelectorAll('main tbody tr')) as HTMLElement[];
            if (rows.length > 1) {
              focusOn(rows[0]);
              key('Enter', {}, rows[0]);
              await settle();
              fireEvent.click(rows[1]);
              await settle();
              key('Escape');
            }
          }
          if (id === 'logs') {
            const tabs = Array.from(document.querySelectorAll('[role="tab"]')) as HTMLElement[];
            if (tabs.length === 2) {
              fireEvent.click(tabs[1]);
              await settle();
              fireEvent.click(tabs[0]);
              await settle();
              const btn = document.querySelector('[role="tabpanel"] button[type="submit"]');
              const form = btn && btn.closest('form');
              if (form) {
                fireEvent.change(form.querySelector('input:not([type="number"])') as Element, { target: { value: 'logs[_ ]cat' } });
                fireEvent.submit(form);
                await settle();
              }
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
  }, 120000);
});
"""

def _r2(*names):
    return [f"{R2_REL}/{n}" for n in names]


READERS_FILES = _r2("common-readers.ts") + [f"{MOCK_REL}/{n}" for n in MOCK_FILES]

# (键, 探针源码, 需要先存在的仓库文件)；所有用到 vi.mock 的探针都需要 common-readers.ts 在位
PROBE_SPECS = {
    "readers": (PROBE_READERS, READERS_FILES),
    "secrets": (PROBE_SECRETS, _r2("secrets-SecretsView.tsx", "secrets-logic.ts", "common-readers.ts")),
    "logs": (PROBE_LOGS, _r2("logs-LogsView.tsx", "logs-SearchPanel.tsx", "logs-SearchResults.tsx", "logs-UsagePanel.tsx", "logs-logic.ts",
                             "common-readers.ts")),
    "plugins": (PROBE_PLUGINS, _r2("plugins-PluginsView.tsx", "plugins-PluginDrawer.tsx", "plugins-logic.ts", "common-readers.ts")),
    "history": (PROBE_HISTORY, _r2("history-HistoryView.tsx", "history-HistoryDrawer.tsx", "history-KeyDiff.tsx", "history-logic.ts",
                                   "common-readers.ts")),
    "app": (PROBE_APP, _r2("secrets-SecretsView.tsx", "logs-LogsView.tsx", "plugins-PluginsView.tsx", "history-HistoryView.tsx",
                           "common-readers.ts") + [f"{MOCK_REL}/{n}" for n in MOCK_FILES]),
    "nonet": (PROBE_NONET, _r2("secrets-SecretsView.tsx", "logs-LogsView.tsx", "plugins-PluginsView.tsx", "history-HistoryView.tsx")),
}
PROBE_ORDER = ("readers", "secrets", "logs", "plugins", "history", "app", "nonet")


def probe_count(source):
    """探针里 ``it(`` 开头的行数；循环里的 it 一行可能跑多条，所以通过数只要求不少于它。drawerBehaviour 里的 6 个 it 另算。"""
    n = len(re.findall(r"^\s*it\(", source, re.M))
    if "function drawerBehaviour(" in source and not re.search(r"^drawerBehaviour\(", source, re.M):
        n -= len(re.findall(r"^    it\(", DRAWER_KIT, re.M))  # 只定义没调用：套件里的用例不会跑
    return n


def build_probe_source(key):
    return PROBE_SPECS[key][0]


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


# 流水线前后不该变的文件（相对 desktop/web）
WATCHED = ("package.json", "package-lock.json", "index.html", "vite.config.ts", "tsconfig.json",
           "src/styles/tokens.css", "src/styles/fonts.css", "src/styles/base.css", "src/main.tsx", "src/App.tsx", "src/App.css",
           "src/api.ts", "src/components/Drawer.tsx", "src/components/Drawer.css")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not any((REPO_ROOT / rel).is_file() for rel in NEW_SOURCE_FILES if rel.endswith((".ts", ".tsx"))):
        pipe.reason = ("候选里还没有 src/pages/readonly2/ 与 src/mock/readonly2-*.ts 的任何源码文件（基线），没有东西可测，未调用 npm；"
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
                name = f"probe-{uid}-t010-{key}.test.tsx"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                written.append(path)
                path.write_text(build_probe_source(key), encoding="utf-8", newline="\n")
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
# P 系列：流水线断言
# ---------------------------------------------------------------------------

def test_p1_d12_pipeline_steps_pass(pipeline):
    """P1 / D12（守卫）：npm ci、npm run build、npm test、npm run check:contract（W4）都退出 0；npm test 有通过的用例，
    没有失败、跳过、待办；Test Files 行没有失败（候选自己的九份 readonly2-* 测试与既有测试一起跑）。"""
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    step = pipeline.steps["npm test"]
    out = step.out
    assert re.search(r"Tests\s+(?:.*\|\s*)?\d+ passed", out), f"npm test 输出里没有 'Tests … N passed'：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", out), f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert re.search(r"Test Files\s+\d+ passed", out) and not re.search(r"Test Files\s+.*\bfailed\b", out), \
        f"npm test 的 Test Files 行异常：\n{step.tail}"


def test_d01_probe_secrets(pipeline):
    """secrets 探针 / D01：表四列（变量名、用在哪里、来源、操作）、没有「值」表头、rowHeight 44、夹具之外的值文字不出现；用在哪里按出现顺序、
    相邻 profile 合并、决策模型、未知 kind 原样带 id、「、」连接；遮蔽占位（变量名与 id）用 span.tt-masked（title 内核已遮蔽、含 LockIcon 14）且只有这三处；
    来源四种取值与未知值的文字、tone、图标（SecretsIcon 14、CircleXIcon 14、其余不带）、data-source；每行 [录入…] 禁用（secondary、sm、14 的图标）；
    表下不可关的 info 说明（不是 Banner）与「“来源”标签」小节；视图根 data-page=secrets 不写 data-page-state、不渲染 h1；说明原文、重新检查、没有刷新。"""
    assert_probe_ok(pipeline, "secrets")


def test_d02_d03_probe_logs(pipeline):
    """logs 探针 / D02、D03：Tabs（日志与用量；检索缺省、用量）切换不改地址不重挂载；用量——固定说明、合计与 token（下界）、四项千分位、三个计数标签（文字、tone、
    中文 title）、跳过的链接、规划端空状态与 [去设置] href（有 mock 时带上）、planner 非空的一行说明、按 attempt 表（状态 Tag 原样、tone、title、缺键与 null 显示未知）、
    按模型表（回报情况、占比一位小数、条宽内联 style、分母 0 显示「—」）、两个空文字；检索——表单默认值、任务选项去重、两条校验文字且不调用读取函数、提交恰调一次且参数正确、
    读取中转圈、只认最后一次请求、出错块（命令、退出码、messages 纯文本）、结果头与说明行顺序、空结果、分组与 N 处、path:line、条目不可点、高亮（mark、
    编译失败与带量词分组不高亮、空匹配跳过、回溯长行 1.5 秒内）、摘录与路径里的 <img onerror>、<script>、标签只是文字。"""
    assert_probe_ok(pipeline, "logs")


def test_d04_d05_probe_plugins(pipeline):
    """plugins 探针 / D04、D05：表（八列、rowHeight 40、版本 tt-num、启用三种写法加未知、锁与资源四类取值与图标、title 为 reason、缺的权限、状态与 reason、
    操作三种情形、无可聚焦单元格）；两个小节与「没有」；[核对全部] 禁用；isEmpty 规则；抽屉——点禁用钮不开、点「详情」行开；标题、warning 条、manifest 小节（dl 顺序、
    权限（缺）、列表、checks 不显示）、资源哈希（前 12 位加…、title 全文）、锁（generation、全文、复制三结果、不弹轻提示）、[重新核对] 禁用；读取中、出错（pre 纯文本）、
    过期回应丢弃；焦点与 Esc（Enter 与点击打开、aria-modal=false、无遮罩、焦点进关闭钮、400ms 内 Esc 回触发行、提示出现后两次 Esc、抽屉外 Esc 与点击不关、
    换行后焦点回后打开那行、关闭后选中行保留、切路由抽屉消失）。"""
    assert_probe_ok(pipeline, "plugins")


def test_d06_d07_probe_history(pipeline):
    """history 探针 / D06、D07：表（十列、倒序、#n tt-num、相对时间与 formatLocalUtc 的 title、解析不了原样无 title、资源、动作中文 title、对象、执行者五种 tone、
    确认、状态四种写法加（补判）与原状态码 title、改动的键 Tag 与遮蔽 note、外部改动标签）、两行注记、broken_lines 的 warning 条、isEmpty 规则；抽屉——标题、dl、
    外部改动条、键级差异五种情形（本机文件优先、非空数组 KeyDiff、空数组、遮蔽的两个分支加锁提示、其他）、KeyDiff 的 U+2212 与加号、未设置、JSON、遮蔽值、
    footer 两种说明与 [回滚到这一条之后] 禁用；读取中、出错、过期回应；焦点与 Esc 同插件抽屉。"""
    assert_probe_ok(pipeline, "history")


def test_transitional_readers_probe(pipeline):
    """接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据；页内读取函数并入 api.ts）

    readers 探针：common-readers.ts 的 searchLogs、getHistoryEntry、getPlugin——command 数组（logs search q [--task t] --max N、config history show n、
    plugins show id）、信封七个字段、已兑现的 Promise 不用计时器、五开关（loading 永不兑现、error 报错原文且先于参数校验、empty 时检索空结果、offline 同 data）、
    夹具之外的参数、固定模式 logs[_ ]cat 的检索夹具（两组以上、skipped_large、摘录 ≤ 200 字、路径后缀）、按 max 截断与 truncated、按 task 过滤、历史 42/41/40 与
    三个插件详情的夹具形状、深拷贝。"""
    assert_probe_ok(pipeline, "readers")


def test_transitional_app_probe_states_fixture_values_and_write_entries(pipeline):
    """接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据；页内读取函数并入 api.ts）

    app 探针：经 ?mock= 渲染 App 的四页五态（loading 299ms 无骨架 300ms 有；data；empty 时三页空态标题、日志仍是 data；error 的命令与退出码与报错原文；
    offline 的 role=alert、可能已过期、data-stale；整页恰一个 data-page-state）；夹具下的具体值（凭据两行、用量合计 22,031,448 与两行 attempt、检索真读取函数、
    docs-checks 抽屉、历史 #42/#41/#40 抽屉）；D09 写入口个数（凭据 2、日志 0、插件 3 抽屉开 4、历史 0 抽屉开 1，不含重新连接）与悬停 400ms 出现「第二阶段接入」，
    各页可用按钮只在白名单内、可用链接只有 [去设置]。"""
    assert_probe_ok(pipeline, "app")


def test_d11_probe_no_network(pipeline):
    """nonet 探针 / D11（守卫）：四页 × 六个开关值逐个渲染，含刷新、重试、打开并换行抽屉、切页签、提交检索，fetch、XMLHttpRequest、EventSource、WebSocket、
    sendBeacon 的调用次数都是 0。"""
    assert_probe_ok(pipeline, "nonet")


def test_p10_d12_worktree_unchanged_by_pipeline(pipeline):
    """P10 / D12（守卫）：流水线与探针前后 git status 相同；package.json、锁文件、index.html、vite.config.ts、tsconfig.json、tokens.css、fonts.css、base.css、
    main.tsx、App.tsx、App.css、api.ts、Drawer.tsx、Drawer.css 的摘要不变；gate-probe/ 没有留下。"""
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
/* readonly2 样式样本 */
.r2-card { background: var(--tt-surface-1); border: 1px solid var(--tt-border); border-radius: var(--tt-radius-lg); padding: var(--tt-space-3) var(--tt-space-4); }
.r2-card h2 { font: var(--tt-title-sm); margin: 0 0 var(--tt-space-2); }
.r2-w720 .tt-table { min-width: 720px; /* Secrets :67 */ }
.r2-w860 .tt-table { min-width: 860px; /* Plugins :70 */ }
.r2-w900 .tt-table { min-width: 900px; /* Logs :182 */ }
.r2-w1000 .tt-table { min-width: 1000px; /* History :67 */ }
.r2-track { height: 8px; /* Logs :237 */ border-radius: var(--tt-radius-full); background: var(--tt-surface-3); min-width: 60px; /* Logs :237 */ }
.r2-fill { height: 100%; background: var(--tt-navy-500); }
.r2-pct { width: 44px; /* Logs :237 */ }
.r2-line mark { background: var(--tt-highlight); color: var(--tt-text-1); border-radius: var(--tt-radius-sm); padding: 0 1px; }
.r2-del { background: var(--tt-diff-del); font: var(--tt-mono-sm); border-radius: var(--tt-radius-sm); padding: 1px var(--tt-space-1); }
.r2-add { background: var(--tt-diff-add); font: var(--tt-mono-sm); border-radius: var(--tt-radius-sm); padding: 1px var(--tt-space-1); }
.r2-key { word-break: break-all; }
.r2-dl { display: grid; grid-template-columns: 96px minmax(0, 1fr); /* Plugins :148 */ gap: var(--tt-space-1) var(--tt-space-3); }
.r2-res { display: grid; grid-template-columns: minmax(0, 1fr) 120px 64px; /* Plugins :158 */ }
.r2-res-head { height: 32px; /* Plugins :158 */ }
.r2-res-row { min-height: 36px; /* Plugins :159 */ }
.r2-form { display: flex; flex-wrap: wrap; gap: var(--tt-space-3); padding: var(--tt-space-3) var(--tt-space-4); }
.r2-q { flex: 1 1 320px; /* Logs :75 */ min-width: 0; }
.r2-task { width: 200px; /* Logs :86 */ }
.r2-max { width: 96px; /* Logs :93 */ }
.r2-res-top { padding: var(--tt-space-2) var(--tt-space-4); }
.r2-group { height: 32px; /* Logs :110 */ background: var(--tt-surface-2); }
.r2-path { font: var(--tt-mono-sm); color: var(--tt-text-2); }
.r2-excerpt { font: var(--tt-mono-md); white-space: pre; overflow: hidden; text-overflow: ellipsis; min-width: 0; }
.r2-total { font: var(--tt-display); }
.r2-note { background: var(--tt-tone-info-bg); color: var(--tt-tone-info-fg); border-radius: var(--tt-radius-md); }
.r2-icon-tag { gap: var(--tt-space-1); }
"""

GOOD_DRAWER_HEADER = ("/* 抽屉（插件页 :133–174、handoff :150）：靠右固定定位、底边让位标签栏、宽 520、最多 60%、层级 drawer；\n"
                      "   顶边让位 40 高的标题栏（插件页 :133）。 */\n")


def make_drawer_css(top="40px /* 插件页 :133 */", header=GOOD_DRAWER_HEADER, tweak=None):
    out = [header]
    for sel, decls in BASELINE_DRAWER_RULES:
        lines = []
        for name, value in decls:
            if sel == ".tt-drawer" and name == "top":
                value = top
            if tweak and tweak[0] == (sel, name):
                value = tweak[1]
            lines.append(f"  {name}: {value};")
        out.append(sel + " {\n" + "\n".join(lines) + "\n}\n")
    return "".join(out)


def test_gate_selfcheck_css_checks():
    """门禁自检：CSS 取值检查放得过合同写明的正确样本，拦得住改坏的样本；Drawer.css 检查同理；令牌与 px 注释检查。"""
    assert css_value_problems(GOOD_CSS) == [], css_value_problems(GOOD_CSS)
    mutants = {
        "最小宽 720 → 700": ("min-width: 720px;", "min-width: 700px;"),
        "占比条填充改金色": ("background: var(--tt-navy-500)", "background: var(--tt-brand-gold)"),
        "轨道高 8 → 10": ("height: 8px;", "height: 10px;"),
        "mark 底色改 surface-3": ("background: var(--tt-highlight)", "background: var(--tt-surface-3)"),
        "删除底色令牌": ("background: var(--tt-diff-del)", "background: var(--tt-surface-2)"),
        "新增底色令牌": ("background: var(--tt-diff-add)", "background: var(--tt-surface-2)"),
        "dl 列宽 96 → 100": ("grid-template-columns: 96px minmax(0, 1fr);", "grid-template-columns: 100px minmax(0, 1fr);"),
        "资源表列写裸 1fr": ("minmax(0, 1fr) 120px 64px", "1fr 120px 64px"),
        "检索框 flex": ("flex: 1 1 320px;", "flex: 1;"),
        "break-all 删掉": ("word-break: break-all;", "word-break: normal;"),
        "合计数字不是 display": ("font: var(--tt-display)", "font: var(--tt-title-sm)"),
    }
    for name, (old, new) in mutants.items():
        assert old in GOOD_CSS, name
        assert css_value_problems(GOOD_CSS.replace(old, new, 1)), f"改坏样本没被拦住：{name}"
    assert px_literal_problems("x", GOOD_CSS) == []
    assert px_literal_problems("x", ".a { width: 33px; }")
    assert token_only_problems("x", GOOD_CSS) == []
    assert token_only_problems("x", ".a { border-radius: 6px; }")
    assert css_w4_problems("x", GOOD_CSS) == [] and css_w4_problems("x", ".a { color: #12abef; }") and css_w4_problems("x", ".a { color: rgb(1,2,3); }")
    good = make_drawer_css()
    assert drawer_css_problems(good) == [], drawer_css_problems(good)
    assert drawer_css_problems(make_drawer_css(top="0"))
    assert drawer_css_problems(make_drawer_css(top="40px"))  # 同一行没有出处注释
    assert drawer_css_problems(make_drawer_css(header="/* 顶边取 0（本片没有标题栏） */\n"))
    assert drawer_css_problems(make_drawer_css(tweak=((".tt-drawer", "width"), "480px")))
    assert drawer_css_problems(make_drawer_css(tweak=((".tt-drawer", "z-index"), "10")))
    assert drawer_css_problems(make_drawer_css(tweak=((".tt-drawer__head", "gap"), "var(--tt-space-2)"))) == [], "不冻结其余规则"


def test_gate_selfcheck_source_guards():
    """门禁自检：源码守卫放得过干净样本，拦得住禁用词、整词网络接口、role=status、颜色形态、ServerIcon、字体引用、data-page-state、h1、Intl、非 type 的 api 引入。"""
    clean = "import { Tag } from '../../components';\nexport const a = 1; // 说明\nconst s = `x`;\n"
    assert source_guard_problems("x", clean) == []
    assert readonly2_rule_problems("x", "import type { UsageData } from '../../api';\nexport const a = 1;\n") == []
    bads = [
        "el.innerHTML = 'x';", "const f = new Function('x');", "document.write('x')", "retrieval(x)", "// git fetch origin\n",
        "const a = new WebSocket('x');", "<div role=\"status\" />", "const c = '#12abef';", "// 颜色 #fff\n", "const c = 'rgb(1, 2, 3)';",
        "<ServerIcon />", "import f from './a.woff2';", "window.matchMedia('x');", "x.scrollIntoView();", "const n = document.fonts;",
        "new ResizeObserver(() => {});",
    ]
    for bad in bads:
        assert source_guard_problems("x", bad), f"没拦住：{bad}"
    assert source_guard_problems("x", "const a = 1; // 编号 #123 不是颜色\n"), "井号加三位十进制数字也形如十六进制：守卫按合同一并拦"
    assert readonly2_rule_problems("x", "<div data-page-state='data' />")
    assert readonly2_rule_problems("x", "<div {...{ 'data-page-state': 'data' }} />")
    assert readonly2_rule_problems("x", "// 视图不写 data-page-state（由 PageFrame 写）\n/* data-page-state */\nexport const a = 1;\n") == []
    assert readonly2_rule_problems("x", "return <h1>标题</h1>;")
    assert readonly2_rule_problems("x", "n.toLocaleString()")
    assert readonly2_rule_problems("x", "new Intl.NumberFormat()")
    assert readonly2_rule_problems("x", "import { getUsage } from '../../api';")
    assert readonly2_rule_problems("x", "import { type UsageData, getUsage } from '../../api';")
    assert readonly2_rule_problems("x", "import { type UsageData, type HistoryData } from '../../api';") == []


def test_gate_selfcheck_helpers():
    """门禁自检：CSS 小解析器、box_sides、sides_is、HasAll、strip_ts_comments、word_hits 的基本行为。"""
    rules = parse_rules(".a, .b { padding: 1px var(--tt-space-1); gap: 2px 3px } @media (x) { .c { top: 0 } }")
    assert [s for s, _d in rules] == [".a, .b", ".c"]
    assert sides_is("padding", top="1px", right="var(--tt-space-1)")(rules[0][1])
    assert not sides_is("padding", top="2px")(rules[0][1])
    assert HasAll(("gap",), "2px", "3px")(rules[0][1])
    assert strip_ts_comments("a // b\n/* c */ d") .replace(" ", "").replace("\n", "") == "ad"
    assert word_hits("git fetch x; prefetch", NETWORK_WORDS) == [(1, "fetch")]
    assert cv(" 1  1 320px !important") == "11320px"
    assert minmax_problems(".a { grid-template-columns: 1fr 2fr; }") and not minmax_problems(".a { grid-template-columns: minmax(0, 1fr) 64px; }")


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
    """门禁自检：每份探针都有用例；PROBE_ORDER 与 PROBE_SPECS 对得上；探针里不写 skip、only、todo；括号配对；
    探针用到的页内读取函数、data-* 与合同一致；过渡断言恰两条。"""
    assert set(PROBE_ORDER) == set(PROBE_SPECS)
    for key in PROBE_ORDER:
        source = build_probe_source(key)
        assert probe_count(source) >= 1, key
        assert not re.search(r"\.(skip|only|todo)\b|\bxit\(|\bxdescribe\(", source), key
        assert js_bracket_problems(source) == [], f"探针 {key} 的括号：{js_bracket_problems(source)}"
        for rel in PROBE_SPECS[key][1]:
            assert rel.startswith(f"{R2_REL}/") or rel.startswith(f"{MOCK_REL}/"), rel
    # 每份探针是独立文件：顶层辅助函数与常量只能用自己源码里定义的，且同一探针里不能重复声明
    decl_re = re.compile(r"^(?:async\s+)?function\s+(\w+)|^(?:const|let|var)\s+(\w+)\s*=", re.M)
    declared = {}
    for key in PROBE_ORDER:
        names = [a or b for a, b in decl_re.findall(build_probe_source(key))]
        dup = sorted({n for n in names if names.count(n) > 1})
        assert dup == [], f"探针 {key} 重复声明顶层名字：{dup}"
        declared[key] = set(names)
    every_name = set().union(*declared.values())
    for key in PROBE_ORDER:
        source = build_probe_source(key)
        used = {n for n in every_name if re.search(rf"(?<![\w.$]){n}\(", source)}
        missing = sorted(used - declared[key])
        assert missing == [], f"探针 {key} 用到了只在别的探针里定义的函数：{missing}"
    assert js_bracket_problems("a(b[c{d}])") == [] and js_bracket_problems("a(b]") and js_bracket_problems("f('x)")
    assert js_bracket_problems("f('(' + \"]\" + `{`)") == []
    # 用到 vi.mock 读取函数模块的探针必须要求 common-readers.ts 在位
    for key, (source, needs) in PROBE_SPECS.items():
        if "common-readers" in source:
            assert f"{R2_REL}/common-readers.ts" in needs, key
    assert sum(1 for name in dir(sys.modules[__name__]) if name.startswith("test_transitional_")) == 2
    for name in dir(sys.modules[__name__]):
        if name.startswith("test_transitional_"):
            doc = getattr(sys.modules[__name__], name).__doc__.splitlines()[0]
            assert doc == "接本机服务那一片推翻（夹具与 ?mock= 开关换成真实数据；页内读取函数并入 api.ts）", name


def test_gate_selfcheck_constants_match_contract():
    """门禁自检：合同写明的文件清单——readonly2 下 23 个源码与样式文件（T013 并走两个）加 3 个夹具；页面文件 4 个；九份执行端测试；基线的 14 份 JSON 与 9 个页面文件名。"""
    assert len(R2_FILES) == 23 and len(set(R2_FILES)) == 23
    assert len(MOCK_FILES) == 3 and len(NEW_SOURCE_FILES) == 26
    assert len(EXECUTOR_TESTS) == 9 and len(set(EXECUTOR_TESTS)) == 9
    assert len(BASELINE_JSON) == 14 and len(BASELINE_PAGES) == 9 and len(PAGE_FILES) == 4
    assert all(n.endswith((".tsx", ".ts", ".css")) for n in R2_FILES)
    assert not any(n.endswith("Page.tsx") for n in R2_FILES)


def test_gate_selfcheck_executor_test_checker(tmp_path, monkeypatch):
    """门禁自检：执行端测试检查对全部在位、无 skip 的样本通过；缺文件、没有用例、写了 skip / only / todo 都会报。"""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    for name in EXECUTOR_TESTS:
        (tests_dir / name).write_text("it('x', () => {});\n", encoding="utf-8")
    monkeypatch.setitem(globals(), "WEB", tmp_path)
    assert executor_test_problems() == []
    for bad in ("it.skip('x', () => {});\n", "describe('x', () => { it.only('y', () => {}); });\n", "it.todo('x');\n", "// 没有用例\n"):
        (tests_dir / EXECUTOR_TESTS[0]).write_text(bad, encoding="utf-8")
        assert executor_test_problems(), bad
    (tests_dir / EXECUTOR_TESTS[0]).unlink()
    assert executor_test_problems()
