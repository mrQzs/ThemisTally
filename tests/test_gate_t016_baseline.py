"""T016 战前门禁：桌面端本机服务第 2 片（读路由与二道脱敏白名单，D1-C 前半）的黑盒基准测试
（合同 t016-desktop-ui-read.v1，plan_version 1，基线 528d7eade5）。

被测对象是 ``ts/packages/ui`` 的第 2 片：19 条只读数据路由（每条起一个内核子进程）、子进程执行器（并发上限 4、
FIFO 队列 16、每条路由的时限、断开与关停取消、系统临时目录、输出上限）、响应先过 redactJson 再按路由登记的白名单
做约束校验、file 路由的随机不透明句柄，以及第 1 片复核留下的 T17（会话默认必须验证）、T18（静态资源只读普通文件）、
T19（防 pid 复用）。

基线（528d7ea）上六个新源文件（kernelenv、kernel、kernelenvelope、redaction、readroutes、cursors）与配套测试都
不存在，routes/app/static/lockdir/server 也还是第 1 片的形状，所以本文件的失败落在「文件不存在」或「合同点名的
标记不在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有仓库文件的读取都发生在用例函数里；
流水线（真的起 Bun 服务、发 HTTP 请求）放在 ``pipeline`` 会话级夹具里，候选里还没有新源文件时不装依赖、不起服务。

结构（编号对应合同 DoD 的 D01–D17；合同 M1–M21 的抓住靠这些断言加执行端被锁定的白盒用例，战后门禁另出变异清单）：

- 静态断言（不用流水线，全量 pytest 也跑）：
  - 六个新源文件在位、且都能从 main.ts 顺 import 到达（D05/D17，接进产品才算实现）；
  - routes.ts 的 public 标记只落在 bootstrap 与 control.bootstrap 上、app.ts 先 findRoute 再验会话、会话排在
    CSRF 之前、/api/ 下不存在的路径 401（D01/T17，M15）；
  - static.ts 的 not-a-file 与可注入的 stat、原有 14 个 reason 一条不少（D02/T18，M16）；
  - lockdir.ts 的 async acquireUiLock、probePort 注入、四种探测结果、server.ts 的 await（D03/T19，M17）；
  - kernelenv.ts 去掉 TYPESAFE_API_KEY（大写比较）、CODEKIT_ACTOR=user-ui、NoDefaultCurrentDirectoryInExePath、
    不加 PYTHONUTF8（除非 README 注明偏离 kernel_env）（D04/T5/T20，M18/M19）；
  - readroutes.ts 的 19 条路由（名字、路径、时限 15/30/60/120、argv 片段）、meta 的 version/repo_name、
    合成 /secrets 的编排（D05/D12/D13）；
  - kernelenvelope.ts 的七字段、messages 只留 ERROR/WARN 且过 redactSecrets、command 的 <cursor>/<transcript>、
    data 用 pyjson dumps(ensureAscii:false, indent:2)（D06，M5/M20）；
  - redaction.ts 的白名单与约束（allowEnvName/allowEnum/allowId/usedByShape、枚举值逐字）（D07，M1/M2/M3）；
  - kernel.ts 的 runSupervised（handleSignals:false、grace:2）、mkdtemp 的 themis-ui- 前缀、503/504 与超时信封
    原文、409 提示原文、server.ts 的 ServeOverrides 只增不减（D08/D09/D10）；
  - cursors.ts 的 randomToken 句柄、1024 容量、next_cursor（D11，M11/M12/M14）；
  - 合同锁定基准测试文件清单：12 个文件在位且要点齐备（19 条路由名进 routes-auth 与 kernel-runner、
    static-paths 追加 not-a-file、lockdir 追加探端口三条、kernel-env 三问、fake-kernel 替身、harness 的
    python/kernel 可覆盖），ui 测试目录里没有 skip/only/todo（D01–D17 各条的白盒用例，M1–M21 的红）；
  - README 的结构表、状态码（409/503+Retry-After/504）、已知限制、决策 key 的 config secret check 口径与
    原因（D16）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：bun install（必要时）→ 照
  启动器的同一条路起真的服务 → 19 条读路由不带 cookie 一律 401（D01）、/api/ 下不存在的路径 401/404、引导地址
  拿会话之后 meta 端到端（信封七字段、data 的 version/repo_name、安全头与 no-store，D06/D13/D14）、参数不合格
  400 且不起子进程（M21）、伪造句柄 409（D11）。

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

# 合同 Steps：六个新源文件（读路由与执行器的那一片）
NEW_SRC_RELS = (
    "ts/packages/ui/src/kernelenv.ts",
    "ts/packages/ui/src/kernel.ts",
    "ts/packages/ui/src/kernelenvelope.ts",
    "ts/packages/ui/src/redaction.ts",
    "ts/packages/ui/src/readroutes.ts",
    "ts/packages/ui/src/cursors.ts",
)
# 本片要改的既有源文件（对照合同 allowed_modified_files）
MODIFIED_SRC_RELS = (
    "ts/packages/ui/src/routes.ts",
    "ts/packages/ui/src/app.ts",
    "ts/packages/ui/src/static.ts",
    "ts/packages/ui/src/lockdir.ts",
    "ts/packages/ui/src/server.ts",
)

# 合同 Behavior contract 的路由表：19 条读路由（名字、示例路径、时限秒）。一条不多一条不少。
READ_ROUTES = (
    ("api.meta.get", "/api/v1/meta", 15),
    ("api.status.get", "/api/v1/status", 30),
    ("api.attempts.list", "/api/v1/attempts", 30),
    ("api.attempts.show", "/api/v1/attempts/demo-task/attempt-001", 30),
    ("api.attempts.file", "/api/v1/attempts/demo-task/attempt-001/file?path=a%2Fb.txt", 60),
    ("api.usage.get", "/api/v1/usage", 120),
    ("api.config.get", "/api/v1/config", 30),
    ("api.config.validate", "/api/v1/config/validate", 30),
    ("api.config.history.list", "/api/v1/config/history", 30),
    ("api.config.history.show", "/api/v1/config/history/1", 30),
    ("api.roles.get", "/api/v1/roles", 30),
    ("api.profiles.get", "/api/v1/profiles", 30),
    ("api.presets.list", "/api/v1/presets", 30),
    ("api.presets.diff", "/api/v1/presets/base/diff/alt", 30),
    ("api.runtimes.get", "/api/v1/runtimes", 30),
    ("api.plugins.list", "/api/v1/plugins", 30),
    ("api.plugins.show", "/api/v1/plugins/example-plugin", 30),
    ("api.secrets.list", "/api/v1/secrets", 120),
    ("api.secrets.show", "/api/v1/secrets/EXAMPLE_KEY", 30),
)
# 路由表里出现的路径字面量（实现里写成路径模式，字面前缀必须能找到）
READ_PATH_FRAGMENTS = (
    "/api/v1/meta", "/api/v1/status", "/api/v1/attempts", "/api/v1/usage", "/api/v1/config/validate",
    "/api/v1/config/history", "/api/v1/roles", "/api/v1/profiles", "/api/v1/presets", "/diff/",
    "/api/v1/runtimes", "/api/v1/plugins", "/api/v1/secrets",
)
# argv 模板里的子命令与选项片段（合同路由表的 argv 模板列）。--repo 不在这里：合同把
# [python, kernel, "--repo", repo, ...argv] 的组装放在执行器 kernel.ts，readroutes.ts 只放各路由的 argv 模板。
ARGV_FRAGMENTS = (
    "--version", "--json", "status", "logs", "list", "show", "cat", "usage", "config",
    "validate", "history", "role", "profile", "preset", "diff", "runtime", "plugins", "secret",
    "check", "--task", "--cursor", "--transcript",
)

# 合同 Behavior contract：信封七个字段与次序（第 1 片 envelope.ts 已定，本片的 kernelenvelope 照它）
ENVELOPE_KEYS = ["ok", "exit_code", "data", "output", "messages", "command", "elapsed_ms"]
# 合同 T015 的静态 reason（14 个一条不少）加本片的 not-a-file
STATIC_REASONS = ("dot-segment", "encoded-dot-or-separator", "backslash", "drive-letter", "empty-segment",
                  "colon", "trailing-dot-or-space", "bad-encoding", "control-char", "reparse-point",
                  "outside-root", "directory", "type-not-allowed", "not-found")
# 合同 Behavior contract：超时信封的 messages 原文与 file 路由 409 的提示原文
TIMEOUT_MSG_TAIL = "），子进程已结束；请改用 CLI 查看"
TIMEOUT_MSG_HEAD = "命令超时（"
CURSOR_409_MESSAGE = "游标无效或文件已变化，请从头读取"
# 合同 D4：CSP 逐字（第 1 片的同一串，本片读路由的安全头照它，D14）
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")

# 合同 Steps 锁定的基准测试文件（执行端不许删改既有用例；新文件按合同要点写）
LOCKED_TEST_RELS = (
    "ts/packages/ui/test/routes-auth.test.ts",
    "ts/packages/ui/test/kernel-env.test.ts",
    "ts/packages/ui/test/kernel-runner.test.ts",
    "ts/packages/ui/test/kernel-real.test.ts",
    "ts/packages/ui/test/redaction.test.ts",
    "ts/packages/ui/test/redaction-routes.test.ts",
    "ts/packages/ui/test/cursors.test.ts",
    "ts/packages/ui/test/argv-templates.test.ts",
    "ts/packages/ui/test/fixtures/fake-kernel.mjs",
)

ASSUMPTIONS = (
    "「六个新源文件都能从 main.ts 顺 import 到达」按 T015 同一规矩的自查实现：顺着仓库内相对 import 走（.ts 后缀与 index 都认）",
    "public 标记的静态断言按「routes.ts 里 public: true 恰好两处、且都落在 bootstrap 与 control.bootstrap 的对象字面量里、读路由表一处也没有」判；逐条行为的验证在被锁定的 routes-auth.test.ts 里",
    "app.ts 的管线次序按文本位置判：findRoute 的调用点在会话检查（readSessionCookie/sessions.valid）之前、会话检查在 csrfCheck 之前；逐请求的行为由流水线黑盒与 routes-auth.test.ts 钉住",
    "时限的静态断言只要求 15/30/60/120 四个数都出现在 readroutes.ts（哪条路由配哪个数由被锁定的 kernel-runner.test.ts 每路由用例钉住）",
    "并发上限 4、队列 16、Retry-After: 2、输出上限 32 MiB/1 MiB 的数值不在本文件静态断言（写法太多样，容易误伤）：它们由被锁定的 kernel-runner.test.ts（U28、503、超限）与战后变异清单钉住",
    "黑盒流水线只起一次服务、走启动器同一条路（bun --no-env-file --config=ts/bunfig.toml cli 入口 --pyargs-b64），python 用跑 pytest 的这个解释器、kernel 用 scripts/pi_dispatch.py；仓库用系统临时目录里的普通目录（--version 不需要 git 仓库，锁只往里写 .agent/.ui.lock）",
    "meta 端到端只断言 data.version 是去掉末尾换行的非空字符串、data.repo_name 是仓库目录名（版本号本身由内核定，不写死）",
    "409 的提示按 errorResponse 的形状断言 messages 恰是一行「ERROR: 游标无效或文件已变化，请从头读取」",
)

# 流水线预算：合同 G01 的超时是 600 秒，留出静态用例与 pytest 自身的开销。
PIPELINE_BUDGET = 540
STEP_CAPS = {"bun install": 240, "service checks": 200}

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


#: 行注释与块注释在同一次从左往右的扫描里认：先出现的那一种算数（与 T006 门禁同一写法，见 7fafe2f）。原来先删块注释、
#: 再删行注释，行注释里的 `/*`（例如 `src/mock/*.json`）会被当成块注释的开头，一直吞到后面某个 `*/`。
#: 冒号、引号或反引号紧跟的 `//` 不算行注释（网址、以 // 开头的字符串），与原来相同。
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def _argv_written(code, *parts):
    """argv 模板片段在不在：连写（``config show``）或相邻的数组元素（``"config", "show"``）都算。"""
    if " ".join(parts) in code:
        return True
    for quote in ('"', "'"):
        elems = ("," + r"\s*").join(quote + re.escape(part) + quote for part in parts)
        if re.search(elems, code) is not None:
            return True
    return False


def _harness_overridable(code, field):
    """harness 的启动项真能覆盖 python/kernel：pyargs 的取值要来自 StartOptions（形如 ``options.python``
    的属性访问，参数叫什么名都认；或 ``python ?? 兜底``）。基线 harness.ts 把它们写死（``python: process.execPath`` /
    ``kernel: "pi_dispatch.py"``），两种形态都匹配不上——这条断言在基线是红的，不接覆盖线的候选也红。"""
    if re.search(rf"\w+\.{field}\b", code):
        return True
    return re.search(rf"\b{field}\s*\?\?", code) is not None


def new_src_union():
    """六个新源文件的去注释文本拼在一起（跨文件的合同要点用它找）。"""
    return "\n".join(strip_ts_comments(need_file(rel)) for rel in NEW_SRC_RELS)


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


# ---------------------------------------------------------------------------
# 静态断言：新源文件在位、接线、路由表、脱敏、执行器、句柄
# ---------------------------------------------------------------------------

def test_static_new_sources_in_place():
    """D05/D17：合同点名的六个新源文件都在位（基线上还没有实现）。"""
    missing = [rel for rel in NEW_SRC_RELS if not (REPO_ROOT / rel).is_file()]
    fail_if([f"{rel} 不存在（基线上还没有实现）" for rel in missing], "六个新源文件")


def test_static_import_graph():
    """D17：六个新源文件都能从 main.ts 顺 import 到达（写了却没接进产品的不算实现）。"""
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
    fail_if(problems, "src 接线（D17）")


def test_static_routes_public_flag():
    """D01/T17（M15）：Route 有 public?: true；public: true 恰好落在 bootstrap 与 control.bootstrap
    上，api.ping 两条与读路由表一处也没有。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/routes.ts"))
    problems = []
    if not re.search(r"public\?\s*:\s*true", code):
        problems.append("Route 接口应加 public?: true")
    for name in ("bootstrap", "control.bootstrap"):
        if not re.search(rf'name\s*:\s*"{re.escape(name)}"[\s\S]{{0,800}}?public\s*:\s*true', code):
            problems.append(f"路由 {name} 应标成 public")
    for name in ("api.ping.get", "api.ping.post"):
        if re.search(rf'name\s*:\s*"{re.escape(name)}"[\s\S]{{0,800}}?public\s*:\s*true', code):
            problems.append(f"路由 {name} 不应标成 public（ping 也要会话）")
    marks = re.findall(r"public\s*:\s*true", code)
    if len(marks) != 2:
        problems.append(f"routes.ts 里 public: true 应恰好两处（bootstrap 与 control.bootstrap），实际 {len(marks)} 处")
    fail_if(problems, "routes.ts 的 public 标记（D01/T17）")


def test_static_app_pipeline():
    """D01/T17（M15）：app.ts 先 findRoute 再验会话（public 不验、其余 /api/ 验），会话排在 CSRF 与读正文
    之前；没命中的 /api/ 路径 401、静态资源不验会话。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/app.ts"))
    problems = []
    i_route = code.find("findRoute(")
    i_session = code.find("readSessionCookie(")
    if i_session < 0:
        i_session = code.find("sessions.valid(")
    i_csrf = code.find("csrfCheck(")
    if i_route < 0:
        problems.append("app.ts 应调用 findRoute")
    elif i_session >= 0 and i_route > i_session:
        problems.append("app.ts 应先 findRoute 再验会话（public 路由不验、其余按路径判）")
    if i_session >= 0 and i_csrf >= 0 and i_session > i_csrf:
        problems.append("会话检查应排在 CSRF 与读正文之前")
    if not re.search(r"\.public\b|route\.public|\bpublic\b", code):
        problems.append("app.ts 应读路由的 public 标记")
    if '"/api/"' not in code and "'/api/'" not in code:
        problems.append("app.ts 应保留 /api/ 前缀判断（没命中的 /api/ 路径 401）")
    if "401" not in code:
        problems.append("app.ts 应保留 401（未认证）")
    fail_if(problems, "app.ts 管线（D01/T17）")


def test_static_not_a_file():
    """D02/T18（M16）：static.ts 在 stat 之后查 isFile，不是普通文件 404 且 reason 是 not-a-file，
    resolveAsset 有可注入的 stat；原有 14 个 reason 一条不少（目录仍是 directory）。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/static.ts"))
    problems = []
    for reason in STATIC_REASONS:
        if reason not in code:
            problems.append(f"static.ts 里原有的 reason「{reason}」不见了")
    if "not-a-file" not in code:
        problems.append("static.ts 应新增 reason「not-a-file」")
    if "isFile" not in code:
        problems.append("static.ts 应在 stat 之后查 isFile()")
    if not re.search(r"stat\?\s*:", code):
        problems.append("resolveAsset 应有可注入的 stat（形如 options?: {stat?: …}）")
    if "directory" not in code:
        problems.append("static.ts 应保留目录的 directory 判断")
    fail_if(problems, "静态资源只读普通文件（D02/T18）")


def test_static_lockdir_probe():
    """D03/T19（M17）：acquireUiLock 改成 async、探测函数可注入、四种探测结果都在；pid 活着且端口
    连不上（被拒）接管，连上了/超时/别的错误 busy running；server.ts 跟着 await。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/lockdir.ts"))
    problems = []
    if not re.search(r"export\s+async\s+function\s+acquireUiLock", code):
        problems.append("acquireUiLock 应改成 async")
    if not re.search(r"probePort\?\s*:", code):
        problems.append("AcquireOptions 应加可注入的 probePort")
    for outcome in ("refused", "connected", "timeout", "other"):
        if outcome not in code:
            problems.append(f"lockdir.ts 里看不到探测结果「{outcome}」")
    if "ECONNREFUSED" not in code:
        problems.append("lockdir.ts 应把连接被拒（ECONNREFUSED）判成 pid 被复用")
    for msg in ("本仓库已有本机服务在运行（pid", "本仓库已有本机服务正在启动（.agent/.ui.lock）",
                "无法确认 .agent/.ui.lock 的持有者（pid"):
        if msg not in code:
            problems.append(f"lockdir.ts 应保留提示原文：{msg}")
    server = strip_ts_comments(need_file("ts/packages/ui/src/server.ts"))
    if not re.search(r"await\s+acquireUiLock", server):
        problems.append("server.ts 应 await acquireUiLock")
    fail_if(problems, "防 pid 复用（D03/T19）")


def test_static_kernelenv():
    """D04/T5/T20（M18/M19）：子进程环境从 process.env 复制（按名字排序）、名字大写后等于
    TYPESAFE_API_KEY 的一律去掉（不给任何路由开例外）、CODEKIT_ACTOR=user-ui、
    NoDefaultCurrentDirectoryInExePath 保留（Windows 上没有就补）；不加 PYTHONUTF8（除非 README
    注明它偏离 kernel_env）。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/kernelenv.ts"))
    problems = []
    if "process.env" not in code:
        problems.append("kernelenv.ts 应从 process.env 复制环境")
    if "TYPESAFE_API_KEY" not in code:
        problems.append("kernelenv.ts 应去掉名字大写后等于 TYPESAFE_API_KEY 的变量")
    if "toUpperCase" not in code:
        problems.append("比较应按名字 toUpperCase()（大小写不同的写法也要去掉）")
    if not re.search(r"CODEKIT_ACTOR", code) or "user-ui" not in code:
        problems.append("kernelenv.ts 应设 CODEKIT_ACTOR=user-ui")
    if "NoDefaultCurrentDirectoryInExePath" not in code:
        problems.append("kernelenv.ts 应保留 NoDefaultCurrentDirectoryInExePath")
    if not re.search(r"\bsort\b", code):
        problems.append("kernelenv.ts 应按名字排序（次序稳定）")
    if re.search(r"PYTHONUTF8", code):
        readme = _read(UI_README)
        if "偏离 kernel_env" not in readme:
            problems.append("加了 PYTHONUTF8 就应在 README 注明它偏离 kernel_env")
    fail_if(problems, "子进程的环境（D04）")


def test_static_readroutes_table():
    """D05/D13：readroutes.ts 登记本片的 19 条读路由（名字、路径、时限 15/30/60/120、argv 模板片段），
    meta 的 data 合成 version 与 repo_name，位置参数的校验用到内核的正则。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/readroutes.ts"))
    problems = []
    for name, _path, _timeout in READ_ROUTES:
        if name not in code:
            problems.append(f"readroutes.ts 里看不到路由 {name}")
    for fragment in READ_PATH_FRAGMENTS:
        if fragment not in code:
            problems.append(f"readroutes.ts 里看不到路径「{fragment}」")
    for number in ("15", "30", "60", "120"):
        if not re.search(rf"(?<![\d.]){number}(?![\d.])", code):
            problems.append(f"readroutes.ts 里看不到时限 {number}（15/30/60/120 四档都要在）")
    for fragment in ARGV_FRAGMENTS:
        if fragment not in code:
            problems.append(f"readroutes.ts 里看不到 argv 片段「{fragment}」")
    if "repo_name" not in code or "version" not in code:
        problems.append("meta 的 data 应合成 {version, repo_name}")
    if "--version" not in code:
        problems.append("meta 应跑内核的 --version")
    fail_if(problems, "读路由表（D05/D13）")


def test_static_kernelenvelope():
    """D06（M5/M20）：信封七个字段与次序；messages 只留 stderr 里 ERROR/WARN 开头的行并逐行过
    redactSecrets；command 是显示用的 argv（游标 <cursor>、transcript <transcript>）；data 用 pyjson 的
    dumps(ensureAscii:false, indent:2) 写出。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/kernelenvelope.ts"))
    problems = []
    for field in ENVELOPE_KEYS:
        if not re.search(rf"\b{field}\b", code):
            problems.append(f"kernelenvelope.ts 里看不到字段 {field}")
    if "ERROR" not in code or "WARN" not in code:
        problems.append("messages 只留 stderr 里 ERROR/WARN 开头的行")
    if "redactSecrets" not in code:
        problems.append("kernelenvelope.ts 应把文本过 redactSecrets")
    if "<cursor>" not in code:
        problems.append("command 里游标应显示成 <cursor>")
    if "<transcript>" not in code:
        problems.append("command 里 transcript 应显示成 <transcript>")
    if "ensureAscii" not in code:
        problems.append("data 应用 pyjson 的 dumps(ensureAscii:false) 写出")
    if not re.search(r"indent\s*[:=]\s*2", code):
        problems.append("data 应用 pyjson 的 dumps(indent:2) 写出")
    if "loads" not in code:
        problems.append("--json 命令的 stdout 应用 pyjson 的 loads 解析")
    fail_if(problems, "信封（D06）")


def test_static_redaction():
    """D07（M1/M2/M3）：redaction.ts 按路由登记白名单——allowEnvName、allowEnum、allowId、usedByShape；
    枚举值逐字照内核（source 与 store_mode、system_backend 的取值）；证据（file 路由）不登记白名单。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/redaction.ts"))
    problems = []
    for token in ("allowEnvName", "allowEnum", "allowId", "usedByShape"):
        if token not in code:
            problems.append(f"redaction.ts 里看不到 {token}")
    for literal in ("credential_env", "env_var_name", "used_by", "credential_store",
                    "windows-credential-manager"):
        if literal not in code:
            problems.append(f"redaction.ts 里看不到白名单涉及的「{literal}」")
    for literal in ('"env"', '"none"', '"system"', '"off"', '"file"'):
        if literal not in code:
            problems.append(f"redaction.ts 里看不到枚举值 {literal}")
    if "profiles" not in code:
        problems.append("redaction.ts 应有 /profiles 的 credential_env 白名单")
    fail_if(problems, "二道脱敏与白名单（D07）")


def test_static_kernel_runner():
    """D08/D09/D10：执行器组装 [python, kernel, "--repo", repo, ...argv]、调 runSupervised
    （handleSignals:false、grace:2、timeout 取路由时限）、并发上限
    与队列、临时目录在系统临时目录下 themis-ui- 前缀的 mkdtemp 根里；503 带 Retry-After、504 带超时信封
    （原文）、file 路由的 409 提示原文；server.ts 的 ServeOverrides 只增不减（maxConcurrent、maxQueue、
    时限覆盖只给测试入口）并接上 extraRoutes。"""
    kernel = strip_ts_comments(need_file("ts/packages/ui/src/kernel.ts"))
    problems = []
    if "runSupervised" not in kernel:
        problems.append("kernel.ts 应调 @themis/base 的 runSupervised")
    if not re.search(r"handleSignals\s*:\s*false", kernel):
        problems.append("runSupervised 应传 handleSignals: false")
    if not re.search(r"grace\s*:\s*2\b", kernel):
        problems.append("runSupervised 的 grace 应是 2 秒")
    if "timeout" not in kernel:
        problems.append("执行器应把路由时限传给 runSupervised 的 timeout")
    if "--repo" not in kernel:
        problems.append('执行器应组装 [python, kernel, "--repo", repo, ...argv]（--repo 由 kernel.ts 拼，'
                        "不在 readroutes.ts 的路由模板里）")
    if "mkdtemp" not in kernel:
        problems.append("临时目录应用 mkdtemp")
    if "themis-ui-" not in kernel:
        problems.append("服务私有的临时根目录应用 themis-ui- 前缀")
    if "signal" not in kernel.lower():
        problems.append("取消应经手工合成的 signal（请求的 signal 与服务关停的 controller）")
    union = new_src_union()
    if "503" not in union:
        problems.append("队列满或服务正在关闭应回 503")
    if not re.search(r"[Rr]etry-[Aa]fter", union):
        problems.append("503 应带 Retry-After 头")
    if "504" not in union:
        problems.append("命令超时应回 504")
    if TIMEOUT_MSG_HEAD not in union or TIMEOUT_MSG_TAIL not in union:
        problems.append(f"超时信封的 messages 应只有一行「ERROR: {TIMEOUT_MSG_HEAD}N 秒{TIMEOUT_MSG_TAIL}」")
    if CURSOR_409_MESSAGE not in union:
        problems.append(f"file 路由的 409 提示应照原文「{CURSOR_409_MESSAGE}」")
    server = strip_ts_comments(need_file("ts/packages/ui/src/server.ts"))
    for token in ("maxConcurrent", "maxQueue"):
        if token not in server:
            problems.append(f"ServeOverrides 应有 {token}（只给测试入口，CLI 与环境变量碰不到）")
    if "extraRoutes" not in server:
        problems.append("server.ts 应把读路由表接进 createApp 的 extraRoutes")
    fail_if(problems, "执行器与错误映射（D08/D09/D10）")


def test_static_cursors():
    """D11（M11/M12/M14）：cursors.ts 的句柄用 randomToken（不含内核游标）、容量 1024 按最近使用淘汰、
    next_cursor 换成句柄、表项绑定 task/attempt/path/cursor。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/cursors.ts"))
    problems = []
    if "randomToken" not in code:
        problems.append("句柄应用 localhttp/tokens 的 randomToken（32 字节 base64url，43 个字符）")
    if not re.search(r"(?<![\d.])1024(?![\d.])", code):
        problems.append("句柄表最多 1024 项（超容量淘汰最旧的一个）")
    union = new_src_union()
    if "next_cursor" not in union:
        problems.append("响应的 next_cursor 应换成句柄（没有下一页时是 null）")
    for token in ("task", "attempt", "path", "cursor"):
        if token not in code:
            problems.append(f"表项应绑定 {token}")
    if "Map" not in code:
        problems.append("句柄表只在内存里（Map），服务退出全部失效")
    fail_if(problems, "file 路由的句柄（D11）")


def test_static_secrets_synthesis():
    """D12：合成的 /secrets 先跑 config show --json 与 config profile show --json 取名单，再逐条串行跑
    config secret check；每项 {name, source, store_mode, system_backend, used_by}（不带 file_dir）。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/readroutes.ts"))
    problems = []
    for parts in (("config", "show"), ("config", "profile", "show"), ("config", "secret", "check")):
        if not _argv_written(code, *parts):
            problems.append(f"合成的 /secrets 应跑「{' '.join(parts)}」")
    if "used_by" not in code and "used_by" not in strip_ts_comments(need_file("ts/packages/ui/src/redaction.ts")):
        problems.append("每项应有 used_by（decisions 在前，随后按 profile 次序）")
    if not re.search(r"decisions", code):
        problems.append("名单应先收 decisions 的名字（decisions.api_key_env）")
    fail_if(problems, "合成的 /secrets（D12）")


def test_static_param_regexes():
    """M21 的静态一半：位置参数的校验用内核的正则（TASK_ID_RE、ENV_NAME_RE、attempt 的 3 位以上编号、
    history 的编号、插件 id），选项的值一律写成 --opt=值。"""
    union = new_src_union()
    problems = []
    if "TASK_ID_RE" not in union:
        problems.append("task 与方案名的校验应过 TASK_ID_RE")
    if "ENV_NAME_RE" not in union:
        problems.append("凭据名的校验应过 ENV_NAME_RE")
    if not re.search(r"attempt-(?:\\d|\[0-9\])\{3,\}", union):
        problems.append("attempt 应过 ^attempt-[0-9]{3,}$")
    if not re.search(r"\[1-9\]", union):
        problems.append("history 编号应过 ^[1-9][0-9]{0,8}$")
    if not re.search(r"a-z0-9-", union):
        problems.append("插件 id 应过 ^[a-z][a-z0-9-]{0,63}$")
    fail_if(problems, "参数校验（M21）")


# ---------------------------------------------------------------------------
# 静态断言：基准测试文件锁定（合同 Steps 的清单）
# ---------------------------------------------------------------------------

def _no_skip_marks(text):
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
        if re.search(bad, text):
            problems.append(f"出现 {bad}（不许 skip、only、todo）")
    return problems


def test_static_locked_test_files():
    """D01–D17 的白盒用例都在位且要点齐备（合同 Steps 锁定的基准测试文件清单，执行端不许删改既有用例）。"""
    problems = []
    for rel in LOCKED_TEST_RELS:
        if not (REPO_ROOT / rel).is_file():
            problems.append(f"{rel} 不存在（合同 Steps 锁定的基准测试文件）")
    if problems:
        fail_if(problems, "基准测试文件在位")
        return

    # routes-auth：19 条读路由一张表、不带 cookie 一律 401
    auth = strip_ts_comments(_read(REPO_ROOT / "ts/packages/ui/test/routes-auth.test.ts"))
    for name, _path, _timeout in READ_ROUTES:
        if name not in auth:
            problems.append(f"routes-auth.test.ts 的「路由名 → 示例路径」表少了 {name}（19 条一条不少）")
    if "401" not in auth:
        problems.append("routes-auth.test.ts 应断言不带 cookie 一律 401")
    problems += [f"routes-auth.test.ts：{p}" for p in _no_skip_marks(auth)]

    # static-paths：追加 not-a-file 一条，原有 14 个 reason 的用例不删
    static_test = strip_ts_comments(_read(REPO_ROOT / "ts/packages/ui/test/static-paths.test.ts"))
    for reason in STATIC_REASONS:
        if reason not in static_test:
            problems.append(f"static-paths.test.ts 里原有的 reason「{reason}」不见了")
    if "not-a-file" not in static_test:
        problems.append("static-paths.test.ts 应追加 not-a-file 一条")
    problems += [f"static-paths.test.ts：{p}" for p in _no_skip_marks(static_test)]

    # lockdir：追加探端口三条，原有用例不删
    lockdir_test = strip_ts_comments(_read(REPO_ROOT / "ts/packages/ui/test/lockdir.test.ts"))
    for token in ("probePort", "refused", "connected", "timeout"):
        if token not in lockdir_test:
            problems.append(f"lockdir.test.ts 应有探端口用例（{token}）")
    for msg in ("本仓库已有本机服务在运行（pid", "本仓库已有本机服务正在启动（.agent/.ui.lock）",
                "无法确认 .ui.lock 的持有者"):
        if msg not in lockdir_test:
            problems.append(f"lockdir.test.ts 应保留被占提示的用例：{msg}")
    problems += [f"lockdir.test.ts：{p}" for p in _no_skip_marks(lockdir_test)]

    # kernel-env：替身只报告三问，钉住每一个内核子进程
    env_test = strip_ts_comments(_read(REPO_ROOT / "ts/packages/ui/test/kernel-env.test.ts"))
    for token in ("TYPESAFE_API_KEY", "CODEKIT_ACTOR", "user-ui", "NoDefaultCurrentDirectoryInExePath"):
        if token not in env_test:
            problems.append(f"kernel-env.test.ts 里看不到「{token}」")
    problems += [f"kernel-env.test.ts：{p}" for p in _no_skip_marks(env_test)]

    # kernel-runner：每条路由一条替身用例（argv、时限、错误映射）+ 并发/队列/503/超时/取消/超限
    runner = strip_ts_comments(_read(REPO_ROOT / "ts/packages/ui/test/kernel-runner.test.ts"))
    for name, _path, _timeout in READ_ROUTES:
        if name not in runner:
            problems.append(f"kernel-runner.test.ts 少了 {name} 的替身用例（每条路由一条）")
    for token in ("503", "504"):
        if token not in runner:
            problems.append(f"kernel-runner.test.ts 应有 {token} 的用例")
    if not re.search(r"[Rr]etry-[Aa]fter", runner):
        problems.append("kernel-runner.test.ts 应断言 503 带 Retry-After")
    if not re.search(r"取消|abort", runner):
        problems.append("kernel-runner.test.ts 应有断开/关停取消的用例")
    if not re.search(r"并发|maxConcurrent|concurren", runner):
        problems.append("kernel-runner.test.ts 应有并发上限与排队的用例")
    if not re.search(r"超限|32|限制|limit", runner):
        problems.append("kernel-runner.test.ts 应有输出超限的用例")
    problems += [f"kernel-runner.test.ts：{p}" for p in _no_skip_marks(runner)]

    # redaction（U22）与 redaction-routes（U5）
    redaction = strip_ts_comments(_read(REPO_ROOT / "ts/packages/ui/test/redaction.test.ts"))
    for token in ("credential_env", "used_by"):
        if token not in redaction:
            problems.append(f"redaction.test.ts 里看不到「{token}」")
    if "<redacted>" not in redaction:
        problems.append("redaction.test.ts 应断言不合约束的值被遮成 <redacted>")
    problems += [f"redaction.test.ts：{p}" for p in _no_skip_marks(redaction)]
    routes_red = strip_ts_comments(_read(REPO_ROOT / "ts/packages/ui/test/redaction-routes.test.ts"))
    if "WARN" not in routes_red:
        problems.append("redaction-routes.test.ts 应断言 messages 只留 ERROR/WARN 开头的行")
    if not re.search(r"证据|file", routes_red):
        problems.append("redaction-routes.test.ts 应有 file 路由（证据）不受白名单影响的用例")
    problems += [f"redaction-routes.test.ts：{p}" for p in _no_skip_marks(routes_red)]

    # cursors（U14f）
    cursors = strip_ts_comments(_read(REPO_ROOT / "ts/packages/ui/test/cursors.test.ts"))
    for token in ("409", "next_cursor"):
        if token not in cursors:
            problems.append(f"cursors.test.ts 里看不到「{token}」")
    if not re.search(r"\{43\}", cursors):
        problems.append("cursors.test.ts 应断言句柄是 43 个字符")
    problems += [f"cursors.test.ts：{p}" for p in _no_skip_marks(cursors)]

    # argv-templates（U4：内核真正的解析器）
    argv_test = strip_ts_comments(_read(REPO_ROOT / "ts/packages/ui/test/argv-templates.test.ts"))
    for token in ("build_parser", "--json"):
        if token not in argv_test:
            problems.append(f"argv-templates.test.ts 里看不到「{token}」")
    problems += [f"argv-templates.test.ts：{p}" for p in _no_skip_marks(argv_test)]

    # kernel-real（U9：真内核、逐字节一致、超时结束整棵树）
    real = strip_ts_comments(_read(REPO_ROOT / "ts/packages/ui/test/kernel-real.test.ts"))
    if "pi_dispatch" not in real:
        problems.append("kernel-real.test.ts 应起真内核（scripts/pi_dispatch.py）")
    if "504" not in real:
        problems.append("kernel-real.test.ts 应有 file 路由超时的用例（504）")
    problems += [f"kernel-real.test.ts：{p}" for p in _no_skip_marks(real)]

    # fake-kernel 替身：只报告三问，不输出任何变量的值
    fake = _read(REPO_ROOT / "ts/packages/ui/test/fixtures/fake-kernel.mjs")
    for token in ("TYPESAFE_API_KEY", "CODEKIT_ACTOR", "NoDefaultCurrentDirectoryInExePath"):
        if token not in fake:
            problems.append(f"fake-kernel.mjs 里看不到「{token}」（替身要报告这三问）")
    fail_if(problems, "基准测试文件锁定")


def test_static_harness_overridable():
    """合同 Steps：harness.ts 追加替身接线（pyargs 的 python 与 kernel 从启动项取值、可覆盖；基线上是
    写死的，所以这条在基线必须红）；ui 的测试目录里没有 skip/only。"""
    harness = strip_ts_comments(need_file("ts/packages/ui/test/harness.ts"))
    problems = []
    for field in ("python", "kernel"):
        if not _harness_overridable(harness, field):
            problems.append(f"harness.ts 的 pyargs 应把 {field} 从启动项取值（options.{field} 或 {field} ?? 兜底）；"
                            f"基线把它写死，不接这条线替身（node 跑 fake-kernel.mjs）就指不过去")
    problems += [f"harness.ts：{p}" for p in _no_skip_marks(harness)]
    for path in sorted(UI_TEST.rglob("*.ts")):
        problems += [f"{path.name}：{p}" for p in _no_skip_marks(_read(path))]
    fail_if(problems, "harness 与测试目录（不许 skip/only/todo）")


def test_static_readme():
    """D16：README 写结构表、最小 API、状态码（409、503 带 Retry-After、504）、已知限制，并写明决策 key
    被去掉之后 /secrets 与 /config 显示的 source 不再是 env、以终端里 config secret check 为准与原因。"""
    text = need_file("ts/packages/ui/README.md")
    problems = []
    for needle in ("结构", "Retry-After", "409", "503", "504", "已知限制", "config secret check",
                   "TYPESAFE_API_KEY"):
        if needle not in text:
            problems.append(f"README 里看不到「{needle}」")
    if not (("开始菜单" in text) or ("资源管理器" in text)):
        problems.append("README 应写明原因：桌面应用从开始菜单或资源管理器起，环境来自登录时的用户与系统环境变量")
    if not re.search(r"以终端|终端里", text):
        problems.append("README 应写明权威口径是用户在自己的终端里跑 config secret check")
    if not re.search(r"不再|不会", text):
        problems.append("README 应写明这把 key 的 source 不再/不会是 env")
    fail_if(problems, "README（D16）")


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


def raw_request(port, method, target, headers=(), timeout=30):
    """发一个请求并读完整响应（Connection: close，一条连接一个请求）。"""
    lines = [f"{method} {target} HTTP/1.1", f"Host: 127.0.0.1:{port}", "Connection: close", "Accept: */*"]
    lines += [f"{key}: {value}" for key, value in headers]
    raw = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall(raw)
        return _read_response(sock, timeout)


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


class Pipeline:
    def __init__(self):
        self.ran = False
        self.reason = ""
        self.stopped_reason = ""
        self.bun = None
        self.services = []
        self.groups = {}
        self.results = {}

    def group(self, name):
        grp = Group(name)
        self.groups[name] = grp
        return grp

    def launch(self, repo, assets):
        """照启动器同一条路起服务：bun --no-env-file --config=ts/bunfig.toml cli 入口 --pyargs-b64。"""
        pyargs = {"command": ["ui"], "repo": str(repo), "desktop": True,
                  "assets": str(assets), "transcript": [], "idle_timeout": None,
                  "python": sys.executable, "kernel": str(REPO_ROOT / "scripts" / "pi_dispatch.py")}
        argv = [str(self.bun), "--no-env-file", "--config=%s" % (TS / "bunfig.toml"),
                str(TS / "packages" / "cli" / "src" / "main.ts"), "--pyargs-b64",
                base64.b64encode(json.dumps(pyargs).encode("utf-8")).decode("ascii")]
        proc = subprocess.Popen(argv, cwd=str(REPO_ROOT), env=_ts_env(), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        svc = Service(proc)
        self.services.append(svc)
        return svc


class Group:
    def __init__(self, name):
        self.name = name
        self.problems = []

    def check(self, cond, msg):
        if not cond:
            self.problems.append(msg)
        return bool(cond)


@pytest.fixture(scope="session")
def pipeline(tmp_path_factory):
    pipe = Pipeline()
    if not all((REPO_ROOT / rel).is_file() for rel in NEW_SRC_RELS):
        pipe.reason = ("候选里还没有六个新源文件（基线 528d7ea，本片功能还没实现），未安装依赖、未起服务；"
                       "执行端实现之后，流水线才会运行 bun install 与黑盒服务检查")
        return pipe
    bun = find_bun()
    if bun is None:
        pipe.reason = "PATH 上找不到 Bun（bun.exe 或 npm 的 bun.cmd 垫片旁边的 bun.exe）"
        return pipe
    pipe.bun = bun
    pipe.ran = True
    pipe.tmp = tmp_path_factory.mktemp("t016-gate")
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


def _run_service_checks(pipe, soft_deadline):
    tmp = pipe.tmp

    def group(name):
        return pipe.group(name)

    svc_dir = tmp / "svc"
    assets = svc_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "index.html").write_text("<!doctype html><title>T016</title>\n", encoding="utf-8")
    repo = tmp / "repo"
    repo.mkdir(exist_ok=True)

    state = {}

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

    main = pipe.launch(repo, assets)
    hs = main.handshake()
    if hs is None:
        why = f"主服务没有在 45 秒内写出握手行（退出码 {main.proc.poll()}）：{main.stderr_tail()}"
        for name in ("auth", "meta", "params"):
            group(name).check(False, why)
        main.kill()
        return
    try:
        port = urlsplit(hs["origin"]).port
        state["port"] = port
        state["bootstrap_path"] = urlsplit(hs["bootstrap"]).path
        state["cookie_value"] = None

        # ---- D01 会话默认必须验证 ------------------------------------------
        def check_auth(grp):
            # 19 条读路由不带 cookie 一律 401；/api/ 下不存在的路径 401；静态资源不验会话
            for name, path, _timeout in READ_ROUTES:
                resp = raw_request(port, "GET", path)
                grp.check(resp.status == 401, f"不带 cookie 访问 {name}（{path}）应 401，实际 {resp.status}")
            resp = raw_request(port, "GET", "/api/v1/nope")
            grp.check(resp.status == 401, f"/api/ 下不存在的路径不带会话应 401，实际 {resp.status}")
            envelope = _json(grp, resp, "401-noapi")
            if envelope is not None:
                grp.check(envelope.get("ok") is False
                          and isinstance(envelope.get("messages"), list)
                          and len(envelope["messages"]) == 1
                          and isinstance(envelope["messages"][0], str)
                          and envelope["messages"][0].startswith("ERROR: "),
                          f"401 应是服务自己的错误信封（一行 ERROR: …），实际 {envelope.get('messages')!r}")
            resp = raw_request(port, "GET", "/")
            grp.check(resp.status == 200, f"静态资源（/）不验会话应 200，实际 {resp.status}")
            # 引导地址拿会话
            resp = raw_request(port, "GET", state["bootstrap_path"])
            if not grp.check(resp.status == 302, f"引导地址应 302，实际 {resp.status}"):
                return
            set_cookie = resp.get("set-cookie")
            if grp.check(set_cookie is not None and "themis_session=" in (set_cookie or ""), "引导应发会话 cookie"):
                state["cookie_value"] = set_cookie.split("themis_session=", 1)[1].split(";", 1)[0]
            cookie = f"themis_session={state['cookie_value']}"
            resp = raw_request(port, "GET", "/api/v1/nope", headers=[("Cookie", cookie)])
            grp.check(resp.status == 404, f"/api/ 下不存在的路径有会话应 404，实际 {resp.status}")
            state["cookie"] = cookie

        # ---- D06/D13/D14 meta 端到端与安全头 ------------------------------
        def check_meta(grp):
            cookie = state.get("cookie")
            if not cookie:
                grp.check(False, "上一阶段没拿到会话，meta 端到端没跑")
                return
            resp = raw_request(port, "GET", "/api/v1/meta", headers=[("Cookie", cookie)])
            if not grp.check(resp.status == 200, f"带会话的 /api/v1/meta 应 200，实际 {resp.status}：{resp.body[:200]!r}"):
                return
            envelope = _json(grp, resp, "meta")
            if envelope is None:
                return
            grp.check(list(envelope.keys()) == ENVELOPE_KEYS,
                      f"信封七个字段与次序应为 {ENVELOPE_KEYS}，实际 {list(envelope.keys())}")
            grp.check(envelope.get("ok") is True, f"meta 的 ok 应为 true，实际 {envelope.get('ok')!r}")
            grp.check(envelope.get("exit_code") == 0, f"meta 的 exit_code 应是 0，实际 {envelope.get('exit_code')!r}")
            data = envelope.get("data")
            if grp.check(isinstance(data, dict), f"meta 的 data 应是对象，实际 {data!r}"):
                version = data.get("version")
                grp.check(isinstance(version, str) and version != "" and "\n" not in version,
                          f"meta 的 version 应是 --version 的 stdout 去掉末尾换行，实际 {version!r}")
                grp.check(data.get("repo_name") == repo.name,
                          f"meta 的 repo_name 应是仓库目录名 {repo.name!r}，实际 {data.get('repo_name')!r}")
            grp.check(envelope.get("output") == [], "本片不把 stdout 原样回传（output 是空数组）")
            grp.check(envelope.get("command") == ["--version"],
                      f"meta 的 command 应只有显示用的 --version，实际 {envelope.get('command')!r}")
            # D14 安全头与 no-store；不开 CORS
            problems = _header_problems(resp)
            grp.check(not problems, "meta 响应的安全头：" + "；".join(problems))

        # ---- M21 参数校验与 D11 伪造句柄 ----------------------------------
        def check_params(grp):
            cookie = state.get("cookie")
            if not cookie:
                grp.check(False, "上一阶段没拿到会话，参数校验没跑")
                return
            base = [("Cookie", cookie)]
            bad_params = (
                ("task 不合 TASK_ID_RE", "/api/v1/attempts?task=-bad"),
                ("task 大写不合", "/api/v1/attempts?task=BAD_task"),
                ("attempt 编号不足三位", "/api/v1/attempts/demo-task/attempt-01"),
                ("path 以 - 开头", "/api/v1/attempts/demo-task/attempt-001/file?path=-x"),
                ("path 以 / 开头", "/api/v1/attempts/demo-task/attempt-001/file?path=/abs"),
                ("history 编号是 0", "/api/v1/config/history/0"),
                ("history 编号不是数字", "/api/v1/config/history/abc"),
                ("插件 id 大写", "/api/v1/plugins/Bad"),
                ("凭据名以数字开头", "/api/v1/secrets/9bad"),
            )
            for label, target in bad_params:
                resp = raw_request(port, "GET", target, headers=base)
                if grp.check(resp.status == 400, f"{label}（{target}）应 400，实际 {resp.status}"):
                    envelope = _json(grp, resp, label)
                    if envelope is not None:
                        grp.check(envelope.get("ok") is False and envelope.get("exit_code") is None,
                                  f"{label}：400 应是服务自己的错误信封（ok=false、exit_code=null），实际 "
                                  f"{envelope.get('ok')!r}/{envelope.get('exit_code')!r}")
            # 伪造的句柄（43 个字符，但不在表里）：409，不起子进程
            forged = "A" * 43
            resp = raw_request(port, "GET",
                               f"/api/v1/attempts/demo-task/attempt-001/file?path=a.txt&cursor={forged}",
                               headers=base)
            if grp.check(resp.status == 409, f"伪造的句柄应 409，实际 {resp.status}：{resp.body[:200]!r}"):
                envelope = _json(grp, resp, "forged-cursor")
                if envelope is not None:
                    grp.check(envelope.get("messages") == [f"ERROR: {CURSOR_409_MESSAGE}"],
                              f"409 的提示应照原文，实际 {envelope.get('messages')!r}")

        phase("auth", check_auth)
        phase("meta", check_meta)
        phase("params", check_params)
    finally:
        main.stop(timeout=15)


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


def _header_problems(resp):
    out = []

    def get(name):
        return resp.get(name)

    if get("content-security-policy") != CSP:
        out.append(f"CSP 应逐字照合同 D4，实际 {get('content-security-policy')!r}")
    if get("x-content-type-options") != "nosniff":
        out.append(f"X-Content-Type-Options 应是 nosniff，实际 {get('x-content-type-options')!r}")
    if get("referrer-policy") != "no-referrer":
        out.append(f"Referrer-Policy 应是 no-referrer，实际 {get('referrer-policy')!r}")
    if get("cache-control") != "no-store":
        out.append(f"读路由应带 Cache-Control: no-store，实际 {get('cache-control')!r}")
    for key, _value in resp.headers:
        if key.lower().startswith("access-control"):
            out.append(f"出现了 {key} 头（不开 CORS）")
    return out


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
    """流水线真的跑了（六个新源文件在位、Bun 找得到、依赖装好、服务起了）。"""
    assert pipeline.ran, pipeline.reason
    assert not pipeline.stopped_reason, f"流水线中途停了：{pipeline.stopped_reason}"


def test_pipeline_auth(pipeline):
    """D01（黑盒）：19 条读路由不带 cookie 一律 401；/api/ 下不存在的路径 401/404；静态资源不验会话。"""
    _pipeline_group(pipeline, "auth")


def test_pipeline_meta(pipeline):
    """D06/D13/D14（黑盒）：meta 端到端的信封七字段、data 合成、安全头与 no-store。"""
    _pipeline_group(pipeline, "meta")


def test_pipeline_params(pipeline):
    """M21/D11（黑盒）：参数不合格 400 且不起子进程；伪造句柄 409 且提示照原文。"""
    _pipeline_group(pipeline, "params")
