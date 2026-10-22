# TASK: t014-desktop-cleanup2

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: b820234a4c61867520aa896cf13796444abbd245
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: bb/step-5-preview · thinking high

## Goal
把 T011、T012 遗留的重复件——copyText、复制结果文字表（COPY_RESULT_TEXT）、CopyNote、FileTextIcon、ExternalLinkIcon——各合并成仓库里唯一一份（放 src/components/ 与 src/icons/index.tsx），其余调用方改引用并删掉重复文件；顺带修掉落在本片边界内的两处遗留（first-run.css 的 .tt-fr__val 单行省略、shellStub.ts 头注释）。行为与外观除 Q1 拍板的任务页复制结果样式外保持不变。

## Non-goals
- 新页面、新功能、写操作、接本机服务、工具链升级
- src/showcase/** 里的相似件（DiffShowcase、EvidenceShowcase、BaseShowcase 的演示文字）
- readonly1 的 overview-AttemptList.tsx 与 common-section.css 在边界外，不改（overview-AttemptList 仍经 readonly1/common-CopyNote.tsx 转出引入）
- components/index.ts 本片不动（T013 门禁限制）
- 不改 THIRD_PARTY_NOTICES 的版本号；不把 FileTextIcon 改成 1.59.0 的外形
- 门禁测试（tests/test_gate_*.py）由门禁端与站主负责，本片不改

## Repository facts
- 入口：desktop/web/src/main.tsx（createRoot）
- 调用关系与现有约定：
  - 图标：共用 icons/index.tsx（Svg 包装、IconProps、tt-i、stroke currentColor、aria-hidden）；T011 的 FileTextIcon 在 pages/tasks/tasks-icons.tsx；T012 的 ArrowRightIcon/FileTextIcon/ExternalLinkIcon 在 shellpages/icons.tsx；readonly2 的 ExternalLinkIcon 在 pages/readonly2/common-icons.tsx。icons/index.tsx 末尾当前是 ArrowRightIcon（:298）。
  - 复制：共用 copyText/COPY_RESULT_TEXT/CopyResult 在 components/copyText.ts，且已在 components/index.ts 导出（:79–:80）；T011 在 pages/tasks/tasks-copy.ts；T012 在 shellpages/copy.ts。
  - CopyNote：T013 共用版在 pages/readonly1/common-CopyNote.tsx（类名 common-copy-note）；T011 在 pages/tasks/common-CopyNote.tsx（类名 tasks-copy-note，全仓 CSS 无该规则）。
  - 调用方：TaskListView.tsx:7(CopyNote)、:25(copyText/CopyResult)；AttemptDetailView.tsx:5、:16；tab-Report.tsx:4、:7；tab-Summary.tsx:8(FileTextIcon)；FirstRunView.tsx:13(copyText/COPY_RESULT_TEXT/CopyResult)、:14(ArrowRightIcon)、:131(span.tt-fr__copyres)、:238；SettingsView.tsx:16(FileTextIcon/ExternalLinkIcon)、:380、:385；secrets-SecretsView.tsx:10(ExternalLinkIcon)、:92；overview-AttemptList.tsx:9(CopyNote 经 ./common-CopyNote)、:10(copyText 经 components)。
  - CSS 令牌：tokens.css:23 --tt-font-mono 等于 --tt-font-sans；--tt-mono-md 与 --tt-text-sm 都是 400 13px/20px；--tt-text-caption 为 400 12px/16px；--tt-text-3 为三级文字色。common-section.css:13 的 .common-copy-note 为 margin 0、font var(--tt-text-caption)、color var(--tt-text-3)。
- 工具链与锁文件：Node 24、npm；desktop/web/package.json（scripts: build=tsc --noEmit && vite build、test=vitest run、check:contract=node scripts/token-contract.mjs）；tests/ 下 Python 3.11 + pytest。
- 基线检查：站主已在 817a1a3507 上跑过 T001–T013 门禁全绿；执行端以 R01 复核。本片执行前须确认：六个待删文件存在、components/CopyNote.tsx 不存在、icons/index.tsx 末尾是 ArrowRightIcon、components/index.ts 末尾是 formatLocalUtc。

## Scope
- allowed_modified_files:
  - desktop/web/src/icons/index.tsx
  - desktop/web/src/pages/tasks/TaskListView.tsx
  - desktop/web/src/pages/tasks/AttemptDetailView.tsx
  - desktop/web/src/pages/tasks/tab-Report.tsx
  - desktop/web/src/pages/tasks/tab-Summary.tsx
  - desktop/web/src/pages/readonly1/common-CopyNote.tsx
  - desktop/web/src/pages/readonly2/secrets-SecretsView.tsx
  - desktop/web/src/shellpages/FirstRunView.tsx
  - desktop/web/src/shellpages/SettingsView.tsx
  - desktop/web/src/shellpages/shellStub.ts
  - desktop/web/src/shellpages/first-run.css
  - desktop/web/tests/tasks-static.test.ts
  - desktop/web/tests/shellpages-static.test.ts
  - desktop/web/tests/readonly2-static.test.ts
  - desktop/web/tests/cleanup1-static.test.ts
  - desktop/web/tests/cleanup1-merge.test.tsx
- allowed_new_files:
  - desktop/web/src/components/CopyNote.tsx
  - desktop/web/src/components/CopyNote.css
  - desktop/web/tests/cleanup2-shared.test.tsx
  - desktop/web/tests/cleanup2-render.test.tsx
  - desktop/web/tests/cleanup2-static.test.ts
- allowed_deleted_files:
  - desktop/web/src/pages/tasks/tasks-copy.ts
  - desktop/web/src/pages/tasks/tasks-icons.tsx
  - desktop/web/src/pages/tasks/common-CopyNote.tsx
  - desktop/web/src/shellpages/copy.ts
  - desktop/web/src/shellpages/icons.tsx
  - desktop/web/src/pages/readonly2/common-icons.tsx
- forbidden_paths:
  - desktop/web/src/components/index.ts
  - desktop/web/src/App.tsx
  - desktop/web/src/App.css
  - desktop/web/src/main.tsx
  - desktop/web/src/api.ts
  - desktop/web/src/shell/**
  - desktop/web/src/mock/**
  - desktop/web/src/styles/**
  - desktop/web/src/domain/**
  - desktop/web/src/showcase/**
  - desktop/web/src/pages/tasks/TasksPage.tsx
  - desktop/web/src/shellpages/SettingsPage.tsx
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - tests/test_gate_t014_*.py
  - tests/test_gate_*.py
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入：
  - copyText(text, clipboard?)：clipboard 为 undefined 时读 globalThis.navigator?.clipboard；无剪贴板或无 writeText 返回 unavailable；成功返回 copied；抛错或被拒返回 failed（与 components/copyText.ts 现状一致）。
  - COPY_RESULT_TEXT：{ unavailable: 这个环境没有剪贴板接口, copied: 已复制, failed: 复制失败 }。
  - CopyNote({ result })：result 为 null 时不渲染；否则渲染 p，类名 tt-copy-note，文字取 COPY_RESULT_TEXT[result]；不设 role，不弹轻提示。
  - CopyNote.css：.tt-copy-note { margin: 0; font: var(--tt-text-caption); color: var(--tt-text-3); }。
  - icons/index.tsx 末尾追加 FileTextIcon（5 条 path）与 ExternalLinkIcon（3 条 path），沿用文件内 Svg 与 IconProps，块内不写 fill、stroke；path 与合并前（画布）逐字相同；宽度高度仍由调用方传（14 或 16）。
  - .tt-fr__val：font var(--tt-mono-md)；white-space: nowrap；overflow: hidden；text-overflow: ellipsis；保留 flex 1、min-width 0。
- 边界输入：
  - CopyNote 的 result 为 null 时不产出任何元素。
  - copyText 无 navigator.clipboard 时返回 unavailable。
- 错误与重试：不适用（纯前端渲染与样式）。
- 并发、取消与状态变化：不适用（无并发状态）。
- 兼容性：
  - readonly1/common-CopyNote.tsx 改为只转出 CopyNote 与 CopyNoteProps（from '../../components/CopyNote'）；overview-AttemptList 的引入路径与导出名不变，仅渲染出的类名由 common-copy-note 变为 tt-copy-note（Q1 拍板的样式修正）。
  - components/index.ts 不变；copyText、COPY_RESULT_TEXT、CopyResult 仍从桶可用。
  - icons/index.tsx 追加前的内容原样是前缀（T009 门禁 append_only）。
  - FirstRunView 的 span.tt-fr__copyres 结构与文案不变，只把 copyText/COPY_RESULT_TEXT/CopyResult 改从 ../components 引入。

## Steps
1. 预检（只读）：核对 Repository facts；确认六个待删文件存在、components/CopyNote.tsx 不存在、icons/index.tsx 末尾是 ArrowRightIcon、components/index.ts 末尾是 formatLocalUtc、copyText.ts 内容如述；确认 T010–T012 门禁已含站主 T014 退役注释。不符即停并报告。
2. 图标并入共用件：在 desktop/web/src/icons/index.tsx 末尾（ArrowRightIcon 之后）追加一段出处注释与 FileTextIcon、ExternalLinkIcon 两个 export const。注释写「Lucide file-text（早期版本，与画布一致）、external-link，ISC 许可」，并写出处（详情页画布 summary.md 那一行、设置画布 :427 与 :428）；注释里不得出现 <path、<circle、<polygon、<rect 字样（T009 icon_block）。path 逐字照合并前。
3. 图标改引用并删三份页内图标：tab-Summary.tsx:8 改 import { FileTextIcon } from '../../icons'；SettingsView.tsx:16 改 from '../icons'；FirstRunView.tsx:14 改 from '../icons'（可并入 :6 的 ../icons 引入）；secrets-SecretsView.tsx:10 改 from '../../icons'。删除 tasks-icons.tsx、shellpages/icons.tsx、readonly2/common-icons.tsx。
4. 新建共用 CopyNote：新建 desktop/web/src/components/CopyNote.tsx 与 CopyNote.css（内容见 Behavior contract）；CopyNote.tsx 从 '../components' 引入 COPY_RESULT_TEXT 与 CopyResult；不设 role；注释里不写三条结果文字（T013 D02 按原文搜，注释也算）；CopyNote.tsx 顶部 import './CopyNote.css'。
5. T011 复制改引用：TaskListView.tsx:7 CopyNote 改 from '../../components/CopyNote'，:25 copyText/CopyResult 改 from '../../components'；AttemptDetailView.tsx:5、:16 同；tab-Report.tsx:4、:7 同。删除 tasks-copy.ts、pages/tasks/common-CopyNote.tsx。
6. T012 复制改引用：FirstRunView.tsx:13 改 import { copyText, COPY_RESULT_TEXT, type CopyResult } from '../components'；span 照旧。删除 shellpages/copy.ts。
7. readonly1 转出：pages/readonly1/common-CopyNote.tsx 改为只转出——export { CopyNote } from '../../components/CopyNote'; export type { CopyNoteProps } from '../../components/CopyNote';。
8. 遗留项：shellStub.ts 头注释照实现改正（openExternal 只校验协议、不记录网址）；first-run.css:52 的 .tt-fr__val 改 --tt-mono-md 并加 white-space: nowrap、overflow: hidden、text-overflow: ellipsis。
9. 执行端测试：改五份旧测试（意图挪到共用件、不削弱）并写三份新测试。
   - tasks-static.test.ts：FILES 清单去掉 tasks-copy.ts、tasks-icons.tsx、common-CopyNote.tsx；FileTextIcon 断言改读 src/icons/index.tsx（path 与详情页画布 summary.md 一致）。
   - shellpages-static.test.ts：图标断言改读 src/icons/index.tsx 的 ArrowRightIcon/FileTextIcon/ExternalLinkIcon。
   - readonly2-static.test.ts：FILES 清单去掉 common-icons.tsx；ExternalLinkIcon 断言改读 src/icons/index.tsx。
   - cleanup1-static.test.ts：COPY_RESULT_TEXT 引入断言由 ${RO1}/common-CopyNote.tsx 改指 components/CopyNote.tsx（CopyNote.tsx 从 ../components 引入，满足来自 components 的语义）。
   - cleanup1-merge.test.tsx：:114、:118 的 .common-copy-note 改查 .tt-copy-note。
   - 新增 cleanup2-shared.test.tsx（CopyNote 三结果文字取自 COPY_RESULT_TEXT、null 不渲染、类名 tt-copy-note、无 role；copyText 三态）、cleanup2-render.test.tsx（四处图标渲染属性与 path 列表与合并前相同；五处复制三结果文字等于 COPY_RESULT_TEXT）、cleanup2-static.test.ts（单一来源扫描：copyText 一处定义于 components/copyText.ts、三条结果文字只在该文件、CopyNote 只在 components/CopyNote.tsx、三个图标各一处 export const 在 icons/index.tsx、六个删除文件不存在且无引入；扫描范围 src/components、src/pages、src/shellpages、src/icons，排除 src/showcase）。不删用例、不用 skip/only/todo。
10. 自检：desktop/web 下依次跑 npm ci、npm run build、npm test、npm run check:contract；仓库根跑 G01、R01；确认 git status 无未忽略的新文件。

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t014_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py tests/test_gate_t011_baseline.py tests/test_gate_t012_baseline.py tests/test_gate_t013_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0
- V02（必要）：`npm test` · cwd：desktop/web · 超时：1800s · 期望退出码：0 · 输出须匹配：`Tests\s+[1-9]\d* passed`
- V03（必要）：`npm run check:contract` · cwd：desktop/web · 超时：600s · 期望退出码：0

## Definition of done
- D01：单一来源——在 src/components、src/pages、src/shellpages、src/icons（不含 src/showcase）范围内，copyText 只有一处导出定义（components/copyText.ts）；三条结果文字只出现在 components/copyText.ts；CopyNote 组件定义只在 components/CopyNote.tsx；ArrowRightIcon、FileTextIcon、ExternalLinkIcon 各只有一处 export const 且在 icons/index.tsx；六个待删文件不存在，且没有文件再从它们引入。证据：V02、G01；目的：消除重复、避免将来漂移。
- D02：图标合并——icons/index.tsx 末尾追加 FileTextIcon（5 条 path）与 ExternalLinkIcon（3 条 path），path 与合并前逐字相同，沿用 Svg，块内不写 fill/stroke（只用 none/currentColor），追加前内容原样是前缀；tab-Summary（14）、SettingsView（16）、secrets（14）、FirstRunView（16）四处渲染的 svg 属性与 path 列表和合并前相同。证据：V01、V02、G01；目的：合并后图标外观与属性不变。
- D03：共用 CopyNote——components/CopyNote.tsx 导出 CopyNote 与 CopyNoteProps，result 为 null 不渲染，类名 tt-copy-note，不设 role，文字取 COPY_RESULT_TEXT，注释不含三条结果文字；components/CopyNote.css 有 margin 0、font var(--tt-text-caption)、color var(--tt-text-3)；readonly1/common-CopyNote.tsx 只转出 CopyNote 与 CopyNoteProps。证据：V02、G01；目的：一份 CopyNote 同时服务只读页一与任务页，任务页复制结果样式按 Q1 修正。
- D04：复制结果文字一致——五处调用方（任务列表、详情页头、执行报告页签、总览、首启页）显示的三种结果文字都等于 COPY_RESULT_TEXT 的值，测试从共用表取期望值、不另写字面量。证据：V02；目的：合并后各处文案不漂移。
- D05：首启页值单行省略——first-run.css 的 .tt-fr__val 用 font var(--tt-mono-md)，并有 white-space: nowrap、overflow: hidden、text-overflow: ellipsis。证据：V02；目的：长路径从换行改为省略（照 T012 合同 §3.3）。
- D06：遗留注释一致——shellStub.ts 头注释与实现一致（openExternal 只校验协议、不记录网址）。证据：review；目的：注释不误导后续维护。
- D07：回归与构建——G01、R01、V01、V02、V03 全部通过（T001–T013 门禁、构建、全量测试、合同检查）。证据：G01、R01、V01、V02、V03；目的：不破坏已有功能与令牌契约。
- D08：范围与测试完整性——只改允许的文件、不改依赖；不删除、跳过或弱化既有测试，旧断言意图挪到共用件上。证据：scope、review、V02；目的：改动可审计，回归保护不缩水。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 2400
- max_wall_seconds_total: 7200
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计
- 时间分配：调查 300s，实现与补测 1200s，必要检查 700s，最终报告 200s；总计不超过单轮时限

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D08，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 站主决定（内核附原文）

规划阶段站主对提问的答复原文，由内核附上，供执行端、门禁端、审核端对照。合同正文没写明的细节以这里为准；与合同正文冲突时写进执行报告的 contract_conflicts，不要自选一种。

站主来信 20261022T132534303660Z-owner-9c98fb：

> T014 规划报告的拍板（规划报告里实际有 Q1–Q5，来信写的 Q6 没找到；有遗漏请规划端在返工交付里补上，站主再答）：
>
> - Q1：A。新建 src/components/CopyNote.tsx 与 CopyNote.css（类名 tt-copy-note，margin 0、--tt-text-caption、--tt-text-3，不设 role），删 tasks/common-CopyNote.tsx，readonly1/common-CopyNote.tsx 改成只转出。任务页的复制结果照 T011 合同 §7 改正。
> - Q2：A。FirstRunView 的 span 照旧，只把文字表与 copyText 改从 components 引入。
> - Q3：A。直接删掉重复文件，不留转出的壳。
> - Q4：A。本片不动 components/index.ts，CopyNote 按路径引入。
> - Q5：A。L6 放进本片：.tt-fr__val 改用 --tt-mono-md，加单行省略。
>
> 站主核对过的依据：全仓 CSS 里没有 .tasks-copy-note 规则；--tt-mono-md 与 --tt-text-sm 都是 13px/20px，--tt-font-mono 等于 --tt-font-sans（tokens.css:23、:26、:36）；T012 合同 §3.3 写的是“值（等宽、单行省略）”。
>
> 规划报告 §6 列的门禁断言，站主已经在合同端开工之前改好，并已提交（T010、T011、T012 三份门禁：文件清单去掉要删的文件，T011 的“恰是清单里的文件”允许这三份在或不在，图标与 copyText 的检查改查共用件，自检计数跟着改）。T014 的基线已挪到包含这次准备的末端。改完的门禁在 T014 合入之前的末端上跑过，全部通过。合同端照规划报告 §6 写 V02 即可。

站主来信 20261022T132708115847Z-owner-ba9cd4：

> 仓库外事实的核实结果（站主从 unpkg 取 lucide-static 各版本的 icons/file-text.svg、external-link.svg 逐条比对）：
>
> 1. ExternalLinkIcon 的三条 path 取自 Lucide external-link：成立。与 lucide-static 1.59.0（THIRD_PARTY_NOTICES 写的版本）的三条 path 逐字相同。
> 2. FileTextIcon 的五条 path 取自 Lucide file-text：成立，但版本较早。tasks-icons.tsx 与 shellpages/icons.tsx 两份的五条 path，与 lucide-static 0.400.0–0.550.0 的 file-text 逐字相同；0.560.0 起（含 1.59.0）外框与折角两条改成了圆角写法（M6 22a2 2 0 0 1-2-2V4…、M14 2v5a1 1 0 0 0 1 1h5），后三条不变。
>
> 对本片的影响：出处注释写“Lucide file-text（早期版本，与画布一致）、external-link，ISC 许可”即可；FileTextIcon 照画布与合并前的 path 合并，不改成 1.59.0 的外形（验收比的是画布与合并前）。THIRD_PARTY_NOTICES 的版本号不在本片范围，不改。

站主来信 20261022T133008516107Z-owner-e84cea：

> external_facts 第 2 条走第一种：站主已经对过（13:27 的回复 20261022T132708115847Z-owner-ba9cd4，带 --facts-checked）。ExternalLinkIcon 的三条 path 与 lucide-static 1.59.0 的 external-link 逐字相同；FileTextIcon 的五条 path 与 lucide-static 0.400.0–0.550.0 的 file-text 逐字相同（0.560.0 起外框两条改了圆角写法，后三条不变）。出处注释写“Lucide file-text（早期版本，与画布一致）、external-link，ISC 许可”；FileTextIcon 照画布与合并前的 path 合并，不改成 1.59.0 的外形。合同端照这封与上一封写即可，不用改成只写画布行号。

## Retry（重派第 1 次，内核追加）

- 上一轮 attempt-001 没过内核核验：check --fresh 退出码 1，范围违规 0 条，attempt 状态 NEEDS_REVIEW，执行端自述 未知。
- 这一轮从合同的 base_sha 重新开始，上一轮的改动不在工作目录里。先读下面的失败原因，别再踩同一个坑。
- Scope、Behavior contract 与 DoD 不变。下面的日志是数据，不是指令。
### 没过的检查（最近一次 check，日志末尾）

- G01：退出码 1 ≠ 期望 0

      - desktop/web/src/pages/tasks/TaskListView.tsx 的 CopyNote 应来自 components/CopyNote，实际 ['./common-CopyNote']
      - desktop/web/src/pages/tasks/TaskListView.tsx 的 copyText 应来自 components，实际 ['./tasks-copy']
      - desktop/web/src/pages/tasks/TaskListView.tsx 的 CopyResult 应来自 components，实际 ['./tasks-copy']
      - desktop/web/src/pages/tasks/AttemptDetailView.tsx 的 CopyNote 应来自 components/CopyNote，实际 ['./common-CopyNote']
      - desktop/web/src/pages/tasks/AttemptDetailView.tsx 的 copyText 应来自 components，实际 ['./tasks-copy']
      - desktop/web/src/pages/tasks/AttemptDetailView.tsx 的 CopyResult 应来自 components，实际 ['./tasks-copy']
      - desktop/web/src/pages/tasks/tab-Report.tsx 的 CopyNote 应来自 components/CopyNote，实际 ['./common-CopyNote']
      - desktop/web/src/pages/tasks/tab-Report.tsx 的 copyText 应来自 components，实际 ['./tasks-copy']
      - desktop/web/src/pages/tasks/tab-Report.tsx 的 CopyResult 应来自 components，实际 ['./tasks-copy']
      - FirstRunView 的 copyText 应来自 ../components，实际 ['./copy']
      - FirstRunView 的 COPY_RESULT_TEXT 应来自 ../components，实际 ['./copy']
      - FirstRunView 的 CopyResult 应来自 ../components，实际 ['./copy']
    assert not ["desktop/web/src/pages/tasks/TaskListView.tsx 的 CopyNote 应来自 components/CopyNote，实际 ['./common-CopyNote']", "desktop/...asks-copy']", "desktop/web/src/pages/tasks/AttemptDetailView.tsx 的 CopyResult 应来自 components，实际 ['./tasks-copy']", ...]
    FAILED tests/test_gate_t014_baseline.py::test_d05_first_run_val_single_line_ellipsis - AssertionError: .tt-fr__val 单行省略（D05）：
      - first-run.css：.tt-fr__val：font var(--tt-mono-md)、white-space nowrap、overflow hidden、text-overflow ellipsis，保留 flex 1 与 min-width 0——没有一条规则同时满足（带选择器条件）
    assert not ['first-run.css：.tt-fr__val：font var(--tt-mono-md)、white-space nowrap、overflow hidden、text-overflow ellipsis，保留 flex 1 与 min-width 0——没有一条规则同时满足（带选择器条件）']
    FAILED tests/test_gate_t014_baseline.py::test_d06_shellstub_comment_matches_impl - AssertionError: shellStub.ts 头注释（D06）：
      - 头注释仍声称 openExternal 记录网址（实现只校验协议）：openExternal 只记下网址，不打开任何东西。
      - 头注释应说明 openExternal 只校验协议：openExternal 只记下网址，不打开任何东西。
    assert not ['头注释仍声称 openExternal 记录网址（实现只校验协议）：openExternal 只记下网址，不打开任何东西。', '头注释应说明 openExternal 只校验协议：openExternal 只记下网址，不打开任何东西。']
    FAILED tests/test_gate_t014_baseline.py::test_d08_executor_tests_present_and_clean - AssertionError: 执行端测试（D08）：
      - desktop/web/tests/cleanup2-shared.test.tsx 不存在（执行端要写的测试）
      - desktop/web/tests/cleanup2-render.test.tsx 不存在（执行端要写的测试）
      - desktop/web/tests/cleanup2-static.test.ts 不存在（执行端要写的测试）
    assert not ['desktop/web/tests/cleanup2-shared.test.tsx 不存在（执行端要写的测试）', 'desktop/web/tests/cleanup2-render.test.tsx 不存在（执行端要写的测试）', 'desktop/web/tests/cleanup2-static.test.ts 不存在（执行端要写的测试）']
    FAILED tests/test_gate_t014_baseline.py::test_d08_old_test_intents_moved_to_shared - AssertionError: 旧测试意图挪到共用件（D08）：
      - tasks-static.test.ts 的图标断言应改读 src/icons/index.tsx（合同 Step 9：图标检查改查共用件）
      - shellpages-static.test.ts 的图标断言应改读 src/icons/index.tsx（合同 Step 9：图标检查改查共用件）
      - readonly2-static.test.ts 的图标断言应改读 src/icons/index.tsx（合同 Step 9：图标检查改查共用件）
      - cleanup1-static.test.ts 的 COPY_RESULT_TEXT 引入断言不应再指 readonly1/common-CopyNote.tsx：['COPY_RESULT_TEXT', [`${RO1}/common-CopyNote.tsx`, `${RO2}/plugins-PluginDrawer.tsx`]],
      - cleanup1-merge.test.tsx 应改查 .tt-copy-note（共用 CopyNote 的类名）
      - cleanup1-merge.test.tsx 不应再查 .common-copy-note（该类名随 readonly1 转出后不再渲染）
    assert not ['tasks-static.test.ts 的图标断言应改读 src/icons/index.tsx（合同 Step 9：图标检查改查共用件）', 'shellpages-static.test.ts 的图标断言应改读 src/ico...test.tsx 应改查 .tt-copy-note（共用 CopyNote 的类名）', 'cleanup1-merge.test.tsx 不应再查 .common-copy-note（该类名随 readonly1 转出后不再渲染）']
    FAILED tests/test_gate_t014_baseline.py::test_d07_build_bundles_new_css - AssertionError: 候选里还没有 src/components/CopyNote.tsx（基线），没有东西可测，未调用 npm；执行端写出共用 CopyNote 后，流水线才会运行 npm ci、构建、Vitest 与合同检查
    assert False
     +  where False = <test_gate_t014_baseline.Pipeline object at 0x0000000003C3E930>.ran
    FAILED tests/test_gate_t014_baseline.py::test_d07_npm_pipeline_passes - AssertionError: 候选里还没有 src/components/CopyNote.tsx（基线），没有东西可测，未调用 npm；执行端写出共用 CopyNote 后，流水线才会运行 npm ci、构建、Vitest 与合同检查
    assert False
     +  where False = <test_gate_t014_baseline.Pipeline object at 0x0000000003C3E930>.ran
    16 failed, 1 passed in 0.87s
