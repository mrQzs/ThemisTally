# 复审记录：t035-desktop-shell-service-b attempt-004（七端信箱 hub）

- 合同：t035-desktop-shell-service-b.v4（base b5cb4c5d54193974250a693d56100e356df0dee7）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 1；变异检查退出码 None
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261113T220448455471Z-0ec5），终审报告如下

## 终审报告

# T035-7-audit-post 报告（attempt-004 终审，审核端 audit-sonnet，2026-11-13T22:3xZ）

## 1. 结论

**返工；退回执行端。** 唯一阻塞项是上一轮封板的那一条（D06：`serviceGone` 守卫按进程级布尔判，意外退出后从不复位），本轮**零改动**，缺陷原样在候选里。门禁端举证的候选缺陷（白盒 w04 红）裁定**成立**，不是白盒误读合同。

v3 的 `max_attempts_total=4` 已用尽（attempt-004 是最后一次），但候选仍违反行为合同四与 DoD D06，不能判通过；处置路径需要站主拍板（见第 7 节与信件「需协调人决定」）。

## 2. 本轮候选是什么（先确认有没有新东西可审）

| 证据 | 值 |
|---|---|
| `.agent/runs/t035-desktop-shell-service-b/attempt-004/candidate.patch` | 0 字节（patch_sha256 = e3b0c442…b855，patch_bytes 0） |
| `changes.json` | `[]`；`candidate.stat.txt` 空 |
| `candidate.json` | tree `3fdd181acc6358e63c94a206a7314fad290b4ae0` = base `b5cb4c5d54193974250a693d56100e356df0dee7`，roundtrip 校验通过 |
| `scope.json` | A0 M0 D0 T0，violations 0，warnings 0，ok=true |
| `run.json` | 20:08:57Z → 20:39:24Z，exit 0，wall 1826.6s |

即 attempt-004 的候选树与 attempt-001 / 002 / 003 **逐字节相同**（都是 attempt-001 的那棵树）。按复审封板规则，本轮只复核上一轮的阻塞项与本轮新改动；**新改动为空**，所以没有别的可审内容。

内核 fresh 重跑的合同检查（`checks/01/checks.json`，run 1 fresh，candidate_tree = 3fdd181）：

| 检查 | 退出码 | 结果 |
|---|---|---|
| V01 `npm test`（desktop/shell） | 0 | `# pass \d+` 与 `# fail 0` 两个 output_must_match 都 matched=true，13.6s |
| G01 `pytest tests/test_gate_t035_baseline.py -q` | 0 | `\d+ passed` matched=true，2.4s |
| R01 34 个门禁文件 | 0 | `869 passed in 1098.76s`（R01.log），`\d+ passed` matched=true |

执行端自报的 R01 失败（exit 1，`tests/test_gate_t032_baseline.py::test_p1_pipeline_steps_pass` 里的 desktop/web vitest 偶发 `window.themisShell` 为 null）**在内核重跑里没有复现**（869 全过），且执行端自己复跑的三项（该文件单跑 14 passed、web 全量 985 passed、T032 门禁单跑 16 passed）都与「负载相关偶发」相符。**这一条不构成问题**。

## 3. 阻塞项复核（唯一一条，来自上一轮封板）

### D06：`serviceGone` 守卫必须按窗口/run 身份判 —— **未修复**

候选源码（`desktop/shell/main.js`，与 attempt-001/002/003 同一棵树）：

- `:68` `let serviceGone = false;`（进程级布尔，声明）
- `:175` `if (serviceGone) return;`（服务窗口 `tracked.closed` 收尾回调的第一个早退守卫）
- `:176-182` 收尾本体：`await flow.stop()` → `stop.exited && stop.code === 0` → `app.exit(0)`，否则 `ERROR: 服务没有以 0 正常退出` + `app.exit(1)`（**本体完整，缺陷只在守卫**）
- `:192` `serviceGone = true;`（意外退出分支分派前置位）
- `grep serviceGone` 全文**仅这 3 处**：`onRunning` 第二次起服务（新 `serviceWindow`、新 `tracked.closed` 处理）时**不复位**它。

触发路径（每一步都在候选源码里核对过，非推测）：

1. 首次启动页点「启动」→ 服务起来 → `onRunning` 建服务窗口 S1、外壳窗口 W1 被外壳关掉（`closedByShell = true` → `shellWin.close()`）。
2. 任务管理器结束服务进程 → `flow.subscribe` 判 `state.kind === "exited" && !info.byShell` → `serviceGone = true` → 此时 `shellWin` 指向已销毁的 W1 → 走分支 2：`openShellWindow(SHELL_STATUS_URL)` → 兑现后 `relay.clear()`、`S1.close()`。S1 的 closed 回调被 `:175` 守卫挡住 —— **这一步的意图是对的**。
3. 用户在服务状态页点「重启服务」→ `restartService` → `state.kind === "exited"` → `startService(state.repo)` → `flow.start` 开新 run → `onRunning` 建**新的**服务窗口 S2 并注册**新的** `tracked.closed` 收尾回调。此时 `serviceGone` 仍是 `true`。
4. 用户关掉 S2 → 收尾回调第一句 `if (serviceGone) return;` 直接返回：`flow.stop()` 不调用、退出码判定不执行、`app.exit(0)` 不调用。

结果：服务子进程留成孤儿（端口不释放），外壳不再走「收服务 → 以 0 退出」，只剩 Electron「最后一个窗口关掉就退出」的默认行为。

违反的条款：

- 行为合同四（外壳分支接线）末条：「**用户关服务窗口**：`flow.stop()`；服务以 0 退出 → `app.exit(0)`；否则往 stderr 写一行 `ERROR: 服务没有以 0 正常退出` 并 `app.exit(1)`。」—— 重启后的服务窗口属于「用户关服务窗口」，必须走这条。
- DoD D06：「用户关窗的收尾（`abort()`/`stop()`/退出码）保持不变。」
- README.md:70 冒烟第 4 条最后一步：「点页面上的『重启服务』→ 主窗口重新出现；关掉主窗口 → 服务随之结束、外壳以 0 退出。」与 README.md:185 的同一条描述 —— 这两处写的是**实现没有兑现的行为**（文档与实现不一致）。
- 合同四的措辞是「把服务窗口标成『服务那边已经收尾』」—— 标的是**那个窗口/那次服务实例**，不是进程级布尔；协调人 2026-11-13T18:14Z 的返工简报已明令「不得只加 `serviceGone = false`」。

修法要求（写进阻塞项）：

- 把「服务窗口已收尾」改成**按窗口/run 身份**计算，使重启后的服务窗口关掉时仍走 `flow.stop()` → `app.exit(0)`。
- **不得只加 `serviceGone = false`**：旧窗口 S1 迟到的 closed 回调会越过守卫，停掉新 run 的服务并 `app.exit(0)`（比现在更糟）。
- 稳妥做法：收尾回调里比对当前 `serviceWindow` 是不是自己那一个窗口（必要时再辅以按 run 的标志）。
- 执行端必须让 D06 的自述与实现一致（见第 5 节）。

## 4. 门禁端举证的候选缺陷裁定

**w04 红 = 候选缺陷成立**（不是白盒测试误读合同）→ 写进阻塞项、退回执行端；**不退回战后门禁**。

依据：

- 失败断言不是空心的：白盒先在候选上验证了收尾本体四条（`await flow.stop()`、`stop.exited && stop.code === 0`、`app.exit(0)`、`ERROR: 服务没有以 0 正常退出`、`app.exit(1)`）——全部通过；红在**守卫身份断言**：`guards` 里唯一条件是 `serviceGone`，`_identity_comparison` 判它没有变量/成员之间的 `===`/`!==` → `identity` 为空 → 失败消息引 D06、行为合同四原文与三处行号。断言指向的是候选代码的真实缺陷，不是测试写法问题。
- 第二层复位检查（若守卫仍读 `serviceGone`，必须在新窗口建立时复位）也会红（resets − decl = 0），与源码事实一致。
- 门禁端本轮的其他核对（w03 意外退出三分支形状、w01/w02/w05/w06、w07–w09）全绿，说明白盒整体没有系统性误判。

## 5. 执行报告的自述核对（发现）

| 自述 | 事实 | 结论 |
|---|---|---|
| D06 = done，note：「用户关外壳窗/服务窗的收尾（abort()/stop()/退出码 0/1 与 ERROR 行）照旧」 | `:175` 的守卫会把**重启后**那个服务窗口的收尾整段跳过 | **自述不实**：D06 的「收尾保持不变」没有兑现 |
| 「终审列的阻塞项为空」 | attempt-002 与 attempt-003 两次终审都退回了执行端，唯一阻塞项就是 D06 | **自述不实**（对执行端而言是简报没带；对报告而言是陈述与事实不符） |
| 「本轮未改任何代码：候选已实现合同各条」 | 与 candidate.patch 0 字节一致 | 属实 |

事件流佐证（执行端确实读过这段代码却判成合规）：

- `events.jsonl:1539/1541`：执行端 read 了 `tracked.closed.then(async () => { if (serviceGone) return; … })` 原文。
- `events.jsonl:1632` 的 reasoning：「in branch 1 of unexpected exit, contract says "把服务窗口标成『服务那边已经收尾』、关掉服务窗口" — serviceGone = true ✓ and relay.clear() ✓」——它把**进程级布尔**当成了「标那个窗口」，并只推演到「第二个服务实例又意外退出 → 分支 1」，没有走「重启服务 → 新服务窗口被用户关掉」这条路。

**流程根因（不是执行端能自行发现的）**：attempt-003 与 attempt-004 的 `plan.md` 的 Rework 段里，「### 终审列的阻塞项（原文）」槽位写的是过期的「（这个候选之后终审没有退回执行端：以合同与新的基准测试为准）」——这是 attempt-001 那轮通过时的内容。两次终审退回的 D06 阻塞项**从没进过执行端的返工简报**，所以执行端照着简报得出「阻塞项为空」的结论。这条要写进下游须知（重派时必须原文带上 D06 阻塞项），本轮不据此退回任何端。

## 6. 其余 DoD 的独立复核（结论：无需返工，不是新增阻塞项）

候选树与前几轮相同，以下是本轮自己读源码/门禁记录的复核结论，不是采信执行端自述：

- **D01** `src/serviceflow.js` 全文读过：准入（`starting`/`running` → `{ok:false, reason:"busy"}`）、新 run 重置（`stopping`/`aborting`/`child`/`repo`，`run += 1`）、旧 run 回调丢弃（`thisRun !== run`、`target === child`）、`byShell` 按 run（`stopping || aborting` 在 moveTo 时算）、同 run 内 `exited` 终态（`moveTo(next, newRun)` 的 `newRun !== true` 闸门）——逐条对上行为合同一。
- **D02** `src/shellapi.js:282-290`：`exited` → `startService(state.repo)`；`starting`/`running` → `{ok:true, value:null}`；`idle`/无控制器 → `{ok:false, reason:"no-previous"}`；未新增控制器方法 —— 对上行为合同二。
- **D03** `src/hostrelay.js`：纯模块不 require electron；五个方法原样转发；无 host 时回 `{ok:false, reason:"forbidden"}`；`senderAllowed` 抛错按 false；`use` 替换、`clear` 清空。`main.js` 外壳分支 `registerHostIpc(ipcMain, relay.host, relay.senderAllowed)` 恰好一处（服务分支那处是合同六要求保留的另一条路）。
- **D04/D05** `main.js`：`registerShellIpc` 一处、来源检查读当前 `shellWin`、选择框与确认框挂当前外壳窗口（不在就不带父窗口）、`openShellWindow` 每次新分区 + 该 session 一次 `protocol.handle`、`.protocol.handle(` 全文一处且前 160 字内有 `fromPartition`、`new BrowserWindow` 一处 —— 对上行为合同四/六。
- **D07** README：退出码表第 1 行、`restartService` 真行为与 reason 词表、意外退出回服务状态页、冒烟第 4 条（含 `T032`、`npm ci`、`npm --prefix ../web run build`、`node node_modules/electron/install.js`）都在；needle 一个没删（G01 的 README needle 门禁 10/10 全绿）。
- **D08/D09** `scope.json` 越界 0；既有 21 个测试文件一条不删（只改两处标题与 shellapi 占位断言），`package.json` 的 `scripts.test` 追加 `tests/hostrelay.test.js`，V01 304 passed，无 xfail/skip。

## 7. 预算与处置

- 合同 Budget：`max_attempts_total: 4`。attempt-001/002/003/004 已用尽 → **v3 内没有执行端返工机会**。
- 终审结论仍如实：候选违反行为合同四与 DoD D06，**不能判通过**；缺陷归属明确在执行端（`desktop/shell/main.js` 的守卫写法），合同端与门禁端（基准测试 G01、白盒 w04）都没有错，**不退回它们**。
- 需要站主拍板的取舍（没有合理默认）：(a) 出 v4 合同再派一次执行端修 D06；(b) 站主/协调人自己改 `desktop/shell/main.js` 这一处再走验收；(c) 把「按窗口/run 身份判的服务窗口收尾」拆成下一片、先按现状关 T035 —— 但那样 README 冒烟第 4 条与 README.md:185 写的是假行为，要一并决定是否改 README。
- 重派时的两点硬要求：返工简报必须原文带上 D06 阻塞项（本次的漏斗就是这里）；修完后门禁端要在新树上重算 w03/w04 的锚点与 main.js 的 M14–M19 变异锚点。

## 8. 证据

- 候选与执行证据：`.agent/runs/t035-desktop-shell-service-b/attempt-004/`（candidate.patch 0 字节、candidate.json、changes.json、scope.json、summary.md、executor-report.md、events.jsonl:1539/1541/1632、checks/01/checks.json、checks/01/R01.log）
- 候选源码：`desktop/shell/main.js:68/:175/:176-182/:192`（候选树 3fdd181）
- 门禁与白盒：`.agent/mailbox/tasks/T035-6-gate-post/report.md`、`evidence/whitebox-20261113T220442591370Z.log`
- JEV：`.agent/mailbox/tasks/T035-6j-jev/report.md`（no_opinion auth_failed，无意见）
- 合同：`.agent/plans/t035-desktop-shell-service-b.v3.md`（行为合同四、DoD D06/D07）

Verdict: REVISE
