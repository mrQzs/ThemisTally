"""生成 ts/packages/base/src/pyregex/tables.ts 与 names.ts：TS 版 Python re（logs search，迁移第 ②b2 步）要的表。

    python ts/packages/base/tools/gen_pyregex_tables.py ts/packages/base/src/pyregex <NameAliases.txt>

- 大小写：sre 匹配时用的是 C 层的简单映射 Py_UNICODE_TOLOWER / Py_UNICODE_TOUPPER（_sre.unicode_tolower 只暴露了
  前一个），经 ctypes 直接调 python3xx.dll 导出的 _PyUnicode_ToLowercase / _PyUnicode_ToUppercase。生成前核对：
  前者与 _sre.unicode_tolower、两者合起来的“是否区分大小写”与 _sre.unicode_iscased 在全部码点上一致。
- 组名：str.isidentifier 的首字符（含 _）与后续字符。
- 字符名（\\N{...}，照 unicodedata.lookup）：unicodedata.name 给出的名字，去掉按算法生成的两类（CJK 统一表意文字、
  韩文音节，TS 照 unicodedata.c 的 _getcode 现算），加上 NameAliases.txt 的别名（Python 没有列别名的接口；每条都用
  unicodedata.lookup 核过）。具名序列不收：lookup 给出多个字符，re 里算“未定义的名字”。名字表按“十六进制码点;名字”
  一行一条，gzip 后 base64 存。

表里只有码点数字与 ASCII 名字，生成的源码里不出现任何特殊字符。只在 Python 的参照版本变了时重新生成。
"""
import base64
import ctypes
import gzip
import sys
import unicodedata
from pathlib import Path

import _sre
from re._casefix import _EXTRA_CASES

MAX = 0x110000


def ranges(predicate):
    out, start = [], None
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


def flat(spans):
    return ", ".join("0x%x, 0x%x" % span for span in spans)


def main():
    out_dir = Path(sys.argv[1])
    aliases_path = Path(sys.argv[2])
    api = ctypes.pythonapi
    to_upper = api._PyUnicode_ToUppercase
    to_lower = api._PyUnicode_ToLowercase
    for fn in (to_upper, to_lower):
        fn.restype = ctypes.c_uint32
        fn.argtypes = [ctypes.c_uint32]
    lower = {cp: to_lower(cp) for cp in range(MAX) if to_lower(cp) != cp}
    upper = {cp: to_upper(cp) for cp in range(MAX) if to_upper(cp) != cp}
    assert all(_sre.unicode_tolower(cp) == lower.get(cp, cp) for cp in range(MAX)), "tolower 与 _sre 不一致"
    assert all(bool(_sre.unicode_iscased(cp)) == (cp in lower or cp in upper) for cp in range(MAX)), "iscased 不一致"

    id_start = ranges(lambda cp: chr(cp).isidentifier())
    id_continue = ranges(lambda cp: ("a" + chr(cp)).isidentifier())
    cjk = ranges(lambda cp: (unicodedata.name(chr(cp), "") or "").startswith("CJK UNIFIED IDEOGRAPH-"))
    is_alpha = ranges(lambda cp: chr(cp).isalpha())  # 内联标志报错时选“unknown flag”还是“missing …”

    names = {}
    for cp in range(MAX):
        name = unicodedata.name(chr(cp), None)
        if name is None or name.startswith("CJK UNIFIED IDEOGRAPH-") or name.startswith("HANGUL SYLLABLE "):
            continue
        assert unicodedata.lookup(name) == chr(cp), name
        names[name] = cp
    aliases = 0
    for line in aliases_path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        code, alias, _kind = line.split(";")
        cp = int(code, 16)
        assert unicodedata.lookup(alias) == chr(cp), alias
        if alias in names:
            assert names[alias] == cp, alias
            continue
        names[alias] = cp
        aliases += 1
    upper_names = {}
    for name, cp in names.items():
        key = name.upper()
        assert upper_names.setdefault(key, cp) == cp, "大小写不同、码点不同的同名：%s" % name
    text = "".join("%x;%s\n" % (cp, name) for name, cp in sorted(names.items(), key=lambda item: (item[1], item[0])))
    assert text.isascii()
    packed = base64.b64encode(gzip.compress(text.encode("ascii"), compresslevel=9, mtime=0)).decode("ascii")

    head = ("// 由 ts/packages/base/tools/gen_pyregex_tables.py 生成，不要手改。\n"
            "// Python %s，unicodedata %s。\n\n" % (sys.version.split()[0], unicodedata.unidata_version))
    tables = [head,
              'export const UNIDATA_VERSION = "%s";\n\n' % unicodedata.unidata_version,
              "/** Py_UNICODE_TOLOWER：与自身不同的码点，[码点, 小写] 成对（%d 对） */\n" % len(lower),
              "export const LOWER: readonly number[] = [%s];\n" % ", ".join("0x%x, 0x%x" % kv for kv in sorted(lower.items())),
              "/** Py_UNICODE_TOUPPER：与自身不同的码点，[码点, 大写] 成对（%d 对） */\n" % len(upper),
              "export const UPPER: readonly number[] = [%s];\n" % ", ".join("0x%x, 0x%x" % kv for kv in sorted(upper.items())),
              "/** str.isidentifier 的首字符（含 _，%d 段） */\n" % len(id_start),
              "export const ID_START: readonly number[] = [%s];\n" % flat(id_start),
              "/** str.isidentifier 的后续字符（%d 段） */\n" % len(id_continue),
              "export const ID_CONTINUE: readonly number[] = [%s];\n" % flat(id_continue),
              "/** CJK 统一表意文字（名字按算法生成的区段，%d 段） */\n" % len(cjk),
              "export const CJK_UNIFIED: readonly number[] = [%s];\n" % flat(cjk),
              "/** str.isalpha（单个字符，%d 段） */\n" % len(is_alpha),
              "export const IS_ALPHA: readonly number[] = [%s];\n" % flat(is_alpha),
              "/** re._casefix._EXTRA_CASES：小写之后不同、可大写相同的码点（%d 个） */\n" % len(_EXTRA_CASES),
              "export const EXTRA_CASES: ReadonlyMap<number, readonly number[]> = new Map([%s]);\n" % ", ".join(
                  "[0x%x, [%s]]" % (key, ", ".join("0x%x" % v for v in values)) for key, values in sorted(_EXTRA_CASES.items()))]
    (out_dir / "tables.ts").write_text("".join(tables), encoding="utf-8", newline="\n")
    (out_dir / "names.ts").write_text(
        head + "/** 字符名与别名：gzip 之后 base64，解开是“十六进制码点;名字”一行一条（%d 个名字，其中别名 %d 个；"
        "原文 %d 字节，压缩后 %d 字节） */\nexport const NAMES_GZ_B64 =\n  \"%s\";\n"
        % (len(names), aliases, len(text), len(packed) * 3 // 4, packed),
        encoding="utf-8", newline="\n")
    print("lower", len(lower), "upper", len(upper), "id_start", len(id_start), "id_continue", len(id_continue),
          "cjk", cjk, "names", len(names), "aliases", aliases, "text", len(text), "b64", len(packed))


if __name__ == "__main__":
    main()
