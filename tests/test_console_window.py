"""第 128 轮：没有控制台的进程起子进程时，子进程不弹窗口（CREATE_NO_WINDOW）。

Windows 给“父进程没有控制台”的控制台程序新开一个可见的控制台；这台机器的缺省终端是 Windows Terminal，桌面上就弹出
窗口，Job 中途结束时还留下一个报错窗口。run_supervised（检查命令、pi）与 run_handoff（启动器转交 TS）都要照顾到。
用例以 DETACHED_PROCESS 起一个没有控制台的 Python，由它经内核起子进程，子进程把 GetConsoleWindow() 写进文件。
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
NEWLINE = chr(10)

pytestmark = pytest.mark.skipif(os.name != "nt", reason="控制台窗口只在 Windows 上有")

REPORT = "import ctypes, sys; open(sys.argv[1], 'w').write(str(ctypes.windll.kernel32.GetConsoleWindow() or 0))"


def console_less(body: str, tmp_path: Path) -> str:
    """在没有控制台的 Python 里执行 body（pd、out、child 已备好），交回子进程写下的窗口句柄。"""
    out = tmp_path / "window.txt"
    code = NEWLINE.join([
        "import subprocess, sys",
        "sys.path.insert(0, %r)" % str(SCRIPTS),
        "import pi_dispatch as pd",
        "from pathlib import Path",
        "out = %r" % str(out),
        "child = [sys.executable, '-c', %r, out]" % REPORT,
        body,
    ])
    done = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path), capture_output=True, timeout=120,
                          creationflags=subprocess.DETACHED_PROCESS)
    assert out.exists(), done.stderr.decode("utf-8", "replace")[-2000:]
    return out.read_text()


def test_run_supervised_children_get_no_window(tmp_path):
    body = NEWLINE.join([
        "with open(%r, 'xb') as log:" % str(tmp_path / "log.txt"),
        "    pd.run_supervised(child, Path(%r), dict(__import__('os').environ), log, subprocess.STDOUT, 60, 1)" % str(tmp_path),
    ])
    assert console_less(body, tmp_path) == "0"


def test_run_handoff_children_get_no_window(tmp_path):
    assert console_less("pd.run_handoff(child, dict(__import__('os').environ))", tmp_path) == "0"

