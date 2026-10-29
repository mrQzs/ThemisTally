"""T024 战前门禁：桌面端前端「需要填表单的写入口」（D2 之六，profile 新建与编辑）的黑盒基准测试
（合同 t024-desktop-ui-forms v1，基线 6fb21d4——站主已按规划报告 §7. 退役 T009、T023 的 6 处断言，
本片的改动都还不存在）。

被测对象是 ``desktop/web/``：``src/api.ts`` 放宽写参数类型（新增 ``WriteArgs``）并新增 ``addProfile``/``editProfile``
两个写函数与 ``WriteAction`` 的 ``profile.add``/``profile.edit`` 两个成员；``src/mock/writes.ts`` 加 ``preview-warn``
与 ``preview-invalid`` 两个情景（20 → 22）、``sameArgs`` 数组比较与 ``NEW_ACTIONS`` 两个新 action；``src/writes/`` 新增
``profileRules.ts``（内核原式校验）、``useLivePreview.ts``（300ms 防抖 + 序号丢弃迟到回应）、``ProfileForm.tsx``
（新建/编辑两用的表单对话框，导出 ``NewProfileAction``/``EditProfileAction``）与 ``profile-form.css``；
``useWriteFlow``/``snapshots`` 加两个新 action 的文字表、分派与 ``profileSnapshot`` 投影；``PageFrame`` 的 ``actions``
放宽成可以是函数；页头 [新建 profile] 与 profile 表 [编辑] 接上。表单底部实时显示内核预览（命令、警告、报错原文）；
[确认…] 交给 A 片确认框走「预览 → 确认 → 执行 → 重读 → 终态」；成功只在重读之后才说（W3）；对话框（表单也算）
里不出现「没有变化」（W3b）。

基线（6fb21d4）上 ``api.ts`` 没有 ``WriteArgs`` 与两个新函数，``mock/writes.ts`` 没有 ``preview-warn``，
``src/writes/`` 四个新文件与两个执行端测试文件都不存在，两个入口仍是 ``DisabledAction``，所以本文件的失败落在
「标记不在」「函数不在」「文件不存在」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，所有仓库文件
的读取都发生在用例函数里；流水线（装依赖之后起 build、Vitest 与探针）放在 ``pipeline`` 会话级夹具里，候选里
``api.ts`` 还没有 ``addProfile`` 标记时不装依赖、不起 Vitest。

结构（编号对应合同 DoD 的 D01–D14）：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：api.ts 的 WriteArgs、两个新写函数与 WriteAction 成员
  （S01/D01）；mock 的两个新情景值与情景总数 22、两个新 action 进 NEW_ACTIONS（S02/D02、D07）；useWriteFlow 的
  两个新 action 分支与 WriteSpec.args 放宽（S03/D03）；snapshots 的 profileSnapshot 投影（S04/D11）；ProfileForm
  导出两个入口组件并 import 自己的样式表（S05/D08）；逐字文字表只出现在 src/writes（S06、S10/D09）；RolesPage
  页头接线且不出现四个禁词（S07/D08）；ProfilesTable 的 [编辑] 接线、保留 useWriteFlow 与 reload（S08/D08）；
  PageFrame 的 actions 放宽（S09/D08）；不新增 JSON 与页面文件、components/index.ts 不进 writes（S11/D13）；
  执行端两个测试文件在位、不用 skip/only/todo、带最小覆盖记号（S12/D04–D07）；src 下不出现联网词（S13）；
  profileRules 的内核原式与 useLivePreview 的 300ms（S14/D04、D06）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：npm ci、npm run build、
  npm test、npm run check:contract，再把探针逐份写成 ``gate-probe/probe-<唯一标识>-t024-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除；构建产物里要有 profile-form.css 的类（T009 的教训：
  样式表写得再对、没接进应用也照样全绿）。

探针（Vitest + jsdom，全部自包含；辅助函数不跨文件共享）：

- api：两个新写函数的导出集合（LATER_API/FORBIDDEN 的名字不在）、预览命令照服务侧 buildWriteArgv（数组逐项、
  按顺序、只传了的字段才有 --opt）、执行命令带 --expect-state、确认号核对（对象/action/数组顺序/丢项/多了项/号
  不存在都 409 且 exit_code 为 null，D02/D03）、preview-warn 与 preview-invalid 的实测响应（D07）、旧 20 个情景
  对两个新 action 照旧、profileSnapshot 投影只比约定字段（D11）；
- form：两个入口可点且样式照门禁（页头 secondary/md、表格 ghost/sm、页头次序照旧、仍在禁用的入口提示
  「第二阶段接入」、角色页禁用数 6、offline 照旧可点，D08/D12）；表单字段与控件（TextField/Select/SegmentedControl/
  标签输入、新建缺省 high、runtime 由 getRuntimes 填）；逐字校验提示且不合法不调 preview（D04/M1、M2）；300ms
  防抖（D06）；底部命令（去掉 --dry-run/--json）、警告与报错原文、[确认…] 门控与预览过期（D06/M4）；迟到回应按
  序号丢弃（D06）；编辑初值与 ID 只读、只传改动字段、thinking 缺省未动不传、还没有改动（不是「没有变化」）、
  清空凭据变量的提示与禁用（D05/M3、M8）；runtime 读失败或为空时「先登记 runtime」（D04）；对话框关着时页里
  不渲染任何按钮（M9）；
- flow：新建/编辑走完整流程——A 片确认框的标题/摘要/命令与 primary（D09）、W3 重读兑现之前整页没有「已新建
  profile」（D10）、成功轻提示与 reload 之后表里真的出现新行（D10/M6）、preview-warn 的警告同时出现在表单底部
  与确认框（D07/M4）、执行失败后重开表单值还在、成功后清空。

合同没有写死、门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：编辑模式「模型」字段
的初值按 provider/model 拼成一段（如 bb/step-5-preview，服务侧 validModel 就是按整段校验的）；标签输入的
「添加」钮按可访问名「添加」找、每个 Tag 的移除钮按「Tag 内的按钮 / aria-label 含变量名 / 与 Tag 同级的按钮」
三种摆法找；preview-invalid 情景下拿不到确认号，「执行与终态照 ok」用 write=ok 预签的确认号换情景后执行来测。
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

# 本片新增的四个源码文件与两个执行端测试文件（合同 allowed_new_files）
PROFILEFORM_REL = f"{WRITES_REL}/ProfileForm.tsx"
PROFILEFORM_CSS_REL = f"{WRITES_REL}/profile-form.css"
PROFILERULES_REL = f"{WRITES_REL}/profileRules.ts"
USELIVEPREVIEW_REL = f"{WRITES_REL}/useLivePreview.ts"
EXECUTOR_TESTS = ("writes-profile-form.test.tsx", "writes-profile-api.test.ts")

API_REL = f"{SRC_REL}/api.ts"
MOCKWRITES_REL = f"{MOCK_REL}/writes.ts"
USE_WRITE_FLOW_REL = f"{WRITES_REL}/useWriteFlow.ts"
WRITE_DIALOG_REL = f"{WRITES_REL}/WriteConfirmDialog.tsx"
SNAPSHOTS_REL = f"{WRITES_REL}/snapshots.ts"
PAGEFRAME_REL = f"{SRC_REL}/shell/PageFrame.tsx"
ROLES_PAGE_REL = f"{SRC_REL}/pages/RolesPage.tsx"
PROFILESTABLE_REL = f"{SRC_REL}/pages/readonly1/roles-ProfilesTable.tsx"
INDEX_TS_REL = f"{SRC_REL}/components/index.ts"

# 入口文件（本片自己的两份）：只许出现按钮，字段、提示与标题文字一律在 src/writes/
# 「新建 profile 」「修改 profile 」带尾随空格：抓的是确认框标题模板，按钮标签「新建 profile」不带尾随空格
BAD_ENTRY_TEXTS = (
    "已新建 profile", "已修改 profile", "profile 表里加上", "改动：", "还没有改动",
    "内核没有清空凭据变量的写法", "手填的模型没有核实", "先登记 runtime",
    "只能用小写字母、数字与连字符", "模型要写成 provider/model",
    "变量名只能用字母、数字与下划线", "值在‘凭据’页录入", "新建 profile ", "修改 profile ",
)
# T022 S15：RolesPage.tsx 的原文（注释也算）里不许出现这四个词；页头渲染函数写在 RolesPage 时注意注释
FORBIDDEN_WORDS = ("preview", "getOperation", "usePreset", "setPluginEnabled")
# 确认框标题、变化区摘要与成功轻提示（合同第六节）以及表单逐字提示（第三节）只许出现在 src/writes/
WRITES_TEXTS = (
    "新建 profile ", "修改 profile ", "已新建 profile", "已修改 profile", "profile 表里加上", "改动：",
    "还没有改动", "内核没有清空凭据变量的写法", "手填的模型没有核实", "先登记 runtime",
    "只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符",
    "模型要写成 provider/model，两段都只能用字母、数字与 . _ : / @ + -",
    "变量名只能用字母、数字与下划线，不能以数字开头，最长 128 个字符",
    "值在‘凭据’页录入",
)
# 内核原式（合同第三节）：ID、凭据变量名、模型两段
KERNEL_REGEX_FRAGMENTS = ("[a-z0-9-]{0,63}", "[A-Za-z0-9_]{0,127}", "[A-Za-z0-9._:/@+-]{0,199}")

# 基线名单：src/mock 恰 14 份 JSON、src/pages 顶层恰 9 个 *Page.tsx（不新增 JSON、不新增页面文件）
BASELINE_MOCK_JSON_COUNT = 14
BASELINE_PAGE_COUNT = 9

API_READS = ("getMeta", "getStatus", "getAttempt", "readFile", "getRoles", "getProfiles", "getPresets",
             "diffPresets", "getRuntimes", "getPlugins", "getHistory", "getUsage", "listSecrets")
API_OLD_WRITES = ("preview", "getOperation", "usePreset", "setPluginEnabled",
                  "removePreset", "removeProfile", "removeRuntime", "rollback")

NETWORK_WORDS = ("fetch", "XMLHttpRequest", "EventSource", "WebSocket")

# 执行端两个测试文件里应出现的记号（合同第 8 步与 DoD 的最小覆盖证据，全部是合同逐字要求的文字/口径）
EXECUTOR_TEST_TOKENS = {
    "writes-profile-form.test.tsx": ("还没有改动", "手填的模型没有核实", "内核没有清空凭据变量的写法"),
    "writes-profile-api.test.ts": ("profile.add", "profile.edit", "preview-warn", "preview-invalid", "409"),
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

def test_s01_api_writargs_and_two_new_writes():
    """S01 / D01：api.ts 新增 WriteArgs 与 addProfile/editProfile（签名照合同），preview 放宽成 WriteArgs，
    WriteAction 加 profile.add/profile.edit；13 个读函数与八个旧写函数保留；禁用的四个名字不出现。"""
    text = read_rel(API_REL)
    assert re.search(r"export type WriteArgs = Record<string, string \| string\[\]>", text), \
        "api.ts 应新增 export type WriteArgs = Record<string, string | string[]>"
    assert re.search(r"export function preview\(\s*action:\s*WriteAction,\s*args:\s*WriteArgs\s*\)", text), \
        "preview 的参数类型应放宽为 WriteArgs（旧调用点传 Record<string,string> 仍合法）"
    for member in ("profile.add", "profile.edit"):
        assert f"'{member}'" in text, f"WriteAction 应含成员 '{member}'"
    assert re.search(
        r"export (?:async )?function addProfile\(\s*args:\s*\{[\s\S]*?profile:\s*string;[\s\S]*?runtime:\s*string;"
        r"[\s\S]*?model:\s*string;[\s\S]*?thinking\?:\s*string;[\s\S]*?credential_env\?:\s*string\[\][\s\S]*?\},"
        r"\s*confirmation:\s*string\s*\)", text), \
        "api.ts 应导出 addProfile(args: {profile; runtime; model; thinking?; credential_env?}, confirmation)"
    assert re.search(
        r"export (?:async )?function editProfile\(\s*args:\s*\{[\s\S]*?profile:\s*string;[\s\S]*?runtime\?:\s*string;"
        r"[\s\S]*?model\?:\s*string;[\s\S]*?thinking\?:\s*string;[\s\S]*?credential_env\?:\s*string\[\][\s\S]*?\},"
        r"\s*confirmation:\s*string\s*\)", text), \
        "api.ts 应导出 editProfile(args: {profile; runtime?; model?; thinking?; credential_env?}, confirmation)"
    for name in API_READS:
        assert re.search(rf"export function {name}\(", text), f"api.ts 的读函数 {name} 应原样保留"
    for name in API_OLD_WRITES:
        assert re.search(rf"export (?:async )?function {name}\(", text), f"api.ts 的旧写函数 {name} 应原样保留"
    bad = [n for n in ("saveProfile", "addRuntime", "setRole", "savePreset")
           if re.search(rf"export (?:async )?function {n}\(", text)]
    assert not bad, f"api.ts 不许导出 {bad}（LATER_API/FORBIDDEN 的名字，合同第一节）"


def test_s02_mock_new_scenarios_and_actions():
    """S02 / D02、D07：mock/writes.ts 收第 21、22 个情景 preview-warn 与 preview-invalid；两个新 action 进
    NEW_ACTIONS（confirmWrite 的号/参数核对对它们生效）。"""
    need_file(MOCKWRITES_REL)
    read = read_rel(MOCKWRITES_REL)
    union = re.search(r"export type WriteScenario =([\s\S]*?);", read)
    assert union, "mock/writes.ts 应保留 WriteScenario 类型"
    members = re.findall(r"'([a-z0-9-]+)'", union.group(1))
    # 按包含不按恰好（T022/T023 的口径）：两个新情景在，且总数不少于 22（20 个旧情景一个不丢）
    assert len(members) >= 22, f"WriteScenario 应从 20 个值加到至少 22 个（preview-warn、preview-invalid），现在 {members}"
    for frag in ("preview-warn", "preview-invalid"):
        assert frag in members, f"WriteScenario 应含 '{frag}'"
    for action in ("profile.add", "profile.edit"):
        assert f"'{action}'" in read, f"mock/writes.ts 应认得新 action '{action}'（baseArgv 与 NEW_ACTIONS）"


def test_s03_usewriteflow_new_action_branches():
    """S03 / D03、D09、第八节：useWriteFlow 认得两个新 action（文字表、快照读、执行分派），
    WriteSpec.args 放宽成 WriteArgs。"""
    need_file(USE_WRITE_FLOW_REL)
    text = read_rel(USE_WRITE_FLOW_REL)
    for member in ("profile.add", "profile.edit"):
        assert f"'{member}'" in text, f"useWriteFlow 应分支处理 {member}"
    for name in ("addProfile", "editProfile"):
        assert re.search(rf"\b{name}\b", text), f"useWriteFlow 的 confirm 应分派到写函数 {name}"
    assert re.search(r"args:\s*WriteArgs", text), "WriteSpec.args 应放宽成 WriteArgs"
    assert "getProfiles" in text, "两个新 action 的快照读都用 getProfiles（第七节）"
    # 状态机一行不改：applyFinal 仍是先轻提示再重读的顺序
    assert re.search(r"case 'done':", text), "applyFinal 的 done 分支应保留（W3 的实现处）"


def test_s04_snapshots_profile_projection():
    """S04 / D11、第七节：snapshots.ts 加 profileSnapshot 投影（options?.thinking ?? null），sameSnapshot 保留。"""
    need_file(SNAPSHOTS_REL)
    text = read_rel(SNAPSHOTS_REL)
    assert re.search(r"export function profileSnapshot\(\s*profiles:\s*ProfilesData\s*\)", text), \
        "snapshots.ts 应导出 profileSnapshot(profiles: ProfilesData)"
    assert "?? null" in text, "profileSnapshot 的 thinking 取 options?.thinking ?? null（缺省算 null）"
    assert re.search(r"export function sameSnapshot\(", text), "sameSnapshot 应保留（纯函数比较）"


def test_s05_profileform_exports_and_css_wired():
    """S05 / D05、D08、第五节：ProfileForm.tsx 导出两个入口组件，并 import 自己的样式表（接进产品）。"""
    need_file(PROFILEFORM_REL)
    text = read_rel(PROFILEFORM_REL)
    assert re.search(r"export function NewProfileAction\b", text), "ProfileForm.tsx 应导出 NewProfileAction"
    assert re.search(r"export function EditProfileAction\b", text), "ProfileForm.tsx 应导出 EditProfileAction"
    assert "./profile-form.css" in text, "ProfileForm.tsx 应 import './profile-form.css'（样式表接进产品）"
    need_file(PROFILEFORM_CSS_REL)


def test_s06_writes_texts_live_in_writes():
    """S06 / D09、第三节：确认框标题、变化区摘要、成功轻提示与表单逐字提示都在 src/writes/（按模板原文片段找）。"""
    pool = writes_texts()
    assert pool, "src/writes/ 应存在且有自己的文件"
    missing = [t for t in WRITES_TEXTS if not any(t in text for text in pool.values())]
    assert not missing, f"src/writes/ 里应出现文字表片段 {missing}（合同第三、六节的逐字表）"


def test_s07_rolespage_header_entry():
    """S07 / D08、第四节：页头 [新建 profile] 由 src/writes 的 NewProfileAction 渲染；次序照旧
    （[保存当前为方案…] 仍是 DisabledAction）；T022 S15 的四个禁词一个都不出现（注释也算）。"""
    need_file(ROLES_PAGE_REL)
    text = read_rel(ROLES_PAGE_REL)
    assert "NewProfileAction" in text, "页头 [新建 profile] 应由 src/writes 的 NewProfileAction 渲染（页面只放按钮）"
    assert '<DisabledAction label="保存当前为方案…"' in text, "页头 [保存当前为方案…] 应照旧是 DisabledAction"
    problems = [w for w in FORBIDDEN_WORDS if re.search(rf"\b{w}\b", text)]
    assert not problems, f"RolesPage.tsx 不许出现 {problems}（T022 S15，注释也算）"


def test_s08_profilestable_edit_entry():
    """S08 / D08、D12、第四节：profile 表 [编辑] 由 src/writes 的 EditProfileAction 渲染（不再是 DisabledAction）；
    本组件自己的 useWriteFlow(reload)（给 [删除] 用）与 reload? prop 照旧（T023 S07）；
    T013 的两条动作说明不许在这里出现（注释也算）。"""
    need_file(PROFILESTABLE_REL)
    text = read_rel(PROFILESTABLE_REL)
    assert "EditProfileAction" in text, "profile 表 [编辑] 应由 src/writes 的 EditProfileAction 渲染（页面只放按钮）"
    assert not re.search(r'<DisabledAction label="编辑"', text), "[编辑] 不应再是 DisabledAction"
    assert re.search(r"useWriteFlow\(", text), "ProfilesTable 应照旧自调 useWriteFlow（[删除] 那份，T023 S07）"
    assert re.search(r"reload\?:", text), "ProfilesTableProps 应保留 reload? prop"
    for frag in ("新建 profile", "修改 profile"):
        assert frag not in text, f"roles-ProfilesTable.tsx（含注释）里不许出现「{frag}」（T013：动作说明只有一份）"


def test_s09_pageframe_actions_can_be_function():
    """S09 / D08、第五节：PageFrame 的 actions 放宽成 ReactNode | ((reload) => ReactNode)，渲染时按类型分派。"""
    need_file(PAGEFRAME_REL)
    text = read_rel(PAGEFRAME_REL)
    assert re.search(r"actions\?:\s*ReactNode\s*\|\s*\(\(reload:\s*\(\)\s*=>\s*Promise<void>\)\s*=>\s*ReactNode\)", text), \
        "PageFrameProps 的 actions 应放宽成 ReactNode | ((reload: () => Promise<void>) => ReactNode)"
    assert re.search(r"typeof\s+actions\s*===\s*'function'\s*\?\s*actions\(reload\)\s*:\s*actions", text), \
        "渲染时应写 typeof actions === 'function' ? actions(reload) : actions"


def test_s10_entry_files_have_no_form_texts():
    """S10 / D09：两个入口文件里不出现表单提示、确认框标题与轻提示文字（这些一律在 src/writes/）。"""
    files = {}
    for rel in (ROLES_PAGE_REL, PROFILESTABLE_REL):
        need_file(rel)
        files[rel] = read_rel(rel)
    problems = []
    for rel, text in files.items():
        for frag in BAD_ENTRY_TEXTS:
            if frag in text:
                problems.append(f"{rel} 出现「{frag}」（字段、提示与标题文字只能写在 src/writes/）")
    fail_if(problems, "入口文件里出现了不该出现的文字")


def test_s11_no_new_json_no_new_pages_index_untouched():
    """S11 / D13、第九节：src/mock 不新增 JSON（仍恰 14 份）、src/pages 顶层不新增页面文件（仍恰 9 个）、
    components/index.ts 不出现 writes/。"""
    jsons = sorted(p.name for p in (REPO_ROOT / MOCK_REL).glob("*.json"))
    assert len(jsons) == BASELINE_MOCK_JSON_COUNT, f"src/mock 应仍恰 {BASELINE_MOCK_JSON_COUNT} 份 JSON，现在有 {jsons}"
    pages = sorted(p.name for p in (REPO_ROOT / f"{SRC_REL}/pages").glob("*Page.tsx"))
    assert len(pages) == BASELINE_PAGE_COUNT, f"src/pages 顶层应仍恰 {BASELINE_PAGE_COUNT} 个 *Page.tsx，现在有 {pages}"
    index = read_rel(INDEX_TS_REL)
    assert "writes" not in index, "components/index.ts 不应引用 src/writes/"


def test_s12_executor_test_files_present_and_tokens():
    """S12 / D04–D07、第 8 步：两个执行端测试文件都在，不用 skip/only/todo，且带最小覆盖记号。"""
    for name in EXECUTOR_TESTS:
        rel = f"{TESTS_REL}/{name}"
        need_file(rel)
        text = read_rel(rel)
        bad = [pat for pat in (r"\.skip\s*\(", r"\.only\s*\(", r"\.todo\s*\(", r"\bxit\s*\(", r"\bdescribe\.only")
               if re.search(pat, text)]
        assert not bad, f"{rel} 里出现了 {bad}（不删用例、不削弱断言）"
        missing = [t for t in EXECUTOR_TEST_TOKENS[name] if t not in text]
        assert not missing, f"{rel} 里缺少记号 {missing}（合同要求的最小覆盖）"


def test_s13_no_network_words_in_src():
    """S13 / 非目标：src 下任何文字（注释也算）不出现 fetch、XMLHttpRequest、EventSource、WebSocket。"""
    problems = []
    for path in sorted(SRC.rglob("*")):
        if not path.is_file() or path.suffix not in (".ts", ".tsx", ".css", ".json"):
            continue
        text = _read(path)
        for word in NETWORK_WORDS:
            if re.search(rf"\b{word}\b", text):
                problems.append(f"{path.relative_to(REPO_ROOT)} 出现 {word}")
    fail_if(problems, "src 下出现了联网词（合同非目标：不做真正的网络客户端）")


def test_s14_rules_and_live_preview_files():
    """S14 / D04、D06、第 5 步：profileRules.ts 带内核原式的三段正则；useLivePreview.ts 带 300ms 防抖。"""
    need_file(PROFILERULES_REL)
    text = read_rel(PROFILERULES_REL)
    for frag in KERNEL_REGEX_FRAGMENTS:
        assert frag in text, f"profileRules.ts 应含内核原式片段 {frag}（TASK_ID_RE/ENV_NAME_RE/模型两段）"
    need_file(USELIVEPREVIEW_REL)
    text2 = read_rel(USELIVEPREVIEW_REL)
    assert "300" in text2, "useLivePreview.ts 应有 300ms 防抖常量"


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
// 两种模态对话框：表单对话框里有 label「ID」；A 片写确认框没有
function modalDialogs(): HTMLElement[] {
  return Array.from(document.querySelectorAll('[role="dialog"][aria-modal="true"]')) as HTMLElement[];
}
function formDialog(): HTMLElement | null {
  return modalDialogs().find((d) => Array.from(d.querySelectorAll('label')).some((l) => textOf(l) === 'ID')) || null;
}
function needFormDialog(): HTMLElement {
  const d = formDialog();
  expect(d, '表单对话框应开着（含 label「ID」的模态框）').not.toBeNull();
  return d as HTMLElement;
}
function confirmDialog(): HTMLElement | null {
  return modalDialogs().find((d) => !Array.from(d.querySelectorAll('label')).some((l) => textOf(l) === 'ID')) || null;
}
function needConfirmDialog(): HTMLElement {
  const d = confirmDialog();
  expect(d, 'A 片写确认框应开着').not.toBeNull();
  return d as HTMLElement;
}
function toastEl(): HTMLElement | null {
  return document.querySelector('.tt-toast') as HTMLElement | null;
}
function bodyText(): string {
  return textOf(document.body);
}
function w3bCheck(where: string) {
  const d = confirmDialog();
  if (d) expect(textOf(d), 'W3b：确认框里不许出现「没有变化」（' + where + '）').not.toContain('没有变化');
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

# 替身 api.ts：默认转调真实现，用 set() 换成任意信封、挂起或受控的延迟（T022/T023 探针同款）
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
# api 探针：两个新写函数、mock 的两个新情景与快照投影（合同第一、二、七节；D01–D03、D07、D11）
# ---------------------------------------------------------------------------

PROBE_API = PROBE_PRELUDE + r"""
import * as api from '../src/api';
import { profileSnapshot, sameSnapshot } from '../src/writes/snapshots';

const READS = ['getMeta', 'getStatus', 'getAttempt', 'readFile', 'getRoles', 'getProfiles', 'getPresets',
  'diffPresets', 'getRuntimes', 'getPlugins', 'getHistory', 'getUsage', 'listSecrets'];
const WRITES_OLD = ['preview', 'getOperation', 'usePreset', 'setPluginEnabled',
  'removePreset', 'removeProfile', 'removeRuntime', 'rollback'];
const FORBIDDEN = [
  'listAttempts', 'getConfig', 'validateConfig', 'getHistoryEntry', 'getPlugin', 'checkSecret', 'subscribeEvents',
  'search', 'startJob', 'getJob', 'cancelJob', 'startSecretEntry', 'setRole', 'savePreset', 'saveProfile', 'addRuntime'];

const ADD_FULL = { profile: 'gate-new', runtime: 'pi', model: 'bb/m1', thinking: 'high',
  credential_env: ['AAA_KEY', 'BBB_KEY'] };
const ADD_MIN = { profile: 'x1', runtime: 'pi', model: 'bb/m' };

describe('T024 api：WriteArgs 与两个新写函数', () => {
  it('导出集合：addProfile/editProfile 在；13 个读函数与八个旧写函数保留；LATER_API/FORBIDDEN 的名字不在', () => {
    expect(typeof (api as any).addProfile, '应导出 addProfile').toBe('function');
    expect(typeof (api as any).editProfile, '应导出 editProfile').toBe('function');
    for (const n of WRITES_OLD) expect(typeof (api as any)[n], '旧写函数 ' + n + ' 应保留').toBe('function');
    for (const n of READS) expect(typeof (api as any)[n], '读函数 ' + n + ' 应保留').toBe('function');
    for (const n of FORBIDDEN) expect((api as any)[n], '不许导出 ' + n).toBeUndefined();
  });

  it('preview 的命令照服务侧 buildWriteArgv：profile.add 全字段（数组按顺序逐项，不拼成字符串）', async () => {
    window.location.hash = '#/roles?write=ok';
    const r = await api.preview('profile.add', ADD_FULL as any);
    expect(r.status).toBe(200);
    expect(r.body.ok).toBe(true);
    expect(r.body.data.command).toEqual(['config', 'profile', 'add', 'gate-new', '--runtime=pi', '--model=bb/m1',
      '--thinking=high', '--credential-env=AAA_KEY', '--credential-env=BBB_KEY', '--dry-run', '--json']);
    expect((r.body.data.confirmation as string).length, '确认号应 43 位').toBe(43);
    expect(r.body.data.binding_changes, '这两个 action 的 binding_changes 恒为空数组').toEqual([]);
  });

  it('profile.add 不传 thinking/credential_env 就没有对应开关；profile.edit 只传了的字段才有 --opt', async () => {
    window.location.hash = '#/roles?write=ok';
    const add = await api.preview('profile.add', ADD_MIN as any);
    expect(add.body.data.command).toEqual(['config', 'profile', 'add', 'x1', '--runtime=pi', '--model=bb/m',
      '--dry-run', '--json']);
    const editMin = await api.preview('profile.edit', { profile: 'step-high', model: 'bb/m2' });
    expect(editMin.body.data.command).toEqual(['config', 'profile', 'edit', 'step-high', '--model=bb/m2',
      '--dry-run', '--json']);
    const editFull = await api.preview('profile.edit', { profile: 'step-high', runtime: 'claude-code',
      model: 'bb/m2', thinking: 'low', credential_env: ['A_KEY'] });
    expect(editFull.body.data.command).toEqual(['config', 'profile', 'edit', 'step-high',
      '--runtime=claude-code', '--model=bb/m2', '--thinking=low', '--credential-env=A_KEY', '--dry-run', '--json']);
  });

  it('执行命令带 --expect-state=<state>；确认号核对：对象错/action 错/数组顺序错/丢项/多了项/号不存在都 409 且 exit_code 为 null', async () => {
    window.location.hash = '#/roles?write=ok';
    const conf = (await api.preview('profile.add', ADD_FULL as any)).body.data.confirmation;
    const okRun = await api.addProfile(ADD_FULL as any, conf);
    expect(okRun.status).toBe(200);
    expect(okRun.body.ok).toBe(true);
    expect(okRun.body.exit_code).toBe(0);
    expect(okRun.body.command).toEqual(['config', 'profile', 'add', 'gate-new', '--runtime=pi', '--model=bb/m1',
      '--thinking=high', '--credential-env=AAA_KEY', '--credential-env=BBB_KEY', '--expect-state=<state>']);
    const confEdit = (await api.preview('profile.edit', { profile: 'step-high', model: 'bb/m2' })).body.data.confirmation;
    const okEdit = await api.editProfile({ profile: 'step-high', model: 'bb/m2' }, confEdit);
    expect(okEdit.status).toBe(200);
    expect(okEdit.body.ok).toBe(true);
    expect(okEdit.body.command).toEqual(['config', 'profile', 'edit', 'step-high', '--model=bb/m2',
      '--expect-state=<state>']);
    const wrongs = [
      ['顺序错', await api.addProfile({ ...ADD_FULL, credential_env: ['BBB_KEY', 'AAA_KEY'] } as any, conf)],
      ['丢项', await api.addProfile({ ...ADD_FULL, credential_env: ['AAA_KEY'] } as any, conf)],
      ['多了项', await api.addProfile({ ...ADD_FULL, credential_env: ['AAA_KEY', 'BBB_KEY', 'CCC_KEY'] } as any, conf)],
      ['对象错', await api.addProfile({ ...ADD_FULL, profile: 'other' } as any, conf)],
      ['action 不符', await api.editProfile({ profile: 'gate-new' }, conf)],
      ['号不存在', await api.editProfile({ profile: 'gate-new' }, 'x'.repeat(43))],
    ] as const;
    for (const [why, w] of wrongs) {
      expect(w.status, why + ' 应 409').toBe(409);
      expect(w.body.exit_code, why + ' 的 exit_code 应为 null').toBe(null);
    }
    expect(wrongs[0][1].body.messages).toEqual(['ERROR 确认号无效、已过期或已用过：请重新预览']);
  });

  it('preview-warn：预览 200 ok，warnings 一行（有 model 用 model、没有就写「模型不在」）；执行与终态照 ok', async () => {
    window.location.hash = '#/roles?write=preview-warn';
    const pv = await api.preview('profile.add', ADD_MIN as any);
    expect(pv.status).toBe(200);
    expect(pv.body.ok).toBe(true);
    expect(pv.body.data.warnings).toEqual(['WARN: 模型 bb/m 不在 pi --list-models 的列表里']);
    const pu = await api.preview('preset.use', { name: 'economy' });
    expect(pu.body.data.warnings).toEqual(['WARN: 模型不在 pi --list-models 的列表里']);
    const run = await api.addProfile(ADD_MIN as any, pv.body.data.confirmation);
    expect(run.status).toBe(200);
    expect(run.body.ok).toBe(true);
    expect(run.body.exit_code).toBe(0);
    const op = await api.getOperation(pv.body.data.confirmation);
    expect(op.status).toBe(200);
    expect(op.body.data.state).toBe('succeeded');
  });

  it('preview-invalid：预览 400、ok:false、exit_code:null、data:null、messages 一行；执行与终态照 ok', async () => {
    window.location.hash = '#/roles?write=preview-invalid';
    const pv = await api.preview('profile.add', { profile: 'p9', runtime: 'pi', model: 'bad' });
    expect(pv.status).toBe(400);
    expect(pv.body.ok).toBe(false);
    expect(pv.body.exit_code).toBe(null);
    expect(pv.body.data).toBe(null);
    expect(pv.body.messages).toEqual(['ERROR: model 不合法']);
    // 预览 400 不签确认号；「执行与终态照 ok」用 ok 情景预签的号换情景后执行
    window.location.hash = '#/roles?write=ok';
    const conf = (await api.preview('profile.add', { profile: 'p9', runtime: 'pi', model: 'bad' })).body.data.confirmation;
    window.location.hash = '#/roles?write=preview-invalid';
    const run = await api.addProfile({ profile: 'p9', runtime: 'pi', model: 'bad' }, conf);
    expect(run.status).toBe(200);
    expect(run.body.ok).toBe(true);
    const op = await api.getOperation(conf);
    expect(op.status).toBe(200);
    expect(op.body.data.state).toBe('succeeded');
  });

  it('旧 20 个情景对两个新 action 照旧（抽 exit1、expired、drop-done 三行）', async () => {
    window.location.hash = '#/roles?write=exit1';
    const e1 = await api.addProfile(ADD_MIN as any,
      (await api.preview('profile.add', ADD_MIN as any)).body.data.confirmation);
    expect(e1.status).toBe(200);
    expect(e1.body.ok).toBe(false);
    expect(e1.body.exit_code).toBe(1);
    window.location.hash = '#/roles?write=expired';
    const ex = await api.editProfile({ profile: 'x1' },
      (await api.preview('profile.edit', { profile: 'x1' })).body.data.confirmation);
    expect(ex.status).toBe(409);
    expect(ex.body.exit_code).toBe(null);
    window.location.hash = '#/roles?write=drop-done';
    await expect(api.addProfile(ADD_MIN as any,
      (await api.preview('profile.add', ADD_MIN as any)).body.data.confirmation)).rejects.toBeTruthy();
  });

  it('快照投影：只比 profiles[].{id,runtime,provider,model,options.thinking,credential_env}，adapter 与多余字段变了仍相同（D11）', () => {
    const p = (id: string, over: any = {}) => ({ id, runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'm1',
      options: { thinking: 'high' }, credential_env: ['S'], ...over });
    const a = { profiles: [p('a'), p('b', { model: 'm2', credential_env: [] })] };
    // adapter 与多余字段不同、顺序颠倒 → 仍相同（按 id 排序、排除字段不进投影）
    const b = { profiles: [p('b', { model: 'm2', credential_env: [], adapter: 'zz', notes: 'x' }),
      p('a', { adapter: 'other', extra: 1 })] };
    expect(sameSnapshot(profileSnapshot(a as any), profileSnapshot(b as any)), '排除字段变了应仍相同').toBe(true);
    const c = { profiles: [p('a', { model: 'CHANGED' }), p('b', { model: 'm2', credential_env: [] })] };
    expect(sameSnapshot(profileSnapshot(a as any), profileSnapshot(c as any)), 'model 变了应不同').toBe(false);
    const d = { profiles: [p('a', { options: {} }), p('b', { model: 'm2', credential_env: [] })] };
    expect(sameSnapshot(profileSnapshot(a as any), profileSnapshot(d as any)), 'thinking 缺省（null）与 high 应不同').toBe(false);
    const e = { profiles: [p('a', { credential_env: ['S', 'T'] }), p('b', { model: 'm2', credential_env: [] })] };
    expect(sameSnapshot(profileSnapshot(a as any), profileSnapshot(e as any)), 'credential_env 变了应不同').toBe(false);
  });
});
"""

# ---------------------------------------------------------------------------
# form 探针：表单对话框与两个入口（合同第三、四、五节；D04–D08；M1–M4、M8、M9）
# ---------------------------------------------------------------------------

PROBE_FORM = PROBE_PRELUDE + PROBE_API_MOCK + r"""
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
function pageFrame(): HTMLElement {
  const f = document.querySelector('[data-page-state]') as HTMLElement | null;
  expect(f, '页面框架应在').toBeTruthy();
  return f as HTMLElement;
}
function pageButtons(): string[] {
  return buttons(document.body)
    .filter((b) => !b.closest('[role="dialog"]'))
    .map((b) => textOf(b)).sort();
}
async function tipOf(btn: HTMLElement): Promise<string> {
  const wrap = btn.closest('.tt-tooltip-wrap') as HTMLElement;
  expect(wrap, '禁用入口应被 Tooltip 的包裹元素包着').not.toBeNull();
  fireEvent.mouseEnter(wrap);
  await advance(400);
  const trigger = wrap.firstElementChild as HTMLElement;
  const tipId = trigger.getAttribute('aria-describedby');
  expect(tipId, '悬停 400ms 后触发元素应带 aria-describedby').toBeTruthy();
  const tip = document.getElementById(tipId as string);
  expect(tip, 'aria-describedby 指向的提示应在文档里').not.toBeNull();
  const out = textOf(tip);
  fireEvent.mouseLeave(wrap);
  return out;
}
// 表单控件：TextField/Select 都用 htmlFor 关联（不用 id 选择器，jsdom 的 id 可能带冒号）
function controlByLabel(d: HTMLElement, labelText: string): HTMLInputElement | HTMLSelectElement {
  const label = Array.from(d.querySelectorAll('label')).find((l) => textOf(l) === labelText) as HTMLElement | undefined;
  expect(label, '表单里应有 label「' + labelText + '」').toBeTruthy();
  const forId = label!.getAttribute('for');
  expect(forId, 'label 应通过 htmlFor 关联控件').toBeTruthy();
  const hit = Array.from(d.querySelectorAll('input, select')).find((el) => el.id === forId);
  expect(hit, 'label 关联的控件应在表单里').toBeTruthy();
  return hit as HTMLInputElement | HTMLSelectElement;
}
function thinkingGroup(d: HTMLElement): HTMLElement {
  const g = d.querySelector('[role="radiogroup"][aria-label="thinking"]');
  expect(g, '应有 aria-label="thinking" 的分段选择').toBeTruthy();
  return g as HTMLElement;
}
function segValues(g: HTMLElement): string[] {
  return Array.from(g.querySelectorAll('[role="radio"]')).map((b) => textOf(b as HTMLElement));
}
function checkedSeg(g: HTMLElement): string {
  const hit = Array.from(g.querySelectorAll('[role="radio"]'))
    .find((b) => (b as HTMLElement).getAttribute('aria-checked') === 'true');
  expect(hit, '应有一个选中的 thinking 段').toBeTruthy();
  return textOf(hit as HTMLElement);
}
// 凭据变量的输入框：表单里除「ID」与「模型」外恰一个文本输入（标签输入的输入位）
function envInput(d: HTMLElement): HTMLInputElement {
  const idEl = controlByLabel(d, 'ID') as HTMLInputElement;
  const modelEl = controlByLabel(d, '模型') as HTMLInputElement;
  const rest = (Array.from(d.querySelectorAll('input')) as HTMLInputElement[])
    .filter((i) => i !== idEl && i !== modelEl && i.type !== 'hidden');
  expect(rest.length, '表单里除 ID 与模型外应恰有一个凭据变量输入框').toBe(1);
  return rest[0];
}
function addTagBtn(d: HTMLElement): HTMLButtonElement {
  const hit = buttons(d).find((b) => {
    const name = textOf(b) || b.getAttribute('aria-label') || '';
    return name === '添加';
  });
  expect(hit, '凭据变量应有「添加」钮').toBeTruthy();
  return hit as HTMLButtonElement;
}
// 每个 Tag 一个移除钮：Tag 里的按钮 / aria-label 含变量名 / 与 Tag 同级的按钮
function tagRemoveBtn(d: HTMLElement, name: string): HTMLButtonElement {
  const tag = Array.from(d.querySelectorAll('.tt-tag')).find((t) => textOf(t) === name);
  expect(tag, '应有 Tag「' + name + '」').toBeTruthy();
  let btn: HTMLButtonElement | null = tag!.querySelector('button');
  if (!btn) {
    btn = buttons(d).find((b) => (b.getAttribute('aria-label') || '').indexOf(name) >= 0) || null;
  }
  if (!btn) {
    const parent = tag!.parentElement as HTMLElement;
    btn = (Array.from(parent.querySelectorAll(':scope > button')) as HTMLButtonElement[])[0] || null;
  }
  expect(btn, '找不到「' + name + '」的移除钮').toBeTruthy();
  return btn as HTMLButtonElement;
}
function formConfirm(d: HTMLElement): HTMLButtonElement {
  return buttonByText(d, '确认…');
}
// 构造一份 PreviewData 信封（门控与迟到回应的测试里给 preview 换返回值用）
function pvData(command: string[]): any {
  return { binding_changes: [], resources: [], notes: [], warnings: [], running_attempts: [],
    needs_yes: false, command, confirmation: 'c' };
}
function fillNew(d: HTMLElement, opts: { id?: string; runtime?: string; model?: string } = {}) {
  fireEvent.change(controlByLabel(d, 'ID') as HTMLInputElement, { target: { value: opts.id ?? 'gate-x' } });
  fireEvent.change(controlByLabel(d, 'runtime') as HTMLSelectElement, { target: { value: opts.runtime ?? 'pi' } });
  fireEvent.change(controlByLabel(d, '模型') as HTMLInputElement, { target: { value: opts.model ?? 'bb/m1' } });
}
const PROFILES_FULL = [
  { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview',
    options: { thinking: 'high' }, credential_env: ['STEP_API_KEY'] },
  { id: 'step-low', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini',
    options: { thinking: 'low' }, credential_env: ['STEP_API_KEY'] },
];

describe('T024 表单对话框与两个入口', () => {
  it('新建表单：字段与控件齐全，runtime 由 getRuntimes 填，thinking 七段缺省 high，模型旁常显「手填的模型没有核实」', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    const d = needFormDialog();
    const idEl = controlByLabel(d, 'ID') as HTMLInputElement;
    expect(idEl.value).toBe('');
    expect(idEl.readOnly, '新建时 ID 可编辑').toBe(false);
    const rt = controlByLabel(d, 'runtime') as HTMLSelectElement;
    const opts = Array.from(rt.querySelectorAll('option')).map((o) => ({ value: (o as HTMLOptionElement).value, label: textOf(o) }));
    expect(opts).toEqual([{ value: 'pi', label: 'pi' }, { value: 'claude-code', label: 'claude-code' },
      { value: 'opencode', label: 'opencode' }]);
    const g = thinkingGroup(d);
    expect(segValues(g)).toEqual(['off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']);
    expect(checkedSeg(g), '新建缺省 high').toBe('high');
    expect(textOf(d), '「手填的模型没有核实」应常显（不是出错时才有）').toContain('手填的模型没有核实');
  });

  it('校验：ID、模型、凭据变量名的逐字提示；不合法的取值不调 preview（调用次数 0）', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    const d = needFormDialog();
    const ID_ERR = '只能用小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符';
    const MODEL_ERR = '模型要写成 provider/model，两段都只能用字母、数字与 . _ : / @ + -';
    const ENV_ERR = '变量名只能用字母、数字与下划线，不能以数字开头，最长 128 个字符';
    fillNew(d, { id: '-abc' });
    expect(textOf(d)).toContain(ID_ERR);
    fireEvent.change(controlByLabel(d, 'ID') as HTMLInputElement, { target: { value: 'a'.repeat(65) } });
    expect(textOf(d), '65 个字符的 ID 也报同一句').toContain(ID_ERR);
    await advance(1000);
    expect(spyCalls('preview'), '表单不合法时不调 preview（ID）').toBe(0);
    fireEvent.change(controlByLabel(d, 'ID') as HTMLInputElement, { target: { value: 'gate-x' } });
    fireEvent.change(controlByLabel(d, '模型') as HTMLInputElement, { target: { value: 'no-slash' } });
    expect(textOf(d), '模型没有 / 也报错').toContain(MODEL_ERR);
    fireEvent.change(controlByLabel(d, '模型') as HTMLInputElement, { target: { value: 'bb/bad!' } });
    expect(textOf(d), '模型段里含非法字符也报错').toContain(MODEL_ERR);
    await advance(1000);
    expect(spyCalls('preview'), '表单不合法时不调 preview（模型）').toBe(0);
    fireEvent.change(controlByLabel(d, '模型') as HTMLInputElement, { target: { value: 'bb/m1' } });
    const inp = envInput(d);
    fireEvent.change(inp, { target: { value: '1ABC' } });
    fireEvent.click(addTagBtn(d));
    await settle();
    expect(textOf(d), '凭据变量名以数字开头报错').toContain(ENV_ERR);
    fireEvent.change(inp, { target: { value: 'A'.repeat(129) } });
    fireEvent.click(addTagBtn(d));
    await settle();
    expect(textOf(d), '129 个字符的变量名也报同一句').toContain(ENV_ERR);
    expect(Array.from(d.querySelectorAll('.tt-tag')).length, '不合法的变量名不加成 Tag').toBe(0);
    fireEvent.change(inp, { target: { value: 'OK_KEY' } });
    fireEvent.click(addTagBtn(d));
    await settle();
    expect(Array.from(d.querySelectorAll('.tt-tag')).map((t) => textOf(t))).toEqual(['OK_KEY']);
    await advance(1000);
    expect(spyCalls('preview'), '整个表单合法之后才调 preview').toBeGreaterThanOrEqual(1);
  });

  it('防抖 300ms：改动后 299ms 内不调，300ms 到才调一次', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    const d = needFormDialog();
    fillNew(d);
    await advance(299);
    expect(spyCalls('preview'), '299ms 内不该调 preview').toBe(0);
    await advance(1);
    expect(spyCalls('preview'), '300ms 防抖后应调 preview（合并成一次）').toBe(1);
  });

  it('底部预览：命令去掉 --dry-run/--json；preview-warn 显示 WARN 原文；preview-invalid 显示 ERROR 原文且 [确认…] 不可点', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    let d = needFormDialog();
    fillNew(d);
    await advance(350);
    expect(textOf(d)).toContain('config profile add gate-x --runtime=pi --model=bb/m1');
    expect(textOf(d), '底部命令不带 --dry-run').not.toContain('--dry-run');
    expect(textOf(d), '底部命令不带 --json').not.toContain('--json');
    expect(formConfirm(d).disabled, 'ok 情景预览过后可点').toBe(false);
    cleanup();
    await mountApp('#/roles?write=preview-warn');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    d = needFormDialog();
    fillNew(d, { model: 'bb/m9' });
    await advance(350);
    expect(textOf(d), '表单底部显示预览的 WARN 原文').toContain('WARN: 模型 bb/m9 不在 pi --list-models 的列表里');
    expect(formConfirm(d).disabled, '预览 200 且 ok 时可点').toBe(false);
    cleanup();
    await mountApp('#/roles?write=preview-invalid');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    d = needFormDialog();
    fillNew(d, { model: 'bb/bad' });
    await advance(350);
    expect(textOf(d), '表单底部显示内核报错原文').toContain('ERROR: model 不合法');
    expect(formConfirm(d).disabled, '预览 400 时 [确认…] 不可点').toBe(true);
  });

  it('[确认…] 门控：预览未回不可点；取值变了（旧预览作废）不可点，新预览回来又可点', async () => {
    vi.useFakeTimers();
    const gate = deferred();
    set('preview', () => gate.promise);
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    const d = needFormDialog();
    fillNew(d);
    await advance(350);
    expect(formConfirm(d).disabled, '预览还没回来时不可点').toBe(true);
    gate.resolve(reply(env(pvData(['config', 'profile', 'add', 'gate-x', '--runtime=pi', '--model=bb/m1',
      '--dry-run', '--json']))));
    await settle();
    await advance(20);
    expect(formConfirm(d).disabled, '预览对应当前取值且 200 ok 时可点').toBe(false);
    fireEvent.change(controlByLabel(d, '模型') as HTMLInputElement, { target: { value: 'bb/m2' } });
    expect(formConfirm(d).disabled, '取值变了，旧预览不作数').toBe(true);
    await advance(350);
    expect(formConfirm(d).disabled, '新预览对应当前取值后又可点').toBe(false);
  });

  it('迟到回应按序号丢弃：后发的先回、先发的后回，底部只认最新的那份', async () => {
    vi.useFakeTimers();
    const gates = [deferred(), deferred()];
    let n = 0;
    set('preview', () => {
      const g = gates[n];
      n += 1;
      return g.promise;
    });
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    const d = needFormDialog();
    fillNew(d);
    await advance(350);
    expect(n, '第一次预览已发出').toBe(1);
    fireEvent.change(controlByLabel(d, '模型') as HTMLInputElement, { target: { value: 'bb/m2' } });
    await advance(350);
    expect(n, '第二次预览已发出').toBe(2);
    gates[1].resolve(reply(env(pvData(['config', 'profile', 'add', 'gate-x', '--runtime=pi', '--model=bb/m2',
      '--dry-run', '--json']))));
    await settle();
    await advance(20);
    expect(textOf(d)).toContain('--model=bb/m2');
    gates[0].resolve(reply(env(pvData(['config', 'profile', 'add', 'gate-x', '--runtime=pi', '--model=bb/m1',
      '--dry-run', '--json']))));
    await settle();
    await advance(20);
    expect(textOf(d), '迟到的旧回应应被丢弃').toContain('--model=bb/m2');
    expect(textOf(d), '迟到的旧回应不应覆盖底部').not.toContain('--model=bb/m1');
    expect(formConfirm(d).disabled).toBe(false);
  });

  it('凭据变量：添加、重复不加、按添加顺序进命令（--credential-env 逐项）', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    const d = needFormDialog();
    fillNew(d);
    const inp = envInput(d);
    fireEvent.change(inp, { target: { value: 'AAA_KEY' } });
    fireEvent.click(addTagBtn(d));
    await settle();
    fireEvent.change(inp, { target: { value: 'AAA_KEY' } });
    fireEvent.click(addTagBtn(d));
    await settle();
    const tags = Array.from(d.querySelectorAll('.tt-tag')).map((t) => textOf(t));
    expect(tags.filter((t) => t === 'AAA_KEY').length, '重复的不加').toBe(1);
    fireEvent.change(inp, { target: { value: 'BBB_KEY' } });
    fireEvent.click(addTagBtn(d));
    await settle();
    expect(Array.from(d.querySelectorAll('.tt-tag')).map((t) => textOf(t))).toEqual(['AAA_KEY', 'BBB_KEY']);
    await advance(350);
    expect(textOf(d), '命令里 --credential-env 按添加顺序逐项').toContain(
      '--credential-env=AAA_KEY --credential-env=BBB_KEY');
  });

  it('编辑：初值带全、ID 只读；全都没改时「还没有改动」（不写「没有变化」）且不可点；只改模型时命令只含 --model', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=ok');
    const row = rowIn(sectionByTitle('profile'), 'step-high');
    const edit = buttonByText(row, '编辑');
    expect(edit.disabled).toBe(false);
    expect(edit.getAttribute('data-variant')).toBe('ghost');
    expect(edit.getAttribute('data-size')).toBe('sm');
    fireEvent.click(edit);
    await settle();
    const d = needFormDialog();
    const idEl = controlByLabel(d, 'ID') as HTMLInputElement;
    expect(idEl.value).toBe('step-high');
    expect(idEl.readOnly, '编辑时 ID 只读').toBe(true);
    expect((controlByLabel(d, 'runtime') as HTMLSelectElement).value).toBe('pi');
    expect((controlByLabel(d, '模型') as HTMLInputElement).value, '模型的初值按 provider/model 拼成一段').toBe('bb/step-5-preview');
    expect(checkedSeg(thinkingGroup(d))).toBe('high');
    expect(Array.from(d.querySelectorAll('.tt-tag')).map((t) => textOf(t))).toEqual(['STEP_API_KEY']);
    expect(textOf(d), '全都没改时写「还没有改动」').toContain('还没有改动');
    expect(textOf(d), 'W3b：表单对话框也不写「没有变化」').not.toContain('没有变化');
    expect(formConfirm(d).disabled, '全都没改时 [确认…] 不可点').toBe(true);
    fireEvent.change(controlByLabel(d, '模型') as HTMLInputElement, { target: { value: 'bb/m2' } });
    await advance(350);
    expect(textOf(d)).toContain('config profile edit step-high --model=bb/m2');
    expect(textOf(d), '没改的 runtime 不传').not.toContain('--runtime=');
    expect(textOf(d), '没改的 thinking 不传').not.toContain('--thinking=');
    expect(textOf(d), '没改的凭据变量不传').not.toContain('--credential-env=');
  });

  it('编辑：thinking 原来缺省（界面显示 high）但没动过 → 不传；清空凭据变量 → 「内核没有清空凭据变量的写法」且不可点', async () => {
    vi.useFakeTimers();
    const noThinking = [
      { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview',
        options: {}, credential_env: ['STEP_API_KEY'] },
      { id: 'step-low', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini',
        options: { thinking: 'low' }, credential_env: ['STEP_API_KEY'] },
    ];
    set('getProfiles', () => Promise.resolve(env({ profiles: noThinking }, ['config', 'profile', 'show'])));
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(rowIn(sectionByTitle('profile'), 'step-high'), '编辑'));
    await settle();
    let d = needFormDialog();
    expect(checkedSeg(thinkingGroup(d)), 'thinking 缺省时界面显示 high').toBe('high');
    fireEvent.change(controlByLabel(d, '模型') as HTMLInputElement, { target: { value: 'bb/m2' } });
    await advance(350);
    expect(textOf(d), 'thinking 缺省而未动过就不传').not.toContain('--thinking=');
    fireEvent.click(buttonByText(d, '取消'));
    await settle();
    // 清空凭据变量：去掉唯一的 Tag
    fireEvent.click(buttonByText(rowIn(sectionByTitle('profile'), 'step-low'), '编辑'));
    await settle();
    d = needFormDialog();
    fireEvent.click(tagRemoveBtn(d, 'STEP_API_KEY'));
    await advance(350);
    expect(textOf(d)).toContain('内核没有清空凭据变量的写法');
    expect(formConfirm(d).disabled, '清空凭据变量时 [确认…] 不可点').toBe(true);
  });

  it('runtime 读失败或没有已登记的 runtime：提示「先登记 runtime」且 [确认…] 不可点', async () => {
    vi.useFakeTimers();
    set('getRuntimes', () => Promise.resolve(env({ runtimes: [] }, ['config', 'runtime', 'list'])));
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    let d = needFormDialog();
    expect(textOf(d), '没有已登记的 runtime 时提示').toContain('先登记 runtime');
    expect(formConfirm(d).disabled).toBe(true);
    fireEvent.click(buttonByText(d, '取消'));
    await settle();
    cleanup();
    set('getRuntimes', () => Promise.resolve({ ok: false, exit_code: 2, data: null, output: [],
      messages: ['ERROR 内核没起来'], command: ['config', 'runtime', 'list'], elapsed_ms: 0 }));
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    d = needFormDialog();
    expect(textOf(d), 'runtime 读失败时也提示').toContain('先登记 runtime');
    expect(formConfirm(d).disabled).toBe(true);
  });

  it('对话框关着时页里不渲染任何按钮（连禁用的 [确认…] 也不渲染）', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=ok');
    const before = pageButtons();
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    needFormDialog();
    fireEvent.click(buttonByText(needFormDialog(), '取消'));
    await settle();
    expect(formDialog(), '取消后表单对话框应关上').toBeNull();
    expect(pageButtons(), '关着时页里的按钮集合与打开前一致').toEqual(before);
    fireEvent.click(buttonByText(rowIn(sectionByTitle('profile'), 'step-high'), '编辑'));
    await settle();
    needFormDialog();
    fireEvent.click(buttonByText(needFormDialog(), '取消'));
    await settle();
    expect(pageButtons(), '编辑入口关上后页里的按钮集合也与打开前一致').toEqual(before);
  });

  it('两个入口的样式与仍在禁用的入口：页头次序照旧、[新建 profile] secondary/md 可点；4 张角色卡的 [更改…] 仍禁用；角色页禁用数 6', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?write=ok');
    const actions = document.querySelector('.tt-page__actions') as HTMLElement;
    expect(actions, '页头操作区应在').toBeTruthy();
    const labels = buttons(actions).map((b) => textOf(b));
    expect(labels, '页头按钮次序照旧（T009 D06）').toEqual(['保存当前为方案…', '新建 profile', '刷新']);
    const save = buttonByText(actions, '保存当前为方案…');
    expect(save.disabled, '[保存当前为方案…] 仍禁用（不在本片）').toBe(true);
    const create = buttonByText(actions, '新建 profile');
    expect(create.disabled).toBe(false);
    expect(create.getAttribute('data-variant')).toBe('secondary');
    expect(create.getAttribute('data-size')).toBe('md');
    expect(await tipOf(save), '仍在禁用的入口悬停「第二阶段接入」').toBe('第二阶段接入');
    const changes = buttons(pageFrame()).filter((b) => textOf(b) === '更改…');
    expect(changes.length, '角色卡应有 4 个 [更改…]').toBe(4);
    for (const c of changes) expect(c.disabled, '[更改…] 仍禁用（下一片）').toBe(true);
    const disabledCount = buttons(pageFrame()).filter((b) => b.disabled).length;
    expect(disabledCount, '角色页禁用按钮 9→6（page-app 的口径）').toBe(6);
  });

  it('offline 下两个入口照旧可点', async () => {
    vi.useFakeTimers();
    await mountApp('#/roles?mock=offline&write=ok');
    const actions = document.querySelector('.tt-page__actions') as HTMLElement;
    expect(buttonByText(actions, '新建 profile').disabled, '离线也可点（同 A 片口径）').toBe(false);
    expect(buttonByText(rowIn(sectionByTitle('profile'), 'step-high'), '编辑').disabled).toBe(false);
  });
});
"""

# ---------------------------------------------------------------------------
# flow 探针：完整流程（合同第三、四、六节；D07、D09、D10；W3、W3b）
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
function controlByLabel(d: HTMLElement, labelText: string): HTMLInputElement | HTMLSelectElement {
  const label = Array.from(d.querySelectorAll('label')).find((l) => textOf(l) === labelText) as HTMLElement | undefined;
  expect(label, '表单里应有 label「' + labelText + '」').toBeTruthy();
  const forId = label!.getAttribute('for');
  expect(forId, 'label 应通过 htmlFor 关联控件').toBeTruthy();
  const hit = Array.from(d.querySelectorAll('input, select')).find((el) => el.id === forId);
  expect(hit, 'label 关联的控件应在表单里').toBeTruthy();
  return hit as HTMLInputElement | HTMLSelectElement;
}
function formConfirm(d: HTMLElement): HTMLButtonElement {
  return buttonByText(d, '确认…');
}
function accentBtn(d: HTMLElement): HTMLButtonElement {
  // 确认框底栏的 [确认…] 是唯一 data-variant 为 danger/primary 的按钮
  const b = buttons(d).find(
    (x) => x.getAttribute('data-variant') === 'danger' || x.getAttribute('data-variant') === 'primary');
  expect(b, '确认框底栏应有 danger/primary 的确认钮').toBeTruthy();
  return b as HTMLButtonElement;
}
async function confirmNow() {
  fireEvent.click(buttonByText(needConfirmDialog(), '确认…'));
  await settle();
  await advance(20);
}
function fillNew(d: HTMLElement, opts: { id?: string; model?: string } = {}) {
  fireEvent.change(controlByLabel(d, 'ID') as HTMLInputElement, { target: { value: opts.id ?? 'gate-x' } });
  fireEvent.change(controlByLabel(d, 'runtime') as HTMLSelectElement, { target: { value: 'pi' } });
  fireEvent.change(controlByLabel(d, '模型') as HTMLInputElement, { target: { value: opts.model ?? 'bb/m1' } });
}
const PROFILES_FULL = [
  { id: 'step-high', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-preview',
    options: { thinking: 'high' }, credential_env: ['STEP_API_KEY'] },
  { id: 'step-low', runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'step-5-mini',
    options: { thinking: 'low' }, credential_env: ['STEP_API_KEY'] },
];

describe('T024 profile 新建与编辑的确认流程', () => {
  it('新建全流程：点 [确认…] 表单关上、A 片确认框接手（标题/摘要/命令/primary）；成功后轻提示且表里出现新行', async () => {
    vi.useFakeTimers();
    let added = false;
    const base = env({ profiles: PROFILES_FULL }, ['config', 'profile', 'show']);
    const withNew = env({ profiles: [...PROFILES_FULL, { id: 'gate-new', runtime: 'pi', adapter: 'pi',
      provider: 'bb', model: 'm1', options: { thinking: 'high' }, credential_env: [] }] },
      ['config', 'profile', 'show']);
    set('getProfiles', () => Promise.resolve(added ? withNew : base));
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    const d = needFormDialog();
    fillNew(d, { id: 'gate-new', model: 'bb/m1' });
    await advance(350);
    fireEvent.click(formConfirm(d));
    await settle();
    expect(formDialog(), '点 [确认…] 之后表单对话框应关上').toBeNull();
    added = true;
    const cd = needConfirmDialog();
    const t = textOf(cd);
    expect(t).toContain('新建 profile gate-new？');
    expect(t).toContain('profile 表里加上 gate-new');
    expect(t).toContain('config profile add gate-new --runtime=pi --model=bb/m1');
    expect(t, '确认框的命令不带 --dry-run').not.toContain('--dry-run');
    expect(accentBtn(cd).getAttribute('data-variant'), 'profile.add 不是危险动作，确认钮是 primary').toBe('primary');
    w3bCheck('新建 profile 的确认框');
    await confirmNow();
    expect(bodyText()).toContain('已新建 profile gate-new');
    expect(confirmDialog(), '成功后确认框关上').toBeNull();
    expect(rowIn(sectionByTitle('profile'), 'gate-new'), '成功并 reload 之后表里应有新行').toBeTruthy();
  });

  it('W3：重读兑现之前整页没有「已新建 profile」、Toast 是空的；兑现之后才弹轻提示', async () => {
    vi.useFakeTimers();
    const gate = deferred();
    const data = env({ profiles: PROFILES_FULL }, ['config', 'profile', 'show']);
    let hang = false;
    set('getProfiles', () => (hang ? gate.promise : Promise.resolve(data)));
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    const d = needFormDialog();
    fillNew(d, { id: 'gate-w3' });
    await advance(350);
    fireEvent.click(formConfirm(d));
    await settle();
    hang = true;
    await confirmNow();
    expect(confirmDialog(), '重读中确认框还开着').not.toBeNull();
    expect(toastEl(), '重读兑现之前 Toast 是空的（W3）').toBeNull();
    expect(bodyText(), '重读兑现之前整页没有「已新建」（W3）').not.toContain('已新建');
    gate.resolve(data);
    await settle();
    await advance(20);
    expect(bodyText(), '重读兑现之后才说成功').toContain('已新建 profile gate-w3');
    expect(confirmDialog()).toBeNull();
    w3bCheck('W3 完成之后');
  });

  it('编辑全流程：摘要只列改动过的字段（runtime、model 按次序）；成功轻提示「已修改 profile …」', async () => {
    vi.useFakeTimers();
    const data = env({ profiles: PROFILES_FULL }, ['config', 'profile', 'show']);
    set('getProfiles', () => Promise.resolve(data));
    await mountApp('#/roles?write=ok');
    const row = rowIn(sectionByTitle('profile'), 'step-high');
    fireEvent.click(buttonByText(row, '编辑'));
    await settle();
    let d = needFormDialog();
    fireEvent.change(controlByLabel(d, '模型') as HTMLInputElement, { target: { value: 'bb/m2' } });
    await advance(350);
    fireEvent.click(formConfirm(d));
    await settle();
    let t = textOf(needConfirmDialog());
    expect(t).toContain('修改 profile step-high？');
    expect(t, '只列改动过的字段').toContain('profile step-high 改动：model');
    expect(t).not.toContain('改动：runtime、');
    fireEvent.click(buttonByText(needConfirmDialog(), '取消'));
    await settle();
    expect(confirmDialog()).toBeNull();
    // 改两个字段 → 摘要按 runtime、model 的次序
    fireEvent.click(buttonByText(row, '编辑'));
    await settle();
    d = needFormDialog();
    fireEvent.change(controlByLabel(d, 'runtime') as HTMLSelectElement, { target: { value: 'claude-code' } });
    fireEvent.change(controlByLabel(d, '模型') as HTMLInputElement, { target: { value: 'bb/m2' } });
    await advance(350);
    fireEvent.click(formConfirm(d));
    await settle();
    t = textOf(needConfirmDialog());
    expect(t, '字段名列表按 runtime、model 次序用「、」连接').toContain('profile step-high 改动：runtime、model');
    expect(accentBtn(needConfirmDialog()).getAttribute('data-variant'), 'profile.edit 也不是危险动作').toBe('primary');
    await confirmNow();
    expect(bodyText()).toContain('已修改 profile step-high');
    expect(confirmDialog()).toBeNull();
  });

  it('preview-warn：表单底部与确认框都有那行 WARN；可以确认、执行成功', async () => {
    vi.useFakeTimers();
    const data = env({ profiles: PROFILES_FULL }, ['config', 'profile', 'show']);
    set('getProfiles', () => Promise.resolve(data));
    await mountApp('#/roles?write=preview-warn');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    const d = needFormDialog();
    fillNew(d, { id: 'gate-warn', model: 'bb/m9' });
    await advance(350);
    expect(textOf(d), '表单底部有那行 WARN').toContain('WARN: 模型 bb/m9 不在 pi --list-models 的列表里');
    expect(formConfirm(d).disabled).toBe(false);
    fireEvent.click(formConfirm(d));
    await settle();
    const t = textOf(needConfirmDialog());
    expect(t, '确认框里也有这行警告').toContain('WARN: 模型 bb/m9 不在 pi --list-models 的列表里');
    await confirmNow();
    expect(bodyText()).toContain('已新建 profile gate-warn');
  });

  it('执行失败后重开表单值还在；成功后清空', async () => {
    vi.useFakeTimers();
    const data = env({ profiles: PROFILES_FULL }, ['config', 'profile', 'show']);
    set('getProfiles', () => Promise.resolve(data));
    await mountApp('#/roles?write=exit1');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    let d = needFormDialog();
    fillNew(d, { id: 'gate-keep', model: 'bb/m1' });
    await advance(350);
    fireEvent.click(formConfirm(d));
    await settle();
    await confirmNow();
    const failed = textOf(needConfirmDialog());
    expect(failed, '失败显示内核原文').toContain('内核拒绝');
    expect(toastEl(), '失败不弹轻提示').toBeNull();
    fireEvent.click(buttonByText(needConfirmDialog(), '关闭'));
    await settle();
    expect(confirmDialog()).toBeNull();
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    d = needFormDialog();
    expect((controlByLabel(d, 'ID') as HTMLInputElement).value, '失败后重开还在原来的值').toBe('gate-keep');
    expect((controlByLabel(d, '模型') as HTMLInputElement).value).toBe('bb/m1');
    fireEvent.click(buttonByText(d, '取消'));
    await settle();
    cleanup();
    set('getProfiles', () => Promise.resolve(env({ profiles: [...PROFILES_FULL, { id: 'gate-ok',
      runtime: 'pi', adapter: 'pi', provider: 'bb', model: 'm1', options: { thinking: 'high' },
      credential_env: [] }] }, ['config', 'profile', 'show'])));
    await mountApp('#/roles?write=ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    d = needFormDialog();
    fillNew(d, { id: 'gate-ok', model: 'bb/m1' });
    await advance(350);
    fireEvent.click(formConfirm(d));
    await settle();
    await confirmNow();
    expect(bodyText()).toContain('已新建 profile gate-ok');
    fireEvent.click(buttonByText(document.body, '新建 profile'));
    await settle();
    d = needFormDialog();
    expect((controlByLabel(d, 'ID') as HTMLInputElement).value, '成功后清空').toBe('');
    expect((controlByLabel(d, '模型') as HTMLInputElement).value).toBe('');
  });
});
"""

# (键, 探针源码, 需要先存在的仓库文件)
PROBE_SPECS = {
    "api": (PROBE_API, (API_REL, MOCKWRITES_REL, SNAPSHOTS_REL)),
    "form": (PROBE_FORM, (PROFILEFORM_REL, ROLES_PAGE_REL, PROFILESTABLE_REL, PAGEFRAME_REL,
                          MOCKWRITES_REL, USE_WRITE_FLOW_REL, WRITE_DIALOG_REL,
                          USELIVEPREVIEW_REL, PROFILERULES_REL)),
    "flow": (PROBE_FLOW, (PROFILEFORM_REL, ROLES_PAGE_REL, PROFILESTABLE_REL, PAGEFRAME_REL,
                          MOCKWRITES_REL, USE_WRITE_FLOW_REL, WRITE_DIALOG_REL,
                          USELIVEPREVIEW_REL, PROFILERULES_REL)),
}
PROBE_ORDER = ("api", "form", "flow")


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


def t024_marker_present():
    """候选里 api.ts 是否已有 T024 标记（addProfile）：没有就不起 npm（基线上必然没有）。"""
    path = REPO_ROOT / API_REL
    if not path.is_file():
        return False
    try:
        return "addProfile" in _read(path)
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
    if not t024_marker_present():
        pipe.reason = ("候选里 api.ts 还没有 T024 的标记（addProfile），没有东西可测，未调用 npm；"
                       "候选把两个新写函数与表单接上之后，流水线才会运行 npm ci、构建、Vitest 和探针")
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
            build = run_step("npm run build", [npm, "run", "build"])
            run_step("npm test", [npm, "test"])
            run_step("npm run check:contract", [npm, "run", "check:contract"])
            uid = uuid.uuid4().hex[:12]
            for key in PROBE_ORDER:
                missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                name = f"probe-{uid}-t024-{key}.test.tsx"
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
    """P1 / D13：npm ci、npm run build、npm test、npm run check:contract 都退出 0；npm test 全绿（含执行端两个
    writes-profile-* 测试文件与照新行为改过的 page-roles/page-app）。"""
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    step = pipeline.steps["npm test"]
    out = step.out
    assert re.search(r"Tests\s+(?:.*\|\s*)?\d+ passed", out), f"npm test 输出里没有 'Tests … N passed'：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", out), f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert re.search(r"Test Files\s+\d+ passed", out) and not re.search(r"Test Files\s+.*\bfailed\b", out), \
        f"npm test 的 Test Files 行异常：\n{step.tail}"


def test_p2_profile_form_css_bundled_into_build(pipeline):
    """P2 / D08（T009 的教训）：profile-form.css 有自己的类名，且 build 产物里有它——只读 CSS 文本不够，
    没接进应用的样式表照样全绿；类名从文件里解析出来，不写死。"""
    assert pipeline.ran, pipeline.reason
    need_file(PROFILEFORM_CSS_REL)
    src = read_rel(PROFILEFORM_CSS_REL)
    classes = set(re.findall(r"\.(-?[A-Za-z_][A-Za-z0-9_-]*)", src))
    others = set()
    for p in (REPO_ROOT / SRC_REL).rglob("*.css"):
        if p.name != "profile-form.css":
            others |= set(re.findall(r"\.(-?[A-Za-z_][A-Za-z0-9_-]*)", _read(p)))
    unique = sorted(c for c in classes if c not in others)
    assert unique, "profile-form.css 应有自己的类名（不是全抄既有样式）"
    dist = WEB / "dist"
    assert dist.is_dir(), "npm run build 之后应有 desktop/web/dist"
    bundled = ""
    for p in sorted(dist.rglob("*.css")):
        bundled += _read(p)
    missing = [c for c in unique if c not in bundled]
    assert not missing, f"构建产物里没有 profile-form.css 的类 {missing}（样式表没接进产品）"


def test_d01_d02_d03_d07_d11_probe_api(pipeline):
    """api 探针 / D01–D03、D07、D11：导出集合（LATER_API/FORBIDDEN 的名字不在）、预览命令照服务侧 buildWriteArgv
    （数组逐项按顺序、只传了的字段才有 --opt）、执行命令带 --expect-state、确认号核对六种错都 409 且 exit_code 为
    null、preview-warn 与 preview-invalid 的实测响应、旧 20 个情景对两个新 action 照旧、profileSnapshot 只比约定
    字段。"""
    assert_probe_ok(pipeline, "api")


def test_d04_d05_d06_d08_probe_form(pipeline):
    """form 探针 / D04–D06、D08：字段与控件齐全（runtime 由 getRuntimes 填、thinking 七段缺省 high、模型旁常显
    「手填的模型没有核实」）、逐字校验提示且不合法不调 preview、300ms 防抖、底部命令（去掉 --dry-run/--json）与
    警告报错原文、[确认…] 门控与预览过期、迟到回应按序号丢弃、编辑初值与 ID 只读、只传改动字段、thinking 缺省
    未动不传、还没有改动（不写「没有变化」）、清空凭据变量的提示与禁用、runtime 读失败「先登记 runtime」、
    对话框关着时页里不渲染任何按钮、两个入口的样式与仍在禁用的入口（角色页禁用数 6）、offline 照旧可点。"""
    assert_probe_ok(pipeline, "form")


def test_d07_d09_d10_probe_flow(pipeline):
    """flow 探针 / D07、D09、D10、W3、W3b：新建/编辑走完整流程（A 片确认框的标题、变化区摘要、命令与 primary
    确认钮）、重读兑现之前整页没有「已新建 profile」（W3）、成功轻提示与 reload 之后表里真的出现新行、
    preview-warn 的警告同时出现在表单底部与确认框、执行失败后重开表单值还在、成功后清空。"""
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
