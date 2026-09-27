# 01 基准与公共协议：分阶段实施与验收入口

依据：[01 设计文档](../01-baseline-and-protocols-审阅增强版.md)，修订 `review-expanded-2026-09-25`。开始于 2026-09-25，续接验证于 2026-09-26。

**当前结论、复跑结果及限制统一见 [completion-review.md](completion-review.md)。** 原始实现为 `182ef16`；后续保护配置、文件名与 Windows 测试修复为 `802fa42`，文档记录为 `e18bc1c`、`cd56775`。本轮在此基础上补齐遗漏并进行独立复审，十组最终验证与独立复审已完成，结果和限定范围见当前验收记录。

## 五个阶段与子任务

| 阶段 | 子任务 | 状态与产物 |
|---|---|---|
| P0 准备与边界 | 0.1 规则与设计交叉检查；0.2 离线边界核实；0.3 工具链；0.4 决策；0.5 证据目录与排除规则 | 完成。`decisions.md`；历史“实施前读取总设计”没有记录，保持 NOT_RUN，不倒填证据 |
| P1 基线取证 | 1.1 Git、输入清单与监督取证工具；1.2 旧自测；1.3 旧行为清单；1.4 回归映射；1.5 读取失败与采集标识回归 | 完成，最终复跑通过。修复元数据读取失败/类型变化误报完整、capture-id 尾换行；工具测试增加至 45 项 |
| P2 公共协议 | 2.1 JSON/错误/快照；2.2 路径与资源引用；2.3 事件；2.4 用量观测；2.5 Schema；2.6 测试与导入约束 | 实现完成。公共协议和 Schema 字节未在本轮改动；独立环境 jsonschema 4.26.0 元校验及五样例通过；协议全组 342 项中 338 通过、4 跳过，零失败 |
| P3 兼容 fixtures | 3.1 原字节选样；3.2 合成与黄金向量；3.3 单故障负例；3.4 锁定旧判断；3.5 来源 manifest；3.6 差分；3.7 兼容矩阵 | 已补齐缺字段两类样本，登记 190 项（目录 191 文件）。局部测试 77 项通过，旧判断 40 项零差异、stub 重生成 10 项零差异；最终取证通过 |
| P4 验收与交接 | 4.1 十组最终复跑；4.2 A01–A16 映射；4.3 平台矩阵；4.4 核心保护与索引；4.5 独立复审返工；4.6 交接与提交核对 | 4.1–4.6 在约定范围内完成，十组取证已归档。只在 Windows 实测，A15 不记 PASS |

## 已落实的决定

- 直接实施并用独立子代理复审；没有派遣 Pi。旧调度器、入口、自测、stub、AGENTS.md、技能源及副本保持原字节。
- `.agent/dispatch.config.json` 的 10 条 `extra_protected_paths` 保护核心、Schema、fixtures、harness、回归测试及阶段文档。用户“按推荐处理”覆盖本次配置修改和本地提交。
- 可选验证依赖安装在被忽略的独立 venv；[固定版本](verification-requirements.txt) 不成为产品运行时依赖。
- 顶层 01 设计文件名与 01/02/03/12 索引链接已修复，增加本实施入口。其他模块仍未实施。
- 历史 EV-C01–EV-C10 取证原样保留；本轮使用独立 capture-id 和归档目录，不覆盖历史证据。
- [closure-rulings.md](closure-rulings.md) 已裁定 R-01、G5 与内联 fixture 引用方式。输入闭包仍为 partial，路径审核仍受 R-P9 限制。

## 当前材料与历史材料

- [completion-review.md](completion-review.md)：当前权威验收、重跑结果与平台限制；[independent-review.md](independent-review.md) 保存独立终审结论。
- [fixture-completion.md](fixture-completion.md)：两类新增样本、具体旧判断、扫描断言与红绿验证。
- [acceptance.md](acceptance.md)：A01–A16 原验收映射、历史平台矩阵、交接项与决策；第 0–6 节保留 EV-C 的历史时点，当前结果见 completion-review。
- [baseline-report.json](baseline-report.json) / [baseline-report.md](baseline-report.md)：修订 7 的历史取证报告，含当前验收指针。13 项非权威照录已明确标历史，A01/A07/A16 历史判定未改。
- [decisions.md](decisions.md)、[closure-rulings.md](closure-rulings.md)：范围与口径裁决。
- [legacy-inventory.md](legacy-inventory.md)：旧行为与特征化映射；内联引用须连同对应取证输入清单中的 harness 摘要一起使用。
- [compatibility-matrix.md](compatibility-matrix.md)、[protocols-api.md](protocols-api.md)：历史兼容矩阵与公共接口。样本数量和本轮关闭项以 fixture-completion / completion-review 为准。
- [evidence/closure/INDEX.md](evidence/closure/INDEX.md)：原十组收尾取证，保留原始摘要与结论；本轮证据在 `evidence/followup/`。

用户已明确将 Linux/macOS 实测移交后续插件，本轮不再推进，Linux/macOS 保持 NOT_RUN，A15 仍不记 PASS。第一阶段的分阶段实施和当前 Windows 范围验收已完成。真实 Pi 流、事件事务化、生产级路径访问、崩溃持久性和后续新旧兼容路径仍按模块归属移交；责任与未来复跑前提见当前验收报告。
