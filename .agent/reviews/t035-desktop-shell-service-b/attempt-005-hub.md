# 复审记录：t035-desktop-shell-service-b attempt-005（七端信箱 hub）

- 合同：t035-desktop-shell-service-b.v5（base b5cb4c5d54193974250a693d56100e356df0dee7）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261114T035428430967Z-cf63），终审报告如下

## 终审报告

# T035-7-audit-post 终审报告（attempt-005 · 审核端 audit-sonnet）

## 1. 结论

**通过。** 上一轮（attempt-004）唯一的阻塞项 D06 已修复：服务窗口的收尾守卫改成按窗口身份判、标志随新 run 复位。本轮候选只改 `desktop/shell/main.js` 三处（8 增 1 删），与返工简报一致；内核三条检查全绿；战后门禁的白盒与变异记录成立；执行报告的自述与实现、事件流对得上。

## 2. 候选核对（范围与形状）

- `candidate.patch`：只有 `desktop/shell/main.js`，3 个 hunk / 8 增 1 删；工作目录里的 `desktop/shell/main.js` 与补丁后像逐行一致（我读的是工作目录那份）。
- `scope.json`：A0 M1 D0 T0，越界 0、警告 0，`head_after = b5cb4c5`（返工基线），改的 `desktop/shell/main.js` 在 `allowed_modified_files` 内 → **D08 成立**。
- 事件流里只有**一次** `edit` 调用（`desktop/shell/main.js`，3 个块，路径 `desktop/shell/main.js`），没有第二个写操作；没碰 `tests/**`、`desktop/web/**`、`preload.js`、`shell-preload.js`、`src/ipc.js`、`src/host.js`、夹具、锁文件 → **D09 成立**（没删/跳过/弱化任何既有测试）。
- 补丁三处都落在 D06 范围内：声明处注释（:67-70）、`onRunning` 里建新服务窗口处（:164-166）、收尾回调守卫（:176-182）。**D01–D05、D07–D09 的实现本轮一行未动**，上一轮已核过，按复审封板不重开。

## 3. 上一轮阻塞项复核（复审封板）

**唯一阻塞项 D06：已解决。**

修复内容（`desktop/shell/main.js`）：

| 位置 | 内容 |
|---|---|
| :180 | 收尾回调首行 `if (serviceWindow !== opened) return;` —— 按窗口身份判（当前 `serviceWindow` 是不是自己那一个） |
| :166 | `onRunning` 里 `serviceWindow = opened;` 之后 `serviceGone = false;` —— 标志随新 run 复位 |
| :67-70 | 声明处注释改成「按 run 记 + 身份检查」语义，变量名保留 |

触发路径逐环复核（每一步都在候选源码里核对过）：

1. 起服务 → `onRunning` 建服务窗口 S1（`serviceWindow = S1`，`serviceGone = false`），外壳关掉 W1。
2. 服务被任务管理器杀掉 → `flow.subscribe` 判 `exited && !byShell` → `serviceGone = true` → 当前无外壳窗口 → 分支 2 开服务状态页 W2 → 兑现后 `relay.clear()`、`S1.close()` → S1 的 closed 回调：身份相等（`serviceWindow` 仍是 S1）→ `serviceGone` 为 true → **return**（不收第二次服务、不误退出）✓。
3. 用户点「重启服务」→ `restartService` → `startService(state.repo)` → 新 run → `onRunning` 建 S2 → `serviceWindow = S2`、`serviceGone = false`。
4. 用户关掉 S2 → 身份相等（S2===S2）、`serviceGone` 为 false → 走 `flow.stop()` → 服务以 0 退出 → `app.exit(0)` ✓ —— **这一环在修复前被整个跳过（服务留成孤儿、外壳不再以 0 退出），现在恢复了**。

返工简报点名要防的那条路（"不得只加 `serviceGone = false`"）也确认被堵住：S1 的 closed 若在 S2 建好之后才到，`serviceWindow(S2) !== opened(S1)` → return，不会误停新 run 的服务、也不会误 `app.exit(0)`。

合同四「用户关服务窗口：`flow.stop()`；服务以 0 退出 → `app.exit(0)`；否则往 stderr 写一行 `ERROR: 服务没有以 0 正常退出` 并 `app.exit(1)`」在 `main.js:183-189` 原样保留，一行未改；用户关**外壳**窗口的收尾（starting → `abort()`、running → `stop()`、`app.exit(0)`）也未动。

`serviceflow.js` 侧复核（只读，未改）：`onRunning` 抛错 → `stop()` → exited 事件 `byShell = true` → `subscribe` 的意外退出分支早退，不会与本次复位互相打架；`stop()` 在 run 已 exited 时回 `{exited:false,...}`，所以 S1 那次回调必须被挡住——这一点由身份检查 + 复位标志共同保证。

## 4. 内核检查与门禁记录

内核 fresh 检查（`.agent/runs/t035-desktop-shell-service-b/attempt-005/checks/01/checks.json`）：

| 检查 | 命令 | 退出码 | 结果 | 用时 |
|---|---|---|---|---|
| V01 | `npm test`（cwd `desktop/shell`） | 0 | `# pass 304` / `# fail 0` | 13.5s |
| G01 | `python -m pytest tests/test_gate_t035_baseline.py -q` | 0 | 通过（`\d+ passed` matched） | 2.4s |
| R01 | 三十份 `tests/test_gate_t0XX_baseline.py -q` | 0 | **869 passed in 1138.66s** | 1139s（预算 1800s 内） |

三条 `output_must_match` 全部 matched；`modified_by_checks: false`、`candidate_files_modified: []`、`covers_all_required: true`。

执行端自报（V01 304/0、G01 10 passed、R01 869 passed / 自跑 1282.57s）与内核实测一致，差异只是机器负载导致的耗时不同，不构成问题。

战后门禁（gate-sonnet，T035-6-gate-post）：

- 白盒 w04 收紧成两条硬约束：早退守卫须含 `serviceWindow !== <本轮服务窗口变量>`（方向）、`serviceGone = false;` 必须落在 `onRunning` 体内；w01–w03、w05–w09 一行未改。
- 变异 M01–M06 全打在 `desktop/shell/main.js` 上（去掉身份检查 / `!==`→`===` / 去掉按 run 复位 / 复位值反了 / 比错变量 / 收尾不调 `flow.stop()`）：**caught 6、missed 0、skipped 0、error 0**，baseline `pytest tests/test_gate_t035_baseline.py tests/test_gate_t035_whitebox.py -q` exit 0，`files_left_modified: []`。
- 我复核的白盒文件（内核存档 `whitebox-20261114T034220066674Z.py`）与工作目录里的 `tests/test_gate_t035_whitebox.py` 是同一份（含 `_on_running_body`、`_identity_comparison`、`serviceWindow\s*!==` 方向断言）——我看的正是跑出结果的那一份。
- 门禁端本轮 `candidate_defects` 为空；上一轮那条 w04 红已由本轮修复消除 → **不需要退回战后门禁/门禁端**。

## 5. 执行报告自述核对（内核摘要线索逐条对上）

- **解读**：执行端报告里 `interpretations` 1 条（复用 `serviceGone` 作按 run 标志），落在合同四「必要时再辅以按 run 的标志」之内；`contract_conflicts` / `unresolved_questions` 均为空。事件流 3227 行处执行端权衡了「按窗口闭包 flag」与「复用布尔 + 身份检查」两种改法后选了后者（与最终实现一致），5276 行处自查了守卫方向——都属于同一处解读的推敲，不是三处未申报的合同解读。**自述与实际相符。**
- **掩盖退出码的命令**：内核摘要点名的两条都是 `grep`（读门禁文件），不是测试/检查命令；事件流里没有写工作目录之外的临时文件、没有临时路径产物，`.pytest_cache/`、`node_modules/`、`desktop/web/dist/` 都是 git 忽略的构建产物。**无「临时路径/可疑命令」与自述对不上的地方。**
- **D06 自述**：本轮报 `done`，与实现一致（上一轮报 done 而实现未改、判为不实，本轮已对上）。
- **流程漏斗**：上一轮发现返工简报里「终审列的阻塞项」槽位是过期的；本轮 `plan.md` 的 Rework 第 2 轮明确写入了 D06 阻塞项原文，漏斗已修好。
- **JEV**（T035-6j-jev）：`no_opinion auth_failed`，无意见可纳入。

## 6. 不挡的意见（建议类，不进阻塞项）

1. `serviceGone` 现在是「按 run 语义」的布尔，名字仍像进程级。以后再动这一段，建议改成按窗口命名的局部标志（闭包变量 + 一个 setter）更耐读；当前实现正确、diff 最小，不为此返工。
2. `serviceWindow` 在窗口销毁后不置 null，意外退出分支靠 `isDestroyed()` 兜。可不改。
3. 真 Electron 的窗口次序与退出码仍只有 README 手工冒烟第 4 条兜底（自动化不起真窗口）。建议合入前由站主手工走一遍：结束服务进程 → 回服务状态页 → 重启服务 → 关主窗口 → 服务随之结束、外壳以 0 退出。
4. 工作目录里留着门禁端产出的未跟踪文件 `tests/test_gate_t035_whitebox.py` 与根目录 `mutation-spec.json`（均不在候选补丁里）。是否入库由门禁端/内核定；不影响 pytest 收集（内核 R01 是在没有它们的干净工作区跑的）。

## 7. 结论

**通过。** D06 已修好并复审封板；无新的阻塞项；实现忠实于合同，范围没有扩大，测试没有被削弱。

Verdict: PASS
