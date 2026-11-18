"""T055 战前门禁：桌面端前端「[探测] 与 [模型]：运行时表每行接上作业接口」的黑盒基准测试
（合同 t055-desktop-web-runtime-probe.v1，基线 f768e08b）。

被测对象是运行时表行内的两个新入口（新文件 ``desktop/web/src/writes/RuntimeProbe.tsx`` 与
``RuntimeModels.tsx``）与它们背后的作业客户端泛化（按 kind 存槽、槽里记 runtime）：

- ``api.ts`` 的 ``JobKind`` 扩成三类（逐字 ``export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';``）；
  ``startJob(kind, runtime?)``：扫描那一支正文逐字 ``{ kind }``，两类新作业正文逐字 ``{ kind, runtime }``；
  201 才算建成；桩分支 ``mockStartJob(kind, runtime)``；``getJob`` / ``cancelJob`` 一个字不改。
- ``jobStore.ts``：``KINDS`` 三类、槽里加 ``runtime: string | null``；``ensureJob`` / ``restartJob`` / ``useJob``
  加可选 runtime；新增 ``useBusyRuntime(kind)``（行内入口订阅也算订阅者，对话框关着时作业照查到底）；
  ``scheduleNext`` 没有作业时不排计时器（不整页常驻时空转）；T054 的公式、setTimeout 链、404 并进
  envelope、五个既有导出照旧。
- ``JobCard.tsx``：props 加可选 ``kind``（缺省 'runtime-scan'）与 ``failedDetail``；三张按 kind 的表
  （失败标题 扫描失败/探测失败/列模型失败、进度条 aria-label 扫描进行中/探测进行中/列模型进行中、
  超时 150/150/120）；扫描那一支的字面与 ``runtime-scan: 150`` 留在文件里。
- 两个新入口：文字逐字「探测」/「模型」（不带「…」）、ghost/sm；本类忙于别的行时 ``DisabledAction``，
  悬停逐字「正在探测 <id>」/「正在列 <id> 的模型」；对话框标题「探测 <id>」/「模型 <id>」；脚注
  [重新探测] / [重新列出] 与 [关闭]（关框不取消作业）。
- 探测结果：版本（空串「版本未知」）、命令来源（env→环境变量 / local→本机文件 / path→PATH /
  missing→找不到，这张小表写在新文件里）、命令（数组空格连、null「—」）；pi 再加缺少的参数（空写
  「无」）与思考级别（「、」连）；``ok`` 为假的 failed 照样显示结果块并点明没过的那一项（「版本命令
  退出码 <N>」「<id> --help 退出码 <N>」「pi 缺少参数：<a、b>」）；没有 data 的 failed 只显示内核报错原文。
- 列模型结果：表上方逐字「模型列表来自 pi --list-models，不调用模型」；三列 provider / model /
  是否在允许列表（true「是」、false「否」、null「不限制」）；``<redacted>`` 原样；空数组「没有列出模型」。
- 桩 ``mock/jobs.ts``：``runtime-scan`` 一字不改；两类新 kind 缺 runtime 回 400；探测夹具同一 runtime
  奇数次 ok 为假、偶数次正常；非 pi 给不带 help 的正常结果；列模型四行含一行 allowed:false、
  ``allowed_executors_set: true``、一行 ``<redacted>``。
- ``runtimes-RuntimesView.tsx``：两处 ``<DisabledAction label="探测" / "模型">`` 换成新入口组件；
  ``canProbe`` / ``canModels`` 规则与其余一字不改。

基线（f768e08b）上新文件都不存在、api.ts 只有一类 JobKind、RuntimesView 仍是两处 DisabledAction，
所以本文件的失败落在「记号不在」「文件不存在」「流水线没跑」这类断言上，不是导入、收集或语法错误：
模块级只导入标准库，所有仓库文件的读取都发生在用例函数里；流水线（npm、Vitest、探针）放在
``pipeline`` 会话级夹具里（全量 pytest 默认跳过，点名运行本文件才跑；候选里还没有本片的标记时
夹具不调 npm——照 T024/T040/T041/T043/T044/T045/T051/T052/T053/T054 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线）：api.ts 的三类 JobKind 与 startJob 正文（S01）；jobStore 的
  KINDS、useBusyRuntime 与既有公式（S02）；JobCard 的三张表与既有字面（S03）；桩的新夹具与扫描一路
  不改（S04）；RuntimesView 的换入口与其余一字不改（S05）；RuntimeProbe.tsx 与 runtime-probe.css
  （S06）；RuntimeModels.tsx 与 runtime-models.css（S07）；执行端三份新测试文件在位且要点齐备（S08）；
  兼容性一节的旧断言逐处改到位（S09）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、
  npm test 全绿；三份探针逐份写成 ``gate-probe/probe-<uid>-t055-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除。探针直接渲染 ``RuntimesView``
  （照包内 page-runtimes.test.tsx 的既有写法注入 runtimes 与 quizs，不 mock 被测组件），真实模式用
  ``setLiveClientForTests`` 注入假服务记录作业请求；等轮询用真实计时器 ``sleep``（不用假计时器，
  钉「没有作业时不排计时器」的那一条用假计时器数挂起的计时器）。每份探针自带全部辅助函数。
  - probe（真实模式）：点 [探测] 的创建正文与标题、进度与每秒查询、成功结果（版本/来源/命令/缺少的
    参数/思考级别）、ok 为假的 failed（结果块照旧 + 点明没过的项）、没有 data 的 failed（只显内核
    原文）、timed_out 150 与重新探测、取消、创建失败 400、忙于别的行（禁用与悬停「正在探测 pi」）、
    本行重开（同一作业、关着时照查）、没有作业时没有计时器。
  - models（真实模式）：点 [模型] 的创建正文与标题、三列表与「是 / 否 / 不限制」与 <redacted>、
    说明句、空数组「没有列出模型」、timed_out 120、两个 pi 行的同类互斥（悬停「正在列 pi 的模型」）。
  - stub（桩模式，不注入客户端）：startJob 缺 runtime 回 400；data 开关下探测奇偶两份（ok 为假带
    data 并点明、[重新探测] 后正常）、非 pi 行的探测、列模型四行含一行「否」与 <redacted>；loading
    一直 running 且取消落「已取消」；error 落 failed 不显示结果块。

门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：见文件末尾 ``ASSUMPTIONS``。
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
WEB = REPO_ROOT / "desktop" / "web"
WEB_REL = "desktop/web"
SRC_REL = f"{WEB_REL}/src"
WRITES_REL = f"{SRC_REL}/writes"
JOBS_REL = f"{SRC_REL}/jobs"
TESTS_REL = f"{WEB_REL}/tests"

API_REL = f"{SRC_REL}/api.ts"
JOBSTORE_REL = f"{JOBS_REL}/jobStore.ts"
JOBCARD_REL = f"{JOBS_REL}/JobCard.tsx"
JOBCARD_CSS_REL = f"{JOBS_REL}/job-card.css"
MOCKJOBS_REL = f"{SRC_REL}/mock/jobs.ts"
RUNTIMESVIEW_REL = f"{SRC_REL}/pages/readonly1/runtimes-RuntimesView.tsx"
RUNTIMEPROBE_REL = f"{WRITES_REL}/RuntimeProbe.tsx"
RUNTIMEPROBE_CSS_REL = f"{WRITES_REL}/runtime-probe.css"
RUNTIMEMODELS_REL = f"{WRITES_REL}/RuntimeModels.tsx"
RUNTIMEMODELS_CSS_REL = f"{WRITES_REL}/runtime-models.css"
TRANSPORT_REL = f"{SRC_REL}/live/transport.ts"
MODE_REL = f"{SRC_REL}/live/mode.ts"

STORE_TEST_REL = f"{TESTS_REL}/jobs-store-runtime.test.ts"
PROBE_PAGE_TEST_REL = f"{TESTS_REL}/jobs-probe-page.test.tsx"
MODELS_PAGE_TEST_REL = f"{TESTS_REL}/jobs-models-page.test.tsx"

T009_GATE_REL = "tests/test_gate_t009_baseline.py"
T023_GATE_REL = "tests/test_gate_t023_baseline.py"
T045_GATE_REL = "tests/test_gate_t045_baseline.py"
T054_GATE_REL = "tests/test_gate_t054_baseline.py"
PAGE_APP_TEST_REL = f"{TESTS_REL}/page-app.test.tsx"
PAGE_RUNTIMES_TEST_REL = f"{TESTS_REL}/page-runtimes.test.tsx"

# 逐字记号（合同 Behavior contract 与「写法钉死」一节，逐字照抄）
JOBKIND_THREE = "export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';"
JOB_STATES = ("queued", "running", "succeeded", "failed", "cancelled", "timed_out")
JOBVIEW_KEYS = ("id", "kind", "state", "reason", "created_ms", "started_ms", "finished_ms", "envelope")

LABEL_PROBE = "探测"
LABEL_MODELS = "模型"
BUTTON_REPROBE = "重新探测"
BUTTON_RELIST = "重新列出"
BUTTON_CLOSE = "关闭"
BUTTON_CANCEL = "取消"
MSG_CANCELLED = "已取消"
MSG_PROBE_FAILED = "探测失败"
MSG_MODELS_FAILED = "列模型失败"
MSG_SCAN_FAILED = "扫描失败"
ARIA_PROBE = "探测进行中"
ARIA_MODELS = "列模型进行中"
ARIA_SCAN = "扫描进行中"
REASON_PROBE_PREFIX = "正在探测 "
REASON_MODELS_PREFIX = "正在列 "
REASON_MODELS_SUFFIX = " 的模型"
MSG_VERSION_UNKNOWN = "版本未知"
MSG_MISSING_NONE = "无"
RESULT_LABEL_VERSION = "版本"
RESULT_LABEL_SOURCE = "命令来源"
RESULT_LABEL_COMMAND = "命令"
RESULT_LABEL_MISSING = "缺少的参数"
RESULT_LABEL_THINKING = "思考级别"
SOURCE_ENV = "环境变量"
SOURCE_LOCAL = "本机文件"
SOURCE_PATH = "PATH"
SOURCE_MISSING = "找不到"
DASH = "—"
FAIL_VERSION_EXIT = "版本命令退出码"
FAIL_HELP_EXIT = "--help 退出码"
FAIL_PI_MISSING = "pi 缺少参数："
MODELS_NOTE = "模型列表来自 pi --list-models，不调用模型"
MODELS_HEADERS = ("provider", "model", "是否在允许列表")
MODELS_YES = "是"
MODELS_NO = "否"
MODELS_ANY = "不限制"
MODELS_REDACTED = "<redacted>"
MODELS_EMPTY = "没有列出模型"
TIMEOUT_PROBE_TEXT = "超时（超过 150 秒），已停止"
TIMEOUT_MODELS_TEXT = "超时（超过 120 秒），已停止"
# 桩的夹具记号（合同桩一节）
MOCK_NO_CONTEXT = "--no-context-files"
MOCK_THINKING_XHIGH = "xhigh"
MOCK_ALLOWED_SET = "allowed_executors_set"
MOCK_SCAN_ERROR_MESSAGE = "ERROR 扫描失败：内核报错（示意）"
MOCK_CANCEL_409 = "作业已经结束"
MOCK_404 = "没有这个作业"
MOCK_SCAN_PATHS = (
    ("pi", "C:/tools/pi/pi.exe", "0.1.2"),
    ("claude-code", "C:/tools/npm/claude.cmd", "1.0.9"),
    ("codex", "C:/tools/codex/codex.exe", "0.5.0"),
)

# 执行端新测试文件的最小覆盖记号（合同第 10 步点名的覆盖点）
EXECUTOR_TEST_TOKENS = {
    STORE_TEST_REL: ("resetJobStoreForTests", "ensureJob", "restartJob", "runtime-probe", "claude-code"),
    PROBE_PAGE_TEST_REL: ("setLiveClientForTests", "runtime-probe", "探测", "取消", "版本未知"),
    MODELS_PAGE_TEST_REL: ("setLiveClientForTests", "models", "模型", "重新列出", "120"),
}

# 新源码的禁词（与 T054 门禁同一口径；t010 禁词由调度器范围之外的既有门禁管）
FORBIDDEN_SOURCE_MARKS = (
    "XMLHttpRequest", "EventSource", "WebSocket", "dangerouslySetInnerHTML", "innerHTML", "outerHTML",
    "insertAdjacentHTML", "eval(", "new Function", "document.write", "srcdoc", "DOMParser",
    "matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver", 'role="status"',
)
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_COLOR_FUNCS = ("rgb(", "rgba(", "hsl(", "hsla(", "color-mix(", "oklch(", "lab(", "hwb(")

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T024/T041/T043/T044/T045/T051/T052/T053/T054 门禁）
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 150}

ASSUMPTIONS = (
    "两个新入口组件的导出名与 props 形状合同没有钉：静态只钉 import 路径（'../../writes/RuntimeProbe' 与"
    " '../../writes/RuntimeModels'）与文件内的记号；探针按渲染 RuntimesView 的行为断言（按钮文字、禁用、"
    "创建正文、对话框标题与结果块）",
    "「没有作业时不排计时器」静态不钉写法（实现自由），由 stub 探针用假计时器数挂起计时器（应为 0）行为断言",
    "三张按 kind 的表的形状不钉：失败标题、aria-label 与超时秒数（150/150/120）按字面与「'runtime-probe': 150」"
    "一类整句记号钉，JobCard 内部怎么组织表不管",
    "探测结果块的行标签按「版本 / 命令来源 / 命令 / 缺少的参数 / 思考级别」断言（合同点名的措辞），行的次序不钉",
    "no-data 的 failed「不显示结果块」按对话框文本不含「版本未知」与不含 failedDetail 的字样断言（结果块与"
    " failedDetail 只在有 data 时出现）",
    "mock 的 error 开关对两类新 kind 的示意原文措辞不钉（扫描那一行被 t054 钉死，新 kind 的一行示意由执行端定），"
    " stub 探针只断言落 failed 且不显示结果块",
    "缺 runtime 回 400 的静态记号不钉写法，由 stub 探针直接调 api.startJob('runtime-probe') 断言回 400",
    "流水线预算 580 秒（G01 的 600 秒减去静态用例与 pytest 自身开销）：node_modules 已在（执行端 Setup 装过）"
    "就不重装；npm ci 只在依赖不齐时跑",
)


# ---------------------------------------------------------------------------
# 通用小工具（只读仓库文件；模块级不做任何仓库 IO）
# ---------------------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def read_rel(rel):
    return _read(REPO_ROOT / rel)


def need_file(rel):
    """断言仓库里的文件存在，返回相对路径。基线上到这里就以断言失败。"""
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return rel


def file_digest(path):
    path = Path(path)
    if not path.is_file():
        return None
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return len(data), hashlib.sha256(data).hexdigest()


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:40])


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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043/T044/T045/T051/T052/T053/T054 的同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def module_func(code, signature):
    """取模块级函数体：从签名的起点到下一个列首的 ``}``（CRLF 已归一）。找不到给 None。"""
    start = code.find(signature)
    if start < 0:
        return None
    end = code.find("\n}", start)
    if end < 0:
        return None
    return code[start:end + 2]


def _no_skip_marks(text):
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
        if re.search(bad, text):
            problems.append(f"出现 {bad}（不许 skip、only、todo）")
    return problems


def _forbidden_marks(rel, text, code):
    """禁词、写死颜色与内联样式的公共核对（T054 等门禁的口径）。"""
    problems = []
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"{rel} 不应出现 {bad}")
    if _HEX_COLOR.search(code) or any(fn in code for fn in _COLOR_FUNCS):
        problems.append(f"{rel} 不应写死颜色")
    if "style={{" in code:
        problems.append(f"{rel} 不应写内联 style")
    return problems


def _css_imports(text):
    return re.findall(r"import\s+['\"]([^'\"]+\.css)['\"]", text)


def _css_px_problems(rel, css):
    """新 CSS：除 0 与 1px 外的 px 字面量同一行要带出处注释（合同入口一节）。"""
    problems = []
    for i, line in enumerate(css.split("\n"), 1):
        if "/*" in line:
            continue
        for m in re.finditer(r"(\d+(?:\.\d+)?)px", line):
            if m.group(1) not in ("0", "1"):
                problems.append(f"{rel}:{i} 的 {m.group(0)} 应在同一行带出处注释（除 0 与 1px 外的 px 字面量）")
    return problems


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 T044/T045/T051/T052/T053/T054 门禁的写法）
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
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    start = time.monotonic()
    proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
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


def git_status_set():
    proc = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
                          cwd=REPO_ROOT, capture_output=True, timeout=120)
    assert proc.returncode == 0, f"git status 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


def t055_marker_present():
    """候选里是否已有 T055 的标记（新入口文件 + jobStore 的 useBusyRuntime + api 的三类 JobKind）：
    没有就不起 npm（基线上必然没有）。"""
    try:
        probe = _read(REPO_ROOT / RUNTIMEPROBE_REL) if (REPO_ROOT / RUNTIMEPROBE_REL).is_file() else ""
        models = _read(REPO_ROOT / RUNTIMEMODELS_REL) if (REPO_ROOT / RUNTIMEMODELS_REL).is_file() else ""
        store = _read(REPO_ROOT / JOBSTORE_REL) if (REPO_ROOT / JOBSTORE_REL).is_file() else ""
        api = _read(REPO_ROOT / API_REL) if (REPO_ROOT / API_REL).is_file() else ""
    except OSError:
        return False
    return (LABEL_PROBE in probe and LABEL_MODELS in models
            and "useBusyRuntime" in store and "'runtime-probe'" in api)


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t055_marker_present():
        pipe.reason = ("候选里还没有 T055 的标记（src/writes/RuntimeProbe.tsx / RuntimeModels.tsx、jobStore 的 "
                       "useBusyRuntime、api.ts 的 'runtime-probe'），没有东西可测，未调用 npm；候选把入口与接线"
                       "都放进去之后，流水线才会运行 npm ci、Vitest 与探针")
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
        # 依赖已在（执行端 Setup 装过）就不重装：省下的时间留给 Vitest 与探针。
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
            if pipe.steps.get("npm test") is not None and pipe.steps["npm test"].code == 0:
                uid = uuid.uuid4().hex[:12]
                for key in PROBE_ORDER:
                    missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                    if missing:
                        pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                        continue
                    name = f"probe-{uid}-t055-{key}.test.tsx"
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


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线；上面是会话级夹具，静态用例不碰它）
# ---------------------------------------------------------------------------

def test_s01_api_jobs():
    """S01 / D01、D05：api.ts——JobKind 逐字三类；startJob(kind, runtime?)：扫描支正文逐字 { kind }、
    两类新作业正文逐字 { kind, runtime }；201 才算建成；时限 15 的字面量在函数体里；桩分支
    mockStartJob(kind, runtime)；getJob / cancelJob 照旧在位；JobState 六值与 JobView 八键照旧。"""
    need_file(API_REL)
    api = read_rel(API_REL)
    code = strip_ts_comments(api)
    problems = []
    if JOBKIND_THREE not in code:
        problems.append(f"api.ts 应有逐字 {JOBKIND_THREE}")
    sm = re.search(r"export type JobState = ([^;]+);", code)
    if sm is None:
        problems.append("api.ts 应有 export type JobState = …")
    else:
        for state in JOB_STATES:
            if f"'{state}'" not in sm.group(1):
                problems.append(f"JobState 应含 '{state}'")
    vm = re.search(r"export interface JobView \{(.*?)\n\}", code, re.S)
    if vm is None:
        problems.append("api.ts 应有 export interface JobView {…}")
    else:
        for key in JOBVIEW_KEYS:
            if not re.search(rf"\b{key}\s*[?:]", vm.group(1)):
                problems.append(f"JobView 应有八键里的 '{key}'")
    start = module_func(code, "export function startJob(")
    if start is None:
        problems.append("api.ts 应有 export function startJob(kind: JobKind, runtime?: string)")
    else:
        if not re.search(r"export function startJob\(kind: JobKind, runtime\?: string\)", start):
            problems.append("startJob 的签名应是 (kind: JobKind, runtime?: string)")
        for mark in ("postRaw", "{ kind }", "{ kind, runtime }", "mockStartJob(kind, runtime)"):
            if mark not in start:
                problems.append(f"startJob 的函数体里应有 {mark}")
        if "reply.status === 201" not in start:
            problems.append("startJob 应 201 才算建成")
        if re.search(r"\b15\b", start) is None:
            problems.append("startJob 的时限应是 15 秒（函数体里的字面量）")
        for bad in ("runtime: undefined",):
            if bad in start:
                problems.append(f"startJob 的正文里不许出现 {bad}（服务键恰好校验会回 400）")
    for name in ("getJob", "cancelJob"):
        if f"export function {name}(" not in code:
            problems.append(f"api.ts 的 export function {name}( 应照旧在位")
    problems.extend(_forbidden_marks("api.ts", api, code))
    fail_if(problems, "api.ts 的作业接线（S01）")


def test_s02_job_store():
    """S02 / D04、D05：jobStore.ts——KINDS 三类；StoreState 加 runtime: string | null；既有五个导出
    （ensureJob / restartJob / cancelJob / useJob / resetJobStoreForTests）都在且带可选 runtime 参数；
    新增 export function useBusyRuntime(kind)；轮询公式与 T054 的字面照旧（setTimeout 链、1000、
    clearTimeout、已用秒数公式、useSyncExternalStore、从 '../api' 引三个作业函数）。"""
    need_file(JOBSTORE_REL)
    text = read_rel(JOBSTORE_REL)
    code = strip_ts_comments(text)
    problems = []
    if not re.search(r"KINDS[^=]*=\s*\[[^\]]*'runtime-scan'[^\]]*'runtime-probe'[^\]]*'models'[^\]]*\]", code):
        problems.append("KINDS 应扩成三类 ['runtime-scan', 'runtime-probe', 'models']")
    if "runtime: string | null" not in code:
        problems.append("槽的形状应加 runtime: string | null（槽里那个作业是哪个 runtime 的）")
    for name in ("ensureJob", "restartJob", "cancelJob", "useJob", "resetJobStoreForTests"):
        if f"export function {name}(" not in code:
            problems.append(f"应导出 export function {name}(")
    if "export function useBusyRuntime(" not in code:
        problems.append("应新增 export function useBusyRuntime(kind)")
    for sig in (r"export function ensureJob\(kind: JobKind, runtime\?: string\)",
                r"export function restartJob\(kind: JobKind, runtime\?: string\)",
                r"export function useJob\(kind: JobKind, runtime\?: string\)",
                r"export function cancelJob\(kind: JobKind\)",
                r"export function useBusyRuntime\(kind: JobKind\)"):
        if re.search(sig, code) is None:
            problems.append(f"签名应照合同：{sig}")
    if "JobKind" not in code:
        problems.append("kind 的类型应是 api.ts 的 JobKind")
    if "from '../api'" not in text:
        problems.append("应从 '../api' 引作业函数")
    else:
        for call in ("startJob(", "getJob(", "cancelJob("):
            if call not in code:
                problems.append(f"应调用 api.ts 的 {call}…）")
    if "setTimeout(" not in code:
        problems.append("轮询应走 setTimeout 链（每 1000 毫秒一次）")
    if "setInterval(" in code:
        problems.append("轮询不该用 setInterval（合同写明 setTimeout 链）")
    if not re.search(r"\b1000\b", code):
        problems.append("轮询间隔应是 1000 毫秒")
    if "clearTimeout" not in code:
        problems.append("卸载时应 clearTimeout（不留悬挂计时器）")
    if not re.search(r"Math\.floor\(\s*\(\s*Date\.now\(\)\s*-\s*t0\s*\)\s*/\s*1000\s*\)", code):
        problems.append("已用秒数应按 Math.floor((Date.now() - t0) / 1000) 算")
    if "useSyncExternalStore" not in code:
        problems.append("useJob 应用 useSyncExternalStore 订阅模块状态")
    problems.extend(_forbidden_marks("jobStore.ts", text, code))
    fail_if(problems, "jobStore.ts 的写法钉死（S02）")


def test_s03_job_card():
    """S03 / D06：JobCard.tsx——props 加可选 kind（缺省 'runtime-scan'）与 failedDetail；三张按 kind 的
    表都在 JobCard.tsx 里（失败标题 扫描失败/探测失败/列模型失败、进度条 aria-label
    扫描进行中/探测进行中/列模型进行中、超时 150/150/120）；扫描那一支的字面与 'runtime-scan': 150
    的时限表留在文件里；既有 props（title / onCancel / children）与结局文字照旧；只引 job-card.css。"""
    need_file(JOBCARD_REL)
    text = read_rel(JOBCARD_REL)
    code = strip_ts_comments(text)
    problems = []
    if "export function JobCard(" not in code:
        problems.append("应导出 export function JobCard(")
    for token in ("title", "onCancel", "children", "kind", "failedDetail"):
        if not re.search(rf"\b{token}\??\s*:", code):
            problems.append(f"JobCard 的 props 应能看到 {token}")
    if not re.search(r"kind\b[^=\n]*=\s*'runtime-scan'", code):
        problems.append("kind 应是可选属性，缺省 'runtime-scan'（RuntimeScan.tsx 一个字不改照样过）")
    for mark, what in ((MSG_SCAN_FAILED, "runtime-scan 失败标题"), (MSG_PROBE_FAILED, "runtime-probe 失败标题"),
                       (MSG_MODELS_FAILED, "models 失败标题"), (ARIA_SCAN, "runtime-scan 进度 aria-label"),
                       (ARIA_PROBE, "runtime-probe 进度 aria-label"), (ARIA_MODELS, "models 进度 aria-label")):
        if mark not in code:
            problems.append(f"三张表里 {what} 应逐字在位：{mark}")
    if not re.search(r"['\"]?runtime-scan['\"]?\s*:\s*150", code):
        problems.append("时限表里应有 'runtime-scan': 150")
    if not re.search(r"['\"]?runtime-probe['\"]?\s*:\s*150", code):
        problems.append("时限表里应有 'runtime-probe': 150")
    if not re.search(r"['\"]?models['\"]?\s*:\s*120", code):
        problems.append("时限表里应有 'models': 120")
    for mark, what in ((MSG_CANCELLED, "cancelled 结局"), (BUTTON_CANCEL, "[取消] 按钮")):
        if mark not in code:
            problems.append(f"{what}的文案应逐字在位：{mark}")
    if not re.search(r"超时（超过 \$\{", code):
        problems.append("timed_out 结局应是「超时（超过 ${…} 秒），已停止」的模板")
    if not re.search(r"已用 \$\{", code):
        problems.append("运行中应显示「已用 ${…} 秒」")
    if 'role="progressbar"' not in code:
        problems.append('运行中应渲染一条不确定进度条（role="progressbar"）')
    css_imports = _css_imports(text)
    if "./job-card.css" not in css_imports:
        problems.append("JobCard.tsx 应 import './job-card.css'（组件带自己的样式表，唯一接线处）")
    for other in css_imports:
        if other != "./job-card.css":
            problems.append(f"JobCard.tsx 不应引别的样式表（{other}；job-card.css 由本组件引）")
    problems.extend(_forbidden_marks("JobCard.tsx", text, code))
    need_file(JOBCARD_CSS_REL)
    fail_if(problems, "JobCard.tsx 的写法钉死（S03）")


def test_s04_mock_jobs():
    """S04 / D08：桩 mock/jobs.ts——扫描那一支一字不改（夹具 path/version、错误一行、409/404 文案、
    found/added、不用计时器、不引 JSON 照旧）；两类新 kind 在位：探测夹具的 ok 为假/为真两份与
    --no-context-files、thinking_levels（xhigh 一类记号）、version_exit_code；非 pi 的正常结果（1.0.9）；
    列模型夹具的四行形状记号（allowed_executors_set、<redacted>、allowed: false）。"""
    need_file(MOCKJOBS_REL)
    text = read_rel(MOCKJOBS_REL)
    code = strip_ts_comments(text)
    problems = []
    for name in ("mockStartJob", "mockGetJob", "mockCancelJob"):
        if f"export function {name}(" not in code:
            problems.append(f"应导出 export function {name}(")
    start = module_func(code, "export function mockStartJob(")
    if start is None:
        problems.append("应有 export function mockStartJob(")
    elif "runtime" not in start or "400" not in start:
        problems.append("mockStartJob 应接受 runtime 参数，缺 runtime 的新 kind 回 400")
    if "setTimeout(" in code or "setInterval(" in code:
        problems.append("桩不用计时器：每次调用都回已兑现的 Promise")
    if "WriteScenario" in text:
        problems.append("mock/jobs.ts 不许出现 WriteScenario（不加写情景值）")
    if re.search(r"from ['\"][^'\"]*\.json['\"]", text):
        problems.append("src/mock 不加 JSON（mock/jobs.ts 不引 .json）")
    for token in ("'runtime-scan'", "'runtime-probe'", "'models'", "'running'", "'succeeded'", "'failed'",
                  "'cancelled'", "'queued'"):
        if token not in code:
            problems.append(f"桩里应有 kind / 状态记号：{token}")
    for mark, what in ((MOCK_SCAN_ERROR_MESSAGE, "error 开关的失败信封一行"),
                       (MOCK_CANCEL_409, "取消已终态的 409 文案"), (MOCK_404, "查不到的 404 文案")):
        if mark not in text:
            problems.append(f"{what}应逐字在位：{mark}")
    for adapter, path, version in MOCK_SCAN_PATHS:
        if path not in text:
            problems.append(f"扫描夹具里 {adapter} 的 path 应逐字 {path}")
        if version not in text:
            problems.append(f"扫描夹具里 {adapter} 的 version 应逐字 {version}")
    if "found" not in code or "added" not in code:
        problems.append("succeeded 的扫描 data 应照服务的形状 { found: […], added: [] }")
    for adapter in ("opencode", "quizs"):
        if f"'{adapter}'" not in code:
            problems.append(f"扫描夹具应含五个适配器里的 '{adapter}'")
    # --- 两类新作业的夹具 ---
    for mark, what in (("ok: false", "探测夹具奇数份（ok 为假）"), ("ok: true", "探测夹具偶数份（ok 为真）"),
                       (MOCK_NO_CONTEXT, "探测夹具缺的参数 --no-context-files"),
                       ("thinking_levels", "探测夹具的 thinking_levels"),
                       ("missing_flags", "探测夹具的 missing_flags"),
                       ("version_exit_code", "探测夹具的 version_exit_code"),
                       (MOCK_THINKING_XHIGH, "思考级别表里的 xhigh"),
                       ("'0.1.2'", "pi 正常探测的版本 0.1.2"), ("'1.0.9'", "非 pi 正常探测的版本 1.0.9")):
        if mark not in code:
            problems.append(f"桩的探测夹具应有 {what}：{mark}")
    if "help" not in code:
        problems.append("探测夹具的 pi 份应带 help（missing_flags / thinking_levels）")
    for mark, what in ((MOCK_ALLOWED_SET, "列模型夹具的 allowed_executors_set"),
                       (MODELS_REDACTED, "列模型夹具的 <redacted> 行"), ("allowed: false", "列模型夹具一行 allowed:false"),
                       ("allowed: true", "列模型夹具的 allowed:true 行"), ("provider", "列模型夹具的 provider"),
                       ("model", "列模型夹具的 model")):
        if mark not in code:
            problems.append(f"桩的列模型夹具应有 {what}：{mark}")
    problems.extend(_forbidden_marks("mock/jobs.ts", text, code))
    fail_if(problems, "mock/jobs.ts 的写法钉死（S04）")


def test_s05_runtimes_view():
    """S05 / D01、D07：runtimes-RuntimesView.tsx——两处 <DisabledAction label="探测" / "模型"> 换成
    新入口组件（import 自 '../../writes/RuntimeProbe' 与 '../../writes/RuntimeModels'）；canProbe /
    canModels 规则照旧（runtimes-logic.ts 一字不改）；其余一字不改（runtime.remove、args、reload、
    useWriteFlow、[运行就绪检查] 仍禁用、两节标题、版本列照旧「—」）。"""
    need_file(RUNTIMESVIEW_REL)
    text = read_rel(RUNTIMESVIEW_REL)
    code = strip_ts_comments(text)
    problems = []
    for label in ("探测", "模型"):
        if re.search(rf"<DisabledAction[^>]*label=\"{label}\"", code):
            problems.append(f"<DisabledAction label=\"{label}\" /> 不应再在（换成新入口组件）")
    for path_lit in ("'../../writes/RuntimeProbe'", "'../../writes/RuntimeModels'"):
        if path_lit not in text:
            problems.append(f"应引入 {path_lit}")
    for mark, what in (("'runtime.remove'", "删除走既有 runtime.remove"),
                       ("args: { runtime", "删除的 args 带 runtime"),
                       ("reload?:", "reload 可选属性"), ("useWriteFlow(", "useWriteFlow"),
                       ("canProbe(", "canProbe 规则照旧"), ("canModels(", "canModels 规则照旧"),
                       ('label="运行就绪检查"', "[运行就绪检查] 仍禁用"),
                       ('"已登记"', "已登记一节标题"), ('"就绪检查"', "就绪检查一节标题"),
                       ("版本: '—'", "版本列照旧「—」")):
        if mark not in code:
            problems.append(f"其余一字不改：{what}（{mark[:40]}）")
    problems.extend(_forbidden_marks("runtimes-RuntimesView.tsx", text, code))
    fail_if(problems, "RuntimesView 的换入口（S05）")


def test_s06_runtime_probe_file():
    """S06 / D01、D02、D04：RuntimeProbe.tsx 与 runtime-probe.css——行内入口与对话框照 T054 的内外两层
    （{open && <内层/>}）；作业调用走 jobStore（ensureJob / restartJob / useJob 带 runtime）+ useBusyRuntime；
    JobCard 从 '../jobs/JobCard' 直接引且 kind="runtime-probe"；按钮文字逐字「探测」（ghost/sm）；忙于别的
    行时 DisabledAction 带 reason「正在探测 …」；对话框标题「探测 <id>」；脚注 [重新探测] 与 [关闭]；
    结果块的逐字文案（版本未知、四个来源标签、—、缺少的参数、思考级别、无）与没过项的三行措辞；
    只引 runtime-probe.css；不用禁词、不写死颜色、不写内联 style。"""
    need_file(RUNTIMEPROBE_REL)
    text = read_rel(RUNTIMEPROBE_REL)
    code = strip_ts_comments(text)
    problems = []
    if not re.search(r"\{open && <", code):
        problems.append("对话框应只在打开时挂载（{open && <内层/>}）")
    for mark, what in (("ensureJob(", "ensureJob"), ("restartJob(", "restartJob"), ("useJob(", "useJob"),
                       ("useBusyRuntime(", "useBusyRuntime（行内入口订阅也算订阅者）")):
        if mark not in code:
            problems.append(f"应调 jobStore 的 {what}")
    if "'runtime-probe'" not in code:
        problems.append("作业 kind 应是 'runtime-probe'")
    if "JobCard" not in code:
        problems.append("对话框 body 里应放 JobCard")
    elif "from '../jobs/JobCard'" not in text:
        problems.append("JobCard 应从 '../jobs/JobCard' 直接引入（不进 components/index.ts）")
    if 'kind="runtime-probe"' not in code:
        problems.append('JobCard 应带 kind="runtime-probe"')
    if 'variant="ghost"' not in code:
        problems.append('入口按钮应写 variant="ghost"（照旧那两处 DisabledAction 的口径）')
    if 'size="sm"' not in code:
        problems.append('入口按钮应写 size="sm"')
    if "DisabledAction" not in code:
        problems.append("忙于别的行时应渲染 DisabledAction")
    for mark, what in ((REASON_PROBE_PREFIX, "忙于别的行的 reason 前缀「正在探测 」"),
                       (BUTTON_REPROBE, "脚注 [重新探测]"), (BUTTON_CLOSE, "脚注 [关闭]"),
                       ("探测 ", "对话框标题「探测 <id>」的措辞（模板或拼接都可）"),
                       (MSG_VERSION_UNKNOWN, "版本未知"), (SOURCE_ENV, "来源标签 环境变量"),
                       (SOURCE_LOCAL, "来源标签 本机文件"), (SOURCE_PATH, "来源标签 PATH"),
                       (SOURCE_MISSING, "来源标签 找不到"),
                       (RESULT_LABEL_VERSION, "结果块行标签 版本"), (RESULT_LABEL_SOURCE, "结果块行标签 命令来源"),
                       (RESULT_LABEL_COMMAND, "结果块行标签 命令"),
                       (RESULT_LABEL_MISSING, "pi 行 缺少的参数"), (RESULT_LABEL_THINKING, "pi 行 思考级别"),
                       (FAIL_VERSION_EXIT, "没过项「版本命令退出码 <N>」"), (FAIL_HELP_EXIT, "没过项「--help 退出码 <N>」"),
                       (FAIL_PI_MISSING, "没过项「pi 缺少参数：…」")):
        if mark not in code:
            problems.append(f"{what}应逐字在位：{mark}")
    if "failedDetail" not in code:
        problems.append("没过项应经 failedDetail 传给作业卡（放在内核报错原文之前）")
    css_imports = _css_imports(text)
    if "./runtime-probe.css" not in css_imports:
        problems.append("应 import './runtime-probe.css'")
    for other in css_imports:
        if other != "./runtime-probe.css":
            problems.append(f"不应引别的样式表（{other}；本文件只引 runtime-probe.css）")
    problems.extend(_forbidden_marks("RuntimeProbe.tsx", text, code))
    need_file(RUNTIMEPROBE_CSS_REL)
    css = read_rel(RUNTIMEPROBE_CSS_REL)
    css_problems = _forbidden_marks("runtime-probe.css", css, css)
    css_problems.extend(_css_px_problems("runtime-probe.css", css))
    fail_if(problems, "RuntimeProbe.tsx 的写法钉死（S06）")
    fail_if(css_problems, "runtime-probe.css 的写法钉死（S06）")


def test_s07_runtime_models_file():
    """S07 / D01、D03、D04：RuntimeModels.tsx 与 runtime-models.css——同一套内外两层与作业接线
    （kind="models"）；按钮文字逐字「模型」（ghost/sm）；忙于别的行时 DisabledAction 带 reason
    「正在列 … 的模型」；对话框标题「模型 <id>」；脚注 [重新列出] 与 [关闭]；说明句、三列列头、
    是/否/不限制、<redacted>、空数组的「没有列出模型」；只引 runtime-models.css。"""
    need_file(RUNTIMEMODELS_REL)
    text = read_rel(RUNTIMEMODELS_REL)
    code = strip_ts_comments(text)
    problems = []
    if not re.search(r"\{open && <", code):
        problems.append("对话框应只在打开时挂载（{open && <内层/>}）")
    for mark, what in (("ensureJob(", "ensureJob"), ("restartJob(", "restartJob"), ("useJob(", "useJob"),
                       ("useBusyRuntime(", "useBusyRuntime（行内入口订阅也算订阅者）")):
        if mark not in code:
            problems.append(f"应调 jobStore 的 {what}")
    if "'models'" not in code:
        problems.append("作业 kind 应是 'models'")
    if "JobCard" not in code:
        problems.append("对话框 body 里应放 JobCard")
    elif "from '../jobs/JobCard'" not in text:
        problems.append("JobCard 应从 '../jobs/JobCard' 直接引入（不进 components/index.ts）")
    if 'kind="models"' not in code:
        problems.append('JobCard 应带 kind="models"')
    if 'variant="ghost"' not in code:
        problems.append('入口按钮应写 variant="ghost"（照旧那两处 DisabledAction 的口径）')
    if 'size="sm"' not in code:
        problems.append('入口按钮应写 size="sm"')
    if "DisabledAction" not in code:
        problems.append("忙于别的行时应渲染 DisabledAction")
    for mark, what in ((REASON_MODELS_PREFIX, "忙于别的行的 reason 前缀「正在列 」"),
                       (REASON_MODELS_SUFFIX, "忙于别的行的 reason 后缀「 的模型」"),
                       (BUTTON_RELIST, "脚注 [重新列出]"), (BUTTON_CLOSE, "脚注 [关闭]"),
                       ("模型 ", "对话框标题「模型 <id>」的措辞（模板或拼接都可）"),
                       (MODELS_NOTE, "表上方说明句"), (MODELS_HEADERS[0], "列头 provider"),
                       (MODELS_HEADERS[1], "列头 model"), (MODELS_HEADERS[2], "列头 是否在允许列表"),
                       (f"'{MODELS_YES}'", "allowed:true 写「是」"), (f"'{MODELS_NO}'", "allowed:false 写「否」"),
                       (f"'{MODELS_ANY}'", "allowed:null 写「不限制」"),
                       (MODELS_REDACTED, "<redacted> 原样显示"), (MODELS_EMPTY, "空数组「没有列出模型」")):
        if mark not in code:
            problems.append(f"{what}应逐字在位：{mark}")
    css_imports = _css_imports(text)
    if "./runtime-models.css" not in css_imports:
        problems.append("应 import './runtime-models.css'")
    for other in css_imports:
        if other != "./runtime-models.css":
            problems.append(f"不应引别的样式表（{other}；本文件只引 runtime-models.css）")
    problems.extend(_forbidden_marks("RuntimeModels.tsx", text, code))
    need_file(RUNTIMEMODELS_CSS_REL)
    css = read_rel(RUNTIMEMODELS_CSS_REL)
    css_problems = _forbidden_marks("runtime-models.css", css, css)
    css_problems.extend(_css_px_problems("runtime-models.css", css))
    fail_if(problems, "RuntimeModels.tsx 的写法钉死（S07）")
    fail_if(css_problems, "runtime-models.css 的写法钉死（S07）")


def test_s08_executor_test_files():
    """S08 / D09：执行端三份新测试文件在位且要点齐备（合同第 10 步点名的覆盖点），不许 skip/only/todo。"""
    problems = []
    for rel, tokens in EXECUTOR_TEST_TOKENS.items():
        try:
            need_file(rel)
            text = read_rel(rel)
        except AssertionError as exc:
            problems.append(str(exc))
            continue
        for token in tokens:
            if token not in text:
                problems.append(f"{rel} 应覆盖到 {token}")
        problems.extend(f"{rel}: {p}" for p in _no_skip_marks(text))
    fail_if(problems, "执行端新测试文件（S08）")


def test_s09_legacy_assertions_updated():
    """S09 / D10：兼容性一节的旧断言逐处改到位——t023（:297-298 加 not、:783 标题、:793 toBe(false)）、
    t009（:2854 标题、:2861 toBe(false)、「应可点」、:2970 标题加尾段、:2974 白名单加「探测」「模型」）、
    t045（:560/:563 运行时页 4→1）、t054（:717 三类的逐字记号）、包内 page-app（运行时页 1、toBe(1)）与
    page-runtimes（:101 标题、:109 toBe(false)）；旧口径不再残留在这些文件里。"""
    problems = []
    # t023：两处 DisabledAction 断言改成 not；it 标题「行内其余按钮也可点」；:793 toBe(false)
    t023 = read_rel(T023_GATE_REL)
    for label in ("探测", "模型"):
        if f'not re.search(r\'<DisabledAction label="{label}"\'' not in t023:
            problems.append(f't023 :297-298 应加 not（<DisabledAction label="{label}" 不应再是）')
    if "行内其余按钮也可点" not in t023:
        problems.append("t023 :783 的 it 标题应改成「行内其余按钮也可点」")
    if "非 [删除…] 的行内按钮也可点（" not in t023 or ".toBe(false);" not in t023:
        problems.append("t023 :793 应改成 toBe(false)，提示语「行内按钮也可点」")
    # t009：:2854 标题、:2861 toBe(false) 与「应可点」、:2970 标题尾段、:2974 白名单
    t009 = read_rel(T009_GATE_REL)
    if "[探测]、[模型] 可点" not in t009:
        problems.append("t009 :2854 的 it 标题末尾应是「[探测]、[模型] 可点」")
    if "应可点').toBe(false)" not in t009:
        problems.append("t009 :2861 应改成 toBe(false)，提示语「应可点」")
    if "T055 接上的 [探测]、[模型]" not in t009:
        problems.append("t009 :2970 的 it 标题应加「与 T055 接上的 [探测]、[模型]」")
    if "'扫描 PATH', '探测', '模型'" not in t009:
        problems.append("t009 :2974 的白名单应加「探测」「模型」")
    # t045：运行时页 4→1
    t045 = read_rel(T045_GATE_REL)
    if "运行时页 1" not in t045:
        problems.append("t045 :560/:563 的「运行时页 4」应改成「运行时页 1」")
    if '("运行时页 1", r"toBe\\(1\\)")' not in t045:
        problems.append('t045 :563 应改成 ("运行时页 1", r"toBe\\(1\\)")')
    if "运行时页 4" in t045:
        problems.append("t045 里不应再残留「运行时页 4」")
    # t054：:717 三类 JobKind
    t054 = read_rel(T054_GATE_REL)
    if f'if "{JOBKIND_THREE}" not in code:' not in t054:
        problems.append("t054 :717 应改成三类 JobKind 的逐字记号")
    if "export type JobKind = 'runtime-scan';" in t054:
        problems.append("t054 里不应再残留一类的旧记号")
    # 包内 page-app：运行时页 1、toBe(1)
    app_test = read_rel(PAGE_APP_TEST_REL)
    if "运行时页 1" not in app_test:
        problems.append("page-app :93 的 it 标题应改成「运行时页 1」")
    if ".toBe(1)" not in app_test or "运行时页 4" in app_test:
        problems.append("page-app :98 应改成 toBe(1)，且不应再残留「运行时页 4」")
    # 包内 page-runtimes：:101 标题、:109 toBe(false)
    rt_test = read_rel(PAGE_RUNTIMES_TEST_REL)
    if "[删除…] 与 [探测]、[模型] 都可点" not in rt_test:
        problems.append("page-runtimes :101 的 it 标题应改成「[删除…] 与 [探测]、[模型] 都可点」")
    if ".toBe(false)" not in rt_test:
        problems.append("page-runtimes :109 应改成 toBe(false)（行内按钮都可点）")
    fail_if(problems, "兼容性一节的旧断言（S09）")


# ---------------------------------------------------------------------------
# 探针（黑盒 Vitest 用例，临时写进 desktop/web/gate-probe/，跑完即删；每份自带全部辅助函数）
# 探针直接渲染 RuntimesView（照包内 page-runtimes.test.tsx 的既有写法注入 runtimes 与 quizs，不 mock 被测组件）。
# ---------------------------------------------------------------------------

PROBE_PROBE = r'''// T055 门禁 probe 探针（真实模式）：setLiveClientForTests 注入假服务记录作业请求，看 [探测] 的创建正文、
// 进度、结局与结果块、同类互斥与重开。每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RuntimesView } from '../src/pages/readonly1/runtimes-RuntimesView';
import { resetJobStoreForTests } from '../src/jobs/jobStore';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const JOB_ID = 'job-probe-fixed-00000000000000000000000000';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
}
function btnIn(root: any, label: string): HTMLButtonElement {
  const hit = qa(root, 'button').find((b: any) => text(b) === label);
  expect(hit, '应有按钮「' + label + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function rowOf(root: any, id: string): any {
  return qa(root, 'tbody tr').find((tr: any) => text(tr.querySelector('td')) === id);
}
function btnInRow(root: any, id: string, label: string): HTMLButtonElement {
  const row = rowOf(root, id);
  expect(row, '应有行 ' + id).toBeTruthy();
  return btnIn(row, label);
}
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}
function errEnv(message: string): any {
  return { ok: false, exit_code: 1, data: null, output: [], messages: [message], command: [], elapsed_ms: 0 };
}

function jobView(state: string, envelope: any): any {
  const terminal = ['succeeded', 'failed', 'cancelled', 'timed_out'].indexOf(state) >= 0;
  return {
    id: JOB_ID, kind: 'runtime-probe', state, reason: null,
    created_ms: 1, started_ms: state === 'queued' ? null : 2, finished_ms: terminal ? 3 : null,
    envelope,
  };
}
function probeEnv(data: any): any {
  return { ok: data && data.ok, exit_code: data && data.ok ? 0 : 1, data, output: [], messages: data && data.ok ? [] : ['ERROR: 探测示意'], command: [], elapsed_ms: 1 };
}
const PI_OK = { runtime: 'pi', adapter: 'pi', source: 'local', command: ['node', 'pi.js'], version_exit_code: 0, version: '3.9.4', help: { exit_code: 0, missing_flags: [], thinking_levels: ['off', 'low', 'high'] }, ok: true };
const PI_BAD = { runtime: 'pi', adapter: 'pi', source: 'local', command: null, version_exit_code: 1, version: '', help: { exit_code: 1, missing_flags: ['--no-context-files'], thinking_levels: [] }, ok: false };

const RUNTIMES = [
  { id: 'pi', adapter: 'pi', source: 'local', command: ['pi'], notes: [] },
  { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['claude'], notes: [] },
  { id: 'opencode', adapter: 'opencode', source: 'missing', command: null, notes: [] },
] as any;
const QUIZS = {
  providers: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { providers: [] } },
  live: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { live: [] } },
} as any;

let jobState = 'running';
let jobEnvelope: any = null;
let createStatus = 201;
let creates: any[] = [];
let cancels: any[] = [];
let queries: string[] = [];

const fake: LiveClient = {
  get(path: string): Promise<any> { return Promise.resolve({ status: 404, body: null }); },
  post(path: string, body: unknown): Promise<any> { return Promise.resolve({ status: 200, body: errEnv('不该调写路由') }); },
  getRaw(path: string): Promise<any> {
    if (path.indexOf('/api/v1/jobs/') === 0) {
      queries.push(path);
      return Promise.resolve({ status: 200, body: jobView(jobState, jobEnvelope) });
    }
    return Promise.resolve({ status: 404, body: null });
  },
  postRaw(path: string, body: unknown): Promise<any> {
    if (path === '/api/v1/jobs') {
      creates.push(body);
      if (createStatus !== 201) return Promise.resolve({ status: createStatus, body: errEnv('ERROR 不支持这个作业') });
      return Promise.resolve({ status: 201, body: jobView('queued', null) });
    }
    if (path.indexOf('/api/v1/jobs/') === 0 && path.endsWith('/cancel')) {
      cancels.push(body);
      jobState = 'cancelled';
      return Promise.resolve({ status: 200, body: jobView('cancelled', null) });
    }
    return Promise.resolve({ status: 404, body: null });
  },
};

beforeEach(() => {
  jobState = 'running';
  jobEnvelope = null;
  createStatus = 201;
  creates = [];
  cancels = [];
  queries = [];
  window.location.hash = '';
  setLiveClientForTests(fake);
});
afterEach(() => {
  cleanup();
  resetJobStoreForTests();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

async function openProbe(id: string): Promise<ReturnType<typeof render>> {
  const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
  fireEvent.click(btnInRow(r.container, id, '探测'));
  await flush();
  return r;
}

async function hoverTip(btn: any): Promise<string> {
  fireEvent.mouseEnter(btn.parentElement);
  await act(async () => { await sleep(700); });
  const tip = document.querySelector('[role="tooltip"]');
  return tip ? text(tip) : '';
}

describe('RuntimesView 的 [探测]（真实模式）', () => {
  it('(a) 点 [探测]：创建正文恰两个键；标题「探测 pi」；进度条 aria-label 探测进行中、已用秒数、每秒查同一个作业号', async () => {
    const r = await openProbe('pi');
    const entry = btnInRow(r.container, 'pi', '探测');
    expect(entry.getAttribute('data-variant'), '入口 ghost').toBe('ghost');
    expect(entry.getAttribute('data-size'), '入口 sm').toBe('sm');
    const d = needDlg();
    expect(text(d), '对话框标题').toContain('探测 pi');
    expect(creates.length, '只发一次创建').toBe(1);
    expect(creates[0], '创建正文恰两个键').toEqual({ kind: 'runtime-probe', runtime: 'pi' });
    expect(Object.keys(creates[0]).length).toBe(2);
    const bar = qa(d, '[role="progressbar"]')[0];
    expect(bar, '运行中应有进度条').toBeTruthy();
    expect(bar.getAttribute('aria-label'), '进度条 aria-label').toBe('探测进行中');
    expect(text(d)).toMatch(/已用 \d+ 秒/);
    expect(btnIn(d, '重新探测').disabled, '运行中重新探测禁用').toBe(true);
    await act(async () => { await sleep(2200); });
    expect(queries.length, '每秒查一次').toBeGreaterThanOrEqual(2);
    expect(queries.every((p) => p === '/api/v1/jobs/' + JOB_ID), '查询同一个作业号').toBe(true);
  }, 20000);

  it('(b) 成功：版本、命令来源、命令；pi 的缺少的参数（无）与思考级别', async () => {
    jobState = 'succeeded';
    jobEnvelope = probeEnv(PI_OK);
    await openProbe('pi');
    await act(async () => { await sleep(1300); });
    const t = text(needDlg());
    expect(t).toContain('3.9.4');
    expect(t).toContain('本机文件');
    expect(t).toContain('node pi.js');
    expect(t).toContain('缺少的参数');
    expect(t).toContain('无');
    expect(t).toContain('思考级别');
    expect(t).toContain('low、high');
  }, 20000);

  it('(c) ok 为假的 failed：结果块照旧（版本未知）并点明没过的项，且在内核原文之前；重新探测可点', async () => {
    jobState = 'failed';
    jobEnvelope = probeEnv(PI_BAD);
    await openProbe('pi');
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    const t = text(d);
    expect(t, '失败标题').toContain('探测失败');
    expect(t, '结果块照旧：空版本写版本未知').toContain('版本未知');
    expect(t, '点明版本命令退出码').toContain('版本命令退出码 1');
    expect(t, '点明 --help 退出码').toContain('pi --help 退出码 1');
    expect(t, '点明缺少的参数').toContain('pi 缺少参数：--no-context-files');
    expect(t.indexOf('版本命令退出码 1'), '没过项在内核原文之前').toBeLessThan(t.indexOf('ERROR: 探测示意'));
    expect(t).toContain('ERROR: 探测示意');
    expect(qa(d, '[role="progressbar"]').length, '终态后没有进度条').toBe(0);
    expect(btnIn(d, '重新探测').disabled, '终态后重新探测可点').toBe(false);
  }, 20000);

  it('(d) 没有 data 的 failed：只显示内核报错原文，不显示结果块', async () => {
    jobState = 'failed';
    jobEnvelope = errEnv('ERROR: 内核报错（探测示意）');
    await openProbe('pi');
    await act(async () => { await sleep(1300); });
    const t = text(needDlg());
    expect(t, '内核原文照显示').toContain('ERROR: 内核报错（探测示意）');
    expect(t, '没有结果块：不写版本未知').not.toContain('版本未知');
    expect(t, '没有 failedDetail').not.toContain('版本命令退出码');
    expect(t, '没有结果块行标签').not.toContain('命令来源');
  }, 20000);

  it('(e) timed_out：超时（超过 150 秒），已停止；重新探测可点，点了发第二次创建、新作业在跑', async () => {
    jobState = 'timed_out';
    await openProbe('pi');
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    expect(text(d)).toContain('超时（超过 150 秒），已停止');
    jobState = 'running';
    fireEvent.click(btnIn(d, '重新探测'));
    await flush();
    expect(creates.length, '重新探测发新创建').toBe(2);
    expect(creates[1]).toEqual({ kind: 'runtime-probe', runtime: 'pi' });
    expect(qa(needDlg(), '[role="progressbar"]').length, '新作业在跑').toBeGreaterThanOrEqual(1);
  }, 20000);

  it('(f) 取消：正文恰 {}，随后「已取消」', async () => {
    await openProbe('pi');
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(cancels.length, '只发一次取消').toBe(1);
    expect(cancels[0], '取消正文恰 {}').toEqual({});
    await act(async () => { await sleep(1300); });
    expect(text(needDlg()), '取消后落已取消').toContain('已取消');
  }, 20000);

  it('(g) 创建失败 400：显示报错原文与探测失败；重新探测可点并重发', async () => {
    createStatus = 400;
    await openProbe('pi');
    await act(async () => { await sleep(300); });
    const d = needDlg();
    expect(text(d), '创建失败的报错原文').toContain('ERROR 不支持这个作业');
    expect(text(d)).toContain('探测失败');
    expect(btnIn(d, '重新探测').disabled, '创建失败后重新探测可点').toBe(false);
    createStatus = 201;
    fireEvent.click(btnIn(d, '重新探测'));
    await flush();
    expect(creates.length, '重发创建').toBe(2);
  }, 20000);

  it('(h) 同类忙于别的行：claude-code 的 [探测] 禁用、悬停「正在探测 pi」；本行仍可点；opencode 行没有 [探测]', async () => {
    const r = await openProbe('pi');
    const other = btnInRow(r.container, 'claude-code', '探测');
    expect(other.disabled, '忙于别的行时同类按钮禁用').toBe(true);
    expect(await hoverTip(other), '悬停写明正在忙谁').toBe('正在探测 pi');
    expect(btnInRow(r.container, 'pi', '探测').disabled, '本行不忙').toBe(false);
    expect(qa(rowOf(r.container, 'opencode'), 'button').map((b: any) => text(b)), '来源 missing 的行没有 [探测]').toEqual(['删除…']);
  }, 20000);

  it('(i) 本行重开：关掉不再创建、关着时照查、再开是同一个作业；关着时 DOM 里没有作业卡', async () => {
    const r = await openProbe('pi');
    fireEvent.click(btnIn(needDlg(), '关闭'));
    await flush();
    expect(dlg(), '关掉后对话框不在').toBeNull();
    expect(document.querySelector('[role="progressbar"]'), 'DOM 里没有作业卡').toBeNull();
    const q = queries.length;
    await act(async () => { await sleep(2200); });
    expect(queries.length, '关着时行内入口的订阅照查（不然别的行一直灰着）').toBeGreaterThan(q);
    fireEvent.click(btnInRow(r.container, 'pi', '探测'));
    await flush();
    expect(creates.length, '再开是同一个作业，不再创建').toBe(1);
    expect(qa(needDlg(), '[role="progressbar"]').length).toBeGreaterThanOrEqual(1);
  }, 20000);

  it('(j) 没点过任何入口：不排每秒空转的计时器（没有 setTimeout(…, 1000)）', async () => {
    const spy = vi.spyOn(globalThis, 'setTimeout');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    await act(async () => { await sleep(2600); });
    const sec = spy.mock.calls.filter((c: any[]) => c[1] === 1000);
    expect(sec.length, '没有作业时不排 1000 毫秒的计时器（不整页常驻时空转）').toBe(0);
    expect(creates.length).toBe(0);
    expect(queries.length, '没点过就没有作业请求').toBe(0);
    spy.mockRestore();
  }, 20000);
});
'''


MODELS_PROBE = r'''// T055 门禁 models 探针（真实模式）：[模型] 的创建正文、三列结果表、空数组、超时 120 与两个 pi 行的
// 同类互斥。每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RuntimesView } from '../src/pages/readonly1/runtimes-RuntimesView';
import { resetJobStoreForTests } from '../src/jobs/jobStore';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const JOB_ID = 'job-models-fixed-0000000000000000000000000';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
}
function btnIn(root: any, label: string): HTMLButtonElement {
  const hit = qa(root, 'button').find((b: any) => text(b) === label);
  expect(hit, '应有按钮「' + label + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function rowOf(root: any, id: string): any {
  return qa(root, 'tbody tr').find((tr: any) => text(tr.querySelector('td')) === id);
}
function btnInRow(root: any, id: string, label: string): HTMLButtonElement {
  const row = rowOf(root, id);
  expect(row, '应有行 ' + id).toBeTruthy();
  return btnIn(row, label);
}
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}

function jobView(state: string, envelope: any): any {
  const terminal = ['succeeded', 'failed', 'cancelled', 'timed_out'].indexOf(state) >= 0;
  return {
    id: JOB_ID, kind: 'models', state, reason: null,
    created_ms: 1, started_ms: state === 'queued' ? null : 2, finished_ms: terminal ? 3 : null,
    envelope,
  };
}
function modelsEnv(models: any[]): any {
  return { ok: true, exit_code: 0, data: { runtime: 'pi', models, allowed_executors_set: true }, output: [], messages: [], command: [], elapsed_ms: 1 };
}
const FOUR = [
  { provider: 'stepfun', model: 'step-5-preview', allowed: true },
  { provider: 'deepseek', model: 'deepseek-chat', allowed: false },
  { provider: 'anthropic', model: 'claude-x', allowed: null },
  { provider: '<redacted>', model: '<redacted>', allowed: true },
];

// 两个 pi 行（adapter 都是 pi）：同类互斥要能在一个页面上看到「忙于别的行」。
const RUNTIMES = [
  { id: 'pi', adapter: 'pi', source: 'local', command: ['pi'], notes: [] },
  { id: 'pi-alt', adapter: 'pi', source: 'env', command: ['pi-alt'], notes: [] },
  { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['claude'], notes: [] },
  { id: 'opencode', adapter: 'opencode', source: 'missing', command: null, notes: [] },
] as any;
const QUIZS = {
  providers: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { providers: [] } },
  live: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { live: [] } },
} as any;

let jobState = 'running';
let jobEnvelope: any = null;
let creates: any[] = [];
let queries: string[] = [];

const fake: LiveClient = {
  get(path: string): Promise<any> { return Promise.resolve({ status: 404, body: null }); },
  post(path: string, body: unknown): Promise<any> { return Promise.resolve({ status: 404, body: null }); },
  getRaw(path: string): Promise<any> {
    if (path.indexOf('/api/v1/jobs/') === 0) {
      queries.push(path);
      return Promise.resolve({ status: 200, body: jobView(jobState, jobEnvelope) });
    }
    return Promise.resolve({ status: 404, body: null });
  },
  postRaw(path: string, body: unknown): Promise<any> {
    if (path === '/api/v1/jobs') {
      creates.push(body);
      return Promise.resolve({ status: 201, body: jobView('queued', null) });
    }
    return Promise.resolve({ status: 404, body: null });
  },
};

beforeEach(() => {
  jobState = 'running';
  jobEnvelope = null;
  creates = [];
  queries = [];
  window.location.hash = '';
  setLiveClientForTests(fake);
});
afterEach(() => {
  cleanup();
  resetJobStoreForTests();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

async function openModels(id: string): Promise<ReturnType<typeof render>> {
  const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
  fireEvent.click(btnInRow(r.container, id, '模型'));
  await flush();
  return r;
}

async function hoverTip(btn: any): Promise<string> {
  fireEvent.mouseEnter(btn.parentElement);
  await act(async () => { await sleep(700); });
  const tip = document.querySelector('[role="tooltip"]');
  return tip ? text(tip) : '';
}

describe('RuntimesView 的 [模型]（真实模式）', () => {
  it('(a) 点 [模型]：创建正文恰两个键；标题「模型 pi」；进度条 aria-label 列模型进行中', async () => {
    const r = await openModels('pi');
    const entry = btnInRow(r.container, 'pi', '模型');
    expect(entry.getAttribute('data-variant'), '入口 ghost').toBe('ghost');
    expect(entry.getAttribute('data-size'), '入口 sm').toBe('sm');
    const d = needDlg();
    expect(text(d), '对话框标题').toContain('模型 pi');
    expect(creates.length).toBe(1);
    expect(creates[0], '创建正文恰两个键').toEqual({ kind: 'models', runtime: 'pi' });
    expect(Object.keys(creates[0]).length).toBe(2);
    const bar = qa(d, '[role="progressbar"]')[0];
    expect(bar, '运行中应有进度条').toBeTruthy();
    expect(bar.getAttribute('aria-label'), '进度条 aria-label').toBe('列模型进行中');
    expect(qa(rowOf(r.container, 'claude-code'), 'button').map((b: any) => text(b)), 'adapter 不是 pi 的行没有 [模型]').toEqual(['探测', '删除…']);
  }, 20000);

  it('(b) 成功：说明句、三列列头与次序、是/否/不限制、<redacted> 原样', async () => {
    jobState = 'succeeded';
    jobEnvelope = modelsEnv(FOUR);
    await openModels('pi');
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    const t = text(d);
    expect(t, '表上方说明句').toContain('模型列表来自 pi --list-models，不调用模型');
    const table = qa(d, 'table')[0];
    expect(qa(table, 'th').map((el: any) => text(el)), '三列列头次序如此').toEqual(['provider', 'model', '是否在允许列表']);
    const rows = qa(table, 'tbody tr');
    expect(rows.length, '四行照 data.models 的次序').toBe(4);
    expect(qa(rows[0], 'td').map((c: any) => text(c))).toEqual(['stepfun', 'step-5-preview', '是']);
    expect(qa(rows[1], 'td').map((c: any) => text(c))).toEqual(['deepseek', 'deepseek-chat', '否']);
    expect(qa(rows[2], 'td').map((c: any) => text(c))).toEqual(['anthropic', 'claude-x', '不限制']);
    expect(qa(rows[3], 'td').map((c: any) => text(c)), '<redacted> 原样显示').toEqual(['<redacted>', '<redacted>', '是']);
    expect(btnIn(d, '重新列出').disabled, '终态后重新列出可点').toBe(false);
  }, 20000);

  it('(c) 空数组：说明句照旧，「没有列出模型」', async () => {
    jobState = 'succeeded';
    jobEnvelope = modelsEnv([]);
    await openModels('pi');
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    expect(text(d), '说明句照旧').toContain('模型列表来自 pi --list-models，不调用模型');
    expect(text(d), '空数组一句话').toContain('没有列出模型');
    expect(qa(d, 'table tbody tr').length, '没有模型行').toBe(0);
  }, 20000);

  it('(d) timed_out：超时（超过 120 秒），已停止；重新列出可点并重发', async () => {
    jobState = 'timed_out';
    await openModels('pi');
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    expect(text(d)).toContain('超时（超过 120 秒），已停止');
    jobState = 'running';
    fireEvent.click(btnIn(d, '重新列出'));
    await flush();
    expect(creates.length, '重新列出发新创建').toBe(2);
    expect(creates[1]).toEqual({ kind: 'models', runtime: 'pi' });
  }, 20000);

  it('(e) 同类忙于别的行：pi-alt 的 [模型] 禁用、悬停「正在列 pi 的模型」；本行可点；结束后能重新开', async () => {
    const r = await openModels('pi');
    const other = btnInRow(r.container, 'pi-alt', '模型');
    expect(other.disabled, '忙于别的行时同类按钮禁用').toBe(true);
    expect(await hoverTip(other), '悬停写明正在忙谁').toBe('正在列 pi 的模型');
    expect(btnInRow(r.container, 'pi', '模型').disabled, '本行不忙').toBe(false);
    jobState = 'succeeded';
    jobEnvelope = modelsEnv(FOUR);
    await act(async () => { await sleep(1300); });
    fireEvent.click(btnInRow(r.container, 'pi-alt', '模型'));
    await flush();
    expect(creates.length, '结束后别的行能重新开').toBe(2);
    expect(creates[1]).toEqual({ kind: 'models', runtime: 'pi-alt' });
  }, 20000);

  it('(f) 关掉再开：不再创建、同一个作业照查', async () => {
    const r = await openModels('pi');
    fireEvent.click(btnIn(needDlg(), '关闭'));
    await flush();
    expect(dlg()).toBeNull();
    const q = queries.length;
    await act(async () => { await sleep(2200); });
    expect(queries.length, '关着时照查').toBeGreaterThan(q);
    fireEvent.click(btnInRow(r.container, 'pi', '模型'));
    await flush();
    expect(creates.length, '再开不再创建').toBe(1);
    expect(qa(needDlg(), '[role="progressbar"]').length).toBeGreaterThanOrEqual(1);
  }, 20000);
});
'''


STUB_PROBE = r'''// T055 门禁 stub 探针（桩模式，不注入客户端）：直接调 api 看缺 runtime 的 400；读夹具看五个开关与
// 探测奇偶两份、非 pi 探测、列模型四行；数计时器钉「没有作业时不排计时器」。每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RuntimesView } from '../src/pages/readonly1/runtimes-RuntimesView';
import { resetJobStoreForTests } from '../src/jobs/jobStore';
import { startJob } from '../src/api';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
}
function btnIn(root: any, label: string): HTMLButtonElement {
  const hit = qa(root, 'button').find((b: any) => text(b) === label);
  expect(hit, '应有按钮「' + label + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function rowOf(root: any, id: string): any {
  return qa(root, 'tbody tr').find((tr: any) => text(tr.querySelector('td')) === id);
}
function btnInRow(root: any, id: string, label: string): HTMLButtonElement {
  const row = rowOf(root, id);
  expect(row, '应有行 ' + id).toBeTruthy();
  return btnIn(row, label);
}
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}

const RUNTIMES = [
  { id: 'pi', adapter: 'pi', source: 'local', command: ['pi'], notes: [] },
  { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['claude'], notes: [] },
  { id: 'opencode', adapter: 'opencode', source: 'missing', command: null, notes: [] },
] as any;
const QUIZS = {
  providers: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { providers: [] } },
  live: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { live: [] } },
} as any;

function setMock(mode: string): void {
  window.location.hash = '#/runtimes?mock=' + mode;
}

beforeEach(() => {
  window.location.hash = '';
});
afterEach(() => {
  cleanup();
  resetJobStoreForTests();
  window.location.hash = '';
});

describe('桩模式：两类新作业', () => {
  it('(a) startJob 缺 runtime：runtime-probe 与 models 都回 400', async () => {
    const a = await startJob('runtime-probe');
    expect(a.status, 'runtime-probe 缺 runtime 回 400').toBe(400);
    const b = await startJob('models');
    expect(b.status, 'models 缺 runtime 回 400').toBe(400);
  }, 20000);

  it('(b) data 开关下 pi 的探测：奇数份 failed 带 data（版本未知 + 点明缺 --no-context-files），重新探测后偶数份 succeeded（0.1.2 + 思考级别）', async () => {
    setMock('data');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    fireEvent.click(btnInRow(r.container, 'pi', '探测'));
    await flush();
    expect(qa(needDlg(), '[role="progressbar"]').length, '第一次查询前是 running').toBeGreaterThanOrEqual(1);
    await act(async () => { await sleep(2300); });
    let d = needDlg();
    let t = text(d);
    expect(t, '奇数份落 failed 带 data').toContain('探测失败');
    expect(t, '空版本写版本未知').toContain('版本未知');
    expect(t, '点明缺少的参数').toContain('pi 缺少参数：--no-context-files');
    expect(btnIn(d, '重新探测').disabled).toBe(false);
    fireEvent.click(btnIn(d, '重新探测'));
    await flush();
    await act(async () => { await sleep(2400); });
    d = needDlg();
    t = text(d);
    expect(t, '偶数份正常：版本 0.1.2').toContain('0.1.2');
    expect(t, '思考级别列出来').toContain('思考级别');
    expect(t, '思考级别含 xhigh').toContain('xhigh');
    expect(t, '缺少的参数为空写无').toContain('无');
  }, 20000);

  it('(c) 非 pi 的探测（claude-code）：succeeded、版本 1.0.9、没有 pi 的两行', async () => {
    setMock('data');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    fireEvent.click(btnInRow(r.container, 'claude-code', '探测'));
    await flush();
    await act(async () => { await sleep(2400); });
    const d = needDlg();
    const t = text(d);
    expect(t, '非 pi 正常探测的版本').toContain('1.0.9');
    expect(t, '没有缺少的参数一行（不带 help）').not.toContain('缺少的参数');
    expect(t, '没有思考级别一行').not.toContain('思考级别');
  }, 20000);

  it('(d) data 开关下 pi 的 [模型]：四行、一行「否」、<redacted> 原样、说明句与三列头', async () => {
    setMock('data');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    fireEvent.click(btnInRow(r.container, 'pi', '模型'));
    await flush();
    await act(async () => { await sleep(2400); });
    const d = needDlg();
    const t = text(d);
    expect(t, '说明句').toContain('模型列表来自 pi --list-models，不调用模型');
    const table = qa(d, 'table')[0];
    expect(qa(table, 'th').map((el: any) => text(el)), '三列列头').toEqual(['provider', 'model', '是否在允许列表']);
    const rows = qa(table, 'tbody tr');
    expect(rows.length, '四行').toBe(4);
    expect(t, '一行不在允许列表').toContain('否');
    expect(t, '一行被遮').toContain('<redacted>');
  }, 20000);

  it('(e) loading 开关：探测一直 running；取消落「已取消」', async () => {
    setMock('loading');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    fireEvent.click(btnInRow(r.container, 'pi', '探测'));
    await flush();
    await act(async () => { await sleep(2200); });
    const d = needDlg();
    expect(qa(d, '[role="progressbar"]').length, 'loading 一直 running').toBeGreaterThanOrEqual(1);
    expect(text(d)).toMatch(/已用 \d+ 秒/);
    fireEvent.click(btnIn(d, '取消'));
    await flush();
    await act(async () => { await sleep(1300); });
    expect(text(needDlg()), '取消后落已取消').toContain('已取消');
  }, 20000);

  it('(f) error 开关：落 failed，不显示结果块', async () => {
    setMock('error');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    fireEvent.click(btnInRow(r.container, 'pi', '探测'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(needDlg());
    expect(t, '落 failed').toContain('探测失败');
    expect(t, '没有 data：不写版本未知').not.toContain('版本未知');
    expect(t, '没有结果块行标签').not.toContain('命令来源');
  }, 20000);

  it('(g) 没点过任何入口：不排每秒空转的计时器（没有 setTimeout(…, 1000)）', async () => {
    const spy = vi.spyOn(globalThis, 'setTimeout');
    render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    await act(async () => { await sleep(2600); });
    const sec = spy.mock.calls.filter((c: any[]) => c[1] === 1000);
    expect(sec.length, '没有作业时不排 1000 毫秒的计时器').toBe(0);
    spy.mockRestore();
  }, 20000);
});
'''


PROBE_SPECS = {
    "probe": (PROBE_PROBE, (RUNTIMEPROBE_REL, RUNTIMEMODELS_REL, JOBSTORE_REL, TRANSPORT_REL, MODE_REL, API_REL, RUNTIMESVIEW_REL)),
    "models": (MODELS_PROBE, (RUNTIMEMODELS_REL, RUNTIMEPROBE_REL, JOBSTORE_REL, MODE_REL, TRANSPORT_REL, API_REL, RUNTIMESVIEW_REL)),
    "stub": (STUB_PROBE, (RUNTIMEPROBE_REL, RUNTIMEMODELS_REL, JOBSTORE_REL, MOCKJOBS_REL, RUNTIMESVIEW_REL, API_REL)),
}
PROBE_ORDER = ("probe", "models", "stub")


# ---------------------------------------------------------------------------
# P 系列：流水线断言；D 系列：探针断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V02、D12：npm 依赖（已在就跳过重装）、npm test（全绿，含执行端三份新测试与既有包内测试）
    都退出 0；依赖文件一个字节没动；gate-probe/ 没有留下。"""
    assert any(pipeline.steps.get(k) is not None and pipeline.steps[k].code == 0
               for k in ("npm ci", "npm ci --offline")), \
        f"npm ci（含 --offline 兑底）未成功：{pipeline.stopped_reason or pipeline.reason}"
    step = assert_step_ok(pipeline, "npm test")
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m, f"npm test 输出里没有通过计数：\n{step.tail}"
    assert int(m.group(1)) > 0
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), \
        f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert pipeline.digests_before == pipeline.digests_after, \
        "npm 流水线不许改动 desktop/web/package.json 与 package-lock.json"
    assert not pipeline.gate_probe_left, "gate-probe/ 目录在探针后应清掉"


def test_p2_worktree_unchanged_by_pipeline(pipeline):
    """P2（守卫）：流水线与探针前后 git status 相同；gate-probe/ 没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"


def test_d01_probe_probe(pipeline):
    """probe 探针 / D01、D02、D04、D05（真实模式，假服务看真实正文）：创建正文恰两个键；标题「探测 pi」；
    进度条 aria-label 探测进行中与已用秒数与每秒查询；成功结果（版本/来源/命令/缺少的参数/思考级别）；
    ok 为假的 failed（结果块照旧 + 点明没过的项、在内核原文之前）；没有 data 的 failed（只显内核原文）；
    timed_out 150 与重新探测；取消正文恰 {}；创建失败 400；忙于别的行（禁用与悬停「正在探测 pi」）；
    本行重开（关着时照查、再开同一作业）；没有作业时不排计时器。"""
    assert_probe_ok(pipeline, "probe")


def test_d02_models_probe(pipeline):
    """models 探针 / D01、D03、D04（真实模式）：创建正文恰两个键；标题「模型 pi」；三列列头与是/否/
    不限制与 <redacted>；说明句；空数组「没有列出模型」；timed_out 120；两个 pi 行的同类互斥（悬停
    「正在列 pi 的模型」、结束后能重新开）；关掉再开同一作业。"""
    assert_probe_ok(pipeline, "models")


def test_d03_stub_probe(pipeline):
    """stub 探针 / D05、D08（桩模式，读夹具）：缺 runtime 的两类新作业回 400；data 开关下 pi 的探测奇数份
    failed 带 data（点明缺 --no-context-files）、重新探测后偶数份 succeeded（0.1.2 + 思考级别）；非 pi 的
    探测（1.0.9、没有 pi 的两行）；列模型四行含一行「否」与 <redacted>；loading 一直 running 且取消落
    「已取消」；error 落 failed 不显示结果块；没有作业时不排计时器。"""
    assert_probe_ok(pipeline, "stub")
