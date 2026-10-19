# 第三方许可与致谢

本项目的图标取自 **Lucide**，桌面端界面随包字体为 **Sarasa Gothic（等距更纱黑体 SC）**；二者的许可与版权如下。

## Lucide

本目录与 `src/icons/` 中的图标取自 **Lucide**。

| 项目     | 内容                                                           |
| -------- | -------------------------------------------------------------- |
| 名称     | Lucide                                                         |
| 版本     | 1.59.0                                                         |
| 许可     | ISC（其中派生自 Feather 的图标另附 MIT，见许可原文）            |
| 来源     | <https://lucide.dev> · <https://github.com/lucide-icons/lucide> · npm 包 `lucide` |
| 许可原文 | [`public/licenses/lucide-1.59.0-LICENSE.txt`](public/licenses/lucide-1.59.0-LICENSE.txt) |

图标路径按 Lucide 手工转写为 React 组件（`src/icons/index.tsx`），24×24 viewBox、`stroke` 用 `currentColor`、`aria-hidden` 为 `true`；24×24 与描边粗细由 `.tt-i`（`src/styles/base.css`）统一控制。

## Sarasa Gothic（等距更纱黑体 SC）

| 项目             | 内容                                                                                                                                                                                                 |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 名称             | Sarasa Gothic（更纱黑体）；用到的字体：等距更纱黑体 SC（Sarasa Mono SC）的 Regular 与 SemiBold                                                                                                         |
| 版本             | 0.36.0                                                                                                                                                                                               |
| 许可             | SIL Open Font License 1.1                                                                                                                                                                            |
| 版权             | Copyright (c) 2015-2022, Renzhi Li (aka. Belleve Invis, belleve@typeof.net).<br>Portions Copyright (c) 2016-2020 The Inter Project Authors.<br>Portions Copyright (c) 2014, 2015 Adobe Systems Incorporated (http://www.adobe.com/), with Reserved Font Name 'Source'.<br>Portions Copyright (c) 2012 Google Inc.（照抄 `fonts/OFL.txt` 前 4 行） |
| 来源             | <https://github.com/be5invis/Sarasa-Gothic>，v0.36.0 发布的 `sarasa-gothic-ttf-0.36.0.7z`                                                                                                             |
| 随包文件与改动   | `fonts/sarasa-mono-sc-regular.woff2`、`fonts/sarasa-mono-sc-semibold.woff2`，由上游 TTF 转成 woff2（wawoff2 2.0.1，默认参数），转换与核对见 `fonts/SOURCE.md`                                          |
| 许可原文         | `public/licenses/OFL.txt`（产物里是 `licenses/OFL.txt`）                                                                                                                                              |

「设置 › 关于」的许可列表由设置页那一片加上。
