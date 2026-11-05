"""ts/tools/hub-alive.py（迁移计划第 ⑤ 步 E2：翻选择文件之前机械地查 hub 停没停）。临时信箱里摆各处记 pid 的文件：本进程（活的 python.exe）、
刚结束的子进程（死的）、一个活着但不是 hub 的进程（ping.exe），以及读不出 pid 的记录。只在 Windows 上跑（判活要 Win32）。"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parent.parent / "ts" / "tools" / "hub-alive.py"
WINDOWS_ONLY = pytest.mark.skipif(sys.platform != "win32", reason="判活要 Win32 的进程查询")


def load_tool():
    spec = importlib.util.spec_from_file_location("hub_alive", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def put(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def dead_pid() -> int:
    """已经退出、句柄也放掉了的进程：OpenProcess 打不开。"""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=30)
    return proc.pid


def exited_process() -> "subprocess.Popen[bytes]":
    """已经退出、句柄还拿着的进程（调用方留着这个对象）：进程对象还在，OpenProcess 打得开，判活要看退出码。
    supervisor 拿着退出了的主任务 runner 的句柄时就是这样。"""
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait(timeout=30)
    return proc


def bun_executable():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import pi_dispatch

    return pi_dispatch.find_bun()


#: pid 4 是 System：打得开，取不到映像文件名，走“拿不到进程信息”那条路（按活的报）
SYSTEM_PID = 4


@WINDOWS_ONLY
def test_live_hub_processes_and_unreadable_records_are_reported(tmp_path, capsys):
    # 四种来源各有一个活的 hub 进程（python.exe 是本进程；bun.exe 是切换之后 hub 进程的映像），去掉哪一种都会少报
    bun = bun_executable()
    if bun is None:
        pytest.skip("PATH 上找不到 Bun")
    box = tmp_path / ".agent" / "mailbox"
    ping = subprocess.Popen(["ping", "-n", "60", "127.0.0.1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    sleeper = subprocess.Popen([str(bun), "-e", "setTimeout(() => {}, 60000)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        put(box, ".runner/owner.json", json.dumps({"pid": os.getpid(), "token": "t", "at": "x"}))
        put(box, ".runners/T001/owner.json", json.dumps({"pid": sleeper.pid}))
        put(box, "ledger/exec-active/T002.json", json.dumps({"pid": os.getpid(), "task": "T002"}))
        put(box, ".pause/T003", json.dumps({"pid": sleeper.pid, "at": "x"}))
        put(box, ".lock/owner.json", json.dumps({"pid": SYSTEM_PID}))
        put(box, ".land/owner.json", "{坏")
        put(box, ".runners/T008/owner.json", json.dumps({"pid": 0}))  # 不是有效的 pid：照读不出报，不拿去查进程
        put(box, ".runners/T009/owner.json", json.dumps({"pid": -3}))
        put(box, ".sweep/owner.json", json.dumps({"pid": ping.pid}))
        put(box, ".owner-sweep/owner.json", json.dumps({"pid": dead_pid()}))
        code = load_tool().main(["--repo", str(tmp_path)])
        out = capsys.readouterr().out.splitlines()
    finally:
        for proc in (ping, sleeper):
            proc.kill()
            proc.wait(timeout=30)
    image = Path(sys.executable).name.lower()
    assert code == 1
    # 按种类列：以“.”开头的锁目录、.runners、exec-active、.pause，各类里按路径排；ping 与死的 pid 不报
    assert out == [
        ".land/owner.json：读不出 pid",
        ".lock/owner.json：pid %d，拿不到进程信息" % SYSTEM_PID,
        ".runner/owner.json：pid %d，%s" % (os.getpid(), image),
        ".runners/T001/owner.json：pid %d，bun.exe" % sleeper.pid,
        ".runners/T008/owner.json：读不出 pid",
        ".runners/T009/owner.json：读不出 pid",
        "ledger/exec-active/T002.json：pid %d，%s" % (os.getpid(), image),
        ".pause/T003：pid %d，bun.exe" % sleeper.pid,
        "有活的 hub 进程：8 处",
    ]


@WINDOWS_ONLY
def test_dead_pids_and_other_programs_do_not_count(tmp_path, capsys):
    box = tmp_path / ".agent" / "mailbox"
    ping = subprocess.Popen(["ping", "-n", "60", "127.0.0.1"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    exited = exited_process()
    try:
        put(box, ".runner/owner.json", json.dumps({"pid": dead_pid()}))
        put(box, ".runners/T001/owner.json", json.dumps({"pid": exited.pid}))
        put(box, ".owner-sweep/owner.json", json.dumps({"pid": ping.pid}))
        code = load_tool().main(["--repo", str(tmp_path)])
        out = capsys.readouterr().out.splitlines()
    finally:
        ping.kill()
        ping.wait(timeout=30)
    assert (code, out) == (0, ["没有活的 hub 进程"])


@WINDOWS_ONLY
def test_an_empty_or_missing_mailbox_has_no_hub(tmp_path, capsys):
    assert load_tool().main(["--repo", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines() == ["没有活的 hub 进程"]
