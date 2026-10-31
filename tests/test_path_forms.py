"""第 124 轮：_path_forms 的次序不随集合的散列变。

同一路径用反斜杠、正斜杠与 Git Bash 的 /c/… 写出来都等长。以前只按长度排，等长的次序随 PYTHONHASHSEED 而变；命令里两处匹配的摘录
区间重叠时，_protected_mentions 与 _mask_paths 的结果就跟着变，同一份事件流每次 collect 可能写出不同的 events-summary。
现在等长的按字面排。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import kit_hub as kh  # noqa: E402
import pi_dispatch as pd  # noqa: E402

SEP = chr(92)
PROJECT = "C:" + SEP + "x" + SEP + "proj"
#: C:/ 的摘录（到空白或命令分隔符为止，逗号不算）盖住了后面那个 /c/ 写法：先处理哪个写法，结果就不同
OVERLAP = "cat C:/x/proj/a,/c/x/proj"


def test_forms_are_ordered_by_length_then_text():
    forms = pd._path_forms([Path(PROJECT), Path("/tmp/pi-wt"), Path("ab")])
    assert forms == sorted(set(forms), key=lambda form: (-len(form), form))


@pytest.mark.skipif(os.name != "nt", reason="盘符与 Git Bash 的 /c/ 写法只在 Windows 上有")
def test_forms_and_mentions_do_not_depend_on_the_hash_seed():
    code = "\n".join([
        "import json, sys",
        "from pathlib import Path",
        "sys.path.insert(0, %r)" % str(SCRIPTS),
        "import pi_dispatch as pd",
        "forms = pd._path_forms([Path(%r)])" % PROJECT,
        "print(json.dumps([forms, pd._protected_mentions(%r, forms), pd._mask_paths(%r, forms)]))" % (OVERLAP, OVERLAP),
    ])
    seen = set()
    for seed in range(16):
        env = dict(os.environ, PYTHONHASHSEED=str(seed))
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=60)
        assert result.returncode == 0, result.stderr
        seen.add(result.stdout.strip())
    assert len(seen) == 1, seen
    forms, mentions, _masked = json.loads(seen.pop())
    assert forms[:3] == ["/c/x/proj", "C:/x/proj", PROJECT]
    assert mentions == ["/c/x/proj", "C:/x/proj/a,/c/x/proj"]

def test_hub_forms_are_ordered_by_length_then_text():
    # 第 133 轮：kit_hub.path_forms 是同一个毛病（三种写法等长、从集合按长度排），修法相同
    forms = kh.path_forms(Path(PROJECT))
    assert forms == sorted(set(forms), key=lambda form: (-len(form), form))


@pytest.mark.skipif(os.name != "nt", reason="盘符与 Git Bash 的 /c/ 写法只在 Windows 上有")
def test_hub_forms_and_guard_config_do_not_depend_on_the_hash_seed():
    code = chr(10).join([
        "import sys",
        "from pathlib import Path",
        "sys.path.insert(0, %r)" % str(SCRIPTS),
        "import kit_hub as kh",
        "print(kh.guard_config(Path(%r), Path(%r)))" % (PROJECT, "C:/x"),
    ])
    seen = set()
    for seed in range(16):
        env = dict(os.environ, PYTHONHASHSEED=str(seed))
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=60)
        assert result.returncode == 0, result.stderr
        seen.add(result.stdout.strip())
    assert len(seen) == 1, seen
    config = json.loads(seen.pop())
    assert config["workspaceForms"] == ["/c/x/proj", "c:/x/proj", PROJECT.lower()]
    assert config["mainForms"] == ["/c/x", "c:/x", "c:" + SEP + "x"]
