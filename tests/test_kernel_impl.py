"""两套实现并存：选择文件与转交给 TS 的启动器（迁移计划第 ② 步、第 5 节；r3 §10 第 64 轮）。

启动器的行为（字节透传、退出码、连带结束、环境）用假入口（Python 脚本）测，不依赖 TS 装没装；Bun 读当前目录、
全局配置与注入变量的几条要真的 Bun，找不到就跳过。启动器一律在独立进程里跑（引导脚本改模块常量再调函数），
句柄继承、Job 与退出码才是真的测到了；生产代码里没有改选择文件路径的环境变量开关。
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import kit_hub as kh  # noqa: E402
import kit_logs  # noqa: E402
import pi_dispatch as pd  # noqa: E402

ALL_PYTHON = {name: "python" for name in pd.KERNEL_IMPL_COMPONENTS}
READONLY_TS = dict(ALL_PYTHON, readonly="ts")


def program(code: str) -> str:
    return "import sys; sys.path.insert(0, %r); import pi_dispatch as pd\n%s" % (str(SCRIPTS), code)


def launcher(code: str, **kwargs) -> "subprocess.CompletedProcess[bytes]":
    """在独立的 Python 进程里跑一段用到 pd 的代码（stdout、stderr 默认收下来）。"""
    kwargs.setdefault("stdout", subprocess.PIPE)
    kwargs.setdefault("stderr", subprocess.PIPE)
    kwargs.setdefault("stdin", subprocess.DEVNULL)
    return subprocess.run([sys.executable, "-c", program(code)], timeout=120, **kwargs)


def main_with(selector: Path, ts_root: Path, argv, cwd: Path, **kwargs) -> "subprocess.CompletedProcess[bytes]":
    """pd.main(argv)，选择文件与 TS 目录指向测试给的位置。"""
    return launcher("pd.KERNEL_IMPL_PATH = pd.Path(%r); pd.KERNEL_TS_ROOT = pd.Path(%r); sys.exit(pd.main(%r))"
                    % (str(selector), str(ts_root), list(argv)), cwd=str(cwd), **kwargs)


def git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    for args in (["init", "-q"], ["config", "user.email", "t@example.invalid"], ["config", "user.name", "t"],
                 ["commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(["git"] + args, cwd=str(path), check=True, stdout=subprocess.DEVNULL)
    return path


def write_selector(path: Path, **values: str) -> Path:
    data = dict({"schema_version": 1}, **dict(ALL_PYTHON, **values))
    path.write_text(json.dumps(data) + "\n", encoding="utf-8")
    return path


def fake_bun(tmp: Path) -> Path:
    bindir = tmp / "bin"
    bindir.mkdir()
    exe = bindir / ("bun.exe" if pd.IS_WINDOWS else "bun")
    exe.write_bytes(b"")
    exe.chmod(0o755)
    return exe


def fake_ts(tmp: Path, bun: Path, entry_text: str = "// 假入口\n") -> Path:
    root = tmp / "ts"
    (root / "packages" / "cli" / "src").mkdir(parents=True)
    (root / pd.TS_ENTRY).write_text(entry_text, encoding="utf-8")
    (root / "packages" / "cli" / "package.json").write_text('{"name": "@themis/cli"}\n', encoding="utf-8")
    (root / "package.json").write_text('{"name": "themis-ts"}\n', encoding="utf-8")
    (root / "bun.lock").write_text("{}\n", encoding="utf-8")
    (root / pd.TS_BUNFIG).write_text("# 空配置\n", encoding="utf-8")
    stamp(root, bun)
    return root


def stamp(root: Path, bun: Path, digest=None) -> None:
    (root / "node_modules").mkdir(exist_ok=True)
    (root / pd.TS_STAMP).write_text(json.dumps({
        "schema_version": 1, "deps_sha256": digest or pd.ts_deps_digest(root), "bun_version": "1.4.2",
        "bun_path": str(bun)}), encoding="utf-8")


# ---------------------------------------------------------------------------
# 选择文件
# ---------------------------------------------------------------------------

def test_a_missing_selector_means_all_python(tmp_path):
    assert pd.read_kernel_impl(tmp_path / "kernel-impl.json") == ALL_PYTHON


def test_a_valid_selector_is_read_as_is(tmp_path):
    assert pd.read_kernel_impl(write_selector(tmp_path / "k.json", readonly="ts")) == READONLY_TS


def test_the_committed_selector_is_valid_and_sits_next_to_the_dispatcher():
    assert pd.KERNEL_IMPL_PATH == SCRIPTS / "kernel-impl.json"
    assert pd.read_kernel_impl()["readonly"] in pd.KERNEL_IMPLS


@pytest.mark.parametrize("text", [
    "", "not json", "﻿" + json.dumps(dict({"schema_version": 1}, **ALL_PYTHON)),
    "[]", json.dumps(ALL_PYTHON),
    json.dumps(dict({"schema_version": 1, "extra": "python"}, **ALL_PYTHON)),
    json.dumps({"schema_version": 1, "readonly": "python", "config": "python", "dispatcher": "python"}),
    json.dumps(dict({"schema_version": 2}, **ALL_PYTHON)),
    json.dumps(dict({"schema_version": True}, **ALL_PYTHON)),
    json.dumps(dict({"schema_version": 1.0}, **ALL_PYTHON)),
    json.dumps(dict({"schema_version": "1"}, **ALL_PYTHON)),
    json.dumps(dict({"schema_version": 1}, **dict(ALL_PYTHON, readonly="TS"))),
    json.dumps(dict({"schema_version": 1}, **dict(ALL_PYTHON, hub=None))),
    json.dumps(dict({"schema_version": 1}, **dict(ALL_PYTHON, config=["ts"]))),
    '{"schema_version": 1, "readonly": "python", "readonly": "ts", "config": "python", "dispatcher": "python", '
    '"hub": "python"}',
])
def test_a_broken_selector_refuses_to_run(tmp_path, text):
    path = tmp_path / "kernel-impl.json"
    path.write_bytes(text.encode("utf-8"))
    with pytest.raises(pd.DispatchError) as caught:
        pd.read_kernel_impl(path)
    assert "拒绝运行" in str(caught.value) and caught.value.code == pd.EXIT_USAGE


def test_an_unreadable_selector_refuses_to_run(tmp_path):
    (tmp_path / "kernel-impl.json").mkdir()
    with pytest.raises(pd.DispatchError, match="拒绝运行"):
        pd.read_kernel_impl(tmp_path / "kernel-impl.json")


def test_main_refuses_every_command_on_a_broken_selector_even_help(tmp_path):
    selector = tmp_path / "kernel-impl.json"
    selector.write_text("{", encoding="utf-8")
    for argv in (["-h"], ["status"], ["doctor"]):
        done = main_with(selector, tmp_path / "no-ts", argv, tmp_path)
        assert done.returncode == pd.EXIT_USAGE and done.stdout == b""
        assert "选择文件不是合法的 JSON" in done.stderr.decode("utf-8")


# ---------------------------------------------------------------------------
# 转交名单与检查顺序
# ---------------------------------------------------------------------------

def test_the_handoff_list_is_exactly_the_six_readonly_commands():
    assert sorted(pd.TS_READONLY_COMMANDS) == sorted([
        ("status",), ("logs", "list"), ("logs", "show"), ("logs", "cat"), ("logs", "search"), ("logs", "usage")])


@pytest.mark.parametrize("argv", [["status"], ["logs", "list"], ["logs", "show", "x"], ["logs", "cat", "x", "p"],
                                  ["logs", "search", "p"], ["logs", "usage"]])
def test_the_handoff_keys_match_argparse(argv):
    # argparse 多了选项而名单没跟上，这里就红：不会悄悄丢掉一个参数
    if argv[0] == "status":
        namespace = vars(pd.build_parser().parse_args(argv))
        skipped = {"command", "func", "assess"}
    else:
        namespace = vars(kit_logs.build_parser().parse_args(argv[1:]))
        skipped = {"command", "func"}
    assert set(pd.TS_READONLY_COMMANDS[tuple(argv[:2] if argv[0] == "logs" else argv[:1])]) == set(namespace) - skipped


def args_of(argv):
    forwarded = pd.forwarded_command(argv)
    return forwarded if forwarded is not None else pd.build_parser().parse_args(argv)


def test_commands_outside_the_list_stay_in_python(tmp_path):
    repo = git_repo(tmp_path / "repo")
    for argv in (["status", "--assess"], ["doctor"], ["config", "show"], ["plugins", "list"], ["logs"],
                 ["metrics"], ["validate", "x.v1"]):
        assert pd.readonly_handoff(args_of(["--repo", str(repo)] + argv)) is None, argv


def test_listed_commands_hand_off_the_parsed_arguments(tmp_path):
    repo = git_repo(tmp_path / "repo")
    assert pd.readonly_handoff(args_of(["--repo", str(repo), "status", "--json"])) == {
        "command": ["status"], "repo": str(repo), "task_id": None, "json": True}
    assert pd.readonly_handoff(args_of(["--repo", str(repo), "logs", "cat", "t.v1", "a.log", "--limit", "7"])) == {
        "command": ["logs", "cat"], "repo": str(repo), "target": "t.v1", "path": "a.log", "cursor": None,
        "limit": 7, "json": False}
    # logs 自己的 --repo 优先，与 kit_logs.main 一样
    other = git_repo(tmp_path / "other")
    assert pd.readonly_handoff(args_of(["--repo", str(repo), "logs", "--repo", str(other), "list"]))["repo"] \
        == str(other)


def test_discovery_errors_are_answered_by_python(tmp_path):
    repo = git_repo(tmp_path / "repo")
    subprocess.run(["git", "worktree", "add", "-q", str(tmp_path / "wt")], cwd=str(repo), check=True)
    plain = tmp_path / "plain"
    plain.mkdir()
    for target in (tmp_path / "wt", plain, tmp_path / "missing"):
        assert pd.readonly_handoff(args_of(["--repo", str(target), "status"])) is None
        assert pd.readonly_handoff(args_of(["--repo", str(target), "logs", "list"])) is None


def test_python_answers_listed_commands_when_discovery_fails_even_without_ts(tmp_path):
    # 选择文件指向 ts、TS 目录根本不存在：worktree 的报错照样是 Python 的原文，碰不到 TS 的检查
    repo = git_repo(tmp_path / "repo")
    subprocess.run(["git", "worktree", "add", "-q", str(tmp_path / "wt")], cwd=str(repo), check=True)
    selector = write_selector(tmp_path / "k.json", readonly="ts")
    done = main_with(selector, tmp_path / "no-ts", ["status"], tmp_path / "wt")
    assert done.returncode == pd.EXIT_USAGE and "请在主工作区运行本工具" in done.stderr.decode("utf-8")


def test_argv_impl_uses_the_same_list():
    assert pd.argv_impl(["status", "--json"], ALL_PYTHON) == "python"
    for argv in (["status"], ["status", "--json", "t"], ["--repo", "x", "status"], ["--repo=x", "logs", "search", "p"],
                 ["logs", "usage", "--task", "t"]):
        assert pd.argv_impl(argv, READONLY_TS) == "ts", argv
    for argv in (["status", "--assess"], ["status", "-h"], ["logs", "--help"], ["logs"], ["prepare", "t.v1"],
                 ["run", "x"], ["config", "show"]):
        assert pd.argv_impl(argv, READONLY_TS) == "python", argv


# ---------------------------------------------------------------------------
# 转交之前的检查
# ---------------------------------------------------------------------------

def test_the_launch_command_carries_the_pyargs_and_shuts_out_the_working_directory(tmp_path):
    bun = fake_bun(tmp_path)
    root = fake_ts(tmp_path, bun)
    pyargs = {"command": ["logs", "search"], "repo": None, "pattern": "\udcff 中", "task": None, "max": 2 ** 70,
              "json": True}
    cmd = pd.ts_launch_command(pyargs, root, {"PATH": str(bun.parent)})
    assert cmd[:4] == [str(bun), "--no-env-file", "--config=%s" % (root / "bunfig.toml"), str(root / pd.TS_ENTRY)]
    assert cmd[4] == "--pyargs-b64" and json.loads(base64.b64decode(cmd[5])) == pyargs


def test_a_selector_pointing_at_ts_without_a_ts_entry_is_an_error(tmp_path):
    with pytest.raises(pd.DispatchError, match="选择文件指向 ts，但找不到 TS 入口"):
        pd.ts_launch_command({"command": ["status"]}, tmp_path / "ts", {"PATH": ""})


def test_a_missing_stamp_says_how_to_install(tmp_path):
    bun = fake_bun(tmp_path)
    root = fake_ts(tmp_path, bun)
    (root / pd.TS_STAMP).unlink()
    with pytest.raises(pd.DispatchError) as caught:
        pd.ts_launch_command({"command": ["status"]}, root, {"PATH": str(bun.parent)})
    assert str(caught.value) == "TS 实现没装好：在 ts/ 下运行 bun install --frozen-lockfile"


@pytest.mark.parametrize("change", ["bun.lock", "package.json", "packages/cli/package.json", "packages/new/package.json"])
def test_a_stale_stamp_says_the_dependencies_do_not_match(tmp_path, change):
    bun = fake_bun(tmp_path)
    root = fake_ts(tmp_path, bun)
    (root / change).parent.mkdir(parents=True, exist_ok=True)
    (root / change).write_text('{"changed": true}\n', encoding="utf-8")
    with pytest.raises(pd.DispatchError) as caught:
        pd.ts_launch_command({"command": ["status"]}, root, {"PATH": str(bun.parent)})
    assert str(caught.value) == "TS 依赖与 bun.lock 不一致：在 ts/ 下运行 bun install --frozen-lockfile"


def test_no_bun_on_path_is_an_error_not_a_fallback(tmp_path):
    bun = fake_bun(tmp_path)
    root = fake_ts(tmp_path, bun)
    with pytest.raises(pd.DispatchError, match="找不到 Bun"):
        pd.ts_launch_command({"command": ["status"]}, root, {"PATH": str(tmp_path / "empty")})


def test_a_different_bun_than_the_one_that_installed_is_an_error(tmp_path):
    bun = fake_bun(tmp_path)
    root = fake_ts(tmp_path, bun)
    other = tmp_path / "other"
    other.mkdir()
    (other / bun.name).write_bytes(b"")
    (other / bun.name).chmod(0o755)
    with pytest.raises(pd.DispatchError, match="当前找到的 bun.exe 与安装依赖时用的不是同一个"):
        pd.ts_launch_command({"command": ["status"]}, root, {"PATH": os.pathsep.join([str(other), str(bun.parent)])})


def test_find_bun_reads_only_absolute_path_entries(tmp_path, monkeypatch):
    bun = fake_bun(tmp_path)
    assert pd.find_bun({"PATH": str(bun.parent)}) == bun
    assert pd.find_bun({"PATH": ""}) is None
    monkeypatch.chdir(tmp_path)  # 当前目录里的 bin/bun 不能经相对路径顶替
    assert pd.find_bun({"PATH": "bin"}) is None
    assert pd.find_bun({"PATH": os.pathsep.join(["", "bin", str(bun.parent)])}) == bun


@pytest.mark.skipif(not pd.IS_WINDOWS, reason="npm 的 bun.cmd 垫片只在 Windows 上")
def test_find_bun_follows_the_npm_shim_to_bun_exe(tmp_path):
    npm = tmp_path / "npm"
    exe = npm / "node_modules" / "bun" / "bin" / "bun.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    (npm / "bun.cmd").write_text("@echo off\n", encoding="utf-8")
    assert pd.find_bun({"Path": str(npm)}) == exe  # Windows 的变量名不分大小写
    exe.unlink()
    assert pd.find_bun({"PATH": str(npm)}) is None


def test_the_hub_filtered_environment_still_finds_bun():
    found = pd.find_bun()
    if found is None:
        pytest.skip("本机 PATH 上没有 Bun")
    assert pd.find_bun(kh.kernel_env()) == found


def test_python_and_js_agree_on_the_dependency_digest(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("没有 node")
    script = SCRIPTS.parent / "ts" / "tools" / "stamp-install.mjs"
    root = tmp_path / "ts"
    for name in ("b", "a", "Z", "a-b", "a.b"):
        (root / "packages" / name).mkdir(parents=True)
        (root / "packages" / name / "package.json").write_text('{"name": "%s"}\n' % name, encoding="utf-8")
    (root / "packages" / "no-manifest").mkdir()
    (root / "packages" / "loose.json").write_text("{}", encoding="utf-8")
    (root / "package.json").write_bytes(b'{"name": "x"}\r\n')
    for with_lock in (False, True):
        if with_lock:
            (root / "bun.lock").write_text("{\n  \"lockfileVersion\": 1\n}\n", encoding="utf-8")
        done = subprocess.run([node, str(script), "--digest", str(root)], stdout=subprocess.PIPE, check=True)
        assert done.stdout.decode("ascii").strip() == pd.ts_deps_digest(root)


def test_the_committed_ts_workspace_has_the_pieces_the_launcher_needs():
    root = SCRIPTS.parent / "ts"
    assert (root / pd.TS_ENTRY).is_file() and (root / pd.TS_BUNFIG).is_file()
    assert json.loads((root / "package.json").read_text(encoding="utf-8"))["scripts"]["postinstall"] \
        == "bun tools/stamp-install.mjs"
    assert pd.KERNEL_TS_ROOT == root


# ---------------------------------------------------------------------------
# 启动器（假入口）
# ---------------------------------------------------------------------------

CHILD_ECHO = r"""
import sys
data = sys.stdin.buffer.read()
sys.stdout.buffer.write(b"out\r\nline\n\xff\xfe" + data)
sys.stderr.buffer.write(b"err\x00\n")
sys.exit(7)
"""


def test_bytes_and_exit_code_pass_through_untouched(tmp_path):
    child = tmp_path / "child.py"
    child.write_text(CHILD_ECHO, encoding="utf-8")
    done = launcher("sys.exit(pd.run_handoff([sys.executable, %r]))" % str(child), input=b"in\x00\xe4\r\n",
                    stdin=None)
    assert done.returncode == 7
    assert done.stdout == b"out\r\nline\n\xff\xfe" + b"in\x00\xe4\r\n"
    assert done.stderr == b"err\x00\n"


@pytest.mark.skipif(not pd.IS_WINDOWS, reason="NTSTATUS 退出码只在 Windows 上")
def test_large_windows_exit_codes_pass_through(tmp_path):
    child = tmp_path / "child.py"
    child.write_text("import os\nos._exit(-1073741819)\n", encoding="utf-8")  # 0xC0000005
    done = launcher("sys.exit(pd.run_handoff([sys.executable, %r]))" % str(child))
    assert done.returncode == 0xC0000005 and done.stdout == b"" and done.stderr == b""


@pytest.mark.skipif(not (pd.IS_WINDOWS or sys.platform.startswith("linux")),
                    reason="macOS 没有父进程死、子进程跟着死的机制（未实机验证）")
def test_killing_the_launcher_ends_the_ts_child(tmp_path):
    child = tmp_path / "child.py"
    child.write_text("import os, time\nprint(os.getpid(), flush=True)\ntime.sleep(120)\n", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-c", program("sys.exit(pd.run_handoff([sys.executable, %r]))"
                                                           % str(child))],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
    try:
        pid = int(proc.stdout.readline())
        assert pd.pid_alive(pid) is True
        proc.kill()  # run_pd 超时也是这样只杀直接子进程
        proc.wait(timeout=30)
        deadline = time.monotonic() + 30
        while pd.pid_alive(pid) and time.monotonic() < deadline:
            time.sleep(0.2)
        assert pd.pid_alive(pid) is False
    finally:
        proc.kill()
        proc.stdout.close()


CHILD_ENV = "import json, os, sys\nsys.stdout.write(json.dumps(dict(os.environ)))\n"


def child_env(tmp_path: Path, env) -> dict:
    child = tmp_path / "env.py"
    child.write_text(CHILD_ENV, encoding="utf-8")
    done = launcher("sys.exit(pd.run_handoff([sys.executable, %r]))" % str(child), env=env)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def norm_env(env) -> dict:
    return {(name.upper() if pd.IS_WINDOWS else name): value for name, value in env.items()}


def test_the_environment_is_what_python_sees(tmp_path):
    env = dict(os.environ, THEMIS_HANDOFF_MARK="中 x")
    seen = norm_env(child_env(tmp_path, env))
    assert seen == norm_env(pd.handoff_env(env)) and seen["THEMIS_HANDOFF_MARK"] == "中 x"


@pytest.mark.parametrize("name", pd.TS_RUNTIME_ENV_DROP)
def test_runtime_injection_variables_are_dropped(tmp_path, name):
    env = dict(os.environ, THEMIS_HANDOFF_MARK="kept", **{name: "--inject"})
    seen = norm_env(child_env(tmp_path, env))
    assert (name.upper() if pd.IS_WINDOWS else name) not in seen and seen["THEMIS_HANDOFF_MARK"] == "kept"


# ---------------------------------------------------------------------------
# 真的 Bun：当前目录、全局配置与注入变量都进不了 TS 进程
# ---------------------------------------------------------------------------

PROBE = """let mod = "no";
try { mod = (await import("zzinjected")).default; } catch {}
console.log(JSON.stringify({ foo: process.env.FOO ?? null, inj: globalThis["__inj"] ?? null, mod }));
"""
CLEAN = {"foo": None, "inj": None, "mod": "no"}


def injection_case(tmp_path: Path, case: str):
    """返回（当前目录, 启动器的环境）：按 case 布下一种注入。"""
    cwd = tmp_path / "cwd"
    inj = tmp_path / "inj"
    cwd.mkdir()
    inj.mkdir()
    (inj / "pre.mjs").write_text('globalThis["__inj"] = "%s";\n' % case, encoding="utf-8")
    (inj / "pre.cjs").write_text('globalThis["__inj"] = "%s";\n' % case, encoding="utf-8")
    (inj / "zzinjected.js").write_text('module.exports = "injected";\n', encoding="utf-8")
    preload = 'preload = ["%s"]\n' % (inj / "pre.mjs").as_posix()
    env = dict(os.environ)
    if case == "dotenv":
        (cwd / ".env").write_text("FOO=from-dotenv\n", encoding="utf-8")
    elif case == "bunfig":
        (cwd / "bunfig.toml").write_text(preload, encoding="utf-8")
    elif case == "global":
        home = tmp_path / "home"
        (home / ".config").mkdir(parents=True)
        for path in (home / ".bunfig.toml", home / ".config" / ".bunfig.toml"):
            path.write_text(preload, encoding="utf-8")
        env.update(HOME=str(home), USERPROFILE=str(home), XDG_CONFIG_HOME=str(home / ".config"))
    elif case == "BUN_OPTIONS":
        env["BUN_OPTIONS"] = "--preload %s" % (inj / "pre.mjs").as_posix()  # Bun 按反斜杠转义解析这个变量
    elif case == "NODE_PATH":
        env["NODE_PATH"] = str(inj)
    elif case == "NODE_OPTIONS":
        env["NODE_OPTIONS"] = "--require %s" % (inj / "pre.cjs").as_posix()
    return cwd, env


@pytest.mark.parametrize("case", ["dotenv", "bunfig", "global", "BUN_OPTIONS", "NODE_PATH", "NODE_OPTIONS"])
def test_bun_reads_nothing_from_the_working_directory_or_injection_variables(tmp_path, case):
    bun = pd.find_bun()
    if bun is None:
        pytest.skip("本机 PATH 上没有 Bun")
    root = fake_ts(tmp_path, bun, PROBE)
    cwd, env = injection_case(tmp_path, case)
    done = launcher("sys.exit(pd.run_handoff(pd.ts_launch_command({'command': ['status']}, pd.Path(%r))))"
                    % str(root), cwd=str(cwd), env=env)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == CLEAN
    if case in ("dotenv", "bunfig", "BUN_OPTIONS", "NODE_PATH"):
        # 对照：不带这些防护时注入确实生效，上面的断言才有意义
        plain = subprocess.run([str(bun), str(root / pd.TS_ENTRY)], cwd=str(cwd), env=env, stdout=subprocess.PIPE,
                               stdin=subprocess.DEVNULL, timeout=60)
        assert json.loads(plain.stdout) != CLEAN


ECHO_PYARGS = """const at = process.argv.indexOf("--pyargs-b64");
process.stdout.write("FROM-TS " + Buffer.from(process.argv[at + 1], "base64").toString("utf8"));
process.exitCode = 3;
"""


def test_main_really_hands_listed_commands_to_ts(tmp_path):
    # 契约测试比的是“输出与 Python 相同”，这里直接看到是 TS 答的、拿到的是启动器从 argparse 生成的参数
    bun = pd.find_bun()
    if bun is None:
        pytest.skip("本机 PATH 上没有 Bun")
    root = fake_ts(tmp_path, bun, ECHO_PYARGS)
    repo = git_repo(tmp_path / "repo")
    selector = write_selector(tmp_path / "ts.json", readonly="ts")
    done = main_with(selector, root, ["logs", "search", "fail(?:ed)?", "--max", "3"], repo)
    assert done.returncode == 3 and done.stderr == b""
    assert done.stdout.startswith(b"FROM-TS ")
    assert json.loads(done.stdout[len(b"FROM-TS "):]) == {
        "command": ["logs", "search"], "repo": None, "pattern": "fail(?:ed)?", "task": None, "max": 3, "json": False}


# ---------------------------------------------------------------------------
# 回退与名单外的命令：没有 TS 也照样由 Python 回答，输出逐字节相同
# ---------------------------------------------------------------------------

def test_rolling_back_to_python_is_byte_identical(tmp_path):
    repo = git_repo(tmp_path / "repo")
    missing = tmp_path / "no-selector.json"
    python = write_selector(tmp_path / "python.json")
    for argv in (["status"], ["status", "--json"], ["logs", "list", "--json"], ["logs", "show", "nope"]):
        before = main_with(missing, tmp_path / "no-ts", argv, repo)
        after = main_with(python, tmp_path / "no-ts", argv, repo)
        assert (after.returncode, after.stdout, after.stderr) == (before.returncode, before.stdout, before.stderr)
        # 两边都得是 Python 正常答出来的：都去转交 TS 的话，两边会同样报“找不到 TS 入口”，比较照样相等
        assert "TS" not in after.stderr.decode("utf-8")
        if argv != ["logs", "show", "nope"]:
            assert after.returncode == 0, after.stderr


def test_commands_outside_the_list_never_touch_ts(tmp_path):
    # TS 目录不存在：要是转交了就会报“找不到 TS 入口”，输出与没有选择文件时逐字节相同才说明是 Python 答的
    repo = git_repo(tmp_path / "repo")
    missing = tmp_path / "no-selector.json"
    ts = write_selector(tmp_path / "ts.json", readonly="ts")
    for argv in (["status", "--assess"], ["logs"], ["logs", "--help"], ["status", "-h"], ["plugins", "list"]):
        before = main_with(missing, tmp_path / "no-ts", argv, repo)
        after = main_with(ts, tmp_path / "no-ts", argv, repo)
        assert (after.returncode, after.stdout, after.stderr) == (before.returncode, before.stdout, before.stderr), argv


def test_a_listed_command_without_ts_reports_the_missing_entry(tmp_path):
    repo = git_repo(tmp_path / "repo")
    done = main_with(write_selector(tmp_path / "ts.json", readonly="ts"), tmp_path / "no-ts", ["status"], repo)
    assert done.returncode == pd.EXIT_USAGE and done.stdout == b""
    assert "选择文件指向 ts，但找不到 TS 入口" in done.stderr.decode("utf-8")


# ---------------------------------------------------------------------------
# 执行器的禁区
# ---------------------------------------------------------------------------

def test_scripts_kernel_impl_is_always_protected():
    protected = pd.compile_patterns(list(pd.PROTECTED_PATTERNS), ignore_case=True)
    assert pd.matches(protected, "scripts/kernel-impl.json") and pd.matches(protected, "Scripts/Kernel-Impl.JSON")
    assert "scripts/kernel-impl.json" not in pd.KIT_LOADED_FILES  # 不随 kit 安装


def test_ts_is_protected_only_in_the_kernel_repo_while_something_runs_on_ts(tmp_path):
    kernel = pd.KERNEL_TS_ROOT.parent
    assert pd.kernel_protected_paths(kernel, READONLY_TS) == list(pd.KERNEL_TS_PROTECTED)
    assert pd.kernel_protected_paths(kernel, ALL_PYTHON) == []  # 回退之后 TS 不在生产路径上
    assert pd.kernel_protected_paths(tmp_path, READONLY_TS) == []  # 目标仓库自己的 ts/ 不受影响
    if pd.IS_WINDOWS:
        assert pd.kernel_protected_paths(Path(str(kernel).upper()), READONLY_TS) == list(pd.KERNEL_TS_PROTECTED)


# 第 69 轮：内核的 TS 禁区从整个 ts/ 收窄到内核实际用到的部分，桌面端本机服务的新包能派给执行器
KERNEL_TS_FILES = ("ts/package.json", "ts/bun.lock", "ts/bunfig.toml", "ts/tsconfig.json", "ts/vitest.config.ts",
                   "ts/tools/stamp-install.mjs", "ts/mutations/readonly-c1.json", "ts/packages/base/src/secrets.ts",
                   "ts/packages/cli/src/main.ts", "ts/packages/config/package.json",
                   "ts/packages/contracts/test/harness.ts", "ts/packages/dispatcher/src/status.ts",
                   "ts/packages/hub/package.json", "TS/Packages/Base/src/x.ts")
OPEN_TS_FILES = ("ts/packages/ui/src/server.ts", "ts/packages/ui/test/server.test.ts", "ts/packages/uix/a.ts",
                 "ts/README.md", "desktop/web/src/api.ts")


def test_the_kernel_ts_protection_covers_the_kernel_and_leaves_new_packages_open():
    protected = pd.compile_patterns(list(pd.PROTECTED_PATTERNS) + list(pd.KERNEL_TS_PROTECTED), ignore_case=True)
    assert [path for path in KERNEL_TS_FILES if not pd.matches(protected, path)] == []
    assert [path for path in OPEN_TS_FILES if pd.matches(protected, path)] == []
    # 现有的内核包都在名单里：新加一个内核包而忘了列进来，这里就红
    on_disk = sorted(d.name for d in (pd.KERNEL_TS_ROOT / "packages").iterdir() if (d / "package.json").is_file())
    assert set(on_disk) - {"ui"} <= {p.split("/")[2] for p in pd.KERNEL_TS_PROTECTED if p.startswith("ts/packages/")}


def contract_for(allowed):
    import test_dispatch as td  # 合同的样板与 Markdown 生成在端到端测试里

    data = td.contract("0" * 40, 1, scope={"allowed_modified_files": list(allowed), "allowed_new_files": [],
                                            "allowed_deleted_files": [], "forbidden_paths": [],
                                            "dependency_changes": "forbidden"})
    return td.build_md(data), data


def test_contracts_may_allow_new_ts_packages_but_not_kernel_ones():
    extra = pd.kernel_protected_paths(pd.KERNEL_TS_ROOT.parent, READONLY_TS)
    for allowed, ok in ((["ts/packages/ui/**"], True), (["ts/packages/ui/src/server.ts"], True),
                        (["ts/packages/base/**"], False), (["ts/packages/dispatcher/src/status.ts"], False),
                        (["ts/bun.lock"], False), (["ts/tsconfig.json"], False), (["ts/mutations/a.json"], False)):
        md, data = contract_for(allowed)
        _contract, errors, _warnings = pd.validate_contract(md, data, "normalize-query.v1", extra)
        assert (not any("受保护路径" in e for e in errors)) is ok, (allowed, errors)
        change = {"path": allowed[0].replace("**", "src/a.ts"), "status": "M", "old_mode": "100644",
                  "new_mode": "100644"}
        scope = pd.evaluate_scope([change], pd.normalize_contract(data), "0" * 40, "0" * 40, extra)
        kinds = [v["kind"] for v in scope["violations"]]
        assert ("protected_path" not in kinds) is ok, (allowed, scope["violations"])


@pytest.mark.skipif(not pd.IS_WINDOWS, reason="8.3 短名与 junction 只在 Windows 上")
def test_same_dir_sees_through_short_names_and_junctions(tmp_path):
    import ctypes
    import _winapi

    target = tmp_path / "a-long-directory-name"
    target.mkdir()
    buffer = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetShortPathNameW(str(target), buffer, 1024) and buffer.value != str(target):
        assert pd.same_dir(Path(buffer.value), target)
    link = tmp_path / "junction"
    _winapi.CreateJunction(str(target), str(link))
    try:
        assert pd.same_dir(link, target) and not pd.same_dir(link, tmp_path)
    finally:
        os.rmdir(str(link))  # 只删 junction 本身


def test_an_attempt_keeps_the_protected_set_it_was_prepared_with():
    assert pd.attempt_protected_paths({}, {"kernel_protected": ["ts/**"]}) == ["ts/**"]
    assert pd.attempt_protected_paths({"extra_protected_paths": ["spec.md"]}, {}) == ["spec.md"]  # 更早的 attempt
