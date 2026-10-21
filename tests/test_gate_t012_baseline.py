"""T012 战前门禁：桌面端前端外壳页——首次启动、设置、服务状态与恢复（第十一片）的黑盒基准测试
（合同 t012-desktop-shellpages，plan_version 1，基线 ce051d4）。

被测对象是 ``desktop/web/``：``src/shellpages/`` 下的 themisShell 接口与内存桩、外壳窗口外框、首次启动视图、服务状态视图、
设置的五组视图、两个对话框、主题 context、图标与夹具；``src/App.tsx`` 按合同 §2.3 的一处改动（根上的外壳窗口分支、主题上提）；
``src/pages/SettingsPage.tsx`` 换成用 PageFrame 的外壳设置页；``src/mock/shellpages-scenarios.ts``；执行端自己的 8 份 tests/shellpages-*。

基线上这些都还没有，所以本文件的“失败”断言落在目标文件不存在或内容不符上，不是导入、收集或语法错误：模块级只导入标准库，
用到被测文件的地方都在用例函数里读；候选里还没有任何 ``src/shellpages/`` 的源码时，``pipeline`` 夹具不跑 npm（没有东西可测，
也省掉联网的 ``npm ci``），用到它的用例以断言失败写明原因。

结构（用例名里带 ``dNN`` 的对应合同 DoD；门禁端加了若干自检）：

- 静态断言（不用流水线，全量 pytest 也跑）：文件在位（D01）、接口十个成员与补丁类型没有路径键（D01）、夹具 .ts 与扫描（D01、D11）、
  源码守卫（D11）、样式出处与取值（D12）、接线（K20，D12）、App.tsx 只有 §2.3 的改动与 :72 一字不改（D13）、执行端 8 份测试在位且不用
  skip/only/todo（D13）、隔离的静态部分（D10）。
- 流水线断言：会话级夹具 ``pipeline`` 在 ``desktop/web`` 下按顺序跑 ``npm ci``、``npm run build``、``npm test``、
  ``npm run check:contract``，再把 7 份探针写成 ``gate-probe/probe-t012-<唯一标识>-<键>.test.tsx``，一次 ``npm test -- gate-probe --reporter=json``
  跑完，``finally`` 里删除；前后各取一次 ``git status``。全量 pytest 默认跳过用到 ``pipeline`` 的用例（``tests/conftest.py``），点名运行本文件时才跑。
  构建之后还要在 ``dist/assets`` 的 css 里找每份新 css 独有的类名（K20，从源文件解析，不写死）。
- 门禁自检（``test_gate_selfcheck_*``，不依赖候选）：把检查函数喂给正确样本和改坏的样本。

探针（Vitest + jsdom）与 DoD 的对应：

- stub：D02（桩的方法、深拷贝、不经计时器兑现、saveSettings 只认约定键、start/restart 幂等与事件、dispose、openExternal 只认 http/https）；
  桩夹具的取值与 1500ms、pid 是过渡断言（合同“过渡与长期断言”）。
- route：D03（parseShellWindow、整窗渲染、服务窗口不挂载、手改地址后手动派发 HashChangeEvent、navigateShell 同步写地址与保留查询串）。
- firstrun：D04、D05（四步状态、六种错误、自动启动恰一次、[进入]、复制三种结果、退出码 1 的禁用按钮）。
- service：D06（退出码 1、2、3，重启后跳回，推送 exited 换新）。
- settings：D07、D08（无 Provider 时本地状态）、D09（关于、许可清单、外部链接先确认）。
- app：D08（主题经 App 与标题栏同步、去过外壳窗口再回来主题不变、不写存储）。
- isolation：D10（api 替身 0 次、网络替身 0 次、window.open 0 次）。

写法约定：F4 未核实，站主放行——探针不靠假计时器推进 jsdom 的 hashchange：经 navigateShell 的跳转点击后直接断言；手改地址写
``location.hash`` 后在 act 里手动派发 ``HashChangeEvent``。假计时器只推进桩自己的 1500ms 与 Tooltip 的 400ms，要在挂载之前打开。
合同没有给出签名的地方（parseShellWindow 的参数、service 事件的判别字段、ThemisShellProvider 的属性名、各视图的内部类名、data-step 与
data-status 的取值）不猜：探针经 App 与 ``useThemisShell`` 取到按场景缓存的桩实例，用 ``vi.spyOn`` 给实例的方法套替身（照常调用原方法），
data-step 只按出现顺序取 4 个，data-status 只比较“相同或不同”。站主决定不被推翻：Q1 :72 一字不改，Q2 退出码 1 的“切换到那个窗口”是禁用按钮，
C1 九页不再断言占位文字，C2 ?mock=empty 的 data 照常，C3 首启不做第 5 步“工人”。

过渡断言（``test_transitional_`` 开头）：进入地址与 shell= 开关、桩夹具的取值、依赖这些场景的首启/服务状态/设置视图用例、
退出码 1 的提示文字、App.tsx 只有 §2.3 的改动——后续接真实外壳或再改 App.tsx 的片推翻。

门禁做不到、留给人的项（合同 H1–H11）：与画布并排的视觉对照（暗色、亮色）、真浏览器里的字体与 Logo 尺寸、真机上 hashchange 时序、
读屏抽查、?mock=offline 时设置页的断线横幅（已知差异 H11）。
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
from html.parser import HTMLParser
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_REL = "desktop/web"
WEB = REPO_ROOT / "desktop" / "web"
SRC_REL = f"{WEB_REL}/src"
SRC = WEB / "src"
SP_REL = f"{SRC_REL}/shellpages"
TESTS_REL = f"{WEB_REL}/tests"
CANVAS_DIR = REPO_ROOT / "docs" / "ui-design" / "pages"
FIRST_RUN_CANVAS = CANVAS_DIR / "03-首次启动-Themis-Tally.html"
SETTINGS_CANVAS = CANVAS_DIR / "12-设置-Themis-Tally.html"

SHELLPAGES_FILES = (
    "themisShell.ts", "shellStub.ts", "shellContext.tsx", "shellWindowRoute.ts", "ShellWindow.tsx", "shell-window.css",
    "firstRunModel.ts", "FirstRunView.tsx", "first-run.css", "exitCodes.ts", "ServiceStatusView.tsx", "service-status.css",
    "SettingsView.tsx", "settings.css", "ExternalLinkDialog.tsx", "LicensesDialog.tsx", "licenses.ts", "themePref.tsx",
    "copy.ts", "format.ts", "icons.tsx",
)
SCENARIOS_REL = f"{SRC_REL}/mock/shellpages-scenarios.ts"
NEW_SOURCE_FILES = tuple(f"{SP_REL}/{name}" for name in SHELLPAGES_FILES) + (SCENARIOS_REL,)
NEW_CSS = tuple(f"{SP_REL}/{name}" for name in SHELLPAGES_FILES if name.endswith(".css"))
EXECUTOR_TESTS = ("shellpages-stub.test.ts", "shellpages-route.test.ts", "shellpages-first-run.test.tsx",
                  "shellpages-service-status.test.tsx", "shellpages-settings.test.tsx", "shellpages-app.test.tsx",
                  "shellpages-isolation.test.tsx", "shellpages-static.test.ts")
SCENARIOS = ("ready", "checking", "first-launch", "not-git", "no-agent", "no-python", "no-kit", "exit-1", "exit-2", "crash", "custom")
INTERFACE_MEMBERS = ("getState", "pickRepo", "pickPython", "pickKit", "pickTranscriptDir", "saveSettings", "startService",
                     "restartService", "openExternal", "on")
PATCH_KEYS = ("theme", "density", "removeRepo", "removeTranscriptDir", "resetPython", "resetKit")

# 合同“公共约定”：静态检查禁用词。
NET_WORDS = ("fetch", "XMLHttpRequest", "EventSource", "WebSocket")
FORBIDDEN_WORDS = ("dangerouslySetInnerHTML", "innerHTML", "outerHTML", "insertAdjacentHTML", "eval(", "new Function",
                   "document.write", "srcdoc", "createContextualFragment", "DOMParser")
FORBIDDEN_CALLS = ("matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver")
FONT_WORDS = (".woff2", ".woff", ".ttf", ".otf", "sarasa-mono-sc-", "@font-face", "FontFace")
SHOWCASE_TEXTS = ("字体 · 等距更纱黑体 SC", "Button 按钮", "Banner 提示条", "弹出轻提示", "已复制到剪贴板", "showcase__")

# 基线 ce051d4 的 src/App.tsx（行尾归一为 LF）里，合同 §2.3 要求原样保留的非空行（第 4–17 行的导入；原 :21–24、:30–87 的函数体）。
# 原 :19、:20、:26–28 被移走或改写，:1–3 的文件头注释只许在末尾加一句，不在这里比。
BASELINE_APP_KEEP = (
    "import { useEffect, useState } from 'react';",
    "import { getMetaNow, getStatus } from './api';",
    "import { TABS } from './shell/routes';",
    "import { useHashRoute } from './shell/router';",
    "import { installShortcuts } from './shell/shortcuts';",
    "import { applyTheme, type ThemePref } from './shell/theme';",
    "import { TitleBar } from './shell/TitleBar';",
    "import { TabBar } from './shell/TabBar';",
    "import { ShellStatusProvider, type PageReport } from './shell/ShellStatusContext';",
    "import { countByGroup, type StatusCounts } from './shell/attemptGroups';",
    "import { currentMock } from './mock/scenario';",
    "import { shellConnectionState } from './mock/shell';",
    "import ShowcasePage from './showcase/ShowcasePage';",
    "import './App.css';",
    "  const { route, navigate } = useHashRoute();",
    "  const meta = getMetaNow();",
    "  const [counts, setCounts] = useState<StatusCounts | null>(null);",
    "  const [page, setPage] = useState<PageReport>({ phase: 'loading', at: null });",
    "  // 快捷键：Ctrl+1…8 切前 8 个 Tab，Ctrl+, 切设置。",
    "  useEffect(",
    "    () =>",
    "      installShortcuts((tabId) => {",
    "        const tab = TABS.find((t) => t.id === tabId);",
    "        if (tab) navigate(tab.path);",
    "      }),",
    "    [navigate],",
    "  );",
    "  // document.title：页面标题 · Themis Tally；陈列页写 组件陈列 · Themis Tally。",
    "  useEffect(() => {",
    "    const tab = TABS.find((t) => t.id === route.pageId);",
    "    document.title =",
    "      route.pageId === 'showcase' ? '组件陈列 · Themis Tally' : `${tab?.title ?? '总览'} · Themis Tally`;",
    "  }, [route.pageId]);",
    "  // 外壳级 getStatus 计数；随 ?mock= 变化重取，未读到显示 —。",
    "  useEffect(() => {",
    "    let alive = true;",
    "    setCounts(null);",
    "    getStatus().then((env) => {",
    "      if (!alive) return;",
    "      if (env.ok && env.data) setCounts(countByGroup(env.data));",
    "    });",
    "    return () => {",
    "      alive = false;",
    "    };",
    "  }, [route.query]);",
    "  const offline = shellConnectionState(currentMock()) === 'disconnected';",
    "  const routeKey = `${route.pageId}|${route.segments.join('/')}|${route.query}`;",
    "  const renderPage = () => {",
    "    if (route.pageId === 'showcase') return <ShowcasePage />;",
    "    const tab = TABS.find((t) => t.id === route.pageId) ?? TABS[0];",
    "    return <tab.Page />;",
    "  };",
    "  return (",
    "    <ShellStatusProvider value={setPage}>",
    "      <div className=\"tt-app tt-shell\">",
    "        <TitleBar theme={theme} onThemeChange={setTheme} repoName={meta.repo_name} />",
    "        <TabBar",
    "          route={route}",
    "          navigate={navigate}",
    "          counts={counts}",
    "          page={page}",
    "          kitVersion={meta.kit_version}",
    "          repoName={meta.repo_name}",
    "          offline={offline}",
    "        />",
    "        <main className=\"tt-shell__content tt-content\" key={routeKey}>",
    "          {renderPage()}",
    "        </main>",
    "      </div>",
    "    </ShellStatusProvider>",
    "  );",
    "}",
)
TITLEBAR_LINE = "<TitleBar theme={theme} onThemeChange={setTheme} repoName={meta.repo_name} />"
APP_IMPORT_SHELL_WINDOW = "import { ShellWindow, useShellWindowRoute } from './shellpages/ShellWindow';"
APP_IMPORT_THEME_PREF = "import { ThemePrefProvider } from './shellpages/themePref';"
APP_MAX_NEW_LINES = 34


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


def rel(path):
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def sp(name):
    return REPO_ROOT / SP_REL / name


def new_ts_files():
    """本片新增的 ts、tsx（含夹具），加上被改的 App.tsx 与 SettingsPage.tsx：源码守卫扫它们。"""
    files = [REPO_ROOT / r for r in NEW_SOURCE_FILES if r.endswith((".ts", ".tsx")) and (REPO_ROOT / r).is_file()]
    files += [p for p in (SRC / "App.tsx", SRC / "pages" / "SettingsPage.tsx") if p.is_file()]
    return files


def new_tsx_view_files():
    return [p for p in new_ts_files() if p.suffix == ".tsx" and p.parent.name in ("shellpages", "pages")]


# ---------------------------------------------------------------------------
# CSS 小解析器
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


def css_has(css, props, token, selector_re=None):
    """有没有一条规则声明了 props 里某个属性（以 ``*`` 结尾的按前缀），归一后的值含 token（也归一）。"""
    want = cv(token)
    for selector, decls in parse_rules(css):
        if selector_re and not re.search(selector_re, selector):
            continue
        for name, value in decls:
            hit = any(name == p or (p.endswith("*") and name.startswith(p[:-1])) for p in props)
            if hit and want in cv(value):
                return True
    return False


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
    """层级、圆角、阴影、字体只用 --tt-* 令牌。"""
    problems = []
    for selector, decls in parse_rules(css):
        for name, value in decls:
            v = cv(value)
            if name == "z-index" and not v.startswith("var(--tt-z-"):
                problems.append(f"{label}：{selector} 的 z-index 应取 --tt-z-* 令牌，实际 {value}")
            elif name == "border-radius" and not re.fullmatch(r"(?:var\(--tt-radius-[\w-]+\)|0|0px|50%)+|inherit", v):
                problems.append(f"{label}：{selector} 的 border-radius 应取 --tt-radius-* 令牌（圆形可写 50%），实际 {value}")
            elif name == "box-shadow" and v != "none" and "var(--tt-" not in v:
                problems.append(f"{label}：{selector} 的 box-shadow 应取令牌，实际 {value}")
            elif name in ("font", "font-family", "font-size") and not (v.startswith("var(--tt-") or v == "inherit"):
                problems.append(f"{label}：{selector} 的 {name} 应取 --tt-* 字体令牌或 inherit，实际 {value}")
    return problems


def tokens_defined():
    text = _read(SRC / "styles" / "tokens.css")
    return set(re.findall(r"(--tt-[A-Za-z0-9_-]+)\s*:", text))


def css_token_problems(label, css_raw):
    """合同公共约定：用到的 --tt- 名都在 tokens.css 里；不在 css 里声明 --tt- 自定义属性；不写 [data-theme] 选择器、不写内联 style 之外的颜色字面量由 W4 另查。"""
    problems = []
    defined = tokens_defined()
    text = strip_comments(css_raw)
    for m in re.finditer(r"(--tt-[A-Za-z0-9_-]+)(\s*:)?", text):
        if m.group(2):
            problems.append(f"{label}：不能在 css 里声明自定义属性 {m.group(1)}")
        elif m.group(1) not in defined:
            problems.append(f"{label}：用了 tokens.css 里没有定义的 {m.group(1)}")
    if re.search(r"\[\s*data-theme", text):
        problems.append(f"{label}：不能写 [data-theme] 选择器（主题由 theme.ts 写 data-theme，样式只用令牌）")
    return problems


HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![0-9a-fA-F])")
COLOR_FUNC_RE = re.compile(r"\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch|color)[ \t]*\(", re.I)


def w4_pitfall_problems(files):
    """W4 的坑（合同公共约定）：只剥块注释，字符串也扫；不出现井号加 3/4/6/8 位十六进制、颜色函数名加括号、拼接 --tt- 前缀。"""
    problems = []
    for path in files:
        text = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), _read(path), flags=re.S)
        label = rel(path)
        for m in HEX_RE.finditer(text):
            problems.append(f"{label}:{text[:m.start()].count(chr(10)) + 1} 出现十六进制颜色形态 {m.group(0)}")
        for m in COLOR_FUNC_RE.finditer(text):
            problems.append(f"{label}:{text[:m.start()].count(chr(10)) + 1} 出现颜色函数形态 {m.group(0)}")
        for m in re.finditer(r"""[`'"][^`'"\n]*--tt-[^`'"\n]*\$\{""", text):
            problems.append(f"{label}:{text[:m.start()].count(chr(10)) + 1} 拼接了 --tt- 令牌名")
    return problems


def word_problems(files, words, whole=False):
    problems = []
    for path in files:
        text = _read(path)
        for word in words:
            pattern = rf"\b{re.escape(word)}\b" if whole else re.escape(word)
            m = re.search(pattern, text)
            if m:
                problems.append(f"{rel(path)}:{text[:m.start()].count(chr(10)) + 1} 出现 {word}")
    return problems


def role_and_interface_problems(label, raw):
    problems = []
    code = strip_ts_comments(raw)
    if re.search(r"""role\s*[=:]\s*\{?\s*["']status["']""", code):
        problems.append(f"{label}：不能渲染 role=status（首启第 4 步用 aria-live=polite）")
    for name in FORBIDDEN_CALLS:
        if re.search(rf"\b{name}\b", code):
            problems.append(f"{label}：不能用 {name}")
    return problems


def inline_style_problems(files):
    problems = []
    for path in files:
        code = strip_ts_comments(_read(path))
        if re.search(r"\bstyle\s*=\s*[{\"']", code) or re.search(r"\.style\.|setAttribute\(\s*['\"]style['\"]|\bcssText\b", code):
            problems.append(f"{rel(path)}：不写内联 style")
    return problems


def forbidden_api_problems(files):
    """公共约定与 D10 的静态部分：不写 localStorage、sessionStorage、window.open、window.confirm、window.themisHost，
    不声明也不读 window.themisShell，不引 ServerIcon。"""
    problems = []
    for path in files:
        code = strip_ts_comments(_read(path))
        label = rel(path)
        for pat, what in ((r"\blocalStorage\b", "localStorage"), (r"\bsessionStorage\b", "sessionStorage"),
                          (r"\bwindow\s*\.\s*open\b|\bwindow\s*\[\s*['\"]open['\"]\s*\]", "window.open"),
                          (r"\bwindow\s*\.\s*confirm\b|\bwindow\s*\[\s*['\"]confirm['\"]\s*\]", "window.confirm"),
                          (r"\bthemisHost\b", "themisHost"),
                          (r"window\s*(?:\.|\[\s*['\"])themisShell|declare\s+global|globalThis\s*(?:\.|\[\s*['\"])themisShell",
                           "window.themisShell 的声明或读取"),
                          (r"\bServerIcon\b", "ServerIcon（应用已有的 ServerCrashIcon）")):
            if re.search(pat, code):
                problems.append(f"{label}：不能出现 {what}")
    return problems


def api_import_problems(files):
    """D10 静态：shellpages/** 与 SettingsPage.tsx 的导入里没有 api 模块（含 import type）。"""
    problems = []
    for path in files:
        code = strip_ts_comments(_read(path))
        for spec in import_specs(code):
            if re.search(r"(^|/)api(\.ts)?$", spec):
                problems.append(f"{rel(path)}：不能导入 api 模块（{spec}）")
    return problems


# ---------------------------------------------------------------------------
# 导入图（K20 接线）
# ---------------------------------------------------------------------------

_IMPORT_RES = (
    re.compile(r"""(?:^|\n)\s*(?:import|export)\b[^;'"]*?\bfrom\s*['"]([^'"]+)['"]"""),
    re.compile(r"""(?:^|\n)\s*import\s*['"]([^'"]+)['"]"""),
    re.compile(r"""\bimport\(\s*['"]([^'"]+)['"]\s*\)"""),
)


def import_specs(text):
    out = []
    for regex in _IMPORT_RES:
        out += regex.findall(text)
    return out


def resolve_import(from_file, spec):
    if not spec.startswith("."):
        return None
    base = (Path(from_file).parent / spec)
    cands = [base] + [Path(str(base) + ext) for ext in (".ts", ".tsx", ".css")] + \
            [base / "index.ts", base / "index.tsx"]
    for cand in cands:
        if cand.is_file():
            return cand.resolve()
    return None


def reachable_files(roots):
    seen, todo = set(), [Path(r).resolve() for r in roots if Path(r).is_file()]
    while todo:
        cur = todo.pop()
        if cur in seen:
            continue
        seen.add(cur)
        if cur.suffix not in (".ts", ".tsx"):
            continue
        for spec in import_specs(strip_ts_comments(_read(cur))):
            nxt = resolve_import(cur, spec)
            if nxt is not None and nxt not in seen:
                todo.append(nxt)
    return seen


def imports_of(path):
    return import_specs(strip_ts_comments(_read(path)))


def wiring_problems(root=None):
    """K20：每份新 css 都被一个能从 App.tsx 或 pages/SettingsPage.tsx 经 import 走到的 ts、tsx import；
    ShellWindow.tsx 引入 shell-window.css，App.tsx 引入 ShellWindow 与 ThemePrefProvider，SettingsPage 渲染 SettingsView，
    各视图引入自己的 css。"""
    problems = []
    web = Path(root) if root else WEB
    src, sp_dir = web / "src", web / "src" / "shellpages"
    reach = reachable_files([src / "App.tsx", src / "pages" / "SettingsPage.tsx"])
    for css in sorted(sp_dir.glob("*.css")):
        importers = []
        for ts in sp_dir.glob("*.ts*"):
            if any(resolve_import(ts, s) == css.resolve() for s in imports_of(ts)):
                importers.append(ts)
        if not importers:
            problems.append(f"{css.name} 没有被任何 shellpages 下的 ts、tsx import")
        elif not any(ts.resolve() in reach for ts in importers):
            problems.append(f"{css.name} 的 importer {[p.name for p in importers]} 从 App.tsx 与 SettingsPage.tsx 走不到")
    own = {"ShellWindow.tsx": "shell-window.css", "FirstRunView.tsx": "first-run.css",
           "ServiceStatusView.tsx": "service-status.css", "SettingsView.tsx": "settings.css"}
    for view, css in own.items():
        path = sp_dir / view
        if not path.is_file():
            problems.append(f"{view} 不存在")
        elif not any(resolve_import(path, s) == (sp_dir / css).resolve() for s in imports_of(path)):
            problems.append(f"{view} 没有 import 自己的 {css}")
    app = src / "App.tsx"
    if app.is_file():
        specs = imports_of(app)
        if not any(s.endswith("shellpages/ShellWindow") for s in specs):
            problems.append("App.tsx 没有 import ./shellpages/ShellWindow")
        if not any(s.endswith("shellpages/themePref") for s in specs):
            problems.append("App.tsx 没有 import ./shellpages/themePref")
        code = strip_ts_comments(_read(app))
        if "<ThemePrefProvider" not in code or "<ShellWindow" not in code:
            problems.append("App.tsx 没有渲染 <ThemePrefProvider> 与 <ShellWindow>")
    page = src / "pages" / "SettingsPage.tsx"
    if page.is_file():
        if not any(s.endswith("shellpages/SettingsView") for s in imports_of(page)):
            problems.append("SettingsPage.tsx 没有 import SettingsView")
        if "<SettingsView" not in strip_ts_comments(_read(page)):
            problems.append("SettingsPage.tsx 没有渲染 <SettingsView>")
    view = sp_dir / "SettingsView.tsx"
    if view.is_file() and not any(s.endswith("themePref") for s in imports_of(view)):
        problems.append("SettingsView.tsx 没有 import themePref（主题经 context 交给设置页）")
    window = sp_dir / "ShellWindow.tsx"
    if window.is_file():
        code = strip_ts_comments(_read(window))
        for name in ("FirstRunView", "ServiceStatusView"):
            if f"<{name}" not in code:
                problems.append(f"ShellWindow.tsx 没有渲染 <{name}>")
    return problems


# ---------------------------------------------------------------------------
# App.tsx 只有 §2.3 的改动
# ---------------------------------------------------------------------------

def app_tsx_problems(text):
    problems = []
    text = _norm(text)
    lines = text.split("\n")
    if not text.rstrip("\n").startswith("//"):
        problems.append("App.tsx 开头应是文件头注释")
    head = "\n".join(lines[:8])
    if "#/first-run" not in head or "#/service-status" not in head or "ThemePrefProvider" not in head:
        problems.append("App.tsx 文件头注释末尾应加一句：#/first-run、#/service-status 由根上的外壳窗口整窗渲染，主题偏好在根上、经 ThemePrefProvider 交给设置页")
    # 保留的行按顺序出现
    pos = 0
    for want in BASELINE_APP_KEEP:
        try:
            pos = lines.index(want, pos) + 1
        except ValueError:
            problems.append(f"App.tsx 缺少（或顺序被改）基线里要原样保留的行：{want.strip()[:90]}")
            break
    if lines.count("        " + TITLEBAR_LINE) != 1:
        problems.append(f"App.tsx 里 :72 的 `{TITLEBAR_LINE}` 要一字不改（含缩进 8 格），且恰一处")
    if APP_IMPORT_SHELL_WINDOW not in lines:
        problems.append(f"App.tsx 缺导入：{APP_IMPORT_SHELL_WINDOW}")
    if APP_IMPORT_THEME_PREF not in lines:
        problems.append(f"App.tsx 缺导入：{APP_IMPORT_THEME_PREF}")
    if len(re.findall(r"^export default function App\(\)", text, re.M)) != 1:
        problems.append("App.tsx 应恰有一处 export default function App()")
    if not re.search(r"^function ServiceApp\(\{\s*theme,\s*setTheme\s*\}: ServiceAppProps\)", text, re.M):
        problems.append("App.tsx 原函数体应改名 function ServiceApp({ theme, setTheme }: ServiceAppProps)")
    if not re.search(r"interface ServiceAppProps\s*\{\s*theme: ThemePref;\s*setTheme: \(pref: ThemePref\) => void;\s*\}", text):
        problems.append("App.tsx 应有 interface ServiceAppProps { theme: ThemePref; setTheme: (pref: ThemePref) => void; }")
    root = text.split("function ServiceApp", 1)[0]
    for need in ("useState<ThemePref>('dark')", "useShellWindowRoute()", "applyTheme(theme)", "<ThemePrefProvider theme={theme} onThemeChange={setTheme}>",
                 "<ShellWindow route={shellWindow} navigate={navigateShell} />", "<ServiceApp theme={theme} setTheme={setTheme} />"):
        if norm_ws(need) not in norm_ws(root):
            problems.append(f"App.tsx 根组件里缺：{need}")
    for api_name in ("getMetaNow", "getStatus", "useHashRoute"):
        if re.search(rf"\b{api_name}\b", strip_ts_comments(root.split("\nexport default function App", 1)[-1])):
            problems.append(f"App.tsx 根组件（App）里不该出现 {api_name}（根组件不调 api.ts 的任何函数，useHashRoute 留在 ServiceApp）")
    service = text.split("function ServiceApp", 1)[-1]
    for need in ("useHashRoute()", "getMetaNow()", "getStatus()"):
        if need not in service:
            problems.append(f"ServiceApp 里应保留 {need}")
    if "useState<ThemePref>" in service:
        problems.append("主题状态应移到根组件，ServiceApp 里不再 useState<ThemePref>")
    # 新增的行（基线里没有的非空行）数量，以及不踩扫描
    baseline_multiset = set(BASELINE_APP_KEEP)
    added = [ln for ln in lines if ln.strip() and ln not in baseline_multiset]
    if len(added) > APP_MAX_NEW_LINES:
        problems.append(f"App.tsx 新增（基线里没有）的非空行有 {len(added)} 行，合同 §2.3 约增 25 行（上限 {APP_MAX_NEW_LINES}）")
    for ln in added:
        for bad in SHOWCASE_TEXTS + ("data-theme", 'role="status"', "role='status'"):
            if bad in ln:
                problems.append(f"App.tsx 新增行里不能写 {bad}：{ln.strip()[:80]}")
        if HEX_RE.search(ln) or COLOR_FUNC_RE.search(ln):
            problems.append(f"App.tsx 新增行里不能写十六进制颜色或颜色函数：{ln.strip()[:80]}")
    return problems


# ---------------------------------------------------------------------------
# 图标：路径等于画布对应行
# ---------------------------------------------------------------------------

class _PathParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.svgs = []
        self.cur = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "svg":
            self.cur = []
            self.svgs.append(self.cur)
        elif self.cur is not None and tag == "path":
            self.cur.append(a.get("d"))

    def handle_endtag(self, tag):
        if tag == "svg":
            self.cur = None


def canvas_paths(path, lineno):
    """画布某一行里每个 svg 的 path d 列表。"""
    line = _read(path).split("\n")[lineno - 1]
    parser = _PathParser()
    parser.feed(line)
    return parser.svgs


def canvas_icon_paths():
    arrow = [s for s in canvas_paths(FIRST_RUN_CANVAS, 358) if s][-1]  # 进入 + 箭头
    file_text = canvas_paths(SETTINGS_CANVAS, 427)[-1]
    external = canvas_paths(SETTINGS_CANVAS, 428)[-1]
    return {"ArrowRightIcon": arrow, "FileTextIcon": file_text, "ExternalLinkIcon": external}


def icon_block(text, name):
    m = re.search(rf"export\s+(?:const|function)\s+{name}\b", text)
    if not m:
        return None
    nxt = re.search(r"\nexport\s+(?:const|function|type|interface)\b", text[m.end():])
    return text[m.start(): m.end() + (nxt.start() if nxt else len(text))]


def icon_problems(icons_text, wants):
    problems = []
    for name, want in wants.items():
        block = icon_block(icons_text, name)
        if block is None:
            problems.append(f"icons.tsx 没有 export {name}")
            continue
        ds = re.findall(r"<path\b[^>]*?\bd=\"([^\"]*)\"", block)
        if ds != want:
            problems.append(f"{name} 的 path d 应依次为 {want}，实际 {ds}")
    for needle in ("tt-i", "currentColor", "aria-hidden"):
        if needle not in icons_text:
            problems.append(f"icons.tsx 的包装应照 icons/index.tsx 写 {needle}")
    return problems


# ---------------------------------------------------------------------------
# TS 小解析：接口成员、补丁键
# ---------------------------------------------------------------------------

def brace_block(text, start_pattern):
    """从 start_pattern 之后的第一个 ``{`` 起取配对的花括号内部；找不到返回 None。"""
    m = re.search(start_pattern, text)
    if not m:
        return None
    i = text.find("{", m.end())
    if i < 0:
        return None
    depth, j = 0, i
    while j < len(text):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j]
        j += 1
    return None


def top_level_members(inner):
    """类型体里第一层的成员名（按换行与分号切，括号里的不算）。"""
    names, buf, depth = [], [], 0
    for ch in inner + "\n":
        if ch in "({[<":
            depth += 1
        elif ch in ")}]>":
            depth = max(0, depth - 1)
        if ch in "\n;" and depth == 0:
            stmt = "".join(buf).strip()
            buf = []
            m = re.match(r"(?:readonly\s+)?(\w+)\s*[?(:<]", stmt)
            if m:
                names.append(m.group(1))
            continue
        buf.append(ch)
    return names


def interface_problems(text):
    problems = []
    code = strip_ts_comments(text)
    inner = brace_block(code, r"(?:interface\s+ThemisShell\b|type\s+ThemisShell\s*=)")
    if inner is None:
        return ["themisShell.ts 里没有 ThemisShell 接口"]
    members = top_level_members(inner)
    if sorted(members) != sorted(INTERFACE_MEMBERS):
        problems.append(f"ThemisShell 应恰有这十个成员 {sorted(INTERFACE_MEMBERS)}（9 个方法加 on，8.9 :1122；没有切换窗口的函数，Q2-A），实际 {sorted(members)}")
    patch = None
    for m in re.finditer(r"(?:interface|type)\s+(\w*Patch\w*)", code):
        patch = brace_block(code[m.start():], r"^[^{]*") or patch
    if patch is None:
        sig = re.search(r"saveSettings\s*\(([^)]*)\)", code)
        patch = sig.group(1) if sig else None
    if patch is None:
        problems.append("找不到 saveSettings 的补丁类型（*Patch*）")
    else:
        keys = set(re.findall(r"\b(\w+)\??\s*:", patch))
        if keys != set(PATCH_KEYS):
            problems.append(f"saveSettings 的补丁只认这六个键 {sorted(PATCH_KEYS)}（不接受任何路径），实际 {sorted(keys)}")
        if any("path" in k.lower() for k in keys):
            problems.append(f"saveSettings 的补丁里不能有路径键：{sorted(keys)}")
    for literal in ("cancelled", "saved", "rejected", "not-git", "no-agent", "python-unusable", "kit-unusable",
                    "idle", "starting", "running", "exited", "service-state", "currentRepoCheck", "currentRepo",
                    "transcriptDirs", "density", "homepage", "lastOpened", "startedAt", "exitCode"):
        if literal not in code:
            problems.append(f"themisShell.ts 里没有 {literal}")
    return problems


# ---------------------------------------------------------------------------
# 静态断言
# ---------------------------------------------------------------------------

def test_d01_files_in_place():
    """D01 / 合同 Scope：src/shellpages/ 的 21 个新文件、src/mock/shellpages-scenarios.ts 与执行端 8 份测试都在位；
    src/pages 顶层仍恰有 9 个 *Page.tsx 且都含 PageFrame；src/mock 仍恰 14 份 JSON。"""
    problems = [f"{r} 不存在" for r in NEW_SOURCE_FILES if not (REPO_ROOT / r).is_file()]
    problems += [f"{TESTS_REL}/{n} 不存在" for n in EXECUTOR_TESTS if not (WEB / "tests" / n).is_file()]
    pages = sorted((SRC / "pages").glob("*Page.tsx"))
    if len(pages) != 9:
        problems.append(f"{SRC_REL}/pages/ 顶层应恰有 9 个 *Page.tsx，实际 {len(pages)}")
    for path in pages:
        if "PageFrame" not in _read(path):
            problems.append(f"{rel(path)}：每页都用 PageFrame")
    jsons = sorted((SRC / "mock").glob("*.json"))
    if len(jsons) != 14:
        problems.append(f"{SRC_REL}/mock/ 应恰有 14 份 JSON（夹具只能写成 .ts），实际 {len(jsons)}")
    fail_if(problems, "合同要的文件")


def test_d01_themis_shell_interface():
    """D01：themisShell.ts 只有类型；ThemisShell 恰有 getState、pickRepo、pickPython、pickKit、pickTranscriptDir、saveSettings、
    startService、restartService、openExternal 与 on 十个成员（8.9 :1122），没有切换窗口的函数；saveSettings 的补丁只有 theme、density、
    removeRepo、removeTranscriptDir、resetPython、resetKit 六个键、没有路径键；PickOutcome 三种、problem 四种、服务四种状态都写出；
    本片不写 window.themisShell 的全局声明。"""
    text = _read(need_file(f"{SP_REL}/themisShell.ts"))
    problems = interface_problems(text)
    code = strip_ts_comments(text)
    if re.search(r"^\s*export\s+(?:const|function|class)\b", code, re.M):
        problems.append("themisShell.ts 只有类型，不导出值")
    fail_if(problems, "themisShell.ts")


def test_d01_scenarios_fixture_is_ts_and_marked():
    """D01：夹具写成 .ts、文件头标明「示意」、路径里的反斜杠已转义（或用正斜杠）；src/mock 仍没有新的 .json。"""
    path = need_file(SCENARIOS_REL)
    text = _read(path)
    problems = []
    if "示意" not in "\n".join(text.split("\n")[:15]):
        problems.append("shellpages-scenarios.ts 的文件头（前 15 行）要标明「示意」")
    if re.search(r"[A-Za-z]:\\(?!\\)", text):
        problems.append("夹具里的 Windows 路径不要写成单个反斜杠（TS 字符串里要转义，或写正斜杠）")
    for name in SCENARIOS:
        if not re.search(rf"""['"`]{re.escape(name)}['"`]""", text):
            problems.append(f"夹具里没有场景名 {name}")
    fail_if(problems, "src/mock/shellpages-scenarios.ts")


def test_transitional_d01_scenario_fixture_values():
    """接真实外壳那一片（桩与夹具换成真实外壳的取值）推翻。

    D01 / 合同“桩与夹具”：夹具取值——仓库 demo-repo 与 docs-site、两条路径、上次打开时间、Python 3.13.1 与 3.12.4、kit 2.12.0、
    app.version 0.0.0、项目主页地址、被拒的 Python 路径、pid 18244、1500ms、SHELL_STARTED_AT（取自 src/mock/shell.ts）。"""
    text = _read(need_file(SCENARIOS_REL))
    stub = _read(need_file(f"{SP_REL}/shellStub.ts"))
    both = text + "\n" + stub
    problems = []
    for lit in ("demo-repo", "docs-site", "C:/Projects/demo-repo", "C:/Projects/docs-site", "2026-10-18", "2026-10-15",
                "C:/Python313/python.exe", "3.13.1", "3.12.4", "2.12.0", "0.0.0", "https://github.com/mrQzs/ThemisTally",
                "C:/Python39/python.exe"):
        if lit not in text:
            problems.append(f"shellpages-scenarios.ts 里没有「{lit}」")
    if "1500" not in stub and "1500" not in text:
        problems.append("桩里没有 1500（starting 之后 1500ms 发 running 或 exited）")
    if "18244" not in both and "SHELL_PID" not in both:
        problems.append("桩或夹具里没有 pid 18244（或取自 src/mock/shell.ts 的 SHELL_PID）")
    if "SHELL_STARTED_AT" not in both and "2026-10-18 09:41:07" not in both:
        problems.append("running 的 startedAt 应取 src/mock/shell.ts 的 SHELL_STARTED_AT")
    fail_if(problems, "桩夹具的取值")


def test_d03_shell_window_route_exports():
    """D03：shellWindowRoute.ts 导出 parseShellWindow（纯函数）；ShellWindow.tsx 导出 ShellWindow 与 useShellWindowRoute（App.tsx 从这里导入）；
    根上钩子监听 hashchange，navigateShell 同一次调用里先改状态再写 location.hash，写地址不放进 setState 的更新函数（K21）。"""
    route = _read(need_file(f"{SP_REL}/shellWindowRoute.ts"))
    window = _read(need_file(f"{SP_REL}/ShellWindow.tsx"))
    fail_if(route_source_problems(route, window), "外壳窗口的地址钩子")


def route_source_problems(route_text, window_text):
    route = strip_ts_comments(route_text)
    window = strip_ts_comments(window_text)
    problems = []
    if not re.search(r"export\s+(?:function|const)\s+parseShellWindow\b", route):
        problems.append("shellWindowRoute.ts 没有导出 parseShellWindow")
    if not re.search(r"export\s+(?:default\s+)?(?:function|const)\s+ShellWindow\b|export\s*\{[^}]*\bShellWindow\b", window):
        problems.append("ShellWindow.tsx 没有导出 ShellWindow")
    both = route + "\n" + window
    if not re.search(r"export\s+(?:function|const)\s+useShellWindowRoute\b|export\s*\{[^}]*\buseShellWindowRoute\b", both) or \
            not re.search(r"export\s*\{[^}]*\buseShellWindowRoute\b|export\s+(?:function|const)\s+useShellWindowRoute\b", window):
        problems.append("ShellWindow.tsx 要导出 useShellWindowRoute（直接定义或从 shellWindowRoute 再导出）")
    hook = route if "useShellWindowRoute" in route and "hashchange" in route else both
    if "hashchange" not in hook:
        problems.append("useShellWindowRoute 要监听 hashchange（手改地址、后退、前进）")
    if "navigateShell" not in hook:
        problems.append("useShellWindowRoute 要返回 navigateShell")
    m = re.search(r"(?:const\s+navigateShell\s*=|function\s+navigateShell\b)", hook)
    if m:
        body = hook[m.start(): m.start() + 900]
        updater = re.search(r"set\w+\(\s*\(?\s*\w*\s*\)?\s*=>[^;]*location\.hash\s*=", body, re.S)
        if updater:
            problems.append("navigateShell 不能把写 location.hash 放进 setState 的更新函数里（K21：同一次调用里先改状态、再写地址）")
        if not re.search(r"location\.hash\s*=", body):
            problems.append("navigateShell 的函数体里要直接写 location.hash")
    return problems


def test_d06_exit_codes_shared_by_first_run_and_service_status():
    """D06：退出码说明映射写在 exitCodes.ts（1「这个仓库已经在另一个窗口里打开了。」、2「应用文件不完整，请重新安装。」、
    其他「本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。」）；ServiceStatusView 与首启（FirstRunView 或 firstRunModel）都从它取，
    视图里不另写这几句。"""
    codes = _read(need_file(f"{SP_REL}/exitCodes.ts"))
    problems = []
    sentences = ("这个仓库已经在另一个窗口里打开了。", "应用文件不完整，请重新安装。",
                 "本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。")
    for s in sentences:
        if s not in codes:
            problems.append(f"exitCodes.ts 里没有「{s}」")
    status = need_file(f"{SP_REL}/ServiceStatusView.tsx")
    first = [sp("FirstRunView.tsx"), sp("firstRunModel.ts")]
    need_file(f"{SP_REL}/FirstRunView.tsx")
    need_file(f"{SP_REL}/firstRunModel.ts")
    if not any(resolve_import(status, s) == sp("exitCodes.ts").resolve() for s in imports_of(status)):
        problems.append("ServiceStatusView.tsx 没有从 ./exitCodes 导入")
    if not any(resolve_import(p, s) == sp("exitCodes.ts").resolve() for p in first for s in imports_of(p)):
        problems.append("首次启动（FirstRunView.tsx 或 firstRunModel.ts）没有从 ./exitCodes 导入（第 4 步与服务状态页共用）")
    for path in [status] + first:
        text = _read(path)
        for s in sentences[1:2] + sentences[2:]:
            if s in text:
                problems.append(f"{path.name} 里另写了退出码说明「{s}」，应只放在 exitCodes.ts")
    fail_if(problems, "退出码说明的共用")


def test_d07_settings_page_and_view_source():
    """D07：SettingsPage 用 PageFrame（title「设置」、description「设置保存在桌面应用自己的用户数据目录里，不写进仓库的配置」），
    load 是 useCallback 包的 getState 加一层 .then（依赖只有 shell，不加 await），command 写 themisShell.getState，不传 isEmpty，
    不 import api.ts，渲染 SettingsView；SettingsView 根元素 data-page=settings，不渲染 h1、不写 data-page-state，
    五个 section 带 data-settings-group（repos、runtime、usage、appearance、about）与 h2。"""
    page_text = _read(need_file(f"{SRC_REL}/pages/SettingsPage.tsx"))
    view_text = _read(need_file(f"{SP_REL}/SettingsView.tsx"))
    fail_if(settings_source_problems(page_text, view_text), "设置页源码")


def settings_source_problems(page_text, view_text):
    page = strip_ts_comments(page_text)
    view = strip_ts_comments(view_text)
    problems = []
    if "<PageFrame" not in page or not any(s.endswith("shell/PageFrame") for s in import_specs(page)):
        problems.append("SettingsPage.tsx 要用 PageFrame（从 ../shell/PageFrame 导入）")
    if "title=\"设置\"" not in page and "title={'设置'}" not in page:
        problems.append("SettingsPage 的 title 要是「设置」")
    if "设置保存在桌面应用自己的用户数据目录里，不写进仓库的配置" not in page:
        problems.append("SettingsPage 的 description 不对")
    if not re.search(r"useCallback\s*\(", page):
        problems.append("load 要用 useCallback（稳定引用）")
    if not re.search(r"\[\s*shell\s*\]", page):
        problems.append("useCallback 的依赖只有 shell")
    if "themisShell.getState" not in page:
        problems.append("信封的 command 要写 themisShell.getState")
    if re.search(r"\bawait\b|\basync\b", page):
        problems.append("SettingsPage 的 load 只有 getState 加一层 .then，不加 await（G6 的 mountApp 只排空 12 个微任务）")
    if re.search(r"\bisEmpty\b", page):
        problems.append("SettingsPage 不传 isEmpty")
    if re.search(r"\bgetMeta\b", page):
        problems.append("SettingsPage 不再用 getMeta")
    if "<SettingsView" not in page:
        problems.append("SettingsPage 要渲染 SettingsView")
    if "data-page=\"settings\"" not in view and "data-page='settings'" not in view:
        problems.append("SettingsView 的根元素要带 data-page=settings")
    if re.search(r"<h1\b", view):
        problems.append("SettingsView 不渲染 h1（h1 由 PageFrame 出）")
    if "data-page-state" in view:
        problems.append("SettingsView 不写 data-page-state（页面里恰有一个，在 PageFrame 根上）")
    for group in ("repos", "runtime", "usage", "appearance", "about"):
        if group not in view:
            problems.append(f"SettingsView 里没有 data-settings-group={group}")
    if "data-settings-group" not in view or "data-repo-id" not in view:
        problems.append("SettingsView 要写 data-settings-group 与 data-repo-id（K18）")
    if not re.search(r"<h2\b", view):
        problems.append("SettingsView 的五个 section 各带 h2（运行时探针逐个核对）")
    return problems


def test_d09_licenses_and_external_link_source():
    """D09：licenses.ts 写 Lucide 1.59.0 ISC、Sarasa Gothic 0.36.0 SIL OFL 1.1 与随包路径（licenses/lucide-1.59.0-LICENSE.txt、licenses/OFL.txt），
    只写项目名与许可、不写字体文件名；ExternalLinkDialog 的标题、说明与按钮文字、只有 http(s) 才显示 [项目主页]。"""
    lic = _read(need_file(f"{SP_REL}/licenses.ts"))
    ext = _read(need_file(f"{SP_REL}/ExternalLinkDialog.tsx"))
    problems = []
    for lit in ("Lucide", "1.59.0", "ISC", "MIT", "licenses/lucide-1.59.0-LICENSE.txt", "Sarasa Gothic", "0.36.0", "SIL OFL 1.1", "licenses/OFL.txt"):
        if lit not in lic:
            problems.append(f"licenses.ts 里没有「{lit}」")
    for word in FONT_WORDS:
        if word in lic:
            problems.append(f"licenses.ts 不写字体文件名或字体声明：{word}")
    for lit in ("在系统浏览器中打开？", "只允许 http 与 https；由外壳交给系统浏览器打开。", "取消", "打开"):
        if lit not in ext:
            problems.append(f"ExternalLinkDialog.tsx 里没有「{lit}」")
    if "开源许可清单" not in _read(need_file(f"{SP_REL}/LicensesDialog.tsx")) + _read(sp("SettingsView.tsx")):
        problems.append("LicensesDialog 或 SettingsView 里没有「开源许可清单」")
    fail_if(problems, "许可清单与外部链接")


def test_d10_static_isolation():
    """D10 静态：src/shellpages/** 与 SettingsPage.tsx 的导入里没有 api 模块（含 import type）；没有 window.themisHost、window.open、
    localStorage、sessionStorage；整个 src 下它们（与 App.tsx 根组件）都不碰浏览器网络接口名（整词，注释与字符串也算）。"""
    need_new_sources()
    files = [REPO_ROOT / r for r in NEW_SOURCE_FILES if r.endswith((".ts", ".tsx")) and "/shellpages/" in r]
    files.append(SRC / "pages" / "SettingsPage.tsx")
    problems = api_import_problems(files) + forbidden_api_problems(files + [SRC / "App.tsx"])
    problems += word_problems(files + [SRC / "App.tsx", REPO_ROOT / SCENARIOS_REL], NET_WORDS, whole=True)
    fail_if(problems, "隔离的静态部分")


def test_d11_source_rules():
    """D11：公共约定的源码守卫（夹具字符串、注释也算）——整词 fetch/XMLHttpRequest/EventSource/WebSocket；子串 dangerouslySetInnerHTML 等 9 个；
    不渲染 role=status、不调 matchMedia/scrollIntoView/ResizeObserver/IntersectionObserver；不写 data-theme；W4 的坑（十六进制、颜色函数名、
    拼接 --tt-）；字体扩展名与 @font-face、FontFace、sarasa-mono-sc-；不写 ServerIcon、localStorage、sessionStorage、window.open、window.confirm；
    不写内联 style。"""
    need_new_sources()
    files = new_ts_files()
    css_files = [REPO_ROOT / r for r in NEW_CSS]
    problems = word_problems(files, NET_WORDS, whole=True) + word_problems(files, FORBIDDEN_WORDS)
    for path in files:
        problems += role_and_interface_problems(rel(path), _read(path))
        if "data-theme" in _read(path):
            problems.append(f"{rel(path)}：新代码不写 data-theme（只有 theme.ts 的 applyTheme 写）")
    problems += word_problems(files + css_files, FONT_WORDS)
    problems += w4_pitfall_problems(files + css_files)
    problems += forbidden_api_problems(files)
    problems += inline_style_problems(new_tsx_view_files())
    fail_if(problems, "源码守卫")


def test_d11_file_names_and_page_inventory():
    """D11：src/shellpages 里不用 *Page.tsx、*Showcase.tsx、DiffView*、LogFollow*（G6 数 src/pages 顶层的 *Page.tsx；陈列页按 *Showcase.tsx 收集）；
    SettingsView 写在一个文件里，不额外拆分；陈列页没有因本片多出 *Showcase.tsx。"""
    folder = SRC / "shellpages"
    assert folder.is_dir(), f"{SP_REL} 不存在（基线上还没有实现）"
    problems = []
    for path in folder.iterdir():
        if re.search(r"Page\.tsx$|Showcase\.tsx$|^DiffView|^LogFollow", path.name):
            problems.append(f"{path.name}：shellpages 里不用这类文件名")
        if re.match(r"SettingsView.+\.tsx?$", path.name):
            problems.append(f"{path.name}：SettingsView 写在一个文件里，不额外拆分")
    shows = sorted(p.name for p in (SRC / "showcase").glob("*Showcase.tsx"))
    if any("shell" in n.lower() and "pages" in n.lower() for n in shows):
        problems.append(f"陈列页多出了本片的演示：{shows}")
    fail_if(problems, "文件名与页面清单")


def test_d11_new_icons_match_canvas():
    """D11：icons.tsx 的 ArrowRightIcon（首启画布 :358）、FileTextIcon（设置画布 :427）、ExternalLinkIcon（设置画布 :428）的 path d 逐个等于画布对应行
    （从画布解析，不写死）；包装照 icons/index.tsx（tt-i、currentColor、aria-hidden）。"""
    text = _read(need_file(f"{SP_REL}/icons.tsx"))
    wants = canvas_icon_paths()
    assert all(wants.values()), f"画布上没解析出图标：{wants}"
    fail_if(icon_problems(text, wants), "src/shellpages/icons.tsx")


CSS_DIMS = {
    "shell-window.css": [
        ("根 .tt-app 高 100vh（外壳窗口占满窗口）", ("height", "min-height"), "100vh"),
        ("根纵向 flex", ("flex-direction",), "column"),
        ("根 overflow hidden", ("overflow",), "hidden"),
        ("标题栏高 40（5.2 :350）", ("height", "min-height"), "40px"),
        ("标题栏右内边距 140（5.2 :352）", ("padding*",), "140px"),
        ("标题栏 --tt-titlebar 底", ("background", "background-color"), "var(--tt-titlebar)"),
        ("标题栏下边框 --tt-border", ("border-bottom", "border-block-end", "border"), "var(--tt-border)"),
        ("标题栏左内边距 --tt-space-3", ("padding*",), "var(--tt-space-3)"),
        ("产品名 --tt-title-sm", ("font",), "var(--tt-title-sm)"),
        ("主区 overflow-y auto", ("overflow-y", "overflow"), "auto"),
        ("主区上下内边距 --tt-space-8（首启画布 :294）", ("padding*",), "var(--tt-space-8)"),
        ("主区左右内边距 --tt-space-4（首启画布 :294）", ("padding*",), "var(--tt-space-4)"),
        ("卡片 margin auto（安全居中）", ("margin*",), "auto"),
    ],
    "first-run.css": [
        ("卡片宽 560（首启画布 :295）", ("width", "max-width", "flex-basis"), "560px"),
        ("编号圆 22（:306）", ("width", "height"), "22px"),
        ("步名宽 72（:307）", ("width", "flex-basis", "min-width"), "72px"),
        ("状态图标 18", ("width", "height"), "18px"),
        ("错误框左缩进 34（:314）", ("padding*", "margin*"), "34px"),
        ("标识 56×64 的宽", ("width",), "56px"),
        ("标识 56×64 的高", ("height",), "64px"),
        ("通过图标 --tt-tone-success-fg", ("color", "fill", "stroke"), "var(--tt-tone-success-fg)"),
        ("未通过图标 --tt-danger-text", ("color", "fill", "stroke"), "var(--tt-danger-text)"),
        ("转圈图标 --tt-tone-info-fg", ("color", "fill", "stroke"), "var(--tt-tone-info-fg)"),
        ("等待图标 --tt-text-disabled", ("color", "fill", "stroke"), "var(--tt-text-disabled)"),
    ],
    "service-status.css": [
        ("卡片宽 440（断线画布 :363）", ("width", "max-width", "flex-basis"), "440px"),
        ("图标 --tt-danger-text", ("color", "fill", "stroke"), "var(--tt-danger-text)"),
    ],
    "settings.css": [
        ("标签列宽 120", ("width", "flex-basis", "min-width", "grid-template-columns"), "120px"),
        ("表头高 32（handoff :142）", ("height", "min-height"), "32px"),
        ("行高 40（handoff :142）", ("height", "min-height"), "40px"),
        ("表最小宽 640（设置画布 :336）", ("min-width", "width"), "640px"),
        ("外层横向滚动", ("overflow-x", "overflow"), "auto"),
        ("内容最大宽 920", ("max-width", "width"), "920px"),
        ("关于的标识 42×48 的宽", ("width",), "42px"),
        ("关于的标识 42×48 的高", ("height",), "48px"),
    ],
}


def css_dim_problems(css_by_name):
    problems = []
    for name, specs in CSS_DIMS.items():
        css = css_by_name.get(name)
        if css is None:
            problems.append(f"{name} 不存在")
            continue
        for desc, props, token in specs:
            if not css_has(css, props, token):
                problems.append(f"{name}：{desc}——没有一条规则的 {'/'.join(props)} 含 {token}")
    # 填色类的规则在本片 css 再写一遍（只用令牌，不依赖 TitleBar.css 是否已加载）
    joined = "\n".join(css_by_name.values())
    if not css_has(joined, ("fill",), "var(--tt-logo-mark)", r"tt-logo__mark"):
        problems.append("本片 css 里要有 .tt-logo__mark { fill: var(--tt-logo-mark) }（Logo 的填色类，规则在 TitleBar.css :16，本片再写一遍）")
    if not css_has(joined, ("fill",), "var(--tt-logo-tally)", r"tt-logo__tally"):
        problems.append("本片 css 里要有 .tt-logo__tally { fill: var(--tt-logo-tally) }")
    return problems


def shell_css_by_name():
    return {Path(r).name: _read(REPO_ROOT / r) for r in NEW_CSS if (REPO_ROOT / r).is_file()}


def test_d12_css_px_notes_tokens_and_key_values():
    """D12：每份新 css 里除 0 与 1px 外的 px 字面量，同一行有出处注释；层级、圆角、阴影、字体只用令牌；用到的 --tt- 名都在 tokens.css 里；
    不在 css 里声明 --tt- 自定义属性；不写 [data-theme] 选择器；合同 §3 写到的关键尺寸与令牌（卡片宽 560 与 440、编号圆 22、步名宽 72、状态图标 18、
    错误框左缩进 34、标题栏高 40 与右内边距 140、设置标签列宽 120、表头 32、行高 40、表最小宽 640、内容最大宽 920、标识 56×64 与 42×48）
    每个都在对应 css 里出现。"""
    need_new_sources()
    problems = []
    by_name = shell_css_by_name()
    for rel_css in NEW_CSS:
        raw = _read(REPO_ROOT / rel_css)
        label = Path(rel_css).name
        problems += px_literal_problems(label, raw)
        problems += token_only_problems(label, raw)
        problems += css_token_problems(label, raw)
    problems += css_dim_problems(by_name)
    fail_if(problems, "新 css 的出处、令牌与关键尺寸")


def test_d12_wiring_imports_reach_from_app_and_settings_page():
    """D12 / K20（接线，静态部分）：每份新 css 都被一个能从 App.tsx 或 pages/SettingsPage.tsx 经 import 走到的 ts、tsx import；
    ShellWindow.tsx 引入 shell-window.css，FirstRunView、ServiceStatusView、SettingsView 各引入自己的 css；App.tsx 引入 ShellWindow 与
    ThemePrefProvider 并渲染它们；SettingsPage 渲染 SettingsView；SettingsView 用 themePref；ShellWindow 渲染两个视图。"""
    need_new_sources()
    fail_if(wiring_problems(), "接线")


def test_transitional_d13_app_tsx_only_section_2_3_change():
    """再改 App.tsx 的后续片（T013 起接真实外壳或加新页面）推翻。

    D13 / Q1-A：App.tsx 只有合同 §2.3 的改动——基线里要原样保留的 72 行都在且顺序不变，:72 的 TitleBar 一行一字不改，
    两行新导入，根组件 App 不调 api.ts、主题状态与 applyTheme 移到根上，原函数体改名 ServiceApp 且从参数拿 theme 与 setTheme，
    新增行不超过上限、不踩陈列页原文与 data-theme。"""
    need_new_sources()
    fail_if(app_tsx_problems(_read(need_file(f"{SRC_REL}/App.tsx"))), "App.tsx")


def executor_test_problems():
    problems = []
    for name in EXECUTOR_TESTS:
        path = WEB / "tests" / name
        if not path.is_file():
            problems.append(f"{name} 不存在")
            continue
        text = _read(path)
        if not re.search(r"^\s*(?:it|test)\(|^\s*(?:it|test)\.each", text, re.M):
            problems.append(f"{name} 里没有用例")
        if re.search(r"\b(?:it|test|describe)\.(?:skip|only|todo)\b|\bxit\(|\bxdescribe\(|\bxtest\(", text):
            problems.append(f"{name} 里写了 skip、only 或 todo（G2 :1493–1502）")
    return problems


def test_d13_executor_tests_in_place_without_skip_only_todo():
    """D13：执行端的 8 份 tests/shellpages-*（stub、route、first-run、service-status、settings、app、isolation、static）都在位、有用例，
    不用 skip、only、todo。"""
    fail_if(executor_test_problems(), "执行端测试")


# ---------------------------------------------------------------------------
# 探针（Vitest + jsdom）：每份若干顶层 describe，describe 名以 D 编号开头；Python 用例按名字分组核对
# ---------------------------------------------------------------------------

PRELUDE = r"""
import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

// 排空 jsdom 里待决的导航与 hashchange（它们在宏任务里触发），使用例之间不互相泄漏；只为清场，不是断言手段
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
  try {
    const sc: any = await import('../src/shellpages/shellContext');
    sc.resetShellStubs();
  } catch (e) {
    // 基线或候选没有这个模块时，用例本身已经失败
  }
  vi.useRealTimers();
  window.location.hash = '';
  document.documentElement.removeAttribute('data-theme');
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
function allBtns(root: ParentNode = document): HTMLButtonElement[] {
  return Array.from(root.querySelectorAll('button')) as HTMLButtonElement[];
}
function btns(root: ParentNode, text: string): HTMLButtonElement[] {
  return allBtns(root).filter((b) => textOf(b) === text);
}
function btn(root: ParentNode, text: string): HTMLButtonElement {
  const hit = btns(root, text)[0];
  expect(hit, '找不到文字为「' + text + '」的按钮').toBeTruthy();
  return hit;
}
async function clickSettle(el: Element) {
  fireEvent.click(el);
  await settle();
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
// 手改地址（后退、前进、地址栏）：写 location.hash 之后在 act 里手动派发 hashchange（F4：不靠假计时器推进 jsdom 自己排的那次）
function hashTo(hash: string) {
  window.location.hash = hash;
  act(() => {
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  });
}
function queryOf(hash: string): URLSearchParams {
  const i = hash.indexOf('?');
  return new URLSearchParams(i < 0 ? '' : hash.slice(i + 1));
}
function pathOf(hash: string): string {
  const i = hash.indexOf('?');
  return i < 0 ? hash : hash.slice(0, i);
}
// 经 useThemisShell 取到「该场景缓存的桩实例」（同一场景同一实例）；hash 里必须带 shell=，不猜 windowDefault 的含义
async function grabShell(hash: string, def: string = 'ready'): Promise<any> {
  window.location.hash = hash;
  const ctx: any = await import('../src/shellpages/shellContext');
  let got: any = null;
  function Grab() {
    got = ctx.useThemisShell(def);
    return null;
  }
  const r = render(<Grab />);
  r.unmount();
  expect(got, 'useThemisShell 应返回桩实例').toBeTruthy();
  return got;
}
const METHODS = ['getState', 'pickRepo', 'pickPython', 'pickKit', 'pickTranscriptDir', 'saveSettings', 'startService', 'restartService', 'openExternal', 'on'];
const SCEN = ['ready', 'checking', 'first-launch', 'not-git', 'no-agent', 'no-python', 'no-kit', 'exit-1', 'exit-2', 'crash', 'custom'];
const SVC = ['idle', 'starting', 'running', 'exited'];
// 对实例的十个方法套 vi.spyOn（照常调用原方法），按实例上的属性替换，视图里 shell.xxx() 的调用都会被记下
function spyAll(shell: any): Record<string, any> {
  const out: Record<string, any> = {};
  for (const m of METHODS) {
    out[m] = vi.spyOn(shell, m);
  }
  return out;
}
// 套 spy 之前先把原方法绑定下来：mockImplementation 里要调原方法时用它，不能在 spy 之后再 bind（会递归）
function origOf(shell: any): Record<string, any> {
  const out: Record<string, any> = {};
  for (const m of METHODS) {
    out[m] = shell[m].bind(shell);
  }
  return out;
}
function totalCalls(spies: Record<string, any>): number {
  return Object.values(spies).reduce((n: number, s: any) => n + s.mock.calls.length, 0);
}
// 服务状态事件的判别字段合同没有定名：在 kind/status/state/phase/type 里找取值是四种状态之一的那个
function svcOf(p: any): any {
  return p && p.service && typeof p.service === 'object' ? p.service : p;
}
function kindOf(p: any): string {
  const s = svcOf(p);
  if (!s || typeof s !== 'object') return '';
  for (const k of ['kind', 'status', 'state', 'phase', 'type']) {
    if (typeof s[k] === 'string' && SVC.includes(s[k])) return s[k];
  }
  return '';
}
function record(shell: any): { events: any[]; off: () => void } {
  const events: any[] = [];
  const off = shell.on('service-state', (e: any) => {
    events.push(e);
  });
  return { events, off };
}
function kinds(events: any[]): string[] {
  return events.map(kindOf);
}
async function outcome(p: Promise<any>): Promise<string> {
  let st = 'pending';
  p.then(
    () => {
      st = 'ok';
    },
    () => {
      st = 'rejected';
    },
  );
  for (let i = 0; i < 12; i += 1) {
    await Promise.resolve();
  }
  return st;
}
async function rejects(p: Promise<any>): Promise<boolean> {
  try {
    await p;
    return false;
  } catch (e) {
    return true;
  }
}
"""

# 桩（D02）：经 useThemisShell 取实例，不依赖 createShellStub 的参数形状
PROBE_STUB = PRELUDE + r"""
import { SHELL_STARTED_AT, SHELL_PID } from '../src/mock/shell';

async function stubOf(name: string): Promise<any> {
  return grabShell('#/first-run?shell=' + name);
}
// 假计时器下渲染再卸载一个空组件之后的计时器数：React 自己若排了计时器也算在里面，桩的计时器按它的增量算
function noopBase(): number {
  const r = render(<div />);
  r.unmount();
  return vi.getTimerCount();
}

describe('D02 桩的方法、深拷贝与创建时不排计时器', () => {
  it('十个成员加 dispose 都是函数', async () => {
    const s = await stubOf('ready');
    for (const m of METHODS.concat(['dispose'])) {
      expect(typeof s[m], m).toBe('function');
    }
  });

  it('同一场景同一实例，换场景换实例，resetShellStubs 之后换新实例', async () => {
    const ctx: any = await import('../src/shellpages/shellContext');
    const a = await stubOf('ready');
    const again = await stubOf('ready');
    expect(again, '同一场景同一实例').toBe(a);
    const other = await stubOf('custom');
    expect(other, '换场景换实例').not.toBe(a);
    ctx.resetShellStubs();
    const fresh = await stubOf('ready');
    expect(fresh, 'reset 之后换新实例').not.toBe(a);
  });

  it('创建与读取不排计时器：11 个场景取桩后、getState 之后计时器数都是 0', async () => {
    vi.useFakeTimers();
    const ctx: any = await import('../src/shellpages/shellContext');
    for (const name of SCEN) {
      ctx.resetShellStubs();
      // 站主指明的 D02 修法：等 hash 就位之后再取基数。jsdom 只会为「值变了」的 hash 排一次 hashchange
      // （SessionHistory 用 setTimeout(fireEvents, 0)，假计时器下一直挂着），所以每个场景先把 hash 设成目标值再取 base；
      // 之后 stubOf 设同一个值，不再加计时器。桩自己的计时器仍按相对基数的增量照常抓。
      window.location.hash = '#/first-run?shell=' + name;
      const base = noopBase();
      const s = await stubOf(name);
      expect(vi.getTimerCount(), name + ' 创建后').toBe(base);
      expect(await outcome(s.getState()), name + ' getState').toBe('ok');
      expect(vi.getTimerCount(), name + ' getState 之后').toBe(base);
    }
  });

  it('各方法返回已兑现或已被拒的 Promise：假计时器下不推进时间，12 个微任务内就有结果', async () => {
    // 站主指明的 D02 修法：在套假计时器之前就设好 hash。jsdom 只会为「值变了」的 hash 排一次 hashchange
    // （SessionHistory 用 setTimeout(fireEvents, 0)），放在假计时器之前它就永远不计入 vi.getTimerCount()；
    // 之后 stubOf 设同一个值，不再排。桩自己的计时器仍按相对基数的增量照常抓。
    window.location.hash = '#/first-run?shell=ready';
    vi.useFakeTimers();
    const base = noopBase();
    const s = await stubOf('ready');
    expect(await outcome(s.getState()), 'getState').toBe('ok');
    for (const m of ['pickRepo', 'pickPython', 'pickKit', 'pickTranscriptDir']) {
      expect(await outcome(s[m]()), m).toBe('ok');
    }
    expect(await outcome(s.saveSettings({ theme: 'dark' })), 'saveSettings').toBe('ok');
    expect(await outcome(s.openExternal('https://example.com/')), 'openExternal').toBe('ok');
    expect(await outcome(s.saveSettings({ pythonPath: 'C:/x' })), '被拒也是已被拒的 Promise').toBe('rejected');
    expect(await outcome(s.openExternal('javascript:alert(1)')), 'openExternal 被拒').toBe('rejected');
    expect(await outcome(s.startService('no-such-repo')), 'startService 被拒').toBe('rejected');
    expect(vi.getTimerCount(), '读取、选择、保存、被拒之后仍没有计时器').toBe(base);
  });

  it('getState 与各返回值深拷贝：改返回值不影响桩里的状态，两次返回不是同一个对象', async () => {
    const s = await stubOf('ready');
    const s1 = await s.getState();
    const snapshot = JSON.parse(JSON.stringify(s1));
    s1.settings.repos[0].name = 'CHANGED';
    s1.settings.repos.pop();
    s1.python.version = '0.0.0-changed';
    const s2 = await s.getState();
    expect(s2).not.toBe(s1);
    expect(s2).toEqual(snapshot);
    const saved = await s.saveSettings({ density: 'compact' });
    saved.settings.repos.length = 0;
    const s3 = await s.getState();
    expect(s3.settings.repos.length, 'saveSettings 的返回值也是拷贝').toBe(snapshot.settings.repos.length);
    expect(s3.settings.density).toBe('compact');
  });
});

describe('D02 桩的 saveSettings 只认约定键', () => {
  it('路径键、取值不对、不存在的 id、移除当前仓库、混入别的键都被拒，状态不变', async () => {
    vi.useFakeTimers();
    const s = await stubOf('ready');
    const s0 = await s.getState();
    const cur = s0.settings.currentRepo;
    const other = s0.settings.repos.find((r: any) => r.id !== cur);
    expect(cur, 'ready 有当前仓库').toBeTruthy();
    expect(other, 'ready 另有一个仓库').toBeTruthy();
    const bad: any[] = [
      { pythonPath: 'C:/x' },
      { kitPath: 'C:/k' },
      { repoPath: 'C:/r' },
      { theme: 'blue' },
      { theme: 1 },
      { density: 'huge' },
      { removeRepo: 'no-such-id' },
      { removeRepo: other.path },
      { removeRepo: cur },
      { removeTranscriptDir: 'no-such-dir' },
      { resetPython: false },
      { resetKit: 'yes' },
      { theme: 'light', pythonPath: 'C:/x' },
    ];
    for (const patch of bad) {
      expect(await rejects(s.saveSettings(patch)), '应被拒：' + JSON.stringify(patch)).toBe(true);
      expect(await s.getState(), '被拒之后状态不变：' + JSON.stringify(patch)).toEqual(s0);
    }
  });

  it('约定键保存成功并返回新状态：theme、density、removeRepo', async () => {
    const s = await stubOf('ready');
    const s0 = await s.getState();
    const r1 = await s.saveSettings({ theme: 'light' });
    expect(r1.settings.theme).toBe('light');
    const r2 = await s.saveSettings({ density: 'compact' });
    expect(r2.settings.density).toBe('compact');
    expect(r2.settings.theme, '别的设置不受影响').toBe('light');
    const other = s0.settings.repos.find((r: any) => r.id !== s0.settings.currentRepo);
    const r3 = await s.saveSettings({ removeRepo: other.id });
    expect(r3.settings.repos.map((r: any) => r.id)).not.toContain(other.id);
    expect(r3.settings.currentRepo).toBe(s0.settings.currentRepo);
    expect(await s.getState(), '返回值等于随后读到的状态').toEqual(r3);
  });

  it('custom 场景：removeTranscriptDir、resetPython、resetKit', async () => {
    const s = await stubOf('custom');
    const s0 = await s.getState();
    expect(s0.python.source).toBe('custom');
    expect(s0.kit.source).toBe('external');
    expect(s0.settings.transcriptDirs.length).toBeGreaterThanOrEqual(1);
    const first = s0.settings.transcriptDirs[0];
    const r1 = await s.saveSettings({ removeTranscriptDir: first.id });
    expect(r1.settings.transcriptDirs.map((d: any) => d.id)).not.toContain(first.id);
    expect(r1.settings.transcriptDirs.length).toBe(s0.settings.transcriptDirs.length - 1);
    const r2 = await s.saveSettings({ resetPython: true });
    expect(r2.python.source).toBe('auto');
    const r3 = await s.saveSettings({ resetKit: true });
    expect(r3.kit.source).toBe('repo');
  });
});

describe('D02 桩的启动、事件与 dispose', () => {
  it('startService 收到不在列表里的 id 被拒（仓库路径也不行）', async () => {
    const s = await stubOf('ready');
    const s0 = await s.getState();
    expect(await rejects(s.startService('no-such-repo'))).toBe(true);
    expect(await rejects(s.startService(s0.settings.repos[0].path))).toBe(true);
  });

  it('startService 在调用里同步发 starting；同一仓库已在启动中时再调什么也不做', async () => {
    // 同 D02 计时器基数：先设好 hash 再套假计时器，把 jsdom 自己排的那一次 hashchange 排除在计时器数之外
    window.location.hash = '#/first-run?shell=ready';
    vi.useFakeTimers();
    const base = noopBase();
    const s = await stubOf('ready');
    const id = (await s.getState()).settings.currentRepo;
    expect(vi.getTimerCount(), '启动之前没有计时器').toBe(base);
    const { events } = record(s);
    const p1 = s.startService(id);
    expect(kinds(events), '调用里同步发 starting').toEqual(['starting']);
    expect(svcOf(events[0]).repo).toBe(id);
    expect(vi.getTimerCount(), '启动之后才排计时器').toBeGreaterThan(base);
    const p2 = s.startService(id);
    await Promise.all([p1, p2]);
    expect(kinds(events), '启动中再调：幂等').toEqual(['starting']);
    vi.advanceTimersByTime(1500);
    expect(kinds(events)).toEqual(['starting', 'running']);
    await s.startService(id);
    vi.advanceTimersByTime(5000);
    expect(kinds(events), '运行中再调：幂等').toEqual(['starting', 'running']);
  });

  it('restartService 同样在调用里同步发 starting，之后按场景发 running', async () => {
    vi.useFakeTimers();
    const s = await stubOf('ready');
    const { events } = record(s);
    const p = s.restartService();
    expect(kinds(events)).toEqual(['starting']);
    await p;
    vi.advanceTimersByTime(1500);
    expect(kinds(events)).toEqual(['starting', 'running']);
  });

  it('取消订阅之后不再收到事件；别的订阅者不受影响', async () => {
    vi.useFakeTimers();
    const s = await stubOf('ready');
    const id = (await s.getState()).settings.currentRepo;
    const a = record(s);
    const b = record(s);
    expect(typeof a.off).toBe('function');
    a.off();
    await s.startService(id);
    vi.advanceTimersByTime(1500);
    expect(a.events, '取消订阅之后').toEqual([]);
    expect(kinds(b.events)).toEqual(['starting', 'running']);
  });

  it('dispose 清掉计时器与监听：之后推进时间也没有事件，计时器数为 0', async () => {
    // 同 D02 计时器基数：先设好 hash 再套假计时器，把 jsdom 自己排的那一次 hashchange 排除在计时器数之外
    window.location.hash = '#/first-run?shell=ready';
    vi.useFakeTimers();
    const base = noopBase();
    const s = await stubOf('ready');
    const id = (await s.getState()).settings.currentRepo;
    const { events } = record(s);
    await s.startService(id);
    expect(vi.getTimerCount()).toBeGreaterThan(base);
    s.dispose();
    expect(vi.getTimerCount(), 'dispose 之后没有挂起计时器').toBe(base);
    vi.advanceTimersByTime(5000);
    expect(kinds(events), 'dispose 之后没有新事件').toEqual(['starting']);
  });
});

describe('D02 桩的 openExternal 只认 http 与 https', () => {
  it('http、https 兑现；别的协议与空串被拒', async () => {
    const s = await stubOf('ready');
    expect(await rejects(s.openExternal('http://example.com/a'))).toBe(false);
    expect(await rejects(s.openExternal('https://example.com/a?b=1#c'))).toBe(false);
    for (const url of ['javascript:alert(1)', 'file:///C:/Windows/win.ini', 'ftp://example.com/', 'mailto:a@example.com',
      'data:text/html,x', 'example.com', '']) {
      expect(await rejects(s.openExternal(url)), '应被拒：' + url).toBe(true);
    }
  });
});

describe('D02 过渡：桩夹具的取值', () => {
  it('ready：两个仓库、当前仓库 ok、Python 3.13.1 自动、kit 2.12.0 仓库里装好的、版本与主页、服务 idle', async () => {
    const s = await stubOf('ready');
    const st = await s.getState();
    expect(st.settings.repos.map((r: any) => r.name)).toEqual(['demo-repo', 'docs-site']);
    const demo = st.settings.repos.find((r: any) => r.name === 'demo-repo');
    const docs = st.settings.repos.find((r: any) => r.name === 'docs-site');
    expect(st.settings.currentRepo).toBe(demo.id);
    expect(demo.path).toBe('C:/Projects/demo-repo');
    expect(docs.path).toBe('C:/Projects/docs-site');
    expect(String(demo.lastOpened)).toMatch(/^2026-10-18T09:41:07/);
    expect(String(docs.lastOpened)).toMatch(/^2026-10-15T16:20:11/);
    expect(st.currentRepoCheck).toBe('ok');
    expect(st.python.status).toBe('ok');
    expect(st.python.source).toBe('auto');
    expect(st.python.path).toBe('C:/Python313/python.exe');
    expect(st.python.version).toBe('3.13.1');
    expect(st.kit.status).toBe('ok');
    expect(st.kit.source).toBe('repo');
    expect(st.kit.version).toBe('2.12.0');
    expect(st.app.version).toBe('0.0.0');
    expect(st.app.homepage).toBe('https://github.com/mrQzs/ThemisTally');
    expect(kindOf(st), 'ready 的服务状态是 idle').toBe('idle');
  });

  it('ready：四个 pick 各给一个 saved；pickRepo 只把仓库加进列表，不切换当前仓库', async () => {
    const s = await stubOf('ready');
    const s0 = await s.getState();
    for (const m of ['pickPython', 'pickKit', 'pickTranscriptDir']) {
      const r = await s[m]();
      expect(r.kind, m).toBe('saved');
      expect(typeof r.path, m + ' 的 path').toBe('string');
      expect(r.state, m + ' 带新状态').toBeTruthy();
    }
    const r = await s.pickRepo();
    expect(r.kind).toBe('saved');
    expect(typeof r.id).toBe('string');
    const st = await s.getState();
    expect(st.settings.repos.map((x: any) => x.id)).toContain(r.id);
    expect(st.settings.currentRepo, '不切换当前仓库').toBe(s0.settings.currentRepo);
  });

  it('first-launch：没有仓库；pickRepo 依次 not-git、no-agent、saved demo-repo，用完后重复最后一个', async () => {
    const s = await stubOf('first-launch');
    const st = await s.getState();
    expect(st.settings.repos).toEqual([]);
    expect(st.settings.currentRepo).toBeNull();
    expect(st.currentRepoCheck).toBeNull();
    const r1 = await s.pickRepo();
    expect([r1.kind, r1.problem]).toEqual(['rejected', 'not-git']);
    expect(typeof r1.path).toBe('string');
    const r2 = await s.pickRepo();
    expect([r2.kind, r2.problem]).toEqual(['rejected', 'no-agent']);
    const r3 = await s.pickRepo();
    expect(r3.kind).toBe('saved');
    expect(r3.path).toBe('C:/Projects/demo-repo');
    const r4 = await s.pickRepo();
    expect(r4.kind, '用完后重复最后一个').toBe('saved');
    expect(r4.path).toBe(r3.path);
    const after = await s.getState();
    expect(after.settings.repos.map((x: any) => x.id)).toContain(r3.id);
    expect(after.settings.currentRepo, '只加进列表，不切换').toBeNull();
  });

  it('no-python：Python missing；pickPython 先 rejected（C:/Python39/python.exe）再 saved 3.13.1', async () => {
    const s = await stubOf('no-python');
    const st = await s.getState();
    expect(st.python.status).toBe('missing');
    const r1 = await s.pickPython();
    expect([r1.kind, r1.problem, r1.path]).toEqual(['rejected', 'python-unusable', 'C:/Python39/python.exe']);
    const r2 = await s.pickPython();
    expect(r2.kind).toBe('saved');
    expect(r2.state.python.version).toBe('3.13.1');
    expect(r2.state.python.status).toBe('ok');
  });

  it('not-git、no-agent、no-kit、custom 的状态', async () => {
    expect((await (await stubOf('not-git')).getState()).currentRepoCheck).toBe('not-git');
    expect((await (await stubOf('no-agent')).getState()).currentRepoCheck).toBe('no-agent');
    expect((await (await stubOf('no-kit')).getState()).kit.status).toBe('missing');
    const c = await (await stubOf('custom')).getState();
    expect([c.python.source, c.python.version, c.kit.source, c.kit.version]).toEqual(['custom', '3.12.4', 'external', '2.12.0']);
    expect(c.settings.transcriptDirs.length).toBe(2);
    expect(c.settings.density).toBe('compact');
  });

  it('start 之后 1499ms 还没有 running、1500ms 发 running（pid 18244，startedAt 取 SHELL_STARTED_AT）', async () => {
    vi.useFakeTimers();
    const s = await stubOf('ready');
    const id = (await s.getState()).settings.currentRepo;
    const { events } = record(s);
    await s.startService(id);
    vi.advanceTimersByTime(1499);
    expect(kinds(events), '1499ms 时').toEqual(['starting']);
    vi.advanceTimersByTime(1);
    expect(kinds(events), '1500ms 时').toEqual(['starting', 'running']);
    const run = svcOf(events[1]);
    expect(run.pid).toBe(18244);
    expect(SHELL_PID).toBe(18244);
    expect(run.startedAt).toBe(SHELL_STARTED_AT);
    expect(run.repo).toBe(id);
  });

  it('checking 停在 starting；exit-1、exit-2 发 exited 1、2；crash 的缺省服务状态 exited 3，start 与 restart 之后 running', async () => {
    vi.useFakeTimers();
    const ctx: any = await import('../src/shellpages/shellContext');
    let s = await stubOf('checking');
    let id = (await s.getState()).settings.currentRepo;
    let rec = record(s);
    await s.startService(id);
    vi.advanceTimersByTime(10000);
    expect(kinds(rec.events)).toEqual(['starting']);
    for (const [name, code] of [['exit-1', 1], ['exit-2', 2]] as Array<[string, number]>) {
      ctx.resetShellStubs();
      s = await stubOf(name);
      id = (await s.getState()).settings.currentRepo;
      rec = record(s);
      await s.restartService();
      vi.advanceTimersByTime(1500);
      expect(kinds(rec.events), name).toEqual(['starting', 'exited']);
      const ex = svcOf(rec.events[1]);
      expect(ex.exitCode, name + ' 的退出码').toBe(code);
      expect(ex.at, name + ' 带时刻').toBeTruthy();
      expect(ex.repo).toBe(id);
    }
    ctx.resetShellStubs();
    s = await stubOf('crash');
    const st = await s.getState();
    expect(kindOf(st), 'crash 的缺省服务状态').toBe('exited');
    expect(svcOf(st).exitCode).toBe(3);
    rec = record(s);
    await s.restartService();
    vi.advanceTimersByTime(1500);
    expect(kinds(rec.events)).toEqual(['starting', 'running']);
  });
});

describe('D01 模块导出的名字', () => {
  it('shellStub、shellContext、shellWindowRoute、ShellWindow、themePref、copy 导出合同写出的名字', async () => {
    const stub: any = await import('../src/shellpages/shellStub');
    expect(typeof stub.createShellStub, 'createShellStub').toBe('function');
    const ctx: any = await import('../src/shellpages/shellContext');
    for (const n of ['ThemisShellProvider', 'useThemisShell', 'resetShellStubs']) {
      expect(typeof ctx[n], n).toBe('function');
    }
    const route: any = await import('../src/shellpages/shellWindowRoute');
    expect(typeof route.parseShellWindow, 'parseShellWindow').toBe('function');
    const win: any = await import('../src/shellpages/ShellWindow');
    expect(typeof win.ShellWindow, 'ShellWindow').toBe('function');
    expect(typeof win.useShellWindowRoute, 'useShellWindowRoute').toBe('function');
    const pref: any = await import('../src/shellpages/themePref');
    expect(typeof pref.ThemePrefProvider, 'ThemePrefProvider').toBe('function');
    expect(typeof pref.useThemePref, 'useThemePref').toBe('function');
    const copy: any = await import('../src/shellpages/copy');
    expect(typeof copy.copyText, 'copyText').toBe('function');
  });
});

describe('D05 copyText 返回 copied、failed、unavailable', () => {
  it('显式传入 clipboard：writeText 成功、抛错、返回被拒的 Promise、没有 writeText', async () => {
    const copy: any = await import('../src/shellpages/copy');
    const calls: string[] = [];
    expect(await copy.copyText('abc', { writeText: async (t: string) => { calls.push(t); } })).toBe('copied');
    expect(calls).toEqual(['abc']);
    expect(await copy.copyText('abc', { writeText: async () => { throw new Error('denied'); } })).toBe('failed');
    expect(await copy.copyText('abc', { writeText: () => Promise.reject(new Error('denied')) })).toBe('failed');
    expect(await copy.copyText('abc', { writeText: () => { throw new Error('sync'); } })).toBe('failed');
    expect(await copy.copyText('abc', {})).toBe('unavailable');
  });

  it('不传 clipboard 时点击当下才读 navigator.clipboard：没有时 unavailable，有时用它', async () => {
    const copy: any = await import('../src/shellpages/copy');
    delete (navigator as any).clipboard;
    expect(await copy.copyText('abc')).toBe('unavailable');
    const calls: string[] = [];
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: async (t: string) => { calls.push(t); } }, configurable: true });
    try {
      expect(await copy.copyText('xyz')).toBe('copied');
      expect(calls).toEqual(['xyz']);
    } finally {
      delete (navigator as any).clipboard;
    }
  });
});
"""

# 进入方式（D03）
PROBE_ROUTE = PRELUDE + r"""
function nav(): HTMLElement | null {
  return document.querySelector('nav[aria-label="主导航"]');
}
function ctrlKey(k: string) {
  return fireEvent.keyDown(window, { key: k, ctrlKey: true });
}
function currentTabs(): string[] {
  return (Array.from(document.querySelectorAll('nav[aria-label="主导航"] a[data-tab]')) as HTMLElement[])
    .filter((a) => a.getAttribute('aria-current') === 'page')
    .map((a) => a.getAttribute('data-tab') as string);
}
function h1s(): string[] {
  return Array.from(document.querySelectorAll('h1')).map((h) => textOf(h));
}
function shellWin(): HTMLElement | null {
  return document.querySelector('[data-shell-window]');
}

describe('D03 服务窗口的路由照旧', () => {
  it('#/settings 仍是 Tab（aria-current=page），h1 是「设置」，设置页根元素 data-page=settings，页面里恰一个 data-page-state', async () => {
    await mountApp('#/settings?shell=ready');
    expect(currentTabs()).toEqual(['settings']);
    expect(h1s()).toEqual(['设置']);
    expect(document.querySelector('[data-page="settings"]')).not.toBeNull();
    expect(document.querySelectorAll('[data-page-state]').length).toBe(1);
    expect(shellWin(), '设置不是外壳窗口').toBeNull();
    expect(document.title).toBe('设置 · Themis Tally');
  });

  it('未知路径与前缀相近的路径仍归总览，不当作外壳窗口', async () => {
    for (const hash of ['#/nope', '#/first-run-x', '#/first-runs', '#/service-status-x', '#/service']) {
      const r = await mountApp(hash);
      expect(h1s(), hash).toEqual(['总览']);
      expect(shellWin(), hash + ' 不是外壳窗口').toBeNull();
      expect(nav(), hash + ' 有主导航').not.toBeNull();
      r.unmount();
    }
  });

  it('Ctrl+, 仍切到设置', async () => {
    await mountApp('#/overview');
    ctrlKey(',');
    expect(h1s()).toEqual(['设置']);
  });
});

describe('D03 过渡：parseShellWindow 与进入地址', () => {
  it('parseShellWindow：第一段是 first-run、service-status 时给出 page 与 query，别的地址给 null', async () => {
    const mod: any = await import('../src/shellpages/shellWindowRoute');
    const f = mod.parseShellWindow;
    expect(typeof f, 'parseShellWindow 要导出为函数').toBe('function');
    const a = f('#/first-run');
    expect(a, '#/first-run').toBeTruthy();
    expect(a.page).toBe('first-run');
    const b = f('#/service-status?mock=data&shell=exit-1');
    expect(b.page).toBe('service-status');
    expect(String(b.query)).toContain('shell=exit-1');
    expect(String(b.query)).toContain('mock=data');
    expect(f('#/first-run/extra').page, '第一段决定，后面的段忽略').toBe('first-run');
    for (const hash of ['', '#', '#/', '#/overview', '#/settings', '#/nope', '#/first-run-x', '#/service-status-x', '#/tasks/first-run']) {
      expect(f(hash), '应为 null：' + JSON.stringify(hash)).toBeNull();
    }
  });

  it('#/first-run 与 #/service-status 整窗渲染：没有主导航、切换仓库钮与 data-tab，恰一个 h1，document.title 正确，Ctrl+1 地址不变', async () => {
    const cases = [
      { hash: '#/first-run', page: 'first-run', h1: '欢迎使用 Themis Tally', title: '首次启动 · Themis Tally' },
      { hash: '#/first-run?mock=data&shell=checking', page: 'first-run', h1: '欢迎使用 Themis Tally', title: '首次启动 · Themis Tally' },
      { hash: '#/first-run/extra?shell=checking', page: 'first-run', h1: '欢迎使用 Themis Tally', title: '首次启动 · Themis Tally' },
      { hash: '#/service-status', page: 'service-status', h1: '本机服务已停止', title: '本机服务已停止 · Themis Tally' },
      { hash: '#/service-status?mock=error&shell=exit-2', page: 'service-status', h1: '本机服务已停止', title: '本机服务已停止 · Themis Tally' },
    ];
    for (const c of cases) {
      vi.useFakeTimers();
      const r = await mountApp(c.hash);
      expect(nav(), c.hash + ' 没有主导航').toBeNull();
      expect(document.querySelector('button[title="切换仓库"]'), c.hash + ' 没有切换仓库钮').toBeNull();
      expect(document.querySelector('[data-tab]'), c.hash + ' 没有 data-tab').toBeNull();
      expect(h1s(), c.hash).toEqual([c.h1]);
      expect(document.title, c.hash).toBe(c.title);
      const win = shellWin();
      expect(win, c.hash + ' 根元素带 data-shell-window').not.toBeNull();
      expect((win as HTMLElement).getAttribute('data-shell-window')).toBe(c.page);
      expect((win as HTMLElement).classList.contains('tt-app'), '根元素是 div.tt-app').toBe(true);
      const before = window.location.hash;
      ctrlKey('1');
      await settle();
      expect(window.location.hash, 'Ctrl+1 不拦截外壳窗口，地址不变').toBe(before);
      expect(shellWin(), 'Ctrl+1 之后仍是外壳窗口').not.toBeNull();
      r.unmount();
      vi.useRealTimers();
    }
  });

  it('缺省场景：#/first-run 为 ready（第 1 步通过），#/service-status 为 crash（退出码 3）；认不出的 shell= 取值回到缺省', async () => {
    vi.useFakeTimers();
    let r = await mountApp('#/first-run');
    let step1 = document.querySelector('[data-step]') as HTMLElement;
    expect(step1.querySelector('[role="img"][aria-label="通过"]'), '缺省 ready').not.toBeNull();
    r.unmount();
    r = await mountApp('#/first-run?shell=nope');
    step1 = document.querySelector('[data-step]') as HTMLElement;
    expect(step1.querySelector('[role="img"][aria-label="通过"]'), '认不出的取值回缺省 ready').not.toBeNull();
    r.unmount();
    r = await mountApp('#/service-status');
    expect(textOf(document.querySelector('[data-exit-code]')), '缺省 crash').toBe('3');
    r.unmount();
    r = await mountApp('#/service-status?shell=nope');
    expect(textOf(document.querySelector('[data-exit-code]')), '认不出的取值回缺省 crash').toBe('3');
  });
});

describe('D03 过渡：两种窗口之间手改地址', () => {
  it('手动派发 HashChangeEvent：服务窗口 → 首启 → 服务窗口 → 服务状态 → 设置；同一地址连派两次页面不重挂', async () => {
    vi.useFakeTimers();
    await mountApp('#/overview?mock=data');
    expect(h1s()).toEqual(['总览']);
    const main = document.querySelector('main');
    hashTo('#/overview?mock=data');
    hashTo('#/overview?mock=data');
    expect(document.querySelector('main'), '同一地址连派两次，服务窗口不重挂').toBe(main);
    expect(h1s()).toEqual(['总览']);

    hashTo('#/first-run?shell=checking');
    await settle();
    expect(shellWin()).not.toBeNull();
    expect(nav(), '服务窗口已卸载').toBeNull();
    const win = shellWin();
    hashTo('#/first-run?shell=checking');
    hashTo('#/first-run?shell=checking');
    expect(shellWin(), '同一地址连派两次，外壳窗口不重挂').toBe(win);

    hashTo('#/overview?mock=data');
    await settle();
    expect(shellWin()).toBeNull();
    expect(nav()).not.toBeNull();
    expect(h1s()).toEqual(['总览']);

    hashTo('#/service-status?shell=exit-1');
    await settle();
    expect(shellWin()?.getAttribute('data-shell-window')).toBe('service-status');
    expect(h1s()).toEqual(['本机服务已停止']);

    hashTo('#/settings?shell=ready');
    await settle();
    expect(shellWin()).toBeNull();
    expect(currentTabs()).toEqual(['settings']);
    expect(h1s()).toEqual(['设置']);
  });
});

describe('D03 过渡：navigateShell 同步改状态与地址并保留查询串', () => {
  it('服务状态页的 [打开设置]：点击返回时地址已是 #/settings、保留 mock、没有 shell 时补上当前场景（crash），设置页已渲染', async () => {
    vi.useFakeTimers();
    await mountApp('#/service-status?mock=data');
    fireEvent.click(btn(document, '打开设置'));
    const hash = window.location.hash;
    expect(pathOf(hash), '点击返回时地址已改').toBe('#/settings');
    const q = queryOf(hash);
    expect(q.get('mock')).toBe('data');
    expect(q.get('shell'), '补上当前场景').toBe('crash');
    expect(shellWin(), '同一次调用里页面已换成服务窗口').toBeNull();
    expect(h1s()).toEqual(['设置']);
    expect(currentTabs()).toEqual(['settings']);
  });

  it('shell= 已有时原样保留（exit-1），两边用同一个桩实例', async () => {
    vi.useFakeTimers();
    const shell = await grabShell('#/service-status?shell=exit-1&mock=data');
    const spy = vi.spyOn(shell, 'getState');
    await mountApp('#/service-status?shell=exit-1&mock=data');
    spy.mockClear();
    fireEvent.click(btn(document, '打开设置'));
    const q = queryOf(window.location.hash);
    expect(q.get('shell')).toBe('exit-1');
    expect(q.get('mock')).toBe('data');
    await settle();
    expect(spy.mock.calls.length, '设置页读的是同一个桩实例').toBeGreaterThanOrEqual(1);
  });

  it('首启的 [进入]：四步全过之后点击，地址立刻是 #/overview，保留 mock、补上 shell=ready，服务窗口已渲染；没过之前点不动', async () => {
    vi.useFakeTimers();
    await mountApp('#/first-run?mock=data');
    const enter = btn(document, '进入');
    expect(enter.disabled, '服务还在启动，进入不可用').toBe(true);
    fireEvent.click(enter);
    expect(pathOf(window.location.hash), '禁用时点不动').toBe('#/first-run');
    advance(1500);
    await settle();
    expect(btn(document, '进入').disabled).toBe(false);
    fireEvent.click(btn(document, '进入'));
    const hash = window.location.hash;
    expect(pathOf(hash)).toBe('#/overview');
    const q = queryOf(hash);
    expect(q.get('mock')).toBe('data');
    expect(q.get('shell')).toBe('ready');
    expect(shellWin(), '同一次调用里页面已换成服务窗口').toBeNull();
    expect(nav()).not.toBeNull();
    expect(h1s()).toEqual(['总览']);
  });
});
"""

# 首次启动（D04、D05）
PROBE_FIRSTRUN = PRELUDE + r"""
const ICONS = ['通过', '未通过', '正在启动', '等待'];

function stepEls(): HTMLElement[] {
  return Array.from(document.querySelectorAll('[data-step]')) as HTMLElement[];
}
function iconOf(step: Element): string {
  const hit = Array.from(step.querySelectorAll('[role="img"]'))
    .map((e) => e.getAttribute('aria-label') || '')
    .find((l) => ICONS.includes(l));
  return hit || '';
}
function icons(): string[] {
  return stepEls().map(iconOf);
}
function alerts(): HTMLElement[] {
  return Array.from(document.querySelectorAll('[role="alert"]')) as HTMLElement[];
}
function stepTexts(): string[] {
  return stepEls().map((s) => textOf(s));
}
function body(): string {
  return textOf(document.body);
}
function statusOf(step: Element): string {
  return step.getAttribute('data-status') || '';
}

async function openFirst(scn: string, extra: string = '', prepare?: (shell: any, spies: Record<string, any>, orig: Record<string, any>) => void) {
  vi.useFakeTimers();
  const hash = '#/first-run?shell=' + scn + extra;
  const shell = await grabShell(hash);
  const state = await shell.getState();
  const orig = origOf(shell);
  const spies = spyAll(shell);
  if (prepare) prepare(shell, spies, orig);
  const r = await mountApp(hash);
  return { shell, spies, state, unmount: r.unmount };
}
function curId(state: any): string {
  return state.settings.currentRepo;
}
function repoPath(state: any, id: string): string {
  return state.settings.repos.find((r: any) => r.id === id).path;
}

describe('D04 过渡：首次启动的四步状态', () => {
  it('ready：四步、先订阅再读状态；三步通过后自动启动恰一次，转圈「正在启动…」，1500ms 后「已启动 · pid 18244」，[进入] 才可用', async () => {
    const { spies, state } = await openFirst('ready');
    expect(stepEls().length, '恰四步（站主 C3：没有第 5 步「工人」）').toBe(4);
    expect(body()).not.toContain('工人');
    expect(icons()).toEqual(['通过', '通过', '通过', '正在启动']);
    const texts = stepTexts();
    expect(texts[0]).toContain('C:/Projects/demo-repo');
    expect(texts[0], '有仓库时操作是 [更换…]').toContain('更换…');
    expect(texts[1]).toContain('3.13.1');
    expect(texts[2]).toContain('2.12.0（仓库里装好的）');
    expect(texts[3]).toContain('正在启动…');
    const live = stepEls()[3].querySelector('[aria-live="polite"]');
    expect(live, '第 4 步的值元素带 aria-live=polite').not.toBeNull();
    expect(document.querySelectorAll('[role="status"]').length, '页面里没有 role=status').toBe(0);
    expect(btn(document, '进入').disabled, '服务还在启动，进入不可用').toBe(true);
    expect(body()).toContain('四步依次检查，全部通过后才能进入');
    expect(spies.startService.mock.calls).toEqual([[curId(state)]]);
    expect(spies.on.mock.calls.length, '订阅 service-state').toBeGreaterThanOrEqual(1);
    expect(spies.on.mock.calls[0][0]).toBe('service-state');
    expect(spies.on.mock.invocationCallOrder[0], '先订阅再调 getState').toBeLessThan(spies.getState.mock.invocationCallOrder[0]);
    advance(1500);
    await settle();
    expect(icons()).toEqual(['通过', '通过', '通过', '通过']);
    expect(stepTexts()[3]).toContain('已启动 · pid 18244');
    expect(btn(document, '进入').disabled, '四步全过，进入可用').toBe(false);
    expect(body()).toContain('四项检查都通过了');
    expect(spies.startService.mock.calls.length, '自动启动恰一次').toBe(1);
  });

  it('data-step 恰四个、data-status：同类状态相同、不同状态不同（取值合同没定，只比较相同与不同）', async () => {
    await openFirst('ready');
    advance(1500);
    await settle();
    const st = stepEls().map(statusOf);
    expect(st.every((v) => v.length > 0), '每步都有 data-status').toBe(true);
    expect(new Set(st).size, '四步都通过：data-status 相同').toBe(1);
  });

  it('checking：服务停在 starting，[进入] 一直不可用', async () => {
    const { spies } = await openFirst('checking');
    advance(10000);
    await settle();
    expect(icons()).toEqual(['通过', '通过', '通过', '正在启动']);
    expect(stepTexts()[3]).toContain('正在启动…');
    expect(btn(document, '进入').disabled).toBe(true);
    expect(spies.startService.mock.calls.length).toBe(1);
  });

  it('first-launch：没有仓库——第 1 步待选择（[选择…]，等待图标），后三步「等待上一步」置灰，不自动启动', async () => {
    const { spies } = await openFirst('first-launch');
    expect(icons()).toEqual(['等待', '等待', '等待', '等待']);
    const texts = stepTexts();
    expect(texts[0]).toContain('还没有选择仓库');
    expect(btns(stepEls()[0], '选择…').length).toBe(1);
    for (const i of [1, 2, 3]) {
      expect(texts[i], '第 ' + (i + 1) + ' 步').toContain('等待上一步');
    }
    const st = stepEls().map(statusOf);
    expect(st[1] === st[2] && st[2] === st[3], '后三步同为等待态').toBe(true);
    expect(spies.startService.mock.calls.length, '没有仓库不自动启动').toBe(0);
    expect(btn(document, '进入').disabled).toBe(true);
    expect(body()).toContain('四步依次检查，全部通过后才能进入');
    expect(alerts().length).toBe(0);
  });

  it('not-git：第 1 步未通过并给出错误框，后面的步骤等待上一步，不自动启动，底栏「处理好上面标出的问题，再接着检查」', async () => {
    const { spies } = await openFirst('not-git');
    const ic = icons();
    expect(ic[0]).toBe('未通过');
    expect(ic[1]).toBe('等待');
    expect(ic[3]).toBe('等待');
    expect(stepTexts()[1]).toContain('等待上一步');
    expect(stepTexts()[3]).toContain('等待上一步');
    expect(btns(stepEls()[0], '更换…').length, '有仓库时操作是 [更换…]').toBe(1);
    expect(spies.startService.mock.calls.length).toBe(0);
    expect(body()).toContain('处理好上面标出的问题，再接着检查');
    expect(document.querySelectorAll('[data-step-error]').length, '错误框恰一个，挂在出错那一步下面').toBe(1);
    const a = alerts();
    expect(a.length).toBe(1);
    expect(stepEls()[0].contains(a[0]) || stepEls()[0].nextElementSibling === a[0] || a[0].previousElementSibling === stepEls()[0] || a[0].closest('[data-step]') === stepEls()[0],
      '错误框挂在第 1 步下面').toBe(true);
    expect(btn(document, '进入').disabled).toBe(true);
  });

  it('no-python：第 2 步未通过，第 4 步等待上一步', async () => {
    const { spies } = await openFirst('no-python');
    const ic = icons();
    expect(ic[0]).toBe('通过');
    expect(ic[1]).toBe('未通过');
    expect(ic[3]).toBe('等待');
    expect(stepTexts()[3]).toContain('等待上一步');
    expect(spies.startService.mock.calls.length).toBe(0);
  });

  it('no-kit：第 1、2 步通过，第 3 步未通过，第 4 步等待上一步', async () => {
    const { spies } = await openFirst('no-kit');
    expect(icons()).toEqual(['通过', '通过', '未通过', '等待']);
    expect(stepTexts()[3]).toContain('等待上一步');
    expect(spies.startService.mock.calls.length).toBe(0);
  });

  it('custom：值写手动指定的版本与外部目录', async () => {
    await openFirst('custom');
    const texts = stepTexts();
    expect(texts[1]).toContain('3.12.4');
    expect(texts[2]).toContain('2.12.0（外部目录）');
  });
});

describe('D05 过渡：首次启动的错误与操作', () => {
  it('not-git：首句、次句与 [重新选择]；点它调 pickRepo()', async () => {
    const { spies } = await openFirst('not-git');
    const a = alerts()[0];
    expect(textOf(a)).toContain('这个文件夹不是 Git 仓库。');
    expect(textOf(a)).toContain('换一个 Git 仓库再试。');
    await clickSettle(btn(a, '重新选择'));
    expect(spies.pickRepo.mock.calls.length).toBe(1);
  });

  it('no-agent：首句、次句、接入命令（<ThemisTally> 原样保留）与 [重新选择]；底栏说明', async () => {
    const { spies, state } = await openFirst('no-agent');
    const a = alerts()[0];
    expect(textOf(a)).toContain('这个仓库还没有接入 Themis Tally。');
    expect(textOf(a)).toContain('在终端里运行下面的命令接入，然后重新选择。');
    const code = a.querySelector('code') as HTMLElement;
    expect(code, '命令放在 CommandLine 的 code 里').not.toBeNull();
    expect(textOf(code)).toBe('python <ThemisTally>/scripts/kit_install.py install ' + repoPath(state, curId(state)));
    expect(body()).toContain('接入后点“重新选择”再检查一次');
    await clickSettle(btn(a, '重新选择'));
    expect(spies.pickRepo.mock.calls.length).toBe(1);
  });

  it('no-python：首句、次句与 [指定 python.exe…]；第一次被拒多一行，第二次保存后第 2 步通过并自动启动', async () => {
    const { spies, state } = await openFirst('no-python');
    const a = alerts()[0];
    expect(textOf(a)).toContain('找不到 Python 3.10 及以上。');
    expect(textOf(a)).toContain('安装后重试，或指定 python.exe。');
    await clickSettle(btn(a, '指定 python.exe…'));
    expect(spies.pickPython.mock.calls.length).toBe(1);
    const r1 = await spies.pickPython.mock.results[0].value;
    expect([r1.kind, r1.problem]).toEqual(['rejected', 'python-unusable']);
    expect(textOf(alerts()[0])).toContain('所选的 python.exe 不能用：' + r1.path + '（要能运行，且是 3.10 及以上）');
    expect(icons()[1], '被拒后第 2 步仍未通过').toBe('未通过');
    await clickSettle(btn(alerts()[0], '指定 python.exe…'));
    expect(spies.pickPython.mock.calls.length).toBe(2);
    const r2 = await spies.pickPython.mock.results[1].value;
    expect(r2.kind).toBe('saved');
    expect(icons()[1], '保存后第 2 步通过').toBe('通过');
    expect(stepTexts()[1]).toContain('3.13.1');
    expect(spies.startService.mock.calls, '前三步通过后自动启动一次').toEqual([[curId(state)]]);
    expect(alerts().length, '错误框已消失').toBe(0);
  });

  it('no-kit：首句、次句与 [指定 kit 目录…]；被拒时多一行（注入一个 rejected 结果）', async () => {
    const { spies } = await openFirst('no-kit', '', (_shell, sp) => {
      sp.pickKit.mockResolvedValueOnce({ kind: 'rejected', problem: 'kit-unusable', path: 'D:/bad-kit' });
    });
    const a = alerts()[0];
    expect(textOf(a)).toContain('找不到 Themis Tally 的 kit。');
    expect(textOf(a)).toContain('在仓库里用 kit_install 装好，或指定 kit 目录。');
    await clickSettle(btn(a, '指定 kit 目录…'));
    expect(spies.pickKit.mock.calls.length).toBe(1);
    expect(textOf(alerts()[0])).toContain('所选目录里的 kit 不能用：D:/bad-kit（要能运行 pi_dispatch.py --version）');
    expect(icons()[2]).toBe('未通过');
  });

  it('first-launch 整条流程：选择… → not-git → no-agent → saved；路径取被拒与保存的那个，保存后三步通过并用保存的 id 启动一次', async () => {
    const { spies } = await openFirst('first-launch');
    await clickSettle(btn(stepEls()[0], '选择…'));
    expect(spies.pickRepo.mock.calls.length).toBe(1);
    const r1 = await spies.pickRepo.mock.results[0].value;
    expect([r1.kind, r1.problem]).toEqual(['rejected', 'not-git']);
    expect(icons()[0]).toBe('未通过');
    expect(stepTexts()[0]).toContain(r1.path);
    expect(textOf(alerts()[0])).toContain('这个文件夹不是 Git 仓库。');
    await clickSettle(btn(alerts()[0], '重新选择'));
    const r2 = await spies.pickRepo.mock.results[1].value;
    expect([r2.kind, r2.problem]).toEqual(['rejected', 'no-agent']);
    expect(textOf(alerts()[0])).toContain('这个仓库还没有接入 Themis Tally。');
    expect(textOf(alerts()[0].querySelector('code'))).toBe('python <ThemisTally>/scripts/kit_install.py install ' + r2.path);
    expect(stepTexts()[0]).toContain(r2.path);
    expect(spies.startService.mock.calls.length, '没保存之前不启动').toBe(0);
    await clickSettle(btn(alerts()[0], '重新选择'));
    const r3 = await spies.pickRepo.mock.results[2].value;
    expect(r3.kind).toBe('saved');
    expect(icons().slice(0, 3)).toEqual(['通过', '通过', '通过']);
    expect(stepTexts()[0]).toContain(r3.path);
    expect(alerts().length).toBe(0);
    expect(spies.startService.mock.calls, '拿到 id 后由 startService 启动它，恰一次').toEqual([[r3.id]]);
    advance(1500);
    await settle();
    expect(icons()).toEqual(['通过', '通过', '通过', '通过']);
    expect(spies.startService.mock.calls.length).toBe(1);
  });

  it('选择被取消（cancelled）什么也不改', async () => {
    const { spies } = await openFirst('first-launch', '', (_s, sp) => {
      sp.pickRepo.mockResolvedValueOnce({ kind: 'cancelled' });
    });
    const before = icons();
    await clickSettle(btn(stepEls()[0], '选择…'));
    expect(spies.pickRepo.mock.calls.length).toBe(1);
    expect(icons()).toEqual(before);
    expect(alerts().length).toBe(0);
    expect(spies.startService.mock.calls.length).toBe(0);
  });

  it('退出码 1：已退出 · 退出码 1，首句与次句，[切换到那个窗口] 是禁用按钮、点了不调任何桩函数，[更换…] 照常可用，不自动重启', async () => {
    const { spies } = await openFirst('exit-1');
    advance(1500);
    await settle();
    expect(icons()).toEqual(['通过', '通过', '通过', '未通过']);
    expect(stepTexts()[3]).toContain('已退出 · 退出码 1');
    const a = alerts();
    expect(a.length).toBe(1);
    expect(textOf(a[0])).toContain('这个仓库已经在另一个窗口里打开了。');
    expect(textOf(a[0])).toContain('切换到那个窗口继续。');
    const sw = btn(document, '切换到那个窗口');
    expect(sw.disabled, '禁用按钮（站主 Q2-A）').toBe(true);
    expect(btn(stepEls()[0], '更换…').disabled, '[更换…] 照常可用').toBe(false);
    expect(body()).toContain('处理好上面标出的问题，再接着检查');
    const starts = spies.startService.mock.calls.length;
    expect(starts).toBeLessThanOrEqual(1);
    const before = totalCalls(spies);
    fireEvent.click(sw);
    await settle();
    expect(totalCalls(spies), '点它不调任何桩函数').toBe(before);
    advance(5000);
    await settle();
    expect(spies.startService.mock.calls.length, 'exited 时不自动重启').toBe(starts);
    expect(btn(document, '进入').disabled).toBe(true);
  });

  it('过渡：退出码 1 的 [切换到那个窗口] 悬停 400ms 出现提示「接入真实外壳后可用」', async () => {
    await openFirst('exit-1');
    advance(1500);
    await settle();
    const sw = btn(document, '切换到那个窗口');
    const wrap = sw.parentElement as HTMLElement;
    expect(wrap.classList.contains('tt-tooltip-wrap'), 'DisabledAction 外面是 Tooltip 的包裹 span').toBe(true);
    fireEvent.mouseEnter(wrap);
    advance(399);
    expect(document.querySelector('[role="tooltip"]')).toBeNull();
    advance(1);
    expect(textOf(document.querySelector('[role="tooltip"]'))).toBe('接入真实外壳后可用');
  });

  it('退出码 2：只有首句「应用文件不完整，请重新安装。」，没有次句、没有按钮', async () => {
    await openFirst('exit-2');
    advance(1500);
    await settle();
    expect(stepTexts()[3]).toContain('已退出 · 退出码 2');
    const a = alerts();
    expect(a.length).toBe(1);
    expect(textOf(a[0])).toBe('应用文件不完整，请重新安装。');
    expect(a[0].querySelectorAll('button').length, '无按钮').toBe(0);
    expect(btns(document, '重新启动').length).toBe(0);
    expect(btns(document, '切换到那个窗口').length).toBe(0);
  });

  it('其他退出码（crash 的 3）：首句带退出码、次句、[重新启动] → startService(id)；之后转圈、1500ms 后 running；exited 时不自动重启', async () => {
    const { spies, state } = await openFirst('crash');
    expect(spies.startService.mock.calls.length, 'exited 时不自动重启').toBe(0);
    expect(icons()[3]).toBe('未通过');
    expect(stepTexts()[3]).toContain('已退出 · 退出码 3');
    const a = alerts()[0];
    expect(textOf(a)).toContain('本机服务没能启动（退出码 3）。');
    expect(textOf(a)).toContain('重新启动；反复出现时打开设置检查 Python 与 kit。');
    await clickSettle(btn(a, '重新启动'));
    expect(spies.startService.mock.calls, '[重新启动] 调 startService(id)').toEqual([[curId(state)]]);
    expect(icons()[3]).toBe('正在启动');
    advance(1500);
    await settle();
    expect(icons()).toEqual(['通过', '通过', '通过', '通过']);
    expect(stepTexts()[3]).toContain('已启动 · pid 18244');
    expect(spies.startService.mock.calls.length).toBe(1);
  });

  it('[进入]：服务 running 之后可用；点了地址立刻是 #/overview，mock 与 shell 都保留，服务窗口已渲染', async () => {
    await openFirst('ready', '&mock=data');
    advance(1500);
    await settle();
    fireEvent.click(btn(document, '进入'));
    const hash = window.location.hash;
    expect(pathOf(hash)).toBe('#/overview');
    expect(queryOf(hash).get('mock')).toBe('data');
    expect(queryOf(hash).get('shell')).toBe('ready');
    expect(document.querySelector('[data-shell-window]')).toBeNull();
    expect(document.querySelector('nav[aria-label="主导航"]')).not.toBeNull();
  });

  it('卸载时取消订阅 service-state', async () => {
    const offs: any[] = [];
    const { unmount } = await openFirst('ready', '', (_shell, sp, orig) => {
      sp.on.mockImplementation((name: any, listener: any) => {
        const off = orig.on(name, listener);
        const wrapped = vi.fn(() => off());
        offs.push(wrapped);
        return wrapped;
      });
    });
    expect(offs.length).toBeGreaterThanOrEqual(1);
    expect(offs.every((o) => o.mock.calls.length === 0)).toBe(true);
    unmount();
    expect(offs.every((o) => o.mock.calls.length >= 1), '卸载时每个订阅都取消').toBe(true);
  });
});

describe('D05 复制命令的三种结果', () => {
  async function copyOnce(clipboard: any): Promise<{ text: string; command: string; writeCalls: any[] }> {
    await openFirst('no-agent');
    if (clipboard === undefined) {
      delete (navigator as any).clipboard;
    } else {
      Object.defineProperty(navigator, 'clipboard', { value: clipboard, configurable: true });
    }
    const command = textOf(alerts()[0].querySelector('code'));
    const copy = document.querySelector('button[aria-label="复制命令"]') as HTMLButtonElement;
    expect(copy, '命令旁有复制钮').not.toBeNull();
    await clickSettle(copy);
    await settle();
    expect(document.querySelectorAll('[role="status"]').length, '不设 role').toBe(0);
    return { text: body(), command, writeCalls: clipboard && clipboard.writeText ? clipboard.writeText.mock.calls : [] };
  }

  it('没有 navigator.clipboard：「这个环境没有剪贴板接口」', async () => {
    try {
      const out = await copyOnce(undefined);
      expect(out.text).toContain('这个环境没有剪贴板接口');
      expect(out.text).not.toContain('已复制');
    } finally {
      delete (navigator as any).clipboard;
    }
  });

  it('writeText 成功：「已复制」，写入的就是命令文字', async () => {
    const clipboard = { writeText: vi.fn(async (_t: string) => undefined) };
    try {
      const out = await copyOnce(clipboard);
      expect(out.text).toContain('已复制');
      expect(out.writeCalls).toEqual([[out.command]]);
    } finally {
      delete (navigator as any).clipboard;
    }
  });

  it('writeText 抛错：「复制失败」', async () => {
    const clipboard = {
      writeText: vi.fn(async (_t: string) => {
        throw new Error('denied');
      }),
    };
    try {
      const out = await copyOnce(clipboard);
      expect(out.text).toContain('复制失败');
      expect(out.text).not.toContain('已复制');
    } finally {
      delete (navigator as any).clipboard;
    }
  });
});
"""

# 服务状态与恢复（D06）
PROBE_SERVICE = PRELUDE + r"""
function pad(n: number): string {
  return String(n).padStart(2, '0');
}
function clock(at: any): string {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? '' : pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
}
function exitCodeEl(): HTMLElement {
  const el = document.querySelector('[data-exit-code]');
  expect(el, '应有带 data-exit-code 的元素').not.toBeNull();
  return el as HTMLElement;
}
function body(): string {
  return textOf(document.body);
}
function h1s(): string[] {
  return Array.from(document.querySelectorAll('h1')).map((h) => textOf(h));
}
// 打开服务状态页；exit-N 场景若缺省不是 exited，先用 restartService 把桩推到 exited（再挂载）
async function openService(scn: string, extra: string = '', prepare?: (shell: any, spies: Record<string, any>, orig: Record<string, any>) => void) {
  vi.useFakeTimers();
  const hash = '#/service-status?shell=' + scn + extra;
  const shell = await grabShell(hash);
  let state = await shell.getState();
  if (kindOf(state) !== 'exited' && scn !== 'ready') {
    await shell.restartService();
    vi.advanceTimersByTime(1500);
    state = await shell.getState();
  }
  const orig = origOf(shell);
  const spies = spyAll(shell);
  if (prepare) prepare(shell, spies, orig);
  const r = await mountApp(hash);
  return { shell, spies, state, unmount: r.unmount };
}

describe('D06 过渡：服务状态页的内容', () => {
  it('退出码 1、2、3 逐个查：danger 图标、h1、data-exit-code、「退出码 N · 时刻。重启后会重新读取数据。」、说明、两个按钮、document.title、不设 role=alert', async () => {
    const want: Array<[string, number, string]> = [
      ['exit-1', 1, '这个仓库已经在另一个窗口里打开了。'],
      ['exit-2', 2, '应用文件不完整，请重新安装。'],
      ['crash', 3, '本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。'],
    ];
    const ctx: any = await import('../src/shellpages/shellContext');
    for (const [scn, code, desc] of want) {
      ctx.resetShellStubs();
      const { state, unmount } = await openService(scn);
      expect(h1s(), scn).toEqual(['本机服务已停止']);
      expect(textOf(exitCodeEl()), scn + ' 的退出码').toBe(String(code));
      expect(exitCodeEl().tagName.toLowerCase(), '退出码放在 code 元素里').toBe('code');
      const at = svcOf(state).at;
      const clk = clock(at);
      if (clk) {
        expect(body(), scn).toContain('退出码 ' + code + ' · ' + clk + '。重启后会重新读取数据。');
      } else {
        expect(body(), scn).toMatch(new RegExp('退出码 ' + code + ' · \\d\\d:\\d\\d:\\d\\d。重启后会重新读取数据。'));
      }
      expect(body(), scn + ' 的说明').toContain(desc);
      const icon = document.querySelector('svg[width="32"][aria-hidden="true"]');
      expect(icon, scn + '：ServerCrashIcon 32，aria-hidden').not.toBeNull();
      expect(btns(document, '重启服务').length, scn).toBe(1);
      expect(btns(document, '打开设置').length, scn).toBe(1);
      expect(btn(document, '重启服务').disabled).toBe(false);
      expect(btn(document, '打开设置').disabled).toBe(false);
      expect(document.querySelectorAll('[role="alert"]').length, '不设 role=alert').toBe(0);
      expect(document.title).toBe('本机服务已停止 · Themis Tally');
      unmount();
    }
  });

  it('service 不是 exited 时（ready：idle）退出码写「—」', async () => {
    await openService('ready');
    expect(textOf(exitCodeEl())).toBe('—');
  });
});

describe('D06 过渡：重启与跳转', () => {
  it('[重启服务]：调一次 restartService() 并进入加载态「正在重启…」；收到 running 才跳回 #/overview，保留查询串', async () => {
    const { spies } = await openService('crash', '&mock=data');
    expect(spies.restartService.mock.calls.length, '只点才调').toBe(0);
    fireEvent.click(btn(document, '重启服务'));
    expect(spies.restartService.mock.calls.length).toBe(1);
    await settle();
    const loading = btn(document, '正在重启…');
    expect(loading.disabled).toBe(true);
    expect(loading.getAttribute('aria-busy')).toBe('true');
    fireEvent.click(loading);
    await settle();
    expect(spies.restartService.mock.calls.length, '加载态点不动').toBe(1);
    advance(1499);
    await settle();
    expect(pathOf(window.location.hash), '没收到 running 之前不跳').toBe('#/service-status');
    advance(1);
    const hash = window.location.hash;
    expect(pathOf(hash), '收到 running 立刻跳回服务窗口').toBe('#/overview');
    expect(queryOf(hash).get('mock')).toBe('data');
    expect(queryOf(hash).get('shell')).toBe('crash');
    expect(document.querySelector('[data-shell-window]')).toBeNull();
    expect(document.querySelector('nav[aria-label="主导航"]')).not.toBeNull();
  });

  it('直接打开这一页不会自己跳走：推进时间后仍在 #/service-status（K15）', async () => {
    await openService('crash');
    advance(10000);
    await settle();
    expect(pathOf(window.location.hash)).toBe('#/service-status');
    expect(h1s()).toEqual(['本机服务已停止']);
  });

  it('重启后仍是 exited（exit-1）：留在本页，退出码与按钮恢复', async () => {
    await openService('exit-1');
    fireEvent.click(btn(document, '重启服务'));
    await settle();
    advance(1500);
    await settle();
    expect(pathOf(window.location.hash)).toBe('#/service-status');
    expect(textOf(exitCodeEl())).toBe('1');
    expect(btn(document, '重启服务').disabled, '恢复可点').toBe(false);
  });

  it('推送 exited 2：退出码、时刻与说明都换掉，按钮恢复（把 exit-2 桩发出的 exited 事件原样交给 exit-1 页的订阅者）', async () => {
    vi.useFakeTimers();
    const other = await grabShell('#/service-status?shell=exit-2');
    const rec = record(other);
    await other.restartService();
    vi.advanceTimersByTime(1500);
    const p2 = [...rec.events].reverse().find((e) => kindOf(e) === 'exited');
    expect(p2, 'exit-2 桩应发出 exited 事件').toBeTruthy();
    expect(svcOf(p2).exitCode).toBe(2);
    const listeners: any[] = [];
    const { spies } = await openService('exit-1', '', (_shell, sp, orig) => {
      sp.on.mockImplementation((name: any, l: any) => {
        listeners.push(l);
        return orig.on(name, l);
      });
      sp.restartService.mockImplementation(async () => undefined);
    });
    expect(textOf(exitCodeEl())).toBe('1');
    expect(listeners.length, '页面订阅了 service-state').toBeGreaterThanOrEqual(1);
    fireEvent.click(btn(document, '重启服务'));
    await settle();
    expect(btns(document, '正在重启…').length).toBe(1);
    act(() => {
      listeners.forEach((l) => l(p2));
    });
    await settle();
    expect(textOf(exitCodeEl()), '退出码换成 2').toBe('2');
    expect(body()).toContain('应用文件不完整，请重新安装。');
    expect(body()).not.toContain('这个仓库已经在另一个窗口里打开了。');
    const clk = clock(svcOf(p2).at);
    if (clk) expect(body()).toContain('退出码 2 · ' + clk + '。重启后会重新读取数据。');
    expect(btn(document, '重启服务').disabled, '恢复可点').toBe(false);
    expect(spies.restartService.mock.calls.length).toBe(1);
    expect(pathOf(window.location.hash), '没有跳走').toBe('#/service-status');
  });

  it('[打开设置]：点了地址立刻是 #/settings，设置页已渲染', async () => {
    await openService('exit-1', '&mock=data');
    fireEvent.click(btn(document, '打开设置'));
    expect(pathOf(window.location.hash)).toBe('#/settings');
    expect(queryOf(window.location.hash).get('mock')).toBe('data');
    expect(queryOf(window.location.hash).get('shell')).toBe('exit-1');
    expect(h1s()).toEqual(['设置']);
  });
});
"""

# 设置（D07、D08 无 Provider、D09）：单独渲染 SettingsPage，不外包 Provider（主题用本地状态，桩按 shell= 取缓存实例）
PROBE_SETTINGS = PRELUDE + r"""
function never(): Promise<any> {
  return new Promise(() => {});
}
function grp(name: string): HTMLElement {
  const el = document.querySelector('[data-settings-group="' + name + '"]');
  expect(el, '应有 data-settings-group=' + name).not.toBeNull();
  return el as HTMLElement;
}
function repoRows(): HTMLElement[] {
  return Array.from(grp('repos').querySelectorAll('[data-repo-id]')) as HTMLElement[];
}
function rowOf(id: string): HTMLElement {
  const hit = repoRows().find((r) => r.getAttribute('data-repo-id') === id);
  expect(hit, '找不到仓库行 ' + id).toBeTruthy();
  return hit as HTMLElement;
}
function alertsIn(root: ParentNode): HTMLElement[] {
  return Array.from(root.querySelectorAll('[role="alert"]')) as HTMLElement[];
}
function radio(group: HTMLElement, label: string, text: string): HTMLButtonElement {
  const g = group.querySelector('[role="radiogroup"][aria-label="' + label + '"]');
  expect(g, '应有 aria-label=' + label + ' 的分段选择').not.toBeNull();
  const hit = Array.from((g as HTMLElement).querySelectorAll('[role="radio"]')).find((b) => textOf(b) === text);
  expect(hit, '「' + label + '」里找不到「' + text + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function radios(group: HTMLElement, label: string): string[] {
  const g = group.querySelector('[role="radiogroup"][aria-label="' + label + '"]') as HTMLElement;
  return Array.from(g.querySelectorAll('[role="radio"]')).map((b) => textOf(b));
}
function checkedOf(group: HTMLElement, label: string): string {
  const g = group.querySelector('[role="radiogroup"][aria-label="' + label + '"]') as HTMLElement;
  const hit = Array.from(g.querySelectorAll('[role="radio"]')).find((b) => b.getAttribute('aria-checked') === 'true');
  return hit ? textOf(hit) : '';
}
function pad(n: number): string {
  return String(n).padStart(2, '0');
}
function localTime(iso: string): string {
  const d = new Date(iso);
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
}

async function openSettings(scn: string = 'ready', prepare?: (shell: any, spies: Record<string, any>, orig: Record<string, any>) => void) {
  vi.useFakeTimers();
  const hash = '#/settings?shell=' + scn;
  const shell = await grabShell(hash);
  const state = await shell.getState();
  const orig = origOf(shell);
  const spies = spyAll(shell);
  if (prepare) prepare(shell, spies, orig);
  window.location.hash = hash;
  const mod: any = await import('../src/pages/SettingsPage');
  const Page = mod.default ?? mod.SettingsPage;
  expect(Page, 'SettingsPage 应默认导出').toBeTruthy();
  const r = render(<Page />);
  await settle();
  return { shell, spies, state, unmount: r.unmount };
}

describe('D07 过渡：设置页的结构与数据取自桩', () => {
  it('PageFrame 的 h1「设置」、恰一个 data-page-state=data、根元素 data-page=settings、五个 section 的顺序与 h2', async () => {
    const { spies } = await openSettings('ready');
    expect(document.querySelectorAll('[data-page-state]').length).toBe(1);
    expect((document.querySelector('[data-page-state]') as HTMLElement).getAttribute('data-page-state')).toBe('data');
    expect(textOf(document.querySelector('h1'))).toBe('设置');
    expect(document.querySelectorAll('h1').length).toBe(1);
    const root = document.querySelector('[data-page="settings"]') as HTMLElement;
    expect(root, '根元素 data-page=settings').not.toBeNull();
    expect(root.querySelector('h1'), 'SettingsView 不渲染 h1').toBeNull();
    expect(root.querySelector('[data-page-state]'), 'SettingsView 不写 data-page-state').toBeNull();
    const groups = Array.from(document.querySelectorAll('[data-settings-group]'));
    expect(groups.map((g) => g.getAttribute('data-settings-group'))).toEqual(['repos', 'runtime', 'usage', 'appearance', 'about']);
    const titles = groups.map((g) => textOf(g.querySelector('h2')));
    expect(titles).toEqual(['仓库', '运行环境', '规划端用量', '外观', '关于']);
    expect(textOf(document.body)).toContain('设置保存在桌面应用自己的用户数据目录里，不写进仓库的配置');
    expect(spies.getState.mock.calls.length, 'getState 只在挂载时调一次').toBe(1);
    expect(alertsIn(document).length).toBe(0);
  });

  it('getState 被拒：交给 PageFrame 的通用出错块「没有收到服务的回应」', async () => {
    await openSettings('ready', (_s, sp) => {
      sp.getState.mockRejectedValue(new Error('boom'));
    });
    expect((document.querySelector('[data-page-state]') as HTMLElement).getAttribute('data-page-state')).toBe('error');
    expect(textOf(document.body)).toContain('没有收到服务的回应');
    expect(document.querySelector('[data-page="settings"]')).toBeNull();
  });
});

describe('D07 过渡：仓库组', () => {
  it('表：列名、两行、当前仓库带「当前」与「现在」、其他用相对时间且 title 写本地时间与 UTC 原值', async () => {
    const { state } = await openSettings('ready');
    const g = grp('repos');
    expect(Array.from(g.querySelectorAll('th')).map((th) => textOf(th))).toEqual(['名称', '路径', '上次打开', '操作']);
    expect(g.querySelector('table'), '自写原生 table').not.toBeNull();
    const rows = repoRows();
    expect(rows.map((r) => r.getAttribute('data-repo-id'))).toEqual(state.settings.repos.map((r: any) => r.id));
    for (const repo of state.settings.repos) {
      const row = rowOf(repo.id);
      expect(textOf(row)).toContain(repo.name);
      expect(textOf(row)).toContain(repo.path);
    }
    const cur = rowOf(state.settings.currentRepo);
    expect(textOf(cur)).toContain('当前');
    expect(textOf(cur)).toContain('现在');
    const other = state.settings.repos.find((r: any) => r.id !== state.settings.currentRepo);
    const orow = rowOf(other.id);
    expect(textOf(orow)).not.toContain('当前');
    expect(textOf(orow)).toMatch(/(秒|分钟|小时|天)前/);
    const titled = Array.from(orow.querySelectorAll('[title]')).map((e) => e.getAttribute('title') || '');
    expect(titled.some((t) => t.includes(localTime(other.lastOpened)) && t.includes('UTC') && t.includes(other.lastOpened)),
      '上次打开的 title 写本地时间与 UTC 原值：' + JSON.stringify(titled)).toBe(true);
    expect(textOf(g)).toContain('“从列表移除”只从应用里移除，不动仓库。');
  });

  it('[从列表移除] 调 saveSettings({ removeRepo: id })，只用返回值更新；当前仓库的移除是禁用按钮、提示「不能移除当前打开的仓库」', async () => {
    const { spies, state } = await openSettings('ready');
    const cur = rowOf(state.settings.currentRepo);
    const dis = btn(cur, '从列表移除');
    expect(dis.disabled, '当前仓库不能移除').toBe(true);
    fireEvent.click(dis);
    await settle();
    expect(spies.saveSettings.mock.calls.length).toBe(0);
    fireEvent.mouseEnter(dis.parentElement as HTMLElement);
    advance(400);
    expect(textOf(document.querySelector('[role="tooltip"]'))).toBe('不能移除当前打开的仓库');
    fireEvent.mouseLeave(dis.parentElement as HTMLElement);
    const other = state.settings.repos.find((r: any) => r.id !== state.settings.currentRepo);
    await clickSettle(btn(rowOf(other.id), '从列表移除'));
    expect(spies.saveSettings.mock.calls).toEqual([[{ removeRepo: other.id }]]);
    expect(repoRows().map((r) => r.getAttribute('data-repo-id'))).toEqual([state.settings.currentRepo]);
  });

  it('[添加仓库…] 调 pickRepo()；saved 表里多一行；cancelled 什么也不做', async () => {
    const { spies, state } = await openSettings('ready');
    await clickSettle(btn(grp('repos'), '添加仓库…'));
    expect(spies.pickRepo.mock.calls.length).toBe(1);
    const r = await spies.pickRepo.mock.results[0].value;
    expect(r.kind).toBe('saved');
    expect(repoRows().length).toBe(state.settings.repos.length + 1);
    expect(repoRows().map((x) => x.getAttribute('data-repo-id'))).toContain(r.id);
    expect(spies.saveSettings.mock.calls.length).toBe(0);
    spies.pickRepo.mockResolvedValueOnce({ kind: 'cancelled' });
    await clickSettle(btn(grp('repos'), '添加仓库…'));
    expect(repoRows().length, 'cancelled 什么也不做').toBe(state.settings.repos.length + 1);
    expect(alertsIn(grp('repos')).length).toBe(0);
  });

  it('first-launch：「还没有添加仓库」；添加依次被拒（not-git、no-agent 另给接入命令）、最后保存', async () => {
    const { spies } = await openSettings('first-launch');
    const g = grp('repos');
    expect(repoRows().length).toBe(0);
    expect(textOf(g)).toContain('还没有添加仓库');
    await clickSettle(btn(g, '添加仓库…'));
    let a = alertsIn(grp('repos'));
    expect(a.length).toBe(1);
    expect(textOf(a[0])).toContain('这个文件夹不是 Git 仓库。');
    const table = grp('repos').querySelector('table') as HTMLElement;
    expect(a[0].compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING, '错误提示在本组顶部、表之前').toBeTruthy();
    await clickSettle(btn(grp('repos'), '添加仓库…'));
    a = alertsIn(grp('repos'));
    expect(textOf(a[0])).toContain('这个仓库还没有接入 Themis Tally。');
    expect(textOf(a[0])).toContain('kit_install.py install');
    await clickSettle(btn(grp('repos'), '添加仓库…'));
    expect(spies.pickRepo.mock.calls.length).toBe(3);
    expect(repoRows().length, '保存后表里多一行').toBe(1);
    expect(textOf(grp('repos'))).not.toContain('还没有添加仓库');
  });
});

describe('D07 过渡：运行环境与规划端用量', () => {
  it('ready：Python 与 kit 各一行（路径、caption）、两个 [更改…] 依次调 pickPython()、pickKit()；没有 [恢复自动检测]；版本信息与组底说明', async () => {
    const { spies } = await openSettings('ready');
    const g = grp('runtime');
    const t = textOf(g);
    expect(t).toContain('C:/Python313/python.exe');
    expect(t).toContain('自动检测 · 3.13.1');
    expect(t).toContain('仓库里装好的 · 2.12.0');
    expect(t).toContain('0.0.0');
    expect(t).toContain('改了 Python、kit 或会话记录目录，保存后外壳会重启本机服务。');
    expect(btns(g, '恢复自动检测').length).toBe(0);
    const change = btns(g, '更改…');
    expect(change.length).toBe(2);
    await clickSettle(change[0]);
    expect([spies.pickPython.mock.calls.length, spies.pickKit.mock.calls.length]).toEqual([1, 0]);
    await clickSettle(btns(grp('runtime'), '更改…')[1]);
    expect([spies.pickPython.mock.calls.length, spies.pickKit.mock.calls.length]).toEqual([1, 1]);
    expect(spies.saveSettings.mock.calls.length, 'pick 不经 saveSettings').toBe(0);
  });

  it('no-python：caption 写「找不到 Python 3.10 及以上」', async () => {
    await openSettings('no-python');
    expect(textOf(grp('runtime'))).toContain('找不到 Python 3.10 及以上');
  });

  it('custom：手动指定 · 3.12.4、外部目录 · 2.12.0；[恢复自动检测] 依次调 saveSettings({ resetPython: true })、({ resetKit: true })，用返回值更新', async () => {
    const { spies } = await openSettings('custom');
    let g = grp('runtime');
    expect(textOf(g)).toContain('手动指定 · 3.12.4');
    expect(textOf(g)).toContain('外部目录 · 2.12.0');
    expect(btns(g, '恢复自动检测').length).toBe(2);
    await clickSettle(btns(g, '恢复自动检测')[0]);
    expect(spies.saveSettings.mock.calls).toEqual([[{ resetPython: true }]]);
    g = grp('runtime');
    expect(btns(g, '恢复自动检测').length, 'Python 恢复后只剩 kit 的').toBe(1);
    expect(textOf(g)).not.toContain('手动指定 · 3.12.4');
    await clickSettle(btns(g, '恢复自动检测')[0]);
    expect(spies.saveSettings.mock.calls).toEqual([[{ resetPython: true }], [{ resetKit: true }]]);
    expect(btns(grp('runtime'), '恢复自动检测').length).toBe(0);
  });

  it('按钮调用期间是加载态，saveSettings 永不兑现时列表与 caption 都不变（不做乐观更新）', async () => {
    const { spies } = await openSettings('custom', (_s, sp) => {
      sp.saveSettings.mockImplementation(() => never());
    });
    const b = btns(grp('runtime'), '恢复自动检测')[0];
    fireEvent.click(b);
    await settle();
    expect(b.getAttribute('aria-busy'), '调用期间加载态').toBe('true');
    expect(b.disabled).toBe(true);
    expect(spies.saveSettings.mock.calls).toEqual([[{ resetPython: true }]]);
    expect(textOf(grp('runtime'))).toContain('手动指定 · 3.12.4');
    expect(btns(grp('runtime'), '恢复自动检测').length).toBe(2);
    const dir = btns(grp('usage'), '移除');
    if (dir.length > 0) {
      fireEvent.click(dir[0]);
      await settle();
      expect(btns(grp('usage'), '移除').length, '会话目录也不做乐观更新').toBe(dir.length);
    }
  });

  it('保存被拒：本组顶部 danger Banner（role=alert）「没能保存：…」，状态不变', async () => {
    await openSettings('custom', (_s, sp) => {
      sp.saveSettings.mockRejectedValue(new Error('磁盘已满'));
    });
    await clickSettle(btns(grp('runtime'), '恢复自动检测')[0]);
    const a = alertsIn(grp('runtime'));
    expect(a.length).toBe(1);
    expect(textOf(a[0]).startsWith('没能保存：')).toBe(true);
    expect(textOf(grp('runtime'))).toContain('手动指定 · 3.12.4');
  });

  it('规划端用量：没有目录时「未设置（可选）」；[选择目录…] 调 pickTranscriptDir()，保存后逐行显示路径与 [移除]，[移除] 调 saveSettings({ removeTranscriptDir: id })；只读不可手输', async () => {
    const { spies } = await openSettings('ready');
    let g = grp('usage');
    expect(textOf(g)).toContain('未设置（可选）');
    expect(textOf(g)).toContain('只读用量字段，不读对话内容。设置后在“日志与用量 › 用量”里按模型列出，分主线与子代理。保存后重启服务生效。');
    expect(g.querySelectorAll('input, textarea, select').length, '路径只能来自对话框，不能手输').toBe(0);
    await clickSettle(btn(g, '选择目录…'));
    expect(spies.pickTranscriptDir.mock.calls.length).toBe(1);
    const r = await spies.pickTranscriptDir.mock.results[0].value;
    expect(r.kind).toBe('saved');
    g = grp('usage');
    expect(textOf(g)).toContain(r.path);
    expect(textOf(g)).not.toContain('未设置（可选）');
    const id = r.state.settings.transcriptDirs.find((d: any) => d.path === r.path).id;
    await clickSettle(btn(g, '移除'));
    expect(spies.saveSettings.mock.calls).toEqual([[{ removeTranscriptDir: id }]]);
    expect(textOf(grp('usage'))).toContain('未设置（可选）');
  });

  it('custom：两个会话目录各有 [移除]', async () => {
    const { spies, state } = await openSettings('custom');
    const g = grp('usage');
    expect(state.settings.transcriptDirs.length).toBe(2);
    for (const d of state.settings.transcriptDirs) {
      expect(textOf(g)).toContain(d.path);
    }
    expect(btns(g, '移除').length).toBe(2);
    await clickSettle(btns(g, '移除')[0]);
    expect(spies.saveSettings.mock.calls).toEqual([[{ removeTranscriptDir: state.settings.transcriptDirs[0].id }]]);
  });
});

describe('D07 load 是稳定引用', () => {
  it('改密度、选目录、添加仓库之后 getState 仍只调一次；点刷新再加一次，刷新带来的新数据换掉本地状态', async () => {
    let n = 0;
    let refreshedRepos = 0;
    const { spies } = await openSettings('ready', (_shell, sp, orig) => {
      sp.getState.mockImplementation(async () => {
        const s = await orig.getState();
        n += 1;
        if (n >= 2) {
          // 合同：ready 场景四个 pick 各给一个 saved（外壳校验通过并已保存），点了「添加仓库…」之后桩里是初始数加 1；
          // 站主指明的 D07 修法：期望值按刷新那次 getState 实际返回的仓库数算，不按初始数减 1
          s.settings.repos.pop();
          refreshedRepos = s.settings.repos.length;
        }
        return s;
      });
    });
    expect(spies.getState.mock.calls.length).toBe(1);
    await clickSettle(radio(grp('appearance'), '密度', '紧凑'));
    await clickSettle(btn(grp('usage'), '选择目录…'));
    await clickSettle(btn(grp('repos'), '添加仓库…'));
    expect(spies.getState.mock.calls.length, '操作不重取').toBe(1);
    await clickSettle(btn(document.body, '刷新'));
    expect(spies.getState.mock.calls.length, '点刷新再加一次').toBe(2);
    expect(repoRows().length, '刷新带来的新数据换掉本地状态').toBe(refreshedRepos);
  });
});

describe('D08 外观（无 Provider 时退回本地状态）', () => {
  it('主题分段选择：选项、点击切换 aria-checked、调 saveSettings({ theme })；没有 Provider 不抛错', async () => {
    const { spies } = await openSettings('ready');
    const g = grp('appearance');
    expect(radios(g, '主题')).toEqual(['跟随系统', '亮', '暗']);
    await clickSettle(radio(g, '主题', '亮'));
    expect(checkedOf(grp('appearance'), '主题')).toBe('亮');
    expect(spies.saveSettings.mock.calls).toEqual([[{ theme: 'light' }]]);
    await clickSettle(radio(grp('appearance'), '主题', '跟随系统'));
    expect(checkedOf(grp('appearance'), '主题')).toBe('跟随系统');
    expect(spies.saveSettings.mock.calls[1]).toEqual([{ theme: 'system' }]);
  });

  it('保存被拒：主题已切换，Banner「主题已切换，但没能保存：…」', async () => {
    await openSettings('ready', (_s, sp) => {
      sp.saveSettings.mockRejectedValue(new Error('磁盘已满'));
    });
    await clickSettle(radio(grp('appearance'), '主题', '亮'));
    expect(checkedOf(grp('appearance'), '主题'), '先切换').toBe('亮');
    const a = alertsIn(grp('appearance'));
    expect(a.length).toBe(1);
    expect(textOf(a[0]).startsWith('主题已切换，但没能保存：')).toBe(true);
  });

  it('密度分段选择：标准/紧凑，value 取返回的 settings.density；点击只调 saveSettings({ density })；caption「紧凑：表格行高 32」', async () => {
    const { spies } = await openSettings('ready');
    const g = grp('appearance');
    expect(radios(g, '密度')).toEqual(['标准', '紧凑']);
    expect(checkedOf(g, '密度')).toBe('标准');
    expect(textOf(g)).toContain('紧凑：表格行高 32');
    await clickSettle(radio(g, '密度', '紧凑'));
    expect(spies.saveSettings.mock.calls).toEqual([[{ density: 'compact' }]]);
    expect(checkedOf(grp('appearance'), '密度')).toBe('紧凑');
  });

  it('密度只按返回值变：saveSettings 永不兑现时仍是「标准」', async () => {
    const { spies } = await openSettings('ready', (_s, sp) => {
      sp.saveSettings.mockImplementation(() => never());
    });
    await clickSettle(radio(grp('appearance'), '密度', '紧凑'));
    expect(spies.saveSettings.mock.calls).toEqual([[{ density: 'compact' }]]);
    expect(checkedOf(grp('appearance'), '密度'), '不做乐观更新').toBe('标准');
  });

  it('custom 的密度是紧凑', async () => {
    await openSettings('custom');
    expect(checkedOf(grp('appearance'), '密度')).toBe('紧凑');
  });
});

describe('D09 过渡：关于、许可清单与外部链接', () => {
  it('版本与两个按钮；[开源许可清单] 打开对话框：Lucide 1.59.0 ISC、Sarasa Gothic 0.36.0 SIL OFL 1.1、随包路径，只当文字，不写字体文件名', async () => {
    await openSettings('ready');
    const g = grp('about');
    expect(textOf(g)).toContain('版本 0.0.0');
    expect(textOf(g)).toContain('Themis Tally · 参验');
    await clickSettle(btn(g, '开源许可清单'));
    const dlg = document.querySelector('[role="dialog"]') as HTMLElement;
    expect(dlg).not.toBeNull();
    expect(dlg.getAttribute('aria-modal')).toBe('true');
    const t = textOf(dlg);
    expect(t).toContain('开源许可清单');
    for (const lit of ['Lucide', '1.59.0', 'ISC', 'Sarasa Gothic', '0.36.0', 'SIL OFL 1.1', 'licenses/lucide-1.59.0-LICENSE.txt', 'licenses/OFL.txt']) {
      expect(t, lit).toContain(lit);
    }
    expect(dlg.querySelectorAll('a').length, '只当文字，不做链接').toBe(0);
    for (const bad of ['.woff2', '.woff', '.ttf', '.otf', 'sarasa-mono-sc-']) {
      expect(t, '不写字体文件名 ' + bad).not.toContain(bad);
    }
    fireEvent.keyDown(dlg, { key: 'Escape' });
    await settle();
    expect(document.querySelector('[role="dialog"]'), 'Esc 关闭').toBeNull();
  });

  it('[项目主页]：先出确认对话框（标题、完整网址、说明），此时 openExternal 0 次；取消、Esc、关闭钮都不调，[打开] 恰调一次并关闭', async () => {
    const { spies, state } = await openSettings('ready');
    const url = state.app.homepage;
    expect(url).toMatch(/^https?:\/\//);
    const openCalls = vi.fn();
    const saved = Object.getOwnPropertyDescriptor(window, 'open');
    Object.defineProperty(window, 'open', { value: openCalls, configurable: true, writable: true });
    try {
      const closers: Array<(dlg: HTMLElement) => Promise<void>> = [
        async (dlg) => clickSettle(btn(dlg, '取消')),
        async (dlg) => {
          fireEvent.keyDown(dlg, { key: 'Escape' });
          await settle();
        },
        async (dlg) => clickSettle(dlg.querySelector('button[aria-label^="关闭"]') as HTMLElement),
      ];
      for (const close of closers) {
        await clickSettle(btn(grp('about'), '项目主页'));
        const dlg = document.querySelector('[role="dialog"]') as HTMLElement;
        expect(dlg, '点 [项目主页] 后出现对话框').not.toBeNull();
        expect(dlg.getAttribute('aria-modal')).toBe('true');
        expect(textOf(dlg)).toContain('在系统浏览器中打开？');
        expect(textOf(dlg.querySelector('code')), '正文是完整网址（code）').toBe(url);
        expect(textOf(dlg)).toContain('只允许 http 与 https；由外壳交给系统浏览器打开。');
        expect(btns(dlg, '取消').length).toBe(1);
        expect(btns(dlg, '打开').length).toBe(1);
        expect(spies.openExternal.mock.calls.length, '确认之前不调 openExternal').toBe(0);
        await close(dlg);
        expect(document.querySelector('[role="dialog"]'), '对话框已关').toBeNull();
        expect(spies.openExternal.mock.calls.length, '取消路径不调 openExternal').toBe(0);
      }
      await clickSettle(btn(grp('about'), '项目主页'));
      await clickSettle(btn(document.querySelector('[role="dialog"]') as HTMLElement, '打开'));
      expect(spies.openExternal.mock.calls, '[打开] 恰调一次，参数等于网址').toEqual([[url]]);
      expect(document.querySelector('[role="dialog"]'), '[打开] 之后关闭').toBeNull();
      expect(openCalls.mock.calls.length, '不调 window.open').toBe(0);
    } finally {
      if (saved) Object.defineProperty(window, 'open', saved);
      else delete (window as any).open;
    }
  });

  it('homepage 不是 http(s)：没有 [项目主页] 按钮，网址只作文字显示', async () => {
    const ctx: any = await import('../src/shellpages/shellContext');
    for (const bad of ['javascript:alert(1)', 'ftp://example.com/x', 'file:///C:/x']) {
      ctx.resetShellStubs();
      const { unmount } = await openSettings('ready', (_shell, sp, orig) => {
        sp.getState.mockImplementation(async () => {
          const s = await orig.getState();
          s.app.homepage = bad;
          return s;
        });
      });
      expect(btns(grp('about'), '项目主页').length, bad + ' 不显示按钮').toBe(0);
      expect(textOf(grp('about')), bad + ' 只作文字').toContain(bad);
      unmount();
    }
  });
});
"""

# 主题经 App 与标题栏同步（D08）
PROBE_APP = PRELUDE + r"""
function header(): HTMLElement {
  const el = document.querySelector('header');
  expect(el, '应有标题栏 header').not.toBeNull();
  return el as HTMLElement;
}
function themeTrigger(): HTMLElement {
  const el = header().querySelector('button[aria-haspopup="menu"][aria-label^="主题："]');
  expect(el, '标题栏里应有名称以「主题：」开头的菜单触发钮').not.toBeNull();
  return el as HTMLElement;
}
function pickFromTitleMenu(text: string) {
  const trigger = themeTrigger();
  act(() => {
    trigger.focus();
  });
  fireEvent.click(trigger);
  const menu = document.querySelector('[role="menu"]');
  expect(menu, '点触发钮后应出现 role=menu').not.toBeNull();
  const item = Array.from((menu as HTMLElement).querySelectorAll('[role="menuitem"], [role="menuitemradio"]')).find((i) => textOf(i) === text);
  expect(item, '菜单里找不到「' + text + '」').toBeTruthy();
  fireEvent.click(item as Element);
}
function group(name: string): HTMLElement {
  const el = document.querySelector('[data-settings-group="' + name + '"]');
  expect(el, '应有 data-settings-group=' + name).not.toBeNull();
  return el as HTMLElement;
}
function themeRadio(text: string): HTMLElement {
  const g = group('appearance').querySelector('[role="radiogroup"][aria-label="主题"]') as HTMLElement;
  const hit = Array.from(g.querySelectorAll('[role="radio"]')).find((b) => textOf(b) === text);
  expect(hit, '主题分段里找不到「' + text + '」').toBeTruthy();
  return hit as HTMLElement;
}
function checkedTheme(): string {
  const g = group('appearance').querySelector('[role="radiogroup"][aria-label="主题"]') as HTMLElement;
  const hit = Array.from(g.querySelectorAll('[role="radio"]')).find((b) => b.getAttribute('aria-checked') === 'true');
  return hit ? textOf(hit) : '';
}

describe('D08 主题经 App 与标题栏同步', () => {
  it('在设置页选亮：标题栏触发钮变「主题：亮」、data-theme 为 light、saveSettings({ theme: light }) 恰一次；在标题栏选跟随系统：设置页分段跟着变、不再调 saveSettings', async () => {
    vi.useFakeTimers();
    const shell = await grabShell('#/settings?shell=ready');
    const spies = spyAll(shell);
    await mountApp('#/settings?shell=ready&mock=data');
    expect(themeTrigger().getAttribute('aria-label')).toBe('主题：暗');
    expect(document.documentElement.getAttribute('data-theme')).toBeNull();
    fireEvent.click(themeRadio('亮'));
    await settle();
    expect(themeTrigger().getAttribute('aria-label'), '标题栏跟着变').toBe('主题：亮');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(spies.saveSettings.mock.calls).toEqual([[{ theme: 'light' }]]);
    expect(checkedTheme()).toBe('亮');
    pickFromTitleMenu('跟随系统');
    await settle();
    expect(document.documentElement.getAttribute('data-theme')).toBe('system');
    expect(checkedTheme(), '设置页分段跟着变').toBe('跟随系统');
    expect(themeTrigger().getAttribute('aria-label')).toBe('主题：跟随系统');
    expect(spies.saveSettings.mock.calls.length, '标题栏的选择不经设置页保存').toBe(1);
  });

  it('去过 #/first-run 再回 #/settings：主题与 data-theme 都不变（主题状态在根上）；不写 localStorage、sessionStorage', async () => {
    vi.useFakeTimers();
    await mountApp('#/settings?shell=ready&mock=data');
    pickFromTitleMenu('亮');
    await settle();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    hashTo('#/first-run?shell=checking');
    await settle();
    expect(document.querySelector('[data-shell-window]'), '已换成外壳窗口').not.toBeNull();
    expect(document.documentElement.getAttribute('data-theme'), '外壳窗口里主题照旧').toBe('light');
    hashTo('#/settings?shell=ready&mock=data');
    await settle();
    expect(document.querySelector('[data-shell-window]')).toBeNull();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(themeTrigger().getAttribute('aria-label')).toBe('主题：亮');
    expect(checkedTheme(), '设置页分段读到根上的主题').toBe('亮');
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
  });

  it('暗是缺省：选回暗之后 data-theme 去掉', async () => {
    vi.useFakeTimers();
    await mountApp('#/settings?shell=ready&mock=data');
    pickFromTitleMenu('亮');
    await settle();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    fireEvent.click(themeRadio('暗'));
    await settle();
    expect(document.documentElement.getAttribute('data-theme')).toBeNull();
    expect(themeTrigger().getAttribute('aria-label')).toBe('主题：暗');
  });
});
"""

# 隔离（D10）：api 模块换成包着原函数的替身，网络接口与 window.open 换成记录调用的替身
PROBE_ISOLATION = PRELUDE + r"""
import * as api from '../src/api';

vi.mock('../src/api', async (importOriginal) => {
  const actual: any = await importOriginal();
  const out: any = {};
  for (const k of Object.keys(actual)) {
    out[k] = typeof actual[k] === 'function' ? vi.fn(actual[k]) : actual[k];
  }
  return out;
});

const NAMES = ['fe' + 'tch', 'XMLHttp' + 'Request', 'Event' + 'Source', 'Web' + 'Socket'];
const netCalls: string[] = [];
const saved: Array<[any, string, PropertyDescriptor | undefined]> = [];

function stubAt(target: any, name: string, value: any) {
  saved.push([target, name, Object.getOwnPropertyDescriptor(target, name)]);
  Object.defineProperty(target, name, { value, configurable: true, writable: true });
}
function installNet() {
  netCalls.length = 0;
  for (const n of NAMES) {
    const stub: any = function (this: any) {
      netCalls.push(n);
      return n === NAMES[0] ? new Promise(() => {}) : undefined;
    };
    ['addEventListener', 'removeEventListener', 'close', 'open', 'send', 'setRequestHeader', 'abort'].forEach((m) => {
      stub.prototype[m] = () => {};
    });
    stubAt(globalThis, n, stub);
    if (typeof window !== 'undefined' && (window as any) !== globalThis) stubAt(window, n, stub);
  }
  stubAt(navigator, 'sendBeacon', () => {
    netCalls.push('sendBeacon');
    return false;
  });
  stubAt(window, 'open', () => {
    netCalls.push('window.open');
    return null;
  });
  stubAt(window, 'confirm', () => {
    netCalls.push('window.confirm');
    return false;
  });
}
function restoreNet() {
  while (saved.length > 0) {
    const [target, name, desc] = saved.pop() as [any, string, PropertyDescriptor | undefined];
    if (desc) Object.defineProperty(target, name, desc);
    else delete target[name];
  }
}
function apiFns(): string[] {
  return Object.keys(api).filter((k) => vi.isMockFunction((api as any)[k]));
}
function apiCalled(): string[] {
  return apiFns().filter((k) => (api as any)[k].mock.calls.length > 0);
}
function clearApi() {
  apiFns().forEach((k) => (api as any)[k].mockClear());
}
function inShell(): boolean {
  return /^#\/(first-run|service-status)(\/|\?|$)/.test(window.location.hash);
}
const SKIP = ['进入', '打开设置'];
// 点遍当前页面上可用的按钮（每个元素只点一次，最多 4 轮）；离开外壳窗口（重启成功跳回服务窗口）就停
async function pressAll(rounds: number = 4) {
  const done = new Set<Element>();
  for (let i = 0; i < rounds; i += 1) {
    const todo = (Array.from(document.querySelectorAll('button')) as HTMLButtonElement[]).filter(
      (b) => !b.disabled && !done.has(b) && !SKIP.includes(textOf(b)),
    );
    if (todo.length === 0) return;
    for (const b of todo) {
      if (!inShell()) return;
      done.add(b);
      if (!document.body.contains(b)) continue;
      fireEvent.click(b);
      await settle();
    }
  }
}

describe('D10 外壳窗口运行时不读 api 也不连网', () => {
  it('自检：替身真的会记录调用（探针不是空转）', async () => {
    installNet();
    try {
      (globalThis as any)[NAMES[0]]('x');
      new (globalThis as any)[NAMES[1]]();
      new (globalThis as any)[NAMES[2]]('x');
      new (globalThis as any)[NAMES[3]]('ws://x');
      navigator.sendBeacon('x');
      window.open('x');
      expect(netCalls.length).toBe(6);
    } finally {
      restoreNet();
    }
    expect(apiFns().length, 'api 模块里的函数都换成了替身').toBeGreaterThan(5);
    (api as any).getMetaNow();
    expect(apiCalled()).toEqual(['getMetaNow']);
    clearApi();
    expect(apiCalled()).toEqual([]);
  });

  it('经 App 打开 #/first-run 与 #/service-status 的全部 11 个场景：点遍按钮（[进入]、[打开设置] 除外）、推进桩计时器，api 替身与网络替身都是 0 次', async () => {
    installNet();
    vi.useFakeTimers();
    try {
      for (const win of ['first-run', 'service-status']) {
        for (const scn of SCEN) {
          clearApi();
          netCalls.length = 0;
          const r = await mountApp('#/' + win + '?shell=' + scn);
          expect(apiCalled(), win + ' ' + scn + ' 挂载后').toEqual([]);
          await pressAll();
          if (inShell()) expect(apiCalled(), win + ' ' + scn + ' 点遍按钮后').toEqual([]);
          advance(1500);
          await settle();
          if (inShell()) expect(apiCalled(), win + ' ' + scn + ' 推进 1500ms 后').toEqual([]);
          await pressAll();
          advance(5000);
          await settle();
          if (inShell()) expect(apiCalled(), win + ' ' + scn + ' 推进到底后').toEqual([]);
          expect(netCalls, win + ' ' + scn + ' 的网络替身与 window.open').toEqual([]);
          r.unmount();
          window.location.hash = '';
        }
      }
    } finally {
      restoreNet();
    }
  }, 120000);

  it('单独渲染 SettingsPage 点遍控件（含两个对话框与 [打开]）：api 替身 0 次、网络替身与 window.open 0 次', async () => {
    installNet();
    vi.useFakeTimers();
    try {
      for (const scn of ['ready', 'custom', 'first-launch', 'no-python', 'no-kit']) {
        clearApi();
        netCalls.length = 0;
        window.location.hash = '#/settings?shell=' + scn;
        const mod: any = await import('../src/pages/SettingsPage');
        const Page = mod.default ?? mod.SettingsPage;
        const r = render(<Page />);
        await settle();
        for (let round = 0; round < 3; round += 1) {
          const todo = (Array.from(document.querySelectorAll('button')) as HTMLButtonElement[]).filter((b) => !b.disabled);
          for (const b of todo) {
            if (!document.body.contains(b)) continue;
            fireEvent.click(b);
            await settle();
          }
        }
        advance(5000);
        await settle();
        expect(apiCalled(), '设置页 ' + scn).toEqual([]);
        expect(netCalls, '设置页 ' + scn + ' 的网络替身与 window.open').toEqual([]);
        r.unmount();
        window.location.hash = '';
      }
    } finally {
      restoreNet();
    }
  }, 120000);

  it('经 App 打开 #/settings：api 替身只被服务窗口自己的 getMetaNow、getStatus 调用，没有 getMeta', async () => {
    installNet();
    vi.useFakeTimers();
    try {
      clearApi();
      await mountApp('#/settings?shell=ready');
      advance(2000);
      await settle();
      const called = apiCalled();
      expect(called, '设置页数据来自桩，不读 getMeta').not.toContain('getMeta');
      for (const k of called) {
        expect(['getMetaNow', 'getStatus'], k + ' 不该被调用').toContain(k);
      }
      expect(called).toContain('getMetaNow');
      expect(netCalls).toEqual([]);
    } finally {
      restoreNet();
    }
  });
});
"""

PROBE_SPECS = {
    "stub": (PROBE_STUB, [f"{SP_REL}/shellStub.ts", f"{SP_REL}/shellContext.tsx"]),
    "route": (PROBE_ROUTE, [f"{SP_REL}/shellWindowRoute.ts", f"{SP_REL}/ShellWindow.tsx", f"{SRC_REL}/App.tsx"]),
    "firstrun": (PROBE_FIRSTRUN, [f"{SP_REL}/FirstRunView.tsx", f"{SP_REL}/shellContext.tsx"]),
    "service": (PROBE_SERVICE, [f"{SP_REL}/ServiceStatusView.tsx", f"{SP_REL}/shellContext.tsx"]),
    "settings": (PROBE_SETTINGS, [f"{SP_REL}/SettingsView.tsx", f"{SP_REL}/themePref.tsx", f"{SRC_REL}/pages/SettingsPage.tsx"]),
    "app": (PROBE_APP, [f"{SP_REL}/themePref.tsx", f"{SRC_REL}/App.tsx"]),
    "isolation": (PROBE_ISOLATION, [f"{SRC_REL}/api.ts", f"{SRC_REL}/App.tsx"]),
}
PROBE_ORDER = ("stub", "route", "firstrun", "service", "settings", "app", "isolation")

# 候选里出现其中任何一个，流水线才跑 npm（基线上都没有，没有东西可测）
CANDIDATE_MARKERS = tuple(f"{SP_REL}/{n}" for n in ("shellStub.ts", "shellContext.tsx", "ShellWindow.tsx", "FirstRunView.tsx",
                                                     "ServiceStatusView.tsx", "SettingsView.tsx"))

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
    """{文件名: ({分组名: {"passed": n, "bad": [(标题, 状态, 失败信息)]}}, 收集错误)}，分组名是最外层 describe 的名字。"""
    files = {}
    for result in data.get("testResults", []):
        name = Path(str(result.get("name", ""))).name
        groups, errors = {}, []
        items = result.get("assertionResults") or []
        if not items and result.get("status") == "failed":
            errors.append((result.get("message") or "")[:1500])
        for item in items:
            ancestors = item.get("ancestorTitles") or []
            group = groups.setdefault(ancestors[0] if ancestors else "", {"passed": 0, "bad": []})
            if item.get("status") == "passed":
                group["passed"] += 1
            else:
                group["bad"].append((item.get("title"), item.get("status"), "\n".join(item.get("failureMessages") or [])[:700]))
        files[name] = (groups, errors)
    return files


def unique_css_classes(css_text, other_css_texts):
    """这份 css 里有、别的 css 里都没有的类名（K20：构建产物里找每份文件独有的选择器）。"""
    mine = set(re.findall(r"\.([A-Za-z_][\w-]*)", strip_comments(css_text)))
    others = set()
    for other in other_css_texts:
        others |= set(re.findall(r"\.([A-Za-z_][\w-]*)", strip_comments(other)))
    return sorted(mine - others)


def dist_css_problems(dist_css, css_by_name, all_other_css=()):
    problems = []
    for name, text in css_by_name.items():
        others = [t for n, t in css_by_name.items() if n != name] + list(all_other_css)
        unique = unique_css_classes(text, others)
        if not unique:
            problems.append(f"{name}：找不到这份文件独有的类名（每份 css 都该有自己的类）")
            continue
        missing = [c for c in unique if not re.search(rf"\.{re.escape(c)}(?![\w-])", dist_css)]
        if missing:
            problems.append(f"{name}：构建产物（dist/assets 下的 css）里找不到它独有的类名 {missing[:6]}——这份 css 没被接进应用")
    return problems


def other_src_css_texts():
    """src 下不属于 shellpages 的 css（App.css、shell/*.css、components/*.css 等），用来排除“别处也有”的类名。"""
    out = []
    for path in SRC.rglob("*.css"):
        if path.parent.name != "shellpages":
            out.append(_read(path))
    return out


# ---------------------------------------------------------------------------
# 会话级夹具：四步 npm + 探针
# ---------------------------------------------------------------------------

# 合同检查项 V01 的 timeout 是 600s：夹具总预算压在 570s 以内，用完就停下并在断言里写明，不等调度器来杀。
PIPELINE_BUDGET = 570
STEP_CAPS = {
    "npm ci": 200,
    "npm run build": 120,
    "npm test": 240,
    "npm run check:contract": 40,
    "probe": 240,
}


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
        self.probe_summary = {}
        self.probe_unparsed = ""
        self.gate_probe_left = None
        self.dist_css = None


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
           "src/api.ts", "src/shell/router.ts", "src/shell/routes.ts")


def build_probe_source(key):
    return PROBE_SPECS[key][0]


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not any((REPO_ROOT / rel_path).is_file() for rel_path in CANDIDATE_MARKERS):
        pipe.reason = ("候选里还没有 src/shellpages/ 下的任何本片源码（基线），没有东西可测，未调用 npm；"
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
            build = run_step("npm run build", [npm, "run", "build"])
            if build is not None and build.code == 0:
                assets = WEB / "dist" / "assets"
                if assets.is_dir():
                    pipe.dist_css = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sorted(assets.glob("*.css")))
            run_step("npm test", [npm, "test"])
            run_step("npm run check:contract", [npm, "run", "check:contract"])
            uid = uuid.uuid4().hex[:12]
            for key in PROBE_ORDER:
                missing = [r for r in PROBE_SPECS[key][1] if not (REPO_ROOT / r).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                name = f"probe-t012-{uid}-{key}.test.tsx"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                written.append(path)
                path.write_text(build_probe_source(key), encoding="utf-8", newline="\n")
                pipe.probe_files[key] = name
            if pipe.probe_files:
                result_name = f"result-t012-{uid}.json"
                result_path = probe_dir / result_name
                written.append(result_path)
                step = run_step("probe", [npm, "test", "--", f"gate-probe/probe-t012-{uid}", "--reporter=json",
                                          f"--outputFile=gate-probe/{result_name}", "--testTimeout=60000"], label="probes")
                if step is not None:
                    data = None
                    if result_path.is_file():
                        try:
                            data = json.loads(result_path.read_text(encoding="utf-8"))
                        except ValueError:
                            data = None
                    if data is None:
                        data = parse_vitest_json(step.out)
                    if data is None:
                        pipe.probe_unparsed = step.tail
                    else:
                        pipe.probe_summary = summarize_vitest(data)
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
    step = pipe.steps.get("probes")
    assert step is not None, f"探针未运行：{pipe.stopped_reason or '前置步骤失败'}"
    assert not step.timed_out, f"探针超时被杀，用时 {step.seconds:.0f}s\n{step.tail}"
    assert pipe.probe_summary, f"探针的输出里找不到 Vitest 的 JSON：\n{pipe.probe_unparsed or step.tail}"
    name = pipe.probe_files.get(key)
    assert name in pipe.probe_summary, f"Vitest 的结果里没有探针文件 {name}：{sorted(pipe.probe_summary)}\n{step.tail}"
    groups, errors = pipe.probe_summary[name]
    assert not errors, f"探针 {key} 收集失败（导入或语法错误）：\n" + "\n".join(errors)
    want = probe_groups(PROBE_SPECS[key][0])[group]
    got = groups.get(group)
    assert got is not None, f"探针 {key} 的输出里没有分组「{group}」"
    assert not got["bad"], f"探针 {key}「{group}」有 {len(got['bad'])} 条没通过：\n" + "\n".join(
        f"- [{status}] {title}\n{msg}" for title, status, msg in got["bad"][:6])
    assert got["passed"] == want, f"探针 {key}「{group}」应有 {want} 条通过，实际 {got['passed']}"


# ---------------------------------------------------------------------------
# 流水线断言（D02–D10 的行为、D12 的构建接线、D13）
# ---------------------------------------------------------------------------

def test_d13_npm_four_steps_pass(pipeline):
    """D13：在 desktop/web 下 npm ci、npm run build（含 tsc --noEmit）、npm test（含执行端 8 份测试与全部既有测试）、
    npm run check:contract（W4）都通过。"""
    assert pipeline.ran, pipeline.reason
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)


def test_d12_k20_each_new_css_is_in_the_build_output(pipeline):
    """D12 / K20（接线，构建部分）：npm run build 之后 dist/assets 下的 css 里，每份新 css 独有的类名（从源文件解析、不写死）都找得到——
    某份 css 写对了却没被 import，这里会红。"""
    assert pipeline.ran, pipeline.reason
    assert_step_ok(pipeline, "npm run build")
    assert pipeline.dist_css, "构建产物里没有读到 dist/assets 下的 css"
    by_name = shell_css_by_name()
    assert len(by_name) == len(NEW_CSS), f"新 css 不全：{sorted(by_name)}"
    fail_if(dist_css_problems(pipeline.dist_css, by_name, other_src_css_texts()), "构建产物里的新 css")


def test_d01_module_exports_the_contract_names(pipeline):
    """D01：src/shellpages 的模块导出合同写出的名字——createShellStub、ThemisShellProvider、useThemisShell、resetShellStubs、parseShellWindow、
    ShellWindow、useShellWindowRoute、ThemePrefProvider、useThemePref、copyText。"""
    assert_probe_group(pipeline, "stub", "D01 模块导出的名字")


def test_d05_copy_text_returns_copied_failed_unavailable(pipeline):
    """D05：copyText(text, clipboard?) 返回 copied（writeText 成功）、failed（抛错或被拒）、unavailable（没有 writeText）；不传 clipboard 时点击当下才读 navigator.clipboard。"""
    assert_probe_group(pipeline, "stub", "D05 copyText 返回 copied、failed、unavailable")


def test_d02_stub_methods_deep_copy_no_timers(pipeline):
    """D02：十个成员加 dispose；同一场景同一实例；创建与读取不排计时器；各方法返回已兑现或已被拒的 Promise（假计时器下不推进时间）；getState 深拷贝。"""
    assert_probe_group(pipeline, "stub", "D02 桩的方法、深拷贝与创建时不排计时器")


def test_d02_stub_save_settings_keys(pipeline):
    """D02：saveSettings 只认约定键与取值——{ pythonPath } 被拒、removeRepo 传路径被拒、移除当前仓库被拒、别的键与不存在的 id 被拒，状态不变；
    约定键保存成功并返回新状态。"""
    assert_probe_group(pipeline, "stub", "D02 桩的 saveSettings 只认约定键")


def test_d02_stub_start_events_dispose(pipeline):
    """D02：startService 不在列表里的 id 被拒、对同一仓库幂等；starting 在调用里同步发；只在 start、restart 之后排计时器；取消订阅之后不再收到事件；
    dispose 之后没有挂起计时器。"""
    assert_probe_group(pipeline, "stub", "D02 桩的启动、事件与 dispose")


def test_d02_stub_open_external_only_http_and_https(pipeline):
    """D02：openExternal 只认 http 与 https。"""
    assert_probe_group(pipeline, "stub", "D02 桩的 openExternal 只认 http 与 https")


def test_transitional_d02_stub_fixture_values(pipeline):
    """接真实外壳那一片（桩与夹具换成真实外壳）推翻。

    D02 / 合同“桩与夹具”：夹具取值——ready、first-launch、no-python 等场景的状态与 pick 队列；start 之后 1499ms 无 running、1500ms 发 running，
    pid 18244、startedAt 取 SHELL_STARTED_AT；checking 停在 starting，exit-1、exit-2、crash 的退出码。"""
    assert_probe_group(pipeline, "stub", "D02 过渡：桩夹具的取值")


def test_d03_service_window_routes_unchanged(pipeline):
    """D03：#/settings 仍是 Tab（aria-current=page）；#/nope 与前缀相近的地址（#/first-run-x 等）仍归总览；Ctrl+, 仍切到设置。"""
    assert_probe_group(pipeline, "route", "D03 服务窗口的路由照旧")


def test_transitional_d03_entry_addresses(pipeline):
    """接真实外壳那一片（进入地址与 shell= 开关）推翻。

    D03：parseShellWindow；#/first-run、#/service-status 整窗渲染——没有主导航、切换仓库钮与 data-tab，恰一个 h1，document.title 正确，Ctrl+1 地址不变；
    缺省场景与认不出的 shell= 取值。"""
    assert_probe_group(pipeline, "route", "D03 过渡：parseShellWindow 与进入地址")


def test_transitional_d03_hashchange_between_windows(pipeline):
    """接真实外壳那一片（进入地址）推翻。

    D03：在两种窗口之间手改地址后手动派发 HashChangeEvent（不靠假计时器推进 jsdom，F4）；同一地址连派两次页面不重挂。"""
    assert_probe_group(pipeline, "route", "D03 过渡：两种窗口之间手改地址")


def test_transitional_d03_navigate_shell_is_synchronous(pipeline):
    """接真实外壳那一片（进入地址与 shell= 开关）推翻。

    D03 / K21：navigateShell 在同一次调用里同步改状态与地址——[打开设置]、[进入] 点击返回时地址已是目标地址、页面已换，保留整个查询串、没有 shell 时补上当前场景，
    两边用同一个桩实例。"""
    assert_probe_group(pipeline, "route", "D03 过渡：navigateShell 同步改状态与地址并保留查询串")


def test_transitional_d04_first_run_states(pipeline):
    """接真实外壳那一片（场景开关与夹具）推翻。

    D04：首次启动的依次检查——逐个场景的四步状态、值文字、图标 aria-label 与置灰；自动启动恰一次；第 4 步值元素 aria-live=polite、页面里没有 role=status；
    恰四步（C3）。"""
    assert_probe_group(pipeline, "firstrun", "D04 过渡：首次启动的四步状态")


def test_transitional_d05_first_run_errors_and_actions(pipeline):
    """接真实外壳那一片（场景开关与夹具）推翻。

    D05：六种错误的文字与操作；被拒的 pick 多出的那一行；退出码 1 的 [切换到那个窗口] 禁用、点了不调任何桩函数（Q2）；自动启动恰一次、exited 时不自动重启；
    [进入] 的禁用条件与跳转；卸载时取消订阅。"""
    assert_probe_group(pipeline, "firstrun", "D05 过渡：首次启动的错误与操作")


def test_transitional_d05_copy_results(pipeline):
    """接真实外壳那一片（场景开关与夹具）推翻。

    D05：复制结果的三种文字——「这个环境没有剪贴板接口」「已复制」「复制失败」。"""
    assert_probe_group(pipeline, "firstrun", "D05 复制命令的三种结果")


def test_transitional_d06_service_status_content(pipeline):
    """接真实外壳那一片（场景开关与夹具）推翻。

    D06：退出码 1、2、3 逐个查（danger 图标、h1、data-exit-code、时刻、说明、两个按钮、document.title、不设 role=alert）；非 exited 时写「—」。"""
    assert_probe_group(pipeline, "service", "D06 过渡：服务状态页的内容")


def test_transitional_d06_service_status_restart_and_navigate(pipeline):
    """接真实外壳那一片（场景开关与夹具）推翻。

    D06：[重启服务] 调一次 restartService 并进入加载态；收到 running 才跳回 #/overview（保留查询串）；推送 exited 2 后退出码与说明都换掉；[打开设置] 跳设置。"""
    assert_probe_group(pipeline, "service", "D06 过渡：重启与跳转")


def test_transitional_d07_settings_structure(pipeline):
    """接真实外壳那一片（设置页数据取自桩）推翻。

    D07：设置页的结构——PageFrame 的 h1 与恰一个 data-page-state、data-page=settings、五个 section 与 h2；getState 被拒走通用出错块（C1：不再断言占位文字）。"""
    assert_probe_group(pipeline, "settings", "D07 过渡：设置页的结构与数据取自桩")


def test_transitional_d07_repos_group(pipeline):
    """接真实外壳那一片（设置页数据取自桩）推翻。

    D07：仓库组——表、当前仓库不能移除（禁用且有提示）、[从列表移除] 与 [添加仓库…] 调的函数与参数精确，只用返回值更新。"""
    assert_probe_group(pipeline, "settings", "D07 过渡：仓库组")


def test_transitional_d07_runtime_and_usage_groups(pipeline):
    """接真实外壳那一片（设置页数据取自桩）推翻。

    D07：运行环境与规划端用量——[更改…]、[恢复自动检测]（只在 custom/external 出现）、[选择目录…]、[移除] 调的函数与参数精确；加载态；不做乐观更新；
    保存被拒的 Banner；会话目录只读。"""
    assert_probe_group(pipeline, "settings", "D07 过渡：运行环境与规划端用量")


def test_transitional_d07_load_is_a_stable_reference(pipeline):
    """接真实外壳那一片（设置页数据取自桩）推翻。

    D07：load 是稳定引用——改密度、选目录、添加仓库之后 getState 只在挂载时调一次，点刷新再加一次，新数据换掉本地状态。"""
    assert_probe_group(pipeline, "settings", "D07 load 是稳定引用")


def test_transitional_d08_appearance_without_provider(pipeline):
    """接真实外壳那一片（设置页数据取自桩）推翻。

    D08：没有 Provider 时主题退回本地状态、不抛错；密度只按返回值变；主题保存被拒的 Banner；caption「紧凑：表格行高 32」。"""
    assert_probe_group(pipeline, "settings", "D08 外观（无 Provider 时退回本地状态）")


def test_transitional_d09_about_and_external_link(pipeline):
    """接真实外壳那一片（设置页数据取自桩）推翻。

    D09：版本；许可清单两项文字（不写字体文件名）；点 [项目主页] 后出现确认对话框、openExternal 0 次；取消、Esc、关闭钮后仍 0 次；[打开] 后恰 1 次；
    homepage 不是 http(s) 时没有 [项目主页] 按钮。"""
    assert_probe_group(pipeline, "settings", "D09 过渡：关于、许可清单与外部链接")


def test_transitional_d08_theme_sync_through_app(pipeline):
    """接真实外壳那一片（设置页数据取自桩）推翻。

    D08：主题经 App 与标题栏同步——在设置页选亮，标题栏触发钮变「主题：亮」、data-theme 为 light、saveSettings({ theme: 'light' }) 恰一次；在标题栏选跟随系统，
    设置页分段跟着变；去过 #/first-run 再回 #/settings 主题不变；localStorage/sessionStorage 为空。"""
    assert_probe_group(pipeline, "app", "D08 主题经 App 与标题栏同步")


def test_d10_runtime_isolation(pipeline):
    """D10：vi.mock 把 api 模块每个导出换成包着原函数的替身，再把 fetch/XMLHttpRequest/EventSource/WebSocket、sendBeacon、window.open 换成记录调用的替身——
    经 App 打开 #/first-run 与 #/service-status 的全部 11 个场景、点遍按钮（[进入]、[打开设置] 除外）、推进桩计时器，单独渲染 SettingsPage 点遍控件，
    api 替身与网络替身都是 0 次；经 App 打开 #/settings 时 api 只被 getMetaNow、getStatus 调用、没有 getMeta。"""
    assert_probe_group(pipeline, "isolation", "D10 外壳窗口运行时不读 api 也不连网")


def test_d13_worktree_unchanged_by_pipeline(pipeline):
    """D13（守卫）：流水线与探针前后 git status 相同；package.json、锁文件、index.html、vite.config.ts、tsconfig.json、tokens.css、fonts.css、base.css、
    main.tsx、App.tsx、App.css、api.ts、router.ts、routes.ts 的摘要不变；gate-probe/ 没有留下。"""
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
    """门禁自检：PROBE_ORDER 与 PROBE_SPECS 对得上；探针里不写 skip、only、todo；括号配对；describe 名不重复、不含单引号；
    每个 describe 分组都有一个 Python 用例核对它（反过来也一样）；每个 test_transitional_ 用例的 docstring 第一行写明推翻它的那一片。"""
    assert set(PROBE_ORDER) == set(PROBE_SPECS) and len(PROBE_ORDER) == 7
    assert js_bracket_problems("a(b[c{d}])") == [] and js_bracket_problems("a(b]") and js_bracket_problems("f('x)")
    assert js_bracket_problems("f('(' + \"]\" + `{`)") == []
    pairs_in_sources = set()
    for key in PROBE_ORDER:
        source = build_probe_source(key)
        assert not re.search(r"__[A-Z_]+__", source), f"探针 {key} 里还有没替换的占位符"
        assert re.search(r"^\s*it\(", source, re.M), key
        assert not re.search(r"\.(skip|only|todo)\b|\bxit\(|\bxdescribe\(", source), key
        assert js_bracket_problems(source) == [], f"探针 {key} 的括号：{js_bracket_problems(source)}"
        names = re.findall(r"^describe\('([^']*)'", source, re.M)
        assert names and len(names) == len(set(names)), f"探针 {key} 的 describe 名：{names}"
        assert names == list(probe_groups(source)), key
        assert all(count >= 1 for count in probe_groups(source).values()), key
        pairs_in_sources |= {(key, name) for name in names}
    own = Path(__file__).read_text(encoding="utf-8")
    pairs_in_tests = set(re.findall(r'assert_probe_group\(pipeline, "(\w+)", "([^"]+)"\)', own))
    assert pairs_in_sources == pairs_in_tests, (sorted(pairs_in_sources - pairs_in_tests), sorted(pairs_in_tests - pairs_in_sources))
    transitional = [n for n in dir(sys.modules[__name__]) if n.startswith("test_transitional_")]
    assert len(transitional) >= 10
    for name in transitional:
        doc = (getattr(sys.modules[__name__], name).__doc__ or "").strip().splitlines()[0]
        assert "推翻" in doc, f"{name} 的 docstring 第一行要写明哪一片推翻它：{doc!r}"


def test_gate_selfcheck_helpers():
    """门禁自检：CSS 解析、出处注释、令牌检查、关键尺寸检查、源码守卫放得过正确样本，拦得住改坏的。"""
    css = ".a { width: 22px; /* 首启画布 :306 */ }\n.b {\n  height: 40px;\n}\n.c { margin: 0 1px; }\n"
    assert len(px_literal_problems("x", css)) == 1 and ":3:" in px_literal_problems("x", css)[0]
    assert px_literal_problems("x", ".a { width: 22px; /* 出处 */ }") == []
    assert px_literal_problems("x", "/* 多行\n注释 */ .a { top: 0; left: 1px; }") == []
    assert css_has(".a { padding: 0 var(--tt-space-3) 0 140px; }", ("padding*",), "140px")
    assert not css_has(".a { margin: 140px; }", ("padding*",), "140px")
    assert css_has("@media (x) { .tt-logo__mark { fill: var(--tt-logo-mark); } }", ("fill",), "var(--tt-logo-mark)", r"tt-logo__mark")
    assert not css_has(".a { fill: var(--tt-logo-mark); }", ("fill",), "var(--tt-logo-mark)", r"tt-logo__mark")
    assert css_token_problems("x", ".a { color: var(--tt-text-1); }") == []
    assert css_token_problems("x", ".a { color: var(--tt-no-such-token); }")
    assert css_token_problems("x", ".a { --tt-text-1: red; }")
    assert css_token_problems("x", "[data-theme='light'] .a { color: var(--tt-text-1); }")
    assert token_only_problems("x", ".a { border-radius: var(--tt-radius-md); z-index: var(--tt-z-dialog); font: var(--tt-text-sm); }") == []
    assert token_only_problems("x", ".a { border-radius: 4px; }")
    assert role_and_interface_problems("x", "<div role=\"status\" />")
    assert role_and_interface_problems("x", "window.matchMedia('x')")
    assert role_and_interface_problems("x", "// role=\"status\" 只在注释里\nconst a = 1;") == []
    assert HEX_RE.search("color: #fff;") and not HEX_RE.search("#/first-run?shell=ready")
    assert COLOR_FUNC_RE.search("rgb (1,2,3)") and not COLOR_FUNC_RE.search("const colors = 1")


def good_css_by_name():
    return {
        "shell-window.css": (
            ".tt-app { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }\n"
            ".tt-shell-bar { height: 40px; /* 5.2 :350 */ padding: 0 140px 0 var(--tt-space-3); /* 5.2 :352 */ "
            "background: var(--tt-titlebar); border-bottom: 1px solid var(--tt-border); }\n"
            ".tt-shell-product { font: var(--tt-title-sm); }\n"
            ".tt-shell-main { flex: 1; overflow-y: auto; padding: var(--tt-space-8) var(--tt-space-4); }\n"
            ".tt-shell-card { margin: auto; }\n"
            ".tt-logo__mark { fill: var(--tt-logo-mark); }\n.tt-logo__tally { fill: var(--tt-logo-tally); }\n"),
        "first-run.css": (
            ".tt-fr { width: 560px; /* 首启画布 :295 */ }\n.tt-fr__no { width: 22px; height: 22px; /* :306 */ }\n"
            ".tt-fr__name { width: 72px; /* :307 */ }\n.tt-fr__icon { width: 18px; height: 18px; /* :306 */ }\n"
            ".tt-fr__err { padding-left: 34px; /* :314 */ }\n.tt-fr__logo { width: 56px; height: 64px; /* K17 */ }\n"
            ".tt-fr__ok { color: var(--tt-tone-success-fg); }\n.tt-fr__bad { color: var(--tt-danger-text); }\n"
            ".tt-fr__spin { color: var(--tt-tone-info-fg); }\n.tt-fr__wait { color: var(--tt-text-disabled); }\n"),
        "service-status.css": ".tt-ss { width: 440px; /* 断线画布 :363 */ }\n.tt-ss__icon { color: var(--tt-danger-text); }\n",
        "settings.css": (
            ".tt-st__label { width: 120px; /* 设置画布 :362 */ }\n.tt-st th { height: 32px; /* handoff :142 */ }\n"
            ".tt-st td { height: 40px; /* handoff :142 */ }\n.tt-st table { min-width: 640px; /* :336 */ }\n"
            ".tt-st__scroll { overflow-x: auto; }\n.tt-st { max-width: 920px; /* K16 */ }\n"
            ".tt-st__logo { width: 42px; height: 48px; /* K17 */ }\n"),
    }


def test_gate_selfcheck_css_dimension_checker():
    """门禁自检：合同 §3 的关键尺寸检查对正确样本通过，每删掉一项就报。"""
    good = good_css_by_name()
    assert css_dim_problems(good) == []
    for name, text in good.items():
        assert px_literal_problems(name, text) == [], name
        assert css_token_problems(name, text) == [], name
    for name, needle in (("shell-window.css", "140px"), ("shell-window.css", "100vh"), ("first-run.css", "560px"), ("first-run.css", "var(--tt-text-disabled)"),
                         ("first-run.css", "34px"), ("service-status.css", "440px"), ("settings.css", "920px"), ("settings.css", "640px"),
                         ("settings.css", "42px"), ("shell-window.css", "var(--tt-logo-tally)")):
        broken = dict(good)
        broken[name] = broken[name].replace(needle, "")
        assert css_dim_problems(broken), f"{name} 去掉 {needle} 应该报"


def test_gate_selfcheck_dist_css_checker():
    """门禁自检：构建产物检查——独有类名都在 dist css 里才通过；没被 import 的 css 会漏掉独有类名。"""
    css = good_css_by_name()
    dist = "\n".join(css.values())
    assert dist_css_problems(dist, css) == []
    dist_missing = "\n".join(v for k, v in css.items() if k != "first-run.css")
    problems = dist_css_problems(dist_missing, css)
    assert problems and "first-run.css" in problems[0]
    assert unique_css_classes(css["first-run.css"], [css["service-status.css"]])
    assert dist_css_problems(dist, {"a.css": ".x { color: red; }", "b.css": ".x { color: blue; }"})


def good_app_text():
    keep = list(BASELINE_APP_KEEP)
    header = ["// 根组件：应用框架。", "// 主题偏好只存内存。",
              "// #/first-run、#/service-status 由根上的外壳窗口整窗渲染，不挂服务窗口；主题偏好在根上，经 ThemePrefProvider 交给设置页。"]
    root = [
        "",
        "export default function App() {",
        "  const [theme, setTheme] = useState<ThemePref>('dark');",
        "  const { shellWindow, navigateShell } = useShellWindowRoute();",
        "  useEffect(() => { applyTheme(theme); }, [theme]);",
        "  return (",
        "    <ThemePrefProvider theme={theme} onThemeChange={setTheme}>",
        "      {shellWindow ? (",
        "        <ShellWindow route={shellWindow} navigate={navigateShell} />",
        "      ) : (",
        "        <ServiceApp theme={theme} setTheme={setTheme} />",
        "      )}",
        "    </ThemePrefProvider>",
        "  );",
        "}",
        "",
        "interface ServiceAppProps { theme: ThemePref; setTheme: (pref: ThemePref) => void; }",
        "function ServiceApp({ theme, setTheme }: ServiceAppProps) {",
    ]
    return "\n".join(header + keep[:14] + [APP_IMPORT_SHELL_WINDOW, APP_IMPORT_THEME_PREF] + root + keep[14:]) + "\n"


def test_gate_selfcheck_app_tsx_checker():
    """门禁自检：App.tsx 检查对合同 §2.3 写的正确样本通过；改了 :72、缺导入、根组件调 api、没改名 ServiceApp、新增行太多、写了陈列页原文都会报。"""
    text = good_app_text()
    assert app_tsx_problems(text) == []
    assert app_tsx_problems(text.replace("repoName={meta.repo_name} />", "repoName={meta.repo_name} theme={theme} />"))
    assert app_tsx_problems(text.replace(APP_IMPORT_THEME_PREF + "\n", ""))
    assert app_tsx_problems(text.replace("  const { shellWindow, navigateShell } = useShellWindowRoute();",
                                         "  const { shellWindow, navigateShell } = useShellWindowRoute();\n  const m = getMetaNow();"))
    assert app_tsx_problems(text.replace("function ServiceApp(", "function Inner("))
    assert app_tsx_problems(text.replace("        <ShellWindow route", "\n".join(f"        const x{i} = {i};" for i in range(40)) + "\n        <ShellWindow route"))
    assert app_tsx_problems(text.replace("  const meta = getMetaNow();", "  const meta = getMetaNow(); // 弹出轻提示"))
    assert app_tsx_problems(text.replace("  const offline =", "  // 缺一行\n  const offlineX ="))
    assert app_tsx_problems(text.replace("  const [theme, setTheme] = useState<ThemePref>('dark');", "  const [theme, setTheme] = useState<ThemePref>('light');"))
    assert app_tsx_problems(text.replace("#/first-run、#/service-status", "外壳窗口"))
    assert len(BASELINE_APP_KEEP) == 72, len(BASELINE_APP_KEEP)


def test_gate_selfcheck_interface_checker():
    """门禁自检：接口检查对十个成员、六个补丁键的正确样本通过；多一个成员、补丁里有路径键、缺 on 都会报。"""
    good = """
export type PickProblem = 'not-git' | 'no-agent' | 'python-unusable' | 'kit-unusable';
export type PickOutcome = { kind: 'cancelled' } | { kind: 'saved'; path: string; id?: string } | { kind: 'rejected'; problem: PickProblem; path: string };
export interface ShellState { currentRepoCheck: 'ok' | null; settings: { currentRepo: string | null; transcriptDirs: string[]; density: string; repos: { lastOpened: string | null }[] };
  app: { homepage: string }; service: { kind: 'idle' } | { kind: 'starting' } | { kind: 'running'; startedAt: string } | { kind: 'exited'; exitCode: number } }
export interface SettingsPatch {
  theme?: 'system' | 'light' | 'dark';
  density?: 'standard' | 'compact';
  removeRepo?: string;
  removeTranscriptDir?: string;
  resetPython?: true;
  resetKit?: true;
}
export interface ThemisShell {
  getState(): Promise<ShellState>;
  pickRepo(): Promise<PickOutcome>;
  pickPython(): Promise<PickOutcome>;
  pickKit(): Promise<PickOutcome>;
  pickTranscriptDir(): Promise<PickOutcome>;
  saveSettings(patch: SettingsPatch): Promise<ShellState>;
  startService(repo: string): Promise<void>;
  restartService(): Promise<void>;
  openExternal(url: string): Promise<void>;
  on(event: 'service-state', listener: (state: ShellState['service']) => void): () => void;
}
"""
    assert interface_problems(good) == []
    assert interface_problems(good.replace("  openExternal(url: string): Promise<void>;\n", "  openExternal(url: string): Promise<void>;\n  focusWindow(id: string): Promise<void>;\n"))
    assert interface_problems(good.replace("  resetKit?: true;\n", "  resetKit?: true;\n  pythonPath?: string;\n"))
    assert interface_problems(good.replace("  resetKit?: true;\n", ""))
    assert interface_problems(good.replace("  on(event: 'service-state', listener: (state: ShellState['service']) => void): () => void;\n", ""))
    assert top_level_members("a(): void;\n b: (x: number) => void;\n c<T>(): T;") == ["a", "b", "c"]


def test_gate_selfcheck_source_guards(tmp_path):
    """门禁自检：api 导入、存储与 window.open、内联 style、W4 的坑、单词扫描对正确样本通过、对改坏的样本报。"""
    good = tmp_path / "Good.tsx"
    good.write_text("import { useState } from 'react';\nimport type { ThemisShell } from './themisShell';\nexport const a = 1; // 注释里的 localStorage 不算\n",
                    encoding="utf-8")
    assert api_import_problems([good]) == []
    assert forbidden_api_problems([good]) == []
    assert inline_style_problems([good]) == []
    assert w4_pitfall_problems([good]) == []
    assert word_problems([good], NET_WORDS, whole=True) == []
    bad = tmp_path / "Bad.tsx"
    cases = [
        ("import { getMeta } from '../api';", api_import_problems),
        ("import type { Envelope } from '../api.ts';", api_import_problems),
        ("localStorage.setItem('a', 'b');", forbidden_api_problems),
        ("window.open('x');", forbidden_api_problems),
        ("const t = window.themisShell;", forbidden_api_problems),
        ("declare global { interface Window { themisShell: any } }", forbidden_api_problems),
        ("import { ServerIcon } from './icons';", forbidden_api_problems),
        ("<div style={{ width: 1 }} />", inline_style_problems),
        ("const c = '#aabbcc';", w4_pitfall_problems),
        ("const c = 'rgb(1,2,3)';", w4_pitfall_problems),
    ]
    for line, checker in cases:
        bad.write_text(line + "\n", encoding="utf-8")
        assert checker([bad]), line
    bad.write_text("// 说明里提到 fetch\n", encoding="utf-8")
    assert word_problems([bad], NET_WORDS, whole=True), "注释里的 fetch 也算"
    bad.write_text("const prefetchAll = 1; const fetched = 2;\n", encoding="utf-8")
    assert word_problems([bad], NET_WORDS, whole=True) == []
    assert word_problems([bad], FORBIDDEN_WORDS) == []
    bad.write_text("el.innerHTML = 'x';\n", encoding="utf-8")
    assert word_problems([bad], FORBIDDEN_WORDS)


def make_tree(root, drop_css_import=False):
    files = {
        "src/App.tsx": ("import { ShellWindow, useShellWindowRoute } from './shellpages/ShellWindow';\n"
                        "import { ThemePrefProvider } from './shellpages/themePref';\n"
                        "export default function App() { return <ThemePrefProvider><ShellWindow /></ThemePrefProvider>; }\n"),
        "src/pages/SettingsPage.tsx": "import { SettingsView } from '../shellpages/SettingsView';\nexport default function P() { return <SettingsView />; }\n",
        "src/shellpages/ShellWindow.tsx": ("import './shell-window.css';\nimport { FirstRunView } from './FirstRunView';\n"
                                           "import { ServiceStatusView } from './ServiceStatusView';\n"
                                           "export function ShellWindow() { return <><FirstRunView /><ServiceStatusView /></>; }\n"),
        "src/shellpages/FirstRunView.tsx": ("" if drop_css_import else "import './first-run.css';\n") + "export const FirstRunView = () => null;\n",
        "src/shellpages/ServiceStatusView.tsx": "import './service-status.css';\nexport const ServiceStatusView = () => null;\n",
        "src/shellpages/SettingsView.tsx": "import './settings.css';\nimport { useThemePref } from './themePref';\nexport const SettingsView = () => null;\n",
        "src/shellpages/themePref.tsx": "export const ThemePrefProvider = (p: any) => p.children;\nexport const useThemePref = () => null;\n",
        "src/shellpages/shell-window.css": ".a{}\n",
        "src/shellpages/first-run.css": ".b{}\n",
        "src/shellpages/service-status.css": ".c{}\n",
        "src/shellpages/settings.css": ".d{}\n",
    }
    for name, text in files.items():
        path = Path(root) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return Path(root)


def test_gate_selfcheck_wiring_checker(tmp_path):
    """门禁自检：接线检查对完整的小树通过；某个视图丢了自己 css 的 import、css 没人 import、根上没渲染 ThemePrefProvider 都会报。"""
    good = make_tree(tmp_path / "good")
    assert wiring_problems(good) == []
    bad = make_tree(tmp_path / "bad", drop_css_import=True)
    problems = wiring_problems(bad)
    assert any("first-run.css" in p for p in problems), problems
    (bad / "src/shellpages/FirstRunView.tsx").write_text("import './first-run.css';\nexport const FirstRunView = () => null;\n", encoding="utf-8")
    assert wiring_problems(bad) == []
    (bad / "src/App.tsx").write_text("import { ShellWindow, useShellWindowRoute } from './shellpages/ShellWindow';\n"
                                     "import { ThemePrefProvider } from './shellpages/themePref';\n"
                                     "export default function App() { return <ShellWindow />; }\n", encoding="utf-8")
    assert wiring_problems(bad)
    unreach = make_tree(tmp_path / "unreach")
    (unreach / "src/shellpages/ShellWindow.tsx").write_text("import { FirstRunView } from './FirstRunView';\nimport './shell-window.css';\n"
                                                            "export function ShellWindow() { return <FirstRunView />; }\n", encoding="utf-8")
    assert any("ServiceStatusView" in p or "service-status.css" in p for p in wiring_problems(unreach))


def test_gate_selfcheck_vitest_summary():
    """门禁自检：Vitest JSON 的解析——按文件、按最外层 describe 分组统计；横幅行后面的 JSON 能取出来。"""
    data = {"numTotalTestSuites": 2, "testResults": [
        {"name": "C:/x/gate-probe/probe-t012-abc-stub.test.tsx", "status": "passed", "assertionResults": [
            {"ancestorTitles": ["D02 a"], "title": "t1", "status": "passed", "failureMessages": []},
            {"ancestorTitles": ["D02 a"], "title": "t2", "status": "failed", "failureMessages": ["boom"]},
            {"ancestorTitles": ["D02 b"], "title": "t3", "status": "passed", "failureMessages": []}]},
        {"name": "C:/x/gate-probe/probe-t012-abc-route.test.tsx", "status": "failed", "assertionResults": [], "message": "collect error"}]}
    files = summarize_vitest(data)
    groups, errors = files["probe-t012-abc-stub.test.tsx"]
    assert groups["D02 a"]["passed"] == 1 and groups["D02 a"]["bad"][0][0] == "t2" and groups["D02 b"]["passed"] == 1 and errors == []
    assert files["probe-t012-abc-route.test.tsx"][1] == ["collect error"]
    parsed = parse_vitest_json("> vitest run\n" + json.dumps(data))
    assert parsed and parsed["numTotalTestSuites"] == 2
    assert parse_vitest_json("no json here") is None
    assert probe_groups("describe('A 组', () => {\n  it('x', () => {});\n  it('y', () => {});\n});\ndescribe('B 组', () => {\n  it('z', () => {});\n});") == {"A 组": 2, "B 组": 1}


def test_gate_selfcheck_canvas_icons_and_icon_checker():
    """门禁自检：画布上能解析出 ArrowRight（首启 :358）、FileText（设置 :427）、ExternalLink（设置 :428）的 path；图标检查对正确样本通过、对改坏的报。"""
    wants = canvas_icon_paths()
    assert wants["ArrowRightIcon"] == ["M5 12h14", "m12 5 7 7-7 7"]
    assert len(wants["FileTextIcon"]) == 5 and len(wants["ExternalLinkIcon"]) == 3
    sample = "const Svg = (p) => <svg className=\"tt-i\" stroke=\"currentColor\" aria-hidden=\"true\" />;\n"
    for name, ds in wants.items():
        sample += f"export const {name} = (props: IconProps) => (\n  <Svg {{...props}}>\n" + "".join(f"    <path d=\"{d}\" />\n" for d in ds) + "  </Svg>\n);\n"
    assert icon_problems(sample, wants) == []
    assert icon_problems(sample.replace("M5 12h14", "M5 12h13"), wants)
    assert icon_problems(sample.replace("export const FileTextIcon", "export const FileText2Icon"), wants)
    assert icon_problems(sample.replace("currentColor", "red"), wants)


def test_gate_selfcheck_executor_test_checker(tmp_path, monkeypatch):
    """门禁自检：执行端测试检查对全部在位、无 skip 的样本通过；缺文件、没有用例、写了 skip / only / todo 都会报。"""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    for name in EXECUTOR_TESTS:
        (tests_dir / name).write_text("it('x', () => {});\n", encoding="utf-8")
    monkeypatch.setitem(globals(), "WEB", tmp_path)
    assert executor_test_problems() == []
    first = tests_dir / EXECUTOR_TESTS[0]
    for bad in ("it.skip('x', () => {});\n", "describe('x', () => { it.only('y', () => {}); });\n", "it.todo('x');\n", "// 没有用例\n"):
        first.write_text(bad, encoding="utf-8")
        assert executor_test_problems(), bad
    first.unlink()
    assert executor_test_problems()


GOOD_ROUTE_TS = """
export function parseShellWindow(hash: string) { return null; }
"""
GOOD_WINDOW_TSX = """
import { useCallback, useEffect, useState } from 'react';
import './shell-window.css';
export function useShellWindowRoute() {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  const navigateShell = useCallback((path: string) => {
    const next = '#' + path;
    setHash(next);
    window.location.hash = next;
  }, []);
  return { shellWindow: null, navigateShell };
}
export function ShellWindow() { return null; }
"""
GOOD_PAGE_TSX = """
import { useCallback } from 'react';
import { PageFrame, type PageFrameProps } from '../shell/PageFrame';
import { SettingsView } from '../shellpages/SettingsView';
export default function SettingsPage() {
  const shell = useThemisShell('settings');
  const load = useCallback(() => shell.getState().then((data) => ({ ok: true, exit_code: 0, data, output: '', messages: [], command: ['themisShell.getState'], elapsed_ms: 0 })), [shell]);
  return <PageFrame title="设置" description="设置保存在桌面应用自己的用户数据目录里，不写进仓库的配置" load={load}>{(d) => <SettingsView data={d} />}</PageFrame>;
}
"""
GOOD_VIEW_TSX = """
export function SettingsView() {
  return <div data-page="settings"><section data-settings-group="repos" data-repo-id="x"><h2>仓库</h2></section>
  <section data-settings-group="runtime" /><section data-settings-group="usage" /><section data-settings-group="appearance" /><section data-settings-group="about" /></div>;
}
"""


def test_gate_selfcheck_route_and_settings_source_checkers():
    """门禁自检：地址钩子与设置页的源码检查对正确样本通过，对 setState 更新函数里写地址、缺导出、load 内联、用 await、View 渲染 h1 都会报。"""
    assert route_source_problems(GOOD_ROUTE_TS, GOOD_WINDOW_TSX) == []
    bad_update = GOOD_WINDOW_TSX.replace("    setHash(next);\n    window.location.hash = next;",
                                         "    setHash((prev) => { window.location.hash = next; return next; });")
    assert any("更新函数" in p for p in route_source_problems(GOOD_ROUTE_TS, bad_update))
    assert route_source_problems(GOOD_ROUTE_TS.replace("parseShellWindow", "parseIt"), GOOD_WINDOW_TSX)
    assert route_source_problems(GOOD_ROUTE_TS, GOOD_WINDOW_TSX.replace("export function useShellWindowRoute", "function useShellWindowRoute"))
    assert route_source_problems(GOOD_ROUTE_TS, GOOD_WINDOW_TSX.replace("hashchange", "popstate"))
    assert settings_source_problems(GOOD_PAGE_TSX, GOOD_VIEW_TSX) == []
    assert settings_source_problems(GOOD_PAGE_TSX.replace("useCallback(", "useMemo("), GOOD_VIEW_TSX)
    assert settings_source_problems(GOOD_PAGE_TSX.replace("[shell])", "[])"), GOOD_VIEW_TSX)
    assert settings_source_problems(GOOD_PAGE_TSX.replace("const load = useCallback(() =>", "const load = useCallback(async () => await"), GOOD_VIEW_TSX)
    assert settings_source_problems(GOOD_PAGE_TSX.replace("load={load}", "load={load} isEmpty={() => false}"), GOOD_VIEW_TSX)
    assert settings_source_problems(GOOD_PAGE_TSX, GOOD_VIEW_TSX.replace("<h2>", "<h1>").replace("</h2>", "</h1>"))
    assert settings_source_problems(GOOD_PAGE_TSX, GOOD_VIEW_TSX.replace('data-page="settings"', ""))
    assert settings_source_problems(GOOD_PAGE_TSX.replace("themisShell.getState", "x"), GOOD_VIEW_TSX)


def test_gate_selfcheck_constants():
    """门禁自检：常量本身——基线 App.tsx 里保留的行含 :72 的 TitleBar 一行（缩进 8 格）；文件清单、场景名、接口成员与补丁键的个数。"""
    assert ("        " + TITLEBAR_LINE) in BASELINE_APP_KEEP
    assert len(NEW_SOURCE_FILES) == 22 and len(NEW_CSS) == 4 and len(EXECUTOR_TESTS) == 8
    assert len(SCENARIOS) == 11 and len(INTERFACE_MEMBERS) == 10 and len(PATCH_KEYS) == 6
