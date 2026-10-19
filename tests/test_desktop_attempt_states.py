"""W5：桌面端的状态表与调度器的 attempt 状态全集逐项相同（同样的状态、同样的顺序）。

桌面端 ``desktop/web/src/domain/attemptStates.ts`` 的 ``ATTEMPT_STATES`` 与调度器
``scripts/pi_dispatch.py`` 的 ``ATTEMPT_STATES`` 必须一致：新增或删除状态要同时改两处。
本文件只用标准库与 pytest，路径由 ``Path(__file__).resolve().parents[1]`` 推出、不依赖 cwd，
也不导入 ``tests/`` 里别的模块（门禁会把它单独拷进临时目录跑）。
改了 ``attemptStates.ts`` 或 PD 的 ``ATTEMPT_STATES`` 之后，在仓库根跑：
``python -m pytest tests/test_desktop_attempt_states.py -q``。
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pi_dispatch as pd  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
TS_PATH = REPO_ROOT / "desktop" / "web" / "src" / "domain" / "attemptStates.ts"


class AttemptStatesParseError(Exception):
    """解析 attemptStates.ts 的第一层键时出错：缺声明、展开、计算键、无键、键重复。"""


def parse_attempt_states_keys(source: str) -> list:
    """从 TS 源码里取 ``export const ATTEMPT_STATES`` 对象字面量第一层的键，保持源码顺序。

    跳过字符串与注释；第一层出现展开（``...``）或计算键（``[...]``）、找不到声明、一个键也没有、键重复都报错。
    """
    decl = re.search(r"export\s+const\s+ATTEMPT_STATES\b", source)
    if not decl:
        raise AttemptStatesParseError("找不到 export const ATTEMPT_STATES 的声明")
    eq = source.find("=", decl.end())
    if eq < 0:
        raise AttemptStatesParseError("ATTEMPT_STATES 声明后没有赋值")
    start = source.find("{", eq)
    if start < 0:
        raise AttemptStatesParseError("ATTEMPT_STATES 没有对象字面量")

    keys: list = []
    seen: set = set()
    n = len(source)
    i = start
    depth = 0
    at_member_start = False
    pending_key = None  # (kind, value)：可能是键的 token
    while i < n:
        c = source[i]
        # 注释：行注释与块注释都跳过。
        if c == "/" and i + 1 < n and source[i + 1] == "/":
            j = source.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if c == "/" and i + 1 < n and source[i + 1] == "*":
            j = source.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        # 字符串：整体跳过，内容不当键（除非它就处在成员首位，那时它是引号键）。
        if c in "\"'":
            quote = c
            j = i + 1
            while j < n:
                if source[j] == "\\":
                    j += 2
                    continue
                if source[j] == quote:
                    break
                j += 1
            if depth == 1 and at_member_start and pending_key is None:
                pending_key = ("str", source[i + 1:j])
            i = j + 1
            continue
        if c == "`":  # 模板字符串：整体跳过，不作键。
            j = i + 1
            while j < n:
                if source[j] == "\\":
                    j += 2
                    continue
                if source[j] == "`":
                    break
                j += 1
            i = j + 1
            continue
        if c == "{":
            depth += 1
            if depth == 1:
                at_member_start = True
                pending_key = None
            i += 1
            continue
        if c == "}":
            depth -= 1
            if depth == 0:
                break
            if depth == 1:
                at_member_start = False
                pending_key = None
            i += 1
            continue
        if c == ",":
            if depth == 1:
                at_member_start = True
                pending_key = None
            i += 1
            continue
        if c == ":":
            if depth == 1 and at_member_start and pending_key is not None:
                key = pending_key[1]
                if key in seen:
                    raise AttemptStatesParseError(f"第一层键重复：{key}")
                seen.add(key)
                keys.append(key)
            at_member_start = False
            pending_key = None
            i += 1
            continue
        if c == "." and source[i:i + 3] == "...":
            if depth == 1 and at_member_start:
                raise AttemptStatesParseError("第一层出现展开写法 ...")
            i += 3
            continue
        if c == "[":
            if depth == 1 and at_member_start:
                raise AttemptStatesParseError("第一层出现计算键 [...]")
            i += 1
            continue
        if c == "]":
            i += 1
            continue
        if c.isspace():
            i += 1
            continue
        if c.isalpha() or c in "_$":
            j = i
            while j < n and (source[j].isalnum() or source[j] in "_$"):
                j += 1
            if depth == 1 and at_member_start and pending_key is None:
                pending_key = ("id", source[i:j])
            i = j
            continue
        i += 1  # 数字、运算符等其它字符：跳过
    if not keys:
        raise AttemptStatesParseError("ATTEMPT_STATES 一个键也没有")
    return keys


def compare_states(pd_states: list, ts_states: list):
    """桌面端与调度器一致返回 None，否则返回分列「桌面端缺 / 桌面端多 / 顺序不同」的说明。"""
    if ts_states == pd_states:
        return None
    ts_set, pd_set = set(ts_states), set(pd_states)
    missing = [s for s in pd_states if s not in ts_set]
    extra = [s for s in ts_states if s not in pd_set]
    lines = ["桌面端 attemptStates.ts 与调度器 pi_dispatch 的 ATTEMPT_STATES 不一致："]
    if missing:
        lines.append(f"  桌面端缺（调度器有、桌面端没有）：{missing}")
    if extra:
        lines.append(f"  桌面端多（桌面端有、调度器没有）：{extra}")
    if not missing and not extra:
        lines.append("  顺序不同（集合相同、顺序不同）：")
        lines.append(f"    调度器：{pd_states}")
        lines.append(f"    桌面端：{ts_states}")
    else:
        lines.append(f"    调度器：{pd_states}")
        lines.append(f"    桌面端：{ts_states}")
    return "\n".join(lines)


def test_desktop_attempt_states_match_dispatcher():
    pd_states = list(pd.ATTEMPT_STATES)
    ts_states = parse_attempt_states_keys(TS_PATH.read_text(encoding="utf-8"))
    problem = compare_states(pd_states, ts_states)
    assert problem is None, problem


def test_parser_catches_one_more_or_one_fewer_key():
    base = "export const ATTEMPT_STATES = { A: { x: 1 }, B: { y: 2 }, C: { z: 3 } };"
    assert parse_attempt_states_keys(base) == ["A", "B", "C"]
    more = "export const ATTEMPT_STATES = { A: { x: 1 }, B: { y: 2 }, C: { z: 3 }, D: { w: 4 } };"
    fewer = "export const ATTEMPT_STATES = { A: { x: 1 }, B: { y: 2 } };"
    assert parse_attempt_states_keys(more) == ["A", "B", "C", "D"]
    assert parse_attempt_states_keys(fewer) == ["A", "B"]
    # 多一个、少一个都和基线不同（看得出来的变化）
    assert parse_attempt_states_keys(more) != parse_attempt_states_keys(base)
    assert parse_attempt_states_keys(fewer) != parse_attempt_states_keys(base)


def test_parser_ignores_fake_keys_in_comments_and_strings():
    src = (
        "export const ATTEMPT_STATES = {\n"
        "  A: { label: '甲：乙', tone: 'x' },\n"  # 字符串里的冒号不算键
        "  /* B: 假键，注释里不算 */\n"
        "  // C: 行注释里的假键也不算\n"
        "  D: { tone: 'y' },\n"
        "};"
    )
    assert parse_attempt_states_keys(src) == ["A", "D"]


def test_parser_rejects_spread_computed_duplicate_missing_and_empty():
    with pytest.raises(AttemptStatesParseError, match="展开"):
        parse_attempt_states_keys("export const ATTEMPT_STATES = { ...BASE, A: { x: 1 } };")
    with pytest.raises(AttemptStatesParseError, match="计算键"):
        parse_attempt_states_keys("export const ATTEMPT_STATES = { [KEY]: { x: 1 } };")
    with pytest.raises(AttemptStatesParseError, match="重复"):
        parse_attempt_states_keys("export const ATTEMPT_STATES = { A: { x: 1 }, A: { y: 2 } };")
    with pytest.raises(AttemptStatesParseError, match="找不到"):
        parse_attempt_states_keys("const OTHER = { A: { x: 1 } };")
    with pytest.raises(AttemptStatesParseError, match="一个键也没有"):
        parse_attempt_states_keys("export const ATTEMPT_STATES = {};")
