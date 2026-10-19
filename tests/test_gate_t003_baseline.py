"""T003 战前门禁：桌面端前端随包字体（第二片）的黑盒基准测试（合同 t003-desktop-fonts，plan_version 1）。

被测对象是 ``desktop/web/``：``src/styles/fonts.css`` 的两条 ``@font-face``、``main.tsx`` 的引入、``dist`` 里恰有的
两个 woff2、``public/licenses/OFL.txt`` 许可副本与 ``THIRD_PARTY_NOTICES.md``、陈列页的中英文对齐样张。
基线（T002 结项）上这些都还没有，所以本文件的“失败”断言落在目标文件不存在或内容不符上，不是导入、收集或语法错误：
模块级只导入标准库，用到被测文件的地方都在用例函数里读。

结构（编号对应规划报告 §6.2 的 S1–S8、P1–P8，门禁端定稿时多加了 S9 和若干自检）：

- 静态断言（S 系列，不用流水线，全量 pytest 也跑）：读 ``fonts.css``、``main.tsx``、``src``、``SOURCE.md``、许可副本、
  notices、``App.css``。
- 流水线断言（P 系列）：会话级夹具 ``pipeline`` 在 ``desktop/web`` 下按顺序跑 ``npm ci``、``npm run build``、
  ``npm test``、``npm run check:contract``，再写一份临时探针 ``gate-probe/probe-<唯一标识>.test.tsx`` 用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除；前后各取一次 ``git status``。全量 pytest 默认跳过用到它的
  用例（``tests/conftest.py``），点名运行本文件时才跑。
- 门禁自检（``test_gate_selfcheck_*``，不依赖候选）：把各检查函数喂给合同写明的正确样本和若干改坏的样本，
  证明门禁自己放得过正确实现、拦得住常见错误。

DoD 对应：

- D01：S1、S2、S3（P4 在产物侧再查一遍）；
- D02：P2、P3、P4、P5（S3 查源码里没有第二处字体文件）；
- D03：S5、S6、S7、P6；
- D04：S8、S9、P8（P1 保证 ``npm test`` 与契约检查在样张进来之后仍通过）；
- D06：S4、P7（范围由调度器的范围门禁证明，这里不写相对基线的改动范围断言）；
- D05、D07 由 V02 里 T002 的断言负责，不在本文件重复。

过渡断言（``test_transitional_`` 开头）：S8、S9、P8。样张在陈列页（根路由）上，T002 规划里的第 3 片“应用框架与夹具数据层”
把陈列页移出根路由时推翻。

写法约定（规划报告 §6.3）：共享文件（notices、``public/licenses``）只断言“包含”；许可比较先把 CRLF 归一成 LF
（本机检出 4,820 字节，Git 里 4,708），woff2 与 dist 里的许可副本严格逐字节比较；产物文件名带哈希，按扩展名和内容找；
dist 的断言从 dist 自己读；只查字体相关的网络地址（React 产物里本来就有 ``https://reactjs.org/…``）；
jsdom 不加载字体、不排版，探针只核对结构与列数（U+4E00–U+9FFF 算 2 列，U+0020–U+007E 算 1 列，其他字符判失败）。

门禁做不到、留给人的项（合同 H1–H6）：
H1 样张各行右端 ``|`` 是否落在同一条竖线上（Regular、SemiBold 各一组，暗色亮色各一次）；
H2 SemiBold 明显比 Regular 粗、500 与 400 一样不是假粗体、Rendered Fonts 里是随包的 ``TT Sarasa Mono SC``；
H3 Network 面板里两个 woff2 同源相对地址加载、没有外部请求；
H4 notices 的版本、许可、来源、版权与 ``SOURCE.md``、``OFL.txt`` 一致（审核端读）；
H5 “设置 › 关于”列出 Sarasa Gothic（本片不做，设置页那一片的待办）；
H6 首屏 ``swap`` 换字体时的闪动是否可接受。
"""

import hashlib
import json
import os
import posixpath
import re
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import unquote as url_unquote

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_REL = "desktop/web"
WEB = REPO_ROOT / "desktop" / "web"
FONTS_DIR = WEB / "fonts"

FAMILY = "TT Sarasa Mono SC"
FONT_REGULAR = "sarasa-mono-sc-regular.woff2"
FONT_SEMIBOLD = "sarasa-mono-sc-semibold.woff2"
# @font-face 的字重区间 → 应指向的字体文件
FACE_WEIGHTS = {"300 500": FONT_REGULAR, "600 800": FONT_SEMIBOLD}
OFL_COPY_REL = f"{WEB_REL}/public/licenses/OFL.txt"
LUCIDE_LICENSE_LINK = "public/licenses/lucide-1.59.0-LICENSE.txt"
SPECIMEN_TITLE = "字体 · 等距更纱黑体 SC"
# 样张里 data-font-weight 的取值 → 应使用的字体令牌
SPECIMEN_TOKENS = {"400": "--tt-text-md", "500": "--tt-text-md-medium", "600": "--tt-title-sm"}

FONT_SUFFIXES = {".woff2", ".woff", ".ttf", ".otf", ".eot", ".ttc", ".otc"}
FONT_SIGNATURES = (b"wOFF", b"wOF2", b"OTTO", b"\x00\x01\x00\x00", b"true", b"ttcf")

# 夹具总预算留出余量给其余快测试（合同检查项 V01 的 timeout 是 2400s）。
PIPELINE_BUDGET = 2100
STEP_CAPS = {
    "npm ci": 1200,
    "npm run build": 600,
    "npm test": 600,
    "npm run check:contract": 120,
    "probe": 420,
}


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def need_file(rel):
    """断言仓库里的文件存在，返回路径。基线上到这里就以断言失败。"""
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return path


def need_dir(rel):
    path = REPO_ROOT / rel
    assert path.is_dir(), f"{rel} 不存在"
    return path


def sha256_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file_digest(path):
    path = Path(path)
    return sha256_of(path) if path.is_file() else None


def git(*args, check=False):
    proc = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, timeout=120)
    if check:
        assert proc.returncode == 0, f"git {' '.join(args)} 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return proc


def git_status_set():
    proc = git("status", "--porcelain=v1", "--untracked-files=all", "-z", check=True)
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


def tail_text(text, max_chars=3500, max_lines=45):
    text = _ANSI.sub("", text)
    lines = text.splitlines()[-max_lines:]
    joined = "\n".join(lines)
    return joined[-max_chars:]


def network_hint(text):
    if re.search(r"ENOTFOUND|ETIMEDOUT|ECONNRESET|ECONNREFUSED|EAI_AGAIN|ENETUNREACH|network|socket hang up|E40[134]|E50\d",
                 text, re.I):
        return "（输出里有网络或 registry 错误的迹象，多半是网络故障，不是代码问题）"
    return ""


def norm_ws(value):
    return re.sub(r"\s+", " ", value.strip())


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def font_path(name):
    path = FONTS_DIR / name
    assert path.is_file(), f"desktop/web/fonts/{name} 不存在（字体文件只读，不应缺失）"
    return path


# ---------------------------------------------------------------------------
# CSS 小解析器：@font-face 与声明
# ---------------------------------------------------------------------------

def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


FONT_FACE = re.compile(r"@font-face\s*\{([^{}]*)\}", re.I)
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def split_decls(body):
    """把声明块按分号切开（引号和括号里的分号不算），返回 [(小写名, 值)]。"""
    parts, buf, depth, quote = [], [], 0, None
    for ch in body:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append("".join(buf))
    decls = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        name, _sep, value = part.partition(":")
        decls.append((name.strip().lower(), value.strip()))
    return decls


def parse_font_faces(css):
    """返回 ([[(名, 值), …] 每条 @font-face 一组], 去掉注释与 @font-face 之后剩下的文本)。"""
    css = strip_comments(css)
    faces = [split_decls(body) for body in FONT_FACE.findall(css)]
    return faces, FONT_FACE.sub("", css).strip()


def decl_map(decls, label, problems):
    out = {}
    for name, value in decls:
        if name in out:
            problems.append(f"{label}：重复声明 {name}")
        out[name] = value
    return out


SRC_RE = re.compile(r"url\(\s*([\"']?)([^\"')]*)\1\s*\)\s*format\(\s*([\"']?)([\w-]+)\3\s*\)")


def parse_src(value):
    """``url(…) format("woff2")`` → (地址, 格式)；写成别的样子返回 None。"""
    m = SRC_RE.fullmatch(norm_ws(value))
    return (m.group(2).strip(), m.group(4)) if m else None


def has_scheme_or_absolute(url):
    return bool(re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", url)) or url.startswith(("/", "\\"))


def token_values(tokens_css):
    """tokens.css 里每个 --tt-* 第一次出现的取值。"""
    out = {}
    for name, value in re.findall(r"(--tt-[\w-]+)\s*:\s*([^;]+);", strip_comments(tokens_css)):
        out.setdefault(name, norm_ws(value))
    return out


def tokens_font_family(tokens_css):
    """--tt-font-sans 字体栈的首项（去引号）。"""
    value = token_values(tokens_css).get("--tt-font-sans", "")
    m = re.match(r"(\"[^\"]*\"|'[^']*'|[^,]+),", value)
    assert m, f"tokens.css 里找不到 --tt-font-sans 的字体栈首项：{value!r}"
    return unquote(m.group(1))


# ---------------------------------------------------------------------------
# 源码侧的检查函数（返回问题列表；空表示通过）
# ---------------------------------------------------------------------------

def font_face_problems(css, token_family):
    """fonts.css：恰两条 @font-face，族名、字重区间、font-display、src 照合同第 1 条。"""
    problems = []
    faces, rest = parse_font_faces(css)
    if rest:
        problems.append(f"除注释和 @font-face 之外还有内容：{rest[:80]!r}")
    if len(faces) != 2:
        problems.append(f"应恰有 2 条 @font-face，实际 {len(faces)}")
    lowered = strip_comments(css).lower()
    for bad in ("local(", "unicode-range"):
        if bad in lowered:
            problems.append(f"fonts.css 不应出现 {bad}")
    if token_family != FAMILY:
        problems.append(f"令牌字体栈首项应为 {FAMILY!r}，实际 {token_family!r}")
    seen = set()
    for index, decls in enumerate(faces, start=1):
        label = f"第 {index} 条 @font-face"
        d = decl_map(decls, label, problems)
        family = norm_ws(unquote(d.get("font-family", "")))
        if family != token_family:
            problems.append(f"{label}：font-family 应等于令牌字体栈首项 {token_family!r}，实际 {family!r}")
        weight = norm_ws(d.get("font-weight", ""))
        if weight not in FACE_WEIGHTS:
            problems.append(f"{label}：font-weight 应是 {sorted(FACE_WEIGHTS)} 之一，实际 {weight!r}")
            continue
        if weight in seen:
            problems.append(f"{label}：字重区间 {weight} 重复")
        seen.add(weight)
        if norm_ws(d.get("font-display", "")) != "swap":
            problems.append(f"{label}：font-display 应为 swap，实际 {d.get('font-display')!r}")
        if norm_ws(d.get("font-style", "normal")) != "normal":
            problems.append(f"{label}：font-style 写了就只能是 normal，实际 {d.get('font-style')!r}")
        src = parse_src(d.get("src", ""))
        if src is None:
            problems.append(f'{label}：src 应恰为一个 url(…) 加 format("woff2")，实际 {d.get("src")!r}')
            continue
        url, fmt = src
        if fmt != "woff2":
            problems.append(f"{label}：format 应为 woff2，实际 {fmt!r}")
        if has_scheme_or_absolute(url) or "?" in url or "#" in url:
            problems.append(f"{label}：src 应是不带协议、开头斜杠、查询串和片段的相对路径，实际 {url!r}")
        else:
            resolved = posixpath.normpath(posixpath.join("src/styles", url))
            expected = f"fonts/{FACE_WEIGHTS[weight]}"
            if resolved != expected:
                problems.append(f"{label}：字重 {weight} 的 src 从 src/styles/ 解析后应是 {expected}，实际 {resolved}（{url!r}）")
    if seen != set(FACE_WEIGHTS):
        problems.append(f"@font-face 应覆盖字重区间 {sorted(FACE_WEIGHTS)}，实际 {sorted(seen)}")
    return problems


def notices_problems(text, ofl_text):
    """notices：只断言“包含”（合同第 4 条）。"""
    flat = re.sub(r"\s+", " ", text)
    needles = [
        "Lucide", "1.59.0", "ISC",
        "Sarasa Gothic", "更纱黑体", "Sarasa Mono SC", "Regular", "SemiBold",
        "0.36.0", "SIL Open Font License 1.1",
        "github.com/be5invis/Sarasa-Gothic", "sarasa-gothic-ttf-0.36.0.7z",
        "sarasa-mono-sc-regular.woff2", "sarasa-mono-sc-semibold.woff2",
        "wawoff2", "2.0.1", "fonts/SOURCE.md",
        "public/licenses/OFL.txt",
    ]
    problems = [f"notices 里没有 {needle!r}" for needle in needles if needle not in flat]
    copyright_lines = [re.sub(r"\s+", " ", ln.strip()) for ln in ofl_text.splitlines()[:4]]
    for line in copyright_lines:
        if line and line not in flat:
            problems.append(f"notices 没有照抄 OFL.txt 的版权声明行：{line!r}")
    tables = re.findall(r"^\|[\s:|-]*-{3,}[\s:|-]*\|?\s*$", text, re.M)
    if len(tables) < 2:
        problems.append(f"notices 应有 Lucide 与 Sarasa Gothic 各一张表，表头分隔行只有 {len(tables)} 个")
    return problems


def notice_link_problems(text, base_dir):
    """notices 里每个相对链接都能从 notices 所在目录解析到文件；Lucide 许可的链接目标是 public/licenses/…。"""
    problems = []
    targets = [m.strip() for m in re.findall(r"\]\(\s*<?([^)\s>]+)>?[^)]*\)", text)]
    if LUCIDE_LICENSE_LINK not in targets:
        problems.append(f"没有指向 {LUCIDE_LICENSE_LINK} 的链接（Lucide 许可原文的链接目标应改成它）；现有链接：{targets}")
    for target in targets:
        if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
            continue
        path = url_unquote(re.split(r"[#?]", target, maxsplit=1)[0])
        if path and not (Path(base_dir) / path).is_file():
            problems.append(f"链接目标 {target!r} 从 {base_dir} 解析不到文件")
    return problems


WEIGHT_ATTR = re.compile(r"""\[\s*data-font-weight\s*=\s*["']?(\d+)["']?\s*\]""")


def weight_rule_problems(app_css, tokens_css):
    """App.css：按 [data-font-weight="…"] 选中的规则用 font: var(令牌)，令牌的字重与组一致。"""
    problems = []
    tokens = token_values(tokens_css)
    rules = RULE.findall(strip_comments(app_css))
    for weight, token in SPECIMEN_TOKENS.items():
        fonts = []
        for selector, body in rules:
            if not any(WEIGHT_ATTR.findall(part) == [weight] for part in selector.split(",")):
                continue
            for name, value in split_decls(body):
                if name == "font":
                    fonts.append(re.sub(r"\s+", "", value))
                elif name in ("font-weight", "font-family"):
                    problems.append(f'[data-font-weight="{weight}"] 的规则里不应单独写 {name}（字重和字体都取自令牌）')
        if not fonts:
            problems.append(f'App.css 里没有按 [data-font-weight="{weight}"] 选中、并用 font: var({token}) 的规则')
        for value in fonts:
            if value != f"var({token})":
                problems.append(f'[data-font-weight="{weight}"] 的 font 应为 var({token})，实际 {value}')
        resolved = tokens.get(token, "")
        m = re.match(r"(\d+)\s", resolved)
        if not m or m.group(1) != weight:
            problems.append(f"tokens.css 里 {token} 的字重应为 {weight}，实际 {resolved!r}")
    return problems


def row_style_problems(app_css):
    """App.css：样张行的样式（white-space: pre、font-variant-ligatures: none、不设 letter-spacing、外框与底色取令牌）。"""
    css = strip_comments(app_css)
    decls = [d for _sel, body in RULE.findall(css) for d in split_decls(body)]
    problems = []
    if not any(n == "white-space" and norm_ws(v) == "pre" for n, v in decls):
        problems.append("没有 white-space: pre 的声明")
    if not any(n == "font-variant-ligatures" and norm_ws(v) == "none" for n, v in decls):
        problems.append("没有 font-variant-ligatures: none 的声明（font 简写会把它重置为 normal）")
    if any(n == "letter-spacing" for n, _v in decls):
        problems.append("App.css 里不应设 letter-spacing")
    if not any(n == "border" and norm_ws(v) == "1px solid var(--tt-border)" for n, v in decls):
        problems.append("没有 border: 1px solid var(--tt-border) 的声明")
    if not any(n in ("background", "background-color") and norm_ws(v) == "var(--tt-surface-1)" for n, v in decls):
        problems.append("没有底色 var(--tt-surface-1) 的声明")
    return problems


# ---------------------------------------------------------------------------
# 产物侧的检查函数（输入 dist 目录；返回问题列表）
# ---------------------------------------------------------------------------

def dist_files(dist):
    return sorted(p for p in Path(dist).rglob("*") if p.is_file())


def dist_woff2_problems(dist):
    """恰两个 woff2，都在 assets/ 下，sha256 的多重集合等于 fonts/ 两个文件的。"""
    dist = Path(dist)
    problems = []
    found = [p for p in dist_files(dist) if p.suffix.lower() == ".woff2"]
    if len(found) != 2:
        problems.append(f"dist 里应恰有 2 个 .woff2，实际 {len(found)}：{[str(p.relative_to(dist)) for p in found]}")
    expected = sorted(sha256_of(font_path(n)) for n in (FONT_REGULAR, FONT_SEMIBOLD))
    got = sorted(sha256_of(p) for p in found)
    if got != expected:
        problems.append(f"dist 里 woff2 的 sha256 与 fonts/ 不同：期望 {expected}，实际 {got}")
    for p in found:
        if p.parent != dist / "assets":
            problems.append(f"{p.relative_to(dist)} 不在 dist/assets/ 下")
    return problems


def dist_other_font_problems(dist):
    """没有 .woff、.ttf、.otf、.eot、.ttc、.otc；除 .woff2 外没有文件以字体签名开头。"""
    dist = Path(dist)
    problems = []
    for p in dist_files(dist):
        rel = p.relative_to(dist)
        if p.suffix.lower() in FONT_SUFFIXES - {".woff2"}:
            problems.append(f"{rel}：不该有的字体文件")
        elif p.suffix.lower() != ".woff2":
            with p.open("rb") as handle:
                head = handle.read(4)
            if head in FONT_SIGNATURES:
                problems.append(f"{rel}：文件以字体签名 {head!r} 开头")
    return problems


def dist_font_face_problems(dist):
    """dist CSS 恰两条 @font-face：族名、字重区间、font-display 同源码；src 是 ./ 开头的相对地址，指向 dist 里字节相同的 woff2。"""
    dist = Path(dist).resolve()
    problems = []
    faces = []
    for css_path in sorted(dist.rglob("*.css")):
        parsed, _rest = parse_font_faces(_read(css_path))
        faces.extend((css_path, decls) for decls in parsed)
    if len(faces) != 2:
        problems.append(f"dist 的 CSS 里应恰有 2 条 @font-face，实际 {len(faces)}")
    seen = set()
    for index, (css_path, decls) in enumerate(faces, start=1):
        label = f"dist 的第 {index} 条 @font-face（{css_path.name}）"
        d = decl_map(decls, label, problems)
        family = norm_ws(unquote(d.get("font-family", "")))
        if family != FAMILY:
            problems.append(f"{label}：font-family 应为 {FAMILY!r}，实际 {family!r}")
        weight = norm_ws(d.get("font-weight", ""))
        if weight not in FACE_WEIGHTS:
            problems.append(f"{label}：font-weight 应是 {sorted(FACE_WEIGHTS)} 之一，实际 {weight!r}")
            continue
        seen.add(weight)
        if norm_ws(d.get("font-display", "")) != "swap":
            problems.append(f"{label}：font-display 应为 swap，实际 {d.get('font-display')!r}")
        if norm_ws(d.get("font-style", "normal")) != "normal":
            problems.append(f"{label}：font-style 写了就只能是 normal，实际 {d.get('font-style')!r}")
        src = parse_src(d.get("src", ""))
        if src is None:
            problems.append(f'{label}：src 应恰为一个 url(…) 加 format("woff2")，实际 {d.get("src")!r}')
            continue
        url, fmt = src
        if fmt != "woff2":
            problems.append(f"{label}：format 应为 woff2，实际 {fmt!r}")
        if has_scheme_or_absolute(url) or not url.startswith("./"):
            problems.append(f"{label}：src 应是 ./ 开头的相对地址（不内联、不用外部地址），实际 {url[:80]!r}")
            continue
        target = (css_path.parent / url_unquote(url)).resolve()
        try:
            target.relative_to(dist)
        except ValueError:
            problems.append(f"{label}：src {url!r} 解析到 dist 之外")
            continue
        if not target.is_file():
            problems.append(f"{label}：src {url!r} 指向的文件不存在")
        elif sha256_of(target) != sha256_of(font_path(FACE_WEIGHTS[weight])):
            problems.append(f"{label}：字重 {weight} 的 src 指向的文件与 fonts/{FACE_WEIGHTS[weight]} 字节不同")
    if faces and seen != set(FACE_WEIGHTS):
        problems.append(f"dist 的 @font-face 应覆盖字重区间 {sorted(FACE_WEIGHTS)}，实际 {sorted(seen)}")
    return problems


REMOTE_FONT_URL = re.compile(r"""(?:https?:)?//[^\s"'()<>]*\.(?:woff2?|ttf|otf|eot)\b""", re.I)
INLINE_FONT = re.compile(r"data:(?:font/|application/(?:font|x-font|vnd\.ms-fontobject))", re.I)
FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")


def dist_remote_problems(dist):
    """dist 的 CSS、JS、HTML 里没有内联字体和外部字体地址；只查字体相关的（React 产物里本来就有 https://reactjs.org/…）。"""
    dist = Path(dist)
    problems = []
    for p in dist_files(dist):
        if p.suffix.lower() not in (".css", ".js", ".mjs", ".html", ".htm"):
            continue
        rel = p.relative_to(dist)
        text = p.read_bytes().decode("utf-8", "replace")
        if INLINE_FONT.search(text):
            problems.append(f"{rel}：内联了字体（data: URI）")
        for host in FONT_HOSTS:
            if host in text:
                problems.append(f"{rel}：引用了 {host}")
        for m in REMOTE_FONT_URL.finditer(text):
            problems.append(f"{rel}：指向外部的字体地址 {m.group(0)[:100]}")
        for block in FONT_FACE.findall(text):
            if "data:" in block.lower() or re.search(r"(?:https?:)?//", block):
                problems.append(f"{rel}：@font-face 里有 data: 或外部地址：{block[:100]!r}")
    return problems


def dist_license_problems(dist, public_copy):
    """dist/licenses/OFL.txt 与 public 里的副本逐字节相同。"""
    dist_copy = Path(dist) / "licenses" / "OFL.txt"
    if not dist_copy.is_file():
        return ["dist/licenses/OFL.txt 不存在（public/licenses/OFL.txt 应随产物发出）"]
    if not Path(public_copy).is_file():
        return [f"{public_copy} 不存在"]
    if Path(dist_copy).read_bytes() != Path(public_copy).read_bytes():
        return ["dist/licenses/OFL.txt 与 public/licenses/OFL.txt 字节不同"]
    return []


# ---------------------------------------------------------------------------
# 会话级夹具：四步 npm + 样张探针
# ---------------------------------------------------------------------------

class Step:
    def __init__(self, name, argv, code, timed_out, out, seconds):
        self.name = name
        self.argv = argv
        self.code = code
        self.timed_out = timed_out
        self.out = _ANSI.sub("", out)
        self.seconds = seconds

    @property
    def tail(self):
        return tail_text(self.out)


class Pipeline:
    def __init__(self):
        self.ran = False
        self.reason = ""
        self.steps = {}
        self.status_before = None
        self.status_after = None
        self.digests_before = {}
        self.digests_after = {}
        self.stopped_reason = ""
        self.probe_file = None
        self.gate_probe_left = None


def _kill_tree(proc):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=60)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        proc.kill()


def run_capture(argv, cwd, timeout, env):
    """跑一条命令，合并 stdout/stderr；超时时连子进程一起杀掉。不用 shell。"""
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    start = time.monotonic()
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode, False, out.decode("utf-8", "replace"), time.monotonic() - start
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            out, _ = proc.communicate(timeout=30)
        except Exception:
            out = b""
        return None, True, out.decode("utf-8", "replace"), time.monotonic() - start


# 样张探针：只核对结构与列数。jsdom 不加载字体也不排版，像素对齐留给人（H1）。
PROBE_SOURCE = r"""
import * as React from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(() => {
  cleanup();
});

const TITLE = '字体 · 等距更纱黑体 SC';
const CJK = /[一-鿿]/;

function isCjk(cp: number): boolean {
  return cp >= 0x4e00 && cp <= 0x9fff;
}
function badChars(text: string): string[] {
  const bad: string[] = [];
  for (const ch of Array.from(text)) {
    const cp = ch.codePointAt(0) as number;
    if (!(isCjk(cp) || (cp >= 0x20 && cp <= 0x7e))) {
      bad.push('U+' + cp.toString(16).toUpperCase().padStart(4, '0'));
    }
  }
  return bad;
}
function columns(text: string): number {
  let n = 0;
  for (const ch of Array.from(text)) {
    n += isCjk(ch.codePointAt(0) as number) ? 2 : 1;
  }
  return n;
}
function textOf(el: Element): string {
  return (el.textContent || '').replace(/\s+/g, ' ').trim();
}

async function mountApp() {
  const mod: any = await import('../src/App');
  const AppComponent = mod.default ?? mod.App;
  expect(AppComponent).toBeTruthy();
  return render(<AppComponent />);
}
async function specimen(): Promise<HTMLElement> {
  await mountApp();
  const roots = document.querySelectorAll('[data-font-specimen]');
  expect(roots.length, '陈列页应恰有一个带 data-font-specimen 的样张节').toBe(1);
  return roots[0] as HTMLElement;
}
function groupsOf(root: HTMLElement): Array<[string, HTMLElement]> {
  return Array.from(root.querySelectorAll('[data-font-weight]')).map(
    (el) => [el.getAttribute('data-font-weight') || '', el as HTMLElement] as [string, HTMLElement],
  );
}
function rowsOf(group: HTMLElement): string[] {
  return Array.from(group.querySelectorAll('[data-specimen-row]')).map((el) => el.textContent || '');
}
function innerOf(row: string): string {
  return row.replace(/^\|/, '').replace(/\|$/, '');
}

describe('字体样张（陈列页）', () => {
  it('样张节恰有一个，标题是「字体 · 等距更纱黑体 SC」', async () => {
    const root = await specimen();
    const h2 = root.querySelector('.showcase__h2');
    expect(h2, '样张节里应有 showcase__h2 标题').not.toBeNull();
    expect(textOf(h2 as Element)).toBe(TITLE);
  });

  it('400、500、600 三个字重组各一个，组旁有 showcase__label 说明', async () => {
    const root = await specimen();
    const weights = groupsOf(root).map(([w]) => w).sort();
    expect(weights).toEqual(['400', '500', '600']);
    const labels = Array.from(root.querySelectorAll('.showcase__label')).map(textOf);
    for (const label of ['Regular 400', '500 按 Regular', 'SemiBold 600']) {
      expect(labels, 'showcase__label 里缺「' + label + '」').toContain(label);
    }
  });

  it('每组至少两行，有纯汉字行和纯 ASCII 行，行都在组里', async () => {
    const root = await specimen();
    let inGroups = 0;
    for (const [weight, group] of groupsOf(root)) {
      const rows = rowsOf(group);
      inGroups += rows.length;
      expect(rows.length, weight + ' 组应至少两行').toBeGreaterThanOrEqual(2);
      const inner = rows.map(innerOf);
      const hanzi = inner.filter(
        (t) => (t.match(/[一-鿿]/g) || []).length >= 6 && !/[A-Za-z0-9]/.test(t),
      );
      const ascii = inner.filter((t) => !CJK.test(t) && /[A-Za-z0-9]/.test(t));
      expect(hanzi.length, weight + ' 组应有纯汉字行（至少 6 个汉字、没有 ASCII 字母数字）').toBeGreaterThanOrEqual(1);
      expect(ascii.length, weight + ' 组应有纯 ASCII 行（没有汉字）').toBeGreaterThanOrEqual(1);
    }
    expect(root.querySelectorAll('[data-specimen-row]').length, '带 data-specimen-row 的行都应在字重组里').toBe(inGroups);
  });

  it('每行首尾各有一个 | 对齐标记，每组各行列数相同（汉字 2 列，ASCII 1 列）', async () => {
    const root = await specimen();
    const groups = groupsOf(root);
    expect(groups.length).toBeGreaterThan(0);
    for (const [weight, group] of groups) {
      const rows = rowsOf(group);
      expect(rows.length, weight + ' 组没有行').toBeGreaterThan(0);
      for (const row of rows) {
        expect(row.length, weight + ' 组有行太短：' + JSON.stringify(row)).toBeGreaterThanOrEqual(3);
        expect(row.startsWith('|') && row.endsWith('|'), weight + ' 组的行首尾应各有一个 |：' + JSON.stringify(row)).toBe(true);
        expect(innerOf(row).includes('|'), weight + ' 组的行中间不应再有 |：' + JSON.stringify(row)).toBe(false);
      }
      const widths = rows.map(columns);
      expect(
        new Set(widths).size,
        weight + ' 组各行列数应相同，实际 ' + JSON.stringify(widths) + '：' + JSON.stringify(rows),
      ).toBe(1);
    }
  });

  it('样张文字只用 CJK 统一表意文字与可打印 ASCII，避开 #、->、=>', async () => {
    const root = await specimen();
    const problems: string[] = [];
    for (const [weight, group] of groupsOf(root)) {
      for (const row of rowsOf(group)) {
        const bad = badChars(row);
        if (bad.length > 0) {
          problems.push(weight + ' ' + JSON.stringify(row) + ' 含不允许的字符 ' + bad.join(','));
        }
        for (const banned of ['#', '->', '=>']) {
          if (row.includes(banned)) {
            problems.push(weight + ' ' + JSON.stringify(row) + ' 含 ' + banned);
          }
        }
      }
    }
    expect(problems).toEqual([]);
  });

  it('样张里没有按钮或别的可交互元素', async () => {
    const root = await specimen();
    const hits = root.querySelectorAll('button, a, input, select, textarea, [tabindex], [role="button"]');
    expect(hits.length, '样张里不该有可交互元素').toBe(0);
  });

  it('样张在页头之后、Button 一节之前', async () => {
    const root = await specimen();
    const head = document.querySelector('.showcase__head');
    expect(head, '找不到页头 .showcase__head').not.toBeNull();
    expect(head!.compareDocumentPosition(root) & Node.DOCUMENT_POSITION_FOLLOWING, '样张应在页头之后').toBeTruthy();
    const buttonH2 = Array.from(document.querySelectorAll('.showcase__h2')).find((h) => /Button/.test(textOf(h)));
    expect(buttonH2, '找不到 Button 一节的标题').toBeTruthy();
    expect(root.compareDocumentPosition(buttonH2 as Element) & Node.DOCUMENT_POSITION_FOLLOWING, '样张应在 Button 一节之前').toBeTruthy();
  });
});
"""

PROBE_TEST_COUNT = len(re.findall(r"^\s*it\(", PROBE_SOURCE, re.M))


def _make_env():
    env = dict(os.environ)
    env.update({
        "CI": "true",
        "NO_COLOR": "1",
        "npm_config_fund": "false",
        "npm_config_audit": "false",
        "npm_config_update_notifier": "false",
    })
    env.pop("FORCE_COLOR", None)
    return env


# 流水线前后不该变的文件（相对 desktop/web）
WATCHED = ("package.json", "package-lock.json", "src/styles/tokens.css", "fonts/OFL.txt", "fonts/SOURCE.md",
           f"fonts/{FONT_REGULAR}", f"fonts/{FONT_SEMIBOLD}")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        pipe.reason = f"找不到 npm 或 node（shutil.which：npm={npm}，node={node}）"
        return pipe
    pipe.ran = True
    env = _make_env()
    deadline = time.monotonic() + PIPELINE_BUDGET
    pipe.status_before = git_status_set()
    pipe.digests_before = {name: file_digest(WEB / name) for name in WATCHED}

    def run_step(name, argv):
        remaining = deadline - time.monotonic()
        if remaining <= 5:
            pipe.stopped_reason = f"{name} 之前整体预算 {PIPELINE_BUDGET}s 已用完，未运行"
            return None
        timeout = min(STEP_CAPS[name], remaining)
        code, timed_out, out, seconds = run_capture(argv, WEB, timeout, env)
        step = Step(name, argv, code, timed_out, out, seconds)
        pipe.steps[name] = step
        return step

    probe_dir = WEB / "gate-probe"
    probe_path = None
    try:
        ci = run_step("npm ci", [npm, "ci"])
        if ci is not None and ci.code == 0:
            run_step("npm run build", [npm, "run", "build"])
            run_step("npm test", [npm, "test"])
            run_step("npm run check:contract", [npm, "run", "check:contract"])
            probe_name = f"probe-{uuid.uuid4().hex[:12]}.test.tsx"
            probe_path = probe_dir / probe_name
            probe_dir.mkdir(exist_ok=True)
            probe_path.write_text(PROBE_SOURCE, encoding="utf-8", newline="\n")
            pipe.probe_file = probe_name
            run_step("probe", [npm, "test", "--", f"gate-probe/{probe_name}"])
        elif ci is not None:
            pipe.stopped_reason = "npm ci 失败，后续步骤未运行"
    finally:
        if probe_path is not None:
            try:
                probe_path.unlink()
            except FileNotFoundError:
                pass
        try:
            probe_dir.rmdir()
        except OSError:
            pass
        pipe.gate_probe_left = probe_dir.exists()
        pipe.status_after = git_status_set()
        pipe.digests_after = {name: file_digest(WEB / name) for name in WATCHED}
    return pipe


def assert_step_ok(pipe, name):
    assert pipe.ran, pipe.reason
    step = pipe.steps.get(name)
    assert step is not None, f"{name} 未运行：{pipe.stopped_reason or '前置步骤失败'}"
    assert step.code == 0, (
        f"{name} 退出码 {step.code}{'（超时被杀）' if step.timed_out else ''}，用时 {step.seconds:.0f}s"
        f"{network_hint(step.out)}\n--- 输出尾部 ---\n{step.tail}")
    return step


def need_build(pipe):
    assert_step_ok(pipe, "npm run build")
    dist = WEB / "dist"
    assert (dist / "index.html").is_file(), "npm run build 之后没有 desktop/web/dist/index.html"
    return dist


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:30])


# ---------------------------------------------------------------------------
# S 系列：静态断言（D01、D03、D06）
# ---------------------------------------------------------------------------

def test_d01_fonts_css_two_font_faces():
    """S1 / D01：fonts.css 恰两条 @font-face（没有别的规则），族名等于 tokens.css 里 --tt-font-sans 的首项，
    字重区间 300 500 与 600 800，font-display: swap，src 是 url(相对路径) 加 format("woff2") 且分别指向两个随包 woff2，
    不写 local() 与 unicode-range。"""
    css = _read(need_file(f"{WEB_REL}/src/styles/fonts.css"))
    family = tokens_font_family(_read(need_file(f"{WEB_REL}/src/styles/tokens.css")))
    fail_if(font_face_problems(css, family), "src/styles/fonts.css 不符合合同第 1 条")


def test_d01_main_imports_fonts_css():
    """S2 / D01：main.tsx 引入 ./styles/fonts.css，并且在 ./styles/tokens.css 之前（合同第 2 条）。"""
    text = _read(need_file(f"{WEB_REL}/src/main.tsx"))
    fonts = re.search(r"""^\s*import\s+['"]\./styles/fonts\.css['"]""", text, re.M)
    tokens = re.search(r"""^\s*import\s+['"]\./styles/tokens\.css['"]""", text, re.M)
    assert fonts, "src/main.tsx 没有 import './styles/fonts.css'"
    assert tokens, "src/main.tsx 没有 import './styles/tokens.css'"
    assert fonts.start() < tokens.start(), "fonts.css 应在 tokens.css 之前引入"


def test_d01_fonts_only_via_fonts_css():
    """S3 / D01、D02（守卫）：src 和 public 里没有字体文件；除 fonts.css 外，src 的 ts、tsx、css、html 里不引用字体文件
    （.woff2 等扩展名、sarasa-mono-sc- 文件名），没有别处的 @font-face，也不用 FontFace API。"""
    src = need_dir(f"{WEB_REL}/src")
    public = need_dir(f"{WEB_REL}/public")
    fonts_css = src / "styles" / "fonts.css"
    problems = []
    for root in (src, public):
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in FONT_SUFFIXES:
                problems.append(f"{path.relative_to(WEB)}：字体文件不该放进 src 或 public")
    patterns = {
        "字体文件的扩展名": re.compile(r"\.(?:woff2?|ttf|otf|eot|ttc|otc)\b", re.I),
        "随包字体的文件名": re.compile(r"sarasa-mono-sc-", re.I),
        "@font-face": re.compile(r"@font-face", re.I),
        "FontFace API": re.compile(r"\bFontFace\b|document\.fonts"),
    }
    for path in sorted(src.rglob("*")):
        if (not path.is_file() or path == fonts_css or ".test." in path.name
                or path.suffix.lower() not in (".ts", ".tsx", ".js", ".jsx", ".css", ".html")):
            continue
        text = _read(path)
        for label, pattern in patterns.items():
            if pattern.search(text):
                problems.append(f"{path.relative_to(WEB)}：出现 {label}（字体只经 src/styles/fonts.css 引用）")
    fail_if(problems, "字体引用不只在 fonts.css")


def test_d06_font_sources_match_source_md():
    """S4 / D06（守卫）：两个 woff2 的字节数与 sha256 等于 SOURCE.md 表格里写的（从 SOURCE.md 解析，不写死）；
    OFL.txt 行尾归一成 LF 后的字节数等于 SOURCE.md 写的 4,708。字体文件只读。"""
    source = _read(need_file(f"{WEB_REL}/fonts/SOURCE.md"))
    rows = re.findall(r"\|\s*`(sarasa-mono-sc-(?:regular|semibold)\.woff2)`\s*\|\s*([\d,]+)\s*\|\s*`([0-9a-f]{64})`\s*\|", source)
    assert sorted(r[0] for r in rows) == sorted([FONT_REGULAR, FONT_SEMIBOLD]), f"SOURCE.md 的 woff2 表格解析异常：{rows}"
    problems = []
    for name, size, digest in rows:
        path = font_path(name)
        if path.stat().st_size != int(size.replace(",", "")):
            problems.append(f"{name} 字节数 {path.stat().st_size} 与 SOURCE.md 的 {size} 不同")
        if sha256_of(path) != digest:
            problems.append(f"{name} 的 sha256 与 SOURCE.md 的 {digest} 不同")
    m = re.search(r"`LICENSE`（([\d,]+) 字节）", source)
    assert m, "SOURCE.md 里找不到 OFL 原文的字节数（形如 `LICENSE`（4,708 字节））"
    ofl = need_file(f"{WEB_REL}/fonts/OFL.txt")
    ofl_size = len(ofl.read_bytes().replace(b"\r\n", b"\n"))
    if ofl_size != int(m.group(1).replace(",", "")):
        problems.append(f"OFL.txt 行尾归一后 {ofl_size} 字节，SOURCE.md 写的是 {m.group(1)}")
    fail_if(problems, "fonts/ 与 SOURCE.md 不一致")


def test_d03_ofl_copy_in_public_licenses():
    """S5 / D03：public/licenses/OFL.txt 存在，行尾归一后与 fonts/OFL.txt 内容相同（含 4 行版权声明）。"""
    copy = _read(need_file(OFL_COPY_REL))
    original = _read(need_file(f"{WEB_REL}/fonts/OFL.txt"))
    assert copy == original, "public/licenses/OFL.txt 与 fonts/OFL.txt 内容不同（行尾归一后比较）"
    assert copy.startswith("Copyright (c) 2015-2022, Renzhi Li"), "许可副本应以版权声明开头"


def test_d03_notices_record_sarasa_and_lucide():
    """S6 / D03：THIRD_PARTY_NOTICES.md 记了 Sarasa Gothic 的名称、用到的字体、版本 0.36.0、SIL Open Font License 1.1、
    来源、随包文件与转换、版权声明（照抄 OFL.txt 前 4 行）、许可原文路径，Lucide 条目仍在，两节各一张表。只断言“包含”。"""
    notices = _read(need_file(f"{WEB_REL}/THIRD_PARTY_NOTICES.md"))
    ofl = _read(need_file(f"{WEB_REL}/fonts/OFL.txt"))
    fail_if(notices_problems(notices, ofl), "THIRD_PARTY_NOTICES.md 缺内容")


def test_d03_notices_license_links_resolve():
    """S7 / D03：notices 里的相对链接从 notices 所在目录（desktop/web/）都能解析到文件，
    Lucide 许可原文的链接目标是 public/licenses/lucide-1.59.0-LICENSE.txt（合同第 4 条）。"""
    path = need_file(f"{WEB_REL}/THIRD_PARTY_NOTICES.md")
    fail_if(notice_link_problems(_read(path), path.parent), "THIRD_PARTY_NOTICES.md 的许可链接")


def test_transitional_d04_specimen_font_weights():
    """应用框架那一片（T002 规划里的第 3 片"应用框架与夹具数据层"）把陈列页移出根路由时推翻。

    S8 / D04：App.css 里按 [data-font-weight="400"]、"500"、"600" 选中的规则用 font: var(--tt-text-md)、
    var(--tt-text-md-medium)、var(--tt-title-sm)，三个令牌在 tokens.css 里的字重分别是 400、500、600；
    规则里不单独写 font-weight 或 font-family。"""
    app_css = _read(need_file(f"{WEB_REL}/src/App.css"))
    tokens = _read(need_file(f"{WEB_REL}/src/styles/tokens.css"))
    fail_if(weight_rule_problems(app_css, tokens), "App.css 的样张字重规则")


def test_transitional_d04_specimen_css_row_style():
    """应用框架那一片（T002 规划里的第 3 片"应用框架与夹具数据层"）把陈列页移出根路由时推翻。

    S9 / D04：App.css 有样张行的样式：white-space: pre、font-variant-ligatures: none、不设 letter-spacing，
    外框 border: 1px solid var(--tt-border)，底色 var(--tt-surface-1)（合同第 5 条）。
    选择器怎么写合同没定，这里只查整个 App.css 里有这些声明；对齐本身由 H1 人工看。"""
    app_css = _read(need_file(f"{WEB_REL}/src/App.css"))
    fail_if(row_style_problems(app_css), "App.css 的样张行样式")


# ---------------------------------------------------------------------------
# P 系列：流水线断言（D01、D02、D03、D04、D06）
# ---------------------------------------------------------------------------

def test_d02_pipeline_steps_pass(pipeline):
    """P1 / D02、D04（守卫）：npm ci、npm run build、npm test、npm run check:contract 都退出 0；
    npm test 有通过的用例，没有失败、跳过、待办。"""
    for name in ("npm ci", "npm run build", "npm test", "npm run check:contract"):
        assert_step_ok(pipeline, name)
    step = pipeline.steps["npm test"]
    out = step.out
    assert re.search(r"Tests\s+(?:.*\|\s*)?\d+ passed", out), f"npm test 输出里没有 'Tests … N passed'：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", out), f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert re.search(r"Test Files\s+\d+ passed", out) and not re.search(r"Test Files\s+.*\bfailed\b", out), \
        f"npm test 的 Test Files 行异常：\n{step.tail}"


def test_d02_dist_exactly_two_woff2_identical(pipeline):
    """P2 / D02：dist 下 *.woff2 恰两个（都在 assets/ 下），sha256 的多重集合等于 fonts/ 两个文件的（逐字节相同）。"""
    fail_if(dist_woff2_problems(need_build(pipeline)), "dist 里的 woff2")


def test_d02_dist_no_other_font_files(pipeline):
    """P3 / D02（守卫）：dist 里没有 .woff、.ttf、.otf、.eot、.ttc、.otc；除 .woff2 外没有文件以字体签名开头。"""
    fail_if(dist_other_font_problems(need_build(pipeline)), "dist 里多出的字体文件")


def test_d02_dist_font_faces_point_to_bundled_woff2(pipeline):
    """P4 / D01、D02：dist 的 CSS 恰两条 @font-face，族名、字重区间、font-display 同源码；src 是 ./ 开头的相对地址，
    按 CSS 所在目录解析后是 dist 里的 woff2：300 500 那条与 Regular 同字节，600 800 那条与 SemiBold 同字节。"""
    fail_if(dist_font_face_problems(need_build(pipeline)), "dist CSS 的 @font-face")


def test_d02_dist_no_inline_or_remote_fonts(pipeline):
    """P5 / D02（守卫）：dist 的 CSS、JS、HTML 里没有内联字体（data:font/ 等）、没有 fonts.googleapis.com 与 fonts.gstatic.com、
    没有指向外部的字体地址，@font-face 里没有 data: 或外部地址（CSP 是 font-src 'self'）。"""
    fail_if(dist_remote_problems(need_build(pipeline)), "dist 里的内联或外部字体")


def test_d03_dist_licenses_has_ofl(pipeline):
    """P6 / D03：dist/licenses/OFL.txt 与 public/licenses/OFL.txt 逐字节相同。"""
    dist = need_build(pipeline)
    fail_if(dist_license_problems(dist, REPO_ROOT / OFL_COPY_REL), "dist 里的 OFL 许可")


def test_d06_worktree_unchanged_by_pipeline(pipeline):
    """P7 / D06（守卫）：流水线与探针前后 git status 相同；package.json、锁文件、tokens.css、fonts/ 下的字体与
    OFL.txt、SOURCE.md 的摘要不变；gate-probe/ 没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"
    changed = sorted(n for n in WATCHED if pipeline.digests_before.get(n) != pipeline.digests_after.get(n))
    assert not changed, f"流水线改动了不该动的文件：{changed}"
    assert not pipeline.gate_probe_left, "desktop/web/gate-probe/ 在探针结束后没有清掉"


def test_transitional_d04_showcase_font_specimen(pipeline):
    """应用框架那一片（T002 规划里的第 3 片"应用框架与夹具数据层"）把陈列页移出根路由时推翻。

    P8 / D04：探针渲染 App：恰一个 [data-font-specimen] 节，标题与 showcase__label 正确；400、500、600 三个
    [data-font-weight] 组各一个；每组至少两行（[data-specimen-row]），有纯汉字行和纯 ASCII 行；每行首尾各一个 |；
    按“汉字 2 列、ASCII 1 列”每组各行列数相同；只用 CJK 统一表意文字与可打印 ASCII；样张里没有可交互元素；
    样张在页头之后、Button 一节之前。像素对齐 jsdom 看不了，留给人（H1）。"""
    assert pipeline.ran, pipeline.reason
    step = assert_step_ok(pipeline, "probe")
    assert pipeline.probe_file and pipeline.probe_file in step.out.replace("\\", "/"), \
        f"探针输出里没有探针文件名，可能没被 Vitest 选中：\n{step.tail}"
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m and int(m.group(1)) == PROBE_TEST_COUNT, f"探针应有 {PROBE_TEST_COUNT} 条通过：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), f"探针有失败或跳过：\n{step.tail}"


# ---------------------------------------------------------------------------
# 门禁自检（不依赖候选）：检查函数放得过合同写明的正确样本，拦得住常见错误
# ---------------------------------------------------------------------------

CONTRACT_FONTS_CSS = """/* 随包字体：等距更纱黑体 SC 0.36.0（Sarasa Mono SC，SIL OFL 1.1），来源与哈希见 desktop/web/fonts/SOURCE.md。
   族名与令牌 --tt-font-sans、--tt-font-mono 的首项一致。更纱没有 Medium：300–500 用 Regular，600–800 用 SemiBold。 */
@font-face {
  font-family: "TT Sarasa Mono SC";
  src: url("../../fonts/sarasa-mono-sc-regular.woff2") format("woff2");
  font-weight: 300 500;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "TT Sarasa Mono SC";
  src: url("../../fonts/sarasa-mono-sc-semibold.woff2") format("woff2");
  font-weight: 600 800;
  font-style: normal;
  font-display: swap;
}
"""

FONTS_CSS_BROKEN = {
    "字重区间改了": ("font-weight: 600 800", "font-weight: 600 700"),
    "font-display 改了": ("font-display: swap;\n}\n\n@font-face", "font-display: block;\n}\n\n@font-face"),
    "两个 url 对调": ("sarasa-mono-sc-regular.woff2", "sarasa-mono-sc-semibold.woff2"),
    "族名少一个字母": ('"TT Sarasa Mono SC";\n  src: url("../../fonts/sarasa-mono-sc-semibold', '"TT Sarasa Mono S";\n  src: url("../../fonts/sarasa-mono-sc-semibold'),
    "没有 format": (' format("woff2");\n  font-weight: 600 800', ';\n  font-weight: 600 800'),
    "加了 local()": ('src: url("../../fonts/sarasa-mono-sc-regular.woff2")', 'src: local("Sarasa Mono SC"), url("../../fonts/sarasa-mono-sc-regular.woff2")'),
    "加了 unicode-range": ("font-style: normal;\n  font-display: swap;\n}\n\n@font-face", "font-style: normal;\n  unicode-range: U+0020-007E;\n  font-display: swap;\n}\n\n@font-face"),
    "地址是绝对路径": ('url("../../fonts/sarasa-mono-sc-regular.woff2")', 'url("/fonts/sarasa-mono-sc-regular.woff2")'),
    "地址层数不对": ('url("../../fonts/sarasa-mono-sc-regular.woff2")', 'url("../fonts/sarasa-mono-sc-regular.woff2")'),
    "多了一条规则": ("@font-face {\n  font-family: \"TT Sarasa Mono SC\";\n  src: url(\"../../fonts/sarasa-mono-sc-regular", ".x { color: red; }\n@font-face {\n  font-family: \"TT Sarasa Mono SC\";\n  src: url(\"../../fonts/sarasa-mono-sc-regular"),
}


def test_gate_selfcheck_fonts_css():
    """门禁自检：合同给的 fonts.css 全文通过 S1 的检查；逐项改坏都被抓住。"""
    assert font_face_problems(CONTRACT_FONTS_CSS, FAMILY) == []
    # 注释里提令牌名、顺序对调、单引号与无引号的写法都不影响
    relaxed = CONTRACT_FONTS_CSS.replace('"', "'").replace("font-style: normal;\n  ", "")
    assert font_face_problems(relaxed, FAMILY) == []
    for name, (old, new) in FONTS_CSS_BROKEN.items():
        assert old in CONTRACT_FONTS_CSS, f"自检样本没有改坏的位置：{name}"
        assert font_face_problems(CONTRACT_FONTS_CSS.replace(old, new, 1), FAMILY), f"没抓住：{name}"
    assert font_face_problems("", FAMILY)


def test_gate_selfcheck_tokens_family():
    """门禁自检：从真实 tokens.css 解析出的字体栈首项是 TT Sarasa Mono SC，字体令牌的字重符合 S8 的预期。"""
    tokens = _read(need_file(f"{WEB_REL}/src/styles/tokens.css"))
    assert tokens_font_family(tokens) == FAMILY
    values = token_values(tokens)
    for token, weight in (("--tt-text-md", "400"), ("--tt-text-md-medium", "500"), ("--tt-title-sm", "600")):
        assert values[token].startswith(weight + " "), (token, values[token])


GOOD_APP_CSS = """
.showcase__label { font: var(--tt-text-caption-strong); }
/* 样张 */
[data-font-specimen] { border: 1px solid var(--tt-border); background: var(--tt-surface-1); }
[data-specimen-row] { white-space: pre; font-variant-ligatures: none; }
[data-font-weight="400"] [data-specimen-row] { font: var(--tt-text-md); font-variant-ligatures: none; }
[data-font-weight='500'] { font: var(--tt-text-md-medium); }
[data-font-weight=600] { font: var(--tt-title-sm); }
@media (max-width: 800px) {
  [data-font-specimen] { margin: 0; }
}
"""


def test_gate_selfcheck_app_css():
    """门禁自检：合同写明的样张样式通过 S8、S9 的检查，改坏的被抓住。"""
    tokens = _read(need_file(f"{WEB_REL}/src/styles/tokens.css"))
    assert weight_rule_problems(GOOD_APP_CSS, tokens) == []
    assert row_style_problems(GOOD_APP_CSS) == []
    broken_weight = {
        "600 组用了 md 令牌": GOOD_APP_CSS.replace("var(--tt-title-sm)", "var(--tt-text-md)"),
        "500 组用了 600 的令牌": GOOD_APP_CSS.replace("var(--tt-text-md-medium)", "var(--tt-title-sm)"),
        "400 组没有规则": GOOD_APP_CSS.replace('[data-font-weight="400"]', '[data-font-weighted="400"]'),
        "规则里单独写了 font-weight": GOOD_APP_CSS.replace("font: var(--tt-title-sm);", "font: var(--tt-title-sm); font-weight: 700;"),
        "没有 500 组": GOOD_APP_CSS.replace("[data-font-weight='500']", ".x"),
        "用了字面量": GOOD_APP_CSS.replace("font: var(--tt-title-sm);", "font: 600 14px/22px monospace;"),
    }
    for name, css in broken_weight.items():
        assert weight_rule_problems(css, tokens), f"没抓住：{name}"
    broken_style = {
        "没有 white-space": GOOD_APP_CSS.replace("white-space: pre;", ""),
        "pre-wrap": GOOD_APP_CSS.replace("white-space: pre;", "white-space: pre-wrap;"),
        "没有关连字": GOOD_APP_CSS.replace("font-variant-ligatures: none;", ""),
        "设了字距": GOOD_APP_CSS.replace("white-space: pre;", "white-space: pre; letter-spacing: 0.02em;"),
        "没有外框": GOOD_APP_CSS.replace("border: 1px solid var(--tt-border);", ""),
        "没有底色": GOOD_APP_CSS.replace("background: var(--tt-surface-1);", ""),
    }
    for name, css in broken_style.items():
        assert row_style_problems(css), f"没抓住：{name}"


def good_notices(ofl_text):
    lines = [ln.strip() for ln in ofl_text.splitlines()[:4]]
    return (
        "# 第三方许可与致谢\n\n本目录随包字体与图标的第三方许可如下。\n\n"
        "## Lucide\n\n| 项目 | 内容 |\n| --- | --- |\n| 名称 | Lucide |\n| 版本 | 1.59.0 |\n| 许可 | ISC |\n"
        f"| 许可原文 | [`{LUCIDE_LICENSE_LINK}`]({LUCIDE_LICENSE_LINK}) |\n\n"
        "## Sarasa Gothic（等距更纱黑体 SC）\n\n| 项目 | 内容 |\n| --- | --- |\n"
        "| 名称 | Sarasa Gothic（更纱黑体）；用到的字体：等距更纱黑体 SC（Sarasa Mono SC）的 Regular 与 SemiBold |\n"
        "| 版本 | 0.36.0 |\n| 许可 | SIL Open Font License 1.1 |\n"
        "| 版权 | " + "<br>".join(lines) + " |\n"
        "| 来源 | <https://github.com/be5invis/Sarasa-Gothic>，v0.36.0 发布的 `sarasa-gothic-ttf-0.36.0.7z` |\n"
        "| 随包文件与改动 | `fonts/sarasa-mono-sc-regular.woff2`、`fonts/sarasa-mono-sc-semibold.woff2`，由上游 TTF 转成 woff2"
        "（wawoff2 2.0.1，默认参数），转换与核对见 `fonts/SOURCE.md` |\n"
        "| 许可原文 | `public/licenses/OFL.txt`（产物里是 `licenses/OFL.txt`） |\n\n"
        "「设置 › 关于」的许可列表由设置页那一片加上。\n"
    )


def test_gate_selfcheck_notices(tmp_path):
    """门禁自检：按合同第 4 条写的 notices 通过 S6、S7 的检查；删字段、断链接都被抓住。"""
    ofl = _read(need_file(f"{WEB_REL}/fonts/OFL.txt"))
    good = good_notices(ofl)
    (tmp_path / "public" / "licenses").mkdir(parents=True)
    (tmp_path / LUCIDE_LICENSE_LINK).write_text("x", encoding="utf-8")
    assert notices_problems(good, ofl) == []
    assert notice_link_problems(good, tmp_path) == []
    for needle in ("0.36.0", "SIL Open Font License 1.1", "github.com/be5invis/Sarasa-Gothic", "public/licenses/OFL.txt",
                   "Lucide", "1.59.0", "ISC", "Portions Copyright (c) 2012 Google Inc.", "2.0.1"):
        assert notices_problems(good.replace(needle, "XX"), ofl), f"没抓住缺 {needle}"
    old_link = good.replace(f"]({LUCIDE_LICENSE_LINK})", "](licenses/lucide-1.59.0-LICENSE.txt)")
    assert notice_link_problems(old_link, tmp_path), "没抓住旧的 Lucide 链接目标"
    missing = good + "\n[x](public/licenses/no-such.txt)\n"
    assert notice_link_problems(missing, tmp_path), "没抓住指向不存在文件的链接"
    (tmp_path / "public" / "licenses" / "OFL.txt").write_text("y", encoding="utf-8")
    assert notice_link_problems(good + "\n[o](public/licenses/OFL.txt)\n", tmp_path) == []


def make_fake_dist(root, regular_name="sarasa-mono-sc-regular-aaaa1111.woff2",
                   semibold_name="sarasa-mono-sc-semibold-bbbb2222.woff2"):
    """造一棵合成的 dist：压缩过的 CSS、带 React 本来就有的网址的 JS、两个真 woff2、许可副本。返回 (dist, 许可副本路径)。"""
    dist = root / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "licenses").mkdir()
    shutil.copyfile(font_path(FONT_REGULAR), dist / "assets" / regular_name)
    shutil.copyfile(font_path(FONT_SEMIBOLD), dist / "assets" / semibold_name)
    css = (f'@font-face{{font-family:TT Sarasa Mono SC;src:url(./{regular_name})format("woff2");'
           f'font-weight:300 500;font-style:normal;font-display:swap}}'
           f'@font-face{{font-family:TT Sarasa Mono SC;src:url(./{semibold_name}) format("woff2");'
           f'font-weight:600 800;font-style:normal;font-display:swap}}'
           ':root{--tt-font-sans:"TT Sarasa Mono SC",monospace}')
    (dist / "assets" / "index-cccc3333.css").write_text(css, encoding="utf-8")
    (dist / "assets" / "index-dddd4444.js").write_text(
        'console.error("https://reactjs.org/docs/error-decoder.html?invariant=");var ns="http://www.w3.org/2000/svg";',
        encoding="utf-8")
    (dist / "index.html").write_text(
        '<!doctype html><link rel="stylesheet" href="./assets/index-cccc3333.css"><script type="module" src="./assets/index-dddd4444.js"></script>',
        encoding="utf-8")
    public_copy = root / "public-OFL.txt"
    public_copy.write_bytes(font_path("OFL.txt").read_bytes())
    shutil.copyfile(public_copy, dist / "licenses" / "OFL.txt")
    return dist, public_copy


def all_dist_problems(dist, public_copy):
    return (dist_woff2_problems(dist) + dist_other_font_problems(dist) + dist_font_face_problems(dist)
            + dist_remote_problems(dist) + dist_license_problems(dist, public_copy))


def _css(dist):
    return dist / "assets" / "index-cccc3333.css"


def _mut_remove_font(dist, _copy):
    (dist / "assets" / "sarasa-mono-sc-semibold-bbbb2222.woff2").unlink()


def _mut_extra_woff2(dist, _copy):
    shutil.copyfile(dist / "assets" / "sarasa-mono-sc-regular-aaaa1111.woff2", dist / "assets" / "again.woff2")


def _mut_ttf(dist, _copy):
    (dist / "assets" / "x.ttf").write_bytes(b"\x00\x01\x00\x00junk")


def _mut_signature_in_bin(dist, _copy):
    (dist / "assets" / "font.bin").write_bytes(b"wOF2junk")


def _mut_bytes_differ(dist, _copy):
    path = dist / "assets" / "sarasa-mono-sc-regular-aaaa1111.woff2"
    data = bytearray(path.read_bytes())
    data[len(data) // 2] ^= 0xFF
    path.write_bytes(bytes(data))


def _mut_swap_weights(dist, _copy):
    css = _css(dist).read_text(encoding="utf-8").replace("300 500", "TMP").replace("600 800", "300 500").replace("TMP", "600 800")
    _css(dist).write_text(css, encoding="utf-8")


def _mut_weight(dist, _copy):
    _css(dist).write_text(_css(dist).read_text(encoding="utf-8").replace("600 800", "600 700"), encoding="utf-8")


def _mut_display(dist, _copy):
    _css(dist).write_text(_css(dist).read_text(encoding="utf-8").replace("font-display:swap", "font-display:block", 1), encoding="utf-8")


def _mut_family(dist, _copy):
    _css(dist).write_text(_css(dist).read_text(encoding="utf-8").replace("font-family:TT Sarasa Mono SC", "font-family:Other", 1), encoding="utf-8")


def _mut_absolute_url(dist, _copy):
    _css(dist).write_text(_css(dist).read_text(encoding="utf-8").replace("url(./", "url(/assets/", 1), encoding="utf-8")


def _mut_remote_url(dist, _copy):
    _css(dist).write_text(_css(dist).read_text(encoding="utf-8").replace(
        "url(./sarasa-mono-sc-regular-aaaa1111.woff2)", "url(https://cdn.example.com/a/regular.woff2)"), encoding="utf-8")


def _mut_inline(dist, _copy):
    _css(dist).write_text(_css(dist).read_text(encoding="utf-8").replace(
        "url(./sarasa-mono-sc-regular-aaaa1111.woff2)", "url(data:font/woff2;base64,AAAA)"), encoding="utf-8")


def _mut_google_fonts(dist, _copy):
    _css(dist).write_text("@import url(https://fonts.googleapis.com/css2?family=X);" + _css(dist).read_text(encoding="utf-8"), encoding="utf-8")


def _mut_html_remote_font(dist, _copy):
    (dist / "index.html").write_text('<link href="//cdn.example.com/f.woff2">', encoding="utf-8")


def _mut_missing_license(dist, _copy):
    (dist / "licenses" / "OFL.txt").unlink()


def _mut_license_differs(dist, _copy):
    path = dist / "licenses" / "OFL.txt"
    path.write_bytes(path.read_bytes().replace(b"Copyright", b"Copyleft", 1))


def _mut_no_css_font_face(dist, _copy):
    _css(dist).write_text(":root{color:red}", encoding="utf-8")


DIST_MUTATIONS = [_mut_remove_font, _mut_extra_woff2, _mut_ttf, _mut_signature_in_bin, _mut_bytes_differ,
                  _mut_swap_weights, _mut_weight, _mut_display, _mut_family, _mut_absolute_url, _mut_remote_url,
                  _mut_inline, _mut_google_fonts, _mut_html_remote_font, _mut_missing_license, _mut_license_differs,
                  _mut_no_css_font_face]


def test_gate_selfcheck_dist_checks_accept_synthetic_dist(tmp_path):
    """门禁自检：合成的正确 dist（压缩过的 CSS、React 本来就有的网址、两个真 woff2、许可副本）通过 P2–P6 的全部检查。"""
    dist, public_copy = make_fake_dist(tmp_path)
    assert all_dist_problems(dist, public_copy) == []
    # 产物文件名带哈希，换个名字也一样
    other, other_copy = make_fake_dist(tmp_path / "other", "r-0000.woff2", "s-1111.woff2")
    _css(other).write_text(
        '@font-face{font-family:"TT Sarasa Mono SC";src:url("./r-0000.woff2") format("woff2");font-weight:300 500;font-display:swap}'
        '@font-face{font-family:"TT Sarasa Mono SC";src:url("./s-1111.woff2") format("woff2");font-weight:600 800;font-display:swap}',
        encoding="utf-8")
    assert all_dist_problems(other, other_copy) == []


@pytest.mark.parametrize("mutation", DIST_MUTATIONS, ids=lambda f: f.__name__.removeprefix("_mut_"))
def test_gate_selfcheck_dist_checks_catch_mutations(tmp_path, mutation):
    """门禁自检：合成 dist 逐项改坏（少字体、多字体、字节不同、字重或地址写错、内联、外链、许可缺失或不同），P2–P6 的检查总有一条抓住。"""
    dist, public_copy = make_fake_dist(tmp_path)
    mutation(dist, public_copy)
    assert all_dist_problems(dist, public_copy), f"没抓住：{mutation.__name__}"


def test_gate_selfcheck_probe_template():
    """门禁自检：探针模板的用例数、文件名约定与 vitest 的 include 一致（gate-probe 目录）。"""
    assert PROBE_TEST_COUNT == 7
    vite_cfg = _read(need_file(f"{WEB_REL}/vite.config.ts"))
    assert "gate-probe/**/*.test.{ts,tsx}" in vite_cfg
    assert "·" in SPECIMEN_TITLE and "·" in PROBE_SOURCE.replace("\\u00b7", "·")
