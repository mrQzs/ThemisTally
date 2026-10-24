"""检查命令的输出模式（第 76 轮）：模式对着去掉 ANSI 控制序列之后的文本匹配；同一条正则既要匹配又不许出现的合同
在校验时就拒绝。

起因是 T015：Windows 上 picocolors 不看是不是终端、一律上色，Vitest 的输出写进日志也带色码，合同 V02–V04 的模式没
容忍色码，退出码 0、测试全过却判了失败；V07 的 must_match 与 must_not_match 写成同一条正则，任何实现都过不了。
两处都白花了 attempt。
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import pi_dispatch as pd  # noqa: E402

COLORED = (" \x1b[32m\x1b[1m✓\x1b[22m\x1b[39m packages/ui/test/app.test.ts \x1b[2m(\x1b[22m\x1b[2m12 tests\x1b[22m\x1b[2m)\x1b[22m\n"
           "\x1b[2m      Tests \x1b[22m \x1b[1m\x1b[32m12 passed\x1b[39m\x1b[22m\x1b[90m (12)\x1b[39m\n"
           "\x1b]8;;file:///x\x07link\x1b]8;;\x1b\\ done\n")


def run_item(tmp_path, patterns_ok=(), patterns_bad=()):
    work = tmp_path / "work"
    out = tmp_path / "out"
    work.mkdir()
    out.mkdir()
    (work / "colored.txt").write_bytes(COLORED.encode("utf-8"))
    item = {"id": "V01", "argv": [sys.executable, "-c",
                                  "import sys; sys.stdout.buffer.write(open('colored.txt', 'rb').read())"],
            "timeout_seconds": 60, "output_must_match": list(patterns_ok), "output_must_not_match": list(patterns_bad)}
    return pd._run_command_item(item, work, dict(pd.os.environ), out, 5.0), out


def test_patterns_match_the_text_without_ansi_escapes(tmp_path):
    record, out = run_item(tmp_path, [r"^\s+Tests\s+12 passed \(12\)$", r"✓ packages/ui/test/app\.test\.ts \(12 tests\)",
                                      r"^link done$"], [r"\x1b", r"failed"])
    assert record["passed"] is True, record["reason"]
    assert all(m["matched"] for m in record["output_must_match"])
    # 日志照原样保存：色码还在
    assert b"\x1b[32m" in (out / "V01.log").read_bytes()


def test_a_forbidden_pattern_still_fires_on_the_visible_text(tmp_path):
    record, _ = run_item(tmp_path, [], [r"12 passed"])
    assert record["passed"] is False and "输出命中禁止模式 12 passed" in record["reason"]


def contract_errors(item):
    errors = []
    pd._validate_command(dict({"id": "V07", "argv": ["x"], "timeout_seconds": 10}, **item), "checks", {}, errors)
    return errors


def test_the_same_pattern_on_both_sides_is_refused_at_validation():
    pattern = r"(?m)^\s*\S+\s+(?!ts/packages/ui/)"
    errors = contract_errors({"output_must_match": [pattern, "ok"], "output_must_not_match": ["bad", pattern]})
    assert errors == ["V07 同一条正则既在 output_must_match 又在 output_must_not_match 里，任何输出都过不了：%s" % pattern]
    assert contract_errors({"output_must_match": ["ok"], "output_must_not_match": ["bad"]}) == []
    # 类型不对的另有报错，这里不重复报，也不崩
    assert contract_errors({"output_must_match": "ok", "output_must_not_match": ["ok"]}) == [
        "V07 output_must_match 必须是字符串数组"]
