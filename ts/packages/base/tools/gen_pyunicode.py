"""生成 ts/packages/base/src/pyunicode.ts：Python 的 re 与 str 对每个码点的判定，按区间存。

TS 的 secrets 要逐字复刻 Python 的脱敏结果，可 JS 的 \\w、\\b、\\s、\\d、re.I 与 Python 不同，Node 与 Bun 自带的
ICU 版本也可能不同。所以不用 \\p{...}，判定一律以本机 Python 为准，生成区间表（迁移计划第 ① 步 secrets）。
只在 Python 的参照版本变了（unicodedata.unidata_version 不同）时重新生成：

    python ts/packages/base/tools/gen_pyunicode.py ts/packages/base/src/pyunicode.ts

表里只有码点数字，生成的源码里不出现任何特殊字符。
"""
import re
import sys
import unicodedata

MAX = 0x110000


def ranges(predicate):
    out = []
    start = None
    for cp in range(MAX):
        hit = predicate(cp)
        if hit and start is None:
            start = cp
        elif not hit and start is not None:
            out.append((start, cp - 1))
            start = None
    if start is not None:
        out.append((start, MAX - 1))
    return out


def regex_set(pattern, flags=0):
    compiled = re.compile(pattern, flags)
    return lambda cp: compiled.fullmatch(chr(cp)) is not None


def render(name, doc, spans):
    flat = ", ".join("0x%x, 0x%x" % span for span in spans)
    return "/** %s（%d 段） */\nexport const %s: readonly number[] = [%s];\n" % (doc, len(spans), name, flat)


def main():
    out_path = sys.argv[1]
    tables = [
        ("WORD", "re 的 \\w（str 模式，Unicode）", regex_set(r"\w")),
        ("DIGIT", "re 的 \\d", regex_set(r"\d")),
        ("SPACE", "re 的 \\s", regex_set(r"\s")),
        ("IS_SPACE", "str.isspace", lambda cp: chr(cp).isspace()),
        ("IS_PRINTABLE", "str.isprintable", lambda cp: chr(cp).isprintable()),
        ("IS_UPPER", "str.isupper（单个字符）", lambda cp: chr(cp).isupper()),
        ("IS_LOWER", "str.islower（单个字符）", lambda cp: chr(cp).islower()),
        ("IS_DIGIT", "str.isdigit（单个字符）", lambda cp: chr(cp).isdigit()),
        ("CF_CC", "unicodedata.category 为 Cf 或 Cc", lambda cp: unicodedata.category(chr(cp)) in ("Cf", "Cc")),
        # NFKC 的占位符换法要用：Python 眼里未分配的码点（ICU 版本更新，可能已有分解或组合类）
        ("UNASSIGNED", "unicodedata.category 为 Cn（Python 眼里未分配）", lambda cp: unicodedata.category(chr(cp)) == "Cn"),
    ]
    parts = [
        "// 由 ts/packages/base/tools/gen_pyunicode.py 生成，不要手改。\n",
        "// Python %s，unicodedata %s。\n\n" % (sys.version.split()[0], unicodedata.unidata_version),
        'export const PYTHON_VERSION = "%s";\n' % sys.version.split()[0],
        'export const UNIDATA_VERSION = "%s";\n\n' % unicodedata.unidata_version,
    ]
    for name, doc, predicate in tables:
        parts.append(render(name, doc, ranges(predicate)))
    # re.I：每个 ASCII 字母在 IGNORECASE 下还匹配哪些非 ASCII 字符（re 文档写明的 İ ı ſ K）
    extra = {}
    for letter in "abcdefghijklmnopqrstuvwxyz":
        compiled = re.compile(letter, re.IGNORECASE)
        found = [cp for cp in range(0x80, MAX) if compiled.fullmatch(chr(cp))]
        if found:
            extra[letter] = found
    body = ", ".join("%s: [%s]" % (letter, ", ".join("0x%x" % cp for cp in cps)) for letter, cps in sorted(extra.items()))
    parts.append("/** re.IGNORECASE：ASCII 字母之外还匹配的码点（按小写字母列） */\n")
    parts.append("export const IGNORECASE_EXTRA: Readonly<Record<string, readonly number[]>> = { %s };\n" % body)
    with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(parts))
    print("wrote", out_path, {name: len(ranges(predicate)) for name, _, predicate in tables[:3]}, extra)


if __name__ == "__main__":
    main()
