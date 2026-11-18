"""T054 战前门禁：桌面端前端「[扫描 PATH]：运行时页接上作业接口，扫出本机的 CLI、逐个登记」的黑盒基准测试
（合同 t054-desktop-web-runtime-scan.v1，基线 00e299d9）。

被测对象是运行时页页头入口 ``ScanRuntimesAction``（新文件 ``desktop/web/src/writes/RuntimeScan.tsx``）与它的接线
（``live/transport.ts`` 的 ``postRaw``、``live/mode.ts`` 的 ``LiveClient`` 第四个成员、``api.ts`` 的三个作业函数与
三个类型、新桩 ``src/mock/jobs.ts``、作业状态模块 ``src/jobs/jobStore.ts``、作业卡 ``src/jobs/JobCard.tsx``、
``RuntimesPage.tsx`` 的换入口）：

- 页头第一个按钮从 ``<DisabledAction label="扫描 PATH" … />`` 换成 ``ScanRuntimesAction``：secondary/md、
  一直可点、带 SearchIcon 16×16、次序不变；RuntimesPage 其余一字不改（并行三读、失败判定、children、
  空态、Quizs 一块、页头说明）。
- 传输层 ``postRaw``（复用内部 ``request``，POST 形状照 ``post``、正文原样交回、401 先 reauth、断线 reject）；
  ``api.ts`` 加 ``startJob`` / ``getJob`` / ``cancelJob``（路径、正文恰 ``{"kind":"runtime-scan"}`` 与 ``{}``、
  时限 15/15/30 秒、桩分支转 ``src/mock/jobs.ts``）与 ``JobKind`` / ``JobState`` / ``JobView`` 三个类型。
- 桩 ``src/mock/jobs.ts``（模块级作业表、不用计时器）：loading 一直 running、error 落 failed、data/offline/empty
  第一次查询 running 第二次 succeeded；五行扫描夹具；取消 200/409；查不到 404。
- 作业状态模块 ``src/jobs/jobStore.ts``：``ensureJob`` / ``restartJob`` / ``cancelJob`` / ``useJob`` /
  ``resetJobStoreForTests``；每秒轮询（``setTimeout`` 链、卸载即停、重开先查一次）；已用秒数从创建回应到达时
  算起（``Math.floor((Date.now() - t0) / 1000)``）；查询 404 按失败处理并允许重新扫描；其他失败当暂时的。
- 作业卡 ``src/jobs/JobCard.tsx``：运行中有不确定进度条（``role="progressbar"``、``--tt-primary``、
  prefers-reduced-motion 停住）、「已用 N 秒」、[取消]；四种结局（succeeded 渲染 children、failed「扫描失败」+
  内核原文、cancelled「已取消」、timed_out「超时（超过 150 秒），已停止」）；不用 ``role="status"``。
- 扫描对话框：标题「扫描 PATH」；脚注 [重新扫描]（排队或运行时禁用）与 [关闭]（不取消作业）；打开时读一次
  ``getRuntimes`` 判断已登记；结果表四列（适配器/路径/版本/操作）五行；[登记…] 先关框再走既有 ``runtime.add``
  的预览 → 确认 → 执行 → 重读（args 只有 runtime 与 adapter、执行正文只有 adapter 与 confirmation）。
- 执行端新测试文件 ``jobs-api.test.ts`` / ``jobs-store.test.ts`` / ``jobs-scan-page.test.tsx`` 覆盖合同第 11 步
  点名的每一项。

基线（00e299d9）上新文件都不存在、接线文件里没有 postRaw 与作业函数，所以本文件的失败落在「记号不在」「文件
不存在」「流水线没跑」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有仓库文件的读取都发生在
用例函数里；流水线（npm、Vitest、探针）放在 ``pipeline`` 会话级夹具里（全量 pytest 默认跳过，点名运行本文件才
跑；候选里还没有本片的标记时夹具不调 npm——照 T024/T040/T041/T043/T044/T045/T051/T052/T053 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线）：RuntimeScan 的写法钉死与逐字文案（S01）；jobStore 的导出、轮询与已用
  秒数公式（S02）；JobCard 与 job-card.css 的进度条、结局文字、令牌与样式表接线（S03）；transport/mode/api 的 postRaw、
  三个作业函数与三个类型（S04）；桩 mock/jobs.ts 的状态机与夹具（S05）；RuntimesPage 的换入口与其余一字不改
  （S06）；执行端三份新测试文件在位且要点齐备（S07）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、npm test 全绿；
  三份探针逐份写成 ``gate-probe/probe-<uid>-t054-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，
  ``finally`` 里删除。探针直接渲染 ``ScanRuntimesAction``（不挂整页 App），不 mock 被测组件；等轮询用真实计时器
  ``sleep``（不用假计时器）；每份自带全部辅助函数，不跨文件共享作用域。
  - scan（真实模式，``setLiveClientForTests`` 注入假服务记录作业请求）：入口 secondary/md/带 svg/一直可点；点开
    创建正文恰 ``{"kind":"runtime-scan"}``；进度条、[取消]、「已用 N 秒」随秒增长；每秒查询；断线一次保留原状态
    继续轮询；[取消] 正文恰 ``{}``、随后「已取消」；failed「扫描失败」+内核原文、timed_out「超时（超过 150
    秒），已停止」；404「没有这个作业」且 [重新扫描] 可点、点了重新创建；关掉再开接着同一个作业且不再创建、
    关着时不轮询、DOM 里没有作业卡。
  - result（真实模式）：结果表列头四列、五行次序照服务、已登记/登记…/没找到三种行；[登记…] 先关扫描框再开
    确认框（标题「登记运行时 codex？」、预览 args 恰 runtime+adapter、执行正文恰 adapter+confirmation、成功
    轻提示与 reload）；读不出已登记表时提示句且无 [登记…]。
  - stub（桩模式，不注入客户端）：data 先 running 后 succeeded 表出现；loading 一直 running、取消落「已取消」；
    error「扫描失败」+「ERROR 扫描失败：内核报错（示意）」；桩下登记流走通（mock/writes 的默认情景）。

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

RUNTIMESCAN_REL = f"{WRITES_REL}/RuntimeScan.tsx"
RUNTIMESCAN_CSS_REL = f"{WRITES_REL}/runtime-scan.css"
JOBSTORE_REL = f"{JOBS_REL}/jobStore.ts"
JOBCARD_REL = f"{JOBS_REL}/JobCard.tsx"
JOBCARD_CSS_REL = f"{JOBS_REL}/job-card.css"
MOCKJOBS_REL = f"{SRC_REL}/mock/jobs.ts"
RUNTIMESPAGE_REL = f"{SRC_REL}/pages/RuntimesPage.tsx"
TRANSPORT_REL = f"{SRC_REL}/live/transport.ts"
MODE_REL = f"{SRC_REL}/live/mode.ts"
API_REL = f"{SRC_REL}/api.ts"

JOBS_API_TEST_REL = f"{TESTS_REL}/jobs-api.test.ts"
JOBS_STORE_TEST_REL = f"{TESTS_REL}/jobs-store.test.ts"
JOBS_PAGE_TEST_REL = f"{TESTS_REL}/jobs-scan-page.test.tsx"

# 逐字记号（合同 Behavior contract，逐字照抄；N 表示整数秒插值）
ENTRY_LABEL = "扫描 PATH"                  # 入口按钮文字与对话框标题同文
BUTTON_RESCAN = "重新扫描"
BUTTON_CLOSE = "关闭"
BUTTON_CANCEL = "取消"
MSG_CANCELLED = "已取消"
MSG_FAILED = "扫描失败"
MSG_TIMEOUT_TEXT = "超时（超过 150 秒），已停止"   # 探针按渲染出的整句断言；静态按模板 + 150 的映射钉
MSG_REGISTERED = "已登记"
MSG_REGISTER = "登记…"                      # U+2026
MSG_READ_FAIL = "读不出已登记的 runtime，暂时不能登记"
RESULT_HEADERS = ("适配器", "路径", "版本", "操作")
JOB_KIND = "runtime-scan"
JOB_STATES = ("queued", "running", "succeeded", "failed", "cancelled", "timed_out")
JOBVIEW_KEYS = ("id", "kind", "state", "reason", "created_ms", "started_ms", "finished_ms", "envelope")
# postRaw 的签名（合同逐字；正则对换行与分号宽容）
POSTRAW_SIG_RE = re.compile(
    r"postRaw<T>\(\s*path:\s*string,\s*body:\s*unknown,\s*timeoutSeconds\?:\s*number;?,?\s*\)"
    r"\s*:\s*Promise<\{\s*status:\s*number;?\s*body:\s*T;?\s*\}>"
)
JOBS_PATH_LIT = "'/api/v1/jobs'"
GETJOB_PATH = "/api/v1/jobs/${encodeURIComponent(id)}"
CANCEL_PATH = "/api/v1/jobs/${encodeURIComponent(id)}/cancel"

# RuntimesPage 的 '../api' import 块（基线逐字；合同：页头仍从 '../api' 命名引入这三个读函数）
RUNTIMESPAGE_API_IMPORT = """import {
  getQuizsLive,
  getQuizsProviders,
  getRuntimes,
  type Envelope,
  type QuizsLiveData,
  type QuizsProvidersData,
  type RuntimesData,
} from '../api';"""

# RuntimesPage 其余必须一字不改的记号（并行三读、失败判定、load、children、空态、Quizs、页头说明、既有入口）
RUNTIMESPAGE_KEEP_MARKS = (
    "import { PageFrame } from '../shell/PageFrame';",
    "import { EmptyState } from '../components';",
    "import { RuntimesView } from './readonly1/runtimes-RuntimesView';",
    "import { QuizsBlock } from './readonly1/runtimes-QuizsBlock';",
    "import { AddRuntimeAction } from '../writes/RuntimeForm';",
    "Promise.all([getRuntimes(), getQuizsProviders(), getQuizsLive()])",
    "load={loadRuntimes}",
    "isEmpty={isRuntimesEmpty}",
    "{(data, reload) =>",
    '<EmptyState title="还没有登记的 runtime"',
    "<QuizsBlock quizs={data.quizs} />",
    "<RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />",
    'title="CLI 运行时"',
    'description="每个 runtime 是一个 CLI 的一份安装；命令来源依次是环境变量（只对 pi）、本机文件、PATH"',
)
SCAN_IMPORT = "import { ScanRuntimesAction } from '../writes/RuntimeScan';"
SCAN_LINE = "<ScanRuntimesAction reload={reload} />"
ADDRUNTIME_LINE = "<AddRuntimeAction reload={reload} />"

# 桩的扫描夹具（合同逐字：path / version / exit_code，opencode 与 quizs 没找到）
MOCKJOBS_FOUND = (
    ("pi", "C:/tools/pi/pi.exe", "0.1.2"),
    ("claude-code", "C:/tools/npm/claude.cmd", "1.0.9"),
    ("codex", "C:/tools/codex/codex.exe", "0.5.0"),
)
MOCKJOBS_ERROR_MESSAGE = "ERROR 扫描失败：内核报错（示意）"
MOCKJOBS_CANCEL_409 = "作业已经结束"
MOCKJOBS_404 = "没有这个作业"

# 执行端新测试文件的最小覆盖记号（合同第 11 步点名的覆盖点）
EXECUTOR_TEST_TOKENS = {
    JOBS_API_TEST_REL: ("setLiveClientForTests", "startJob", "getJob", "cancelJob", "/api/v1/jobs"),
    JOBS_STORE_TEST_REL: ("resetJobStoreForTests", "ensureJob", "restartJob", "404"),
    JOBS_PAGE_TEST_REL: ("ScanRuntimesAction", "扫描 PATH", "runtime.add", "登记", "取消"),
}

# 新源码的禁词（page-static.test.ts 的口径 + T006/T009 的 matchMedia 一类；合同 JobCard/写法钉死一节）
FORBIDDEN_SOURCE_MARKS = (
    "XMLHttpRequest", "EventSource", "WebSocket", "dangerouslySetInnerHTML", "innerHTML", "outerHTML",
    "insertAdjacentHTML", "eval(", "new Function", "document.write", "srcdoc", "DOMParser",
    "matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver", 'role="status"',
)
# 颜色字面量与颜色函数（T006/T009 的口径）
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_COLOR_FUNCS = ("rgb(", "rgba(", "hsl(", "hsla(", "color-mix(", "oklch(", "lab(", "hwb(")

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T024/T041/T043/T044/T045/T051/T052/T053 门禁）
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 150}

ASSUMPTIONS = (
    "超时文案里 150 的来源不钉文件位置：JobCard 里写整句「超时（超过 150 秒），已停止」，或在前端任一新文件里"
    "维护「runtime-scan: 150」的时限表再插值，都算过；探针按渲染出的整句断言",
    "postRaw 的签名按空白宽容的正则钉（合同给的签名逐字，换行格式化不算出入）",
    "探针直接渲染 ScanRuntimesAction（照合同第 11 步给执行端新测试规定的写法），不挂整页 App；入口「一直可点」"
    "按渲染后 disabled === false 与 variant/size/svg 钉",
    "「已用 N 秒」按 /已用 \\d+ 秒/ 匹配且随时间增长断言，不钉具体 N（起点是创建回应到达，节流有先后）",
    "结果表列头按表头单元格恰为「适配器」「路径」「版本」「操作」四列、次序如此；行次序照服务给的 found 次序"
    "（五个适配器各一行）",
    "「已登记」按整词断言（不匹配「读不出已登记的 runtime」里的子串——探针按行内取值断言，静态按记号）",
    "stub 探针的登记流走 mock/writes.ts 的默认情景（与 T053 stub 探针同一口径），不另设 ?write= 情景",
    "mock/jobs.ts 的「第一次查询 running、第二次 succeeded」静态只钉状态记号与开关名在位，节奏由 stub 探针行为断言",
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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043/T044/T045/T051/T052/T053 的同一口径）
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
    """禁词、写死颜色与内联样式的公共核对（T045 S10 / T051 S07 / T052/T053 的口径）。"""
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


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 T044/T045/T051/T052/T053 门禁的写法）
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


def t054_marker_present():
    """候选里是否已有 T054 的标记（新入口文件 + api.ts 的作业函数）：没有就不起 npm（基线上必然没有）。"""
    try:
        scan = _read(REPO_ROOT / RUNTIMESCAN_REL) if (REPO_ROOT / RUNTIMESCAN_REL).is_file() else ""
        api = _read(REPO_ROOT / API_REL) if (REPO_ROOT / API_REL).is_file() else ""
    except OSError:
        return False
    return "ScanRuntimesAction" in scan and "startJob" in api


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t054_marker_present():
        pipe.reason = ("候选里还没有 T054 的标记（src/writes/RuntimeScan.tsx 的 ScanRuntimesAction 或 api.ts 的 "
                       "startJob），没有东西可测，未调用 npm；候选把入口与接线都放进去之后，"
                       "流水线才会运行 npm ci、Vitest 与探针")
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
                    name = f"probe-{uid}-t054-{key}.test.tsx"
                    probe_dir.mkdir(exist_ok=True)
                    path = probe_dir / name
                    written.append(path)
                    path.write_text(PROBE_SPECS[key][0], encoding="utf-8", newline="\n")
                    pipe.probe_files[key] = name
                    run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        else:
            pipe.stopped_reason = "npm ci（含 --offline 兕底）失败，后续步骤未运行"
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

def test_s01_runtime_scan_form():
    """S01 / D01、D04–D06、写法钉死（对话框一节）：RuntimeScan.tsx 在位——只导出 ScanRuntimesAction
    （外加类型）；入口按钮文字逐字「扫描 PATH」、secondary/md、带 SearchIcon 16×16；内外两层照 T053
    （外层 useWriteFlow(reload)、{open && <内层/>}、<WriteFlow flow={flow} />）；ensureJob/restartJob
    ('runtime-scan')、打开时读 getRuntimes()；对话框标题逐字「扫描 PATH」；脚注 [重新扫描] 与 [关闭]；
    逐字文案一个不少（已登记、登记…、读不出…、四列列头）；[登记…] 走 runtime.add 且 args 带 runtime 与
    adapter；复用 job-card.css 之外只引 runtime-scan.css；不写死颜色、不写内联 style、不出现禁词。"""
    need_file(RUNTIMESCAN_REL)
    text = read_rel(RUNTIMESCAN_REL)
    code = strip_ts_comments(text)
    problems = []
    # --- 导出形态 ---
    exports = [line for line in code.split("\n") if line.startswith("export ")]
    if not exports:
        problems.append("应有 export（至少导出 ScanRuntimesAction）")
    for line in exports:
        if line.startswith("export function ScanRuntimesAction("):
            continue
        if line.startswith("export interface ") or line.startswith("export type "):
            continue
        problems.append(f"只许导出 ScanRuntimesAction 与类型导出：{line.strip()[:60]}")
    if "export function ScanRuntimesAction(" not in code:
        problems.append("应导出 export function ScanRuntimesAction(")
    # --- 入口按钮：文字、variant、size、SearchIcon 16×16 ---
    if ENTRY_LABEL not in code:
        problems.append(f"入口按钮与对话框标题应逐字「{ENTRY_LABEL}」")
    if 'variant="secondary"' not in code:
        problems.append("入口按钮应写 variant=\"secondary\"")
    if 'size="md"' not in code:
        problems.append("入口按钮应写 size=\"md\"")
    if "SearchIcon" not in code:
        problems.append("入口按钮应带 SearchIcon（t009 :2883 断言页头第一个按钮里有 svg）")
    elif not re.search(r"SearchIcon\b[^/>]*width=\{16\}", text):
        problems.append("SearchIcon 应写 width={16}（16×16，照基线页头的写法）")
    # --- 内外两层（T053 的样板）---
    if "useWriteFlow(reload)" not in code:
        problems.append("外层应写 useWriteFlow(reload)（内外两层照 T053）")
    if not re.search(r"\{open && <", code):
        problems.append("内层对话框应只在打开时挂载（{open && <内层/>}）")
    if "<WriteFlow flow={flow} />" not in code:
        problems.append("文件里应放 <WriteFlow flow={flow} />（写流程在外层照常渲染）")
    # --- 作业接线 ---
    if not re.search(r"ensureJob\(\s*'runtime-scan'\s*\)", code):
        problems.append("点入口应先 ensureJob('runtime-scan')（已有作业不另建）")
    if not re.search(r"restartJob\(\s*'runtime-scan'\s*\)", code):
        problems.append("[重新扫描] 应调 restartJob('runtime-scan')")
    if not re.search(r"useJob\(\s*'runtime-scan'\s*\)", code):
        problems.append("内层应用 useJob('runtime-scan') 订阅作业状态")
    if "JobCard" not in code:
        problems.append("对话框 body 里应放 JobCard")
    elif "from '../jobs/JobCard'" not in text:
        problems.append("JobCard 应从 '../jobs/JobCard' 直接引入（不进 components/index.ts）")
    # --- 已登记判定 ---
    if "getRuntimes(" not in code:
        problems.append("对话框打开时应读一次 getRuntimes() 判断哪些已登记")
    # --- 对话框标题与脚注 ---
    if not re.search(r"title=\{?[\"'`]" + ENTRY_LABEL + r"[\"'`]\}?", code):
        problems.append(f"对话框标题应逐字「{ENTRY_LABEL}」（title 属性）")
    for label, what in ((BUTTON_RESCAN, "脚注 [重新扫描]"), (BUTTON_CLOSE, "脚注 [关闭]")):
        if label not in code:
            problems.append(f"{what}应逐字在位：{label}")
    # --- 逐字文案（包含式核对，一个不少）---
    for mark, what in (
        (MSG_REGISTERED, "已登记"),
        (MSG_REGISTER, "登记…"),
        (MSG_READ_FAIL, "读不出已登记"),
        (RESULT_HEADERS[0], "列头 适配器"),
        (RESULT_HEADERS[1], "列头 路径"),
        (RESULT_HEADERS[2], "列头 版本"),
        (RESULT_HEADERS[3], "列头 操作"),
    ):
        if mark not in text:
            problems.append(f"{what}的文案应逐字在位：{mark[:24]}…")
    # --- [登记…] 走既有 runtime.add，args 只有 runtime 与 adapter（不带 command）---
    if "'runtime.add'" not in code:
        problems.append("[登记…] 应走既有 runtime.add 的写流程（start({ action: 'runtime.add', … })）")
    elif not re.search(r"args:\s*\{\s*runtime:\s*[\w.]+,\s*adapter:\s*[\w.]+\s*\}", code):
        problems.append("[登记…] 的 args 应恰是 { runtime: <适配器名>, adapter: <适配器名> }（不带 command）")
    # --- 样式：只引 runtime-scan.css（job-card.css 由 JobCard 引）---
    css_imports = _css_imports(text)
    if "./runtime-scan.css" not in css_imports:
        problems.append("应 import './runtime-scan.css'")
    for other in css_imports:
        if other != "./runtime-scan.css":
            problems.append(f"不应引别的样式表（{other}；本文件只引 runtime-scan.css）")
    problems.extend(_forbidden_marks("RuntimeScan.tsx", text, code))
    fail_if(problems, "RuntimeScan.tsx 的写法钉死（S01）")


def test_s02_job_store():
    """S02 / D03：jobStore.ts 在位——五个导出（ensureJob / restartJob / cancelJob / useJob /
    resetJobStoreForTests）；状态按 kind 分开；轮询用 setTimeout 链每 1000 毫秒（不用 setInterval、
    卸载 clearTimeout）；已用秒数 Math.floor((Date.now() - t0) / 1000)；useJob 走 useSyncExternalStore；
    作业函数从 '../api' 引（startJob / getJob / cancelJob）；不出现禁词。"""
    need_file(JOBSTORE_REL)
    text = read_rel(JOBSTORE_REL)
    code = strip_ts_comments(text)
    problems = []
    for name in ("ensureJob", "restartJob", "cancelJob", "useJob", "resetJobStoreForTests"):
        if f"export function {name}(" not in code:
            problems.append(f"应导出 export function {name}(")
    if "JobKind" not in code:
        problems.append("kind 的类型应是 api.ts 的 JobKind（本片只有 'runtime-scan' 一类）")
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
        problems.append("已用秒数应按 Math.floor((Date.now() - t0) / 1000) 算（t0 是创建回应到达的时刻）")
    if "useSyncExternalStore" not in code:
        problems.append("useJob 应用 useSyncExternalStore 订阅模块状态")
    problems.extend(_forbidden_marks("jobStore.ts", text, code))
    fail_if(problems, "jobStore.ts 的写法钉死（S02）")


def test_s03_job_card():
    """S03 / D04：JobCard.tsx 与 job-card.css 在位——组件接受 title、作业、已用秒数、onCancel 与
    children；运行中有不确定进度条（role="progressbar"）、「已用 ${…} 秒」、[取消]；四种结局的文字
    （succeeded 渲染 children、failed「扫描失败」、cancelled「已取消」、timed_out「超时（超过 ${…} 秒），
    已停止」）；150 的值由整句或「runtime-scan: 150」的时限表给出；JobCard.tsx 的样式表 import 里含
    './job-card.css'（唯一接线处，照 S01 对 runtime-scan.css 的写法）；CSS 有 --tt-primary 与动画、
    prefers-reduced-motion 时停住、只用令牌；不用 role="status"、不写死颜色。"""
    need_file(JOBCARD_REL)
    text = read_rel(JOBCARD_REL)
    code = strip_ts_comments(text)
    problems = []
    if "export function JobCard(" not in code:
        problems.append("应导出 export function JobCard(")
    for token, what in (("title", "title"), ("onCancel", "onCancel"), ("children", "children")):
        if token not in code:
            problems.append(f"JobCard 的 props 应能看到 {what}")
    if 'role="progressbar"' not in code:
        problems.append("运行中应渲染一条不确定进度条（role=\"progressbar\"）")
    if BUTTON_CANCEL not in code:
        problems.append(f"运行中应有 [取消] 按钮（文字逐字「{BUTTON_CANCEL}」）")
    if not re.search(r"已用 \$\{", code):
        problems.append("运行中应显示「已用 ${…} 秒」（N 是整数秒）")
    for mark, what in ((MSG_FAILED, "failed 结局"), (MSG_CANCELLED, "cancelled 结局")):
        if mark not in code:
            problems.append(f"{what}的文字应逐字在位：{mark}")
    if not re.search(r"超时（超过 \$\{", code):
        problems.append("timed_out 结局应是「超时（超过 ${…} 秒），已停止」的模板")
    # 150 的来源：整句或时限表都算过（另两个新文件可能还不在，缺了不算错，S01/S02 各自钉）
    def _maybe(rel):
        path = REPO_ROOT / rel
        return strip_ts_comments(_read(path)) if path.is_file() else ""

    timeout_sources = code + _maybe(JOBSTORE_REL) + _maybe(RUNTIMESCAN_REL)
    if MSG_TIMEOUT_TEXT not in text and not re.search(r"runtime-scan['\"]?\s*[:=]\s*150", timeout_sources):
        problems.append("超时文案里的 150 应逐字在位（整句或「runtime-scan: 150」的时限表）")
    # succeeded 渲染 children（结果表放在作业卡里）
    if "children" not in code:
        problems.append("succeeded 结局应渲染 children（结果表）")
    # --- 样式表接线（B1：CSS 只有被组件 import 才生效；v2 合同硬要求 JobCard.tsx 引 './job-card.css'，
    #     不许由 main.tsx 或第三个文件引入——照 S01 对 runtime-scan.css 的写法）---
    css_imports = _css_imports(text)
    if "./job-card.css" not in css_imports:
        problems.append("JobCard.tsx 应 import './job-card.css'（组件带自己的样式表，唯一接线处）")
    for other in css_imports:
        if other != "./job-card.css":
            problems.append(f"JobCard.tsx 不应引别的样式表（{other}；job-card.css 由本组件引）")
    problems.extend(_forbidden_marks("JobCard.tsx", text, code))
    # --- CSS ---
    need_file(JOBCARD_CSS_REL)
    css = read_rel(JOBCARD_CSS_REL)
    css_problems = []
    if "--tt-primary" not in css:
        css_problems.append("进度条应用 --tt-primary 令牌")
    if "animation" not in css and "@keyframes" not in css:
        css_problems.append("进度条应有 CSS 动画（不确定进度条）")
    if "prefers-reduced-motion" not in css:
        css_problems.append("prefers-reduced-motion: reduce 时动画应停住")
    css_problems.extend(_forbidden_marks("job-card.css", css, css))
    fail_if(problems, "JobCard.tsx 的写法钉死（S03）")
    fail_if(css_problems, "job-card.css 的写法钉死（S03）")


def test_s04_transport_mode_api_jobs():
    """S04 / D02：传输层与 api.ts 的作业接线——transport.ts 加 postRaw（签名逐字、复用内部 request、
    401 先 runReauth、断线 reject）；mode.ts 的 LiveClient 类型加 postRaw 成员；api.ts 加 JobKind /
    JobState / JobView 三个类型与 toJobView（八键投影、envelope 用 isEnvelope 校验）、startJob / getJob /
    cancelJob 三个导出（路径与时限 15/15/30、创建正文恰 { kind }、取消正文恰 {}、桩分支转 mock/jobs.ts）。"""
    need_file(TRANSPORT_REL)
    transport = read_rel(TRANSPORT_REL)
    problems = []
    m = POSTRAW_SIG_RE.search(transport)
    if m is None:
        problems.append("transport.ts 的 createLiveClient 应加 postRaw<T>(path, body, timeoutSeconds?)"
                        ": Promise<{ status: number; body: T }>（签名照合同逐字）")
    else:
        window = transport[m.start():m.start() + 2500]
        if "request(" not in window:
            problems.append("postRaw 应复用内部 request（不许另起一条请求代码；t037 S01 钉住出现次数）")
        if "runReauth()" not in window:
            problems.append("postRaw 的 401 应先 runReauth() 再回合成的 401 失败信封（照 getRaw）")
        if "result.missed" not in window:
            problems.append("postRaw 拿不到回应时应 reject（照 post）")
    # --- mode.ts ---
    need_file(MODE_REL)
    mode = read_rel(MODE_REL)
    if POSTRAW_SIG_RE.search(mode) is None:
        problems.append("mode.ts 的 LiveClient 类型应加 postRaw 成员（签名与 transport 逐字一致）")
    # --- api.ts ---
    need_file(API_REL)
    api = read_rel(API_REL)
    code = strip_ts_comments(api)
    if "export type JobKind = 'runtime-scan' | 'runtime-probe' | 'models';" not in code:
        problems.append("api.ts 的 JobKind 应登记三类（runtime-scan / runtime-probe / models）")
    sm = re.search(r"export type JobState = ([^;]+);", code)
    if sm is None:
        problems.append("api.ts 应有 export type JobState = …")
    else:
        for state in JOB_STATES:
            if f"'{state}'" not in sm.group(1):
                problems.append(f"JobState 应含 '{state}'（与服务一致）")
    vm = re.search(r"export interface JobView \{(.*?)\n\}", code, re.S)
    if vm is None:
        problems.append("api.ts 应有 export interface JobView {…}")
    else:
        for key in JOBVIEW_KEYS:
            if not re.search(rf"\b{key}\s*[?:]", vm.group(1)):
                problems.append(f"JobView 应有八键里的 '{key}'（与 jobView 一一对应）")
    if "function toJobView(" not in code:
        problems.append("api.ts 应有 function toJobView(（八键投影）")
    else:
        tojv = module_func(code, "function toJobView(")
        if "isEnvelope" not in (tojv or ""):
            problems.append("toJobView 应用 isEnvelope 校验 envelope（不合法取 null）")
    specs = (
        ("startJob", ("postRaw",), (JOBS_PATH_LIT, "{ kind }", "mockStartJob("), (r"\b15\b",)),
        ("getJob", ("getRaw",), (GETJOB_PATH, "mockGetJob("), (r"\b15\b",)),
        ("cancelJob", ("postRaw",), (CANCEL_PATH, "mockCancelJob("), (r"\b30\b",)),
    )
    for name, must_calls, must_marks, must_digits in specs:
        fn = module_func(code, f"export function {name}(")
        if fn is None:
            problems.append(f"api.ts 应新导出 export function {name}(")
            continue
        for call in must_calls:
            if call not in fn:
                problems.append(f"{name} 真实分支应走 {call}")
        for mark in must_marks:
            if mark not in fn:
                problems.append(f"{name} 里应有 {mark[:60]}")
        for digit in must_digits:
            if re.search(digit, fn) is None:
                problems.append(f"{name} 的时限应是 {digit[2:-2]} 秒")
    cancel_fn = module_func(code, "export function cancelJob(")
    if cancel_fn is not None and re.search(r"\{\s*\}", cancel_fn) is None:
        problems.append("cancelJob 的正文应恰是 {}（服务要求正文是 JSON 对象）")
    fail_if(problems, "transport/mode/api 的作业接线（S04）")


def test_s05_mock_jobs():
    """S05 / D02、桩一节：mock/jobs.ts 在位——导出 mockStartJob / mockGetJob / mockCancelJob；模块级
    作业表、不用计时器（没有 setTimeout/setInterval）；不用计时器的已兑现 Promise；五个开关的状态记号
    在位（loading→running、error→failed、data/offline/empty 先 running 后 succeeded）；错误信封一行
    「ERROR 扫描失败：内核报错（示意）」；取消 409「作业已经结束」、查不到 404「没有这个作业」；五行
    扫描夹具的 path/version 逐字；不出现 WriteScenario、不引 JSON、不加计时器、不出现禁词。"""
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
    for token, what in (("'runtime-scan'", "kind 记号"), ("'running'", "running 状态"),
                        ("'succeeded'", "succeeded 状态"), ("'failed'", "failed 状态"),
                        ("'cancelled'", "cancelled 状态")):
        if token not in code:
            problems.append(f"桩里应有 {what}：{token}")
    for mark, what in ((MOCKJOBS_ERROR_MESSAGE, "error 开关的失败信封一行"),
                       (MOCKJOBS_CANCEL_409, "取消已终态的 409 文案"), (MOCKJOBS_404, "查不到的 404 文案")):
        if mark not in text:
            problems.append(f"{what}应逐字在位：{mark}")
    if "404" not in code:
        problems.append("桩里应有 404（查不存在的作业号）")
    if "409" not in code:
        problems.append("桩里应有 409（取消已终态的作业）")
    for adapter, path, version in MOCKJOBS_FOUND:
        if path not in text:
            problems.append(f"扫描夹具里 {adapter} 的 path 应逐字 {path}")
        if version not in text:
            problems.append(f"扫描夹具里 {adapter} 的 version 应逐字 {version}")
    for adapter in ("opencode", "quizs"):
        if f"'{adapter}'" not in code:
            problems.append(f"扫描夹具应含五个适配器里的 '{adapter}'（PATH 上没有，path/version 是 null）")
    if "found" not in code or "added" not in code:
        problems.append("succeeded 的 data 应照服务的形状 { found: […], added: [] }")
    problems.extend(_forbidden_marks("mock/jobs.ts", text, code))
    fail_if(problems, "mock/jobs.ts 的写法钉死（S05）")


def test_s06_runtimes_page():
    """S06 / D01：RuntimesPage.tsx 的换入口——页头第一个按钮换成 <ScanRuntimesAction reload={reload} />
    （从 '../writes/RuntimeScan' 引入、排在 <AddRuntimeAction> 之前）；删掉 DisabledAction 与 SearchIcon 的
    import；文件头注释改成新的事实（旧注释「仍禁用」不在）；'../api' 的 import 块与其余一字不改
    （并行三读、失败判定、children、空态、Quizs 一块、页头说明）。"""
    need_file(RUNTIMESPAGE_REL)
    text = read_rel(RUNTIMESPAGE_REL)
    code = strip_ts_comments(text)
    problems = []
    if SCAN_IMPORT not in text:
        problems.append(f"应引入 {SCAN_IMPORT}")
    if SCAN_LINE not in code:
        problems.append(f"页头第一个按钮应是 {SCAN_LINE}")
    elif ADDRUNTIME_LINE in code and code.index(SCAN_LINE) > code.index(ADDRUNTIME_LINE):
        problems.append("页头次序不变：[扫描 PATH] 应排在 [手动登记…] 之前")
    if "DisabledAction" in code:
        problems.append("RuntimesPage 不应再有 DisabledAction（[扫描 PATH] 变可点）")
    if "SearchIcon" in code:
        problems.append("SearchIcon 应移到 src/writes/RuntimeScan.tsx 里用（RuntimesPage 删掉这个 import）")
    if "仍禁用" in text:
        problems.append("文件头注释应改成新的事实（[扫描 PATH] 可点，旧的「仍禁用」注释已不对）")
    if RUNTIMESPAGE_API_IMPORT not in text:
        problems.append("'../api' 的 import 块应一字不改（页头仍从 '../api' 引三个读函数）")
    for mark in RUNTIMESPAGE_KEEP_MARKS:
        if mark not in text:
            problems.append(f"其余一字不改：{mark[:70]}")
    fail_if(problems, "RuntimesPage 的换入口（S06）")


def test_s07_executor_test_files():
    """S07 / D07：执行端三份新测试文件在位且要点齐备（合同第 11 步点名的覆盖点），不许 skip/only/todo。"""
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


# ---------------------------------------------------------------------------
# 探针（黑盒 Vitest 用例，临时写进 desktop/web/gate-probe/，跑完即删；每份自带全部辅助函数）
# ---------------------------------------------------------------------------

SCAN_PROBE = r'''// T054 门禁 scan 探针（真实模式）：setLiveClientForTests 注入假服务记录作业请求，看创建正文、
// 轮询、已用秒数、取消、四种结局、404 与关掉再开。直接渲染 ScanRuntimesAction（不 mock 被测组件），
// 等轮询用真实计时器 sleep。每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ScanRuntimesAction } from '../src/writes/RuntimeScan';
import { resetJobStoreForTests } from '../src/jobs/jobStore';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const ENTRY = '扫描 PATH';
const JOB_ID = 'job-fixed-id-0000000000000000000000000'; // 不透明作业号，原样传回

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
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}
function secsUsed(root: any): number {
  const m = text(root).match(/已用 (\d+) 秒/);
  expect(m, '应显示已用 N 秒').toBeTruthy();
  return Number(m![1]);
}
function envOf<T>(data: T, command: string[] = []): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

function jobView(state: string, envelope: any): any {
  const terminal = ['succeeded', 'failed', 'cancelled', 'timed_out'].indexOf(state) >= 0;
  return {
    id: JOB_ID, kind: 'runtime-scan', state, reason: null,
    created_ms: 1, started_ms: state === 'queued' ? null : 2, finished_ms: terminal ? 3 : null,
    envelope,
  };
}

const RUNTIMES_OK = {
  runtimes: [
    { id: 'pi', adapter: 'pi', source: 'local', command: ['pi'], notes: [] },
    { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['claude'], notes: [] },
    { id: 'opencode', adapter: 'opencode', source: 'missing', command: null, notes: [] },
  ],
};

let jobState = 'running';
let jobEnvelope: any = null;
let failQueryOnce = false;
let queryStatus = 200;
let runtimesFail = false;
let creates: any[] = [];
let cancels: any[] = [];
let queries: string[] = [];
let posts: Array<{ path: string; body: any }> = [];

const fake: LiveClient = {
  get(path: string): Promise<any> {
    if (path === '/api/v1/runtimes') {
      if (runtimesFail) {
        return Promise.resolve({ ok: false, exit_code: 1, data: null, output: [], messages: ['ERROR 读不出'], command: [], elapsed_ms: 0 });
      }
      return Promise.resolve(envOf(RUNTIMES_OK, ['config', 'runtime', 'list']));
    }
    return Promise.resolve(envOf(null));
  },
  post(path: string, body: unknown): Promise<any> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      const a: any = (body as any).args;
      const command = ['config', 'runtime', 'add', a.runtime, '--adapter=' + a.adapter, '--dry-run', '--json'];
      const preview = {
        binding_changes: [], resources: [{ resource: 'runtimes' }], notes: [], warnings: [],
        running_attempts: [], running_turns: [], needs_yes: false, hub_changes: [],
      };
      return Promise.resolve({ status: 200, body: envOf({ preview, confirmation: 'c-scan-1' }, command) });
    }
    return Promise.resolve({ status: 200, body: envOf(null) });
  },
  getRaw(path: string): Promise<any> {
    if (path.indexOf('/api/v1/jobs/') === 0) {
      queries.push(path);
      if (failQueryOnce) {
        failQueryOnce = false;
        return Promise.reject(new Error('disconnect'));
      }
      if (queryStatus === 404) {
        return Promise.resolve({
          status: 404,
          body: { ok: false, exit_code: 1, data: null, output: [], messages: ['没有这个作业'], command: [], elapsed_ms: 0 },
        });
      }
      return Promise.resolve({ status: 200, body: jobView(jobState, jobEnvelope) });
    }
    return Promise.resolve({ status: 404, body: null });
  },
  postRaw(path: string, body: unknown): Promise<any> {
    if (path === '/api/v1/jobs') {
      creates.push(body);
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
  failQueryOnce = false;
  queryStatus = 200;
  runtimesFail = false;
  creates = [];
  cancels = [];
  queries = [];
  posts = [];
  window.location.hash = '';
  setLiveClientForTests(fake);
});
afterEach(() => {
  cleanup();
  resetJobStoreForTests();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('ScanRuntimesAction：创建、轮询、进度、取消与结局（真实模式）', () => {
  it('(a) 入口 secondary/md/带 svg/一直可点；创建正文恰 {"kind":"runtime-scan"}；进度条与已用秒数随秒增长', async () => {
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    const entry = btnIn(r.container, ENTRY);
    expect(entry.disabled, '入口一直可点').toBe(false);
    expect(entry.getAttribute('data-variant')).toBe('secondary');
    expect(entry.getAttribute('data-size')).toBe('md');
    expect(entry.querySelector('svg'), '带 SearchIcon').toBeTruthy();
    fireEvent.click(entry);
    await flush();
    const d = needDlg();
    expect(text(d), '对话框标题').toContain('扫描 PATH');
    expect(creates.length, '只发一次创建').toBe(1);
    expect(creates[0], '创建正文恰 {"kind":"runtime-scan"}').toEqual({ kind: 'runtime-scan' });
    expect(Object.keys(creates[0]).length, '创建正文只有一个键').toBe(1);
    expect(qa(d, '[role="progressbar"]').length, '运行中应有进度条').toBeGreaterThanOrEqual(1);
    const s1 = secsUsed(d);
    expect(btnIn(d, '取消').disabled, '运行中可取消').toBe(false);
    expect(btnIn(d, '重新扫描').disabled, '运行中重新扫描禁用').toBe(true);
    await act(async () => { await sleep(2100); });
    const d2 = needDlg();
    expect(secsUsed(d2), '已用秒数随时间增长').toBeGreaterThan(s1);
    expect(queries.length, '每秒查一次').toBeGreaterThanOrEqual(2);
    expect(queries.every((p) => p === '/api/v1/jobs/' + JOB_ID), '查询路径带同一个作业号').toBe(true);
  }, 20000);

  it('(b) 查询断线一次：保留原状态继续轮询，不弹错误', async () => {
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    failQueryOnce = true;
    await act(async () => { await sleep(1200); });
    const d = needDlg();
    expect(text(d), '断线时仍显示进度').toMatch(/已用 \d+ 秒/);
    expect(qa(d, '[role="progressbar"]').length).toBeGreaterThanOrEqual(1);
    await act(async () => { await sleep(1200); });
    expect(queries.length, '下一秒接着查').toBeGreaterThanOrEqual(2);
  }, 20000);

  it('(c) 取消：正文恰 {}；随后「已取消」；终态后重新扫描可点', async () => {
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(cancels.length, '只发一次取消').toBe(1);
    expect(cancels[0], '取消正文恰 {}').toEqual({});
    await act(async () => { await sleep(1200); });
    const d = needDlg();
    expect(text(d), '取消后落已取消').toContain('已取消');
    expect(qa(d, '[role="progressbar"]').length, '终态后没有进度条').toBe(0);
    expect(btnIn(d, '重新扫描').disabled, '终态后重新扫描可点').toBe(false);
  }, 20000);

  it('(d) failed「扫描失败」+内核原文；重新扫描后 timed_out「超时（超过 150 秒），已停止」', async () => {
    jobState = 'failed';
    jobEnvelope = {
      ok: false, exit_code: 2, data: null, output: [],
      messages: ['ERROR: 内核扫描失败（示意）'], command: [], elapsed_ms: 5,
    };
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    await act(async () => { await sleep(1200); });
    let d = needDlg();
    expect(text(d), 'failed 标题').toContain('扫描失败');
    expect(text(d), '内核原文照显示').toContain('ERROR: 内核扫描失败（示意）');
    expect(qa(d, '[role="progressbar"]').length, '终态后没有进度条').toBe(0);
    jobState = 'timed_out';
    jobEnvelope = null;
    fireEvent.click(btnIn(d, '重新扫描'));
    await flush();
    expect(creates.length, '重新扫描发新创建').toBe(2);
    await act(async () => { await sleep(1200); });
    d = needDlg();
    expect(text(d), 'timed_out 文案').toContain('超时（超过 150 秒），已停止');
  }, 20000);

  it('(e) 查询 404：显示服务报错原文，允许重新扫描，点了重新创建', async () => {
    queryStatus = 404;
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    await act(async () => { await sleep(1200); });
    const d = needDlg();
    expect(text(d), '服务的报错原文').toContain('没有这个作业');
    expect(btnIn(d, '重新扫描').disabled, '404 允许重新扫描').toBe(false);
    queryStatus = 200;
    jobState = 'running';
    fireEvent.click(btnIn(d, '重新扫描'));
    await flush();
    expect(creates.length, '重新扫描发新创建').toBe(2);
    expect(qa(needDlg(), '[role="progressbar"]').length, '新作业在跑').toBeGreaterThanOrEqual(1);
  }, 20000);

  it('(f) 关掉再开接着同一个作业，不再创建；关着不轮询、DOM 里没有作业卡', async () => {
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    expect(creates.length).toBe(1);
    fireEvent.click(btnIn(needDlg(), '关闭'));
    await flush();
    expect(dlg(), '关掉后对话框不在').toBeNull();
    expect(document.querySelector('[role="progressbar"]'), 'DOM 里没有作业卡').toBeNull();
    const q = queries.length;
    await act(async () => { await sleep(2200); });
    expect(queries.length, '卸载后不再查').toBe(q);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    expect(creates.length, '再开不再创建').toBe(1);
    const d = needDlg();
    expect(secsUsed(d), '再开接着同一个作业').toBeGreaterThanOrEqual(0);
    expect(qa(d, '[role="progressbar"]').length).toBeGreaterThanOrEqual(1);
  }, 20000);
});
'''


RESULT_PROBE = r'''// T054 门禁 result 探针（真实模式）：作业落 succeeded 后的结果表三种行、[登记…] 的完整写流程
// （预览 args 恰 runtime+adapter、执行正文恰 adapter+confirmation）与读不出已登记表。每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ScanRuntimesAction } from '../src/writes/RuntimeScan';
import { resetJobStoreForTests } from '../src/jobs/jobStore';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const ENTRY = '扫描 PATH';
const JOB_ID = 'job-fixed-id-0000000000000000000000000';

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
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}
function envOf<T>(data: T, command: string[] = []): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

function scanEnvelope(): any {
  const found = [
    { adapter: 'pi', program: 'pi', path: 'C:/tools/pi/pi.exe', version: '0.1.2', exit_code: 0 },
    { adapter: 'claude-code', program: 'claude', path: 'C:/tools/npm/claude.cmd', version: '1.0.9', exit_code: 0 },
    { adapter: 'codex', program: 'codex', path: 'C:/tools/codex/codex.exe', version: '0.5.0', exit_code: 0 },
    { adapter: 'opencode', program: 'opencode', path: null, version: null, exit_code: null },
    { adapter: 'quizs', program: 'quizs', path: null, version: null, exit_code: null },
  ];
  return { ok: true, exit_code: 0, data: { found, added: [] }, output: [], messages: [], command: ['config', 'runtime', 'scan', '--json'], elapsed_ms: 10 };
}
function jobSucceeded(): any {
  return {
    id: JOB_ID, kind: 'runtime-scan', state: 'succeeded', reason: null,
    created_ms: 1, started_ms: 2, finished_ms: 3, envelope: scanEnvelope(),
  };
}

const RUNTIMES_OK = {
  runtimes: [
    { id: 'pi', adapter: 'pi', source: 'local', command: ['pi'], notes: [] },
    { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['claude'], notes: [] },
    { id: 'opencode', adapter: 'opencode', source: 'missing', command: null, notes: [] },
  ],
};

let runtimesFail = false;
let posts: Array<{ path: string; body: any }> = [];
let creates: any[] = [];

const fake: LiveClient = {
  get(path: string): Promise<any> {
    if (path === '/api/v1/runtimes') {
      if (runtimesFail) {
        return Promise.resolve({ ok: false, exit_code: 1, data: null, output: [], messages: ['ERROR 读不出'], command: [], elapsed_ms: 0 });
      }
      return Promise.resolve(envOf(RUNTIMES_OK, ['config', 'runtime', 'list']));
    }
    return Promise.resolve(envOf(null));
  },
  post(path: string, body: unknown): Promise<any> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      const a: any = (body as any).args;
      const command = ['config', 'runtime', 'add', a.runtime, '--adapter=' + a.adapter, '--dry-run', '--json'];
      const preview = {
        binding_changes: [], resources: [{ resource: 'runtimes' }], notes: [], warnings: [],
        running_attempts: [], running_turns: [], needs_yes: false, hub_changes: [],
      };
      return Promise.resolve({ status: 200, body: envOf({ preview, confirmation: 'c-scan-1' }, command) });
    }
    return Promise.resolve({ status: 200, body: envOf(null) });
  },
  getRaw(path: string): Promise<any> {
    if (path === '/api/v1/jobs/' + JOB_ID) {
      return Promise.resolve({ status: 200, body: jobSucceeded() });
    }
    return Promise.resolve({ status: 404, body: null });
  },
  postRaw(path: string, body: unknown): Promise<any> {
    if (path === '/api/v1/jobs') {
      creates.push(body);
      return Promise.resolve({ status: 201, body: { id: JOB_ID, kind: 'runtime-scan', state: 'running', reason: null, created_ms: 1, started_ms: null, finished_ms: null, envelope: null } });
    }
    return Promise.resolve({ status: 404, body: null });
  },
};

async function openWithResult(): Promise<ReturnType<typeof render>> {
  const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
  fireEvent.click(btnIn(r.container, ENTRY));
  await flush();
  await act(async () => { await sleep(1300); });
  return r;
}

beforeEach(() => {
  runtimesFail = false;
  posts = [];
  creates = [];
  window.location.hash = '';
  setLiveClientForTests(fake);
});
afterEach(() => {
  cleanup();
  resetJobStoreForTests();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('ScanRuntimesAction：结果表与登记流（真实模式）', () => {
  it('(a) 结果表：四列列头、五行次序照服务、已登记/登记…/没找到三种行', async () => {
    await openWithResult();
    const d = needDlg();
    expect(qa(d, 'table th').map((el: any) => text(el)), '列头四列次序如此').toEqual(['适配器', '路径', '版本', '操作']);
    const rows = qa(d, 'table tbody tr');
    expect(rows.length, '五个适配器各一行').toBe(5);
    const cellsOf = (row: any) => qa(row, 'td').map((c: any) => text(c));
    expect(cellsOf(rows[0]), 'pi 找到且已登记').toEqual(['pi', 'C:/tools/pi/pi.exe', '0.1.2', '已登记']);
    expect(cellsOf(rows[1]), 'claude-code 找到且已登记').toEqual(['claude-code', 'C:/tools/npm/claude.cmd', '1.0.9', '已登记']);
    expect(cellsOf(rows[3]), 'opencode 没找到（哪怕已登记）：路径版本是 —、操作列空').toEqual(['opencode', '—', '—', '']);
    expect(cellsOf(rows[4]), 'quizs 没找到').toEqual(['quizs', '—', '—', '']);
    expect(qa(rows[0], 'button').length, '已登记没有按钮').toBe(0);
    expect(qa(rows[1], 'button').length, '已登记没有按钮').toBe(0);
    expect(qa(rows[3], 'button').length, '没找到没有按钮').toBe(0);
    expect(qa(rows[4], 'button').length, '没找到没有按钮').toBe(0);
    const btn = btnIn(rows[2], '登记…');
    expect(btn.disabled, 'codex 找到且没登记给登记…').toBe(false);
    expect(text(rows[2])).toContain('C:/tools/codex/codex.exe');
    expect(text(rows[2])).toContain('0.5.0');
  }, 20000);

  it('(b) 登记流：先关扫描框；预览 args 恰 runtime+adapter；确认框标题；执行正文恰 adapter+confirmation；轻提示与 reload', async () => {
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<ScanRuntimesAction reload={reload} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    expect(qa(d, 'table').length, '结果表在').toBeGreaterThanOrEqual(1);
    fireEvent.click(btnIn(d, '登记…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '确认框标题（扫描框已关）').toContain('登记运行时 codex？');
    const prev = posts.filter((x) => x.path === '/api/v1/preview').pop();
    expect(prev, '应发过预览').toBeTruthy();
    expect((prev!.body as any).action).toBe('runtime.add');
    expect((prev!.body as any).args, '预览 args 恰 runtime 与 adapter（不带 command）').toEqual({ runtime: 'codex', adapter: 'codex' });
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await act(async () => { await sleep(200); });
    const writes = posts.filter((x) => x.path === '/api/v1/runtimes/codex/add');
    expect(writes.length, '只发一次写路由').toBe(1);
    expect(Object.keys(writes[0].body).sort(), '执行正文只有 adapter 与 confirmation').toEqual(['adapter', 'confirmation']);
    expect((writes[0].body as any).adapter).toBe('codex');
    expect(typeof (writes[0].body as any).confirmation).toBe('string');
    expect(text(document.body), '成功轻提示').toContain('已登记运行时 codex');
    expect(reload, '写完重读整页').toHaveBeenCalled();
  }, 20000);

  it('(c) 读不出已登记表：提示句在、所有行都不给 [登记…]，表还在', async () => {
    runtimesFail = true;
    await openWithResult();
    const d = needDlg();
    expect(text(d), '读不出的提示句').toContain('读不出已登记的 runtime，暂时不能登记');
    expect(qa(d, 'table button').length, '不给登记按钮').toBe(0);
    expect(qa(d, 'table tr').length, '表还在（五行 + 表头）').toBe(6);
    expect(text(d)).toContain('C:/tools/codex/codex.exe');
  }, 20000);
});
'''


STUB_PROBE = r'''// T054 门禁 stub 探针（桩模式）：不注入客户端，读夹具（mock/jobs.ts 的状态机 + mock/runtimes.json
// 里已登记 pi/claude-code/opencode）。验证五个开关的表现与桩下登记流（mock/writes 的默认情景）。
// 每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ScanRuntimesAction } from '../src/writes/RuntimeScan';
import { resetJobStoreForTests } from '../src/jobs/jobStore';

const ENTRY = '扫描 PATH';

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
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}
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

describe('ScanRuntimesAction：桩模式五个开关与登记流', () => {
  it('(a) data：先 running 后 succeeded，表出现（列头、三种行）', async () => {
    setMock('data');
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    expect(qa(needDlg(), '[role="progressbar"]').length, '第一次查询前是 running').toBeGreaterThanOrEqual(1);
    await act(async () => { await sleep(2300); });
    const d = needDlg();
    expect(qa(d, 'table th').map((el: any) => text(el)), '列头四列').toEqual(['适配器', '路径', '版本', '操作']);
    const rows = qa(d, 'table tbody tr');
    expect(rows.length, '五个适配器各一行').toBe(5);
    expect(text(rows[0]), 'pi 已登记').toContain('已登记');
    expect(text(rows[1]), 'claude-code 已登记').toContain('已登记');
    expect(btnIn(rows[2], '登记…'), 'codex 给登记…').toBeTruthy();
    expect(text(rows[3]), 'opencode 没找到').toContain('—');
    expect(qa(rows[3], 'button').length, '没找到没有按钮').toBe(0);
    expect(qa(rows[4], 'button').length, '没找到没有按钮').toBe(0);
  }, 20000);

  it('(b) loading：一直 running；取消落「已取消」', async () => {
    setMock('loading');
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    await act(async () => { await sleep(2200); });
    const d = needDlg();
    expect(qa(d, '[role="progressbar"]').length, 'loading 一直 running').toBeGreaterThanOrEqual(1);
    expect(qa(d, 'table').length, '还没有结果表').toBe(0);
    expect(text(d)).toMatch(/已用 \d+ 秒/);
    fireEvent.click(btnIn(d, '取消'));
    await flush();
    await act(async () => { await sleep(1300); });
    expect(text(needDlg()), '取消后落已取消').toContain('已取消');
  }, 20000);

  it('(c) error：第一次查询就落 failed，显示「扫描失败」与示意原文', async () => {
    setMock('error');
    const r = render(<ScanRuntimesAction reload={vi.fn(() => Promise.resolve())} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    await act(async () => { await sleep(1300); });
    const d = needDlg();
    expect(text(d), 'failed 标题').toContain('扫描失败');
    expect(text(d), '错误信封一行照显示').toContain('ERROR 扫描失败：内核报错（示意）');
  }, 20000);

  it('(d) 桩下登记流：确认框标题、成功轻提示与 reload', async () => {
    setMock('data');
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<ScanRuntimesAction reload={reload} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    await act(async () => { await sleep(2300); });
    fireEvent.click(btnIn(needDlg(), '登记…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '确认框标题（扫描框已关）').toContain('登记运行时 codex？');
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await act(async () => { await sleep(200); });
    expect(text(document.body), '成功轻提示').toContain('已登记运行时 codex');
    expect(reload).toHaveBeenCalled();
  }, 20000);
});
'''


PROBE_SPECS = {
    "scan": (SCAN_PROBE, (RUNTIMESCAN_REL, JOBSTORE_REL, TRANSPORT_REL, MODE_REL, API_REL)),
    "result": (RESULT_PROBE, (RUNTIMESCAN_REL, JOBSTORE_REL, API_REL)),
    "stub": (STUB_PROBE, (RUNTIMESCAN_REL, JOBSTORE_REL, MOCKJOBS_REL)),
}
PROBE_ORDER = ("scan", "result", "stub")


# ---------------------------------------------------------------------------
# P 系列：流水线断言；D 系列：探针断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、D08：npm 依赖（已在就跳过重装）、npm test（全绿，含执行端新测试与既有包内测试）
    都退出 0；依赖文件一个字节没动；gate-probe/ 没有留下。"""
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


def test_d01_scan_probe(pipeline):
    """scan 探针 / D01–D04（真实模式，假服务看真实正文）：入口 secondary/md/带 svg/一直可点；
    创建正文恰 {"kind":"runtime-scan"}；进度条、「已用 N 秒」随秒增长、每秒查询同一个作业号；断线一次保留
    原状态继续轮询；取消正文恰 {}、随后「已取消」；failed「扫描失败」+内核原文；重新扫描后 timed_out
    「超时（超过 150 秒），已停止」；404 显示服务报错原文且允许重新扫描、点了重新创建；关掉再开接着同一个
    作业不再创建、关着不轮询、DOM 里没有作业卡。"""
    assert_probe_ok(pipeline, "scan")


def test_d02_result_probe(pipeline):
    """result 探针 / D05、D06（真实模式）：结果表四列列头、五行次序照服务、已登记（无按钮）/登记…/没找到
    （路径版本 —、无按钮）三种行；[登记…] 先关扫描框再开确认框（标题「登记运行时 codex？」、预览 args
    恰 runtime+adapter、执行正文恰 adapter+confirmation、成功轻提示与 reload）；读不出已登记表时提示句
    在且不给 [登记…]。"""
    assert_probe_ok(pipeline, "result")


def test_d03_stub_probe(pipeline):
    """stub 探针 / D02、D05（桩模式，读夹具）：data 先 running 后 succeeded、表出现（列头与三种行）；
    loading 一直 running 且取消落「已取消」；error 第一次查询就落 failed（「扫描失败」与示意原文）；
    桩下登记流走通（确认框标题、成功轻提示与 reload）。"""
    assert_probe_ok(pipeline, "stub")
