"""⑤j3 经真启动器的场景用：顶替 hub 起的长命子进程（主任务 runner、owner-sweep），不碰信箱与仓库，不起回合。场景把它复制进自己的
临时目录，再经 hub_launcher.py 让 hub 起它：TS 一边照 context.kit_hub 起 [python, 本文件, --repo, 仓库, …]，Python 一边照
subprocess.Popen 换掉第二项。

起来之后把这些写进本文件旁边的 <角色>.json（先写临时文件再改名）：整条命令行（GetCommandLineW）、sys.executable、sys.argv、进程号、
直接所在的 Job 的 LimitFlags（不在任何 Job 里是 -1）、有没有控制台窗口、窗口可见不可见。角色是 owner-sweep、task-<主任务> 或 run。
之后每 0.1 秒看一次旁边的 release，有了就退出；收到 CTRL_BREAK 先写 <角色>.break 再退出；最多活 120 秒，场景中途挂了也不留孤儿。
"""
import ctypes
import json
import os
import signal
import sys
import time
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
if "owner-sweep" in sys.argv:
    ROLE = "owner-sweep"
elif "--task" in sys.argv:
    ROLE = "task-" + sys.argv[sys.argv.index("--task") + 1]
else:
    ROLE = "run"

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.GetCommandLineW.restype = wintypes.LPCWSTR
k32.GetConsoleWindow.restype = wintypes.HWND
k32.QueryInformationJobObject.restype = wintypes.BOOL
k32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
user32 = ctypes.WinDLL("user32")
user32.IsWindowVisible.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]


class BasicLimit(ctypes.Structure):
    _fields_ = [("user", ctypes.c_longlong), ("job_user", ctypes.c_longlong), ("flags", wintypes.DWORD),
                ("low", ctypes.c_size_t), ("high", ctypes.c_size_t), ("active", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]


def job_flags() -> int:
    info = BasicLimit()
    ok = k32.QueryInformationJobObject(None, 2, ctypes.byref(info), ctypes.sizeof(info), None)
    return info.flags if ok else -1


def on_break(*_args) -> None:
    (HERE / (ROLE + ".break")).write_text(str(os.getpid()), encoding="utf-8")
    os._exit(3)


signal.signal(signal.SIGBREAK, on_break)
window = k32.GetConsoleWindow()
record = {
    "pid": os.getpid(), "cmdline": k32.GetCommandLineW(), "executable": sys.executable, "argv": sys.argv,
    "job_flags": job_flags(), "window": bool(window), "visible": bool(window) and bool(user32.IsWindowVisible(window)),
}
temporary = HERE / (ROLE + ".json.tmp")
temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
os.replace(temporary, HERE / (ROLE + ".json"))
deadline = time.monotonic() + 120
while not (HERE / "release").exists() and time.monotonic() < deadline:
    time.sleep(0.1)
