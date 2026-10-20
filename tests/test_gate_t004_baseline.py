"""T004 战前门禁：桌面端前端浮层与焦点（第三片）的黑盒基准测试（合同 t004-desktop-overlays，plan_version 3）。

被测对象是 ``desktop/web/``：6 个浮层组件（图标按钮、工具提示、菜单、对话框、抽屉、轻提示）与内部 ``overlay/``、两处状态补丁
（``ACCEPTED_WITH_EXCEPTION`` 的 warning 圆点、``INFRA_FAILURE`` 的图标改名 ``ServerCrashIcon``）、陈列页页尾的 5 节演示，
以及仓库根的 W5 测试 ``tests/test_desktop_attempt_states.py``。
基线（T003 结项）上这些都还没有，所以本文件的“失败”断言落在目标文件不存在或内容不符上，不是导入、收集或语法错误：
模块级只导入标准库，用到被测文件的地方都在用例函数里读；组件探针只在它要用的文件都在时才写出和运行。

结构（编号对应合同第 12 条的 S1–S7、P1–P8；门禁端多加了 P9 和若干自检）：

- 静态断言（S 系列，不用流水线，全量 pytest 也跑）：读组件 CSS、``components/index.ts``、``icons/index.tsx``、
  ``attemptStates.ts``、令牌板；S7 在子进程里跑 W5 测试，并在 ``tmp_path`` 里搭最小副本验证改动能被抓住。
- 流水线断言（P 系列）：会话级夹具 ``pipeline`` 在 ``desktop/web`` 下按顺序跑 ``npm ci``、``npm run build``、
  ``npm test``、``npm run check:contract``，再把探针逐份写成 ``gate-probe/probe-<唯一标识>-<编号>.test.tsx``，
  各用 ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除；前后各取一次 ``git status``。
  现在只有组件探针（P2–P7）；原来分开写、分开跑的陈列页探针（P8）随 P8 一起退役了（见下面的“过渡断言”）。
  全量 pytest 默认跳过用到它的用例（``tests/conftest.py``），点名运行本文件时才跑。
- 门禁自检（``test_gate_selfcheck_*``，不依赖候选）：把各检查函数喂给正确样本和若干改坏的样本，证明门禁自己
  放得过正确实现、拦得住常见错误。

DoD 对应：

- D01：S1、S6、P2；D02：S1、S6、P3；D03：S1、S3、S6、P4；D04：S1、S4、P5；D05：S1、S5、P6；
- D06：S7（V03 与战后变异另证）；D07：S2、S6、P7；D08：原来是 P8（过渡），已退役，本文件不再覆盖（见下一段）；
- D09：P1（V02 另证 T001–T003 门禁）；D10：P9 守卫 package.json、锁文件、令牌、base.css 不变
  （改动范围由调度器的范围门禁证明，这里不写相对基线的改动范围断言）；
- D11：新增测试不用 skip、only、todo 由 V02 里 T002 的 ``test_d03_new_tests_not_skipped`` 机械检查，
  其余（既有测试不改）由终审读差异。

过渡断言（``test_transitional_`` 开头）：原来只有 P8（``test_transitional_d08_showcase_overlay_demos``，探针渲染根 ``App``
核对陈列页页尾的 5 节浮层演示），只在陈列页是根 ``App`` 时成立，站主在登记 T006（应用框架与夹具数据层）之前退役了，
连同它的探针 ``PROBE_P8`` 与 ``PROBE_SPECS`` 里的 ``p8``。T006 把根 ``App`` 改成应用框架、把陈列页移出根路由，
这条在根 ``App`` 上不再成立；5 节演示在新位置上的覆盖由 T006 自己的门禁重新负责。
其余（组件行为、CSS 几何与层级、两处补丁、W5）都是长期断言，照旧保留。

写法约定：CSS 比较先归一空白（``calc(…)`` 里的也一样）；jsdom 不排版，宽、位置、层级读 CSS 文件的文本，探针只看结构、
焦点、计时与属性；悬停与聚焦的探针从 ``@testing-library/react`` 导入 ``fireEvent``（它给 React 打了补丁）；
不写 skip、xfail、only、todo。

门禁做不到、留给人的项（合同 H1–H6）：
H1 视觉（图标按钮各态、工具提示位置与配色、菜单、对话框、抽屉、轻提示、圆点位置与描边，暗色亮色各一次）；
H2 真浏览器键盘（StrictMode 的 dev 服务器与 vite preview）；H3 读屏抽查；H4 减少动态效果；
H5 1024 × 640 与缩放 80%–200%；H6 Windows 高对比度。
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
COMP_REL = f"{SRC_REL}/components"
CANVAS = REPO_ROOT / "docs" / "ui-design" / "pages" / "01-设计令牌-Themis-Tally.html"
W5_REL = "tests/test_desktop_attempt_states.py"

NEW_COMPONENTS = ("IconButton", "Tooltip", "Menu", "Dialog", "Drawer", "Toast")
OLD_COMPONENTS = ("Button", "Tag", "StatusTag", "Card", "Banner")

# 夹具总预算留出余量给其余快测试（合同检查项 V01 的 timeout 是 2400s）。
PIPELINE_BUDGET = 2100
STEP_CAPS = {
    "npm ci": 1200,
    "npm run build": 600,
    "npm test": 600,
    "npm run check:contract": 120,
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


# ---------------------------------------------------------------------------
# CSS 小解析器：规则、声明、按类名取声明
# ---------------------------------------------------------------------------

def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def split_decls(body):
    """把声明块按分号切开（引号和括号里的分号不算），返回 [(小写名, 值)]，保持源码顺序。"""
    parts, buf, depth, quote = [], [], 0, None
    for ch in body:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf))
    decls = []
    for part in parts:
        part = part.strip()
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


def selector_has_class(selector, cls):
    """选择器列表里有一项的最后一个复合选择器带 .cls 且没有伪类（.a > .cls、.cls.other 都算）。"""
    for part in selector.split(","):
        compound = re.split(r"[\s>+~]+", part.strip())[-1]
        if ":" in compound:
            continue
        if cls in re.findall(r"\.([\w-]+)", compound):
            return True
    return False


def class_decls(css, cls):
    """所有带 .cls 的规则的声明，按源码顺序拼起来。"""
    out = []
    for selector, decls in parse_rules(css):
        if selector_has_class(selector, cls):
            out.extend(decls)
    return out


def cv(value):
    """归一值：去 !important，所有空白去掉（calc(…) 里的也一样）。"""
    return re.sub(r"\s+", "", re.sub(r"!important", "", value or "", flags=re.I))


def last_value(decls, *names):
    got = None
    for name, value in decls:
        if name in names:
            got = cv(value)
    return got


def is_zero(value):
    return value in ("0", "0px", "0%")


def resolved_edges(decls):
    """按源码顺序展开 inset 简写与 top/right/bottom/left，返回 {边: 归一值}。"""
    edges = {}
    for name, value in decls:
        if name == "inset":
            vals = [cv(v) for v in value.replace("!important", "").split()]
            if not vals or len(vals) > 4:
                continue
            top = vals[0]
            right = vals[1] if len(vals) > 1 else top
            bottom = vals[2] if len(vals) > 2 else top
            left = vals[3] if len(vals) > 3 else right
            edges.update({"top": top, "right": right, "bottom": bottom, "left": left})
        elif name in ("top", "right", "bottom", "left"):
            edges[name] = cv(value)
    return edges


def edge_problems(decls, label, want):
    """want: {边: '0' 或 令牌表达式}；'0' 表示 0 / 0px。"""
    problems = []
    edges = resolved_edges(decls)
    for side, expected in want.items():
        got = edges.get(side)
        ok = is_zero(got) if expected == "0" else got == cv(expected)
        if not ok:
            problems.append(f"{label}：{side} 应为 {expected}，实际 {got!r}")
    return problems


def decl_problem(decls, label, names, expected, desc=None):
    got = last_value(decls, *names)
    if got != cv(expected):
        return [f"{label}：{desc or '/'.join(names)} 应为 {expected}，实际 {got!r}"]
    return []


def has_rule_declaring(css, name_options, expected):
    for _selector, decls in parse_rules(css):
        if last_value(decls, *name_options) == cv(expected):
            return True
    return False


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
    for comp in NEW_COMPONENTS + OLD_COMPONENTS:
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


def canvas_icon_ds(key):
    """令牌板状态标签那一节里 ``s.ic.<key>`` 的 path d 列表（svg 内，不含圆点的 span）。"""
    html = _read(CANVAS)
    m = re.search(r'<sc-if value="\{\{ s\.ic\.' + re.escape(key) + r' \}\}"[^>]*>(.*?)</sc-if>', html, re.S)
    assert m, f"令牌板里找不到 s.ic.{key} 那一块"
    svg = re.search(r"<svg\b.*?</svg>", m.group(1), re.S)
    assert svg, f"令牌板 s.ic.{key} 里没有 svg"
    return re.findall(r'\bd="([^"]*)"', svg.group(0))


def infra_failure_problems(icons_text, states_text, src_texts):
    problems = []
    if icon_component_ds(icons_text, "ServerCrashIcon") is None:
        problems.append("icons/index.tsx 没有 export const ServerCrashIcon")
    else:
        got = icon_component_ds(icons_text, "ServerCrashIcon")
        want = canvas_icon_ds("server")
        if got != want:
            problems.append(f"ServerCrashIcon 的 path d 应等于令牌板 :342 s.ic.server（含 m13 6-4 6h6l-4 6），实际 {got}，期望 {want}")
    for rel, text in src_texts.items():
        if re.search(r"\bServerIcon\b", strip_ts_comments(text)):
            problems.append(f"{rel}：还有 ServerIcon（应改名为 ServerCrashIcon，不留别名）")
    entry = re.search(r"INFRA_FAILURE\s*:\s*\{[^{}]*\}", states_text)
    if not entry:
        problems.append("attemptStates.ts 里找不到 INFRA_FAILURE 的条目")
    elif not re.search(r"\bicon\s*:\s*ServerCrashIcon\b", entry.group(0)):
        problems.append(f"INFRA_FAILURE 的 icon 应是 ServerCrashIcon：{entry.group(0)[:120]!r}")
    imports = re.findall(r"import\s*\{([^}]*)\}\s*from\s*['\"][^'\"]*icons[^'\"]*['\"]", states_text)
    if not any(re.search(r"\bServerCrashIcon\b", block) for block in imports):
        problems.append("attemptStates.ts 没有从 icons 导入 ServerCrashIcon")
    return problems


def dialog_css_problems(css):
    problems = []
    dialog = class_decls(css, "tt-dialog")
    scrim = class_decls(css, "tt-dialog-scrim")
    if not dialog:
        problems.append("Dialog.css 里没有 .tt-dialog 的规则")
    else:
        problems += decl_problem(dialog, ".tt-dialog", ("width",), "560px")
        problems += decl_problem(dialog, ".tt-dialog", ("max-width",), "100%")
        problems += decl_problem(dialog, ".tt-dialog", ("border-radius",), "var(--tt-radius-xl)")
        problems += decl_problem(dialog, ".tt-dialog", ("box-shadow",), "var(--tt-shadow-3)")
    if not scrim:
        problems.append("Dialog.css 里没有 .tt-dialog-scrim 的规则")
    else:
        problems += decl_problem(scrim, ".tt-dialog-scrim", ("position",), "fixed")
        problems += edge_problems(scrim, ".tt-dialog-scrim", {"top": "0", "right": "0", "bottom": "0", "left": "0"})
        problems += decl_problem(scrim, ".tt-dialog-scrim", ("z-index",), "var(--tt-z-dialog)")
        problems += decl_problem(scrim, ".tt-dialog-scrim", ("background", "background-color"), "var(--tt-scrim)", "background")
    return problems


def drawer_css_problems(css):
    problems = []
    drawer = class_decls(css, "tt-drawer")
    if not drawer:
        return ["Drawer.css 里没有 .tt-drawer 的规则"]
    problems += decl_problem(drawer, ".tt-drawer", ("position",), "fixed")
    problems += edge_problems(drawer, ".tt-drawer", {"right": "0", "bottom": "var(--tt-tabbar-height)"})
    problems += decl_problem(drawer, ".tt-drawer", ("width",), "520px")
    problems += decl_problem(drawer, ".tt-drawer", ("max-width",), "60%")
    problems += decl_problem(drawer, ".tt-drawer", ("z-index",), "var(--tt-z-drawer)")
    return problems


def toast_css_problems(css):
    """Toast.css 里没有写死类名：找固定定位的规则，其中一条要同时满足右、下、层级。"""
    fixed = [decls for _sel, decls in parse_rules(css) if last_value(decls, "position") == "fixed"]
    if not fixed:
        return ["Toast.css 里没有 position: fixed 的规则"]
    first = None
    for decls in fixed:
        problems = edge_problems(decls, "轻提示", {"right": "var(--tt-space-6)",
                                                   "bottom": "calc(var(--tt-tabbar-height) + var(--tt-space-4))"})
        problems += decl_problem(decls, "轻提示", ("z-index",), "var(--tt-z-toast)")
        if not problems:
            return []
        first = first or problems
    return first


def layer_and_dot_problems(tooltip_css, menu_css, status_css):
    problems = []
    dot = class_decls(status_css, "tt-status__dot")
    if not dot:
        problems.append("StatusTag.css 里没有 .tt-status__dot 的规则")
    else:
        problems += decl_problem(dot, ".tt-status__dot", ("background", "background-color"), "var(--tt-tone-warning-fg)", "background")
        ring = [cv(v) for n, v in dot if n in ("box-shadow", "border", "outline")]
        if not any("var(--tt-tone-success-bg)" in v for v in ring):
            problems.append(".tt-status__dot 的描边（box-shadow 或 border）应取 var(--tt-tone-success-bg)")
        radius = last_value(dot, "border-radius")
        if radius not in ("var(--tt-radius-full)", "50%"):
            problems.append(f".tt-status__dot 的 border-radius 应为 var(--tt-radius-full) 或 50%，实际 {radius!r}")
    for what, css, name_options, expected in (
        ("工具提示底色", tooltip_css, ("background", "background-color"), "var(--tt-gray-900)"),
        ("工具提示字色", tooltip_css, ("color",), "var(--tt-gray-50)"),
        ("工具提示层级", tooltip_css, ("z-index",), "var(--tt-z-tooltip)"),
        ("菜单层级", menu_css, ("z-index",), "var(--tt-z-popover)"),
    ):
        if not has_rule_declaring(css, name_options, expected):
            problems.append(f"{what}：没有规则声明 {'/'.join(name_options)}: {expected}")
    return problems


# ---------------------------------------------------------------------------
# W5（tests/test_desktop_attempt_states.py）：原样通过，改动被抓住
# ---------------------------------------------------------------------------

PD_STATES_LINE = (
    '    "INFRA_FAILURE", "TIMEOUT", "CANCELLED", "INTEGRATED", "ABANDONED", "SUPERSEDED")\n'
)
PD_STATES_DROP = PD_STATES_LINE.replace(', "SUPERSEDED")', ")")
PD_STATES_ADD = PD_STATES_LINE.replace('"SUPERSEDED")', '"SUPERSEDED", "GATE_FAKE_STATE")')


def mutate_pd_drop(text):
    assert PD_STATES_LINE in text, "scripts/pi_dispatch.py 里 ATTEMPT_STATES 的末行与门禁预期不同，门禁需要更新"
    return text.replace(PD_STATES_LINE, PD_STATES_DROP, 1)


def mutate_pd_add(text):
    assert PD_STATES_LINE in text, "scripts/pi_dispatch.py 里 ATTEMPT_STATES 的末行与门禁预期不同，门禁需要更新"
    return text.replace(PD_STATES_LINE, PD_STATES_ADD, 1)


def mutate_ts_drop(text):
    for code in ("SUPERSEDED", "ABANDONED", "CANCELLED", "TIMEOUT"):
        pattern = re.compile(rf"^[ \t]*{code}\s*:\s*\{{[^{{}}]*\}},?[ \t]*\n", re.M)
        if pattern.search(text):
            return pattern.sub("", text, count=1)
    raise AssertionError("attemptStates.ts 里找不到可删除的单个状态条目，门禁需要更新")


def mutate_ts_add(text):
    pattern = re.compile(r"(export\s+const\s+ATTEMPT_STATES[^=]*=\s*\{)")
    assert pattern.search(text), "attemptStates.ts 里找不到 ATTEMPT_STATES 的声明"
    return pattern.sub(r"\1\n  GATE_FAKE_STATE: { label: '假', tone: 'neutral', icon: LayersIcon },", text, count=1)


def run_w5(root, timeout=240):
    """在 root 下跑 W5 测试；返回 (退出码, 输出)。"""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTEST_ADDOPTS", None)
    proc = subprocess.run([sys.executable, "-m", "pytest", W5_REL, "-q", "-p", "no:cacheprovider"],
                          cwd=root, env=env, capture_output=True, timeout=timeout)
    out = (proc.stdout + proc.stderr).decode("utf-8", "replace")
    return proc.returncode, out


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
           "src/styles/tokens.css", "src/styles/base.css", "src/main.tsx")


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
function tooltipEl(): HTMLElement | null {
  return document.querySelector('[role="tooltip"]');
}
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
function focusables(root: Element): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => !el.hasAttribute('hidden'));
}
function escapeCalls(spy: any): number {
  return spy.mock.calls.filter((c: any[]) => c[0] && c[0].key === 'Escape').length;
}
function inMountLayer(el: Element, container: Element) {
  expect(container.contains(el), '浮层应挂到 body 下，不在渲染容器里').toBe(false);
  expect(document.body.contains(el)).toBe(true);
  const layer = el.closest('.tt-app') as HTMLElement | null;
  expect(layer, '浮层外应包一层带 tt-app 类的挂载层').not.toBeNull();
  expect(layer!.parentElement, '挂载层应是 body 的直接子元素').toBe(document.body);
  expect(el.classList.contains('tt-app'), '浮层根本身不能带 tt-app（底色会被盖成 --tt-bg）').toBe(false);
}
"""

PROBE_P2 = PRELUDE + r"""
let IconButton: any;
let Tooltip: any;
let XIcon: any;

beforeAll(async () => {
  IconButton = (await import('../src/components/IconButton')).IconButton;
  Tooltip = (await import('../src/components/Tooltip')).Tooltip;
  XIcon = (await import('../src/icons')).XIcon;
});

function mountIcon(props: any = {}, outerKey?: any) {
  const ui = <IconButton label="关闭" icon={<XIcon />} {...props} />;
  const r = render(outerKey ? <div onKeyDown={outerKey}>{ui}</div> : ui);
  const button = r.container.querySelector('button') as HTMLButtonElement;
  return { ...r, button };
}

describe('图标按钮与工具提示', () => {
  it('aria-label 等于 label，图标 aria-hidden，按钮里没有文字', () => {
    const { button } = mountIcon();
    expect(button.getAttribute('aria-label')).toBe('关闭');
    expect(button.getAttribute('type')).toBe('button');
    const svg = button.querySelector('svg');
    expect(svg, '按钮里应有 svg 图标').not.toBeNull();
    expect(svg!.getAttribute('aria-hidden')).toBe('true');
    expect((button.textContent || '').trim()).toBe('');
  });

  it('悬停 399ms 没有提示，400ms 出现，aria-describedby 指向它，移开立即消失', () => {
    const { button } = mountIcon();
    expect(tooltipEl()).toBeNull();
    fireEvent.mouseEnter(button);
    advance(399);
    expect(tooltipEl(), '399ms 时还不该出现').toBeNull();
    advance(1);
    const tip = tooltipEl();
    expect(tip, '400ms 时应出现 role=tooltip').not.toBeNull();
    expect((tip!.textContent || '').trim()).toBe('关闭');
    expect(tip!.id).not.toBe('');
    expect(button.getAttribute('aria-describedby')).toBe(tip!.id);
    fireEvent.mouseLeave(button);
    expect(tooltipEl(), '移开应立即消失').toBeNull();
    expect(button.hasAttribute('aria-describedby'), '消失后触发元素不再带 aria-describedby').toBe(false);
  });

  it('计时中移开会取消计时', () => {
    const { button } = mountIcon();
    fireEvent.mouseEnter(button);
    advance(300);
    fireEvent.mouseLeave(button);
    advance(500);
    expect(tooltipEl()).toBeNull();
  });

  it('聚焦同样 400ms 出现（399ms 没有），失焦立即消失', () => {
    const { button } = mountIcon();
    fireEvent.focus(button);
    advance(399);
    expect(tooltipEl(), '聚焦 399ms 时还不该出现').toBeNull();
    advance(1);
    const tip = tooltipEl();
    expect(tip, '聚焦 400ms 时应出现').not.toBeNull();
    expect(button.getAttribute('aria-describedby')).toBe(tip!.id);
    fireEvent.blur(button);
    expect(tooltipEl(), '失焦应立即消失').toBeNull();
    expect(button.hasAttribute('aria-describedby')).toBe(false);
  });

  it('只悬停时按 Esc：提示消失，之后不再出现，重新悬停才再出现', () => {
    const { button } = mountIcon();
    fireEvent.mouseEnter(button);
    advance(400);
    expect(tooltipEl()).not.toBeNull();
    fireEvent.keyDown(document.body, { key: 'Escape' });
    expect(tooltipEl(), 'Esc 后应消失').toBeNull();
    advance(1000);
    expect(tooltipEl(), '重新悬停之前不再出现').toBeNull();
    fireEvent.mouseLeave(button);
    fireEvent.mouseEnter(button);
    advance(400);
    expect(tooltipEl(), '重新悬停后应再次出现').not.toBeNull();
  });

  it('聚焦时按 Esc：提示消失且被消费，之后不再出现，重新聚焦才再出现', () => {
    const outer = vi.fn();
    const { button } = mountIcon({}, outer);
    fireEvent.focus(button);
    advance(400);
    expect(tooltipEl()).not.toBeNull();
    fireEvent.keyDown(button, { key: 'Escape' });
    expect(tooltipEl(), 'Esc 后应消失').toBeNull();
    expect(escapeCalls(outer), '提示可见时 Esc 由提示消费，不再往外传').toBe(0);
    advance(1000);
    expect(tooltipEl(), '重新聚焦之前不再出现').toBeNull();
    fireEvent.blur(button);
    fireEvent.focus(button);
    advance(400);
    expect(tooltipEl(), '重新聚焦后应再次出现').not.toBeNull();
  });

  it('计时中按 Esc 取消，之后不再出现', () => {
    const { button } = mountIcon();
    fireEvent.focus(button);
    advance(200);
    fireEvent.keyDown(button, { key: 'Escape' });
    advance(1000);
    expect(tooltipEl()).toBeNull();
  });

  it('tooltip 属性与名称不同时，提示用 tooltip，aria-label 仍是 label', () => {
    const { button } = mountIcon({ label: '复制', tooltip: '复制（已复制会弹轻提示）' });
    expect(button.getAttribute('aria-label')).toBe('复制');
    fireEvent.mouseEnter(button);
    advance(400);
    expect((tooltipEl()!.textContent || '').trim()).toBe('复制（已复制会弹轻提示）');
  });

  it('提示挂在 body 下的挂载层里，外框带 tt-fc', () => {
    const { button, container } = mountIcon();
    fireEvent.mouseEnter(button);
    advance(400);
    const tip = tooltipEl() as HTMLElement;
    inMountLayer(tip, container);
    expect(tip.classList.contains('tt-fc'), '提示外框应带 tt-fc').toBe(true);
  });

  it('单独用 Tooltip：content 可以是节点，聚焦 400ms 出现，卸载后不再出现', () => {
    const r = render(
      <Tooltip content={<span>提示文字</span>}>
        <button type="button">目标</button>
      </Tooltip>,
    );
    const button = r.container.querySelector('button') as HTMLButtonElement;
    fireEvent.focus(button);
    advance(400);
    const tip = tooltipEl();
    expect(tip).not.toBeNull();
    expect((tip!.textContent || '').trim()).toBe('提示文字');
    expect(button.getAttribute('aria-describedby')).toBe(tip!.id);
    r.unmount();
    expect(tooltipEl(), '卸载后提示不在').toBeNull();
    const r2 = render(
      <Tooltip content="x">
        <button type="button">目标</button>
      </Tooltip>,
    );
    fireEvent.mouseEnter(r2.container.querySelector('button') as Element);
    advance(200);
    r2.unmount();
    advance(1000);
    expect(tooltipEl(), '卸载时计时器应清掉').toBeNull();
  });
});
"""

PROBE_P3 = PRELUDE + r"""
let Menu: any;

beforeAll(async () => {
  Menu = (await import('../src/components/Menu')).Menu;
});

const ITEMS = [
  { id: 'a', label: '甲' },
  { id: 'b', label: '乙' },
  { id: 'c', label: '丙' },
];

function menuEl(): HTMLElement | null {
  return document.querySelector('[role="menu"]');
}
function itemEls(): HTMLElement[] {
  const m = menuEl();
  return m ? Array.from(m.querySelectorAll<HTMLElement>('[role="menuitem"]')) : [];
}
function mountMenu() {
  const onSelect = vi.fn();
  const outer = vi.fn();
  const r = render(
    <div onKeyDown={outer}>
      <Menu label="更多操作" items={ITEMS} onSelect={onSelect} />
    </div>,
  );
  const trigger = r.container.querySelector('button[aria-haspopup="menu"]') as HTMLButtonElement;
  return { ...r, trigger, onSelect, outer };
}
function openMenu(trigger: HTMLElement) {
  focusOn(trigger);
  fireEvent.click(trigger);
}

describe('菜单', () => {
  it('触发按钮：aria-haspopup=menu、aria-expanded 随开合变化、打开后 aria-controls 指向菜单，菜单 aria-labelledby 指回按钮', () => {
    const { trigger } = mountMenu();
    expect(trigger, '应有 aria-haspopup=menu 的触发按钮').not.toBeNull();
    expect(trigger.textContent).toContain('更多操作');
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(menuEl(), '关闭时没有菜单').toBeNull();
    openMenu(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('true');
    const menu = menuEl();
    expect(menu, '点击后应出现 role=menu').not.toBeNull();
    expect(menu!.id).not.toBe('');
    expect(trigger.getAttribute('aria-controls')).toBe(menu!.id);
    expect(trigger.id).not.toBe('');
    expect(menu!.getAttribute('aria-labelledby')).toBe(trigger.id);
    expect(menu!.classList.contains('tt-fc'), '菜单外框应带 tt-fc').toBe(true);
    const items = itemEls();
    expect(items.map((el) => (el.textContent || '').trim())).toEqual(['甲', '乙', '丙']);
    for (const el of items) {
      expect(el.getAttribute('tabindex')).toBe('-1');
    }
  });

  it('打开后焦点在第一项；再点触发按钮关闭', () => {
    const { trigger } = mountMenu();
    openMenu(trigger);
    expect(document.activeElement).toBe(itemEls()[0]);
    fireEvent.click(trigger);
    expect(menuEl(), '再点触发按钮应关闭').toBeNull();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('ArrowDown、ArrowUp 移动并循环，Home、End 到首尾', () => {
    const { trigger } = mountMenu();
    openMenu(trigger);
    const items = itemEls();
    key('ArrowDown');
    expect(document.activeElement).toBe(items[1]);
    key('ArrowDown');
    expect(document.activeElement).toBe(items[2]);
    key('ArrowDown');
    expect(document.activeElement, '末项再按 ArrowDown 回到第一项').toBe(items[0]);
    key('ArrowUp');
    expect(document.activeElement, '首项按 ArrowUp 到末项').toBe(items[2]);
    key('ArrowUp');
    expect(document.activeElement).toBe(items[1]);
    key('Home');
    expect(document.activeElement).toBe(items[0]);
    key('End');
    expect(document.activeElement).toBe(items[2]);
  });

  it('Enter：onSelect 收到该项 id 一次，菜单消失，焦点回触发按钮，aria-expanded=false', () => {
    const { trigger, onSelect } = mountMenu();
    openMenu(trigger);
    key('ArrowDown');
    key('Enter');
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith('b');
    expect(menuEl(), 'Enter 后菜单应消失').toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });

  it('Esc：菜单消失，焦点回触发按钮，不调 onSelect，Esc 不再往外传', () => {
    const { trigger, onSelect, outer } = mountMenu();
    openMenu(trigger);
    key('ArrowDown');
    key('Escape');
    expect(menuEl(), 'Esc 后菜单应消失').toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
    expect(onSelect).not.toHaveBeenCalled();
    expect(escapeCalls(outer), 'Esc 由菜单处理，stopPropagation').toBe(0);
  });

  it('在菜单与触发按钮之外按下鼠标：菜单关闭；在菜单里按下鼠标不关', () => {
    const { trigger } = mountMenu();
    openMenu(trigger);
    fireEvent.mouseDown(itemEls()[1]);
    expect(menuEl(), '在菜单里按下鼠标不该关闭').not.toBeNull();
    fireEvent.mouseDown(document.body);
    expect(menuEl(), '在外面按下鼠标应关闭').toBeNull();
    expect(trigger.getAttribute('aria-expanded')).toBe('false');
  });
});
"""

PROBE_P4 = PRELUDE + r"""
let Dialog: any;

beforeAll(async () => {
  Dialog = (await import('../src/components/Dialog')).Dialog;
});

function DialogBody() {
  return (
    <>
      <p>正文</p>
      <input aria-label="名称" />
    </>
  );
}
const FOOTER = (
  <>
    <button type="button">取消</button>
    <button type="button">确定</button>
  </>
);

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
        title="确认操作"
        footer={FOOTER}
      >
        <DialogBody />
      </Dialog>
    </div>
  );
}

function openDialog() {
  const onClose = vi.fn();
  const outer = vi.fn();
  const r = render(
    <div onKeyDown={outer}>
      <Harness onClose={onClose} />
    </div>,
  );
  const trigger = r.container.querySelector('#gate-trigger') as HTMLButtonElement;
  focusOn(trigger);
  fireEvent.click(trigger);
  const dialog = document.querySelector('[role="dialog"]') as HTMLElement;
  return { ...r, trigger, onClose, outer, dialog };
}

describe('对话框（W6）', () => {
  it('open 为 false 时不渲染对话框和遮罩', () => {
    const r = render(
      <Dialog open={false} onClose={() => {}} title="标题">
        内容
      </Dialog>,
    );
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.querySelector('.tt-dialog-scrim')).toBeNull();
    expect(document.body.textContent).not.toContain('内容');
    r.unmount();
  });

  it('role=dialog、aria-modal=true、aria-labelledby 指向标题 h2，带 tt-dialog、tt-enter、tt-fc，在遮罩里', () => {
    const { dialog } = openDialog();
    expect(dialog, '点触发按钮后应出现 role=dialog').not.toBeNull();
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    const labelId = dialog.getAttribute('aria-labelledby');
    expect(labelId, '应有 aria-labelledby').toBeTruthy();
    const title = document.getElementById(labelId as string);
    expect(title, 'aria-labelledby 应指向存在的元素').not.toBeNull();
    expect(title!.tagName).toBe('H2');
    expect((title!.textContent || '').trim()).toBe('确认操作');
    expect(dialog.classList.contains('tt-dialog')).toBe(true);
    expect(dialog.classList.contains('tt-enter')).toBe(true);
    expect(dialog.classList.contains('tt-fc'), '外框应带 tt-fc').toBe(true);
    const scrim = document.querySelector('.tt-dialog-scrim') as HTMLElement;
    expect(scrim, '应有遮罩 tt-dialog-scrim').not.toBeNull();
    expect(scrim.contains(dialog)).toBe(true);
    expect(document.body.textContent).toContain('正文');
  });

  it('遮罩和对话框不在渲染容器里，在 body 下的挂载层里', () => {
    const { container, dialog } = openDialog();
    const scrim = document.querySelector('.tt-dialog-scrim') as HTMLElement;
    inMountLayer(scrim, container);
    inMountLayer(dialog, container);
  });

  it('打开时焦点进对话框，落在第一个可聚焦元素（头部的关闭钮，名称「关闭（Esc）」）', () => {
    const { dialog } = openDialog();
    const list = focusables(dialog);
    expect(list.length).toBeGreaterThanOrEqual(4);
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).toBe(list[0]);
    expect(list[0].getAttribute('aria-label')).toBe('关闭（Esc）');
  });

  it('末元素按 Tab：preventDefault 并回到首元素；首元素按 Shift+Tab：preventDefault 并到末元素', () => {
    const { dialog } = openDialog();
    const list = focusables(dialog);
    const first = list[0];
    const last = list[list.length - 1];
    expect((last.textContent || '').trim()).toBe('确定');
    focusOn(last);
    const notPrevented = key('Tab');
    expect(notPrevented, '末元素的 Tab 应被 preventDefault').toBe(false);
    expect(document.activeElement).toBe(first);
    const notPrevented2 = key('Tab', { shiftKey: true });
    expect(notPrevented2, '首元素的 Shift+Tab 应被 preventDefault').toBe(false);
    expect(document.activeElement).toBe(last);
  });

  it('Esc：调一次 onClose，对话框消失，焦点回触发按钮，Esc 不再往外传', () => {
    const { dialog, trigger, onClose, outer } = openDialog();
    const input = dialog.querySelector('input') as HTMLInputElement;
    focusOn(input);
    key('Escape');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.querySelector('[role="dialog"]'), 'Esc 后应消失').toBeNull();
    expect(document.querySelector('.tt-dialog-scrim')).toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(escapeCalls(outer), '处理了 Esc 就 stopPropagation').toBe(0);
  });

  it('关闭钮：调一次 onClose，对话框消失，焦点回触发按钮', () => {
    const { dialog, trigger, onClose } = openDialog();
    const close = dialog.querySelector('[aria-label="关闭（Esc）"]') as HTMLElement;
    expect(close, '头部应有名称为「关闭（Esc）」的关闭钮').not.toBeNull();
    fireEvent.click(close);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('遮罩上 mousedown 被阻止默认（不把焦点移走），点遮罩不关闭', () => {
    const { dialog, onClose } = openDialog();
    const scrim = document.querySelector('.tt-dialog-scrim') as HTMLElement;
    const notPrevented = fireEvent.mouseDown(scrim);
    expect(notPrevented, '遮罩上的 mousedown 应被 preventDefault').toBe(false);
    fireEvent.click(scrim);
    expect(onClose).not.toHaveBeenCalled();
    expect(document.querySelector('[role="dialog"]')).toBe(dialog);
  });

  it('卸载时也把焦点还给打开前的元素', () => {
    function Toggle() {
      const [mounted, setMounted] = React.useState(false);
      return (
        <div>
          <button type="button" id="gate-trigger" onClick={() => setMounted(true)}>
            开
          </button>
          <button type="button" id="gate-remove" onClick={() => setMounted(false)}>
            拆
          </button>
          {mounted && (
            <Dialog open onClose={() => {}} title="T">
              <input aria-label="名称" />
            </Dialog>
          )}
        </div>
      );
    }
    const r = render(<Toggle />);
    const trigger = r.container.querySelector('#gate-trigger') as HTMLButtonElement;
    focusOn(trigger);
    fireEvent.click(trigger);
    const dialog = document.querySelector('[role="dialog"]') as HTMLElement;
    expect(dialog.contains(document.activeElement)).toBe(true);
    fireEvent.click(r.container.querySelector('#gate-remove') as Element);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement, '卸载后焦点应回到触发按钮').toBe(trigger);
  });

  it('StrictMode 下一开始就打开：焦点进框，关闭后回到打开前的元素（记与还都幂等）', () => {
    const opener = document.createElement('button');
    opener.textContent = '外部触发';
    document.body.appendChild(opener);
    try {
      opener.focus();
      expect(document.activeElement).toBe(opener);
      const ui = (open: boolean) => (
        <React.StrictMode>
          <Dialog open={open} onClose={() => {}} title="S" footer={FOOTER}>
            <DialogBody />
          </Dialog>
        </React.StrictMode>
      );
      const r = render(ui(true));
      const dialog = document.querySelector('[role="dialog"]') as HTMLElement;
      expect(dialog).not.toBeNull();
      expect(dialog.contains(document.activeElement), 'StrictMode 下焦点也应在框里').toBe(true);
      r.rerender(ui(false));
      expect(document.querySelector('[role="dialog"]')).toBeNull();
      expect(document.activeElement, 'StrictMode 下关闭后焦点应回到打开前的元素').toBe(opener);
    } finally {
      opener.remove();
    }
  });
});
"""

PROBE_P5 = PRELUDE + r"""
let Drawer: any;

beforeAll(async () => {
  Drawer = (await import('../src/components/Drawer')).Drawer;
});

const FOOTER = (
  <>
    <button type="button">取消</button>
    <button type="button">确定</button>
  </>
);

function Harness({ onClose }: { onClose: () => void }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div>
      <button type="button" id="gate-trigger" onClick={() => setOpen(true)}>
        打开抽屉
      </button>
      <Drawer
        open={open}
        onClose={() => {
          onClose();
          setOpen(false);
        }}
        title="详情"
        footer={FOOTER}
      >
        <p>说明</p>
        <input aria-label="备注" />
      </Drawer>
    </div>
  );
}

function openDrawer() {
  const onClose = vi.fn();
  const outer = vi.fn();
  const r = render(
    <div onKeyDown={outer}>
      <Harness onClose={onClose} />
    </div>,
  );
  const trigger = r.container.querySelector('#gate-trigger') as HTMLButtonElement;
  focusOn(trigger);
  fireEvent.click(trigger);
  const drawer = document.querySelector('[role="dialog"]') as HTMLElement;
  return { ...r, trigger, onClose, outer, drawer };
}

describe('抽屉', () => {
  it('open 为 false 时不渲染', () => {
    render(
      <Drawer open={false} onClose={() => {}} title="详情">
        内容
      </Drawer>,
    );
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.body.textContent).not.toContain('内容');
  });

  it('role=dialog、aria-modal=false、aria-labelledby 指向标题，带 tt-drawer、tt-drawer-in、tt-fc，没有遮罩', () => {
    const { drawer } = openDrawer();
    expect(drawer, '点触发按钮后应出现 role=dialog').not.toBeNull();
    expect(drawer.getAttribute('aria-modal')).toBe('false');
    const labelId = drawer.getAttribute('aria-labelledby');
    expect(labelId).toBeTruthy();
    const title = document.getElementById(labelId as string);
    expect(title).not.toBeNull();
    expect((title!.textContent || '').trim()).toBe('详情');
    expect(drawer.classList.contains('tt-drawer')).toBe(true);
    expect(drawer.classList.contains('tt-drawer-in')).toBe(true);
    expect(drawer.classList.contains('tt-fc'), '外框应带 tt-fc').toBe(true);
    expect(document.querySelector('[class*="scrim"]'), '抽屉没有遮罩').toBeNull();
    expect(document.querySelector('[aria-modal="true"]')).toBeNull();
  });

  it('抽屉不在渲染容器里，在 body 下的挂载层里', () => {
    const { container, drawer } = openDrawer();
    inMountLayer(drawer, container);
  });

  it('打开时焦点进抽屉，落在第一个可聚焦元素', () => {
    const { drawer } = openDrawer();
    const list = focusables(drawer);
    expect(list.length).toBeGreaterThanOrEqual(4);
    expect(document.activeElement).toBe(list[0]);
  });

  it('不困焦点：末元素 Tab、首元素 Shift+Tab 都不被 preventDefault', () => {
    const { drawer } = openDrawer();
    const list = focusables(drawer);
    focusOn(list[list.length - 1]);
    expect(key('Tab'), '末元素的 Tab 不该被拦').toBe(true);
    expect(document.activeElement, '抽屉自己不挪焦点').toBe(list[list.length - 1]);
    focusOn(list[0]);
    expect(key('Tab', { shiftKey: true }), '首元素的 Shift+Tab 不该被拦').toBe(true);
    expect(document.activeElement).toBe(list[0]);
  });

  it('焦点在抽屉里按 Esc：调一次 onClose，抽屉消失，焦点回触发按钮，Esc 不再往外传', () => {
    const { drawer, trigger, onClose, outer } = openDrawer();
    focusOn(drawer.querySelector('input') as HTMLElement);
    key('Escape');
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.querySelector('[role="dialog"]'), 'Esc 后应消失').toBeNull();
    expect(document.activeElement).toBe(trigger);
    expect(escapeCalls(outer), '处理了 Esc 就 stopPropagation').toBe(0);
  });

  it('关闭钮关闭并还焦点；点抽屉外不关闭（非模态）', () => {
    const { drawer, trigger, onClose } = openDrawer();
    fireEvent.mouseDown(document.body);
    fireEvent.click(document.body);
    expect(onClose, '点抽屉外不该关闭').not.toHaveBeenCalled();
    expect(document.querySelector('[role="dialog"]')).toBe(drawer);
    const close = focusables(drawer)[0];
    fireEvent.click(close);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it('StrictMode 下一开始就打开：焦点进抽屉，关闭后回到打开前的元素', () => {
    const opener = document.createElement('button');
    opener.textContent = '外部触发';
    document.body.appendChild(opener);
    try {
      opener.focus();
      const ui = (open: boolean) => (
        <React.StrictMode>
          <Drawer open={open} onClose={() => {}} title="S" footer={FOOTER}>
            <p>说明</p>
          </Drawer>
        </React.StrictMode>
      );
      const r = render(ui(true));
      const drawer = document.querySelector('[role="dialog"]') as HTMLElement;
      expect(drawer).not.toBeNull();
      expect(drawer.contains(document.activeElement)).toBe(true);
      r.rerender(ui(false));
      expect(document.querySelector('[role="dialog"]')).toBeNull();
      expect(document.activeElement).toBe(opener);
    } finally {
      opener.remove();
    }
  });
});
"""

PROBE_P6 = PRELUDE + r"""
let Toast: any;

beforeAll(async () => {
  Toast = (await import('../src/components/Toast')).Toast;
});

function statusEl(): HTMLElement {
  return document.querySelector('[role="status"]') as HTMLElement;
}
function deepestWith(root: Element, text: string): HTMLElement {
  let found = root as HTMLElement;
  const walk = (el: Element) => {
    for (const child of Array.from(el.children)) {
      if ((child.textContent || '').includes(text)) {
        found = child as HTMLElement;
        walk(child);
        break;
      }
    }
  };
  walk(root);
  return found;
}
function mountToast(open = true, props: any = {}) {
  const onClose = vi.fn();
  const ui = (o: boolean) => (
    <Toast open={o} onClose={onClose} {...props}>
      已复制
    </Toast>
  );
  const r = render(ui(open));
  return { ...r, onClose, ui };
}

describe('轻提示', () => {
  it('常驻 role=status、aria-live=polite 的区域：没有轻提示时也在，是空的，没有按钮', () => {
    mountToast(false);
    const status = statusEl();
    expect(status, 'open 为 false 时也应渲染 role=status 区域').not.toBeNull();
    expect(status.getAttribute('aria-live')).toBe('polite');
    expect((status.textContent || '').trim()).toBe('');
    expect(status.querySelector('button')).toBeNull();
  });

  it('可见时：图标 aria-hidden、文字、名称「关闭提示」的关闭钮；挂在 body 下的挂载层里，外框带 tt-fc', () => {
    const { container } = mountToast(true);
    const status = statusEl();
    expect(status.textContent).toContain('已复制');
    const svg = status.querySelector('svg');
    expect(svg, '应有图标').not.toBeNull();
    expect(svg!.getAttribute('aria-hidden')).toBe('true');
    expect(status.querySelector('button[aria-label="关闭提示"]'), '应有名称为「关闭提示」的关闭钮').not.toBeNull();
    inMountLayer(status, container);
    expect(status.matches('.tt-fc') || status.querySelector('.tt-fc') !== null, '外框应带 tt-fc').toBe(true);
  });

  it('4999ms 时 onClose 没调，5000ms 调一次，之后不重复调', () => {
    const { onClose } = mountToast(true);
    advance(4999);
    expect(onClose).not.toHaveBeenCalled();
    advance(1);
    expect(onClose).toHaveBeenCalledTimes(1);
    advance(20000);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('鼠标移入暂停：第 3000ms 移入，再推 10000ms 不调；移出后按剩余 2000ms 接着走', () => {
    const { onClose } = mountToast(true);
    advance(3000);
    const target = deepestWith(statusEl(), '已复制');
    fireEvent.mouseEnter(target);
    advance(10000);
    expect(onClose, '悬停期间不计时').not.toHaveBeenCalled();
    fireEvent.mouseLeave(target);
    advance(1999);
    expect(onClose, '移出后还剩 2000ms，1999ms 时不该调').not.toHaveBeenCalled();
    advance(1);
    expect(onClose, '移出后 2000ms 调一次（接着走剩余时间，不是重新计 5 秒）').toHaveBeenCalledTimes(1);
  });

  it('关闭钮立即调 onClose', () => {
    const { onClose } = mountToast(true);
    fireEvent.click(statusEl().querySelector('button[aria-label="关闭提示"]') as Element);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('关闭后重新打开：旧计时器清掉，重新计满 5000ms；关闭后区域变空', () => {
    const { onClose, rerender, ui } = mountToast(true);
    advance(2000);
    rerender(ui(false));
    expect((statusEl().textContent || '').trim()).toBe('');
    expect(statusEl().querySelector('button')).toBeNull();
    advance(10000);
    expect(onClose, '关闭后旧计时器不该再触发').not.toHaveBeenCalled();
    rerender(ui(true));
    advance(4999);
    expect(onClose).not.toHaveBeenCalled();
    advance(1);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('卸载清计时器', () => {
    const { onClose, unmount } = mountToast(true);
    advance(1000);
    unmount();
    advance(10000);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('tone 可选 success、info，缺省 success，都照常显示', () => {
    for (const tone of [undefined, 'success', 'info']) {
      const { unmount } = mountToast(true, tone ? { tone } : {});
      expect(statusEl().textContent).toContain('已复制');
      unmount();
    }
  });
});
"""

CODES17 = ["PREPARING", "PREPARED", "PREPARE_FAILED", "RUNNING", "COLLECTING", "NEEDS_REVIEW", "PASS",
           "ACCEPTED_WITH_EXCEPTION", "REVISE", "BLOCKED", "ESCALATE", "INFRA_FAILURE", "TIMEOUT", "CANCELLED",
           "INTEGRATED", "ABANDONED", "SUPERSEDED"]

PROBE_P7 = PRELUDE + r"""
let StatusTag: any;
const SERVER_DS: string[] = __SERVER_DS__;
const BADGE_DS: string[] = __BADGE_DS__;
const CODES: string[] = __CODES__;

beforeAll(async () => {
  StatusTag = (await import('../src/components/StatusTag')).StatusTag;
});

function mountTag(state: string, size?: string) {
  const r = render(<StatusTag state={state} size={size as any} />);
  return { ...r, tag: r.container.firstElementChild as HTMLElement };
}
function dsOf(svg: Element): Array<string | null> {
  return Array.from(svg.querySelectorAll('path')).map((p) => p.getAttribute('d'));
}

describe('状态补丁', () => {
  it('ACCEPTED_WITH_EXCEPTION 中号、小号都恰有一个圆点：aria-hidden、没有文字、在第一个 svg 之后', () => {
    for (const size of ['md', 'sm']) {
      const { tag, unmount } = mountTag('ACCEPTED_WITH_EXCEPTION', size);
      const dots = tag.querySelectorAll('.tt-status__dot');
      expect(dots.length, size + ' 号应恰有一个 tt-status__dot').toBe(1);
      const dot = dots[0] as HTMLElement;
      expect(dot.getAttribute('aria-hidden')).toBe('true');
      expect((dot.textContent || '').trim()).toBe('');
      expect(dot.tagName.toLowerCase(), '圆点不是 svg').not.toBe('svg');
      const svg = tag.querySelector('svg') as Element;
      expect(svg).not.toBeNull();
      expect(svg.compareDocumentPosition(dot) & Node.DOCUMENT_POSITION_FOLLOWING, '圆点应在第一个 svg 之后').toBeTruthy();
      unmount();
    }
  });

  it('第一个 svg 仍是 badge-check（路径等于令牌板），标签文字仍是「带豁免通过」，圆点和图标包在 tt-status__icon 里', () => {
    const { tag } = mountTag('ACCEPTED_WITH_EXCEPTION');
    const svgs = tag.querySelectorAll('svg');
    expect(svgs.length, '圆点不能做成 svg').toBe(1);
    expect(svgs[0].getAttribute('aria-hidden')).toBe('true');
    expect(dsOf(svgs[0])).toEqual(BADGE_DS);
    expect((tag.textContent || '').trim()).toBe('带豁免通过');
    const wrap = tag.querySelector('.tt-status__icon') as HTMLElement;
    expect(wrap, '应有相对定位的 tt-status__icon 包着图标').not.toBeNull();
    expect(wrap.contains(svgs[0])).toBe(true);
    expect(wrap.contains(tag.querySelector('.tt-status__dot'))).toBe(true);
  });

  it('其余 16 个状态与未知状态码没有圆点，每个标签恰一个 svg 且 aria-hidden', () => {
    const others = CODES.filter((c) => c !== 'ACCEPTED_WITH_EXCEPTION');
    expect(others.length).toBe(16);
    for (const code of [...others, 'FUTURE_STATE', 'constructor']) {
      for (const size of ['md', 'sm']) {
        const { tag, unmount } = mountTag(code, size);
        expect(tag.querySelectorAll('.tt-status__dot').length, code + '（' + size + '）不该有圆点').toBe(0);
        const svgs = tag.querySelectorAll('svg');
        expect(svgs.length, code + ' 应恰有一个 svg').toBe(1);
        expect(svgs[0].getAttribute('aria-hidden')).toBe('true');
        unmount();
      }
    }
  });

  it('INFRA_FAILURE 的 svg 路径等于令牌板的 server-crash（含 m13 6-4 6h6l-4 6）', () => {
    const { tag } = mountTag('INFRA_FAILURE');
    const svg = tag.querySelector('svg') as Element;
    expect(svg).not.toBeNull();
    expect(dsOf(svg)).toEqual(SERVER_DS);
    expect(SERVER_DS).toContain('m13 6-4 6h6l-4 6');
    expect((tag.textContent || '').trim()).toBe('基础设施故障');
  });
});
"""

# (键, 探针源码, 需要先存在的仓库文件, 对应的用例名)
PROBE_SPECS = {
    "p2": (PROBE_P2, [f"{COMP_REL}/IconButton.tsx", f"{COMP_REL}/Tooltip.tsx"]),
    "p3": (PROBE_P3, [f"{COMP_REL}/Menu.tsx"]),
    "p4": (PROBE_P4, [f"{COMP_REL}/Dialog.tsx"]),
    "p5": (PROBE_P5, [f"{COMP_REL}/Drawer.tsx"]),
    "p6": (PROBE_P6, [f"{COMP_REL}/Toast.tsx"]),
    "p7": (PROBE_P7, [f"{COMP_REL}/StatusTag.tsx", f"{SRC_REL}/domain/attemptStates.ts"]),
}


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


def build_probe_source(key):
    source = PROBE_SPECS[key][0]
    if key == "p7":
        source = (source.replace("__SERVER_DS__", json.dumps(canvas_icon_ds("server"), ensure_ascii=False))
                  .replace("__BADGE_DS__", json.dumps(canvas_icon_ds("badge"), ensure_ascii=False))
                  .replace("__CODES__", json.dumps(CODES17)))
    return source


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
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
            for key in PROBE_SPECS:
                missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                try:
                    source = build_probe_source(key)
                except AssertionError as exc:
                    pipe.probe_skipped[key] = f"探针 {key} 的输入（令牌板路径）取不出来，未运行：{exc}"
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


def need_components(*names, css=True):
    """用例开头先查组件文件在不在；缺哪个就以断言失败写明（基线上组件还不存在）。"""
    missing = []
    for name in names:
        for ext in (("tsx", "css") if css else ("tsx",)):
            if not (REPO_ROOT / COMP_REL / f"{name}.{ext}").is_file():
                missing.append(f"{COMP_REL}/{name}.{ext}")
    assert not missing, f"缺少组件文件（基线上还没有实现）：{missing}"


# ---------------------------------------------------------------------------
# S 系列：静态断言
# ---------------------------------------------------------------------------

def test_d01_components_exported():
    """S1 / D01–D05：6 个新组件的 .tsx 与 .css 都在，components/overlay/ 里有内部模块；components/index.ts 导出 6 个新组件与
    它们的 Props 类型、原来的 5 个组件，且不导出 overlay。"""
    need_components(*NEW_COMPONENTS)
    overlay = need_dir(f"{COMP_REL}/overlay")
    modules = [p for p in overlay.iterdir() if p.is_file() and p.suffix in (".ts", ".tsx") and ".test." not in p.name]
    assert modules, f"{COMP_REL}/overlay/ 里没有内部模块（*.ts、*.tsx）"
    fail_if(index_problems(_read(need_file(f"{COMP_REL}/index.ts"))), "components/index.ts 的导出")


def test_d07_infra_failure_icon_is_server_crash():
    """S2 / D07：icons/index.tsx 有 ServerCrashIcon、没有 ServerIcon（src 里任何非测试文件都不再出现 ServerIcon）；它的 path d
    列表等于令牌板 :342 的 s.ic.server（含 m13 6-4 6h6l-4 6）；attemptStates.ts 的 INFRA_FAILURE 用 ServerCrashIcon 并导入它。"""
    icons = _read(need_file(f"{SRC_REL}/icons/index.tsx"))
    states = _read(need_file(f"{SRC_REL}/domain/attemptStates.ts"))
    texts = {}
    for path in sorted((WEB / "src").rglob("*")):
        if path.is_file() and path.suffix in (".ts", ".tsx") and ".test." not in path.name:
            texts[path.relative_to(WEB).as_posix()] = _read(path)
    fail_if(infra_failure_problems(icons, states, texts), "INFRA_FAILURE 的 server-crash 图标")


def test_d03_dialog_css_and_scrim():
    """S3 / D03：Dialog.css 里 .tt-dialog 宽 560px、max-width: 100%、border-radius: var(--tt-radius-xl)、box-shadow: var(--tt-shadow-3)；
    .tt-dialog-scrim 固定定位、四边为 0（inset: 0 或 top、right、bottom、left 各为 0，底部不让位）、z-index: var(--tt-z-dialog)、
    background: var(--tt-scrim)。"""
    fail_if(dialog_css_problems(_read(need_file(f"{COMP_REL}/Dialog.css"))), "Dialog.css")


def test_d04_drawer_css_geometry():
    """S4 / D04：Drawer.css 里 .tt-drawer 宽 520px、max-width: 60%、固定定位、right 为 0、bottom: var(--tt-tabbar-height)、
    z-index: var(--tt-z-drawer)。不断言顶边（本片取 0，应用框架那一片接标题栏时再改）。"""
    fail_if(drawer_css_problems(_read(need_file(f"{COMP_REL}/Drawer.css"))), "Drawer.css")


def test_d05_toast_css_position():
    """S5 / D05：Toast.css 里有一条固定定位的规则同时满足 right: var(--tt-space-6)、
    bottom: calc(var(--tt-tabbar-height) + var(--tt-space-4))（空白归一）、z-index: var(--tt-z-toast)。"""
    fail_if(toast_css_problems(_read(need_file(f"{COMP_REL}/Toast.css"))), "Toast.css")


def test_d07_layer_and_dot_css_tokens():
    """S6 / D01、D02、D07：StatusTag.css 的 .tt-status__dot 用 background: var(--tt-tone-warning-fg)、描边（box-shadow 或 border）用
    var(--tt-tone-success-bg)、圆角 var(--tt-radius-full) 或 50%；圆点不画进 src/icons/；Tooltip.css 有底 var(--tt-gray-900)、
    字 var(--tt-gray-50)、z-index: var(--tt-z-tooltip)；Menu.css 有 z-index: var(--tt-z-popover)。"""
    tooltip = _read(need_file(f"{COMP_REL}/Tooltip.css"))
    menu = _read(need_file(f"{COMP_REL}/Menu.css"))
    status = _read(need_file(f"{COMP_REL}/StatusTag.css"))
    problems = layer_and_dot_problems(tooltip, menu, status)
    icons = _read(need_file(f"{SRC_REL}/icons/index.tsx"))
    if "tt-status__dot" in icons:
        problems.append("圆点不该画进 src/icons/")
    fail_if(problems, "层级与圆点的令牌")


def test_d06_w5_passes_and_catches_changes(tmp_path):
    """S7 / D06：子进程跑 python -m pytest tests/test_desktop_attempt_states.py -q 通过；在 tmp_path 搭最小副本
    （scripts/pi_dispatch.py、desktop/web/src/domain/attemptStates.ts、这个测试文件），原样副本通过，
    四种改法（桌面端各删一个、各加一个状态；调度器各删一个、各加一个状态）各跑一次都失败。"""
    w5 = need_file(W5_REL)
    code, out = run_w5(REPO_ROOT)
    assert code == 0, f"{W5_REL} 在仓库里应通过，退出码 {code}：\n{tail_text(out)}"

    pd_src = _read(need_file("scripts/pi_dispatch.py"))
    ts_src = _read(need_file(f"{SRC_REL}/domain/attemptStates.ts"))
    w5_src = w5.read_text(encoding="utf-8")

    def make_copy(name, pd_text, ts_text):
        root = tmp_path / name
        (root / "scripts").mkdir(parents=True)
        (root / "tests").mkdir()
        (root / "desktop" / "web" / "src" / "domain").mkdir(parents=True)
        (root / "scripts" / "pi_dispatch.py").write_text(pd_text, encoding="utf-8", newline="\n")
        (root / "desktop" / "web" / "src" / "domain" / "attemptStates.ts").write_text(ts_text, encoding="utf-8", newline="\n")
        (root / W5_REL).write_text(w5_src, encoding="utf-8", newline="\n")
        return root

    code, out = run_w5(make_copy("same", pd_src, ts_src))
    assert code == 0, f"原样副本（不依赖仓库里的别的文件）应通过，退出码 {code}：\n{tail_text(out)}"

    variants = {
        "桌面端少一个状态": (pd_src, mutate_ts_drop(ts_src)),
        "桌面端多一个状态": (pd_src, mutate_ts_add(ts_src)),
        "调度器少一个状态": (mutate_pd_drop(pd_src), ts_src),
        "调度器多一个状态": (mutate_pd_add(pd_src), ts_src),
    }
    survived = []
    for index, (name, (pd_text, ts_text)) in enumerate(variants.items()):
        code, out = run_w5(make_copy(f"variant{index}", pd_text, ts_text))
        if code == 0:
            survived.append(name)
    assert not survived, f"这些改动没有让 {W5_REL} 变红：{survived}"


# ---------------------------------------------------------------------------
# P 系列：流水线断言
# ---------------------------------------------------------------------------

def test_d09_pipeline_steps_pass(pipeline):
    """P1 / D09（守卫）：npm ci、npm run build、npm test、npm run check:contract 都退出 0；npm test 有通过的用例，没有失败、跳过、待办。"""
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    step = pipeline.steps["npm test"]
    out = step.out
    assert re.search(r"Tests\s+(?:.*\|\s*)?\d+ passed", out), f"npm test 输出里没有 'Tests … N passed'：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", out), f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert re.search(r"Test Files\s+\d+ passed", out) and not re.search(r"Test Files\s+.*\bfailed\b", out), \
        f"npm test 的 Test Files 行异常：\n{step.tail}"


def test_d01_probe_icon_button_tooltip(pipeline):
    """P2 / D01：探针渲染 IconButton 与 Tooltip：aria-label 等于 label；svg aria-hidden；按钮里没有文字；悬停 399ms 没有 role=tooltip、
    400ms 有且文字对、aria-describedby 指向它；移开立即消失；聚焦同样 400ms，失焦消失；可见时 Esc 消失，之后再推 1000ms 仍不出现；
    计时中 Esc 取消；提示在 body 下的挂载层里。"""
    need_components("IconButton", "Tooltip")
    assert_probe_ok(pipeline, "p2")


def test_d02_probe_menu_keyboard(pipeline):
    """P3 / D02：点按钮 aria-expanded=true、role=menu 出现、焦点在第一项；ArrowDown 到第二项；末项 ArrowDown 回第一项；首项 ArrowUp 到末项；
    Home、End；Enter：onSelect 收到该项 id 一次、菜单消失、焦点回按钮、aria-expanded=false；再开、Esc：消失、焦点回按钮、onSelect 没被调；
    菜单外 mousedown 关闭。"""
    need_components("Menu")
    assert_probe_ok(pipeline, "p3")


def test_d03_probe_dialog_w6(pipeline):
    """P4 / D03（W6）：先聚焦再点触发按钮；role=dialog、aria-modal=true、aria-labelledby 指向标题；焦点在框内（第一个可聚焦元素）；
    末元素 Tab 到首元素；首元素 Shift+Tab 到末元素（keydown 被 preventDefault）；Esc：对话框消失、焦点回触发按钮；关闭钮同；
    遮罩不在渲染容器里、在 body 下的挂载层里；遮罩 mousedown 被阻止默认、点遮罩不关；卸载与 StrictMode 下焦点也对。"""
    need_components("Dialog")
    assert_probe_ok(pipeline, "p4")


def test_d04_probe_drawer_nonmodal(pipeline):
    """P5 / D04：role=dialog、aria-modal=false；没有遮罩；焦点进入；末元素 Tab 不被拦（keydown 没有被 preventDefault）；
    焦点在抽屉里按 Esc：消失、焦点回触发按钮；点抽屉外不关闭。"""
    need_components("Drawer")
    assert_probe_ok(pipeline, "p5")


def test_d05_probe_toast_timing(pipeline):
    """P6 / D05：role=status；4999ms 时 onClose 没调、5000ms 调一次；第 3000ms 移入再推 10000ms 不调；移出后 1999ms 不调、2000ms 调；
    关闭钮立即调；关闭后重新打开重新计满 5000ms；卸载清计时器。"""
    need_components("Toast")
    assert_probe_ok(pipeline, "p6")


def test_d07_probe_status_patches(pipeline):
    """P7 / D07：ACCEPTED_WITH_EXCEPTION 恰一个 tt-status__dot、aria-hidden=true、在第一个 svg 之后、标签文字仍是「带豁免通过」；
    其余 16 个与未知状态码没有圆点；INFRA_FAILURE 的 svg d 列表等于令牌板 s.ic.server。"""
    assert_probe_ok(pipeline, "p7")


def test_d10_worktree_unchanged_by_pipeline(pipeline):
    """P9 / D10（守卫，门禁端多加的一条）：流水线与探针前后 git status 相同；package.json、锁文件、index.html、vite.config.ts、
    tsconfig.json、tokens.css、base.css、main.tsx 的摘要不变；gate-probe/ 没有留下。"""
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

GOOD_DIALOG_CSS = """
/* 写操作页 :357 */
.tt-dialog-scrim {
  position: fixed;
  inset: 0;
  z-index: var(--tt-z-dialog);
  display: grid;
  place-items: center;
  padding: var(--tt-space-6);
  background: var(--tt-scrim);
}
.tt-dialog {
  width: 560px;
  max-width: 100%;
  max-height: calc(100vh - var(--tt-space-12));
  background: var(--tt-surface-1);
  border-radius: var(--tt-radius-xl);
  box-shadow: var(--tt-shadow-3);
}
@media (prefers-reduced-motion: reduce) { .tt-dialog { animation: none; } }
"""

DIALOG_BROKEN = {
    "宽改成 520": ("width: 560px", "width: 520px"),
    "没有 max-width": ("max-width: 100%;", ""),
    "圆角改了": ("var(--tt-radius-xl)", "var(--tt-radius-lg)"),
    "阴影改了": ("var(--tt-shadow-3)", "var(--tt-shadow-2)"),
    "不是固定定位": ("position: fixed", "position: absolute"),
    "inset 不是 0": ("inset: 0;", "inset: 0 0 var(--tt-tabbar-height);"),
    "层级改了": ("var(--tt-z-dialog)", "var(--tt-z-drawer)"),
    "遮罩底色改了": ("background: var(--tt-scrim)", "background: rgba(0, 0, 0, 0.5)"),
}

GOOD_DRAWER_CSS = """
.tt-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: var(--tt-tabbar-height);
  width: 520px;
  max-width: 60%;
  z-index: var(--tt-z-drawer);
}
"""

DRAWER_BROKEN = {
    "宽改成 560": ("width: 520px", "width: 560px"),
    "max-width 改了": ("max-width: 60%", "max-width: 100%"),
    "bottom 改成 0": ("bottom: var(--tt-tabbar-height)", "bottom: 0"),
    "不是固定定位": ("position: fixed", "position: absolute"),
    "right 不是 0": ("right: 0", "right: 8px"),
    "层级改了": ("var(--tt-z-drawer)", "var(--tt-z-dialog)"),
}

GOOD_TOAST_CSS = """
.tt-toast-region { position: relative; }
.tt-toast {
  position: fixed;
  right: var(--tt-space-6);
  bottom: calc(var(--tt-tabbar-height) + var(--tt-space-4));
  z-index: var(--tt-z-toast);
}
"""

TOAST_BROKEN = {
    "right 改了": ("right: var(--tt-space-6)", "right: var(--tt-space-4)"),
    "bottom 少了 tabbar": ("calc(var(--tt-tabbar-height) + var(--tt-space-4))", "var(--tt-space-4)"),
    "层级改了": ("var(--tt-z-toast)", "var(--tt-z-tooltip)"),
    "不是固定定位": ("position: fixed", "position: absolute"),
}


def test_gate_selfcheck_component_css_checks():
    """门禁自检：合同写明的 Dialog、Drawer、Toast 样式通过 S3–S5 的检查（写法有变也通过）；逐项改坏都被抓住。"""
    assert dialog_css_problems(GOOD_DIALOG_CSS) == []
    assert drawer_css_problems(GOOD_DRAWER_CSS) == []
    assert toast_css_problems(GOOD_TOAST_CSS) == []
    # 写法变化不影响：四边分开写、calc 里空白不同、!important、inset 多值
    assert dialog_css_problems(GOOD_DIALOG_CSS.replace("inset: 0;", "top: 0; right: 0; bottom: 0; left: 0;")) == []
    assert dialog_css_problems(GOOD_DIALOG_CSS.replace("inset: 0;", "inset: 0px 0px 0 0;")) == []
    assert drawer_css_problems(GOOD_DRAWER_CSS.replace("top: 0;\n  right: 0;\n  bottom: var(--tt-tabbar-height);",
                                                      "inset: 0 0 var(--tt-tabbar-height) auto;")) == []
    assert toast_css_problems(GOOD_TOAST_CSS.replace("calc(var(--tt-tabbar-height) + var(--tt-space-4))",
                                                     "calc( var(--tt-tabbar-height)+var(--tt-space-4) )")) == []
    assert dialog_css_problems(GOOD_DIALOG_CSS.replace(".tt-dialog {", ".tt-dialog-scrim > .tt-dialog.tt-enter {")) == []
    for name, (old, new) in DIALOG_BROKEN.items():
        assert old in GOOD_DIALOG_CSS, f"自检样本没有改坏的位置：{name}"
        assert dialog_css_problems(GOOD_DIALOG_CSS.replace(old, new, 1)), f"没抓住（Dialog）：{name}"
    for name, (old, new) in DRAWER_BROKEN.items():
        assert old in GOOD_DRAWER_CSS, f"自检样本没有改坏的位置：{name}"
        assert drawer_css_problems(GOOD_DRAWER_CSS.replace(old, new, 1)), f"没抓住（Drawer）：{name}"
    for name, (old, new) in TOAST_BROKEN.items():
        assert old in GOOD_TOAST_CSS, f"自检样本没有改坏的位置：{name}"
        assert toast_css_problems(GOOD_TOAST_CSS.replace(old, new, 1)), f"没抓住（Toast）：{name}"
    assert dialog_css_problems("") and drawer_css_problems("") and toast_css_problems("")


GOOD_TOOLTIP_CSS = ".tt-tooltip { position: fixed; background: var(--tt-gray-900); color: var(--tt-gray-50); z-index: var(--tt-z-tooltip); }"
GOOD_MENU_CSS = ".tt-menu { position: absolute; z-index: var(--tt-z-popover); }"
GOOD_STATUS_CSS = """
.tt-status__icon { position: relative; display: inline-flex; }
.tt-status__dot {
  position: absolute; right: -2px; top: -2px; width: 6px; height: 6px;
  border-radius: var(--tt-radius-full);
  background: var(--tt-tone-warning-fg);
  box-shadow: 0 0 0 1.5px var(--tt-tone-success-bg);
}
"""


def test_gate_selfcheck_layer_and_dot_checks():
    """门禁自检：合同写明的工具提示、菜单、圆点样式通过 S6 的检查；逐项改坏都被抓住。"""
    assert layer_and_dot_problems(GOOD_TOOLTIP_CSS, GOOD_MENU_CSS, GOOD_STATUS_CSS) == []
    assert layer_and_dot_problems(GOOD_TOOLTIP_CSS, GOOD_MENU_CSS,
                                  GOOD_STATUS_CSS.replace("var(--tt-radius-full)", "50%")) == []
    assert layer_and_dot_problems(GOOD_TOOLTIP_CSS, GOOD_MENU_CSS,
                                  GOOD_STATUS_CSS.replace("box-shadow: 0 0 0 1.5px var(--tt-tone-success-bg)",
                                                          "border: 1.5px solid var(--tt-tone-success-bg)")) == []
    broken = {
        "圆点底色": (GOOD_TOOLTIP_CSS, GOOD_MENU_CSS, GOOD_STATUS_CSS.replace("var(--tt-tone-warning-fg)", "var(--tt-tone-danger-fg)")),
        "圆点描边": (GOOD_TOOLTIP_CSS, GOOD_MENU_CSS, GOOD_STATUS_CSS.replace("var(--tt-tone-success-bg)", "var(--tt-surface-1)")),
        "圆点圆角": (GOOD_TOOLTIP_CSS, GOOD_MENU_CSS, GOOD_STATUS_CSS.replace("var(--tt-radius-full)", "var(--tt-radius-sm)")),
        "没有圆点规则": (GOOD_TOOLTIP_CSS, GOOD_MENU_CSS, ".tt-status__icon { position: relative; }"),
        "提示底色": (GOOD_TOOLTIP_CSS.replace("--tt-gray-900", "--tt-gray-800"), GOOD_MENU_CSS, GOOD_STATUS_CSS),
        "提示字色": (GOOD_TOOLTIP_CSS.replace("--tt-gray-50", "--tt-gray-100"), GOOD_MENU_CSS, GOOD_STATUS_CSS),
        "提示层级": (GOOD_TOOLTIP_CSS.replace("--tt-z-tooltip", "--tt-z-toast"), GOOD_MENU_CSS, GOOD_STATUS_CSS),
        "菜单层级": (GOOD_TOOLTIP_CSS, GOOD_MENU_CSS.replace("--tt-z-popover", "--tt-z-dialog"), GOOD_STATUS_CSS),
    }
    for name, args in broken.items():
        assert layer_and_dot_problems(*args), f"没抓住：{name}"


def test_gate_selfcheck_index_and_icon_parsers():
    """门禁自检：components/index.ts 的导出解析认得 export {…}、export type {…}、as 改名；图标块解析与令牌板路径提取对得上
    仓库里没动的 HourglassIcon；令牌板 server 一块有 5 条路径且含 server-crash 的闪电。"""
    good = "\n".join(
        [f"export {{ {c} }} from './{c}';\nexport type {{ {c}Props }} from './{c}';" for c in NEW_COMPONENTS + OLD_COMPONENTS])
    assert index_problems(good) == []
    assert index_problems(good.replace("export { Toast } from './Toast';", "// export { Toast } from './Toast';"))
    assert index_problems(good.replace("export type { MenuProps } from './Menu';", ""))
    assert index_problems(good + "\nexport * from './overlay/focus';")
    assert index_problems(good.replace("export { Drawer }", "export { Drawer as Panel }"))
    star = "\n".join([f"export * from './{c}';" for c in NEW_COMPONENTS + OLD_COMPONENTS])
    assert index_problems(star) == []
    server = canvas_icon_ds("server")
    assert len(server) == 5 and "m13 6-4 6h6l-4 6" in server, server
    badge = canvas_icon_ds("badge")
    assert len(badge) == 2, badge
    icons = _read(need_file(f"{SRC_REL}/icons/index.tsx"))
    assert icon_component_ds(icons, "HourglassIcon") == canvas_icon_ds("hourglass")
    assert icon_component_ds(icons, "BadgeCheckIcon") == badge
    assert icon_component_ds(icons, "NoSuchIcon") is None
    sample = ('export const ServerCrashIcon = (p: P) => (\n  <Svg>\n    <path d="a b" />\n    <path d="c" />\n  </Svg>\n);\n\n'
              'export const Next = () => <path d="zzz" />;\n')
    assert icon_component_ds(sample, "ServerCrashIcon") == ["a b", "c"]


def test_gate_selfcheck_infra_failure_checker():
    """门禁自检：合成的正确图标与状态表通过 S2 的检查；留着 ServerIcon、路径改一位、INFRA_FAILURE 仍用旧名、缺导入都被抓住。"""
    ds = canvas_icon_ds("server")
    block = "\n".join(f'    <path d="{d}" />' for d in ds)
    icons = f"export const ServerCrashIcon = (props: IconProps) => (\n  <Svg {{...props}}>\n{block}\n  </Svg>\n);\n"
    states = ("import { BadgeCheckIcon, ServerCrashIcon } from '../icons';\n"
              "export const ATTEMPT_STATES = {\n"
              "  INFRA_FAILURE: { label: '基础设施故障', tone: 'danger', icon: ServerCrashIcon },\n};\n")
    assert infra_failure_problems(icons, states, {"a.ts": states, "icons.tsx": icons}) == []
    assert infra_failure_problems(icons.replace("m13 6-4 6h6l-4 6", "m13 6-4 6h6l-4 7"), states, {})
    assert infra_failure_problems(icons + "export const ServerIcon = () => null;\n", states, {"icons.tsx": icons + "export const ServerIcon = () => null;\n"})
    assert infra_failure_problems(icons, states.replace("icon: ServerCrashIcon", "icon: ServerIcon"), {})
    assert infra_failure_problems(icons, states.replace("BadgeCheckIcon, ServerCrashIcon", "BadgeCheckIcon"), {})
    assert infra_failure_problems(icons.replace("ServerCrashIcon", "OtherIcon"), states, {})
    assert infra_failure_problems(icons, states, {"x.ts": "import { ServerIcon } from './icons';"})
    # 注释里提到旧名不算
    assert infra_failure_problems(icons, states, {"x.ts": "// 原来叫 ServerIcon\nexport const x = 1;"}) == []


def test_gate_selfcheck_w5_mutations_apply():
    """门禁自检：S7 的四种改法在当前仓库的 pi_dispatch.py 与 attemptStates.ts 上都能落地，且确实改变了文件。"""
    pd_src = _read(need_file("scripts/pi_dispatch.py"))
    ts_src = _read(need_file(f"{SRC_REL}/domain/attemptStates.ts"))
    for mutate, src in ((mutate_pd_drop, pd_src), (mutate_pd_add, pd_src), (mutate_ts_drop, ts_src), (mutate_ts_add, ts_src)):
        assert mutate(src) != src, mutate.__name__
    assert "GATE_FAKE_STATE" in mutate_pd_add(pd_src) and "GATE_FAKE_STATE" in mutate_ts_add(ts_src)
    assert len(mutate_ts_drop(ts_src)) < len(ts_src) and len(mutate_pd_drop(pd_src)) < len(pd_src)
    multi = "export const ATTEMPT_STATES: R = {\n  A: { label: 'a', tone: 'x', icon: I },\n  SUPERSEDED: {\n    label: 'b',\n    tone: 'n',\n    icon: L,\n  },\n};\n"
    assert "SUPERSEDED" not in mutate_ts_drop(multi)


def test_gate_selfcheck_probe_templates():
    """门禁自检：6 份探针（P2–P7；P8 已退役）的用例数、文件名约定与 vitest 的 include 一致；探针不用 skip、only、todo，
    悬停与聚焦的 fireEvent 来自 @testing-library/react（不从 @testing-library/dom 导入）；P7 的占位符都能替换掉。"""
    counts = {key: probe_count(spec[0]) for key, spec in PROBE_SPECS.items()}
    assert counts == {"p2": 10, "p3": 6, "p4": 10, "p5": 8, "p6": 8, "p7": 4}, counts
    vite_cfg = _read(need_file(f"{WEB_REL}/vite.config.ts"))
    assert "gate-probe/**/*.test.{ts,tsx}" in vite_cfg
    for key, (source, _requires) in PROBE_SPECS.items():
        assert not re.search(r"\b(?:it|test|describe)\.(?:skip|todo|only|skipIf|runIf)\b|\bx(?:it|describe)\(|\.only\(", source), key
        assert "@testing-library/dom" not in source, key
        assert "from '@testing-library/react'" in source, key
        assert "useFakeTimers" in source, key
    p7 = build_probe_source("p7")
    for token in ("__SERVER_DS__", "__BADGE_DS__", "__CODES__"):
        assert token not in p7, token
    assert "m13 6-4 6h6l-4 6" in p7 and "ACCEPTED_WITH_EXCEPTION" in p7
    assert len(CODES17) == 17 and len(set(CODES17)) == 17
