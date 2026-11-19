"""T056 战前门禁：桌面端前端「[运行就绪检查]：就绪检查一节接上作业接口，逐个角色显示就绪卡」的黑盒基准测试
（合同 t056-desktop-web-runtime-doctor.v1，基线 cb255d54）。

被测对象是「就绪检查」一节的 [运行就绪检查] 入口（新文件 ``desktop/web/src/writes/RuntimeDoctor.tsx`` 与
``runtime-doctor.css``）与它背后的作业客户端扩一类（doctor）：

- ``api.ts`` 的 ``JobKind`` 扩成四类（doctor 加在末尾）；``startJob`` 的函数体一个字不改（doctor 不带 runtime
  时本来就发 ``{ kind }``，正文恰一个键）；201 才算建成；桩分支 ``mockStartJob(kind, runtime)``；
  ``getJob`` / ``cancelJob`` 照旧。
- ``jobStore.ts``：``KINDS`` 扩成四类（次序 scan、probe、models、doctor）；``snaps`` 与 ``subscribers`` 两张
  ``Record<JobKind, …>`` 各加 doctor 一项；doctor 的槽里 runtime 是 null（``ensureJob`` / ``restartJob`` /
  ``useJob`` 不带 runtime）；五个既有导出与 ``useBusyRuntime`` 照旧；T055 的公式、setTimeout 链、
  「没有作业时不排计时器」照旧。
- ``JobCard.tsx``：只在三张按 kind 查的表里各加 doctor 一项（失败标题「就绪检查失败」、进度条 aria-label
  「就绪检查进行中」、超时 600）；扫描、探测、列模型三支的字面与 ``runtime-scan: 150`` 一字不动；
  failed 分支照旧（doctor 的结果块不经过它）。
- 新组件 ``RuntimeDoctor.tsx``：按钮文字始终逐字「运行就绪检查」（secondary/md、PlayIcon 16，运行中只禁用
  不换字）；没跑过时虚线框 ``p.rt-ready`` 与新句子（去掉「运行入口在第二阶段接入」）；运行中渲染 JobCard
  （``kind="doctor"``、``title="就绪检查"``、``key={job?.id ?? 'creating'}``）并另起一行「离开这个页面作业
  也会继续，回来时显示结果。」；结束后自己渲染结果块（汇总「全部就绪」/「有未就绪的角色（N 个）」、无头角色
  一张就绪卡（卡头 ✓ 就绪 / ✗ 未就绪 · 角色中文名 · profile X、八个键值行、问题列表、说明行）、不是无头的
  角色各一行）；有 data 的 failed 照样显示结果块（不显示笼统的「就绪检查失败」），没有 data 的 failed 与
  取消、超时交给 JobCard；缺键写「—」、允许列表 null 写「不限制」、凭据空写「无」；不跨层引 ``src/pages``。
- 桩 ``mock/jobs.ts``：doctor 不带 runtime 也放行（201）；终态信封按 doctor 作业次序奇偶（奇数次执行端没就绪、
  落 failed 带 data；偶数次全部就绪、succeeded）；``kindFailedEnvelope`` 加 doctor 一支（error 开关下没有
  data）；扫描、探测、列模型三支一字不改。
- ``runtimes-RuntimesView.tsx``：「就绪检查」一节只渲染 ``<RuntimeDoctor />``；``DisabledAction`` 删干净；
  其余一字不改。

基线（cb255d54）上新文件不存在、api.ts 只有三类 JobKind、视图仍是 DisabledAction，所以本文件的失败落在
「记号不在」「文件不存在」「流水线没跑」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有仓库
文件的读取都发生在用例函数里；流水线（npm、Vitest、探针）放在 ``pipeline`` 会话级夹具里（全量 pytest 默认
跳过，点名运行本文件才跑；候选里还没有本片的标记时夹具不调 npm——照 T024/T040/T041/T043/T044/T045/T051/
T052/T053/T054/T055 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线）：api.ts 的四类 JobKind 与 startJob 正文（S01）；jobStore 的 KINDS 四类、
  两张表各加 doctor 与既有公式（S02）；JobCard 的三张表加 doctor 与既有字面（S03）；桩的 doctor 夹具与三支
  不改（S04）；RuntimesView 的换组件与其余一字不改（S05）；RuntimeDoctor.tsx（S06）；runtime-doctor.css
  （S07）；执行端新测试文件在位且要点齐备（S08）；兼容性一节的旧断言逐处改到位（S09）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、npm test 全绿；
  两份探针逐份写成 ``gate-probe/probe-<uid>-t056-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，
  ``finally`` 里删除。探针直接渲染 ``RuntimesView``（照包内 page-runtimes.test.tsx 的既有写法注入 runtimes 与
  quizs，不 mock 被测组件），真实模式用 ``setLiveClientForTests`` 注入假服务记录作业请求；等轮询用真实计时器
  ``sleep``（不用假计时器，钉「没有作业时不排计时器」的那一条用假计时器数挂起的计时器）。每份探针自带全部
  辅助函数。
  - probe（真实模式）：空态（可点 secondary/md 带 PlayIcon、虚线框新句子、没有作业卡）；点 [运行就绪检查] 的
    创建正文恰 ``{"kind":"doctor"}``、进度（aria-label 就绪检查进行中、已用秒数、[取消]）、「离开这个页面」
    那一行、每秒查同一个作业号；succeeded 的结果块（汇总全部就绪、就绪卡卡头与八个键值行、凭据/允许列表/
    思考级别、说明行、其他角色一行）；failed 带 data（汇总有未就绪的角色（N 个）、问题列表、不显示就绪检查
    失败）；缺键写「—」与「本机 pi 不接受这个档位」、凭据为空写「无」；failed 没有 data（内核原文、无结果块）；
    已取消；超时 600；卸载再挂载同一作业不再创建、结束后再点新创建；取消之后再点新作业的 [取消] 可点；
    创建失败 400 与重建；没有作业时不排计时器。
  - stub（桩模式，不注入客户端）：doctor 不带 runtime 也能建（201）；data 开关下奇数份 failed 带 data
    （汇总与问题列表与凭据不可用、不显示就绪检查失败）、再点偶数份全部就绪；loading 一直 running 且按钮
    禁用；error 落 failed 没有 data。

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
RUNTIMEDOCTOR_REL = f"{WRITES_REL}/RuntimeDoctor.tsx"
RUNTIMEDOCTOR_CSS_REL = f"{WRITES_REL}/runtime-doctor.css"
TRANSPORT_REL = f"{SRC_REL}/live/transport.ts"
MODE_REL = f"{SRC_REL}/live/mode.ts"

DOCTOR_PAGE_TEST_REL = f"{TESTS_REL}/jobs-doctor-page.test.tsx"

T009_GATE_REL = "tests/test_gate_t009_baseline.py"
T023_GATE_REL = "tests/test_gate_t023_baseline.py"
T043_GATE_REL = "tests/test_gate_t043_baseline.py"
T045_GATE_REL = "tests/test_gate_t045_baseline.py"
T054_GATE_REL = "tests/test_gate_t054_baseline.py"
T055_GATE_REL = "tests/test_gate_t055_baseline.py"
PAGE_APP_TEST_REL = f"{TESTS_REL}/page-app.test.tsx"
PAGE_RUNTIMES_TEST_REL = f"{TESTS_REL}/page-runtimes.test.tsx"

# 逐字记号（合同 Behavior contract 与「写法钉死」一节，逐字照抄）
JOBKINDS = ("runtime-scan", "runtime-probe", "models", "doctor")
JOB_STATES = ("queued", "running", "succeeded", "failed", "cancelled", "timed_out")
JOBVIEW_KEYS = ("id", "kind", "state", "reason", "created_ms", "started_ms", "finished_ms", "envelope")

LABEL_DOCTOR = "运行就绪检查"
SECTION_TITLE = "就绪检查"
MSG_DOCTOR_FAILED = "就绪检查失败"
ARIA_DOCTOR = "就绪检查进行中"
MSG_CANCELLED = "已取消"
TIMEOUT_DOCTOR_TEXT = "超时（超过 600 秒），已停止"
LEAVE_NOTE = "离开这个页面作业也会继续，回来时显示结果。"
EMPTY_NOTE = "还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据。"
EMPTY_NOTE_OLD_TAIL = "；运行入口在第二阶段接入"
SUMMARY_ALL = "全部就绪"
SUMMARY_SOME = "有未就绪的角色"
SUMMARY_SOME_ONE = "有未就绪的角色（1 个）"
DASH = "—"
YES = "是"
NO = "否"
ANY_ALLOWED = "不限制"
CREDS_NONE = "无"
CREDS_OK = "可用"
CREDS_BAD = "不可用"
CONNECTED = "已接通"
NOT_CONNECTED = "未接通"
THINK_OK = "本机 pi 接受这个档位"
THINK_BAD = "本机 pi 不接受这个档位"
ROW_LABELS = ("命令", "版本", "模型在列表中", "登录", "思考级别", "允许列表", "凭据", "接通状态")
SOURCE_ENV = "环境变量"
SOURCE_LOCAL = "本机文件"
SOURCE_PATH = "PATH"
SOURCE_MISSING = "找不到"
ROLE_PLANNING = "规划审核端"
ROLE_CONTRACT = "合同端"
ROLE_EXECUTION = "执行端"
ROLE_SCHEDULER = "调度代理"
SOURCE_SUFFIX = "（来源："
MARK_READY = "✓"
MARK_NOT_READY = "✗"
WORD_READY = "就绪"
WORD_NOT_READY = "未就绪"
PROFILE_PREFIX = "profile "
# 桩的夹具记号（合同桩一节）
MOCK_SCAN_ERROR_MESSAGE = "ERROR 扫描失败：内核报错（示意）"
MOCK_CANCEL_409 = "作业已经结束"
MOCK_404 = "没有这个作业"
MOCK_SCAN_PATHS = (
    ("pi", "C:/tools/pi/pi.exe", "0.1.2"),
    ("claude-code", "C:/tools/npm/claude.cmd", "1.0.9"),
    ("codex", "C:/tools/codex/codex.exe", "0.5.0"),
)
MOCK_CRED_NAME = "STEP_API_KEY"
MOCK_CRED_PROBLEM = "凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY"
MOCK_ROLE_TEXT_HOST = "（交互宿主的模型不由 Themis 切换）"
MOCK_ROLE_CODES = ("planning_review", "contract", "execution", "scheduler_agent")
MOCK_EXEC_PROFILE = "step-high"
MOCK_EXEC_MODEL = "step-5-preview"

# 执行端新测试文件的最小覆盖记号（合同第 9 步点名的覆盖点）
EXECUTOR_TEST_TOKENS = {
    DOCTOR_PAGE_TEST_REL: (
        "setLiveClientForTests", "'doctor'", "{ kind: 'doctor' }", LABEL_DOCTOR, SUMMARY_ALL, SUMMARY_SOME,
        MSG_CANCELLED, TIMEOUT_DOCTOR_TEXT, LEAVE_NOTE,
    ),
}

# 新源码的禁词（与 T054/T055 门禁同一口径）
FORBIDDEN_SOURCE_MARKS = (
    "XMLHttpRequest", "EventSource", "WebSocket", "dangerouslySetInnerHTML", "innerHTML", "outerHTML",
    "insertAdjacentHTML", "eval(", "new Function", "document.write", "srcdoc", "DOMParser",
    "matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver", 'role="status"',
)
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_COLOR_FUNCS = ("rgb(", "rgba(", "hsl(", "hsla(", "color-mix(", "oklch(", "lab(", "hwb(")

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T024/T041/T043/T044/T045/T051/T052/T053/T054/T055 门禁）
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 150}

ASSUMPTIONS = (
    "结果块的 DOM 形状不钉（合同只点名 <dt> 标签逐字）：探针按 dt 标签在它的父元素里找 dd 取值；卡片头按"
    " 整节文字分开断言「✓ 就绪 / ✗ 未就绪」「角色中文名」「profile step-high」，不钉三段之间的空白写法",
    "键值行的次序不钉（合同的表没写明次序），只钉八个标签都在、值配对正确（valuesOf 收集同名 dt 的全部 dd）",
    "汇总「有未就绪的角色（N 个）」的 N 按 roles 里 ready 不为真的个数（合同钉死）：探针用恰好一个未就绪的"
    " 夹具断言逐字「有未就绪的角色（1 个）」",
    "其他角色一行「✓ 角色中文名 · 内核那一行 text」按折叠空白后的包含断言（✓ 与角色名之间的空白不钉）",
    "桩的 doctor 奇偶按作业次序：stub 探针里直接调 api.startJob('doctor') 的那条放在最后，避免它先挪动奇偶计数",
    "视图里 DisabledAction 与 PlayIcon 的 import 应删干净（合同「删干净」）：S05 静态断言整个文件不再出现这两"
    "个记号（PlayIcon 原本只有就绪检查那一处用到）",
    "mock 的 error 开关对 doctor 的示意原文措辞不钉（扫描那一行被 t054 钉死，doctor 的一行示意由执行端定），"
    " stub 探针只断言落 failed 且不显示结果块",
    "RuntimeDoctor 的导出名与内部结构不钉：静态只钉 import 路径、接线记号与逐字文案；行为按渲染 RuntimesView"
    " 的探针断言",
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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043/T044/T045/T051/T052/T053/T054/T055 的同一口径）
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
    """禁词、写死颜色与内联样式的公共核对（T054/T055 等门禁的口径）。"""
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


def _css_class_problems(rel, css):
    """新 CSS：类名一律以 .rd- 开头（不与别的样式表共用类名）；var() 只用 --tt- 令牌（合同写法钉死）。"""
    problems = []
    for m in re.finditer(r"([^{}]+)\{", css):
        selector = m.group(1)
        if selector.strip().startswith("@"):
            continue
        for cm in re.finditer(r"\.([-\w]+)", selector):
            if not cm.group(1).startswith("rd-"):
                problems.append(f"{rel} 的类名 .{cm.group(1)} 应以 rd- 开头（不与别的样式表共用类名）")
    for vm in re.finditer(r"var\((--[\w-]+)", css):
        if not vm.group(1).startswith("--tt-"):
            problems.append(f"{rel} 的变量 {vm.group(1)} 不是 --tt- 令牌")
    return problems


def _api_import_type_only(rel, text):
    """从 ../../api 引入的每一条 import 语句都只能是 import type（t043 :497 与 t009 D13 的口径）。"""
    problems = []
    for m in re.finditer(r"import[^;]*?from\s*['\"]\.\./\.\./api['\"]", text, re.S):
        stmt = m.group(0)
        if not (stmt.lstrip().startswith("import type") or re.search(r"import\s*\{\s*type\b", stmt)):
            problems.append(f"{rel} 的 api 引入不是 import type：{stmt.splitlines()[0][:70]}")
    return problems


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 T044/T045/T051/T052/T053/T054/T055 门禁的写法）
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


def t056_marker_present():
    """候选里是否已有 T056 的标记（新组件 + api/jobStore 里的 'doctor'）：没有就不起 npm（基线上必然没有）。"""
    try:
        doctor = _read(REPO_ROOT / RUNTIMEDOCTOR_REL) if (REPO_ROOT / RUNTIMEDOCTOR_REL).is_file() else ""
        api = _read(REPO_ROOT / API_REL) if (REPO_ROOT / API_REL).is_file() else ""
        store = _read(REPO_ROOT / JOBSTORE_REL) if (REPO_ROOT / JOBSTORE_REL).is_file() else ""
    except OSError:
        return False
    return LABEL_DOCTOR in doctor and "'doctor'" in api and "'doctor'" in store


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t056_marker_present():
        pipe.reason = ("候选里还没有 T056 的标记（src/writes/RuntimeDoctor.tsx、api.ts / jobStore.ts 的 "
                       "'doctor'），没有东西可测，未调用 npm；候选把入口与接线都放进去之后，流水线才会运行 "
                       "npm ci、Vitest 与探针")
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
                    name = f"probe-{uid}-t056-{key}.test.tsx"
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
    """S01 / D01、D06：api.ts——JobKind 四类（含 doctor，取 `export type JobKind = …;` 那一行核对，
    后面再接别的类不必改这里）；startJob 的函数体一个字不改（postRaw、正文逐字 { kind } 与
    { kind, runtime }、201 才算建成、时限 15、桩分支 mockStartJob(kind, runtime)、不许出现
    runtime: undefined）；getJob / cancelJob 照旧在位；JobState 六值与 JobView 八键照旧。"""
    need_file(API_REL)
    api = read_rel(API_REL)
    code = strip_ts_comments(api)
    problems = []
    jk = re.search(r"export type JobKind = ([^;]+);", code)
    if jk is None:
        problems.append("api.ts 应有 export type JobKind = …")
    else:
        for kind in JOBKINDS:
            if f"'{kind}'" not in jk.group(1):
                problems.append(f"api.ts 的 JobKind 应含 '{kind}'")
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
                problems.append(f"startJob 的函数体里应有 {mark}（doctor 不带 runtime 时本来就发 {{ kind }}）")
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
    """S02 / D06：jobStore.ts——KINDS 扩成四类（次序 scan、probe、models、doctor，doctor 在末尾）；
    snaps 与 subscribers 两张 Record<JobKind, …> 各加 doctor 一项；五个既有导出（ensureJob /
    restartJob / cancelJob / useJob / resetJobStoreForTests）与 useBusyRuntime 都在且签名照旧；
    轮询公式与 T055 的字面照旧（setTimeout 链、1000、clearTimeout、已用秒数公式、
    useSyncExternalStore、从 '../api' 引三个作业函数）。"""
    need_file(JOBSTORE_REL)
    text = read_rel(JOBSTORE_REL)
    code = strip_ts_comments(text)
    problems = []
    if not re.search(r"KINDS[^=]*=\s*\[[^\]]*'runtime-scan'[^\]]*'runtime-probe'[^\]]*'models'[^\]]*'doctor'[^\]]*\]",
                     code):
        problems.append("KINDS 应扩成四类 ['runtime-scan', 'runtime-probe', 'models', 'doctor']（doctor 在末尾）")
    for table in ("snaps", "subscribers"):
        m = re.search(rf"const {table}[^=]*=\s*\{{(.*?)\}};", code, re.S)
        if m is None:
            problems.append(f"{table} 的初始化应在位")
        elif "'doctor'" not in m.group(1) and "doctor:" not in m.group(1):
            problems.append(f"{table} 应加 doctor 一项（Record<JobKind, …> 少了会 tsc 报错）")
    for name in ("ensureJob", "restartJob", "cancelJob", "useJob", "resetJobStoreForTests"):
        if f"export function {name}(" not in code:
            problems.append(f"应导出 export function {name}(")
    if "export function useBusyRuntime(" not in code:
        problems.append("useBusyRuntime 应照旧在位")
    for sig in (r"export function ensureJob\(kind: JobKind, runtime\?: string\)",
                r"export function restartJob\(kind: JobKind, runtime\?: string\)",
                r"export function useJob\(kind: JobKind, runtime\?: string\)",
                r"export function cancelJob\(kind: JobKind\)",
                r"export function useBusyRuntime\(kind: JobKind\)"):
        if re.search(sig, code) is None:
            problems.append(f"签名应照合同（doctor 的槽里 runtime 是 null，不带 runtime 参数即 null）：{sig}")
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
    """S03 / D06：JobCard.tsx——三张按 kind 查的表各加 doctor 一项（失败标题「就绪检查失败」、
    进度条 aria-label「就绪检查进行中」、超时 600）；扫描那一支的字面与 'runtime-scan': 150 留在
    文件里；既有 props（title / onCancel / children / kind / failedDetail）与结局文字照旧；
    只引 job-card.css。"""
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
    for mark, what in (("扫描失败", "runtime-scan 失败标题"), (MSG_DOCTOR_FAILED, "doctor 失败标题"),
                       ("探测失败", "runtime-probe 失败标题"), ("列模型失败", "models 失败标题"),
                       ("扫描进行中", "runtime-scan 进度 aria-label"), (ARIA_DOCTOR, "doctor 进度 aria-label"),
                       ("探测进行中", "runtime-probe 进度 aria-label"), ("列模型进行中", "models 进度 aria-label")):
        if mark not in code:
            problems.append(f"三张表里 {what} 应逐字在位：{mark}")
    for pat, what in ((r"['\"]?runtime-scan['\"]?\s*:\s*150", "'runtime-scan': 150"),
                      (r"['\"]?doctor['\"]?\s*:\s*600", "doctor: 600"),
                      (r"['\"]?runtime-probe['\"]?\s*:\s*150", "'runtime-probe': 150"),
                      (r"['\"]?models['\"]?\s*:\s*120", "models: 120")):
        if re.search(pat, code) is None:
            problems.append(f"时限表里应有 {what}")
    for mark, what in ((MSG_CANCELLED, "cancelled 结局"), ("取消", "[取消] 按钮")):
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
    """S04 / D07：桩 mock/jobs.ts——三个既有导出；不用计时器、不引 JSON、不出现 WriteScenario；
    四个 kind 都在；既有扫描夹具与文案一字不改（夹具 path/version、错误一行、409/404 文案、
    found/added）；doctor 夹具在位（STEP_API_KEY、凭据不可用那一条 problems、四个角色照
    roles.json：角色代码、interactive_host、step-high、step-5-preview、交互宿主的说明文字）。"""
    need_file(MOCKJOBS_REL)
    text = read_rel(MOCKJOBS_REL)
    code = strip_ts_comments(text)
    problems = []
    for name in ("mockStartJob", "mockGetJob", "mockCancelJob"):
        if f"export function {name}(" not in code:
            problems.append(f"应导出 export function {name}(")
    if "setTimeout(" in code or "setInterval(" in code:
        problems.append("桩不用计时器：每次调用都回已兑现的 Promise")
    if "WriteScenario" in text:
        problems.append("mock/jobs.ts 不许出现 WriteScenario（不加写情景值）")
    if re.search(r"from ['\"][^'\"]*\.json['\"]", text):
        problems.append("src/mock 不加 JSON（mock/jobs.ts 不引 .json）")
    for token in ("'runtime-scan'", "'runtime-probe'", "'models'", "'doctor'", "'running'", "'succeeded'",
                  "'failed'", "'cancelled'", "'queued'"):
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
    # --- doctor 的夹具 ---
    for mark, what in ((MOCK_CRED_NAME, "doctor 夹具的凭据变量 STEP_API_KEY"),
                       (MOCK_CRED_PROBLEM, "奇数份 problems 的一条（凭据变量不可用）"),
                       ("ready: false", "奇数份 data.ready 为假"), ("ready: true", "偶数份 data.ready 为真"),
                       (MOCK_ROLE_TEXT_HOST, "规划审核端的 text（交互宿主说明）"),
                       ("interactive_host", "规划审核端的 mode"),
                       (MOCK_EXEC_PROFILE, "执行端的 profile step-high"),
                       (MOCK_EXEC_MODEL, "执行端的 model step-5-preview")):
        if mark not in code:
            problems.append(f"桩的 doctor 夹具应有 {what}：{mark}")
    for role in MOCK_ROLE_CODES:
        if f"'{role}'" not in code:
            problems.append(f"桩的 doctor 夹具应含四个角色里的 '{role}'（照 mock/roles.json）")
    problems.extend(_forbidden_marks("mock/jobs.ts", text, code))
    fail_if(problems, "mock/jobs.ts 的写法钉死（S04）")


def test_s05_runtimes_view():
    """S05 / D01、D08：runtimes-RuntimesView.tsx——「就绪检查」一节只渲染 <RuntimeDoctor />
    （div.rt-ready-area 保留在视图里）；DisabledAction 删干净（整个文件不再出现）、PlayIcon 不再
    用到；其余一字不改（runtime.remove、args、reload、useWriteFlow、canProbe、canModels、两节标题、
    版本列照旧「—」、runtimes-styles.css 接线、从 ../../api 只许 import type）。"""
    need_file(RUNTIMESVIEW_REL)
    text = read_rel(RUNTIMESVIEW_REL)
    code = strip_ts_comments(text)
    problems = []
    if re.search(r"<DisabledAction[^>]*label=\"运行就绪检查\"", code):
        problems.append('<DisabledAction label="运行就绪检查" /> 不应再在（换成新组件）')
    if "DisabledAction" in text:
        problems.append("DisabledAction 只在就绪检查那一处用过，应连 import 一起删干净")
    if "PlayIcon" in text:
        problems.append("PlayIcon 原本只有就绪检查那一处用到，应随入口一起删掉（新组件自带）")
    if "'../../writes/RuntimeDoctor'" not in text:
        problems.append("应引入 '../../writes/RuntimeDoctor'")
    if "rt-ready-area" not in code:
        problems.append("div.rt-ready-area 应保留在视图里（虚线框区域还由视图包着）")
    for mark, what in (("'runtime.remove'", "删除走既有 runtime.remove"),
                       ("args: { runtime", "删除的 args 带 runtime"),
                       ("reload?:", "reload 可选属性"), ("useWriteFlow(", "useWriteFlow"),
                       ("canProbe(", "canProbe 规则照旧"), ("canModels(", "canModels 规则照旧"),
                       ('"已登记"', "已登记一节标题"), ('"就绪检查"', "就绪检查一节标题"),
                       ("版本: '—'", "版本列照旧「—」"),
                       ("import './runtimes-styles.css'", "页面样式表接线（.rt-ready 的规则留在那里）")):
        if mark not in text and mark not in code:
            problems.append(f"其余一字不改：{what}（{mark[:40]}）")
    problems.extend(_api_import_type_only("runtimes-RuntimesView.tsx", text))
    problems.extend(_forbidden_marks("runtimes-RuntimesView.tsx", text, code))
    fail_if(problems, "RuntimesView 的换组件（S05）")


def test_s06_runtime_doctor_file():
    """S06 / D01–D05：RuntimeDoctor.tsx——作业接线走 jobStore（ensureJob / restartJob / useJob 用
    'doctor'，不用 useBusyRuntime）；JobCard 从 '../jobs/JobCard' 直接引且 kind="doctor"、
    key={job?.id ?? 'creating'}（每个作业重新挂载）；按钮逐字「运行就绪检查」（secondary/md、
    PlayIcon 16，运行中只禁用不换字）；逐字文案全在（空框新句子、离开页那句、汇总、卡头、八个键值行
    标签、是/否/不限制/无/可用/不可用/已接通/未接通、思考档位两句、来源四标签、角色名四项）；不跨层引
    src/pages；只引 runtime-doctor.css；不用禁词、不写死颜色、不写内联 style。"""
    need_file(RUNTIMEDOCTOR_REL)
    text = read_rel(RUNTIMEDOCTOR_REL)
    code = strip_ts_comments(text)
    problems = []
    for mark, what in (("ensureJob(", "ensureJob"), ("restartJob(", "restartJob"), ("useJob(", "useJob")):
        if mark not in code:
            problems.append(f"应调 jobStore 的 {what}")
    for call in ("ensureJob('doctor')", "restartJob('doctor')", "useJob('doctor')"):
        if call not in code:
            problems.append(f"作业调用应不带 runtime：{call}")
    if "useBusyRuntime" in code:
        problems.append("doctor 这一支不用 useBusyRuntime（同类只有一个作业，没有忙于谁的行）")
    if "JobCard" not in code:
        problems.append("应渲染 JobCard")
    elif "from '../jobs/JobCard'" not in text:
        problems.append("JobCard 应从 '../jobs/JobCard' 直接引入（不进 components/index.ts）")
    if 'kind="doctor"' not in code:
        problems.append('JobCard 应带 kind="doctor"')
    if "key={job?.id ?? 'creating'}" not in code:
        problems.append("JobCard 应带 key={job?.id ?? 'creating'}（每个作业重新挂载，新作业的 [取消] 一出来就可点）")
    if "import './runtime-doctor.css';" not in text:
        problems.append("应 import './runtime-doctor.css'（组件自带样式表）")
    if re.search(r"from\s+'\.\./pages", text) or re.search(r'from\s+"\.\./pages', text):
        problems.append("组件不许跨层引 src/pages（角色名与来源标签照抄小表写在组件里）")
    for mark, what in (('variant="secondary"', "入口 secondary"), ('size="md"', "入口 md"),
                       ("PlayIcon", "PlayIcon 图标"), ("width={16}", "图标 16")):
        if mark not in text and mark not in code:
            problems.append(f"入口按钮应带 {what}：{mark}")
    for mark, what in ((LABEL_DOCTOR, "按钮文字逐字「运行就绪检查」（运行中只禁用不换字）"),
                       (SECTION_TITLE, "作业卡标题「就绪检查」"), (MSG_DOCTOR_FAILED, "「就绪检查失败」在 JobCard 的表里"),
                       (ARIA_DOCTOR, "「就绪检查进行中」在 JobCard 的表里"),
                       (LEAVE_NOTE, "运行中那句「离开这个页面作业也会继续，回来时显示结果。」"),
                       (EMPTY_NOTE, "空框新句子（去掉「运行入口在第二阶段接入」）"),
                       (SUMMARY_ALL, "汇总「全部就绪」"), (SUMMARY_SOME, "汇总「有未就绪的角色」"),
                       (WORD_READY, "卡头「就绪」"), (WORD_NOT_READY, "卡头「未就绪」"),
                       (MARK_READY, "卡头与角色一行的 ✓"), (MARK_NOT_READY, "卡头与角色一行的 ✗"),
                       (PROFILE_PREFIX, "卡头的 profile 前缀"),
                       (YES, "是"), (NO, "否"), (ANY_ALLOWED, "允许列表 null 写「不限制」"),
                       (CREDS_NONE, "凭据空写「无」"), (CREDS_OK, "凭据「可用」"), (CREDS_BAD, "凭据「不可用」"),
                       (CONNECTED, "接通状态「已接通」"), (NOT_CONNECTED, "接通状态「未接通」"),
                       (THINK_OK, "「本机 pi 接受这个档位」"), (THINK_BAD, "「本机 pi 不接受这个档位」"),
                       (SOURCE_SUFFIX, "命令行的「（来源：…）」后缀"),
                       (DASH, "缺键写「—」")):
        if mark not in code:
            problems.append(f"{what}应逐字在位：{mark}")
    for label in ROW_LABELS:
        if f">{label}<" not in code:
            problems.append(f"键值行的 <dt> 标签应逐字在位：{label}")
    for mark, what in ((SOURCE_ENV, "来源标签 环境变量"), (SOURCE_LOCAL, "来源标签 本机文件"),
                       (SOURCE_PATH, "来源标签 PATH"), (SOURCE_MISSING, "来源标签 找不到"),
                       (ROLE_PLANNING, "角色名 规划审核端"), (ROLE_CONTRACT, "角色名 合同端"),
                       (ROLE_EXECUTION, "角色名 执行端"), (ROLE_SCHEDULER, "角色名 调度代理")):
        if mark not in code:
            problems.append(f"照抄小表应逐字在位：{what}（{mark}）")
    css_imports = _css_imports(text)
    if "./runtime-doctor.css" not in css_imports:
        problems.append("应 import './runtime-doctor.css'")
    for other in css_imports:
        if other != "./runtime-doctor.css":
            problems.append(f"不应引别的样式表（{other}；本文件只引 runtime-doctor.css）")
    problems.extend(_forbidden_marks("RuntimeDoctor.tsx", text, code))
    fail_if(problems, "RuntimeDoctor.tsx 的写法钉死（S06）")


def test_s07_runtime_doctor_css():
    """S07 / D08：runtime-doctor.css——类名一律以 .rd- 开头（不与别的样式表共用类名，虚线框的
    .rt-ready 由页面样式表提供）；只用 --tt- 令牌；除 0 与 1px 外的 px 字面量同一行带出处注释；
    不写死颜色。"""
    need_file(RUNTIMEDOCTOR_CSS_REL)
    css = read_rel(RUNTIMEDOCTOR_CSS_REL)
    problems = _forbidden_marks("runtime-doctor.css", css, css)
    problems.extend(_css_px_problems("runtime-doctor.css", css))
    problems.extend(_css_class_problems("runtime-doctor.css", css))
    if not css.strip():
        problems.append("runtime-doctor.css 不应是空文件")
    fail_if(problems, "runtime-doctor.css 的写法钉死（S07）")


def test_s08_executor_test_files():
    """S08 / D09：执行端新测试文件 jobs-doctor-page.test.tsx 在位且要点齐备（合同第 9 步点名的
    覆盖点：真实模式的创建正文与进度与结局、有 data 的 failed、取消与超时、离开页那句、汇总），
    不许 skip/only/todo。"""
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
    """S09 / D10：兼容性一节的旧断言逐处改到位——t009（:2895 标题「可点」、:2904 toBe(false)、:2907 新句子、
    :2970 标题尾段、:2974 白名单加「运行就绪检查」、:2975 toBe(0)）、t023（:805 标题、:808 toBe(false)、
    :809-810 删掉悬停两行、:37 与 :1401 两处文档串）、t043（:491-492 两个记号换成 "RuntimeDoctor"）、
    t045（:560/:563 运行时页 1→0）、t054（:717-718 改成「含这几类」的正则核对）、t055（:109 JOBKINDS 元组、
    :532-533 正则核对、:749 记号换新组件、:918-923 与 :926-929 与 :930-935 反查改成新口径、:889-893 文档串）、
    包内 page-app（运行时页 0、toBe(0)）与 page-runtimes（:115 标题、:119 toBe(false)）；
    旧口径不再残留在这些文件里。"""
    problems = []
    # t009
    t009 = read_rel(T009_GATE_REL)
    if '就绪检查：h2 加可点的 [运行就绪检查]' not in t009:
        problems.append('t009 :2895 的 it 标题只把「禁用」改成「可点」')
    if "expect(b, '应有 [运行就绪检查]').not.toBeNull();\n    expect(b.disabled).toBe(false);" not in t009:
        problems.append('t009 :2904 应改成 toBe(false)（只改 true→false，:2905/:2906 照旧）')
    if "toContain('" + EMPTY_NOTE + "')" not in t009:
        problems.append('t009 :2907 的空框句子应换成新句子（去掉「；运行入口在第二阶段接入」）')
    if EMPTY_NOTE + EMPTY_NOTE_OLD_TAIL in t009:
        problems.append('t009 里不应再残留旧句子「；运行入口在第二阶段接入」')
    if '与 T056 接上的 [运行就绪检查]' not in t009:
        problems.append('t009 :2970 的 it 标题应加「与 T056 接上的 [运行就绪检查]」')
    if '与 T055 接上的 [探测]、[模型]' not in t009:
        problems.append('t009 :2970 的 it 标题应保留「与 T055 接上的 [探测]、[模型]」这一段（t055 门禁认它）')
    if "'扫描 PATH', '探测', '模型'" not in t009:
        problems.append('t009 :2974 的「扫描 PATH / 探测 / 模型」要照旧连着写（t055 门禁认它）')
    if "'模型', '运行就绪检查'" not in t009:
        problems.append('t009 :2974 的白名单应在「模型」后面加「运行就绪检查」')
    if 'expect(disabledButtons().length).toBe(0);' not in t009:
        problems.append('t009 :2975 应改成 expect(disabledButtons().length).toBe(0);')
    # t023
    t023 = read_rel(T023_GATE_REL)
    if '[运行就绪检查] 可点（secondary 带 PlayIcon），空框原文照旧' not in t023:
        problems.append('t023 :805 的 it 标题应改成「[运行就绪检查] 可点（secondary 带 PlayIcon），空框原文照旧」')
    if 'expect(ready.disabled).toBe(false);' not in t023:
        problems.append('t023 :808 应改成 toBe(false)')
    if 'expect(ready.disabled).toBe(true);' in t023:
        problems.append('t023 里不应再残留 expect(ready.disabled).toBe(true);')
    if 'tipOf(ready)' in t023:
        problems.append('t023 :809-810 两行应删掉（vi.useFakeTimers 与悬停提示断言）')
    if '[编辑] 照旧禁用提示「第二阶段接入」、[运行就绪检查] 可点' not in t023:
        problems.append('t023 :37 的文档串应改成「[编辑] 照旧禁用提示「第二阶段接入」、[运行就绪检查] 可点」')
    if '[编辑] 照旧禁用、[运行就绪检查] 可点' not in t023:
        problems.append('t023 :1401 的文档串应改成「[编辑] 照旧禁用、[运行就绪检查] 可点」')
    if '[运行就绪检查] 照旧禁用' in t023:
        problems.append('t023 里不应再残留「[运行就绪检查] 照旧禁用」的说法')
    # t043
    t043 = read_rel(T043_GATE_REL)
    if '"RuntimeDoctor", "runtime.remove"' not in t043:
        problems.append('t043 :491-492 应把「还没有运行过就绪检查」与 label="运行就绪检查" 两个记号换成 "RuntimeDoctor"')
    if '"还没有运行过就绪检查"' in t043:
        problems.append('t043 里不应再残留记号 "还没有运行过就绪检查"（文案挪进新组件）')
    if "'label=\"运行就绪检查\"'" in t043:
        problems.append("t043 里不应再残留记号 'label=\"运行就绪检查\"'（入口换成新组件）")
    # t045
    t045 = read_rel(T045_GATE_REL)
    if '、运行时页 0、总览 0' not in t045:
        problems.append('t045 :560 正则里的「运行时页 1」应改成「运行时页 0」')
    if r'("运行时页 0", r"toBe\(0\)"), ("总览 0", r"toBe\(0\)")' not in t045:
        problems.append(r't045 :563 应改成 (("运行时页 0", r"toBe\(0\)"), ("总览 0", r"toBe\(0\)"))')
    if '运行时页 1' in t045:
        problems.append('t045 里不应再残留「运行时页 1」')
    # t054
    t054 = read_rel(T054_GATE_REL)
    if 'r"export type JobKind = ([^;]+);"' not in t054:
        problems.append('t054 :717-718 应改成取 export type JobKind = …; 那一行的正则核对')
    if 'for kind in ("runtime-scan", "runtime-probe", "models", "doctor"):' not in t054:
        problems.append('t054 :717-718 应核对含 doctor 在内的四类（后面接别的片不必再改）')
    if "if \"export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';\" not in code:" in t054:
        problems.append('t054 里不应再残留三类的逐字记号断言')
    if 'export type JobState = ([^;]+);' not in t054:
        problems.append('t054 :719 起的 JobState 检查照旧，不许改')
    if 'function toJobView(' not in t054 or '("startJob", ("postRaw",)' not in t054:
        problems.append('t054 :719 起的 toJobView 与 startJob/getJob/cancelJob 各项照旧，不许改')
    # t055
    t055 = read_rel(T055_GATE_REL)
    if 'JOBKINDS = ("runtime-scan", "runtime-probe", "models", "doctor")' not in t055:
        problems.append('t055 :109 应改成 JOBKINDS = 四类元组')
    if 'JOBKIND_THREE' in t055:
        problems.append('t055 里不应再残留 JOBKIND_THREE 的旧记号')
    if 'jk = re.search(r"export type JobKind = ([^;]+);", code)' not in t055:
        problems.append('t055 :532-533 应改成取 JobKind 那一行的正则核对')
    if 'for kind in JOBKINDS:' not in t055:
        problems.append('t055 :532-533 应按 JOBKINDS 元组核对「含这几类」')
    if "(\"'../../writes/RuntimeDoctor'\", \"就绪检查走新组件\")," not in t055:
        problems.append("t055 :749 的 S05 记号应换成 (\"'../../writes/RuntimeDoctor'\", \"就绪检查走新组件\") 照合同 :391 逐字")
    if "('label=\"运行就绪检查\"', \"[运行就绪检查] 仍禁用\")," in t055:
        problems.append('t055 :749 里不应再残留 仍禁用 的旧记号')
    if 'if "运行时页 0" not in t045:' not in t055:
        problems.append('t055 :918-923 反查 t045 的「运行时页」应改成 0')
    if '("运行时页 0", r"toBe' not in t055:
        problems.append('t055 :918-923 反查 t045 的 toBe 匹配应改成新写法')
    if '("运行时页 1", r"toBe' in t055:
        problems.append('t055 里不应再残留 运行时页 1 的旧反查')
    if 'if "运行时页 1" in t045:' not in t055:
        problems.append('t055 :918-923 应加一条 运行时页 1 在 t045 的残留检查')
    if '"export type JobKind = ([^;]+);" not in t054' not in t055:
        problems.append('t055 :926-929 反查 t054 应改成核对新写法')
    if "expect(disabled().length, '运行时页').toBe(0)\" not in app_test" not in t055:
        problems.append('t055 :930-935 反查包内 page-app 应认 toBe(0) 的新写法')
    if '运行时页 1→0' not in t055:
        problems.append('t055 :889-893 的 S09 文档串应改成 运行时页 1→0 的说法')
    if '运行时页 4→1' in t055:
        problems.append('t055 里不应再残留 运行时页 4→1 的说法')
    # 包内 page-app
    app_test = read_rel(PAGE_APP_TEST_REL)
    if "describe('写入口个数（过渡）'" not in app_test:
        problems.append('page-app 的 describe 标题「写入口个数（过渡）」一字不动（t037 S06、t045 认它）')
    if '运行时页 0' not in app_test:
        problems.append('page-app :93 的 it 标题里「运行时页 1」应改成「运行时页 0」')
    if "expect(disabled().length, '运行时页').toBe(0)" not in app_test:
        problems.append("page-app :98 应改成 expect(disabled().length, '运行时页').toBe(0)")
    if '运行时页 1' in app_test:
        problems.append('page-app 里不应再残留「运行时页 1」')
    # 包内 page-runtimes
    rt_test = read_rel(PAGE_RUNTIMES_TEST_REL)
    if '[运行就绪检查] 可点 secondary 带 PlayIcon' not in rt_test:
        problems.append('page-runtimes :115 的 it 标题应改成 可点 的新标题')
    if 'expect(b?.disabled).toBe(false);' not in rt_test:
        problems.append('page-runtimes :119 应改成 toBe(false)')
    if 'expect(b?.disabled).toBe(true);' in rt_test:
        problems.append('page-runtimes 里不应再残留 expect(b?.disabled).toBe(true);')
    if "toContain('还没有运行过就绪检查。')" not in rt_test:
        problems.append("page-runtimes :123 的 toContain('还没有运行过就绪检查。') 照旧")
    fail_if(problems, '兼容性一节的旧断言（S09）')


# ---------------------------------------------------------------------------
# 探针（黑盒 Vitest 用例，临时写进 desktop/web/gate-probe/，跑完即删；每份自带全部辅助函数）
# 探针直接渲染 RuntimesView（照包内 page-runtimes.test.tsx 的既有写法注入 runtimes 与 quizs，不 mock 被测组件）。
# ---------------------------------------------------------------------------

DOCTOR_PROBE = r'''
// T056 门禁 probe 探针（真实模式）：setLiveClientForTests 注入假服务记录作业请求，看 [运行就绪检查] 的创建正文、
// 进度、结果块（汇总/就绪卡/其他角色一行）、有 data 的 failed、缺键写「—」、取消与超时 600、卸载再挂载与
// 再点新作业、创建失败。每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { RuntimesView } from '../src/pages/readonly1/runtimes-RuntimesView';
import { resetJobStoreForTests } from '../src/jobs/jobStore';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

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
function sectionNamed(root: any, title: string): any {
  return qa(root, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    return text(id ? document.getElementById(id) : null) === title;
  });
}
function readySection(root: any): any {
  const sec = sectionNamed(root, '就绪检查');
  expect(sec, '应有「就绪检查」一节').toBeTruthy();
  return sec;
}
function errEnv(message: string): any {
  return { ok: false, exit_code: 1, data: null, output: [], messages: [message], command: [], elapsed_ms: 0 };
}
function doctorEnv(data: any, ok: boolean): any {
  return { ok, exit_code: ok ? 0 : 1, data, output: [], messages: [], command: ['config', 'doctor', '--json'], elapsed_ms: 1 };
}
function valuesOf(root: any, label: string): string[] {
  return qa(root, 'dt').filter((el: any) => text(el) === label).map((el: any) => {
    const dd = el.parentElement ? el.parentElement.querySelector('dd') : null;
    return dd ? text(dd) : '';
  });
}

const PLANNING = { role: 'planning_review', mode: 'interactive_host', problems: [], text: 'interactive_host · claude-code（交互宿主的模型不由 Themis 切换）', ready: true };
const CONTRACT_MANUAL = { role: 'contract', mode: 'manual', problems: [], text: 'manual', ready: true };
const SCHEDULER = { role: 'scheduler_agent', mode: 'disabled', problems: [], text: 'disabled', ready: true };
const HEAD_OK = { role: 'execution', mode: 'headless', problems: [], profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, notes: ['说明一行（示意）'], allowed: null, credentials: { STEP_API_KEY: true }, ready: true, command: ['node', 'pi.js'], source: 'local', version: '0.1.2', model_listed: true, auth_ready: true, thinking_supported: true };
const HEAD_BAD = { ...HEAD_OK, problems: ['凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY'], credentials: { STEP_API_KEY: false }, ready: false, notes: [] };
const HEAD_MISSING = { role: 'contract', mode: 'headless', problems: [], profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, notes: [], allowed: null, credentials: {}, ready: true };
const HEAD_REJECT = { role: 'execution', mode: 'headless', problems: ['思考级别 high 不受本机 pi 支持'], profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: false, notes: [], allowed: true, credentials: { STEP_API_KEY: false, OTHER_TOKEN: true }, ready: false, command: ['pi'], source: 'path', version: '9.9.9', model_listed: false, auth_ready: false, thinking_supported: false };
const ALL_READY = { ready: true, roles: [PLANNING, CONTRACT_MANUAL, HEAD_OK, SCHEDULER] };
const EXEC_NOT_READY = { ready: false, roles: [PLANNING, CONTRACT_MANUAL, HEAD_BAD, SCHEDULER] };
const PARTIAL = { ready: false, roles: [PLANNING, HEAD_MISSING, HEAD_REJECT, SCHEDULER] };

const RUNTIMES = [
  { id: 'pi', adapter: 'pi', source: 'local', command: ['pi'], notes: [] },
  { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['claude'], notes: [] },
] as any;
const QUIZS = {
  providers: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { providers: [] } },
  live: { ok: true, exit_code: 0, output: [], messages: [], command: [], elapsed_ms: 0, data: { live: [] } },
} as any;

let seq = 0;
let jobState = 'running';
let jobEnvelope: any = null;
let createStatus = 201;
let creates: any[] = [];
let cancels: any[] = [];
let queries: string[] = [];

function viewFor(id: string): any {
  const terminal = ['succeeded', 'failed', 'cancelled', 'timed_out'].indexOf(jobState) >= 0;
  return {
    id, kind: 'doctor', state: jobState, reason: null,
    created_ms: 1, started_ms: jobState === 'queued' ? null : 2, finished_ms: terminal ? 3 : null,
    envelope: jobEnvelope,
  };
}

const fake: LiveClient = {
  get(path: string): Promise<any> { return Promise.resolve({ status: 404, body: null }); },
  post(path: string, body: unknown): Promise<any> { return Promise.resolve({ status: 404, body: null }); },
  getRaw(path: string): Promise<any> {
    if (path.indexOf('/api/v1/jobs/') === 0 && path.indexOf('/cancel') < 0) {
      queries.push(path);
      const id = path.slice('/api/v1/jobs/'.length);
      return Promise.resolve({ status: 200, body: viewFor(id) });
    }
    return Promise.resolve({ status: 404, body: null });
  },
  postRaw(path: string, body: unknown): Promise<any> {
    if (path === '/api/v1/jobs') {
      creates.push(body);
      if (createStatus !== 201) return Promise.resolve({ status: createStatus, body: errEnv('ERROR 不支持这个作业') });
      seq += 1;
      return Promise.resolve({ status: 201, body: { id: 'job-doctor-' + seq, kind: 'doctor', state: 'queued', reason: null, created_ms: 1, started_ms: null, finished_ms: null, envelope: null } });
    }
    if (path.indexOf('/api/v1/jobs/') === 0 && path.endsWith('/cancel')) {
      cancels.push(body);
      jobState = 'cancelled';
      const id = path.slice('/api/v1/jobs/'.length, path.length - '/cancel'.length);
      return Promise.resolve({ status: 200, body: viewFor(id) });
    }
    return Promise.resolve({ status: 404, body: null });
  },
};

beforeEach(() => {
  seq = 0;
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

function mountReady(): ReturnType<typeof render> {
  return render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
}

describe('就绪检查（真实模式）', () => {
  it('(a) 空态可点 secondary/md 带 PlayIcon、虚线框新句子、没有作业卡；点击创建正文恰一个键，进度与已用秒数与 [取消]、离开页那句、按钮禁用、每秒查同一个作业号', async () => {
    const r = mountReady();
    const sec = readySection(r.container);
    const b = btnIn(sec, '运行就绪检查');
    expect(b.disabled, '还没跑过时按钮可点').toBe(false);
    expect(b.getAttribute('data-variant')).toBe('secondary');
    expect(b.getAttribute('data-size')).toBe('md');
    expect(b.querySelector('svg'), 'PlayIcon').not.toBeNull();
    expect(text(sec), '虚线框新句子').toContain('还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据。');
    expect(qa(sec, '[role="progressbar"]').length, '没跑过不渲染作业卡').toBe(0);
    fireEvent.click(b);
    await flush();
    expect(creates.length, '只发一次创建').toBe(1);
    expect(creates[0], '创建正文恰一个键').toEqual({ kind: 'doctor' });
    expect(Object.keys(creates[0]).length).toBe(1);
    const again = btnIn(sec, '运行就绪检查');
    expect(again.textContent, '运行中只禁用不换字').toBe('运行就绪检查');
    expect(again.disabled, '运行中按钮禁用').toBe(true);
    const bar = qa(sec, '[role="progressbar"]')[0];
    expect(bar, '运行中应有进度条').toBeTruthy();
    expect(bar.getAttribute('aria-label'), '进度条 aria-label').toBe('就绪检查进行中');
    expect(text(sec)).toMatch(/已用 \d+ 秒/);
    expect(text(sec), '运行中那句提示').toContain('离开这个页面作业也会继续，回来时显示结果。');
    expect(btnIn(sec, '取消'), '有 [取消]').toBeTruthy();
    await act(async () => { await sleep(2200); });
    expect(queries.length, '每秒查一次').toBeGreaterThanOrEqual(2);
    expect(queries.every((p) => p === '/api/v1/jobs/job-doctor-1'), '查询同一个作业号').toBe(true);
  }, 20000);

  it('(b) succeeded：汇总全部就绪；就绪卡卡头与八个键值行（命令带来源、思考档位、凭据可用、允许列表不限制、已接通）、说明行；其他角色各一行', async () => {
    jobState = 'succeeded';
    jobEnvelope = doctorEnv(ALL_READY, true);
    const r = mountReady();
    fireEvent.click(btnIn(readySection(r.container), '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(1300); });
    const sec = readySection(r.container);
    const t = text(sec);
    expect(t, '汇总').toContain('全部就绪');
    expect(t, '卡头 ✓ 就绪').toContain('✓ 就绪');
    expect(t, '卡头有角色中文名').toContain('执行端');
    expect(t, '卡头有 profile').toContain('profile step-high');
    expect(valuesOf(sec, '命令'), '命令空格连，后接来源').toEqual(['node pi.js（来源：本机文件）']);
    expect(valuesOf(sec, '版本')).toEqual(['0.1.2']);
    expect(valuesOf(sec, '模型在列表中')).toEqual(['是']);
    expect(valuesOf(sec, '登录')).toEqual(['是']);
    expect(valuesOf(sec, '思考级别')).toEqual(['high（本机 pi 接受这个档位）']);
    expect(valuesOf(sec, '允许列表')).toEqual(['不限制']);
    expect(valuesOf(sec, '凭据')).toEqual(['STEP_API_KEY 可用']);
    expect(valuesOf(sec, '接通状态')).toEqual(['已接通']);
    expect(t, '说明行').toContain('说明一行（示意）');
    expect(t, 'problems 为空不渲染问题列表').not.toContain('凭据变量不可用');
    expect(t, '其他角色一行：规划审核端').toContain('✓ 规划审核端');
    expect(t).toContain('interactive_host · claude-code（交互宿主的模型不由 Themis 切换）');
    expect(t, '其他角色一行：合同端').toContain('✓ 合同端');
    expect(t, '合同端的内核行').toContain('manual');
    expect(t, '其他角色一行：调度代理').toContain('✓ 调度代理');
    expect(t, '调度代理的内核行').toContain('disabled');
    expect(qa(sec, '[role="progressbar"]').length, '终态后没有进度条').toBe(0);
    expect(btnIn(sec, '运行就绪检查').disabled, '结束后按钮可点').toBe(false);
  }, 20000);

  it('(c) failed 带 data：照样显示结果块，汇总「有未就绪的角色（1 个）」，问题列表在，✗ 未就绪，不显示「就绪检查失败」与内核报错', async () => {
    jobState = 'failed';
    jobEnvelope = doctorEnv(EXEC_NOT_READY, false);
    const r = mountReady();
    fireEvent.click(btnIn(readySection(r.container), '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(1300); });
    const sec = readySection(r.container);
    const t = text(sec);
    expect(t, '汇总带个数').toContain('有未就绪的角色（1 个）');
    expect(t, '卡头 ✗ 未就绪').toContain('✗ 未就绪');
    expect(t, '问题列表在').toContain('凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY');
    expect(t, '凭据不可用').toContain('STEP_API_KEY 不可用');
    expect(t, '不显示笼统的失败标题').not.toContain('就绪检查失败');
    expect(t, '不显示内核报错').not.toContain('内核报错');
    expect(qa(sec, '[role="progressbar"]').length).toBe(0);
    expect(btnIn(sec, '运行就绪检查').disabled, '终态后按钮可点').toBe(false);
  }, 20000);

  it('(d) 无头行缺键写「—」；凭据为空写「无」；思考不支持写「本机 pi 不接受这个档位」；允许列表真写「是」；两个凭据变量用「、」连', async () => {
    jobState = 'failed';
    jobEnvelope = doctorEnv(PARTIAL, false);
    const r = mountReady();
    fireEvent.click(btnIn(readySection(r.container), '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(1300); });
    const sec = readySection(r.container);
    const t = text(sec);
    expect(t, '汇总按未就绪的个数').toContain('有未就绪的角色（1 个）');
    expect(valuesOf(sec, '命令'), '缺键写「—」').toContain('—');
    expect(valuesOf(sec, '命令'), '在列表的那行照常带来源').toContain('pi（来源：PATH）');
    expect(valuesOf(sec, '版本')).toContain('—');
    expect(valuesOf(sec, '版本')).toContain('9.9.9');
    expect(valuesOf(sec, '模型在列表中')).toContain('—');
    expect(valuesOf(sec, '模型在列表中')).toContain('否');
    expect(valuesOf(sec, '登录')).toContain('—');
    expect(valuesOf(sec, '登录')).toContain('否');
    expect(valuesOf(sec, '思考级别')).toContain('—');
    expect(valuesOf(sec, '思考级别'), '不接受这个档位').toContain('high（本机 pi 不接受这个档位）');
    expect(valuesOf(sec, '允许列表')).toContain('不限制');
    expect(valuesOf(sec, '允许列表'), '真写「是」').toContain('是');
    expect(valuesOf(sec, '凭据'), '空写「无」').toContain('无');
    expect(valuesOf(sec, '凭据'), '两个变量用「、」连').toContain('STEP_API_KEY 不可用、OTHER_TOKEN 可用');
    expect(valuesOf(sec, '接通状态')).toContain('已接通');
    expect(valuesOf(sec, '接通状态')).toContain('未接通');
    expect(t, '两行卡头：✓ 与 ✗').toContain('✓ 就绪');
    expect(t).toContain('✗ 未就绪');
    expect(t, '问题列表在').toContain('思考级别 high 不受本机 pi 支持');
  }, 20000);

  it('(e) failed 没有 data：显示「就绪检查失败」与内核报错原文，不显示结果块', async () => {
    jobState = 'failed';
    jobEnvelope = errEnv('ERROR: 就绪检查示意');
    const r = mountReady();
    fireEvent.click(btnIn(readySection(r.container), '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(1300); });
    const sec = readySection(r.container);
    const t = text(sec);
    expect(t, '失败标题').toContain('就绪检查失败');
    expect(t, '内核原文照显示').toContain('ERROR: 就绪检查示意');
    expect(t, '没有汇总').not.toContain('全部就绪');
    expect(t, '没有结果块').not.toContain('有未就绪的角色');
    expect(t, '没有就绪卡').not.toContain('profile ');
  }, 20000);

  it('(f) 已取消显示「已取消」；结束后再点是新作业，超时显示「超时（超过 600 秒），已停止」', async () => {
    jobState = 'cancelled';
    const r = mountReady();
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(1300); });
    expect(text(sec), '取消后落已取消').toContain('已取消');
    jobState = 'timed_out';
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    expect(creates.length, '结束后再点是新作业').toBe(2);
    await act(async () => { await sleep(1300); });
    expect(text(sec), '超时 600').toContain('超时（超过 600 秒），已停止');
  }, 20000);

  it('(g) 卸载再挂载看到同一个作业、不再发创建请求；跑完显示结果；结束后再点发新的创建请求', async () => {
    const r = mountReady();
    fireEvent.click(btnIn(readySection(r.container), '运行就绪检查'));
    await flush();
    cleanup();
    const r2 = mountReady();
    const sec2 = readySection(r2.container);
    expect(creates.length, '重挂载不再创建').toBe(1);
    expect(qa(sec2, '[role="progressbar"]').length, '回来还是同一个作业（在跑）').toBeGreaterThanOrEqual(1);
    const q = queries.length;
    await act(async () => { await sleep(1300); });
    expect(queries.length, '回来后照查').toBeGreaterThan(q);
    jobState = 'succeeded';
    jobEnvelope = doctorEnv(ALL_READY, true);
    await act(async () => { await sleep(1300); });
    expect(text(sec2), '跑完显示结果').toContain('全部就绪');
    fireEvent.click(btnIn(sec2, '运行就绪检查'));
    await flush();
    expect(creates.length, '结束后再点是重新检查（新作业）').toBe(2);
    expect(creates[1]).toEqual({ kind: 'doctor' });
  }, 20000);

  it('(h) 点 [取消] 只发一次（正文恰 {}）；取消之后再点 [运行就绪检查]，新作业的 [取消] 一出来就可点', async () => {
    const r = mountReady();
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    fireEvent.click(btnIn(sec, '取消'));
    await flush();
    expect(cancels.length, '只发一次取消').toBe(1);
    expect(cancels[0], '取消正文恰 {}').toEqual({});
    await act(async () => { await sleep(1300); });
    expect(text(sec), '取消后落已取消').toContain('已取消');
    jobState = 'running';
    jobEnvelope = null;
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    expect(creates.length, '再点是新作业').toBe(2);
    const cancel2 = btnIn(sec, '取消');
    expect(cancel2.disabled, '新作业的 [取消] 可点（JobCard 按作业号重新挂载）').toBe(false);
  }, 20000);

  it('(i) 创建失败 400：显示「就绪检查失败」与错误原文；按钮可点，点了重建', async () => {
    createStatus = 400;
    const r = mountReady();
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    expect(creates.length).toBe(1);
    const t = text(sec);
    expect(t, '失败标题').toContain('就绪检查失败');
    expect(t, '错误原文').toContain('ERROR 不支持这个作业');
    expect(btnIn(sec, '运行就绪检查').disabled, '创建失败后按钮可点').toBe(false);
    createStatus = 201;
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    expect(creates.length, '点了重建').toBe(2);
  }, 20000);

  it('(j) 没点过：不排每秒空转的计时器，也没有作业请求', async () => {
    const spy = vi.spyOn(globalThis, 'setTimeout');
    mountReady();
    await act(async () => { await sleep(2600); });
    const sec = spy.mock.calls.filter((c: any[]) => c[1] === 1000);
    expect(sec.length, '没有作业时不排 1000 毫秒的计时器').toBe(0);
    expect(creates.length).toBe(0);
    expect(queries.length, '没点过就没有作业请求').toBe(0);
    spy.mockRestore();
  }, 20000);
});
'''


STUB_PROBE = r'''
// T056 门禁 stub 探针（桩模式，不注入客户端）：?mock= 开关下 doctor 的奇偶两份与 loading/error；
// 直接调 api.startJob 看 doctor 不带 runtime 也放行（放在最后，避免挪动奇偶计数）。每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
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
function sectionNamed(root: any, title: string): any {
  return qa(root, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    return text(id ? document.getElementById(id) : null) === title;
  });
}
function readySection(root: any): any {
  const sec = sectionNamed(root, '就绪检查');
  expect(sec, '应有「就绪检查」一节').toBeTruthy();
  return sec;
}

const RUNTIMES = [
  { id: 'pi', adapter: 'pi', source: 'local', command: ['pi'], notes: [] },
  { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['claude'], notes: [] },
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

describe('桩模式：doctor 作业', () => {
  it('(a) data 开关：奇数份 failed 带 data（汇总与问题列表、凭据不可用、✗ 未就绪、不显示就绪检查失败），再点是偶数份全部就绪', async () => {
    setMock('data');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    expect(qa(sec, '[role="progressbar"]').length, '第一次查询前是 running').toBeGreaterThanOrEqual(1);
    expect(btnIn(sec, '运行就绪检查').disabled, '运行中按钮禁用').toBe(true);
    await act(async () => { await sleep(2400); });
    let t = text(sec);
    expect(t, '奇数份落 failed 带 data：汇总').toContain('有未就绪的角色（1 个）');
    expect(t, '卡头 ✗ 未就绪').toContain('✗ 未就绪');
    expect(t, '问题列表在').toContain('凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY');
    expect(t, '凭据不可用').toContain('STEP_API_KEY 不可用');
    expect(t, '不显示笼统的失败标题').not.toContain('就绪检查失败');
    expect(btnIn(sec, '运行就绪检查').disabled, '终态后按钮可点').toBe(false);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(2400); });
    t = text(sec);
    expect(t, '偶数份全部就绪').toContain('全部就绪');
    expect(t, '凭据可用').toContain('STEP_API_KEY 可用');
    expect(t, '没有未就绪的卡头').not.toContain('✗ 未就绪');
  }, 20000);

  it('(b) loading 开关：一直 running（进度条 aria-label 与已用秒数），按钮一直禁用', async () => {
    setMock('loading');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(2200); });
    expect(qa(sec, '[role="progressbar"]').length, 'loading 一直 running').toBeGreaterThanOrEqual(1);
    const bar = qa(sec, '[role="progressbar"]')[0];
    expect(bar.getAttribute('aria-label')).toBe('就绪检查进行中');
    expect(text(sec)).toMatch(/已用 \d+ 秒/);
    expect(btnIn(sec, '运行就绪检查').disabled, '运行中按钮禁用').toBe(true);
  }, 20000);

  it('(c) error 开关：落 failed 且没有 data，显示就绪检查失败，不显示结果块', async () => {
    setMock('error');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, '落 failed').toContain('就绪检查失败');
    expect(t, '没有汇总').not.toContain('全部就绪');
    expect(t, '没有结果块').not.toContain('有未就绪的角色');
    expect(t, '没有就绪卡').not.toContain('profile ');
  }, 20000);

  it('(d) startJob 不带 runtime 也放行 doctor（201；缺 runtime 回 400 的只该是 runtime-probe 与 models）', async () => {
    const reply = await startJob('doctor');
    expect(reply.status, 'doctor 不带 runtime 应放行').toBe(201);
  }, 20000);
});
'''


PROBE_SPECS = {
    "probe": (DOCTOR_PROBE, (RUNTIMEDOCTOR_REL, RUNTIMESVIEW_REL, JOBSTORE_REL, TRANSPORT_REL, MODE_REL, API_REL)),
    "stub": (STUB_PROBE, (RUNTIMEDOCTOR_REL, RUNTIMESVIEW_REL, JOBSTORE_REL, MOCKJOBS_REL, API_REL, MODE_REL)),
}
PROBE_ORDER = ("probe", "stub")


# ---------------------------------------------------------------------------
# P 系列：流水线断言；D 系列：探针断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V02、D12：npm 依赖（已在就跳过重装）、npm test（全绿，含执行端新测试与既有包内测试）都退出 0；
    依赖文件一个字节没动；gate-probe/ 没有留下。"""
    assert any(pipeline.steps.get(k) is not None and pipeline.steps[k].code == 0
               for k in ("npm ci", "npm ci --offline")), \
        f"npm ci（含 --offline 兜底）未成功：{pipeline.stopped_reason or pipeline.reason}"
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


def test_d01_doctor_probe(pipeline):
    """probe 探针 / D01–D05（真实模式，假服务看真实正文）：空态与创建正文恰 {"kind":"doctor"}、进度与已用秒数
    与离开页那句、每秒查同一个作业号；succeeded 的结果块（汇总、就绪卡、八个键值行、其他角色一行）；failed 带
    data 照样显示结果块（不显示就绪检查失败）；缺键写「—」与思考档位与凭据；failed 没有 data 只显内核原文；
    已取消与超时 600；卸载再挂载同一作业、结束后再点新创建；取消之后再点新作业的 [取消] 可点；创建失败 400
    与重建；没有作业时不排计时器。"""
    assert_probe_ok(pipeline, "probe")


def test_d02_stub_probe(pipeline):
    """stub 探针 / D07（桩模式）：doctor 不带 runtime 也放行（201）；data 开关下奇数份 failed 带 data、再点
    偶数份全部就绪；loading 一直 running 且按钮禁用；error 落 failed 没有 data。"""
    assert_probe_ok(pipeline, "stub")
