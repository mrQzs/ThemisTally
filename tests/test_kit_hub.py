"""3.0 第三轮：七端信箱（docs/themis-tally-3.0-r3-七端与信箱.md）。

覆盖：
- 信件的格式与形状校验（§3.2）；投递永不覆盖、读信即移到 cur（§3.1）；
- 内核状态机（§5）：每一行前置条件各有拒收用例，满足时放行；上游重新交付使下游结论作废；
- 回合审计（§6.3）：白名单之外的 tool_use 与 server_tool_use（advisor）、init 的工具、MCP、自动记忆、模型；
- 调度循环（§3.3）：协调人的信经内核校验才投递，连续拒收转 blocked；工人回合审计不过时信不投递；
  “通过、等待、停止”不唤醒工人。

模型调用一律换成假的回合启动器；工作区换成 tmp_path 里的目录。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import kit_hub as kh  # noqa: E402

BASE = "a" * 40


def make_ts(jev: bool = True) -> dict:
    return kh.new_task_state("T001", "doc", "改桌面端文档", BASE, jev)


def meta(kind: str, to: str, task: str) -> dict:
    return {"type": kind, "to": to, "task-id": task, "from": kh.COORDINATOR, "in-reply-to": "none"}


def fields(**extra: str) -> dict:
    out = {key: "无" for key in kh.FIELDS}
    out["摘要"] = "做完了"
    out.update(extra)
    return out


def locked(ts: dict) -> dict:
    ts["contract"].update(validated=True, sha256="c1", key="t001-doc.v1", version=1)
    ts["oracle"].update(sha="o" * 40, locked=True)
    for suffix in ("1-plan", "2-contract", "3-gate-pre"):
        ts["stages"][suffix]["status"] = "delivered"
    return ts


# ---------------------------------------------------------------------------
# 信件
# ---------------------------------------------------------------------------

def test_letter_round_trip_keeps_multiline_fields():
    head = {"msg-id": "m1", "from": "planner-opus", "to": kh.COORDINATOR, "task-id": "T001-1-plan",
            "in-reply-to": "none", "type": "交付"}
    body = fields(偏离="第一行\n第二行：带冒号也算续行")
    parsed, parsed_fields, lines = kh.parse_letter(kh.render_letter(head, body))
    assert parsed == head
    assert parsed_fields["偏离"] == "第一行\n第二行：带冒号也算续行"
    assert lines == 7
    assert kh.letter_errors(parsed, parsed_fields, lines) == []


@pytest.mark.parametrize("change, expected", [
    (lambda h, f, n: f.pop("验证"), "正文缺“验证”"),
    (lambda h, f, n: h.update(type="开工"), "planner-opus 不能发 开工"),
    (lambda h, f, n: h.update(to="nobody"), "收信人 nobody 不在名册里"),
    (lambda h, f, n: h.update({"task-id": "X1"}), "不是主任务号"),
])
def test_letter_shape_errors(change, expected):
    head = {"from": "planner-opus", "to": kh.COORDINATOR, "task-id": "T001-1-plan", "in-reply-to": "none",
            "type": "交付"}
    body = fields()
    change(head, body, 0)
    assert any(expected in error for error in kh.letter_errors(head, body, 6))


def test_letter_body_limit_and_audit_verdict():
    head = {"from": "audit-sonnet", "to": kh.COORDINATOR, "task-id": "T001-4-audit-pre", "in-reply-to": "none",
            "type": "交付"}
    assert any("超过 40 行" in e for e in kh.letter_errors(head, fields(结论="通过"), 41))
    assert any("结论" in e for e in kh.letter_errors(head, fields(), 6))
    assert any("退回" in e for e in kh.letter_errors(head, fields(结论="返工"), 7))
    assert kh.letter_errors(head, fields(结论="返工", 退回="门禁端"), 8) == []


def test_delivery_never_overwrites_and_take_moves_to_cur(tmp_path):
    hub = kh.Hub(tmp_path)
    hub.ensure()
    head = {"msg-id": "20260101T000000000000Z-owner-aaaaaa", "from": kh.OWNER, "to": kh.COORDINATOR,
            "task-id": "T001", "in-reply-to": "none", "type": "任务"}
    hub.deliver(head, fields())
    with pytest.raises(kh.HubError):
        hub.deliver(head, fields(摘要="别的内容"))
    head2 = dict(head, **{"msg-id": "20250101T000000000000Z-owner-bbbbbb"})
    hub.deliver(head2, fields())
    unread = hub.unread(kh.COORDINATOR)
    assert [p.stem for p in unread] == [head2["msg-id"], head["msg-id"]]
    moved = hub.take(unread[0])
    assert moved.parent.name == "cur" and not unread[0].exists()
    assert "做完了" in moved.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 状态机（设计 §5）：每一行前置条件
# ---------------------------------------------------------------------------

def test_guard_owner_and_routing_rules():
    ts = make_ts()
    assert kh.guard(ts, meta("汇报", kh.OWNER, "T001")) is None
    assert "给站主只能发" in kh.guard(ts, meta("开工", kh.OWNER, "T001"))
    assert "只发给站主" in kh.guard(ts, meta("汇报", "planner-opus", "T001-1-plan"))
    assert "归 contract-glm" in kh.guard(ts, meta("开工", "gate-sonnet", "T001-2-contract"))
    assert "阶段任务" in kh.guard(ts, meta("开工", "planner-opus", "T001"))
    assert "没有登记主任务" in kh.guard(None, meta("开工", "planner-opus", "T001-1-plan"))
    ts["status"] = "stopped"
    assert "已停止" in kh.guard(ts, meta("开工", "planner-opus", "T001-1-plan"))


def test_guard_plan_contract_gate_and_jev_starts():
    ts = make_ts()
    assert kh.guard(ts, meta("开工", "planner-opus", "T001-1-plan")) is None
    ts["stages"]["1-plan"]["status"] = "assigned"
    assert "已经开工" in kh.guard(ts, meta("开工", "planner-opus", "T001-1-plan"))
    assert "规划端还没交付" in kh.guard(ts, meta("开工", "contract-glm", "T001-2-contract"))
    ts["stages"]["1-plan"]["status"] = "delivered"
    assert kh.guard(ts, meta("开工", "contract-glm", "T001-2-contract")) is None
    assert "validate" in kh.guard(ts, meta("开工", "gate-sonnet", "T001-3-gate-pre"))
    assert "合同端还没交付" in kh.guard(ts, meta("开工", "jev-judge", "T001-3j-jev"))
    ts["contract"]["validated"] = True
    ts["stages"]["2-contract"]["status"] = "delivered"
    assert kh.guard(ts, meta("开工", "gate-sonnet", "T001-3-gate-pre")) is None
    assert kh.guard(ts, meta("开工", "jev-judge", "T001-3j-jev")) is None


def test_guard_audit_pre_needs_locked_baseline_and_jev():
    ts = make_ts()
    ts["contract"]["validated"] = True
    assert "基准测试还没锁定" in kh.guard(ts, meta("开工", "audit-sonnet", "T001-4-audit-pre"))
    locked(ts)
    assert "3j-jev" in kh.guard(ts, meta("开工", "audit-sonnet", "T001-4-audit-pre"))
    ts["jev"]["3j-jev"] = {"status": "no_opinion"}
    assert kh.guard(ts, meta("开工", "audit-sonnet", "T001-4-audit-pre")) is None
    off = locked(make_ts(jev=False))
    assert kh.guard(off, meta("开工", "audit-sonnet", "T001-4-audit-pre")) is None


def test_guard_exec_needs_passing_first_review_on_the_same_bytes():
    ts = locked(make_ts())
    assert "一审还没有通过" in kh.guard(ts, meta("开工", "exec-step", "T001-5-exec"))
    ts["audit_pre"].update(verdict="返工", contract_sha256="c1", oracle_sha="o" * 40)
    assert "一审还没有通过" in kh.guard(ts, meta("开工", "exec-step", "T001-5-exec"))
    ts["audit_pre"]["verdict"] = "通过"
    assert kh.guard(ts, meta("开工", "exec-step", "T001-5-exec")) is None
    ts["contract"]["sha256"] = "c2"  # 一审之后合同变了
    assert "重新一审" in kh.guard(ts, meta("开工", "exec-step", "T001-5-exec"))
    ts["contract"]["sha256"] = "c1"
    ts["oracle"]["sha"] = "p" * 40  # 一审之后基线提交变了
    assert "重新一审" in kh.guard(ts, meta("开工", "exec-step", "T001-5-exec"))


def test_guard_short_circuit_after_execution():
    ts = locked(make_ts())
    ts["exec"].update(run_dir="r", check_ok=False)
    for task, worker in (("T001-6-gate-post", "gate-sonnet"), ("T001-6j-jev", "jev-judge"),
                         ("T001-7-audit-post", "audit-sonnet")):
        assert kh.guard(ts, meta("开工", worker, task)) is not None
    assert kh.guard(ts, meta("返工", "exec-step", "T001-5-exec")) is None  # 短路：只能返工给执行端
    ts["exec"]["check_ok"] = True
    assert kh.guard(ts, meta("开工", "gate-sonnet", "T001-6-gate-post")) is None
    assert "没有执行之后的失败记录" in kh.guard(ts, meta("返工", "exec-step", "T001-5-exec"))
    ts["gate_post"].update(ran=True, ok=False)
    assert "战后门禁" in kh.guard(ts, meta("开工", "jev-judge", "T001-6j-jev"))
    assert "战后门禁" in kh.guard(ts, meta("开工", "audit-sonnet", "T001-7-audit-post"))
    assert kh.guard(ts, meta("返工", "exec-step", "T001-5-exec")) is None
    ts["gate_post"]["ok"] = True
    assert kh.guard(ts, meta("开工", "jev-judge", "T001-6j-jev")) is None
    assert "6j-jev" in kh.guard(ts, meta("开工", "audit-sonnet", "T001-7-audit-post"))
    ts["jev"]["6j-jev"] = {"status": "answered"}
    assert kh.guard(ts, meta("开工", "audit-sonnet", "T001-7-audit-post")) is None


def test_guard_rework_targets():
    ts = locked(make_ts())
    assert "没有一审退回" in kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract"))
    assert "没有一审退回" in kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre"))
    ts["audit_pre"].update(verdict="返工", target="门禁端")
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre")) is None
    assert "没有一审退回" in kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract"))
    ts["stages"]["2-contract"]["status"] = "failed"  # 内核核验失败也允许返工
    assert kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract")) is None
    assert "不到 3 次" in kh.guard(ts, meta("返工", "planner-opus", "T001-1-plan"))
    ts["audit_pre"]["fails"] = 3
    assert kh.guard(ts, meta("返工", "planner-opus", "T001-1-plan")) is None
    ts["audit_post"].update(verdict="返工", target="执行端")
    assert kh.guard(ts, meta("返工", "exec-step", "T001-5-exec")) is None
    ts["stages"]["4-audit-pre"]["status"] = "assigned"
    assert "正在进行" in kh.guard(ts, meta("返工", "audit-sonnet", "T001-4-audit-pre"))


def test_guard_final_pass_needs_final_review():
    ts = locked(make_ts())
    assert "终审还没有通过" in kh.guard(ts, meta("通过", "exec-step", "T001-5-exec"))
    ts["audit_post"]["verdict"] = "通过"
    assert kh.guard(ts, meta("通过", "exec-step", "T001-5-exec")) is None
    assert "还没交付" in kh.guard(ts, meta("通过", "audit-sonnet", "T001-7-audit-post"))
    assert kh.guard(ts, meta("等待", "audit-sonnet", "T001-7-audit-post")) is None


def test_upstream_redelivery_invalidates_only_dependents():
    ts = locked(make_ts())
    ts["jev"]["3j-jev"] = {"status": "answered"}
    ts["audit_pre"].update(verdict="通过", fails=2)
    kh.invalidate_after(ts, "3-gate-pre")  # 门禁重新交付：JEV 只依赖合同，不作废
    assert "3j-jev" in ts["jev"]
    assert ts["audit_pre"] == {"fails": 2}
    ts["exec"].update(run_dir="r", check_ok=True)
    ts["stages"]["5-exec"]["status"] = "delivered"
    ts["audit_post"]["verdict"] = "通过"
    kh.invalidate_after(ts, "2-contract")  # 合同重新交付：基线、JEV、一审，以及隔了几层的执行与终审都作废
    assert ts["oracle"] == {} and "3j-jev" not in ts["jev"]
    assert ts["stages"]["3-gate-pre"]["status"] == "idle"
    assert ts["exec"] == {} and ts["stages"]["5-exec"]["status"] == "idle" and ts["audit_post"] == {}
    assert ts["stages"]["1-plan"]["status"] == "delivered"


def test_allowed_moves_lists_only_passing_letters():
    ts = make_ts()
    assert kh.allowed_moves(ts) == ["开工 → planner-opus（T001-1-plan）"]


# ---------------------------------------------------------------------------
# 回合审计（设计 §6.3）
# ---------------------------------------------------------------------------

def stream(*events: dict) -> list:
    return [json.dumps(event) for event in events]


INIT = {"type": "system", "subtype": "init", "tools": ["Read", "Grep", "Glob"], "mcp_servers": [],
        "model": "claude-sonnet-5-5", "session_id": "s1"}
SPEC = {"tools": ["Read", "Grep", "Glob"], "model": "claude-sonnet-5-5"}


def assistant(*blocks: dict, model: str = "claude-sonnet-5-5") -> dict:
    return {"type": "assistant", "message": {"model": model, "content": list(blocks)}}


def test_claude_audit_rejects_advisor_and_tools_outside_the_allowlist():
    clean = kh.audit_claude_stream(stream(INIT, assistant({"type": "tool_use", "name": "Read"}),
                                          {"type": "result", "result": "ok"}), SPEC)
    assert clean["violations"] == [] and clean["final_text"] == "ok"
    advisor = kh.audit_claude_stream(stream(INIT, assistant({"type": "server_tool_use", "name": "advisor"}),
                                            {"type": "result", "result": "ok"}), SPEC)
    assert any("advisor" in v for v in advisor["violations"])
    bash = kh.audit_claude_stream(stream(INIT, assistant({"type": "tool_use", "name": "Bash"})), SPEC)
    assert any("Bash" in v for v in bash["violations"])


def test_claude_audit_checks_init_and_model():
    bad_init = dict(INIT, tools=["Read", "Grep", "Glob", "Write"], mcp_servers=[{"name": "docs"}],
                    memory_paths={"auto": "x"})
    result = kh.audit_claude_stream(stream(bad_init), SPEC)
    text = "\n".join(result["violations"])
    assert "init 的工具" in text and "MCP" in text and "自动记忆" in text
    assert any("没有 init" in v for v in kh.audit_claude_stream(stream(), SPEC)["violations"])
    other = kh.audit_claude_stream(stream(INIT, assistant(model="claude-haiku-5-5")), SPEC)
    assert any("实际模型" in v for v in other["violations"])
    synthetic = kh.audit_claude_stream(stream(INIT, assistant(model="<synthetic>")), SPEC)
    assert synthetic["violations"] == []


def test_pi_audit_rejects_tools_and_records_effective_level():
    spec = {"tools": ["read", "grep"], "provider": "p", "model": "m"}
    events = stream({"type": "tool_execution_start", "toolName": "bash"},
                    {"type": "message_end", "message": {"role": "assistant", "provider": "p", "model": "m",
                                                        "thinkingLevel": "high", "stopReason": "stop",
                                                        "content": [{"type": "text", "text": "done"}]}},
                    {"type": "agent_settled"})
    result = kh.audit_pi_stream(events, spec)
    assert any("bash" in v for v in result["violations"])
    assert result["effective_levels"] == ["high"] and result["final_text"] == "done" and result["terminal"]
    other = kh.audit_pi_stream(stream({"type": "message_end", "message": {"role": "assistant", "provider": "q",
                                                                         "model": "m", "content": []}}), spec)
    assert any("实际模型" in v for v in other["violations"])


def test_output_block_is_the_last_json_fence():
    text = "前文\n```json\n{\"a\": 1}\n```\n中间\n```json\n{\"letter\": {\"type\": \"交付\"}}\n```\n"
    assert kh.extract_json_block(text) == {"letter": {"type": "交付"}}
    with pytest.raises(kh.HubError):
        kh.extract_json_block("没有代码块")
    with pytest.raises(kh.HubError):
        kh.extract_json_block("```json\n{坏的}\n```")


# ---------------------------------------------------------------------------
# 合同的内核要求（设计 §7）
# ---------------------------------------------------------------------------

def test_contract_requirements(tmp_path):
    hub = kh.Hub(tmp_path)
    ts = make_ts()
    ts["contract"] = {"key": "t001-doc.v1"}
    plans = tmp_path / ".agent" / "plans"
    plans.mkdir(parents=True)
    contract = {"scope": {"forbidden_paths": []}, "checks": [], "executor": {}, "authorization": {"integration": []}}
    (plans / "t001-doc.v1.json").write_text(json.dumps(contract), encoding="utf-8")
    problems = "\n".join(kh.contract_requirements(hub, ts))
    for needle in ("forbidden_paths", "test_gate_t001_baseline.py", "执行模型", "local_branch"):
        assert needle in problems
    contract.update(
        scope={"forbidden_paths": ["tests/test_gate_t001_*.py"]},
        checks=[{"id": "VG1", "argv": ["python", "-m", "pytest", "tests/test_gate_t001_baseline.py", "-q"],
                 "expect_on_base": "fail", "required": True}],
        executor={"provider": "bb", "model": "step-5-preview", "thinking": "high"},
        authorization={"integration": ["local_branch", "merge"]})
    (plans / "t001-doc.v1.json").write_text(json.dumps(contract), encoding="utf-8")
    assert kh.contract_requirements(hub, ts) == []
    contract["checks"][0]["expect_on_base"] = "pass"
    (plans / "t001-doc.v1.json").write_text(json.dumps(contract), encoding="utf-8")
    assert any("基线应失败" in p for p in kh.contract_requirements(hub, ts))


# ---------------------------------------------------------------------------
# 调度循环（假的回合启动器）
# ---------------------------------------------------------------------------

class FakeRunner:
    def __init__(self, outputs: list) -> None:
        self.outputs = list(outputs)
        self.calls = []

    def run(self, agent, session_key, workspace, role_prompt, prompt, retry_of=None, fresh=False):
        self.calls.append((agent, session_key, prompt))
        self.fresh = getattr(self, "fresh", []) + [fresh]
        output, violations = self.outputs.pop(0)
        return {"turn_id": "t%d" % len(self.calls), "turn_dir": "turns/x", "output": output,
                "violations": violations, "output_error": None if output is not None else "没有代码块"}


@pytest.fixture
def engine_env(tmp_path, monkeypatch):
    hub = kh.Hub(tmp_path)
    hub.ensure()
    state = {"tasks": {"T001": make_ts()}}
    hub.save_state(state)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.setattr(kh, "ensure_worktree", lambda hub, ts, kind, commit: workspace)
    monkeypatch.setattr(kh, "role_prompt", lambda agent: "角色：%s" % agent)
    return hub


def owner_task(hub):
    hub.deliver({"from": kh.OWNER, "to": kh.COORDINATOR, "task-id": "T001", "in-reply-to": "none", "type": "任务"},
                fields(摘要="改桌面端文档"))


def start_planner(brief: str = "# 任务书\n做规划") -> dict:
    return {"to": "planner-opus", "type": "开工", "task_id": "T001-1-plan", "in_reply_to": "none",
            "摘要": "开工规划", "提交": "无", "验证": "无", "偏离": "无", "需协调人决定": "无", "证据": "无",
            "brief": brief}


def test_coordinator_letters_pass_the_guard_before_delivery(engine_env):
    hub = engine_env
    owner_task(hub)
    bad = dict(start_planner(), to="exec-step", task_id="T001-5-exec")
    runner = FakeRunner([({"letters": [start_planner(), bad], "state": "s"}, [])])
    assert kh.Engine(hub, runner).step()
    state = hub.load_state()["tasks"]["T001"]
    assert state["stages"]["1-plan"]["status"] == "assigned"
    assert (hub.task_dir("T001-1-plan") / "brief.md").read_text(encoding="utf-8").startswith("# 任务书")
    assert len(hub.unread("planner-opus")) == 1
    assert hub.unread("exec-step") == []  # 一审没通过的开工被拒收
    notice = hub.unread(kh.COORDINATOR)
    assert len(notice) == 1 and "type: 核验" in notice[0].read_text(encoding="utf-8")
    assert state["coordinator_rejections"] == 1


def test_three_rejected_coordinator_turns_block_the_task(engine_env):
    hub = engine_env
    owner_task(hub)
    bad = dict(start_planner(), to="exec-step", task_id="T001-5-exec")
    runner = FakeRunner([({"letters": [bad]}, [])] * 3)
    engine = kh.Engine(hub, runner)
    for _ in range(3):
        assert engine.step()
    state = hub.load_state()["tasks"]["T001"]
    assert state["status"] == "blocked"
    assert any("type: 阻塞" in p.read_text(encoding="utf-8") for p in hub.unread(kh.OWNER))
    assert not engine.step() or hub.load_state()["tasks"]["T001"]["status"] == "blocked"


def test_start_without_brief_is_rejected(engine_env):
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([({"letters": [dict(start_planner(), brief="")]}, [])])
    kh.Engine(hub, runner).step()
    assert hub.unread("planner-opus") == []
    assert hub.load_state()["tasks"]["T001"]["stages"]["1-plan"]["status"] == "idle"


def planner_delivery() -> dict:
    return {"letter": {"type": "交付", "in_reply_to": "m", "摘要": "拆成 3 步", "提交": "无", "验证": "读了文档",
                       "偏离": "无", "需协调人决定": "无", "证据": "report.md"},
            "report": "# 概要步骤\n1. …", "state": "2026-10-19T00:00Z 交付"}


def test_worker_delivery_is_verified_then_forwarded(engine_env):
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([({"letters": [start_planner()]}, []), (planner_delivery(), [])])
    engine = kh.Engine(hub, runner)
    engine.step()  # 协调人开工规划端
    engine.step()  # 规划端交付
    assert runner.calls[1][0] == "planner-opus" and runner.calls[1][1] == "T001-1-plan"
    state = hub.load_state()["tasks"]["T001"]
    assert state["stages"]["1-plan"]["status"] == "delivered"
    assert (hub.task_dir("T001-1-plan") / "report.md").read_text(encoding="utf-8").startswith("# 概要步骤")
    letters = [p.read_text(encoding="utf-8") for p in hub.unread(kh.COORDINATOR)]
    assert len(letters) == 1 and "from: planner-opus" in letters[0] and "内核核验: 通过" in letters[0]


def test_worker_turn_with_violation_is_not_delivered(engine_env):
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([({"letters": [start_planner()]}, []),
                         (planner_delivery(), ["调用了白名单之外的工具：advisor（server_tool_use）"])])
    engine = kh.Engine(hub, runner)
    engine.step()
    engine.step()
    assert len(runner.calls) == 2  # 有违规就不再给第二次机会
    state = hub.load_state()["tasks"]["T001"]
    assert state["stages"]["1-plan"]["status"] == "failed"
    letters = [p.read_text(encoding="utf-8") for p in hub.unread(kh.COORDINATOR)]
    assert len(letters) == 1 and "from: 内核" in letters[0] and "advisor" in letters[0]
    assert not (hub.task_dir("T001-1-plan") / "report.md").exists()


def test_invalid_output_gets_one_retry(engine_env):
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([({"letters": [start_planner()]}, []), (None, []), (planner_delivery(), [])])
    engine = kh.Engine(hub, runner)
    engine.step()
    engine.step()
    assert len(runner.calls) == 3 and "上一次输出没有通过内核校验" in runner.calls[2][2]
    assert hub.load_state()["tasks"]["T001"]["stages"]["1-plan"]["status"] == "delivered"


def test_info_letters_do_not_wake_workers(engine_env):
    hub = engine_env
    hub.deliver({"from": kh.COORDINATOR, "to": "planner-opus", "task-id": "T001-1-plan", "in-reply-to": "none",
                 "type": "等待"}, fields())
    runner = FakeRunner([])
    assert kh.Engine(hub, runner).step()
    assert runner.calls == [] and hub.unread("planner-opus") == []


def test_rework_starts_a_clean_session(engine_env):
    hub = engine_env
    state = hub.load_state()
    state["tasks"]["T001"]["stages"]["1-plan"]["status"] = "assigned"
    hub.save_state(state)
    for kind in ("开工", "返工"):
        for path in hub.unread(kh.COORDINATOR):  # 上一轮转给协调人的交付信：先读掉，免得它先被处理
            hub.take(path)
        hub.deliver({"from": kh.COORDINATOR, "to": "planner-opus", "task-id": "T001-1-plan", "in-reply-to": "none",
                     "type": kind}, fields())
        runner = FakeRunner([(planner_delivery(), [])])
        kh.Engine(hub, runner).step()
        assert runner.calls[0][0] == "planner-opus" and runner.fresh == [kind == "返工"]


def test_role_prompt_only_renders_the_workers_own_duties():
    planner = kh.role_prompt("planner-opus")
    assert "`planner-opus`（规划端）" in planner and "`gate-sonnet`（门禁端）" not in planner
    assert "<!--" not in planner and "{{" not in planner
    gate = kh.role_prompt("gate-sonnet")
    assert "只增不改" in gate and "`audit-sonnet`（审核端）" not in gate
    assert "planner-opus" in kh.role_prompt(kh.COORDINATOR)


def test_session_ids_change_on_a_fresh_restart(tmp_path):
    hub = kh.Hub(tmp_path)
    hub.ensure()
    seen = []

    def launcher(cmd, cwd, env, out, err, timeout):
        seen.append(cmd)
        out.write(b'{"type":"message_end","message":{"role":"assistant","provider":"cc-switch-zhipu-glm",'
                  b'"model":"glm-5.3","thinkingLevel":"high","stopReason":"stop","content":[{"type":"text",'
                  b'"text":"```json\\n{\\"letter\\": {}}\\n```"}]}}\n')
        return {"exit_code": 0, "timed_out": False, "wall_seconds": 1.0}

    runner = kh.TurnRunner(hub, launcher=launcher)
    for fresh in (False, False, True):
        runner.run("contract-glm", "T001-2-contract", tmp_path, "角色", "输入", fresh=fresh)
    ids = [cmd[cmd.index("--session-id") + 1] for cmd in seen]
    assert ids == ["T001-2-contract-g0", "T001-2-contract-g0", "T001-2-contract-g1"]
    assert all(cmd[-2].startswith("@") for cmd in seen)  # pi 的输入一律经 @文件


def test_worker_env_drops_the_decision_key_and_host_session_vars(monkeypatch):
    monkeypatch.setenv(kh.DECISIONS_KEY_ENV, "examplevalue")
    monkeypatch.setenv("CLAUDECODE", "1")
    env = kh.worker_env()
    assert kh.DECISIONS_KEY_ENV not in env and "CLAUDECODE" not in env
    assert kh.DECISIONS_KEY_ENV not in kh.kernel_env()
