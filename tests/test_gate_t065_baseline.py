"""T065 战前门禁：三个同步外观读取处理函数改成「每条路径恰好给 ``event.returnValue`` 赋一次」
（合同 t065-desktop-appearance-sync-read-fix.v1，基线 9da7f2a——三个处理函数都是「先设
``event.returnValue = null`` 再 ``try/catch``、``catch`` 里再设一次」，每处赋 2-3 次；Electron 的
``returnValue`` 第一次赋值就是给渲染进程的回复，之后的赋值不报错、直接被丢掉，所以页面首帧恒读到
``null``）。

被测对象（只钉本片带来的形状；T061 的其他行为、通道字面量与注册位置由改过的 T061 门禁 S07 照旧管）：

- ``desktop/shell/main.js`` 的三个同步外观读取处理函数（配平扫描定位，不按行号）：
  - 每个处理函数的跨度里给 ``event.returnValue`` 赋值**恰好一处**；
  - 外壳分支两处（赋非 null 值的那两处）：先 ``let answer = null;``，``try`` 块里来源被认时
    ``answer = currentAppearance;``，``catch`` 块里只有 ``answer = null;``（不出现 ``returnValue``），
    最后一句 ``event.returnValue = answer;`` 锚在处理函数体末尾（后面只剩 ``}`` 与 ``)``）；
  - 带参数起服务分支那一处：函数体只有 ``event.returnValue = null;`` 一句，没有 ``try``/``catch``。
- ``desktop/shell/README.md`` 的同步读取那一句改成「每条路径恰好给 ``event.returnValue`` 赋一次」，
  并带上原因句（第一次赋值就是回复、之后的赋值被丢掉）。

基线上这些形状不存在（三处各赋 2-3 次、README 写的是「每条路径都设过」），所以失败落在断言上，
不是收集失败：模块级只导入标准库，仓库文件的读取发生在用例函数里。没有流水线用例。
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL = REPO_ROOT / "desktop" / "shell"

HOST_APPEARANCE_CHANNEL = "themis-host:get-appearance"
SHELL_APPEARANCE_CHANNEL = "themis-shell:get-appearance"

# ipcMain.on( 的调用点（配平扫描取整个调用文本，不按行号）
IPC_MAIN_ON_RE = re.compile(r"ipcMain\s*\.\s*on\s*\(")
# 一次「给 returnValue 赋值」（== / === 这类比较不算）
RETURN_VALUE_ASSIGN_RE = re.compile(r"event\s*\.\s*returnValue\s*=(?!=)")
# 赋的是非 null 的值（与 T061 S07 的 RETURN_VALUE_NON_NULL_RE 同款：answering/always_null 的分类依据）
RETURN_VALUE_NON_NULL_RE = re.compile(r"event\s*\.\s*returnValue\s*=\s*(?!\s*null\b)")
# 外壳两处的尾锚：赋值是处理函数体的最后一句，右边是标识符，后面只剩 } 与 )
TAIL_ASSIGN_RE = re.compile(
    r"event\s*\.\s*returnValue\s*=\s*(?P<rhs>[A-Za-z_$][\w$]*)\s*;?\s*\}\s*\)\s*$"
)
# 带参数那一处的函数体：只有 event.returnValue = null; 一句（形参仍叫 event）
ONLY_NULL_BODY_RE = re.compile(
    r"\(\s*event\s*\)\s*=>\s*\{\s*event\s*\.\s*returnValue\s*=\s*null\s*;?\s*\}\s*\)\s*$"
)

ALLOWED_SYNC_CHANNEL_ARGS = (
    "HOST_APPEARANCE_CHANNEL",
    '"themis-host:get-appearance"',
    "SHELL_APPEARANCE_CHANNEL",
    '"themis-shell:get-appearance"',
)


# ---------------------------------------------------------------------------
# 通用小工具（只读仓库文件；模块级不做任何仓库 IO）
# ---------------------------------------------------------------------------

def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def _shell_read(rel: str) -> str:
    p = SHELL / rel
    assert p.is_file(), f"desktop/shell/{rel} 不存在"
    return _norm(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# JS 源码的区域提取：配平扫描（跳过字符串与注释），不按行号
# ---------------------------------------------------------------------------

def _match_bracket(text: str, open_at: int) -> int:
    """open_at 处是 '(' 或 '{'：返回与之配平的闭括号下标；配不上回 -1。跳过 // 与 /* */ 注释和字符串。"""
    opener = text[open_at]
    closer = {"(": ")", "{": "}"}[opener]
    depth = 0
    i = open_at
    n = len(text)
    while i < n:
        c = text[i]
        if c == "/" and text[i + 1:i + 2] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
            continue
        if c == "/" and text[i + 1:i + 2] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "'\"`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _strip_js_comments(text: str) -> str:
    """删掉 // 与 /* */ 注释，字符串照抄；每个被删字符换成空格，长度不变（下标仍可用）。
    main.js 的形状扫描先过这一遍：注释里提一句不算违规，只有代码里的形状才算。"""
    out = list(text)
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "/" and text[i + 1:i + 2] == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        if c == "/" and text[i + 1:i + 2] == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != "\n":
                    out[k] = " "
            i = j
            continue
        if c in "'\"`":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        i += 1
    return "".join(out)


def _main_code() -> str:
    """main.js 剥注释之后的文本（形状扫描用它）。"""
    return _strip_js_comments(_shell_read("main.js"))


def _ipc_main_on_calls(code: str):
    """main.js 里每次 ipcMain.on( 调用的（文本，首参）列表；首参取到第一层逗号为止。"""
    calls = []
    for m in IPC_MAIN_ON_RE.finditer(code):
        open_at = code.find("(", m.start())
        end = _match_bracket(code, open_at)
        assert end > 0, "main.js 里 ipcMain.on( 的括号配不平"
        span = code[m.start():end + 1]
        head = span[span.find("(") + 1:]
        first_arg = head.split(",")[0].strip()
        calls.append((span, first_arg))
    return calls


def _keyword_block(text: str, keyword: str):
    """keyword（如 "try" / "catch"）后面第一个配平的 {…} 块；找不到回 None。"""
    m = re.search(rf"\b{keyword}\b", text)
    if m is None:
        return None
    open_at = text.find("{", m.end())
    if open_at < 0:
        return None
    end = _match_bracket(text, open_at)
    return None if end < 0 else text[open_at:end + 1]


# ---------------------------------------------------------------------------
# main.js 的三条形状判定（都吃剥过注释的文本；测试函数与自检脚本共用）
# ---------------------------------------------------------------------------

def _check_exactly_one_assignment(code: str) -> None:
    """三处 ipcMain.on、通道白名单、宿主两处外壳一处；每个处理函数恰好一次 event.returnValue =。"""
    calls = _ipc_main_on_calls(code)
    assert len(calls) == 3, \
        f"main.js 的同步外观读取要恰好三处 ipcMain.on（现在是 {len(calls)} 处：两处在 runShellPage、" \
        "一处在带参数起服务分支）"
    for span, first_arg in calls:
        assert first_arg in ALLOWED_SYNC_CHANNEL_ARGS, \
            f"ipcMain.on 的通道只许那两个外观读取字面量，却见到：{first_arg}"
    host_reads = [c for c in calls if c[1] in ("HOST_APPEARANCE_CHANNEL", '"themis-host:get-appearance"')]
    shell_reads = [c for c in calls if c[1] in ("SHELL_APPEARANCE_CHANNEL", '"themis-shell:get-appearance"')]
    assert len(host_reads) == 2, "宿主同步读取要注册两处（外壳分支 + 带参数分支）"
    assert len(shell_reads) == 1, "外壳同步读取只在外壳分支注册一处"
    for span, _ in calls:
        count = len(RETURN_VALUE_ASSIGN_RE.findall(span))
        assert count == 1, \
            f"每个处理函数给 event.returnValue 赋值要恰好一次（这段跨度里有 {count} 次）：\n{span}"


def _check_shell_branch_shape(code: str) -> None:
    """外壳两处（赋非 null 值的）：局部变量 answer、末尾赋一次、try 里赋 currentAppearance、
    catch 里只有 answer = null。"""
    calls = _ipc_main_on_calls(code)
    answering = [span for span, _ in calls if RETURN_VALUE_NON_NULL_RE.search(span)]
    always_null = [span for span, _ in calls if not RETURN_VALUE_NON_NULL_RE.search(span)]
    assert len(answering) == 2, \
        f"外壳分支的两处要赋非 null 的当前外观（赋非 null 值的现在有 {len(answering)} 处）"
    assert len(always_null) == 1, "带参数起服务分支那一处恒答 null（只此一处）"
    for span in answering:
        tail = TAIL_ASSIGN_RE.search(span)
        assert tail, \
            f"外壳两处的 event.returnValue = answer; 要是处理函数体的最后一句（后面只剩 }} 与 )）：\n{span}"
        assert tail.group("rhs") == "answer", \
            f"右边要是局部变量 answer（逐字），却见到：{tail.group('rhs')}"
        assert re.search(r"let\s+answer\s*=\s*null\s*;", span), \
            "处理函数开头要有 let answer = null;（来源不认 / 读出错的缺省就是 null）"
        assert re.search(r"\btry\b", span) and re.search(r"\bcatch\b", span), \
            "跨度里要有 try 与 catch（读设置 / 窗口状态出错按 null 答）"
        try_block = _keyword_block(span, "try")
        catch_block = _keyword_block(span, "catch")
        assert try_block is not None and catch_block is not None, "try / catch 块要配得平"
        assert re.search(r"\banswer\s*=\s*currentAppearance\s*;", try_block), \
            "try 块里来源被认时要把 answer 赋成 currentAppearance（不是直接给 returnValue 赋值）"
        assert "returnValue" not in catch_block, \
            f"catch 块里不许再碰 returnValue（算好再赋一次才有意义）：\n{catch_block}"
        assert re.search(r"\banswer\s*=\s*null\s*;", catch_block), \
            "catch 块里要把 answer 设回 null"


def _check_with_args_shape(code: str) -> None:
    """带参数起服务分支那一处：函数体只有 event.returnValue = null; 一句，没有 try/catch。"""
    calls = _ipc_main_on_calls(code)
    always_null = [c for c in calls if not RETURN_VALUE_NON_NULL_RE.search(c[0])]
    assert len(always_null) == 1, "恒答 null 的要只有带参数起服务分支那一处"
    span, first_arg = always_null[0]
    assert first_arg in ("HOST_APPEARANCE_CHANNEL", '"themis-host:get-appearance"'), \
        "恒答 null 的那一处是带参数分支的宿主同步读取（HOST 通道）"
    assert not re.search(r"\btry\b", span) and not re.search(r"\bcatch\b", span), \
        f"带参数分支没有设置存储，不需要 try/catch：\n{span}"
    assert ONLY_NULL_BODY_RE.search(span), \
        f"带参数分支的处理函数体要只有 event.returnValue = null; 一句（形参仍叫 event）：\n{span}"


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_handlers_exactly_one_assignment():
    """S01 / D01：main.js 恰好三处同步外观读取 ipcMain.on（宿主两处、外壳一处），
    每个处理函数的跨度里给 event.returnValue 赋值恰好一次。"""
    _check_exactly_one_assignment(_main_code())


def test_s02_shell_branch_assign_once_at_end():
    """S02 / D01：外壳两处先在局部变量 answer 里算好（try 里来源被认赋 currentAppearance、
    catch 里设回 null），最后一句 event.returnValue = answer; 锚在处理函数体末尾；
    catch 块里不碰 returnValue。"""
    _check_shell_branch_shape(_main_code())


def test_s03_with_args_handler_only_null():
    """S03 / D01：带参数起服务分支那一处恒答 null——函数体只有 event.returnValue = null; 一句，
    没有 try/catch（这条分支没有设置存储）。"""
    _check_with_args_shape(_main_code())


def test_s04_readme_exactly_once_and_reason():
    """S04 / D03：README 的同步读取那一句改成「每条路径恰好给 event.returnValue 赋一次」，
    并带上原因句（第一次赋值就是回复、之后的赋值被丢掉）；那一行其余内容（三处全在 main.js、
    带参数分支恒答 null 等）仍在。"""
    text = _shell_read("README.md")
    lines = text.split("\n")
    sync_line = next((l for l in lines if "只此三处" in l and "ipcMain.on" in l), None)
    assert sync_line, "README 要保留同步读取那一句（只此三处、全在 main.js）"
    assert "恰好" in sync_line and "赋一次" in sync_line, \
        f"同步读取那一句要改成「每条路径恰好给 event.returnValue 赋一次」：\n{sync_line}"
    assert "都设过" not in sync_line, \
        f"旧说法「每条路径都设过」要改成「恰好赋一次」（多次赋值只有第一次生效）：\n{sync_line}"
    # 原因句写在外观段里：returnValue 第一次赋值就是回复，之后的赋值被丢掉
    start = text.find("## 外观")
    assert start >= 0, "README 要有「外观」一节"
    nxt = text.find("\n## ", start + 1)
    section = text[start:nxt if nxt > 0 else len(text)]
    for needle in ("第一次赋值", "回复", "丢"):
        assert needle in section, f"外观段要写清原因：returnValue {needle}…（第一次赋值就是回复，之后的赋值被丢掉）"
