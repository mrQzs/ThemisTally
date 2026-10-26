"""T020 战前门禁：桌面端本机服务第 6 片「profile、runtime 的写路由，令牌不外泄的回归保护，慢请求不被空闲超时断开
（D2 之二）」的黑盒基准测试（合同 t020-desktop-ui-profile v1，基线 00a648ccf9bbc2c6568eb36f6a2f63b807537d34）。

被测对象是 ``ts/packages/ui``：``WRITE_ACTIONS`` 收进 profile/runtime 的五条 action（必填可选、八个新键的校验、
基础 argv 的选项次序与 ``--command=JSON.stringify(command)``）、五条写路由（``POST /api/v1/profiles/<id>/add|edit|remove``、
``POST /api/v1/runtimes/<id>/add|remove``，与既有七条同一条链）、预览正文的顶层键收紧（只许 action 与 args，多出回 400
「参数含有未知键」）、``credential_env`` 的三种写法（缺省不带、非空数组逐项、空数组 400）、U4 收紧
（``OPEN_WRITE_COMMAND_PATHS`` 恰好 12 条、``NOT_OPEN_WRITE_COMMANDS`` 每条带理由、``T020_WRITE_COMMANDS`` 删掉）、
两资源令牌（带 ``--command`` 的 runtime add 与 runtime remove 是 config+local 两段）、令牌不外泄的 12 行 × 4 查法
（预览/执行/操作正文逐段搜不到、替身 report 的 expect_state 与整条令牌逐字相同）、以及空闲超时修复（由内核子进程应答的
请求对这一条请求调 ``server.timeout(request, 0)``，判定用 ``findRoute`` 迟绑定，全局 ``idleTimeout`` 生产路径保持缺省）。

基线（00a648c）上五条 action 不在 ``WRITE_ACTIONS``、``OPEN_WRITE_COMMAND_PATHS``/``NOT_OPEN_WRITE_COMMANDS`` 不存在、
``T020_WRITE_COMMANDS`` 还在、五条路由与三个新测试文件不存在、README 的第 108 行还是「只 SSE」的说法，所以本文件的失败
落在「标记不在」「文件不存在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有仓库文件的读取都发生在用例
函数里；流水线（装依赖之后起 vitest 跑三个新/改测试文件与被锁定的既有用例文件）放在 ``pipeline`` 会话级夹具里，候选里
没有新测试文件时不装依赖、不起 vitest。

结构（编号对应合同 DoD 的 D01–D11；合同 §11 的 13 条变异靠这些断言加被锁定的 Vitest 用例抓，战后门禁另出变异清单）：

- 静态断言（不用流水线，全量 pytest 也跑）：``WRITE_ACTIONS`` 恰好 12 个 action、五个新 action 的必填/可选（D01/D02）；
  ``WRITE_ARGV`` 13 行、12 条命令路径、五条新示例的选项值（D02）；``OPEN_WRITE_COMMAND_PATHS`` 恰好 12 条命令路径、
  ``NOT_OPEN_WRITE_COMMANDS`` 七条各带理由、``T020_WRITE_COMMANDS`` 消失（D04）；``validValue`` 八个新键
  （TASK_ID_RE、MODEL_TOKEN_RE 的正则、thinking 七选一、allowEnvName、adapter 四选一、cleanText 1–1024）（D02）；
  ``buildWriteArgv`` 五个新分支与 ``--opt=值`` 模板、``JSON.stringify``（D02）；五条路由的名字、路径与路径参数键
  ``profile``/``runtime``（D01）；预览正文的顶层键检查在 ``validateWriteArgs`` 之前（D03）；server.ts 的 ``findRoute``
  接线、``.timeout(x, 0)``、``idleTimeout`` 无数字字面量（D06/D08）；harness 的 ``env`` 选项且不写 vitest 进程的
  process.env（D06）；替身的新记号（FAKE_WRITE_SLOW_GATE/FAKE_WRITE_SLEEP_MS/读一支/--json、action 推导、
  ``local=`` 两段令牌）与 T019 记号全保留（D05/D06/D08）；write-config/slow-request/write-real-config（或 write-real
  里的 describe）三个测试文件在位且要点齐备，write-argv.test.ts 的 W2/W4 改到新事实（D01–D06/D11）；README 的 12 条
  写路由、两资源令牌、credential_env 三种写法、第 108 行的空闲超时、已知限制与「T020」保留（D07）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：bun install --frozen-lockfile
  （依赖不齐时）之后起三次 vitest——快的本片与既有写用例（write-argv/write-config/write-routes/confirmations/
  operations）、慢请求用例（slow-request，真 Bun 起服务，约 15 秒）、真内核用例（write-real-config 若存在、加被锁定的
  write-real.test.ts），退出码 0 且 Tests 行 passed。

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
UI_SRC = TS / "packages" / "ui" / "src"

WRITEROUTES_REL = "ts/packages/ui/src/writeroutes.ts"
SERVER_REL = "ts/packages/ui/src/server.ts"
HARNESS_REL = "ts/packages/ui/test/harness.ts"
FAKE_KERNEL_REL = "ts/packages/ui/test/fixtures/fake-write-kernel.mjs"
README_REL = "ts/packages/ui/README.md"
WRITE_ARGV_TEST_REL = "ts/packages/ui/test/write-argv.test.ts"
WRITE_REAL_TEST_REL = "ts/packages/ui/test/write-real.test.ts"
WRITE_REAL_CONFIG_REL = "ts/packages/ui/test/write-real-config.test.ts"

# 合同 Scope：三个新测试文件（write-real-config 允许并进 write-real.test.ts 的一个 describe）
NEW_TEST_RELS = (
    "ts/packages/ui/test/write-config.test.ts",
    "ts/packages/ui/test/slow-request.test.ts",
)
# 流水线连跑的被锁定既有用例（D08：T019 的 write-* 用例一条不推翻）
FAST_GROUP_RELS = (
    "ts/packages/ui/test/write-argv.test.ts",
    "ts/packages/ui/test/write-config.test.ts",
    "ts/packages/ui/test/write-routes.test.ts",
    "ts/packages/ui/test/confirmations.test.ts",
    "ts/packages/ui/test/operations.test.ts",
)
SLOW_GROUP_RELS = ("ts/packages/ui/test/slow-request.test.ts",)

# 合同 Behavior contract：WRITE_ACTIONS 收 12 个 action（既有 7 + 本片 5）
ALL_12_ACTIONS = ("role.set", "preset.use", "preset.save", "preset.remove", "config.rollback",
                  "plugin.enable", "plugin.disable", "profile.add", "profile.edit", "profile.remove",
                  "runtime.add", "runtime.remove")
# 五个新 action 的必填与可选（路径参数算给过了）
T020_ACTION_SPECS = {
    "profile.add": (["profile", "runtime", "model"], ["thinking", "credential_env"]),
    "profile.edit": (["profile"], ["runtime", "model", "thinking", "credential_env"]),
    "profile.remove": (["profile"], []),
    "runtime.add": (["runtime", "adapter"], ["command", "force"]),
    "runtime.remove": (["runtime"], []),
}
# U4：开放的 12 条写命令路径（与内核 --dry-run 集合相等）
OPEN_WRITE_PATHS = (
    ("config", "role", "set"), ("config", "preset", "use"), ("config", "preset", "save"),
    ("config", "preset", "remove"), ("config", "rollback"), ("plugins", "enable"),
    ("plugins", "disable"), ("config", "profile", "add"), ("config", "profile", "edit"),
    ("config", "profile", "remove"), ("config", "runtime", "add"), ("config", "runtime", "remove"),
)
# U4：不开放的写命令（七行：六条具体命令 + 调度器顶层命令一行）
NOT_OPEN_PATH_TOKENS = ("set", "unset", "init", "decisions", "scan", "secret", "prepare", "run", "verdict")
# 五条写路由的名字与路径（Behavior contract 第 1 节的表）
FIVE_ROUTE_NAMES = ("api.profiles.add", "api.profiles.edit", "api.profiles.remove",
                    "api.runtimes.add", "api.runtimes.remove")
# thinking 七选一与 adapter 四选一（合同：scripts/pi_dispatch.py:95、scripts/kit_roles.py:45）
THINKING_ENUM = ("off", "minimal", "low", "medium", "high", "xhigh", "max")
ADAPTER_ENUM = ("pi", "claude-code", "codex", "opencode")
# MODEL_TOKEN_RE 的正则串（合同：照抄 scripts/pi_dispatch.py:86 并注明出处）
MODEL_TOKEN_PATTERN = r"\[A-Za-z0-9\]\[A-Za-z0-9._:/@\+-\]\{0,199\}"

# write-config.test.ts（第 3/5/10 步：五条路由、credential_env、--command、顶层键、12 行 × 4 查法）
WRITE_CONFIG_TEST_TOKENS = (
    (r"startApp", "照 write-routes.test.ts 在进程内建 app"),
    (r"/api/v1/profiles/", "五条路由的 profiles 路径"),
    (r"/api/v1/runtimes/", "五条路由的 runtimes 路径"),
    (r"credential_env", "credential_env 的三种写法"),
    (r"\[\]", "空数组的 credential_env → 400"),
    (r"参数含有未知键", "预览正文多出顶层键 → 400「参数含有未知键」"),
    (r"--command=", "runtime.add 拼 --command= 选项"),
    (r"JSON\.parse", "argv 恰为 --command= 加 JSON.stringify(command)、JSON.parse 逐项相等"),
    (r"expect_state", "替身 report 的 expect_state 与整条令牌逐字相同（第四查）"),
    (r"includes", "令牌逐段 includes 搜不到（预览/执行/操作正文三查）"),
    (r"\{64\}|repeat\(\s*64\s*\)|0x[0-9a-f]", "令牌段的 64 位小写十六进制（每行各不相同）"),
    (r"/api/v1/operations", "第四查之外的八键操作记录查询"),
    (r"confirmation", "预览拿 43 位确认号"),
    (r"fake-write-kernel", "内核用替身"),
)
# slow-request.test.ts（第 9 步：真 Bun、生产 Bun.serve 选项、三条并发）
SLOW_REQUEST_TEST_TOKENS = (
    (r"startService", "真 Bun 服务照 harness 的 startService"),
    (r"overrides\s*:\s*\{\s*\}", "overrides 只传 {}（不传 bunIdleTimeoutSeconds 与 timeouts）"),
    (r"env\s*:", "环境变量经 startService 新加的 env 参数传给服务"),
    (r"FAKE_WRITE_SLOW_GATE", "慢门的门文件（出现后才睡）"),
    (r"FAKE_WRITE_SLEEP_MS", "睡眠时长（毫秒，缺省 15000）"),
    (r"/api/v1/roles", "并发一：读路由 GET /api/v1/roles"),
    (r"/api/v1/preview", "并发二：POST /api/v1/preview"),
    (r"execution", "并发三：写路由 POST /api/v1/roles/execution（带确认号）"),
    (r"90_?000", "用例时限 90 秒（替身睡 15 秒，不靠机器够快）"),
    (r"begin", "替身 report 的 begin 行"),
    (r"end", "三次调用的 begin 都有对应的 end（没被取消）"),
    (r"fake-write-kernel", "内核子进程用替身（不碰真内核）"),
    (r"process\.execPath", "起替身的 python 用 process.execPath"),
)
# write-real-config.test.ts（第 11 步：a–d 四条；或并进 write-real.test.ts 的一个 describe）
WRITE_REAL_CONFIG_TOKENS = (
    (r"THEMIS_PYTHON|pi_dispatch", "真内核用 THEMIS_PYTHON / scripts/pi_dispatch.py"),
    (r"startService", "起真服务照 harness 的 startService"),
    (r"/api/v1/profiles|profile", "(a) profile add：预览加执行"),
    (r"/api/v1/runtimes|runtimes", "(b)(c) runtime add --command 的 U6b 与成功"),
    (r"credential_env", "(d) U22：读到的 credential_env 原样回填 profile.edit"),
    (r"user-ui", "(a) 审计里的 actor 是 user-ui"),
    (r"409", "(b) 预览后改配置：执行回 409"),
    (r"exit_code", "(b) 信封的 exit_code 是 4"),
    (r"stale", "(b) 操作记 stale"),
    (r"逐字节|snapshotAgent", "(b) 配置与审计逐字节不变"),
    (r"\\\\", "(c) 路径含反斜杠与空格（Windows 命令行引号）"),
)
# write-argv.test.ts 的 W2/W4 改到新事实（D04/D11：导出已删、action 已开放）
WRITE_ARGV_TEST_NEW_TOKENS = (
    (r"OPEN_WRITE_COMMAND_PATHS", "W2 用 OPEN_WRITE_COMMAND_PATHS 与内核 --dry-run 集合比对"),
    (r"NOT_OPEN_WRITE_COMMANDS", "W2：不开放名单每条都被内核解析器拒绝、与开放集合不相交"),
    (r"build_parser", "W1/W2 仍用内核真正的解析器"),
    (r"12", "去重后的命令路径恰好 12 条"),
)
# 替身的新记号与必须保留的 T019 记号（下游须知 5：T019 门禁点名的记号保留）
FAKE_KERNEL_NEW_TOKENS = (
    (r"FAKE_KERNEL_REPORT", "begin/end 行照既有替身记进同一份报告（T019 记号）"),
    (r"FAKE_WRITE_PREVIEW", "预览一支由 FAKE_WRITE_PREVIEW 覆盖（T019 记号）"),
    (r"FAKE_WRITE_PLAN", "执行一支按 FAKE_WRITE_PLAN 走（T019 记号）"),
    (r"FAKE_WRITE_GATE", "pause 计划的门文件（T019 记号）"),
    (r"FAKE_WRITE_BEGIN", "pause 先往 stdout 写 FAKE_WRITE_BEGIN（T019 记号）"),
    (r"FAKE_WRITE_SLOW_GATE", "慢门：门文件路径记号（新）"),
    (r"FAKE_WRITE_SLEEP_MS", "睡眠时长记号（新，缺省 15000）"),
    (r"15_?000", "慢门的缺省睡眠 15000 毫秒"),
    (r"--dry-run", "按 argv 里有没有 --dry-run 分两支（T019 记号）"),
    (r"--json", "读一支：argv 带 --json 且无 --dry-run 时打一份 JSON（新）"),
    (r"--expect-state", "执行 argv 记进报告（T019 记号）"),
    (r"profile\.add", "预览一支的 action 由 argv 推导：profile.add"),
    (r"runtime\.add", "推导：runtime.add"),
    (r"runtime\.remove", "推导：runtime.remove"),
    (r"local=", "两资源令牌：v1;config=<C>;local=<L>（runtime.add 带 command 与 runtime.remove）"),
    (r"\"ok\"|'ok'", "计划取值 ok（T019 记号）"),
    (r"\"stale\"|'stale'", "计划取值 stale（T019 记号）"),
    (r"audit-fail", "计划取值 audit-fail（T019 记号）"),
    (r"\"pause\"|'pause'", "计划取值 pause（T019 记号）"),
)

ASSUMPTIONS = (
    "「WRITE_ARGV 的行数」按「引号键开头、冒号、左方括号」的行数计（13 行：role.set 两行示例 + 其余 11 条 action 各一行，"
    "合同写死表共 13 行、命令路径去重 12 条）；键名本身五个新行按合同写死（profile.add 等），role.set 的第二行键名不查",
    "「NOT_OPEN_WRITE_COMMANDS 每条带理由」按块内 reason 键出现至少 7 次 + 七行的路径记号（set/unset/init/decisions/"
    "scan/secret 与 prepare/run/verdict）都在判；理由的文字内容不逐字断言（合同只给了一行理由的要点）",
    "「预览正文的顶层键检查」按 previewRoute 函数体里出现「参数含有未知键」且在 validateWriteArgs 调用之前判；实现若把"
    "检查抽成单独的函数，把它挪回 previewRoute 或让提示在该函数体里出现即可，行为面（report 无 begin 行）由被锁定的 "
    "write-config.test.ts 钉住",
    "「server.ts 的空闲超时修复」静态面只查 findRoute 已接进 server.ts、.timeout(x, 0) 仍在、idleTimeout 无数字字面量；"
    "「迟绑定（两批建好之前不判定）」与「读路由/预览/写路由三批都放宽」是运行时行为，由 slow-request.test.ts（真 Bun、"
    "生产选项）钉住，静态不猜变量名",
    "「harness 的 env 只合进服务子进程」静态面查 StartOptions 里有 env 且 harness.ts 不出现对 process.env 的赋值；"
    "「不改 vitest 进程的 process.env」按这个负向正则判",
    "「替身预览一支的 action 推导」按 fixture 里出现 profile.add/runtime.add/runtime.remove 的字样判（推导需要一张"
    "命令路径到 action 名的映射表，plugins→plugin 的单复数差异使纯拼接不可行）；若实现用别的推导法，让这三个 action 名"
    "在 fixture 里出现即可",
    "「write-real-config.test.ts」合同允许并进 write-real.test.ts 的一个 describe：token 按两份文件里存在的那份判",
    "slow-request.test.ts 里不许出现 bunIdleTimeoutSeconds 与「timeouts:」（合同：overrides 只传 {}）；注释里提到"
    "「timeouts」不带冒号不受影响",
    "流水线预算 480 秒（G01 的 600 秒减去静态用例与 pytest 自身开销）：依赖装好时三组 vitest 实测远小于预算；bun install "
    "只在依赖不齐时跑（候选做完 S01 之后不会跑）",
)

# 流水线预算：合同 G01 的超时是 600 秒，留出静态用例与 pytest 自身的开销。
PIPELINE_BUDGET = 480
STEP_CAPS = {"bun install": 200, "vitest write": 300, "vitest slow": 200, "vitest real": 240}

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
    """argv 模板片段在不在：连写（``config role set``）或相邻的数组元素（``"config", "role", "set"``）都算。"""
    if " ".join(parts) in code:
        return True
    for quote in ('"', "'"):
        elems = ("," + r"\s*").join(quote + re.escape(part) + quote for part in parts)
        if re.search(elems, code) is not None:
            return True
    return False


def _number_written(code, value):
    """数字字面量在不在（86400 与 86_400 都认）。"""
    digits = str(value)
    sep = r"_?" if len(digits) > 3 else ""
    pattern = digits[0] + "".join(sep + d for d in digits[1:])
    return re.search(pattern, code) is not None


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
# 静态断言：writeroutes.ts（登记、校验、argv、五条路由、顶层键）
# ---------------------------------------------------------------------------

def test_static_write_actions_registry():
    """D01/D02/D04（M13）：``WRITE_ACTIONS`` 恰好 12 个 action（既有 7 + 本片 5），五个新 action 的必填/可选照
    合同的表；``T020_WRITE_COMMANDS`` 这个导出删掉（U4）。"""
    code = strip_ts_comments(need_file(WRITEROUTES_REL))
    problems = []
    if "WRITE_ACTIONS" not in code:
        problems.append("writeroutes.ts 应有 WRITE_ACTIONS 登记表（导出）")
    else:
        block = _block(code, "WRITE_ACTIONS", "\n};")
        entries = dict(re.findall(r'(?m)^[ \t]*"([^"]+)"\s*:\s*\{([^}]*)\}', block))
        if len(entries) != 12:
            problems.append(f"WRITE_ACTIONS 应恰好 12 个 action，实际 {len(entries)}：{sorted(entries)}")
        for action in ALL_12_ACTIONS:
            if action not in entries:
                problems.append(f"WRITE_ACTIONS 里应有「{action}」")
        for action, (required, optional) in T020_ACTION_SPECS.items():
            body = entries.get(action)
            if body is None:
                continue
            if "required" not in body or "optional" not in body:
                problems.append(f"{action} 的登记应写 required 与 optional")
                continue
            for key in required:
                if f'"{key}"' not in body:
                    problems.append(f"{action} 的必填键「{key}」不在登记表里")
            if optional:
                for key in optional:
                    if f'"{key}"' not in body:
                        problems.append(f"{action} 的可选键「{key}」不在登记表里")
            elif "[]" not in body:
                problems.append(f"{action} 没有可选项，optional 应是空数组")
    if "T020_WRITE_COMMANDS" in code:
        problems.append("T020_WRITE_COMMANDS 这个导出应删掉（U4：改由 OPEN_WRITE_COMMAND_PATHS 与 NOT_OPEN_WRITE_COMMANDS 表达）")
    fail_if(problems, "WRITE_ACTIONS（D01/D02/D04）")


def test_static_open_and_not_open_lists():
    """D04（U4）：``OPEN_WRITE_COMMAND_PATHS`` 恰好 12 条命令路径；``NOT_OPEN_WRITE_COMMANDS`` 每条
    ``{ path, reason }``（七行：config set/unset/init/decisions/runtime scan/secret 与调度器顶层命令）。"""
    code = strip_ts_comments(need_file(WRITEROUTES_REL))
    problems = []
    if "OPEN_WRITE_COMMAND_PATHS" not in code:
        problems.append("writeroutes.ts 应导出 OPEN_WRITE_COMMAND_PATHS（W2 与内核 --dry-run 集合比对）")
    else:
        block = _block(code, "OPEN_WRITE_COMMAND_PATHS")
        for path in OPEN_WRITE_PATHS:
            if not _argv_written(block, *path):
                problems.append(f"OPEN_WRITE_COMMAND_PATHS 里应有「{' '.join(path)}」")
    if "NOT_OPEN_WRITE_COMMANDS" not in code:
        problems.append("writeroutes.ts 应导出 NOT_OPEN_WRITE_COMMANDS（每条 { path, reason }）")
    else:
        block = _block(code, "NOT_OPEN_WRITE_COMMANDS")
        if "path" not in block:
            problems.append("NOT_OPEN_WRITE_COMMANDS 的条目应有 path 键")
        if len(re.findall(r"\breason\b", block)) < 7:
            problems.append("NOT_OPEN_WRITE_COMMANDS 应有七行、每行一个 reason（每条写一行理由）")
        for token in NOT_OPEN_PATH_TOKENS:
            if re.search(rf"[\"']{re.escape(token)}[\"']", block) is None:
                problems.append(f"NOT_OPEN_WRITE_COMMANDS 里应有命令路径记号「{token}」")
    fail_if(problems, "OPEN / NOT_OPEN 名单（D04）")


def test_static_write_argv_table():
    """D02：``WRITE_ARGV`` 加五条示例（表共 13 行、命令路径去重 12 条），示例的选项值照合同写死（--runtime=、
    --model=、--thinking=high、两个 --credential-env、--adapter=pi、--command=[\"C:/tools/pi.exe\",\"--flag\"]、--force）。"""
    code = strip_ts_comments(need_file(WRITEROUTES_REL))
    problems = []
    if "WRITE_ARGV" not in code:
        problems.append("writeroutes.ts 应有 WRITE_ARGV 登记表（导出）")
    else:
        block = _block(code, "WRITE_ARGV")
        rows = re.findall(r"(?m)^[ \t]*[\"']([^\"']+)[\"']\s*:\s*\[", block)
        if len(rows) != 13:
            problems.append(f"WRITE_ARGV 应有 13 行示例（role.set 两行），实际 {len(rows)}")
        for action in ("profile.add", "profile.edit", "profile.remove", "runtime.add", "runtime.remove"):
            if action not in rows:
                problems.append(f"WRITE_ARGV 的键里应有「{action}」")
        # 12 条命令路径（去重后）都在示例表里
        for path in OPEN_WRITE_PATHS:
            if not _argv_written(block, *path):
                problems.append(f"WRITE_ARGV 里应有「{' '.join(path)}」的示例")
        for sample in ("demo-profile", "demo-runtime", "--runtime=demo-runtime", "--model=demo-provider/demo-model",
                       "--thinking=high", "--credential-env=DEMO_API_KEY", "--credential-env=OTHER_KEY",
                       "--adapter=pi", "C:/tools/pi.exe", "--flag", "--force"):
            if sample not in block:
                problems.append(f"WRITE_ARGV 的新示例值「{sample}」不在登记表里（合同 Behavior contract）")
    fail_if(problems, "WRITE_ARGV（D02）")


def test_static_valid_value_new_keys():
    """D02（M1）：``validValue`` 加八个新键——profile/runtime 过 TASK_ID_RE、model 过 MODEL_TOKEN_RE（切两段）、
    thinking 七选一、credential_env 过 allowEnvName（非空数组）、adapter 四选一、command 每项 cleanText(1, 1024)、
    force 只认 true。"""
    code = strip_ts_comments(need_file(WRITEROUTES_REL))
    problems = []
    block = _block(code, "function validValue", "\n}")
    if not block:
        problems.append("writeroutes.ts 应有 validValue（预览与写路由共用的单键校验）")
    else:
        for key in ("profile", "runtime", "model", "thinking", "credential_env", "adapter", "command", "force"):
            if f'"{key}"' not in block:
                problems.append(f"validValue 应处理「{key}」（八个新键）")
        if "TASK_ID_RE" not in block:
            problems.append("profile/runtime 应过 TASK_ID_RE（与读路由同源）")
    if "MODEL_TOKEN_RE" not in code or re.search(MODEL_TOKEN_PATTERN, code) is None:
        problems.append("model 的校验应有 MODEL_TOKEN_RE（^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}$，照抄 pi_dispatch.py:86）")
    for value in THINKING_ENUM:
        if f'"{value}"' not in code:
            problems.append(f"thinking 的取值「{value}」不在 writeroutes.ts（七选一）")
    for value in ADAPTER_ENUM:
        if f'"{value}"' not in code:
            problems.append(f"adapter 的取值「{value}」不在 writeroutes.ts（四选一）")
    if "allowEnvName" not in code:
        problems.append("credential_env 每项应过 allowEnvName（@themis/base/secrets，不像令牌）")
    if "cleanText" not in code or not _number_written(code, 1024):
        problems.append("command 每项应过 cleanText(item, 1, 1024)（1–1024 码点）")
    fail_if(problems, "validValue 的八个新键（D02）")


def test_static_build_argv_new_branches():
    """D02（M2/M3）：``buildWriteArgv`` 加五个新分支，选项一律 ``--opt=值``（--runtime/--model/--thinking/
    --credential-env/--adapter/--command），``--command`` 的值是 ``JSON.stringify(command)``，``--force`` 只在
    force 为真时出现。"""
    code = strip_ts_comments(need_file(WRITEROUTES_REL))
    problems = []
    block = _block(code, "export function buildWriteArgv", "\n}")
    if not block:
        problems.append("writeroutes.ts 应导出 buildWriteArgv")
    else:
        for action in ("profile.add", "profile.edit", "profile.remove", "runtime.add", "runtime.remove"):
            if f'"{action}"' not in block:
                problems.append(f"buildWriteArgv 应有「{action}」分支")
        for opt in ("--runtime=", "--model=", "--thinking=", "--credential-env=", "--adapter=", "--command=", "--force"):
            if opt not in block:
                problems.append(f"buildWriteArgv 应拼「{opt}值」（选项的值一律 --opt=值）")
        if "JSON.stringify" not in block:
            problems.append("--command 的值应是 JSON.stringify(command) 的结果（不加引号、不转义）")
    fail_if(problems, "buildWriteArgv 的五个新分支（D02）")


def test_static_five_routes():
    """D01：五条写路由的名字（api.profiles.add|edit|remove、api.runtimes.add|remove）与路径
    （/api/v1/profiles/<id>/add|edit|remove、/api/v1/runtimes/<id>/add|remove），路径参数键 ``profile`` 与
    ``runtime``（路径参数压正文同名键，照 mergeArgs 原样）。"""
    code = strip_ts_comments(need_file(WRITEROUTES_REL))
    problems = []
    block = _block(code, "export function writeRoutes", "\n}")
    if not block:
        problems.append("writeroutes.ts 应导出 writeRoutes")
    else:
        for name in FIVE_ROUTE_NAMES:
            if f'"{name}"' not in block and f"'{name}'" not in block:
                problems.append(f"写路由「{name}」不见了（合同 Behavior contract 第 1 节的表）")
        unescaped = block.replace("\\/", "/")
        for prefix in ("/api/v1/profiles/", "/api/v1/runtimes/"):
            if prefix not in unescaped:
                problems.append(f"路径「{prefix}…」不在 writeRoutes")
        for tail in ("/add", "/edit", "/remove"):
            if tail not in unescaped:
                problems.append(f"路径尾段「…{tail}」不在 writeRoutes")
        if re.search(r"\{\s*profile\s*:\s*params", block) is None:
            problems.append("profiles 三条路由的路径参数键应是 profile")
        if re.search(r"\{\s*runtime\s*:\s*params", block) is None:
            problems.append("runtimes 两条路由的路径参数键应是 runtime")
    fail_if(problems, "五条写路由（D01）")


def test_static_preview_top_level_keys():
    """D03（M12）：预览正文的顶层键只许 action 与 args——多出任何键回 400「参数含有未知键」，在
    ``validateWriteArgs`` 之前判、不起子进程；缺 action/缺 args 的两条既有提示原样保留。"""
    code = strip_ts_comments(need_file(WRITEROUTES_REL))
    problems = []
    block = _block(code, "async function previewRoute", "\n}")
    if not block:
        problems.append("writeroutes.ts 应有 previewRoute（POST /api/v1/preview）")
    else:
        i_top = block.find("参数含有未知键")
        i_valid = block.find("validateWriteArgs")
        if i_top < 0:
            problems.append("previewRoute 应对正文多出的顶层键回 400「参数含有未知键」")
        elif 0 <= i_valid < i_top:
            problems.append("顶层键的检查应在 validateWriteArgs 之前（多出的键不进内核校验，也不起子进程）")
        for message in ("请求体必须是 JSON 对象", "action 不合法"):
            if message not in code:
                problems.append(f"既有提示原文「{message}」应保留")
    fail_if(problems, "预览正文的顶层键（D03）")


# ---------------------------------------------------------------------------
# 静态断言：server.ts（空闲超时修复）、harness.ts（env）、替身
# ---------------------------------------------------------------------------

def test_static_server_timeout_relief():
    """D06/D08（M9/M10/M11 的静态面）：server.ts 用 routes.ts 的 ``findRoute`` 判定请求命中的是不是内核子进程应答的
    那两批路由（readRoutes/writeRoutes，不另抄路径表），命中就对这一条请求调 ``.timeout(request, 0)``；全局
    ``idleTimeout`` 生产路径保持缺省（不许数字字面量，只由 bunIdleTimeoutSeconds 覆盖）——T017 门禁的口径不动。"""
    server = strip_ts_comments(need_file(SERVER_REL))
    problems = []
    for token in ("findRoute", "readRoutes", "writeRoutes", "bunIdleTimeoutSeconds", "isEventsRequest"):
        if token not in server:
            problems.append(f"server.ts 里看不到「{token}」")
    if re.search(r"\.timeout\(\s*\w+\s*,\s*0\s*\)", server) is None:
        problems.append("应对这一条请求调 server.timeout(request, 0)（SSE 与内核子进程应答的请求）")
    for m in re.finditer(r"idleTimeout\s*[:=]\s*\d", server):
        problems.append(f"生产路径不许给 idleTimeout 设数字字面量（T017 门禁），位置：{server[m.start():m.end()]!r}")
        break
    fail_if(problems, "server.ts 的空闲超时修复（D06/D08）")


def test_static_harness_env_option():
    """D06：harness 的 ``StartOptions`` 加 ``env``，只合进服务子进程的环境（不写 vitest 进程的 process.env）；
    内核子进程的环境来自 kernelEnv()（读服务进程的 process.env），所以 env 能传到替身。"""
    code = strip_ts_comments(need_file(HARNESS_REL))
    problems = []
    iface = _block(code, "export interface StartOptions", "\n}")
    if re.search(r"\benv\b", iface) is None:
        problems.append("StartOptions 应有 env 选项（环境变量经它传给服务子进程）")
    for m in re.finditer(r"process\.env(?:\[[^\]]*\]|\.\w+)\s*=[^=]", code):
        problems.append("harness.ts 不许给 vitest 进程的 process.env 赋值（env 只合进服务子进程的环境）")
        break
    if "childEnv" not in code:
        problems.append("服务子进程的环境合并（childEnv）应保留")
    fail_if(problems, "harness 的 env 选项（D06）")


def test_static_fake_kernel_extended():
    """D05/D06/D08：替身保留 T019 门禁点名的记号与 §2.1 的默认预览；新加慢门（FAKE_WRITE_SLOW_GATE 门文件、
    FAKE_WRITE_SLEEP_MS 毫秒、缺省 15000，门文件出现后才睡）、读一支（argv 带 --json 且无 --dry-run 时打一份 JSON）、
    预览一支的 action 由 argv 推导、两资源令牌（runtime.add 带 command 与 runtime.remove 给 config+local 两段）。"""
    raw = need_file(FAKE_KERNEL_REL)
    code = strip_ts_comments(raw)
    problems = _token_problems(code, FAKE_KERNEL_NEW_TOKENS)
    fail_if(problems, "替身 fake-write-kernel.mjs 的记号（D05/D06/D08）")


# ---------------------------------------------------------------------------
# 静态断言：三个新测试文件与 write-argv.test.ts 的更新
# ---------------------------------------------------------------------------

def test_static_new_test_files():
    """D01–D06/D11：三个新测试文件在位且要点齐备（write-config：五条路由、credential_env 三种写法、--command 的
    JSON、顶层键 400、12 行 × 4 查法；slow-request：真 Bun、overrides 只传 {}、env、慢门、三条并发、90 秒时限；
    write-real-config 或 write-real 里的 describe：真内核四条），不许出现 skip、only、todo。"""
    problems = []
    for rel in NEW_TEST_RELS + (WRITE_REAL_CONFIG_REL,):
        if not (REPO_ROOT / rel).is_file() and rel != WRITE_REAL_CONFIG_REL:
            problems.append(f"{rel} 不存在（合同 Steps 锁定的基准测试文件）")
    if problems:
        fail_if(problems, "基准测试文件在位")
        return
    checks = (
        ("ts/packages/ui/test/write-config.test.ts", WRITE_CONFIG_TEST_TOKENS),
        ("ts/packages/ui/test/slow-request.test.ts", SLOW_REQUEST_TEST_TOKENS),
    )
    for rel, tokens in checks:
        text = need_file(rel)
        stripped = strip_ts_comments(text)
        problems += [f"{rel}：{p}" for p in _token_problems(stripped, tokens)]
        problems += [f"{rel}：{p}" for p in _no_skip_marks(stripped)]
    # write-config 的 12 行令牌表：12 个 action 每个一行
    config_text = strip_ts_comments(need_file("ts/packages/ui/test/write-config.test.ts"))
    for action in ALL_12_ACTIONS:
        if f'"{action}"' not in config_text and f"'{action}'" not in config_text:
            problems.append(f"write-config.test.ts 的令牌表应有一行「{action}」（12 行 × 4 查法）")
    # slow-request：不传 bunIdleTimeoutSeconds 与 timeouts（走生产的 Bun.serve 选项）
    slow_text = strip_ts_comments(need_file("ts/packages/ui/test/slow-request.test.ts"))
    if "bunIdleTimeoutSeconds" in slow_text:
        problems.append("slow-request.test.ts 不许传 bunIdleTimeoutSeconds（全局 idleTimeout 生产路径保持缺省）")
    if re.search(r"timeouts\s*:", slow_text):
        problems.append("slow-request.test.ts 不许传 timeouts（走生产的时限）")
    # 真内核四条：write-real-config.test.ts 或 write-real.test.ts 里的一个 describe
    if (REPO_ROOT / WRITE_REAL_CONFIG_REL).is_file():
        real_rel = WRITE_REAL_CONFIG_REL
    else:
        real_rel = WRITE_REAL_TEST_REL
    real_text = strip_ts_comments(need_file(real_rel))
    problems += [f"{real_rel}：{p}" for p in _token_problems(real_text, WRITE_REAL_CONFIG_TOKENS)]
    problems += [f"{real_rel}：{p}" for p in _no_skip_marks(real_text)]
    fail_if(problems, "三个新测试文件的要点（D01–D06/D11）")


def test_static_write_argv_test_updated():
    """D04/D11：write-argv.test.ts 的 W2 从 ``OPEN_WRITE_COMMAND_PATHS`` 取期望集合、W4 改成五个 T020 action
    已开放（12 个 action 的登记表断言）；``T020_WRITE_COMMANDS`` 的引用删掉（导出已删，import 会编译失败）。"""
    code = strip_ts_comments(need_file(WRITE_ARGV_TEST_REL))
    problems = _token_problems(code, WRITE_ARGV_TEST_NEW_TOKENS)
    if "T020_WRITE_COMMANDS" in code:
        problems.append("write-argv.test.ts 不应再引用 T020_WRITE_COMMANDS（导出已删，D11 是改断言不是留旧引用）")
    for action in ("profile.add", "profile.edit", "profile.remove", "runtime.add", "runtime.remove"):
        if f'"{action}"' not in code and f"'{action}'" not in code:
            problems.append(f"write-argv.test.ts 的登记表断言应包含「{action}」（12 个 action 的新事实）")
    problems += _no_skip_marks(code)
    fail_if(problems, "write-argv.test.ts 的 W2/W4 改到新事实（D04/D11）")


# ---------------------------------------------------------------------------
# 静态断言：README
# ---------------------------------------------------------------------------

def _section(text, heading):
    head = text.find(heading)
    if head < 0:
        return None
    tail = text.find("\n## ", head + 1)
    return text[head:tail if tail > 0 else len(text)]


def test_static_readme():
    """D07：README 与行为同步——「写操作」一节改成 12 条写路由（profile、runtime、两资源令牌、credential_env 的
    三种写法含空数组 400）；「最小 API」补五条写路由；第 108 行那条连接空闲超时改成「SSE 与由内核子进程应答的请求
    对这一条请求调 server.timeout(req, 0)」；已知限制写 credential_env 清不空；删掉 T020_WRITE_COMMANDS 的说法、
    至少保留一处「T020」（T019 门禁 test_static_readme 查这个词）。"""
    text = need_file(README_REL)
    problems = []
    if "T020" not in text:
        problems.append("README 应至少保留一处「T020」（T019 门禁 test_static_readme 查这个词）")
    if "T020_WRITE_COMMANDS" in text:
        problems.append("README 里提到 T020_WRITE_COMMANDS 的地方应一并改掉（导出已删）")
    section = _section(text, "## 写操作")
    if section is None:
        problems.append("README 应有「## 写操作」一节")
    else:
        if re.search(r"12\s*条写路由", section) is None:
            problems.append("「写操作」一节应写成 12 条写路由（本片接进 profile 与 runtime）")
        for needle in ("profile", "runtime", "credential_env", "credential_env 不合法", "空数组", "local"):
            if needle not in section:
                problems.append(f"「写操作」一节里看不到「{needle}」（D07 点名要写的结论）")
    for needle in ("/profiles/<", "/runtimes/<"):
        if needle not in text:
            problems.append(f"README 的最小 API 应补五条写路由（看不到「{needle}…」）")
    at = text.find("连接空闲超时")
    if at < 0:
        problems.append("README 应保留「连接空闲超时」那一条")
    else:
        bullet_end = text.find("\n- ", at)
        bullet = text[at:bullet_end if bullet_end > 0 else at + 600]
        for needle in ("server.timeout(req, 0)", "读路由", "预览", "12 条"):
            if needle not in bullet:
                problems.append(f"「连接空闲超时」那一条应写到由内核子进程应答的请求（看不到「{needle}」）")
    limits = _section(text, "## 已知限制")
    if limits is None:
        problems.append("README 应有「## 已知限制」一节")
    else:
        if "credential_env" not in limits:
            problems.append("「已知限制」应写 credential_env 清不空（内核没有清空的写法）")
        if "清空" not in limits and "清不空" not in limits:
            problems.append("「已知限制」应写清 credential_env 清不空这件事")
    fail_if(problems, "README（D07）")


# ---------------------------------------------------------------------------
# 会话级流水线夹具：vitest 跑三个新/改测试文件与被锁定的既有用例文件
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
        pipe.reason = ("候选里还没有本片的测试文件（基线 00a648c，profile/runtime 的写链路还没实现），未装依赖、"
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
                    "vitest-write", min(deadline - 120, time.monotonic() + STEP_CAPS["vitest write"]))
        if not pipe.stopped_reason:
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in SLOW_GROUP_RELS],
                    "vitest-slow", min(deadline - 60, time.monotonic() + STEP_CAPS["vitest slow"]))
        if not pipe.stopped_reason:
            real_files = [rel.removeprefix("ts/") for rel in
                          ([WRITE_REAL_CONFIG_REL] if (REPO_ROOT / WRITE_REAL_CONFIG_REL).is_file() else [])
                          + [WRITE_REAL_TEST_REL]]
            _vitest(pipe, node, real_files, "vitest-real",
                    min(deadline - 20, time.monotonic() + STEP_CAPS["vitest real"]))
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


def test_pipeline_write_tests(pipeline):
    """D01–D05/D11 的机械判据：write-argv（W1–W4 改到新事实）、write-config（五条路由、credential_env、12 行 × 4
    查法）与 T019 的 write-routes/confirmations/operations 在 vitest 下全过（既有断言一条不推翻）。"""
    _pipeline_group(pipeline, "vitest-write")


def test_pipeline_slow_request(pipeline):
    """D06 的机械判据：slow-request.test.ts 在 vitest 下全过（真 Bun 服务、生产 Bun.serve 选项，三条并发都拿到
    完整响应，替身三次调用都有 end 且退出码 0）。"""
    _pipeline_group(pipeline, "vitest-slow")


def test_pipeline_real_kernel(pipeline):
    """D01/D02/D04 的真内核判据：write-real-config（若存在）与被锁定的 write-real.test.ts 在 vitest 下全过
    （W2 的集合比对、U6b 的 409、--command 的 Windows 引号、U22 的 credential_env 回填）。"""
    _pipeline_group(pipeline, "vitest-real")
