# 复审记录：t033-desktop-shell-service attempt-001（七端信箱 hub）

- 合同：t033-desktop-shell-service.v1（base aebf35503940cdefb5b39833ba51a442f282b6ee）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261113T070616320461Z-3ad5），终审报告如下

## 终审报告

# T033-7-audit-post 终审报告（审核端 audit-sonnet）

- 回合：T033-7-audit-post，2026-11-13T07:06Z 起，40 分钟时限
- 候选：`aebf355` 基线 + `.agent/runs/t033-desktop-shell-service/attempt-001/candidate.patch`（候选树 `75c9d4bd`）
- 结论：**通过**（无阻塞项；3 条不挡的意见见第 7 节）

---

## 1. 结论与依据

终审通过。候选补丁忠实于合同《Behavior contract》第 1–10 节，改动只落在 Scope 允许集合内，没有越界、没有弱化既有测试、没有为过测试写的特判；执行报告的 DoD 自述与源码、断言、内核记录逐条对得上。战后门禁声明「W2 预期抓不住」的 9 条变异，我逐条核了 W1 侧是否真有断言能抓住，结论是能，不算漏网。

JEV 判断是 `no_opinion auth_failed`（6j-jev 报告全文两行，没有意见），所以本回合没有可对照的 JEV 结论——这一条只能算审核端本轮的局限，不是候选的缺陷。

## 2. 源码逐条核对（读的是工作目录里的候选树）

### 2.1 `src/serviceflow.js`（新增，纯模块，不 require electron）
- 状态机 `idle → starting → running → exited`，`moveTo` 开头有 `if (current.kind === "exited") return;`（合同「只前进不后退、重复 exited 不覆盖」）✔
- 退出码映射：`codeOf()` 有数字码就用数字码，否则 `-1`（合同第 6 节）✔；`at` 取 `now()`、`startedAt` 取 `new Date(now()).toISOString()` ✔
- 借 `src/service.js` 的 `spawn` 选项拿子进程：包一层 `wrapped` 后传给 `startService({command, spawn: wrapped, env, timeoutMs})`，`src/service.js` 一字未改（不在改动文件表里）✔
- 失败次序：`start()` 的 catch 里先 `moveTo(exited)` 再回信封；spawn 失败回 `start-failed`，其余回 `handshake-failed` ✔（合同第 2 节）
- `onRunning` 抛错 → `await stop()` → 状态 `exited`、回 `start-failed` ✔
- 控制令牌只在 `onRunning` 的实参里；状态、事件负载、信封里都没有 ✔（状态字段只有 kind/repo/pid/startedAt/exitCode/at）
- `byShell` 只在订阅回调第二个实参里（`stopping || aborting`），不进状态 ✔
- `stop()` 回 `{exited, code, signal}` 三个键（`stopService` 的第四个键 `killed` 没外传）✔；`abort()` 立刻 `kill()`、等 exit 最多 3 秒、超时再 SIGKILL ✔
- 「不是 idle 就 start」回 `busy`（执行端解读 4，合同未写死，门禁已钉）

### 2.2 `src/shellipc.js`
- 新导出 `SERVICE_STATE_CHANNEL = "themis-shell:service-state"`，**不在** `SHELL_CHANNELS` 里；`SHELL_CHANNELS` 仍恰好九个、名字与顺序逐字不变；`SHELL_METHOD`/`SHELL_ARITY`/`registerShellIpc`/`shellSenderAllowed` 未动 ✔

### 2.3 `src/shellapi.js`
- 可选注入 `service`/`assets`；没有控制器时 `getState().service` 仍是 `{kind:"idle"}`、`startService` 回 `no-service` ✔
- `startService(repoId)`：按 **id** 查设置 → 查不到 `unknown-repo`（不起进程）→ busy/幂等 → `python-missing` → **kit 按目标仓库算**（`kitPath` 优先，否则目标仓库 `path`；现场 `probeKit`，不读 `kitInfo` 的当前仓库缓存）→ `kit-missing` → 同一个 `serviceCommand` 拼命令 → 交控制器并原样回信封 ✔
- `restartService` 仍回 `not-implemented`（A 片过渡）✔；`on` 真订阅、只传 `state` 一个实参、别的事件名回空退订函数 ✔；照旧 require `./settings`/`./detect`/`./hostcheck` ✔

### 2.4 `shell-preload.js`
- 自包含（只 require electron）、恰好一次 `exposeInMainWorld`、暴露面十个成员 ✔
- 模块加载时只注册 **一个** `ipcRenderer.on`，频道是字面量 ✔；监听函数只收到 `state` 一个实参（事件对象不过桥）✔；别的事件名同步回空退订函数 ✔；`on` 与退订都不发 invoke/send ✔；文件里无 `ipcRenderer.send`、无相对路径/`node:` require ✔
- 例外见第 7 节第 ① 条（Set 存监听，同一函数引用重复 `on` 的边角）

### 2.5 `main.js`
- `flow = createServiceFlow({onRunning})`，`createShellApi` 多注入 `service: flow` 与 `assets: root` ✔
- `flow.subscribe((state, info) => …)`：`if (!win.isDestroyed()) win.webContents.send(SERVICE_STATE_CHANNEL, state);`——只发 `state` 一个实参、只发给当前外壳页窗口 ✔
- `onRunning`：`createHost({origin, control, repo, …})`（repo 由 id 查回路径，执行端解读 1）→ `registerHostIpc(ipcMain, host, senderAllowed)`（来源三条件）→ `guardedWindow` 开服务窗口（新 `partitionName()`、`mainWebPreferences(分区, preload.js)`、`isServiceUrl` 判定）→ **之后**才 `closedByShell = true; win.close();`（先建后关，任何时刻不出现零窗口）✔
- 用户关外壳页：`closedByShell` 为假 → 状态 `starting` 先 `await flow.abort()`、`running` 先 `await flow.stop()`（解读 2）→ `app.exit(0)`；`closedByShell` 为真 → 不退出应用 ✔
- 用户关服务窗口 → `await flow.stop()` → `exited && code === 0` → `app.exit(0)`；否则写一行 `ERROR: 服务没有以 0 正常退出` → `app.exit(1)`（与带参数那条路同一句）✔
- 服务在 `running` 期间自己退出（`info.byShell` 为假）→ 写一行 `ERROR: 服务意外退出（退出码 N）` → 关服务窗口 → `app.exit(1)`；`serviceGone` 防同一次退出被收两次 ✔
- 既有形状未破：`new BrowserWindow` 恰好一处（`guardedWindow`）、`launchMode(` 早于 `runShell(`、`runShell` 五键不变、服务分支整体未改 ✔

### 2.6 范围与依赖
改动文件恰为 12 个：README.md、main.js、package.json、shell-preload.js、src/serviceflow.js(A)、src/shellapi.js、src/shellipc.js、tests/fixtures/fake-service-exit.js(A)、tests/serviceflow.test.js(A)、tests/shellapi.test.js、tests/shellipc.test.js、tests/shellpreload.test.js——全在 allowed 集合内；`package-lock.json`、`desktop/web/**`、`ts/**`、`scripts/**`、其余 `src/**` 与 `preload.js` 未动；`devDependencies` 仍 `{"electron": "44.9.0"}` ✔（内核 scope 报「越界 0」，警告只有 package.json 的 dependency_manifest_changed——那是「允许改此文件但禁止依赖变更」的人工确认提示，实际依赖没变）

## 3. DoD → 测试 → 断言 映射（我逐条复核后的判定）

| DoD | 证明它的测试与断言 | 我的判定 |
|---|---|---|
| D01 | 包内 `tests/shellapi.test.js`（改写的那一条）：`ctl.starts.length === 0`（unknown-repo 不起进程）、`kitCalls[0]` 逐字等于目标仓库目录、命令 `deepEqual(serviceCommand({...}))`；门禁 P02 探针 + 白盒 W04（kit 缓存不串味、busy 先于 no-service） | 成立 |
| D02 | `tests/serviceflow.test.js`「starting → running」（pid 取握手的 4242、startedAt 可 `Date.parse`）；窗口次序靠门禁 S04/W01 的文本次序断言 + 人工审阅（不跑真 Electron） | 成立（窗口次序部分只能人工审阅 + 静态断言，已如实标注） |
| D03 | `tests/shellipc.test.js` 新增一条（常量逐字、不在 SHELL_CHANNELS、九个不变、preload 源码里的字面量一致）；W01 断言 `webContents.send(SERVICE_STATE_CHANNEL, state)` 整句恰好一次 | 成立 |
| D04 | `tests/shellpreload.test.js` 改写的两条：只注册一个监听、页面监听只收到一个实参、退订一个另一个照收、重复退订不抛错、别的事件名不发 IPC；门禁 P04 | 成立 |
| D05 | `tests/serviceflow.test.js`（exit2→2、坏握手/超时→-1、外部信号杀→-1、stop/abort→byShell true、自己退出→byShell false）；白盒 W03「注入的 now」「onRunning 抛错」「被外部杀掉」 | 成立 |
| D06 | 门禁 S04 与 `test_transitional_s05`、白盒 W01（两句 ERROR 文案 + 各自 `app.exit(1)` 的行次序）；真机行为只能人工审阅/冒烟 | 成立（退出码与文案有断言，关窗收尾的真实行为只能人工审阅） |
| D07 | `tests/serviceflow.test.js` abort 用例：轮询 `child.exitCode/signalCode` 证明子进程真退出、状态 `exited`、`byShell === true`；W01 断言 `await flow.abort()` 那行 | 成立 |
| D08 | `tests/serviceflow.test.js` 对每条状态与事件断言 `!JSON.stringify(s).includes("ctrl-tok")`；createHost 闭包靠人工审阅 | 成立 |
| D09 | 门禁 S01–S03（词面扫描、`new BrowserWindow` 一处、接线标记、`launchMode` 早于 `runShell`）；`package.json` 的 `scripts.test` 点名 21 个 `tests/*.test.js`，与 `tests/` 目录实际 21 个一致（`tests/package.test.js` 也断言这一点） | 成立 |
| D10 | 逐文件 diff：三份既有测试只改了合同点名的条目（shellapi 一条占位用例、shellpreload 两条、shellipc 新增一条），其余 20 份文件未出现在补丁里 | 成立 |
| D11 | README 现状逐条比对 T025/T026/T028/T030 的 needle 清单（`## 外壳页`、`themis-shell://app/index.html#/first-run`、`desktop/web/dist`、`npm --prefix ../web run build`、`themisShell`、`桩数据`、`standard`、`secure`、`404`、`themis-shell:get-state`、`外壳页在本片就位`、T026 的 28 个词、T028/T025 的词）——**全部仍在**；门禁 S06 + 白盒 W02 | 成立 |
| D12 | 改动清单与 `checks.json`（`covers_all_required: true`、`candidate_files_modified: []`）；锁文件与依赖未动 | 成立 |
| D13 | 补丁 diff 中没有删除/改名/弱化任何既有断言；被替换的两条正是合同第 8 节点名要改写的 | 成立 |

## 4. 有没有越界或弱化测试

- 新测试测的是真实现：`tests/serviceflow.test.js` 真起子进程（夹具 `fake-service.js` / `fake-service-exit.js`），不 mock `child_process`；等子进程一律轮询（`waitFor`），不固定睡几百毫秒 ✔
- 断言是实质的，不是空心的：unknown-repo 断言「控制器没被调用」、kit 断言「探测的是目标仓库目录且不是当前仓库目录」、命令逐字 `deepEqual(serviceCommand(...))`、令牌不出现在任何状态/事件、`byShell` 真假两路都测 ✔
- 没有发现「为过测试而写的特判」：serviceflow.js 里没有针对测试的名字/路径/环境的分支；main.js 里的分支都有业务语义 ✔
- 异常处理不是空的：`onRunning` 抛错 → 收服务 + `start-failed`；服务窗口加载失败 → 关窗并让 `onRunning` 抛错（解读 7）；abort 的 `child.kill()` 有 try/catch 与 SIGKILL 兜底 ✔
- 范围没有悄悄扩大：`src/service.js`、`src/window.js` 等只读模块一字未改，事件通道没有进 `SHELL_CHANNELS`，`preload.js`（服务页的）未动 ✔

## 5. 门禁记录复核（战后门禁 T033-6-gate-post）

- 变异清单 32 条，执行端改的 8 个非测试文件每个至少一条；基线命令在候选上：W1 15 passed、W2 296 pass/0 fail ✔
- 门禁端标「这条命令预期抓不住（W2）」的 9 条，我逐条核了 W1 侧是否真有断言：
  - `m-flow-startedat` → W03「注入的 now」断言 `startedAt === new Date(FIXED).toISOString()` ✔
  - `m-flow-now-inject` → 同上断言 `events[1].at === FIXED` ✔
  - `m-main-send-arg` → W01 断言 `if (!win.isDestroyed()) win.webContents.send(SERVICE_STATE_CHANNEL, state);` 恰好一次（少传 state 就对不上整句）✔
  - `m-main-abort` → W01 断言 `'  if (state.kind === "starting") await flow.abort();' in text` ✔
  - `m-main-running-stop` → W01 断言对应的 `else if (state.kind === "running") await flow.stop();` ✔
  - `m-main-unexpected-exit-code` → W01 断言「服务意外退出（退出码」下一行 `serviceWindow.close();`、再下一行 `app.exit(1);` ✔
  - `m-main-inject-flow` → W01 断言 `"    service: flow,"` 恰好一次 ✔
  - `m-readme-smoke-t032` → W02 needle「**页面上的点击要等 T032 落地**」✔
  - `m-readme-exit-row` → W02 needle「服务意外退出（外壳页分支：服务在 `running` 期间自己退出）」（表行独有片段）✔
  → 9 条都不是漏网，门禁端声明成立。
- 门禁端列的两条「不构成缺陷」：preload 的 Set 固有语义、意外退出的竞态窗口——我同意不算阻塞（见第 7 节），但门禁报告里「合同未定义同函数重复注册的行为」这句不够准确（合同第 4 节写了「每次 on 登记一个独立订阅」），已写进第 7 节第 ① 条。

## 6. 执行报告自述 ↔ 内核摘要/检查记录 逐条对照

- 内核摘要的「临时路径」线索（新增被 Git 忽略的 `.pytest_cache/`、`desktop/web/dist/`、`node_modules/`）：都是 Git 忽略项，不在候选补丁里（补丁只含 12 个受控文件），不构成越界；`desktop/web/dist` 与 `node_modules` 是为了跑前端构建/装依赖留下的，不影响候选 ✔
- 内核摘要的「可疑命令」线索：`kill 448 …; pkill -f "test_gate_t001_baseline" …; rm -f .agent-runs-r01.log; git status --short` —— 是 R01 期间的探索性清场（收掉卡住的 T001 进程、删自己写的日志）。它**不与执行报告的任何自述冲突**：报告里三条检查（V01/G01/R01）都写了 `set -o pipefail`，内核摘要标的那 5 条被管道掩盖的是探索命令，不是这三条；被删的 `.agent-runs-r01.log` 不在候选里。所以**不判自述不实**，但建议执行端以后把这类杀进程/清理命令写进报告的「遗留与限制」。
- 执行报告自述的缺口「R01 在最后两处改动（`moveTo` 守卫与 README 一处措辞）后没重跑」：内核在**最终候选树**上独立跑了 R01 → `824 passed in 1076.82s`，退出码 0，`output_must_match "\d+ passed"` 命中；G01 `11 passed`；V01 `npm test` 退出码 0、`# pass 296`。所以这个缺口已被内核的检查补上，不构成遗留 ✔
- 执行报告的 8 条 interpretations 与源码一致（我逐条对过实现），未发现报告与代码不符之处；`contract_conflicts` 为空数组，与合同文本不冲突 ✔

## 7. 不挡的意见（交站主决定，不进阻塞项）

① **preload 的 Set 语义**：`subscriptions` 是 `Set<listener>`，`on` 直接 `add(listener)`。合同第 4 节写「每次 `on` 登记**一个独立订阅**；返回的退订函数**只删自己那一条**」，第 8 节又写「假 electron 里不需要 `removeListener`/`off`（**用 Set 方案**）」——两句有张力。触发路径：页面把**同一个函数引用** `on('service-state', f)` 注册两次，再退订其中一个 → 另一个也失效（Set 里只有一条）。概率：低（外壳页还没接线，T032 才写页面；正常写法每次传新的箭头函数就没问题）。要多写：把 Set 里存的东西从「函数」改成「每次 `on` 的一个包装条目」，约 3 行。建议：B 片或 T032 落地前按站主意见改，或在 T032 的页面契约里写明「同一函数重复注册不保证独立」。
② **意外退出的窄竞态**：`main.js` 的意外退出分支以 `serviceWindow !== null` 为前提。`running` 状态发出到服务窗口建成之间若服务自己退出，这条分支不触发，最终走「服务没有以 0 正常退出」那句（退出码仍是 1，只是文案与合同第 3 节第 6 条不同）。概率：低（要服务握手后立刻死），需要真 Electron 才触发。建议：留到真机冒烟；B 片回服务状态页时把这段窗口一并收进新逻辑。
③ **失败之后不能再起（属 B 片）**：控制器的状态机只前进不后退，`exited` 之后 `start` 回 `busy`（执行端解读 4，门禁已钉）。所以本片里「第一次起服务失败 → 再点启动」这条路是断的（页面拿到 `busy`）。这在合同 Non-goals（「第二次起服务的接线」是 B 片）之内，不是本片的偏离，但 B 片若只做「回服务状态页 + 重启」而不处理重试语义，用户会卡在起不来服务上——已写进下游须知。
④ 附带提醒（非缺陷）：执行报告里的 DoD D06/D07 的「关窗收服务 / 意外退出以 1 退出」没有包内单测覆盖（main.js 没有可单测的纯逻辑），只有静态接线断言 + 人工审阅；合同本身也允许（证据写的是 G01 + review）。

## 8. 本回合的局限

- 未跑真 Electron（合同禁止），窗口次序、关窗收服务、意外退出三条真机行为只有静态断言与代码审阅支撑。
- 本回合我没有执行命令（审核端只有读工具）；所有「绿」的结论都引用内核在候选树上的独立检查与门禁端的记录，并核对了日志内容。
- JEV 报告是 `no_opinion auth_failed`，没有可对照的意见。

Verdict: PASS
