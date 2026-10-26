"""T018 战前门禁：桌面端本机服务第 4 片「日志跟随」（D1-C 后半之二）的黑盒基准测试
（合同 t018-desktop-ui-follow v1，基线 5913f5199d6f285e67fa80abb912a4b369cd953c）。

被测对象是 ``ts/packages/ui`` 的 file 路由加「跟随」：请求带 ``follow=1`` 时 argv 追加
``--complete-lines``（内核只给已经写完的 JSONL 行，``--cursor=`` 仍排最后），读到末尾也发句柄、
没有新行时空页复用请求里的同一个句柄（句柄表项数不变），跟随响应的 data 末尾追加
``poll_after_ms``（2000，与 503 的 ``Retry-After: 2`` 一致）；follow 取值不是字面 ``1``、或路径不是
``.jsonl``（大小写不敏感，``LOG.JSONL`` 放行）都在起子进程之前回 400；409 的情形沿用 T016（内核退出 2
且 stderr 含「游标对应的文件已变化」→ 409 并丢句柄）；轮询照样经执行器（队列满 503 带 retry-after: 2）；
句柄表（cursors.ts）与 localhttp 一个字不改；非跟随的 file 路由逐字节不变；README 加「日志跟随」一节。

基线（5913f51）上 ``ts/packages/ui/src/readroutes.ts`` 里没有 follow 的任何标记（follow、
--complete-lines、poll_after_ms、FOLLOW_ARGV 都不存在）、两个新测试文件与 README 的那一节都不存在，
所以本文件的失败落在「标记不在」「文件不存在」这类断言上，不是导入、收集或语法错误：模块级只导入
标准库，所有仓库文件的读取都发生在用例函数里；流水线（起 vitest 跑两个新文件与三个被锁定的既有
用例文件）放在 ``pipeline`` 会话级夹具里，候选里没有新测试文件时不装依赖、不起 vitest。

结构（编号对应合同 DoD 的 D01–D18；合同 M1–M8 的抓住靠这些断言加被锁定的新旧 Vitest 用例，
战后门禁另出变异清单）：

- 静态断言（不用流水线，全量 pytest 也跑）：
  - readroutes.ts：``FOLLOW_MIN_INTERVAL_MS = 2000`` 与导出的 ``FOLLOW_ARGV`` 两条（示例值照合同，
    ``--complete-lines`` 在 ``--cursor=`` 之前、``--cursor=`` 在最后；D03/D08）；file 路由的跟随 argv
    真用了 ``--complete-lines``（D03）；follow 与 path、cursor 同法取值、两条 400 提示原文、
    ``toLowerCase().endsWith(".jsonl")`` 的判定、只认字面 ``1``（D01/D02）；``poll_after_ms`` 进跟随的
    data、值取 FOLLOW_MIN_INTERVAL_MS、空页判内核给的 ``lines``、旧句柄不 drop（只有「游标对应的
    文件已变化」那一处 drop；D04–D06/D08）；不回 429（D08）；19 条读路由一条不动、
    ``READ_ROUTE_ARGV`` 不并 follow（D14/D16）。
  - 两个新测试文件在位且要点齐备：``follow.test.ts``（F1–F12：FOLLOW_ARGV 逐项、--complete-lines、
    poll_after_ms/2000、503 与 retry-after、maxConcurrent/maxQueue、1024、part/parts、LOG.JSONL、
    a.jſonl、follow=0/true/空串、409 与「游标对应的文件已变化」、43 字符句柄、非跟随 null、
    空页 lines）；``follow-real.test.ts``（R1–R3：kit_logs.build_parser、complete_lines、
    --complete-lines、appendFileSync/truncateSync、pi_dispatch、startService、events.jsonl、
    part、超过一页的长行）。两个文件不许出现 skip/only/todo（D17）。
  - D14 的既有断言哨兵：cursors.test.ts 的 ``next_cursor`` 为 null 那条、kernel-real.test.ts 的
    「逐字节」、argv-templates.test.ts 的 READ_ROUTE_ARGV 逐项解析与「每个以 -- 开头的项都含 =」
    （并进去 --complete-lines 就会红）；cursors.ts 的 1024/LRU 哨兵；ui 包依赖清单不加（D16）。
  - README（D15/V08）：「## 日志跟随」一节写齐合同点名的结论；V08 的 need 列表一字不差；
    状态码那一段与句柄两条既有段落逐字保留。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：bun install
  --frozen-lockfile（依赖不齐时）之后起两次 vitest——两个新文件（F1–F12/R1–R3/D12/D13/D18 的机械
  判据）与三个被锁定的既有用例文件（cursors / argv-templates / kernel-real，D14：非跟随逐字节不变），
  退出码 0 且 Tests 行 passed。

合同没有写死、门禁端按最合理读法定下的地方（交付信「需协调人决定」里逐条列出，终审可改）：
见 ``ASSUMPTIONS``。
"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TS = REPO_ROOT / "ts"
UI_TEST = TS / "packages" / "ui" / "test"

# 合同 Scope 锁定的本片改动面
READROUTES_REL = "ts/packages/ui/src/readroutes.ts"
README_REL = "ts/packages/ui/README.md"
FOLLOW_TEST_RELS = (
    "ts/packages/ui/test/follow.test.ts",
    "ts/packages/ui/test/follow-real.test.ts",
)
# D14：非跟随逐字节不变的既有用例（流水线里连跑；静态只查哨兵）
LOCKED_NONFOLLOW_RELS = (
    "ts/packages/ui/test/cursors.test.ts",
    "ts/packages/ui/test/argv-templates.test.ts",
    "ts/packages/ui/test/kernel-real.test.ts",
)
# 既有 19 条读路由的名字（T016 的口径一条不动）
READ_ROUTE_NAMES = (
    "api.meta.get", "api.status.get", "api.attempts.list", "api.attempts.show", "api.attempts.file",
    "api.usage.get", "api.config.get", "api.config.validate", "api.config.history.list",
    "api.config.history.show", "api.roles.get", "api.profiles.get", "api.presets.list",
    "api.presets.diff", "api.runtimes.get", "api.plugins.list", "api.plugins.show",
    "api.secrets.list", "api.secrets.show",
)
# 合同 Behavior contract：FOLLOW_ARGV 的两条（示例值照 READ_ROUTE_ARGV 的约定）
FOLLOW_ARGV_EXPECTED = {
    "api.attempts.file.follow": ("logs", "cat", "demo-task/attempt-001", "events.jsonl", "--json",
                                 "--complete-lines"),
    "api.attempts.file.follow.cursor": ("logs", "cat", "demo-task/attempt-001", "events.jsonl", "--json",
                                        "--complete-lines", "--cursor=fake-cursor-0001"),
}
# 两条 400 提示的原文（合同 Behavior contract）
FOLLOW_MSG_VALUE = "follow 参数不合格（只接受 1）"
FOLLOW_MSG_NOT_JSONL = "只有 JSONL 文件支持跟随"
# V08 的 README 口径（合同 Validation commands V08 的 need 列表，一字不差）
README_V08_NEEDLES = ("follow", "poll_after_ms", "--complete-lines", "2000", "409", "503", "Retry-After",
                      "已知限制")
# 「日志跟随」一节必须写到的结论（合同 D15；元组给的是可替代表述之一）
README_SECTION_NEEDLES = (
    ("follow=1", None),
    (FOLLOW_MSG_VALUE, None),
    (FOLLOW_MSG_NOT_JSONL, None),
    ("大小写", "LOG.JSONL"),
    ("句柄", None),
    ("复用", "空页"),
    ("末尾", None),
    ("poll_after_ms", None),
    ("2000", None),
    ("Retry-After", None),
    ("不强制", None),
    ("409", None),
    ("503", None),
    ("半行", None),
    ("并发", None),
    ("重复", None),
)
# D15：既有段落逐字保留（状态码那一段与 T016 钉住的句柄两条）
README_PRESERVED = (
    "状态码：201 作业创建成功",
    "409 句柄无效或内核报「游标对应的文件已变化」（提示「游标无效或文件已变化，请从头读取」）",
    "命令退出非 0 一律回 200（信封 `ok` 为 false、`exit_code` 原样）",
    "`/api/v1/attempts/<task>/<attempt>/file` 给界面的 `next_cursor` 是 43 个字符的随机不透明句柄，"
    "内核游标只存在服务内存里（服务退出全部失效）。",
    "`file` 路由的句柄只在内存里：服务重启之后旧句柄一律 409",
)
# follow.test.ts（F1–F12）要点：字面量或正则（带 re.S 的元组按正则处理）
FOLLOW_UNIT_TOKENS = (
    (r"FOLLOW_ARGV", "F1：跟随 argv 与登记表逐项一致"),
    (r"--complete-lines", "F1/M1：--complete-lines 进跟随 argv"),
    (r"readRoutes", "替身用例照 cursors.test.ts 的写法（进程内 app + 替身 runner）"),
    (r"43", "F2/D04：句柄 43 个字符"),
    (r"toBe\(null\)", "F2/M4：非跟随的同一份内核输出仍是 null"),
    (r"lines", "F3/F4/M5：空页（lines 为空数组）"),
    (r"游标对应的文件已变化", "F6/M6：内核报游标失效"),
    (r"409", "F6/F11：句柄无效或文件已变化"),
    (r"LOG\.JSONL", "F7/M7：JSONL 判定大小写不敏感放行"),
    (r"a\.jſonl", "F7/M7：近似扩展名（ſ 不是 s）回 400"),
    (r"\.txt", "F7：notes.txt 不许跟随"),
    (r"\.json\b", "F7：a.json 不许跟随"),
    (r"follow=0", "F8：follow=0 回 400"),
    (r"follow=true", "F8：follow=true 回 400"),
    (r"follow=[^0-9A-Za-z=]", "F8：follow=（空串）回 400"),
    (r"poll_after_ms", "F9/M8：跟随响应带 poll_after_ms"),
    (r"2000", "F9：值是 2000"),
    (r"maxConcurrent", "F10：startApp({maxConcurrent:1, maxQueue:0}) 的队列用例"),
    (r"maxQueue", "F10：队列满的覆盖项"),
    (r"503", "F10/D09：队列满回 503"),
    (r"[Rr]etry-[Aa]fter", "F10：retry-after: 2"),
    (r"1024|CURSOR_CAPACITY", "F11/D10：发满 1024 个句柄"),
    (r"part", "F12/D11：分片接着给"),
    (r"startApp", "F10：用测试支架 startApp"),
    (r"next_cursor", "F1–F5：next_cursor 换发句柄"),
)
# follow-real.test.ts（R1–R3）要点
FOLLOW_REAL_TOKENS = (
    (r"kit_logs", "R1/D12：内核的 kit_logs"),
    (r"build_parser", "R1/D12：内核自己的 build_parser"),
    (r"complete_lines", "R1/M1：解析出的 complete_lines 为真"),
    (r"--complete-lines", "R1：FOLLOW_ARGV 的两条逐项解析"),
    (r"pi_dispatch", "R2/D13：真内核（scripts/pi_dispatch.py）"),
    (r"startService", "R2：真服务（harness 的 startService）"),
    (r"appendFileSync", "R2/M2/M3：文件增长一律 appendFileSync"),
    (r"truncateSync", "R2/M6：截短用 truncateSync"),
    (r"events\.jsonl", "R2：证据文件 events.jsonl"),
    (r"demo-task", "R2：demo-task/attempt-001"),
    (r"attempt-001", "R2：demo-task/attempt-001"),
    (r"半行|\{\"b\": ?2", "R2/M2：先写半行不给"),
    (r"poll_after_ms", "R2/M8：每一步 poll_after_ms === 2000"),
    (r"part", "R3/D11：一行超过一页的分片"),
    (r"256|262144|Ki", "R3：长行大于 256Ki 个字符"),
    (r"409", "R2/M6：截短回 409 且句柄被丢"),
)

ASSUMPTIONS = (
    "「两条 400 都在起子进程之前」与「follow 校验排在句柄校验之前」是行为断言，由被锁定的 "
    "follow.test.ts（F7/F8：替身 runner 的调用计数为 0）钉住，静态断言只查提示原文与取值写法",
    "「FOLLOW_ARGV 真被 file 路由的跟随分支使用」按「--complete-lines 出现在 fileRoute 的组装区，"
    "或该区引用了 FOLLOW_*」判；argv 的逐项一致由 follow.test.ts 的 F1（替身收到的 argv 与 FOLLOW_ARGV "
    "逐项相等）钉住",
    "「旧句柄留在表里（Q1 不 drop）」按「readroutes.ts 里 drop 的调用仍只有『游标对应的文件已变化』"
    "那一处」判；带旧句柄再请求不是 409 由 follow.test.ts 的 F5 钉住",
    "「非跟随的 file 路由逐字节不变」的静态面按 19 条路由名、READ_ROUTE_ARGV 的 file 两条示例值"
    "（a/b.txt、--cursor=fake-cursor-0001）与三个既有用例文件的哨兵判；逐字节的行为面由流水线里连跑 "
    "cursors.test.ts / argv-templates.test.ts / kernel-real.test.ts 钉住（D14）",
    "「ui 包依赖清单仍是 base+contracts」「cursors.ts 的 1024/LRU 哨兵」是 D16 禁改面的哨兵；"
    "ts/bun.lock 未改由 V01 的 bun install --frozen-lockfile 机械判，不在本文件静态断言",
    "「README 既有段落逐字保留」按合同 D15 点名的「状态码那一段」与 T016 钉住的句柄两条整句判；"
    "「最小 API」的路由表行不在点名清单里（执行端可以合法地把 [&follow=1] 补进那一行），不断言",
    "基线 README「已知限制」里「本片不做跟随……要等内核先给 logs cat 补开关」那句已过时（内核的 "
    "--complete-lines 早已存在，A6）；合同没说这句要改还是要留，本文件不断言它，见交付信",
)

# 流水线预算：合同 G01 的超时是 600 秒，留出静态用例与 pytest 自身的开销。
PIPELINE_BUDGET = 480
STEP_CAPS = {"bun install": 200, "vitest follow": 300, "vitest locked": 200}

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


def _num_near(code, name, value):
    """常量定义形如 ``NAME = 2000``（允许数字分隔符 2_000 与类型标注）。"""
    digits = str(value)
    sep = r"_?" if len(digits) > 3 else ""
    pattern = digits[0] + "".join(sep + d for d in digits[1:])
    return re.search(rf"\b{name}\b[^=\n;{{}}]*=\s*{pattern}\b", code) is not None


def _block(text, start_marker, end_marker="};"):
    """从 start_marker 起到 end_marker 止的一段（登记表/函数体切片用）。"""
    start = text.find(start_marker)
    if start < 0:
        return ""
    end = text.find(end_marker, start)
    return text[start:end if end >= 0 else len(text)]


def _entry(block, key):
    """登记表里一条（从键起到下一个 ] 止）。"""
    start = block.find(key)
    if start < 0:
        return ""
    end = block.find("]", start)
    return block[start:end if end >= 0 else len(block)]


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
# 静态断言：readroutes.ts 的跟随实现面
# ---------------------------------------------------------------------------

def test_static_follow_constants():
    """D03/D08：导出 ``FOLLOW_MIN_INTERVAL_MS = 2000`` 与 ``FOLLOW_ARGV`` 两条登记表
    （示例值照合同；``--complete-lines`` 在 ``--cursor=`` 之前、``--cursor=`` 在最后）。"""
    code = strip_ts_comments(need_file(READROUTES_REL))
    problems = []
    if not _num_near(code, "FOLLOW_MIN_INTERVAL_MS", 2000):
        problems.append("应有导出常量 FOLLOW_MIN_INTERVAL_MS = 2000（与 503 的 Retry-After: 2 一致）")
    if "FOLLOW_ARGV" not in code:
        problems.append("应有 FOLLOW_ARGV 登记表（导出在 readroutes.ts，供替身与真内核用例逐条对照）")
        fail_if(problems, "跟随的常量与登记表（D03/D08）")
        return
    block = _block(code, "FOLLOW_ARGV")
    for key, argv in FOLLOW_ARGV_EXPECTED.items():
        quoted = f'"{key}"'
        if quoted not in block:
            problems.append(f"FOLLOW_ARGV 里应有「{key}」")
            continue
        entry = _entry(block, quoted)
        for part in argv:
            if f'"{part}"' not in entry:
                problems.append(f"{key} 的 argv 应含「{part}」（合同 Behavior contract 的示例值）")
        if '"--cursor=fake-cursor-0001"' in entry:
            i_flag = entry.find('"--complete-lines"')
            i_cursor = entry.find('"--cursor=fake-cursor-0001"')
            if not (0 <= i_flag < i_cursor):
                problems.append(f"{key} 的 --complete-lines 应在 --cursor= 之前（--cursor= 排最后）")
        elif key.endswith(".cursor"):
            problems.append(f"{key} 的 argv 应含「--cursor=fake-cursor-0001」")
    fail_if(problems, "跟随的常量与登记表（D03/D08）")


def test_static_follow_validation():
    """D01/D02：follow 与 path、cursor 同法取值；只认字面 ``1``；两条 400 提示原文；
    JSONL 判定 ``toLowerCase().endsWith(".jsonl")``（大小写不敏感）。两条 400 都不起子进程的行为面
    由 follow.test.ts 的 F7/F8（替身调用计数为 0）钉住。"""
    code = strip_ts_comments(need_file(READROUTES_REL))
    problems = []
    if not re.search(r'get\(\s*["\']follow["\']\s*\)', code):
        problems.append('follow 应与 path、cursor 同法取值（url.searchParams.get("follow")，不另查重复参数）')
    if FOLLOW_MSG_VALUE not in code:
        problems.append(f"follow 取值不合格的 400 提示原文应是「{FOLLOW_MSG_VALUE}」")
    if FOLLOW_MSG_NOT_JSONL not in code:
        problems.append(f"非 JSONL 跟随的 400 提示原文应是「{FOLLOW_MSG_NOT_JSONL}」")
    if not re.search(r'toLowerCase\(\)\s*\.\s*endsWith\(\s*["\']\.jsonl["\']\s*\)', code):
        problems.append('JSONL 判定应是 path.toLowerCase().endsWith(".jsonl")（与内核 safe_mode 一致）')
    if not re.search(r'[!=]==?\s*["\']1["\']|["\']1["\']\s*[!=]==?', code):
        problems.append('follow 只认字面 "1"（应有与 "1" 的严格比较）')
    fail_if(problems, "follow 的参数校验（D01/D02）")


def test_static_follow_response():
    """D04/D05/D06/D08 的静态面：``poll_after_ms`` 进跟随的 data、值取 FOLLOW_MIN_INTERVAL_MS、
    空页判内核给的 ``lines``；drop 仍只有「游标对应的文件已变化」那一处（Q1：旧句柄不 drop）；
    不回 429（服务不强制下限）。"""
    code = strip_ts_comments(need_file(READROUTES_REL))
    problems = []
    if "poll_after_ms" not in code:
        problems.append("跟随响应的 data 应追加 poll_after_ms（只在跟随响应里出现）")
    if code.count("FOLLOW_MIN_INTERVAL_MS") < 2:
        problems.append("FOLLOW_MIN_INTERVAL_MS 不应只是定义（值 2000 要真用在 poll_after_ms 上）")
    if not re.search(r'get\(\s*["\']lines["\']\s*\)', code):
        problems.append('空页复用句柄要判内核给的 lines（page.get("lines") 为空数组）')
    if not re.search(r'get\(\s*["\']next_cursor["\']\s*\)', code):
        problems.append('next_cursor 的换发应仍读内核给的 next_cursor')
    drops = [m.start() for m in re.finditer(r"\.drop\(", code)]
    if len(drops) != 1:
        problems.append(f"readroutes.ts 里 drop 的调用应仍只有「游标对应的文件已变化」那一处"
                        f"（跟随发新句柄不 drop 旧句柄，站主 Q1），实际 {len(drops)} 处")
    if "429" in code:
        problems.append("读路由里不应出现 429（服务不强制轮询下限，队列与 503 兜底）")
    fail_if(problems, "跟随的响应与句柄（D04–D06/D08）")


def test_static_follow_wired_into_route():
    """D03：file 路由的跟随分支真用了 ``--complete-lines``（登记表写了、路由没接等于没实现，
    T009 的教训）；``--cursor=`` 仍由游标拼在末尾。"""
    code = strip_ts_comments(need_file(READROUTES_REL))
    problems = []
    body = _block(code, "async function fileRoute", "\n}\n")
    if not body:
        problems.append("readroutes.ts 里应仍有 fileRoute 处理函数（Repository facts A1）")
    else:
        if '"--complete-lines"' not in body and "FOLLOW" not in body:
            problems.append("fileRoute 的跟随 argv 组装里应出现 \"--complete-lines\"（或引用 FOLLOW_* 登记表）")
    fail_if(problems, "跟随接进 file 路由（D03）")


# ---------------------------------------------------------------------------
# 静态断言：19 条读路由与非跟随的口径不动
# ---------------------------------------------------------------------------

def test_static_routes_and_argv_untouched():
    """D14/D16：19 条读路由一条不动；``FOLLOW_ARGV`` 不并进 ``READ_ROUTE_ARGV``
    （既有断言要求每个以 ``--`` 开头的项都含 ``=``，``--complete-lines`` 是开关）；
    既有 file 两条的示例值仍是 a/b.txt 与 --cursor=fake-cursor-0001。"""
    code = strip_ts_comments(need_file(READROUTES_REL))
    problems = []
    specs = _block(code, "READ_ROUTE_SPECS", "\n];")
    if not specs:
        problems.append("readroutes.ts 里应仍有 READ_ROUTE_SPECS 登记表")
    else:
        names = re.findall(r'name:\s*"([^"]+)"', specs)
        if len(names) != 19:
            problems.append(f"READ_ROUTE_SPECS 应仍恰好 19 条（T016 的口径），实际 {len(names)} 条")
        for name in READ_ROUTE_NAMES:
            if name not in names:
                problems.append(f"读路由 {name} 不见了（19 条一条不动）")
    argv_table = _block(code, "READ_ROUTE_ARGV")
    if not argv_table:
        problems.append("readroutes.ts 里应仍有 READ_ROUTE_ARGV 登记表")
    else:
        if "follow" in argv_table.lower():
            problems.append("FOLLOW_ARGV 不并进 READ_ROUTE_ARGV（--complete-lines 是不含 = 的开关）")
        if "--complete-lines" in argv_table:
            problems.append("READ_ROUTE_ARGV 里不应出现 --complete-lines（A8：既有用例锁死了它的形状）")
        for key in ("api.attempts.file", "api.attempts.file.cursor"):
            entry = _entry(argv_table, f'"{key}"')
            if '"a/b.txt"' not in entry:
                problems.append(f"READ_ROUTE_ARGV 里 {key} 的示例 path 应仍是非跟随的 a/b.txt（一条不改）")
        if '"--cursor=fake-cursor-0001"' not in _entry(argv_table, '"api.attempts.file.cursor"'):
            problems.append("READ_ROUTE_ARGV 的 file.cursor 示例值应仍是 --cursor=fake-cursor-0001")
    fail_if(problems, "19 条读路由与非跟随 argv（D14/D16）")


def test_static_follow_test_files():
    """D17：合同锁定的两个新测试文件在位且要点齐备（F1–F12 与 R1–R3 的覆盖面），
    且不许出现 skip、only、todo。"""
    problems = []
    for rel in FOLLOW_TEST_RELS:
        if not (REPO_ROOT / rel).is_file():
            problems.append(f"{rel} 不存在（合同 Steps 锁定的基准测试文件）")
    if problems:
        fail_if(problems, "基准测试文件在位")
        return
    unit = need_file(FOLLOW_TEST_RELS[0])
    problems += [f"follow.test.ts：{p}" for p in _token_problems(unit, FOLLOW_UNIT_TOKENS)]
    problems += [f"follow.test.ts：{p}" for p in _no_skip_marks(strip_ts_comments(unit))]
    real = need_file(FOLLOW_TEST_RELS[1])
    problems += [f"follow-real.test.ts：{p}" for p in _token_problems(real, FOLLOW_REAL_TOKENS)]
    problems += [f"follow-real.test.ts：{p}" for p in _no_skip_marks(strip_ts_comments(real))]
    fail_if(problems, "两个新测试文件的要点（F1–F12 / R1–R3）")


def test_static_nonfollow_locked_files():
    """D14：三个既有用例文件的哨兵在位——cursors.test.ts 的「done 为真时 next_cursor 是 null」
    那条（钉住非跟随不被带坏）、kernel-real.test.ts 的「逐字节」、argv-templates.test.ts 的
    READ_ROUTE_ARGV 逐项解析（把 --complete-lines 并进去它就红）；cursors.ts 的 1024/LRU 哨兵、
    ui 包依赖清单不加（D16 禁改面）。"""
    problems = []
    cursors_test = need_file("ts/packages/ui/test/cursors.test.ts")
    if 'expect(secondData["next_cursor"]).toBe(null)' not in cursors_test:
        problems.append("cursors.test.ts 的「done 为真时 next_cursor 为 null」那条（非跟随）不见了")
    if "游标对应的文件已变化" not in cursors_test:
        problems.append("cursors.test.ts 的 409 用例（内核报游标失效）不见了")
    real = need_file("ts/packages/ui/test/kernel-real.test.ts")
    if "逐字节" not in real:
        problems.append("kernel-real.test.ts 的「data 与 CLI stdout 逐字节一致」不见了")
    argv_test = need_file("ts/packages/ui/test/argv-templates.test.ts")
    if "Object.entries(READ_ROUTE_ARGV)" not in argv_test:
        problems.append("argv-templates.test.ts 的 READ_ROUTE_ARGV 逐项解析不见了")
    if "--complete-lines" in argv_test:
        problems.append("argv-templates.test.ts 是既有文件（禁改）：FOLLOW_ARGV 的解析用例应在"
                        " follow-real.test.ts 里另起一条 describe（A8）")
    cursors_src = strip_ts_comments(need_file("ts/packages/ui/src/cursors.ts"))
    for needle in ("CURSOR_CAPACITY", "1024", "issue", "take", "drop"):
        if needle not in cursors_src:
            problems.append(f"cursors.ts 是禁改文件：看不到「{needle}」（句柄表的地基原样）")
    pkg = json.loads(need_file("ts/packages/ui/package.json"))
    deps = set(pkg.get("dependencies", {}))
    if deps != {"@themis/base", "@themis/contracts"}:
        problems.append(f"ui 包的依赖清单应仍只有 base 与 contracts（不加依赖），实际 {sorted(deps)}")
    for rel in ("tests/test_gate_t016_baseline.py", "tests/test_gate_t017_baseline.py"):
        if not (REPO_ROOT / rel).is_file():
            problems.append(f"{rel} 不在（T016/T017 的门禁回归，R01/V06 的口径）")
    fail_if(problems, "非跟随的既有断言哨兵（D14/D16）")


def test_static_readme():
    """D15/V08：README 加「## 日志跟随」一节，写齐合同点名的结论；V08 的 need 列表一字不差；
    状态码那一段与 T016 钉住的句柄两条既有段落逐字保留。"""
    text = need_file(README_REL)
    problems = []
    for needle in README_V08_NEEDLES:
        if needle not in text:
            problems.append(f"README 里看不到「{needle}」（V08 的口径）")
    head = text.find("## 日志跟随")
    if head < 0:
        problems.append('README 应有「## 日志跟随」一节')
    else:
        tail = text.find("\n## ", head + 1)
        section = text[head:tail if tail > 0 else len(text)]
        for primary, alt in README_SECTION_NEEDLES:
            if primary not in section and (alt is None or alt not in section):
                where = f"「{primary}」" + (f"或「{alt}」" if alt else "")
                problems.append(f"「日志跟随」一节里看不到 {where}（D15 点名要写的结论）")
    for sentence in README_PRESERVED:
        if sentence not in text:
            problems.append(f"README 的既有段落被改了：看不到「{sentence[:40]}…」（D15 逐字保留）")
    fail_if(problems, "README（D15/V08）")


# ---------------------------------------------------------------------------
# 会话级流水线夹具：vitest 跑两个新文件与三个被锁定的既有用例文件
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
    missing = [rel for rel in FOLLOW_TEST_RELS if not (REPO_ROOT / rel).is_file()]
    if missing:
        pipe.reason = ("候选里还没有两个新测试文件（基线 5913f51，本片的跟随还没实现），未装依赖、"
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
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in FOLLOW_TEST_RELS],
                    "vitest-follow", min(deadline - 60, time.monotonic() + STEP_CAPS["vitest follow"]))
        if not pipe.stopped_reason:
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in LOCKED_NONFOLLOW_RELS],
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
    """流水线真的跑了（两个新测试文件在位、bun/node 找得到、依赖装好、vitest 起了）。"""
    assert pipeline.ran, pipeline.reason
    assert not pipeline.stopped_reason, f"流水线中途停了：{pipeline.stopped_reason}"


def test_pipeline_follow_tests(pipeline):
    """D01–D13/D17/D18（机械判据）：follow.test.ts 与 follow-real.test.ts 在 vitest 下全过
    （F1–F12 的替身用例与 R1–R3 的真内核用例）。"""
    _pipeline_group(pipeline, "vitest-follow")


def test_pipeline_nonfollow_locked(pipeline):
    """D14（机械判据）：cursors.test.ts（含 next_cursor 为 null 那条）、argv-templates.test.ts
    （READ_ROUTE_ARGV 的形状）、kernel-real.test.ts（data 与 CLI stdout 逐字节一致）照旧全过。"""
    _pipeline_group(pipeline, "vitest-locked")
