"""T015 战前门禁：桌面端本机服务第 1 片（服务骨架、安全基线、握手，D1-B）的黑盒基准测试
（合同 t015-desktop-ui-core.v1，plan_version 1，基线 2a5c7213da）。

被测对象是 ``ts/packages/ui``：一个只绑 127.0.0.1 的 Bun 本机服务——stdout 只写一行握手 JSON，一次性引导地址
与会话 cookie、控制接口（恒定时间比较加失败限速）、Host/Origin/CSRF 校验、安全响应头、64 KiB 请求体上限、
静态资源的目录边界（路径只解码一次）、每仓库一个的锁目录，以及空闲超时与 stdin EOF 的关停。

基线（2a5c7213da）上 ``src/localhttp/``、``server.ts`` 等还不存在（``runUi`` 只写「本机服务还没有实现」），
所以本文件的失败落在「文件不存在」或「起不了服务」上，不是导入、收集或语法错误：模块级只导入标准库，
所有仓库文件的读取都发生在用例函数里，流水线（真的起 Bun 服务、发 HTTP 请求）放在 ``pipeline`` 会话级夹具里。

结构（编号对应合同 DoD 的 D01–D17）：

- 静态断言（不用流水线，全量 pytest 也跑）：合同点名的源文件与 README 在位、main.ts 接线（D14/D17）、
  信封七字段与四条路由（D02/D08）、静态路径的 reason 串与 Content-Type 白名单（D09）、localhttp 常量与
  逐字串（D03/D07/D08/D11/D12，过渡断言）、server/lifecycle/lockdir 的常量与提示原文（D01/D13/D15）、
  README 的已知限制（D13）、src 的 import 图接线（D17）、args.test.ts 三条既有用例未改未删（D14）、
  .gitignore 的 .agent/.ui.lock/（D17）。改动范围只按「流水线前后 git status 差集」证
  （test_pipeline_scope，对照 t002/t012 的惯例）：集成时别片的合法改动会让全树绝对范围断言必红，
  执行期的范围由合同 V07 管。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：先 ``bun install``
  （V01），再照启动器的同一条路（``bun --no-env-file --config=ts/bunfig.toml ts/packages/cli/src/main.ts
  --pyargs-b64 …``）起真的服务，用原始套接字发 HTTP 请求逐条钉 D01–D16 的行为（握手、Host、会话与引导地址、
  CSRF、方法白名单、静态资源与目录边界、请求体上限、安全头矩阵、控制接口与限速、两种拒绝的同一个响应、
  日志里没有令牌、用法错误与已有服务、生命周期与锁、经 pi_dispatch.py 的端到端），最后跑 V02（契约与源码
  卫生）与 V05（tsc）。候选里还没有 ``src/localhttp``（基线）时不装依赖、不起服务，用到夹具的用例以断言失败
  写明原因。

合同没有写死、门禁端按最合理读法定下的地方（交付信「需协调人决定」里逐条列出，终审可改）：见 ``ASSUMPTIONS``。

过渡断言：``test_transitional_localhttp_constants`` 一条（localhttp 的常量与逐字串），docstring 第一行写明
哪项后续工作会推翻它（迁移第 ③d 步把 ``src/localhttp`` 搬进 ``@themis/base/localhttp``）。
"""

import base64
import json
import os
import re
import select
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TS = REPO_ROOT / "ts"
UI_SRC = TS / "packages" / "ui" / "src"
UI_TEST = TS / "packages" / "ui" / "test"
README_REL = "ts/packages/ui/README.md"
README = REPO_ROOT / README_REL
GATE_FILE_REL = "tests/test_gate_t015_baseline.py"
ARGS_TEST_REL = "ts/packages/ui/test/args.test.ts"
MAIN_REL = "ts/packages/ui/src/main.ts"
SERVER_REL = "ts/packages/ui/src/server.ts"
LIFECYCLE_REL = "ts/packages/ui/src/lifecycle.ts"
LOCKDIR_REL = "ts/packages/ui/src/lockdir.ts"
STATIC_REL = "ts/packages/ui/src/static.ts"
ENVELOPE_REL = "ts/packages/ui/src/envelope.ts"
ROUTES_REL = "ts/packages/ui/src/routes.ts"
# 不随 ③d（localhttp 搬进 @themis/base）搬家的源文件：main/envelope/routes/app/static/lockdir/lifecycle/server
DURABLE_SRC_RELS = (MAIN_REL, ENVELOPE_REL, ROUTES_REL, "ts/packages/ui/src/app.ts", STATIC_REL,
                    LOCKDIR_REL, LIFECYCLE_REL, SERVER_REL)

# 合同 Behavior contract：CSP 逐字照 D4
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
# 合同 Behavior contract：Set-Cookie 逐字（32 字节令牌 base64url 后 43 个字符）
COOKIE_RE = r"themis_session=[A-Za-z0-9_-]{43}; HttpOnly; SameSite=Strict; Path=/"
# 合同 Behavior contract：信封七个字段，次序照 §5.3
ENVELOPE_KEYS = ["ok", "exit_code", "data", "output", "messages", "command", "elapsed_ms"]
# 合同 Behavior contract：静态路径每一类的 reason（D09 逐类）
REASONS = ("dot-segment", "encoded-dot-or-separator", "backslash", "drive-letter", "empty-segment", "colon",
           "trailing-dot-or-space", "bad-encoding", "control-char", "reparse-point", "outside-root",
           "directory", "type-not-allowed", "not-found")
# 合同 Behavior contract：Content-Type 白名单的值
CONTENT_TYPES = ("text/html; charset=utf-8", "text/javascript; charset=utf-8", "text/css; charset=utf-8",
                 "application/json; charset=utf-8", "text/plain; charset=utf-8", "font/woff2", "font/woff",
                 "image/svg+xml", "image/png", "image/x-icon")

ASSUMPTIONS = (
    "302 的 Location：合同写「Location: /」，门禁按路径分量校验（等于 /），同时接受实现写成绝对地址 http://127.0.0.1:<port>/",
    "控制接口的请求照合同两种读法都成立的方式发（Origin 同源 + X-Themis-UI: 1 + Content-Type: application/json + 空 JSON 正文）：合同管线第 4 步对所有 POST 跑 csrfCheck，而路由表说 control.bootstrap 不读正文、只过 controlOriginAllowed；这两种读法下这些头都无害，门禁不断言「不带 Origin 的控制请求会怎样」",
    "静态路径上的错误响应（400/404）只断言三个安全头，不断言 Cache-Control：合同「所有错误带 no-store、静态资源带 no-cache」没说到静态路径上的错误响应该算哪一边",
    "HTTP 负面路径只覆盖合同 D10 点名的五条（%2f、%2e、%5c、%00、双编码）加「..」与原始反斜杠两条只断言「拿不到 assets 之外的文件」；盘符、UNC、ADS、末尾点/空格、junction 这些 Bun 会规范化或到不了 fetch 的类别由静态断言（reason 串与检查项）与执行端的 V03 覆盖",
    "429 的 Retry-After 只断言「存在且是正整数」；锁定时长翻倍用行为探针证明（第二次锁定期内正确令牌仍 429），不断言具体秒数",
    "锁的 busy/接管用例用临时仓库目录（pytest 的 tmp 目录），不写进工作目录；.agent/.ui.lock 的清理由用例自己负责",
    "经启动器的一路用 git init 出来的临时仓库（Repo.discover 拒绝 worktree），锁目录落在临时仓库里",
    "流水线预算 540 秒：bun install → 服务黑盒检查 → V02 → tsc；任一步在预算用完时没跑，对应用例以断言失败写明原因（本文件不许用 skip）",
    "空闲退出「有请求就推迟」用 --idle-timeout 3、每 0.6 秒一个 GET /，4.5 秒后仍活着来证明；退出阈值一律放宽到 10 秒以上",
    "D14 的「退出 2 提示原文」按 checkArgs 的三条提示逐字断言（合同说 UiArgs、checkArgs、EXIT_* 不改）",
    "握手行的 themis_ui 字段合同没规定取值，只断言字段存在与五个字段的次序",
    "黑盒请求一律带 Connection: close，每条连接一个请求；响应头比较除 Date 与 Connection 外逐字节相同",
)

# 流水线整体预算：合同 G01 的超时是 600 秒，留出静态用例与 pytest 自身的开销。
PIPELINE_BUDGET = 540
STEP_CAPS = {"bun install": 240, "service checks": 230, "vitest-contracts": 140, "tsc": 180}

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_ENV_DROP = ("BUN_OPTIONS", "NODE_OPTIONS", "NODE_PATH", "BUN_INSPECT", "BUN_INSPECT_CONNECT_TO", "BUN_INSPECT_NOTIFY")


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

class GateError(Exception):
    """黑盒检查里的超时/协议错误，由所在的检查组收进失败清单。"""


def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def git_status_set():
    """git status --porcelain=v1 -z 的条目集合（NUL 分隔，带空格/引号的路径不用去引号）。"""
    proc = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
                          cwd=str(REPO_ROOT), capture_output=True, timeout=120)
    assert proc.returncode == 0, f"git status 失败：{proc.stderr.decode('utf-8', 'replace')[:300]}"
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


def status_path(entry):
    """从一条 git status 条目里取出路径（改名条取后面的那一半）。

    ``-z`` 输出的改名是两条：``XY <新路径>\0<原路径>\0``，第二条没有状态前缀，所以先按 porcelain 的两字符
    状态码加一个空格去前缀，去不掉就整条当路径。"""
    m = re.match(r"[ MADRCU?!]{2} ", entry)
    path = entry[m.end():] if m else entry
    if " -> " in path:
        path = path.split(" -> ")[-1]
    return path.strip().strip('"')


# 流水线差集断言里允许出现的路径前缀：合同 allowed 的 ts/packages/ui/（src 与 test 与 README 都在它下面），
# 外加 ts/mutations/——合同把它列进 forbidden 是禁**实现**去动它，而战后是内核把变异记录写进那里，
# 那条写入不是实现越界；实现自己的改动范围由合同 V07 判，不在这个差集窗口里。
# 别片的改动在集成时已经提交，git status 看不见，所以差集断言不会随集成变红。
SCOPE_ALLOWED_PREFIXES = ("ts/packages/ui/", "ts/mutations/")


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


def ui_src_files():
    files = {}
    if not UI_SRC.is_dir():
        return files
    for path in sorted(UI_SRC.rglob("*.ts")):
        if path.is_file():
            files[path.relative_to(REPO_ROOT).as_posix()] = _read(path)
    return files


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


def run_capture(argv, cwd, timeout):
    """跑一条命令，合并 stdout/stderr；超时时连子进程一起杀掉。不用 shell。"""
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


def _dead_pid():
    """拿一个肯定已经不在的 pid（起一个立刻退出的子进程，等它退出）。"""
    proc = subprocess.Popen([sys.executable, "-c", "pass"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pid = proc.pid
    proc.wait()
    return pid


# ---------------------------------------------------------------------------
# 静态断言：文件在位、main 接线、既有用例
# ---------------------------------------------------------------------------

def test_static_durable_files_in_place():
    """D01–D17 的骨架：合同点名、且不随 ③d 搬家的源文件与 README 都在位。"""
    missing = [rel for rel in DURABLE_SRC_RELS if not (REPO_ROOT / rel).is_file()]
    if not README.is_file():
        missing.append(README_REL)
    fail_if([f"{rel} 不存在（基线上还没有实现）" for rel in missing], "合同点名的源文件与 README")


def test_static_main_wiring():
    """D14/D17：main.ts 的 checkArgs 三条提示原文不变，runUi 在检查通过之后转交 serveUi。"""
    code = strip_ts_comments(need_file(MAIN_REL))
    problems = []
    for msg in ("管理台只由桌面应用启动", "找不到前端资源目录", "--idle-timeout 必须是正整数"):
        if msg not in code:
            problems.append(f"checkArgs 的提示原文「{msg}」不在 main.ts")
    if "checkArgs" not in code or "EXIT_USAGE" not in code:
        problems.append("main.ts 仍应经 checkArgs 做用法检查并返回 EXIT_USAGE")
    m = re.search(r"export\s+async\s+function\s+runUi\b", code)
    if not m:
        problems.append("main.ts 里找不到 runUi")
    else:
        body = code[m.start():]
        i_check, i_serve = body.find("checkArgs"), body.find("serveUi")
        if i_serve < 0:
            problems.append("runUi 应在 checkArgs 通过之后调用 serveUi（基线里还只有「还没有实现」的占位）")
        elif i_check < 0 or i_check > i_serve:
            problems.append("serveUi 应排在 checkArgs 之后（先用法检查，再起服务）")
    fail_if(problems, "main.ts 接线（D14）")


def test_static_args_test_intact():
    """D14：ts/packages/ui/test/args.test.ts 的三条既有用例未改未删，没有 skip/only/todo。"""
    text = need_file(ARGS_TEST_REL)
    problems = []
    for title in ("不带 --desktop：退出 2，提示管理台只由桌面应用启动",
                  "前端资源目录不在、不是目录、没给：用法错误",
                  "空闲时限必须是正整数"):
        if title not in text:
            problems.append(f"args.test.ts 少了既有用例「{title}」")
    count = len(re.findall(r"(?m)^\s*it\(", text))
    if count < 3:
        problems.append(f"args.test.ts 应至少有 3 个 it，实际 {count}")
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
        if re.search(bad, text):
            problems.append(f"args.test.ts 里出现 {bad}（不许 skip、only、todo）")
    fail_if(problems, "args.test.ts 既有用例（D14）")


# ---------------------------------------------------------------------------
# 静态断言：信封、路由、静态路径
# ---------------------------------------------------------------------------

def test_static_envelope_and_routes():
    """D02/D08：信封七个字段都在 envelope.ts；routes.ts 登记本片的四条路由与引导地址的正则。"""
    envelope = need_file(ENVELOPE_REL)
    problems = []
    for field in ENVELOPE_KEYS:
        if not re.search(rf"\b{field}\b", envelope):
            problems.append(f"envelope.ts 里看不到字段 {field}")
    routes = strip_ts_comments(need_file(ROUTES_REL))
    for name in ("bootstrap", "control.bootstrap", "api.ping.get", "api.ping.post"):
        if name not in routes:
            problems.append(f"routes.ts 里看不到路由 {name}")
    if not re.search(r"\^/bootstrap/\(\[A-Za-z0-9_-\]\{1,128\}\)\$", routes):
        problems.append("bootstrap 路由应照合同的正则 ^/bootstrap/([A-Za-z0-9_-]{1,128})$")
    for path in ("/bootstrap/", "/control/bootstrap", "/api/v1/ping"):
        if path not in routes:
            problems.append(f"routes.ts 里看不到路径 {path}")
    fail_if(problems, "信封与路由（D02/D08）")


def test_static_static_reasons():
    """D09：static.ts 逐类给出 reason、Content-Type 照白名单、rawPathOf 不做规范化、
    原始路径上的 %2f/%5c/%2e/%00 检查排在解码之前（只解码一次）。"""
    code = strip_ts_comments(need_file(STATIC_REL))
    problems = []
    for reason in REASONS:
        if reason not in code:
            problems.append(f"static.ts 里看不到 reason「{reason}」")
    for ctype in CONTENT_TYPES:
        if ctype not in code:
            problems.append(f"static.ts 的 Content-Type 白名单少了「{ctype}」")
    if "index.html" not in code:
        problems.append("static.ts 应把 / 映射到 index.html")
    if "rawPathOf" not in code:
        problems.append("static.ts 应有 rawPathOf（取原始路径，不经 URL 规范化）")
    m_enc = re.search(r"%2[fF]|%5[cC]|%2[eE]|%00", code)
    m_dec = re.search(r"decodeURIComponent", code)
    if not (m_enc and m_dec):
        problems.append("static.ts 里看不到 %2f/%5c/%2e/%00 的预解码拒绝或 decodeURIComponent")
    elif m_enc.start() > m_dec.start():
        problems.append("原始路径上的 %2f/%5c/%2e/%00 检查应排在解码之前（只解码一次）")
    fail_if(problems, "静态资源边界（D09）")


def test_transitional_localhttp_constants():
    """D03/D07/D08/D11/D12：localhttp 的常量与逐字串照合同（CSP、cookie、控制头、限速参数、正文上限、
    路由名校验）。【过渡断言】迁移第 ③d 步把 src/localhttp 整体搬进 @themis/base/localhttp 之后，这些常量随之
    搬家、本条会失败，由后续任务开工之前按名字退役。"""
    src = "\n".join(strip_ts_comments(text) for text in ui_src_files().values())
    if not src.strip():
        fail_if(["ts/packages/ui/src 下没有 .ts 文件（基线上还没有实现）"], "localhttp 常量（过渡断言）")
        return
    problems = []
    for name, value in (("NONCE_TTL_MS", "60000"), ("TOKEN_BYTES", "32"), ("CONTROL_MAX_FAILURES", "5"),
                        ("CONTROL_LOCK_BASE_MS", "1000"), ("CONTROL_LOCK_MAX_MS", "60000"),
                        ("MAX_BODY_BYTES", "65536"), ("ACCESS_LOG_MAX", "1000")):
        if not re.search(rf"\b{name}\s*=\s*{value}\b", src):
            problems.append(f"看不到常量 {name} = {value}")
    for name, value in (("SESSION_COOKIE", "themis_session"), ("CONTROL_HEADER", "x-themis-control")):
        if not re.search(rf"\b{name}\s*=\s*['\"]{value}['\"]", src):
            problems.append(f"看不到常量 {name} = \"{value}\"")
    if CSP not in src:
        problems.append("CSP 应逐字照合同 D4 的那一串")
    for token in ("timingSafeEqual", "sha256", "randomBytes", "base64url", "HttpOnly", "SameSite=Strict",
                  "Path=/", "invalid-route-name", "[a-z][a-z0-9.-]"):
        if token not in src:
            problems.append(f"src 下看不到「{token}」")
    fail_if(problems, "localhttp 常量与逐字串（D03/D07/D08/D11/D12，过渡断言）")


def test_static_server_lifecycle_lockdir():
    """D01/D13/D15：server 只绑 127.0.0.1、maxRequestBodySize 是 131072；idleMs 的 1800 秒与
    MAX_SAFE_INTEGER 封顶、setTimeout 每段不超过 2^31-1；lockdir 的三条被占提示原文。"""
    server = strip_ts_comments(need_file(SERVER_REL))
    problems = []
    if not re.search(r"['\"]127\.0\.0\.1['\"]", server):
        problems.append("server.ts 应只绑 127.0.0.1")
    if not re.search(r"maxRequestBodySize\s*:\s*131072", server):
        problems.append("server.ts 的 maxRequestBodySize 应是 131072（64 KiB 的两倍）")
    lifecycle = strip_ts_comments(need_file(LIFECYCLE_REL))
    if "1800" not in lifecycle:
        problems.append("lifecycle.ts 应有 1800 秒（空闲时限缺省）")
    if "MAX_SAFE_INTEGER" not in lifecycle:
        problems.append("lifecycle.ts 的换算应封顶 Number.MAX_SAFE_INTEGER")
    if not re.search(r"2147483647|2\s*\*\*\s*31|0x7fff", lifecycle):
        problems.append("lifecycle.ts 的 setTimeout 每段应不超过 2^31-1 毫秒")
    lockdir = strip_ts_comments(need_file(LOCKDIR_REL))
    for msg in ("本仓库已有本机服务在运行（pid", "本仓库已有本机服务正在启动（.agent/.ui.lock）",
                "无法确认 .agent/.ui.lock 的持有者（pid"):
        if msg not in lockdir:
            problems.append(f"lockdir.ts 应保留提示原文：{msg}")
    fail_if(problems, "server/lifecycle/lockdir（D01/D13/D15）")


def test_static_readme_known_limits():
    """D13：README 写明 Bun 自己给出的三种响应（413、413、400）不带安全头与理由、服务自己的 64 KiB 加 1
    先于 Bun 的上限触发、maxRequestBodySize 是 131072。"""
    text = need_file(README_REL)
    problems = []
    if "413" not in text:
        problems.append("README 应写明 Bun 自己回的 413")
    if "400" not in text:
        problems.append("README 应写明 Bun 自己回的 400")
    if "畸形" not in text:
        problems.append("README 应写明畸形请求行的 400")
    if "分块" not in text:
        problems.append("README 应写明分块传输超过 Bun 上限的 413")
    if not (("不带安全头" in text) or ("没有安全头" in text)):
        problems.append("README 应写明这三种响应不带安全头")
    if "纯文本" not in text:
        problems.append("README 应写明理由（Bun 生成的纯文本，没有攻击者可控的 HTML）")
    if not (("64 KiB" in text) or ("65536" in text)):
        problems.append("README 应写明服务自己的 64 KiB 加 1 先停")
    if "131072" not in text:
        problems.append("README 应写明 maxRequestBodySize 是 131072")
    fail_if(problems, "README 已知限制（D13）")


def test_static_import_graph():
    """D17：不随 ③d 搬家的每个源文件都能从 main.ts 顺 import 到达（写了却没接进产品的不算实现）。"""
    files = ui_src_files()
    problems = []
    if MAIN_REL not in files:
        fail_if(["ts/packages/ui/src/main.ts 读不到"], "src 接线")
        return
    reached = reachable_from(files, MAIN_REL)
    for rel in DURABLE_SRC_RELS:
        if rel == MAIN_REL:
            continue
        if rel not in files:
            problems.append(f"{rel} 不存在")
        elif rel not in reached:
            problems.append(f"{rel} 从 main.ts 顺 import 到不了（写了却没接进产品）")
    fail_if(problems, "src 接线（D17）")


def test_static_scope():
    """D17：.gitignore 含 .agent/.ui.lock/（长期断言）。

    执行期的改动范围由合同 V07 管；门禁与流水线有没有弄脏工作区，由 test_pipeline_scope 用流水线前后的
    git status 差集证明（对照 t002/t012 的前后差集惯例）。这里不再对全树做绝对范围断言：后续任务把本文件
    点名进 R01 时，它们自己的合法改动（③d 动 ts/packages/base、D3 动 desktop/）会让那种断言必红，
    战后门禁写出的变异清单文件同样会。"""
    if ".agent/.ui.lock/" not in _read(REPO_ROOT / ".gitignore"):
        fail_if([".gitignore 应含 .agent/.ui.lock/（锁目录记 pid 与端口，是本机运行状态，不提交）"],
                "共享文件（D17）")


# ---------------------------------------------------------------------------
# 黑盒 HTTP 客户端（原始套接字：自定义 Host/Cookie/Origin、原始路径、分块正文都不被客户端规范化）
# ---------------------------------------------------------------------------

class Resp:
    def __init__(self, status, reason, headers, body):
        self.status = status
        self.reason = reason
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
    return int(parts[1]), (parts[2] if len(parts) > 2 else ""), headers


def _read_chunked(sock, rest, timeout):
    sock.settimeout(timeout)
    buf, out = rest, b""
    while True:
        while b"\r\n" not in buf:
            chunk = sock.recv(65536)
            if not chunk:
                return out
            buf += chunk
        line, _, buf = buf.partition(b"\r\n")
        try:
            size = int(line.split(b";", 1)[0].strip(), 16)
        except ValueError:
            return out
        if size == 0:
            return out
        while len(buf) < size + 2:
            chunk = sock.recv(65536)
            if not chunk:
                return out
            buf += chunk
        out += buf[:size]
        buf = buf[size + 2:]


def _read_response(sock, method, timeout):
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
    status, reason, headers = _parse_head(head)
    resp = Resp(status, reason, headers, b"")
    if method.upper() == "HEAD" or status in (204, 304):
        return resp
    if "chunked" in (resp.get("transfer-encoding") or "").lower():
        resp.body = _read_chunked(sock, rest, timeout)
        return resp
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
        except socket.timeout:
            break
        except OSError:
            break
        if not chunk:
            break
        body += chunk
    resp.body = body
    return resp


def raw_request(port, method, target, headers=(), body=b"", host=None, timeout=20, read_body=True):
    """发一个请求并读完整响应。headers 是 [(名, 值)]，原样发送（不发客户端自己的默认值）。"""
    lines = [f"{method} {target} HTTP/1.1", f"Host: {host or f'127.0.0.1:{port}'}",
             "Connection: close", "Accept: */*"]
    lines += [f"{key}: {value}" for key, value in headers]
    if method.upper() in ("POST", "PUT") and not any(k.lower() == "transfer-encoding" for k, _v in headers):
        lines.append(f"Content-Length: {len(body)}")
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1") + body
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall(raw)
        resp = _read_response(sock, method, timeout)
    return resp if read_body else Resp(resp.status, resp.reason, resp.headers, b"")


def raw_no_body(port, method, target, headers, content_length, timeout=10, host=None):
    """只发头（声明 Content-Length 却不发正文）：服务若真的去读正文，这里就会超时。"""
    lines = [f"{method} {target} HTTP/1.1", f"Host: {host or f'127.0.0.1:{port}'}",
             "Connection: close", f"Content-Length: {content_length}"]
    lines += [f"{key}: {value}" for key, value in headers]
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall(raw)
        return _read_response(sock, method, timeout)


def raw_chunked_watch(port, method, target, headers, total, chunk_size=8192, timeout=25, host=None):
    """分块发送 total 字节，边发边看服务是不是提前回响应。返回 (Resp, early, sent)。"""
    lines = [f"{method} {target} HTTP/1.1", f"Host: {host or f'127.0.0.1:{port}'}",
             "Connection: close", "Transfer-Encoding: chunked"]
    lines += [f"{key}: {value}" for key, value in headers]
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    filler = b"x" * chunk_size
    resp, early, sent = None, False, 0
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall(raw)
        while sent < total:
            size = min(chunk_size, total - sent)
            sock.sendall(b"%x\r\n%s\r\n" % (size, filler[:size]))
            sent += size
            readable, _w, _e = select.select([sock], [], [], 0.15)
            if readable:
                resp, early = _read_response(sock, method, timeout), True
                break
        if resp is None:
            readable, _w, _e = select.select([sock], [], [], 3.0)
            if readable:
                resp, early = _read_response(sock, method, timeout), True
        if resp is None:
            sock.sendall(b"0\r\n\r\n")
            resp = _read_response(sock, method, timeout)
    return resp, early, sent


# ---------------------------------------------------------------------------
# 信封与响应头的小断言
# ---------------------------------------------------------------------------

def parse_envelope(group, resp, label):
    try:
        data = json.loads(resp.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        group.check(False, f"{label}：正文不是 JSON 信封：{resp.body[:200]!r}")
        return None
    if not isinstance(data, dict):
        group.check(False, f"{label}：正文不是 JSON 对象：{resp.body[:200]!r}")
        return None
    group.check(list(data.keys()) == ENVELOPE_KEYS,
                f"{label}：信封七个字段与次序应为 {ENVELOPE_KEYS}，实际 {list(data.keys())}")
    return data


def check_ok_envelope(group, resp, label):
    data = parse_envelope(group, resp, label)
    if data is not None:
        group.check(data.get("ok") is True, f"{label}：ok 应为 true，实际 {data.get('ok')!r}")
    return data


def check_error_envelope(group, resp, label):
    data = parse_envelope(group, resp, label)
    if data is None:
        return None
    group.check(data.get("ok") is False, f"{label}：ok 应为 false，实际 {data.get('ok')!r}")
    group.check(data.get("exit_code") is None, f"{label}：exit_code 应为 null")
    group.check(data.get("data") is None, f"{label}：data 应为 null，实际 {data.get('data')!r}")
    group.check(data.get("output") == [], f"{label}：output 应为空数组")
    group.check(data.get("command") == [], f"{label}：command 应为空数组")
    messages = data.get("messages")
    group.check(isinstance(messages, list) and len(messages) == 1
                and isinstance(messages[0], str) and messages[0].startswith("ERROR: "),
                f"{label}：messages 应只有一行 ERROR: …，实际 {messages!r}")
    return data


def cache_expect(label):
    if label in ("static-200-index", "static-200-js"):
        return "no-cache"
    if label.startswith("static-"):
        return None
    return "no-store"


def header_problems(label, headers):
    out = []

    def get(name):
        for key, value in headers:
            if key.lower() == name:
                return value
        return None

    if get("content-security-policy") != CSP:
        out.append(f"CSP 应逐字照合同 D4，实际 {get('content-security-policy')!r}")
    if get("x-content-type-options") != "nosniff":
        out.append(f"X-Content-Type-Options 应是 nosniff，实际 {get('x-content-type-options')!r}")
    if get("referrer-policy") != "no-referrer":
        out.append(f"Referrer-Policy 应是 no-referrer，实际 {get('referrer-policy')!r}")
    for key, _value in headers:
        if key.lower().startswith("access-control"):
            out.append(f"出现了 {key} 头（不开 CORS）")
    want = cache_expect(label)
    if want is not None and get("cache-control") != want:
        out.append(f"Cache-Control 应是 {want}，实际 {get('cache-control')!r}")
    return out


# ---------------------------------------------------------------------------
# 服务进程句柄
# ---------------------------------------------------------------------------

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
    """一个起着的 Bun 服务进程（或经 pi_dispatch.py 起的同一棵树）。stdout/stderr 由后台线程收行。"""

    def __init__(self, proc, label):
        self.proc = proc
        self.label = label
        self.out_lines = []
        self.err_lines = []
        self.handshake_line = None
        self.handshake_data = None
        self._threads = [threading.Thread(target=_pump, args=(proc.stdout, self.out_lines), daemon=True),
                         threading.Thread(target=_pump, args=(proc.stderr, self.err_lines), daemon=True)]
        for thread in self._threads:
            thread.start()

    def _scan(self):
        for raw in list(self.out_lines):
            text = raw.decode("utf-8", "replace").strip()
            if not text:
                continue
            try:
                data = json.loads(text)
            except ValueError:
                continue
            if isinstance(data, dict) and "themis_ui" in data:
                self.handshake_line = text
                self.handshake_data = data
                return data
        return None

    def handshake(self, timeout=45):
        deadline = time.monotonic() + timeout
        while True:
            found = self._scan()
            if found is not None:
                return found
            if self.proc.poll() is not None:
                time.sleep(0.5)
                return self._scan()
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.1)

    def stdout_text(self):
        return b"".join(self.out_lines).decode("utf-8", "replace")

    def stderr_text(self):
        return b"".join(self.err_lines).decode("utf-8", "replace")

    def stderr_tail(self, limit=1200):
        return self.stderr_text()[-limit:]

    def close_stdin(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass

    def wait(self, timeout):
        try:
            return self.proc.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            return None, True

    def stop(self, timeout=15):
        """关 stdin 等退出；没退出就杀进程树。返回 (退出码, 是否超时, 是否被杀)。"""
        self.close_stdin()
        code, timed_out = self.wait(timeout)
        killed = False
        if timed_out:
            _kill_tree(self.proc)
            killed = True
            code, _ = self.wait(10)
        return code, timed_out, killed

    def kill(self):
        _kill_tree(self.proc)


class Brief:
    """跑完就退的启动（用法错误之类）：退出码 + stdout + stderr。"""

    def __init__(self, code, stdout, stderr, timed_out):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out


# ---------------------------------------------------------------------------
# 会话级流水线夹具
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
        return "\n".join(self.out.splitlines()[-45:])[-3500:]


class Group:
    """一个 DoD 检查组的失败清单。"""

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
        self.steps = {}
        self.stopped_reason = ""
        self.bun = None
        self.node = None
        self.services = []
        self.groups = {}
        self.samples = []
        self.tmp = None

    def group(self, name):
        grp = Group(name)
        self.groups[name] = grp
        return grp

    def sample(self, label, resp):
        self.samples.append((label, resp.status, list(resp.headers)))

    def launch(self, repo, assets, idle_timeout=None, desktop=True):
        """照启动器同一条路起服务：bun --no-env-file --config=ts/bunfig.toml cli 入口 --pyargs-b64。"""
        pyargs = {"command": ["ui"], "repo": str(repo), "desktop": bool(desktop),
                  "assets": str(assets) if assets is not None else None, "transcript": [],
                  "idle_timeout": idle_timeout, "python": sys.executable,
                  "kernel": str(REPO_ROOT / "scripts" / "pi_dispatch.py")}
        argv = [str(self.bun), "--no-env-file", "--config=%s" % (TS / "bunfig.toml"),
                str(TS / "packages" / "cli" / "src" / "main.ts"), "--pyargs-b64",
                base64.b64encode(json.dumps(pyargs).encode("utf-8")).decode("ascii")]
        proc = subprocess.Popen(argv, cwd=str(REPO_ROOT), env=_ts_env(), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        svc = Service(proc, "direct")
        self.services.append(svc)
        return svc

    def launch_brief(self, repo, assets, idle_timeout=None, desktop=True, timeout=60):
        """起一个应当立刻退出的进程（用法错误、锁被占），收齐全再返回。"""
        pyargs = {"command": ["ui"], "repo": str(repo), "desktop": bool(desktop),
                  "assets": str(assets) if assets is not None else None, "transcript": [],
                  "idle_timeout": idle_timeout, "python": sys.executable,
                  "kernel": str(REPO_ROOT / "scripts" / "pi_dispatch.py")}
        argv = [str(self.bun), "--no-env-file", "--config=%s" % (TS / "bunfig.toml"),
                str(TS / "packages" / "cli" / "src" / "main.ts"), "--pyargs-b64",
                base64.b64encode(json.dumps(pyargs).encode("utf-8")).decode("ascii")]
        try:
            proc = subprocess.Popen(argv, cwd=str(REPO_ROOT), env=_ts_env(), stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            self.services.append(proc)
            out, err = proc.communicate(timeout=timeout)
            return Brief(proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), False)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            try:
                out, err = proc.communicate(timeout=30)
            except Exception:
                out, err = b"", b""
            return Brief(None, out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), True)


def _deps_ready():
    return ((TS / "node_modules" / ".themis-installed").is_file()
            and (TS / "node_modules" / "vitest").is_dir()
            and (TS / "node_modules" / "typescript").is_dir())


def _stamp_bun():
    try:
        stamp = json.loads((TS / "node_modules" / ".themis-installed").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    path = stamp.get("bun_path") if isinstance(stamp, dict) else None
    return Path(path) if isinstance(path, str) and Path(path).is_file() else None


def _run_step(pipe, name, argv, cwd, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 10:
        pipe.stopped_reason = f"{name} 之前整体预算 {PIPELINE_BUDGET}s 已用完，未运行"
        return None
    code, timed_out, out, seconds = run_capture(argv, cwd, min(STEP_CAPS[name], remaining))
    pipe.steps[name] = Step(name, argv, code, timed_out, out, seconds)
    return pipe.steps[name]


def assert_step_ok(pipe, name):
    assert pipe.ran, pipe.reason
    step = pipe.steps.get(name)
    assert step is not None, f"{name} 未运行：{pipe.stopped_reason or '前置步骤失败'}"
    assert step.code == 0, (f"{name} 退出码 {step.code}{'（超时被杀）' if step.timed_out else ''}，"
                            f"用时 {step.seconds:.0f}s\n--- 输出尾部 ---\n{step.tail}")
    return step


@pytest.fixture(scope="session")
def pipeline(tmp_path_factory):
    pipe = Pipeline()
    if not (UI_SRC / "localhttp").is_dir() or not (UI_SRC / "server.ts").is_file():
        pipe.reason = ("候选里还没有 src/localhttp/ 与 src/server.ts（基线 2a5c721，本片功能还没实现），"
                       "未安装依赖、未起服务；执行端实现之后，流水线才会运行 bun install、黑盒服务检查与 V02/tsc")
        return pipe
    bun = find_bun()
    if bun is None:
        pipe.reason = "PATH 上找不到 Bun（bun.exe 或 npm 的 bun.cmd 垫片旁边的 bun.exe）"
        return pipe
    pipe.bun = bun
    # 候选在位（src/localhttp/ 与 server.ts）、Bun 也找得到：流水线真的跑了。少了这一句，实现全部正确时
    # 17 条流水线用例仍会在 assert pipeline.ran 处以空 reason 失败（一审 B1；对照 t002:499、t012:3523）。
    pipe.ran = True
    pipe.node = shutil.which("node")
    pipe.tmp = tmp_path_factory.mktemp("t015-gate")
    pipe.status_before = git_status_set()
    deadline = time.monotonic() + PIPELINE_BUDGET
    try:
        if not _deps_ready():
            _run_step(pipe, "bun install", [str(pipe.bun), "install", "--frozen-lockfile"], TS, deadline)
        if not _deps_ready():
            if not pipe.stopped_reason:
                pipe.stopped_reason = "bun install 之后依赖仍不齐（node_modules/.themis-installed 不在）"
        else:
            stamped = _stamp_bun()
            if stamped is not None:
                pipe.bun = stamped
            _run_service_checks(pipe, deadline)
            if pipe.node:
                _run_step(pipe, "vitest-contracts",
                          [pipe.node, "node_modules/vitest/vitest.mjs", "run",
                           "packages/contracts/test/ui.contract.test.ts",
                           "packages/contracts/test/source-hygiene.test.ts"], TS, deadline)
                _run_step(pipe, "tsc", [pipe.node, "node_modules/typescript/bin/tsc", "-p", "tsconfig.json"],
                          TS, deadline)
            else:
                pipe.stopped_reason = "找不到 node，V02 与 tsc 未运行"
    finally:
        pipe.status_after = git_status_set()
        for svc in pipe.services:
            if isinstance(svc, Service):
                try:
                    svc.kill()
                except Exception:
                    pass
            else:
                try:
                    _kill_tree(svc)
                except Exception:
                    pass
    return pipe


# ---------------------------------------------------------------------------
# 黑盒服务检查：一个长住的 main 服务 + 若干短命服务
# ---------------------------------------------------------------------------

REQUIRED_SAMPLES = ("302-bootstrap", "200-ping", "401-nocookie", "403-badhost", "403-control-no-token",
                    "404-bootstrap-rejected", "404-api-noroute", "405-put", "413-chunked",
                    "415-content-type", "429-control", "static-200-index", "static-200-js",
                    "static-404-missing", "static-400-traversal")


def _run_service_checks(pipe, deadline):
    tmp = pipe.tmp
    soft = min(deadline - 150, time.monotonic() + STEP_CAPS["service checks"])

    def group(name):
        return pipe.group(name)

    def phase(fn, name):
        grp = group(name)
        if time.monotonic() > soft:
            grp.problems.append(f"服务检查的整体预算（{STEP_CAPS['service checks']}s / 全局 {PIPELINE_BUDGET}s）将尽，{name} 未运行")
            return grp
        try:
            fn(grp)
        except Exception as exc:  # 一个检查组出错不拖垮其余
            grp.problems.append(f"{name} 检查抛出异常：{type(exc).__name__}: {exc}")
        return grp

    # 资源目录与目录外金丝雀（负面路径断言「拿不到 --assets 之外的文件」）
    svc_dir = tmp / "svc"
    assets = svc_dir / "assets"
    (assets / "assets").mkdir(parents=True, exist_ok=True)
    (assets / "sub").mkdir(parents=True, exist_ok=True)
    (assets / "index.html").write_text("<!doctype html><title>T015</title><p>T015-INDEX-MARKER</p>\n", encoding="utf-8")
    (assets / "assets" / "app.js").write_text("// T015-APP-JS-MARKER\nconsole.log('t015');\n", encoding="utf-8")
    (assets / "notes.xyz").write_text("T015-NOTES-XYZ\n", encoding="utf-8")
    canary = "T015-CANARY-" + uuid.uuid4().hex
    (svc_dir / "secret.txt").write_text(canary + "\n", encoding="utf-8")
    (tmp / "secret.txt").write_text(canary + "\n", encoding="utf-8")
    body_canary = "T015-BODY-" + uuid.uuid4().hex
    repo = tmp / "repo"
    repo.mkdir(exist_ok=True)
    state = {}

    main = pipe.launch(repo, assets)
    hs = main.handshake()
    if hs is None:
        why = (f"主服务没有在 45 秒内写出握手行（退出码 {main.proc.poll()}）：{main.stderr_tail()}")
        for name in ("handshake", "host", "session", "csrf", "methods", "assets", "body", "headers",
                     "control", "rejection", "logs", "usage", "lifecycle", "launcher"):
            group(name).check(False, why)
        return

    port = None
    try:
        port = urlsplit(hs["origin"]).port
    except Exception:
        port = None
    state["port"] = port
    state["token"] = hs.get("control")
    state["bootstrap_path"] = urlsplit(hs["bootstrap"]).path if hs.get("bootstrap") else None
    state["original_bootstrap_path"] = state["bootstrap_path"]
    state["original_nonce"] = (state["bootstrap_path"] or "").rsplit("/", 1)[-1]
    state["cookie_value"] = None
    state["final_bootstrap_path"] = None

    # ---- D01 握手与绑定 ----------------------------------------------------
    def check_handshake(grp):
        grp.check(isinstance(port, int), f"握手行的 origin 应带端口：{hs.get('origin')!r}")
        if not isinstance(port, int):
            return
        grp.check(list(hs.keys()) == ["themis_ui", "bootstrap", "origin", "control", "pid"],
                  f"握手行字段与次序应照合同，实际 {list(hs.keys())}")
        grp.check(hs.get("origin") == f"http://127.0.0.1:{port}",
                  f"origin 应是 http://127.0.0.1:{port}，实际 {hs.get('origin')!r}")
        grp.check(isinstance(hs.get("bootstrap"), str)
                  and hs["bootstrap"].startswith(f"http://127.0.0.1:{port}/bootstrap/"),
                  f"bootstrap 应是 http://127.0.0.1:{port}/bootstrap/<nonce>，实际 {hs.get('bootstrap')!r}")
        grp.check(hs.get("pid") == main.proc.pid,
                  f"握手行的 pid 应是服务进程的 pid {main.proc.pid}，实际 {hs.get('pid')!r}")
        grp.check(isinstance(state["token"], str) and re.fullmatch(r"[A-Za-z0-9_-]{43}", state["token"]),
                  f"控制令牌应是 32 字节随机数的 base64url（43 字符），实际 {state['token']!r}")
        reachable_v6 = False
        try:
            with socket.create_connection(("::1", port), timeout=5):
                reachable_v6 = True
        except OSError:
            reachable_v6 = False
        grp.check(not reachable_v6, "服务只绑 127.0.0.1：同一端口在 ::1 上应连不上（实际连上了）")
        sanity = raw_request(port, "GET", "/")
        grp.check(sanity.status == 200, f"127.0.0.1:{port} 上应能访问（sanity），实际 {sanity.status}")

    # ---- D04 Host 校验 -----------------------------------------------------
    def check_host(grp):
        origin = f"http://127.0.0.1:{port}"
        evil = f"evil.example:{port}"
        for method, path, hdrs in (("GET", "/", ()),
                                   ("GET", "/api/v1/ping", ()),
                                   ("GET", state["bootstrap_path"], ()),
                                   ("POST", "/control/bootstrap",
                                    [("Origin", f"http://{evil}"), ("X-Themis-UI", "1"),
                                     ("Content-Type", "application/json")])):
            resp = raw_request(port, method, path, headers=hdrs, host=evil,
                               body=b"{}" if method == "POST" else b"")
            grp.check(resp.status == 403, f"Host 是 {evil} 时 {method} {path} 应 403，实际 {resp.status}")
        for bad in (f"127.0.0.1:{port + 1}", f"localhost:{port + 1}", "127.0.0.1", "localhost",
                    "localhost.", f"localhost.:{port}"):
            resp = raw_request(port, "GET", "/", host=bad)
            grp.check(resp.status == 403, f"Host 是 {bad!r} 时应 403，实际 {resp.status}")
        resp = raw_request(port, "GET", "/", host=f"localhost:{port}")
        grp.check(resp.status == 200, f"Host 是 localhost:{port} 时应放行，实际 {resp.status}")
        # Host 不对时引导地址没有被消耗
        resp = raw_request(port, "GET", state["bootstrap_path"], host=evil)
        grp.check(resp.status == 403, f"Host 不对时引导地址应 403，实际 {resp.status}")
        resp = raw_request(port, "GET", state["bootstrap_path"])
        grp.check(resp.status == 302,
                  f"Host 不对的 403 之后，同一个引导地址用正确的 Host 仍应可用（没被消耗），实际 {resp.status}")
        set_cookie = resp.get("set-cookie")
        grp.check(bool(set_cookie) and bool(re.fullmatch(COOKIE_RE, set_cookie)),
                  f"引导成功的 Set-Cookie 应逐字是 themis_session=<令牌>; HttpOnly; SameSite=Strict; Path=/，实际 {set_cookie!r}")
        if set_cookie:
            state["cookie_value"] = set_cookie.split("=", 1)[1].split(";", 1)[0]
        location = resp.get("location")
        grp.check(location is not None and urlsplit(location).path == "/",
                  f"引导成功应 302 到 /，实际 Location={location!r}")

    # ---- D02 会话与引导地址 ------------------------------------------------
    def check_session(grp):
        cookie = f"themis_session={state['cookie_value']}" if state["cookie_value"] else None
        for method in ("GET", "POST"):
            hdrs = ([("Origin", f"http://127.0.0.1:{port}"), ("X-Themis-UI", "1"),
                     ("Content-Type", "application/json")] if method == "POST" else [])
            resp = raw_request(port, method, "/api/v1/ping", headers=hdrs,
                               body=b"{}" if method == "POST" else b"")
            grp.check(resp.status == 401, f"不带 cookie 的 {method} /api/v1/ping 应 401，实际 {resp.status}")
            check_error_envelope(grp, resp, f"401-{method}-nocookie")
            pipe.sample("401-nocookie", resp)
        for label, value in (("cookie 错", "themis_session=wrong"),
                             ("cookie 重复", "themis_session=a; themis_session=b")):
            resp = raw_request(port, "GET", "/api/v1/ping", headers=[("Cookie", value)])
            grp.check(resp.status == 401, f"{label} 应 401，实际 {resp.status}")
        # 引导地址只能用一次；过期/用过/不存在走同一个响应
        resp = raw_request(port, "GET", state["bootstrap_path"])
        grp.check(resp.status == 404, f"引导地址第二次应 404，实际 {resp.status}")
        grp.check(resp.get("set-cookie") is None, "引导地址失败时不应带 Set-Cookie")
        grp.check(resp.body.decode("utf-8", "replace") == "引导地址无效\n",
                  f"引导地址失败的正文应逐字是「引导地址无效」加换行，实际 {resp.body!r}")
        grp.check((resp.get("content-type") or "").split(";")[0].strip() == "text/plain",
                  f"引导地址失败应是 text/plain，实际 {resp.get('content-type')!r}")
        pipe.sample("404-bootstrap-rejected", resp)
        resp = raw_request(port, "GET", "/api/v1/nope")
        grp.check(resp.status == 401, f"/api/ 下不存在的路径没有会话应 401，实际 {resp.status}")
        if cookie:
            resp = raw_request(port, "GET", "/api/v1/nope", headers=[("Cookie", cookie)])
            grp.check(resp.status == 404, f"/api/ 下不存在的路径有会话应 404，实际 {resp.status}")
            pipe.sample("404-api-noroute", resp)
            resp = raw_request(port, "GET", "/api/v1/ping", headers=[("Cookie", cookie)])
            grp.check(resp.status == 200, f"带有效会话的 GET /api/v1/ping 应 200，实际 {resp.status}")
            data = check_ok_envelope(grp, resp, "200-ping")
            if data is not None:
                posts = (data.get("data") or {}).get("posts") if isinstance(data.get("data"), dict) else None
                grp.check(posts == 0, f"还没有成功 POST 时 posts 应仍为 0，实际 {posts!r}")
            pipe.sample("200-ping", resp)

    # ---- D05 CSRF ----------------------------------------------------------
    def check_csrf(grp):
        origin = f"http://127.0.0.1:{port}"
        cookie = f"themis_session={state['cookie_value']}" if state["cookie_value"] else None

        def post(origin_value=origin, ui="1", ctype="application/json", body=b"{}", use_cookie=True):
            hdrs = []
            if use_cookie and cookie:
                hdrs.append(("Cookie", cookie))
            if origin_value is not None:
                hdrs.append(("Origin", origin_value))
            if ui is not None:
                hdrs.append(("X-Themis-UI", ui))
            if ctype is not None:
                hdrs.append(("Content-Type", ctype))
            return raw_request(port, "POST", "/api/v1/ping", headers=hdrs, body=body)

        for label, resp in (("缺 X-Themis-UI", post(ui=None)),
                            ("Origin 不同", post(origin_value="https://evil.example")),
                            ("缺 Origin", post(origin_value=None))):
            grp.check(resp.status == 403, f"POST {label} 应 403，实际 {resp.status}")
        for label, ctype in (("text/plain", "text/plain"), ("application/jsonp", "application/jsonp")):
            resp = post(ctype=ctype)
            grp.check(resp.status == 415, f"Content-Type 是 {label} 应 415，实际 {resp.status}")
            if label == "text/plain":
                pipe.sample("415-content-type", resp)
        # 次序：Origin 不对优先于缺头与 Content-Type；缺头优先于 Content-Type
        grp.check(post(origin_value="https://evil.example", ui=None, ctype="text/plain").status == 403,
                  "Origin 不对时（即使同时缺 X-Themis-UI、Content-Type 也不对）应 403")
        grp.check(post(ui=None, ctype="text/plain").status == 403,
                  "缺 X-Themis-UI 时（即使 Content-Type 也不对）应 403")
        # 三种拒绝下处理函数没有运行
        resp = raw_request(port, "GET", "/api/v1/ping", headers=[("Cookie", cookie)] if cookie else [])
        data = check_ok_envelope(grp, resp, "posts-after-csrf")
        if data is not None:
            posts = (data.get("data") or {}).get("posts") if isinstance(data.get("data"), dict) else None
            grp.check(posts == 0, f"CSRF 被拒时处理函数不应运行（posts 应仍为 0），实际 {posts!r}")
        # 合格的 POST（Content-Type 带参数）
        resp = post(ctype="application/json; charset=utf-8")
        grp.check(resp.status == 200, f"合格的 POST 应 200，实际 {resp.status}")
        data = check_ok_envelope(grp, resp, "posts-after-valid")
        if data is not None:
            posts = (data.get("data") or {}).get("posts") if isinstance(data.get("data"), dict) else None
            grp.check(posts == 1, f"合格的 POST 应把 posts 变成 1，实际 {posts!r}")

    # ---- D16 只有 GET 与 POST ----------------------------------------------
    def check_methods(grp):
        for method in ("PUT", "DELETE", "OPTIONS", "HEAD"):
            for path in ("/", "/api/v1/ping"):
                resp = raw_request(port, method, path)
                grp.check(resp.status == 405, f"{method} {path} 应 405，实际 {resp.status}")
                if path == "/":
                    grp.check(resp.get("allow") == "GET, POST",
                              f"{method} 应带 Allow: GET, POST，实际 {resp.get('allow')!r}")
                    if method == "PUT":
                        pipe.sample("405-put", resp)
        resp = raw_request(port, "PUT", "/api/v1/ping")
        grp.check(resp.status == 405, f"方法校验先于会话校验：不带 cookie 的 PUT /api/v1/ping 也应 405，实际 {resp.status}")

    # ---- D09/D10/D12 静态资源与目录边界 ------------------------------------
    def check_assets(grp):
        resp = raw_request(port, "GET", "/")
        grp.check(resp.status == 200, f"/ 应给 index.html，实际 {resp.status}")
        grp.check((resp.get("content-type") or "").split(";")[0].strip() == "text/html",
                  f"/ 的 Content-Type 应是 text/html，实际 {resp.get('content-type')!r}")
        grp.check(b"T015-INDEX-MARKER" in resp.body, "/ 的正文应是 index.html 的内容")
        pipe.sample("static-200-index", resp)
        resp = raw_request(port, "GET", "/assets/app.js")
        grp.check(resp.status == 200, f"/assets/app.js 应 200，实际 {resp.status}")
        grp.check((resp.get("content-type") or "").split(";")[0].strip() == "text/javascript",
                  f"/assets/app.js 的 Content-Type 应是 text/javascript，实际 {resp.get('content-type')!r}")
        grp.check(b"T015-APP-JS-MARKER" in resp.body, "/assets/app.js 的正文应是该文件的内容")
        pipe.sample("static-200-js", resp)
        for label, path in (("找不到的文件", "/missing.txt"), ("不在白名单的后缀", "/notes.xyz"),
                            ("目录", "/sub")):
            resp = raw_request(port, "GET", path)
            grp.check(resp.status == 404, f"{label}（{path}）应 404，实际 {resp.status}")
            if label == "找不到的文件":
                pipe.sample("static-404-missing", resp)
        # 合同 D10 点名的五条负面路径（客户端不做规范化）
        for target, expect in (("/..%2f..%2fsecret.txt", 400),
                               ("/%2e%2e%2fsecret.txt", 400),
                               ("/x%5c..%5csecret.txt", 400),
                               ("/secret%00.txt", 400),
                               ("/%252e%252e%252fsecret.txt", 404)):
            resp = raw_request(port, "GET", target)
            grp.check(resp.status == expect, f"{target} 应回 {expect}，实际 {resp.status}")
            grp.check(canary.encode("utf-8") not in resp.body,
                      f"{target}：正文里不应出现 --assets 之外的金丝雀文件内容")
            if expect == 400:
                pipe.sample("static-400-traversal", resp)
        # Bun 会规范化的两条：只断言拿不到目录外的文件
        for target in ("/../secret.txt", "/x\\..\\..\\secret.txt"):
            resp = raw_request(port, "GET", target)
            grp.check(canary.encode("utf-8") not in resp.body,
                      f"{target}：正文里不应出现 --assets 之外的金丝雀文件内容（实际 {resp.status}）")

    # ---- D11 请求体上限 ----------------------------------------------------
    def check_body(grp):
        origin = f"http://127.0.0.1:{port}"
        cookie = f"themis_session={state['cookie_value']}" if state["cookie_value"] else None
        base = [("Origin", origin), ("X-Themis-UI", "1"), ("Content-Type", "application/json")]
        if cookie:
            base.append(("Cookie", cookie))
        # 分块传输 65537 字节：413，且服务数到第 65537 个字节就停（不等正文收完）
        resp, early, sent = raw_chunked_watch(port, "POST", "/api/v1/ping", base, total=65537 + 8192)
        grp.check(resp.status == 413, f"分块传输 65537 字节应 413，实际 {resp.status}")
        grp.check(early, f"分块传输超限后服务应提前回 413（已发 {sent} 字节、还没发结束块时就应收到响应）")
        pipe.sample("413-chunked", resp)
        # 正好 65536 字节的合法 JSON：收下
        pad = "x" * (65536 - len('{"pad":""}'))
        payload = ('{"pad":"' + pad + '"}').encode("utf-8")
        resp = raw_request(port, "POST", "/api/v1/ping", headers=base, body=payload)
        grp.check(resp.status == 200, f"正好 65536 字节的合法 JSON 应 200，实际 {resp.status}")
        check_ok_envelope(grp, resp, "body-65536")
        # Content-Length 声明超过上限：413 且一个字节也不读
        resp = raw_no_body(port, "POST", "/api/v1/ping", base, content_length=65537)
        grp.check(resp.status == 413, f"Content-Length 声明 65537 应 413，实际 {resp.status}")
        pipe.sample("413-declared", resp)
        # 坏的 UTF-8 / 不是 JSON / 空正文：400 且不回显原值
        for label, payload in (("坏的 UTF-8", b"\xff\xfe\xff\xfe"),
                               ("不是 JSON", body_canary.encode("utf-8") + b" not json"),
                               ("空正文", b"")):
            resp = raw_request(port, "POST", "/api/v1/ping", headers=base, body=payload)
            grp.check(resp.status == 400, f"{label} 应 400，实际 {resp.status}")
            if payload:  # 空正文时“不回显原值”恒真，没有可断言的内容
                grp.check(payload not in resp.body, f"{label}：响应里不应回显原值 {payload[:40]!r}")

    # ---- D12 安全头矩阵 ----------------------------------------------------
    def check_headers(grp):
        origin = f"http://127.0.0.1:{port}"
        # 控制阶段作废了旧会话：用最后给出的新引导地址拿一个新会话
        path = state.get("final_bootstrap_path")
        grp.check(bool(path), "控制阶段应给出新的引导地址（否则拿不到新会话）")
        if path:
            resp = raw_request(port, "GET", path)
            grp.check(resp.status == 302, f"新的引导地址应可用，实际 {resp.status}")
            pipe.sample("302-bootstrap", resp)
            set_cookie = resp.get("set-cookie")
            grp.check(bool(set_cookie) and bool(re.fullmatch(COOKIE_RE, set_cookie)),
                      f"Set-Cookie 应逐字照合同，实际 {set_cookie!r}")
            if set_cookie:
                value = set_cookie.split("=", 1)[1].split(";", 1)[0]
                resp = raw_request(port, "GET", "/api/v1/ping",
                                   headers=[("Cookie", f"themis_session={value}")])
                grp.check(resp.status == 200, f"新会话应能访问 /api/v1/ping，实际 {resp.status}")
        resp = raw_request(port, "GET", "/", host=f"evil.example:{port}")
        pipe.sample("403-badhost", resp)
        labels = {label for label, _status, _headers in pipe.samples}
        for need in REQUIRED_SAMPLES:
            grp.check(need in labels, f"缺少 {need} 响应样本（对应阶段可能没跑到）")
        for label, status, headers in pipe.samples:
            problems = header_problems(label, headers)
            grp.check(not problems, f"{label}（{status}）：" + "；".join(problems))

    # ---- D06/D07 控制接口与限速 --------------------------------------------
    def check_control(grp):
        origin = f"http://127.0.0.1:{port}"
        token = state["token"]

        def ctrl(tok=token, org=origin):
            hdrs = [("Origin", org), ("X-Themis-UI", "1"), ("Content-Type", "application/json")]
            if tok is not None:
                hdrs.append(("X-Themis-Control", tok))
            return raw_request(port, "POST", "/control/bootstrap", headers=hdrs, body=b"{}")

        def new_bootstrap(resp, label):
            data = check_ok_envelope(grp, resp, label)
            if data is None:
                return None
            value = data.get("data")
            bs = value.get("bootstrap") if isinstance(value, dict) else None
            grp.check(isinstance(bs, str) and bs.startswith(f"http://127.0.0.1:{port}/bootstrap/"),
                      f"{label}：data.bootstrap 应是新的引导地址，实际 {bs!r}")
            return urlsplit(bs).path if isinstance(bs, str) else None

        resp = ctrl(tok=None)
        grp.check(resp.status == 403, f"控制接口不带令牌应 403，实际 {resp.status}")
        pipe.sample("403-control-no-token", resp)
        grp.check(ctrl(tok="wrong-token").status == 403, "控制接口令牌错应 403")
        cookie = f"themis_session={state['cookie_value']}" if state["cookie_value"] else None
        only_cookie = raw_request(port, "POST", "/control/bootstrap",
                                  headers=([("Cookie", cookie)] if cookie else []) +
                                  [("Origin", origin), ("X-Themis-UI", "1"),
                                   ("Content-Type", "application/json")], body=b"{}")
        grp.check(only_cookie.status == 403, f"只带会话 cookie 不带控制令牌应 403，实际 {only_cookie.status}")
        resp = ctrl()
        grp.check(resp.status == 200, f"对的令牌应 200，实际 {resp.status}")
        path = new_bootstrap(resp, "control-ok")
        if path:
            state["final_bootstrap_path"] = path
            resp = raw_request(port, "GET", "/api/v1/ping", headers=[("Cookie", cookie)] if cookie else [])
            grp.check(resp.status == 401, f"控制接口换过之后旧会话应 401，实际 {resp.status}")
            resp = raw_request(port, "GET", state["original_bootstrap_path"])
            grp.check(resp.status == 404, f"旧引导地址应 404，实际 {resp.status}")
            resp = raw_request(port, "GET", path)
            grp.check(resp.status == 302, f"新引导地址应可用，实际 {resp.status}")
            set_cookie = resp.get("set-cookie")
            if set_cookie:
                state["cookie_value"] = set_cookie.split("=", 1)[1].split(";", 1)[0]
        # Origin 是别的站点：403 且不计入限速
        for _index in range(6):
            resp = ctrl(org="https://evil.example")
            grp.check(resp.status == 403,
                      f"控制接口 Origin 是别的站点应 403，实际 {resp.status}")
        resp = ctrl()
        grp.check(resp.status == 200,
                  f"别的站点的 Origin 失败不应计入限速（6 次之后正确的令牌仍应 200），实际 {resp.status}")
        path = new_bootstrap(resp, "control-ok-after-foreign")
        if path:
            state["final_bootstrap_path"] = path
        # 连续 5 次失败之后锁 1 秒；锁定期内对的令牌也 429 且带 Retry-After
        for index in range(5):
            resp = ctrl(tok=f"wrong-{index}")
            grp.check(resp.status == 403, f"第 {index + 1} 次令牌失败应 403，实际 {resp.status}")
        resp = ctrl()
        grp.check(resp.status == 429, f"连续 5 次失败之后对的令牌也应 429，实际 {resp.status}")
        pipe.sample("429-control", resp)
        retry = resp.get("retry-after")
        grp.check(retry is not None and retry.strip().isdigit() and int(retry) >= 1,
                  f"429 应带 Retry-After（正整数），实际 {retry!r}")
        time.sleep(1.4)
        resp = ctrl()
        grp.check(resp.status == 200, f"锁定时长（1 秒）过后对的令牌应恢复 200，实际 {resp.status}")
        path = new_bootstrap(resp, "control-ok-after-lock")
        if path:
            state["final_bootstrap_path"] = path
        # 翻倍：再连续失败到第 5 次锁 1 秒，过期后第 6 次失败锁 2 秒
        for index in range(5):
            resp = ctrl(tok=f"wrong-b-{index}")
            grp.check(resp.status == 403, f"第 {index + 1} 次令牌失败应 403，实际 {resp.status}")
        time.sleep(1.4)
        resp = ctrl(tok="wrong-double")
        grp.check(resp.status == 403, f"锁过期后的失败应 403，实际 {resp.status}")
        time.sleep(1.4)
        resp = ctrl()
        grp.check(resp.status == 429,
                  f"锁定时长应翻倍（第二次锁定期内、1.4 秒时对的令牌仍应 429），实际 {resp.status}")
        time.sleep(1.2)
        resp = ctrl()
        grp.check(resp.status == 200, f"翻倍后的锁定期（2 秒）过后应恢复 200，实际 {resp.status}")
        path = new_bootstrap(resp, "control-ok-after-double")
        if path:
            state["final_bootstrap_path"] = path

    # ---- D03 两种拒绝走同一个响应 ------------------------------------------
    def check_rejection(grp):
        unknown = "/bootstrap/" + "z" * 43
        used = raw_request(port, "GET", state["original_bootstrap_path"])
        missing = raw_request(port, "GET", unknown)
        grp.check(used.status == 404 and missing.status == 404,
                  f"用过与不存在的引导地址都应 404，实际 {used.status}/{missing.status}")
        grp.check(used.body == missing.body,
                  f"用过与不存在的引导地址的正文应逐字节相同：{used.body!r} vs {missing.body!r}")
        head_used = {k.lower(): v for k, v in used.headers if k.lower() not in ("date", "connection")}
        head_missing = {k.lower(): v for k, v in missing.headers if k.lower() not in ("date", "connection")}
        grp.check(head_used == head_missing,
                  f"用过与不存在的引导地址的头（除 Date 与 Connection）应相同：{head_used} vs {head_missing}")

    # ---- D08 日志里没有令牌 ------------------------------------------------
    def check_logs(grp):
        lines = [line for line in main.stdout_text().splitlines() if line.strip()]
        grp.check(len(lines) == 1, f"stdout 应只有握手一行，实际 {len(lines)} 行：{main.stdout_text()[:400]!r}")
        secrets = [state["token"], state["cookie_value"], state["original_nonce"], canary, body_canary]
        stderr = main.stderr_text()
        rest = main.stdout_text().replace(main.handshake_line or "\x00", "", 1)
        for secret in secrets:
            if not secret:
                continue
            grp.check(secret not in stderr,
                      f"stderr 里不应出现控制令牌/会话 cookie/引导地址 nonce/正文金丝雀：{secret[:16]}…")
            grp.check(secret not in rest,
                      f"握手行之外的 stdout 里不应出现控制令牌/会话 cookie/引导地址 nonce/正文金丝雀：{secret[:16]}…")

    # ---- D14 用法错误与已有服务 --------------------------------------------
    def check_usage(grp):
        res = pipe.launch_brief(repo, assets, desktop=False)
        grp.check(not res.timed_out and res.code == 2, f"不带 --desktop 应退出 2，实际 {res.code}")
        grp.check(res.stderr.strip() == "ERROR: 管理台只由桌面应用启动",
                  f"提示应照 checkArgs 原文，实际 {res.stderr!r}")
        grp.check(res.stdout == "", f"stdout 应为空，实际 {res.stdout!r}")
        missing = pipe.tmp / "missing-assets-dir"
        res = pipe.launch_brief(repo, missing)
        grp.check(not res.timed_out and res.code == 2, f"找不到前端资源应退出 2，实际 {res.code}")
        grp.check(res.stderr.startswith("ERROR: 找不到前端资源目录：")
                  and "missing-assets-dir" in res.stderr,
                  f"提示应照 checkArgs 原文，实际 {res.stderr!r}")
        grp.check(res.stdout == "", f"stdout 应为空，实际 {res.stdout!r}")
        res = pipe.launch_brief(repo, assets, idle_timeout=0)
        grp.check(not res.timed_out and res.code == 2, f"--idle-timeout 0 应退出 2，实际 {res.code}")
        grp.check(res.stderr.startswith("ERROR: --idle-timeout 必须是正整数：0"),
                  f"提示应照 checkArgs 原文，实际 {res.stderr!r}")
        grp.check(res.stdout == "", f"stdout 应为空，实际 {res.stdout!r}")
        # 已有服务在运行：退出 1、stderr 报 pid 与端口、stdout 为空、原来的服务照常响应
        res = pipe.launch_brief(repo, assets)
        grp.check(not res.timed_out and res.code == 1, f"已有服务在运行时应退出 1，实际 {res.code}")
        grp.check(re.search(r"本仓库已有本机服务在运行（pid \d+，端口 \d+）", res.stderr) is not None,
                  f"被占时的提示应照原文（含 pid 与端口），实际 {res.stderr!r}")
        grp.check(str(main.proc.pid) in res.stderr and str(port) in res.stderr,
                  f"被占时的提示应报出 pid {main.proc.pid} 与端口 {port}，实际 {res.stderr!r}")
        grp.check(res.stdout == "", f"stdout 应为空，实际 {res.stdout!r}")
        resp = raw_request(port, "GET", "/")
        grp.check(resp.status == 200, f"原来的服务应照常响应，实际 {resp.status}")

    # ---- D15 生命周期与锁 --------------------------------------------------
    def check_lifecycle(grp):
        # 没有 owner.json 的锁目录「超过 10 秒」用真实等待证明，不用 os.utime 做旧：合同只写「锁目录建立
        # 不到/超过 10 秒」、没定判据，实现可能按 Windows 的 birthtime（“建立”的字面义）判龄，
        # 而 os.utime 改不了 birthtime，做旧会让正确实现反被 busy 判红。目录在这里先建好，等下面的用例
        # 一个个跑过去它自然就老了；到用时还不够 10 秒，就补一段真实的等待。
        repo_stale = pipe.tmp / "repo-stale"
        stale_lock = repo_stale / ".agent" / ".ui.lock"
        stale_lock.mkdir(parents=True, exist_ok=True)
        stale_born = time.monotonic()
        # --idle-timeout 1：stdin 一直开着，服务自己因空闲退出 0 且锁目录清除。先关 stdin 的话，退出 0
        # 可以完全归因 stdin EOF，空闲计时器彻底坏掉的实现照样通过（一审 B3）。
        repo_idle = pipe.tmp / "repo-idle"
        repo_idle.mkdir(exist_ok=True)
        svc = pipe.launch(repo_idle, assets, idle_timeout=1)
        if svc.handshake() is None:
            grp.check(False, f"--idle-timeout 1 的服务没有写出握手行：{svc.stderr_tail()}")
        else:
            code, timed_out = svc.wait(12)
            if timed_out:
                svc.kill()
                code, _ = svc.wait(10)
            grp.check(not timed_out and code == 0,
                      f"stdin 一直开着时 --idle-timeout 1 应自己空闲退出 0，"
                      f"实际 code={code} timed_out={timed_out}：{svc.stderr_tail()}")
            grp.check(not (repo_idle / ".agent" / ".ui.lock").exists(), "空闲退出后锁目录应被清除")
        # 有请求就推迟空闲退出
        repo_defer = pipe.tmp / "repo-defer"
        repo_defer.mkdir(exist_ok=True)
        svc = pipe.launch(repo_defer, assets, idle_timeout=3)
        data = svc.handshake()
        if data is None:
            grp.check(False, f"--idle-timeout 3 的服务没有写出握手行：{svc.stderr_tail()}")
        else:
            defer_port = urlsplit(data["origin"]).port
            start = time.monotonic()
            while time.monotonic() - start < 4.5:
                if svc.proc.poll() is not None:
                    break
                raw_request(defer_port, "GET", "/")
                time.sleep(0.6)
            grp.check(svc.proc.poll() is None, "每 0.6 秒一个请求时应一直推迟空闲退出（4.5 秒后仍应活着）")
            code, timed_out, killed = svc.stop(timeout=15)
            grp.check(not timed_out and not killed and code == 0,
                      f"请求停下之后应正常退出 0，实际 code={code} timed_out={timed_out}")
            grp.check(not (repo_defer / ".agent" / ".ui.lock").exists(), "退出后锁目录应被清除")
        # stdin 管道关闭（EOF）：退出 0、锁目录清除、stdout 仍只有握手一行
        repo_eof = pipe.tmp / "repo-eof"
        repo_eof.mkdir(exist_ok=True)
        svc = pipe.launch(repo_eof, assets)
        if svc.handshake() is None:
            grp.check(False, f"stdin EOF 用例的服务没有写出握手行：{svc.stderr_tail()}")
        else:
            svc.close_stdin()
            code, timed_out = svc.wait(20)
            grp.check(not timed_out and code == 0, f"stdin EOF 应退出 0，实际 code={code} timed_out={timed_out}")
            grp.check(not (repo_eof / ".agent" / ".ui.lock").exists(), "stdin EOF 退出后锁目录应被清除")
            lines = [line for line in svc.stdout_text().splitlines() if line.strip()]
            grp.check(len(lines) == 1, f"stdout 仍应只有握手一行，实际 {len(lines)} 行")

        def write_owner(target, payload):
            lock = target / ".agent" / ".ui.lock"
            lock.mkdir(parents=True, exist_ok=True)
            (lock / "owner.json").write_text(json.dumps(payload), encoding="utf-8")
            return lock

        def take_over(target, label):
            svc = pipe.launch(target, assets)
            data = svc.handshake()
            grp.check(data is not None, f"{label}：服务应能起来（接管锁），实际没有握手行：{svc.stderr_tail()}")
            if data is not None:
                code, timed_out, killed = svc.stop(timeout=15)
                grp.check(not timed_out and not killed and code == 0, f"{label}：退出码应为 0，实际 {code}")
                grp.check(not (target / ".agent" / ".ui.lock").exists(), f"{label}：退出后锁目录应被清除")

        # 锁里的 pid 已不在：接管
        repo_dead = pipe.tmp / "repo-dead"
        repo_dead.mkdir(exist_ok=True)
        dead = _dead_pid()
        write_owner(repo_dead, {"pid": dead, "port": 1, "token": "stale", "at": int(time.time() * 1000)})
        take_over(repo_dead, "锁里的 pid 已不在")
        # 持有者活着：busy
        repo_live = pipe.tmp / "repo-live"
        repo_live.mkdir(exist_ok=True)
        write_owner(repo_live, {"pid": os.getpid(), "port": 45999, "token": "live", "at": int(time.time() * 1000)})
        res = pipe.launch_brief(repo_live, assets)
        grp.check(not res.timed_out and res.code == 1, f"持有者活着时应退出 1，实际 {res.code}")
        grp.check(re.search(r"本仓库已有本机服务在运行（pid \d+，端口 \d+）", res.stderr) is not None,
                  f"持有者活着时的提示应照原文，实际 {res.stderr!r}")
        grp.check(str(os.getpid()) in res.stderr and "45999" in res.stderr,
                  f"提示里应报出 pid {os.getpid()} 与端口 45999，实际 {res.stderr!r}")
        grp.check(res.stdout == "", f"stdout 应为空，实际 {res.stdout!r}")
        # owner.json 缺失且锁目录不到 10 秒：busy（正在启动）
        repo_fresh = pipe.tmp / "repo-fresh"
        (repo_fresh / ".agent" / ".ui.lock").mkdir(parents=True, exist_ok=True)
        res = pipe.launch_brief(repo_fresh, assets)
        grp.check(not res.timed_out and res.code == 1, f"锁目录新建（无 owner.json）时应退出 1，实际 {res.code}")
        grp.check("本仓库已有本机服务正在启动（.agent/.ui.lock）" in res.stderr,
                  f"提示应照「正在启动」的原文，实际 {res.stderr!r}")
        # owner.json 缺失且锁目录真实地超过 10 秒：接管
        waited = stale_born + 11 - time.monotonic()
        if waited > 0:
            time.sleep(waited)
        take_over(repo_stale, "锁目录超过 10 秒且没有 owner.json")
        # 释放只删自己的锁
        repo_tamper = pipe.tmp / "repo-tamper"
        repo_tamper.mkdir(exist_ok=True)
        svc = pipe.launch(repo_tamper, assets)
        data = svc.handshake()
        if data is None:
            grp.check(False, f"锁令牌对不上的用例没有握手行：{svc.stderr_tail()}")
        else:
            owner = repo_tamper / ".agent" / ".ui.lock" / "owner.json"
            payload = json.loads(owner.read_text(encoding="utf-8"))
            payload["token"] = "someone-else"
            owner.write_text(json.dumps(payload), encoding="utf-8")
            code, timed_out, killed = svc.stop(timeout=15)
            grp.check(not timed_out and not killed and code == 0,
                      f"owner.json 令牌被换掉时关停仍应退出 0，实际 code={code}")
            grp.check((repo_tamper / ".agent" / ".ui.lock").exists(),
                      "释放只删自己的锁：owner.json 的令牌不是自己时锁目录不应被删")

    # ---- D15 经启动器再走一遍 stdin EOF -----------------------------------
    def check_launcher(grp):
        scratch = pipe.tmp / "launcher-repo"
        scratch.mkdir(exist_ok=True)
        done = subprocess.run(["git", "init", "-q", str(scratch)], capture_output=True, timeout=120)
        if done.returncode != 0:
            grp.check(False, f"git init 临时仓库失败：{done.stderr.decode('utf-8', 'replace')[:300]}")
            return
        argv = [sys.executable, str(REPO_ROOT / "scripts" / "pi_dispatch.py"), "--repo", str(scratch),
                "ui", "--desktop", "--assets", str(assets)]
        proc = subprocess.Popen(argv, cwd=str(REPO_ROOT), env=_ts_env(), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        svc = Service(proc, "launcher")
        pipe.services.append(svc)
        data = svc.handshake(timeout=60)
        if data is None:
            grp.check(False, f"经启动器起的服务应写出握手行（退出码 {proc.poll()}）：{svc.stderr_tail()}")
            svc.kill()
            return
        svc.close_stdin()
        code, timed_out = svc.wait(25)
        grp.check(not timed_out and code == 0,
                  f"关掉 stdin 之后启动器应退出 0，实际 code={code} timed_out={timed_out}：{svc.stderr_tail()}")
        grp.check(not (scratch / ".agent" / ".ui.lock").exists(), "经启动器退出后锁目录应被清除")
        lines = [line for line in svc.stdout_text().splitlines() if line.strip()]
        grp.check(len(lines) == 1, f"stdout 仍应只有握手一行，实际 {len(lines)} 行")

    phase(check_handshake, "handshake")
    phase(check_host, "host")
    phase(check_session, "session")
    phase(check_csrf, "csrf")
    phase(check_methods, "methods")
    phase(check_assets, "assets")
    phase(check_body, "body")
    phase(check_control, "control")
    phase(check_headers, "headers")
    phase(check_rejection, "rejection")
    phase(check_logs, "logs")
    phase(check_usage, "usage")
    phase(check_lifecycle, "lifecycle")
    phase(check_launcher, "launcher")


# ---------------------------------------------------------------------------
# 流水线用例
# ---------------------------------------------------------------------------

def _group(pipeline, name):
    assert pipeline.ran, pipeline.reason
    grp = pipeline.groups.get(name)
    assert grp is not None, f"检查组 {name} 没有建立：{pipeline.stopped_reason or '流水线没有跑到服务检查'}"
    assert not grp.problems, f"{name}：\n" + "\n".join(f"- {p}" for p in grp.problems[:20])
    return grp


def test_pipeline_handshake(pipeline):
    """D01：stdout 只有一行握手 JSON，字段与次序照合同，origin 是 http://127.0.0.1:<port>，只绑 127.0.0.1。"""
    _group(pipeline, "handshake")


def test_pipeline_host(pipeline):
    """D04：只认 127.0.0.1:<port> 与 localhost:<port>；其余 Host 一律 403；Host 不对时引导地址没被消耗。"""
    _group(pipeline, "host")


def test_pipeline_session(pipeline):
    """D02：401/404 逐字、Set-Cookie 逐字、引导地址只能用一次、/api/ 下不存在的路径 401/404。"""
    _group(pipeline, "session")


def test_pipeline_csrf(pipeline):
    """D05：缺 X-Themis-UI / Origin 不同或缺 / Content-Type 不是 JSON 分别 403、403、415，处理函数没运行。"""
    _group(pipeline, "csrf")


def test_pipeline_methods(pipeline):
    """D16：PUT、DELETE、OPTIONS、HEAD 都是 405，带 Allow: GET, POST。"""
    _group(pipeline, "methods")


def test_pipeline_assets(pipeline):
    """D09/D10：静态资源照白名单给 Content-Type；目录边界与只解码一次的负面路径都拿不到目录外的文件。"""
    _group(pipeline, "assets")


def test_pipeline_body(pipeline):
    """D11：65537 字节 413 且之后不再读、65536 字节收下、声明超限一个字节也不读、坏正文 400 不回显。"""
    _group(pipeline, "body")


def test_pipeline_headers(pipeline):
    """D12：各类响应都带 CSP、nosniff、no-referrer；API/引导/控制/错误带 no-store，静态带 no-cache；没有 Access-Control-*。"""
    _group(pipeline, "headers")


def test_pipeline_control(pipeline):
    """D06/D07：控制接口的 403/200 与新引导地址；失败限速（5 次锁 1 秒、翻倍、锁定期内 429 带 Retry-After、成功清零）。"""
    _group(pipeline, "control")


def test_pipeline_rejection(pipeline):
    """D03：用过与不存在的引导地址走同一个响应（状态、头除 Date、正文逐字节相同）。"""
    _group(pipeline, "rejection")


def test_pipeline_logs(pipeline):
    """D08：stdout 只有握手一行；stderr 与握手行之外的 stdout 里没有控制令牌、会话 cookie、nonce 与正文。"""
    _group(pipeline, "logs")


def test_pipeline_usage(pipeline):
    """D14：不带 --desktop、找不到前端资源、空闲时限不是正整数都退出 2 且提示原文、stdout 为空；已有服务在运行退出 1。"""
    _group(pipeline, "usage")


def test_pipeline_lifecycle(pipeline):
    """D15：空闲退出与锁清除、有请求就推迟、stdin EOF、锁的接管与 busy、释放只删自己的锁。"""
    _group(pipeline, "lifecycle")


def test_pipeline_launcher(pipeline):
    """D15：经 pi_dispatch.py 起服务，stdout 只有握手一行；关掉 stdin 之后退出 0 且锁目录清除。"""
    _group(pipeline, "launcher")


def test_pipeline_vitest_contracts(pipeline):
    """D17（V02）：契约测试与源码卫生测试通过（localhttp 的导入规则由 source-hygiene 强制）。"""
    step = assert_step_ok(pipeline, "vitest-contracts")
    assert re.search(r"Tests\s+[1-9]\d* passed", step.out), f"V02 的输出应含 Tests N passed：\n{step.tail}"


def test_pipeline_tsc(pipeline):
    """D17（V05）：tsc -p tsconfig.json 通过（strict、noUncheckedIndexedAccess 等）。"""
    assert_step_ok(pipeline, "tsc")


def test_pipeline_scope(pipeline):
    """D17：流水线（bun install、起服务、V02、tsc）前后的 git status 差集里没有落在允许范围之外的改动。

    只证「门禁与流水线没弄脏树、也没弄丢东西」：允许范围是合同 allowed 的 ts/packages/ui/ 加门禁自己的
    文件与内核的变异清单目录。别片的改动在集成时已经提交，git status 看不见，所以差集断言不会像全树绝对
    范围断言那样必红；执行期的范围由合同 V07 管。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None, "流水线没有记录 git status"
    problems = []
    for label, diff in (("之后多出", pipeline.status_after - pipeline.status_before),
                        ("之后少了", pipeline.status_before - pipeline.status_after)):
        for entry in sorted(diff):
            path = status_path(entry)
            if path == GATE_FILE_REL or path.startswith(SCOPE_ALLOWED_PREFIXES):
                continue
            problems.append(f"流水线运行{label}允许范围之外的改动：{entry!r}")
    fail_if(problems, "流水线前后的改动范围（D17）")
