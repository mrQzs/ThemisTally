"""T037 战前门禁：桌面端前端第 4 片——写操作接真实路由（预览、确认、执行、操作终态）（D6）的
黑盒基准测试（合同 t037-desktop-web-writes.v1，基线 9839e86e）。

被测对象是 ``desktop/web/``：改 ``src/live/transport.ts``（LiveClient 加 ``post`` 与 ``getRaw``，
三个公开方法走同一个内部请求函数）、``src/live/mode.ts``（LiveClient 类型加两个成员，导出集合仍是
四个）、``src/api.ts``（参数整理、preview/getOperation 映射、十个写函数接真实路由、删 501 的
unwired 分支、WriteAction 加 hub.set/hub.unset）、``src/mock/writes.ts``（hub 两条的桩）与执行端
测试 ``tests/live-transport.test.ts``、``tests/live-api.test.ts``。共享文件的集合断言按包含不卡
恰好（基线一个不丢、本片新增的在），后续片合法地加导出或情景值不会误红。

基线（9839e86e）上 transport 仍只有 ``get``、mode.ts 的 LiveClient 只有 get 成员、api.ts 的写函数
与 getOperation 一律回 501（unwired 分支还在）、mock/writes.ts 没有 hub 两条、两份执行端测试没有
新用例，所以本文件的失败落在「记号不在」「导出不在」「探针断言红」上，不是导入、收集或语法错误：
模块级只导入标准库，所有仓库文件的读取都发生在用例函数里；流水线（npm ci、npm test、npm run
build、探针）放在 ``pipeline`` 会话级夹具里（全量 pytest 默认跳过，点名运行本文件才跑）。

结构（编号大致对应合同 DoD 的 D01–D14）：

- 静态断言（``test_s*``，不用流水线，全量 pytest 也跑）：transport 的 post/getRaw 形状、单一
  超时路径与两处中止判定（D01–D03）；mode.ts 的 LiveClient 类型与四个导出（D04）；api.ts 的
  写函数接线路由、unwired 删除、WriteAction 成员与导出集合恰好加两个（D05–D08、D10）；mock
  的 hub 两条与 22 个情景值不增不减（D09）；两份执行端测试只追加/替换（D11）；两条写入口过渡
  用例与 mock JSON 不动（兼容性）。
- 流水线断言（``test_p*``，``pipeline`` 会话级夹具）：npm ci（node_modules 已在时跳过重装）、
  npm test（全绿）、npm run build（tsc --noEmit + vite build）；探针逐份写成
  ``gate-probe/probe-<唯一标识>-t037-<键>.test.ts``，各用 ``npm test -- gate-probe/<文件名>`` 跑，
  ``finally`` 里删除。

探针（Vitest + jsdom，全部自包含，辅助函数不跨文件共享；注入用的假 fetch/假 LiveClient，不 mock
被测模块本身）：

- post：``createLiveClient`` 的 post/getRaw——请求形状（POST、same-origin、两个头、JSON 正文、
  signal、不拼 Origin）、200 合法信封、401（reauth 恰好一次、固定文案）、503（服务自己的信封
  原样；非信封按 Retry-After 合成）、504 原样、非信封正文的合成信封（≥400 与 200 两种文案）、
  断线 reject（get 同样断线仍回失败信封、绝不 reject）、假计时器下的超时 reject（文案带秒数）、
  getRaw 的 200 八键对象原样与 404 信封（D01、D02）。
- api：注入带 post/getRaw 的假客户端——preview 的路径/正文/参数整理（number 转 JSON 数字、
  空串与空数组不传、转不成原样传）、PreviewData 映射（from/to 显示格式、resources 不去重、
  notes 并入 unreadable、command 取信封顶层、confirmation）、preview 失败透传（400/500/503/
  200-ok:false/缺 confirmation）、getOperation 的 200 八键视图（envelope 非法取 null、正文不是
  对象或缺 state 取 null）与 404 透传、十个写函数的路径/正文/90 秒时限、没有回应时 reject、
  真实模式不再回 501（D05–D08、D10）。
- mock：hub.set/hub.unset 的桩——baseArgv（含 --fallback）、previewData（binding_changes 恒空、
  resources 为 ['hub']）、确认号与参数核对（ok/丢项 409/号不存在 409、post 不符 409）、
  ?write= 情景照旧作用于 hub 写（D09）。

getRaw 对「正文不是合法信封」的归成规则合同没写死（写死会与 getOperation 的八键原样冲突），
探针只测合同第 6 步点名的两件事：200 八键对象原样、404 信封原样；见交付信「下游须知」。
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

TRANSPORT_REL = f"{SRC_REL}/live/transport.ts"
MODE_REL = f"{SRC_REL}/live/mode.ts"
API_REL = f"{SRC_REL}/api.ts"
MOCKWRITES_REL = f"{SRC_REL}/mock/writes.ts"
LIVE_TRANSPORT_TEST_REL = f"{TESTS_REL}/live-transport.test.ts"
LIVE_API_TEST_REL = f"{TESTS_REL}/live-api.test.ts"
PAGE_APP_TEST_REL = f"{TESTS_REL}/page-app.test.tsx"
READONLY2_APP_TEST_REL = f"{TESTS_REL}/readonly2-app.test.tsx"

# 传输层的六条定稿文案（与 T027 S04 同一批锚点，本片不许改字）
MSG_TIMEOUT_PREFIX = "ERROR: 请求超时（"
MSG_DISCONNECT = "ERROR: 连不上本机服务（请求没有到达服务）"
MSG_401 = "ERROR: 会话已失效"
MSG_503_PREFIX = "ERROR: 服务繁忙（排队过长），请 "
MSG_HTTP_PREFIX = "ERROR: 服务返回 HTTP "
MSG_BAD_JSON_PREFIX = "ERROR: 服务的响应不是合法的 JSON（HTTP "

# 中止判定的定稿写法（站主硬要求：恰好两处，都在内部请求函数里）
ABORT_CHECK = "timedOut || (error as Error)?.name === 'AbortError'"

# api.ts 的 15 个读函数 + getMetaNow（本片一字不改，T027 S06 也钉着）
API_READS = (
    "getMeta", "getStatus", "getAttempt", "readFile", "getRoles", "getProfiles", "getPresets",
    "diffPresets", "getRuntimes", "getPlugins", "getHistory", "getUsage", "listSecrets",
    "getHistoryEntry", "getPlugin", "getMetaNow",
)
# preview + getOperation + A/B 片八个写函数 + 本片两个 hub 写函数（仍都是同步的 export function）
API_WRITES = (
    "preview", "getOperation", "usePreset", "setPluginEnabled", "removePreset", "removeProfile",
    "removeRuntime", "rollback", "addProfile", "editProfile", "setHubRole", "unsetHubRole",
)
# api.ts 导出的基线集合（一个都不许丢，本片新增 setHubRole/unsetHubRole 两个——按包含不卡恰好，
# 「不许多导出」属范围门禁，由 diff 审阅兜底）
API_EXPORT_BASELINE = frozenset({
    "getMeta", "getStatus", "getAttempt", "readFile", "getRoles", "getProfiles", "getPresets",
    "diffPresets", "getRuntimes", "getPlugins", "getHistory", "getUsage", "listSecrets",
    "getHistoryEntry", "getPlugin", "getMetaNow", "preview", "getOperation", "usePreset",
    "setPluginEnabled", "removePreset", "removeProfile", "removeRuntime", "rollback", "addProfile",
    "editProfile", "Envelope", "HttpReply", "BindingChange", "PreviewData", "OperationView",
    "WriteAction", "WriteArgs", "MetaData", "StatusRow", "StatusData", "AttemptData", "FileData",
    "RolesData", "ProfilesData", "PresetsData", "PresetDiffData", "RuntimesData", "PluginsData",
    "HistoryData", "UsageData", "SecretsData",
})
# mock/writes.ts 导出的基线集合（一个都不许丢，本片新增两个 hub 桩——按包含不卡恰好）
MOCK_EXPORT_BASELINE = frozenset({
    "WriteScenario", "writeScenario", "mockPreview", "mockGetOperation", "mockUsePreset",
    "mockSetPluginEnabled", "mockRemovePreset", "mockRemoveProfile", "mockRemoveRuntime",
    "mockRollback", "mockAddProfile", "mockEditProfile",
})
# 22 个 ?write= 情景值的基线值（一个都不许丢，总数不少于 22——按包含不卡恰好，后续片可加）
WRITE_SCENARIOS = (
    "ok", "warn", "exit1", "exit2", "exit3", "stale", "expired", "busy", "closing", "spawn",
    "toolarge", "timeout", "drop-done", "drop-lost", "drop-hang", "preview-fail", "preview-busy",
    "reread-fail", "reread-fail-exit1", "in-use", "preview-warn", "preview-invalid",
)
# 写路由在 api.ts 里该出现的记号（按路径前缀查、不带外层引号，与 T027 的 API_ROUTES 同一口径：
# 插值路径会写成模板字面量，带引号的整串查不到；仍查去注释的代码——基线注释里也提到 /api/v1/preview）
API_ROUTE_MARKS = (
    "/api/v1/preview", "/api/v1/operations/", "/api/v1/config/rollback/", "/api/v1/hub/roles/",
    "/use", "/remove", "/enable", "/disable", "/add", "/edit", "/unset",
)

NETWORK_RE = re.compile(r"(?<![A-Za-z0-9_$])(?:fetch|XMLHttpRequest|EventSource|WebSocket)(?![A-Za-z0-9_$])")

# ---------------------------------------------------------------------------
# 通用小工具（与 T036 门禁同一口径）
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


def fail_if(problems, title):
    assert not problems, title + "：\n" + "\n".join(f"- {p}" for p in problems[:40])


# TS 注释剥离（与 T010/T034/T036 的同一口径）
_TS_COMMENT = re.compile(r"(?<![:'\"`])//[^\n]*|/\*.*?\*/", re.S)


def strip_ts_comments(text):
    return _TS_COMMENT.sub("", text)


def export_names(code):
    """TS 源码（先去注释）里的顶层导出名集合（function/const/let/var/type/interface 与 export {}）。"""
    names = set()
    for pattern in (r"export\s+(?:async\s+)?function\s+(\w+)",
                    r"export\s+(?:const|let|var)\s+(\w+)",
                    r"export\s+(?:type|interface)\s+(\w+)"):
        names.update(m.group(1) for m in re.finditer(pattern, code))
    for em in re.finditer(r"export\s*\{([^}]*)\}", code):
        for item in em.group(1).split(","):
            name = item.strip()
            if not name:
                continue
            if name.startswith("type "):
                name = name[5:].strip()
            name = name.split(" as ")[-1].strip()
            if name:
                names.add(name)
    return names


# ---------------------------------------------------------------------------
# S 系列：静态断言（不用流水线）
# ---------------------------------------------------------------------------

def test_s01_transport_post_getraw_shape():
    """S01 / D01–D03、第一节：transport.ts——createLiveClient 回的对象加 ``post`` 与 ``getRaw``；
    post 的请求形状（POST、same-origin、两个头、JSON.stringify 正文）；三个公开方法共用一个内部
    请求函数（AbortController 与 setTimeout 各只有一处）；中止判定仍是恰好两处；六条定稿文案在；
    get 的签名不变。"""
    need_file(TRANSPORT_REL)
    text = read_rel(TRANSPORT_REL)
    assert re.search(r"\bpost<T>\(", text), "transport.ts 应有 post<T>( 方法"
    assert re.search(r"\bgetRaw<T>\(", text), "transport.ts 应有 getRaw<T>( 方法"
    assert re.search(r"get<T>\(\s*path:\s*string,\s*query\?", text), "get 的签名应保持原样（query 可选）"
    assert re.search(r"method:\s*['\"]POST['\"]", text), "post 的请求应带 method: 'POST'"
    code = strip_ts_comments(text)
    assert "application/json" in code, "post 的请求头应有 Content-Type: application/json"
    assert "X-Themis-UI" in code, "post 的请求头应有 X-Themis-UI: 1"
    assert "JSON.stringify(" in code, "post 的正文应是 JSON.stringify(body)"
    assert code.count("new AbortController(") == 1, \
        f"内部请求函数只应有一处 new AbortController(（三个公开方法共用），现 {code.count('new AbortController(')} 处"
    assert code.count("setTimeout(") == 1, \
        f"内部请求函数只应有一条超时路径（一处 setTimeout），现 {code.count('setTimeout(')} 处"
    assert code.count("credentials: 'same-origin'") + code.count('credentials: "same-origin"') == 1, \
        "credentials: 'same-origin' 只应在内部请求函数里出现一次（不许为 post/getRaw 复制请求代码）"
    assert text.count(ABORT_CHECK) == 2, \
        f"中止判定 {ABORT_CHECK!r} 应恰好两处（站主硬要求），现 {text.count(ABORT_CHECK)} 处"
    assert "clearTimeout" in text, "时限机制应保留（clearTimeout）"
    messages = {
        "超时": MSG_TIMEOUT_PREFIX,
        "断线": MSG_DISCONNECT,
        "401": MSG_401,
        "503": MSG_503_PREFIX,
        "其他状态码": MSG_HTTP_PREFIX,
        "坏 JSON": MSG_BAD_JSON_PREFIX,
    }
    for label, msg in messages.items():
        assert msg in text, f"transport.ts 缺少{label}的定稿文案 {msg!r}"
    assert "exit_code: null" in text, "合成信封的 exit_code 应是 null"


def test_s02_mode_live_client_type():
    """S02 / D04、第一节：mode.ts——LiveClient 类型加 post 与 getRaw 两个成员；导出集合仍恰好四个；
    三个函数与 declare const 一字不改；对 ../api 仍只许 import type。"""
    need_file(MODE_REL)
    text = read_rel(MODE_REL)
    assert re.search(r"\bpost<T>\(", text), "LiveClient 类型应有 post<T>( 成员"
    assert re.search(r"\bgetRaw<T>\(", text), "LiveClient 类型应有 getRaw<T>( 成员"
    assert re.search(r"declare const __THEMIS_LIVE_MODE__", text), "declare const __THEMIS_LIVE_MODE__ 应保留"
    for name in ("liveModeIsReal", "liveClient", "setLiveClientForTests"):
        assert re.search(rf"export function {name}\(", text), f"mode.ts 应保留导出函数 {name}"
    code = strip_ts_comments(text)
    assert not re.search(r"export\s*\*", code), "mode.ts 不许 export *（导出集合固定为四个）"
    names = export_names(code)
    assert names == {"liveModeIsReal", "liveClient", "setLiveClientForTests", "LiveClient"}, \
        f"mode.ts 的导出集合应仍恰好四个，实际 {sorted(names)}"
    for m in re.finditer(r"""import\s+([^;\n]*)\s+from\s+['"]\.\./api['"];?""", text):
        assert m.group(1).strip().startswith("type"), \
            f"mode.ts 对 ../api 只许 import type，实际 {m.group(0)}"


def test_s03_api_writes_wired():
    """S03 / D05–D08、D10、第一节：api.ts——12 个写侧函数（preview、getOperation、十个写函数）仍是
    同步的 ``export function``；unwired 分支与「写操作尚未接通」删掉；WriteAction 加 hub.set/
    hub.unset；真实写路由的记号在；导出集合基线一个不丢、本片两个 hub 写函数在（按包含不卡恰好）；
    网络词一处不许有。"""
    need_file(API_REL)
    text = read_rel(API_REL)
    for name in API_READS:
        assert re.search(rf"export function {name}\(", text), f"api.ts 的读函数 {name} 应保持 export function 原样"
    for name in API_WRITES:
        assert re.search(rf"export function {name}\(", text), \
            f"api.ts 的写侧函数 {name} 应是 export function（不是 export async function）"
    code = strip_ts_comments(text)
    assert "unwired" not in code, \
        "api.ts 应删掉 501 的 unwired 分支（真实模式不再回 501；去注释后查，改注释说明不算）"
    assert "写操作尚未接通" not in code, \
        "api.ts 应删掉「ERROR: 写操作尚未接通」那句（去注释后查）"
    assert "'hub.set'" in code and "'hub.unset'" in code, "WriteAction 应加 'hub.set' 与 'hub.unset' 成员"
    for mark in API_ROUTE_MARKS:
        assert mark in code, f"api.ts（去注释）应出现写路由记号 {mark}"
    assert "currentMock" in text, "夹具分支的 currentMock 机制应保留"
    for iface in ("Envelope", "HttpReply", "BindingChange", "PreviewData", "OperationView"):
        assert re.search(rf"export interface {iface}\b", text), f"api.ts 应保留 export interface {iface}"
    names = export_names(code)
    api_missing = (API_EXPORT_BASELINE | {"setHubRole", "unsetHubRole"}) - names
    assert not api_missing, \
        f"api.ts 的导出应保住基线全部并新增 setHubRole、unsetHubRole（按包含不卡恰好），缺 {sorted(api_missing)}"
    for m in NETWORK_RE.finditer(text):
        pytest.fail(f"{API_REL} 出现网络接口名 {m.group(0)}（连注释都不许，T027 S10）")


def test_s04_mock_hub_stubs():
    """S04 / D09、第一节：mock/writes.ts——加 mockSetHubRole/mockUnsetHubRole（走 confirmWrite）；
    hub.set/hub.unset 进 NEW_ACTIONS；baseArgv 认 --fallback；previewData 给 hub 一条分支
    （binding_changes 恒空、resources 为 ['hub']）；22 个情景值保住基线且不少于 22（按包含不卡恰好）；
    导出集合基线不丢、两个 hub 桩在。"""
    need_file(MOCKWRITES_REL)
    text = read_rel(MOCKWRITES_REL)
    assert re.search(r"export function mockSetHubRole\(", text), "mock/writes.ts 应导出 mockSetHubRole"
    assert re.search(r"export function mockUnsetHubRole\(", text), "mock/writes.ts 应导出 mockUnsetHubRole"
    code = strip_ts_comments(text)
    assert "confirmWrite('hub.set'" in code, "mockSetHubRole 应走 confirmWrite('hub.set', …)"
    assert "confirmWrite('hub.unset'" in code, "mockUnsetHubRole 应走 confirmWrite('hub.unset', …)"
    new_actions = re.search(r"NEW_ACTIONS\s*=\s*new Set<string>\(\[([^\]]*)\]", code)
    assert new_actions, "mock/writes.ts 应保留 NEW_ACTIONS 集合"
    for action in ("'hub.set'", "'hub.unset'"):
        assert action in new_actions.group(1), f"NEW_ACTIONS 应含 {action}"
    assert "--fallback=" in code, "hub.set 的 baseArgv 应认 --fallback=<值>"
    assert re.search(r"resources:\s*\[\s*'hub'\s*\]", code), "previewData 的 hub 分支应给 resources: ['hub']"
    union = re.search(r"export type WriteScenario =([\s\S]*?);", text)
    assert union, "mock/writes.ts 应保留 WriteScenario 类型"
    members = re.findall(r"'([a-z0-9-]+)'", union.group(1))
    scenario_missing = [s for s in WRITE_SCENARIOS if s not in members]
    assert not scenario_missing and len(members) >= len(WRITE_SCENARIOS), \
        f"WriteScenario 应保住基线 22 个情景值且总数不少于 22（按包含不卡恰好，后续片可加），" \
        f"缺 {scenario_missing}，现 {len(members)} 个：{members}"
    names = export_names(code)
    mock_missing = (MOCK_EXPORT_BASELINE | {"mockSetHubRole", "mockUnsetHubRole"}) - names
    assert not mock_missing, \
        f"mock/writes.ts 的导出应保住基线全部并新增两个 hub 桩（按包含不卡恰好），缺 {sorted(mock_missing)}"


def test_s05_executor_tests_appended():
    """S05 / D11、第 6/7 步：live-transport.test.ts 只追加（19 条之上至少 9 条 post/getRaw 用例）；
    live-api.test.ts 的 501 describe 换成真实分支用例（旧记号「写操作尚未接通」不在）；两份都覆盖
    新函数且不用 skip/only/todo。"""
    need_file(LIVE_TRANSPORT_TEST_REL)
    transport_test = read_rel(LIVE_TRANSPORT_TEST_REL)
    count = len(re.findall(r"^\s*it\(", transport_test, re.M))
    assert count >= 28, f"live-transport.test.ts 应追加到至少 28 条 it（基线 19 + 合同第 6 步 9 条），现 {count} 条"
    assert re.search(r"\.post\(", transport_test), "live-transport.test.ts 应有用 post 的用例"
    assert re.search(r"\.getRaw\(", transport_test), "live-transport.test.ts 应有用 getRaw 的用例"
    assert re.search(r"themis-ui", transport_test, re.I), "请求形状用例应断言 X-Themis-UI 头"
    need_file(LIVE_API_TEST_REL)
    api_test = read_rel(LIVE_API_TEST_REL)
    assert "写操作尚未接通" not in api_test, "live-api.test.ts 的 501 describe 应换成真实分支用例"
    for token in ("setHubRole", "unsetHubRole", "getOperation", "/api/v1/preview", "operations"):
        assert token in api_test, f"live-api.test.ts 应覆盖 {token}（合同第 7 步的真实分支用例）"
    assert re.search(r"\b90\b", api_test), "live-api.test.ts 应断言写函数的服务端时限 90 秒"
    api_count = len(re.findall(r"^\s*it\(", api_test, re.M))
    assert api_count >= 14, f"live-api.test.ts 替换后的用例数应不少于 14 条（现 {api_count} 条）"
    for rel, text in ((LIVE_TRANSPORT_TEST_REL, transport_test), (LIVE_API_TEST_REL, api_test)):
        bad = [pat for pat in (r"\.skip\s*\(", r"\.only\s*\(", r"\.todo\s*\(", r"\bxit\s*\(", r"describe\.only")
               if re.search(pat, text)]
        assert not bad, f"{rel} 里出现了 {bad}（合同 D11：不删用例、不削弱断言）"


def test_s06_transitional_and_fixtures_untouched():
    """S06 / 兼容性、Non-goals：两条写入口过渡用例（page-app.test.tsx、readonly2-app.test.tsx）不推翻；
    src/mock 仍恰 14 份 JSON（桩的夹具不动）；writes 流程文件仍在（本片一个字不动，由范围门禁证明）。"""
    page_app = read_rel(PAGE_APP_TEST_REL)
    assert "describe('写入口个数（过渡）'" in page_app, "page-app.test.tsx 的写入口过渡用例应保留（不推翻、不改写）"
    readonly2 = read_rel(READONLY2_APP_TEST_REL)
    assert "describe('夹具下的写入口（过渡）'" in readonly2, \
        "readonly2-app.test.tsx 的夹具写入口过渡用例应保留（不推翻、不改写）"
    jsons = sorted(p.name for p in (REPO_ROOT / SRC_REL / "mock").glob("*.json"))
    assert len(jsons) == 14, f"src/mock 应仍恰 14 份 JSON（现 {len(jsons)}）"
    need_file(f"{SRC_REL}/writes/useWriteFlow.ts")
    need_file(f"{SRC_REL}/writes/writeOutcome.ts")


# ---------------------------------------------------------------------------
# 探针源码（每份自包含：辅助函数不跨文件共享）
# ---------------------------------------------------------------------------

PROBE_POST = r"""
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getConnectionState, setConnectionState } from '../src/live/connection';
import { createLiveClient } from '../src/live/transport';

type Seen = { input: string; init: RequestInit };

function envelope(data: unknown) {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command: ['x'], elapsed_ms: 4 };
}

function failureEnvelope(message: string) {
  return { ok: false, exit_code: null, data: null, output: [], messages: [message], command: [], elapsed_ms: 0 };
}

function textResponse(status: number, body: string, headers: Record<string, string> = {}) {
  const lower: Record<string, string> = {};
  for (const key of Object.keys(headers)) lower[key.toLowerCase()] = headers[key];
  return {
    status,
    ok: status >= 200 && status < 300,
    text: async () => body,
    headers: {
      get: (name: string) =>
        Object.prototype.hasOwnProperty.call(lower, name.toLowerCase()) ? lower[name.toLowerCase()] : null,
    },
  };
}

function jsonResponse(status: number, body: unknown, headers?: Record<string, string>) {
  return textResponse(status, JSON.stringify(body), headers);
}

function recorder(responder: (seen: Seen) => unknown) {
  const seen: Seen[] = [];
  const fn = (input: unknown, init?: RequestInit) => {
    seen.push({ input: String(input), init: init ?? {} });
    return Promise.resolve(responder(seen[seen.length - 1]));
  };
  return { seen, fn };
}

function abortError(): Error {
  return Object.assign(new Error('The operation was aborted'), { name: 'AbortError' });
}

// 收到 signal 后一直挂起，直到我方中止——超时那条用例用它。
function hanging() {
  const seen: Seen[] = [];
  const fn = (input: unknown, init?: RequestInit) => {
    seen.push({ input: String(input), init: init ?? {} });
    return new Promise((_resolve, reject) => {
      const signal = init?.signal as AbortSignal | undefined;
      if (!signal) return;
      if (signal.aborted) reject(abortError());
      else signal.addEventListener('abort', () => reject(abortError()));
    });
  };
  return { seen, fn };
}

// 头可以是 Headers、数组或普通对象：都归成 Headers 再查（大小写不敏感）。
function headersOf(init: RequestInit): Headers {
  const h = init.headers;
  if (h instanceof Headers) return h;
  return new Headers((h ?? undefined) as Record<string, string> | undefined);
}

beforeEach(() => {
  setConnectionState('connected');
});

afterEach(() => {
  vi.useRealTimers();
  setConnectionState('connected');
});

describe('live/transport：post 与 getRaw（T037 合同第一节）', () => {
  it('post 的请求形状：POST、same-origin、两个头、JSON 正文、带 signal；不拼 Origin、不带凭据头', async () => {
    const rec = recorder(() => jsonResponse(200, envelope(null)));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    const body = { action: 'preset.use', args: { name: 'default' } };
    const reply = await client.post('/api/v1/preview', body, 30);
    expect(reply.status).toBe(200);
    expect(rec.seen.length).toBe(1);
    expect(rec.seen[0].input).toBe('/api/v1/preview');
    expect(rec.seen[0].init.method).toBe('POST');
    expect(rec.seen[0].init.credentials).toBe('same-origin');
    expect(rec.seen[0].init.body).toBe(JSON.stringify(body));
    const h = headersOf(rec.seen[0].init);
    expect(h.get('content-type')).toBe('application/json');
    expect(h.get('x-themis-ui')).toBe('1');
    expect(h.get('origin')).toBeNull();
    expect(h.get('authorization')).toBeNull();
    const signal = rec.seen[0].init.signal as AbortSignal | undefined;
    expect(signal && typeof signal.aborted === 'boolean').toBe(true);
    expect(getConnectionState()).toBe('connected');
  });

  it('post：200 正文是合法信封 → { status, body } 原样；请求结束后不留守计时器', async () => {
    vi.useFakeTimers();
    const want = envelope({ preview: { dry_run: true }, confirmation: 'c1' });
    const rec = recorder(() => jsonResponse(200, want));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    const reply = await client.post('/api/v1/preview', {}, 30);
    expect(reply).toEqual({ status: 200, body: want });
    expect(vi.getTimerCount()).toBe(0);
  });

  it('post：401 → reauth 恰好一次、状态码 401 与固定文案；下一波 401 再起一次新的', async () => {
    let reauthCalls = 0;
    const rec = recorder(() => jsonResponse(401, { some: 'body' }));
    const client = createLiveClient({
      fetch: rec.fn as unknown as typeof fetch,
      host: {
        reauth: () => {
          reauthCalls += 1;
          return Promise.resolve({ ok: true });
        },
      },
    });
    const reply = await client.post('/api/v1/preview', {});
    expect(reply.status).toBe(401);
    expect(reply.body).toEqual(failureEnvelope('ERROR: 会话已失效'));
    expect(reauthCalls).toBe(1);
    const second = await client.post('/api/v1/preview', {});
    expect(second.status).toBe(401);
    expect(second.body).toEqual(failureEnvelope('ERROR: 会话已失效'));
    expect(reauthCalls).toBe(2);
    expect(getConnectionState()).toBe('connected');
  });

  it('post：503 正文是服务自己的信封就原样用，状态码 503 原样返回', async () => {
    const serverEnvelope = {
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR 服务繁忙，请稍后重试'],
      command: [],
      elapsed_ms: 0,
    };
    const rec = recorder(() => jsonResponse(503, serverEnvelope));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    const reply = await client.post('/x', {});
    expect(reply).toEqual({ status: 503, body: serverEnvelope });
  });

  it('post：504 正文是合法信封 → 状态码原样、信封原样（执行超时的终态透传）', async () => {
    const serverEnvelope = {
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 命令超时（90 秒），子进程已结束；请改用 CLI 查看'],
      command: ['config', 'rollback', '41'],
      elapsed_ms: 90001,
    };
    const rec = recorder(() => jsonResponse(504, serverEnvelope));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    const reply = await client.post('/x', {});
    expect(reply).toEqual({ status: 504, body: serverEnvelope });
  });

  it('post：正文不是合法信封 → 合成失败信封（≥400 用 HTTP 码、200 用坏 JSON 文案），状态码不变', async () => {
    const rec500 = recorder(() => textResponse(500, 'internal error'));
    const c500 = createLiveClient({ fetch: rec500.fn as unknown as typeof fetch });
    const r500 = await c500.post('/x', {});
    expect(r500.status).toBe(500);
    expect(r500.body).toEqual(failureEnvelope('ERROR: 服务返回 HTTP 500'));
    const rec200 = recorder(() => jsonResponse(200, { hello: 1 }));
    const c200 = createLiveClient({ fetch: rec200.fn as unknown as typeof fetch });
    const r200 = await c200.post('/x', {});
    expect(r200.status).toBe(200);
    expect(r200.body).toEqual(failureEnvelope('ERROR: 服务的响应不是合法的 JSON（HTTP 200）'));
    const rec503 = recorder(() => textResponse(503, 'busy', { 'Retry-After': '7' }));
    const c503 = createLiveClient({ fetch: rec503.fn as unknown as typeof fetch });
    const r503 = await c503.post('/x', {});
    expect(r503.status).toBe(503);
    expect(r503.body).toEqual(failureEnvelope('ERROR: 服务繁忙（排队过长），请 7 秒后重试'));
  });

  it('post：断线 → reject（固定文案），状态 disconnected；同一客户端的 get 绝不 reject、仍回失败信封', async () => {
    const client = createLiveClient({
      fetch: (() => Promise.reject(new TypeError('Failed to fetch'))) as unknown as typeof fetch,
    });
    await expect(client.post('/api/v1/preview', {})).rejects.toThrow(
      'ERROR: 连不上本机服务（请求没有到达服务）',
    );
    expect(getConnectionState()).toBe('disconnected');
    const env = await client.get('/api/v1/roles');
    expect(env).toEqual(failureEnvelope('ERROR: 连不上本机服务（请求没有到达服务）'));
  });

  it('post：假计时器下的超时 → reject，文案带秒数（服务端时限 + 5），计时器清掉、状态 disconnected', async () => {
    vi.useFakeTimers();
    const hang = hanging();
    const client = createLiveClient({ fetch: hang.fn as unknown as typeof fetch });
    const pending = client.post('/api/v1/preview', {}, 30);
    let settled = false;
    pending.then(() => (settled = true), () => (settled = true));
    await vi.advanceTimersByTimeAsync(34999);
    expect(settled).toBe(false);
    await vi.advanceTimersByTimeAsync(1);
    await expect(pending).rejects.toThrow('ERROR: 请求超时（35 秒），没有收到服务的回应');
    expect((hang.seen[0].init.signal as AbortSignal).aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
    expect(getConnectionState()).toBe('disconnected');
  });

  it('getRaw：200 的八键操作对象原样交回（不归成信封）；GET、查询用 URLSearchParams 拼', async () => {
    const opView = {
      id: 'op1',
      action: 'config rollback',
      state: 'succeeded',
      reason: null,
      created_ms: 1,
      started_ms: 2,
      finished_ms: 3,
      envelope: { ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 5 },
    };
    const rec = recorder(() => jsonResponse(200, opView));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    const reply = await client.getRaw('/api/v1/operations/op1');
    expect(reply).toEqual({ status: 200, body: opView });
    expect(rec.seen[0].init.method).toBe('GET');
    expect(rec.seen[0].init.credentials).toBe('same-origin');
    await client.getRaw('/api/v1/operations/op 1', { q: 'a b' });
    expect(rec.seen[1].input).toBe('/api/v1/operations/op 1?q=a+b');
  });

  it('getRaw：404 的错误信封原样交回（状态码 404）', async () => {
    const notFound = {
      ok: false,
      exit_code: null,
      data: null,
      output: [],
      messages: ['ERROR: 没有这个操作'],
      command: [],
      elapsed_ms: 0,
    };
    const rec = recorder(() => jsonResponse(404, notFound));
    const client = createLiveClient({ fetch: rec.fn as unknown as typeof fetch });
    const reply = await client.getRaw('/api/v1/operations/nope');
    expect(reply).toEqual({ status: 404, body: notFound });
    expect(getConnectionState()).toBe('connected');
  });
});
"""

PROBE_API = r"""
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import * as api from '../src/api';
import { setLiveClientForTests, type LiveClient } from '../src/live/mode';

type PostCall = { path: string; body: any; timeoutSeconds: number | undefined };
type RawCall = { path: string; query: Record<string, string | undefined> | undefined; timeoutSeconds: number | undefined };

const posts: PostCall[] = [];
const raws: RawCall[] = [];
let nextPost: { status: number; body: any } | null = null;
let nextRaw: { status: number; body: any } | null = null;
let postError: Error | null = null;

const fakeClient = {
  get() {
    return Promise.resolve({ ok: true, exit_code: 0, data: null, output: [], messages: [], command: [], elapsed_ms: 0 });
  },
  post(path: string, body: unknown, timeoutSeconds?: number) {
    posts.push({ path, body, timeoutSeconds });
    return postError ? Promise.reject(postError) : Promise.resolve(nextPost);
  },
  getRaw(path: string, query?: Record<string, string | undefined>, timeoutSeconds?: number) {
    raws.push({ path, query, timeoutSeconds });
    return Promise.resolve(nextRaw);
  },
} as unknown as LiveClient;

function okEnv(data: any, command: string[] = []) {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 7 };
}

function failEnv(messages: string[], exitCode: number | null = null) {
  return { ok: false, exit_code: exitCode, data: null, output: [], messages, command: [], elapsed_ms: 3 };
}

// 服务的内核预览 JSON（键集合照 tests/test_kit_roles.py 钉死的那套；binding_changes 是
// {role, before, after}，resources 是 {resource, changed, changed_keys}，warnings 已去前缀，
// 另有 unreadable；不含 command——command 在信封顶层）。
const servicePreview = {
  action: 'preset.use',
  binding_changes: [
    {
      role: 'execution',
      before: null,
      after: { mode: 'ask', profile: 'step-high', runtime: 'r1', adapter: 'a1', provider: 'prov', model: 'm1', thinking: '' },
    },
    {
      role: 'review',
      before: { mode: 'ask', profile: '', runtime: '', adapter: '', provider: 'Anthropic', model: 'claude-x', thinking: '' },
      after: { mode: 'plan', profile: '', runtime: '', adapter: '', provider: '', model: '', thinking: '' },
    },
    {
      role: 'tools',
      before: { mode: 'ask', profile: '', runtime: '', adapter: '', provider: '', model: 'gpt-x', thinking: '' },
      after: null,
    },
  ],
  changed: true,
  dry_run: true,
  needs_yes: true,
  notes: ['note-1'],
  resources: [
    { resource: 'roles', changed: true, changed_keys: ['execution'] },
    { resource: 'config', changed: true, changed_keys: [] },
    { resource: 'roles', changed: false, changed_keys: [] },
  ],
  running_attempts: ['ui-readonly-api/attempt-001'],
  unreadable: ['读取不到 roles/build'],
  warnings: ['模型 claude-x 不在 pi --list-models 的列表里'],
};

beforeEach(() => {
  posts.length = 0;
  raws.length = 0;
  nextPost = null;
  nextRaw = null;
  postError = null;
  window.location.hash = '';
  setLiveClientForTests(fakeClient);
});

afterEach(() => {
  setLiveClientForTests(undefined);
  window.location.hash = '';
});

describe('api.ts 真实分支：preview（T037 合同）', () => {
  it('路径 /api/v1/preview、正文 {action, args}、时限 30 秒；PreviewData 按映射规则给出', async () => {
    nextPost = {
      status: 200,
      body: okEnv({ preview: servicePreview, confirmation: 'c12345' }, ['config', 'preset', 'use', 'default', '--dry-run', '--json']),
    };
    const reply = await api.preview('preset.use', { name: 'default' });
    expect(posts.length).toBe(1);
    expect(posts[0].path).toBe('/api/v1/preview');
    expect(posts[0].body).toEqual({ action: 'preset.use', args: { name: 'default' } });
    expect(posts[0].timeoutSeconds).toBe(30);
    expect(reply.status).toBe(200);
    expect(reply.body.ok).toBe(true);
    const data: any = reply.body.data;
    expect(data.binding_changes).toEqual([
      { role: 'execution', from: '—', to: 'step-high' },
      { role: 'review', from: 'Anthropic/claude-x', to: 'plan' },
      { role: 'tools', from: 'gpt-x', to: '—' },
    ]);
    expect(data.resources).toEqual(['roles', 'config', 'roles']);
    expect(data.notes).toEqual(['note-1', '读取不到 roles/build']);
    expect(data.warnings).toEqual(['模型 claude-x 不在 pi --list-models 的列表里']);
    expect(data.running_attempts).toEqual(['ui-readonly-api/attempt-001']);
    expect(data.needs_yes).toBe(true);
    expect(data.command).toEqual(['config', 'preset', 'use', 'default', '--dry-run', '--json']);
    expect(data.confirmation).toBe('c12345');
  });

  it('参数整理：number 键转成 JSON 数字（转不成原样传）；空串与空数组不传；数组按顺序原样传', async () => {
    nextPost = { status: 200, body: okEnv({ preview: { dry_run: true }, confirmation: 'c2' }) };
    await api.preview('config.rollback', { number: '41' });
    expect(posts[0].body).toEqual({ action: 'config.rollback', args: { number: 41 } });
    expect(typeof posts[0].body.args.number).toBe('number');
    await api.preview('config.rollback', { number: 'x4?' });
    expect(posts[1].body).toEqual({ action: 'config.rollback', args: { number: 'x4?' } });
    await api.preview('profile.edit', { profile: 'p1', model: '', thinking: '', credential_env: [] });
    expect(posts[2].body).toEqual({ action: 'profile.edit', args: { profile: 'p1' } });
    await api.preview('profile.add', { profile: 'p2', runtime: 'r', model: 'm', credential_env: ['A', 'B'] });
    expect(posts[3].body).toEqual({
      action: 'profile.add',
      args: { profile: 'p2', runtime: 'r', model: 'm', credential_env: ['A', 'B'] },
    });
    await api.preview('hub.set', { post: 'build', profile: 'step-high', fallback: '' });
    expect(posts[4].body).toEqual({ action: 'hub.set', args: { post: 'build', profile: 'step-high' } });
  });

  it('预览不成：400/500/503 与 200-ok:false 的信封原样透传，不改写成 501、不签发确认号', async () => {
    const bad400 = failEnv(['ERROR: model 不合法']);
    nextPost = { status: 400, body: bad400 };
    const r400 = await api.preview('profile.add', { profile: 'p1', runtime: 'r', model: 'm' });
    expect(r400.status).toBe(400);
    expect(r400.body).toEqual(bad400);
    const bad500 = failEnv(['ERROR 内核的预览不合格']);
    nextPost = { status: 500, body: bad500 };
    const r500 = await api.preview('profile.add', { profile: 'p1', runtime: 'r', model: 'm' });
    expect(r500.status).toBe(500);
    expect(r500.body).toEqual(bad500);
    const busy = failEnv(['ERROR 服务繁忙，请稍后重试']);
    nextPost = { status: 503, body: busy };
    const r503 = await api.preview('preset.use', { name: 'default' });
    expect(r503.status).toBe(503);
    expect(r503.body).toEqual(busy);
    const kernelFail = { ok: false, exit_code: 2, data: null, output: [], messages: ['ERROR 预览不合格：参数不符合组合规则'], command: ['config', 'preset', 'use', 'default', '--dry-run', '--json'], elapsed_ms: 9 };
    nextPost = { status: 200, body: kernelFail };
    const r200 = await api.preview('preset.use', { name: 'default' });
    expect(r200.status).toBe(200);
    expect(r200.body).toEqual(kernelFail);
  });

  it('200 且 ok 但 data 缺 confirmation：信封原样透传（不签发确认号）', async () => {
    const env = okEnv({ preview: servicePreview }, ['config', 'preset', 'use', 'default', '--dry-run', '--json']);
    nextPost = { status: 200, body: env };
    const reply = await api.preview('preset.use', { name: 'default' });
    expect(reply.status).toBe(200);
    expect(reply.body).toEqual(env);
  });

  it('没有回应：preview reject（「预览失败：服务没有回应」的那条路）', async () => {
    postError = new Error('ERROR: 连不上本机服务（请求没有到达服务）');
    await expect(api.preview('preset.use', { name: 'default' })).rejects.toThrow('连不上本机服务');
  });
});

describe('api.ts 真实分支：getOperation（T037 合同）', () => {
  it('GET /api/v1/operations/<encodeURIComponent(id)>、时限 30 秒；200 包成 ok 信封、data 是八键视图', async () => {
    const opBody = {
      id: 'op 1/x',
      action: 'config rollback',
      state: 'succeeded',
      reason: null,
      created_ms: 1,
      started_ms: 2,
      finished_ms: 3,
      envelope: { ok: true, exit_code: 0, data: null, output: [], messages: [], command: ['config', 'rollback', '41'], elapsed_ms: 5 },
    };
    nextRaw = { status: 200, body: opBody };
    const reply = await api.getOperation('op 1/x');
    expect(raws.length).toBe(1);
    expect(raws[0].path).toBe('/api/v1/operations/op%201%2Fx');
    expect(raws[0].timeoutSeconds).toBe(30);
    expect(reply.status).toBe(200);
    expect(reply.body.ok).toBe(true);
    expect(reply.body.exit_code).toBe(0);
    expect(reply.body.messages).toEqual([]);
    expect(reply.body.data).toEqual(opBody);
  });

  it('200 但 envelope 不是合法七字段信封 → 视图的 envelope 取 null，其余七键照取；正文不是对象或缺 state → data 取 null', async () => {
    nextRaw = {
      status: 200,
      body: { id: 'o2', action: 'x', state: 'failed', reason: 'exit', created_ms: 1, started_ms: 2, finished_ms: 3, envelope: { foo: 1 } },
    };
    const a = await api.getOperation('o2');
    expect(a.status).toBe(200);
    const view: any = a.body.data;
    expect(view.id).toBe('o2');
    expect(view.state).toBe('failed');
    expect(view.reason).toBe('exit');
    expect(view.envelope).toBeNull();
    nextRaw = { status: 200, body: 'plain' };
    const b = await api.getOperation('o3');
    expect(b.status).toBe(200);
    expect(b.body.ok).toBe(true);
    expect(b.body.data).toBeNull();
    nextRaw = { status: 200, body: { id: 'o4', action: 'x' } };
    const c = await api.getOperation('o4');
    expect(c.body.data).toBeNull();
  });

  it('404：状态码与信封原样透传（「结果未知」与「过期」分得开）', async () => {
    const nf = failEnv(['ERROR: 没有这个操作']);
    nextRaw = { status: 404, body: nf };
    const reply = await api.getOperation('gone');
    expect(reply.status).toBe(404);
    expect(reply.body).toEqual(nf);
    expect(raws.length).toBe(1);
  });
});

describe('api.ts 真实分支：十个写函数（T037 合同的表）', () => {
  const ROWS: Array<{ name: string; run: () => Promise<{ status: number; body: any }>; path: string; body: any }> = [
    { name: 'usePreset', run: () => api.usePreset('economy', 'c1'), path: '/api/v1/presets/economy/use', body: { confirmation: 'c1' } },
    { name: 'setPluginEnabled(true)', run: () => api.setPluginEnabled('decisions', true, 'c1'), path: '/api/v1/plugins/decisions/enable', body: { confirmation: 'c1' } },
    { name: 'setPluginEnabled(false)', run: () => api.setPluginEnabled('decisions', false, 'c1'), path: '/api/v1/plugins/decisions/disable', body: { confirmation: 'c1' } },
    { name: 'removePreset（路径段编码）', run: () => api.removePreset('a b/c', 'c1'), path: '/api/v1/presets/a%20b%2Fc/remove', body: { confirmation: 'c1' } },
    { name: 'removeProfile', run: () => api.removeProfile('p1', 'c1'), path: '/api/v1/profiles/p1/remove', body: { confirmation: 'c1' } },
    { name: 'removeRuntime', run: () => api.removeRuntime('r1', 'c1'), path: '/api/v1/runtimes/r1/remove', body: { confirmation: 'c1' } },
    { name: 'rollback', run: () => api.rollback(41, 'c1'), path: '/api/v1/config/rollback/41', body: { confirmation: 'c1' } },
    {
      name: 'addProfile（空串与空数组不传）',
      run: () => api.addProfile({ profile: 'p2', runtime: 'r', model: 'm', thinking: '', credential_env: [] }, 'c1'),
      path: '/api/v1/profiles/p2/add',
      body: { confirmation: 'c1', runtime: 'r', model: 'm' },
    },
    {
      name: 'editProfile（数组按顺序原样）',
      run: () => api.editProfile({ profile: 'p1', model: 'm2', credential_env: ['A', 'B'] }, 'c1'),
      path: '/api/v1/profiles/p1/edit',
      body: { confirmation: 'c1', model: 'm2', credential_env: ['A', 'B'] },
    },
    {
      name: 'setHubRole',
      run: () => api.setHubRole({ post: 'build', profile: 'step-high', fallback: 'step-low' }, 'c1'),
      path: '/api/v1/hub/roles/build',
      body: { confirmation: 'c1', profile: 'step-high', fallback: 'step-low' },
    },
    {
      name: 'setHubRole（不带 fallback）',
      run: () => api.setHubRole({ post: 'review', profile: 'step-high' }, 'c1'),
      path: '/api/v1/hub/roles/review',
      body: { confirmation: 'c1', profile: 'step-high' },
    },
    { name: 'unsetHubRole', run: () => api.unsetHubRole('build', 'c1'), path: '/api/v1/hub/roles/build/unset', body: { confirmation: 'c1' } },
  ];

  for (const row of ROWS) {
    it(`${row.name} → POST ${row.path}，正文 ${JSON.stringify(row.body)}，时限 90 秒，不再回 501`, async () => {
      nextPost = { status: 200, body: okEnv(null) };
      const reply = await row.run();
      expect(reply.status).toBe(200);
      expect(posts.length).toBe(1);
      expect(posts[0].path).toBe(row.path);
      expect(posts[0].body).toEqual(row.body);
      expect(posts[0].timeoutSeconds).toBe(90);
    });
  }

  it('执行回 409 且 exit_code null（确认号无效/过期/参数不符）→ 原样透传；没有回应 → reject', async () => {
    nextPost = { status: 409, body: failEnv(['ERROR 确认号无效、已过期或已用过：请重新预览']) };
    const reply = await api.removePreset('old', 'c1');
    expect(reply.status).toBe(409);
    expect(reply.body.ok).toBe(false);
    expect(reply.body.exit_code).toBeNull();
    postError = new Error('ERROR: 连不上本机服务（请求没有到达服务）');
    await expect(api.usePreset('economy', 'c1')).rejects.toThrow('连不上本机服务');
  });
});
"""

PROBE_MOCK = r"""
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mockPreview, mockSetHubRole, mockUnsetHubRole } from '../src/mock/writes';

beforeEach(() => {
  window.location.hash = '';
});

afterEach(() => {
  window.location.hash = '';
});

describe('mock/writes：hub.set 与 hub.unset（T037 合同）', () => {
  it('hub.set 预览：command 带 --fallback、binding_changes 恒空、resources 为 [\'hub\']、签发确认号；执行核对通过', async () => {
    const pre = await mockPreview('hub.set', { post: 'build', profile: 'step-high', fallback: 'step-low' });
    expect(pre.status).toBe(200);
    const data: any = pre.body.data;
    expect(data.command).toEqual(['config', 'hub', 'set', 'build', 'step-high', '--fallback=step-low', '--dry-run', '--json']);
    expect(data.binding_changes).toEqual([]);
    expect(data.resources).toEqual(['hub']);
    expect(typeof data.confirmation).toBe('string');
    expect(data.confirmation.length).toBeGreaterThanOrEqual(40);
    const okReply = await mockSetHubRole({ post: 'build', profile: 'step-high', fallback: 'step-low' }, data.confirmation);
    expect(okReply.status).toBe(200);
    expect(okReply.body.ok).toBe(true);
  });

  it('hub.set 不带 fallback：command 不带 --fallback 开关', async () => {
    const pre = await mockPreview('hub.set', { post: 'build', profile: 'step-high' });
    const data: any = pre.body.data;
    expect(data.command).toEqual(['config', 'hub', 'set', 'build', 'step-high', '--dry-run', '--json']);
    expect(data.resources).toEqual(['hub']);
  });

  it('hub.set 的确认号与参数核对：丢项 / 号不存在 → 409 且 exit_code null', async () => {
    const pre = await mockPreview('hub.set', { post: 'build', profile: 'step-high', fallback: 'step-low' });
    const confirmation = (pre.body.data as any).confirmation;
    const mismatch = await mockSetHubRole({ post: 'build', profile: 'step-high' }, confirmation);
    expect(mismatch.status).toBe(409);
    expect(mismatch.body.exit_code).toBeNull();
    expect(mismatch.body.messages[0]).toContain('确认号');
    const noOp = await mockSetHubRole({ post: 'build', profile: 'step-high', fallback: 'step-low' }, 'n' + 'x'.repeat(42));
    expect(noOp.status).toBe(409);
    expect(noOp.body.exit_code).toBeNull();
  });

  it('hub.unset 预览与执行：command 一致、核对通过；post 不符 → 409', async () => {
    const pre = await mockPreview('hub.unset', { post: 'review' });
    const data: any = pre.body.data;
    expect(data.command).toEqual(['config', 'hub', 'unset', 'review', '--dry-run', '--json']);
    expect(data.binding_changes).toEqual([]);
    expect(data.resources).toEqual(['hub']);
    const okReply = await mockUnsetHubRole('review', data.confirmation);
    expect(okReply.status).toBe(200);
    expect(okReply.body.ok).toBe(true);
    const wrongPost = await mockUnsetHubRole('build', data.confirmation);
    expect(wrongPost.status).toBe(409);
    expect(wrongPost.body.exit_code).toBeNull();
  });

  it('?write= 情景照旧作用于 hub 写：busy → 503 服务繁忙', async () => {
    window.location.hash = '#/roles?write=busy';
    const pre = await mockPreview('hub.set', { post: 'build', profile: 'step-high', fallback: 'step-low' });
    const confirmation = (pre.body.data as any).confirmation;
    const reply = await mockSetHubRole({ post: 'build', profile: 'step-high', fallback: 'step-low' }, confirmation);
    expect(reply.status).toBe(503);
    expect(reply.body.messages[0]).toContain('服务繁忙');
  });
});
"""

PROBE_SPECS = {
    "post": (PROBE_POST, (TRANSPORT_REL, MODE_REL)),
    "api": (PROBE_API, (API_REL, MODE_REL)),
    "mock": (PROBE_MOCK, (MOCKWRITES_REL,)),
}
PROBE_ORDER = ("post", "api", "mock")


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
    "probe": 110,
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
                name = f"probe-{uid}-t037-{key}.test.ts"
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
    """P1 / V01、V02、D13、D14：npm ci（或已在的依赖）、npm test（全绿）、npm run build
    （tsc --noEmit + vite build）都退出 0；依赖文件一个字节没动。"""
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


def test_p2_probe_post(pipeline):
    """P2 / D01、D02：传输层 post/getRaw 探针全绿（请求形状、状态码原样、合成信封、断线与超时
    reject、getRaw 的八键与 404）。"""
    assert_probe_ok(pipeline, "post")


def test_p3_probe_api(pipeline):
    """P3 / D05–D08、D10：api.ts 真实分支探针全绿（preview 的整理与映射、失败透传、getOperation
    的视图与 404、十个写函数的路径/正文/90 秒、reject、不再 501）。"""
    assert_probe_ok(pipeline, "api")


def test_p4_probe_mock(pipeline):
    """P4 / D09：mock/writes.ts 的 hub 桩探针全绿（argv、确认号与参数核对、情景照旧）。"""
    assert_probe_ok(pipeline, "mock")
