"""T063 战前门禁（片 B，前端侧）：页面用宿主给的外观起步、跟着外观事件变，紧凑密度生效
（合同 t063-desktop-appearance-web.v1，基线 9da7f2a3——theme.ts 只有 applyTheme、没有密度，
外壳桥与宿主都没有外观函数，App 的主题只存内存，Table.css 没有紧凑规则）。

被测对象（合同「Behavior contract」的逐字语义，不按规划报告的占位名）：

- ``desktop/web/src/shell/theme.ts``：新增 ``DensityPref`` 与 ``applyDensity``（标准去掉
  ``data-density``、紧凑写 ``compact``，只碰 documentElement 的这一个属性）；头注释去掉
  「偏好只存内存」；``applyTheme`` 一行不动、仍是唯一写 ``data-theme`` 的地方。
- ``desktop/web/src/components/Table.css``：现有三条行高规则之后追加三条紧凑规则
  （40→32、44→36、52→44），每条同一行带出处注释；只作用于带 ``data-row-height`` 的 ``td``。
- ``desktop/web/src/shellpages/themisShell.ts``：只补类型 ``ShellAppearance``；
  ``interface ThemisShell`` 仍恰好十个成员；文件仍只导出类型。
- ``desktop/web/src/shellpages/shellBridge.ts``：另导出 ``shellAppearanceNow`` 与
  ``shellOnAppearance``——十成员齐全且 ``getAppearance`` 是函数才调；逐字段校验
  （非法字段取缺省 ``'dark'``/``'standard'``）；不满足能力、抛错、回值不是对象回 ``null``
  或空退订；只有十个成员的旧外壳仍被认作有外壳。
- ``desktop/web/src/live/hostSettings.ts``：新增 ``hostGetAppearance``、``hostOnAppearance``
  、``hostSaveTheme``（只转交 ``pref`` 一个实参、信封原样）；``HostEnvelope`` 补 ``value?``。
- ``desktop/web/src/App.tsx``：主题与密度懒初值（宿主 → 桥 → 缺省暗/标准）、根上订阅外观事件
  （逐字段校验、非法字段忽略）、``useLayoutEffect`` 首帧之前写属性、标题栏三档保存
  （宿主档 ``ok:true`` 才切、桥档兑现后才切、都没有只切内存；失败保持原主题、不弹提示）；
  原文里连注释也不出现 ``data-theme``/``data-density``。
- ``desktop/web/README.md``：改掉「偏好只存内存」，写清外壳保存、启动同步读、改了广播、
  紧凑 40/44/52 各降 8；保留「主题」「标题栏」两词。

基线上这些记号与行为都不存在，所以失败落在「记号不在」与「流水线没跑」这类断言上，
不是收集失败：模块级只导入标准库，仓库文件的读取与探针的运行都发生在用例函数里。
前端流水线（npm 依赖、Vitest、探针）放在 ``pipeline`` 会话级夹具里：全量 pytest 默认跳过
用到它的用例（点名运行本文件才跑）；候选里还没有本片的标记时夹具不调 npm（照 T057/T060
门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线）：theme.ts 的密度写入口（S01）；Table.css 三条紧凑规则
  与同行出处注释（S02）；themisShell.ts 只补类型、接口不动（S03）；shellBridge 两个新导出
  与能力判据记号（S04）；hostSettings 三个新函数与 ``HostEnvelope.value``（S05）；App 的
  接线（useLayoutEffect、宿主优先、禁字样）（S06）；README（S07）。
- 流水线断言（``test_q*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、``npm test``
  全绿（含执行端两个新测试文件）、两份 Vitest 探针逐条核对合同行为：
  - probe:units / D01–D04——applyDensity 的属性写法与不碰别的；Table.css 三条规则的文本；
    shellBridge 两函数的全部失败分支与退订；hostSettings 三函数的能力判据、逐字段校验、
    ``saveTheme`` 恰好一次且只转交一个实参、信封原样。
  - probe:app / D05、D06——桩模式照旧（缺省暗+标准、根元素不多属性、只改内存、不写存储）；
    服务窗口初值来自宿主（首帧即 light/compact）、外观事件逐字段覆盖、非法取值被忽略、
    标题栏三档保存（成功才切、失败保持原主题）、卸载退订；桥档在十成员假外壳下生效；
    「宿主与外壳同时在」两条——初值/订阅/保存都取宿主（桥那边零次），
    宿主同步读回 null 时初值落到桥（审核退回项 3 的行为证据）。

门禁端按最合理读法定下的地方（交付信「下游须知」里列出，终审可改）：

- theme.ts 头注释与 Table.css 文件头说明注释里提到 data-density 不算犯规：S01 在剥注释后的
  代码上计数，S02 与探针一只数含 :root[data-density="compact"] 选择器的行（审核退回项 1、2）。
- 「宿主优先于桥」只在行为上钉（探针二的「宿主与外壳同时在」两条），不钉 App 的 import 次序
  ——次序与运行时优先级无关（审核退回项 3）。

- theme.ts 头注释的新说法只钉「外壳」出现（不逐字钉整句）；README 的新句子同样只钉
  四个要点各自的记号（「同步」「广播」「紧凑」+ 32/36/44）。
- App 的懒初值不在静态上钉 ``useState`` 的写法（执行端可能提成局部函数），由探针的
  「render 之后立刻就是 light/compact」从行为上钉。
- Table.css 的出处注释只钉「同一行有 ``/* */`` 且括号里非空」，不钉注释原文。
"""

import hashlib
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB = REPO_ROOT / "desktop" / "web"

THEME_REL = "desktop/web/src/shell/theme.ts"
TABLECSS_REL = "desktop/web/src/components/Table.css"
TSHELL_REL = "desktop/web/src/shellpages/themisShell.ts"
BRIDGE_REL = "desktop/web/src/shellpages/shellBridge.ts"
HOSTSETTINGS_REL = "desktop/web/src/live/hostSettings.ts"
APP_REL = "desktop/web/src/App.tsx"
README_REL = "desktop/web/README.md"

SHELL_MEMBER_NAMES = (
    "getState", "pickRepo", "pickPython", "pickKit", "pickTranscriptDir",
    "saveSettings", "startService", "restartService", "openExternal", "on",
)

#: Table.css 里紧凑规则的期望：data-row-height 的值 → 紧凑行高。
COMPACT_ROWS = (("40", "32px"), ("44", "36px"), ("52", "44px"))


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
    """断言仓库里的文件存在。基线上到这里就以断言失败。"""
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return path


def tail_text(text, max_chars=3500, max_lines=45):
    text = _ANSI.sub("", text)
    lines = text.splitlines()[-max_lines:]
    joined = "\n".join(lines)
    return joined[-max_chars:]


#: TS 注释剥离（与 t005–t045 各门禁同一口径）：行注释与块注释在同一次从左往右的扫描里认。
#: 「data-density 只许出现在 applyDensity 函数体里」这类计数在剥注释后的代码上做——
#: 头注释里提到它不算犯规（审核退回项 1）。
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


# ---------------------------------------------------------------------------
# JS/TS 源码的区域提取：配平扫描（跳过字符串与注释），不按行号（照 T060 门禁的写法）
# ---------------------------------------------------------------------------

def _match_bracket(text: str, open_at: int) -> int:
    """open_at 处是 '(' 或 '{'：返回与之配平的闭括号下标；配不上回 -1。跳过 // 与 /* */ 注释和字符串。"""
    opener = text[open_at]
    closer = {"(": ")", "{": "}"}[opener]
    depth = 0
    i = open_at
    n = len(text)
    while i < n:
        c = text[i]
        if c == "/" and text[i + 1:i + 2] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if c == "/" and text[i + 1:i + 2] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "'\"`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _call_span(text: str, token: str):
    """token 形如 "useLayoutEffect("：返回那次调用（含括号）的文本；找不到回 None。"""
    at = text.find(token)
    if at < 0:
        return None
    open_at = text.find("(", at)
    end = _match_bracket(text, open_at)
    return None if end < 0 else text[at:end + 1]


def _block_span(text: str, token: str):
    """token 形如 "export function applyDensity("：返回那个函数（含函数体）的文本；找不到回 None。"""
    at = text.find(token)
    if at < 0:
        return None
    open_at = text.find("{", at)
    end = _match_bracket(text, open_at)
    return None if end < 0 else text[at:end + 1]


def _interface_block(text: str, name: str):
    """取 ``export interface <name> {`` 到行首 ``}`` 的块（照外壳解析器的口径，逐成员一行）。"""
    start = text.find(f"export interface {name} {{")
    if start < 0:
        return None
    end = text.find("\n}", start)
    return None if end < 0 else text[start:end]


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_theme_density_api():
    """S01 / D01：theme.ts 的密度写入口——DensityPref 与 applyDensity 逐字在位，只碰 data-density，
    applyTheme 照旧，「偏好只存内存」从注释里退场。"""
    need_file(THEME_REL)
    text = read_rel(THEME_REL)
    assert "export type DensityPref = 'standard' | 'compact';" in text, \
        "theme.ts 要逐字导出 export type DensityPref = 'standard' | 'compact';"
    assert "export function applyDensity(pref: DensityPref): void" in text, \
        "theme.ts 要导出 export function applyDensity(pref: DensityPref): void"
    body = _block_span(text, "export function applyDensity(")
    assert body, "theme.ts 里找不到 applyDensity 的函数体"
    assert re.search(r"removeAttribute\(\s*'data-density'\s*\)", body), \
        "applyDensity 要有 removeAttribute('data-density')（标准密度是去掉属性）"
    assert re.search(r"setAttribute\(\s*'data-density'\s*,\s*'compact'\s*\)", body), \
        "applyDensity 要有 setAttribute('data-density', 'compact')"
    assert "document.documentElement" in body, "applyDensity 只碰 document.documentElement"
    # 唯一写 data-density 的地方：剥注释后计数，头注释里提到它不算犯规（审核退回项 1）。
    # 函数体也在剥注释后的代码上取，函数体内的注释同样不计数。
    code = strip_ts_comments(text)
    code_body = _block_span(code, "export function applyDensity(")
    assert code_body, "applyDensity 的函数体（剥注释后）找不到"
    assert code.count("data-density") == code_body.count("data-density") >= 2, \
        "data-density 只许出现在 applyDensity 的函数体里（注释里提到不算）"
    # 别的东西一概不碰（T006 D06 的口径外加 matchMedia；同样只管代码，不管注释）
    for bad, why in (
        (r"classList", "不许碰 classList"),
        (r"className", "不许碰 className"),
        (r"\.style\b", "不许写内联样式"),
        (r"document\.body", "不许碰 document.body"),
        (r"localStorage", "不许碰 localStorage"),
        (r"sessionStorage", "不许碰 sessionStorage"),
        (r"matchMedia", "不许用 matchMedia"),
    ):
        assert not re.search(bad, code), f"theme.ts {why}"
    # applyTheme 保持现状：仍是唯一写 data-theme 的地方
    theme_body = _block_span(text, "export function applyTheme(")
    assert theme_body, "applyTheme 的函数体要照旧在位"
    assert re.search(r"removeAttribute\(\s*'data-theme'\s*\)", theme_body)
    assert re.search(r"setAttribute\(\s*'data-theme'\s*,", theme_body)
    assert "偏好只存内存" not in text, "头注释要去掉「偏好只存内存」"
    assert "外壳" in text, "头注释要写清偏好由桌面外壳保存一类的新说法（要提到「外壳」）"


def test_s02_table_css_compact_rules():
    """S02 / D02：Table.css 三条紧凑规则（40→32、44→36、52→44）各带同一行出处注释，
    追加在现有三条行高规则之后；只作用于带 data-row-height 的 td，不碰表头。"""
    need_file(TABLECSS_REL)
    text = read_rel(TABLECSS_REL)
    lines = text.splitlines()
    # 只数含 :root[data-density="compact"] 选择器的行：文件头说明注释里提到 data-density 不计数
    # （审核退回项 2）。三条紧凑规则每条各占一行，选择器逐字出现。
    compact_sel = re.compile(r':root\[data-density="compact"\]')
    compact_lines = [(i, line) for i, line in enumerate(lines) if compact_sel.search(line)]
    assert len(compact_lines) == 3, \
        (f"Table.css 里含 :root[data-density=\"compact\"] 选择器的行要恰好三条" \
         f"（现在是 {len(compact_lines)} 条；说明注释里提到 data-density 不计数）")
    for (lineno, line), (height, compact) in zip(compact_lines, COMPACT_ROWS):
        pattern = (r":root\[data-density=\"compact\"\]\s*"
                   r"\.tt-table\[data-row-height=\"" + height + r"\"\]\s*"
                   r"td\s*\{\s*height:\s*" + re.escape(compact) + r";\s*\}")
        sel = line.split("{")[0] if "{" in line else line
        assert re.search(pattern, line), \
            f"第 {lineno + 1} 行应是 :root[data-density=\"compact\"] 的 {height}→{compact} 规则：{line.strip()}"
        assert not re.search(r"\bth\b", sel), f"紧凑规则只许作用于 td，不许匹配表头：{line.strip()}"
        comment_at = line.rfind("/*")
        assert comment_at >= 0 and line.find("*/", comment_at) > comment_at + 2, \
            f"第 {lineno + 1} 行要在同一行带非空的出处注释（T007 的 px 规则）：{line.strip()}"
    # 追加在现有三条行高规则之后（次序与合同一致：40、44、52）
    base_at = text.find('.tt-table[data-row-height="40"] td')
    first_compact_at = text.find(':root[data-density="compact"]')
    assert base_at >= 0 and first_compact_at > base_at, "三条紧凑规则要加在现有三条行高规则之后"
    # Table.css 仍被接进产品（T009 的教训：样式表要真的被 import）
    wired = False
    for ts in (WEB / "src").rglob("*.ts*"):
        if "Table.css" in ts.read_text(encoding="utf-8", errors="replace"):
            wired = True
            break
    assert wired, "components/Table.css 必须仍被 src 里的模块 import"


def test_s03_themis_shell_types_only():
    """S03 / D07：themisShell.ts 只补类型 ShellAppearance（字段照合同），interface ThemisShell
    一个成员都不加（仍恰好十个、on 仍只认 service-state），文件仍只导出类型。"""
    need_file(TSHELL_REL)
    text = read_rel(TSHELL_REL)
    block = _interface_block(text, "ShellAppearance")
    assert block, "themisShell.ts 要有 export interface ShellAppearance {"
    assert re.search(r"theme[?]?\s*:\s*'system'\s*\|\s*'light'\s*\|\s*'dark'\s*;", block), \
        "ShellAppearance.theme 的类型要是 'system' | 'light' | 'dark'"
    assert re.search(r"density[?]?\s*:\s*'standard'\s*\|\s*'compact'\s*;", block), \
        "ShellAppearance.density 的类型要是 'standard' | 'compact'"
    themis = _interface_block(text, "ThemisShell")
    assert themis, "interface ThemisShell 要照旧在位"
    for name in SHELL_MEMBER_NAMES:
        assert re.search(r"^\s+%s\(" % name, themis, re.M), \
            f"interface ThemisShell 的成员 {name} 不见了（一个都不许动）"
    members = [line for line in themis.splitlines() if re.match(r"^\s+\w+\(", line)]
    assert len(members) == 10, \
        f"interface ThemisShell 仍要恰好十个成员（现在是 {len(members)} 个）：\n" + "\n".join(members)
    assert "getAppearance" not in themis, \
        "getAppearance 不许加进 interface ThemisShell（外观类型走 ShellAppearance；外壳解析器钉十个成员）"
    assert re.search(r"on\(event:\s*'service-state'", themis), "ThemisShell.on 的签名要照旧只认 service-state"
    for bad in ("export const", "export function", "export class"):
        assert bad not in text, f"themisShell.ts 仍只导出类型，不许出现 {bad}"


def test_s04_shell_bridge_appearance_exports():
    """S04 / D03：shellBridge 另导出两个外观函数——能力判据（十成员齐全且 getAppearance 是函数）、
    逐字段校验的字面量、appearance 事件名都在；旧导出一行不动（SHELL_MEMBERS 仍十个名字）。"""
    need_file(BRIDGE_REL)
    text = read_rel(BRIDGE_REL)
    for token in (
        "export function shellAppearanceNow",
        "export function shellOnAppearance",
    ):
        assert token in text, f"shellBridge.ts 要另导出 {token}（合同定的正式名）"
    for fn in ("shellAppearanceNow", "shellOnAppearance"):
        body = _block_span(text, "export function %s(" % fn)
        assert body, f"{fn} 的函数体找不到"
    # 能力判据（十成员齐全且 getAppearance 是函数）与 typeof 写法：判据可提成共享小函数，只钉文件里在
    assert "getAppearance" in text, "shellBridge.ts 的能力判据要提到 getAppearance"
    assert "typeof" in text and re.search(r"['\"]function['\"]", text), \
        "shellBridge.ts 要用 typeof 判断成员是不是函数"
    # 逐字段校验与缺省值：同步读里两个缺省字面量都要在
    now_body = _block_span(text, "export function shellAppearanceNow(")
    assert now_body, "shellAppearanceNow 的函数体找不到"
    # 逐字段校验的缺省值可写在共享的小函数里，只钉文件里在
    assert "'dark'" in text and "'standard'" in text, \
        "逐字段校验要取缺省 'dark' 与 'standard'（字面量要在文件里）"
    on_body = _block_span(text, "export function shellOnAppearance(")
    assert on_body, "shellOnAppearance 的函数体找不到"
    assert "'appearance'" in on_body, "shellOnAppearance 要调原对象的 on('appearance', listener)"
    # 旧导出一行不动：十个成员名逐字还在，SHELL_MEMBERS 仍十个名字
    for name in SHELL_MEMBER_NAMES:
        assert "'%s'" % name in text, f"SHELL_MEMBERS 仍要逐字含十个成员名（{name} 不见了）"
    members = re.search(r"export const SHELL_MEMBERS[^=]*=\s*\[([^\]]*)\]", text)
    assert members, "SHELL_MEMBERS 数组要照旧"
    names = re.findall(r"'([a-zA-Z]+)'", members.group(1))
    assert names == list(SHELL_MEMBER_NAMES), \
        f"SHELL_MEMBERS 仍要是那十个名字（现在是 {names}）"
    for legacy in ("export function shellBridgeInstance", "export function unavailableShell",
                   "export function resetShellBridge", "没有连上外壳", "cancelled"):
        assert legacy in text, f"shellBridge.ts 的旧导出与记号要照旧（缺 {legacy}）"


def test_s05_host_settings_appearance_exports():
    """S05 / D04：hostSettings 新增三个宿主函数与 HostEnvelope.value；既有导出与 T060 S06 的
    记号照旧；不写 declare global、不读 window.themisShell、不 import api。"""
    need_file(HOSTSETTINGS_REL)
    text = read_rel(HOSTSETTINGS_REL)
    for token in (
        "export function hostGetAppearance",
        "export function hostOnAppearance",
        "export function hostSaveTheme",
    ):
        assert token in text, f"hostSettings.ts 要新增 {token}（合同定的正式名）"
    envelope = _interface_block(text, "HostEnvelope")
    assert envelope, "HostEnvelope 要照旧在位"
    assert re.search(r"value[?]?\s*:\s*\{\s*theme:\s*string;\s*density:\s*string\s*\}", envelope), \
        "HostEnvelope 要能装下 value（value?: { theme: string; density: string }）"
    for fn, member, back in (("hostGetAppearance", "getAppearance", "return null"),
                             ("hostOnAppearance", "onAppearance", "=>"),
                             ("hostSaveTheme", "saveTheme", "return null")):
        body = _block_span(text, "export function %s(" % fn)
        assert body, f"{fn} 的函数体找不到"
        assert member in body, f"{fn} 里要判 {member} 是不是函数才调（能力判据）"
        assert back in body, f"{fn} 能力不满足/抛错的回退要在（return null 或空退订）"
    assert re.search(r"typeof\s+\w+\s*!==\s*['\"]function['\"]", text), \
        "typeof x !== 'function' 的判断要在（能力判据，T060 S06 的口径）"
    save_body = _block_span(text, "export function hostSaveTheme(")
    assert save_body and re.search(r"\bpref\b", save_body), \
        "hostSaveTheme 只转交 pref 一个实参"
    for legacy in ("hostOpenSettings", "hostHasOpenSettings", "themisHost", "openSettings"):
        assert legacy in text, f"hostSettings.ts 的旧导出与记号要照旧（缺 {legacy}）"
    assert re.search(r"typeof\s+\w+\s*!==\s*['\"]function['\"]", text), \
        "typeof x !== 'function' 的判断要照旧在（T060 S06）"
    assert "declare global" not in text, "不许 declare global（沿用 hostBridge 的类型断言写法）"
    assert not re.search(r"window\s*\.\s*themisShell", text), "hostSettings.ts 不许读 window.themisShell"
    assert not re.search(r"from\s+['\"][^'\"]*api['\"]", text), "hostSettings.ts 不许 import api"


def test_s06_app_wiring_static():
    """S06 / D05、D06：App 的接线——useLayoutEffect 首帧之前写属性（两个 apply 都在里面）、
    标题栏三档要用的名字都在；原文连注释也不出现 data-theme / data-density。
    「宿主优先于桥」不在静态上钉：import 的先后次序与运行时的调用优先级无关（审核退回项 3），
    由探针二的「宿主与外壳同时在」两条用例从行为上钉。"""
    need_file(APP_REL)
    text = read_rel(APP_REL)
    assert "useLayoutEffect" in text, "App 要用 useLayoutEffect 写属性（首帧之前，别用 useEffect）"
    layout = None
    at = text.find("useLayoutEffect(")
    while at >= 0 and layout is None:
        open_at = text.find("(", at)
        end = _match_bracket(text, open_at)
        if end > 0 and "applyTheme(" in text[at:end + 1]:
            layout = text[at:end + 1]
        else:
            at = text.find("useLayoutEffect(", end + 1 if end > 0 else at + 1)
    assert layout, "找不到写着 applyTheme 的那个 useLayoutEffect 调用"
    assert "applyDensity(" in layout, "useLayoutEffect 里要同时写 applyTheme 与 applyDensity"
    assert "applyDensity" in text, "App 要从 ./shell/theme 引 applyDensity"
    for token in ("hostGetAppearance", "hostOnAppearance", "hostSaveTheme",
                  "shellAppearanceNow", "shellOnAppearance", "shellBridgeInstance"):
        assert token in text, f"App 里要有 {token}（合同定的正式名）"
    assert "saveSettings" in text, "桥档要经外壳实例调 saveSettings({ theme: pref })"
    # 宿主优先于桥不在这里钉：import 的先后次序与运行时的调用优先级无关，文本序断言
    # 既会误报照合同顺序写 import 的正确实现、也证不了运行时优先级（审核退回项 3）；
    # 行为证据在探针二的「宿主与外壳同时在」两条用例。
    for bad in ("data-theme", "data-density"):
        assert bad not in text, f"App.tsx 原文（含注释）不许出现 {bad}（属性名只留在 theme.ts）"


def test_s07_readme_appearance():
    """S07 / D08：README 改掉「偏好只存内存」，写清四点（外壳保存、启动同步读、改了广播、
    紧凑 40/44/52 各降 8），保留「主题」「标题栏」两词。"""
    need_file(README_REL)
    text = read_rel(README_REL)
    assert "偏好只存内存" not in text, "README 要改掉「偏好只存内存」"
    lines = text.splitlines()
    appearance = [line for line in lines if "主题" in line or "外观" in line or "紧凑" in line]
    assert any("外壳" in line and ("保存" in line or "存" in line) for line in appearance), \
        "要写清外观由桌面外壳保存（服务窗口经宿主、外壳页经桥）"
    assert any("同步" in line and ("读" in line or "取" in line) for line in appearance), \
        "要写清启动时同步读当前外观"
    assert any("广播" in line for line in appearance), "要写清保存成功后外壳把新外观广播给所有开着的窗口"
    compact = [line for line in lines if "紧凑" in line]
    assert compact, "要写紧凑密度"
    joined = "\n".join(compact)
    for num in ("40", "44", "52", "32", "36"):
        assert num in joined, f"紧凑那几句里要写清 {num}（40/44/52 各降 8 到 32/36/44）"
    assert "主题" in text and "标题栏" in text, "「主题」「标题栏」两词要保留（T006 的 README 断言照旧）"


# ---------------------------------------------------------------------------
# Vitest 探针一（probe:units）：theme.ts / Table.css / shellBridge / hostSettings 的单元行为
# 探针自带全部辅助函数与桩，被测模块只在 it 里动态 import（照 T060 门禁探针的写法）。
# ---------------------------------------------------------------------------

VITEST_PROBE_UNITS = r'''// T063 门禁探针一：外观的单元行为（合同 t063-desktop-appearance-web.v1 的 Behavior contract）。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const MEMBERS = ['getState', 'pickRepo', 'pickPython', 'pickKit', 'pickTranscriptDir',
  'saveSettings', 'startService', 'restartService', 'openExternal', 'on'];

function fakeShell(): Record<string, unknown> {
  return {
    getState: vi.fn(() => Promise.resolve({})),
    pickRepo: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickPython: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickKit: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickTranscriptDir: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    saveSettings: vi.fn(() => Promise.resolve({})),
    startService: vi.fn(() => Promise.resolve(undefined)),
    restartService: vi.fn(() => Promise.resolve(undefined)),
    openExternal: vi.fn(() => Promise.resolve(undefined)),
    on: vi.fn(() => () => {}),
  };
}

beforeEach(() => {
  document.documentElement.removeAttribute('data-theme');
  document.documentElement.removeAttribute('data-density');
});
afterEach(() => {
  delete (window as any).themisShell;
  delete (window as any).themisHost;
});

describe('applyDensity', () => {
  it('紧凑写 data-density=compact，标准去掉属性；不碰 style/class/body/存储', async () => {
    const theme: any = await import('../src/shell/theme');
    const root = document.documentElement;
    const styleBefore = root.getAttribute('style');
    const classBefore = root.className;
    expect(typeof theme.applyDensity).toBe('function');
    theme.applyDensity('compact');
    expect(root.getAttribute('data-density')).toBe('compact');
    theme.applyDensity('standard');
    expect(root.hasAttribute('data-density')).toBe(false);
    theme.applyDensity('compact');
    theme.applyDensity('compact');
    expect(root.getAttribute('data-density')).toBe('compact');
    theme.applyDensity('standard');
    expect(root.hasAttribute('data-density')).toBe(false);
    expect(root.getAttribute('style')).toBe(styleBefore);
    expect(root.className).toBe(classBefore);
    expect(document.body.hasAttribute('data-density')).toBe(false);
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});

describe('Table.css 紧凑规则', () => {
  it('三条规则 40→32、44→36、52→44，各带同行注释，只作用于 td', () => {
    // 这套 Windows + vitest 下 new URL(…, import.meta.url) 不是 file: 地址，读之前就抛
    // TypeError（The URL must be of scheme file，attempt-001 实测）；探针在 desktop/web 下跑，
    // 按 process.cwd() 拼路径读（站主 2026-11-20 拍板，照 t011 探针的 cwd 拼法）。
    const css = readFileSync(resolve(process.cwd(), 'src/components/Table.css'), 'utf8');
    const lines = css.split(/\r?\n/);
    // 只数含选择器的行：文件头说明注释里提到 data-density 不计数（审核退回项 2）。
    const compact = lines.filter((l) => l.indexOf(':root[data-density="compact"]') !== -1);
    expect(compact.length, '含 :root[data-density="compact"] 选择器的行要恰好三条').toBe(3);
    const want = [['40', '32'], ['44', '36'], ['52', '44']];
    compact.forEach((line, i) => {
      const [h, px] = want[i];
      expect(line, `第 ${i} 条紧凑规则要选 data-row-height=${h} 的 td`).toMatch(
        new RegExp(`:root\\[data-density="compact"\\]\\s*\\.tt-table\\[data-row-height="${h}"\\]\\s*td\\s*\\{\\s*height:\\s*${px}px;\\s*\\}`));
      const sel = line.split('{')[0];
      expect(sel, '紧凑规则不许匹配表头').not.toMatch(/\bth\b/);
      expect(line, '同一行要带非空出处注释').toMatch(/\/\*[^*]/);
    });
  });
});

describe('shellAppearanceNow / shellOnAppearance', () => {
  it('十成员齐全且 getAppearance 是函数：同步读透传，订阅经原对象的 on(appearance)', async () => {
    const bridge: any = await import('../src/shellpages/shellBridge');
    const shell: any = fakeShell();
    shell.getAppearance = vi.fn(() => ({ theme: 'light', density: 'compact' }));
    shell.on = vi.fn(() => () => {});
    (window as any).themisShell = shell;
    expect(bridge.shellAppearanceNow()).toEqual({ theme: 'light', density: 'compact' });
    expect(shell.getAppearance.mock.calls.length).toBe(1);
    const got: any[] = [];
    const off = bridge.shellOnAppearance((a: any) => got.push(a));
    expect(shell.on.mock.calls.length, '订阅要调原对象的 on').toBe(1);
    expect(shell.on.mock.calls[0][0]).toBe('appearance');
    expect(typeof off).toBe('function');
    shell.on.mock.calls[0][1]({ theme: 'dark', density: 'standard' });
    expect(got).toEqual([{ theme: 'dark', density: 'standard' }]);
    off();
    shell.on.mock.calls[0][1]({ theme: 'light', density: 'light' as any });
    expect(got.length, '退订之后不再收').toBe(1);
  });

  it('只有十个成员的旧外壳：仍算有外壳，但外观能力按没有处理（回 null / 空退订，不调 on）', async () => {
    const bridge: any = await import('../src/shellpages/shellBridge');
    bridge.resetShellBridge();
    const shell: any = fakeShell();
    (window as any).themisShell = shell;
    expect(bridge.shellBridgeInstance(), '十成员齐全的旧壳仍被认作有外壳').not.toBeNull();
    expect(bridge.shellAppearanceNow()).toBeNull();
    const off = bridge.shellOnAppearance(() => {});
    expect(typeof off).toBe('function');
    expect(shell.on.mock.calls.length, '没有能力就不调 on').toBe(0);
    off();
  });

  it('getAppearance 存在但不是函数：同上（回 null / 空退订，不调）', async () => {
    const bridge: any = await import('../src/shellpages/shellBridge');
    bridge.resetShellBridge();
    const shell: any = fakeShell();
    shell.getAppearance = 42;
    (window as any).themisShell = shell;
    expect(bridge.shellAppearanceNow()).toBeNull();
    expect(typeof bridge.shellOnAppearance(() => {})).toBe('function');
  });

  it('getAppearance 抛错：同步读回 null，不抛到调用方', async () => {
    const bridge: any = await import('../src/shellpages/shellBridge');
    bridge.resetShellBridge();
    const shell: any = fakeShell();
    shell.getAppearance = () => { throw new Error('boom'); };
    (window as any).themisShell = shell;
    expect(bridge.shellAppearanceNow()).toBeNull();
  });

  it('回值不是对象（null / 字符串 / 数字）：回 null，不因字段非法而整体回 null', async () => {
    const bridge: any = await import('../src/shellpages/shellBridge');
    bridge.resetShellBridge();
    for (const bad of [() => null, () => undefined, () => 'x', () => 5]) {
      const shell: any = fakeShell();
      shell.getAppearance = bad;
      (window as any).themisShell = shell;
      expect(bridge.shellAppearanceNow()).toBeNull();
      bridge.resetShellBridge();
    }
    const shell2: any = fakeShell();
    shell2.getAppearance = () => ({ theme: 'neon' });
    (window as any).themisShell = shell2;
    expect(bridge.shellAppearanceNow(), 'theme 非法取缺省 dark').toEqual({ theme: 'dark', density: 'standard' });
    bridge.resetShellBridge();
    const shell3: any = fakeShell();
    shell3.getAppearance = () => ({ theme: 'light', density: null });
    (window as any).themisShell = shell3;
    expect(bridge.shellAppearanceNow(), 'density 非法取缺省 standard').toEqual({ theme: 'light', density: 'standard' });
  });

  it('on(appearance) 抛错：回空退订函数，不抛', async () => {
    const bridge: any = await import('../src/shellpages/shellBridge');
    bridge.resetShellBridge();
    const shell: any = fakeShell();
    shell.getAppearance = vi.fn(() => ({ theme: 'dark', density: 'standard' }));
    shell.on = () => { throw new Error('no-events'); };
    (window as any).themisShell = shell;
    const off = bridge.shellOnAppearance(() => {});
    expect(typeof off).toBe('function');
    expect(() => off()).not.toThrow();
  });
});

describe('hostGetAppearance / hostOnAppearance / hostSaveTheme', () => {
  function installHost(host: Record<string, unknown>) {
    (window as any).themisHost = host;
  }

  it('三个函数齐全：读透传、订阅转发可退订、save 恰好转交一个实参且信封原样', async () => {
    const hs: any = await import('../src/live/hostSettings');
    const saveCalls: any[] = [];
    const offs: any[] = [];
    const heard: any[] = [];
    installHost({
      getAppearance: () => ({ theme: 'system', density: 'compact' }),
      onAppearance: (fn: any) => { offs.push(fn); return () => { offs.length = 0; }; },
      saveTheme: (...args: any[]) => { saveCalls.push(args); return Promise.resolve({ ok: true, value: { theme: args[0], density: 'standard' } }); },
    });
    expect(hs.hostGetAppearance()).toEqual({ theme: 'system', density: 'compact' });
    const off = hs.hostOnAppearance((a: any) => heard.push(a));
    expect(offs.length).toBe(1);
    offs[0]({ theme: 'dark', density: 'compact' });
    expect(heard).toEqual([{ theme: 'dark', density: 'compact' }]);
    off();
    const p = hs.hostSaveTheme('light');
    expect(p).toBeInstanceOf(Promise);
    expect(await p).toEqual({ ok: true, value: { theme: 'light', density: 'standard' } });
    expect(saveCalls, 'saveTheme 恰好调一次、只转交 pref 一个实参').toEqual([['light']]);
  });

  it('旧宿主（只有 reauth）：读回 null、订阅空退订且不被调、保存回 null 且不被调', async () => {
    const hs: any = await import('../src/live/hostSettings');
    const host: any = { reauth: () => {} };
    installHost(host);
    expect(hs.hostGetAppearance()).toBeNull();
    const off = hs.hostOnAppearance(() => {});
    expect(typeof off).toBe('function');
    expect(() => off()).not.toThrow();
    expect(hs.hostSaveTheme('dark')).toBeNull();
  });

  it('getAppearance 缺/不是函数/抛错/回非对象/字段非法：分别回 null 或缺省', async () => {
    const hs: any = await import('../src/live/hostSettings');
    installHost({ openSettings: () => {} });
    expect(hs.hostGetAppearance()).toBeNull();
    installHost({ getAppearance: 42 });
    expect(hs.hostGetAppearance(), '不是函数不调').toBeNull();
    installHost({ getAppearance: () => { throw new Error('boom'); } });
    expect(hs.hostGetAppearance(), '抛错回 null').toBeNull();
    installHost({ getAppearance: () => 'nope' });
    expect(hs.hostGetAppearance(), '回值不是对象回 null').toBeNull();
    installHost({ getAppearance: () => ({ theme: 'neon', density: 'compact' }) });
    expect(hs.hostGetAppearance(), 'theme 非法取缺省').toEqual({ theme: 'dark', density: 'compact' });
    installHost({ getAppearance: () => ({ theme: 'light', density: 9 }) });
    expect(hs.hostGetAppearance(), 'density 非法取缺省').toEqual({ theme: 'light', density: 'standard' });
  });

  it('saveTheme 抛错回 null；onAppearance 回的不是函数或抛错都回空退订', async () => {
    const hs: any = await import('../src/live/hostSettings');
    installHost({ saveTheme: () => { throw new Error('boom'); } });
    expect(hs.hostSaveTheme('dark')).toBeNull();
    installHost({ onAppearance: () => 42 });
    expect(typeof hs.hostOnAppearance(() => {})).toBe('function');
    installHost({ onAppearance: () => { throw new Error('boom'); } });
    expect(typeof hs.hostOnAppearance(() => {})).toBe('function');
    installHost({ saveTheme: () => Promise.reject(new Error('later')) });
    const p: any = hs.hostSaveTheme('dark');
    expect(p).toBeInstanceOf(Promise);
    await expect(p).rejects.toThrow('later');
  });
});
'''


# ---------------------------------------------------------------------------
# Vitest 探针二（probe:app）：App 的桩模式 / 服务窗口（假宿主）/ 桥档与事件 / 卸载退订
# ---------------------------------------------------------------------------

VITEST_PROBE_APP = r'''// T063 门禁探针二：App 用宿主给的外观起步、跟着事件变、标题栏三档保存（合同 Behavior contract）。
// 桩模式照 T012 PROBE_APP 的口径：不装 window.themisShell 也不装 themisHost。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render } from '@testing-library/react';

const MIN_STATE = {
  app: { version: '0.0.0', homepage: 'https://example.com/' },
  settings: { repos: [], currentRepo: null, transcriptDirs: [], theme: 'system', density: 'standard' },
  currentRepoCheck: null,
  python: { status: 'ok', source: 'auto', path: 'C:/Python313/python.exe', version: '3.13.1' },
  kit: { status: 'ok', source: 'repo', path: 'C:/kit', version: '2.12.0' },
  service: { kind: 'idle' },
};

function fakeShell(): any {
  return {
    getState: vi.fn(() => Promise.resolve(JSON.parse(JSON.stringify(MIN_STATE)))),
    pickRepo: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickPython: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickKit: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    pickTranscriptDir: vi.fn(() => Promise.resolve({ kind: 'cancelled' })),
    saveSettings: vi.fn(() => Promise.resolve(JSON.parse(JSON.stringify(MIN_STATE)))),
    startService: vi.fn(() => Promise.resolve(undefined)),
    restartService: vi.fn(() => Promise.resolve(undefined)),
    openExternal: vi.fn(() => Promise.resolve(undefined)),
    on: vi.fn(() => () => {}),
  };
}

function makeHost(appearance: any, saveAnswer: any) {
  const heard: any[] = [];
  const saveCalls: any[] = [];
  const state = { offCalls: 0 };
  const listeners: any[] = [];
  const host: any = {
    getAppearance: appearance === null ? undefined : () => appearance,
    onAppearance: (fn: any) => {
      listeners.push(fn);
      return () => { state.offCalls += 1; listeners.length = 0; };
    },
    saveTheme: saveAnswer === null ? undefined : (...args: any[]) => {
      saveCalls.push(args);
      if (saveAnswer instanceof Error) return Promise.reject(saveAnswer);
      return Promise.resolve(saveAnswer);
    },
    reauth: () => {},
  };
  return { host, listeners, saveCalls, heard, state, deliver: (a: any) => { for (const fn of listeners) fn(a); } };
}

function resetRoot() {
  document.documentElement.removeAttribute('data-theme');
  document.documentElement.removeAttribute('data-density');
}
async function drainNav() {
  for (let i = 0; i < 2; i += 1) await new Promise<void>((r) => setTimeout(r, 0));
}
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
async function mountApp(hash: string) {
  window.location.hash = hash;
  const mod: any = await import('../src/App');
  const out = render(<mod.default />);
  await settle();
  return out;
}
function themeTrigger(): HTMLButtonElement {
  const hit = (Array.from(document.querySelectorAll('button')) as HTMLButtonElement[])
    .filter((b) => (b.getAttribute('aria-label') || '').indexOf('主题：') === 0)[0];
  expect(hit, '找不到主题菜单钮').toBeTruthy();
  return hit as HTMLButtonElement;
}
function themeLabel(): string {
  return (themeTrigger().getAttribute('aria-label') || '').slice('主题：'.length);
}
function pickTheme(label: string) {
  fireEvent.click(themeTrigger());
  const item = (Array.from(document.querySelectorAll('[role="menuitemradio"]')) as HTMLElement[])
    .filter((el) => ((el.textContent || '').replace(/\s+/g, '')).indexOf(label) !== -1)[0];
  expect(item, `菜单里找不到「${label}」`).toBeTruthy();
  fireEvent.click(item as HTMLElement);
}

beforeEach(async () => {
  window.location.hash = '';
  resetRoot();
  await drainNav();
});
afterEach(async () => {
  cleanup();
  delete (window as any).themisShell;
  delete (window as any).themisHost;
  resetRoot();
  try {
    const bridge: any = await import('../src/shellpages/shellBridge');
    bridge.resetShellBridge();
  } catch { /* 基线上还没这个模块时探针自身已红 */ }
  window.location.hash = '';
  await drainNav();
});

describe('桩模式照旧', () => {
  it('缺省暗+标准：根元素不多属性；菜单只改内存；不写存储', async () => {
    const r = await mountApp('#/overview');
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    expect(themeLabel()).toBe('暗');
    pickTheme('亮');
    await settle();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    expect(localStorage.length + sessionStorage.length).toBe(0);
    r.unmount();
  });
});

describe('服务窗口（假宿主）', () => {
  it('起步就是宿主给的外观：render 一返回就是 light/compact，标题栏「主题：亮」', async () => {
    const h = makeHost({ theme: 'light', density: 'compact' }, { ok: true, value: { theme: 'light', density: 'compact' } });
    (window as any).themisHost = h.host;
    window.location.hash = '#/overview';
    const mod: any = await import('../src/App');
    const r = render(<mod.default />);
    expect(document.documentElement.getAttribute('data-theme'), '首帧之前就要写好（懒初值+useLayoutEffect）').toBe('light');
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    await settle();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    expect(themeLabel()).toBe('亮');
    r.unmount();
  });

  it('外观事件逐字段覆盖：{dark,standard} 都去掉；非法字段忽略；非对象实参整个忽略', async () => {
    const h = makeHost({ theme: 'light', density: 'compact' }, null);
    (window as any).themisHost = h.host;
    const r = await mountApp('#/overview');
    await act(async () => { h.deliver({ theme: 'dark', density: 'standard' }); });
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    expect(themeLabel()).toBe('暗');
    await act(async () => { h.deliver({ theme: 'light', density: 'neon' }); });
    expect(document.documentElement.getAttribute('data-theme'), 'density 非法只忽略那一个字段').toBe('light');
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    await act(async () => { h.deliver({ theme: 5, density: 'compact' }); });
    expect(document.documentElement.getAttribute('data-theme'), 'theme 非法只忽略那一个字段').toBe('light');
    expect(document.documentElement.getAttribute('data-density'), '合法的 density 仍生效').toBe('compact');
    await act(async () => { h.deliver('nope'); });
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    r.unmount();
  });

  it('标题栏保存·宿主档：saveTheme 恰好一次且只传 pref；ok:true 才切；失败保持原主题、不弹提示', async () => {
    const h = makeHost({ theme: 'dark', density: 'standard' }, { ok: true, value: { theme: 'light', density: 'standard' } });
    (window as any).themisHost = h.host;
    const r = await mountApp('#/overview');
    pickTheme('亮');
    await settle();
    expect(h.saveCalls, 'saveTheme 恰好调一次、只转交 pref').toEqual([['light']]);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    r.unmount();
  });

  it('标题栏保存·宿主档 ok:false：保持原主题、不重试、不弹带 reason 的提示', async () => {
    const h = makeHost({ theme: 'dark', density: 'standard' }, { ok: false, reason: 'write-failed' });
    (window as any).themisHost = h.host;
    const r = await mountApp('#/overview');
    pickTheme('亮');
    await settle();
    expect(h.saveCalls.length, '失败不重试').toBe(1);
    expect(document.documentElement.hasAttribute('data-theme'), '保持原主题（暗）').toBe(false);
    expect(themeLabel()).toBe('暗');
    expect((document.body.textContent || '').indexOf('write-failed')).toBe(-1);
    r.unmount();
  });

  it('标题栏保存·宿主档 Promise 被拒：保持原主题', async () => {
    const h = makeHost({ theme: 'dark', density: 'standard' }, new Error('boom'));
    (window as any).themisHost = h.host;
    const r = await mountApp('#/overview');
    pickTheme('亮');
    await settle();
    expect(h.saveCalls.length).toBe(1);
    expect(document.documentElement.hasAttribute('data-theme'), '被拒也保持原主题（暗）').toBe(false);
    r.unmount();
  });

  it('卸载退订：off 被调，之后的事件不再到达', async () => {
    const h = makeHost({ theme: 'dark', density: 'standard' }, null);
    (window as any).themisHost = h.host;
    const r = await mountApp('#/overview');
    expect(h.state.offCalls).toBe(0);
    r.unmount();
    expect(h.state.offCalls, '卸载时要退订').toBe(1);
    await act(async () => { h.deliver({ theme: 'light', density: 'compact' }); });
    expect(document.documentElement.hasAttribute('data-theme'), '退订后不再受事件影响').toBe(false);
  });
});

describe('桥档（十成员假外壳，无宿主）', () => {
  it('初值来自桥；标题栏菜单经 saveSettings({ theme }) 保存一次；事件对齐', async () => {
    const shell = fakeShell();
    shell.getAppearance = vi.fn(() => ({ theme: 'dark', density: 'standard' }));
    const appearanceListeners: any[] = [];
    shell.on = vi.fn((event: string, fn: any) => {
      if (event === 'appearance') appearanceListeners.push(fn);
      return () => { appearanceListeners.length = 0; };
    });
    (window as any).themisShell = shell;
    const r = await mountApp('#/overview');
    expect(shell.getAppearance.mock.calls.length, '初值先读桥的同步读').toBeGreaterThanOrEqual(1);
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
    pickTheme('亮');
    await settle();
    expect(shell.saveSettings.mock.calls, '桥档经外壳实例调 saveSettings({ theme: pref })').toEqual([[{ theme: 'light' }]]);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    await act(async () => { for (const fn of appearanceListeners) fn({ theme: 'dark', density: 'compact' }); });
    expect(document.documentElement.hasAttribute('data-theme'), '事件以事件里的值为准').toBe(false);
    expect(document.documentElement.getAttribute('data-density')).toBe('compact');
    r.unmount();
  });

  it('旧外壳（没有外观成员）：仍走桥档保存，订阅不订阅、不抛错', async () => {
    const shell = fakeShell();
    (window as any).themisShell = shell;
    const r = await mountApp('#/overview');
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false);
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    pickTheme('亮');
    await settle();
    expect(shell.saveSettings.mock.calls).toEqual([[{ theme: 'light' }]]);
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(shell.on.mock.calls.filter((c: any[]) => c[0] === 'appearance').length, '没有能力就不订').toBe(0);
    r.unmount();
  });
});

describe('宿主与外壳同时在（优先级，审核退回项 3）', () => {
  it('初值取宿主给的、订阅走 host.onAppearance、保存走 host.saveTheme：桥那边零次', async () => {
    const h = makeHost({ theme: 'light', density: 'compact' }, { ok: true, value: { theme: 'dark', density: 'compact' } });
    (window as any).themisHost = h.host;
    const shell = fakeShell();
    shell.getAppearance = vi.fn(() => ({ theme: 'dark', density: 'standard' }));
    shell.on = vi.fn(() => () => {});
    (window as any).themisShell = shell;
    const r = await mountApp('#/overview');
    expect(document.documentElement.getAttribute('data-theme'), '初值取宿主给的 light，不是桥的 dark').toBe('light');
    expect(document.documentElement.getAttribute('data-density'), '密度也取宿主给的 compact').toBe('compact');
    expect(shell.getAppearance.mock.calls.length, '宿主档读到了就不碰桥的同步读').toBe(0);
    expect(h.listeners.length, '订阅走 host.onAppearance').toBeGreaterThanOrEqual(1);
    expect(shell.on.mock.calls.filter((c: any[]) => c[0] === 'appearance').length, '桥的 on(appearance) 零次').toBe(0);
    pickTheme('暗');
    await settle();
    expect(h.saveCalls, '保存走 host.saveTheme 且只转交 pref').toEqual([['dark']]);
    expect(shell.saveSettings.mock.calls.length, '外壳 saveSettings 零次').toBe(0);
    expect(document.documentElement.hasAttribute('data-theme'), 'ok:true 才切（暗是去掉属性）').toBe(false);
    await act(async () => { h.deliver({ theme: 'light', density: 'standard' }); });
    expect(document.documentElement.getAttribute('data-theme'), '宿主事件生效').toBe('light');
    expect(document.documentElement.hasAttribute('data-density')).toBe(false);
    r.unmount();
  });

  it('宿主 getAppearance 回的不是对象 → hostGetAppearance 回 null → 初值落到外壳桥', async () => {
    const h = makeHost('nope' as any, { ok: true, value: { theme: 'dark', density: 'standard' } });
    (window as any).themisHost = h.host;
    const shell = fakeShell();
    shell.getAppearance = vi.fn(() => ({ theme: 'light', density: 'compact' }));
    (window as any).themisShell = shell;
    const r = await mountApp('#/overview');
    expect(document.documentElement.getAttribute('data-theme'), '宿主读回 null，初值落到桥给的 light').toBe('light');
    expect(document.documentElement.getAttribute('data-density'), '密度落到桥给的 compact').toBe('compact');
    expect(shell.getAppearance.mock.calls.length, '桥的同步读被调了').toBeGreaterThanOrEqual(1);
    r.unmount();
  });
});
'''


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + Vitest 探针（照 T057/T060 门禁的写法；候选里还没有本片标记时不调 npm）
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


def file_digest(path):
    path = Path(path)
    if not path.is_file():
        return None
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return len(data), hashlib.sha256(data).hexdigest()


def t063_marker_present():
    """候选里是否已有 T063 的标记（三个源文件的正式名）：没有就不起 npm（T042 的教训）。"""
    marks = {}
    for rel, needle in ((THEME_REL, "applyDensity"), (BRIDGE_REL, "shellAppearanceNow"),
                        (HOSTSETTINGS_REL, "hostGetAppearance")):
        path = REPO_ROOT / rel
        marks[rel] = needle in _read(path) if path.is_file() else False
    return all(marks.values()), marks


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")

# G01 的超时是 600s：夹具总预算压在 580s 以内（照 T057/T060 门禁）
PIPELINE_BUDGET = 580
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 150}

#: 探针 key → （探针源码，落地文件名的后缀，要用的仓库文件）
PROBES = {
    "units": ("VITEST_PROBE_UNITS", ".test.ts", (THEME_REL, TABLECSS_REL, BRIDGE_REL, HOSTSETTINGS_REL)),
    "app": ("VITEST_PROBE_APP", ".test.tsx", (APP_REL, BRIDGE_REL)),
}


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = "desktop/web/package.json 不存在，未调用 npm"
        return pipe
    present, marks = t063_marker_present()
    if not present:
        missing = [rel for rel, ok in marks.items() if not ok]
        pipe.reason = ("候选里还没有 T063 的标记（" + "、".join(missing) +
                       "），没有东西可测，未调用 npm；候选把入口与接线都放进去之后，"
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
                for key, (source_name, suffix, needed) in PROBES.items():
                    missing = [rel for rel in needed if not (REPO_ROOT / rel).is_file()]
                    if missing:
                        pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                        continue
                    uid = uuid.uuid4().hex[:12]
                    name = f"probe-{uid}-t063-{key}{suffix}"
                    probe_dir.mkdir(exist_ok=True)
                    path = probe_dir / name
                    written.append(path)
                    path.write_text(globals()[source_name], encoding="utf-8", newline="\n")
                    pipe.probe_files[key] = name
                    run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        else:
            pipe.stopped_reason = "npm ci（含 --offline 兑底）失败，后续步骤未运行"
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
        f"\n--- 输出尾部 ---\n{step.tail}")
    return step


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


def assert_probe_ok(pipe, key):
    """探针 key 在候选上全部通过：退出码 0、输出里有探针文件名、通过数不少于 it( 行数、没有失败跳过待办。"""
    assert pipe.ran, pipe.reason
    assert key not in pipe.probe_skipped, pipe.probe_skipped[key]
    step = assert_step_ok(pipe, f"probe:{key}")
    name = pipe.probe_files.get(key)
    assert name and name in step.out.replace("\\", "/"), \
        f"探针输出里没有探针文件名，可能没被 Vitest 选中：\n{step.tail}"
    want = probe_count(globals()[PROBES[key][0]])
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m and int(m.group(1)) >= want, f"探针 {key} 应至少有 {want} 条通过：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), f"探针 {key} 有失败或跳过：\n{step.tail}"


# ---------------------------------------------------------------------------
# Q / D 系列：流水线断言与 Vitest 探针
# ---------------------------------------------------------------------------

def test_q1_pipeline_steps_pass(pipeline):
    """Q1 / V01：npm 依赖（已在就跳过重装）、npm test 全绿（含执行端两个新测试与全部既有测试）
    都退出 0；依赖文件一个字节没动；gate-probe/ 没有留下。"""
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


def test_q2_worktree_unchanged_by_pipeline(pipeline):
    """Q2（守卫）：流水线与探针前后 git status 相同；gate-probe/ 没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"


def test_d01_units_probe(pipeline):
    """D01–D04 / D10：探针一——applyDensity 的写法与不碰到的；Table.css 三条紧凑规则；
    shellBridge 两函数的能力判据与全部失败分支、退订真的能退、十成员旧壳仍算有外壳；
    hostSettings 三函数的能力判据、逐字段校验、saveTheme 恰好一次且只转交 pref、信封原样。"""
    assert_probe_ok(pipeline, "units")


def test_d02_app_probe(pipeline):
    """D05、D06 / D10：探针二——桩模式照旧（缺省、根元素不多属性、只改内存、不写存储）；
    服务窗口首帧就是宿主给的外观、事件逐字段覆盖、非法取值被忽略、卸载退订；
    标题栏三档保存（宿主档成功才切、失败保持原主题；桥档经 saveSettings；都没有只切内存）。"""
    assert_probe_ok(pipeline, "app")
