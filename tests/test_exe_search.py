"""按名字起程序时不查当前目录（第 77 轮，themistally-15 复核 T015 时实测）。

Windows 上 CreateProcess 与 libuv 按名字找程序时，调用方自己的当前目录排在 System32 之前：仓库里放一个 git.exe
或 tasklist.exe，在仓库里跑 pi_dispatch.py 就会执行它。环境里有 NoDefaultCurrentDirectoryInExePath 时不查。hub
一直被 Claude Code 给 shell 设的这个变量碰巧护着；普通终端与桌面应用没有。

做法：pi_dispatch 在导入时就设上这个变量（导入它的 kit_hub、kit_install 跟着受保护），child_env、handoff_env 显式
带上；tasklist、taskkill 改用 System32 下的绝对路径。测试起子进程时显式去掉这个变量，否则在 Claude Code 或 hub
的环境里会空过。
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pi_dispatch as pd  # noqa: E402
import python_kernel  # noqa: E402

pytestmark = pytest.mark.skipif(not pd.IS_WINDOWS, reason="当前目录参与按名字找程序是 Windows 的行为")

VAR = "NoDefaultCurrentDirectoryInExePath"
HOST = socket.gethostname().lower()


def planted(tmp_path: Path) -> Path:
    """一个目录：git.exe、tasklist.exe、taskkill.exe 都是改了名的 hostname.exe（只会打印主机名）。"""
    plant = tmp_path / "plant"
    plant.mkdir()
    hostname = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "HOSTNAME.EXE"
    for name in ("git.exe", "tasklist.exe", "taskkill.exe"):
        shutil.copyfile(str(hostname), str(plant / name))
    return plant


def bare_env() -> dict:
    """去掉了这个变量的环境：测试本身就跑在设了它的进程里（导入 pd 时设上的，Claude Code 的 shell 也设了）。"""
    return {k: v for k, v in os.environ.items() if k.upper() != VAR.upper()}


def run_in(plant: Path, code: str) -> str:
    program = "import sys; sys.path.insert(0, %r)\n%s" % (str(SCRIPTS), code)
    done = subprocess.run([sys.executable, "-c", program], cwd=str(plant), env=bare_env(), stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    return done.stdout.decode("utf-8", "replace")


def test_the_attack_is_real_without_the_guard(tmp_path):
    # 先证明威胁存在：没导入 pd、环境里也没有这个变量时，按名字起 git 执行的是当前目录里的冒牌程序
    out = run_in(planted(tmp_path), "import subprocess; print(subprocess.run(['git'], capture_output=True, text=True).stdout)")
    assert out.strip().lower().startswith(HOST)


def test_importing_the_dispatcher_turns_the_guard_on(tmp_path):
    out = run_in(planted(tmp_path), "import os, subprocess, pi_dispatch\n"
                                    "print(os.environ.get(%r))\n"
                                    "print(subprocess.run(['git', '--version'], capture_output=True, text=True).stdout)" % VAR)
    lines = out.strip().splitlines()
    assert lines[0] == "1"
    assert lines[1].startswith("git version"), out


def test_pid_alive_runs_the_real_tasklist(tmp_path):
    # 冒牌的 tasklist 只打印主机名：pid_alive 会把活着的进程判成死的
    out = run_in(planted(tmp_path), "import os, pi_dispatch as pd; print(pd.pid_alive(os.getpid()))")
    assert out.strip() == "True"


def test_the_absolute_tasklist_path_holds_even_without_the_variable(tmp_path):
    # 第二道防线：导入之后再把变量删掉，pid_alive 照样跑的是 System32 里的 tasklist
    out = run_in(planted(tmp_path), "import os, pi_dispatch as pd\n"
                                    "del os.environ[%r]\n"
                                    "print(pd.pid_alive(os.getpid()))" % VAR)
    assert out.strip() == "True"


def status_in_a_planted_repo(tmp_path: Path, kernel: Path) -> None:
    plant = planted(tmp_path)
    subprocess.run(["git", "init", "-q", str(plant)], check=True, env=bare_env())
    done = subprocess.run([sys.executable, str(kernel), "status", "--json"], cwd=str(plant),
                          env=bare_env(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=120)
    assert done.returncode == 0, done.stderr.decode("utf-8", "replace")
    assert done.stdout.decode("utf-8").strip() == "[]"


def test_status_in_a_repo_with_a_planted_git(tmp_path):
    # 钉成 Python（迁移计划 D5）：没装 TS 依赖的工作树里也要跑
    status_in_a_planted_repo(tmp_path, python_kernel.script(tmp_path / "kernel"))


def test_status_handed_to_ts_in_a_repo_with_a_planted_git(tmp_path):
    # 经启动器转交 TS 时，TS 起 git 也不查当前目录（handoff_env 带上防护）。ts/ 的 harden.test.ts 直接起 main.ts、
    # 不经启动器，所以这一份留在这里；没装依赖时跳过，Python 那一份照常跑
    try:
        pd.ts_launch_command({"command": ["status"]})
    except pd.DispatchError as exc:
        pytest.skip("没装 TS 依赖，经启动器转交 TS 的这一份不跑：%s" % exc)
    kernel = python_kernel.script(tmp_path / "kernel")
    selector = dict({name: "python" for name in pd.KERNEL_IMPL_COMPONENTS}, readonly="ts")
    assert pd.argv_impl(["status", "--json"], selector) == "ts"
    (kernel.parent / "kernel-impl.json").write_text(json.dumps(dict(selector, schema_version=1)), encoding="utf-8")
    status_in_a_planted_repo(tmp_path, kernel)


def test_child_environments_carry_the_guard():
    env, _removed = pd.child_env({"env_remove": [VAR], "env_keep": []})
    assert env.get(VAR) == "1"
    assert pd.handoff_env({"PATH": "x"}).get(VAR) == "1"


def test_system_tools_are_called_by_absolute_path():
    assert Path(pd.SYSTEM_TOOL["tasklist"]).is_file() and Path(pd.SYSTEM_TOOL["tasklist"]).is_absolute()
    assert Path(pd.SYSTEM_TOOL["taskkill"]).is_file() and Path(pd.SYSTEM_TOOL["taskkill"]).is_absolute()
    # 第 78 轮（themistally-15 复核第 77 轮）：管凭据文件权限的 icacls 同样用绝对路径
    from codekit import secrets

    assert Path(secrets.ICACLS).is_file() and Path(secrets.ICACLS).is_absolute()


def test_the_standalone_baseline_tool_hardens_its_entry(tmp_path):
    # 第 78 轮：codekit/baseline.py 有自己的 __main__、按名字起 git、不导入 pi_dispatch，单独运行时要自己设上
    code = ("import os, runpy, sys\n"
            "sys.argv = ['baseline.py', '--help']\n"
            "try:\n"
            "    runpy.run_path(%r, run_name='__main__')\n"
            "except SystemExit:\n"
            "    pass\n"
            "print(os.environ.get(%r))" % (str(SCRIPTS / "codekit" / "baseline.py"), VAR))
    out = run_in(planted(tmp_path), code)
    assert out.strip().splitlines()[-1] == "1"
