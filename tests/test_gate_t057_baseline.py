"""T057 战前门禁：桌面端前端「[核验]：就绪检查一节加『按版本记录核验』，结果卡写明版本记录」的黑盒基准测试
（合同 t057-desktop-web-runtime-record.v1，基线 a7168a13）。

被测对象是「就绪检查」一节在 [运行就绪检查] 后面接的一组「按版本记录核验」（文本框 + [核验] 按钮，同一行），
与它背后的作业客户端扩一类（doctor-record）：

- ``api.ts``：``JobKind`` 扩成五类（doctor-record 加在末尾）；``startJob`` 签名逐字不改，正文多一支
  ``{ kind, record: runtime }``（kind 是 doctor-record 且带值时），原有的 ``{ kind }`` 与 ``{ kind, runtime }``
  两个字面保留；201 才算建成；时限 15；桩分支 ``mockStartJob(kind, runtime)``；不许出现 ``runtime: undefined``。
- ``jobStore.ts``：``KINDS`` 扩成五类（次序 scan、probe、models、doctor、doctor-record）；``snaps`` 与
  ``subscribers`` 两张 ``Record<JobKind, …>`` 各加 doctor-record 一项；五个既有导出与 ``useBusyRuntime``
  的签名一个字不改；T055 的公式（setTimeout 链、1000、clearTimeout、已用秒数、useSyncExternalStore）照旧。
- ``JobCard.tsx``：只在三张按 kind 查的表里各加 doctor-record 一项（失败标题「核验失败」、进度条 aria-label
  「核验进行中」、超时 600）；扫描、探测、列模型、就绪检查四支的字面与 ``runtime-scan: 150`` 一字不动。
- ``RuntimeDoctor.tsx``（T056 的组件，本片只加不删）：根部横排容器 ``.rd-entries`` 里 [运行就绪检查] 原样 +
  核验组 ``.rd-record``（``TextField``（label 逐字「按版本记录核验」、mono、不带 list）+ [核验] 按钮
  （secondary/md、无图标））；``PLAN_KEY_RE`` 照 ``jobroutes.ts:22`` 抄在本文件里；值不合格（空、大写、没有
  ``.v``、``v0``、含空格）不发请求、提示逐字「写成 <task-id>.v<N>，例如 logs-cat.v2」（TextField 的 error，
  改文本框或点了一个合格的值时清掉）；合格时依次 ``restartJob('doctor-record', 值)``、
  ``ensureJob('doctor-record', 值)``（在途的创建共用，只发一次创建请求）；``useJob('doctor-record')`` 管状态，
  JobCard 用 ``kind="doctor-record"``、``title="版本记录核验"``、``key={job?.id ?? 'creating'}``；结果块（标题
  逐字「版本记录 <roles[0].record>」（缺键写「—」）+ 每行一张 T056 的就绪卡、不加汇总行）在自己的容器
  ``.rd-record-body`` 里；succeeded 放 JobCard 的 children 里，有 data 的 failed 不渲染 JobCard（不出现笼统的
  「核验失败」），没有 data 的 failed 与取消、超时交给 JobCard；[核验] 的禁用只看 doctor-record 这一类作业
  是否在创建、排队或运行，空闲时一直可点（运行时页禁用按钮数照旧是 0），与 [运行就绪检查] 各管各的禁用。
- 桩 ``mock/jobs.ts``：doctor-record 不带记录值回 400；``logs-cat.v2`` 给有 data 的结果（那一行是 doctor 的
  无头行加一个 ``record`` 键，值 ``.agent/runs/logs-cat/binding-v2.json``；奇数次没就绪落 failed 带 data、
  偶数次就绪 succeeded，**计数独立于 doctor 的 doctorCounts**）；别的记录落 failed、没有 data，messages 一行
  「<记录> 还没有版本记录：第一次 prepare 才会建立；核验当前绑定用 config doctor」；``kindFailedEnvelope``
  与 ``terminalEnvelope`` 各加 doctor-record 一支；既有四支一字不改。
- 兼容性：t009 的 :2895/:2909/:2970/:2974 与 page-runtimes 的 :116/:125 逐处只改合同写明的那一处（[核验] 在
  「就绪检查」一节里、可点、白名单加「核验」），t009 :2903-2908、:2975 与包内 page-app/readonly2 的过渡断言
  一条都不推翻。

基线（a7168a13）上 api.ts 只有四类 JobKind、RuntimeDoctor 没有核验组、t009/page-runtimes 仍钉着「没有
[核验]」，所以本文件的失败落在「记号不在」「旧断言还在」「流水线没跑」这类断言上，不是导入、收集或语法错误：
模块级只导入标准库，所有仓库文件的读取都发生在用例函数里；流水线（npm、Vitest、探针）放在 ``pipeline``
会话级夹具里（全量 pytest 默认跳过，点名运行本文件才跑；候选里还没有本片的标记时夹具不调 npm——照
T024/T040/T041/T043/T044/T045/T051/T052/T053/T054/T055/T056 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线）：api.ts 的五类 JobKind 与 startJob 三支正文（S01）；jobStore 的 KINDS
  五类、两张表各加 doctor-record 与既有公式（S02）；JobCard 的三张表加 doctor-record 与既有字面（S03）；
  桩的 doctor-record 夹具与既有四支不改（S04）；RuntimeDoctor.tsx 只加不删（S05）；runtime-doctor.css
  （S06）；执行端新测试文件在位且要点齐备（S07）；兼容性一节的旧断言逐处改到位（S08）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、npm test 全绿；
  两份探针逐份写成 ``gate-probe/probe-<uid>-t057-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，
  ``finally`` 里删除。探针直接渲染 ``RuntimesView``（照包内 page-runtimes.test.tsx 的既有写法注入 runtimes 与
  quizs，不 mock 被测组件），真实模式用 ``setLiveClientForTests`` 注入假服务记录作业请求；等轮询用真实计时器
  ``sleep``（钉「没有作业时不排计时器」的那一条用假计时器数挂起的计时器）。每份探针自带全部辅助函数。
  - probe（真实模式）：核验组在位（label、文本框不带下拉、[核验] 可点、两类入口同一行）、创建正文恰
    ``{"kind":"doctor-record","record":"<值>"}``、进度（aria-label 核验进行中、已用秒数、[取消]）、每秒查同
    一个作业号；succeeded 的结果块（标题「版本记录 <record>」+ 就绪卡八个键值行、说明行、无汇总行）；failed
    带 data 照样显示结果块（不显示「核验失败」）；缺 record 键写「—」；failed 没有 data 显内核原文；已取消
    与超时 600；值不合格不发请求、出提示、改文本框清提示；卸载再挂载同一作业不再创建、结束后同值再点与换值
    再点都只发一次新的创建请求；创建失败 400 与重建；两类作业同时跑各管各的禁用；没有作业时不排计时器。
  - stub（桩模式，不注入客户端）：doctor 与 doctor-record 的奇偶计数互不影响；logs-cat.v2 的两份结局（偶数份
    就绪、奇数份没就绪落 failed 带 data）；别的记录落「还没有版本记录」；loading 一直 running 且 [核验] 禁
    用；error 落 failed 没有 data；startJob 缺记录值回 400。

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

DOCTOR_RECORD_PAGE_TEST_REL = f"{TESTS_REL}/jobs-doctor-record-page.test.tsx"

T009_GATE_REL = "tests/test_gate_t009_baseline.py"
PAGE_RUNTIMES_TEST_REL = f"{TESTS_REL}/page-runtimes.test.tsx"

# 逐字记号（合同 Behavior contract 与「写法钉死」一节，逐字照抄）
JOBKINDS = ("runtime-scan", "runtime-probe", "models", "doctor", "doctor-record")
JOB_STATES = ("queued", "running", "succeeded", "failed", "cancelled", "timed_out")
JOBVIEW_KEYS = ("id", "kind", "state", "reason", "created_ms", "started_ms", "finished_ms", "envelope")

SECTION_TITLE = "就绪检查"
LABEL_RUN = "运行就绪检查"
LABEL_RECORD = "按版本记录核验"
LABEL_VERIFY = "核验"
CARD_TITLE_RECORD = "版本记录核验"
MSG_RECORD_FAILED = "核验失败"
ARIA_RECORD = "核验进行中"
TIMEOUT_RECORD_TEXT = "超时（超过 600 秒），已停止"
HINT_INVALID = "写成 <task-id>.v<N>，例如 logs-cat.v2"
RESULT_PREFIX = "版本记录"
RECORD_PATH = ".agent/runs/logs-cat/binding-v2.json"
MOCK_NO_RECORD_TAIL = "还没有版本记录：第一次 prepare 才会建立；核验当前绑定用 config doctor"
MSG_CANCELLED = "已取消"
# PLAN_KEY_RE 照 ts/packages/ui/src/jobroutes.ts:22 抄进 RuntimeDoctor.tsx（合同入口一节逐字）。
PLAN_KEY_RE_SRC = "/^[a-z0-9][a-z0-9-]{0,63}\\.v[1-9][0-9]{0,3}$/u"
# T056 照旧的记号与逐字文案（本片只加不删）
MSG_DOCTOR_FAILED = "就绪检查失败"
ARIA_DOCTOR = "就绪检查进行中"
LEAVE_NOTE = "离开这个页面作业也会继续，回来时显示结果。"
EMPTY_NOTE = "还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据。"
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
# 桩的夹具记号（合同桩一节；既有四支的记号由 t054/t055/t056 门禁照旧管）
MOCK_SCAN_ERROR_MESSAGE = "ERROR 扫描失败：内核报错（示意）"
MOCK_CANCEL_409 = "作业已经结束"
MOCK_404 = "没有这个作业"
MOCK_CRED_NAME = "STEP_API_KEY"
MOCK_CRED_PROBLEM = "凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY"

# 执行端新测试文件的最小覆盖记号（合同第 9 步点名的覆盖点）
EXECUTOR_TEST_TOKENS = {
    DOCTOR_RECORD_PAGE_TEST_REL: (
        "setLiveClientForTests", "'doctor-record'", "'logs-cat.v2'",
        "{ kind: 'doctor-record', record: 'logs-cat.v2' }",
        LABEL_RECORD, LABEL_VERIFY, MSG_RECORD_FAILED, ARIA_RECORD, RESULT_PREFIX,
        RECORD_PATH, HINT_INVALID, MSG_CANCELLED, TIMEOUT_RECORD_TEXT, MOCK_NO_RECORD_TAIL,
    ),
}

# 新源码的禁词（与 T054/T055/T056 门禁同一口径）
FORBIDDEN_SOURCE_MARKS = (
    "XMLHttpRequest", "EventSource", "WebSocket", "dangerouslySetInnerHTML", "innerHTML", "outerHTML",
    "insertAdjacentHTML", "eval(", "new Function", "document.write", "srcdoc", "DOMParser",
    "matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver", 'role="status"',
)
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_COLOR_FUNCS = ("rgb(", "rgba(", "hsl(", "hsla(", "color-mix(", "oklch(", "lab(", "hwb(")

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T024/T041/T043/T044/T045/T051/T052/T053/T054/T055/T056 门禁）
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 150}

ASSUMPTIONS = (
    "结果块的 DOM 形状不钉（合同只点名标题逐字与 HeadlessCard 复用）：探针按 <dt> 标签在它的父元素里找 dd 取"
    " 值、标题按整节折叠空白后的包含断言，不钉它们之间的空白写法",
    "「同一行」按 .rd-entries 横排容器断言（合同把类名钉成 .rd-entries/.rd-record/.rd-record-body）：[运行就绪"
    " 检查] 与核验组都应在这个容器里，不钉 CSS 具体写法（S06 只钉令牌与类名前缀）",
    "[核验] 的无图标按探针断言（按钮里没有 svg）；静态只钉 variant=\"secondary\" 与 size=\"md\" 记号在文件里",
    "桩的 doctor-record 奇偶「按记录值计数」由 stub 探针的行为断言（先点一次 doctor 再点 logs-cat.v2 应各是奇"
    "数份）；静态不钉计数表的名字，只钉不动 doctorCounts 的既有记号",
    "mock 的 error 开关对 doctor-record 的一行示意原文措辞不钉（t056 的口径）：stub 探针只断言落 failed 且没有"
    " data、不显示结果块",
    "探针里 doctor 与 doctor-record 的作业号用不同前缀（job-doctor-* / job-record-*），便于各自断言查询与创建",
    "400（创建失败）那一行示意原文的措辞不钉（真实服务 400 的正文随错误变），探针用自己注入的原文断言显示",
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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043/T044/T045/T051/T052/T053/T054/T055/T056 的同一口径）
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
    """禁词、写死颜色与内联样式的公共核对（T054/T055/T056 等门禁的口径）。"""
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
    """新 CSS：除 0 与 1px 外的 px 字面量同一行要带出处注释（合同样式一节）。"""
    problems = []
    for i, line in enumerate(css.split("\n"), 1):
        if "/*" in line:
            continue
        for m in re.finditer(r"(\d+(?:\.\d+)?)px", line):
            if m.group(1) not in ("0", "1"):
                problems.append(f"{rel}:{i} 的 {m.group(0)} 应在同一行带出处注释（除 0 与 1px 外的 px 字面量）")
    return problems


def _css_class_problems(rel, css):
    """新 CSS：类名一律以 .rd- 开头（不与别的样式表共用类名）；var() 只用 --tt- 令牌（合同写法钉死）。
    选择器扫描前先剥掉 /* … */ 注释：规则之间的出处注释（例如「§6.5」）不该被当成选择器。"""
    problems = []
    bare = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for m in re.finditer(r"([^{}]+)\{", bare):
        selector = m.group(1)
        if selector.strip().startswith("@"):
            continue
        for cm in re.finditer(r"\.([-\w]+)", selector):
            if not cm.group(1).startswith("rd-"):
                problems.append(f"{rel} 的类名 .{cm.group(1)} 应以 rd- 开头（不与别的样式表共用类名）")
    for vm in re.finditer(r"var\((--[\w-]+)", bare):
        if not vm.group(1).startswith("--tt-"):
            problems.append(f"{rel} 的变量 {vm.group(1)} 不是 --tt- 令牌")
    return problems


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 T044/T045/T051/T052/T053/T054/T055/T056 门禁的写法）
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


def t057_marker_present():
    """候选里是否已有 T057 的标记（RuntimeDoctor 的核验组 + api/jobStore 里的 'doctor-record'）：
    没有就不起 npm（基线上必然没有）。"""
    try:
        doctor = _read(REPO_ROOT / RUNTIMEDOCTOR_REL) if (REPO_ROOT / RUNTIMEDOCTOR_REL).is_file() else ""
        api = _read(REPO_ROOT / API_REL) if (REPO_ROOT / API_REL).is_file() else ""
        store = _read(REPO_ROOT / JOBSTORE_REL) if (REPO_ROOT / JOBSTORE_REL).is_file() else ""
    except OSError:
        return False
    return LABEL_RECORD in doctor and "'doctor-record'" in api and "'doctor-record'" in store


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t057_marker_present():
        pipe.reason = ("候选里还没有 T057 的标记（src/writes/RuntimeDoctor.tsx 的「按版本记录核验」、api.ts / "
                       "jobStore.ts 的 'doctor-record'），没有东西可测，未调用 npm；候选把入口与接线都放进去"
                       "之后，流水线才会运行 npm ci、Vitest 与探针")
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
                    name = f"probe-{uid}-t057-{key}.test.tsx"
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
    """S01 / D02、D06：api.ts——JobKind 五类（取 `export type JobKind = …;` 那一行核对「含这几类」）；
    startJob 的签名逐字不改，函数体里三支正文都在（postRaw、`{ kind }`、`{ kind, runtime }`、
    `{ kind, record: runtime }`、mockStartJob(kind, runtime)、201 才算建成、时限 15、不许出现
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
            problems.append("startJob 的签名应是 (kind: JobKind, runtime?: string)（逐字不改）")
        for mark in ("postRaw", "{ kind }", "{ kind, runtime }", "{ kind, record: runtime }",
                     "mockStartJob(kind, runtime)"):
            if mark not in start:
                problems.append(f"startJob 的函数体里应有 {mark}（doctor-record 且带值时发 {{ kind, record: runtime }}）")
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
    """S02 / D06：jobStore.ts——KINDS 扩成五类（次序 scan、probe、models、doctor、doctor-record，
    doctor-record 在末尾）；snaps 与 subscribers 两张 Record<JobKind, …> 各加 doctor-record 一项；五个既有
    导出（ensureJob / restartJob / cancelJob / useJob / resetJobStoreForTests）与 useBusyRuntime 都在且
    签名照旧；轮询公式与 T055/T056 的字面照旧（setTimeout 链、1000、clearTimeout、已用秒数公式、
    useSyncExternalStore、从 '../api' 引三个作业函数）。"""
    need_file(JOBSTORE_REL)
    text = read_rel(JOBSTORE_REL)
    code = strip_ts_comments(text)
    problems = []
    if not re.search(
            r"KINDS[^=]*=\s*\[[^\]]*'runtime-scan'[^\]]*'runtime-probe'[^\]]*'models'[^\]]*'doctor'"
            r"[^\]]*'doctor-record'[^\]]*\]", code):
        problems.append("KINDS 应扩成五类（次序 scan、probe、models、doctor、doctor-record；"
                        "resetJobStoreForTests 照 KINDS 复位，不加会串状态）")
    for table in ("snaps", "subscribers"):
        m = re.search(rf"const {table}[^=]*=\s*\{{(.*?)\}};", code, re.S)
        if m is None:
            problems.append(f"{table} 的初始化应在位")
        else:
            for kind in ("doctor", "doctor-record"):
                if f"'{kind}'" not in m.group(1) and f"{kind}:" not in m.group(1):
                    problems.append(f"{table} 应含 '{kind}' 一项（Record<JobKind, …> 少了会 tsc 报错）")
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
            problems.append(f"签名应照合同一个字不改：{sig}")
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
    """S03 / D06：JobCard.tsx——三张按 kind 查的表各加 doctor-record 一项（失败标题「核验失败」、
    进度条 aria-label「核验进行中」、超时 600）；扫描、探测、列模型、就绪检查四支的字面与
    'runtime-scan': 150 一字不动；既有 props（title / onCancel / children / kind / failedDetail）与
    结局文字照旧；只引 job-card.css。"""
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
    for mark, what in (("扫描失败", "runtime-scan 失败标题"), ("探测失败", "runtime-probe 失败标题"),
                       ("列模型失败", "models 失败标题"), (MSG_DOCTOR_FAILED, "doctor 失败标题"),
                       (MSG_RECORD_FAILED, "doctor-record 失败标题"),
                       ("扫描进行中", "runtime-scan 进度 aria-label"), ("探测进行中", "runtime-probe 进度 aria-label"),
                       ("列模型进行中", "models 进度 aria-label"), (ARIA_DOCTOR, "doctor 进度 aria-label"),
                       (ARIA_RECORD, "doctor-record 进度 aria-label")):
        if mark not in code:
            problems.append(f"三张表里 {what} 应逐字在位：{mark}")
    for pat, what in ((r"['\"]?runtime-scan['\"]?\s*:\s*150", "'runtime-scan': 150"),
                      (r"['\"]?runtime-probe['\"]?\s*:\s*150", "'runtime-probe': 150"),
                      (r"['\"]?models['\"]?\s*:\s*120", "models: 120"),
                      (r"['\"]?doctor['\"]?\s*:\s*600", "doctor: 600"),
                      (r"['\"]?doctor-record['\"]?\s*:\s*600", "doctor-record: 600")):
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
    五个 kind 都在；既有扫描夹具与 doctor 夹具的记号一字不改；doctor-record 的夹具在位
    （mockStartJob 缺记录值回 400；logs-cat.v2 的那一行带 record 键与
    .agent/runs/logs-cat/binding-v2.json；别的记录的 messages 一行「还没有版本记录…」；
    kindFailedEnvelope 与 terminalEnvelope 各加 doctor-record 一支）。"""
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
    for token in ("'runtime-scan'", "'runtime-probe'", "'models'", "'doctor'", "'doctor-record'",
                  "'running'", "'succeeded'", "'failed'", "'cancelled'", "'queued'"):
        if token not in code:
            problems.append(f"桩里应有 kind / 状态记号：{token}")
    for mark, what in ((MOCK_SCAN_ERROR_MESSAGE, "error 开关的失败信封一行（既有）"),
                       (MOCK_CANCEL_409, "取消已终态的 409 文案（既有）"), (MOCK_404, "查不到的 404 文案（既有）"),
                       (MOCK_CRED_NAME, "doctor 夹具的凭据变量 STEP_API_KEY（既有）"),
                       (MOCK_CRED_PROBLEM, "奇数份 problems 的一条（既有）"),
                       ("ready: false", "奇数份 data.ready 为假"), ("ready: true", "偶数份 data.ready 为真"),
                       ("interactive_host", "规划审核端的 mode（既有）"),
                       ("step-high", "执行端的 profile（既有）"), ("step-5-preview", "执行端的 model（既有）")):
        if mark not in text and mark not in code:
            problems.append(f"桩里应有 {what}：{mark}")
    for role in ("planning_review", "contract", "execution", "scheduler_agent"):
        if f"'{role}'" not in code:
            problems.append(f"桩的 doctor 夹具应含四个角色里的 '{role}'（照 mock/roles.json，既有）")
    # --- doctor-record 的夹具 ---
    for mark, what in (("'logs-cat.v2'", "记录值 logs-cat.v2"),
                       (RECORD_PATH, "那一行的 record 键值 .agent/runs/logs-cat/binding-v2.json"),
                       (MOCK_NO_RECORD_TAIL, "别的记录的 messages 一行「还没有版本记录…」")):
        if mark not in text and mark not in code:
            problems.append(f"桩的 doctor-record 夹具应有 {what}：{mark}")
    start = module_func(code, "export function mockStartJob(")
    if start is None:
        problems.append("应能找到 export function mockStartJob(…)")
    elif not (re.search(r"doctor-record[\s\S]{0,300}?\b400\b", start)
              or re.search(r"\b400\b[\s\S]{0,300}?doctor-record", start)):
        problems.append("mockStartJob 里 doctor-record 不带记录值应回 400（与服务同样的规则）")
    for func, what in (("function kindFailedEnvelope(", "kindFailedEnvelope 加 doctor-record 一支"),
                       ("function terminalEnvelope(", "terminalEnvelope 加 doctor-record 一支")):
        body = module_func(code, func)
        if body is None:
            problems.append(f"应能找到 {func}…)")
        elif "doctor-record" not in body:
            problems.append(f"{what}（函数体里应有 'doctor-record'）")
    problems.extend(_forbidden_marks("mock/jobs.ts", text, code))
    fail_if(problems, "mock/jobs.ts 的写法钉死（S04）")


def test_s05_runtime_doctor_file():
    """S05 / D01–D05、D08：RuntimeDoctor.tsx 只加不删——既有 doctor 那一支照旧，又有 doctor-record
    那一支；PLAN_KEY_RE 照 jobroutes.ts:22 抄在本文件里；横排容器与核验组的类名；新逐字文案在；
    T056 的记号与逐字文案一个没删；Button 与 TextField 从 '../components' 引；不跨层引 src/pages；
    只引 runtime-doctor.css；不用 useBusyRuntime、不用禁词、不写死颜色、不写内联 style。"""
    need_file(RUNTIMEDOCTOR_REL)
    text = read_rel(RUNTIMEDOCTOR_REL)
    code = strip_ts_comments(text)
    problems = []
    # --- 既有 doctor 那一支照旧 ---
    for call in ("ensureJob('doctor')", "restartJob('doctor')", "useJob('doctor')", "cancelJob('doctor')"):
        if call not in code:
            problems.append(f"doctor 那一支照旧，应逐字在位：{call}")
    if 'kind="doctor"' not in code:
        problems.append('JobCard 应照旧带 kind="doctor"')
    if "key={job?.id ?? 'creating'}" not in code:
        problems.append("JobCard 应带 key={job?.id ?? 'creating'}（每个作业重新挂载）")
    # --- 新的 doctor-record 那一支 ---
    for call in ("restartJob('doctor-record'", "ensureJob('doctor-record'", "useJob('doctor-record')",
                 "cancelJob('doctor-record')"):
        if call not in code:
            problems.append(f"doctor-record 那一支应有 {call}…（useJob 不带值；restart/ensure 带记录值）")
    if 'kind="doctor-record"' not in code:
        problems.append('JobCard 应带 kind="doctor-record"')
    if 'title="版本记录核验"' not in code:
        problems.append('JobCard 应带 title="版本记录核验"（逐字）')
    if PLAN_KEY_RE_SRC not in code:
        problems.append(f"PLAN_KEY_RE 应照 ts/packages/ui/src/jobroutes.ts:22 抄在本文件里：{PLAN_KEY_RE_SRC}")
    for cls, what in (("rd-entries", "横排容器"), ("rd-record", "核验组"), ("rd-record-body", "结果区容器")):
        if cls not in code:
            problems.append(f"{what}的类名 {cls} 应在组件里（合同把类名钉成这三个）")
    # --- 引入 ---
    if "JobCard" not in code:
        problems.append("应渲染 JobCard")
    elif "from '../jobs/JobCard'" not in text:
        problems.append("JobCard 应从 '../jobs/JobCard' 直接引入（不进 components/index.ts）")
    if "TextField" not in code:
        problems.append("核验组的文本框应用 components 已导出的 TextField")
    if "from '../components'" not in text:
        problems.append("Button 与 TextField 应从 '../components' 引（index.ts 按字节冻结，不加新导出）")
    if "import './runtime-doctor.css';" not in text:
        problems.append("应 import './runtime-doctor.css'（组件自带样式表，照旧只引这一份）")
    css_imports = _css_imports(text)
    for other in css_imports:
        if other != "./runtime-doctor.css":
            problems.append(f"不应引别的样式表（{other}；本文件只引 runtime-doctor.css）")
    if re.search(r"from\s+'\.\./pages", text) or re.search(r'from\s+"\.\./pages', text):
        problems.append("组件不许跨层引 src/pages（角色名与来源标签照抄小表写在组件里）")
    # --- 新逐字文案 ---
    for mark, what in ((LABEL_RECORD, "文本框 label「按版本记录核验」"), (LABEL_VERIFY, "按钮文字「核验」"),
                       (MSG_RECORD_FAILED, "「核验失败」与 JobCard 的表对齐"),
                       (ARIA_RECORD, "「核验进行中」与 JobCard 的表对齐"),
                       (RESULT_PREFIX, "结果块标题「版本记录 …」"),
                       (HINT_INVALID, "提示「写成 <task-id>.v<N>，例如 logs-cat.v2」")):
        if mark not in code:
            problems.append(f"新文案应逐字在位：{what}：{mark}")
    # --- T056 的记号与逐字文案一个没删 ---
    for mark, what in ((LABEL_RUN, "按钮文字逐字「运行就绪检查」（运行中只禁用不换字）"),
                       (SECTION_TITLE, "doctor 作业卡标题「就绪检查」"),
                       (MSG_DOCTOR_FAILED, "「就绪检查失败」与 JobCard 的表对齐"),
                       (ARIA_DOCTOR, "「就绪检查进行中」与 JobCard 的表对齐"),
                       (LEAVE_NOTE, "运行中那句「离开这个页面作业也会继续，回来时显示结果。」"),
                       (EMPTY_NOTE, "空框句子（还没有运行过就绪检查…）"),
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
            problems.append(f"T056 的文案不许删：{what}应逐字在位：{mark}")
    for label in ROW_LABELS:
        if f">{label}<" not in code:
            problems.append(f"T056 的键值行 <dt> 标签应逐字在位：{label}")
    for mark, what in ((SOURCE_ENV, "来源标签 环境变量"), (SOURCE_LOCAL, "来源标签 本机文件"),
                       (SOURCE_PATH, "来源标签 PATH"), (SOURCE_MISSING, "来源标签 找不到"),
                       (ROLE_PLANNING, "角色名 规划审核端"), (ROLE_CONTRACT, "角色名 合同端"),
                       (ROLE_EXECUTION, "角色名 执行端"), (ROLE_SCHEDULER, "角色名 调度代理")):
        if mark not in code:
            problems.append(f"T056 的照抄小表应逐字在位：{what}（{mark}）")
    if "useBusyRuntime" in code:
        problems.append("doctor / doctor-record 都不用 useBusyRuntime（同类只有一个作业，没有忙于谁的行）")
    problems.extend(_forbidden_marks("RuntimeDoctor.tsx", text, code))
    fail_if(problems, "RuntimeDoctor.tsx 的只加不删（S05）")


def test_s06_runtime_doctor_css():
    """S06 / D08：runtime-doctor.css——本片新加的三条规则（.rd-entries / .rd-record / .rd-record-body）
    在位；类名一律以 .rd- 开头；只用 --tt- 令牌；除 0 与 1px 外的 px 字面量同一行带出处注释；
    不写死颜色；接线由 S05 的 import './runtime-doctor.css' 保证（组件被视图引着）。"""
    need_file(RUNTIMEDOCTOR_CSS_REL)
    css = read_rel(RUNTIMEDOCTOR_CSS_REL)
    problems = _forbidden_marks("runtime-doctor.css", css, css)
    problems.extend(_css_px_problems("runtime-doctor.css", css))
    problems.extend(_css_class_problems("runtime-doctor.css", css))
    for cls in ("rd-entries", "rd-record", "rd-record-body"):
        if not re.search(rf"\.{cls}\s*\{{", css):
            problems.append(f"runtime-doctor.css 应有 .{cls} 的规则（合同把类名钉成这三个）")
    if not css.strip():
        problems.append("runtime-doctor.css 不应是空文件")
    fail_if(problems, "runtime-doctor.css 的写法钉死（S06）")


def test_s07_executor_test_files():
    """S07 / D09：执行端新测试文件 jobs-doctor-record-page.test.tsx 在位且要点齐备（合同第 9 步点名的
    覆盖点：真实模式的创建正文恰两个键、进度与结局、有 data 的 failed、取消与超时、值不合格不发请求、
    卸载再挂载与同值/换值再点、桩的两支与 400），不许 skip/only/todo。"""
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
    fail_if(problems, "执行端新测试文件（S07）")


def test_s08_legacy_assertions_updated():
    """S08 / D10：兼容性一节的旧断言逐处改到位——t009（:2895 标题换成「按版本记录核验是文本框加可点的
    [核验]，没有下拉」、:2909 改成 [核验] 在节里且可点、:2970 标题尾接「与 T057 接上的 [核验]」、
    :2974 白名单加「核验」）；page-runtimes（:116 标题同样改、:125 改成 [核验] 在且可点）；
    t009 :2903-2908（尤其不放下拉那行）与 :2975（禁用按钮数 0）、page-runtimes :120/:123/:124 照旧；
    旧口径不再残留在这些文件里。本片不推翻任何过渡断言（包内 page-app/readonly2 不进允许修改范围）。"""
    problems = []
    # t009
    t009 = read_rel(T009_GATE_REL)
    if '就绪检查：h2 加可点的 [运行就绪检查]（PlayIcon，secondary），虚线空框原文；按版本记录核验是文本框加可点的 [核验]，没有下拉' not in t009:
        problems.append('t009 :2895 的 it 标题只把末尾「；没有按版本核验的下拉与 [核验]」改成「；按版本记录核验是文本框加可点的 [核验]，没有下拉」')
    if '没有按版本核验的下拉与' in t009:
        problems.append('t009 里不应再残留旧标题尾巴「没有按版本核验的下拉与 [核验]」')
    if re.search(r"expect\(sec\.querySelector\('select, \[role=\"combobox\"\], \[role=\"listbox\"\]'\), '不放按版本核验的下拉'\)\.toBeNull\(\);", t009) is None:
        problems.append('t009 :2908 不放下拉那一行应一字不动（t056 门禁认它）')
    if re.search(r"btn\(sec, '核验'\)(?P<rest>[\s\S]{0,260})", t009) is None:
        problems.append("t009 :2909 应改成在「就绪检查」这一节里找 [核验]（btn(sec, '核验')）")
    else:
        rest = re.search(r"btn\(sec, '核验'\)(?P<rest>[\s\S]{0,260})", t009).group("rest")
        if not re.search(r"not\.toBeNull\(\)", rest) or not re.search(r"disabled\)?\.toBe\(false\)", rest):
            problems.append('t009 :2909 应断言 [核验] 不为 null 且 disabled 为 false（空闲时一直可点）')
    if "btn(r, '核验')" in t009:
        problems.append("t009 里不应再残留 btn(r, '核验')（旧断言：整页没有 [核验]）")
    if '与 T056 接上的 [运行就绪检查] 与 T057 接上的 [核验]' not in t009:
        problems.append('t009 :2970 的 it 标题应在「与 T056 接上的 [运行就绪检查]」后面接「与 T057 接上的 [核验]」')
    if '与 T055 接上的 [探测]、[模型]' not in t009:
        problems.append('t009 :2970 的 it 标题应保留「与 T055 接上的 [探测]、[模型]」这一段（t055 门禁认它）')
    if "'扫描 PATH', '探测', '模型'" not in t009:
        problems.append("t009 :2974 的「扫描 PATH / 探测 / 模型」要照旧连着写（t055 门禁认它）")
    if "'模型', '运行就绪检查', '核验']" not in t009:
        problems.append("t009 :2974 的白名单应在「运行就绪检查」后面加「核验」（「模型, 运行就绪检查」照旧连着写，t056 门禁认它）")
    if "'运行就绪检查']" in t009:
        problems.append("t009 里不应再残留以 '运行就绪检查' 结尾的白名单旧写法（应为 '运行就绪检查', '核验']）")
    if 'expect(disabledButtons().length).toBe(0);' not in t009:
        problems.append('t009 :2975 的 expect(disabledButtons().length).toBe(0); 应一字不动（空闲时 [核验] 可点）')
    # 包内 page-runtimes
    rt_test = read_rel(PAGE_RUNTIMES_TEST_REL)
    if '[运行就绪检查] 可点 secondary 带 PlayIcon，虚线空框，按版本记录核验是文本框加可点的 [核验]，无下拉' not in rt_test:
        problems.append('page-runtimes :116 的 it 标题只把末尾「，无按版本核验下拉」改成「，按版本记录核验是文本框加可点的 [核验]，无下拉」')
    if '无按版本核验下拉' in rt_test:
        problems.append('page-runtimes 里不应再残留旧标题尾巴「无按版本核验下拉」')
    if "expect(btn(container, '核验')).toBeTruthy();" not in rt_test:
        problems.append("page-runtimes :125 应改成 expect(btn(container, '核验')).toBeTruthy();（照合同兼容性一节的写法）")
    else:
        m = re.search(r"expect\(btn\(container, '核验'\)\)\.toBeTruthy\(\);(?P<rest>[\s\S]{0,300})", rt_test)
        if m is not None and not re.search(r"disabled[\s\S]{0,120}?toBe\(false\)", m.group("rest")):
            problems.append('page-runtimes :125 truthy 之后应断言 [核验] 的 disabled 为 false')
    if "expect(btn(container, '核验')).toBeUndefined();" in rt_test:
        problems.append("page-runtimes 里不应再残留 expect(btn(container, '核验')).toBeUndefined(); 的旧断言")
    if 'expect(b?.disabled).toBe(false);' not in rt_test:
        problems.append('page-runtimes :120 应一字不动（t056 门禁认它）')
    if "toContain('还没有运行过就绪检查。')" not in rt_test:
        problems.append("page-runtimes :123 的 toContain('还没有运行过就绪检查。') 应一字不动（t056 门禁认它）")
    if 'expect(sec.querySelector(\'select, [role="combobox"], [role="listbox"]\')).toBeNull();' not in rt_test:
        problems.append('page-runtimes :124 不放下拉那一行应一字不动（t056 门禁认它）')
    fail_if(problems, '兼容性一节的旧断言（S08）')


# ---------------------------------------------------------------------------
# 探针（黑盒 Vitest 用例，临时写进 desktop/web/gate-probe/，跑完即删；每份自带全部辅助函数）
# 探针直接渲染 RuntimesView（照包内 page-runtimes.test.tsx 的既有写法注入 runtimes 与 quizs，不 mock 被测组件）。
# ---------------------------------------------------------------------------

RECORD_PROBE = r'''
// T057 门禁 probe 探针（真实模式）：setLiveClientForTests 注入假服务记录作业请求，看「按版本记录核验」的
// 创建正文恰两个键、进度、结果块（标题「版本记录 <record>」+ 就绪卡）、有 data 的 failed、缺 record 键写「—」、
// 取消与超时 600、值不合格不发请求、卸载再挂载与同值/换值再点、创建失败 400、两类作业同时跑。每份探针自带全部
// 辅助函数。
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
function recordInput(sec: any): HTMLInputElement {
  const label = qa(sec, 'label').find((l: any) => text(l) === '按版本记录核验');
  expect(label, '应有「按版本记录核验」的可见 label').toBeTruthy();
  const id = label.getAttribute('for');
  const input = id ? document.getElementById(id) : null;
  expect(input, 'label 应用 htmlFor 关联 input').toBeTruthy();
  return input as HTMLInputElement;
}
function typeRecord(sec: any, value: string): void {
  fireEvent.change(recordInput(sec), { target: { value } });
}
function errEnv(message: string): any {
  return { ok: false, exit_code: 1, data: null, output: [], messages: [message], command: [], elapsed_ms: 0 };
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
// 无头行的基底：不带 record 键（缺键写「—」的那份就是它）。
const HEAD_BASE = { role: 'execution', mode: 'headless', problems: [], profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, notes: ['说明一行（示意）'], allowed: null, credentials: { STEP_API_KEY: true }, ready: true, command: ['node', 'pi.js'], source: 'local', version: '0.1.2', model_listed: true, auth_ready: true, thinking_supported: true };
const RECORD_OK = { ...HEAD_BASE, record: '.agent/runs/logs-cat/binding-v2.json' };
const RECORD_BAD = { ...RECORD_OK, ready: false, problems: ['凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY'], credentials: { STEP_API_KEY: false }, notes: [] };
const ALL_READY = { ready: true, roles: [PLANNING, CONTRACT_MANUAL, HEAD_BASE, SCHEDULER] };
function doctorEnv(data: any, ok: boolean): any {
  return { ok, exit_code: ok ? 0 : 1, data, output: [], messages: [], command: ['config', 'doctor', '--json'], elapsed_ms: 1 };
}
function recordEnv(row: any, ready: boolean): any {
  return { ok: ready, exit_code: ready ? 0 : 1, data: { ready, roles: [row] }, output: [], messages: [], command: ['config', 'doctor', '--record=logs-cat.v2', '--json'], elapsed_ms: 1 };
}

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
let envelopeFor: ((job: any) => any) | null = null;
let createStatus = 201;
let creates: any[] = [];
let cancels: any[] = [];
let queries: string[] = [];
const jobMap = new Map<string, { kind: string; record: string | null }>();

function viewFor(id: string): any {
  const job = jobMap.get(id) || { kind: 'doctor-record', record: null };
  const terminal = ['succeeded', 'failed', 'cancelled', 'timed_out'].indexOf(jobState) >= 0;
  const envelope = envelopeFor != null ? envelopeFor(job) : null;
  return {
    id, kind: job.kind, state: jobState, reason: null,
    created_ms: 1, started_ms: 2, finished_ms: terminal ? 3 : null,
    envelope,
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
      const kind = (body as any)?.kind ?? 'doctor-record';
      const id = (kind === 'doctor' ? 'job-doctor-' : 'job-record-') + seq;
      jobMap.set(id, { kind, record: kind === 'doctor-record' ? ((body as any)?.record ?? null) : null });
      return Promise.resolve({ status: 201, body: { id, kind, state: 'queued', reason: null, created_ms: 1, started_ms: null, finished_ms: null, envelope: null } });
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
  envelopeFor = null;
  createStatus = 201;
  creates = [];
  cancels = [];
  queries = [];
  jobMap.clear();
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

describe('按版本记录核验（真实模式）', () => {
  it('(a) 空态：核验组在（label 关联 input、不带 list、不预填、mono、没有下拉），[核验] 可点 secondary/md 无图标，与 [运行就绪检查] 同在 .rd-entries；填 logs-cat.v2 点 [核验]：创建正文恰两个键，进度与已用秒数与 [取消]，[核验] 禁用，每秒查同一个作业号', async () => {
    const r = mountReady();
    const sec = readySection(r.container);
    const entries = sec.querySelector('.rd-entries');
    expect(entries, '横排容器 .rd-entries').toBeTruthy();
    const runBtn = btnIn(sec, '运行就绪检查');
    expect(entries.contains(runBtn), '[运行就绪检查] 在 .rd-entries 里').toBe(true);
    const group = sec.querySelector('.rd-record');
    expect(group, '核验组 .rd-record').toBeTruthy();
    const input = recordInput(sec);
    expect(group.contains(input), '文本框在核验组里').toBe(true);
    expect(input.value, '不预填').toBe('');
    expect(input.getAttribute('list'), '不带 list 属性').toBeNull();
    expect(String(input.className), '等宽字体（mono）').toContain('mono');
    expect(sec.querySelector('select, [role="combobox"], [role="listbox"]'), '没有下拉').toBeNull();
    const v = btnIn(sec, '核验');
    expect(group.contains(v), '[核验] 在核验组里').toBe(true);
    expect(v.disabled, '空闲时 [核验] 一直可点').toBe(false);
    expect(v.getAttribute('data-variant')).toBe('secondary');
    expect(v.getAttribute('data-size')).toBe('md');
    expect(v.querySelector('svg'), '[核验] 不带图标').toBeNull();
    expect(qa(sec, '[role="progressbar"]').length, '空闲不渲染作业卡').toBe(0);
    expect(queries.length, '没点过就没有作业请求').toBe(0);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(v);
    await flush();
    expect(creates.length, '只发一次创建（restartJob 与 ensureJob 共用在途创建）').toBe(1);
    expect(creates[0], '创建正文恰两个键').toEqual({ kind: 'doctor-record', record: 'logs-cat.v2' });
    expect(Object.keys(creates[0]).length).toBe(2);
    expect(btnIn(sec, '核验').disabled, '作业排队或运行时 [核验] 禁用').toBe(true);
    const bar = qa(sec, '[role="progressbar"]')[0];
    expect(bar, '运行中应有进度条').toBeTruthy();
    expect(bar.getAttribute('aria-label'), '进度条 aria-label').toBe('核验进行中');
    expect(text(sec)).toMatch(/已用 \d+ 秒/);
    expect(btnIn(sec, '取消'), '有 [取消]').toBeTruthy();
    await act(async () => { await sleep(2200); });
    expect(queries.length, '每秒查一次').toBeGreaterThanOrEqual(2);
    expect(queries.every((p) => p === '/api/v1/jobs/job-record-1'), '查询同一个作业号').toBe(true);
  }, 20000);

  it('(b) succeeded：结果块标题「版本记录 .agent/runs/logs-cat/binding-v2.json」+ 就绪卡（八个键值行、说明行），不加汇总行；[核验] 可点', async () => {
    jobState = 'succeeded';
    envelopeFor = () => recordEnv(RECORD_OK, true);
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, '标题').toContain('版本记录 .agent/runs/logs-cat/binding-v2.json');
    expect(t, '卡头 ✓ 就绪').toContain('✓ 就绪');
    expect(t, '卡头角色中文名').toContain('执行端');
    expect(t, '卡头 profile').toContain('profile step-high');
    expect(valuesOf(sec, '命令')).toEqual(['node pi.js（来源：本机文件）']);
    expect(valuesOf(sec, '版本')).toEqual(['0.1.2']);
    expect(valuesOf(sec, '模型在列表中')).toEqual(['是']);
    expect(valuesOf(sec, '登录')).toEqual(['是']);
    expect(valuesOf(sec, '思考级别')).toEqual(['high（本机 pi 接受这个档位）']);
    expect(valuesOf(sec, '允许列表')).toEqual(['不限制']);
    expect(valuesOf(sec, '凭据')).toEqual(['STEP_API_KEY 可用']);
    expect(valuesOf(sec, '接通状态')).toEqual(['已接通']);
    expect(t, '说明行').toContain('说明一行（示意）');
    expect(t, '不加汇总行').not.toContain('全部就绪');
    expect(t, '不加汇总行').not.toContain('有未就绪的角色');
    expect(t, 'succeeded 不显示失败标题').not.toContain('核验失败');
    expect(qa(sec, '[role="progressbar"]').length, '终态后没有进度条').toBe(0);
    expect(btnIn(sec, '核验').disabled, '结束后 [核验] 可点').toBe(false);
  }, 20000);

  it('(c) failed 带 data：照样显示结果块（✗ 未就绪、问题列表、凭据不可用），不显示「核验失败」与内核报错', async () => {
    jobState = 'failed';
    envelopeFor = () => recordEnv(RECORD_BAD, false);
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(1300); });
    const sec2 = readySection(r.container);
    const t = text(sec2);
    expect(t, '标题').toContain('版本记录 .agent/runs/logs-cat/binding-v2.json');
    expect(t, '卡头 ✗ 未就绪').toContain('✗ 未就绪');
    expect(t, '问题列表在').toContain('凭据变量不可用（被移除、没有设置或为空）：STEP_API_KEY');
    expect(t, '凭据不可用').toContain('STEP_API_KEY 不可用');
    expect(t, '不显示笼统的失败标题').not.toContain('核验失败');
    expect(t, '不显示内核报错').not.toContain('内核报错');
    expect(qa(sec2, '[role="progressbar"]').length).toBe(0);
    expect(btnIn(sec2, '核验').disabled, '终态后 [核验] 可点').toBe(false);
  }, 20000);

  it('(d) failed 没有 data：显示「核验失败」与内核报错原文，不显示结果块', async () => {
    jobState = 'failed';
    envelopeFor = () => errEnv('ERROR: 记录核验示意');
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, '失败标题').toContain('核验失败');
    expect(t, '内核原文照显示').toContain('ERROR: 记录核验示意');
    expect(t, '没有结果块').not.toContain('.agent/runs/logs-cat/binding-v2.json');
    expect(t, '没有就绪卡').not.toContain('未就绪');
  }, 20000);

  it('(e) 那一行缺 record 键：标题写「版本记录 —」，其余照常', async () => {
    jobState = 'succeeded';
    envelopeFor = () => recordEnv(HEAD_BASE, true);
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, '缺键写「—」').toContain('版本记录 —');
    expect(t, '就绪卡照常').toContain('✓ 就绪');
  }, 20000);

  it('(f) 点 [取消] 只发一次（正文恰 {}）；取消后落「已取消」，再点是新作业且 [取消] 可点；超时显示「超时（超过 600 秒），已停止」', async () => {
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    fireEvent.click(btnIn(sec, '取消'));
    await flush();
    expect(cancels.length, '只发一次取消').toBe(1);
    expect(cancels[0], '取消正文恰 {}').toEqual({});
    await act(async () => { await sleep(1300); });
    expect(text(sec), '取消后落已取消').toContain('已取消');
    jobState = 'running';
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    expect(creates.length, '取消后再点是新作业（只发一次创建）').toBe(2);
    expect(btnIn(sec, '取消').disabled, '新作业的 [取消] 可点（JobCard 按作业号重新挂载）').toBe(false);
    jobState = 'timed_out';
    await act(async () => { await sleep(1300); });
    expect(text(sec), '超时 600').toContain('超时（超过 600 秒），已停止');
  }, 20000);

  it('(g) 值不合格（空、大写、没有 .v、v0、尾空格）点 [核验] 不发请求、出提示且 aria-invalid；改文本框就清掉；合格的值照常起作业', async () => {
    const r = mountReady();
    const sec = readySection(r.container);
    const input = recordInput(sec);
    for (const value of ['', 'LOGS-CAT.V2', 'logs-cat', 'logs-cat.v0', 'logs-cat.v2 ']) {
      fireEvent.change(input, { target: { value } });
      fireEvent.click(btnIn(sec, '核验'));
      await flush();
      expect(creates.length, `「${value}」不合格，不发创建请求`).toBe(0);
      expect(text(sec), `「${value}」应出提示`).toContain('写成 <task-id>.v<N>，例如 logs-cat.v2');
      expect(input.getAttribute('aria-invalid'), '出错时 aria-invalid 为真').toBe('true');
    }
    expect(queries.length, '没有作业就没有查询').toBe(0);
    fireEvent.change(input, { target: { value: 'logs-cat.v2' } });
    await flush();
    expect(text(sec), '改了文本框就清提示').not.toContain('写成 <task-id>');
    expect(input.getAttribute('aria-invalid'), '清掉后 aria-invalid 不在').toBeNull();
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    expect(creates.length, '合格的值照常起作业').toBe(1);
  }, 20000);

  it('(h) 卸载再挂载看到同一个作业、不再发创建请求；跑完显示结果；结束后同值再点、换值再点都只发一次新的创建请求', async () => {
    const r = mountReady();
    typeRecord(readySection(r.container), 'logs-cat.v2');
    fireEvent.click(btnIn(readySection(r.container), '核验'));
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
    envelopeFor = () => recordEnv(RECORD_OK, true);
    await act(async () => { await sleep(1300); });
    expect(text(sec2), '跑完显示结果').toContain('版本记录 .agent/runs/logs-cat/binding-v2.json');
    typeRecord(sec2, 'logs-cat.v2');
    fireEvent.click(btnIn(sec2, '核验'));
    await flush();
    expect(creates.length, '同值再点是新作业（只发一次创建）').toBe(2);
    expect(creates[1]).toEqual({ kind: 'doctor-record', record: 'logs-cat.v2' });
    await act(async () => { await sleep(1300); });
    jobState = 'failed';
    envelopeFor = () => errEnv('ERROR: other-task.v1 还没有版本记录');
    typeRecord(sec2, 'other-task.v1');
    fireEvent.click(btnIn(sec2, '核验'));
    await flush();
    expect(creates.length, '换值再点也是新作业（只发一次创建）').toBe(3);
    expect(creates[2]).toEqual({ kind: 'doctor-record', record: 'other-task.v1' });
    await act(async () => { await sleep(1300); });
    expect(text(sec2), '换值后的失败照显示内核原文').toContain('ERROR: other-task.v1 还没有版本记录');
  }, 20000);

  it('(i) 创建失败 400：显示「核验失败」与错误原文；[核验] 仍可点，点了重建', async () => {
    createStatus = 400;
    const r = mountReady();
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    expect(creates.length).toBe(1);
    const t = text(sec);
    expect(t, '失败标题').toContain('核验失败');
    expect(t, '错误原文').toContain('ERROR 不支持这个作业');
    expect(btnIn(sec, '核验').disabled, '创建失败后 [核验] 可点').toBe(false);
    createStatus = 201;
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    expect(creates.length, '点了重建').toBe(2);
  }, 20000);

  it('(j) 两类作业各管各的：doctor 在跑时 [核验] 仍可点、核验在跑时 [运行就绪检查] 仍可点；同时跑两条进度条；跑完两个结果都在', async () => {
    const r = mountReady();
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    expect(creates.length).toBe(1);
    expect(creates[0]).toEqual({ kind: 'doctor' });
    expect(btnIn(sec, '核验').disabled, 'doctor 在跑不影响 [核验]（各管各的禁用）').toBe(false);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    expect(creates.length, '两类各建一个').toBe(2);
    expect(creates[1]).toEqual({ kind: 'doctor-record', record: 'logs-cat.v2' });
    expect(btnIn(sec, '核验').disabled, '两类同时跑，[核验] 因自己的作业禁用').toBe(true);
    expect(btnIn(sec, '运行就绪检查').disabled, '两类同时跑，[运行就绪检查] 因自己的作业禁用').toBe(true);
    await act(async () => { await sleep(400); });
    const labels = qa(sec, '[role="progressbar"]').map((b: any) => b.getAttribute('aria-label'));
    expect(labels, '两条进度条各带自己的名字').toContain('核验进行中');
    expect(labels).toContain('就绪检查进行中');
    expect(queries.filter((p) => p.indexOf('job-doctor-') >= 0).length, 'doctor 的作业在查').toBeGreaterThan(0);
    expect(queries.filter((p) => p.indexOf('job-record-') >= 0).length, 'record 的作业在查').toBeGreaterThan(0);
    jobState = 'succeeded';
    envelopeFor = (job: any) => job.kind === 'doctor' ? doctorEnv(ALL_READY, true) : recordEnv(RECORD_OK, true);
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, 'doctor 的结果').toContain('全部就绪');
    expect(t, 'record 的结果').toContain('版本记录 .agent/runs/logs-cat/binding-v2.json');
    expect(qa(sec, '[role="progressbar"]').length, '终态后没有进度条').toBe(0);
  }, 20000);

  it('(k) 没点过：不排每秒空转的计时器，也没有作业请求', async () => {
    const spy = vi.spyOn(globalThis, 'setTimeout');
    mountReady();
    await act(async () => { await sleep(2600); });
    const perSecond = spy.mock.calls.filter((c: any[]) => c[1] === 1000);
    expect(perSecond.length, '没有作业时不排 1000 毫秒的计时器').toBe(0);
    expect(creates.length).toBe(0);
    expect(queries.length, '没点过就没有作业请求').toBe(0);
    spy.mockRestore();
  }, 20000);
});
'''


STUB_PROBE = r'''
// T057 门禁 stub 探针（桩模式，不注入客户端）：?mock= 开关下 doctor-record 的奇偶两份、别的记录落
// 「还没有版本记录」、loading 一直 running 且 [核验] 禁用、error 落 failed 且没有 data；直接调 api.startJob
// 看缺记录值回 400（放在最后，避免挪动计数）。每份探针自带全部辅助函数。
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
function recordInput(sec: any): HTMLInputElement {
  const label = qa(sec, 'label').find((l: any) => text(l) === '按版本记录核验');
  expect(label, '应有「按版本记录核验」的可见 label').toBeTruthy();
  const id = label.getAttribute('for');
  const input = id ? document.getElementById(id) : null;
  expect(input, 'label 应用 htmlFor 关联 input').toBeTruthy();
  return input as HTMLInputElement;
}
function typeRecord(sec: any, value: string): void {
  fireEvent.change(recordInput(sec), { target: { value } });
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

describe('桩模式：doctor-record 作业', () => {
  it('(a) doctor 与 doctor-record 的奇偶计数互不影响：先点 [运行就绪检查]（奇数份没就绪），再点 logs-cat.v2 的 [核验] 也应是奇数份（✗ 未就绪，若共用计数会变偶数份）', async () => {
    setMock('data');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    const sec = readySection(r.container);
    fireEvent.click(btnIn(sec, '运行就绪检查'));
    await flush();
    await act(async () => { await sleep(2400); });
    expect(text(sec), 'doctor 的第奇数份没就绪').toContain('有未就绪的角色（1 个）');
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(2400); });
    const t = text(sec);
    expect(t, '记录核验的结果块（奇数份也带 data）').toContain('版本记录 .agent/runs/logs-cat/binding-v2.json');
    expect(t, 'record 的第奇数份没就绪（若与 doctor 共用计数会变偶数份）').toContain('✗ 未就绪');
    expect(t, '不显示笼统的失败标题').not.toContain('核验失败');
  }, 20000);

  it('(b) logs-cat.v2 的两份结局：偶数份全部就绪（✓ 就绪、凭据可用），再点是奇数份没就绪（failed 带 data、不显示核验失败）', async () => {
    setMock('data');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(2400); });
    let t = text(sec);
    expect(t, '偶数份全部就绪').toContain('✓ 就绪');
    expect(t, '凭据可用').toContain('STEP_API_KEY 可用');
    expect(t, '没有未就绪的卡头').not.toContain('✗ 未就绪');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(2400); });
    t = text(sec);
    expect(t, '奇数份没就绪（failed 带 data）').toContain('✗ 未就绪');
    expect(t, '凭据不可用').toContain('STEP_API_KEY 不可用');
    expect(t, '不显示笼统的失败标题').not.toContain('核验失败');
    expect(btnIn(sec, '核验').disabled, '终态后 [核验] 可点').toBe(false);
  }, 20000);

  it('(c) 别的记录落 failed 且没有 data：显示「核验失败」与内核那句原文，不显示结果块', async () => {
    setMock('data');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    const sec = readySection(r.container);
    typeRecord(sec, 'other-task.v1');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(2400); });
    const t = text(sec);
    expect(t, '失败标题').toContain('核验失败');
    expect(t, '还没有版本记录那句').toContain('ERROR: other-task.v1 还没有版本记录：第一次 prepare 才会建立；核验当前绑定用 config doctor');
    expect(t, '没有结果块').not.toContain('.agent/runs/logs-cat/binding-v2.json');
    expect(t, '没有就绪卡').not.toContain('✗ 未就绪');
  }, 20000);

  it('(d) loading 开关：doctor-record 一直 running（进度条与已用秒数），[核验] 一直禁用，doctor 空闲不受影响', async () => {
    setMock('loading');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(2200); });
    const bar = qa(sec, '[role="progressbar"]')[0];
    expect(bar, 'loading 一直 running').toBeTruthy();
    expect(bar.getAttribute('aria-label')).toBe('核验进行中');
    expect(text(sec)).toMatch(/已用 \d+ 秒/);
    expect(btnIn(sec, '核验').disabled, '运行中 [核验] 禁用').toBe(true);
    expect(btnIn(sec, '运行就绪检查').disabled, 'doctor 空闲不受影响').toBe(false);
  }, 20000);

  it('(e) error 开关：落 failed 且没有 data，显示「核验失败」，不显示结果块', async () => {
    setMock('error');
    const r = render(<RuntimesView runtimes={RUNTIMES} quizs={QUIZS} />);
    const sec = readySection(r.container);
    typeRecord(sec, 'logs-cat.v2');
    fireEvent.click(btnIn(sec, '核验'));
    await flush();
    await act(async () => { await sleep(1300); });
    const t = text(sec);
    expect(t, '落 failed').toContain('核验失败');
    expect(t, '没有结果块').not.toContain('.agent/runs/logs-cat/binding-v2.json');
    expect(t, '没有就绪卡').not.toContain('✓ 就绪');
    expect(t).not.toContain('✗ 未就绪');
  }, 20000);

  it('(f) startJob 缺记录值回 400，带 logs-cat.v2 放行（201）', async () => {
    const bad = await startJob('doctor-record');
    expect(bad.status, '缺记录值应回 400（与服务同样的规则）').toBe(400);
    const ok = await startJob('doctor-record', 'logs-cat.v2');
    expect(ok.status, '带记录值放行').toBe(201);
  }, 20000);
});
'''


PROBE_SPECS = {
    "probe": (RECORD_PROBE, (RUNTIMEDOCTOR_REL, RUNTIMESVIEW_REL, JOBSTORE_REL, TRANSPORT_REL, MODE_REL, API_REL)),
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
        f"npm ci（含 --offline 兕底）未成功：{pipeline.stopped_reason or pipeline.reason}"
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


def test_d01_record_probe(pipeline):
    """probe 探针 / D01–D05（真实模式，假服务看真实正文）：核验组在位与创建正文恰两个键、进度与已用秒数与
    [取消]、每秒查同一个作业号；succeeded 的结果块（标题「版本记录 <record>」+ 就绪卡、无汇总行）；failed 带
    data 照样显示结果块（不显示核验失败）；缺 record 键写「—」；failed 没有 data 只显内核原文；已取消与超时
    600；值不合格不发请求、出提示、改文本框清提示；卸载再挂载同一作业、同值/换值再点都只发一次创建；创建失败
    400 与重建；两类作业同时跑各管各的禁用；没有作业时不排计时器。"""
    assert_probe_ok(pipeline, "probe")


def test_d02_stub_probe(pipeline):
    """stub 探针 / D07（桩模式）：doctor 与 doctor-record 的奇偶计数互不影响；logs-cat.v2 的偶数份就绪、奇数
    份没就绪落 failed 带 data；别的记录落「还没有版本记录」；loading 一直 running 且 [核验] 禁用；error 落
    failed 没有 data；startJob 缺记录值回 400。"""
    assert_probe_ok(pipeline, "stub")
