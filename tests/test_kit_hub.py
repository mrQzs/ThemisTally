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
    # 复审封板：返工要一次列全阻塞项
    assert any("阻塞项" in e for e in kh.letter_errors(head, fields(结论="返工", 退回="门禁端"), 8))
    assert any("阻塞项" in e for e in kh.letter_errors(head, fields(结论="返工", 退回="门禁端", 阻塞项="无"), 9))
    assert kh.letter_errors(head, fields(结论="返工", 退回="门禁端", 阻塞项="1. 断言太松"), 9) == []
    # 一审时还没有执行：不能退回执行端或战后门禁
    for target in ("执行端", "战后门禁"):
        assert any("一审只能退回" in e for e in kh.letter_errors(head, fields(结论="返工", 退回=target, 阻塞项="x"), 9))
    final = dict(head, **{"task-id": "T001-7-audit-post"})
    assert kh.letter_errors(final, fields(结论="返工", 退回="战后门禁", 阻塞项="x"), 9) == []


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
    assert "没有一审或终审退回" in kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract"))
    assert "没有一审或终审退回" in kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre"))
    ts["audit_pre"].update(verdict="返工", target="门禁端")
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre")) is None
    assert "没有一审或终审退回" in kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract"))
    ts["stages"]["2-contract"]["status"] = "failed"  # 内核核验失败也允许返工
    assert kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract")) is None
    assert "不到 3 次" in kh.guard(ts, meta("返工", "planner-opus", "T001-1-plan"))
    ts["audit_pre"]["fails"] = 3
    assert kh.guard(ts, meta("返工", "planner-opus", "T001-1-plan")) is None
    ts["audit_post"].update(verdict="返工", target="执行端")
    assert kh.guard(ts, meta("返工", "exec-step", "T001-5-exec")) is None
    ts["stages"]["4-audit-pre"]["status"] = "assigned"
    assert "正在进行" in kh.guard(ts, meta("返工", "audit-sonnet", "T001-4-audit-pre"))


def test_final_review_can_return_to_the_contract_and_to_the_post_gate():
    ts = locked(make_ts())
    ts["audit_pre"].update(verdict="通过")
    assert kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract")) is not None
    assert "战后门禁" in kh.guard(ts, meta("返工", "gate-sonnet", "T001-6-gate-post"))
    ts["audit_post"].update(verdict="返工", target="合同端")  # 原来是死路：只认一审的退回
    assert kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract")) is None
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-6-gate-post")) is not None
    ts["audit_post"]["target"] = "战后门禁"
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-6-gate-post")) is None
    assert kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract")) is not None


def test_owner_can_order_a_rework_before_the_first_review(tmp_path, monkeypatch):
    import io
    repo, head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    ts = kh.new_task_state("T001", "doc", "改文档", head, True)
    ts["stages"]["2-contract"]["status"] = "delivered"
    hub.save_state({"tasks": {"T001": ts}})
    assert kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract")) is not None
    monkeypatch.setattr(sys, "stdin", io.StringIO("合同去掉待确认标注"))
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    for bad in (["--type", "停止", "--rework", "2-contract"], ["--type", "回复", "--rework", "3j-jev"],
                ["--type", "回复", "--rework", "9-x"]):
        assert kh.main(["--repo", str(repo), "send", "T001"] + bad) == kh.EXIT_USAGE
    assert kh.main(["--repo", str(repo), "send", "T001", "--type", "回复", "--rework", "2-contract"]) == kh.EXIT_OK
    state = hub.load_state()
    assert state["tasks"]["T001"]["owner_rework"]["suffix"] == "2-contract"
    letter = hub.unread(kh.COORDINATOR)[0].read_text(encoding="utf-8")
    assert "站主要求 T001-2-contract 返工" in letter
    ts = state["tasks"]["T001"]
    assert kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract")) is None
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre")) is not None  # 只放行指定的那一个阶段
    engine = kh.Engine(hub, FakeRunner([]))
    assert engine.deliver_coordinator_letter(state, dict(start_planner(), to="contract-glm", type="返工",
                                                         task_id="T001-2-contract")) is None
    ts = hub.load_state()["tasks"]["T001"]
    assert "owner_rework" not in ts and ts["stages"]["2-contract"]["status"] == "assigned"  # 用过就作废


def test_gate_hotfix_needs_the_executors_evidence_or_a_final_review_return():
    ts = locked(make_ts())
    ts["audit_pre"].update(verdict="通过", contract_sha256="c1", oracle_sha="o" * 40)
    ts["exec"].update(run_dir="r", check_ok=False, conflicts=0)
    assert "没有一审或终审退回" in kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre"))
    ts["exec"]["conflicts"] = 2  # 执行端举证
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre")) is None
    ts["exec"]["conflicts"] = 0
    ts["audit_post"].update(verdict="返工", target="执行端")
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre")) is not None
    ts["audit_post"]["target"] = "门禁端"  # 终审退回门禁端
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre")) is None
    kh.invalidate_after(ts, "3-gate-pre")  # 热修补交付后：一审、执行、终审都作废，执行端必须重跑
    assert kh.hotfix_reason(ts) is None
    assert "一审还没有通过" in kh.guard(ts, meta("开工", "exec-step", "T001-5-exec"))


def test_hotfix_rework_records_the_previous_baseline(engine_env):
    hub = engine_env
    state = hub.load_state()
    ts = locked(state["tasks"]["T001"])
    ts["exec"].update(run_dir="r", check_ok=False, conflicts=1)
    hub.save_state(state)
    hub.deliver({"from": kh.OWNER, "to": kh.COORDINATOR, "task-id": "T001", "in-reply-to": "none", "type": "回复"},
                fields())
    item = dict(start_planner("# 热修补\n第 3 条断言写反了"), to="gate-sonnet", type="返工", task_id="T001-3-gate-pre")
    kh.Engine(hub, FakeRunner([({"letters": [item]}, [])])).step()
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["hotfix"]["previous_oracle"] == "o" * 40 and "合同矛盾" in ts["hotfix"]["reason"]
    assert ts["stages"]["3-gate-pre"]["status"] == "assigned"


def test_dispatched_contract_is_bumped_not_edited(tmp_path):
    hub = kh.Hub(tmp_path)
    ts = make_ts()
    plans = tmp_path / ".agent" / "plans"
    plans.mkdir(parents=True)
    (plans / "t001-doc.v1.md").write_text("# TASK: t001-doc\n\n## Identity\n- plan_version: 1\n- base_sha: x\n",
                                         encoding="utf-8")
    ts["contract"] = {"key": "t001-doc.v1", "version": 1, "dispatched": True}
    assert kh.bump_contract_version(hub, ts) == []
    assert ts["contract"]["key"] == "t001-doc.v2" and "dispatched" not in ts["contract"]
    assert "- plan_version: 2" in (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    assert "- plan_version: 1" in (plans / "t001-doc.v1.md").read_text(encoding="utf-8")  # 已派遣的版本不动
    ts["contract"].update(key="t001-doc.v1", version=1)
    assert any("已存在" in p for p in kh.bump_contract_version(hub, ts))


def git_repo(tmp_path):
    import subprocess
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["config", "user.name", "t"], ["config", "user.email", "t@example.invalid"],
                 ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git"] + args, cwd=str(repo), check=True)
    (repo / "README.md").write_text("基线\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=str(repo), check=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), check=True,
                          stdout=subprocess.PIPE).stdout.decode().strip()
    return repo, head


def test_gate_pre_commit_bumps_a_dispatched_contract_and_keeps_the_hotfix_diff(tmp_path, monkeypatch):
    repo, head = git_repo(tmp_path)
    roots = tmp_path / "worktrees"
    roots.mkdir()
    monkeypatch.setattr(kh, "worktree_root", lambda repo_path: roots)
    calls = []
    monkeypatch.setattr(kh, "run_pd", lambda hub, args, timeout=600: calls.append(list(args)) or (0, "ok"))
    hub = kh.Hub(repo)
    hub.ensure()
    ts = kh.new_task_state("T001", "doc", "改文档", head, True)
    plans = repo / ".agent" / "plans"
    plans.mkdir(parents=True)
    contract = {"scope": {"forbidden_paths": ["tests/test_gate_t001_*.py"]},
                "checks": [{"argv": ["python", "-m", "pytest", "tests/test_gate_t001_baseline.py", "-q"],
                            "expect_on_base": "fail", "required": True}],
                "executor": {key: kh.ROSTER["exec-step"][key] for key in ("provider", "model", "thinking")},
                "authorization": {"integration": ["local_branch", "merge"]}}
    for version in (1, 2):  # run_pd 是假的：derive-json 不会真的写 JSON，先放好
        (plans / ("t001-doc.v%d.json" % version)).write_text(json.dumps(contract), encoding="utf-8")
    (plans / "t001-doc.v1.md").write_text("# TASK: t001-doc\n- plan_version: 1\n- base_sha: %s\n" % head,
                                         encoding="utf-8")
    ts["contract"] = {"key": "t001-doc.v1", "version": 1}
    workspace = kh.ensure_worktree(hub, ts, "gate", head)
    target = workspace / "tests" / "test_gate_t001_baseline.py"
    target.parent.mkdir(parents=True)
    target.write_text("def test_x():\n    assert False\n", encoding="utf-8")
    assert kh.accept_gate_pre(hub, ts, workspace) == []
    first = ts["oracle"]["sha"]
    assert ts["oracle"]["locked"] and ts["contract"]["key"] == "t001-doc.v1"
    assert "- base_sha: %s" % first in (plans / "t001-doc.v1.md").read_text(encoding="utf-8")
    assert ["baseline", "t001-doc.v1"] in calls
    # 派遣过之后热修补：退回基线、改测试、重新交付 → 出 v2，v1 不动，差异留给一审
    ts["contract"]["dispatched"] = True
    ts["hotfix"] = {"reason": "执行端报了 1 条合同矛盾", "previous_oracle": first}
    engine = kh.Engine(hub, FakeRunner([]))
    assert engine.stage_workspace(ts, "gate-sonnet", "3-gate-pre") == workspace
    target.write_text("def test_x():\n    assert 1 == 2  # 改了断言\n", encoding="utf-8")
    assert kh.accept_gate_pre(hub, ts, workspace) == []
    assert ts["contract"]["key"] == "t001-doc.v2" and ts["oracle"]["sha"] != first
    assert "- base_sha: %s" % first in (plans / "t001-doc.v1.md").read_text(encoding="utf-8")
    assert "- base_sha: %s" % ts["oracle"]["sha"] in (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    diff = (repo / ts["oracle"]["hotfix_diff"]).read_text(encoding="utf-8")
    assert "assert 1 == 2" in diff and "assert False" in diff
    assert "hotfix" not in ts and ts["hotfixes"][0]["oracle"] == ts["oracle"]["sha"]
    refs = kh.git(["for-each-ref", "--format=%(refname)", "refs/themis/oracle/"], repo).split()
    assert refs == ["refs/themis/oracle/t001-doc/v1", "refs/themis/oracle/t001-doc/v2"]
    # 门禁端改了别的文件：拒收
    (workspace / "README.md").write_text("改了\n", encoding="utf-8")
    kh.git(["reset", "-q", "--mixed", head], workspace)
    assert any("不能改动别的文件" in p for p in kh.accept_gate_pre(hub, ts, workspace))
    kh.git(["worktree", "remove", "--force", str(workspace)], repo)


def gate_setup(tmp_path, monkeypatch, run_pd=None):
    repo, head = git_repo(tmp_path)
    roots = tmp_path / "worktrees"
    roots.mkdir()
    monkeypatch.setattr(kh, "worktree_root", lambda repo_path: roots)
    calls = []
    monkeypatch.setattr(kh, "run_pd", run_pd or (lambda hub, args, timeout=600: calls.append(list(args)) or (0, "ok")))
    hub = kh.Hub(repo)
    hub.ensure()
    ts = kh.new_task_state("T001", "doc", "改文档", head, True)
    plans = repo / ".agent" / "plans"
    plans.mkdir(parents=True)
    contract = {"scope": {"forbidden_paths": ["tests/test_gate_t001_*.py"]},
                "checks": [{"argv": ["python", "-m", "pytest", "tests/test_gate_t001_baseline.py", "-q"],
                            "expect_on_base": "fail", "required": True}],
                "executor": {key: kh.ROSTER["exec-step"][key] for key in ("provider", "model", "thinking")},
                "authorization": {"integration": ["local_branch", "merge"]},
                "definition_of_done": [{"id": "D01"}, {"id": "D02"}, {"id": "D11"}]}
    (plans / "t001-doc.v1.json").write_text(json.dumps(contract), encoding="utf-8")
    (plans / "t001-doc.v1.md").write_text("# TASK: t001-doc\n- plan_version: 1\n- base_sha: %s\n" % head,
                                         encoding="utf-8")
    ts["contract"] = {"key": "t001-doc.v1", "version": 1}
    return repo, head, hub, ts, plans, calls


def test_gate_pre_rejects_a_baseline_that_does_not_collect(tmp_path, monkeypatch):
    repo, head, hub, ts, _plans, calls = gate_setup(tmp_path, monkeypatch)
    workspace = kh.ensure_worktree(hub, ts, "gate", head)
    target = workspace / "tests" / "test_gate_t001_baseline.py"
    target.parent.mkdir(parents=True)
    # 在基线上照样“失败”，但失败在收集上：断言什么也没证明（空心基线）
    for text in ("def test_x(:\n    pass\n", "from not_written_yet import feature\n\ndef test_x():\n    assert feature()\n",
                 "# 没有用例\n"):
        target.write_text(text, encoding="utf-8")
        problems = kh.accept_gate_pre(hub, ts, workspace)
        assert len(problems) == 1 and "收集失败" in problems[0], problems
        assert calls == [] and not ts["oracle"]  # 没提交、没锁定
    target.write_text("def test_x():\n    from not_written_yet import feature\n    assert feature()\n", encoding="utf-8")
    assert kh.accept_gate_pre(hub, ts, workspace) == [] and ts["oracle"]["locked"]
    kh.git(["worktree", "remove", "--force", str(workspace)], repo)


def test_contract_with_pending_marks_is_rejected(tmp_path, monkeypatch):
    _repo, _head, hub, ts, plans, _calls = gate_setup(tmp_path, monkeypatch)
    md = plans / "t001-doc.v1.md"
    clean = md.read_text(encoding="utf-8")
    assert kh.contract_requirements(hub, ts) == []
    md.write_text(clean + "- A7：加四行【与任务书不同，待站主确认】\n- A13：【Q2 待确认】\n", encoding="utf-8")
    problems = kh.contract_requirements(hub, ts)
    assert len(problems) == 1 and "2 处未决标注" in problems[0] and "提问" in problems[0]
    md.write_text(clean + "- A7：加四行（站主 2026-10-19 已确认）\n", encoding="utf-8")
    assert kh.contract_requirements(hub, ts) == []


def write_budget(hub, ts, attempts, total, per=3600):
    plans = hub.repo / ".agent" / "plans"
    plans.mkdir(parents=True, exist_ok=True)
    ts["contract"].update(key="t001-doc.v2", version=2)
    (plans / "t001-doc.v2.json").write_text(json.dumps({"budget": {
        "max_attempts_total": attempts, "max_wall_seconds_per_attempt": per, "max_wall_seconds_total": total}}),
        encoding="utf-8")


def claim_attempt(hub, n, wall=None, reserved=None):
    attempt = hub.repo / ".agent" / "runs" / "t001-doc" / ("attempt-%03d" % n)
    (attempt / "claim").mkdir(parents=True)
    if wall is not None:
        (attempt / "run.json").write_text(json.dumps({"wall_seconds": wall}), encoding="utf-8")
    if reserved is not None:
        (attempt / "claim" / "reservation.json").write_text(json.dumps({"timeout_seconds": reserved}),
                                                            encoding="utf-8")


def test_contract_budget_counts_attempts_of_earlier_versions(tmp_path):
    # T002：v2 照抄 v1 的 2 次，调度器跨版本累计，v1 已经用掉 1 次，v2 只剩 1 次（第 8 轮）
    hub = kh.Hub(tmp_path)
    ts = make_ts()
    write_budget(hub, ts, 2, 7200)
    assert kh.budget_problems(hub, ts) == []  # 还没有派遣过
    claim_attempt(hub, 1, wall=1671.4)
    problems = kh.budget_problems(hub, ts)
    assert len(problems) == 2
    assert "已用掉 1 次，这一版只剩 1 次" in problems[0] and "只剩 5528 秒" in problems[1]
    write_budget(hub, ts, 3, 10800)
    assert kh.budget_problems(hub, ts) == []
    write_budget(hub, ts, 3, 8000)  # 次数够、墙钟不够两次单次时限
    assert [p for p in kh.budget_problems(hub, ts)] == [
        "max_wall_seconds_total=8000，已用掉 1671 秒，只剩 6328 秒：至少留 2 次单次时限（7200 秒）"]
    claim_attempt(hub, 2, reserved=3600)  # 还在跑的 attempt 按预留的时限计
    write_budget(hub, ts, 4, 14400)
    assert kh.budget_problems(hub, ts) == []
    write_budget(hub, ts, 3, 14400)
    assert "已用掉 2 次，这一版只剩 1 次" in kh.budget_problems(hub, ts)[0]


def test_contract_delivery_is_refused_when_the_budget_leaves_one_attempt(tmp_path, monkeypatch):
    hub = kh.Hub(tmp_path)
    ts = make_ts()
    claim_attempt(hub, 1, wall=1671)
    budget = {"attempts": 2}

    def revalidate(hub, ts):
        write_budget(hub, ts, budget["attempts"], 10800)
        ts["contract"]["validated"] = True
        return []

    monkeypatch.setattr(kh, "revalidate_contract", revalidate)
    problems = kh.accept_contract(hub, ts, {"contract_md": "# TASK: t001-doc\n正文"})
    assert len(problems) == 1 and "这一版只剩 1 次" in problems[0]
    assert ts["contract"]["validated"] is False  # 门禁端开不了工
    assert kh.guard(dict(ts, stages=dict(ts["stages"])), meta("开工", "gate-sonnet", "T001-3-gate-pre")) is not None
    budget["attempts"] = 3
    assert kh.accept_contract(hub, ts, {"contract_md": "# TASK: t001-doc\n正文"}) == []
    assert ts["contract"]["validated"] is True and ts["contract"]["key"] == "t001-doc.v2"
    # 合同端的回合输入写明已用掉的预算
    prompt = kh.turn_prompt(hub, ts, "contract-glm", "T001-2-contract", [], tmp_path)
    assert "`t001-doc` 各版本的累计上限" in prompt and "已用掉 1 次、1671 秒" in prompt


def test_planner_sees_the_transitional_gate_assertions(tmp_path):
    hub = kh.Hub(tmp_path)
    ts = make_ts()
    workspace = tmp_path / "ws"
    (workspace / "tests").mkdir(parents=True)
    (workspace / "tests" / "test_gate_t002_baseline.py").write_text(
        "def test_g1_keeps():\n    assert True\n\n\n"
        "def test_transitional_no_fonts(pipeline):\n"
        "    \"\"\"T003 随包字体会推翻：第 1 片不带字体文件。\"\"\"\n    assert True\n\n\n"
        "class TestNotices:\n    def test_transitional_notices_only_lucide(self) -> None:\n        assert True\n",
        encoding="utf-8")
    (workspace / "tests" / "test_other.py").write_text("def test_transitional_ignored():\n    pass\n",
                                                     encoding="utf-8")
    section = kh.transitional_section(workspace)
    assert section[1].startswith("## 仓库里现有的过渡断言")
    assert "- `tests/test_gate_t002_baseline.py::test_transitional_no_fonts`：T003 随包字体会推翻：第 1 片不带字体文件。" \
        in section
    assert "- `tests/test_gate_t002_baseline.py::test_transitional_notices_only_lucide`：（没有说明）" in section
    assert not any("test_g1_keeps" in line or "ignored" in line for line in section)
    assert "## 仓库里现有的过渡断言" in kh.turn_prompt(hub, ts, "planner-opus", "T001-1-plan", [], workspace)
    assert "## 仓库里现有的过渡断言" not in kh.turn_prompt(hub, ts, "audit-sonnet", "T001-4-audit-pre", [], workspace)
    assert kh.transitional_section(tmp_path / "empty") == []
    assert "test_transitional_" in kh.role_prompt("gate-sonnet")


def test_gate_rules_keep_the_regression_tests_valid_after_integration():
    # T002 的 D02 断言“相对基线的改动只落在允许集合内”，落到分支末端上必然失败（第 11 轮）
    assert "不写相对基线的改动范围断言" in kh.role_prompt("gate-sonnet")
    assert "集成之后必然失败，退回门禁端" in kh.role_prompt("audit-sonnet")
    assert "不写相对基线的改动范围断言" not in kh.role_prompt("planner-opus")


def test_first_review_report_must_map_every_dod(tmp_path, monkeypatch):
    _repo, _head, hub, ts, _plans, _calls = gate_setup(tmp_path, monkeypatch)
    problems = kh.dod_coverage_problems(hub, ts, "| D01 | test_a | assert x |\n| D11 | 只能人工审阅 |")
    assert len(problems) == 1 and "D02" in problems[0] and "D11" not in problems[0]
    assert kh.dod_coverage_problems(hub, ts, "D01 D02 D11") == []
    assert kh.dod_coverage_problems(hub, ts, "D011 D02 D11")  # D011 不算 D01
    engine = kh.Engine(hub, FakeRunner([]))
    assert engine.verify_delivery(ts, "audit-sonnet", "4-audit-pre", {"report": "D01"}, {"结论": "通过"})
    assert engine.verify_delivery(ts, "audit-sonnet", "7-audit-post", {"report": ""}, {"结论": "通过"}) == []


def mutation_record(*statuses, unexpected=None) -> dict:
    results = []
    for index, status in enumerate(statuses, 1):
        miss = status == "missed" and (unexpected is None or index in unexpected)
        results.append({"id": "M%02d" % index, "status": status, "unexpected": ["W1"] if miss else []})
    return {"results": results, "counts": {}}


def test_mutation_verdict_reads_the_record_not_the_exit_code():
    # mutate --tree 的退出码在变异漏网时也是 0：只看退出码，这一关等于没有
    assert kh.mutation_problems(0, mutation_record("caught", "caught"), "") == []
    missed = kh.mutation_problems(0, mutation_record("caught", "missed"), "")
    assert len(missed) == 1 and "M02" in missed[0] and "漏网" in missed[0]
    assert kh.mutation_problems(0, mutation_record("caught", "missed", unexpected=[]), "") == []  # 声明等价的漏网
    for status in ("skipped", "error"):
        assert any("没有生效" in p for p in kh.mutation_problems(0, mutation_record("caught", status), ""))
    multi = {"results": [{"id": "M01", "status": "caught", "unexpected": [],
                          "commands": {"W1": {"status": "caught"}, "W2": {"status": "error"}}}]}
    assert any("没有生效" in p for p in kh.mutation_problems(0, multi, ""))
    assert any("没有一条变异被抓住" in p for p in kh.mutation_problems(0, mutation_record("missed", unexpected=[]), ""))
    assert any("没有跑完" in p for p in kh.mutation_problems(2, mutation_record("caught"), "baseline failed"))
    assert any("没有跑完" in p for p in kh.mutation_problems(0, {}, ""))


def test_gate_post_judges_mutations_from_the_record(tmp_path, monkeypatch):
    records = {}

    def fake_pd(hub, args, timeout=600):
        out_dir = Path(args[args.index("--out") + 1])
        out_dir.mkdir(parents=True)
        (out_dir / "mutations.json").write_text(json.dumps(records["next"]), encoding="utf-8")
        return 0, "变异 2 条"

    repo, head, hub, ts, _plans, _calls = gate_setup(tmp_path, monkeypatch, run_pd=fake_pd)
    run_dir = tmp_path / "attempt-001"
    ts["exec"] = {"run_dir": str(run_dir)}
    workspace = kh.ensure_worktree(hub, ts, "post-attempt-001", head)
    ts["workspaces"]["post-attempt-001"]["baseline_status"] = []
    target = workspace / "tests" / "test_gate_t001_whitebox.py"
    target.parent.mkdir(parents=True)
    target.write_text("def test_ok():\n    print('白盒输出')\n", encoding="utf-8")
    spec = {"mutations": [{"name": "去掉检查", "file": "README.md", "old": "基线", "new": "x"},
                          {"name": "等价改写", "file": "README.md", "old": "线", "new": "线", "equivalent": "同一个字"}]}
    records["next"] = mutation_record("caught", "missed")
    problems = kh.accept_gate_post(hub, ts, workspace, {"mutation_spec": spec})
    assert any("漏网" in p for p in problems) and ts["gate_post"]["ok"] is False
    assert ts["gate_post"]["mutate_exit"] == 0  # 退出码是 0，照样不通过
    records["next"] = mutation_record("caught", "missed", unexpected=[])
    assert kh.accept_gate_post(hub, ts, workspace, {"mutation_spec": spec}) == [] and ts["gate_post"]["ok"]
    assert ts["gate_post"]["equivalent"] == ["等价改写：同一个字"]
    record = ts["gate_post"]["mutate_record"]  # 在信箱的证据目录里：终审读得到
    assert record.startswith(".agent/mailbox/tasks/T001-6-gate-post/evidence/mutate-") and (repo / record).is_file()
    log = repo / ts["gate_post"]["whitebox_log"]
    assert log.is_file() and ts["gate_post"]["whitebox_exit"] == 0 and "passed" in ts["gate_post"]["whitebox_tail"]
    target.write_text("def test_bad():\n    assert False\n", encoding="utf-8")
    assert any("白盒测试" in p for p in kh.accept_gate_post(hub, ts, workspace, {"mutation_spec": spec}))
    kh.git(["worktree", "remove", "--force", str(workspace)], repo)


PYTEST_LOG = """\
tests/test_w.py .F..sxFE                                                [100%]
=================================== ERRORS ====================================
_________________________ ERROR at setup of test_err __________________________
---------------------------- Captured stdout call -----------------------------
FAILED tests/fake.py::inside_capture - 用例自己打印的
3 passed, 4 deselected in 0.01s
=========================== short test summary info ===========================
FAILED tests/test_w.py::test_probe[constructor] - AssertionError: assert 'con...
FAILED tests/test_w.py::test_probe[a b] - AssertionError: x - y
FAILED tests/test_w.py::TestK::test_m
ERROR tests/test_w.py::test_err - RuntimeError: fixture
3 failed, 2 passed, 1 skipped, 1 xfailed, 1 error, 2 warnings in 75.43s (0:01:15)
"""


def test_pytest_outcomes_reads_the_summary_not_the_captured_output(tmp_path):
    log = tmp_path / "whitebox.log"
    log.write_text(PYTEST_LOG, encoding="utf-8")
    counts, failed, errored = kh.pytest_outcomes(log)
    assert counts == {"failed": 3, "passed": 2, "skipped": 1, "xfailed": 1, "errors": 1, "warnings": 2}
    assert failed == ["tests/test_w.py::test_probe[constructor]", "tests/test_w.py::test_probe[a b]",
                      "tests/test_w.py::TestK::test_m"]
    assert errored == ["tests/test_w.py::test_err"]
    assert kh.defect_matches("test_probe", failed[1]) and kh.defect_matches("TestK::test_m", failed[2])
    assert kh.defect_matches("test_probe[a b]", failed[1]) and not kh.defect_matches("test_probe[a b]", failed[0])
    assert kh.defect_matches(failed[0], failed[0]) and not kh.defect_matches("test_m", failed[0])
    assert not kh.defect_matches("probe", failed[0]) and not kh.defect_matches("test_w.py", failed[0])


def test_gate_post_may_leave_the_candidate_red_with_evidence(tmp_path, monkeypatch):
    # T002：战后门禁把 3 处合同违反标成 xfail(strict=True)，候选照样“通过”，靠终审才拦下来（第 9 轮）
    calls = []

    def fake_pd(hub, args, timeout=600):
        calls.append(args[0])
        out_dir = Path(args[args.index("--out") + 1])
        out_dir.mkdir(parents=True)
        (out_dir / "mutations.json").write_text(json.dumps(mutation_record("caught")), encoding="utf-8")
        return 0, "变异 1 条"

    repo, head, hub, ts, _plans, _calls = gate_setup(tmp_path, monkeypatch, run_pd=fake_pd)
    ts["exec"] = {"run_dir": str(tmp_path / "attempt-001")}
    workspace = kh.ensure_worktree(hub, ts, "post-attempt-001", head)
    ts["workspaces"]["post-attempt-001"]["baseline_status"] = []
    target = workspace / "tests" / "test_gate_t001_whitebox.py"
    target.parent.mkdir(parents=True)
    spec = {"mutations": [{"name": "去掉检查", "file": "README.md", "old": "基线", "new": "x"}]}
    defect = {"test": "test_probe", "contract": "任意状态码：原样显示，不报错", "where": "src/a.ts:83"}

    def deliver(body, **output):
        target.write_text("import pytest\n\n\ndef test_ok():\n    assert True\n\n\n" + body, encoding="utf-8")
        return kh.accept_gate_post(hub, ts, workspace, dict(output, mutation_spec=spec))

    probe = "@pytest.mark.parametrize('code', ['ok', 'constructor'])\ndef test_probe(code):\n    assert code == 'ok'\n"
    problems = deliver("@pytest.mark.xfail(strict=True)\ndef test_known():\n    assert False\n")
    assert any("1 个 xfailed" in p for p in problems) and not ts["gate_post"]["ok"]
    assert ts["gate_post"]["whitebox_counts"] == {"passed": 1, "xfailed": 1}
    assert any("1 个 skipped" in p for p in deliver("@pytest.mark.skip(reason='x')\ndef test_later():\n    pass\n"))
    calls.clear()
    assert deliver(probe, candidate_defects=[defect]) == []
    assert ts["gate_post"]["defects"] == [defect] and ts["gate_post"]["ok"] is False
    assert calls == [] and "mutate_record" not in ts["gate_post"]  # 候选是红的：变异检查不跑
    assert ts["gate_post"]["whitebox_counts"] == {"failed": 1, "passed": 2}
    assert "候选有 1 处缺陷" in kh.stage_status_table(hub, ts)
    other = probe + "\n\ndef test_other():\n    assert False\n"
    problems = deliver(other, candidate_defects=[defect])
    assert problems == ["这些用例红了，candidate_defects 却没有列：tests/test_gate_t001_whitebox.py::test_other"
                        "（白盒测试自己有错就改测试）"]
    assert "defects" not in ts["gate_post"]
    problems = deliver(probe, candidate_defects=[defect, dict(defect, test="test_ok")])
    assert problems == ["candidate_defects 列的这些用例没有红：test_ok"]
    problems = deliver(probe, candidate_defects=[dict(defect, contract=" ")])
    assert any("第 1 条缺 contract" in p for p in problems) and "defects" not in ts["gate_post"]
    assert any("候选不满足合同写明的行为时" in p for p in deliver(probe))  # 红了却没有举证
    broken = probe + "\n\n@pytest.fixture\ndef env():\n    raise RuntimeError('x')\n\n\ndef test_env(env):\n    pass\n"
    assert any("没有全部通过" in p for p in deliver(broken, candidate_defects=[defect]))  # 出错不是缺陷
    problems = deliver("", candidate_defects=[defect])
    assert any("可白盒测试在候选上全部通过" in p for p in problems) and calls == ["mutate"]
    assert kh.accept_gate_post(hub, ts, workspace, {"mutation_spec": spec}) == [] and ts["gate_post"]["ok"]
    kh.git(["worktree", "remove", "--force", str(workspace)], repo)


def test_candidate_defects_go_to_the_final_review_which_cannot_pass_them(tmp_path):
    hub = kh.Hub(tmp_path)
    hub.ensure()
    engine = kh.Engine(hub, FakeRunner([]))
    ts = locked(make_ts())
    ts["exec"].update(run_dir="r", check_ok=True)
    defect = {"test": "test_probe", "contract": "任意状态码：原样显示，不报错", "where": "src/a.ts:83"}
    ts["gate_post"] = {"ran": True, "ok": False, "defects": [defect], "whitebox_log": "w.log"}
    assert kh.guard(ts, meta("开工", "jev-judge", "T001-6j-jev")) is None
    ts["jev"]["6j-jev"] = {"status": "answered"}
    assert kh.guard(ts, meta("开工", "audit-sonnet", "T001-7-audit-post")) is None
    assert kh.guard(ts, meta("返工", "exec-step", "T001-5-exec")) is None
    passed = engine.verify_delivery(ts, "audit-sonnet", "7-audit-post", {"report": ""}, {"结论": "通过"})
    assert len(passed) == 1 and "举证了 1 处候选缺陷，不能判通过" in passed[0]
    assert engine.verify_delivery(ts, "audit-sonnet", "7-audit-post", {"report": ""},
                                  {"结论": "返工", "退回": "执行端"}) == []
    prompt = kh.turn_prompt(hub, ts, "audit-sonnet", "T001-7-audit-post", [], tmp_path)
    assert "## 门禁端举证的候选缺陷" in prompt and "- `test_probe`：src/a.ts:83 —— 合同：任意状态码：原样显示，不报错" in prompt
    assert "门禁端举证的候选缺陷" not in kh.turn_prompt(hub, ts, "audit-sonnet", "T001-4-audit-pre", [], tmp_path)
    letter = {"内核核验": "通过"}
    engine.after_delivery(ts, "6-gate-post", letter)
    assert letter["内核核验"].startswith("通过：门禁端举证了 1 处候选缺陷")
    ts["gate_post"] = {"ran": True, "ok": False}
    assert "战后门禁" in kh.guard(ts, meta("开工", "jev-judge", "T001-6j-jev"))
    assert "战后门禁" in kh.guard(ts, meta("开工", "audit-sonnet", "T001-7-audit-post"))
    assert "- 战后门禁：未通过" in kh.stage_status_table(hub, ts)
    letter = {"内核核验": "通过"}
    engine.after_delivery(ts, "6-gate-post", letter)
    assert letter == {"内核核验": "通过"}
    gate = kh.turn_prompt(hub, ts, "gate-sonnet", "T001-6-gate-post", [], tmp_path)
    assert "candidate_defects" in gate and "不许用 xfail、skip 标掉" in gate
    assert "xfail" in kh.role_prompt("gate-sonnet") and "候选缺陷" in kh.role_prompt("audit-sonnet")


def test_runner_exits_between_steps_once_the_kernel_changes(tmp_path, monkeypatch):
    # 第 9 轮：模板每回合现读、代码还是启动时那一份；落地新一轮改动之后，跑着的 hub 要在两步之间退出
    import argparse
    templates = tmp_path / "hub"
    templates.mkdir()
    (templates / "worker.md").write_text("旧模板", encoding="utf-8")
    code = tmp_path / "kit_hub.py"
    code.write_text("# 旧内核", encoding="utf-8")
    first = kh.code_fingerprint(code, templates)
    assert kh.code_fingerprint(code, templates) == first
    (templates / "worker.md").write_text("新模板", encoding="utf-8")
    second = kh.code_fingerprint(code, templates)
    code.write_text("# 新内核", encoding="utf-8")
    assert len({first, second, kh.code_fingerprint(code, templates)}) == 3
    assert kh.code_fingerprint() == kh.code_fingerprint(Path(kh.__file__), kh.TEMPLATE_DIR)
    repo, _head = git_repo(tmp_path)
    seen = iter(["a", "a", "a", "b", "b"])
    monkeypatch.setattr(kh, "code_fingerprint", lambda *args: next(seen))
    steps = []
    monkeypatch.setattr(kh.Engine, "step", lambda self: steps.append(1) or True)
    assert kh.cmd_run(argparse.Namespace(repo=str(repo), max_steps=10, idle_exit=0.0, poll=0.0)) == kh.EXIT_OK
    assert len(steps) == 2  # 启动时 a；第 1、2 步之前还是 a；第 3 步之前变成 b，退出
    events = [json.loads(line)["event"] for line in kh.Hub(repo).ledger().read_text(encoding="utf-8").splitlines()]
    assert [e for e in events if e.startswith("runner.")] == ["runner.started", "runner.code_changed", "runner.stopped"]


def test_tail_file_reads_only_the_end(tmp_path):
    path = tmp_path / "big.log"
    path.write_bytes(b"".join(b"line %d\n" % i for i in range(400000)))  # 约 5 MiB
    import tracemalloc
    tracemalloc.start()
    try:
        assert kh.tail_file(path, 2, limit=4096) == "line 399998\nline 399999"
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 512 * 1024, peak  # 只读了末尾，没有整份读进内存


def test_review_history_survives_rework_and_seals_the_next_round(tmp_path, monkeypatch):
    hub = kh.Hub(tmp_path)
    hub.ensure()
    ts = locked(make_ts())
    engine = kh.Engine(hub, FakeRunner([]))
    engine.after_delivery(ts, "7-audit-post", {"结论": "返工", "退回": "执行端", "阻塞项": "1. 空的 except 吞掉了错误"})
    ts["gate_post"] = {"ok": True, "equivalent": ["等价改写：同一个字"]}
    kh.invalidate_after(ts, "5-exec")  # 执行端重跑：终审的记录清空，历史留着
    assert ts["audit_post"] == {} and ts["audit_history"][-1]["blockers"] == "1. 空的 except 吞掉了错误"
    ts["gate_post"] = {"ok": True, "equivalent": ["等价改写：同一个字"],
                       "mutate_record": ".agent/mailbox/tasks/T001-6-gate-post/evidence/mutate-1/mutations.json"}
    prompt = kh.turn_prompt(hub, ts, "audit-sonnet", "T001-7-audit-post", [], tmp_path)
    assert "复审封板" in prompt and "空的 except 吞掉了错误" in prompt and "等价改写：同一个字" in prompt
    assert "evidence/mutate-1/mutations.json" in prompt.replace("\\", "/")
    first = kh.turn_prompt(hub, ts, "audit-sonnet", "T001-4-audit-pre", [], tmp_path)
    assert "复审封板" not in first and "等价改写" not in first  # 只给同一阶段的上一轮
    engine.after_delivery(ts, "7-audit-post", {"结论": "通过"})
    assert "复审封板" not in kh.turn_prompt(hub, ts, "audit-sonnet", "T001-7-audit-post", [], tmp_path)


def test_rewritten_reports_and_briefs_keep_their_previous_versions(tmp_path):
    path = tmp_path / "report.md"
    for text in ("第一轮", "第二轮", "第三轮"):
        kh.keep_previous(path)
        path.write_text(text, encoding="utf-8")
    assert [p.read_text(encoding="utf-8") for p in (tmp_path / "report.1.md", tmp_path / "report.2.md", path)] == [
        "第一轮", "第二轮", "第三轮"]


def test_jev_report_flags_answers_by_the_battery_thresholds():
    thresholds = {"review": 0.35, "action": 0.70, "severity_action": 2.0}
    noul = {"type": "noul", "criteria": {"true": "某条 DoD 没有机械证据", "false": "都有"}}
    assert kh.jev_flag({"type": "noul", "noul": 0.12}, noul, thresholds) == ""
    review = kh.jev_flag({"type": "noul", "noul": 0.41}, noul, thresholds)
    assert "【留意】" in review and "某条 DoD 没有机械证据" in review
    assert "【需关注】" in kh.jev_flag({"type": "noul", "noul": 0.70}, noul, thresholds)
    score = {"type": "score", "criteria": ["低", "中", "高", "严重"]}
    assert kh.jev_flag({"type": "score", "score": 1.0, "levels": 4}, score, thresholds) == ""
    assert "判据：高" in kh.jev_flag({"type": "score", "score": 2.0, "levels": 4}, score, thresholds)


def test_execution_jev_gets_the_objective_fingerprint(tmp_path, monkeypatch):
    from codekit import decisions
    seen = {}

    class FakeSession:
        def __init__(self, settings, path):
            pass

        def ask(self, battery, state, context=None):
            seen["state"] = state
            return {"status": "ok", "answers": {"scope_creep": {"type": "noul", "noul": 0.8}}}

    battery = {"id": "report-screen", "version": "1.0.0", "labels": {"scope_creep": "超出范围"},
               "questions": {"scope_creep": {"type": "noul", "criteria": {"true": "改了范围外的文件"}}},
               "thresholds": {"review": 0.35, "action": 0.7}}
    monkeypatch.setattr(decisions, "Session", FakeSession)
    monkeypatch.setattr(decisions, "load_locked_batteries", lambda path: {"report-screen": battery})
    hub = kh.Hub(tmp_path)
    hub.ensure()
    run_dir = tmp_path / "attempt-001"
    run_dir.mkdir()
    (run_dir / "scope.json").write_text(json.dumps({"files": [{"path": "docs/a.md", "status": "M"}]}), encoding="utf-8")
    (run_dir / "observations.json").write_text(json.dumps({"review_hints": {"assertion_lines_removed": 3}}),
                                               encoding="utf-8")
    ts = locked(make_ts())
    ts["exec"] = {"run_dir": str(run_dir), "check_exit": 0, "scope_violations": 0}
    ts["gate_post"] = {"whitebox_exit": 0, "mutation_counts": {"caught": 2}}
    fields = kh.run_jev(hub, ts, "6j-jev")
    observed = seen["state"]["observations"]
    assert observed["changed_files"] == ["docs/a.md"] and observed["review_hints"]["assertion_lines_removed"] == 3
    assert observed["mutation_counts"] == {"caught": 2}
    report = (hub.task_dir("T001-6j-jev") / "report.md").read_text(encoding="utf-8")
    assert "超出范围" in report and "【需关注】" in report and "改了范围外的文件" in report
    assert "【需关注】" in fields["摘要"]


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


def test_refused_calls_outside_the_allowlist_only_warn():
    # T001 的终审：模型发了一次 Bash，CLI 当场拒绝，内核却把 16 分钟的回合整个作废
    use = assistant({"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "git log"}})

    def result_of(is_error: bool, text: str) -> dict:
        return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1",
                                                         "is_error": is_error, "content": text}]}}

    refused = kh.audit_claude_stream(stream(INIT, use, result_of(True, "<tool_use_error>Error: No such tool "
                                                                        "available: Bash.</tool_use_error>"),
                                            {"type": "result", "result": "ok"}), SPEC)
    assert refused["violations"] == [] and refused["warnings"] and "Bash" in refused["warnings"][0]
    for is_error, text in ((False, "abc123 commit"), (True, "Permission denied")):  # 执行了，或者是别的错
        audit = kh.audit_claude_stream(stream(INIT, use, result_of(is_error, text)), SPEC)
        assert any("Bash" in v for v in audit["violations"]) and audit["warnings"] == []
    assert any("Bash" in v for v in kh.audit_claude_stream(stream(INIT, use), SPEC)["violations"])  # 看不到结果
    advisor = assistant({"type": "server_tool_use", "id": "t1", "name": "advisor"})  # 服务端工具没有豁免
    audit = kh.audit_claude_stream(stream(INIT, advisor, result_of(True, "No such tool available: advisor")), SPEC)
    assert any("advisor" in v for v in audit["violations"]) and audit["warnings"] == []


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


API_ERROR = {"type": "assistant", "error": "oauth_org_not_allowed", "is_api_error_message": True,
             "api_error_status": 403, "api_error_code": "oauth_not_allowed_for_organization",
             "message": {"model": "<synthetic>", "content": [{"type": "text", "text": "Your organization has disabled"}]}}


def test_audits_name_model_api_errors_instead_of_blaming_the_output():
    # 2026-10-19 旧机器上的真实形状：claude 把 403 合成为一条 <synthetic> 消息，内核却报成“没有 json 代码块”
    failed = kh.audit_claude_stream(stream(INIT, API_ERROR, {"type": "result", "result": "x",
                                                             "terminal_reason": "api_error"}), SPEC)
    assert failed["violations"] == []
    assert "403" in failed["api_error"] and "oauth_not_allowed_for_organization" in failed["api_error"]
    recovered = kh.audit_claude_stream(stream(INIT, API_ERROR, assistant({"type": "text", "text": "ok"}),
                                              {"type": "result", "result": "ok"}), SPEC)
    assert recovered["api_error"] is None
    terminal = kh.audit_claude_stream(stream(INIT, {"type": "result", "result": "boom",
                                                    "terminal_reason": "api_error"}), SPEC)
    assert "api_error" in terminal["api_error"]
    spec = {"tools": ["read"], "provider": "p", "model": "m"}

    def pi_end(stop: str, error: str = "") -> dict:
        return {"type": "message_end", "message": {"role": "assistant", "provider": "p", "model": "m",
                                                   "stopReason": stop, "errorMessage": error, "content": []}}

    assert kh.audit_pi_stream(stream(pi_end("error", "429 rate limited")), spec)["api_error"] == "429 rate limited"
    assert kh.audit_pi_stream(stream(pi_end("error", "429"), pi_end("stop")), spec)["api_error"] is None


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
        executor={"provider": "other", "model": "step-5-preview", "thinking": "high"},
        authorization={"integration": ["local_branch", "merge"]})
    (plans / "t001-doc.v1.json").write_text(json.dumps(contract), encoding="utf-8")
    assert any("执行模型" in p for p in kh.contract_requirements(hub, ts))  # provider 要与名册一致
    contract["executor"] = {key: kh.ROSTER["exec-step"][key] for key in ("provider", "model", "thinking")}
    (plans / "t001-doc.v1.json").write_text(json.dumps(contract), encoding="utf-8")
    assert kh.contract_requirements(hub, ts) == []
    assert kh.CONTRACT_EXECUTOR_LINE == "- executor: %s/step-5-preview · thinking high" % contract["executor"]["provider"]
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
        output, violations, *rest = self.outputs.pop(0)
        api_error = rest[0] if rest else None
        return {"turn_id": "t%d" % len(self.calls), "turn_dir": "turns/x", "output": output,
                "violations": violations, "api_error": api_error,
                "output_error": None if output is not None else ("接口报错" if api_error else "没有代码块")}


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


def planner_delivery(facts: list = None) -> dict:
    return {"letter": {"type": "交付", "in_reply_to": "m", "摘要": "拆成 3 步", "提交": "无", "验证": "读了文档",
                       "偏离": "无", "需协调人决定": "无", "证据": "report.md"},
            "report": "# 概要步骤\n1. …", "state": "2026-10-19T00:00Z 交付", "external_facts": facts or []}


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


FONT_FACT = {"fact": "@fontpkg/sarasa-mono-sc@0.36.0 里有完整的 Regular、SemiBold woff2", "source": "handoff.md",
             "verified": "未核实"}
REACT_FACT = {"fact": "react@18.3.1 的许可是 MIT", "source": "npm", "verified": "npm view react@18.3.1 license → MIT"}


@pytest.mark.parametrize("facts, problem", [
    (None, "输出里没有 external_facts"),
    ("无", "输出里没有 external_facts"),
    ([REACT_FACT, {"fact": "x", "verified": ""}], "第 2 条缺 fact 或 verified"),
    ([{"source": "y", "verified": "未核实"}], "第 1 条缺 fact 或 verified"),
    (["react 是 MIT"], "第 1 条缺 fact 或 verified"),
])
def test_plan_delivery_must_list_its_external_facts(engine_env, facts, problem):
    # T002：字体包没有交接文档说的 woff2，合同、门禁、一审都没法核实，执行端跑了 28 分钟才撞上（第 7 轮）
    hub = engine_env
    state = hub.load_state()
    state["tasks"]["T001"]["stages"]["1-plan"]["status"] = "assigned"
    hub.save_state(state)
    hub.deliver({"from": kh.COORDINATOR, "to": "planner-opus", "task-id": "T001-1-plan", "in-reply-to": "none",
                 "type": "开工"}, fields())
    output = planner_delivery()
    if facts is None:
        del output["external_facts"]
    else:
        output["external_facts"] = facts
    kh.Engine(hub, FakeRunner([(output, [])])).step()
    stage = hub.load_state()["tasks"]["T001"]["stages"]["1-plan"]
    assert stage["status"] == "failed" and problem in stage["note"]
    assert hub.unread(kh.OWNER) == []


def test_plan_with_only_verified_facts_goes_straight_to_the_contract(engine_env):
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([({"letters": [start_planner()]}, []), (planner_delivery([REACT_FACT]), [])])
    engine = kh.Engine(hub, runner)
    engine.step()
    engine.step()
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["stages"]["1-plan"]["status"] == "delivered"
    assert ts["external_facts"]["items"] == [REACT_FACT] and ts["external_facts"]["pending"] == []
    assert hub.unread(kh.OWNER) == []
    assert kh.guard(ts, meta("开工", "contract-glm", "T001-2-contract")) is None
    assert "待站主核实" not in kh.stage_status_table(hub, ts)


def test_unverified_external_facts_wait_for_the_owner(tmp_path, monkeypatch):
    import io
    repo, head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    ts = kh.new_task_state("T001", "doc", "改文档", head, True)
    ts["stages"]["1-plan"]["status"] = "assigned"
    hub.save_state({"tasks": {"T001": ts}})
    hub.deliver({"from": kh.COORDINATOR, "to": "planner-opus", "task-id": "T001-1-plan", "in-reply-to": "none",
                 "type": "开工"}, fields())
    monkeypatch.setattr(kh, "ensure_worktree", lambda hub, ts, kind, commit: tmp_path)
    monkeypatch.setattr(kh, "role_prompt", lambda agent: "角色")
    facts = [REACT_FACT, FONT_FACT, dict(FONT_FACT, fact="OFL 原文随包", verified="无法核实（要联网）")]
    kh.Engine(hub, FakeRunner([(planner_delivery(facts), [])])).step()
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["stages"]["1-plan"]["status"] == "delivered"  # 规划照常交付，只是合同端要等
    assert [p["fact"] for p in ts["external_facts"]["pending"]] == [FONT_FACT["fact"], "OFL 原文随包"]
    letters = [p.read_text(encoding="utf-8") for p in hub.unread(kh.OWNER)]
    assert len(letters) == 1 and "from: 内核" in letters[0] and "type: 提问" in letters[0]
    assert FONT_FACT["fact"] in letters[0] and "OFL 原文随包" in letters[0] and "react" not in letters[0]
    assert "--facts-checked" in letters[0]
    assert "send --facts-checked" in kh.guard(ts, meta("开工", "contract-glm", "T001-2-contract"))
    assert "2 条待站主核实" in kh.stage_status_table(hub, ts)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stdin", io.StringIO("字体包只有 TTF；OFL 原文从上游仓库取"))
    assert kh.main(["--repo", str(repo), "send", "T001", "--type", "停止", "--facts-checked"]) == kh.EXIT_USAGE
    monkeypatch.setattr(sys, "stdin", io.StringIO("字体包只有 TTF；OFL 原文从上游仓库取"))
    assert kh.main(["--repo", str(repo), "send", "T001", "--type", "回复", "--facts-checked"]) == kh.EXIT_OK
    ts = hub.load_state()["tasks"]["T001"]
    record = ts["external_facts"]
    assert record["pending"] == [] and len(record["checked"]) == 2 and record["checked_msg"]
    assert kh.guard(ts, meta("开工", "contract-glm", "T001-2-contract")) is None
    letter = hub.unread(kh.COORDINATOR)[-1].read_text(encoding="utf-8")
    assert "站主已核实" in letter and "字体包只有 TTF" in letter
    monkeypatch.setattr(sys, "stdin", io.StringIO("再来一次"))
    assert kh.main(["--repo", str(repo), "send", "T001", "--type", "回复", "--facts-checked"]) == kh.EXIT_USAGE
    # 合同端与一审看得到这张表与站主的核实；规划端的输出格式要求交出它
    for agent, task_id in (("contract-glm", "T001-2-contract"), ("audit-sonnet", "T001-4-audit-pre")):
        prompt = kh.turn_prompt(hub, ts, agent, task_id, [], tmp_path)
        assert "## 规划依赖的仓库外事实" in prompt and FONT_FACT["fact"] in prompt
        assert "站主已在 %s 的回复里核实" % record["checked_msg"] in prompt
    for agent, task_id in (("gate-sonnet", "T001-3-gate-pre"), ("audit-sonnet", "T001-7-audit-post")):
        assert "## 规划依赖的仓库外事实" not in kh.turn_prompt(hub, ts, agent, task_id, [], tmp_path)
    assert '"external_facts"' in kh.turn_prompt(hub, ts, "planner-opus", "T001-1-plan", [], tmp_path)


def test_plan_redelivery_replaces_the_external_facts(engine_env):
    hub = engine_env
    state = hub.load_state()
    ts = state["tasks"]["T001"]
    ts["external_facts"] = {"items": [FONT_FACT], "pending": [{"fact": FONT_FACT["fact"], "source": ""}]}
    ts["stages"]["1-plan"]["status"] = "failed"
    hub.save_state(state)
    hub.deliver({"from": kh.COORDINATOR, "to": "planner-opus", "task-id": "T001-1-plan", "in-reply-to": "none",
                 "type": "返工"}, fields())
    verified = dict(FONT_FACT, verified="npm view … files → 只有 10 个 ttf")
    kh.Engine(hub, FakeRunner([(planner_delivery([verified]), [])])).step()
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["external_facts"]["items"] == [verified] and ts["external_facts"]["pending"] == []
    assert kh.guard(ts, meta("开工", "contract-glm", "T001-2-contract")) is None


def test_legacy_task_without_external_facts_is_not_blocked():
    ts = make_ts()
    ts["stages"]["1-plan"]["status"] = "delivered"
    assert "external_facts" not in ts
    assert kh.guard(ts, meta("开工", "contract-glm", "T001-2-contract")) is None
    assert kh.external_facts_section(ts) == []


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


def test_model_api_errors_are_not_retried_and_go_to_the_owner(engine_env):
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([({"letters": [start_planner()]}, []),
                         (None, [], "403 oauth_not_allowed_for_organization：Your organization has disabled")])
    engine = kh.Engine(hub, runner)
    engine.step()
    engine.step()
    assert len(runner.calls) == 2  # 接口报错不重试
    state = hub.load_state()["tasks"]["T001"]
    assert state["stages"]["1-plan"]["status"] == "failed" and state["status"] == "blocked"
    assert hub.unread(kh.COORDINATOR) == []  # 协调人也会撞上同样的错：不唤醒它
    letters = [p.read_text(encoding="utf-8") for p in hub.unread(kh.OWNER)]
    assert len(letters) == 1 and "403" in letters[0]


def test_coordinator_api_error_is_not_retried(engine_env):
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([(None, [], "403 oauth_not_allowed_for_organization")])
    kh.Engine(hub, runner).step()
    assert len(runner.calls) == 1
    assert hub.load_state()["tasks"]["T001"]["status"] == "blocked"
    assert len(hub.unread(kh.OWNER)) == 1


def test_kernel_runs_jev_right_after_a_passing_delivery(engine_env, monkeypatch):
    hub = engine_env
    calls = []
    monkeypatch.setattr(kh, "run_jev", lambda hub, ts, suffix: calls.append(suffix) or fields(摘要="JEV：无异常"))
    engine = kh.Engine(hub, FakeRunner([]))
    state = hub.load_state()
    ts = state["tasks"]["T001"]
    for suffix in ("1-plan", "2-contract"):
        ts["stages"][suffix]["status"] = "delivered"
    engine.auto_jev(state, ts, "1-plan")  # 规划之后没有 JEV
    ts["jev_enabled"] = False
    engine.auto_jev(state, ts, "2-contract")
    assert calls == []
    ts["jev_enabled"] = True
    engine.auto_jev(state, ts, "2-contract")
    assert calls == ["3j-jev"] and hub.load_state()["tasks"]["T001"]["stages"]["3j-jev"]["status"] == "delivered"
    letters = [p.read_text(encoding="utf-8") for p in hub.unread(kh.COORDINATOR)]
    assert len(letters) == 1 and "from: jev-judge" in letters[0] and "task-id: T001-3j-jev" in letters[0]
    ts["gate_post"] = {"ran": True, "ok": False}  # 战后门禁没过：短路，不跑 JEV
    engine.auto_jev(state, ts, "6-gate-post")
    ts["gate_post"]["ok"] = True
    engine.auto_jev(state, ts, "6-gate-post")
    assert calls == ["3j-jev", "6j-jev"]


def test_worker_delivery_hands_over_to_the_kernel_jev_only_when_it_passes(engine_env, monkeypatch):
    hub = engine_env
    seen = []
    monkeypatch.setattr(kh.Engine, "auto_jev", lambda self, state, ts, suffix: seen.append(suffix))
    owner_task(hub)
    empty = dict(planner_delivery(), report=" ")  # 内核核验不过：规划报告为空
    engine = kh.Engine(hub, FakeRunner([({"letters": [start_planner()]}, []), (empty, [])]))
    engine.step()
    engine.step()
    assert seen == []
    hub.take(hub.unread(kh.COORDINATOR)[0])
    hub.deliver({"from": kh.COORDINATOR, "to": "planner-opus", "task-id": "T001-1-plan", "in-reply-to": "none",
                 "type": "返工"}, fields())
    kh.Engine(hub, FakeRunner([(planner_delivery(), [])])).step()
    assert seen == ["1-plan"]


def attempt_dir(hub, state: dict, violations: int = 0):
    run_dir = hub.repo / ".agent" / "runs" / "t001-doc" / "attempt-002"
    run_dir.mkdir(parents=True)
    (run_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (run_dir / "scope.json").write_text(json.dumps({"violations": ["x"] * violations, "files": []}), encoding="utf-8")
    (run_dir / "executor-report.json").write_text(json.dumps({"executor_status": "completed", "dod": []}),
                                                  encoding="utf-8")
    return run_dir


def test_exec_verdict_reads_the_attempt_state_key(engine_env, monkeypatch):
    hub = engine_env
    check = {"code": 0}
    monkeypatch.setattr(kh, "run_pd", lambda hub, args, timeout=600: (check["code"], "check 输出"))
    ts = make_ts()
    # 调度器把状态写在 "state" 键（pi_dispatch.get_state）；T001 时读成了 "status"，执行阶段永远判不过
    run_dir = attempt_dir(hub, {"state": "NEEDS_REVIEW"})
    kh.finish_exec(hub, ts, run_dir, 0)
    assert ts["exec"]["status"] == "NEEDS_REVIEW" and ts["exec"]["check_ok"] is True
    (run_dir / "state.json").write_text(json.dumps({"status": "NEEDS_REVIEW"}), encoding="utf-8")
    kh.finish_exec(hub, ts, run_dir, 0)
    assert ts["exec"]["check_ok"] is False
    (run_dir / "state.json").write_text(json.dumps({"state": "BUDGET_EXCEEDED"}), encoding="utf-8")
    assert kh.finish_exec(hub, ts, run_dir, 0) and ts["exec"]["check_ok"] is False
    (run_dir / "state.json").write_text(json.dumps({"state": "NEEDS_REVIEW"}), encoding="utf-8")
    check["code"] = 1
    kh.finish_exec(hub, ts, run_dir, 0)
    assert ts["exec"]["check_ok"] is False


def test_exec_recheck_revisits_the_last_attempt_without_rerunning(engine_env, monkeypatch):
    hub = engine_env
    monkeypatch.setattr(kh, "run_pd", lambda hub, args, timeout=600: (0, "ok") if args[0] == "check" else (9, "不该跑"))
    run_dir = attempt_dir(hub, {"state": "NEEDS_REVIEW"})
    state = hub.load_state()
    ts = locked(state["tasks"]["T001"])
    ts["exec"] = {"run_dir": str(run_dir), "run_exit": 0, "check_ok": False, "status": None}
    hub.save_state(state)
    engine = kh.Engine(hub, FakeRunner([]))
    with pytest.raises(kh.HubError):  # 执行阶段没判失败：不能重新核验
        engine.recheck_exec("T001")
    ts["stages"]["5-exec"]["status"] = "failed"
    hub.save_state(state)
    result = engine.recheck_exec("T001")
    assert result["check_ok"] is True
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["stages"]["5-exec"]["status"] == "delivered" and ts["exec"]["check_ok"] is True
    letters = [p.read_text(encoding="utf-8") for p in hub.unread(kh.COORDINATOR)]
    assert len(letters) == 1 and "from: exec-step" in letters[0] and "exec-recheck" in letters[0]
    assert "内核核验: 通过" in letters[0]
    assert kh.guard(ts, meta("开工", "gate-sonnet", "T001-6-gate-post")) is None  # 可以接着开工战后门禁


def test_finalize_lands_the_oracle_commit_first_and_can_be_retried(tmp_path, monkeypatch):
    import subprocess
    repo, head = git_repo(tmp_path)
    branch = kh.git(["rev-parse", "--abbrev-ref", "HEAD"], repo).strip()
    (repo / "tests").mkdir()
    (repo / "tests" / "test_gate_t001_baseline.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    kh.git(["checkout", "-q", "-b", "oracle"], repo)
    kh.git(["add", "tests/test_gate_t001_baseline.py"], repo)
    kh.git(["commit", "-q", "-m", "门禁端基准测试"], repo)
    oracle = kh.git(["rev-parse", "HEAD"], repo).strip()
    kh.git(["checkout", "-q", branch], repo)
    calls = []

    def fake_pd(hub, args, timeout=600):
        on_branch = subprocess.run(["git", "merge-base", "--is-ancestor", oracle, "HEAD"], cwd=str(repo)).returncode == 0
        calls.append((args[0], on_branch))
        if args[0] == "verdict":
            (run_dir / "state.json").write_text(json.dumps({"state": "PASS"}), encoding="utf-8")
        return 0, "ok"

    monkeypatch.setattr(kh, "run_pd", fake_pd)
    hub = kh.Hub(repo)
    hub.ensure()
    run_dir = attempt_dir(hub, {"state": "NEEDS_REVIEW"})
    ts = locked(kh.new_task_state("T001", "doc", "改文档", head, True))
    ts["oracle"].update(sha=oracle, files=["tests/test_gate_t001_baseline.py"])
    ts["exec"] = {"run_dir": str(run_dir), "check_exit": 0, "scope_violations": 0}
    ok, _detail = kh.finalize(hub, ts)
    # 先记结论，再把基准测试提交 ff 到当前分支，然后 integrate：integrate 看到的末端上已经有基准测试
    assert ok and calls == [("verdict", False), ("integrate", True)]
    assert kh.git(["rev-parse", "HEAD"], repo).strip() == oracle and ts["oracle"]["landed_at"]
    calls.clear()
    assert kh.finalize(hub, ts)[0] and calls == [("integrate", True)]  # 重试：attempt 已是 PASS，不再记结论
    # 任务进行期间分支前进了（分叉）：不能 ff，就把基准测试提交挑到末端，再 integrate
    kh.git(["reset", "-q", "--hard", head], repo)
    (repo / "README.md").write_text("分叉\n", encoding="utf-8")
    kh.git(["commit", "-q", "-am", "分叉"], repo)
    (repo / "notes.txt").write_text("主工作区里无关的未提交文件\n", encoding="utf-8")
    calls.clear()
    ok, _detail = kh.finalize(hub, ts)
    assert ok and [c[0] for c in calls] == ["integrate"] and ts["oracle"]["landed_by"] == "cherry-pick"
    tip = kh.git(["rev-parse", "HEAD"], repo).strip()
    assert (repo / "tests" / "test_gate_t001_baseline.py").read_text(encoding="utf-8") == "def test_x():\n    pass\n"
    assert "cherry picked from commit %s" % oracle in kh.git(["log", "-1", "--format=%B"], repo)
    calls.clear()
    assert kh.finalize(hub, ts)[0] and kh.git(["rev-parse", "HEAD"], repo).strip() == tip  # 重试：不再挑一次
    # 末端上已有内容不同的同名文件：挑入冲突，中止并如实报告，不留半截状态，也不 integrate
    kh.git(["reset", "-q", "--hard", "HEAD~1"], repo)
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "test_gate_t001_baseline.py").write_text("def test_y():\n    pass\n", encoding="utf-8")
    kh.git(["add", "tests"], repo)
    kh.git(["commit", "-q", "-m", "同名不同内容"], repo)
    calls.clear()
    ok, detail = kh.finalize(hub, ts)
    assert not ok and "不能干净地挑" in detail and calls == []
    assert not (repo / ".git" / "CHERRY_PICK_HEAD").exists()
    assert kh.git(["status", "--porcelain", "--", "tests"], repo).strip() == ""


def rework_setup(tmp_path, attempts=3):
    repo, head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    ts = locked(kh.new_task_state("T001", "doc", "改文档", head, True))
    plans = repo / ".agent" / "plans"
    plans.mkdir(parents=True)
    (plans / "t001-doc.v1.md").write_text("# TASK: t001-doc\n- plan_version: 1\n- base_sha: %s\n\n## Forbidden\n- 无\n"
                                          % ("o" * 40), encoding="utf-8")
    (plans / "t001-doc.v1.json").write_text(json.dumps({"budget": {
        "max_attempts_total": attempts, "max_wall_seconds_per_attempt": 3600, "max_wall_seconds_total": 10800}}),
        encoding="utf-8")
    ts["contract"] = {"key": "t001-doc.v1", "version": 1, "dispatched": True}
    previous = repo / ".agent" / "runs" / "t001-doc" / "attempt-001"
    (previous / "claim").mkdir(parents=True)
    (previous / "candidate.patch").write_text("diff --git a/x b/x\n", encoding="utf-8")
    (previous / "state.json").write_text(json.dumps({"state": "NEEDS_REVIEW"}), encoding="utf-8")
    ts["exec"] = {"run_dir": str(previous), "check_ok": True}
    ts["audit_post"] = {"verdict": "返工", "target": "执行端"}
    ts["audit_history"] = [{"stage": "7-audit-post", "verdict": "返工", "target": "执行端",
                            "blockers": "B1 StatusTag 遇到 constructor 崩溃"}]
    return repo, hub, ts, plans, previous


def test_exec_rework_continues_from_the_reviewed_candidate(tmp_path, monkeypatch):
    # T002：attempt-003 照同一份合同从头重写，终审的阻塞项一条没改，用掉了最后一次预算（第 10 轮）
    repo, hub, ts, plans, previous = rework_setup(tmp_path)
    rework = "a" * 40
    calls = []

    def fake_pd(hub, args, timeout=600):
        calls.append(args[0] if args[0] != "prepare" else "prepare " + args[1])
        if args[0] == "verdict":
            assert args[args.index("--verdict") + 1] == "REVISE" and "--class" in args
            review = Path(args[args.index("--review") + 1]).read_text(encoding="utf-8")
            assert review.rstrip().endswith("Verdict: REVISE")
            (previous / "state.json").write_text(json.dumps({"state": "REVISE"}), encoding="utf-8")
        if args[0] == "branch":
            assert args[1:] == [str(previous), "--rework"]
            return 0, "已创建本地分支 pi-rework/x → %s（未推送）。\ncommit=%s branch=pi-rework/x" % (rework, rework)
        if args[0] == "prepare":
            return 9, "prepare 停在这里"
        return 0, "ok"

    monkeypatch.setattr(kh, "run_pd", fake_pd)
    monkeypatch.setattr(kh, "contract_requirements", lambda hub, ts: [])
    fields = kh.run_exec(hub, ts)
    assert calls == ["verdict", "branch", "derive-json", "validate", "prepare t001-doc.v2"]
    v2 = (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    assert "- plan_version: 2" in v2 and "- base_sha: %s" % rework in v2
    assert "## Rework（返工第 1 轮，内核追加）" in v2 and "attempt-001 的候选" in v2
    assert v2.rstrip().endswith("B1 StatusTag 遇到 constructor 崩溃")
    assert ts["contract"]["key"] == "t001-doc.v2" and ts["rework_chain"][0]["commit"] == rework
    assert "prepare 停在这里" in fields["验证"]
    assert "attempt-001 的候选 → 返工提交 aaaaaaaaaa（t001-doc.v2）" in kh.stage_status_table(hub, ts)
    # 已经是 REVISE（重试）就不再记一次结论；不是终审退回执行端的返工（例如检查没过），照原合同重派
    ts["exec"], ts["audit_post"] = {"run_dir": str(previous)}, {"verdict": "返工", "target": "执行端"}
    calls.clear()
    (plans / "t001-doc.v2.json").write_text((plans / "t001-doc.v1.json").read_text(encoding="utf-8"),
                                            encoding="utf-8")
    kh.run_exec(hub, ts)
    assert calls == ["branch", "derive-json", "validate", "prepare t001-doc.v3"] and len(ts["rework_chain"]) == 2
    assert "## Rework（返工第 2 轮，内核追加）" in (plans / "t001-doc.v3.md").read_text(encoding="utf-8")
    calls.clear()
    ts["exec"], ts["audit_post"] = {"run_dir": str(previous)}, {}
    kh.run_exec(hub, ts)
    assert calls == ["prepare t001-doc.v3"]
    calls.clear()
    ts["exec"], ts["audit_post"] = {"run_dir": str(previous)}, {"verdict": "返工", "target": "战后门禁"}
    kh.run_exec(hub, ts)
    assert calls == ["prepare t001-doc.v3"]
    # 上一轮没有候选补丁：没有可接着改的东西，照原合同重派
    (previous / "candidate.patch").write_text("", encoding="utf-8")
    calls.clear()
    ts["exec"], ts["audit_post"] = {"run_dir": str(previous)}, {"verdict": "返工", "target": "执行端"}
    kh.run_exec(hub, ts)
    assert calls == ["prepare t001-doc.v3"]


def test_exec_rework_reports_when_the_rework_base_cannot_be_built(tmp_path, monkeypatch):
    repo, hub, ts, plans, previous = rework_setup(tmp_path)
    answers = {"verdict": (1, "复审记录不合格")}
    calls = []
    monkeypatch.setattr(kh, "run_pd", lambda hub, args, timeout=600: calls.append(args[0]) or answers.get(args[0], (0, "ok")))
    fields = kh.run_exec(hub, ts)
    assert calls == ["verdict"] and "verdict REVISE 被调度器拒绝" in fields["验证"] and "复审记录不合格" in fields["验证"]
    assert ts["exec"]["run_dir"] is None and not (plans / "t001-doc.v2.md").exists()
    answers["verdict"] = (0, "ok")
    calls.clear()
    ts["exec"] = {"run_dir": str(previous)}
    fields = kh.run_exec(hub, ts)
    assert calls == ["verdict", "branch"] and "branch --rework 没有建出返工提交" in fields["验证"]
    assert not (plans / "t001-doc.v2.md").exists() and "rework_chain" not in ts


def test_exec_rework_stops_at_the_budget(tmp_path, monkeypatch):
    repo, hub, ts, plans, previous = rework_setup(tmp_path, attempts=1)
    calls = []
    monkeypatch.setattr(kh, "run_pd", lambda hub, args, timeout=600: calls.append(args[0]) or (0, "ok"))
    fields = kh.run_exec(hub, ts)
    assert calls == [] and "预算用完" in fields["验证"] and ts["exec"]["attempts_left"] == 0  # 没有任何副作用
    assert not (plans / "t001-doc.v2.md").exists() and "rework_chain" not in ts
    ts["stages"]["5-exec"]["status"] = "failed"
    assert "attempt 已经用完" in kh.guard(ts, meta("返工", "exec-step", "T001-5-exec"))
    assert "attempt 已经用完" in kh.stage_status_table(hub, ts)
    ts["owner_rework"] = {"suffix": "5-exec"}  # 站主拍板照样放行（例如刚出了追加预算的新版本）
    assert kh.guard(ts, meta("返工", "exec-step", "T001-5-exec")) is None
    assert kh.attempts_left(hub, ts) == 0
    (plans / "t001-doc.v1.json").write_text("不是 JSON", encoding="utf-8")
    assert kh.attempts_left(hub, ts) is None
    # 每个 attempt 收尾时记下还剩几次
    run_dir = attempt_dir(hub, {"state": "NEEDS_REVIEW"})
    (plans / "t001-doc.v1.json").write_text(json.dumps({"budget": {"max_attempts_total": 4}}), encoding="utf-8")
    kh.finish_exec(hub, ts, run_dir, 0)
    assert ts["exec"]["attempts_left"] == 3


def test_post_gate_worktree_starts_from_the_attempt_base(tmp_path, monkeypatch):
    repo, head, hub, ts, _plans, _calls = gate_setup(tmp_path, monkeypatch)
    branch = kh.git(["rev-parse", "--abbrev-ref", "HEAD"], repo).strip()
    kh.git(["checkout", "-q", "-b", "rework"], repo)
    (repo / "earlier.txt").write_text("上一轮的候选\n", encoding="utf-8")
    kh.git(["add", "earlier.txt"], repo)
    kh.git(["commit", "-q", "-m", "返工提交"], repo)
    rework = kh.git(["rev-parse", "HEAD"], repo).strip()
    kh.git(["checkout", "-q", branch], repo)
    run_dir = tmp_path / "attempt-002"
    run_dir.mkdir()
    (run_dir / "meta.json").write_text(json.dumps({"base_sha": rework}), encoding="utf-8")
    ts["exec"] = {"run_dir": str(run_dir)}
    ts["oracle"]["sha"] = head
    workspace = kh.apply_candidate(hub, ts)
    assert kh.git(["rev-parse", "HEAD"], workspace).strip() == rework and (workspace / "earlier.txt").is_file()
    assert kh.attempt_base(ts, tmp_path / "no-meta") == head
    kh.git(["worktree", "remove", "--force", str(workspace)], repo)


def test_finalize_lands_the_rework_chain_before_integrating(tmp_path, monkeypatch):
    import subprocess
    repo, head = git_repo(tmp_path)
    branch = kh.git(["rev-parse", "--abbrev-ref", "HEAD"], repo).strip()
    kh.git(["checkout", "-q", "-b", "chain"], repo)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_gate_t001_baseline.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    kh.git(["add", "tests"], repo)
    kh.git(["commit", "-q", "-m", "门禁端基准测试"], repo)
    oracle = kh.git(["rev-parse", "HEAD"], repo).strip()
    (repo / "earlier.txt").write_text("上一轮的候选\n", encoding="utf-8")
    kh.git(["add", "earlier.txt"], repo)
    kh.git(["commit", "-q", "-m", "返工提交"], repo)
    rework = kh.git(["rev-parse", "HEAD"], repo).strip()
    kh.git(["checkout", "-q", branch], repo)
    calls = []

    def fake_pd(hub, args, timeout=600):
        has_chain = subprocess.run(["git", "merge-base", "--is-ancestor", rework, "HEAD"], cwd=str(repo)).returncode == 0
        calls.append((args[0], has_chain or (repo / "earlier.txt").is_file()))
        if args[0] == "verdict":
            (run_dir / "state.json").write_text(json.dumps({"state": "PASS"}), encoding="utf-8")
        return 0, "ok"

    monkeypatch.setattr(kh, "run_pd", fake_pd)
    hub = kh.Hub(repo)
    hub.ensure()
    run_dir = attempt_dir(hub, {"state": "NEEDS_REVIEW"})
    ts = locked(kh.new_task_state("T001", "doc", "改文档", head, True))
    ts["oracle"].update(sha=oracle, files=["tests/test_gate_t001_baseline.py"])
    ts["rework_chain"] = [{"from": "attempt-001", "commit": rework, "contract": "t001-doc.v2"}]
    ts["exec"] = {"run_dir": str(run_dir), "check_exit": 0, "scope_violations": 0}
    ok, _detail = kh.finalize(hub, ts)
    # integrate 只挑最后一轮“基线→候选”的改动：前几轮的返工提交要先在末端上
    assert ok and calls == [("verdict", False), ("integrate", True)]
    assert kh.git(["rev-parse", "HEAD"], repo).strip() == rework and ts["rework_chain"][0]["landed_by"] == "ff"
    calls.clear()
    assert kh.finalize(hub, ts)[0] and calls == [("integrate", True)]
    # 任务进行期间分支前进了：基准测试与返工提交依次挑到末端
    kh.git(["reset", "-q", "--hard", head], repo)
    (repo / "README.md").write_text("分叉\n", encoding="utf-8")
    kh.git(["commit", "-q", "-am", "分叉"], repo)
    for key in ("landed_at", "landed_by"):
        ts["oracle"].pop(key, None)
        ts["rework_chain"][0].pop(key, None)
    calls.clear()
    ok, _detail = kh.finalize(hub, ts)
    assert ok and calls == [("integrate", True)] and ts["rework_chain"][0]["landed_by"] == "cherry-pick"
    assert "cherry picked from commit %s" % rework in kh.git(["log", "-1", "--format=%B"], repo)
    assert (repo / "earlier.txt").read_text(encoding="utf-8") == "上一轮的候选\n"
    tip = kh.git(["rev-parse", "HEAD"], repo).strip()
    assert kh.finalize(hub, ts)[0] and kh.git(["rev-parse", "HEAD"], repo).strip() == tip  # 重试：不再挑一次
    # 末端上同名文件内容不同：挑入冲突，中止并如实报告，不 integrate
    kh.git(["reset", "-q", "--hard", "HEAD~1"], repo)
    (repo / "earlier.txt").write_text("别的内容\n", encoding="utf-8")
    kh.git(["add", "earlier.txt"], repo)
    kh.git(["commit", "-q", "-m", "同名不同内容"], repo)
    ts["rework_chain"][0].pop("landed_at")
    calls.clear()
    ok, detail = kh.finalize(hub, ts)
    assert not ok and "返工提交 %s" % rework[:12] in detail and calls == []
    assert not (repo / ".git" / "CHERRY_PICK_HEAD").exists()


def test_owner_takeover_closes_the_task(tmp_path, monkeypatch):
    import io
    repo, head = git_repo(tmp_path)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    hub = kh.Hub(repo)
    hub.ensure()
    state = hub.load_state()
    state["tasks"]["T001"] = kh.new_task_state("T001", "doc", "改文档", head, True)
    hub.save_state(state)
    note = tmp_path / "close.md"
    parser = kh.build_parser()

    def close(ref):
        args = parser.parse_args(["--repo", str(repo), "task", "close", "T001", "--ref", ref, "--file", str(note)])
        return args.func(args)

    note.write_text("  \n", encoding="utf-8")
    with pytest.raises(kh.HubError):
        close("HEAD")  # 没写怎样接手
    note.write_text("预算用完，规划端在 attempt-002 的候选上补完 B1–B6，V01 75 passed。", encoding="utf-8")
    kh.git(["checkout", "-q", "-b", "side"], repo)
    (repo / "side.txt").write_text("不在分支上\n", encoding="utf-8")
    kh.git(["add", "side.txt"], repo)
    kh.git(["commit", "-q", "-m", "side"], repo)
    side = kh.git(["rev-parse", "HEAD"], repo).strip()
    kh.git(["checkout", "-q", "-"], repo)
    for ref in (side, "no-such-ref"):
        with pytest.raises(kh.HubError):
            close(ref)  # 接手的工作要已经落在当前分支上
    assert close("HEAD") == kh.EXIT_OK
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["status"] == "done" and ts["closed_by_owner"]["ref"] == head
    assert "V01 75 passed" in (repo / ts["closed_by_owner"]["note"]).read_text(encoding="utf-8")
    assert "站主接手结项：%s" % head[:12] in kh.stage_status_table(hub, ts)
    assert "已结项" in kh.guard(ts, meta("开工", "exec-step", "T001-5-exec"))
    with pytest.raises(kh.HubError):
        close("HEAD")  # 不能结项两次
    events = [json.loads(line)["event"] for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert "task.closed_by_owner" in events


def test_task_brief_must_not_reference_uncommitted_paths(tmp_path, monkeypatch):
    import io
    repo, _head = git_repo(tmp_path)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    (repo / ".gitignore").write_text(".agent/runs/\n", encoding="utf-8")
    kh.git(["add", ".gitignore"], repo)
    kh.git(["commit", "-q", "-m", "ignore runs"], repo)
    (repo / "docs" / "ui design").mkdir(parents=True)
    (repo / "docs" / "ui design" / "a.md").write_text("设计稿\n", encoding="utf-8")
    (repo / ".agent" / "runs").mkdir(parents=True)
    (repo / ".agent" / "runs" / "x.json").write_text("{}", encoding="utf-8")
    brief = tmp_path / "brief.md"

    def register(task: str, text: str) -> int:
        brief.write_text(text, encoding="utf-8")
        return kh.main(["--repo", str(repo), "task", "new", task, "--slug", "ui", "--title", "界面", "--brief", str(brief)])

    # T002：设计稿没入库，工人在任务基线的 worktree 里看不到
    assert register("T002", "照 `docs/ui design/` 实现") == kh.EXIT_USAGE
    assert register("T002", "照 `docs/ui design/a.md` 实现") == kh.EXIT_USAGE
    kh.git(["add", "docs"], repo)
    kh.git(["commit", "-q", "-m", "设计稿"], repo)
    (repo / "docs" / "ui design" / "a.md").write_text("改了没提交\n", encoding="utf-8")
    assert register("T002", "照 `docs/ui design/a.md` 实现") == kh.EXIT_USAGE
    kh.git(["checkout", "--", "docs"], repo)
    text = "照 `docs/ui design/a.md` 实现；证据看 `.agent/runs/x.json`；新文件写到 `desktop/web/`；`npm ci`"
    assert register("T002", text) == kh.EXIT_OK  # 已提交、被忽略、还不存在的路径都不拦
    assert "T002" in kh.Hub(repo).load_state()["tasks"]


def test_coordinator_runs_at_high_effort():
    # 用户 2026-10-19 同意：协调人从 max 降到 high（T001 里每回合 1–4.5 分钟，大头是思考输出）
    assert kh.ROSTER[kh.COORDINATOR]["effort"] == "high"


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
    # 返工交付覆盖 report.md 之前，上一轮的报告留档
    directory = hub.task_dir("T001-1-plan")
    assert (directory / "report.1.md").is_file() and (directory / "report.md").is_file()


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


def test_claude_workers_read_the_main_repo_and_write_only_their_worktree(tmp_path):
    hub = kh.Hub(tmp_path)
    hub.ensure()
    seen = []

    def launcher(cmd, cwd, env, out, err, timeout):
        seen.append(cmd)
        return {"exit_code": 0, "timed_out": False, "wall_seconds": 1.0}

    runner = kh.TurnRunner(hub, launcher=launcher)
    runner.run("gate-sonnet", "T001-3-gate-pre", tmp_path / "ws", "角色", "输入")
    runner.run("audit-sonnet", "T001-4-audit-pre", tmp_path / "ws", "角色", "输入")
    gate, audit = seen
    for cmd in (gate, audit):  # 合同、信箱与执行证据只在主工作区里
        assert cmd[cmd.index("--add-dir") + 1] == str(tmp_path)
    # 默认模式下没人答权限提示，工作目录里的写入也会被拒：门禁端要 acceptEdits，主工作区的写入另行拒绝
    assert gate[gate.index("--permission-mode") + 1] == "acceptEdits"
    rule = kh.claude_path_rule(tmp_path)
    assert gate[gate.index("--disallowedTools") + 1:gate.index("--permission-prompts")] == [
        "Edit(%s)" % rule, "Write(%s)" % rule]
    assert "--permission-mode" not in audit and "--disallowedTools" not in audit


def test_planner_may_only_run_npm_view(tmp_path):
    hub = kh.Hub(tmp_path)
    hub.ensure()
    seen = []

    def launcher(cmd, cwd, env, out, err, timeout):
        seen.append(cmd)
        return {"exit_code": 0, "timed_out": False, "wall_seconds": 1.0}

    kh.TurnRunner(hub, launcher=launcher).run("planner-opus", "T001-1-plan", tmp_path / "ws", "角色", "输入")
    cmd = seen[0]
    assert cmd[cmd.index("--tools") + 1] == "Read,Grep,Glob,Bash"
    assert cmd[cmd.index("--allowedTools") + 1:cmd.index("--add-dir")] == ["Bash(npm view:*)"]
    assert "--permission-mode" not in cmd and "--disallowedTools" not in cmd  # 没有写工具，别的 Bash 一律被拒
    role = kh.role_prompt("planner-opus")
    assert "npm view" in role and "external_facts" in role


def test_claude_path_rule_uses_the_absolute_form():
    if sys.platform == "win32":
        assert kh.claude_path_rule(Path("C:/Code/ThemisTally")) == "//c/Code/ThemisTally/**"
    else:
        assert kh.claude_path_rule(Path("/srv/repo")) == "//srv/repo/**"


def test_turn_with_api_error_says_so(tmp_path):
    hub = kh.Hub(tmp_path)
    hub.ensure()

    def launcher(cmd, cwd, env, out, err, timeout):
        events = [dict(INIT, tools=["Read", "Grep", "Glob"], model="claude-opus-5-5"), API_ERROR,
                  {"type": "result", "result": "Your organization has disabled", "terminal_reason": "api_error"}]
        out.write(("\n".join(json.dumps(e) for e in events) + "\n").encode("utf-8"))
        return {"exit_code": 1, "timed_out": False, "wall_seconds": 1.0}

    turn = kh.TurnRunner(hub, launcher=launcher).run("planner-opus", "T001-1-plan", tmp_path, "角色", "输入")
    assert turn["output"] is None and "403" in turn["api_error"]
    assert "接口报错" in turn["output_error"] and "json" not in turn["output_error"]
    record = json.loads(Path(turn["turn_dir"], "result.json").read_text(encoding="utf-8"))
    assert "403" in record["api_error"]


def test_cli_output_survives_a_non_utf8_console(monkeypatch):
    import io
    consoles = [io.TextIOWrapper(io.BytesIO(), encoding="cp1252") for _ in range(2)]
    monkeypatch.setattr(sys, "stdout", consoles[0])
    monkeypatch.setattr(sys, "stderr", consoles[1])
    with pytest.raises(SystemExit):
        kh.main(["--help"])
    consoles[0].flush()
    assert "七端信箱" in consoles[0].buffer.getvalue().decode("utf-8")


def test_owner_reply_piped_on_a_non_utf8_console_keeps_its_text(tmp_path, monkeypatch):
    import io
    repo, _head = git_repo(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO("环境已修好，恢复".encode("utf-8")), encoding="cp1252"))
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))
    assert kh.main(["--repo", str(repo), "send", "T009", "--type", "回复"]) == kh.EXIT_OK
    letters = [p.read_text(encoding="utf-8") for p in kh.Hub(repo).unread(kh.COORDINATOR)]
    assert len(letters) == 1 and "摘要: 环境已修好，恢复" in letters[0]


def test_worker_env_drops_the_decision_key_and_host_session_vars(monkeypatch):
    monkeypatch.setenv(kh.DECISIONS_KEY_ENV, "examplevalue")
    monkeypatch.setenv("CLAUDECODE", "1")
    env = kh.worker_env()
    assert kh.DECISIONS_KEY_ENV not in env and "CLAUDECODE" not in env
    assert kh.DECISIONS_KEY_ENV not in kh.kernel_env()
