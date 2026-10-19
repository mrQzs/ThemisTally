# Themis Tally 桌面端 · 设计稿（可读版）

Claude Design 导出的 13 个 HTML（`docs/Themis Tally UI设计/`，约 30 MB，未入库）是自解包的打包文件，模型读不了。
这里是从中解出来的设计源码，供七端流水线（T002 起）与人工实现时阅读。2026-10-19 由 `extract.py` 生成：
`python docs/ui-design/extract.py "docs/Themis Tally UI设计" docs/ui-design`（再复制交接文档为 `handoff.md`）。

## 怎么读

- **`handoff.md`**：开发交接，设计决策汇总（窗口与布局、Token 补充、字体与品牌、原型与文档的差异、交互与工程细则）。先读它。
- **`screens/*.dc.html`**：11 个画面的组件源码（总览 Main、attempt 详情 Attempt、角色与模型 Roles、日志与用量 Logs、CLI 运行时 Runtimes、历史与审计 History、任务 Tasks、插件 Plugins、设置 Settings、凭据 Secrets、首次启动 Welcome）。
- **`pages/NN-标题.html`**：每个画面变体的页面。主画面（标题带“Themis Tally”）是完整内容；浅色、窄窗口、空、出错、抽屉等变体只写用哪个组件、什么状态。设计系统各板（设计令牌、基础组件、七端组件、领域组件、品牌标识、写操作流程、断线与重连、长作业原型）也在这里。
- **`assets/Logo.png`**：Logo 原图（矢量版的描摹说明见 `handoff.md` 的“Logo”与 `pages/01-品牌标识-Themis-Tally.html`）。
- **`assets/support.js`**：设计画布的运行时（dc-runtime，生成文件），只供理解 `*.dc.html` 的写法，不进应用。
- **`index.json`**：页面清单（来自哪个导出、用到哪些组件）。

## 没有拷进来的

- **字体**：画布里的两个 woff2 是只含本稿用字的子集。应用按 `handoff.md` 的“字体”一节，用 npm 包 `@fontpkg/sarasa-mono-sc` 的完整 Regular 与 SemiBold。
- **React 18.3.1 / ReactDOM**：画布从 CDN 加载。应用的技术栈以桌面端设计文档 D9 为准，不从 CDN 加载任何东西（D4、交接 0.2）。

## 页面

| 导出 | 页面 | 用到 |
|---|---|---|
| 1.html | `pages/01-品牌标识-Themis-Tally.html` | `assets/Logo.png` |
| 1.html | `pages/01-设计令牌-Themis-Tally.html` | — |
| 2.html | `pages/02-基础组件-Themis-Tally.html` | — |
| 2.html | `pages/02-领域组件-Themis-Tally.html` | — |
| 2.html | `pages/02-七端组件-Themis-Tally.html` | — |
| 3.html | `pages/03-首次启动-Themis-Tally.html` | — |
| 3.html | `pages/03-首次启动-仓库未接入.html` | `screens/Welcome.dc.html` |
| 3.html | `pages/03-首次启动-浅色.html` | `screens/Welcome.dc.html` |
| 4.html | `pages/04-总览-Themis-Tally.html` | — |
| 4.html | `pages/04-总览-浅色.html` | `screens/Main.dc.html` |
| 4.html | `pages/04-总览-1024-窄窗口.html` | `screens/Main.dc.html` |
| 4.html | `pages/04-总览-首次加载.html` | `screens/Main.dc.html` |
| 4.html | `pages/04-总览-空.html` | `screens/Main.dc.html` |
| 4.html | `pages/04-总览-出错.html` | `screens/Main.dc.html` |
| 5.html | `pages/05-任务-Themis-Tally.html` | — |
| 5.html | `pages/05-attempt-详情-Themis-Tally.html` | — |
| 5.html | `pages/05-attempt-详情-1024-门禁报告.html` | `screens/Attempt.dc.html` |
| 5.html | `pages/05-attempt-详情-信件.html` | `screens/Attempt.dc.html` |
| 5.html | `pages/05-任务-浅色.html` | `screens/Tasks.dc.html` |
| 5.html | `pages/05-attempt-详情-浅色-合同.html` | `screens/Attempt.dc.html` |
| 5.html | `pages/05-attempt-详情-审核记录.html` | `screens/Attempt.dc.html` |
| 6.html | `pages/06-角色与模型-Themis-Tally.html` | — |
| 6.html | `pages/06-更改角色绑定-Themis-Tally.html` | — |
| 6.html | `pages/06-配置决策端-Themis-Tally.html` | — |
| 6.html | `pages/06-新建-profile-Themis-Tally.html` | — |
| 6.html | `pages/06-角色与模型-浅色.html` | `screens/Roles.dc.html` |
| 7.html | `pages/07-CLI-运行时-Themis-Tally.html` | — |
| 7.html | `pages/07-手动登记-runtime-Themis-Tally.html` | — |
| 7.html | `pages/07-CLI-运行时-浅色.html` | `screens/Runtimes.dc.html` |
| 8.html | `pages/08-凭据-Themis-Tally.html` | — |
| 8.html | `pages/08-凭据-浅色.html` | `screens/Secrets.dc.html` |
| 9.html | `pages/09-日志与用量-Themis-Tally.html` | — |
| 9.html | `pages/09-日志与用量-用量.html` | `screens/Logs.dc.html` |
| 9.html | `pages/09-日志与用量-浅色.html` | `screens/Logs.dc.html` |
| 10.html | `pages/10-插件-Themis-Tally.html` | — |
| 10.html | `pages/10-插件-详情抽屉.html` | `screens/Plugins.dc.html` |
| 10.html | `pages/10-插件-浅色.html` | `screens/Plugins.dc.html` |
| 11.html | `pages/11-历史与审计-Themis-Tally.html` | — |
| 11.html | `pages/11-历史与审计-差异抽屉.html` | `screens/History.dc.html` |
| 11.html | `pages/11-历史与审计-浅色.html` | `screens/History.dc.html` |
| 12.html | `pages/12-设置-Themis-Tally.html` | — |
| 12.html | `pages/12-设置-浅色.html` | `screens/Settings.dc.html` |
| 13.html | `pages/13-写操作流程-Themis-Tally.html` | — |
| 13.html | `pages/13-长作业原型-就绪检查.html` | `screens/Runtimes.dc.html` |
| 13.html | `pages/13-断线与重连-Themis-Tally.html` | — |

## 来源校验（sha256）

| 文件 | sha256 |
|---|---|
| `1.html` | `7606e90c7b0833ce31a6cb50ded51af8ff887639aecc8751b8289ca2a92ed74b` |
| `2.html` | `59743c5b723135c61cc57d7608f097376de00f3eabc37c9898732890cd034b24` |
| `3.html` | `9f91ec892705c69d49bc76cbde2eb381b3ebf3de14767e4b28b5d1f9e128c7a2` |
| `4.html` | `ec2b8b03536a39c553417be2b5ab175b0313113537146f65ea9ac21c3c192231` |
| `5.html` | `dae5768eff3ec9bc4dd286e00b8d286251eefab6ead6c87b0a99ac10909f1726` |
| `6.html` | `eb4d8a5ef5ceab7046674780b7ddd05b76c1104cee0d182cd16d8a411b567946` |
| `7.html` | `2613f4dd8a466ad3af33e0f1a3baaeb389562edc92dc64001b0e5baf9eb65274` |
| `8.html` | `073e0c00a8308aff61b9c0deb3a1295af03342daa0b5928c2fe5908b3f7b3aef` |
| `9.html` | `d70949d9b3c1d574b8ee0e02c9ce60e807de46c62c57520114a811859e8d5001` |
| `10.html` | `7b2692c485cb7e2d0ae29d28543ada1f47a476a4f05f0f099d77b792ec093d2c` |
| `11.html` | `f117e054f3d89eb448dafa9211d18978a32124d9e1ac823fdb157d3dbd5858f8` |
| `12.html` | `5b3e4a2474a07a934171964f83c0d827d9c287656273bd058e94aa8b653ec297` |
| `13.html` | `8b914b5aeb8aa1a6bbb1ced9c20ceab9e64d9aa099860755d22bd8e218584a6b` |
| `Themis Tally · 开发交接：设计决策汇总.md` | `f43efd56210d4b494f7135cdc1a39b0d491f93ff54b50538b9f3ad975efab684` |
