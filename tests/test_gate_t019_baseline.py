"""T019 战前门禁：桌面端本机服务第 5 片「写配置的预览、确认号与操作终态」（D2 之一）的黑盒基准测试
（合同 t019-desktop-ui-write v2，基线 a1c40f6bfded82ca913e072c1b0f964dd7d720b6）。

被测对象是 ``ts/packages/ui`` 的写链路：``POST /api/v1/preview``（基础 argv 加 ``--dry-run --json``，核对内核
预览的 ``dry_run``/``action``/``state``/``needs_yes``、拿掉 ``state`` 令牌、过 ``PREVIEW_ALLOW`` 脱敏、签发 43 位
确认号），七条写路由（``POST /api/v1/roles/<role>``、``/api/v1/presets/<name>/use|save|remove``、
``/api/v1/config/rollback/<n>``、``/api/v1/plugins/<id>/enable|disable``：同一个 ``validateWriteArgs``/
``buildWriteArgv``、执行是基础 argv 加 ``--expect-state=<state>``、needs_yes 为真才加 ``--yes``、退出 4 转 409 的
stale、确认号的一次性/过期/表满/并发/参数不符），``GET /api/v1/operations/<id>`` 的八键操作记录（容量 100、
断开不取消、超时记 timed_out、满了淘汰最早结束的终态、收不了先看操作表再拿确认号），预览内容是内核算出来的
变化的忠实反映（§2.1：白名单命中的值原样保留、该遮的位置恰为 ``<redacted>``、令牌原文在整个响应正文里一次
都不出现，S14），退出 4 转 409 的七字段信封并记 stale（S15），信封补 ``output`` 与
``--expect-state=<state>`` 的占位（读路由逐字节不变），以及 server.ts 的接线（第四批 writeRoutes、空闲判定看
操作表、``ServeOverrides.confirmationTtlMs``）。

基线（a1c40f6）上三个新源文件（writeroutes、confirmations、operations）与六个新测试文件（write-argv、
write-routes、confirmations、operations、write-real、fake-write-kernel.mjs）都不存在，既有文件里也没有本片的
标记，所以本文件的失败落在「文件不存在」「标记不在」这类断言上，不是导入、收集或语法错误：模块级只导入
标准库，所有仓库文件的读取都发生在用例函数里；流水线（装依赖之后起 vitest 跑六个新测试文件与三个被锁定的
既有用例文件）放在 ``pipeline`` 会话级夹具里，候选里没有新测试文件时不装依赖、不起 vitest。

结构（编号对应合同 DoD 的 D01–D19；合同变异清单 1–23 的抓住靠这些断言加被锁定的 Vitest 用例，战后门禁另出
变异清单）：

- 静态断言（不用流水线，全量 pytest 也跑）：三个新源文件在位、都能从 main.ts 顺 import 到达（D13，接进产品才算
  实现）；``WRITE_ACTIONS`` 七个 action 与参数形状、五类 400 提示原文（D01）；``WRITE_ARGV`` 与七条命令路径
  （D01/D02；“T020 的五个 action 名不登记”“``T020_WRITE_COMMANDS``”两项站主 2026-10-25 退役：T020 把五条接进
  ``WRITE_ACTIONS``、删掉这个导出）；九条路由（预览 + 七写 + 操作查询）、两条
  409 与 404/500 的提示原文、时限键 ``api.preview``（30）/``api.write``（90）、预览对 ``dry_run``/``action``/
  ``state``（含 ``absent`` 的形状）/``needs_yes`` 的核对、执行 argv 的 ``--expect-state=``/``--yes``（D03–D08）；
  confirmations.ts 的 ``CONFIRMATION_TTL_MS = 60_000``/``MAX_CONFIRMATIONS = 100``/43 位 base64url/记录绑定的键
  （D06）；operations.ts 的 ``MAX_OPERATIONS = 100``/五种状态/四种 failed reason/八键投影（D10）；kernelenvelope.ts
  的可选 ``output`` 与 ``--expect-state=<state>`` 占位、写死的 ``"output": []`` 消失（D09）；redaction.ts 的
  ``allowPreviewName``/``allowPreviewText``/``PREVIEW_ALLOW`` 的全部路径与 ``unreadable`` 不进白名单（D12）；
  server.ts 的第四批接线、空闲判定加 ``operations.active()``、三个既有记号与关停次序（D13）；六个新测试文件
  在位且要点齐备（W1–W4/S1–S15/C1–C5/O1–O4/R1–R5，§2.1 写死的预览 JSON 在用例或替身里），
  不许 skip/only/todo（D18）；README 的「写操作」一节与
  V08 口径、既有段落保留（D16）；T016–T018 的哨兵与 ui 依赖清单（D17）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：bun install --frozen-lockfile
  （依赖不齐时）之后起三次 vitest——四个快的本片用例文件（W1–W4/S1–C5/O1–O4）、真内核的 write-real.test.ts
  （R1–R5）、三个被锁定的既有用例文件（argv-templates/cursors/kernel-real，读路由逐字节不变），退出码 0 且
  Tests 行 passed。

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
MAIN_REL = "ts/packages/ui/src/main.ts"

# 合同 Scope：三个新源文件、六个新测试文件、四个改动的既有文件
NEW_SRC_RELS = (
    "ts/packages/ui/src/writeroutes.ts",
    "ts/packages/ui/src/confirmations.ts",
    "ts/packages/ui/src/operations.ts",
)
NEW_TEST_RELS = (
    "ts/packages/ui/test/write-argv.test.ts",
    "ts/packages/ui/test/write-routes.test.ts",
    "ts/packages/ui/test/confirmations.test.ts",
    "ts/packages/ui/test/operations.test.ts",
    "ts/packages/ui/test/write-real.test.ts",
    "ts/packages/ui/test/fixtures/fake-write-kernel.mjs",
)
FAST_WRITE_TEST_RELS = (
    "ts/packages/ui/test/write-argv.test.ts",
    "ts/packages/ui/test/write-routes.test.ts",
    "ts/packages/ui/test/confirmations.test.ts",
    "ts/packages/ui/test/operations.test.ts",
)
REAL_WRITE_TEST_RELS = ("ts/packages/ui/test/write-real.test.ts",)
# D09：读路由逐字节不变的既有用例（流水线里连跑；静态只查哨兵）
LOCKED_READ_RELS = (
    "ts/packages/ui/test/cursors.test.ts",
    "ts/packages/ui/test/argv-templates.test.ts",
    "ts/packages/ui/test/kernel-real.test.ts",
)
# 既有 19 条读路由的名字（T016 的口径一条不动；写路由不并进 readRoutes()）
READ_ROUTE_NAMES = (
    "api.meta.get", "api.status.get", "api.attempts.list", "api.attempts.show", "api.attempts.file",
    "api.usage.get", "api.config.get", "api.config.validate", "api.config.history.list",
    "api.config.history.show", "api.roles.get", "api.profiles.get", "api.presets.list",
    "api.presets.diff", "api.runtimes.get", "api.plugins.list", "api.plugins.show",
    "api.secrets.list", "api.secrets.show",
)
# 合同 Behavior contract 第 1 节：七个 action（T020 只登记不实现的五个，站主 2026-10-25 随 T020 退役）
WRITE_ACTION_NAMES = ("role.set", "preset.use", "preset.save", "preset.remove", "config.rollback",
                      "plugin.enable", "plugin.disable")
# 第 5 节：九条路由的名字与路径
WRITE_ROUTE_NAMES = ("api.preview", "api.roles.set", "api.presets.use", "api.presets.save",
                     "api.presets.remove", "api.config.rollback", "api.plugins.enable",
                     "api.plugins.disable", "api.operations.get")
WRITE_ROUTE_PATHS = ("/api/v1/preview", "/api/v1/roles/", "/api/v1/presets/", "/api/v1/config/rollback/",
                     "/api/v1/plugins/", "/api/v1/operations/")
# 第 1 节：五类 400 的提示原文（固定、不回显请求里的值）
WRITE_400_MESSAGES = ("请求体必须是 JSON 对象", "action 不合法", "参数含有未知键", "参数缺少必填键", "不合法")
# 第 4/5/6 节：409 两种、404 与 500 的提示原文
CONFIRM_409_MESSAGE = "确认号无效、已过期或已用过：请重新预览"
ARGV_409_MESSAGE = "确认号与这次请求的参数不符：请重新预览"
OPERATION_404_MESSAGE = "没有这个操作"
PREVIEW_500_MESSAGE = "内核的预览不合格"
# 第 1 节：role.set 的枚举（kit_roles.py:29 的 ROLES、目标三选一、宿主两选一）
ROLE_ENUM = ("planning_review", "contract", "execution", "scheduler_agent")
TARGET_ENUM = ("manual", "disabled", "interactive_host")
HOST_ENUM = ("claude-code", "codex")
# 第 2/5 节：时限覆盖键与秒数
WRITE_TIMEOUT_KEYS = {"api.preview": 30, "api.write": 90}
# 第 3 节：PREVIEW_ALLOW 放行的绑定字段（before 与 after 各七个）与数组路径
BINDING_FIELDS = ("profile", "runtime", "adapter", "provider", "model", "thinking")
PREVIEW_ARRAY_PATHS = ("changed_keys", "notes", "warnings", "running_attempts")
# 第 6 节：operationView 的八键（一个不能少，值可 null）
OPERATION_KEYS = ("id", "action", "state", "reason", "created_ms", "started_ms", "finished_ms", "envelope")
OPERATION_STATES = ("queued", "running", "succeeded", "failed", "stale", "timed_out")
OPERATION_REASONS = ("exit", "spawn-error", "output-too-large", "closing")
# V08 的 README 口径（合同 Validation commands V08 的 need 列表，一字不差）
README_V08_NEEDLES = ("preview", "confirmation", "operations", "--expect-state", "409", "503", "504",
                      "60", "已知限制", "T020")
# 「写操作」一节必须写到的结论（D16 点名）
README_SECTION_NEEDLES = (
    "确认号",
    "重新预览",
    "参数不符",
    "Retry-After",
    "断开",
    "结果未知",
    "profile",
    "runtime",
    "/api/v1/operations",
)
README_NEW_API_NEEDLES = ("/api/v1/preview", "/api/v1/roles/")
# D16：既有段落保留（基线 README 里逐字抄来的整句）
README_PRESERVED = (
    "状态码：201 作业创建成功",
    "## 日志跟随",
    "`file` 路由的句柄只在内存里：服务重启之后旧句柄一律 409",
    "**作业表只在内存里**",
)
# write-argv.test.ts（W1–W4）要点
WRITE_ARGV_TEST_TOKENS = (
    (r"WRITE_ARGV", "W1：七条基础 argv 的登记表"),
    (r"WRITE_ACTIONS", "W4：动作登记表驱动校验"),
    (r"validateWriteArgs", "W4：同一个校验函数"),
    (r"buildWriteArgv", "W1/W3：由参数拼基础 argv"),
    (r"build_parser", "W1/W2：内核真正的解析器"),
    (r"kit_config", "W1：config 组的解析器"),
    (r"kit_plugins", "W1：plugins 组的解析器"),
    (r"dry_run", "W1：解析出的 dry_run 为真"),
    (r"expect_state", "W1：解析出的 expect_state 是期望值"),
    (r"--dry-run", "W1：预览加 --dry-run --json"),
    (r"--expect-state=", "W1：执行加 --expect-state=v1;config=<64 个 0>"),
    (r"--yes", "W1/W3：needs_yes 才加 --yes（plugins 不加）"),
    (r"请求体必须是 JSON 对象", "W4：提示原文固定"),
    (r"action 不合法", "W4：T020 的五个 action 名回 400"),
    (r"参数含有未知键", "W4：未知键回 400"),
    (r"参数缺少必填键", "W4：缺必填键回 400"),
    (r"\b64\b", "W1：--expect-state 的 64 位十六进制示例"),
)
# write-routes.test.ts（S1–S15）要点
WRITE_ROUTES_TEST_TOKENS = (
    (r"fake-write-kernel", "替身是新的 fake-write-kernel.mjs"),
    (r"FAKE_WRITE_PREVIEW", "预览一支由 FAKE_WRITE_PREVIEW 给 JSON"),
    (r"FAKE_WRITE_PLAN", "执行一支按 FAKE_WRITE_PLAN 走"),
    (r"FAKE_WRITE_GATE", "pause 计划的门文件"),
    (r"startApp", "照 support.ts 的写法在进程内建 app"),
    (r"/api/v1/preview", "S 组的预览请求"),
    (r"confirmation", "S 组的确认号"),
    (r"确认号无效、已过期或已用过", "S1/S2/S3：缺号/过期/用第二次的 409 原文"),
    (r"确认号与这次请求的参数不符", "S4：argv 不符的 409 原文"),
    (r"内核的预览不合格", "S10：预览不合格回 500 的原文"),
    (r"没有这个操作", "S12：查不到操作号的 404 原文"),
    (r"并发", "S5：同一个号并发只接受一个"),
    (r"101", "S7：发 101 个确认号的表满用例"),
    (r"maxConcurrent", "S6：maxConcurrent=1 占住名额"),
    (r"maxQueue", "S6：maxQueue=0 队列满 503"),
    (r"503", "S6：503 不消耗确认号"),
    (r"[Rr]etry-[Aa]fter", "S6：503 带 Retry-After: 2"),
    (r"needs_yes|needsYes", "S8：needs_yes 决定 --yes"),
    (r"--expect-state=", "S9：替身记下的 --expect-state 与预览逐字相同"),
    (r"<state>", "S9：command 里是 --expect-state=<state> 占位"),
    (r"operations", "S12：轮询 GET /api/v1/operations/<id>"),
    (r"AbortController", "S12（U21）：断开用 AbortController"),
    (r"timed_out", "S13：超时记 timed_out"),
    (r"504", "S13：超时回 504"),
    (r"audit-fail", "替身的 audit-fail 计划（U19）"),
    (r"pause", "替身的 pause 计划（U21）"),
    (r"stale", "S15：替身走 stale 计划（退出 4）→ 409 七字段信封、操作记 stale"),
    (r"exit_code", "S15：409 的正文是七字段信封（exit_code 是 4，不是 errorResponse 的形状）"),
)
# 合同 §2.1 写死的替身预览 JSON（S14 的期望值对得上）：FAKE_WRITE_PREVIEW 的内容在用例或替身里
PREVIEW_JSON_TOKENS = (
    (r"demo-model", "S14 放行位：binding_changes[0].after.model 原样"),
    (r"demo-profile", "S14 放行位：after.profile 原样（也是 WRITE_ARGV 的示例值）"),
    (r"demo warning", "S14 放行位：warnings[0] 原样"),
    (r"demo note", "S14 放行位：notes[0] 原样"),
    (r"<redacted>", "S14 被遮位：恰好是字符串 <redacted>"),
    (r"api_key", "S14 被遮位：敏感键 api_key 下的值一律遮"),
    (r"sk-abcdefghijklmnopqrstuvwxyz012345", "S14：令牌原文（替身 JSON 与「全文一次都不出现」共用这一份）"),
    (r"binding_changes", "S14：断言落在 data.preview.binding_changes 上"),
    (r"changed_keys", "S14：resources[0].changed_keys[0] 的断言"),
    (r"dry_run", "§2.1：预览 JSON 的 dry_run 键"),
    (r"needs_yes", "§2.1：预览 JSON 的 needs_yes 键"),
    (r"0{64}|\"0\"\.repeat\(\s*64\s*\)", "§2.1：state 令牌的 64 个 0（过形状校验）"),
)
# confirmations.test.ts（C1–C5）要点
CONFIRMATIONS_TEST_TOKENS = (
    (r"ConfirmationTable", "被测的确认号表"),
    (r"60_000|60000", "C1：TTL 的边界是 60 秒"),
    (r"43", "C5：编号 43 位 base64url"),
    (r"A-Za-z0-9_-\]\{43\}", "C5：形状 ^[A-Za-z0-9_-]{43}$"),
    (r"挤掉|淘汰", "C3：表满先清过期再挤最早发出的未用号"),
    (r"过期", "C1/C2：过期即失效"),
    (r"argv", "C4：绑定核对按 argv"),
    (r"needs_yes|needsYes", "C4：needs_yes 记在表里"),
    (r"state", "C4：state 令牌记在表里"),
    (r"第二次|一次性", "C2：确认号一次性"),
)
# operations.test.ts（O1–O4）要点
OPERATIONS_TEST_TOKENS = (
    (r"OperationTable", "被测的操作表"),
    (r"markRunning", "O1：queued 变 running 只走一次"),
    (r"settle", "O1：终态只走一次（重复忽略）"),
    (r"operationView", "O2：八键投影"),
    (r"created_ms", "O2：created_ms 键"),
    (r"started_ms", "O2：started_ms 键"),
    (r"finished_ms", "O2：finished_ms 键"),
    (r"envelope", "O2：envelope 键（完整信封）"),
    (r"active", "O4：active() 数非终态"),
    (r"100|MAX_OPERATIONS", "O3：容量 100"),
    (r"503", "O3：没有可淘汰的终态回 503"),
    (r"stale", "O1：退出 4 的终态是 stale"),
    (r"timed_out", "O1：超时的终态是 timed_out"),
)
# write-real.test.ts（R1–R5）要点
WRITE_REAL_TEST_TOKENS = (
    (r"THEMIS_PYTHON", "R1–R4：真内核用 THEMIS_PYTHON（A1）"),
    (r"pi_dispatch", "R1–R4：kernel 是 scripts/pi_dispatch.py"),
    (r"startService", "R1–R4：真服务照 harness 的 startService"),
    (r"overrides", "R1：entry overrides 的覆盖入口"),
    (r"state\.json", "R2/R3：按 A4 建 RUNNING 的 attempt"),
    (r"RUNNING", "R2/R3：state.json 写 RUNNING"),
    (r"attempt-001", "R2/R3：.agent/runs/<task>/attempt-001"),
    (r"user-ui", "R2（U7）：审计的 actor 是 user-ui"),
    (r"confirmation", "R2（U7）：confirmation 是 none/flag"),
    (r"history", "R2（U7）：config history --json 读审计"),
    (r"kill_grace_seconds|config set", "R1（U6b）：预览后用 CLI 写一次配置"),
    (r"exit_code", "R1（U6b）：退出 4 的 exit_code"),
    (r"409", "R1（U6b）：退出 4 转 409"),
    (r"逐字节", "R1（U6b）：配置与审计逐字节不变"),
    (r"stale", "R1：操作记 stale"),
    (r"--yes", "R2（U7）：needs_yes 为真时执行带 --yes"),
    (r"needs_yes", "R2/R3：预览的 needs_yes"),
    (r"failed", "R3（U8）：先预览再建 attempt 再执行记 failed/exit"),
    (r"WARN", "R4（U20）：output 里有那条 WARN"),
    (r"\.agent", "R5（U15）：预览前后 .agent/ 逐字节不变"),
)
# fake-write-kernel.mjs 的要点
FAKE_WRITE_KERNEL_TOKENS = (
    (r"FAKE_KERNEL_REPORT", "begin/end 行照既有替身记进同一份报告"),
    (r"FAKE_WRITE_PREVIEW", "预览一支：把 FAKE_WRITE_PREVIEW 给的 JSON 打到 stdout"),
    (r"FAKE_WRITE_PLAN", "执行一支按 FAKE_WRITE_PLAN 走"),
    (r"FAKE_WRITE_GATE", "pause 计划等的门文件"),
    (r"FAKE_WRITE_BEGIN", "pause 先往 stdout 写 FAKE_WRITE_BEGIN"),
    (r"--dry-run", "按 argv 里有没有 --dry-run 分两支"),
    (r"--expect-state", "把执行 argv（含 --expect-state=）记进报告"),
    (r"\"ok\"|'ok'", "计划取值 ok"),
    (r"\"stale\"|'stale'", "计划取值 stale（退出 4）"),
    (r"audit-fail", "计划取值 audit-fail（U19）"),
    (r"\"pause\"|'pause'", "计划取值 pause（U21）"),
)

ASSUMPTIONS = (
    "合同 §2.1 写死的替身预览 JSON 按「在 write-routes.test.ts 或 fake-write-kernel.mjs 里出现」判（替身经环境变量"
    "拿 FAKE_WRITE_PREVIEW，内容放在哪一侧由实现定）；S14 的行为断言（放行位原样、被遮位恰为 <redacted>、"
    "令牌原文全文不出现）由被锁定的 write-routes.test.ts 钉住，静态只查 §2.1 的样例值在那份 JSON 里",
    "「WRITE_ARGV 的键名」合同没写死（七条 action 各一条示例，可选参数的示例键怎么起名留给实现）：静态断言只查"
    " 七条命令路径与示例值（execution、manual、demo-profile、demo-preset、1、example-plugin、demo-permission）"
    " 出现在登记表里，键名与可选项怎么并进去由 write-argv.test.ts 的 W1 逐条钉住",
    "「确认号记录绑定的键名」（needsYes/needs_yes、issued_ms/issuedMs）两种拼法都认：合同只写绑定的内容，不写"
    " 字段名；行为由 confirmations.test.ts 的 C4 钉住",
    "「cadence_seconds 的 60–86400、description 的 200 码点、allow_permission 的 256 码点」按数字字面量（允许"
    " 86400 与 86_400 两种写法）静态钉住；每一类不合格的用例由 write-argv.test.ts 的 W4 钉住",
    "「读路由逐字节不变」的静态面按 19 条路由名与三个既有用例文件的哨兵判；逐字节的行为面由流水线里连跑 "
    "cursors.test.ts / argv-templates.test.ts / kernel-real.test.ts 钉住（D09）",
    "「write-real.test.ts 是 attempt 2」不影响本文件：G01 在两个 attempt 都做完之后才跑，六个测试文件到那时"
    " 都应在位；流水线把它单独一组（起真服务与临时 git 仓库，最慢）",
    "基线 README「已知限制」里「本片不做预览、写路由与凭据录入作业」那句在本片完成后已过时：合同 D16 说既有"
    " 段落逐字保留，本文件不断言这句（改与留都由执行端按 D16 处理，见交付信）",
    "「ui 包依赖清单仍是 base+contracts」「T016–T018 门禁文件在位」是 D17/D18 的哨兵；ts/bun.lock 未改由 V01 的"
    " bun install --frozen-lockfile 机械判，不在本文件静态断言",
)

# 流水线预算：合同 G01 的超时是 600 秒，留出静态用例与 pytest 自身的开销。
PIPELINE_BUDGET = 480
STEP_CAPS = {"bun install": 200, "vitest write": 300, "vitest write-real": 280, "vitest locked": 200}

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


def _num_near(code, name, value):
    """常量定义形如 ``NAME = 60_000``（允许数字分隔符 60000 与类型标注）。"""
    digits = str(value)
    sep = r"_?" if len(digits) > 3 else ""
    pattern = digits[0] + "".join(sep + d for d in digits[1:])
    return re.search(rf"\b{name}\b[^=\n;{{}}]*=\s*{pattern}\b", code) is not None


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


def _write_union():
    """三个新源文件的去注释文本拼在一起（跨文件的合同要点用它找）。"""
    return "\n".join(strip_ts_comments(need_file(rel)) for rel in NEW_SRC_RELS)


# ---------------------------------------------------------------------------
# 静态断言：新源文件在位、接线
# ---------------------------------------------------------------------------

def test_static_new_sources_in_place():
    """D13：合同点名的三个新源文件都在位（基线上还没有实现）。"""
    missing = [rel for rel in NEW_SRC_RELS if not (REPO_ROOT / rel).is_file()]
    fail_if([f"{rel} 不存在（基线上还没有实现）" for rel in missing], "三个新源文件")


def test_static_import_graph():
    """D13：三个新源文件都能从 main.ts 顺 import 到达（写了却没接进产品的不算实现，T009 的教训）。"""
    files = ui_src_files()
    if MAIN_REL not in files:
        fail_if(["ts/packages/ui/src/main.ts 读不到"], "src 接线")
        return
    reached = reachable_from(files, MAIN_REL)
    problems = []
    for rel in NEW_SRC_RELS:
        if rel not in files:
            problems.append(f"{rel} 不存在")
        elif rel not in reached:
            problems.append(f"{rel} 从 main.ts 顺 import 到不了（写了却没接进产品）")
    fail_if(problems, "src 接线（D13）")


def test_static_server_wiring():
    """D13：server.ts 建两张表、``writeRoutes`` 作为第四批进 extraRoutes；空闲判定加
    ``operations.active() > 0``；``ServeOverrides.confirmationTtlMs``；三个既有记号与 IdleTimer 的位置、
    关停先 ``hub.close()`` 一律不动。"""
    server = strip_ts_comments(need_file("ts/packages/ui/src/server.ts"))
    problems = []
    for token in ("writeRoutes", "ConfirmationTable", "OperationTable", "confirmationTtlMs"):
        if token not in server:
            problems.append(f"server.ts 里看不到「{token}」")
    i_extra = server.find("extraRoutes")
    if i_extra < 0 or "writeRoutes" not in server[i_extra:]:
        problems.append("writeRoutes(...) 应并进交给 createApp 的 extraRoutes")
    for token in ("readRoutes", "eventRoutes", "jobRoutes"):
        if token not in server:
            problems.append(f"server.ts 应仍有 {token}(...)（T017 的三个记号不动）")
    i_timer = server.find("new IdleTimer")
    i_app = server.find("createApp(")
    if i_timer < 0 or i_app < 0 or i_timer > i_app:
        problems.append("server.ts 的 IdleTimer 构造应仍在 createApp 之前（找不到判定窗口）")
    else:
        window = server[i_timer:i_app]
        for token in ("hub", "operations"):
            if token not in window:
                problems.append(f"空闲回调应看 {token}（有写在跑时服务不因空闲退出）")
        if not re.search(r"job", window, re.I):
            problems.append("空闲回调应仍看作业表（T017 的口径不动）")
    i_hub = server.find("hub.close")
    i_runner = server.find("runner.shutdown")
    if i_hub < 0:
        problems.append("server.ts 的 shutdown 应先 hub.close()")
    elif i_runner >= 0 and i_hub > i_runner:
        problems.append("hub.close() 必须排在 runner.shutdown() 之前（T017 的口径不动）")
    fail_if(problems, "server.ts 的接线（D13）")


def test_static_no_task_literal():
    """D13/A7：新写的 ui src 文件里不出现 ``<task>/`` 字面量（T017 门禁遍历所有 src 文件查它）。"""
    problems = []
    for rel in NEW_SRC_RELS:
        code = strip_ts_comments(need_file(rel))
        if "<task>/" in code:
            problems.append(f"{rel} 里出现了「<task>/」字面量（T017 的名单规则）")
    fail_if(problems, "新源文件不抄名单模板（D13/A7）")


# ---------------------------------------------------------------------------
# 静态断言：writeroutes.ts（登记、校验、argv、路由、预览、执行）
# ---------------------------------------------------------------------------

def test_static_write_actions_registry():
    """D01：``WRITE_ACTIONS`` 登记七个 action；``WRITE_ARGV`` 是七条命令路径的示例表。T020 的五个 action 名不登记、
    ``T020_WRITE_COMMANDS`` 只登记五条命令路径这两项，站主 2026-10-25 随 T020 退役。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/writeroutes.ts"))
    problems = []
    if "WRITE_ACTIONS" not in code:
        problems.append("writeroutes.ts 应有 WRITE_ACTIONS 登记表（导出）")
    else:
        block = _block(code, "WRITE_ACTIONS", "\n};")
        for action in WRITE_ACTION_NAMES:
            if f'"{action}"' not in block and f"'{action}'" not in block:
                problems.append(f"WRITE_ACTIONS 里应有「{action}」")
    if "WRITE_ARGV" not in code:
        problems.append("writeroutes.ts 应有 WRITE_ARGV 登记表（导出，同 READ_ROUTE_ARGV 的写法）")
    else:
        block = _block(code, "WRITE_ARGV")
        for path in (("config", "role", "set"), ("config", "preset", "use"), ("config", "preset", "save"),
                     ("config", "preset", "remove"), ("config", "rollback", "1"), ("plugins", "enable"),
                     ("plugins", "disable")):
            if not _argv_written(block, *path):
                problems.append(f"WRITE_ARGV 里应有「{' '.join(path)}」（七条命令路径的示例）")
        for sample in ("execution", "manual", "demo-preset", "demo-profile", "example-plugin", "demo-permission"):
            if sample not in block:
                problems.append(f"WRITE_ARGV 的示例值「{sample}」不在登记表里（合同 Behavior contract）")
    fail_if(problems, "WRITE_ACTIONS / WRITE_ARGV（D01/D02）")


def test_static_write_validation():
    """D01/W4/M20：``validateWriteArgs`` 的五类 400 提示原文（固定、不回显请求里的值）；role 的枚举、
    target 三选一或 TASK_ID_RE、host 两选一、cadence 60–86400；TASK_ID_RE 与 PLUGIN_ID_RE；
    number 的形状；allow_permission 的 256 码点上限。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/writeroutes.ts"))
    problems = []
    if "validateWriteArgs" not in code:
        problems.append("writeroutes.ts 应导出 validateWriteArgs（预览与七条写路由用同一个）")
    if "buildWriteArgv" not in code:
        problems.append("writeroutes.ts 应导出 buildWriteArgv（由校验过的参数拼基础 argv）")
    for message in WRITE_400_MESSAGES:
        if message not in code:
            problems.append(f"400 的提示原文「{message}」不在 writeroutes.ts（D01 固定提示）")
    for role in ROLE_ENUM:
        if role not in code:
            problems.append(f"role 的取值「{role}」不在 writeroutes.ts（kit_roles.py:29 的 ROLES）")
    for target in TARGET_ENUM:
        if target not in code:
            problems.append(f"target 的取值「{target}」不在 writeroutes.ts")
    for host in HOST_ENUM:
        if host not in code:
            problems.append(f"host 的取值「{host}」不在 writeroutes.ts（kit_config.py:1650）")
    if "TASK_ID_RE" not in code:
        problems.append("name/target 过 TASK_ID_RE 的校验应引用 @themis/base/secrets（与读路由同源）")
    if "PLUGIN_ID_RE" not in code:
        problems.append("插件 id 的校验应过 PLUGIN_ID_RE 的形状（^a-z 开头）")
    if not _number_written(code, 86400):
        problems.append("cadence_seconds 的上界 86400 不在 writeroutes.ts（60–86400 的整数）")
    if not _number_written(code, 256):
        problems.append("allow_permission 每项的 256 码点上限不在 writeroutes.ts（A5 的形状校验）")
    fail_if(problems, "validateWriteArgs 的形状校验（D01）")


def test_static_write_routes_table():
    """D03–D08：九条路由的名字与路径；两条 409 与 404/500 的提示原文；时限键 api.preview（30 秒）与
    api.write（90 秒，七条共用）。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/writeroutes.ts"))
    problems = []
    for name in WRITE_ROUTE_NAMES:
        if f'"{name}"' not in code and f"'{name}'" not in code:
            problems.append(f"写路由「{name}」不见了（合同 Behavior contract 第 5 节的九条）")
    # 路径可能写成 exact("/api/v1/…")，也可能写成正则字面量 \/api\/v1\/…：两种都认
    unescaped = code.replace("\\/", "/")
    for path in WRITE_ROUTE_PATHS:
        if path not in code and path not in unescaped:
            problems.append(f"路径「{path}」不在 writeroutes.ts")
    if "POST" not in code:
        problems.append("预览与七条写路由都是 POST")
    if "GET" not in code:
        problems.append("操作查询路由 api.operations.get 是 GET")
    for message in (CONFIRM_409_MESSAGE, ARGV_409_MESSAGE, OPERATION_404_MESSAGE, PREVIEW_500_MESSAGE):
        if message not in code:
            problems.append(f"提示原文「{message}」不在 writeroutes.ts")
    for key, seconds in WRITE_TIMEOUT_KEYS.items():
        if f'"{key}"' not in code and f"'{key}'" not in code:
            problems.append(f"时限覆盖键「{key}」不在 writeroutes.ts（七条写路由的时限经它覆盖）")
        if not _number_written(code, seconds):
            problems.append(f"时限 {seconds} 秒不在 writeroutes.ts（{key}）")
    if re.search(r'name\s*:\s*"api\.\w+"[\s\S]{0,800}?public\s*:\s*true', code):
        problems.append("写路由不应标成 public（预览、写与操作查询都要会话）")
    fail_if(problems, "写路由表（D03–D08）")


def test_static_preview_flow():
    """D03/D04/M9/M10/M13/M21：预览起基础 argv 加 --dry-run --json；核对 dry_run/action/state（形状含
    absent）/needs_yes；拿掉 state 再过 redactJson(…, PREVIEW_ALLOW)；data 是 {preview, confirmation}；
    执行加 --expect-state=、needs_yes 为真才加 --yes、不带 --json。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/writeroutes.ts"))
    problems = []
    for token in ("--dry-run", "--json", "--expect-state=", "--yes"):
        if token not in code:
            problems.append(f"预览/执行的 argv 组装里应有「{token}」")
    for token in ("dry_run", "needs_yes"):
        if token not in code:
            problems.append(f"内核预览的键「{token}」应被核对（退出 0 时的四项检查）")
    if "absent" not in code:
        problems.append("state 令牌的形状 ^v1(?:;(?:config|local)=(?:[0-9a-f]{64}|absent))+$ 应在服务侧核对"
                        "（替身给坏令牌回 500，M21）")
    if "redactJson" not in code or "PREVIEW_ALLOW" not in code:
        problems.append("预览对象去掉 state 之后应过 redactJson(…, PREVIEW_ALLOW)（redaction.ts 的白名单）")
    if "preview" not in code or "confirmation" not in code:
        problems.append("预览成功的 data 应是 {preview: …, confirmation: …}（信封仍是七字段）")
    if "canAccept" not in code:
        problems.append("写路由应先看 runner.canAccept()（队列满或关停中回 503 且不消耗确认号）")
    fail_if(problems, "预览与执行的 argv 组装（D03/D04/D07）")


# ---------------------------------------------------------------------------
# 静态断言：confirmations.ts 与 operations.ts
# ---------------------------------------------------------------------------

def test_static_confirmations_table():
    """D06/M1/M2/M16：``CONFIRMATION_TTL_MS = 60_000``、``MAX_CONFIRMATIONS = 100``、43 位 base64url
    （randomBytes(32)）、记录绑 {action, argv, state, needs_yes, issued_ms}、now 可注入、不绑会话。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/confirmations.ts"))
    problems = []
    if "ConfirmationTable" not in code:
        problems.append("confirmations.ts 应有 ConfirmationTable")
    if not _num_near(code, "CONFIRMATION_TTL_MS", 60000):
        problems.append("应有导出常量 CONFIRMATION_TTL_MS = 60_000（从签发算起 60 秒）")
    if not _num_near(code, "MAX_CONFIRMATIONS", 100):
        problems.append("应有导出常量 MAX_CONFIRMATIONS = 100")
    for token in ("randomBytes", "base64url"):
        if token not in code:
            problems.append(f"编号应是 crypto.{token}（43 个字符、随机不可猜）")
    if not re.search(r"(?<![\d.])32(?![\d.])", code):
        problems.append("randomBytes 应取 32 字节（base64url 后 43 个字符）")
    for token in ("argv", "state", "issued"):
        if token not in code:
            problems.append(f"确认号记录应绑定「{token}」（D06 的记录内容）")
    if "needs_yes" not in code and "needsYes" not in code:
        problems.append("确认号记录应绑定 needs_yes（执行时为真才加 --yes）")
    if not re.search(r"\bnow\b", code):
        problems.append("时钟应可注入（构造参数 now，测试用它拨过 60 秒）")
    fail_if(problems, "confirmations.ts（D06）")


def test_static_operations_table():
    """D10/M12/M17：``MAX_OPERATIONS = 100``；状态机 queued→running→succeeded|failed|stale|timed_out
    每一步只走一次；failed 的 reason 四种；operationView 的八键；满了淘汰最早结束的终态、没有可淘汰的回 503。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/operations.ts"))
    problems = []
    if "OperationTable" not in code:
        problems.append("operations.ts 应有 OperationTable")
    if "operationView" not in code:
        problems.append("operations.ts 应导出 operationView（GET /api/v1/operations/<id> 的正文就是它）")
    if not _num_near(code, "MAX_OPERATIONS", 100):
        problems.append("应有导出常量 MAX_OPERATIONS = 100")
    for state in OPERATION_STATES:
        if f'"{state}"' not in code:
            problems.append(f"状态机的「{state}」不见了")
    for reason in OPERATION_REASONS:
        if f'"{reason}"' not in code:
            problems.append(f"failed 的 reason「{reason}」不见了")
    for key in OPERATION_KEYS:
        if key not in code:
            problems.append(f"operationView 的八键里应有「{key}」")
    if "503" not in code:
        problems.append("操作表满且没有可淘汰的终态时应回 503（且不消耗确认号）")
    if "active" not in code:
        problems.append("OperationTable 应有 active()（空闲判定与在跑写计数都看它）")
    fail_if(problems, "operations.ts（D10）")


# ---------------------------------------------------------------------------
# 静态断言：kernelenvelope.ts 与 redaction.ts
# ---------------------------------------------------------------------------

def test_static_kernelenvelope_output():
    """D09/M17：``KernelEnvelope`` 加可选 ``output``（缺省 []）、``envelopeBody`` 把它写进七字段的第四位
    （写死的 ``"output": []`` 消失、读路由不填它仍是 []）；``displayArgv`` 把 ``--expect-state=`` 的值换成
    ``--expect-state=<state>``（与 --cursor/--transcript 同样的写法）。"""
    raw = need_file("ts/packages/ui/src/kernelenvelope.ts")
    code = strip_ts_comments(raw)
    problems = []
    iface = _block(code, "interface KernelEnvelope", "\n}")
    if not re.search(r"readonly\s+output\??\s*:\s*readonly string\[\]", iface):
        problems.append("KernelEnvelope 应有可选的 output（readonly string[]，缺省 []）")
    body = _block(code, "export function envelopeBody", "\n}")
    if "output" not in body:
        problems.append("envelopeBody 应把 output 写进七字段里的第四位")
    if '"output": []' in body:
        problems.append('envelopeBody 里的 "output": [] 是写死的（应改成 envelope.output，读路由靠缺省仍是 []）')
    if '"--expect-state=<state>"' not in code:
        problems.append("displayArgv 应把 --expect-state= 的值换成占位 --expect-state=<state>（令牌不外泄）")
    if '"--cursor=<cursor>"' not in code or '"--transcript=<transcript>"' not in code:
        problems.append("--cursor/--transcript 的占位写法应保持不动（既有行为）")
    fail_if(problems, "kernelenvelope.ts（D09）")


def test_static_redaction_preview_allow():
    """D12：``allowPreviewName``（null 或 1–128 码点、只含 A-Za-z0-9._:/-、tokenShaped 为假）与
    ``allowPreviewText``（redactSecrets(v) === v）；``PREVIEW_ALLOW`` 放行 before/after 各七个绑定字段、
    resources.*.changed_keys.*、notes/warnings/running_attempts；``unreadable`` 不进白名单。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/redaction.ts"))
    problems = []
    for token in ("allowPreviewName", "allowPreviewText", "PREVIEW_ALLOW"):
        if token not in code:
            problems.append(f"redaction.ts 应导出「{token}」")
    if problems:
        fail_if(problems, "redaction.ts（D12）")
        return
    if "tokenShaped" not in code:
        problems.append("allowPreviewName 应过 tokenShaped（不像凭据才放行）")
    if "redactSecrets" not in code:
        problems.append("allowPreviewText 应判 redactSecrets(value) === value")
    if not _number_written(code, 128):
        problems.append("allowPreviewName 的 128 码点上限不在 redaction.ts")
    block = _block(code, "PREVIEW_ALLOW")
    if "binding_changes" not in block:
        problems.append("PREVIEW_ALLOW 应放行 binding_changes.*.before|after 的绑定字段")
    for field in BINDING_FIELDS:
        for section in ("before", "after"):
            if f'"{section}"' not in block or f'"{field}"' not in block:
                problems.append(f"PREVIEW_ALLOW 里看不到「{section}」或「{field}」（七个绑定字段×两段）")
                break
    for path in PREVIEW_ARRAY_PATHS:
        if f'"{path}"' not in block:
            problems.append(f"PREVIEW_ALLOW 应放行「{path}」的数组元素")
    if "unreadable" in block:
        problems.append("unreadable 不进白名单（内核的报错文字照 messages 处理）")
    if '"state"' in block or "'state'" in block:
        problems.append("PREVIEW_ALLOW 不为 state 开口子（令牌在进白名单之前就被拿掉）")
    fail_if(problems, "PREVIEW_ALLOW（D12）")


# ---------------------------------------------------------------------------
# 静态断言：读路由与既有钉子不动
# ---------------------------------------------------------------------------

def test_static_read_routes_untouched():
    """D09/D17：readroutes.ts 里 19 条读路由一条不动、写路由一条不并进去；ui 包依赖清单仍只有
    base 与 contracts；T016–T018 的门禁文件在位（V06 的口径）。"""
    code = strip_ts_comments(need_file("ts/packages/ui/src/readroutes.ts"))
    problems = []
    specs = _block(code, "READ_ROUTE_SPECS", "\n];")
    names = re.findall(r'name:\s*"([^"]+)"', specs)
    if len(names) != 19:
        problems.append(f"READ_ROUTE_SPECS 应仍恰好 19 条（T016 的口径），实际 {len(names)} 条")
    for name in READ_ROUTE_NAMES:
        if name not in names:
            problems.append(f"读路由 {name} 不见了（19 条一条不动）")
    for name in WRITE_ROUTE_NAMES:
        if name in code:
            problems.append(f"readroutes.ts 里出现了 {name}（写路由另建 writeRoutes()，不并进 readRoutes()）")
    if "WRITE" in code:
        problems.append("readroutes.ts 里不应出现 WRITE_* 登记表（写路由在 writeroutes.ts）")
    pkg = json.loads(need_file("ts/packages/ui/package.json"))
    deps = set(pkg.get("dependencies", {}))
    if deps != {"@themis/base", "@themis/contracts"}:
        problems.append(f"ui 包的依赖清单应仍只有 base 与 contracts（不加依赖），实际 {sorted(deps)}")
    for rel in ("tests/test_gate_t016_baseline.py", "tests/test_gate_t017_baseline.py",
                "tests/test_gate_t018_baseline.py"):
        if not (REPO_ROOT / rel).is_file():
            problems.append(f"{rel} 不在（T016–T018 的门禁回归，V06 的口径）")
    fail_if(problems, "读路由与既有钉子（D09/D17）")


def test_static_locked_test_files():
    """D09：三个既有用例文件的哨兵在位——argv-templates.test.ts 的 READ_ROUTE_ARGV 逐项解析、
    kernel-real.test.ts 的「逐字节」、cursors.test.ts 的句柄用例（读路由不被写路由带坏）。"""
    problems = []
    argv_test = need_file("ts/packages/ui/test/argv-templates.test.ts")
    if "Object.entries(READ_ROUTE_ARGV)" not in argv_test:
        problems.append("argv-templates.test.ts 的 READ_ROUTE_ARGV 逐项解析不见了（既有文件禁改）")
    if "WRITE" in argv_test:
        problems.append("argv-templates.test.ts 是既有文件（禁改）：写 argv 的解析用例应在 write-argv.test.ts 里")
    real = need_file("ts/packages/ui/test/kernel-real.test.ts")
    if "逐字节" not in real:
        problems.append("kernel-real.test.ts 的「data 与 CLI stdout 逐字节一致」不见了（读路由不变的地基）")
    cursors_src = strip_ts_comments(need_file("ts/packages/ui/src/cursors.ts"))
    for needle in ("CURSOR_CAPACITY", "1024"):
        if needle not in cursors_src:
            problems.append(f"cursors.ts 是禁改文件：看不到「{needle}」（句柄表的地基原样）")
    fail_if(problems, "既有断言哨兵（D09/D17）")


# ---------------------------------------------------------------------------
# 静态断言：六个新测试文件在位且要点齐备
# ---------------------------------------------------------------------------

def test_static_new_test_files():
    """D18：合同锁定的六个新测试文件在位且要点齐备（W1–W4/S1–S15/C1–C5/O1–O4/R1–R5 与替身的计划；
    §2.1 写死的预览 JSON 在 write-routes.test.ts 或替身里），不许出现 skip、only、todo。"""
    problems = []
    for rel in NEW_TEST_RELS:
        if not (REPO_ROOT / rel).is_file():
            problems.append(f"{rel} 不存在（合同 Steps 锁定的基准测试文件）")
    if problems:
        fail_if(problems, "基准测试文件在位")
        return
    checks = (
        ("ts/packages/ui/test/write-argv.test.ts", WRITE_ARGV_TEST_TOKENS),
        ("ts/packages/ui/test/write-routes.test.ts", WRITE_ROUTES_TEST_TOKENS),
        ("ts/packages/ui/test/confirmations.test.ts", CONFIRMATIONS_TEST_TOKENS),
        ("ts/packages/ui/test/operations.test.ts", OPERATIONS_TEST_TOKENS),
        ("ts/packages/ui/test/write-real.test.ts", WRITE_REAL_TEST_TOKENS),
        ("ts/packages/ui/test/fixtures/fake-write-kernel.mjs", FAKE_WRITE_KERNEL_TOKENS),
    )
    for rel, tokens in checks:
        text = need_file(rel)
        stripped = strip_ts_comments(text)
        problems += [f"{rel}：{p}" for p in _token_problems(stripped, tokens)]
        problems += [f"{rel}：{p}" for p in _no_skip_marks(stripped)]
    # §2.1：FAKE_WRITE_PREVIEW 的写死 JSON 在用例或替身里（S14 的期望值对得上；
    # 预览请求是 role.set，action 与请求的相同，否则服务回 500）
    union = strip_ts_comments(need_file("ts/packages/ui/test/write-routes.test.ts") + "\n"
                              + need_file("ts/packages/ui/test/fixtures/fake-write-kernel.mjs"))
    problems += [f"§2.1 写死的预览 JSON：{p}" for p in _token_problems(union, PREVIEW_JSON_TOKENS)]
    if '"role.set"' not in union and "'role.set'" not in union:
        problems.append("S14：预览请求应是 role.set（action 与替身回的相同，否则服务回 500）")
    fail_if(problems, "六个新测试文件的要点（W/R/S/C/O）")


# ---------------------------------------------------------------------------
# 静态断言：README
# ---------------------------------------------------------------------------

def test_static_readme():
    """D16/V08：README 加「## 写操作」一节写齐合同点名的结论；「最小 API」补预览与写路由；
    V08 的 need 列表一字不差；点名的既有段落逐字保留。"""
    text = need_file("ts/packages/ui/README.md")
    problems = []
    for needle in README_V08_NEEDLES:
        if needle not in text:
            problems.append(f"README 里看不到「{needle}」（V08 的口径）")
    for needle in README_NEW_API_NEEDLES:
        if needle not in text:
            problems.append(f"README 的最小 API 应补「{needle}」（预览与写路由）")
    head = text.find("## 写操作")
    if head < 0:
        problems.append('README 应有「## 写操作」一节')
    else:
        tail = text.find("\n## ", head + 1)
        section = text[head:tail if tail > 0 else len(text)]
        for needle in README_SECTION_NEEDLES:
            if needle not in section:
                problems.append(f"「写操作」一节里看不到「{needle}」（D16 点名要写的结论）")
        if not re.search(r"60\s*秒|60_000|60000|有效期.*60|60.*秒", section):
            problems.append("「写操作」一节应写清确认号 60 秒的有效期")
        if "409" not in section:
            problems.append("「写操作」一节应写 409 的情形（确认号无效/已过期/已用过、参数不符、退出 4 的 stale）")
        if "504" not in section:
            problems.append("「写操作」一节应写 504（超时记 timed_out）")
    for sentence in README_PRESERVED:
        if sentence not in text:
            problems.append(f"README 的既有段落被改了：看不到「{sentence[:30]}…」（D16 逐字保留）")
    fail_if(problems, "README（D16/V08）")


# ---------------------------------------------------------------------------
# 会话级流水线夹具：vitest 跑六个新测试文件与三个被锁定的既有用例文件
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
        pipe.reason = ("候选里还没有本片的测试文件（基线 a1c40f6，写链路还没实现），未装依赖、未起 vitest；"
                       "执行端实现之后，流水线才会运行 bun install 与 vitest")
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
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in FAST_WRITE_TEST_RELS],
                    "vitest-write", min(deadline - 90, time.monotonic() + STEP_CAPS["vitest write"]))
        if not pipe.stopped_reason:
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in REAL_WRITE_TEST_RELS],
                    "vitest-write-real", min(deadline - 60, time.monotonic() + STEP_CAPS["vitest write-real"]))
        if not pipe.stopped_reason:
            _vitest(pipe, node, [rel.removeprefix("ts/") for rel in LOCKED_READ_RELS],
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
    """流水线真的跑了（六个新测试文件在位、bun/node 找得到、依赖装好、vitest 起了）。"""
    assert pipeline.ran, pipeline.reason
    assert not pipeline.stopped_reason, f"流水线中途停了：{pipeline.stopped_reason}"


def test_pipeline_write_tests(pipeline):
    """D01–D13 的机械判据：write-argv / write-routes / confirmations / operations 四个用例文件
    在 vitest 下全过（W1–W4、S1–S15、C1–C5、O1–O4）。"""
    _pipeline_group(pipeline, "vitest-write")


def test_pipeline_write_real(pipeline):
    """D14/D15 的机械判据：真内核的 write-real.test.ts 在 vitest 下全过（R1–R5）。"""
    _pipeline_group(pipeline, "vitest-write-real")


def test_pipeline_locked_read(pipeline):
    """D09 的机械判据：cursors.test.ts、argv-templates.test.ts、kernel-real.test.ts 照旧全过
    （读路由的信封与 argv 逐字节不变）。"""
    _pipeline_group(pipeline, "vitest-locked")
