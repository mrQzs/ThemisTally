"""⑤j3 经真启动器的场景用：在独立进程里调 kit_hub.main(argv)，也就是真的启动器，照场景的配置改几处。argv[1] 是配置文件（JSON）：

- scripts：内核的 scripts 目录。sys.path 用它，kit_hub.__file__ 跟着它的写法；
- selector：选择文件（pi_dispatch.KERNEL_IMPL_PATH）；
- argv：交给 kit_hub.main 的参数；
- context_out：hub 选 ts 时，真的 hub_handoff 交回的 context 原样写进这个文件（有没有 stub 都写）；
- stub：可选。长命子进程（主任务 runner、owner-sweep）换成这个脚本（hub_child_stub.py 的副本）：
  - hub 选 ts 时，把交给 TS 的 context.kit_hub 换成它；
  - hub 选 python 时，给 subprocess.Popen 包一层，命令行第二项是 kit_hub.py 的，换成它。别的子进程照旧；
  - popen_out：可选。换之前把原来的命令行写进这个文件（一行一条 JSON）；
- outer_job：可选。先把本进程放进一个 LimitFlags 为这个值的 Job，模拟从别的工具的 Job 里起 hub；
- interrupt：可选，{"ready": 路径, "signals": [...]}。ready 出现之后，在本进程里依次 signal.raise_signal，相隔 1.5 秒
  （同 test_kernel_impl 的 signalled）；
- 错误模式：import kit_hub 之前先清成 0，见下面那一处的注释；
- console：可选，{"stdout": 路径, "stderr": 路径}。本脚本先用 CREATE_NO_WINDOW 另起一份自己：独立的隐藏控制台，转发的 CTRL_BREAK
  只发给这个控制台上的 TS 进程组（learn27）。标准输出、错误写进这两个文件，交回它的退出码；300 秒没结束就结束整棵树。
"""
import ctypes
import json
import os
import signal
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000
CONFIG_PATH = Path(sys.argv[1])
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def own_console(streams) -> int:
    inner = CONFIG_PATH.with_name(CONFIG_PATH.stem + ".inner.json")
    inner.write_text(json.dumps(dict(CONFIG, console=None)), encoding="utf-8")
    with open(streams["stdout"], "wb") as out, open(streams["stderr"], "wb") as err:
        proc = subprocess.Popen([sys.executable, __file__, str(inner)], stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                creationflags=CREATE_NO_WINDOW)
        try:
            code = proc.wait(timeout=300)
        except subprocess.TimeoutExpired:
            taskkill = os.path.join(os.environ["SystemRoot"], "System32", "taskkill.exe")
            subprocess.run([taskkill, "/T", "/F", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            proc.wait()
            return 124
    return code - (1 << 32) if code > 0x7FFFFFFF else code  # NTSTATUS 之类的大值按有符号 32 位交给 sys.exit


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops", "read", "write", "other")]


class BasicLimit(ctypes.Structure):
    _fields_ = [("user", ctypes.c_longlong), ("job_user", ctypes.c_longlong), ("flags", wintypes.DWORD),
                ("low", ctypes.c_size_t), ("high", ctypes.c_size_t), ("active", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]


class ExtendedLimit(ctypes.Structure):
    _fields_ = [("basic", BasicLimit), ("io", IoCounters), ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]


def enter_outer_job(flags: int) -> None:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    job = k32.CreateJobObjectW(None, None)
    info = ExtendedLimit()
    info.basic.flags = flags
    if not (job and k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info))
            and k32.AssignProcessToJobObject(job, k32.GetCurrentProcess())):
        sys.exit("外层 Job 没建成：%d" % ctypes.get_last_error())


def record_handoff(kit_hub, stub) -> None:
    """hub 选 ts 时，真的 hub_handoff 交回的 context 原样写进 context_out；给了 stub 再把 context.kit_hub 换成它。"""
    real_handoff = kit_hub.hub_handoff

    def handoff(args, impl):
        pyargs = real_handoff(args, impl)
        Path(CONFIG["context_out"]).write_text(json.dumps(pyargs["context"]), encoding="utf-8")
        if stub:
            pyargs["context"]["kit_hub"] = stub
        return pyargs

    kit_hub.hub_handoff = handoff


def use_stub(kit_hub, stub: str) -> None:
    hub_file = str(Path(kit_hub.__file__))

    class StubPopen(subprocess.Popen):
        def __init__(self, args, *rest, **kwargs):
            if isinstance(args, list) and args[1:2] == [hub_file]:
                if CONFIG.get("popen_out"):
                    with open(CONFIG["popen_out"], "a", encoding="utf-8") as out:
                        out.write(json.dumps(args) + chr(10))
                args = [args[0], stub] + args[2:]
            super().__init__(args, *rest, **kwargs)

    subprocess.Popen = StubPopen


def interrupt_when_ready(ready: str, signals) -> None:
    deadline = time.monotonic() + 60
    while not os.path.exists(ready):
        if time.monotonic() > deadline:
            return
        time.sleep(0.05)
    time.sleep(0.5)
    for name in signals:
        signal.raise_signal(getattr(signal, name))
        time.sleep(1.5)


if CONFIG.get("console"):
    sys.exit(own_console(CONFIG["console"]))
if CONFIG.get("outer_job") is not None:
    enter_outer_job(CONFIG["outer_job"])
if sys.platform == "win32":
    # 清掉继承来的错误模式：跑契约的进程（例如 mutate 的 pd.main）多半已设了 0x8003，会一路传给启动器与孙进程。
    # 清了之后，孙进程读到的 0x8003 只能来自 kit_hub.main 的 quiet_error_mode（TS 一边另有 Bun 自己设的）
    ctypes.windll.kernel32.SetErrorMode(0)
sys.path.insert(0, CONFIG["scripts"])
import kit_hub  # noqa: E402

kit_hub.pd.KERNEL_IMPL_PATH = kit_hub.pd.Path(CONFIG["selector"])
record_handoff(kit_hub, CONFIG.get("stub"))
if CONFIG.get("stub"):
    use_stub(kit_hub, CONFIG["stub"])
if CONFIG.get("interrupt"):
    threading.Thread(target=interrupt_when_ready, args=(CONFIG["interrupt"]["ready"], CONFIG["interrupt"]["signals"]),
                     daemon=True).start()
sys.exit(kit_hub.main(CONFIG["argv"]))
