# 复审记录：t057-desktop-web-runtime-record attempt-003（七端信箱 hub）

- 合同：t057-desktop-web-runtime-record.v3（base 759287fe666f91e75dfadf210051816cd68decdc）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 answered
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261119T120000121496Z-8e21），终审报告如下

## 终审报告

# T057-7-audit-post 终审报告（审核端 audit-sonnet · 2026-11-19 UTC）

## 0. 结论

**通过**。无阻塞项，不退回（return_to：无）。

本回合输入没有「门禁端举证的候选缺陷」一节；战后门禁报告明确 candidate_defects 为空、白盒在候选上全绿、无 xfail/skip → 没有要裁定的候选缺陷。

## 1. 审的对象

- 合同 v3：`.agent/plans/t057-desktop-web-runtime-record.v3.md`（587 行；plan_version 3；base_sha 759287fe）
- 候选：attempt-003（候选树 436ce55f，补丁 3 文件），连同前两轮合并后的完整改动集
- 执行概述与执行报告：`.agent/runs/t057-desktop-web-runtime-record/attempt-003/summary.md`、`executor-report.md`
- 内核独立跑的检查：同目录 `checks/01/{G01,V01,V02,V03,V04,R01}.log` 与 `checks.json`
- 战后门禁：`.agent/mailbox/tasks/T057-6-gate-post/report.md` + `evidence/whitebox-*.py|.log` + `evidence/mutate-*/mutations.json`
- JEV 判断：`.agent/mailbox/tasks/T057-6j-jev/report.md`；一审与热修补判定：`.agent/mailbox/tasks/T057-4-audit-pre/report.md`

## 2. 候选源码逐条核对（先读源码，再看记录）

### 2.1 上一轮要求撤掉的两处绕路：撤干净了

- `RuntimeDoctor.tsx`：模块级 `lastRecord` 已删（全文无 lastRecord）。`onVerify` 现在只按 `PLAN_KEY_RE.test(record)` 判合格，不合格就 `setRecordError(RECORD_HINT)` 并 return，不发任何请求 → 合同 Non-goals「不做预填、记住上次的值；不 trim 输入值」与「边界输入：值不合格（空值…）不发任何请求」都成立。
- `jobStore.ts`：`doCreate` 恢复成基线逐字（与 attempt-002 补丁里的 `-` 行逐字一致：`if ((subscribers[kind] ?? 0) > 0) startPolling(kind);` 加原注释）→「创建之后立刻查一次」的语义回来，四类旧作业的轮询节奏与基线一致；合同 Steps 第 3 步「jobStore 签名与逻辑都不动」成立。

### 2.2 doctor-record 的五种状态语义（合同 Behavior contract）

逐情形推演 `restartJob`（jobStore.ts:100-107）与 `ensureJob`（:87-97）：空槽→建；终态同值→restartJob 建、ensureJob 共用在途创建（只发一次）；终态异值→restartJob 交回旧作业、ensureJob 建（只发一次）；在跑同值→都不建；在跑异值→都不建；创建失败→restartJob 建。与合同的「实现口径」逐字一致，槽里记的 runtime 就是 `<task>.vN`。

### 2.3 界面（RuntimeDoctor.tsx）

- 入口：`.rd-entries` 横排容器里 [运行就绪检查] 原样 + `.rd-record` 组（TextField label 逐字「按版本记录核验」、mono、无 list、不预填、不 trim）+ [核验]（secondary/md、无图标）。禁用只看 doctor-record（creating/queued/running），空闲恒可点（运行时页禁用按钮数照旧 0）。
- 结果区 `.rd-record-body`：failed 带 data → 只渲染 RecordResult（不渲染 JobCard）；succeeded → 结果块放在 JobCard 的 children 里；无 data 的 failed、取消、超时 → 交回 JobCard。标题逐字「版本记录 ${first?.record ?? '—'}」，不加汇总行，复用 HeadlessCard，行是头less 的判定沿用 doctor 那一套。
- T056 的记号与逐字文案一个没删；没有 useBusyRuntime、没有跨层引 src/pages、只引 './runtime-doctor.css'（源码里 useBusyRuntime / src/pages 只出现在 T056 原有注释里）。

### 2.4 客户端、卡片、桩、样式

- api.ts:155 JobKind 五类（doctor-record 在末尾）；:774 写明第二个参数的含义；:780-782 正文第三支 `{ kind, record: runtime }`，`{ kind }` 与 `{ kind, runtime }` 两个字面还在，没有 `runtime: undefined`，postRaw / 15 / 201 / mockStartJob 照旧。
- JobCard.tsx：三张按 kind 的表各加 doctor-record（600 / 核验失败 / 核验进行中），旧四支字面未动。
- mock/jobs.ts：缺记录值回 400 且守卫在 `seq += 1` 之前；logs-cat.v2 给有 data 的结果（那一行加 record 键、奇偶）；别的记录落 failed 无 data 并给内核那句；奇偶用独立的 `recordCounts`（doctorCounts 一个字没动）；桩里没有计时器、没有 .json、没有 WriteScenario。
- runtime-doctor.css：`.rd-entries` / `.rd-record` / `.rd-record-body` 三条规则在位，只用 --tt- 令牌、不写死颜色、不写内联 style、类名一律 rd- 前缀。

### 2.5 旧断言逐处改（合同「兼容性」一节）

- t009：:2895 标题改后半句；:2909-2911 改成「不为 null 且 disabled 为 false」；:2972 标题末尾接「与 T057 接上的 [核验]」；:2976 白名单在 '运行就绪检查' 后加 '核验'；:2903-2908 与 :2977（`disabledButtons().length` toBe(0)）一字未动。
- page-runtimes.test.tsx：:116 标题改后半句；:125-126 改成 toBeTruthy + disabled 为 false；:120/:123/:124 未动。
- 包内 page-app:91-98、readonly2-app:106 未动（R01 1142 passed 兜住）。

## 3. 有没有为过测试而写的特判、弱化测试

- 本轮三个文件的差异逐行看过：只有「删两处绕路」「卸载再挂载后补一次 typeRecord」「补一条空值断言」，没有一行是迁就断言的代码。
- 断言只增不减：observations.json 记 `assertion_lines_added: 2 / assertion_lines_removed: 0`；新测试文件里 grep 不到 skip/only/todo。
- 源码里没有硬编码的测试输入：`logs-cat.v2` 与 `.agent/runs/logs-cat/binding-v2.json` 只出现在桩里（合同指定的示意原文），界面只显示内核给的 record 与 messages 原文。
- 没有空异常处理：本片改的文件里没有新增的 try/catch 或吞异常分支。
- 上一轮一审记的覆盖缺口（已有作业时清空文本框再点 [核验]）本轮补上了：包内测试 (i) 末尾新断言「creates.length 仍为 3 + 出提示」，这条留在仓库里当回归测试。

## 4. 检查与门禁记录（全绿不等于对，逐条看了）

- 内核在候选上独立跑的六条：G01 `12 passed`、V01 `18 passed`、V02 退出 0、V03 退出 0、V04 `✓ built in 1.54s`、R01 `1142 passed`；checks.json 里六条都是 exit_code 0 / status passed。
- 战后门禁：白盒 `10 passed`；变异记录 `caught 33 / missed 0 / skipped 0`，baseline passed。我逐条看了变异名：M04 正是「把 startPolling 换回 scheduleNext（重引入绕路之二）」、M16「把奇偶计数并回 doctorCounts（重引入 T056 会撞的错）」、M20 去 import、M24 去 restartJob 接线、M31 换 cancelJob 目标、M32/M33 改 CSS 类名 → 接线类与「绕路不回潮」都在清单里；两处 count=2（两张作业卡各一次）已声明。门禁端说没法变异的只有执行端改动的 3 个测试文件（按口径不进清单），我核了这三个确实是测试文件，6 个非测试源文件全覆盖。
- 白盒文件与变异清单按岗位口径只用于本次核验，不当成会留在仓库里的回归测试提意见。

## 5. DoD 自述与内核摘要的线索逐条对上

- 临时路径：events-summary `temp_path_uses: []`、`temp_dirs_without_cleanup: []`、`outside_worktree_paths: []` → 执行报告也没有声称在临时路径写过东西；自述与记录一致。
- 可疑命令：`suspicious_commands: []`。4 条 masked_exit_commands 全是 grep / git log（`check: false`），不是检查；真正的检查命令都带 `set -o pipefail` 与 `EXIT=${PIPESTATUS[0]}`，退出码没有被管道掩盖（与合同 Validation commands 开头那句一致）。
- 主工作区 `M AGENT_LEARNINGS.md`：执行端 cwd 是 worktree（…\pi-worktrees\ThemisTally-t057-desktop-web-runtime-a003-1428ezmr），observations 里 head 未变、landed=false、outside_worktree_paths 为空，32 条命令里没有指向主工作区的写入；候选树里的 AGENT_LEARNINGS.md 也没有 T057 相关内容 → 不是执行端写的，不构成越界（不挡）。
- JEV 两条提示：「自行解读合同 p=0.59」——执行报告列了 3 条 interpretations 且都写了依据；「自述完成而无证据 p=0.86」——12 条 DoD 每条都带证据指针，且证据由内核独立复跑兜住；我逐条对照源码与日志后没有「说完成但没证据」的条目。

## 6. 范围

三轮改动并起来正好是合同允许的 8 改 1 增（api.ts、jobStore.ts、JobCard.tsx、mock/jobs.ts、RuntimeDoctor.tsx、runtime-doctor.css、tests/test_gate_t009_baseline.py、desktop/web/tests/page-runtimes.test.tsx；新增 desktop/web/tests/jobs-doctor-record-page.test.tsx），三轮内核 scope 都是「越界 0」；forbidden_paths（tests/test_gate_t057_*.py、components/**、shell/**、live/**、ts/packages/**、scripts/**、锁文件、既有包内测试等）一个没碰。

## 7. 非阻塞观察（不挡，写进 report 不进阻塞项）

1. 工作目录里留着门禁端写的 `tests/test_gate_t057_whitebox.py`（未跟踪，不在候选补丁与候选提交里）。集成按候选提交/候选补丁取，别把工作目录整个搬过去。
2. `RuntimeDoctor.tsx` 里 `RECORD_CARD_LABELS` 与 JobCard 的表各存一份「核验失败/核验进行中」——合同「写法钉死」要求这两个逐字文案在本文件里（与 T056 的 DOCTOR_CARD_LABELS 同性质），不是新造的特判；将来清旧门禁那批可以一起收。
3. `api.ts:154` 的注释按合同逐字改成「服务还有一类，前端本片不接」，现在读着别扭（本片其实接了 doctor-record），但合同要求这么改。
4. `RecordResult` 用 `first?.record ?? '—'`：若内核给的是空串而不是缺键，标题会成「版本记录 」（空）。内核 recordReadiness 不会给空串，没有具体触发路径，不挡。
5. 合同 v4 仍未落地（.agent/plans 里只有 v1/v2/v3）：v3 的 (h) 措辞与热修补后的门禁不冲突，不挡；若要落 v4，只需把 (h) 段的时序写清。

## 8. 下游须知

- 集成端：按候选提交/候选补丁取，别把工作目录里未跟踪的 tests/test_gate_t057_whitebox.py 带进仓库。
- 门禁端：probe(g) 的空值一例仍是在没有作业时点的，「已有作业时清空再点不发请求」现在靠执行端包内测试 (i) 的新断言钉住（这一条在仓库里，是回归测试）。

Verdict: PASS
