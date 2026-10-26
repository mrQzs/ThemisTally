"""T022 战前门禁：桌面端前端「写操作的确认框与流程」A 片（D2 之四，W3、W3b）的黑盒基准测试
（合同 t022-desktop-ui-confirm v2，基线 7fafe2f——531a608 的后代，两提交之间只改了 ts/、文档与门禁文件，desktop/web
内容相同；v2 相对 v1 允许改 desktop/web/tests/page-app.test.tsx 的写入口计数，见 D17）。

被测对象是 ``desktop/web/``：``src/api.ts`` 新增 ``preview``/``getOperation``/``usePreset``/``setPluginEnabled``
四个写函数与配套类型（``Envelope.exit_code`` 放宽成 ``number | null``），新增 ``src/mock/writes.ts``（``?write=``
演示情景）、``src/writes/`` 的 ``writeOutcome.ts``/``snapshots.ts``/``useWriteFlow.ts``/``WriteConfirmDialog.tsx``/
``write-flow.css``，``Dialog`` 加 ``dismissible``，``PageFrame`` 的 ``children`` 加可选 ``reload``，并把三个写入口
（角色页方案 [切换…]、方案表 [使用]、插件表 [启用…]/[停用…]）接上；B 片的四个入口照旧是带「第二阶段接入」提示的
``DisabledAction``。成功只在重读之后才说（W3）；确认框里不出现「没有变化」这个子串（W3b）。

基线（7fafe2f，desktop/web 内容与 531a608 相同）上 ``src/mock/writes.ts``、``src/writes/`` 与四个 ``tests/writes-*``
测试文件都不存在，``api.ts``
没有四个写函数，``Dialog`` 没有 ``dismissible``，三个入口都是 ``DisabledAction``，所以本文件的失败落在「文件不存在」
「标记不在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有仓库文件的读取都发生在用例函数里；流水线
（装依赖之后起 build、Vitest 与探针）放在 ``pipeline`` 会话级夹具里，候选里没有任何新源码文件时不装依赖、不起 Vitest。

结构（编号对应合同 DoD 的 D01–D18，其中 D17 是 v2 新增的 page-app.test.tsx 计数改法、D18 是执行纪律无机械断言；
D16 附带的 21 条变异靠这些断言加执行端的四个 ``writes-*`` 测试文件抓，战后门禁另出变异清单）：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：新文件在位（D01）；api.ts 恰好四个写函数加配套类型、
  13 个读函数都在、exit_code 放宽（D01）；不导出 B 片的四个写函数与 LATER_API 里的名字（D02，过渡）；Dialog 的
  dismissible（D08）；PageFrame 的 reload 与六处类型放宽（D14）；write-flow.css 只用既有令牌且被接进源码（D14）；
  B 片四个入口仍是 DisabledAction（D06，过渡）；三个入口的接线（D09–D11）；不新增 JSON 夹具、页面文件与
  components/index.ts（D15）；执行端四个测试文件在位、不用 skip/only/todo、且带有覆盖映射表/快照/轮询/对话框的记号
  （D03–D05、D12–D13）；页面与视图不引入写函数（第八节）；mock/writes.ts 收全 19 个情景值（第二节）；page-app.test.tsx
  的「写入口个数（过渡）」计数 13→12 且用例名列出所数按钮（D17，v2 新增，过渡——见下方过渡断言与 B 片退役清单）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：npm ci、npm run build、
  npm test、npm run check:contract，再把探针逐份写成 ``gate-probe/probe-<唯一标识>-t022-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除。

探针（Vitest + jsdom，全部自包含）：

- api：四个写函数的导出集合与形状（PreviewData 八键、OperationView 八键、命令照 README :83–95）、19 个 ``?write=``
  情景逐行（预览、执行、getOperation 三列）、``exit_code`` 为 null；
- dialog：``dismissible`` 缺省行为不变；为 false 时 Esc、遮罩、头部关闭钮都不关框（D08/M14–M16）；
- entries：三个入口接上（[切换…] 可点且 primary md、说明「已选 economy」；[使用] ghost sm；插件 [启用…]/[停用…] 可点
  且不冒泡——抽屉不开、getPlugin 不被调用，offline 下也保持可点）（D07、D09–D11）；B 片 [删除…] 照旧禁用带提示（D06）；
- flow：经真实 ``?write=`` 情景走完确认流程——完成才弹「已切换到方案 economy」且关框、重读卡住时整页没有「已切换」（W3/M1）、
  exit3 之后整页没有「已切换」没有「成功」（W3/M18）、warn 不关框列 WARN 行（M17）、stale/expired 两种 409（M4）、busy 回到
  可确认提示「服务繁忙」（M5/M6）、closing 到失败带「服务出错」、reread-fail 是「命令已成功，但重新读取失败」且不弹轻提示
  （M9）、drop-done 轮询到终态（M12）、drop-lost 进「结果未知」（M13）、drop-hang 到 119 秒不下结论、121 秒进「结果未知」
  （M10/M11）、执行中 Esc/遮罩/[取消]/关闭钮都关不掉（M14–M16）、确认框任何状态都不出现「没有变化」（W3b）。

过渡断言（``test_transitional_`` 开头，docstring 第一行写明哪项后续工作推翻它）：api.ts 不导出 B 片的四个写函数
（B 片开工时推翻）、B 片四个入口仍是 DisabledAction（B 片接上时推翻）、page-app.test.tsx 的「写入口个数（过渡）」
仍是 A 片的 12/9/0 计数与按钮列举用例名（B 片接上时推翻：角色页 12→9、运行时页 9→8）。其余（入口接线、确认框
文案、W3/W3b、令牌规则、文件名单）是长期断言。

B 片退役清单（B 片开工准备时统一退役，站主按名字找，共五项）：``test_transitional_s03_api_no_b_writes_no_later_names``、
``test_transitional_s09_b_entries_still_disabled_actions``、``test_transitional_s17_page_app_write_entry_count`` 三条
``test_transitional_`` 用例；entries 探针里 it 名带「（过渡：B 片开工时推翻）」的那条（方案表 [删除…] 仍是带
「第二阶段接入」提示的禁用入口）；api 探针 FORBIDDEN 数组里 B 片的四个名字（removePreset、removeProfile、
removeRuntime、rollback）。

合同没有写死、门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：``preview`` 的 args 记录键名
（``preset.use`` 用 ``{name}``、插件用 ``{id}``）；getOperation 在 ``drop-*``/busy/expired 情景里用预览返回的 confirmation
当操作号（合同第三节「每 1 秒查一次 getOperation(确认号)」）；轮询探针的计时推进量（119000/121000 毫秒）取上下界各容
半秒到一秒的抖动。
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
SRC = WEB / "src"
WRITES_REL = f"{SRC_REL}/writes"
MOCK_REL = f"{SRC_REL}/mock"
TESTS_REL = f"{WEB_REL}/tests"

# 合同 Scope 的新增源码（allowed_new_files 里的非测试文件）
NEW_SOURCE_FILES = (
    f"{MOCK_REL}/writes.ts",
    f"{WRITES_REL}/writeOutcome.ts",
    f"{WRITES_REL}/snapshots.ts",
    f"{WRITES_REL}/useWriteFlow.ts",
    f"{WRITES_REL}/WriteConfirmDialog.tsx",
    f"{WRITES_REL}/write-flow.css",
)
# 合同 Scope 的新增执行端测试（allowed_new_files 里的测试文件）
EXECUTOR_TESTS = (
    "writes-outcome.test.ts",
    "writes-snapshots.test.ts",
    "writes-flow.test.tsx",
    "writes-dialog.test.tsx",
)

API_REL = f"{SRC_REL}/api.ts"
DIALOG_REL = f"{SRC_REL}/components/Dialog.tsx"
PAGEFRAME_REL = f"{SRC_REL}/shell/PageFrame.tsx"
PRESETBAR_REL = f"{SRC_REL}/pages/readonly1/roles-PresetBar.tsx"
PRESETSTABLE_REL = f"{SRC_REL}/pages/readonly1/roles-PresetsTable.tsx"
PLUGINSVIEW_REL = f"{SRC_REL}/pages/readonly2/plugins-PluginsView.tsx"
ROLESVIEW_REL = f"{SRC_REL}/pages/readonly1/roles-RolesView.tsx"
ROLES_PAGE_REL = f"{SRC_REL}/pages/RolesPage.tsx"
PLUGINS_PAGE_REL = f"{SRC_REL}/pages/PluginsPage.tsx"
INDEX_TS_REL = f"{SRC_REL}/components/index.ts"

# 只放宽 exit_code 类型的另外五个文件（PageFrame 之外）
RELAXED_TYPE_FILES = (
    f"{SRC_REL}/pages/tasks/common-FileReader.tsx",
    f"{SRC_REL}/pages/readonly1/roles-PresetDiff.tsx",
    f"{SRC_REL}/pages/readonly2/history-HistoryDrawer.tsx",
    f"{SRC_REL}/pages/readonly2/logs-SearchResults.tsx",
    f"{SRC_REL}/pages/readonly2/plugins-PluginDrawer.tsx",
)
# B 片四个入口所在的文件（A 片期间照旧是 DisabledAction）
B_ENTRY_FILES = (PRESETSTABLE_REL, f"{SRC_REL}/pages/readonly1/roles-ProfilesTable.tsx",
                 f"{SRC_REL}/pages/readonly1/runtimes-RuntimesView.tsx",
                 f"{SRC_REL}/pages/readonly2/history-HistoryView.tsx")

# 基线名单：src/mock 恰 14 份 JSON、src/pages 顶层恰 9 个 *Page.tsx（不新增 JSON、不新增页面文件）
BASELINE_MOCK_JSON_COUNT = 14
BASELINE_PAGE_COUNT = 9

# 13 个读函数一行不改（名字都在）
API_READS = ("getMeta", "getStatus", "getAttempt", "readFile", "getRoles", "getProfiles", "getPresets",
             "diffPresets", "getRuntimes", "getPlugins", "getHistory", "getUsage", "listSecrets")
# 合同第一节：四个新写函数与配套类型
API_NEW_EXPORTS = ("preview", "getOperation", "usePreset", "setPluginEnabled")
API_NEW_TYPES = ("WriteAction", "HttpReply", "BindingChange", "PreviewData", "OperationView")
# B 片的四个写函数（站主决定第二条）与 T006 LATER_API 里剩下的名字：api.ts 一律不许导出
B_WRITE_EXPORTS = ("removePreset", "removeProfile", "removeRuntime", "rollback")
LATER_API = ("listAttempts", "getConfig", "validateConfig", "getHistoryEntry", "getPlugin", "checkSecret",
             "subscribeEvents", "search", "startJob", "getJob", "cancelJob", "startSecretEntry",
             "setRole", "savePreset", "saveProfile", "addRuntime")

# 合同第二节的 19 个情景值
WRITE_SCENARIOS = ("ok", "warn", "exit1", "exit2", "exit3", "stale", "expired", "busy", "closing", "spawn",
                   "toolarge", "timeout", "drop-done", "drop-lost", "drop-hang", "preview-fail",
                   "preview-busy", "reread-fail", "reread-fail-exit1")

NETWORK_WORDS = ("fetch", "XMLHttpRequest", "EventSource", "WebSocket")

# 执行端四个测试文件里应出现的记号（合同第 5 步与 D03–D05、D12–D13 的最小覆盖证据）
EXECUTOR_TEST_TOKENS = {
    "writes-outcome.test.ts": ("WARN", "内核拒绝", "用法错误", "已部分写入", "结果未知", "读取当前状态失败",
                               "请求被拒", "超时", "服务出错", "失败（退出"),
    "writes-snapshots.test.ts": ("active_preset", "binding", "enabled", "connected", "lock", "external_changes"),
    "writes-flow.test.tsx": ("连接中断", "120", "drop", "服务繁忙", "已部分写入"),
    "writes-dialog.test.tsx": ("Escape", "预览没有列出变化", "<b>", "遮罩"),
}


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def read_rel(rel):
    return _read(REPO_ROOT / rel)


def need_file(rel):
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return path


def need_new_sources():
    missing = [rel for rel in NEW_SOURCE_FILES if not (REPO_ROOT / rel).is_file()]
    assert not missing, f"缺少本片的新文件（基线上还没有实现）：{missing}"


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


_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


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


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:40])


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_new_source_files_present():
    """S01 / D01、D15：合同 allowed_new_files 的六个新源码文件都在（基线上没有，本条先红）。"""
    need_new_sources()


def test_s01b_executor_test_files_present():
    """S01b / D16：合同 allowed_new_files 的四个执行端测试文件都在，且不用 skip/only/todo。"""
    for name in EXECUTOR_TESTS:
        rel = f"{TESTS_REL}/{name}"
        need_file(rel)
        text = read_rel(rel)
        bad = [pat for pat in (r"\.skip\s*\(", r"\.only\s*\(", r"\.todo\s*\(", r"\bxit\s*\(", r"\bdescribe\.only")
               if re.search(pat, text)]
        assert not bad, f"{rel} 里出现了 {bad}（合同 D16：不删用例、不削弱断言）"


def test_s02_api_four_write_exports_and_types():
    """S02 / D01：api.ts 恰好新增四个写函数与配套类型，Envelope.exit_code 放宽成 number | null，13 个读函数都在。"""
    need_new_sources()
    text = read_rel(API_REL)
    for name in API_NEW_EXPORTS:
        # 合同写的是 export function preview(...)，执行端加 async 是语义等价的正确实现（演示数据全部已兑现）
        assert re.search(rf"export (?:async )?function {name}\(", text), f"api.ts 应导出 {name}"
    for tname in API_NEW_TYPES:
        assert re.search(rf"export (?:type|interface) {tname}\b", text), f"api.ts 应导出类型 {tname}"
    # Envelope 的 exit_code 放宽（宽松空白，避免格式差异）
    assert re.search(r"exit_code:\s*number\s*\|\s*null", text), "api.ts 的 Envelope.exit_code 应是 number | null"
    for name in API_READS:
        assert re.search(rf"export function {name}\(", text), f"api.ts 的读函数 {name} 应原样保留"
    # WriteAction 的三个成员
    assert "'preset.use'" in text and "'plugin.enable'" in text and "'plugin.disable'" in text, \
        "WriteAction 应只有 preset.use / plugin.enable / plugin.disable 三个成员"


def test_transitional_s03_api_no_b_writes_no_later_names():
    """B 片（写函数与删除/回滚入口）开工时推翻：api.ts 不导出 removePreset/removeProfile/removeRuntime/rollback，
    也不放 LATER_API 里的任何名字（站主决定第二条、T006 的 LATER_API 现状）。"""
    text = read_rel(API_REL)
    for name in B_WRITE_EXPORTS + LATER_API:
        assert not re.search(rf"export (?:async )?function {name}\b", text), \
            f"api.ts 不许导出 {name}（B 片或后续片的名字）"


def test_s04_no_network_words_in_src():
    """S04 / 非目标：src 下任何文字（注释也算）不出现 fetch、XMLHttpRequest、EventSource、WebSocket。"""
    problems = []
    for path in sorted(SRC.rglob("*")):
        if not path.is_file() or path.suffix not in (".ts", ".tsx", ".css", ".json"):
            continue
        text = _read(path)
        for word in NETWORK_WORDS:
            if re.search(rf"\b{word}\b", text):
                problems.append(f"{path.relative_to(REPO_ROOT)} 出现 {word}")
    fail_if(problems, "src 下出现了联网词（合同非目标：不做真正的网络客户端）")


def test_s05_dialog_dismissible():
    """S05 / D08、D14：DialogProps 加 dismissible?: boolean（缺省 true 的行为由 dialog 探针验证）。"""
    need_new_sources()
    text = read_rel(DIALOG_REL)
    assert re.search(r"dismissible\?:\s*boolean", text), "DialogProps 应有 dismissible?: boolean"


def test_s06_pageframe_reload_and_relaxed_types():
    """S06 / D14：PageFrame 的 ErrorInfo.exit_code 放宽、children 加可选的第二个参数 reload。"""
    need_new_sources()
    text = read_rel(PAGEFRAME_REL)
    assert re.search(r"exit_code:\s*number\s*\|\s*null", text), "PageFrame 的 ErrorInfo.exit_code 应放宽成 number | null"
    assert re.search(r"children:\s*\([^)]*reload", text) or re.search(r"reload\s*\(\)\s*:\s*Promise", text), \
        "PageFrame 的 children 应加可选的第二个参数 reload(): Promise<void>"


def test_s07_relaxed_type_files():
    """S07 / D14、第 4 步：另外五个文件只把 exit_code: number 放宽成 number | null（类型放宽，行为不变）。"""
    need_new_sources()
    for rel in RELAXED_TYPE_FILES:
        text = read_rel(rel)
        assert re.search(r"exit_code:\s*number\s*\|\s*null", text), f"{rel} 的 exit_code 类型应放宽"


def test_s08_write_flow_css_tokens_and_wiring():
    """S08 / D14、第六节：write-flow.css 不声明 --tt-* 变量、不写十六进制颜色与颜色函数；且被 src 里的模块 import
    （终审 T009 的教训：只读 CSS 文本证明不了它接进了产品）。"""
    need_new_sources()
    css = read_rel(f"{WRITES_REL}/write-flow.css")
    assert not re.search(r"--tt-[\w-]+\s*:", css), "write-flow.css 不许声明任何 --tt-* 变量（token-contract 的口径）"
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "write-flow.css 不许写十六进制颜色"
    assert not re.search(r"\b(?:rgb|rgba|hsl|hsla|color|oklch|lab)\s*\(", css), "write-flow.css 不许写颜色函数"
    # 接线：src 里要有模块 import 它，且 import 的模块自己被三个入口之一引到
    importers = [p for p in SRC.rglob("*.tsx") if "write-flow.css" in _read(p)]
    assert importers, "src 里没有模块 import write-flow.css（CSS 没接进产品）"
    entry_texts = "".join(read_rel(rel) for rel in (PRESETBAR_REL, PRESETSTABLE_REL, PLUGINSVIEW_REL))
    assert "writes/" in entry_texts, "三个入口文件应从 src/writes/ 引入写流程（CSS 的接线上游）"


def test_transitional_s09_b_entries_still_disabled_actions():
    """B 片（写函数与删除/回滚入口）开工时推翻：B 片的四个入口仍是 DisabledAction——方案表 [删除…]、profile 表
    [删除]、运行时表 [删除…]、历史页 [回滚到这一条之后]（站主决定第一条，A 片不越界）。"""
    need_new_sources()
    pairs = (
        (PRESETSTABLE_REL, 'label="删除…"'),
        (f"{SRC_REL}/pages/readonly1/roles-ProfilesTable.tsx", 'label="删除"'),
        (f"{SRC_REL}/pages/readonly1/runtimes-RuntimesView.tsx", 'label="删除…"'),
        (f"{SRC_REL}/pages/readonly2/history-HistoryView.tsx", "回滚到这一条之后"),
    )
    for rel, marker in pairs:
        text = read_rel(rel)
        assert marker in text, f"{rel} 里应有 {marker}（B 片的入口在 A 片期间不动）"
        assert "DisabledAction" in text, f"{rel} 的 B 片入口应仍是 DisabledAction"
    # 方案表里 [删除…] 仍是 DisabledAction、[使用] 不再是
    table = read_rel(PRESETSTABLE_REL)
    assert re.search(r"<DisabledAction label=\"删除…\"", table), "方案表 [删除…] 应仍是 DisabledAction"
    assert not re.search(r"<DisabledAction label=\"使用\"", table), "方案表 [使用] 应换成可点的 Button"


def test_s10_presetbar_wiring():
    """S10 / D09、第七节：[切换…] 是可点的 Button（primary、md），选中的就是当前方案时是普通禁用 Button；
    不渲染 DisabledAction；说明文字改掉「切换在第二阶段接入」。"""
    need_new_sources()
    text = read_rel(PRESETBAR_REL)
    assert "DisabledAction" not in text, "roles-PresetBar 不许再渲染 DisabledAction（[切换…] 接上写流程）"
    assert "切换…" in text, "[切换…] 的文字应保留"
    assert 'variant="primary"' in text and 'size="md"' in text, "[切换…] 应是 primary、md"
    assert "切换在第二阶段接入" not in text, "说明文字里的「切换在第二阶段接入」应删掉"
    assert "已选" in text, "改选后的说明应是「已选 <方案名>」"


def test_s11_presets_table_use_wired():
    """S11 / D10、第七节：非当前行的 [使用] 换成可点 Button（ghost、sm）；当前行照旧写「当前方案不能删」。"""
    need_new_sources()
    text = read_rel(PRESETSTABLE_REL)
    assert "当前方案不能删" in text, "当前行应照旧写「当前方案不能删」"
    assert "使用" in text, "[使用] 的文字应保留"
    assert not re.search(r"<DisabledAction label=\"使用\"", text), "[使用] 不应再是 DisabledAction"


def test_s12_plugins_actioncell_wiring():
    """S12 / D07、D11、第七节：ActionCell 的按钮换成可点 Button（ghost、sm），保留 span.r2-act 的 stopPropagation。"""
    need_new_sources()
    text = read_rel(PLUGINSVIEW_REL)
    assert "stopPropagation" in text, "ActionCell 应保留 span.r2-act 的 stopPropagation（点按钮不开抽屉）"
    assert "DisabledAction" in text, "插件页仍有别的 DisabledAction（核对全部、重新核对）"
    assert "Button" in text, "插件页的启停按钮应是可点的 Button"
    assert 'variant="ghost"' in text and 'size="sm"', "启停按钮应是 ghost、sm"


def test_s13_no_new_json_no_new_pages_index_untouched():
    """S13 / D15、Repository facts：src/mock 不新增 JSON（仍恰 14 份）、src/pages 顶层不新增页面文件（仍恰 9 个）、
    components/index.ts 不出现 writes/（新组件不进 components/）。"""
    need_new_sources()
    jsons = sorted(p.name for p in (REPO_ROOT / MOCK_REL).glob("*.json"))
    assert len(jsons) == BASELINE_MOCK_JSON_COUNT, f"src/mock 应仍恰 {BASELINE_MOCK_JSON_COUNT} 份 JSON，现在有 {jsons}"
    pages = sorted(p.name for p in (REPO_ROOT / f"{SRC_REL}/pages").glob("*Page.tsx"))
    assert len(pages) == BASELINE_PAGE_COUNT, f"src/pages 顶层应仍恰 {BASELINE_PAGE_COUNT} 个 *Page.tsx，现在有 {pages}"
    index = read_rel(INDEX_TS_REL)
    assert "writes" not in index, "components/index.ts 不应引用 src/writes/（新组件不进 components/）"


def test_s14_executor_test_tokens():
    """S14 / D03–D05、D12–D13：四个执行端测试文件里应出现的记号（映射表、快照排除、轮询上限、对话框细节）。"""
    for name, tokens in EXECUTOR_TEST_TOKENS.items():
        rel = f"{TESTS_REL}/{name}"
        need_file(rel)
        text = read_rel(rel)
        missing = [t for t in tokens if t not in text]
        assert not missing, f"{rel} 里缺少记号 {missing}（合同第 5 步要求的最小覆盖）"


def test_s15_pages_and_views_do_not_call_writes():
    """S15 / 第八节：页面文件与 readonly1 视图不 import 写函数（preview/getOperation/usePreset/setPluginEnabled），
    调写函数的代码只能在 src/writes/。"""
    need_new_sources()
    problems = []
    for rel in (ROLES_PAGE_REL, PLUGINS_PAGE_REL, PRESETBAR_REL, PRESETSTABLE_REL, ROLESVIEW_REL):
        text = read_rel(rel)
        for name in API_NEW_EXPORTS:
            if re.search(rf"\b{name}\b", text):
                problems.append(f"{rel} 出现 {name}（写函数只能从 src/writes/ 调）")
    fail_if(problems, "页面与视图直接调了写函数")


def test_s16_mock_writes_scenarios():
    """S16 / 第二节：mock/writes.ts 收全 19 个情景值。"""
    need_new_sources()
    text = read_rel(f"{MOCK_REL}/writes.ts")
    missing = [v for v in WRITE_SCENARIOS if f"'{v}'" not in text and f'"{v}"' not in text]
    assert not missing, f"mock/writes.ts 缺少情景值 {missing}"


def test_transitional_s17_page_app_write_entry_count():
    """B 片（接上四个删除/回滚入口）开工时推翻：page-app.test.tsx 是共享文件，B 片接上方案表 [删除…]、profile 表
    [删除]×2（角色页 12→9）、运行时页 [删除…]（9→8）后必然改写「写入口个数（过渡）」块，这条断言随之作废。
    S17 / D17（v2 新增）：A 片只改角色页那一个计数——由 13 改成 12（接上方案表 [使用] 之后它不再是禁用按钮；
    [切换…] 在默认选中当前方案时仍是禁用的普通 Button，照旧计入），用例名按 D17 写死成列出所数按钮的写法；
    运行时页 9 与总览 0 不动；该文件其余用例（三页五态、总览指标、点指标卡换到任务页）一个字都不改。"""
    rel = f"{TESTS_REL}/page-app.test.tsx"
    need_file(rel)
    text = read_rel(rel)
    for marker in ("三页五态（经 ?mock=）", "总览指标", "点指标卡换到任务页并保留 mock"):
        assert marker in text, f"{rel} 的其余用例应照旧（缺「{marker}」，D17：一个字都不改）"
    m = re.search(r"describe\(['\"]写入口个数（过渡）['\"]", text)
    assert m, f"{rel} 应保留「写入口个数（过渡）」这条过渡用例"
    rest = text[m.start():]
    nxt = rest.find("describe(", 1)
    block = rest if nxt < 0 else rest[:nxt]
    assert "角色页 13" not in block and "toBe(13)" not in block, \
        "角色页的禁用计数应已从 13 改成 12（接上方案表 [使用] 之后它不再是禁用按钮）"
    for marker in ("角色页 12", "运行时页 9", "总览 0",
                   "保存当前为方案…", "新建 profile", "更改…", "编辑", "删除…", "切换…"):
        assert marker in block, f"「写入口个数（过渡）」的用例名应列出所数的按钮（缺「{marker}」，D17 写死的写法）"
    for num in ("12", "9", "0"):
        assert f"toBe({num})" in block, f"「写入口个数（过渡）」应仍断言 toBe({num})（运行时页 9 与总览 0 不动）"


# ---------------------------------------------------------------------------
# 探针源码（每份自包含：PRELUDE 里的辅助函数不跨文件共享）
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
function maybeButton(root: ParentNode, text: string): HTMLButtonElement | null {
  return (buttons(root).find((b) => textOf(b) === text) as HTMLButtonElement) || null;
}
function confirmDialog(): HTMLElement | null {
  // 写确认框是模态（role=dialog、aria-modal=true）；插件抽屉是 aria-modal=false，不会撞上
  return document.querySelector('[role="dialog"][aria-modal="true"]') as HTMLElement | null;
}
function drawerEl(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="false"]') as HTMLElement | null;
}
function toastEl(): HTMLElement | null {
  return document.querySelector('.tt-toast') as HTMLElement | null;
}
function bodyText(): string {
  return textOf(document.body);
}
function dialogText(): string {
  const d = confirmDialog();
  expect(d, '写确认框应开着').not.toBeNull();
  return textOf(d as HTMLElement);
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
function w3bCheck(where: string) {
  const d = confirmDialog();
  if (d) expect(textOf(d), 'W3b：确认框里不许出现「没有变化」（' + where + '）').not.toContain('没有变化');
}
"""

# 替身 api.ts：默认转调真实现，用 set() 换成任意信封、挂起或受控的延迟（T009 探针同款）
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
function deferred<T = any>(): { promise: Promise<T>; resolve: (v: T) => void } {
  let resolve: any = null;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
function env(data: any, command: string[] = ['gate']): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}
function reply(body: any, status = 200): any {
  return { status, body };
}
"""

# ---------------------------------------------------------------------------
# api 探针：四个写函数的形状与 19 个 ?write= 情景（合同第一、二节）
# ---------------------------------------------------------------------------

PROBE_API = PROBE_PRELUDE + r"""
import * as api from '../src/api';

const READS = ['getMeta', 'getStatus', 'getAttempt', 'readFile', 'getRoles', 'getProfiles', 'getPresets',
  'diffPresets', 'getRuntimes', 'getPlugins', 'getHistory', 'getUsage', 'listSecrets'];
const WRITES = ['preview', 'getOperation', 'usePreset', 'setPluginEnabled'];
const FORBIDDEN = ['removePreset', 'removeProfile', 'removeRuntime', 'rollback',
  'listAttempts', 'getConfig', 'validateConfig', 'getHistoryEntry', 'getPlugin', 'checkSecret', 'subscribeEvents',
  'search', 'startJob', 'getJob', 'cancelJob', 'startSecretEntry', 'setRole', 'savePreset', 'saveProfile', 'addRuntime'];

async function p(action: api.WriteAction, args: Record<string, string>): Promise<any> {
  return (api as any).preview(action, args);
}

describe('T022 api：四个写函数', () => {
  it('导出集合：四个写函数与 13 个读函数都在；B 片与 LATER_API 的名字不在', () => {
    for (const n of WRITES) expect(typeof (api as any)[n], '应导出 ' + n).toBe('function');
    for (const n of READS) expect(typeof (api as any)[n], '读函数 ' + n + ' 应保留').toBe('function');
    for (const n of FORBIDDEN) expect((api as any)[n], '不许导出 ' + n + '（过渡：B 片开工时推翻）').toBeUndefined();
  });

  it('preview 返回 HttpReply<PreviewData>：八键齐全、命令照 README 的预览写法、confirmation 非空', async () => {
    window.location.hash = '#/roles?write=ok';
    const r = await p('preset.use', { name: 'economy' });
    expect(r.status).toBe(200);
    expect(r.body.ok).toBe(true);
    const keys = Object.keys(r.body.data).sort();
    expect(keys).toEqual(['binding_changes', 'command', 'confirmation', 'needs_yes', 'notes',
      'resources', 'running_attempts', 'warnings']);
    const cmd: string[] = r.body.data.command;
    expect(cmd.slice(0, 4)).toEqual(['config', 'preset', 'use', 'economy']);
    expect(cmd).toContain('--dry-run');
    expect(typeof r.body.data.confirmation).toBe('string');
    expect((r.body.data.confirmation as string).length).toBeGreaterThan(0);
    expect(Array.isArray(r.body.data.binding_changes)).toBe(true);
    expect(typeof r.body.data.needs_yes).toBe('boolean');
  });

  it('usePreset / setPluginEnabled 在 ok 情景返回 200 ok；getOperation 八键', async () => {
    window.location.hash = '#/roles?write=ok';
    const pv = await p('preset.use', { name: 'economy' });
    const conf: string = pv.body.data.confirmation;
    const used = await api.usePreset('economy', conf);
    expect(used.status).toBe(200);
    expect(used.body.ok).toBe(true);
    expect(used.body.exit_code).toBe(0);
    const en = await p('plugin.enable', { id: 'code-change' });
    const conf2: string = en.body.data.confirmation;
    const set1 = await api.setPluginEnabled('code-change', true, conf2);
    expect(set1.status).toBe(200);
    expect(set1.body.ok).toBe(true);
    const op = await api.getOperation(conf2);
    const keys = Object.keys(op.body.data).sort();
    expect(keys).toEqual(['action', 'created_ms', 'envelope', 'finished_ms', 'id', 'reason', 'started_ms', 'state']);
  });

  it('预览自己的失败：preview-fail 是 200 ok:false 退出 2；preview-busy 是 503', async () => {
    window.location.hash = '#/roles?write=preview-fail';
    const r = await p('preset.use', { name: 'economy' });
    expect(r.status).toBe(200);
    expect(r.body.ok).toBe(false);
    expect(r.body.exit_code).toBe(2);
    window.location.hash = '#/roles?write=preview-busy';
    const b = await p('preset.use', { name: 'economy' });
    expect(b.status).toBe(503);
  });

  it('执行响应逐行：ok、warn（output 与 messages 各有一行 WARN）、exit1/2/3（ERROR 行）', async () => {
    window.location.hash = '#/roles?write=ok';
    const conf = (await p('preset.use', { name: 'economy' })).body.data.confirmation;
    expect((await api.usePreset('economy', conf)).body.ok).toBe(true);
    window.location.hash = '#/roles?write=warn';
    const w = await api.usePreset('economy', conf);
    expect(w.status).toBe(200);
    expect(w.body.ok).toBe(true);
    expect(w.body.output.some((l: string) => l.startsWith('WARN'))).toBe(true);
    expect(w.body.messages.some((l: string) => l.startsWith('WARN'))).toBe(true);
    for (const [sc, code] of [['exit1', 1], ['exit2', 2], ['exit3', 3]] as const) {
      window.location.hash = '#/roles?write=' + sc;
      const e = await api.usePreset('economy', conf);
      expect(e.status, sc).toBe(200);
      expect(e.body.ok, sc).toBe(false);
      expect(e.body.exit_code, sc).toBe(code);
      expect(e.body.messages.some((l: string) => l.startsWith('ERROR')), sc).toBe(true);
    }
  });

  it('409 的两种：stale 退出 4；expired exit_code 为 null 且 getOperation 404', async () => {
    window.location.hash = '#/roles?write=stale';
    const conf = (await p('preset.use', { name: 'economy' })).body.data.confirmation;
    const s = await api.usePreset('economy', conf);
    expect(s.status).toBe(409);
    expect(s.body.exit_code).toBe(4);
    window.location.hash = '#/roles?write=expired';
    const x = await api.usePreset('economy', conf);
    expect(x.status).toBe(409);
    expect(x.body.exit_code).toBe(null);
    const op = await api.getOperation(conf);
    expect(op.status).toBe(404);
  });

  it('服务端错误：busy 503 且查号 404；closing/spawn/toolarge 500；timeout 504', async () => {
    window.location.hash = '#/roles?write=busy';
    const conf = (await p('preset.use', { name: 'economy' })).body.data.confirmation;
    const b = await api.usePreset('economy', conf);
    expect(b.status).toBe(503);
    expect((await api.getOperation(conf)).status).toBe(404);
    for (const sc of ['closing', 'spawn', 'toolarge']) {
      window.location.hash = '#/roles?write=' + sc;
      const r = await api.usePreset('economy', conf);
      expect(r.status, sc).toBe(sc === 'closing' ? 503 : 500);
      expect(r.body.ok, sc).toBe(false);
    }
    window.location.hash = '#/roles?write=timeout';
    const t = await api.usePreset('economy', conf);
    expect(t.status).toBe(504);
  });

  it('drop-*：执行抛错；getOperation——done 第一次 running 第二次起 succeeded、lost 404、hang 一直 running', async () => {
    window.location.hash = '#/roles?write=drop-done';
    const conf = (await p('preset.use', { name: 'economy' })).body.data.confirmation;
    await expect(api.usePreset('economy', conf)).rejects.toBeTruthy();
    const first = await api.getOperation(conf);
    expect(first.status).toBe(200);
    expect(first.body.data.state).toBe('running');
    const second = await api.getOperation(conf);
    expect(second.body.data.state).toBe('succeeded');
    window.location.hash = '#/roles?write=drop-lost';
    await expect(api.usePreset('economy', conf)).rejects.toBeTruthy();
    expect((await api.getOperation(conf)).status).toBe(404);
    window.location.hash = '#/roles?write=drop-hang';
    await expect(api.usePreset('economy', conf)).rejects.toBeTruthy();
    for (let i = 0; i < 3; i += 1) {
      const op = await api.getOperation(conf);
      expect(op.status).toBe(200);
      expect(op.body.data.state).toBe('running');
    }
  });
});
"""

# ---------------------------------------------------------------------------
# dialog 探针：dismissible 缺省不变；为 false 时关不掉（合同第六节）
# ---------------------------------------------------------------------------

PROBE_DIALOG = PROBE_PRELUDE + r"""
import { Dialog } from '../src/components/Dialog';

function dlg(): HTMLElement {
  const d = document.querySelector('[role="dialog"][aria-modal="true"]') as HTMLElement | null;
  expect(d, '对话框应开着').not.toBeNull();
  return d as HTMLElement;
}
function closeBtn(d: HTMLElement): HTMLButtonElement {
  const b = Array.from(d.querySelectorAll('button')).find((x) => (x.getAttribute('aria-label') || '').includes('关闭'));
  expect(b, '头部应有关闭钮').toBeTruthy();
  return b as HTMLButtonElement;
}

describe('T022 Dialog 的 dismissible', () => {
  it('缺省（不传）：Esc 与头部关闭钮都调 onClose（现有行为一字不变）', async () => {
    const fn = vi.fn();
    render(<Dialog open onClose={fn} title="t">x</Dialog>);
    await settle();
    const d = dlg();
    expect(closeBtn(d).disabled).toBe(false);
    fireEvent.keyDown(d, { key: 'Escape' });
    await settle();
    expect(fn.mock.calls.length).toBe(1);
    fireEvent.click(closeBtn(d));
    await settle();
    expect(fn.mock.calls.length).toBe(2);
  });

  it('dismissible={false}：Esc 不调 onClose；头部关闭钮禁用；点遮罩不关', async () => {
    const fn = vi.fn();
    render(<Dialog open onClose={fn} title="t" dismissible={false}>x</Dialog>);
    await settle();
    const d = dlg();
    fireEvent.keyDown(d, { key: 'Escape' });
    await settle();
    expect(fn.mock.calls.length, 'Esc 不该关掉不能关闭的框').toBe(0);
    expect(confirmDialog(), 'Esc 之后框还在').not.toBeNull();
    const btn = closeBtn(d);
    expect(btn.disabled, '头部关闭钮应禁用').toBe(true);
    const scrim = document.querySelector('.tt-dialog-scrim') as HTMLElement;
    expect(scrim, '应有遮罩').not.toBeNull();
    fireEvent.mouseDown(scrim);
    fireEvent.click(scrim);
    await settle();
    expect(fn.mock.calls.length, '遮罩不关').toBe(0);
    expect(confirmDialog(), '遮罩之后框还在').not.toBeNull();
  });

  it('dismissible={false}：框内 Tab 照旧困在框里（焦点陷阱不变）', async () => {
    const fn = vi.fn();
    render(<Dialog open onClose={fn} title="t" dismissible={false}><button type="button">a</button></Dialog>);
    await settle();
    const d = dlg();
    const inner = Array.from(d.querySelectorAll('button')).find((b) => textOf(b) === 'a') as HTMLElement;
    inner.focus();
    fireEvent.keyDown(d, { key: 'Tab' });
    await settle();
    expect(document.activeElement === inner || d.contains(document.activeElement), '焦点仍在框内').toBe(true);
  });
});
"""

# ---------------------------------------------------------------------------
# entries 探针：三个入口接上、B 片照旧禁用（合同第七节、D06–D11）
# ---------------------------------------------------------------------------

PROBE_ENTRIES = PROBE_PRELUDE + PROBE_API_MOCK + r"""
const hoisted2 = vi.hoisted(() => ({ spies: {} as Record<string, any> }));
vi.mock('../src/pages/readonly2/common-readers', async (importOriginal) => {
  const actual: any = await importOriginal();
  const out: any = { ...actual };
  for (const [name, fn] of Object.entries(actual)) {
    if (typeof fn === 'function') {
      const spy = vi.fn((...args: any[]) => (fn as any)(...args));
      out[name] = spy;
      (hoisted2 as any).spies[name] = spy;
    }
  }
  return out;
});

function rolesRoot(): HTMLElement {
  const el = document.querySelector('[data-page="roles"]');
  expect(el, '应有角色页视图根').not.toBeNull();
  return el as HTMLElement;
}
function radio(name: string): HTMLElement {
  const hit = Array.from(document.querySelectorAll('[role="radio"]')).find((r) => textOf(r) === name);
  expect(hit, '应有方案「' + name + '」的分段选项').toBeTruthy();
  return hit as HTMLElement;
}
function presetRow(name: string): HTMLElement {
  const sec = Array.from(document.querySelectorAll('section')).find((s) => {
    const id = s.getAttribute('aria-labelledby');
    return id && textOf(document.getElementById(id)) === '方案';
  });
  expect(sec, '应有「方案」区块').toBeTruthy();
  const row = Array.from((sec as HTMLElement).querySelectorAll('tbody tr')).find((tr) => textOf(tr.querySelector('td')) === name);
  expect(row, '方案表应有「' + name + '」行').toBeTruthy();
  return row as HTMLElement;
}
async function await_act_advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
async function tipOf(btn: HTMLElement): Promise<string> {
  const wrap = btn.closest('.tt-tooltip-wrap') as HTMLElement;
  expect(wrap, '禁用入口应被 Tooltip 的包裹元素包着').not.toBeNull();
  fireEvent.mouseEnter(wrap);
  await await_act_advance(400);
  const trigger = wrap.firstElementChild as HTMLElement;
  const tipId = trigger.getAttribute('aria-describedby');
  expect(tipId, '悬停 400ms 后触发元素应带 aria-describedby').toBeTruthy();
  const tip = document.getElementById(tipId as string);
  expect(tip, 'aria-describedby 指向的提示应在文档里').not.toBeNull();
  const out = textOf(tip);
  fireEvent.mouseLeave(wrap);
  return out;
}

describe('T022 三个写入口', () => {
  it('方案 [切换…]：选中当前方案时是普通禁用 Button（primary md、无提示包裹）；改选后可点、说明是「已选 economy」', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=ok');
    const r = rolesRoot();
    const cur = buttonByText(r, '切换…');
    expect(cur.disabled, '初值选中当前方案时 [切换…] 禁用').toBe(true);
    expect(cur.getAttribute('data-variant')).toBe('primary');
    expect(cur.getAttribute('data-size')).toBe('md');
    expect(cur.closest('.tt-tooltip-wrap'), '普通禁用 Button 不带提示包裹').toBeNull();
    fireEvent.click(radio('economy'));
    await settle();
    expect(textOf(r), '改选后说明是「已选 economy」').toContain('已选 economy');
    expect(textOf(r)).not.toContain('切换在第二阶段接入');
    const after = buttonByText(r, '切换…');
    expect(after.disabled, '选中的不是当前方案时 [切换…] 可点').toBe(false);
    w3bCheck('角色页改选后');
  });

  it('方案表 [使用]：非当前行可点（ghost、sm），点开确认框标题「使用方案 economy？」；当前行照旧「当前方案不能删」', async () => {
    await mountApp('#/roles?write=ok');
    const cur = presetRow('default');
    expect(textOf(cur)).toContain('当前方案不能删');
    expect(maybeButton(cur, '使用'), '当前行不渲染 [使用]').toBeNull();
    const eco = presetRow('economy');
    const use = buttonByText(eco, '使用');
    expect(use.disabled).toBe(false);
    expect(use.getAttribute('data-variant')).toBe('ghost');
    expect(use.getAttribute('data-size')).toBe('sm');
    fireEvent.click(use);
    await settle();
    expect(dialogText()).toContain('使用方案 economy？');
    expect(dialogText()).toContain('将运行的命令');
    expect(maybeButton(confirmDialog() as HTMLElement, '取消')).not.toBeNull();
    expect(maybeButton(confirmDialog() as HTMLElement, '确认…')).not.toBeNull();
    w3bCheck('方案表 [使用] 打开的确认框');
  });

  it('方案表 [删除…] 仍是带「第二阶段接入」提示的禁用入口（过渡：B 片开工时推翻）', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=ok');
    const del = buttonByText(presetRow('economy'), '删除…');
    expect(del.disabled, '[删除…] 在 A 片仍禁用').toBe(true);
    expect(await tipOf(del), '[删除…] 悬停仍是「第二阶段接入」').toBe('第二阶段接入');
  });

  it('插件 [启用…]/[停用…] 可点（ghost、sm）：点开只弹写确认框——抽屉不开、getPlugin 不被调用', async () => {
    await mountApp('#/plugins?write=ok');
    const enable = buttonByText(document.body, '启用…');
    expect(enable.disabled).toBe(false);
    expect(enable.getAttribute('data-variant')).toBe('ghost');
    expect(enable.getAttribute('data-size')).toBe('sm');
    const disable = buttonByText(document.body, '停用…');
    expect(disable.disabled).toBe(false);
    fireEvent.click(enable);
    await settle();
    expect(dialogText()).toContain('启用插件 code-change？');
    expect(drawerEl(), '插件抽屉不该开').toBeNull();
    const getCalls = ((hoisted2.spies.getPlugin as any) || { mock: { calls: [] } }).mock.calls.length;
    expect(getCalls, 'getPlugin 不该被调用（站主决定第四条）').toBe(0);
    w3bCheck('插件 [启用…] 打开的确认框');
  });

  it('插件页 offline 下 [启用…]/[停用…] 也保持可点；「核对全部」照旧禁用带提示', async () => {
    vi.useFakeTimers();
    await mountApp('#/plugins?mock=offline&write=ok');
    expect(buttonByText(document.body, '启用…').disabled, '断线时也保持可点（D11）').toBe(false);
    expect(buttonByText(document.body, '停用…').disabled).toBe(false);
    const check = buttonByText(document.body, '核对全部');
    expect(check.disabled).toBe(true);
    expect(await tipOf(check)).toBe('第二阶段接入');
  });

  it('方案 [切换…] 走完 ok 流程：确认后关框、弹「已切换到方案 economy」轻提示', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=ok');
    fireEvent.click(radio('economy'));
    await settle();
    fireEvent.click(buttonByText(rolesRoot(), '切换…'));
    await settle();
    expect(dialogText()).toContain('切换到方案 economy？');
    expect(dialogText()).toContain('config preset use economy');
    fireEvent.click(buttonByText(confirmDialog() as HTMLElement, '确认…'));
    await settle();
    await advance(20);
    expect(confirmDialog(), '完成后关框').toBeNull();
    expect(bodyText()).toContain('已切换到方案 economy');
    expect(toastEl(), '轻提示应出现').not.toBeNull();
    w3bCheck('完成之后');
  });
});
"""

# ---------------------------------------------------------------------------
# flow 探针：状态机经真实 ?write= 情景（合同第三、四节；W3、W3b；D04、D05、D12）
# ---------------------------------------------------------------------------

PROBE_FLOW = PROBE_PRELUDE + PROBE_API_MOCK + r"""
function rolesRoot(): HTMLElement {
  const el = document.querySelector('[data-page="roles"]');
  expect(el, '应有角色页视图根').not.toBeNull();
  return el as HTMLElement;
}
function radio(name: string): HTMLElement {
  const hit = Array.from(document.querySelectorAll('[role="radio"]')).find((r) => textOf(r) === name);
  expect(hit, '应有方案「' + name + '」的分段选项').toBeTruthy();
  return hit as HTMLElement;
}
async function openConfirm(hash: string) {
  const r = await mountApp(hash);
  fireEvent.click(radio('economy'));
  await settle();
  fireEvent.click(buttonByText(rolesRoot(), '切换…'));
  await settle();
  dialogText();
  return r;
}
async function confirmNow() {
  fireEvent.click(buttonByText(confirmDialog() as HTMLElement, '确认…'));
  await settle();
  await advance(20);
}

describe('T022 写流程状态机', () => {
  it('预览失败（preview-fail）：按钮 [重新预览] [关闭]，不重读', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=preview-fail');
    await advance(20);
    const t = dialogText();
    expect(maybeButton(confirmDialog() as HTMLElement, '重新预览'), '预览失败应有 [重新预览]').not.toBeNull();
    expect(maybeButton(confirmDialog() as HTMLElement, '关闭')).not.toBeNull();
    expect(t).not.toContain('已切换');
    w3bCheck('预览失败');
  });

  it('预览失败（preview-busy）：提示「服务繁忙，请稍后重试」', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=preview-busy');
    await advance(20);
    expect(dialogText()).toContain('服务繁忙，请稍后重试');
    w3bCheck('preview-busy');
  });

  it('exit3（W3）：整页没有「已切换」没有「成功」，确认框里有「内核拒绝」与 [重新预览] [关闭]', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=exit3');
    await confirmNow();
    expect(toastEl(), 'Toast 区域应是空的（W3）').toBeNull();
    expect(bodyText()).not.toContain('已切换');
    expect(bodyText()).not.toContain('成功');
    expect(dialogText()).toContain('内核拒绝');
    expect(maybeButton(confirmDialog() as HTMLElement, '重新预览')).not.toBeNull();
    expect(maybeButton(confirmDialog() as HTMLElement, '关闭')).not.toBeNull();
    w3bCheck('exit3');
  });

  it('exit1：快照相同 → 失败，原因「内核拒绝」；不弹轻提示', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=exit1');
    await confirmNow();
    expect(toastEl()).toBeNull();
    expect(dialogText()).toContain('内核拒绝');
    expect(bodyText()).not.toContain('已切换');
    w3bCheck('exit1');
  });

  it('warn：不关框，warning 条列出 WARN 行，按钮 [知道了]', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=warn');
    await confirmNow();
    const d = confirmDialog() as HTMLElement;
    expect(d, '有 WARN 时不应直接关框（M17）').not.toBeNull();
    expect(d.querySelector('[data-tone="warning"]'), '应有 warning 条').not.toBeNull();
    expect(textOf(d)).toContain('WARN');
    expect(maybeButton(d, '知道了')).not.toBeNull();
    expect(toastEl(), '完成但有警告不弹轻提示').toBeNull();
    w3bCheck('warn');
  });

  it('stale（409 退出 4）：「配置在你确认之前被改动了，请重新预览」+ [重新预览]，不重读', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=stale');
    await confirmNow();
    expect(dialogText()).toContain('配置在你确认之前被改动了，请重新预览');
    expect(maybeButton(confirmDialog() as HTMLElement, '重新预览')).not.toBeNull();
    expect(toastEl()).toBeNull();
    w3bCheck('stale');
  });

  it('expired（409、exit_code 为 null）：「确认已失效」与 stale 的文案不同（M4）', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=expired');
    await confirmNow();
    const t = dialogText();
    expect(t).toContain('确认已失效');
    expect(t).toContain('请重新预览');
    expect(t).not.toContain('配置在你确认之前被改动了');
    expect(maybeButton(confirmDialog() as HTMLElement, '重新预览')).not.toBeNull();
    w3bCheck('expired');
  });

  it('busy（503 且查不到操作）：回到可确认，提示「服务繁忙，请稍后再确认」', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=busy');
    await confirmNow();
    const t = dialogText();
    expect(t).toContain('服务繁忙，请稍后再确认');
    expect(maybeButton(confirmDialog() as HTMLElement, '确认…'), '回到可确认应有 [确认…]').not.toBeNull();
    expect(toastEl()).toBeNull();
    w3bCheck('busy');
  });

  it('closing（503，查到 failed/closing 终态）：按服务出错重读再分，快照相同 → 失败带「服务出错」', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=closing');
    await confirmNow();
    expect(dialogText()).toContain('服务出错');
    expect(maybeButton(confirmDialog() as HTMLElement, '重新预览')).not.toBeNull();
    expect(toastEl()).toBeNull();
    w3bCheck('closing');
  });

  it('reread-fail（M9）：执行成功但重读失败 →「命令已成功，但重新读取失败，请刷新」+ [关闭]，不弹轻提示', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=reread-fail');
    await confirmNow();
    const t = dialogText();
    expect(t).toContain('命令已成功，但重新读取失败，请刷新');
    expect(maybeButton(confirmDialog() as HTMLElement, '关闭')).not.toBeNull();
    expect(toastEl(), '成功但重读失败不弹轻提示（M9）').toBeNull();
    expect(bodyText()).not.toContain('已切换');
    w3bCheck('reread-fail');
  });

  it('drop-done（M12）：执行抛错 →「连接中断，正在确认结果…」轮询，查到终态后重读完成、弹轻提示', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=drop-done');
    await confirmNow();
    expect(dialogText()).toContain('连接中断，正在确认结果…');
    w3bCheck('drop-done 断线时');
    await advance(1000);
    await advance(1000);
    expect(bodyText(), '轮询到 succeeded 后重读完成').toContain('已切换到方案 economy');
    expect(confirmDialog()).toBeNull();
  });

  it('drop-lost（M13）：404 → 「结果未知，请在历史与审计里核对」+ [打开历史]', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=drop-lost');
    await confirmNow();
    await advance(1500);
    const t = dialogText();
    expect(t).toContain('结果未知，请在历史与审计里核对');
    expect(maybeButton(confirmDialog() as HTMLElement, '打开历史')).not.toBeNull();
    expect(toastEl()).toBeNull();
    w3bCheck('drop-lost');
  });

  it('drop-hang（M10/M11）：119 秒仍在轮询不下结论；121 秒进「结果未知」', async () => {
    vi.useFakeTimers();
    await openConfirm('#/roles?write=drop-hang');
    await confirmNow();
    expect(dialogText()).toContain('连接中断');
    await advance(119000);
    const t = dialogText();
    expect(t, '119 秒仍是 running 时不下结论（M10）').toContain('连接中断');
    expect(t).not.toContain('结果未知');
    await advance(2000);
    expect(dialogText(), '120 秒上限到了进「结果未知」，不是失败（M11）').toContain('结果未知，请在历史与审计里核对');
    expect(dialogText()).not.toContain('内核拒绝');
    w3bCheck('drop-hang');
  });

  it('执行中关不掉（M14–M16）：[取消] 禁用、Esc 与遮罩不关框、头部关闭钮禁用', async () => {
    vi.useFakeTimers();
    const gate = deferred();
    set('usePreset', () => gate.promise);
    await openConfirm('#/roles?write=ok');
    fireEvent.click(buttonByText(confirmDialog() as HTMLElement, '确认…'));
    await settle();
    await advance(20);
    const d = confirmDialog() as HTMLElement;
    expect(d, '执行中框还开着').not.toBeNull();
    expect(buttonByText(d, '取消').disabled, '执行中 [取消] 禁用（M16）').toBe(true);
    fireEvent.keyDown(d, { key: 'Escape' });
    await settle();
    expect(confirmDialog(), '执行中 Esc 不关框（M14）').not.toBeNull();
    const scrim = document.querySelector('.tt-dialog-scrim') as HTMLElement;
    fireEvent.mouseDown(scrim);
    fireEvent.click(scrim);
    await settle();
    expect(confirmDialog(), '执行中遮罩不关框（M15）').not.toBeNull();
    const close = Array.from(d.querySelectorAll('button')).find((b) => (b.getAttribute('aria-label') || '').includes('关闭'));
    expect(close, '头部应有关闭钮').toBeTruthy();
    expect((close as HTMLButtonElement).disabled, '执行中头部关闭钮禁用').toBe(true);
    w3bCheck('执行中');
    gate.resolve(reply(env(null)));
    await settle();
    await advance(20);
    expect(bodyText()).toContain('已切换到方案 economy');
  });

  it('W3 核心：重读卡住时整页没有「已切换」、Toast 区域空；重读兑现后才弹「已切换到方案 economy」（M1）', async () => {
    vi.useFakeTimers();
    const gate = deferred();
    const presets = env({
      active_preset: 'default',
      presets: [
        { name: 'default', description: '日常', roles: ['contract', 'execution', 'planning_review', 'scheduler_agent'], active: true },
        { name: 'economy', description: '省钱', roles: ['execution'], active: false },
      ],
    }, ['config', 'preset', 'show']);
    // 不数调用次数：页面加载（含 hashchange 再加载）与预览阶段的快照读次数不定，全部照常兑现；
    // 打开确认框（预览与快照都已兑现、进入可确认）之后才挂开关，此后第一次 getPresets 就是重读
    // （合同第三节「重读 = 再调一次这个 action 的快照读函数」，preset.use 的快照读函数含 getPresets）。
    // gate.resolve 之后 gate.promise 已兑现，完成后的 reload() 再读也立刻返回，不会卡住。
    let hangReread = false;
    set('getPresets', () => (hangReread ? gate.promise : Promise.resolve(presets)));
    await openConfirm('#/roles?write=ok');
    hangReread = true;
    await confirmNow();
    expect(confirmDialog(), '重读中框还开着').not.toBeNull();
    expect(toastEl(), '重读兑现之前 Toast 区域是空的（W3/M1）').toBeNull();
    expect(bodyText(), '重读兑现之前整页没有「已切换」（W3/M1）').not.toContain('已切换');
    gate.resolve(presets);
    await settle();
    await advance(20);
    expect(bodyText(), '重读兑现之后才说成功').toContain('已切换到方案 economy');
    expect(confirmDialog()).toBeNull();
    w3bCheck('W3 完成之后');
  });
});
"""

# (键, 探针源码, 需要先存在的仓库文件)
PROBE_SPECS = {
    "api": (PROBE_API, (API_REL, f"{MOCK_REL}/writes.ts", f"{WRITES_REL}/writeOutcome.ts")),
    "dialog": (PROBE_DIALOG, (DIALOG_REL, f"{WRITES_REL}/WriteConfirmDialog.tsx")),
    "entries": (PROBE_ENTRIES, (PRESETBAR_REL, PRESETSTABLE_REL, PLUGINSVIEW_REL, f"{MOCK_REL}/writes.ts",
                                f"{WRITES_REL}/useWriteFlow.ts", f"{WRITES_REL}/WriteConfirmDialog.tsx")),
    "flow": (PROBE_FLOW, (PRESETBAR_REL, f"{MOCK_REL}/writes.ts", f"{WRITES_REL}/useWriteFlow.ts",
                          f"{WRITES_REL}/WriteConfirmDialog.tsx")),
}
PROBE_ORDER = ("api", "dialog", "entries", "flow")


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


def build_probe_source(key):
    return PROBE_SPECS[key][0]


# ---------------------------------------------------------------------------
# 会话级夹具：npm 四步 + 探针
# ---------------------------------------------------------------------------

PIPELINE_BUDGET = 560
STEP_CAPS = {
    "npm ci": 200,
    "npm run build": 120,
    "npm test": 220,
    "npm run check:contract": 40,
    "probe": 90,
}


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


# 流水线前后不该变的文件（相对 desktop/web）
WATCHED = ("package.json", "package-lock.json", "index.html", "vite.config.ts", "tsconfig.json",
           "src/styles/tokens.css", "src/styles/fonts.css", "src/styles/base.css", "src/main.tsx", "src/App.tsx", "src/App.css")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not any((REPO_ROOT / rel).is_file() for rel in NEW_SOURCE_FILES):
        pipe.reason = ("候选里还没有 src/mock/writes.ts 与 src/writes/ 的任何源码文件（基线），没有东西可测，未调用 npm；"
                       "候选写出新文件后，流水线才会运行 npm ci、构建、Vitest 和探针")
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
        ci = run_step("npm ci", [npm, "ci"])
        if ci is not None and ci.code == 0:
            run_step("npm run build", [npm, "run", "build"])
            run_step("npm test", [npm, "test"])
            run_step("npm run check:contract", [npm, "run", "check:contract"])
            uid = uuid.uuid4().hex[:12]
            for key in PROBE_ORDER:
                missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                name = f"probe-{uid}-t022-{key}.test.tsx"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                written.append(path)
                path.write_text(build_probe_source(key), encoding="utf-8", newline="\n")
                pipe.probe_files[key] = name
                run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        elif ci is not None:
            pipe.stopped_reason = "npm ci 失败，后续步骤未运行"
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
    """P1 / D14：npm ci、npm run build、npm test、npm run check:contract 都退出 0；npm test 全绿（含执行端四个
    writes-* 测试文件与四份照新行为改过的既有测试，其中 page-app.test.tsx 照 D17 只改计数与用例名）。"""
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    step = pipeline.steps["npm test"]
    out = step.out
    assert re.search(r"Tests\s+(?:.*\|\s*)?\d+ passed", out), f"npm test 输出里没有 'Tests … N passed'：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", out), f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert re.search(r"Test Files\s+\d+ passed", out) and not re.search(r"Test Files\s+.*\bfailed\b", out), \
        f"npm test 的 Test Files 行异常：\n{step.tail}"


def test_d01_d02_probe_api(pipeline):
    """api 探针 / D01、D02：四个写函数的导出集合（B 片与 LATER_API 的名字不在——过渡）、PreviewData 与
    OperationView 的形状、命令照 README 的预览写法、19 个 ?write= 情景的预览/执行/getOperation 三列逐行。"""
    assert_probe_ok(pipeline, "api")


def test_d08_probe_dialog(pipeline):
    """dialog 探针 / D08、D14：dismissible 缺省行为一字不变；为 false 时 Esc、遮罩、头部关闭钮都不关框。"""
    assert_probe_ok(pipeline, "dialog")


def test_d06_d07_d09_d10_d11_probe_entries(pipeline):
    """entries 探针 / D06、D07、D09–D11：[切换…] 可点且 primary md、说明「已选 economy」；[使用] ghost sm、当前行
    「当前方案不能删」；插件 [启用…]/[停用…] 可点、不冒泡（抽屉不开、getPlugin 不被调用）；offline 下也保持可点；
    [核对全部] 照旧禁用带提示；B 片 [删除…] 仍禁用带「第二阶段接入」（过渡）；ok 流程关框弹「已切换到方案 economy」。"""
    assert_probe_ok(pipeline, "entries")


def test_d03_d04_d05_d12_d13_probe_flow(pipeline):
    """flow 探针 / D03–D05、D12、D13、W3、W3b：预览失败的两种、exit3 之后整页没有「已切换」「成功」且 Toast 空、
    exit1 快照相同判失败、warn 不关框列 WARN 行、stale/expired 两种 409 文案不同、busy 回到可确认、closing 按终态
    重读、reread-fail 不弹轻提示、drop-done 轮询到终态、drop-lost 进结果未知、drop-hang 的 119/121 秒、执行中
    Esc/遮罩/[取消]/关闭钮都关不掉、重读卡住时整页没有「已切换」（W3/M1）、确认框任何状态都没有「没有变化」（W3b）。"""
    assert_probe_ok(pipeline, "flow")


def test_p10_worktree_unchanged_by_pipeline(pipeline):
    """P10（守卫）：流水线与探针前后 git status 相同；锁文件与外壳文件摘要不变；gate-probe/ 没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"
    changed = sorted(n for n in WATCHED if pipeline.digests_before.get(n) != pipeline.digests_after.get(n))
    assert not changed, f"流水线改动了不该动的文件：{changed}"
    assert not pipeline.gate_probe_left, "desktop/web/gate-probe/ 在探针结束后没有清掉"
