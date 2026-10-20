# Themis Tally · desktop/web

桌面端 Web 渲染层（React 18 + TypeScript strict + Vite + Vitest）。先后交付四片：工程骨架、设计令牌、W4 契约检查与原子组件；浮层与焦点；表单与数据原子。外加一个组件陈列页。

## 命令

| 命令                      | 作用                                                      |
| ------------------------- | --------------------------------------------------------- |
| `npm ci`                  | 按锁文件可复现安装依赖                                    |
| `npm run dev`             | 本地开发服务器（Vite）                                    |
| `npm run build`           | 先 `tsc --noEmit` 再 `vite build`，产物在 `dist/`         |
| `npm test`                | `vitest run`，跑 `src`、`tests`、`gate-probe` 三处测试    |
| `npm run typecheck`       | 只跑 `tsc --noEmit`                                      |
| `npm run check:contract`  | W4 契约检查：`node scripts/token-contract.mjs`            |

## 目录约定

```
desktop/web/
  index.html            # 只一个外部 module script，无内联脚本/样式，不写 data-theme
  src/
    main.tsx            # 挂载 App，引入 fonts.css / tokens.css / base.css
    App.tsx / App.css   # 应用框架：标题栏 + 内容区（按路由重挂载）+ 底部 Tab 栏；组件陈列页移到 #/showcase
    styles/
      tokens.css        # 只有 --tt-* 自定义属性与 color-scheme（画布逐项相等）
      base.css          # 基础样式，只用令牌与允许的全局值
      fonts.css         # 随包字体的两条 @font-face（等距更纱黑体 SC）
    components/         # 四片组件，各带一份 CSS：
                        #   第 1 片 Button / Tag / StatusTag / Card / Banner；
                        #   第 3 片 IconButton / Tooltip / Menu / Dialog / Drawer / Toast；
                        #   第 4 片 SegmentedControl / Switch / Checkbox / Tabs / TextField / Select / Table /
                        #            KeyValueList / EmptyState / Skeleton / ConnectionPill / Breadcrumb
      field/             # 输入框 / 下拉 / 开关 / 复选框共用的接线工具（useFieldA11y、useToggle），不从 index 导出
      overlay/           # 浮层共用的内部模块（挂载层、可聚焦查询、焦点管理），不从 index 导出
    showcase/           # 组件陈列页：ShowcasePage.tsx 用 import.meta.glob 急切收集同目录的 *Showcase.tsx，
                        #   按文件名 ASCII 编码顺序排序（JS 默认 sort，大写在前），每节包 div[data-showcase=文件名去掉 .tsx]；
                        #   加一节演示就新增一个 *Showcase.tsx（BaseShowcase 基础组件、FormsShowcase 表单与数据原子、
                        #   ShellShowcase 应用框架；EvidenceShowcase 留给后续片）
    shell/              # 应用框架：router/routes/shortcuts/theme、TitleBar/Logo/ShellMenu/TabBar/PageFrame/DisabledAction 等，各带 CSS
    pages/              # 9 个页面占位（*Page.tsx），各用 PageFrame
    mock/               # 夹具数据层：14 份 *.json（UI 文档第 9 节逐值相等）+ scenario.ts（?mock= 开关）/ empty.ts / shell.ts
    api.ts              # 只读数据层：13 个读函数，返回 Promise<信封>，数据来自 mock/，运行时不发网络请求
    domain/
      attemptStates.ts  # 17 个已知状态 + 未知兜底
    icons/              # Lucide 图标（React 组件）：index.tsx 状态图标，icons/frame.tsx 框架图标（标题栏 / Tab 栏 / 刷新）
  scripts/
    token-contract.mjs  # W4 契约检查（Node，零依赖）
  tests/                # Vitest 测试
  public/
    licenses/           # Lucide ISC 与 Sarasa Gothic OFL 许可原文
  fonts/                # 随包字体，只读，来源与哈希见 fonts/SOURCE.md
  THIRD_PARTY_NOTICES.md
```

## 令牌规则

- 所有颜色、字体、圆角、时长一律取 `--tt-*` 令牌，不写死十六进制、颜色函数或命名颜色。
- 基础重置（`base.css` 里的元素重置）一律包进 `:where()`，特异性降到 0，避免盖过组件的单类规则；`tests/base-reset.test.ts` 与门禁都会核查这条约定。
- 主题缺省为**暗色**；亮色 `data-theme="light"`，跟随系统 `data-theme="system"`；由标题栏的主题菜单切换（`src/shell/theme.ts` 的 `applyTheme` 是唯一写 `data-theme` 的地方，偏好只存内存）。
- `npm run check:contract` 扫描 `src/**/*.{css,ts,tsx}`（排除 `tokens.css` 与 `*.test.*`）：
  - 规则 1（未定义变量）：出现的每个 `--tt-…` 都必须在 `tokens.css` 定义。
  - 规则 2（写死颜色）：十六进制、颜色函数、作为颜色属性取值的命名颜色一律判违规。
  - 有违规退出 1，无违规退出 0；`--src`/`--tokens` 路径不存在以非 0 退出并给出可读错误。

## 应用框架、路由与数据层

- 自写 hash 路由（不装 react-router，G2 也禁止它）：`#/overview` 总览、`#/tasks` 任务、`#/roles` 角色与模型、`#/runtimes` CLI 运行时、`#/secrets` 凭据、`#/logs` 日志与用量、`#/plugins` 插件、`#/history` 历史与审计、`#/settings` 设置；`#/showcase` 组件陈列（不是 Tab，没有当前项）。空、`#`、`#/` 与未知路径都显示总览，不改写地址。快捷键 Ctrl+1…8 依次切前 8 个 Tab，Ctrl+, 切设置；Tab 链接与快捷键导航都保留当前 `?mock=`。
- `?mock=` 夹具开关（`src/mock/scenario.ts`，每次调用时读地址）五个取值：`data`（缺省）、`loading`、`empty`、`error`、`offline`，用来演示页面框架的五态与断线；`empty` 只对 status / runtimes / secrets / plugins / history 五个列表资源生效，`getMeta` 不受影响。接本机服务那一片会把它换成真实请求。
- 数据层 `src/api.ts` 的 13 个读函数返回 `Promise<信封>`，数据取自 `src/mock/*.json`；运行时不发任何网络请求。`tests/shell-no-network.test.ts` 递归扫 `src` 全部文件，按整词查 fetch / XMLHttpRequest / EventSource / WebSocket，即不连服务的静态检查。

## 门禁探针目录（Q4）

`gate-probe/`（被根 `.gitignore` 忽略）用于门禁端投放临时探针：文件名 `probe-<唯一标识>.test.tsx`，`vite.config.ts` 的 `test.include` 已覆盖 `gate-probe/**/*.test.{ts,tsx}`；运行 `npm test -- gate-probe/<文件名>`。

## 桌面端状态表与调度器一致（W5）

仓库根的 `tests/test_desktop_attempt_states.py` 守住桌面端 `src/domain/attemptStates.ts` 的 `ATTEMPT_STATES` 与调度器 `scripts/pi_dispatch.py` 的 `ATTEMPT_STATES` 逐项相同（同样的状态、同样的顺序）。改了 `attemptStates.ts` 或 PD 的 `ATTEMPT_STATES` 之后，在仓库根跑：

```
python -m pytest tests/test_desktop_attempt_states.py -q
```
