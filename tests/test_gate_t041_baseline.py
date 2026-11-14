"""T041 战前门禁：桌面端前端第 7 片——CLI 运行时页手动登记运行时（模型配置 M4 之二）的黑盒基准测试
（合同 t041-desktop-web-runtime-add.v2，基线 f4012ee3b7548bfaf3f0fbe664aa07a71a3b09cc）。

被测对象是 ``desktop/web/`` 与服务侧四处：

- ``src/api.ts``：``WriteAction`` 加 ``'runtime.add'``，新增同步 ``export function addRuntime(args, confirmation)``
  （真实模式 POST ``/api/v1/runtimes/<encodeURIComponent(runtime)>/add``、正文 ``{...writeArgs({adapter, command}),
  confirmation}``、时限 90 秒；桩模式转 ``mockAddRuntime``）。
- ``src/mock/writes.ts``：``baseArgv`` / ``NEW_ACTIONS`` / ``previewData`` 认 ``runtime.add``（命令行与服务
  ``buildWriteArgv`` 逐字一致），新增 ``mockAddRuntime`` 与情景 ``preview-registered``（预览 200、ok 假、
  退出码 1、一行 ``ERROR: runtime <id> 已登记为 <adapter>；改 adapter 要加 --force``、不发确认号）。
- ``src/writes/useWriteFlow.ts``：文字表（确认框标题「登记运行时 X？」、变化区摘要「已登记表里加上 X
  （适配器 A）」（带命令接「；命令写进本机文件」）、成功轻提示「已登记运行时 X」）、快照读
  （getRuntimes + runtimeRemoveSnapshot）与执行分派（addRuntime）加 runtime.add 分支。
- 新文件 ``src/writes/RuntimeForm.tsx``（可在 ``runtimeRules.ts`` 放命令解析）：导出 ``AddRuntimeAction({reload})``
  ——按钮 primary/PlusIcon/「手动登记…」、离线也可点；对话框标题「登记运行时」；三个字段（ID 等宽复用
  ``profileRules.validId``、适配器下拉五值含 quizs 缺省 pi、命令等宽、help「JSON 字符串数组，第一项写命令的
  绝对路径」）；底部实时预览（300ms 防抖、命令、警告与内核报错原文）；[确认…] 门控照 ProfileForm；整个界面
  没有 force。``src/pages/RuntimesPage.tsx`` 只放按钮（AddRuntimeAction），空态说明改成合同第八步的原文。
- 服务侧四处（站主拍板的方案乙）：``writeroutes.ts`` 的 ADAPTERS 扩到五值（含 quizs）并改注释、
  ``write-argv.test.ts`` 加 quizs 通过用例、``README.md`` 补「adapter 取五值」一句、``redaction.ts:14`` 注释
  去掉「四值」的说法（枚举不动）。

基线（f4012ee）上 WriteAction 没有 ``'runtime.add'``、服务只认四个适配器、RuntimeForm 与两个新测试不存在、
空态说明还是旧原文，所以本文件的失败落在「记号不在」「文件不在」「探针断言红」上，不是导入、收集或语法
错误：模块级只导入标准库，所有仓库文件的读取都发生在用例函数里；流水线（npm、Vitest、探针）放在
``pipeline`` 会话级夹具里（全量 pytest 默认跳过，点名运行本文件才跑；候选里 api.ts 还没有 addRuntime 时，
夹具不调 npm——基线上没有新测试可跑，也避免联网装依赖，照 T024/T040 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：api.ts 的 addRuntime 与 WriteAction（S01）；
  mock 的 runtime.add 与 preview-registered（S02）；useWriteFlow 的分支（S03）；RuntimeForm 的导出、
  字段接线与「没有 force」（S04）；RuntimesPage 入口与空态说明、入口文件不出现文字表（S05）；
  文字表片段只出现在 src/writes（S06）；服务侧四处（S07）；执行端两个测试文件与最小记号（S08）；
  共享面不动——mock JSON 仍 14 份、顶层页面仍 9 个、components/index 不引用 writes、snapshots.ts 的
  runtimeRemoveSnapshot 原样复用（S09）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、npm test
  （全绿，含执行端两个新测试与照新行为改过的 page-app）、npm run build；探针逐份写成
  ``gate-probe/probe-<uid>-t041-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，``finally``
  里删除。探针用 ``vi.mock('../src/api')`` 的替身（默认转调真实现、可注入任意信封）挂载整个 App，不 mock
  被测组件；每份自带全部辅助函数，不跨文件共享作用域。
  - form：页头次序与样式（[手动登记…] 可点、PlusIcon、primary；[扫描 PATH] 仍禁用）、空态与 offline 也
    能点开、适配器五值缺省 pi、ID 与命令的逐字校验与门控（不调 preview）、300ms 防抖与改值只发最新一次、
    服务 400 原文、``?write=preview-registered`` 的内核原文（[确认…] 不可点、没有 force 控件）、全流程
    （确认框标题与变化区摘要、addRuntime 的参数与确认号、成功轻提示「已登记运行时 X」、成功后表单清空）。
  - api：真实模式的路径/正文/时限（命令留空与空数组都不带 command 键）；桩模式预览命令照服务
    buildWriteArgv 逐字（quizs、``--command=JSON.stringify`` 无空格）、resources 不带命令 [config]、带命令
    [config,local]；执行命令带 --expect-state、确认号或参数不符 409；preview-registered 的原文与退出码。

门禁做不到、留给人的项：真 Electron 窗口里的写操作冒烟（站主的验收：登记一个 quizs 与一个 pi 运行时）、
视觉与读屏核对。

门禁端按最合理读法定下的地方（交付信「下游须知」里也写）：

- 「界面没有 force」在 DOM 上查（按钮/选项/aria-label/整页文本），但 ``?write=preview-registered`` 的
  用例除外——内核原文本身含「--force」，合同要求逐字显示；静态查 RuntimeForm/runtimeRules 的代码
  （去注释）里没有 force。
- D01 的命令口径（v2 合同下游须知第 4 条）：界面显示的「将运行的命令」不含 ``--dry-run``、``--json``
  （form 探针两条 not.toContain 钓住）；服务侧预览请求的命令带这两个开关（api 探针的桩模式预览断言
  钉的就是带开关的那条 argv，与服务 buildWriteArgv 逐字一致）。
- ID 校验的逐字提示用非空的非法值断言（照 ProfileForm「非空才显示」的惯例）；空 ID 只断言不调 preview、
  [确认…] 不可点——合同对「空」是否显示提示文字的写法留了空间，门禁不钉死。
- 适配器下拉的选项值按合同枚举的次序断言（pi、claude-code、codex、opencode、quizs，缺省 pi）。
- preview-registered 的原文里「已登记为」哪个适配器由桩自选，门禁用正则断言前后缀与 id 部分。
- ts 侧的 V03（write-argv.test）不进门禁流水线：ts 用 bun、worktree 不提交 node_modules，基线上依赖未装
  （v2 合同 Repository facts），执行端靠 Setup S02 装上后自己跑 V03；门禁由 S07 静态钉住服务侧四处。
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
WEB_REL = "desktop/web"
WEB = REPO_ROOT / "desktop" / "web"
SRC_REL = f"{WEB_REL}/src"
TESTS_REL = f"{WEB_REL}/tests"
WRITES_REL = f"{SRC_REL}/writes"
MOCK_REL = f"{SRC_REL}/mock"

API_REL = f"{SRC_REL}/api.ts"
MODE_REL = f"{SRC_REL}/live/mode.ts"
MOCKWRITES_REL = f"{MOCK_REL}/writes.ts"
FLOW_REL = f"{WRITES_REL}/useWriteFlow.ts"
PROFILEFORM_REL = f"{WRITES_REL}/ProfileForm.tsx"
RUNTIMEFORM_REL = f"{WRITES_REL}/RuntimeForm.tsx"
RUNTIMERULES_REL = f"{WRITES_REL}/runtimeRules.ts"
RUNTIMESPAGE_REL = f"{SRC_REL}/pages/RuntimesPage.tsx"
SNAPSHOTS_REL = f"{WRITES_REL}/snapshots.ts"
INDEX_TS_REL = f"{SRC_REL}/components/index.ts"
WRITEROUTES_REL = "ts/packages/ui/src/writeroutes.ts"
WRITE_ARGV_TEST_REL = "ts/packages/ui/test/write-argv.test.ts"
UI_README_REL = "ts/packages/ui/README.md"
REDACTION_REL = "ts/packages/ui/src/redaction.ts"

EXECUTOR_TESTS = ("writes-runtime-form.test.tsx", "writes-runtime-api.test.ts")

# WriteAction 既有的 11 个成员（合同 Repository facts）：一个不许少
OLD_ACTIONS = (
    "preset.use", "plugin.enable", "plugin.disable", "preset.remove", "profile.remove", "runtime.remove",
    "config.rollback", "profile.add", "profile.edit", "hub.set", "hub.unset",
)

# 合同 Behavior contract 逐字要求的文字（S06 在 src/writes 的文件池里按包含查）
WRITES_TEXTS = (
    "登记运行时",
    "已登记运行时",
    "已登记表里加上",
    "（适配器",
    "；命令写进本机文件",
    "只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符",
    '命令要写成 JSON 字符串数组，例如 ["C:/tools/pi.exe"]；每项非空、不超过 1024 个字符、不含控制字符',
    "JSON 字符串数组，第一项写命令的绝对路径",
    "quizs",
)

# 入口文件（RuntimesPage.tsx）不许出现的文字：确认框标题模板、轻提示、摘要、内核原文与字段提示（S05）
BAD_ENTRY_TEXTS = (
    "已登记运行时", "已登记表里加上", "；命令写进本机文件", "已登记为",
    "ERROR: runtime", "改 adapter 要加",
    "只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符",
    "命令要写成 JSON 字符串数组",
    "JSON 字符串数组，第一项写命令的绝对路径",
    "登记运行时 ${",
)

# 合同第八步：空态说明的原文（标题「还没有登记的 runtime」不动，说明改成这一句）
EMPTY_DESC = "用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）"

# 服务侧四处（站主拍板的方案乙）
ADAPTER_FIVE = ("pi", "claude-code", "codex", "opencode", "quizs")
README_ADAPTER_SENTENCE = "adapter 取五值：pi、claude-code、codex、opencode、quizs"

# 执行端两个测试文件里应出现的记号（合同第 10 步的最小覆盖证据）
EXECUTOR_TEST_TOKENS = {
    "writes-runtime-form.test.tsx": ("手动登记", "登记运行时", "已登记运行时", "已登记为", "quizs"),
    "writes-runtime-api.test.ts": ("addRuntime", "setLiveClientForTests", "preview-registered", "/api/v1/runtimes", "409"),
}

# 基线名单：src/mock 恰 14 份 JSON、src/pages 顶层恰 9 个 *Page.tsx（不新增 JSON、不新增页面文件）
BASELINE_MOCK_JSON_COUNT = 14
BASELINE_PAGE_COUNT = 9

# G01 的超时是 600s：夹具总预算压在 560s 以内（照 T024 门禁），用完就停下并在断言里写明，不等调度器来杀。
PIPELINE_BUDGET = 560
STEP_CAPS = {
    "npm ci": 240,
    "npm ci --offline": 240,
    "npm test": 240,
    "npm run build": 180,
    "probe": 120,
}


# ---------------------------------------------------------------------------
# 通用小工具（与 T024/T040 门禁同一口径）
# ---------------------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def read_rel(rel):
    return _read(REPO_ROOT / rel)


def need_file(rel):
    """断言仓库里的文件存在，返回路径。基线上到这里就以断言失败。"""
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return path


def file_digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def git(*args, check=False):
    proc = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, timeout=120)
    if check:
        assert proc.returncode == 0, f"git {' '.join(args)} 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return proc


def git_status_set():
    proc = git("status", "--porcelain=v1", "--untracked-files=all", "-z", check=True)
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


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


# TS 注释剥离（与 T010/T034/T036/T037/T040 的同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def writes_texts():
    """src/writes/ 下所有源文件的原文池（S6 的按包含查）。"""
    root = REPO_ROOT / WRITES_REL
    if not root.is_dir():
        return {}
    return {str(p.relative_to(REPO_ROOT)): _read(p) for p in sorted(root.glob("*.ts*")) if p.is_file()}


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:40])


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_api_addruntime():
    """S01 / D01、兼容性：api.ts 的 WriteAction 加 'runtime.add'（既有 11 个成员一个不丢）；
    新增同步 export function addRuntime(args: {runtime; adapter; command?}, confirmation)——
    真实模式 POST /api/v1/runtimes/<encodeURIComponent(runtime)>/add，桩模式转 mockAddRuntime。"""
    need_file(API_REL)
    text = read_rel(API_REL)
    assert "'runtime.add'" in text, "WriteAction 应含成员 'runtime.add'"
    for member in OLD_ACTIONS:
        assert f"'{member}'" in text, f"WriteAction 的既有成员 '{member}' 应保留（合同：导出集合一个不丢）"
    assert re.search(r"export function addRuntime\(", text), \
        "api.ts 应导出同步 export function addRuntime（T037 S03：写侧函数是同步 export function）"
    assert not re.search(r"export async function addRuntime\(", text), "addRuntime 不应是 async 函数"
    assert re.search(
        r"export function addRuntime\(\s*args:\s*\{[\s\S]*?runtime:\s*string;[\s\S]*?adapter:\s*string;"
        r"[\s\S]*?command\?:\s*string\[\][\s\S]*?\}\s*,\s*confirmation:\s*string\s*\)",
        text), "addRuntime 的签名应是 (args: {runtime: string; adapter: string; command?: string[]}, confirmation: string)"
    assert re.search(r"/api/v1/runtimes/\$\{encodeURIComponent\(args\.runtime\)\}/add", text), \
        "真实模式应 POST /api/v1/runtimes/${encodeURIComponent(args.runtime)}/add（合同第 3 步）"
    assert "mockAddRuntime" in text, "桩模式应转 mockAddRuntime（合同第 3 步）"
    for name in ("preview", "getOperation", "removeRuntime", "addProfile", "setHubRole", "getRuntimes"):
        assert re.search(rf"export function {name}\(", text), f"api.ts 既有导出 {name} 应保留"


def test_s02_mock_runtime_add_and_scenario():
    """S02 / D01、桩模式：mock/writes.ts 认 runtime.add（baseArgv 与 NEW_ACTIONS）、导出 mockAddRuntime、
    新增情景 preview-registered（内核原文的两个片段），22 个旧情景一个不丢。"""
    need_file(MOCKWRITES_REL)
    read = read_rel(MOCKWRITES_REL)
    union = re.search(r"export type WriteScenario =([\s\S]*?);", read)
    assert union, "mock/writes.ts 应保留 WriteScenario 类型"
    members = re.findall(r"'([a-z0-9-]+)'", union.group(1))
    assert "preview-registered" in members, "WriteScenario 应含 'preview-registered'（已登记为别的适配器的桩情景）"
    assert len(members) >= 23, f"WriteScenario 从 22 个旧值加 preview-registered 应至少 23 个，现在 {len(members)}"
    for frag in ("reread-fail", "reread-fail-exit1", "preview-warn", "preview-invalid", "in-use", "drop-hang"):
        assert frag in members, f"旧情景 '{frag}' 应保留（夹具模式不变）"
    assert read.count("'runtime.add'") >= 2, "baseArgv 与 NEW_ACTIONS 都应认得 'runtime.add'"
    assert re.search(r"export function mockAddRuntime\(", read), "mock/writes.ts 应导出 mockAddRuntime"
    for frag in ("已登记为", "；改 adapter 要加 --force"):
        assert frag in read, f"preview-registered 的内核原文应含片段「{frag}」（合同逐字）"


def test_s03_usewriteflow_runtime_add_branches():
    """S03 / D01：useWriteFlow 认得 runtime.add——文字表、快照读（getRuntimes + runtimeRemoveSnapshot）与
    执行分派（addRuntime）都要有显式分支（缺了会落到 getPlugins / 回滚文字 / setPluginEnabled 的兜底）。"""
    need_file(FLOW_REL)
    text = read_rel(FLOW_REL)
    assert text.count("'runtime.add'") >= 3, \
        "useWriteFlow 应至少在三处分支认得 'runtime.add'（titleOf/successTextOf/changeSummaryOf、readSnapshot、confirm）"
    assert re.search(r"\baddRuntime\b", text), "useWriteFlow 的 confirm 应分派到写函数 addRuntime"
    assert "runtimeRemoveSnapshot" in text, "runtime.add 的快照应沿用 runtimeRemoveSnapshot（合同第 5 步，不改 snapshots.ts）"


def test_s04_runtimeform_export_and_no_force():
    """S04 / D01、D03：RuntimeForm.tsx 导出 AddRuntimeAction（按钮文字、PlusIcon、Select 下拉、validId 复用、
    命令校验的 1024 上限）；代码（去注释）里没有 force——界面不提供 force（注释里解释「为什么不提供」不算）。"""
    need_file(RUNTIMEFORM_REL)
    text = read_rel(RUNTIMEFORM_REL)
    assert re.search(r"export function AddRuntimeAction\b", text), \
        "RuntimeForm.tsx 应导出 AddRuntimeAction（合同第 6 步）"
    assert "手动登记…" in text, "按钮文字「手动登记…」应写在 RuntimeForm（入口文件只放组件）"
    assert "PlusIcon" in text, "按钮应带 PlusIcon"
    assert "Select" in text, "适配器应用 Select 下拉（合同第 6 步）"
    assert "validId" in text and "profileRules" in text, "ID 校验应复用 profileRules 的 validId（合同第 6 步）"
    code = strip_ts_comments(text)
    assert not re.search(r"force", code, re.I), "RuntimeForm 的代码里不该出现 force（界面不提供 force）"
    rules = REPO_ROOT / RUNTIMERULES_REL
    if rules.is_file():
        rcode = strip_ts_comments(read_rel(RUNTIMERULES_REL))
        assert not re.search(r"force", rcode, re.I), "runtimeRules 的代码里不该出现 force"
        assert "1024" in rcode, "runtimeRules.ts 应有命令每项 1024 码点的上限（合同第 7 步）"
    else:
        assert "1024" in code, "命令校验（每项 1024 码点）应写在 RuntimeForm.tsx 或 runtimeRules.ts（合同第 7 步）"


def test_s05_runtimes_page_entry():
    """S05 / D01、D07：RuntimesPage 只放按钮——AddRuntimeAction 接在页头（[扫描 PATH] 仍是 DisabledAction）；
    空态说明改成合同第八步的原文；确认框标题、轻提示、内核原文与字段提示一个都不出现在入口文件
    （T013 D02 的「登记 runtime」也不许出现）。"""
    need_file(RUNTIMESPAGE_REL)
    text = read_rel(RUNTIMESPAGE_REL)
    assert "AddRuntimeAction" in text, "页头 [手动登记…] 应由 src/writes 的 AddRuntimeAction 渲染（页面只放按钮）"
    assert '<DisabledAction label="扫描 PATH"' in text, "[扫描 PATH] 应照旧是 DisabledAction（次序不变）"
    assert EMPTY_DESC in text, f"空态说明应改成合同第八步的原文「{EMPTY_DESC}」"
    assert "还没有登记的 runtime" in text, "空态标题「还没有登记的 runtime」不动"
    problems = [f"RuntimesPage.tsx 出现「{frag}」（文字表与字段提示只能写在 src/writes/）"
                for frag in BAD_ENTRY_TEXTS if frag in text]
    if "登记 runtime" in text:
        problems.append("RuntimesPage.tsx 出现「登记 runtime」（T013 D02：动作说明只在 components/actionTitle.ts）")
    fail_if(problems, "入口文件里出现了不该出现的文字")


def test_s06_writes_texts_live_in_writes():
    """S06 / D01–D03：确认框标题、变化区摘要、成功轻提示与表单逐字提示都在 src/writes/（按模板原文片段找）。
    动作说明「登记 runtime」不得出现：基线 ProfileForm.tsx 的字段提示「先登记 runtime」（T024 的逐字表要求
    保留、本片禁改该文件）含这个子串，只豁免这一个文件里的这一基线短语；其余任何写入文件——含本片新增或
    改动的 RuntimeForm、runtimeRules、useWriteFlow——出现动作说明仍红。"""
    pool = writes_texts()
    assert pool, "src/writes/ 应存在且有自己的文件"
    missing = [t for t in WRITES_TEXTS if not any(t in text for text in pool.values())]
    assert not missing, f"src/writes/ 里应出现文字表片段 {missing}（合同 Behavior contract 的逐字表）"
    # 基线 ProfileForm.tsx:183 的字段提示「先登记 runtime」是 T024 逐字表要求的基线文案，不算本片越界；
    # 除它之外任何写入文件（含本片新增的）出现「登记 runtime」都算动作说明泄漏。
    problems = [f"{rel} 出现「登记 runtime」（T013 D02：动作说明只在 components/actionTitle.ts）"
                for rel, text in pool.items()
                if "登记 runtime" in (text.replace("先登记 runtime", "")
                                      if rel.replace("\\", "/") == PROFILEFORM_REL else text)]
    fail_if(problems, "src/writes/ 里出现了动作说明「登记 runtime」")


def test_s07_service_side_four_spots():
    """S07 / D02、D08：服务只改站主拍板的四处——writeroutes.ts 的 ADAPTERS 扩到五值（含 quizs）且注释不再说
    「四个」；write-argv.test.ts 有 quizs 通过的用例；README 补「adapter 取五值」一句；redaction.ts 的注释
    去掉「四值 ADAPTERS」的说法（HUB_ADAPTER_ENUM 枚举不动）。"""
    need_file(WRITEROUTES_REL)
    text = read_rel(WRITEROUTES_REL)
    m = re.search(r"const ADAPTERS = \[([^\]]*)\]", text)
    assert m, "writeroutes.ts 应保留 const ADAPTERS"
    values = re.findall(r'"([^"]+)"', m.group(1))
    assert values == list(ADAPTER_FIVE), \
        f"runtime.add 的 ADAPTERS 应恰为五个值 {list(ADAPTER_FIVE)}（与内核 kit_roles.py 对齐），实际 {values}"
    head = text[: m.start()]
    cstart = head.rfind("/**")
    comment = text[cstart: m.start()] if cstart >= 0 else ""
    assert "四个" not in comment, "ADAPTERS 的注释应随五值更新（不再写「四个取值」）"
    need_file(WRITE_ARGV_TEST_REL)
    test = read_rel(WRITE_ARGV_TEST_REL)
    assert re.search(r'ok\(\s*"runtime\.add"\s*,\s*\{[^}]*adapter:\s*"quizs"[^}]*\}', test), \
        'write-argv.test.ts 应加一条 quizs 通过的用例（ok("runtime.add", {…, adapter: "quizs"})）'
    need_file(UI_README_REL)
    assert README_ADAPTER_SENTENCE in read_rel(UI_README_REL), \
        f"ui README 的 runtime.add 一条应补「{README_ADAPTER_SENTENCE}」"
    need_file(REDACTION_REL)
    redaction = read_rel(REDACTION_REL)
    assert "四值 ADAPTERS" not in redaction, "redaction.ts 的注释不应再说「四值 ADAPTERS」（runtime.add 的表也是五个）"
    assert 'allowEnum("pi", "claude-code", "codex", "opencode", "quizs", null)' in redaction, \
        "HUB_ADAPTER_ENUM 的枚举应原样保留（只改注释，枚举不动）"


def test_s08_executor_tests_present_and_tokens():
    """S08 / D01、第 10 步：两个执行端测试文件都在，不用 skip/only/todo，且带最小覆盖记号。"""
    for name in EXECUTOR_TESTS:
        rel = f"{TESTS_REL}/{name}"
        need_file(rel)
        text = read_rel(rel)
        bad = [pat for pat in (r"\.skip\s*\(", r"\.only\s*\(", r"\.todo\s*\(", r"\bxit\s*\(", r"describe\.only")
               if re.search(pat, text)]
        assert not bad, f"{rel} 里出现了 {bad}（不删用例、不削弱断言）"
        missing = [t for t in EXECUTOR_TEST_TOKENS[name] if t not in text]
        assert not missing, f"{rel} 里缺少记号 {missing}（合同要求的最小覆盖）"


def test_s09_shared_surfaces_untouched():
    """S09 / D05、非目标：src/mock 不新增 JSON（仍恰 14 份）、src/pages 顶层不新增页面文件（仍恰 9 个）、
    components/index.ts 不引用 writes/、snapshots.ts 的 runtimeRemoveSnapshot 原样复用（不改名、不改文件）。"""
    jsons = sorted(p.name for p in (REPO_ROOT / MOCK_REL).glob("*.json"))
    assert len(jsons) == BASELINE_MOCK_JSON_COUNT, f"src/mock 应仍恰 {BASELINE_MOCK_JSON_COUNT} 份 JSON，现在有 {jsons}"
    pages = sorted(p.name for p in (REPO_ROOT / f"{SRC_REL}/pages").glob("*Page.tsx"))
    assert len(pages) == BASELINE_PAGE_COUNT, f"src/pages 顶层应仍恰 {BASELINE_PAGE_COUNT} 个 *Page.tsx，现在有 {pages}"
    assert "writes" not in read_rel(INDEX_TS_REL), "components/index.ts 不应引用 src/writes/"
    need_file(SNAPSHOTS_REL)
    snapshots = read_rel(SNAPSHOTS_REL)
    assert re.search(r"export function runtimeRemoveSnapshot\(", snapshots), \
        "snapshots.ts 应原样保留 runtimeRemoveSnapshot（runtime.add 的快照复用它，不改名）"
    assert re.search(r"export function sameSnapshot\(", snapshots), "sameSnapshot 应保留"


# ---------------------------------------------------------------------------
# 探针源码（每份自包含：辅助函数不跨文件共享）
# ---------------------------------------------------------------------------

PROBE_PRELUDE = r"""
import * as React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

vi.setConfig({ testTimeout: 60000 });

async function drainNav() {
  for (let i = 0; i < 2; i += 1) {
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
  }
}
beforeEach(async () => {
  window.location.hash = '';
  await drainNav();
});
afterEach(async () => {
  cleanup();
  vi.useRealTimers();
  window.location.hash = '';
  await drainNav();
});
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) {
      await Promise.resolve();
    }
  });
}
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
function textOf(el: Element | null | undefined): string {
  return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
}
function buttons(root: ParentNode): HTMLButtonElement[] {
  return Array.from(root.querySelectorAll('button')) as HTMLButtonElement[];
}
function buttonByText(root: ParentNode, text: string): HTMLButtonElement {
  const hit = buttons(root).find((b) => textOf(b) === text);
  expect(hit, '找不到文字为「' + text + '」的按钮').toBeTruthy();
  return hit as HTMLButtonElement;
}
function toastText(): string {
  return textOf(document.querySelector('.tt-toast'));
}
function bodyText(): string {
  return textOf(document.body);
}
function frame(): HTMLElement | null {
  return document.querySelector('[data-page-state]');
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  const mod: any = await import('../src/App');
  const App = mod.default ?? mod.App;
  expect(App, 'src/App.tsx 应导出 App').toBeTruthy();
  const out = render(<App />);
  await settle();
  return out;
}
"""

# 替身 api.ts（T022/T023/T024 探针同款）：默认转调真实现，用 set() 换成任意信封或挂起
PROBE_API_MOCK = r"""
const hoisted = vi.hoisted(() => ({ spies: {} as Record<string, any>, overrides: {} as Record<string, any> }));
vi.mock('../src/api', async (importOriginal) => {
  const actual: any = await importOriginal();
  const out: any = { ...actual };
  for (const [name, fn] of Object.entries(actual)) {
    if (typeof fn === 'function') {
      const spy = vi.fn((...args: any[]) => (hoisted.overrides[name] ? hoisted.overrides[name](...args) : (fn as any)(...args)));
      hoisted.spies[name] = spy;
      out[name] = spy;
    }
  }
  return out;
});
beforeEach(() => {
  Object.keys(hoisted.overrides).forEach((k) => delete hoisted.overrides[k]);
  Object.values(hoisted.spies).forEach((s: any) => s.mockClear());
});
function set(name: string, value: any) {
  hoisted.overrides[name] = typeof value === 'function' ? value : () => Promise.resolve(value);
}
function env(data: any, command: string[] = ['gate']): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}
function reply(body: any, status = 200): any {
  return { status, body };
}
function previewCalls(): any[] {
  const s = (hoisted.spies as any)['preview'];
  return s ? s.mock.calls : [];
}
function addRuntimeCalls(): any[] {
  const s = (hoisted.spies as any)['addRuntime'];
  return s ? s.mock.calls : [];
}
"""

# form 探针：页头入口、表单字段与校验、实时预览、已登记原文与全流程（合同 Behavior contract；D01–D04）
PROBE_FORM = PROBE_PRELUDE + PROBE_API_MOCK + r"""
function headerButtons(): HTMLButtonElement[] {
  const bar = document.querySelector('.tt-page__actions');
  expect(bar, '页头应有 .tt-page__actions').toBeTruthy();
  return buttons(bar as HTMLElement);
}
function modalDialogs(): HTMLElement[] {
  return Array.from(document.querySelectorAll('[role="dialog"][aria-modal="true"]')) as HTMLElement[];
}
// 表单对话框：里面有适配器下拉（选项值里有 quizs）；写确认框（WriteConfirmDialog）没有下拉
function formDialog(): HTMLElement | null {
  return modalDialogs().find((d) =>
    Array.from(d.querySelectorAll('option')).some((o) => (o as HTMLOptionElement).value === 'quizs')) || null;
}
function needFormDialog(): HTMLElement {
  const d = formDialog();
  expect(d, '登记运行时的表单对话框应开着（含适配器下拉）').not.toBeNull();
  return d as HTMLElement;
}
function confirmDialog(): HTMLElement | null {
  return modalDialogs().find((d) => d !== formDialog()) || null;
}
function needConfirmDialog(): HTMLElement {
  const d = confirmDialog();
  expect(d, '写确认框应开着').not.toBeNull();
  return d as HTMLElement;
}
// 命令字段：帮助文字「JSON 字符串数组，第一项写命令的绝对路径」所在的 .tt-field 里的输入框（合同逐字）
const CMD_HELP = 'JSON 字符串数组，第一项写命令的绝对路径';
function commandField(d: HTMLElement): HTMLInputElement {
  const field = Array.from(d.querySelectorAll('.tt-field')).find(
    (f) => textOf((f as HTMLElement).querySelector('.tt-field__help')) === CMD_HELP);
  expect(field, '命令字段应带帮助文字「' + CMD_HELP + '」').toBeTruthy();
  const input = (field as HTMLElement).querySelector('input');
  expect(input, '命令字段里应有输入框').toBeTruthy();
  return input as HTMLInputElement;
}
// ID 字段：表单里除命令字段外恰一个文本输入
function idField(d: HTMLElement): HTMLInputElement {
  const cmd = commandField(d);
  const rest = (Array.from(d.querySelectorAll('input')) as HTMLInputElement[])
    .filter((i) => i !== cmd && i.type !== 'hidden');
  expect(rest.length, '除命令字段外应恰有一个 ID 输入框').toBe(1);
  return rest[0];
}
function adapterSelect(d: HTMLElement): HTMLSelectElement {
  const sels = Array.from(d.querySelectorAll('select'));
  expect(sels.length, '表单里应恰有一个适配器下拉').toBe(1);
  return sels[0] as HTMLSelectElement;
}
function formConfirm(d: HTMLElement): HTMLButtonElement {
  const hit = buttons(d).find((b) => textOf(b) === '确认…');
  expect(hit, '表单底部应有 [确认…]').toBeTruthy();
  return hit as HTMLButtonElement;
}
async function openForm(hash: string = '#/runtimes'): Promise<HTMLElement> {
  await mountApp(hash);
  fireEvent.click(buttonByText(document.body, '手动登记…'));
  await settle();
  return needFormDialog();
}
function fillId(d: HTMLElement, value: string) {
  fireEvent.change(idField(d), { target: { value } });
}
// 界面上没有任何 force 控件（按钮/选项/输入）；整页文本另查（preview-registered 的内核原文本身含 --force）
function noForceControls(root: ParentNode): void {
  const labelled = buttons(root).map((b) => textOf(b) || b.getAttribute('aria-label') || '');
  expect(labelled.some((t) => /force/i.test(t)), '不应有 force 按钮：' + labelled.join(',')).toBe(false);
  const opts = Array.from(root.querySelectorAll('option')).map((o) => (o as HTMLOptionElement).value);
  expect(opts.some((v) => /force/i.test(v)), '不应有 force 选项：' + opts.join(',')).toBe(false);
}

describe('T041 运行时页 [手动登记…] 与表单', () => {
  it('页头：次序 [扫描 PATH]、[手动登记…]（可点、PlusIcon、primary）、[刷新]；[扫描 PATH] 仍禁用；点开标题「登记运行时」的表单', async () => {
    vi.useFakeTimers();
    await mountApp('#/runtimes');
    const bs = headerButtons();
    expect(bs.map(textOf)).toEqual(['扫描 PATH', '手动登记…', '刷新']);
    expect(bs[0].disabled, '[扫描 PATH] 仍禁用（本片不做扫描）').toBe(true);
    expect(bs[1].disabled, '[手动登记…] 应可点（R1 放宽后的新行为）').toBe(false);
    expect(bs[1].querySelector('svg'), '[手动登记…] 带 PlusIcon').not.toBeNull();
    expect(bs[1].getAttribute('data-variant')).toBe('primary');
    fireEvent.click(bs[1]);
    await settle();
    const d = needFormDialog();
    expect(textOf(d), '对话框标题「登记运行时」').toContain('登记运行时');
  });

  it('空态：标题「还没有登记的 runtime」保留、说明改成指向页头的 [手动登记…]；空态下入口照样能点开表单', async () => {
    await mountApp('#/runtimes?mock=empty');
    const f = frame();
    expect(f && f.getAttribute('data-page-state')).toBe('empty');
    expect(textOf(f)).toContain('还没有登记的 runtime');
    expect(textOf(f)).toContain('用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）');
    fireEvent.click(buttonByText(document.body, '手动登记…'));
    await settle();
    needFormDialog();
  });

  it('offline（?mock=offline）：[手动登记…] 照样可点（与 [新建 profile] 同口径）', async () => {
    await mountApp('#/runtimes?mock=offline');
    const b = buttonByText(document.body, '手动登记…');
    expect(b.disabled, '离线时也应可点').toBe(false);
    fireEvent.click(b);
    await settle();
    needFormDialog();
  });

  it('字段：适配器下拉恰五个值（缺省 pi）；ID 与命令等宽；命令帮助原文；界面没有 force', async () => {
    vi.useFakeTimers();
    const d = await openForm();
    const sel = adapterSelect(d);
    const opts = Array.from(sel.querySelectorAll('option')).map((o) => (o as HTMLOptionElement).value);
    expect(opts, '适配器五值（合同 Behavior contract 的次序）').toEqual(['pi', 'claude-code', 'codex', 'opencode', 'quizs']);
    expect(sel.value, '适配器缺省 pi').toBe('pi');
    expect(/mono/.test(idField(d).className), 'ID 等宽').toBe(true);
    expect(/mono/.test(commandField(d).className), '命令等宽').toBe(true);
    noForceControls(d);
    expect(bodyText(), '整页没有 force（此刻没有任何内核原文）').not.toMatch(/force/i);
  });

  it('ID 不合法（大写/下划线、连字符开头、超 64）：逐字提示、不调 preview、[确认…] 不可点；空 ID 也不调 preview', async () => {
    vi.useFakeTimers();
    const d = await openForm();
    const ID_ERR = '只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符';
    for (const v of ['Bad_ID', '-lead', 'a'.repeat(65)]) {
      fillId(d, v);
      await advance(301);
      expect(textOf(d), 'ID 提示逐字（' + v.slice(0, 8) + '）').toContain(ID_ERR);
      expect(previewCalls().length, 'ID 不合法不调 preview').toBe(0);
      expect(formConfirm(d).disabled).toBe(true);
    }
    fillId(d, '');
    await advance(301);
    expect(previewCalls().length, '空 ID 不调 preview').toBe(0);
    expect(formConfirm(d).disabled).toBe(true);
  });

  it('命令不合法（非 JSON、非数组、空数组、空串、超 1024 码点、控制字符）：逐字提示、不调 preview、[确认…] 不可点', async () => {
    vi.useFakeTimers();
    const d = await openForm();
    fillId(d, 'gate-x');
    const CMD_ERR = '命令要写成 JSON 字符串数组，例如 ["C:/tools/pi.exe"]；每项非空、不超过 1024 个字符、不含控制字符';
    const bad = ['not json', '"pi"', '[]', '[""]', '["' + 'x'.repeat(1025) + '"]', '["ab"]'];
    for (const v of bad) {
      fireEvent.change(commandField(d), { target: { value: v } });
      await advance(301);
      expect(textOf(d), '命令提示逐字（' + v.slice(0, 10) + '）').toContain(CMD_ERR);
      expect(previewCalls().length, '命令不合法不调 preview').toBe(0);
      expect(formConfirm(d).disabled).toBe(true);
    }
  });

  it('合法表单：300ms 防抖后调一次 preview（action 为 runtime.add、args 无 command 键），底部显示将运行的命令，[确认…] 可点', async () => {
    vi.useFakeTimers();
    const d = await openForm();
    fillId(d, 'gate-x');
    await advance(299);
    expect(previewCalls().length, '299ms 不发').toBe(0);
    await advance(1);
    expect(previewCalls().length, '300ms 恰好发一次').toBe(1);
    expect(previewCalls()[0][0]).toBe('runtime.add');
    expect(previewCalls()[0][1], '命令留空 → 不传 command 这个键').toEqual({ runtime: 'gate-x', adapter: 'pi' });
    expect(textOf(d)).toContain('config runtime add gate-x --adapter=pi');
    expect(textOf(d), '界面显示的是「将运行的命令」，不含 --dry-run 与 --json（v2 合同 D01 的口径）').not.toContain('--dry-run');
    expect(textOf(d)).not.toContain('--json');
    expect(formConfirm(d).disabled).toBe(false);
  });

  it('改值后只发最新一次：gate-a 改成 gate-b，两次 299ms 都不发，最终只预览 gate-b', async () => {
    vi.useFakeTimers();
    const d = await openForm();
    fillId(d, 'gate-a');
    await advance(299);
    fillId(d, 'gate-b');
    await advance(299);
    expect(previewCalls().length).toBe(0);
    await advance(2);
    expect(previewCalls().length).toBe(1);
    expect(previewCalls()[0][1]).toEqual({ runtime: 'gate-b', adapter: 'pi' });
  });

  it('换适配器与带命令：args 原样带数组、命令行带 --command=（JSON.stringify，无空格），选 quizs 不在本地被拦', async () => {
    vi.useFakeTimers();
    const d = await openForm();
    fillId(d, 'gate-x');
    fireEvent.change(adapterSelect(d), { target: { value: 'quizs' } });
    fireEvent.change(commandField(d), { target: { value: '["C:/tools/pi.exe","--flag"]' } });
    await advance(301);
    expect(previewCalls()[0][1]).toEqual({ runtime: 'gate-x', adapter: 'quizs', command: ['C:/tools/pi.exe', '--flag'] });
    expect(textOf(d)).toContain('config runtime add gate-x --adapter=quizs');
    expect(textOf(d)).toContain('--command=["C:/tools/pi.exe","--flag"]');
    expect(formConfirm(d).disabled).toBe(false);
  });

  it('服务 400：预览区原样显示该行，[确认…] 不可点', async () => {
    vi.useFakeTimers();
    set('preview', () => Promise.resolve({ status: 400, body: { ok: false, exit_code: null, data: null, output: [], messages: ['ERROR: adapter 不合法'], command: ['config', 'runtime', 'add', 'gate-x'], elapsed_ms: 0 } }));
    const d = await openForm();
    fillId(d, 'gate-x');
    await advance(301);
    expect(textOf(d)).toContain('ERROR: adapter 不合法');
    expect(formConfirm(d).disabled).toBe(true);
  });

  it('已登记为别的适配器（?write=preview-registered）：内核原文逐字显示、[确认…] 不可点、界面没有 force 控件', async () => {
    vi.useFakeTimers();
    const d = await openForm('#/runtimes?write=preview-registered');
    fillId(d, 'gate-x');
    await advance(301);
    expect(previewCalls().length).toBe(1);
    expect(textOf(d)).toMatch(/ERROR: runtime gate-x 已登记为 [a-z-]+；改 adapter 要加 --force/);
    expect(formConfirm(d).disabled, '内核拒绝时 [确认…] 不可点').toBe(true);
    noForceControls(d);
  });

  it('全流程：[确认…] 进确认框（标题「登记运行时 X？」、变化区摘要、命令），执行 addRuntime 后成功轻提示「已登记运行时 X」；成功后表单清空', async () => {
    vi.useFakeTimers();
    const d = await openForm();
    fillId(d, 'gate-x');
    await advance(301);
    fireEvent.click(formConfirm(d));
    await settle();
    const cd = needConfirmDialog();
    const t = textOf(cd);
    expect(t).toContain('登记运行时 gate-x？');
    expect(t).toContain('已登记表里加上 gate-x（适配器 pi）');
    expect(t).toContain('config runtime add gate-x --adapter=pi');
    expect(t, '同一个 id 同一个适配器也照常走完流程（不显示「没有变化」）').not.toContain('没有变化');
    fireEvent.click(buttonByText(cd, '确认…'));
    await settle();
    expect(addRuntimeCalls().length).toBe(1);
    expect(addRuntimeCalls()[0][0], '命令留空 → 不传 command 键').toEqual({ runtime: 'gate-x', adapter: 'pi' });
    expect(typeof addRuntimeCalls()[0][1]).toBe('string');
    expect(toastText(), '成功轻提示').toContain('已登记运行时 gate-x');
    expect(formDialog(), '确认后表单对话框关闭').toBeNull();
    // 成功后表单清空：重开表单
    fireEvent.click(buttonByText(document.body, '手动登记…'));
    await settle();
    const d2 = needFormDialog();
    expect(idField(d2).value).toBe('');
    expect(adapterSelect(d2).value).toBe('pi');
    expect(commandField(d2).value).toBe('');
  });

  it('带命令的全流程：变化区摘要接「；命令写进本机文件」，addRuntime 带命令数组', async () => {
    vi.useFakeTimers();
    const d = await openForm();
    fillId(d, 'gate-x');
    fireEvent.change(commandField(d), { target: { value: '["C:/tools/pi.exe","--flag"]' } });
    await advance(301);
    fireEvent.click(formConfirm(d));
    await settle();
    const cd = needConfirmDialog();
    expect(textOf(cd)).toContain('已登记表里加上 gate-x（适配器 pi）；命令写进本机文件');
    fireEvent.click(buttonByText(cd, '确认…'));
    await settle();
    expect(addRuntimeCalls()[0][0]).toEqual({ runtime: 'gate-x', adapter: 'pi', command: ['C:/tools/pi.exe', '--flag'] });
    expect(toastText()).toContain('已登记运行时 gate-x');
  });
});
"""

# api 探针：addRuntime 真实模式的路由与正文、桩模式的命令行与 409、preview-registered 情景（D01、D02）
PROBE_API = PROBE_PRELUDE + r"""
import * as api from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const posts: Array<{ path: string; body: any; timeoutSeconds: number | undefined }> = [];
const fake = {
  get(_path: string, _query?: any, _timeoutSeconds?: number) {
    return Promise.resolve({ ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0 });
  },
  post(path: string, body: unknown, timeoutSeconds?: number) {
    posts.push({ path, body, timeoutSeconds });
    return Promise.resolve({ status: 200, body: { ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0 } });
  },
  getRaw(_path: string, _query?: any, _timeoutSeconds?: number) {
    return Promise.resolve({ status: 404, body: null });
  },
} as unknown as LiveClient;

afterEach(() => {
  posts.length = 0;
  setLiveClientForTests(undefined);
});

describe('T041 api：addRuntime 与桩', () => {
  it('真实模式：POST /api/v1/runtimes/<id>/add，正文带 adapter 与 confirmation，命令留空不带 command，时限 90 秒', async () => {
    setLiveClientForTests(fake);
    await api.addRuntime({ runtime: 'demo-run', adapter: 'quizs' }, 'c-1');
    expect(posts.length).toBe(1);
    expect(posts[0].path).toBe('/api/v1/runtimes/demo-run/add');
    expect(posts[0].body).toEqual({ adapter: 'quizs', confirmation: 'c-1' });
    expect(posts[0].timeoutSeconds).toBe(90);
  });

  it('真实模式：命令按字符串数组原样传；空数组等于留空（正文不带 command 键）', async () => {
    setLiveClientForTests(fake);
    await api.addRuntime({ runtime: 'demo-run', adapter: 'pi', command: ['C:/tools/pi.exe', '--flag'] }, 'c-2');
    await api.addRuntime({ runtime: 'demo-run', adapter: 'pi', command: [] }, 'c-3');
    expect(posts.length).toBe(2);
    expect(posts[0].body).toEqual({ adapter: 'pi', command: ['C:/tools/pi.exe', '--flag'], confirmation: 'c-2' });
    expect(posts[1].body, '空数组的 command 会被去掉（writeArgs 的规则）').toEqual({ adapter: 'pi', confirmation: 'c-3' });
  });

  it('桩模式预览：命令照服务 buildWriteArgv 逐字（quizs、--command=JSON.stringify 无空格、--dry-run --json）；resources 不带命令 [config]、带命令 [config,local]', async () => {
    window.location.hash = '#/gate?write=ok';
    const r = await api.preview('runtime.add', { runtime: 'demo-run', adapter: 'quizs' });
    expect(r.status).toBe(200);
    expect(r.body.ok).toBe(true);
    expect(r.body.data.command).toEqual(['config', 'runtime', 'add', 'demo-run', '--adapter=quizs', '--dry-run', '--json']);
    expect(r.body.data.resources).toEqual(['config']);
    expect(r.body.data.binding_changes).toEqual([]);
    expect((r.body.data.confirmation as string).length).toBe(43);
    const withCmd = await api.preview('runtime.add', { runtime: 'demo-run', adapter: 'pi', command: ['C:/tools/pi.exe', '--flag'] });
    expect(withCmd.body.data.command).toEqual(['config', 'runtime', 'add', 'demo-run', '--adapter=pi',
      '--command=["C:/tools/pi.exe","--flag"]', '--dry-run', '--json']);
    expect(withCmd.body.data.resources).toEqual(['config', 'local']);
  });

  it('桩模式执行：命令带 --expect-state=<state>；确认号或参数不符 409（exit_code null、原文）；空数组命令与「预览没带」等价', async () => {
    window.location.hash = '#/gate?write=ok';
    const conf = (await api.preview('runtime.add', { runtime: 'demo-run', adapter: 'quizs' })).body.data.confirmation;
    const run = await api.addRuntime({ runtime: 'demo-run', adapter: 'quizs' }, conf);
    expect(run.status).toBe(200);
    expect(run.body.ok).toBe(true);
    expect(run.body.command).toEqual(['config', 'runtime', 'add', 'demo-run', '--adapter=quizs', '--expect-state=<state>']);
    const same = await api.addRuntime({ runtime: 'demo-run', adapter: 'quizs', command: [] }, conf);
    expect(same.status, '空数组命令整理后与「没带」等价，确认号应匹配').toBe(200);
    const badConf = await api.addRuntime({ runtime: 'demo-run', adapter: 'quizs' }, 'x'.repeat(43));
    expect(badConf.status).toBe(409);
    expect(badConf.body.exit_code).toBe(null);
    expect(badConf.body.messages).toEqual(['ERROR 确认号无效、已过期或已用过：请重新预览']);
    const badArgs = await api.addRuntime({ runtime: 'demo-run', adapter: 'codex' }, conf);
    expect(badArgs.status, '参数不符也回 409').toBe(409);
  });

  it('preview-registered 情景：预览 200、ok 假、退出码 1、data null、一行内核原文（带请求的 id），不发确认号；执行回 409', async () => {
    window.location.hash = '#/gate?write=preview-registered';
    const r = await api.preview('runtime.add', { runtime: 'demo-run', adapter: 'pi' });
    expect(r.status).toBe(200);
    expect(r.body.ok).toBe(false);
    expect(r.body.exit_code).toBe(1);
    expect(r.body.data).toBe(null);
    expect(r.body.messages.length).toBe(1);
    expect(r.body.messages[0]).toMatch(/^ERROR: runtime demo-run 已登记为 [a-z-]+；改 adapter 要加 --force$/);
    expect(r.body.messages[0]).not.toContain('undefined');
    const run = await api.addRuntime({ runtime: 'demo-run', adapter: 'pi' }, 'y'.repeat(43));
    expect(run.status, '没有签发确认号，执行一律 409').toBe(409);
  });
});
"""

PROBE_SPECS = {
    "form": (PROBE_FORM, (RUNTIMESPAGE_REL, RUNTIMEFORM_REL, API_REL)),
    "api": (PROBE_API, (API_REL, MODE_REL)),
}
PROBE_ORDER = ("form", "api")


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针
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


class Pipeline:
    def __init__(self):
        self.ran = False
        self.reason = ""
        self.steps = {}
        self.status_before = None
        self.status_after = None
        self.digests_before = {}
        self.digests_after = {}
        self.stopped_reason = ""
        self.probe_files = {}
        self.probe_skipped = {}
        self.gate_probe_left = None


def _kill_tree(proc):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=60)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        proc.kill()


def run_capture(argv, cwd, timeout, env):
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    start = time.monotonic()
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
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
    return env


def t041_marker_present():
    """候选里 api.ts 是否已有 T041 的标记（addRuntime）：没有就不起 npm（基线上必然没有）。"""
    path = REPO_ROOT / API_REL
    if not path.is_file():
        return False
    try:
        return "addRuntime" in _read(path)
    except OSError:
        return False


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t041_marker_present():
        pipe.reason = ("候选里 api.ts 还没有 T041 的标记（addRuntime），没有东西可测，未调用 npm；"
                       "候选把写函数、表单与桩接上之后，流水线才会运行 npm ci、Vitest 与探针")
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
        if ci_ok:
            run_step("npm test", [npm, "test"])
            run_step("npm run build", [npm, "run", "build"])
            uid = uuid.uuid4().hex[:12]
            for key in PROBE_ORDER:
                missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                name = f"probe-{uid}-t041-{key}.test.tsx"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                written.append(path)
                path.write_text(PROBE_SPECS[key][0], encoding="utf-8", newline="\n")
                pipe.probe_files[key] = name
                run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        else:
            pipe.stopped_reason = "npm ci（含 --offline 兜底）失败，后续步骤未运行"
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
        pipe.status_after = git_status_set()
        pipe.digests_after = {name: file_digest(WEB / name) for name in WATCHED}
    return pipe


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


# ---------------------------------------------------------------------------
# P 系列：流水线断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、V02、D06：npm 依赖（已在就跳过）、npm test（全绿，含执行端两个新测试与照新行为改过的
    page-app）、npm run build 都退出 0；依赖文件一个字节没动。"""
    assert any(pipeline.steps.get(k) is not None and pipeline.steps[k].code == 0
               for k in ("npm ci", "npm ci --offline")), \
        f"npm ci 未成功：{pipeline.stopped_reason or pipeline.reason}"
    for name in ("npm test", "npm run build"):
        step = assert_step_ok(pipeline, name)
        if name == "npm test":
            m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
            assert m, f"npm test 输出里没有通过计数：\n{step.tail}"
            assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), \
                f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
        if name == "npm run build":
            assert "built in" in step.out, f"vite build 应打印 built in：\n{step.tail}"
    assert pipeline.digests_before == pipeline.digests_after, \
        "npm 流水线不许改动 desktop/web/package.json 与 package-lock.json"
    assert not pipeline.gate_probe_left, "gate-probe/ 目录在探针后应清掉"


def test_p2_worktree_unchanged_by_pipeline(pipeline):
    """P2（守卫）：流水线与探针前后 git status 相同；gate-probe/ 没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"


def test_d01_d03_probe_form(pipeline):
    """form 探针 / D01–D03：页头入口可点（PlusIcon、primary、次序）、空态与 offline 也能点开、
    适配器五值缺省 pi、ID 与命令的逐字校验与门控（不调 preview）、300ms 防抖与改值只发最新一次、
    服务 400 原文、preview-registered 的内核原文（[确认…] 不可点、没有 force 控件）、全流程（确认框
    标题与变化区摘要、addRuntime 的参数与确认号、成功轻提示、成功后表单清空）。"""
    assert_probe_ok(pipeline, "form")


def test_d01_d02_probe_api(pipeline):
    """api 探针 / D01、D02：addRuntime 真实模式的路径/正文/时限（命令留空与空数组都不带 command 键）；
    桩模式预览命令照服务 buildWriteArgv 逐字、resources 两态；执行命令带 --expect-state、409 的两种；
    preview-registered 的原文与退出码。"""
    assert_probe_ok(pipeline, "api")
