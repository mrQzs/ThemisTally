"""T013 战前门禁：桌面端前端收尾一（合并 T009、T010 的重复件，补只读页视觉遗留）的黑盒基准测试
（合同 t013-desktop-cleanup1.v1，plan_version 1，基线 fc0a2da）。

被测对象是 ``desktop/web/``：把四样重复件各并成一份共用件（``src/components/`` 下的 copyText.ts、actionTitle.ts，
以及 ActorTag.tsx 追加 actorTone、RelativeTime.tsx 追加 formatLocalUtc），删掉 readonly1/common-copyText.ts、
readonly2/common-copy.ts、readonly2/history-ActorTag.tsx 三份重复件；再补 T009 终审遗留的视觉修整
（指标卡纵向 + 色调条贴左缘 + 图标、.rt-cmd display block、方案表 aria-controls 只在展开时给 + useId、attempt 行名称 --tt-mono-md），
并把 T010 遗留的样式表接线断言（L2）收进本片门禁。

基线（fc0a2da）上共用件还不存在、重复件还在、视觉修整还没做，所以本文件的“失败”断言落在目标文件不存在或内容不符上，
不是导入、收集或语法错误：模块级只导入标准库，用到被测文件的地方都在用例函数里读。

结构（编号对应合同 DoD 的 D01–D10）：

- 静态断言（不用流水线，全量 pytest 也跑）：共用件的导出与逻辑（D01）、没有第二份的扫描（D02）、T009/T010 两侧渲染接线（D03/D04）、
  指标卡 CSS 与 DOM 结构（D05）、.rt-cmd 与 .ov-row__name 的 CSS（D06/D08）、方案表 aria-controls 的源码形状（D07）、
  样式表接线（D09，从 src/main.tsx 顺 import 可达）、执行端五份新测试在位且不用 skip/only/todo（D10）。
- 流水线断言（``pipeline`` 会话级夹具，全量 pytest 默认跳过，点名运行本文件才跑）：在 ``desktop/web`` 下依次跑
  ``npm ci``、``npm run build``、``npm test``、``npm run check:contract``（V01/V02/V03），并收集 ``dist/assets/*.css``，
  核对每份页面样式表独有的类都进了构建产物（D09 的构建层证据）。候选里还没有共用件（基线）时不调用 npm，用到夹具的用例以断言失败写明原因。

合同没有写死、门禁端按最合理读法定下的地方（交付信“需协调人决定”里逐条列出，终审可改）：见 ``ASSUMPTIONS``。

过渡断言：本片不写（任务书要求只写长期断言）。所有断言都指向合并与视觉修整完成后的长期状态。
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
RO1_REL = f"{SRC_REL}/pages/readonly1"
RO1 = SRC / "pages" / "readonly1"
RO2_REL = f"{SRC_REL}/pages/readonly2"
RO2 = SRC / "pages" / "readonly2"
TESTS_REL = f"{WEB_REL}/tests"

# 共用件与重复件（合同 Scope、D01、D02）
COPY_TEXT_REL = f"{COMP_REL}/copyText.ts"
ACTION_TITLE_REL = f"{COMP_REL}/actionTitle.ts"
ACTOR_TAG_REL = f"{COMP_REL}/ActorTag.tsx"
RELATIVE_TIME_REL = f"{COMP_REL}/RelativeTime.tsx"
INDEX_REL = f"{COMP_REL}/index.ts"
METRIC_CARD_REL = f"{RO1_REL}/overview-MetricCard.tsx"
CONFIG_CHANGES_REL = f"{RO1_REL}/overview-ConfigChanges.tsx"
ATTEMPT_LIST_REL = f"{RO1_REL}/overview-AttemptList.tsx"
OVERVIEW_LOGIC_REL = f"{RO1_REL}/overview-logic.ts"
PRESETS_TABLE_REL = f"{RO1_REL}/roles-PresetsTable.tsx"
OVERVIEW_CSS_REL = f"{RO1_REL}/overview-styles.css"
RUNTIMES_CSS_REL = f"{RO1_REL}/runtimes-styles.css"
HISTORY_VIEW_REL = f"{RO2_REL}/history-HistoryView.tsx"
HISTORY_DRAWER_REL = f"{RO2_REL}/history-HistoryDrawer.tsx"
HISTORY_LOGIC_REL = f"{RO2_REL}/history-logic.ts"
PLUGIN_DRAWER_REL = f"{RO2_REL}/plugins-PluginDrawer.tsx"
DELETED_DUPES = (f"{RO1_REL}/common-copyText.ts", f"{RO2_REL}/common-copy.ts", f"{RO2_REL}/history-ActorTag.tsx")
# 执行端要写的五份新测试（合同 allowed_new_files、D10）
NEW_TEST_FILES = ("cleanup1-shared.test.ts", "cleanup1-merge.test.tsx", "cleanup1-visual.test.tsx",
                  "cleanup1-css.test.ts", "cleanup1-static.test.ts")

# readonly1、readonly2 下每份 CSS（D09）
RO1_CSS = ("common-section.css", "overview-styles.css", "roles-styles.css", "runtimes-styles.css")
RO2_CSS = ("common-styles.css", "secrets-styles.css", "logs-styles.css", "plugins-styles.css", "history-styles.css")
ALL_CSS_RELS = tuple(f"{RO1_REL}/{n}" for n in RO1_CSS) + tuple(f"{RO2_REL}/{n}" for n in RO2_CSS)

# 合同 Behavior contract：copyText 三种结果的文字
COPY_RESULT_STRINGS = ("这个环境没有剪贴板接口", "已复制", "复制失败")
# 合同 Behavior contract：13 条动作说明（逐字）
ACTION_TITLES = {
    "config.set": "设置配置键",
    "config.unset": "删除配置键",
    "config.rollback": "回滚配置",
    "preset.use": "切换方案",
    "preset.save": "保存方案",
    "preset.remove": "删除方案",
    "role.set": "修改角色绑定",
    "profile.add": "新建 profile",
    "profile.edit": "修改 profile",
    "profile.remove": "删除 profile",
    "runtime.add": "登记 runtime",
    "runtime.remove": "删除 runtime",
    "external": "检测到界面与命令之外的改动",
}
# 合同 Behavior contract：指标卡图标颜色令牌（各自只引用本卡）
METRIC_ICON_TOKENS = {"running": "tone-info-fg", "review": "accent-text", "decide": "tone-escalate-fg", "integrate": "tone-brand-fg"}

# 基线 components/index.ts（fc0a2da）的字节数与 sha256（行尾归一为 LF）：证明“只在末尾追加”。
INDEX_BASELINE = (3986, "a12cf25c78687f553ceb13385bd697c162d553cc24a988c2dec7c9692c7b3f4e")

ASSUMPTIONS = (
    "合同没规定指标卡图标用哪个图标（Step 5 写“按 Q1”）：门禁只验标签行里有一个 16px 的图标且对读屏隐藏（aria-hidden 写在标签上，或用的是 src/icons 下自带 aria-hidden 的图标组件），不指定具体图标",
    "指标卡“图标颜色规则各自只引用本卡色调令牌”：用 [data-metric=<分组>] 作作用域（组件稳定地写 data-metric），要求该作用域里有一条颜色规则（color/fill/stroke）取本卡令牌且不取另外三卡的令牌；不依赖合同没定的图标类名",
    "D03/D04“渲染与合并前相同”：门禁验接线（总览/历史/插件三侧改用共用件）加共用件取值正确（D01），不在门禁里逐像素对照合并前后",
    "D04“时间格换用 RelativeTime（span 变成带 dateTime 的 time）”：验 HistoryView 对 at 格改用 RelativeTime（其渲染 <time dateTime>），不直接解析 DOM",
    "D07“收起的按钮没有 aria-controls”：源码层验 aria-controls 的取值含 undefined（收起即省略）、面板 id 用 useId 加行序号拼、aria-controls 与面板 id 同源；展开时指向的面板真的在文档里、值不含空白，由执行端的 V02 测试另证",
    "index.ts“只在末尾追加”：验基线内容仍是候选内容的前缀、末尾确实追加了内容、追加部分只涉及四个共用件模块；哪几个名字进桶看消费方的写法——有 readonly1/readonly2 的文件从 '../../components' 桶里引入某个共用件名字时，index.ts 必须导出它（直接写 '../../components/copyText' 引用的不强制进桶）",
    "D09“从 src/main.tsx 顺 import 到达”：静态 import 图可达性（去 import type、去 ?raw 之类查询）；构建产物里是否真有，由流水线的 dist 检查另证",
)

# 合同检查项 V01/V02/V03 的 timeout 是 600s：流水线整体预算压在 560s 以内，用完就停下并在断言里写明，不等调度器来杀。
# 各步上限之和大于总预算，总预算在后面的步骤上起作用（沿用 T009/T010 的门禁写法）。
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
# CSS 小解析器：规则、声明（沿用 T009/T010 的写法）
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


def HasAll(names, *tokens):
    names = (names,) if isinstance(names, str) else tuple(names)

    def check(decls):
        joined = "|".join(cv(v) for n, v in decls if n in names)
        return bool(joined) and all(cv(t) in joined for t in tokens)
    return check


def cond_ok(decls, cond):
    if callable(cond):
        return bool(cond(decls))
    if cond[0] == "any":
        return any(cond_ok(decls, c) for c in cond[1])
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
# D02 扫描：src/components、readonly1、readonly2 下的 ts/tsx
# ---------------------------------------------------------------------------

def d02_scan_files():
    out = {}
    for base in (COMP, RO1, RO2):
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.suffix in (".ts", ".tsx") and p.is_file():
                out[p.relative_to(REPO_ROOT).as_posix()] = _read(p)
    return out


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


def import_sources(code, name):
    """返回从哪些模块说明符 import 了名字 name（含 import type 的也列，调用方自己判 components/本地）。"""
    srcs = []
    for m in re.finditer(r"import\s+(?:type\s+)?\{([^}]*)\}\s+from\s+['\"]([^'\"]+)['\"]", code):
        names = []
        for part in m.group(1).split(","):
            part = part.strip()
            if not part:
                continue
            names.append(re.sub(r"^type\s+", "", part).split(" as ")[0].strip())
        if name in names:
            srcs.append(m.group(2))
    return srcs


def index_exports(text):
    """components/index.ts 导出的名字集合（含 export type 与 as 改名）。"""
    text = strip_ts_comments(text)
    names = set()
    for m in re.finditer(r"export\s+(?:type\s+)?\{([^}]*)\}", text):
        for part in m.group(1).split(","):
            part = re.sub(r"^\s*type\s+", "", part.strip())
            if part:
                names.add(part.split(" as ")[-1].strip())
    return names


def object_pairs(code, name):
    """从 ``<name> … = { … }`` 对象字面量里取出 {'key': 'value'} 对（键可带可不带引号）。
    类型注解（Record<string, string>）里也有花括号，所以先定位名字，再找它后面第一个 ``= {``。"""
    m = re.search(rf"\b{name}\b", code)
    if not m:
        return None
    eq = re.search(r"=\s*\{", code[m.end():])
    if not eq:
        return None
    start = m.end() + eq.end() - 1
    depth, i, n = 1, start + 1, len(code)
    while i < n and depth:
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
        i += 1
    body = code[start + 1:i - 1]
    pairs = {}
    for pm in re.finditer(r"(['\"]?)([\w.\-]+)\1\s*:\s*(['\"])([^'\"]+)\3", body):
        pairs[pm.group(2)] = pm.group(4)
    return pairs


def _jsx_expr(code, attr):
    """取 JSX 属性 ``<attr>={…}`` 里花括号配平后的表达式文本（容忍里面的模板字面量、三元）。"""
    m = re.search(rf"\b{attr}\s*=\s*\{{", code)
    if not m:
        return None
    i = m.end() - 1
    depth, j, n = 1, i + 1, len(code)
    while j < n and depth:
        if code[j] == "{":
            depth += 1
        elif code[j] == "}":
            depth -= 1
        j += 1
    return code[i + 1:j - 1]


# ---------------------------------------------------------------------------
# D09 静态 import 图：从 main.tsx 顺 import 可达（沿用 T009）
# ---------------------------------------------------------------------------

ENTRY_REL = f"{SRC_REL}/main.tsx"
IMPORT_RE = re.compile(r"""(?:\bimport|\bexport)\s*(?P<head>[^'"`;()]*?)\bfrom\s*['"](?P<from>[^'"]+)['"]"""
                       r"""|\bimport\s*['"](?P<bare>[^'"]+)['"]"""
                       r"""|\bimport\s*\(\s*['"](?P<dyn>[^'"]+)['"]\s*\)""")
RESOLVE_SUFFIXES = ("", ".ts", ".tsx", ".css", "/index.ts", "/index.tsx")


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
    base = posixpath.normpath(posixpath.join(posixpath.dirname(current), spec))
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
        if cur.endswith(".css"):
            continue
        for spec in import_specs(files[cur]):
            nxt = resolve_import(files, cur, spec)
            if nxt is not None and nxt not in seen:
                todo.append(nxt)
    return seen


def css_wiring_problems(files, css_rels, entry=ENTRY_REL):
    problems = []
    if entry not in files:
        return [f"{entry} 不存在"]
    reached = reachable_from(files, entry)
    for rel in css_rels:
        if rel not in files:
            problems.append(f"{rel} 不存在")
            continue
        if rel in reached:
            continue
        importers = sorted(cur for cur, text in files.items()
                           if not cur.endswith(".css") and any(resolve_import(files, cur, s) == rel for s in import_specs(text)))
        if importers:
            problems.append(f"{rel} 只被 {importers} 引入，而它们从 {entry} 出发到不了：样式表没进应用")
        else:
            problems.append(f"{rel} 没有任何 .ts/.tsx 以 import 引入（样式表没接线，页面不会套用它）")
    return problems


def src_files_by_rel():
    files = {}
    for path in sorted(SRC.rglob("*")):
        if path.suffix in (".ts", ".tsx", ".css") and path.is_file():
            files[path.relative_to(REPO_ROOT).as_posix()] = _read(path)
    return files


# ---------------------------------------------------------------------------
# 静态断言：D01 共用件
# ---------------------------------------------------------------------------

def test_d01_copytext_shared_module():
    """D01：src/components/copyText.ts 存在，导出 copyText、CopyResult、COPY_RESULT_TEXT；copyText 成功 copied、
    没有 writeText 返回 unavailable、抛错/被拒返回 failed、缺省取 navigator.clipboard；COPY_RESULT_TEXT 三条文字逐字。"""
    code = strip_ts_comments(_read(need_file(COPY_TEXT_REL)))
    problems = []
    if not (re.search(r"export\s+(?:async\s+)?function\s+copyText\b", code) or re.search(r"export\s+const\s+copyText\b", code)):
        problems.append("copyText.ts 没有导出 copyText")
    if not re.search(r"export\s+type\s+CopyResult\b|CopyResult\s*=", code):
        problems.append("copyText.ts 没有导出 CopyResult")
    if not re.search(r"export\s+const\s+COPY_RESULT_TEXT\b", code):
        problems.append("copyText.ts 没有导出 COPY_RESULT_TEXT")
    for s in COPY_RESULT_STRINGS:
        if s not in code:
            problems.append(f"COPY_RESULT_TEXT 少了文字「{s}」")
    for result in ("copied", "unavailable", "failed"):
        if f"'{result}'" not in code and f'"{result}"' not in code:
            problems.append(f"copyText 逻辑里看不到返回 '{result}'")
    if "navigator" not in code:
        problems.append("copyText 缺省应取 navigator.clipboard（源码里看不到 navigator）")
    if not re.search(r"catch", code):
        problems.append("copyText 应有 try/catch：抛错或被拒时返回 failed")
    fail_if(problems, "copyText 共用件（D01）")


def test_d01_actiontitle_shared_module():
    """D01：src/components/actionTitle.ts 存在，导出 ACTION_TITLES（13 条逐字）与 actionTitle；
    用 Object.prototype.hasOwnProperty.call 查表，表外返回 null（由此 Object.prototype 上的名字也返回 null）。"""
    code = strip_ts_comments(_read(need_file(ACTION_TITLE_REL)))
    problems = []
    if not re.search(r"export\s+const\s+ACTION_TITLES\b", code):
        problems.append("actionTitle.ts 没有导出 ACTION_TITLES")
    if not (re.search(r"export\s+function\s+actionTitle\b", code) or re.search(r"export\s+const\s+actionTitle\b", code)):
        problems.append("actionTitle.ts 没有导出 actionTitle")
    pairs = object_pairs(code, "ACTION_TITLES")
    if pairs is None:
        problems.append("读不到 ACTION_TITLES 对象字面量")
    elif pairs != ACTION_TITLES:
        missing = {k: v for k, v in ACTION_TITLES.items() if pairs.get(k) != v}
        extra = {k: v for k, v in pairs.items() if ACTION_TITLES.get(k) != v}
        problems.append(f"ACTION_TITLES 应与合同 13 条逐字相同：缺/错 {missing}，多/错 {extra}")
    if "Object.prototype.hasOwnProperty.call" not in code:
        problems.append("actionTitle 应用 Object.prototype.hasOwnProperty.call 查表（否则表外/原型名不返回 null）")
    if not re.search(r":\s*null|return\s+null|\?\?\s*null", code):
        problems.append("actionTitle 表外应返回 null")
    fail_if(problems, "actionTitle 共用件（D01）")


def test_d01_actortag_exports_actortone():
    """D01：components/ActorTag.tsx 追加导出 actorTone，五类色调（user-ui brand、user neutral、agent: 开头 info、
    undeclared warning、其他 neutral）；ActorTag、ActorTagProps 名字与属性（actor 必填、className 可选）不变。"""
    code = strip_ts_comments(_read(need_file(ACTOR_TAG_REL)))
    problems = []
    if not re.search(r"export\s+function\s+actorTone\b|export\s+const\s+actorTone\b", code):
        problems.append("ActorTag.tsx 没有导出 actorTone")
    m = re.search(r"(?:export\s+)?function\s+actorTone\b[^{]*\{", code)
    if not m:
        problems.append("找不到 actorTone 函数体")
    else:
        start = m.end() - 1
        depth, i, n = 1, start + 1, len(code)
        while i < n and depth:
            if code[i] == "{":
                depth += 1
            elif code[i] == "}":
                depth -= 1
            i += 1
        body = code[start:i]
        for cond, tone in (("'user-ui'", "brand"), ("'agent:'", "info"), ("'undeclared'", "warning")):
            if not re.search(rf"{re.escape(cond)}[^;}}]*'{tone}'", body) and not re.search(rf"'{tone}'[^;}}]*{re.escape(cond)}", body):
                problems.append(f"actorTone 应把 {cond} 归为 '{tone}'")
        if not re.search(r"return\s+'neutral'", body):
            problems.append("actorTone 的兜底/其他应返回 'neutral'")
        # 若有显式的 'user' 分支（注意 'user-ui' 不含独立的 'user'），必须归到 neutral；没有该分支则走兜底 neutral。
        if re.search(r"actor\s*===\s*'user'", body) and not re.search(r"actor\s*===\s*'user'[^;}]*'neutral'", body):
            problems.append("actorTone 对 'user' 应返回 'neutral'")
    if not re.search(r"export\s+function\s+ActorTag\b|export\s+const\s+ActorTag\b", code):
        problems.append("ActorTag.tsx 仍应导出 ActorTag")
    if not re.search(r"export\s+(?:interface|type)\s+ActorTagProps\b", code):
        problems.append("ActorTag.tsx 仍应导出 ActorTagProps")
    if not re.search(r"\bactor\s*:", code) or "className" not in code:
        problems.append("ActorTagProps 应保留 actor（必填）与 className（可选）两个属性")
    fail_if(problems, "ActorTag actorTone（D01）")


def test_d01_relativetime_exports_formatlocalutc():
    """D01：components/RelativeTime.tsx 追加导出 formatLocalUtc，格式「YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）」，
    解析不了返回 null；RelativeTime 仍渲染 <time dateTime=原文 title=formatLocalUtc>；RelativeTime、RelativeTimeProps 名字与属性不变。"""
    code = strip_ts_comments(_read(need_file(RELATIVE_TIME_REL)))
    problems = []
    if not re.search(r"export\s+function\s+formatLocalUtc\b|export\s+const\s+formatLocalUtc\b", code):
        problems.append("RelativeTime.tsx 没有导出 formatLocalUtc")
    if "（UTC " not in code:
        problems.append("formatLocalUtc 的格式应含全角括号里的「（UTC 」")
    if not re.search(r"return\s+null", code):
        problems.append("formatLocalUtc 解析不了应返回 null")
    if not re.search(r"<time\b", code) or not re.search(r"dateTime\s*=\s*\{\s*iso\s*\}", code):
        problems.append("RelativeTime 仍应渲染 <time dateTime={iso}>")
    if not re.search(r"export\s+function\s+RelativeTime\b|export\s+const\s+RelativeTime\b", code):
        problems.append("RelativeTime.tsx 仍应导出 RelativeTime")
    if not re.search(r"export\s+(?:interface|type)\s+RelativeTimeProps\b", code):
        problems.append("RelativeTime.tsx 仍应导出 RelativeTimeProps")
    for prop in ("iso", "now", "className"):
        if not re.search(rf"\b{prop}\s*\??\s*:", code):
            problems.append(f"RelativeTimeProps 应保留属性 {prop}")
    fail_if(problems, "RelativeTime formatLocalUtc（D01）")


def test_d01_index_append_only_and_new_exports():
    """D01：components/index.ts 只在末尾追加——基线内容（fc0a2da）仍是候选内容的前缀，末尾确实追加了内容，
    且追加的部分只涉及四个共用件模块；消费方从 '../../components' 桶里引入的共用件名字，index.ts 必须导出。"""
    data = _read(need_file(INDEX_REL)).encode("utf-8")
    problems = []
    size, digest = INDEX_BASELINE
    if not sha_prefix_ok(data, size, digest):
        problems.append("components/index.ts：基线内容不是新内容的前缀（只许在末尾追加，不许改已有的行、文件头）")
    appended = data[size:].decode("utf-8", "replace")
    if not appended.strip():
        problems.append("components/index.ts 没有在末尾追加内容")
    for m in re.finditer(r"from\s+'\./([^']+)'", appended):
        if m.group(1) not in ("copyText", "actionTitle", "ActorTag", "RelativeTime"):
            problems.append(f"index.ts 末尾追加的部分引入了合同外的模块 './{m.group(1)}'")
    names = index_exports(data.decode("utf-8", "replace"))
    needed = set()
    for base in (RO1, RO2):
        for p in sorted(base.rglob("*")):
            if p.suffix not in (".ts", ".tsx") or not p.is_file():
                continue
            code = strip_ts_comments(_read(p))
            for m in re.finditer(r"import\s+(?:type\s+)?\{([^}]*)\}\s+from\s+['\"](?:\.\./)*components['\"]", code):
                for part in m.group(1).split(","):
                    part = re.sub(r"^\s*type\s+", "", part.strip())
                    if part:
                        needed.add(part.split(" as ")[0].strip())
    for name in ("copyText", "CopyResult", "COPY_RESULT_TEXT", "actionTitle", "ACTION_TITLES", "actorTone", "formatLocalUtc"):
        if name in needed and name not in names:
            problems.append(f"有 readonly1/readonly2 的文件从 '../../components' 桶里引入 {name}，但 index.ts 没有导出它")
    fail_if(problems, "components/index.ts 追加（D01）")


# ---------------------------------------------------------------------------
# 静态断言：D02 没有第二份
# ---------------------------------------------------------------------------

def test_d02_copytext_single_source():
    """D02：在 src/components、readonly1、readonly2 范围内，copyText 只有一处导出定义（components/copyText.ts）；
    「这个环境没有剪贴板接口」「已复制」「复制失败」只出现在 components/copyText.ts。"""
    files = d02_scan_files()
    problems = []
    defs = exported_defs(files, "copyText")
    if defs != [COPY_TEXT_REL]:
        problems.append(f"copyText 的导出定义应只在 {COPY_TEXT_REL}，实际 {defs}")
    for s in COPY_RESULT_STRINGS:
        where = files_with_literal(files, s)
        if where != [COPY_TEXT_REL]:
            problems.append(f"「{s}」应只出现在 {COPY_TEXT_REL}，实际 {where}")
    fail_if(problems, "copyText 只有一份（D02）")


def test_d02_action_titles_single_source():
    """D02：13 条动作说明只出现在 components/actionTitle.ts。"""
    files = d02_scan_files()
    problems = []
    for value in ACTION_TITLES.values():
        where = files_with_literal(files, value)
        if where != [ACTION_TITLE_REL]:
            problems.append(f"动作说明「{value}」应只出现在 {ACTION_TITLE_REL}，实际 {where}")
    fail_if(problems, "动作说明只有一份（D02）")


def test_d02_actortag_single_source():
    """D02：ActorTag 组件只有一处导出定义（components/ActorTag.tsx）；带引号的 undeclared 只出现在 components/ActorTag.tsx。"""
    files = d02_scan_files()
    problems = []
    defs = exported_defs(files, "ActorTag")
    if defs != [ACTOR_TAG_REL]:
        problems.append(f"ActorTag 的导出定义应只在 {ACTOR_TAG_REL}，实际 {defs}")
    where = sorted(rel for rel, text in files.items() if "'undeclared'" in text or '"undeclared"' in text)
    if where != [ACTOR_TAG_REL]:
        problems.append(f"带引号的 undeclared 应只出现在 {ACTOR_TAG_REL}，实际 {where}")
    fail_if(problems, "ActorTag 只有一份（D02）")


def test_d02_formatlocalutc_single_source():
    """D02：「（UTC 」拼写只出现在 components/RelativeTime.tsx（readonly2/common-format.ts 的 formatLocalUtc 已移除）。"""
    files = d02_scan_files()
    where = files_with_literal(files, "（UTC ")
    fail_if([] if where == [RELATIVE_TIME_REL] else [f"「（UTC 」应只出现在 {RELATIVE_TIME_REL}，实际 {where}"],
            "formatLocalUtc 只有一份（D02）")


def test_d02_deleted_duplicates_gone():
    """D02：readonly1/common-copyText.ts、readonly2/common-copy.ts、readonly2/history-ActorTag.tsx 不存在。"""
    problems = [f"{rel} 仍存在（应删除）" for rel in DELETED_DUPES if (REPO_ROOT / rel).is_file()]
    fail_if(problems, "重复件应删除（D02）")


def test_d02_consumers_import_from_components():
    """D02：readonly1、readonly2 用到这几样时只从 components 引入，不再从被删的 common-copyText / common-copy / history-ActorTag 引入。"""
    files = d02_scan_files()
    bad_local = re.compile(r"from\s+['\"](?:\.\.?/)*(?:common-copyText|common-copy|history-ActorTag)['\"]")
    problems = []
    for rel, text in files.items():
        code = strip_ts_comments(text)
        for m in bad_local.finditer(code):
            problems.append(f"{rel} 仍从被删模块引入：{m.group(0)}")
    fail_if(problems, "只从 components 引入（D02）")


# ---------------------------------------------------------------------------
# 静态断言：D03 / D04 渲染接线不变
# ---------------------------------------------------------------------------

def test_d03_overview_render_wiring():
    """D03：总览配置变更改用共用件——ConfigChanges 从 components 引入 ActorTag 与 RelativeTime，并用动作中文表（actionLabel/actionTitle）；
    AttemptList 从 components 引入 copyText 并渲染 CopyNote；复制三结果文字与合并前相同（由 D01/D02 保证只在 copyText.ts）。"""
    problems = []
    cc = strip_ts_comments(_read(need_file(CONFIG_CHANGES_REL)))
    for name in ("ActorTag", "RelativeTime"):
        srcs = import_sources(cc, name)
        if not any("components" in s for s in srcs):
            problems.append(f"overview-ConfigChanges 应从 components 引入 {name}，实际来自 {srcs}")
    if not re.search(r"actionLabel\s*\(|actionTitle\s*\(", cc):
        problems.append("overview-ConfigChanges 仍应给动作挂中文 title（actionLabel/actionTitle）")
    al = strip_ts_comments(_read(need_file(ATTEMPT_LIST_REL)))
    ct = import_sources(al, "copyText")
    if not any("components" in s for s in ct):
        problems.append(f"overview-AttemptList 应从 components 引入 copyText，实际来自 {ct}")
    if "CopyNote" not in al:
        problems.append("overview-AttemptList 仍应渲染 CopyNote（复制三结果文字）")
    ol = strip_ts_comments(_read(need_file(OVERVIEW_LOGIC_REL)))
    for name in ("actionTitle",):
        srcs = import_sources(ol, name)
        if srcs and not any("components" in s for s in srcs):
            problems.append(f"overview-logic 的 {name} 若引入应来自 components，实际 {srcs}")
    fail_if(problems, "总览渲染接线（D03）")


def test_d04_readonly2_render_wiring():
    """D04：历史表从 components 引入 ActorTag，并对 at 格改用 RelativeTime（渲染 <time dateTime=原文>）；
    HistoryDrawer 从 components 引入 formatLocalUtc；PluginDrawer 从 components 引入 copyText 与 COPY_RESULT_TEXT。"""
    problems = []
    hv = strip_ts_comments(_read(need_file(HISTORY_VIEW_REL)))
    at = import_sources(hv, "ActorTag")
    if not any("components" in s for s in at):
        problems.append(f"history-HistoryView 应从 components 引入 ActorTag，实际来自 {at}")
    rt = import_sources(hv, "RelativeTime")
    if not any("components" in s for s in rt):
        problems.append(f"history-HistoryView 应从 components 引入 RelativeTime，实际来自 {rt}")
    if "<RelativeTime" not in hv:
        problems.append("history-HistoryView 的 at 格应改用 <RelativeTime>（渲染带 dateTime 的 time）")
    hd = strip_ts_comments(_read(need_file(HISTORY_DRAWER_REL)))
    fl = import_sources(hd, "formatLocalUtc")
    if not any("components" in s for s in fl):
        problems.append(f"history-HistoryDrawer 应从 components 引入 formatLocalUtc，实际来自 {fl}")
    pd = strip_ts_comments(_read(need_file(PLUGIN_DRAWER_REL)))
    for name in ("copyText", "COPY_RESULT_TEXT"):
        srcs = import_sources(pd, name)
        if not any("components" in s for s in srcs):
            problems.append(f"plugins-PluginDrawer 应从 components 引入 {name}，实际来自 {srcs}")
    hl = strip_ts_comments(_read(need_file(HISTORY_LOGIC_REL)))
    for name in ("actionTitle", "actorTone"):
        srcs = import_sources(hl, name)
        if srcs and not any("components" in s for s in srcs):
            problems.append(f"history-logic 的 {name} 若引入应来自 components，实际 {srcs}")
    fail_if(problems, "readonly2 渲染接线（D04）")


# ---------------------------------------------------------------------------
# 静态断言：D05 指标卡
# ---------------------------------------------------------------------------

def _ov_metric_sel(selector):
    return bool(re.search(r"\.ov-metric(?![\w-])", selector))


def metric_icon_problems(css):
    """四张卡的图标颜色规则各自只引用本卡色调令牌（用 [data-metric=<分组>] 作作用域，看 color 规则）。"""
    problems = []
    rules = parse_rules(css)
    for metric, token in METRIC_ICON_TOKENS.items():
        others = [t for m, t in METRIC_ICON_TOKENS.items() if m != metric]
        want = f"var(--tt-{token})"
        ok = False
        for selector, decls in rules:
            sel = selector.replace('"', '').replace("'", '')
            if f"[data-metric={metric}]" not in sel:
                continue
            colors = [cv(v) for n, v in decls if n in ("color", "fill", "stroke")]
            if want not in colors:
                continue
            all_vals = " ".join(cv(v) for _n, v in decls)
            if any(f"var(--tt-{t})" in all_vals for t in others):
                continue
            ok = True
            break
        if not ok:
            problems.append(f"指标卡 {metric}：没有 [data-metric={metric}] 规则把图标颜色（color/fill/stroke）设成 {want}（且不引用别的卡的令牌）")
    return problems


def _tag_text(code, start):
    """从 code[start]（'<'）起按花括号配平取到标签结束的 '>'，返回整段标签文本。"""
    depth, i, n = 0, start, len(code)
    while i < n:
        ch = code[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif ch == ">" and depth == 0:
            return code[start:i + 1]
        i += 1
    return code[start:]


def _anchor_block(code):
    m = re.search(r"<a\b", code)
    if not m:
        return None
    end = code.find("</a>", m.start())
    if end < 0:
        return None
    return code[m.start():end + len("</a>")]


def _element_span(code, marker):
    """含 marker 的那个 JSX 元素的 (起点, 结束之后)；找不到返回 None。"""
    i = code.find(marker)
    if i < 0:
        return None
    start = code.rfind("<", 0, i)
    if start < 0:
        return None
    tag = _tag_text(code, start)
    close = code.find("</", start + len(tag))
    if close < 0:
        return (start, start + len(tag))
    gt = code.find(">", close)
    return (start, gt + 1)


def _icon_uses(code, block):
    """块里的图标用法：[(组件名, 标签文本, 位置)]。名字以 Icon 结尾，或是裸 svg。"""
    out = []
    for m in re.finditer(r"<([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)", block):
        name = m.group(1)
        if not (name.endswith("Icon") or name == "svg"):
            continue
        out.append((name, _tag_text(block, m.start()), m.start()))
    return out


def test_d05_metric_card_css_rules():
    """D05（CSS）：卡片规则有 position relative、display flex、flex-direction column、gap --tt-space-0_5；
    色调条规则有 position absolute，left/top/bottom 为 0，width 3px；四张卡图标颜色规则各自只引用本卡色调令牌。"""
    css = _read(need_file(OVERVIEW_CSS_REL))
    specs = [
        ("指标卡：position relative、display flex、flex-direction column、gap --tt-space-0_5", _ov_metric_sel,
         [C("position", eq="relative"), C("display", eq="flex"), C("flex-direction", eq="column"),
          HasAll(("gap", "row-gap"), tok("space-0_5"))]),
        ("色调条：position absolute，left/top/bottom 0，width 3px", lambda s: ".ov-metric__bar" in s,
         [C("position", eq="absolute"), C("left", zero=True), C("top", zero=True), C("bottom", zero=True), C("width", eq="3px")]),
    ]
    problems = group_problems(css, "overview-styles.css", specs) + metric_icon_problems(css)
    fail_if(problems, "指标卡 CSS（D05）")


def test_d05_metric_card_dom_structure():
    """D05（DOM，读源码）：每张卡的 a 里依次是色调条（aria-hidden）、标签行（16px 图标 aria-hidden + 标签文字）、数字（tt-num）；
    卡上只有计数这一个 tt-num；没有内联 style。"""
    code = strip_ts_comments(_read(need_file(METRIC_CARD_REL)))
    block = _anchor_block(code)
    assert block, "overview-MetricCard.tsx 里找不到 <a>…</a>（整张卡应是一个 a 链接）"
    problems = []
    bar = re.search(r"ov-metric__bar", block)
    if not bar:
        problems.append("指标卡里没有色调条 ov-metric__bar")
    elif not re.search(r"ov-metric__bar[^/>]*aria-hidden", block):
        problems.append("色调条应带 aria-hidden")
    icon = None
    icons = _icon_uses(code, block)
    label = _element_span(block, "ov-metric__label")
    inside = [it for it in icons if label is None or label[0] <= it[2] < label[1]]
    if not inside:
        where = "（在 ov-metric__label 里）" if label is not None else ""
        problems.append(f"标签行里应有一个 16px 的图标{where}")
    else:
        for name, props, _pos in inside:
            if not (re.search(r"\bwidth\s*=\s*\{?\s*16\s*\}?", props) and re.search(r"\bheight\s*=\s*\{?\s*16\s*\}?", props)):
                problems.append(f"标签行里的图标 {name} 应是 16px（width、height 都是 16）")
            if "aria-hidden" not in props and not any("icons" in s for s in import_sources(code, name)):
                problems.append(f"标签行里的图标 {name} 应 aria-hidden（本仓库的图标组件自带，或在标签上显式写）")
        icon = inside[0]
    num = re.search(r"ov-metric__num", block)
    if not num:
        problems.append("指标卡里没有数字 ov-metric__num")
    elif not re.search(r"ov-metric__num[^/>]*tt-num|tt-num[^/>]*ov-metric__num", block):
        problems.append("数字应带 tt-num")
    if bar and icon and num and not (bar.start() < icon[2] < num.start()):
        problems.append("a 里顺序应是 色调条 → 标签行(含图标) → 数字")
    if code.count("tt-num") != 1:
        problems.append(f"卡上应只有计数一个 tt-num，实际 {code.count('tt-num')} 处")
    if re.search(r"\bstyle\s*=", code):
        problems.append("指标卡不写内联 style")
    fail_if(problems, "指标卡 DOM 结构（D05，读源码）")


# ---------------------------------------------------------------------------
# 静态断言：D06 / D08 CSS
# ---------------------------------------------------------------------------

def test_d06_rt_cmd_display_block():
    """D06：.rt-cmd 同一条规则有 display block、max-width 280px、overflow hidden、white-space nowrap、--tt-mono-sm。"""
    css = _read(need_file(RUNTIMES_CSS_REL))
    specs = [(".rt-cmd：display block、max-width 280px、overflow hidden、white-space nowrap、--tt-mono-sm",
              lambda s: ".rt-cmd" in s,
              [C("display", eq="block"), C("max-width", eq="280px"), C("overflow", eq="hidden"),
               C("white-space", eq="nowrap"), C("font", eq=tok("mono-sm"))])]
    fail_if(group_problems(css, "runtimes-styles.css", specs), ".rt-cmd（D06）")


def test_d08_ov_row_name_mono():
    """D08：.ov-row__name 规则有 font var(--tt-mono-md)，仍单行省略（overflow hidden、white-space nowrap、text-overflow ellipsis）。"""
    css = _read(need_file(OVERVIEW_CSS_REL))
    specs = [(".ov-row__name：font var(--tt-mono-md)，仍单行省略", lambda s: ".ov-row__name" in s,
              [C("font", eq=tok("mono-md")), C("overflow", eq="hidden"), C("white-space", eq="nowrap"),
               C("text-overflow", eq="ellipsis")])]
    fail_if(group_problems(css, "overview-styles.css", specs), ".ov-row__name（D08）")


# ---------------------------------------------------------------------------
# 静态断言：D07 方案表 aria-controls
# ---------------------------------------------------------------------------

def _panel_id_problems(code, uid_name):
    """面板 id：用 useId 的结果加行序号拼（各行 id 才互不相同），不用方案名拼。"""
    templates = [t for t in re.findall(r"`[^`]*`", code) if "${" + uid_name + "}" in t.replace(" ", "")]
    if not templates:
        if re.search(rf"\b{re.escape(uid_name)}\s*\+|\+\s*{re.escape(uid_name)}\b", code):
            return []  # 字符串拼接式（uid + '-' + 行序号）
        return [f"找不到用 useId 结果 {uid_name} 拼面板 id 的写法"]
    problems = []
    for body in templates:
        parts = re.findall(r"\$\{([^{}]*)\}", body)
        others = [p.strip() for p in parts if p.strip() != uid_name]
        if not others:
            problems.append(f"面板 id 只用了 useId 的结果，没加行序号（各行 id 会相同）：{body}")
            continue
        for other in others:
            if re.search(r"\bname\b", other, re.I) and not re.search(r"findIndex|indexOf", other):
                problems.append(f"面板 id 不该用方案名拼（应加行序号）：{body}")
            elif not (re.fullmatch(r"[A-Za-z_$][\w$]*", other) and (re.search(r"index|idx", other, re.I) or len(other) <= 2)
                      or re.search(r"findIndex|indexOf", other)):
                problems.append(f"面板 id 的另一个取值应是行序号：{body}")
    return problems


def _uid_template(expr, uid_name):
    """表达式里含 ${{uid}} 的模板字面量；没有返回 None。"""
    for t in re.findall(r"`[^`]*`", expr or ""):
        if "${" + uid_name + "}" in t.replace(" ", ""):
            return t
    return None


def test_d07_presets_table_aria_controls():
    """D07（源码）：roles-PresetsTable.tsx 用 useId 加行序号生成面板 id（没有用方案名拼 id 的写法）；
    展开的 [查看差异] 才给 aria-controls（取值含 undefined，收起即省略），且指向同一个面板 id。"""
    code = strip_ts_comments(_read(need_file(PRESETS_TABLE_REL)))
    problems = []
    if not re.search(r"import\s+\{[^}]*\buseId\b[^}]*\}\s+from\s+['\"]react['\"]", code):
        problems.append("roles-PresetsTable 应从 react 引入 useId")
    uid = re.search(r"\b(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*useId\s*\(", code)
    if not uid:
        problems.append("roles-PresetsTable 应调用 useId() 并把结果存进变量（面板 id 用它生成）")
        fail_if(problems, "方案表 aria-controls（D07）")
        return
    uid_name = uid.group(1)
    problems.extend(_panel_id_problems(code, uid_name))
    m = re.search(r"<PresetDiff\b", code)
    panel_id = _jsx_expr(code[m.start():], "id") if m else None
    if panel_id is None:
        problems.append("差异面板的 id 应是动态表达式（useId 加行序号），不是写死的字符串")
    elif re.fullmatch(r"['\"][^'\"]*['\"]", panel_id.strip()):
        problems.append(f"差异面板的 id 不该是写死的字符串：{panel_id.strip()}")
    ac = _jsx_expr(code, "aria-controls")
    if ac is None:
        problems.append("[查看差异] 应有 aria-controls={…}（动态取值，展开时才给）")
    else:
        if "undefined" not in ac:
            problems.append(f"aria-controls 的取值应含 undefined（收起即省略），实际 {ac.strip()!r}")
        pid_t, ac_t = _uid_template(panel_id, uid_name), _uid_template(ac, uid_name)
        if pid_t and ac_t:
            if re.sub(r"\$\{[^{}]*\}", "#", pid_t) != re.sub(r"\$\{[^{}]*\}", "#", ac_t):
                problems.append(f"aria-controls 与面板 id 不是同一个 id：aria-controls={ac_t}，id={pid_t}")
        elif not (uid_name in ac or re.search(rf"\b{re.escape((panel_id or '').strip())}\b", ac)):
            problems.append(f"aria-controls 应指向面板 id（用 {uid_name} 拼出来的那个）：aria-controls={ac.strip()!r}")
    fail_if(problems, "方案表 aria-controls（D07）")


# ---------------------------------------------------------------------------
# 静态断言：D09 样式表接线（import 图）
# ---------------------------------------------------------------------------

def test_d09_css_reachable_from_main():
    """D09：readonly1、readonly2 下每份 CSS 都能从 src/main.tsx 顺 import 到达（光写 CSS 没人 import，页面不套用它）。"""
    fail_if(css_wiring_problems(src_files_by_rel(), list(ALL_CSS_RELS)), "样式表接线（D09）")


# ---------------------------------------------------------------------------
# 静态断言：D10 执行端新测试在位且干净
# ---------------------------------------------------------------------------

def test_d10_executor_tests_present_and_clean():
    """D10：执行端五份 cleanup1-* 新测试都在（shared、merge、visual、css、static），各至少一条用例，
    不出现 skip、only、todo、fails。"""
    problems = []
    folder = WEB / "tests"
    for name in NEW_TEST_FILES:
        path = folder / name
        if not path.is_file():
            problems.append(f"{TESTS_REL}/{name} 不存在（执行端要写的测试）")
            continue
        text = _read(path)
        if not re.search(r"^\s*(?:it|test|describe)(?:\.each\([^)]*\))?\(", text, re.M):
            problems.append(f"{name} 里没有用例")
        for bad in (r"\.skip\b", r"\.only\b", r"\.todo\b", r"\bxit\(", r"\bxtest\(", r"\bxdescribe\(", r"\.fails\b", r"\bit\.skipIf\b"):
            if re.search(bad, text):
                problems.append(f"{name} 里出现 {bad}（不许 skip、only、todo）")
    fail_if(problems, "执行端的新测试（D10）")


# ---------------------------------------------------------------------------
# 流水线：V01/V02/V03 + 构建产物里的样式表（D09 构建层、D10）
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
    started = (REPO_ROOT / COPY_TEXT_REL).is_file() or (REPO_ROOT / ACTION_TITLE_REL).is_file()
    if not started:
        pipe.reason = ("候选里还没有 src/components/copyText.ts 或 actionTitle.ts（基线），没有东西可测，未调用 npm；"
                       "执行端写出共用件后，流水线才会运行 npm ci、构建、Vitest 与合同检查")
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


def css_classes(css):
    out = set()
    for selector, _decls in parse_rules(css):
        out |= set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", re.sub(r"\"[^\"]*\"|'[^']*'", "", selector)))
    return out


def built_css_problems(built, texts):
    """每份源 CSS 至少一个独有的类选择器要出现在构建产物里（从文件里解析，不写死）。
    没有独有类可核对时（类都被别的 CSS 用了），退一步看它自己的类有没有进产物。"""
    problems = []
    classes = {rel: css_classes(text) for rel, text in texts.items()}
    for rel, own in classes.items():
        others = set().union(*(c for r, c in classes.items() if r != rel))
        pool = sorted(own - others)
        if not pool:
            if own and not any(re.search(rf"\.{re.escape(name)}(?![\w-])", built) for name in sorted(own)):
                problems.append(f"{rel}：构建产物 dist/assets/*.css 里找不到它的任何一个类，样式表没被打进构建")
            continue
        if not any(re.search(rf"\.{re.escape(name)}(?![\w-])", built) for name in pool):
            problems.append(f"{rel}：构建产物 dist/assets/*.css 里找不到它独有的类（如 .{pool[0]}），样式表没被打进构建")
    return problems


def test_d09_build_bundles_all_css(pipeline):
    """D09（构建层）：npm run build 成功后，readonly1、readonly2 每份 CSS 独有的类都出现在 dist/assets/*.css 里。"""
    assert pipeline.ran, pipeline.reason
    build = assert_step_ok(pipeline, "npm run build")
    assert pipeline.built_css, f"构建产物里没有 CSS（dist/assets/*.css）：\n{build.tail}"
    texts = {rel: _read(REPO_ROOT / rel) for rel in ALL_CSS_RELS}
    fail_if(built_css_problems(pipeline.built_css, texts), "构建产物里的样式表（D09）")


def test_d10_npm_build_test_contract_pass(pipeline):
    """D10：V01 构建、V02 全量测试、V03 合同检查都通过；流水线没有动 package.json、package-lock.json。"""
    assert pipeline.ran, pipeline.reason
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    changed = [n for n in WATCHED if pipeline.digests_before.get(n) != pipeline.digests_after.get(n)]
    fail_if([f"流水线改了本片不许动的文件：{n}" for n in changed], "流水线副作用的看护文件")
