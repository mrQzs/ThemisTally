#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧调度器生命周期的特征化回归（01 P4；01-A07、01-A08，文档 C.4“锁与预算竞争”“超时”“取消”“进程恢复”）。

锁定 HEAD a4fa199 时 scripts/pi_dispatch.py 的**现有**行为：取消、超时后的退出码、预算竞争落败方、墙钟预算
耗尽与剩余不足 60 秒、--timeout 被预算截短、allowed_executors 未命中、任务锁的等待超时与过期接管、pid 存活时
拒绝恢复、COLLECTING 状态恢复、attempt 编号（01-D03）。断言的是现状，不是期望：现状可疑的地方在 docstring
中标“可疑”，并引用 docs/themis-tally-v2/01-baseline/legacy-inventory.md 的条目号（LB-*）或小节号。

- 每个用例的 docstring 写对应的 LB-* 条目（或“新增：<源码行号>”）与验收号；源码行号指 a4fa199 的
  scripts/pi_dispatch.py。
- 临时仓库、受控环境与假 pi 都来自 tests/legacy_harness.py（01-L05 隔离：不调用真实 pi/claude/codex，不联网）。
- 标“白盒”的用例在进程内加载被测源码（legacy_harness.load_legacy_module），直接调用 TaskLock 或 set_state；
  修改的默认参数都用 addCleanup 恢复。
- 平台：本机为 Windows。CTRL_BREAK_EVENT 的用例只在 Windows 且当前进程有控制台时运行；SIGINT 的用例只在
  POSIX 上运行（本机跳过，结果为 NOT_RUN）；各自的跳过原因写在 skipUnless 中。
- PID 复用：“Pi 已退出后 collect --recover”的用例在 Pi 存活时就打开它的进程句柄（LifecycleCase.reserve_pid），
  用例结束前这个 PID 不会分配给别的进程，旧实现 pid_alive（:726-733，Windows 用 tasklist）的判断因此是确定的；
  否则 PID 被别的进程占用时恢复会被拒（legacy-inventory.md 6.11 第 5 项“PID 复用会被误判为存活”）。
- 运行：python tests/test_legacy_lifecycle.py（01-L04：按文件单独运行，不用 unittest discover）。
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
import types
import unittest
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

sys.dont_write_bytecode = True  # 导入 legacy_harness 时不写 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))

from legacy_harness import (  # noqa: E402
    IS_WINDOWS, OK_FILES, PLAN_KEY, PY, TASK_ID, LegacyCase, alive, jload, kill_tree, legacy_facts, ok_events,
    remove_tree, send_interrupt,
)

#: Windows 进程被控制台 Ctrl 事件的系统默认处理结束时的退出码（STATUS_CONTROL_C_EXIT）。
STATUS_CONTROL_C_EXIT = 0xC000013A
REF1 = "normalize-query/attempt-001"
LOCK_REFUSED_TAIL = "（另一个 run 正在领取；如确认无人使用可删除该目录）"
#: run_ok_reserving_pi 的假 pi 输出完全部事件后再停留的秒数：测试在这段时间内打开它的进程句柄。
PI_LINGER_SECONDS = 3
#: reserve_pid 核对“打开的就是 pid.txt 记录的 Pi”时，进程创建时刻相对 pid.txt 修改时刻的容差（纳秒）。
#: 两者的时钟粒度可能不同；复用该 PID 的进程只能在 Pi 退出之后创建，至少晚 PI_LINGER_SECONDS 秒，远超此容差。
PID_CREATION_TOLERANCE_NS = 1_000_000_000
#: FILETIME（1601-01-01 起的 100ns 计数）与 Unix 纪元之差。
_FILETIME_UNIX_EPOCH = 116444736000000000


def _win_open_process(pid: int):
    """Windows：打开进程句柄（SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION），返回 (关闭函数, 创建时刻 ns)。

    用独立的 WinDLL 实例声明函数签名，不改动 ctypes.windll.kernel32（进程内加载的被测模块也用它）。
    句柄打开期间，即使进程已退出，系统也不会把它的 PID 分配给别的进程；已退出的进程不出现在 tasklist 中。
    失败时抛 OSError。"""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k32.GetProcessTimes.restype = wintypes.BOOL
    k32.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    k32.CloseHandle.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = k32.OpenProcess(0x00100000 | 0x1000, False, int(pid))
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    times = [wintypes.FILETIME() for _ in range(4)]
    if not k32.GetProcessTimes(handle, *[ctypes.byref(t) for t in times]):
        error = ctypes.get_last_error()
        k32.CloseHandle(handle)
        raise ctypes.WinError(error)
    created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
    return (lambda: k32.CloseHandle(handle)), (created - _FILETIME_UNIX_EPOCH) * 100


#: 白盒子进程（test_LB_LIFE_006_task_lock_release_ignores_ownership_whitebox 的持有者 A）：从 KIT 加载被测
#: pi_dispatch.py（与 legacy_harness.load_legacy_module 相同，编译执行读到的字节、不写字节码），进入 TaskLock，
#: 把自己的 pid 与 owner.json 写进就绪文件，等到释放文件出现后离开 with（执行 __exit__）并退出 0；120 秒内
#: 等不到释放文件时退出 5。
_LOCK_HOLDER_SCRIPT = r'''# -*- coding: utf-8 -*-
import json
import os
import sys
import time
import types
from pathlib import Path

source, runs_dir, ready, release = sys.argv[1:5]
module = types.ModuleType("codekit_legacy_lock_holder")
module.__file__ = source
sys.modules[module.__name__] = module
exec(compile(Path(source).read_bytes(), source, "exec"), module.__dict__)
lock = module.TaskLock(types.SimpleNamespace(runs_dir=Path(runs_dir)), "t")
with lock:
    owner = json.loads((lock.path / "owner.json").read_text(encoding="utf-8"))
    Path(ready + ".tmp").write_text(json.dumps({"pid": os.getpid(), "owner": owner}), encoding="utf-8")
    os.replace(ready + ".tmp", ready)
    deadline = time.monotonic() + 120
    while not Path(release).exists():
        if time.monotonic() > deadline:
            sys.exit(5)
        time.sleep(0.05)
sys.exit(0)
'''


def _windows_console_available() -> bool:
    """GenerateConsoleCtrlEvent（CTRL_BREAK_EVENT）要求当前进程有控制台；GetConsoleCP 在没有控制台时返回 0。"""
    if not IS_WINDOWS:
        return False
    try:
        import ctypes
        return bool(ctypes.windll.kernel32.GetConsoleCP())  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False


WINDOWS_CONSOLE = _windows_console_available()
SKIP_NO_CTRL_BREAK = ("只在 Windows 且当前进程有控制台时运行：CTRL_BREAK_EVENT 由 GenerateConsoleCtrlEvent 发送，"
                      "要求控制台；POSIX 的对应用例见 *_posix")
SKIP_NOT_POSIX = "只在 POSIX 上运行：SIGINT 到达调度器的语义（KeyboardInterrupt/_Interrupted）；Windows 用 CTRL_BREAK 用例"


class LifecycleCase(LegacyCase):
    """生命周期用例的公共辅助（只读 attempt 证据，或按注明的方式构造旧实现可达的状态）。"""

    # -- 证据读取 -------------------------------------------------------------

    def attempt_names(self, repo: Path) -> list:
        """.agent/runs/<task>/ 下所有以 attempt- 开头的目录名（含不匹配旧正则的，便于看出被忽略的目录）。"""
        base = repo / ".agent/runs" / TASK_ID
        if not base.is_dir():
            return []
        return sorted(d.name for d in base.iterdir() if d.is_dir() and d.name.startswith("attempt-"))

    def history(self, repo: Path, n: int = 1) -> list:
        text = (self.rd(repo, n) / "history.jsonl").read_text(encoding="utf-8")
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    def history_kinds(self, repo: Path, n: int = 1) -> list:
        """history.jsonl 的记录种类：state:<STATE> 或 event:<EVENT>（set_state/log_event，:2539-2551）。"""
        return [("state:%s" % r["state"]) if "state" in r else ("event:%s" % r.get("event"))
                for r in self.history(repo, n)]

    @staticmethod
    def failed_gates(out: str):
        """从“PASS 被拒绝：门禁 G1, G4 未通过。”（:4289）取出门禁列表；没有这句时返回 None。"""
        match = re.search(r"PASS 被拒绝：门禁 ([G0-9, ]+) 未通过", out)
        return match.group(1).split(", ") if match else None

    # -- 构造旧实现可达的状态 ---------------------------------------------------

    def fake_claim(self, repo: Path, n: int, timeout_seconds: int) -> None:
        """构造“领取后调度器立即退出”的 attempt（LB-LIFE-022 所列可达状态，同 test_stuck_states 的 mkdir claim）：
        claim/ 目录加 reservation.json（字段同 :3314-3315）；没有 run.json，budget_usage 按预留时限计时（:2577-2579）。"""
        claim = self.rd(repo, n) / "claim"
        claim.mkdir()
        (claim / "reservation.json").write_text(
            json.dumps({"timeout_seconds": timeout_seconds, "pid": 0, "at": "2026-09-25T00:00:00Z"}, indent=2) + "\n",
            encoding="utf-8")

    def fake_run_json(self, repo: Path, n: int, wall_seconds) -> None:
        """在（已由 fake_claim 领取的）attempt 中写 run.json，只含 budget_usage 读取的 wall_seconds（:2574-2576）。
        wall_seconds 为 None 时同 collect --recover 合成的 run.json（:3430-3431），budget_usage 回退到按预留计时。"""
        (self.rd(repo, n) / "run.json").write_text(json.dumps({"wall_seconds": wall_seconds}, indent=2) + "\n",
                                                   encoding="utf-8")

    def lock_dir(self, repo: Path) -> Path:
        """TaskLock 的位置：.agent/runs/<task_id>/.task.lock（:2587）。"""
        return repo / ".agent/runs" / TASK_ID / ".task.lock"

    def hold_lock(self, repo: Path, age_seconds: float = 0.0) -> Path:
        """模拟另一个 run 持有任务锁：建锁目录与一个旧实现不会读取的 owner.json（:2597 只写不读），
        age_seconds>0 时把锁目录的 mtime 改到那么久以前（过期判定只看 mtime，:2601-2604）。"""
        lock = self.lock_dir(repo)
        lock.mkdir(parents=True)
        (lock / "owner.json").write_text('{"pid": "not-a-pid", "at": "unreadable"}\n', encoding="utf-8")
        if age_seconds:
            stamp = time.time() - age_seconds
            os.utime(str(lock), (stamp, stamp))
        return lock

    # -- 后台进程 ---------------------------------------------------------------

    def finish(self, proc: subprocess.Popen, timeout: float = 300.0):
        """等待 popen_tool 启动的进程结束，返回 (退出码, 合并输出)；超时则结束进程树并使用例失败。"""
        try:
            out, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(proc)
            out, _ = proc.communicate(timeout=60)
            self.fail("后台调度器 %.0fs 内没有结束：\n%s" % (timeout, (out or b"").decode("utf-8", "replace")[-3000:]))
        return proc.returncode, (out or b"").decode("utf-8", "replace")

    def wait_path(self, proc: subprocess.Popen, path: Path, timeout: float = 120.0) -> None:
        """轮询等待 path 出现；调度器提前退出或超时都使用例失败（附上输出）。"""
        ok = self.wait_for(lambda: path.exists() or proc.poll() is not None, timeout)
        if not path.exists():
            code, out = self.finish(proc, 60) if proc.poll() is not None else (None, "")
            self.fail("等待 %s 失败（ok=%s，调度器退出码 %s）：\n%s" % (path, ok, code, out[-3000:]))

    def start_hang_run(self, repo: Path, new_process_group: bool = False):
        """prepare 后在后台 run（stub 的 hang 场景：写候选文件、输出第一条助手消息、起孙进程、睡 600s）。

        等到 pid.txt（on_spawn 写入，:3336-3337；此时中断处理器已安装，:676）与孙进程的 child.pid 都出现后返回
        (proc, pi_pid, grandchild_pid)；孙进程登记到清理列表。"""
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        proc = self.popen_tool(repo, "run", REF1, env={"STUB_SCENARIO": "hang"}, new_process_group=new_process_group)
        self.wait_path(proc, self.rd(repo) / "pid.txt")
        self.wait_path(proc, self.worktree_of(repo) / "child.pid")
        pi_pid = int((self.rd(repo) / "pid.txt").read_text(encoding="utf-8").strip())
        grandchild = self.track_pid((self.worktree_of(repo) / "child.pid").read_text(encoding="utf-8").strip())
        return proc, pi_pid, grandchild

    def reserve_pid(self, pid: int, pid_file: Path) -> None:
        """在 Pi 仍存活时保留它的 PID，直到用例结束（legacy-inventory.md 6.11 第 5 项“PID 复用会被误判为存活”）。

        Windows：打开 Pi 的进程句柄，用 addCleanup 关闭。句柄未关闭时系统不会把这个 PID 分配给别的进程；已退出的
        进程不出现在 tasklist 中（本机实测），所以 Pi 退出后旧实现 pid_alive（:726-733）对它返回 False，
        collect --recover 放行是确定的。打开后核对进程创建时刻不晚于 pid.txt 的修改时刻（容差见
        PID_CREATION_TOLERANCE_NS）：pid.txt 在 Pi 创建之后写入（on_spawn，:3336-3337），复用该 PID 的进程只能
        在 Pi 退出后创建，所以通过核对就说明打开的正是 pid.txt 记录的 Pi。必须在 Pi 退出之前调用。
        POSIX：不做处理（PID 顺序分配，短时间内复用的可能很小；本机未取证）。"""
        if not IS_WINDOWS:
            return
        written_ns = pid_file.stat().st_mtime_ns
        try:
            close, created_ns = _win_open_process(pid)
        except OSError as exc:
            self.fail("无法打开 pid.txt 记录的 Pi 进程 %s（应在 Pi 存活时调用）：%s" % (pid, exc))
        self.addCleanup(close)
        self.assertLessEqual(created_ns, written_ns + PID_CREATION_TOLERANCE_NS,
                             "PID %s 已被别的进程复用：该进程创建于 pid.txt 写入之后（%d ns > %d ns）"
                             % (pid, created_ns, written_ns))

    def run_ok_reserving_pi(self, repo: Path):
        """prepare 后在后台 run attempt-001，并在 Pi 存活时保留它的 PID（reserve_pid）；返回 (退出码, 输出)。

        Pi 是 legacy_harness 的假 pi：事件为 ok_events()、文件为 OK_FILES（复现 stub 的 ok 场景），输出完后再停留
        PI_LINGER_SECONDS 秒、以 0 退出，留出打开句柄的时间。"""
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        pi = self.fake_pi(ok_events(), files=OK_FILES, hang_seconds=PI_LINGER_SECONDS)
        proc = self.popen_tool(repo, "run", REF1, pi_cmd=pi)
        pid_file = self.rd(repo) / "pid.txt"
        self.wait_path(proc, pid_file)
        # pid.txt 以 "x" 模式创建后才写入内容（write_text，:364-366）：等到内容完整再读。
        self.assertTrue(self.wait_for(lambda: pid_file.read_text(encoding="utf-8").strip().isdigit(), 30),
                        "pid.txt 内容不是进程号：%r" % pid_file.read_text(encoding="utf-8"))
        self.reserve_pid(int(pid_file.read_text(encoding="utf-8").strip()), pid_file)
        return self.finish(proc, 300)

    def pass_verdict(self, repo: Path, ref: str = REF1):
        return self.tool(repo, "verdict", ref, "--verdict", "PASS", "--review", self.review(repo, "PASS"))

    def assert_pi_exit_after_terminate(self, run: dict) -> None:
        """被 _terminate_tree 结束的 Pi（stub hang）的退出码（run.json.exit_code 是 Pi 进程自己的退出码，:719）。

        Windows：先向 Pi 的进程组发 CTRL_BREAK（:597-601），stub 没有 SIGBREAK 处理器，被系统默认处理结束，
        退出码 0xC000013A；这要求有控制台，没有控制台时发送失败，改由 TerminateJobObject 以退出码 1 结束（:543）。
        POSIX：killpg SIGTERM（:617），这里只要求不是 0 或 None（本机未取证）。"""
        if IS_WINDOWS and WINDOWS_CONSOLE:
            self.assertEqual(run["exit_code"], STATUS_CONTROL_C_EXIT, run)
        elif IS_WINDOWS:
            self.assertEqual(run["exit_code"], 1, run)
        else:
            self.assertNotIn(run["exit_code"], (0, None), run)

    def assert_hang_pass_refused(self, out: str) -> None:
        """stub hang 场景的 attempt（没有 check）上 verdict PASS 的门禁结果（:4152-4256、:4284-4290）：
        G1（本用例的原因另行断言；另有“没有观察到完整的结束事件”“最终 assistant stopReason=toolUse”）、
        G2（stub 把 child.pid 写进 worktree，范围外新文件）、G3 与 G4（没有有效的独立检查记录）未通过。"""
        self.assertEqual(self.failed_gates(out), ["G1", "G2", "G3", "G4"], out)
        self.assertIn("ERROR: PASS 被拒绝：门禁 G1, G2, G3, G4 未通过。", out)
        self.assertIn("GATE G1 没有观察到完整的结束事件（agent_settled / agent_end）", out)
        self.assertIn("GATE G1 最终 assistant stopReason=toolUse", out)
        self.assertIn("GATE G2 out_of_scope child.pid", out)
        self.assertIn("GATE G4 没有有效的独立检查记录", out)


# ---------------------------------------------------------------------------
# 取消
# ---------------------------------------------------------------------------

class CancelTests(LifecycleCase):

    @unittest.skipUnless(IS_WINDOWS and WINDOWS_CONSOLE, SKIP_NO_CTRL_BREAK)
    def test_LB_LIFE_017_ctrl_break_during_pi_run_is_cancelled_exit_1_not_130(self):
        """LB-LIFE-017（取消）、LB-LIFE-019、LB-LIFE-020、LB-EXIT-031；C.4“取消”（LB-TEST-COV-09）、01-A07。

        Pi 运行期间（run_supervised 内）向调度器进程组发送 CTRL_BREAK_EVENT：SIGBREAK 处理器抛 _Interrupted
        （:571-585），被 run_supervised 接住并置 interrupted=True、终止进程树（:703-706）；随后照常 collect，
        候选树存在、未超时，判定为 CANCELLED（:3399-3400）；run 返回 EXIT_FAIL=1（:3349），**不是** 130——
        main 的 KeyboardInterrupt→130（:4969-4971）不会到达，也不输出“已取消。”。
        verdict PASS 被 G1 拒绝：“运行被取消或调度器中断”（:4172）与“Pi 退出码为 <exit_code>”（:4173-4174），
        退出码 1（:4289-4290），状态保持 CANCELLED、不写 verdicts/；同时未通过的还有 G2、G3、G4（stub hang 场景
        与未运行 check 所致，见 assert_hang_pass_refused）。
        Pi 的 exit_code 是 Pi 进程自己的退出码：Windows 上 _terminate_tree 先向 Pi 发 CTRL_BREAK（:597-601），
        stub 没有 SIGBREAK 处理器，被系统默认处理结束（0xC000013A）；没有送达时由 TerminateJobObject 以 1 结束
        （:543）。取消的 attempt 保留 claim/，计入预算（:2572）。
        """
        repo, base = self.make_repo("cancel")
        self.write_config(repo, kill_grace_seconds=5)
        proc, pi_pid, grandchild = self.start_hang_run(repo, new_process_group=True)
        self.assertEqual(self.state(repo), "RUNNING")
        send_interrupt(proc)
        code, out = self.finish(proc, 180)
        self.assertEqual(code, 1, out)
        self.assertNotIn("已取消。", out)
        self.assertIn("CANCELLED normalize-query.v1.a001", out)
        self.assertEqual(self.state(repo), "CANCELLED")
        rd = self.rd(repo)
        run = jload(rd / "run.json")
        self.assertIs(run["interrupted"], True, run)
        self.assertIs(run["timed_out"], False, run)
        self.assertIsNone(run["spawn_error"], run)
        self.assertEqual(run["kill_method"], "job-object", run)
        self.assertNotIn("recovered", run)
        self.assert_pi_exit_after_terminate(run)
        record = self.state_record(repo)
        self.assertEqual(record["exit_code"], run["exit_code"], record)
        self.assertIs(record["events_ok"], False, record)
        self.assertIs(record["scope_ok"], False, record)
        self.assertEqual(self.history_kinds(repo),
                         ["state:PREPARING", "state:PREPARED", "state:RUNNING", "state:COLLECTING", "state:CANCELLED"])
        self.assertTrue((rd / "claim").is_dir())
        self.assertTrue(self.wait_for(lambda: not alive(pi_pid) and not alive(grandchild), 60),
                        "Pi %s 或孙进程 %s 仍在运行" % (pi_pid, grandchild))

        code, out = self.pass_verdict(repo)
        self.assertEqual(code, 1, out)
        self.assertIn("GATE G1 运行被取消或调度器中断", out)
        self.assertNotIn("GATE G1 运行超时", out)
        self.assertIn("GATE G1 Pi 退出码为 %s" % run["exit_code"], out)
        self.assert_hang_pass_refused(out)
        self.assertEqual(self.state(repo), "CANCELLED")
        self.assertFalse((rd / "verdicts").exists())

    @unittest.skipUnless(IS_WINDOWS and WINDOWS_CONSOLE, SKIP_NO_CTRL_BREAK)
    def test_LB_LIFE_035_ctrl_break_before_claim_kills_dispatcher_without_130(self):
        """LB-LIFE-035（各阶段收到 Ctrl+C 或信号后的状态）、LB-EXIT-031；C.4“取消”（LB-TEST-COV-09）、01-A07。

        可疑（与 legacy-inventory.md 6.5“run 领取前 Ctrl+C → 130”、7.3“run 的中断”的说法不同，那里指的是
        SIGINT/KeyboardInterrupt）：Windows 上中断处理器只在 run_supervised 内安装（:676、:712），其余时间
        SIGBREAK 没有 Python 处理器，CTRL_BREAK_EVENT 由系统默认处理直接结束调度器，退出码 0xC000013A
        （STATUS_CONTROL_C_EXIT），不经过 main 的 130 分支（:4969-4971），也不输出“已取消。”。
        构造：另一个 run 持有新鲜的任务锁，调度器写完 preflight/context-files.json（:3279-3280）后停在锁等待
        （:3300，最多 30s），此时发送。领取前被结束：状态保持 PREPARED、没有 claim/、run-started.json、
        run.json，history 不变（LB-LIFE-013）；锁目录是别人的，保持原样。
        """
        repo, base = self.make_repo("cancel-early")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        lock = self.hold_lock(repo)
        proc = self.popen_tool(repo, "run", REF1, env={"STUB_SCENARIO": "ok"}, new_process_group=True)
        self.wait_path(proc, self.rd(repo) / "preflight" / "context-files.json")
        send_interrupt(proc)
        code, out = self.finish(proc, 120)
        self.assertEqual(code, STATUS_CONTROL_C_EXIT, out)
        self.assertNotIn("已取消。", out)
        self.assertEqual(self.state(repo), "PREPARED")
        rd = self.rd(repo)
        for name in ("claim", "run-started.json", "run.json", "pid.txt"):
            self.assertFalse((rd / name).exists(), name)
        self.assertEqual(self.history_kinds(repo), ["state:PREPARING", "state:PREPARED"])
        self.assertTrue(lock.is_dir())

    @unittest.skipUnless(os.name == "posix", SKIP_NOT_POSIX)
    def test_LB_LIFE_017_sigint_during_pi_run_is_cancelled_exit_1_posix(self):
        """LB-LIFE-017、LB-LIFE-020、LB-EXIT-031；C.4“取消”（LB-TEST-COV-09）、01-A07。本机（Windows）NOT_RUN。

        POSIX 上 Pi 运行期间向调度器发 SIGINT：处理器抛 _Interrupted（:571-585），run_supervised 置
        interrupted=True 并对 Pi 进程组 SIGTERM→SIGKILL（:617-622、:703-706）；状态 CANCELLED，run 退出 1，
        不输出“已取消。”；verdict PASS 被 G1“运行被取消或调度器中断”拒绝，退出 1。
        """
        repo, base = self.make_repo("cancel-posix")
        self.write_config(repo, kill_grace_seconds=5)
        proc, pi_pid, grandchild = self.start_hang_run(repo, new_process_group=True)
        send_interrupt(proc)
        code, out = self.finish(proc, 180)
        self.assertEqual(code, 1, out)
        self.assertNotIn("已取消。", out)
        self.assertEqual(self.state(repo), "CANCELLED")
        run = jload(self.rd(repo) / "run.json")
        self.assertIs(run["interrupted"], True, run)
        self.assertIs(run["timed_out"], False, run)
        self.assertEqual(run["kill_method"], "process-group", run)
        self.assert_pi_exit_after_terminate(run)
        code, out = self.pass_verdict(repo)
        self.assertEqual(code, 1, out)
        self.assertIn("GATE G1 运行被取消或调度器中断", out)
        self.assertEqual(self.state(repo), "CANCELLED")

    @unittest.skipUnless(os.name == "posix", SKIP_NOT_POSIX)
    def test_LB_LIFE_035_sigint_before_claim_exits_130_posix(self):
        """LB-LIFE-035、LB-EXIT-002；C.4“取消”（LB-TEST-COV-09）、01-A07。本机（Windows）NOT_RUN。

        POSIX 上领取前（停在任务锁等待，:3300）收到 SIGINT：Python 默认处理器抛 KeyboardInterrupt，main 输出
        “已取消。”并返回 130（:4969-4971）；状态保持 PREPARED，没有 claim/（legacy-inventory.md 6.5“run 领取前
        Ctrl+C”）。
        """
        repo, base = self.make_repo("cancel-early-posix")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        lock = self.hold_lock(repo)
        proc = self.popen_tool(repo, "run", REF1, env={"STUB_SCENARIO": "ok"}, new_process_group=True)
        self.wait_path(proc, self.rd(repo) / "preflight" / "context-files.json")
        send_interrupt(proc)
        code, out = self.finish(proc, 120)
        self.assertEqual(code, 130, out)
        self.assertIn("已取消。", out)
        self.assertEqual(self.state(repo), "PREPARED")
        self.assertFalse((self.rd(repo) / "claim").exists())
        self.assertEqual(self.history_kinds(repo), ["state:PREPARING", "state:PREPARED"])
        self.assertTrue(lock.is_dir())


# ---------------------------------------------------------------------------
# 超时
# ---------------------------------------------------------------------------

class TimeoutTests(LifecycleCase):

    def test_LB_LIFE_016_timeout_run_exits_1_and_pass_refused_by_g1(self):
        """LB-LIFE-016（超时）、LB-LIFE-011、LB-LIFE-020、LB-EXIT-009；C.4“超时”（LB-TEST-COV-08）、01-A07。

        test_timeout 只检查了状态；这里补上退出码与门禁：--timeout 6 收紧本轮时限（:3308-3309，reservation 与
        run.json 都记 6），到期置 timed_out=True 并终止进程树（:691-697）；collect 判为 TIMEOUT（:3397-3398，
        判定在 CANCELLED 之前）；run 退出 1（:3349）。verdict PASS 被 G1“运行超时”（:4169-4170）拒绝，退出 1，
        状态保持 TIMEOUT、不写 verdicts/。孙进程随 Job Object/进程组一并结束。
        """
        repo, base = self.make_repo("hang")
        self.write_config(repo, kill_grace_seconds=2)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        code, out = self.tool(repo, "run", REF1, "--timeout", "6", env={"STUB_SCENARIO": "hang"})
        pid_file = self.worktree_of(repo) / "child.pid"
        grandchild = self.track_pid(pid_file.read_text(encoding="utf-8").strip()) if pid_file.exists() else None
        self.assertEqual(code, 1, out)
        self.assertIn("RUNNING normalize-query.v1.a001（时限 6s）", out)
        self.assertIn("TIMEOUT normalize-query.v1.a001", out)
        self.assertEqual(self.state(repo), "TIMEOUT")
        rd = self.rd(repo)
        run = jload(rd / "run.json")
        self.assertIs(run["timed_out"], True, run)
        self.assertIs(run["interrupted"], False, run)
        self.assertIsNone(run["spawn_error"], run)
        self.assertEqual(run["timeout_seconds"], 6, run)
        self.assertEqual(jload(rd / "claim" / "reservation.json")["timeout_seconds"], 6)
        self.assert_pi_exit_after_terminate(run)
        record = self.state_record(repo)
        self.assertEqual(record["exit_code"], run["exit_code"], record)
        self.assertIs(record["events_ok"], False, record)
        self.assertIs(record["scope_ok"], False, record)
        self.assertEqual(self.history_kinds(repo),
                         ["state:PREPARING", "state:PREPARED", "state:RUNNING", "state:COLLECTING", "state:TIMEOUT"])
        self.assertIsNotNone(grandchild, "stub 没有写出 child.pid")
        self.assertTrue(self.wait_for(lambda: not alive(grandchild), 30), "孙进程 %s 仍在运行" % grandchild)

        code, out = self.pass_verdict(repo)
        self.assertEqual(code, 1, out)
        self.assertIn("GATE G1 运行超时", out)
        self.assertNotIn("GATE G1 运行被取消或调度器中断", out)
        self.assertIn("GATE G1 Pi 退出码为 %s" % run["exit_code"], out)
        self.assert_hang_pass_refused(out)
        self.assertEqual(self.state(repo), "TIMEOUT")
        self.assertFalse((rd / "verdicts").exists())


# ---------------------------------------------------------------------------
# 预算
# ---------------------------------------------------------------------------

class BudgetTests(LifecycleCase):

    def test_LB_LIFE_012_budget_race_loser_stays_prepared_exit_3(self):
        """LB-LIFE-012（预算竞争的结果）、LB-LIFE-005、LB-LIFE-007、LB-LIFE-010；C.4“锁与预算竞争”
        （LB-TEST-COV-07）、01-A07。

        test_budget_race 只断言恰好一个 claim；这里补上落败方：两个已准备的 attempt 并发争最后一次额度
        （max_attempts_total=2，已用 1 次）。落败方在锁外预检（:3273-3275，不会进入 Pi 预检，没有 preflight/）
        或锁内复核（:3301-3303，已有 preflight/）被拒，两处文本相同：“BUDGET_EXCEEDED：已达到
        max_attempts_total=2。”，退出码 3；状态保持 PREPARED、没有 claim/、history 不留痕（:3275、:3303），
        worktree 保留。胜方 NEEDS_REVIEW、退出 0。之后 prepare 在锁外预检拒绝，退出 3，不分配新编号
        （:3183-3185）。拒绝点取决于时序，本用例两者都接受；锁外预检由
        test_LB_LIFE_012_run_count_precheck_outside_lock_refuses_before_preflight 确定性覆盖。
        """
        repo, base = self.make_repo("race", attempts=2)
        code, out = self.run_ok(repo)
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        for n in (2, 3):
            code, out = self.tool(repo, "prepare", PLAN_KEY)
            self.assertEqual(code, 0, out)
            self.assertIn("PREPARED normalize-query.v1.a%03d" % n, out)
        procs = {n: self.popen_tool(repo, "run", self.attempt_ref(n), env={"STUB_SCENARIO": "ok"}) for n in (2, 3)}
        results = {n: self.finish(proc, 300) for n, proc in procs.items()}
        claimed = [n for n in (2, 3) if (self.rd(repo, n) / "claim").is_dir()]
        self.assertEqual(len(claimed), 1, (claimed, results))
        winner = claimed[0]
        loser = 5 - winner
        self.assertEqual(results[winner][0], 0, results[winner][1])
        self.assertEqual(self.state(repo, winner), "NEEDS_REVIEW")
        loser_code, loser_out = results[loser]
        refusal_point = "锁内复核" if (self.rd(repo, loser) / "preflight").exists() else "锁外预检"
        self.assertEqual(loser_code, 3, (refusal_point, loser_out))
        self.assertIn("ERROR: BUDGET_EXCEEDED：已达到 max_attempts_total=2。", loser_out)
        self.assertEqual(self.state(repo, loser), "PREPARED")
        self.assertFalse((self.rd(repo, loser) / "claim").exists())
        self.assertFalse((self.rd(repo, loser) / "run-started.json").exists())
        self.assertEqual(self.history_kinds(repo, loser), ["state:PREPARING", "state:PREPARED"], refusal_point)
        self.assertTrue(self.worktree_of(repo, loser).is_dir())

        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 3, out)
        self.assertIn("ERROR: BUDGET_EXCEEDED：任务 normalize-query 已运行 2 次，达到 max_attempts_total=2。", out)
        self.assertEqual(self.attempt_names(repo), ["attempt-001", "attempt-002", "attempt-003"])

    def test_LB_LIFE_012_run_count_precheck_outside_lock_refuses_before_preflight(self):
        """LB-LIFE-012、LB-LIFE-010（prepare 不取锁、只数已领取的 attempt）、LB-LIFE-007；C.4“锁与预算竞争”
        （LB-TEST-COV-07）、01-A07。确定性覆盖 run 的锁外次数预检（:3273-3275）。

        构造：max_attempts_total=2；先 prepare 出 attempt-001～003（此时已领取 0 次，三次都放行，legacy-inventory.md
        11.2 第 11 项“可以准备出超额的 PREPARED”），再把 001、002 构造为已领取（fake_claim，各预留 100s，墙钟
        预算不是拒绝原因）。run attempt-003 在锁外预检被拒：“BUDGET_EXCEEDED：已达到 max_attempts_total=2。”，
        退出 3；拒绝发生在 Pi 预检（:3276-3280）之前，所以没有 preflight/；状态保持 PREPARED、没有 claim/、
        history 不留痕。锁内复核（:3301-3303）的文本相同，但它在 Pi 预检之后，只能由 preflight/ 是否存在区分。
        之后 prepare 在锁外预检拒绝（:3183-3185），不分配 attempt-004。
        """
        repo, base = self.make_repo("count-precheck", attempts=2)
        for n in (1, 2, 3):
            code, out = self.tool(repo, "prepare", PLAN_KEY)
            self.assertEqual(code, 0, out)
            self.assertIn("PREPARED normalize-query.v1.a%03d" % n, out)
        self.fake_claim(repo, 1, 100)
        self.fake_claim(repo, 2, 100)
        code, out = self.tool(repo, "run", self.attempt_ref(3), env={"STUB_SCENARIO": "ok"})
        self.assertEqual(code, 3, out)
        self.assertIn("ERROR: BUDGET_EXCEEDED：已达到 max_attempts_total=2。", out)
        rd = self.rd(repo, 3)
        self.assertFalse((rd / "preflight").exists(), "锁外预检应在 Pi 预检之前拒绝")
        self.assertNotIn("PREFLIGHT ", out)
        self.assertEqual(self.state(repo, 3), "PREPARED")
        for name in ("claim", "run-started.json", "run.json", "pid.txt"):
            self.assertFalse((rd / name).exists(), name)
        self.assertEqual(self.history_kinds(repo, 3), ["state:PREPARING", "state:PREPARED"])

        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 3, out)
        self.assertIn("ERROR: BUDGET_EXCEEDED：任务 normalize-query 已运行 2 次，达到 max_attempts_total=2。", out)
        self.assertEqual(self.attempt_names(repo), ["attempt-001", "attempt-002", "attempt-003"])

    def test_LB_LIFE_009_wall_budget_counts_actual_wall_seconds_from_run_json(self):
        """LB-LIFE-009（budget_usage：有 run.json 且 wall_seconds 非空时按实际用时计入）、LB-LIFE-010、LB-LIFE-011；
        C.4“锁与预算竞争”、01-A07。

        budget_usage 对已领取的 attempt：run.json 的 wall_seconds 不为 None 时计入它（:2574-2576），否则按
        claim/reservation.json 的 timeout_seconds 计入（:2577-2579）。构造 attempt-001 已领取、预留 600s，而
        run.json 记实际用时 1750s（取极端值以区分两个分支：实际用时可以超过预留，legacy-inventory.md 11.2 第 11 项）：
        - prepare 按 1750 核算，1750 < 1800，放行，分配 attempt-002（退出 0）；
        - attempt-002 的 run 在锁内被拒：“BUDGET_EXCEEDED：剩余墙钟预算 50s，不足 60s。”，退出 3（按预留计时
          则剩余 1200s，会放行）；保持 PREPARED、没有 claim/、history 不留痕。
        """
        repo, base = self.make_repo("wall-actual")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.fake_claim(repo, 1, 600)
        self.fake_run_json(repo, 1, 1750)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.assertIn("PREPARED normalize-query.v1.a002", out)
        code, out = self.tool(repo, "run", self.attempt_ref(2), env={"STUB_SCENARIO": "ok"})
        self.assertEqual(code, 3, out)
        self.assertIn("ERROR: BUDGET_EXCEEDED：剩余墙钟预算 50s，不足 60s。", out)
        self.assertEqual(self.state(repo, 2), "PREPARED")
        self.assertFalse((self.rd(repo, 2) / "claim").exists())
        self.assertEqual(self.history_kinds(repo, 2), ["state:PREPARING", "state:PREPARED"])

    def test_LB_LIFE_009_wall_seconds_null_falls_back_to_reservation(self):
        """LB-LIFE-009（budget_usage 的回退分支）、LB-LIFE-022（恢复合成的 run.json）、LB-LIFE-011；C.4“锁与预算竞争”、
        01-A07。

        run.json 存在但 wall_seconds 为 null（collect --recover 合成的 run.json 就是这样，:3430-3431）：按
        claim/reservation.json 的 timeout_seconds 计入（:2577-2579）。构造 attempt-001 已领取、预留 1750s、
        run.json 的 wall_seconds 为 null：prepare 放行 attempt-002；它的 run 在锁内被拒：“BUDGET_EXCEEDED：剩余
        墙钟预算 50s，不足 60s。”，退出 3（若把 null 当 0 计，剩余 1800s，会放行）；保持 PREPARED、没有 claim/。
        """
        repo, base = self.make_repo("wall-null")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.fake_claim(repo, 1, 1750)
        self.fake_run_json(repo, 1, None)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.assertIn("PREPARED normalize-query.v1.a002", out)
        code, out = self.tool(repo, "run", self.attempt_ref(2), env={"STUB_SCENARIO": "ok"})
        self.assertEqual(code, 3, out)
        self.assertIn("ERROR: BUDGET_EXCEEDED：剩余墙钟预算 50s，不足 60s。", out)
        self.assertEqual(self.state(repo, 2), "PREPARED")
        self.assertFalse((self.rd(repo, 2) / "claim").exists())
        self.assertEqual(self.history_kinds(repo, 2), ["state:PREPARING", "state:PREPARED"])

    def test_LB_LIFE_010_wall_total_exhausted_refused_by_run_and_prepare(self):
        """LB-LIFE-010（prepare 的预算预检）、LB-LIFE-011（run 的锁内复核）、LB-LIFE-009（按预留计时）；
        C.4“锁与预算竞争”（缺口“max_wall_seconds_total 耗尽（prepare 与 run 两种文本）”）、01-A07。

        构造：attempt-001 已领取、没有 run.json，预留 1800s（= max_wall_seconds_total），budget_usage 按预留计入
        （:2577-2579）。已准备好的 attempt-002 的 run：锁外次数预检通过（1<3），Pi 预检之后在锁内因剩余 0s 被拒：
        “BUDGET_EXCEEDED：剩余墙钟预算 0s，不足 60s。”，退出 3（:3304-3306），保持 PREPARED、没有 claim/。
        之后 prepare 因 used≥total 被拒：“BUDGET_EXCEEDED：累计运行 1800s，达到 max_wall_seconds_total=1800。”，
        退出 3（:3187-3189），不分配 attempt-003。
        """
        repo, base = self.make_repo("wall-exhausted")
        for _ in (1, 2):
            code, out = self.tool(repo, "prepare", PLAN_KEY)
            self.assertEqual(code, 0, out)
        self.fake_claim(repo, 1, 1800)
        code, out = self.tool(repo, "run", self.attempt_ref(2), env={"STUB_SCENARIO": "ok"})
        self.assertEqual(code, 3, out)
        self.assertIn("ERROR: BUDGET_EXCEEDED：剩余墙钟预算 0s，不足 60s。", out)
        self.assertEqual(self.state(repo, 2), "PREPARED")
        self.assertFalse((self.rd(repo, 2) / "claim").exists())
        self.assertTrue((self.rd(repo, 2) / "preflight").is_dir(), "锁内复核发生在 Pi 预检之后")
        self.assertEqual(self.history_kinds(repo, 2), ["state:PREPARING", "state:PREPARED"])

        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 3, out)
        self.assertIn("ERROR: BUDGET_EXCEEDED：累计运行 1800s，达到 max_wall_seconds_total=1800。", out)
        self.assertEqual(self.attempt_names(repo), ["attempt-001", "attempt-002"])

    def test_LB_LIFE_011_remaining_wall_under_60s_run_refused_but_prepare_allowed(self):
        """LB-LIFE-011（run 的预算复核）、LB-LIFE-010；C.4“锁与预算竞争”（缺口“剩余墙钟不足 60 s”）、01-A07。

        可疑（legacy-inventory.md 6.3“两个时长门槛不同”、11.2 第 11 项）：prepare 只在 used≥total 时拒绝
        （:3187），run 要求 total-used≥60（:3305）。构造 attempt-001 已领取、预留 1750s（total=1800）：prepare
        成功分配 attempt-002（退出 0），而它的 run 在锁内被拒：“BUDGET_EXCEEDED：剩余墙钟预算 50s，不足 60s。”，
        退出 3，保持 PREPARED、没有 claim/、history 不留痕。
        """
        repo, base = self.make_repo("wall-under-60")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.fake_claim(repo, 1, 1750)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.assertIn("PREPARED normalize-query.v1.a002", out)
        code, out = self.tool(repo, "run", self.attempt_ref(2), env={"STUB_SCENARIO": "ok"})
        self.assertEqual(code, 3, out)
        self.assertIn("ERROR: BUDGET_EXCEEDED：剩余墙钟预算 50s，不足 60s。", out)
        self.assertEqual(self.state(repo, 2), "PREPARED")
        self.assertFalse((self.rd(repo, 2) / "claim").exists())
        self.assertEqual(self.history_kinds(repo, 2), ["state:PREPARING", "state:PREPARED"])

    def test_LB_LIFE_011_remaining_wall_exactly_60s_is_allowed(self):
        """LB-LIFE-011（run 的预算复核，边界）；C.4“锁与预算竞争”（缺口“剩余墙钟不足 60 s”）、01-A07。

        门槛是严格小于：remaining_total < 60 才拒绝（:3305）。构造 attempt-001 已领取、预留 1740s（total=1800），
        剩余恰好 60s：attempt-002 的 run 放行，本轮时限 int(min(600, 60)) = 60（:3307），reservation、run-started.json、
        run.json 都记 60，输出“RUNNING normalize-query.v1.a002（时限 60s）”；stub ok 在时限内完成，NEEDS_REVIEW、退出 0。
        """
        repo, base = self.make_repo("wall-exactly-60")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.fake_claim(repo, 1, 1740)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        code, out = self.tool(repo, "run", self.attempt_ref(2), env={"STUB_SCENARIO": "ok"})
        self.assertEqual((code, self.state(repo, 2)), (0, "NEEDS_REVIEW"), out)
        self.assertNotIn("BUDGET_EXCEEDED", out)
        self.assertIn("RUNNING normalize-query.v1.a002（时限 60s）", out)
        rd = self.rd(repo, 2)
        self.assertEqual(jload(rd / "claim" / "reservation.json")["timeout_seconds"], 60)
        self.assertEqual(jload(rd / "run-started.json")["timeout_seconds"], 60)
        self.assertEqual(jload(rd / "run.json")["timeout_seconds"], 60)

    def test_LB_LIFE_011_remaining_wall_59s_is_refused(self):
        """LB-LIFE-011（run 的预算复核，边界）；C.4“锁与预算竞争”（缺口“剩余墙钟不足 60 s”）、01-A07。

        构造 attempt-001 已领取、预留 1741s（total=1800），剩余 59s < 60：attempt-002 的 run 在锁内被拒：
        “BUDGET_EXCEEDED：剩余墙钟预算 59s，不足 60s。”，退出 3（:3304-3306）；保持 PREPARED、没有 claim/、
        history 不留痕。与 test_LB_LIFE_011_remaining_wall_exactly_60s_is_allowed 一起固定 60 这个门槛。
        """
        repo, base = self.make_repo("wall-59")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.fake_claim(repo, 1, 1741)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        code, out = self.tool(repo, "run", self.attempt_ref(2), env={"STUB_SCENARIO": "ok"})
        self.assertEqual(code, 3, out)
        self.assertIn("ERROR: BUDGET_EXCEEDED：剩余墙钟预算 59s，不足 60s。", out)
        self.assertEqual(self.state(repo, 2), "PREPARED")
        self.assertFalse((self.rd(repo, 2) / "claim").exists())
        self.assertEqual(self.history_kinds(repo, 2), ["state:PREPARING", "state:PREPARED"])

    def test_LB_LIFE_011_timeout_flag_capped_by_per_attempt_budget(self):
        """LB-LIFE-011（本轮时限）；C.4“锁与预算竞争”（缺口“--timeout 被预算截短”）、01-A07。

        本轮时限 = int(min(max_wall_seconds_per_attempt, total-used))（:3307）；--timeout N 只能收紧：
        N 非 0 时取 max(1, min(时限, N))，N=0 时不生效（:3308-3309）。合同 per_attempt=600：
        --timeout 5000 → 600；--timeout 0 → 600。reservation、run-started.json、run.json 与“RUNNING …（时限 600s）”
        一致；两次都 NEEDS_REVIEW、退出 0。
        """
        repo, base = self.make_repo("timeout-cap")
        for n, flag in ((1, "5000"), (2, "0")):
            code, out = self.tool(repo, "prepare", PLAN_KEY)
            self.assertEqual(code, 0, out)
            code, out = self.tool(repo, "run", self.attempt_ref(n), "--timeout", flag, env={"STUB_SCENARIO": "ok"})
            self.assertEqual((code, self.state(repo, n)), (0, "NEEDS_REVIEW"), out)
            self.assertIn("RUNNING normalize-query.v1.a%03d（时限 600s）" % n, out)
            rd = self.rd(repo, n)
            self.assertEqual(jload(rd / "claim" / "reservation.json")["timeout_seconds"], 600, flag)
            self.assertEqual(jload(rd / "run-started.json")["timeout_seconds"], 600, flag)
            self.assertEqual(jload(rd / "run.json")["timeout_seconds"], 600, flag)

    def test_LB_LIFE_011_negative_timeout_flag_becomes_1s(self):
        """LB-LIFE-011（本轮时限）；legacy-inventory.md 6.3“本轮时限”（N 为负数时得到 1）；C.4“锁与预算竞争”
        （缺口“--timeout 被预算截短”）、01-A07。

        --timeout=-5（用等号写法，argparse 不会把 -5 当作选项）：-5 非 0，timeout = max(1, min(600, -5)) = 1
        （:3308-3309）；reservation、run-started.json、run.json 都记 1，输出“RUNNING normalize-query.v1.a001（时限 1s）”。
        用 stub 的 hang 场景使结果确定：1 秒后超时、终止进程树（kill_grace_seconds=2），TIMEOUT，run 退出 1。
        时限若变成 0，旧实现视为不限时（:691，deadline 为 None），hang 会一直运行，本用例在 180 秒后判失败。
        """
        repo, base = self.make_repo("timeout-negative")
        self.write_config(repo, kill_grace_seconds=2)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        code, out = self.tool(repo, "run", REF1, "--timeout=-5", env={"STUB_SCENARIO": "hang"}, timeout=180)
        pid_file = self.worktree_of(repo) / "child.pid"
        if pid_file.exists() and pid_file.read_text(encoding="utf-8").strip().isdigit():
            self.track_pid(pid_file.read_text(encoding="utf-8").strip())
        self.assertEqual(code, 1, out)
        self.assertIn("RUNNING normalize-query.v1.a001（时限 1s）", out)
        self.assertIn("TIMEOUT normalize-query.v1.a001", out)
        self.assertEqual(self.state(repo), "TIMEOUT")
        rd = self.rd(repo)
        self.assertEqual(jload(rd / "claim" / "reservation.json")["timeout_seconds"], 1)
        self.assertEqual(jload(rd / "run-started.json")["timeout_seconds"], 1)
        run = jload(rd / "run.json")
        self.assertEqual(run["timeout_seconds"], 1, run)
        self.assertIs(run["timed_out"], True, run)

    def test_LB_LIFE_011_timeout_flag_capped_by_remaining_total_budget(self):
        """LB-LIFE-011（本轮时限）、LB-LIFE-009；C.4“锁与预算竞争”（缺口“--timeout 被预算截短”）、01-A07。

        构造 attempt-001 已领取、预留 1500s（total=1800）：attempt-002 的本轮时限为
        int(min(600, 1800-1500)) = 300（:3307），--timeout 1000 被截为 300（:3309）；reservation 与 run.json 都记 300，
        输出“RUNNING normalize-query.v1.a002（时限 300s）”，NEEDS_REVIEW、退出 0。
        """
        repo, base = self.make_repo("timeout-remaining")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.fake_claim(repo, 1, 1500)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        code, out = self.tool(repo, "run", self.attempt_ref(2), "--timeout", "1000", env={"STUB_SCENARIO": "ok"})
        self.assertEqual((code, self.state(repo, 2)), (0, "NEEDS_REVIEW"), out)
        self.assertIn("RUNNING normalize-query.v1.a002（时限 300s）", out)
        rd = self.rd(repo, 2)
        self.assertEqual(jload(rd / "claim" / "reservation.json")["timeout_seconds"], 300)
        self.assertEqual(jload(rd / "run.json")["timeout_seconds"], 300)


# ---------------------------------------------------------------------------
# 执行模型允许列表
# ---------------------------------------------------------------------------

class ExecutorAllowlistTests(LifecycleCase):

    def test_LB_LIFE_036_allowed_executors_miss_refused_at_prepare_and_run(self):
        """LB-LIFE-036（run 领取前 resolve_executor 的拒绝）、LB-LIFE-003、LB-EXIT-005；C.4“锁与预算竞争”
        （缺口“allowed_executors 未命中”）、01-A07。

        allowed_executors 非空且没有 provider 与 model 同时相等的项时，resolve_executor 抛 DispatchError(
        “执行模型 step/step-5-preview 不在 .agent/dispatch.config.json 的 allowed_executors 中”, EXIT_BLOCKED)
        （:2688-2694）。prepare（JSON 合同写了 provider 与 model，:3178-3180）：退出 3，在分配编号之前，
        不建 .agent/runs/<task>/。run（prepare 之后才加入允许列表）：退出 3，在 Pi 预检之前（:3271），
        保持 PREPARED、没有 claim/ 与 preflight/，history 不留痕。
        """
        miss = [{"provider": "step", "model": "step-9-other"}]
        message = "ERROR: 执行模型 step/step-5-preview 不在 .agent/dispatch.config.json 的 allowed_executors 中"
        repo, base = self.make_repo("allowlist-miss")
        self.write_config(repo, allowed_executors=miss)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 3, out)
        self.assertIn(message, out)
        self.assertFalse((repo / ".agent/runs" / TASK_ID).exists())

        self.write_config(repo)
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.assertIn("PREPARED normalize-query.v1.a001", out)
        self.write_config(repo, allowed_executors=miss)
        code, out = self.tool(repo, "run", REF1, env={"STUB_SCENARIO": "ok"})
        self.assertEqual(code, 3, out)
        self.assertIn(message, out)
        self.assertEqual(self.state(repo), "PREPARED")
        for name in ("claim", "preflight"):
            self.assertFalse((self.rd(repo) / name).exists(), name)
        self.assertEqual(self.history_kinds(repo), ["state:PREPARING", "state:PREPARED"])


# ---------------------------------------------------------------------------
# 任务锁
# ---------------------------------------------------------------------------

class TaskLockTests(LifecycleCase):

    def patch_lock_defaults(self, wait_seconds: float, stale_seconds: float = 300.0):
        """白盒：临时改 TaskLock.__init__ 的默认参数（旧值 (30.0, 300.0)，:2586），用 addCleanup 恢复。"""
        pd = self.pd
        original = pd.TaskLock.__init__.__defaults__
        self.assertEqual(original, (30.0, 300.0))
        pd.TaskLock.__init__.__defaults__ = (wait_seconds, stale_seconds)
        self.addCleanup(setattr, pd.TaskLock.__init__, "__defaults__", original)
        return pd

    def test_LB_LIFE_005_held_task_lock_run_waits_30s_then_exit_3(self):
        """LB-LIFE-005（TaskLock 的获取与等待）、LB-LIFE-013；C.4“锁与预算竞争”（缺口“TaskLock 等待 30 s 后
        任务锁被占用”）、01-A07。黑盒，耗时约 30 秒。

        另一个 run 持有新鲜的锁（mtime 未超过 300s）时，run 每 0.2s 重试、最多 30s（:2586、:2593、:2607-2610），
        然后报“任务锁被占用：<锁路径>（另一个 run 正在领取；如确认无人使用可删除该目录）”，退出 3。
        owner.json 不被读取（内容无法解析也不影响，:2597）；锁目录保持原样（__enter__ 失败，__exit__ 不执行）；
        attempt 保持 PREPARED、没有 claim/、history 不留痕。删除锁目录后再次 run 沿用同一编号并成功。
        整个 run 的用时下界 30 秒；上界 60 秒是宽松值（锁等待 30 秒加进程启动、G0 核对与 Pi 预检的余量），
        用来发现等待时长变长。
        """
        repo, base = self.make_repo("lock-held")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        lock = self.hold_lock(repo)
        owner = (lock / "owner.json").read_bytes()
        started = time.monotonic()
        code, out = self.tool(repo, "run", REF1, env={"STUB_SCENARIO": "ok"})
        elapsed = time.monotonic() - started
        self.assertEqual(code, 3, out)
        match = re.search(r"ERROR: 任务锁被占用：(.+?)" + re.escape(LOCK_REFUSED_TAIL), out)
        self.assertIsNotNone(match, out)
        self.assertEqual(os.path.normcase(str(Path(match.group(1)).resolve())), os.path.normcase(str(lock.resolve())))
        self.assertGreaterEqual(elapsed, 30.0, "等待不足 30 秒：%.1fs" % elapsed)
        self.assertLess(elapsed, 60.0, "锁等待远超 30 秒：%.1fs" % elapsed)
        self.assertEqual(self.state(repo), "PREPARED")
        self.assertFalse((self.rd(repo) / "claim").exists())
        self.assertEqual(self.history_kinds(repo), ["state:PREPARING", "state:PREPARED"])
        self.assertTrue(lock.is_dir())
        self.assertEqual((lock / "owner.json").read_bytes(), owner)

        remove_tree(lock)
        code, out = self.tool(repo, "run", REF1, env={"STUB_SCENARIO": "ok"})
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        self.assertEqual(self.attempt_names(repo), ["attempt-001"])

    def test_LB_LIFE_006_stale_task_lock_taken_over_by_run(self):
        """LB-LIFE-006（过期接管）；C.4“锁与预算竞争”（缺口“300 s 过期接管”）、01-A07。黑盒。

        锁目录的 mtime 早于 300s（:2601-2604 只看 mtime，不看 owner.json 中的 pid）：run 删除它（rmtree）后
        重新取得锁，领取、运行成功（NEEDS_REVIEW、退出 0）；离开临界区时 __exit__ 删除锁目录（:2612-2613），
        原锁中的 owner.json 随之消失。
        """
        repo, base = self.make_repo("lock-stale")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        lock = self.hold_lock(repo, age_seconds=400)
        self.assertGreater(time.time() - lock.stat().st_mtime, 300)
        code, out = self.tool(repo, "run", REF1, env={"STUB_SCENARIO": "ok"})
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        self.assertNotIn("任务锁被占用", out)
        self.assertTrue((self.rd(repo) / "claim").is_dir())
        self.assertFalse(lock.exists())

    def test_LB_LIFE_005_task_lock_wait_timeout_and_stale_takeover_whitebox(self):
        """LB-LIFE-005、LB-LIFE-006；C.4“锁与预算竞争”、01-A07。白盒（进程内调用 TaskLock，默认等待改为 1.5s）。

        - 默认参数为 wait_seconds=30.0、stale_seconds=300.0（:2586）。
        - 锁被占用且未过期：约 wait_seconds 后抛 DispatchError，code=EXIT_BLOCKED(3)，消息逐字为
          “任务锁被占用：<path>（另一个 run 正在领取；如确认无人使用可删除该目录）”（:2607-2609）；不读取、
          不改动别人的 owner.json。等待时长不短于 wait_seconds（:2593、:2607），也不超过 wait_seconds + 1.5s
          （每轮睡 0.2s，:2610；1.5s 是宽松的调度余量）。
        - 锁目录 mtime 早于 stale_seconds：rmtree 后取得（:2604-2606），owner.json 改写为本进程 pid（:2597）；
          退出时删除锁目录。
        """
        wait = 1.5
        pd = self.patch_lock_defaults(wait)
        repo_ns = types.SimpleNamespace(runs_dir=self.work / "wb-runs")
        lock = repo_ns.runs_dir / "t" / ".task.lock"
        lock.mkdir(parents=True)
        (lock / "owner.json").write_text("not json\n", encoding="utf-8")
        started = time.monotonic()
        with self.assertRaises(pd.DispatchError) as caught:
            with pd.TaskLock(repo_ns, "t"):
                self.fail("被占用的锁不应取得")
        elapsed = time.monotonic() - started
        self.assertEqual(caught.exception.code, pd.EXIT_BLOCKED)
        self.assertEqual(pd.EXIT_BLOCKED, 3)
        self.assertEqual(str(caught.exception), "任务锁被占用：%s%s" % (lock, LOCK_REFUSED_TAIL))
        self.assertGreaterEqual(elapsed, wait)
        self.assertLess(elapsed, wait + 1.5, "锁等待远超 wait_seconds：%.2fs" % elapsed)
        self.assertEqual((lock / "owner.json").read_text(encoding="utf-8"), "not json\n")

        stamp = time.time() - 400
        os.utime(str(lock), (stamp, stamp))
        with pd.TaskLock(repo_ns, "t") as held:
            self.assertEqual(held.path, lock)
            owner = json.loads((lock / "owner.json").read_text(encoding="utf-8"))
            self.assertEqual(owner["pid"], os.getpid())
            self.assertEqual(sorted(owner), ["at", "pid"])
        self.assertFalse(lock.exists())

    def start_lock_holder(self, runs_dir: Path):
        """白盒：在子进程中以持有者 A 的身份进入 TaskLock（_LOCK_HOLDER_SCRIPT，从 KIT 加载被测源码）。

        等到就绪文件出现后返回 (proc, 就绪信息 {"pid", "owner"}, 释放文件路径)；创建释放文件后 A 离开临界区
        （执行 __exit__）并退出 0。子进程用受控环境（child_env），用例结束时若仍在运行则结束其进程树。"""
        script = self.work / "lock_holder.py"
        script.write_text(_LOCK_HOLDER_SCRIPT, encoding="utf-8")
        ready = self.work / "lock-holder.ready"
        release = self.work / "lock-holder.release"
        source = self.kit / "scripts" / "pi_dispatch.py"
        proc = subprocess.Popen([PY, str(script), str(source), str(runs_dir), str(ready), str(release)],
                                cwd=str(self.work), env=self.child_env(), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def cleanup() -> None:
            kill_tree(proc)
            if proc.stdout is not None and not proc.stdout.closed:
                proc.stdout.close()

        self.addCleanup(cleanup)
        if not self.wait_for(lambda: ready.exists() or proc.poll() is not None, 60) or not ready.exists():
            kill_tree(proc)
            out, _ = proc.communicate(timeout=60)
            self.fail("持有者 A 没有取得锁（退出码 %s）：\n%s" % (proc.returncode, (out or b"").decode("utf-8", "replace")))
        return proc, jload(ready), release

    def test_LB_LIFE_006_task_lock_release_ignores_ownership_whitebox(self):
        """LB-LIFE-006（过期接管与归属判断）；C.4“锁与预算竞争”（缺口“过期接管与归属缺失”）、01-A07。白盒。

        可疑（legacy-inventory.md 6.2“释放”、6.11 第 2 项、11.2 第 10 项）：A 持锁 → 锁目录 mtime 变旧 → B 接管
        （删除 A 的锁目录内容后重建，owner.json 写 B 的 pid）→ A 退出时 __exit__ 无条件 rmtree（:2612-2613），
        删掉了 B 持有的锁；B 仍在临界区时，C 可以立即取得锁（互斥失效）。B 之后退出时 ignore_errors，不报错。
        A 在子进程中持锁（start_lock_holder），B、C 在本进程：A 与 B 的 pid 不同，若 __exit__ 按 owner.json 的
        pid 核对归属，A 退出时就不会删除 B 的锁，本用例失败。
        """
        pd = self.patch_lock_defaults(0.6)
        repo_ns = types.SimpleNamespace(runs_dir=self.work / "wb-runs")
        lock = repo_ns.runs_dir / "t" / ".task.lock"
        proc_a, info_a, release_a = self.start_lock_holder(repo_ns.runs_dir)
        self.assertNotEqual(info_a["pid"], os.getpid())
        self.assertEqual(info_a["owner"]["pid"], info_a["pid"], info_a)
        self.assertTrue(lock.is_dir())
        holder_b = pd.TaskLock(repo_ns, "t")
        holder_c = pd.TaskLock(repo_ns, "t")
        entered = []
        try:
            (lock / "a-marker").write_text("A\n", encoding="utf-8")
            stamp = time.time() - 400
            os.utime(str(lock), (stamp, stamp))
            holder_b.__enter__()
            entered.append(holder_b)
            self.assertTrue(lock.is_dir())
            self.assertFalse((lock / "a-marker").exists(), "B 接管时应已删除 A 的锁目录")
            self.assertEqual(jload(lock / "owner.json")["pid"], os.getpid())

            release_a.write_text("release\n", encoding="utf-8")
            out_a, _ = proc_a.communicate(timeout=60)
            self.assertEqual(proc_a.returncode, 0, (out_a or b"").decode("utf-8", "replace"))
            self.assertFalse(lock.exists(), "A 退出时删除了 B 持有的锁")

            holder_c.__enter__()
            entered.append(holder_c)
            self.assertTrue(lock.is_dir(), "B 未释放时 C 已取得锁")
            self.assertEqual(jload(lock / "owner.json")["pid"], os.getpid())
        finally:
            for holder in reversed(entered):
                holder.__exit__(None, None, None)
        self.assertFalse(lock.exists())


# ---------------------------------------------------------------------------
# 恢复
# ---------------------------------------------------------------------------

class RecoverTests(LifecycleCase):

    def test_LB_LIFE_024_recover_refused_while_pi_alive_then_recovers_cancelled(self):
        """LB-LIFE-024（pid_alive）、LB-LIFE-022、LB-LIFE-023、LB-EXIT-010；C.4“进程恢复”（缺口“pid 仍存活时拒绝
        恢复”）、01-A08。

        调度器仍在运行（RUNNING，pid.txt 记录的 Pi 存活）时 collect --recover 被拒：“记录的 Pi 进程 <pid> 可能仍在
        运行；确认终止后再恢复。”，退出 3（:3421-3425），不写 run.json、不改名任何证据。调度器被强制结束
        （Windows：taskkill /F，不带 /T，由 Job Object 回收 Pi 与孙进程）后恢复：合成 run.json（exit_code=None、
        timed_out=False、interrupted=True、recovered=True、wall_seconds=None、spawn_error=None，:3426-3434），
        候选存在 → CANCELLED，输出“CANCELLED（恢复收集；事件可能不完整）”，退出 0（:3441-3443）；history 从 RUNNING
        直接到 CANCELLED（不经过 COLLECTING，:3440），再记 recovered_collection；不分配新编号。verdict PASS 被拒，
        退出 1：G1“运行被取消或调度器中断”“Pi 退出码为 None”，另有 G2/G3/G4（见 assert_hang_pass_refused）。
        Pi 运行期间即保留它的 PID（reserve_pid），Pi 被回收后这个 PID 不会被别的进程占用，第二次恢复的放行是确定的。
        """
        repo, base = self.make_repo("recover-alive")
        proc, pi_pid, grandchild = self.start_hang_run(repo)
        rd = self.rd(repo)
        self.reserve_pid(pi_pid, rd / "pid.txt")
        self.assertEqual(self.state(repo), "RUNNING")
        code, out = self.tool(repo, "collect", REF1, "--recover")
        self.assertEqual(code, 3, out)
        self.assertIn("ERROR: 记录的 Pi 进程 %d 可能仍在运行；确认终止后再恢复。" % pi_pid, out)
        self.assertEqual(self.state(repo), "RUNNING")
        self.assertFalse((rd / "run.json").exists())
        self.assertEqual(sorted(p.name for p in rd.iterdir() if p.name.endswith(".partial")), [])

        if IS_WINDOWS:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/F"], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(proc.pid, signal.SIGKILL)
            try:
                os.killpg(pi_pid, signal.SIGKILL)  # Pi 以 start_new_session 启动，进程组号等于其 pid
            except ProcessLookupError:
                pass
        self.finish(proc, 120)
        self.assertTrue(self.wait_for(lambda: not alive(pi_pid), 60), "Pi %s 仍在运行" % pi_pid)
        self.assertEqual(self.state(repo), "RUNNING")

        code, out = self.tool(repo, "collect", REF1, "--recover")
        self.assertEqual(code, 0, out)
        self.assertIn("CANCELLED（恢复收集；事件可能不完整）", out)
        self.assertEqual(self.state(repo), "CANCELLED")
        run = jload(rd / "run.json")
        self.assertIsNone(run["exit_code"], run)
        self.assertIs(run["timed_out"], False, run)
        self.assertIs(run["interrupted"], True, run)
        self.assertIs(run["recovered"], True, run)
        self.assertIsNone(run["wall_seconds"], run)
        self.assertIsNone(run["spawn_error"], run)
        record = self.state_record(repo)
        self.assertIsNone(record["exit_code"], record)
        self.assertIs(record["events_ok"], False, record)
        self.assertEqual(self.history_kinds(repo),
                         ["state:PREPARING", "state:PREPARED", "state:RUNNING", "state:CANCELLED",
                          "event:recovered_collection"])
        self.assertEqual(self.attempt_names(repo), ["attempt-001"])

        code, out = self.pass_verdict(repo)
        self.assertEqual(code, 1, out)
        self.assertIn("GATE G1 运行被取消或调度器中断", out)
        self.assertIn("GATE G1 Pi 退出码为 None", out)
        self.assert_hang_pass_refused(out)
        self.assertEqual(self.state(repo), "CANCELLED")

    def test_LB_LIFE_023_recover_from_collecting_reuses_run_json_and_can_pass(self):
        """LB-LIFE-023（恢复收集的结果与证据处理）、LB-LIFE-022、LB-EXIT-010；C.4“进程恢复”（缺口“COLLECTING 状态的
        恢复”“run.json 已存在时的恢复”“非可恢复状态或缺 --recover 时的 2”）、01-A08。

        构造：一次正常运行（run_ok_reserving_pi：复现 stub ok 场景的假 pi，Pi 存活时保留其 PID，所以 pid.txt
        记录的进程已退出、PID 不会被复用，pid_alive 为 False）结束后用 set_state 把状态改回 COLLECTING（模拟调度器
        死在收集阶段，:3344）。pid 存活时的拒绝由 test_LB_LIFE_024 的前半段覆盖。
        - 不带 --recover：退出 2，“…（当前 COLLECTING）。”（:3416-3420）。
        - collect --recover：run.json 已存在，原样沿用、字节不变（:3426）；candidate.json、changes.json、scope.json、
          candidate.patch 改名为 *.partial 后重新收集（:3436-3440），候选树不变；不经过 COLLECTING，直接
          NEEDS_REVIEW，记 recovered_collection，退出 0。
        - 再次 collect --recover（状态已是 NEEDS_REVIEW）：退出 2。
        - 可疑（legacy-inventory.md 6.10、11.2 第 13 项；与 dispatch-pi SKILL.md“恢复的证据不能直接作为 PASS 依据”
          不一致）：沿用已有 run.json 时 G1 通过，check 后 verdict PASS 被接受（退出 0，状态 PASS）。
        """
        repo, base = self.make_repo("recover-collecting")
        code, out = self.run_ok_reserving_pi(repo)
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        rd = self.rd(repo)
        run_bytes = (rd / "run.json").read_bytes()
        tree = jload(rd / "candidate.json")["tree"]
        self.pd.set_state(rd, "COLLECTING")

        code, out = self.tool(repo, "collect", REF1)
        self.assertEqual(code, 2, out)
        self.assertIn("ERROR: collect 只用于调度器异常退出后的恢复：需要状态 RUNNING/COLLECTING（或已领取的 PREPARED）"
                      "且指定 --recover（当前 COLLECTING）。", out)

        code, out = self.tool(repo, "collect", REF1, "--recover")
        self.assertEqual(code, 0, out)
        self.assertIn("NEEDS_REVIEW（恢复收集；事件可能不完整）", out)
        self.assertEqual(self.state(repo), "NEEDS_REVIEW")
        self.assertEqual((rd / "run.json").read_bytes(), run_bytes)
        for name in ("candidate.json", "changes.json", "scope.json", "candidate.patch"):
            self.assertTrue((rd / (name + ".partial")).is_file(), name)
            self.assertTrue((rd / name).is_file(), name)
        self.assertEqual(jload(rd / "candidate.json")["tree"], tree)
        self.assertEqual(self.history_kinds(repo)[-3:],
                         ["state:COLLECTING", "state:NEEDS_REVIEW", "event:recovered_collection"])
        self.assertEqual(self.attempt_names(repo), ["attempt-001"])

        code, out = self.tool(repo, "collect", REF1, "--recover")
        self.assertEqual(code, 2, out)
        self.assertIn("（当前 NEEDS_REVIEW）。", out)

        code, out = self.tool(repo, "check", REF1)
        self.assertEqual(code, 0, out)
        code, out = self.pass_verdict(repo)
        self.assertEqual((code, self.state(repo)), (0, "PASS"), out)

    @unittest.skipUnless(IS_WINDOWS, "只在 Windows 上运行：Path.rename 在目标已存在时抛 FileExistsError；POSIX 的 rename "
                                     "会覆盖目标，行为不同（未取证）")
    def test_LB_LIFE_023_second_recover_with_partial_present_crashes_on_windows(self):
        """LB-LIFE-023；新增：scripts/pi_dispatch.py:3436-3439、4964-4971；C.4“进程恢复”（缺口“.partial 重命名”）、01-A08。

        可疑（legacy-inventory.md 6.11 第 4 项、第 6 节未解决事项“二次 collect --recover 时 *.partial 已存在”）：第一次
        恢复已留下 candidate.json.partial；状态再次停在 COLLECTING 后恢复，candidate.json 改名撞上已存在的
        candidate.json.partial，Windows 上抛 FileExistsError，main 不捕获（只捕获 DispatchError 与
        KeyboardInterrupt），输出 Traceback、退出 1；状态停在 COLLECTING，不记 recovered_collection。
        运行用 run_ok_reserving_pi（Pi 存活时保留其 PID），两次恢复都不会因 PID 被复用而在 pid_alive 处被拒；
        pid 存活时的拒绝由 test_LB_LIFE_024 的前半段覆盖。
        """
        repo, base = self.make_repo("recover-twice")
        code, out = self.run_ok_reserving_pi(repo)
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        rd = self.rd(repo)
        self.pd.set_state(rd, "COLLECTING")
        code, out = self.tool(repo, "collect", REF1, "--recover")
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        self.pd.set_state(rd, "COLLECTING")
        code, out = self.tool(repo, "collect", REF1, "--recover")
        self.assertEqual(code, 1, out)
        self.assertIn("Traceback (most recent call last)", out)
        self.assertIn("FileExistsError", out)
        self.assertNotIn("恢复收集", out)
        self.assertEqual(self.state(repo), "COLLECTING")
        self.assertTrue((rd / "candidate.json").is_file())
        self.assertTrue((rd / "candidate.json.partial").is_file())
        self.assertEqual(self.history_kinds(repo)[-1], "state:COLLECTING")


# ---------------------------------------------------------------------------
# attempt 编号（01-D03）
# ---------------------------------------------------------------------------

class AttemptNumberTests(LifecycleCase):

    def test_LB_LIFE_002_first_attempt_is_1_and_only_prepare_advances(self):
        """LB-LIFE-002（首次编号为 1）、LB-LIFE-001、LB-LIFE-003、LB-LIFE-004；01-D03、01-A08。

        - 首次 prepare 得到 attempt-001：meta.attempt_no=1、attempt_id=normalize-query.v1.a001（:2621-2623、:3193）。
        - 预检失败（模型不在列表中）：退出 3，“预检失败：attempt 保持 PREPARED，未计入尝试次数。修正环境后可再次
          run。”（:3281-3285），记 preflight_failed，不领取、不分配新编号。
        - 修正后再次 run 沿用 attempt-001：NEEDS_REVIEW、退出 0。
        - 只有 prepare 使编号前进：第二次 prepare 得到 attempt-002；编号跨 plan_version 连续，v2 合同的 prepare
          得到 attempt-003（normalize-query.v2.a003），不从 1 重新开始（:2617，legacy-inventory.md 6.1“作用域”）。
        """
        repo, base = self.make_repo("numbering")
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.assertIn("PREPARED normalize-query.v1.a001", out)
        meta = jload(self.rd(repo) / "meta.json")
        self.assertEqual((meta["attempt_no"], meta["attempt_id"]), (1, "normalize-query.v1.a001"))
        self.assertEqual(self.attempt_names(repo), ["attempt-001"])

        code, out = self.tool(repo, "run", REF1, env={"STUB_MODELS": "openrouter stepfun/step-3.7-flash"})
        self.assertEqual(code, 3, out)
        self.assertIn("PREFLIGHT ", out)
        self.assertIn("ERROR: 预检失败：attempt 保持 PREPARED，未计入尝试次数。修正环境后可再次 run。", out)
        self.assertEqual(self.state(repo), "PREPARED")
        self.assertFalse((self.rd(repo) / "claim").exists())
        self.assertEqual(self.history_kinds(repo), ["state:PREPARING", "state:PREPARED", "event:preflight_failed"])
        self.assertEqual(self.attempt_names(repo), ["attempt-001"])

        code, out = self.tool(repo, "run", REF1, env={"STUB_SCENARIO": "ok"})
        self.assertEqual((code, self.state(repo)), (0, "NEEDS_REVIEW"), out)
        self.assertIn("NEEDS_REVIEW normalize-query.v1.a001", out)
        self.assertEqual(self.attempt_names(repo), ["attempt-001"])

        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.assertIn("PREPARED normalize-query.v1.a002", out)
        self.assertEqual(jload(self.rd(repo, 2) / "meta.json")["attempt_no"], 2)

        self.write_plan(repo, base, 2)
        code, out = self.tool(repo, "prepare", "normalize-query.v2")
        self.assertEqual(code, 0, out)
        self.assertIn("PREPARED normalize-query.v2.a003", out)
        meta = jload(self.rd(repo, 3) / "meta.json")
        self.assertEqual((meta["attempt_no"], meta["attempt_id"], meta["plan_version"]),
                         (3, "normalize-query.v2.a003", 2))
        self.assertEqual(self.attempt_names(repo), ["attempt-001", "attempt-002", "attempt-003"])

    def test_LB_LIFE_001_number_is_max_plus_one_and_never_zero(self):
        """LB-LIFE-001（目录名与编号格式）、LB-LIFE-002；01-D03、01-A08。

        number = max(已有编号, default=0) + 1（:2619-2621），只认 ^attempt-(\\d{3,})$（:62）：手工放入的
        attempt-000 与不足 3 位的 attempt-01 不影响结果，首个编号仍为 1（旧实现从不生成 0）；多补零的
        attempt-0007 按 7 参与取最大值，下一次得到 attempt-008（编号不回填空缺）。
        """
        repo, base = self.make_repo("numbering-max")
        base_dir = repo / ".agent/runs" / TASK_ID
        (base_dir / "attempt-000").mkdir(parents=True)
        (base_dir / "attempt-01").mkdir()
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.assertIn("PREPARED normalize-query.v1.a001", out)
        self.assertEqual(self.attempt_names(repo), ["attempt-000", "attempt-001", "attempt-01"])

        (base_dir / "attempt-0007").mkdir()
        code, out = self.tool(repo, "prepare", PLAN_KEY)
        self.assertEqual(code, 0, out)
        self.assertIn("PREPARED normalize-query.v1.a008", out)
        self.assertEqual(jload(self.rd(repo, 8) / "meta.json")["attempt_no"], 8)
        self.assertEqual(self.attempt_names(repo),
                         ["attempt-000", "attempt-0007", "attempt-001", "attempt-008", "attempt-01"])


if __name__ == "__main__":
    _facts = legacy_facts()
    print("被测 pi_dispatch.py sha256=%s（与 a4fa199 一致：%s）"
          % (_facts["pi_dispatch_sha256"], _facts["pi_dispatch_matches_a4fa199"]), file=sys.stderr)
    unittest.main(verbosity=2)
