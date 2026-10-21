# TASK: t008-desktop-diff

## Identity
- plan_version: 2
- repository: ThemisTally
- base_sha: f17c849f5a96be3a576faff57137f2672728b892
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: step/step-5-preview · thinking high

## Goal
交付 T008 第 7 片（桌面端前端差异视图与日志跟随）。在 desktop/web/ 新增差异视图 DiffView（自带 git 补丁解析 diff/parseDiff.ts 与分屏配对 diff/splitPairs.ts）、日志跟随 LogFollow（建在 T007 的 TextViewer 上）、3 个图标（PauseIcon、FilterIcon、FileDiffIcon）、新建演示 DiffShowcase，并按站主 Q1 选甲给 TextViewer.tsx 追加 6 个可选属性；不改依赖、不改令牌、不改 App.css、不接服务、不改 T007 其他组件与 evidence/**。

## Non-goals
- 页面（任务列表、attempt 详情）与数据接入；接本机服务、SSE、轮询；Ctrl+F 查找、虚拟滚动；工具链升级。
- 差异视图：字词级高亮、语法高亮、展开更多上下文、评论；二进制内容的预览；不带 diff --git 行的普通 unified diff（显示成「补丁里没有改动」）。
- 日志跟随：取页、游标、轮询由调用方做；组件只对 pages 的变化做出反应。
- 不改 README；不改 T006 的应用框架目录（src/shell/、src/pages/、src/mock/、src/api.ts、src/App.tsx、src/App.css、src/main.tsx、src/styles/**、desktop/web/README.md）；不新增依赖；不改 T007 其他组件（TextViewer.css、SafeMarkdown、EffortPair、MaskedValue、CommandLine、NextStep、evidence/**、EvidenceShowcase、showcase-evidence.css）与既有执行端测试。

## Repository facts
- 入口：desktop/web/src/main.tsx 挂载 desktop/web/src/App.tsx（陈列页）；desktop/web/src/components/index.ts 统一导出五片组件；图标在 desktop/web/src/icons/index.tsx（Svg 包装为模块内私有）；陈列页在 desktop/web/src/showcase/（现有 FormsShowcase.tsx、showcase-forms.css、EvidenceShowcase.tsx、showcase-evidence.css）。
- 工具链与锁文件：Node 24.19.0；React 18.3.1 + react-dom 18.3.1 + TypeScript 5.6.3 + Vite 5.4.11 + Vitest 2.1.8；@testing-library/react 16.1.0、@testing-library/dom 10.4.0、jsdom 25.0.1，无 user-event；vite.config.ts 的 test.include 含 src、tests、gate-probe；tsconfig.json 只含 src 与 vite.config.ts（测试不进 tsc）；锁文件 desktop/web/package-lock.json（lockfileVersion 3），npm ci 可复现。C11 核对：package.json 精确固定这些版本，与仓库外事实一致。
- 基线：worktree HEAD = base_sha = 2b6563ef706ab0d926f304d2e030ee59d739a342（T007 已结项落地后的末端），git status 干净。tests/test_gate_t008_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在（V01 基线应失败）。T001–T005、T007 门禁 tests/test_gate_t00{1,2,3,4,5}_baseline.py 与 tests/test_gate_t007_baseline.py 都在，基线上应通过（回归）。
- T006 未落地（C10）：src/ 下没有 shell/、pages/、mock/、api.ts。因此 V02 不含 test_gate_t006，showcase-forms.test.tsx 现在渲染的 App 还不含 DiffShowcase。
- conftest.py:33–41：带 pipeline 夹具的前端流水线在全量 pytest 里默认跳过，点名运行文件或设 TT_FRONTEND_TESTS=1 才跑；门禁必须点名运行。
- T007 接口核对（C1–C12，在新基线 2b6563ef70 上逐条核对，报告 §8）：
  - C1：index.ts 导出 TextViewer 与 TextViewerProps，属性与 T007 合同第 8 条一致（title、pages、hasMore、onLoadMore、loadingMore、changed、onReload、onCopy、defaultLineNumbers、defaultWrap、className）。
  - C2：TextViewer 实际 DOM——根 div.tt-viewer（类含 tt-viewer、行号关时 tt-viewer--no-num、换行开时 tt-viewer--wrap、再拼 className）；头部 div.tt-viewer__head（标题 span.tt-viewer__title、工具 div.tt-viewer__tools 里两个文字按钮「行号」「换行」与复制 IconButton）；提示条 Banner（changed 时）；主体 div.tt-viewer__body（overflow-x: auto，是「放行的主体」）；行 div.tt-viewer__row（span.tt-viewer__num + div.tt-viewer__content）；底栏 div.tt-viewer__foot。现状没有任何 ref、滚动回调或插槽——所以日志跟随需要的 6 个属性必须新增（甲）。
  - C3：evidence/ansi.ts 导出 stripAnsi(text: string): string。
  - C4（丙用）：evidence/viewerLines.ts 的页转行函数是 pagesToLines(readonly ViewerPage[]): ViewerLine[]。甲不依赖它。
  - C5：icons/index.tsx 以 EyeOffIcon 结尾，Svg 包装未变；还没有 PauseIcon、FilterIcon、FileDiffIcon。
  - C6：index.ts 文件头注释写「共五片」，末尾是 NextStep 的导出。T007 的 evidence-static.test.ts（S1）断言 index.ts 含「共五片」且去掉注释后不出现 overlay/evidence；因此本片只在末尾追加，不改文件头注释（若改成「共七片」会让 T007 门禁 P1 变红）。
  - C7：EvidenceShowcase 的 7 个 data-demo 依次是 text-viewer、text-viewer-jsonl、safe-markdown、effort、masked-value、command-line、next-step。本片的 diff-view、log-follow 不与之及既有 16 个重复。
  - C8：T007 门禁（tests/test_gate_t007_baseline.py）里扫全 src 的静态检查是 test_s2_d12_no_forbidden_words_in_src（扫 src 下全部 ts/tsx 的禁用词）与 test_s3_d12_new_sources_rules（扫 6 个新组件 + evidence/ 源码：无 href、src=、target=，不渲染 role=status，不调 matchMedia/scrollIntoView/ResizeObserver/IntersectionObserver）；对 TextViewer 结构有 test_s5_d01_text_viewer_css_values（查 TextViewer.css 取值）与 test_d01_probe_w1_text_only、test_d02_probe_*（渲染 TextViewer 断言默认 DOM 与行为）。甲只加可选属性、不改 TextViewer.css、不传属性时 DOM 不变，才能让这些照常通过。T007 门禁的过渡断言是 test_transitional_s7（showcase-forms.css 与胶囊行）与 test_transitional_p9（EvidenceShowcase），本片不碰这些文件。
  - C9：T007 执行端测试里 evidence-static.test.ts 扫 components/icons/showcase 下 ts/tsx 的禁用词，并查 index.ts 的导出、文件头「共五片」、不导出 overlay/evidence；evidence-text-viewer.test.tsx 等渲染 TextViewer（默认行为不能变）。本片只追加、默认行为不变即无冲突。
  - C10：T006 未落地（见上）。
  - C11：package.json 依赖版本没变（见工具链）。
  - C12：TextViewer.css 里主体规则是 .tt-viewer__body { padding: var(--tt-space-2) 0; overflow-x: auto; }，没有 max-height、没有 overflow-y。LogFollow 要用 bodyClassName 加 max-height 480 与 overflow-y auto，必须用 .tt-log .tt-log__body（特异性 (0,2,0)）压过 .tt-viewer__body（0,1,0）。
- §11 假设核对（A1–A11，在新基线上）：
  - A1 成立（读 T007 v2 合同与 §8）。
  - A2 成立：scripts/pi_dispatch.py:3393–3394 用 git diff --binary --no-ext-diff --no-textconv --no-renames --full-index；:991 的 git 包装带 -c core.quotepath=off。
  - A3 成立：Switch 是 role=switch 的 span、受控、label 即名称、disabled 时不可聚焦；SegmentedControl 的选项只有 value、label；IconButton 必填 label、size sm 为 28、其余属性透传 button；Button 有 loading 与 loadingText；ChevronDownIcon、ChevronRightIcon 已有。
  - A4 成立：tokens.css 有 §2.8 列的令牌；--tt-diff-add、--tt-diff-del 在暗、亮、跟随系统三处都有。
  - A5 基本成立：base.css 的 tt-stack-narrow 在容器查询 max-width 807px 时改纵向（报告写「内容宽小于 808」，实际断点 807，功能一致）；tt-num 与焦点环都在。
  - A6 成立：G5（test_gate_t005_baseline.py）的 test_d12_new_sources_forbidden_things 扫 12 个新组件、field/*.tsx、showcase/*.tsx，source_rule_problems 查 role=status 与四个禁用接口；DiffShowcase 会被扫到。
  - A7 成立：showcase-forms.test.tsx:39–50 断言整页只有轻提示一个 role=status，且所有按钮有文字或 aria-label。
  - A8 成立：既有 data-demo 共 16 个（App.tsx 的 icon-button、menu、dialog、drawer、toast 5 个 + FormsShowcase.tsx 的 11 个），加 T007 的 7 个共 23 个；本片不撞。
  - A9：画布与文档出处照报告 §9 的引用；以设计稿为准，人工项 H1–H11 复核。
  - A10 成立：T006 未落地（见 C10）。
  - A11 成立：主工作区 .agent/runs/t003-desktop-fonts/attempt-001/candidate.patch 的 :1–5、:65–69、:184 是 git 实际产出的头；它被 Git 忽略，worktree 里没有。
- 仓库外事实（F1–F6，以站主/内核记录为准）：
  - F1 jsdom 25.0.1：scrollTop 可写、读回写进去的值、不夹范围；scrollHeight、clientHeight 恒为 0。
  - F2 react-dom 18.3.1：scroll 是不委托的事件，元素带 onScroll 时直接在该元素上挂监听，fireEvent.scroll 能触发 onScroll。
  - F3 @testing-library/dom 10.4.0：fireEvent.scroll 派发不冒泡、不可取消的 UIEvent，滚动监听要挂在滚动元素本身上。
  - F4 Vitest 2.1.8：useFakeTimers 不传参只假 setTimeout、clearTimeout、setInterval、clearInterval、setImmediate、clearImmediate、Date，不假 requestAnimationFrame 与 performance。
  - F5 git diff 常见头：diff --git、40 位 index 行、new file mode、--- /dev/null、+++ b/路径、@@ -a,b +c,d @@、以反斜杠开头的 No newline 标记行。
  - F6（站主在临时仓库实测，git 2.55.0）：带 --binary 时二进制文件写成 GIT binary patch 后跟两个块（先正向 literal N 或 delta N，再反向），每块是 base85 行、块后一个空行，之后直到下一个 diff --git 没有别的内容，没有 ---、+++ 行；不带 --binary 时写成 Binary files a/x and b/x differ，新文件是 Binary files /dev/null and b/x differ；删除的文件有 deleted file mode 100644、--- a/路径、+++ /dev/null；改名（-M）有 similarity index、rename from 旧、rename to 新，路径不带 a/、b/（candidate.patch 用 --no-renames 生成，实物里不会出现改名，改名按一删一增显示）；core.quotepath=off 时中文路径不加引号，含双引号、反斜杠或制表符的路径整个加引号、引号包住带 a/、b/ 前缀的整段、按 C 风格转义。解析规则 R3–R5 按此实现；二进制块整体跳到下一个 diff --git，两个块都覆盖。

## Scope
- allowed_modified_files:
  - desktop/web/src/components/index.ts
  - desktop/web/src/icons/index.tsx
  - desktop/web/src/components/TextViewer.tsx
- allowed_new_files:
  - desktop/web/src/components/DiffView.tsx
  - desktop/web/src/components/DiffView.css
  - desktop/web/src/components/diff/parseDiff.ts
  - desktop/web/src/components/diff/splitPairs.ts
  - desktop/web/src/components/LogFollow.tsx
  - desktop/web/src/components/LogFollow.css
  - desktop/web/src/showcase/DiffShowcase.tsx
  - desktop/web/src/showcase/showcase-diff.css
  - desktop/web/tests/diff-parse.test.ts
  - desktop/web/tests/diff-view.test.tsx
  - desktop/web/tests/diff-css.test.ts
  - desktop/web/tests/log-follow.test.tsx
  - desktop/web/tests/diff-showcase.test.tsx
  - desktop/web/tests/diff-static.test.ts
  - desktop/web/tests/text-viewer-slots.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - desktop/web/src/App.tsx
  - desktop/web/src/App.css
  - desktop/web/src/main.tsx
  - desktop/web/src/vite-env.d.ts
  - desktop/web/src/styles/**
  - desktop/web/src/domain/**
  - desktop/web/src/shell/**
  - desktop/web/src/pages/**
  - desktop/web/src/mock/**
  - desktop/web/src/api.ts
  - desktop/web/README.md
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/index.html
  - desktop/web/vite.config.ts
  - desktop/web/tsconfig.json
  - desktop/web/scripts/**
  - desktop/web/public/**
  - desktop/web/fonts/**
  - desktop/web/THIRD_PARTY_NOTICES.md
  - desktop/web/src/components/Button.*
  - desktop/web/src/components/Tag.*
  - desktop/web/src/components/StatusTag.*
  - desktop/web/src/components/Card.*
  - desktop/web/src/components/Banner.*
  - desktop/web/src/components/IconButton.*
  - desktop/web/src/components/Tooltip.*
  - desktop/web/src/components/Menu.*
  - desktop/web/src/components/Dialog.*
  - desktop/web/src/components/Drawer.*
  - desktop/web/src/components/Toast.*
  - desktop/web/src/components/SegmentedControl.*
  - desktop/web/src/components/Switch.*
  - desktop/web/src/components/Checkbox.*
  - desktop/web/src/components/Tabs.*
  - desktop/web/src/components/TextField.*
  - desktop/web/src/components/Select.*
  - desktop/web/src/components/Table.*
  - desktop/web/src/components/KeyValueList.*
  - desktop/web/src/components/EmptyState.*
  - desktop/web/src/components/Skeleton.*
  - desktop/web/src/components/ConnectionPill.*
  - desktop/web/src/components/Breadcrumb.*
  - desktop/web/src/components/TextViewer.css
  - desktop/web/src/components/SafeMarkdown.*
  - desktop/web/src/components/EffortPair.*
  - desktop/web/src/components/MaskedValue.*
  - desktop/web/src/components/CommandLine.*
  - desktop/web/src/components/NextStep.*
  - desktop/web/src/components/overlay/**
  - desktop/web/src/components/field/**
  - desktop/web/src/components/evidence/**
  - desktop/web/src/showcase/FormsShowcase.tsx
  - desktop/web/src/showcase/showcase-forms.css
  - desktop/web/src/showcase/EvidenceShowcase.tsx
  - desktop/web/src/showcase/showcase-evidence.css
  - desktop/web/tests/base-reset.test.ts
  - desktop/web/tests/component-css.test.ts
  - desktop/web/tests/connection-pill.test.tsx
  - desktop/web/tests/data-atoms.test.tsx
  - desktop/web/tests/dialog-scrim.test.tsx
  - desktop/web/tests/dialog.test.tsx
  - desktop/web/tests/drawer.test.tsx
  - desktop/web/tests/evidence-atoms.test.tsx
  - desktop/web/tests/evidence-effort.test.tsx
  - desktop/web/tests/evidence-markdown.test.tsx
  - desktop/web/tests/evidence-showcase.test.tsx
  - desktop/web/tests/evidence-static.test.ts
  - desktop/web/tests/evidence-text-viewer.test.tsx
  - desktop/web/tests/font-specimen.test.tsx
  - desktop/web/tests/forms-patches-css.test.ts
  - desktop/web/tests/forms-patches.test.tsx
  - desktop/web/tests/icon-button.test.tsx
  - desktop/web/tests/menu.test.tsx
  - desktop/web/tests/segmented-control.test.tsx
  - desktop/web/tests/showcase-forms.test.tsx
  - desktop/web/tests/showcase-overlays.test.tsx
  - desktop/web/tests/skeleton.test.tsx
  - desktop/web/tests/status-tag-patches.test.tsx
  - desktop/web/tests/status-tag.test.tsx
  - desktop/web/tests/switch-checkbox.test.tsx
  - desktop/web/tests/table.test.tsx
  - desktop/web/tests/tabs.test.tsx
  - desktop/web/tests/text-field-select.test.tsx
  - desktop/web/tests/toast-close-tooltip.test.tsx
  - desktop/web/tests/toast.test.tsx
  - desktop/web/tests/token-contract.test.ts
  - tests/test_gate_*.py
  - tests/test_gate_t008_*.py
  - tests/conftest.py
  - tests/test_attempt_states.py
  - tests/test_desktop_attempt_states.py
  - .gitignore
  - docs/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 公共约定（§5.0）
- 沿用 T005、T007：键盘看 event.key，处理了的键都 preventDefault，Esc 例外；尺寸字面量同一行注释；颜色、字体、圆角、阴影、层级只用令牌；间距没有对应刻度时就近取 --tt-space-*、平局取小。
- 新组件、diff/ 与 DiffShowcase 都不渲染 role=status、对话框、菜单；都不调用 matchMedia、scrollIntoView、ResizeObserver、IntersectionObserver。
- 不可信文字（补丁的路径、片段头、行内容，日志的行）只作 React 的文本子节点；证据文字除 title 外不进任何属性。
- DiffView.tsx、LogFollow.tsx、diff/ 的源码里不出现 href、src=、target=，也不出现禁用词（dangerouslySetInnerHTML、innerHTML、outerHTML、insertAdjacentHTML、eval(、new Function、document.write、srcdoc、createContextualFragment、DOMParser）。
- 来自补丁的文字显示前都用 T007 的 stripAnsi（src/components/evidence/ansi.ts）去掉 ANSI，不自己再写一份。
- id 用 React 18 的 useId。
- W4 的坑（token-contract.mjs 只剥块注释、字符串也扫）：新代码与演示文字里不出现井号加 3/4/6/8 位十六进制颜色、不出现 rgb(/color(/lab( 这类颜色函数名紧跟括号、不拼接 --tt- 前缀、不写 role 等于 status 的属性写法。
- 尺寸字面量出处：handoff 的取值写 handoff 行号，画布写简称加行号，规划端定的写「规划端定」，演示写「演示自定」。

### 1. parseDiff（diff/parseDiff.ts）与 splitPairs（diff/splitPairs.ts）（§5.1）
数据形状（字段名建议）：
- DiffFile：oldPath（字符串或 null）、newPath（字符串或 null）、status（modified、added、deleted、renamed）、binary（布尔）、hunks、additions、deletions。
- DiffHunk：header（整行）、oldStart、oldLines、newStart、newLines、lines。
- DiffLine：kind（context、add、del）、text（去掉行首标记的内容，原样，不去 ANSI）、oldNo、newNo（没有就是 null）、noNewline（布尔）。

规则：
- R1 切行：按换行符（U+000A）切；每行去掉一个末尾的回车符（U+000D）；文本以换行符结尾时末尾的空串不算一行。
- R2 文件：以 diff --git 加一个空格开头的行开始一个新文件，任何状态下都是（内容行总以空格、加号、减号或反斜杠开头，不会以 d 开头）。第一个 diff --git 之前的行忽略。
- R3 文件头（第一个片段之前）：new file mode 开头→added；deleted file mode 开头→deleted；rename from X、rename to Y→旧、新路径（按 R5 解码，不去前缀），renamed；--- X、+++ Y→旧、新路径（按 R5 解码，再去掉一个 a/ 或 b/ 前缀；/dev/null 记为 null）；以 Binary files 开头、以 differ 结尾→binary；以 GIT binary patch 开头→binary，之后直到下一个 diff --git 的行都跳过；以 @@ 开头→片段（R6）；其他（index、similarity index、old mode、new mode 等）忽略。
- R4 没有 ---、+++、rename 行时（二进制、只改权限、空文件），路径取自 diff --git 行的余下部分：以双引号开头时依次读两个带引号的路径（R5），各去 a/、b/；否则形如 a/P b/P 且两段 P 相同就取 P（按长度算中点，不用正则）；否则在第一个空格加 b/ 处切开；---、+++、rename 行给的路径优先。
- R5 路径解码：以双引号开头的去掉两端引号，按 C 风格还原转义（反斜杠后跟反斜杠、双引号、a、b、f、n、r、t、v 之一，或跟三位八进制数字即一个字节；八进制字节按 UTF-8 解码，解不出的用替换字符）；不带引号的截到第一个制表符为止。
- R6 片段头：@@ -a[,b] +c[,d] @@ 加可有可无的余下文字；b、d 缺省为 1；用不回溯的写法解析（手写扫描，或锚定开头、没有嵌套量词的正则）；不合格的 @@ 行忽略。
- R7 片段里：还有剩余行数时，空格开头为 context（旧、新行号各加一），加号为 add（新行号），减号为 del（旧行号，哪怕以 --- 开头），反斜杠开头的给本片段上一行记 noNewline、不计数，空行为 context、内容为空（容忍去掉了行尾空格的补丁），其他行片段结束、按 R2、R3 处理这一行；剩余行数用完后，反斜杠行照样记给上一行，@@ 开始下一片段，diff --git 开始下一个文件，其他行忽略。
- R8 状态：added（new file mode，或旧路径为 null）；deleted（deleted file mode，或新路径为 null）；renamed（有 rename 行，或新旧路径都在且不同）；其余 modified。
- R9 计数：additions、deletions 只数片段里的 add、del；二进制为 0。
- R10 性能：线性；1 MiB 的病态输入 2 秒内返回（一条 1 MiB 长行；2 万个只有 diff --git 头的文件；一个片段头写着很大的行数、后面只有几行；1 MiB 的反斜杠行）。
- 显示用的路径（在 DiffView 里算）：deleted 用 oldPath，其余用 newPath；renamed 的文件头写「oldPath → newPath」。
splitPairs（分屏的行）：输入一个片段的 lines，输出行的列表：context 左右都是这一行；连续的非 context 行算一段，段内 del 按顺序、add 按顺序，第 k 个 del 配第 k 个 add，多出来的一侧为空。与 Attempt 画面 :486–503 的写法（先删后增成段配对）在 git 输出上结果相同。

### 2. DiffView（差异视图，7.14）（§5.2）
API：patch: string；title?: string；truncated?: boolean、onLoadMore?: () => void、loadingMore?: boolean（规划端补，可删）；defaultMode?: 'unified' | 'split'（缺省 unified）；defaultWrap?: boolean（缺省 false，handoff :149）；className?。
结构（类名与 data-* 建议）：
- 根 div.tt-diff，带 data-mode（unified、split）与 data-wrap（true、false）。
- 工具栏 div.tt-diff__bar：摘要 span.tt-diff__summary（FileDiffIcon 16、aria-hidden；title 有才显示、mono-sm；N 个文件、+A、−D；减号是 U+2212；空白折叠后整段如「candidate.patch · 4 个文件 · +160 −2」，没有 title 时去掉第一段）；SegmentedControl（aria-label 为「差异显示方式」，选项「统一」unified、「分屏」split）；Switch（label「自动换行」）。
- 没有文件时：只有工具栏与 div.tt-diff__empty「补丁里没有改动」，不渲染列表。
- 主区 div.tt-diff__main，另带 base.css 的 tt-stack-narrow（详情页 :398；内容宽小于 808 时上下堆叠）。
- 文件列表 ul.tt-diff__files（aria-label「文件」），每项 li 里一个 button.tt-diff__file-item（type=button）：当前文件带 aria-current=true，其他不带；span.tt-diff__file-path（title 为显示路径）里再套一层 span 放显示路径（左截断）；文本文件：tt-num 的 +A 与 −D；二进制：「二进制」。
- 文件 section.tt-diff__file，带 data-status、data-binary、data-collapsed：头 div.tt-diff__file-head（tabIndex=-1）：文本文件有折叠钮（IconButton，label「折叠」或「展开」；aria-labelledby 为自己 id 加路径 span 的 id；aria-expanded；aria-controls 指向主体；图标 ChevronDownIcon 或 ChevronRightIcon 14）；路径 span.tt-diff__file-name（带 id 与 title）；注记 span.tt-diff__file-note（按顺序用「 · 」连接：added「新文件」、deleted「已删除」、折叠着「已折叠」、truncated 时最后一个文件「未读完」，为空不渲染）；文本文件的 +A、−D（tt-num）。主体 div.tt-diff__file-body（带 id）：折叠时带 hidden 属性、不渲染行（元素始终在，aria-controls 不悬空）；二进制没有折叠钮，主体是「二进制文件，不显示内容」；没有片段的文本文件是「没有内容改动」。
- 行容器 div.tt-diff__table，行 div.tt-diff__row：统一视图每片段先一行 data-kind=hunk（文字是整行片段头），之后每行 data-kind 为 context、add、del；四格：旧行号、新行号（span.tt-diff__no，aria-hidden，tt-num）、符号 span.tt-diff__sign、文字 span.tt-diff__text；分屏片段头一行 data-kind=hunk（一格占满），其余每行 data-kind=pair 六格，每格带 data-side（left、right）与 data-kind（context、del、add、empty）；行号 context 两侧都有、add 只有新、del 只有旧、空侧什么都没有；符号 add 为加号、del 为 −（U+2212）、其余为空，符号格不设 aria-hidden（读屏能读到增删）、不可选中；noNewline 的行文字后加 span.tt-diff__eof「（文件末尾没有换行）」；补丁原文里的反斜杠标记行不出现在 DOM 里。
- 没读完：truncated 时根元素末尾有 div.tt-diff__foot「补丁没有读完，只显示了已读到的部分」；给了 onLoadMore 就有 Button（secondary、sm）「继续加载」；loadingMore 时用 Button 的 loading，文字「正在加载…」。
行为：折叠缺省——added 的文本文件折叠，其余展开；二进制没有折叠；折叠状态按序号加显示路径记，patch 变化后这两样都没变的文件保持原状态、其余按缺省。当前文件缺省第一个；patch 变化后序号越界就回到第一个；点列表项：设为当前、折叠着就展开、焦点移到这个文件的头。切模式、切换行只改 data-mode、data-wrap 与行的结构，不重置折叠与当前文件。
样式（括号里是出处；没写出处的都用令牌）：
- 根：--tt-surface-1、1px --tt-border、--tt-radius-lg、overflow hidden（详情页 :387）。
- 工具栏：flex、可换行、垂直居中；间距 --tt-space-2 与 --tt-space-3；内边距 --tt-space-2 与 --tt-space-3；下边框（详情页 :388）。摘要 --tt-text-sm、--tt-text-2，标题 --tt-mono-sm；加号计数 --tt-tone-success-fg，减号计数 --tt-tone-danger-fg（详情页 :389）；分段靠右（margin-left auto）。
- 文件列表：宽 260（handoff :149）、flex none、右边框、内边距 --tt-space-1（画布 6，平局取小）、纵向、间距 --tt-space-0_5、无列表符（详情页 :399）。
- 列表项：宽 100%、最小高 32（详情页 :401）、flex、间距 --tt-space-2、内边距 --tt-space-1 与 --tt-space-2、无边框、--tt-radius-md、透明底、--tt-text-1、左对齐；当前项 --tt-surface-selected；悬停 --tt-surface-3。路径：flex 1、min-width 0、--tt-mono-sm、overflow hidden、text-overflow ellipsis、white-space nowrap、direction rtl、text-align left；里层 direction ltr、unicode-bidi isolate。计数 --tt-mono-sm；「二进制」--tt-text-caption、--tt-text-3。
- 文件区：flex 1、min-width 0、纵向、间距与内边距 --tt-space-3（详情页 :404）。文件卡片：1px --tt-border、--tt-radius-md、overflow hidden。
- 文件头：flex、垂直居中、间距 --tt-space-2、高 36、内边距左 --tt-space-2（画布 10，平局取小）右 --tt-space-1（画布 6）、--tt-surface-2、下边框；折叠时没有下边框；二进制左内边距 40（详情页 :458）。折叠钮由 .tt-diff__file-head .tt-icon-btn（特异性 (0,2,0)，高于 IconButton 单类规则）缩成 24、--tt-radius-sm、图标 14（详情页 :408）。路径 --tt-mono-sm、单行、右侧省略（详情页 :409）；注记 --tt-text-caption、--tt-text-3。
- 文件主体：overflow-x auto（详情页 :412）。二进制、没有内容改动、补丁里没有改动这几种说明：内边距 --tt-space-3 与 --tt-space-4、--tt-text-sm、--tt-text-3（详情页 :461）。
- 行：--tt-mono-md；统一 grid-template-columns 为 44px 44px 18px minmax(0, 1fr)、行最小宽 560；分屏为 44px 18px minmax(0, 1fr) 44px 18px minmax(0, 1fr)、行最小宽 760（handoff :149；详情页 :414–416、:426–430）。
- 换行关：表格 width max-content、min-width 100%，文字 white-space pre；换行开：文字 white-space pre-wrap、word-break break-all（详情页 :420）。
- 底色：统一视图 add 行 --tt-diff-add、del 行 --tt-diff-del；hunk 行 --tt-surface-2、文字 --tt-text-3；context 透明。分屏按格：del 格 --tt-diff-del、add 格 --tt-diff-add、empty 格 --tt-surface-2（handoff :149）；左侧文字格右边框 1px；分屏的 hunk 行左内边距 --tt-space-3、white-space pre（详情页 :428）。
- 行号：右对齐、右内边距 --tt-space-2、--tt-text-3、不可选中；统一视图的新行号格右边框 1px（详情页 :418）。符号：居中、字重 600（详情页 :419）、不可选中；add --tt-tone-success-fg，del --tt-tone-danger-fg。文字：右内边距统一 --tt-space-3、分屏 --tt-space-2（详情页 :420、:433）；eof 注记 --tt-text-3、左外边距 --tt-space-1、不可选中。
- 底部（没读完）：--tt-surface-2、上边框、内边距 --tt-space-2 与 --tt-space-3、--tt-text-caption、--tt-text-3，按钮靠右（与 T007 查看器的底栏相同）。

### 3. LogFollow（日志跟随，7.15）（§5.3）
API：TextViewer 的全部属性（§5.4 的 6 个除外，由本组件控制），另加 defaultFollow?: boolean（缺省 true）、followDisabledReason?: string（非空时跟随不可用）。
结构（甲）：渲染一个 TextViewer——className 前面加 tt-log；bodyClassName 为 tt-log__body；bodyRef、onBodyScroll 接自己的处理；filter 为过滤框的值。headerExtra：label.tt-log__filter（FilterIcon 14、aria-hidden，加 input.tt-log__filter-input：type=text、aria-label「过滤事件」、placeholder「按文字包含过滤…」、受控）；span.tt-log__follow（disabled 时 title 为原因）包着 Switch，label「跟随」，following、paused 时 checked，disabled 状态下 Switch 禁用。bottomBar：div.tt-log__status（带 data-follow），按状态——following「正在跟随最新内容」；paused：PauseIcon 16（aria-hidden）、「已暂停跟随：你在往上看」、Button（secondary、sm）「回到底部」；off「已关闭跟随」；disabled：原因文字。不设 role、不设 aria-live。
状态机（d = scrollHeight − scrollTop − clientHeight；贴底 = d ≤ 40；计时 150ms）：
- following→paused：主体滚动事件里 scrollTop 比上次记下的小（往上滚）且 d > 40，同时开始 150ms 计时。
- paused 中每个滚动事件都重新计时 150ms；到时 d ≤ 40 回 following，否则保持 paused。
- paused→following：点 [回到底部] 立即；焦点移到「跟随」开关里的 role=switch 元素（Switch 不转发 ref，从外层容器找）。
- 开关关→off；开关开→following。followDisabledReason 非空→disabled；变回空→following。
- 进入 following 时，以及 following 中 pages 或过滤变化之后（useLayoutEffect），滚到底：scrollTop = scrollHeight，再记下 scrollTop。
- 每个滚动事件之后、每次程序滚动之后都记下当时的 scrollTop。看方向而不是只看距离（程序滚到底后浏览器才派发 scroll 事件，期间又追加内容时 d 可能已大于 40）。
- 计时只用 setTimeout（不用 requestAnimationFrame 与 performance.now）；卸载时清掉计时器。常量 40、150 写在 LogFollow.tsx，同一行注释 UI 文档 7.15 :910。
- 过滤：空串不过滤；否则做不分大小写的子串包含（两边 toLowerCase）；匹配的是分片拼好、去掉 ANSI 之后的整行文字；隐藏行不显示、行号保持原值、复制只含显示的行；一行也没有时主体显示「没有匹配的行」；「已显示 N 页」不变；行尾的 [继续加载] 跟着那一行，那一行被滤掉时不显示，底栏的照常。
样式：.tt-log__body max-height 480（规划端定，约 24 行）、overflow-y auto；若被 T007 的规则盖掉，用 .tt-log .tt-log__body 提高特异性（§8 C12）。过滤框（详情页 :636–639）：外层 position relative、flex 0 1 360px、min-width 200；图标 position absolute、left 10、top 9、--tt-text-3；输入框宽 100%、高 32、内边距右 --tt-space-2（画布 10）左 --tt-space-8（画布 30，就近 32）、1px --tt-border-strong、--tt-radius-md、--tt-surface-1、--tt-text-1、--tt-text-sm。跟随：inline-flex，与过滤框间距 --tt-space-2。底部状态：flex、垂直居中、间距 --tt-space-2（画布 10，平局取小）、内边距 --tt-space-2 与 --tt-space-3、上边框；following、off、disabled 用 --tt-surface-2、--tt-text-3、--tt-text-caption；paused 用 --tt-tone-neutral-bg、--tt-tone-neutral-fg、--tt-text-sm（领域板 :380；handoff :215 改成 neutral），按钮靠右。

### 4. TextViewer 的 6 个可选属性（§5.4，甲；站主 Q1 选甲）
- 只给 src/components/TextViewer.tsx 加 6 个可选属性，只加不改：bodyRef?: Ref<HTMLDivElement>（指向放行的主体元素 div.tt-viewer__body）、onBodyScroll?: (event: UIEvent<HTMLDivElement>) => void（挂在同一个元素的 onScroll 上）、bodyClassName?: string（加在同一个元素的 class 上）、headerExtra?: ReactNode（头部最右端，复制钮之后）、bottomBar?: ReactNode（主体与底栏之间，占满宽度，不随主体滚动）、filter?: string（§3 的过滤规则）。
- 一个都不传时，DOM 与行为同 T007 合同第 8 条（不多渲染包装元素）；不改 TextViewer.css 与 evidence/**；不改已有属性的行为。
- 在 T007 落地后的版本（新基线上的 TextViewer.tsx）上改。终审按差异核对本文件只加了这 6 个可选属性、没动别的。

### 5. 图标与导出（§5.5）
- 图标追加在 icons/index.tsx 末尾，沿用模块内 Svg 包装，fill、stroke 不写别的取值（G2 test_g8_icons_dir）：PauseIcon（领域板 :381，两个 rect：width=4 height=14 x=6 y=5 rx=1；width=4 height=14 x=14 y=5 rx=1）；FilterIcon（详情页 :638，polygon points=22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3）；FileDiffIcon（详情页 :389，四条 path：M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z、M9 10h6、M12 13V7、M9 17h6）。折叠钮用已有的 ChevronDownIcon、ChevronRightIcon（T005）。追加的那一段注释写「路径照画布」。
- index.ts 末尾追加一行注释「第 7 片：差异视图（7.14）与日志跟随（7.15）」，再导出 DiffView、DiffViewProps、LogFollow、LogFollowProps；不改文件头注释与已有的行（C6）；去掉注释后仍不出现 overlay（G4、G5 的检查）。diff/ 的两个模块不从 index 导出（同 T007 的 evidence/）。

### 6. DiffShowcase（演示）（§5.6）
- 默认导出一个组件，渲染两节 section.showcase__section（带 data-demo），每节一个 h2.showcase__h2；样式在 showcase-diff.css，复用 App.css 的 showcase__* 类；不挂到陈列页（T006 落地后自动收进）。data-demo：diff-view、log-follow（不与已有 16 个与 T007 的 7 个重复）。
- diff-view 节：一个 DiffView，title 为 candidate.patch，补丁至少有——改动文件两个片段（有上下文、成段的删与加、只删、只加）；新文件（缺省折叠）；删除的文件，其中一行内容以 -- 开头（补丁里是以 --- 开头的删除行）；改名文件（rename from、rename to，相似度 100%，没有片段）；二进制新文件（GIT binary patch 加 literal 0 块）；超长行（运行时拼出 2000 字符以上）；一个文件里有 <script>alert(1)</script>、<img src=x onerror=alert(1)>、带 ANSI 颜色（ESC 加 [31m 与 ESC 加 [0m）的行、一个网址，最后一行带 No newline 标记；可选第二个 DiffView 演示 truncated 与 [继续加载]。
- log-follow 节：一个 LogFollow，title 为「ui-readonly-api / events.jsonl」；初始页取 UI 文档 9.4 :1203–1210（含 not_json、too_long 与第 6 行第 1/2 片），加第 6 行第 2/2 片与之后 30 行左右事件，其中有一行 <script>alert(1)</script>、一行带 ANSI、一条超长行；按钮 [开始追加]（setInterval 每 400ms 追加一行，演示自定；追加到 500 行自己停）、[停止追加]、[模拟 attempt 已结束]（切换 followDisabledReason「attempt 已结束，没有新事件」）；计时器只在点了之后跑、卸载时清掉；复制照 T007 演示的做法（有 navigator.clipboard 就写进去，旁边显示「已复制 N 个字符」「复制失败」「这个环境没有剪贴板接口」，不用轻提示）。
- §2.9 的约束都要满足（W4 十六进制/颜色函数、禁用词、role=status、四个接口、字体扩展名、ServerIcon、主题按钮探针）；演示的二进制块只用 literal 0 与不含井号的 base85 行；ANSI 的 ESC 用 Unicode 转义写；样式里的尺寸写「演示自定」。

### 门禁断言（§7.3、§7.4；门禁端定稿写进 tests/test_gate_t008_baseline.py）
静态（S，全量 pytest 也跑）：
- S1：新文件都在；index.ts 的基线内容是前缀，新导出 DiffView、DiffViewProps、LogFollow、LogFollowProps 都在，旧导出都在。
- S2：icons/index.tsx 的基线内容是前缀；三个图标的元素与属性等于画布那几行（领域板 :381；详情页 :638、:389）。
- S3：src 全文没有 §5.0 的禁用词（与 T007 S2 相同）；新组件与 diff/ 没有 href、src=、target=、role=status、四个接口；DiffShowcase 没有 role 等于 status 的写法与四个接口名。
- S4：CSS 取值——文件列表宽 260；两种 grid-template-columns；行最小宽 560 与 760；换行的两种 white-space；add、del、hunk、empty 的底色令牌；hunk 文字 text-3；符号颜色与字重；列表路径的 rtl 与里层 isolate；文件头 36；折叠钮 24；跟随主体的限高 480 与 overflow-y；暂停状态的 neutral 色调。
- S5：新 CSS（含 showcase-diff.css）只用令牌（层级、圆角、阴影、字体），除 0 与 1px 外的 px 字面量带同一行注释。
流水线（P）：
- P1：npm 四步退出 0；npm test 没有失败、跳过、待办。
- P2：解析，即 D01（纯函数探针）。P3：统一视图、文件列表、折叠、二进制、摘要、没读完，即 D02、D04、D06。P4：分屏，即 D03。P5：W1 同款探针，即 D05。P6：跟随状态机，即 D07。P7：过滤，即 D08。P8（甲）：TextViewer 的可选属性，即 D09。P9（过渡）：渲染 DiffShowcase，即 D11。
- P10：流水线前后 git status 不变、gate-probe/ 清掉；受监视文件摘要不变（package.json、锁文件、index.html、vite.config.ts、tsconfig.json、tokens.css、fonts.css、base.css、main.tsx、App.tsx、App.css；甲时加 TextViewer.tsx、TextViewer.css 不变）。
- 探针沿用 T002–T007 的做法；组件探针与演示探针分开跑；探针名带 t008。
过渡断言（§7.4）：新增 P9 一条，按 test_transitional_ 命名，docstring 第一行「陈列页的演示改版（整理陈列页或换成真实页面）时推翻」。长期断言：解析、组件行为、CSS 取值、静态检查、图标、导出。不推翻现有断言（T003–T005 的已在 8214a1f 退役；T007 的 S7、P9 管 showcase-forms、EvidenceShowcase，本片不碰）。

### 执行端测试（§7.2）
- 写法沿用 T005、T007：render、act、fireEvent、cleanup 从 @testing-library/react 导入，不加 user-event；beforeEach 开假计时器，afterEach 还原；推进时间包在 act 里；样式断言读 CSS 文本，用 process.cwd() 定位；性能用例不开假计时器，用 Date.now() 计时。
- 滚动（F1–F3）：jsdom 不排版。测试给主体打桩 scrollHeight、clientHeight（实例上 Object.defineProperty，或渲染前在 HTMLElement.prototype 上按类名打桩，用完还原）；scrollTop 可直接写、读回原值；要像浏览器那样夹住时再给 scrollTop 打一个夹到 0 与 scrollHeight − clientHeight 之间的桩。滚动用 fireEvent.scroll(主体)（scroll 不冒泡，监听要挂在滚动元素本身）。
- 假计时器（F4）：跟随的 150ms 只能用 setTimeout；useFakeTimers 不假 requestAnimationFrame 与 performance。
- 文件：diff-parse.test.ts、diff-view.test.tsx、diff-css.test.ts、log-follow.test.tsx、diff-showcase.test.tsx、diff-static.test.ts；甲另有 text-viewer-slots.test.tsx。新测试不用 skip、only、todo。

## Steps
1. 预检（只读）：核对本合同的 Repository facts（C1–C12、A1–A11）与基线；不符就停并报告。范围：不改文件。
2. 解析纯函数：diff/parseDiff.ts、diff/splitPairs.ts、tests/diff-parse.test.ts（§1 的 R1–R10 与分屏配对）。验收：P2（D01）。风险：以 --- 开头的删除行当成文件头、二进制块没跳干净、留下回车符、用会回溯的正则。
3. 图标：icons/index.tsx 末尾追加 PauseIcon、FilterIcon、FileDiffIcon（§5）。验收：S2；G2 test_g8_icons_dir 照常通过。风险：动到已有图标。
4. 差异视图主体：DiffView.tsx、DiffView.css、tests/diff-view.test.tsx（工具栏、文件列表、文件卡片、统一视图、折叠、二进制、没读完，§2）。验收：P3、P5（D02、D04、D05）。风险：新文件没折叠、折叠后 aria-controls 悬空、路径进了 aria-label。
5. 分屏与换行：DiffView.tsx、DiffView.css、tests/diff-view.test.tsx、tests/diff-css.test.ts（§1 配对、§2 分屏与换行样式）。验收：P4、S4（D03、D06）。风险：配对错位、空侧没有标记。
6. （甲）TextViewer 的可选属性：TextViewer.tsx、tests/text-viewer-slots.test.tsx（§4）。验收：P8（D09）；T007 门禁（V02）与 T007 执行端测试照常通过。风险：不传属性时多渲染了元素、顺手改了别的行为。
7. 日志跟随状态机：LogFollow.tsx、LogFollow.css、tests/log-follow.test.tsx（§3）。验收：P6（D07）。风险：只看距离不看方向、计时用 requestAnimationFrame、卸载没清计时器、[回到底部] 之后焦点丢失。
8. 过滤：LogFollow.tsx（甲另有 TextViewer.tsx）、tests/log-follow.test.tsx（§3 过滤）。验收：P7（D08）。风险：在去 ANSI 或拼分片之前匹配、改了行号。
9. 导出：index.ts 末尾（§5）。验收：S1；G2–G5 与 T007 门禁的导出检查照常通过。风险：改了已有的行、改了文件头「共五片」。
10. 演示：DiffShowcase.tsx、showcase-diff.css、tests/diff-showcase.test.tsx（§6）。验收：P9（过渡，D11）、S3；W4。风险：演示文字踩到 §2.9 的检查、计时器自己启动。
11. 静态测试：把 §2.9、§5.0 的规则写成执行端测试，tests/diff-static.test.ts。验收：S3、S5（D12）。风险：只扫本片文件，漏了全 src 的禁用词。
12. 自检：在 desktop/web 下依次跑 npm ci（要网络）、npm run build、npm test、npm run check:contract；在仓库根点名跑 V01、V02、V03；git status 里没有新的未忽略文件。风险：V02 份数多、费时，先跑快的。

## Setup
无。本合同的 prepare setup 为空；npm ci 只在门禁 pytest 与执行端自检里跑（与 T002–T007 相同）。

## Validation commands
- V01（必要，基线应失败）：`python -m pytest tests/test_gate_t008_baseline.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V02（必要，基线应通过）：`python -m pytest tests/test_gate_t001_baseline.py tests/test_gate_t002_baseline.py tests/test_gate_t003_baseline.py tests/test_gate_t004_baseline.py tests/test_gate_t005_baseline.py tests/test_gate_t007_baseline.py -q` · cwd：仓库根 · 超时：1800s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V03（必要，基线应通过）：`python -m pytest tests/test_desktop_attempt_states.py tests/test_attempt_states.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配：`\d+ passed`
说明：V01 的 tests/test_gate_t008_baseline.py 由门禁端稍后写好、内核做成基线提交，基线上不存在（基线应失败）。V02 合并 T001–T005、T007 六份门禁回归，点名运行以让前端流水线不被 conftest 跳过（T006 未落地，不含 test_gate_t006）。V03 是桌面端状态表与调度器 ATTEMPT_STATES 的回归（本片不改状态表，基线应通过）。门禁要点名运行，conftest 才不会跳过前端流水线（tests/conftest.py:33–41）。

## Definition of done
- D01：解析——三个文件的补丁顺序、路径、状态、计数都对；新文件（new file mode、--- /dev/null、@@ -0,0 +1,3 @@）added、新行号 1 到 3；删除（deleted file mode、+++ /dev/null）deleted、显示旧路径；改名（rename from、rename to，无片段；另一例带片段）renamed；二进制两种写法（Binary files 那一行；GIT binary patch 加 literal 块，块后的下一个文件照常解析）；No newline 标记不计数、不推进行号、记在上一行；CRLF 与 LF 结果逐项相同、内容不带回车符；以 ---、+++ 开头的内容行分别算删除、新增；@@ -1 +1 @@ 行数缺省为 1、多个片段各自从片段头起算；空串与乱码返回空列表；R10 病态输入 2 秒内返回；证据：V01；目的：补丁是不可信内容，解析要稳且快。
- D02：统一视图——行的顺序与 data-kind；两列行号按 kind 有无；加号与 −（U+2212）；片段头整行文字；摘要整段文字；文件头的路径、注记、计数；证据：V01。
- D03：分屏——配对（两删三加得三行，第三行左侧 empty）；左侧 del、context、empty，右侧 add、context、empty；两侧行号；片段头一格占满；证据：V01。
- D04：折叠与列表——新文件 aria-expanded false、主体 hidden、没有行、注记「新文件 · 已折叠」，点开后有行、注记「新文件」；其他文本文件缺省展开；二进制没有折叠钮、有说明文字；没有片段的文件写「没有内容改动」；aria-controls 指向存在的元素；折叠钮的 aria-labelledby 含自己与路径；列表的计数、二进制、title、两层 span；缺省第一个是当前；点折叠着的新文件后它变成当前、展开、焦点在它的头上；证据：V01。
- D05：只按文本显示——行与路径里有 <script>alert(1)</script>、<img src=x onerror=alert(1)>、ESC[31m 与 ESC[0m 包着的文字、网址；DiffView 里没有 script、img、a 元素；文字原样；ESC 字符与 [31m 不出现；路径除文字外只出现在 title；目的：不可信内容不执行；证据：V01。
- D06：模式与换行——缺省 unified、换行关；切换后 data-mode、data-wrap 变，折叠与当前文件不变；CSS 的两种 white-space；证据：V01。
- D07：跟随（假计时器）——挂载后、following 中追加页后滚到底；往上滚且 d > 40 暂停；往上滚但 d ≤ 40 不暂停；scrollTop 没变小（内容变长）时即使 d > 40 也不暂停；paused 中追加页不滚动；d 为 40 时 149ms 仍 paused、150ms 恢复并滚到底；d 为 41 时过了 150ms 仍 paused；第二次滚动重新计时；[回到底部] 立即恢复并滚到底、焦点到开关；开关关 off、追加不滚，开关开 following、滚到底；原因非空 disabled、开关 aria-disabled 且不可聚焦、title 与底部文字都是原因、追加不滚；四种状态的文字与 data-follow；卸载后没有挂起的计时器；证据：V01；目的：快速追加时跟随不自己停。
- D08：过滤——不分大小写；拼好分片、去掉 ANSI 后匹配；隐藏行不显示；行号不变；没有匹配时的提示；清空后还原；复制只含显示的行；「已显示 N 页」不变；证据：V01。
- D09：（甲）TextViewer 的可选属性——不传时与 T007 合同第 8 条结构相同（T007 门禁兜底）；bodyRef 指向放行的元素；onBodyScroll 收到该元素的 scroll；bodyClassName 在该元素上；headerExtra 在复制钮之后；bottomBar 在主体与底栏之间；filter 按 §3 过滤且不改行号；证据：V01、V02。
- D10：图标与导出——三个图标的属性等于画布；icons/index.tsx 与 index.ts 只在末尾追加（行尾归一后基线内容是新内容的前缀）；新导出四项都在、旧的都在；证据：V01。
- D11：演示（过渡）——两节都在、data-demo 不重复；diff-view 节有 §6 的各类文件、新文件折叠、W1 样例只是文字；log-follow 节有 LogFollow；没有 role=status、对话框、菜单；没有文字的按钮都有 aria-label；节标题不含 Button；按钮文字避开主题字样；挂载后没有计时器在跑、点 [开始追加] 后推进时间会追加行、卸载后计时器清空；证据：V01。
- D12：静态——§2.9 与 §5.0 的禁用词与写法；新组件与 diff/ 的源码没有 href、src=、target=、role=status、四个接口；新 CSS 只用令牌，除 0 与 1px 外的 px 字面量带同一行注释；W4 通过；证据：V01。
- D13：回归——T001–T005、T007 门禁全绿；V03 通过；npm 四步退出 0；证据：V02、V03、V01。
- D14：范围——只改允许的文件；不改依赖；既有测试不改；新测试不用 skip、only、todo；证据：scope、V02。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续（尤其 App.tsx、App.css、main.tsx、tokens.css、package.json、锁文件、T007 其他组件与 evidence/**、tests/test_gate_t008_*.py）。
- 需要新增或升级依赖、写 .npmrc、装全局包、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 7200
- max_wall_seconds_total: 21600
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）。
- 时间分配：调查约 15 分钟、实现与补测约 65 分钟、必要检查约 30 分钟、最终报告约 10 分钟；总计不超过单轮 7200 秒。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01 到 D14，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务、不读取或输出凭据。
