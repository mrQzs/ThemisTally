"""T050 战前门禁：「新建 profile 第二次打开时 Quizs 档案一直停在读取中」（T046 的 effect 竞态）
的黑盒基准测试（合同 t050-desktop-web-profile-archive-race.v1，基线 2020f80be9a26da12ba4a2c64b18572ce40842d6）。

被测对象是 ``desktop/web/src/writes/ProfileForm.tsx`` 读提供方档案的 effect：站主登记的卡死顺序是
「第二次打开 → 用户在 ``getRuntimes()`` 回来之前选了 quizs 运行时 → 读档案发出（标记置真）→
``getRuntimes()`` 回来、``setRuntimes`` 换了新数组 → effect 重跑：清理把在途结果作废，重跑时
『本次打开已经读过』仍为真，不再读 → 档案永远停在 loading」。同根的另外两条路径：取消后重开
（运行时留着上次的 quizs）、读档案途中切到非 quizs 再切回。

与 T046 门禁不同的两点：

- 本片不改文件清单（被测文件、包内测试都在基线上），**红点必须落在行为上**，所以流水线夹具不用
  「标记不在就提前返回」的写法——基线上照样起 npm、跑 Vitest 探针，race 探针里的用例 A / C 在
  未修的实现上是红的（停在 1 次读、界面停在「正在读 Quizs 的提供方档案…」），修好后转绿；
  用例 B 在基线上就是绿的（守住「修复不许变成每次重跑都重读」）。
- 复现竞态必须让 ``getRuntimes`` 与 ``getQuizsProviders`` 都返回**手动兑现**的 promise（合同
  Repository facts 按内核记录与 React 18.3.1 的 act 语义推得：两个已兑现 promise 的回调会在
  同一次 act 里跑完，不手动控制就复现不出竞态，用例在基线上也会绿）。探针里全部手动兑现。

结构：

- 静态断言（``test_s*``，不用流水线）：依赖冻结（package.json 与锁文件按基线字节冻结——本片
  dependency_changes: forbidden）。其余共享面（ProfileForm 的逐字文案、七段档位、执行端测试
  记号）由 T046 门禁长期钉着，这里不重复钉，免得后来片合法改动时旧门禁连锁红。
- 流水线断言（``test_p*`` / ``test_d*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、
  ``npm test``（全绿，含执行端在 ``tests/writes-profile-quizs.test.tsx`` 末尾追加的手动兑现
  用例）；race 探针写成 ``gate-probe/probe-<uid>-t050-race.test.tsx``，用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除。探针照包内测试的
  ``vi.mock('../src/api')`` 转调写法（可注入手动兑现的 promise），不 mock 被测组件，每份自带
  全部辅助函数。三条用例：
  - A（站主登记的顺序）：第二次打开、在 ``getRuntimes()`` 兑现之前选 quizs 运行时 → 列表换新
    数组作废在途读 → 重跑照样再读一次 → 档案读到（Select 两项自动选第一项、档位
    low/medium/high、不再写「正在读」、命令带 ``--runtime=quizs-cli --model=stepfun/step-5-preview``、
    [确认…] 可点）；迟到的第 1 次读（失败信封）回来照旧丢弃；共 2 次读。基线红。
  - B：档案先读完（第 1 次读兑现 ok）之后列表才换新数组 → effect 重跑**不再读第二次**（仍 1 次）、
    档案仍显示；再把 runtime 切到 pi 再切回 → 已读到的档案仍显示、不重复读。基线绿、候选绿。
  - C（同根第三条路径）：第 1 次读还在路上时切到 pi 再切回 quizs → 切回时重新读（2 次）、档案
    照样读到；迟到的第 1 次读回来照旧丢弃。基线红。

门禁端按最合理读法定下的地方（交付信「下游须知」里逐条列出，终审可改）：见文件末尾 ``ASSUMPTIONS``。
"""

import hashlib
import os
import re
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB = REPO_ROOT / "desktop" / "web"
WEB_REL = "desktop/web"

PROFILEFORM_REL = f"{WEB_REL}/src/writes/ProfileForm.tsx"
FORM_TEST_REL = f"{WEB_REL}/tests/writes-profile-quizs.test.tsx"

# 依赖冻结（合同 D08：package.json 与锁文件一个字节都不动；值与 T043/T046 门禁一致）
BASELINE_DIGESTS = {
    f"{WEB_REL}/package.json": (820, "094d3622e54097e0f50f0ab2a71a5caa22491dba9d3ac6ef83047426f8c57f5a"),
    f"{WEB_REL}/package-lock.json": (108793, "1bc4e1fbfeb02a17280d0de1d98a5f3b2721fa91229c271c66d590d059d82d28"),
}

# G01 的超时是 600s：夹具总预算压在 550s 以内（pytest 启动、静态用例与子进程收拾的开销都在预算外）
PIPELINE_BUDGET = 550
STEP_CAPS = {"npm ci": 240, "npm ci --offline": 240, "npm test": 300, "probe": 120}

ASSUMPTIONS = (
    "探针只按行为断言，不钉变量名（settled / archiveRead）与 effect 的写法（合同下游须知第 1 条）",
    "用例 B 在基线上也是绿的：它守住「修复不许变成每次重跑都重读」（合同 D03），不是缺陷证据；"
    "基线上的红点只落在用例 A（作废后重读 = 2 次）与用例 C（切回重读 = 2 次）——基线都停在 1 次、"
    "界面停在「正在读 Quizs 的提供方档案…」",
    "race 探针的失败断言顺序：先钉「作废/切回后读到 2 次读」，再钉界面形态（Select、选项、不再"
    "「正在读」），让基线上的红点带着清晰的说明落在次数上",
    "现有 writes-profile-quizs.test.tsx 的 1 次 / 2 次 / 0 次断言与 T046 门禁的 form 探针一条不"
    "动：本门禁不重复跑它们（由 npm test 全量与 R01 的 T046 门禁覆盖），只加本片的竞态行为",
    "执行端在 writes-profile-quizs.test.tsx 末尾追加的手动兑现用例（合同第 3 步）由 npm test 全量"
    "覆盖（P1），本门禁不再静态钉追加内容的记号——后来片合法重写那些用例时不许被本门禁误伤",
    "静态断言只冻结两份依赖文件（本片 D08）：ProfileForm 的逐字文案、七段档位、quizs 接线与执行端"
    "测试记号由 T046 门禁长期钉着，这里不重复",
)


# ---------------------------------------------------------------------------
# 通用小工具（只读仓库文件；模块级不做任何仓库 IO）
# ---------------------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def read_rel(rel):
    return _read(REPO_ROOT / rel)


def need_file(rel):
    """断言仓库里的文件存在，返回相对路径。"""
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在"
    return rel


def file_digest(path):
    path = Path(path)
    if not path.is_file():
        return None
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return len(data), hashlib.sha256(data).hexdigest()


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:40])


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
# S 系列：静态断言（不用流水线；基线上绿——共享面回归由 R01 的旧门禁覆盖）
# ---------------------------------------------------------------------------

def test_s01_dependencies_frozen():
    """S01 / D08：desktop/web/package.json 与 package-lock.json 按基线字节冻结（本片不新增、
    不升级、不删依赖；两份文件一个字节都不许动）。"""
    problems = []
    for rel, want in BASELINE_DIGESTS.items():
        got = file_digest(REPO_ROOT / rel)
        if got != want:
            problems.append(f"{rel} 应按基线字节冻结（行尾归一 LF）：{got} != {want}")
    fail_if(problems, "依赖文件冻结（S01）")


# ---------------------------------------------------------------------------
# race 探针（写在 desktop/web/gate-probe/ 下，npm test -- <文件> 跑；自带全部辅助函数）
# ---------------------------------------------------------------------------

PROBE_RACE = r'''// T050 门禁 race 探针：读提供方档案的 effect 竞态（合同 t050 行为口径，不钉实现写法）。
// 复现竞态的关键：getRuntimes 与 getQuizsProviders 都换成手动兑现的 promise——两个已兑现
// promise 的回调会在同一次 act 里跑完，不手动控制就复现不出「列表换数组作废在途读」。
// 写法照 tests/writes-profile-quizs.test.tsx：vi.mock('../src/api') 的替身默认转调真实现。
import { cleanup, fireEvent, render, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const hoisted = vi.hoisted(() => ({
  spies: {} as Record<string, { mock: { calls: unknown[] }; mockClear: () => void }>,
  overrides: {} as Record<string, (...args: unknown[]) => Promise<unknown>>,
}));
vi.mock('../src/api', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>;
  const out: Record<string, unknown> = { ...actual };
  for (const [name, fn] of Object.entries(actual)) {
    if (typeof fn === 'function') {
      const spy = vi.fn((...args: unknown[]) =>
        hoisted.overrides[name] ? hoisted.overrides[name](...args) : (fn as (...a: unknown[]) => unknown)(...args),
      );
      hoisted.spies[name] = spy;
      out[name] = spy;
    }
  }
  return out;
});

const { NewProfileAction } = await import('../src/writes/ProfileForm');

// 运行时两行（与包内测试同款）：第二行的 adapter 是 quizs（id 与 adapter 不同名）。
const RT_ENV = {
  ok: true, exit_code: 0,
  data: {
    runtimes: [
      { id: 'pi', adapter: 'pi', source: 'env', command: ['pi'], notes: '' },
      { id: 'quizs-cli', adapter: 'quizs', source: 'env', command: ['quizs'], notes: '' },
    ],
  },
  output: [], messages: [], command: ['config', 'runtime', 'list'], elapsed_ms: 0,
};
// 档案 ok 信封（照 src/mock/quizs.ts 的 PROVIDER_ROWS 两行；信封形状照 quizsProvidersEnvelope）。
const OK_PROVIDERS_ENV = {
  ok: true, exit_code: 0,
  data: {
    providers: [
      { provider: 'stepfun', model: 'step-5-preview', thinking: ['low', 'medium', 'high'], billing: 'step_plan_credits' },
      { provider: 'deepseek', model: 'deepseek-chat', thinking: ['low', 'high'], billing: 'deepseek_prepaid_balance' },
    ],
  },
  output: [], messages: [], command: ['config', 'quizs', 'providers', '--json'], elapsed_ms: 0,
};
// 失败信封：只给「迟到的第 1 次读」用——回晚了必须被丢掉，不许盖掉读到的档案。
const BROKEN_PROVIDERS_ENV = {
  ok: false, exit_code: 1, data: null,
  output: [], messages: ['ERROR: 手动兑现的迟到失败信封'], command: [], elapsed_ms: 0,
};

// 手动兑现：promise 的兑现时机由测试掌握。
function deferred<T = unknown>(): { promise: Promise<T>; resolve: (v: T) => void } {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}

beforeEach(() => {
  vi.useFakeTimers();
  window.location.hash = '';
  Object.keys(hoisted.overrides).forEach((k) => delete hoisted.overrides[k]);
  Object.values(hoisted.spies).forEach((s) => s.mockClear());
  set('getRuntimes', () => Promise.resolve(RT_ENV));
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  window.location.hash = '';
});

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const modalDialogs = () => Array.from(document.querySelectorAll('[role="dialog"][aria-modal="true"]')) as HTMLElement[];
const hasIdLabel = (d: Element) => Array.from(d.querySelectorAll('label')).some((l) => text(l) === 'ID');
const formDialog = () => modalDialogs().find(hasIdLabel) ?? null;
const needFormDialog = () => {
  const d = formDialog();
  expect(d, '表单对话框应开着').not.toBeNull();
  return d as HTMLElement;
};
const buttonByText = (root: ParentNode, label: string) =>
  Array.from(root.querySelectorAll('button')).find((b) => text(b) === label) as HTMLButtonElement | undefined;
function controlByLabel(d: HTMLElement, labelText: string): HTMLInputElement | HTMLSelectElement {
  const label = Array.from(d.querySelectorAll('label')).find((l) => text(l) === labelText) as HTMLElement | undefined;
  expect(label, `应有 label「${labelText}」`).toBeTruthy();
  const forId = label!.getAttribute('for');
  const hit = Array.from(d.querySelectorAll('input, select')).find((el) => el.id === forId) as HTMLInputElement | HTMLSelectElement;
  expect(hit, `label 关联的控件「${labelText}」应在`).toBeTruthy();
  return hit;
}
const thinkingGroup = (d: HTMLElement) => d.querySelector('[role="radiogroup"][aria-label="thinking"]') as HTMLElement;
const segTexts = (g: HTMLElement) => Array.from(g.querySelectorAll('[role="radio"]')).map((b) => text(b as HTMLElement));
const modelOptions = (d: HTMLElement) =>
  Array.from((controlByLabel(d, '模型') as HTMLSelectElement).querySelectorAll('option')).map((o) => (o as HTMLOptionElement).value);
const formConfirm = (d: HTMLElement) => buttonByText(d, '确认…') as HTMLButtonElement;
async function settle() {
  await act(async () => {
    for (let i = 0; i < 12; i += 1) await Promise.resolve();
  });
}
async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
function set(name: string, value: (...args: unknown[]) => Promise<unknown>) {
  hoisted.overrides[name] = value;
}
const spyCalls = (name: string) => hoisted.spies[name]?.mock.calls.length ?? 0;
async function openNew() {
  render(<NewProfileAction />);
  fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
  await settle();
  return needFormDialog();
}

// 三条用例共用的开场（站主登记的顺序）：先打开一次让运行时列表就位（已兑现的桩）、取消；
// 再换成手动兑现的两个读函数，在同一个已挂载的组件上再打开一次（不重新 render），回到
// 「getRuntimes 还没兑现、运行时列表还是旧数组」的第二次打开；填 ID、选 quizs 运行时，
// 发出第 1 次档案读（还在路上）。返回手动兑现的把手。
async function secondOpenWithDeferredReads(id: string) {
  window.location.hash = '#/roles?write=ok&quizs=ok';
  const first = await openNew();
  expect((controlByLabel(first, 'runtime') as HTMLSelectElement).value, '夹具自证：第一次打开后 runtime 落在 pi').toBe('pi');
  fireEvent.click(buttonByText(first, '取消') as HTMLButtonElement);
  await settle();
  const rt = deferred<typeof RT_ENV>();
  const reads = [deferred(), deferred(), deferred()];
  let n = 0;
  set('getRuntimes', () => rt.promise);
  set('getQuizsProviders', () => reads[n++]?.promise ?? new Promise(() => {}));
  fireEvent.click(buttonByText(document.body, '新建 profile') as HTMLButtonElement);
  await settle();
  const d = needFormDialog();
  fireEvent.change(controlByLabel(d, 'ID'), { target: { value: id } });
  fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'quizs-cli' } });
  await settle();
  return { d, rt, reads };
}

describe('T050 竞态：第二次打开与读档案途中 effect 重跑', () => {
  it('A 第二次打开、getRuntimes 回来之前选 quizs：列表换数组作废在途读，重跑照样再读，档案读到', async () => {
    const { d, rt, reads } = await secondOpenWithDeferredReads('t050-a');
    expect(spyCalls('getQuizsProviders'), '选了 quizs 运行时发出第 1 次读（还在路上）').toBe(1);
    expect(text(d), '夹具自证：界面停在正在读').toContain('正在读 Quizs 的提供方档案…');
    expect(controlByLabel(d, '模型').tagName, '夹具自证：读取中模型是手填').toBe('INPUT');
    rt.resolve(RT_ENV);
    await settle();
    expect(spyCalls('getQuizsProviders'), '列表换新数组作废在途读后重跑照样再读（作废一次 + 重读一次）').toBe(2);
    reads[1].resolve(OK_PROVIDERS_ENV);
    await settle();
    const model = controlByLabel(d, '模型') as HTMLSelectElement;
    expect(model.tagName, '档案读到后模型是档案 Select').toBe('SELECT');
    expect(modelOptions(d)).toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(model.value, '新建自动选档案第一项').toBe('stepfun/step-5-preview');
    expect(segTexts(thinkingGroup(d)), '档位按档案给').toEqual(['low', 'medium', 'high']);
    expect(text(d), '不再停在「正在读」').not.toContain('正在读 Quizs 的提供方档案…');
    await advance(350);
    expect(text(d), '命令带 --runtime=quizs-cli --model=provider/model').toContain('--runtime=quizs-cli --model=stepfun/step-5-preview');
    expect(formConfirm(d).disabled, '档案读到、预览回话之后 [确认…] 才可点（预览有 300ms 防抖，须先推进假计时器）').toBe(false);
    reads[0].resolve(BROKEN_PROVIDERS_ENV);
    await settle();
    expect((controlByLabel(d, '模型') as HTMLSelectElement).tagName, '迟到的第 1 次读回来不改界面').toBe('SELECT');
    expect(modelOptions(d)).toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(spyCalls('getQuizsProviders')).toBe(2);
  });

  it('B 档案读完之后列表换数组或切走再切回：不再读第二次，已读到的档案仍显示', async () => {
    const { d, rt, reads } = await secondOpenWithDeferredReads('t050-b');
    expect(spyCalls('getQuizsProviders')).toBe(1);
    reads[0].resolve(OK_PROVIDERS_ENV);
    await settle();
    expect((controlByLabel(d, '模型') as HTMLSelectElement).tagName, '夹具自证：档案读到了').toBe('SELECT');
    rt.resolve(RT_ENV);
    await settle();
    expect(spyCalls('getQuizsProviders'), '读完之后 effect 再重跑不再读第二次').toBe(1);
    expect((controlByLabel(d, '模型') as HTMLSelectElement).tagName, '已读到的档案仍在').toBe('SELECT');
    expect(modelOptions(d)).toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'pi' } });
    await settle();
    fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'quizs-cli' } });
    await settle();
    expect(spyCalls('getQuizsProviders'), '切到非 quizs 再切回不重复读').toBe(1);
    expect((controlByLabel(d, '模型') as HTMLSelectElement).tagName, '切回后已读到的档案仍显示').toBe('SELECT');
    expect(modelOptions(d)).toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
  });

  it('C 读档案途中（结果还在路上）切到 pi 再切回 quizs：切回时重新读，档案照样读到', async () => {
    const { d, reads } = await secondOpenWithDeferredReads('t050-c');
    expect(spyCalls('getQuizsProviders')).toBe(1);
    fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'pi' } });
    await settle();
    fireEvent.change(controlByLabel(d, 'runtime'), { target: { value: 'quizs-cli' } });
    await settle();
    expect(spyCalls('getQuizsProviders'), '结果还在路上时切走作废这次读，切回时重读').toBe(2);
    reads[1].resolve(OK_PROVIDERS_ENV);
    await settle();
    const model = controlByLabel(d, '模型') as HTMLSelectElement;
    expect(model.tagName, '切回后档案照样读到').toBe('SELECT');
    expect(modelOptions(d)).toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(text(d), '不再停在「正在读」').not.toContain('正在读 Quizs 的提供方档案…');
    reads[0].resolve(BROKEN_PROVIDERS_ENV);
    await settle();
    expect((controlByLabel(d, '模型') as HTMLSelectElement).tagName, '迟到的第 1 次读回来不改界面').toBe('SELECT');
    expect(modelOptions(d)).toEqual(['stepfun/step-5-preview', 'deepseek/deepseek-chat']);
    expect(spyCalls('getQuizsProviders')).toBe(2);
  });
});
'''

PROBE_SPECS = {
    "race": (PROBE_RACE, (PROFILEFORM_REL, FORM_TEST_REL)),
}
PROBE_ORDER = ("race",)


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针
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
        self.probe_files = {}
        self.probe_skipped = {}
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
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    start = time.monotonic()
    proc = subprocess.Popen(argv, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
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
    # 这台机器上线用的 QUIZS_* 不进 vitest 子进程（与 tests/conftest.py 的 no_ambient_quizs 同一口径）。
    for name in ("QUIZS_CMD", "QUIZS_LIVE_PLAN", "QUIZS_PROVIDER_PROFILE", "QUIZS_QUALIFICATION"):
        env.pop(name, None)
    return env


def git_status_set():
    proc = subprocess.run(["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"],
                          cwd=REPO_ROOT, capture_output=True, timeout=120)
    assert proc.returncode == 0, f"git status 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


def t050_targets_present():
    """本片被测的两份文件在不在（基线上就在；不在说明基线与合同不符，照常返回 False、
    夹具给出理由后不跑 npm）。"""
    try:
        return (REPO_ROOT / PROFILEFORM_REL).is_file() and (REPO_ROOT / FORM_TEST_REL).is_file()
    except OSError:
        return False


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    if not t050_targets_present():
        pipe.reason = (f"被测文件不在（{PROFILEFORM_REL} / {FORM_TEST_REL}），与合同 Repository facts 不符，未调用 npm")
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

    def run_step(name, argv, label=None):
        remaining = deadline - time.monotonic()
        if remaining <= 5:
            pipe.stopped_reason = f"{label or name} 之前整体预算 {PIPELINE_BUDGET}s 已用完，未运行"
            return None
        timeout = min(STEP_CAPS[name], remaining)
        code, timed_out, out, seconds = run_capture(argv, WEB, timeout, env)
        step = Step(label or name, argv, code, timed_out, out, seconds)
        pipe.steps[label or name] = step
        return step

    probe_dir = WEB / "gate-probe"
    written = []
    try:
        # 依赖已在（执行端 Setup 装过）就不重装：省下的时间留给 Vitest 与探针。
        # 本片红点必须在行为上（基线上被测文件都在），所以基线上也照常起 npm。
        if (WEB / "node_modules" / "vitest").is_dir():
            pipe.steps["npm ci"] = Step("npm ci", [], 0, False, "node_modules 已在，未重装依赖", 0.0)
        else:
            ci = run_step("npm ci", [npm, "ci"])
            if ci is not None and ci.code != 0:
                run_step("npm ci --offline", [npm, "ci", "--offline"])
        ci_ok = any(pipe.steps.get(k) is not None and pipe.steps[k].code == 0
                    for k in ("npm ci", "npm ci --offline"))
        if ci_ok:
            run_step("npm test", [npm, "test"])
            if pipe.steps.get("npm test") is not None and pipe.steps["npm test"].code == 0:
                uid = uuid.uuid4().hex[:12]
                for key in PROBE_ORDER:
                    missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                    if missing:
                        pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                        continue
                    name = f"probe-{uid}-t050-{key}.test.tsx"
                    probe_dir.mkdir(exist_ok=True)
                    path = probe_dir / name
                    written.append(path)
                    path.write_text(PROBE_SPECS[key][0], encoding="utf-8", newline="\n")
                    pipe.probe_files[key] = name
                    run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        else:
            pipe.stopped_reason = "npm ci（含 --offline 兑底）失败，后续步骤未运行"
    finally:
        for path in written:
            try:
                path.unlink()
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


def assert_probe_ok(pipe, key):
    """探针 key 在候选上全部通过：退出码 0、输出里有探针文件名、通过数不少于 it( 行数、没有失败跳过待办。"""
    assert pipe.ran, pipe.reason
    assert key not in pipe.probe_skipped, pipe.probe_skipped[key]
    step = assert_step_ok(pipe, f"probe:{key}")
    name = pipe.probe_files.get(key)
    assert name and name in step.out.replace("\\", "/"), \
        f"探针输出里没有探针文件名，可能没被 Vitest 选中：\n{step.tail}"
    want = probe_count(PROBE_SPECS[key][0])
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m and int(m.group(1)) >= want, f"探针 {key} 应至少有 {want} 条通过：\n{step.tail}"
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), f"探针 {key} 有失败或跳过：\n{step.tail}"


# ---------------------------------------------------------------------------
# P / D 系列：流水线断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、D08、D10：npm 依赖（已在就跳过）、npm test（全绿，含执行端在
    writes-profile-quizs.test.tsx 末尾追加的手动兑现用例与原有 15 条用例）都退出 0；
    依赖文件一个字节没动；gate-probe/ 没有留下。"""
    assert any(pipeline.steps.get(k) is not None and pipeline.steps[k].code == 0
               for k in ("npm ci", "npm ci --offline")), \
        f"npm ci（含 --offline 兑底）未成功：{pipeline.stopped_reason or pipeline.reason}"
    step = assert_step_ok(pipeline, "npm test")
    m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
    assert m, f"npm test 输出里没有通过计数：\n{step.tail}"
    assert int(m.group(1)) > 0
    assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), \
        f"npm test 有失败、跳过或待办的用例：\n{step.tail}"
    assert pipeline.digests_before == pipeline.digests_after, \
        "npm 流水线不许改动 desktop/web/package.json 与 package-lock.json"
    assert not pipeline.gate_probe_left, "gate-probe/ 目录在探针后应清掉"


def test_p2_worktree_unchanged_by_pipeline(pipeline):
    """P2（守卫）：流水线与探针前后 git status 相同；gate-probe/ 没有留下。"""
    assert pipeline.ran, pipeline.reason
    assert pipeline.status_before is not None and pipeline.status_after is not None
    appeared = sorted(pipeline.status_after - pipeline.status_before)
    gone = sorted(pipeline.status_before - pipeline.status_after)
    assert not appeared and not gone, f"git status 前后不同：新增 {appeared[:20]}，消失 {gone[:20]}"


def test_d01_d02_d04_probe_race(pipeline):
    """race 探针 / D01、D02、D04、D07：第二次打开、在 getRuntimes() 兑现之前选 quizs 运行时
    之后，档案仍读到（Select 两项自动选第一项、档位 low/medium/high、不再「正在读」、命令带
    --runtime=quizs-cli --model=stepfun/step-5-preview、[确认…] 可点）；作废的那次读回来照旧丢弃；
    档案读完之后列表换数组或切走再切回不再读第二次、已读到的档案仍显示；读档案途中切到非 quizs
    再切回重新读到档案。基线上 A / C 红（停在 1 次读、界面停在「正在读」），修好后三条全绿。"""
    assert_probe_ok(pipeline, "race")
