"""T021 战前门禁：桌面端本机服务第 7 片「凭据录入作业与控制取消（D2 之三）」的黑盒基准测试
（合同 t021-desktop-ui-secret v2，基线 1a58dd35754aa20281853db9c76a7d984e13bdff；v2 相对 v1 的要点：既有测试文件
kernel-runner.test.ts、jobs.test.ts、jobs-service.test.ts、support.ts 一个字不改，本片新用例一律写进新建的三个
测试文件；等握手到点先 settle 成 timed_out 再 abort；set 投影的键数随内核是否报错而变，不写死；令牌搜不到的
搜索从四处加到五处（作业查询、SSE、messages、command、访问日志）。）

被测对象是 ``ts/packages/ui``：新路由 ``POST /api/v1/secrets/<name>/entry``（作业方式跑
``config secret set <name> --no-browser --timeout=600``，从子进程的 stderr 读一次性页面地址并严格核对，地址只活在
这一次请求的局部变量里）、``kernel.ts`` 的 ``RunHooks.onStderr`` 钩子（轮询里读还在写的 stderr 文件，ENOENT 跳过）、
``jobs.ts`` 的 kind 放宽（``JobKind | "secret-entry"``）与 ``JobRecord.exited``、``jobroutes.ts`` 导出的
``cancelJob`` 与新控制路由 ``control.jobs.cancel``（标 ``control: true``、不读正文）、``routes.ts`` 的
``Route.control?: true`` 与控制门搬进 ``app.ts``（一次过 Origin 与令牌两道、免 CSRF、删掉按路由名的两处特判）、
``readroutes.ts`` 的 ``secretCheckData`` 加 export、``server.ts`` 把 ``secretEntryRoutes`` 同时并进
``extraRoutes`` 与 ``kernelAnsweredRoutes``（M14 的白盒断言）、以及三个新测试文件与新替身
``fake-secret-kernel.mjs``。四张作业表（JOB_KINDS/JOB_ARGV/JOB_TIMEOUTS/JOB_ALLOW）仍是六项，六种状态与五种
reason 不增不减，routes.ts 里 ``public: true`` 仍恰好两处（T016 门禁钉着，本片只加 ``control: true``）。

基线（1a58dd3）上 ``secretentry.ts`` 与三个新测试文件、新替身都不存在，``kernel.ts`` 没有 ``onStderr``、
``jobs.ts`` 没有 ``exited``、``jobroutes.ts`` 没有 ``cancelJob`` 与控制路由、``routes.ts`` 没有 ``control`` 标记、
``app.ts`` 还是按路由名特判、``readroutes.ts`` 的 ``secretCheckData`` 未导出、README 也没有这两条，所以本文件的
失败落在「标记不在」「文件不存在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有仓库文件的读取都
发生在用例函数里；流水线（装依赖之后起 vitest 跑新/改测试文件与被锁定的既有用例文件）放在 ``pipeline`` 会话级夹具
里，候选里没有新测试文件时不装依赖、不起 vitest。

结构（编号对应合同 DoD 的 D01–D16；合同 D14 的 22 条变异靠这些断言加三个新 Vitest 文件抓，战后门禁另出变异清单）：

- 静态断言（不用流水线，全量 pytest 也跑）：``secretentry.ts`` 的常量、argv、握手正则与端口范围、错误提示、
  状态码、时限覆盖键、重查 argv 与投影、``data`` 的 Map 构造（D01–D06）；``--verify``/``--tty`` 不出现（D02）；
  ``verified`` 不进投影（D06/M8）；``kernel.ts`` 的 onStderr（D01）；``jobs.ts`` 的 kind 放宽与 exited（D06/D10）；
  ``jobroutes.ts`` 的 cancelJob、控制路由、四张表仍六项（D07/D10/M13）；``routes.ts`` 的 control 标记与门搬走
  （D09/M16–M22）；``app.ts`` 的三道门与删掉的特判（D09）；``readroutes.ts`` 的 export（D06）；``server.ts`` 的
  接线（D08/M14，过渡断言：合并两批构造的那一片会推翻）；三个新测试文件与新替身的记号（D01–D12）；routes-auth
  只追加（D13/D16）；README 只追加（D13）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：bun install --frozen-lockfile
  （依赖不齐时）之后起三次 vitest——新用例（secret-entry 与 control-routes）、真内核用例（secret-entry-real）、
  被锁定的既有用例（app/routes-auth/kernel-runner/jobs/jobs-service/service，app.ts 与 kernel.ts 改动波及它们），
  退出码 0 且 Tests 行 passed。

合同没有写死、门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：见 ``ASSUMPTIONS``。
"""

import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TS = REPO_ROOT / "ts"
UI_SRC = TS / "packages" / "ui" / "src"
UI_TEST = TS / "packages" / "ui" / "test"

SECRETENTRY_REL = "ts/packages/ui/src/secretentry.ts"
KERNEL_REL = "ts/packages/ui/src/kernel.ts"
JOBS_REL = "ts/packages/ui/src/jobs.ts"
JOBROUTES_REL = "ts/packages/ui/src/jobroutes.ts"
ROUTES_REL = "ts/packages/ui/src/routes.ts"
APP_REL = "ts/packages/ui/src/app.ts"
SERVER_REL = "ts/packages/ui/src/server.ts"
READROUTES_REL = "ts/packages/ui/src/readroutes.ts"
README_REL = "ts/packages/ui/README.md"
ROUTES_AUTH_REL = "ts/packages/ui/test/routes-auth.test.ts"

# 合同 Scope：三个新测试文件 + 新替身（都已锁进禁改路径之外的允许新增清单）
SECRET_ENTRY_TEST_REL = "ts/packages/ui/test/secret-entry.test.ts"
SECRET_ENTRY_REAL_REL = "ts/packages/ui/test/secret-entry-real.test.ts"
CONTROL_ROUTES_TEST_REL = "ts/packages/ui/test/control-routes.test.ts"
FAKE_SECRET_REL = "ts/packages/ui/test/fixtures/fake-secret-kernel.mjs"
NEW_FILE_RELS = (SECRET_ENTRY_TEST_REL, SECRET_ENTRY_REAL_REL, CONTROL_ROUTES_TEST_REL, FAKE_SECRET_REL)

# 流水线连跑的被锁定既有用例（app.ts、kernel.ts、jobs.ts、jobroutes.ts 的改动波及它们）
LOCKED_GROUP_RELS = (
    "ts/packages/ui/test/app.test.ts",
    "ts/packages/ui/test/routes-auth.test.ts",
    "ts/packages/ui/test/kernel-runner.test.ts",
    "ts/packages/ui/test/jobs.test.ts",
    "ts/packages/ui/test/jobs-service.test.ts",
    "ts/packages/ui/test/service.test.ts",
)
NEW_GROUP_RELS = (SECRET_ENTRY_TEST_REL, CONTROL_ROUTES_TEST_REL)
REAL_GROUP_RELS = (SECRET_ENTRY_REAL_REL,)

# 合同 Behavior contract 第二节：secretentry.ts 导出的五个常量
SECRET_ENTRY_CONSTANTS = {
    "SECRET_ENTRY_PAGE_SECONDS": 600,
    "SECRET_ENTRY_MARGIN_SECONDS": 30,
    "SECRET_ENTRY_JOB_SECONDS": 630,
    "SECRET_ENTRY_HANDSHAKE_SECONDS": 15,
    "SECRET_ENTRY_RECHECK_SECONDS": 30,
}
# 合同 Behavior contract 第一节：argv 恰好这六项（示例名 EXAMPLE_KEY 登记成 SECRET_ENTRY_ARGV）
SECRET_ENTRY_ARGV_PARTS = ("config", "secret", "set", "EXAMPLE_KEY", "--no-browser", "--timeout=600")
# 校验次序里的固定提示（第一节）
ENTRY_MESSAGES = ("请求体必须是 JSON 对象", "请求体含有未知键", "凭据名不合法", "服务繁忙，请稍后重试", "作业表已满，请稍后重试")
# 六个既有 kind：四张表（JOB_KINDS/JOB_ARGV/JOB_TIMEOUTS/JOB_ALLOW）仍是六项，secret-entry 不进去
SIX_KINDS = ("doctor", "doctor-record", "runtime-scan", "runtime-probe", "models", "search")
FOUR_TABLES = ("JOB_KINDS", "JOB_ARGV", "JOB_TIMEOUTS", "JOB_ALLOW")

# secret-entry.test.ts 的要点（合同第 10 步点名的最小记号表 + v1 一致的反例与覆盖键）
SECRET_ENTRY_TEST_TOKENS = (
    (r"secretEntryRoutes", "把 entry 路由接进 extraRoutes（照 write-routes.test.ts 的写法）"),
    (r"createApp", "进程内建 app（自建，不用 support.ts 的 startApp）"),
    (r"KernelRunner", "自建 KernelRunner（kernel 指向新替身）"),
    (r"TS_ROOT", "替身路径由 harness 的 TS_ROOT 拼出"),
    (r"fake-secret-kernel", "内核用新替身"),
    (r"process\.execPath", "起替身的 python 用 process.execPath"),
    (r"SECRET_ENTRY_ARGV", "argv 逐字对照登记表（M1/M2）"),
    (r"FAKE_KERNEL_REPORT", "替身记 argv 进报告，用例逐条比对"),
    (r"FAKE_SECRET_URL", "替身按环境变量打握手行（正例与反例）"),
    (r"FAKE_SECRET_GATE", "secret set 等门文件（计时用例不靠睡眠时长）"),
    (r"FAKE_SECRET_CHECK_GATE", "secret check 卡在门文件（取消不等重查，M15）"),
    (r"\b201\b", "握手正例回 201"),
    (r"\b502\b", "握手之前子进程结束回 502"),
    (r"\b504\b", "等握手到点回 504（M9）"),
    (r"secret-entry\.handshake", "timeouts 覆盖等握手的上限"),
    (r"job\.secret-entry", "timeouts 覆盖作业时限"),
    (r"cancelled", "请求断开/取消的终态 cancelled"),
    (r"kind 不合法", 'POST /api/v1/jobs 提交 kind=secret-entry 应回 400「kind 不合法」（M13/D07）'),
    (r"JOB_KINDS", "四张表仍各六项、jobView 仍八键的新用例（合同第 4 步）"),
    (r"jobView", "jobView 的八键断言"),
    (r"allowEnvName", "凭据名过 allowEnvName 的用例（合同第 10 步点名的记号）"),
    (r"canAccept", "执行器收不了回 503 的用例（合同第 10 步点名的记号）"),
    (r"[Rr]etry-[Aa]fter", "两种 503 带 Retry-After: 2（合同第 10 步点名的记号）"),
    (r"65536", "端口 65536 反例（M3/M4）"),
    (r"99999", "端口 99999 反例（M4）"),
    (r"localhost", "localhost 反例（M3）"),
    (r"repeat\(\s*3[13]\s*\)|\b3[13]\b", "31/33 个字符的令牌反例（M3）"),
    (r"\burl\b", "响应正文带 url 键"),
    (r"accessLog", "访问日志里搜不到令牌（M7）"),
    (r"messages", "messages 里搜不到令牌（M6）"),
    (r"command", "信封的 command 里搜不到令牌（M5，五处的第四处）"),
    (r"events|SSE|sse", "SSE 里搜不到令牌（M5）"),
    (r"pidAlive", "pid 是否还在用 pidAlive 轮询（M10/M20）"),
    (r"stored", "set 投影的 stored 键（键数不写死，只查白名单里）"),
    (r"check", "check 投影（重查）"),
)
# control-routes.test.ts 的要点（D09/D10/D11）
CONTROL_ROUTES_TEST_TOKENS = (
    (r"control\.jobs\.cancel", "控制取消路由"),
    (r"/control/jobs/", "控制取消的路径"),
    (r"control\s*:\s*true", "表驱动筛 control === true 的路由（M21）"),
    (r"\b403\b", "令牌错、只带 cookie、外来 Origin 都回 403（M16/M17/M19）"),
    (r"\b429\b", "第 6 次令牌错回 429（M18）"),
    (r"[Rr]etry-[Aa]fter", "429 带 Retry-After"),
    (r"[Oo]rigin", "外来 Origin 反例"),
    (r"[Cc]ookie|cookie", "只带 cookie 过不了门"),
    (r"[Tt]hemis-[Cc]ontrol", "控制令牌头"),
    (r"extraRoutes", "注入 control 探针路由（M21）"),
    (r"\b404\b", "不存在的作业 404"),
    (r"\b409\b", "已终态的作业 409"),
    (r"\b200\b", "正常取消回 200"),
    (r"running", "取消不等重查：响应里作业仍 running（M15）"),
    (r"bootstrap", "control.bootstrap 只带令牌、不带正文回 200（M22）"),
)
# fake-secret-kernel.mjs 的要点（合同第 2 步：三个门禁钉死的环境变量名 + 沿用既有替身的约定）
FAKE_SECRET_KERNEL_TOKENS = (
    (r"FAKE_KERNEL_REPORT", "begin/end 行照既有替身记进同一份报告"),
    (r"FAKE_KERNEL_EXIT", "退出码沿用既有替身的 FAKE_KERNEL_EXIT"),
    (r"begin", "记 begin 行"),
    (r"stderr", "握手行写到 stderr（照环境变量给的地址）"),
    (r"FAKE_SECRET_URL", "环境变量给握手地址（缺省给一个合格地址）"),
    (r"127\.0\.0\.1", "缺省的合格地址"),
    (r"FAKE_SECRET_GATE", "secret set 等门文件或一直等"),
    (r"FAKE_SECRET_CHECK_GATE", "secret check 可以卡在门文件上"),
    (r"FAKE_KERNEL_PIDFILE", "把 pid 写进文件（照既有替身记法，取消/超时之后 pid 不在的用例用）"),
    (r"\bcheck\b", "演 secret check"),
    (r"stored", "stdout 结果 JSON 带 stored"),
    (r"backend", "结果 JSON 带 backend"),
    (r"verified", "结果 JSON 带 verified: null（替身照内核的 stdout 原样，投影由服务做）"),
    (r"store_mode", "secret check 输出 store_mode（照内核的一行 JSON）"),
)
# secret-entry-real.test.ts 的要点（D12）
SECRET_ENTRY_REAL_TOKENS = (
    (r"startService", "照 harness 起真服务"),
    (r"CODEKIT_SECRET_STORE", "file 后端经 startService 的 env 传给服务子进程"),
    (r"XDG_CONFIG_HOME", "临时 XDG_CONFIG_HOME（绝不写进本机真正的凭据库）"),
    (r"THEMIS_UI_TEST_", "名字用 THEMIS_UI_TEST_<hex> 前缀"),
    (r"store_mode", "录入前断言 store_mode 是 file"),
    (r"system_backend", "录入前断言 system_backend 是 null"),
    (r"succeeded", "保存之后作业终态 succeeded"),
    (r"source", "重查的 source 是 file"),
    (r"backend", "set.backend 是 file"),
    (r"env\s*:", "环境变量经 startService({ env }) 传（不改 vitest 进程的 process.env）"),
    (r"pi_dispatch|THEMIS_PYTHON", "真内核用 scripts/pi_dispatch.py / THEMIS_PYTHON"),
)

ASSUMPTIONS = (
    "「SECRET_ENTRY_ARGV」按块里能连写或逐项找到六个元素判（EXAMPLE_KEY 作示例名）；「--timeout 恒 600」按"
    "--timeout=600 的字面量在登记表里判，测试覆盖项（timeouts[\"job.secret-entry\"] 等）不改 argv 由三个新测试文件钉住",
    "「四张表仍是六项」按四张表的块里不出现 secret-entry、且 JOB_KINDS 块里六个 kind 都在判；六项的精确形状仍由"
    "T017 门禁（test_static_job_argv / test_static_job_redaction）钉着，本文件不重复",
    "「既有测试文件一个字不改」（v2：kernel-runner.test.ts、jobs.test.ts、jobs-service.test.ts、support.ts）由"
    "调度器的范围门禁机械证明（合同 v2 的 forbidden_paths），本文件不写判据，也不写相对基线的改动范围断言"
    "（T021-4 一审 B2：整文件否定是范围门禁的弱化重复，还会误伤后续片往这三个文件里加 onStderr / "
    "secret-entry 用例的合法改动）",
    "「控制门搬进 app.ts」静态面查 app.ts 里有 controlOriginAllowed、state.control.check、retryAfterSeconds 与"
    "retry-after、按 match.route.control 判定，且按路由名 control.bootstrap 的特判（字符串）删净；Origin 先于令牌、"
    "外来 Origin 不计限速这些运行时行为由 control-routes.test.ts 钉住",
    "「server.ts 的接线」按 kernelAnsweredRoutes 的赋值表达式里有 secretEntryRoutes( 判（合同 D08 的白盒断言原文）；"
    "extraRoutes 一批同样要并进。这条是过渡断言：将来合并两批构造的那一片（T020 终审非阻断建议）会推翻它",
    "「set 投影丢 verified」按 strip 注释后 secretentry.ts 里不出现 verified 判（合同写死丢掉恒为 null 的键）；键数随"
    "内核是否报错而变（error 只在报错时出现），不写死「恰好三个键」，白名单键序由新测试文件的运行时断言钉住",
    "「重查的信号」静态面查 secretentry.ts 里有 new AbortController（新的、只跟服务关停走的信号）；「不用作业自己"
    "那个信号」是运行时行为（M12），由取消之后 check 仍不为 null 的用例钉住；「先 settle 成 timed_out 再 abort」"
    "静态面查 settle 被 secretentry.ts 引用，次序由 504 用例钉住",
    "替身的环境变量名按本文件钉的记号判（FAKE_SECRET_URL/FAKE_SECRET_GATE/FAKE_SECRET_CHECK_GATE，另沿用既有替身"
    "的 FAKE_KERNEL_REPORT/FAKE_KERNEL_EXIT/FAKE_KERNEL_PIDFILE）；执行端照记号实现，要换名就先改这份门禁",
    "流水线预算 480 秒（G01 的 600 秒减去静态用例与 pytest 自身开销）：依赖装好时三组 vitest 实测远小于预算；"
    "bun install 只在依赖不齐时跑（候选做完 S01 之后不会跑）",
)

# 流水线预算：合同 G01 的超时是 600 秒，留出静态用例与 pytest 自身的开销。
PIPELINE_BUDGET = 480
STEP_CAPS = {"bun install": 200, "vitest new": 240, "vitest real": 200, "vitest locked": 260}

_ENV_DROP = ("BUN_OPTIONS", "NODE_OPTIONS", "NODE_PATH", "BUN_INSPECT", "BUN_INSPECT_CONNECT_TO", "BUN_INSPECT_NOTIFY")


# ---------------------------------------------------------------------------
# 通用小工具（只读仓库文件；模块级不做任何仓库 IO）
# ---------------------------------------------------------------------------

def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def need_file(rel):
    """断言仓库里的文件存在，返回文本。基线上到这里就以断言失败。"""
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return _read(path)


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:40])


def strip_ts_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(^|[^:'\"`])//[^\n]*", r"\1", text)


def _argv_written(code, *parts):
    """argv 模板片段在不在：连写（``config secret set``）或相邻的数组元素（``"config", "secret", "set"``）都算。"""
    if " ".join(parts) in code:
        return True
    for quote in ('"', "'"):
        elems = ("," + r"\s*").join(quote + re.escape(part) + quote for part in parts)
        if re.search(elems, code) is not None:
            return True
    return False


def _block(text, start_marker, end_marker="};"):
    """从 start_marker 起到 end_marker 止的一段（登记表/函数体切片用）。"""
    start = text.find(start_marker)
    if start < 0:
        return ""
    end = text.find(end_marker, start)
    return text[start:end if end >= 0 else len(text)]


def _no_skip_marks(text):
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
        if re.search(bad, text):
            problems.append(f"出现 {bad}（不许 skip、only、todo）")
    return problems


def _token_problems(text, tokens):
    problems = []
    for pattern, label in tokens:
        if re.search(pattern, text) is None:
            problems.append(f"看不到「{pattern}」（{label}）")
    return problems


def find_bun():
    """照启动器 find_bun 的读法找 Bun：PATH 上第一个 bun.exe，没有就取第一个 bun.cmd 旁边的 bun.exe。"""
    dirs = [d for d in os.environ.get("PATH", "").split(os.pathsep) if d and os.path.isabs(d)]
    for d in dirs:
        candidate = Path(d) / "bun.exe"
        if candidate.is_file():
            return candidate
    for d in dirs:
        if (Path(d) / "bun.cmd").is_file():
            candidate = Path(d) / "node_modules" / "bun" / "bin" / "bun.exe"
            if candidate.is_file():
                return candidate
    return None


def _ts_env():
    env = dict(os.environ)
    env.update({"CI": "true", "NO_COLOR": "1"})
    for name in _ENV_DROP:
        env.pop(name, None)
        env.pop(name.lower(), None)
    return env


def _kill_tree(proc):
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=60)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def run_capture(argv, cwd, timeout):
    start = time.monotonic()
    proc = subprocess.Popen(argv, cwd=str(cwd), env=_ts_env(), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
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


def _deps_ready():
    return ((TS / "node_modules" / ".themis-installed").is_file()
            and (TS / "node_modules" / "vitest").is_dir())


# ---------------------------------------------------------------------------
# 静态断言：secretentry.ts（常量、argv、握手、校验、状态码、重查、投影）
# ---------------------------------------------------------------------------

def test_static_secret_entry_module():
    """D01–D06：新文件 secretentry.ts 导出 secretEntryRoutes(runner, jobs, timeouts)、五个时限常量、
    SECRET_ENTRY_ARGV（六项、无 --verify/--tty）、握手正则（两头锚定、令牌定长 32）与端口范围 1–65535、
    固定提示、201/502/503/504、timeouts 的两个覆盖键、重查 argv（config secret check，不带 --json）、
    secretCheckData 投影、data 的 Map 构造、set 白名单投影（无 verified）。"""
    code = strip_ts_comments(need_file(SECRETENTRY_REL))
    problems = []
    if not re.search(r"export\s+function\s+secretEntryRoutes\s*\(", code):
        problems.append("secretentry.ts 应导出 secretEntryRoutes(runner, jobs, timeouts)")
    else:
        sig = _block(code, "export function secretEntryRoutes", ")")
        for token in ("KernelRunner", "JobTable"):
            if token not in sig:
                problems.append(f"secretEntryRoutes 的签名里应有 {token}")
        if "timeouts" not in sig:
            problems.append("secretEntryRoutes 的签名应有 timeouts 参数（测试入口的时限覆盖）")
    for name, value in SECRET_ENTRY_CONSTANTS.items():
        m = re.search(rf"{name}\s*=\s*([^;\n]+)", code)
        if m is None:
            problems.append(f"secretentry.ts 应导出常量 {name}（= {value}）")
            continue
        rhs = m.group(1)
        if str(value) not in rhs:
            # JOB_SECONDS 允许写成 PAGE + MARGIN（600 + 30 = 630）
            if not (name == "SECRET_ENTRY_JOB_SECONDS" and "PAGE_SECONDS" in rhs and "MARGIN_SECONDS" in rhs):
                problems.append(f"{name} 的值应是 {value}，实际：{rhs.strip()[:60]}")
    if not re.search(r"export\s+const\s+SECRET_ENTRY_ARGV", code):
        problems.append("secretentry.ts 应导出 SECRET_ENTRY_ARGV 登记表（示例名 EXAMPLE_KEY）")
    else:
        block = _block(code, "SECRET_ENTRY_ARGV")
        if not _argv_written(block, *SECRET_ENTRY_ARGV_PARTS):
            problems.append("SECRET_ENTRY_ARGV 应恰好是 " + " ".join(SECRET_ENTRY_ARGV_PARTS))
    for bad in ("--verify", "--tty"):
        if bad in code:
            problems.append(f"secretentry.ts 不许出现 {bad}（不开放 --verify 与 --tty）")
    # 握手正则：127.0.0.1 锚定、端口 1–5 位数字、令牌恰好 32 个字符，端口数值再核 1–65535
    for token in ("127\\.0\\.0\\.1", "\\d{1,5}", "[A-Za-z0-9_-]{32}", "65535"):
        if token not in code:
            problems.append(f"握手的核对应有「{token}」（整串匹配、令牌定长 32、端口范围 1–65535）")
    for message in ENTRY_MESSAGES:
        if message not in code:
            problems.append(f"校验的固定提示「{message}」不在 secretentry.ts")
    for status in ("201", "502", "503", "504"):
        if not re.search(rf"(?<!\d){status}(?!\d)", code):
            problems.append(f"录入路由的响应应用到状态码 {status}")
    for key in ('"job"', '"url"'):
        if key not in code and key.strip('"') not in code:
            problems.append(f"响应正文应有键 {key}（{{job, url}}，不套七字段信封）")
    if "jobView" not in code:
        problems.append("响应里的 job 应是 jobView 的八键投影")
    if "allowEnvName" not in code:
        problems.append("凭据名应过 allowEnvName（@themis/base/secrets，不像令牌）")
    if "canAccept" not in code:
        problems.append("建作业之前应先看 runner.canAccept()（503 且不建作业）")
    if not re.search(r"[Rr]etry-[Aa]fter", code):
        problems.append("503 应带 Retry-After: 2")
    for key in ("job.secret-entry", "secret-entry.handshake"):
        if key not in code:
            problems.append(f"timeouts 的覆盖键「{key}」不在 secretentry.ts（CLI 与环境变量碰不到）")
    # 重查：config secret check <name>（不带 --json），投影用 readroutes 的 secretCheckData
    if not _argv_written(code, "config", "secret", "check"):
        problems.append("重查的 argv 应是 config secret check <name>")
    if "secretCheckData" not in code:
        problems.append("check 的投影应用 readroutes.ts 的 secretCheckData")
    if "verified" in code:
        problems.append("set 的白名单投影应丢掉恒为 null 的 verified")
    for key in ("name", "stored", "backend", "error"):
        if f'"{key}"' not in code:
            problems.append(f"set 的白名单投影应有键「{key}」")
    if "new Map" not in code:
        problems.append("data 一律用 Map 构造（pyjson 只认 Map 与数组，键序 set、check）")
    for key in ('"set"', '"check"'):
        if key not in code:
            problems.append(f"data 的键 {key} 不在 secretentry.ts")
    if "exited" not in code:
        problems.append("录入作业应给 record.exited 赋值（子进程结束就落定，不等重查）")
    if "new AbortController" not in code:
        problems.append("重查应用一个新的 AbortController（只跟服务关停走，不用作业自己那个信号）")
    if "abort" not in code:
        problems.append("等握手到点应 abort 作业（排队出队、在跑整棵树结束）")
    if "settle" not in code:
        problems.append("到点时应先 settle 成 timed_out 再 abort（jobs.ts 的 settle 已导出、只认第一次）")
    fail_if(problems, "secretentry.ts（D01–D06）")


# ---------------------------------------------------------------------------
# 静态断言：kernel.ts 的 onStderr 钩子
# ---------------------------------------------------------------------------

def test_static_kernel_on_stderr():
    """D01：RunHooks 加 onStderr?: (text: string) => void，在 start() 现有的轮询里调用（子进程还在跑、
    stderr 比上次大时把全文交给钩子）；不传钩子时行为不变（读路由与六类作业照旧）。"""
    code = strip_ts_comments(need_file(KERNEL_REL))
    problems = []
    iface = _block(code, "export interface RunHooks", "\n}")
    if "onStderr" not in iface:
        problems.append("RunHooks 应加 onStderr?: (text: string) => void")
    if len(re.findall(r"onStderr", code)) < 2:
        problems.append("onStderr 除了接口声明还应在校验/轮询里被调用")
    if "readOutput" not in code:
        problems.append("读 stderr 应用 readOutput（读不到就跳过这一轮：ENOENT 不算失败）")
    if "OUTPUT_POLL_MS" not in code:
        problems.append("onStderr 应挂在现有 OUTPUT_POLL_MS 的轮询里")
    fail_if(problems, "kernel.ts 的 onStderr（D01）")


# ---------------------------------------------------------------------------
# 静态断言：jobs.ts 的 kind 放宽与 exited
# ---------------------------------------------------------------------------

def test_static_jobs_secret_entry_kind():
    """D06/D10：JobRecord.kind 与 JobTable.create 的 kind 参数放宽成 JobKind | "secret-entry"；JobRecord 加
    exited: Promise<void>（六类作业的 exited 就是 run）；JobKind 六项一个不动。"""
    code = strip_ts_comments(need_file(JOBS_REL))
    problems = []
    widened = re.findall(r'JobKind\s*\|\s*"secret-entry"', code)
    if len(widened) < 2:
        problems.append('JobRecord.kind 与 JobTable.create 的 kind 参数都应放宽成 JobKind | "secret-entry"'
                        f"（实际 {len(widened)} 处）")
    iface = _block(code, "export interface JobRecord", "\n}")
    if "exited" not in iface:
        problems.append("JobRecord 应加字段 exited: Promise<void>")
    if "run: Promise<void>" not in code and "run:" not in iface:
        problems.append("JobRecord 的 run 字段应保留（六类作业的 exited 就是它）")
    kinds = _block(code, "export type JobKind", ";")
    for kind in SIX_KINDS:
        if f'"{kind}"' not in kinds:
            problems.append(f"JobKind 六项里的「{kind}」不见了")
    if "secret-entry" in kinds:
        problems.append('JobKind 不许收 "secret-entry"（六项一个不动，T017 门禁钉着）')
    fail_if(problems, "jobs.ts 的 kind 放宽与 exited（D06/D10）")


# ---------------------------------------------------------------------------
# 静态断言：jobroutes.ts 的 cancelJob 与控制取消路由
# ---------------------------------------------------------------------------

def test_static_jobroutes_cancel_job():
    """D07/D10：导出 cancelJob(table, id)（api.jobs.cancel 与 control.jobs.cancel 共用）；新路由
    control.jobs.cancel 标 control: true、不标 public、路径 /control/jobs/<id>/cancel；取消等 record.exited
    （不等 run，重查没跑完也回）；四张表仍是六项（secret-entry 不进去）。"""
    code = strip_ts_comments(need_file(JOBROUTES_REL))
    problems = []
    if not re.search(r"export\s+(?:async\s+)?function\s+cancelJob\s*\(", code):
        problems.append("jobroutes.ts 应导出 cancelJob(table, id)")
    if len(re.findall(r"cancelJob\s*\(", code)) < 3:
        problems.append("cancelJob 应被两条取消路由共用（定义之外至少两处调用）")
    if "record.exited" not in code:
        problems.append("取消应 await record.exited（不等 run：控制取消不等重查）")
    if "control.jobs.cancel" not in code:
        problems.append("jobRoutes() 里应加控制取消路由 control.jobs.cancel")
    else:
        at = code.find('"control.jobs.cancel"')
        if at < 0:
            at = code.find("'control.jobs.cancel'")
        block = code[at:at + 900]
        if "control: true" not in block:
            problems.append("control.jobs.cancel 应标 control: true")
        if re.search(r"public\s*:\s*true", block):
            problems.append("control.jobs.cancel 不应标 public（门是控制令牌，不是公开）")
        if "/control/jobs/" not in block or "cancel" not in block:
            problems.append("control.jobs.cancel 的路径应是 ^/control/jobs/([^/]+)/cancel$")
        if "cancelJob" not in block:
            problems.append("control.jobs.cancel 的处理函数应只调 cancelJob（门只在 app.ts 一处）")
        if re.search(r"control\.check", block):
            problems.append("处理函数里不许再调 control.check（门只在 app.ts 一处）")
    for table in FOUR_TABLES:
        block = _block(code, table, ";")
        if not block:
            problems.append(f"jobroutes.ts 应有 {table} 登记表")
            continue
        if "secret-entry" in block:
            problems.append(f"{table} 仍是六项，不许收 secret-entry")
    kinds_block = _block(code, "JOB_KINDS", ";")
    for kind in SIX_KINDS:
        if f'"{kind}"' not in kinds_block:
            problems.append(f"JOB_KINDS 六项里的「{kind}」不见了")
    fail_if(problems, "jobroutes.ts 的 cancelJob 与控制取消（D07/D10）")


# ---------------------------------------------------------------------------
# 静态断言：routes.ts 的 control 标记与门的搬移
# ---------------------------------------------------------------------------

def test_static_routes_control_flag():
    """D09/M21：Route 加 control?: true；control.bootstrap 保留 public: true 再加 control: true；令牌比对、
    429 与 Retry-After 全部搬进 app.ts（routes.ts 的处理函数只剩业务：revokeAll 与发新的 nonce）。"""
    code = strip_ts_comments(need_file(ROUTES_REL))
    problems = []
    if not re.search(r"control\?\s*:\s*true", code):
        problems.append("Route 接口应加 control?: true")
    at = code.find('"control.bootstrap"')
    if at < 0:
        at = code.find("'control.bootstrap'")
    if at < 0:
        problems.append("routes.ts 应保留 control.bootstrap 路由")
    else:
        block = code[at:at + 900]
        if not re.search(r"public\s*:\s*true", block):
            problems.append("control.bootstrap 应保留 public: true（T016 门禁要求恰好两处 public）")
        if not re.search(r"control\s*:\s*true", block):
            problems.append("control.bootstrap 应加 control: true")
    if re.search(r"control\.check", code):
        problems.append("routes.ts 里不应再有令牌门（state.control.check 搬进 app.ts）")
    if re.search(r"[Rr]etry-[Aa]fter", code):
        problems.append("routes.ts 里不应再有 429 的 Retry-After（搬进 app.ts）")
    if len(re.findall(r"revokeAll", code)) < 2:
        problems.append("control.bootstrap 的处理函数应只剩业务（revokeAll 两次）")
    fail_if(problems, "routes.ts 的 control 标记（D09）")


# ---------------------------------------------------------------------------
# 静态断言：app.ts 的控制门（一次过 Origin 与令牌两道、免 CSRF、删特判）
# ---------------------------------------------------------------------------

def test_static_app_control_gate():
    """D09/M16–M22：app.ts 按 match.route.control 判定——先 controlOriginAllowed（不过 403，不计入限速），
    再 state.control.check（403 / 429 带 Retry-After=retryAfterSeconds），两道都过跳过 CSRF 与读正文；
    按路由名 control.bootstrap 的两处特判删净；普通 POST 的 CSRF 与读正文照旧。"""
    code = strip_ts_comments(need_file(APP_REL))
    problems = []
    for token in ("controlOriginAllowed", "state.control.check", "retryAfterSeconds", "retry-after"):
        if token not in code:
            problems.append(f"app.ts 的控制门应有「{token}」")
    if not re.search(r"(?:match\.route|route)\.control", code):
        problems.append("app.ts 应按路由的 control 标记判定（不再按路由名特判）")
    if not re.search(r"\b429\b", code):
        problems.append("令牌门 429 的分支应在 app.ts")
    if "control.bootstrap" in code:
        problems.append("app.ts 里按路由名 control.bootstrap 的特判应删净（字符串一个不剩）")
    if "csrfCheck" not in code:
        problems.append("普通 POST 的 CSRF 三查应照旧（control 路由之外）")
    if "readJsonBody" not in code:
        problems.append("普通 POST 的读正文应照旧（control 路由不读）")
    fail_if(problems, "app.ts 的控制门（D09）")


# ---------------------------------------------------------------------------
# 静态断言：server.ts 的接线（过渡断言）
# ---------------------------------------------------------------------------

def test_transitional_server_secret_entry_wiring():
    """过渡断言：将来「合并 extraRoutes 与 kernelAnsweredRoutes 两份构造」的那一片（T020 终审非阻断建议、
    合同 Non-goals 明确不顺手做）会推翻这条白盒断言，届时按名字退役。
    D08/M14：secretEntryRoutes(...) 同时并进 extraRoutes 与 kernelAnsweredRoutes（entry 是内核应答、
    要等握手 N 秒的请求，必须在放宽批次里）。"""
    code = strip_ts_comments(need_file(SERVER_REL))
    problems = []
    if "secretEntryRoutes" not in code:
        problems.append("server.ts 应 import 并调用 secretEntryRoutes(...)")
    total = len(re.findall(r"secretEntryRoutes\s*\(", code))
    if total < 2:
        problems.append(f"secretEntryRoutes 应同时并进 extraRoutes 与 kernelAnsweredRoutes（至少两处调用，实际 {total}）")
    at = code.find("kernelAnsweredRoutes =")
    if at < 0:
        problems.append("server.ts 应保留 kernelAnsweredRoutes 的构造（T019/T020 门禁钉着）")
    elif "secretEntryRoutes(" not in code[at:at + 2500]:
        problems.append("kernelAnsweredRoutes 的表达式里应有 secretEntryRoutes(（entry 必须在放宽批次里）")
    fail_if(problems, "server.ts 的接线（D08/M14）")


# ---------------------------------------------------------------------------
# 静态断言：readroutes.ts 的 secretCheckData 导出
# ---------------------------------------------------------------------------

def test_static_readroutes_export():
    """D06：给 secretCheckData 加一个 export 关键字（重查的投影复用它），行为一个字不改（键 name、source、
    store_mode、system_backend，没有 file_dir）。"""
    code = strip_ts_comments(need_file(READROUTES_REL))
    problems = []
    if not re.search(r"export\s+function\s+secretCheckData", code) and not re.search(
            r"export\s*\{[^}]*secretCheckData", code):
        problems.append("readroutes.ts 的 secretCheckData 应加 export 关键字")
    block = _block(code, "secretCheckData", "\n}")
    for key in ("name", "source", "store_mode", "system_backend"):
        if f'"{key}"' not in block:
            problems.append(f"secretCheckData 的投影键「{key}」不见了（行为一个字不改）")
    if "file_dir" in block:
        problems.append("secretCheckData 不带 file_dir（行为一个字不改）")
    fail_if(problems, "readroutes.ts 的 secretCheckData 导出（D06）")


# ---------------------------------------------------------------------------
# 静态断言：三个新测试文件与新替身
# ---------------------------------------------------------------------------

def test_static_new_test_files():
    """D01–D12：三个新测试文件与新替身在位且要点齐备（token 表对应合同第 2/10 步点名的记号），不许出现
    skip、only、todo。既有测试文件（kernel-runner/jobs/jobs-service/support.ts）一个字不改由调度器的范围
    门禁机械证明（合同 v2 的 forbidden_paths），本文件不写判据（T021-4 一审 B2：整文件否定是范围门禁的
    弱化重复，还会误伤后续片的合法新用例）。"""
    missing = [rel for rel in NEW_FILE_RELS if not (REPO_ROOT / rel).is_file()]
    if missing:
        fail_if([f"{rel} 不存在（合同 Steps 锁定的基准测试文件）" for rel in missing], "新测试文件在位")
        return
    checks = (
        (SECRET_ENTRY_TEST_REL, SECRET_ENTRY_TEST_TOKENS),
        (CONTROL_ROUTES_TEST_REL, CONTROL_ROUTES_TEST_TOKENS),
        (SECRET_ENTRY_REAL_REL, SECRET_ENTRY_REAL_TOKENS),
        (FAKE_SECRET_REL, FAKE_SECRET_KERNEL_TOKENS),
    )
    problems = []
    for rel, tokens in checks:
        text = strip_ts_comments(need_file(rel))
        problems += [f"{rel}：{p}" for p in _token_problems(text, tokens)]
        problems += [f"{rel}：{p}" for p in _no_skip_marks(text)]
    fail_if(problems, "三个新测试文件与新替身的要点（D01–D12）")


def test_static_routes_auth_appended():
    """D13/D16：routes-auth.test.ts 只追加——entry 路由不带 cookie 回 401 的新表在位，既有的 19 条断言
    （expect(listed.length).toBe(19)）一字不动。"""
    raw = need_file(ROUTES_AUTH_REL)
    code = strip_ts_comments(raw)
    problems = []
    if "api.secrets.entry" not in code:
        problems.append("routes-auth.test.ts 应追加 entry 路由（api.secrets.entry）不带 cookie 回 401 的新表")
    if "401" not in code:
        problems.append("routes-auth.test.ts 应断言不带 cookie 一律 401")
    if "expect(listed.length).toBe(19)" not in raw:
        problems.append("routes-auth.test.ts 的「正好 19 条」断言不见了（只追加，一字不动）")
    problems += _no_skip_marks(code)
    fail_if(problems, "routes-auth.test.ts 只追加（D13/D16）")


# ---------------------------------------------------------------------------
# 静态断言：README 只追加
# ---------------------------------------------------------------------------

def test_static_readme_additions():
    """D13：README 只追加——录入路由（POST /api/v1/secrets/<name>/entry）与控制取消
    （POST /control/jobs/<id>/cancel）两条写进去；既有被门禁逐字钉住的句子一个字不动（T015/T017/T019/T020
    的 README 断言另查，本文件只查新增的两条）。"""
    text = need_file(README_REL)
    problems = []
    if "/api/v1/secrets/<name>/entry" not in text:
        problems.append("README 应追加录入路由（POST /api/v1/secrets/<name>/entry）")
    if "录入" not in text:
        problems.append("README 应写到凭据录入（本片的新能力）")
    if "/control/jobs/" not in text:
        problems.append("README 应追加控制取消路由（POST /control/jobs/<id>/cancel）")
    if "control: true" not in text and "Route.control" not in text and "按 control" not in text:
        problems.append("README 应写到控制门按 Route.control 统一判断（不再按路由名特判）")
    fail_if(problems, "README 只追加（D13）")


# ---------------------------------------------------------------------------
# 会话级流水线夹具：vitest 跑新/改测试文件与被锁定的既有用例文件
# ---------------------------------------------------------------------------

class Group:
    def __init__(self, name):
        self.name = name
        self.problems = []

    def check(self, cond, msg):
        if not cond:
            self.problems.append(msg)
        return bool(cond)


class Pipeline:
    def __init__(self):
        self.ran = False
        self.reason = ""
        self.stopped_reason = ""
        self.groups = {}

    def group(self, name):
        grp = Group(name)
        self.groups[name] = grp
        return grp


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    missing = [rel for rel in NEW_FILE_RELS if not (REPO_ROOT / rel).is_file()]
    if missing:
        pipe.reason = ("候选里还没有本片的测试文件（基线 1a58dd3，凭据录入作业与控制取消还没实现），未装依赖、"
                       "未起 vitest；执行端实现之后，流水线才会运行 bun install 与 vitest")
        return pipe
    node = shutil.which("node")
    if node is None:
        pipe.reason = "PATH 上找不到 node.exe（vitest 用 node 起）"
        return pipe
    bun = find_bun() if not _deps_ready() else None
    if bun is None and not _deps_ready():
        pipe.reason = "依赖不齐且 PATH 上找不到 Bun（bun.exe 或 npm 的 bun.cmd 垫片旁边的 bun.exe）"
        return pipe
    pipe.ran = True
    deadline = time.monotonic() + PIPELINE_BUDGET
    try:
        if not _deps_ready():
            remaining = deadline - time.monotonic()
            if remaining <= 120:
                pipe.stopped_reason = "整体预算将尽，bun install 未运行"
            else:
                code, timed_out, out, seconds = run_capture(
                    [str(bun), "install", "--frozen-lockfile"], TS,
                    min(STEP_CAPS["bun install"], remaining))
                if code != 0:
                    pipe.stopped_reason = (f"bun install 退出码 {code}{'（超时被杀）' if timed_out else ''}，"
                                           f"用时 {seconds:.0f}s：{out[-800:]}")
        if not _deps_ready() and not pipe.stopped_reason:
            pipe.stopped_reason = "bun install 之后依赖仍不齐（node_modules/.themis-installed 不在）"
        if not pipe.stopped_reason:
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in NEW_GROUP_RELS],
                    "vitest-new", min(deadline - 160, time.monotonic() + STEP_CAPS["vitest new"]))
        if not pipe.stopped_reason:
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in REAL_GROUP_RELS],
                    "vitest-real", min(deadline - 100, time.monotonic() + STEP_CAPS["vitest real"]))
        if not pipe.stopped_reason:
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in LOCKED_GROUP_RELS],
                    "vitest-locked", min(deadline - 20, time.monotonic() + STEP_CAPS["vitest locked"]))
    finally:
        pass
    return pipe


def _vitest(pipe, node, files, label, cap):
    """起一次 vitest run（cwd：ts），退出码 0 且 Tests 行 passed 才算过。"""
    grp = pipe.group(label)
    if cap <= 30:
        grp.check(False, f"{label} 未运行：整体预算将尽（cap={cap:.0f}s）")
        return grp
    argv = [node, os.path.join("node_modules", "vitest", "vitest.mjs"), "run", *files]
    code, timed_out, out, seconds = run_capture(argv, TS, cap)
    if not grp.check(code == 0,
                     f"vitest（{' '.join(files)}）退出码 {code}{'（超时被杀）' if timed_out else ''}，"
                     f"用时 {seconds:.0f}s：{out[-1500:]}"):
        return grp
    grp.check(re.search(r"Tests[^\n]*[1-9]\d*[^\n]*passed", out) is not None,
              f"vitest 的 Tests 行应有 passed 计数：{out[-600:]}")
    grp.check(re.search(r"(?:Tests|Test Files)[^\n]*\bfailed\b", out) is None,
              f"vitest 的汇总行不应有 failed：{out[-600:]}")
    return grp


# ---------------------------------------------------------------------------
# 流水线断言（pipeline 会话级夹具；全量 pytest 默认跳过，点名运行本文件才跑）
# ---------------------------------------------------------------------------

def _pipeline_group(pipeline, name):
    assert pipeline.ran, pipeline.reason or "流水线没有运行"
    grp = pipeline.groups.get(name)
    if grp is None:
        assert not pipeline.stopped_reason, f"{name} 未运行：{pipeline.stopped_reason}"
    assert grp is not None, f"{name} 未运行"
    fail_if(grp.problems, f"{name}（流水线 vitest）")


def test_pipeline_ran(pipeline):
    """流水线真的跑了（三个新测试文件与新替身在位、bun/node 找得到、依赖装好、vitest 起了）。"""
    assert pipeline.ran, pipeline.reason
    assert not pipeline.stopped_reason, f"流水线中途停了：{pipeline.stopped_reason}"


def test_pipeline_new_tests(pipeline):
    """D01–D11 的机械判据：secret-entry（argv 逐字对照、握手正例反例、令牌四处搜不到、504/502/取消、四张表
    400）与 control-routes（表驱动 403/429、探针路由、取消 404/409/200、取消不等重查）在 vitest 下全过。"""
    _pipeline_group(pipeline, "vitest-new")


def test_pipeline_real_kernel(pipeline):
    """D12 的机械判据：secret-entry-real（CODEKIT_SECRET_STORE=file 与临时 XDG_CONFIG_HOME 经 startService 的
    env 传进内核、录入前 store_mode/system_backend 核对、保存之后 succeeded/check.source 是 file）在 vitest 下
    全过。"""
    _pipeline_group(pipeline, "vitest-real")


def test_pipeline_locked_existing(pipeline):
    """D13/D16 的机械判据：app、routes-auth、kernel-runner、jobs、jobs-service、service 这些被改动的源文件
    波及的既有用例在 vitest 下全过（一条不推翻）。"""
    _pipeline_group(pipeline, "vitest-locked")
