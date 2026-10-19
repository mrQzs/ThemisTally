"""调度器导出的 attempt 状态全集（T002 的站主 Q3）：桌面端的状态标签与状态表按这张表画。"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pi_dispatch as pd  # noqa: E402

SOURCE = (Path(__file__).resolve().parents[1] / "scripts" / "pi_dispatch.py").read_text(encoding="utf-8")


def test_attempt_states_are_the_seventeen_of_the_ui_document():
    # 顺序同 UI 文档 §3.4 的状态表
    assert pd.ATTEMPT_STATES == (
        "PREPARING", "PREPARED", "PREPARE_FAILED", "RUNNING", "COLLECTING", "NEEDS_REVIEW",
        "PASS", "ACCEPTED_WITH_EXCEPTION", "REVISE", "BLOCKED", "ESCALATE",
        "INFRA_FAILURE", "TIMEOUT", "CANCELLED", "INTEGRATED", "ABANDONED", "SUPERSEDED")


def test_every_state_the_dispatcher_writes_is_listed():
    written = set(re.findall(r'set_state\([^,]+, "([A-Z_]+)"', SOURCE))
    written |= set(re.findall(r'^\s+state = "([A-Z_]+)"', SOURCE, re.M))  # finish_run 算出的状态
    mark = re.search(r'p\.add_argument\("state", choices=\(([^)]*)\)\)', SOURCE)
    written |= set(re.findall(r'"([A-Z_]+)"', mark.group(1)))
    assert {"PREPARING", "RUNNING", "TIMEOUT", "CANCELLED", "NEEDS_REVIEW", "SUPERSEDED"} <= written
    assert written | set(pd.VERDICTS) == set(pd.ATTEMPT_STATES)  # verdict 写的状态就是结论本身


def test_state_groups_stay_inside_the_full_set():
    for group in (pd.VERDICTS, pd.REVIEWABLE_STATES, pd.TERMINAL_STATES, pd.PENDING_INTEGRATION_STATES):
        assert set(group) <= set(pd.ATTEMPT_STATES), group
