# 复审记录：t025-desktop-shell attempt-003（七端信箱 hub）

- 合同：t025-desktop-shell.v3（base 65f3a77e8f07d9e98e1008078ac17b8a67fc0801）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261101T095031551840Z-b5f5），终审报告如下

## 终审报告

# T025-7-audit-post 终审报告（attempt-003，audit-sonnet）

## 0. 结论

**通过。** 上一轮的三条阻塞项 B1/B2/B3 全部落实，我逐行读过候选源码与新增的 6 条用例；候选的范围、DoD、退出码与不变量符合合同 v3；没有越界、没有弱化测试、没有为过测试写的特判。门禁记录（52 条变异全 caught，没有 equivalent / expect_missed / unmutated 声明）与内核四条独立检查（V01 65/65、G01 11 passed、R01 753 passed、V02 added 13 packages）我都逐条核对过。

本回合只读：没有改任何文件，也没有执行命令（本回合只有读文件与搜索工具）。

---

## 1. 上一轮三条阻塞项逐条复核（复审封板）

### B1（main.js 的窗口关闭事件注册太晚）——已解决

- 现在的代码：`desktop/shell/main.js:26-31` 里 `const closed = new Promise((resolve) => { win.on("closed", resolve); });` 在 `await contents.loadURL(bootstrap)` **之前**建好并注册；loadURL 的 reject 被 try/catch 接住，只有 `!win.isDestroyed()` 时才把错误抛出去（窗口确已被销毁 → 视为「窗口已关」，交给 core 走正常收尾）；`close()` 也加了 `isDestroyed()` 守卫（main.js:42）。
- 触发路径闭合：用户在页面加载完成前关窗 → 'closed' 一定被接到（监听器在建窗后同步挂上，早于任何用户交互）→ core 走「窗口关闭」分支 → stopService 关 stdin → 服务以 0 退出 → 退出码 0。不再出现孤儿服务占着 `.agent/.ui.lock` 与端口，也不再出现未捕获拒绝（stderr 没有 `ERROR: ` 行、退出码不是 0/1）。
- openWindow 失败不再裸奔：`core.js:96-107` 接住 → 一行 `ERROR: 打开窗口失败` → `stopService` 收干净子进程 → 退出码 1。
- 用例：`core.test.js` 新增「窗口在 openWindow 返回前就关了」（closed 在 openWindow 返回前兑现 → 仍走关窗收尾、退出码 0、`stdinEnded` 为真、输出不含令牌与 nonce）与「openWindow 失败：一行 ERROR、收干净子进程、退出码 1」（断言 stderr 里以 `ERROR: ` 开头的行**恰好 1 行**、`stdinEnded` 为真、输出里不含 nonce 也不含 `/bootstrap/`）。
- 非空心核对：这两条对 pre-fix 的 core.js 确实是红的——pre-fix 没有 openWindow 的 catch 分支，openWindow 抛出会让 runShell 的 promise 直接 reject，退出码断言（1）与「一行 ERROR」断言都不成立。

### B2（core.js 的服务退出事件注册太晚）——已解决

- `core.js:87` `const serviceExit = watchServiceExit(child)` 在 `await openWindow(...)`（core.js:97）**之前**；
- `watchServiceExit`（core.js:23-38）先 `readExit(child)` 查 `child.exitCode` / `child.signalCode`（core.js:11-21）：已退出就直接按「服务意外退出」处理（core.js:89-93：一行带退出码的 ERROR、退出码 1；此刻没有窗口可关），没退出才 `child.on("exit", …)`；
- 开窗口期间服务死掉：`core.js:98-104` 在 openWindow 的 catch 里再查一次退出态 → 报「服务意外退出（退出码 N）」而不是「打开窗口失败」；子进程已死，无需再收；
- 竞态分支：`core.js:110-114` 的 `Promise.race` 现在拿 `serviceExit.exited`（带退出码与信号名），服务先退 → 一行 `ERROR: 服务意外退出（退出码 N）` + `win.close()` + 退出码 1（core.js:115-122）；
- 文案统一走 `exitLabel`（core.js:40-45）：退出码是数字就写数字，否则写信号名，都没有写「未知」。
- 用例三条：
  - 「服务在握手后、开窗口完成前以 3 退出」：openWindow 真等 40ms，fake spawn 在握手行写完后 setImmediate 以 3 退出；断言退出码 1、stderr 含「服务意外退出（退出码 3）」、`close` 被调。**我独立推演过它对 pre-fix 的 core.js 是红的**：pre-fix 在 `await openWindow(...)` 之后才 `child.on("exit")`，退出事件在等待期间已经发过，race 永远不兑现 → 用例 5 秒超时变红（执行端换回基线实测同样是「旧实现挂起，5 秒用例超时失败」）。
  - 「服务在开窗口之前就已经没了」：握手与退出都在 spawn 里同步发生 → 断言一行「服务意外退出（退出码 5）」、**不开窗口**、退出码 1。
  - 「开窗口期间服务退出导致 openWindow 失败」：报的是「服务意外退出（退出码 4）」而不是「打开窗口失败」，退出码 1。
- 与合同的对应：D09「服务意外退出 → 1、stderr 里有服务的退出码、窗口被关掉」三条现在都有用例；D07「关窗口必须收干净服务」在关窗分支上由 stopService 保证，失败分支上也补了收干净。

### B3（io 没有兜底）——已解决

- `core.js:48-52` 解构默认值 `io = { stdout: process.stdout, stderr: process.stderr }`：不传 io 时「参数错」这条路照合同写一行 `ERROR: …` 到 process.stderr 并返回 2，不再抛 TypeError。
- 用例：「不传 io：参数错时用默认的 process.stderr 写一行 ERROR，退出码 2」——临时接管 `process.stderr.write`（`t.after` 还原），断言退出码 2、不开窗口、不起服务、输出里有 `ERROR: `。

三条全部落实，本轮没有需要执行端再改的地方。

---

## 2. 候选与合同的逐条核对

**范围**：`scope.json` 记 M3 / A0 / D0 / T0、violations 0、warnings 0 —— 只动了 `desktop/shell/main.js`、`desktop/shell/src/core.js`、`desktop/shell/tests/core.test.js`，三个都在合同 `allowed_modified_files` 里；`forbidden_paths`（`tests/**`、`desktop/web/**`、`ts/**`、`scripts/**`、`docs/**`、`.agent/**`）一个都没碰；`candidate.patch` 里也只有这三个文件。本轮没有顺手改 `service.js` / `args.js` / `python.js` / `handshake.js` / `window.js` / `package.json` / 锁文件 / README，范围没有悄悄扩大。

**DoD**：D01–D14 里，上一轮已逐条核对过的部分不受本轮改动影响（本轮只动了上面三个文件里的编排与 main.js 接线，包、锁文件、README、其余五个模块一字未改），新补的三条路径由 6 条新用例覆盖；内核 V01 独立跑出 `# tests 65 / # pass 65 / # fail 0`，其中第 18–23 号就是本轮的 6 条新用例。

**静态禁令**：新增代码里没有 `persist:`、`shell: true`、fs 写函数、`fetch` / `net.request` / `http(s).request` / `autoUpdater` / `crashReporter` / `openExternal`；`require('electron')` 仍只在 `main.js:3`。G01 的 S03/S04 扫描通过。

**退出码三条路互不串**：0（关窗口、服务以 0 退出）、1（找不到 Python / 握手失败或超时 / 服务意外退出 / 关窗口后服务没有以 0 正常退出 / 打开窗口失败）、2（命令行参数错）。每种失败都是「一行 `ERROR: ` 开头 → 结束子进程 → 约定的退出码」。

**秘密不外泄**：新增的「打开窗口失败」刻意**不回显**底层 `err.message`（Electron 的 loadURL 拒绝消息形如 `ERR_FAILED (-2) loading http://127.0.0.1:8123/bootstrap/<nonce>`，回显即泄 nonce，对应 D10 的红线）；用例专门断言输出里不含 NONCE 也不含 `/bootstrap/`。`openWindow` 的入参仍只有 `{ bootstrap, origin }`。

---

## 3. 新增用例的质量（非空心）

| 新用例 | 断言了什么 | 杀的是哪个 pre-fix 行为 |
|---|---|---|
| 窗口在 openWindow 返回前就关了 | 退出码 0、`stdinEnded` 为真、exit 0、`close` 未被调、输出无令牌/nonce | core 对「closed 先兑现」的收尾（同时钉住 core 侧不再依赖 loadURL 的次序） |
| 服务在握手后、开窗口完成前以 3 退出 | 退出码 1、stderr 含「服务意外退出（退出码 3）」、`close` 被调 | B2：退出事件注册在 openWindow 之后（对旧实现是挂起→超时红） |
| 服务在开窗口之前就已经没了 | 一行「服务意外退出（退出码 5）」、`w.calls.length === 0`、退出码 1 | B2 的「注册后立刻查退出态」分支 |
| openWindow 失败 | `ERROR: ` 行恰好 1 行、含「打开窗口失败」、`stdinEnded` 为真、exit 0、退出码 1、输出无 nonce 与 `/bootstrap/` | B1 的「openWindow 失败也要走 ERROR + 收干净 + 约定退出码」 |
| 开窗口期间服务退出导致 openWindow 失败 | 报「服务意外退出（退出码 4）」、退出码 1、输出无 nonce | B2 的「开窗期间死掉优先报服务意外退出」 |
| 不传 io | 退出码 2、不开窗口、不起服务、process.stderr 上有 `ERROR: ` | B3：io 无默认值 → TypeError |

断言都是实打实的（不是「文件存在」这类空心断言，也没有把业务逻辑抄进测试）；`fakeSpawn` 只多记了 `state.stdinEnded` / `state.exit` 与一个 `exitAfterHandshake` 分支，既有的 `spawn` 形状断言一行没放松。

---

## 4. 门禁记录与内核检查的裁定

**门禁（6-gate-post）**：白盒 8 条 pytest 全绿；`mutations.json` 52 条逐条 `status=caught`、`count_expected=1` / `count_found=1`（锚点逐字命中，可信）；`equivalent` / `expect_missed` / `unmutated` 三项**都没有声明** → 本轮没有需要我逐条裁定的等价变异或不可变异文件；`candidate_defects` 为空。

**但门禁的覆盖面有一处缺口（记为观察项 + 下游须知，不作为打回理由）**：门禁的白盒（w08 的 6 条 core 探针）与 52 条变异**一条都没碰到** attempt-003 新增的四条路径（服务在开窗口期间退出、开窗前服务已死、openWindow 失败、不传 io 的默认 stderr）；锁定的基准门禁 `tests/test_gate_t025_baseline.py` 的 p06（PROBE_CORE，5 条用例）同样没覆盖。门禁报告里「现有断言继续覆盖核心编排」这句对新代码说得偏松。

不把它升级为阻塞项的理由：这四条路径目前由候选自带的 `desktop/shell/tests/core.test.js` 覆盖，而内核已在冻结候选上独立跑过 V01（65/65）；合同 D14 的变异对照表也把 M12/M13 的「杀它的用例」指定为 `core.test.js`。本轮没有出现「门禁声明等价却真的测不出来」或「门禁说没法变异其实该测」的情形。

**内核 checks/01**：`tree_before == tree_after == 6d9ccf97`、`modified_by_checks=false`、`candidate_files_modified=[]`、`unexpected_files_by_checks=[]`；G01 11 passed（3.40s）、R01 753 passed（1028s）、V01 65/65、V02 `added 13 packages`。检查没有改动候选。

**执行概述里的「可疑命令」**：四条都是「临时把基线版 `src/core.js` 换进去跑测试、同一条命令里 `cp` 回来并 `rm -f` 备份」的变异反测；备份 `src/core.js.orig` 在工作目录内且同命令删除，收尾 `git status` 只有三个改动文件 → 符合合同 D14（临时文件不写固定路径、用完即删）。管道掩盖退出码的 5 条命令都在探索阶段，最终判定用的是内核独立实跑的 `checks.json`。

---

## 5. JEV 两条「需关注」的裁定

- **「自行解读合同 p=0.93」——不成立为缺陷。** 执行端本轮的四条解读都写进了 `executor-report.md` 的 `interpretations`（openWindow 失败的固定文案不回显底层消息、服务在开窗前已死就不开窗口、开窗期间服务退出优先报「服务意外退出」、io 用解构默认值），每条都给了理由。四条都是合同没写死、且有安全默认的路径（判据说的是「挑了一种读法却没申报为冲突或提问」，本轮已申报）。
- **「自述完成而无证据 p=0.93」——不成立。** D01–D14 每条都引用了 `self_checks` 里真实存在的检查 id（V01/V02/G01/R01），内核又在冻结候选上独立实跑了同四条（退出码、日志字节数与 sha256 都在 `checks/01/` 里）。
- **弱化测试 p=0.04 / 超出范围 p=0.06** 与我的核对一致（补丁只有三个文件；`core.test.js` 只增不减）。

---

## 6. 不挡的意见（写进 report，不进阻塞项）

1. **三条新用例没设 timeout**：可能挂住的三条里，「服务在握手后、开窗口完成前以 3 退出」与「开窗口期间服务退出导致 openWindow 失败」有 `{ timeout: 5000 }`，而「服务在开窗口之前就已经没了」「窗口在 openWindow 返回前就关了」「不传 io」没有。若将来实现回退到 pre-fix（前两条会等一个永远不兑现的 race），`npm test` 会**挂住**而不是变红。改法：给可能挂住的用例补 `{ timeout: 5000 }`，三行以内。
2. **main.js 的兜底只认 `win.isDestroyed()`**：若 loadURL 的 reject 比窗口销毁更早到达（Electron 里 `CloseImmediately` 先 `NotifyWindowClosed`、拒绝再异步投递，所以大概率 `isDestroyed()` 已为真），外壳会报「打开窗口失败」并以 1 退出，而不是按「关窗口」以 0 退出。服务仍会被 stopService 收干净，不留孤儿，伤害限于退出码与文案。更稳的做法是 catch 里也看一眼 closed 是否已兑现（约 3 行）。概率低，不挡。
3. **`stopService` 对已死的子进程 `child.stdin.end()`**：Node 上对已销毁的 stdin 结束可能触发 EPIPE / ERR_STREAM_DESTROYED 的 'error' 事件；这条要撞上「关窗口与服务退出几乎同时发生」的巧合才有，pre-fix 就有，本轮没有让它更容易发生（新的 `already` 分支反而多避开了一种）。要稳可在 stopService 里先看 `child.exitCode`，或给 stdin 挂一个吞错的 error 监听（约 2 行）。
4. 门禁报告里「现有断言继续覆盖核心编排」这句对新代码说得偏松（见第 4 节），不影响结论，但下一轮门禁要补。

---

## 7. 证据

- 合同：`.agent/plans/t025-desktop-shell.v3.md`
- 候选：`desktop/shell/main.js`、`desktop/shell/src/core.js`、`desktop/shell/tests/core.test.js`（工作副本全文逐行读）；`.agent/runs/t025-desktop-shell/attempt-003/candidate.patch`、`scope.json`、`summary.md`、`executor-report.md`
- 内核检查：`.agent/runs/t025-desktop-shell/attempt-003/checks/01/{checks.json,V01.log,G01.log,R01.log,V02.log}`
- 门禁：`.agent/mailbox/tasks/T025-6-gate-post/report.md`、`evidence/whitebox-20261101T094424342524Z.py`、`evidence/mutate-20261101T094427257927Z/mutations.json`
- JEV：`.agent/mailbox/tasks/T025-6j-jev/report.md`

Verdict: PASS
