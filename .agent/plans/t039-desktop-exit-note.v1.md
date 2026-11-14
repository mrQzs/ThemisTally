# TASK: t039-desktop-exit-note

<!-- 桌面端外壳第 7 片（D3 收尾）：服务状态页按“跑起来之后才退出”写说明。
     基线：b71819daedea8ff35bc397807505cc4ed4b1a854（站主的门禁准备提交 b71819d 已合入：T032 的过渡断言
     test_transitional_s09_baseline_files_untouched 已按名字退役 src/shellpages/themisShell.ts、
     src/mock/shellpages-scenarios.ts、tests/shellpages-service-status.test.tsx 三项，s09 其余项照旧冻结、整条不退役）。
     改动：外壳 3 个文件（serviceflow.js 及其测试、README）＋ 前端 5 个文件（类型、说明、视图、夹具、页面测试）。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 65b3bdd2cf0d17d94bb5cbdba11777774273dcab
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
外壳给“进过 running 之后才退出”的 exited 状态带一个 `afterRunning: true`（启动阶段的退出不带这个键），服务状态页据此一律显示“本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。”，退出码那一行照旧显示真实码；不带这个键的 exited 照旧按退出码给说明（1 是“已经在另一个窗口里打开了”、2 是“应用文件不完整”、其他是“意外退出”）。开发与测试模式的桩补一个“跑起来之后退出、退出码 1”的场景，页面测试覆盖退出码 1 的两种情形，外壳 README 的冒烟第 4 条与状态说明补上对应约定。

## Non-goals
- 不改退出码本身，不改服务（`pi_dispatch.py ui`）的退出码约定，不改 `ts/**`。
- 不改 `desktop/shell/main.js`、`shell-preload.js`、`src/shellapi.js`、`src/shellipc.js`、`src/service.js`：意外退出仍看 `info.byShell`，窗口次序与收尾一字不改。
- 不改桩 `desktop/web/src/shellpages/shellStub.ts`（一个字也不改）。
- 不改首启页：`exitCodes.ts` 的 `firstRunHeadline`、`FirstRunView.tsx`、`firstRunModel.ts` 一字不改；首启第 4 步的错误框不变。
- 不改设计文档（`docs/**`）、不改门禁测试文件（仓库根 `tests/**`）。
- 不删、不改、不弱化任何既有测试；不新增依赖、不动任何 `package.json` 与锁文件。

## Repository facts
- 入口与关键位置（**都是新基线 b71819d 上的行号**）：
  - `desktop/shell/src/serviceflow.js`：`createServiceFlow({spawn, env, timeoutMs, now, onRunning})` → `{start, stop, abort, state, subscribe}`。`moveTo(next, newRun)` 在 `:67`，终态判定 `if (current.kind === "exited" && newRun !== true) return;` 在 `:68`，赋值 `current = next` 在 `:69`；产生 exited 的四处：`:102`（握手成功后服务自己退出）、`:117`（握手失败/起不来）、`:151`（`stop()` 补发）、`:179`（`abort()` 补发）；`running` 状态在 `:123`。
  - `desktop/shell/main.js:194–195`：`flow.subscribe((state, info) => { … webContents.send(SERVICE_STATE_CHANNEL, state) })` —— **状态对象原样转发**，不按字段挑拣；`:198` 的意外退出判定看 `info.byShell`。
  - `desktop/shell/shell-preload.js:12–14`：`ipcRenderer.on("themis-shell:service-state", (_event, state) => { for (const listener of [...subscriptions]) listener(state); })` —— 原样交给页面。
  - `desktop/shell/src/shellapi.js`：`serviceState()` 在 `:128–132` 原样返回控制器的状态；`:144` 把它放进 `stateView()`；`:297–299` 只把 `state` 一个实参交给监听者（`info` 不外传）。
  - `desktop/web/src/shellpages/exitCodes.ts`：三句常量在 `:5`（已经打开）、`:6`（文件不完整）、`:7`（意外退出）；`stoppedNote(code)` 在 `:10`（1→已经打开、2→文件不完整、其他→意外退出）；`firstRunHeadline(code)` 在 `:17`。文件头第 2 行注释写着“接真实外壳那一片再定退出码 1 的两种含义”。
  - `desktop/web/src/shellpages/ServiceStatusView.tsx`：`:9` 从 `./exitCodes` 导入 `stoppedNote`；`:61` `const exited = service.kind === 'exited'`；`:62` 退出码行；`:64` `const note = noteError ?? stoppedNote(exited ? service.exitCode : 0);`；退出码那一行的文字是 `退出码 <code> · <时刻>。重启后会重新读取数据。`。
  - `desktop/web/src/shellpages/themisShell.ts`：`ServiceState` 在 `:32`，exited 分支 `:36` 是 `{ kind: 'exited'; repo: string; exitCode: number; at: number }`；文件头注释说“服务四种状态：idle / starting / running / exited”。
  - `desktop/web/src/mock/shellpages-scenarios.ts`：`exit-1` 场景 `:111`（`start: { kind: 'exited', exitCode: 1 }`）、`exit-2` 紧跟其后、`crash` `:127`（base 是 exited 3，`start: { kind: 'running' }`）；`SHELLPAGE_SCENARIO_NAMES` 在 `:158`（`Object.keys(SHELLPAGE_SCENARIOS)`）；文件头前 15 行标着“示意”，路径用正斜杠。
  - `desktop/web/src/shellpages/shellStub.ts`：初始状态是夹具 `base` 的深拷贝；`start`/`restart` 之后 1500ms 发的 exited 是 `{ kind: 'exited', repo, exitCode, at }`（**不带任何新键**）；本片一个字不改。
  - `desktop/web/src/shellpages/shellContext.tsx:25–38`：`?shell=<名字>` 只在 `SHELLPAGE_SCENARIO_NAMES.includes(value)` 时认；认不出取缺省（服务状态页的缺省是 `crash`）。
  - `desktop/shell/tests/serviceflow.test.js`：`:118–121` 是“握手前退出（exit2）”的 4 键 deepEqual（启动阶段）；后面一条是“握手成功后服务自己退出”（码 3）；`stop()` 那条用例只逐字段断言，不 deepEqual。
  - `desktop/shell/tests/shellshape.test.js`：`typeLiterals`（`:60–79`）按单引号与顶层分号解析 `export type X = …`；`:145–148` 断言 `ServiceState` 的字面量集合与 `st.service.kind` 对得上。
  - `desktop/shell/README.md`：退出码表 `:39–47`（`| **1** |` 在 `:44`，该行现在没有“服务意外退出”，有“服务状态页”）；手工冒烟第 4 条 `:70`（里面有“并显示退出码”）；状态说明 `:189`（现在写着“`ServiceState` 被 `themisShell.ts` 钉死，页面负载多一个键就与类型不符”）。
  - 门禁：`tests/test_gate_t032_baseline.py:117–118`（站主 2026-11-14 按名字退掉三项的说明）与 `UNTOUCHED_REL`（`:119–130`，其余项仍在）；`tests/test_gate_t033_baseline.py:465`（启动失败 exited 的 4 键 deepEqual）、`:779`（假控制器的状态原样透传）、`:800`（事件负载里不许有 `byShell`）；`tests/test_gate_t012_baseline.py:88` 与 `:869–871`（11 个旧场景名都必须在，**没有**“恰好 11 个”的断言）、`:934–958`（三句只在 `exitCodes.ts`、视图从 `./exitCodes` 导入）、`:1721–1750`（桩夹具取值）、`:2460–2495`（服务状态页内容）；`tests/test_gate_t035_baseline.py:430–471`（README：`| **1** |` 行不许出现“服务意外退出”、“服务状态页”至少 2 处、needle 清单）。
- 调用关系：`desktop/shell/src/serviceflow.js`（状态机，唯一产生 `afterRunning` 的地方）→ `main.js` 的 `flow.subscribe` → `SERVICE_STATE_CHANNEL` IPC → `shell-preload.js` → 页面 `useThemisShell()` 的实例 → `ServiceStatusView.tsx` 读 `service.afterRunning` → `exitCodes.ts` 的 `stoppedNote(code, afterRunning)`。全程原样转发，中间没有人按字段挑拣。
- 服务一侧（判断“跑起来之后的退出码 1 不可能是已经打开”的依据）：`ts/packages/ui/src/server.ts:85–89` 先拿锁（锁被占就写 ERROR 并回 `EXIT_ERROR`=1），`:98` 才 `bun.serve`，`:195–198` 最后才写握手行；`ts/packages/ui/src/main.ts:33–35` 的 `EXIT_OK=0 / EXIT_ERROR=1 / EXIT_USAGE=2`。所以“服务已经起来过”与“启动阶段就被占”是两回事，只有新键能分开。
- 工具链与锁文件：`desktop/web/package.json`（npm、Vite 5.4.11、Vitest 2.1.8、TypeScript 5.6.3；`npm test` = `vitest run`，`npm run build` = `tsc --noEmit && vite build`，`npm run check:contract` = `node scripts/token-contract.mjs`）、`desktop/shell/package.json`（commonjs；`npm test` = `node --test --test-reporter=tap` 并逐个列出 22 个 `tests/*.test.js`）。两处的 `package.json` 与锁文件本片一律不动。
- 基线检查（合同端本回合只读探查，**没有执行**任何命令）：基线是 `b71819daedea8ff35bc397807505cc4ed4b1a854`，站主已把 T032 的 `test_transitional_s09_baseline_files_untouched` 里本片要改的三项按名字退役（`tests/test_gate_t032_baseline.py:117–118`），**s09 其余各项照旧冻结、整条断言不退役**。本片自己的门禁文件由门禁端稍后写、内核做成基线提交，纯基线上还没有它（G01 在纯基线上跑不起来属预期）。

## Scope
- allowed_modified_files:
  - desktop/shell/src/serviceflow.js
  - desktop/shell/tests/serviceflow.test.js
  - desktop/shell/README.md
  - desktop/web/src/shellpages/themisShell.ts
  - desktop/web/src/shellpages/exitCodes.ts
  - desktop/web/src/shellpages/ServiceStatusView.tsx
  - desktop/web/src/mock/shellpages-scenarios.ts
  - desktop/web/tests/shellpages-service-status.test.tsx
- allowed_new_files: 无
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/**
  - tests/test_gate_t039_*.py
  - desktop/shell/main.js
  - desktop/shell/preload.js
  - desktop/shell/shell-preload.js
  - desktop/shell/src/shellapi.js
  - desktop/shell/src/shellipc.js
  - desktop/shell/src/service.js
  - desktop/shell/src/host.js
  - desktop/shell/src/hostrelay.js
  - desktop/shell/src/ipc.js
  - desktop/shell/src/core.js
  - desktop/shell/src/settings.js
  - desktop/shell/src/detect.js
  - desktop/shell/src/window.js
  - desktop/shell/src/launch.js
  - desktop/shell/src/hostcheck.js
  - desktop/shell/src/control.js
  - desktop/shell/src/args.js
  - desktop/shell/src/handshake.js
  - desktop/shell/src/python.js
  - desktop/shell/tests/fixtures/**
  - desktop/shell/package.json
  - desktop/shell/package-lock.json
  - desktop/web/src/shellpages/shellStub.ts
  - desktop/web/src/shellpages/shellContext.tsx
  - desktop/web/src/shellpages/shellWindowRoute.ts
  - desktop/web/src/shellpages/shellBridge.ts
  - desktop/web/src/shellpages/ShellWindow.tsx
  - desktop/web/src/shellpages/SettingsView.tsx
  - desktop/web/src/shellpages/FirstRunView.tsx
  - desktop/web/src/shellpages/firstRunModel.ts
  - desktop/web/src/shellpages/ExternalLinkDialog.tsx
  - desktop/web/src/shellpages/LicensesDialog.tsx
  - desktop/web/tests/shellpages-stub.test.ts
  - desktop/web/tests/shellpages-route.test.ts
  - desktop/web/tests/shellpages-first-run.test.tsx
  - desktop/web/tests/shellpages-settings.test.tsx
  - desktop/web/tests/shellpages-app.test.tsx
  - desktop/web/tests/shellpages-isolation.test.tsx
  - desktop/web/tests/shellpages-static.test.ts
  - desktop/web/tests/cleanup2-static.test.ts
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/vite.config.ts
  - desktop/web/scripts/**
  - ts/**
  - docs/**
  - scripts/**
- dependency_changes: forbidden（依赖与锁文件一字不动）
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 一、外壳：exited 的 `afterRunning` 键（`desktop/shell/src/serviceflow.js`）
- **键名**：`afterRunning`（只加不改）。外壳只在“进过 running 之后的退出”上写 `afterRunning: true`。
- **唯一改动点**：`moveTo(next, newRun)` 里，在给 `current` 赋值**之前**判断——`next.kind === "exited"` 且**此刻的** `current.kind === "running"` 时，把 `current` 设成 `{ ...next, afterRunning: true }`；其余情况 `current` 就是 `next` 本身。
- **启动阶段的 exited 一律不带这个键**（不是 `false`、不是 `afterRunning: undefined` 的显式键）：握手失败/起不来（`:117`）、握手前子进程退出、握手超时、spawn 失败、starting 期间 abort（`:179`，此时 `current.kind` 是 `starting`）。判据是“赋值前那一刻的 `current.kind`”，所以天然按 run 算：新 run 先 `starting`，启动阶段的失败不带键。
- **盖住的路径**：握手成功后服务自己退出（`:102`）、跑起来之后外壳自己 `stop()`（`:151`）、`onRunning` 失败后的收服务（走 `stop()` → `:151`）。这三类都带 `afterRunning: true`（外壳自己停的、跑起来之后的退出也带 true）。
- **一字不改的既有语义**：`moveTo` 的终态判定（同一 run 里 exited 不再变，新 run 的 starting 例外）、`info.byShell`（只留在主进程，仍是 `stopping || aborting`、按 run 算）、`start` 的信封（`{ok:true,value:null}` / `{ok:false,reason:"busy"|"start-failed"|"handshake-failed"}`）、`stop()`/`abort()` 的返回值、控制令牌只进 `onRunning` 实参。
- **旧消费方照旧能读**：状态对象多一个可选键，`exitCode`/`at`/`repo`/`kind` 一字不动；`state()` 与事件负载给的是同一个对象。

### 二、前端类型（`desktop/web/src/shellpages/themisShell.ts`）
- `ServiceState` 的 exited 分支加一个可选键：`{ kind: 'exited'; repo: string; exitCode: number; at: number; afterRunning?: boolean }`。
- **类型体里不写注释**（`shellshape.test.js` 的 `typeLiterals` 按单引号与顶层分号解析，类型体里带引号或分号的注释会让解析失败）；说明写在 `ServiceState` 上方那行注释里（例如“exited 带 repo/exitCode/at；跑起来之后才退出的另带 afterRunning”）。
- 其余三个状态分支、十个接口成员、`PickOutcome`、`RepoCheck`、`PickProblem`、`SettingsPatch` 一字不改。

### 三、说明文案（`desktop/web/src/shellpages/exitCodes.ts`）
- `stoppedNote(code: number, afterRunning = false): string`：
  - `afterRunning` 为真 → 返回 `UNEXPECTED`（“本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。”）；
  - 否则照旧：1 → `ALREADY_OPEN`（“这个仓库已经在另一个窗口里打开了。”）、2 → `INCOMPLETE`（“应用文件不完整，请重新安装。”）、其他 → `UNEXPECTED`。
- 默认参数 `= false` 让既有调用点与门禁探针照旧成立（首启页与门禁都只按码调用）。
- 三句常量与 `firstRunHeadline` **一字不改**；文件头第 2 行注释里“接真实外壳那一片再定退出码 1 的两种含义”这句要改成已定的说法（两种含义已由 `afterRunning` 分开）。
- 这三句只放在本模块；视图与首启都从 `./exitCodes` 取，别处不许另写。

### 四、服务状态页（`desktop/web/src/shellpages/ServiceStatusView.tsx`）
- 说明行改成：`const note = noteError ?? stoppedNote(exited ? service.exitCode : 0, exited && service.afterRunning === true);`
- **退出码那一行照旧**：仍是 `退出码 <真实码> · <时刻>。重启后会重新读取数据。`，退出码取 `service.exitCode`，不因为 `afterRunning` 改成别的字样；`data-exit-code` 元素、`<code>` 标签、h1「本机服务已停止」、图标、[重启服务] / [打开设置] 两个按钮、`document.title`、不设 `role=alert` 一律不变。
- 视图里不许另写那三句文案。

### 五、首启第 4 步：不变
- `firstRunHeadline`、`FirstRunView.tsx`、`firstRunModel.ts` 一个字不改；首启第 4 步的错误框与取值文字照旧（那里只有启动阶段的失败）。首启页**不读** `afterRunning`。

### 六、桩与夹具
- `desktop/web/src/shellpages/shellStub.ts` **一个字不改**（在 forbidden_paths 里）。桩在 `start`/`restart` 之后 1500ms 发出的 exited 一律不带 `afterRunning`（那是启动阶段的退出）；场景初始状态里的 exited 带不带键，由夹具的 `base` 决定。
- `desktop/web/src/mock/shellpages-scenarios.ts`：
  - **新场景 `crash-1`**：`base.service` 是 `{ kind: 'exited', repo: 'demo-repo', exitCode: 1, at: Date.parse('2026-10-18T09:41:07'), afterRunning: true }`；其余队列字段与 `crash` 一样（`repo`/`python`/`kit`/`transcriptDir` 都是「保存成功」模板）；`start` 是 `{ kind: 'exited', exitCode: 1 }`（**不带键**）——这样同一页先显示“意外退出”，点「重启服务」1500ms 之后换成“已经在另一个窗口里打开了”。
  - **`crash` 场景**：base 的 exited 补 `afterRunning: true`（语义上它就是跑起来之后崩的）；**退出码 3 与 `start: { kind: 'running' }` 一字不改**（T012 的 d02、d06 过渡探针靠它）。
  - 11 个旧场景名（`ready`、`checking`、`first-launch`、`not-git`、`no-agent`、`no-python`、`no-kit`、`exit-1`、`exit-2`、`crash`、`custom`）一个都不删、不改名；`SHELLPAGE_SCENARIO_NAMES` 仍是 `Object.keys(SHELLPAGE_SCENARIOS)`（新场景名自动进名单，`?shell=crash-1` 能打开）。
  - 文件头前 15 行的“示意”标注保留；路径继续用正斜杠。

### 七、页面测试（`desktop/web/tests/shellpages-service-status.test.tsx`）
- **既有用例一条不删、不改**；只在同一个文件里补用例。
- 补的用例至少覆盖：
  1. `crash-1`：h1 是「本机服务已停止」；`data-exit-code` 的文字是 `1`；退出码行仍是 `退出码 1 · hh:mm:ss。重启后会重新读取数据。`；说明是“本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。”；**说明不含**“这个仓库已经在另一个窗口里打开了。”；两个按钮照旧在；不设 `role=alert`。
  2. `exit-1`（启动阶段的退出 1）：说明仍是“这个仓库已经在另一个窗口里打开了。”（退出码 1 的另一种含义）。
  3. `crash-1` 点「重启服务」：1500ms 之后说明换成“这个仓库已经在另一个窗口里打开了。”；退出码仍是 `1`；**地址仍在 `#/service-status`**（没收到 running，不跳走）；按钮恢复可用。
- 写测试不许用 `skip`/`only`/`todo`；不抄一份业务逻辑进测试（断言页面真实渲染出来的文字）。

### 八、外壳 README（`desktop/shell/README.md`，只增改这两处）
1. **手工冒烟第 4 条**（`:70`）：在“并显示退出码”之后补半句，写明那一页的说明是“本机服务意外退出……”那一句（例如“并显示退出码，说明是「本机服务意外退出」那一句”）。既有字样（`T032 已落地，页面点得动`、`themis-shell://app/index.html#/service-status`、`重启服务` 等）一个不许删。
2. **状态说明处**（`:189` 那一段）：补一句 `afterRunning` 的约定——跑起来之后才退出的 exited 另带 `afterRunning: true`，启动阶段的退出不带这个键；服务状态页靠它分辨退出码 1 的两种含义。**同时**把该段里“`ServiceState` 被 `themisShell.ts` 钉死，页面负载多一个键就与类型不符”这句改成只说 `byShell` 不外传（例如“这个标志只在主进程，不进事件负载、不进 `getState().service`——`byShell` 不在 `ServiceState` 里”）：类型里现在多了这个可选键，原话会与实现自相矛盾。
- **`| **1** |` 那一行一个字不许动**（那一行现在没有“服务意外退出”，不许加；T035 `test_s05_readme` 盯着）。
- 既有 needle 一个不许删（T035 抽样：`T032`、`on('service-state'`、`桩数据`、`外壳页在本片就位`、`npm --prefix ../web run build`、`themis-shell://app/index.html#/first-run`、`desktop/web/dist`、`themisShell`；“服务状态页”在 README 里仍至少 2 处）。

### 九、既有断言：哪些跟着改、哪些不能动
- **本片合法改动（已由站主在 b71819d 按名字退役，不再是冻结项）**：`desktop/web/src/shellpages/themisShell.ts`、`desktop/web/src/mock/shellpages-scenarios.ts`、`desktop/web/tests/shellpages-service-status.test.tsx`。
- **不推翻，但要守住**：
  - T033 `PROBE_SERVICEFLOW` `:465`：握手失败的 exited 仍是 4 个键（`kind`/`repo`/`exitCode`/`at`）——靠“启动阶段不带键”守住；`desktop/shell/tests/serviceflow.test.js:118–121` 同理。
  - T033 `PROBE_SHELLAPI` `:779`：假控制器的状态原样透传（不受影响）；`:800`：事件负载里不许出现 `byShell`——新键叫 `afterRunning`，不叫 `byShell`，成立。
  - `desktop/shell/tests/shellshape.test.js:60–79` 与 `:145–148`：`ServiceState` 的四种状态名与字面量集合不变（类型体里不加注释）。
  - T012 `interface_problems`（十个成员、六个补丁键、字面量）、`test_d06`（三句只在 `exitCodes.ts`、视图从 `./exitCodes` 导入）、`test_d01_scenarios_fixture_is_ts_and_marked`（文件头“示意”、11 个旧场景名都在）、`test_d11_source_rules`（新代码照样守源码规则）、`test_gate_selfcheck_constants`。
  - T012 过渡用例（行为照旧成立）：`test_transitional_d01_scenario_fixture_values`、`d02_stub_fixture_values`（exit-1/exit-2 的启动阶段码、crash 退出码 3、重启之后 running）、`d06_service_status_content`（exit-1 是重启后的启动阶段退出 → “已经打开”；crash → “意外退出”）、`d06_service_status_restart_and_navigate`（推入的 exited 2 说明照旧是“文件不完整”）。
  - T035 `test_s05_readme`（见第八节）。
  - T032：p3/p4 探针照旧；**s09 名单里除已退役三项之外的每一项逐字不许动**（`shellStub.ts`、`ShellWindow.tsx`、`SettingsView.tsx`、`shellWindowRoute.ts`、`vite.config.ts`、`scripts/check-live-build.mjs`、`tests/shellpages-static.test.ts`、`tests/cleanup2-static.test.ts`、`tests/shellpages-stub.test.ts`、`shellpages-route.test.ts`、`shellpages-first-run.test.tsx`、`shellpages-settings.test.tsx`、`shellpages-app.test.tsx`、`shellpages-isolation.test.tsx`）；**整条 s09 断言不退役**，也不许改门禁文件。
  - 前端 `tests/page-app.test.tsx:91` 与 `tests/readonly2-app.test.tsx:106`（写入口个数，与服务状态无关）照旧。
- **规划列的假设 A1–A6（合同端已在新基线上逐条核实，全部成立）**：
  - A1：s09 里三项已按名字退役（`tests/test_gate_t032_baseline.py:117–118`），`UNTOUCHED_REL`（`:119–130`）里已不含它们，其余项仍在名单里 → 本片只按“其余项不得动、整条不退役”执行。
  - A2：`ts/packages/ui/src/server.ts:85–89` 先拿锁（被占回 `EXIT_ERROR`=1），`:195–198` 才写握手行 → 跑起来之后的退出码 1 不可能是“已经打开”。
  - A3：`main.js:195`、`shell-preload.js:12–14`、`shellapi.js:128–132` 与 `:297–299` 都原样转发状态对象，中间没有按字段挑拣的地方 → 新键原样到页面。
  - A4：除 T033 `:465`、`:779` 与 `desktop/shell/tests/serviceflow.test.js:118–121` 外，没有别的测试对 exited 做 deepEqual 或键集合比对（`desktop/web/tests` 下只有服务状态页那份文件断言退出码与说明）。
  - A5：没有测试断言 `SHELLPAGE_SCENARIO_NAMES` 恰好 11 个（T012 `:88` 的清单只要求这 11 个名字都在）；`shellContext.tsx:33` 认名单里的任何名字 → `?shell=crash-1` 能打开。
  - A6：`firstRunModel.ts:50–53` 的 `exitError` 只看码，`:137–138` 只用 `svc.exitCode` → 首启第 4 步不受新键影响。

### 十、兼容性与不变的东西
- `ServiceState` 的 exited 多一个**可选**键；不读它的旧代码照旧工作；`getState().service` 与事件负载一致（两者是同一个对象）。
- `window.themisShell` 的十个成员与名字不变；`info.byShell` 仍不外传。
- 服务状态页的 DOM 结构、类名、图标、按钮、title 一律不变；变的只有那一句说明的取法。
- 退出码语义、服务（`pi_dispatch.py ui`）的退出码约定、`ts/**` 一律不变。

## Steps
1. 读 `desktop/shell/src/serviceflow.js`、`desktop/web/src/shellpages/exitCodes.ts`、`ServiceStatusView.tsx`、`themisShell.ts`、`desktop/web/src/mock/shellpages-scenarios.ts`、`desktop/shell/README.md`，确认签名与上面「Repository facts」一致；不一致就停止并报告。
2. `desktop/shell/src/serviceflow.js`：只在 `moveTo` 里加 `afterRunning`（Behavior contract 一）。注释写清“进过 running 之后的退出才带这个键，启动阶段不带”。`info.byShell` 与其余语义一字不动。
3. `desktop/shell/tests/serviceflow.test.js`：在现有用例之外补用例（既有用例一条不改）：
   - 带 `afterRunning: true` 的：握手成功后服务自己退出（`tests/fixtures/fake-service-exit.js`，`FAKE_SERVICE_EXIT_CODE=1` 与缺省 3 都试）、跑起来之后 `stop()`（外壳自己停的也带 true）。
   - **不带这个键**的（断言 `"afterRunning" in state` 为假）：握手前退出（exit2）、坏握手、握手超时、spawn 失败（ENOENT）、starting 期间 abort。
   - 按 run 算：run1 跑起来之后退出（带键），run2 启动阶段失败（不带键）。
   - `info.byShell` 的取值照旧。
   - 照现有写法用轮询等子进程退出，不用固定等几百毫秒。
4. `desktop/web/src/shellpages/themisShell.ts`：exited 分支加 `afterRunning?: boolean`；说明写在类型上方的注释里，类型体里不写注释。
5. `desktop/web/src/shellpages/exitCodes.ts`：`stoppedNote(code: number, afterRunning = false)`；三句常量与 `firstRunHeadline` 一字不改；文件头第 2 行注释改成“两种含义已定”的说法。
6. `desktop/web/src/shellpages/ServiceStatusView.tsx`：只改说明那一行（传 `exited && service.afterRunning === true`）；退出码行与其余 DOM 一字不改。
7. `desktop/web/src/mock/shellpages-scenarios.ts`：加 `crash-1` 场景（base 是 exited 1 + `afterRunning: true`，`start` 是 exited 1）；`crash` 的 base 补 `afterRunning: true`（退出码 3 与 `start: running` 不动）；11 个旧场景名一个不删；文件头“示意”保留。
8. `desktop/web/tests/shellpages-service-status.test.tsx`：按 Behavior contract 七补三条用例；既有用例一条不删不改；不用 skip/only/todo。
9. `desktop/shell/README.md`：按 Behavior contract 八改那两处（含 `:189` 那句关于类型与负载的话）；`| **1** |` 那一行与既有 needle 一个不动。
10. 跑 Validation commands 里与改动相关的检查（V01–V04），记录命令与结果；写执行报告。遇到合同未定义的行为，停止并报告。
    - **两条硬规矩**：①遇到合同与既有测试（或门禁）冲突时，不要越界改范围外的文件，把冲突写进执行报告的 `contract_conflicts`（哪一处、合同要求什么、实际是什么），继续做范围内的部分；不许为了让检查变绿去改 `tests/test_gate_*`。②临时文件不许写到固定路径；照 AGENTS.md 用 `T=$(mktemp -d)`，用完在同一条命令里 `rm -rf "$T"`。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
- V01（必要）：`npm test` · cwd：desktop/shell · 超时：900s · 期望退出码：0 · 输出须匹配：`# pass \d+`、`# fail 0`
- V02（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`npm run build` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`built in`
- V04（必要）：`npm run check:contract` · cwd：desktop/web · 超时：300s · 期望退出码：0 · 输出须匹配：`契约检查：通过`
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t039_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`

说明：G01 指向的门禁文件由门禁端写好、内核做成基线提交，纯基线上还没有它（G01 在纯基线上跑不起来，属预期；照常跑 V01–V04 与 R01，并在执行报告里写明 G01 未跑）。R01 是 T001–T036 的门禁回归（基线应通过），其中若干门禁会自己跑前端流水线。V01–V04 需要 `desktop/web/node_modules`（由 Setup 的 `npm ci` 装好）与 Node 24 的 `node --test`（`desktop/shell` 的 `npm test` 已带 `--test-reporter=tap`，输出里有 `# pass`/`# fail 0`）。V03 的 `npm run build` 含 `tsc --noEmit`，新代码必须过严格类型检查。本片点名的门禁（T012、T025、T026、T028、T032、T033、T035）都在 R01 里，R01 太慢时可以先单独跑这七份。

## Definition of done
- D01：外壳在“进过 running 之后的退出”上带 `afterRunning: true`（服务自己退出、跑起来之后被 stop、onRunning 失败后的收服务），启动阶段的退出（握手失败、握手超时、spawn 失败、握手前退出、starting 期间 abort）**不带这个键**；键按 run 算；`info.byShell` 与其余状态机语义一字未变。证据：V01、G01；目的：退出码 1 的两种含义只能由外壳分清，页面不许自己猜；启动阶段多带一个键就会撞门禁里那条“启动失败的 exited 只认四个键”的 deepEqual。
- D02：服务状态页按 `afterRunning` 给说明：带键的一律是“本机服务意外退出。重启服务；反复出现时打开设置检查 Python 与 kit。”，退出码那一行照旧显示真实码（`退出码 <码> · <时刻>。重启后会重新读取数据。`）；不带键的照旧按码（1 已经打开、2 文件不完整、其他意外退出）；h1、图标、两个按钮、title、不设 `role=alert` 一律不变。证据：V02、V03、G01；目的：站主真窗口里结束服务进程后看到的是“意外退出”，不是让用户去找根本不存在的另一个窗口。
- D03：首启第 4 步不变：`firstRunHeadline`、`FirstRunView.tsx`、`firstRunModel.ts` 一个字未改，首启的错误框与取值照旧；那三句说明只放在 `exitCodes.ts`，视图与首启都从 `./exitCodes` 取。证据：V02、V04、G01、R01；目的：首启与服务状态页共用同一份文案，改动不许波及第 4 步。
- D04：退出码 1 的两种情形都有用例钉住：`crash-1` 初始说明是“意外退出”且不含“已经打开”，`exit-1` 仍是“已经打开”，`crash-1` 点「重启服务」1500ms 后说明换成“已经打开”、退出码仍是 1、地址仍在 `#/service-status`。证据：V02、V03、G01；目的：这正是站主要修的用户可见错误，两种情形都要有用例，免得下次又退回按码套话。
- D05：外壳 README 两处写清：冒烟第 4 条在“并显示退出码”之后补上“说明是意外退出那一句”；状态说明处写清 `afterRunning` 的约定（跑起来之后才退出的带 `true`、启动阶段不带），并把原先“页面负载多一个键就与类型不符”那句改成只说 `byShell` 不外传；`| **1** |` 那一行与既有 needle 一个未动。证据：V01、V04、G01、R01；目的：真窗口行为自动化测不到（键经 IPC 过桥），README 与站主的真窗口冒烟是唯一的验收凭据。
- D06：范围与纪律：只改 Scope 里允许的 8 个文件；门禁文件、桩 `shellStub.ts`、首启页三个文件、`main.js`、`shellapi.js`、`shell-preload.js`、夹具、锁文件、`ts/**`、`docs/**` 一个字未动；T032 的 s09 名单里除已退役三项之外的每一项逐字未动。证据：scope、review；目的：别的片的契约不许被这一片削弱。
- D07：没有删除、跳过或弱化既有测试：`desktop/shell/tests/serviceflow.test.js` 与 `desktop/web/tests/shellpages-service-status.test.tsx` 的既有用例一条不删不改（只补用例），不用 `skip`/`only`/`todo`。证据：V01、V02、scope、review；目的：本片的门禁靠既有用例兜底既有行为。
- D08：回归：G01 与 R01 全绿，既有门禁基准测试文件一条没删没改。证据：G01、R01；目的：别的片的契约不许被这一片削弱。

## Stop conditions
- 基线、接口或必要文件与「Repository facts」不符（例如 `serviceflow.js` 的 `moveTo` 形状、`exitCodes.ts` 的三句文案、`ServiceStatusView.tsx` 的说明行、门禁里那条“启动失败的 exited 只认四个键”的 deepEqual 与本基线不同）。
- 必须修改允许范围之外的文件才能继续。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如退出码 1 在带键与不带键两种情形下的说明与本契约不同）。
- G01 指向的门禁文件在基线上还不存在、导致 G01 跑不起来时：照常跑 V01–V04 与 R01，并在执行报告里写明 G01 未跑（不要自己写门禁文件）。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id 汇总，包括返工版本；本片已用掉 0 次）
- max_wall_seconds_per_attempt: 2400
- max_wall_seconds_total: 7200（本片已用掉 0 秒；给这一版留 2 次以上 attempt 与 2 倍以上单轮时限）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读代码与核对 20 分钟、实现与补测 45 分钟、跑 V01–V04 与点名门禁 20 分钟、写执行报告 5 分钟；单轮合计约 90 分钟（单轮上限 2400 秒 = 40 分钟，改动集中在 8 个文件、源码约 20 行、测试 60–90 行，留一次返工的余量）。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 下游须知
- 键名 `afterRunning`；TS 写成 `afterRunning?: boolean`；类型体里不写注释（说明放类型上方注释）。外壳只在 running→exited 时设 `true`；启动阶段的 exited **不带这个键**（不是 false）。
- 场景名 `crash-1`：base 是 exited 1 + `afterRunning: true`；`start` 是 exited 1（不带键）→ 点重启 1500ms 后说明换成“已经打开”。`crash` 的 base 补 `afterRunning: true`，退出码 3 与 `start: running` 不动。11 个旧场景名一个不删。
- 三句说明只放 `exitCodes.ts`；首启页（`firstRunHeadline`/`FirstRunView`/`firstRunModel`）一个字不改。
- 桩 `shellStub.ts` 一个字不改：它在 forbidden_paths 里，它 start/restart 之后发出的 exited 不带任何新键。
- README 两处：冒烟第 4 条在“并显示退出码”之后补半句；状态说明处补 `afterRunning` 约定，并把 `:189` 那句“页面负载多一个键就与类型不符”改成只说 `byShell` 不外传。`| **1** |` 那一行不许出现“服务意外退出”。
- 门禁端写本片门禁文件时可用的现成锚点：T033 `:465`/`:779`/`:800`；T012 `:88`/`:869–871`/`:934–958`/`:1721–1750`/`:2460–2495`；T035 `:430–471`；T032 `:117–130`（s09 其余项仍冻结）。
- R5：真 Electron 下这个键经 IPC 过桥，与现有的 `exitCode`、`at` 走同一条路，自动化测不到；合入后由站主在真窗口走 README 冒烟第 4 条确认，结论回给协调人。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261114T052826962285Z-owner-22c58e：

> 站主决定（T039 规划交付后的提问）：
>
> 1. T032 门禁的过渡断言 `test_transitional_s09_baseline_files_untouched` 已按名字退掉三项：`src/shellpages/themisShell.ts`、`src/mock/shellpages-scenarios.ts`、`tests/shellpages-service-status.test.tsx`（站主门禁准备提交 b71819d，已合入主分支；s09 在新末端上单跑通过）。名单其余各项照旧冻结，本片不动，包括 `shellStub.ts`、`shellpages-isolation`、stub 测试。整条不退役。
> 2. 基线已挪到合入门禁准备之后的新末端（`task rebase`），合同端照规划报告开工：页面测试照规划写进现有的 `shellpages-service-status.test.tsx`。
> 3. 规划报告的 A1–A6 由合同端逐条核实，写进合同。R1–R5 写成合同的约束：启动阶段的 exited 不带新键或保持原形，不要写成 false 让 T033 的 4 键 deepEqual 变红；ServiceState 的类型体里不写带引号或分号的注释；README 的新句子不写进 `| **1** |` 那一行；不改 crash 场景的退出码与起法。
> 4. 合入后站主在真 Electron 窗口里再走一遍 README 冒烟第 4 条，结果回给你（R5 只能靠这一步）。
