"""子进程里的 Python 走 UTF-8 模式（第 199 轮，候选 #73）。

区域编码是 cp1252 的机器上，pytest 的输出里有一个字写不出来，就把整段（断言说明、docstring，连换行一起）转成 \\uXXXX
（_pytest/_io/terminalwriter.py 遇到 UnicodeEncodeError 的退路）：调度器的检查日志、执行端与门禁工人读到的中文断言全是
转义串（11-18 T054 attempt-001 的 G01.log；那之前 32 份检查日志共三千多处）。调度器的 child_env 补上 PYTHONUTF8=1，
内核的 worker_env、kernel_pytest_env 建在它上面，跟着带上；外面显式设了就照外面的。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import kit_hub as kh  # noqa: E402
import pi_dispatch as pd  # noqa: E402

FAILING = 'def test_demo():\n    assert "门禁" == "合同", "中文断言说明：两边不一样"\n'


def test_child_env_turns_on_utf8_mode_unless_set_outside(monkeypatch):
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    env, _removed = pd.child_env({})
    assert env["PYTHONUTF8"] == "1"
    assert kh.worker_env()["PYTHONUTF8"] == "1"
    assert kh.kernel_pytest_env()["PYTHONUTF8"] == "1"
    monkeypatch.setenv("PYTHONUTF8", "0")
    env, _removed = pd.child_env({})
    assert env["PYTHONUTF8"] == "0"


def test_a_failing_chinese_assertion_reads_as_chinese_in_the_check_log(tmp_path, monkeypatch):
    # 照调度器跑检查的写法：子进程的输出原样写进日志文件（字节），再按 UTF-8 读
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    (tmp_path / "test_demo.py").write_text(FAILING, encoding="utf-8")
    env, _removed = pd.child_env({})
    log = tmp_path / "G01.log"
    with open(log, "xb") as handle:
        code = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "test_demo.py"],
                              cwd=str(tmp_path), env=env, stdin=subprocess.DEVNULL, stdout=handle,
                              stderr=subprocess.STDOUT, timeout=120).returncode
    text = log.read_bytes().decode("utf-8")
    assert code == 1
    assert "AssertionError: 中文断言说明：两边不一样" in text
    assert "\\u4e2d" not in text and "\\u95e8" not in text


def test_the_variable_is_what_makes_the_difference_on_a_cp1252_locale(tmp_path, monkeypatch):
    # 对照：同一条用例去掉 PYTHONUTF8、把标准输出编码钉成 cp1252（这台机器的缺省），断言说明就成了转义串。
    # 钉住编码是为了在别的区域编码（例如本来就是 UTF-8 的机器）上也测得出来
    (tmp_path / "test_demo.py").write_text(FAILING, encoding="utf-8")
    env, _removed = pd.child_env({})
    env.pop("PYTHONUTF8", None)
    env["PYTHONIOENCODING"] = "cp1252"
    out = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", "test_demo.py"],
                         cwd=str(tmp_path), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, timeout=120).stdout.decode("utf-8", "replace")
    assert "\\u4e2d\\u6587" in out
    assert "中文断言说明" not in out
    assert os.environ.get("PYTHONIOENCODING") != "cp1252"  # 只改子进程的环境
