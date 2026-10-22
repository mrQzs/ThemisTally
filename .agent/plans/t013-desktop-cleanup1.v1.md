# TASK: t013-desktop-cleanup1

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 009efa081bcdb3b7fddc9c3401d72fe3a5dea38c
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: bb/step-5-preview · thinking high

## Goal
- 合并 T009、T010 的四样重复件（ActorTag、相对时间 title 格式、动作中文表、复制与结果文字），每样只留一份共用件（放 src/components/），另一处改引用
- 补 T009 终审遗留四项视觉修整（指标卡纵向 + 色调条贴左缘 + 图标；.rt-cmd display block；方案表 aria-controls 只在展开时给 + useId；attempt 行名称 --tt-mono-md）
- 把 T010 遗留的样式表接线断言（L2）放进本片门禁

## Non-goals
- buildHash 编码方式；新页面、新功能；写操作流程；接本机服务；工具链升级
- T011、T012 在途片里的同类件（tasks-copy.ts、common-CopyNote.tsx、shellpages/copy.ts、ArrowRightIcon、ExternalLinkIcon）
- 范围外的相似件（showcase/DiffShowcase.tsx、readonly2/common-icons.tsx、RelativeTime.tsx 的 relativeText、减号常量）
- 总览七端版的四张卡
- T010 规划 H1 里要改已有组件才能消除的视觉差异
- 门禁测试（tests/test_gate_t013_*.py）

## Repository facts
- 入口：desktop/web/src/main.tsx（createRoot，不传选项）
- 调用关系与现有约定：
  - readonly1、readonly2 下的页面文件从 src/components/ 引入共用组件
  - 样式表从页面文件 import，Vite 打包
  - id 用 useId（React 18.3.1 客户端生成 :r<32 进制序号>:，不含空白）
- 工具链与锁文件：Node 24、npm；desktop/web/package.json；tests/ 下 Python 3.11 + pytest
- 基线检查：python -m pytest tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py -q · 期望退出码 0 · 输出匹配 \d+ passed
- 基线说明：base_sha 取 fc0a2da（站主退役 G9/G10 R1–R5 的提交），当前 HEAD a7931122b540 与 fc0a2da 的差异与本任务无关（差异在门禁端，不影响本片源码与测试）。

## Scope
- allowed_modified_files:
  - desktop/web/src/components/ActorTag.tsx
  - desktop/web/src/components/RelativeTime.tsx
  - desktop/web/src/components/index.ts
  - desktop/web/src/pages/readonly1/overview-MetricCard.tsx
  - desktop/web/src/pages/readonly1/overview-styles.css
  - desktop/web/src/pages/readonly1/overview-logic.ts
  - desktop/web/src/pages/readonly1/overview-ConfigChanges.tsx
  - desktop/web/src/pages/readonly1/overview-AttemptList.tsx
  - desktop/web/src/pages/readonly1/common-CopyNote.tsx
  - desktop/web/src/pages/readonly1/roles-PresetsTable.tsx
  - desktop/web/src/pages/readonly1/runtimes-styles.css
  - desktop/web/src/pages/readonly2/history-HistoryView.tsx
  - desktop/web/src/pages/readonly2/history-HistoryDrawer.tsx
  - desktop/web/src/pages/readonly2/history-logic.ts
  - desktop/web/src/pages/readonly2/common-format.ts
  - desktop/web/src/pages/readonly2/plugins-PluginDrawer.tsx
  - desktop/web/tests/page-logic.test.ts
  - desktop/web/tests/page-static.test.ts
  - desktop/web/tests/page-roles.test.tsx
  - desktop/web/tests/readonly2-logic.test.ts
  - desktop/web/tests/readonly2-static.test.ts
- allowed_new_files:
  - desktop/web/src/components/copyText.ts
  - desktop/web/src/components/actionTitle.ts
  - desktop/web/tests/cleanup1-shared.test.ts
  - desktop/web/tests/cleanup1-merge.test.tsx
  - desktop/web/tests/cleanup1-visual.test.tsx
  - desktop/web/tests/cleanup1-css.test.ts
  - desktop/web/tests/cleanup1-static.test.ts
- allowed_deleted_files:
  - desktop/web/src/pages/readonly1/common-copyText.ts
  - desktop/web/src/pages/readonly2/common-copy.ts
  - desktop/web/src/pages/readonly2/history-ActorTag.tsx
- forbidden_paths:
  - desktop/web/src/icons/index.tsx
  - desktop/web/src/App.tsx
  - desktop/web/src/App.css
  - desktop/web/src/main.tsx
  - desktop/web/src/shell/**
  - desktop/web/src/api.ts
  - desktop/web/src/mock/**
  - desktop/web/src/styles/**
  - desktop/web/src/domain/**
  - desktop/web/src/showcase/**
  - desktop/web/src/pages/tasks/**
  - desktop/web/src/mock/tasks-*
  - desktop/web/src/shellpages/**
  - desktop/web/src/mock/shellpages-*
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/tests/shell-app.test.tsx
  - tests/test_gate_t013_*.py
  - tests/test_gate_*.py
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

说明：src/mock 下已有的文件不改；本片不新建 mock 文件。desktop/web/src/pages/tasks/**、desktop/web/src/shellpages/** 是 T011、T012 在途片的文件，本片不碰。

## Behavior contract
- 正常输入：
  - src/components/copyText.ts 导出 copyText、CopyResult、COPY_RESULT_TEXT；copyText 成功返回 copied；没有 writeText 返回 unavailable；抛错或被拒返回 failed；缺省取 navigator.clipboard
  - src/components/actionTitle.ts 导出 ACTION_TITLES（13 条）、actionTitle；用 Object.prototype.hasOwnProperty.call 查表；表外返回 null
  - src/components/ActorTag.tsx 追加 actorTone 导出；五类色调（user-ui brand、user neutral、agent: 开头 info、undeclared warning、其他 neutral）
  - src/components/RelativeTime.tsx 追加 formatLocalUtc 导出；格式「YYYY-MM-DD HH:mm:ss（UTC HH:mm:ss）」；解析不了返回 null
  - 指标卡：每张卡的 a 里依次是色调条（aria-hidden）、标签行（16px 图标 aria-hidden + 标签文字）、数字（tt-num）；卡片规则 position relative、display flex、flex-direction column、gap --tt-space-0_5；色调条规则 position absolute、left/top/bottom 0、width 3px；图标颜色规则各自只引用本卡色调令牌（运行中 --tt-tone-info-fg、待验收 --tt-accent-text、要你决定 --tt-tone-escalate-fg、待集成 --tt-tone-brand-fg）
  - .rt-cmd：同一条规则有 display block、max-width 280px、overflow hidden、white-space nowrap、--tt-mono-sm
  - aria-controls：展开的 [查看差异] 的 aria-controls 指向文档里存在的面板，值不含空白；收起的按钮没有 aria-controls；各行面板 id 互不相同（useId 加行序号）
  - .ov-row__name：规则有 font var(--tt-mono-md)，仍单行省略
  - 样式表接线：readonly1、readonly2 下每份 CSS 都能从 src/main.tsx 顺 import 到达
- 边界输入：
  - actionTitle：Object.prototype 上的名字（constructor、toString、valueOf、hasOwnProperty、__proto__ 等）返回 null
  - formatLocalUtc：解析不了返回 null
  - copyText：没有剪贴板接口返回 unavailable
- 错误与重试：不适用（纯前端渲染与样式）
- 并发、取消与状态变化：不适用（无并发状态）
- 兼容性：
  - ActorTag、ActorTagProps、RelativeTime、RelativeTimeProps 的名字与属性不变
  - index.ts 基线前缀不变，只在末尾追加
  - T001–T010 门禁（按 §8 退役之后）都是回归，不能变红

## Steps
1. 预检（只读）
   - 意图：在开工时的末端上核对假设 A1–A13；确认 Q1–Q3 已定、§8 的断言已退役；看 T011、T012 是否已落地，已落地就读它们门禁里对 components/ActorTag.tsx、RelativeTime.tsx、index.ts、icons/index.tsx 的断言
   - 验收意图：不符就停
   - 风险：低
2. 共用件
   - 范围：components/copyText.ts、actionTitle.ts；ActorTag.tsx 追加 actorTone；RelativeTime.tsx 追加 formatLocalUtc 并自用；index.ts 末尾追加；测试 cleanup1-shared
   - 验收意图：copyText 三种结果与缺省取 navigator.clipboard；三条结果文字；13 条动作说明，表外为 null，Object.prototype 上的名字为 null；actorTone 五类；formatLocalUtc 的格式，解析不了时为 null；RelativeTime 的 title 等于 formatLocalUtc；ActorTag、RelativeTime 原有导出与属性不变
   - 风险：index.ts 的新名字或文件名碰到禁用子串；改了基线前缀
3. T009 侧改引用
   - 范围：common-CopyNote、overview-AttemptList、overview-ConfigChanges、overview-logic；删 common-copyText.ts；page-logic、page-static 改引入与清单
   - 验收意图：总览的复制三结果、配置变更的动作 title、执行者标签、相对时间与合并前相同
   - 风险：漏改一处引入，构建失败
4. T010 侧改引用
   - 范围：history-HistoryView、history-HistoryDrawer、history-logic、common-format、plugins-PluginDrawer；删 common-copy.ts、history-ActorTag.tsx；readonly2-logic、readonly2-static 改引入与清单
   - 验收意图：历史表执行者五色、动作 title、时间文字与 title、抽屉 dl 的时间、插件抽屉的复制三结果与合并前相同；时间格换 RelativeTime（span 变成带 dateTime 的 time）
   - 风险：改写 timeCell 的测试时丢了断言
5. 指标卡
   - 范围：overview-MetricCard.tsx、overview-styles.css；图标按 Q1；测试 cleanup1-visual
   - 验收意图：D05
   - 风险：图标颜色写成内联 style；图标颜色规则引用了别的卡的令牌；px 没写出处；选 LoaderCircle 时误加转动类
6. attempt 行名称
   - 范围：overview-styles.css 的 .ov-row__name
   - 验收意图：D08
   - 风险：低
7. CLI 运行时命令格
   - 范围：runtimes-styles.css 的 .rt-cmd
   - 验收意图：D06
   - 风险：低
8. 方案表 aria-controls
   - 范围：roles-PresetsTable.tsx；page-roles.test.tsx 的 :145；cleanup1-visual 的可访问性用例
   - 验收意图：D07
   - 风险：各行共用一个 id；用方案名拼 id
9. 本片测试与源码规则
   - 范围：cleanup1-static；cleanup1-css
   - 验收意图：D02、D09
   - 风险：「只有一份」的扫描范围写太宽，扫到陈列页、TextViewer 的内部回调或 T011、T012 的文件而误红
10. 自检
    - 意图：在 desktop/web 下依次跑 npm ci、npm run build、npm test、npm run check:contract；在仓库根点名跑 G01、R01、V03；确认 git status 没有新的未忽略文件
    - 风险：R01 十份门禁慢，超时设 1800s

## Setup
- S01：`npm ci --no-audit --no-fund` · cwd：desktop/web · 超时：900s

## Validation commands
- G01（必要，基线应失败）：`python -m pytest tests/test_gate_t013_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- R01（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t006_baseline.py tests/test_gate_t007_baseline.py tests/test_gate_t008_baseline.py tests/test_gate_t009_baseline.py tests/test_gate_t010_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V01（必要）：`npm run build` · cwd：desktop/web · 超时：600s · 期望退出码：0
- V02（必要）：`npm test` · cwd：desktop/web · 超时：1800s · 期望退出码：0
- V03（必要）：`npm run check:contract` · cwd：desktop/web · 超时：600s · 期望退出码：0

## Definition of done
- D01：共用件——components/copyText.ts、actionTitle.ts 存在并导出正确；copyText 三种结果与缺省取 navigator.clipboard；COPY_RESULT_TEXT 三条文字；actionTitle 13 条逐字，表外与 Object.prototype 名字均为 null；actorTone 五类色调；formatLocalUtc 格式正确，解析不了为 null；RelativeTime 的 title 等于 formatLocalUtc；ActorTag、ActorTagProps、RelativeTime、RelativeTimeProps 名字与属性不变；index.ts 只在末尾追加；证据：V02；目的：仓库里四样重复件各只留一份，后续片可以直接引用。
- D02：没有第二份——在 src/components/**、src/pages/readonly1/**、src/pages/readonly2/** 范围内，copyText 只有一处函数定义（在 components/copyText.ts）；「这个环境没有剪贴板接口」「已复制」「复制失败」只出现在 components/copyText.ts；13 条动作说明只出现在 components/actionTitle.ts；「（UTC 」拼写只出现在 components/RelativeTime.tsx；ActorTag 组件只有一个定义；带引号的 undeclared 只出现在 components/ActorTag.tsx；readonly1/common-copyText.ts、readonly2/common-copy.ts、readonly2/history-ActorTag.tsx 不存在；readonly1、readonly2 用到这几样时只从 components 引入；证据：V02、review；目的：消除重复，避免将来漂移。
- D03：T009 侧渲染不变——总览配置变更的动作 title（13 条）、执行者五色、相对时间文字与 title、复制三结果文字，与合并前相同；证据：V02；目的：合并后总览页的视觉与交互与合并前一致。
- D04：T010 侧渲染不变——历史表的执行者五色、动作 title、时间文字与 title、抽屉 dl 的时间、插件抽屉的复制三结果，与合并前相同；时间格元素解析得了是 time，dateTime 为原文；证据：V02；目的：合并后历史页与插件页的视觉与交互与合并前一致。
- D05：指标卡——每张卡的 a 里依次是色调条（aria-hidden）、标签行、数字（tt-num）；标签行在数字之前，含 16px 图标（aria-hidden）与标签文字；卡上仍只有计数这一个数字；卡片规则有 position relative、display flex、flex-direction column、gap --tt-space-0_5；色调条规则有 position absolute，left、top、bottom 为 0，width 3px；四张卡的图标颜色规则各自只引用本卡的色调令牌（待验收用 --tt-accent-text）；没有内联 style；证据：V02；目的：照设计稿领域板 7.23 与 Main :97–100。
- D06：.rt-cmd——同一条规则有 display block、max-width 280px、overflow hidden、white-space nowrap、--tt-mono-sm；证据：V02；目的：照设计稿 Runtimes :109。
- D07：aria-controls——展开的 [查看差异] 的 aria-controls 指向文档里存在的面板，值不含空白；收起的按钮没有 aria-controls；各行面板 id 互不相同；方案名带空格时同样成立；roles-PresetsTable.tsx 用 useId，没有用方案名拼 id 的写法；证据：V02；目的：读屏不报找不到的面板。
- D08：.ov-row__name——规则有 font var(--tt-mono-md)，仍单行省略；证据：V02；目的：照设计稿 Main :111。
- D09：样式表接线——readonly1、readonly2 下每份 CSS 都能从 src/main.tsx 顺 import 到达，构建成功；证据：V01、V02；目的：CSS 在真实构建里被打包。
- D10：回归与范围——T001–T010 门禁（按 §8 退役之后）通过；V01 构建、V02 全量测试、V03 合同检查通过；只改允许的文件；不改依赖；新测试不用 skip、only、todo；证据：G01、R01、V01、V02、V03、scope；目的：不破坏已有功能。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续。
- 需要新增或升级依赖、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 7200
- max_wall_seconds_total: 21600
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计
- 时间分配：调查 600s，实现与补测 4500s，必要检查 1500s，最终报告 600s；总计不超过单轮时限

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D10，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。

## 10. 后续收尾
- T011、T012 落地后，把它们的 copyText、复制结果的显示、ExternalLinkIcon、ArrowRightIcon，以及 readonly2/common-icons.tsx 的 ExternalLinkIcon，并进本片建的共用件与 icons/index.tsx。
- 提醒 T011/T012 的门禁端不要冻结 components/ActorTag.tsx、RelativeTime.tsx、index.ts 的整份摘要或内容断言。
