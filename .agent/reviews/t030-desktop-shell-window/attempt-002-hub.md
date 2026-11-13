# 复审记录：t030-desktop-shell-window attempt-002（七端信箱 hub）

- 合同：t030-desktop-shell-window.v2（base a7cf95d2389e62503cc99800b775c85682b8d58c）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261112T232510499780Z-0e40），终审报告如下

## 终审报告

# T030-7-audit-post 终审报告（审核端 audit-sonnet）

2026-11-12 UTC。判断对象：候选树 `52faa1f1abb1f770303f0fedc5b656f1d73ab59b`；合同 `.agent/plans/t030-desktop-shell-window.v2.md`（v2，base_sha `a7cf95d2389…`）。

**结论: 通过**（不退回任何一端）。

## 0. 摘要

- 先读源码再读检查：候选的 14 个改动文件逐行核对，**忠实于合同 v2**，没有弱化测试、没有为过测试写的特判、没有悄悄扩大的范围。
- 改动范围：14 个文件全在合同 `allowed_modified_files` 内，依赖与锁文件未动，无 Electron 本体下载痕迹。
- 检查：内核在**固定候选树**上整跑 V01（283 pass / fail 0 / skipped 0）、G01（10 passed）、R01（789 passed in 1224.44s），三条 `output_must_match` 全部命中。
- 门禁：战前黑盒 10 条 + 战后白盒 8 条在候选上全绿；31 条变异 31 caught、0 missed、0 equivalent、8 个非测试文件每个都有变异。
- 我在一审里点的四个人工审阅面（D04 控制令牌、D06 关窗以 0 退出、D08 九通道表与退出码行、凭据窗导航判定）逐条核对通过。

## 1. 本回合核了什么

- 合同全文（Behavior contract §1–§9、Scope、Validation commands、DoD D01–D11、Stop conditions、站主决定原文）。
- 候选源码全文：`desktop/shell/main.js`、`shell-preload.js`、`src/launch.js`、`src/shellprotocol.js`、`src/shellipc.js`、`src/detect.js`、`package.json`、`README.md`，以及六份新增/修改的测试与夹具（`tests/launch.test.js`、`shellprotocol.test.js`、`shellipc.test.js`、`shellpreload.test.js`、`detect.test.js` 新增两例、`tests/fixtures/fake-late-output.js`）。
- 旁证源码（未被本片改动、用来核对接口）：`src/window.js`（`trackWindow`/`partitionName`/`mainWebPreferences`/`isServiceUrl`）、`src/shellapi.js`（`createShellApi` 十成员）、`src/settings.js`、`preload.js`、`src/ipc.js`。
- 补丁：`attempt-001/candidate.patch`（52 437 B，14 个文件，patch_roundtrip_verified=true）。**注意**：任务书给的 `attempt-002/candidate.patch` 是 0 字节、`attempt-002/changes.json` 是 `[]`——本轮执行端确实一行未改（摘要 `变更：A0 M0 D0 T0`），真正的改动集全在 attempt-001 的候选里。这与战后门禁的判断一致，不是缺陷。
- 内核检查记录：`attempt-002/checks/01/checks.json` 与 V01/G01/R01 三份日志。
- 战后门禁：`T030-6-gate-post/report.md`、`evidence/whitebox-…log`、`evidence/mutate-…/mutations.json`（31 条逐条结果）、两份 T030 门禁源码 `tests/test_gate_t030_baseline.py`（战前黑盒）与 `tests/test_gate_t030_whitebox.py`（战后白盒）。
- 执行报告：`attempt-001/executor-report.json`（含 4 条 interpretations）、`attempt-002/executor-report.md`、两份 `events-summary.json`。
- JEV（6j-jev）：`no_opinion auth_failed`，无意见。

本回合**没有运行命令**（审核端只读，且本轮工具集无 shell），**没有改任何文件**。

## 2. 候选实现逐文件核对（源码优先）

### 2.1 `main.js`（唯一允许改的入口文件）

- 协议特权：顶层（`app.whenReady()` 之前）唯一一处 `protocol.registerSchemesAsPrivileged([{ scheme: "themis-shell", privileges: { standard: true, secure: true } }])`，无 `supportFetchAPI`/`corsEnabled` ✓（合同 §6.1、站主事实 1/2）。
- 导航判定函数化：`guardedWindow({ partition, prefs, options, allowNavigation })`，`will-navigate` 里 `if (!allowNavigation(url)) event.preventDefault()`；`new BrowserWindow` 全文件恰好一处；权限请求/权限检查一律拒、`setWindowOpenHandler` 一律 deny 照旧 ✓。
- **三个调用点的导航判定都正确**（这是我在一审里点名的缺口）：服务主窗 `(url) => isServiceUrl(url, origin)`、凭据窗 `(url) => isServiceUrl(url, pageOrigin)`、外壳窗 `isShellPageUrl`。凭据窗**没有**被误套 `isShellPageUrl` ✓。
- 外壳分支七步逐条对上合同 §6.2–§6.8：产物根 `path.join(__dirname, "..", "web", "dist")` → 无 `index.html` 时 `process.stderr.write("ERROR: …")` 并 `app.exit(1)`；`partitionName()` 内存分区；**`session.fromPartition(partition).protocol.handle("themis-shell", …)`**（handler 真的挂在分区 session 的 protocol 上，不是模块级 `protocol`）；handler 用 `resolveShellAsset(root, request.url)` 的结果**自己构造** `new Response(resolved.body, { status, headers })`（无 `fetch(`/`net.fetch`）；`guardedWindow({ partition, prefs: mainWebPreferences(partition, path.join(__dirname, "shell-preload.js")), options: { title: "ThemisTally" }, allowNavigation: isShellPageUrl })`；`createShellApi({ store: createSettingsStore({ dir: app.getPath("userData") }), chooseDirectory, chooseFile, confirmExternal, openExternal, appVersion: app.getVersion() })`（`showOpenDialog` 取消或空 `filePaths` → `null`；`showMessageBox` 的 `buttons/defaultId/cancelId/message/detail/noLink` 与合同逐字相同，`response === 0` 算确认）；`registerShellIpc(ipcMain, api, (event) => shellSenderAllowed(event, win.webContents))`；`trackWindow(win, () => win.webContents.loadURL(SHELL_START_URL))` → `await tracked.closed;` → `app.exit(0)` ✓。
- 分支判定：`launchMode(argv) === "shell"` 走外壳页、`return`；服务分支的 `runShell({ argv, io, openWindow, onServiceReady, env })` 调用形状逐字未改（只把 `argv` 的声明上移，值不变）✓；`parseShellArgs` 未被调用、外壳分支不解析参数 ✓。
- 服务分支的行为语义未变：`guardedWindow` 的 `origin` 参数改成 `allowNavigation`（合同 §6 明写的要求），`isServiceUrl(url, origin)` 的判据一字未改 ✓。
- 静态禁令自查：`main.js` 里 `fetch(`/`net.request`/`persist:`/`shell: true`/写文件函数/`autoUpdater`/`crashReporter` 全部 0 命中（grep 复核）；`dialog`/`shell.openExternal`/`showItemInFolder`/`Notification` 只出现在 `main.js` ✓。

### 2.2 `shell-preload.js`（顶层，自包含）

- 只 `require("electron")`，无相对路径、无 `node:` 模块 ✓；`contextBridge.exposeInMainWorld` 恰好一次、名字 `themisShell` ✓；不暴露 `themisHost` ✓；全文无 `ipcRenderer.send`、无 `ipcRenderer.on` ✓。
- 十个成员：`getState/pickRepo/pickPython/pickKit/pickTranscriptDir/saveSettings/startService/restartService/openExternal/on`，与 `desktop/web/src/shellpages/themisShell.ts` 的 `interface ThemisShell` 一致（测试从 .ts 解析比对，不是另抄一份键表）✓。
- 信封拆分：`envelope.ok === true` → resolve `value`，否则 `throw new Error(envelope.reason)`（reason 只进 message，不挂别的属性）✓；`on` 同步返回退订函数、不发 IPC、不注册监听 ✓。

### 2.3 `src/launch.js`

纯函数：`--repo` 原样一项或 `--repo=` 开头 → `"service"`，否则 `"shell"`；非数组按空数组 → `"shell"`。`--repox`/`--repo-x`/`--REPO`/`--repo␠` 都不误判。**实现是通用判定，不是为测试写的特判** ✓（与合同 §1 一致）。

### 2.4 `src/shellprotocol.js`

- 常量逐字：`SHELL_SCHEME="themis-shell"`、`SHELL_HOST="app"`、`SHELL_START_URL="themis-shell://app/index.html#/first-run"` ✓。
- `isShellPageUrl`：`new URL` 接住抛错 → false；逐项比 `protocol`/`host`/`username`/`password`，**不比 origin** ✓；`app:8080`、`user@app`、`app\@evil` 全拒 ✓。
- `resolveShellAsset`：只解码一次，解码后仍含 `%` 拒（`%252e`）；解码后含 `\`/NUL/`:` 拒；空段/`.`/`..` 段拒；`fs.realpathSync(path.resolve(root, ...segments))` 必须**逐字等于** `path.join(realpath(root), ...segments)`（任一级的链接/junction 都拒）；再一道 `path.relative` 的「落在 root 内」；扩展名不在 MIME 表 → 404；只服务普通文件；200 的三个头（`Content-Type`/`Content-Security-Policy` 逐字取自 `headers.ts` 的 CSP/`X-Content-Type-Options: nosniff`）；一切拒绝回 404、`body` 空、`path` 为 null ✓。
- 安全性复核（我自己走的路径）：`path.resolve(root, ...segments)` 不会因绝对路径段而丢掉 root——绝对路径段必须含 `:`（Windows 盘符）或以 `/` 开头（会产生空段），两者都被前面的规则拒掉；`..` 段被拒 ✓。

### 2.5 `src/shellipc.js`

九个通道冻结、顺序固定；只用 `ipcMain.handle`；来源三条件（`event.sender === contents`、`senderFrame` 非空、`isShellPageUrl(frame.url)`）；来源不对 → `{ok:false,reason:"forbidden"}` 且不进 api；api 抛错（同步/异步）→ `{ok:false,reason:"internal"}` 且不外传消息；多余实参按 arity 截断 ✓（与合同 §3 一致）。

### 2.6 `src/detect.js`（合同 §5 只许改这两处）

补丁只有两个 hunk：`runProcess` 改成在 `close` 里 resolve（`exit` 不再 resolve；超时路仍立刻给结果并 kill；`error`/ENOENT 路照旧）；`detectKit` 的 `path` 改成 `path.resolve(kitDir, "scripts", "pi_dispatch.py")` ✓。别的没动 ✓。

### 2.7 `package.json`

只改 `scripts.test` 一行：新增四份测试文件被显式点名、`--test-reporter=tap` 仍在文件清单之前；`devDependencies` 仍 `{"electron": "44.9.0"}`；`package-lock.json` 未动 ✓。

### 2.8 `README.md`

新增「## 外壳页」一节（无参数启动行为与起步地址、产物位置与构建命令、协议与 privileges、拒绝规则、十个成员与 reject 约定、**九个通道的表**、**桩数据说明**、Electron 无 postinstall）；「退出码」表写明外壳分支找不到产物时以 **1** 退出；手工冒烟收敛为**三条**；开头句改成「外壳页在本片就位（界面接线在下一片）」。既有 needle 我逐条核对仍在：T025 的 9 个词 + 「10 秒」「30 秒」；T026 的 27 个词；T028 的 10 个词（`README_T026_NEEDLES`/`README_T028_NEEDLES` 我从门禁源码里读出来逐条比过）✓。

## 3. 补丁与范围核对

| 项 | 结论 |
|---|---|
| 改动文件 | 14 个，全部在 `allowed_modified_files` 内（8 个实现 + 6 个测试/夹具），**无 forbidden_paths、无桌面/网页/ts/scripts 改动** |
| 既有测试 | `tests/detect.test.js` 的 hunk 是纯追加（`@@ -318,3 +318,31 @@`），没有删除、跳过或弱化任何既有断言；其余既有测试文件一字未动 |
| 依赖 | `package.json` 只改 `scripts.test`；`package-lock.json` 未动；`devDependencies` 未变 |
| 构建产物 | 摘要里列的 `.pytest_cache/`、`desktop/web/dist/`、`desktop/web/node_modules/`、`ts/**/node_modules/` 都是 gitignored 的本地产物，**不在候选树**（`candidate.stat.txt` 只有 14 个文件） |
| Electron 本体 | 候选里没有 `desktop/shell/node_modules`，执行端报告也未跑 install.js；本片不跑真 Electron 的约束守住 ✓ |

## 4. 执行报告自述 vs 证据（逐条对上）

| 自述 | 证据 | 结论 |
|---|---|---|
| V01 `npm test` 283 pass | 内核固定候选上 V01：`# tests 283 / # pass 283 / # fail 0 / # skipped 0`，`# pass [1-9]\d*` 命中 | 相符 |
| G01 10 passed | 内核 G01：`10 passed in 1.55s`，`\d+ passed` 命中 | 相符 |
| t025/t026/t028 37 passed | 内核 R01 整跑含这三份，全绿 | 相符 |
| t021 隔离 15 passed、上一轮那条红是 `ts/**` 环境 flake | 内核 R01 整跑 **789 passed in 1224.44s**（含 t021），无失败无超时；站主已裁定该条为 flake | 相符（R01 的完整证据由内核补齐） |
| 完整 R01 本轮撞墙钟（约 93% 全绿） | 内核 `checks.json`：`R01` exit_code 0、wall 1224.776s、`all_required_passed: true`、`covers_all_required: true`、`modified_by_checks: false` | 相符（自述的局限已在 limitations 里如实写出） |
| 本轮未改任何文件 | `attempt-002/changes.json` = `[]`、`candidate.patch` 0 字节、摘要 `A0 M0 D0 T0` | 相符 |
| 只动允许集合内 14 个文件 | `changes.json`（attempt-001）14 项 + `candidate.stat.txt` | 相符 |

**内核摘要里的线索逐条对上（没有「自述不实」）**：

1. 「执行器自行宣布了 3 处解读」——`events-summary.json` 的 3 条 `interpretation_mentions` 全部出自同一句思考，内容是「D09 完整回归没跑完，我选 `completed`」的**状态判断**；执行报告的 `interpretations: []` 与 limitations 里对 R01 未跑完的如实披露是一致的，不是隐瞒。真正涉及实现取舍的解读记在 **attempt-001** 的 `executor-report.json`（4 条：MIME 扩展名大小写、`guardedWindow` 签名重构 vs「服务分支逐字不变」、开头句改写、冒烟收敛与 needle 保留），四条都给了合同原文、采取的做法与理由，且与合同不冲突 → **不判自述不实**。
2. 「掩盖退出码的 3 条命令」——逐条看过原文：一条 `grep … | head; sed -n`、一条 `grep -rn "ipcRenderer.send\|ipcMain.on" … || echo "(none found)"`、一条 `git status --short; git diff --stat`。都是**查看/检索**命令（内核自己也标了 `check: false`），不是测试或检查命令；执行端报告里自报的四条检查命令与内核独立复跑的结果一致。
3. 「新增被 Git 忽略的路径」——见第 3 节，都是本地产物，不在候选里。

## 5. 检查与门禁记录核对

- **内核固定候选复跑**（`checks.json`）：V01 exit 0 / `# pass` 命中；G01 exit 0 / `10 passed` 命中；R01 exit 0 / `789 passed` 命中（1224.44s < 合同 1800s 超时）。三条 `output_must_match` 在门禁机上都有成立的依据（V01 的 tap 汇总格式由 `scripts.test` 钉死的 `--test-reporter=tap` 决定；G01/R01 是 pytest `-q` 的汇总行，同一匹配在基线/历片合同里已用过）。
- **战前黑盒** `tests/test_gate_t030_baseline.py`：10 条（s01–s05 + p01–p05），候选上 10 passed。覆盖 D01–D11；无空心基线、无空心断言、无相对基线的改动范围断言、无共享页面全局否定（我一审已逐条核过）。
- **战后白盒** `tests/test_gate_t030_whitebox.py`：3 条静态 + 5 条 node --test 探针，候选上 **8 passed**（白盒日志与变异 baseline 日志都是 `8 passed`）。探针里 `require` 的是**真模块**（绝对路径指向 `desktop/shell`），期望值从 `themisShell.ts`/`headers.ts` 解析，不抄业务逻辑；junction、`%2e.js`、迟到输出都用真夹具。
- **31 条变异**：覆盖 8 个非测试文件，每个 ≥1 条（launch 3、shellprotocol 7、shellipc 5、shell-preload 6、detect 3、main 5、package.json 1、README 1），**31 caught / 0 missed / 0 skipped / 0 error / 0 equivalent / 0 未变异文件**；`files_left_modified: []`（变异后都恢复了）。关键的几条我逐条判断「是不是真的测不出来」：
  - M07「realpath 逐字相等那道被短路」被抓住——靠白盒里 **root 内部 junction** 的用例（消掉那道时「落在 root 内」双保险拦不住 root 内链接），这条变异确实可测 ✓；
  - M06「二次解码防护失效」被抓住——靠磁盘上真造一个叫 `%2e.js` 的文件，消掉那道时 `%252e` 请求会读到它回 200，确实可测 ✓；
  - M22「close 退回 exit」被抓住——靠真夹具（孙进程 detached+unref+stdio inherit），确实可测 ✓；
  - M10/M15/M21/M24 打在 **require/接线**上（fs、isShellPageUrl、electron、spawn），确实断的是接线而不是取值 ✓；
  - M28「去掉 `await tracked.closed`」被抓住 ✓。
  - 门禁端没有声明任何「等价变异」，也没有声明「某文件没法变异」——8 个非测试文件全覆盖，没有需要我另行裁定的空白 ✓。
- 门禁端自述的局限（官方 `pi_dispatch.py mutate --check-anchors` 在 worktree 跑不通、按内核同款归一逻辑复刻并逐条活体验证）不影响判定：内核在自己的环境跑 mutate 时以其结果为准；我核对的口径是「锚点逐字出现一次 + 逐条真施加真恢复 + 31/31 CAUGHT」，证据链完整。

## 6. DoD 逐条结论

| DoD | 结论 | 依据 |
|---|---|---|
| **D01** 启动分支 | 成立 | `src/launch.js` 实现通用判定；main.js 里判定在 `runShell` 之前；`parseShellArgs` 未动；V01 `launch.test.js` 6 例 + 白盒 wp01 8 例 + 变异 M01–M03 |
| **D02** 协议安全 | 成立 | `src/shellprotocol.js` 逐条对上合同 §2（含 realpath 逐字相等、双保险、MIME 表、CSP 逐字）；V01 `shellprotocol.test.js`（9 种扩展名 + 14 条 404 + junction + 越界性质断言）+ 白盒 wp02（%zz、%252e 有牙齿、root 内 junction、空段、root 不存在）+ 变异 M04–M10 |
| **D03** 外壳 IPC | 成立 | `src/shellipc.js` 九通道冻结/只用 handle/三条件/forbidden-internal 不带消息/多余实参截断；V01 `shellipc.test.js` + 白盒 wp03（缺方法、抛非 Error、异步 reject、实参不足、端口/反斜杠 frame）+ 变异 M11–M15 |
| **D04** 外壳 preload | 成立 | `shell-preload.js` 只 require electron、自包含、恰好一次 expose、十个成员与 .ts 一致、reject 带 reason、`on` 不发 IPC；服务页 `preload.js` 未动（仍只暴露 `themisHost`）；**「渲染进程拿不到控制令牌」人工核对通过**（见 §7.1） |
| **D05** detect 两处 | 成立 | 补丁只两个 hunk；V01 新两例（相对 kitPath → 绝对；迟到输出夹具）+ 白盒 wp05（repo 分支也绝对、迟到输出、ENOENT）+ 变异 M22–M24 |
| **D06** main.js 接线 | 成立 | 协议特权一处且 whenReady 前、privileges 只 standard/secure、handler 在分区 session、BrowserWindow 一处、外壳窗关退 0、服务分支编排不变；G01 + T025/T026 + 白盒 w01 + 变异 M25–M29；**「关窗以 0 退出」人工核对通过**（见 §7.2） |
| **D07** 静态禁令 | 成立 | G01 s03（含顶层 `shell-preload.js` 纳入扫描）+ 我自己 grep 复核 main.js/src/** 零命中；`dialog` 等四词只在 main.js |
| **D08** README | 成立 | 「## 外壳页」一节齐全：协议、拒绝规则、十个成员、**九通道表**、**桩数据说明**、三条冒烟、**退出码 1**；既有 needle 逐条在位；**人工 review 面通过**（见 §7.3） |
| **D09** 全量回归 | 成立 | 内核固定候选整跑 R01 = 789 passed（无失败、无超时）；V01 283 pass / 0 fail / 0 skipped；既有测试一条没删没改名没弱化 |
| **D10** 范围与依赖 | 成立 | 14 文件全在允许集合；`package-lock.json` 与 `devDependencies` 未动；候选里无 Electron 本体 |
| **D11** 不弱化测试 | 成立 | `detect.test.js` 纯追加；其余既有测试未动；V01 `# skipped 0` |

## 7. 人工审阅面（一审里我点的四处，逐条核对）

### 7.1 D04「渲染进程拿不到控制令牌」
- 外壳分支**根本不起服务**：`runShellPage()` 里没有 `runShell`、没有 `createHost`、没有 `onServiceReady`，控制令牌在服务分支才产生（`createHost({ origin, control, repo })`），外壳分支拿不到也传不出 ✓。
- 外壳 preload 只暴露 `themisShell` 十个成员，无令牌相关成员 ✓；服务页 `preload.js` 未被本片改动，仍只暴露 `themisHost` ✓。
- `registerShellIpc` 只转交 `createShellApi` 的九个方法，api 不接触令牌 ✓。**结论：成立。**

### 7.2 D06「外壳窗口关掉以 0 退出」
- 代码路径：`trackWindow(win, load)` → 内部先挂 `closed` 的 Promise（`win.on("closed")` 里 resolve）→ `await load()` → 返回 `{ closed, close }`；外壳分支 `const tracked = await trackWindow(...); await tracked.closed; app.exit(0);`。
- `trackWindow` 的 `closed` 确实是窗口 `closed` 事件的 Promise（`src/window.js` 逐行核过），不是 undefined → `await` 不会立刻穿过去 ✓。
- `app.exit(0)` 在 `await tracked.closed` 之后（源码顺序 + 白盒 w01 的顺序断言 + 变异 M28 被抓住，三重证据）✓。**结论：成立（真窗口行为仍属 README 手工冒烟面，属既定局限）。**

### 7.3 D08「九个通道的表」与「退出码表补一行」
- 九通道表：README 的表里九条通道与 `SHELL_CHANNELS` 的九条逐字一致、方法名与实参个数与合同 §3 一致 ✓。
- 退出码 1：README「退出码」表的 **1** 行写明「……、外壳分支找不到产物 index.html」；代码里 `ERROR: ` 一行 + `app.exit(1)`（白盒 w01 断言 `ERROR: ` 在 `app.exit(1);` 之前，变异 M26 被抓住）✓。实现是**并进既有的 1 行**而不是字面「新增一行」（见 §8 第 1 条，不挡）。**结论：成立。**

### 7.4 门禁与合同的越界用例口径
- 门禁（战前 p02、战后 wp02、合同 §2）对「越界」的写法一致：**回 200 的 path 必须落在 `realpath(root)` 之内**（性质断言），`%252e` 单独钉 404；我核了执行端 `shellprotocol.test.js` 与白盒探针，写法同款，没有把 `..` 写成「必 404」✓。

## 8. 不挡的意见（建议类，不进阻塞项）

1. **README 的退出码表是「并入第 1 行」而不是合同 §8 字面的「补一行」**：语义等价（同一个退出码 1，T025/T028 的 needle 与白盒 w03 的「外壳分支找不到产物」都覆盖），但字面上与 §8 有一字之差。若站主希望严格照字面（表里出现两行 `1`），下一片或 README 微调时可改；本片不构成打回。
2. **外壳分支的失败路径没有兜底**：`runShellPage()` 里若 `loadURL` 抛错且窗口未被销毁，`trackWindow` 会把错误抛回，`await runShellPage()` 在 `app.whenReady().then(...)` 里没人接 → 进程会停在「无窗口、也不退出」的状态。当前实现里 `resolveShellAsset` 对一切拒绝都回 404（不抛），触发概率很低；合同也没定义这条失败路径。下一片接真行为（起服务、事件）时建议顺手加 catch 与退出码。
3. **Windows 上请求路径大小写**：`realpath` 逐字比较使「大小写与磁盘不符」的请求回 404（如请求 `Index.html` 而文件是 `index.html`）。合同未规定，无安全影响，仅是行为取舍。
4. **战后白盒对 `main.js` 的文本断言写得较具体**（`launchMode(argv) === "shell"`、`session.fromPartition(partition).protocol.handle("themis-shell"`、`await tracked.closed;`、`ERROR: `、`shellSenderAllowed(event, win.webContents)`、`if (!allowNavigation(url))`、`new BrowserWindow` 恰好一处）：下一片若重构外壳分支，必须同步改这两份 T030 门禁，否则会红（白盒自己不是相对基线的断言，集成本候选后仍全绿）。
5. **两份 T030 门禁不在合同 R01 的命令清单里**（R01 列的是 t001–t026 + t028）。要不要把 `tests/test_gate_t030_*.py` 带进下一片的 R01，由下一份合同定。
6. `src/shellapi.js:114` 的相对 kit 路径仍留（站主已裁定本片不改），外壳页 `getState` 的 kit 路径要等下一片。

## 9. 结论

- 实现忠实于合同 v2：九个 DoD 全部成立，四个人工审阅面逐条核对通过。
- 范围干净：14 个允许文件，既有测试无删除/弱化，依赖与锁文件未动。
- 检查与门禁：内核固定候选上 V01/G01/R01 全绿；白盒 8 条 + 31 条变异证据链完整、无等价变异、无未覆盖文件；JEV 无意见。
- 无阻塞项；不退回任何一端。

**结论: 通过**

Verdict: PASS
