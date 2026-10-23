"""run_supervised 结束进程树时的 CTRL_BREAK（第 70 轮，迁移计划第 8.2 节）。

GenerateConsoleCtrlEvent 只能发给与调用方共用同一个控制台的进程组。调用方本身的控制台状态由测试控制：用
DETACHED_PROCESS（没有控制台）或 CREATE_NO_WINDOW（有控制台、不显示窗口）起一个辅助进程，由它调 run_supervised，
结果写进文件。测试证明的是“子进程真的收到了”（标记文件），不只看返回值。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pi_dispatch as pd  # noqa: E402

pytestmark = pytest.mark.skipif(not pd.IS_WINDOWS, reason="CTRL_BREAK 与 Job Object 只在 Windows 上")

DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000

# 子进程：装 SIGBREAK 处理器，收到就写标记文件、以 3 退出；分小段睡，处理器才能及时运行（Windows 上 Python 的
# time.sleep 只被 SIGINT 提前唤醒）。另起一个脱离父进程的孙进程，记下它的编号，验证整棵树都被结束。
CHILD = r"""
import pathlib, signal, subprocess, sys, time
out = pathlib.Path(sys.argv[1])
def on_break(signum, frame):
    (out / "marker").write_text("got", encoding="utf-8")
    sys.exit(3)
signal.signal(signal.SIGBREAK, on_break)
grandchild = subprocess.Popen([sys.executable, "-c", "import time\nfor _ in range(1200): time.sleep(0.1)"],
                              creationflags=0x00000008, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
(out / "grandchild.pid").write_text(str(grandchild.pid), encoding="utf-8")
for _ in range(1200):
    time.sleep(0.1)
"""

# 调用方：调 run_supervised（timeout 1 秒、grace 15 秒），把结果写进 result.json。
CALLER = r"""
import json, os, pathlib, sys
sys.path.insert(0, sys.argv[1])
import pi_dispatch as pd
out = pathlib.Path(sys.argv[2])
with open(out / "stdout.log", "xb") as stdout, open(out / "stderr.log", "xb") as stderr:
    result = pd.run_supervised([sys.executable, "-c", sys.argv[3], str(out)], out, dict(os.environ), stdout, stderr,
                               1, 15.0)
(out / "result.json").write_text(json.dumps(result), encoding="utf-8")
"""


def run_caller(tmp_path: Path, flags: int) -> dict:
    subprocess.run([sys.executable, "-c", CALLER, str(SCRIPTS), str(tmp_path), CHILD], creationflags=flags,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
    return json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))


def wait_gone(pid: int) -> bool:
    for _ in range(100):
        if pd.pid_alive(pid) is False:
            return True
        import time
        time.sleep(0.1)
    return False


def test_a_caller_without_a_console_does_not_wait_out_the_grace(tmp_path):
    result = run_caller(tmp_path, DETACHED_PROCESS)
    assert result["timed_out"] is True and result["kill_method"] == "job-object"
    assert result["ctrl_break"] == "failed" and result["ctrl_break_winerror"] == 6  # ERROR_INVALID_HANDLE
    assert result["wall_seconds"] < 8, result  # 以前送不到也照样白等 15 秒
    assert not (tmp_path / "marker").exists()
    assert wait_gone(int(result["pid"])) and wait_gone(int((tmp_path / "grandchild.pid").read_text()))


def test_a_caller_with_a_hidden_console_really_delivers_ctrl_break(tmp_path):
    result = run_caller(tmp_path, CREATE_NO_WINDOW)
    assert result["timed_out"] is True and result["kill_method"] == "job-object"
    assert result["ctrl_break"] == "sent" and result["ctrl_break_winerror"] is None
    assert (tmp_path / "marker").read_text(encoding="utf-8") == "got"  # 子进程真的收到了
    assert result["exit_code"] == 3 and result["wall_seconds"] < 8, result  # 没等满宽限就退出
    assert wait_gone(int((tmp_path / "grandchild.pid").read_text()))


class FakeProc:
    def __init__(self, returncode=None, error=None):
        self.returncode = returncode
        self.error = error
        self.sent = []

    def send_signal(self, sig):
        self.sent.append(sig)
        if self.error is not None:
            raise self.error


def test_the_ctrl_break_states_follow_cpython():
    # returncode 已知：CPython 的 send_signal 什么都不发
    done = FakeProc(returncode=0)
    assert pd._send_ctrl_break(done) == (None, None)
    assert pd._send_ctrl_break(FakeProc()) == ("sent", None)
    failed = FakeProc(error=OSError(22, "句柄无效", None, 6))
    assert pd._send_ctrl_break(failed) == ("failed", 6)
    assert pd._send_ctrl_break(FakeProc(error=ValueError("x"))) == ("failed", None)


def test_run_supervised_reports_no_ctrl_break_when_nothing_was_sent(tmp_path):
    with open(tmp_path / "o", "xb") as out, open(tmp_path / "e", "xb") as err:
        result = pd.run_supervised([sys.executable, "-c", "pass"], tmp_path, dict(os.environ), out, err, 30, 15.0)
    assert result["exit_code"] == 0 and result["ctrl_break"] is None and result["ctrl_break_winerror"] is None
