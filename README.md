

![content](Logo/content.png)

# **Themis Tally | 参验**

"循名参验"——《韩非子·奸劫弑臣》云：“循名实而定是非，因参验而审言辞。”又《显学》曰：“无参验而必之者，愚也。”古之良制，主上立规划于庙堂，百工效劳力于坊肆，中设司契之官隔绝内外，绝不轻信工匠自矜之虚辞，唯凭实测之符契与案验定其功过。“参验”即隔离规划与执行，废止模型自述，唯以客观证据为凭。

> Themis, high judge who frames the sov'reign plan; And Tally, rod where silent proofs are carv'd. Conjoin'd as one, doth Themis Tally bar Vain boasting tongues, and weigh the deed alone.
>
> 忒弥法神，乃运筹立宪之主； 符契之筹，录铁证无欺之章。 二者合一，是为忒弥参验， 屏绝虚辞，唯核于实测之堂。

**专业的零信任 AI 编码协作与取证调度框架 — 从顶层架构规划到客观证据链验收的全链路解决方案。**

[可配置执行、跨平台、插件与规划委派设计（含分阶段改造清单）](docs/themis-tally-v2-design.md)

[13 份实施子文档与依赖索引](docs/themis-tally-v2/README.md)

每轮提速与执行器纪律（2.10.0）：`integrate` 在当前末端相对候选只多了规划文件时，沿用最近一次干净的 `check --fresh`，不再把全量重跑一遍（`--recheck` 强制重跑）；执行说明在每条检查下面给出保留退出码的“自检照抄”写法；执行报告多一个 `interpretations` 列表，`review-draft` 把它和事件流里的解读线索并排列出。设计说明 [docs/themis-tally-2.10-集成沿用与执行器纪律.md](docs/themis-tally-2.10-集成沿用与执行器纪律.md)。

安装与更新（2.9.0）：两种用法。
- **从 kit 目录运行**（KitExperiment 的做法）：在目标仓库根目录执行 `python <kit>/scripts/pi_dispatch.py <命令>`，不用往目标里复制任何东西；目标只需要 `.agent/` 与把 `.agent/runs/` 加进 `.gitignore`。
- **装进目标仓库**：`python <kit>/scripts/kit_install.py check|install|update <目标仓库> [--force]` 把调度器、它加载的模块、决策插件、四个技能（含 Claude Code 副本）与示例按字节复制进去，留安装记录 `.agent/kit-install.json`；之后技能里的 `bash scripts/dispatch-pi.sh …` 直接可用。已有的 AGENTS.md 不动（输出列出要手工合并的章节），本地改过的文件不覆盖（`--force` 先备份），`.gitignore` / `.gitattributes` 只追加缺少的规则。`doctor` 报告布局、缺的文件与安装之后的改动。设计说明 [docs/themis-tally-2.9-安装与更新.md](docs/themis-tally-2.9-安装与更新.md)。

规划端吞吐（2.8.0）：`integrate`（当前末端上验证后落地）、`review-draft`（复审骨架与简报）、多命令变异与预期、metrics 的最终去向与价格估算，设计说明 [docs/themis-tally-2.8-规划端吞吐.md](docs/themis-tally-2.8-规划端吞吐.md)。

配置管理器（2.7.0）：`bash scripts/dispatch-pi.sh config show|validate|set|unset|init|decisions|secret`，设计说明 [docs/themis-tally-2.7-配置管理器.md](docs/themis-tally-2.7-配置管理器.md)；决策插件（2.6.0）见 [docs/themis-tally-2.6-决策插件.md](docs/themis-tally-2.6-决策插件.md)。
