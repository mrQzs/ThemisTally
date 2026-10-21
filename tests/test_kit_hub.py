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
import shutil
import sys
import time
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
    # 第 14 轮：一审第一次就退回规划端（例如仓库外事实没核实），此前被拒
    ts["audit_pre"].update(verdict="返工", target="规划端")
    assert kh.guard(ts, meta("返工", "planner-opus", "T001-1-plan")) is None
    ts["audit_pre"].update(verdict="返工", target="门禁端")
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
    ts["contract"] = {"key": "t001-doc.v1", "version": 1, "dispatched": True, "written_version": 1}
    assert kh.bump_contract_version(hub, ts) == []
    assert ts["contract"]["key"] == "t001-doc.v2" and "dispatched" not in ts["contract"]
    assert ts["contract"]["written_version"] == 1  # 升版不改内容：还是合同端写的那一版
    assert "- plan_version: 2" in (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    assert "- plan_version: 1" in (plans / "t001-doc.v1.md").read_text(encoding="utf-8")  # 已派遣的版本不动
    ts["contract"].update(key="t001-doc.v1", version=1)
    assert any("已存在" in p for p in kh.bump_contract_version(hub, ts))


def pd_with_baseline(calls, exit_code=1, summary="1 failed in 0.01s", timed_out=False):
    """假的 run_pd：记下调用；baseline 照调度器的样子写一份检查记录，门禁那条检查在基线上按给定的方式结束。"""
    def fake(hub, args, timeout=600):
        calls.append(list(args))
        if args[0] != "baseline":
            return 0, "ok"
        runs = hub.repo / ".agent" / "runs" / "t001-doc" / "baseline"
        runs.mkdir(parents=True, exist_ok=True)
        out = runs / ("%02d" % (len(list(runs.iterdir())) + 1))
        out.mkdir()
        (out / "V01.log").write_text("tests/test_gate_t001_baseline.py F\n%s\n" % summary, encoding="utf-8")
        record = {"results": [{"id": "V01", "argv": ["python", "-m", "pytest", "tests/test_gate_t001_baseline.py", "-q"],
                               "log": "%s/V01.log" % out.name, "exit_code": exit_code, "timed_out": timed_out,
                               "interrupted": False, "spawn_error": None}]}
        (out / "checks.json").write_text(json.dumps(record), encoding="utf-8")
        return 0, "V01  fail  failed  符合预期\n基线检查记录：%s\n" % (out / "checks.json").relative_to(hub.repo).as_posix()
    return fake


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
    monkeypatch.setattr(kh, "run_pd", pd_with_baseline(calls))
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
    monkeypatch.setattr(kh, "run_pd", run_pd or pd_with_baseline(calls))
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


def test_gate_pre_baseline_must_fail_on_assertions(tmp_path, monkeypatch):
    # 第 14 轮：超时、pytest 退出码 2–5、setup 出错都算“在基线上失败”，测试其实没跑起来（docs/实际问题/门禁端.md）
    calls = []
    repo, head, hub, ts, _plans, _calls = gate_setup(tmp_path, monkeypatch, run_pd=pd_with_baseline(calls, exit_code=5))
    expected = "tests/test_gate_t001_baseline.py"
    workspace = kh.ensure_worktree(hub, ts, "gate", head)
    (workspace / "tests").mkdir()
    (workspace / expected).write_text("def test_x():\n    assert False\n", encoding="utf-8")
    problems = kh.accept_gate_pre(hub, ts, workspace)
    assert problems == ["V01 在基线上的 pytest 退出码是 5：只有 1 是用例失败（2 中断、3 内部错误、4 用法错误、5 没有用例）"]
    assert not ts["oracle"]["locked"]  # 不锁进禁改路径
    kh.git(["worktree", "remove", "--force", str(workspace)], repo)

    def judge(**outcome):
        _code, out = pd_with_baseline([], **outcome)(hub, ["baseline", "t001-doc.v1"])
        return kh.hollow_baseline_problems(hub, out, expected)

    assert judge() == [] and judge(summary="11 failed, 29 passed in 23.50s") == []  # T003 的基线就是这样
    assert any("超时" in p for p in judge(timed_out=True))
    for code in (0, 2, 3, 4):
        assert any("退出码是 %d" % code in p for p in judge(exit_code=code))
    assert any("2 个用例出错" in p for p in judge(summary="1 failed, 2 errors in 0.10s"))
    assert any("没有失败的用例" in p for p in judge(summary="3 passed in 0.10s"))
    assert judge(summary="（没有摘要行）") == []  # 读不到摘要，只看退出码
    assert kh.hollow_baseline_problems(hub, "ok", expected) == ["baseline 没有留下检查记录，核对不了基准测试在基线上是怎样失败的"]
    _code, out = pd_with_baseline([])(hub, ["baseline", "t001-doc.v1"])
    assert kh.hollow_baseline_problems(hub, out, "tests/test_gate_t009_baseline.py") == [
        "baseline 的检查记录里没有跑 tests/test_gate_t009_baseline.py 的检查"]


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
    assert ts["contract"]["written_version"] == 2  # 合同端写的这一版：之后升版的都按它做（第 35 轮）
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
    assert "名为 `pipeline` 的会话级夹具" in kh.role_prompt("gate-sonnet")  # tests/conftest.py 认这个名字


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
    records, timeouts = {}, []

    def fake_pd(hub, args, timeout=600):
        if "--check-anchors" in args:
            return 0, "锚点核对：2 条，0 条不符"
        timeouts.append(timeout)
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
    # 第 15 轮：每条变异的时限按白盒用时定（下限 60 秒），写进存档的清单；整份的时限按条数放宽
    archived = json.loads(Path(ts["gate_post"]["mutate_spec"]).read_text(encoding="utf-8"))
    assert archived["timeout_seconds"] == ts["gate_post"]["mutant_timeout"] == 60 and timeouts[-1] == 3600
    assert kh.accept_gate_post(hub, ts, workspace, {"mutation_spec": dict(spec, timeout_seconds=2000)}) == []
    assert ts["gate_post"]["mutant_timeout"] == 2000 and timeouts[-1] == 3 * 2000 + 600  # 门禁端写了就照它的
    record = ts["gate_post"]["mutate_record"]  # 在信箱的证据目录里：终审读得到
    assert record.startswith(".agent/mailbox/tasks/T001-6-gate-post/evidence/mutate-") and (repo / record).is_file()
    log = repo / ts["gate_post"]["whitebox_log"]
    assert log.is_file() and ts["gate_post"]["whitebox_exit"] == 0 and "passed" in ts["gate_post"]["whitebox_tail"]
    # 白盒测试文件也存进信箱：结项清掉 worktree 之后，终审与站主还能复核跑的是哪一份（第 12 轮）
    copy = repo / ts["gate_post"]["whitebox_file"]
    assert copy.parent == log.parent and copy.read_text(encoding="utf-8") == target.read_text(encoding="utf-8")
    prompt = kh.turn_prompt(hub, ts, "audit-sonnet", "T001-7-audit-post", [], tmp_path)
    assert str(copy) in prompt
    target.write_text("def test_bad():\n    assert False\n", encoding="utf-8")
    assert any("白盒测试" in p for p in kh.accept_gate_post(hub, ts, workspace, {"mutation_spec": spec}))
    kh.git(["worktree", "remove", "--force", str(workspace)], repo)


def test_gate_post_checks_the_anchors_before_mutating(tmp_path, monkeypatch):
    # T003 的 M29：old 把全角括号写成了半角，内核只回一句“M29 没生效”，门禁端手里没有原文，30 条全部重写（第 12 轮）
    real = kh.run_pd
    calls = []

    def fake_pd(hub, args, timeout=600):
        calls.append([arg for arg in args if arg.startswith("--")])
        if "--check-anchors" in args:
            return real(hub, args, timeout)  # 真的调度器：锚点核对不跑命令，只读文件
        out_dir = Path(args[args.index("--out") + 1])
        out_dir.mkdir(parents=True)
        (out_dir / "mutations.json").write_text(json.dumps(mutation_record("caught")), encoding="utf-8")
        return 0, "变异 1 条"

    repo, head, hub, ts, _plans, _calls = gate_setup(tmp_path, monkeypatch, run_pd=fake_pd)
    ts["exec"] = {"run_dir": str(tmp_path / "attempt-001")}
    workspace = kh.ensure_worktree(hub, ts, "post-attempt-001", head)
    (workspace / "README.md").write_text("目录约定\nfonts.css  # 随包字体（等距更纱黑体 SC）\n", encoding="utf-8")
    ts["workspaces"]["post-attempt-001"]["baseline_status"] = kh.workspace_status(workspace)  # 候选补丁改的
    target = workspace / "tests" / "test_gate_t001_whitebox.py"
    target.parent.mkdir(parents=True)
    target.write_text("def test_ok():\n    pass\n", encoding="utf-8")
    wrong = {"name": "删掉 fonts.css 那一行", "file": "README.md", "old": "# 随包字体(等距更纱黑体 SC)", "new": ""}
    command = ["python", "-m", "pytest", "tests/test_gate_t001_whitebox.py", "-q"]
    problems = kh.accept_gate_post(hub, ts, workspace, {"mutation_spec": {"command": command, "mutations": [wrong]}})
    assert len(problems) == 1 and "锚点核对" in problems[0] and "变异没有跑" in problems[0], problems
    assert "M01" in problems[0] and "最相近 L2" in problems[0] and "（等距更纱黑体 SC）" in problems[0]
    assert calls == [["--tree", "--spec", "--check-anchors"]] and ts["gate_post"]["ok"] is False
    # 返工时门禁端读得到上一版清单的存档，在它上面改
    spec_path = ts["gate_post"]["mutate_spec"]
    assert Path(spec_path).is_file() and Path(spec_path).relative_to(repo).as_posix() in problems[0]
    assert spec_path in kh.turn_prompt(hub, ts, "gate-sonnet", "T001-6-gate-post", [], workspace)
    calls.clear()
    right = dict(wrong, old="# 随包字体（等距更纱黑体 SC）")
    assert kh.accept_gate_post(hub, ts, workspace, {"mutation_spec": {"command": command, "mutations": [right]}}) == []
    assert calls == [["--tree", "--spec", "--check-anchors"], ["--tree", "--spec", "--out"]] and ts["gate_post"]["ok"]
    kh.git(["worktree", "remove", "--force", str(workspace)], repo)


def test_contract_title_is_the_registered_task_title(tmp_path, monkeypatch):
    # T003 的提交主题取自 Goal 第一行、截到 120 字，断在“让 `dist` 里恰有与”（第 12 轮）
    _repo, _head, hub, ts, _plans, calls = gate_setup(tmp_path, monkeypatch)
    kh.revalidate_contract(hub, ts)
    assert calls[0] == ["derive-json", "t001-doc.v1", "--force", "--title", "改文档"]


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
        if "--check-anchors" in args:
            return 0, "锚点核对：1 条，0 条不符"
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
    assert any("可白盒测试在候选上全部通过" in p for p in problems) and calls == ["mutate", "mutate"]  # 锚点、变异
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
    templates = tmp_path / "hub"
    templates.mkdir()
    (templates / "worker.md").write_text("旧模板", encoding="utf-8")
    code = tmp_path / "kit_hub.py"
    code.write_text("# 旧内核", encoding="utf-8")
    dispatcher = tmp_path / "pi_dispatch.py"
    dispatcher.write_text("# 旧调度器", encoding="utf-8")
    files = [code, dispatcher, templates / "worker.md"]
    first = kh.code_fingerprint(files)
    assert kh.code_fingerprint(files) == first
    seen = {first}
    for path, text in ((templates / "worker.md", "新模板"), (code, "# 新内核"), (dispatcher, "# 新调度器")):
        path.write_text(text, encoding="utf-8")
        seen.add(kh.code_fingerprint(files))
    assert len(seen) == 4  # 第 13 轮：调度器也算（内核在进程里直接调它的函数）
    here = Path(kh.__file__).parent
    assert kh.kernel_files()[:2] == [Path(kh.__file__), here / "pi_dispatch.py"]
    assert here / "hub" / "worker.md" in kh.kernel_files() and kh.code_fingerprint() == kh.code_fingerprint(kh.kernel_files())
    repo, _head = git_repo(tmp_path)
    events, steps, spawned = run_with_kernel_change(repo, monkeypatch, dirty=[True], no_restart=False, settle=0.0)
    assert len(steps) == 2 and spawned == []  # 启动时 a；第 1、2 步之前还是 a；第 3 步之前变成 b；还没提交，退出
    assert [e["event"] for e in events if e["event"].startswith("runner.")] == [
        "runner.started", "runner.code_changed", "runner.stopped"]
    assert next(e for e in events if e["event"] == "runner.code_changed")["restart"] is False


def run_with_kernel_change(repo, monkeypatch, dirty, no_restart, settle):
    """跑 cmd_run：指纹在第 3 步之前变掉；kernel_dirty 依次返回 dirty 里的值（用完之后一直是最后一个）。"""
    import argparse
    seen = iter(["a", "a", "a", "b", "b"])
    monkeypatch.setattr(kh, "code_fingerprint", lambda *args: next(seen))
    answers = list(dirty)
    monkeypatch.setattr(kh, "kernel_dirty", lambda *args: answers.pop(0) if len(answers) > 1 else answers[0])
    steps, spawned = [], []
    monkeypatch.setattr(kh.Engine, "step", lambda self: steps.append(1) or True)

    def spawn(argv):
        # 运行锁已经交出：子进程拿得到
        with kh.DirLock(kh.Hub(repo).root / ".runner", wait_seconds=0.1):
            spawned.append(list(argv))
        return 7

    monkeypatch.setattr(kh, "spawn_runner", spawn)
    code = kh.cmd_run(argparse.Namespace(repo=str(repo), max_steps=10, idle_exit=0.0, poll=0.0, settle=settle,
                                         no_restart=no_restart))
    assert code == (7 if spawned else kh.EXIT_OK)
    events = [json.loads(line) for line in kh.Hub(repo).ledger().read_text(encoding="utf-8").splitlines()]
    return events, steps, spawned


def test_runner_restarts_on_committed_kernel_changes(tmp_path, monkeypatch):
    # 第 13 轮：持续自我迭代时内核频繁落地，每次都要站主手动重启，任务就停在那里等
    repo, _head = git_repo(tmp_path)
    events, steps, spawned = run_with_kernel_change(repo, monkeypatch, dirty=[True, True, False], no_restart=False,
                                                    settle=60.0)
    assert len(steps) == 2 and len(spawned) == 1  # 等到改动提交，再用新代码接着跑
    argv = spawned[0]
    assert argv[1] == str(Path(kh.__file__)) and argv[2:5] == ["--repo", str(repo), "run"]
    assert argv[argv.index("--max-steps") + 1] == "8" and argv[argv.index("--settle") + 1] == "60.0"
    changed = next(e for e in events if e["event"] == "runner.code_changed")
    assert changed["restart"] is True and changed["steps"] == 2
    _events, _steps, spawned = run_with_kernel_change(repo, monkeypatch, dirty=[False], no_restart=True, settle=60.0)
    assert spawned == []  # --no-restart：照第 9 轮退出


def test_kernel_dirty_reads_git_status(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))  # basetemp 可能就在本仓库里
    repo, _head = git_repo(tmp_path)
    readme = repo / "README.md"
    assert kh.kernel_dirty([readme]) is False
    readme.write_text("改了\n", encoding="utf-8")
    assert kh.kernel_dirty([readme]) is True
    kh.git(["commit", "-q", "-am", "提交"], repo)
    assert kh.kernel_dirty([readme]) is False
    outside = tmp_path / "plain"
    outside.mkdir()
    (outside / "kit_hub.py").write_text("# 不在仓库里\n", encoding="utf-8")
    assert kh.kernel_dirty([outside / "kit_hub.py"]) is True  # 说不清是哪一份代码，不自动重启


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
    plans = tmp_path / ".agent" / "plans"
    plans.mkdir(parents=True)
    (plans / "t001-doc.v1.md").write_text("# TASK: t001-doc\n\n## Goal\n补完桌面端文档的第 3 节，\n不改代码。\n\n"
                                         "## Scope\n- docs/a.md\n", encoding="utf-8")
    (plans / "t001-doc.v1.json").write_text(json.dumps({"title": "改桌面端文档"}), encoding="utf-8")
    fields = kh.run_jev(hub, ts, "6j-jev")
    # 判“超出范围”看完整的目标：合同标题现在是站主登记的短名（第 12 轮）
    assert seen["state"]["contract_goal"] == "补完桌面端文档的第 3 节，\n不改代码。"
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


def test_output_block_tolerates_only_trailing_closers():
    # T004 的协调人 8 次输出都在结尾多写了 `]}`，每次白跑一个回合（第 18 轮）
    warnings: list = []
    text = "```json\n{\"letters\": [{\"to\": \"x\"}], \"state\": \"s\"}]}\n```"
    assert kh.extract_json_block(text, warnings) == {"letters": [{"to": "x"}], "state": "s"}
    assert len(warnings) == 1 and "]}" in warnings[0]
    clean: list = []
    assert kh.extract_json_block("```json\n{\"a\": 1}\n```", clean) == {"a": 1} and clean == []
    for extra in ("]} 还有话", "{\"b\": 2}", "x"):  # 多了别的内容照旧拒收
        with pytest.raises(kh.HubError):
            kh.extract_json_block("```json\n{\"a\": 1}%s\n```" % extra, [])
    with pytest.raises(kh.HubError):
        kh.extract_json_block("```json\n[1]]\n```", [])  # 顶层不是对象


def test_output_block_merges_keys_written_after_an_early_close():
    # 第 32 轮：T010 的规划端在 state 之后收了尾，又写了 `, "external_facts": [...]}`，四万多字的回合作废
    warnings: list = []
    text = ("```json\n{\"letter\": {\"type\": \"交付\"}, \"report\": \"r\", \"state\": \"s\"}, "
            "\"external_facts\": [{\"fact\": \"f\"}]}\n```")
    assert kh.extract_json_block(text, warnings) == {"letter": {"type": "交付"}, "report": "r", "state": "s",
                                                     "external_facts": [{"fact": "f"}]}
    assert len(warnings) == 1 and "提前收了尾" in warnings[0] and "external_facts" in warnings[0]
    # 后面改写了已有的键：不是“补上漏写的键”，不并；只是重复已有键的，照第 25 轮取第一份
    assert kh.merge_early_close("{\"a\": 1}, \"a\": 2}", 8, {"a": 1}) is None
    assert kh.extract_json_block("```json\n{\"a\": 1}, \"a\": 2}\n```", []) == {"a": 1}
    for bad in ("{\"a\": 1}, 坏的}", "{\"a\": 1} , \"state\": [}", "{\"a\": 1}\"state\": 2}",
                "{\"a\": 1}, \"verdict\": 2}"):  # 认不得的键（第 25 轮）照旧拒收
        with pytest.raises(kh.HubError):
            kh.extract_json_block("```json\n%s\n```" % bad, [])
    assert kh.merge_early_close("{\"a\": 1} , \"state\": \"s\"}", 8, {"a": 1}) == {"a": 1, "state": "s"}
    assert kh.merge_early_close("{\"a\": 1}, \"a\": 1}", 8, {"a": 1}) is None  # 没有新键：不是漏写
    assert kh.merge_early_close("{\"a\": 1}, \"a\": 2, \"state\": \"s\"}", 8, {"a": 1}) is None  # 顺手改了已有的键
    assert kh.merge_early_close("[1], 2]", 3, [1]) is None  # 顶层不是对象
    assert kh.merge_early_close("{\"a\": 1}, \"state\": 2", 8, {"a": 1}) is None  # 并不成一个对象（少了右括号）


def test_turn_records_the_ignored_trailing_closers(tmp_path, monkeypatch):
    monkeypatch.setitem(kh.ROSTER, "audit-sonnet", CLAUDE_AUDIT)
    hub = kh.Hub(tmp_path)
    hub.ensure()
    final = "交付。\n```json\n{\"letter\": {\"type\": \"交付\"}, \"state\": \"s\"}]}\n```"

    def launcher(cmd, cwd, env, out, err, timeout):
        events = [INIT, {"type": "result", "result": final}]  # 审核端：只读三件工具，sonnet
        out.write(("\n".join(json.dumps(e) for e in events) + "\n").encode("utf-8"))
        return {"exit_code": 0, "timed_out": False, "wall_seconds": 1.0}

    turn = kh.TurnRunner(hub, launcher=launcher).run("audit-sonnet", "T001-7-audit-post", tmp_path, "角色", "输入")
    assert turn["violations"] == [] and turn["output"] == {"letter": {"type": "交付"}, "state": "s"}
    assert turn["output_error"] is None
    record = json.loads(Path(turn["turn_dir"], "result.json").read_text(encoding="utf-8"))
    assert any("末尾多了 ]}" in w for w in record["warnings"])


def test_pi_refused_calls_outside_the_allowlist_only_warn():
    # T004 的合同端：pi 回 “Tool bash not found”，模型改用 ls，内核却把回合作废
    spec = {"tools": ["read", "ls"], "provider": "p", "model": "m"}
    start = {"type": "tool_execution_start", "toolCallId": "c1", "toolName": "bash", "args": {"command": "ls -la"}}

    def end(is_error: bool, text: str) -> dict:
        return {"type": "tool_execution_end", "toolCallId": "c1", "toolName": "bash", "isError": is_error,
                "result": {"content": [{"type": "text", "text": text}]}}

    refused = kh.audit_pi_stream(stream(start, end(True, "Tool bash not found")), spec)
    assert refused["violations"] == [] and len(refused["warnings"]) == 1 and "bash" in refused["warnings"][0]
    for is_error, text in ((False, "total 0"), (False, "Tool bash not found"), (True, "Permission denied"),
                           (True, "Tool read not found")):
        audit = kh.audit_pi_stream(stream(start, end(is_error, text)), spec)
        assert any("bash" in v for v in audit["violations"]) and audit["warnings"] == []
    other_id = dict(end(True, "Tool bash not found"), toolCallId="c2")  # 别的调用的拒绝不算
    assert any("bash" in v for v in kh.audit_pi_stream(stream(start, other_id), spec)["violations"])


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


def test_kernel_writes_the_contract_version_and_base_it_assigns(tmp_path, monkeypatch):
    # 第 16、17 轮：T004 的合同端返工时照抄了上一版的 plan_version，base_sha 写成当时的 HEAD；
    # 内核每交一次没过核验就占掉一个版本号，要求的版本号跟着涨，三次都追不上
    _repo, head, hub, ts, plans, _calls = gate_setup(tmp_path, monkeypatch)
    ts["contract"]["validated"] = True  # v1 通过过核验（例如一审退回之后重写）：出新版本
    md = "# TASK: t001-doc\n\n## Identity\n- plan_version: 1\n- base_sha: %s\n" % ("b" * 40)
    kh.accept_contract(hub, ts, {"contract_md": md})
    first = (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    assert ts["contract"]["key"] == "t001-doc.v2" and ts["contract"]["validated"] is False  # 假调度器没写 JSON
    assert "\n- plan_version: 2\n" in first and "\n- base_sha: %s\n" % head in first
    # v2 没过核验、也没派遣：原号重写，旧稿留档；写对了照原样
    right = md.replace("plan_version: 1", "plan_version: `2`").replace("b" * 40, head)
    kh.accept_contract(hub, ts, {"contract_md": right})
    assert ts["contract"]["key"] == "t001-doc.v2" and not (plans / "t001-doc.v3.md").exists()
    assert "\n- plan_version: `2`\n" in (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    archived = list((hub.task_dir("T001-2-contract") / "evidence").glob("t001-doc.v2.rejected-*.md"))
    assert len(archived) == 1 and archived[0].read_text(encoding="utf-8") == first
    # 派遣过的版本只增不改
    ts["contract"]["dispatched"] = True
    kh.accept_contract(hub, ts, {"contract_md": md})
    assert ts["contract"]["key"] == "t001-doc.v3"
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert [(e["key"], e["written"]) for e in events if e["event"] == "contract.identity_normalized"] == [
        ("t001-doc.v2", {"plan_version": "1", "base_sha": "b" * 40}),
        ("t001-doc.v3", {"plan_version": "1", "base_sha": "b" * 40})]
    assert [e["key"] for e in events if e["event"] == "contract.redrafted"] == ["t001-doc.v2"]
    ts["contract"] = {"key": "t001-doc.v3", "version": 3}
    prompt = kh.turn_prompt(hub, ts, "contract-glm", "T001-2-contract", [], _repo)
    assert "plan_version 写 3、base_sha 写 %s" % head in prompt  # 没过核验的 v3 原号重写


def test_contract_runs_the_earlier_gates_as_regression_checks(tmp_path, monkeypatch):
    # 第 14 轮：T002 的合同没有回归检查，T003 的是合同端自愿写的；存量功能静默退化没有一道关拦
    repo, _head, hub, ts, plans, _calls = gate_setup(tmp_path, monkeypatch)
    (repo / "tests").mkdir()
    for name in ("test_gate_t000_baseline.py", "test_gate_t001_baseline.py", "test_gate_t000_whitebox.py", "test_x.py"):
        (repo / "tests" / name).write_text("def test_x():\n    pass\n", encoding="utf-8")
    kh.git(["add", "tests"], repo)
    kh.git(["commit", "-q", "-m", "先前各片"], repo)
    ts["base_head"] = kh.git(["rev-parse", "HEAD"], repo).strip()
    assert kh.regression_gates(hub, ts) == ["tests/test_gate_t000_baseline.py"]  # 本任务自己的、白盒、别的测试不算
    contract = json.loads((plans / "t001-doc.v1.json").read_text(encoding="utf-8"))
    assert kh.contract_requirements(hub, ts) == [
        "Validation commands 要有一条必要、基线应通过的回归检查，跑先前各片的门禁基准测试：tests/test_gate_t000_baseline.py"]
    regression = {"id": "VR1", "argv": ["python", "-m", "pytest", "tests/test_gate_t000_baseline.py", "-q"],
                  "expect_on_base": "pass", "required": True}
    for check, ok in ((dict(regression, expect_on_base="fail"), False), (dict(regression, required=False), False),
                      (regression, True)):
        contract["checks"] = [contract["checks"][0], check]
        (plans / "t001-doc.v1.json").write_text(json.dumps(contract), encoding="utf-8")
        assert (kh.contract_requirements(hub, ts) == []) is ok, check
    prompt = kh.turn_prompt(hub, ts, "contract-glm", "T001-2-contract", [], repo)
    assert "R01（必要，基线应通过）：`python -m pytest tests/test_gate_t000_baseline.py -q`" in prompt
    assert "VG1" not in prompt and "VR1" not in prompt  # 调度器只认一个大写字母加两位数字（第 43 轮）


def test_mutant_timeout_follows_the_whitebox_time():
    assert kh.mutant_timeout({"mutations": []}, 12.3) == 62
    assert kh.mutant_timeout({"mutations": []}, 3.0) == 60
    assert kh.mutant_timeout({"mutations": [], "timeout_seconds": 900}, 12.3) is None
    assert kh.mutant_timeout({"mutations": []}, None) is None


def test_contract_block_or_executor_conflict_can_send_the_work_upstream(engine_env):
    # 第 15 轮：合同端发现规划有缺陷没有路由；执行端的合同矛盾只能走门禁热修补
    hub = engine_env
    state = hub.load_state()
    ts = state["tasks"]["T001"] = locked(make_ts())
    ts["stages"]["2-contract"]["status"] = "assigned"
    hub.save_state(state)
    hub.deliver({"from": kh.COORDINATOR, "to": "contract-glm", "task-id": "T001-2-contract", "in-reply-to": "none",
                 "type": "开工"}, fields(摘要="写合同"))
    blocked = {"letter": {"type": "阻塞", "in_reply_to": "m", "摘要": "规划第 3 步要改的 src/x.ts 不存在", "提交": "无",
                          "验证": "读了代码", "偏离": "无", "需协调人决定": "退回规划端", "证据": "src/"},
               "report": "# 阻塞", "state": "s"}
    assert kh.Engine(hub, FakeRunner([(blocked, [])])).step()
    ts = hub.load_state()["tasks"]["T001"]
    # 第 28 轮：工人停下之后阶段是 paused，不再一直挂着 assigned
    assert ts["stages"]["2-contract"]["last_letter"] == "阻塞" and ts["stages"]["2-contract"]["status"] == "paused"
    assert kh.guard(ts, meta("返工", "planner-opus", "T001-1-plan")) is None
    ts["stages"]["2-contract"]["last_letter"] = "提问"
    assert "合同端也没有发" in kh.guard(ts, meta("返工", "planner-opus", "T001-1-plan"))
    # 执行端报了合同矛盾：门禁热修补与合同改版都放行，由协调人按矛盾指向哪一端来选
    ts["stages"]["2-contract"]["status"] = "delivered"
    assert "没有一审或终审退回" in kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract"))
    ts["exec"]["conflicts"] = 1
    assert kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract")) is None
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre")) is None


def test_mutations_must_cover_the_changed_files(tmp_path, monkeypatch):
    # 第 14 轮：变异可以全打在无关紧要的地方，核心改动一条也不碰（docs/实际问题/审核端.md）
    calls = []
    monkeypatch.setattr(kh, "run_pd", lambda hub, args, timeout=600: calls.append(list(args)) or (0, "ok"))
    hub = kh.Hub(tmp_path)
    hub.ensure()
    run_dir = tmp_path / "attempt-001"
    run_dir.mkdir()
    files = [{"path": path, "status": status} for path, status in (
        ("src/a.ts", "M"), ("src/b.css", "A"), ("fonts/x.woff2", "A"), ("old.txt", "D"), ("tests/test_x.py", "A"),
        ("desktop/web/tests/x.test.tsx", "A"), ("src/c.spec.ts", "A"))]
    (run_dir / "scope.json").write_text(json.dumps({"files": files}), encoding="utf-8")
    ts = locked(make_ts())
    ts["exec"] = {"run_dir": str(run_dir)}
    ts["gate_post"] = {"ran": True}
    spec = {"mutations": [{"name": "改坏", "file": "src/a.ts", "old": "a", "new": "b"}]}
    assert kh.unmutated_problems(ts, spec, {}) == [
        "执行端改动了这些文件，变异清单却一条也没打在上面：fonts/x.woff2、src/b.css。每个改动的文件至少一条变异；"
        "确实没法变异的（例如二进制文件），在输出的 unmutated 里写 {\"file\": ..., \"reason\": ...}，终审会复核"]
    stage_dir = hub.task_dir("T001-6-gate-post")
    stage_dir.mkdir(parents=True)
    problems = kh.run_mutations(hub, ts, tmp_path, stage_dir, {"mutation_spec": spec})
    assert len(problems) == 1 and "fonts/x.woff2、src/b.css" in problems[0] and calls == []  # 没覆盖就不跑变异
    blank = {"unmutated": [{"file": "fonts/x.woff2", "reason": " "}, {"file": "src/b.css", "reason": "只有注释"}]}
    assert "fonts/x.woff2" in kh.unmutated_problems(ts, spec, blank)[0]  # 理由不能是空的
    explained = {"unmutated": [{"file": "fonts/x.woff2", "reason": "二进制字体"}, {"file": "src/b.css", "reason": "只有注释"},
                               {"file": "nope.txt", "reason": "没改过的文件不列"}]}
    assert kh.unmutated_problems(ts, spec, explained) == []
    assert ts["gate_post"]["unmutated"] == ["fonts/x.woff2：二进制字体", "src/b.css：只有注释"]
    prompt = kh.turn_prompt(hub, ts, "audit-sonnet", "T001-7-audit-post", [], tmp_path)
    assert "## 门禁端说没法变异的改动文件" in prompt and "- fonts/x.woff2：二进制字体" in prompt


def test_stage_reworks_are_capped(engine_env):
    # 第 14 轮：执行端有合同预算封顶，别的阶段没有，同一处可以无限返工（docs/实际问题/协调端.md 的返工乒乓）
    hub = engine_env
    state = hub.load_state()
    ts = state["tasks"]["T001"] = locked(make_ts())
    engine = kh.Engine(hub, FakeRunner([]))
    letter = dict(fields(), to="contract-glm", task_id="T001-2-contract", type="返工", brief="# 改合同")
    for count in (1, 2, 3):
        ts["stages"]["2-contract"]["status"] = "failed"
        assert engine.deliver_coordinator_letter(state, letter) is None and ts["reworks"] == {"2-contract": count}
    ts["stages"]["2-contract"]["status"] = "failed"
    assert "已经返工 3 次" in engine.deliver_coordinator_letter(state, letter)
    ts["owner_rework"] = {"suffix": "2-contract"}  # 站主指定的照样放行，也不计数
    assert engine.deliver_coordinator_letter(state, letter) is None and ts["reworks"] == {"2-contract": 3}
    assert "owner_rework" not in ts and "2-contract 3 次" in kh.stage_status_table(hub, ts)
    ts["reworks"]["5-exec"] = 9  # 执行端由合同预算封顶，不受这个上限
    ts["audit_post"].update(verdict="返工", target="执行端")
    assert kh.guard(ts, meta("返工", "exec-step", "T001-5-exec")) is None
    kh.invalidate_after(ts, "1-plan")  # 上游重新交付：下游的返工从头计
    assert ts["reworks"] == {}


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
        timed_out = rest[1] if len(rest) > 1 else False
        rate_limited_until = rest[2] if len(rest) > 2 else None
        return {"turn_id": "t%d" % len(self.calls), "turn_dir": "turns/x", "output": output,
                "violations": violations, "api_error": api_error, "timed_out": timed_out,
                "rate_limited_until": rate_limited_until,
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


LIMIT = "429 rate_limit：You've hit your session limit · resets 5:20am (America/Los_Angeles)"


def make_held_due(hub):
    state = hub.load_state()
    for item in state["tasks"]["T001"]["held"]:
        item["until"] = "2000-01-01T00:00:00Z"
    hub.save_state(state)


def test_a_rate_limited_worker_turn_is_held_and_resumed(engine_env):
    # 第 33 轮：T010 的门禁端撞上 session limit，阶段判 failed，等站主回信才接着做
    hub = engine_env
    owner_task(hub)
    until = int(time.time()) + 3600
    runner = FakeRunner([({"letters": [start_planner()]}, []), (None, [], LIMIT, False, until),
                         (planner_delivery(), [])])
    engine = kh.Engine(hub, runner)
    engine.step()
    engine.step()
    assert len(runner.calls) == 2  # 不重试，也不升级
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["status"] == "active" and ts["stages"]["1-plan"]["status"] == "paused"
    held = ts["held"][0]
    assert held["agent"] == "planner-opus" and held["suffix"] == "1-plan" and len(held["letters"]) == 1
    assert held["until"] == time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(until))
    letters = [p.read_text(encoding="utf-8") for p in hub.unread(kh.OWNER)]
    assert len(letters) == 1 and "type: 核验" in letters[0] and "额度限制" in letters[0] and held["until"] in letters[0]
    assert hub.unread("planner-opus") == [] and hub.unread(kh.COORDINATOR) == []
    assert kh.letters_held(hub) and kh.supervisor_busy(hub, [], 0) and not kh.runner_may_idle_exit(hub, None)
    assert kh.runner_may_idle_exit(hub, "T001")  # 主任务 runner 可以退：到点由 supervisor 再起
    assert engine.step() is False and kh.release_held(hub) == []  # 没到点：信还扣着
    make_held_due(hub)
    assert kh.release_held(hub) == ["T001"] and len(hub.unread("planner-opus")) == 1
    assert hub.load_state()["tasks"]["T001"]["stages"]["1-plan"]["status"] == "assigned"  # 协调人不能再开工一次
    assert engine.step()  # 信放回信箱，接着做（续接原来的会话）
    assert runner.calls[2][0] == "planner-opus" and runner.fresh[-1] is False
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["stages"]["1-plan"]["status"] == "delivered" and ts["held"] == []
    assert not kh.letters_held(hub) and not kh.supervisor_busy(hub, [], 0) and kh.supervisor_busy(hub, ["T001"], 0)
    assert kh.supervisor_busy(hub, [], 1) and kh.runner_may_idle_exit(hub, None)
    events = [json.loads(line)["event"] for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert "letters.held" in events and "letters.released" in events


def test_held_letters_are_dropped_when_the_stage_was_restarted_meanwhile(engine_env):
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([({"letters": [start_planner()]}, []), (None, [], LIMIT, False, int(time.time()) + 60)])
    engine = kh.Engine(hub, runner)
    engine.step()
    engine.step()
    name = hub.load_state()["tasks"]["T001"]["held"][0]["letters"][0]
    state = hub.load_state()
    state["tasks"]["T001"]["stages"]["1-plan"]["status"] = "assigned"  # 站主提前回信，协调人又开工了
    hub.save_state(state)
    make_held_due(hub)
    assert kh.release_held(hub) == ["T001"]
    assert hub.unread("planner-opus") == []  # 放回去就会做两遍
    assert (hub.inbox("planner-opus").parent / "cur" / name).is_file()
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["held"] == [] and ts["stages"]["1-plan"]["status"] == "assigned"
    events = [json.loads(line)["event"] for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert "letters.dropped" in events and "letters.released" not in events


def test_a_rate_limited_turn_that_also_broke_the_rules_is_not_held(engine_env):
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([({"letters": [start_planner()]}, []),
                         (None, ["调用了白名单之外的工具：Bash（tool_use）"], LIMIT, False, int(time.time()) + 60)])
    engine = kh.Engine(hub, runner)
    engine.step()
    engine.step()
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["stages"]["1-plan"]["status"] == "failed" and not ts.get("held")


def test_supervisor_puts_due_letters_back_and_starts_their_runner(tmp_path, monkeypatch):
    hub = kh.Hub(tmp_path)
    hub.ensure()
    hub.save_state({"tasks": {"T001": make_ts()}})
    path = hub.deliver({"from": kh.COORDINATOR, "to": "planner-opus", "task-id": "T001-1-plan", "in-reply-to": "none",
                        "type": "开工"}, fields())
    taken = hub.take(hub.inbox("planner-opus") / ("%s.md" % path))
    state = hub.load_state()
    state["tasks"]["T001"]["stages"]["1-plan"]["status"] = "paused"
    state["tasks"]["T001"]["held"] = [{"agent": "planner-opus", "letters": [taken.name], "until": "2000-01-01T00:00:00Z",
                                       "suffix": "1-plan", "turn": "t1"}]
    hub.save_state(state)
    spawned = []
    monkeypatch.setattr(kh, "kernel_dirty", lambda *a: False)
    child = type("Child", (), {"pid": 7})()
    monkeypatch.setattr(kh, "spawn_task_runner", lambda hub_, task, args: spawned.append(task) or child)
    pending, live, count = kh.supervise_tick(hub, None, 3, {}, {})
    assert pending == ["T001"] and spawned == ["T001"] and count == 1
    assert [p.name for p in hub.unread("planner-opus")] == [taken.name]


def test_turn_runner_reports_when_the_rate_limit_lifts(tmp_path):
    hub = kh.Hub(tmp_path)
    hub.ensure()

    def launcher(cmd, cwd, env, out, err, timeout):
        events = [dict(INIT, tools=["Read", "Grep", "Glob"], model="claude-opus-5-5"),
                  {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "resetsAt": 1792585200}},
                  dict(API_ERROR, api_error_status=429, api_error_code="rate_limit"),
                  {"type": "result", "result": "You've hit your session limit"}]
        out.write(("\n".join(json.dumps(e) for e in events) + "\n").encode("utf-8"))
        return {"exit_code": 1, "timed_out": False, "wall_seconds": 1.0}

    turn = kh.TurnRunner(hub, launcher=launcher).run("planner-opus", "T001-1-plan", tmp_path, "角色", "输入")
    assert turn["rate_limited_until"] == 1792585200 and "429" in turn["api_error"]


def test_a_rate_limited_coordinator_turn_is_held_and_resumed(engine_env):
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([(None, [], LIMIT, False, int(time.time()) + 600), ({"letters": [start_planner()]}, [])])
    engine = kh.Engine(hub, runner)
    engine.step()
    ts = hub.load_state()["tasks"]["T001"]
    assert len(runner.calls) == 1 and ts["status"] == "active"  # 不再转 blocked
    assert ts["held"][0]["agent"] == kh.COORDINATOR and ts["held"][0]["suffix"] is None
    assert hub.unread(kh.COORDINATOR) == [] and "额度限制" in hub.unread(kh.OWNER)[0].read_text(encoding="utf-8")
    make_held_due(hub)
    assert engine.step() and runner.calls[1][0] == kh.COORDINATOR
    assert hub.load_state()["tasks"]["T001"]["stages"]["1-plan"]["status"] == "assigned"


def test_audit_reads_when_a_rate_limit_lifts():
    def limit(status):
        return {"type": "rate_limit_event", "rate_limit_info": {"status": status, "resetsAt": 1792585200}}
    result = {"type": "result", "result": "x"}
    limited = kh.audit_claude_stream(stream(INIT, limit("allowed_warning"), limit("rejected"), API_ERROR, result), SPEC)
    assert limited["rate_limited_until"] == 1792585200
    for events in ((limit("rejected"), limit("allowed"), API_ERROR, result),  # 后来又放行了：是别的错
                   (limit("allowed_warning"), API_ERROR, result),  # 只是警告
                   (limit("rejected"), assistant({"type": "text", "text": "ok"}), result)):  # 没有报错
        assert kh.audit_claude_stream(stream(INIT, *events), SPEC)["rate_limited_until"] is None


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
    # 第 20 轮：落地之后顺手提交本主任务的复审记录，只提交这几个路径
    assert kh.git(["rev-parse", "HEAD~1"], repo).strip() == oracle and ts["oracle"]["landed_at"]
    assert kh.git(["show", "--name-only", "--format=", "HEAD"], repo).split() == [
        ".agent/reviews/t001-doc/%s-hub.md" % run_dir.name]
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
    monkeypatch.setattr(kh, "rework_added_files", lambda hub, ts: [])  # 返工基线里新增的文件另有测试
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


def test_rework_contract_lets_the_executor_modify_files_added_earlier(tmp_path, monkeypatch):
    # T004：返工基线里已经有 attempt-001 新增的 Tooltip.tsx，attempt-002 改它修阻塞项，状态是 M，
    # 合同却只“允许新增”：范围门禁判越界，用掉一次 attempt（第 18 轮）
    repo, head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    ts = locked(kh.new_task_state("T001", "doc", "改文档", head, True))
    ts["oracle"]["sha"] = head
    (repo / "src").mkdir()
    for name in ("新.ts", "keep.ts"):
        (repo / "src" / name).write_text("x\n", encoding="utf-8")
    (repo / "README.md").write_text("改\n", encoding="utf-8")
    kh.git(["add", "-A"], repo)
    kh.git(["commit", "-q", "-m", "rework"], repo)
    rework = kh.git(["rev-parse", "HEAD"], repo).strip()
    ts["rework_chain"] = [{"from": "attempt-001", "commit": rework, "contract": "t001-doc.v1"}]
    plans = repo / ".agent" / "plans"
    plans.mkdir(parents=True)
    v1 = ("# TASK: t001-doc\n\n## Identity\n- plan_version: 1\n- base_sha: %s\n\n## Scope\n"
          "- allowed_modified_files:\n  - README.md\n  - src/keep.ts\n- allowed_new_files:\n  - src/*.ts\n"
          "- forbidden_paths: 无\n\n## Rework（返工第 1 轮，内核追加）\n\n- B1\n" % rework)
    (plans / "t001-doc.v1.md").write_text(v1, encoding="utf-8")
    (plans / "t001-doc.v1.json").write_text(json.dumps({"budget": {
        "max_attempts_total": 3, "max_wall_seconds_per_attempt": 3600, "max_wall_seconds_total": 10800}}),
        encoding="utf-8")
    ts["contract"]["dispatched"] = True
    ts["exec"], ts["audit_post"] = {"run_dir": None}, {}  # 检查没过之后的返工：没有终审结论，照合同重派
    calls = []

    def fake_pd(hub, args, timeout=600):
        calls.append(args[0] if args[0] != "prepare" else "prepare " + args[1])
        return (9, "prepare 停在这里") if args[0] == "prepare" else (0, "ok")

    monkeypatch.setattr(kh, "run_pd", fake_pd)
    monkeypatch.setattr(kh, "contract_requirements", lambda hub, ts: [])
    kh.run_exec(hub, ts)
    assert calls == ["derive-json", "validate", "prepare t001-doc.v2"]
    v2 = (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    scope = kh.pd._md_scope_lists(v2)
    assert scope["allowed_modified_files"] == ["README.md", "src/keep.ts", "src/新.ts"]
    assert scope["allowed_new_files"] == ["src/*.ts"] and "- plan_version: 2" in v2 and "## Rework" in v2
    assert (plans / "t001-doc.v1.md").read_text(encoding="utf-8") == v1  # 派遣过的版本不改
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert [e["files"] for e in events if e["event"] == "contract.scope_widened"] == [["src/新.ts"]]
    calls.clear()
    kh.run_exec(hub, ts)  # 范围已经齐了：不再出新版本
    assert calls == ["prepare t001-doc.v2"]
    # 还没派遣的版本就地补上，不出新版本
    (plans / "t001-doc.v2.md").write_text(v2.replace("  - src/新.ts\n", ""), encoding="utf-8")
    calls.clear()
    assert kh.ensure_rework_scope(hub, ts) == [] and calls == ["derive-json", "validate"]
    assert "  - src/新.ts\n" in (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    assert not (plans / "t001-doc.v3.md").exists()
    # 读不出返工基线：如实报告，不派遣
    ts["rework_chain"][-1]["commit"] = "f" * 40
    calls.clear()
    fields = kh.run_exec(hub, ts)
    assert calls == [] and "读不出返工基线" in fields["验证"] and ts["exec"]["run_dir"] is None


def test_add_modified_files_handles_both_list_forms():
    text, problems = kh.add_modified_files(
        "## Scope\n- allowed_modified_files: 无\n- allowed_new_files: a.ts\n\n## DoD\n- x\n", ["a.ts"])
    assert problems == [] and kh.pd._md_scope_lists(text)["allowed_modified_files"] == ["a.ts"]
    assert kh.pd._md_scope_lists(text)["allowed_new_files"] == ["a.ts"] and text.endswith("## DoD\n- x\n")
    text, _ = kh.add_modified_files("## Scope\n- allowed_modified_files: `b.ts`, c.ts\n", ["a.ts", "c.ts"])
    assert kh.pd._md_scope_lists(text)["allowed_modified_files"] == ["b.ts", "c.ts", "a.ts"]
    assert kh.add_modified_files("## Goal\n- allowed_modified_files: a\n", ["b"])[1]  # 没有 Scope 一节
    assert kh.add_modified_files("## Scope\n- allowed_new_files: a\n", ["a"])[1]


def failed_checks(run_dir: Path, ids=("V01",), log_lines=60) -> None:
    """一次没过的 check --fresh：checks/01 是 run 自己跑的，checks/02 是内核的复核。"""
    for number, status in (("01", "passed"), ("02", "failed")):
        folder = run_dir / "checks" / number
        folder.mkdir(parents=True)
        results = [{"id": "V09", "status": "passed", "log": "%s/V09.log" % number}]
        for cid in ids:
            results.append({"id": cid, "status": status, "reason": "退出码 1 ≠ 期望 0", "log": "%s/%s.log" % (number, cid)})
            body = ["第 %d 行 %s %s" % (i, number, cid) for i in range(log_lines)] + ["FAILED tests/x.py::test_%s" % cid]
            (folder / ("%s.log" % cid)).write_text("\n".join(body) + "\n", encoding="utf-8")
        (folder / "checks.json").write_text(json.dumps({"results": results}), encoding="utf-8")


def test_retry_after_failed_checks_tells_the_executor_why(tmp_path, monkeypatch):
    # 检查没过之后重派同一份合同：执行端只读合同，协调人的信到不了它，等于盲目重来（第 19 轮）
    repo, hub, ts, plans, previous = rework_setup(tmp_path)
    v1 = (plans / "t001-doc.v1.md").read_text(encoding="utf-8")
    failed_checks(previous)
    (previous / "scope.json").write_text(json.dumps({"violations": [
        {"path": "src/外面.ts", "kind": "out_of_scope", "detail": "状态 M 不在允许集合"}]}), encoding="utf-8")
    (previous / "executor-report.json").write_text(json.dumps({"executor_status": "DONE"}), encoding="utf-8")
    failed = {"run_dir": str(previous), "check_ok": False, "check_exit": 1, "scope_violations": 1,
              "status": "NEEDS_REVIEW"}
    ts["exec"], ts["audit_post"] = dict(failed), {}
    calls = []

    def fake_pd(hub, args, timeout=600):
        calls.append(args[0] if args[0] != "prepare" else "prepare " + args[1])
        return (9, "prepare 停在这里") if args[0] == "prepare" else (0, "ok")

    monkeypatch.setattr(kh, "run_pd", fake_pd)
    monkeypatch.setattr(kh, "contract_requirements", lambda hub, ts: [])
    kh.run_exec(hub, ts)
    assert calls == ["derive-json", "validate", "prepare t001-doc.v2"]
    v2 = (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    assert "- plan_version: 2" in v2 and "## Retry（重派第 1 次，内核追加）" in v2
    assert "上一轮 attempt-001 没过内核核验：check --fresh 退出码 1，范围违规 1 条" in v2 and "执行端自述 DONE" in v2
    assert "- V01：退出码 1 ≠ 期望 0" in v2 and "    FAILED tests/x.py::test_V01" in v2
    assert "第 59 行 02 V01" in v2 and "第 20 行 02 V01" not in v2 and " 01 V01" not in v2  # 最近一次 check 的末尾
    assert "V09" not in v2 and "- `src/外面.ts`：out_of_scope（状态 M 不在允许集合）" in v2
    assert (plans / "t001-doc.v1.md").read_text(encoding="utf-8") == v1 and ts["retry_notes"] == ["attempt-001"]
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert [e["previous"] for e in events if e["event"] == "exec.retry_noted"] == ["attempt-001"]
    # 同一个 attempt 只写一次；检查通过了、或者状态里没有结论的，都不写
    for state in (dict(failed), dict(failed, check_ok=True), {"run_dir": str(previous)}):
        ts["exec"] = state
        calls.clear()
        kh.run_exec(hub, ts)
        assert calls == ["prepare t001-doc.v2"]
    # 下一个没过的 attempt，合同还没派遣：就地追加，不出新版本；没过的检查多于 3 条时只附前 3 条
    second = previous.parent / "attempt-002"
    failed_checks(second, ids=("V01", "V02", "V03", "V04"), log_lines=5)
    ts["exec"] = dict(failed, run_dir=str(second), scope_violations=0)
    calls.clear()
    kh.run_exec(hub, ts)
    assert calls == ["derive-json", "validate", "prepare t001-doc.v2"] and not (plans / "t001-doc.v3.md").exists()
    v2 = (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    assert "## Retry（重派第 2 次，内核追加）" in v2 and "- V03：" in v2 and "- V04：" not in v2
    assert "另有 1 条检查没过" in v2 and ts["retry_notes"] == ["attempt-001", "attempt-002"]
    # 新版本建不出来：如实报告，不派遣
    third = previous.parent / "attempt-003"
    failed_checks(third)
    ts["exec"], ts["contract"]["dispatched"] = dict(failed, run_dir=str(third)), True
    (plans / "t001-doc.v3.md").write_text("占住\n", encoding="utf-8")
    calls.clear()
    fields = kh.run_exec(hub, ts)
    assert calls == [] and "重派合同没有建成" in fields["验证"] and "已存在" in fields["验证"]


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
    assert kh.git(["rev-parse", "HEAD~1"], repo).strip() == rework and ts["rework_chain"][0]["landed_by"] == "ff"
    assert "regression" not in ts  # 分支在任务期间没动：integrate 的检查就够了，不跑合入后回归
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


def forked_landing_setup(tmp_path, monkeypatch):
    """任务期间分支前进了：结项要把基准测试与返工提交挑到末端，再 integrate（integrate 的结果由 outcome 决定）。"""
    repo, head = git_repo(tmp_path)
    branch = kh.git(["rev-parse", "--abbrev-ref", "HEAD"], repo).strip()
    kh.git(["checkout", "-q", "-b", "chain"], repo)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_gate_t001_baseline.py").write_text("def test_x():\n    assert '宽'\n", encoding="utf-8")
    kh.git(["add", "tests"], repo)
    kh.git(["commit", "-q", "-m", "门禁端基准测试"], repo)
    oracle = kh.git(["rev-parse", "HEAD"], repo).strip()
    (repo / "earlier.txt").write_text("上一轮的候选\n", encoding="utf-8")
    kh.git(["add", "earlier.txt"], repo)
    kh.git(["commit", "-q", "-m", "返工提交"], repo)
    rework = kh.git(["rev-parse", "HEAD"], repo).strip()
    kh.git(["checkout", "-q", branch], repo)
    (repo / "viewer.txt").write_text("并行主任务先落地的组件\n", encoding="utf-8")
    kh.git(["add", "viewer.txt"], repo)
    kh.git(["commit", "-q", "-m", "并行主任务先落地"], repo)
    fork = kh.git(["rev-parse", "HEAD"], repo).strip()
    outcome = {"integrate": 1, "during": None}
    calls = []

    def fake_pd(hub, args, timeout=600):
        calls.append(args[0])
        if args[0] == "verdict":
            (run_dir / "state.json").write_text(json.dumps({"state": "PASS"}), encoding="utf-8")
        if args[0] == "integrate" and outcome["during"]:
            outcome["during"]()
        return (outcome["integrate"], "CHECK V01 failed") if args[0] == "integrate" else (0, "ok")

    monkeypatch.setattr(kh, "run_pd", fake_pd)
    hub = kh.Hub(repo)
    hub.ensure()
    run_dir = attempt_dir(hub, {"state": "NEEDS_REVIEW"})
    ts = locked(kh.new_task_state("T001", "doc", "改文档", head, True))
    ts["oracle"].update(sha=oracle, files=["tests/test_gate_t001_baseline.py"])
    ts["rework_chain"] = [{"from": "attempt-001", "commit": rework, "contract": "t001-doc.v2"}]
    ts["exec"] = {"run_dir": str(run_dir), "check_exit": 0, "scope_violations": 0, "check_ok": True}
    return repo, hub, ts, fork, outcome, calls


def test_failed_integrate_takes_the_landed_commits_back_off_the_branch(tmp_path, monkeypatch):
    repo, hub, ts, fork, outcome, calls = forked_landing_setup(tmp_path, monkeypatch)
    (repo / "README.md").write_text("站主改了一半、没提交\n", encoding="utf-8")
    (repo / "notes.txt").write_text("无关的未提交文件\n", encoding="utf-8")
    ok, detail = kh.finalize(hub, ts)
    # 第 29 轮（T006）：integrate 没过，挑上去的基准测试与返工提交不能留在分支上
    assert not ok and calls == ["verdict", "integrate"]
    assert kh.git(["rev-parse", "HEAD"], repo).strip() == fork
    assert not (repo / "earlier.txt").exists() and not (repo / "tests" / "test_gate_t001_baseline.py").exists()
    assert "landed_at" not in ts["oracle"] and "landed_at" not in ts["rework_chain"][0]
    assert "已把这次带上分支的基准测试与返工提交撤回" in detail and fork[:12] in detail
    # 候选 check 通过过、分支在任务期间前进了：列出先落地的提交，站主好找冲突
    assert "先落地了这些提交" in detail and "并行主任务先落地" in detail
    assert (repo / "README.md").read_text(encoding="utf-8") == "站主改了一半、没提交\n"
    assert (repo / "notes.txt").is_file()
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert [e for e in events if e["event"] == "landing.undone"][-1]["back_to"] == fork
    # 修好之后重试：重新挑上去，integrate 落地
    outcome["integrate"] = 0
    calls.clear()
    ok, _detail = kh.finalize(hub, ts)
    assert ok and calls == ["integrate"] and (repo / "earlier.txt").is_file()
    assert ts["oracle"]["landed_by"] == "cherry-pick" and ts["rework_chain"][0]["landed_by"] == "cherry-pick"


def test_a_rework_commit_that_cannot_land_takes_the_oracle_back_off_too(tmp_path, monkeypatch):
    repo, hub, ts, fork, _outcome, calls = forked_landing_setup(tmp_path, monkeypatch)
    (repo / "earlier.txt").write_text("末端上同名不同内容\n", encoding="utf-8")
    kh.git(["add", "earlier.txt"], repo)
    kh.git(["commit", "-q", "-m", "同名不同内容"], repo)
    tip = kh.git(["rev-parse", "HEAD"], repo).strip()
    ok, detail = kh.finalize(hub, ts)
    assert not ok and "返工提交" in detail and calls == ["verdict"]
    assert kh.git(["rev-parse", "HEAD"], repo).strip() == tip and "landed_at" not in ts["oracle"]
    assert not (repo / "tests" / "test_gate_t001_baseline.py").exists()


def test_failed_integrate_names_the_meanwhile_commits_only_when_the_candidate_had_passed(tmp_path, monkeypatch):
    repo, hub, ts, fork, outcome, _calls = forked_landing_setup(tmp_path, monkeypatch)
    ts["exec"]["check_ok"] = False
    ok, detail = kh.finalize(hub, ts)
    assert not ok and "先落地了这些提交" not in detail and "已把这次带上分支" in detail
    ts["exec"]["check_ok"] = True
    ts["base_head"] = fork  # 任务期间分支没动：检查没过就是候选自己的问题，不列提交
    ok, detail = kh.finalize(hub, ts)
    assert not ok and "先落地了这些提交" not in detail
    assert kh.landed_meanwhile(hub, dict(ts, base_head=fork), fork) == ""


def test_landing_is_not_undone_when_the_branch_moved_elsewhere_or_local_edits_block_it(tmp_path, monkeypatch):
    repo, hub, ts, fork, outcome, _calls = forked_landing_setup(tmp_path, monkeypatch)
    base = kh.git(["rev-parse", "HEAD~1"], repo).strip()
    # integrate 期间分支被挪到了别处：结项开始时的末端不再是祖先，不能 reset 过去
    outcome["during"] = lambda: kh.git(["reset", "-q", "--hard", base], repo)
    ok, detail = kh.finalize(hub, ts)
    assert not ok and "没有撤回" in detail and kh.git(["rev-parse", "HEAD"], repo).strip() == base
    assert ts["oracle"].get("landed_at")  # 没撤回：记录照旧
    # 记录说落地过、分支上却没有：重试时照样重新挑上去，不信 landed_at
    outcome.update(integrate=0, during=None)
    assert kh.finalize(hub, ts)[0] and (repo / "earlier.txt").is_file()
    assert (repo / "tests" / "test_gate_t001_baseline.py").is_file()
    outcome["integrate"] = 1
    # 挑上去的文件被改了没提交：reset --keep 拒绝，不丢站主的改动
    kh.git(["reset", "-q", "--hard", fork], repo)
    for record in kh.landing_records(ts):
        record.pop("landed_at", None)
        record.pop("landed_by", None)

    def edit_landed():
        (repo / "earlier.txt").write_text("站主手上的改动\n", encoding="utf-8")

    outcome["during"] = edit_landed
    ok, detail = kh.finalize(hub, ts)
    assert not ok and "没能撤回" in detail
    assert (repo / "earlier.txt").read_text(encoding="utf-8") == "站主手上的改动\n"
    assert kh.git(["rev-parse", "HEAD"], repo).strip() != fork


def test_retrying_finalize_does_not_pick_a_gate_the_owner_narrowed_again(tmp_path, monkeypatch):
    repo, hub, ts, fork, outcome, calls = forked_landing_setup(tmp_path, monkeypatch)
    outcome["integrate"] = 0
    assert kh.finalize(hub, ts)[0]
    # 落地前站主在分支上收窄了基准测试里的断言（T006：陈列页的 aria-pressed）；再结项时它已经在分支上了
    gate = repo / "tests" / "test_gate_t001_baseline.py"
    gate.write_text("def test_x():\n    assert '窄'\n", encoding="utf-8")
    kh.git(["commit", "-q", "-am", "站主收窄门禁断言"], repo)
    tip = kh.git(["rev-parse", "HEAD"], repo).strip()
    for record in kh.landing_records(ts):
        record.pop("landed_at", None)
    calls.clear()
    ok, detail = kh.finalize(hub, ts)
    assert ok and calls == ["integrate"], detail
    assert gate.read_text(encoding="utf-8") == "def test_x():\n    assert '窄'\n"
    assert kh.git(["rev-parse", "HEAD"], repo).strip() == tip
    assert kh.on_branch(hub, ts["oracle"]["sha"]) and kh.on_branch(hub, ts["rework_chain"][0]["commit"])
    assert not kh.on_branch(hub, "0" * 40)


def test_owner_takeover_closes_the_task(tmp_path, monkeypatch):
    import io
    repo, head = git_repo(tmp_path)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    hub = kh.Hub(repo)
    hub.ensure()
    roots = tmp_path / "worktrees"
    roots.mkdir()
    monkeypatch.setattr(kh, "worktree_root", lambda repo_path: roots)
    state = hub.load_state()
    state["tasks"]["T001"] = kh.new_task_state("T001", "doc", "改文档", head, True)
    gate = kh.ensure_worktree(hub, state["tasks"]["T001"], "gate", head)
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
    assert not gate.exists() and ts["workspaces"]["gate"]["removed_at"]  # 结项清掉阶段 worktree（第 12 轮）
    assert "V01 75 passed" in (repo / ts["closed_by_owner"]["note"]).read_text(encoding="utf-8")
    assert "站主接手结项：%s" % head[:12] in kh.stage_status_table(hub, ts)
    assert "已结项" in kh.guard(ts, meta("开工", "exec-step", "T001-5-exec"))
    with pytest.raises(kh.HubError):
        close("HEAD")  # 不能结项两次
    events = [json.loads(line)["event"] for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert "task.closed_by_owner" in events


def test_finished_tasks_remove_their_stage_worktrees(tmp_path, monkeypatch):
    # T001–T003 结项之后留下 10 个阶段 worktree，T001、T002 的 attempt-001 一直停在 NEEDS_REVIEW；
    # 证据已经存进信箱，结项时收尾（第 12 轮）
    import io
    repo, head = git_repo(tmp_path)
    roots = tmp_path / "worktrees"
    roots.mkdir()
    monkeypatch.setattr(kh, "worktree_root", lambda repo_path: roots)
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(kh, "finalize", lambda hub, ts: (True, "integrate ok"))
    pd_calls = []

    def fake_pd(hub, args, timeout=600):
        pd_calls.append(list(args))
        if args[0] == "mark":
            (Path(args[1]) / "state.json").write_text(json.dumps({"state": args[2]}), encoding="utf-8")
        elif args[0] == "cleanup":
            Path(json.loads((Path(args[1]) / "meta.json").read_text(encoding="utf-8"))["worktree"]).rmdir()
        return 0, "ok"

    monkeypatch.setattr(kh, "run_pd", fake_pd)
    hub = kh.Hub(repo)
    hub.ensure()
    runs = repo / ".agent" / "runs" / "t001-doc"
    attempts = {}
    for name, attempt_state in (("attempt-001", "NEEDS_REVIEW"), ("attempt-002", "INTEGRATED"),
                                ("attempt-003", "RUNNING")):
        run_dir = attempts[name] = runs / name
        run_dir.mkdir(parents=True)
        (run_dir / "state.json").write_text(json.dumps({"state": attempt_state}), encoding="utf-8")
        (run_dir / "meta.json").write_text(json.dumps({"worktree": str(tmp_path / ("wt-" + name))}), encoding="utf-8")
    (tmp_path / "wt-attempt-001").mkdir()  # attempt-002 的 worktree 已由 integrate 删掉
    state = hub.load_state()
    ts = state["tasks"]["T001"] = kh.new_task_state("T001", "doc", "改文档", head, True)
    ts["exec"] = {"run_dir": str(attempts["attempt-002"])}
    gate = kh.ensure_worktree(hub, ts, "gate", head)
    post = kh.ensure_worktree(hub, ts, "post-attempt-001", head)
    (post / "node_modules").mkdir()
    (post / "node_modules" / "x.js").write_text("// 战后门禁装的依赖，未跟踪\n", encoding="utf-8")
    stray = roots / "not-a-worktree"
    stray.mkdir()
    ts["workspaces"]["base"] = {"path": str(stray), "commit": head}
    kh.Engine(hub, FakeRunner([])).handle_pass(state, meta("通过", "exec-step", "T001-5-exec"))
    assert ts["status"] == "done" and not gate.exists() and not post.exists() and stray.is_dir()
    assert ts["workspaces"]["gate"]["removed_at"] and "removed_at" not in ts["workspaces"]["base"]
    letter = hub.unread(kh.OWNER)[0].read_text(encoding="utf-8")
    assert "已 integrate" in letter and "结项收尾没做完" in letter and "not-a-worktree" in letter
    assert "attempt-003 还处在 RUNNING" in letter
    removed = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert sorted(e["kind"] for e in removed if e["event"] == "workspace.removed") == ["gate", "post-attempt-001"]
    # 没有结论的 attempt 记成 ABANDONED 再清 worktree；已合入的、还在跑的不动
    first = str(attempts["attempt-001"])
    assert [c[:3] for c in pd_calls] == [["mark", first, "ABANDONED"], ["cleanup", first]]
    assert "T001 已由 hub 结项（attempt-002 通过并合入）" in pd_calls[0][pd_calls[0].index("--reason") + 1]
    assert kh.pd.get_state(attempts["attempt-002"]) == "INTEGRATED" and not (tmp_path / "wt-attempt-001").exists()
    parser = kh.build_parser()

    def cleanup(task):
        args = parser.parse_args(["--repo", str(repo), "task", "cleanup", task])
        return args.func(args)

    pd_calls.clear()
    assert cleanup("T001") == kh.EXIT_FAIL and pd_calls == []  # 删不掉的如实报告；收尾过的不再动
    (attempts["attempt-003"] / "state.json").write_text(json.dumps({"state": "CANCELLED"}), encoding="utf-8")
    assert cleanup("T001") == kh.EXIT_FAIL  # 还剩不是 worktree 的目录
    stray.rmdir()  # 目录已经不在：记成清理过
    assert cleanup("T001") == kh.EXIT_OK and hub.load_state()["tasks"]["T001"]["workspaces"]["base"]["removed_at"]
    state = hub.load_state()
    state["tasks"]["T002"] = kh.new_task_state("T002", "web", "前端", head, True)
    hub.save_state(state)
    with pytest.raises(kh.HubError):
        cleanup("T002")  # 进行中的主任务还要用这些 worktree
    # 调度器拒绝标记：如实报告，也不去删它的 worktree
    monkeypatch.setattr(kh, "run_pd", lambda hub, args, timeout=600: pd_calls.append(list(args)) or (1, "ERROR 拒绝"))
    (attempts["attempt-001"] / "state.json").write_text(json.dumps({"state": "NEEDS_REVIEW"}), encoding="utf-8")
    (tmp_path / "wt-attempt-001").mkdir()
    pd_calls.clear()
    assert kh.retire_attempts(hub, ts, "收尾") == ["attempt-001 没能记成 ABANDONED：ERROR 拒绝"]
    assert [c[0] for c in pd_calls] == ["mark"]


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
    assert kh.ROSTER[kh.COORDINATOR]["thinking"] == "high"


def test_only_the_planner_stays_on_claude():
    # 第 36 轮（用户 2026-10-21）：最重要的岗位 Opus 5.5 max，第二重要的 GLM-5.3，其余换到 pi 上
    on = {name: (spec["adapter"], spec.get("provider"), spec["model"]) for name, spec in kh.ROSTER.items()
          if spec["adapter"] in ("claude", "pi", "dispatcher")}
    assert on == {
        kh.COORDINATOR: ("pi", "token", "qwen3.7-plus"),
        "planner-opus": ("claude", None, "claude-opus-5-5"),
        "contract-glm": ("pi", "cc-switch-zhipu-glm", "glm-5.3"),  # 第 46 轮：qwen 写合同接连出错
        "gate-sonnet": ("pi", "bb", "step-5-preview"),
        "audit-sonnet": ("pi", "cc-switch-zhipu-glm", "glm-5.3"),
        "exec-step": ("dispatcher", "bb", "step-5-preview")}
    assert kh.ROSTER["planner-opus"]["effort"] == "max" and kh.ROSTER["audit-sonnet"]["thinking"] == "max"
    assert kh.CONTRACT_EXECUTOR_LINE == "- executor: bb/step-5-preview · thinking high"


def test_invalid_output_gets_one_retry(engine_env):
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([({"letters": [start_planner()]}, []), (None, []), (planner_delivery(), [])])
    engine = kh.Engine(hub, runner)
    engine.step()
    engine.step()
    assert len(runner.calls) == 3 and "上一次输出没有通过内核校验" in runner.calls[2][2]
    assert hub.load_state()["tasks"]["T001"]["stages"]["1-plan"]["status"] == "delivered"


def test_a_timed_out_turn_does_not_use_up_the_format_retry(engine_env):
    # 第 32 轮：T010 的规划第一回合超时，续上的回合 JSON 写错，没机会再改
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([({"letters": [start_planner()]}, []), (None, [], None, True), (None, []),
                         (planner_delivery(), [])])
    engine = kh.Engine(hub, runner)
    engine.step()
    engine.step()
    assert len(runner.calls) == 4 and "上一次输出没有通过内核校验" in runner.calls[3][2]
    assert hub.load_state()["tasks"]["T001"]["stages"]["1-plan"]["status"] == "delivered"


@pytest.mark.parametrize("planner_turns", [
    [(None, []), (None, [])],  # 没有超时：输出不合格只重试一次
    [(None, [], None, True), (None, [], None, True), (None, [], None, True)],  # 一直超时：最多重试两次
    [(None, ["写了工作目录以外的文件"], None, True)],  # 越界的回合不重试，超时也一样
])
def test_worker_retries_stop_when_the_output_stays_invalid(engine_env, planner_turns):
    hub = engine_env
    owner_task(hub)
    runner = FakeRunner([({"letters": [start_planner()]}, [])] + planner_turns + [(planner_delivery(), [])])
    engine = kh.Engine(hub, runner)
    engine.step()
    engine.step()
    assert len(runner.calls) == 1 + len(planner_turns)
    assert hub.load_state()["tasks"]["T001"]["stages"]["1-plan"]["status"] == "failed"


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


def test_turn_cost_is_this_turn_not_the_session_total(tmp_path):
    # 第 16 轮：claude -p --resume 回报会话累计的花费，T001 协调人 20 个回合从 0.04 涨到 2.17，按回合加总多算十倍
    hub = kh.Hub(tmp_path)
    hub.ensure()
    totals = iter([0.10, 0.25, 0.27, 0.05])

    def launcher(cmd, cwd, env, out, err, timeout):
        init = dict(INIT, tools=kh.ROSTER["planner-opus"]["tools"], model=kh.ROSTER["planner-opus"]["model"])
        result = {"type": "result", "result": "```json\n{\"letters\": []}\n```", "total_cost_usd": next(totals)}
        out.write(("\n".join(stream(init, result)) + "\n").encode("utf-8"))
        return {"exit_code": 0, "timed_out": False, "wall_seconds": 2.5}

    runner = kh.TurnRunner(hub, launcher=launcher)
    turns = [runner.run("planner-opus", "T001-1-plan", tmp_path, "角色", "输入", fresh=fresh)
             for fresh in (False, False, False, True)]
    assert [t["cost_usd"] for t in turns] == [0.10, 0.15, 0.02, 0.05]  # 会话重开之后从头计
    assert [t["session_cost_usd"] for t in turns] == [0.10, 0.25, 0.27, 0.05]
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    finished = [e for e in events if e["event"] == "turn.finished"]
    assert [e["cost_usd"] for e in finished] == [0.10, 0.15, 0.02, 0.05] and finished[0]["wall_seconds"] == 2.5
    assert kh.turn_cost_usd("claude", {"cost_usd_total": 0.3}, 0.1) == (0.1, 0.1)  # 累计值变小：当它是这一回合的
    assert kh.turn_cost_usd("pi", {"cost_usd_total": 0.3}, 0.4) == (0.4, None)  # pi 的回报原样记
    assert kh.turn_cost_usd("claude", {}, None) == (None, None)


def test_metrics_reports_per_turn_costs_and_converts_legacy_session_totals(tmp_path, monkeypatch):
    import io
    repo, _head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()

    def record(agent, turn_id, session_key, session_id, cost, seconds, **extra):
        turn = hub.root / "turns" / agent / turn_id
        turn.mkdir(parents=True)
        data = dict({"turn_id": turn_id, "agent": agent, "session_key": session_key, "session_id": session_id,
                     "cost_usd": cost, "wall_seconds": seconds}, **extra)
        (turn / "result.json").write_text(json.dumps(data), encoding="utf-8")

    # 第 16 轮之前：claude 工人的 cost_usd 是会话累计值（倒序写入，按 turn_id 排）
    record("womovie-c8", "20261019T010300Z-c", "T001", "s1", 0.27, 60)
    record("womovie-c8", "20261019T010100Z-a", "T001", "s1", 0.10, 60)
    record("womovie-c8", "20261019T010200Z-b", "T001", "s1", 0.25, 60)
    record("audit-sonnet", "20261019T020000Z-d", "T001-4-audit-pre", "s2", 4.0, 600)
    record("contract-glm", "20261019T020500Z-e", "T001-2-contract", "T001-2-contract-g0", None, 300)
    # 第 16 轮之后：cost_usd 已经是这一回合的
    record("womovie-c8", "20261019T030000Z-f", "T002", "s3", 0.02, 30, session_cost_usd=0.02)
    record("womovie-c8", "20261019T030100Z-g", "T002", "s3", 0.05, 30, session_cost_usd=0.07)  # 新记录不再换算
    rows = kh.turn_metrics(hub)
    assert [(r["agent"], r["cost_usd"]) for r in rows] == [
        ("womovie-c8", 0.10), ("womovie-c8", 0.15), ("womovie-c8", 0.02), ("audit-sonnet", 4.0),
        ("contract-glm", None), ("womovie-c8", 0.02), ("womovie-c8", 0.05)]
    assert [r["task"] for r in rows] == ["T001"] * 5 + ["T002"] * 2
    for event, at in (("exec.started", "2026-10-19T04:00:00Z"), ("exec.finished", "2026-10-19T04:30:00Z")):
        hub.append_event(event, task="T001", run_dir="r1", at_override=at)
    lines = hub.ledger().read_text(encoding="utf-8").splitlines()
    fixed = []
    for line in lines:  # append_event 自己写 at：改成固定时刻
        event = json.loads(line)
        event["at"] = event.pop("at_override")
        fixed.append(json.dumps(event))
    hub.ledger().write_text("\n".join(fixed) + "\n", encoding="utf-8")
    assert kh.exec_metrics(hub) == {"T001": {"attempts": 1, "seconds": 1800.0}}
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    parser = kh.build_parser()
    args = parser.parse_args(["--repo", str(repo), "metrics"])
    assert args.func(args) == kh.EXIT_OK
    text = out.getvalue()
    assert "| womovie-c8 | 3 | 3.0 | 0.27 |" in text and "| contract-glm | 1 | 5.0 | 未回报 |" in text
    assert "| 执行端（调度器 run） | 1 个 attempt | 30.0 |" in text
    assert "工人回合合计：7 个" in text and "4.34 美元" in text


#: 第 36 轮之前门禁端、审核端在 claude 上的规格。claude 的这条路照旧保留（换回来时用），按原来的规格测
CLAUDE_GATE = {"role": "gate", "adapter": "claude", "model": "claude-sonnet-5-5", "effort": "high",
               "tools": ["Read", "Grep", "Glob", "Edit", "Write", "Bash"], "allowed_rules": ["Bash(python -m pytest:*)"],
               "timeout": 2400, "workspace": "stage"}
CLAUDE_AUDIT = {"role": "audit", "adapter": "claude", "model": "claude-sonnet-5-5", "effort": "max",
                "tools": ["Read", "Grep", "Glob"], "timeout": 2400, "workspace": "stage"}


def test_claude_workers_read_the_main_repo_and_write_only_their_worktree(tmp_path, monkeypatch):
    monkeypatch.setitem(kh.ROSTER, "gate-sonnet", CLAUDE_GATE)
    monkeypatch.setitem(kh.ROSTER, "audit-sonnet", CLAUDE_AUDIT)
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


# ---------------------------------------------------------------------------
# 第 20 轮：几个主任务并行（每个主任务一个 runner 进程）
# ---------------------------------------------------------------------------

def two_task_hub(tmp_path):
    hub = kh.Hub(tmp_path)
    hub.ensure()
    hub.save_state({"tasks": {"T001": make_ts(), "T002": kh.new_task_state("T002", "x", "另一片", BASE, True)}})
    return hub


def test_state_saves_merge_by_task_and_key(tmp_path):
    hub = two_task_hub(tmp_path)
    mine, theirs = hub.load_state(), hub.load_state()
    mine["tasks"]["T001"]["notes"] = ["T001 的 runner 写的"]
    theirs["tasks"]["T002"]["notes"] = ["T002 的 runner 写的"]
    theirs["tasks"]["T001"]["owner_rework"] = {"suffix": "2-contract"}  # 站主的 send 改了 T001 的另一个键
    hub.save_state(theirs)
    hub.save_state(mine)  # 整份覆盖会把上面两处冲掉
    disk = hub.load_state()["tasks"]
    assert disk["T001"]["notes"] == ["T001 的 runner 写的"] and disk["T002"]["notes"] == ["T002 的 runner 写的"]
    assert disk["T001"]["owner_rework"] == {"suffix": "2-contract"}
    # 再存一次：没动的键仍以读出来时为准，不拿过时的值盖掉别人后写的
    mine["tasks"]["T001"]["status"] = "done"
    hub.save_state(mine)
    disk = hub.load_state()["tasks"]
    assert disk["T001"]["owner_rework"] == {"suffix": "2-contract"} and disk["T002"]["notes"] == ["T002 的 runner 写的"]
    assert disk["T001"]["status"] == "done"
    # 两边改了同一个键：以后存的为准，记一条冲突；删掉的键照删
    first, second = hub.load_state(), hub.load_state()
    first["tasks"]["T001"]["notes"] = ["先"]
    second["tasks"]["T001"]["notes"] = ["后"]
    del second["tasks"]["T001"]["owner_rework"]
    hub.save_state(first)
    hub.save_state(second)
    disk = hub.load_state()["tasks"]["T001"]
    assert disk["notes"] == ["后"] and "owner_rework" not in disk
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert [e["key"] for e in events if e["event"] == "state.conflict"] == ["notes"]
    # 新登记的主任务整个写进去；手搭的 dict 照旧整份写
    later = hub.load_state()
    later["tasks"]["T003"] = kh.new_task_state("T003", "y", "第三片", BASE, False)
    hub.save_state(later)
    assert set(hub.load_state()["tasks"]) == {"T001", "T002", "T003"}
    hub.save_state({"tasks": {"T009": make_ts()}})
    assert set(hub.load_state()["tasks"]) == {"T009"}


def test_turn_end_keeps_the_sessions_other_tasks_wrote(tmp_path):
    hub = kh.Hub(tmp_path)
    hub.ensure()
    hub.save_agent_record("gate-sonnet", {"name": "gate-sonnet", "sessions": {"T001": {"id": "a", "turns": 3}}})
    hub.save_agent_session("gate-sonnet", "T002", {"id": "b", "turns": 1})
    hub.save_agent_session("gate-sonnet", "T001", {"id": "a", "turns": 4})
    record = hub.agent_record("gate-sonnet")
    assert record["sessions"] == {"T001": {"id": "a", "turns": 4}, "T002": {"id": "b", "turns": 1}}
    assert record["last_turn_at"]


def test_file_lock_keeps_other_holders_out(tmp_path):
    import threading
    path = tmp_path / ".x.lock"
    entered, release, outcome = threading.Event(), threading.Event(), {}

    def holder():
        with kh.file_lock(path):
            entered.set()
            release.wait(10)

    thread = threading.Thread(target=holder)
    thread.start()
    assert entered.wait(10)
    try:
        with kh.file_lock(path, wait_seconds=0.2):
            outcome["got"] = True
    except kh.HubError as exc:
        outcome["error"] = str(exc)
    release.set()
    thread.join(10)
    assert "等文件锁超时" in outcome.get("error", "")
    with kh.file_lock(path, wait_seconds=1.0):  # 持有者放开之后拿得到
        pass


def test_task_runner_only_takes_its_own_task_letters(tmp_path):
    hub = two_task_hub(tmp_path)
    for task in ("T001-1-plan", "T002-1-plan"):
        hub.deliver({"from": kh.COORDINATOR, "to": "planner-opus", "task-id": task, "in-reply-to": "none",
                     "type": "开工"}, fields())
    agent, paths = kh.Engine(hub, FakeRunner([]), only_task="T002").next_job()
    assert agent == "planner-opus" and [kh.letter_main(p) for p in paths] == ["T002"]
    assert kh.Engine(hub, FakeRunner([])).next_job()[1][0].name < paths[0].name  # 串行：最早那封
    assert kh.Engine(hub, FakeRunner([]), only_task="T003").next_job() is None
    assert kh.tasks_with_work(hub) == ["T001", "T002"]
    state = hub.load_state()
    state["tasks"]["T001"]["status"] = "done"
    hub.save_state(state)
    assert kh.tasks_with_work(hub) == ["T002"]  # 结项的主任务不再起 runner


def test_landing_waits_for_other_tasks_executors(tmp_path, monkeypatch):
    import os
    hub = two_task_hub(tmp_path)
    monkeypatch.setattr(kh.pd, "_running_attempts", lambda repo: ["t001-doc/attempt-002", "t009-x/attempt-001"])
    t001 = hub.load_state()["tasks"]["T001"]
    marks = kh.exec_marks(hub)
    marks.mkdir(parents=True)
    (marks / "T002.json").write_text(json.dumps({"pid": os.getpid(), "task": "T002"}), encoding="utf-8")
    (marks / "T001.json").write_text(json.dumps({"pid": os.getpid(), "task": "T001"}), encoding="utf-8")
    (marks / "T003.json").write_text(json.dumps({"pid": 2 ** 22 + 7, "task": "T003"}), encoding="utf-8")
    monkeypatch.setattr(kh.pd, "pid_alive", lambda pid: pid == os.getpid())
    # 自己的标记、自己合同的 attempt、进程已不在的标记都不算
    assert kh.landing_blockers(hub, t001) == ["T002 的执行端", "attempt t009-x/attempt-001"]
    hub.deliver({"from": kh.COORDINATOR, "to": "exec-step", "task-id": "T001-5-exec", "in-reply-to": "none",
                 "type": "通过"}, fields())
    letter = hub.unread("exec-step")[0]
    passes = []

    class Engine:
        def handle_pass(self, state, meta):
            passes.append(meta["task-id"])

        def after_land(self, main):
            passes.append("after:" + main)

    blockers = kh.land(hub, Engine(), letter, kh.parse_letter(letter.read_text(encoding="utf-8"))[0])
    assert blockers and passes == [] and hub.unread("exec-step") == [letter]  # 信留在 new 里，下一轮再试
    (marks / "T002.json").unlink()
    monkeypatch.setattr(kh.pd, "_running_attempts", lambda repo: [])
    assert kh.land(hub, Engine(), letter, kh.parse_letter(letter.read_text(encoding="utf-8"))[0]) == []
    assert passes == ["T001-5-exec", "after:T001"] and hub.unread("exec-step") == []


def test_exec_window_marks_the_run_and_waits_for_a_landing(tmp_path, monkeypatch):
    hub = two_task_hub(tmp_path)
    monkeypatch.setattr(kh.pd, "_running_attempts", lambda repo: [])
    ts = hub.load_state()["tasks"]["T002"]
    with kh.exec_window(hub, ts):
        assert json.loads((kh.exec_marks(hub) / "T002.json").read_text(encoding="utf-8"))["task"] == "T002"
        assert kh.landing_blockers(hub, hub.load_state()["tasks"]["T001"]) == ["T002 的执行端"]
    assert not (kh.exec_marks(hub) / "T002.json").exists()
    monkeypatch.setattr(kh, "EXEC_LAND_WAIT_SECONDS", 0.2)
    with kh.DirLock(hub.root / ".land", wait_seconds=1.0):  # 正在落地：执行端等它落完，等不到就不开始
        with pytest.raises(kh.LandBusy):
            with kh.exec_window(hub, ts):
                pytest.fail("落地锁被占着时不该开始执行")
    assert not (kh.exec_marks(hub) / "T002.json").exists()


def test_supervisor_runs_one_runner_per_task_up_to_the_limit(tmp_path, monkeypatch):
    import argparse
    repo, _head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    hub.save_state({"tasks": {t: kh.new_task_state(t, "x", t, BASE, True) for t in ("T001", "T002", "T003")}})
    for task in ("T001", "T002", "T003"):
        hub.deliver({"from": kh.OWNER, "to": kh.COORDINATOR, "task-id": task, "in-reply-to": "none", "type": "任务"},
                    fields())
    spawned = []

    class Child:
        def __init__(self, task):
            self.task, self.pid, self.polls = task, 4000 + len(spawned), 0

        def poll(self):
            self.polls += 1
            if self.polls < 2:
                return None
            for path in hub.unread(kh.COORDINATOR):  # 子进程办完了这个主任务的信
                if kh.letter_main(path) == self.task:
                    hub.take(path)
            return 0

    def spawn(hub_, task, args):
        assert args.parallel == 2
        spawned.append(task)
        return Child(task)

    monkeypatch.setattr(kh, "spawn_task_runner", spawn)
    monkeypatch.setattr(kh, "kernel_dirty", lambda *a: False)
    code = kh.cmd_run(argparse.Namespace(repo=str(repo), max_steps=10, idle_exit=0.0, poll=0.0, settle=0.0,
                                         no_restart=False, parallel=2, task=None))
    assert code == kh.EXIT_OK and spawned == ["T001", "T002", "T003"]
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    starts = [e["event"] for e in events if e["event"] in ("runner.child_started", "runner.child_exited")]
    # 同时最多 2 个：T003 要等前两个里有一个退出才起
    live, peak = 0, 0
    for event in starts:
        live += 1 if event == "runner.child_started" else -1
        peak = max(peak, live)
    assert peak == 2 and starts[:3] == ["runner.child_started", "runner.child_started", "runner.child_exited"]


def test_parallel_comes_from_the_flag_or_runner_json(tmp_path):
    import argparse
    hub = kh.Hub(tmp_path)
    hub.ensure()
    assert kh.configured_parallel(hub, argparse.Namespace()) == 1
    (hub.root / "runner.json").write_text('{"parallel": 3}', encoding="utf-8")
    assert kh.configured_parallel(hub, argparse.Namespace(parallel=None)) == 3  # 自动重启的 hub 不带新参数
    assert kh.configured_parallel(hub, argparse.Namespace(parallel=2)) == 2
    (hub.root / "runner.json").write_text("坏的", encoding="utf-8")
    assert kh.configured_parallel(hub, argparse.Namespace(parallel=None)) == 1


def test_serial_runner_refuses_while_task_runners_are_alive(tmp_path):
    import argparse
    repo, _head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    with kh.DirLock(kh.runner_lock(hub, "T002"), wait_seconds=1.0):
        with pytest.raises(kh.HubError, match="T002"):
            kh.cmd_run(argparse.Namespace(repo=str(repo), max_steps=1, idle_exit=0.0, poll=0.0, settle=0.0,
                                          no_restart=True, parallel=1, task=None))
    assert not kh.lock_alive(kh.runner_lock(hub, "T002"))


def test_task_runner_exits_for_the_supervisor_on_kernel_changes(tmp_path, monkeypatch):
    import argparse
    repo, _head = git_repo(tmp_path)
    seen = iter(["a", "b"])
    monkeypatch.setattr(kh, "code_fingerprint", lambda *args: next(seen))
    monkeypatch.setattr(kh, "kernel_dirty", lambda *args: False)
    monkeypatch.setattr(kh, "spawn_runner", lambda argv: pytest.fail("主任务 runner 不自己重启"))
    code = kh.cmd_run(argparse.Namespace(repo=str(repo), max_steps=10, idle_exit=0.0, poll=0.0, settle=0.0,
                                         no_restart=False, parallel=None, task="T002"))
    assert code == kh.EXIT_RESTART
    assert kh.runner_lock(kh.Hub(repo), "T002").name == "T002" and not kh.lock_alive(kh.runner_lock(kh.Hub(repo), "T002"))


def test_records_commit_takes_only_the_tasks_plans_and_reviews(tmp_path):
    repo, _head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    ts = make_ts()
    plans, reviews = repo / ".agent" / "plans", repo / ".agent" / "reviews" / "t001-doc"
    plans.mkdir(parents=True)
    reviews.mkdir(parents=True)
    for name in ("t001-doc.v1.md", "t001-doc.v1.json", "t001-doc.v2.md", "t002-x.v1.md"):
        (plans / name).write_text(name + "\n", encoding="utf-8")
    (reviews / "attempt-001-hub.md").write_text("Verdict: PASS\n", encoding="utf-8")
    (repo / "README.md").write_text("站主暂存了别的东西\n", encoding="utf-8")
    kh.git(["add", "README.md"], repo)
    sha, problem = kh.commit_records(hub, ts)
    assert problem is None and sha
    assert sorted(kh.git(["show", "--name-only", "--format=", "HEAD"], repo).split()) == [
        ".agent/plans/t001-doc.v1.json", ".agent/plans/t001-doc.v1.md", ".agent/plans/t001-doc.v2.md",
        ".agent/reviews/t001-doc/attempt-001-hub.md"]
    assert kh.git(["diff", "--cached", "--name-only"], repo).split() == ["README.md"]  # 站主的暂存原样留着
    assert kh.commit_records(hub, ts) == (None, None)  # 没有新改动就不提交


def test_regression_sweep_runs_every_gate_baseline_on_the_new_tip(tmp_path, monkeypatch):
    repo, _head = git_repo(tmp_path)
    monkeypatch.setattr(kh, "worktree_root", lambda repo_: tmp_path / "wt")
    (tmp_path / "wt").mkdir()
    tests = repo / "tests"
    tests.mkdir()
    (tests / "test_gate_t001_baseline.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    (tests / "test_gate_t002_baseline.py").write_text("def test_ok():\n    pass\n", encoding="utf-8")
    (tests / "test_gate_t002_whitebox.py").write_text("def test_red():\n    assert False\n", encoding="utf-8")
    kh.git(["add", "tests"], repo)
    kh.git(["commit", "-q", "-m", "两份门禁"], repo)
    hub = kh.Hub(repo)
    ts = make_ts()
    ok, summary = kh.regression_sweep(hub, ts)
    assert ok and "2 份" in summary and ts["regression"]["exit"] == 0  # 白盒不算门禁基准
    (tests / "test_gate_t002_baseline.py").write_text("def test_red():\n    assert False\n", encoding="utf-8")
    kh.git(["commit", "-q", "-am", "被并行的另一片打破"], repo)
    ok, summary = kh.regression_sweep(hub, ts)
    assert not ok and "test_gate_t002_baseline.py::test_red" in summary
    assert list((tmp_path / "wt").iterdir()) == []  # 临时 worktree 收掉了


def rehearsal_setup(tmp_path, monkeypatch):
    """T006 的情形：门禁与候选在本任务的基线上都过，任务期间先落地的提交让门禁在末端上红。"""
    repo, _head = git_repo(tmp_path)
    monkeypatch.setattr(kh, "worktree_root", lambda repo_: tmp_path / "wt")
    (tmp_path / "wt").mkdir()
    head = land_on_main(repo, "notes.txt", "一\n二\n三\n四\n五\n", "五行的共享文件")
    branch = kh.git(["rev-parse", "--abbrev-ref", "HEAD"], repo).strip()
    kh.git(["checkout", "-q", "-b", "task"], repo)
    oracle = land_on_main(repo, "tests/test_gate_t001_baseline.py",
                          "from pathlib import Path\n\n\ndef test_feature():\n    assert Path('feature.txt').is_file()\n"
                          "    assert Path('earlier.txt').is_file()\n    assert '三改' in Path('notes.txt').read_text("
                          "encoding='utf-8')\n\n\ndef test_no_toggle_anywhere():\n    assert not Path('toggle.txt').exists()\n",
                          "门禁端基准测试")
    rework = land_on_main(repo, "earlier.txt", "上一轮的候选\n", "返工提交")
    (repo / "feature.txt").write_text("功能\n", encoding="utf-8")
    (repo / "notes.txt").write_text("一\n二\n三改\n四\n五\n", encoding="utf-8")
    kh.git(["add", "feature.txt", "notes.txt"], repo)
    kh.git(["commit", "-q", "-m", "候选"], repo)
    patch = kh.git(["diff", "--binary", rework, "HEAD"], repo)
    kh.git(["checkout", "-q", branch], repo)
    hub = kh.Hub(repo)
    hub.ensure()
    run_dir = repo / ".agent" / "runs" / "t001-doc" / "attempt-002"
    run_dir.mkdir(parents=True)
    (run_dir / "meta.json").write_text(json.dumps({"base_sha": rework}), encoding="utf-8")
    (run_dir / "candidate.patch").write_text(patch, encoding="utf-8", newline="\n")
    ts = locked(kh.new_task_state("T001", "doc", "改文档", head, True))
    ts["oracle"].update(sha=oracle, files=["tests/test_gate_t001_baseline.py"])
    ts["rework_chain"] = [{"from": "attempt-001", "commit": rework, "contract": "t001-doc.v2"}]
    ts["exec"] = {"run_dir": str(run_dir), "check_ok": True}
    return repo, hub, ts, run_dir


def land_on_main(repo, name, text, message):
    if text is None:
        kh.git(["rm", "-q", name], repo)
    else:
        (repo / name).parent.mkdir(parents=True, exist_ok=True)
        (repo / name).write_text(text, encoding="utf-8")
        kh.git(["add", name], repo)
    kh.git(["commit", "-q", "-m", message], repo)
    return kh.git(["rev-parse", "HEAD"], repo).strip()


def test_landing_rehearsal_catches_a_gate_that_a_meanwhile_commit_breaks(tmp_path, monkeypatch):
    repo, hub, ts, run_dir = rehearsal_setup(tmp_path, monkeypatch)
    assert kh.rehearse_landing(hub, ts) is None  # 分支在任务期间没动：check --fresh 已经是在这个末端上跑的
    head = kh.git(["rev-parse", "HEAD"], repo).strip()
    kh.git(["merge", "-q", "--ff-only", ts["rework_chain"][0]["commit"]], repo)
    assert kh.rehearse_landing(hub, ts) is None  # 末端就是 attempt 的基线
    kh.git(["reset", "-q", "--hard", head], repo)
    land_on_main(repo, "notes.txt", "一\n二\n三\n四\n五改\n", "别的片改了第五行")  # 与候选的第三行要三方合并
    tip = land_on_main(repo, "toggle.txt", "带 aria-pressed 的切换钮\n", "并行的一片先落地")
    ok, summary = kh.rehearse_landing(hub, ts)
    # 第 30 轮（T006）：候选在自己的基线上过了，合到末端上门禁红：现在就报，不等结项
    assert not ok and "test_no_toggle_anywhere" in summary and "test_feature" not in summary.split("\n")[0]
    assert "先落地了这些提交" in summary and "并行的一片先落地" in summary
    assert ts["rehearsal"] == {"head": tip, "run_dir": str(run_dir), "ok": False, "at": ts["rehearsal"]["at"]}
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert [e for e in events if e["event"] == "landing.rehearsed"][-1]["ok"] is False
    assert kh.rehearse_landing(hub, ts) is None  # 同一个末端、同一个候选：不再预演一次
    shutil.copytree(run_dir, run_dir.with_name("attempt-003"))
    ts["exec"]["run_dir"] = str(run_dir.with_name("attempt-003"))
    assert kh.rehearse_landing(hub, ts)[0] is False  # 新的 attempt：同一个末端也要预演
    ts["exec"]["run_dir"] = str(run_dir)
    # 主工作区不动：候选与基准测试只在临时 worktree 里
    assert kh.git(["rev-parse", "HEAD"], repo).strip() == tip and not (repo / "feature.txt").exists()
    assert list((tmp_path / "wt").iterdir()) == []
    land_on_main(repo, "toggle.txt", None, "收掉切换钮")
    ok, summary = kh.rehearse_landing(hub, ts)
    assert ok and "全部门禁基准（1 份）" in summary and "2 passed" in summary and ts["rehearsal"]["ok"] is True
    # 第 44 轮（T012）：接着返工提交改、一行没动的 attempt，补丁是空的；活在返工链里，照样预演
    empty = run_dir.with_name("attempt-004")
    empty.mkdir()
    (empty / "meta.json").write_text(json.dumps({"base_sha": ts["rework_chain"][0]["commit"]}), encoding="utf-8")
    (empty / "candidate.patch").write_text("", encoding="utf-8")
    ts["exec"]["run_dir"] = str(empty)
    ok, summary = kh.rehearse_landing(hub, ts)
    assert not ok and not summary.startswith("候选补丁") and "test_feature" in summary  # 返工链里没有功能：门禁红
    candidate = kh.git(["log", "--all", "--format=%H", "-1", "--grep=^候选$"], repo).strip()
    ts["rework_chain"].append({"from": "attempt-002", "commit": candidate, "contract": "t001-doc.v3"})
    ts.pop("rehearsal")  # 同一个末端、同一个候选不再预演：换了返工链，清掉记录重来
    ok, summary = kh.rehearse_landing(hub, ts)
    assert ok and "attempt-004 的候选" in summary and "2 passed" in summary  # 活都在返工链里


def test_landing_rehearsal_reports_commits_that_no_longer_apply(tmp_path, monkeypatch):
    repo, hub, ts, run_dir = rehearsal_setup(tmp_path, monkeypatch)
    land_on_main(repo, "feature.txt", "别的片写的同名文件\n", "同名文件")
    ok, summary = kh.rehearse_landing(hub, ts)
    assert not ok and summary.startswith("候选补丁（attempt-002）打不到末端") and "同名文件" in summary
    land_on_main(repo, "tests/test_gate_t001_baseline.py", "def test_other():\n    pass\n", "同名门禁")
    ok, summary = kh.rehearse_landing(hub, ts)
    assert not ok and summary.startswith("提交 %s 挑不到末端" % ts["oracle"]["sha"][:12])
    assert list((tmp_path / "wt").iterdir()) == []
    land_on_main(repo, "unrelated.txt", "x\n", "无关")
    for exec_state in ({"run_dir": str(run_dir), "check_ok": False}, {"run_dir": None, "check_ok": True},
                       {"run_dir": str(tmp_path / "gone"), "check_ok": True}):
        ts["exec"] = exec_state
        assert kh.rehearse_landing(hub, ts) is None  # 没有过了检查的候选：没什么可预演


def test_exec_delivery_carries_the_rehearsal_and_warns_the_owner(engine_env, monkeypatch):
    hub = engine_env
    outcome = {"rehearsal": (False, "末端上 test_gate_t007 红了")}

    def fake_exec(hub_, ts):
        ts["exec"] = {"run_dir": "attempt-001", "check_ok": True}
        return fields(摘要="执行端完成")

    monkeypatch.setattr(kh, "run_exec", fake_exec)
    monkeypatch.setattr(kh, "rehearse_landing", lambda hub_, ts: outcome["rehearsal"])
    engine = kh.Engine(hub, FakeRunner([]))
    for expected_owner in (1, 1):
        hub.deliver({"from": kh.COORDINATOR, "to": "exec-step", "task-id": "T001-5-exec", "in-reply-to": "none",
                     "type": "开工"}, fields())
        state = hub.load_state()
        engine.worker_job(state, "exec-step", hub.unread("exec-step"))
        letter = hub.unread(kh.COORDINATOR)[-1].read_text(encoding="utf-8")
        owner = hub.unread(kh.OWNER)
        assert len(owner) == expected_owner
        assert hub.load_state()["tasks"]["T001"]["stages"]["5-exec"]["status"] == "delivered"
        if outcome["rehearsal"] is None:
            assert "落地预演" not in letter
        else:
            # 候选自己没错：阶段照常交付，信里写明预演没过，另给站主写阻塞信
            assert "落地预演: 没过，已写信给站主" in letter and "test_gate_t007" in letter
            assert "type: 阻塞" in owner[0].read_text(encoding="utf-8")
            assert "落地预演没过（执行端交付时）" in owner[0].read_text(encoding="utf-8")
        outcome["rehearsal"] = None
    outcome["rehearsal"] = (True, "末端加上候选，全部门禁基准（8 份）：333 passed")
    hub.deliver({"from": kh.COORDINATOR, "to": "exec-step", "task-id": "T001-5-exec", "in-reply-to": "none",
                 "type": "开工"}, fields())
    engine.worker_job(hub.load_state(), "exec-step", hub.unread("exec-step"))
    assert "落地预演: 通过：末端加上候选" in hub.unread(kh.COORDINATOR)[-1].read_text(encoding="utf-8")
    assert len(hub.unread(kh.OWNER)) == 1


def test_after_land_rehearses_the_other_active_candidates(tmp_path, monkeypatch):
    hub = two_task_hub(tmp_path)
    state = hub.load_state()
    state["tasks"]["T003"] = kh.new_task_state("T003", "y", "已结项的一片", BASE, True)
    state["tasks"]["T003"]["status"] = "done"
    state["tasks"]["T004"] = kh.new_task_state("T004", "z", "预演通过的一片", BASE, True)
    hub.save_state(state)
    calls = []

    def rehearse(hub_, ts):
        calls.append(ts["task"])
        ts["rehearsal"] = {"ok": ts["task"] != "T002"}
        return {"T002": (False, "末端上红了"), "T004": (True, "通过")}.get(ts["task"])

    monkeypatch.setattr(kh, "rehearse_landing", rehearse)
    engine = kh.Engine(hub, FakeRunner([]))
    engine.after_land("T001")  # T001 没结项（结项失败）：末端没动，不预演
    assert calls == [] and hub.unread(kh.OWNER) == []
    state = hub.load_state()
    state["tasks"]["T001"]["status"] = "done"
    hub.save_state(state)
    engine.after_land("T001")
    assert calls == ["T002", "T004"]  # 已结项的 T003 与刚落地的 T001 不预演
    letters = [p.read_text(encoding="utf-8") for p in hub.unread(kh.OWNER)]
    assert len(letters) == 1 and "task-id: T002" in letters[0] and "落地预演没过（T001 刚落地）" in letters[0]
    disk = hub.load_state()["tasks"]
    assert disk["T002"]["rehearsal"] == {"ok": False} and disk["T004"]["rehearsal"] == {"ok": True}


def test_after_land_reports_the_regression_to_the_owner(tmp_path, monkeypatch):
    hub = two_task_hub(tmp_path)
    state = hub.load_state()
    state["tasks"]["T001"]["regression"] = {"pending": True}
    hub.save_state(state)
    calls = []

    def sweep(hub_, ts):
        calls.append(ts["task"])
        ts["regression"] = {"exit": 1}
        return False, "合入后的门禁回归（2 份）：1 failed"

    monkeypatch.setattr(kh, "regression_sweep", sweep)
    engine = kh.Engine(hub, FakeRunner([]))
    engine.after_land("T002")  # 没有待跑的回归
    engine.after_land("T001")
    engine.after_land("T001")  # 跑过了不再跑
    assert calls == ["T001"]
    letter = hub.unread(kh.OWNER)[0].read_text(encoding="utf-8")
    assert "type: 阻塞" in letter and "合入后的门禁回归没过" in letter


def test_exclusive_runs_the_command_once_executors_are_done(tmp_path, monkeypatch):
    import argparse
    import os
    repo, _head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    monkeypatch.setattr(kh.pd, "_running_attempts", lambda repo_: [])
    marks = kh.exec_marks(hub)
    marks.mkdir(parents=True)
    (marks / "T002.json").write_text(json.dumps({"pid": os.getpid(), "task": "T002"}), encoding="utf-8")
    out = tmp_path / "ran.txt"
    command = ["--", sys.executable, "-c", "open(r'%s', 'w').write('ok')" % out]
    with pytest.raises(kh.HubError, match="T002 的执行端"):
        kh.cmd_exclusive(argparse.Namespace(repo=str(repo), wait=0.0, command=command))
    assert not out.exists()
    (marks / "T002.json").unlink()
    assert kh.cmd_exclusive(argparse.Namespace(repo=str(repo), wait=5.0, command=command)) == 0
    assert out.read_text(encoding="utf-8") == "ok"
    assert kh.main(["--repo", str(repo), "exclusive"]) == kh.EXIT_USAGE  # 没写命令


def supervisor_env(tmp_path, monkeypatch, tasks):
    repo, _head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    hub.save_state({"tasks": {t: kh.new_task_state(t, "x", t, BASE, True) for t in tasks}})
    for task in tasks:
        hub.deliver({"from": kh.OWNER, "to": kh.COORDINATOR, "task-id": task, "in-reply-to": "none", "type": "任务"},
                    fields())
    spawned = []

    class Child:
        pid = 4321

        def __init__(self, task):
            self.task = task

        def poll(self):
            for path in hub.unread(kh.COORDINATOR):  # 子进程把这个主任务的信办完了
                if kh.letter_main(path) == self.task:
                    hub.take(path)
            return 0

    def spawn(hub_, task, args):
        spawned.append(task)
        return Child(task)

    monkeypatch.setattr(kh, "spawn_task_runner", spawn)
    return repo, hub, spawned


def supervise_once(repo, parallel):
    import argparse
    return kh.cmd_run(argparse.Namespace(repo=str(repo), max_steps=10, idle_exit=0.0, poll=0.0, settle=0.0,
                                         no_restart=False, parallel=parallel, task=None))


def test_supervisor_counts_runners_left_by_its_previous_generation(tmp_path, monkeypatch):
    repo, hub, spawned = supervisor_env(tmp_path, monkeypatch, ("T001", "T002", "T003"))
    monkeypatch.setattr(kh, "kernel_dirty", lambda *a: False)
    lock = kh.DirLock(kh.runner_lock(hub, "T001"), wait_seconds=1.0)
    lock.__enter__()  # 上一代 supervisor 起的 T001 runner 还活着
    real, calls = kh.tasks_with_work, []

    def pending(hub_):
        calls.append(spawned[:])
        if len(calls) == 3:
            lock.__exit__(None, None, None)  # 它办完退出了
        return real(hub_)

    monkeypatch.setattr(kh, "tasks_with_work", pending)
    assert supervise_once(repo, 2) == kh.EXIT_OK
    # 它占着一个名额：同时只起一个；它还活着时不重复起 T001，退出之后才起
    assert calls[:3] == [[], ["T002"], ["T002", "T003"]] and spawned == ["T002", "T003", "T001"]


def test_supervisor_waits_for_a_settled_kernel_before_starting_runners(tmp_path, monkeypatch):
    repo, _hub, spawned = supervisor_env(tmp_path, monkeypatch, ("T002",))
    dirty = [True, True, False]
    monkeypatch.setattr(kh, "kernel_dirty", lambda *a: dirty.pop(0) if len(dirty) > 1 else dirty[0])
    assert supervise_once(repo, 2) == kh.EXIT_OK
    assert spawned == ["T002"] and dirty == [False]  # 内核有未提交的改动时不起，落定之后才起


def test_status_shows_the_parallel_runners(tmp_path, capsys):
    import argparse
    import os
    repo, _head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    (hub.root / "runner.json").write_text('{"parallel": 2}', encoding="utf-8")
    marks = kh.exec_marks(hub)
    marks.mkdir(parents=True)
    (marks / "T002.json").write_text(json.dumps({"pid": os.getpid(), "task": "T002"}), encoding="utf-8")
    with kh.DirLock(kh.runner_lock(hub, "T002"), wait_seconds=1.0):
        kh.cmd_status(argparse.Namespace(repo=str(repo), json=False))
    out = capsys.readouterr().out
    assert "并行：最多 2 个主任务；在跑的主任务 runner：T002；在跑的执行端：T002 的执行端" in out


def test_worktree_add_retries_when_git_metadata_is_busy(tmp_path, monkeypatch):
    hub = kh.Hub(tmp_path)
    hub.ensure()
    calls = []

    def flaky(args, cwd, check=True, timeout=120):
        calls.append(list(args))
        if len(calls) < 3:
            raise kh.HubError("git worktree add 失败：could not lock")
        return ""

    monkeypatch.setattr(kh, "git", flaky)
    monkeypatch.setattr(kh.time, "sleep", lambda seconds: None)
    kh.add_worktree(hub, tmp_path / "wt", "abc")
    assert len(calls) == 3 and calls[-1] == ["worktree", "add", "--detach", str(tmp_path / "wt"), "abc"]
    calls.clear()
    monkeypatch.setattr(kh, "WORKTREE_ADD_TRIES", 2)
    with pytest.raises(kh.HubError):  # 次数用完照实报错
        kh.add_worktree(hub, tmp_path / "wt", "abc")
    assert len(calls) == 2


def test_supervisor_stays_while_a_runner_works_without_unread_letters(tmp_path, monkeypatch):
    # 执行端一跑一小时：它的信早已读掉，supervisor 不能因为“没有未读信”就退出，否则站主以为 hub 停了
    repo, hub, spawned = supervisor_env(tmp_path, monkeypatch, ())
    monkeypatch.setattr(kh, "kernel_dirty", lambda *a: False)
    lock = kh.DirLock(kh.runner_lock(hub, "T001"), wait_seconds=1.0)
    lock.__enter__()
    calls = []

    def pending(hub_):
        calls.append(1)
        if len(calls) == 3:
            lock.__exit__(None, None, None)
        return []

    monkeypatch.setattr(kh, "tasks_with_work", pending)
    assert supervise_once(repo, 2) == kh.EXIT_OK
    assert len(calls) >= 3 and spawned == []


def hold_until_called(hub, monkeypatch, name, times):
    """T001 有扣着、没到点的信；被 monkeypatch 的那个函数第 times 次调用时放掉，hub 才可能退出。"""
    state = hub.load_state()
    state["tasks"]["T001"] = make_ts()
    state["tasks"]["T001"]["held"] = [{"agent": "planner-opus", "letters": [], "until": "2999-01-01T00:00:00Z",
                                       "suffix": None, "turn": "t1"}]
    hub.save_state(state)
    real, calls = getattr(kh, name), []

    def counted(*args):
        calls.append(1)
        if len(calls) == times:
            state = hub.load_state()
            state["tasks"]["T001"]["held"] = []
            hub.save_state(state)
        return real(*args)

    monkeypatch.setattr(kh, name, counted)
    return calls


def test_supervisor_stays_while_letters_are_held(tmp_path, monkeypatch):
    # 第 33 轮：扣着的信要到点才放回；supervisor 先退了，就没人放
    repo, hub, spawned = supervisor_env(tmp_path, monkeypatch, ())
    monkeypatch.setattr(kh, "kernel_dirty", lambda *a: False)
    calls = hold_until_called(hub, monkeypatch, "tasks_with_work", 3)
    assert supervise_once(repo, 2) == kh.EXIT_OK
    assert len(calls) >= 3 and spawned == []


def test_serial_hub_stays_while_letters_are_held(tmp_path, monkeypatch):
    repo, hub, _spawned = supervisor_env(tmp_path, monkeypatch, ())
    calls = hold_until_called(hub, monkeypatch, "release_held", 3)
    assert supervise_once(repo, 1) == kh.EXIT_OK  # 并行数 1：串行的 hub
    assert len(calls) >= 3


# ---------------------------------------------------------------------------
# 第 21 轮：依赖前一片的切片先规划；站主命令在并行时拿得到锁
# ---------------------------------------------------------------------------

def test_dependent_task_plans_first_and_waits_for_its_dependencies(tmp_path):
    ts = make_ts()
    ts["after"] = ["T006", "T007"]
    assert kh.guard(ts, meta("开工", "planner-opus", "T001-1-plan")) is None  # 规划不受依赖限制
    ts["stages"]["1-plan"]["status"] = "delivered"
    reason = kh.guard(ts, meta("开工", "contract-glm", "T001-2-contract"))
    assert reason and "T006、T007" in reason and "合同端" in reason
    assert not any("contract-glm" in move for move in kh.allowed_moves(ts))
    ts["after_released"] = {"head": "b" * 40, "previous": BASE, "after": ["T006", "T007"]}
    assert kh.guard(ts, meta("开工", "contract-glm", "T001-2-contract")) is None


def test_release_moves_the_base_once_every_dependency_is_done(tmp_path):
    repo, head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    tasks = {t: kh.new_task_state(t, t.lower(), t, BASE, True) for t in ("T006", "T007", "T008", "T009")}
    tasks["T008"]["after"] = ["T006", "T007"]
    tasks["T008"]["workspaces"] = {"base": {"path": "old-base"}, "gate": {"path": "old-gate"}, "post-a": {"path": "p"}}
    tasks["T009"]["after"] = ["T006"]
    tasks["T009"]["status"] = "stopped"
    state = {"tasks": tasks}
    tasks["T006"]["status"] = "done"
    assert kh.release_dependents(hub, state, "T006") == []  # T007 还没结项；T009 已停止
    assert "after_released" not in tasks["T008"] and tasks["T008"]["base_head"] == BASE
    tasks["T007"]["status"] = "done"
    assert kh.release_dependents(hub, state, "T007") == ["T008"]
    t008 = tasks["T008"]
    assert t008["base_head"] == head and t008["after_released"]["previous"] == BASE
    # 旧基线的阶段 worktree 改名留着，结项时一并清掉；新基线上重新建
    assert set(t008["workspaces"]) == {"base@%s" % BASE[:10], "gate@%s" % BASE[:10], "post-a"}
    letter = hub.unread(kh.COORDINATOR)[0].read_text(encoding="utf-8")
    assert "type: 核验" in letter and "task-id: T008" in letter and "开工 contract-glm" in letter
    assert kh.release_dependents(hub, state, "T007") == []  # 只放行一次
    assert "依赖 T006、T007 已结项" in kh.stage_status_table(hub, t008)


def test_task_new_records_only_unfinished_dependencies(tmp_path, capsys):
    repo, _head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    state = hub.load_state()
    state["tasks"]["T006"] = kh.new_task_state("T006", "a", "a", BASE, True)
    state["tasks"]["T005"] = kh.new_task_state("T005", "b", "b", BASE, True)
    state["tasks"]["T005"]["status"] = "done"
    hub.save_state(state)
    brief = tmp_path / "brief.md"
    brief.write_text("# 任务书\n", encoding="utf-8")
    base = ["--repo", str(repo), "task", "new", "--slug", "pages", "--title", "页面", "--brief", str(brief)]
    assert kh.main(base[:4] + ["T008"] + base[4:] + ["--after", "T005,T099"]) == kh.EXIT_USAGE
    assert kh.main(base[:4] + ["T008"] + base[4:] + ["--after", "T005, T006"]) == kh.EXIT_OK
    assert "合同端等 T006 结项" in capsys.readouterr().out
    ts = hub.load_state()["tasks"]["T008"]
    assert ts["after"] == ["T006"]  # 已结项的 T005 不用等
    assert "依赖：等 T006 结项" in kh.stage_status_table(hub, ts)
    assert kh.main(base[:4] + ["T009"] + base[4:] + ["--after", "T005"]) == kh.EXIT_OK
    assert "after" not in hub.load_state()["tasks"]["T009"]


def test_passing_and_owner_close_release_the_dependents(tmp_path, monkeypatch):
    repo, head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    state = hub.load_state()
    for task in ("T006", "T008"):
        state["tasks"][task] = kh.new_task_state(task, task.lower(), task, BASE, True)
    state["tasks"]["T008"]["after"] = ["T006"]
    state["tasks"]["T006"]["exec"] = {"run_dir": str(repo / "attempt-001")}
    hub.save_state(state)
    monkeypatch.setattr(kh, "finalize", lambda hub_, ts: (True, "integrate ok"))
    monkeypatch.setattr(kh, "tidy_finished", lambda hub_, ts, reason: [])
    engine = kh.Engine(hub, FakeRunner([]))
    engine.handle_pass(hub.load_state(), {"task-id": "T006-5-exec"})
    assert hub.load_state()["tasks"]["T008"]["after_released"]["head"] == head
    # 站主接手结项也放行
    state = hub.load_state()
    state["tasks"]["T010"] = kh.new_task_state("T010", "x", "x", BASE, True)
    state["tasks"]["T011"] = kh.new_task_state("T011", "y", "y", BASE, True)
    state["tasks"]["T011"]["after"] = ["T010"]
    hub.save_state(state)
    note = tmp_path / "close.md"
    note.write_text("站主接手\n", encoding="utf-8")
    assert kh.main(["--repo", str(repo), "task", "close", "T010", "--ref", head, "--file", str(note)]) == kh.EXIT_OK
    assert hub.load_state()["tasks"]["T011"]["after_released"]["head"] == head


def test_owner_commands_only_need_the_task_lock_under_a_supervisor(tmp_path):
    repo, _head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    with kh.task_quiet(hub, "T006"):  # 没有 hub 在跑：两把锁都拿
        assert kh.lock_alive(kh.runner_lock(hub, "T006")) and kh.lock_alive(kh.runner_lock(hub, None))
    assert not kh.lock_alive(kh.runner_lock(hub, None))
    with kh.DirLock(kh.runner_lock(hub, None), wait_seconds=1.0):
        with pytest.raises(kh.HubError):  # 串行的 hub 在跑：等不到总锁
            with kh.task_quiet(hub, "T006"):
                pass
        kh.write_text_atomic(kh.runner_lock(hub, None) / "mode", "supervisor\n")
        assert kh.supervisor_alive(hub)
        with kh.task_quiet(hub, "T006"):  # 并行：supervisor 不办信，只要主任务的锁
            assert kh.lock_alive(kh.runner_lock(hub, "T006"))
        with kh.DirLock(kh.runner_lock(hub, "T007"), wait_seconds=1.0):
            with pytest.raises(kh.HubError):  # T007 的 runner 正在办信（只等 1 秒；缺省会等它办完这一步）
                with kh.task_quiet(hub, "T007", wait=1.0):
                    pass


def test_owner_rebases_a_task_before_its_contract_starts(tmp_path):
    # 第 22 轮：T006 规划时发现 T002 门禁里还有两条渲染根 App 的用例，站主退役之后要把 T006 的基线挪过去
    repo, head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    state = hub.load_state()
    state["tasks"]["T006"] = kh.new_task_state("T006", "shell", "应用框架", BASE, True)
    state["tasks"]["T006"]["workspaces"] = {"base": {"path": "old"}, "post-a": {"path": "p"}}
    hub.save_state(state)
    cmd = ["--repo", str(repo), "task", "rebase", "T006"]
    assert kh.main(cmd + ["--reason", " "]) == kh.EXIT_USAGE  # 要写原因
    assert kh.main(cmd + ["--reason", "退役了 T002 门禁的两条根 App 用例"]) == kh.EXIT_OK
    ts = hub.load_state()["tasks"]["T006"]
    assert ts["base_head"] == head and ts["rebases"][0]["previous"] == BASE
    assert set(ts["workspaces"]) == {"base@%s" % BASE[:10], "post-a"}
    letter = hub.unread(kh.COORDINATOR)[0].read_text(encoding="utf-8")
    assert "type: 核验" in letter and "退役了 T002 门禁的两条根 App 用例" in letter
    assert kh.main(cmd + ["--reason", "再来一次"]) == kh.EXIT_OK and len(hub.unread(kh.COORDINATOR)) == 1  # 已是末端
    state = hub.load_state()
    state["tasks"]["T006"]["base_head"] = BASE
    state["tasks"]["T006"]["stages"]["2-contract"]["status"] = "assigned"  # 合同端开工了：不能再挪
    hub.save_state(state)
    assert kh.main(cmd + ["--reason", "晚了"]) == kh.EXIT_BLOCKED
    state = hub.load_state()
    state["tasks"]["T006"]["stages"]["2-contract"]["status"] = "idle"
    state["tasks"]["T006"]["contract"] = {"key": "t006-shell.v1"}
    hub.save_state(state)
    assert kh.main(cmd + ["--reason", "晚了"]) == kh.EXIT_BLOCKED
    state = hub.load_state()
    state["tasks"]["T006"].update(contract={}, status="done")
    hub.save_state(state)
    assert kh.main(cmd + ["--reason", "结项了"]) == kh.EXIT_USAGE
    assert kh.main(["--repo", str(repo), "task", "rebase", "T404", "--reason", "x"]) == kh.EXIT_USAGE


def test_owner_adds_a_dependency_found_in_planning(tmp_path):
    # 第 31 轮：T011 的规划要 T009 新加的分组 ID，可 T011 登记时没写 --after
    repo, head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    state = hub.load_state()
    for task in ("T006", "T009", "T010", "T011"):
        state["tasks"][task] = kh.new_task_state(task, task.lower(), task, BASE, True)
    state["tasks"]["T006"]["status"] = "done"
    state["tasks"]["T010"]["after"] = ["T011"]
    state["tasks"]["T011"]["after"] = ["T006"]
    state["tasks"]["T011"]["after_released"] = {"head": BASE, "previous": BASE, "after": ["T006"]}
    hub.save_state(state)
    cmd = ["--repo", str(repo), "task", "after", "T011"]
    reason = ["--reason", "要用 T009 给 attemptGroups.ts 加的 groupOfState"]
    assert kh.main(cmd + ["--on", "T009", "--reason", " "]) == kh.EXIT_USAGE  # 要写原因
    assert kh.main(cmd + ["--on", "T404"] + reason) == kh.EXIT_USAGE
    assert kh.main(cmd + ["--on", "T011"] + reason) == kh.EXIT_USAGE  # 不能等自己
    assert kh.main(cmd + ["--on", " , "] + reason) == kh.EXIT_USAGE
    assert kh.main(cmd + ["--on", "T010"] + reason) == kh.EXIT_USAGE  # T010 在等 T011：互相等
    assert kh.main(cmd + ["--on", "T006"] + reason) == kh.EXIT_OK  # 已结项：不用等，什么都不改
    assert hub.unread(kh.COORDINATOR) == [] and hub.load_state()["tasks"]["T011"]["after"] == ["T006"]
    assert kh.main(cmd + ["--on", "T009,T006"] + reason) == kh.EXIT_OK
    ts = hub.load_state()["tasks"]["T011"]
    assert ts["after"] == ["T006", "T009"] and "after_released" not in ts
    assert ts["after_added"][0]["on"] == ["T009"]
    letter = hub.unread(kh.COORDINATOR)[0].read_text(encoding="utf-8")
    assert "type: 核验" in letter and "等 T009 结项" in letter and "groupOfState" in letter
    assert "要等它们都结项" in kh.guard(ts, meta("开工", "contract-glm", "T011-2-contract"))
    assert kh.guard(ts, meta("开工", "planner-opus", "T011-1-plan")) is None  # 规划照常
    # T009 结项：内核照登记时写的依赖一样放行，把基线挪到末端
    state = hub.load_state()
    state["tasks"]["T009"]["status"] = "done"
    assert kh.release_dependents(hub, state, "T009") == ["T011"]
    assert state["tasks"]["T011"]["base_head"] == head
    # 合同端开工之后不能再补：合同钉在当前基线上
    state["tasks"]["T011"]["stages"]["2-contract"]["status"] = "assigned"
    hub.save_state(state)
    assert kh.main(cmd + ["--on", "T009"] + reason) == kh.EXIT_BLOCKED
    state = hub.load_state()
    state["tasks"]["T011"]["status"] = "done"
    hub.save_state(state)
    assert kh.main(cmd + ["--on", "T009"] + reason) == kh.EXIT_USAGE
    assert kh.main(["--repo", str(repo), "task", "after", "T404", "--on", "T009"] + reason) == kh.EXIT_USAGE


def test_tasks_others_wait_for_get_runners_first(tmp_path):
    # 第 23 轮：T009 依赖 T006；T006 的信晚到，名额满时它也该先拿到
    hub = kh.Hub(tmp_path)
    hub.ensure()
    tasks = {t: kh.new_task_state(t, t.lower(), t, BASE, True) for t in ("T006", "T008", "T009")}
    tasks["T009"]["after"] = ["T006"]
    tasks["T008"]["after"] = ["T007"]
    hub.save_state({"tasks": tasks})
    for task in ("T009", "T008", "T006"):
        hub.deliver({"from": kh.OWNER, "to": kh.COORDINATOR, "task-id": task, "in-reply-to": "none", "type": "回复"},
                    fields())
    assert kh.tasks_with_work(hub) == ["T006", "T009", "T008"]
    state = hub.load_state()
    state["tasks"]["T009"]["after_released"] = {"head": "b" * 40}  # 放行之后不再算“被等着”
    hub.save_state(state)
    assert kh.tasks_with_work(hub) == ["T009", "T008", "T006"]


def test_supervisor_picks_up_runner_json_changes_while_running(tmp_path, monkeypatch):
    repo, hub, spawned = supervisor_env(tmp_path, monkeypatch, ("T001", "T002", "T003"))
    monkeypatch.setattr(kh, "kernel_dirty", lambda *a: False)
    (hub.root / "runner.json").write_text('{"parallel": 2}', encoding="utf-8")
    polls = {"n": 0}
    real_spawn = kh.spawn_task_runner
    exits_before_third = []

    class Slow:
        pid = 1

        def __init__(self, inner):
            self.inner = inner

        def poll(self):
            polls["n"] += 1
            if len(spawned) < 3 and polls["n"] < 40:
                (hub.root / "runner.json").write_text('{"parallel": 3}', encoding="utf-8")  # 站主调大
                return None
            return self.inner.poll()

    def spawn(hub_, task, args):
        if task == "T003":
            exits_before_third.append(polls["n"] >= 40)
        return Slow(real_spawn(hub_, task, args))

    monkeypatch.setattr(kh, "spawn_task_runner", spawn)
    import argparse
    assert kh.cmd_run(argparse.Namespace(repo=str(repo), max_steps=10, idle_exit=0.0, poll=0.0, settle=0.0,
                                         no_restart=False, parallel=None, task=None)) == kh.EXIT_OK
    assert spawned == ["T001", "T002", "T003"] and exits_before_third == [False]  # 前两个都没退出时，第三个就起了


def test_supervisor_restart_keeps_where_parallel_came_from(tmp_path, monkeypatch):
    import argparse
    repo, hub, _spawned = supervisor_env(tmp_path, monkeypatch, ())
    (hub.root / "runner.json").write_text('{"parallel": 2}', encoding="utf-8")
    seen = []
    monkeypatch.setattr(kh, "kernel_settled", lambda *a: True)
    monkeypatch.setattr(kh, "spawn_runner", lambda argv: seen.append(argv) or 0)
    for flag in (None, 3):
        prints = iter(["a", "b"])
        monkeypatch.setattr(kh, "code_fingerprint", lambda *a: next(prints))
        kh.cmd_run(argparse.Namespace(repo=str(repo), max_steps=10, idle_exit=0.0, poll=0.0, settle=0.0,
                                      no_restart=False, parallel=flag, task=None))
    assert "--parallel" not in seen[0]  # 从 runner.json 来的：重启后接着读 runner.json
    assert seen[1][seen[1].index("--parallel") + 1] == "3"


# ---------------------------------------------------------------------------
# 第 24 轮：supervisor 不因一次意外整个停下
# ---------------------------------------------------------------------------

def test_fingerprint_survives_a_file_being_swapped(tmp_path):
    # git merge 换文件的那一瞬间文件不在：指纹照样算得出，只是与原来不同
    code = tmp_path / "kit_hub.py"
    code.write_text("# 内核\n", encoding="utf-8")
    before = kh.code_fingerprint([code])
    code.unlink()
    missing = kh.code_fingerprint([code])
    assert missing != before
    code.write_text("# 内核\n", encoding="utf-8")
    assert kh.code_fingerprint([code]) == before


def test_supervisor_keeps_going_after_a_bad_tick(tmp_path, monkeypatch):
    repo, hub, spawned = supervisor_env(tmp_path, monkeypatch, ("T001",))
    monkeypatch.setattr(kh, "kernel_dirty", lambda *a: False)
    real, calls = kh.tasks_with_work, []

    def flaky(hub_):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("state.json 正被替换")
        return real(hub_)

    monkeypatch.setattr(kh, "tasks_with_work", flaky)
    monkeypatch.setattr(kh.time, "sleep", lambda seconds: None)
    assert supervise_once(repo, 2) == kh.EXIT_OK
    assert spawned == ["T001"]  # 出错的那一轮之后照常起了 runner
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert [e["error"] for e in events if e["event"] == "supervisor.error"] == ["OSError: state.json 正被替换"]


def test_supervisor_stops_restarting_a_crashing_runner(tmp_path, monkeypatch):
    repo, hub, spawned = supervisor_env(tmp_path, monkeypatch, ("T001", "T002"))
    monkeypatch.setattr(kh, "kernel_dirty", lambda *a: False)
    codes = {"T001": [1, 1, 1, 1], "T002": [kh.EXIT_RESTART] * kh.RUNNER_CRASH_LIMIT + [0]}

    class Child:
        pid = 7

        def __init__(self, task):
            self.task = task

        def poll(self):
            code = codes[self.task].pop(0)
            if code == 0:
                for path in hub.unread(kh.COORDINATOR):
                    if kh.letter_main(path) == self.task:
                        hub.take(path)
            return code

    monkeypatch.setattr(kh, "spawn_task_runner", lambda hub_, task, args: spawned.append(task) or Child(task))
    assert supervise_once(repo, 2) == kh.EXIT_OK
    assert spawned.count("T001") == kh.RUNNER_CRASH_LIMIT  # 崩够次数就不再起，信留着等站主
    assert spawned.count("T002") == kh.RUNNER_CRASH_LIMIT + 1  # 为内核换代退出（75）不算崩，多少次都照起
    letters = [p.read_text(encoding="utf-8") for p in hub.unread(kh.OWNER)]
    assert len(letters) == 1 and "T001 的 runner 接连 3 次异常退出" in letters[0]
    assert [kh.letter_main(p) for p in hub.unread(kh.COORDINATOR)] == ["T001"]


def test_output_block_takes_the_first_copy_when_keys_are_repeated():
    # 第 25 轮：T008 的协调人两次都在对象结束之后又写了一遍 `], "state": "…"}`
    warnings: list = []
    text = ('```json\n{"letters": [{"to": "站主", "摘要": "x"}], "state": "# 断点 一"}], '
            '"state": "# 断点 二"}\n```')
    assert kh.extract_json_block(text, warnings) == {"letters": [{"to": "站主", "摘要": "x"}], "state": "# 断点 一"}
    assert warnings == ["JSON 代码块末尾又写了一遍 state，已忽略，取第一份"]
    for extra in (', "letters": []}', ', "verdict": "通过"}', '], {"to": "x"}]}'):
        # 多出来的有对象里没有的键，或者又写了一遍 letters（可能是改过的信）：照旧拒收，并说清楚错在哪
        with pytest.raises(kh.HubError, match="只能有一个 JSON 对象"):
            kh.extract_json_block('```json\n{"letters": [], "state": "s"}%s\n```' % extra, [])


# ---------------------------------------------------------------------------
# 第 26 轮：回合中途出意外，信不能悄悄丢掉
# ---------------------------------------------------------------------------

class BrokenRunner:
    def run(self, *args, **kwargs):
        raise kh.HubError("git worktree add 失败：could not lock")


def test_a_crashed_turn_tells_the_owner_which_letters_were_taken(engine_env):
    hub = engine_env
    owner_task(hub)
    letter = hub.unread(kh.COORDINATOR)[0].name
    assert kh.Engine(hub, BrokenRunner()).step() is True  # 不把 runner 带崩
    assert hub.unread(kh.COORDINATOR) == []  # 信已经读了
    owner = hub.unread(kh.OWNER)
    assert len(owner) == 1
    text = owner[0].read_text(encoding="utf-8")
    assert "type: 阻塞" in text and "task-id: T001" in text and letter in text and "could not lock" in text
    assert "send T001 --type 回复" in text
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert [e["letters"] for e in events if e["event"] == "step.error"] == [[letter]]


def test_template_read_waits_out_a_file_being_replaced(monkeypatch):
    reads = []
    real = kh.read_text

    def flaky(path):
        reads.append(path)
        return "" if len(reads) < 3 else real(path)

    monkeypatch.setattr(kh, "read_text", flaky)
    monkeypatch.setattr(kh.time, "sleep", lambda seconds: None)
    assert "{{" not in kh.render_template("coordinator.md", {"仓库": "x", "名字": "y"}) and len(reads) == 3
    reads.clear()
    monkeypatch.setattr(kh, "read_text", lambda path: reads.append(path) or "")
    with pytest.raises(kh.HubError, match="找不到提示词模板"):
        kh.render_template("coordinator.md", {})
    assert len(reads) == kh.TEMPLATE_READ_TRIES + 1


def test_exec_recheck_resumes_an_execution_the_hub_was_killed_in(engine_env, monkeypatch):
    # 第 27 轮：系统内存紧张，hub 在 T007 的执行端跑完、check 做到一半时被收掉；开工信早已读掉，阶段停在 assigned
    hub = engine_env
    calls = []
    monkeypatch.setattr(kh, "run_pd", lambda hub, args, timeout=600: calls.append(args[0]) or (0, "ok"))
    state = hub.load_state()
    ts = locked(state["tasks"]["T001"])
    ts["stages"]["5-exec"].update(status="assigned", kind="开工")
    hub.save_state(state)
    engine = kh.Engine(hub, FakeRunner([]))
    with pytest.raises(kh.HubError, match="没有 attempt"):
        engine.recheck_exec("T001")
    run_dir = attempt_dir(hub, {"state": "RUNNING"})
    with pytest.raises(kh.HubError, match="collect --recover"):
        engine.recheck_exec("T001")
    (run_dir / "state.json").write_text(json.dumps({"state": "REVISE"}), encoding="utf-8")
    with pytest.raises(kh.HubError, match="已经有结论"):
        engine.recheck_exec("T001")
    (run_dir / "state.json").write_text(json.dumps({"state": "NEEDS_REVIEW", "exit_code": 0}), encoding="utf-8")
    earlier = run_dir.parent / "attempt-001"  # 上一轮已经判过的 attempt：取最近的那个
    earlier.mkdir()
    (earlier / "state.json").write_text(json.dumps({"state": "REVISE"}), encoding="utf-8")
    result = engine.recheck_exec("T001")
    assert result["check_ok"] is True and result["run_dir"] == str(run_dir) and result["run_exit"] == 0
    assert calls == ["check"]  # 只重做核验，不重跑执行端
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["stages"]["5-exec"]["status"] == "delivered" and ts["contract"]["dispatched"] is True
    letters = [p.read_text(encoding="utf-8") for p in hub.unread(kh.COORDINATOR)]
    assert len(letters) == 1 and "from: exec-step" in letters[0]
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert [e["run_dir"] for e in events if e["event"] == "exec.resumed"] == [str(run_dir)]


def test_paused_worker_stage_can_be_started_again(engine_env):
    # 第 28 轮：T006 的战后门禁发“阻塞”之后阶段一直是 assigned，开工、返工都被拒，只能站主动 state
    hub = engine_env
    state = hub.load_state()
    ts = state["tasks"]["T001"] = locked(make_ts())
    ts["stages"]["3-gate-pre"]["status"] = "assigned"
    hub.save_state(state)
    hub.deliver({"from": kh.COORDINATOR, "to": "gate-sonnet", "task-id": "T001-3-gate-pre", "in-reply-to": "none",
                 "type": "开工"}, fields(摘要="写基准测试"))
    asked = {"letter": {"type": "提问", "in_reply_to": "m", "摘要": "合同 D3 的空列表算不算", "提交": "无",
                        "验证": "读了合同", "偏离": "无", "需协调人决定": "D3", "证据": "plan.md:40"},
             "report": "# 提问", "state": "s"}
    assert kh.Engine(hub, FakeRunner([(asked, [])])).step()
    state = hub.load_state()
    ts = state["tasks"]["T001"]
    stage = ts["stages"]["3-gate-pre"]
    assert stage["status"] == "paused" and stage["last_letter"] == "提问" and stage["paused_at"]
    assert kh.guard(ts, meta("开工", "gate-sonnet", "T001-3-gate-pre")) is None
    letter = dict(start_planner("# 答复\n空列表算"), to="gate-sonnet", task_id="T001-3-gate-pre")
    assert kh.Engine(hub).deliver_coordinator_letter(state, letter) is None
    stage = hub.load_state()["tasks"]["T001"]["stages"]["3-gate-pre"]
    assert stage["status"] == "assigned" and "last_letter" not in stage and stage["kind"] == "开工"
    assert "已经开工" in kh.guard(hub.load_state()["tasks"]["T001"], meta("开工", "gate-sonnet", "T001-3-gate-pre"))
    # 交付、返工完成照旧：不会停在 paused
    assert not {"交付", "返工完成"} & set(kh.PAUSE_TYPES)
    assert set(kh.PAUSE_TYPES) == set(kh.WORKER_TYPES) - {"交付", "返工完成"}
    # 第 28 轮之前留下的旧状态：assigned 加上工人停下的信，也当作停下了；别的 assigned 照旧算在办
    for kind in kh.PAUSE_TYPES:
        assert not kh.stage_busy({"status": "assigned", "last_letter": kind})
    assert kh.stage_busy({"status": "assigned"}) and kh.stage_busy({"status": "assigned", "last_letter": "交付"})
    assert not kh.stage_busy({"status": "paused", "last_letter": "阻塞"})
    ts = locked(make_ts())
    ts["stages"]["6-gate-post"] = {"status": "assigned", "last_letter": "阻塞"}
    ts["exec"]["check_ok"] = True
    assert kh.guard(ts, meta("开工", "gate-sonnet", "T001-6-gate-post")) is None
    assert "正在进行" not in kh.guard(ts, meta("返工", "gate-sonnet", "T001-6-gate-post"))
    ts["stages"]["6-gate-post"] = {"status": "assigned"}
    assert "已经开工" in kh.guard(ts, meta("开工", "gate-sonnet", "T001-6-gate-post"))
    assert "正在进行" in kh.guard(ts, meta("返工", "gate-sonnet", "T001-6-gate-post"))
    assert "paused" in (kh.TEMPLATE_DIR / "coordinator.md").read_text(encoding="utf-8")


def test_audit_may_return_several_stages_and_the_upstream_one_goes_first():
    # 第 28 轮：T008 的一审要同时退回门禁端与合同端，字段只能写一个，合同端的返工被内核拒收
    head = {"from": "audit-sonnet", "to": kh.COORDINATOR, "task-id": "T001-4-audit-pre", "in-reply-to": "m",
            "type": "交付"}
    for value in ("合同端、门禁端", "合同端，门禁端", "合同端, 门禁端", "合同端/门禁端", "合同端 门禁端"):
        assert kh.letter_errors(head, fields(结论="返工", 退回=value, 阻塞项="1. D09"), 9) == []
        assert kh.return_stages(value) == ["2-contract", "3-gate-pre"]
    assert kh.return_stages("门禁端、合同端、门禁端") == ["2-contract", "3-gate-pre"]
    assert kh.return_stages("") == [] and kh.return_stages(None) == [] and kh.return_stages("乱写") == []
    for value in ("合同端、乱写", "、", ""):
        assert any("退回" in e for e in kh.letter_errors(head, fields(结论="返工", 退回=value, 阻塞项="x"), 9))
    assert any("一审只能退回" in e for e in kh.letter_errors(head, fields(结论="返工", 退回="合同端、执行端", 阻塞项="x"), 9))
    final = dict(head, **{"task-id": "T001-7-audit-post"})
    assert kh.letter_errors(final, fields(结论="返工", 退回="门禁端、执行端", 阻塞项="x"), 9) == []
    # 一审同时退回：合同端先返工；门禁端等合同端重新交付、回到 idle 之后再开工
    ts = locked(make_ts())
    ts["stages"]["4-audit-pre"]["status"] = "delivered"
    ts["audit_pre"].update(verdict="返工", target="门禁端、合同端")
    refused = kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre"))
    assert "先返工最上游的 2-contract" in refused and "2-contract、3-gate-pre" in refused
    assert kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract")) is None
    ts["owner_rework"] = {"suffix": "3-gate-pre"}  # 站主指定的照样放行
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre")) is None
    del ts["owner_rework"]
    ts["audit_pre"].update(target="门禁端")  # 只退回一个：照旧
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre")) is None
    assert "没有一审或终审退回" in kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract"))
    # 终审退回门禁端与执行端：热修补先走，执行端等门禁重新交付
    ts = locked(make_ts())
    ts["audit_post"].update(verdict="返工", target="门禁端、执行端")
    assert kh.hotfix_reason(ts) == "终审退回门禁端"
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre")) is None
    assert "先返工最上游的 3-gate-pre" in kh.guard(ts, meta("返工", "exec-step", "T001-5-exec"))
    ts["audit_post"].update(target="合同端、门禁端")  # 门禁端不在第一个也认
    assert kh.hotfix_reason(ts) == "终审退回门禁端"
    ts["audit_post"].update(target="合同端、门禁端、执行端")  # 两处上游：点名最上游的
    assert "先返工最上游的 2-contract" in kh.guard(ts, meta("返工", "exec-step", "T001-5-exec"))
    ts["audit_post"].update(target="执行端")
    assert kh.hotfix_reason(ts) is None and kh.guard(ts, meta("返工", "exec-step", "T001-5-exec")) is None
    ts["audit_post"].update(target="合同端、执行端")
    assert kh.guard(ts, meta("返工", "contract-glm", "T001-2-contract")) is None
    assert "先返工最上游的 2-contract" in kh.guard(ts, meta("返工", "exec-step", "T001-5-exec"))
    ts["audit_post"].update(verdict="通过")
    assert "没有执行之后的失败记录" in kh.guard(ts, meta("返工", "exec-step", "T001-5-exec"))
    assert "“、”隔开" in kh.ROLE_EXTRA_OUTPUT["audit"]
    assert "合同端、门禁端" in (kh.TEMPLATE_DIR / "worker.md").read_text(encoding="utf-8")


def test_claude_workers_return_to_the_workspace_after_each_command(tmp_path, monkeypatch):
    # 第 28 轮：门禁 cd 进主工作区之后，碰工作目录的命令都要审批，没人能答就全被拒
    monkeypatch.setitem(kh.ROSTER, "gate-sonnet", CLAUDE_GATE)
    hub = kh.Hub(tmp_path)
    hub.ensure()
    seen = []

    def launcher(cmd, cwd, env, out, err, timeout):
        seen.append(env)
        return {"exit_code": 0, "timed_out": False, "wall_seconds": 1.0}

    runner = kh.TurnRunner(hub, launcher=launcher)
    runner.run("gate-sonnet", "T001-3-gate-pre", tmp_path / "ws", "角色", "输入")
    assert seen[-1]["CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR"] == "1"
    runner.run("contract-glm", "T001-2-contract", tmp_path / "ws", "角色", "输入")
    assert "CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR" not in seen[-1]
    worker = (kh.TEMPLATE_DIR / "worker.md").read_text(encoding="utf-8")
    assert "不要 `cd` 到别处" in worker and "git -C" in worker


def test_new_attempt_gate_post_starts_from_the_previous_whitebox(tmp_path):
    # 第 28 轮：返工之后候选 worktree 是新建的，T006 的门禁自己 cp 上一轮的白盒测试，被拒之后整回合什么都没跑
    hub = kh.Hub(tmp_path)
    hub.ensure()
    ts = locked(make_ts())
    ts["exec"]["run_dir"] = str(tmp_path / "runs" / "attempt-002")
    ts["workspaces"]["post-attempt-002"] = {"patched": True}
    workspace = tmp_path / "post"
    workspace.mkdir()
    target = workspace / kh.gate_file(ts, "whitebox")
    assert kh.seed_whitebox(hub, ts, workspace) is None and not target.exists()  # 第一轮：没有上一份
    evidence = hub.task_dir("T001-6-gate-post") / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "whitebox-20261020T090000000000Z.py").write_text("old = 1\n", encoding="utf-8")
    (evidence / "whitebox-20261020T141324849895Z.py").write_text("latest = 1\n", encoding="utf-8")
    (evidence / "whitebox-20261020T141324849895Z.log").write_text("1 passed\n", encoding="utf-8")
    (evidence / "whitebox-20261020T150000000000Z.log").write_text("1 passed\n", encoding="utf-8")  # 只认 .py
    seeded = kh.seed_whitebox(hub, ts, workspace)
    assert seeded == ".agent/mailbox/tasks/T001-6-gate-post/evidence/whitebox-20261020T141324849895Z.py"
    assert target.read_text(encoding="utf-8") == "latest = 1\n"
    assert ts["workspaces"]["post-attempt-002"]["whitebox_seeded"] == seeded
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert [e["source"] for e in events if e["event"] == "whitebox.seeded"] == [seeded]
    target.unlink()  # 门禁删了它：不再放
    assert kh.seed_whitebox(hub, ts, workspace) is None and not target.exists()
    ts["workspaces"]["post-attempt-002"] = {"patched": True}
    target.write_text("mine = 1\n", encoding="utf-8")  # 工作目录里已经有：不覆盖
    assert kh.seed_whitebox(hub, ts, workspace) is None
    assert target.read_text(encoding="utf-8") == "mine = 1\n"
    assert "whitebox_seeded" not in ts["workspaces"]["post-attempt-002"]
    ts["workspaces"]["post-attempt-002"]["whitebox_seeded"] = seeded
    prompt = kh.turn_prompt(hub, ts, "gate-sonnet", "T001-6-gate-post", [], workspace)
    assert "内核已把上一轮的白盒测试（%s）放进工作目录" % seeded in prompt
    del ts["workspaces"]["post-attempt-002"]["whitebox_seeded"]
    assert "上一轮的白盒测试" not in kh.turn_prompt(hub, ts, "gate-sonnet", "T001-6-gate-post", [], workspace)
    ts["workspaces"]["post-attempt-002"]["whitebox_seeded"] = seeded
    assert "上一轮的白盒测试" not in kh.turn_prompt(hub, ts, "gate-sonnet", "T001-3-gate-pre", [], workspace)


def test_gate_post_workspace_is_seeded_before_the_gate_starts(engine_env, monkeypatch):
    hub = engine_env
    state = hub.load_state()
    ts = state["tasks"]["T001"]
    calls = []
    monkeypatch.setattr(kh, "apply_candidate", lambda hub, ts: hub.repo / "post")
    monkeypatch.setattr(kh, "seed_whitebox", lambda hub, ts, workspace: calls.append(workspace))
    engine = kh.Engine(hub)
    assert engine.stage_workspace(ts, "gate-sonnet", "6-gate-post") == hub.repo / "post"
    assert calls == [hub.repo / "post"]
    assert engine.stage_workspace(ts, "audit-sonnet", "7-audit-post") == hub.repo / "post"
    assert calls == [hub.repo / "post"]  # 终审不放：白盒测试是门禁的


# ---------------------------------------------------------------------------
# 第 35 轮：等锁不算出错、卡住的阶段能恢复、超时与门禁热修补之后接着改候选
# ---------------------------------------------------------------------------

def exec_letter(hub, kind="开工"):
    hub.deliver({"from": kh.COORDINATOR, "to": "exec-step", "task-id": "T001-5-exec", "in-reply-to": "none",
                 "type": kind}, fields())
    state = hub.load_state()
    state["tasks"]["T001"]["stages"]["5-exec"]["status"] = "assigned"
    hub.save_state(state)


def test_exec_waits_for_the_landing_lock_by_holding_its_letter(engine_env, monkeypatch):
    # T009 的执行端等站主的 exclusive 等满一小时，回合出错，阶段卡在 assigned，要站主恢复
    hub = engine_env
    monkeypatch.setattr(kh, "EXEC_LAND_WAIT_SECONDS", 0.2)
    monkeypatch.setattr(kh, "carry_source", lambda hub_, ts: pytest.fail("拿到锁之前不该建返工版本"))
    exec_letter(hub)
    engine = kh.Engine(hub, FakeRunner([]))
    with kh.DirLock(hub.root / ".land", wait_seconds=1.0):
        assert engine.step() is True
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["stages"]["5-exec"]["status"] == "paused" and "落地锁被占" in ts["stages"]["5-exec"]["note"]
    assert ts["held"][0]["agent"] == "exec-step" and ts["held"][0]["suffix"] == "5-exec"
    assert hub.unread(kh.OWNER) == [] and hub.unread(kh.COORDINATOR) == [] and hub.unread("exec-step") == []
    assert not (kh.exec_marks(hub) / "T001.json").exists()
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert [e["reason"] for e in events if e["event"] == "letters.held"][0].startswith("落地锁被占")
    assert "step.error" not in [e["event"] for e in events]
    make_held_due(hub)
    assert kh.release_held(hub) == ["T001"] and len(hub.unread("exec-step")) == 1

    def fake_exec(hub_, ts):
        ts["exec"] = {"run_dir": "attempt-001", "check_ok": True}
        return fields(摘要="执行端完成")

    monkeypatch.setattr(kh, "run_exec", fake_exec)
    monkeypatch.setattr(kh, "rehearse_landing", lambda hub_, ts: None)
    assert engine.step() is True
    assert hub.load_state()["tasks"]["T001"]["stages"]["5-exec"]["status"] == "delivered"


def test_a_crashed_worker_turn_leaves_the_stage_restartable(engine_env, monkeypatch):
    hub = engine_env
    state = hub.load_state()
    ts = locked(state["tasks"]["T001"])
    ts["audit_pre"].update(verdict="通过", contract_sha256="c1", oracle_sha="o" * 40)
    ts["stages"]["4-audit-pre"]["status"] = "delivered"
    hub.save_state(state)
    exec_letter(hub)

    def boom(hub_, ts_):
        raise kh.HubError("prepare 里 git 出错")

    monkeypatch.setattr(kh, "run_exec", boom)
    assert kh.Engine(hub, FakeRunner([])).step() is True
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["stages"]["5-exec"]["status"] == "failed" and "git 出错" in ts["stages"]["5-exec"]["note"]
    owner = hub.unread(kh.OWNER)[0].read_text(encoding="utf-8")
    assert "type: 阻塞" in owner and "阶段 T001-5-exec 已标成 failed" in owner
    assert kh.guard(ts, meta("开工", "exec-step", "T001-5-exec")) is None  # 站主回信后协调人能重发开工
    engine = kh.Engine(hub)
    hub.deliver({"from": "planner-opus", "to": kh.COORDINATOR, "task-id": "T001-1-plan", "in-reply-to": "none",
                 "type": "提问"}, fields())
    state = hub.load_state()
    state["tasks"]["T001"]["stages"]["1-plan"].update(status="assigned", last_letter="提问")
    hub.save_state(state)
    # 协调人的回合出事：信是工人发来的，那个阶段停着等回信，不是卡住，不标
    assert engine.fail_stage(kh.COORDINATOR, hub.unread(kh.COORDINATOR), "x") is None
    assert engine.fail_stage("planner-opus", hub.unread(kh.COORDINATOR), "x") is None  # 停着等回信也不算卡住
    state = hub.load_state()
    state["tasks"]["T001"]["stages"]["1-plan"].pop("last_letter")  # 规划端正在办
    hub.save_state(state)
    assert engine.fail_stage(kh.COORDINATOR, hub.unread(kh.COORDINATOR), "x") is None  # 协调人出事不碰工人的阶段
    assert hub.load_state()["tasks"]["T001"]["stages"]["1-plan"]["status"] == "assigned"


def test_owner_unsticks_a_stage_nobody_is_working_on(tmp_path):
    import argparse
    import os
    repo, head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    ts = locked(kh.new_task_state("T001", "doc", "改文档", head, True))
    ts["stages"]["5-exec"]["status"] = "assigned"
    hub.save_state({"tasks": {"T001": ts}})
    args = argparse.Namespace(repo=str(repo), task="T001", stage="5-exec", reason="等落地锁超时，回合出错")
    run = repo / ".agent" / "runs" / "t001-doc" / "attempt-001"
    run.mkdir(parents=True)
    (run / "state.json").write_text(json.dumps({"state": "RUNNING"}), encoding="utf-8")
    with pytest.raises(kh.HubError, match="还在跑（attempt-001）"):
        kh.cmd_task_unstick(args)
    (run / "state.json").write_text(json.dumps({"state": "NEEDS_REVIEW"}), encoding="utf-8")
    kh.exec_marks(hub).mkdir(parents=True)
    mark = kh.exec_marks(hub) / "T001.json"
    mark.write_text(json.dumps({"pid": os.getpid(), "task": "T001"}), encoding="utf-8")
    with pytest.raises(kh.HubError, match="还在跑（执行标记）"):
        kh.cmd_task_unstick(args)
    mark.unlink()
    for bad in ({"reason": " "}, {"stage": "9-x"}, {"task": "T009"}):
        with pytest.raises(kh.HubError):
            kh.cmd_task_unstick(argparse.Namespace(**dict(vars(args), **bad)))
    assert kh.cmd_task_unstick(args) == kh.EXIT_OK
    stage = hub.load_state()["tasks"]["T001"]["stages"]["5-exec"]
    assert stage["status"] == "failed" and "等落地锁超时" in stage["note"]
    letter = hub.unread(kh.COORDINATOR)[0].read_text(encoding="utf-8")
    assert "type: 核验" in letter and "T001-5-exec 标成了 failed" in letter and "exec-step 重发开工" in letter
    with pytest.raises(kh.HubError, match="没有卡在"):
        kh.cmd_task_unstick(args)
    state = hub.load_state()
    state["tasks"]["T001"]["stages"]["5-exec"].update(status="assigned", last_letter="提问")
    hub.save_state(state)
    with pytest.raises(kh.HubError, match="没有卡在"):  # 工人发了提问：停着等回信，不是卡住
        kh.cmd_task_unstick(args)


def test_owner_ordered_gate_rework_is_a_hotfix_and_holds_the_executor_back():
    # T010：站主查出门禁自相矛盾、要门禁返工，执行端正好交付，协调人照例重派会在要改的门禁上用掉预算
    ts = locked(make_ts())
    ts["audit_pre"].update(verdict="通过", contract_sha256="c1", oracle_sha="o" * 40)
    ts["stages"]["4-audit-pre"]["status"] = "delivered"
    ts["exec"].update(run_dir="r", check_ok=False, conflicts=0)
    ts["stages"]["5-exec"]["status"] = "failed"
    assert kh.hotfix_reason(ts) is None and kh.guard(ts, meta("返工", "exec-step", "T001-5-exec")) is None
    ts["owner_rework"] = {"suffix": "3-gate-pre"}
    assert kh.hotfix_reason(ts) == "站主指定门禁返工"
    for kind, to, task in (("返工", "exec-step", "T001-5-exec"), ("开工", "audit-sonnet", "T001-4-audit-pre")):
        assert "站主指定了 3-gate-pre 返工，还没发" in kh.guard(ts, meta(kind, to, task))
    assert kh.guard(ts, meta("返工", "gate-sonnet", "T001-3-gate-pre")) is None
    ts["exec"] = {}
    assert kh.hotfix_reason(ts) is None  # 还没执行过：普通的门禁返工


def timed_out(run_dir, violations=()):
    (run_dir / "state.json").write_text(json.dumps({"state": "TIMEOUT"}), encoding="utf-8")
    (run_dir / "scope.json").write_text(json.dumps({"violations": list(violations)}), encoding="utf-8")


def test_a_timed_out_attempt_is_continued_instead_of_restarted(tmp_path, monkeypatch):
    # T010 的 attempt-001 跑满 7200s 时只差一条用例和执行报告（A37 M5、越界 0），重派却从 base_sha 从头来
    repo, hub, ts, plans, previous = rework_setup(tmp_path)
    failed_checks(previous)
    timed_out(previous)
    ts["exec"], ts["audit_post"] = {"run_dir": str(previous), "check_ok": False, "status": "TIMEOUT"}, {}
    v1 = plans / "t001-doc.v1.md"
    v1.write_text(v1.read_text(encoding="utf-8") + "\n## Retry（重派第 1 次，内核追加）\n\n- 这一轮从合同的 base_sha 重新开始\n"
                  "\n## Notes\n- 合同自己的一节\n", encoding="utf-8")
    rework, calls = "a" * 40, []

    def fake_pd(hub_, args, timeout=600):
        calls.append(args[0] if args[0] != "prepare" else "prepare " + args[1])
        if args[0] == "verdict":
            assert args[args.index("--class") + 1] == "TIMEOUT"
            (previous / "state.json").write_text(json.dumps({"state": "REVISE"}), encoding="utf-8")
        if args[0] == "branch":
            return 0, "commit=%s branch=pi-rework/x" % rework
        return (9, "prepare 停在这里") if args[0] == "prepare" else (0, "ok")

    monkeypatch.setattr(kh, "run_pd", fake_pd)
    monkeypatch.setattr(kh, "contract_requirements", lambda hub_, ts_: [])
    monkeypatch.setattr(kh, "rework_added_files", lambda hub_, ts_: [])
    kh.run_exec(hub, ts)
    assert calls == ["verdict", "branch", "derive-json", "validate", "prepare t001-doc.v2"]
    v2 = (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    assert "- base_sha: %s" % rework in v2 and "上一轮跑满了时限" in v2 and "调度器 `branch --rework`" in v2
    assert "## Retry" not in v2 and "从合同的 base_sha 重新开始" not in v2 and "- 合同自己的一节" in v2
    assert "### 上一轮没过的地方" in v2 and "- V01：退出码 1 ≠ 期望 0" in v2 and "门禁端在上一轮之后" not in v2
    assert ts["rework_chain"][-1]["why"] == "timeout" and "retry_notes" not in ts
    # 越界的、或检查没过而自己收了尾的：照旧从基线重来（第 19 轮的理由不变）
    for state, violations in (("TIMEOUT", [{"path": "x", "kind": "out_of_scope", "detail": "d"}]), ("NEEDS_REVIEW", [])):
        timed_out(previous, violations)
        (previous / "state.json").write_text(json.dumps({"state": state}), encoding="utf-8")
        assert kh.carry_source(hub, dict(ts, exec={"run_dir": str(previous), "check_ok": False}, audit_post={})) is None
    shutil.rmtree(previous / "checks")
    passed_checks(previous)  # 检查全过、执行阶段的记录还在（例如战后门禁没过）：照旧，不在这里接着改
    assert kh.carry_source(hub, dict(ts, exec={"run_dir": str(previous), "check_ok": True}, audit_post={})) is None
    (previous / "candidate.patch").write_text("", encoding="utf-8")
    timed_out(previous)
    assert kh.carry_source(hub, dict(ts, exec={"run_dir": str(previous)}, audit_post={})) is None  # 没有候选


def passed_checks(run_dir):
    folder = run_dir / "checks" / "01"
    folder.mkdir(parents=True)
    (folder / "checks.json").write_text(json.dumps({"results": [{"id": "V01", "status": "passed"}]}), encoding="utf-8")


def test_carry_after_an_upstream_redelivery_finds_the_latest_usable_attempt(tmp_path):
    repo, hub, ts, plans, first = rework_setup(tmp_path)
    ts["exec"], ts["audit_post"] = {}, {}
    ts["contract"].update(written_version=1)
    runs = first.parent
    for name, state in (("attempt-001", "TIMEOUT"), ("attempt-002", "NEEDS_REVIEW")):
        run = runs / name
        run.mkdir(exist_ok=True)
        (run / "candidate.patch").write_text("diff --git a/x b/x\n", encoding="utf-8")
        (run / "meta.json").write_text(json.dumps({"plan_version": 1}), encoding="utf-8")
        timed_out(run)
        (run / "state.json").write_text(json.dumps({"state": state}), encoding="utf-8")
    failed_checks(runs / "attempt-002")  # 被站主停掉、检查没过：跳过，接着往前找
    assert kh.carry_source(hub, ts) == (runs / "attempt-001", "upstream")
    shutil.rmtree(runs / "attempt-002" / "checks")
    passed_checks(runs / "attempt-002")
    assert kh.carry_source(hub, ts) == (runs / "attempt-002", "upstream")  # 最近的优先
    (runs / "attempt-002" / "state.json").write_text(json.dumps({"state": "REVISE"}), encoding="utf-8")
    assert kh.carry_source(hub, ts) is None  # 已经有去处的之前都不再看
    (runs / "attempt-002" / "state.json").write_text(json.dumps({"state": "RUNNING"}), encoding="utf-8")
    assert kh.carry_source(hub, ts) == (runs / "attempt-001", "upstream")  # 还在跑的不算
    ts["contract"]["written_version"] = 2  # 合同端重写过：旧合同下的候选不接着改
    assert kh.carry_source(hub, ts) is None


def test_a_gate_hotfix_moves_the_candidate_onto_the_new_baseline(tmp_path, monkeypatch):
    # T009：终审退回门禁端与执行端，门禁热修补把执行阶段的记录清掉，执行端开工就要从头重写一份只差三个 import 的候选
    repo, _head = git_repo(tmp_path)
    monkeypatch.setattr(kh, "worktree_root", lambda repo_: tmp_path / "wt")
    (tmp_path / "wt").mkdir()
    gate = "tests/test_gate_t001_baseline.py"
    head = land_on_main(repo, "src/page.css", ".a {}\n", "共享样式")
    branch = kh.git(["rev-parse", "--abbrev-ref", "HEAD"], repo).strip()
    kh.git(["checkout", "-q", "-b", "old"], repo)
    land_on_main(repo, gate, "def test_v1():\n    assert False\n", "旧门禁")
    earlier = land_on_main(repo, "src/earlier.tsx", "export const Earlier = 0;\n", "上一轮的返工提交")
    (repo / "src" / "page.tsx").write_text("export const Page = 1;\n", encoding="utf-8")
    (repo / "src" / "page.css").write_text(".a { color: red; }\n", encoding="utf-8")
    kh.git(["add", "src"], repo)
    kh.git(["commit", "-q", "-m", "候选"], repo)
    tree = kh.git(["rev-parse", "HEAD^{tree}"], repo).strip()
    patch = kh.git(["diff", "--binary", earlier, "HEAD"], repo)
    kh.git(["checkout", "-q", branch], repo)
    kh.git(["checkout", "-q", "-b", "new"], repo)
    new_oracle = land_on_main(repo, gate, "def test_v2():\n    assert False\n", "热修补后的门禁")
    kh.git(["checkout", "-q", branch], repo)
    hub = kh.Hub(repo)
    hub.ensure()
    run = repo / ".agent" / "runs" / "t001-doc" / "attempt-001"
    run.mkdir(parents=True)
    (run / "meta.json").write_text(json.dumps({"base_sha": earlier, "plan_version": 1}), encoding="utf-8")
    (run / "candidate.json").write_text(json.dumps({"tree": tree}), encoding="utf-8")
    (run / "candidate.patch").write_text(patch, encoding="utf-8", newline="\n")
    (run / "state.json").write_text(json.dumps({"state": "NEEDS_REVIEW"}), encoding="utf-8")
    (run / "scope.json").write_text(json.dumps({"violations": []}), encoding="utf-8")
    passed_checks(run)
    plans = repo / ".agent" / "plans"
    plans.mkdir(parents=True)
    (plans / "t001-doc.v2.md").write_text("# TASK: t001-doc\n- plan_version: 2\n- base_sha: %s\n" % new_oracle,
                                          encoding="utf-8")
    (plans / "t001-doc.v2.json").write_text(json.dumps({"budget": {
        "max_attempts_total": 3, "max_wall_seconds_per_attempt": 3600, "max_wall_seconds_total": 10800}}),
        encoding="utf-8")
    ts = locked(kh.new_task_state("T001", "doc", "改文档", head, True))
    ts["contract"] = {"key": "t001-doc.v2", "version": 2, "written_version": 1}  # 热修补升的版，还没派遣
    ts["oracle"].update(sha=new_oracle, files=[gate])
    ts["rework_chain"] = [{"from": "attempt-000", "commit": earlier, "contract": "t001-doc.v1"}]
    ts["audit_history"] = [{"stage": "7-audit-post", "verdict": "返工", "target": "门禁端、执行端",
                            "blockers": "B1 page.css 没 import", "at": "2999-01-01T00:00:00Z"}]
    calls = []

    def fake_pd(hub_, args, timeout=600):
        calls.append(args[0] if args[0] != "prepare" else "prepare " + args[1])
        assert args[0] != "branch", "候选建在旧门禁上：不能用 branch --rework"
        if args[0] == "verdict":
            assert args[args.index("--class") + 1] == "EXECUTION_ERROR"
            (run / "state.json").write_text(json.dumps({"state": "REVISE"}), encoding="utf-8")
        return (9, "prepare 停在这里") if args[0] == "prepare" else (0, "ok")

    monkeypatch.setattr(kh, "run_pd", fake_pd)
    monkeypatch.setattr(kh, "contract_requirements", lambda hub_, ts_: [])
    monkeypatch.setattr(kh, "rework_added_files", lambda hub_, ts_: [])
    kh.run_exec(hub, ts)
    assert calls == ["verdict", "derive-json", "validate", "prepare t001-doc.v2"]  # 没派遣过：就地改，不升版
    sha = ts["rework_chain"][-1]["commit"]
    assert kh.git(["rev-parse", sha + "^"], repo).strip() == new_oracle
    assert kh.git(["show", "%s:%s" % (sha, gate)], repo) == "def test_v2():\n    assert False\n"
    assert kh.git(["show", sha + ":src/page.tsx"], repo) == "export const Page = 1;\n"
    assert kh.git(["show", sha + ":src/page.css"], repo) == ".a { color: red; }\n"
    assert kh.git(["show", sha + ":src/earlier.tsx"], repo) == "export const Earlier = 0;\n"  # 之前返工链的改动也在
    assert kh.git(["rev-parse", "refs/themis/rework/t001-doc/attempt-001"], repo).strip() == sha
    assert ts["rework_chain"] == [dict(ts["rework_chain"][0], why="upstream", rebuilt=True)]
    assert ts["rework_chain_superseded"][0]["commit"] == earlier  # 旧链的改动已经含在新提交里，落地不再挑它
    v2 = (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    assert "- base_sha: %s" % sha in v2 and "内核把它搬到当前基准测试上" in v2 and "门禁端在上一轮之后改过基准测试" in v2
    assert "B1 page.css 没 import" in v2 and "上一轮跑满了时限" not in v2
    assert list((tmp_path / "wt").iterdir()) == []
    # 放不上去：如实报告，不派遣
    (run / "state.json").write_text(json.dumps({"state": "NEEDS_REVIEW"}), encoding="utf-8")
    land_on_main(repo, "src/page.css", ".a { color: blue; }\n", "别的片改了同一行")
    ts["oracle"]["sha"] = kh.git(["rev-parse", "HEAD"], repo).strip()
    ts["rework_chain"], ts["exec"] = [], {}
    calls.clear()
    out = kh.run_exec(hub, ts)
    assert calls == ["verdict"] and "放不到基准测试" in out["验证"] and "src/page.css" in out["验证"]


def test_carried_candidate_gets_only_the_final_review_blockers_raised_after_it(tmp_path):
    run = tmp_path / "attempt-001"
    run.mkdir()
    (run / "candidate.patch").write_text("diff\n", encoding="utf-8")
    ts = {"audit_history": [
        {"stage": "7-audit-post", "verdict": "返工", "target": "执行端", "blockers": "B0 上一个候选的", "at": "2000-01-01T00:00:00Z"},
        {"stage": "4-audit-pre", "verdict": "返工", "target": "执行端", "blockers": "一审的", "at": "2999-01-01T00:00:00Z"},
        {"stage": "7-audit-post", "verdict": "返工", "target": "门禁端", "blockers": "只退门禁端", "at": "2999-01-01T00:00:00Z"},
        {"stage": "7-audit-post", "verdict": "通过", "target": "执行端", "blockers": "通过的", "at": "2999-01-01T00:00:00Z"}]}
    assert kh.returned_blockers(ts, run) == ""
    ts["audit_history"].insert(1, {"stage": "7-audit-post", "verdict": "返工", "target": "门禁端、执行端",
                                   "blockers": "B1 这个候选的", "at": "2999-01-01T00:00:00Z"})
    assert kh.returned_blockers(ts, run) == "B1 这个候选的"


def test_facts_checked_before_the_plan_is_delivered_says_why(tmp_path):
    import argparse
    repo, head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    hub.save_state({"tasks": {"T001": kh.new_task_state("T001", "doc", "改文档", head, True)}})
    body = tmp_path / "reply.md"
    body.write_text("Q1 选 A；F4 核实过了\n", encoding="utf-8")
    args = argparse.Namespace(repo=str(repo), task="T001", type="回复", reply_to=None, rework=None,
                              facts_checked=True, file=str(body))
    with pytest.raises(kh.HubError, match="规划端还没交付，事实在交付时才登记"):
        kh.cmd_send(args)


# ---------------------------------------------------------------------------
# 第 36 轮：只有规划端留在 claude 上，门禁端到了 pi 上要另设护栏
# ---------------------------------------------------------------------------

def test_pi_workers_run_their_rostered_model_and_tools(tmp_path):
    hub = kh.Hub(tmp_path)
    hub.ensure()
    seen = []

    def launcher(cmd, cwd, env, out, err, timeout):
        seen.append((cmd, cwd, timeout))
        return {"exit_code": 0, "timed_out": False, "wall_seconds": 1.0}

    runner = kh.TurnRunner(hub, launcher=launcher)
    for agent, key in ((kh.COORDINATOR, "T001"), ("contract-glm", "T001-2-contract"), ("gate-sonnet", "T001-3-gate-pre"),
                       ("audit-sonnet", "T001-4-audit-pre")):
        runner.run(agent, key, tmp_path / "ws", "角色", "输入")
        cmd, cwd, timeout = seen[-1]
        spec = kh.ROSTER[agent]
        assert cmd[cmd.index("--provider") + 1] == spec["provider"] and cmd[cmd.index("--model") + 1] == spec["model"]
        assert cmd[cmd.index("--thinking") + 1] == spec["thinking"] and cmd[cmd.index("--tools") + 1] == ",".join(spec["tools"])
        assert cwd == tmp_path / "ws" and timeout == spec["timeout"] and "claude" not in Path(cmd[0]).name
    assert seen[2][0][seen[2][0].index("--tools") + 1] == "read,grep,find,ls,edit,write,bash"  # 门禁端要写测试、跑测试
    assert all("write" not in cmd[cmd.index("--tools") + 1] for cmd, _cwd, _t in (seen[0], seen[1], seen[3]))


def test_pi_workers_may_not_write_outside_their_worktree(tmp_path):
    repo, ws = tmp_path / "Repo", tmp_path / "Repo" / "wt"  # 测试里工作目录在仓库里：提到工作目录本身不算碰主工作区
    ws.mkdir(parents=True)
    spec = {"tools": ["read", "write", "edit", "bash"], "provider": "p", "model": "m"}

    def call(name, **args):
        return {"type": "tool_execution_start", "toolCallId": "c-%s" % name, "toolName": name, "args": args}

    def audit(*events):
        return kh.audit_pi_stream(stream(*events), spec, ws, repo)

    fine = audit(call("write", path="tests/test_gate_t001_baseline.py"), call("edit", path=str(ws / "a.py")),
                 call("read", path=str(repo / ".agent" / "plans" / "t001.v1.md")),
                 call("bash", command="cd %s && python -m pytest -q tests" % str(ws).replace("\\", "/")),
                 call("bash", command="npm test"))
    assert fine["violations"] == [] and fine["warnings"] == []
    looked = audit(call("bash", command="cat %s | head -20" % (repo / ".agent" / "plans" / "a.md")),
                   call("bash", command="grep -n x /%s%s/scripts/kit_hub.py" % (str(repo)[0], str(repo)[2:].replace("\\", "/"))))
    assert looked["violations"] == [] and len(looked["warnings"]) == 2 and "主工作区" in looked["warnings"][0]
    # 第 41 轮：T012 门禁端的 `ls "<主工作区>/desktop/web/" 2>&1 | head` 被当成写入，整回合作废
    main = str(repo).replace("\\", "/")
    quiet = audit(call("bash", command='ls "%s/desktop/web/" 2>&1 | head -20; echo "---"' % main),
                  call("bash", command='cd "%s" && ls "%s/.agent/" 2>/dev/null' % (str(ws).replace("\\", "/"), main)),
                  call("bash", command="cat %s/a.md >&2 &>NUL; ls %s 2>>/dev/null" % (main, main)))
    assert quiet["violations"] == [] and len(quiet["warnings"]) == 3
    # 第 45 轮：T011 门禁端的 grep 模式里有 \|，按引号里的 | 切开之后 `require("` 不是只读命令，整回合作废
    quoted = audit(call("bash", command='cd "%s" && grep -n "readFileSync\\|require(" tests/a.py | head; echo ===' % main),
                   call("bash", command="grep -n 'a > b; rm -rf x' %s/f.py" % main),
                   call("bash", command='grep -n "say \\"hi\\" > x" %s/f.py' % main),
                   call("bash", command="grep -n a\\|b %s/f.py" % main))
    assert quoted["violations"] == [] and len(quoted["warnings"]) == 4
    segments, bare = kh.split_unquoted('a "x|y" | b && c; d || e & f')
    assert segments == ['a "x|y"', "b", "c", "d", "e", "f"] and "x" not in bare and bare.split() == list("abcdef")
    for event in (call("write", path="../outside.py"), call("edit", path=str(repo / "scripts" / "kit_hub.py")),
                  call("bash", command="ls %s 2>/dev/nullx" % main),  # 不是空设备：照旧算写入
                  call("bash", command="cat %s/a 2>&1 > out.txt" % main),
                  call("bash", command="cd %s && rm -rf tests" % main),
                  call("bash", command='grep -n "x|y" %s/f.py | tee out.txt' % main),  # 引号外的管道照样切
                  call("bash", command="echo 'a' > %s/f.py" % main),  # 引号外的 > 照样算写入
                  call("write", path=str(tmp_path / "Repo" / "wtx" / "a.py")),
                  call("bash", command="cp a.py %s" % (repo / "scripts")),
                  call("bash", command="cat x > %s" % str(repo / "y").replace("\\", "/")),
                  call("bash", command="sed -i s/a/b/ %s" % (repo / "z")),
                  call("bash", command="ls && git -C %s checkout ." % str(repo).upper())):
        assert len(audit(event)["violations"]) == 1, event
    assert kh.audit_pi_stream(stream(call("write", path="../x")), spec)["violations"] == []  # 没给工作目录：照旧
    # 回合里也这样审：门禁端的回合写到工作目录之外，整回合作废
    hub = kh.Hub(repo)
    hub.ensure()
    gate = kh.ROSTER["gate-sonnet"]
    done = {"type": "message_end", "message": {"role": "assistant", "provider": gate["provider"], "model": gate["model"],
                                               "stopReason": "stop", "content": [
                                                   {"type": "text", "text": "```json\n{\"letters\": []}\n```"}]}}

    def launcher(cmd, cwd, env, out, err, timeout):
        out.write(("\n".join(stream(call("write", path="../outside.py"), done)) + "\n").encode("utf-8"))
        return {"exit_code": 0, "timed_out": False, "wall_seconds": 1.0}

    turn = kh.TurnRunner(hub, launcher=launcher).run("gate-sonnet", "T001-3-gate-pre", ws, "角色", "输入")
    assert turn["violations"] == ["write 写到了工作目录之外：../outside.py"] and turn["output"] is None


def test_unsent_contracts_get_the_rostered_executor_line(tmp_path, monkeypatch):
    # 本机的 step-5-preview 从 step 回到 bb：T009、T010 的合同写着 step/step-5-preview，接着改时 validate 不过
    hub = kh.Hub(tmp_path)
    hub.ensure()
    plans = tmp_path / ".agent" / "plans"
    plans.mkdir(parents=True)
    md = plans / "t001-doc.v3.md"
    md.write_text("# TASK: t001-doc\n## Identity\n- executor: step/step-5-preview · thinking high\n- base_sha: x\n",
                  encoding="utf-8")
    ts = make_ts()
    ts["contract"] = {"key": "t001-doc.v3", "version": 3}
    monkeypatch.setattr(kh, "run_pd", lambda hub_, args, timeout=600: (0, "ok"))
    monkeypatch.setattr(kh, "contract_requirements", lambda hub_, ts_: [])
    assert kh.revalidate_contract(hub, ts) == []
    assert "- executor: bb/step-5-preview · thinking high\n- base_sha: x" in md.read_text(encoding="utf-8")
    events = [json.loads(line) for line in hub.ledger().read_text(encoding="utf-8").splitlines()]
    assert [e["previous"] for e in events if e["event"] == "contract.executor_synced"] == [
        "- executor: step/step-5-preview · thinking high"]
    assert kh.sync_executor_line(hub, ts) is None  # 已经一致
    md.write_text(md.read_text(encoding="utf-8").replace("bb/", "step/"), encoding="utf-8")
    ts["contract"]["dispatched"] = True  # 派遣过的版本只增不改
    assert kh.sync_executor_line(hub, ts) is None and "step/" in md.read_text(encoding="utf-8")


def test_a_throttled_pi_turn_is_held_with_a_growing_backoff(tmp_path):
    # 第 38 轮：T012 的协调人（pi 上的 qwen）回 429 throttling，没有解除时刻，内核当成接口故障、主任务转 blocked
    hub = kh.Hub(tmp_path)
    hub.ensure()
    spec = kh.ROSTER[kh.COORDINATOR]
    answers = []

    def message(error):
        body = {"role": "assistant", "provider": spec["provider"], "model": spec["model"], "content": [
            {"type": "text", "text": "" if error else "```json\n{\"letters\": []}\n```"}], "stopReason": "error" if error else "stop"}
        if error:
            body["errorMessage"] = error
        return {"type": "message_end", "message": body}

    def launcher(cmd, cwd, env, out, err, timeout):
        out.write((json.dumps(message(answers.pop(0))) + "\n").encode("utf-8"))
        return {"exit_code": 0, "timed_out": False, "wall_seconds": 1.0}

    runner = kh.TurnRunner(hub, launcher=launcher)
    throttle = '429 {"error":{"code":"throttling","message":"usage allocated quota exceeded. please try again later."}}'
    waits = []
    for error in [throttle, throttle, None, throttle] + [throttle] * 5 + [None, "500 internal error"]:
        answers.append(error)
        before = int(time.time())
        turn = runner.run(kh.COORDINATOR, "T001", tmp_path, "角色", "输入")
        waits.append(None if turn["rate_limited_until"] is None else turn["rate_limited_until"] - before)
        assert (turn["output"] is None) == bool(error)
    assert [w if w is None else round(w / 300) * 300 for w in waits] == [
        300, 600, None, 300, 600, 1200, 2400, 3600, None, None, None]  # 成功一回清零；连着 5 次之后交给站主；别的报错不扣
    assert kh.ROSTER["planner-opus"]["adapter"] == "claude"  # claude 有自己的 rate_limit_event（第 33 轮），不走这里


def test_state_writes_and_reads_wait_out_a_sharing_violation(tmp_path, monkeypatch):
    # 第 37 轮：T010 的协调人回合替换 state.json 时撞上 WinError 5（别的进程正读着），回合出错，临时文件留在 ledger 里
    monkeypatch.setattr(kh, "SHARING_PAUSE", 0)
    real_replace, fails = kh.os.replace, {"n": 2}

    def flaky_replace(src, dst):
        if fails["n"]:
            fails["n"] -= 1
            raise PermissionError(5, "Access is denied")
        return real_replace(src, dst)

    monkeypatch.setattr(kh.os, "replace", flaky_replace)
    target = tmp_path / "state.json"
    kh.write_text_atomic(target, "{}")
    assert target.read_text(encoding="utf-8") == "{}" and fails["n"] == 0
    fails["n"] = kh.SHARING_RETRIES
    with pytest.raises(PermissionError):
        kh.write_text_atomic(target, '{"x": 1}')
    assert target.read_text(encoding="utf-8") == "{}" and list(tmp_path.glob("*.tmp")) == []  # 不留临时文件
    monkeypatch.setattr(kh.os, "replace", real_replace)
    real_read, blocked = Path.read_text, {"n": 0}

    def flaky_read(self, *args, **kwargs):
        if self.name == "state.json" and blocked["n"]:
            blocked["n"] -= 1
            raise PermissionError(5, "Access is denied")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky_read)
    hub = kh.Hub(tmp_path / "hub")
    hub.ensure()
    hub.save_state({"tasks": {"T001": make_ts()}})
    blocked["n"] = 2
    assert "T001" in hub.load_state()["tasks"] and blocked["n"] == 0
    blocked["n"] = kh.SHARING_RETRIES  # 一直读不到：报错，不当成没有主任务（工人会把信收掉不办）
    with pytest.raises(kh.HubError, match="读不出"):
        hub.load_state()
    blocked["n"] = 0
    assert kh.read_text(tmp_path / "missing.txt") == ""
    assert kh.Hub(tmp_path / "fresh").load_state() == {"tasks": {}}  # 还没有 state.json：照旧是空的


def cut_short(run_dir, report="missing", stop="length", files=("a.tsx", "b.tsx")):
    """执行端的输出被截断：最后一条 stopReason=length，执行报告没写成。"""
    (run_dir / "state.json").write_text(json.dumps({"state": "NEEDS_REVIEW"}), encoding="utf-8")
    (run_dir / "scope.json").write_text(json.dumps({"violations": [], "files": [{"path": f} for f in files]}),
                                        encoding="utf-8")
    (run_dir / "events-summary.json").write_text(json.dumps({"final_stop_reason": stop}), encoding="utf-8")
    (run_dir / "report-status.json").write_text(json.dumps({"status": report}), encoding="utf-8")


def test_a_cut_off_attempt_is_continued_instead_of_restarted(tmp_path, monkeypatch):
    # T012 的 attempt-002：5170s、新增 30 个文件，V01 56 条只差 3 条，模型输出被截断没交报告，重派却从基线从头来
    repo, hub, ts, plans, previous = rework_setup(tmp_path)
    failed_checks(previous)
    cut_short(previous)
    ts["exec"], ts["audit_post"] = {"run_dir": str(previous), "check_ok": False, "status": "NEEDS_REVIEW"}, {}
    assert kh.carry_source(hub, ts) == (previous, "cutoff")
    for report, stop in (("json_ok", "length"), ("missing", "stop"), ("no_json", "toolUse")):
        cut_short(previous, report, stop)  # 交了报告的，或者不是截断（被杀、自己停）：照旧从基线重来
        assert kh.carry_source(hub, ts) is None
    cut_short(previous, "no_json")  # 报告写了一半被截断：也接着改
    calls = []

    def fake_pd(hub_, args, timeout=600):
        calls.append(args[0] if args[0] != "prepare" else "prepare " + args[1])
        if args[0] == "verdict":
            assert args[args.index("--class") + 1] == "EXECUTION_ERROR"
            (previous / "state.json").write_text(json.dumps({"state": "REVISE"}), encoding="utf-8")
        if args[0] == "branch":
            return 0, "commit=%s branch=pi-rework/x" % ("a" * 40)
        return (9, "prepare 停在这里") if args[0] == "prepare" else (0, "ok")

    monkeypatch.setattr(kh, "run_pd", fake_pd)
    monkeypatch.setattr(kh, "contract_requirements", lambda hub_, ts_: [])
    monkeypatch.setattr(kh, "rework_added_files", lambda hub_, ts_: [])
    kh.run_exec(hub, ts)
    assert calls == ["verdict", "branch", "derive-json", "validate", "prepare t001-doc.v2"]
    v2 = (plans / "t001-doc.v2.md").read_text(encoding="utf-8")
    assert "输出被截断（stopReason=length）" in v2 and "上一轮跑满了时限" not in v2
    assert "### 上一轮没过的地方" in v2 and "- V01：退出码 1 ≠ 期望 0" in v2
    assert ts["rework_chain"][-1]["why"] == "cutoff"


def test_an_abandoned_attempt_is_skipped_when_looking_for_a_candidate(tmp_path):
    # 站主停掉从头重来的 attempt-003（记成 ABANDONED），返工要接着被截断的 attempt-002 改
    repo, hub, ts, plans, first = rework_setup(tmp_path)
    runs, ts["audit_post"] = first.parent, {}
    for name in ("attempt-002", "attempt-003"):
        (runs / name).mkdir()
        (runs / name / "candidate.patch").write_text("diff --git a/y b/y\n", encoding="utf-8")
    cut_short(runs / "attempt-002")
    cut_short(runs / "attempt-003", stop="toolUse")
    ts["exec"] = {"run_dir": str(runs / "attempt-003"), "check_ok": False}
    assert kh.carry_source(hub, ts) is None  # 没停掉：被杀的不是截断，照旧从基线重来
    (runs / "attempt-003" / "state.json").write_text(json.dumps({"state": "ABANDONED"}), encoding="utf-8")
    assert kh.carry_source(hub, ts) == (runs / "attempt-002", "cutoff")
    timed_out(runs / "attempt-002")
    assert kh.carry_source(hub, ts) == (runs / "attempt-002", "timeout")
    ts["exec"] = {}
    assert kh.carry_source(hub, ts) == (runs / "attempt-002", "upstream")  # 上游重新交付：同样跳过停掉的
    cut_short(runs / "attempt-002", stop="stop")
    passed_checks(runs / "attempt-002")
    ts["exec"] = {"run_dir": str(runs / "attempt-003"), "check_ok": False}
    assert kh.carry_source(hub, ts) is None  # 检查全过、活干完了的：不在这里接着改
    (runs / "attempt-002" / "state.json").write_text(json.dumps({"state": "REVISE"}), encoding="utf-8")
    cut_short(first)
    assert kh.carry_source(hub, ts) is None  # 已经有去处的之前都不再看


def test_exec_letter_counts_the_candidate_and_names_the_failed_checks(engine_env, monkeypatch):
    # T012 的交付信写“改动 0 个文件”（数的是执行报告），协调人照着回“仍 0 文件改动”
    hub = engine_env
    check = {"code": 1}
    monkeypatch.setattr(kh, "run_pd", lambda hub, args, timeout=600: (check["code"], "check 输出"))
    ts = make_ts()
    run_dir = attempt_dir(hub, {"state": "NEEDS_REVIEW"})
    (run_dir / "executor-report.json").unlink()
    cut_short(run_dir, files=("a.tsx", "b.tsx", "c.css"))
    failed_checks(run_dir)
    ts["contract"] = {"key": "t001-doc.v1", "version": 1}
    contract = kh.contract_paths(hub, ts)[1]
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(json.dumps({"budget": {"max_attempts_total": 3}}), encoding="utf-8")
    (run_dir / "claim").mkdir()
    letter = kh.finish_exec(hub, ts, run_dir, 0)
    assert "执行端自述 没交执行报告（模型最后一条输出被截断：stopReason=length）" in letter["摘要"]
    assert "候选改动 3 个文件" in letter["摘要"]
    assert letter["验证"].endswith("没过的检查：V01（FAILED tests/x.py::test_V01）；合同预算还剩 2 次 attempt")
    cut_short(run_dir, stop="toolUse", files=())
    letter = kh.finish_exec(hub, ts, run_dir, 0)
    assert "执行端自述 未知（没有可读的执行报告）" in letter["摘要"] and "候选改动 0 个文件" in letter["摘要"]
    (run_dir / "executor-report.json").write_text(json.dumps({"executor_status": "completed", "changed_files": ["x"]}),
                                                  encoding="utf-8")
    (run_dir / "scope.json").write_text(json.dumps({"violations": []}), encoding="utf-8")
    check["code"] = 0
    letter = kh.finish_exec(hub, ts, run_dir, 0)
    assert "执行端自述 completed" in letter["摘要"] and "候选改动 1 个文件" in letter["摘要"]  # 没有清单才数报告
    assert "没过的检查" not in letter["验证"]
    contract.unlink()
    assert "预算" not in kh.finish_exec(hub, ts, run_dir, 0)["验证"]  # 读不到合同：不写


def test_an_unsent_contract_gets_the_rostered_executor_before_dispatch(tmp_path, monkeypatch):
    # T012 的 v1 在名册换执行模型之前就通过了校验，派遣时仍写着 step 提供商，预检失败白用掉一次 attempt
    repo, hub, ts, plans, previous = rework_setup(tmp_path)
    ts["exec"], ts["audit_post"] = {}, {}
    ts["contract"].update(dispatched=False, md=".agent/plans/t001-doc.v1.md")
    md = plans / "t001-doc.v1.md"
    md.write_text(md.read_text(encoding="utf-8") + "- executor: step/step-5-preview · thinking high\n", encoding="utf-8")
    calls, answer = [], {"validate": (0, "ok")}

    def fake_pd(hub_, args, timeout=600):
        calls.append(args[0] if args[0] != "prepare" else "prepare " + args[1])
        return (9, "prepare 停在这里") if args[0] == "prepare" else answer.get(args[0], (0, "ok"))

    monkeypatch.setattr(kh, "run_pd", fake_pd)
    monkeypatch.setattr(kh, "contract_requirements", lambda hub_, ts_: [])
    kh.run_exec(hub, ts)
    assert calls == ["derive-json", "validate", "prepare t001-doc.v1"]
    assert kh.CONTRACT_EXECUTOR_LINE in md.read_text(encoding="utf-8")
    del calls[:]
    kh.run_exec(hub, ts)
    assert calls == ["prepare t001-doc.v1"]  # 已经一致：不再校验
    md.write_text(md.read_text(encoding="utf-8").replace(kh.CONTRACT_EXECUTOR_LINE, "- executor: x/y · thinking high"),
                  encoding="utf-8")
    answer["validate"] = (1, "合同坏了")
    del calls[:]
    letter = kh.run_exec(hub, ts)
    assert calls == ["derive-json", "validate"] and "执行端没有开始" in letter["摘要"]
    assert "没有通过校验" in ts["exec"]["error"]


def test_owner_raises_the_attempt_budget(tmp_path, monkeypatch):
    # T012 的 attempt-003 是内核把被截断的候选当成从头重来用掉的，接着改的返工只剩最后一次
    import argparse
    import os
    import re
    repo, head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    plans = repo / ".agent" / "plans"
    plans.mkdir(parents=True)
    (plans / "t001-doc.v3.md").write_text(
        "# TASK: t001-doc\n- plan_version: 3\n- base_sha: %s\n\n## Budget\n- max_attempts_total: 3\n"
        "- max_wall_seconds_per_attempt: 7200\n- max_wall_seconds_total: 21600\n" % ("o" * 40), encoding="utf-8")

    def derive(key):
        text = (plans / ("%s.md" % key)).read_text(encoding="utf-8")
        budget = {k: int(v) for k, v in re.findall(r"(?m)^- (max_\w+):\s*(\d+)$", text)}
        (plans / ("%s.json" % key)).write_text(json.dumps({"budget": budget}), encoding="utf-8")

    derive("t001-doc.v3")
    ts = locked(kh.new_task_state("T001", "doc", "改文档", head, True))
    ts["contract"] = {"key": "t001-doc.v3", "version": 3, "dispatched": True, "md": ".agent/plans/t001-doc.v3.md"}
    ts["exec"] = {"run_dir": "r", "check_ok": False, "attempts_left": 0}
    ts["stages"]["5-exec"]["status"] = "failed"
    hub.save_state({"tasks": {"T001": ts}})
    assert "预算的 attempt 已经用完" in kh.guard(ts, meta("返工", "exec-step", "T001-5-exec"))
    for number in (1, 2, 3):
        run = repo / ".agent" / "runs" / "t001-doc" / ("attempt-00%d" % number)
        (run / "claim").mkdir(parents=True)
        (run / "run.json").write_text(json.dumps({"wall_seconds": 6000}), encoding="utf-8")
    calls, answer = [], {"validate": (0, "ok")}

    def fake_pd(hub_, args, timeout=600):
        calls.append(args[0])
        if args[0] == "derive-json":
            derive(args[1])
        return answer.get(args[0], (0, "ok"))

    monkeypatch.setattr(kh, "run_pd", fake_pd)
    monkeypatch.setattr(kh, "contract_requirements", lambda hub_, ts_: [])
    args = argparse.Namespace(repo=str(repo), task="T001", attempts=4, reason="两次是内核的错")
    with pytest.raises(kh.HubError, match="至少 5"):  # 已用 3 次，返工之后还要留一次
        kh.cmd_task_budget(args)
    for bad in ({"reason": " "}, {"task": "T009"}, {"attempts": 21}, {"attempts": 3}):
        with pytest.raises(kh.HubError):
            kh.cmd_task_budget(argparse.Namespace(**dict(vars(args), **bad)))
    kh.exec_marks(hub).mkdir(parents=True)
    mark = kh.exec_marks(hub) / "T001.json"
    mark.write_text(json.dumps({"pid": os.getpid(), "task": "T001"}), encoding="utf-8")
    with pytest.raises(kh.HubError, match="执行端正在办"):
        kh.cmd_task_budget(argparse.Namespace(**dict(vars(args), attempts=5)))
    mark.unlink()
    state = hub.load_state()
    status, state["tasks"]["T001"]["status"] = state["tasks"]["T001"]["status"], "done"
    hub.save_state(state)
    with pytest.raises(kh.HubError, match="没有可追加预算"):
        kh.cmd_task_budget(argparse.Namespace(**dict(vars(args), attempts=5)))
    state["tasks"]["T001"]["status"] = status
    hub.save_state(state)
    assert not (plans / "t001-doc.v4.md").exists() and calls == []
    assert kh.cmd_task_budget(argparse.Namespace(**dict(vars(args), attempts=5))) == kh.EXIT_OK
    v4 = (plans / "t001-doc.v4.md").read_text(encoding="utf-8")
    assert "- plan_version: 4" in v4 and "- max_attempts_total: 5" in v4
    assert "- max_wall_seconds_total: 32400" in v4  # 已用 18000 秒，再留两次单次时限
    assert "- max_attempts_total: 3" in (plans / "t001-doc.v3.md").read_text(encoding="utf-8")  # 派遣过的不改
    ts = hub.load_state()["tasks"]["T001"]
    assert ts["contract"]["key"] == "t001-doc.v4" and ts["exec"]["attempts_left"] == 2
    assert kh.guard(ts, meta("返工", "exec-step", "T001-5-exec")) is None  # 协调人能重发返工了
    assert calls == ["derive-json", "validate"]
    assert '"event": "budget.raised"' in (hub.root / "ledger" / "events.jsonl").read_text(encoding="utf-8")
    with pytest.raises(kh.HubError, match="要大于现在的 5"):  # 只能追加
        kh.cmd_task_budget(argparse.Namespace(**dict(vars(args), attempts=5)))
    answer["validate"] = (1, "合同坏了")
    with pytest.raises(kh.HubError, match="预算没有追加成"):
        kh.cmd_task_budget(argparse.Namespace(**dict(vars(args), attempts=6)))
    ts = hub.load_state()["tasks"]["T001"]  # 没派遣过的 v4 就地改；问题记在状态里
    assert ts["contract"]["key"] == "t001-doc.v4" and ts["contract"]["problems"]
    assert "- max_attempts_total: 6" in (plans / "t001-doc.v4.md").read_text(encoding="utf-8")


def test_bold_item_ids_in_the_contract_are_normalized(tmp_path, monkeypatch):
    # T011 的合同端三次都写成 `- **D01**: …`，调度器一条 DoD 也认不出（“definition_of_done 必须是非空数组”）
    text = ("## Definition of Done\n- **D01**: 纯函数；证据：V01\n- **D02**：数据层\n  * **D10**:缩进的\n"
            "- **V01：** `npm test`\n- D03：已经对的\n- **说明**: 不是编号\n**D04**: 不在列表里\n- **D5**: 一位数\n")
    fixed, count = kh.normalize_markup(text)
    assert count == 4
    assert fixed.splitlines()[1:] == ["- D01：纯函数；证据：V01", "- D02：数据层", "  * D10：缩进的", "- V01：`npm test`",
                                      "- D03：已经对的", "- **说明**: 不是编号", "**D04**: 不在列表里", "- **D5**: 一位数"]
    hub = kh.Hub(tmp_path)
    ts = make_ts()
    monkeypatch.setattr(kh, "revalidate_contract", lambda hub_, ts_: [])
    monkeypatch.setattr(kh, "budget_problems", lambda hub_, ts_: [])
    assert kh.accept_contract(hub, ts, {"contract_md": "# TASK: t001-doc\n" + text}) == []
    written = (tmp_path / ".agent" / "plans" / ("%s.md" % ts["contract"]["key"])).read_text(encoding="utf-8")
    assert "- D01：纯函数；证据：V01" in written and "**D01**" not in written
    events = (hub.root / "ledger" / "events.jsonl").read_text(encoding="utf-8")
    assert '"event": "contract.markup_normalized"' in events and '"lines": 4' in events
    kh.accept_contract(hub, ts, {"contract_md": "# TASK: t001-doc\n- D01：对的\n"})
    assert (hub.root / "ledger" / "events.jsonl").read_text(encoding="utf-8").count("markup_normalized") == 1


def test_an_unchanged_attempt_on_a_rework_base_still_carries_the_work(tmp_path):
    # T012 的 attempt-004 接着 attempt-002 改，一行没动就被截断：补丁是空的，可工作目录里有 attempt-002 的活
    repo, hub, ts, plans, first = rework_setup(tmp_path)
    runs, ts["audit_post"] = first.parent, {}
    (first / "state.json").write_text(json.dumps({"state": "REVISE"}), encoding="utf-8")
    rework = "b" * 40
    ts["rework_chain"] = [{"from": "attempt-001", "commit": rework, "contract": "t001-doc.v2"}]
    run = runs / "attempt-002"
    run.mkdir()
    (run / "candidate.patch").write_text("", encoding="utf-8")
    (run / "meta.json").write_text(json.dumps({"base_sha": rework, "plan_version": 2}), encoding="utf-8")
    cut_short(run)
    ts["exec"] = {"run_dir": str(run), "check_ok": False}
    assert kh.carry_source(hub, ts) == (run, "cutoff")
    ts["exec"] = {}
    assert kh.carry_source(hub, ts) == (run, "upstream")  # 门禁热修补之后：搬它的候选，不停在 REVISE 的上一轮
    ts["rework_chain_superseded"], ts["rework_chain"] = ts.pop("rework_chain"), []
    assert kh.carry_source(hub, ts) == (run, "upstream")  # 搬过一次、链作废了：基线里仍有活
    ts["rework_chain_superseded"] = []
    assert kh.carry_source(hub, ts) is None  # 基线不是返工提交、补丁又是空的：没有活


def test_owner_commands_pause_a_busy_task_runner(tmp_path, monkeypatch):
    # 第 42 轮：runner 拿着锁直到闲下来退出，T012 一封接一封有信，站主的 task budget 重试半小时也插不进去
    import argparse
    import os
    repo, _head = git_repo(tmp_path)
    hub = kh.Hub(repo)
    hub.ensure()
    marker = kh.pause_marker(hub, "T002")
    assert not kh.pause_requested(hub, "T002")
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    assert kh.pause_requested(hub, "T002")
    monkeypatch.setattr(kh.pd, "pid_alive", lambda pid: False)  # 命令的进程已经不在：标记作废
    assert not kh.pause_requested(hub, "T002") and not marker.exists()
    monkeypatch.undo()
    marker.write_text(json.dumps({"pid": os.getpid()}), encoding="utf-8")
    # runner 在两步之间看到标记就让出锁，不等闲下来
    monkeypatch.setattr(kh, "code_fingerprint", lambda *args: "a")
    code = kh.cmd_run(argparse.Namespace(repo=str(repo), max_steps=10, idle_exit=60.0, poll=0.0, settle=0.0,
                                         no_restart=False, parallel=None, task="T002"))
    assert code == kh.EXIT_OK and not kh.lock_alive(kh.runner_lock(hub, "T002"))
    assert '"event": "runner.paused"' in (hub.root / "ledger" / "events.jsonl").read_text(encoding="utf-8")
    # supervisor 也不给它起 runner
    hub.save_state({"tasks": {"T002": make_ts()}})
    hub.deliver({"from": kh.OWNER, "to": kh.COORDINATOR, "task-id": "T002", "in-reply-to": "none", "type": "回复"},
                fields())
    monkeypatch.setattr(kh, "tasks_with_work", lambda hub_: ["T002"])
    monkeypatch.setattr(kh, "kernel_dirty", lambda *a: False)
    spawned = []
    monkeypatch.setattr(kh, "spawn_task_runner", lambda hub_, task, args: spawned.append(task) or type("C", (), {"pid": 7})())
    kh.supervise_tick(hub, None, 3, {}, {})
    assert spawned == []
    marker.unlink()
    kh.supervise_tick(hub, None, 3, {}, {})
    assert spawned == ["T002"]
    # 命令自己挂标记、办完撤掉；supervisor 在跑时缺省等 OWNER_WAIT_SECONDS
    waits = []
    real = kh.DirLock.__init__

    def record(self, path, wait_seconds=30.0):
        waits.append((Path(path).name, wait_seconds))
        real(self, path, wait_seconds)

    monkeypatch.setattr(kh.DirLock, "__init__", record)
    with kh.DirLock(kh.runner_lock(hub, None), wait_seconds=1.0):
        kh.write_text_atomic(kh.runner_lock(hub, None) / "mode", "supervisor\n")
        with kh.task_quiet(hub, "T002"):
            assert kh.pause_requested(hub, "T002")
    assert not marker.exists() and ("T002", kh.OWNER_WAIT_SECONDS) in waits
    del waits[:]
    with kh.task_quiet(hub, "T002"):  # 没有 supervisor：串行的 hub 不看标记，照旧只等 1 秒
        pass
    assert waits == [("T002", 1.0), (".runner", 1.0)] and not marker.exists()
    with pytest.raises(kh.HubError):
        with kh.task_quiet(hub, "T002"):
            raise kh.HubError("命令半路出错")
    assert not marker.exists()  # 出错也撤掉标记


def test_scope_notes_are_stripped_and_unparsed_check_ids_are_named(tmp_path):
    # T013 的合同端写了 `tests/test_gate_t013_*.py（执行端禁止碰…）`，调度器连说明一起当成路径，什么也禁不住；
    # 它又照内核给的范例写了 VG1、VR1，调度器只认一个大写字母加两位数字，两条检查都丢了，返工三次没人说清为什么
    text = ("## Scope\n- forbidden_paths:\n  - tests/test_gate_t013_*.py（执行端禁止碰）\n"
            "  - tests/test_gate_*.py（除 t013 外）（执行端禁止碰旧门禁）\n  - src/api.ts\n"
            "- allowed_modified_files: 无（本片只新增）\n\n## Goal\n- 合并重复件（说明不在 Scope 里，不动）\n")
    fixed, count = kh.normalize_markup(text)
    assert count == 2  # 单值字段的说明（`无（本片只新增）`）调度器自己会去掉，不动
    assert fixed.splitlines()[2:7] == ["  - tests/test_gate_t013_*.py", "  - tests/test_gate_*.py", "  - src/api.ts",
                                       "- allowed_modified_files: 无（本片只新增）", ""]
    assert "- 合并重复件（说明不在 Scope 里，不动）" in fixed
    md = ("## Validation commands\n- VG1（必要，基线应失败）：`python -m pytest tests/test_gate_t013_baseline.py -q` · cwd：仓库根\n"
          "- V01（必要）：`npm test` · cwd：desktop/web\n- VR1: `python -m pytest tests/x.py -q`\n"
          "- 说明：这一行不是检查\n\n## Definition of done\n- D01：x；证据：V01\n")
    assert kh.unparsed_check_ids(md) == ["VG1", "VR1"]
    repo, hub, ts, plans, _previous = rework_setup(tmp_path)
    (plans / "t001-doc.v1.md").write_text("# TASK: t001-doc\n" + md, encoding="utf-8")
    problems = kh.contract_requirements(hub, ts)
    assert "Validation commands 里这几行调度器认不出、等于没写：VG1、VR1" in problems[0] and "G01、R01" in problems[0]
    (plans / "t001-doc.v1.md").write_text("# TASK: t001-doc\n" + md.replace("VG1", "G01").replace("VR1", "R01"),
                                          encoding="utf-8")
    assert not any("认不出" in p for p in kh.contract_requirements(hub, ts))


def test_scope_paths_missing_the_directory_prefix_are_named(tmp_path):
    # 第 46 轮：T013 的合同把路径都写成相对 desktop/web 的 `src/pages/readonly1/…`，执行端照它做会全部越界
    repo, hub, ts, plans, _previous = rework_setup(tmp_path)
    head = land_on_main(repo, "desktop/web/src/a.ts", "export const a = 1;\n", "已有的文件")
    data = {"base_sha": head, "scope": {
        "allowed_modified_files": ["src/a.ts", "desktop/web/src/a.ts", "src/new.ts"],
        "allowed_new_files": ["newdir/x.ts", "desktop/web/src/b.ts"],
        "allowed_deleted_files": [], "forbidden_paths": ["src/**", "README.md", "web/src/a.ts"]}}
    assert kh.scope_missing_prefix(hub, data) == ["src/a.ts → desktop/web/src/a.ts", "web/src/a.ts → desktop/web/src/a.ts"]
    assert kh.scope_missing_prefix(hub, dict(data, base_sha=None)) == []
    (plans / "t001-doc.v1.json").write_text(json.dumps(data), encoding="utf-8")
    problems = kh.contract_requirements(hub, ts)
    assert any(p.startswith("Scope 的路径要从仓库根写起") and "src/a.ts → desktop/web/src/a.ts" in p for p in problems)
