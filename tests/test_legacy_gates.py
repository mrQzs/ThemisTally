#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧门禁 G0–G6、verdict、候选漂移与补丁完整性的特征化回归（01-A07；01 文档附录 C.4）。

目的：锁定 HEAD a4fa199b0e5bdc658215765ee7558b9fe6723940 时旧调度器 scripts/pi_dispatch.py 的**现有**行为，
不修 bug。现状可疑的地方在测试 docstring 中标注“可疑”，并引用 docs/themis-tally-v2/01-baseline/legacy-inventory.md
的条目号或小节号（例如 11.2 第 5 条）。断言的每条文本都按源码核对过，docstring 中的 ``:NNNN`` 是
scripts/pi_dispatch.py 在 a4fa199 的行号。

覆盖范围（legacy-inventory.md 第 2 节 G0–G6 表、5.6、5.7、10 节 C.4 缺口、11.5 第 1、2 条）：
- G0：plan.md / contract.json 哈希不符、plan.md 缺失、基线提交不可用、meta.json 不校验、contract.json 缺失或损坏时的未捕获异常；
- G1：缺 run.json、缺事件摘要、事件问题（没有 agent_settled）、Pi 非 0 退出、超时（run 退出 1）、运行中被中断；
  ``run --timeout`` 只能收紧、不能超过合同预算；
- G2：scope 违规、缺 scope.json、主工作区变化只作备注；
- G3/G4：无有效检查记录、非当前候选、未覆盖必要检查、检查修改候选、必要检查失败、DoD 证据失败；
- G5：恒通过、固定备注；
- G6：记录后修改、只差行尾、行尾加新增文件、删除候选文件、无法重新快照、worktree 不存在时跳过比较、补丁缺失/被改/哈希不符/往返失败；
  运行后 core.autocrlf 改变时快照仍按记录值、行尾消息报告当前值；
- verdict 拒绝分支：状态不可复审、复审报告缺失或为空、Verdict 行不符、--waive 格式（先于门禁求值）、PASS 带豁免、
  AWE 缺豁免或 --decided-by、REVISE/BLOCKED/ESCALATE 缺 --class；
- verdict 接受分支：豁免理由去掉首尾空白、PASS 带 --class、INFRA_FAILURE 可复审、五种结论之后都可再次 verdict；
- 候选漂移：check 运行前修改候选文件（退出 4）、aborted 记录成为最近一次；
- 补丁完整性：check --fresh 与 mutate 的拒绝、留下空 checks/NN、原地 check 不查补丁、branch 在树对象存在时不按补丁重建、
  树对象丢失时按补丁重建的三个分支。

运行：``python tests/test_legacy_gates.py``（按文件单独运行，01-L04；建议设置 PYTHONDONTWRITEBYTECODE=1）。
每个用例在 tests/legacy_harness.py 提供的独立临时区域与受控环境中运行（01-L05），不调用真实 pi/claude/codex，不联网。
"""
from __future__ import annotations

import contextlib
import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

sys.dont_write_bytecode = True  # 导入 legacy_harness 时不在 tests/ 下写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))

from legacy_harness import (  # noqa: E402
    IS_WINDOWS, OK_FILES, PLAN_KEY, PY, LegacyCase, default_checks, legacy_facts, ok_events, send_interrupt,
    sha256_file,
)

REF = LegacyCase.attempt_ref(1)
ATTEMPT_ID = "normalize-query.v1.a001"
VERDICTS_REL = ".agent/runs/normalize-query/attempt-001/verdicts"

# 源码原文（scripts/pi_dispatch.py @a4fa199）
PASS_REFUSED = ("PASS 被拒绝：门禁 %s 未通过。修正后重新验收，或按授权使用 "
                "ACCEPTED_WITH_EXCEPTION 并逐项豁免。")                                      # :4289-4290
PASS_NO_WAIVER = "PASS 不接受豁免；有豁免时使用 ACCEPTED_WITH_EXCEPTION"                    # :4292
AWE_MISSING = "以下失败门禁没有豁免理由：%s"                                                  # :4296
AWE_NEEDS = "ACCEPTED_WITH_EXCEPTION 需要至少一项 --waive 与 --decided-by"                  # :4298
NEEDS_CLASS = "%s 需要 --class（PLAN_ERROR, EXECUTION_ERROR, INFRA_FAILURE, SCOPE_VIOLATION, " \
              "REQUIREMENT_BLOCKED, TIMEOUT, BUDGET_EXCEEDED, CANCELLED）"                   # :4300、:77-78
WAIVE_FORMAT = "--waive 格式应为 G2=原因"                                                   # :4278
NOT_REVIEWABLE = "状态 %s 不能记录验收结论"                                                   # :4265
NO_REVIEW = "找不到复审报告：%s"                                                              # :4269
VERDICT_LINE = "复审报告中的 'Verdict:' 行必须恰好是 %s"                                      # :4273
NO_CHECK = "没有有效的独立检查记录"                                                           # :4204-4205
PATCH_BAD = "候选补丁缺失、被改动或未通过往返校验"                                            # :4255
PATCH_BAD_FRESH = "候选补丁缺失、被改动或未通过往返校验，不能建立干净副本"                     # :3988、:3600
G5_NOTE = "质量复审（测试是否弱化、兼容性、残余风险）由复审报告负责，工具不做机械判断"            # :4154
IN_PLACE_NOTE = ("检查在执行 worktree 中运行：被 .gitignore 忽略的文件（依赖、构建产物）"
                 "也可能影响结果；中高风险任务建议 check --fresh")                             # :4221-4222
THINKING_NOTE = "提供商未回报思考级别：只能确认请求的级别（high）"                             # :4178-4179
MAIN_REPO_NOTE = "运行期间主工作区有规划路径之外的变化，复审时确认来源（见 summary.md）"          # :4196
CHECKS_ALL_OK = "检查结果（in_place）：全部必要检查通过"                                       # :4049-4050
GATE_NAMES = ["G0", "G1", "G2", "G3", "G4", "G5", "G6"]


class Prefix(str):
    """期望的 GATE 行只比较前缀：行的其余部分是 git 的原始错误文本，随 Git 版本变化。"""


def gate_lines(out: str) -> List[str]:
    """verdict PASS 被拒时逐条打印的 ``GATE <Gx> <problem>`` 行（:4286-4288），按输出顺序。"""
    return [line.rstrip("\r") for line in out.splitlines() if line.startswith("GATE ")]


def _write_or_remove(path: Path, data: Optional[bytes]) -> None:
    if path.exists():
        os.chmod(str(path), 0o600)  # Git 对象文件与 worktree 的 .git 文件在 Windows 上是只读的
    if data is None:
        if path.exists():
            path.unlink()
    elif path.exists():
        # 就地改写而不是重建：Windows 上 git 把 worktree 的 .git 文件设为隐藏，按“新建覆盖”打开隐藏文件会被拒绝
        with open(str(path), "r+b") as handle:
            handle.write(data)
            handle.truncate()
    else:
        path.write_bytes(data)


def json_bytes(path: Path, mutate: Callable[[Any], None]) -> bytes:
    """读 JSON、就地修改、按调度器的格式（indent=2、末尾换行）写回的字节。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def has_console() -> bool:
    """当前进程是否挂在控制台上（Windows）。GenerateConsoleCtrlEvent 只能把 CTRL_BREAK 送给共享同一控制台的进程组。"""
    if not IS_WINDOWS:
        return True
    import ctypes
    buffer = (ctypes.c_uint32 * 4)()
    return ctypes.windll.kernel32.GetConsoleProcessList(buffer, 4) > 0  # type: ignore[attr-defined]


def swap_line_endings(data: bytes) -> bytes:
    """CRLF → LF；文件本来是 LF 时 LF → CRLF（只改行尾，不改内容）。"""
    return data.replace(b"\r\n", b"\n") if b"\r\n" in data else data.replace(b"\n", b"\r\n")


def out_lines(out: str) -> List[str]:
    """输出按行拆开并去掉行尾的 \\r（Windows 上子进程输出是 CRLF）。"""
    return [line.rstrip("\r") for line in out.splitlines()]


class LegacyGateCase(LegacyCase):
    """公共流程：make_repo → prepare → run（stub 或假 pi）→ 原地 check → verdict。"""

    def start(self, name: str, *, pi_cmd: Optional[Sequence[str]] = None, scenario: str = "ok",
              env: Optional[Dict[str, str]] = None, check: bool = True, config: Optional[Dict[str, Any]] = None,
              run_args: Sequence[str] = (), expect_run: Tuple[int, str] = (0, "NEEDS_REVIEW"),
              **over: Any) -> Tuple[Path, str]:
        """建仓库、prepare、run，并断言 run 的 (退出码, 状态) 等于 expect_run；run 的输出存到 self.run_out。"""
        repo, base = self.make_repo(name, **over)
        if config:
            self.write_config(repo, **config)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        run_env = {"STUB_SCENARIO": scenario}
        run_env.update(env or {})
        code, out = self.tool(repo, "run", REF, *run_args, env=run_env, pi_cmd=pi_cmd)
        self.run_out = out
        self.assertEqual((code, self.state(repo)), expect_run, out)
        if check:
            self.check_ok(repo)
        return repo, base

    def check_ok(self, repo: Path, *args: str) -> str:
        code, out = self.tool(repo, "check", REF, *args)
        self.assertEqual(code, 0, out)
        self.assertIn(CHECKS_ALL_OK, out)
        return out

    def verdict(self, repo: Path, verdict: str, *extra: str, review: Optional[str] = None) -> Tuple[int, str]:
        return self.tool(repo, "verdict", REF, "--verdict", verdict,
                         "--review", review if review is not None else self.review(repo, verdict), *extra)

    def verdict_record(self, repo: Path, number: int) -> Dict[str, Any]:
        return self.jload(self.rd(repo) / "verdicts" / ("%02d.json" % number))

    @contextlib.contextmanager
    def replaced(self, path: Path, data: Optional[bytes]) -> Iterator[None]:
        """暂时把 path 换成 data（None 表示删除），结束时恢复原字节（原来不存在则删除）。"""
        original = path.read_bytes() if path.exists() else None
        _write_or_remove(path, data)
        try:
            yield
        finally:
            _write_or_remove(path, original)

    # -- 断言 -------------------------------------------------------------------

    def assert_gate_lines(self, out: str, expected: Sequence[str]) -> None:
        actual = gate_lines(out)
        self.assertEqual(len(actual), len(expected), "GATE 行：%r\n%s" % (actual, out))
        for line, want in zip(actual, expected):
            if isinstance(want, Prefix):
                self.assertTrue(line.startswith("GATE " + want), "%r 应以 %r 开头" % (line, "GATE " + want))
            else:
                self.assertEqual(line, "GATE " + want)

    def assert_pass_refused(self, repo: Path, code: int, out: str, gates: Sequence[str], lines: Sequence[str],
                            state: str = "NEEDS_REVIEW", verdicts_expected: bool = False) -> None:
        """PASS 被门禁拒绝：退出 1（EXIT_FAIL，:4290），先逐条 GATE 行，再 ERROR；不写记录、不改状态。"""
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR: " + PASS_REFUSED % ", ".join(gates), out)
        self.assert_gate_lines(out, lines)
        self.assertEqual(self.state(repo), state)
        if not verdicts_expected:
            self.assertFalse((self.rd(repo) / "verdicts").exists(), "被拒绝的 verdict 不应写记录")

    def assert_error(self, code: int, out: str, exit_code: int, message: str) -> None:
        """DispatchError：stderr 打印 ``ERROR: <msg>``，退出码为其 code（:4966-4968）；没有 GATE 行。"""
        self.assertEqual(code, exit_code, out)
        self.assertIn("ERROR: " + message, out)
        self.assertEqual(gate_lines(out), [], out)

    def assert_traceback(self, code: int, out: str, exc_name: str) -> None:
        """非 DispatchError 的异常不被 main 捕获（:4964-4971）：Python 回溯，退出 1，没有 ERROR: 行。"""
        self.assertEqual(code, 1, out)
        self.assertIn("Traceback (most recent call last)", out)
        self.assertIn(exc_name, out)
        self.assertNotIn("ERROR: ", out)


class G0InputConsistency(LegacyGateCase):

    def test_lb_gates_024_g0_hash_base_and_contract_failures(self):
        """LB-GATES-024（G0，:4160-4163；verify_inputs :2659-2665；resolve_commit :768-770）、LB-GATES-023（求值顺序）。
        01-A07；C.4“G0–G6”（缺口：G0 全部失败路径 :4161、:4163）。

        特征化：plan.md 被改或缺失、contract.json 被改 → G0 失败，PASS 退出 1；meta.json 的 base_sha 改为不存在的
        提交 → G0“基线提交不可用”，同时 G6“无法重新快照：git read-tree <base_sha> 失败：…”。
        可疑（legacy-inventory 5.6 G0 补充、11.2 第 5 条）：meta.json 本身不做哈希校验（改了也没有“meta.json”问题）；
        contract.json 被改后 G4 仍按被改的合同判定（新增的必要检查 V02 报 not_run）；contract.json 缺失或不是合法 JSON
        时 load_attempt（:2653-2656）抛出未捕获异常，以 Traceback 退出 1，G0 来不及报告（原为推断，此处实测）。
        """
        repo, _base = self.start("g0")
        rd = self.rd(repo)
        plan, contract_json, meta = rd / "plan.md", rd / "contract.json", rd / "meta.json"

        with self.subTest("plan.md 内容被改"):
            with self.replaced(plan, plan.read_bytes() + b"\n"):
                code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G0"], ["G0 plan.md 的哈希与 prepare 时记录的不一致"])

        with self.subTest("plan.md 缺失"):
            with self.replaced(plan, None):
                code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G0"], ["G0 plan.md 的哈希与 prepare 时记录的不一致"])

        with self.subTest("contract.json 只多一个换行（仍是合法 JSON）"):
            with self.replaced(contract_json, contract_json.read_bytes() + b"\n"):
                code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G0"], ["G0 contract.json 的哈希与 prepare 时记录的不一致"])

        with self.subTest("contract.json 被改后 G4 仍按被改的合同判定（可疑）"):
            extra = dict(default_checks()[0], id="V02")
            data = json_bytes(contract_json, lambda c: c["checks"].append(extra))
            with self.replaced(contract_json, data):
                code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G0", "G4"],
                                     ["G0 contract.json 的哈希与 prepare 时记录的不一致", "G4 必要检查 V02：not_run"])

        with self.subTest("meta.json 的 base_sha 被改：只报基线不可用，不报 meta.json 哈希（可疑）"):
            bogus = "deadbeef" * 5
            with self.replaced(meta, json_bytes(meta, lambda m: m.update(base_sha=bogus))):
                code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G0", "G6"],
                                     ["G0 基线提交不可用", Prefix("G6 无法重新快照：git read-tree %s 失败：" % bogus)])
            self.assertNotIn("meta.json", "\n".join(gate_lines(out)))

        with self.subTest("contract.json 缺失：未捕获 FileNotFoundError（可疑）"):
            with self.replaced(contract_json, None):
                code, out = self.verdict(repo, "PASS")
            self.assert_traceback(code, out, "FileNotFoundError")
            self.assertEqual(self.state(repo), "NEEDS_REVIEW")

        with self.subTest("contract.json 不是合法 JSON：未捕获 JSONDecodeError（可疑）"):
            with self.replaced(contract_json, b"{not json"):
                code, out = self.verdict(repo, "PASS")
            self.assert_traceback(code, out, "JSONDecodeError")
            self.assertEqual(self.state(repo), "NEEDS_REVIEW")

        # 全部恢复后 PASS 通过：上面的失败只来自各自的改动
        code, out = self.verdict(repo, "PASS")
        self.assertEqual((code, self.state(repo)), (0, "PASS"), out)


class G1ExecutionComplete(LegacyGateCase):

    def test_lb_gates_025_g1_missing_run_json_and_events_summary(self):
        """LB-GATES-025（G1，:4165-4176）。01-A07；C.4“G0–G6”（缺口：G1 缺少 run.json :4168）。

        特征化：run.json 缺失时 G1 同时报“缺少 run.json”与“Pi 退出码为 None”（exit_code 缺失按非 0 处理，:4173）；
        events-summary.json 缺失时报“缺少事件摘要”（:4175）。
        """
        repo, _base = self.start("g1-missing")
        rd = self.rd(repo)
        with self.subTest("缺少 run.json"):
            with self.replaced(rd / "run.json", None):
                code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G1"], ["G1 缺少 run.json", "G1 Pi 退出码为 None"])
        with self.subTest("缺少 events-summary.json"):
            with self.replaced(rd / "events-summary.json", None):
                code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G1"], ["G1 缺少事件摘要"])

    def test_lb_gates_025_g1_event_problem_nosettle(self):
        """LB-GATES-025（:4175-4176，problem 来源 :2344-2348）、LB-EVENTS-021。01-A07；C.4“G0–G6”。

        特征化：事件流没有 agent_settled（pi 0.87 应以它结束）→ run 退出 1，但状态仍是 NEEDS_REVIEW（:3395-3406、:3349）；
        check 可以通过；PASS 被 G1 拒绝，problem 原文照录。
        """
        repo, _base = self.start("g1-nosettle", scenario="nosettle", expect_run=(1, "NEEDS_REVIEW"))
        summary = self.jload(self.rd(repo) / "events-summary.json")
        problem = "没有 agent_settled：该 pi 版本应以它结束，事件流可能被截断或运行被中断"
        self.assertEqual((summary["ok"], summary["problems"]), (False, [problem]))
        code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G1"], ["G1 " + problem])

    def test_lb_gates_025_g1_nonzero_pi_exit_only_caught_by_gate(self):
        """LB-GATES-025（:4173-4174）、LB-LIFE-019/020（:3349、:3395-3406）。01-A07；C.4“G0–G6”（缺口：非 0 退出码经 verdict）。

        特征化：Pi 以 3 退出但事件完整、无 problem → collect 状态 NEEDS_REVIEW、run 退出 0；只有 G1 记录退出码。
        可疑（legacy-inventory 11.2 第 15 条，原为源码推断，此处实测）：run 的退出码与状态都不反映 Pi 的非 0 退出。
        """
        pi = self.fake_pi(ok_events(), 3, files=OK_FILES)
        repo, _base = self.start("g1-exit", pi_cmd=pi, expect_run=(0, "NEEDS_REVIEW"))
        rd = self.rd(repo)
        self.assertEqual(self.jload(rd / "run.json")["exit_code"], 3)
        self.assertEqual(self.jload(rd / "events-summary.json")["problems"], [])
        code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G1"], ["G1 Pi 退出码为 3"])

    def test_lb_life_016_timeout_run_exit_1_and_g1_timeout(self):
        """LB-LIFE-016（超时，:678、:691-699、:3395-3398、:4169-4170）、LB-LIFE-020、LB-GATES-025。
        01-A07；C.4“超时”（缺口：超时后 run 退出 1、verdict 的 G1“运行超时”）。

        特征化：``run --timeout 5`` 在合同预算（600 s）之内生效（:3308-3309，“只能收紧”见
        test_lb_life_011_timeout_flag_cannot_exceed_budget）；到时 timed_out=true，状态 TIMEOUT，run 打印
        ``TIMEOUT <attempt_id>``（:3346）并退出 1（:3349）——事件完整（events ok=true、无 problem）时也是 1，
        只有 NEEDS_REVIEW 才可能退出 0；TIMEOUT 可复审，check 可以运行；PASS 被 G1 拒绝（“运行超时”加上被终止
        进程的退出码）；ACCEPTED_WITH_EXCEPTION 豁免 G1 并给出 --decided-by 后可以记录。
        """
        pi = self.fake_pi(ok_events(), 0, files=OK_FILES, hang_seconds=120)
        repo, _base = self.start("g1-timeout", pi_cmd=pi, run_args=("--timeout", "5"),
                                 config={"kill_grace_seconds": 1}, check=False, expect_run=(1, "TIMEOUT"))
        self.assertIn("RUNNING %s（时限 5s）" % ATTEMPT_ID, out_lines(self.run_out))
        self.assertIn("TIMEOUT %s" % ATTEMPT_ID, out_lines(self.run_out))
        rd = self.rd(repo)
        run = self.jload(rd / "run.json")
        self.assertEqual((run["timeout_seconds"], run["timed_out"], run["interrupted"]), (5, True, False))
        summary = self.jload(rd / "events-summary.json")
        self.assertEqual((summary["ok"], summary["problems"]), (True, []))  # 退出 1 只因为状态是 TIMEOUT
        self.check_ok(repo)
        code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G1"], ["G1 运行超时", "G1 Pi 退出码为 %s" % run["exit_code"]],
                                 state="TIMEOUT")
        self.assertNotEqual(run["exit_code"], 0)
        code, out = self.verdict(repo, "ACCEPTED_WITH_EXCEPTION", "--waive", "G1=超时前已完成全部改动",
                                 "--decided-by", "tester")
        self.assertEqual((code, self.state(repo)), (0, "ACCEPTED_WITH_EXCEPTION"), out)
        self.assertIn("未通过的门禁：G1", out)
        record = self.verdict_record(repo, 1)
        self.assertEqual((record["state_before"], record["waivers"]), ("TIMEOUT", {"G1": "超时前已完成全部改动"}))

    def test_lb_life_011_timeout_flag_cannot_exceed_budget(self):
        """LB-LIFE-011（本轮时限，:3307-3309、:3314-3315、:3333）。01-A07；C.4“锁与预算竞争”（缺口：``--timeout``
        被预算截短）、legacy-inventory 6.3“本轮时限”行。

        特征化：``run --timeout 3600`` 大于合同的 max_wall_seconds_per_attempt（600）→ 时限仍是 600：
        ``--timeout`` 只能收紧（取 min），不能放宽；RUNNING 行、run.json 与 claim/reservation.json 都记 600。
        """
        repo, _base = self.start("timeout-cap", check=False, run_args=("--timeout", "3600"))
        rd = self.rd(repo)
        budget = self.jload(rd / "contract.json")["budget"]
        self.assertEqual((budget["max_wall_seconds_per_attempt"], budget["max_wall_seconds_total"]), (600, 1800))
        self.assertIn("RUNNING %s（时限 600s）" % ATTEMPT_ID, out_lines(self.run_out))
        self.assertEqual(self.jload(rd / "run.json")["timeout_seconds"], 600)
        self.assertEqual(self.jload(rd / "claim" / "reservation.json")["timeout_seconds"], 600)

    @unittest.skipUnless(has_console(), "Windows 上当前进程没有控制台：CTRL_BREAK_EVENT 无法送达调度器（平台限制，不是失败）")
    def test_lb_life_017_interrupt_during_run_is_cancelled_exit_1(self):
        """LB-LIFE-017（取消，:571-585、:703-706、:3399-3400、:4171-4172）、LB-EXIT-031、LB-GATES-025。
        01-A07；C.4“取消”（缺口：没有信号用例）。

        特征化：Pi 运行期间调度器收到中断（Windows：CTRL_BREAK_EVENT → SIGBREAK；POSIX：SIGINT）→ run_supervised
        捕获 _Interrupted、终止进程树、run.json 记 interrupted=true → collect 判 CANCELLED → run 退出 **1**（不是 130，
        也不打印“已取消。”）；CANCELLED 可复审；PASS 被 G1 拒绝“运行被取消或调度器中断”。
        可疑（legacy-inventory 11.2 第 15 条）：Pi 运行期间的中断最终退出 1，与“已取消”的 130 不同。
        """
        repo, _base = self.make_repo("g1-cancel")
        self.write_config(repo, kill_grace_seconds=1)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        rd = self.rd(repo)
        pi = self.fake_pi(ok_events(), 0, files=OK_FILES, hang_seconds=300)
        proc = self.popen_tool(repo, "run", REF, pi_cmd=pi, new_process_group=True)
        events_path = rd / "events.jsonl"
        ready = self.wait_for(lambda: events_path.is_file() and b"agent_settled" in events_path.read_bytes()
                              and (rd / "pid.txt").is_file(), timeout=120)
        self.assertTrue(ready, "Pi 没有在 120 秒内输出完整事件")
        send_interrupt(proc)
        stdout, _ = proc.communicate(timeout=300)
        text = (stdout or b"").decode("utf-8", "replace")
        self.assertEqual(proc.returncode, 1, text)
        self.assertIn("CANCELLED %s" % ATTEMPT_ID, text)
        self.assertNotIn("已取消。", text)
        self.assertEqual(self.state(repo), "CANCELLED")
        run = self.jload(rd / "run.json")
        self.assertEqual((run["interrupted"], run["timed_out"]), (True, False))
        self.assertNotEqual(run["exit_code"], 0)
        self.check_ok(repo)
        code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G1"],
                                 ["G1 运行被取消或调度器中断", "G1 Pi 退出码为 %s" % run["exit_code"]],
                                 state="CANCELLED")


class G2Scope(LegacyGateCase):

    def test_lb_gates_026_g2_violation_missing_scope_and_g3_scope_evidence(self):
        """LB-GATES-026（G2，:4188-4193）、LB-GATES-027（G3 的 scope 证据，:4228-4232）、LB-GATES-018（违规顺序）。
        01-A07；C.4“G0–G6”（缺口：G2 缺少 scope.json :4188-4190；G3 失败断言 :4232）。

        特征化：越界（README.md 不在允许集合、package.json 命中 forbidden 且是依赖清单）→ G2 每条违规一行
        ``<kind> <path>``；默认 DoD D02 的证据是 scope，G3 同时失败“D02 依赖的范围证据未通过”（旧测试只断言 G2）。
        scope.json 缺失时 G2“缺少 scope.json”，G3 的 scope 证据同样失败。
        """
        repo, _base = self.start("g2-scope", scenario="scope")
        code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G2", "G3"],
                                 ["G2 out_of_scope README.md", "G2 forbidden_path package.json",
                                  "G2 dependency_change package.json", "G3 D02 依赖的范围证据未通过"])
        with self.replaced(self.rd(repo) / "scope.json", None):
            code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G2", "G3"], ["G2 缺少 scope.json", "G3 D02 依赖的范围证据未通过"])


class GateNotes(LegacyGateCase):

    def test_lb_gates_023_notes_never_block_pass_and_g5_constant(self):
        """LB-GATES-023（evaluate_gates 结构与顺序，:4152-4158）、LB-GATES-022（主工作区变化只作 G2 备注，:4194-4196）、
        LB-GATES-029（G5 恒通过，:4153-4154）、LB-GATES-030（G6 新增文件只作备注，:4249-4251）。
        01-A07；C.4“G0–G6”（缺口：G5 无测试；G2 备注未经 verdict 断言）、C.4“候选树漂移”（G6 中新增文件只作备注）。

        特征化：运行期间改写主工作区的 README.md、check 之后在 worktree 新增 notes.txt，PASS 仍被接受（退出 0）；
        记录中七个门禁按 G0…G6 排列，全部 passed，备注逐字如下；除 G3 外备注不打印（:4282-4283）。
        """
        repo, _base = self.make_repo("notes")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        code, out = self.tool(repo, "run", REF, env={"STUB_SCENARIO": "touchmain", "STUB_MAIN_REPO": str(repo)})
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        self.check_ok(repo)
        (self.worktree_of(repo) / "notes.txt").write_text("review scratch\n", encoding="utf-8")
        code, out = self.verdict(repo, "PASS")
        self.assertEqual((code, self.state(repo)), (0, "PASS"), out)
        self.assertIn("PASS 已记录（%s/01.json）。" % VERDICTS_REL, out)
        self.assertNotIn("NOTE  G3", out)
        self.assertNotIn(MAIN_REPO_NOTE, out)
        gates = self.verdict_record(repo, 1)["gates"]
        self.assertEqual(list(gates), GATE_NAMES)
        expected_notes = {
            "G0": [], "G1": [THINKING_NOTE], "G2": [MAIN_REPO_NOTE], "G3": [], "G4": [IN_PLACE_NOTE],
            "G5": [G5_NOTE], "G6": ["工作副本有候选之外的新文件（不会被集成）：notes.txt"],
        }
        for gate in GATE_NAMES:
            with self.subTest(gate=gate):
                self.assertEqual(gates[gate], {"passed": True, "problems": [], "notes": expected_notes[gate]})


class G3G4Checks(LegacyGateCase):

    def test_lb_gates_028_g4_partial_coverage_and_stale_candidate(self):
        """LB-GATES-028（G4，:4208-4211、:4223-4227）、LB-GATES-027（G3 检查引用，:4233-4236）、LB-EXIT-036。
        01-A07；C.4“G0–G6”（缺口：G4 非当前候选、未覆盖必要检查 :4209、:4211）。

        特征化：合同有两个必要检查 V01、V02（D03 引用 V02）。``check --only V01`` 退出 0（required_ok 只看运行了的项，
        LB-EXIT-036），但 PASS 被拒：G3“D03 依赖的 V02 未通过或未运行”，G4“没有覆盖全部必要检查”与“必要检查 V02：not_run”。
        完整 check 之后，把最近一次记录的 candidate_tree 改成基线树 → G4“最近一次检查不是针对当前候选”。
        """
        v02 = {"id": "V02", "argv": [PY, "-c", "print('ok')"], "cwd": ".", "timeout_seconds": 120,
               "required": True, "expected_exit_code": 0}
        dod = [{"id": "D01", "text": "行为正确", "evidence": ["V01"]},
               {"id": "D02", "text": "范围合规", "evidence": ["scope"]},
               {"id": "D03", "text": "探针通过", "evidence": ["V02"]}]
        repo, base = self.start("g4-cover", check=False, checks=default_checks() + [v02], definition_of_done=dod)
        out = self.check_ok(repo, "--only", "V01")
        self.assertNotIn("CHECK V02", out)
        record = self.jload(self.rd(repo) / "checks/01/checks.json")
        self.assertEqual((record["covers_all_required"], record["all_required_passed"]), (False, True))
        code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G3", "G4"],
                                 ["G3 D03 依赖的 V02 未通过或未运行",
                                  "G4 最近一次检查没有覆盖全部必要检查（使用了 --only？）",
                                  "G4 必要检查 V02：not_run"])
        self.check_ok(repo)
        checks_json = self.rd(repo) / "checks/02/checks.json"
        base_tree = self.git(repo, "rev-parse", base + "^{tree}")
        with self.replaced(checks_json, json_bytes(checks_json, lambda c: c.update(candidate_tree=base_tree))):
            code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G4"], ["G4 最近一次检查不是针对当前候选"])
        code, out = self.verdict(repo, "PASS")
        self.assertEqual((code, self.state(repo)), (0, "PASS"), out)

    def test_lb_gates_028_g4_required_check_failed(self):
        """LB-GATES-028（:4223-4227）、LB-GATES-027（:4233-4236）、LB-GATES-014（check 退出码）。
        01-A07；C.4“G0–G6”（缺口：必要检查失败 :4227、G3 失败断言 :4236）。

        特征化：候选实现错误 → 必要检查 V01 failed，check 退出 1；PASS 被拒：G3“D01 依赖的 V01 未通过或未运行”，
        G4“必要检查 V01：failed”。
        """
        files = dict(OK_FILES)
        files["src/normalize.py"] = "def normalize(q):\n    return q.lower()\n"
        pi = self.fake_pi(ok_events(), 0, files=files)
        repo, _base = self.start("g4-failed", pi_cmd=pi, check=False)
        code, out = self.tool(repo, "check", REF)
        self.assertEqual(code, 1, out)
        self.assertIn("CHECK V01 failed", out)
        self.assertIn("检查结果（in_place）：存在失败的必要检查", out)
        code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G3", "G4"],
                                 ["G3 D01 依赖的 V01 未通过或未运行", "G4 必要检查 V01：failed"])

    def test_lb_gates_027_g3_dod_evidence_on_optional_check(self):
        """LB-GATES-027（G3 DoD 证据，:4228-4236）、LB-EXIT-036（:4030）。01-A07；C.4“G0–G6”（缺口：G3 检查引用失败）。

        特征化：非必要检查 V02（required=false）失败时 check 仍退出 0、G4 通过；DoD D03 引用 V02 → 只有 G3 失败
        “D03 依赖的 V02 未通过或未运行”；引用 review 的 D04 被跳过，不产生问题。
        """
        v02 = {"id": "V02", "argv": [PY, "-c", "raise SystemExit(3)"], "cwd": ".", "timeout_seconds": 120,
               "required": False, "expected_exit_code": 0}
        dod = [{"id": "D01", "text": "行为正确", "evidence": ["V01"]},
               {"id": "D02", "text": "范围合规", "evidence": ["scope"]},
               {"id": "D03", "text": "可选探针", "evidence": ["V02"]},
               {"id": "D04", "text": "人工复审", "evidence": ["review"]}]
        repo, _base = self.start("g3-dod", check=False, checks=default_checks() + [v02], definition_of_done=dod)
        out = self.check_ok(repo)
        self.assertIn("CHECK V02 failed 退出码 3 ≠ 期望 0", out)
        code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G3"], ["G3 D03 依赖的 V02 未通过或未运行"])

    def test_lb_gates_014_g4_check_modified_candidate(self):
        """LB-GATES-014（check 运行后漂移，:4022-4052）、LB-GATES-028（:4212-4213）、LB-GATES-030（:4247-4248）。
        01-A07；C.4“G0–G6”（缺口：修改候选文件 :4213）、C.4“候选树漂移”。

        特征化：检查命令改写了候选文件 → check 打印 WARN、仍写记录、退出 1（必要检查本身通过）；PASS 被拒：
        G4“检查过程修改了候选文件”，G6（worktree 已被改）“候选文件在记录后被修改”。
        """
        v02 = {"id": "V02", "argv": [PY, "-c", "open('src/normalize.py','a').write('#x')"], "cwd": ".",
               "timeout_seconds": 120, "required": False, "expected_exit_code": 0}
        repo, _base = self.start("g4-modify", check=False, checks=default_checks() + [v02])
        code, out = self.tool(repo, "check", REF)
        self.assertEqual(code, 1, out)
        self.assertIn("WARN  检查修改了候选文件：src/normalize.py（结果不能作为 PASS 证据）", out)
        self.assertIn(CHECKS_ALL_OK, out)
        record = self.jload(self.rd(repo) / "checks/01/checks.json")
        self.assertEqual((record["modified_by_checks"], record["candidate_files_modified"]),
                         (True, ["src/normalize.py"]))
        code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G4", "G6"],
                                 ["G4 检查过程修改了候选文件：src/normalize.py",
                                  "G6 候选文件在记录后被修改：src/normalize.py"])


class CandidateDrift(LegacyGateCase):

    def test_lb_gates_013_check_refuses_modified_candidate_and_aborted_record_blocks(self):
        """LB-GATES-013（check 运行前漂移拒绝，:4002-4014）、LB-GATES-027/028（:4200-4205、:3446-3450）。
        01-A07；C.4“候选树漂移”（缺口：check 前修改候选文件 drift_before.modified）。

        特征化：check 之后在 worktree 改写候选文件，再次 check → 写 ``{"aborted": "candidate_drift"}``、退出 4
        （EXIT_DRIFT），消息中的列表是 Python repr，空列表写“无”。把文件恢复原样后 PASS 仍被拒：被拒那次的 aborted
        记录成了“最近一次检查”，G3/G4 报“没有有效的独立检查记录”，即使更早的 checks/01 有效（legacy-inventory 5.9 G4 行）。
        """
        repo, _base = self.start("drift")
        target = self.worktree_of(repo) / "src/normalize.py"
        with self.replaced(target, target.read_bytes() + b"# drift\n"):
            code, out = self.tool(repo, "check", REF)
        self.assert_error(code, out, 4,
                          "工作副本与候选不一致，检查结果无法代表候选：被修改的候选文件 ['src/normalize.py']；"
                          "候选之外的新文件 无。删除这些额外文件、重新派遣以固定新候选，或用 --fresh 在干净副本上验收。")
        record = self.jload(self.rd(repo) / "checks/02/checks.json")
        self.assertEqual((record["aborted"], record["modified"], record["unexpected_files"]),
                         ("candidate_drift", ["src/normalize.py"], []))
        code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G3", "G4"], ["G3 " + NO_CHECK, "G4 " + NO_CHECK])


class G6Integrable(LegacyGateCase):

    def test_lb_gates_030_g6_drift_after_record(self):
        """LB-GATES-030（G6，:4237-4253）、LB-GATES-010（tree_drift / line_endings_only，:858-870）。
        01-A07；C.4“G0–G6”（缺口：G6 失败 :4244、:4248、:4253）、C.4“候选树漂移”（verdict 层）。

        特征化（每项单独改 worktree，verdict 后恢复）：
        - 改内容 →“候选文件在记录后被修改：<路径>”；删除候选文件同样记为“修改”；
        - 只改行尾 →“候选文件与记录只差行尾（CRLF / LF）：1 个文件……（prepare 时记录 <值>，现在 <值>）……”；
        - 只改行尾再加一个新文件 → 不给行尾专门消息，报“候选文件在记录后被修改”。可疑（legacy-inventory 11.2 第 6 条：
          line_endings_only 比较整棵树，原只在临时仓库用同一条 git 命令核实，此处端到端实测）；
        - worktree 的 .git 文件损坏 →“无法重新快照：git read-tree <base> 失败：<git 的原始错误>”（:760 的消息只取 argv 前两项）；
        - 运行后把临时仓库的 core.autocrlf 从 false 改成 true：门禁快照仍按 prepare 时记录的值（meta.json 的
          git_autocrlf，:4240 → :780-790）归一行尾，不动 worktree 时 PASS 照常被接受（新增文件 tests/test_normalize.py
          是 CRLF，按 true 快照会变成 LF）；只改行尾时，消息中的“现在”取当前生效的配置（effective_autocrlf，:4246、
          :773-777），即“（prepare 时记录 false，现在 true）”。期望中的“现在”用 ``git config --get core.autocrlf`` 求得。
        """
        repo, _base = self.start("g6-drift")
        wt = self.worktree_of(repo)
        src, test_file = wt / "src/normalize.py", wt / "tests/test_normalize.py"
        meta = self.jload(self.rd(repo) / "meta.json")
        self.assertEqual(meta.get("git_autocrlf"), "false")  # 临时仓库 core.autocrlf=false（legacy_harness）

        def line_endings_message(files: int) -> str:
            now = self.git(repo, "config", "--get", "core.autocrlf")  # 当前生效值，不取自 meta
            return ("G6 候选文件与记录只差行尾（CRLF / LF）：%d 个文件。多半是 core.autocrlf 在运行后被改动"
                    "（prepare 时记录 %s，现在 %s）；先恢复配置再重新 verdict" % (files, meta["git_autocrlf"], now))

        with self.subTest("内容被改"):
            with self.replaced(src, src.read_bytes() + b"# edited after record\n"):
                code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G6"], ["G6 候选文件在记录后被修改：src/normalize.py"])
        with self.subTest("候选文件被删除"):
            with self.replaced(test_file, None):
                code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G6"], ["G6 候选文件在记录后被修改：tests/test_normalize.py"])
        with self.subTest("只差行尾"):
            with self.replaced(src, swap_line_endings(src.read_bytes())):
                code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G6"], [line_endings_message(1)])
        with self.subTest("只差行尾 + 新增文件：报成被修改（可疑）"):
            with self.replaced(src, swap_line_endings(src.read_bytes())), \
                    self.replaced(wt / "extra.txt", b"extra\n"):
                code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G6"], ["G6 候选文件在记录后被修改：src/normalize.py"])
        with self.subTest("无法重新快照"):
            with self.replaced(wt / ".git", b"this is not a gitdir file\n"):
                code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G6"],
                                     [Prefix("G6 无法重新快照：git read-tree %s 失败：" % meta["base_sha"])])
        # 以下在 core.autocrlf=true 下进行，直到用例结束（临时仓库随用例删除，不需要恢复）
        self.git(repo, "config", "core.autocrlf", "true")
        self.assertEqual(self.git(repo, "config", "--get", "core.autocrlf"), "true")
        with self.subTest("运行后 core.autocrlf 改为 true，再只差行尾：消息报告当前值"):
            with self.replaced(src, swap_line_endings(src.read_bytes())):
                code, out = self.verdict(repo, "PASS")
            message = line_endings_message(1)
            self.assertIn("（prepare 时记录 false，现在 true）", message)
            self.assert_pass_refused(repo, code, out, ["G6"], [message])
        # 全部恢复后 PASS 通过；此时 core.autocrlf=true，门禁快照仍固定为记录的 false
        code, out = self.verdict(repo, "PASS")
        self.assertEqual((code, self.state(repo)), (0, "PASS"), out)
        self.assertEqual(self.verdict_record(repo, 1)["gates"]["G6"], {"passed": True, "problems": [], "notes": []})

    def test_lb_gates_030_g6_worktree_missing_skips_drift_but_checks_patch(self):
        """LB-GATES-030（:4238 的 is_dir 条件、:4254-4255）、LB-GATES-037（cleanup）。
        01-A07；C.4“G0–G6”、C.4“补丁往返/完整性”。

        特征化：cleanup 移除 worktree 后，G6 不再比较漂移（整段跳过），只检查补丁：补丁被改时 PASS 仍被 G6 拒绝；
        补丁恢复后 PASS 被接受，G6 没有问题。可疑（legacy-inventory 11.2 第 6 条：worktree 不存在时跳过比较，意图未知）。
        旧实现（a4fa199）此时 G6 也没有备注；调度器 2.4.0 起有意补上一条备注，写明没有重新快照、只凭补丁往返校验
        （KitExperiment 跨机器复审的反馈，见 docs/KitExperiment实机反馈.md），这里按后继实现断言。
        """
        repo, _base = self.start("g6-nowt")
        wt = self.worktree_of(repo)
        code, out = self.tool(repo, "cleanup", REF)
        self.assertEqual(code, 0, out)
        self.assertIn("已移除 worktree：", out)
        self.assertFalse(wt.exists())
        patch = self.rd(repo) / "candidate.patch"
        with self.replaced(patch, patch.read_bytes() + b"\n"):
            code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G6"], ["G6 " + PATCH_BAD])
        code, out = self.verdict(repo, "PASS")
        self.assertEqual((code, self.state(repo)), (0, "PASS"), out)
        missing_note = ("执行 worktree 不存在（已清理，或在派遣 attempt 的另一台机器上）：%s。"
                        "没有重新快照，G6 只凭候选补丁的往返校验" % wt)
        self.assertEqual(self.verdict_record(repo, 1)["gates"]["G6"],
                         {"passed": True, "problems": [], "notes": [missing_note]})


class PatchIntegrity(LegacyGateCase):

    def test_lb_gates_006_g6_patch_missing_tampered_sha_and_roundtrip(self):
        """LB-GATES-006（candidate_patch_ok，:3474-3477）、LB-GATES-030（:4254-4255）、LB-GATES-005（candidate.json 字段）。
        01-A07；C.4“补丁往返/完整性”（缺口：缺失、篡改、sha256 不符、往返失败）。

        特征化：candidate.patch 缺失、字节被改、candidate.json 的 patch_sha256 不符、patch_roundtrip_verified 为 false，
        四种情况都只报同一条 G6“候选补丁缺失、被改动或未通过往返校验”，PASS 退出 1。
        """
        repo, _base = self.start("patch-g6")
        rd = self.rd(repo)
        patch, candidate = rd / "candidate.patch", rd / "candidate.json"
        cand = self.jload(candidate)
        self.assertTrue(cand["patch_roundtrip_verified"])
        self.assertEqual(cand["patch_sha256"], sha256_file(patch))
        cases = [
            ("补丁缺失", patch, None),
            ("补丁字节被改", patch, patch.read_bytes() + b"\n"),
            ("patch_sha256 不符", candidate, json_bytes(candidate, lambda c: c.update(patch_sha256="0" * 64))),
            ("往返校验失败", candidate, json_bytes(candidate, lambda c: c.update(patch_roundtrip_verified=False))),
        ]
        for label, path, data in cases:
            with self.subTest(label):
                with self.replaced(path, data):
                    code, out = self.verdict(repo, "PASS")
                self.assert_pass_refused(repo, code, out, ["G6"], ["G6 " + PATCH_BAD])
        code, out = self.verdict(repo, "PASS")
        self.assertEqual((code, self.state(repo)), (0, "PASS"), out)

    def test_lb_gates_012_fresh_check_and_mutate_refuse_bad_patch(self):
        """LB-GATES-006（:3987-3988、:3599-3600）、LB-GATES-012（干净副本）、LB-GATES-016（mutate）、LB-EXIT-011/013。
        01-A07；C.4“补丁往返/完整性”（缺口：--fresh 与 mutate 的拒绝）。

        特征化：补丁被改时 ``check --fresh`` 退出 3，``mutate`` 在读取变异清单之前就退出 3（不建 mutations/）；
        原地 check 不检查补丁（照常退出 0）。
        可疑（legacy-inventory 11.2 第 7 条）：``check --fresh`` 被拒时已建好的 checks/02 留空（没有 checks.json），
        它成为“最近一次检查”后，补丁恢复原样 PASS 仍被 G3/G4“没有有效的独立检查记录”拒绝，即使 checks/01 有效。
        """
        repo, _base = self.start("patch-fresh")
        rd = self.rd(repo)
        patch = rd / "candidate.patch"
        tampered = patch.read_bytes() + b"\n"
        with self.replaced(patch, tampered):
            code, out = self.tool(repo, "check", REF, "--fresh")
            self.assert_error(code, out, 3, PATCH_BAD_FRESH)
            code, out = self.tool(repo, "mutate", REF, "--spec", "no-such-spec.json")
            self.assert_error(code, out, 3, PATCH_BAD_FRESH)
        self.assertTrue((rd / "checks/02").is_dir())
        self.assertEqual(list((rd / "checks/02").iterdir()), [])
        self.assertFalse((rd / "mutations").exists())
        code, out = self.verdict(repo, "PASS")
        self.assert_pass_refused(repo, code, out, ["G3", "G4"], ["G3 " + NO_CHECK, "G4 " + NO_CHECK])
        with self.replaced(patch, tampered):
            self.check_ok(repo)  # 原地 check（checks/03）不看补丁
        self.assertTrue((rd / "checks/03/checks.json").is_file())
        code, out = self.verdict(repo, "PASS")
        self.assertEqual((code, self.state(repo)), (0, "PASS"), out)

    def test_lb_gates_035_branch_patch_rebuild_paths(self):
        """LB-GATES-035（branch，:4327-4392；重建分支 :4348-4352）、LB-EXIT-015。
        01-A07；C.4“补丁往返/完整性”（缺口：旧测试没有删除树对象，走不到 :4348 的重建分支）。

        特征化（PASS 之后）：
        - 树对象存在时（:4348 的 ``cat-file -e`` 成功）branch 既不调用 candidate_patch_ok，也不按补丁重建：
          candidate.patch 缺失、或换成空文件（按补丁重建会得到基线树）都照常建分支，退出 0，分支的树等于候选树；
        - 删除树对象（松散对象文件）→ 按补丁重建，分支的树等于候选树、父提交是基线；
        - 树对象丢失且补丁重建结果不同（换成空补丁）→ 退出 3“候选树对象已丢失，且补丁重建结果不一致”，不校验 patch_sha256；
        - 树对象丢失且 candidate.patch 也缺失 → tree_from_patch 的 ``patch.stat()``（:4349 → :824）抛出未捕获的
          FileNotFoundError（Traceback，退出 1）。可疑（legacy-inventory 11.2 第 3 条，原为推断，此处实测）。
        """
        repo, base = self.start("branch")
        code, out = self.verdict(repo, "PASS")
        self.assertEqual((code, self.state(repo)), (0, "PASS"), out)
        rd = self.rd(repo)
        patch = rd / "candidate.patch"
        tree = self.jload(rd / "candidate.json")["tree"]
        loose = repo / ".git" / "objects" / tree[:2] / tree[2:]

        def tree_present() -> bool:
            return self.sh(["git", "cat-file", "-e", tree + "^{tree}"], repo, check=False)[0] == 0

        def branch_exists(name: str) -> bool:
            return self.sh(["git", "rev-parse", "--verify", "--quiet", "refs/heads/" + name], repo, check=False)[0] == 0

        for label, data, name in (("补丁缺失", None, "t/no-patch"), ("补丁换成空文件", b"", "t/empty-patch")):
            with self.subTest("树对象存在：%s也能建分支，不按补丁重建" % label):
                self.assertTrue(tree_present())
                with self.replaced(patch, data):
                    code, out = self.tool(repo, "branch", REF, "--name", name)
                self.assertEqual(code, 0, out)
                self.assertIn("已创建本地分支 %s → " % name, out)
                self.assertEqual(self.git(repo, "rev-parse", name + "^{tree}"), tree)

        with self.subTest("树对象丢失：按补丁重建"):
            self.assertTrue(loose.is_file(), "候选树应是松散对象：%s" % loose)
            _write_or_remove(loose, None)
            self.assertFalse(tree_present())
            code, out = self.tool(repo, "branch", REF)
            self.assertEqual(code, 0, out)
            self.assertIn("已创建本地分支 pi/normalize-query-v1-a001 → ", out)
            self.assertTrue(tree_present())
            self.assertEqual(self.git(repo, "rev-parse", "pi/normalize-query-v1-a001^{tree}"), tree)
            self.assertEqual(self.git(repo, "rev-parse", "pi/normalize-query-v1-a001^"), base)

        with self.subTest("树对象丢失且重建结果不一致"):
            _write_or_remove(loose, None)
            with self.replaced(patch, b""):
                code, out = self.tool(repo, "branch", REF, "--name", "t/mismatch")
            self.assert_error(code, out, 3, "候选树对象已丢失，且补丁重建结果不一致")
            self.assertFalse(branch_exists("t/mismatch"))

        with self.subTest("树对象与补丁都缺失：未捕获异常（可疑）"):
            self.assertFalse(tree_present())
            with self.replaced(patch, None):
                code, out = self.tool(repo, "branch", REF, "--name", "t/nopatch")
            self.assert_traceback(code, out, "FileNotFoundError")
            self.assertFalse(branch_exists("t/nopatch"))


class VerdictRules(LegacyGateCase):

    def test_lb_gates_031_state_not_reviewable(self):
        """LB-GATES-031（前置校验顺序，:4263-4265）、LB-GATES-033（REVIEWABLE_STATES :80）、LB-EXIT-035（拒绝顺序）。
        01-A05、01-A07；C.4“G0–G6”（verdict 拒绝分支：非 REVIEWABLE 状态）。

        特征化：PREPARED、ABANDONED（mark 设置）与 UNKNOWN（state.json 缺失）都被拒，退出 3（DispatchError 缺省码）；
        状态检查先于复审报告检查（报告不存在也先报状态）。可复审的一侧见 test_lb_gates_033_*（INFRA_FAILURE、
        五种结论之后再次 verdict）、G1 的超时与取消用例（TIMEOUT、CANCELLED）。
        """
        repo, _base = self.make_repo("not-reviewable")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        missing = str(repo / ".agent/reviews/missing.md")
        code, out = self.verdict(repo, "PASS", review=missing)
        self.assert_error(code, out, 3, NOT_REVIEWABLE % "PREPARED")
        code, out = self.tool(repo, "mark", REF, "ABANDONED", "--reason", "特征化测试")
        self.assertEqual((code, self.state(repo)), (0, "ABANDONED"), out)
        code, out = self.verdict(repo, "PASS")
        self.assert_error(code, out, 3, NOT_REVIEWABLE % "ABANDONED")
        (self.rd(repo) / "state.json").unlink()
        code, out = self.verdict(repo, "REVISE", "--class", "PLAN_ERROR")
        self.assert_error(code, out, 3, NOT_REVIEWABLE % "UNKNOWN")
        self.assertFalse((self.rd(repo) / "verdicts").exists())

    def test_lb_gates_032_verdict_rejection_branches(self):
        """LB-GATES-031（:4267-4279）、LB-GATES-032（各结论的要求，:4284-4300）、LB-EXIT-014、LB-EXIT-035。
        01-A05、01-A07；C.4“G0–G6”（verdict 拒绝分支）。

        特征化（run 之后不 check，G3/G4 失败）：
        - 复审报告不存在或为空 → 2；Verdict 行不符 → 2；--waive 格式错（门禁名区分大小写、理由为空、缺“=”）→ 2；
          PASS 带错误格式的豁免也是 2，不打印 GATE 行（先于按门禁拒绝）；
        - --waive 格式校验先于门禁求值（:4274-4279 在 :4280 的 evaluate_gates 之前）：meta.json 缺少 worktree 键时，
          格式正确的 PASS 在 evaluate_gates（:4237）抛出未捕获的 KeyError（Traceback，退出 1），而错误格式的
          --waive 仍以 2 拒绝。可疑（legacy-inventory 5.6 G0 补充）：meta.json 不做校验，缺键时不是 G0 问题而是回溯；
        - argparse 拒绝未知 --class → 2；
        - PASS 有失败门禁时带合法豁免仍按门禁拒绝（退出 1，先判门禁再判豁免）；
        - ACCEPTED_WITH_EXCEPTION 缺失败门禁的豁免 → 2 并列出缺哪些；豁免齐全但缺 --decided-by → 2；
        - REVISE/BLOCKED/ESCALATE 缺 --class → 2，消息列出全部分类；
        所有拒绝都不改状态、不写 verdicts/。
        """
        repo, _base = self.start("verdict-reject", check=False)
        reviews = repo / ".agent/reviews"
        with self.subTest("复审报告不存在或为空"):
            missing = reviews / "missing.md"
            code, out = self.verdict(repo, "PASS", review=str(missing))
            self.assert_error(code, out, 2, NO_REVIEW % missing)
            empty = self.review(repo, "PASS", name="empty.md", text="")
            code, out = self.verdict(repo, "PASS", review=empty)
            self.assert_error(code, out, 2, NO_REVIEW % empty)
        with self.subTest("Verdict 行不符"):
            code, out = self.verdict(repo, "PASS", review=self.review(repo, "REVISE", name="other.md"))
            self.assert_error(code, out, 2, VERDICT_LINE % "PASS")
        with self.subTest("--waive 格式错误"):
            for bad in ("G7=原因", "g3=原因", "G3=   ", "G3", "=原因"):
                code, out = self.verdict(repo, "ACCEPTED_WITH_EXCEPTION", "--waive", bad, "--decided-by", "tester")
                self.assert_error(code, out, 2, WAIVE_FORMAT)
            code, out = self.verdict(repo, "PASS", "--waive", "G3")
            self.assert_error(code, out, 2, WAIVE_FORMAT)
        with self.subTest("--waive 格式校验先于门禁求值"):
            meta = self.rd(repo) / "meta.json"
            with self.replaced(meta, json_bytes(meta, lambda m: m.pop("worktree"))):
                code, out = self.verdict(repo, "PASS")
                self.assert_traceback(code, out, "KeyError: 'worktree'")
                code, out = self.verdict(repo, "PASS", "--waive", "G3")
                self.assert_error(code, out, 2, WAIVE_FORMAT)
        with self.subTest("argparse 拒绝未知 --class"):
            code, out = self.verdict(repo, "REVISE", "--class", "NOPE")
            self.assertEqual(code, 2, out)
            self.assertIn("argument --class: invalid choice: 'NOPE'", out)
        with self.subTest("PASS：门禁失败时先按门禁拒绝，不管豁免"):
            code, out = self.verdict(repo, "PASS")
            self.assert_pass_refused(repo, code, out, ["G3", "G4"], ["G3 " + NO_CHECK, "G4 " + NO_CHECK])
            code, out = self.verdict(repo, "PASS", "--waive", "G3=a", "--waive", "G4=b")
            self.assert_pass_refused(repo, code, out, ["G3", "G4"], ["G3 " + NO_CHECK, "G4 " + NO_CHECK])
            self.assertNotIn(PASS_NO_WAIVER, out)
        with self.subTest("ACCEPTED_WITH_EXCEPTION 缺豁免或 --decided-by"):
            code, out = self.verdict(repo, "ACCEPTED_WITH_EXCEPTION", "--decided-by", "tester")
            self.assert_error(code, out, 2, AWE_MISSING % "G3, G4")
            code, out = self.verdict(repo, "ACCEPTED_WITH_EXCEPTION", "--waive", "G3=a", "--decided-by", "tester")
            self.assert_error(code, out, 2, AWE_MISSING % "G4")
            code, out = self.verdict(repo, "ACCEPTED_WITH_EXCEPTION", "--waive", "G3=a", "--waive", "G4=b")
            self.assert_error(code, out, 2, AWE_NEEDS)
        with self.subTest("REVISE / BLOCKED / ESCALATE 缺 --class"):
            for verdict in ("REVISE", "BLOCKED", "ESCALATE"):
                code, out = self.verdict(repo, verdict)
                self.assert_error(code, out, 2, NEEDS_CLASS % verdict)
        self.assertEqual(self.state(repo), "NEEDS_REVIEW")
        self.assertFalse((self.rd(repo) / "verdicts").exists())

    def test_lb_gates_032_waiver_rules_when_all_gates_pass(self):
        """LB-GATES-032（:4291-4298）、LB-GATES-038（与 gates.md 的不一致）。01-A05、01-A07；C.4“G0–G6”（verdict 拒绝分支）。

        特征化（七门全过）：PASS 带豁免 → 2“PASS 不接受豁免”；ACCEPTED_WITH_EXCEPTION 即使没有失败门禁也至少要一项
        --waive 与 --decided-by（缺一 → 2）；可以豁免已通过的门禁；同一门禁重复豁免时保留最后一条，理由去掉首尾空白
        后存储（:4279）。之后（LB-GATES-033，REVIEWABLE_STATES :80）：AWE 之后可以再记 PASS，且 PASS 带 --class 不被
        拒绝（legacy-inventory 5.9 PASS 行“拒绝 --waive，不拒绝 --class”），failure_class 照样写进记录与 state.json
        （:4306、:4312）；PASS 之后还能再记 REVISE（5.9 状态行“已有结论的 attempt 可以再次 verdict”）。
        可疑（legacy-inventory 5.9 AWE 行）：gates.md 只要求“每个失败门禁都要 --waive”，源码另要求至少一项豁免。
        可疑（5.9 状态行、11.2 第 12 条）：gates.md 称 PASS/AWE 之后只能到 INTEGRATED/ABANDONED。
        """
        repo, _base = self.start("waive-all-pass")
        code, out = self.verdict(repo, "PASS", "--waive", "G5=无需豁免")
        self.assert_error(code, out, 2, PASS_NO_WAIVER)
        code, out = self.verdict(repo, "ACCEPTED_WITH_EXCEPTION", "--decided-by", "tester")
        self.assert_error(code, out, 2, AWE_NEEDS)
        code, out = self.verdict(repo, "ACCEPTED_WITH_EXCEPTION", "--waive", "G2=备注")
        self.assert_error(code, out, 2, AWE_NEEDS)
        self.assertEqual(self.state(repo), "NEEDS_REVIEW")
        self.assertFalse((self.rd(repo) / "verdicts").exists())
        code, out = self.verdict(repo, "ACCEPTED_WITH_EXCEPTION", "--waive", "G5=第一条", "--waive", "G5=  最后一条  ",
                                 "--decided-by", "tester")
        self.assertEqual((code, self.state(repo)), (0, "ACCEPTED_WITH_EXCEPTION"), out)
        self.assertIn("ACCEPTED_WITH_EXCEPTION 已记录（%s/01.json）。" % VERDICTS_REL, out)
        self.assertNotIn("未通过的门禁", out)
        record = self.verdict_record(repo, 1)
        self.assertEqual((record["waivers"], record["decided_by"]), ({"G5": "最后一条"}, "tester"))
        self.assertTrue(all(info["passed"] for info in record["gates"].values()))

        code, out = self.verdict(repo, "PASS", "--class", "PLAN_ERROR")
        self.assertEqual((code, self.state(repo)), (0, "PASS"), out)
        self.assertIn("PASS 已记录（%s/02.json）。" % VERDICTS_REL, out)
        second = self.verdict_record(repo, 2)
        self.assertEqual((second["verdict"], second["failure_class"], second["waivers"], second["state_before"]),
                         ("PASS", "PLAN_ERROR", {}, "ACCEPTED_WITH_EXCEPTION"))
        state = self.state_record(repo)
        self.assertEqual((state["verdict_no"], state["failure_class"]), (2, "PLAN_ERROR"))

        code, out = self.verdict(repo, "REVISE", "--class", "EXECUTION_ERROR")
        self.assertEqual((code, self.state(repo)), (0, "REVISE"), out)
        self.assertIn("REVISE 已记录（%s/03.json）。" % VERDICTS_REL, out)
        third = self.verdict_record(repo, 3)
        self.assertEqual((third["verdict"], third["failure_class"], third["state_before"]),
                         ("REVISE", "EXECUTION_ERROR", "PASS"))

    def test_lb_gates_033_repeat_verdict_increments_number(self):
        """LB-GATES-033（记录、状态迁移与重复下结论，:4301-4316、:80）、LB-GATES-029（失败记录中 G5 仍恒通过）。
        01-A05、01-A07；C.4“G0–G6”（verdict：重复记录）。

        特征化：REVISE（带 --class，--waive 不被拒绝、照样记录）写 verdicts/01.{md,json}，打印“未通过的门禁”；
        REVISE 仍在 REVIEWABLE_STATES 中，可以再记 ESCALATE → 02，state_before 为 REVISE，状态随最新结论变化；
        同样可以在 ESCALATE 之后记 BLOCKED（03）、在 BLOCKED 之后记 REVISE（04）。
        可疑（legacy-inventory 5.9 状态行、11.2 第 12 条）：gates.md 称 REVISE 之后只能到 ABANDONED，源码允许再次 verdict。
        """
        repo, _base = self.start("verdict-repeat", check=False)
        rd = self.rd(repo)
        review = self.review(repo, "REVISE")
        code, out = self.verdict(repo, "REVISE", "--class", "EXECUTION_ERROR", "--waive", "G3=记录在案",
                                 "--note", "第一次", review=review)
        self.assertEqual((code, self.state(repo)), (0, "REVISE"), out)
        self.assertIn("REVISE 已记录（%s/01.json）。" % VERDICTS_REL, out)
        self.assertIn("未通过的门禁：G3, G4", out)
        first = self.verdict_record(repo, 1)
        self.assertEqual((first["number"], first["verdict"], first["failure_class"], first["waivers"],
                          first["note"], first["state_before"]),
                         (1, "REVISE", "EXECUTION_ERROR", {"G3": "记录在案"}, "第一次", "NEEDS_REVIEW"))
        self.assertEqual(first["candidate_tree"], self.jload(rd / "candidate.json")["tree"])
        self.assertEqual((rd / "verdicts/01.md").read_bytes(), Path(review).read_bytes())
        self.assertEqual(first["review_sha256"], sha256_file(rd / "verdicts/01.md"))
        self.assertEqual(first["gates"]["G3"], {"passed": False, "problems": [NO_CHECK], "notes": []})
        self.assertEqual(first["gates"]["G5"], {"passed": True, "problems": [], "notes": [G5_NOTE]})
        state = self.state_record(repo)
        self.assertEqual((state["verdict_no"], state["failure_class"]), (1, "EXECUTION_ERROR"))
        code, out = self.verdict(repo, "ESCALATE", "--class", "PLAN_ERROR")
        self.assertEqual((code, self.state(repo)), (0, "ESCALATE"), out)
        self.assertIn("ESCALATE 已记录（%s/02.json）。" % VERDICTS_REL, out)
        second = self.verdict_record(repo, 2)
        self.assertEqual((second["number"], second["verdict"], second["state_before"]), (2, "ESCALATE", "REVISE"))
        self.assertEqual(sorted(p.name for p in (rd / "verdicts").iterdir()), ["01.json", "01.md", "02.json", "02.md"])
        for number, verdict, failure_class, before in ((3, "BLOCKED", "REQUIREMENT_BLOCKED", "ESCALATE"),
                                                       (4, "REVISE", "PLAN_ERROR", "BLOCKED")):
            code, out = self.verdict(repo, verdict, "--class", failure_class)
            self.assertEqual((code, self.state(repo)), (0, verdict), out)
            self.assertIn("%s 已记录（%s/%02d.json）。" % (verdict, VERDICTS_REL, number), out)
            record = self.verdict_record(repo, number)
            self.assertEqual((record["number"], record["verdict"], record["failure_class"], record["state_before"]),
                             (number, verdict, failure_class, before))

    def test_lb_gates_033_infra_failure_attempt_is_reviewable(self):
        """LB-GATES-033（REVIEWABLE_STATES :80 含 INFRA_FAILURE，:4264）、LB-LIFE-019（没有 assistant 回复 →
        INFRA_FAILURE，:3401-3402）。01-A05、01-A07；C.4“G0–G6”（verdict：可复审的状态）。

        特征化：stub 的 startfail 场景（pi 报缺少 API key、退出 1，没有 assistant 消息）→ 状态 INFRA_FAILURE，run 退出 1；
        不 check 也可以直接记 REVISE --class INFRA_FAILURE（退出 0），state_before 为 INFRA_FAILURE，G1 未通过。
        """
        repo, _base = self.start("verdict-infra", scenario="startfail", check=False, expect_run=(1, "INFRA_FAILURE"))
        code, out = self.verdict(repo, "REVISE", "--class", "INFRA_FAILURE")
        self.assertEqual((code, self.state(repo)), (0, "REVISE"), out)
        self.assertIn("REVISE 已记录（%s/01.json）。" % VERDICTS_REL, out)
        record = self.verdict_record(repo, 1)
        self.assertEqual((record["verdict"], record["failure_class"], record["state_before"]),
                         ("REVISE", "INFRA_FAILURE", "INFRA_FAILURE"))
        self.assertFalse(record["gates"]["G1"]["passed"])
        self.assertIn("Pi 退出码为 1", record["gates"]["G1"]["problems"])
        self.assertEqual(self.state_record(repo)["failure_class"], "INFRA_FAILURE")


def _print_facts() -> None:
    facts = legacy_facts()
    print("被测 pi_dispatch.py sha256=%s（与 a4fa199 一致：%s）；Python %s；%s"
          % (facts["pi_dispatch_sha256"], facts["pi_dispatch_matches_a4fa199"], facts["python"], facts["platform"]),
          file=sys.stderr)


if __name__ == "__main__":
    _print_facts()
    unittest.main(verbosity=2)
