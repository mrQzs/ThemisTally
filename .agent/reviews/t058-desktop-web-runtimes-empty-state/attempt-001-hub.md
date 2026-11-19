# 复审记录：t058-desktop-web-runtimes-empty-state attempt-001（七端信箱 hub）

- 合同：t058-desktop-web-runtimes-empty-state.v1（base 6bcc3aa6cc836cc4bc44b2096c8a9e13c9d91478）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 answered；终审前 answered
- 复审者：audit-sonnet（MiniMax-M3.1-Flash，思考档位要求 max、生效 未回报；回合 20261119T150733346620Z-e3f5），终审报告如下

## 终审报告

# T058-7 终审报告（审核端 audit-sonnet）

## 结论
通过。候选补丁忠实于合同 v1 的行为面与「写法钉死」；五份旧门禁只改了合同点名的那几处，没有顺手改别的断言；没有弱化任何测试。战后门禁的白盒与 12 条变异记录可信（12 抓住 / 0 漏 / 0 跳 / 0 错），抽查的失败都落在真断言上，不是收集失败。战后门禁报「候选缺陷：无」，我独立核对后同意。

## 我核了什么
- 合同：`.agent/plans/t058-desktop-web-runtimes-empty-state.v1.md`（Behavior contract、兼容性逐处、写法钉死、DoD、Validation commands）
- 候选补丁：`.agent/runs/t058-desktop-web-runtimes-empty-state/attempt-001/candidate.patch`（9 文件，146 增 / 117 删）与快照源码 `desktop/web/src/pages/RuntimesPage.tsx`、`desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`
- 执行侧材料：`executor-report.md`、`summary.md`、`events-summary.json`、`scope.json`、`checks/01/{V01,V02,V03,V04,G01,R01}.log` 与 `checks.json`
- 战后门禁：`T058-6-gate-post/report.md`、`evidence/whitebox-*.py`、`evidence/mutate-*/mutations.json` 与 M02/M09 日志

## 实现忠实度（逐条对合同）
| 合同条目 | 候选里的样子 | 判定 |
|---|---|---|
| 入口页 children 只渲染 RuntimesView 一行 | `{(data, reload) => (<RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />)}`，前缀与那一行逐字未变 | 合 |
| 删掉整页空态那一支与两个 import | `import { EmptyState } from '../components';` 与 QuizsBlock 的 import 已删；文件里不再出现 `<EmptyState` / `<QuizsBlock` | 合 |
| 保留 isEmpty 与一行式 isRuntimesEmpty | `isEmpty={isRuntimesEmpty}`、`const isRuntimesEmpty = (d: { runtimes: RuntimesData }) => d.runtimes.runtimes.length === 0;` 逐字未动 | 合 |
| api 那一组 import、loadRuntimes、页头两钮、title | diff 里一字未动 | 合 |
| 视图：EmptyState 并进 components 那一行 import | `import { Button, EmptyState, Table, Tag, type TableColumn } from '../../components';`，`import './runtimes-styles.css';` 仍是最后一行 import | 合 |
| 视图：「已登记」节按 runtimes.length === 0 二选一 | 空 → `<EmptyState title=… description=… />`（两段文案逐字同一行）；非空 → 原 `<Table …>` 六属性未动 | 合 |
| 视图：就绪检查节 / QuizsBlock / WriteFlow / 列与 rows 照旧 | diff 里这几块一字未动，只在 `<Section title="已登记">` 里加了三元 | 合 |
| 页面状态仍是 empty | `PageFrame.tsx:167-170` 是 `if (phase === 'empty' && empty)` 才整页空态；入口页不传 `empty`，children 在 empty 阶段照常渲染 | 机制成立 |
| 空态落在「已登记」那一节里 | 视图里 EmptyState 在该节内，Quizs 一块与就绪检查节仍在视图根里 | 合 |
| 不加 CSS、不改组件/壳/mock/api/ts/scripts | 候选里没有这些文件；`scope.json` 记 9 M / 0 新增 / 0 删除 / 0 越界 | 合 |

## DoD 核对（自述 → 实际证据）
- **D01**：视图里空态支的两段文案逐字；证据是战前门禁 `tests/test_gate_t058_baseline.py` 的 S02 与 PROBE_EMPTY（`sec.querySelector('.tt-empty')` 在场、该节无 `table[aria-label="已登记的 runtime"]`）与包内 `page-runtimes-empty.test.tsx` 的 `expectRegisteredEmpty`；V01/G01/R01 全绿。自述 done 属实。
- **D02**：就绪检查节未动，`RuntimeDoctor.tsx:291/297` 的 `disabled={running}` / `disabled={recordRunning}` 空闲即 false；证据是门禁探针按 `disabled === false` 判两钮、包内 `expectReadySection`（两钮在、label「按版本记录核验」在、`input.tt-field__input` 在）、白盒 W04。属实。
- **D03**：`<QuizsBlock quizs={quizs} />` 仍在视图根里；证据是门禁探针的 `quizsSec.closest('[data-page="runtimes"]') === root`、两张 Quizs 表各 2 行、页面级 `.tt-page__error` 为 null，包内 `expectQuizsInRoot` 与 page-quizs.test.tsx 那个 it。属实。
- **D04**：`isEmpty` 与一行式 isRuntimesEmpty 保留 + PageFrame 不传 empty；证据是各层 `data-page-state` 断言为 empty（包内 (a)(b)(c)(d)、门禁探针、t009 D10、t009 TRANS1 的 runtimes/empty 例外）。属实。
- **D05**：有 runtime 时表格支 DOM 逐字未动；证据是 page-runtimes.test.tsx 未改仍绿（V02）、t009/t043/t049/t054/t055/t056/t057 照旧（R01）、白盒 WP1 的 1 条与 2 条边界。属实。
- **D06**：入口页只渲染视图那一行、两个 import 删净；证据是门禁 S01、白盒 W05、t049 S02 新增的「不该再出现 `<EmptyState` / `<QuizsBlock`」、t054 的 KEEP_MARKS 保留项。属实。
- **D07**：五份旧门禁逐 hunk 核对，只改合同点名处；t009 的 diff 只有两处 hunk（`:2914`/`:2919` 与 TRANS1 `:3029`），`:2895-2911`、`:2970-2977` 未动；t056 S09 / t057 S08、page-app.test.tsx:91、readonly2-app.test.tsx:106、page-runtimes.test.tsx 都不在候选里。属实。
- **D08**：包内 (a)(b)(c)(d) 按新口径重写，桩模式 `?mock=empty` 与注入替身各一遍；15 个记号齐备、无 skip/only/todo（门禁 S03 逐 token 查，G01 绿）；page-quizs.test.tsx 那个 it 改成新行为且仍留 `sectionNamed(frame(), 'Quizs')`（门禁 S04）。属实。
- **D09**：`scope.json` 与 candidate.stat 一致（9 个允许文件、0 新增/0 删除）。属实。
- **D10**：V03/V04/V01/V02 全绿；内核自己跑的 R01（t001–t028 + t030–t057 共 56 份，一条命令）1154 passed、0 failed、1111s。属实。

## 门禁端声明的逐条裁定
1. 「其余 7 个改动文件是测试文件，不在变异范围」→ **成立**。这 7 份就是被改的测试本身（两份包内测试 + 五份旧门禁基准），变异它们没有意义；它们删掉的每条旧口径断言都有对应替换或被门禁/白盒/包内测试重新覆盖：t049 S02 删的六项记号 → 改成「有 `<RuntimesView`、没有 `<EmptyState`/`<QuizsBlock`」，文案本身改由 t041 S05 在视图文件里逐字钉；t049 PROBE_EMPTY 删的「EmptyState 直接挂 .tt-page 下」→ 换成「`.tt-empty` 在「已登记」一节里」+「视图根在」；t043 PROBE_PAGE 删的「视图根为 null」→ 换成视图根在 + Quizs 在视图根里；t009 D10/TRANS1 换成视图根在并给 runtimes 的 empty 开例外；t054 删的四项记号本就不存在了。
2. 「M09 的只插入代码 WARN 仍算抓住」→ **成立**：mutations.json 记 M09 caught、exit 1，日志里探针报 `RuntimesView is not defined`，行为真变了。
3. 「M12（丢 reload）行为面观察不到，由 t054 :141 的逐字钉与 W05 静态抓住」→ **成立**：t054 的 KEEP_MARKS 仍含 `<RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />` 逐字，W05 也逐字比对 children 块。
4. 「M11 探针超时不是唯一防线」→ **成立**：W05 静态先红（isEmpty 标记丢）。
5. 「候选缺陷：无」→ **同意**，我独立核对未发现合同违反。

## 执行自述与内核线索的对照
- 内核摘要里 39 条「掩盖退出码」的写法逐条看过：全是 grep / sed / ls / cat 探索命令（标记 check: false），没有一条是检查命令；真正的检查命令都带 `set -o pipefail`。
- `events-summary.json` 的 temp_path_uses / outside_worktree_paths / suspicious_commands / problems 全为空；执行端的 CRLF 统一动作是在工作目录内对自己改过的文件做的字节改写，没往工作目录外写。
- DoD 自述与内核线索逐条对得上，没有「自述完成而无证据」的项。

## 非阻塞意见（不挡，供站主决定）
1. `page-runtimes-empty.test.tsx` 的 (f) 用例被从 `() =>` 改成 `async () =>`，而合同第 4 步写「(e)、(f) 不动」。零功能影响（没有 await），只是范围外的一处噪声；下片若还动这个文件可以顺手改回去。
2. 执行报告写「R01 两批覆盖合同点名的全部 55 份文件」，合同清单实为 56 份（t001–t028 与 t030–t057 各 28）。覆盖没有缺口：内核独立跑的 R01 就是这 56 份一条命令、1154 passed，与执行端两批之和（812 + 342）相同；只是报告里的计数错了一个。
3. t049 探针里两处空态文案仍按 frame 找（`f.querySelector('.tt-empty__title')` / `.tt-empty__desc'`），没限定到「已登记」一节。同一用例紧跟着的 `sec!.querySelector('.tt-empty')` 已把空态钉在该节内，且 DOM 次序上「已登记」在 Quizs 之前，不会误伤；按合同第 4 步的口径这两行本可也限定到该节。
4. 包内 `expectReadySection` 把「就绪检查」一节的按钮文案钉成恰好 `['运行就绪检查', '核验']`，比合同「两钮都在」严。当前 RuntimeDoctor 空闲时正好这两个，成立；将来该节多一个按钮这条会红——更严而非更松。

## 结论
通过。不退回。

Verdict: PASS
