"""DoD 行里“证据”的解析（第 80 轮）。

T016 的合同 D07 写着“…照样遮掉；证据不登记任何白名单；用例：redaction.test.ts 的 U22…；证据：V02”。解析器把第一个
“；证据”当作分隔，U22 成了证据，validate 报“不是已定义的检查 id”；合同端交了四次都卡在这里，协调人还以为它在
重发旧文本。现在有带冒号的“；证据：”时取最后一个；没有时照旧（2.5.0 的第一个“；证据”，更老的第一个“证据”）。
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "scripts"))
sys.path.insert(0, str(TESTS))

import pi_dispatch as pd  # noqa: E402
import test_dispatch as td  # noqa: E402  合同的样板与 Markdown 生成在端到端测试里

TEMPLATE = "- D01: 行为正确；证据：V01。"


def dod(line: str) -> dict:
    md = td.build_md(td.contract("0" * 40, 1))
    assert TEMPLATE in md
    derived, problems = pd.derive_contract_json(md.replace(TEMPLATE, line), "dod")
    return derived["definition_of_done"][0]


def test_a_clause_that_starts_with_evidence_before_the_labelled_one_stays_in_the_text():
    item = dod("- D01: 照样遮掉；证据不登记任何白名单；用例：redaction.test.ts 的 U22；证据：V01；目的：白名单只放名字")
    assert item["evidence"] == ["V01"]
    assert item["text"] == "照样遮掉；证据不登记任何白名单；用例：redaction.test.ts 的 U22"
    assert item["intent"] == "白名单只放名字"


def test_with_several_labelled_clauses_the_last_one_is_the_evidence():
    # 正文里引用了“；证据：”这种写法本身：证据是最后那一处，前面的留在正文里
    item = dod("- D01: 报告写成“问题；证据：日志第 3 行”的格式；证据：V01、scope")
    assert item["text"] == "报告写成“问题；证据：日志第 3 行”的格式"
    assert item["evidence"] == ["V01", "scope"]


def test_the_older_forms_still_parse_the_same():
    assert dod("- D01: 行为正确；证据 V01。") == {"id": "D01", "text": "行为正确", "evidence": ["V01"]}
    assert dod("- D01: 行为正确，证据 V01。") == {"id": "D01", "text": "行为正确", "evidence": ["V01"]}
    item = dod("- D01: 证据一半来自规划端的 oracle，另一半来自执行器；证据：V01、scope。")
    assert item["text"] == "证据一半来自规划端的 oracle，另一半来自执行器" and item["evidence"] == ["V01", "scope"]
