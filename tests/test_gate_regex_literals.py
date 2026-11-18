"""第 193 轮：门禁基准交给 re.* 的正则字面量，收集时先各编译一遍（tests/conftest.py 的 GateModule），编译不过的门禁收集失败。"""

import shutil
import subprocess
import sys
from pathlib import Path

import conftest

CONFTEST = Path(conftest.__file__).resolve()

#: T054 门禁的 _no_skip_marks 原样：r"\bxit\(" 写成了 r"\xit\("
T054_HELPER = r'''import re


def _no_skip_marks(text):
    problems = []
    for bad in (r"\.skip\b", r"\.only\b", r"\xit\(", r"\bxtest\("):
        if re.search(bad, text):
            problems.append(bad)
    return problems


def test_marks():
    assert _no_skip_marks("it('x')") == []
'''
T054_FIXED = T054_HELPER.replace(r'r"\xit\("', r'r"\bxit\("')

SHAPES = r'''import re

WORD = r"\bok\b"
BROKEN = r"[a-"
PAIRS = ((r"\d+", "number"), (r"(?P<x", "group"))


def check(text):
    hits = [re.search(WORD, text), re.findall(BROKEN, text), re.compile(r"\q"), re.compile(r"[[:alpha:]]")]
    for pattern, label in PAIRS:
        hits.append((label, re.match(pattern, text)))
    compiled = [re.compile(p) for p in (r"fine", r"\k")]
    return hits, compiled, re.sub(r"a{2,1}", "", text)
'''

FLAGS = r'''import re

LOOSE = 0


def check(text):
    return (re.compile(r"[a-z]+  # ( a comment, not a group", re.X),
            re.search(r"[a-z]+  # ( again", text, flags=re.VERBOSE | re.I),
            re.search(r"(  # not verbose here", text),
            re.compile(r"(", LOOSE))
'''

SHADOWS = r'''import re

ROOT = r"C:\Users\x"
pattern = r"("


def has(ROOT, text):
    return re.search(ROOT, text)


def find(text, build):
    pattern = build()
    return re.search(pattern, text)
'''


def where(problems):
    """每处问题的“行号 + 写法”（re 的报错文字随 Python 版本可能变，不比）。"""
    return [problem.split(": ", 1)[0] for problem in problems]


def test_t054s_typo_is_caught_where_the_loop_takes_it_from_a_literal_tuple():
    assert conftest.regex_literal_problems(T054_HELPER) == [r'line 6 r"\xit\(": incomplete escape \x at position 0']
    assert conftest.regex_literal_problems(T054_FIXED) == []


def test_literals_given_directly_or_by_name_are_compiled():
    # 直接写的、模块级的、推导式与拆包取出的都认，按行号排；嵌套集合的 FutureWarning 不算编译不过
    assert where(conftest.regex_literal_problems(SHAPES)) == [
        'line 4 r"[a-"', 'line 5 r"(?P<x"', r'line 9 r"\q"', r'line 12 r"\k"', 'line 13 r"a{2,1}"']


def test_flags_decide_how_a_literal_reads():
    # re.X 下 # 起的是注释；flags 认不得（这里是个名字）就不编，免得把 verbose 写法当错
    assert where(conftest.regex_literal_problems(FLAGS)) == ['line 9 r"(  # not verbose here"']


def test_a_name_bound_in_its_own_function_is_not_taken_from_the_module():
    assert conftest.regex_literal_problems(SHADOWS) == []


def test_every_gate_in_the_repo_compiles():
    gates = sorted(CONFTEST.parent.glob("test_gate_t*_baseline.py"))
    assert len(gates) >= 52
    found = {gate.name: conftest.regex_literal_problems(gate.read_text(encoding="utf-8")) for gate in gates}
    assert {name: problems for name, problems in found.items() if problems} == {}


def collect(tmp_path, name, source):
    tests = tmp_path / "tests"
    tests.mkdir(exist_ok=True)
    shutil.copy(CONFTEST, tests / "conftest.py")
    (tests / name).write_text(source, encoding="utf-8")
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only", "tests/" + name],
                          cwd=str(tmp_path), capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=120)
    return proc.returncode, proc.stdout


def test_collection_stops_a_gate_whose_regex_does_not_compile(tmp_path):
    # 内核收门禁时跑的就是 pytest --collect-only：退出码 2，报错原样写着行号与源码里的写法
    code, out = collect(tmp_path, "test_gate_t999_baseline.py", T054_HELPER)
    assert code == 2
    assert r'line 6 r"\xit\(": incomplete escape \x at position 0' in out
    assert collect(tmp_path, "test_gate_t998_baseline.py", T054_FIXED)[0] == 0
    # 只管门禁基准；别的测试文件照旧到跑起来才编译
    assert collect(tmp_path, "test_other.py", T054_HELPER)[0] == 0
    # 语法错误照旧由 pytest 自己报，不从 conftest 的核对里抛出来
    code, out = collect(tmp_path, "test_gate_t997_baseline.py", "def test_x(:\n    pass\n")
    assert code == 2 and "SyntaxError" in out and "regex_literal_problems" not in out
