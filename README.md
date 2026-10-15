# Code-Kit

[可配置执行、跨平台、插件与规划委派设计（含分阶段改造清单）](docs/code-kit-v2-design.md)

[13 份实施子文档与依赖索引](docs/code-kit-v2/README.md)

安装与更新（2.9.0）：两种用法。
- **从 kit 目录运行**（KitExperiment 的做法）：在目标仓库根目录执行 `python <kit>/scripts/pi_dispatch.py <命令>`，不用往目标里复制任何东西；目标只需要 `.agent/` 与把 `.agent/runs/` 加进 `.gitignore`。
- **装进目标仓库**：`python <kit>/scripts/kit_install.py check|install|update <目标仓库> [--force]` 把调度器、它加载的模块、决策插件、四个技能（含 Claude Code 副本）与示例按字节复制进去，留安装记录 `.agent/kit-install.json`；之后技能里的 `bash scripts/dispatch-pi.sh …` 直接可用。已有的 AGENTS.md 不动（输出列出要手工合并的章节），本地改过的文件不覆盖（`--force` 先备份），`.gitignore` / `.gitattributes` 只追加缺少的规则。`doctor` 报告布局、缺的文件与安装之后的改动。设计说明 [docs/code-kit-2.9-安装与更新.md](docs/code-kit-2.9-安装与更新.md)。

规划端吞吐（2.8.0）：`integrate`（当前末端上验证后落地）、`review-draft`（复审骨架与简报）、多命令变异与预期、metrics 的最终去向与价格估算，设计说明 [docs/code-kit-2.8-规划端吞吐.md](docs/code-kit-2.8-规划端吞吐.md)。

配置管理器（2.7.0）：`bash scripts/dispatch-pi.sh config show|validate|set|unset|init|decisions|secret`，设计说明 [docs/code-kit-2.7-配置管理器.md](docs/code-kit-2.7-配置管理器.md)；决策插件（2.6.0）见 [docs/code-kit-2.6-决策插件.md](docs/code-kit-2.6-决策插件.md)。
