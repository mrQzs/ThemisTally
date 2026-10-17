"""scripts/kit_logs.py 的执行端自测：只补 oracle 没有覆盖的细节（kit-logs v1）。

覆盖：时间解析（Z、+08:00、小数位）、--max/--state 的参数错误、--since 晚于 --until、
requested_model 不是对象时的分组、state.json 的异常取值。夹具都在 pytest 的 tmp_path 里现场生成，
不读取任何真实的会话记录或用户目录；不用 tempfile 自建目录。
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import kit_logs  # noqa: E402
import pi_dispatch as pd  # noqa: E402

IN_WINDOW = "2026-10-17T10:15:00Z"
SINCE = "2026-10-17T10:00:00Z"
UNTIL = "2026-10-17T10:30:00Z"
MODEL_OBJ = {"provider": "bb", "model": "step-5-preview", "thinking": "high"}


# ---------------------------------------------------------------------------
# 夹具
# ---------------------------------------------------------------------------

def make_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".agent" / "runs").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(repo), check=True)
    return repo


def put(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def attempt(repo, task, number, *, state="PASS", state_at="2026-10-17T10:00:00Z", events=None):
    directory = repo / ".agent" / "runs" / task / ("attempt-%03d" % number)
    directory.mkdir(parents=True, exist_ok=True)
    if state is not None:
        put(directory / "state.json", json.dumps({"state": state, "at": state_at}) + "\n")
    if events is not None:
        put(directory / "events-summary.json", events if isinstance(events, str) else json.dumps(events) + "\n")
    return directory


def rec(rid, *, ts=IN_WINDOW, model="model-a", sidechain=False, use=None, stop="end_turn"):
    row = {"timestamp": ts,
           "message": {"id": rid, "model": model, "stop_reason": stop,
                       "usage": use if use is not None else {"input_tokens": 10, "cache_creation_input_tokens": 2,
                                                             "cache_read_input_tokens": 3, "output_tokens": 4}}}
    if sidechain:
        row["isSidechain"] = True
    return row


def transcript(path, rows):
    put(path, "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n")


def run_logs(argv, repo):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = kit_logs.main([str(item) for item in argv], repo=str(repo))
        except SystemExit as exc:  # argparse
            code = exc.code if isinstance(exc.code, int) else 1
    return code, out.getvalue(), err.getvalue()


def jrun(argv, repo):
    code, out, err = run_logs(list(argv) + ["--json"], repo)
    return code, (json.loads(out) if code == 0 else None), err


def planner(tmp_path, repo, rows, *extra):
    path = tmp_path / "planner.jsonl"
    transcript(path, rows)
    argv = ["usage", "--transcript", str(path)] + list(extra)
    code, obj, err = jrun(argv, repo)
    assert code == 0, err
    return obj["planner"]


# ---------------------------------------------------------------------------
# 时间解析：Z、+08:00 与小数位（B7.1、B7.2）
# ---------------------------------------------------------------------------

def test_cli_times_accept_offsets_and_fractional_seconds(tmp_path):
    repo = make_repo(tmp_path)
    # 18:00+08:00 就是 10:00Z；小数秒 3 位与 6 位都能解析
    p = planner(tmp_path, repo, [rec("m1")],
                "--since", "2026-10-17T18:00:00+08:00", "--until", "2026-10-17T18:30:00+08:00")
    assert (p["included_messages"], p["outside_window_ids"]) == (1, 0)
    p = planner(tmp_path, repo, [rec("m1", ts="2026-10-17T10:15:00.123Z")],
                "--since", "2026-10-17T10:15:00.123+00:00", "--until", "2026-10-17T10:15:00.124+00:00")
    assert (p["included_messages"], p["outside_window_ids"]) == (1, 0)
    p = planner(tmp_path, repo, [rec("m1", ts="2026-10-17T10:15:00.123456Z")],
                "--since", "2026-10-17T10:15:00.123456+00:00", "--until", "2026-10-17T10:15:00.123500+00:00")
    assert (p["included_messages"], p["outside_window_ids"]) == (1, 0)


def test_record_timestamp_forms_decide_usability(tmp_path):
    repo = make_repo(tmp_path)
    rows = [
        rec("a1", ts="2026-10-17T18:15:00+08:00"),   # 10:15Z：可用
        rec("a2", ts="2026-10-17T10:15:00.5Z"),      # 一位小数秒：3.10 的 fromisoformat 不接受
        rec("a3", ts="2026-10-17T10:15:00.500Z"),    # 三位小数秒：可用
        rec("a4", ts="2026-10-17T10:15:00"),         # 不带时区：不可用
        rec("a5", ts=1792321700),                    # 不是字符串：不可用
    ]
    p = planner(tmp_path, repo, rows, "--since", SINCE, "--until", UNTIL)
    assert (p["included_messages"], p["ids_without_time"], p["unusable_timestamps"]) == (2, 3, 3)


def test_since_after_until_is_a_usage_error(tmp_path):
    repo = make_repo(tmp_path)
    path = tmp_path / "t.jsonl"
    transcript(path, [rec("m1")])
    code, out, err = run_logs(["usage", "--transcript", str(path), "--since", UNTIL, "--until", SINCE], repo)
    assert code == 2
    assert "ERROR:" in err
    assert "Traceback" not in err
    # 相等不是错误：窗口为空，全部落在窗外而不是用法错误
    code, obj, err = jrun(["usage", "--transcript", str(path), "--since", SINCE, "--until", SINCE], repo)
    assert code == 0, err
    assert obj["planner"]["outside_window_ids"] == 1


# ---------------------------------------------------------------------------
# 参数错误：--max、--state（B3、B6、B9）
# ---------------------------------------------------------------------------

def test_max_must_be_a_positive_integer(tmp_path):
    repo = make_repo(tmp_path)
    attempt(repo, "task-a", 1)
    for value in ("0", "-3", "abc", "1.5"):
        code, out, err = run_logs(["search", "x", "--max", value], repo)
        assert code == 2, (value, out, err)
        assert "Traceback" not in err, value


def test_state_filter_is_an_exact_string_match(tmp_path):
    repo = make_repo(tmp_path)
    attempt(repo, "task-a", 1, state="PASS")
    attempt(repo, "task-a", 2, state="pass")
    attempt(repo, "task-a", 3, state="RUNNING")
    code, obj, err = jrun(["list", "--state", "PASS"], repo)
    assert code == 0, err
    assert [row["attempt"] for row in obj["attempts"]] == ["attempt-001"]
    code, obj, err = jrun(["list", "--state", "pass"], repo)
    assert [row["attempt"] for row in obj["attempts"]] == ["attempt-002"]
    code, obj, err = jrun(["list", "--state", "PASSING"], repo)
    assert (code, obj["attempts"]) == (0, [])
    code, out, err = run_logs(["list", "--state", "NOPE"], repo)
    assert code == 0
    assert "没有 attempt" in out


def test_bad_task_id_is_a_usage_error_for_every_subcommand(tmp_path):
    repo = make_repo(tmp_path)
    attempt(repo, "task-a", 1)
    for argv in (["list", "--task", "Task-A"], ["search", "x", "--task", "../x"], ["usage", "--task", ""]):
        code, out, err = run_logs(argv, repo)
        assert code == 2, (argv, out, err)
        assert "Traceback" not in err, argv


# ---------------------------------------------------------------------------
# requested_model 的分组（B7.1）
# ---------------------------------------------------------------------------

def test_requested_model_that_is_not_an_object_groups_as_null(tmp_path):
    repo = make_repo(tmp_path)
    good = {"provider": "bb", "model": "step-5-preview"}
    usage = {"input": 1, "output": 2, "cacheRead": 3, "cacheWrite": 4, "totalTokens": 10}
    complete = {"complete": True, "truncated": False, "parse_error_lines": []}
    attempt(repo, "task-a", 1, events=dict(requested_model=good, usage=usage, **complete))
    attempt(repo, "task-a", 2, events=dict(requested_model="bb/step-5-preview", usage=usage, **complete))
    attempt(repo, "task-a", 3, events=dict(usage=usage, **complete))
    attempt(repo, "task-a", 4, events=dict(requested_model=["bb", "step-5-preview"], usage=usage, **complete))
    attempt(repo, "task-a", 5, events=dict(requested_model={"provider": "bb"}, usage=usage, **complete))
    attempt(repo, "task-a", 6, events=dict(requested_model={"provider": 1, "model": "m"}, usage=usage, **complete))
    code, obj, err = jrun(["usage"], repo)
    assert code == 0, err
    groups = obj["executor"]["by_model"]
    assert [group["requested_model"] for group in groups] == [None, "bb/step-5-preview"]
    assert (groups[0]["known"], groups[0]["partial"], groups[0]["unknown"]) == (5, 0, 0)
    assert (groups[1]["known"], groups[1]["partial"], groups[1]["unknown"]) == (1, 0, 0)
    rows = {(row["task"], row["attempt"]): row for row in obj["executor"]["attempts"]}
    assert rows[("task-a", "attempt-001")]["requested_model"] == "bb/step-5-preview"
    for number in (2, 3, 4, 5, 6):
        assert rows[("task-a", "attempt-%03d" % number)]["requested_model"] is None, number
    # null 组排在前面，但它的用量仍然计入合计（unknown 不计、known/partial 计）
    assert obj["executor"]["totals"]["input"] == 6


def test_usage_task_filter_with_an_unknown_task_is_empty_not_an_error(tmp_path):
    repo = make_repo(tmp_path)
    attempt(repo, "task-a", 1, events={"usage": {"input": 1, "output": 2, "cacheRead": 3, "cacheWrite": 4,
                                                 "totalTokens": 10}, "complete": True})
    code, obj, err = jrun(["usage", "--task", "task-zzz"], repo)
    assert code == 0, err
    assert obj["executor"]["attempts"] == []
    assert obj["executor"]["totals"] == {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0,
                                         "totalTokens": 0}
    assert obj["executor"]["counts"] == {"known": 0, "partial": 0, "unknown": 0}


# ---------------------------------------------------------------------------
# state.json 的异常取值（B2）
# ---------------------------------------------------------------------------

def test_state_json_with_odd_values_falls_back_to_unknown(tmp_path):
    repo = make_repo(tmp_path)
    runs = repo / ".agent" / "runs"
    put(runs / "task-a" / "attempt-001" / "state.json", "[1, 2]\n")
    put(runs / "task-a" / "attempt-002" / "state.json", json.dumps({"state": 5, "at": "T"}) + "\n")
    put(runs / "task-a" / "attempt-003" / "state.json", json.dumps({"state": "PASS", "at": 7}) + "\n")
    put(runs / "task-a" / "attempt-004" / "state.json", json.dumps({"at": "T4"}) + "\n")
    put(runs / "task-a" / "attempt-005" / "state.json", "{not json")
    code, obj, err = jrun(["list"], repo)
    assert code == 0, err
    rows = {row["attempt"]: row for row in obj["attempts"]}
    assert (rows["attempt-001"]["state"], rows["attempt-001"]["state_at"]) == ("UNKNOWN", None)
    assert (rows["attempt-002"]["state"], rows["attempt-002"]["state_at"]) == ("UNKNOWN", "T")
    assert (rows["attempt-003"]["state"], rows["attempt-003"]["state_at"]) == ("PASS", None)
    assert (rows["attempt-004"]["state"], rows["attempt-004"]["state_at"]) == ("UNKNOWN", "T4")
    assert (rows["attempt-005"]["state"], rows["attempt-005"]["state_at"]) == ("UNKNOWN", None)


# ---------------------------------------------------------------------------
# 文本输出里的注明（B3、B6）
# ---------------------------------------------------------------------------

def test_text_output_notes_skipped_links(tmp_path):
    repo = make_repo(tmp_path)
    runs = repo / ".agent" / "runs"
    attempt(repo, "task-a", 1)
    outside = tmp_path / "outside"
    (outside / "task-l" / "attempt-001").mkdir(parents=True)
    link = runs / "task-l"
    if os.name == "nt":
        proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside / "task-l")],
                              capture_output=True)
        if proc.returncode != 0:
            pytest.skip("mklink /J 不可用")
    else:
        try:
            os.symlink(str(outside / "task-l"), str(link), target_is_directory=True)
        except OSError:
            pytest.skip("符号链接不可用")
    assert pd.is_link_or_junction(link)
    code, out, err = run_logs(["list"], repo)
    assert code == 0, err
    assert "跳过的链接：1" in out
    code, out, err = run_logs(["search", "x"], repo)
    assert code == 0, err
    assert "跳过的链接：1" in out


def test_show_text_output_notes_truncation_with_total_bytes(tmp_path):
    repo = make_repo(tmp_path)
    put(repo / ".agent" / "runs" / "task-a" / "attempt-001" / "summary.md", "z" * 70000)
    code, out, err = run_logs(["show", "task-a/attempt-001"], repo)
    assert code == 0, err
    assert "已截断" in out
    assert "70000" in out
    assert len(out) < 70000


def test_search_decodes_invalid_utf8_with_replacement(tmp_path):
    repo = make_repo(tmp_path)
    path = repo / ".agent" / "runs" / "task-a" / "attempt-001" / "notes.txt"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"caf\xe9 NEEDLE\nsecond line\n")
    code, out, err = run_logs(["search", "NEEDLE"], repo)
    assert code == 0, err
    assert "task-a/attempt-001/notes.txt:1: caf" in out
    assert "NEEDLE" in out


def test_search_line_numbers_count_every_line(tmp_path):
    repo = make_repo(tmp_path)
    path = repo / ".agent" / "runs" / "task-a" / "attempt-001" / "summary.md"
    path.parent.mkdir(parents=True)
    path.write_text("no hit\nno hit\nneedle here\n", encoding="utf-8")
    code, out, err = run_logs(["search", "needle"], repo)
    assert code == 0, err
    assert out.startswith("task-a/attempt-001/summary.md:3: needle here")


def test_transcript_given_twice_counts_the_records_twice(tmp_path):
    repo = make_repo(tmp_path)
    path = tmp_path / "t.jsonl"
    transcript(path, [rec("m1")])
    code, obj, err = jrun(["usage", "--transcript", str(path), "--transcript", str(path),
                           "--since", SINCE, "--until", UNTIL], repo)
    assert code == 0, err
    # 同一个 id 的两条最终记录计数相同：不算冲突，只算一条消息加一条重复记录
    planner = obj["planner"]
    assert (planner["included_messages"], planner["duplicate_records"], planner["conflict_ids"]) == (1, 1, 0)
