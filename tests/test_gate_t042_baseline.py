"""T042 战前门禁：桌面端前端第 8 片 A 片「本机服务的 Quizs 两条读路由」（模型配置 M3、M4 之三）的黑盒基准测试
（合同 t042-desktop-web-quizs-facts v1，基线 53f2d47aa56dfdcacc868a9589384c423fc803ec）。

被测对象是 ``ts/packages/ui``：两条只读路由 ``api.quizs.providers.get``（``GET /api/v1/quizs/providers`` →
``config quizs providers --json``，时限 60 秒）与 ``api.quizs.live.get``（``GET /api/v1/quizs/live`` →
``config quizs live --json``，时限 150 秒），登记为 READ_ROUTE_SPECS 的第 21、22 条（时限常量
``QUIZS_PROVIDERS_TIMEOUT``/``QUIZS_LIVE_TIMEOUT``，``server.ts`` 不改）；redaction.ts 的两份逐字段白名单
``QUIZS_PROVIDERS_ALLOW``（4 条路径：provider/model 用 allowBindingName、thinking.* 六档枚举、billing 三值枚举）
与 ``QUIZS_LIVE_ALLOW``（8 条路径：source/provider/problem/status.problem/state/missing.*/certificate.expires_at_ms/
profile.valid_until）加五个枚举与三个可空校验函数；三份既有用例照新行为改到 22 条（routes-auth 的示例表与条数、
kernel-runner 的 CASES 与时限数组含 60/150、argv-templates 的长度）；新用例文件 ``quizs-routes.test.ts``
（替身 + 真内核，真内核的 QUIZS_CMD 指向夹具里的假 Quizs 脚本）；README 的条数与路由表同步到 22。

基线（53f2d47）上两条路由、两份白名单、五个枚举、新测试文件与 README 的 22 条说法都不存在，所以本文件的失败落在
「标记不在」「文件不存在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有仓库文件的读取都发生在
用例函数里；流水线（装依赖之后起 vitest 跑新测试文件、被改的既有用例与一份行为探针）放在 ``pipeline`` 会话级夹具里，
候选里没有新测试文件时不装依赖、不起 vitest（照 T031 门禁的写法）。

结构（编号对应合同 DoD 的 D01–D08；战后门禁另出变异清单）：

- 静态断言（不用流水线，全量 pytest 也跑）：readroutes.ts 的两条路由、argv 模板、时限常量、第 21/22 条登记、
  条数注释 22 与「第 20 条」原文保留（D01）；redaction.ts 的五个枚举、两份白名单恰好 4+8 条路径、三类可空校验
  的记号（自由文字、非负整数毫秒、带毫秒的 ISO 8601 UTC——按整份文件的范围判在，语义由行为探针钉）、
  HUB_ROLES_ALLOW 等既有面不推翻（D02）；三份既有用例改到 22（D04）；新测试文件在位且要点齐备（D03/D05）；
  README（D06）；共享面：routes.ts 的 public 恰两处、ui 包依赖、server.ts 不出现 quizs（D07/D08 的回归面）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：bun install --frozen-lockfile
  （依赖不齐时）之后起三次 vitest——quizs-routes（替身 + 真内核）、被锁定的 routes-auth/kernel-runner/
  argv-templates/hub-routes，以及一份行为探针（临时写进 ``ts/packages/ui/test/gate-probe/``，跑完即删）：探针
  直接对两份白名单跑 ``redactJson``，钉住放行/越界遮/凭据形状遮的语义——这些行为执行端的替身用例只覆盖一部分
  （比如 valid_until 少了毫秒、expires_at_ms 是负数），探针补上。

合同没有写死、门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：见 ``ASSUMPTIONS``。
"""

import json
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
TS = REPO_ROOT / "ts"

READROUTES_REL = "ts/packages/ui/src/readroutes.ts"
REDACTION_REL = "ts/packages/ui/src/redaction.ts"
ROUTES_REL = "ts/packages/ui/src/routes.ts"
SERVER_REL = "ts/packages/ui/src/server.ts"
UI_PACKAGE_REL = "ts/packages/ui/package.json"
README_REL = "ts/packages/ui/README.md"
ROUTES_AUTH_REL = "ts/packages/ui/test/routes-auth.test.ts"
KERNEL_RUNNER_REL = "ts/packages/ui/test/kernel-runner.test.ts"
ARGV_TEMPLATES_REL = "ts/packages/ui/test/argv-templates.test.ts"

# 合同 Scope：唯一的新测试文件（其余三份是「照新行为改」的既有用例）
NEW_TEST_RELS = ("ts/packages/ui/test/quizs-routes.test.ts",)
# 流水线连跑：新测试文件（替身 + 真内核都在里面）与被改/相邻的被锁定既有用例
QUIZS_GROUP_RELS = ("ts/packages/ui/test/quizs-routes.test.ts",)
LOCKED_GROUP_RELS = (
    "ts/packages/ui/test/routes-auth.test.ts",
    "ts/packages/ui/test/kernel-runner.test.ts",
    "ts/packages/ui/test/argv-templates.test.ts",
    "ts/packages/ui/test/hub-routes.test.ts",
)

# 既有 20 条读路由的名字（合同 Repository facts）：一条不许少
OLD_20_SPECS = (
    "api.meta.get", "api.status.get", "api.attempts.list", "api.attempts.show", "api.attempts.file",
    "api.usage.get", "api.config.get", "api.config.validate", "api.config.history.list", "api.config.history.show",
    "api.roles.get", "api.profiles.get", "api.presets.list", "api.presets.diff", "api.runtimes.get",
    "api.plugins.list", "api.plugins.show", "api.secrets.list", "api.secrets.show", "api.hub.roles.get",
)
# 两条新路由（合同 Behavior contract）
QUIZS_ROUTES = (
    ("api.quizs.providers.get", "/api/v1/quizs/providers", "QUIZS_PROVIDERS_TIMEOUT", 60, "QUIZS_PROVIDERS_ALLOW",
     ("config", "quizs", "providers", "--json")),
    ("api.quizs.live.get", "/api/v1/quizs/live", "QUIZS_LIVE_TIMEOUT", 150, "QUIZS_LIVE_ALLOW",
     ("config", "quizs", "live", "--json")),
)
# 两份白名单的路径（合同 Behavior contract 的白名单一节，逐条）
PROVIDERS_ALLOW_PATHS = (
    ("providers", "*", "provider"),
    ("providers", "*", "model"),
    ("providers", "*", "thinking", "*"),
    ("providers", "*", "billing"),
)
LIVE_ALLOW_PATHS = (
    ("live", "*", "source"),
    ("live", "*", "provider"),
    ("live", "*", "problem"),
    ("live", "*", "status", "problem"),
    ("live", "*", "status", "state"),
    ("live", "*", "status", "missing", "*"),
    ("live", "*", "status", "certificate", "expires_at_ms"),
    ("live", "*", "status", "profile", "valid_until"),
)
# 五个枚举（取值抄自 scripts/kit_roles.py 与站主核实的 Quizs 输出形状）
QUIZS_ENUMS = (
    ("QUIZS_THINKING_ENUM", ("off", "low", "medium", "high", "xhigh", "max")),
    ("QUIZS_BILLING_ENUM", ("none_test_only", "step_plan_credits", "deepseek_prepaid_balance")),
    ("QUIZS_LIVE_SOURCE_ENUM", ("mailbox", "env")),
    ("QUIZS_LIVE_STATE_ENUM", ("ready", "expired", "build_mismatch", "invalid", "missing")),
    ("QUIZS_LIVE_FILE_ENUM", ("plan.json", "profile.json", "qualification.json")),
)
# HUB_ROLES_ALLOW 的 15 条路径（T031 合同；本片不许动它）
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
# 超时信封的提示原文（时限覆盖成 1 秒的那条用例；合同边界输入一节）
TIMEOUT_MESSAGE = "命令超时（1 秒），子进程已结束；请改用 CLI 查看"

# quizs-routes.test.ts（合同第六节：替身部分 + 真内核部分都在这一个文件里）
QUIZS_TEST_TOKENS = (
    (r"startApp", "替身部分照 kernel-runner/support.ts 的 startApp 起进程内应用"),
    (r"FAKE_KERNEL_JSON", "替身用 FAKE_KERNEL_JSON 给 quizs 形状的 JSON"),
    (r"/api/v1/quizs/providers", "providers 路由的路径"),
    (r"/api/v1/quizs/live", "live 路由的路径"),
    (r"""["']config["']\s*,\s*["']quizs["']\s*,\s*["']providers["']\s*,\s*["']--json["']|READ_ROUTE_ARGV\["api\.quizs\.providers\.get"\]""",
     "providers 的 argv 逐字是 config quizs providers --json（数组元素允许换行与任意空白）"),
    (r"""["']config["']\s*,\s*["']quizs["']\s*,\s*["']live["']\s*,\s*["']--json["']|READ_ROUTE_ARGV\["api\.quizs\.live\.get"\]""",
     "live 的 argv 逐字是 config quizs live --json（数组元素允许换行与任意空白）"),
    (r"ENVELOPE_KEYS|elapsed_ms", "信封七字段齐全（ok/exit_code/data/output/messages/command/elapsed_ms）"),
    (r"<redacted>", "越界的枚举值/凭据形状的值变成 <redacted>"),
    (r"credential_ref|access_tokens", "凭据形状的键（credential_ref、*_tokens）默认遮掉"),
    (r"FAKE_KERNEL_EXIT", "退出码用例（FAKE_KERNEL_EXIT 时回 200、ok 假、exit_code 原样）"),
    (r"FAKE_KERNEL_SLEEP_MS", "超时用例用 FAKE_KERNEL_SLEEP_MS 拖住子进程"),
    (r"timeouts", "超时用例经 startApp 的 timeouts 覆盖路由时限"),
    (r"504", "超时回 504"),
    (r"命令超时（1 秒），子进程已结束；请改用 CLI 查看", "超时信封的提示原文（时限覆盖成 1 秒）"),
    (r"QUIZS_CMD", "真内核用例把 QUIZS_CMD 指向夹具里的假 Quizs 脚本"),
    (r"THEMIS_PYTHON", "真内核的解释器用 THEMIS_PYTHON（缺省 python）"),
    (r"pi_dispatch", "真内核是 scripts/pi_dispatch.py"),
    (r"REPO_ROOT", "仓库路径从 test/harness.ts 的 REPO_ROOT 推出来（不写死绝对路径）"),
    (r'"init"', "git 夹具仓库（git init + 一次提交）"),
    (r"QUIZS_LIVE_PLAN", "QUIZS_LIVE_PLAN 用完恢复原状"),
    (r"QUIZS_PROVIDER_PROFILE", "QUIZS_PROVIDER_PROFILE 用完恢复原状"),
    (r"QUIZS_QUALIFICATION", "QUIZS_QUALIFICATION 用完恢复原状"),
    (r"problem", "某一套读不出来只在那一行的 problem 里写原因、整条退出 0"),
    (r"exit_code", "信封退出码断言"),
    (r"expires_at_ms", "live 的证书到期毫秒数"),
    (r"valid_until", "profile 的 valid_until（带毫秒的 ISO 8601 UTC）"),
    (r"mailbox", "live 里 source=mailbox 的那一套"),
    (r"ready", "status.state=ready"),
    (r"schema_version|quizs\.providers\.v1", "假 Quizs 脚本打印带 schema_version 的 JSON"),
)

ASSUMPTIONS = (
    "「第 21、22 条」按登记顺序里两条新路由的位置判「不早于」（providers 不早于第 21 个、live 不早于第 22 个），"
    "不钉恰好——与站主 2026-11-14 给 T031 门禁放宽的同一口径；总数只查「不少于 22」与既有 20 条一条不少",
    "三份既有用例的条数断言只认「不少于 22」与点名的两行/两组值（末尾 60、150 或同名常量、byName 的 60/150），"
    "不钉恰好——总数由 routes-auth 的集合比对与 kernel-runner 的时限数组（vitest 全绿）钉住",
    "readRoutes() 处理器里的 argv 按「逐字写在数组里」或「引用 READ_ROUTE_ARGV[路由名]」两种写法都认（合同说"
    "「argv 逐字是模板里的三条」，两种写法都满足；替身用例的 argv 断言在流水线里逐字核对）",
    "redaction.ts 三个新校验函数的名字、导出与否、正则写在函数体里还是模块级常量合同都没写死：静态只按整份"
    "文件的记号判「这三类校验在文件里」（自由文字=新代码调 allowPreviewText 或再过一遍 redactSecrets；毫秒="
    "bigint；ISO=+00:00 加三位毫秒的任一写法），语义（放行/越界遮/缺毫秒遮/null 放行）由行为探针与执行端用例"
    "钉住——T042-4 一审的放宽口径，函数体切片的旧写法会误判模块级正则常量与非导出箭头函数",
    "README 的条数按合同写死 22（本片就是 22 条）；「连接空闲超时」那一条认「22 条读路由、预览、14 条写路由」，"
    "写路由的 14 一个字不许动；后续片再改数时按站主口径放宽",
    "server.ts 的「一个字没改」用「不出现 quizs、仍把 readRoutes() 接进 kernelAnsweredRoutes」静态判（不做 "
    "git diff 断言——范围由调度器的范围门禁证明）；routes.ts 的 public: true 恰两处是既有回归面",
    "流水线预算 500 秒（G01 的 600 秒减去静态用例与 pytest 自身开销）：依赖装好时三次 vitest 实测远小于预算；"
    "bun install 只在依赖不齐时跑（候选做完 S01 之后不会跑）",
    "流水线起 vitest 时把环境里的 QUIZS_CMD 与三个 QUIZS_LIVE_* 去掉（与 tests/conftest.py 的 no_ambient_quizs "
    "同一口径）：真内核用例自己设 QUIZS_CMD 指向夹具里的假脚本，执行机器上设着的那几套只会让 live 多出一行、"
    "结果随机器变", 
    "hub-routes.test.ts 连进流水线是被锁定面（T031 的用例，与本片共享 READ_ROUTE_SPECS）；真内核组不再单列——"
    "quizs-routes.test.ts 一个文件里替身与真内核都有",
)

# 流水线预算：合同 G01 的超时是 600 秒，留出静态用例与 pytest 自身的开销。
PIPELINE_BUDGET = 500
STEP_CAPS = {"bun install": 200, "vitest quizs": 220, "vitest locked": 200, "probe": 120}

_ENV_DROP = ("BUN_OPTIONS", "NODE_OPTIONS", "NODE_PATH", "BUN_INSPECT", "BUN_INSPECT_CONNECT_TO", "BUN_INSPECT_NOTIFY")
# 这台机器上线用的 QUIZS_* 不进 vitest 子进程（与 tests/conftest.py 的 no_ambient_quizs 同一口径）：真内核用例自己设
# QUIZS_CMD 指向夹具里的假脚本、自己恢复三个 QUIZS_LIVE_*，环境里带着用户级的那几套只会让 live 多出一行。
_QUIZS_DROP = ("QUIZS_CMD", "QUIZS_LIVE_PLAN", "QUIZS_PROVIDER_PROFILE", "QUIZS_QUALIFICATION")


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


#: 行注释与块注释在同一次从左往右的扫描里认：先出现的那一种算数（与 T031 门禁同一写法）。冒号、引号或反引号
#: 紧跟的 `//` 不算行注释（网址、以 // 开头的字符串）。
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def _argv_written(code, *parts):
    """argv 模板片段在不在：连写（``config quizs providers``）或相邻的数组元素（``"config", "quizs", …``）都算。"""
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


def _allow_paths(block):
    """白名单块里的路径集合：[["a","*",…], fn] 一行一条。"""
    rows = re.findall(r"\[\s*\[\s*((?:\"[^\"]*\"\s*,?\s*)+)\]\s*,", block)
    return {tuple(re.findall(r'"([^"]*)"', row)) for row in rows}


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
    for name in _QUIZS_DROP:
        env.pop(name, None)
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
# 静态断言：readroutes.ts（D01）
# ---------------------------------------------------------------------------

def test_static_quizs_routes_registered():
    """D01：两条 Quizs 读路由接上——时限常量 60/150、argv 模板、readRoutes() 的路由项（GET、精确路径、jsonRoute、
    各自的白名单、at() 的时限覆盖、不标 public）、READ_ROUTE_SPECS 第 21/22 条（既有 20 条一条不少）、条数注释 22、
    「api.hub.roles.get 是第 20 条」原文保留、去注释后不出现 WRITE。"""
    text = need_file(READROUTES_REL)
    code = strip_ts_comments(text)
    problems = []
    # 时限常量（文件头导出）
    for const, seconds in (("QUIZS_PROVIDERS_TIMEOUT", 60), ("QUIZS_LIVE_TIMEOUT", 150)):
        m = re.search(rf"export const {const}\s*=\s*(\d+)", code)
        if m is None:
            problems.append(f"readroutes.ts 应导出 {const}（时限 {seconds} 秒）")
        elif int(m.group(1)) != seconds:
            problems.append(f"{const} 应是 {seconds}，实际 {m.group(1)}")
    # READ_ROUTE_ARGV 模板
    argv_block = _block(code, "export const READ_ROUTE_ARGV")
    if not argv_block:
        problems.append("readroutes.ts 应有 export const READ_ROUTE_ARGV（模板表）")
    # readRoutes() 的路由项
    specs_block = _block(code, "export const READ_ROUTE_SPECS", "\n];")
    if not specs_block:
        problems.append("readroutes.ts 应有 export const READ_ROUTE_SPECS（登记表）")
    names = re.findall(r'name:\s*"([^"]+)"', specs_block)
    for old in OLD_20_SPECS:
        if old not in names:
            problems.append(f"READ_ROUTE_SPECS 里应有既有路由「{old}」（20 条一条不许少）")
    if len(names) < 22:
        problems.append(f"READ_ROUTE_SPECS 不应少于 22 条，实际 {len(names)}")
    for name, path, const, seconds, allow, argv in QUIZS_ROUTES:
        row = re.search(rf'name:\s*"{re.escape(name)}"[^}}]*}}', specs_block)
        if row is None:
            problems.append(f'READ_ROUTE_SPECS 里应有「{name}」的登记行')
        else:
            if f'path: "{path}"' not in row.group(0):
                problems.append(f"{name} 的 path 应恰为 {path}")
            if f"timeoutSeconds: {const}" not in row.group(0):
                problems.append(f"{name} 的时限应是 {const}（{seconds} 秒）")
        at = names.index(name) if name in names else -1
        floor = 20 if name.endswith("providers.get") else 21
        if at < floor:
            problems.append(f"{name} 应追加在表末（不早于第 {floor + 1} 条），实际是第 {at + 1} 个")
        route = _block(code, f'name: "{name}"', "\n    },")
        if not route:
            problems.append(f'readRoutes() 里应有 name: "{name}" 的路由项')
            continue
        if "GET" not in route:
            problems.append(f"{name} 应是 GET")
        if f'exact("{path}")' not in route:
            problems.append(f'{name} 的 pattern 应是 exact("{path}")')
        if "jsonRoute" not in route:
            problems.append(f"{name} 的处理器应走 jsonRoute")
        if allow not in route:
            problems.append(f"{name} 的处理器应登记白名单 {allow}")
        if not _argv_written(route, *argv) and f'READ_ROUTE_ARGV["{name}"]' not in route:
            problems.append(f"{name} 的处理器交出的 argv 应恰为 {list(argv)}")
        if f'at("{name}", {const})' not in route:
            problems.append(f'{name} 的时限应经 at("{name}", {const})')
        if "public" in route:
            problems.append(f"{name} 不许标 public（两条 Quizs 路由都要会话）")
        if not argv_block:
            continue
        template = re.search(rf'"{re.escape(name)}"\s*:\s*\[([^\]]*)\]', argv_block)
        if template is None:
            problems.append(f'READ_ROUTE_ARGV 里应有 "{name}" 的模板')
        elif not _argv_written(template.group(0), *argv):
            problems.append(f'READ_ROUTE_ARGV 的 {name} 模板应恰为 {list(argv)}')
    # 条数注释：三处 22 条；「api.hub.roles.get 是第 20 条」原文保留；登记表说明里补 Quizs 一句
    if len(re.findall(r"22\s*条", text)) < 3:
        problems.append("readroutes.ts 的条数注释应有三处改成 22 条（文件头、readRoutes() 说明、登记表说明）")
    if re.search(r"api\.hub\.roles\.get\s*是第\s*20\s*条", text) is None or "追加在表末" not in text:
        problems.append("readroutes.ts 应保留「api.hub.roles.get 是第 20 条（追加在表末）」这句原文（T031 门禁点名）")
    at = text.find("export const READ_ROUTE_SPECS")
    if at < 0 or "Quizs" not in text[max(0, at - 800):at]:
        problems.append("READ_ROUTE_SPECS 的说明注释应补一句后面两条是本片加的 Quizs 读路由")
    # 干净面：去注释后不出现 WRITE（T019 门禁口径的回归）
    if "WRITE" in code:
        problems.append("readroutes.ts 去注释后不应出现 WRITE（T019 门禁）")
    fail_if(problems, "两条 Quizs 读路由（D01）")


# ---------------------------------------------------------------------------
# 静态断言：redaction.ts（D02）
# ---------------------------------------------------------------------------

def test_static_redaction_quizs_allows():
    """D02：五个枚举（thinking 六档、billing 三值、source 两值、state 五值、missing 三个文件名）、
    QUIZS_PROVIDERS_ALLOW 恰好 4 条路径、QUIZS_LIVE_ALLOW 恰好 8 条路径（没登记的不在表里：build_id、live_dir、
    plan.*、implementation_digest、capabilities 一条也不出现）、三类可空校验的记号（自由文字、非负整数毫秒、带毫秒
    的 ISO 8601 UTC——合同没写死名字与写法，按整份文件的记号判在，语义由行为探针钉）、provider/model/live 的
    provider 用 allowBindingName、出处注明 kit_roles.py；既有面不推翻
    （HUB_ROLES_ALLOW 15 条、allowBindingName/allowPreviewText/allowPreviewName、PREVIEW_ALLOW 的行数）。"""
    text = need_file(REDACTION_REL)
    code = strip_ts_comments(text)
    problems = []
    # 五个枚举
    for const, values in QUIZS_ENUMS:
        m = re.search(rf"export const {const}\s*=\s*allowEnum\(([^)]*)\)", code)
        if m is None:
            problems.append(f"redaction.ts 应导出 {const}（取值 {list(values)}）")
            continue
        got = tuple(re.findall(r'"([^"]*)"', m.group(1)))
        if got != values:
            problems.append(f"{const} 的取值应恰为 {list(values)}，实际 {list(got)}")
    # 两份白名单：路径恰好
    for const, wanted in (("QUIZS_PROVIDERS_ALLOW", PROVIDERS_ALLOW_PATHS),
                          ("QUIZS_LIVE_ALLOW", LIVE_ALLOW_PATHS)):
        block = _block(code, f"export const {const}", "\n];")
        if not block:
            problems.append(f"redaction.ts 应导出 {const}")
            continue
        seen = _allow_paths(block)
        for path in wanted:
            if path not in seen:
                problems.append(f"{const} 里应有路径 {list(path)}")
        extra = seen - set(wanted)
        if extra:
            problems.append(f"{const} 不应登记别的路径（{sorted(extra)}）：build_id、live_dir、plan.*、"
                            "implementation_digest、capabilities 都不登记")
        if "allowBindingName" not in block and const.endswith("LIVE_ALLOW"):
            problems.append("QUIZS_LIVE_ALLOW 里 live.*.provider 应过 allowBindingName（名字形状或 null）")
    providers_block = _block(code, "export const QUIZS_PROVIDERS_ALLOW", "\n];")
    if providers_block and "allowBindingName" not in providers_block:
        problems.append("QUIZS_PROVIDERS_ALLOW 里 provider/model 应过 allowBindingName")
    # 三类可空校验「在文件里」（合同没写死名字、导出与否、正则写在函数体里还是模块级常量——redaction.ts 自己的
    # 既有写法就是模块级正则常量 PREVIEW_NAME_RE：按整份文件（去注释后）的记号判，模块级常量一起看；语义由
    # 流水线的行为探针钉住——探针直接对两份白名单跑 redactJson，-5 与缺毫秒 → <redacted>，+00:00 与 null 放行）。
    if code.count("allowPreviewText(") < 2 and code.count("redactSecrets(") < 2:
        problems.append("redaction.ts 应加一个可空的自由文字校验（null 放行，否则沿用 allowPreviewText 的口径："
                        "新校验要么调 allowPreviewText、要么自己再过一遍 redactSecrets）")
    if "bigint" not in code.lower():
        problems.append("redaction.ts 应加一个非负整数毫秒的校验（null 放行；bigint 与 number 都接——代码里应出现"
                        "bigint 的接法）")
    if "+00:00" not in code or not ("{3}" in code or "\\d\\d\\d" in code
                                    or ("toISOString" in code and "new Date" in code)):
        problems.append("redaction.ts 应加一个带毫秒的 ISO 8601 UTC 校验（null 放行；三位毫秒（{3}、\\d\\d\\d 或 "
                        "Date 的 toISOString 任一写法）、Z 与 +00:00 两种结尾都放行（代码里应出现 +00:00））")
    # 出处注释（合同第四步：注明抄自 kit_roles.py 与站主核实的输出形状）
    pos = text.find("QUIZS_THINKING_ENUM")
    region = text[max(0, pos - 800):pos + 4000] if pos >= 0 else text
    if "kit_roles.py" not in region:
        problems.append("Quizs 那一段的注释应注明取值抄自 scripts/kit_roles.py 与站主核实的 Quizs 输出形状")
    # 既有面不推翻（本片不改它们的语义）
    hub_block = _block(code, "export const HUB_ROLES_ALLOW", "\n];")
    if not hub_block:
        problems.append("redaction.ts 应保留 HUB_ROLES_ALLOW（本片不许动它）")
    else:
        seen = _allow_paths(hub_block)
        missing = [p for p in HUB_ALLOW_PATHS if p not in seen]
        if missing:
            problems.append(f"HUB_ROLES_ALLOW 的 15 条路径一条不许少，缺 {missing}")
    for name in ("allowBindingName", "allowPreviewText", "allowPreviewName", "allowNullableId"):
        if f"export function {name}" not in code:
            problems.append(f"redaction.ts 应保留 export function {name}（本片不许改它的语义）")
    if len(re.findall(r'\[\s*\[\s*"binding_changes"', code)) < 12:
        problems.append("PREVIEW_ALLOW 的 binding_changes 行应保留 12 条")
    fail_if(problems, "两份 Quizs 白名单（D02）")


# ---------------------------------------------------------------------------
# 静态断言：三份既有用例照新行为改（D04）
# ---------------------------------------------------------------------------

def test_static_locked_routes_auth():
    """D04：routes-auth.test.ts 的 READ_ROUTE_EXAMPLES 加两行（quizs 两条的示例路径）、条数断言不少于 22、
    不许 skip/only/todo。"""
    text = need_file(ROUTES_AUTH_REL)
    problems = []
    for name, path in (("api.quizs.providers.get", "/api/v1/quizs/providers"),
                       ("api.quizs.live.get", "/api/v1/quizs/live")):
        if f'"{name}": "{path}"' not in text:
            problems.append(f'READ_ROUTE_EXAMPLES 应加一行 "{name}": "{path}"')
    m = re.search(r"expect\(listed\.length\)\.toBe\((\d+)\)", text)
    if m is None:
        problems.append("routes-auth.test.ts 应保留条数断言 expect(listed.length).toBe(…)")
    elif int(m.group(1)) < 22:
        problems.append(f"条数断言的值不应少于 22（新事实），实际 toBe({m.group(1)})")
    problems += _no_skip_marks(strip_ts_comments(text))
    fail_if(problems, "routes-auth.test.ts（D04）")


def test_static_locked_kernel_runner():
    """D04：kernel-runner.test.ts 的 CASES 加两行（名字、示例路径、argv 取 READ_ROUTE_ARGV）、时限数组补到
    不少于 22 个值且末尾是 60 与 150、按名字断言两条新路由的时限、「时限照合同」那条用例的档位集合认 150。"""
    text = need_file(KERNEL_RUNNER_REL)
    code = strip_ts_comments(text)
    problems = []
    for name, path in (("api.quizs.providers.get", "/api/v1/quizs/providers"),
                       ("api.quizs.live.get", "/api/v1/quizs/live")):
        if f'name: "{name}"' not in code:
            problems.append(f'CASES 应加一行 name: "{name}"（放在表末）')
        if f'path: "{path}"' not in code:
            problems.append(f'CASES 新行的 path 应是 {path}')
        if f'READ_ROUTE_ARGV["{name}"]' not in code:
            problems.append(f'CASES 新行的 argv 应取 READ_ROUTE_ARGV["{name}"]')
    m = re.search(r"READ_ROUTE_SPECS\.map\(\(spec\)\s*=>\s*spec\.timeoutSeconds\)\)\.toEqual\(\[([^\]]*)\]", code)
    if m is None:
        problems.append("kernel-runner.test.ts 应保留 READ_ROUTE_SPECS 时限数组的断言")
    else:
        values = [v.strip() for v in m.group(1).split(",") if v.strip()]
        if len(values) < 22:
            problems.append(f"时限数组不应少于 22 个值（末尾补 60、150），实际 {len(values)}")
        if len(values) >= 2:
            if values[-2] not in ("60", "QUIZS_PROVIDERS_TIMEOUT"):
                problems.append(f"时限数组的倒数第二个值应是 60（providers），实际 {values[-2]}")
            if values[-1] not in ("150", "QUIZS_LIVE_TIMEOUT"):
                problems.append(f"时限数组的最后一个值应是 150（live），实际 {values[-1]}")
    if re.search(r'byName\.get\("api\.quizs\.providers\.get"\)\)\.toBe\(\s*60\s*\)', code) is None:
        problems.append('那条时限用例应按名字断言 byName.get("api.quizs.providers.get") 是 60')
    if re.search(r'byName\.get\("api\.quizs\.live\.get"\)\)\.toBe\(\s*150\s*\)', code) is None:
        problems.append('那条时限用例应按名字断言 byName.get("api.quizs.live.get") 是 150')
    if re.search(r"===\s*150", code) is None:
        problems.append("「时限照合同」那条用例的档位集合应认 150（否则新路由的 150 会被它判成 30 而红）")
    problems += _no_skip_marks(code)
    fail_if(problems, "kernel-runner.test.ts（D04）")


def test_static_locked_argv_templates():
    """D04：argv-templates.test.ts 的 READ_ROUTE_SPECS 长度断言改成不少于 22（新模板会被内核真正的解析器逐条
    解析，`config quizs providers|live --json` 已被 kit_config.py 支持）。"""
    text = need_file(ARGV_TEMPLATES_REL)
    problems = []
    m = re.search(r"expect\(READ_ROUTE_SPECS\)\.toHaveLength\((\d+)\)", text)
    if m is None:
        problems.append("argv-templates.test.ts 应保留 expect(READ_ROUTE_SPECS).toHaveLength(…)")
    elif int(m.group(1)) < 22:
        problems.append(f"READ_ROUTE_SPECS 的长度断言不应少于 22，实际 toHaveLength({m.group(1)})")
    problems += _no_skip_marks(strip_ts_comments(text))
    fail_if(problems, "argv-templates.test.ts（D04）")


# ---------------------------------------------------------------------------
# 静态断言：新测试文件在位且要点齐备（D03/D05 的静态面）
# ---------------------------------------------------------------------------

def test_static_quizs_test_file():
    """D05 的静态面：quizs-routes.test.ts 在位——替身部分（startApp、FAKE_KERNEL_JSON、两条路由的路径与 argv、
    信封七字段、白名单的 <redacted> 与凭据形状、FAKE_KERNEL_EXIT、超时 504 与提示原文）与真内核部分（THEMIS_PYTHON、
    pi_dispatch、REPO_ROOT、git 夹具仓库、QUIZS_CMD 指向夹具里的假脚本、三个 QUIZS_LIVE_* 用完恢复、逐套 problem）
    的记号一个不许少；不许 skip/only/todo。"""
    rel = NEW_TEST_RELS[0]
    text = need_file(rel)
    stripped = strip_ts_comments(text)
    problems = _token_problems(stripped, QUIZS_TEST_TOKENS)
    problems += _no_skip_marks(stripped)
    fail_if(problems, f"{rel} 的要点（D03/D05）")


# ---------------------------------------------------------------------------
# 静态断言：README（D06）
# ---------------------------------------------------------------------------

def test_static_readme():
    """D06：README 与行为同步——读路由表加两行（路径、argv、时限 60/150 秒）；「本片加的 N 条只读数据路由」改成
    22；结构表 readroutes.ts 行的条数改 22、redaction.ts 行补两份 Quizs 白名单；「连接空闲超时」那一条写成
    「22 条读路由、预览、14 条写路由」；首段「第 2 片加 20 条只读数据路由」是历史叙述保留；写路由的 14 条与
    三处不许动的段落一字不改。"""
    text = need_file(README_REL)
    problems = []
    # 路由表两行（逐行查：命令与时限写在这一行里）
    for path, command, seconds in (("/api/v1/quizs/providers", "config quizs providers --json", "60"),
                                   ("/api/v1/quizs/live", "config quizs live --json", "150")):
        rows = [line for line in text.splitlines() if f"GET {path}" in line]
        if not rows:
            problems.append(f"读路由表应加一行 GET {path}")
            continue
        row = rows[0]
        if command not in row:
            problems.append(f"GET {path} 那行应写 {command}")
        if f"（{seconds} 秒）" not in row:
            problems.append(f"GET {path} 那行应写时限（{seconds} 秒）")
    # 条数的说法
    if re.search(r"22\s*条只读数据路由", text) is None:
        problems.append("README 的「本片加的 N 条只读数据路由」应改成 22 条")
    # 结构表：readroutes.ts 行的条数、redaction.ts 行补 Quizs 白名单
    for line in text.splitlines():
        if "`src/readroutes.ts`" in line and "条读路由" in line:
            m = re.search(r"(\d+)\s*条读路由", line)
            if m is None or int(m.group(1)) < 22:
                problems.append(f"结构表 readroutes.ts 行的条数应改成 22，实际「{line.strip()[:60]}」")
        if "`src/redaction.ts`" in line and "|" in line:
            if "Quizs" not in line:
                problems.append("结构表 redaction.ts 行应补上两份 Quizs 白名单")
    # 连接空闲超时那一条
    at = text.find("连接空闲超时")
    if at < 0:
        problems.append("README 应保留「连接空闲超时」那一条")
    else:
        bullet_end = text.find("\n- ", at)
        bullet = text[at:bullet_end if bullet_end > 0 else at + 600]
        if re.search(r"22\s*条读路由、预览、14\s*条写路由", bullet) is None:
            problems.append("「连接空闲超时」那一条应写成「22 条读路由、预览、14 条写路由」")
    # 历史叙述与写路由的 14 条不动
    if "第 2 片加 20 条只读数据路由" not in text:
        problems.append("首段「第 2 片加 20 条只读数据路由」是历史叙述，应保留原样")
    if re.search(r"14\s*条写路由", text) is None:
        problems.append("写路由的 14 条说法应保留（一个字不改）")
    if "GET /api/v1/hub/roles" not in text or "POST /api/v1/hub/roles/<post>" not in text:
        problems.append("hub 的两条路由表行应保留（T031 门禁点名）")
    # 既有段落不动（这些记号一个不许少）
    for needle in ("## 日志跟随", "状态码：201 作业创建成功", "**作业表只在内存里**"):
        if needle not in text:
            problems.append(f"README 的既有段落应一字不动（看不到「{needle}」）")
    fail_if(problems, "README（D06）")


# ---------------------------------------------------------------------------
# 静态断言：共享面不动（D07/D08 的回归面）
# ---------------------------------------------------------------------------

def test_static_shared_surfaces():
    """D07/D08：ui 包的依赖清单仍只许 @themis/base 与 @themis/contracts；routes.ts 里 public: true 仍恰好两处
    （Quizs 两条新路由不许标 public——它们要会话，且路由本来就不在 routes.ts）；server.ts 一个字没改（仍把
    readRoutes() 接进 kernelAnsweredRoutes，且不出现 quizs——两条路由进 readRoutes() 就自动接上）。这条在基线上
    就是绿的，是回归保护。"""
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
    server = need_file(SERVER_REL)
    if "readRoutes" not in server:
        problems.append("server.ts 应仍把 readRoutes() 接进 createApp/kernelAnsweredRoutes")
    if "quizs" in server.lower():
        problems.append("server.ts 不应出现 quizs（两条路由进 readRoutes() 就自动接上，server.ts 一个字没改）")
    fail_if(problems, "ui 包依赖与共享面（D07/D08）")


# ---------------------------------------------------------------------------
# 行为探针：直接对两份白名单跑 redactJson（放行/越界遮/凭据形状遮的语义）
# ---------------------------------------------------------------------------

PROBE_SOURCE = """// T042 战前门禁的行为探针（gate-sonnet 临时写出，跑完即删，不进仓库）：直接对两份 Quizs 白名单跑 redactJson，
// 钉住合同 Behavior contract 的白名单语义——放行的字段原样、越界的枚举值变成 <redacted>、凭据形状的键默认遮掉、
// expires_at_ms 与 valid_until 的形状校验。内核 stdout 的 JSON 先过 parseJsonData（与 jsonRoute 同一条路）。
import { describe, expect, it } from "vitest";
import { redactJson } from "@themis/base/secrets";
import { parseJsonData } from "../../src/kernelenvelope.ts";
import { QUIZS_LIVE_ALLOW, QUIZS_PROVIDERS_ALLOW } from "../../src/redaction.ts";

function redacted(text: string, allow: Parameters<typeof redactJson>[1]): unknown {
  const parsed = parseJsonData(text);
  expect(parsed, "JSON 应解析得了").toBeDefined();
  return redactJson(parsed ?? null, allow);
}

function at(value: unknown, ...path: (string | number)[]): unknown {
  let cur: unknown = value;
  for (const step of path) {
    if (Array.isArray(cur)) cur = cur[step as number];
    else if (cur instanceof Map) cur = cur.get(step);
    else return undefined;
  }
  return cur;
}

describe("QUIZS_PROVIDERS_ALLOW 的语义", () => {
  it("provider/model 原样、thinking 与 billing 越界遮、凭据形状的键默认遮", () => {
    const data = redacted(JSON.stringify({
      build_id: "b-2026",
      providers: [
        { provider: "deepseek", id: "deepseek-api", model: "deepseek-chat",
          thinking: ["off", "high", "turbo"], billing: "monthly",
          credential_ref: "cred-1", access_tokens: ["t-1"] },
        { provider: "stepfun", model: "step-plan", thinking: ["max"], billing: "step_plan_credits" },
      ],
    }), QUIZS_PROVIDERS_ALLOW);
    const one = at(data, "providers", 0) as Map<string, unknown>;
    expect(at(one, "provider")).toBe("deepseek");
    expect(at(one, "model")).toBe("deepseek-chat");
    expect(at(one, "thinking", 0)).toBe("off");
    expect(at(one, "thinking", 1)).toBe("high");
    expect(at(one, "thinking", 2)).toBe("<redacted>");
    expect(at(one, "billing")).toBe("<redacted>");
    expect(at(one, "credential_ref")).toBe("<redacted>");
    expect(at(one, "access_tokens", 0)).toBe("<redacted>");
    const two = at(data, "providers", 1) as Map<string, unknown>;
    expect(at(two, "provider")).toBe("stepfun");
    expect(at(two, "thinking", 0)).toBe("max");
    expect(at(two, "billing")).toBe("step_plan_credits");
  });
});

describe("QUIZS_LIVE_ALLOW 的语义", () => {
  it("放行的字段原样；state/missing/expires_at_ms/valid_until 越界遮；problem 透传自由文字", () => {
    const data = redacted(JSON.stringify({
      live: [
        { source: "mailbox", provider: "deepseek", live_dir: null, problem: null,
          status: { state: "ready", problem: null, missing: ["plan.json", "other.txt"],
            certificate: { issued_at_ms: 1789000000000, expires_at_ms: 1790000000000 },
            profile: { valid_until: "2026-11-14T08:00:00.000Z" } } },
        { source: "env", provider: null, live_dir: null,
          problem: "quizs live status 失败（退出码 127）",
          status: { state: "Ready", problem: "证书过期", missing: [],
            certificate: { expires_at_ms: -5 }, profile: { valid_until: "2026-11-14T08:00:00Z" } } },
        { source: "env", provider: null, live_dir: null, problem: null,
          status: { state: "expired", problem: null, missing: [],
            certificate: { expires_at_ms: null },
            profile: { valid_until: "2026-11-14T08:00:00.000+00:00" } } },
      ],
    }), QUIZS_LIVE_ALLOW);
    const mailbox = at(data, "live", 0) as Map<string, unknown>;
    expect(at(mailbox, "source")).toBe("mailbox");
    expect(at(mailbox, "provider")).toBe("deepseek");
    expect(at(mailbox, "status", "state")).toBe("ready");
    expect(at(mailbox, "status", "missing", 0)).toBe("plan.json");
    expect(at(mailbox, "status", "missing", 1)).toBe("<redacted>");
    expect(Number(at(mailbox, "status", "certificate", "expires_at_ms"))).toBe(1790000000000);
    expect(at(mailbox, "status", "profile", "valid_until")).toBe("2026-11-14T08:00:00.000Z");
    const env = at(data, "live", 1) as Map<string, unknown>;
    expect(at(env, "source")).toBe("env");
    expect(at(env, "provider")).toBeNull();
    expect(at(env, "problem"), "内核的逐套报错文字原样透传").toBe("quizs live status 失败（退出码 127）");
    expect(at(env, "status", "state")).toBe("<redacted>");
    expect(at(env, "status", "problem")).toBe("证书过期");
    expect(at(env, "status", "certificate", "expires_at_ms")).toBe("<redacted>");
    expect(at(env, "status", "profile", "valid_until")).toBe("<redacted>");
    const offset = at(data, "live", 2) as Map<string, unknown>;
    expect(at(offset, "status", "state")).toBe("expired");
    expect(at(offset, "status", "certificate", "expires_at_ms")).toBeNull();
    expect(at(offset, "status", "profile", "valid_until"), "+00:00 结尾也放行").toBe("2026-11-14T08:00:00.000+00:00");
  });
});
"""


# ---------------------------------------------------------------------------
# 会话级流水线夹具：vitest 跑新测试文件、被改的既有用例与行为探针
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
        self.probe_rel = ""
        self.probe_removed = True

    def group(self, name):
        return self.groups.setdefault(name, Group(name))


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    missing = [rel for rel in NEW_TEST_RELS if not (REPO_ROOT / rel).is_file()]
    if missing:
        pipe.reason = ("候选里还没有本片的测试文件（基线 53f2d47，Quizs 的两条读路由还没实现），未装依赖、"
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
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in QUIZS_GROUP_RELS],
                    "vitest-quizs", min(deadline - 160, time.monotonic() + STEP_CAPS["vitest quizs"]))
        if not pipe.stopped_reason:
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in LOCKED_GROUP_RELS],
                    "vitest-locked", min(deadline - 60, time.monotonic() + STEP_CAPS["vitest locked"]))
        if not pipe.stopped_reason:
            _probe(pipe, node, deadline)
    finally:
        _remove_probe(pipe)
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


def _probe(pipe, node, deadline):
    """把行为探针临时写进 ts/packages/ui/test/gate-probe/，用 vitest 跑一遍，finally 里删掉。"""
    grp = pipe.group("vitest-probe")
    cap = min(STEP_CAPS["probe"], deadline - time.monotonic())
    if cap <= 30:
        grp.check(False, f"行为探针未运行：整体预算将尽（cap={cap:.0f}s）")
        return grp
    probe_dir = TS / "packages" / "ui" / "test" / "gate-probe"
    pipe.probe_rel = f"ts/packages/ui/test/gate-probe/probe-{uuid.uuid4().hex[:8]}-t042-quizs.test.ts"
    try:
        probe_dir.mkdir(parents=True, exist_ok=True)
        (REPO_ROOT / pipe.probe_rel).write_text(PROBE_SOURCE, encoding="utf-8", newline="\n")
        pipe.probe_removed = False
    except OSError as error:
        grp.check(False, f"行为探针写不进 {probe_dir}：{error}")
        return grp
    argv = [node, os.path.join("node_modules", "vitest", "vitest.mjs"), "run",
            pipe.probe_rel.removeprefix("ts/")]
    code, timed_out, out, seconds = run_capture(argv, TS, cap)
    if not grp.check(code == 0,
                     f"行为探针退出码 {code}{'（超时被杀）' if timed_out else ''}，"
                     f"用时 {seconds:.0f}s：{out[-1500:]}"):
        return grp
    grp.check(re.search(r"Tests[^\n]*[1-9]\d*[^\n]*passed", out) is not None,
              f"行为探针的 Tests 行应有 passed 计数：{out[-600:]}")
    return grp


def _remove_probe(pipe):
    if pipe.probe_rel and not pipe.probe_removed:
        probe_dir = (REPO_ROOT / pipe.probe_rel).parent
        shutil.rmtree(probe_dir, ignore_errors=True)
        pipe.probe_removed = True


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
    """流水线真的跑了（quizs-routes.test.ts 在位、bun/node 找得到、依赖装好、vitest 起了、探针删干净）。"""
    assert pipeline.ran, pipeline.reason
    assert not pipeline.stopped_reason, f"流水线中途停了：{pipeline.stopped_reason}"
    assert not (TS / "packages" / "ui" / "test" / "gate-probe").exists(), "行为探针的目录应已删除"


def test_pipeline_quizs_group(pipeline):
    """D03/D05 的机械判据：quizs-routes.test.ts（替身 + 真内核）在 vitest 下全过——argv、信封、白名单、退出 1、
    超时 504、QUIZS_CMD 指向假脚本的两条真内核用例、逐套 problem 的语义。"""
    _pipeline_group(pipeline, "vitest-quizs")


def test_pipeline_locked_group(pipeline):
    """D04/D08 的机械判据：routes-auth（22 条都要会话、401）、kernel-runner（CASES 与时限数组）、argv-templates
    （模板过内核真正的解析器）与 T031 的 hub-routes 在 vitest 下全过。"""
    _pipeline_group(pipeline, "vitest-locked")


def test_pipeline_probe(pipeline):
    """D02 的行为判据：探针直接对两份白名单跑 redactJson——放行的字段原样、越界的枚举值遮掉、凭据形状的键默认遮、
    expires_at_ms 与 valid_until 的形状校验（含 +00:00 与 null）。"""
    _pipeline_group(pipeline, "vitest-probe")
