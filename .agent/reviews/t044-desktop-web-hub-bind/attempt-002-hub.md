# 复审记录：t044-desktop-web-hub-bind attempt-002（七端信箱 hub）

- 合同：t044-desktop-web-hub-bind.v4（base f454ef501dac57bc37f87cb19c541607e4de7faa）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261116T061321313688Z-22ee），终审报告如下

## 终审报告

# T044-7 终审报告（audit-sonnet，2026-11-16）

## 结论

**通过。** 候选（attempt-002，基线 f454ef50 + 14 个文件的补丁）忠实于合同 v4：改动集合正好等于允许集合，「写法钉死」1–7 逐条对得上，D01–D13 都有对应证据；没有越界改动、没有弱化既有测试、没有为过测试而写的特判。内核独立复跑的五项必要检查全绿；战后门禁 24 条变异的判定与实测记录自洽，本回合点名的 14 条「这条命令预期抓不住」逐条复核后都成立（漏掉的那条命令确实测不到，但每条都被另一条命令抓住，覆盖面没丢）。**无阻塞项。**

## 1. 复核方法（先源码、后记录）

1. 先读候选补丁 `.agent/runs/t044-desktop-web-hub-bind/attempt-002/candidate.patch`（14 文件，+956/−20），与合同 v4 的 Behavior contract、「写法钉死」1–7、DoD D01–D13 逐条对；
2. 再读工作目录里的真实源码（`useWriteFlow.ts` 的 readSnapshot/confirm 链/runPreview、`api.ts` 的 toPreviewData/getHubRoles/setHubRole/unsetHubRole、`writeOutcome.ts` 的 finalFromReread、`mock/writes.ts` 的 previewData/mockPreview、`snapshots.ts` 的 hubSnapshot、`hubChangeLines.ts`）；
3. 再读内核的检查记录（attempt-002/checks/01/checks.json：G01/V01/V02/V03/R01 全部 exit 0，`modified_by_checks:false`、tree 前后一致、`covers_all_required:true`）与门禁记录（T044-6-gate-post 的白盒文件、24 条变异实测 mutations.json）；
4. 最后核对执行报告的自述与内核摘要的线索（临时路径、可疑命令、掩盖退出码、assertion 行增减）。

## 2. 源码面复核（逐条要点）

- **api.ts（只增不改，83 行全为新增）**：`HubChangeFallback/HubChangeSide/HubChange` 三个 `export interface`；`PreviewData` 加两个必填字段 `hub_changes`/`running_turns`（各占一行、非可选）。映射：`hubChangeOf` 对 `post` 非字符串整项跳过（返回 null 不入列），`hubSideOf` 对非对象侧、非 default/config 的 source、非字符串的六字段一律归 null，`hubFallbackOf` 对非对象 fallback 与非字符串字段归 null；`running_turns: stringsOf(preview.running_turns)`（stringsOf 只留字符串项，已核 api.ts:290）；`notes` 仍并入 `unreadable`，既有八字段的映射一字未动。**无硬编码、无特判、无空异常处理。**
- **snapshots.ts**：`HubSnapshot` 的 interface 逐字照「写法钉死」第 2 条（嵌套对象逐字段换行）；`hubSnapshot` 纯函数，只投影 post/source/profile/fallback_profile，`byKey('post')` 排序，`row.fallback?.profile ?? null`。
- **useWriteFlow.ts**：hub 分支逐字为 `if (action === 'hub.set' || action === 'hub.unset') {`，排在 `config.rollback`（本函数第一个 `getPlugins()`）**之前** ✓；读 `getHubRoles()`，失败 `{ok:false}`、成功 `hubSnapshot(hub.data)`（`getHubRoles` 返回 `Envelope<HubRolesData>`，`!hub.ok || !hub.data` 的口径成立）；confirm 链里 hub.set/hub.unset 排在 `setPluginEnabled` **之前**，不再落到插件启停；标题/轻提示/摘要六条文案与合同逐字一致；原因句那一行是合同给的那一行原文（三个条件 + 原因句原文，同一物理行，原因句一字未改）；`content` 里 `hubChanges: data.hub_changes`、`runningTurns: data.running_turns`；`contentOf()` 缺省给两个 `[]`。
- **WriteConfirmDialog.tsx**：`ConfirmContent` 加两个必填字段；`Changes` 的空态条件是 `changes.length === 0 && hubChanges.length === 0`（changes 空且 hubChanges 非空时不出空态、也不出 summary，两者都空才出 `summary ?? '预览没有列出变化'`）；岗位块用 `wf-hub`/`wf-hub__post`/`wf-hub__line`；`Risks` 的 hasRisk 计入 `content.runningTurns.length > 0`，在跑回合那行逐字后半句在位，`有 attempt 正在运行：…` 那行一字未改。
- **hubChangeLines.ts（新）**：只 `import type`、不碰 DOM/时钟；恰好四行、次序固定；「（默认）」**按侧生效**且该侧四行都带（替补行无替补时是 `—（默认）`，与合同例子一致）；替补文字两种拼法（profile 优先，否则 runtime · provider/model）；`hubPostLabel` 六个中文名 + 未知码原样；岗位名表在本文件另维护一份并写了理由（合同 Steps 第 5 步要求，不是随手重复）。
- **write-flow.css**：只在末尾追加三条规则（`.wf-hub`/`.wf-hub__post`/`.wf-hub__line`），只用 `--tt-space-1`/`--tt-text-1`/`--tt-text-2`/`--tt-text-sm`/`--tt-mono-md`，无 px、无颜色字面量、**块内无任何注释**（上一版凑字节数的长注释确实撤了）；基线 1597 字节前缀未动（diff 显示只在文件末尾追加，S06 的 sha 校验在内核 R01 里绿）。
- **mock/writes.ts**：四个岗位情景进 `WriteScenario` 与 `SCENARIOS`（既有 23 个一字未改）；6 处 `PreviewData` 字面量都补了两个字段；hub 分支按夹具算 `hub_changes`（before 取名册行、after 取 profiles.json 的 `step-high` 一行或另放一份的 `HUB_DEFAULTS`），`HUB_DEFAULTS` 与 `scripts/kit_roles.py:82-90` 逐项核对一致（coordinator 的 fallback 是 pi/dsf/deepseek-flash/high，其余五岗 fallback 为 null）；`args.post` 不在六行里 → 空数组；桩数据里没有引入 `step-low`（既有 6 处演示字面量原样在位，已在工作目录逐行数过）；桩只在 `liveClient()` 为 null 时生效（`mockPreview` 未改）。
- **三个新测试文件**：`writes-hub-api.test.ts`（映射逐字段 + 缺键兜底 + 两条写路由与正文）、`writes-hub-logic.test.ts`（快照投影与排序、四行文案与两种拼法、六个岗位名）、`writes-hub-flow.test.tsx`（真实模式注入假服务跑完整流程、确认框渲染、needs_yes 两种说法、桩四情景）。断言打在真实实现上（不 mock 被测组件），无 skip/only/todo（内核 observations.json 的 `skip_markers_added: []` 与 S08 双向一致）。
- **范围**：`scope.json` 的 14 个文件全部 `in_scope`（A4/M10/D0/T0、violations 空）；forbidden_paths（`tests/test_gate_t044_*.py`、其余门禁文件、`ts/packages/ui/**`、`scripts/**`、`desktop/web/src/pages/**`、`src/mock/*.json`、`src/mock/hub-roles.ts`、五份禁改测试、`package.json`/锁文件）一个都没碰；`tests/test_gate_t022_baseline.py` 只动了那一处期望键表（一个 hunk，2 行换 2 行）。

## 3. DoD → 证据（复核结果）

| DoD | 结论 | 证据（复核过的） |
|---|---|---|
| D01 预览映射 | 达成 | api.ts 源码 + `writes-hub-api.test.ts` + `writes-hub-logic` 无关；T022 十键键表（D13） |
| D02 hubSnapshot | 达成 | `writes-hub-logic.test.ts`（四字段、按 post 排序、替补 profile 为 null） |
| D03 路由/文案/不落 setPluginEnabled | 达成 | `writes-hub-flow.test.tsx`（路径断言 + `expect(paths.some(p => p.startsWith('/api/v1/plugins/'))).toBe(false)`）+ `writes-hub-api.test.ts` |
| D04 原因句与两种说法 | 达成 | 源码同一物理行 + `writes-hub-flow.test.tsx`（unreadable→原因句在 notes 第一条；running_turns→不出原因句、Risks 逐行；running_attempts→旧说法照旧）；R01 含 T040 |
| D05 变化一节 | 达成 | `writes-hub-flow.test.tsx`（四行对比、「（默认）」、不出空态）+ 白盒 W-P 探针第 2/4 条 |
| D06 纯逻辑 | 达成 | `writes-hub-logic.test.ts` |
| D07 桩与四情景 | 达成 | `writes-hub-flow.test.tsx` 桩段 + S07（R01 内） |
| D08 既有测试未弱化 | 达成 | diff：三个既有测试文件只各补夹具字段，断言一字未改；V01 121 files/1151 passed |
| D09 范围 | 达成 | scope.json（violations 空）+ candidate.stat.txt |
| D10 源码规矩 | 达成 | S06/G01/R01 + `hubChangeLines.ts` 只 import type、无 DOM/时钟 |
| D11 不调插件启停 | 达成 | `writes-hub-flow.test.tsx`（三条路径断言） |
| D12 桩数据规矩 | 达成 | S07（step-low 恰 6 处）+ `writes-hub-flow.test.tsx`（`JSON.stringify(...).not.toContain('step-low')`） |
| D13 t022 恰一个 hunk | 达成 | 白盒 W01（当前文件 == 基线 blob 的一次片段替换）+ patch 里的单个 hunk |

## 4. 门禁端「这条命令预期抓不住」的 14 条变异——逐条裁定

| 变异 | 漏掉的命令 | 实际抓住它的命令 | 裁定 |
|---|---|---|---|
| api: post 非字符串守卫失效 | W1（静态查文本，查不出行为差异） | W2：`writes-hub-api.test.ts` 断言 post 不是字符串的项被跳过 | 成立（测得到） |
| api: hubSideOf 丢掉 source==='config' | W1 | W2：逐字段 `toEqual` 断言 source='config' | 成立 |
| api: 返回对象不带 hub_changes 键 | W1 | W2：键集断言 | 成立 |
| snapshots: 改按 source 排序 | W1 | W2：按 post 排序断言 | 成立 |
| snapshots: 去掉 import type 的 HubRolesData | W2（类型导入编译后擦除，运行时无差别） | W1：静态断言 import type 行 | 成立 |
| useWriteFlow: 去掉 getHubRoles 的 import | W1 | W2：运行时未定义 | 成立 |
| WriteConfirmDialog: 空态 && 改 \|\| | W1 | W2：不出空态的渲染断言 | 成立 |
| hubChangeLines: 「（默认）」错认成 config | W1 | W2：四行文案断言 | 成立 |
| hubChangeLines: 替补文字改看 runtime | W1 | W2：两种拼法断言 | 成立 |
| mock: HUB_DEFAULTS 的 contract 缺省 model 被改 | W1 | W2：`after.model` 断言 | 成立 |
| mock: hub 分支 after 恒取 hub.set 一侧 | W1 | W2：hub.unset 的 after 是缺省 | 成立 |
| mock: hub-running 的 needs_yes 恒假 | W1 | W2：needs_yes 为真 | 成立 |
| css: `.wf-hub__line` 改名 | W2（jsdom 不加载 CSS） | W1：S06/W02 的选择器文本断言 | 成立 |
| css: `.wf-hub__line` 字体令牌改 12px 字面量 | W2 | W1：S06 的 px 字面量断言（除 0/1px 外须带出处注释） | 成立 |

**结论：14 条里 W1 漏的 11 条全被 W2 抓、W2 漏的 3 条全被 W1 抓，mutations.json 的实测记录（caught 13/missed 11、caught 21/missed 3、unexpected_missed 为空）与此一致。门禁端声明「这条命令测不到」成立，覆盖面没有丢。** 门禁端说「测试文件不需要变异」也成立：既有测试文件在 diff 里只补夹具字段，断言一字未改；三个新测试文件的断言打在真实实现上。

## 5. 执行报告的自述 vs 内核摘要的线索

| 内核摘要的线索 | 执行报告的说法 | 复核 |
|---|---|---|
| 「掩盖退出码的写法（9 条命令）」 | 无 | events-summary.json 里 9 条全部标 `check:false`（ls/grep/git show 之类）；执行端真跑的 pytest/npm 命令都带 `set -o pipefail`，必要检查由内核另跑（checks/01 全部 exit 0）→ **自述不实的部分没有** |
| 「删除了 1 行含断言的代码」 | D13：只改期望键表 | 对得上：删的那行就是 `expect(keys).toEqual([...八键])`，换成合同第 7 条的十键片段（授权的唯一例外），其余部分一字未动 |
| 「临时路径」线索 | 无 | `temp_path_uses: []`、`temp_dirs_without_cleanup: []`、`suspicious_commands: []` → attempt-001 那种往固定临时路径写文件并报 done 的问题在本轮没有重演 |
| 「4 处提到合同的歧义」 | interpretations 三条、contract_conflicts 空 | 对得上：①桩替补不按适配器筛、②hub-ok/hub-unset 为显式别名、③原因句同一物理行——三条与合同边界输入一致，门禁端已逐条核实（解读①②由 W03 与探针钉住）；第 4 处（hub-warn 的 needs_yes 为假）符合合同（hub-warn = hub-ok + 警告，needs_yes 假） |

## 6. 不挡的意见（写进 report，不退回）

1. `hubChangeLines.ts` 与 `roles-logic.ts` 各有一份岗位中文名表：这是合同 Steps 第 5 步明写的设计（不跨层引 `src/pages`），但以后改岗位名要两处同步——T045（B 片）要特别注意。
2. 桩的 hub-warn 警告对 hub.set 与 hub.unset 都给；内核 `_hub_set`/`_hub_unset` 同样都打这条 WARN，所以这是对的，不算超出合同。
3. `Changes` 里岗位小标题用 `<span className="wf-hub__post">`（不是标题元素）：合同只要求「小标题行 + 类名 wf-hub 前缀」，门禁 S05 也只查类名与文案，不挡；若站主想要真标题元素，可留给 T045 的 UI 打磨。
4. 候选里 `desktop/web/dist/`、`.pytest_cache/` 是构建/测试产物，均被 Git 忽略，未进候选。

## 7. 后续

- 本片（桌面端前端第 10 片 · A 片）可以合入；合入后 `tests/test_gate_t044_whitebox.py` 留在仓库当回归测试（其探针用例依赖会话级 pipeline 夹具，全量 pytest 经 conftest 跳过，点名运行才起 npm）。
- B 片是站主另登记的 T045：入口与表单、替补筛法（主选是 quizs 才能选替补）、三条门禁准备（T038 退役/放宽、T009 白名单加两项）都在 T045 合同里，本片一条都没碰。

**结论：通过。退回：无。阻塞项：无。**

Verdict: PASS
