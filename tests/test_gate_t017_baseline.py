"""T017 战前门禁：桌面端本机服务第 3 片（SSE 与作业，D1-C 后半之一）的黑盒基准测试
（合同 t017-desktop-ui-live 第二稿正文，plan_version 2（协调人称 v3），基线 d329e518ef340509e699b14849257882c834158f）。

被测对象是 ``ts/packages/ui`` 的第 3 片：SSE 路由 ``GET /api/v1/events``（快照与序号、心跳与 retry、去抖与共享、
只 stat 内核名单、跳过重解析点、会话失效即断流、``server.timeout(req, 0)`` 只放宽这一条连接、全局 16 / 每会话 4 的
订阅上限、心跳写失败立刻清理、订阅算活动），作业路由 ``POST /api/v1/jobs``、``GET /api/v1/jobs/<id>``、
``POST /api/v1/jobs/<id>/cancel``（六 kind、严格参数校验、43 位随机作业号、容量 100、四种终态、取消结束整棵进程树；
创建回 201、创建与查询的正文都是顶层八键作业对象、不套信封，D31），
第 2 片复核留下的三条加固（H1 输出上限边写边看、H2 真内核拒绝越界路径、H3 关停清队列并摘监听），以及 D11/D12 的
计时抖动（两段式发送，断言只加强不放宽）。

基线（d329e51）上四个新源文件（watch、events、jobs、jobroutes）与四个新测试文件都不存在，既有文件里也没有本片的
标记，所以本文件的失败落在「文件不存在」「标记不在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，
所有仓库文件的读取都发生在用例函数里；流水线（真的起 Bun 服务、发 HTTP 与 SSE 请求）放在 ``pipeline`` 会话级夹具
里，候选里没有新源文件时不装依赖、不起服务。

结构（编号对应合同 DoD 的 D01–D31；合同 M1–M25 的抓住靠这些断言加被锁定的白盒用例，战后门禁另出变异清单）：

- 静态断言（不用流水线，全量 pytest 也跑）：
  - 四个新源文件在位、且都能从 main.ts 顺 import 到达（D25，接进产品才算实现）；
  - 新路由另建 eventRoutes()/jobRoutes()（不并进 readRoutes()）、server.ts 把三批合成一批交给 createApp；
    既有「读路由表正好 19 条」两处断言一字不动（tests/test_gate_t016_baseline.py 的哨兵与
    ts/packages/ui/test/routes-auth.test.ts 的 19 名表 + toBe(19)，另加四行新表，D01/D12）；
  - 名单从 @themis/contracts/status-inputs.json 取、ui 包里没有名单副本（``<task>/`` 字样不许出现在 ui src）、
    ui 包依赖清单仍是 base+contracts 两项（D05/D26）；
  - events.ts：路由与报文（text/event-stream、retry、snapshot/update、id、: hb）、四个常量（2000/300/15000/3000）、
    status 走共享执行器、queue-full/closing 与 timeout 信封（D01/D02/D04/D07/D08）；
  - 订阅上限（MAX_SUBSCRIPTIONS=16、MAX_SUBSCRIPTIONS_PER_SESSION=4、两条错误信封原文、不挤已有订阅、名额归还）
    与 ServeOverrides 六个新覆盖项（D27）；
  - 会话作废关流（Sessions.valid）、hub.close() 排在 runner.shutdown() 之前、心跳写失败清理（D28/D29）；
  - 空闲判定看 hub 与作业、订阅算活动（D30）；
  - server.timeout(req, 0) 只作用于 SSE、全局 idleTimeout 只能由 bunIdleTimeoutSeconds 覆盖（D10）；
  - watch.ts：名单导入、isReparsePoint 复用、root-reparse、bigint stat、fs/promises（D05/D06）；
  - 作业三路由、四类校验（PLAN_KEY_RE 形状、TASK_ID_RE、max 1–1000、pattern 512 与控制字符）、六 kind 的
    JOB_ARGV/JOB_TIMEOUTS（600/150/120/180、``--`` 分隔符、示例值）、JOB_ALLOW 恰好六项全 undefined、
    作业表（randomBytes(32)/43 位/MAX_JOBS=100/淘汰/canAccept）、状态机与取消、二道脱敏（D12–D19）；
  - kernel.ts 的 H1（OUTPUT_POLL_MS=100、statSync 轮询、overflow 先判、结束后兜底、finally 清定时器）、
    H3（release 挂到 Entry、shutdown 逐个调用）、canAccept、hooks.onStart（D20/D22）；
  - D11/D12 的抖动（harness 的 chunkedWatch 两段式 heldBack/sent、service.test 的 heldBack 与 ECONNRESET）（D23）；
  - 合同锁定的 14 个基准测试文件（4 新 + 10 追加）在位且要点齐备（含 routes-auth 的新表、fake-kernel 的
    FAKE_KERNEL_PLAN、argv-templates 的 JOB_ARGV 与四个 pattern、kernel-real 的越界路径、
    events-service 的 U17–U21）（D21/D25）；
  - README 写到新路由、SSE、订阅上限、作业与已知限制（V08 的口径）（D25）；
  - localhttp 的地基原样（revokeAll/valid、withSecurityHeaders 流式转交、isReparsePoint）（D26）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：三个覆盖入口的服务——
  主服务（heartbeatMs=300、maxSubscriptions=2、maxSubscriptionsPerSession=4）：新路由不带 cookie 一律 401、
  POST 缺 CSRF 403 / 非对象正文 400（D01/D12/D13）；SSE 流的头与 retry: 3000、snapshot id=1、data 是
  ``status --json`` 的七字段信封、: hb 心跳、连接活过 12 秒（Bun 缺省空闲超时掐不断，D02/D04/D10 的 M21）、
  内容不变不加号（第二个订阅者的 snapshot 序号仍是 1）、带 Last-Event-ID 的第二条订阅第一条仍是 snapshot
  （D02）；全局上限第 3 条 503 + Retry-After: 2 + 错误信封原文、已有订阅照旧收心跳、关掉一条名额归还（D27）；
  心跳写失败立刻清理（名额归还，D29）；作业 400 一组、404 同文、创建回 201 且顶层八键（D31）、
  GET 只认顶层八键到终态、取消已结束 409（D13/D16/D17/D18/D31）；
  会话上限服务（perSession=1）：同会话第 2 条 503 会话级原文、control.bootstrap 换发引导地址后旧订阅被关、
  新会话可订阅（D27/D28）；空闲服务（idle 3 秒）：订阅开着服务不退出、断开后自己退出（D30/U21）。
  名单变化触发 update 的黑盒验证需要 status 输出随 runs 变化（真内核在非 git 目录上恒退 2，输出恒定，
  ASSUMPTIONS 有记录），由被锁定的 events-service.test.ts（替身 status 读夹具文件）钉住，不在流水线里。

合同没有写死、门禁端按最合理读法定下的地方（交付信「需协调人决定」里逐条列出，终审可改）：见 ``ASSUMPTIONS``。
"""

import base64
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TS = REPO_ROOT / "ts"
UI_SRC = TS / "packages" / "ui" / "src"
UI_TEST = TS / "packages" / "ui" / "test"
UI_README = TS / "packages" / "ui" / "README.md"
MAIN_REL = "ts/packages/ui/src/main.ts"

# 合同 Scope：四个新源文件（SSE 与作业的那一片）
NEW_SRC_RELS = (
    "ts/packages/ui/src/watch.ts",
    "ts/packages/ui/src/events.ts",
    "ts/packages/ui/src/jobs.ts",
    "ts/packages/ui/src/jobroutes.ts",
)
# 合同 Steps 锁定的基准测试文件（执行端不许删改既有用例；新文件按合同要点写）
LOCKED_NEW_TEST_RELS = (
    "ts/packages/ui/test/events.test.ts",
    "ts/packages/ui/test/events-service.test.ts",
    "ts/packages/ui/test/jobs.test.ts",
    "ts/packages/ui/test/jobs-service.test.ts",
)
LOCKED_MODIFIED_RELS = (
    "ts/packages/ui/test/harness.ts",
    "ts/packages/ui/test/support.ts",
    "ts/packages/ui/test/service.test.ts",
    "ts/packages/ui/test/argv-templates.test.ts",
    "ts/packages/ui/test/kernel-runner.test.ts",
    "ts/packages/ui/test/kernel-real.test.ts",
    "ts/packages/ui/test/routes-auth.test.ts",
    "ts/packages/ui/test/fixtures/fake-kernel.mjs",
    "ts/packages/ui/test/fixtures/serve-overrides.ts",
    "ts/packages/ui/README.md",
)
# 既有 19 条读路由的名字（T016 的口径一条不动；新路由不并进 readRoutes()）
READ_ROUTE_NAMES = (
    "api.meta.get", "api.status.get", "api.attempts.list", "api.attempts.show", "api.attempts.file",
    "api.usage.get", "api.config.get", "api.config.validate", "api.config.history.list",
    "api.config.history.show", "api.roles.get", "api.profiles.get", "api.presets.list",
    "api.presets.diff", "api.runtimes.get", "api.plugins.list", "api.plugins.show",
    "api.secrets.list", "api.secrets.show",
)
# 合同 Behavior contract：三条新路由
NEW_ROUTE_NAMES = ("api.events", "api.jobs.create", "api.jobs.get", "api.jobs.cancel")
# 六个作业 kind 与时限（A8：doctor 与 doctor-record 放宽到 600）
JOB_KINDS = ("doctor", "doctor-record", "runtime-scan", "runtime-probe", "models", "search")
JOB_TIMEOUTS = {"doctor": 600, "doctor-record": 600, "runtime-scan": 150, "runtime-probe": 150,
                "models": 120, "search": 180}
# JOB_ARGV 的示例值（合同：record=demo-task.v1、runtime=demo-runtime、task=demo-task、max=50、pattern=token）
JOB_ARGV_EXAMPLES = {
    "doctor": ("config", "doctor", "--json"),
    "doctor-record": ("config", "doctor", "--record=demo-task.v1", "--json"),
    "runtime-scan": ("config", "runtime", "scan", "--json"),
    "runtime-probe": ("config", "runtime", "probe", "demo-runtime", "--json"),
    "models": ("config", "models", "demo-runtime", "--json"),
    "search": ("logs", "search", "--json", "--task=demo-task", "--max=50", "--", "token"),
}
# 错误信封与提示的原文（合同 Behavior contract）
SSE_LIMIT_GLOBAL_MSG = "ERROR: SSE 订阅数已达上限"
SSE_LIMIT_SESSION_MSG = "ERROR: 该会话的 SSE 订阅数已达上限"
JOB_404_MSG = "没有这个作业"
JOB_409_MSG = "作业已经结束"
TIMEOUT_MSG_HEAD = "命令超时（"
TIMEOUT_MSG_TAIL = "），子进程已结束；请改用 CLI 查看"
# 信封七个字段与次序（第 1 片 envelope.ts 的口径）
ENVELOPE_KEYS = ["ok", "exit_code", "data", "output", "messages", "command", "elapsed_ms"]
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
# ServeOverrides：既有四项只增不减，本片新增六项
OLD_OVERRIDE_FIELDS = ("nonceTtlMs", "maxConcurrent", "maxQueue", "timeouts")
NEW_OVERRIDE_FIELDS = ("statIntervalMs", "debounceMs", "heartbeatMs", "bunIdleTimeoutSeconds",
                       "maxSubscriptions", "maxSubscriptionsPerSession")
# V08 的 README 口径（合同 Validation commands V08 的 need 列表，一字不差）
README_NEEDLES = ("events", "jobs", "Retry-After", "409", "503", "504", "config secret check",
                  "TYPESAFE_API_KEY", "已知限制", "131072", "订阅上限")
# 作业号的形状（crypto.randomBytes(32) 的 base64url，43 个字符）
JOB_ID_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
# D31：创建与查询的正文就是顶层八键作业对象（不套信封、不套 data，一个不能少，值可 null）
JOB_KEYS = {"id", "kind", "state", "reason", "created_ms", "started_ms", "finished_ms", "envelope"}
# SSE 的四个常量（合同：STAT_INTERVAL_MS=2000、DEBOUNCE_MS=300、HEARTBEAT_MS=15000、RETRY_MS=3000）
SSE_CONSTANTS = (("STAT_INTERVAL_MS", 2000), ("DEBOUNCE_MS", 300), ("HEARTBEAT_MS", 15000), ("RETRY_MS", 3000))

ASSUMPTIONS = (
    "「四个新源文件都能从 main.ts 顺 import 到达」按 T015/T016 同一规矩的自查实现：顺着仓库内相对 import 走",
    "「既有 19 条读路由的断言一字不动」按哨兵字符串判（routes-auth.test.ts 的 19 个名字与 toBe(19)、"
    "tests/test_gate_t016_baseline.py 的 READ_ROUTES 表头与最后一条路由名）；逐字 diff 由战后门禁与 review 做",
    "「ui 包里不许出现名单副本」按「去注释后的 ui src 里不出现 `<task>/` 路径模板」判：名单的路径值全都以 "
    "<task>/ 开头，从 JSON 读键（attempt_pattern、numbered_pattern、read_when_running）不算抄",
    "SSE 报文的静态断言只钉字面片段（retry、snapshot、update、: hb、text/event-stream）；逐字节的报文格式、"
    "序号规则与去抖节奏由流水线黑盒与被锁定的 events-service.test.ts 钉住",
    "「空闲判定看 hub 与作业」按 server.ts 的 IdleTimer 回调窗口里有 hub 与 job 的引用判；行为由 U21 的"
    "流水线（订阅开着不退出、断开后退出）与被锁定的 events-service.test.ts 钉住",
    "黑盒流水线起三个服务（主服务 + 会话上限服务 + 空闲服务），都走第 2 片的 serve-overrides 测试入口"
    "（--pyargs-b64 加 --overrides-b64），python 用跑 pytest 的这个解释器、kernel 用 scripts/pi_dispatch.py，"
    "仓库用系统临时目录里的普通目录；真内核在非 git 目录上退出码是 2（已实测），所以作业用例只断言到达终态、"
    "不断言 succeeded",
    "流水线的作业创建用 search kind（非 git 仓库上很快失败到终态）；「400 不起子进程」在黑盒里观察不到，"
    "由被锁定的 jobs.test.ts（每类一条）钉住",
    "「ts/bun.lock 未改」不在本文件静态断言：V01 的 bun install --frozen-lockfile 在依赖或锁文件动了时会失败，"
    "那才是机械判据",
    "全局 idleTimeout 的「生产路径保持缺省」按一审意见 4 的选法二判：server.ts 里没有 idleTimeout 被赋"
    "数字字面量（类型声明、bunIdleTimeoutSeconds 的解构与转交都合法），且 bunIdleTimeoutSeconds 必须在文件里",
    "SSE 的「名单变化触发 update」不在流水线黑盒里验证：真内核在非 git 目录上 Repo.discover 恒退 2、stderr 恒定，"
    "status 输出永远不变，按合同「内容相同不推不加号」永远不会有 update（正确实现上也会红）；git init 又不在"
    "门禁的权限里。这条行为由被锁定的 events-service.test.ts（替身 status 读夹具文件，在真实的文件变化上测；"
    "含 snapshot 与 reconnect 两条命名用例、update 与「序号大于断开之前」的锁定要点，合同 v3）钉住；流水线改钉"
    "它的逆命题——内容不变不加号（第二个订阅者的 snapshot 序号仍是 1）",
    "作业创建与查询的响应形状按合同 v3 的 D31 定死：创建回 201、正文就是顶层八键作业对象；GET 同形状；"
    "流水线只认顶层、不认 data 包一层（一审意见 3，不再两认）",
    "hub.close() 的「关停与空闲退出两处」按合同「空闲退出走同一条路」只断 shutdown 里 hub.close() 排在"
    "runner.shutdown() 之前；不要求 hub.close 出现两次（单一次 shutdown 同路实现同样满足合同）",
)

# 流水线预算：合同 G01 的超时是 600 秒，留出静态用例与 pytest 自身的开销。
PIPELINE_BUDGET = 520
STEP_CAPS = {"bun install": 240, "service checks": 420}
SSE_READ_TIMEOUT = 20

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
    """argv 模板片段在不在：连写（``config doctor``）或相邻的数组元素（``"config", "doctor"``）都算。"""
    if " ".join(parts) in code:
        return True
    for quote in ('"', "'"):
        elems = ("," + r"\s*").join(quote + re.escape(part) + quote for part in parts)
        if re.search(elems, code) is not None:
            return True
    return False


def _num_near(code, name, value):
    """常量定义形如 ``NAME = 2000``（允许数字分隔符 2_000 与类型标注）。"""
    digits = str(value)
    sep = r"_?" if len(digits) > 3 else ""
    pattern = digits[0] + "".join(sep + d for d in digits[1:])
    return re.search(rf"\b{name}\b[^=\n;{{}}]*=\s*{pattern}\b", code) is not None


IMPORT_RE = re.compile(r"""(?:\bimport|\bexport)\s*(?P<head>[^'"`;()]*?)\bfrom\s*['"](?P<from>[^'"]+)['"]"""
                       r"""|\bimport\s*['"](?P<bare>[^'"]+)['"]"""
                       r"""|\bimport\s*\(\s*['"](?P<dyn>[^'"]+)['"]\s*\)""")
RESOLVE_SUFFIXES = ("", ".ts", ".tsx", "/index.ts", "/index.tsx")


def import_specs(text):
    specs = []
    for m in IMPORT_RE.finditer(strip_ts_comments(text)):
        if m.group("from") is not None:
            if re.match(r"\s*(?:type\b|\{\s*\}\s*$)", m.group("head")):
                continue
            specs.append(m.group("from"))
        else:
            specs.append(m.group("bare") or m.group("dyn"))
    return [s for s in specs if s.startswith(".") and "?" not in s]


def resolve_import(files, current, spec):
    base = os.path.normpath(os.path.join(os.path.dirname(current), spec)).replace(os.sep, "/")
    for suffix in RESOLVE_SUFFIXES:
        if base + suffix in files:
            return base + suffix
    return None


def reachable_from(files, entry):
    seen, todo = set(), [entry] if entry in files else []
    while todo:
        cur = todo.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for spec in import_specs(files[cur]):
            nxt = resolve_import(files, cur, spec)
            if nxt is not None and nxt not in seen:
                todo.append(nxt)
    return seen


def ui_src_files():
    files = {}
    if not UI_SRC.is_dir():
        return files
    for path in sorted(UI_SRC.rglob("*.ts")):
        if path.is_file():
            files[path.relative_to(REPO_ROOT).as_posix()] = _read(path)
    return files


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


def _deps_ready():
    return ((TS / "node_modules" / ".themis-installed").is_file()
            and (TS / "node_modules" / "vitest").is_dir())


def _no_skip_marks(text):
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
        if re.search(bad, text):
            problems.append(f"出现 {bad}（不许 skip、only、todo）")
    return problems


def _sse_union():
    """四个新源文件的去注释文本拼在一起（跨文件的合同要点用它找）。"""
    return "\n".join(strip_ts_comments(need_file(rel)) for rel in NEW_SRC_RELS)


# ---------------------------------------------------------------------------
# 静态断言：新源文件在位、接线、既有断言不动
# ---------------------------------------------------------------------------

def test_static_new_sources_in_place():
    """D25：合同点名的四个新源文件都在位（基线上还没有实现）。"""
    missing = [rel for rel in NEW_SRC_RELS if not (REPO_ROOT / rel).is_file()]
    fail_if([f"{rel} 不存在（基线上还没有实现）" for rel in missing], "四个新源文件")


def test_static_import_graph():
    """D25：四个新源文件都能从 main.ts 顺 import 到达（写了却没接进产品的不算实现）。"""
    files = ui_src_files()
    if MAIN_REL not in files:
        fail_if(["ts/packages/ui/src/main.ts 读不到"], "src 接线")
        return
    reached = reachable_from(files, MAIN_REL)
    problems = []
    for rel in NEW_SRC_RELS:
        rel_posix = Path(rel).as_posix()
        if rel_posix not in files:
            problems.append(f"{rel_posix} 不存在")
        elif rel_posix not in reached:
            problems.append(f"{rel_posix} 从 main.ts 顺 import 到不了（写了却没接进产品）")
    fail_if(problems, "src 接线（D25）")


def test_static_route_batches():
    """D01/D12/D25：新路由另建 eventRoutes()/jobRoutes()，server.ts 把三批合成一批交给 createApp；
    readRoutes() 里一条新路由也不许有（19 条读路由的既有断言不动）。"""
    events = strip_ts_comments(need_file("ts/packages/ui/src/events.ts"))
    jobroutes = strip_ts_comments(need_file("ts/packages/ui/src/jobroutes.ts"))
    server = strip_ts_comments(need_file("ts/packages/ui/src/server.ts"))
    readroutes = strip_ts_comments(need_file("ts/packages/ui/src/readroutes.ts"))
    problems = []
    for token in ("eventRoutes", "api.events", "/api/v1/events", "text/event-stream"):
        if token not in events:
            problems.append(f"events.ts 里看不到「{token}」")
    for token in ("jobRoutes", "api.jobs.create", "api.jobs.get", "api.jobs.cancel", "/api/v1/jobs"):
        if token not in jobroutes:
            problems.append(f"jobroutes.ts 里看不到「{token}」")
    for token in ("eventRoutes", "jobRoutes", "readRoutes"):
        if token not in server:
            problems.append(f"server.ts 应把 {token}(...) 合成一批交给 createApp")
    for name in NEW_ROUTE_NAMES:
        if name in readroutes:
            problems.append(f"readroutes.ts 里出现了 {name}（新路由不并进 readRoutes()）")
    for name in READ_ROUTE_NAMES:
        if name not in readroutes:
            problems.append(f"readroutes.ts 里原有的路由 {name} 不见了（19 条一条不动）")
    if (UI_SRC / "eventroutes.ts").is_file():
        problems.append("src/eventroutes.ts 不应存在（eventRoutes() 导出在 src/events.ts 里，合同 v3 第 8 步）")
    # api.events 不标 public（照 T17 走会话检查）
    if re.search(r'name\s*:\s*"api\.events"[\s\S]{0,800}?public\s*:\s*true', events):
        problems.append("api.events 不应标成 public（SSE 也要会话）")
    fail_if(problems, "路由的分批与接线（D01/D12/D25）")


def test_static_routes_auth_19_intact():
    """D01/D12/M10：routes-auth.test.ts 的既有 19 名表与 toBe(19) 一字不动，另加四行新表（不带 cookie 一律 401）；
    T016 门禁文件的哨兵也在。"""
    auth = _read(REPO_ROOT / "ts/packages/ui/test/routes-auth.test.ts")
    problems = []
    for name in READ_ROUTE_NAMES:
        if name not in auth:
            problems.append(f"routes-auth.test.ts 里原有的路由名 {name} 不见了（19 条一条不动）")
    if "expect(listed.length).toBe(19)" not in auth:
        problems.append("routes-auth.test.ts 的「正好 19 条」断言（expect(listed.length).toBe(19)）不见了")
    for name in NEW_ROUTE_NAMES:
        if name not in auth:
            problems.append(f"routes-auth.test.ts 应另立新表（四行：{name}）")
    if "401" not in auth:
        problems.append("routes-auth.test.ts 的新表应断言不带 cookie 一律 401")
    problems += [f"routes-auth.test.ts：{p}" for p in _no_skip_marks(strip_ts_comments(auth))]
    gate16 = _read(REPO_ROOT / "tests/test_gate_t016_baseline.py")
    if "READ_ROUTES = (" not in gate16 or "api.secrets.show" not in gate16:
        problems.append("tests/test_gate_t016_baseline.py 的 19 条读路由表（哨兵）不见了")
    fail_if(problems, "既有 19 条断言不动 + 新表（D01/D12）")


def test_static_roster_source():
    """D05/D26/M3：名单从 @themis/contracts/status-inputs.json 导入（A1 的两种写法都认这一份文件）；
    ui src 里不出现名单的路径模板（<task>/ 开头）；ui 包依赖清单仍只有 base 与 contracts。"""
    watch = strip_ts_comments(need_file("ts/packages/ui/src/watch.ts"))
    problems = []
    if "@themis/contracts/status-inputs.json" not in watch:
        problems.append("watch.ts 应从 @themis/contracts/status-inputs.json 取名单（A1）")
    for token in ("attempt_pattern", "numbered_pattern", "read_when_running"):
        if token not in watch:
            problems.append(f"watch.ts 应读名单的「{token}」键")
    for rel, text in ui_src_files().items():
        code = strip_ts_comments(text)
        if "<task>/" in code:
            problems.append(f"{rel} 里出现了名单的路径模板「<task>/」（名单的值不许抄进 ui 包）")
    pkg = json.loads(need_file("ts/packages/ui/package.json"))
    deps = set(pkg.get("dependencies", {}))
    if deps != {"@themis/base", "@themis/contracts"}:
        problems.append(f"ui 包的依赖清单应仍只有 base 与 contracts（不加依赖），实际 {sorted(deps)}")
    fail_if(problems, "名单的来源与依赖清单（D05/D26）")


def test_static_event_stream_shape():
    """D01/D02/D04：SSE 报文的字面片段——流一打开先写 retry、事件带 id 与 event: snapshot/update、
    data 行、心跳一行 : hb；content-type 是 text/event-stream; charset=utf-8。"""
    union = _sse_union()
    problems = []
    for token in ("retry", "snapshot", "update", "hb", "id: ", "data: ", "event: "):
        if token not in union:
            problems.append(f"新源文件里看不到 SSE 报文片段「{token}」")
    if "text/event-stream; charset=utf-8" not in union:
        problems.append('content-type 应是 text/event-stream; charset=utf-8')
    for name, value in SSE_CONSTANTS:
        if not _num_near(union, name, value):
            problems.append(f"常量 {name} 应是 {value}（合同四个常量由单元测试钉住）")
    fail_if(problems, "SSE 报文与常量（D01/D02/D04）")


def test_static_event_hub_behavior():
    """D03/D07/D08/D09：status 走第 2 片的执行器（一次一份、全员共享）、超时推超时信封、
    queue-full/closing 记 retryPending、订阅者为 0 停、hub 自己的 AbortController、每次推送与心跳之前查会话。"""
    union = _sse_union()
    problems = []
    if not _argv_written(union, "status", "--json"):
        problems.append("EventHub 的 status 应跑 status --json（与读路由共用执行器）")
    if "timeoutEnvelope" not in union:
        problems.append("status 超时应推 timeoutEnvelope（与 /api/v1/status 的 504 同一份）")
    for token in ("queue-full", "closing", "retryPending"):
        if token not in union:
            problems.append(f"EventHub 应处理「{token}」（记 retryPending，下一轮重试）")
    if "AbortController" not in union:
        problems.append("hub 应有自己的 AbortController（订阅者归零时中止在跑的 status）")
    if not re.search(r"\.valid\s*\(", union):
        problems.append("hub 应在每次心跳与推送之前查 Sessions.valid(token)（A4/A11）")
    if not re.search(r"dirty", union):
        problems.append("在跑期间又有变化应记 dirty 标记、跑完只补跑一次（去抖）")
    fail_if(problems, "EventHub 的行为要点（D03/D07/D08/D09）")


def test_static_watch_details():
    """D05/D06/M3/M4：watch.ts 复用 static.ts 的 isReparsePoint、根目录本身是重解析点时整轮指纹是 root-reparse、
    stat 用 bigint（size/mtimeNs/ino）、fs 一律 node:fs/promises 异步、根目录是 <repo>/.agent/runs。"""
    watch = strip_ts_comments(need_file("ts/packages/ui/src/watch.ts"))
    union = _sse_union()
    problems = []
    if "isReparsePoint" not in watch:
        problems.append("watch.ts 应复用 static.ts 的 isReparsePoint（A5，不另写一套）")
    if "root-reparse" not in watch:
        problems.append("根目录本身是重解析点时整轮指纹应记成固定一行「root-reparse」")
    if "node:fs/promises" not in watch:
        problems.append("fs 应一律用 node:fs/promises 的异步调用")
    if not re.search(r"bigint\s*:\s*true", watch):
        problems.append("stat 应带 bigint: true（size/mtimeNs/ino）")
    for token in ("mtimeNs", "ino"):
        if token not in watch:
            problems.append(f"指纹应取「{token}」")
    if ".agent" not in union or "runs" not in union:
        problems.append("stat 的根目录应是 <repo>/.agent/runs")
    if not re.search(r"attempt-\\d|\[0-9\]\{3,\}|attempt_pattern", watch):
        problems.append("task 目录下只认 attempt_pattern（^attempt-\\d{3,}$）")
    fail_if(problems, "watch.ts 的监视细节（D05/D06）")


def test_static_subscription_limits():
    """D27/M22：全局 16、每会话 4（MAX_SUBSCRIPTIONS / MAX_SUBSCRIPTIONS_PER_SESSION），超限 503 带
    Retry-After: 2 与两条错误信封原文；两个数只由 ServeOverrides 覆盖。"""
    union = _sse_union()
    server = strip_ts_comments(need_file("ts/packages/ui/src/server.ts"))
    problems = []
    if not _num_near(union, "MAX_SUBSCRIPTIONS", 16):
        problems.append("全局订阅上限应是 MAX_SUBSCRIPTIONS = 16")
    if not _num_near(union, "MAX_SUBSCRIPTIONS_PER_SESSION", 4):
        problems.append("每会话订阅上限应是 MAX_SUBSCRIPTIONS_PER_SESSION = 4")
    if SSE_LIMIT_GLOBAL_MSG[7:] not in union:
        problems.append(f"全局超限的正文应是「{SSE_LIMIT_GLOBAL_MSG}」")
    if SSE_LIMIT_SESSION_MSG[7:] not in union:
        problems.append(f"会话级超限的正文应是「{SSE_LIMIT_SESSION_MSG}」")
    if not re.search(r"[Rr]etry-[Aa]fter", union):
        problems.append("订阅超限的 503 应带 Retry-After")
    for token in ("maxSubscriptions", "maxSubscriptionsPerSession"):
        if token not in server:
            problems.append(f"ServeOverrides 应有 {token}（只给测试入口，CLI 与环境变量碰不到）")
    fail_if(problems, "订阅上限（D27）")


def test_static_disconnect_and_close():
    """D28/D29/M23/M24/M25：会话作废主动关流并清定时器；心跳写失败立刻清理（清定时器、关流、计数各减一）；
    server.ts 的关停先 hub.close() 再 runner.shutdown()，空闲退出走同一条路。"""
    union = _sse_union()
    server = strip_ts_comments(need_file("ts/packages/ui/src/server.ts"))
    problems = []
    if not re.search(r"revokeAll|\.valid\s*\(", union):
        problems.append("会话作废（revokeAll 之后 valid 为 false）应主动关流（A11）")
    if not re.search(r"close", union):
        problems.append("hub 应能关掉订阅者的流（主动断开与写失败清理）")
    i_hub = server.find("hub.close")
    i_runner = server.find("runner.shutdown")
    if i_hub < 0:
        problems.append("server.ts 的 shutdown 应先 hub.close()（关全部流与定时器、中止在跑的 status）")
    elif i_runner >= 0 and i_hub > i_runner:
        problems.append("hub.close() 必须排在 runner.shutdown() 之前（A12；空闲退出走同一条路，见 ASSUMPTIONS）")
    fail_if(problems, "主动断开与关停次序（D28/D29）")


def test_static_bun_idle_timeout():
    """D10/M21：SSE 订阅时对这一条请求调 server.timeout(req, 0)；全局 idleTimeout 生产路径保持缺省
    （server.ts 里不许出现 idleTimeout 被赋数字字面量；类型声明与 bunIdleTimeoutSeconds 的转交都合法，
    覆盖项本身必须在）——一审意见 4 的选法二。"""
    server = strip_ts_comments(need_file("ts/packages/ui/src/server.ts"))
    problems = []
    if not re.search(r"\.timeout\(\s*\w+\s*,\s*0\s*\)", server):
        problems.append("SSE 订阅时应对这一条请求调 server.timeout(req, 0)")
    if "bunIdleTimeoutSeconds" not in server:
        problems.append("ServeOverrides 应有 bunIdleTimeoutSeconds（测试入口才碰得到全局 idleTimeout）")
    for m in re.finditer(r"idleTimeout\s*[:=]\s*\d", server):
        problems.append(f"生产路径不许给 idleTimeout 设数字字面量（只许由 bunIdleTimeoutSeconds 覆盖，"
                        f"位置 {m.start()}：{server[m.start():m.end()]!r})")
        break
    fail_if(problems, "Bun 的连接空闲超时（D10）")


def test_static_idle_counts_subscription():
    """D30/M20：空闲判定加上「hub 订阅者为 0」与「没有在等或在跑的作业」，订阅开着算活动。"""
    server = strip_ts_comments(need_file("ts/packages/ui/src/server.ts"))
    problems = []
    i_timer = server.find("new IdleTimer")
    i_app = server.find("createApp(")
    if i_timer < 0 or i_app < 0 or i_timer > i_app:
        problems.append("server.ts 的 IdleTimer 构造应仍在 createApp 之前（找不到判定窗口）")
    else:
        window = server[i_timer:i_app]
        if "hub" not in window:
            problems.append("空闲回调应看 hub 的订阅者数（订阅开着不算空闲）")
        if not re.search(r"job", window, re.I):
            problems.append("空闲回调应看作业表（没有在等或在跑的作业才退出）")
    fail_if(problems, "空闲判定（D30）")


# ---------------------------------------------------------------------------
# 静态断言：作业（路由、校验、argv、作业表、状态机、脱敏）
# ---------------------------------------------------------------------------

def _jobs_union():
    return "\n".join(strip_ts_comments(need_file(rel))
                     for rel in ("ts/packages/ui/src/jobs.ts", "ts/packages/ui/src/jobroutes.ts"))


def test_static_job_routes():
    """D12/D16/M10：三条作业路由（方法与名字）、404 与 409 的提示原文、<id> 是 43 位 base64url。"""
    jobroutes = strip_ts_comments(need_file("ts/packages/ui/src/jobroutes.ts"))
    union = _jobs_union()
    problems = []
    for token in ("POST", "GET", '"api.jobs.create"', '"api.jobs.get"', '"api.jobs.cancel"'):
        if token not in jobroutes:
            problems.append(f"jobroutes.ts 里看不到「{token}」")
    if JOB_404_MSG not in union:
        problems.append(f"不在表里与格式不对应回同一个 404「{JOB_404_MSG}」")
    if JOB_409_MSG not in union:
        problems.append(f"取消已结束的作业应回 409「{JOB_409_MSG}」")
    if not re.search(r"\{43\}|\[A-Za-z0-9_\-\]\{43\}", union):
        problems.append("<id> 应过 ^[A-Za-z0-9_-]{43}$（43 位 base64url）")
    if re.search(r'name\s*:\s*"api\.jobs\.\w+"[\s\S]{0,800}?public\s*:\s*true', jobroutes):
        problems.append("作业路由不应标成 public（也要会话）")
    fail_if(problems, "作业路由（D12/D16）")


def test_static_job_validation():
    """D13/M12：严格参数校验——400、record 过 PLAN_KEY_RE 的形状、runtime/task 过 TASK_ID_RE、
    max 是 1 到 1000 的整数、pattern 是 1 到 512 个码点且不含控制字符。"""
    union = _jobs_union()
    problems = []
    if "400" not in union:
        problems.append("参数不合格应回 400")
    if "TASK_ID_RE" not in union:
        problems.append("runtime 与 task 的校验应过 TASK_ID_RE（@themis/base/secrets）")
    if not re.search(r"\\\.v\[1-9\]", union):
        problems.append("record 的校验应过 PLAN_KEY_RE 的形状（^…\\.v[1-9][0-9]{0,3}$）")
    if not re.search(r"(?<![\d.])1000(?![\d.])", union):
        problems.append("max 应是 1 到 1000 的整数")
    if not re.search(r"(?<![\d.])512(?![\d.])", union):
        problems.append("pattern 应是 1 到 512 个码点")
    raw = need_file("ts/packages/ui/src/jobroutes.ts") + "\n" + need_file("ts/packages/ui/src/jobs.ts")
    if not re.search(r"0000|001[fF]|\\x00|u0000|0x1[fF]|0x7[fF]|<\s*32|<\s*0x20|控制字符", raw):
        problems.append("pattern 不应含 U+0000–U+001F 与 U+007F（控制字符的校验）")
    if not re.search(r"[dD]800|0xffff|0xFFFF|surrogate|代理", raw):
        problems.append("pattern 不应含孤立的代理项（校验或文档写明）")
    fail_if(problems, "作业的严格参数校验（D13）")


def test_static_job_argv():
    """D14/D15/M13：JOB_ARGV 登记表（六个 kind、示例值）、时限照表、search 的 pattern 用 -- 传、
    job.<kind> 作时限覆盖的键。"""
    jobroutes = strip_ts_comments(need_file("ts/packages/ui/src/jobroutes.ts"))
    problems = []
    if "JOB_ARGV" not in jobroutes:
        problems.append("jobroutes.ts 应有 JOB_ARGV 登记表（真内核用例与替身用例逐条对照）")
    if "JOB_TIMEOUTS" not in jobroutes and not re.search(r"TIMEOUTS", jobroutes):
        problems.append("jobroutes.ts 应有作业时限表")
    for kind in JOB_KINDS:
        if kind not in jobroutes:
            problems.append(f"jobroutes.ts 里看不到 kind「{kind}」")
    for kind, argv in JOB_ARGV_EXAMPLES.items():
        if not _argv_written(jobroutes, *argv):
            problems.append(f"{kind} 的 argv 应含「{' '.join(argv)}」")
    for kind, seconds in JOB_TIMEOUTS.items():
        if not re.search(rf"(?<![\d.]){seconds}(?![\d.])", jobroutes):
            problems.append(f"{kind} 的时限 {seconds} 秒不在 jobroutes.ts（A8 的表）")
    if not re.search(r"['\"]job\.['\"]|`job\.|\"job\.", jobroutes):
        problems.append("时限覆盖应用 job.<kind> 作键（测试入口 timeouts）")
    for sample in ("demo-task.v1", "demo-runtime", "token"):
        if sample not in jobroutes:
            problems.append(f"JOB_ARGV 的示例值「{sample}」不在 jobroutes.ts")
    fail_if(problems, "JOB_ARGV 与时限（D14/D15）")


def test_static_job_table():
    """D16/M16/M17：作业号 crypto.randomBytes(32) 转 base64url（43 位、随机不可猜）、容量 MAX_JOBS=100、
    满了淘汰最早终态、没有可淘汰回 503 带 Retry-After、创建之前先看执行器 canAccept。"""
    jobs = strip_ts_comments(need_file("ts/packages/ui/src/jobs.ts"))
    kernel = strip_ts_comments(need_file("ts/packages/ui/src/kernel.ts"))
    union = _jobs_union()
    problems = []
    if "randomBytes" not in jobs:
        problems.append("作业号应用 crypto.randomBytes(32)（随机、不可猜）")
    if not re.search(r"(?<![\d.])32(?![\d.])", jobs):
        problems.append("randomBytes 应取 32 字节（base64url 后 43 个字符）")
    if "base64url" not in jobs:
        problems.append("作业号应转 base64url")
    if not _num_near(union, "MAX_JOBS", 100):
        problems.append("作业表容量应是 MAX_JOBS = 100")
    if "503" not in union:
        problems.append("没有可淘汰的终态作业时应回 503")
    if not re.search(r"[Rr]etry-[Aa]fter", union):
        problems.append("503 应带 Retry-After: 2")
    if "canAccept" not in kernel:
        problems.append("KernelRunner 应加 canAccept()（收不了就不建作业）")
    if "canAccept" not in union:
        problems.append("创建作业之前应先看执行器的 canAccept()（回 503 且不建作业）")
    if "Map" not in jobs:
        problems.append("作业表只在内存里（Map），服务退出就丢")
    fail_if(problems, "作业表（D16）")


def test_static_job_states():
    """D17/D18/M14/M15：queued→running→四种终态只走一次；reason 的取值；超时推 timeoutEnvelope；
    GET 返回 {id, kind, state, reason, created_ms, started_ms, finished_ms, envelope}；每个作业自己的
    AbortController；执行器加 hooks.onStart。"""
    union = _jobs_union()
    kernel = strip_ts_comments(need_file("ts/packages/ui/src/kernel.ts"))
    problems = []
    for state in ("queued", "running", "succeeded", "failed", "cancelled", "timed_out"):
        if state not in union:
            problems.append(f"状态机的「{state}」不见了")
    for reason in ("exit", "spawn-error", "output-too-large", "invalid-json", "closing"):
        if reason not in union:
            problems.append(f"failed 的 reason「{reason}」不见了")
    if "timeoutEnvelope" not in union:
        problems.append("超时的作业终态应带 timeoutEnvelope（data 为 null）")
    for field in ("created_ms", "started_ms", "finished_ms", "envelope", "reason", "kind"):
        if field not in union:
            problems.append(f"GET /api/v1/jobs/<id> 的返回里应有 {field}")
    if "AbortController" not in union:
        problems.append("每个作业应有自己的 AbortController（作业比创建它的 POST 请求活得久）")
    if "onStart" not in kernel:
        problems.append("RunKernel.run 应加可选的第 4 个参数 hooks.onStart（queued 变 running 靠它通知）")
    if "onStart" not in union:
        problems.append("作业应经 hooks.onStart 等执行器通知（读路由不传）")
    fail_if(problems, "状态机与取消（D17/D18）")


def test_static_job_redaction():
    """D19/M11：JOB_ALLOW 恰好六项、全是 undefined；data 过 redactJson；messages 只留 ERROR/WARN 开头的行
    并逐行过 redactSecrets；command 里 search 的 pattern 也过 redactSecrets。"""
    jobroutes = strip_ts_comments(need_file("ts/packages/ui/src/jobroutes.ts"))
    problems = []
    if "JOB_ALLOW" not in jobroutes:
        problems.append("jobroutes.ts 应有 JOB_ALLOW 登记表（恰好六项、全是 undefined）")
    else:
        block = jobroutes[jobroutes.find("JOB_ALLOW"):jobroutes.find("JOB_ALLOW") + 700]
        for kind in JOB_KINDS:
            if kind not in block:
                problems.append(f"JOB_ALLOW 里应有 {kind}")
    if "redactJson" not in jobroutes and "redactJson" not in strip_ts_comments(need_file("ts/packages/ui/src/jobs.ts")):
        problems.append("作业结果应过 redactJson（与读路由同一套二道脱敏）")
    if "redactSecrets" not in jobroutes and "redactSecrets" not in strip_ts_comments(need_file("ts/packages/ui/src/jobs.ts")):
        problems.append("messages 与 pattern 应过 redactSecrets")
    fail_if(problems, "作业结果的脱敏与白名单（D19）")


# ---------------------------------------------------------------------------
# 静态断言：加固（kernel.ts 的 H1/H3）与抖动（harness/service）
# ---------------------------------------------------------------------------

def test_static_h1_output_polling():
    """D20/M18：OUTPUT_POLL_MS=100 的 statSync 轮询、overflow 先于 timed_out 与 interrupted 判定、
    结束后那次检查保留（sizeOf）、轮询定时器在 finally 里清掉。"""
    kernel = strip_ts_comments(need_file("ts/packages/ui/src/kernel.ts"))
    problems = []
    if not _num_near(kernel, "OUTPUT_POLL_MS", 100):
        problems.append("H1 应有 OUTPUT_POLL_MS = 100 的轮询间隔")
    if "statSync" not in kernel:
        problems.append("轮询应用 statSync 看 stdout.txt 与 stderr.txt 的大小")
    for token in ("stdout.txt", "stderr.txt"):
        if token not in kernel:
            problems.append(f"轮询应看「{token}」")
    if "overflow" not in kernel:
        problems.append("超限应记 overflow = true 并中止这次运行自己的 controller")
    if "output-too-large" not in kernel:
        problems.append("overflow 应映射成 output-too-large")
    if not re.search(r"clear(?:Interval|Timeout)", kernel):
        problems.append("轮询定时器应在 finally 里清掉")
    if "sizeOf" not in kernel:
        problems.append("结束后先判 overflow、再判 timed_out/interrupted 的那次兜底检查应保留（sizeOf）")
    fail_if(problems, "H1 输出上限边写边看（D20）")


def test_static_h3_release_on_entry():
    """D22/M19：release 挂到 Entry 上（Entry 上存 release），shutdown 清队列时逐个调用
    （摘掉请求 signal 与关停 signal 上的监听）。"""
    kernel = strip_ts_comments(need_file("ts/packages/ui/src/kernel.ts"))
    problems = []
    if not re.search(r"release\s*:", kernel):
        problems.append("Entry 上应存 release（不再是 run() 里的局部闭包）")
    i_shutdown = kernel.find("async shutdown")
    if i_shutdown < 0:
        problems.append("KernelRunner 应有 shutdown()")
    elif "release" not in kernel[i_shutdown:]:
        problems.append("shutdown 清队列时应逐个调用 release（摘监听）")
    fail_if(problems, "H3 关停清队列并摘监听（D22）")


def test_static_jitter_harness():
    """D23：harness 的 chunkedWatch 改成两段式（分块发到 65537 字节就停、等响应头，返回 heldBack 与 sent）；
    service.test.ts 的 D11 加 heldBack 断言、ECONNRESET 的判定写明。"""
    harness = _read(REPO_ROOT / "ts/packages/ui/test/harness.ts")
    service = _read(REPO_ROOT / "ts/packages/ui/test/service.test.ts")
    problems = []
    for token in ("heldBack", "sent"):
        if token not in harness:
            problems.append(f"harness.ts 的 chunkedWatch 应返回「{token}」（两段式）")
    if "65537" not in harness:
        problems.append("chunkedWatch 应分块发到正文累计 65537 字节（8 块 8192 加 1 字节）")
    if "heldBack" not in service:
        problems.append("service.test.ts 的 D11 应加 heldBack 为真的断言")
    if "ECONNRESET" not in service and "ECONNRESET" not in harness:
        problems.append("ECONNRESET（头到之后不算失败、头没到照旧判失败）应写明")
    problems += [f"service.test.ts：{p}" for p in _no_skip_marks(strip_ts_comments(service))]
    fail_if(problems, "D11/D12 的抖动（D23）")


# ---------------------------------------------------------------------------
# 静态断言：锁定的基准测试文件在位且要点齐备
# ---------------------------------------------------------------------------

def test_static_locked_test_files():
    """D25：合同 Steps 锁定的基准测试文件都在位且要点齐备（新文件按覆盖矩阵，既有文件只追加）。"""
    problems = []
    for rel in LOCKED_NEW_TEST_RELS + LOCKED_MODIFIED_RELS:
        if not (REPO_ROOT / rel).is_file():
            problems.append(f"{rel} 不存在（合同 Steps 锁定的基准测试文件）")
    if problems:
        fail_if(problems, "基准测试文件在位")
        return

    # events.test.ts：四个常量与 retry 由单元测试钉住
    events_unit = _read(REPO_ROOT / "ts/packages/ui/test/events.test.ts")
    for name, value in SSE_CONSTANTS:
        # 数字分隔符写法（15_000）与普通写法（15000）都认
        digits = str(value)
        sep = "_?" if len(digits) > 3 else ""
        tolerant = digits[0] + "".join(sep + d for d in digits[1:])
        if not re.search(tolerant, events_unit):
            problems.append(f"events.test.ts 应钉住常量 {name} = {value}")
    if "3000" not in events_unit or "retry" not in events_unit:
        problems.append("events.test.ts 应钉住 retry 一行恒为 3000")
    problems += [f"events.test.ts：{p}" for p in _no_skip_marks(strip_ts_comments(events_unit))]

    # events-service.test.ts：U17–U21 与 T3 的各条（黑盒，替身 status 读夹具文件）
    events_svc = _read(REPO_ROOT / "ts/packages/ui/test/events-service.test.ts")
    for token, label in (
        ("snapshot", "U17 订阅后第一条是 snapshot（命名用例）"),
        ("reconnect", "U17 的 reconnect 命名用例（序号递增由它钉住，合同 v3）"),
        ("Last-Event-ID", "U17 带 Last-Event-ID 重连第一条仍是 snapshot"),
        ("update", "U17/T3 名单变化推 update（M1 的正向钉子）"),
        ("maxSubscriptions", "U18 订阅上限的覆盖项"),
        ("已达上限", "U18 超限的错误信封原文"),
        ("revokeAll", "U19 会话作废"),
        ("心跳", "U19/U20 心跳"),
        ("写失败", "U20 心跳写失败即清理"),
        ("空闲", "U21 订阅算活动"),
        ("junction", "T3 junction 不跟随"),
        ("逐字节", "T3 推送的 data 与 /api/v1/status 逐字节一致"),
        ("bunIdleTimeoutSeconds", "D10 Bun 空闲超时那条"),
        ("共用", "T3 多订阅者共用一次 status"),
    ):
        if token not in events_svc:
            problems.append(f"events-service.test.ts 里看不到「{token}」（{label}）")
    if not re.search(r"去抖|20\s*次", events_svc):
        problems.append("events-service.test.ts 应有去抖那条（2 秒内写 20 次、status 不超过 2 次）")
    if not re.search(r"序号[\s\S]{0,40}大于|id[^\n]{0,8}(?:为|:|＝|=)\s*[\"']?[2-9]|GreaterThan\(\s*[1-9]",
                     events_svc):
        problems.append("events-service.test.ts 应有序号递增的断言（「序号大于断开之前」或 id 加到 2 以上，"
                        "一审意见 2）")
    problems += [f"events-service.test.ts：{p}" for p in _no_skip_marks(strip_ts_comments(events_svc))]

    # jobs.test.ts / jobs-service.test.ts
    jobs_unit = _read(REPO_ROOT / "ts/packages/ui/test/jobs.test.ts")
    for token, label in (
        ("JOB_ARGV", "argv 与登记表逐条一致"),
        ("JOB_ALLOW", "白名单恰好六项"),
        ("undefined", "全是 undefined"),
        ("43", "作业号 43 位"),
        ("400", "每类校验失败各一例"),
        ("404", "不在表里与格式不对的同一个 404"),
        ("409", "取消已结束的 409"),
    ):
        if token not in jobs_unit:
            problems.append(f"jobs.test.ts 里看不到「{token}」（{label}）")
    if not re.search(r"起子进程|toHaveBeenCalled|没有起", jobs_unit):
        problems.append("jobs.test.ts 应断言 400 的一类不起子进程")
    problems += [f"jobs.test.ts：{p}" for p in _no_skip_marks(strip_ts_comments(jobs_unit))]
    jobs_svc = _read(REPO_ROOT / "ts/packages/ui/test/jobs-service.test.ts")
    for token, label in (
        ("timed_out", "终态 timed_out（search 超时也是它）"),
        ("cancelled", "终态 cancelled"),
        ("search", "search 的作业"),
        ("succeeded", "终态 succeeded"),
        ("failed", "终态 failed"),
        ("201", "D31 创建回 201"),
        ("八键", "D31 创建与查询的八键正文（不套信封）"),
    ):
        if token not in jobs_svc:
            problems.append(f"jobs-service.test.ts 里看不到「{token}」（{label}）")
    if not re.search(r"pidAlive|孙进程", jobs_svc):
        problems.append("jobs-service.test.ts 应证明取消/超时后孙进程也不在了（pidAlive）")
    if "503" not in jobs_svc:
        problems.append("jobs-service.test.ts 应有 503（执行器收不了/表满）的用例")
    problems += [f"jobs-service.test.ts：{p}" for p in _no_skip_marks(strip_ts_comments(jobs_svc))]

    # argv-templates.test.ts：JOB_ARGV 另立一条 describe、四个 pattern 过真内核解析器
    argv_test = _read(REPO_ROOT / "ts/packages/ui/test/argv-templates.test.ts")
    for token in ("JOB_ARGV", "-x", "-1", "logs search"):
        if token not in argv_test:
            problems.append(f"argv-templates.test.ts 里看不到「{token}」")
    if argv_test.count("describe(") < 2:
        problems.append("JOB_ARGV 应另立一条 describe（不并进 READ_ROUTE_ARGV 的既有断言）")
    problems += [f"argv-templates.test.ts：{p}" for p in _no_skip_marks(strip_ts_comments(argv_test))]

    # kernel-runner.test.ts：H1、H3、canAccept、hooks.onStart
    runner = _read(REPO_ROOT / "ts/packages/ui/test/kernel-runner.test.ts")
    for token, label in (
        ("output-too-large", "H1 洪泛输出 10 秒内 output-too-large"),
        ("canAccept", "canAccept 的用例"),
        ("onStart", "hooks.onStart 的用例"),
    ):
        if token not in runner:
            problems.append(f"kernel-runner.test.ts 里看不到「{token}」（{label}）")
    if not re.search(r"监听器|listener|addEventListener", runner):
        problems.append("kernel-runner.test.ts 应有 H3 的监听器归零用例")
    if not re.search(r"1024|1048576|1_048_576|MiB", runner):
        problems.append("kernel-runner.test.ts 的 H1 用例应把上限设成 1 MiB")
    problems += [f"kernel-runner.test.ts：{p}" for p in _no_skip_marks(strip_ts_comments(runner))]

    # kernel-real.test.ts：H2 越界路径与 U10 的真内核
    real = _read(REPO_ROOT / "ts/packages/ui/test/kernel-real.test.ts")
    for token, label in (
        ("../x", "H2 由内核拒绝的越界路径"),
        ("C:/x", "H2 盘符路径"),
        ("a/../../x", "H2 中间翻出"),
        ("..\\x", "H2 反斜杠由服务回 400"),
        ("exit_code", "H2 断言 exit_code 为 2"),
    ):
        if token not in real:
            problems.append(f"kernel-real.test.ts 里看不到「{token}」（{label}）")
    problems += [f"kernel-real.test.ts：{p}" for p in _no_skip_marks(strip_ts_comments(real))]

    # fake-kernel.mjs：FAKE_KERNEL_PLAN 与既有的四个环境变量
    fake = _read(REPO_ROOT / "ts/packages/ui/test/fixtures/fake-kernel.mjs")
    for token in ("FAKE_KERNEL_PLAN", "flood", "sleep", "hang", "spawn-grandchild"):
        if token not in fake:
            problems.append(f"fake-kernel.mjs 里看不到「{token}」（替身计划）")
    for token in ("FAKE_KERNEL_JSON", "FAKE_KERNEL_STDERR", "FAKE_KERNEL_EXIT", "FAKE_KERNEL_SLEEP_MS"):
        if token not in fake:
            problems.append(f"fake-kernel.mjs 里既有的「{token}」不见了（既有用例靠它们）")

    # support.ts：起 hub/作业表的应用辅助与心跳写失败的替身客户端
    support = _read(REPO_ROOT / "ts/packages/ui/test/support.ts")
    if not re.search(r"hub|订阅", support):
        problems.append("support.ts 应追加起 hub/作业表的应用辅助")
    if not re.search(r"心跳|heartbeat|写失败", support):
        problems.append("support.ts 应追加心跳写失败的替身客户端")

    # serve-overrides 测试入口仍在（--pyargs-b64 与 --overrides-b64）
    overrides_entry = _read(REPO_ROOT / "ts/packages/ui/test/fixtures/serve-overrides.ts")
    if "--overrides-b64" not in overrides_entry or "--pyargs-b64" not in overrides_entry:
        problems.append("serve-overrides.ts 应仍收 --pyargs-b64 与 --overrides-b64")

    # ui 测试目录里没有 skip/only/todo
    for path in sorted(UI_TEST.rglob("*.ts")):
        problems += [f"{path.name}：{p}" for p in _no_skip_marks(_read(path))]
    fail_if(problems, "基准测试文件锁定")


def test_static_readme():
    """D25/V08：README 写新路由、SSE、订阅上限、作业与已知限制（V08 的 need 列表），心跳与取消也写到。"""
    text = need_file("ts/packages/ui/README.md")
    problems = []
    for needle in README_NEEDLES:
        if needle not in text:
            problems.append(f"README 里看不到「{needle}」（V08 的口径）")
    for needle in ("心跳", "取消", "201"):
        if needle not in text:
            problems.append(f"README 里看不到「{needle}」")
    fail_if(problems, "README（D25/D31/V08）")


def test_static_localhttp_and_deps():
    """D26：localhttp 的地基原样——Sessions 有 create/valid/revokeAll、withSecurityHeaders 原样转交正文流、
    static.ts 仍导出 isReparsePoint、csrfCheck 的三查仍在（作业的 POST 走既有管线）。"""
    session = strip_ts_comments(need_file("ts/packages/ui/src/localhttp/session.ts"))
    headers = strip_ts_comments(need_file("ts/packages/ui/src/localhttp/headers.ts"))
    static = strip_ts_comments(need_file("ts/packages/ui/src/static.ts"))
    guards = strip_ts_comments(need_file("ts/packages/ui/src/localhttp/guards.ts"))
    problems = []
    for token in ("create", "valid", "revokeAll"):
        if token not in session:
            problems.append(f"localhttp/session.ts 里应有 {token}（A4/A11 的地基）")
    if "new Response(response.body" not in headers:
        problems.append("withSecurityHeaders 应仍用 new Response(response.body, …) 原样转交流（A2）")
    if "isReparsePoint" not in static:
        problems.append("static.ts 应仍导出 isReparsePoint（A5，watch.ts 复用它）")
    if "csrfCheck" not in guards or "x-themis-ui" not in guards.lower():
        problems.append("guards.ts 的 CSRF 三查应原样（作业 POST 走既有管线）")
    fail_if(problems, "localhttp 与依赖（D26）")


# ---------------------------------------------------------------------------
# 会话级流水线夹具
# ---------------------------------------------------------------------------

class GateError(Exception):
    """黑盒检查里的超时/协议错误。"""


def run_capture(argv, cwd, timeout):
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    start = time.monotonic()
    proc = subprocess.Popen(argv, cwd=str(cwd), env=_ts_env(), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, **kwargs)
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


class Resp:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self.body = body

    def get(self, name, default=None):
        low = name.lower()
        for key, value in self.headers:
            if key.lower() == low:
                return value
        return default


def _parse_head(head):
    lines = head.split(b"\r\n")
    parts = lines[0].decode("latin-1").split(" ", 2)
    if len(parts) < 2 or not parts[1].isdigit():
        raise GateError(f"响应行不像 HTTP：{lines[0][:120]!r}")
    headers = []
    for line in lines[1:]:
        if not line:
            continue
        if line[:1] in (b" ", b"\t") and headers:
            key, value = headers[-1]
            headers[-1] = (key, value + " " + line.strip().decode("latin-1"))
            continue
        key, _sep, value = line.partition(b":")
        headers.append((key.decode("latin-1").strip(), value.decode("latin-1").strip()))
    return int(parts[1]), headers


def _read_response(sock, timeout):
    sock.settimeout(timeout)
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
    head, _, rest = buf.partition(b"\r\n\r\n")
    if not head:
        raise GateError("没有收到响应头")
    status, headers = _parse_head(head)
    resp = Resp(status, headers, b"")
    length = resp.get("content-length")
    if length is not None and length.strip().isdigit():
        need = int(length.strip())
        body = rest
        while len(body) < need:
            chunk = sock.recv(65536)
            if not chunk:
                break
            body += chunk
        resp.body = body[:need]
        return resp
    body = rest
    sock.settimeout(6)
    while True:
        try:
            chunk = sock.recv(65536)
        except (socket.timeout, OSError):
            break
        if not chunk:
            break
        body += chunk
    resp.body = body
    return resp


def raw_request(port, method, target, headers=(), body=b"", timeout=30):
    """发一个请求并读完整响应（Connection: close，一条连接一个请求）。"""
    lines = [f"{method} {target} HTTP/1.1", f"Host: 127.0.0.1:{port}", "Connection: close", "Accept: */*"]
    lines += [f"{key}: {value}" for key, value in headers]
    if body:
        lines.append(f"Content-Length: {len(body)}")
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall(raw)
        return _read_response(sock, timeout)


def _pump(stream, sink):
    try:
        for line in iter(stream.readline, b""):
            sink.append(line)
    except Exception:
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass


class Service:
    """一个起着的 Bun 服务进程，stdout/stderr 由后台线程收行。"""

    def __init__(self, proc):
        self.proc = proc
        self.out_lines = []
        self.err_lines = []
        self.handshake_data = None
        self._threads = [threading.Thread(target=_pump, args=(proc.stdout, self.out_lines), daemon=True),
                         threading.Thread(target=_pump, args=(proc.stderr, self.err_lines), daemon=True)]
        for thread in self._threads:
            thread.start()

    def handshake(self, timeout=45):
        deadline = time.monotonic() + timeout
        while True:
            for raw in list(self.out_lines):
                text = raw.decode("utf-8", "replace").strip()
                if not text:
                    continue
                try:
                    data = json.loads(text)
                except ValueError:
                    continue
                if isinstance(data, dict) and "themis_ui" in data:
                    self.handshake_data = data
                    return data
            if self.proc.poll() is not None or time.monotonic() >= deadline:
                return None
            time.sleep(0.1)

    def stderr_tail(self, limit=1200):
        return b"".join(self.err_lines).decode("utf-8", "replace")[-limit:]

    def stop(self, timeout=15):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            return self.proc.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            _kill_tree(self.proc)
            try:
                return self.proc.wait(timeout=10), True
            except subprocess.TimeoutExpired:
                return None, True

    def kill(self):
        _kill_tree(self.proc)


class SseSub:
    """一条 SSE 订阅：发 GET 并把流收进缓冲区；状态行与头解析一次，正文由后台线程持续收。"""

    def __init__(self, port, cookie, last_event_id=None, timeout=15):
        self.status = None
        self.headers = []
        self.buf = bytearray()
        self.closed = False
        self._lock = threading.Lock()
        headers = [f"Host: 127.0.0.1:{port}", "Connection: close", "Accept: text/event-stream",
                   f"Cookie: {cookie}"]
        if last_event_id is not None:
            headers.append(f"Last-Event-ID: {last_event_id}")
        raw = (f"GET /api/v1/events HTTP/1.1\r\n" + "\r\n".join(headers) + "\r\n\r\n").encode("latin-1")
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
        self.sock.sendall(raw)
        head = b""
        self.sock.settimeout(timeout)
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(65536)
            if not chunk:
                break
            head += chunk
        if not head:
            self.sock.close()
            raise GateError("SSE 没有收到响应头")
        head_bytes, _, rest = head.partition(b"\r\n\r\n")
        self.status, self.headers = _parse_head(head_bytes)
        self.buf += rest
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        try:
            while True:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                with self._lock:
                    self.buf += chunk
        except OSError:
            pass
        finally:
            with self._lock:
                self.closed = True

    def get(self, name, default=None):
        low = name.lower()
        for key, value in self.headers:
            if key.lower() == low:
                return value
        return default

    def wait_for(self, needle, timeout, after=0):
        """等缓冲区里出现 needle（在 after 偏移之后）；订阅被关且仍没有就报错。"""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                data = bytes(self.buf)
                found = data.find(needle, after)
                closed = self.closed
            if found >= 0:
                return found
            if closed:
                raise GateError(f"订阅被服务关掉了，没等到 {needle!r}（收到的末尾：{data[-200:]!r}）")
            if time.monotonic() >= deadline:
                raise GateError(f"{timeout} 秒内没等到 {needle!r}（收到的末尾：{data[-200:]!r}）")
            time.sleep(0.05)

    def blocks(self):
        """把缓冲区按空行拆成 SSE 块（retry / 心跳 / 事件）。"""
        with self._lock:
            text = bytes(self.buf).decode("utf-8", "replace").replace("\r\n", "\n")
        out = []
        for block in text.split("\n\n"):
            lines = [line for line in block.split("\n") if line != ""]
            if not lines:
                continue
            item = {"raw": block}
            data_lines = []
            for line in lines:
                if line.startswith("id: "):
                    item["id"] = line[4:]
                elif line.startswith("event: "):
                    item["event"] = line[7:]
                elif line.startswith("data: "):
                    data_lines.append(line[6:])
                elif line.startswith("retry: "):
                    item["retry"] = line[7:]
                elif line.startswith(":"):
                    item["comment"] = line
            if data_lines:
                item["data"] = "\n".join(data_lines)
            out.append(item)
        return out

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def wait_closed(self, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self.closed:
                    return True
            time.sleep(0.05)
        return False


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
        self.bun = None
        self.services = []
        self.groups = {}

    def group(self, name):
        grp = Group(name)
        self.groups[name] = grp
        return grp

    def launch(self, repo, assets, overrides=None, idle_timeout=None):
        """照第 2 片测试入口的同一条路起服务：bun serve-overrides.ts --pyargs-b64 [--overrides-b64]。"""
        pyargs = {"command": ["ui"], "repo": str(repo), "desktop": True,
                  "assets": str(assets), "transcript": [], "idle_timeout": idle_timeout,
                  "python": sys.executable, "kernel": str(REPO_ROOT / "scripts" / "pi_dispatch.py")}
        argv = [str(self.bun), "--no-env-file", "--config=%s" % (TS / "bunfig.toml"),
                str(TS / "packages" / "ui" / "test" / "fixtures" / "serve-overrides.ts"),
                "--pyargs-b64", base64.b64encode(json.dumps(pyargs).encode("utf-8")).decode("ascii")]
        if overrides is not None:
            argv += ["--overrides-b64",
                     base64.b64encode(json.dumps(overrides).encode("utf-8")).decode("ascii")]
        proc = subprocess.Popen(argv, cwd=str(REPO_ROOT), env=_ts_env(), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        svc = Service(proc)
        self.services.append(svc)
        return svc


def _json(grp, resp, label):
    try:
        data = json.loads(resp.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        grp.check(False, f"{label}：正文不是 JSON 信封：{resp.body[:200]!r}")
        return None
    if not isinstance(data, dict):
        grp.check(False, f"{label}：正文不是 JSON 对象：{resp.body[:200]!r}")
        return None
    return data


def _sse_header_problems(sub):
    out = []
    ctype = sub.get("content-type") or ""
    if not ctype.lower().startswith("text/event-stream"):
        out.append(f"content-type 应是 text/event-stream; charset=utf-8，实际 {ctype!r}")
    if sub.get("cache-control") != "no-store":
        out.append(f"Cache-Control 应是 no-store，实际 {sub.get('cache-control')!r}")
    if sub.get("content-security-policy") != CSP:
        out.append("CSP 应逐字照合同 D4")
    if sub.get("x-content-type-options") != "nosniff":
        out.append("X-Content-Type-Options 应是 nosniff")
    if sub.get("referrer-policy") != "no-referrer":
        out.append("Referrer-Policy 应是 no-referrer")
    for key, _value in sub.headers:
        if key.lower().startswith("access-control"):
            out.append(f"出现了 {key} 头（不开 CORS）")
    return out


@pytest.fixture(scope="session")
def pipeline(tmp_path_factory):
    pipe = Pipeline()
    if not all((REPO_ROOT / rel).is_file() for rel in NEW_SRC_RELS):
        pipe.reason = ("候选里还没有四个新源文件（基线 d329e51，本片功能还没实现），未安装依赖、未起服务；"
                       "执行端实现之后，流水线才会运行 bun install 与黑盒服务检查")
        return pipe
    bun = find_bun()
    if bun is None:
        pipe.reason = "PATH 上找不到 Bun（bun.exe 或 npm 的 bun.cmd 垫片旁边的 bun.exe）"
        return pipe
    pipe.bun = bun
    pipe.ran = True
    pipe.tmp = tmp_path_factory.mktemp("t017-gate")
    deadline = time.monotonic() + PIPELINE_BUDGET
    try:
        if not _deps_ready():
            remaining = deadline - time.monotonic()
            if remaining <= 60:
                pipe.stopped_reason = "整体预算将尽，bun install 未运行"
            else:
                code, timed_out, out, seconds = run_capture([str(bun), "install", "--frozen-lockfile"], TS,
                                                            min(STEP_CAPS["bun install"], remaining))
                if code != 0:
                    pipe.stopped_reason = (f"bun install 退出码 {code}{'（超时被杀）' if timed_out else ''}，"
                                           f"用时 {seconds:.0f}s：{out[-800:]}")
        if not _deps_ready() and not pipe.stopped_reason:
            pipe.stopped_reason = "bun install 之后依赖仍不齐（node_modules/.themis-installed 不在）"
        if not pipe.stopped_reason:
            _run_service_checks(pipe, min(deadline - 30, time.monotonic() + STEP_CAPS["service checks"]))
    finally:
        for svc in pipe.services:
            try:
                svc.kill()
            except Exception:
                pass
    return pipe


def _session_of(port, bootstrap_url):
    path = urlsplit(bootstrap_url).path
    resp = raw_request(port, "GET", path)
    if resp.status != 302:
        raise GateError(f"引导地址应 302，实际 {resp.status}")
    set_cookie = resp.get("set-cookie") or ""
    if "themis_session=" not in set_cookie:
        raise GateError("引导应发会话 cookie")
    return "themis_session=" + set_cookie.split("themis_session=", 1)[1].split(";", 1)[0]


def _csrf(port, cookie):
    return [("Cookie", cookie), ("Origin", f"http://127.0.0.1:{port}"), ("X-Themis-UI", "1"),
            ("Content-Type", "application/json")]


def _post_json(port, target, cookie, payload):
    body = json.dumps(payload).encode("utf-8") if not isinstance(payload, (bytes, bytearray)) else payload
    return raw_request(port, "POST", target, headers=_csrf(port, cookie), body=body)


def _run_service_checks(pipe, soft_deadline):
    tmp = pipe.tmp

    def group(name):
        return pipe.group(name)

    def phase(name, fn):
        grp = group(name)
        if time.monotonic() > soft_deadline:
            grp.problems.append(f"服务检查的预算将尽，{name} 未运行")
            return grp
        try:
            fn(grp)
        except Exception as exc:
            grp.problems.append(f"{name} 检查抛出异常：{type(exc).__name__}: {exc}")
        return grp

    # 场地：主服务的仓库与资源
    svc_dir = tmp / "main"
    assets = svc_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "index.html").write_text("<!doctype html><title>T017</title>\n", encoding="utf-8")
    repo = svc_dir / "repo"
    repo.mkdir(exist_ok=True)

    # 主服务：心跳 300ms、全局上限 2、每会话上限 4（一个会话就够了：非ces一次引导只发一个 nonce）
    main = pipe.launch(repo, assets, overrides={"heartbeatMs": 300, "maxSubscriptions": 2,
                                                "maxSubscriptionsPerSession": 4})
    hs = main.handshake()
    if hs is None:
        why = f"主服务没有在 45 秒内写出握手行（退出码 {main.proc.poll()}）：{main.stderr_tail()}"
        for name in ("auth", "sse", "limits", "disconnect", "jobs", "session-limit", "idle"):
            group(name).check(False, why)
        return
    state = {"port": urlsplit(hs["origin"]).port, "control": hs["control"], "bootstrap": hs["bootstrap"]}

    # ------------------------------------------------------------------ auth
    def check_auth(grp):
        port = state["port"]
        for method, target, label in (
            ("GET", "/api/v1/events", "api.events"),
            ("POST", "/api/v1/jobs", "api.jobs.create"),
            ("GET", "/api/v1/jobs/" + "A" * 43, "api.jobs.get"),
            ("POST", "/api/v1/jobs/" + "A" * 43 + "/cancel", "api.jobs.cancel"),
        ):
            headers = [("Content-Type", "application/json")] if method == "POST" else []
            resp = raw_request(port, method, target, headers=headers, body=b"{}" if method == "POST" else b"")
            if grp.check(resp.status == 401, f"不带 cookie 访问 {label} 应 401，实际 {resp.status}"):
                envelope = _json(grp, resp, label)
                if envelope is not None:
                    grp.check(envelope.get("ok") is False and envelope.get("messages") == ["ERROR: 未认证"],
                              f"{label} 的 401 应是「ERROR: 未认证」，实际 {envelope.get('messages')!r}")
        cookie = _session_of(port, state["bootstrap"])
        state["cookie"] = cookie
        # POST 的 CSRF 与正文走既有管线：缺 CSRF 403、非 JSON 媒体类型 415、正文不是对象 400
        resp = raw_request(port, "POST", "/api/v1/jobs", headers=[("Cookie", cookie)], body=b"{}")
        grp.check(resp.status == 403, f"POST /api/v1/jobs 缺 CSRF 应 403，实际 {resp.status}")
        resp = raw_request(port, "POST", "/api/v1/jobs",
                           headers=[("Cookie", cookie), ("Origin", f"http://127.0.0.1:{port}"),
                                    ("X-Themis-UI", "1"), ("Content-Type", "text/plain")], body=b"{}")
        grp.check(resp.status == 415, f"POST /api/v1/jobs 非 JSON 媒体类型应 415，实际 {resp.status}")
        resp = _post_json(port, "/api/v1/jobs", cookie, [1, 2])
        if grp.check(resp.status == 400, f"正文是数组应 400，实际 {resp.status}"):
            envelope = _json(grp, resp, "jobs-array")
            if envelope is not None:
                grp.check(envelope.get("ok") is False and envelope.get("exit_code") is None,
                          "400 应是服务自己的错误信封（ok=false、exit_code=null）")
        # /api/v1/nope 有会话仍 404（既有行为不动）
        resp = raw_request(port, "GET", "/api/v1/nope", headers=[("Cookie", cookie)])
        grp.check(resp.status == 404, f"/api/ 下不存在的路径有会话应 404，实际 {resp.status}")

    # ------------------------------------------------------------------- sse
    def check_sse(grp):
        port = state["port"]
        cookie = state["cookie"]
        started = time.monotonic()
        sub = SseSub(port, cookie)
        try:
            if not grp.check(sub.status == 200, f"GET /api/v1/events 应 200，实际 {sub.status}"):
                return
            grp.check(not _sse_header_problems(sub), "SSE 响应头：" + "；".join(_sse_header_problems(sub)))
            # 流一打开先写 retry: 3000 与一个空行；第一条事件是 snapshot 且带序号 1
            sub.wait_for(b"retry: 3000", SSE_READ_TIMEOUT)
            blocks = sub.blocks()
            retry_blocks = [b for b in blocks if "retry" in b]
            if grp.check(retry_blocks, "流的第一块应是 retry: 3000"):
                grp.check(retry_blocks[0]["retry"] == "3000",
                          f"retry 应是 3000，实际 {retry_blocks[0].get('retry')!r}")
            sub.wait_for(b"event: snapshot", SSE_READ_TIMEOUT)
            events = [b for b in sub.blocks() if "event" in b]
            first = events[0] if events else None
            if grp.check(first is not None, "订阅后应先收到 snapshot"):
                grp.check(first.get("event") == "snapshot",
                          f"第一条事件应是 snapshot，实际 {first.get('event')!r}")
                grp.check(first.get("id") == "1", f"snapshot 的序号应从 1 起，实际 {first.get('id')!r}")
                data = first.get("data")
                if grp.check(data is not None, "snapshot 应带 data 行"):
                    envelope = json.loads(data)
                    grp.check(list(envelope.keys()) == ENVELOPE_KEYS,
                              f"data 应是七字段信封，实际 {list(envelope.keys())}")
                    grp.check(envelope.get("command") == ["status", "--json"],
                              f"snapshot 的 command 应是 status --json，实际 {envelope.get('command')!r}")
            # 心跳：一行 : hb（heartbeatMs 覆盖成 300ms，3 秒内必到）
            sub.wait_for(b": hb", 3)
            # 「名单变化触发 update」的黑盒验证见 ASSUMPTIONS（非 git 目录上 status 输出恒定，
            # 正确实现上也不会有 update）；这里改钉它的逆命题：内容不变不推也不加号，
            # 并验证连接活过 12 秒：Bun 缺省的连接空闲超时掐不断（server.timeout(req, 0) 只放宽这一条）
            while time.monotonic() - started < 12:
                with sub._lock:
                    length = len(sub.buf)
                sub.wait_for(b": hb", 5, after=length)
            # 带 Last-Event-ID 的第二条订阅（sub 还开着，全局上限 2 恰好用满）：第一条仍是 snapshot
            # （重连不续传）；内容没变过，序号不应加号——第二个订阅者的 snapshot 序号仍是 1
            sub2 = SseSub(port, cookie, last_event_id="999")
            try:
                if grp.check(sub2.status == 200, f"带 Last-Event-ID 的订阅应 200，实际 {sub2.status}"):
                    sub2.wait_for(b"event: snapshot", SSE_READ_TIMEOUT)
                    events2 = [b for b in sub2.blocks() if "event" in b]
                    if grp.check(events2, "重连后应收到 snapshot"):
                        grp.check(events2[0].get("event") == "snapshot",
                                  f"重连的第一条应是 snapshot（不续传），实际 {events2[0].get('event')!r}")
                        grp.check(events2[0].get("id") == "1",
                                  f"内容没变过序号不应加号（snapshot 序号应仍是 1），实际 {events2[0].get('id')!r}")
                        grp.check(events2[0].get("data") is not None, "snapshot 应带 data 行")
            finally:
                sub2.close()
        finally:
            sub.close()

    # --------------------------------------------------------------- limits
    def check_limits(grp):
        port = state["port"]
        cookie = state["cookie"]
        # 同一会话两条（每会话上限 4 放行），全局上限 2：第 3 条 503
        sub1 = SseSub(port, cookie)
        sub2 = SseSub(port, cookie)
        try:
            grp.check(sub1.status == 200 and sub2.status == 200,
                      f"前两条订阅应成功（{sub1.status}/{sub2.status}）")
            sub1.wait_for(b"event: snapshot", SSE_READ_TIMEOUT)
            third = raw_request(port, "GET", "/api/v1/events", headers=[("Cookie", cookie)])
            if grp.check(third.status == 503, f"全局上限（2）满了第 3 条应 503，实际 {third.status}"):
                grp.check((third.get("retry-after") or "") == "2",
                          f"503 应带 Retry-After: 2，实际 {third.get('retry-after')!r}")
                envelope = _json(grp, third, "sse-limit")
                if envelope is not None:
                    grp.check(envelope.get("ok") is False and envelope.get("exit_code") is None
                              and envelope.get("data") is None and envelope.get("output") == []
                              and envelope.get("command") == [],
                              "503 应是服务自己的错误信封（ok=false、exit_code=null、data=null、空数组）")
                    grp.check(envelope.get("messages") == [SSE_LIMIT_GLOBAL_MSG],
                              f"全局超限的正文应是一行「{SSE_LIMIT_GLOBAL_MSG}」，实际 {envelope.get('messages')!r}")
            # 已有的两条不被挤掉：照旧收到心跳
            with sub1._lock:
                mark1 = len(sub1.buf)
            sub1.wait_for(b": hb", 3, after=mark1)
            with sub2._lock:
                mark2 = len(sub2.buf)
            sub2.wait_for(b": hb", 3, after=mark2)
            # 关掉一条，名额立刻归还
            sub1.close()
            time.sleep(1.0)
            sub3 = SseSub(port, cookie)
            try:
                grp.check(sub3.status == 200, f"关掉一条之后名额应还回来（再订阅 200），实际 {sub3.status}")
            finally:
                sub3.close()
        finally:
            sub2.close()

    # ----------------------------------------------------------- disconnect
    def check_disconnect(grp):
        port = state["port"]
        cookie = state["cookie"]
        # 心跳写失败立刻清理：两条占满全局，客户端直接断开一条（不发 abort），
        # 服务下一次写心跳失败 → 立刻清理 → 名额归还 → 第 3 条订阅成功
        w1 = SseSub(port, cookie)
        w2 = SseSub(port, cookie)
        try:
            grp.check(w1.status == 200 and w2.status == 200, "占满全局上限的两条订阅应成功")
            w1.wait_for(b"event: snapshot", SSE_READ_TIMEOUT)
            w2.wait_for(b"event: snapshot", SSE_READ_TIMEOUT)
            w1.close()  # 直接断开：服务写心跳会失败
            time.sleep(1.5)
            w3 = SseSub(port, cookie)
            try:
                grp.check(w3.status == 200,
                          "心跳写失败应立刻清理（清定时器、关流、计数减一），名额归还后第 3 条应 200，"
                          f"实际 {w3.status}")
            finally:
                w3.close()
        finally:
            w2.close()
        # 会话作废（control.bootstrap 换发引导地址 → revokeAll）：该会话名下的订阅在一个心跳间隔内被关掉
        r1 = SseSub(port, cookie)
        try:
            grp.check(r1.status == 200, "会话作废之前的订阅应成功")
            r1.wait_for(b"event: snapshot", SSE_READ_TIMEOUT)
            resp = raw_request(port, "POST", "/control/bootstrap",
                               headers=[("x-themis-control", str(state["control"]))], body=b"")
            grp.check(resp.status == 200, f"POST /control/bootstrap 应 200，实际 {resp.status}")
            grp.check(r1.wait_closed(3), "revokeAll 之后订阅应在一个心跳间隔内被服务关掉（300ms 心跳）")
        finally:
            r1.close()

    # ------------------------------------------------------------------ jobs
    def check_jobs(grp):
        port = state["port"]
        cookie = state["cookie"]
        bad_bodies = (
            ("正文不是对象（字符串）", "x"),
            ("没有 kind", {}),
            ("kind 不在六个之内", {"kind": "nope"}),
            ("未知键", {"kind": "doctor", "extra": 1}),
            ("少必填键", {"kind": "doctor-record"}),
            ("record 不合 PLAN_KEY_RE", {"kind": "doctor-record", "record": "BAD.v1"}),
            ("runtime 不合 TASK_ID_RE", {"kind": "runtime-probe", "runtime": "Bad_Runtime"}),
            ("max 是布尔", {"kind": "search", "pattern": "x", "max": True}),
            ("max 超出 1–1000", {"kind": "search", "pattern": "x", "max": 0}),
            ("pattern 含控制字符", {"kind": "search", "pattern": "a\u0001b"}),
            ("pattern 超过 512 个码点", {"kind": "search", "pattern": "x" * 513}),
        )
        for label, payload in bad_bodies:
            resp = _post_json(port, "/api/v1/jobs", cookie, payload)
            if grp.check(resp.status == 400, f"{label} 应 400，实际 {resp.status}：{resp.body[:120]!r}"):
                envelope = _json(grp, resp, label)
                if envelope is not None:
                    grp.check(envelope.get("ok") is False and envelope.get("exit_code") is None,
                              f"{label}：400 应是服务自己的错误信封（ok=false、exit_code=null）")
                    grp.check(isinstance(envelope.get("messages"), list) and len(envelope["messages"]) == 1
                              and isinstance(envelope["messages"][0], str)
                              and envelope["messages"][0].startswith("ERROR: "),
                              f"{label}：messages 应是一行 ERROR: …")
        # 404：格式不对与不在表里回同一个 404「没有这个作业」
        bad_id = raw_request(port, "GET", "/api/v1/jobs/abc", headers=[("Cookie", cookie)])
        unknown_id = raw_request(port, "GET", "/api/v1/jobs/" + "B" * 43, headers=[("Cookie", cookie)])
        if grp.check(bad_id.status == 404 and unknown_id.status == 404,
                     f"作业号格式不对与不在表里都应 404，实际 {bad_id.status}/{unknown_id.status}"):
            grp.check(bad_id.body == unknown_id.body, "两种 404 的响应应相同（不泄露作业号在不在）")
            envelope = _json(grp, unknown_id, "jobs-404")
            if envelope is not None:
                grp.check(f"{JOB_404_MSG}" in json.dumps(envelope.get("messages"), ensure_ascii=False),
                          f"404 应是「{JOB_404_MSG}」，实际 {envelope.get('messages')!r}")
        cancel_unknown = _post_json(port, "/api/v1/jobs/" + "B" * 43 + "/cancel", cookie, {})
        grp.check(cancel_unknown.status == 404, f"取消不存在的作业应 404，实际 {cancel_unknown.status}")
        # 创建一个 search 作业（真内核，非 git 仓库上很快到终态）；D31：创建成功回 201，
        # 正文就是顶层八键作业对象（不套信封、不套 data），创建当下 state=queued、四个键值为 null
        created = _post_json(port, "/api/v1/jobs", cookie, {"kind": "search", "pattern": "zzz"})
        if not grp.check(created.status == 201,
                         f"POST /api/v1/jobs 成功应 201（D31 定死，不许两认），实际 {created.status}："
                         f"{created.body[:200]!r}"):
            return
        job = _json(grp, created, "jobs-create")
        if not grp.check(isinstance(job, dict),
                         f"创建的正文应是顶层 JSON 对象（不套信封），实际 {created.body[:200]!r}"):
            return
        grp.check(set(job.keys()) == JOB_KEYS,
                  f"创建的正文应恰好是八个键 {sorted(JOB_KEYS)}，实际 {sorted(job.keys())}")
        grp.check("data" not in job and "ok" not in job, "创建的正文不套七字段信封、不套 data（D31）")
        if not grp.check(isinstance(job.get("id"), str) and JOB_ID_RE.match(job.get("id") or "") is not None
                         and job["id"] != "B" * 43,
                         f"作业号应是 43 位随机 base64url，实际 {job.get('id')!r}"):
            return
        job_id = job["id"]
        grp.check(job.get("kind") == "search", f"kind 应是刚给的 search，实际 {job.get('kind')!r}")
        grp.check(job.get("state") == "queued",
                  f"创建成功的当下 state 应是 queued，实际 {job.get('state')!r}")
        for field in ("reason", "started_ms", "finished_ms", "envelope"):
            grp.check(field in job and job.get(field) is None,
                      f"创建成功的当下 {field} 应是 null（键在、值为 null），实际 {job.get(field)!r}")
        terminal = {"succeeded", "failed", "cancelled", "timed_out"}
        state_seen = None
        envelope = None
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            resp = raw_request(port, "GET", f"/api/v1/jobs/{job_id}", headers=[("Cookie", cookie)])
            if not grp.check(resp.status == 200, f"GET 作业应 200，实际 {resp.status}"):
                return
            job = _json(grp, resp, "jobs-get")
            if not grp.check(isinstance(job, dict),
                             f"GET 的正文应是顶层 JSON 对象（不套信封、不套 data，D31），实际 {resp.body[:200]!r}"):
                return
            if isinstance(job.get("state"), str):
                state_seen = job["state"]
                if state_seen in terminal:
                    envelope = job.get("envelope")
                    break
            time.sleep(0.4)
        if grp.check(state_seen in terminal, f"作业应在 45 秒内到四种终态之一，实际 {state_seen!r}"):
            # GET 的正文形状在终态那一次逐键断言（避免轮询期间重复报同一问题）
            grp.check(set(job.keys()) == JOB_KEYS,
                      f"GET 的正文应恰好是八个键 {sorted(JOB_KEYS)}，实际 {sorted(job.keys())}")
            grp.check("data" not in job, "GET 的正文不套 data（D31）")
            if envelope is None:
                # 只有 cancelled 的 envelope 才可以是 null；这里没取消过，到不了别的终态
                grp.check(state_seen == "cancelled",
                          f"只有 cancelled 的 envelope 才可以是 null（state={state_seen!r}）")
            else:
                grp.check(isinstance(envelope, dict) and "search" in json.dumps(envelope.get("command", [])),
                          f"终态的 envelope 应带脱敏后的七字段信封（command 含 search），实际 {envelope!r}")
        # 取消已结束的作业回 409「作业已经结束」
        cancelled = _post_json(port, f"/api/v1/jobs/{job_id}/cancel", cookie, {})
        if grp.check(cancelled.status == 409, f"取消已结束的作业应 409，实际 {cancelled.status}"):
            envelope = _json(grp, cancelled, "jobs-409")
            if envelope is not None:
                grp.check(f"{JOB_409_MSG}" in json.dumps(envelope.get("messages"), ensure_ascii=False),
                          f"409 应是「{JOB_409_MSG}」，实际 {envelope.get('messages')!r}")

    try:
        phase("auth", check_auth)
        phase("sse", check_sse)
        phase("limits", check_limits)
        phase("jobs", check_jobs)
        # disconnect 放最后：它调 control.bootstrap 换发引导地址，旧会话当场作废
        phase("disconnect", check_disconnect)
    finally:
        main.stop(timeout=15)

    # ------------------------------------------------- 会话上限服务（perSession=1）
    def check_session_limit(grp):
        sess_dir = tmp / "sess"
        assets2 = sess_dir / "assets"
        assets2.mkdir(parents=True, exist_ok=True)
        (assets2 / "index.html").write_text("<!doctype html><title>T017b</title>\n", encoding="utf-8")
        repo2 = sess_dir / "repo"
        repo2.mkdir(exist_ok=True)
        svc = pipe.launch(repo2, assets2, overrides={"heartbeatMs": 300, "maxSubscriptions": 8,
                                                     "maxSubscriptionsPerSession": 1})
        try:
            hs2 = svc.handshake()
            if not grp.check(hs2 is not None, f"会话上限服务没写出握手行：{svc.stderr_tail()}"):
                return
            port = urlsplit(hs2["origin"]).port
            cookie = _session_of(port, hs2["bootstrap"])
            first = SseSub(port, cookie)
            try:
                grp.check(first.status == 200, f"该会话的第 1 条订阅应成功，实际 {first.status}")
                first.wait_for(b"event: snapshot", SSE_READ_TIMEOUT)
                second = raw_request(port, "GET", "/api/v1/events", headers=[("Cookie", cookie)])
                if grp.check(second.status == 503, f"同一会话的第 2 条应 503，实际 {second.status}"):
                    envelope = _json(grp, second, "sse-session-limit")
                    if envelope is not None:
                        grp.check(envelope.get("messages") == [SSE_LIMIT_SESSION_MSG],
                                  f"会话级超限应是一行「{SSE_LIMIT_SESSION_MSG}」，实际 {envelope.get('messages')!r}")
                        grp.check((second.get("retry-after") or "") == "2", "503 应带 Retry-After: 2")
            finally:
                first.close()
            # 换发引导地址：旧会话作废（上面那条订阅被关），新会话的第 1 条成功
            resp = raw_request(port, "POST", "/control/bootstrap",
                               headers=[("x-themis-control", str(hs2["control"]))], body=b"")
            if grp.check(resp.status == 200, f"POST /control/bootstrap 应 200，实际 {resp.status}"):
                payload = _json(grp, resp, "control")
                new_path = urlsplit((payload or {}).get("data", {}).get("bootstrap", "") if payload else "").path
                if grp.check(bool(new_path), "换发的引导地址应在返回里"):
                    cookie2 = _session_of(port, (payload or {})["data"]["bootstrap"])
                    fresh = SseSub(port, cookie2)
                    try:
                        grp.check(fresh.status == 200,
                                  f"另一个会话（换发后的新会话）的第 1 条订阅应成功，实际 {fresh.status}")
                    finally:
                        fresh.close()
        finally:
            svc.stop(timeout=15)

    phase("session-limit", check_session_limit)

    # ------------------------------------------------------ 空闲服务（U21/D30）
    def check_idle(grp):
        idle_dir = tmp / "idle"
        assets3 = idle_dir / "assets"
        assets3.mkdir(parents=True, exist_ok=True)
        (assets3 / "index.html").write_text("<!doctype html><title>T017c</title>\n", encoding="utf-8")
        repo3 = idle_dir / "repo"
        repo3.mkdir(exist_ok=True)
        svc = pipe.launch(repo3, assets3, overrides={"heartbeatMs": 300}, idle_timeout=3)
        try:
            hs3 = svc.handshake()
            if not grp.check(hs3 is not None, f"空闲服务没写出握手行：{svc.stderr_tail()}"):
                return
            port = urlsplit(hs3["origin"]).port
            cookie = _session_of(port, hs3["bootstrap"])
            sub = SseSub(port, cookie)
            try:
                grp.check(sub.status == 200, f"订阅应成功，实际 {sub.status}")
                sub.wait_for(b"event: snapshot", SSE_READ_TIMEOUT)
                # 空闲时限 3 秒：订阅开着时空闲时限到了也不退出（订阅算活动）
                for _ in range(12):
                    time.sleep(0.5)
                    with sub._lock:
                        mark = len(sub.buf)
                    sub.wait_for(b": hb", 4, after=mark)
                    if svc.proc.poll() is not None:
                        grp.check(False, "有订阅开着时服务不应因空闲退出（订阅算活动）")
                        break
                    if time.monotonic() - started_idle > 6.5:
                        break
            finally:
                sub.close()
            # 订阅全部断开之后，空闲时限到了服务才退出（先 hub.close() 再退出）
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline and svc.proc.poll() is None:
                time.sleep(0.3)
            grp.check(svc.proc.poll() is not None, "订阅断开之后，空闲时限到了服务应自己退出")
        finally:
            svc.kill()

    started_idle = time.monotonic()
    phase("idle", check_idle)


# ---------------------------------------------------------------------------
# 流水线断言（pipeline 会话级夹具；全量 pytest 默认跳过，点名运行本文件才跑）
# ---------------------------------------------------------------------------

def _pipeline_group(pipeline, name):
    assert pipeline.ran, pipeline.reason or "流水线没有运行"
    grp = pipeline.groups.get(name)
    if grp is None:
        assert not pipeline.stopped_reason, f"{name} 未运行：{pipeline.stopped_reason}"
    assert grp is not None, f"{name} 未运行"
    fail_if(grp.problems, f"{name}（流水线黑盒检查）")


def test_pipeline_ran(pipeline):
    """流水线真的跑了（四个新源文件在位、Bun 找得到、依赖装好、服务起了）。"""
    assert pipeline.ran, pipeline.reason
    assert not pipeline.stopped_reason, f"流水线中途停了：{pipeline.stopped_reason}"


def test_pipeline_auth(pipeline):
    """D01/D12（黑盒）：events 与三条作业路由不带 cookie 一律 401；POST 走既有 CSRF/正文管线。"""
    _pipeline_group(pipeline, "auth")


def test_pipeline_sse(pipeline):
    """D01/D02/D04/D10（黑盒）：SSE 的头、retry: 3000、snapshot 序号 1、data 是 status 的七字段信封、
    心跳、名单上的变化推 update、连接活过 12 秒（Bun 缺省空闲超时掐不断）、Last-Event-ID 重连仍是 snapshot。"""
    _pipeline_group(pipeline, "sse")


def test_pipeline_limits(pipeline):
    """D27（黑盒）：全局上限第 3 条 503 + Retry-After: 2 + 错误信封原文、已有订阅不被挤掉、名额归还。"""
    _pipeline_group(pipeline, "limits")


def test_pipeline_disconnect(pipeline):
    """D28/D29（黑盒）：心跳写失败立刻清理（名额归还）；control.bootstrap 换发后旧会话的订阅被关。"""
    _pipeline_group(pipeline, "disconnect")


def test_pipeline_jobs(pipeline):
    """D13/D16/D17/D18（黑盒）：每类参数不合格 400、404 同文、创建作业到终态、取消已结束 409。"""
    _pipeline_group(pipeline, "jobs")


def test_pipeline_session_limit(pipeline):
    """D27/D28（黑盒）：每会话上限 1 时同会话第 2 条 503（会话级原文）；换发引导地址后新会话可订阅。"""
    _pipeline_group(pipeline, "session-limit")


def test_pipeline_idle(pipeline):
    """D30/U21（黑盒）：订阅开着时空闲时限到了服务不退出；订阅断开后空闲时限到了才退出。"""
    _pipeline_group(pipeline, "idle")
