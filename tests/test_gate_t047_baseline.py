"""T047 战前门禁：桌面端前端第 12 片「七端岗位每行显示岗位拿到了什么：时限与工具、预算、最近一回合，
思考档位格有最近一回合时显示档位三值」+ 服务的白名单与校验器（模型配置 §6 第二条的界面一半，只做片一）
的黑盒基准测试（合同 t047-desktop-web-hub-turns.v1，基线 29e985753e68b333a2ac2d16465f4d3be42d8385）。

被测对象分两半：

- 服务（``ts/packages/ui``）：``redaction.ts`` 的四个新校验器（``allowNonNegativeInt``/``allowToolName``/
  ``allowIsoSecondUtc``/``allowEffortLevels``，名字逐字照合同）与 ``HUB_ROLES_ALLOW`` 追加的 15 条路径
  （``turn.timeout_seconds``/``turn.tools.*``/``turn.budgets`` 五项/``last_turn.at``/``last_turn.adapter``/
  ``last_turn.models.*``/``last_turn.profile``/``last_turn.thinking`` 三项/``last_turn.fallback``）；
  ``posts.*.turn``、``posts.*.last_turn``、``posts.*.turn.budgets``、``posts.*.last_turn.thinking`` 四层对象
  不登记（T031 的判法）；``redaction.test.ts`` 与 ``hub-routes-real.test.ts`` 各追加用例（多档位
  ``high,medium``、带本机路径的 fallback 原文不遮）。
- 前端（``desktop/web``）：``api.ts`` 四个接口与 ``HubPostRow`` 两个可选键；桩六行加 ``turn``/``last_turn``
  （十个绑定字段一个不改）；``roles-logic.ts`` 九个纯函数（``hubTimeoutText``/``hubBudgetText``/``hubMib``/
  ``hubEffortTriple``/``hubEffortDiffers``/``hubEffortState``/``hubLastTurnText``/``hubLastTurnMark``/
  ``hubFallbackExcerpt``）与 ``normalizeHubPost`` 的 ``turn``/``lastTurn`` 归一；``roles-HubPosts.tsx`` 七列变
  十列（「时限与工具」「预算」「最近一回合」插在「替补」与「操作」之间，前六列与「操作」列一字不改）、
  三值格、新样式文件 ``roles-hub-turns.css``；``page-hub.test.tsx`` 两处断言照新行为改 + 新文件
  ``roles-hub-turns.test.ts``。

基线（29e98575）上四个校验器、15 条新路径、九个纯函数、三列、三值格与新样式文件都不存在，所以本文件的
失败落在「记号不在」「文件不存在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有仓库文件
的读取都发生在用例函数里；流水线（npm、Vitest、探针）放在 ``pipeline`` 会话级夹具里（全量 pytest 默认跳过，
点名运行本文件才跑；候选里还没有本片的文件时夹具不调 npm——照 T024/T040/T041/T043/T044/T045 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：redaction.ts 的四个校验器与 15 条新路径、既有面
  不推翻（S01）；两份服务测试的追加用例记号（S02/S03）；api.ts 四个接口与两个可选键（S04）；桩六行的
  turn/last_turn 与十个绑定字段（S05）；roles-logic 九个纯函数与归一（S06）；HubPosts 十列与三值格、
  T038/T045 形状（S07）；roles-hub-turns.css 的令牌规矩（S08）；两份包内测试（S09）；共享面与禁改文件
  字节冻结（S10）。
- 流水线断言（``test_p*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、npm test 全绿；两份
  探针逐份写成 ``gate-probe/probe-<uid>-t047-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，
  ``finally`` 里删除；ts 侧用 node 起 vitest 跑两份改过的测试文件与一份 ts 行为探针（照 T042 的写法，
  依赖不齐且找不到 bun 时停下并写明）。
  - unit（desktop/web）：九个纯函数的逐字口径与 ``normalizeHubPost`` 的归一边界。
  - page（desktop/web）：桩模式十列表头、三个新列的逐格文字、四行三值与两行 EffortPair、contract 行的
    退回替补 Tag 与 title 全文、MiB 段的 aria-label、新格里没有可聚焦元素；真实模式（注入假服务）确认
    旧服务缺键时三列是「—」、页面不出现桩的值。
  - ts-probe（ts/packages/ui）：四个校验器的合格/不合格值、整份 hub 行过 ``redactJson`` 的放行与遮掉。

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
PAGES_RO = f"{SRC_REL}/pages/readonly1"
TESTS_REL = f"{WEB_REL}/tests"
TS = REPO_ROOT / "ts"

REDACTION_REL = "ts/packages/ui/src/redaction.ts"
REDACTION_TEST_REL = "ts/packages/ui/test/redaction.test.ts"
HUB_REAL_TEST_REL = "ts/packages/ui/test/hub-routes-real.test.ts"
API_REL = f"{SRC_REL}/api.ts"
MOCK_HUB_ROLES_REL = f"{SRC_REL}/mock/hub-roles.ts"
ROLES_LOGIC_REL = f"{PAGES_RO}/roles-logic.ts"
HUBPOSTS_REL = f"{PAGES_RO}/roles-HubPosts.tsx"
HUB_TURNS_CSS_REL = f"{PAGES_RO}/roles-hub-turns.css"
PAGE_HUB_TEST_REL = f"{TESTS_REL}/page-hub.test.tsx"
TURNS_LOGIC_TEST_REL = f"{TESTS_REL}/roles-hub-turns.test.ts"

# 基线名单：src/mock 仍恰 14 份 JSON、src/pages 顶层仍恰 9 个 *Page.tsx（合同兼容性）
BASELINE_MOCK_JSON_COUNT = 14
BASELINE_PAGE_COUNT = 9

# 禁改文件的基线冻结（行尾归一 LF 后的字节数与 sha256；全部在合同 forbidden_paths 里：两份依赖与锁文件、
# roles-styles.css（T038 S08 的基线前缀 sha256）、RolesView/RolesPage、两份包内测试、ui 的两条路由文件）
BASELINE_DIGESTS = {
    f"{WEB_REL}/package.json": (820, "094d3622e54097e0f50f0ab2a71a5caa22491dba9d3ac6ef83047426f8c57f5a"),
    f"{WEB_REL}/package-lock.json": (108793, "1bc4e1fbfeb02a17280d0de1d98a5f3b2721fa91229c271c66d590d059d82d28"),
    "ts/package.json": (492, "40543111aa14209fdfb993cffb9173ae9cd5917b2189eb97cc2ff7da02f2601a"),
    "ts/bun.lock": (25475, "a845dc902d2d410846d46610d6f4186b4f958bb06776662459abf76aa1b94f90"),
    f"{PAGES_RO}/roles-styles.css": (4282, "a81ce331e93a3ef9b06f44c76ee3c72d75c0a52f965169437bf9e9f8bd338d06"),
    f"{PAGES_RO}/roles-RolesView.tsx": (2058, "0d662ae27d95a84c488f52fdaab1206b7dae7ed6ef208697c37164ec639c171f"),
    f"{SRC_REL}/pages/RolesPage.tsx": (2193, "eb1be8fd5f53bf34cab1d3f42a2942ac593a1683915aa3de8070aac2eeb3000d"),
    f"{TESTS_REL}/roles-hub-logic.test.ts": (3724, "039a63b960171c919681cd66ac6b59583326afda6e7d861e74aee40c6dd4bf26"),
    f"{TESTS_REL}/page-app.test.tsx": (4005, "a8986dee7f02a1f43579ae8249a9f51ab0158c873e5b7525fda31edd458698e9"),
    "ts/packages/ui/src/readroutes.ts": (33189, "da67f8568f339d1988684cba1e056958a48361132a6bfc180fb5b91c49f42007"),
    "ts/packages/ui/src/writeroutes.ts": (32897, "ef4dd4d345a0820d8031bfccabec97a6f6af05a25941d9f58ca8b57cbdc0fd76"),
}

# HUB_ROLES_ALLOW 既有的 15 条（T031 合同；路径、次序与校验函数一个都不动）
OLD_HUB_ALLOW = (
    (("posts", "*", "post"), "allowEnum"),
    (("posts", "*", "source"), "allowEnum"),
    (("posts", "*", "allowed_adapters", "*"), "HUB_ADAPTER_ENUM"),
    (("posts", "*", "adapter"), "HUB_ADAPTER_ENUM"),
    (("posts", "*", "provider"), "allowBindingName"),
    (("posts", "*", "model"), "allowBindingName"),
    (("posts", "*", "thinking"), "HUB_THINKING_ENUM"),
    (("posts", "*", "profile"), "allowNullableId"),
    (("posts", "*", "runtime"), "allowNullableId"),
    (("posts", "*", "fallback", "adapter"), "HUB_ADAPTER_ENUM"),
    (("posts", "*", "fallback", "provider"), "allowBindingName"),
    (("posts", "*", "fallback", "model"), "allowBindingName"),
    (("posts", "*", "fallback", "thinking"), "HUB_THINKING_ENUM"),
    (("posts", "*", "fallback", "profile"), "allowNullableId"),
    (("posts", "*", "fallback", "runtime"), "allowNullableId"),
)
# 本片追加的 15 条（合同 Behavior contract 第 1 节，路径与校验函数逐条钉死）
NEW_HUB_ALLOW = (
    (("posts", "*", "turn", "timeout_seconds"), "allowNonNegativeInt"),
    (("posts", "*", "turn", "tools", "*"), "allowToolName"),
    (("posts", "*", "turn", "budgets", "max_requests"), "allowNonNegativeInt"),
    (("posts", "*", "turn", "budgets", "max_tool_calls"), "allowNonNegativeInt"),
    (("posts", "*", "turn", "budgets", "max_input_bytes"), "allowNonNegativeInt"),
    (("posts", "*", "turn", "budgets", "max_response_bytes"), "allowNonNegativeInt"),
    (("posts", "*", "turn", "budgets", "max_object_bytes"), "allowNonNegativeInt"),
    (("posts", "*", "last_turn", "at"), "allowIsoSecondUtc"),
    (("posts", "*", "last_turn", "adapter"), "HUB_ADAPTER_ENUM"),
    (("posts", "*", "last_turn", "models", "*"), "allowBindingName"),
    (("posts", "*", "last_turn", "profile"), "allowNullableId"),
    (("posts", "*", "last_turn", "thinking", "requested"), "HUB_THINKING_ENUM"),
    (("posts", "*", "last_turn", "thinking", "mapped"), "HUB_THINKING_ENUM"),
    (("posts", "*", "last_turn", "thinking", "effective"), "allowEffortLevels"),
    (("posts", "*", "last_turn", "fallback"), "allowNullablePreviewText"),
)
# T031 的新判法只认 turn/last_turn 之下的叶子路径：这四层对象本身登记了就会被判成「别的路径」
HUB_LAYER_BAN = (
    ("posts", "*", "turn"),
    ("posts", "*", "last_turn"),
    ("posts", "*", "turn", "budgets"),
    ("posts", "*", "last_turn", "thinking"),
)
# 四个新校验器：名字逐字照合同，函数体里应看到的记号（语义另由 ts 行为探针钉）
NEW_VALIDATOR_MARKS = {
    "allowNonNegativeInt": ("0n", "Number.isInteger", ">= 0"),
    "allowToolName": ("[A-Za-z][A-Za-z0-9_-]{0,63}", "{1,128}", "tokenShaped", "?$/u"),
    "allowIsoSecondUtc": ("\\d{4}-\\d{2}-\\d{2}", "+00:00"),
    "allowEffortLevels": ("split(", "trim", "=== null"),
}
EFFORT_LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")

# roles-logic.ts 的九个纯函数（签名逐字照合同 Behavior contract 第 4 节）
LOGIC_NEW_FUNCTIONS = (
    ("hubTimeoutText", r"export function hubTimeoutText\(\s*turn:\s*HubPostTurnInfo \| null\s*\):\s*string"),
    ("hubBudgetText", r"export function hubBudgetText\(\s*budgets:\s*HubPostBudgetInfo \| null\s*\):\s*string"),
    ("hubMib", r"export function hubMib\(\s*bytes:\s*number \| null\s*\):\s*string"),
    ("hubEffortTriple", r"export function hubEffortTriple\(\s*lastTurn:\s*HubPostLastTurnInfo \| null\s*\):\s*string"),
    ("hubEffortDiffers", r"export function hubEffortDiffers\(\s*lastTurn:\s*HubPostLastTurnInfo \| null\s*\):\s*boolean"),
    ("hubEffortState", r"export function hubEffortState\(\s*lastTurn:\s*HubPostLastTurnInfo \| null\s*\):\s*'none' \| 'unknown' \| 'same' \| 'differs'"),
    ("hubLastTurnText", r"export function hubLastTurnText\(\s*lastTurn:\s*HubPostLastTurnInfo \| null\s*\):\s*string"),
    ("hubLastTurnMark", r"export function hubLastTurnMark\(\s*lastTurn:\s*HubPostLastTurnInfo \| null,\s*boundAdapter:\s*string \| null\s*\)"),
    ("hubFallbackExcerpt", r"export function hubFallbackExcerpt\(\s*text:\s*string \| null\s*\):\s*\{\s*shown:\s*string;\s*full:\s*string;\s*\}"),
)
# 函数体里应看到的口径记号（值与分隔符逐字照合同；完整行为由 unit 探针钉）
LOGIC_BODY_MARKS = {
    "hubTimeoutText": ("/ 60", "分钟", "秒", "·"),
    "hubBudgetText": ("请求 ", "工具调用 ", "MiB"),
    "hubMib": ("Math.round", "1048576"),
    "hubEffortTriple": ("要求 ", "映射 ", "生效 "),
    "hubLastTurnMark": ("退回替补", "与当前绑定不同"),
    "hubFallbackExcerpt": ("slice(0, 20)", "…"),
    "hubEffortState": ("'none'", "'unknown'", "'same'", "'differs'"),
}
LOGIC_NEW_TYPES = ("HubPostBudgetInfo", "HubPostTurnInfo", "HubPostLastTurnThinkingInfo", "HubPostLastTurnInfo")
OLD_LOGIC_EXPORTS = ("hubPostName", "allowedProfiles", "normalizeHubPost")

# 七端岗位的十列（前六列与「操作」一字不改；三个新列插在「替补」与「操作」之间）
HUB_HEADERS = ("岗位", "运行时", "模型", "思考档位", "来源", "替补", "时限与工具", "预算", "最近一回合", "操作")

# api.ts HubPostRow 既有字段的原样声明（基线 29e98575 的原文：接口成员缩进两空格）。D04 要求既有字段
# 与类型一字不改：按基线原文逐字钉住（含缩进、类型与联合），不用行首无缩进锚定——基线成员本来
# 就带两空格缩进，无缩进的 `^字段:` 在未改动的基线上也必红（attempt-002 合同矛盾 1）。
ROW_BASELINE_DECLS = (
    "  post: string;",
    "  source: 'default' | 'config';",
    "  allowed_adapters: string[];",
    "  adapter: string | null;",
    "  provider: string | null;",
    "  model: string | null;",
    "  thinking: string | null;",
    "  profile: string | null;",
    "  runtime: string | null;",
    "  fallback: HubPostFallback | null;",
)

# 新列逐格文字（合同 Behavior contract 第 6 节，桩的六行）
CELL_TEXTS = {
    ("coordinator", "时限与工具"): "10 分钟 · read、grep、find、ls",
    ("coordinator", "预算"): "请求 32 · 工具调用 48 · 2 / 8 / 8 MiB",
    ("coordinator", "最近一回合"): "2026-11-15T08:00:00Z · quizs · deepseek-flash",
    ("planner", "时限与工具"): "40 分钟 · Read、Grep、Glob、Bash(npm view:*)",
    ("planner", "预算"): "—",
    ("planner", "最近一回合"): "2026-11-15T07:30:00Z · claude-code · claude-opus-5-5",
    ("contract", "时限与工具"): "40 分钟 · read、grep、find、ls",
    ("contract", "预算"): "请求 128 · 工具调用 128 · 2 / 8 / 8 MiB",
    ("contract", "最近一回合"): "2026-11-15T09:00:00Z · pi · step-5-preview",
    ("gate", "时限与工具"): "40 分钟 · read、grep、find、ls、edit、write、bash",
    ("gate", "预算"): "—",
    ("gate", "最近一回合"): "2026-11-15T09:15:00Z · pi · cc-switch-zhipu-glm/glm-5.3",
    ("audit", "时限与工具"): "40 分钟 · read、grep、find、ls",
    ("audit", "预算"): "—",
    ("audit", "最近一回合"): "—",
    ("exec", "时限与工具"): "—",
    ("exec", "预算"): "—",
    ("exec", "最近一回合"): "—",
}
# 思考档位：有最近一回合的四行是三值（要求 · 映射 · 生效），audit/exec 两行照旧经 EffortPair
EFFORT_TRIPLES = {
    "coordinator": "要求 high · 映射 high · 生效 —",
    "planner": "要求 max · 映射 — · 生效 max",
    "contract": "要求 high · 映射 — · 生效 high",
    "gate": "要求 high · 映射 — · 生效 high",
}
EFFORT_PAIR_ROWS = {"audit": "要求 max · 生效 未知", "exec": "要求 high · 生效 未知"}
MIB_ARIA = "单次输入 2 MiB、单次回应 8 MiB、单个对象 8 MiB"
CONTRACT_FALLBACK = "读不出资格证书 C:\\Users\\example\\.agent\\mailbox\\quizs\\live\\minimax\\qualification.json"
WARN_TAG = "与要求不同"

# 桩六行：十个绑定字段（基线值，一个不许改）与 turn/last_turn（合同第 3 节的表；键序不钉，逐字段断言）
MOCK_ROW_FIELDS = {
    "coordinator": [
        "post: 'coordinator'", "source: 'default'", "allowed_adapters: ['quizs', 'pi']", "adapter: 'quizs'",
        "provider: 'deepseek'", "model: 'deepseek-flash'", "thinking: 'high'", "profile: null", "runtime: null",
        "fallback: { adapter: 'pi', provider: 'dsf', model: 'deepseek-flash', thinking: 'high' }",
        "timeout_seconds: 600", "tools: ['read', 'grep', 'find', 'ls']",
        "max_requests: 32", "max_tool_calls: 48", "max_input_bytes: 2097152", "max_response_bytes: 8388608",
        "max_object_bytes: 8388608",
        "at: '2026-11-15T08:00:00Z'", "models: ['deepseek-flash']", "requested: 'high'", "mapped: 'high'",
        "effective: null",
    ],
    "planner": [
        "post: 'planner'", "source: 'default'", "allowed_adapters: ['claude-code']", "adapter: 'claude-code'",
        "provider: null", "model: 'claude-opus-5-5'", "thinking: 'max'", "profile: null", "runtime: null",
        "fallback: null",
        "timeout_seconds: 2400", "tools: ['Read', 'Grep', 'Glob', 'Bash(npm view:*)']", "budgets: null",
        "at: '2026-11-15T07:30:00Z'", "models: ['claude-opus-5-5']", "requested: 'max'", "mapped: null",
        "effective: 'max'",
    ],
    "contract": [
        "post: 'contract'", "source: 'config'", "allowed_adapters: ['pi', 'quizs']", "adapter: 'quizs'",
        "provider: 'minimax'", "model: 'MiniMax-M3.1-Flash'", "thinking: 'high'", "profile: 'quizs-m3'",
        "runtime: 'quizs'",
        "fallback: { profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high' }",
        "timeout_seconds: 2400", "tools: ['read', 'grep', 'find', 'ls']",
        "max_requests: 128", "max_tool_calls: 128", "max_input_bytes: 2097152", "max_response_bytes: 8388608",
        "max_object_bytes: 8388608",
        "at: '2026-11-15T09:00:00Z'", "models: ['step-5-preview']", "profile: 'step-high'",
        "requested: 'high'", "mapped: null", "effective: 'high'",
        "fallback: '" + CONTRACT_FALLBACK.replace("\\", "\\\\") + "'",
    ],
    "gate": [
        "post: 'gate'", "source: 'default'", "allowed_adapters: ['pi']", "adapter: 'pi'",
        "provider: 'cc-switch-zhipu-glm'", "model: 'glm-5.3'", "thinking: 'high'", "profile: null", "runtime: null",
        "fallback: null",
        "timeout_seconds: 2400", "tools: ['read', 'grep', 'find', 'ls', 'edit', 'write', 'bash']", "budgets: null",
        "at: '2026-11-15T09:15:00Z'", "models: ['cc-switch-zhipu-glm/glm-5.3']", "requested: 'high'",
        "mapped: null", "effective: 'high'",
    ],
    "audit": [
        "post: 'audit'", "source: 'default'", "allowed_adapters: ['pi', 'quizs']", "adapter: 'pi'",
        "provider: 'minimax'", "model: 'MiniMax-M3.1-Flash'", "thinking: 'max'", "profile: null", "runtime: null",
        "fallback: null",
        "timeout_seconds: 2400", "tools: ['read', 'grep', 'find', 'ls']", "budgets: null", "last_turn: null",
    ],
    "exec": [
        "post: 'exec'", "source: 'config'", "allowed_adapters: ['pi']", "adapter: 'pi'",
        "provider: 'bb'", "model: 'step-5-preview'", "thinking: 'high'", "profile: 'step-high'", "runtime: 'pi'",
        "fallback: null", "turn: null", "last_turn: null",
    ],
}
MOCK_ROW_ORDER = ("coordinator", "planner", "contract", "gate", "audit", "exec")

# 执行端新测试文件的最小覆盖记号（合同第 6、11 步）
TURNS_TEST_TOKENS = (
    "hubTimeoutText", "hubBudgetText", "hubMib", "hubEffortTriple", "hubEffortDiffers", "hubEffortState",
    "hubLastTurnText", "hubLastTurnMark", "hubFallbackExcerpt", "normalizeHubPost", "setLiveClientForTests",
    "45 秒", "2 / 8 / 8 MiB", "high,medium", "退回替补", "与当前绑定不同",
)

# redaction.test.ts 追加用例的记号（合同第 4 步）
REDACTION_TEST_TOKENS = (
    "Bash(npm view:*)", "high,medium", "2026-11-15T08:00:00Z", "2026-11-15T08:00:00+00:00",
    "sk-abcdefghijklmnopqrstuvwxyz0123456789", "<redacted>", "timeout_seconds", "max_object_bytes",
    "last_turn", "HUB_ROLES_ALLOW",
)
# hub-routes-real.test.ts 追加用例的记号（合同第 5 步；回合目录名不钉——合同说随便起一个能排序的名字）
HUB_REAL_TEST_TOKENS = (
    "result.json", "finished_at", "2026-11-15T08:00:00Z", "effort_effective", "high,medium", "quizs_fallback",
    "读不出资格证书", "turn.timeout_seconds", "turn.tools", "max_requests", "max_tool_calls", "last_turn",
    "deepseek-flash",
)
# redaction.test.ts 既有的 describe（一个都不许动）
REDACTION_OLD_DESCRIBES = (
    "usedByShape", "/config 的白名单", "/profiles 的白名单", "/secrets 的白名单", "/secrets/<name> 的白名单",
)
HUB_REAL_OLD_DESCRIBES = ("U9：GET /api/v1/hub/roles 与 config hub show --json 逐字段相等",)

# page-hub.test.tsx 既有断言的记号（一个都不许动）
PAGE_HUB_KEEP_TOKENS = (
    "describe('七端岗位（桩模式渲染 #/roles）'", "失败时不出重试钮", "失败时这一组不渲染表格行",
    "改绑定…", "恢复缺省…",
)
PAGE_HUB_HEADERS_LINE = "['岗位', '运行时', '模型', '思考档位', '来源', '替补', '时限与工具', '预算', '最近一回合', '操作']"

# 新源码的禁词（page-static 的口径 + T006/T009 的 matchMedia 一类；roles-* 系列不查「（UTC 」——时刻原样显示
# 内核给的秒级 UTC 原文，不带「（UTC 」字样，但文件里可能出现 UTC 相关注释，只对 HubPosts 与 css 查旧口径）
FORBIDDEN_SOURCE_MARKS = (
    "XMLHttpRequest", "EventSource", "WebSocket", "dangerouslySetInnerHTML", "innerHTML", "outerHTML",
    "insertAdjacentHTML", "eval(", "new Function", "document.write", "srcdoc", "DOMParser",
    "matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver", "role=\"status\"",
)
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_COLOR_FUNCS = ("rgb(", "rgba(", "hsl(", "hsla(", "color-mix(", "oklch(", "lab(", "hwb(")

# G01 的超时是 600s：夹具总预算压在 575s 以内，用完就停下并在断言里写明
PIPELINE_BUDGET = 575
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 150,
             "ts vitest": 240, "ts probe": 120}

ASSUMPTIONS = (
    "桩六行的 turn/last_turn 按字段断言（键序不钉）：合同第 3 节给的是逐字段值表，键的书写次序不影响行为",
    "「预算」格 MiB 那一段的 aria-label 只在桩的两个 quizs 行（2/8/8）上断言；null 项写「— MiB」由 unit 探针"
    "的纯函数断言覆盖（页面上没有现成的全 null 桩行）",
    "探针断言三值格的 data-state：coordinator（effective 无段）是 unknown、planner/contract/gate 是 same；"
    "「与要求不同」的 warning Tag 在桩上没有触发行（六行里 effective 要么无段要么等于 requested），由 unit "
    "探针的 hubEffortDiffers 与页面的 markup 记号共同背书",
    "禁改文件按字节冻结（行尾归一 LF）：两份依赖与锁文件、roles-styles.css、RolesView、RolesPage、两份包内"
    "测试、ui 的 readroutes/writeroutes——全在合同 forbidden_paths 里",
    "redaction.test.ts 与 hub-routes-real.test.ts 的追加用例按记号断言（合同点名的值都在），运行时行为由 "
    "ts 探针与执行端自己的用例（V05/V06）背书",
    "流水线预算 575 秒（G01 的 600 秒减去静态用例与 pytest 自身开销）：node_modules 已在（执行端 Setup 装过）"
    "就不重装；npm ci 只在依赖不齐时跑；探针在 npm test 之后照跑（红候选也能拿到探针诊断）",
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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043/T044/T045 的同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def _block(text, start_marker, end_marker="\n};"):
    start = text.find(start_marker)
    if start < 0:
        return ""
    end = text.find(end_marker, start)
    return text[start:end if end >= 0 else len(text)]


def _squish(text):
    return re.sub(r"\s+", "", text)


def _no_skip_marks(text):
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
        if re.search(bad, text):
            problems.append(f"出现 {bad}（不许 skip、only、todo）")
    return problems


def _allow_rows(block):
    """白名单块里的 (路径元组, 校验函数名) 有序列表：[["a","*",…], fn] 一行一条。"""
    rows = []
    for m in re.finditer(r"\[\s*\[\s*((?:\"[^\"]*\"\s*,?\s*)+)\]\s*,\s*([A-Za-z_][A-Za-z0-9_]*)", block):
        path = tuple(re.findall(r'"([^"]*)"', m.group(1)))
        rows.append((path, m.group(2)))
    return rows


def _sq(text):
    """去全部空白，再去掉尾逗号（prettier 多行字面量带尾逗号，字段比对不该看它）。"""
    squashed = _squish(text)
    return squashed.replace(",}", "}").replace(",]", "]")


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_redaction_validators_and_paths():
    """S01 / D01：redaction.ts 的四个新校验器（名字逐字）与 HUB_ROLES_ALLOW 追加的 15 条路径
    （校验函数逐条钉死）；既有 15 条路径与次序一条不动；四层对象本身不登记；出处注释注明
    kit_roles.py 与 kit_hub.py。"""
    need_file(REDACTION_REL)
    text = read_rel(REDACTION_REL)
    code = strip_ts_comments(text)
    problems = []
    for name, marks in NEW_VALIDATOR_MARKS.items():
        if f"export function {name}" not in code:
            problems.append(f"redaction.ts 应导出 export function {name}（名字逐字照合同）")
            continue
        body = _block(code, f"export function {name}", "\n}")
        if not body:
            problems.append(f"找不到 {name} 的函数体")
            continue
        for mark in marks:
            if mark not in body:
                problems.append(f"{name} 的函数体里应有记号「{mark}」（合同 Behavior contract 第 1 节）")
        # 合同 §11.1：allowNonNegativeInt/allowIsoSecondUtc/allowEffortLevels 都写明「null 放行」；
        # allowToolName 写的是「不是字符串 → false」（null 也遮），不要 null 分支。
        if name != "allowToolName" and "value === null" not in body and "=== null" not in body:
            problems.append(f"{name} 应对 null 放行（=== null 的分支）")
    # 合格/不合格样例值与档位表不作为静态记号：合同第 1 节只钉语义（正则 + tokenShaped / 七档枚举），
    # 样例名与档位可以写在注释、常量或测试里，行为由 ts 行为探针逐条钉住。
    iso_body = _block(code, "export function allowIsoSecondUtc", "\n}")
    if iso_body and ("\\.\\d{3}" in iso_body or ".000" in iso_body):
        problems.append("allowIsoSecondUtc 是秒级时刻校验，不应要求毫秒位")
    hub_block = _block(code, "export const HUB_ROLES_ALLOW", "\n];")
    if not hub_block:
        problems.append("redaction.ts 应保留 HUB_ROLES_ALLOW")
    else:
        rows = _allow_rows(hub_block)
        paths = [p for p, _ in rows]
        by_path = dict(rows)
        for path, fn in OLD_HUB_ALLOW:
            got = by_path.get(path)
            if got is None:
                problems.append(f"HUB_ROLES_ALLOW 既有路径 {list(path)} 一条不许少")
            elif got != fn:
                problems.append(f"HUB_ROLES_ALLOW 既有路径 {list(path)} 的校验函数应是 {fn}，实际 {got}")
        old_head = [p for p, _ in OLD_HUB_ALLOW]
        if paths[:len(old_head)] != old_head:
            problems.append("既有 15 条路径的次序不许动（新 15 条应排在原有 15 条之后）")
        new_paths = [p for p, _ in NEW_HUB_ALLOW]
        if set(paths[len(old_head):]) != set(new_paths) or len(paths) != 30:
            missing = [list(p) for p in new_paths if p not in set(paths[len(old_head):])]
            extra = [list(p) for p in set(paths[len(old_head):]) - set(new_paths)]
            problems.append(f"追加的 15 条路径应逐条照合同（缺 {missing[:5]}，多 {extra[:5]}，共 {len(paths)} 行）")
        for path, fn in NEW_HUB_ALLOW:
            got = by_path.get(path)
            if got is not None and got != fn:
                problems.append(f"新路径 {list(path)} 的校验函数应是 {fn}，实际 {got}")
        for layer in HUB_LAYER_BAN:
            if layer in set(paths):
                problems.append(f"{list(layer)} 这一层对象不许登记（T031 只认其下的路径）")
    region = text[text.find("allowNonNegativeInt") - 200:] if "allowNonNegativeInt" in text else text
    if "kit_roles.py" not in region:
        problems.append("新校验器那一段的注释应注明出处（scripts/kit_roles.py 的 _hub_turn/_hub_last_turn）")
    if "kit_hub.py" not in text:
        problems.append("redaction.ts 的注释应注明 kit_hub.py（:2683 的多档位拼接、:2145 的本机路径原因）")
    for name in ("allowNonNegativeMs", "allowIsoMsUtc", "allowPreviewName", "allowPreviewText",
                 "allowBindingName", "allowNullableId", "allowNullablePreviewText"):
        if f"export function {name}" not in code:
            problems.append(f"redaction.ts 应保留 export function {name}（语义一个字不许改）")
    fail_if(problems, "redaction.ts 的四个校验器与 15 条新路径（S01）")


def test_s02_redaction_test_appended():
    """S02 / D02：redaction.test.ts 追加一个 describe（既有用例一条不改）——合格值原样放行
    （Bash(npm view:*)、high,medium、两种时刻、带本机路径的 fallback 文字），不合格值变 <redacted>，
    原有 15 条一条不少、四层对象不登记。"""
    need_file(REDACTION_TEST_REL)
    text = read_rel(REDACTION_TEST_REL)
    problems = []
    for token in REDACTION_TEST_TOKENS:
        if token not in text:
            problems.append(f"redaction.test.ts 应含记号「{token}」（合同第 4 步点名的覆盖点）")
    for d in REDACTION_OLD_DESCRIBES:
        if f'describe("{d}"' not in text:
            problems.append(f"redaction.test.ts 既有 describe「{d}」一条不许动")
    squished = _squish(text)
    for layer in HUB_LAYER_BAN:
        dq = '[' + ','.join(f'"{seg}"' for seg in layer) + ']'
        sq = '[' + ','.join(f"'{seg}'" for seg in layer) + ']'
        if dq not in squished and sq not in squished:
            problems.append(f"追加用例应断言白名单里没有 {list(layer)} 这一层（写成路径元组，登记了 T031 会不过）")
    problems.extend(_no_skip_marks(text))
    fail_if(problems, "redaction.test.ts 的追加用例（S02）")


def test_s03_hub_routes_real_appended():
    """S03 / D03：hub-routes-real.test.ts 追加一条真内核用例（既有用例不动）——在夹具仓库的
    .agent/mailbox/turns/<工人>/<回合>/result.json 写一条回合记录，断言读路由与 config hub show --json
    逐字段一致、coordinator 行的 turn 与 last_turn 各字段（多档位 high,medium、带本机路径的 fallback
    原文）、其余五个岗位的 last_turn 是 null。"""
    need_file(HUB_REAL_TEST_REL)
    text = read_rel(HUB_REAL_TEST_REL)
    problems = []
    for token in HUB_REAL_TEST_TOKENS:
        if token not in text:
            problems.append(f"hub-routes-real.test.ts 应含记号「{token}」（合同第 5 步点名的覆盖点）")
    for token in ("turns", "womovie-c8"):
        if token not in text:
            problems.append(f"hub-routes-real.test.ts 应含记号「{token}」（coordinator 的信箱在 turns/<工人> 下）")
    for d in HUB_REAL_OLD_DESCRIBES:
        if f'describe("{d}"' not in text:
            problems.append(f"hub-routes-real.test.ts 既有 describe「{d}」一条不许动")
    problems.extend(_no_skip_marks(text))
    fail_if(problems, "hub-routes-real.test.ts 的追加用例（S03）")


def test_s04_api_types():
    """S04 / D04、兼容性：api.ts 只加不改——四个新接口（HubPostBudgets/HubPostTurn/HubPostLastTurnThinking/
    HubPostLastTurn）与 HubPostRow 的两个可选键 turn?/last_turn?；既有十一个字段与 HubRolesData 一字不改。"""
    need_file(API_REL)
    text = read_rel(API_REL)
    code = strip_ts_comments(text)
    problems = []
    budgets = _block(code, "export interface HubPostBudgets")
    if not budgets:
        problems.append("api.ts 应加 export interface HubPostBudgets")
    else:
        for field in ("max_requests", "max_tool_calls", "max_input_bytes", "max_response_bytes", "max_object_bytes"):
            if f"{field}: number | null;" not in budgets:
                problems.append(f"HubPostBudgets 应有 {field}: number | null;")
    turn = _block(code, "export interface HubPostTurn")
    if not turn:
        problems.append("api.ts 应加 export interface HubPostTurn")
    else:
        for decl in ("timeout_seconds: number | null;", "tools: string[];", "budgets: HubPostBudgets | null;"):
            if decl not in turn:
                problems.append(f"HubPostTurn 应有 {decl}")
    think = _block(code, "export interface HubPostLastTurnThinking")
    if not think:
        problems.append("api.ts 应加 export interface HubPostLastTurnThinking")
    else:
        for decl in ("requested: string | null;", "mapped: string | null;", "effective: string | null;"):
            if decl not in think:
                problems.append(f"HubPostLastTurnThinking 应有 {decl}")
    last = _block(code, "export interface HubPostLastTurn")
    if not last:
        problems.append("api.ts 应加 export interface HubPostLastTurn")
    else:
        for decl in ("at: string | null;", "adapter: string | null;", "models: string[];",
                     "profile: string | null;", "thinking: HubPostLastTurnThinking;", "fallback: string | null;"):
            if decl not in last:
                problems.append(f"HubPostLastTurn 应有 {decl}")
    row = _block(code, "export interface HubPostRow", "\n}")
    if not row:
        problems.append("api.ts 应保留 export interface HubPostRow")
    else:
        if "turn?: HubPostTurn | null;" not in row:
            problems.append("HubPostRow 应加可选键 turn?: HubPostTurn | null;（旧服务缺键也能编译）")
        if "last_turn?: HubPostLastTurn | null;" not in row:
            problems.append("HubPostRow 应加可选键 last_turn?: HubPostLastTurn | null;")
        for decl in ROW_BASELINE_DECLS:
            if not re.search(rf"^{re.escape(decl)}$", row, re.M):
                problems.append(f"HubPostRow 既有字段应一字不改（含两空格缩进与类型）：{decl.strip()}")
    roles = _block(code, "export interface HubRolesData")
    if "posts: HubPostRow[];" not in roles:
        problems.append("HubRolesData 应不变（posts: HubPostRow[];）")
    fail_if(problems, "api.ts 的四个接口与两个可选键（S04）")


def test_s05_mock_hub_rows():
    """S05 / D05：桩六行——十个绑定字段一个不改（基线值逐字段比对），每行加 turn 与 last_turn
    （合同第 3 节的表逐字段断言；键序不钉）；行序照旧六行。"""
    need_file(MOCK_HUB_ROLES_REL)
    text = read_rel(MOCK_HUB_ROLES_REL)
    squished = _squish(text)
    problems = []
    posts = [m.group(1) for m in re.finditer(r"post: '([a-z]+)'", text)]
    if posts != list(MOCK_ROW_ORDER):
        problems.append(f"桩的行序应是 {list(MOCK_ROW_ORDER)}，实际 {posts}")
    spans = [(m.start(), m.group(1)) for m in re.finditer(r"post: '([a-z]+)'", text)]
    for i, (start, post) in enumerate(spans):
        end = spans[i + 1][0] if i + 1 < len(spans) else len(text)
        row = _sq(text[start:end])
        for field in MOCK_ROW_FIELDS[post]:
            if _sq(field) not in row:
                problems.append(f"桩的 {post} 行应有「{field}」（合同第 3 节的表 / 基线绑定值）")
    # last_turn: 里含子串 turn:，直接 count 会双计：用前置边界（前一个字符不是字母/数字/下划线）数各自恰 6 处
    if len(re.findall(r"(?<![\w_])turn:", squished)) != 6:
        problems.append(f"六行每行都应有 turn:…（找到 {len(re.findall(r'(?<![\\w_])turn:', squished))} 处）")
    if len(re.findall(r"(?<![\w_])last_turn:", squished)) != 6:
        problems.append(f"六行每行都应有 last_turn:…（找到 {len(re.findall(r'(?<![\\w_])last_turn:', squished))} 处）")
    if "getQuizsLive" in text or "getRaw" in text:
        problems.append("桩文件不应顺手加 live 读取（那是片二）")
    fail_if(problems, "桩六行的 turn/last_turn 与十个绑定字段（S05）")


def test_s06_roles_logic_functions():
    """S06 / D06：roles-logic.ts 只追加——九个纯函数（签名逐字照合同）与四个归一类型；
    normalizeHubPost 的返回值加 turn/lastTurn 两个字段；三个既有导出一字不动，仍只 import type。"""
    need_file(ROLES_LOGIC_REL)
    text = read_rel(ROLES_LOGIC_REL)
    code = strip_ts_comments(text)
    problems = []
    for name, pattern in LOGIC_NEW_FUNCTIONS:
        if not re.search(pattern, code):
            problems.append(f"roles-logic.ts 应导出 {name}（签名逐字照合同第 4 节）")
    for tname in LOGIC_NEW_TYPES:
        if not re.search(rf"export (?:interface|type) {tname}\b", code):
            problems.append(f"roles-logic.ts 应导出类型 {tname}（名字逐字照合同）")
    for name, marks in LOGIC_BODY_MARKS.items():
        body = _block(code, f"export function {name}", "\n}")
        if not body:
            problems.append(f"找不到 {name} 的函数体")
            continue
        for mark in marks:
            if mark not in body:
                problems.append(f"{name} 的函数体里应有记号「{mark}」（口径逐字照合同）")
    norm = _block(code, "export function normalizeHubPost")
    if not norm:
        problems.append("roles-logic.ts 应保留 normalizeHubPost")
    else:
        for token in ("turn:", "lastTurn:"):
            if token not in norm:
                problems.append(f"normalizeHubPost 的返回值应加 {token} 字段（合同第 4 节）")
    imports = re.findall(r"import[^;]*?from\s*['\"][^'\"]+['\"]", text)
    for stmt in imports:
        if not stmt.lstrip().startswith("import type"):
            problems.append(f"roles-logic.ts 只许 import type（T038 S07）：{stmt.strip()[:60]}")
    for name in OLD_LOGIC_EXPORTS:
        if not re.search(rf"export function {name}\(", code):
            problems.append(f"既有导出 {name} 应保留（签名与行为不变）")
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"roles-logic.ts 不应出现 {bad}")
    if _HEX_COLOR.search(code) or any(fn in code for fn in _COLOR_FUNCS):
        problems.append("roles-logic.ts 不应写死颜色")
    fail_if(problems, "roles-logic.ts 的九个纯函数与归一（S06）")


def test_s07_hub_posts_columns():
    """S07 / D07、D08、D11：roles-HubPosts.tsx 七列变十列（次序逐字）；前六列与「操作」列一字不改；
    三值格的 markup（tt-effort、data-state、三个 __label 与三个 __level、与要求不同的 warning Tag）；
    预算格 MiB 段的 aria-label；最近一回合格的退回替补/与当前绑定不同 Tag 与 fallback 截断的 title；
    lastTurn 为 null 的行照旧经 EffortPair；新样式文件在组件 import 之后引入；静态形状一个不少。"""
    need_file(HUBPOSTS_REL)
    text = read_rel(HUBPOSTS_REL)
    code = strip_ts_comments(text)
    problems = []
    cols = _block(code, "const COLUMNS", "\n];")
    headers = re.findall(r"header: '([^']+)'", cols)
    if tuple(headers) != HUB_HEADERS:
        problems.append(f"列头应恰为十列 {list(HUB_HEADERS)}，实际 {headers}")
    for token in ('Section title="七端岗位"', 'aria-label="七端岗位"', "rowHeight={40}",
                  "rl-table rl-hub", "hubPostName", "rowAttrs", "'data-post'"):
        if token not in code:
            problems.append(f"T038/T045 的静态形状应保留（看不到 {token}）")
    if "data-role" in code:
        problems.append("七端岗位一组不出现 data-role（行属性用 data-post）")
    if "<EffortPair requested={p.thinking} effective={null} />" not in code:
        problems.append("lastTurn 为 null 的行应照旧渲染 <EffortPair requested={p.thinking} effective={null} />")
    for token in ('className="tt-effort"', "data-state=", "tt-effort__label", "tt-effort__level"):
        if token not in code:
            problems.append(f"三值格的 markup 应含 {token}")
    if "hubEffortState(" not in code:
        problems.append("三值格的 data-state 应用 hubEffortState(lastTurn)")
    if 'tone="warning">与要求不同' not in code:
        problems.append("hubEffortDiffers 为真时应加 warning Tag（文字逐字「与要求不同」）")
    for token in ("hubTimeoutText(", "hubBudgetText(", "hubLastTurnText("):
        if token not in code:
            problems.append(f"三个新格的文字应分别来自 {token}…)")
    if "单次输入" not in code or "单次回应" not in code or "单个对象" not in code:
        problems.append("预算格的 MiB 段应带 aria-label（单次输入/单次回应/单个对象 … MiB）")
    if "hubLastTurnMark(" not in code:
        problems.append("最近一回合格应用 hubLastTurnMark 判断标签")
    if 'tone="warning">退回替补' not in code:
        problems.append("退回替补应是 warning Tag（文字逐字「退回替补」）")
    if 'tone="neutral">与当前绑定不同' not in code:
        problems.append("与当前绑定不同应是 neutral Tag（文字逐字「与当前绑定不同」）")
    if "hubFallbackExcerpt(" not in code or "title=" not in code:
        problems.append("fallback 非 null 时应显示 hubFallbackExcerpt 的截断文字，并给这一段文字加 title 全文")
    css_pos = text.find("import './roles-hub-turns.css';")
    if css_pos < 0:
        problems.append("roles-HubPosts.tsx 应 import './roles-hub-turns.css'（样式表接进产品）")
    else:
        after = [stmt for stmt in re.findall(r"import[^;]*?from\s*['\"]\./[^'\"]+['\"]", text)
                 if text.find(stmt) > css_pos]
        if after:
            problems.append("import './roles-hub-turns.css' 应放在组件 import 之后（合同第 5 节）")
    for stmt in re.findall(r"import[^;]*?from\s*['\"]\.\./\.\./api['\"]", text, re.S):
        if not stmt.lstrip().startswith("import type"):
            problems.append(f"roles-HubPosts.tsx 从 '../../api' 只许 import type：{stmt.strip()[:60]}")
    ok_branch = code.find("hub.ok && hub.data")
    wf_pos = code.find("<WriteFlow flow={flow} />")
    if wf_pos < 0:
        problems.append("读成功的分支里应保留 <WriteFlow flow={flow} />")
    elif ok_branch >= 0 and wf_pos < ok_branch:
        problems.append("<WriteFlow flow={flow} /> 应只在读成功的分支里")
    if "没能读到七端岗位" not in code:
        problems.append("读失败分支的失败信封应照旧（没能读到七端岗位…）")
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"roles-HubPosts.tsx 不应出现 {bad}")
    if "style={{" in text:
        problems.append("roles-HubPosts.tsx 不出现内联 style")
    if "step-low" in code:
        problems.append("roles-HubPosts.tsx 不应写死 step-low")
    if _HEX_COLOR.search(code) or any(fn in code for fn in _COLOR_FUNCS):
        problems.append("roles-HubPosts.tsx 不应写死颜色")
    fail_if(problems, "roles-HubPosts.tsx 的十列与三值格（S07）")


def test_s08_hub_turns_css():
    """S08 / D09：新文件 roles-hub-turns.css——放宽表宽的那条写成 .rl-hub table.tt-table
    { min-width: 1120px; }（比 roles-styles.css:69 的 .rl-hub .tt-table 特异性高才不会被盖掉）；
    只用 --tt-* 令牌、不声明令牌、不写死颜色；px 字面量除 0 与 1px 外要带出处注释；带出处注释。"""
    need_file(HUB_TURNS_CSS_REL)
    text = read_rel(HUB_TURNS_CSS_REL)
    code = strip_ts_comments(text)
    problems = []
    if ".rl-hubtable.tt-table{min-width:1120px;}" not in _squish(code):
        problems.append("放宽表宽的那条应写成 .rl-hub table.tt-table { min-width: 1120px; }（特异性 (0,2,1)）")
    if re.search(r"^\s*--tt-[\w-]+\s*:", code, re.M):
        problems.append("roles-hub-turns.css 不应声明令牌（只用 src/styles/tokens.css 里已定义的）")
    if _HEX_COLOR.search(code) or any(fn in code for fn in _COLOR_FUNCS):
        problems.append("roles-hub-turns.css 不应写死颜色（只用 --tt-* 令牌）")
    for m in re.finditer(r"(\d+(?:\.\d+)?)px", text):
        # 出处核对在剥注释前的原文上做（合同第 5 节：出处就是 /* */ 注释，剥掉再核对必空——
        # attempt-002 合同矛盾 2）；其余断言（令牌、颜色、禁词）照旧在剥注释后的代码上做。
        value = m.group(1)
        if value in ("0", "1"):
            continue
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.end())
        line = text[line_start:line_end if line_end >= 0 else len(text)]
        if not (re.search(r"出处|照 .*的写法|与 .*同口径", line) or re.search(r"/\*.+?\*/", line)):
            problems.append(f"px 字面量 {value}px 所在行要带出处注释：{line.strip()[:60]}")
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"roles-hub-turns.css 不应出现 {bad}")
    fail_if(problems, "roles-hub-turns.css 新文件（S08）")


def test_s09_package_tests():
    """S09 / D10：page-hub.test.tsx 只改两处断言（列头十列、思考档位逐行）并新增一个新列逐格文字的
    用例（describe 标题不动、既有断言不删）；新文件 roles-hub-turns.test.ts 在位且覆盖记号齐备；
    都不许 skip/only/todo。"""
    problems = []
    hub_text = read_rel(need_file(PAGE_HUB_TEST_REL))
    if _squish(PAGE_HUB_HEADERS_LINE) not in _squish(hub_text):
        problems.append("page-hub.test.tsx 的列头断言应改成十列（含三个新列）")
    for token in PAGE_HUB_KEEP_TOKENS:
        if token not in hub_text:
            problems.append(f"page-hub.test.tsx 的既有断言应照旧（看不到 {token}）")
    for post, triple in EFFORT_TRIPLES.items():
        if triple not in hub_text:
            problems.append(f"page-hub.test.tsx 的思考档位逐行断言应含 {post} 行的三值「{triple}」")
    for post, pair_text in EFFORT_PAIR_ROWS.items():
        if pair_text not in hub_text:
            problems.append(f"page-hub.test.tsx 的 audit/exec 两行应照旧断言 EffortPair 文字「{pair_text}」")
    for (post, col), cell in CELL_TEXTS.items():
        if col == "最近一回合" and post in ("audit", "exec"):
            continue
        if cell not in hub_text:
            problems.append(f"page-hub.test.tsx 应新增新列逐格文字的用例（{post} 的「{col}」是「{cell}」）")
    if "退回替补" not in hub_text or "title" not in hub_text:
        problems.append("page-hub.test.tsx 的新用例应断言 contract 行的退回替补 Tag 与 title 全文")
    problems.extend("page-hub.test.tsx: " + p for p in _no_skip_marks(hub_text))
    turns_text = read_rel(need_file(TURNS_LOGIC_TEST_REL))
    for token in TURNS_TEST_TOKENS:
        if token not in turns_text:
            problems.append(f"roles-hub-turns.test.ts 应含记号「{token}」（合同第 6 节点名的覆盖点）")
    problems.extend("roles-hub-turns.test.ts: " + p for p in _no_skip_marks(turns_text))
    fail_if(problems, "两份包内测试（S09）")


def test_s10_shared_surfaces():
    """S10 / D12、D13、兼容性：共享面——src/mock 仍恰 14 份 JSON、src/pages 顶层仍恰 9 个 *Page.tsx；
    禁改文件字节冻结（依赖与锁文件、roles-styles.css、RolesView、RolesPage、两份包内测试、
    ui 的 readroutes/writeroutes）；RolesPage 的并行四读一字不改。"""
    problems = []
    mock_jsons = sorted(p.name for p in (REPO_ROOT / SRC_REL / "mock").glob("*.json"))
    if len(mock_jsons) != BASELINE_MOCK_JSON_COUNT:
        problems.append(f"src/mock 应仍恰 {BASELINE_MOCK_JSON_COUNT} 份 JSON，实际 {len(mock_jsons)}：{mock_jsons}")
    pages = sorted(p.name for p in (REPO_ROOT / SRC_REL / "pages").glob("*Page.tsx"))
    if len(pages) != BASELINE_PAGE_COUNT:
        problems.append(f"src/pages 顶层应仍恰 {BASELINE_PAGE_COUNT} 个 *Page.tsx，实际 {len(pages)}：{pages}")
    for rel, digest in BASELINE_DIGESTS.items():
        got = file_digest(REPO_ROOT / rel)
        if got != digest:
            problems.append(f"{rel} 应字节冻结（行尾归一 LF 后 {digest[0]} 字节），实际 {got}")
    roles_page = read_rel(need_file(f"{SRC_REL}/pages/RolesPage.tsx"))
    if "Promise.all([getRoles(),getProfiles(),getPresets(),getHubRoles()])" not in _squish(roles_page):
        problems.append("RolesPage 的并行四读一字不改（getQuizsLive 不许加进 Promise.all）")
    if "getQuizsLive" in roles_page:
        problems.append("本片不读 live（getQuizsLive 不出现在 RolesPage）")
    fail_if(problems, "共享面与禁改面（S10）")


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 T045 门禁的写法）+ ts 侧 vitest（照 T042 门禁的写法）
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
        self.steps = {}
        self.status_before = None
        self.status_after = None
        self.digests_before = {}
        self.digests_after = {}
        self.probe_files = {}
        self.probe_skipped = {}
        self.gate_probe_left = None
        self.groups = {}
        self.ts_probe_removed = True
        self.ts_probe_rel = ""

    def group(self, name):
        return self.groups.setdefault(name, Group(name))


def _kill_tree(proc):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=60)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        proc.kill()


def run_capture(argv, cwd, timeout, env=None):
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    start = time.monotonic()
    proc = subprocess.Popen(argv, cwd=str(cwd), env=env or dict(os.environ),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
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
    for name in ("QUIZS_CMD", "QUIZS_LIVE_PLAN", "QUIZS_PROVIDER_PROFILE", "QUIZS_QUALIFICATION"):
        env.pop(name, None)
    return env


def git_status_set():
    proc = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
                          cwd=REPO_ROOT, capture_output=True, timeout=120)
    assert proc.returncode == 0, f"git status 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


def t047_marker_present():
    """候选里是否已有 T047 的标记（roles-logic 的纯函数或新样式文件）：没有就不起 npm（基线上必然没有）。"""
    try:
        return "hubTimeoutText" in _read(REPO_ROOT / ROLES_LOGIC_REL) or (REPO_ROOT / HUB_TURNS_CSS_REL).is_file()
    except OSError:
        return (REPO_ROOT / HUB_TURNS_CSS_REL).is_file()


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


def _ts_deps_ready():
    return ((TS / "node_modules" / ".themis-installed").is_file()
            and (TS / "node_modules" / "vitest").is_dir())


#: 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")
PROBE_SPECS = {
    "unit": (None, (ROLES_LOGIC_REL,)),
    "page": (None, (HUBPOSTS_REL, HUB_TURNS_CSS_REL, ROLES_LOGIC_REL, MOCK_HUB_ROLES_REL)),
}
PROBE_ORDER = ("unit", "page")
TS_VITEST_FILES = ("packages/ui/test/redaction.test.ts", "packages/ui/test/hub-routes-real.test.ts")
TS_PROBE_SOURCE = None


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    PROBE_SPECS["unit"] = (UNIT_PROBE, PROBE_SPECS["unit"][1])
    PROBE_SPECS["page"] = (PAGE_PROBE, PROBE_SPECS["page"][1])
    globals()["TS_PROBE_SOURCE"] = TS_PROBE_SRC
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t047_marker_present():
        pipe.reason = ("候选里还没有 T047 的标记（roles-logic 的 hubTimeoutText 或新样式文件 roles-hub-turns.css），"
                       "没有东西可测，未调用 npm；候选把纯函数、三列与三值格接上之后，流水线才会运行"
                       " npm ci、Vitest 与探针")
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
    ts_probe_rel = ""
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
        if not ci_ok:
            pipe.stopped_reason = "npm ci（含 --offline 兑底）失败，后续步骤未运行"
            return pipe
        # npm test 的结果照记；探针照跑（红候选也能拿到探针诊断，照 T047 的下游须知）
        run_step("npm test", [npm, "test"])
        if (WEB / "node_modules" / "vitest").is_dir():
            uid = uuid.uuid4().hex[:12]
            for key in PROBE_ORDER:
                missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                name = f"probe-{uid}-t047-{key}.test.tsx"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                written.append(path)
                path.write_text(PROBE_SPECS[key][0], encoding="utf-8", newline="\n")
                pipe.probe_files[key] = name
                run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        else:
            for key in PROBE_ORDER:
                pipe.probe_skipped[key] = "node_modules 不齐，探针未运行"
        # ts 侧：依赖齐了才起 vitest（bun install 只在依赖不齐且找得到 bun 时跑）
        ts_pipe(pipe, node, env, deadline)
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
        if ts_probe_rel or pipe.ts_probe_rel:
            ts_dir = REPO_ROOT / (ts_probe_rel or pipe.ts_probe_rel)
            try:
                shutil.rmtree(ts_dir.parent)
                pipe.ts_probe_removed = True
            except OSError:
                pipe.ts_probe_removed = False
        pipe.status_after = git_status_set()
        pipe.digests_after = {name: file_digest(WEB / name) for name in WATCHED}
    return pipe


def ts_pipe(pipe, node, env, deadline):
    """ts 侧的 vitest：两份改过的测试文件 + 一份行为探针；依赖不齐时先 bun install（找不到 bun 就停下并写明）。"""
    grp = pipe.group("ts-vitest")
    if not all((TS / rel).is_file() for rel in TS_VITEST_FILES):
        grp.check(False, f"ts 的两份测试文件不在：{list(TS_VITEST_FILES)}")
        return grp
    if not _ts_deps_ready():
        bun = find_bun()
        if bun is None:
            grp.check(False, "ts 依赖不齐且 PATH 上找不到 Bun（bun.exe 或 npm 的 bun.cmd 垫片旁边的 bun.exe）："
                             "执行端 Setup 的 bun install --frozen-lockfile 跑过就有了")
            return grp
        remaining = deadline - time.monotonic()
        if remaining <= 60:
            grp.check(False, "ts 侧 vitest 未运行：整体预算将尽，bun install 未跑")
            return grp
        code, timed_out, out, seconds = run_capture(
            [str(bun), "install", "--frozen-lockfile"], TS, min(240, remaining), env)
        if code != 0:
            grp.check(False, f"bun install 退出码 {code}{'（超时被杀）' if timed_out else ''}，"
                             f"用时 {seconds:.0f}s：{out[-600:]}")
            return grp
    if not _ts_deps_ready():
        grp.check(False, "bun install 之后依赖仍不齐（node_modules/.themis-installed 不在）")
        return grp
    argv = [node, os.path.join("node_modules", "vitest", "vitest.mjs"), "run", *TS_VITEST_FILES]
    cap = min(STEP_CAPS["ts vitest"], deadline - time.monotonic())
    if cap <= 30:
        grp.check(False, f"ts 侧 vitest 未运行：整体预算将尽（cap={cap:.0f}s）")
        return grp
    code, timed_out, out, seconds = run_capture(argv, TS, cap, env)
    if not grp.check(code == 0, f"vitest（{' '.join(TS_VITEST_FILES)}）退出码 {code}"
                     f"{'（超时被杀）' if timed_out else ''}，用时 {seconds:.0f}s：{out[-1200:]}"):
        return grp
    grp.check(re.search(r"Tests[^\n]*[1-9]\d*[^\n]*passed", out) is not None,
              f"ts vitest 的 Tests 行应有 passed 计数：{out[-500:]}")
    grp.check(re.search(r"(?:Tests|Test Files)[^\n]*\bfailed\b", out) is None,
              f"ts vitest 的汇总行不应有 failed：{out[-500:]}")
    pgrp = pipe.group("ts-probe")
    cap = min(STEP_CAPS["ts probe"], deadline - time.monotonic())
    if cap <= 30:
        pgrp.check(False, f"ts 行为探针未运行：整体预算将尽（cap={cap:.0f}s）")
        return pgrp
    probe_dir = TS / "packages" / "ui" / "test" / "gate-probe"
    probe_rel = f"packages/ui/test/gate-probe/probe-{uuid.uuid4().hex[:8]}-t047-hub-turns.test.ts"
    try:
        probe_dir.mkdir(parents=True, exist_ok=True)
        (TS / probe_rel).write_text(globals()["TS_PROBE_SOURCE"], encoding="utf-8", newline="\n")
        pipe.ts_probe_rel = f"ts/{probe_rel}"
        pipe.ts_probe_removed = False
    except OSError as error:
        pgrp.check(False, f"行为探针写不进 {probe_dir}：{error}")
        return pgrp
    argv = [node, os.path.join("node_modules", "vitest", "vitest.mjs"), "run", probe_rel]
    code, timed_out, out, seconds = run_capture(argv, TS, cap, env)
    if not pgrp.check(code == 0, f"ts 行为探针退出码 {code}{'（超时被杀）' if timed_out else ''}，"
                     f"用时 {seconds:.0f}s：{out[-1200:]}"):
        return pgrp
    pgrp.check(re.search(r"Tests[^\n]*[1-9]\d*[^\n]*passed", out) is not None,
              f"ts 行为探针的 Tests 行应有 passed 计数：{out[-500:]}")
    return grp


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
# 探针（黑盒 Vitest 用例，临时写进 desktop/web/gate-probe/，跑完即删；每份自带全部辅助函数）
# ---------------------------------------------------------------------------

UNIT_PROBE = r'''// T047 门禁 unit 探针：roles-logic 九个纯函数的逐字口径（时限与工具、预算 MiB、三值、标记、截断）与
// normalizeHubPost 的 turn/lastTurn 归一边界。不 mock 被测模块。
import { describe, expect, it } from 'vitest';
import {
  hubBudgetText, hubEffortDiffers, hubEffortState, hubEffortTriple, hubFallbackExcerpt,
  hubLastTurnMark, hubLastTurnText, hubMib, hubTimeoutText, normalizeHubPost,
  type HubPostBudgetInfo, type HubPostLastTurnInfo, type HubPostTurnInfo,
} from '../src/pages/readonly1/roles-logic';

const budgets = (o: Partial<HubPostBudgetInfo> = {}): HubPostBudgetInfo => ({
  max_requests: 32, max_tool_calls: 48, max_input_bytes: 2097152,
  max_response_bytes: 8388608, max_object_bytes: 8388608, ...o,
});
const turn = (o: Partial<HubPostTurnInfo> = {}): HubPostTurnInfo => ({
  timeout_seconds: 600, tools: ['read', 'grep', 'find', 'ls'], budgets: null, ...o,
});
const lt = (o: Partial<HubPostLastTurnInfo> = {}): HubPostLastTurnInfo => ({
  at: '2026-11-15T08:00:00Z', adapter: 'quizs', models: ['deepseek-flash'], profile: null,
  thinking: { requested: 'high', mapped: 'high', effective: null }, fallback: null, ...o,
});

describe('hubTimeoutText', () => {
  it('null 与 timeout_seconds 为 null 都是 —', () => {
    expect(hubTimeoutText(null)).toBe('—');
    expect(hubTimeoutText(turn({ timeout_seconds: null }))).toBe('—');
  });
  it('能被 60 整除写「N 分钟」，否则「N 秒」；工具非空时是「时限 · 工具」（合同第 4 节）', () => {
    expect(hubTimeoutText(turn())).toBe('10 分钟 · read、grep、find、ls');
    expect(hubTimeoutText(turn({ timeout_seconds: 2400 }))).toBe('40 分钟 · read、grep、find、ls');
    expect(hubTimeoutText(turn({ timeout_seconds: 45 }))).toBe('45 秒 · read、grep、find、ls');
  });
  it('工具为空数组时只给时限那一段（合同第 4 节）', () => {
    expect(hubTimeoutText(turn({ tools: [] }))).toBe('10 分钟');
    expect(hubTimeoutText(turn({ timeout_seconds: 2400, tools: [] }))).toBe('40 分钟');
    expect(hubTimeoutText(turn({ timeout_seconds: 45, tools: [] }))).toBe('45 秒');
  });
  it('工具用「、」连起来，段间是「 · 」', () => {
    expect(hubTimeoutText(turn({ timeout_seconds: 2400, tools: ['Read', 'Grep', 'Glob', 'Bash(npm view:*)'] })))
      .toBe('40 分钟 · Read、Grep、Glob、Bash(npm view:*)');
    expect(hubTimeoutText(turn({ timeout_seconds: 2400, tools: ['read', 'grep', 'find', 'ls', 'edit', 'write', 'bash'] })))
      .toBe('40 分钟 · read、grep、find、ls、edit、write、bash');
  });
});

describe('hubMib 与 hubBudgetText', () => {
  it('hubMib：1048576 → 1、2097152 → 2、8388608 → 8、null → —', () => {
    expect(hubMib(1048576)).toBe('1');
    expect(hubMib(2097152)).toBe('2');
    expect(hubMib(8388608)).toBe('8');
    expect(hubMib(null)).toBe('—');
  });
  it('budgets 为 null → —；整份文本逐字（两个 quizs 行的预算）', () => {
    expect(hubBudgetText(null)).toBe('—');
    expect(hubBudgetText(budgets())).toBe('请求 32 · 工具调用 48 · 2 / 8 / 8 MiB');
    expect(hubBudgetText(budgets({ max_requests: 128, max_tool_calls: 128 })))
      .toBe('请求 128 · 工具调用 128 · 2 / 8 / 8 MiB');
  });
  it('任一项是 null 时该项写 —', () => {
    expect(hubBudgetText(budgets({ max_requests: null, max_input_bytes: null })))
      .toBe('请求 — · 工具调用 48 · — / 8 / 8 MiB');
  });
});

describe('hubEffortTriple / hubEffortDiffers / hubEffortState', () => {
  it('null → —；三值逐字（null 写 —）', () => {
    expect(hubEffortTriple(null)).toBe('—');
    expect(hubEffortTriple(lt())).toBe('要求 high · 映射 high · 生效 —');
    expect(hubEffortTriple(lt({ thinking: { requested: 'max', mapped: null, effective: 'max' } })))
      .toBe('要求 max · 映射 — · 生效 max');
  });
  it('effective 逗号连起来的多个档位：拆开、去空白、滤空段、用「、」连', () => {
    expect(hubEffortTriple(lt({ thinking: { requested: 'high', mapped: 'high', effective: 'high,medium' } })))
      .toBe('要求 high · 映射 high · 生效 high、medium');
    expect(hubEffortTriple(lt({ thinking: { requested: 'high', mapped: null, effective: ' high , medium ,' } })))
      .toBe('要求 high · 映射 — · 生效 high、medium');
    expect(hubEffortTriple(lt({ thinking: { requested: 'high', mapped: null, effective: '' } })))
      .toBe('要求 high · 映射 — · 生效 —');
  });
  it('hubEffortDiffers：requested null → false；effective 任一段不等于 requested → true；effective 无段时看 mapped', () => {
    expect(hubEffortDiffers(lt({ thinking: { requested: null, mapped: 'max', effective: null } }))).toBe(false);
    expect(hubEffortDiffers(lt({ thinking: { requested: 'high', mapped: 'high', effective: 'high,medium' } }))).toBe(true);
    expect(hubEffortDiffers(lt({ thinking: { requested: 'high', mapped: 'high', effective: 'high' } }))).toBe(false);
    expect(hubEffortDiffers(lt({ thinking: { requested: 'high', mapped: 'max', effective: null } }))).toBe(true);
    expect(hubEffortDiffers(lt({ thinking: { requested: 'high', mapped: 'max', effective: 'high' } }))).toBe(false);
  });
  it('hubEffortState：none / unknown / same / differs', () => {
    expect(hubEffortState(null)).toBe('none');
    expect(hubEffortState(lt({ thinking: { requested: null, mapped: null, effective: null } }))).toBe('none');
    expect(hubEffortState(lt())).toBe('unknown');
    expect(hubEffortState(lt({ thinking: { requested: 'max', mapped: null, effective: 'max' } }))).toBe('same');
    expect(hubEffortState(lt({ thinking: { requested: 'high', mapped: null, effective: 'high,medium' } }))).toBe('differs');
  });
});

describe('hubLastTurnText / hubLastTurnMark', () => {
  it('文本：时刻 · 实际载体 · 模型；models 空数组写 —；null 段写 —', () => {
    expect(hubLastTurnText(null)).toBe('—');
    expect(hubLastTurnText(lt())).toBe('2026-11-15T08:00:00Z · quizs · deepseek-flash');
    expect(hubLastTurnText(lt({ models: [] }))).toBe('2026-11-15T08:00:00Z · quizs · —');
    expect(hubLastTurnText(lt({ at: null, adapter: null }))).toBe('— · — · deepseek-flash');
  });
  it('标记：fallback 非 null → 退回替补；载体与绑定不同 → 与当前绑定不同；其余 null', () => {
    expect(hubLastTurnMark(null, 'quizs')).toBe(null);
    expect(hubLastTurnMark(lt({ fallback: '读不出资格证书 C:\\x\\y.json' }), 'quizs')).toBe('退回替补');
    expect(hubLastTurnMark(lt(), 'pi')).toBe('与当前绑定不同');
    expect(hubLastTurnMark(lt(), 'quizs')).toBe(null);
    expect(hubLastTurnMark(lt({ adapter: null }), 'quizs')).toBe(null);
    expect(hubLastTurnMark(lt(), null)).toBe(null);
  });
});

describe('hubFallbackExcerpt', () => {
  it('null → 两段空串；长度 ≤ 20 原样；超长截断加 …', () => {
    expect(hubFallbackExcerpt(null)).toEqual({ shown: '', full: '' });
    expect(hubFallbackExcerpt('读不出资格证书')).toEqual({ shown: '读不出资格证书', full: '读不出资格证书' });
    const long = '读不出资格证书 C:\\Users\\example\\.agent\\mailbox\\quizs\\live\\minimax\\qualification.json';
    const cut = hubFallbackExcerpt(long);
    expect(cut.shown).toBe(long.slice(0, 20) + '…');
    expect(cut.full).toBe(long);
  });
});

describe('normalizeHubPost 的 turn/lastTurn 归一', () => {
  const base: any = {
    post: 'gate', source: 'default', allowed_adapters: ['pi'], adapter: 'pi', provider: null,
    model: null, thinking: 'high', profile: null, runtime: null, fallback: null,
  };
  it('缺 turn/last_turn 键、或不是对象 → 都按 null', () => {
    expect(normalizeHubPost(base).turn).toBe(null);
    expect(normalizeHubPost(base).lastTurn).toBe(null);
    expect(normalizeHubPost({ ...base, turn: 'x' } as any).turn).toBe(null);
    expect(normalizeHubPost({ ...base, last_turn: 7 } as any).lastTurn).toBe(null);
  });
  it('turn：budgets 缺键/不是对象 → null；tools 不是数组 → []；timeout 不是数 → null', () => {
    const p = normalizeHubPost({ ...base, turn: { timeout_seconds: 2400, tools: 'no' } } as any);
    expect(p.turn && p.turn.timeout_seconds).toBe(2400);
    expect(p.turn && p.turn.tools).toEqual([]);
    expect(p.turn && p.turn.budgets).toBe(null);
    const q = normalizeHubPost({ ...base, turn: { timeout_seconds: 'x', tools: [], budgets: 'y' } } as any);
    expect(q.turn && q.turn.timeout_seconds).toBe(null);
    expect(q.turn && q.turn.budgets).toBe(null);
  });
  it('last_turn：models 不是数组 → []；thinking 不是对象 → 三档都 null；fallback 不是字符串 → null', () => {
    const p = normalizeHubPost({
      ...base,
      last_turn: { at: '2026-11-15T08:00:00Z', adapter: 'pi', models: 'no', profile: 3, thinking: 'x', fallback: 9 },
    } as any);
    expect(p.lastTurn && p.lastTurn.models).toEqual([]);
    expect(p.lastTurn && p.lastTurn.thinking).toEqual({ requested: null, mapped: null, effective: null });
    expect(p.lastTurn && p.lastTurn.fallback).toBe(null);
    expect(p.lastTurn && p.lastTurn.profile).toBe(null);
  });
});
'''


PAGE_PROBE = r'''// T047 门禁 page 探针：桩模式挂 App——十列表头、三个新列的逐格文字、四行三值与两行 EffortPair、
// contract 行的退回替补与 title 全文、MiB 段 aria-label、新格里没有可聚焦元素；真实模式（注入假服务）
// 确认旧服务缺键时三列是 —、页面不出现桩的值。不用假计时器。每份探针自带全部辅助函数。
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import App from '../src/App';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { setConnectionState } from '../src/live/connection';
import type { Envelope } from '../src/api';

const HEADERS = ['岗位', '运行时', '模型', '思考档位', '来源', '替补', '时限与工具', '预算', '最近一回合', '操作'];
const POSTS = ['coordinator', 'planner', 'contract', 'gate', 'audit', 'exec'];
const NEW_COLS = ['时限与工具', '预算', '最近一回合'];
const CELLS: Record<string, Record<string, string>> = {
  coordinator: {
    '时限与工具': '10 分钟 · read、grep、find、ls',
    '预算': '请求 32 · 工具调用 48 · 2 / 8 / 8 MiB',
    '最近一回合': '2026-11-15T08:00:00Z · quizs · deepseek-flash',
  },
  planner: {
    '时限与工具': '40 分钟 · Read、Grep、Glob、Bash(npm view:*)',
    '预算': '—',
    '最近一回合': '2026-11-15T07:30:00Z · claude-code · claude-opus-5-5',
  },
  contract: {
    '时限与工具': '40 分钟 · read、grep、find、ls',
    '预算': '请求 128 · 工具调用 128 · 2 / 8 / 8 MiB',
    '最近一回合': '2026-11-15T09:00:00Z · pi · step-5-preview',
  },
  gate: {
    '时限与工具': '40 分钟 · read、grep、find、ls、edit、write、bash',
    '预算': '—',
    '最近一回合': '2026-11-15T09:15:00Z · pi · cc-switch-zhipu-glm/glm-5.3',
  },
  audit: { '时限与工具': '40 分钟 · read、grep、find、ls', '预算': '—', '最近一回合': '—' },
  exec: { '时限与工具': '—', '预算': '—', '最近一回合': '—' },
};
const TRIPLE: Record<string, string> = {
  coordinator: '要求 high · 映射 high · 生效 —',
  planner: '要求 max · 映射 — · 生效 max',
  contract: '要求 high · 映射 — · 生效 high',
  gate: '要求 high · 映射 — · 生效 high',
};
const TRIPLE_LEVELS: Record<string, string[]> = {
  coordinator: ['high', 'high', '—'],
  planner: ['max', '—', 'max'],
  contract: ['high', '—', 'high'],
  gate: ['high', '—', 'high'],
};
const TRIPLE_STATE: Record<string, string> = {
  coordinator: 'unknown', planner: 'same', contract: 'same', gate: 'same',
};
const PAIR: Record<string, string> = { audit: '要求 max · 生效 未知', exec: '要求 high · 生效 未知' };
const FULL_FALLBACK = '读不出资格证书 C:\\Users\\example\\.agent\\mailbox\\quizs\\live\\minimax\\qualification.json';
const MIB_ARIA = '单次输入 2 MiB、单次回应 8 MiB、单个对象 8 MiB';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
async function flush() {
  for (let i = 0; i < 12; i += 1) await act(async () => { await Promise.resolve(); });
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  await flush();
  render(<App />);
  await flush();
}
function hubSec(): any {
  return qa(document, 'section').find((s: any) => {
    const id = s.getAttribute('aria-labelledby');
    return id ? text(document.getElementById(id)) === '七端岗位' : false;
  }) || null;
}
function hubRow(post: string): any {
  const sec = hubSec();
  expect(sec, '应有「七端岗位」区块').toBeTruthy();
  const row = qa(sec, 'tbody tr').find((tr: any) => tr.getAttribute('data-post') === post);
  expect(row, '应有 data-post=' + post + ' 的行').toBeTruthy();
  return row;
}
function cell(row: any, header: string): any {
  const hit = qa(row, 'td')[HEADERS.indexOf(header)];
  expect(hit, '应有「' + header + '」那一格').toBeTruthy();
  return hit;
}

beforeEach(() => {
  setLiveClientForTests(undefined);
  setConnectionState('connected');
  window.location.hash = '';
});
afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('桩模式：十列与三个新列的逐格文字（D07、D08）', () => {
  it('列头恰是十列（三个新列在「替补」与「操作」之间）；六行×三列的逐格文字照合同', async () => {
    await mountApp('#/roles');
    const table = hubSec().querySelector('table[aria-label="七端岗位"]');
    expect(qa(table, 'thead th').map(text)).toEqual(HEADERS);
    for (const post of POSTS) {
      const row = hubRow(post);
      for (const col of NEW_COLS) {
        if (post === 'contract' && col === '最近一回合') {
          // 合同第 5 节：这一格在基础文字后面还放「退回替补」Tag 与截断的原因文字，只钉开头的基础文字
          expect(text(cell(row, col)), post + ' 的「' + col + '」开头').toContain(CELLS[post][col]);
        } else {
          expect(text(cell(row, col)), post + ' 的「' + col + '」').toBe(CELLS[post][col]);
        }
      }
    }
  });
  it('思考档位：有最近一回合的四行是三值格（label/level 各三段，段间「 · 」），audit/exec 照旧 EffortPair', async () => {
    await mountApp('#/roles');
    for (const post of ['coordinator', 'planner', 'contract', 'gate']) {
      const e = cell(hubRow(post), '思考档位').querySelector('.tt-effort');
      expect(e, post + ' 应有三值格').toBeTruthy();
      expect(text(e), post + ' 三值文字').toBe(TRIPLE[post]);
      expect(e.getAttribute('data-state'), post + ' data-state').toBe(TRIPLE_STATE[post]);
      expect(qa(e, '.tt-effort__label').map(text), post + ' 三个 label').toEqual(['要求', '映射', '生效']);
      expect(qa(e, '.tt-effort__level').map(text), post + ' 三个 level').toEqual(TRIPLE_LEVELS[post]);
    }
    for (const post of ['audit', 'exec']) {
      const e = cell(hubRow(post), '思考档位').querySelector('.tt-effort');
      expect(e, post + ' 仍经 EffortPair').toBeTruthy();
      expect(e.getAttribute('data-state'), post + ' data-state').toBe('unknown');
      expect(text(e), post + ' EffortPair 文字').toBe(PAIR[post]);
    }
  });
  it('预算格的 MiB 段单独在一个 span 里，aria-label 是「单次输入 2 MiB、单次回应 8 MiB、单个对象 8 MiB」，文字照旧', async () => {
    await mountApp('#/roles');
    for (const post of ['coordinator', 'contract']) {
      const span = qa(cell(hubRow(post), '预算'), 'span[aria-label]')[0];
      expect(span, post + ' 的 MiB 段应有 span[aria-label]').toBeTruthy();
      expect(span.getAttribute('aria-label'), post + ' aria-label').toBe(MIB_ARIA);
      expect(text(span), post + ' MiB 段文字').toBe('2 / 8 / 8 MiB');
    }
  });
  it('contract 行最近一回合格：tt-tag--warning 的「退回替补」，后面跟截断的原因文字且 title 给全文', async () => {
    await mountApp('#/roles');
    const c = cell(hubRow('contract'), '最近一回合');
    const tag = c.querySelector('.tt-tag--warning');
    expect(tag, '应有 tt-tag--warning').toBeTruthy();
    expect(text(tag)).toBe('退回替补');
    const titled = qa(c, '[title]').find((el: any) => (el.getAttribute('title') || '').indexOf('读不出资格证书') === 0);
    expect(titled, '原因文字那一段应有 title').toBeTruthy();
    expect(titled.getAttribute('title'), 'title 给全文（本机路径原样）').toBe(FULL_FALLBACK);
    expect(text(titled), '截断显示：前 20 个字加 …').toBe(FULL_FALLBACK.slice(0, 20) + '…');
  });
  it('没有 fallback 的行：最近一回合格没有 Tag；三个新格里没有可聚焦元素', async () => {
    await mountApp('#/roles');
    for (const post of POSTS) {
      const row = hubRow(post);
      for (const col of NEW_COLS) {
        expect(qa(cell(row, col), 'button, a, [tabindex]').length, post + ' ' + col + ' 不该有可聚焦元素').toBe(0);
      }
      if (post !== 'contract') {
        expect(qa(cell(row, '最近一回合'), '.tt-tag').length, post + ' 没有 Tag').toBe(0);
      }
    }
  });
});

// ---- 真实模式（注入假服务）----

function okEnv<T>(data: T, command: string[] = []): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}
const ROLES = { active_preset: 'default', roles: [
  { role: 'contract', explicit: false, binding: { mode: 'manual' }, differs_from_preset: false },
  { role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' }, differs_from_preset: false, profile: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', thinking: 'high', connected: true, effort_effective: 'high' },
] };
const PRESETS = { active_preset: 'default', presets: [
  { name: 'default', description: '日常', roles: ['execution'], active: true },
] };
const REAL_PROFILES = { profiles: [
  { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview', options: { thinking: 'high' }, credential_env: [] },
] };
const THINK: Record<string, string> = {
  coordinator: 'high', planner: 'max', contract: 'high', gate: 'high', audit: 'max', exec: 'high',
};
const REAL_ROWS: any[] = POSTS.map((post) => ({
  post, source: 'default', allowed_adapters: ['pi'], adapter: 'pi', provider: null,
  model: null, thinking: THINK[post], profile: null, runtime: null, fallback: null,
}));
const fake: LiveClient = {
  get<T>(path: string): Promise<Envelope<T>> {
    if (path === '/api/v1/hub/roles') return Promise.resolve(okEnv({ posts: REAL_ROWS }, ['config', 'hub', 'show', '--json']) as unknown as Envelope<T>);
    if (path === '/api/v1/roles') return Promise.resolve(okEnv(ROLES) as unknown as Envelope<T>);
    if (path === '/api/v1/profiles') return Promise.resolve(okEnv(REAL_PROFILES) as unknown as Envelope<T>);
    if (path === '/api/v1/presets') return Promise.resolve(okEnv(PRESETS) as unknown as Envelope<T>);
    if (path === '/api/v1/meta') return Promise.resolve(okEnv({ version: 'pi_dispatch 1.0.0', repo_name: 'r' }) as unknown as Envelope<T>);
    return Promise.resolve(okEnv(null) as unknown as Envelope<T>);
  },
  post<T>(): Promise<{ status: number; body: Envelope<T> }> {
    return Promise.resolve({ status: 200, body: okEnv(null) as unknown as Envelope<T> });
  },
  getRaw<T>(): Promise<{ status: number; body: T }> {
    return Promise.resolve({ status: 404, body: null as unknown as T });
  },
};

describe('真实模式：旧服务缺 turn/last_turn（D06 的第 7 组、边界输入）', () => {
  it('三个新列都是 —、思考档位仍是 EffortPair 的 unknown、页面不出现桩的值', async () => {
    setLiveClientForTests(fake);
    await mountApp('#/roles');
    for (const post of POSTS) {
      const row = hubRow(post);
      for (const col of NEW_COLS) {
        expect(text(cell(row, col)), post + ' ' + col).toBe('—');
      }
      const e = cell(row, '思考档位').querySelector('.tt-effort');
      expect(e.getAttribute('data-state'), post + ' data-state').toBe('unknown');
      expect(text(e), post + ' EffortPair 文字').toBe('要求 ' + THINK[post] + ' · 生效 未知');
    }
    const page = text(document.body);
    expect(page).not.toContain('10 分钟');
    expect(page).not.toContain('请求 32');
    expect(page).not.toContain('2026-11-15T08:00:00Z');
  });
});
'''


TS_PROBE_SRC = r'''// T047 门禁 ts 行为探针（临时写出，跑完即删）：四个新校验器的合格/不合格值 + 整份 hub 行过 redactJson
// （放行、越界遮、凭据形状遮、对象层不登记时缺省口径照走）。内核 stdout 的 JSON 先过 parseJsonData。
import { describe, expect, it } from "vitest";
import { redactJson } from "@themis/base/secrets";
import { parseJsonData } from "../../src/kernelenvelope.ts";
import {
  HUB_ROLES_ALLOW, allowEffortLevels, allowIsoSecondUtc, allowNonNegativeInt, allowToolName,
} from "../../src/redaction.ts";

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

describe("四个新校验器", () => {
  it("allowNonNegativeInt：null/0/600/bigint 放行；负数、小数、字符串、布尔不行", () => {
    expect(allowNonNegativeInt(null)).toBe(true);
    expect(allowNonNegativeInt(0)).toBe(true);
    expect(allowNonNegativeInt(600)).toBe(true);
    expect(allowNonNegativeInt(8388608n)).toBe(true);
    expect(allowNonNegativeInt(-1)).toBe(false);
    expect(allowNonNegativeInt(1.5)).toBe(false);
    expect(allowNonNegativeInt("600")).toBe(false);
    expect(allowNonNegativeInt(true)).toBe(false);
  });
  it("allowToolName：read…bash、Read/Grep/Glob、Bash(npm view:*) 放行；像凭据的、空串、非字符串不行", () => {
    for (const name of ["read", "grep", "find", "ls", "edit", "write", "bash",
                       "Read", "Grep", "Glob", "Bash(npm view:*)"]) {
      expect(allowToolName(name), name).toBe(true);
    }
    expect(allowToolName("sk-abcdefghijklmnopqrstuvwxyz0123456789")).toBe(false);
    expect(allowToolName("")).toBe(false);
    expect(allowToolName(null)).toBe(false);
    expect(allowToolName(123 as never)).toBe(false);
  });
  it("allowIsoSecondUtc：秒级 Z 与 +00:00 放行；带毫秒、无时区、非字符串不行", () => {
    expect(allowIsoSecondUtc(null)).toBe(true);
    expect(allowIsoSecondUtc("2026-11-15T08:00:00Z")).toBe(true);
    expect(allowIsoSecondUtc("2026-11-15T08:00:00+00:00")).toBe(true);
    expect(allowIsoSecondUtc("2026-11-15T08:00:00.000Z")).toBe(false);
    expect(allowIsoSecondUtc("2026-11-15T08:00:00")).toBe(false);
    expect(allowIsoSecondUtc("2026-11-15 08:00:00Z")).toBe(false);
  });
  it("allowEffortLevels：high 与 high,medium（含空格）放行；high,bogus、空段、空串不行", () => {
    expect(allowEffortLevels(null)).toBe(true);
    expect(allowEffortLevels("high")).toBe(true);
    expect(allowEffortLevels("high,medium")).toBe(true);
    expect(allowEffortLevels(" high , medium ")).toBe(true);
    expect(allowEffortLevels("high,bogus")).toBe(false);
    expect(allowEffortLevels("high,")).toBe(false);
    expect(allowEffortLevels("")).toBe(false);
  });
});

describe("HUB_ROLES_ALLOW 对整份 hub 行", () => {
  it("合格值原样（含 Bash(npm view:*)、多档位、带本机路径的 fallback）；不合格值遮成 <redacted>", () => {
    const data = redacted(JSON.stringify({
      posts: [
        { post: "coordinator", source: "default", allowed_adapters: ["quizs", "pi"], adapter: "quizs",
          provider: "deepseek", model: "deepseek-flash", thinking: "high", profile: null, runtime: null,
          fallback: null,
          turn: { timeout_seconds: 600, tools: ["read", "grep", "find", "ls", "Bash(npm view:*)"],
                 budgets: { max_requests: 32, max_tool_calls: 48, max_input_bytes: 2097152,
                            max_response_bytes: 8388608, max_object_bytes: 8388608 } },
          last_turn: { at: "2026-11-15T08:00:00Z", adapter: "quizs", models: ["deepseek-flash"], profile: null,
                       thinking: { requested: "high", mapped: "high", effective: "high,medium" },
                       fallback: "读不出资格证书 C:\\Users\\e\\q.json" } },
        { post: "planner", source: "default", allowed_adapters: ["claude-code"], adapter: null, provider: null,
          model: null, thinking: null, profile: null, runtime: null, fallback: null,
          turn: { timeout_seconds: -1, tools: ["sk-abcdefghijklmnopqrstuvwxyz0123456789"],
                 budgets: { max_requests: 1.5, max_tool_calls: 48, max_input_bytes: 2097152,
                            max_response_bytes: 8388608, max_object_bytes: 8388608 } },
          last_turn: { at: "2026-11-15T08:00:00.000Z", adapter: "turbo", models: ["deepseek-flash"],
                       profile: "p-1", thinking: { requested: "high", mapped: null, effective: "high,bogus" },
                       fallback: null } },
      ],
    }), HUB_ROLES_ALLOW);
    const one = at(data, "posts", 0) as Map<string, unknown>;
    const turn = at(one, "turn") as Map<string, unknown>;
    expect(Number(at(turn, "timeout_seconds"))).toBe(600);
    expect(at(turn, "tools", 4), "带括号参数的工具名放行").toBe("Bash(npm view:*)");
    const budgets = at(turn, "budgets") as Map<string, unknown>;
    expect(Number(at(budgets, "max_requests"))).toBe(32);
    expect(Number(at(budgets, "max_object_bytes"))).toBe(8388608);
    const lt = at(one, "last_turn") as Map<string, unknown>;
    expect(at(lt, "at")).toBe("2026-11-15T08:00:00Z");
    expect(at(lt, "thinking", "effective"), "逗号连起来的多个档位不遮").toBe("high,medium");
    expect(at(lt, "fallback"), "带本机路径的原因原文不遮").toBe("读不出资格证书 C:\\Users\\e\\q.json");
    const two = at(data, "posts", 1) as Map<string, unknown>;
    const t2 = at(two, "turn") as Map<string, unknown>;
    expect(at(t2, "timeout_seconds")).toBe("<redacted>");
    expect(at(t2, "tools", 0), "像凭据的工具名遮").toBe("<redacted>");
    expect(at(t2, "budgets", "max_requests")).toBe("<redacted>");
    const l2 = at(two, "last_turn") as Map<string, unknown>;
    expect(at(l2, "at"), "带毫秒的时刻遮").toBe("<redacted>");
    expect(at(l2, "adapter"), "枚举外的载体遮").toBe("<redacted>");
    expect(at(l2, "thinking", "requested")).toBe("high");
    expect(at(l2, "thinking", "effective"), "有非法档位的串遮").toBe("<redacted>");
  });
});
'''


# ---------------------------------------------------------------------------
# P 系列：流水线断言；D 系列：探针断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01：npm 依赖（已在就跳过）、npm test 全绿（含 page-hub 两处改过的断言、新的
    roles-hub-turns.test.ts 与 cleanup1-css 认得到的新样式文件）；依赖文件一个字节没动；
    gate-probe/ 没有留下。"""
    assert any(pipeline.steps.get(k) is not None and pipeline.steps[k].code == 0
               for k in ("npm ci", "npm ci --offline")), \
        f"npm ci（含 --offline 兑底）未成功：{pipeline.stopped_reason or pipeline.reason}"
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
    """P2（守卫）：流水线与探针前后 git status 相同；两个探针目录都没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"
    assert not (WEB / "gate-probe").exists(), "desktop/web/gate-probe 应已删除"
    assert pipeline.ts_probe_removed, "ts 行为探针应已删除"


def test_p3_ts_vitest_and_probe(pipeline):
    """P3 / V05、D02、D03：ts 侧 vitest——redaction.test.ts 与 hub-routes-real.test.ts（执行端追加的用例
    都在里面）全绿；ts 行为探针（四个校验器的合格/不合格值、整份 hub 行过 redactJson）通过且删干净。"""
    assert pipeline.ran, pipeline.reason
    for name in ("ts-vitest", "ts-probe"):
        grp = pipeline.groups.get(name)
        if grp is None:
            assert not pipeline.stopped_reason, f"{name} 未运行：{pipeline.stopped_reason}"
        assert grp is not None, f"{name} 未运行"
        fail_if(grp.problems, f"{name}（ts 侧 vitest）")
    assert not (TS / "packages" / "ui" / "test" / "gate-probe").exists(), "ts 行为探针的目录应已删除"


def test_d06_probe_unit(pipeline):
    """unit 探针 / D06：九个纯函数的逐字口径（时限与工具、预算 MiB、三值、标记、截断）与
    normalizeHubPost 的 turn/lastTurn 归一边界。"""
    assert_probe_ok(pipeline, "unit")


def test_d07_d08_d10_d11_probe_page(pipeline):
    """page 探针 / D07、D08、D10、D11：十列表头与三个新列的逐格文字、四行三值与两行 EffortPair、
    contract 行的退回替补 Tag 与 title 全文、MiB 段 aria-label、新格里没有可聚焦元素；
    真实模式（注入假服务）旧服务缺键时三列是「—」、页面不出现桩的值。"""
    assert_probe_ok(pipeline, "page")
