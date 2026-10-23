"""mutate 碰上被中断的运行（第 72 轮）。

run_supervised 收到 Ctrl+C、关闭控制台或控制台的 CTRL_BREAK 时报 interrupted。此前 mutate 把这样的运行记成
“被取消”却算抓住，还接着跑后面的变异：按 Ctrl+C 停不下来，被打断、没跑完的测试也被当成“抓住”的证据。实例：
TS 进程监督的变异 V17（不另起进程组）让 CTRL_BREAK 广播到整个控制台，外层 shell 被结束，mutate 却继续把树改下去。
测试在进程内替换 run_supervised，文件里出现指定文字时让它报 interrupted。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pi_dispatch as pd  # noqa: E402

MUTATED = "A = 1\nB = 2\nC = 3\n"


def _mutate_with_interrupt(tmp_path, monkeypatch, interrupt_on, commands=None):
    """在一棵临时树上跑 mutate --tree；文件里出现 interrupt_on 时，让 run_supervised 报 interrupted（如同收到
    Ctrl+C 或控制台的 CTRL_BREAK）。返回（退出码, mutations.json, 每次运行时看到的文件内容）。"""
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "m.py").write_bytes(MUTATED.encode("utf-8"))
    real = pd.run_supervised
    seen = []

    def fake(cmd, cwd, env, stdout, stderr, *args, **kwargs):
        result = real(cmd, cwd, env, stdout, stderr, *args, **kwargs)
        text = (Path(cwd) / "m.py").read_bytes().decode("utf-8")
        seen.append(text)
        return dict(result, interrupted=True) if interrupt_on in text else result

    monkeypatch.setattr(pd, "run_supervised", fake)
    # 变异都把某个值改成以 0 结尾的数：出现 "0\n" 就以 1 退出（抓住）
    check = [sys.executable, "-c", "import sys; t = open('m.py').read(); sys.exit(1 if '0' + chr(10) in t else 0)"]
    spec = {"timeout_seconds": 60,
            "mutations": [{"name": "抓住", "file": "m.py", "old": "A = 1\n", "new": "A = 10\n"},
                          {"name": "被中断", "file": "m.py", "old": "B = 2\n", "new": "B = 20\n"},
                          {"name": "没有运行", "file": "m.py", "old": "C = 3\n", "new": "C = 30\n"}]}
    if commands:
        spec["commands"] = [{"id": cid, "argv": check} for cid in commands]
    else:
        spec["command"] = check
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out"
    code = pd.main(["--repo", str(tmp_path), "mutate", "--tree", str(tree), "--spec", str(spec_path), "--out", str(out)])
    assert (tree / "m.py").read_bytes() == MUTATED.encode("utf-8")  # 被中断的那条也恢复了
    return code, json.loads((out / "mutations.json").read_text(encoding="utf-8")), seen


def test_an_interrupted_run_is_an_error_and_stops_the_mutations(tmp_path, monkeypatch, capsys):
    code, record, seen = _mutate_with_interrupt(tmp_path, monkeypatch, "B = 20")
    printed = capsys.readouterr().out
    assert code == pd.EXIT_FAIL
    assert [r["status"] for r in record["results"]] == ["caught", "error"]
    assert "被中断" in record["results"][1]["reason"] and "不算抓住" in record["results"][1]["reason"]
    assert record["not_run"] == ["没有运行"]
    assert record["files_left_modified"] == []
    assert not any("C = 30" in text for text in seen)  # 后面那条真的没有套用
    assert "MUTATE 被中断：后面 1 条变异没有运行" in printed
    assert "只跑了 2 条" in printed and "没有运行：没有运行" in printed


def test_an_interrupted_baseline_still_aborts_before_any_mutation(tmp_path, monkeypatch, capsys):
    code, record, seen = _mutate_with_interrupt(tmp_path, monkeypatch, "A = 1\n")
    assert code == pd.EXIT_BLOCKED and "不做变异时 command 没有通过（被取消）" in capsys.readouterr().err
    assert record["aborted"] == "baseline_failed" and seen == [MUTATED]


def test_with_several_commands_the_rest_are_not_run_after_an_interrupt(tmp_path, monkeypatch, capsys):
    code, record, seen = _mutate_with_interrupt(tmp_path, monkeypatch, "B = 20", commands=["one", "two"])
    assert code == pd.EXIT_FAIL
    assert sorted(record["results"][1]["commands"]) == ["one"]  # 第一条命令被中断，第二条不再跑
    assert record["results"][1]["commands"]["one"]["status"] == "error"
    assert sum("B = 20" in text for text in seen) == 1
    assert record["not_run"] == ["没有运行"]


def test_a_complete_run_has_an_empty_not_run_list(tmp_path, monkeypatch, capsys):
    code, record, _seen = _mutate_with_interrupt(tmp_path, monkeypatch, "never")
    assert code == pd.EXIT_OK
    assert [r["status"] for r in record["results"]] == ["caught", "caught", "caught"]
    assert record["not_run"] == []
    assert "运行被中断" not in capsys.readouterr().out
