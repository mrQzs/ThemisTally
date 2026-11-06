# 复审记录：t026-desktop-shell-host attempt-001（七端信箱 hub）

- 合同：t026-desktop-shell-host.v1（base d2dda9d879ab9d1d84f1b972ddff4c1eba094999）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261106T075701900495Z-4157），终审报告如下

## 终审报告

# T026-7-audit-post 终审报告（audit-sonnet）

## 一、结论

**返工，退回执行端**（1 条阻塞项）。除该条外，D01–D17 的实现忠实度、范围合规、既有测试强度、门禁记录我都逐条核对过，没有别的必须改的问题。

## 二、我核了什么

- 材料：合同 `.agent/plans/t026-desktop-shell-host.v1.md`；候选补丁 `candidate.patch`（20 文件，A11/M9）；执行概述 `summary.md` 与 `executor-report.md`；内核独立跑的检查 `checks/01/{checks.json,G01.log,R01.log,V01.log}`；战前基线 `baseline/02/checks.json`；战后门禁 `T026-6-gate-post/report.md` 与证据（whitebox `.py`/`.log`、`mutations.json`、`spec.json`）；JEV 报告（`no_opinion auth_failed`）。
- 方法：逐文件读工作目录里的实际源码（`main.js`、`preload.js`、`src/{control,core,host,hostcheck,ipc,service,window}.js`、`tests/{control,core,host,hostcheck,ipc,preload,service,window}.test.js`、`tests/fixtures/fake-control-server.js`、`README.md`、`package.json`），对照合同 §一–§十二与 D01–D17；读补丁 diff 确认既有测试只增不改；核对门禁 31 条变异与 6 条「这条命令预期抓不住」的裁定；核对内核与门禁的记录。
- 本回合没有执行任何命令（审核端只读、无 bash）。下文「通过」的结论都来自：内核/门禁已跑出的记录 + 我对源码与断言的逐行阅读。

## 三、DoD 逐条核对（实现忠实度 + 证据）

| DoD | 实现是否忠实合同 | 证据 | 结论 |
|---|---|---|---|
| D01 preload 自包含、五键、只转交不校验 | ✓ `preload.js` 只 require electron 的 contextBridge/ipcRenderer，恰好一次 `exposeInMainWorld("themisHost")`，键恰好五个 | `tests/preload.test.js` 用 `vm.runInNewContext` 真跑源码（5 条，含「不许 require 相对路径/node: 模块」「exposeInMainWorld 只许一次」） | 通过 |
| D02 五通道、只用 handle、首行判来源、try/catch 回 internal、多余实参丢掉 | ✓ `src/ipc.js`：`HOST_CHANNELS` 冻结、首行同步 `senderAllowed`、catch 回 internal 不外传、按 `HOST_ARITY` 切实参 | `tests/ipc.test.js` 4 条 + 白盒 W05 | 通过 |
| D03 reauth 请求形状与五种 bad-response | ✓ `POST /control/bootstrap`、头 `x-themis-control`、无 Origin/Cookie、不写正文；信封四道校验（200 / ok===true / bootstrap 非空串 / origin 相同） | `tests/host.test.js` 6 条 bad-response + `tests/control.test.js` 3 条 + 白盒 W04 | 通过 |
| D04 限速 3 次/60 秒、失败也占名额、60000ms 放行 | ✓ `createRateLimiter` 滑动窗口，被拒不计数 | `tests/hostcheck.test.js` 两条 + `tests/host.test.js` 两条（注入时钟） | 通过 |
| D05 页面地址/作业号正反例、busy/同 job 复用、关窗后可再开、出处对齐 | ✓ `isSecretPageUrl`/`isJobId` 与 `secretentry.ts`/`jobs.ts` 字面量一致；`current` 占位在第一个 await 之前 | `tests/hostcheck.test.js` 的「出处对齐」用例 + `tests/host.test.js` 4 条 | 通过 |
| D06 凭据窗口十键无 preload、另取分区、origin 是页自己的、一个建窗工厂 | ✓ `main.js` 的 `guardedWindow` 是唯一 `new BrowserWindow`；凭据窗口用 `webPreferences(credentialPartition)`，分区由 `partitionName()` 另取 | `tests/window.test.js`（十键/十一键 deepEqual）+ 白盒 W01（`new BrowserWindow` 恰好一处） | 通过 |
| D07 关窗取消恰好一次、once、404/409/500/断连都吞掉 | ✓ `win.once("closed")` + `cancelJob` 的 `.then(()=>{},()=>{})` | `tests/host.test.js` 两条（含 404/409/500/destroy 四种） | 通过 |
| D08 先校验后确认框、cancelled、open-failed、bad-url 反例齐全 | ✓ `isExternalUrl` 不过就不弹框；`confirmExternal` 抛错兜底回 internal | `tests/host.test.js` 4 条 + 白盒 W04 | 通过 |
| D09 字面检查各类反例、bad-path、不碰显示函数 | ✓ `isRevealLiteralOk` 与合同逐条对应（空段、`.`/`..`、反斜杠、`:`、段尾点/空格、控制字符） | `tests/hostcheck.test.js` 正反各一条 + `tests/host.test.js` 一条 | 通过 |
| D10 realpath 比较、junction 正反、root 本身拒绝、`..foo` 不误判、只认文件或目录 | ✓ `isWithin` 与 `ts/packages/ui/src/static.ts:52-55` 写法逐字相同（`path.relative` 逐段比，不用前缀） | `tests/hostcheck.test.js` 注入版 + 真文件系统 junction 版两套 + `tests/host.test.js` 三条 | 通过 |
| D11 两条文案逐字、坏类型 bad-kind、额外参数不进文案 | ✓ `NOTIFY_TEXT` 用 `Map` 查 | `tests/hostcheck.test.js` + `tests/host.test.js` + 白盒 W03/W04 | 通过 |
| D12 令牌/nonce 不外泄（返回值、错误、**stdout、stderr**、`JSON.stringify(host)`） | 实现本身当前是干净的：`src/**` 与 `main.js` 里没有任何 `console.*`/`process.stdout`/`process.stderr` 写入（grep 全空），令牌只活在闭包里 | 返回值与错误：`tests/host.test.js` 多处 `JSON.stringify(r)` 不含令牌/nonce/地址 + `tests/ipc.test.js` 的 internal 用例；`JSON.stringify(host)` 一条。**stdout/stderr 这一路没有任何断言** | **返工** |
| D13 T025 三处（core 三条 timeout、trackWindow 四情形、stopService 两条） | ✓ `core.test.js` 只加了 `{ timeout: 5000 }`；`window.js` 的 `trackWindow` 先挂 closed 再 load；`service.js` 先查退出态再碰 stdin | `tests/window.test.js` 4 条、`tests/service.test.js` 2 条（真子进程带时限） | 通过 |
| D14 E1 快照与 T025 门禁兼容 | ✓ `webPreferences` 一字未改（十键无 preload），`mainWebPreferences` = 十键加 preload；`onServiceReady` 可选、在 `openWindow` 之前、收恰好三键、抛错一行 ERROR + 收服务 + 退 1；`openWindow` 入参不变 | `tests/core.test.js` 新增 3 条 + `tests/window.test.js` deepEqual；R01（T025 全部门禁）764 passed | 通过 |
| D15 静态禁令按文件收紧、只连 127.0.0.1 | ✓ `require('electron')` 只在 main.js/preload.js；`http.request` 只在 `src/control.js`；`shell.openExternal`/`showItemInFolder`/`dialog`/`Notification` 只在 main.js；无 `ipcMain.on`/`ipcRenderer.send` | G01（`tests/test_gate_t026_baseline.py`）14 passed | 通过 |
| D16 `scripts.test` 列全 12 份、README 要点齐、T025 要点未删 | ✓ 12 份 `*.test.js` 全列、tap 开关在前；README 保留 npm ci/npm start/--repo/--kit/--assets/退出码/install.js/node_modules/electron/冒烟/10 秒/30 秒，并新增五函数、reason 词表、窗口上限、限速、relPath 基准、通知文案、真 Electron 缺口、Ctrl+V | 白盒 W02 + README 关键词逐条 grep 命中 | 通过 |
| D17 范围合规、不弱化测试 | ✓ `scope.json` violations 为空、20 文件全在允许集合；`observations.json` 的 `assertion_lines_removed: 0`；无 skip/only/todo；令牌与 nonce 随机生成；临时目录用 `mkdtempSync` 并在 `test.after`/`t.after` 清掉 | 内核 scope 记录 + 补丁 diff | 通过 |

## 四、门禁端记录核对

**6 条「这条命令预期抓不住」（W2 = 执行端自己的 12 份 node 测试）逐条裁定：**

| 变异 | W2 真的测不到吗 | 谁抓住 | 裁定 |
|---|---|---|---|
| README 凭据窗口上限 1→2 | 真的测不到：执行端的 12 份测试没有一条读 README | W1 白盒 W02 的 `README_T026_NEEDLES` 含「凭据窗口同时最多 1 个」 | 声明诚实，不退回 |
| main.js 拿掉 `createHost` 的 require | 真的测不到：main.js 需要真 electron，测试从不加载它 | W1 白盒 W01 的 `MAIN_WIRING_IMPORTS` + `createHost(` 调用形态 | 声明诚实 |
| main.js 主窗口 prefs 换成十键 | 同上 | W1 白盒 W01 的 `prefs: mainWebPreferences(partition, preloadPath)` | 声明诚实 |
| main.js 凭据窗口 prefs 换成带 preload | 同上 | W1 白盒 W01 的 `prefs: webPreferences(credentialPartition)` | 声明诚实 |
| main.js `senderAllowed` 不校验 origin | 同上 | W1 白盒 W01 的 `return isServiceUrl(frame.url, serviceOrigin);` | 声明诚实 |
| hostcheck.js 去掉控制字符扫描 | 真的测不到：执行端 `isExternalUrl` 的反例只有空白/换行/`http:\\x`/协议类，**没有** DEL、NUL、0x1f | W1 白盒 W03 的 DEL/NUL/0x1f/串中空白四例 | 声明诚实 |

六条都由 W1 真抓住（`mutations.json` 里 `status: caught`、W1 `caught`），W2 的 missed 6 条与 `expect_missed` 完全对得上——门禁没有把「测不到」写成「测到了」。

**其余**：31 条变异覆盖执行端全部 11 个非测试文件（README 1、package.json 1、main.js 4、preload.js 1、control 3、core 1、host 5、hostcheck 8、ipc 2、service 2、window 3），caught 31 / missed 0；基线先行、文件逐字节恢复；白盒测试是真探针（`node --test` 子进程跑真实模块）+ 静态锚点，不是空心断言；`tests/**` 不变异是本仓库惯例（既有测试本身就是证据），我已逐条读过新测试，没有「为过测试而写的特判」「硬编码输入」或「空异常处理」。门禁端 `candidate_defects` 为空，与我核到的实现一致。

## 五、执行自述与内核线索对账

- **被管道掩码的退出码**：内核列的 5 条（`npm test 2>&1 | tail -n 15` 等）都是探索命令；三条验收命令在事件流里是 `set -o pipefail; …` 的写法，且内核自己独立重跑出 **G01 14 passed / R01 764 passed / V01 退出码 0、# tests 136 / # pass 136 / # fail 0**（`checks/01/checks.json` 的 `output_must_match` 三条都 matched）。执行报告的自述与内核记录一致，没有把推断当事实。
- **主工作区 `AGENT_LEARNINGS.md` 被改**（`observations.json` 的 `other_paths`）：不在候选补丁里（`candidate.stat.txt` 只有 20 个 `desktop/shell/**` 文件），未进候选。AGENTS.md 第 49 行要求「每次犯错后更新它」，执行端确实犯过一次（G01 曾因 `tests/preload.test.js` 注释里出现 `require('electron')` 字面串红过），看着是照仓库惯例做的。**不挡**，记一笔（见「不挡的意见」）。
- **`package.json` 的 `dependency_manifest_changed` 警告**：核对补丁，`package.json` 只改了 `scripts.test` 一行；`devDependencies` 仍是 `{"electron": "44.9.0"}`，`package-lock.json` 一个字节没动 → 误报。
- **越界**：无。`tests/test_gate_*`、`desktop/web/**`、`ts/**`、`scripts/**`、`docs/**`、`package-lock.json` 都不在 `candidate.stat.txt` 里。

## 六、阻塞项（1 条，只列会导致打回的）

1. **（归执行端）DoD D12 的 stdout/stderr 证据缺失，自述比证据宽。**
   合同 D12 原文：「控制令牌（测试里随机生成）不出现在五个函数任何路径的返回值、错误与 **stdout、stderr** 里，也不出现在 `JSON.stringify(createHost(...))` 里；bootstrap 的 nonce 与一次性页面的 32 位令牌同样不出现在返回值与输出里……**在全部输出里搜令牌，不靠人读**」——这条把「搜令牌」写成了证据方法。一审的下游须知也点名：「D12 的『stdout、stderr 不含令牌』门禁仍不覆盖：执行端必须在自己的 `host.test.js` 里捕获 stdout/stderr 并搜令牌与 nonce」。
   实际：候选里**没有任何一处捕获 stdout/stderr**。`grep -n "stdout|stderr|console\."` 扫 `desktop/shell/tests/` 只命中 `core.test.js` 里 T025 既有那条（它盯的是 `core.js` 的 `io`，不是五个宿主函数）与 `service.test.js` 的子进程流；`grep` 扫 `desktop/shell/src/` 只命中 `core.js` 的 `io` 默认值。`tests/host.test.js` 的 D12 断言只有三类：`JSON.stringify(r)` 不含令牌/nonce/地址、`JSON.stringify(host)` 不含令牌与 bootstrap 地址、假的 `loadURL` 拒绝消息带地址时也不外传。
   执行报告的 D12 行写「令牌与 bootstrap 地址（含一次性页面 32 位令牌）不在任何返回值、`JSON.stringify(host)` 与**输出**里」并标 `done`——「输出」这一路没有任何断言撑着，属自述宽于证据。
   补法（范围仍限 `desktop/shell` 的测试与报告）：在 `tests/host.test.js` 加一条用例，在五个函数的成功与各失败分支（reauth 的成功/bad-response/request-failed/load-failed，openSecretWindow 的 bad-args/busy/load-failed，openExternal 的 bad-url/cancelled/open-failed，reveal 的 bad-path，notify 的 bad-kind）期间接管 `process.stdout.write` 与 `process.stderr.write` 并收集内容，断言控制令牌、bootstrap nonce、一次性页面令牌都不在其中；并把执行报告的 D12 一行改回合同原文（返回值、错误、stdout、stderr、`JSON.stringify(host)` 五处都写）。既有断言不许删改。

## 七、不挡的意见（由站主决定做不做）

1. **（执行端）`src/ipc.js` 的 `senderAllowed(event)` 在 try/catch 之外**：`senderAllowed` 抛错时 invoke 处理器会把错误抛出去，与合同「处理器一律不抛错」有出入。当前 `main.js` 的 `senderAllowed` 不会抛（`isServiceUrl` 自己 catch 了 URL 解析失败，`event.senderFrame` 的 null/undefined 也判了），触发路径极窄。改成把首行判断挪进 try 即可（一行），但不是必须。
2. **（执行端/站主）主工作区 `AGENT_LEARNINGS.md` 在运行期间被改**（不在候选补丁内）。AGENTS.md 第 49 行要求犯错了更新它，所以这处改动不算越界，只是落在主工作区、没进候选；站主可自行决定保留与否。
3. **（门禁端）白盒 W01 的静态锚点偏脆**：`'prefs: mainWebPreferences(partition, preloadPath)'` 这类逐字匹配会让后续片对 `main.js` 的合法重构变红。门禁端自己已声明「重构 main.js/core.js 的后续片会红，属预期，改门禁即可」，故不退回；只是提醒下一片别为了迁就门禁去改实现。

## 八、下一轮

复审封板：下一轮只复核第六节那一条阻塞项与它带来的新增改动（测试文件 + 报告的 D12 一行），不重看已判过的 D01–D17。

Verdict: REVISE
