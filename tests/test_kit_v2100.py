"""Code-Kit 2.10.0 的单元测试：integrate 沿用 check --fresh 的条件、自检照抄的写法、执行报告的自定解读清单、改名。

端到端的部分（integrate 沿用与重跑、执行说明里的自检写法、复审骨架列出解读与线索）在 tests/test_dispatch.py 的
test_v2100_*。
"""
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import pi_dispatch as pd  # noqa: E402

NL = chr(10)
TREE = "a" * 40
OTHER_TREE = "b" * 40


def _tmpdir(case: unittest.TestCase) -> Path:
    path = Path(tempfile.mkdtemp(prefix="codekit-v2100-"))
    case.addCleanup(shutil.rmtree, str(path), True)
    return path


def _result(cid, passed=True, required=True):
    return {"id": cid, "required": required, "status": "passed" if passed else "failed", "passed": passed}


def _clean(**over):
    """一份干净的 check --fresh 记录：V01 必要、V02 非必要，都跑过、都通过。"""
    data = {"run": 1, "mode": "fresh", "candidate_tree": TREE, "ended_at": "2026-10-15T00:00:00Z",
            "covers_all_required": True, "all_required_passed": True, "modified_by_checks": False,
            "unexpected_files_by_checks": [], "results": [_result("V01"), _result("V02", required=False)]}
    data.update(over)
    return data


CONTRACT = {"checks": [{"id": "V01", "argv": ["python", "run.py"], "cwd": ".", "timeout_seconds": 60, "required": True},
                       {"id": "V02", "argv": ["python", "probe.py"], "cwd": ".", "timeout_seconds": 60,
                        "required": False}]}


class FreshCheckReuse(unittest.TestCase):
    """两棵树相同时不调用 git、不读配置，只看记录本身。"""

    def setUp(self):
        self.run_dir = _tmpdir(self)
        self.repo = types.SimpleNamespace(root=self.run_dir, config=lambda: {})

    def record(self, number, data):
        folder = self.run_dir / "checks" / ("%02d" % number)
        folder.mkdir(parents=True)
        (folder / "checks.json").write_text(json.dumps(data), encoding="utf-8")

    def reuse(self):
        return pd._fresh_check_reuse(self.repo, self.run_dir, CONTRACT, TREE, TREE)

    def test_without_any_record_there_is_nothing_to_reuse(self):
        self.assertEqual(self.reuse(), (None, "没有 check --fresh 的记录"))

    def test_in_place_records_do_not_count(self):
        self.record(1, _clean(mode="in_place"))
        self.assertEqual(self.reuse(), (None, "没有 check --fresh 的记录"))

    def test_a_clean_fresh_record_is_reused(self):
        self.record(1, _clean())
        info, reason = self.reuse()
        self.assertEqual(reason, "")
        self.assertEqual((info["record"], info["ended_at"], info["planner_paths"], [r["id"] for r in info["results"]]),
                         ("checks/01", "2026-10-15T00:00:00Z", [], ["V01", "V02"]))

    def test_a_later_in_place_record_does_not_hide_the_fresh_one(self):
        self.record(1, _clean())
        self.record(2, _clean(mode="in_place", all_required_passed=False))
        self.assertEqual(self.reuse()[0]["record"], "checks/01")

    def test_the_newest_fresh_record_decides(self):
        self.record(1, _clean())
        self.record(2, _clean(results=[_result("V01", passed=False), _result("V02", required=False)],
                              all_required_passed=False))
        info, reason = self.reuse()
        self.assertIsNone(info)
        self.assertEqual(reason, "checks/02 的必要检查没有全过（V01）")

    def test_record_numbers_sort_as_numbers(self):
        for number in range(1, 10):
            self.record(number, _clean(mode="in_place"))
        self.record(10, _clean())
        self.assertEqual(self.reuse()[0]["record"], "checks/10")

    def test_an_aborted_fresh_record_blocks_reuse(self):
        self.record(1, _clean())
        self.record(2, {"aborted": "fresh_workspace_failed", "mode": "fresh", "error": "x", "at": "t"})
        self.assertEqual(self.reuse(), (None, "最近一次 check --fresh（checks/02）中止了：fresh_workspace_failed"))

    def test_an_old_workspace_abort_without_mode_counts_as_fresh(self):
        self.record(1, _clean())
        self.record(2, {"aborted": "fresh_workspace_failed", "error": "x", "at": "t"})
        self.assertIsNone(self.reuse()[0])

    def test_an_old_drift_abort_without_mode_is_not_taken_for_fresh(self):
        # 2.10.0 之前的漂移中止没写 mode；干净副本建好时已核对过候选树，漂移实际只出自就地检查。
        self.record(1, _clean())
        self.record(2, {"aborted": "candidate_drift", "tree_now": TREE})
        self.assertEqual(self.reuse()[0]["record"], "checks/01")

    def test_another_candidate_tree_is_not_reused(self):
        self.record(1, _clean(candidate_tree=OTHER_TREE))
        self.assertEqual(self.reuse(), (None, "checks/01 测的不是这个候选树"))

    def test_every_check_must_have_run_including_optional_ones(self):
        self.record(1, _clean(results=[_result("V01")]))
        self.assertEqual(self.reuse(), (None, "checks/01 没有跑 V02"))

    def test_a_failed_optional_check_does_not_block_reuse(self):
        self.record(1, _clean(results=[_result("V01"), _result("V02", passed=False, required=False)]))
        self.assertEqual(self.reuse()[0]["record"], "checks/01")

    def test_the_record_flag_must_agree(self):
        self.record(1, _clean(all_required_passed=False))
        self.assertEqual(self.reuse(), (None, "checks/01 的必要检查没有全过（all_required_passed 为假）"))

    def test_a_check_that_modified_the_candidate_blocks_reuse(self):
        self.record(1, _clean(modified_by_checks=True))
        self.assertEqual(self.reuse(), (None, "checks/01 的检查改动了候选文件或产生了新文件"))

    def test_a_check_that_left_new_files_blocks_reuse(self):
        self.record(1, _clean(unexpected_files_by_checks=["report.txt"]))
        self.assertEqual(self.reuse(), (None, "checks/01 的检查改动了候选文件或产生了新文件"))


class PlannerPathDiff(unittest.TestCase):
    """合并后的树相对候选树只能在规划路径下有差异；planner_paths 来自仓库配置。"""

    def setUp(self):
        self.work = _tmpdir(self)
        pd.git(["init", "-q"], self.work)
        self.trees = []
        for rel in ("a.txt", ".agent/reviews/t/attempt-001.md", "README.md"):
            target = self.work / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x" + NL, encoding="utf-8")
            pd.git(["add", rel], self.work)
            pd.git(["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
                    "commit", "-qm", rel], self.work)
            self.trees.append(pd.git_text(["rev-parse", "HEAD^{tree}"], self.work))
        self.run_dir = _tmpdir(self)
        folder = self.run_dir / "checks" / "01"
        folder.mkdir(parents=True)
        (folder / "checks.json").write_text(json.dumps(_clean(candidate_tree=self.trees[0])), encoding="utf-8")

    def reuse(self, merged, config=None):
        repo = types.SimpleNamespace(root=self.work, config=lambda: dict(config or {}))
        return pd._fresh_check_reuse(repo, self.run_dir, CONTRACT, self.trees[0], merged)

    def test_a_review_record_on_the_tip_is_a_planner_path(self):
        info, reason = self.reuse(self.trees[1])
        self.assertEqual((reason, info["planner_paths"]), ("", [".agent/reviews/t/attempt-001.md"]))

    def test_any_other_path_means_a_rerun(self):
        info, reason = self.reuse(self.trees[2])
        self.assertIsNone(info)
        self.assertEqual(reason, "当前末端相对候选多了规划路径之外的改动：README.md")

    def test_the_repository_config_decides_what_a_planner_path_is(self):
        info, reason = self.reuse(self.trees[2], {"planner_paths": [".agent/reviews/**", "README.md"]})
        self.assertEqual(sorted(info["planner_paths"]), [".agent/reviews/t/attempt-001.md", "README.md"])


class SelfCheckForms(unittest.TestCase):
    CHECK = {"id": "V01", "argv": ["python", "-m", "pytest", "-q", "tests/test x.py"], "cwd": ".", "timeout_seconds": 60}

    def test_bash_keeps_the_exit_code_with_pipefail(self):
        self.assertEqual(pd.self_check_command(self.CHECK, ["read", "bash"]),
                         "set -o pipefail; python -m pytest -q 'tests/test x.py' 2>&1 | tail -n 40")

    def test_the_form_is_not_flagged_as_a_masked_exit_code(self):
        self.assertEqual(pd._masked_exit_mention(pd.self_check_command(self.CHECK, ["bash"])), "")
        # 对照：执行器的老写法会被摘要标出来。
        self.assertNotEqual(pd._masked_exit_mention("python -m pytest -q 2>&1 | tail -n 40"), "")

    def test_cwd_and_env_come_first(self):
        check = dict(self.CHECK, cwd="sub dir", env={"B": "2", "A": "x y"})
        self.assertEqual(pd.self_check_command(check, ["bash"]),
                         "set -o pipefail; cd 'sub dir' && A='x y' B=2 python -m pytest -q 'tests/test x.py' "
                         "2>&1 | tail -n 40")

    def test_powershell_prints_the_exit_code(self):
        check = dict(self.CHECK, cwd="sub", env={"A": "it's"})
        self.assertEqual(pd.self_check_command(check, ["read", "powershell"]),
                         "Set-Location 'sub'; $env:A = 'it''s'; & 'python' '-m' 'pytest' '-q' 'tests/test x.py' "
                         "2>&1 | Select-Object -Last 40; " + '"exit=$LASTEXITCODE"')

    def test_bash_wins_when_both_shells_are_there(self):
        self.assertTrue(pd.self_check_command(self.CHECK, ["powershell", "bash"]).startswith("set -o pipefail; "))

    def test_no_shell_no_form(self):
        self.assertIsNone(pd.self_check_command(self.CHECK, ["read", "edit"]))


META = {"task_id": "t", "plan_version": 1, "attempt_id": "t/attempt-001", "worktree": "/w", "base_sha": "c" * 40}
EXECUTOR = {"tools": ["read", "edit", "bash"]}


def _contract(**over):
    data = {"authorization": {"executor": ["local_edit", "local_test"], "integration": []},
            "scope": {"allowed_modified_files": ["src/a.py"], "allowed_new_files": [], "allowed_deleted_files": [],
                      "forbidden_paths": [], "dependency_changes": "forbidden"},
            "checks": [{"id": "V01", "argv": ["python", "run.py"], "cwd": ".", "timeout_seconds": 60, "required": True,
                        "expected_exit_code": 0},
                       {"id": "V02", "argv": ["python", "probe.py"], "cwd": ".", "timeout_seconds": 60,
                        "required": False, "expected_exit_code": 3}],
            "definition_of_done": [{"id": "D01", "text": "x", "evidence": ["V01"]}]}
    data.update(over)
    return data


class InstructionForms(unittest.TestCase):
    def test_the_summary_puts_a_form_under_each_check(self):
        lines = pd.machine_summary(_contract(), (), ["bash"]).splitlines()
        at = next(n for n, line in enumerate(lines) if line.startswith("  - V01"))
        self.assertEqual(lines[at + 1], "    自检照抄：`set -o pipefail; python run.py 2>&1 | tail -n 40`")
        self.assertNotIn("期望退出码", lines[at])
        self.assertIn("，期望退出码 3", next(line for line in lines if line.startswith("  - V02")))

    def test_without_tools_the_summary_has_no_forms(self):
        self.assertNotIn("自检照抄：`", pd.machine_summary(_contract()))

    def test_the_instruction_carries_the_forms_only_when_the_executor_may_test(self):
        self.assertIn("自检照抄：`set -o pipefail; python run.py", pd.render_instruction(META, _contract(), EXECUTOR, 600))
        # 规则第 5 条总会提到这种写法；没有自检授权或没有 shell 时，摘要里没有具体的写法。
        no_test = _contract(authorization={"executor": ["local_edit"], "integration": []})
        self.assertNotIn("自检照抄：`", pd.render_instruction(META, no_test, EXECUTOR, 600))
        self.assertNotIn("自检照抄：`", pd.render_instruction(META, _contract(), {"tools": ["read", "edit"]}, 600))

    def test_the_rules_and_the_report_ask_for_interpretations(self):
        text = pd.render_instruction(META, _contract(), EXECUTOR, 600)
        rules = text.split("## 必须遵守")[1].split("## 机器合同摘要")[0]
        self.assertIn("开头同样加 `set -o pipefail;`", rules)
        self.assertNotIn('echo "exit=$?"', rules)
        self.assertIn("写进报告的 `interpretations`", rules)
        report = text.split("## 最后一条消息必须是执行报告")[1]
        self.assertIn('{"quote": "合同原文或条目号", "adopted": "你采用的做法", "reason": "理由"}', report)
        block = json.loads(report.split("```json")[1].split("```")[0])
        self.assertEqual(block["interpretations"], [])


def _report_text(report):
    return "## 执行报告" + NL + "```json" + NL + json.dumps(report, ensure_ascii=False) + NL + "```" + NL


class ReportInterpretations(unittest.TestCase):
    def extract(self, report):
        return pd.extract_report(_report_text(report), _tmpdir(self))

    def test_the_list_is_counted(self):
        status = self.extract({"executor_status": "completed", "contract_conflicts": [], "unresolved_questions": [],
                               "interpretations": [{"quote": "q", "adopted": "a", "reason": "r"}]})
        self.assertEqual((status["status"], status["interpretations"], status["contract_conflicts"]), ("json_ok", 1, 0))
        self.assertNotIn("interpretations_missing", status)

    def test_an_empty_list_counts_as_present(self):
        status = self.extract({"interpretations": []})
        self.assertEqual(status["interpretations"], 0)
        self.assertNotIn("interpretations_missing", status)

    def test_a_missing_or_non_list_field_is_flagged(self):
        for report in ({"executor_status": "completed"}, {"interpretations": "无"}):
            status = self.extract(report)
            self.assertEqual((status["interpretations"], status.get("interpretations_missing")), (0, True), report)


class SummaryNotes(unittest.TestCase):
    def summary(self, report, events):
        run_dir = _tmpdir(self)
        (run_dir / "events-summary.json").write_text(json.dumps(events), encoding="utf-8")
        (run_dir / "report-status.json").write_text(json.dumps(dict({"status": "json_ok"}, **report)), encoding="utf-8")
        pd.write_summary(run_dir, types.SimpleNamespace(root=run_dir))
        text = (run_dir / "summary.md").read_text(encoding="utf-8")

        def section(name):
            head = "## " + name
            return text.split(head)[1].split(NL + "## ")[0] if head in text else ""
        return section("复审需要关注"), section("备注")

    CLUE = {"interpretation_mention_count": 1, "interpretation_mentions": [
        {"line": 9, "kind": "thinking", "keyword": "I'll go with", "excerpt": "I'll go with the toplevel check"}]}

    def test_an_unreported_interpretation_is_attention(self):
        attention, notes = self.summary({"interpretations": 0}, self.CLUE)
        self.assertIn("执行器自行宣布了 1 处解读", attention)
        self.assertIn("报告的 interpretations、contract_conflicts 与 unresolved_questions 都为空", attention)

    def test_a_reported_interpretation_turns_it_into_a_note(self):
        attention, notes = self.summary({"interpretations": 1}, self.CLUE)
        self.assertNotIn("自行宣布", attention)
        self.assertIn("核对它们都在报告的 interpretations / contract_conflicts / unresolved_questions 里", notes)

    def test_a_missing_list_is_a_note(self):
        attention, notes = self.summary({"interpretations": 0, "interpretations_missing": True}, {})
        self.assertIn("执行报告没有 interpretations 列表", notes)
        self.assertNotIn("interpretations", attention)

    def test_reported_interpretations_also_answer_ambiguity_mentions(self):
        events = {"ambiguity_mention_count": 1, "ambiguity_mentions": [
            {"line": 4, "kind": "thinking", "excerpt": "the contract is ambiguous about tabs"}]}
        attention, notes = self.summary({"interpretations": 1}, events)
        self.assertNotIn("歧义", attention)
        self.assertIn("报告列出了 interpretations / contract_conflicts / unresolved_questions", notes)


class ReviewClues(unittest.TestCase):
    def test_clues_are_listed_with_line_numbers_and_capped(self):
        mentions = [{"line": n, "kind": "thinking", "excerpt": "I'll go with %d" % n} for n in range(12)]
        lines = pd._interpretation_clue_lines({"interpretation_mention_count": 12, "interpretation_mentions": mentions})
        self.assertEqual(len(lines), pd.REVIEW_CLUE_LIMIT + 1)
        self.assertEqual(lines[0], "  - 第 0 行（thinking）：I'll go with 0")
        self.assertEqual(lines[-1], "  - 另有 2 处，见 events-summary.json 的 interpretation_mentions")

    def test_no_clues_no_lines(self):
        self.assertEqual(pd._interpretation_clue_lines({}), [])

    def test_the_review_lists_interpretations_among_the_statements(self):
        self.assertEqual([key for key, _label in pd.REPORT_STATEMENTS],
                         ["contract_conflicts", "interpretations", "limitations", "unresolved_questions"])


class Naming(unittest.TestCase):
    def test_live_kit_files_say_code_kit(self):
        paths = [ROOT / "AGENTS.md", ROOT / "README.md", ROOT / ".codex" / "config.example.toml"]
        paths += sorted((ROOT / "scripts").glob("*.py"))
        for base in (".agents/skills", ".claude/skills", ".claude/agents"):
            paths += sorted(p for p in (ROOT / base).rglob("*") if p.is_file())
        stale = [str(p.relative_to(ROOT)) for p in paths if "PI-Kit" in p.read_text(encoding="utf-8", errors="replace")]
        self.assertEqual(stale, [])
        self.assertIn("本仓库用 Code-Kit 协作", (ROOT / "AGENTS.md").read_text(encoding="utf-8"))

    def test_agents_md_carries_the_two_executor_rules(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("开头加 `set -o pipefail;`", agents)
        self.assertIn("写进执行报告的 `interpretations`", agents)
        self.assertNotIn('echo "exit=$?"', agents)


if __name__ == "__main__":
    unittest.main()
