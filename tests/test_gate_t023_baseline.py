"""T023 战前门禁：桌面端前端「删除与回滚的写入口」（D2 之五，T022 的 B 片）的黑盒基准测试
（合同 t023-desktop-ui-writes-b v1，基线 04f7952——T022 A 片已合入，B 片的四项改动都还不存在）。

被测对象是 ``desktop/web/``：``src/api.ts`` 新增 ``removePreset``/``removeProfile``/``removeRuntime``/``rollback``
四个写函数与 ``WriteAction`` 的四个新成员；``src/mock/writes.ts`` 加第 20 个情景 ``in-use`` 与确认号/参数核对；
``src/writes/snapshots.ts`` 加四个快照投影；``useWriteFlow``/``WriteConfirmDialog`` 支持按 action 拼标题与
``danger`` 确认钮；四个入口（方案表 [删除…]、profile 表 [删除]、运行时 [删除…]、历史抽屉 [回滚到这一条之后]）
接上同一条写流程。成功只在重读之后才说（W3）；确认框里不出现「没有变化」这个子串（W3b）。

基线（04f7952）上 ``api.ts`` 没有四个新函数与四个新 action 成员，``mock/writes.ts`` 没有 ``in-use``，四个入口
仍是 ``DisabledAction``（方案表/profile 表/运行时的 [删除…] 提示「第二阶段接入」，历史抽屉的回滚钮无理由提示），
三个执行端测试文件不存在，所以本文件的失败落在「标记不在」「函数不在」「文件不存在」这类断言上，不是导入、收集
或语法错误：模块级只导入标准库，所有仓库文件的读取都发生在用例函数里；流水线（装依赖之后起 build、Vitest 与
探针）放在 ``pipeline`` 会话级夹具里，候选里 ``api.ts`` 还没有 ``preset.remove`` 标记时不装依赖、不起 Vitest。

结构（编号对应合同 DoD 的 D01–D15；D15 附带的 11 条变异 B1–B11 靠这些断言加执行端的三个 ``writes-*`` 测试文件
抓，战后门禁另出变异清单）：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：api.ts 的四个新写函数与 WriteAction 七成员（D01）；
  mock 的 in-use 与内核原文的位置（D02、D11）；useWriteFlow 的四个新分支、可选 title 与 danger（D03、D04）；
  WriteConfirmDialog 的 danger 三元（D04）；snapshots 至少七个导出投影（D10）；四个入口的接线与 reload 转交
  （D05）；入口文件里不出现标题、轻提示与内核原文（D03、D11/B11）；不新增 JSON 与页面文件、components/index.ts
  不进 writes（D14）；执行端三个测试文件在位、不用 skip/only/todo、带最小覆盖记号（D06–D08）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：npm ci、npm run build、
  npm test、npm run check:contract，再把探针逐份写成 ``gate-probe/probe-<唯一标识>-t023-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除。

探针（Vitest + jsdom，全部自包含）：

- api：四个新写函数的导出集合、预览命令照服务侧基础 argv（``config preset remove <name>`` 等）、三个删除的
  binding_changes 恒空与 rollback 最新一条为空/其余一条演示变化、ok 执行命令带 ``--expect-state=<state>``、
  确认号核对四种错（不存在、action 不符、args 不符、rollback 用错编号）都 409 且 exit_code 为 null（D02/B9）、
  in-use 的三种内核原文逐字与 getOperation failed/exit（D11/B8）、19 个旧情景对四个新 action 照旧抽三行；
- entries：四个入口可点且样式照门禁（方案表/profile 表 ghost sm、运行时 ghost sm、回滚 secondary md 带图标）、
  确认框标题/摘要/命令、方案表点 [删除…] 不调 onDiff（B2）、历史抽屉点回滚钮抽屉仍在且 h2 不变、Esc 只关确认框
  （D12/B2）、本机文件条目禁用提示「本机文件不存快照，不能回滚」（D06/B3）、最新一条可点（D06/B4）、确认框元素
  文字不含「没有变化」（W3b/B4）、[编辑]/[探测]/[运行就绪检查] 照旧禁用提示「第二阶段接入」、offline 下四个入口
  照旧可点；
- flow：[确认…] 五个状态都是 danger、A 片 preset.use 仍是 primary（D04/B1）、W3 重读兑现之前整页没有「已删除」
  （D07/B5）、成功之后行真的消失（D08/B6）、in-use 的失败与内核原文且不弹轻提示（D11/B8）、回滚成功后抽屉仍开
  仍是同一条（D12）、expired 的「确认已失效」（D02）。

合同没有写死、门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：in-use 对 config.rollback
与 A 片 action 的响应照 exit1（合同 §3 只给三个删除的内核原文）；probe 里 danger 按钮的找法是「确认框里唯一
data-variant 为 danger/primary 的按钮」（Footer 的 [确认…] 是唯一着色钮）；「标题/轻提示文字在 src/writes/」的
静态检查按模板原文片段（如「已删除方案」「方案表里去掉」）找，执行端若把字符串拆开拼会在这里红，属合同 §4
「逐字」的合理读法。
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

# B 片不新增源码文件：合同 allowed_new_files 只有三个执行端测试文件
EXECUTOR_TESTS = (
    "writes-remove.test.tsx",
    "writes-rollback.test.tsx",
    "writes-snapshots-b.test.ts",
)

API_REL = f"{SRC_REL}/api.ts"
MOCKWRITES_REL = f"{MOCK_REL}/writes.ts"
USE_WRITE_FLOW_REL = f"{WRITES_REL}/useWriteFlow.ts"
WRITE_DIALOG_REL = f"{WRITES_REL}/WriteConfirmDialog.tsx"
SNAPSHOTS_REL = f"{WRITES_REL}/snapshots.ts"
PRESETSTABLE_REL = f"{SRC_REL}/pages/readonly1/roles-PresetsTable.tsx"
PROFILESTABLE_REL = f"{SRC_REL}/pages/readonly1/roles-ProfilesTable.tsx"
ROLESVIEW_REL = f"{SRC_REL}/pages/readonly1/roles-RolesView.tsx"
RUNTIMESVIEW_REL = f"{SRC_REL}/pages/readonly1/runtimes-RuntimesView.tsx"
RUNTIMESPAGE_REL = f"{SRC_REL}/pages/RuntimesPage.tsx"
HISTORYVIEW_REL = f"{SRC_REL}/pages/readonly2/history-HistoryView.tsx"
HISTORYPAGE_REL = f"{SRC_REL}/pages/HistoryPage.tsx"
ROLES_PAGE_REL = f"{SRC_REL}/pages/RolesPage.tsx"
INDEX_TS_REL = f"{SRC_REL}/components/index.ts"

# 入口文件（readonly1、readonly2 与三个顶层页面）：只许出现按钮标签，不许出现标题、轻提示与内核原文
ENTRY_SCAN_DIRS = (SRC / "pages" / "readonly1", SRC / "pages" / "readonly2")
ENTRY_SCAN_FILES = (ROLES_PAGE_REL, RUNTIMESPAGE_REL, HISTORYPAGE_REL)
# 「删除方案」「删除 profile」「回滚配置」是 T013 的 13 条（T013 自己扫）；这里补 B 片的其余禁字
BAD_ENTRY_FRAGMENTS = (
    "删除方案", "删除 profile", "删除运行时", "回滚配置",
    "已删除", "已回滚",
    "先改这些绑定或方案", "先改或删这些 profile", "config unset active_preset",
)
# 确认框标题、摘要与成功轻提示的文字表必须放在 src/writes/（合同 §4）
WRITES_TEXTS = (
    "已删除方案", "已删除 profile", "已删除运行时", "已回滚到",
    "方案表里去掉", "profile 表里去掉", "已登记表里去掉",
)
# in-use 的内核原文（合同 §5）只许出现在 src/mock/writes.ts 或 src/writes/
KERNEL_TEXT_FRAGMENTS = ("先改这些绑定或方案", "先改或删这些 profile", "先 preset use 别的方案")

# 基线名单：src/mock 恰 14 份 JSON、src/pages 顶层恰 9 个 *Page.tsx（不新增 JSON、不新增页面文件）
BASELINE_MOCK_JSON_COUNT = 14
BASELINE_PAGE_COUNT = 9

API_READS = ("getMeta", "getStatus", "getAttempt", "readFile", "getRoles", "getProfiles", "getPresets",
             "diffPresets", "getRuntimes", "getPlugins", "getHistory", "getUsage", "listSecrets")
API_A_WRITES = ("preview", "getOperation", "usePreset", "setPluginEnabled")
API_B_WRITES = ("removePreset", "removeProfile", "removeRuntime", "rollback")
WRITE_ACTION_MEMBERS = ("preset.use", "plugin.enable", "plugin.disable",
                        "preset.remove", "profile.remove", "runtime.remove", "config.rollback")

NETWORK_WORDS = ("fetch", "XMLHttpRequest", "EventSource", "WebSocket")

# 执行端三个测试文件里应出现的记号（合同第 3、5、7 步与 D06–D08 的最小覆盖证据）
EXECUTOR_TEST_TOKENS = {
    "writes-remove.test.tsx": ("已删除方案", "已删除 profile", "已删除运行时", "danger", "409"),
    "writes-rollback.test.tsx": ("已回滚到", "本机文件不存快照，不能回滚", "danger", "没有变化"),
    "writes-snapshots-b.test.ts": ("description", "source", "command", "credential_env", "adapter", "history"),
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


def writes_texts():
    """src/writes 下所有 ts/tsx 的文本（存在才读，方便基线上给出清晰的失败信息）。"""
    out = {}
    base = REPO_ROOT / WRITES_REL
    if base.is_dir():
        for p in sorted(base.rglob("*")):
            if p.suffix in (".ts", ".tsx") and p.is_file():
                out[p.relative_to(REPO_ROOT).as_posix()] = _read(p)
    return out


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_api_new_writes_and_action_members():
    """S01 / D01：api.ts 新增四个写函数（签名照合同）与 WriteAction 的四个新成员；13 个读函数与 A 片四个写函数保留。"""
    text = read_rel(API_REL)
    for member in WRITE_ACTION_MEMBERS:
        assert f"'{member}'" in text, f"WriteAction 应含成员 '{member}'"
    assert re.search(r"export (?:async )?function removePreset\(\s*name:\s*string,\s*confirmation:\s*string\s*\)", text), \
        "api.ts 应导出 removePreset(name: string, confirmation: string)"
    assert re.search(r"export (?:async )?function removeProfile\(\s*profile:\s*string,\s*confirmation:\s*string\s*\)", text), \
        "api.ts 应导出 removeProfile(profile: string, confirmation: string)"
    assert re.search(r"export (?:async )?function removeRuntime\(\s*runtime:\s*string,\s*confirmation:\s*string\s*\)", text), \
        "api.ts 应导出 removeRuntime(runtime: string, confirmation: string)"
    assert re.search(r"export (?:async )?function rollback\(\s*number:\s*number,\s*confirmation:\s*string\s*\)", text), \
        "api.ts 应导出 rollback(number: number, confirmation: string)"
    for name in API_READS:
        assert re.search(rf"export function {name}\(", text), f"api.ts 的读函数 {name} 应原样保留"
    for name in API_A_WRITES:
        assert re.search(rf"export (?:async )?function {name}\(", text), f"api.ts 的 A 片写函数 {name} 应原样保留"


def test_s02_mock_in_use_and_kernel_texts():
    """S02 / D02、D11：mock/writes.ts 收第 20 个情景 in-use；内核原文只出现在 src/mock/writes.ts 或 src/writes/。"""
    need_file(MOCKWRITES_REL)
    read = read_rel(MOCKWRITES_REL)
    assert "'in-use'" in read, "mock/writes.ts 应有第 20 个情景值 'in-use'"
    pool = dict(writes_texts())
    pool[MOCKWRITES_REL] = read
    for frag in KERNEL_TEXT_FRAGMENTS:
        assert any(frag in t for t in pool.values()), \
            f"内核原文片段「{frag}」应出现在 src/mock/writes.ts 或 src/writes/（合同 §5）"


def test_s03_usewriteflow_new_actions_and_optional_title():
    """S03 / D03、第 4 步：useWriteFlow 认得四个新 action（快照读与执行分派），WriteSpec.title 可选。"""
    need_file(USE_WRITE_FLOW_REL)
    text = read_rel(USE_WRITE_FLOW_REL)
    for member in ("preset.remove", "profile.remove", "runtime.remove", "config.rollback"):
        assert f"'{member}'" in text, f"useWriteFlow 应分支处理 {member}"
    for name in API_B_WRITES:
        assert re.search(rf"\b{name}\b", text), f"useWriteFlow 应调用写函数 {name}"
    assert re.search(r"title\?:", text), "WriteSpec.title 应改成可选（缺省由 titleOf(action, args) 补上）"
    assert "getRuntimes" in text, "config.rollback 的快照读要用 getRuntimes（runtimes 投影）"
    assert "getPlugins" in text, "config.rollback 的快照读要用 getPlugins（plugins 投影）"


def test_s04_dialog_danger_variant():
    """S04 / D04、B1：WriteConfirmDialog 加 danger，Footer 的 [确认…] 用 variant={danger ? 'danger' : 'primary'}。"""
    need_file(WRITE_DIALOG_REL)
    text = read_rel(WRITE_DIALOG_REL)
    assert re.search(r"danger\??:\s*boolean", text), "WriteConfirmDialogProps/FlowRender 应有 danger 标志"
    assert re.search(r"danger\s*\?\s*'danger'\s*:\s*'primary'", text), \
        "Footer 的 [确认…] 应写 variant={danger ? 'danger' : 'primary'}（合同 §4 的做法）"


def test_s05_snapshots_four_new_projections():
    """S05 / D10：snapshots.ts 在 A 片三个导出之外再加四个投影（共至少七个导出函数），sameSnapshot 保留。"""
    need_file(SNAPSHOTS_REL)
    text = read_rel(SNAPSHOTS_REL)
    names = re.findall(r"export function (\w+)", text)
    assert len(names) >= 7, f"snapshots.ts 应有至少 7 个导出投影（A 片 3 个 + B 片 4 个），现在只有 {names}"
    assert "sameSnapshot" in names, "sameSnapshot 应保留（纯函数比较）"


def test_s06_presetstable_delete_wired():
    """S06 / D05、第 5 步：方案表 [删除…] 换成可点 Button（ghost sm）走 preset.remove；当前行照旧「当前方案不能删」。"""
    need_file(PRESETSTABLE_REL)
    text = read_rel(PRESETSTABLE_REL)
    assert "'preset.remove'" in text, "方案表 [删除…] 应 start({action:'preset.remove', args:{name}})"
    assert re.search(r"args:\s*\{\s*name", text), "preset.remove 的 args 键应是 {name}"
    assert "当前方案不能删" in text, "当前行应照旧只写「当前方案不能删」"
    assert not re.search(r'<DisabledAction label="删除…"', text), "[删除…] 不应再是 DisabledAction"
    assert re.search(r'useWriteFlow\(reload\)', text), "PresetsTable 应照旧自调 useWriteFlow(reload)"


def test_s07_profilestable_delete_wired():
    """S07 / D05：profile 表 [删除] 可点（ghost sm）走 profile.remove；加 reload prop。"""
    need_file(PROFILESTABLE_REL)
    text = read_rel(PROFILESTABLE_REL)
    assert "'profile.remove'" in text, "profile 表 [删除] 应走 profile.remove"
    assert re.search(r"args:\s*\{\s*profile", text), "profile.remove 的 args 键应是 {profile}"
    # [编辑] 不再断言是 DisabledAction：T024 接上 profile 编辑（站主按 T024 规划报告 §7.1 退役）
    assert not re.search(r'<DisabledAction label="删除"', text), "[删除] 不应再是 DisabledAction"
    assert re.search(r"reload\?:", text), "ProfilesTableProps 应加 reload? prop"
    assert re.search(r'useWriteFlow\(', text), "ProfilesTable 应自调 useWriteFlow"


def test_s08_runtimesview_delete_wired():
    """S08 / D05：运行时 [删除…] 可点（ghost sm）走 runtime.remove；[探测][模型] 照旧 DisabledAction；加 reload。"""
    need_file(RUNTIMESVIEW_REL)
    text = read_rel(RUNTIMESVIEW_REL)
    assert "'runtime.remove'" in text, "运行时 [删除…] 应走 runtime.remove"
    assert re.search(r"args:\s*\{\s*runtime", text), "runtime.remove 的 args 键应是 {runtime}"
    assert re.search(r'<DisabledAction label="探测"', text), "[探测] 照旧是 DisabledAction"
    assert re.search(r'<DisabledAction label="模型"', text), "[模型] 照旧是 DisabledAction"
    assert not re.search(r'<DisabledAction label="删除…"', text), "[删除…] 不应再是 DisabledAction"
    assert re.search(r"reload\?:", text), "RuntimesViewProps 应加 reload? prop"
    assert re.search(r'useWriteFlow\(', text), "RuntimesView 应自调 useWriteFlow"


def test_s09_historyview_rollback_wired():
    """S09 / D05、D06：历史抽屉回滚钮——非本机文件条目可点（secondary md 带 RotateCcwIcon 16）走 config.rollback；
    本机文件条目是 DisabledAction，reason「本机文件不存快照，不能回滚」。"""
    need_file(HISTORYVIEW_REL)
    text = read_rel(HISTORYVIEW_REL)
    assert "'config.rollback'" in text, "回滚钮应走 config.rollback"
    assert re.search(r'args:\s*\{\s*number', text), "config.rollback 的 args 键应是 {number}"
    assert "本机文件不存快照，不能回滚" in text, "本机文件条目的悬停提示应是「本机文件不存快照，不能回滚」"
    assert 'variant="secondary"' in text and 'size="md"' in text, "回滚钮应保持 secondary、md"
    assert "RotateCcwIcon" in text and re.search(r"RotateCcwIcon width=\{16\} height=\{16\}", text), \
        "回滚钮应带 16px 的 RotateCcwIcon"
    assert re.search(r"reload\?:", text), "HistoryViewProps 应加 reload? prop"
    assert re.search(r'useWriteFlow\(', text), "HistoryView 应自调 useWriteFlow"


def test_s10_reload_transfer():
    """S10 / D05、第 5 步：reload 由 RolesView 转交 ProfilesTable、RuntimesPage 与 HistoryPage 转交视图。"""
    need_file(ROLESVIEW_REL)
    m = re.search(r"<ProfilesTable.*?/>", read_rel(ROLESVIEW_REL), re.S)
    assert m and "reload" in m.group(0), "roles-RolesView 应把 reload 转交给 ProfilesTable"
    for rel in (RUNTIMESPAGE_REL, HISTORYPAGE_REL):
        need_file(rel)
        text = read_rel(rel)
        assert re.search(r"\(data,\s*reload\s*\)", text), f"{rel} 的 children 应改成 (data, reload) => …"
        assert "reload={reload}" in text, f"{rel} 应把 reload 转交给视图"


def test_s11_entry_files_have_no_titles_or_kernel_texts():
    """S11 / D03、D11、B11：入口文件（readonly1、readonly2 与三个页面）里不出现确认框标题、成功轻提示与内核原文
    （按钮标签「删除…」「删除」「回滚到这一条之后」不在禁字之列；这些文字一律由 src/writes/ 按 action 拼）。"""
    need_file(HISTORYVIEW_REL)
    files = {}
    for base in ENTRY_SCAN_DIRS:
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                if p.suffix in (".ts", ".tsx") and p.is_file():
                    files[p.relative_to(REPO_ROOT).as_posix()] = _read(p)
    for rel in ENTRY_SCAN_FILES:
        need_file(rel)
        files[rel] = read_rel(rel)
    problems = []
    for rel, text in files.items():
        for frag in BAD_ENTRY_FRAGMENTS:
            if frag in text:
                problems.append(f"{rel} 出现「{frag}」（标题/轻提示/内核原文只能写在 src/writes/ 或 src/mock/）")
    fail_if(problems, "入口文件里出现了不该出现的文字")


def test_s12_writes_texts_live_in_writes():
    """S12 / D03：四个新 action 的标题、摘要与成功轻提示的文字表放在 src/writes/（按模板原文片段找）。"""
    need_file(USE_WRITE_FLOW_REL)
    pool = writes_texts()
    assert pool, "src/writes/ 应存在且有自己的文件"
    missing = [t for t in WRITES_TEXTS if not any(t in text for text in pool.values())]
    assert not missing, f"src/writes/ 里应出现文字表片段 {missing}（合同 §4 的逐字表）"


def test_s13_no_new_json_no_new_pages_index_untouched():
    """S13 / D14、Repository facts：src/mock 不新增 JSON（仍恰 14 份）、src/pages 顶层不新增页面文件（仍恰 9 个）、
    components/index.ts 不出现 writes/。"""
    need_file(MOCKWRITES_REL)
    jsons = sorted(p.name for p in (REPO_ROOT / MOCK_REL).glob("*.json"))
    assert len(jsons) == BASELINE_MOCK_JSON_COUNT, f"src/mock 应仍恰 {BASELINE_MOCK_JSON_COUNT} 份 JSON，现在有 {jsons}"
    pages = sorted(p.name for p in (REPO_ROOT / f"{SRC_REL}/pages").glob("*Page.tsx"))
    assert len(pages) == BASELINE_PAGE_COUNT, f"src/pages 顶层应仍恰 {BASELINE_PAGE_COUNT} 个 *Page.tsx，现在有 {pages}"
    index = read_rel(INDEX_TS_REL)
    assert "writes" not in index, "components/index.ts 不应引用 src/writes/"


def test_s14_executor_test_files_present_and_tokens():
    """S14 / D06–D08、第 7 步：三个执行端测试文件都在，不用 skip/only/todo，且带最小覆盖记号。"""
    for name in EXECUTOR_TESTS:
        rel = f"{TESTS_REL}/{name}"
        need_file(rel)
        text = read_rel(rel)
        bad = [pat for pat in (r"\.skip\s*\(", r"\.only\s*\(", r"\.todo\s*\(", r"\bxit\s*\(", r"\bdescribe\.only")
               if re.search(pat, text)]
        assert not bad, f"{rel} 里出现了 {bad}（不删用例、不削弱断言）"
        missing = [t for t in EXECUTOR_TEST_TOKENS[name] if t not in text]
        assert not missing, f"{rel} 里缺少记号 {missing}（合同要求的最小覆盖）"


def test_s15_no_network_words_in_src():
    """S15 / 非目标：src 下任何文字（注释也算）不出现 fetch、XMLHttpRequest、EventSource、WebSocket。"""
    problems = []
    for path in sorted(SRC.rglob("*")):
        if not path.is_file() or path.suffix not in (".ts", ".tsx", ".css", ".json"):
            continue
        text = _read(path)
        for word in NETWORK_WORDS:
            if re.search(rf"\b{word}\b", text):
                problems.append(f"{path.relative_to(REPO_ROOT)} 出现 {word}")
    fail_if(problems, "src 下出现了联网词（合同非目标：不做真正的网络客户端）")


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
  // 写确认框是模态（role=dialog、aria-modal=true）；历史抽屉是 aria-modal=false，不会撞上
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

# 替身 api.ts：默认转调真实现，用 set() 换成任意信封、挂起或受控的延迟（T022 探针同款）
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
function spyCalls(name: string): number {
  const s = (hoisted.spies as any)[name];
  return s ? s.mock.calls.length : 0;
}
"""

# ---------------------------------------------------------------------------
# api 探针：四个新写函数的形状、确认号核对与 in-use（合同第一、二、三、五节）
# ---------------------------------------------------------------------------

PROBE_API = PROBE_PRELUDE + r"""
import * as api from '../src/api';

const READS = ['getMeta', 'getStatus', 'getAttempt', 'readFile', 'getRoles', 'getProfiles', 'getPresets',
  'diffPresets', 'getRuntimes', 'getPlugins', 'getHistory', 'getUsage', 'listSecrets'];
const WRITES_OLD = ['preview', 'getOperation', 'usePreset', 'setPluginEnabled'];
const WRITES_NEW = ['removePreset', 'removeProfile', 'removeRuntime', 'rollback'];
const FORBIDDEN = [
  'listAttempts', 'getConfig', 'validateConfig', 'getHistoryEntry', 'getPlugin', 'checkSecret', 'subscribeEvents',
  'search', 'startJob', 'getJob', 'cancelJob', 'startSecretEntry', 'setRole', 'savePreset', 'saveProfile', 'addRuntime'];

async function p(action: string, args: Record<string, string>): Promise<any> {
  return (api as any).preview(action, args);
}

describe('T023 api：四个新写函数', () => {
  it('导出集合：四个新写函数与既有读写的名字都在；LATER_API 的名字不在', () => {
    for (const n of WRITES_NEW) expect(typeof (api as any)[n], '应导出 ' + n).toBe('function');
    for (const n of WRITES_OLD) expect(typeof (api as any)[n], 'A 片写函数 ' + n + ' 应保留').toBe('function');
    for (const n of READS) expect(typeof (api as any)[n], '读函数 ' + n + ' 应保留').toBe('function');
    for (const n of FORBIDDEN) expect((api as any)[n], '不许导出 ' + n + '（LATER_API 的名字）').toBeUndefined();
  });

  it('preview 的命令照服务侧基础 argv：四个 action 各自带对的对象与编号；确认号 43 位', async () => {
    window.location.hash = '#/roles?write=ok';
    const pr = await p('preset.remove', { name: 'economy' });
    expect(pr.status).toBe(200);
    expect(pr.body.ok).toBe(true);
    expect(pr.body.data.command).toEqual(['config', 'preset', 'remove', 'economy', '--dry-run', '--json']);
    const pf = await p('profile.remove', { profile: 'step-low' });
    expect(pf.body.data.command).toEqual(['config', 'profile', 'remove', 'step-low', '--dry-run', '--json']);
    const rt = await p('runtime.remove', { runtime: 'pi' });
    expect(rt.body.data.command).toEqual(['config', 'runtime', 'remove', 'pi', '--dry-run', '--json']);
    const rb = await p('config.rollback', { number: '42' });
    expect(rb.body.data.command).toEqual(['config', 'rollback', '42', '--dry-run', '--json']);
    for (const r of [pr, pf, rt, rb]) {
      expect((r.body.data.confirmation as string).length, '确认号应 43 位').toBe(43);
      expect(Array.isArray(r.body.data.binding_changes)).toBe(true);
    }
  });

  it('三个删除的 binding_changes 恒为空；rollback 最新一条（#42）为空、其余给一条演示变化', async () => {
    window.location.hash = '#/roles?write=ok';
    for (const [a, args] of [
      ['preset.remove', { name: 'economy' }],
      ['profile.remove', { profile: 'step-low' }],
      ['runtime.remove', { runtime: 'pi' }],
    ] as const) {
      expect((await p(a, args as any)).body.data.binding_changes, a).toEqual([]);
    }
    expect((await p('config.rollback', { number: '42' })).body.data.binding_changes).toEqual([]);
    const other = (await p('config.rollback', { number: '40' })).body.data.binding_changes;
    expect(other.length).toBe(1);
    expect(other[0].role).toBe('execution');
    expect(other[0].from).toBe('step-low');
    expect(other[0].to).toBe('step-high');
  });

  it('ok 情景执行：200 ok、退出 0，命令是基础 argv 加 --expect-state=<state>', async () => {
    window.location.hash = '#/roles?write=ok';
    const conf = (await p('preset.remove', { name: 'economy' })).body.data.confirmation;
    const r = await api.removePreset('economy', conf);
    expect(r.status).toBe(200);
    expect(r.body.ok).toBe(true);
    expect(r.body.exit_code).toBe(0);
    expect(r.body.command).toEqual(['config', 'preset', 'remove', 'economy', '--expect-state=<state>']);
    const conf2 = (await p('config.rollback', { number: '42' })).body.data.confirmation;
    const rb = await api.rollback(42, conf2);
    expect(rb.status).toBe(200);
    expect(rb.body.ok).toBe(true);
    expect(rb.body.command).toEqual(['config', 'rollback', '42', '--expect-state=<state>']);
  });

  it('确认号核对：号不存在、action 不符、args 不符（删错对象、rollback 用错编号）都 409 且 exit_code 为 null', async () => {
    window.location.hash = '#/roles?write=ok';
    const ghost = await api.removePreset('economy', 'x'.repeat(43));
    expect(ghost.status).toBe(409);
    expect(ghost.body.exit_code).toBe(null);
    expect(ghost.body.messages).toEqual(['ERROR 确认号无效、已过期或已用过：请重新预览']);
    const c1 = (await p('preset.remove', { name: 'economy' })).body.data.confirmation;
    const wrongObj = await api.removePreset('default', c1);
    expect(wrongObj.status).toBe(409);
    expect(wrongObj.body.exit_code).toBe(null);
    const c2 = (await p('profile.remove', { profile: 'step-low' })).body.data.confirmation;
    const wrongObj2 = await api.removeProfile('step-high', c2);
    expect(wrongObj2.status).toBe(409);
    const wrongAct = await api.removeRuntime('pi', c2);
    expect(wrongAct.status).toBe(409);
    expect(wrongAct.body.exit_code).toBe(null);
    const c3 = (await p('config.rollback', { number: '42' })).body.data.confirmation;
    const wrongNum = await api.rollback(40, c3);
    expect(wrongNum.status).toBe(409);
    expect(wrongNum.body.exit_code).toBe(null);
    const right = await api.rollback(42, c3);
    expect(right.status).toBe(200);
    expect(right.body.ok).toBe(true);
  });

  it('in-use：三种内核原文逐字、退出 1；getOperation 是 failed/exit', async () => {
    window.location.hash = '#/roles?write=in-use';
    const pv = await p('profile.remove', { profile: 'step-low' });
    expect(pv.status).toBe(200);
    expect(pv.body.ok).toBe(true);
    const conf = pv.body.data.confirmation;
    const r = await api.removeProfile('step-low', conf);
    expect(r.status).toBe(200);
    expect(r.body.ok).toBe(false);
    expect(r.body.exit_code).toBe(1);
    expect(r.body.messages).toEqual(['ERROR: profile step-low 被 roles.execution 引用：先改这些绑定或方案']);
    const rt = await api.removeRuntime('pi', (await p('runtime.remove', { runtime: 'pi' })).body.data.confirmation);
    expect(rt.body.exit_code).toBe(1);
    expect(rt.body.messages).toEqual(['ERROR: runtime pi 被 profile step-high、step-low 引用：先改或删这些 profile']);
    const ps = await api.removePreset('economy', (await p('preset.remove', { name: 'economy' })).body.data.confirmation);
    expect(ps.body.exit_code).toBe(1);
    expect(ps.body.messages).toEqual(['ERROR: 方案 economy 正在用：先 preset use 别的方案，或 config unset active_preset']);
    const op = await api.getOperation(conf);
    expect(op.status).toBe(200);
    expect(op.body.data.state).toBe('failed');
    expect(op.body.data.reason).toBe('exit');
  });

  it('in-use 对 rollback 与 A 片 action 照 exit1：200 ok:false、退出 1、带 ERROR 行', async () => {
    window.location.hash = '#/roles?write=in-use';
    const rb = await api.rollback(42, (await p('config.rollback', { number: '42' })).body.data.confirmation);
    expect(rb.status).toBe(200);
    expect(rb.body.ok).toBe(false);
    expect(rb.body.exit_code).toBe(1);
    expect(rb.body.messages.some((l: string) => l.startsWith('ERROR'))).toBe(true);
    const used = await api.usePreset('economy', (await p('preset.use', { name: 'economy' })).body.data.confirmation);
    expect(used.body.ok).toBe(false);
    expect(used.body.exit_code).toBe(1);
  });

  it('19 个旧情景对四个新 action 照旧（抽 exit1、expired、drop-done 三行）', async () => {
    window.location.hash = '#/roles?write=exit1';
    const e1 = await api.removeProfile('step-low', (await p('profile.remove', { profile: 'step-low' })).body.data.confirmation);
    expect(e1.status).toBe(200);
    expect(e1.body.exit_code).toBe(1);
    window.location.hash = '#/roles?write=expired';
    const ex = await api.removeRuntime('pi', (await p('runtime.remove', { runtime: 'pi' })).body.data.confirmation);
    expect(ex.status).toBe(409);
    expect(ex.body.exit_code).toBe(null);
    window.location.hash = '#/roles?write=drop-done';
    await expect(api.rollback(42, (await p('config.rollback', { number: '42' })).body.data.confirmation)).rejects.toBeTruthy();
  });
});
"""

# ---------------------------------------------------------------------------
# entries 探针：四个入口接上（合同第四节、第七节；D05、D06、W3b）
# ---------------------------------------------------------------------------

PROBE_ENTRIES = PROBE_PRELUDE + PROBE_API_MOCK + r"""
function sectionByTitle(title: string): HTMLElement {
  const sec = Array.from(document.querySelectorAll('section')).find((s) => {
    const id = s.getAttribute('aria-labelledby');
    return id && textOf(document.getElementById(id)) === title;
  });
  expect(sec, '应有「' + title + '」区块').toBeTruthy();
  return sec as HTMLElement;
}
function rowIn(sec: HTMLElement, firstCell: string): HTMLElement {
  const row = Array.from(sec.querySelectorAll('tbody tr')).find((tr) => textOf(tr.querySelector('td')) === firstCell);
  expect(row, '表里应有「' + firstCell + '」行').toBeTruthy();
  return row as HTMLElement;
}
function runtimeRows(): HTMLElement[] {
  const table = document.querySelector('table[aria-label="已登记的 runtime"]');
  expect(table, '应有已登记表').toBeTruthy();
  return Array.from((table as HTMLElement).querySelectorAll('tbody tr')) as HTMLElement[];
}
async function openHistoryRow(n: number): Promise<HTMLElement> {
  const table = document.querySelector('table[aria-label="配置历史"]');
  expect(table, '应有历史表').toBeTruthy();
  const row = Array.from((table as HTMLElement).querySelectorAll('tbody tr'))
    .find((r) => textOf(r.querySelector('td')) === '#' + n) as HTMLElement;
  expect(row, '历史表应有 #' + n + ' 行').toBeTruthy();
  row.focus();
  fireEvent.keyDown(row, { key: 'Enter' });
  await settle();
  const d = drawerEl();
  expect(d, '抽屉应开着').not.toBeNull();
  return d as HTMLElement;
}
function drawerH2(): string {
  const d = drawerEl();
  expect(d, '抽屉应开着').not.toBeNull();
  return textOf((d as HTMLElement).querySelector('h2'));
}
function rollbackBtn(): HTMLButtonElement {
  const d = drawerEl() as HTMLElement;
  expect(d, '抽屉应开着').not.toBeNull();
  const b = Array.from(d.querySelectorAll('button')).find((x) => textOf(x) === '回滚到这一条之后');
  expect(b, '抽屉底栏应有回滚钮').toBeTruthy();
  return b as HTMLButtonElement;
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

describe('T023 四个写入口', () => {
  it('方案表 [删除…]：当前行照旧「当前方案不能删」，economy 行可点（ghost sm）；标题与摘要由 writes 拼；不触发差异读取', async () => {
    await mountApp('#/roles?write=ok');
    const cur = rowIn(sectionByTitle('方案'), 'default');
    expect(textOf(cur)).toContain('当前方案不能删');
    expect(maybeButton(cur, '删除…'), '当前行不渲染 [删除…]').toBeNull();
    const eco = rowIn(sectionByTitle('方案'), 'economy');
    const del = buttonByText(eco, '删除…');
    expect(del.disabled).toBe(false);
    expect(del.getAttribute('data-variant')).toBe('ghost');
    expect(del.getAttribute('data-size')).toBe('sm');
    fireEvent.click(del);
    await settle();
    const t = dialogText();
    expect(t).toContain('删除方案 economy？');
    expect(t).toContain('方案表里去掉 economy，角色绑定不变');
    expect(t).toContain('config preset remove economy');
    expect(t).not.toContain('--dry-run');
    expect(spyCalls('diffPresets'), '点 [删除…] 不该调 onDiff（diffPresets）').toBe(0);
    w3bCheck('方案表 [删除…] 打开的确认框');
  });

  it('profile 表 [删除] 可点（ghost sm），标题与摘要', async () => {
    await mountApp('#/roles?write=ok');
    const row = rowIn(sectionByTitle('profile'), 'step-low');
    // [编辑] 不再断言禁用与悬停提示：T024 接上 profile 编辑（站主按 T024 规划报告 §7.1 退役）
    const del = buttonByText(row, '删除');
    expect(del.disabled).toBe(false);
    expect(del.getAttribute('data-variant')).toBe('ghost');
    expect(del.getAttribute('data-size')).toBe('sm');
    fireEvent.click(del);
    await settle();
    const t = dialogText();
    expect(t).toContain('删除 profile step-low？');
    expect(t).toContain('profile 表里去掉 step-low');
    expect(t).toContain('config profile remove step-low');
    w3bCheck('profile [删除] 打开的确认框');
  });

  it('运行时 [删除…] 三行都可点（ghost sm），行内其余按钮禁用；标题与摘要', async () => {
    await mountApp('#/runtimes?write=ok');
    const rows = runtimeRows();
    expect(rows.length).toBe(3);
    for (const row of rows) {
      const del = buttonByText(row, '删除…');
      expect(del.disabled, '每行 [删除…] 都可点').toBe(false);
      expect(del.getAttribute('data-variant')).toBe('ghost');
      expect(del.getAttribute('data-size')).toBe('sm');
      for (const b of buttons(row)) {
        if (textOf(b) !== '删除…') expect(b.disabled, '非 [删除…] 的行内按钮仍禁用（' + textOf(b) + '）').toBe(true);
      }
    }
    fireEvent.click(buttonByText(rows[2], '删除…'));
    await settle();
    const t = dialogText();
    expect(t).toContain('删除运行时 opencode？');
    expect(t).toContain('已登记表里去掉 opencode；本机文件里登记的命令一并删去');
    expect(t).toContain('config runtime remove opencode');
    w3bCheck('运行时 [删除…] 打开的确认框');
  });

  it('[运行就绪检查] 照旧禁用，悬停提示「第二阶段接入」', async () => {
    await mountApp('#/runtimes?write=ok');
    const ready = buttonByText(document.body, '运行就绪检查');
    expect(ready.disabled).toBe(true);
    vi.useFakeTimers();
    expect(await tipOf(ready)).toBe('第二阶段接入');
  });

  it('历史抽屉 #42（最新一条）：回滚钮可点（secondary md 带图标）；点开确认框，变化区「预览没有列出变化」；'
     + '抽屉仍在、标题不变；Esc 只关确认框', async () => {
    await mountApp('#/history?write=ok');
    const d = await openHistoryRow(42);
    expect(textOf(d), '抽屉底栏说明照旧（T010 钉着）').toContain('这是最新的一条，回滚后没有变化');
    const rb = rollbackBtn();
    expect(rb.disabled, '最新一条的回滚钮必须可点').toBe(false);
    expect(rb.getAttribute('data-variant')).toBe('secondary');
    expect(rb.getAttribute('data-size')).toBe('md');
    expect(rb.querySelector('svg'), '回滚钮应带图标').not.toBeNull();
    fireEvent.click(rb);
    await settle();
    const t = dialogText();
    expect(t).toContain('回滚到 #42 之后？');
    expect(t).toContain('config rollback 42');
    expect(t).toContain('预览没有列出变化');
    expect(t, 'W3b：确认框元素文字不含「没有变化」').not.toContain('没有变化');
    expect(drawerEl(), '确认框开着时抽屉仍在').not.toBeNull();
    expect(drawerH2()).toBe('#42 · preset.use default');
    fireEvent.keyDown(confirmDialog() as HTMLElement, { key: 'Escape' });
    await settle();
    expect(confirmDialog(), 'Esc 只关确认框').toBeNull();
    expect(drawerEl(), '抽屉不该被 Esc 关掉').not.toBeNull();
  });

  it('历史抽屉 #40：回滚钮可点，变化区给一条演示变化', async () => {
    await mountApp('#/history?write=ok');
    await openHistoryRow(40);
    const rb = rollbackBtn();
    expect(rb.disabled).toBe(false);
    fireEvent.click(rb);
    await settle();
    const t = dialogText();
    expect(t).toContain('回滚到 #40 之后？');
    expect(t).toContain('config rollback 40');
    expect(t).toContain('execution');
    expect(t).toContain('step-low');
    expect(t).toContain('step-high');
    w3bCheck('#40 回滚确认框');
  });

  it('本机文件条目 #41：回滚钮禁用，悬停提示「本机文件不存快照，不能回滚」', async () => {
    await mountApp('#/history?write=ok');
    await openHistoryRow(41);
    const rb = rollbackBtn();
    expect(rb.disabled, '本机文件条目不能回滚').toBe(true);
    vi.useFakeTimers();
    expect(await tipOf(rb)).toBe('本机文件不存快照，不能回滚');
  });

  it('offline 下四个入口照旧可点', async () => {
    await mountApp('#/roles?mock=offline&write=ok');
    expect(buttonByText(rowIn(sectionByTitle('方案'), 'economy'), '删除…').disabled).toBe(false);
    expect(buttonByText(rowIn(sectionByTitle('profile'), 'step-low'), '删除').disabled).toBe(false);
    cleanup();
    await mountApp('#/runtimes?mock=offline&write=ok');
    expect(buttonByText(runtimeRows()[0], '删除…').disabled).toBe(false);
    cleanup();
    await mountApp('#/history?mock=offline&write=ok');
    await openHistoryRow(42);
    expect(rollbackBtn().disabled).toBe(false);
  });
});
"""

# ---------------------------------------------------------------------------
# flow 探针：新 action 的确认流程（合同第三、四、七节；D04、D07–D09、D11、D12；W3、W3b）
# ---------------------------------------------------------------------------

PROBE_FLOW = PROBE_PRELUDE + PROBE_API_MOCK + r"""
function sectionByTitle(title: string): HTMLElement {
  const sec = Array.from(document.querySelectorAll('section')).find((s) => {
    const id = s.getAttribute('aria-labelledby');
    return id && textOf(document.getElementById(id)) === title;
  });
  expect(sec, '应有「' + title + '」区块').toBeTruthy();
  return sec as HTMLElement;
}
function rowIn(sec: HTMLElement, firstCell: string): HTMLElement {
  const row = Array.from(sec.querySelectorAll('tbody tr')).find((tr) => textOf(tr.querySelector('td')) === firstCell);
  expect(row, '表里应有「' + firstCell + '」行').toBeTruthy();
  return row as HTMLElement;
}
function runtimeRows(): HTMLElement[] {
  const table = document.querySelector('table[aria-label="已登记的 runtime"]');
  expect(table, '应有已登记表').toBeTruthy();
  return Array.from((table as HTMLElement).querySelectorAll('tbody tr')) as HTMLElement[];
}
async function openHistoryRow(n: number): Promise<HTMLElement> {
  const table = document.querySelector('table[aria-label="配置历史"]');
  const row = Array.from((table as HTMLElement).querySelectorAll('tbody tr'))
    .find((r) => textOf(r.querySelector('td')) === '#' + n) as HTMLElement;
  expect(row, '历史表应有 #' + n + ' 行').toBeTruthy();
  row.focus();
  fireEvent.keyDown(row, { key: 'Enter' });
  await settle();
  const d = drawerEl();
  expect(d, '抽屉应开着').not.toBeNull();
  return d as HTMLElement;
}
function rollbackBtn(): HTMLButtonElement {
  const d = drawerEl() as HTMLElement;
  expect(d, '抽屉应开着').not.toBeNull();
  const b = Array.from(d.querySelectorAll('button')).find((x) => textOf(x) === '回滚到这一条之后');
  expect(b, '抽屉底栏应有回滚钮').toBeTruthy();
  return b as HTMLButtonElement;
}
function drawerH2(): string {
  const d = drawerEl();
  expect(d, '抽屉应开着').not.toBeNull();
  return textOf((d as HTMLElement).querySelector('h2'));
}
function accentBtn(d: HTMLElement): HTMLButtonElement {
  // Footer 的 [确认…] 是确认框里唯一 data-variant 为 danger/primary 的按钮
  const b = Array.from(d.querySelectorAll('button')).find(
    (x) => x.getAttribute('data-variant') === 'danger' || x.getAttribute('data-variant') === 'primary');
  expect(b, '确认框底栏应有 danger/primary 的确认钮').toBeTruthy();
  return b as HTMLButtonElement;
}
async function confirmNow() {
  fireEvent.click(buttonByText(confirmDialog() as HTMLElement, '确认…'));
  await settle();
  await advance(20);
}
const PROFILES_FULL = [
  { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview',
    options: { thinking: 'high' }, credential_env: ['STEP_API_KEY'] },
  { id: 'step-low', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini',
    options: { thinking: 'low' }, credential_env: ['STEP_API_KEY'] },
];
const PRESETS_FULL = { active_preset: 'default', presets: [
  { name: 'default', description: 'd', roles: ['contract', 'execution', 'planning_review', 'scheduler_agent'], active: true },
  { name: 'economy', description: 'e', roles: ['execution'], active: false },
]};
const RUNTIMES_FULL = [
  { id: 'pi', adapter: 'pi', source: 'local', command: ['a'], notes: [] },
  { id: 'claude-code', adapter: 'claude-code', source: 'path', command: ['b'], notes: [] },
  { id: 'opencode', adapter: 'opencode', source: 'missing', command: null, notes: [] },
];

describe('T023 删除与回滚的确认流程', () => {
  it('预览中：[确认…] 禁用且已是 danger，可以 [取消]', async () => {
    vi.useFakeTimers();
    const gate = deferred();
    set('preview', () => gate.promise);
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(rowIn(sectionByTitle('profile'), 'step-low'), '删除'));
    await settle();
    await advance(20);
    const b = accentBtn(confirmDialog() as HTMLElement);
    expect(b.getAttribute('data-variant'), '预览中也是 danger（D04：五个状态）').toBe('danger');
    expect(b.disabled).toBe(true);
    fireEvent.click(buttonByText(confirmDialog() as HTMLElement, '取消'));
    await settle();
    expect(confirmDialog()).toBeNull();
  });

  it('可确认 → 执行中 → 重读中：[确认…] 都是 danger；完成后弹「已删除 profile step-low」并关框', async () => {
    vi.useFakeTimers();
    const gateExec = deferred();
    const gateRe = deferred();
    const data = env({ profiles: PROFILES_FULL }, ['config', 'profile', 'show']);
    let hang = false;
    set('getProfiles', () => (hang ? gateRe.promise : Promise.resolve(data)));
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(rowIn(sectionByTitle('profile'), 'step-low'), '删除'));
    await settle();
    expect(accentBtn(confirmDialog() as HTMLElement).getAttribute('data-variant'), '可确认时 danger').toBe('danger');
    set('removeProfile', () => gateExec.promise);
    fireEvent.click(buttonByText(confirmDialog() as HTMLElement, '确认…'));
    await settle();
    await advance(20);
    expect(dialogText()).toContain('执行中');
    expect(accentBtn(confirmDialog() as HTMLElement).getAttribute('data-variant'), '执行中 danger').toBe('danger');
    hang = true;
    gateExec.resolve(reply(env(null)));
    await settle();
    await advance(20);
    expect(dialogText()).toContain('重读中');
    expect(accentBtn(confirmDialog() as HTMLElement).getAttribute('data-variant'), '重读中 danger').toBe('danger');
    gateRe.resolve(data);
    await settle();
    await advance(20);
    expect(bodyText()).toContain('已删除 profile step-low');
    expect(confirmDialog()).toBeNull();
  });

  it('确认结果中（drop-done 断线轮询）：[确认…] 也是 danger', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=drop-done');
    fireEvent.click(buttonByText(rowIn(sectionByTitle('profile'), 'step-low'), '删除'));
    await settle();
    await confirmNow();
    expect(dialogText()).toContain('连接中断，正在确认结果…');
    expect(accentBtn(confirmDialog() as HTMLElement).getAttribute('data-variant'), '确认结果中 danger').toBe('danger');
    await advance(1000);
    await advance(1000);
    expect(bodyText(), '轮询到终态后重读完成').toContain('已删除 profile step-low');
  });

  it('A 片 preset.use 的 [确认…] 仍是 primary', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(rowIn(sectionByTitle('方案'), 'economy'), '使用'));
    await settle();
    expect(dialogText()).toContain('使用方案 economy？');
    expect(accentBtn(confirmDialog() as HTMLElement).getAttribute('data-variant'), 'A 片照旧 primary').toBe('primary');
  });

  it('W3：重读兑现之前整页没有「已删除 profile」、Toast 区域空；兑现之后才弹轻提示', async () => {
    vi.useFakeTimers();
    const gate = deferred();
    const data = env({ profiles: PROFILES_FULL }, ['config', 'profile', 'show']);
    let hang = false;
    set('getProfiles', () => (hang ? gate.promise : Promise.resolve(data)));
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(rowIn(sectionByTitle('profile'), 'step-low'), '删除'));
    await settle();
    hang = true;
    await confirmNow();
    expect(confirmDialog(), '重读中框还开着').not.toBeNull();
    expect(toastEl(), '重读兑现之前 Toast 区域是空的（W3）').toBeNull();
    expect(bodyText(), '重读兑现之前整页没有「已删除」（W3）').not.toContain('已删除');
    gate.resolve(data);
    await settle();
    await advance(20);
    expect(bodyText(), '重读兑现之后才说成功').toContain('已删除 profile step-low');
    expect(confirmDialog()).toBeNull();
    w3bCheck('W3 完成之后');
  });

  it('成功之后重读并 reload：step-low 行从 profile 表消失', async () => {
    vi.useFakeTimers();
    let gone = false;
    const full = env({ profiles: PROFILES_FULL }, ['config', 'profile', 'show']);
    const minus = env({ profiles: PROFILES_FULL.filter((p: any) => p.id !== 'step-low') }, ['config', 'profile', 'show']);
    set('getProfiles', () => Promise.resolve(gone ? minus : full));
    await mountApp('#/roles?write=ok');
    const sec = sectionByTitle('profile');
    expect(rowIn(sec, 'step-low')).toBeTruthy();
    fireEvent.click(buttonByText(rowIn(sec, 'step-low'), '删除'));
    await settle();
    gone = true;
    await confirmNow();
    expect(bodyText()).toContain('已删除 profile step-low');
    const sec2 = sectionByTitle('profile');
    const hit = Array.from(sec2.querySelectorAll('tbody tr')).find((tr) => textOf(tr.querySelector('td')) === 'step-low');
    expect(hit, '成功之后删掉的那一行应从表里消失').toBeFalsy();
  });

  it('方案表删除走完整流程：轻提示「已删除方案 economy」，economy 行消失', async () => {
    vi.useFakeTimers();
    let gone = false;
    const full = env(PRESETS_FULL, ['config', 'preset', 'list']);
    const minus = env({ active_preset: 'default',
      presets: PRESETS_FULL.presets.filter((p: any) => p.name !== 'economy') }, ['config', 'preset', 'list']);
    set('getPresets', () => Promise.resolve(gone ? minus : full));
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(rowIn(sectionByTitle('方案'), 'economy'), '删除…'));
    await settle();
    gone = true;
    await confirmNow();
    expect(bodyText()).toContain('已删除方案 economy');
    const sec = sectionByTitle('方案');
    const hit = Array.from(sec.querySelectorAll('tbody tr')).find((tr) => textOf(tr.querySelector('td')) === 'economy');
    expect(hit, '成功之后 economy 行应从方案表消失').toBeFalsy();
  });

  it('运行时删除走完整流程：轻提示「已删除运行时 opencode」，行消失', async () => {
    vi.useFakeTimers();
    let gone = false;
    const full = env({ runtimes: RUNTIMES_FULL }, ['config', 'runtime', 'list']);
    const minus = env({ runtimes: RUNTIMES_FULL.filter((r: any) => r.id !== 'opencode') }, ['config', 'runtime', 'list']);
    set('getRuntimes', () => Promise.resolve(gone ? minus : full));
    await mountApp('#/runtimes?write=ok');
    fireEvent.click(buttonByText(runtimeRows()[2], '删除…'));
    await settle();
    gone = true;
    await confirmNow();
    expect(bodyText()).toContain('已删除运行时 opencode');
    expect(runtimeRows().length, '成功之后 opencode 行应消失（剩 2 行）').toBe(2);
  });

  it('in-use（profile 被引用）：失败带「内核拒绝」与内核原文，不弹轻提示、没有「成功」「已部分写入」', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=in-use');
    fireEvent.click(buttonByText(rowIn(sectionByTitle('profile'), 'step-low'), '删除'));
    await settle();
    await confirmNow();
    const t = dialogText();
    expect(t).toContain('内核拒绝');
    expect(t).toContain('ERROR: profile step-low 被 roles.execution 引用：先改这些绑定或方案');
    expect(maybeButton(confirmDialog() as HTMLElement, '重新预览')).not.toBeNull();
    expect(maybeButton(confirmDialog() as HTMLElement, '关闭')).not.toBeNull();
    expect(toastEl(), 'Toast 区域应是空的').toBeNull();
    expect(bodyText()).not.toContain('已删除');
    expect(bodyText()).not.toContain('成功');
    expect(bodyText()).not.toContain('已部分写入');
    w3bCheck('in-use 失败之后');
  });

  it('in-use（runtime 被引用）：内核原文逐字，Toast 空', async () => {
    vi.useFakeTimers();
    await mountApp('#/runtimes?write=in-use');
    fireEvent.click(buttonByText(runtimeRows()[0], '删除…'));
    await settle();
    await confirmNow();
    const t = dialogText();
    expect(t).toContain('内核拒绝');
    expect(t).toContain('ERROR: runtime pi 被 profile step-high、step-low 引用：先改或删这些 profile');
    expect(toastEl()).toBeNull();
    expect(bodyText()).not.toContain('已删除');
    w3bCheck('in-use runtime 失败之后');
  });

  it('回滚成功：轻提示「已回滚到 #42 之后」，关框后抽屉仍开、仍是同一条', async () => {
    vi.useFakeTimers();
    await mountApp('#/history?write=ok');
    await openHistoryRow(42);
    fireEvent.click(rollbackBtn());
    await settle();
    expect(dialogText()).toContain('回滚到 #42 之后？');
    await confirmNow();
    expect(bodyText()).toContain('已回滚到 #42 之后');
    expect(confirmDialog()).toBeNull();
    expect(drawerEl(), '回滚成功后抽屉仍开着（reload 不卸载子组件）').not.toBeNull();
    expect(drawerH2(), '抽屉仍是同一条').toBe('#42 · preset.use default');
    w3bCheck('回滚完成之后');
  });

  it('expired 情景：确认号失效的文案，不弹轻提示', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=expired');
    fireEvent.click(buttonByText(rowIn(sectionByTitle('profile'), 'step-low'), '删除'));
    await settle();
    await confirmNow();
    const t = dialogText();
    expect(t).toContain('确认已失效');
    expect(t).toContain('请重新预览');
    expect(toastEl()).toBeNull();
    w3bCheck('expired');
  });
});
"""

# (键, 探针源码, 需要先存在的仓库文件)
PROBE_SPECS = {
    "api": (PROBE_API, (API_REL, MOCKWRITES_REL)),
    "entries": (PROBE_ENTRIES, (PRESETSTABLE_REL, PROFILESTABLE_REL, RUNTIMESVIEW_REL, HISTORYVIEW_REL,
                                MOCKWRITES_REL, USE_WRITE_FLOW_REL, WRITE_DIALOG_REL)),
    "flow": (PROBE_FLOW, (PRESETSTABLE_REL, PROFILESTABLE_REL, RUNTIMESVIEW_REL, HISTORYVIEW_REL,
                          MOCKWRITES_REL, USE_WRITE_FLOW_REL, WRITE_DIALOG_REL)),
}
PROBE_ORDER = ("api", "entries", "flow")


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


def b_marker_present():
    """候选里 api.ts 是否已有 B 片标记（preset.remove）：没有就不起 npm（基线上必然没有）。"""
    path = REPO_ROOT / API_REL
    if not path.is_file():
        return False
    try:
        return "preset.remove" in _read(path)
    except OSError:
        return False


# 流水线前后不该变的文件（相对 desktop/web）
WATCHED = ("package.json", "package-lock.json", "index.html", "vite.config.ts", "tsconfig.json",
           "src/styles/tokens.css", "src/styles/fonts.css", "src/styles/base.css", "src/main.tsx", "src/App.tsx", "src/App.css")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not b_marker_present():
        pipe.reason = ("候选里 api.ts 还没有 B 片的标记（WriteAction 的 preset.remove），没有东西可测，未调用 npm；"
                       "候选把四个新写函数接上之后，流水线才会运行 npm ci、构建、Vitest 和探针")
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
                name = f"probe-{uid}-t023-{key}.test.tsx"
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
    """P1 / D13、D14：npm ci、npm run build、npm test、npm run check:contract 都退出 0；npm test 全绿（含执行端三个
    writes-* 测试文件与照新行为改过的五份既有测试）。"""
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    step = pipeline.steps["npm test"]
    out = step.out
    assert re.search(r"Tests\s+(?:.*\|\s*)?\d+ passed", out), f"npm test 输出里没有 'Tests … N passed'：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", out), f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert re.search(r"Test Files\s+\d+ passed", out) and not re.search(r"Test Files\s+.*\bfailed\b", out), \
        f"npm test 的 Test Files 行异常：\n{step.tail}"


def test_d01_d02_probe_api(pipeline):
    """api 探针 / D01、D02、B9：四个新写函数的导出集合（LATER_API 的名字不在）、预览命令照服务侧基础 argv、
    确认号核对四种错都 409 且 exit_code 为 null、in-use 的三种内核原文逐字与 getOperation failed/exit、
    19 个旧情景对四个新 action 照旧。"""
    assert_probe_ok(pipeline, "api")


def test_d05_d06_probe_entries(pipeline):
    """entries 探针 / D05、D06、D12、B2–B4、W3b：四个入口可点且样式照门禁、确认框标题/摘要/命令、点入口不冒泡
    （diffPresets 不被调、抽屉仍在 h2 不变、Esc 只关确认框）、本机文件条目禁用提示「本机文件不存快照，不能回滚」、
    最新一条可点、确认框元素文字不含「没有变化」、[编辑]/[运行就绪检查] 照旧禁用、offline 下四个入口照旧可点。"""
    assert_probe_ok(pipeline, "entries")


def test_d03_d04_d07_d08_d11_d12_probe_flow(pipeline):
    """flow 探针 / D03、D04、D07–D09、D11、D12、B1、B5、B6、B8、W3、W3b：[确认…] 五个状态都是 danger 而 A 片
    preset.use 仍是 primary、重读兑现之前整页没有「已删除」（W3）、成功之后行真的消失（profile/方案/运行时三处）、
    in-use 的失败与内核原文且不弹轻提示、回滚成功后抽屉仍开仍是同一条、expired 的「确认已失效」。"""
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
