"""T031 战前门禁：桌面端本机服务第 8 片「七端岗位绑定的读写路由（模型配置 M3）」的黑盒基准测试
（合同 t031-desktop-ui-hub-roles v2，基线 399121064f2b4978680a1e6785bc86c770c15923）。

被测对象是 ``ts/packages/ui``：读路由 ``api.hub.roles.get``（``GET /api/v1/hub/roles`` → ``config hub show --json``，
登记为 READ_ROUTE_SPECS 的第 20 条，时限 30 秒，二道脱敏白名单 ``HUB_ROLES_ALLOW``）、两条写路由
``api.hub.roles.set``/``api.hub.roles.unset``（action 逐字 ``hub.set``/``hub.unset``，路径参数键 ``post``，
校验 ``post`` 六个岗位名、``fallback`` 过 TASK_ID_RE）、``OPEN_WRITE_COMMAND_PATHS`` 加进 hub 两条（
``PENDING_WRITE_COMMAND_PATHS`` 保留导出、两条 hub 命令不再在里面）、四份锁定的基准测试与两份只追加文件按合同
第四节逐条改、新用例文件 ``hub-routes.test.ts``（两个替身各起各的服务实例：读路由 fake-kernel + FAKE_KERNEL_JSON，
写路由 fake-write-kernel）与 ``hub-routes-real.test.ts``（真内核）在位、README 的路由表与条数同步，以及既有口径
不推翻（readroutes.ts 去注释后无 WRITE、ui 包依赖只许 base 与 contracts、``public: true`` 仍恰好两处、README
保留「T020」）。条数断言按站主口径只认「写明了/不少于」，不钉恰好、不做整页否定（后续片改数不误伤）；本片的
总数由被锁定用例 W2 的集合比对与 routes-auth 的条数断言钉住。

基线（3991210）上 ``api.hub.roles.get`` 不在 READ_ROUTE_SPECS、``HUB_ROLES_ALLOW``/``allowBindingName`` 不在
redaction.ts、``hub.set``/``hub.unset`` 不在 WRITE_ACTIONS、开放集合仍是 12 条（PENDING 还有两条）、两个新测试文件
不存在、README 还是 19/12 的说法，所以本文件的失败落在「标记不在」「文件不存在」这类断言上，不是导入、收集或语法
错误：模块级只导入标准库，所有仓库文件的读取都发生在用例函数里；流水线（装依赖之后起 vitest 跑新/改测试文件与被
锁定的既有用例文件）放在 ``pipeline`` 会话级夹具里，候选里没有新测试文件时不装依赖、不起 vitest。

结构（编号对应合同 DoD 的 D01–D15；合同 D15 的 16 条变异靠这些断言加被锁定的 Vitest 用例抓，战后门禁另出变异清单）：

- 静态断言（不用流水线，全量 pytest 也跑）：READ_ROUTE_SPECS 的第 20 条与 READ_ROUTE_ARGV 模板（D01）；readroutes.ts
  去注释后无 WRITE、无写路由名，条数注释写 20（D01/D11）；redaction.ts 的 allowBindingName 与 HUB_ROLES_ALLOW
  逐条登记 15 条路径、posts 之外不登记、id 路径用 allowNullableId/allowId、出处注明 kit_roles.py、
  allowPreviewName/PREVIEW_ALLOW 保留（D02/D11）；
  WRITE_ACTIONS 的 hub.set/hub.unset、validValue 的 post 与 fallback、buildWriteArgv 的两个分支、WRITE_ARGV 的两行
  示例（D03/D04）；OPEN/PENDING/NOT_OPEN 三张表（D05）；两条写路由的名字、路径与路径参数键 post（D03）；四份锁定
  测试与两份只追加文件的合同第四节改法（D10/D11）；两个新测试文件在位且要点齐备（D06–D09 的静态面）；README（D12）；
  ui 包依赖清单与 public: true 恰好两处（D11/D13）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：bun install --frozen-lockfile
  （依赖不齐时）之后起两次 vitest——快组（write-argv/write-config/hub-routes/routes-auth/kernel-runner/
  argv-templates）与真内核组（hub-routes-real 与被锁定的 write-real-config/write-real），退出码 0 且 Tests 行 passed。

合同没有写死、门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：见 ``ASSUMPTIONS``。
"""

import json
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

READROUTES_REL = "ts/packages/ui/src/readroutes.ts"
REDACTION_REL = "ts/packages/ui/src/redaction.ts"
WRITEROUTES_REL = "ts/packages/ui/src/writeroutes.ts"
ROUTES_REL = "ts/packages/ui/src/routes.ts"
UI_PACKAGE_REL = "ts/packages/ui/package.json"
README_REL = "ts/packages/ui/README.md"
FAKE_KERNEL_REL = "ts/packages/ui/test/fixtures/fake-write-kernel.mjs"
ROUTES_AUTH_REL = "ts/packages/ui/test/routes-auth.test.ts"
KERNEL_RUNNER_REL = "ts/packages/ui/test/kernel-runner.test.ts"
ARGV_TEMPLATES_REL = "ts/packages/ui/test/argv-templates.test.ts"
WRITE_ARGV_TEST_REL = "ts/packages/ui/test/write-argv.test.ts"
WRITE_CONFIG_REL = "ts/packages/ui/test/write-config.test.ts"

# 合同 Scope：两个新测试文件（新用例一律写在这里，不许动别的既有测试文件）
NEW_TEST_RELS = (
    "ts/packages/ui/test/hub-routes.test.ts",
    "ts/packages/ui/test/hub-routes-real.test.ts",
)
# 流水线连跑的被锁定既有用例（D11：四份锁定的基准测试加令牌表，一条不推翻）
FAST_GROUP_RELS = (
    "ts/packages/ui/test/write-argv.test.ts",
    "ts/packages/ui/test/write-config.test.ts",
    "ts/packages/ui/test/hub-routes.test.ts",
    "ts/packages/ui/test/routes-auth.test.ts",
    "ts/packages/ui/test/kernel-runner.test.ts",
    "ts/packages/ui/test/argv-templates.test.ts",
)
REAL_GROUP_RELS = (
    "ts/packages/ui/test/hub-routes-real.test.ts",
    "ts/packages/ui/test/write-real-config.test.ts",
)

# 六个岗位（scripts/kit_roles.py 的 HUB_POST_ADAPTERS，合同第一节/第二节）
HUB_POSTS = ("coordinator", "planner", "contract", "gate", "audit", "exec")
# 五个适配器（kit_roles.py 的 ADAPTERS/HUB_POST_ADAPTERS；T041 起 runtime.add 也认 quizs）
HUB_ADAPTERS = ("pi", "claude-code", "codex", "opencode", "quizs")
# thinking 七档（writeroutes.ts 既有的 THINKING_LEVELS）
THINKING_ENUM = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
# 既有 12 个 action（本片只加 hub.set/hub.unset，共 14 个）
OLD_12_ACTIONS = ("role.set", "preset.use", "preset.save", "preset.remove", "config.rollback",
                  "plugin.enable", "plugin.disable", "profile.add", "profile.edit", "profile.remove",
                  "runtime.add", "runtime.remove")
# U4：开放的 14 条写命令路径（既有 12 条一条不改 + config hub set / config hub unset）
OPEN_14_PATHS = (
    "config role set", "config preset use", "config preset save", "config preset remove", "config rollback",
    "plugins enable", "plugins disable", "config profile add", "config profile edit", "config profile remove",
    "config runtime add", "config runtime remove", "config hub set", "config hub unset",
)
# NOT_OPEN_WRITE_COMMANDS 的命令路径记号（合同：本片不动这张表）
NOT_OPEN_PATH_TOKENS = ("set", "unset", "init", "decisions", "scan", "secret", "prepare", "run", "verdict")
# HUB_ROLES_ALLOW 的 15 条路径（合同第二节的表；posts.*.fallback 本身不登记）
HUB_ALLOW_PATHS = (
    ("posts", "*", "post"),
    ("posts", "*", "source"),
    ("posts", "*", "allowed_adapters", "*"),
    ("posts", "*", "adapter"),
    ("posts", "*", "provider"),
    ("posts", "*", "model"),
    ("posts", "*", "thinking"),
    ("posts", "*", "profile"),
    ("posts", "*", "runtime"),
    ("posts", "*", "fallback", "adapter"),
    ("posts", "*", "fallback", "provider"),
    ("posts", "*", "fallback", "model"),
    ("posts", "*", "fallback", "thinking"),
    ("posts", "*", "fallback", "profile"),
    ("posts", "*", "fallback", "runtime"),
)
# 读路由的 argv 模板（合同第一节）
HUB_SHOW_ARGV = ("config", "hub", "show", "--json")
# WRITE_ARGV 的两行新示例（合同第五节）
HUB_SET_ARGV = ("config", "hub", "set", "coordinator", "demo-profile", "--fallback=demo-fallback")
HUB_UNSET_ARGV = ("config", "hub", "unset", "coordinator")

# hub-routes.test.ts（合同 v2 第六节：起真的服务进程，两个替身各起各的服务实例——读路由一支走
# fake-kernel.mjs + FAKE_KERNEL_JSON 给 hub 形状 JSON，写路由一支走 fake-write-kernel.mjs；白名单、五种 400、
# U6 的四种 409、--yes/--expect-state、预览 action 不符回 500、令牌不外泄）
HUB_ROUTES_TEST_TOKENS = (
    (r"startService", "照 write-config/routes-auth 的写法起真的服务进程（两个替身各起各的实例）"),
    (r"fake-kernel", "读路由一支的内核子进程走 fake-kernel.mjs（fake-write-kernel 的 --json 一支固定回 {}）"),
    (r"FAKE_KERNEL_JSON", "用 FAKE_KERNEL_JSON 给 hub 形状的 JSON（六个岗位各一行，含 null 行与越界行）"),
    (r"fake-write-kernel", "写路由一支的内核子进程走 fake-write-kernel.mjs"),
    (r"/api/v1/hub/roles", "读路由与两条写路由的路径"),
    (r"waitForBegin|FAKE_KERNEL_REPORT", "等子进程起来照 kernel-runner 的 waitForBegin 写法（不许固定睡）"),
    (r"begin", "替身报告的 begin 行（不起子进程的用例断言没有它）"),
    (r"config[\"'], ?[\"']hub[\"'], ?[\"']show[\"'], ?[\"']--json[\"']|--json", "argv 恰为 config hub show --json"),
    (r"401", "不带会话一律 401"),
    (r"<redacted>", "越界的枚举值/凭据形状的值变成 <redacted>"),
    (r"post 不合法", "post 不在六个岗位名里 → 400"),
    (r"fallback 不合法", "fallback 不合格 → 400"),
    (r"确认号无效、已过期或已用过：请重新预览", "U6 前三种 409 的提示原文"),
    (r"确认号与这次请求的参数不符：请重新预览", "U6 换参数那种 409 的提示原文"),
    (r"FAKE_WRITE_PREVIEW", "预览的 action 与请求不同时（M10）用 FAKE_WRITE_PREVIEW 覆盖成别的 action"),
    (r"内核的预览不合格", "预览 action 不符 → 500 的提示原文"),
    (r"--expect-state", "执行 argv 带 --expect-state=<state>"),
    (r"--yes", "只有预览说 needs_yes 时执行 argv 才带 --yes"),
    (r"expect_state", "替身报告的 expect_state 与整条令牌逐字相同（令牌不外泄的查法）"),
)
# hub-routes-real.test.ts（合同第六节真内核用例：U9 逐字段一致、U7 审计 actor、U6b 的 409/stale、不许的绑定）
HUB_ROUTES_REAL_TEST_TOKENS = (
    (r"startService", "照 write-real-config.test.ts 的写法起真服务"),
    (r"THEMIS_PYTHON|pi_dispatch", "真内核用 THEMIS_PYTHON / scripts/pi_dispatch.py"),
    (r"/api/v1/hub/roles", "读路由与两条写路由的路径"),
    (r"hub[\"'], ?[\"']show|config hub show", "直接跑 config hub show --json 与读路由的 data 逐字段比"),
    (r"逐字段|逐项|toEqual", "U9 逐字段一致的比较口径"),
    (r"user-ui", "U7 审计的 actor 是 user-ui"),
    (r"409", "U6b：预览之后配置被别的进程改了 → 409"),
    (r"exit_code", "U6b：信封的 exit_code 是 4"),
    (r"stale", "U6b：操作记 stale"),
    (r"逐字节", "U6b/不许的绑定：配置与审计逐字节不变"),
    (r"fallback|profile", "U7 夹具里登记 runtime 与 profile、hub set 的正文"),
)
# fake-write-kernel.mjs：T019/T020 点名的记号一个不许少，另加 hub 的两条映射
FAKE_KERNEL_KEEP_TOKENS = (
    "FAKE_KERNEL_REPORT", "FAKE_WRITE_PREVIEW", "FAKE_WRITE_PLAN", "FAKE_WRITE_GATE", "FAKE_WRITE_BEGIN",
    "FAKE_WRITE_SLOW_GATE", "--dry-run", "--expect-state", "ok", "stale", "audit-fail", "pause",
)

ASSUMPTIONS = (
    "「READ_ROUTE_SPECS 的第 20 条」按登记顺序里 api.hub.roles.get 的位置不早于第 20 个判（后续片再加条目也不误伤）；"
    "条数只查「不少于 20」与该条自身的 path/timeoutSeconds（站主已把旧门禁的「恰好 19」放宽成「不少于」，同一口径）",
    "「api.hub.roles.get 的时限 30 秒」按登记行的 timeoutSeconds: DEFAULT_TIMEOUT 判（DEFAULT_TIMEOUT=30 由既有用例钉住）",
    "「PENDING_WRITE_COMMAND_PATHS」只查两条 hub 命令不在里面（本片已挪进开放集合）；是否为空数组不钉——后续片"
    "把新命令记进去是设计内行为（W2 的两张表合起来与内核集合比对仍在被锁定用例里钉住总数）；导出保留由名字在判",
    "「NOT_OPEN_WRITE_COMMANDS 不动」按七条命令路径记号都在、reason 至少 7 处判（合同 Repository facts 写 8 条、实数 7 条"
    "路径行，按 T020 门禁的同一口径；条数不逐一断言）",
    "HUB_ROLES_ALLOW 的 15 条路径按块内逐行解析判「恰好这 15 条、posts 之外不登记」；每行的校验函数只查符号与取值"
    "集合出现在 redaction.ts 里（六个岗位、五个适配器含 quizs、七个档位、allowBindingName、allowNullableId 或"
    "allowId——合同 v2 第二节用新增的 allowNullableId，也接受别的可空包装写法），枚举 choices 带 null 与越界遮掉"
    "由替身用例的白名单断言与真内核 U9 的逐字段一致在流水线里钉住，静态不猜实现写法",
    "「岗位名与适配器名注明出处」按 redaction.ts 与 writeroutes.ts 的注释里出现 kit_roles.py 判（未去注释的全文找）",
    "「readroutes.ts 去注释后无 WRITE」沿用 T019 门禁的注释剥离口径；本片另加两条写路由名 api.hub.roles.set/"
    "api.hub.roles.unset 与 action 名 hub.set/hub.unset 也不许出现；条数注释只查写明了「N 条」（站主 11-14 为 T042 放宽，原来只查「20 条」出现），不查「19 条」"
    "消失（合同 §1 只点名文件头那一处，另两处注释改不改由执行端自定）",
    "「四份锁定的基准测试只改点名的几处」按点名的标记在判（名表与示例的新行、条数断言的值不少于 20/14、时限数组"
    "不少于 20 个值、令牌表的两行）；条数与行数的具体值不钉恰好、旧数不查消失——站主口径：数随后续片变，"
    "总数由被锁定用例 W2 的集合比对与 routes-auth 的条数断言钉住，证据不丢",
    "README 的条数只认「写明了」（读路由与写操作两处有「N 条…」的说法）；「连接空闲超时」那一条按合同 v2 §7 "
    "要求写成「N 条读路由、预览、M 条写路由」（站主 11-14 为 T042 放宽，原来逐字钉 20 与 14；不做整页否定）",
    "流水线预算 480 秒（G01 的 600 秒减去静态用例与 pytest 自身开销）：依赖装好时两组 vitest 实测远小于预算；bun install "
    "只在依赖不齐时跑（候选做完 S01 之后不会跑）",
)

# 流水线预算：合同 G01 的超时是 600 秒，留出静态用例与 pytest 自身的开销。
PIPELINE_BUDGET = 480
STEP_CAPS = {"bun install": 200, "vitest fast": 300, "vitest real": 200}

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


#: 行注释与块注释在同一次从左往右的扫描里认：先出现的那一种算数（与 T006/T020 门禁同一写法）。冒号、引号或反引号
#: 紧跟的 `//` 不算行注释（网址、以 // 开头的字符串）。
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def _argv_written(code, *parts):
    """argv 模板片段在不在：连写（``config hub show``）或相邻的数组元素（``"config", "hub", "show"``）都算。"""
    if " ".join(parts) in code:
        return True
    for quote in ('"', "'"):
        elems = ("," + r"\s*").join(quote + re.escape(part) + quote for part in parts)
        if re.search(elems, code) is not None:
            return True
    return False


def _block(text, start_marker, end_marker="\n};"):
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
# 静态断言：读路由（D01/D11）
# ---------------------------------------------------------------------------

def test_static_read_route_registered():
    """D01（M15/M16）：``api.hub.roles.get`` 登记为 READ_ROUTE_SPECS 的第 20 条——path 恰为 /api/v1/hub/roles、
    时限 DEFAULT_TIMEOUT（30 秒）；readRoutes() 里有这条 GET 路由，处理器交出的 argv 恰为 config hub show --json
    且白名单用 HUB_ROLES_ALLOW。"""
    code = strip_ts_comments(need_file(READROUTES_REL))
    problems = []
    block = _block(code, "export const READ_ROUTE_SPECS", "\n];")
    if not block:
        problems.append("readroutes.ts 应有 export const READ_ROUTE_SPECS（登记表）")
    else:
        names = re.findall(r'name:\s*"([^"]+)"', block)
        if "api.hub.roles.get" not in names:
            problems.append("READ_ROUTE_SPECS 里应有「api.hub.roles.get」（第 20 条）")
        else:
            at = names.index("api.hub.roles.get")
            if at < 19:
                problems.append(f"api.hub.roles.get 应追加在表末（第 20 条或更后），实际是第 {at + 1} 个")
            if len(names) < 20:
                problems.append(f"READ_ROUTE_SPECS 不应少于 20 条，实际 {len(names)}")
            row = re.search(r'name:\s*"api\.hub\.roles\.get"[^}]*}', block)
            if row is None:
                problems.append("READ_ROUTE_SPECS 里 api.hub.roles.get 的登记行读不出来")
            else:
                if 'path: "/api/v1/hub/roles"' not in row.group(0):
                    problems.append("api.hub.roles.get 的 path 应恰为 /api/v1/hub/roles")
                if "timeoutSeconds: DEFAULT_TIMEOUT" not in row.group(0):
                    problems.append("api.hub.roles.get 的时限应是 DEFAULT_TIMEOUT（30 秒）")
    # 处理函数：GET、精确路径、jsonRoute + HUB_ROLES_ALLOW、argv 与模板一致
    route = _block(code, 'name: "api.hub.roles.get"', "\n    },")
    if not route:
        problems.append("readRoutes() 里应有 name: \"api.hub.roles.get\" 的路由项")
    else:
        if "GET" not in route:
            problems.append("api.hub.roles.get 应是 GET")
        if 'exact("/api/v1/hub/roles")' not in route:
            problems.append("api.hub.roles.get 的 pattern 应是 exact(\"/api/v1/hub/roles\")")
        if "jsonRoute" not in route:
            problems.append("api.hub.roles.get 的处理器应走 jsonRoute")
        if "HUB_ROLES_ALLOW" not in route:
            problems.append("api.hub.roles.get 的处理器应登记白名单 HUB_ROLES_ALLOW")
        if not _argv_written(route, *HUB_SHOW_ARGV):
            problems.append("api.hub.roles.get 的处理器交出的 argv 应恰为 config hub show --json")
        if 'at("api.hub.roles.get", DEFAULT_TIMEOUT)' not in route:
            problems.append("api.hub.roles.get 的时限应经 at(\"api.hub.roles.get\", DEFAULT_TIMEOUT)")
    # READ_ROUTE_ARGV 模板
    argv_block = _block(code, "export const READ_ROUTE_ARGV")
    row = re.search(r'"api\.hub\.roles\.get"\s*:\s*\[([^\]]*)\]', argv_block)
    if row is None:
        problems.append("READ_ROUTE_ARGV 里应有 \"api.hub.roles.get\" 的模板")
    elif not _argv_written(row.group(0), *HUB_SHOW_ARGV):
        problems.append(f"READ_ROUTE_ARGV 的 api.hub.roles.get 模板应恰为 {list(HUB_SHOW_ARGV)}")
    fail_if(problems, "读路由登记（D01）")


def test_static_readroutes_clean():
    """D01/D11：readroutes.ts 去注释后不许出现字符串 WRITE，也不许出现写路由名（api.hub.roles.set/
    api.hub.roles.unset）与 action 名（hub.set/hub.unset）；文件里的「19 条」说法改成「20 条」。"""
    text = need_file(READROUTES_REL)
    code = strip_ts_comments(text)
    problems = []
    for needle, label in (("WRITE", "WRITE（T019 门禁）"),
                          ("api.hub.roles.set", "写路由名 api.hub.roles.set"),
                          ("api.hub.roles.unset", "写路由名 api.hub.roles.unset"),
                          ("hub.set", "action 名 hub.set"),
                          ("hub.unset", "action 名 hub.unset")):
        if needle in code:
            problems.append(f"readroutes.ts 去注释后不应出现 {label}")
    # 站主门禁准备（2026-11-14）：T042 再加两条 Quizs 读路由，条数随片变；只认写明了条数（原来钉「20 条」）
    if re.search(r"\d+\s*条", text) is None:
        problems.append("readroutes.ts 的文件头注释应写明有几条读路由（「N 条」）")
    fail_if(problems, "readroutes.ts 的干净面（D01/D11）")


# ---------------------------------------------------------------------------
# 静态断言：redaction.ts（D02/D11）
# ---------------------------------------------------------------------------

def test_static_redaction_allowlist():
    """D02（M1–M3）：redaction.ts 新增导出 allowBindingName（null 放行；字符串过
    ^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$ 且 tokenShaped 为假）与 HUB_ROLES_ALLOW（恰好第二节那 15 条路径、
    posts 之下不登记别的路径、posts.*.fallback 本身不登记）；六个岗位、五个适配器（含 quizs）、七个档位都抄进来了，
    出处注明 kit_roles.py；allowPreviewName 与 PREVIEW_ALLOW 的既有行保留（本片不改它们的语义）。"""
    text = need_file(REDACTION_REL)
    code = strip_ts_comments(text)
    problems = []
    # allowBindingName：新导出的校验函数
    fn = _block(code, "export function allowBindingName", "\n}")
    if not fn:
        problems.append("redaction.ts 应导出 allowBindingName（provider/model 与 fallback 同名字段统一用它）")
    else:
        for token, label in (("[A-Za-z0-9._:/@+-]", "字符集（带 : / @ +）"),
                             ("{0,199}", "长度上限 200 的量词"),
                             ("tokenShaped", "不像凭据（tokenShaped 为假）"),
                             ("null", "值为 null 直接放行")):
            if token not in fn:
                problems.append(f"allowBindingName 里看不到「{token}」（{label}）")
    # HUB_ROLES_ALLOW：恰好 15 条路径
    block = _block(code, "export const HUB_ROLES_ALLOW", "\n];")
    if not block:
        problems.append("redaction.ts 应导出 HUB_ROLES_ALLOW（/api/v1/hub/roles 的白名单）")
    else:
        rows = re.findall(r"\[\s*\[\s*((?:\"[^\"]*\"\s*,?\s*)+)\]\s*,", block)
        seen = {tuple(re.findall(r'"([^"]*)"', row)) for row in rows}
        for path in HUB_ALLOW_PATHS:
            if path not in seen:
                problems.append(f"HUB_ROLES_ALLOW 里应有路径 {list(path)}")
        extra = seen - set(HUB_ALLOW_PATHS)
        if extra:
            problems.append(f"HUB_ROLES_ALLOW 不应登记别的路径（posts.*.fallback 本身也不登记）：{sorted(extra)}")
        # 白名单里用到的名字与符号都在文件里
        for name in HUB_POSTS:
            if f'"{name}"' not in code:
                problems.append(f"redaction.ts 里应抄有岗位名「{name}」（kit_roles.py 的 HUB_POST_ADAPTERS）")
        for name in HUB_ADAPTERS:
            if f'"{name}"' not in code:
                problems.append(f"redaction.ts 里应抄有适配器名「{name}」（五个，含 quizs）")
        for level in THINKING_ENUM:
            if f'"{level}"' not in code:
                problems.append(f"redaction.ts 里应有档位「{level}」（七个档位）")
        if '"default"' not in code or '"config"' not in code:
            problems.append("redaction.ts 里应有 source 的两个取值 default 与 config")
        if "allowBindingName" not in block:
            problems.append("HUB_ROLES_ALLOW 里应有路径用 allowBindingName（provider/model 及 fallback 同名字段）")
        if re.search(r"allowNullableId|allowId", block) is None:
            # 合同 v2 第二节：四条 id 路径用 allowNullableId（null 放行再 allowId）；也接受别的可空包装写法
            problems.append("HUB_ROLES_ALLOW 里应有路径用 allowNullableId/allowId（profile/runtime 及 fallback 同名字段）")
    # 出处注释（ui 包不许 import @themis/config，名字另抄一份并注明出处）
    if "kit_roles.py" not in text:
        problems.append("redaction.ts 的注释应注明岗位名与适配器名抄自 scripts/kit_roles.py（HUB_POST_ADAPTERS）")
    # 既有函数与白名单保留（本片不改它们的语义）
    if "allowPreviewName" not in code:
        problems.append("redaction.ts 应保留 allowPreviewName（本片不许改它的语义）")
    preview_rows = len(re.findall(r'\[\s*\[\s*"binding_changes"', code))
    if preview_rows < 12:
        problems.append(f"PREVIEW_ALLOW 的 binding_changes 行应保留 12 条，实际 {preview_rows}")
    fail_if(problems, "HUB_ROLES_ALLOW（D02）")


# ---------------------------------------------------------------------------
# 静态断言：writeroutes.ts（D03/D04/D05）
# ---------------------------------------------------------------------------

def test_static_write_actions_registry():
    """D03/D04：WRITE_ACTIONS 收进 hub.set（必填 post、profile；可选 fallback）与 hub.unset（必填 post；无可选），
    共 14 个 action（既有 12 个一个不许少）；岗位名抄自 kit_roles.py 并在注释里注明出处。"""
    text = need_file(WRITEROUTES_REL)
    code = strip_ts_comments(text)
    problems = []
    block = _block(code, "export const WRITE_ACTIONS")
    if not block:
        problems.append("writeroutes.ts 应有 export const WRITE_ACTIONS（登记表）")
    else:
        entries = dict(re.findall(r'(?m)^[ \t]*"([^"]+)"\s*:\s*\{([^}]*)\}', block))
        if len(entries) < 14:
            problems.append(f"WRITE_ACTIONS 不应少于 14 个 action，实际 {len(entries)}：{sorted(entries)}")
        for action in OLD_12_ACTIONS:
            if action not in entries:
                problems.append(f"WRITE_ACTIONS 里应有「{action}」（既有 12 个一个不许少）")
        expected = {"hub.set": (["post", "profile"], ["fallback"]), "hub.unset": (["post"], [])}
        for action, (required, optional) in expected.items():
            body = entries.get(action)
            if body is None:
                problems.append(f"WRITE_ACTIONS 里应有「{action}」")
                continue
            req = re.search(r"required:\s*\[([^\]]*)\]", body)
            opt = re.search(r"optional:\s*\[([^\]]*)\]", body)
            if req is None or opt is None:
                problems.append(f"{action} 的登记应写 required 与 optional")
                continue
            req_keys = re.findall(r'"([^"]+)"', req.group(1))
            opt_keys = re.findall(r'"([^"]+)"', opt.group(1))
            if sorted(req_keys) != sorted(required):
                problems.append(f"{action} 的必填键应恰为 {required}，实际 {req_keys}")
            if sorted(opt_keys) != sorted(optional):
                problems.append(f"{action} 的可选键应恰为 {optional}，实际 {opt_keys}")
    # 岗位名另抄一份并注明出处（ui 包不许 import @themis/config）
    for name in HUB_POSTS:
        if f'"{name}"' not in code:
            problems.append(f"writeroutes.ts 里应抄有岗位名「{name}」（六个岗位）")
    if "kit_roles.py" not in text:
        problems.append("writeroutes.ts 的注释应注明岗位名抄自 scripts/kit_roles.py（HUB_POST_ADAPTERS）")
    fail_if(problems, "WRITE_ACTIONS（D03/D04）")


def test_static_valid_value_hub_keys():
    """D04（M4/M5）：validValue 加 post（六个岗位名之一）与 fallback（与 profile 同一规则，过 TASK_ID_RE）；
    runtime.add 的 ADAPTERS 至少有原来这四个值（站主按 T041 规划报告 §4.1 R4 退役“不许加 quizs”：T041 起它也认 quizs）。"""
    code = strip_ts_comments(need_file(WRITEROUTES_REL))
    problems = []
    block = _block(code, "function validValue", "\n}")
    if not block:
        problems.append("writeroutes.ts 应有 validValue（预览与写路由共用的单键校验）")
    else:
        post_lines = [line for line in block.splitlines() if '=== "post"' in line or '"post"' in line]
        # 分支的枚举对照由六个岗位名在文件里（另一条用例）加替身用例的白名单/400 断言钉住，这里只查分支在
        if not post_lines:
            problems.append("validValue 应处理键「post」（六个岗位名之一，否则 400「post 不合法」）")
        fb_lines = [line for line in block.splitlines() if '"fallback"' in line]
        if not fb_lines:
            problems.append("validValue 应处理键「fallback」")
        elif not any("TASK_ID_RE" in line for line in fb_lines):
            problems.append("validValue 的 fallback 分支应过 TASK_ID_RE（与 profile 同一规则）")
    # runtime.add 的 ADAPTERS 至少有原来这四个值（T041 起也认 quizs）
    adapters = _block(code, "const ADAPTERS", "\n")
    if adapters:
        for name in ("pi", "claude-code", "codex", "opencode"):
            if f'"{name}"' not in adapters:
                problems.append(f"runtime.add 的 ADAPTERS 应保留「{name}」")
    fail_if(problems, "validValue 的 hub 键（D04）")


def test_static_build_argv_hub():
    """D03（M6/M7）：buildWriteArgv 加两个分支——hub.set → config hub set <post> <profile>（给了 fallback 再加
    --fallback=<fallback>，放最后）、hub.unset → config hub unset <post>；WRITE_ARGV 加两行示例（表共 15 行）。"""
    code = strip_ts_comments(need_file(WRITEROUTES_REL))
    problems = []
    body = _block(code, "export function buildWriteArgv", "\n}\n")
    if not body:
        problems.append("writeroutes.ts 应有 buildWriteArgv")
    else:
        set_at = body.find('case "hub.set"')
        unset_at = body.find('case "hub.unset"')
        default_at = body.find("default:", unset_at if unset_at >= 0 else set_at)
        if set_at < 0:
            problems.append("buildWriteArgv 应有 case \"hub.set\" 分支")
        else:
            seg = body[set_at:unset_at if unset_at > set_at else len(body)]
            for part in ("config", "hub", "set"):
                if f'"{part}"' not in seg:
                    problems.append(f"hub.set 的基础 argv 应含「{part}」")
            if 'args["post"]' not in seg and "args.post" not in seg:
                problems.append("hub.set 的基础 argv 应用正文里的 post")
            if 'args["profile"]' not in seg and "args.profile" not in seg:
                problems.append("hub.set 的基础 argv 应用正文里的 profile")
            if "--fallback=" not in seg:
                problems.append("hub.set 给了 fallback 应加 --fallback=<fallback>（放最后）")
        if unset_at < 0:
            problems.append("buildWriteArgv 应有 case \"hub.unset\" 分支")
        else:
            seg = body[unset_at:default_at if default_at > unset_at else len(body)]
            for part in ("config", "hub", "unset"):
                if f'"{part}"' not in seg:
                    problems.append(f"hub.unset 的基础 argv 应含「{part}」")
            if 'args["post"]' not in seg and "args.post" not in seg:
                problems.append("hub.unset 的基础 argv 应用正文里的 post")
    # WRITE_ARGV 的两行新示例（表共 15 行，既有十三行不动）
    table = _block(code, "export const WRITE_ARGV")
    if not table:
        problems.append("writeroutes.ts 应有 export const WRITE_ARGV（示例表）")
    else:
        rows = re.findall(r'(?m)^[ \t]*["\']([^"\']+)["\']\s*:\s*\[', table)
        if len(rows) < 15:
            problems.append(f"WRITE_ARGV 不应少于 15 行示例（role.set 两行 + 13 条 action 各一行），实际 {len(rows)}")
        row = re.search(r'"hub\.set"\s*:\s*\[([^\]]*)\]', table)
        if row is None:
            problems.append("WRITE_ARGV 应有 \"hub.set\" 的示例行")
        else:
            for part in HUB_SET_ARGV:
                if f'"{part}"' not in row.group(0):
                    problems.append(f"hub.set 的示例应含「{part}」")
        row = re.search(r'"hub\.unset"\s*:\s*\[([^\]]*)\]', table)
        if row is None:
            problems.append("WRITE_ARGV 应有 \"hub.unset\" 的示例行")
        elif not _argv_written(row.group(0), *HUB_UNSET_ARGV):
            problems.append(f"hub.unset 的示例应恰为 {list(HUB_UNSET_ARGV)}")
    fail_if(problems, "buildWriteArgv 与 WRITE_ARGV（D03）")


def test_static_write_routes_registered():
    """D03：写路由表加两条——api.hub.roles.set（POST /api/v1/hub/roles/<post>）与 api.hub.roles.unset
    （POST /api/v1/hub/roles/<post>/unset），路径参数键叫 post（路径参数压正文），action 逐字 hub.set/hub.unset。"""
    code = strip_ts_comments(need_file(WRITEROUTES_REL))
    problems = []
    # 路径正则按源码里的字面写法查（照既有十二条：/^\/api\/v1\/hub\/roles\/([^/]+)$/u）
    for name, action, extra in (
        ("api.hub.roles.set", "hub.set", None),
        ("api.hub.roles.unset", "hub.unset", "/unset$"),
    ):
        route = _block(code, f'name: "{name}"', "\n    },")
        if not route:
            problems.append(f"writeRoutes() 里应有 name: \"{name}\" 的路由项")
            continue
        if "POST" not in route:
            problems.append(f"{name} 应是 POST")
        if "/api\\/v1\\/hub\\/roles\\/" not in route:
            problems.append(f"{name} 的 pattern 应匹配 /api/v1/hub/roles/<post>{'/unset' if extra else ''}")
        if "([^/]+)" not in route:
            problems.append(f"{name} 的 pattern 应有一个路径参数段（岗位名）")
        if extra is not None and extra not in route:
            problems.append(f"{name} 的 pattern 应以 {extra} 结尾（unset 子路径）")
        if not re.search(rf'run\(\s*"{re.escape(action)}"\s*,\s*\{{\s*post\s*:', route):
            problems.append(f"{name} 应以路径参数键 post 调 run(\"{action}\", …)")
    fail_if(problems, "两条写路由（D03）")


def test_static_open_pending_lists():
    """D05（M8/M9）：OPEN_WRITE_COMMAND_PATHS 不少于 14 条且既有 12 条与 config hub set / config hub unset
    都在（逐条名字检查，不钉恰好——总数由被锁定用例 W2 的集合比对钉住）；PENDING_WRITE_COMMAND_PATHS 导出
    保留，且两条 hub 命令不在里面（已挪进开放集合；是否为空不钉，后续片往里记新命令是设计内行为）；
    NOT_OPEN_WRITE_COMMANDS 不动（七条命令路径记号都在、每行一个 reason、不含 hub）。"""
    code = strip_ts_comments(need_file(WRITEROUTES_REL))
    problems = []
    m_open = re.search(r"export const OPEN_WRITE_COMMAND_PATHS[^=]*=\s*\[([^\]]*)\]", code, re.S)
    if m_open is None:
        problems.append("writeroutes.ts 应导出 OPEN_WRITE_COMMAND_PATHS")
    else:
        listed = re.findall(r'"([^"]+)"', m_open.group(1))
        if len(listed) != len(set(listed)):
            problems.append("OPEN_WRITE_COMMAND_PATHS 里不该有重复")
        missing = [p for p in OPEN_14_PATHS if p not in listed]
        if missing:
            problems.append(f"OPEN_WRITE_COMMAND_PATHS 里少了这些命令路径：{missing}")
        if len(listed) < len(OPEN_14_PATHS):
            problems.append(f"OPEN_WRITE_COMMAND_PATHS 不应少于 {len(OPEN_14_PATHS)} 条，实际 {len(listed)} 条")
    m_pending = re.search(r"export const PENDING_WRITE_COMMAND_PATHS[^=]*=\s*\[([^\]]*)\]", code, re.S)
    if m_pending is None:
        problems.append("writeroutes.ts 应保留 PENDING_WRITE_COMMAND_PATHS 这个导出（给后续片留位置）")
    else:
        pending = re.findall(r'"([^"]+)"', m_pending.group(1))
        left = [p for p in ("config hub set", "config hub unset") if p in pending]
        if left:
            problems.append(f"PENDING_WRITE_COMMAND_PATHS 里不该再有 {left}（本片已挪进开放集合）")
    not_open = _block(code, "export const NOT_OPEN_WRITE_COMMANDS", "\n];")
    if not not_open:
        problems.append("writeroutes.ts 应保留 NOT_OPEN_WRITE_COMMANDS（本片不动这张表）")
    else:
        if len(re.findall(r"\breason\b", not_open)) < 7:
            problems.append("NOT_OPEN_WRITE_COMMANDS 的 reason 不应少于 7 处（每条写一行理由）")
        for token in NOT_OPEN_PATH_TOKENS:
            if re.search(rf"[\"']{re.escape(token)}[\"']", not_open) is None:
                problems.append(f"NOT_OPEN_WRITE_COMMANDS 里应有命令路径记号「{token}」（既有条目不许删）")
        if "hub" in not_open:
            problems.append("NOT_OPEN_WRITE_COMMANDS 不该把 hub 的两条写进去（它们挪进了开放集合）")
    fail_if(problems, "OPEN / PENDING / NOT_OPEN（D05）")


# ---------------------------------------------------------------------------
# 静态断言：四份锁定的基准测试与两份只追加的文件（D10/D11）
# ---------------------------------------------------------------------------

def test_static_locked_routes_auth():
    """D11：routes-auth.test.ts 只改点名的几处——READ_ROUTE_EXAMPLES 加 \"api.hub.roles.get\":
    \"/api/v1/hub/roles\"、条数断言写成新事实（值不少于 20，不钉恰好——后续片加路由不误伤）；不许出现 skip/only/todo。"""
    text = need_file(ROUTES_AUTH_REL)
    problems = []
    if '"api.hub.roles.get": "/api/v1/hub/roles"' not in text:
        problems.append('READ_ROUTE_EXAMPLES 应加一行 "api.hub.roles.get": "/api/v1/hub/roles"')
    m = re.search(r"expect\(listed\.length\)\.toBe\((\d+)\)", text)
    if m is None:
        problems.append("routes-auth.test.ts 应保留条数断言 expect(listed.length).toBe(…)")
    elif int(m.group(1)) < 20:
        problems.append(f"条数断言的值不应少于 20（新事实），实际 toBe({m.group(1)})")
    problems += _no_skip_marks(strip_ts_comments(text))
    fail_if(problems, "routes-auth.test.ts（D11）")


def test_static_locked_kernel_runner():
    """D11：kernel-runner.test.ts 的 CASES 加 api.hub.roles.get 一行（path /api/v1/hub/roles、argv 取
    READ_ROUTE_ARGV），时限数组不少于 20 个值（末尾补 30；不钉恰好——后续片加路由不误伤）。"""
    text = need_file(KERNEL_RUNNER_REL)
    code = strip_ts_comments(text)
    problems = []
    if re.search(r'name:\s*"api\.hub\.roles\.get"', code) is None:
        problems.append("CASES 应加一行 name: \"api.hub.roles.get\"（放在表末）")
    if re.search(r'path:\s*"/api/v1/hub/roles"', code) is None:
        problems.append("CASES 新行的 path 应是 /api/v1/hub/roles")
    if 'READ_ROUTE_ARGV["api.hub.roles.get"]' not in code:
        problems.append("CASES 新行的 argv 应取 READ_ROUTE_ARGV[\"api.hub.roles.get\"]")
    m = re.search(r"READ_ROUTE_SPECS\.map\(\(spec\)\s*=>\s*spec\.timeoutSeconds\)\)\.toEqual\(\[([^\]]*)\]", code)
    if m is None:
        problems.append("kernel-runner.test.ts 应保留 READ_ROUTE_SPECS 时限数组的断言")
    else:
        values = [v.strip() for v in m.group(1).split(",") if v.strip()]
        if len(values) < 20:
            problems.append(f"时限数组不应少于 20 个值（末尾补 30），实际 {len(values)}")
    problems += _no_skip_marks(code)
    fail_if(problems, "kernel-runner.test.ts（D11）")


def test_static_locked_argv_templates():
    """D11：argv-templates.test.ts 的 READ_ROUTE_SPECS 长度断言改成不少于 20（不钉恰好——后续片不误伤）。"""
    text = need_file(ARGV_TEMPLATES_REL)
    problems = []
    m = re.search(r"expect\(READ_ROUTE_SPECS\)\.toHaveLength\((\d+)\)", text)
    if m is None:
        problems.append("argv-templates.test.ts 应保留 expect(READ_ROUTE_SPECS).toHaveLength(…)")
    elif int(m.group(1)) < 20:
        problems.append(f"READ_ROUTE_SPECS 的长度断言不应少于 20，实际 toHaveLength({m.group(1)})")
    problems += _no_skip_marks(strip_ts_comments(text))
    fail_if(problems, "argv-templates.test.ts（D11）")


def test_static_locked_write_argv_test():
    """D05/D10/D11：write-argv.test.ts 的 W2 改到新事实——open 长度 14、known 仍是开放加 PENDING 两张表合起来与
    内核集合比对；W4 的 action 名单加 hub.set 与 hub.unset；W3 的示例补两条；W4 加 post/fallback 的取值用例与
    buildWriteArgv 的两条逐项断言。open 的长度断言不钉恰好（不少于 14，后续片不误伤）。"""
    text = need_file(WRITE_ARGV_TEST_REL)
    code = strip_ts_comments(text)
    problems = []
    m_len = re.search(r"expect\(open\)\.toHaveLength\((\d+)\)", code)
    if m_len is None:
        problems.append("W2 应保留 expect(open).toHaveLength(…)")
    elif int(m_len.group(1)) < 14:
        problems.append(f"W2 的 open 长度断言不应少于 14（本片把 hub 两条挪进开放集合），实际 {m_len.group(1)}")
    if "PENDING_WRITE_COMMAND_PATHS" not in code:
        problems.append("W2 应仍用 PENDING_WRITE_COMMAND_PATHS（两张表合起来与内核集合相等、互不相交）")
    for action in ("hub.set", "hub.unset"):
        if f'"{action}"' not in code:
            problems.append(f"W4 的 action 名单应含「{action}」")
    if re.search(r'"hub\.set"\s*:\s*\{\s*post:\s*"coordinator"', code) is None:
        problems.append('W3 的示例应补 "hub.set": { post: "coordinator", … }')
    if re.search(r'"hub\.unset"\s*:\s*\{\s*post:\s*"coordinator"', code) is None:
        problems.append('W3 的示例应补 "hub.unset": { post: "coordinator" }')
    if "post 不合法" not in code:
        problems.append("W4 应加 post 取值的用例（「post 不合法」）")
    if "fallback 不合法" not in code:
        problems.append("W4 应加 fallback 取值的用例（「fallback 不合法」）")
    if 'buildWriteArgv("hub.set"' not in code:
        problems.append("W4 应加 buildWriteArgv(\"hub.set\", …) 的逐项断言")
    if 'buildWriteArgv("hub.unset"' not in code:
        problems.append("W4 应加 buildWriteArgv(\"hub.unset\", …) 的逐项断言")
    problems += _no_skip_marks(code)
    fail_if(problems, "write-argv.test.ts（D05/D10/D11）")


def test_static_locked_write_config():
    """D10/D11：write-config.test.ts 只追加——「令牌不外泄」的 ROWS 加 hub.set（path /api/v1/hub/roles/coordinator、
    body {profile: \"demo-profile\"}）与 hub.unset（path /api/v1/hub/roles/coordinator/unset、body {}）两行，
    四查法一字不改（expect_state 与 includes 的记号仍在）；行数的说法只认写明了（不钉具体数）。"""
    text = need_file(WRITE_CONFIG_REL)
    code = strip_ts_comments(text)
    problems = []
    set_row = re.search(r'action:\s*"hub\.set"[^\n]*', code)
    if set_row is None:
        problems.append("令牌表应加一行 action: \"hub.set\"")
    else:
        if 'path: "/api/v1/hub/roles/coordinator"' not in set_row.group(0):
            problems.append("hub.set 那行的 path 应是 /api/v1/hub/roles/coordinator")
        if 'profile: "demo-profile"' not in set_row.group(0):
            problems.append("hub.set 那行的 body 应是 { profile: \"demo-profile\" }")
    unset_row = re.search(r'action:\s*"hub\.unset"[^\n]*', code)
    if unset_row is None:
        problems.append("令牌表应加一行 action: \"hub.unset\"")
    else:
        if 'path: "/api/v1/hub/roles/coordinator/unset"' not in unset_row.group(0):
            problems.append("hub.unset 那行的 path 应是 /api/v1/hub/roles/coordinator/unset")
    if re.search(r"\d+\s*行", text) is None:
        problems.append("「令牌不外泄」的 describe 与文件头注释应写明行数（站主口径：只认写明了条数）")
    if "expect_state" not in code:
        problems.append("四查法的 expect_state 逐字比对应保留")
    if "includes" not in code:
        problems.append("四查法的令牌逐段 includes 搜不到应保留")
    problems += _no_skip_marks(code)
    fail_if(problems, "write-config.test.ts（D10/D11）")


def test_static_fake_kernel_subactions():
    """D11：替身只追加——SUBACTIONS 加 hub: { set: \"hub.set\", unset: \"hub.unset\" }（deriveAction 把
    config hub set/unset 推成这两个 action，预览一支的 action 与请求逐字相同）；既有映射与 T019/T020 点名的
    记号一个不许少。"""
    text = need_file(FAKE_KERNEL_REL)
    problems = []
    if re.search(r"hub\s*:\s*\{\s*set\s*:\s*[\"']hub\.set[\"']\s*,\s*unset\s*:\s*[\"']hub\.unset[\"']\s*\}", text) is None:
        problems.append('SUBACTIONS 应加 hub: { set: "hub.set", unset: "hub.unset" }')
    # 既有 SUBACTIONS 的映射记号（分组键与子命令）都在
    sub = text.split("SUBACTIONS", 1)[-1].split("deriveAction", 1)[0] if "SUBACTIONS" in text else ""
    if sub:
        for key in ("role", "preset", "profile", "runtime"):
            if f"{key}: " not in sub:
                problems.append(f"SUBACTIONS 里应保留「{key}」的映射")
    for token in FAKE_KERNEL_KEEP_TOKENS:
        if token not in text:
            problems.append(f"替身里应保留记号「{token}」（T019/T020 门禁点名）")
    fail_if(problems, "fake-write-kernel.mjs（D11）")


# ---------------------------------------------------------------------------
# 静态断言：两个新测试文件在位且要点齐备（D06–D09 的静态面）
# ---------------------------------------------------------------------------

def test_static_new_test_files():
    """D06–D09 的静态面：hub-routes.test.ts（替身用例——argv 恰为 config hub show --json、401、白名单的
    <redacted>、四种 400、U6 的两种 409 提示原文、--yes/--expect-state、waitForBegin、令牌不外泄）与
    hub-routes-real.test.ts（真内核用例——U9 逐字段一致、U7 的 user-ui、U6b 的 409/exit_code 4/stale/逐字节）
    在位且不许出现 skip/only/todo。"""
    problems = []
    for rel, tokens in (
        ("ts/packages/ui/test/hub-routes.test.ts", HUB_ROUTES_TEST_TOKENS),
        ("ts/packages/ui/test/hub-routes-real.test.ts", HUB_ROUTES_REAL_TEST_TOKENS),
    ):
        text = need_file(rel)
        stripped = strip_ts_comments(text)
        problems += [f"{rel}：{p}" for p in _token_problems(stripped, tokens)]
        problems += [f"{rel}：{p}" for p in _no_skip_marks(stripped)]
    fail_if(problems, "两个新测试文件的要点（D06–D09）")


# ---------------------------------------------------------------------------
# 静态断言：README（D12）
# ---------------------------------------------------------------------------

def _section(text, heading):
    head = text.find(heading)
    if head < 0:
        return None
    tail = text.find("\n## ", head + 1)
    return text[head:tail if tail > 0 else len(text)]


def test_static_readme():
    """D12：README 与行为同步——读路由表加 GET /api/v1/hub/roles（config hub show --json、30 秒）、写路由表加
    两条 POST /api/v1/hub/roles/<post>（90 秒）；条数只认「写明了」（站主口径：数随后续片变，不做整页否定，
    只查读路由与写路由的条数说法还在）；「连接空闲超时」那一条按合同 v2 §7 仍逐字写「20 条读路由、预览、
    14 条写路由」；「已知限制」把 hub set/unset 列进写路由的覆盖里（覆盖数只认写明了）；至少保留一处「T020」；
    既有段落（## 日志跟随、状态码：201 作业创建成功、**作业表只在内存里**）不动。"""
    text = need_file(README_REL)
    problems = []
    if "T020" not in text:
        problems.append("README 应至少保留一处「T020」（T019 门禁 test_static_readme 查这个词）")
    # 三条新路由进了路由表
    if re.search(r"GET\s+/api/v1/hub/roles\b", text) is None:
        problems.append("读路由表应加一行 GET /api/v1/hub/roles")
    elif "config hub show --json" not in text:
        problems.append("GET /api/v1/hub/roles 那行应写 config hub show --json")
    if re.search(r"POST\s+/api/v1/hub/roles/<post>\s", text) is None and "POST /api/v1/hub/roles/<post>" not in text:
        problems.append("写路由表应加一行 POST /api/v1/hub/roles/<post>")
    if "config hub set" not in text:
        problems.append("POST /api/v1/hub/roles/<post> 那行应写 config hub set <post> <profile> [--fallback=<profile>]")
    if "POST /api/v1/hub/roles/<post>/unset" not in text:
        problems.append("写路由表应加一行 POST /api/v1/hub/roles/<post>/unset")
    if "config hub unset" not in text:
        problems.append("POST /api/v1/hub/roles/<post>/unset 那行应写 config hub unset <post>")
    # 条数的说法（站主口径：只认写明了条数，不做整页否定、不钉具体数——后续片改数不误伤）
    if re.search(r"\d+\s*条只读数据路由", text) is None:
        problems.append("README 应写明有几条只读数据路由（看不到「N 条只读数据路由」的说法）")
    write_section = _section(text, "## 写操作")
    if write_section is None or re.search(r"\d+\s*条写路由", write_section) is None:
        problems.append("「写操作」一节应写明有几条写路由（看不到「N 条写路由」的说法）")
    # 连接空闲超时那一条
    at = text.find("连接空闲超时")
    if at < 0:
        problems.append("README 应保留「连接空闲超时」那一条")
    else:
        bullet_end = text.find("\n- ", at)
        bullet = text[at:bullet_end if bullet_end > 0 else at + 600]
        # 站主门禁准备（2026-11-14）：T042 加读路由，条数随片变；只认「N 条读路由、预览、M 条写路由」的说法（原来逐字钉 20 与 14）
        if re.search(r"\d+\s*条读路由、预览、\d+\s*条写路由", bullet) is None:
            problems.append("「连接空闲超时」那一条应写「N 条读路由、预览、M 条写路由」")
    # 已知限制
    limits = _section(text, "## 已知限制")
    if limits is None:
        problems.append("README 应有「## 已知限制」一节")
    else:
        if re.search(r"写路由覆盖\s*\d+\s*条", limits) is None:
            problems.append("「已知限制」应写明写路由覆盖几条（只认写明了条数）")
        if "hub set" not in limits or "hub unset" not in limits:
            problems.append("「已知限制」应把 hub set 与 hub unset 列进写路由的覆盖里")
    # 既有段落不动（这些记号一个不许少）
    for needle in ("## 日志跟随", "状态码：201 作业创建成功", "**作业表只在内存里**"):
        if needle not in text:
            problems.append(f"README 的既有段落应一字不动（看不到「{needle}」）")
    fail_if(problems, "README（D12）")


# ---------------------------------------------------------------------------
# 静态断言：既有口径不推翻（D11/D13）
# ---------------------------------------------------------------------------

def test_static_ui_package_and_public_routes():
    """D11/D13：ui 包的依赖清单仍只许 @themis/base 与 @themis/contracts；routes.ts 里 public: true 仍恰好两处
    （新路由不许标 public——它们要会话）。这条在基线上就是绿的，是回归保护。"""
    problems = []
    pkg = json.loads(need_file(UI_PACKAGE_REL))
    for section in ("dependencies", "devDependencies"):
        listed = pkg.get(section) or {}
        extra = [name for name in listed if name not in ("@themis/base", "@themis/contracts")]
        if extra:
            problems.append(f"ui 包的 {section} 只许 @themis/base 与 @themis/contracts，多出 {extra}")
    routes = strip_ts_comments(need_file(ROUTES_REL))
    count = len(re.findall(r"public:\s*true", routes))
    if count != 2:
        problems.append(f"routes.ts 里 public: true 应恰好两处（bootstrap 与 control.bootstrap），实际 {count}")
    fail_if(problems, "ui 包依赖与 public 路由（D11/D13）")


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
    missing = [rel for rel in NEW_TEST_RELS if not (REPO_ROOT / rel).is_file()]
    if missing:
        pipe.reason = ("候选里还没有本片的测试文件（基线 3991210，hub 的读写路由还没实现），未装依赖、"
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
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in FAST_GROUP_RELS],
                    "vitest-fast", min(deadline - 120, time.monotonic() + STEP_CAPS["vitest fast"]))
        if not pipe.stopped_reason:
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in REAL_GROUP_RELS],
                    "vitest-real", min(deadline - 20, time.monotonic() + STEP_CAPS["vitest real"]))
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
    """流水线真的跑了（两个新测试文件在位、bun/node 找得到、依赖装好、vitest 起了）。"""
    assert pipeline.ran, pipeline.reason
    assert not pipeline.stopped_reason, f"流水线中途停了：{pipeline.stopped_reason}"


def test_pipeline_fast_group(pipeline):
    """D01/D03–D06/D10/D11 的机械判据：write-argv（W1–W4 改到新事实）、write-config（14 行 × 4 查法）、
    hub-routes（替身用例）、routes-auth/kernel-runner/argv-templates（第 20 条读路由）在 vitest 下全过。"""
    _pipeline_group(pipeline, "vitest-fast")


def test_pipeline_real_kernel(pipeline):
    """D07–D09 的机械判据：hub-routes-real（U9 逐字段一致、U7 的 user-ui、U6b 的 409/stale、不许的绑定）与被
    锁定的 write-real-config 在 vitest 下全过（真内核写配置与审计，只在夹具仓库里）。"""
    _pipeline_group(pipeline, "vitest-real")
