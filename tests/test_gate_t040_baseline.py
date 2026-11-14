"""T040 战前门禁：桌面端前端第 6 片——写操作的真实模式收尾（T037 片 2，D6）的黑盒基准测试
（合同 t040-desktop-web-writes-2.v1，基线 94c960f5）。

被测对象是 ``desktop/web/``：``src/writes/useWriteFlow.ts`` 的重读演示情景（reread-fail /
reread-fail-exit1）只在 ``liveClient() === null``（非真实模式）时认、``runPreview`` 在
``needs_yes`` 为真且没有正在运行的 attempt 时把逐字的原因句排在 notes 最前面；
``src/api.ts`` 第 246 行的注释去掉「501」字样；``src/writes/useLivePreview.ts`` 第 2 行的注释改成
与真实模式相符的说法；新增真实模式的流程集成测试（``tests/writes-live-flow.test.tsx``，可选
``tests/writes-live-preview.test.tsx``），只经 ``setLiveClientForTests`` 注入假服务。

基线（94c960f5）上 ``useWriteFlow`` 的重读情景不看模式、``data.needs_yes`` 没用、api.ts 里还有
「501」、``useLivePreview`` 的注释还写着「只读演示数据，不联网」、两份新测试不存在，所以本文件的
失败落在「记号不在」「注释没改」「文件不在」「探针断言红」上，不是导入、收集或语法错误：模块级只
导入标准库，所有仓库文件的读取都发生在用例函数里；流水线（npm、Vitest、探针）放在 ``pipeline``
会话级夹具里（全量 pytest 默认跳过，点名运行本文件才跑；候选里还没有本片的新测试文件时，夹具不调
npm——基线上没有新测试可跑，也避免联网装依赖，照 T038 门禁的写法）。

结构：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：useWriteFlow 的真实模式门与禁词（S01）；
  needs_yes 原因句逐字在位且触发条件挨着它（S02）；api.ts 不再出现「501」、新注释逐字在位（S03）；
  useLivePreview 的新注释与 ``DEBOUNCE_MS = 300``（S04）；新测试文件在位、注入方式与合同点名的
  情景记号（S05）；夹具模式的 reread-fail 用例照旧保留（S06，兼容性）。
- 流水线断言（``test_p*``，``pipeline`` 会话级夹具）：npm 依赖（已在就跳过重装）、npm test（全绿）、
  npm run build；探针逐份写成 ``gate-probe/probe-<uid>-t040-<键>.test.tsx``，各用
  ``npm test -- gate-probe/<文件名>`` 跑，``finally`` 里删除（探针单份封 60s，540s 总预算里
  npm test、build 之后两份探针都还能跑）。探针注入假 LiveClient（get/post/getRaw
  都记路径、正文与时限），不 vi.mock 被测模块；每份自带全部辅助函数，不跨文件共享作用域。
  - flow：经真实 ``useWriteFlow``（PresetBar 驱动 preset.use）——成功路径的真实路由（预览正文
    ``{action, args}``、执行路径与正文、时限 90 秒、轻提示只在重读之后）；needs_yes 的三种情形
    （原因句逐字且排在原样路径行之前 / running 非空不加 / needs_yes 为假不加）；真实模式门
    （hash 带 ``?write=reread-fail`` 时照常重读、不出「重新读取失败」）；真实模式下的重读失败
    （读 reject →「命令已成功，但重新读取失败，请刷新」）。
  - preview：``useLivePreview`` 在真实模式下——299ms 不发、300ms 恰好发一次 ``POST /api/v1/preview``
    （正文与时限）；返回的命令去掉 ``--dry-run`` 与 ``--json``；400 信封显示 messages 原文；post
    reject 显示「预览失败：服务没有回应」。

门禁做不到、留给人的项：真 Electron 窗口里的写操作冒烟（站主的验收）、视觉与读屏核对。

门禁端按最合理读法定下的地方（交付信「下游须知」里也写）：

- ``useWriteFlow`` 对 ``../live/mode`` 的 import 必须是只引 ``liveClient`` 一个符号的花括号写法
  （合同写死）；代码里不出现 ``liveModeIsReal``（去注释后查，注释里解释「为什么不用它」不算用）。
- 真实模式门的判据在 ``readSnapshot`` 函数体里写成 ``liveClient() === null``（空白容忍），且
  ``reread-fail`` 与 ``reread-fail-exit1`` 两个情景值仍留在函数体里；useWriteFlow.ts 里要有一条
  注释提到 ``liveClient``（合同要求「注释写明判据与理由」）。
- 原因句逐字照合同（提成常量再引用也算）；触发条件与「排在 notes 最前面」的语义由 P2 探针在真实
  实现上验证，静态新言只查句子在位与代码里用到 ``data.needs_yes``（基线上组 content 时没看它）。
- 新测试文件的情景记号按合同 Behavior contract 的表查文案（逐字照 ``WriteConfirmDialog.tsx`` 与
  ``writeOutcome.ts``），两份新文件合在一起算；``writes-live-flow.test.tsx`` 必须存在，
  ``writes-live-preview.test.tsx`` 可选（预览用例可以放进前一份）。
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
WEB_REL = "desktop/web"
WEB = REPO_ROOT / "desktop" / "web"
SRC_REL = f"{WEB_REL}/src"
TESTS_REL = f"{WEB_REL}/tests"

FLOW_REL = f"{SRC_REL}/writes/useWriteFlow.ts"
PREVIEW_HOOK_REL = f"{SRC_REL}/writes/useLivePreview.ts"
API_REL = f"{SRC_REL}/api.ts"
MODE_REL = f"{SRC_REL}/live/mode.ts"
PRESETBAR_REL = f"{SRC_REL}/pages/readonly1/roles-PresetBar.tsx"
NEW_FLOW_TEST_REL = f"{TESTS_REL}/writes-live-flow.test.tsx"
NEW_PREVIEW_TEST_REL = f"{TESTS_REL}/writes-live-preview.test.tsx"
FIXTURE_FLOW_TEST_REL = f"{TESTS_REL}/writes-flow.test.tsx"
MOCKWRITES_REL = f"{SRC_REL}/mock/writes.ts"

# 合同 Behavior contract 逐字写死的原因句（D02）。
REASON_SENTENCE = "有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。"
# api.ts 第 246 行改后的注释（D03，逐字照合同）。
API_COMMENT_NEW = "// 缺任何一样（含 data 缺 preview）就原样透传：不签发确认号，状态码与信封都不改。"
# useLivePreview.ts 第 2 行改后的注释（D04，逐字照合同）。
PREVIEW_COMMENT_NEW = "// 夹具模式下读演示数据，真实模式下走服务的预览。"

# 新测试里合同点名的情景记号（两份新文件合并查；文案逐字照 WriteConfirmDialog/writeOutcome）。
NEW_TEST_MARKS = (
    "setLiveClientForTests",
    "/api/v1/preview",
    "/api/v1/presets",
    "/api/v1/operations",
    "已切换到方案",
    "配置在你确认之前被改动了",
    "确认已失效",
    "服务繁忙，请稍后再确认",
    "连接中断，正在确认结果",
    "结果未知，请在历史与审计里核对",
    "服务出错",
    "超时",
    "已部分写入",
    "内核拒绝",
    "reread-fail",
    "命令已成功，但重新读取失败",
    "有 attempt 正在运行",
    REASON_SENTENCE,
    "299",
    "--dry-run",
    "预览失败：服务没有回应",
)

# 四个浏览器网络整词（src 下除 live/ 以外不许出现，T027 S10；注释与字符串都算）
NETWORK_RE = re.compile(r"(?<![A-Za-z0-9_$])(?:fetch|XMLHttpRequest|EventSource|WebSocket)(?![A-Za-z0-9_$])")

# --------------------------------------------------------------------------- 
# 通用小工具（与 T036/T037/T038 门禁同一口径）
# ---------------------------------------------------------------------------

def _norm(text):
    return text.replace("\r\n", "\n")


def _read(path):
    return _norm(Path(path).read_text(encoding="utf-8"))


def read_rel(rel):
    return _read(REPO_ROOT / rel)


def need_file(rel):
    path = REPO_ROOT / rel
    assert path.is_file(), f"{rel} 不存在（基线上还没有实现）"
    return path


def file_digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def git(*args, check=False):
    proc = subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, timeout=120)
    if check:
        assert proc.returncode == 0, f"git {' '.join(args)} 失败：{proc.stderr.decode('utf-8', 'replace')}"
    return proc


def git_status_set():
    proc = git("status", "--porcelain=v1", "--untracked-files=all", "-z", check=True)
    return {entry for entry in proc.stdout.decode("utf-8", "replace").split("\0") if entry}


_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


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


# TS 注释剥离（与 T010/T034/T036/T037 的同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_usewriteflow_real_mode_gate():
    """S01 / D01：useWriteFlow.ts——从 ``../live/mode`` 只引 ``liveClient`` 一个符号；代码里不用
    ``liveModeIsReal``；``readSnapshot`` 函数体里的重读演示情景（reread-fail / reread-fail-exit1）
    带着 ``liveClient() === null`` 的前提；有一条注释提到判据；四个网络整词一个不许有。"""
    need_file(FLOW_REL)
    text = read_rel(FLOW_REL)
    m = re.search(r"import\s*\{([^}]*)\}\s*from\s*['\"]\.\./live/mode['\"]", text)
    assert m, "useWriteFlow.ts 应有 import { liveClient } from '../live/mode'（只引这一个符号）"
    imported = {part.strip() for part in m.group(1).split(",") if part.strip()}
    assert imported == {"liveClient"}, \
        f"对 ../live/mode 应只引 liveClient 一个符号（合同写死），实际 {sorted(imported)}"
    code = strip_ts_comments(text)
    assert "liveModeIsReal" not in code, \
        "useWriteFlow.ts 的代码里不该用 liveModeIsReal（不认测试注入，合同写死用 liveClient()）"
    block = re.search(r"async function readSnapshot[\s\S]*?(?=\nexport function)", text)
    assert block, "useWriteFlow.ts 里应仍有 async function readSnapshot（重读情景的门开在这里）"
    body = block.group(0)
    assert re.search(r"liveClient\(\)\s*===\s*null|!liveClient\(\)", body), \
        "readSnapshot 的重读演示情景应带 liveClient() === null（或 !liveClient()）的前提" \
        "（真实模式下不认 ?write= 的 reread 情景；判据要写在函数体里，不要提成函数外的具名布尔量）"
    assert "reread-fail" in body and "reread-fail-exit1" in body, \
        "reread-fail 与 reread-fail-exit1 两个情景值应仍在 readSnapshot 里（夹具模式照旧认）"
    assert re.search(r"//[^\n]*liveClient", text), \
        "useWriteFlow.ts 应有一条注释提到 liveClient（合同：注释写明判据与理由）"
    for hit in NETWORK_RE.finditer(text):
        pytest.fail(f"{FLOW_REL} 出现网络接口名 {hit.group(0)}（连注释都不许，T027 S10）")


def test_s02_needs_yes_reason_sentence():
    """S02 / D02：useWriteFlow.ts——原因句逐字在位，且代码里用到了 ``data.needs_yes``（基线上
    ``useWriteFlow`` 根本没用 needs_yes）。触发条件（needs_yes 为真且 running_attempts 为空才加、
    排在 notes 最前面）的逐字语义由 P2 探针在真实实现上验证，静态新言不写死实现写法。"""
    need_file(FLOW_REL)
    text = read_rel(FLOW_REL)
    assert REASON_SENTENCE in text, \
        f"useWriteFlow.ts 应包含逐字的原因句 {REASON_SENTENCE!r}（合同 Behavior contract 写死）"
    code = strip_ts_comments(text)
    assert "needs_yes" in code, \
        "useWriteFlow.ts 的代码里应用到 data.needs_yes（基线上组 content 时没看它；注释里提一句不算）"
    assert "running_attempts" in code, "useWriteFlow.ts 的代码里应仍有 running_attempts（running 那行照旧）"


def test_s03_api_comment_no_501():
    """S03 / D03：api.ts——整个文件不再出现「501」三个字符；第 246 行的新注释逐字在位。"""
    need_file(API_REL)
    text = read_rel(API_REL)
    assert "501" not in text, \
        "api.ts 里不该再出现「501」（站主采纳的终审意见 4：将来恢复查 501 的断言时不误伤；连注释都不许有）"
    assert API_COMMENT_NEW in text, f"api.ts 应包含逐字的新注释 {API_COMMENT_NEW!r}"
    assert "不改写成 501" not in text, "api.ts 的旧注释（「不改写成 501」）应已替换"


def test_s04_live_preview_comment():
    """S04 / D04：useLivePreview.ts——第 2 行的新注释逐字在位；旧说法不在；``DEBOUNCE_MS = 300``
    与其余代码保住（T024 S14 依赖「300」记号）。"""
    need_file(PREVIEW_HOOK_REL)
    text = read_rel(PREVIEW_HOOK_REL)
    assert PREVIEW_COMMENT_NEW in text, \
        f"useLivePreview.ts 应包含逐字的新注释 {PREVIEW_COMMENT_NEW!r}"
    assert "只读演示数据，不联网" not in text, "useLivePreview.ts 的旧注释「只读演示数据，不联网」应已替换"
    assert "const DEBOUNCE_MS = 300;" in text, "useLivePreview.ts 应保住 DEBOUNCE_MS = 300（T024 S14）"


def test_s05_new_tests_shape():
    """S05 / D05–D10：writes-live-flow.test.tsx 必须存在（writes-live-preview.test.tsx 可选）；两份
    合并后只用 setLiveClientForTests 注入、不 vi.mock 被测模块、没有 skip/only/todo；合同点名的
    情景记号（真实路由、九条执行分支的文案、真实模式门、重读失败、needs_yes 三种、预览回归）都在。"""
    need_file(NEW_FLOW_TEST_REL)
    flow_test = read_rel(NEW_FLOW_TEST_REL)
    combined = flow_test
    preview_path = REPO_ROOT / NEW_PREVIEW_TEST_REL
    if preview_path.is_file():
        combined += "\n" + read_rel(NEW_PREVIEW_TEST_REL)
    for m in re.finditer(r"vi\.mock\(\s*['\"]([^'\"]+)['\"]", combined):
        target = m.group(1)
        assert "src/api" not in target and "useWriteFlow" not in target and "live/mode" not in target, \
            f"新测试不许 vi.mock 被测模块（{target}）：只许 setLiveClientForTests 注入假客户端"
    bad = [pat for pat in (r"\.skip\s*\(", r"\.only\s*\(", r"\.todo\s*\(", r"\bxit\s*\(", r"describe\.only")
           if re.search(pat, combined)]
    assert not bad, f"新测试里出现了 {bad}（合同：不许 skip/only/todo）"
    missing = [mark for mark in NEW_TEST_MARKS if mark not in combined]
    assert not missing, \
        f"新测试应覆盖合同 Behavior contract 点名的情形（两份合并查），缺这些记号：{missing}"


def test_s06_fixture_mode_reread_kept():
    """S06 / D11（兼容性）：夹具模式的 reread-fail 用例照旧在 writes-flow.test.tsx 里；mock 的两个
    重读情景值照旧在 mock/writes.ts 里（夹具模式一字不变，门禁不推翻既有断言）。"""
    fixture_test = read_rel(FIXTURE_FLOW_TEST_REL)
    assert "reread-fail" in fixture_test, "writes-flow.test.tsx 的 reread-fail 用例应保留（夹具模式不变）"
    assert "命令已成功，但重新读取失败" in fixture_test, \
        "writes-flow.test.tsx 的「重新读取失败」文案断言应保留"
    mock = read_rel(MOCKWRITES_REL)
    assert "'reread-fail'" in mock and "'reread-fail-exit1'" in mock, \
        "mock/writes.ts 应保住 reread-fail 与 reread-fail-exit1 两个情景值（夹具模式不变）"


# ---------------------------------------------------------------------------
# 探针源码（每份自包含：辅助函数不跨文件共享）
# ---------------------------------------------------------------------------

PROBE_FLOW = r"""
import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Envelope, PresetsData, RolesData } from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { PresetBar } from '../src/pages/readonly1/roles-PresetBar';

// 合同 Behavior contract 逐字写死的原因句。
const REASON = '有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。';

const PRESETS = [
  { name: 'default', description: 'x', roles: ['contract', 'execution', 'planning_review', 'scheduler_agent'], active: true },
  { name: 'economy', description: 'y', roles: ['execution'], active: false },
] as unknown as PresetsData['presets'];

const ROLES = [
  { role: 'execution', explicit: true, binding: { mode: 'headless', profile: 'step-high' }, differs_from_preset: false },
  { role: 'contract', explicit: false, binding: { mode: 'manual' }, differs_from_preset: false },
] as unknown as RolesData['roles'];

type ExecPlan = { status: number; body: Envelope<null> } | { reject: Error };

const gets: Array<{ path: string; timeoutSeconds: number | undefined }> = [];
const posts: Array<{ path: string; body: any; timeoutSeconds: number | undefined }> = [];
const raws: Array<{ path: string; timeoutSeconds: number | undefined }> = [];

let presetsActive = 'default';
let previewJson: Record<string, unknown> | null = null;
let execPlan: ExecPlan | null = null;
let rereadPlan: 'ok' | 'fail' | 'reject' = 'ok';
let afterExec = false;

function envelope(data: unknown, command: string[] = []): Envelope<unknown> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 3 };
}

function failEnvelope(messages: string[]): Envelope<null> {
  return { ok: false, exit_code: null, data: null, output: [], messages, command: [], elapsed_ms: 0 };
}

// 服务的内核预览 JSON（api.ts 的 toPreviewData 会把 unreadable 并进 notes、needs_yes 照抄）。
function basePreview(needsYes: boolean, extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    binding_changes: [],
    changed: true,
    dry_run: true,
    needs_yes: needsYes,
    notes: [],
    resources: [],
    running_attempts: [],
    unreadable: [],
    warnings: [],
    ...extra,
  };
}

const fake = {
  get<T>(path: string, _query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<Envelope<T>> {
    gets.push({ path, timeoutSeconds });
    if (afterExec && rereadPlan === 'fail') {
      return Promise.resolve(failEnvelope(['ERROR: 状态读不出来']) as unknown as Envelope<T>);
    }
    if (afterExec && rereadPlan === 'reject') {
      return Promise.reject(new Error('读不到'));
    }
    if (path === '/api/v1/presets') {
      return Promise.resolve(envelope({ active_preset: presetsActive, presets: PRESETS }) as unknown as Envelope<T>);
    }
    if (path === '/api/v1/roles') {
      return Promise.resolve(envelope({ active_preset: presetsActive, roles: ROLES }) as unknown as Envelope<T>);
    }
    return Promise.resolve(failEnvelope([`探针没有给 ${path} 编排应答`]) as unknown as Envelope<T>);
  },
  post<T>(path: string, body: unknown, timeoutSeconds?: number): Promise<{ status: number; body: Envelope<T> }> {
    posts.push({ path, body, timeoutSeconds });
    if (path === '/api/v1/preview') {
      return Promise.resolve({
        status: 200,
        body: envelope(
          { preview: previewJson, confirmation: 'conf-e2e' },
          ['config', 'preset', 'use', 'economy', '--dry-run', '--json'],
        ) as unknown as Envelope<T>,
      });
    }
    afterExec = true;
    if (execPlan && 'reject' in execPlan) return Promise.reject(execPlan.reject);
    const plan = execPlan as { status: number; body: Envelope<null> } | null;
    if (!plan) return Promise.resolve({ status: 500, body: failEnvelope(['探针没有编排执行应答']) as unknown as Envelope<T> });
    return Promise.resolve({ status: plan.status, body: plan.body as unknown as Envelope<T> });
  },
  getRaw<T>(path: string, _query?: Record<string, string | undefined>, timeoutSeconds?: number): Promise<{ status: number; body: T }> {
    raws.push({ path, timeoutSeconds });
    return Promise.resolve({ status: 404, body: null as unknown as T });
  },
} as unknown as LiveClient;

const text = (el: Element | null) => ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
const dlg = () => document.querySelector('[role="dialog"][aria-modal="true"]') as HTMLElement | null;
const dlgText = () => {
  const d = dlg();
  expect(d, '写确认框应开着').not.toBeNull();
  return text(d as HTMLElement);
};
const bodyText = () => text(document.body);
const toastText = () => text(document.querySelector('.tt-toast'));
const btn = (root: ParentNode, label: string) =>
  Array.from(root.querySelectorAll('button')).find((b) => text(b) === label) as HTMLButtonElement | undefined;

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

async function openConfirm(hash: string) {
  window.location.hash = hash;
  render(<PresetBar presets={PRESETS} active="default" />);
  await settle();
  const radio = Array.from(document.querySelectorAll('[role="radio"]')).find((r) => text(r as Element) === 'economy');
  fireEvent.click(radio as HTMLElement);
  await settle();
  fireEvent.click(btn(document.body, '切换…') as HTMLButtonElement);
  await settle();
  dlgText();
}
async function confirmNow() {
  fireEvent.click(btn(dlg() as HTMLElement, '确认…') as HTMLButtonElement);
  await settle();
  await advance(20);
}

beforeEach(() => {
  vi.useFakeTimers();
  window.location.hash = '';
  gets.length = 0;
  posts.length = 0;
  raws.length = 0;
  presetsActive = 'default';
  previewJson = basePreview(false);
  execPlan = null;
  rereadPlan = 'ok';
  afterExec = false;
  setLiveClientForTests(fake);
});

afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  vi.useRealTimers();
  window.location.hash = '';
});

describe('useWriteFlow 真实模式（注入假服务）：T040 合同', () => {
  it('成功：预览与执行走真实路由，轻提示只在重读之后（D06/D07）', async () => {
    execPlan = { status: 200, body: envelope(null, ['config', 'preset', 'use', 'economy']) };
    await openConfirm('#/roles');
    expect(posts.length).toBe(1);
    expect(posts[0].path).toBe('/api/v1/preview');
    expect(posts[0].body).toEqual({ action: 'preset.use', args: { name: 'economy' } });
    expect(posts[0].timeoutSeconds).toBe(30);
    const before = dlgText();
    expect(before).toContain('将运行的命令');
    expect(before).toContain('config preset use economy');
    expect(before).not.toContain('--dry-run');
    expect(before).not.toContain('--json');
    await confirmNow();
    expect(posts.length).toBe(2);
    expect(posts[1].path).toBe('/api/v1/presets/economy/use');
    expect(posts[1].body).toEqual({ confirmation: 'conf-e2e' });
    expect(posts[1].timeoutSeconds).toBe(90);
    expect(dlg(), '重读完成后关框').toBeNull();
    expect(bodyText()).toContain('已切换到方案 economy');
  });

  it('needs_yes 且读不到状态：原因句逐字在位，排在原样路径行之前（D02）', async () => {
    previewJson = basePreview(true, { unreadable: ['roles/build（权限不够，读不到）'] });
    await openConfirm('#/roles');
    const notes = Array.from((dlg() as HTMLElement).querySelectorAll('.wf-note')).map((el) => text(el));
    expect(notes.length).toBe(2);
    expect(notes[0]).toBe(REASON);
    expect(notes[1]).toContain('roles/build');
    expect(dlgText()).toContain('影响与风险');
  });

  it('needs_yes 且有正在运行的 attempt：只有 running 那行，不加原因句（D02）', async () => {
    previewJson = basePreview(true, { running_attempts: ['ui-readonly-api/attempt-001'] });
    await openConfirm('#/roles');
    const t = dlgText();
    expect(t).toContain('有 attempt 正在运行：ui-readonly-api/attempt-001');
    expect(t).toContain('这次改动需要你确认');
    expect(t).not.toContain(REASON);
    expect((dlg() as HTMLElement).querySelectorAll('.wf-note').length).toBe(0);
  });

  it('needs_yes 为假：不出现原因句（D02）', async () => {
    previewJson = basePreview(false);
    await openConfirm('#/roles');
    const t = dlgText();
    expect(t).not.toContain(REASON);
    expect(t).not.toContain('影响与风险');
  });

  it('真实模式门：hash 带 ?write=reread-fail，执行成功照常重读，不出「重新读取失败」（D01）', async () => {
    execPlan = { status: 200, body: envelope(null, ['config', 'preset', 'use', 'economy']) };
    await openConfirm('#/roles?write=reread-fail');
    await confirmNow();
    expect(bodyText()).toContain('已切换到方案 economy');
    expect(bodyText()).not.toContain('重新读取失败');
  });

  it('真实模式下的重读失败：读 reject →「命令已成功，但重新读取失败，请刷新」（D09）', async () => {
    execPlan = { status: 200, body: envelope(null, ['config', 'preset', 'use', 'economy']) };
    rereadPlan = 'reject';
    await openConfirm('#/roles');
    await confirmNow();
    expect(dlgText()).toContain('命令已成功，但重新读取失败，请刷新');
    expect(toastText()).toBe('');
  });
});
"""

PROBE_PREVIEW = r"""
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Envelope } from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';
import { useLivePreview } from '../src/writes/useLivePreview';

const posts: Array<{ path: string; body: any; timeoutSeconds: number | undefined }> = [];
let postReply: { status: number; body: Envelope<unknown> } | null = null;
let postError: Error | null = null;

function envelope(data: unknown, command: string[]): Envelope<unknown> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 3 };
}

function failEnvelope(messages: string[]): Envelope<unknown> {
  return { ok: false, exit_code: null, data: null, output: [], messages, command: [], elapsed_ms: 0 };
}

const fake = {
  get() {
    return Promise.resolve(envelope(null, []));
  },
  post(path: string, body: unknown, timeoutSeconds?: number) {
    posts.push({ path, body, timeoutSeconds });
    return postError ? Promise.reject(postError) : Promise.resolve(postReply);
  },
  getRaw() {
    return Promise.resolve({ status: 404, body: null });
  },
} as unknown as LiveClient;

beforeEach(() => {
  vi.useFakeTimers();
  window.location.hash = '';
  posts.length = 0;
  postReply = null;
  postError = null;
  setLiveClientForTests(fake);
});

afterEach(() => {
  cleanup();
  setLiveClientForTests(undefined);
  vi.useRealTimers();
  window.location.hash = '';
});

describe('useLivePreview 真实模式（注入假服务）：T040 合同', () => {
  it('300ms 防抖：299ms 不发，300ms 恰好发一次 POST /api/v1/preview（正文 {action, args}、时限 30）；命令去掉两个开关', async () => {
    postReply = {
      status: 200,
      body: envelope(
        { preview: { dry_run: true }, confirmation: 'c1' },
        ['config', 'profile', 'add', 'p1', '--dry-run', '--json'],
      ),
    };
    const { result } = renderHook(() =>
      useLivePreview('profile.add', { profile: 'p1', runtime: 'r', model: 'm' }, true),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(299);
    });
    expect(posts.length).toBe(0);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(posts.length).toBe(1);
    expect(posts[0].path).toBe('/api/v1/preview');
    expect(posts[0].body).toEqual({ action: 'profile.add', args: { profile: 'p1', runtime: 'r', model: 'm' } });
    expect(posts[0].timeoutSeconds).toBe(30);
    expect(result.current.current).toBe(true);
    expect(result.current.result?.command).toEqual(['config', 'profile', 'add', 'p1']);
  });

  it('400 信封：错误行显示 messages 原文，不算成功', async () => {
    postReply = { status: 400, body: failEnvelope(['ERROR: model 不在 pi --list-models 的列表里']) };
    const { result } = renderHook(() =>
      useLivePreview('profile.add', { profile: 'p1', runtime: 'r', model: 'm' }, true),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(301);
    });
    expect(posts.length).toBe(1);
    expect(result.current.result?.ok).toBe(false);
    expect(result.current.result?.error).toBe('ERROR: model 不在 pi --list-models 的列表里');
  });

  it('没有回应：post reject → 错误行是「预览失败：服务没有回应」', async () => {
    postError = new Error('ERROR: 连不上本机服务（请求没有到达服务）');
    const { result } = renderHook(() =>
      useLivePreview('profile.add', { profile: 'p1', runtime: 'r', model: 'm' }, true),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(301);
    });
    expect(result.current.result?.ok).toBe(false);
    expect(result.current.result?.error).toBe('预览失败：服务没有回应');
  });
});
"""

PROBE_SPECS = {
    "flow": (PROBE_FLOW, (FLOW_REL, API_REL, MODE_REL, PRESETBAR_REL)),
    "preview": (PROBE_PREVIEW, (PREVIEW_HOOK_REL, API_REL, MODE_REL)),
}
PROBE_ORDER = ("flow", "preview")


def probe_count(source):
    return len(re.findall(r"^\s*it\(", source, re.M))


# ---------------------------------------------------------------------------
# 会话级夹具：npm 流水线 + 探针
# ---------------------------------------------------------------------------

# G01 的超时是 600s：夹具总预算压在 540s 以内，用完就停下并在断言里写明，不等调度器来杀。
PIPELINE_BUDGET = 540
STEP_CAPS = {
    "npm ci": 240,
    "npm ci --offline": 240,
    "npm test": 240,
    "npm run build": 180,
    "probe": 60,
}


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


# 流水线前后不该变的文件（相对 desktop/web；依赖一个字节都不许动）
WATCHED = ("package.json", "package-lock.json")


@pytest.fixture(scope="session")
def pipeline():
    pipe = Pipeline()
    if not (WEB / "package.json").is_file():
        pipe.reason = f"{WEB_REL}/package.json 不存在，未调用 npm"
        return pipe
    # 候选就绪检查（照 T038 门禁的写法）：本片的新测试文件还没有时（基线），不调 npm——
    # 基线上没有新测试可跑，也避免联网装依赖；失败信号由 S 系列的静态断言给出。
    if not (WEB / "tests" / "writes-live-flow.test.tsx").is_file():
        pipe.reason = "desktop/web/tests/writes-live-flow.test.tsx 还不存在（基线），未调用 npm"
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
        if (WEB / "node_modules" / "vitest").is_dir():
            pipe.steps["npm ci"] = Step("npm ci", [], 0, False, "node_modules 已在，未重装依赖", 0.0)
        else:
            ci = run_step("npm ci", [npm, "ci"])
            if ci is not None and ci.code != 0:
                # 网络不可用时改用本机 npm 缓存再试一次
                run_step("npm ci --offline", [npm, "ci", "--offline"])
        ci_ok = any(pipe.steps.get(k) is not None and pipe.steps[k].code == 0
                    for k in ("npm ci", "npm ci --offline"))
        if ci_ok:
            run_step("npm test", [npm, "test"])
            run_step("npm run build", [npm, "run", "build"])
            uid = uuid.uuid4().hex[:12]
            for key in PROBE_ORDER:
                missing = [rel for rel in PROBE_SPECS[key][1] if not (REPO_ROOT / rel).is_file()]
                if missing:
                    pipe.probe_skipped[key] = f"探针 {key} 要用的文件不存在，未运行：{missing}"
                    continue
                name = f"probe-{uid}-t040-{key}.test.tsx"
                probe_dir.mkdir(exist_ok=True)
                path = probe_dir / name
                written.append(path)
                path.write_text(PROBE_SPECS[key][0], encoding="utf-8", newline="\n")
                pipe.probe_files[key] = name
                run_step("probe", [npm, "test", "--", f"gate-probe/{name}"], label=f"probe:{key}")
        else:
            pipe.stopped_reason = "npm ci（含 --offline 兜底）失败，后续步骤未运行"
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
# P 系列：流水线断言
# ---------------------------------------------------------------------------

def test_p1_pipeline_steps_pass(pipeline):
    """P1 / V01、V02、D11、D13：npm 依赖（已在就跳过）、npm test（全绿，含两份新测试）、
    npm run build（tsc --noEmit + vite build）都退出 0；依赖文件一个字节没动。"""
    assert any(pipeline.steps.get(k) is not None and pipeline.steps[k].code == 0
               for k in ("npm ci", "npm ci --offline")), \
        f"npm ci 未成功：{pipeline.stopped_reason or pipeline.reason}"
    for name in ("npm test", "npm run build"):
        step = assert_step_ok(pipeline, name)
        if name == "npm test":
            m = re.search(r"Tests\s+(?:.*\|\s*)?(\d+) passed", step.out)
            assert m, f"npm test 输出里没有通过计数：\n{step.tail}"
            assert not re.search(r"Tests\s+.*\b(failed|skipped|todo)\b", step.out), \
                f"npm test 有失败或跳过：\n{step.tail}"
        if name == "npm run build":
            assert "built in" in step.out, f"vite build 应打印 built in：\n{step.tail}"
    assert pipeline.digests_before == pipeline.digests_after, \
        "npm 流水线不许改动 desktop/web/package.json 与 package-lock.json"
    assert not pipeline.gate_probe_left, "gate-probe/ 目录在探针后应清掉"


def test_p2_probe_flow(pipeline):
    """P2 / D01、D02、D06、D07、D09：useWriteFlow 真实模式探针全绿（成功路径的真实路由与
    「成功只在重读之后」、needs_yes 的三种情形、真实模式门、真实模式下的重读失败）。"""
    assert_probe_ok(pipeline, "flow")


def test_p3_probe_preview(pipeline):
    """P3 / D10：useLivePreview 真实模式探针全绿（300ms 防抖恰好一次、命令去开关、
    400 信封 messages 原文、没有回应的固定文案）。"""
    assert_probe_ok(pipeline, "preview")
