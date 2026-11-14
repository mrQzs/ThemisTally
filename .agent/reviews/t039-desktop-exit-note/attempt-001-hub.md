# 复审记录：t039-desktop-exit-note attempt-001（七端信箱 hub）

- 合同：t039-desktop-exit-note.v1（base 65b3bdd2cf0d17d94bb5cbdba11777774273dcab）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261114T111305506533Z-58e3），终审报告如下

## 终审报告

# T039-7-audit-post 终审报告（审核端 audit-sonnet）

- 候选：`t039-desktop-exit-note.v1.a001`（基线 `65b3bdd2cf0d17d94bb5cbdba11777774273dcab` + 8 文件补丁）
- 合同：`.agent/plans/t039-desktop-exit-note.v1.md`（plan_version 1）
- 结论：**通过**（阻塞项：无）

---

## 一、本回合实际读了什么

| 材料 | 位置 | 读法 |
|---|---|---|
| 合同 | `.agent/plans/t039-desktop-exit-note.v1.md` | 全文 |
| 候选补丁 | `.agent/runs/t039-desktop-exit-note/attempt-001/candidate.patch` | 全文（8 个文件、逐 hunk） |
| 执行报告 / 概述 | `attempt-001/executor-report.md`、`summary.md` | 全文 |
| 内核检查记录 | `attempt-001/checks/01/checks.json` + V01/V02/V03/V04/G01/R01 日志 | 逐条读出关键行 |
| 战后门禁 | `.agent/mailbox/tasks/T039-6-gate-post/report.md`、`evidence/whitebox-20261114T102417131712Z.py`、`evidence/mutate-20261114T102423657001Z/{mutations.json,M01.log,…}` | 全文 + 抽查日志 |
| JEV 判断 | `.agent/mailbox/tasks/T039-6j-jev/report.md` | 全文（`no_opinion auth_failed`） |
| **候选源码** | 工作目录里 8 个改动文件 + `shellStub.ts` | 逐个读源码（不只看 diff） |

顺序按岗位要求：先读候选源码，再看检查与门禁记录。

---

## 二、候选实现逐条核对（源码事实，不以 diff 推断）

### 2.1 外壳：`desktop/shell/src/serviceflow.js`

唯一改动点在 `moveTo` 里（源码原样）：

```js
function moveTo(next, newRun) {
  if (current.kind === "exited" && newRun !== true) return;
  current = next.kind === "exited" && current.kind === "running" ? { ...next, afterRunning: true } : next;
  const info = { byShell: next.kind === "exited" ? stopping || aborting : false };
  for (const listener of [...listeners]) listener(current, info);
}
```

- 判据取的是**赋值前那一刻**的 `current.kind`（JS 先求值右值再赋值），与合同一一致；`{ ...next, afterRunning: true }` 与合同写法一致。
- **盖住的三条路径**（读源码推演，与执行端补测一致）：
  - 握手成功后服务自己退出：`spawned.on("exit")` 里 `phase === "running"` 时 `moveTo(exited)`，此刻 `current.kind === "running"` → 带键。
  - 跑起来之后外壳 `stop()`：`stop()` 的兜底分支判 `current.kind === "running"` → 带键。
  - `onRunning` 抛错 → `await stop()` 收服务 → 走上一条 → 带键。
- **启动阶段的五条路径**（此刻 `current.kind` 是 `starting`，一律不带键，且不是 `false`、不是显式 `undefined` 键）：握手前退出（exit2）、坏握手、握手超时、spawn 失败、`starting` 期间 abort。`start()` 的 catch 分支 `moveTo(exited)` 发生在 `moveTo(starting)` 之后、`phase = "running"` 之前，故仍不带键。
- **按 run 算**：新 run 先 `moveTo({kind:"starting"}, true)`，状态回到 `starting`；旧 run 的子进程回调有 `thisRun !== run` 的守卫，键不会跨 run 粘连，也不会继承到新 run。
- **未动的语义**（逐行比对，一字未改）：终态判定 `current.kind === "exited" && newRun !== true` 的 return、`info.byShell` 的取值与按 run 算、`start` 的信封 `{ok:true,value:null}` / `{ok:false,reason:"busy"|"start-failed"|"handshake-failed"}`、`stop()`/`abort()` 的返回值、控制令牌只进 `onRunning` 实参。

### 2.2 前端

- `exitCodes.ts`：`stoppedNote(code: number, afterRunning = false)`，`if (afterRunning) return UNEXPECTED;` 在按码判定**之前**；三句常量与 `firstRunHeadline` 一字未改；文件头第 2 行已改成「两种含义已由外壳的 afterRunning 分开」。默认参数保住了首启页与门禁探针的按码调用。
- `ServiceStatusView.tsx`：只改说明那一行 → `stoppedNote(exited ? service.exitCode : 0, exited && service.afterRunning === true)`，与合同四逐字一致；退出码行（`退出码 <code> · <时刻>。重启后会重新读取数据。`）、`data-exit-code`、`<code>` 标签、h1、图标、两个按钮、`document.title`、不设 `role=alert` 一字未动；视图里没有另写那三句文案。
- `themisShell.ts`：`exited` 分支是 `afterRunning?: boolean`（**可选**，必选键会让启动阶段与桩的负载与类型不符）；说明写在类型上方的注释里，类型体里没有注释。
- `shellpages-scenarios.ts`：新增 `crash-1`（base = exited 1 + `afterRunning: true`，`start` = `{kind:'exited', exitCode:1}` 不带键）；`crash` 的 base 补 `afterRunning: true`，退出码 3 与 `start: {kind:'running'}` 一字未动；11 个旧场景名都在，`SHELLPAGE_SCENARIO_NAMES` 仍是 `Object.keys(SHELLPAGE_SCENARIOS)`。
- `shellStub.ts`（禁改文件）：读源码确认桩 `clone(config.base)` 走 JSON 深拷贝 → `afterRunning` 会被带到页面；`scheduleResolve` 里 1500ms 后发的 exited 是 `{kind:'exited', repo, exitCode, at}`，**不带任何新键**（与合同六一致）。也就是说「crash-1 点重启后说明换成『已经打开』」走的是真实现，不是测试里造出来的假象。
- 首启三件（`firstRunHeadline` / `FirstRunView.tsx` / `firstRunModel.ts`）：不在补丁里，`exitCodes.ts` 里的 `firstRunHeadline` 也一字未改 → D03 成立。

### 2.3 README（两处，按合同八）

- 第 70 行冒烟第 4 条：「…并显示退出码**说明是「本机服务意外退出」那一句**（跑起来之后才退出的 exited 带 `afterRunning: true`，页面据此给说明，退出码那一行仍是真实码）；…」——既有字样（`T032 已落地，页面点得动`、`themis-shell://app/index.html#/service-status`、`重启服务`）一个没删。
- 第 189 行状态说明：补了 `afterRunning` 约定（哪些路径带 `true`、启动阶段不带、判据是赋值前那一刻的状态、键按 run 算、页面据此分辨退出码 1 的两种含义），并把「`ServiceState` 被 `themisShell.ts` 钉死，页面负载多一个键就与类型不符」改成只说「`byShell` 不在 `ServiceState` 里」——原话确实会与新类型自相矛盾，合同要求改是对的。
- `| **1** |` 那一行（README:44）**一字未动**，行内没有「服务意外退出」（T035 `test_s05_readme` 的红线守住）；第 186 行的 `ERROR: 服务意外退出（退出码 N）` 是既有原文，未改。

### 2.4 范围与纪律

`scope.json`：`A0 M8 D0 T0`、`violations: []`、`warnings: []`、`ok: true`，8 个文件全部 `in_scope`，与合同 Scope 的 8 个允许改动文件逐一对上；`head_after` 仍是基线提交（未提交、未推送）。`changes.json` 里只有 M、没有 A/D/T。两个测试文件的 diff 是纯新增（`serviceflow.test.js` +173、`shellpages-service-status.test.tsx` +43，合计 216 insertions / 0 deletions），既有用例一条不删不改；新增用例里没有 `skip`/`only`/`todo`。

---

## 三、DoD → 证据映射

| DoD | 核对结论 | 证据（我亲自核过） |
|---|---|---|
| D01 外壳带 `afterRunning`，启动阶段不带，键按 run 算 | 成立 | `serviceflow.js` 源码（2.1 的三条/五条路径推演）；执行端新增 6 条外壳用例（V01 通过）；白盒 W06（真起子进程，run1/run2 键重現）、W07（starting 期间 stop 不带键）；变异 M01/M02/M03 被抓 |
| D02 页面按 `afterRunning` 给说明，退出码行照旧 | 成立 | `ServiceStatusView.tsx` 源码只改一行；`exitCodes.ts` 分支在按码之前；白盒 W08/W09/W10（真渲染 App）；变异 M04–M08 被抓 |
| D03 首启第 4 步不变，三句只在 `exitCodes.ts` | 成立 | 补丁不含首启三件；`firstRunHeadline` 未改；`exitCodes.ts` 里三句常量仍在；V02/V04/R01 全绿 |
| D04 退出码 1 两种情形都有用例 | 成立 | `shellpages-service-status.test.tsx` 新增 3 条 it（crash-1 初始 / exit-1 / crash-1 重启 1500ms 后换说明、退出码仍 1、仍留在 `#/service-status`、按钮恢复）；白盒 W09 |
| D05 README 两处 | 成立 | README:70 与 README:189（贴原文核对）；README:44 未动；变异 M15–M17 被抓；T035 在 R01 里绿 |
| D06 范围与纪律 | 成立 | `scope.json` ok / A0 M8 D0 T0；禁改文件（`shellStub.ts`、`main.js`、`shellapi.js`、`shell-preload.js`、夹具、两份锁文件、`ts/**`、`docs/**`、`scripts/**`、`tests/**`）均不在改动清单里 |
| D07 不删不弱化既有测试 | 成立 | 两个测试文件 0 删除；无 skip/only/todo；既有用例的原文我逐行读过（`shellpages-service-status.test.tsx` 既有 5 条 it 未动；`serviceflow.test.js` 既有 8 条 test 未动） |
| D08 回归 | 成立 | 内核独立复跑 G01 `11 passed`、R01 `913 passed`（日志原文）；门禁文件未删未改 |

---

## 四、检查与门禁记录的独立核对

### 4.1 内核自己的检查（`checks/01/checks.json`，在候选树上重跑）

| ID | 命令 | 退出码 | output_must_match | 我从日志读到的原文 |
|---|---|---|---|---|
| V01 | `npm test`（desktop/shell） | 0 | `# pass \d+`、`# fail 0` 均 matched | `# tests 310` / `# pass 310` / `# fail 0` |
| V02 | `npm test`（desktop/web） | 0 | `Tests\s+[1-9]\d* passed` matched | `Test Files 110 passed (110)` |
| V03 | `npm run build` | 0 | `built in` matched | `✓ built in 1.17s`（含 `tsc --noEmit`） |
| V04 | `npm run check:contract` | 0 | `契约检查：通过` matched | `契约检查：通过，无违规。` |
| G01 | `pytest tests/test_gate_t039_baseline.py -q` | 0 | `\d+ passed` matched | `11 passed in 12.70s` |
| R01 | T001–T036 门禁回归 | 0 | `\d+ passed` matched | `913 passed in 1195.26s (0:19:55)` |

执行报告自述的数字与内核记录**逐条一致**（V01 310/310/0、V02 110 files、R01 913 passed、G01 11 passed）；自述的唯一差异是 R01 墙钟（自跑 1391.89s vs 内核复跑 1195.26s），属机器负载差异，不是自述造假。

### 4.2 战后门禁

- 白盒 `tests/test_gate_t039_whitebox.py` 10 条：W01–W05 静态结构断言（键只接在 `moveTo`、默认参数与分支、三句常量、夹具头计数与取值、README 两处、可选键）；W06/W07 是 `node --test` **真起子进程**的行为探针；W08–W10 是 Vitest **真渲染 `src/App`** 的页面探针（自检夹具后再断言页面文字）。不是空心断言：页面探针断言的是渲染出来的文字，行为探针断言的是真实状态机的键。
- 变异：`mutations.json` = caught 17 / missed 0 / skipped 0 / error 0，`expected_missed: 0`，`decisions: null`（**没有声明任何等价变异**），`files_left_modified: []`。6 个非测试文件每个至少一条变异（serviceflow×3、exitCodes×2、view×3、themisShell×2、scenarios×4、README×3）。
- 我抽查 M01 日志：失败落在 **W06 的行为断言**（`run1：跑起来之后退出要带键` 实得 `undefined`、期望 `true`），说明这类变异是被行为探针抓住的，不是只靠静态文本匹配。
- 门禁端自查事故（`git checkout --` 把两个文件还原到基线）已恢复：报告称用只读输入目录里的 `candidate.patch` 重新 `git apply` 并用 `git apply --reverse --check` 全量比对通过。我直接读了本回合工作目录里的 `serviceflow.js` 与 `exitCodes.ts`，确认两处都是候选内容（键三元、`if (afterRunning) return UNEXPECTED;` 都在），事故没有留下坏内容。
- `desktop/web/gate-probe/` 目录在本回合工作目录里已不存在（白盒的 pipeline 夹具在 finally 里删净）；白盒的 node 探针走 `tempfile.TemporaryDirectory`，落在系统临时目录并自动清理，与 AGENTS.md 认可的 `mktemp -d` 模式一致。

### 4.3 对门禁端声明的逐条裁定（岗位要求）

- **等价变异**：门禁端声明 0 条（`expected_missed: 0`、`decisions: null`），没有「测不出来」的辩解需要复核 → 无异议。
- **「没法变异的改动文件」**：门禁端声明 `unmutated: 无`，6 个非测试文件每文件至少一条变异；我对照 `mutations.json` 逐条核过 id 与文件，确实覆盖了全部 6 个非测试文件 → 无遗漏文件需要裁定。

---

## 五、执行报告自述 vs 内核摘要线索（逐条对上）

| 内核摘要线索 | 我的核对 | 结论 |
|---|---|---|
| 新增被 Git 忽略的路径：`.pytest_cache/`、`desktop/web/dist/`、`ts/node_modules/` 等 | 都是跑检查的副产物（pytest 缓存、V03 的 build 产物、依赖安装戳记），全部被 Git 忽略；候选树是 A0/M8/D0/T0，`scope.json` ok，没有一个进候选 | 不是候选缺陷，也不构成「自述不实」（见意见 4：措辞偏松） |
| 「掩盖退出码的写法（11 条命令，`|| true` 直接抹掉）」 | 内核自己判定这些不是测试/检查命令；我另核执行端事件流：V01–V04 全部是 `set -o pipefail; cd … && npm … 2>&1 \| tail -n 40`，管道后的退出码没有被抹；11 条 `\|\| true` 里的是 `wc -l`/`grep` 之类的只读探查 | 与自述一致，无自述不实 |
| 「工具错误 1」 | `events.jsonl:2681`：一次 `edit` 因「替换后内容相同」而报空错，随后该文件重做成功；最终文件内容由补丁逐字核对 + V01 310 全绿确认 | 无残留影响 |

---

## 六、发现

### 阻塞项（会导致打回）

无。

### 不挡的意见（建议类，写在这里不退回）

1. **白盒 W02 把写法钉死了**：它要求 `exitCodes.ts` 里出现字面量 `if (afterRunning) return UNEXPECTED;`。语义等价但写法不同（加大括号、换成三元、先判 `afterRunning === true`）都会红。W08 已经用行为断言覆盖同一件事，建议合入后把 W02 放宽成「有 afterRunning 分支且默认参数在」，别让门禁只认一种写法。
2. **W03 其实不钉死数字**：它比的是「文件头里的数字 == 实际场景键数」，不是「== 12」；执行端把夹具头从 11 改成 12 是它的自选措辞（interpretations 1），不违反合同。建议保持这种「数字不许是假话」的写法。
3. **执行报告「无临时文件残留」的措辞偏松**：工作树里确实留着 `.pytest_cache/`、`desktop/web/dist/`、`ts/node_modules/`（都是 Git 忽略的检查副产物，不进候选）。不改结论，只是措辞收紧。
4. **R5 仍未覆盖**：真 Electron 下 `afterRunning` 经 IPC 过桥（`main.js` → `SERVICE_STATE_CHANNEL` → `shell-preload.js` → 页面）与 `exitCode`/`at` 同路，自动化测不到；合入后仍要站主在真窗口走 README 冒烟第 4 条。README 已把预期写清（说明是「本机服务意外退出」那一句、退出码那一行仍是真实码）。
5. **JEV 本轮 `no_opinion auth_failed`**：筛查器没跑起来（基础设施问题，不涉及候选）；结论依据是内核独立复跑的六条检查与战后门禁的 17 条变异。
6. audit-pre 遗留的两条不挡建议（S06 的措辞别钉死、断言 `gate-probe` 目录已删）门禁端仍未采纳，仍是不挡。

---

## 七、结论

候选忠实实现了合同的一到十节；改动范围与纪律无越界；既有测试既没删也没弱化；执行报告的自述与内核独立检查记录、战后门禁记录逐条对得上，没有自述不实，也没有「为过测试而写的特判」「空的异常处理」「悄悄扩大的范围」。

**结论: 通过**（无阻塞项，不退回任何端）。

Verdict: PASS
