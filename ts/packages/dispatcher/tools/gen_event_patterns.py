"""生成 ts/packages/dispatcher/src/event-patterns.ts：pi_dispatch 的事件流摘要（迁移第 ④b6 片）用到的正则原文。

TS 一侧用 @themis/base/pyregex 的 sre 移植编译同一份原文，re.I、MULTILINE 下的 ^ $、Unicode 的词字符、词边界与后行断言都与
Python 逐字一致，不手译。模块级的模式按名字取（编译时的标志写成开头的内联标志）；函数里内联的几条按 ast 取出。
用法：python ts/packages/dispatcher/tools/gen_event_patterns.py（在仓库根目录运行）。改了 pi_dispatch 的这些正则就重新生成，
生成的文件不手改。--check 只比较、不写：与现有文件不同时退出 1（④b6 的契约调用它）。
"""
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))
import pi_dispatch  # noqa: E402

OUT = ROOT / "ts" / "packages" / "dispatcher" / "src" / "event-patterns.ts"
NAMED = [
    "TEMP_PATH_RE", "_ABS_PATH_START_RE", "_DEVICE_PATH_RE", "_RM_CALL_RE", "SKIP_MARKER_RE", "ASSERT_RE",
    "AMBIGUITY_RE", "INTERPRETATION_RE", "MASKED_EXIT_RE", "_PIPEFAIL_RE", "_CHECK_COMMAND_RE", "_TEMP_DIR_CREATE_RE",
    "_TEMP_DIR_CLEANUP_RE", "AMBIGUITY_NEGATION_RE", "AMBIGUITY_DOUBLE_NEGATION_RE", "AMBIGUITY_RESOLVED_RE",
    "TEXTUAL_TOOL_CALL_RE", "AMBIGUITY_CONTEXT_RE",
]
FLAG_LETTERS = ((re.I, "i"), (re.M, "m"), (re.S, "s"), (re.X, "x"))


def with_flags(pattern: str, flags: int) -> str:
    letters = "".join(letter for flag, letter in FLAG_LETTERS if flags & flag)
    return ("(?%s)" % letters if letters else "") + pattern


def re_calls(function: str):
    """函数里每个 re.<方法>(…) 调用：（方法名, 第一个参数里的字符串常量，按左到右）。"""
    tree = ast.parse(Path(pi_dispatch.__file__).read_text(encoding="utf-8"))
    node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == function)
    calls = []
    for item in ast.walk(node):
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) and isinstance(item.func.value, ast.Name) \
                and item.func.value.id == "re" and item.args:
            constants = [part.value for part in ast.walk(item.args[0]) if isinstance(part, ast.Constant) and isinstance(part.value, str)]
            calls.append((item.lineno, item.func.attr, constants))
    return [(attr, constants) for _line, attr, constants in sorted(calls)]


def inline(function: str, method: str, index: int = 0) -> str:
    found = [constants for attr, constants in re_calls(function) if attr == method]
    assert len(found[index]) == 1, (function, method, found)
    return found[index][0]


def cache_target_shape() -> None:
    """_CACHE_TARGET_RE 带反向引用，sre 移植不收：TS 按步骤解析（shell-scan.ts 的 cacheTargetDirs），这里钉住它的形状。"""
    backslash = chr(92)
    names = "|".join(re.escape(name) for name in pi_dispatch._CACHE_DIR_NAMES)
    expected = "^([\"']?)((?:[A-Za-z0-9_.-]+/)*)(%s)/?" % names + backslash + "1$"
    assert pi_dispatch._CACHE_TARGET_RE.pattern == expected and not pi_dispatch._CACHE_TARGET_RE.flags & ~re.U, (
        "_CACHE_TARGET_RE 变了：同时改 shell-scan.ts 的 cacheTargetDirs")


def main() -> None:
    cache_target_shape()
    patterns = {name: with_flags(getattr(pi_dispatch, name).pattern, getattr(pi_dispatch, name).flags) for name in NAMED}
    left_edge = inline("_protected_mentions", "finditer")
    assert left_edge == inline("_mask_paths", "finditer"), "两处左边界不同"
    patterns["LEFT_EDGE"] = left_edge
    patterns["PATH_TAIL"] = inline("_outside_mentions", "match", 1)
    patterns["REMOVE_ITEM"] = with_flags(inline("_cache_dir_cleanup", "search"), re.I)
    patterns["SKIP_HEADING"] = with_flags(inline("ambiguity_domain_words", "match"), re.I)
    tables = {
        "SUSPICIOUS_COMMANDS": [[pattern, label] for pattern, label in pi_dispatch.SUSPICIOUS_COMMANDS],
        "STDERR_WARNING_PATTERNS": [[name, pattern] for name, pattern in pi_dispatch.STDERR_WARNING_PATTERNS],
    }
    lines = [
        "// 由 ts/packages/dispatcher/tools/gen_event_patterns.py 生成，不要手改：改了 pi_dispatch 的这些正则就重新生成。",
        "// 原文交给 @themis/base/pyregex 的 sre 移植编译（compilePy），语义与 Python 逐字一致。",
        "",
        "export const EVENT_PATTERNS = {",
    ]
    lines += ["  %s: %s," % (name, json.dumps(value, ensure_ascii=False)) for name, value in patterns.items()]
    lines += ["} as const;", ""]
    for name, rows in tables.items():
        lines.append("export const %s: readonly (readonly [string, string])[] = [" % name)
        lines += ["  [%s, %s]," % (json.dumps(a, ensure_ascii=False), json.dumps(b, ensure_ascii=False)) for a, b in rows]
        lines += ["];", ""]
    lines.append("export const CACHE_DIR_NAMES: readonly string[] = %s;" % json.dumps(list(pi_dispatch._CACHE_DIR_NAMES)))
    lines.append("")
    data = chr(10).join(lines).encode("utf-8")
    if "--check" in sys.argv[1:]:
        if not OUT.is_file() or OUT.read_bytes() != data:
            print("%s 与 pi_dispatch 的正则不一致：重新运行本脚本" % OUT.relative_to(ROOT))
            sys.exit(1)
        print("一致")
        return
    OUT.write_bytes(data)
    print("写入 %s：%d 条模式" % (OUT.relative_to(ROOT), len(patterns) + sum(len(rows) for rows in tables.values())))


if __name__ == "__main__":
    main()
