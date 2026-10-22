"""T014 战前门禁：桌面端前端收尾二（合并 T011、T012 的重复件）的黑盒基准测试
（合同 t014-desktop-cleanup2.v1，plan_version 1，基线 817a1a3507）。

被测对象是 ``desktop/web/``：把 T011、T012 各写一份的复制件（copyText、COPY_RESULT_TEXT、CopyNote）
与三个图标（ArrowRightIcon、FileTextIcon、ExternalLinkIcon）各并成一份共用件
（``src/components/copyText.ts``、新建 ``src/components/CopyNote.tsx``、``src/icons/index.tsx``），
删掉六份重复文件（tasks/tasks-copy.ts、tasks/tasks-icons.tsx、tasks/common-CopyNote.tsx、
shellpages/copy.ts、shellpages/icons.tsx、readonly2/common-icons.tsx），调用方改引用；
顺带修 first-run.css 的 .tt-fr__val 单行省略与 shellStub.ts 的头注释。

基线（817a1a3507）上共用件 CopyNote.tsx 还不存在、六份重复件还在、调用方还从页内模块引入，
所以本文件的"失败"断言落在目标文件不存在或内容不符上，不是导入、收集或语法错误：
模块级只导入标准库，用到被测文件的地方都在用例函数里读。

结构（编号对应合同 DoD 的 D01–D08）：

- 静态断言（不用流水线，全量 pytest 也跑）：单一来源与六份重复件删除（D01）、图标并入共用件且四处渲染不变（D02）、
  共用 CopyNote 与它的样式表（D03）、复制调用方改引用（D04）、.tt-fr__val 单行省略（D05）、
  shellStub.ts 头注释与实现一致（D06）、执行端测试在位且旧断言意图挪到共用件（D08）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：在 ``desktop/web`` 下依次跑
  ``npm ci``、``npm run build``、``npm test``、``npm run check:contract``（V01/V02/V03），并收集 ``dist/assets/*.css``，
  核对 CopyNote.css 的 .tt-copy-note 与 first-run.css 的 .tt-fr__val 省略声明真的进了构建产物（D07 的构建层证据）。
  候选里还没有共用 CopyNote（基线）时不调用 npm，用到夹具的用例以断言失败写明原因。

合同没有写死、门禁端按最合理读法定下的地方（交付信"需协调人决定"里逐条列出，终审可改）：见 ``ASSUMPTIONS``。

过渡断言：``test_transitional_d03_readonly1_reexport_and_overview_import`` 一条（readonly1/common-CopyNote.tsx
只做转出、overview-AttemptList 的引入路径不变），docstring 第一行写明哪项后续工作会推翻它。
"""

import hashlib
import os
import posixpath
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_REL = "desktop/web"
WEB = REPO_ROOT / "desktop" / "web"
SRC_REL = f"{WEB_REL}/src"
SRC = WEB / "src"
COMP_REL = f"{SRC_REL}/components"
COMP = SRC / "components"
ICONS_REL = f"{SRC_REL}/icons/index.tsx"
TASKS_REL = f"{SRC_REL}/pages/tasks"
RO1_REL = f"{SRC_REL}/pages/readonly1"
SP_REL = f"{SRC_REL}/shellpages"
TESTS_REL = f"{WEB_REL}/tests"

# 共用件（合同 Scope、D01、D03）
COPY_TEXT_REL = f"{COMP_REL}/copyText.ts"
COPY_NOTE_REL = f"{COMP_REL}/CopyNote.tsx"
COPY_NOTE_CSS_REL = f"{COMP_REL}/CopyNote.css"
INDEX_REL = f"{COMP_REL}/index.ts"
# 调用方（合同 Steps 3/5/6、D02、D04）
TASK_LIST_REL = f"{TASKS_REL}/TaskListView.tsx"
ATTEMPT_DETAIL_REL = f"{TASKS_REL}/AttemptDetailView.tsx"
TAB_REPORT_REL = f"{TASKS_REL}/tab-Report.tsx"
TAB_SUMMARY_REL = f"{TASKS_REL}/tab-Summary.tsx"
SETTINGS_VIEW_REL = f"{SP_REL}/SettingsView.tsx"
SECRETS_VIEW_REL = f"{SRC_REL}/pages/readonly2/secrets-SecretsView.tsx"
FIRST_RUN_REL = f"{SP_REL}/FirstRunView.tsx"
FIRST_RUN_CSS_REL = f"{SP_REL}/first-run.css"
SHELL_STUB_REL = f"{SP_REL}/shellStub.ts"
RO1_COPY_NOTE_REL = f"{RO1_REL}/common-CopyNote.tsx"
OVERVIEW_ATTEMPT_LIST_REL = f"{RO1_REL}/overview-AttemptList.tsx"
# 合同 Scope allowed_deleted_files：六份重复件
DELETED_DUPES = (
    f"{TASKS_REL}/tasks-copy.ts",
    f"{TASKS_REL}/tasks-icons.tsx",
    f"{TASKS_REL}/common-CopyNote.tsx",
    f"{SP_REL}/copy.ts",
    f"{SP_REL}/icons.tsx",
    f"{SRC_REL}/pages/readonly2/common-icons.tsx",
)
# 合同 Behavior contract：复制三种结果的文字（逐字）
COPY_RESULT_STRINGS = ("这个环境没有剪贴板接口", "已复制", "复制失败")
# 合同 Steps 9、allowed_new_files：执行端三份新测试
NEW_TEST_FILES = ("cleanup2-shared.test.tsx", "cleanup2-render.test.tsx", "cleanup2-static.test.ts")
# 合同 Steps 9：执行端要改的五份旧测试（不删用例、意图挪到共用件）
OLD_TEST_FILES = ("tasks-static.test.ts", "shellpages-static.test.ts", "readonly2-static.test.ts",
                  "cleanup1-static.test.ts", "cleanup1-merge.test.tsx")
# 基线（817a1a3507）上五份旧测试的用例数：D08「不删用例」的下限
OLD_TEST_CASE_COUNTS = {
    "tasks-static.test.ts": 9,
    "shellpages-static.test.ts": 8,
    "readonly2-static.test.ts": 8,
    "cleanup1-static.test.ts": 9,
    "cleanup1-merge.test.tsx": 7,
}
# 合同 D02「path 与合并前逐字相同」：合并前三份重复件里的 path d（与站主核对过的画布逐字相同：
# FileTextIcon=详情页画布 summary.md 那一行/设置画布 :427，ExternalLinkIcon=设置画布 :428）
FILE_TEXT_PATHS = (
    "M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z",
    "M14 2v4a2 2 0 0 0 2 2h4",
    "M10 9H8",
    "M16 13H8",
    "M16 17H8",
)
EXTERNAL_LINK_PATHS = (
    "M15 3h6v6",
    "M10 14 21 3",
    "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6",
)
ARROW_RIGHT_PATHS = ("M5 12h14", "m12 5 7 7-7 7")
# 四处图标渲染的调用方与尺寸（合同 D02：tab-Summary 14、SettingsView 16、secrets 14、FirstRunView 16）
ICON_SITES = (
    (TAB_SUMMARY_REL, "FileTextIcon", 14),
    (SETTINGS_VIEW_REL, "FileTextIcon", 16),
    (SETTINGS_VIEW_REL, "ExternalLinkIcon", 16),
    (SECRETS_VIEW_REL, "ExternalLinkIcon", 14),
    (FIRST_RUN_REL, "ArrowRightIcon", 16),
)
# 基线 icons/index.tsx 的字节数与 sha256（行尾归一为 LF）：证明「只在末尾追加」。
ICONS_BASELINE = (8791, "86d6c1fe6685135c5376423508533ed53b9b65d8f89faaab39f80c6e3615f088")
# 合同 Non-goals「components/index.ts 本片不动」：基线字节数与 sha256，逐字未动。
INDEX_BASELINE = (4346, "db1b506cc08e512e64935952083773169444d83163f4d19cf5dad1b4e48986ff")

ASSUMPTIONS = (
    "D01 扫描范围按合同原文：src/components、src/pages、src/shellpages、src/icons（src/showcase 有演示用的同类文字，天然在范围外）；"
    "「三个图标各只有一处 export const」按规划报告 §7 扫整个 src（画布外的 src/icons/frame.tsx 那一批图标不含这三个名字）",
    "D02「path 与合并前逐字相同」：期望值取自基线三份重复件（站主已核对与画布逐字相同），不随 docs/ui-design 画布文件变动；"
    "「四处渲染的 svg 属性与 path 列表和合并前相同」在源码层验调用方引入路径与 width/height，加共用件里的 Svg 包装与 path 列表，"
    "DOM 级对照由执行端的 cleanup2-render.test.tsx 与 V02 另证",
    "D02 出处注释：按合同 Step 2 原文验「Lucide」「ISC」「file-text」「external-link」与出处（summary.md、设置画布 :427/:428），"
    "并验注释里不出现 <path、<circle、<polygon、<rect（T009 icon_block 会把追加注释算进 ArrowRightIcon 那一块）",
    "D03「文字取 COPY_RESULT_TEXT」：验 CopyNote.tsx 里出现 COPY_RESULT_TEXT[result]，且整个文件（含注释）不出现三条结果文字（T013 D02 按原文搜，注释也算）",
    "D06「头注释与实现一致」：验头注释里 openExternal 那一子句不声称记录网址、且说明校验协议；实现侧验仍是 https? 协议校验、不把 url 存进别处；注释措辞本身留给 review",
    "D08「不删用例」：五份旧测试的 it( 用例数不低于基线（9/8/8/9/7）；「旧断言意图挪到共用件」验三份静态测试改读 src/icons/index.tsx、"
    "cleanup1-static 的 COPY_RESULT_TEXT 那一行改指 components/CopyNote.tsx、cleanup1-merge 改查 .tt-copy-note。"
    "cleanup1-static 的 TOUCHED 清单仍会提到 readonly1/common-CopyNote.tsx（该文件本片要改成转出），所以不整份文件扫这个文件名",
    "D07 回归：V01/V02/V03 由流水线夹具跑（点名运行本文件才跑，全量 pytest 跳过）；R01（T001–T013 门禁）由调度器按合同 Validation commands 单跑，本文件不重复跑",
)

# 合同检查项 V01/V02/V03 的 timeout 是 600s：流水线整体预算压在 560s 以内，用完就停下并在断言里写明，不等调度器来杀。
PIPELINE_BUDGET = 560
STEP_CAPS = {"npm ci": 200, "npm run build": 120, "npm test": 220, "npm run check:contract": 40}
# 流水线前后不该变的文件（相对 desktop/web）：本片不许改的依赖（npm 步骤也不该动它们）
WATCHED = ("package.json", "package-lock.json")


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def need_file(rel):
    """断言仓库里的文件存在，返回路径。基线上到这里就以断言失败。"""
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return path


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:40])


def strip_ts_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)(^|[^:'\"`])//[^\n]*", r"\1", text)


def file_digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def sha_prefix_ok(data, size, digest):
    return len(data) >= size and hashlib.sha256(data[:size]).hexdigest() == digest


# ---------------------------------------------------------------------------
# CSS 小解析器：规则、声明（沿用 T009/T010/T013 的写法）
# ---------------------------------------------------------------------------

def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def split_top(text, sep=","):
    """按顶层 sep 切（圆括号、方括号、引号里的不算）。"""
    parts, buf, depth, quote = [], [], 0, None
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
            continue
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf))
    return [p.strip() for p in parts]


def split_decls(body):
    decls = []
    for part in split_top(body, ";"):
        if not part:
            continue
        name, _sep, value = part.partition(":")
        decls.append((name.strip().lower(), value.strip()))
    return decls


NESTING_AT_RULES = re.compile(r"@(?:media|supports|container|layer|document)\b", re.I)


def norm_ws(value):
    return re.sub(r"\s+", " ", value.strip())


def parse_rules(css):
    """返回 [(选择器, [(名, 值)…])]；@media 等包裹块里的规则展平，@keyframes 不展开。"""
    css = strip_comments(css)
    out = []

    def walk(text):
        i, n = 0, len(text)
        while i < n:
            j = text.find("{", i)
            if j < 0:
                break
            prelude = text[i:j].strip()
            depth, k = 1, j + 1
            while k < n and depth:
                if text[k] == "{":
                    depth += 1
                elif text[k] == "}":
                    depth -= 1
                k += 1
            body = text[j + 1:k - 1]
            if prelude.startswith("@"):
                if NESTING_AT_RULES.match(prelude):
                    walk(body)
            else:
                out.append((norm_ws(prelude), split_decls(body)))
            i = k

    walk(css)
    return out


def cv(value):
    """归一值：去 !important，所有空白去掉，小写。"""
    return re.sub(r"\s+", "", re.sub(r"!important", "", value or "", flags=re.I)).lower()


def is_zero(value):
    return value in ("0", "0px", "0%")


def C(names, eq=None, has=(), zero=False):
    if isinstance(names, str):
        names = (names,)
    return ("decl", tuple(names), eq, tuple(has), zero)


def cond_ok(decls, cond):
    if cond[0] == "decl":
        _tag, names, eq, has, zero = cond
        for name, value in decls:
            if name not in names:
                continue
            v = cv(value)
            if zero:
                if is_zero(v):
                    return True
                continue
            if eq is not None and v != cv(eq):
                continue
            if any(cv(h) not in v for h in has):
                continue
            return True
        return False
    raise AssertionError(f"未知条件 {cond!r}")


def sel_ok(selector, sel):
    if sel is None:
        return True
    if callable(sel):
        return bool(sel(selector))
    return bool(re.search(sel, selector))


def group_problems(css, label, specs):
    """specs: [(说明, 选择器正则/函数或 None, [条件…])]；每条都要有一条规则同时满足全部条件。"""
    problems = []
    rules = parse_rules(css)
    for desc, sel, conds in specs:
        hit = False
        for selector, decls in rules:
            if not sel_ok(selector, sel):
                continue
            if all(cond_ok(decls, c) for c in conds):
                hit = True
                break
        if not hit:
            where = "（带选择器条件）" if sel else ""
            problems.append(f"{label}：{desc}——没有一条规则同时满足{where}")
    return problems


def tok(name):
    return f"var(--tt-{name})"


# ---------------------------------------------------------------------------
# 源码扫描与引入解析
# ---------------------------------------------------------------------------

def src_tsx_files():
    """整个 desktop/web/src 下的 ts/tsx（{仓库相对路径: 文本}）。"""
    files = {}
    for path in sorted(SRC.rglob("*")):
        if path.suffix in (".ts", ".tsx") and path.is_file():
            files[path.relative_to(REPO_ROOT).as_posix()] = _read(path)
    return files


def scan_dirs_tsx(dirs):
    """只扫给定的 src 子目录（合同 D01 的扫描范围）。"""
    files = {}
    for rel in dirs:
        base = REPO_ROOT / rel
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix in (".ts", ".tsx") and path.is_file():
                files[path.relative_to(REPO_ROOT).as_posix()] = _read(path)
    return files


def files_with_literal(files, literal):
    return sorted(rel for rel, text in files.items() if literal in text)


def exported_defs(files, name):
    """返回把 name 作为模块级导出函数/常量定义的文件（export function/const name）。"""
    hits = []
    for rel, text in files.items():
        code = strip_ts_comments(text)
        if re.search(rf"export\s+(?:async\s+)?function\s+{name}\b", code) or re.search(rf"export\s+(?:const|let|var)\s+{name}\b", code):
            hits.append(rel)
    return sorted(hits)


def import_specs_of(code):
    """[(名字列表, 模块说明符)]；含 import type，名字去掉 type 前缀与 as 改名。"""
    out = []
    for m in re.finditer(r"import\s+(?:type\s+)?\{([^}]*)\}\s+from\s+['\"]([^'\"]+)['\"]", code):
        names = []
        for part in m.group(1).split(","):
            part = part.strip()
            if not part:
                continue
            names.append(re.sub(r"^type\s+", "", part).split(" as ")[0].strip())
        out.append((names, m.group(2)))
    return out


def resolve_base(rel_file, spec):
    """把相对引入说明符解析成仓库相对路径（不带扩展名）。"""
    return posixpath.normpath(posixpath.join(posixpath.dirname(rel_file), spec))


def sources_of(rel, name):
    """文件 rel 里名字 name 来自哪些模块说明符。"""
    code = strip_ts_comments(_read(REPO_ROOT / rel))
    return [spec for names, spec in import_specs_of(code) if name in names]


def imports_from(rel, name, want_base):
    """文件 rel 是否从 want_base（仓库相对、不带扩展名）引入 name。"""
    return any(resolve_base(rel, spec) == want_base for spec in sources_of(rel, name))


def arrow_body(code, name):
    """取 ``const name = (…) => { … }`` 的花括号配平函数体；找不到返回 None。"""
    m = re.search(rf"const\s+{name}\s*=\s*\(", code)
    if not m:
        return None
    i = code.find("{", m.end())
    if i < 0:
        return None
    depth, j, n = 1, i + 1, len(code)
    while j < n and depth:
        if code[j] == "{":
            depth += 1
        elif code[j] == "}":
            depth -= 1
        j += 1
    return code[i:j]


# ---------------------------------------------------------------------------
# 图标块解析（沿用 T011 的写法）
# ---------------------------------------------------------------------------

def icon_block(text, name):
    m = re.search(rf"export\s+(?:const|function)\s+{name}\b", text)
    if not m:
        return None
    nxt = re.search(r"\nexport\s+(?:const|function|type|interface)\b", text[m.end():])
    return text[m.start(): m.end() + (nxt.start() if nxt else len(text))]


def tag_attrs(tag_text):
    got = {}
    for m in re.finditer(r"""(\w+)\s*=\s*(?:"([^"]*)"|'([^']*)'|\{\s*["']?([\d.]+)["']?\s*\})""", tag_text):
        got[m.group(1)] = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4))
    return got


def icon_shape_problems(block, name, want_paths, label):
    problems = []
    if "<Svg" not in block:
        problems.append(f"{label}：{name} 应沿用文件里的 Svg 包装")
    paths = [tag_attrs(p).get("d") for p in re.findall(r"<path\b([^>]*)>", block)]
    if paths != list(want_paths):
        problems.append(f"{label}：{name} 的 path d 应依次为 {list(want_paths)}，实际 {paths}")
    for m in re.finditer(r"\b(?:fill|stroke)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|\{[^}]*\})", block):
        value = m.group(1) or m.group(2)
        if value not in ("none", "currentColor"):
            problems.append(f"{label}：{name} 的 fill/stroke 只许 none 或 currentColor，实际 {value!r}")
    return problems


# ---------------------------------------------------------------------------
# 静态断言：D01 单一来源
# ---------------------------------------------------------------------------

def test_d01_copy_text_single_source():
    """D01：在 src/components、src/pages、src/shellpages、src/icons 范围内，copyText 与 COPY_RESULT_TEXT
    只有一处导出定义（components/copyText.ts）；三条结果文字只出现在 components/copyText.ts。"""
    files = scan_dirs_tsx((COMP_REL, f"{SRC_REL}/pages", SP_REL, f"{SRC_REL}/icons"))
    problems = []
    for name in ("copyText", "COPY_RESULT_TEXT"):
        defs = exported_defs(files, name)
        if defs != [COPY_TEXT_REL]:
            problems.append(f"{name} 的导出定义应只在 {COPY_TEXT_REL}，实际 {defs}")
    for s in COPY_RESULT_STRINGS:
        where = files_with_literal(files, s)
        if where != [COPY_TEXT_REL]:
            problems.append(f"「{s}」应只出现在 {COPY_TEXT_REL}，实际 {where}")
    fail_if(problems, "copyText 与结果文字只有一份（D01）")


def test_d01_copy_note_single_source():
    """D01：CopyNote 组件定义（export function/const CopyNote）只在 components/CopyNote.tsx；
    readonly1/common-CopyNote.tsx 改成转出后不再是定义处。"""
    files = scan_dirs_tsx((COMP_REL, f"{SRC_REL}/pages", SP_REL, f"{SRC_REL}/icons"))
    defs = exported_defs(files, "CopyNote")
    fail_if([] if defs == [COPY_NOTE_REL] else [f"CopyNote 的导出定义应只在 {COPY_NOTE_REL}，实际 {defs}"],
            "CopyNote 只有一份（D01）")


def test_d01_icons_single_source():
    """D01：整个 src 里 ArrowRightIcon、FileTextIcon、ExternalLinkIcon 各只有一处 export const，且在 icons/index.tsx。"""
    files = src_tsx_files()
    problems = []
    for name in ("ArrowRightIcon", "FileTextIcon", "ExternalLinkIcon"):
        defs = exported_defs(files, name)
        if defs != [ICONS_REL]:
            problems.append(f"{name} 的 export const 应只在 {ICONS_REL}，实际 {defs}")
    fail_if(problems, "三个图标只有一份（D01）")


def test_d01_deleted_duplicates_gone_and_unimported():
    """D01：合同 Scope 列的六份重复件不存在；src 与 desktop/web/tests 下没有任何文件再从它们引入。"""
    problems = [f"{rel} 仍存在（应删除）" for rel in DELETED_DUPES if (REPO_ROOT / rel).is_file()]
    stems = {rel.rsplit(".", 1)[0] for rel in DELETED_DUPES}
    files = src_tsx_files()
    for path in sorted((WEB / "tests").rglob("*")):
        if path.suffix in (".ts", ".tsx") and path.is_file():
            files[path.relative_to(REPO_ROOT).as_posix()] = _read(path)
    for rel, text in sorted(files.items()):
        code = strip_ts_comments(text)
        for _names, spec in import_specs_of(code):
            if not spec.startswith("."):
                continue
            if resolve_base(rel, spec) in stems:
                problems.append(f"{rel} 仍从已删除模块引入：{spec}")
    fail_if(problems, "六份重复件应删除且无人引入（D01）")


def test_d01_components_index_unchanged():
    """D01 / Non-goals：components/index.ts 本片不动——与基线（817a1a3507）逐字相同。"""
    data = _read(need_file(INDEX_REL)).encode("utf-8")
    size, digest = INDEX_BASELINE
    fail_if([] if sha_prefix_ok(data, size, digest) and len(data) == size else
            [f"components/index.ts 应与基线逐字相同（{size} 字节、sha256 {digest[:12]}…），实际 {len(data)} 字节；"
             f"本合同不许改它（Q4-A，T013 门禁约束）"], "components/index.ts 未动（D01）")


# ---------------------------------------------------------------------------
# 静态断言：D02 图标合并
# ---------------------------------------------------------------------------

def test_d02_icons_appended_to_shared_only():
    """D02：icons/index.tsx 只在末尾追加——基线内容仍是前缀、末尾确实追加了内容；追加部分有
    FileTextIcon（5 条 path）与 ExternalLinkIcon（3 条 path），在 ArrowRightIcon 之后，path 与合并前逐字相同，
    沿用 Svg、块内 fill/stroke 只用 none/currentColor；出处注释写 Lucide/ISC 与画布行，且注释里不出现
    <path、<circle、<polygon、<rect（否定检查只查追加内容里的注释文本，不碰追加的两个图标定义本身）。"""
    path = need_file(ICONS_REL)
    data = _read(path).encode("utf-8")
    problems = []
    size, digest = ICONS_BASELINE
    if not sha_prefix_ok(data, size, digest):
        problems.append("icons/index.tsx：基线内容不是新内容的前缀（只许在末尾追加，不许改已有的行、文件头）")
        fail_if(problems, "icons/index.tsx 追加（D02）")
        return
    appended = data[size:].decode("utf-8", "replace")
    if not appended.strip():
        problems.append("icons/index.tsx 没有在末尾追加内容（基线末端仍是 ArrowRightIcon）")
    text = strip_ts_comments(_read(path))
    pos = {}
    for name, want in (("ArrowRightIcon", ARROW_RIGHT_PATHS), ("FileTextIcon", FILE_TEXT_PATHS), ("ExternalLinkIcon", EXTERNAL_LINK_PATHS)):
        block = icon_block(text, name)
        if block is None:
            problems.append(f"icons/index.tsx 没有 export const {name}")
            continue
        pos[name] = text.find(f"export const {name}")
        problems.extend(icon_shape_problems(block, name, want, "icons/index.tsx"))
    if "ArrowRightIcon" in pos and "FileTextIcon" in pos and not pos["ArrowRightIcon"] < pos["FileTextIcon"]:
        problems.append("FileTextIcon 应追加在 ArrowRightIcon 之后（只在末尾追加）")
    if "FileTextIcon" in pos and "ExternalLinkIcon" in pos and not pos["FileTextIcon"] < pos["ExternalLinkIcon"]:
        problems.append("ExternalLinkIcon 应追加在 FileTextIcon 之后（合同 Step 2 的顺序）")
    # 否定检查只作用于追加内容里的注释文本（合同 Step 2 的「注释里不得出现」）：追加的两个图标定义
    # 本身就含 <path>，拿整段 appended 查会让任何正确实现都恒红（一审阻塞项，:539 与 :555-557）。
    appended_comments = "\n".join(
        m.group(0) for m in re.finditer(r"/\*.*?\*/|(?<![:'\"`])//[^\n]*", appended, re.S))
    for bad in ("<path", "<circle", "<polygon", "<rect"):
        if bad in appended_comments:
            problems.append(f"追加的出处注释里不许出现 {bad}（T009 的 icon_block 会把它算进 ArrowRightIcon 那一块）")
    for want in ("Lucide", "ISC", "file-text", "external-link"):
        if not re.search(re.escape(want), appended, re.I):
            problems.append(f"追加的出处注释里应写明「{want}」（合同 Step 2）")
    for want in ("summary.md", "427", "428"):
        if want not in appended:
            problems.append(f"追加的出处注释里应写出处「{want}」（详情页画布 summary.md 那一行、设置画布 :427 与 :428）")
    fail_if(problems, "icons/index.tsx 追加（D02）")


def test_d02_icon_render_sites_unchanged():
    """D02：四处渲染改从 src/icons 引入，宽度高度照旧（tab-Summary 14、SettingsView 16、secrets 14、FirstRunView 16）；
    svg 属性与 path 列表和合并前相同由共用件那一侧（test_d02_icons_appended_to_shared_only）保证。"""
    problems = []
    icons_base = f"{SRC_REL}/icons"
    for rel, name, size in ICON_SITES:
        if not imports_from(rel, name, icons_base):
            problems.append(f"{rel} 应从 src/icons 引入 {name}，实际来自 {sources_of(rel, name)}")
        code = strip_ts_comments(_read(REPO_ROOT / rel))
        if not re.search(rf"<{name}\s[^>]*?width\s*=\s*\{{\s*{size}\s*\}}\s*[^>]*?height\s*=\s*\{{\s*{size}\s*\}}", code):
            problems.append(f"{rel} 渲染 {name} 时应是 width/height 都是 {size}（与合并前相同）")
    fail_if(problems, "四处图标渲染不变（D02）")


# ---------------------------------------------------------------------------
# 静态断言：D03 共用 CopyNote
# ---------------------------------------------------------------------------

def test_d03_shared_copy_note_module():
    """D03：components/CopyNote.tsx 导出 CopyNote 与 CopyNoteProps；result 为 null 时不渲染；渲染 p、类名 tt-copy-note；
    不设 role；文字取 COPY_RESULT_TEXT；从 '../components' 引入 COPY_RESULT_TEXT 与 CopyResult；顶部 import './CopyNote.css'；
    整个文件（含注释）不出现三条结果文字。"""
    code = strip_ts_comments(_read(need_file(COPY_NOTE_REL)))
    raw = _read(REPO_ROOT / COPY_NOTE_REL)
    problems = []
    if not re.search(r"export\s+(?:function|const)\s+CopyNote\b", code):
        problems.append("CopyNote.tsx 没有导出 CopyNote")
    if not re.search(r"export\s+(?:interface|type)\s+CopyNoteProps\b", code):
        problems.append("CopyNote.tsx 没有导出 CopyNoteProps")
    if not re.search(r"if\s*\([^)]*\bresult\b[^)]*\)\s*\{?\s*return\s+null", code):
        problems.append("CopyNote 在 result 为 null 时应 return null（不渲染任何元素）")
    if not re.search(r"<p\b", code):
        problems.append("CopyNote 应渲染 p 元素")
    if not re.search(r"className\s*=\s*(?:[\"']tt-copy-note[\"']|\{\s*['\"]tt-copy-note['\"]\s*\})", code):
        problems.append("CopyNote 的类名应是 tt-copy-note")
    if re.search(r"\brole\s*=", code):
        problems.append("CopyNote 不设 role")
    if re.search(r"\btoast\b|Toast", code):
        problems.append("CopyNote 不弹轻提示（不出现 toast/Toast）")
    if not re.search(r"COPY_RESULT_TEXT\s*\[", code):
        problems.append("CopyNote 的文字应取 COPY_RESULT_TEXT[result]（不另写字面量）")
    for name in ("COPY_RESULT_TEXT", "CopyResult"):
        if not imports_from(COPY_NOTE_REL, name, COMP_REL):
            problems.append(f"CopyNote.tsx 应从 '../components' 引入 {name}，实际来自 {sources_of(COPY_NOTE_REL, name)}")
    if not re.search(r"import\s+'\./CopyNote\.css'", code):
        problems.append("CopyNote.tsx 顶部应 import './CopyNote.css'（样式表接进产品）")
    for s in COPY_RESULT_STRINGS:
        if s in raw:
            problems.append(f"CopyNote.tsx 里不许出现结果文字「{s}」（含注释；文字只从 COPY_RESULT_TEXT 取）")
    fail_if(problems, "共用 CopyNote（D03）")


def test_d03_copy_note_css():
    """D03：components/CopyNote.css 的 .tt-copy-note 规则有 margin 0、font var(--tt-text-caption)、color var(--tt-text-3)；
    且这份样式表被 CopyNote.tsx import（光写 CSS 没人 import，页面不套用它）。"""
    problems = group_problems(_read(need_file(COPY_NOTE_CSS_REL)), "CopyNote.css",
                              [(".tt-copy-note：margin 0、font var(--tt-text-caption)、color var(--tt-text-3)",
                                lambda s: ".tt-copy-note" in s,
                                [C("margin", zero=True), C("font", eq=tok("text-caption")), C("color", eq=tok("text-3"))])])
    code = strip_ts_comments(_read(need_file(COPY_NOTE_REL)))
    if not re.search(r"import\s+'\./CopyNote\.css'", code):
        problems.append("CopyNote.css 没有被 CopyNote.tsx import（样式表没接进应用）")
    fail_if(problems, "CopyNote 样式（D03）")


def test_transitional_d03_readonly1_reexport_and_overview_import():
    """改 overview-AttemptList.tsx 引入的那一片推翻（AttemptList 改从 components 直接引入 CopyNote、删掉 readonly1/common-CopyNote.tsx）。

    D03：readonly1/common-CopyNote.tsx 只转出 CopyNote 与 CopyNoteProps（from '../../components/CopyNote'），
    不再自己定义组件与私有文字表；overview-AttemptList 的引入路径与导出名不变（仍从 './common-CopyNote' 引入 CopyNote、
    从 '../../components' 引入 copyText），并仍渲染 CopyNote。"""
    problems = []
    code = strip_ts_comments(_read(need_file(RO1_COPY_NOTE_REL)))
    exports = re.findall(r"export\s+(?:type\s+)?\{([^}]*)\}\s+from\s+['\"]([^'\"]+)['\"]", code)
    got = sorted((re.sub(r"^\s*type\s+", "", names).strip(), spec) for names, spec in exports)
    want = sorted([("CopyNote", "../../components/CopyNote"), ("CopyNoteProps", "../../components/CopyNote")])
    if got != want:
        problems.append(f"readonly1/common-CopyNote.tsx 应只转出 CopyNote 与 CopyNoteProps（from '../../components/CopyNote'），实际 {got}")
    if re.search(r"export\s+(?:function|const)\s+CopyNote\b", code):
        problems.append("readonly1/common-CopyNote.tsx 不应再自己定义 CopyNote 组件")
    if re.search(r"export\s+(?:declare\s+)?(?:interface|type)\s+CopyNoteProps\b", code):
        problems.append("readonly1/common-CopyNote.tsx 不应再自己定义 CopyNoteProps")
    for s in COPY_RESULT_STRINGS:
        if s in _read(REPO_ROOT / RO1_COPY_NOTE_REL):
            problems.append(f"readonly1/common-CopyNote.tsx 里不应再出现结果文字「{s}」（转出件不存文字）")
    al = strip_ts_comments(_read(need_file(OVERVIEW_ATTEMPT_LIST_REL)))
    if not imports_from(OVERVIEW_ATTEMPT_LIST_REL, "CopyNote", f"{RO1_REL}/common-CopyNote"):
        problems.append(f"overview-AttemptList 的 CopyNote 引入路径应不变（仍从 './common-CopyNote'），实际 {sources_of(OVERVIEW_ATTEMPT_LIST_REL, 'CopyNote')}")
    if not imports_from(OVERVIEW_ATTEMPT_LIST_REL, "copyText", COMP_REL):
        problems.append(f"overview-AttemptList 的 copyText 应来自 components，实际 {sources_of(OVERVIEW_ATTEMPT_LIST_REL, 'copyText')}")
    if not re.search(r"<CopyNote\b[^>]*result\s*=", al):
        problems.append("overview-AttemptList 仍应渲染 <CopyNote result=…>")
    fail_if(problems, "readonly1 转出（D03，过渡断言）")


# ---------------------------------------------------------------------------
# 静态断言：D04 复制结果文字一致（调用方改引用）
# ---------------------------------------------------------------------------

def test_d04_copy_wiring_merged_sites():
    """D04：T011 三处（TaskListView、AttemptDetailView、tab-Report）CopyNote 改从 components/CopyNote 引入、
    copyText/CopyResult 改从 components 引入，并仍渲染 <CopyNote result=…>；T012（FirstRunView）copyText、
    COPY_RESULT_TEXT、CopyResult 改从 ../components 引入，span.tt-fr__copyres 结构与 COPY_RESULT_TEXT[copyResult] 照旧。"""
    problems = []
    for rel in (TASK_LIST_REL, ATTEMPT_DETAIL_REL, TAB_REPORT_REL):
        if not imports_from(rel, "CopyNote", f"{COMP_REL}/CopyNote"):
            problems.append(f"{rel} 的 CopyNote 应来自 components/CopyNote，实际 {sources_of(rel, 'CopyNote')}")
        for name in ("copyText", "CopyResult"):
            if not imports_from(rel, name, COMP_REL):
                problems.append(f"{rel} 的 {name} 应来自 components，实际 {sources_of(rel, name)}")
        code = strip_ts_comments(_read(REPO_ROOT / rel))
        if not re.search(r"<CopyNote\b[^>]*result\s*=", code):
            problems.append(f"{rel} 仍应渲染 <CopyNote result=…>")
    for name in ("copyText", "COPY_RESULT_TEXT", "CopyResult"):
        if not imports_from(FIRST_RUN_REL, name, COMP_REL):
            problems.append(f"FirstRunView 的 {name} 应来自 ../components，实际 {sources_of(FIRST_RUN_REL, name)}")
    fr = strip_ts_comments(_read(REPO_ROOT / FIRST_RUN_REL))
    if "tt-fr__copyres" not in fr:
        problems.append("FirstRunView 的 span.tt-fr__copyres 结构应照旧（Q2-A：只改引入，不换 CopyNote）")
    if not re.search(r"COPY_RESULT_TEXT\s*\[\s*copyResult\s*\]", fr):
        problems.append("FirstRunView 的结果文字仍应取 COPY_RESULT_TEXT[copyResult]")
    fail_if(problems, "复制调用方改引用（D04）")


# ---------------------------------------------------------------------------
# 静态断言：D05 首启页值单行省略
# ---------------------------------------------------------------------------

def test_d05_first_run_val_single_line_ellipsis():
    """D05：first-run.css 的 .tt-fr__val 用 font var(--tt-mono-md)，加 white-space nowrap、overflow hidden、
    text-overflow ellipsis，保留 flex 1 与 min-width 0；这份样式表仍被 FirstRunView import。"""
    problems = group_problems(_read(need_file(FIRST_RUN_CSS_REL)), "first-run.css",
                              [(".tt-fr__val：font var(--tt-mono-md)、white-space nowrap、overflow hidden、"
                                "text-overflow ellipsis，保留 flex 1 与 min-width 0",
                                lambda s: ".tt-fr__val" in s,
                                [C("font", eq=tok("mono-md")), C("white-space", eq="nowrap"), C("overflow", eq="hidden"),
                                 C("text-overflow", eq="ellipsis"), C("flex", eq="1"), C("min-width", zero=True)])])
    code = strip_ts_comments(_read(need_file(FIRST_RUN_REL)))
    if not re.search(r"import\s+'\./first-run\.css'", code):
        problems.append("FirstRunView.tsx 仍应 import './first-run.css'（样式表接进应用）")
    fail_if(problems, ".tt-fr__val 单行省略（D05）")


# ---------------------------------------------------------------------------
# 静态断言：D06 遗留注释一致
# ---------------------------------------------------------------------------

def test_d06_shellstub_comment_matches_impl():
    """D06：shellStub.ts 头注释与实现一致——openExternal 那一子句不声称记录网址、说明只校验协议；
    实现侧仍是 https? 协议校验，且不把 url 存进别处（不记录网址）。"""
    raw = _read(need_file(SHELL_STUB_REL))
    problems = []
    m = re.search(r"(?m)^import\b", raw)
    header = raw[:m.start()] if m else raw
    clauses = [c.strip() for c in re.split(r"[；;]", header) if c.strip()]
    clause = next((c for c in clauses if "openExternal" in c), None)
    if clause is None:
        problems.append("shellStub.ts 头注释里应有一段讲 openExternal")
    else:
        if re.search(r"记下网址|记录网址|保存网址|记下链接|记录链接", clause):
            problems.append(f"头注释仍声称 openExternal 记录网址（实现只校验协议）：{clause}")
        if not re.search(r"协议|https?", clause, re.I):
            problems.append(f"头注释应说明 openExternal 只校验协议：{clause}")
    code = strip_ts_comments(raw)
    body = arrow_body(code, "openExternal")
    if body is None:
        problems.append("shellStub.ts 里找不到 openExternal 的实现")
    else:
        if not re.search(r"https?", body):
            problems.append("openExternal 的实现应校验协议（http/https）")
        if "push(" in body or re.search(r"\b\w+\s*=\s*url\b", body):
            problems.append("openExternal 的实现不应记录网址（不存入任何变量或集合）")
    fail_if(problems, "shellStub.ts 头注释（D06）")


# ---------------------------------------------------------------------------
# 静态断言：D08 执行端测试在位、干净、旧断言意图挪到共用件
# ---------------------------------------------------------------------------

def test_d08_executor_tests_present_and_clean():
    """D08：执行端三份 cleanup2-* 新测试与五份旧测试都在，各至少一条用例，不出现 skip、only、todo、fails；
    五份旧测试的用例数不低于基线（不删用例）。"""
    problems = []
    folder = WEB / "tests"
    for name in NEW_TEST_FILES + OLD_TEST_FILES:
        path = folder / name
        if not path.is_file():
            problems.append(f"{TESTS_REL}/{name} 不存在（执行端要写的测试）")
            continue
        text = _read(path)
        if not re.search(r"(?m)^\s*it(?:\.each\([^)]*\))?\(", text):
            problems.append(f"{name} 里没有用例")
        for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b"):
            if re.search(bad, text):
                problems.append(f"{name} 里出现 {bad}（不许 skip、only、todo）")
    for name, base in OLD_TEST_CASE_COUNTS.items():
        path = folder / name
        if path.is_file():
            n = len(re.findall(r"(?m)^\s*it(?:\.each\([^)]*\))?\(", _read(path)))
            if n < base:
                problems.append(f"{name} 的用例数 {n} 低于基线 {base}（不删用例）")
    fail_if(problems, "执行端测试（D08）")


def test_d08_old_test_intents_moved_to_shared():
    """D08：旧断言意图挪到共用件上、不削弱——三份静态测试的图标断言改读 src/icons/index.tsx；
    cleanup1-static 的 COPY_RESULT_TEXT 那一行改指 components/CopyNote.tsx；cleanup1-merge 改查 .tt-copy-note。"""
    problems = []
    folder = WEB / "tests"
    for name in ("tasks-static.test.ts", "shellpages-static.test.ts", "readonly2-static.test.ts"):
        path = folder / name
        if not path.is_file():
            problems.append(f"{TESTS_REL}/{name} 不存在")
            continue
        if "src/icons/index.tsx" not in _read(path):
            problems.append(f"{name} 的图标断言应改读 src/icons/index.tsx（合同 Step 9：图标检查改查共用件）")
    static = folder / "cleanup1-static.test.ts"
    if not static.is_file():
        problems.append(f"{TESTS_REL}/cleanup1-static.test.ts 不存在")
    else:
        rows = [line for line in _read(static).splitlines()
                if "COPY_RESULT_TEXT" in line and "plugins-PluginDrawer.tsx" in line]
        if len(rows) != 1:
            problems.append(f"cleanup1-static.test.ts 里应有一行 COPY_RESULT_TEXT 的引入断言，实际 {len(rows)} 行")
        else:
            row = rows[0]
            if "CopyNote.tsx" not in row:
                problems.append(f"cleanup1-static.test.ts 的 COPY_RESULT_TEXT 引入断言应改指 components/CopyNote.tsx：{row.strip()}")
            if "common-CopyNote.tsx" in row:
                problems.append(f"cleanup1-static.test.ts 的 COPY_RESULT_TEXT 引入断言不应再指 readonly1/common-CopyNote.tsx：{row.strip()}")
    merge = folder / "cleanup1-merge.test.tsx"
    if not merge.is_file():
        problems.append(f"{TESTS_REL}/cleanup1-merge.test.tsx 不存在")
    else:
        text = _read(merge)
        if "'.tt-copy-note'" not in text and '".tt-copy-note"' not in text:
            problems.append("cleanup1-merge.test.tsx 应改查 .tt-copy-note（共用 CopyNote 的类名）")
        if "'.common-copy-note'" in text or '".common-copy-note"' in text:
            problems.append("cleanup1-merge.test.tsx 不应再查 .common-copy-note（该类名随 readonly1 转出后不再渲染）")
    fail_if(problems, "旧测试意图挪到共用件（D08）")


# ---------------------------------------------------------------------------
# 流水线：V01/V02/V03 + 构建产物里的新样式（D07）
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
        lines = self.out.splitlines()[-45:]
        return "\n".join(lines)[-3500:]


class Pipeline:
    def __init__(self):
        self.ran = False
        self.reason = ""
        self.steps = {}
        self.stopped_reason = ""
        self.built_css = None
        self.digests_before = {}
        self.digests_after = {}


def _kill_tree(proc):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=60)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        proc.kill()


def run_capture(argv, cwd, timeout, env):
    """跑一条命令，合并 stdout/stderr；超时时连子进程一起杀掉。不用 shell。"""
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
    env.update({"CI": "true", "NO_COLOR": "1", "npm_config_fund": "false", "npm_config_audit": "false",
                "npm_config_update_notifier": "false"})
    env.pop("FORCE_COLOR", None)
    return env


def _collect_built_css():
    assets = WEB / "dist" / "assets"
    if not assets.is_dir():
        return None
    parts = [_read(p) for p in sorted(assets.glob("*.css"))]
    return "\n".join(parts) if parts else ""


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    started = (REPO_ROOT / COPY_NOTE_REL).is_file()
    if not started:
        pipe.reason = ("候选里还没有 src/components/CopyNote.tsx（基线），没有东西可测，未调用 npm；"
                       "执行端写出共用 CopyNote 后，流水线才会运行 npm ci、构建、Vitest 与合同检查")
        return pipe
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        pipe.reason = f"找不到 npm 或 node（shutil.which：npm={npm}，node={node}）"
        return pipe
    pipe.ran = True
    env = _make_env()
    deadline = time.monotonic() + PIPELINE_BUDGET
    pipe.digests_before = {name: file_digest(WEB / name) for name in WATCHED}

    def run_step(name, argv):
        remaining = deadline - time.monotonic()
        if remaining <= 5:
            pipe.stopped_reason = f"{name} 之前整体预算 {PIPELINE_BUDGET}s 已用完，未运行"
            return None
        code, timed_out, out, seconds = run_capture(argv, WEB, min(STEP_CAPS[name], remaining), env)
        step = Step(name, argv, code, timed_out, out, seconds)
        pipe.steps[name] = step
        return step

    try:
        ci = run_step("npm ci", [npm, "ci"])
        if ci is not None and ci.code == 0:
            build = run_step("npm run build", [npm, "run", "build"])
            if build is not None and build.code == 0:
                pipe.built_css = _collect_built_css()
            run_step("npm test", [npm, "test"])
            run_step("npm run check:contract", [npm, "run", "check:contract"])
        elif ci is not None:
            pipe.stopped_reason = "npm ci 失败，后续步骤未运行"
    finally:
        pipe.digests_after = {name: file_digest(WEB / name) for name in WATCHED}
    return pipe


def assert_step_ok(pipe, name):
    assert pipe.ran, pipe.reason
    step = pipe.steps.get(name)
    assert step is not None, f"{name} 未运行：{pipe.stopped_reason or '前置步骤失败'}"
    assert step.code == 0, (f"{name} 退出码 {step.code}{'（超时被杀）' if step.timed_out else ''}，"
                            f"用时 {step.seconds:.0f}s\n--- 输出尾部 ---\n{step.tail}")
    return step


def built_css_problems(built):
    """CopyNote.css 的 .tt-copy-note 与 first-run.css 的 .tt-fr__val 省略声明要出现在构建产物里
    （从源文件解析出的类名与声明，不写死；证明两份样式表真的接进了构建）。"""
    problems = []
    if not re.search(r"\.tt-copy-note(?![\w-])", built):
        problems.append("构建产物 dist/assets/*.css 里找不到 .tt-copy-note（CopyNote.css 没接进构建）")
    m = re.search(r"\.tt-fr__val(?![\w-])\s*\{([^}]*)\}", built)
    if not m:
        problems.append("构建产物里找不到 .tt-fr__val 规则（first-run.css 没接进构建）")
    else:
        body = m.group(1)
        if "text-overflow" not in body or "ellipsis" not in body:
            problems.append(".tt-fr__val 规则里没有 text-overflow: ellipsis（first-run.css 的改动没进构建）")
        if "--tt-mono-md" not in body:
            problems.append(".tt-fr__val 规则里没有 font var(--tt-mono-md)（first-run.css 的改动没进构建）")
    return problems


def test_d07_build_bundles_new_css(pipeline):
    """D07（构建层）：npm run build 成功后，CopyNote.css 的 .tt-copy-note 与 first-run.css 的 .tt-fr__val
    单行省略声明都出现在 dist/assets/*.css 里（T009 的教训：只读 CSS 文本、没人 import 也照样全绿）。"""
    assert pipeline.ran, pipeline.reason
    build = assert_step_ok(pipeline, "npm run build")
    assert pipeline.built_css, f"构建产物里没有 CSS（dist/assets/*.css）：\n{build.tail}"
    fail_if(built_css_problems(pipeline.built_css), "构建产物里的新样式（D07）")


def test_d07_npm_pipeline_passes(pipeline):
    """D07：V01 构建、V02 全量测试、V03 合同检查都通过；流水线没有动 package.json、package-lock.json。"""
    assert pipeline.ran, pipeline.reason
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    changed = [n for n in WATCHED if pipeline.digests_before.get(n) != pipeline.digests_after.get(n)]
    fail_if([f"流水线改了本片不许动的文件：{n}" for n in changed], "流水线副作用的看护文件")
