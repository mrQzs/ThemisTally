"""T002 战前门禁：桌面端前端第 1 片的黑盒基准测试（合同 t002-desktop-web，plan_version 2）。

v2 把随包字体移出第 1 片（站主答复 msg-id 20261019T092117759962Z-owner-b9ad32）：本文件不再断言字体包、
``fonts.css``、``dist`` 里的 woff2 或 OFL 原文；反过来断言第 1 片里没有任何字体依赖、字体文件和 ``@font-face``（D05）。
令牌里 ``--tt-font-sans`` / ``--tt-font-mono`` 仍照 handoff 写整条字体栈，首项 ``"TT Sarasa Mono SC"``。

被测对象是新建的 ``desktop/web/``（React 18 + TypeScript + Vite + Vitest）。基线是提交 ``e76da22``（合同的
base_sha），那时 ``desktop/web`` 还不存在，所以本文件在基线上的每条断言都落在“目标文件不存在”上，不是导入、
收集或语法错误：模块级只导入标准库，npm 和 node 只在 ``desktop/web/package.json`` 存在时才调用。

结构：

- 一个会话级夹具 ``pipeline``：``package.json`` 存在时，按合同顺序在 ``desktop/web`` 下跑 ``npm ci``、
  ``npm run build``、``npm test``、``npm run check:contract``，再写一份临时的组件探针（Q4）用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除；前后各取一次 ``git status``；
  ``npm ci`` 失败则不跑后续步骤。整体受 ``PIPELINE_BUDGET`` 约束（合同检查项的 timeout_seconds 是 2400）。
- 其余断言读候选的文件、读 ``dist``、读画布（``docs/ui-design/pages/01-设计令牌-Themis-Tally.html``）。

测试名里的 G1–G10 对应规划报告 §4.5 的断言编号，docstring 写明对应的合同条款与 DoD：

- D01（四步通过、令牌逐项相等、5 个组件与陈列页就位）：G1–G8、G10；
- D02（范围）：由内核的范围检查证明。原来的 ``test_d02_changes_stay_inside_allowed_set`` 断言“相对基线的改动只落在允许集合内”，T002 结项时由站主退役：集成之后分支上有别的提交（内核第 7–10 轮）和用户未提交的文件，它在末端上必然失败；
- D03（没有删除、跳过、弱化既有测试）：``test_d03_*`` 做能机械检查的部分（既有测试文件不动、新测试不跳过），
  “有没有弱化”由终审读差异判断；
- D04（契约检查脚本真检查）：G9；
- D05（依赖里没有字体包）：G1、G2。原来还断言“``dist``、``src``、``public`` 里没有字体文件与 ``@font-face``、
  没有 ``fonts.css``，``public/licenses`` 与 ``THIRD_PARTY_NOTICES.md`` 只记 Lucide”，这几条只在第 1 片成立，
  站主在登记 T003（随包字体）之前退役了：``test_d05_src_and_public_have_no_fonts``、``test_d05_dist_has_no_fonts``、
  ``test_g7_third_party_notices_only_lucide``，以及 ``test_g7_lucide_license_in_public_and_dist`` 里“没有 OFL”那一句。

门禁做不到、留给人的项：陈列页与画布的视觉还原（尺寸、间距、悬停/按下/聚焦/禁用/加载各状态）、1024 宽无整页
横向滚动、许可与来源记录的准确性与完整性、按钮高 28/32/36 与 Tag/Card 的具体像素（jsdom 不算样式）。

组件探针的取舍（站主 Q4）：合同没有规定“加载文字”的属性名，探针不传加载文字，只验证 ``loading`` 的
disabled、aria-busy 与转圈图标；陈列页的三个主题按钮没有规定文案，探针按文字里的“暗/亮/系统”（或
dark/light/system）找按钮。

基线上本文件应当失败，原因是 ``desktop/web`` 的内容缺失；不是导入、路径或语法错误。
"""

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

import pytest

BASE_SHA = "e76da22d608b8192647c33791b9436122d4c6e82"
REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_REL = "desktop/web"
WEB = REPO_ROOT / "desktop" / "web"
CANVAS = REPO_ROOT / "docs" / "ui-design" / "pages" / "01-设计令牌-Themis-Tally.html"

# 合同检查项 V01 的 timeout_seconds 是 2400；夹具总预算留出余量给其余快测试。
PIPELINE_BUDGET = 2100
STEP_CAPS = {
    "npm ci": 1200,
    "npm run build": 600,
    "npm test": 600,
    "npm run check:contract": 120,
    "probe": 420,
}

# UI 文档 §3.4：17 个状态 → (中文, 色调, Lucide 图标)
STATES = [
    ("PREPARING", "准备中", "info", "hourglass"),
    ("PREPARED", "待运行", "neutral", "circle-dashed"),
    ("PREPARE_FAILED", "准备失败", "danger", "circle-x"),
    ("RUNNING", "运行中", "info", "loader-circle"),
    ("COLLECTING", "收集证据", "info", "archive"),
    ("NEEDS_REVIEW", "待验收", "attention", "scale"),
    ("PASS", "通过", "success", "circle-check"),
    ("ACCEPTED_WITH_EXCEPTION", "带豁免通过", "success", "badge-check"),
    ("REVISE", "返工", "warning", "rotate-ccw"),
    ("BLOCKED", "阻塞", "danger", "octagon-x"),
    ("ESCALATE", "升级", "escalate", "circle-arrow-up"),
    ("INFRA_FAILURE", "基础设施故障", "danger", "server"),
    ("TIMEOUT", "超时", "warning", "timer-off"),
    ("CANCELLED", "已取消", "neutral", "ban"),
    ("INTEGRATED", "已集成", "brand", "git-merge"),
    ("ABANDONED", "已放弃", "neutral", "archive-x"),
    ("SUPERSEDED", "已被取代", "neutral", "layers"),
]
TONES = ["neutral", "info", "attention", "success", "warning", "danger", "escalate", "brand"]
# 第 1 片图标：17 个状态图标 + circle-help + info、triangle-alert、x（loader-circle 已在 17 个里）
ICON_NAMES = sorted({s[3] for s in STATES} | {"circle-help", "loader-circle", "info", "triangle-alert", "x"})

FORBIDDEN_DEP_NAMES = ("tailwindcss", "framer-motion", "lucide-react", "lucide", "react-icons")
FORBIDDEN_DEP_PREFIXES = ("@fortawesome/", "@heroicons/", "@phosphor-icons/", "react-router", "@tanstack/react-router",
                          "@tabler/icons", "@radix-ui/react-icons")

CSS_NAMED_COLORS = """
aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown burlywood
cadetblue chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray
darkgreen darkgrey darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen
darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue
firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew
hotpink indianred indigo ivory khaki lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan
lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray
lightslategrey lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue
mediumorchid mediumpurple mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred
midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid
palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum powderblue purple
rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue
slateblue slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white
whitesmoke yellow yellowgreen
""".split()


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def need_file(rel):
    """断言 desktop/web 下（或仓库里）的文件存在，返回路径。基线上到这里就以断言失败。"""
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上 desktop/web 尚未实现）"
    return path


def need_dir(rel):
    path = REPO_ROOT / rel
    assert path.is_dir(), f"{rel} 不存在（基线上 desktop/web 尚未实现）"
    return path


def load_json(rel):
    path = need_file(rel)
    try:
        return json.loads(_read(path))
    except ValueError as exc:
        pytest.fail(f"{rel} 不是合法 JSON：{exc}")


def git(*args, check=False):
    proc = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, timeout=120)
    if check:
        assert proc.returncode == 0, f"git {' '.join(args)} 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return proc


def git_status_set():
    proc = git("status", "--porcelain=v1", "--untracked-files=all", "-z", check=True)
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


def file_digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


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


# ---------------------------------------------------------------------------
# 会话级夹具：四步 npm + 组件探针
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
        self.probe_expected_min = 0
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


PROBE_TEMPLATE = r"""
import * as React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';
import * as Components from '../src/components';

const { Button, Tag, StatusTag, Card, Banner } = Components as any;
const STATES: Array<[string, string, string]> = __STATES__;
const TONES: string[] = __TONES__;
const VARIANTS = ['primary', 'secondary', 'ghost', 'danger'];
const SIZES = ['sm', 'md', 'lg'];
const COMBOS: Array<[string, string]> = [];
for (const v of VARIANTS) { for (const s of SIZES) { COMBOS.push([v, s]); } }

afterEach(() => {
  cleanup();
  document.documentElement.removeAttribute('data-theme');
});

function rootOf(container: HTMLElement): HTMLElement {
  return container.firstElementChild as HTMLElement;
}
function iconOf(el: Element | null): string {
  const svg = el ? el.querySelector('svg') : null;
  return svg ? svg.innerHTML : '';
}
function textOf(el: Element | null): string {
  return ((el && el.textContent) || '').trim();
}

describe('components/index 统一导出', () => {
  it.each(['Button', 'Tag', 'StatusTag', 'Card', 'Banner'])('%s', (name) => {
    expect((Components as any)[name]).toBeTruthy();
  });
});

describe('StatusTag', () => {
  it.each(STATES)('已知状态 %s：中文、title、色调、图标', (code, label, tone) => {
    const { container } = render(<StatusTag state={code} />);
    const root = rootOf(container);
    expect(root.getAttribute('title')).toBe(code);
    expect(textOf(root)).toBe(label);
    expect(root.getAttribute('data-tone')).toBe(tone);
    const svg = root.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute('aria-hidden')).toBe('true');
    expect(svg!.getAttribute('viewBox')).toBe('0 0 24 24');
  });

  it('17 个状态的图标互不相同', () => {
    const seen = new Set<string>();
    for (const [code] of STATES) {
      const { container, unmount } = render(<StatusTag state={code} />);
      seen.add(iconOf(rootOf(container)));
      unmount();
    }
    expect(seen.size).toBe(STATES.length);
  });

  it.each(['WAITING_FOR_GODOT', 'preparing', 'Pass', '已完成'])('未知状态码 %s：原样显示、neutral、title 为状态码', (code) => {
    const { container } = render(<StatusTag state={code} />);
    const root = rootOf(container);
    expect(textOf(root)).toBe(code);
    expect(root.getAttribute('data-tone')).toBe('neutral');
    expect(root.getAttribute('title')).toBe(code);
    expect(root.querySelector('svg')).not.toBeNull();
  });

  it('未知状态用 circle-help 图标，不同于 17 个已知状态的图标', () => {
    const known = new Set<string>();
    for (const [code] of STATES) {
      const { container, unmount } = render(<StatusTag state={code} />);
      known.add(iconOf(rootOf(container)));
      unmount();
    }
    const a = render(<StatusTag state="NOT_A_STATE" />);
    const b = render(<StatusTag state="ANOTHER_ONE" />);
    const iconA = iconOf(rootOf(a.container));
    expect(iconA).not.toBe('');
    expect(iconA).toBe(iconOf(rootOf(b.container)));
    expect(known.has(iconA)).toBe(false);
  });

  it.each(['md', 'sm'])('size=%s → data-size', (size) => {
    const { container } = render(<StatusTag state="PASS" size={size} />);
    expect(rootOf(container).getAttribute('data-size')).toBe(size);
  });
});

describe('Tag', () => {
  it.each(TONES)('tone=%s → data-tone 与文字', (tone) => {
    const { container } = render(<Tag tone={tone}>标签文字</Tag>);
    const root = rootOf(container);
    expect(root.getAttribute('data-tone')).toBe(tone);
    expect(textOf(root)).toBe('标签文字');
  });

  it('mono 不改变色调，文字照常渲染', () => {
    const { container } = render(<Tag tone="brand" mono>abc123</Tag>);
    const root = rootOf(container);
    expect(root.getAttribute('data-tone')).toBe('brand');
    expect(textOf(root)).toBe('abc123');
  });
});

describe('Button', () => {
  it.each(COMBOS)('variant=%s size=%s', (variant, size) => {
    const { container } = render(<Button variant={variant} size={size}>确定</Button>);
    const root = rootOf(container);
    expect(root.tagName).toBe('BUTTON');
    expect(root.getAttribute('data-variant')).toBe(variant);
    expect(root.getAttribute('data-size')).toBe(size);
    expect(root.hasAttribute('disabled')).toBe(false);
    expect(root.getAttribute('aria-busy')).not.toBe('true');
    expect(textOf(root)).toContain('确定');
  });

  it('disabled 属性', () => {
    const { container } = render(<Button disabled>不可点</Button>);
    const root = rootOf(container) as HTMLButtonElement;
    expect(root.disabled).toBe(true);
    expect(root.getAttribute('aria-busy')).not.toBe('true');
  });

  it('loading：转圈图标、disabled、aria-busy 为 true，不触发 onClick', () => {
    const onClick = vi.fn();
    const { container } = render(<Button variant="danger" size="lg" loading onClick={onClick}>保存</Button>);
    const root = rootOf(container) as HTMLButtonElement;
    expect(root.tagName).toBe('BUTTON');
    expect(root.disabled).toBe(true);
    expect(root.getAttribute('aria-busy')).toBe('true');
    expect(root.getAttribute('data-variant')).toBe('danger');
    expect(root.getAttribute('data-size')).toBe('lg');
    const svg = root.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg!.getAttribute('aria-hidden')).toBe('true');
    const running = render(<StatusTag state="RUNNING" />);
    expect(svg!.innerHTML).toBe(iconOf(rootOf(running.container)));
    fireEvent.click(root);
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe('Card', () => {
  it('根元素是 div，标题、操作、内容按头部到内容的顺序渲染', () => {
    const { container } = render(
      <Card title={<span data-testid="t">标题X</span>} actions={<button data-testid="a">操作Y</button>}>
        <p data-testid="c">内容Z</p>
      </Card>,
    );
    const root = rootOf(container);
    expect(root.tagName).toBe('DIV');
    const t = root.querySelector('[data-testid="t"]');
    const a = root.querySelector('[data-testid="a"]');
    const c = root.querySelector('[data-testid="c"]');
    expect(t).not.toBeNull();
    expect(a).not.toBeNull();
    expect(c).not.toBeNull();
    expect(t!.compareDocumentPosition(a!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(a!.compareDocumentPosition(c!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe('Banner', () => {
  it('info：渲染关闭按钮（aria-label 为「关闭提示」），点击触发 onClose，无 alert role', () => {
    const onClose = vi.fn();
    const { container } = render(<Banner tone="info" onClose={onClose}>提示内容</Banner>);
    const root = rootOf(container);
    expect(root.getAttribute('data-tone')).toBe('info');
    expect(textOf(root)).toContain('提示内容');
    const close = root.querySelector('[aria-label="关闭提示"]') as HTMLElement | null;
    expect(close).not.toBeNull();
    expect(close!.tagName).toBe('BUTTON');
    fireEvent.click(close!);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(root.getAttribute('role')).not.toBe('alert');
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });

  it('info 不传 onClose 也渲染关闭按钮', () => {
    const { container } = render(<Banner tone="info">提示</Banner>);
    expect(container.querySelector('[aria-label="关闭提示"]')).not.toBeNull();
  });

  it.each(['warning', 'danger'])('%s：没有关闭按钮（即使传了 onClose）', (tone) => {
    const { container } = render(<Banner tone={tone} onClose={() => {}}>提示内容</Banner>);
    const root = rootOf(container);
    expect(root.getAttribute('data-tone')).toBe(tone);
    expect(textOf(root)).toContain('提示内容');
    expect(container.querySelector('[aria-label="关闭提示"]')).toBeNull();
    expect(container.querySelector('button')).toBeNull();
  });

  it('danger 根元素 role 为 alert；warning 没有 alert role', () => {
    const d = render(<Banner tone="danger">出错了</Banner>);
    expect(rootOf(d.container).getAttribute('role')).toBe('alert');
    const w = render(<Banner tone="warning">注意</Banner>);
    expect(rootOf(w.container).getAttribute('role')).not.toBe('alert');
    expect(w.container.querySelector('[role="alert"]')).toBeNull();
  });

  it('info 用 info 图标，warning 与 danger 同用 triangle-alert 图标', () => {
    const i = render(<Banner tone="info">a</Banner>);
    const w = render(<Banner tone="warning">b</Banner>);
    const d = render(<Banner tone="danger">c</Banner>);
    const iconI = iconOf(rootOf(i.container));
    const iconW = iconOf(rootOf(w.container));
    const iconD = iconOf(rootOf(d.container));
    expect(iconI).not.toBe('');
    expect(iconW).not.toBe('');
    expect(iconW).toBe(iconD);
    expect(iconI).not.toBe(iconW);
  });
});

describe('App 陈列页', () => {
  async function mountApp() {
    const mod: any = await import('../src/App');
    const AppComponent = mod.default ?? mod.App;
    expect(AppComponent).toBeTruthy();
    return render(<AppComponent />);
  }

  function themeButton(pattern: RegExp): HTMLElement {
    const hit = Array.from(document.querySelectorAll('button')).find((b) => pattern.test(textOf(b)));
    expect(hit, `找不到文字匹配 ${pattern} 的按钮`).toBeTruthy();
    return hit as HTMLElement;
  }

  it('列出 17 个状态、8 种色调、4 种按钮变体与 3 种尺寸、加载态与三种提示条', async () => {
    await mountApp();
    for (const [code] of STATES) {
      expect(document.querySelector('[title="' + code + '"]'), '状态 ' + code).not.toBeNull();
    }
    for (const tone of TONES) {
      expect(document.querySelector('[data-tone="' + tone + '"]'), '色调 ' + tone).not.toBeNull();
    }
    for (const v of VARIANTS) {
      expect(document.querySelector('button[data-variant="' + v + '"]'), '按钮变体 ' + v).not.toBeNull();
    }
    for (const s of SIZES) {
      expect(document.querySelector('button[data-size="' + s + '"]'), '按钮尺寸 ' + s).not.toBeNull();
    }
    expect(document.querySelector('button[aria-busy="true"]'), '加载态按钮').not.toBeNull();
    expect(document.querySelector('[role="alert"]'), 'danger 提示条').not.toBeNull();
    expect(document.querySelector('[aria-label="关闭提示"]'), 'info 提示条的关闭按钮').not.toBeNull();
  });

  it('三个按钮切换根元素的 data-theme：亮 → light，跟随系统 → system，暗 → 去掉', async () => {
    await mountApp();
    const root = document.documentElement;
    fireEvent.click(themeButton(/亮|浅|light/i));
    expect(root.getAttribute('data-theme')).toBe('light');
    fireEvent.click(themeButton(/系统|system|auto/i));
    expect(root.getAttribute('data-theme')).toBe('system');
    fireEvent.click(themeButton(/暗|深|dark/i));
    expect(root.hasAttribute('data-theme')).toBe(false);
  });
});
"""


def build_probe_source():
    states = [[code, label, tone] for code, label, tone, _icon in STATES]
    return (PROBE_TEMPLATE
            .replace("__STATES__", json.dumps(states, ensure_ascii=False))
            .replace("__TONES__", json.dumps(TONES)))


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


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在（基线上目标尚未实现），未调用 npm"
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
    pipe.digests_before = {name: file_digest(WEB / name) for name in ("package.json", "package-lock.json")}

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
            probe_path.write_text(build_probe_source(), encoding="utf-8", newline="\n")
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
        pipe.digests_after = {name: file_digest(WEB / name) for name in ("package.json", "package-lock.json")}
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


# ---------------------------------------------------------------------------
# G1 package.json 与工程骨架（合同 Behavior contract / Steps 3–4；D01）
# ---------------------------------------------------------------------------

def _deps(pkg):
    return pkg.get("dependencies", {}), pkg.get("devDependencies", {})


def is_font_package(name):
    """字体包：包名里带 font、sarasa、typeface、woff 的（@fontpkg/*、@fontsource/*、typeface-* 等）。"""
    return bool(re.search(r"font|sarasa|typeface|woff", name, re.I))


def test_g1_package_json_deps_and_scripts():
    """G1：private、type、脚本、运行时与开发依赖、精确版本、没有被禁的依赖（合同 Steps 3–4、Stop conditions）。"""
    pkg = load_json(f"{WEB_REL}/package.json")
    assert pkg.get("private") is True, "package.json 的 private 应为 true"
    assert pkg.get("type") == "module", "package.json 的 type 应为 module"
    scripts = pkg.get("scripts", {})
    for name in ("dev", "build", "test", "typecheck", "check:contract"):
        assert name in scripts, f"scripts 缺 {name}"
    build = re.sub(r"\s+", " ", scripts["build"]).strip()
    assert build.startswith("tsc --noEmit") and re.search(r"&&\s*vite build", build), \
        f"build 应先 tsc --noEmit 再 vite build，实际：{scripts['build']}"
    assert re.sub(r"\s+", " ", scripts["test"]).strip() == "vitest run", f"test 应为 vitest run，实际：{scripts['test']}"
    assert scripts["check:contract"].strip().startswith("node scripts/token-contract.mjs"), \
        f"check:contract 应为 node scripts/token-contract.mjs，实际：{scripts['check:contract']}"

    runtime, dev = _deps(pkg)
    allv = {**runtime, **dev}
    assert re.fullmatch(r"18\.\d+\.\d+", runtime.get("react", "")), f"react 应精确固定为 18.x.y：{runtime.get('react')}"
    assert re.fullmatch(r"18\.\d+\.\d+", runtime.get("react-dom", "")), f"react-dom 应精确固定为 18.x.y：{runtime.get('react-dom')}"
    fonts = sorted(n for n in allv if is_font_package(n))
    assert not fonts, f"v2：第 1 片不装任何字体包（@fontpkg/* 或其他），package.json 里有：{fonts}"
    for name in ("typescript", "vite", "@vitejs/plugin-react", "vitest", "jsdom", "@testing-library/react",
                 "@testing-library/dom", "@types/react", "@types/react-dom"):
        assert name in dev, f"devDependencies 缺 {name}"
    assert re.match(r"18\.", dev["@types/react"]), f"@types/react 应为 18.x：{dev['@types/react']}"
    assert re.match(r"18\.", dev["@types/react-dom"]), f"@types/react-dom 应为 18.x：{dev['@types/react-dom']}"
    loose = {n: v for n, v in allv.items() if not re.match(r"\d+\.\d+\.\d+", v)}
    assert not loose, f"依赖应用 --save-exact 精确固定，下列不是：{loose}"
    bad = [n for n in allv if n in FORBIDDEN_DEP_NAMES or n.startswith(FORBIDDEN_DEP_PREFIXES)]
    assert not bad, f"与 D9 技术栈冲突的依赖：{bad}"


def test_g1_project_files_exist():
    """合同 Repository facts / Steps 3–12：约定的入口与文件都在。"""
    for rel in ("index.html", "vite.config.ts", "tsconfig.json", "README.md", "THIRD_PARTY_NOTICES.md",
                "src/main.tsx", "src/App.tsx", "src/components/index.ts", "src/domain/attemptStates.ts",
                "src/styles/tokens.css", "src/styles/base.css",
                "scripts/token-contract.mjs", "tests/token-contract.test.ts"):
        need_file(f"{WEB_REL}/{rel}")
    need_dir(f"{WEB_REL}/src/icons")
    need_dir(f"{WEB_REL}/public/licenses")


def test_g1_no_npmrc_anywhere():
    """合同 Compatibility / Stop conditions：不写 .npmrc。"""
    need_file(f"{WEB_REL}/package.json")
    assert not (WEB / ".npmrc").exists(), "desktop/web/.npmrc 不应存在"
    assert not (REPO_ROOT / ".npmrc").exists(), "仓库根 .npmrc 不应存在"


def test_g1_index_html_source():
    """合同 Compatibility / Steps 3：index.html 的 lang、只有一个外部 module 脚本、无内联脚本与样式、不写 data-theme。"""
    html = _read(need_file(f"{WEB_REL}/index.html"))
    assert re.search(r'<html[^>]*\blang=["\']zh-CN["\']', html), "index.html 的 html 应带 lang=\"zh-CN\""
    scripts = re.findall(r"<script\b([^>]*)>", html, re.I)
    assert len(scripts) == 1, f"index.html 应恰好有一个 script，实际 {len(scripts)}"
    assert re.search(r'\btype=["\']module["\']', scripts[0]) and re.search(r"\bsrc=", scripts[0]), \
        f"唯一的 script 应是带 src 的 module：{scripts[0]}"
    assert not re.search(r"<script\b(?![^>]*\bsrc=)[^>]*>", html, re.I), "index.html 不应有内联脚本"
    assert not re.search(r"<style\b", html, re.I), "index.html 不应有 <style>"
    assert not re.search(r"\sstyle\s*=", html, re.I), "index.html 不应有 style= 属性"
    assert "data-theme" not in html, "index.html 不应写 data-theme（缺省即暗色）"
    assert not re.search(r"(?:src|href)\s*=\s*[\"'](?:https?:)?//", html, re.I), "index.html 不应引用外部资源"


def test_g1_vite_config_and_entry():
    """合同 Steps 3：vite.config.ts 的 base、Vitest 的 jsdom 与 include；main.tsx 挂载 App。"""
    cfg = _read(need_file(f"{WEB_REL}/vite.config.ts"))
    assert re.search(r"""base\s*:\s*['"]\./['"]""", cfg), "vite.config.ts 的 base 应为 './'"
    assert re.search(r"""environment\s*:\s*['"]jsdom['"]""", cfg), "vitest environment 应为 jsdom"
    for glob in ("src/**/*.test.{ts,tsx}", "tests/**/*.test.{ts,tsx}", "gate-probe/**/*.test.{ts,tsx}"):
        assert glob in cfg, f"vite.config.ts 的 test.include 缺 {glob}"
    main = _read(need_file(f"{WEB_REL}/src/main.tsx"))
    assert "createRoot" in main and re.search(r"""from\s+['"]\./App(\.tsx)?['"]""", main), \
        "src/main.tsx 应用 createRoot 挂载 ./App"


def test_g1_readme_documents_commands():
    """合同 Steps 12：README.md 写命令、目录约定、令牌规则。"""
    readme = _read(need_file(f"{WEB_REL}/README.md"))
    for needle in ("npm ci", "npm run build", "npm test", "check:contract"):
        assert needle in readme, f"README.md 没有提到 {needle}"
    assert "--tt-" in readme, "README.md 应写令牌规则（--tt-*）"


# ---------------------------------------------------------------------------
# G2 锁文件
# ---------------------------------------------------------------------------

def test_g2_lockfile():
    """G2（合同 Steps 4）：lockfileVersion 为 3，resolved 全在 registry.npmjs.org，没有 git/file/link 依赖，没有被禁的包。"""
    lock = load_json(f"{WEB_REL}/package-lock.json")
    assert lock.get("lockfileVersion") == 3, f"lockfileVersion 应为 3：{lock.get('lockfileVersion')}"
    packages = lock.get("packages", {})
    assert "" in packages and len(packages) > 20, "锁文件的 packages 异常（缺根或太少）"
    problems = []
    for key, entry in packages.items():
        if key == "":
            continue
        if entry.get("link"):
            problems.append(f"{key}: link")
            continue
        resolved = entry.get("resolved")
        if resolved is None:
            if not entry.get("inBundle"):
                problems.append(f"{key}: 没有 resolved")
        elif not resolved.startswith("https://registry.npmjs.org/"):
            problems.append(f"{key}: {resolved}")
    assert not problems, "锁文件里有不在 registry.npmjs.org 的来源：\n" + "\n".join(problems[:20])
    names = {k.rsplit("node_modules/", 1)[-1] for k in packages if k}
    banned = sorted(n for n in names if n in FORBIDDEN_DEP_NAMES or n.startswith(FORBIDDEN_DEP_PREFIXES))
    assert not banned, f"锁文件里有与 D9 冲突的包：{banned}"
    fonts = sorted(n for n in names if is_font_package(n))
    assert not fonts, f"v2：锁文件里不应有任何字体包：{fonts}"


# ---------------------------------------------------------------------------
# G3 tsconfig
# ---------------------------------------------------------------------------

def test_g3_tsconfig_json_and_strict():
    """G3（合同 Steps 3）：tsconfig*.json 都是纯 JSON；tsconfig.json 的 strict 与 noEmit 为 true，其它不得把 strict 设成 false。"""
    need_file(f"{WEB_REL}/tsconfig.json")
    files = sorted(WEB.glob("tsconfig*.json"))
    assert files, "desktop/web 下没有 tsconfig*.json"
    for path in files:
        try:
            data = json.loads(_read(path))
        except ValueError as exc:
            pytest.fail(f"{path.name} 不是合法 JSON（不能有注释或尾逗号）：{exc}")
        opts = data.get("compilerOptions", {})
        if path.name == "tsconfig.json":
            assert opts.get("strict") is True, "tsconfig.json 的 compilerOptions.strict 应为 true"
            assert opts.get("noEmit") is True, "tsconfig.json 的 compilerOptions.noEmit 应为 true"
        else:
            assert opts.get("strict", True) is True, f"{path.name} 不得把 strict 设为 false"


# ---------------------------------------------------------------------------
# G4 .gitignore
# ---------------------------------------------------------------------------

NEW_IGNORE_LINES = ["desktop/**/node_modules/", "desktop/**/dist/", "desktop/web/gate-probe/"]


def test_g4_gitignore_append_only_and_effective():
    """G4（合同 Steps 2、Scope、Q4）：根 .gitignore 相对基线只追加那三行（外加注释），原有行不变；git check-ignore 认得。"""
    base = git("show", f"{BASE_SHA}:.gitignore")
    assert base.returncode == 0, f"读不到基线 .gitignore：{base.stderr.decode('utf-8', 'replace')}"
    base_lines = _norm(base.stdout.decode("utf-8")).splitlines()
    cand_lines = _read(REPO_ROOT / ".gitignore").splitlines()
    assert cand_lines[:len(base_lines)] == base_lines, "根 .gitignore 的原有行被改动或重排；只允许在末尾追加"
    added = [ln.strip() for ln in cand_lines[len(base_lines):] if ln.strip() and not ln.strip().startswith("#")]
    for line in NEW_IGNORE_LINES:
        assert line in added, f".gitignore 末尾缺追加行：{line}"
    assert sorted(added) == sorted(NEW_IGNORE_LINES), f"追加的非注释行应恰为那三行，实际：{added}"

    def ignored(rel):
        return git("check-ignore", "-q", "--no-index", "--", rel).returncode == 0

    for rel in ("desktop/web/node_modules/x", "desktop/web/dist/index.html", "desktop/web/gate-probe/probe-x.test.tsx"):
        assert ignored(rel), f"git check-ignore 应忽略 {rel}"
    for rel in ("desktop/web/src/App.tsx", "desktop/web/package.json", "desktop/web/package-lock.json",
                "desktop/web/public/licenses/LICENSE-lucide.txt", "desktop/web/tests/token-contract.test.ts"):
        assert not ignored(rel), f"{rel} 不应被忽略"


# ---------------------------------------------------------------------------
# G5 四步 npm 与工作树洁净（D01）
# ---------------------------------------------------------------------------

def test_g5_npm_ci(pipeline):
    """G5（合同 Behavior contract）：npm ci 按锁文件安装，退出 0。"""
    assert_step_ok(pipeline, "npm ci")


def test_g5_npm_run_build(pipeline):
    """G5：npm run build（tsc --noEmit 加 vite build）退出 0。"""
    assert_step_ok(pipeline, "npm run build")


def test_g5_npm_test(pipeline):
    """G5：npm test（vitest run）退出 0，确有测试通过，没有失败、跳过、待办。"""
    step = assert_step_ok(pipeline, "npm test")
    out = step.out
    assert re.search(r"Tests\s+(?:.*\|\s*)?\d+ passed", out), f"npm test 输出里没有 'Tests … N passed'：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", out), f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert re.search(r"Test Files\s+\d+ passed", out) and not re.search(r"Test Files\s+.*\bfailed\b", out), \
        f"npm test 的 Test Files 行异常：\n{step.tail}"


def test_g5_npm_run_check_contract(pipeline):
    """G5：npm run check:contract 对真实 src 退出 0。"""
    assert_step_ok(pipeline, "npm run check:contract")


def test_g5_worktree_unchanged_by_npm(pipeline):
    """G5（合同 Compatibility）：四步 npm 与探针前后 git status 相同（没有留下未忽略的文件），package.json 与锁文件内容不变。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"
    assert pipeline.digests_before == pipeline.digests_after, "npm 命令改动了 package.json 或 package-lock.json"
    assert not pipeline.gate_probe_left, "desktop/web/gate-probe/ 在探针结束后没有清掉"
    strays = [p for p in WEB.rglob("*.tsbuildinfo") if "node_modules" not in p.parts and "dist" not in p.parts]
    assert not strays, f"留下了 .tsbuildinfo：{strays}"


def test_g5_dist_has_index_and_assets(pipeline):
    """合同 Behavior contract：build 生成 dist/index.html 与资源（js、css）。"""
    dist = need_build(pipeline)
    assets = [p for p in dist.rglob("*") if p.is_file()]
    assert any(p.suffix == ".js" for p in assets), "dist 里没有 .js"
    assert any(p.suffix == ".css" for p in assets), "dist 里没有 .css"


# ---------------------------------------------------------------------------
# G6 dist/index.html 与离线（合同 Compatibility）
# ---------------------------------------------------------------------------

def test_g6_dist_index_html_offline(pipeline):
    """G6：dist/index.html 没有 <style、没有内联脚本、没有 style= 属性，src/href 不指向 http(s) 或 //，也不是以 / 开头的绝对路径（base 为 ./）。"""
    dist = need_build(pipeline)
    html = _read(dist / "index.html")
    assert not re.search(r"<style\b", html, re.I), "dist/index.html 含 <style"
    assert not re.search(r"<script\b(?![^>]*\bsrc=)[^>]*>", html, re.I), "dist/index.html 含不带 src 的 <script"
    assert not re.search(r"\sstyle\s*=", html, re.I), "dist/index.html 含 style= 属性"
    refs = re.findall(r"""\b(?:src|href)\s*=\s*["']([^"']*)["']""", html, re.I)
    assert refs, "dist/index.html 没有任何 src/href"
    for ref in refs:
        assert not re.match(r"(?:https?:)?//", ref, re.I), f"dist/index.html 引用了外部资源：{ref}"
        assert not ref.startswith("/"), f"dist/index.html 用了绝对路径 {ref}，base 应为 ./"
    assert len(re.findall(r"<script\b", html, re.I)) == 1, "dist/index.html 应只有一个 script"


def test_g6_dist_css_no_external_urls(pipeline):
    """G6：dist 的 CSS 里 url( 与 @import 不指向外部。"""
    dist = need_build(pipeline)
    css_files = [p for p in dist.rglob("*.css")]
    assert css_files, "dist 里没有 CSS"
    for path in css_files:
        css = _read(path)
        for url in re.findall(r"url\(\s*[\"']?([^)\"']*)", css):
            assert not re.match(r"(?:https?:)?//", url.strip(), re.I), f"{path.name} 的 url() 指向外部：{url}"
        for imp in re.findall(r"@import\s+(?:url\(\s*)?[\"']?([^\"');\s]*)", css):
            assert not re.match(r"(?:https?:)?//", imp, re.I), f"{path.name} 的 @import 指向外部：{imp}"


def test_g6_dist_css_carries_tokens(pipeline):
    """合同 Behavior contract：令牌与跟随系统、减少动效的媒体查询确实进了构建产物（字体栈来自令牌，不需要字体文件）。"""
    dist = need_build(pipeline)
    css = "\n".join(_read(p) for p in dist.rglob("*.css"))
    for needle in ("--tt-bg", "--tt-tone-info-fg", "TT Sarasa Mono SC", "prefers-color-scheme", "prefers-reduced-motion"):
        assert needle in css, f"dist 的 CSS 里没有 {needle}"


# ---------------------------------------------------------------------------
# G7 许可（Lucide）
# ---------------------------------------------------------------------------

ISC_SNIPPET = "Permission to use, copy, modify, and/or distribute this software"


def test_g7_lucide_license_in_public_and_dist(pipeline):
    """合同 v2 兼容性与 Steps 8：public/licenses 与随产物发布的 dist/licenses 里有 Lucide 的 ISC 许可原文。"""
    lic_dir = need_dir(f"{WEB_REL}/public/licenses")
    dist = need_build(pipeline)
    for label, directory in (("public/licenses", lic_dir), ("dist/licenses", dist / "licenses")):
        assert directory.is_dir(), f"{label} 不存在（public/licenses 应随产物发布）"
        texts = [_read(p) for p in directory.rglob("*") if p.is_file() and p.stat().st_size < 500_000]
        assert any(ISC_SNIPPET in t for t in texts), f"{label} 没有 Lucide 的 ISC 许可原文"


# ---------------------------------------------------------------------------
# G8 令牌（D01）：CSS 解析与比对
# ---------------------------------------------------------------------------

def _strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _scan(text):
    """按顶层切分：返回 [(前导, 花括号内原文或 None)]。None 表示以分号结尾的语句或声明。"""
    out = []
    i = 0
    n = len(text)
    start = 0
    paren = 0
    while i < n:
        ch = text[i]
        if ch in "\"'":
            j = i + 1
            while j < n and text[j] != ch:
                j += 2 if text[j] == "\\" else 1
            i = j + 1
            continue
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        elif ch == ";" and paren == 0:
            out.append((text[start:i].strip(), None))
            start = i + 1
        elif ch == "{" and paren == 0:
            depth = 1
            j = i + 1
            while j < n and depth:
                c = text[j]
                if c in "\"'":
                    q = c
                    j += 1
                    while j < n and text[j] != q:
                        j += 2 if text[j] == "\\" else 1
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                j += 1
            out.append((text[start:i].strip(), text[i + 1:j - 1]))
            start = j
            i = j
            continue
        i += 1
    tail = text[start:].strip()
    if tail:
        out.append((tail, None))
    return out


def norm_value(value):
    """空白归一化：连续空白并成一个空格，逗号与括号内侧的空白去掉。取值本身（大小写、小数位）不动。"""
    value = re.sub(r"\s+", " ", value.strip())
    value = re.sub(r"\s*,\s*", ",", value)
    value = re.sub(r"\(\s+", "(", value)
    value = re.sub(r"\s+\)", ")", value)
    return value


def parse_decls(body):
    decls = {}
    for prelude, nested in _scan(_strip_comments(body)):
        if nested is not None or ":" not in prelude:
            continue
        name, value = prelude.split(":", 1)
        name = name.strip()
        if not name.startswith("--"):
            name = name.lower()
        decls[name] = norm_value(value)
    return decls


THEME_CLASS = re.compile(r"^\.tt-theme-(dark|light)$")


def norm_selectors(prelude):
    parts = [re.sub(r"[\s\"']", "", p) for p in prelude.split(",")]
    return tuple(sorted({p for p in parts if p and not THEME_CLASS.match(p)}))


def parse_css(css, media=()):
    """解析成规则列表：style（选择器 + 声明）、at（@font-face、@keyframes、@container 等，保留原文）、statement。"""
    rules = []
    for prelude, body in _scan(_strip_comments(css)):
        if body is None:
            rules.append({"kind": "statement", "media": media, "prelude": prelude})
        elif prelude.startswith("@"):
            name = re.match(r"@[\w-]+", prelude).group(0).lower()
            if name in ("@media", "@supports", "@layer"):
                rules.extend(parse_css(body, media + (re.sub(r"\s+", "", prelude.lower()),)))
            else:
                rules.append({"kind": "at", "media": media, "prelude": prelude, "body": body})
        else:
            rules.append({"kind": "style", "media": media, "selectors": norm_selectors(prelude),
                          "decls": parse_decls(body)})
    return rules


MQ_LIGHT = "@media(prefers-color-scheme:light)"
MQ_REDUCED = "@media(prefers-reduced-motion:reduce)"
CONTEXTS = {
    "dark": ((), (":root",)),
    "light": ((), (":root[data-theme=light]",)),
    "system": ((MQ_LIGHT,), (":root[data-theme=system]",)),
    "reduced": ((MQ_REDUCED,), (":root",)),
}


def collect(rules, ctx):
    media, selectors = CONTEXTS[ctx]
    out = {}
    for rule in rules:
        if rule["kind"] == "style" and rule["media"] == media and rule["selectors"] == selectors:
            out.update(rule["decls"])
    return out


def canvas_rules():
    html = _read(CANVAS)
    start = html.index("<style>") + len("<style>")
    end = html.index("</style>", start)
    return parse_css(html[start:end])


def token_decls(decls):
    return {k: v for k, v in decls.items() if k.startswith("--tt-") or k == "color-scheme"}


def effective(rules, theme):
    """某个主题下的有效取值：暗色缺省，亮色与跟随系统（系统为亮）在其上覆盖。"""
    values = dict(collect(rules, "dark"))
    if theme == "light":
        values.update(collect(rules, "light"))
    elif theme == "system":
        values.update(collect(rules, "system"))
    return values


def cand_rules():
    return parse_css(_read(need_file(f"{WEB_REL}/src/styles/tokens.css")))


def _diff_report(expected, got, limit=20):
    lines = []
    for name, value in expected.items():
        if name not in got:
            lines.append(f"缺 {name}（画布：{value}）")
        elif got[name] != value:
            lines.append(f"{name}：画布 {value}  候选 {got[name]}")
    if len(lines) > limit:
        lines = lines[:limit] + [f"…… 共 {len(lines)} 处"]
    return lines


def test_gate_selfcheck_canvas_parse():
    """门禁自检（不依赖候选）：画布解析得到四个语境，数量与关键取值符合预期，system 与 light 的有效取值一致。"""
    rules = canvas_rules()
    dark, light, system, reduced = (collect(rules, c) for c in ("dark", "light", "system", "reduced"))
    assert dark["--tt-bg"] == "#0C111A" and dark["color-scheme"] == "dark"
    assert light["--tt-bg"] == "#F3F5F9" and light["color-scheme"] == "light"
    assert system["--tt-bg"] == "#F3F5F9" and system["color-scheme"] == "light"
    assert reduced == {"--tt-duration-fast": "0ms", "--tt-duration-base": "0ms", "--tt-duration-slow": "0ms"}
    assert len([k for k in dark if k.startswith("--tt-")]) >= 130
    eff_light, eff_system = effective(rules, "light"), effective(rules, "system")
    assert {k: v for k, v in eff_light.items() if k.startswith("--tt-")} == \
        {k: v for k, v in eff_system.items() if k.startswith("--tt-")}
    assert len(CSS_NAMED_COLORS) == 148 and len(set(CSS_NAMED_COLORS)) == 148


def equal_problems(canvas, cand):
    problems = []
    for ctx in ("dark", "light", "system", "reduced"):
        expected = token_decls(collect(canvas, ctx))
        got = collect(cand, ctx)
        if not expected:
            problems.append(f"[{ctx}] 画布没有这个语境（门禁解析问题）")
        for line in _diff_report(expected, got):
            problems.append(f"[{ctx}] {line}")
    return problems


def system_problems(cand):
    if not collect(cand, "dark"):
        return ["候选没有 :root 暗色块"]
    eff_light, eff_system = effective(cand, "light"), effective(cand, "system")
    bad = []
    for name in sorted(set(eff_light) | set(eff_system)):
        if not name.startswith("--tt-") and name != "color-scheme":
            continue
        if eff_light.get(name) != eff_system.get(name):
            bad.append(f"{name}：亮 {eff_light.get(name)}  跟随系统 {eff_system.get(name)}")
    return bad[:20]


def test_g8_tokens_equal_canvas_per_context():
    """G8（合同 设计令牌）：画布每个语境（暗色缺省、亮、跟随系统、减少动效）里的每个 --tt-* 与 color-scheme，候选都有且取值相同（空白归一化）。"""
    problems = equal_problems(canvas_rules(), cand_rules())
    assert not problems, "令牌与画布不一致：\n" + "\n".join(problems)


def test_g8_system_theme_matches_light_for_every_token():
    """G8（合同 设计令牌 / 规划 §4.5）：候选里亮色与暗色取值不同的每个令牌，跟随系统块里都有且与亮色相同。"""
    bad = system_problems(cand_rules())
    assert not bad, "跟随系统（系统为亮色）与亮色的有效取值不同：\n" + "\n".join(bad)


HANDOFF_BOTH = {
    "--tt-tabbar-height": "56px",
    "--tt-sidebar-dot-info": "#67E8F9",
    "--tt-sidebar-text-active": "#FFFFFF",
    "--tt-text-caption-strong": "600 12px/16px var(--tt-font-sans)",
    "--tt-text-sm-medium": "500 13px/20px var(--tt-font-sans)",
    "--tt-text-md-medium": "500 14px/22px var(--tt-font-sans)",
    "--tt-logo-tally": "#D49C32",
    "--tt-z-sticky": "10", "--tt-z-popover": "100", "--tt-z-drawer": "200",
    "--tt-z-dialog": "300", "--tt-z-toast": "400", "--tt-z-tooltip": "500",
}
HANDOFF_FONT_STACK = ('"TT Sarasa Mono SC","Sarasa Mono SC","等距更纱黑体 SC","Sarasa Term SC","Maple Mono NF CN",'
                      '"Cascadia Mono","Noto Sans Mono CJK SC",monospace')


def handoff_problems(cand):
    dark, light = effective(cand, "dark"), effective(cand, "light")
    problems = []
    # 修正 1：主题缺省为暗色
    if not (dark.get("color-scheme") == "dark" and dark.get("--tt-bg") == "#0C111A"):
        problems.append(":root 应是暗色缺省（color-scheme: dark，--tt-bg: #0C111A）")
    if not (light.get("color-scheme") == "light" and light.get("--tt-bg") == "#F3F5F9"):
        problems.append(':root[data-theme="light"] 应是亮色（color-scheme: light，--tt-bg: #F3F5F9）')
    # 修正 2：字体栈（sans 与 mono 同一条等宽栈）
    stack = norm_value(HANDOFF_FONT_STACK)
    if dark.get("--tt-font-sans") != stack:
        problems.append(f"--tt-font-sans 应为更纱字体栈：{dark.get('--tt-font-sans')}")
    if dark.get("--tt-font-mono") not in (stack, "var(--tt-font-sans)"):
        problems.append(f"--tt-font-mono 应与 sans 同栈：{dark.get('--tt-font-mono')}")
    for name, value in HANDOFF_BOTH.items():
        for theme, vals in (("暗", dark), ("亮", light)):
            if vals.get(name) != value:
                problems.append(f"[{theme}] {name}：应为 {value}，实际 {vals.get(name)}")
    for name, (d, l) in {"--tt-logo-mark": ("#DDE6F2", "#012852")}.items():
        if dark.get(name) != d:
            problems.append(f"[暗] {name}：应为 {d}，实际 {dark.get(name)}")
        if light.get(name) != l:
            problems.append(f"[亮] {name}：应为 {l}，实际 {light.get(name)}")
    reduced = collect(cand, "reduced")
    for name in ("--tt-duration-fast", "--tt-duration-base", "--tt-duration-slow"):
        if reduced.get(name) != "0ms":
            problems.append(f"减少动效时 {name} 应置 0ms：{reduced.get(name)}")
    return problems


def test_g8_handoff_additions_and_corrections():
    """G8（handoff「Token 补充」）：7 项新增与 2 项修正逐项断言（与画布无关的硬编码取值）。"""
    problems = handoff_problems(cand_rules())
    assert not problems, "handoff 的令牌补充不符：\n" + "\n".join(problems)


def test_gate_selfcheck_compare_helpers_accept_canvas():
    """门禁自检（不依赖候选）：把画布本身当候选喂给上面三组比对，应当全部通过；改一个取值则应被抓住。"""
    canvas = canvas_rules()
    assert equal_problems(canvas, canvas) == []
    assert system_problems(canvas) == []
    assert handoff_problems(canvas) == []
    broken = parse_css(re.sub(r"--tt-surface-3:\s*#262E3C", "--tt-surface-3: #262E3D", _read(CANVAS), count=1)
                       .split("</style>")[0].split("<style>", 1)[1])
    assert any("--tt-surface-3" in p for p in equal_problems(canvas, broken))


def test_g8_tokens_file_only_has_tokens():
    """G8（合同 设计令牌）：令牌文件里只有 --tt-* 与 color-scheme，不含 @font-face 与基础样式；按四个选择器分块。"""
    path = need_file(f"{WEB_REL}/src/styles/tokens.css")
    text = _read(path)
    assert "@font-face" not in text and "url(" not in text and "@import" not in text, "tokens.css 不应含 @font-face、url( 或 @import"
    rules = parse_css(text)
    assert rules, "tokens.css 没有规则"
    allowed = set(CONTEXTS.values()) | {((), ())}
    problems = []
    for rule in rules:
        if rule["kind"] != "style":
            problems.append(f"不允许的规则：{rule.get('prelude', '')[:60]}")
            continue
        if (rule["media"], rule["selectors"]) not in allowed:
            problems.append(f"不允许的语境：{rule['media']} {rule['selectors']}")
        for name in rule["decls"]:
            if not (name.startswith("--tt-") or name == "color-scheme"):
                problems.append(f"不允许的声明：{name}")
    assert not problems, "tokens.css 含令牌以外的内容：\n" + "\n".join(problems[:20])


# ---------------------------------------------------------------------------
# 基础样式与状态表、图标的静态检查（合同 基础样式、状态表、图标）
# ---------------------------------------------------------------------------

def _squash(text):
    return re.sub(r"\s+", " ", _strip_comments(text))


def test_g8_base_css_rules():
    """合同 基础样式：搬了画布的基础规则（.tt-app 的字体与连字、box-sizing、焦点环、.tt-num、.tt-i、关键帧与减少动效、容器查询、forced-colors）。"""
    css = _squash(_read(need_file(f"{WEB_REL}/src/styles/base.css")))
    required = {
        ".tt-app": r"\.tt-app\b[^{]*\{[^}]*font-variant-ligatures:\s*none",
        "box-sizing": r"box-sizing:\s*border-box",
        ":focus-visible 焦点环": r":focus-visible[^{]*\{[^}]*outline:\s*2px solid var\(--tt-focus\)",
        ".tt-num": r"\.tt-num\b[^{]*\{[^}]*tabular-nums",
        ".tt-i": r"\.tt-i\b[^{]*\{[^}]*stroke:\s*currentColor",
        "@keyframes tt-spin": r"@keyframes\s+tt-spin",
        "减少动效": r"@media\s*\(prefers-reduced-motion:\s*reduce\)",
        ".tt-content 容器": r"\.tt-content\b[^{]*\{[^}]*container-type:\s*inline-size",
        "@container": r"@container\s+tt-content",
        "forced-colors": r"@media\s*\(forced-colors:\s*active\)",
    }
    missing = [name for name, pat in required.items() if not re.search(pat, css)]
    assert not missing, f"base.css 缺这些基础规则：{missing}"


def _icon_forms(kebab):
    parts = kebab.split("-")
    pascal = "".join(p.capitalize() for p in parts)
    camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
    return {kebab, pascal, camel}


def _enclosing_braces(text, idx):
    depth = 0
    i = idx
    while i >= 0:
        if text[i] == "}":
            depth += 1
        elif text[i] == "{":
            if depth == 0:
                break
            depth -= 1
        i -= 1
    if i < 0:
        return ""
    depth = 1
    j = i + 1
    while j < len(text) and depth:
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
        j += 1
    return text[i:j]


def test_g8_attempt_states_table_source():
    """合同 状态表：attemptStates.ts 里 17 个状态各有 中文、色调、Lucide 图标，另有兜底（circle-help、neutral）。运行时行为由探针验证。"""
    text = _read(need_file(f"{WEB_REL}/src/domain/attemptStates.ts"))
    codes = [s[0] for s in STATES]
    any_code = re.compile(r"(?<![A-Z_])(?:" + "|".join(codes) + r")(?![A-Z_])")
    problems = []
    for code, label, tone, icon in STATES:
        hits = [m.start() for m in re.finditer(r"(?<![A-Z_])" + code + r"(?![A-Z_])", text)]
        if not hits:
            problems.append(f"{code}: 没有出现")
            continue
        ok = False
        for pos in hits:
            nxt = any_code.search(text, pos + len(code))
            window = text[pos:(nxt.start() if nxt else len(text))][:500]
            group = _enclosing_braces(text, pos)
            for scope in (window, group if len(any_code.findall(group)) == 1 else ""):
                if (label in scope and re.search(r"""['"]""" + tone + r"""['"]""", scope)
                        and any(f in scope for f in _icon_forms(icon))):
                    ok = True
        if not ok:
            problems.append(f"{code}: 找不到同一条目里的 {label} / {tone} / {icon}")
    assert not problems, "attemptStates.ts 与 UI 文档 §3.4 的 17 个状态不符：\n" + "\n".join(problems)
    assert any(f in text for f in _icon_forms("circle-help")) and re.search(r"""['"]neutral['"]""", text), \
        "attemptStates.ts 缺未知状态的兜底（circle-help、neutral）"


def test_g8_icons_dir():
    """合同 图标：src/icons 放齐 17 个状态图标与 circle-help、loader-circle、info、triangle-alert、x；24×24、aria-hidden、没有写死的颜色。"""
    icon_dir = need_dir(f"{WEB_REL}/src/icons")
    files = [p for p in icon_dir.rglob("*") if p.is_file() and p.suffix in (".ts", ".tsx", ".svg", ".js", ".jsx")]
    assert files, "src/icons 里没有文件"
    text = "\n".join(_read(p) for p in files)
    names_blob = text + "\n" + "\n".join(p.stem for p in files)
    missing = [n for n in ICON_NAMES if not any(f in names_blob for f in _icon_forms(n))]
    assert not missing, f"src/icons 缺这些图标：{missing}"
    assert re.search(r"viewBox\W+0 0 24 24", text), "图标应是 24×24 的 viewBox"
    assert re.search(r"aria-hidden", text), "图标应带 aria-hidden"
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", text), "图标里不应有写死的十六进制颜色"
    assert not re.search(r"""\b(?:fill|stroke)\s*[=:]\s*\{?\s*["'](?!none|currentColor)[^"']+["']""", text), \
        "图标的 fill/stroke 只能是 none 或 currentColor"


# ---------------------------------------------------------------------------
# G9 契约检查脚本（D04）：合成样本
# ---------------------------------------------------------------------------

SCRIPT = WEB / "scripts" / "token-contract.mjs"

CLEAN_TOKENS = (":root {\n  color-scheme: dark;\n  --tt-bg: #0C111A;\n  --tt-text-1: #E8ECF2;\n"
                "  --tt-border: #262E3C;\n  --tt-duration-fast: 100ms;\n}\n")
CLEAN_CSS = """.box {
  color: var(--tt-text-1);
  background: var(--tt-bg);
  border: 1px solid var(--tt-border);
  border: none;
  white-space: nowrap;
  outline-color: currentColor;
  background-color: transparent;
  border-color: inherit;
  color: CanvasText;
  background: Canvas;
  outline: 2px solid Highlight;
  fill: currentColor;
  stroke: currentColor;
  color: initial;
  background: unset;
  border-color: revert;
  outline-color: revert-layer;
  transition: color var(--tt-duration-fast);
  box-shadow: none;
}
"""
CLEAN_TSX = """import type { ReactNode } from 'react';

export function Demo({ children }: { children?: ReactNode }) {
  return (
    <div className="red blue" style={{ color: 'var(--tt-text-1)', background: 'transparent', whiteSpace: 'nowrap', borderColor: 'currentColor', outlineColor: 'CanvasText' }}>
      <a href="/add">red</a>
      {children}
    </div>
  );
}
"""
CLEAN_TS = "export const label = 'red';\nexport const bg = 'var(--tt-bg)';\n"
EXCLUDED_BAD_TEST_TSX = "export const x = { color: '#123456', background: 'rgba(0, 0, 0, .5)' };\nexport const v = 'var(--tt-nope)';\n"


def make_src(root, extra=None, tokens_inside=True):
    """造一棵合成的 src：干净文件（含应被排除的令牌文件、*.test.*、非 css/ts/tsx 文件）+ extra {相对路径: 内容}。"""
    src = root / "src"
    files = {
        "a.css": CLEAN_CSS,
        "b.tsx": CLEAN_TSX,
        "c.ts": CLEAN_TS,
        "sub/deep/d.css": ".d { color: var(--tt-bg); }\n",
        "bad.test.tsx": EXCLUDED_BAD_TEST_TSX,
        "bad.test.ts": EXCLUDED_BAD_TEST_TSX,
        "notes.md": "colors: #123456 red rgba(0,0,0,.5) var(--tt-nope)\n",
        "data.json": '{"color": "#123456"}\n',
    }
    if tokens_inside:
        files["styles/tokens.css"] = CLEAN_TOKENS
    files.update(extra or {})
    for rel, content in files.items():
        path = src / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
    if tokens_inside:
        tokens = src / "styles" / "tokens.css"
    else:
        tokens = root / "tokens.css"
        tokens.write_text(CLEAN_TOKENS, encoding="utf-8", newline="\n")
    return src, tokens


def run_contract(root, src, tokens):
    node = shutil.which("node")
    assert node, "找不到 node"
    assert SCRIPT.is_file(), "desktop/web/scripts/token-contract.mjs 不存在（基线上目标尚未实现）"
    proc = subprocess.run([node, str(SCRIPT), "--src", str(src), "--tokens", str(tokens)],
                          cwd=root, capture_output=True, timeout=120)
    out = proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace")
    return proc.returncode, _ANSI.sub("", out)


def assert_reported(out, filename, line, needle):
    pattern = rf"[^\n]*{re.escape(filename)}:{line}: [^\n]*{re.escape(needle)}"
    assert re.search(pattern, out), f"输出里没有『{filename}:{line}: 规则: …{needle}…』这样的一行：\n{out[-1500:]}"


def test_g9_clean_samples_pass(tmp_path):
    """G9 / D04：合法写法（white-space、currentColor、transparent、全局关键字、系统颜色、已定义的 var）加被排除的文件，退出 0。"""
    for inside in (True, False):
        root = tmp_path / f"clean-{inside}"
        root.mkdir()
        src, tokens = make_src(root, tokens_inside=inside)
        code, out = run_contract(root, src, tokens)
        assert code == 0, f"干净样本（令牌文件{'在' if inside else '不在'} src 内）应退出 0，实际 {code}：\n{out[-1500:]}"


HEX_CASES = [
    ("hex3", "bad.css", ".a {\n  color: #123;\n}\n", 2, "#123"),
    ("hex4", "bad.css", ".a {\n  color: #1234;\n}\n", 2, "#1234"),
    ("hex6", "bad.css", ".a {\n  color: #1a2b3c;\n}\n", 2, "#1a2b3c"),
    ("hex8", "bad.css", ".a {\n  color: #11223344;\n}\n", 2, "#11223344"),
    ("hex6-upper", "bad.css", ".a {\n  background: #ABCDEF;\n}\n", 2, "#ABCDEF"),
    ("hex-in-border", "bad.css", ".a {\n  margin: 0;\n  border: 1px solid #fff;\n}\n", 3, "#fff"),
    ("hex-nested-dir", "deep/nested/bad.css", "\n\n.a { color: #123456; }\n", 3, "#123456"),
    ("hex-ts-string", "bad.ts", "export const x = 1;\nexport const c = '#123456';\n", 2, "#123456"),
    ("hex-tsx-anchor", "bad.tsx", "export const A = () => (\n  <a href=\"#add\">x</a>\n);\n", 2, "#add"),
]
FUNC_CASES = [(fn, "bad.css", f".a {{\n  background: {fn}{arg};\n}}\n", 2, f"{fn}")
              for fn, arg in (("rgb(", "1, 2, 3)"), ("rgba(", "1, 2, 3, .5)"), ("hsl(", "10 20% 30%)"),
                              ("hsla(", "10, 20%, 30%, .5)"), ("hwb(", "10 20% 30%)"), ("lab(", "50% 40 59)"),
                              ("lch(", "50% 40 59)"), ("oklab(", "0.5 0.1 0.1)"), ("oklch(", "0.5 0.1 120)"),
                              ("color(", "srgb 1 0 0)"))]
VAR_CASES = [
    ("undefined-var-css", "bad.css", ".a {\n  color: var(--tt-not-defined);\n}\n", 2, "--tt-not-defined"),
    ("undefined-var-fallback", "bad.css", ".a {\n  margin: var(--tt-no-such, 4px);\n}\n", 2, "--tt-no-such"),
    ("var-defined-in-component", "bad.css", ".a {\n  --tt-local: 4px;\n}\n", 2, "--tt-local"),
    ("undefined-var-ts-string", "bad.ts", "export const x = 1;\nexport const v = 'var(--tt-ghost)';\n", 2, "--tt-ghost"),
    ("undefined-var-tsx-string", "bad.tsx",
     "export const A = () => (\n  <div style={{ color: 'var(--tt-ghost2)' }}>x</div>\n);\n", 2, "--tt-ghost2"),
]
TSX_CASES = [
    ("tsx-style-hex", "bad.tsx", "export const A = () => (\n  <div style={{ color: '#123' }}>x</div>\n);\n", 2, "#123"),
    ("tsx-style-named", "bad.tsx", "export const A = () => (\n  <div style={{ color: 'red' }}>x</div>\n);\n", 2, "red"),
    ("tsx-style-named-camel", "bad.tsx",
     "export const A = () => (\n  <div style={{ backgroundColor: 'blue' }}>x</div>\n);\n", 2, "blue"),
    ("tsx-style-named-border", "bad.tsx",
     "export const A = () => (\n  <div style={{ borderColor: \"tomato\" }}>x</div>\n);\n", 2, "tomato"),
    ("tsx-style-rgba", "bad.tsx",
     "export const A = () => (\n  <div style={{ background: 'rgba(0,0,0,.5)' }}>x</div>\n);\n", 2, "rgba("),
    ("tsx-style-shadow-named", "bad.tsx",
     "export const A = () => (\n  <div style={{ boxShadow: '0 0 2px black' }}>x</div>\n);\n", 2, "black"),
]
NAMED_CSS_CASES = [
    ("named-color", "bad.css", ".a {\n  color: red;\n}\n", 2, "red"),
    ("named-background", "bad.css", ".a {\n  background: rebeccapurple;\n}\n", 2, "rebeccapurple"),
    ("named-border-shorthand", "bad.css", ".a {\n  border: 1px solid blue;\n}\n", 2, "blue"),
    ("named-box-shadow", "bad.css", ".a {\n  box-shadow: 0 0 2px black;\n}\n", 2, "black"),
]


@pytest.mark.parametrize("case", HEX_CASES + FUNC_CASES + VAR_CASES + TSX_CASES + NAMED_CSS_CASES,
                         ids=lambda c: c[0].replace("(", "-fn"))
def test_g9_violation_is_reported(tmp_path, case):
    """G9 / D04：十六进制（3/4/6/8 位）、颜色函数、命名颜色、未定义或组件内自定义的 --tt-*、TSX 写法各判违规：退出 1，
    输出含『文件:行号: 规则: 片段』一行；干净文件不受影响。"""
    _id, rel, content, line, needle = case
    src, tokens = make_src(tmp_path, {rel: content})
    code, out = run_contract(tmp_path, src, tokens)
    assert code == 1, f"{_id}: 应退出 1，实际 {code}：\n{out[-1500:]}"
    assert_reported(out, Path(rel).name, line, needle)
    for clean in ("a.css", "b.tsx", "c.ts", "tokens.css", "bad.test.tsx", "bad.test.ts", "notes.md", "data.json"):
        if clean != Path(rel).name:
            assert not re.search(rf"{re.escape(clean)}:\d+:", out), f"{_id}: 不该报告 {clean}：\n{out[-1500:]}"


def test_g9_all_148_named_colors_are_violations(tmp_path):
    """G9 / D04（合同 规则 2）：148 个 CSS 命名颜色作 color 取值都判违规，每个一行。"""
    assert len(CSS_NAMED_COLORS) == 148
    body = ".a {\n" + "".join(f"  color: {n};\n" for n in CSS_NAMED_COLORS) + "}\n"
    src, tokens = make_src(tmp_path, {"bad.css": body})
    code, out = run_contract(tmp_path, src, tokens)
    assert code == 1, f"应退出 1，实际 {code}"
    reported = {int(m) for m in re.findall(r"bad\.css:(\d+):", out)}
    missed = [n for i, n in enumerate(CSS_NAMED_COLORS, start=2) if i not in reported]
    assert not missed, f"这些命名颜色没被报告：{missed}"


COLOR_PROPS = ["color", "background", "background-color", "border", "border-top", "border-right", "border-bottom",
               "border-left", "border-color", "border-top-color", "border-right-color", "border-bottom-color",
               "border-left-color", "outline", "outline-color", "box-shadow", "fill", "stroke",
               "text-decoration-color", "caret-color"]


def test_g9_named_color_in_every_color_property(tmp_path):
    """G9 / D04（合同 规则 2）：命名颜色在合同列出的每个颜色类属性里都判违规。"""
    value_for = {"border": "1px solid red", "outline": "2px solid red", "box-shadow": "0 0 2px red"}
    for side in ("top", "right", "bottom", "left"):
        value_for[f"border-{side}"] = "1px solid red"
    body = ".a {\n" + "".join(f"  {p}: {value_for.get(p, 'red')};\n" for p in COLOR_PROPS) + "}\n"
    src, tokens = make_src(tmp_path, {"bad.css": body})
    code, out = run_contract(tmp_path, src, tokens)
    assert code == 1, f"应退出 1，实际 {code}"
    reported = {int(m) for m in re.findall(r"bad\.css:(\d+):", out)}
    missed = [p for i, p in enumerate(COLOR_PROPS, start=2) if i not in reported]
    assert not missed, f"这些属性里的命名颜色没被报告：{missed}"


def test_g9_multiple_violations_one_line_each(tmp_path):
    """G9（合同 命令行）：多处违规每处一行，行号准确。"""
    body = ".a {\n  color: #123;\n  margin: 0;\n  background: rgba(0, 0, 0, .5);\n  border: 1px solid red;\n  padding: var(--tt-zzz);\n}\n"
    src, tokens = make_src(tmp_path, {"bad.css": body})
    code, out = run_contract(tmp_path, src, tokens)
    assert code == 1
    lines = {int(m) for m in re.findall(r"bad\.css:(\d+): ", out)}
    assert lines == {2, 4, 5, 6}, f"应报告第 2、4、5、6 行，实际 {sorted(lines)}：\n{out[-1500:]}"


@pytest.mark.parametrize("which", ["src", "tokens"])
def test_g9_missing_path_is_readable_error(tmp_path, which):
    """G9（合同 契约检查）：--src 或 --tokens 指向不存在的目录或文件时，非 0 退出并给出可读错误（不是 JS 堆栈）。"""
    src, tokens = make_src(tmp_path)
    if which == "src":
        src = tmp_path / "no-such-dir"
    else:
        tokens = tmp_path / "no-such-tokens.css"
    code, out = run_contract(tmp_path, src, tokens)
    assert code != 0, f"--{which} 不存在时应非 0 退出，实际 {code}"
    assert out.strip(), "应有可读的错误输出"
    assert not re.search(r"^\s+at .+:\d+:\d+\)?\s*$", out, re.M) and "node:internal" not in out, f"错误输出不应是 JS 堆栈：\n{out[-800:]}"
    assert f"--{which}" in out or ("no-such-dir" if which == "src" else "no-such-tokens") in out, \
        f"错误信息应点名 --{which} 或路径：\n{out[-800:]}"


def test_g9_runs_from_any_cwd_with_absolute_paths(tmp_path):
    """G9：脚本用绝对路径 --src/--tokens 在别的 cwd 下也能跑（上面各例都是这样）；并确认缺省参数在 desktop/web 下对真实 src 退出 0 由 G5 负责。"""
    other = tmp_path / "elsewhere"
    other.mkdir()
    src, tokens = make_src(tmp_path)
    code, out = run_contract(other, src, tokens)
    assert code == 0, out[-800:]


# ---------------------------------------------------------------------------
# G10 组件探针与陈列页（D01；站主 Q4）
# ---------------------------------------------------------------------------

def test_g10_component_probe(pipeline):
    """G10：门禁运行时写入 desktop/web/gate-probe/probe-<唯一标识>.test.tsx，用 npm test -- gate-probe/<文件名> 运行。
    断言 5 个组件的导出、17 个状态各自的中文与 title 与色调、未知状态兜底、加载按钮 disabled 与 aria-busy、
    三种提示条的关闭按钮有无与 danger 的 role=alert，以及 App 陈列页列全变体、三个按钮切换 data-theme。"""
    assert pipeline.ran, pipeline.reason
    step = assert_step_ok(pipeline, "probe")
    assert pipeline.probe_file and pipeline.probe_file in step.out.replace("\\", "/"), \
        f"探针输出里没有探针文件名，可能没被 Vitest 选中：\n{step.tail}"
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m and int(m.group(1)) >= 17, f"探针应至少有 17 条通过：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), f"探针有失败或跳过：\n{step.tail}"


# ---------------------------------------------------------------------------
# D03 能机械检查的部分
# ---------------------------------------------------------------------------

def test_d03_new_tests_not_skipped():
    """D03（合同 Forbidden）：desktop/web 新增的测试里没有 skip、todo、only。弱化既有测试由终审读差异判断。"""
    tests = [p for d in ("src", "tests") for p in (WEB / d).rglob("*.test.*")] if (WEB / "tests").is_dir() else []
    assert tests, "desktop/web 里没有任何 *.test.* 文件（基线上目标尚未实现）"
    hits = []
    for path in tests:
        text = _read(path)
        for m in re.finditer(r"\b(?:it|test|describe)\.(?:skip|todo|only|skipIf|runIf)\b|\bx(?:it|describe)\(|\.only\(", text):
            hits.append(f"{path.relative_to(WEB)}: {m.group(0)}")
    assert not hits, "新增测试里有跳过或只跑一部分：\n" + "\n".join(hits)
