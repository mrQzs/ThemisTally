# 随包字体：等距更纱黑体 SC（Sarasa Mono SC）0.36.0

桌面端界面中英文统一用这一款字体（`docs/ui-design/handoff.md`「字体与品牌」）：
- Regular 管字重 300–500，SemiBold 管 600–800；
- 由字体片接进 `src/styles/fonts.css`。

用户 2026-10-19 拍板：
- 字体从上游官方发布取；
- 一次性转成 woff2 提交进仓库；
- 接受安装包多约 17 MB。

## 来源

- **上游官方发布**：be5invis/Sarasa-Gothic v0.36.0（2022-02-27）。
  - 压缩包：<https://github.com/be5invis/Sarasa-Gothic/releases/download/v0.36.0/sarasa-gothic-ttf-0.36.0.7z>
  - 大小 244,971,846 字节，sha256 `a8366b532ebac177af0cb93950727caa7cb9fffe9577392677e94a86cef5543c`。
  - 这一版的发布没有附 SHA-256 文件，哈希是站主 2026-10-19 下载时算的。
- **从压缩包取出的两个 TTF**：

  | 文件 | 字节 | sha256 |
  |---|---|---|
  | `sarasa-mono-sc-regular.ttf` | 25,897,640 | `00c49d6963436952332c69fee313495851f3579f2346769b049947220dba36d7` |
  | `sarasa-mono-sc-semibold.ttf` | 25,829,836 | `942c94b35a1a34ef42808dd70550ac5c58a55bc2c341ff1c66bd170dd47cb383` |

- **关于 npm 包 `@fontpkg/sarasa-mono-sc@0.36.0`**：
  - 交接文档原本指定它，包里的同名 TTF 与上面逐字节相同；
  - 但它只有 TTF、没有 woff2，README 自称“非字体下载页”，repository 是占位地址，所以不用它。

## 转换

- **工具**：`convert.mjs`，用 wawoff2@2.0.1（Google woff2 的 wasm 版），默认参数。
- **可复现**：同一个 TTF 转两次，哈希相同。

| 文件 | 字节 | sha256 |
|---|---|---|
| `sarasa-mono-sc-regular.woff2` | 8,625,628 | `4a5192c1a5f24a06e5f17d7d1551bdb9e5b7ea5a5b4226e0fd2286fa29e3a010` |
| `sarasa-mono-sc-semibold.woff2` | 8,787,944 | `b18e1bc7f4b60ce2f9dbf07d7b0056df4205b5dc6ac5b1de587e3927453bf3fb` |

**核对**：woff2 解回 TTF，与原 TTF 比较：
- 字形数 52,473 相同；
- 字符映射相同（48,604 个码位）；
- 「中」宽 1000、「A」宽 500，一个汉字正好两个英文字符宽；
- 只少了 DSIG 签名表：woff2 编码器按规范丢弃它，原签名对改了封装的字体不再有效。

## 许可

- **许可证**：SIL Open Font License 1.1。
- **原文**：`OFL.txt`，取自上游仓库 v0.36.0 标签下的 `LICENSE`（4,708 字节），内含版权声明。
- **保留字体名**：只有 Adobe 的 “Source”，转成 woff2 后沿用 Sarasa 的名字不受限。
- **随包义务**：OFL 要求随字体附上版权声明与许可原文。字体片要做到两点：
  - 把 `OFL.txt` 放进产物；
  - 在「设置 › 关于」的开源许可列表里列出 Sarasa Gothic。

## 复现

1. 下载上面的压缩包，核对 sha256。
2. 用 7-Zip 取出两个 TTF：
   ```
   7za e <压缩包> sarasa-mono-sc-regular.ttf sarasa-mono-sc-semibold.ttf
   ```
3. 在仓库之外建一个临时目录，执行 `npm install wawoff2@2.0.1`。
4. 把 `convert.mjs` 复制进去（ESM 的 import 不认 `NODE_PATH`），运行：
   ```
   node convert.mjs <TTF 目录> <输出目录>
   ```
5. 把输出的 sha256 与上表核对。
