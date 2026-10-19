"""tests/conftest.py：全量 pytest 默认跳过前端流水线，点名运行或设 TT_FRONTEND_TESTS=1 照常跑（T002 的站主 Q6）。"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

CONFTEST = Path(__file__).resolve().parent / "conftest.py"
SAMPLE = '''import pytest


@pytest.fixture(scope="session")
def pipeline():
    return "npm 跑过了"


@pytest.fixture
def built(pipeline):
    return pipeline


def test_reads_source():
    assert True


def test_uses_pipeline(pipeline):
    assert pipeline


def test_uses_it_indirectly(built):
    assert built
'''


def run(tmp_path, *args, frontend=None):
    env = {key: value for key, value in os.environ.items() if key != "TT_FRONTEND_TESTS"}
    if frontend is not None:
        env["TT_FRONTEND_TESTS"] = frontend
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
                          cwd=str(tmp_path), env=env, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=120)
    return proc.stdout.strip().splitlines()[-1]


def test_full_run_skips_the_frontend_pipeline_unless_named_or_asked(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    shutil.copy(CONFTEST, tests / "conftest.py")
    (tests / "test_gate_sample.py").write_text(SAMPLE, encoding="utf-8")
    (tests / "test_other.py").write_text("def test_other():\n    assert True\n", encoding="utf-8")
    assert run(tmp_path).startswith("2 passed, 2 skipped")
    assert run(tmp_path, "tests").startswith("2 passed, 2 skipped")
    assert run(tmp_path, "tests/test_gate_sample.py").startswith("3 passed")
    assert run(tmp_path, "tests/test_gate_sample.py::test_uses_pipeline").startswith("1 passed")
    assert run(tmp_path, str(tests / "test_gate_sample.py"), "tests/test_other.py").startswith("4 passed")
    assert run(tmp_path, frontend="1").startswith("4 passed")
    assert run(tmp_path, frontend="0").startswith("2 passed, 2 skipped")
