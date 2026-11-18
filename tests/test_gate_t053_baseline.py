"""T053 战前门禁：桌面端前端「[保存当前为方案…]：把当前角色绑定存成方案」的黑盒基准测试
（合同 t053-desktop-web-preset-save.v1，基线 f8ed8e20）。

被测对象是角色与模型页页头新入口 ``PresetSaveAction``（新文件 ``desktop/web/src/writes/PresetSaveForm.tsx``）
与它的四条接线（``api.ts``、``mock/writes.ts``、``useWriteFlow.ts``、``RolesPage.tsx``）：

- 页头第一个按钮从 ``<DisabledAction label="保存当前为方案…" />`` 换成 ``PresetSaveAction``：secondary/md、
  一直可点；RolesPage 其余一字不改（并行四读、失败判定、load/children 行、页头说明、四个禁词、'../api'
  的读函数白名单）。
- 表单（对话框标题「保存当前为方案」）：方案名（validId 当场校验）、说明（1–200 码点、无控制字符、空着不传）、
  要存的角色（只列读到的 explicit === true 角色、缺省全选、roles 一律显式带）、覆盖（重名时显示「会覆盖方案 X」
  并要显式勾「覆盖方案 X」才带 force；改名即复位勾选）；一个显式绑定都没有、一个都没勾、读不出各有原因句，
  这些态不调预览、[确认…] 不可点。
- 预览 → 确认 → 执行 → 重读走既有 useWriteFlow：确认框标题「保存方案 X？」、成功轻提示「已保存方案 X」、
  摘要「方案表里加上 X：存 …」/「覆盖方案 X：存 …」；先关表单再 start。
- ``api.ts``：WriteAction 加 ``'preset.save'``；writeArgs 加 force 'true' → JSON 布尔 true 这一条（预览与执行
  共用）；新导出 ``savePreset``（真实模式 ``POST /api/v1/presets/<name>/save``、正文 ``{ ...writeArgs(w),
  confirmation }`` 且 w 不含 name；桩模式 ``mockSavePreset``）。
- 桩：``baseArgv`` 的 preset.save 分支（--description=/--roles=/--force 逐字照服务）、NEW_ACTIONS 加成员、
  ``previewData`` 加分支（``binding_changes: []``、``resources: ['presets']``）、新导出 ``mockSavePreset`` 走
  ``confirmWrite``；WriteScenario 仍 27 个值、step-low 仍是基线的 6 处。
- 执行端新测试文件 ``desktop/web/tests/writes-preset-save.test.tsx`` 覆盖合同第 7 步点名的每一项。

基线（f8ed8e20）上 ``PresetSaveForm.tsx`` 与新测试文件都不存在，四个接线文件也没有 preset.save，所以本文件的
失败落在「记号不在」「文件不存在」「流水线没跑」这类断言上，不是导入、收集或语法错误：模块级只导入标准库，
所有仓库文件的读取都发生在用例函数里；流水线（npm、Vitest、探针）放在 ``pipeline`` 会话级夹具里（全量 pytest
默认跳过，点名运行本文件才跑；候选里还没有本片的标记时夹具不调 npm——照 T024/T040/T041/T043/T044/T045/
T051/T052 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线）：PresetSaveForm 的写法钉死与逐字提示句（S01）；api.ts 的三个改动
  （S02）；桩的四处改动与 27 值守卫（S03）；useWriteFlow 的三张文字表、readSnapshot 分支与执行分派（S04）；
  RolesPage 的换入口与其余一字不改（S05）；执行端新测试文件在位且要点齐备（S06）。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、npm test 全绿；
  两份探针逐份写成 ``gate-probe/probe-<uid>-t053-<键>.test.tsx``，各用 ``npm test -- gate-probe/<文件名>`` 跑，
  ``finally`` 里删除。探针直接渲染 ``PresetSaveAction``（不挂整页 App），不 mock 被测组件；等防抖用真实计时器
  ``sleep(450)``（不用假计时器）；每份自带全部辅助函数，不跨文件共享作用域。
  - form（真实模式，``setLiveClientForTests`` 注入假服务记录预览与写请求）：入口按钮 secondary/md/一直可点；
    只列 explicit 角色且缺省全选、预览 args 的 roles 恰是读到的两个（次序照读到的）、说明空不带 description；
    方案名空/不合法当场错误句且不发预览；说明超 200 码点错误句且不发预览；一个都不勾原因句且不发预览；
    重名显示「会覆盖方案 default」、不勾覆盖不可预览、勾了预览/执行正文带布尔 force、改名复位覆盖勾选；
    确认先关表单再开确认框（标题、摘要、命令）、执行 POST /api/v1/presets/<name>/save（正文无 name、无 force、
    roles/description/confirmation 齐）、成功轻提示与 reload；覆盖流摘要与正文 force === true；一个显式绑定
    都没有原因句且入口仍可点；读不出原因句；取消再开回到缺省全选、外部改了数据再开按当时数据预填。
  - stub（桩模式，不注入客户端）：底部预览命令逐字（config preset save <name> --roles=… [--description=…]）；
    完整确认流走通（confirmWrite 的参数核对）、成功轻提示与 reload；重名勾覆盖命令带 --force、摘要
    「覆盖方案 default：存 …」、写流程成功。

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
WRITES_REL = f"{SRC_REL}/writes"
TESTS_REL = f"{WEB_REL}/tests"

PRESETSAVEFORM_REL = f"{WRITES_REL}/PresetSaveForm.tsx"
API_REL = f"{SRC_REL}/api.ts"
MOCKWRITES_REL = f"{SRC_REL}/mock/writes.ts"
USEWRITEFLOW_REL = f"{WRITES_REL}/useWriteFlow.ts"
ROLESPAGE_REL = f"{SRC_REL}/pages/RolesPage.tsx"
EXEC_TEST_REL = f"{TESTS_REL}/writes-preset-save.test.tsx"

# 逐字记号（合同 Behavior contract 与「写法钉死」，逐字照抄；X 表示变量名插值）
ENTRY_LABEL = "保存当前为方案…"            # 入口按钮文字（U+2026）
DIALOG_TITLE = "保存当前为方案"            # 对话框标题
NAME_LABEL = "方案名"                      # TextField label
DESC_LABEL = "说明"                        # TextField label
MSG_NAME_REQUIRED = "方案名要填"
MSG_NAME_INVALID = "方案名不合法：小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符"
MSG_DESC_TOO_LONG = "说明最多 200 个字，不能有控制字符"
MSG_NO_EXPLICIT = "还没有写出绑定的角色：先在角色卡上用 [更改…] 写出绑定"
MSG_NONE_CHECKED = "还没有勾要存的角色"
MSG_WILL_OVERWRITE = "会覆盖方案"          # 后接方案名
MSG_OVERWRITE_CHECKBOX = "覆盖方案"        # 后接方案名（勾选项 label）
MSG_READ_FAILED = "读不出当前的角色绑定与方案列表：稍后再试"
MSG_PREVIEWING = "预览中…"
TITLE_OF_SAVE = "保存方案 ${args.name}？"       # useWriteFlow.titleOf 的模板字面量
SUCCESS_OF_SAVE = "已保存方案 ${args.name}"     # useWriteFlow.successTextOf 的模板字面量
SUMMARY_ADD = "方案表里加上 ${args.name}：存"   # changeSummaryOf 不覆盖一支的开头
SUMMARY_OVERWRITE = "覆盖方案 ${args.name}：存"  # changeSummaryOf 覆盖一支的开头

# RolesPage 的 '../api' import 块（基线逐字；合同：从 '../api' 引入的值仍只许白名单里的）
ROLESPAGE_API_IMPORT = """import {
  diffPresets,
  getPresets,
  getProfiles,
  getRoles,
  getHubRoles,
  getQuizsLive,
  type Envelope,
  type HubRolesData,
  type PresetDiffData,
  type PresetsData,
  type ProfilesData,
  type QuizsLiveData,
  type RolesData,
} from '../api';"""

# RolesPage 其余必须一字不改的记号（并行四读、失败判定、load、children、页头说明、既有入口）
ROLESPAGE_KEEP_MARKS = (
    "import { useEffect, useState } from 'react';",
    "import { PageFrame } from '../shell/PageFrame';",
    "import { RolesView, type RolesViewData } from './readonly1/roles-RolesView';",
    "import { NewProfileAction } from '../writes/ProfileForm';",
    "Promise.all([getRoles(), getProfiles(), getPresets(), getHubRoles()])",
    "[roles, profiles, presets].find(",
    "load={loadRoles}",
    "<RolesView data={data} onDiff={diffPresets} reload={reload} live={live} />",
    "<NewProfileAction reload={reload} />",
    'description="四个角色各用哪个 CLI 与模型；方案可以一键切换"',
)
ROLESPAGE_NEW_IMPORTS = (
    "import { PresetSaveAction } from '../writes/PresetSaveForm';",
    "import { roleName } from './readonly1/roles-logic';",
)
PRESETSAVEACTION_LINE = "<PresetSaveAction reload={reload} roleLabel={roleName} />"
# RolesPage 的四个禁词（t048 S 口径：注释也算）
ROLESPAGE_FORBIDDEN = ("preview", "getOperation", "usePreset", "setPluginEnabled")

# api.ts 的 WriteAction 既有 13 个成员（合同：一个不丢）
WRITE_ACTION_MEMBERS = (
    "preset.use", "plugin.enable", "plugin.disable", "preset.remove", "profile.remove",
    "runtime.remove", "config.rollback", "profile.add", "profile.edit", "hub.set",
    "hub.unset", "runtime.add", "role.set",
)
SAVEPRESET_PATH = "/api/v1/presets/${encodeURIComponent(args.name)}/save"

# 桩的守卫：WriteScenario 仍 27 个值；step-low 在代码（去注释）里仍是基线的 6 处（新代码不许再加）
SCENARIO_COUNT = 27
STEP_LOW_COUNT = 6

# 执行端新测试文件的最小覆盖记号（合同第 7 步点名的覆盖点）
EXECUTOR_TEST_TOKENS = (
    "PresetSaveAction", "setLiveClientForTests", "会覆盖方案", "覆盖方案", "/api/v1/presets/",
    "force", "还没有写出绑定的角色", "450", "取消", "reload",
)

# 新源码的禁词（page-static.test.ts 的口径 + T006/T009 的 matchMedia 一类；合同写法钉死第 1 条）
FORBIDDEN_SOURCE_MARKS = (
    "XMLHttpRequest", "EventSource", "WebSocket", "dangerouslySetInnerHTML", "innerHTML", "outerHTML",
    "insertAdjacentHTML", "eval(", "new Function", "document.write", "srcdoc", "DOMParser",
    "matchMedia", "scrollIntoView", "ResizeObserver", "IntersectionObserver", 'role="status"',
)
# 颜色字面量与颜色函数（T006/T009 的口径）
_HEX_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_COLOR_FUNCS = ("rgb(", "rgba(", "hsl(", "hsla(", "color-mix(", "oklch(", "lab(", "hwb(")

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T024/T041/T043/T044/T045/T051/T052 门禁）
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 150}

ASSUMPTIONS = (
    "「会覆盖方案 X」与勾选项「覆盖方案 X」静态按前缀记号 + 探针按整句断言（勾选项 label 逐字「覆盖方案 "
    "default」在探针里钉死）；静态不区分这两条模板的变量名",
    "useWriteFlow 三张文字表的 preset.save 一支按模板开头钉（保存方案 ${args.name}？等），roles 的连接写法"
    "（join('、')）由探针的摘要断言钉死，不静态钉源码写法",
    "writeArgs 的 force 规则按「函数体里有 force 与 'true'」+ 探针看真实正文（预览与执行正文里 force 都是布尔 "
    "true）钉死；number/cadence_seconds/asNumber 仍在由静态钉（t051 S01 的口径）",
    "执行分派「排在 setPluginEnabled 兜底之前」按源码位置钉（savePreset( 的位置在 setPluginEnabled( 之前）；"
    "先关表单再 start 按行为断言（点表单的 [确认…] 后表单对话框关上、写确认框开上），不静态钉调用次序",
    "探针直接渲染 PresetSaveAction（照合同第 7 步给执行端新测试规定的写法），roleLabel 传自定义映射"
    "（'角色-'+code），顺带证明中文名确实走 prop、不在 src/writes 里写死",
    "「预览中…」的三态（读取中/读到/读不出）里，读取中一态静态钉记号；读不出与读到由探针断言"
    "（jsdom 下 Promise 读太快，读取中一态行为上抓不住）",
    "mock/writes.ts 的 step-low 计数按基线 6 处钉（合同「代码里不出现 step-low」按规划报告 §3 的读法：新代码"
    "不许再加，基线 6 处保留）",
    "桩下不断言方案表里多出新方案（桩不改夹具，mock/presets.json 冻结）；桩下断言底部预览命令、确认框标题与"
    "摘要、成功轻提示与 reload（下游须知第 2 条同款口径）",
    "流水线预算 580 秒（G01 的 600 秒减去静态用例与 pytest 自身开销）：node_modules 已在（执行端 Setup 装过）"
    "就不重装；npm ci 只在依赖不齐时跑",
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


#: TS 注释剥离（与 T010/T034/T036/T037/T040/T041/T043/T044/T045/T051/T052 的同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def module_func(code, signature):
    """取模块级函数体：从签名的起点到下一个列首的 ``}``（CRLF 已归一）。找不到给 None。"""
    start = code.find(signature)
    if start < 0:
        return None
    end = code.find("\n}", start)
    if end < 0:
        return None
    return code[start:end + 2]


def _no_skip_marks(text):
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
        if re.search(bad, text):
            problems.append(f"出现 {bad}（不许 skip、only、todo）")
    return problems


def _forbidden_marks(rel, text, code):
    """禁词、写死颜色与跨层引用的公共核对（T045 S10 / T051 S07 / T052 的口径）。"""
    problems = []
    for bad in FORBIDDEN_SOURCE_MARKS:
        if bad in text:
            problems.append(f"{rel} 不应出现 {bad}")
    if _HEX_COLOR.search(code) or any(fn in code for fn in _COLOR_FUNCS):
        problems.append(f"{rel} 不应写死颜色")
    if "style={{" in code:
        problems.append(f"{rel} 不应写内联 style")
    if re.search(r"from\s*['\"]\.\./pages", text):
        problems.append(f"{rel} 不应跨层引 src/pages（中文名由入口文件当 prop 传进来）")
    return problems


def _css_imports(text):
    return re.findall(r"import\s*['\"]([^'\"]+\.css)['\"]", text)


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_preset_save_form():
    """S01 / D01–D03、写法钉死第 1 条：PresetSaveForm.tsx 在位——只导出 PresetSaveAction（外加类型），
    入口按钮文字逐字「保存当前为方案…」且 secondary/md；对话框标题逐字「保存当前为方案」；
    字段 label「方案名」（用 validId，从 ./profileRules 引，不另写正则）与「说明」；逐字提示句
    一个不少；读 roles 与 presets 各一次；useLivePreview('preset.save')、<WriteFlow flow={flow} />
    与 [确认…] 门控记号在位；复用 hub-bind-form.css 的 hb-* 类；不写内联 style、不写死颜色、
    不出现禁词、不跨层引 src/pages。"""
    need_file(PRESETSAVEFORM_REL)
    text = read_rel(PRESETSAVEFORM_REL)
    code = strip_ts_comments(text)
    problems = []
    # --- 导出形态（写法钉死第 1 条：只导出 PresetSaveAction，外加必要的类型导出）---
    exports = [line for line in code.split("\n") if line.startswith("export ")]
    if not exports:
        problems.append("应有 export（至少导出 PresetSaveAction）")
    for line in exports:
        if line.startswith("export function PresetSaveAction("):
            continue
        if line.startswith("export interface ") or line.startswith("export type "):
            continue
        problems.append(f"只许导出 PresetSaveAction 与类型导出：{line.strip()[:60]}")
    if "export function PresetSaveAction(" not in code:
        problems.append("应导出 export function PresetSaveAction(")
    # --- 入口按钮：文字、variant、size ---
    if ENTRY_LABEL not in code:
        problems.append(f"入口按钮文字应逐字「{ENTRY_LABEL}」（U+2026）")
    if 'variant="secondary"' not in code:
        problems.append("入口按钮应写 variant=\"secondary\"")
    if 'size="md"' not in code:
        problems.append("入口按钮应写 size=\"md\"")
    # --- 对话框标题与字段 ---
    if not re.search(r"title=\{?[\"'`]" + DIALOG_TITLE + r"[\"'`]\}?", code):
        problems.append(f"对话框标题应逐字「{DIALOG_TITLE}」（title 属性）")
    if f'label="{NAME_LABEL}"' not in code:
        problems.append(f"方案名字段的 label 应恰为「{NAME_LABEL}」")
    if f'label="{DESC_LABEL}"' not in code:
        problems.append(f"说明字段的 label 应恰为「{DESC_LABEL}」")
    if "mono" not in code:
        problems.append("方案名字段应用等宽字体（mono）")
    # --- 方案名校验走 profileRules 的 validId，不另写正则 ---
    if "validId" not in code:
        problems.append("方案名校验应直接用 profileRules 的 validId（合同写法钉死第 1 条/规划端核实项 1）")
    if "from './profileRules'" not in text:
        problems.append("应从 './profileRules' 引入 validId")
    if "[a-z0-9][a-z0-9-]{0,63}" in code:
        problems.append("不应在表单里另写 ID 正则（用 profileRules 的 validId）")
    # --- 逐字提示句（包含式核对，一个不少）---
    for mark, what in (
        (MSG_NAME_REQUIRED, "方案名为空"),
        (MSG_NAME_INVALID, "方案名不合法"),
        (MSG_DESC_TOO_LONG, "说明超长/控制字符"),
        (MSG_NO_EXPLICIT, "没有显式绑定"),
        (MSG_NONE_CHECKED, "一个都没勾"),
        (MSG_WILL_OVERWRITE, "会覆盖方案"),
        (MSG_READ_FAILED, "读不出"),
        (MSG_PREVIEWING, "预览中…"),
    ):
        if mark not in text:
            problems.append(f"{what}的提示句应逐字在位：{mark[:24]}…")
    if not re.search(r"覆盖方案 \$\{", code):
        problems.append("覆盖勾选项的 label 应是「覆盖方案 ${…}」模板（写法钉死第 1 条）")
    # --- 读取与预览接线 ---
    if "getRoles(" not in code or "getPresets(" not in code:
        problems.append("表单应读 getRoles() 与 getPresets()（打开时各读一次）")
    if not re.search(r"useLivePreview\(\s*'preset\.save'", code):
        problems.append("表单底部应用 useLivePreview('preset.save', args, enabled)")
    if "<WriteFlow flow={flow} />" not in code:
        problems.append("文件里应放 <WriteFlow flow={flow} />（写流程在外层照常渲染）")
    if "dispatchCommand" not in code:
        problems.append("底部预览应显示 dispatchCommand(result.command)")
    for token in ("current", "onClose", "onConfirm"):
        if token not in code:
            problems.append(f"[确认…] 的门控/次序应能看到 {token}（照既有表单的写法）")
    if not ("result.ok" in code or "result?.ok" in code):
        problems.append("[确认…] 的门控应能看到 result.ok")
    # --- 样式：复用 hub-bind-form.css，不新建、不内联、不写死颜色 ---
    css_imports = _css_imports(text)
    if "./hub-bind-form.css" not in css_imports:
        problems.append("应 import './hub-bind-form.css'（复用 .hb-* 类，不新建 CSS）")
    for other in css_imports:
        if other != "./hub-bind-form.css":
            problems.append(f"不应引别的样式表（{other}；样式只复用 hub-bind-form.css）")
    if "hb-" not in code:
        problems.append("底部与字段应复用 hub-bind-form.css 的 hb-* 类")
    problems.extend(_forbidden_marks("PresetSaveForm.tsx", text, code))
    fail_if(problems, "PresetSaveForm.tsx 的写法钉死（S01）")


def test_s02_api_save_preset():
    """S02 / D05、写法钉死第 2 条：api.ts 的三个改动——WriteAction 加 'preset.save'（既有 13 个成员
    一个不丢）；writeArgs 加 force 键 'true' → JSON 布尔 true 这一条（number/cadence_seconds/asNumber
    的既有规则仍在，预览与执行共用）；新导出 savePreset（真实模式路径与正文逐字、桩模式 mockSavePreset）；
    preview 的正文仍是 args: writeArgs(args)。"""
    need_file(API_REL)
    text = read_rel(API_REL)
    code = strip_ts_comments(text)
    problems = []
    # --- WriteAction：14 个成员（13 个既有 + preset.save）---
    m = re.search(r"export type WriteAction =\s*(.*?);", code, re.S)
    assert m, "api.ts 里应有 export type WriteAction = … 联合类型"
    block = m.group(1)
    for member in WRITE_ACTION_MEMBERS:
        if f"'{member}'" not in block:
            problems.append(f"WriteAction 既有成员 '{member}' 不应丢")
    if "'preset.save'" not in block:
        problems.append("WriteAction 应加成员 'preset.save'")
    # --- writeArgs：force 这一条规则 + 既有规则不动 ---
    body = module_func(code, "function writeArgs(")
    if body is None:
        problems.append("应仍有模块级 function writeArgs（预览与执行共用）")
    else:
        if "'force'" not in body:
            problems.append("writeArgs 应有 force 键的规则（'true' → JSON 布尔 true）")
        elif "'true'" not in body:
            problems.append("writeArgs 的 force 规则应只认 'true'（其余写法原样传，服务回 400）")
        if "asNumber(" not in body or "'cadence_seconds'" not in body or "'number'" not in body:
            problems.append("writeArgs 的 number/cadence_seconds/asNumber 既有规则不应动（t051 S01）")
    # --- preview 仍走同一份规则 ---
    if "args: writeArgs(args)" not in code:
        problems.append("preview 的正文应仍是 { action, args: writeArgs(args) }（预览与执行共用）")
    # --- savePreset：导出、路径、正文、桩分支 ---
    if "export function savePreset(" not in code:
        problems.append("应新导出 export function savePreset(")
    else:
        fn = module_func(code, "export function savePreset(")
        if SAVEPRESET_PATH not in (fn or ""):
            problems.append(f"savePreset 真实模式路径应逐字 {SAVEPRESET_PATH}")
        if not re.search(r"\{ \.\.\.writeArgs\(\w+\), confirmation \}", fn or ""):
            problems.append("savePreset 真实模式正文应恰是 { ...writeArgs(w), confirmation }（writeArgs 套同一份规则）")
        if "mockSavePreset(" not in (fn or ""):
            problems.append("savePreset 桩模式应转 mockSavePreset(")
    fail_if(problems, "api.ts 的 preset.save 接线（S02）")


def test_s03_mock_writes():
    """S03 / D05、写法钉死第 3 条：mock/writes.ts 的四处改动——baseArgv 的 preset.save 分支
    （--description=/--roles=/--force 逐字照服务）；NEW_ACTIONS 加 'preset.save'；previewData 加
    preset.save 分支（binding_changes 空数组、resources: ['presets']）；新导出 mockSavePreset 走
    confirmWrite('preset.save', …)；WriteScenario 仍恰 27 个值；step-low 仍是基线的 6 处（新代码不加）。"""
    need_file(MOCKWRITES_REL)
    text = read_rel(MOCKWRITES_REL)
    code = strip_ts_comments(text)
    problems = []
    # --- baseArgv 的 preset.save 分支 ---
    base = module_func(code, "function baseArgv(")
    if base is None:
        problems.append("应仍有模块级 function baseArgv")
    else:
        if "'preset.save'" not in base:
            problems.append("baseArgv 应有 preset.save 分支")
        else:
            for token in ("'config'", "'preset'", "'save'", "--description=", "--roles=", "--force"):
                if token not in base:
                    problems.append(f"baseArgv 的 preset.save 分支应含 {token}（逐字照服务 buildWriteArgv）")
    # --- NEW_ACTIONS 加 'preset.save' ---
    m = re.search(r"const NEW_ACTIONS = new Set<string>\(\[(.*?)\]\)", code, re.S)
    if m is None:
        problems.append("应仍有 const NEW_ACTIONS = new Set<string>([…])")
    elif "'preset.save'" not in m.group(1):
        problems.append("NEW_ACTIONS 应加 'preset.save'（写函数的确认号与参数核对靠它）")
    # --- previewData 的 preset.save 分支 ---
    preview = module_func(code, "function previewData(")
    if preview is None:
        problems.append("应仍有模块级 function previewData")
    else:
        if "'preset.save'" not in preview:
            problems.append("previewData 应有 preset.save 分支")
        if "resources: ['presets']" not in preview:
            problems.append("previewData 的 preset.save 分支应给 resources: ['presets']")
    # --- mockSavePreset 走 confirmWrite ---
    if "export function mockSavePreset(" not in code:
        problems.append("应新导出 export function mockSavePreset(")
    elif "confirmWrite('preset.save'" not in module_func(code, "export function mockSavePreset("):
        problems.append("mockSavePreset 应走 confirmWrite('preset.save', …)（与预览时同一份 args）")
    # --- WriteScenario 仍恰 27 个值 ---
    union = re.search(r"export type WriteScenario =\s*(.*?);", code, re.S)
    if union is None:
        problems.append("应仍有 export type WriteScenario")
    else:
        count = len(re.findall(r"\|\s*'[a-z0-9-]+'", union.group(1)))
        if count != SCENARIO_COUNT:
            problems.append(f"WriteScenario 应仍恰 {SCENARIO_COUNT} 个值（现在是 {count}，一个都不许加）")
    arr = re.search(r"const SCENARIOS: readonly WriteScenario\[\] =\s*\[(.*?)\]", code, re.S)
    if arr is None:
        problems.append("应仍有 const SCENARIOS 数组")
    else:
        count = len(re.findall(r"'[^']+'", arr.group(1)))
        if count != SCENARIO_COUNT:
            problems.append(f"SCENARIOS 应仍恰 {SCENARIO_COUNT} 个值（现在是 {count}）")
    # --- step-low 仍是基线的 6 处（新代码不许再加）---
    hits = code.count("step-low")
    if hits != STEP_LOW_COUNT:
        problems.append(f"代码（去注释）里 step-low 应仍是基线的 {STEP_LOW_COUNT} 处（现在是 {hits}；新分支不许用 step-low）")
    fail_if(problems, "mock/writes.ts 的 preset.save 桩（S03）")


def test_s04_use_write_flow():
    """S04 / D04、D05、写法钉死第 4 条：useWriteFlow.ts 的三处接线——三张文字表各有 preset.save
    一支（标题/成功轻提示/摘要的模板逐字开头）；readSnapshot 有 preset.save 分支（getPresets()）；
    执行分派有 preset.save → savePreset(…) 且排在 setPluginEnabled 兕底之前；既有动作的分支与
    文字一个不改（抽检 preset.remove 与 role.set）；dangerOf 不改（preset.save 不是危险动作）。"""
    need_file(USEWRITEFLOW_REL)
    text = read_rel(USEWRITEFLOW_REL)
    code = strip_ts_comments(text)
    problems = []
    # --- 三张文字表 ---
    title = module_func(code, "function titleOf(")
    if title is None or TITLE_OF_SAVE not in title:
        problems.append(f"titleOf 应有 preset.save 一支：{TITLE_OF_SAVE}")
    elif "改角色绑定 ${args.role}？" not in title:
        problems.append("titleOf 既有 role.set 文字不应动")
    success = module_func(code, "function successTextOf(")
    if success is None or SUCCESS_OF_SAVE not in success:
        problems.append(f"successTextOf 应有 preset.save 一支：{SUCCESS_OF_SAVE}")
    summary = module_func(code, "function changeSummaryOf(")
    if summary is None or SUMMARY_ADD not in summary:
        problems.append(f"changeSummaryOf 应有不覆盖一支：{SUMMARY_ADD} …")
    elif SUMMARY_OVERWRITE not in summary:
        problems.append(f"changeSummaryOf 应有覆盖一支：{SUMMARY_OVERWRITE} …")
    elif "方案表里去掉 ${args.name}，角色绑定不变" not in summary:
        problems.append("changeSummaryOf 既有 preset.remove 文字不应动")
    # --- readSnapshot 的 preset.save 分支 ---
    snap = module_func(code, "async function readSnapshot(")
    if snap is None:
        problems.append("应仍有 async function readSnapshot")
    elif "'preset.save'" not in snap or "getPresets()" not in snap:
        problems.append("readSnapshot 应有 preset.save 分支（读 getPresets()；快照用 presetRemoveSnapshot）")
    if "presetRemoveSnapshot" not in text:
        problems.append("应仍从 './snapshots' 引 presetRemoveSnapshot")
    # --- 执行分派：preset.save → savePreset，排在 setPluginEnabled 兕底之前 ---
    if "savePreset," not in code:
        problems.append("应从 '../api' 引入 savePreset")
    ci = code.find("const confirm = useCallback(")
    if ci < 0:
        problems.append("应仍有 const confirm = useCallback 分派链")
    else:
        tail = code[ci:]
        p_save = tail.find("'preset.save'")
        p_call = tail.find("savePreset(")
        p_fallback = tail.find("setPluginEnabled(")
        if p_save < 0 or p_call < 0:
            problems.append("执行分派应有 preset.save → savePreset(…)")
        elif p_fallback < 0 or p_call > p_fallback:
            problems.append("savePreset(…) 应排在 setPluginEnabled 兕底之前")
    # --- dangerOf 不改（保存方案不是危险动作）---
    danger = module_func(code, "function dangerOf(")
    if danger is None:
        problems.append("应仍有 function dangerOf")
    elif "preset.save" in danger:
        problems.append("dangerOf 不应把 preset.save 算成危险动作（覆盖也用 primary）")
    fail_if(problems, "useWriteFlow.ts 的三处接线（S04）")


def test_s05_roles_page():
    """S05 / D01、写法钉死第 5 条：RolesPage.tsx 换入口且其余一字不改——页头第一个按钮换成
    <PresetSaveAction reload={reload} roleLabel={roleName} />（在 NewProfileAction 之前）；
    新增两个 import（PresetSaveAction、只引 roleName 一个值）；不再出现 DisabledAction；
    '../api' 的 import 块逐字照旧（读函数白名单）；并行四读、失败判定、load、children、页头说明、
    既有入口一个不少；四个禁词（注释也算）一个不出现。"""
    need_file(ROLESPAGE_REL)
    text = read_rel(ROLESPAGE_REL)
    problems = []
    if PRESETSAVEACTION_LINE not in text:
        problems.append(f"页头应写 {PRESETSAVEACTION_LINE}")
    if "<NewProfileAction reload={reload} />" not in text:
        problems.append("页头应仍渲染 <NewProfileAction reload={reload} />")
    elif PRESETSAVEACTION_LINE in text and text.find(PRESETSAVEACTION_LINE) > text.find("<NewProfileAction"):
        problems.append("页头次序应仍是「保存当前为方案…」在前、「新建 profile」在后")
    for line in ROLESPAGE_NEW_IMPORTS:
        if line not in text:
            problems.append(f"应新增 import：{line}")
    if "DisabledAction" in text:
        problems.append("不再出现 DisabledAction（入口换成了 PresetSaveAction）")
    for mark in ROLESPAGE_KEEP_MARKS:
        if mark not in text:
            problems.append(f"其余部分一字不改，应仍有：{mark[:60]}")
    if ROLESPAGE_API_IMPORT not in text:
        problems.append("'../api' 的 import 块应逐字照旧（读函数白名单，一个不加）")
    for bad in ROLESPAGE_FORBIDDEN:
        if bad in text:
            problems.append(f"RolesPage 不应出现禁词 {bad}（t048 口径，注释也算）")
    fail_if(problems, "RolesPage.tsx 的换入口（S05）")


def test_s06_executor_test_file():
    """S06 / D06：执行端新测试文件 desktop/web/tests/writes-preset-save.test.tsx 在位且覆盖记号
    齐备（合同第 7 步点名的覆盖点：直接渲染 PresetSaveAction、setLiveClientForTests 注入假服务、
    重名与覆盖勾选、写路由 /api/v1/presets/、force、没有显式绑定的原因句、真实计时器 450ms 等
    防抖、取消后再开、reload），不许 skip/only/todo（T002 会扫全部 *.test.*）。"""
    need_file(EXEC_TEST_REL)
    text = read_rel(EXEC_TEST_REL)
    problems = []
    for token in EXECUTOR_TEST_TOKENS:
        if token not in text:
            problems.append(f"writes-preset-save.test.tsx 应含记号「{token}」（合同第 7 步点名的覆盖点）")
    problems.extend(_no_skip_marks(text))
    fail_if(problems, "执行端新测试文件（S06）")


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针（照 T044/T045/T051/T052 门禁的写法）
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
    proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
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


def git_status_set():
    proc = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
                          cwd=REPO_ROOT, capture_output=True, timeout=120)
    assert proc.returncode == 0, f"git status 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


def t053_marker_present():
    """候选里是否已有 T053 的标记（新表单文件 + 四条接线）：没有就不起 npm（基线上必然没有）。"""
    try:
        form = _read(REPO_ROOT / PRESETSAVEFORM_REL) if (REPO_ROOT / PRESETSAVEFORM_REL).is_file() else ""
        api = _read(REPO_ROOT / API_REL) if (REPO_ROOT / API_REL).is_file() else ""
    except OSError:
        return False
    return "PresetSaveAction" in form and "preset.save" in api


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t053_marker_present():
        pipe.reason = ("候选里还没有 T053 的标记（src/writes/PresetSaveForm.tsx 的 PresetSaveAction 或 api.ts 的 "
                       "preset.save），没有东西可测，未调用 npm；候选把入口与接线都放进去之后，"
                       "流水线才会运行 npm ci、Vitest 与探针")
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
            if pipe.steps.get("npm test") is not None and pipe.steps["npm test"].code == 0:
                uid = uuid.uuid4().hex[:12]
                for key in PROBE_ORDER:
                    missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                    if missing:
                        pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                        continue
                    name = f"probe-{uid}-t053-{key}.test.tsx"
                    probe_dir.mkdir(exist_ok=True)
                    path = probe_dir / name
                    written.append(path)
                    path.write_text(PROBE_SPECS[key][0], encoding="utf-8", newline="\n")
                    pipe.probe_files[key] = name
                    run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        else:
            pipe.stopped_reason = "npm ci（含 --offline 兕底）失败，后续步骤未运行"
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


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


# ---------------------------------------------------------------------------
# 探针（黑盒 Vitest 用例，临时写进 desktop/web/gate-probe/，跑完即刪；每份自带全部辅助函数）
# ---------------------------------------------------------------------------

FORM_PROBE = r'''// T053 门禁 form 探针（真实模式）：setLiveClientForTests 注入假服务，记录预览与写请求，看真实正文
// （预览正文过 writeArgs：force 'true' 应转成布尔 true）。直接渲染入口组件（不 mock 被测组件），
// roleLabel 传自定义映射（证明中文名确实走 prop）；等防抖用真实计时器 sleep(450)。每份探针自带全部辅助函数。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PresetSaveAction } from '../src/writes/PresetSaveForm';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

const ENTRY = '保存当前为方案…';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
}
function btnIn(root: any, label: string): HTMLButtonElement {
  const hit = qa(root, 'button').find((b: any) => text(b) === label);
  expect(hit, '应有按钮「' + label + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}
function inputByLabel(d: HTMLElement, labelText: string): HTMLInputElement {
  const label = qa(d, 'label').find((l: any) => text(l) === labelText);
  expect(label, '表单里应有 label「' + labelText + '」').toBeTruthy();
  const hit = qa(d, 'input').find((el: any) => el.id === (label as any).getAttribute('for'));
  expect(hit, 'label 关联的 input 应在表单里').toBeTruthy();
  return hit as HTMLInputElement;
}
function checkboxByLabel(d: HTMLElement, label: string): HTMLElement {
  const hit = qa(d, '[role="checkbox"]').find((b: any) => text(b) === label);
  expect(hit, '应有勾选项「' + label + '」').toBeTruthy();
  return hit as HTMLElement;
}
function boxesOf(d: HTMLElement): any[] {
  return qa(d, '[role="checkbox"]').filter((b: any) => text(b).indexOf('角色-') === 0);
}

function okEnv<T>(data: T, command: string[] = []): any {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}
function badEnv(): any {
  return { ok: false, exit_code: 1, data: null, output: [], messages: ['ERROR 读不出'], command: [], elapsed_ms: 0 };
}

let posts: Array<{ path: string; body: any }> = [];

// 可变数据：探针里换内容模拟「外部改了数据后再开」与读失败
function rolesEnvelope(explicit: Record<string, boolean>): any {
  const binding: Record<string, unknown> = { mode: 'manual' };
  return {
    roles: ['planning_review', 'contract', 'execution', 'scheduler_agent'].map((role) => ({
      role,
      explicit: explicit[role] === true,
      binding,
    })),
  };
}
const DEFAULT_ROLES = rolesEnvelope({ planning_review: true, execution: true });
const PRESETS_DATA = {
  active_preset: 'default',
  presets: [
    { name: 'default', description: '日常', roles: ['contract', 'execution', 'planning_review', 'scheduler_agent'], active: true },
    { name: 'economy', description: '省钱', roles: ['execution'], active: false },
  ],
};
let rolesData: any = DEFAULT_ROLES;
let presetsData: any = PRESETS_DATA;
let rolesFail = false;
let presetsFail = false;

const fake: LiveClient = {
  get(path: string): Promise<any> {
    if (path === '/api/v1/roles') return Promise.resolve(rolesFail ? badEnv() : okEnv(rolesData));
    if (path === '/api/v1/presets') return Promise.resolve(presetsFail ? badEnv() : okEnv(presetsData));
    return Promise.resolve(okEnv(null));
  },
  post(path: string, body: unknown): Promise<any> {
    posts.push({ path, body });
    if (path === '/api/v1/preview') {
      const a: any = (body as any).args;
      const command = ['config', 'preset', 'save', a.name, '--roles=' + (a.roles || []).join(',')];
      if (a.description) command.push('--description=' + a.description);
      if (a.force === true) command.push('--force');
      command.push('--dry-run', '--json');
      const preview = {
        binding_changes: [], resources: [{ resource: 'presets' }], notes: [], warnings: [],
        running_attempts: [], running_turns: [], needs_yes: false, hub_changes: [],
      };
      return Promise.resolve({ status: 200, body: okEnv({ preview, confirmation: 'c-real-1' }, command) });
    }
    return Promise.resolve({ status: 200, body: okEnv(null, ['config', 'preset', 'save']) });
  },
  getRaw(): Promise<any> {
    return Promise.resolve({ status: 404, body: null });
  },
};

function props(over: Record<string, unknown> = {}): any {
  return {
    reload: vi.fn(() => Promise.resolve()),
    roleLabel: (c: string) => '角色-' + c,
    ...over,
  };
}
function previews(): any[] {
  return posts.filter((x) => x.path === '/api/v1/preview');
}
function saveWrites(): any[] {
  return posts.filter((x) => x.path.indexOf('/api/v1/presets/') === 0 && x.path.endsWith('/save'));
}

beforeEach(() => {
  posts = [];
  rolesData = DEFAULT_ROLES;
  presetsData = PRESETS_DATA;
  rolesFail = false;
  presetsFail = false;
  setLiveClientForTests(fake);
  window.location.hash = '';
});
afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('PresetSaveAction：表单与写流程（真实模式，D01–D04）', () => {
  it('(a) 入口 secondary/md 一直可点；只列 explicit 角色且缺省全选；预览 args 恰是 name+roles', async () => {
    const r = render(<PresetSaveAction {...props()} />);
    const entry = btnIn(r.container, ENTRY);
    expect(entry.disabled, '入口一直可点').toBe(false);
    expect(entry.getAttribute('data-variant')).toBe('secondary');
    expect(entry.getAttribute('data-size')).toBe('md');
    fireEvent.click(entry);
    await flush();
    const d = needDlg();
    expect(text(d), '对话框标题').toContain('保存当前为方案');
    const boxes = boxesOf(d);
    expect(boxes.map((b: any) => text(b)), '只列 explicit 的两个，次序照读到的').toEqual(['角色-planning_review', '角色-execution']);
    expect(boxes.every((b: any) => b.getAttribute('aria-checked') === 'true'), '缺省全选').toBe(true);
    const name = inputByLabel(d, '方案名');
    expect(name.className, '方案名等宽字体').toContain('mono');
    expect(text(d), '名字空 → 错误句').toContain('方案名要填');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    fireEvent.change(name, { target: { value: 'demo-save' } });
    await sleep(450);
    await flush();
    const prev = previews().pop();
    expect(prev, '应发过预览').toBeTruthy();
    expect((prev!.body as any).args, 'roles 一律显式带，说明空不带 description').toEqual({ name: 'demo-save', roles: ['planning_review', 'execution'] });
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    expect(text(needDlg()), '底部预览命令').toContain('config preset save demo-save --roles=planning_review,execution');
  });

  it('(b) 不合法名/超长说明当场错误句且不发预览；一个都没勾原因句；勾回一个预览更新', async () => {
    const r = render(<PresetSaveAction {...props()} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    const name = inputByLabel(needDlg(), '方案名');
    fireEvent.change(name, { target: { value: 'Bad Name' } });
    await flush();
    let d = needDlg();
    expect(text(d), '不合法名 → 错误句').toContain('方案名不合法：小写字母、数字与连字符，首字符不能是连字符，最长 64 个字符');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    fireEvent.change(inputByLabel(d, '说明'), { target: { value: '字'.repeat(201) } });
    await sleep(450);
    await flush();
    d = needDlg();
    expect(text(d), '说明超 200 码点 → 错误句').toContain('说明最多 200 个字，不能有控制字符');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    expect(previews().length, '不合法时不调预览').toBe(0);
    fireEvent.change(name, { target: { value: 'good-name' } });
    fireEvent.change(inputByLabel(needDlg(), '说明'), { target: { value: '' } });
    await sleep(450);
    await flush();
    expect(previews().length, '改合法后预览发出').toBe(1);
    fireEvent.click(checkboxByLabel(needDlg(), '角色-planning_review'));
    await sleep(450);
    await flush();
    const half = previews().pop();
    expect((half!.body as any).args.roles, '只勾 execution').toEqual(['execution']);
    const before = previews().length;
    fireEvent.click(checkboxByLabel(needDlg(), '角色-execution'));
    await sleep(450);
    await flush();
    d = needDlg();
    expect(text(d), '一个都没勾 → 原因句').toContain('还没有勾要存的角色');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    expect(previews().length, '一个都没勾时不调预览').toBe(before);
  });

  it('(c) 重名显示会覆盖；不勾覆盖不发预览；勾了正文带布尔 force；改名复位覆盖勾选', async () => {
    const r = render(<PresetSaveAction {...props()} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'default' } });
    await sleep(450);
    await flush();
    let d = needDlg();
    expect(text(d), '重名提示').toContain('会覆盖方案 default');
    const over = checkboxByLabel(d, '覆盖方案 default');
    expect(over.getAttribute('aria-checked'), '覆盖勾选缺省不勾').toBe('false');
    expect(btnIn(d, '确认…').disabled, '不勾覆盖不可确认').toBe(true);
    expect(previews().length, '不勾覆盖不发预览').toBe(0);
    fireEvent.click(over);
    await sleep(450);
    await flush();
    const prev = previews().pop();
    expect(prev, '勾了覆盖才预览').toBeTruthy();
    expect((prev!.body as any).args.force, 'writeArgs 把 force 转成布尔 true').toBe(true);
    expect(text(needDlg()), '命令带 --force').toContain('--force');
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'economy' } });
    await flush();
    d = needDlg();
    expect(checkboxByLabel(d, '覆盖方案 economy').getAttribute('aria-checked'), '改名后覆盖勾选复位').toBe('false');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    fireEvent.change(inputByLabel(d, '方案名'), { target: { value: 'fresh-preset' } });
    await sleep(450);
    await flush();
    d = needDlg();
    expect(text(d), '不重名 → 没有覆盖提示').not.toContain('会覆盖方案');
    expect(qa(d, '[role="checkbox"]').some((b: any) => text(b).indexOf('覆盖方案') === 0), '没有覆盖勾选项').toBe(false);
    const prev2 = previews().pop();
    expect((prev2!.body as any).args.force, '不重名不带 force').toBeUndefined();
    expect(btnIn(d, '确认…').disabled).toBe(false);
  });

  it('(d) 确认先关表单再开确认框；POST 正文无 name 无 force；成功轻提示与 reload；再开按当时数据预填', async () => {
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<PresetSaveAction {...props({ reload })} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'demo-save' } });
    fireEvent.change(inputByLabel(needDlg(), '说明'), { target: { value: '一句说明' } });
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '写确认框标题（表单已关上）').toContain('保存方案 demo-save？');
    expect(text(cd), '写确认框里没有表单字段').not.toContain('方案名');
    expect(text(cd), '变化区摘要').toContain('方案表里加上 demo-save：存 planning_review、execution');
    expect(text(cd), '将运行的命令').toContain('config preset save demo-save --roles=planning_review,execution --description=一句说明');
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(120);
    await flush();
    const writes = saveWrites();
    expect(writes.length, '只发一次写路由').toBe(1);
    expect(writes[0].path).toBe('/api/v1/presets/demo-save/save');
    const wb = writes[0].body as any;
    expect(wb.roles).toEqual(['planning_review', 'execution']);
    expect(wb.description).toBe('一句说明');
    expect(typeof wb.confirmation).toBe('string');
    expect('name' in wb, 'name 走路径段，不在正文').toBe(false);
    expect('force' in wb, '不覆盖不带 force').toBe(false);
    expect(text(document.body), '成功轻提示').toContain('已保存方案 demo-save');
    expect(reload, '成功后 reload').toHaveBeenCalled();
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    const d2 = needDlg();
    const boxes = boxesOf(d2);
    expect(boxes.map((b: any) => text(b)), '写完后再开按当时数据预填').toEqual(['角色-planning_review', '角色-execution']);
    expect(boxes.every((b: any) => b.getAttribute('aria-checked') === 'true'), '再开缺省全选').toBe(true);
    expect(inputByLabel(d2, '方案名').value, '再开名字清空').toBe('');
  });

  it('(d2) 覆盖流：摘要「覆盖方案 default：存 …」；正文 force 是布尔 true；成功轻提示与 reload', async () => {
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<PresetSaveAction {...props({ reload })} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'default' } });
    await sleep(450);
    await flush();
    fireEvent.click(checkboxByLabel(needDlg(), '覆盖方案 default'));
    await sleep(450);
    await flush();
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '覆盖分支的摘要').toContain('覆盖方案 default：存 planning_review、execution');
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(120);
    await flush();
    const writes = saveWrites();
    expect(writes.length).toBe(1);
    expect(writes[0].path).toBe('/api/v1/presets/default/save');
    expect((writes[0].body as any).force, '正文 force 是布尔 true').toBe(true);
    expect(text(document.body), '成功轻提示').toContain('已保存方案 default');
    expect(reload).toHaveBeenCalled();
  });

  it('(e) 一个显式绑定都没有：原因句、确认… 不可点、不发预览；入口仍可点', async () => {
    rolesData = rolesEnvelope({});
    const r = render(<PresetSaveAction {...props()} />);
    const entry = btnIn(r.container, ENTRY);
    expect(entry.disabled, '页头入口不随数据变灰').toBe(false);
    fireEvent.click(entry);
    await flush();
    const d = needDlg();
    expect(text(d), '原因句').toContain('还没有写出绑定的角色：先在角色卡上用 [更改…] 写出绑定');
    expect(boxesOf(d).length, '没有角色勾选项').toBe(0);
    expect(btnIn(d, '确认…').disabled).toBe(true);
    fireEvent.change(inputByLabel(d, '方案名'), { target: { value: 'demo-save' } });
    await sleep(450);
    await flush();
    expect(previews().length, '没有可存的角色时不调预览').toBe(0);
  });

  it('(f) 读不出（roles 或 presets 失败）：原因句、确认… 不可点、不发预览', async () => {
    rolesFail = true;
    const r1 = render(<PresetSaveAction {...props()} />);
    fireEvent.click(btnIn(r1.container, ENTRY));
    await flush();
    let d = needDlg();
    expect(text(d), '读不出 → 原因句').toContain('读不出当前的角色绑定与方案列表：稍后再试');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    await sleep(450);
    await flush();
    expect(previews().length, '读不出时不调预览').toBe(0);
    r1.unmount();
    rolesFail = false;
    presetsFail = true;
    const r2 = render(<PresetSaveAction {...props()} />);
    fireEvent.click(btnIn(r2.container, ENTRY));
    await flush();
    d = needDlg();
    expect(text(d), 'presets 读不出也是同一句').toContain('读不出当前的角色绑定与方案列表：稍后再试');
    expect(btnIn(d, '确认…').disabled).toBe(true);
    await sleep(450);
    await flush();
    expect(previews().length).toBe(0);
  });

  it('(g) 取消再开回到缺省全选；外部改了数据再开按新数据预填', async () => {
    const r = render(<PresetSaveAction {...props()} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    fireEvent.click(checkboxByLabel(needDlg(), '角色-execution'));
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'draft' } });
    await flush();
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单应关上').toBeNull();
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    let d = needDlg();
    const boxes = boxesOf(d);
    expect(boxes.every((b: any) => b.getAttribute('aria-checked') === 'true'), '取消后再开回到缺省全选（丢弃未保存取值）').toBe(true);
    expect(inputByLabel(d, '方案名').value, '取消后再开名字清空').toBe('');
    fireEvent.click(btnIn(d, '取消'));
    await flush();
    rolesData = rolesEnvelope({ execution: true });
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    d = needDlg();
    expect(boxesOf(d).map((b: any) => text(b)), '外部改了绑定后再开按新数据预填').toEqual(['角色-execution']);
    expect(boxesOf(d)[0].getAttribute('aria-checked'), '新清单也缺省全选').toBe('true');
  });
});
'''


STUB_PROBE = r'''// T053 门禁 stub 探针（桩模式）：不注入客户端，读夹具（roles.json 里 planning_review 与 execution 是
// explicit；presets.json 里 default 与 economy）。验证桩的四处接线：baseArgv 的命令逐字（--roles=/
// --description=/--force）、previewData、NEW_ACTIONS、mockSavePreset 的 confirmWrite 参数核对
// （预览与执行同一份 args，对不上回 409，写流程走不到成功轻提示）。真实计时器 sleep(450) 等防抖。
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { PresetSaveAction } from '../src/writes/PresetSaveForm';

const ENTRY = '保存当前为方案…';

const text = (el: any): string => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const qa = (root: any, sel: string): any[] => Array.from(root.querySelectorAll(sel));
const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
async function flush() {
  for (let i = 0; i < 15; i += 1) await act(async () => { await Promise.resolve(); });
}
function btnIn(root: any, label: string): HTMLButtonElement {
  const hit = qa(root, 'button').find((b: any) => text(b) === label);
  expect(hit, '应有按钮「' + label + '」').toBeTruthy();
  return hit as HTMLButtonElement;
}
function dlg(): HTMLElement | null {
  return document.querySelector('[role="dialog"][aria-modal="true"]');
}
function needDlg(): HTMLElement {
  const d = dlg();
  expect(d, '对话框应开着').toBeTruthy();
  return d as HTMLElement;
}
function inputByLabel(d: HTMLElement, labelText: string): HTMLInputElement {
  const label = qa(d, 'label').find((l: any) => text(l) === labelText);
  expect(label, '表单里应有 label「' + labelText + '」').toBeTruthy();
  const hit = qa(d, 'input').find((el: any) => el.id === (label as any).getAttribute('for'));
  expect(hit, 'label 关联的 input 应在表单里').toBeTruthy();
  return hit as HTMLInputElement;
}
function checkboxByLabel(d: HTMLElement, label: string): HTMLElement {
  const hit = qa(d, '[role="checkbox"]').find((b: any) => text(b) === label);
  expect(hit, '应有勾选项「' + label + '」').toBeTruthy();
  return hit as HTMLElement;
}

beforeEach(() => {
  window.location.hash = '';
});
afterEach(() => {
  cleanup();
  window.location.hash = '';
});

describe('PresetSaveAction：桩下的预览命令与写流程（D05）', () => {
  it('(a) 底部预览命令逐字（说明空不带 --description）；确认流走通、成功轻提示与 reload', async () => {
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<PresetSaveAction reload={reload} roleLabel={(c: string) => '角色-' + c} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    const d = needDlg();
    const boxes = qa(d, '[role="checkbox"]').filter((b: any) => text(b).indexOf('角色-') === 0);
    expect(boxes.map((b: any) => text(b)), '夹具里 explicit 的两个').toEqual(['角色-planning_review', '角色-execution']);
    expect(boxes.every((b: any) => b.getAttribute('aria-checked') === 'true')).toBe(true);
    fireEvent.change(inputByLabel(d, '方案名'), { target: { value: 'stub-save' } });
    await sleep(450);
    await flush();
    const bottom = text(needDlg());
    expect(bottom, '命令逐字照 baseArgv（--roles= 连接）').toContain('config preset save stub-save --roles=planning_review,execution');
    expect(bottom, '说明空不带 --description').not.toContain('--description=');
    expect(btnIn(needDlg(), '确认…').disabled).toBe(false);
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '确认框标题').toContain('保存方案 stub-save？');
    expect(text(cd), '变化区摘要').toContain('方案表里加上 stub-save：存 planning_review、execution');
    expect(text(cd), '将运行的命令').toContain('config preset save stub-save --roles=planning_review,execution');
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(120);
    await flush();
    expect(text(document.body), '成功轻提示（confirmWrite 的参数核对通过才走得到）').toContain('已保存方案 stub-save');
    expect(reload).toHaveBeenCalled();
  });

  it('(b) 说明非空命令带 --description=；重名勾覆盖命令带 --force、摘要走覆盖分支、写流程走通', async () => {
    const reload = vi.fn(() => Promise.resolve());
    const r = render(<PresetSaveAction reload={reload} roleLabel={(c: string) => '角色-' + c} />);
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'stub-two' } });
    fireEvent.change(inputByLabel(needDlg(), '说明'), { target: { value: '一句说明' } });
    await sleep(450);
    await flush();
    expect(text(needDlg()), '说明非空命令带 --description=').toContain('--description=一句说明');
    fireEvent.click(btnIn(needDlg(), '取消'));
    await flush();
    expect(dlg(), '取消后表单应关上').toBeNull();
    fireEvent.click(btnIn(r.container, ENTRY));
    await flush();
    fireEvent.change(inputByLabel(needDlg(), '方案名'), { target: { value: 'default' } });
    await sleep(450);
    await flush();
    expect(text(needDlg()), '夹具里的重名').toContain('会覆盖方案 default');
    fireEvent.click(checkboxByLabel(needDlg(), '覆盖方案 default'));
    await sleep(450);
    await flush();
    expect(text(needDlg()), '勾了覆盖命令带 --force').toContain('--force');
    fireEvent.click(btnIn(needDlg(), '确认…'));
    await flush();
    const cd = needDlg();
    expect(text(cd), '覆盖分支的摘要').toContain('覆盖方案 default：存 planning_review、execution');
    fireEvent.click(btnIn(cd, '确认…'));
    await flush();
    await sleep(120);
    await flush();
    expect(text(document.body), '成功轻提示（force 与预览时是同一份 args 才走得到）').toContain('已保存方案 default');
    expect(reload).toHaveBeenCalled();
  });
});
'''


PROBE_SPECS = {
    "form": (FORM_PROBE, (PRESETSAVEFORM_REL, API_REL)),
    "stub": (STUB_PROBE, (PRESETSAVEFORM_REL, MOCKWRITES_REL)),
}
PROBE_ORDER = ("form", "stub")


# ---------------------------------------------------------------------------
# P 系列：流水线断言；D 系列：探针断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、D08：npm 依赖（已在就跳过重装）、npm test（全绿，含执行端新测试与既有包内测试）
    都退出 0；依赖文件一个字节没动；gate-probe/ 没有留下。"""
    assert any(pipeline.steps.get(k) is not None and pipeline.steps[k].code == 0
               for k in ("npm ci", "npm ci --offline")), \
        f"npm ci（含 --offline 兕底）未成功：{pipeline.stopped_reason or pipeline.reason}"
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
    """P2（守卫）：流水线与探针前后 git status 相同；gate-probe/ 没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"


def test_d01_form_probe(pipeline):
    """form 探针 / D01–D04（真实模式，假服务看真实正文）：入口 secondary/md 一直可点；只列 explicit
    角色且缺省全选，预览 args 的 roles 恰是读到的两个（说明空不带 description）；不合法名/超长说明
    当场错误句且不发预览；一个都没勾原因句；重名显示「会覆盖方案 default」，不勾覆盖不发预览，勾了
    正文 force 是布尔 true，改名复位覆盖勾选；确认先关表单再开确认框（标题、摘要、命令）、执行
    POST /api/v1/presets/<name>/save（正文无 name、无 force）、成功轻提示与 reload、再开按当时数据
    预填；覆盖流摘要与正文 force === true；一个显式绑定都没有原因句且入口仍可点；读不出原因句；
    取消再开与外部改数据再开都按当时数据预填。"""
    assert_probe_ok(pipeline, "form")


def test_d02_stub_probe(pipeline):
    """stub 探针 / D05（桩模式，读夹具）：底部预览命令逐字（--roles= 连接、说明空不带 --description、
    说明非空带 --description=）；完整确认流走通（confirmWrite 的参数核对，对不上回 409 走不到成功
    轻提示）、成功轻提示与 reload；重名勾覆盖命令带 --force、摘要走覆盖分支。"""
    assert_probe_ok(pipeline, "stub")
