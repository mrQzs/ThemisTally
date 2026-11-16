# 复审记录：t049-desktop-web-runtimes-empty-quizs attempt-001（七端信箱 hub）

- 合同：t049-desktop-web-runtimes-empty-quizs.v1（base 82749c795c8c28cfff5e07150ec4b8e9449ac07b）
- 内核 check --fresh：退出码 0；范围违规 0
- 战后门禁：白盒测试退出码 0；变异检查退出码 0
- JEV：一审前 no_opinion；终审前 no_opinion
- 复审者：audit-sonnet（minimax/MiniMax-M3.1-Flash，思考档位要求 max、生效 max；回合 20261116T020904313682Z-51ca），终审报告如下

## 终审报告

# T049-7 终审报告（audit-sonnet · 审核端）

- 任务：T049-7-audit-post（终审）
- 候选：attempt-001，候选树 `9f4eb9db857f852a100776f1b11cf031ecaa288f`（补丁往返校验：是）
- 合同：`.agent/plans/t049-desktop-web-runtimes-empty-quizs.v1.md`
- 结论：**通过**（无阻塞项）

## 0. 我怎么核的

本端只有只读工具（read/grep/find/ls），工作树里也没有 `desktop/web/node_modules`，因此**没有自己重跑** npm/pytest；行为面的依据是内核在干净工作树里独立跑的检查记录（`checks/01/checks.json`：`mode=fresh`，`candidate_tree=9f4eb9db…`，`tree_before==tree_after`，`modified_by_checks=false`，`unexpected_files_by_checks=[]`）。

1. **逐行读候选源码**：`desktop/web/src/pages/RuntimesPage.tsx`、`desktop/web/index.html`、`desktop/web/tests/page-quizs.test.tsx`、`desktop/web/tests/page-runtimes-empty.test.tsx`；再读它依赖的既有件：`shell/PageFrame.tsx`、`components/EmptyState.tsx`、`pages/readonly1/runtimes-QuizsBlock.tsx`、`pages/readonly1/runtimes-RuntimesView.tsx`、`pages/readonly1/runtimes-quizs-logic.ts`、`pages/readonly1/common-Section.tsx`、`writes/RuntimeForm.tsx`、`api.ts`、`mock/scenario.ts`、`mock/quizs.ts`、`App.tsx`、`shell/PageFrame.css`、`vite.config.ts`。
2. **核内核的检查记录**：`checks/01/checks.json`（G01/V01/V02/V03/R01 全部 `exit_code=0`，`output_must_match` 全部 `matched`）与四份日志。
3. **核战后门禁**：`.agent/mailbox/tasks/T049-6-gate-post/report.md`、白盒测试文件、`evidence/mutate-*/mutations.json`。
4. **核执行报告自述与内核摘要线索是否对得上**（第 5 节）。

## 1. 实现是否忠实于合同

合同 Steps 第 2/3/4/5 步逐条比对，候选是**逐字照抄**（`RuntimesPage.tsx`）：

| 合同要求 | 候选实现 | 判定 |
| --- | --- | --- |
| 加 `import { EmptyState } from '../components';` | `RuntimesPage.tsx:18` | ✓ |
| 加 `import { QuizsBlock } from './readonly1/runtimes-QuizsBlock';` | `RuntimesPage.tsx:20` | ✓ |
| 删掉 `empty={{…}}` 那一行 | 已删（PageFrame 不再收到 `empty`） | ✓ |
| `isEmpty={isRuntimesEmpty}` 照传 | `RuntimesPage.tsx:57` | ✓ |
| `isRuntimesEmpty` 一行不改 | 仍是一行、只谈 `runtimes.length`、以 `;` 收尾、不掺 `quizs` | ✓ |
| children 逐字 `{(data, reload) =>` 开头、三段式 | `RuntimesPage.tsx:65-73`，与合同给的代码块逐字相同 | ✓ |
| `reload={reload}` 保留 | `:61`（页头 AddRuntimeAction）与 `:72`（RuntimesView） | ✓ |
| 两段空态文字留在本文件 | `:68` title/description 逐字 | ✓ |
| 文件头补一句说明、不许出现 t041 禁字 | 已补；全文 grep「已登记运行时／已登记表里加上／；命令写进本机文件／已登记为／ERROR: runtime／改 adapter 要加／登记 runtime／.css」**零命中** | ✓ |
| `index.html` 只改 `<title>` 一行 | `:6` 为 `<title>Themis Tally</title>`，lang/charset/viewport/#root/入口脚本一字未动 | ✓ |
| 新测试覆盖 (a)–(f)、不引依赖、禁用 skip/only/todo | `tests/page-runtimes-empty.test.tsx` 194 行，(a)–(f) 齐 | ✓ |
| `page-quizs.test.tsx` 只改那一个 it | 只改了那一个 it（标题、提示语、加一条断言），其余一字未动 | ✓ |

**行为面的手工核对**（不靠自述，靠读实现）：

- PageFrame 的地基分支确认存在：`PageFrame.tsx` 的 `renderBody()` 里 `phase==='empty' && empty` 成立才换 `EmptyState`，**没传 `empty` 就落到 `children(data, reload)`**；且 empty 态 `setData(env.data)` 后 `data != null`，所以 children 一定被调用。候选正是走这条此前无人使用的分支 —— 与计划端「本片必须在 App 一级钉住它」的要求对上。
- 空态 DOM 形状：children 返回一个 Fragment，`.tt-empty` 与 Quizs 的 `<section>` 都成为 `.tt-page` 的直接子元素（无额外 DOM 包装）→ 满足合同「直接挂在 `.tt-page` 下」「在视图根之外」；视图根仍只由 `RuntimesView` 渲染 → `[data-page="runtimes"]` 仍为 null。
- 间距不是空话：`PageFrame.css` 的 `.tt-page` 确有 `display:flex; flex-direction:column; gap:var(--tt-space-4)` → 空态两块自动拿到 gap，合同「不加任何 CSS」成立（`RuntimesPage.tsx` 未引任何 `.css`）。
- 空态下 `[手动登记…]` 真能干活：`writes/RuntimeForm.tsx` 的 `AddRuntimeAction` 自带 `AddRuntimeDialog` 与 `<WriteFlow>`（对话框在页头渲染，与视图根无关），确认后走 `PageFrame` 的 `request(true)` 重读 —— 即 D05 的「登记成功 → 重读 → data 态」路径，与测试 (d) 走同一条 `request(true)`。这条是我额外核的，合同只说「可点」。
- 读失败语义没被破坏：`loadRuntimes` 仍只让 runtimes 失败整页失败；Quizs 两个信封整体进 `data.quizs`，失败只由 `QuizsBlock` 写「Quizs 跑不起来」/「没能读到 Quizs 的 live 套」/逐套「读不出」。
- 初始标题：`App.tsx` 的运行时改写规则一字未动（仍是「CLI 运行时 · Themis Tally」，陈列页仍「组件陈列 · Themis Tally」）；`index.html` 只是初始标题不再闪「组件陈列」。

**没有发现越界、偷换范围或特判**：补丁只有 4 个文件（`scope.json`：M3 A1，`violations: []`，`warnings: []`），未碰 `PageFrame`/`readonly1/**`/`api.ts`/`mock/**`/`App.tsx`/`components/**`/`writes/**`；`package.json`、`package-lock.json` 字节未动（S03 冻结绿）；没有新依赖、没有新 CSS。

## 2. DoD → 测试 → 断言 映射（每条 DoD 都有出处）

| DoD | 由哪条测试/门禁的哪个断言证明 | 判定 |
| --- | --- | --- |
| D01 空态同时有标题、说明原文、Quizs 一块（两表各 2 行） | 新测试 (a)：`data-page-state==='empty'`、`.tt-empty__title`/`.tt-empty__desc` 逐字相等、`sectionNamed(frame(),'Quizs')` 存在、两张 `aria-label` 表 `tbody tr` 各 2 行；G01 empty 探针两条（EmptyState `parentElement===.tt-page`、两表各 2 行且含 stepfun/就绪） | 证明得了 |
| D02 空态下 Quizs 读失败只坏这一块 | 新测试 (b) `?mock=empty&quizs=broken`：状态仍 empty、区块含「Quizs 跑不起来」、live 每行含「读不出」、无 `.tt-page__error`；(c) 注入 providers 失败（含 E-ONE）、无页面级出错块；G01 empty 探针对应两条 | 证明得了（各情景 expired/missing/empty 在空态下没有单独用例，见第 6 节建议项） |
| D03 有 runtime 时逐字不变 | data 支仍是同一句 `<RuntimesView runtimes=… quizs=… reload=… />`；G01 states 探针（data 态、视图根内「已登记」「就绪检查」在前、Quizs 在其后且在视图根内、页头三钮与[扫描 PATH]禁用）；R01 999 passed；`page-quizs`/`page-runtimes` 既有断言未动 | 证明得了 |
| D04 empty 态、视图根 null、Quizs 块挂 `.tt-page` 下、无新 CSS | 新测试 (a) 的 `pageRoot()` 为 null；G01 empty 探针 `sec.parentElement === f`（.tt-page）且 `sec.closest('[data-page="runtimes"]')` 为 null；S02 静态「不引 .css」 | 证明得了 |
| D05 空态可点[手动登记…]、重读后按 data 态显示 | 新测试 (a) `buttons[1].disabled===false`、三钮次序 `['扫描 PATH','手动登记…','刷新']`；(d) 注入替身先空后有点[刷新] → `data-page-state==='data'`、视图根出现、`sec.closest('[data-page="runtimes"]')===root` | 证明得了（另手工核了 AddRuntimeAction 自带对话框，见第 1 节） |
| D06 index.html 初始标题 | 新测试 (f) 读文件断言含 `<title>Themis Tally</title>` 且不含「组件陈列」；S01 静态；W03；M9 变异被抓住；G01 states 探针钉运行时 `document.title==='CLI 运行时 · Themis Tally'` | 证明得了 |
| D07 静态红线一条不破 | S02（`isEmpty={isRuntimesEmpty}` 照传、不传 empty、`loadRuntimes`/`isRuntimesEmpty` 命名的模块级 const、`isRuntimesEmpty` 一行只谈长度不掺 quizs 且以 `;` 收尾、children 前缀正则、`reload={reload}`、两段文字逐字、两条引入、禁字表、无 .css）；R01 999 passed | 证明得了 |
| D08 新测试在 App 一级钉住 empty 分支 | 新文件挂整个 App（`import App from '../src/App'`），(a)–(f) 覆盖 `?mock=empty`、`?mock=empty&quizs=broken`、注入失败、先空后有、loading/error、初始标题；W05 + S04 记号齐备；两个文件均无 skip/only/todo | 证明得了 |
| D09 既有测试没被删/跳过/弱化 | 唯一改动是 `page-quizs.test.tsx` 那一个 it：旧断言 `expect(pageRoot(), …).toBeNull()` **保留**（只换提示语）并新增 `sectionNamed(frame(),'Quizs')`；内核摘要「删除了 1 行含断言的代码（新增 43 行）」对上这行被替换的断言（替换后语义更强，不是弱化）；t043 `:149-158` 的 12 个记号我逐个 grep 过，全在；`page-app`/`readonly2-app`/`page-runtimes`/`writes-remove` 一字未改；门禁文件未改 | 证明得了 |
| D10 范围与依赖 | `scope.json` 4 文件全 in_scope、0 越界；S03 依赖字节冻结（820/108793 字节的 sha256 基线值）绿；未碰 `PageFrame`/`readonly1`/`api.ts`/`mock`/`App.tsx`/`components`/`writes`/`shell`；无新依赖、无新 CSS | 证明得了 |

## 3. 测试是不是「空心」的（不靠全绿，靠看断言打在什么上）

- **不是空心基线**：新测试的每条断言都打在真实 DOM/状态上：`data-page-state`、`.tt-empty__title`/`.tt-empty__desc` 文本、`section[aria-labelledby]` 指向的 h2 标题、`table[aria-label]` 的 `tbody tr` 计数、`.tt-page__error` 是否存在、`.tt-page__actions` 里按钮的 disabled。失败会落在断言上，不是「文件不存在/导入失败」。
- **唯一读源文件文本的断言是 (f)（index.html 标题）**：这不是空心断言。index.html 是 vite 的入口 HTML（`vite.config.ts` 的 root 就是 `desktop/web`，构建产物 `dist/index.html` 由它生成），标题不是构建期模板变量；「文件里逐字是 `<title>Themis Tally</title>`」+ V03 构建通过 + t002 G1/G6 的 lang/脚本门禁，就等于「文件接进了应用」的证明；再加 states 探针钉运行时改写仍在。**不退回门禁端**。
- **门禁文件集成后仍绿，不会误伤**：`tests/test_gate_t049_baseline.py` 的 S01/S02/S03/S04 都是对候选内容的静态断言，P2 只比较**同一次流水线前后**的 `git status`（不是「相对基线的改动范围断言」），D 类是行为探针；白盒 `tests/test_gate_t049_whitebox.py` 也是纯结构断言。它们留在仓库当回归测试是安全的。**不退回门禁端**。
- **没有共享页面上的全局否定断言**：新测试只断言「本页面自己的东西在/不在」（视图根为 null、Quizs 区块在 frame 里），别片加东西不会误伤。

## 4. 战后门禁记录的裁定

- **等价变异**：门禁端声明「无 equivalent、无 expect_missed、无 unmutated」，`mutations.json` 的 `counts` 为 caught 12 / missed 0 / skipped 0 / error 0，`counts_by_command.W1.unexpected_missed=[]`、`unexpected_caught=[]`。逐条看 12 条变异（M1/M2 删两条引入、M3 条件取反、M4 丢 description、M5 QuizsBlock 的 quizs 改 undefined、M6 去掉 isEmpty、M7 RuntimesView 丢 reload、M8 QuizsBlock 挪进 data 支、M9 标题退回、M10 viewport 砍短、M11 入口脚本改相对路径、M12 lang 改 en）**每条都是真实缺陷**，没有一条是「改了但行为不变」的假变异；也没有被声明成等价而实际能测出来的。**判定：门禁端记录属实。**
- **M3 的「insertion_only」提示**：变异把 `isRuntimesEmpty(data) ? (` 换成 `!isRuntimesEmpty(data) ? (`，新串包含旧串，所以变异工具给出「插入式」的告警。白盒 W01 用锚定正则 `\{\(data, reload\) =>\s*isRuntimesEmpty\(data\) \? \(` 与 `"!isRuntimesEmpty" not in code` 抓住它，不是靠子串蒙对的假阳性。**判定：抓住属实。**
- **「没法变异的改动文件」**：两个测试文件（`page-quizs.test.tsx`、新测试）按惯例不打变异，内容由 W04/W05 + 基准 S04 钉住，并由 V01 真正执行。**判定：这两个文件确实不必打变异。**
- **白盒测试的定位**：门禁端本端无 node_modules，白盒只能做静态结构断言，行为面交给基准探针；我核对后认为这个分工站得住（基准探针在装好依赖的树上由内核独立跑过，G01 8 passed 含两条探针）。**判定：战后门禁够用，不退回。**
- **门禁端没有举证的候选缺陷**（本回合输入无「门禁端举证的候选缺陷」一节，其报告也写明无 candidate_defects）。

## 5. 执行报告自述 vs 内核摘要线索（逐条对上）

| 内核摘要线索 | 执行报告自述 | 核对结果 |
| --- | --- | --- |
| 「删除了 1 行含断言的代码（新增 43 行）」 | D09「只改 page-quizs 那一个 it（标题、提示语、加一条新断言）」 | 对上：那 1 行就是被替换的 `expect(pageRoot(), '空态不渲染视图，Quizs 一块也就看不到').toBeNull()`，新行是同一断言换提示语并**追加**一条断言 —— 不是弱化 |
| 「掩盖退出码的写法：`npm ci … 2>&1 \| tail -n 20`」 | 报告把 `npm ci` 写进「自检命令」段，但 JSON 的 `self_checks` 只有 V01/V02/V03/G01/R01 五条真实退出码 | 对上：那条是**装机准备**不是检查命令；npm test 若缺依赖会立刻红；内核又在干净工作树（依赖已就位）独立重跑了 5 条检查，全绿。不影响结论 |
| 「新增被 Git 忽略的路径：.pytest_cache/、desktop/web/dist/、node_modules/…」 | 报告「`node_modules` 原本缺失，已按锁文件 `npm ci`」 | 对上：这些都在 `.gitignore`（`desktop/**/node_modules/`、`desktop/**/dist/`）或由 pytest 自带的 `.pytest_cache/.gitignore`（内容 `*`）自忽略；`scope.json` 越界 0 |
| 「运行期间规划路径有变化：`.agent/plans/t044-desktop-web-hub-bind.v4.*`」 | 报告未提 | 不算自述不实：这是**规划端**在主工作区写的另一任务的文件，不在候选补丁（4 个 desktop/web 文件）里，也不在候选树里 |
| 「执行器自行宣布了 2 处解读」 | 报告 `interpretations` 只有 1 条（(f) 读 index.html 用 `resolve(process.cwd(), …)`），另两条是 `contract_conflicts: []`、`unresolved_questions: []` | 第 1 条解读与合同第 4 步 (f) 并列允许的写法一致（合同的另一种写法在本机 vitest+jsdom 下不可用），已在 W05 里钉住；另一条应是被核归到「执行说明」类的自述（合同第 4 步 (f) 的备选写法说明），**不构成自述不实** |
| JEV 判断 | 6j-jev 报告为 `no_opinion auth_failed` | 本回合**没有独立的 JEV 信号**，本审核的依据是我逐行读的源码 + 门禁记录 + 内核独立检查记录 |

## 6. 不挡的意见（建议类，不进阻塞项）

1. **空态下 Quizs 的 expired/missing/empty 三个情景没有单独用例**。D02 写的是「各情景与有运行时时一样」；现在空态与 data 态共用同一个 `QuizsBlock`、同一份信封，行为按构造一致，(b)/(c) 也钉住了 broken 与注入失败。若站主要求更严，可各补一条空态用例（约 10 行）；不需要在本片返工。
2. **(f) 依赖 vitest 的 cwd = `desktop/web`**（`npm test` 的工作目录）。若哪天从仓库根直接跑 vitest，这条会因读不到 `index.html` 而**报错**（不是静默通过），属于响亮的失败，可以接受。
3. **桌面外壳主窗口标题仍是 `"ThemisTally"`**（`desktop/shell/main.js:85`，无空格），与 App 的「· Themis Tally」写法不一致。合同写明本片不改外壳，记一笔留给外壳那一片。
4. **工作树里还留着门禁端的两件工件**：`tests/test_gate_t049_whitebox.py`（门禁文件，按仓库惯例应入库）与 `mutation-spec.json`（回合工件，`.gitignore` 未忽略它）。合并时别把 `mutation-spec.json` 带进提交（见交付信「下游须知」）。

## 7. 结论

实现忠实于合同，范围没有扩大，测试钉得住且没有弱化既有断言，内核独立复跑与战后门禁的变异记录都成立，**不挡的意见只有 4 条建议**。

**结论：通过。退回：无。阻塞项：无。**

Verdict: PASS
