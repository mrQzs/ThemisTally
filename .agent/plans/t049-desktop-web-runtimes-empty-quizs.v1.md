# TASK: t049-desktop-web-runtimes-empty-quizs

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 82749c795c8c28cfff5e07150ec4b8e9449ac07b
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: cc-switch-step-fun/step-5-preview · thinking high

## Goal
CLI 运行时页一个 runtime 都没登记时，页面上同时有 T041 定下的空态（标题「还没有登记的 runtime」与说明原文）与一块「Quizs」（提供方档案表与 live 套表；它的读取中、读失败、各情景与有运行时时完全一样，读失败只在区块里显示）；有运行时时页面一个字不变；页头 [手动登记…] 在空态下照样能用，重读之后按有运行时的样子显示。另把 `desktop/web/index.html` 的初始 `<title>` 改成 `Themis Tally`。

## Non-goals
- 不改 `PageFrame` 的接口与行为（九个页面共用，能不动就不动）；不新增 `PageFrame` 属性。
- 不改 `desktop/web/src/pages/readonly1/**`（Quizs 区块、RuntimesView、纯函数、CSS 一律不动）。
- 不改 `desktop/web/src/api.ts`、`desktop/web/src/mock/**`、`desktop/web/src/components/**`、`desktop/web/src/writes/**`、`desktop/web/src/live/**`、`desktop/web/src/App.tsx`、`desktop/web/src/shell/**`。
- 不改 `desktop/web/package.json` 与 `package-lock.json`，不新增或升级依赖，不加 CSS。
- 不改 `ts/packages/ui` 与内核；不改 `desktop/shell`（主窗口 `options.title` 是 "ThemisTally"，留给以后外壳那一片）。
- 不放宽任何门禁断言，不改任何 `tests/test_gate_*.py`；不删、不跳过、不弱化既有测试。
- 不做资格认证、续期、凭据录入；不给空态下的 Quizs 区块加按钮。

## Repository facts
以下事实在基线 `618196a2ef607174e4a242fbb422b73d49a9aa91` 的工作目录里逐行核对过（本回合只读探查，没有运行 npm/pytest）。
- 入口与现状：
  - `desktop/web/src/pages/RuntimesPage.tsx`（66 行）：`:16-41` 的 `loadRuntimes` 用 `Promise.all([getRuntimes(), getQuizsProviders(), getQuizsLive()])` 并行读三条，只有 runtimes 失败才整页失败；`:43` 的 `isRuntimesEmpty` 是一行 const（`d.runtimes.runtimes.length === 0`，以 `;` 收尾）；`:45` 起是页面组件：`:50` `title="CLI 运行时"`、`:54` `isEmpty={isRuntimesEmpty}`、`:55` `empty={{ title: '还没有登记的 runtime', description: '用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）' }}`、`:57-60` 页头 [扫描 PATH]（DisabledAction）与 [手动登记…]（AddRuntimeAction）、`:63` `{(data, reload) => <RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />}`。
  - `desktop/web/src/shell/PageFrame.tsx`：`:84-88` 读成功后 `isEmpty` 为真时照样 `setData(env.data)` 并 `setPhase('empty')`（数据不为 null）；`:167-170` 渲染时 `phase === 'empty' && empty` 成立才换成 `EmptyState`，**没传 `empty` 就落到 `children(data, reload)`**（`<>{data != null ? children(data, reload) : null}</>`）。`empty` 属性是可选的（`:28`）。
  - 这条「empty 态不传 `empty` 时渲染 children」的分支目前**没有任何页面在用、也没有测试钉住**：`grep 'isEmpty={' desktop/web/src` 只有 7 处，每处都同时传了 `empty`。本片的新测试必须在 App 一级钉住它。
- 可用的现成件：
  - `desktop/web/src/components/index.ts:45` 导出 `EmptyState`（`desktop/web/src/components/EmptyState.tsx`：props 为 `icon?`/`title`/`description?`/`action?`，标题渲染成 `<p class="tt-empty__title">`，说明成 `<p class="tt-empty__desc">`；`EmptyState.css` 没有 `flex:1`/`min-height`）。
  - `desktop/web/src/pages/readonly1/runtimes-QuizsBlock.tsx`：`QuizsBlock({ quizs })`，`quizs` 形状是 `{ providers: Envelope<QuizsProvidersData>; live: Envelope<QuizsLiveData> }`；用 `Section title="Quizs"` 摆（`common-Section.tsx`：`<section aria-labelledby>` + h2 标题）；两张表 `aria-label` 分别是「Quizs 提供方档案」「Quizs live 套」；providers 失败写「Quizs 跑不起来」，live 失败写「没能读到 Quizs 的 live 套」；空列表写「还没有 Quizs 提供方档案」「还没有 Quizs live 套」；区块里没有按钮、没有 `role=status`、没有内联 style。
  - `desktop/web/src/pages/readonly1/runtimes-RuntimesView.tsx`：视图根是 `<div className="rt" data-page="runtimes">`，依次是「已登记」「就绪检查」两节、`QuizsBlock`、`WriteFlow`。
  - `desktop/web/src/api.ts`：`:386-391` 的 `read(command, produce)` 里只有 `loading`（挂起）与 `error`（错误信封）优先于情景；`:499-505` `getRuntimes`；`:507-520` `getQuizsProviders`/`getQuizsLive`（桩模式走 `read()`，`?mock=empty` 不影响这两个读函数）。
  - `desktop/web/src/mock/scenario.ts:8-18` 只认查询串里的 `mock` 键；`desktop/web/src/mock/quizs.ts:60-73` 只认 `quizs` 键——两个键各自独立解析，`#/runtimes?mock=empty&quizs=broken` 两个都生效。
  - `desktop/web/src/live/mode.ts:33-35` 的 `setLiveClientForTests(client)` 可注入替身 client（`desktop/web/tests/page-quizs.test.tsx` 已有用法）。
  - `desktop/web/index.html:6` 是 `<title>Themis Tally · 组件陈列</title>`；`desktop/web/src/App.tsx:58-63` 挂载后把 `document.title` 改成「<页面标题> · Themis Tally」（陈列页写「组件陈列 · Themis Tally」）。
  - `desktop/web/package.json`：`npm test` = `vitest run`，`npm run typecheck` = `tsc --noEmit`，`npm run build` = `tsc --noEmit && vite build`；`desktop/web/vite.config.ts` 的 `test.include` 收 `tests/**/*.test.{ts,tsx}`（环境 jsdom）。
- 门禁事实（逐条读过原文；方案丁之下没有一条要放宽）：
  - `tests/test_gate_t009_baseline.py:866-891` 页面接线：`load` 与 `isEmpty` 必须是命名的模块级函数（`isEmpty` 的取值正则 `\s*[A-Za-z_$][\w$]*\s*`）、文件里要有 `readonly1/`、从 `'../api'` 只能引入白名单里的读函数。`:2897-2921` D10：`?mock=empty`（注入空数组）下 `data-page-state` 是 `empty`、页面文字含「还没有登记的 runtime」、**视图根 `[data-page="runtimes"]` 为 null**。`:3019-3044` TRANS1：`#/runtimes?mock=empty` 下是 empty 态、根为 null、有标题。`:3281-3283` 与 `:3808-3816`：WATCHED 名单里含 `index.html`，但比的是**流水线前后**的摘要，不与基线比，改标题不红。
  - `tests/test_gate_t041_baseline.py:137` 的 `EMPTY_DESC = "用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）"`；`:319-333` S05：这段说明与标题「还没有登记的 runtime」必须仍在 `RuntimesPage.tsx` 里；`:127-134` 的 `BAD_ENTRY_TEXTS`（「已登记运行时」「已登记表里加上」「；命令写进本机文件」「已登记为」「ERROR: runtime」「改 adapter 要加」等）与「登记 runtime」不许出现在入口文件里。
  - `tests/test_gate_t043_baseline.py:419-465` S03：`loadRuntimes`/`isRuntimesEmpty` 仍是命名的模块级函数、`isRuntimesEmpty` 仍只看 `runtimes.length` 且不掺 `quizs`、children 正则 `\{\(data, reload\)\s*=>`、页头与「还没有登记的 runtime」保留；`:276-292` 的 `_statement` 切片按「第一个分号或下一条声明」截——`isRuntimesEmpty` 必须仍是一行并以 `;` 收尾，否则 JSX 里的 `quizs={data.quizs}` 会被吞进切片而误报；`:149-158` 的 `EXECUTOR_TEST_TOKENS` 列出 `page-quizs.test.tsx` 必须留住的记号；`:612-683` S08 查这些记号与 skip/only/todo；`:1057-1073` 的五态探针里 `:1069` 那句提示语「空态不渲染视图，Quizs 一块也就看不到」与新行为相反，但它断言的「视图根为 null」仍成立，不会红。
  - `tests/test_gate_t023_baseline.py:319-328` S10：children 形如 `(data, reload)`，且文件里要有 `reload={reload}`。
  - `tests/test_gate_t002_baseline.py:628-640` G1 与 `:802-814` G6 只钉 lang、脚本、样式与外部资源，**不钉标题**。
  - `tests/test_gate_t006_baseline.py:2014-2087` EMPTIES：`?mock=empty` 下各页是 empty 态、页面文字含各自的空态标题，且不含「夹具数据已读到」。
- 已核实的仓库外事实：无。本片不涉及依赖包的文件、版本、许可或体积；`npm ci`（若需要）只按现有锁文件装，不改依赖清单。

## Scope
- allowed_modified_files:
  - desktop/web/src/pages/RuntimesPage.tsx
  - desktop/web/index.html
  - desktop/web/tests/page-quizs.test.tsx
- allowed_new_files:
  - desktop/web/tests/page-runtimes-empty.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_gate_t049_*.py
  - tests/test_gate_*.py
  - desktop/web/src/shell/**
  - desktop/web/src/pages/readonly1/**
  - desktop/web/src/pages/readonly2/**
  - desktop/web/src/components/**
  - desktop/web/src/writes/**
  - desktop/web/src/live/**
  - desktop/web/src/mock/**
  - desktop/web/src/api.ts
  - desktop/web/src/App.tsx
  - desktop/web/src/App.css
  - desktop/web/src/shellpages/**
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/tests/page-app.test.tsx
  - desktop/web/tests/readonly2-app.test.tsx
  - desktop/web/tests/page-runtimes.test.tsx
  - desktop/web/tests/writes-remove.test.tsx
  - ts/packages/ui/**
  - scripts/**
  - 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh
- dependency_changes: forbidden（不新增、不升级、不删依赖；package.json 与 package-lock.json 一个字节都不动）

## Behavior contract
- 正常输入：
  - 有 runtime（`runtimes.runtimes` 非空）：页面与现在**逐字一致**——`data-page-state="data"`、`[data-page="runtimes"]` 里依次是「已登记」「就绪检查」「Quizs」三节，页头 [扫描 PATH]（禁用）、[手动登记…]、[刷新] 不变。
  - 没有 runtime（`runtimes.runtimes` 是空数组）：`data-page-state` 仍是 `empty`；页面正文里同时有
    - 空态：`EmptyState` 的 title 逐字是「还没有登记的 runtime」、description 逐字是「用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）」；
    - 「Quizs」一块：`QuizsBlock`，形状与有运行时时**完全一样**（同一套表、同一套文案、同一套错误显示）。
  - 空态下 `[data-page="runtimes"]`（视图根）**仍为 null**：视图根只由 `RuntimesView` 渲染，空态不渲染视图。
  - 空态下「Quizs」区块直接挂在 `.tt-page` 下（**在 `[data-page="runtimes"]` 之外**）；间距靠 `.tt-page` 自己的 gap，**不加任何 CSS**。
  - 页头 [手动登记…] 在空态下照样能点（它由 `AddRuntimeAction` 渲染在页头，与页面状态无关）；登记成功或点 [刷新] 之后重读，若此时有 runtime，页面按 data 态显示（视图根出现，Quizs 区块在视图根内）。
  - `desktop/web/index.html` 的初始标题逐字是 `<title>Themis Tally</title>`；`App.tsx` 挂载后改写 `document.title` 的行为不变。
- 边界输入：
  - `?mock=empty`（桩模式）：runtimes 读回空数组，Quizs 两个读照常给出 ok 信封（两个键各自独立解析，`?mock=empty` 不影响 Quizs 读）。
  - `?mock=empty&quizs=broken`：runtimes 仍空；providers 信封失败（区块顶部写「Quizs 跑不起来」与命令、退出码、messages），live 两套状态写「读不出」；**页面级出错块（`.tt-page__error`）不出现**，页面状态仍是 `empty`。
  - `?mock=loading`：整页挂起，`data-page-state="loading"`，没有 Quizs 区块。
  - `?mock=error`：整页出错，`data-page-state="error"`，页面级出错块照旧写命令与退出码，没有 Quizs 区块。
  - `?mock=offline`：仍是 data 态（断线保留旧数据），Quizs 区块照常。
  - Quizs 读失败（任一信封坏）：失败只写在区块里，页面其余照旧；runtimes 读失败：整页出错（这条不变）。
- 错误与重试：不新增重试、不新增错误分支。Quizs 两个读失败只影响区块（与 T043 一样）；runtimes 读失败仍整页出错；空态下不出现页面级出错块。
- 并发、取消与状态变化：不适用——本片没有取消、没有并发写；三个读仍是一次性并行（`Promise.all`），渲染顺序固定（空态：EmptyState → Quizs；data 态：已登记 → 就绪检查 → Quizs）。重读（[刷新] 或写成功后的 reload）走 `PageFrame` 既有的 `request(true)`。
- 兼容性：`PageFrame` 的 props 与行为一个字不改（`empty` 是可选属性）；`QuizsBlock` 的 props、`RuntimesView` 的 props、`api.ts` 的导出、`mock/` 的夹具、`App.tsx`、`components/` 都不改；`index.html` 只改 `<title>` 那一行；`document.title` 的运行时改写规则不变。

## Steps
1. 读 Repository facts 里的文件，确认签名与本基线一致；不一致就停下并报告（不要自己改事实）。
2. **`desktop/web/src/pages/RuntimesPage.tsx`**（改动约 15 行）：
   - 加两个引入：`import { EmptyState } from '../components';`（照 `PageFrame.tsx:6` 的引法）与 `import { QuizsBlock } from './readonly1/runtimes-QuizsBlock';`。
   - **删掉** `:55` 的 `empty={{ title: '还没有登记的 runtime', description: '用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）' }}` 这一行（空态改由本页自己摆）。
   - `:54` 的 `isEmpty={isRuntimesEmpty}` **照传**（不改名、不内联）。
   - `:43` 的 `isRuntimesEmpty` **一行不改**（仍以 `;` 收尾、仍只谈 `runtimes.length`、不掺 `quizs`）。
   - `:63` 的 children 改成下面这段（**写法照抄，别自己另起炉灶**）：
     ```tsx
     {(data, reload) =>
       isRuntimesEmpty(data) ? (
         <>
           <EmptyState title="还没有登记的 runtime" description="用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）" />
           <QuizsBlock quizs={data.quizs} />
         </>
       ) : (
         <RuntimesView runtimes={data.runtimes.runtimes} quizs={data.quizs} reload={reload} />
       )
     }
     ```
     必须满足的写法约束（静态门禁按字面查，写歪了就红）：
     - children 的开头逐字是 `{(data, reload) =>`（逗号后**恰好一个空格**；t043 `:463` 的正则 `\{\(data, reload\)\s*=>`）；
     - 文件里保留 `reload={reload}`（t023 `:328` 按字面查；data 那一支的 `RuntimesView` 上有它，页头 `AddRuntimeAction reload={reload}` 也在）；
     - `loadRuntimes` 与 `isRuntimesEmpty` 仍是命名的模块级函数（t009 `:876-883`）；
     - 两段空态文字仍写在**这个文件**里（t041 `:137`/`:319-333`、t043 S03）；
     - 文件头注释补一句说明「空态也摆 Quizs 一块」，但**不许出现**「已登记运行时」「已登记表里加上」「；命令写进本机文件」「已登记为」「ERROR: runtime」「改 adapter 要加」「登记 runtime」这些字样（t041 `:127-134`），也别写内核报错原文。
3. **`desktop/web/index.html`**：把 `:6` 的 `<title>Themis Tally · 组件陈列</title>` 改成 `<title>Themis Tally</title>`；**只改这一行**，lang、script、style、viewport 一个字都不动（t002 G1/G6）。
4. **新测试 `desktop/web/tests/page-runtimes-empty.test.tsx`**（约 100–150 行；文件头写一句说明这是「空态也显示 Quizs 一块」的用例）。写法照 `desktop/web/tests/page-quizs.test.tsx`（`mount`/`flush`/`frame`/`pageRoot`/`sectionNamed`/`tableOf`/`rowsOf` 这几个小助手可以照抄或改名字；`sectionNamed` 找的是 `section[aria-labelledby]` 指向文字为该标题的 h2 的元素）。至少覆盖这些用例：
   - (a) `#/runtimes?mock=empty`：`frame()` 的 `data-page-state` 是 `empty`；页面文字含「还没有登记的 runtime」与说明原文「用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）」；`[data-page="runtimes"]` 为 null；**frame 里**有名叫「Quizs」的 section（用 `sectionNamed(frame(), 'Quizs')`，不要用 `quizsSection()`——它要求视图根存在）；区块里有 `aria-label="Quizs 提供方档案"` 与 `aria-label="Quizs live 套"` 两张表，各 2 行；页面上没有 `.tt-page__error`；页头动作次序是 [扫描 PATH]、[手动登记…]、[刷新]，[手动登记…] 可点（`disabled` 为 false）。
   - (b) `#/runtimes?mock=empty&quizs=broken`：`data-page-state` 仍是 `empty`；标题与说明仍在；区块里写「Quizs 跑不起来」与 live 那一半的「读不出」；**没有** `.tt-page__error`。
   - (c) 注入替身 client（`setLiveClientForTests`，写法照 `page-quizs.test.tsx` 的 `clientWith`）：runtimes 读回空数组、providers 读失败 → 页面状态是 `empty`，失败只写在区块里（「Quizs 跑不起来」），没有页面级出错块。
   - (d) 注入替身 client：runtimes 第一次读回空数组、第二次读回一条（替身对同一路径按次数给不同信封）；点页头的 [刷新] 之后 → `data-page-state` 变成 `data`，`[data-page="runtimes"]` 出现，Quizs 区块在视图根内。（[刷新] 与写成功后的 reload 走同一条 `request(true)`。）
   - (e) `#/runtimes?mock=loading` → 状态 `loading`、没有 Quizs 区块；`#/runtimes?mock=error` → 状态 `error`、有页面级出错块、没有 Quizs 区块。
   - (f) 初始标题：读 `desktop/web/index.html` 的文本，断言含 `<title>Themis Tally</title>` 且不含「组件陈列」。jsdom 不加载 index.html，用 `readFileSync` 读文件：`readFileSync(new URL('../index.html', import.meta.url), 'utf8')`（或 `resolve(process.cwd(), 'index.html')`；vitest 的 cwd 是 `desktop/web`）。
   - 新测试里不用 `skip`/`only`/`todo`；不用 `describe.skip` 之类；不引入新依赖。
5. **`desktop/web/tests/page-quizs.test.tsx`**：只许改 `'?mock=loading 挂起（三个读一起等）、?mock=empty 空态不渲染视图'` 那**一个** `it`（文件里 `:182-190` 附近）：
   - 保留两条既有断言（`data-page-state` 是 `empty`、`pageRoot()` 为 null）；
   - 把提示语「空态不渲染视图，Quizs 一块也就看不到」改成与新行为一致的写法（例如「空态不渲染视图（Quizs 一块在视图根外）」）；
   - 加一条新断言：`sectionNamed(frame(), 'Quizs')` 存在（**用 `sectionNamed(frame(), …)`，不要用 `quizsSection()`**，后者要求视图根存在）；
   - it 的标题相应改（例如「?mock=loading 挂起（三个读一起等）、?mock=empty 空态不渲染视图但 Quizs 一块照常」）。
   - 文件里其余部分**一行不改**：t043 `:149-158` 的记号 token（`Quizs 提供方档案`、`Quizs live 套`、`Quizs 跑不起来`、`读不出`、`quizs live status 失败（退出码 127）`、`看这一套自己的问题`、`已过期`、`缺 qualification.json`、`还没有 Quizs`、`button`、`quizs=`、`getRuntimes`）一个都不能少，`formatLocalUtc`/`UTC` 的时刻写法也不许动。
6. 自检：依次跑 Validation commands 里的 V01、V02、V03，再跑 R01（门禁回归较慢，放最后跑一次）；`desktop/web/node_modules` 若不存在，先按现有锁文件跑 `npm ci --no-audit --no-fund`（**不改 package.json 与 package-lock.json**；需要网络，装不上就停下报告）。
7. 写执行报告；遇到合同未定义的行为（例如 PageFrame 的 empty 分支与本文件写的对不上），停下并报告，不要改范围外的文件，也不要为了变绿去改 `tests/test_gate_*.py`。

## Validation commands
必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。

- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t049_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm test` · cwd：desktop/web · 超时：900s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V02（必要）：`npm run typecheck` · cwd：desktop/web · 超时：300s · 期望退出码：0
- V03（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py tests/test_gate_t014_baseline.py tests/test_gate_t015_baseline.py tests/test_gate_t016_baseline.py tests/test_gate_t017_baseline.py tests/test_gate_t018_baseline.py tests/test_gate_t019_baseline.py tests/test_gate_t020_baseline.py tests/test_gate_t021_baseline.py tests/test_gate_t022_baseline.py tests/test_gate_t023_baseline.py tests/test_gate_t024_baseline.py tests/test_gate_t025_baseline.py tests/test_gate_t026_baseline.py tests/test_gate_t027_baseline.py tests/test_gate_t028_baseline.py tests/test_gate_t030_baseline.py tests/test_gate_t031_baseline.py tests/test_gate_t032_baseline.py tests/test_gate_t033_baseline.py tests/test_gate_t034_baseline.py tests/test_gate_t035_baseline.py tests/test_gate_t036_baseline.py tests/test_gate_t037_baseline.py tests/test_gate_t038_baseline.py tests/test_gate_t039_baseline.py tests/test_gate_t040_baseline.py tests/test_gate_t041_baseline.py tests/test_gate_t042_baseline.py tests/test_gate_t043_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`

## Definition of done
- D01：一个 runtime 都没登记时，页面上同时有标题「还没有登记的 runtime」、说明原文「用页头的[手动登记…]登记运行时：填运行时 ID、适配器与命令（可选）」与「Quizs」一块（提供方档案表与 live 套表各 2 行）；证据：V01、G01；目的：刚装好、还没登记 CLI 的机器要能先看到 Quizs 装没装好、批准了哪些提供方。
- D02：Quizs 区块在空态下的读取中、读失败与各情景与有运行时时一样（`?quizs=broken` 时只有区块写「Quizs 跑不起来」与 live 的「读不出」，页面级不出错块）；证据：V01、G01；目的：读失败只坏这一块，页面其余照常。
- D03：有 runtime 时页面逐字不变（data 态、视图根内三节次序、页头两钮与 [刷新]、表内容）；证据：V01、R01；目的：不给已有用法添乱。
- D04：空态下 `data-page-state` 仍是 `empty`、`[data-page="runtimes"]` 仍为 null；空态的 Quizs 区块直接挂在 `.tt-page` 下（不在视图根内），没有新增 CSS；证据：V01、G01、R01；目的：视图根与页面状态的语义不变，空态的区块不混进视图。
- D05：页头 [手动登记…] 在空态下可点；重读（[刷新] 或登记成功后的 reload）后若有 runtime，页面按 data 态显示（视图根出现、Quizs 区块在视图根内）；证据：V01；目的：空态不是死路，登记完就回到正常样子。
- D06：`desktop/web/index.html` 的初始标题逐字是 `<title>Themis Tally</title>`（文件里不再有「组件陈列」），挂载后 `document.title` 仍按页面由 `App.tsx` 改写；证据：V01、G01、R01；目的：加载那一下不再闪出「组件陈列」。
- D07：静态红线一条不破：`loadRuntimes`/`isRuntimesEmpty` 仍是命名的模块级函数；`isRuntimesEmpty` 仍是一行、只谈 `runtimes.length`、不掺 `quizs`；children 仍逐字以 `{(data, reload) =>` 开头；`reload={reload}` 仍在；`isEmpty={isRuntimesEmpty}` 照传；两段空态文字仍在 `RuntimesPage.tsx`；`RuntimesPage.tsx` 不出现 t041 的禁字表与「登记 runtime」；证据：V01、G01、R01；目的：这些是 T009/T023/T041/T043 的长期门禁，写歪了会红。
- D08：新测试在 App 一级钉住「empty 态不传 `empty` 时 PageFrame 渲染 children」这条分支（此前没有任何测试钉住它），并覆盖 `?mock=empty`、`?mock=empty&quizs=broken`、注入失败、先空后有、`?mock=loading`/`?mock=error`、初始标题；新测试不用 skip/only/todo；证据：V01、G01；目的：这条分支是本片行为的地基，必须有测试护住。
- D09：既有测试没被删、跳过或弱化：`desktop/web/tests/page-quizs.test.tsx` 只许改那一个 `it`（标题、提示语、加一条新断言），t043 `:149-158` 的记号一个不少；`page-app.test.tsx`、`readonly2-app.test.tsx`、`page-runtimes.test.tsx`、`writes-remove.test.tsx` 一字不改；门禁测试文件一个不改（`tests/test_gate_t049_*.py` 在禁改范围里）；证据：scope、V01、R01、review；目的：既有断言是长期保护，不能为新功能放松。
- D10：所有修改都在允许集合内（3 个可改文件 + 1 个可新增文件），没有碰 forbidden_paths；`package.json` 与 `package-lock.json` 不变；没有新增依赖、没有新增 CSS、没有改 `PageFrame`/`readonly1`/`api.ts`/`mock`/`App.tsx`；证据：scope、G01、R01、V03；目的：这一片不许顺手改别的片的地盘。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符（例如 `PageFrame` 的 empty 分支不是「没传 `empty` 就渲染 children」、或 `RuntimesPage.tsx` 的 children 写法与合同写的不同），停下报告，不要自己改事实。
- 必须修改允许范围之外的文件才能继续（例如要动 `PageFrame.tsx`、`readonly1/**`、`api.ts`、`mock/**`、既有门禁测试、`page-app.test.tsx`）。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为（例如要在空态加写入口，或要把 Quizs 区块放进视图根里）。
- 基线检查（V01/V02/V03）在**未改代码时**就已经红：停下报告，不要改门禁或既有测试去凑绿。
- 达到单轮时限。

## Budget
- max_attempts_total: 3（按 task-id 汇总，含返工版本；累计已用 0 次——本版留 2 次实现与定点返工，余量 1 次）
- max_wall_seconds_per_attempt: 5400
- max_wall_seconds_total: 16200（3 次 × 5400；累计已用 0 秒，本版可用 16200 秒 ≥ 2×5400）
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：读源码与核对事实 15 分钟；实现（RuntimesPage、index.html）20 分钟；补测（新测试文件 + page-quizs 一处 it）30 分钟；必要检查（V01、V02、V03；R01 放最后跑一次）20 分钟；最终报告 5 分钟；总计约 90 分钟，单轮时限 5400 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01…D10，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过；不改 `tests/test_gate_*.py`。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
