# TASK: t003-desktop-fonts

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: 69970b0151cf656f01b2bddaf745f79dc04cd2c3
- risk_level: medium
- authorized_actions: local_edit, local_test, network
- integration_actions: local_branch, merge
- executor: step/step-5-preview · thinking high

## Goal
交付 T003 第 2 片（桌面端前端随包字体）：在 `desktop/web/` 用 `src/styles/fonts.css` 的两条 `@font-face` 接入随包字体等距更纱黑体 SC 0.36.0，让 `dist` 里恰有与 `desktop/web/fonts/` 逐字节相同的两个 woff2、OFL 许可原文随产物发出、陈列页加一块中英文对齐样张；不改依赖、不改令牌、不改字体文件。

## Non-goals
- 不做「设置 › 关于」页的开源许可列表（OFL 的第二项随包义务，留给设置页那一片）。
- 不改字体栈或任何令牌（`tokens.css` 一字不改）。
- 不做 Electron 外壳与安装包。
- 不做字体子集化、重新转换、换版本；不加 `<link rel="preload">`，不用 Font Loading API（`FontFace`）。
- 不碰 T002 留下的非阻塞项。

## Repository facts
- 入口：`desktop/web/src/main.tsx` 挂载 `src/App.tsx`（组件陈列页，根元素带 `tt-app`、`tt-content`、`showcase` 三个类）；主题按钮在页头；`desktop/web/fonts/` 有 5 个文件：`convert.mjs`、`OFL.txt`、`sarasa-mono-sc-regular.woff2`、`sarasa-mono-sc-semibold.woff2`、`SOURCE.md`。
- 调用关系与现有约定：陈列页各节用 `showcase__section` / `showcase__h2` / `showcase__row` / `showcase__label`；`src/styles/` 现有 `tokens.css` 与 `base.css`，还没有 `fonts.css`；`public/licenses/` 现有 `lucide-1.59.0-LICENSE.txt`，还没有 `OFL.txt`；`tests/` 现有 `status-tag.test.tsx` 与 `token-contract.test.ts`。
- 关键事实：`tokens.css` 的 `--tt-font-sans` 首项是 `"TT Sarasa Mono SC"`，`--tt-font-mono: var(--tt-font-sans)`；`--tt-text-md` 是 `400 14px/22px`，`--tt-text-md-medium` 是 `500 14px/22px`，`--tt-title-sm` 是 `600 14px/22px`；`vite.config.ts` 的 `base` 为 `'./'`，Vitest 用 jsdom，`test.include` 含 `src`、`tests`、`gate-probe` 三处。两个 woff2 的 sha256 与字节数、`OFL.txt` 的内容以 `desktop/web/fonts/SOURCE.md` 为准（woff2：8,625,628 / 8,787,944 字节；`OFL.txt` 行尾归一为 LF 后 4,708 字节，前 4 行是版权声明）。
- 工具链与锁文件：Node 24.19.0；npm 11.x，registry `https://registry.npmjs.org/`；React 18 + TypeScript strict + Vite 5.4.11 + Vitest 2.1.8；锁文件 `desktop/web/package-lock.json`（`lockfileVersion` 为 3），`npm ci` 可复现。
- 基线检查：base HEAD `75b95821f29a48959dc39878af7d4dc1641d3f86`，`git status` 干净。T002 门禁 `tests/test_gate_t002_baseline.py` 在基线上应 71 passed（提交 `a0eafa9` 的记录）；T003 门禁 `tests/test_gate_t003_baseline.py` 由门禁端稍后写好、内核做成基线提交，在基线上应失败。

## Scope
- allowed_modified_files:
  - desktop/web/src/main.tsx
  - desktop/web/src/App.tsx
  - desktop/web/src/App.css
  - desktop/web/THIRD_PARTY_NOTICES.md
  - desktop/web/README.md
- allowed_new_files:
  - desktop/web/src/styles/fonts.css
  - desktop/web/public/licenses/OFL.txt
  - desktop/web/tests/font-*.test.ts
  - desktop/web/tests/font-*.test.tsx
- allowed_deleted_files: 无
- forbidden_paths:
  - desktop/web/fonts/**
  - desktop/web/src/styles/tokens.css
  - desktop/web/src/styles/base.css
  - desktop/web/package.json
  - desktop/web/package-lock.json
  - desktop/web/index.html
  - desktop/web/vite.config.ts
  - desktop/web/tsconfig.json
  - desktop/web/scripts/**
  - desktop/web/src/components/**
  - desktop/web/src/domain/**
  - desktop/web/src/icons/**
  - desktop/web/public/licenses/lucide-1.59.0-LICENSE.txt
  - desktop/web/tests/status-tag.test.tsx
  - desktop/web/tests/token-contract.test.ts
  - .gitignore
  - .gitattributes
  - tests/conftest.py
  - tests/test_gate_*.py
  - tests/test_gate_t003_*.py
  - docs/**
  - scripts/**
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

### 正常输入与输出

改动都在 `desktop/web/` 内，按下列各条实现。

**1. `src/styles/fonts.css`（新增，建议全文）：**

```css
/* 随包字体：等距更纱黑体 SC 0.36.0（Sarasa Mono SC，SIL OFL 1.1），来源与哈希见 desktop/web/fonts/SOURCE.md。
   族名与令牌 --tt-font-sans、--tt-font-mono 的首项一致。更纱没有 Medium：300–500 用 Regular，600–800 用 SemiBold。 */
@font-face {
  font-family: "TT Sarasa Mono SC";
  src: url("../../fonts/sarasa-mono-sc-regular.woff2") format("woff2");
  font-weight: 300 500;
  font-style: normal;
  font-display: swap;
}

@font-face {
  font-family: "TT Sarasa Mono SC";
  src: url("../../fonts/sarasa-mono-sc-semibold.woff2") format("woff2");
  font-weight: 600 800;
  font-style: normal;
  font-display: swap;
}
```

- 文件里只有这两条规则（另有注释）；不写 `local()`，不写 `unicode-range`；`font-style: normal` 只把缺省值写明，不改行为；注释里可以提令牌名（契约检查先剥块注释）。

**2. `src/main.tsx`：** 在 `import './styles/tokens.css';` 之前加一行 `import './styles/fonts.css';`，别的不动（T002 的 G1 只查 `createRoot` 与 `./App`）。

**3. 许可副本 `public/licenses/OFL.txt`（新增）：** 用文件复制把 `desktop/web/fonts/OFL.txt` 复制成 `desktop/web/public/licenses/OFL.txt`（不手抄，也不从 `git show` 重定向生成）。内容是 `fonts/OFL.txt` 的逐字副本，含 4 行版权声明；Vite 把 `public/` 原样复制到 `dist/`，产物里是 `dist/licenses/OFL.txt`。

**4. `THIRD_PARTY_NOTICES.md`：** 开头一句总述，然后「Lucide」「Sarasa Gothic（等距更纱黑体 SC）」两节，各一张表。
- Lucide 一节照抄现有内容，只改一处：许可原文的链接目标改为 `public/licenses/lucide-1.59.0-LICENSE.txt`（相对本文件 `desktop/web/` 可解析）。
- Sarasa Gothic 一节的字段（只写 `SOURCE.md` 与 `OFL.txt` 里有的内容）：
  - 名称：Sarasa Gothic（更纱黑体）；用到的字体：等距更纱黑体 SC（Sarasa Mono SC）的 Regular 与 SemiBold；
  - 版本：0.36.0；
  - 许可：SIL Open Font License 1.1；
  - 版权：照抄 `fonts/OFL.txt` 的前 4 行；
  - 来源：<https://github.com/be5invis/Sarasa-Gothic>，v0.36.0 发布的 `sarasa-gothic-ttf-0.36.0.7z`；
  - 随包文件与改动：`fonts/sarasa-mono-sc-regular.woff2`、`fonts/sarasa-mono-sc-semibold.woff2`，由上游 TTF 转成 woff2（wawoff2 2.0.1，默认参数），转换与核对见 `fonts/SOURCE.md`；
  - 许可原文：`public/licenses/OFL.txt`（产物里是 `licenses/OFL.txt`）；
  - 一句说明：「设置 › 关于」的许可列表由设置页那一片加上。

**5. 陈列页样张（`src/App.tsx` + `src/App.css`）：**
- 位置：陈列页页头之后、Button 一节之前，加一节；标题「字体 · 等距更纱黑体 SC」（`showcase__h2`）。
- DOM 约定：节根带 `data-font-specimen` 属性；每种字重一组，组元素带 `data-font-weight`，取值 `400`、`500`、`600`（三组都要有；500 展示“500 按 Regular 显示”）；组内每行一个元素，带 `data-specimen-row` 属性；组旁用 `showcase__label` 写「Regular 400」「500 按 Regular」「SemiBold 600」。
- 字重取令牌：400 用 `--tt-text-md`，500 用 `--tt-text-md-medium`，600 用 `--tt-title-sm`；写在 `App.css` 里按 `[data-font-weight="…"]` 选中的规则中，用 `font: var(…)`。
- 行样式：`white-space: pre`；`font-variant-ligatures: none`（`font` 简写会把它重置为 normal）；不设 `letter-spacing`。
- 对齐标记：每行首尾各加一个 `|`，右端的 `|` 应落在同一条竖线上；外框 `border: 1px solid var(--tt-border)`，底色 `var(--tt-surface-1)`，只用令牌。
- 样张文字（建议），每行 26 列（不算两端 `|`）：
  1. `一个汉字正好两个英文字符宽`（13 个汉字）
  2. `ABCDEFGHIJKLMNOPQRSTUVWXYZ`
  3. `12345678901234567890123456`
  4. `日志 attempt-001 已通过 OK`（4 + 1 + 11 + 1 + 6 + 1 + 2）
- 三组用同样的四行。
- 字符限制：只用 CJK 统一表意文字（U+4E00–U+9FFF）与可打印 ASCII（U+0020–U+007E）；不用全角标点与弯引号；避开 `#`，以及 `->`、`=>` 这类可能连字的写法。
- 不加按钮或别的可交互元素。

**6. `README.md`（只改文档）：**
- 目录约定加两行：`fonts/`（随包字体，只读，来源与哈希见 `fonts/SOURCE.md`）与 `src/styles/fonts.css`。
- `main.tsx` 一行改成“引入 fonts.css / tokens.css / base.css”。
- `public/licenses/` 一行改成“Lucide ISC 与 Sarasa Gothic OFL 许可原文”。
- 命令一节不动（T002 的 G1 查 `npm ci`、`npm run build`、`npm test`、`check:contract` 与 `--tt-`）。

### 边界与错误
- 契约检查（`check:contract`）扫描 TSX 全文（只剥块注释）：样张文字里不能有 `#` 加 3/4/6/8 位十六进制字符，也不能有 `rgb(`、`lab(`、`color(` 这类“函数名 + 括号”；样张只用汉字与 ASCII，避开这些写法。
- 样张不加按钮，避免 T002 的探针按文字找“暗/亮/系统”按钮时误判；主题按钮仍在页头。
- 构建产物：`dist/assets/` 下恰两个 `*.woff2`，与 `fonts/` 逐字节相同；没有别的字体文件；`dist/licenses/OFL.txt` 与副本逐字节相同；dist CSS 的 `@font-face` 用 `./` 开头的相对地址；不内联成 `data:`，不用外部地址。
- 若字体也放进了 `public/`，dist 会有四个 woff2——禁止。

### 禁止的做法
- 把字体复制进 `public/`；
- 在 TS/TSX 里引用字体文件（`?url` 导入等）或用 `FontFace` API；
- 在 `index.html` 加 `<link rel="preload">`；
- 改 Vite 的资源选项（`assetsInlineLimit`、`assetFileNames`、`base` 等）；
- `npm install` 或升级依赖。

### 过渡断言（门禁端，S8、P8）
- 只在陈列页存在于根路由这一片成立的断言按 `test_transitional_` 命名：S8（`App.css` 字重令牌）与 P8（探针渲染陈列页样张）。
- 它们的 docstring 第一行写：「应用框架那一片（T002 规划里的第 3 片"应用框架与夹具数据层"）把陈列页移出根路由时推翻」。
- 门禁断言的具体细节（S1–S8、P1–P8 的编号与实现）由门禁端定稿；本片只需证明 DoD 与检查命令。

### 人工验收项（H1–H6，不由门禁或执行端代做）
- H1 对齐：在浏览器里打开陈列页，看样张各行右端的 `|` 是否在同一条竖线上；Regular、SemiBold 各看一组，暗色、亮色各看一次。开发用 `npm run dev`；看产物用 `npm run build` 后 `npx vite preview`，都用 `npm ci` 装好的 vite，不新增依赖。
- H2 字重与字体来源：SemiBold 组明显比 Regular 粗；500 组与 400 组一样，不是假粗体；DevTools 的 Elements › Computed › Rendered Fonts 里，汉字与英文都是 `TT Sarasa Mono SC`（Network resource）；本机装了更纱时，字体栈的后备项同样对齐。
- H3 网络：Network 面板里两个 woff2 从同源相对地址（`assets/…-<哈希>.woff2`）加载，没有外部请求。
- H4 许可记录：notices 的版本、许可、来源、版权与 `SOURCE.md`、`OFL.txt` 一致（审核端读）。
- H5 OFL 的第二项随包义务：「设置 › 关于」列出 Sarasa Gothic（本片不做，记为设置页那一片的待办）。
- H6 体验：首屏 `swap` 换字体时的闪动是否可以接受；产物多约 17 MB（站主已接受）。

### 并发、取消
不适用：本片是纯静态只读前端，没有异步业务状态。

### 兼容性
- 只改上述允许的文件；`fonts/`、`tokens.css`、`base.css`、`package.json`、锁文件、`index.html`、`vite.config.ts`、`tsconfig.json`、`scripts/**`、既有组件与 domain 与 icons、既有测试都不动。
- 不新增依赖（`dependency_changes: forbidden`）。
- 运行时不从网络加载字体；CSP 是 `font-src 'self'`，字体只从应用包同源加载。
- T002 门禁的其余断言是回归测试，不能变红。

## Steps
1. 预检（只读）：确认两个 woff2 的 sha256 与字节数、`OFL.txt` 行尾归一后 4,708 字节都与 `SOURCE.md` 一致；`tokens.css` 的 `--tt-font-sans` 首项是 `"TT Sarasa Mono SC"`；`fonts.css` 与 `public/licenses/OFL.txt` 都还不存在。不符就停止并报告。
2. 写 `src/styles/fonts.css`：见 Behavior contract 第 1 条（建议全文）。
3. `src/main.tsx`：在 `import './styles/tokens.css';` 之前加 `import './styles/fonts.css';`。
4. 许可副本：用文件复制把 `fonts/OFL.txt` 复制成 `public/licenses/OFL.txt`（不手抄，也不从 `git show` 重定向生成）。
5. `THIRD_PARTY_NOTICES.md`：改成 Lucide 与 Sarasa Gothic 两节，字段见 Behavior contract 第 4 条。
6. 陈列页样张：`App.tsx` 加一节、`App.css` 加样式，见 Behavior contract 第 5 条。
7. 执行端 Vitest 测试：建议一份 `desktop/web/tests/font-specimen.test.tsx`，守住样张列数与字重分组；不用 skip/only/todo。
8. `README.md`：只改文档，见 Behavior contract 第 6 条。
9. 构建核对：先在 `desktop/web` 下按锁文件 `npm ci`（要网络，见授权），再 `npm run build`；核对 `dist/assets/` 下恰两个 `*.woff2`、sha256 与 `fonts/` 相同、`dist/licenses/OFL.txt` 存在、dist CSS 的 `@font-face` 用 `./` 相对地址。
10. 自检（先 npm，门禁放最后）：跑 `npm test`、`npm run check:contract`；再点名运行 `python -m pytest tests/test_gate_t003_baseline.py -q` 与 `python -m pytest tests/test_gate_t002_baseline.py -q`；`git status` 没有新的未忽略文件。

## Setup
无。本合同的 prepare setup 为空；`npm ci` 只在门禁 pytest 与第 9 步自检里跑（与 T002 相同）。

## Validation commands
- V01（必要，基线应失败）：`python -m pytest tests/test_gate_t003_baseline.py -q` · cwd：仓库根 · 超时：2400s · 期望退出码：0 · 输出须匹配：`\d+ passed`
- V02（必要，回归，基线应通过）：`python -m pytest tests/test_gate_t002_baseline.py -q` · cwd：仓库根 · 超时：2400s · 期望退出码：0 · 输出须匹配：`\d+ passed`

说明：V01 的 `tests/test_gate_t003_baseline.py` 由门禁端稍后写好、内核做成基线提交；V02 是 T002 门禁回归，点名运行以让前端流水线不被 conftest 跳过，基线上应 71 passed。两份门禁各跑一遍 `npm ci` 与构建，合计约 20–30 分钟。

## Definition of done
- D01：`fonts.css` 恰有两条 `@font-face`，族名、字重区间、`font-display`、`src` 照 Behavior contract 第 1 条；`main.tsx` 引入它；字体只经 `fonts.css` 引用；证据：V01；目的：令牌首项真有对应的随包字体，字重按设计映射。
- D02：`dist` 恰有两个 woff2，与 `fonts/` 逐字节相同；没有别的字体文件；dist CSS 的 `@font-face` 用相对地址指向这两个文件；不内联成 `data:`，不用外部地址；证据：V01；目的：D14 与 CSP 的 `font-src 'self'`，字体只从应用包同源加载。
- D03：许可副本与 `fonts/OFL.txt` 内容相同（行尾归一），并随产物进入 `dist/licenses/`；notices 记了 Sarasa Gothic 的名称、版本、许可、来源与许可原文路径，Lucide 条目仍在；证据：V01、review；目的：履行 OFL 的随包义务。
- D04：陈列页有样张：400、500、600 三组，各有纯汉字行与纯 ASCII 行；按“汉字 2 列、ASCII 1 列”，每组各行列数相同；行首尾有对齐标记；字重取令牌；证据：V01、review；目的：人能直接看出中英文对齐与两种字重。
- D05：T002 门禁基准全部通过；证据：V02；目的：不破坏第 1 片（令牌、契约检查、组件、无字体包）。
- D06：只改允许的文件；`fonts/`、`tokens.css`、`package.json` 与锁文件不变；不新增依赖；证据：scope；目的：字体只读、令牌不变、依赖不变。
- D07：不删除、跳过或弱化任何测试；新增测试不用 skip/only/todo；证据：review；目的：机械部分由 V02 里 T002 的 `test_d03_new_tests_not_skipped` 查，保证测试不被削弱。

## Stop conditions
- 基线、接口或必要文件与 Repository facts 不符。
- 必须修改允许范围之外的文件才能继续（尤其 `fonts/`、`tokens.css`、`package.json`、锁文件、`vite.config.ts`、门禁测试 `tests/test_gate_t003_*.py`）。
- 需要新增或升级依赖、写 `.npmrc`、装全局包、远程写入、访问凭据或提升权限。
- 验收要求互相冲突，或出现合同没有定义的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 3
- max_wall_seconds_per_attempt: 3600
- max_wall_seconds_total: 10800
- cost_budget: tracking-only
- 时间分配：调查约 6 分钟、实现与补测约 12 分钟、必要检查约 18 分钟、最终报告约 4 分钟。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01 到 D07，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试来获得通过。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务、不读取或输出凭据。
