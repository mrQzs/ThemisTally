"""T001 战前门禁：桌面端两份设计文档的黑盒基准测试（合同 t001-desktop-doc，plan_version 1）。

被测对象是两份纯 Markdown 文档，没有代码：

- 架构文档 ``docs/themis-tally-3.0-桌面端.md``（下称“架构”）；
- UI 文档 ``docs/themis-tally-3.0-桌面端-UI设计.md``（下称“UI”）。

基线是提交 ``13e3d58``（合同的 base_sha）。未动的段落一律用 ``git show <基线>:<路径>`` 读出来逐字比对，
不用 HEAD（内核会把本文件做成基线提交，HEAD 会变）。定位节用标题的编号（例如 ``D7``、``10.1``、``7.24``），
不用行号；改动处按合同 DoD 点名的原句与关键词断言，不要求整段草稿逐字相同。

每条测试对应的 DoD 项写在测试名前缀里（``test_d02_…`` 对应 D02）。D01（范围）由内核的范围检查证明，
D11（行号可核）与 D12（文风）是人工审阅，都不写进本基准。

站主已按推荐确认 Q1–Q4 与 §0 的四行（2026-10-19）。本基准只断言 DoD 点名的内容，不断言“待站主确认”
这个标注在或不在，也不断言 Q1（§8.1 的 PD 行）、Q3（UI 的“下一步”提示）的取舍：
``UNCHANGED_EXEMPT`` 里的几节因此不参加“未动的节逐字不变”的比对。

拿不准的断言（理由都写在各测试的 docstring 里，并已列入“需协调人决定”）：

- 未动的节逐字不变（``test_unchanged_sections_*``）：合同只点名要求 §0.1–§0.6 与 §11 逐字不动，
  其余是依据合同“所有改动落点”清单推出来的；
- ``test_d05_u14e_…`` 要求同时写出 ``truncated`` 的 true 与 false；
- ``test_d06_…`` 要求四个新行按 D1A-2-S1、D1A-2-S2、七端-1、七端-2 的顺序接在原有七行之后。

候选文档一律从仓库根读取，基线一律从 Git 读取。

基线上本文件应当失败，原因是文档缺少要求的内容；不是导入、路径或语法错误。
"""

import functools
import json
import re
import subprocess
from pathlib import Path

import pytest

BASE_SHA = "13e3d580f2893136f9b03f1e126d68b38bd139f6"
REPO_ROOT = Path(__file__).resolve().parents[1]
CAND_ROOT = REPO_ROOT

ARCH_REL = "docs/themis-tally-3.0-桌面端.md"
UI_REL = "docs/themis-tally-3.0-桌面端-UI设计.md"

# B1 收窄后的原句（合同 D03），逐字。
B1_SENTENCE = "除文件大小、合法性和超长行保护这些显式元数据门槛外，匹配和摘录只依赖脱敏结果"
B1_OLD_SENTENCE = "返回与否只取决于脱敏之后的文本"

# 与 Q1、Q3 的取舍相关，本基准不替站主断言它们在或不在（见模块 docstring）。
UNCHANGED_EXEMPT = {
    ARCH_REL: {"8.1"},
    UI_REL: {"6.2", "7.21", "10.3"},
}

# 合同“所有改动落点”清单里的节（按节号），其余节必须与基线逐字相同。
# 注意：键是标题里的第一个词；H1 是文首（标题与状态行、上位设计、缩写）。
ARCH_CHANGED = {"H1", "0.0", "1.3", "2.9", "D1", "D2", "D3", "D6", "D7", "D11", "D12", "D13",
                "6.", "9.", "10.1", "10.2"}
UI_CHANGED = {"H1", "0.2", "1.", "6.3", "6.4", "6.7", "6.11", "7.22", "7.24", "9.2", "9.5",
              "10.1", "12."}


# ---------------------------------------------------------------------------
# 读文档
# ---------------------------------------------------------------------------

def _norm(text):
    return text.replace("\r\n", "\n")


@functools.lru_cache(maxsize=None)
def base_text(rel):
    """基线（13e3d58）上的文档原文，经 git show 读取。"""
    proc = subprocess.run(["git", "show", f"{BASE_SHA}:{rel}"], cwd=REPO_ROOT,
                          capture_output=True)
    if proc.returncode != 0:
        pytest.fail(f"读不到基线 {BASE_SHA[:7]}:{rel}：{proc.stderr.decode('utf-8', 'replace')}")
    return _norm(proc.stdout.decode("utf-8"))


@functools.lru_cache(maxsize=None)
def new_text(rel):
    """工作目录里的文档原文（候选）。"""
    path = CAND_ROOT / rel
    if not path.is_file():
        pytest.fail(f"工作目录里没有 {rel}")
    return _norm(path.read_bytes().decode("utf-8"))


# ---------------------------------------------------------------------------
# Markdown 切分（认围栏，围栏里的 # 不算标题）
# ---------------------------------------------------------------------------

_FENCE_LINE = re.compile(r"^\s*```")
_HEADING = re.compile(r"^(#{1,6}) (.+?)\s*$")


@functools.lru_cache(maxsize=None)
def leaves(text):
    """按标题切成叶子节：{键: 含标题行的正文}，保持出现顺序。

    键是标题的第一个词（``### D7 实时…`` 的 ``D7``，``### 10.1 本机服务…`` 的 ``10.1``，
    ``## 12. 验收清单`` 的 ``12.``）；H1 的键是 ``H1``。同名键加 ``#2`` 区分。
    """
    out = {}
    key = "PRE"
    buf = []
    in_fence = False

    def flush():
        if buf or key != "PRE":
            k = key
            n = 2
            while k in out:
                k = f"{key}#{n}"
                n += 1
            out[k] = "\n".join(buf)

    for line in text.split("\n"):
        if _FENCE_LINE.match(line):
            in_fence = not in_fence
            buf.append(line)
            continue
        m = None if in_fence else _HEADING.match(line)
        if m:
            flush()
            buf = [line]
            key = "H1" if len(m.group(1)) == 1 else m.group(2).split()[0]
        else:
            buf.append(line)
    flush()
    return out


def sec(rel, key, which="new"):
    text = new_text(rel) if which == "new" else base_text(rel)
    lv = leaves(text)
    if key not in lv:
        pytest.fail(f"{rel} 里找不到节 {key}（{which}）")
    return lv[key]


def fenced_blocks(text):
    """[(语言, 内容)]；开围栏可缩进，关围栏是单独一行 ```。"""
    blocks = []
    lang = None
    buf = []
    for line in text.split("\n"):
        if lang is None:
            m = re.match(r"^\s*```(\S*)\s*$", line)
            if m:
                lang = m.group(1)
                buf = []
        elif line.strip() == "```":
            blocks.append((lang, "\n".join(buf)))
            lang = None
        else:
            buf.append(line)
    return blocks


def outside_fences(text):
    lines = []
    in_fence = False
    for line in text.split("\n"):
        if _FENCE_LINE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence:
            lines.append(line)
    return "\n".join(lines)


def table_rows(text):
    """[(单元格列表, 原行)]，只收以 | 开头并结尾的行；转义的 \\| 不分列。"""
    rows = []
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("|") and s.endswith("|") and len(s) > 1:
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", s)[1:-1]]
            rows.append((cells, line))
    return rows


def data_rows(text):
    """表格的数据行（去掉表头与分隔线）。表头的第一格是“编号”“页面”“档”“阶段”。"""
    out = []
    for cells, line in table_rows(text):
        first = cells[0]
        if re.fullmatch(r":?-+:?", first):
            continue
        out.append((cells, line))
    return out


def row_by_first(text, first):
    for cells, line in table_rows(text):
        if cells[0] == first:
            return cells
    return None


def must_row(text, first, ncells):
    cells = row_by_first(text, first)
    assert cells is not None, f"表里找不到第一格是 {first!r} 的行"
    assert len(cells) == ncells, f"{first!r} 行的列数应为 {ncells}，实际 {len(cells)}：表格被破坏"
    return cells


def appended_part(base_cell, new_cell, what):
    """基线单元格原文必须仍是新单元格的子串（只追加）；返回追加的部分。"""
    assert base_cell in new_cell, f"{what}：基线原文不再是新内容的子串（原文被改动或删除）"
    return new_cell.replace(base_cell, "", 1)


def span(text, start_prefix, end_prefix=None):
    """从第一条以 start_prefix 开头的行，到第一条以 end_prefix 开头的行之前（含头，不含尾）。"""
    lines = text.split("\n")
    i = next((n for n, l in enumerate(lines) if l.startswith(start_prefix)), None)
    assert i is not None, f"找不到以 {start_prefix!r} 开头的行"
    j = len(lines)
    if end_prefix is not None:
        j = next((n for n in range(i + 1, len(lines)) if lines[n].startswith(end_prefix)), None)
        assert j is not None, f"找不到以 {end_prefix!r} 开头的行"
    return "\n".join(lines[i:j]).rstrip()


def has_all(text, needles):
    return [n for n in needles if n not in text]


def assert_has(text, needles, where):
    missing = has_all(text, needles)
    assert not missing, f"{where} 缺少：{missing}"


# ---------------------------------------------------------------------------
# D02：闸一记录逐字不动
# ---------------------------------------------------------------------------

def test_d02_arch_sections_0_1_to_0_6_verbatim():
    """架构 §0.1–§0.6（基线 L35–115，从“### 0.1”到“## 1. 范围”之前）与基线逐字相同。"""
    base = span(base_text(ARCH_REL), "### 0.1 ", "## 1. ")
    assert base.count("\n") > 60, "基线上 §0.1–§0.6 的切分不对"
    new = span(new_text(ARCH_REL), "### 0.1 ", "## 1. ")
    assert new == base, "架构 §0.1–§0.6 与基线不同"


def test_d02_arch_section_11_verbatim():
    """架构 §11（基线 L862–884，从“## 11.”到文件末尾）与基线逐字相同。"""
    base = span(base_text(ARCH_REL), "## 11. ")
    assert base.count("\n") > 10, "基线上 §11 的切分不对"
    new = span(new_text(ARCH_REL), "## 11. ")
    assert new == base, "架构 §11 与基线不同"


# ---------------------------------------------------------------------------
# D03 / D04：B1 的措辞与元数据门槛
# ---------------------------------------------------------------------------

def _search_region(which="new"):
    """D7 里“搜索”那一条（含它的子要点与新增的“元数据门槛”），到“脱敏的耗时”之前。"""
    d7 = sec(ARCH_REL, "D7", which)
    lines = d7.split("\n")
    i = next((n for n, l in enumerate(lines) if re.match(r"^\s*- \*\*搜索\*\*", l)), None)
    assert i is not None, "D7 里找不到“搜索”这一条"
    j = next((n for n in range(i + 1, len(lines)) if re.match(r"^\s*- \*\*脱敏的耗时\*\*", lines[n])), None)
    assert j is not None, "D7 里找不到“脱敏的耗时”这一条"
    return "\n".join(lines[i:j])


def test_d03_b1_sentence_in_d7_search():
    """D7“搜索”含收窄后的原句。"""
    assert B1_SENTENCE in _search_region(), "D7“搜索”缺少收窄后的原句"


def test_d03_b1_sentence_in_section_0_0():
    """§0.0 也含这句原句（B1 行的“处置”追加与 D1A-2-S1 行都可以）。"""
    assert B1_SENTENCE in sec(ARCH_REL, "0.0"), "§0.0 缺少收窄后的原句"


def test_d03_b1_sentence_at_least_twice():
    assert new_text(ARCH_REL).count(B1_SENTENCE) >= 2, "架构文档里这句原句不足两处"


def test_d03_d7_drops_old_claim():
    """D7 不再含“返回与否只取决于脱敏之后的文本”（基线上有）。"""
    assert B1_OLD_SENTENCE in sec(ARCH_REL, "D7", "base"), "基线上本来应有旧论证（基线核对）"
    assert B1_OLD_SENTENCE not in sec(ARCH_REL, "D7"), "D7 仍含过宽的旧论证"


def _line_with(region, *needles):
    for line in region.split("\n"):
        if all(n in line for n in needles):
            return line
    return None


def test_d04_overlong_and_unparsable_jsonl_lines_not_searched_not_counted():
    """超过 4 MiB 的 JSONL 行与解析不了的行不参加搜索、不计数，并带 KL: 行号。

    “同一条里写全”依据合同草稿 7.1（每件事一条要点、各带 KL:）。
    """
    line = _line_with(_search_region(), "4 MiB", "JSONL", "解析不了", "不参加搜索", "不计数")
    assert line is not None, "D7“搜索”里没有一条写明：超过 4 MiB 的 JSONL 行与解析不了的行不参加搜索、不计数"
    assert re.search(r"KL:\d+", line), "这一条没有带 KL: 行号"


def test_d04_skipped_large_counts_text_over_64mib_or_unreadable_not_jsonl():
    """超过 64 MiB 或读不出来的文本（含 .json）计入 skipped_large；JSONL 没有整份上限、不计入；带 KL: 行号。"""
    line = _line_with(_search_region(), "64 MiB", "skipped_large", ".json", "读不出来")
    assert line is not None, "D7“搜索”里没有一条写明：超过 64 MiB 或读不出来的文本（含 .json）计入 skipped_large"
    assert_has(line, ["JSONL", "没有整份", "不计入"], "这一条（JSONL 没有整份上限、不计入）")
    assert re.search(r"KL:\d+", line), "这一条没有带 KL: 行号"


def test_d04_truncated_only_means_over_max():
    """truncated 只表示匹配超过了 --max；带 KL: 行号。"""
    line = _line_with(_search_region(), "truncated", "--max", "只表示")
    assert line is not None, "D7“搜索”里没有一条写明：truncated 只表示匹配超过 --max"
    assert re.search(r"KL:\d+", line), "这一条没有带 KL: 行号"


# ---------------------------------------------------------------------------
# D05：§10.1 的 U10、U14d、U14e（只追加，不新增编号）
# ---------------------------------------------------------------------------

def _u_rows(which):
    text = sec(ARCH_REL, "10.1", which)
    return {cells[0]: cells for cells, _ in data_rows(text) if re.fullmatch(r"U\d+\w*", cells[0])}


def _added(uid):
    """新行相对基线行追加的文字（场景与断言两格合起来）。同时核对“基线原文仍是新行的子串”。"""
    base = _u_rows("base")[uid]
    assert len(base) == 3, f"基线 {uid} 行应有 3 列"
    new_rows = _u_rows("new")
    assert uid in new_rows, f"§10.1 里找不到 {uid}"
    new = new_rows[uid]
    assert len(new) == 3, f"{uid} 行的列数应为 3，实际 {len(new)}：表格被破坏"
    return (appended_part(base[1], new[1], f"{uid} 的失败场景")
            + "\n" + appended_part(base[2], new[2], f"{uid} 的断言"))


def test_d05_no_new_numbers_and_originals_kept():
    """§10.1 没有新增（或删除、改名）编号；三行以外的 U 行与基线逐字相同。"""
    base_rows = _u_rows("base")
    new_rows = _u_rows("new")
    assert list(new_rows) == list(base_rows), "§10.1 的编号集合或顺序与基线不同（不许新增编号）"
    for uid, cells in base_rows.items():
        if uid in ("U10", "U14d", "U14e"):
            continue
        assert new_rows[uid] == cells, f"{uid} 行被改动"


def test_d05_u10_search_job_quadratic_redaction_timeout():
    """U10 追加：search 作业、平方级脱敏、超时。"""
    added = _added("U10")
    assert_has(added, ["search", "平方级", "超时"], "U10 追加的内容")
    assert "脱敏" in added, "U10 追加的内容没有提到脱敏"


def test_d05_u14d_plain_text_truncation_mtime_409():
    """U14d 追加：普通文本、截短、修改时间，以及“文件已变化”或 409。"""
    added = _added("U14d")
    assert_has(added, ["普通文本", "截短", "修改时间"], "U14d 追加的内容")
    assert ("文件已变化" in added) or ("409" in added), "U14d 追加的内容既没有“文件已变化”也没有 409"


def test_d05_u14e_concrete_skipped_large_and_truncated_values():
    """U14e 追加：写出 skipped_large 与 truncated 的具体值。

    取值依据合同草稿 7.5：skipped_large 为 1；truncated 在 --max 不小于可见匹配数时为 false、
    少 1 时为 true。DoD 只说“具体值”，这里要求 true 与 false 都写出来（拿不准，已列入需协调人决定）。
    """
    added = _added("U14e")
    assert "skipped_large" in added and "truncated" in added, "U14e 追加的内容没有同时提到 skipped_large 与 truncated"
    sep = r"[`\s]*(?:为|=|是|等于|:|：)[`\s]*"
    assert re.search(r"skipped_large" + sep + r"1(?!\d)", added), "U14e 追加的内容没有写出 skipped_large 的具体值 1"
    assert re.search(r"truncated" + sep + r"(?:false|假)", added), "U14e 追加的内容没有写出 truncated 为 false"
    assert re.search(r"truncated" + sep + r"(?:true|真)", added), "U14e 追加的内容没有写出 truncated 为 true"


# ---------------------------------------------------------------------------
# D06：§0.0 的四个新行；原有七行逐字不变（B1 行只在“处置”列追加）
# ---------------------------------------------------------------------------

NEW_0_0_IDS = ["D1A-2-S1", "D1A-2-S2", "七端-1", "七端-2"]


def _0_0_rows(which):
    return [cells for cells, _ in data_rows(sec(ARCH_REL, "0.0", which)) if cells[0] != "编号"]


def test_d06_four_new_rows_after_the_seven_original():
    """§0.0 共 11 个数据行：基线的 7 行在前，接着是四个新行（顺序依合同草稿 8.2）。"""
    base_ids = [c[0] for c in _0_0_rows("base")]
    assert len(base_ids) == 7, "基线 §0.0 应有 7 个数据行（基线核对）"
    new_rows = _0_0_rows("new")
    assert [c[0] for c in new_rows] == base_ids + NEW_0_0_IDS, "§0.0 的编号列不是“原有七行 + 四个新行”"
    for cells in new_rows[7:]:
        assert len(cells) == 3 and all(cells), f"{cells[0]} 行应有 3 个非空列"


def test_d06_original_rows_verbatim_except_b1_handling_append():
    """原有七行除 D1A-1-B1 的“处置”列追加外逐字不变；B1 行的“处置”以基线原文开头。"""
    base_rows = _0_0_rows("base")
    new_rows = {c[0]: c for c in _0_0_rows("new")}
    for b in base_rows:
        assert b[0] in new_rows, f"§0.0 缺少原有的 {b[0]} 行"
        n = new_rows[b[0]]
        if b[0] != "D1A-1-B1":
            assert n == b, f"§0.0 的 {b[0]} 行被改动"
            continue
        assert n[:2] == b[:2], "D1A-1-B1 行的“编号”或“结论”被改动"
        assert n[2].startswith(b[2]) and len(n[2]) > len(b[2]), "D1A-1-B1 行的“处置”不是“基线原文 + 追加”"
        assert B1_SENTENCE in n[2][len(b[2]):], "D1A-1-B1 行的“处置”追加里没有收窄后的原句"


# ---------------------------------------------------------------------------
# D07：§2.9
# ---------------------------------------------------------------------------

WORKER_NAMES = ["womovie-c8", "planner-opus", "contract-glm", "gate-sonnet", "audit-sonnet",
                "exec-step", "jev-judge"]


def test_d07_section_2_9_exists_between_2_8_and_3():
    keys = list(leaves(new_text(ARCH_REL)))
    assert "2.9" in keys, "架构文档没有 §2.9"
    assert keys.index("2.8") < keys.index("2.9") < keys.index("3."), "§2.9 不在 §2.8 与第 3 节之间"
    assert "七端" in sec(ARCH_REL, "2.9").split("\n")[0], "§2.9 的标题没有“七端”"


def test_d07_section_2_9_cites_r3_with_line_numbers():
    s = sec(ARCH_REL, "2.9")
    assert "r3" in s, "§2.9 没有引用 r3"
    refs = re.findall(r"第 \d+(?:[–-]\d+)?(?:、\d+(?:[–-]\d+)?)* 行", s)
    assert len(refs) >= 3, f"§2.9 引用 r3 的行号不足 3 处（找到 {len(refs)} 处）"
    assert re.search(r"KH:\d+", s), "§2.9 没有 KH: 行号"


def test_d07_section_2_9_does_not_recopy_r3_tables():
    """不出现 r3 §5 的前置条件表、§3.2 的信件格式、§2 的名册表。

    判据取自 r3 原文的特征词：前置条件表（“前置条件”“协调人发的信”、阶段任务目录名）、
    信件格式（msg-id、in-reply-to、“需协调人决定”）、名册表（表头“载体”；表格行里出现工人名字）。
    """
    s = sec(ARCH_REL, "2.9")
    for n in ["前置条件", "协调人发的信", "-3-gate-pre", "-5-exec", "msg-id", "in-reply-to",
              "需协调人决定", "载体"]:
        assert n not in s, f"§2.9 重抄了 r3 的内容：{n}"
    for cells, line in table_rows(s):
        assert not any(w in line for w in WORKER_NAMES), "§2.9 的表格里出现了 r3 名册的工人名字"


# ---------------------------------------------------------------------------
# D08：要点二——桌面端不启动、不唤醒、不停止角色进程
# ---------------------------------------------------------------------------

def test_d08_d1_not_a_fifth_role_and_not_launching_roles():
    d1 = sec(ARCH_REL, "D1")
    assert "第五个角色" in sec(ARCH_REL, "D1", "base"), "基线 D1 本来应有“第五个角色”（基线核对）"
    assert "第五个角色" not in d1, "D1 仍含“第五个角色”"
    assert "不是七端（§2.9）里的任何一端" in d1, "D1 没有改成“不是七端（§2.9）里的任何一端”"
    assert_has(d1, ["不启动", "不唤醒", "不停止", "只读", "状态与记录"], "D1")
    assert "后台进程" in d1 and "§2.9" in d1, "D1 没有写明角色由内核以后台进程按信唤醒（§2.9）"


def test_d08_d2_roles_woken_by_kernel_mailbox_process():
    """A11：D2 写明角色回合由内核的信箱进程（kit_hub.py）以后台进程唤醒；服务的子进程不含角色回合。"""
    assert_has(sec(ARCH_REL, "D2"), ["kit_hub.py", "后台进程", "角色回合", "§2.9"], "D2")


def test_d08_d3_subprocesses_are_not_role_turns_and_probes_are_readonly():
    """A12：D3 写明子进程不是角色回合，只读探测不调用模型。"""
    assert_has(sec(ARCH_REL, "D3"),
               ["角色回合", "--list-models", "auth check --no-refresh", "不调用模型", "AGENTS.md:62"], "D3")


def test_d08_d6_future_opening_does_not_launch_models_directly():
    """A13：D6“花钱或集成”一档的规则列追加“将来开放时同样不由桌面端直接启动模型”。"""
    d6 = sec(ARCH_REL, "D6")
    base_row = must_row(sec(ARCH_REL, "D6", "base"), "花钱或集成", 4)
    new_row = must_row(d6, "花钱或集成", 4)
    added = appended_part(base_row[3], new_row[3], "D6“花钱或集成”的规则列")
    assert_has(added, ["不由桌面端直接启动模型", "D1", "§2.9"], "D6“花钱或集成”规则列的追加")


def test_d08_d11_role_and_model_row_names_the_seven_end_roster_elsewhere():
    """A16：D11“角色与模型”追加：四个角色在配置中心，七端名册在 hub 自己的配置里，不在这一页。"""
    base = must_row(sec(ARCH_REL, "D11", "base"), "角色与模型", 4)
    new = must_row(sec(ARCH_REL, "D11"), "角色与模型", 4)
    added = appended_part(base[1], new[1], "D11“角色与模型”的内容列")
    assert_has(added, ["思考档位", "配置中心的四个角色", "七端的名册", "hub 自己的配置", "不在这一页"],
               "D11“角色与模型”内容列的追加")


def test_d08_d11_logs_and_usage_row_seven_end_sessions_not_mixed():
    """A18：D11“日志与用量”追加：七端工人的会话不混进规划端的用量，用量记在回合记录里。"""
    base = must_row(sec(ARCH_REL, "D11", "base"), "日志与用量", 4)
    new = must_row(sec(ARCH_REL, "D11"), "日志与用量", 4)
    added = appended_part(base[1], new[1], "D11“日志与用量”的内容列")
    assert_has(added, ["七端工人的会话", "不混进规划端的用量", "回合记录"], "D11“日志与用量”内容列的追加")


def test_d08_d11_seven_ends_and_mailbox_row_replaces_four_ends_topology():
    """A19：“四端拓扑”改为“七端与信箱”：只读，命令是 kit_hub.py status --json，现在可做为“否”。"""
    d11 = sec(ARCH_REL, "D11")
    assert row_by_first(d11, "四端拓扑") is None, "D11 仍有“四端拓扑”一行"
    row = must_row(d11, "七端与信箱", 4)
    assert_has(row[1], ["未读的信", "思考档位", "只读"], "D11“七端与信箱”的内容列")
    assert "kit_hub.py status --json" in row[2], "D11“七端与信箱”的命令列没有 kit_hub.py status --json"
    assert row[3].startswith("否"), "D11“七端与信箱”的“现在可做”不是“否”"


def test_d08_d11_advance_row_wakes_models_so_not_started_by_desktop():
    """A20：D11“推进”追加：会唤醒模型，属于 D6“花钱或集成”一档，也不由桌面端直接启动（D1）。"""
    base = must_row(sec(ARCH_REL, "D11", "base"), "推进", 4)
    new = must_row(sec(ARCH_REL, "D11"), "推进", 4)
    added = appended_part(base[1], new[1], "D11“推进”的内容列")
    assert_has(added, ["唤醒模型", "花钱或集成", "不由桌面端直接启动"], "D11“推进”内容列的追加")


def test_d08_d12_seven_end_workers_do_not_drive_the_console():
    """A22：D12 追加：七端的工人同样不启动、不驱动管理台；门禁端 Bash 只放行 python -m pytest（r3 §2、§6.3）。"""
    assert_has(sec(ARCH_REL, "D12"), ["七端的工人", "python -m pytest", "r3 §2", "r3 §6.3"], "D12")


def test_d08_section_6_notes_seven_end_flow_decision():
    """A24：§6 末尾加一句现状：用户 2026-10-19 提出改用七端流程（§2.9），D1-B 起怎样执行另定。"""
    s = sec(ARCH_REL, "6.")
    base = sec(ARCH_REL, "6.", "base")
    assert base.rstrip() in s or all(l in s for l in base.split("\n") if l.strip()), "§6 的原文被改动或删除"
    assert_has(s, ["2026-10-19", "七端流程", "§2.9", "D1-B", "另定"], "§6")


def _9_rows(which):
    return {cells[0]: cells for cells, _ in data_rows(sec(ARCH_REL, "9.", which))}


def test_d08_section_9_d4_row_does_not_launch_models_directly():
    """A25：§9 D4 行的完成标准追加“不由桌面端直接启动模型（D1）”。"""
    base = _9_rows("base")["D4"]
    new = _9_rows("new")["D4"]
    assert len(new) == len(base) == 4
    added = appended_part(base[3], new[3], "§9 D4 行的完成标准")
    assert_has(added, ["不由桌面端直接启动模型", "D1"], "§9 D4 行完成标准的追加")


def test_d08_section_9_d5_row_seven_ends_and_mailbox():
    """A26：§9 D5 行：“四端拓扑”改“七端与信箱”；依赖加“r3 的只读记录（§2.9）”。"""
    new = _9_rows("new")["D5"]
    assert len(new) == 4
    assert "四端拓扑" not in new[1], "§9 D5 行仍有“四端拓扑”"
    assert "七端与信箱" in new[1], "§9 D5 行没有“七端与信箱”"
    assert_has(new[2], ["r3", "只读记录", "§2.9"], "§9 D5 行的依赖列")


def test_d08_section_9_other_rows_unchanged():
    base = _9_rows("base")
    new = _9_rows("new")
    assert list(new) == list(base), "§9 的阶段行集合或顺序与基线不同"
    for k in ("D0", "D2", "D3"):
        assert new[k] == base[k], f"§9 的 {k} 行被改动"


def test_d08_ui_0_2_item_7_roles_only_woken_by_kernel():
    """B2：UI 0.2 第 7 条句末追加：不放启动、唤醒、停止 claude、pi 角色进程或给工人发信的按钮，只由内核做。"""
    s = sec(UI_REL, "0.2")
    lines = s.split("\n")
    i = next((n for n, l in enumerate(lines) if l.startswith("7. ")), None)
    assert i is not None, "UI 0.2 里找不到第 7 条"
    j = next((n for n in range(i + 1, len(lines)) if re.match(r"^\d+\. ", lines[n])), len(lines))
    item = "\n".join(lines[i:j])
    base_lines = sec(UI_REL, "0.2", "base").split("\n")
    bi = next(n for n, l in enumerate(base_lines) if l.startswith("7. "))
    assert base_lines[bi].rstrip("。 ") in item, "UI 0.2 第 7 条的原文被改动"
    assert_has(item, ["启动", "唤醒", "停止", "角色进程", "只由内核"], "UI 0.2 第 7 条")
    assert "§2.9" in item, "UI 0.2 第 7 条没有指向架构文档 §2.9"


def test_d08_ui_section_1_workers_woken_by_kernel():
    """B3：UI 第 1 节“用户”追加：七端的工人由内核以后台进程按信唤醒，同样不用这个界面。"""
    assert_has(sec(UI_REL, "1."), ["七端的工人", "后台进程", "§2.9"], "UI 第 1 节")


def test_d08_ui_6_4_page_head_names_four_roles_not_the_seven_end_roster():
    """B6：UI 6.4 页首：这一页显示配置中心的四个角色绑定；七端的工人名册不在这一页（架构文档 D11）。"""
    assert_has(sec(UI_REL, "6.4"), ["四个角色绑定", "hub 自己的配置", "不在这一页"], "UI 6.4")


def test_d08_ui_6_7_usage_does_not_count_seven_end_workers():
    """B11：UI 6.7 用量的规划端追加：七端工人的用量记在回合记录里，不混进规划端的会话目录，这一页现在不统计。"""
    assert_has(sec(UI_REL, "6.7"), ["七端工人的用量", "回合记录", "不混进规划端的会话目录", "不统计"], "UI 6.7")


def test_d08_ui_6_11_seven_ends_and_mailbox_read_only():
    """B12：UI 6.11：“四端拓扑”改为“七端与信箱”，接入之后只读，不启动角色。"""
    s = sec(UI_REL, "6.11")
    assert "四端拓扑" not in s, "UI 6.11 仍有“四端拓扑”"
    assert_has(s, ["七端与信箱", "只读", "不启动角色"], "UI 6.11")


# ---------------------------------------------------------------------------
# D09：要点三（架构）——D11 的“思考档位”与 D13 的“另做”
# ---------------------------------------------------------------------------

def _effort_block():
    """D11 表下的“思考档位：要求与生效并列”要点（到 D11 结束）。"""
    d11 = sec(ARCH_REL, "D11")
    lines = d11.split("\n")
    i = next((n for n, l in enumerate(lines) if re.match(r"^\W*\*\*思考档位[:：]", l)), None)
    assert i is not None, "D11 里没有“**思考档位：…**”要点"
    return "\n".join(lines[i:])


def test_d09_d11_effort_block_rules():
    """并列、逐字比较、不一致标出、缺失为“未知”且不当作一致、没有要求档位为“—”。"""
    b = _effort_block()
    assert_has(b, ["并列", "逐字相同", "标出", "未知", "不当作一致", "没有要求档位"], "D11 的思考档位要点")
    assert "“—”" in b, "D11 的思考档位要点没有写明没有要求档位显示“—”"
    assert re.search(r"不是“未知”|与“未知”区分", b), "D11 的思考档位要点没有把“—”与“未知”区分开"
    assert_has(b, ["thinkingLevel", "effort"], "D11 的思考档位要点（生效档位的来源）")


def test_d09_d11_effort_block_cites_all_four_sources():
    """现状带 KH/KR/PD/KL 行号。"""
    b = _effort_block()
    for abbr in ("KH", "KR", "PD", "KL"):
        assert re.search(abbr + r":\d+", b), f"D11 的思考档位要点没有 {abbr}: 行号"


def test_d09_d11_other_rows_carry_effort_notes():
    """A15、A17：任务与 attempt 行、CLI 运行时行各追加一句，原文保留。"""
    base_d11 = sec(ARCH_REL, "D11", "base")
    new_d11 = sec(ARCH_REL, "D11")
    b = must_row(base_d11, "任务与 attempt", 4)
    n = must_row(new_d11, "任务与 attempt", 4)
    assert "思考档位" in appended_part(b[1], n[1], "D11“任务与 attempt”的内容列"), "D11“任务与 attempt”没有提到思考档位"
    b = must_row(base_d11, "CLI 运行时", 4)
    n = must_row(new_d11, "CLI 运行时", 4)
    added = appended_part(b[1], n[1], "D11“CLI 运行时”的内容列")
    assert_has(added, ["思考级别", "不是生效档位"], "D11“CLI 运行时”内容列的追加")


def test_d09_d11_rows_not_in_the_change_list_unchanged():
    base = {c[0]: l for c, l in data_rows(sec(ARCH_REL, "D11", "base"))}
    new_lines = {l for _, l in data_rows(sec(ARCH_REL, "D11"))}
    for k in ("总览", "凭据", "插件", "历史与审计", "需求与合同", "反馈流"):
        assert base[k] in new_lines, f"D11 的“{k}”行被改动"


def test_d09_d13_has_a_separate_work_item_for_effort():
    """A23：D13 的 PD 要点追加“另做”一条：补读 thinkingLevel，补上之前界面显示“未知”。"""
    assert "另做" not in sec(ARCH_REL, "D13", "base"), "基线 D13 本来不应有“另做”（基线核对）"
    assert_has(sec(ARCH_REL, "D13"), ["另做", "thinkingLevel", "未知"], "D13")


def test_d09_arch_header_defines_r3_and_kh():
    """A2、A4：文首给出 r3 的路径与缩写 KH（§2.9 与思考档位要点用到）。"""
    head = sec(ARCH_REL, "H1")
    assert "docs/themis-tally-3.0-r3-七端与信箱.md" in head, "文首没有给出 r3 文档的路径"
    assert re.search(r"KH\s*=\s*`scripts/kit_hub\.py`", head), "文首的缩写没有 KH = `scripts/kit_hub.py`"


# ---------------------------------------------------------------------------
# D10：要点三（UI）
# ---------------------------------------------------------------------------

def test_d10_ui_status_line_is_draft_7_pointing_to_arch_0_0():
    line = next((l for l in sec(UI_REL, "H1").split("\n") if l.startswith("状态：")), None)
    assert line is not None, "UI 文档没有“状态：”行"
    assert_has(line, ["第 7 稿", "§0.0", "架构文档"], "UI 状态行")


def test_d10_ui_section_7_24_exists_with_four_displays():
    keys = list(leaves(new_text(UI_REL)))
    assert "7.24" in keys, "UI 文档没有 7.24"
    assert keys.index("7.23") < keys.index("7.24") < keys.index("8."), "7.24 不在 7.23 与第 8 节之间"
    s = sec(UI_REL, "7.24")
    assert "思考档位" in s.split("\n")[0], "7.24 的标题没有“思考档位”"
    assert_has(s, ["要求", "生效", "与要求不同", "未知", "—", "D11"], "UI 7.24")
    # 四种情形：相同、不同、未知、没有要求档位——表里至少四个数据行
    assert len(data_rows(s)) >= 5, "7.24 的表没有四种情形（相同、不同、未知、没有要求档位）"


@pytest.mark.parametrize("key", ["6.3", "6.4", "7.22"])
def test_d10_ui_pages_reference_7_24(key):
    """6.3、6.4、7.22 引用 7.24。"""
    assert "7.24" in sec(UI_REL, key), f"UI {key} 没有引用 7.24"


def test_d10_ui_6_3_list_and_detail_show_effort():
    """B4、B5：6.3 列表页的列与详情页的数据来源提到思考档位。"""
    s = sec(UI_REL, "6.3")
    assert re.search(r"思考档位（要求 / 生效，7\.24）", s), "UI 6.3 列表页的列没有“思考档位（要求 / 生效，7.24）”"
    assert "与思考档位（7.24）" in s, "UI 6.3 详情页的数据来源没有“与思考档位（7.24）”"


def test_d10_ui_6_4_thinking_is_the_requested_level_and_silent_downgrade():
    """B7–B9：6.4 角色卡显示要求 / 生效；profile 的 thinking 是要求的档位，并提到静默降档。"""
    s = sec(UI_REL, "6.4")
    assert re.search(r"思考档位（要求 / 生效，7\.24）", s), "UI 6.4 角色卡没有“思考档位（要求 / 生效，7.24）”"
    assert "thinking（要求的档位）" in s, "UI 6.4 的 profile 表没有“thinking（要求的档位）”列"
    assert "静默降档" in s, "UI 6.4 的 thinking 说明没有提到静默降档"
    assert "要求的档位" in outside_fences(s).replace("thinking（要求的档位）", ""), \
        "UI 6.4 的 thinking 说明没有写明这是要求的档位"


def test_d10_ui_7_22_readiness_thinking_level_is_not_the_effective_level():
    """B13：7.22 就绪卡的“思考级别”注明本机 pi 接受这个档位，不是生效档位。"""
    assert_has(sec(UI_REL, "7.22"), ["本机 pi 接受这个档位", "不是生效档位"], "UI 7.22")


def test_d10_ui_6_7_search_result_notes():
    """B10：UI 6.7 检索加一条结果说明：truncated、skipped_large 与不参加搜索的 JSONL 行。"""
    s = sec(UI_REL, "6.7")
    assert_has(s, ["truncated", "skipped_large", "4 MiB", "元数据门槛"], "UI 6.7")


def _json_block(rel_key):
    blocks = [b for lang, b in fenced_blocks(sec(UI_REL, rel_key)) if lang == "json"]
    assert len(blocks) == 1, f"UI {rel_key} 应有且仅有 1 个 json 代码块"
    try:
        return json.loads(blocks[0])
    except ValueError as exc:
        pytest.fail(f"UI {rel_key} 的 json 代码块不是合法 JSON：{exc}")


def test_d10_ui_9_2_sample_rows_have_effort_fields_marked_illustrative():
    """B15：9.2 两行带 effort_requested / effort_effective：一行生效为 null，一行与要求不同；字段说明标“示意”。"""
    rows = [r for r in _json_block("9.2") if "effort_requested" in r or "effort_effective" in r]
    assert len(rows) >= 2, "UI 9.2 的示例里带思考档位字段的行不足两行"
    assert all("effort_requested" in r and "effort_effective" in r for r in rows), \
        "UI 9.2 的示例里 effort_requested 与 effort_effective 没有成对出现"
    assert any(r["effort_effective"] is None for r in rows), "UI 9.2 没有生效为 null 的行"
    assert any(r["effort_effective"] is not None and r["effort_effective"] != r["effort_requested"]
               for r in rows), "UI 9.2 没有生效与要求不同的行"
    notes = outside_fences(sec(UI_REL, "9.2"))
    assert_has(notes, ["示意", "D13", "未知", "7.24"], "UI 9.2 的字段说明")


def test_d10_ui_9_5_executor_row_has_null_effective_effort_marked_illustrative():
    """B16：9.5 执行端一行带示意字段 effort_effective（null）；代码块下注“示意，见 9.2”。"""
    roles = _json_block("9.5")["roles"]
    execution = next(r for r in roles if r["role"] == "execution")
    assert "effort_effective" in execution and execution["effort_effective"] is None, \
        "UI 9.5 的执行端一行没有 effort_effective: null"
    assert "示意，见 9.2" in outside_fences(sec(UI_REL, "9.5")), "UI 9.5 代码块下没有“示意，见 9.2”"


def _12_items(which):
    items = {}
    for line in sec(UI_REL, "12.", which).split("\n"):
        m = re.match(r"^(\d+)\. (.*)$", line)
        if m:
            items[int(m.group(1))] = m.group(2)
    return items


def test_d10_ui_section_12_adds_item_18_about_effort():
    """B17：第 12 节新增第 18 条：并列显示要求与生效；不同的标出；未知显示“未知”，不显示成一致。"""
    base = _12_items("base")
    new = _12_items("new")
    assert sorted(base) == list(range(1, 18)), "基线第 12 节应有 1–17 条（基线核对）"
    assert sorted(new) == list(range(1, 19)), "第 12 节不是 1–18 条"
    assert_has(new[18], ["思考档位", "要求", "生效", "标出", "未知", "7.24"], "第 12 节第 18 条")
    for i in range(1, 18):
        if i == 15:  # O3 可在句末追加
            assert new[15].startswith(base[15].rstrip("。")), "第 12 节第 15 条的原文被改动"
        else:
            assert new[i] == base[i], f"第 12 节第 {i} 条被改动"


def test_d10_ui_text_blocks_wireframes_verbatim():
    """UI 文档全部 text 代码块（线框）逐字不变，数量、顺序也不变。"""
    base = [b for lang, b in fenced_blocks(base_text(UI_REL)) if lang == "text"]
    new = [b for lang, b in fenced_blocks(new_text(UI_REL)) if lang == "text"]
    assert len(base) == 10, f"基线应有 10 个 text 代码块，实际 {len(base)}（基线核对）"
    assert new == base, "UI 文档的 text 代码块（线框）与基线不同"


def test_d10_arch_10_2_has_w7():
    """架构 §10.2 新增 W7（思考档位五种情形），W1–W6 原样。"""
    base = [(c[0], l) for c, l in data_rows(sec(ARCH_REL, "10.2", "base"))]
    new = data_rows(sec(ARCH_REL, "10.2"))
    assert [c[0] for c, _ in new] == [k for k, _ in base] + ["W7"], "§10.2 的编号不是 W1–W7"
    assert [l for _, l in new[:-1]] == [l for _, l in base], "§10.2 的 W1–W6 被改动"
    cells = new[-1][0]
    assert len(cells) == 3, "W7 行的列数应为 3"
    assert_has(" ".join(cells), ["思考档位", "与要求不同", "未知", "—"], "W7")


def test_d10_arch_section_9_d1_row_includes_w7():
    """A27：§9 D1 行的完成标准“W4–W6”改“W4–W7”。"""
    done = _9_rows("new")["D1"][3]
    assert "W4–W7" in done, "§9 D1 行的完成标准没有 W4–W7"
    assert "W4–W6" not in done, "§9 D1 行的完成标准仍是 W4–W6"


# ---------------------------------------------------------------------------
# 未动的节逐字不变（合同“所有改动落点”之外）
# ---------------------------------------------------------------------------

def _unchanged_check(rel, changed, new_keys):
    base = leaves(base_text(rel))
    new = leaves(new_text(rel))
    # 不删节、不改名节：基线的每个节号在新文档里按原顺序都在，只多出合同允许的新节
    assert [k for k in new if k in base] == list(base), f"{rel} 的节被删除、改名或换了顺序"
    assert [k for k in new if k not in base] == new_keys, f"{rel} 新增的节与合同不符（应只新增 {new_keys}）"
    exempt = UNCHANGED_EXEMPT.get(rel, set())
    for k, body in base.items():
        if k in changed or k in exempt:
            continue
        assert new[k].rstrip() == body.rstrip(), f"{rel} 的 {k} 节不在合同的改动清单里，却与基线不同"


def test_unchanged_sections_arch():
    """架构文档：合同清单之外的节与基线逐字相同（§8.1 的 PD 行取舍属 Q1，不参加比对）。

    清单：文首、§0.0、§1.3、D1、D2、D3、D6、D7、D11、D12、D13、§6、§9、§10.1、§10.2；新增 §2.9。
    拿不准的地方：合同只硬性要求 §0.1–§0.6 与 §11 逐字不动（D02），这里是依据“所有改动落点”推出的更宽比对。
    """
    _unchanged_check(ARCH_REL, ARCH_CHANGED, ["2.9"])


def test_unchanged_sections_ui():
    """UI 文档：合同清单之外的节与基线逐字相同（6.2、7.21、10.3 含 Q3 的“下一步”提示，不参加比对）。

    清单：状态行、0.2、第 1 节、6.3、6.4、6.7、6.11、7.22、9.2、9.5、10.1、第 12 节；新增 7.24。
    """
    _unchanged_check(UI_REL, UI_CHANGED, ["7.24"])
