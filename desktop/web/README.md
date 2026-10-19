# Themis Tally · desktop/web

桌面端 Web 渲染层（React 18 + TypeScript strict + Vite + Vitest）。本片（T002 第 1 片）交付工程骨架、设计令牌、W4 契约检查与 5 个原子组件，以及一个组件陈列页。

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
    main.tsx            # 挂载 App，引入 tokens.css / base.css
    App.tsx / App.css   # 组件陈列页
    styles/
      tokens.css        # 只有 --tt-* 自定义属性与 color-scheme（画布逐项相等）
      base.css          # 基础样式，只用令牌与允许的全局值
    components/         # Button / Tag / StatusTag / Card / Banner，各带一份 CSS
    domain/
      attemptStates.ts  # 17 个已知状态 + 未知兜底
    icons/              # Lucide 图标（React 组件）
  scripts/
    token-contract.mjs  # W4 契约检查（Node，零依赖）
  tests/                # Vitest 测试
  public/
    licenses/           # Lucide ISC 许可原文
  THIRD_PARTY_NOTICES.md
```

## 令牌规则

- 所有颜色、字体、圆角、时长一律取 `--tt-*` 令牌，不写死十六进制、颜色函数或命名颜色。
- 主题缺省为**暗色**；亮色 `data-theme="light"`，跟随系统 `data-theme="system"`（由 App 切到 `<html>`）。
- `npm run check:contract` 扫描 `src/**/*.{css,ts,tsx}`（排除 `tokens.css` 与 `*.test.*`）：
  - 规则 1（未定义变量）：出现的每个 `--tt-…` 都必须在 `tokens.css` 定义。
  - 规则 2（写死颜色）：十六进制、颜色函数、作为颜色属性取值的命名颜色一律判违规。
  - 有违规退出 1，无违规退出 0；`--src`/`--tokens` 路径不存在以非 0 退出并给出可读错误。

## 门禁探针目录（Q4）

`gate-probe/`（被根 `.gitignore` 忽略）用于门禁端投放临时探针：文件名 `probe-<唯一标识>.test.tsx`，`vite.config.ts` 的 `test.include` 已覆盖 `gate-probe/**/*.test.{ts,tsx}`；运行 `npm test -- gate-probe/<文件名>`。
