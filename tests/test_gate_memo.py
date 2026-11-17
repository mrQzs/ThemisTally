"""第 186 轮：conftest 的 memo_gate_runs 让全量回归里几十份门禁的 `npm ci` 与整套 `npm test` 在一个会话里只真跑一次。"""

import os
import sys
import types

import conftest


def fake_run(calls, results=None):
    def run_capture(argv, cwd, timeout, env=None):
        calls.append(list(argv[1:]))
        return (results or {}).get(tuple(argv[1:]), (0, False, "ok %d" % len(calls), 3.0))
    return run_capture


def web(tmp_path):
    root = tmp_path / "web"
    (root / "src").mkdir(parents=True)
    (root / "src" / "a.ts").write_text("export const a = 1;\n", encoding="utf-8")
    (root / "package.json").write_text("{}\n", encoding="utf-8")
    (root / "package-lock.json").write_text("{}\n", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / ".package-lock.json").write_text("{}\n", encoding="utf-8")
    return root


def test_the_whole_suite_runs_once_per_tree(tmp_path, monkeypatch):
    monkeypatch.setattr(conftest, "_GATE_MEMO", {})
    root, calls = web(tmp_path), []
    run = conftest._memoized(fake_run(calls))
    env = {"CI": "true"}
    first = run(["npm", "test"], root, 600, env)
    assert run(["C:/nodejs/npm.CMD", "test"], root, 600, env) == first and calls == [["test"]]
    # 门禁的环境是 os.environ 的副本，带着 pytest 每条用例都改写的 PYTEST_CURRENT_TEST：不算环境不同
    assert run(["npm", "test"], root, 600, dict(env, PYTEST_CURRENT_TEST="tests/test_gate_t048_baseline.py::t (setup)")) == first
    assert calls == [["test"]]
    # 探针带着文件名：照旧真跑；被 git 忽略的探针目录里有文件也算树变了
    run(["npm", "test", "--", "gate-probe/p.test.tsx"], root, 600, env)
    (root / "gate-probe").mkdir()
    (root / "gate-probe" / "p.test.tsx").write_text("x\n", encoding="utf-8")
    run(["npm", "test"], root, 600, env)
    assert calls == [["test"], ["test", "--", "gate-probe/p.test.tsx"], ["test"]]
    (root / "gate-probe" / "p.test.tsx").unlink()
    (root / "gate-probe").rmdir()
    # 树回到第一遍的样子：照第一遍；时限短于上一遍的用时、环境不同、产物目录变了都照旧真跑（dist 不算）
    (root / "dist").mkdir()
    (root / "dist" / "index.html").write_text("<p>\n", encoding="utf-8")
    assert run(["npm", "test"], root, 600, env) == first
    run(["npm", "test"], root, 2, env)
    run(["npm", "test"], root, 600, {"CI": "true", "TZ": "UTC"})
    assert len(calls) == 5
    (root / "src" / "a.ts").write_text("export const a = 2;\n", encoding="utf-8")
    run(["npm", "test"], root, 600, env)
    assert len(calls) == 6


def test_a_reinstall_is_skipped_only_while_the_install_is_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(conftest, "_GATE_MEMO", {})
    root, calls = web(tmp_path), []
    run = conftest._memoized(fake_run(calls))
    run(["npm", "ci"], root, 900)
    run(["npm", "ci"], root, 900)
    assert calls == [["ci"]]
    stamp = root / "node_modules" / ".package-lock.json"
    stat = stamp.stat()
    os.utime(stamp, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000))  # 别人重装过
    run(["npm", "ci"], root, 900)
    (root / "package-lock.json").write_text('{"v": 2}\n', encoding="utf-8")
    run(["npm", "ci"], root, 900)
    assert len(calls) == 3
    # 失败、超时不记；npm run build 这类照旧每次真跑
    failing, timed_out = [], []
    conftest._GATE_MEMO.clear()
    bad = conftest._memoized(fake_run(failing, {("ci",): (1, False, "E", 9.0)}))
    bad(["npm", "ci"], root, 900)
    bad(["npm", "ci"], root, 900)
    slow = conftest._memoized(fake_run(timed_out, {("test",): (None, True, "", 600.0)}))
    slow(["npm", "test"], root, 600, None)
    slow(["npm", "test"], root, 600, None)
    build = conftest._memoized(fake_run(calls))
    build(["npm", "run", "build"], root, 600, None)
    build(["npm", "run", "build"], root, 600, None)
    assert len(failing) == 2 and len(timed_out) == 2 and calls[-2:] == [["run", "build"], ["run", "build"]]


def test_the_log_switch_records_each_decision(tmp_path, monkeypatch):
    monkeypatch.setattr(conftest, "_GATE_MEMO", {})
    log = tmp_path / "memo.log"
    monkeypatch.setenv("TT_GATE_MEMO_LOG", str(log))
    root, calls = web(tmp_path), []
    run = conftest._memoized(fake_run(calls))
    run(["npm", "test"], root, 600, {"CI": "true"})
    run(["npm", "test"], root, 600, {"CI": "true"})
    run(["npm", "ci"], root, 900)
    lines = log.read_text(encoding="utf-8").splitlines()
    assert [line.split()[:3] for line in lines] == [["miss", "test", "timeout=600"], ["hit", "test", "timeout=600"],
                                                     ["miss", "ci", "timeout=900"]]


def test_only_gate_modules_with_the_env_signature_are_wrapped(tmp_path, monkeypatch):
    def four(argv, cwd, timeout, env=None):
        return (0, False, "", 1.0)

    def three(argv, cwd, timeout):
        return (0, False, "", 1.0)

    made = {}
    for name, function in (("test_gate_t901_baseline", four), ("test_gate_t902_baseline", three), ("test_other", four)):
        module = types.ModuleType(name)
        module.__file__ = str(tmp_path / "tests" / (name + ".py"))
        module.run_capture = function
        monkeypatch.setitem(sys.modules, "memo_probe_" + name, module)
        made[name] = module
    assert conftest.memo_gate_runs() >= 1
    assert made["test_gate_t901_baseline"].run_capture.__wrapped__ is four
    assert made["test_gate_t902_baseline"].run_capture is three and made["test_other"].run_capture is four
    conftest.memo_gate_runs()
    assert made["test_gate_t901_baseline"].run_capture.__wrapped__ is four  # 不重复包
