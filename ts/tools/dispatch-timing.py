"""调度器与 hub 命令的耗时：同一批只读命令，钉成全部 Python 与全部 TS（经真的启动器）各跑若干次，取中位数（迁移计划第 9 节的计时）。

用法：python ts/tools/dispatch-timing.py [--repo 仓库] [--runs 10] [--plan 合同版本] [--task 任务]
内核是本文件所在的仓库；--repo 缺省也是它。选择文件写在临时目录里，不碰提交的那一份。
调度器的命令只读，在 --repo 上跑。hub 的命令（kit_hub.py，第 ⑤j3 片）会写信箱，一律在临时目录里新建的仓库上跑，不碰 --repo 的信箱：
status、status --json、metrics --json，与空信箱时调度循环的一轮（run --max-steps 1 --idle-exit 0 --poll 0，含内核指纹）。
最后记常驻开销：run 跑着的那几秒里的工作集，全 python 时是 hub 进程自己，全 ts 时是 Python 启动器与 TS 进程各自（只记数，不设门槛）。
"""
import argparse
import ctypes
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KERNEL = Path(__file__).resolve().parents[2]
SCRIPTS = KERNEL / "scripts"
PD_PROGRAM = ("import sys; sys.path.insert(0, %r); import pi_dispatch as pd; pd.KERNEL_IMPL_PATH = pd.Path(sys.argv[1]); "
              "sys.exit(pd.main(sys.argv[2:]))" % str(SCRIPTS))
HUB_PROGRAM = ("import sys; sys.path.insert(0, %r); import kit_hub; kit_hub.pd.KERNEL_IMPL_PATH = kit_hub.pd.Path(sys.argv[1]); "
               "sys.exit(kit_hub.main(sys.argv[2:]))" % str(SCRIPTS))


def selectors(directory: Path) -> dict:
    def write(name: str, hub: str) -> Path:
        path = directory / name
        path.write_text(json.dumps({"schema_version": 1, "readonly": "ts", "config": "ts", "dispatcher": "ts", "hub": hub}),
                        encoding="utf-8")
        return path

    return {"python": directory / "absent.json", "ts": write("ts.json", "python"), "hub-ts": write("hub-ts.json", "ts")}


def median_seconds(program: str, selector: Path, repo: Path, argv: list, runs: int) -> tuple:
    times = []
    code = None
    for _ in range(runs):
        start = time.perf_counter()
        done = subprocess.run([sys.executable, "-c", program, str(selector), "--repo", str(repo)] + argv, cwd=str(repo),
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        times.append(time.perf_counter() - start)
        code = done.returncode
    return statistics.median(times), code


def hub_repo(directory: Path, selector: Path) -> Path:
    """临时目录里的 hub 仓库：一个提交，建好信箱。"""
    repo = directory / "hub-repo"
    repo.mkdir()
    for argv in (["init", "-q"], ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "--allow-empty", "-m", "base"]):
        subprocess.run(["git"] + argv, cwd=str(repo), check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, "-c", HUB_PROGRAM, str(selector), "--repo", str(repo), "init"], cwd=str(repo), check=True,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    return repo


def working_set_mb(pid: int) -> float:
    """进程当前的工作集（MB）；拿不到时是 -1。"""

    class Counters(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [(name, ctypes.c_size_t) for name in (
            "peak", "working_set", "peak_paged", "paged", "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = ctypes.c_void_p
    handle = k32.OpenProcess(0x1000 | 0x0010, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ
    if not handle:
        return -1.0
    try:
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        ok = k32.K32GetProcessMemoryInfo(ctypes.c_void_p(handle), ctypes.byref(counters), counters.cb)
        return counters.working_set / 1048576 if ok else -1.0
    finally:
        k32.CloseHandle(ctypes.c_void_p(handle))


def resident(selector: Path, repo: Path) -> tuple:
    """run 跑着的那会儿，起的那个进程与账本里最后一条 runner.started 记的进程各自的工作集（MB）。hub 选 python 时两者是同一个
    进程（Python 的 hub）；选 ts 时前者是 Python 启动器，后者是它转交的 TS 进程（bun）。"""
    ledger = repo / ".agent" / "mailbox" / "ledger" / "events.jsonl"
    before = ledger.read_bytes().count(b"runner.started") if ledger.is_file() else 0
    proc = subprocess.Popen([sys.executable, "-c", HUB_PROGRAM, str(selector), "--repo", str(repo), "run", "--max-steps", "1",
                             "--idle-exit", "5", "--poll", "0.5"], cwd=str(repo), stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 30
        while (ledger.read_bytes().count(b"runner.started") if ledger.is_file() else 0) == before:
            if time.monotonic() > deadline:
                return -1.0, -1.0
            time.sleep(0.1)
        time.sleep(1)
        started = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if '"runner.started"' in line][-1]
        return working_set_mb(proc.pid), working_set_mb(int(started["pid"]))
    finally:
        proc.wait(timeout=60)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=str(KERNEL))
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--plan", default="t023-desktop-ui-writes-b.v1")
    parser.add_argument("--task", default="t023-desktop-ui-writes-b")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    commands = [
        ["validate", args.plan],
        ["metrics"],
        ["wait", args.task, "--timeout", "1"],
        ["sync-adapters", "--check"],
        ["release-check"],
        ["status", "--json"],
        ["config", "show", "--json"],
    ]
    hub_commands = [["status"], ["status", "--json"], ["metrics", "--json"], ["run", "--max-steps", "1", "--idle-exit", "0", "--poll", "0"]]
    with tempfile.TemporaryDirectory(prefix="dispatch-timing-") as directory:
        chosen = selectors(Path(directory))
        for argv in commands:
            py, py_code = median_seconds(PD_PROGRAM, chosen["python"], repo, argv, args.runs)
            ts, ts_code = median_seconds(PD_PROGRAM, chosen["ts"], repo, argv, args.runs)
            print("%-28s python %6.2f s  ts %6.2f s  (+%.2f s)  exit %s/%s" % (" ".join(argv[:2]), py, ts, ts - py, py_code, ts_code))
        hub = hub_repo(Path(directory), chosen["python"])
        for argv in hub_commands:
            py, py_code = median_seconds(HUB_PROGRAM, chosen["python"], hub, argv, args.runs)
            ts, ts_code = median_seconds(HUB_PROGRAM, chosen["hub-ts"], hub, argv, args.runs)
            print("%-28s python %6.2f s  ts %6.2f s  (+%.2f s)  exit %s/%s" % ("hub " + " ".join(argv[:2]), py, ts, ts - py, py_code, ts_code))
        if sys.platform == "win32":
            alone, _same = resident(chosen["python"], hub)
            launcher, child = resident(chosen["hub-ts"], hub)
            print("hub run 常驻（工作集）：全 python 的 hub 进程 %.1f MB；全 ts 时 Python 启动器 %.1f MB 加 TS 进程（bun）%.1f MB，共 %.1f MB"
                  % (alone, launcher, child, launcher + child))
    return 0


if __name__ == "__main__":
    sys.exit(main())
