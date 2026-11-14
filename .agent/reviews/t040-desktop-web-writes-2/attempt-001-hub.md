# 复审记录：t040-desktop-web-writes-2 attempt-001（七端信箱 hub）

- 合同：t040-desktop-web-writes-2.v1（base 2326220f6bc4d66fdc36e602d1295e4d5ffe29be）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261114T132727744054Z-e418），终审报告如下

## 终审报告

# T040-7-audit-post 终审报告（audit-sonnet）

任务：T040 桌面端前端第 6 片（写操作的真实模式收尾），候选 attempt-001。
基线 2326220f，候选树 3a5b5f5。合同 `.agent/plans/t040-desktop-web-writes-2.v1.md`。

**结论：通过。** 无 candidate_defects，无阻塞项；两条不挡的意见写在第 6 节。

---

## 1. 本回合做了什么

- 读候选补丁 `.agent/runs/t040-desktop-web-writes-2/attempt-001/candidate.patch`（5 个文件、+531/-4）与工作树里的实际源码（候选已应用）。
- 逐条核对合同的 Behavior contract、边界输入与 D01–D13。
- 核对内核的检查记录（`checks/01/checks.json` 与四份日志）、战后门禁报告、白盒门禁文件 `tests/test_gate_t040_whitebox.py`、变异清单与变异结果。
- 核对执行报告的自述与内核摘要里的线索（可疑命令、被掩盖的退出码、新增被忽略路径）。
- **本回合没有跑任何命令**（本次会话只有读文件/搜索/列目录的工具，没有 shell），所以我没有自己重跑检查；结论建立在「内核在候选树上跑出的检查记录 + 我逐行读的源码」上。这一点在下文每个依赖处都标了出处。

## 2. 改动面：合同允许集合内，没有偷偷扩大

| 文件 | 状态 | 合同允许 | 实际改动 |
|---|---|---|---|
| `desktop/web/src/writes/useWriteFlow.ts` | M | 允许改 | import 一行 + `readSnapshot` 的门 + 注释 + `runPreview` 组 notes（14 行） |
| `desktop/web/src/api.ts` | M | 允许改（只动第 246 行注释） | 只有那一句注释（补丁 1 行） |
| `desktop/web/src/writes/useLivePreview.ts` | M | 允许改（只动第 2 行注释） | 只有那一句注释（补丁 1 行） |
| `desktop/web/tests/writes-live-flow.test.tsx` | A | 允许新增 | 18 条用例 |
| `desktop/web/tests/writes-live-preview.test.tsx` | A | 允许新增 | 3 条用例 |

禁改清单（`src/live/**`、`src/mock/**`、`WriteConfirmDialog.tsx`、`writeOutcome.ts`、`snapshots.ts`、`src/pages/**`、`tests/` 下既有文件、`ts/**`）一个都没动：`changes.json` 只列上表 5 个文件，`candidate.stat.txt` 与补丁一致，既有测试文件零改动（`observations.json`：assertion_lines_added 103 / removed 0、skip_markers_added 空、main_repo_changed false）。锁文件与 `package.json` 没动。

## 3. 实现是否忠实于合同（逐条）

- **真实模式门**：`useWriteFlow.ts` 顶部 `import { liveClient } from '../live/mode';`（只这一个符号）；门开在 `readSnapshot` 函数体内：
  `if (isReread && liveClient() === null && (writeScenario() === 'reread-fail' || writeScenario() === 'reread-fail-exit1'))`。
  代码里没有 `liveModeIsReal`（只在注释里解释为什么不用它），四个网络整词一个都没有。夹具模式多了一个前提，行为一字不变 ✓。
- **needs_yes 原因句**：`const notes = data.needs_yes === true && data.running_attempts.length === 0 ? ['有状态读不出来，不能确定没有正在运行的 attempt；这次改动需要你确认。', ...data.notes] : data.notes;`
  逐字与合同一致；合取、前插（不是追加）、命中才加；`content.notes` 用的是这个变量；没新增界面元素与类名（`WriteConfirmDialog.tsx` 零改动，渲染仍是 `wf-note` 段落）✓。
- **api.ts 注释**：新句逐字为合同那句，全文不再有「501」；去注释后代码逐字不变（补丁只有这一行）✓。
- **useLivePreview 注释**：新句逐字为合同那句，`const DEBOUNCE_MS = 300;` 未动，其余代码零改动 ✓。
- 没有为过测试写的特判：`liveClient() === null` 与 `needs_yes && running 空` 都是合同写死的判据，不是迁就测试的写法；没有把业务逻辑抄进实现。

## 4. DoD → 证据（终审逐条核对）

| DoD | 证据 | 判定 |
|---|---|---|
| D01 真实模式不认 `?write=` 重读演示情景 | 实现的门（源码）+ 新测试「hash 带 ?write=reread-fail / reread-fail-exit1：照常重读并出轻提示，不出现「重新读取失败」」两条 | ✓ |
| D02 needs_yes 原因句 | 三条用例：`.wf-note` 第 0 条逐字相等且排在原样路径行之前（notes.length===2、notes[1] 含 roles/build）；running 非空时 `not.toContain(REASON)` 且 `.wf-note` 数为 0；needs_yes 假时全无 | ✓ |
| D03 api.ts 只改注释 | 补丁 1 行 + 白盒 W3/W3b | ✓ |
| D04 useLivePreview 注释 | 补丁 1 行 + 白盒 W4/W4b | ✓ |
| D05 只注入不 mock | 两份新文件无 `vi.mock`（对整个 `desktop/web/tests` 扫过：命中的都是既有文件）、无 skip/only/todo；假客户端实现 get/post/getRaw 并记路径、正文、时限 | ✓（见意见 3） |
| D06 真实路由与正文 | 「预览发 POST /api/v1/preview…执行发 POST /api/v1/presets/economy/use」用例断言路径、正文 `{action,args}` / `{confirmation}`、时限 30 / 90；断线后断言 `GET /api/v1/operations/<确认号>` | ✓ |
| D07 成功只在重读之后 | 「重读挂起时整页没有「已切换」、Toast 空；兑现之后才说成功」：断言 `dlg` 未关、页面无「已切换」、`.tt-toast` 为空，兑现后才出现轻提示 | ✓ |
| D08 九条分支 | 状态已变（+ 读次数不增）、过期、繁忙（+ 回可确认 + 查了一次操作）、断线后轮询（+ [取消] 禁用 + running→succeeded）、120 秒上限（119s 不下结论、120s 进「结果未知」+ [打开历史]）、服务出错（+ 原文）、超时、部分写入（+ [查看历史]）、内核拒绝 —— 每条都断言真实 DOM 文案与按钮，不是记号 | ✓ |
| D09 真实模式重读失败 | 读 reject 与读回 ok:false 两条，都断言「命令已成功，但重新读取失败，请刷新」+ [关闭] + 无轻提示 | ✓ |
| D10 useLivePreview 真实模式 | 299ms 不发 / 300ms 恰好一次 + 命令去掉两个开关；400 信封显示 messages 原文；post reject → 「预览失败：服务没有回应」 | ✓ |
| D11 夹具模式不变 | 未改任何既有测试；V01 里 `writes-flow.test.tsx` 23 条全绿；G01/R01 全绿 | ✓ |
| D12 不越权 | 第 2 节 | ✓ |
| D13 检查全绿 | 内核 `checks/01`：G01 **9 passed**；R01（**37 个门禁文件全量**）**923 passed in 1216s**；V01 **112 files / 1056 tests passed**；V02 `tsc --noEmit` 退出 0 | ✓ |

关于 R01 的那条遗留：执行端自述「R01 未全量（只跑了 16 个文件 451 条）」是**它自己手动跑**的情况；内核在候选树上的检查记录里 R01 跑的是合同写明的完整命令（37 个文件），923 passed、退出 0（`checks/01/checks.json` 的 argv 与 `R01.log`）。战后门禁交给验收端补跑全量 R01 的那条要求，因此有着落，不构成缺口。

## 5. 门禁记录与自述的核对

- **白盒门禁**（`tests/test_gate_t040_whitebox.py`，8 条）：W1 判据接线（import 恰好一个符号、代码真调用、门与两个情景值同句在 `readSnapshot` 内）、W2 原因句逐字 + 合取 + 前插形状、W3/W4 两处注释、W3b/W4b 去注释后与基线逐字相同、W5 两份新测试的收尾（复位注入/假计时器/不 mock 被测模块/无 skip）。都是真断言，不是空心断言；W3b/W4b 以 `test_transitional_` 开头并在 docstring 里写明将来按名字退役——符合仓库既有做法，不是「集成之后必然失败」的暗坑。
- **变异清单**（12 条，全部非等价、全部被抓住）：mutations.json 记「caught 12 / missed 0 / skipped 0 / error 0」，每条都有 M0x.log 与退出码 1 的理由，`files_left_modified: []`。逐条看下来都是有意义的变异（接线拆除、门反向、拆门、注释删除、丢 running 半边、合取改析取、原因句挪尾、措辞改字、两处注释退回、DEBOUNCE 300→400、api.ts 代码改 needs_yes 恒真），没有「改了但测不出来」的等价豁免，也没有「没法变异」而未覆盖的文件：3 个非测试改动文件每个至少一条变异，两份新测试是测试文件不变异。**没有需要我裁定的门禁端候选缺陷**（门禁端声明 candidate_defects 为空，我同意）。
- **执行自述 vs 内核线索**：内核摘要里的「可疑命令 `rm -rf desktop/web/dist`」与执行报告「dist 已删除」对得上，dist 是构建产物（gitignored），不是越权删文件；「2 条命令退出码被管道掩盖」是探索性的 grep，不是四条必需检查，四条必需检查由内核在候选树上带真实退出码跑过；「新增被 Git 忽略的路径」是 `.pytest_cache/` 与 `node_modules/`，不进候选。**没有发现自述不实**。
- **JEV 判断**：T040-6j-jev 报告为 `no_opinion auth_failed`（无意见），没有可核的内容，不影响判定。

## 6. 发现（不挡，仅供站主/后续片参考）

1. 预览那份新测试（`writes-live-preview.test.tsx`）的假客户端里 `get`/`getRaw` 只返回信封、不记录调用，只有 `post` 记路径/正文/时限；合同「假客户端实现 get/post/getRaw 并记录路径、正文与时限」由 flow 那份（三个方法都记）满足，不影响判定。
2. 原因句读 `data.running_attempts.length`，假定的是 api.ts 映射后的 `PreviewData` 形状。若服务回 200/ok 但 `data` 缺 `preview`（`mappedPreview` 原样透传），这里会 TypeError；不过改动前同样会崩（崩在 `data.command.filter` 与 `Risks` 读 `content.warnings.length`），只是崩点更早，属既有形状假设，不是本片引入的回归。
3. 已知局限照合同实现：needs_yes 真且 running 非空时只显示 running 那句、读不到的行照旧原样显示（分辨它们要改 api.ts 的预览映射，本片不许改）——测试与白盒探针都钉住了这个边界。

## 7. 本回合没能做的事

- 本回合没有执行任何命令（无 shell 工具），因此没有自己重跑 G01/R01/V01/V02，也没有自己跑白盒门禁与变异；相关结论引自内核的检查记录与战后门禁的存档（出处见上）。
- 没有改动任何文件（审核端只读），没有在主工作区留下任何痕迹。

Verdict: PASS
