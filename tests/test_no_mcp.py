"""pi 一律带 --no-mcp（第 81 轮）。

pi 1.4.0 内置 MCP，--tools 白名单保留 MCP 工具（除非条目以 mcp__ 开头）。执行器、hub 的 pi 工人与 --help、
--list-models 的探测都经 RESOURCE_FLAGS 带上它；它也是必需参数，不支持它的 pi 在派遣预检时就挡下，不静默降级。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / "scripts"))

import pi_dispatch as pd  # noqa: E402

HELP = (TESTS / "stub_pi_help.txt").read_text(encoding="utf-8")
NO_MCP_LINE = "  --no-mcp                       Disable built-in MCP support: no servers connect and no MCP tools\n"

FAKE_PI = '''import os, sys
args = sys.argv[1:]
if "--help" in args:
    sys.stdout.write(open(os.environ["FAKE_PI_HELP"], encoding="utf-8").read())
elif "--version" in args:
    print("1.4.0")
elif "--list-models" in args:
    print("provider  model           context  max-out  thinking  images")
    print("step      step-5-preview  256K     64K      yes       no")
elif args[:2] == ["auth", "check"]:
    print('{"ok": true}')
'''


def preflight(tmp_path: Path, help_text: str) -> dict:
    fake = tmp_path / "fake_pi.py"
    fake.write_text(FAKE_PI, encoding="utf-8")
    help_file = tmp_path / "help.txt"
    help_file.write_text(help_text, encoding="utf-8")
    env = dict(os.environ, FAKE_PI_HELP=str(help_file))
    executor = {"provider": "step", "model": "step-5-preview", "thinking": "high", "tools": list(pd.DEFAULT_TOOLS)}
    return pd.pi_preflight([sys.executable, str(fake)], tmp_path, executor, tmp_path / "out", env)


def test_no_mcp_is_passed_everywhere_and_required():
    assert "--no-mcp" in pd.RESOURCE_FLAGS  # 执行器、hub 的 pi 工人、--help 与 --list-models 的探测都带
    assert "--no-mcp" in pd.REQUIRED_PI_FLAGS


def test_preflight_blocks_a_pi_that_cannot_turn_mcp_off(tmp_path):
    assert NO_MCP_LINE in HELP
    result = preflight(tmp_path, HELP.replace(NO_MCP_LINE, ""))
    assert "本机 pi 不支持参数：--no-mcp" in result["problems"]
    assert result["ok"] is False


def test_preflight_passes_when_pi_supports_it(tmp_path):
    result = preflight(tmp_path, HELP)
    assert result["problems"] == []
    assert "--no-mcp" in result["help"]["flags"]
