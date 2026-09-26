# 01 验收映射（01-A01–A16）、平台矩阵与交接检查

- **依据**：`docs/code-kit-v2/01-baseline-and-protocols-审阅增强版.md`（仓库中文件名因编码显示为 `01-baseline-and-protocols-╔≤╘─╘÷╟┐░µ.md`，修订 `review-expanded-2026-09-25`，128737 字节，sha256 `c5fca7b163d6e8d42f0c79dc0b5d6755c508ec832e8a87f514a294c8a300f42d`）第 1.1、2.3、2.4、6.4、7、9.2 节与附录 C.3、C.5、D.3；决策见 [decisions.md](decisions.md)。
- **编写**：规划端子代理（P4 4.2、4.3、4.6），2026-09-26。本文是 README 列出的 P4 产物，**待独立复审**（P4 4.5）。
- **修订**：2026-09-26 完整性审查返工（规划端子代理）。处理审查提出的 14 个问题，逐条结果见第 12 节；没有改变任何一项验收的判定，只补登记录、更正事实错误并增加未完成项。
- **修订（第二次）**：2026-09-26 对抗性核验返工（规划端子代理）。处理核验确认的 7 个 minor 问题，逐条结果见第 13 节；没有改变任何一项验收的判定。
- **修订（第三次，收尾轮验收收尾）**：2026-09-26（规划端子代理）。依据 decisions.md 末尾的“收尾轮裁决”（R-01、R-02、R-P3 勘误、R-P10–R-P12 与 R-P11 补充）、收尾轮的代码改动，以及规划端在受控环境中按 R-01 严格 pyc 口径做的 10 次收尾取证（`bl-01closure-*-20260926`，归档在 `evidence/closure/`）。逐条处理见第 14 节：
  - 全文的运行证据切换到收尾取证（第 2.3 节新编号 EV-C01–EV-C10）；最终取证 `bl-01final-*`（EV-01–EV-08）与实施前基线（EV-00）保留为历史引用；
  - **改判**：01-A01 按 R-01 重判，01-A07 按 R-02 重判（两项采用基线报告修订 6 的判定，本文核对了其依据的归档事实）；01-A02 有了方法级证据与 `codekit01_legacy.py` 两条核对命令的归档，由“整项不记 PASS”改为“01 范围内 PASS”；
  - A03、A04、A09–A13 按收尾轮新增或改动的测试更新方法清单与计数；第 4 节按当前测试文件与归档输出重新核对；
  - 第 7 节未完成项逐项标注“已关闭：<依据>”或如实保留，新增第 20–25 项；第 10 节 minor 与剩余风险同步；
  - 没有运行任何被测命令，没有调用模型，没有联网；没有修改代码、测试、fixture、Schema、受保护文件、`.agent/baseline/` 原件与已有归档目录。
- **修订（第四次，对抗性核验第二轮）**：2026-09-26（规划端子代理）。处理核验确认的 8 个 minor 问题，逐条结果见第 15 节；**没有改变任何一项验收的判定**，只更正依据的写法与证据等级（宁可降级）：3.2 中 A02 方法归属的依据分两种写；3.12 与兼容矩阵中“没有白名单放行”改记为静态核对；2.2 不再说操作者记录与 capture.json“逐字段一致”；M-07、第 7 节第 9、19 项与基线报告统一关闭状态的用词；3.13 更正 `SEALING_LIMITATIONS` 的条号。基线报告（修订 7）、兼容矩阵（修订 12）与 `evidence/closure/INDEX.md` 在同一轮更正，本文引用的摘要随之更新（第 1、15 节）。新增第 10 节 M-16。
- **本文怎么得出结论**：只读取归档证据与工作区，**没有重跑任何被测命令**，没有调用模型，没有联网。
  - PASS 只来自 10 次收尾取证的归档输出（measured）。实施前基线与 8 次最终取证只作历史对照，不作为本修订任何 PASS 的依据。
  - “某个测试方法属于哪一项验收”由测试方法名与 docstring 静态对应（source_inspected）；方法与收尾轮裁决的对应同样只是静态对应（`evidence/closure/INDEX.md` 4.3 节）。个别方法的名称与 docstring 都没有标注验收项，是规划端按内容归入的推断，在引用处逐项注明（例如 3.2 的 6 个方法，第四次修订补记）。
  - 核对方法见第 11 节（本修订为第 11 条）。
- **01-A01、01-A07、01-A16** 采用 [baseline-report.md](baseline-report.md) 修订 6 第 8 节的判定（待独立复审）；本文核对了该判定所依据的归档事实（第 11 节第 11 条），并把判定成立的前提写入第 3.1、3.7 节与第 7 节第 20–22 项。其余 13 项由本文判定。基线报告“JSON 与 MD 分歧时以 JSON 为准”只适用于报告自己的两份文件，不适用于本文判定的 13 项；报告 JSON 中照录的 13 项文字取自本文修订前的字节（138322 字节，`f01f659c…`），与本修订不一致之处以本文为准（第 7 节第 25 项）。

**判定规则**（文档 2.4、6.4、7.4、C.5）：

- PASS 必须同时能追到：取证 ID、归档文件路径与 sha256、测试方法名（旧自测为 check 名，核对命令为逐行输出）、基线一致（`baseline_consistent=true`）。缺任何一项都不记 PASS。
- 跳过的方法记 NOT_RUN（缺 jsonschema 的一项记 BLOCKED，01-L07），不计通过。
- `tests/test_codekit01_fixtures.py`：最终取证（EV-03，历史）的输出只有 36 个“.”，只有命令级结论；收尾取证以 `-v` 运行（EV-C08），75 个方法都有方法名。方法级结论只来自 EV-C08。
- 方法名与验收项、与裁决的对应是静态对应（source_inspected），不配运行型 PASS；PASS 只针对该方法实际运行的断言。
- 平台分开记：只有 Windows 实测；Linux、macOS 一律 NOT_RUN，不从 Windows 推导（01-D10、7.5）。
- 范围受限的项写成“01 范围内 PASS + 范围外 NOT_RUN / 移交模块”，**不把整项写成 PASS**。
- 判定依赖尚待规划端确认的前提时，写明前提与不成立时的结论（3.1、3.7）。
- 本文不写笼统的“全部通过”。
- “不适用”用 `applicability` 与理由表达（01-L09，文档 2.4）：取 not_applicable 时必须写理由；它只表示检查对该平台或范围没有意义，不能代替必需能力的判定，必需的安全能力不能标不适用来绕过，对应能力仍按 NOT_RUN 等状态记录。

**目录**：0 结论摘要 · 1 交付物总览 · 2 共同依据（实现版本、基线、证据编号）· 3 A01–A16 逐项 · 4 F001–F050 · 5 平台矩阵（7.5）· 6 G0–G6 最终表（7.3）· 7 交接检查（D.3）与未完成项 · 8 给 02/03/04 合同的绑定清单（9.2）· 9 待用户决定的事项 · 10 minor 与剩余风险 · 11 本文的核对方法 · 12 完整性审查的逐条处理（历史）· 13 对抗性核验的逐条处理（历史）· 14 收尾轮验收收尾的逐条处理

第 12、13 节是此前两轮返工的处理记录，原文保留不改；其中的证据编号（EV-01–EV-08）、计数与摘要都是当时的值，指最终取证。

## 0. 结论摘要（分范围）

| 验收 | Windows（实测） | Linux | macOS | 范围外 / 移交 / 待确认 | 判定来源 |
|---|---|---|---|---|---|
| 01-A01 基准报告 | PASS（R-01 严格 pyc 口径；范围：10 次收尾取证；pyc 受控禁用只有操作者记录，取证工具没有测量；输入闭包 partial） | NOT_RUN | NOT_RUN | 两个前提待规划端确认（3.1；第 7 节第 20、21 项）：不接受操作者记录作为受控禁用的依据时为**不满足**；R-01 若覆盖仓库外输入则为 **FAIL** | baseline-report 修订 6（本文核对依据） |
| 01-A02 v1 合同与历史证据兼容 | 01 范围内 PASS（方法级：EV-C08 中 19 个方法 ok，其中 6 个与 A02 的对应是规划端推断，见 3.2；EV-C03 38 行 SAME；EV-C10 10 行 SAME） | NOT_RUN | NOT_RUN | 文档 6.6 七类的新旧差分：NOT_RUN（新路径不存在，归 07、10）；缺字段类两种样本：NOT_COVERED（第 7 节第 24 项）；真实历史派遣证据：仓库中没有，NOT_RUN；合同 v1 字段语义新校验：09 | 本文（改判：最终取证时方法级 NOT_RUN、整项不记 PASS） |
| 01-A03 快照字节与哈希 | 01 范围内 PASS | NOT_RUN | NOT_RUN | F017“机器路径进入环境锁”：NOT_RUN，归 02（01-D05） | 本文 |
| 01-A04 单一原因拒绝 | PASS | NOT_RUN | NOT_RUN | — | 本文 |
| 01-A05 wait/退出/审核/verdict/集成分维 | PASS | NOT_RUN | NOT_RUN | — | 本文 |
| 01-A06 用量未知与币种 | 01 范围内 PASS（观测视图，不记账） | NOT_RUN | NOT_RUN | 唯一记账：07（01-D08） | 本文 |
| 01-A07 G0–G6 等回归映射 | PASS（R-02，Windows，范围限定，带 unmet_within_scope） | NOT_RUN | NOT_RUN | 3.7 所列子分支、POSIX 与备注层缺口（迁移比较记 NOT_COVERED）；G5 的读法待规划端确认（第 7 节第 22 项），若要求 G5 有可触发的失败断言则为 **FAIL** | baseline-report 修订 6（本文核对依据） |
| 01-A08 标识归属与恢复 | 01 范围内 PASS | NOT_RUN | NOT_RUN | 标识的持久唯一性与分配、request 预算根：07 | 本文 |
| 01-A09 Schema 家族与降级防护 | PASS；Schema 元校验 BLOCKED | NOT_RUN | NOT_RUN | — | 本文 |
| 01-A10 路径与实际消费一致 | 01 范围内 PASS（词法 + 静态审阅） | NOT_RUN | NOT_RUN | F029、F030 与生产级安全访问：NOT_RUN，归后续访问实现模块（01-D06，模块未指定）；授权层（保护路径判断）：未实现，归 03 | 本文 |
| 01-A11 事件幂等与完整性 | 01 范围内 PASS（协议函数层；日志内部 run/request/role 绑定一致） | NOT_RUN | NOT_RUN | 事务化持久日志、真实崩溃恢复、与受信 RunContext 的一致性：NOT_RUN，归 07、04 | 本文 |
| 01-A12 脱敏证据来源 | 01 范围内 PASS（来源规则、R-P11 条目字段、fixture 凭据形态扫描） | NOT_RUN | NOT_RUN | 真实 captured 样本、脱敏前后偏移映射：04；凭据发现后的处置流程：规划端与用户 | 本文 |
| 01-A13 不可变发布与补偿 | 01 范围内 PASS（发布与索引补偿） | NOT_RUN | NOT_RUN | 崩溃持久性：NOT_RUN，归持久存储的实现模块（未指定，第 7 节第 2 项）；受控清理未引用候选：07、04 | 本文 |
| 01-A14 无副作用导入 | PASS | NOT_RUN | NOT_RUN | — | 本文 |
| 01-A15 平台声明与能力 | Windows 结果已实测并单独记录；整项不记 PASS | NOT_RUN | NOT_RUN | 其他平台：05（三平台运行）与第 9 节 (c) | 本文 |
| 01-A16 参考与项目验证隔离 | PASS | applicability=not_applicable（理由：分栏规则不分平台；不表示有测试在此运行） | applicability=not_applicable（理由同左） | — | baseline-report 修订 6（本文核对依据） |

**一句话**：在 Windows Server 2025 + CPython 3.12.10、HEAD `a4fa199` 加未提交工作区上，10 次收尾取证全部退出 0 且前后一致（R-01 严格 pyc 口径；受控禁用的依据只有操作者记录）。只看 Windows：

- A04、A05、A14、A16：PASS；
- A09：PASS，但 Draft 2020-12 元校验 BLOCKED；
- A01：PASS（R-01 严格口径，范围限定），成立的两个前提待规划端确认：不接受操作者记录作为受控禁用的依据时为不满足；R-01 若覆盖仓库外输入则为 FAIL；
- A07：PASS（R-02，范围限定，带 `unmet_within_scope`），G5 的读法待规划端确认，若要求 G5 有可触发的失败断言则为 FAIL；
- A02、A03、A06、A08、A10–A13：只在 01 范围内 PASS，范围外部分 NOT_RUN，已移交 02、03、04、07、09、10，或归属模块未指定（A10 的生产级安全访问、A13 的崩溃持久性，第 7 节第 2 项）；
- A15：只有 Windows 实测，整项不记 PASS。

Linux、macOS 全部 NOT_RUN。这不是“01 全部通过”。

## 1. 交付物总览（文档 1.1 目标产物 × 2.3 输出物）

状态说明：“已产生”指文件在工作区中存在并已核对字节；第一阶段代码、Schema、fixtures、测试、文档与证据已在提交 `182ef16` 中；本轮新增的保护配置与索引修复随本次收尾提交。字节与 sha256 为本修订编写时测得。

| 产物（1.1 / 2.3） | 1.1 最低可用标准 | 2.3 应含 / 不应含 | 文件路径 | 字节，sha256 | 状态 |
|---|---|---|---|---|---|
| 基线报告 | 精确关联代码版本、实际输入、工具链、命令、退出信息、结果及限制 | 含输入引用、环境摘要、命令结果、旧行为映射、未运行项；不含自身哈希、凭据、猜测性 PASS | [baseline-report.json](baseline-report.json)（以它为准）<br>[baseline-report.md](baseline-report.md) | 467608，`b49b20236c9f806569b9772c785cc6f53a003615754396dfaf4ff55138140d5b`<br>171426，`592013782247ca086e6a0aec98a6a5a235b878b25a0db9e0390e8e1777de8541`<br>（修订 7；修订 6 为 459146 `6449e16b…` 与 163364 `62dd9414…`；修订 5 为 288103 `d1ddf225…` 与 97583 `209f9605…`，更早的见第 12、13、14 节） | 已产生（修订 6：新增第 13 节收尾取证，依据 R-01、R-02 重判 A01、A07、A16，三项仍为 PASS 并写明范围与前提；修订 7：对抗性核验勘误，不改判定，见第 15 节）；报告不内嵌自身摘要，也不内嵌本文的摘要（本文摘要记在 README）；判定待独立复审 |
| 旧行为清单与回归映射（基线报告的 legacy_inventory 分区） | 同上 | 同上 | [legacy-inventory.md](legacy-inventory.md) | 721294，`9fdba24ca5de15b4cb75c206caf1e9633bb6866f0f2a8d12372ded225792adc4`（收尾轮更新后；收尾取证输入清单记录的是更新前的 570632 `a9d3d189…`） | 已产生（收尾轮：9.10.5–9.10.7 按 R-P12 回填 input_fixture_ref 与 comparison_projection_revision，12.10 给出 159 个方法的代码内联引用，第 0.5、12.1 节更正用词（M-08））；待独立复审 |
| 证据目录 | —（2.3） | 含分离的 stdout/stderr、来源元数据、脱敏记录；不含未授权保留的真实密钥 | `evidence/closure/`（10 次收尾取证，各 84 个文件，另有 [INDEX.md](evidence/closure/INDEX.md)；当前依据）<br>`evidence/final/`（8 次最终取证，历史）<br>`evidence/bl-01t1-legacy-20260925/`（实施前基线）<br>`evidence/run-controls/`、`run-controls-final/`、`run-controls-closure/`（操作者记录与受控环境）<br>`evidence/inventory-items/`（旧行为清单的结构化条目）<br>`evidence/reference-appendix-b-windows/`（参考代码验证） | 各 manifest 的摘要见 2.3；`evidence/closure/INDEX.md` 48511，`85ae818f8a5de0b42cf0568b2a5b5205752012e9340519013c12a3706718f0ba`（第四次修订时勘误后的字节；此前为 44858 `a6a84822…`）；`evidence/final/INDEX.md` 25868，`bc04e2c39cbf67301af0b7f387bdcd8c476e51d5d28478eddc67aa74536a496d`（未变） | 已产生；redact-v2 脱敏，`unredacted_files` 均为空；原件在 `.agent/baseline/`（被 Git 忽略，只读）；两份 INDEX.md 是手写索引，不是归档文件 |
| fixture manifest | 来源、脱敏、预期判断、平台适用性、历史能力边界明确 | 含来源类别、源版本、文件哈希、用途、预期结果；不含伪造的厂商输出或不存在的提交 | `tests/fixtures/codekit01/manifest.json`（188 条）及同目录 188 个登记文件 | 408977，`95c58a9b5a68166e104ee8a719385d43a8f346bff96ab96806518d6c94a830e0`（收尾轮按 R-P11 重新生成；最终取证时为 171 条，338969 `50dc2fc3…`） | 已产生；全部为 `synthetic_fixture` 表示（legacy 18、negative 157、synthetic 13），**没有 captured 条目**。R-P11 后条目有 `integrity`、`platform_scope`、`capture`、`redaction.protocol_structure_preserved`、`origin.traceable`（M-03 已关闭），1.1 的“平台适用性”与 6.6 的“完整性”有了字段；但 `platform_scope` 与 `traceable` 是登记者的声明，产品入口不核对追溯链，也不代表已在所列平台运行，`capture` 没有真实样本。6.6 选样：七类按 R-P12 为“旧路径已锁定，差分 NOT_RUN”；缺字段类仍缺两种样本（第 7 节第 24 项） |
| 公共 Schema 与参考实现（公共协议、资源引用） | 字段有类型、作用域、必填规则、校验顺序和稳定错误；内容变更可检出，来源可信度与字节一致性分开判断 | 含数据结构、纯校验逻辑、边界说明；不含调度、执行授权或扣款实现 | `scripts/codekit/protocols.py`、`scripts/codekit/sealing.py`、`scripts/codekit/__init__.py`<br>`schemas/codekit-public-v1.schema.json`<br>接口说明 [protocols-api.md](protocols-api.md) | 见 2.1 表<br>protocols-api.md 301574，`785c75f6c3481065fcf8c7a04ea56018a6d69d0309203cc037e3c1b19b016fa0`（与收尾取证输入清单记录的相同） | 已产生；只依赖标准库（01-L01）；Schema 与附录 E.2 摘要一致；Schema 元校验 BLOCKED；`ResourceKind` 已按 R-P10 增加 schema、允许的载荷表示与语义校验器三项，并新增 `validate_resource_payload`（M-10 已关闭）；事件日志函数按 M-01 核对日志内部的 request/role 绑定 |
| 取证工具（为基线报告服务） | — | — | `scripts/codekit/baseline.py` | 见 2.1 表 | 已产生；40 项自测 PASS（EV-C04）；不记录 `PYTHONPYCACHEPREFIX`（第 7 节第 20 项） |
| 兼容矩阵 | 区分读取、验证、运行、审核、集成能力，未知版本不降级 | 含类型/版本/平台/读取与执行能力；不含不带条件的“全面兼容” | [compatibility-matrix.md](compatibility-matrix.md) | 118604，`07b3aa17a5e8ed1909f83f4cee7a239d3ea9a7875cdc92a62b52b4d0abe2af34`（修订 12；修订 11 为 116258 `f388c96f…`；收尾取证输入清单记录的是修订 10，105770 `6a5defe9…`） | 已产生（修订 9–11：D-20–D-23 落为 fixture、R-P11 字段、凭据扫描、8.4 归属核对、收尾取证引用；修订 12：E19 与 9.1 节“没有白名单放行”改记为静态核对）；自述“不是验收结论”；第 1 节两条 `codekit01_legacy.py` 命令现有归档（EV-C03、EV-C10，M-06 已关闭） |
| 验收映射 | 每个结论可追到输入、命令或断言；未运行不等于通过 | 含旧场景、新断言、责任模块、证据引用；不只凭测试名称认定覆盖 | 本文 `acceptance.md` | 本文不内嵌自身摘要（记在 README） | 已产生（第三次修订；第四次修订为勘误，不改判定，见第 15 节）；待独立复审 |
| 决策记录 | — | — | [decisions.md](decisions.md) | 20186，`8b460b2d57f1e0e8c1ea2cc2da140c66e186f92425a8d8a586a2eb51ececbb61`（与收尾取证输入清单记录的相同） | 已产生；收尾轮追加 R-01、R-02、R-P3 勘误（M-02 已关闭）、R-P10–R-P12 与 R-P11 补充 |
| 保护范围（文档 5.2） | — | — | `.agent/dispatch.config.json` | — | **已落实**：按选项二登记；机械保护覆盖 01 核心代码、Schema、fixtures、legacy harness/tests、三组第一阶段测试与 `docs/code-kit-v2/01-baseline/`（第 9 节 (a)） |

## 2. 共同依据

### 2.1 实现版本（implementation_revision，IR）

- **提交**：HEAD `a4fa199b0e5bdc658215765ee7558b9fe6723940`（sha1 对象格式，对象类型 commit），与文档 2.1 的调查提交相同。
- **工作区**：收尾取证时（提交前）的工作区曾包含第一阶段新增代码、测试、fixture、Schema 与文档；这些内容现已进入提交 `182ef16`，本轮只增加保护配置与索引修复。结论只对下表记录的字节成立。
- 下表的 sha256 由本修订编写时重算，与收尾取证输入清单（`pre/input-manifest.json`，sha256 `3a559ca5cc328a9632831666f5f59137df0484b2fc5f778af351843cdd619982`）记录的值逐一相同。“最终取证时”一列只列收尾轮改动过的文件。

| 文件 | 字节 | sha256 | 取证清单中的来源 | 最终取证时（历史） |
|---|---|---|---|---|
| `scripts/codekit/__init__.py` | 82 | `145ff733182c785d097833d8402adc0ee4487de1998ce917f3b4102be88cb8f9` | untracked | 相同 |
| `scripts/codekit/baseline.py` | 80514 | `dbb08466778db639966336902653525fa26a4f9f9152c5827594ea9313e49ce8` | untracked | 相同 |
| `scripts/codekit/protocols.py` | 215838 | `64d75bb0a5b37a5dd93240eac3f58455538a12e58c91b324a72b3d14708bc42b` | untracked | 188693 `d980e8ca…` |
| `scripts/codekit/sealing.py` | 25001 | `af92c1f97af0d762d59b37c4411c477e39246e8e9fb9d9ccddfd8af42f84f265` | untracked | 相同 |
| `schemas/codekit-public-v1.schema.json` | 13335 | `7895442dc9907b6ab1a0c1dd946a1b0caaf2cdd49caaa1ebabff94fa10cdf291` | untracked | 相同 |
| `tests/test_protocols.py` | 558783 | `b0d354a1d33d7d7e592e9e78f26a0896531f256e4f1eba2a59d98b80b917859b` | untracked | 494529 `5db9c197…` |
| `tests/test_codekit01_fixtures.py` | 214461 | `16b71bca5f0c86378a00b59fcfc6426de4772b79f04cf356ae6ee4525131a57b` | untracked | 133849 `c3c8f1b9…` |
| `tests/test_baseline_tool.py` | 54951 | `1b7842099e434292124e7354ee77117b4bfb98a4847647ecf7b5df5e5386ee8b` | untracked | 相同 |
| `tests/test_legacy_gates.py` | 66481 | `d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | untracked | 相同 |
| `tests/test_legacy_lifecycle.py` | 77345 | `f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | untracked | 相同 |
| `tests/test_legacy_cli.py` | 84800 | `1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | untracked | 相同 |
| `tests/test_legacy_events.py` | 72723 | `f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | untracked | 相同 |
| `tests/legacy_harness.py` | 79723 | `c4e871372a35f35c59a76172ccc366a50316c5af9ad3ec4703d1fb6c27d4b974` | untracked | 65866 `3d133d5f…` |
| `tests/codekit01_legacy.py` | 87792 | `f1d208361aabfff72e98005ed9e5e7003506a72e7bab7b9c7e8ff392962d6e86` | untracked | 72970 `9ce7318b…` |
| `tests/fixtures/codekit01/manifest.json`（另有 188 个登记文件） | 408977 | `95c58a9b5a68166e104ee8a719385d43a8f346bff96ab96806518d6c94a830e0` | untracked | 338969 `50dc2fc3…`（171 条） |
| `tests/fixtures/codekit01/expected/legacy-contracts.json` | 254437 | `5328bb62721095f07ac48350c53aa74e6a0e8dc64440ab15a713c618fc866ed0` | untracked | `71613d00…`（16 个合同用例） |
| `tests/fixtures/codekit01/expected/legacy-events.json` | 107353 | `e889fef038d674d155a8b5cbb1403e07a8a469b36e9b8c8eec0ff44eba34973b` | untracked | 相同 |
| `tests/fixtures/codekit01/expected/legacy-new-strict.json` | 15638 | `e936407998da7042596c68223cbb9fbfb6c94409e258a6ae9888a832be71af82` | untracked | `bf7f8ad4…` |
| `docs/code-kit-v2/01-baseline/protocols-api.md`（测试读取其中的节） | 301574 | `785c75f6c3481065fcf8c7a04ea56018a6d69d0309203cc037e3c1b19b016fa0` | untracked | 242742 `4efea533…` |
| 01 设计文档（审阅增强版，测试按前缀读取） | 128737 | `c5fca7b163d6e8d42f0c79dc0b5d6755c508ec832e8a87f514a294c8a300f42d` | untracked | 相同 |
| `scripts/pi_dispatch.py`（旧调度器，被测对象） | 274717 | `a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4` | tracked，相对 HEAD 无改动 | 相同 |
| `scripts/dispatch-pi.sh` | 1010 | `e2e12058ef5d58b4126527b158bef8dcc04653527f7ce20544c0d7cd77bdb2f4` | tracked，无改动 | 相同 |
| `tests/test_dispatch.py` | 121490 | `c6fed33534b096b764145257ba5c2ce340f50cbaf483b5007097874c3bbd543e` | tracked，无改动 | 相同 |
| `tests/stub_pi.py` | 14376 | `96c0d4a5ba775e9c23ce104176f1e2f0fbe6eb2925eafef5b0c5fd5c248e916a` | tracked，无改动 | 相同 |
| `tests/stub_pi_help.txt` | 10176 | `5668cff3cf34fd6f0dbcb7b0d10667761219ca47879ba09d11c137507245824c` | tracked，无改动 | 相同 |
| `AGENTS.md` | 10932 | `7571e9a9e68046f421909995ab58070f45e5aea2d48176389d8cb2c892245cc2` | tracked，无改动 | 相同 |
| `.gitattributes` | 453 | `06f42b3dbb6186b55a93193124d2167f8879e049eaeeb25685f6420971429e8a` | tracked，有 01 的改动（3 条 `-text` 规则） | 相同 |
| `.gitignore` | 162 | `67fe42da6d0116dbd9145fa3debe288ec15c6bc1e15e48b0aeb92acb56af5021` | tracked，有 01 的改动（`.agent/baseline/`） | 相同 |

- **受保护文件**：本修订编写时，`git diff HEAD --stat` 对 `scripts/pi_dispatch.py`、`scripts/dispatch-pi.sh`、`tests/test_dispatch.py`、`tests/stub_pi.py`、`tests/stub_pi_help.txt`、`AGENTS.md`、`.agents/`、`.claude/` 输出 0 行，`git status --porcelain` 对这些路径为 0 项（measured，不属于取证）。取证时的记录见 2.2。
- **取证之后工作区的变化**（本修订编写时重算，measured）：收尾取证输入清单共 1073 项，其中 1067 项带摘要，6 项是取证时已删除、不带摘要的旧文档（现在仍不存在）。
  - 本修订写入之前，1067 项中有 **4 项**的当前字节与清单不同：`baseline-report.json`、`baseline-report.md`（报告修订 6）、`compatibility-matrix.md`（修订 11）、`legacy-inventory.md`（收尾轮更新），都是取证之后更新的文档。其余 1063 项字节相同，包括 2.1 表中的全部代码、测试、fixture、Schema、`protocols-api.md`、`decisions.md` 与设计文档。
  - 本修订写入之后，本文 `acceptance.md`（清单记录 138322 字节，`f01f659c…`）与 `README.md`（清单记录 12363 字节，`0381b1a4…`）也与清单不同，共 6 项。
  - 清单中没有、取证之后才加入的文件：`evidence/closure/`（841 个）与 `evidence/run-controls-closure/`（2 个）。
  - 测试读取的文档只有设计文档与 `protocols-api.md`（字节未变），另外 `PublicEntryRejectionTests.test_baseline_records_are_internal` 按文件名在 `evidence/` 下递归查找取证记录（source_inspected，`tests/test_codekit01_fixtures.py` 的 `EVIDENCE_DIR.rglob`）。取证时读到 capture.json、input-manifest.json、environment.json、archive-manifest.json 各 9、18、18、9 份，`evidence/closure/` 归档后是 19、38、38、19 份，所以以后再运行时它的输入与取证时不同（第 10 节 R-13）。其余测试不读取上述 6 份文档（source_inspected：`tests/` 与 `scripts/codekit/` 中只在注释与 docstring 里提到这些文件名）。

### 2.2 基线引用（baseline_ref）

| 编号 | 取证 | 基线事实（measured，取自各 `capture.json` 与 `pre/`、`post/` 记录） |
|---|---|---|
| BL-PRE | `bl-01t1-legacy-20260925`（实施前） | HEAD `a4fa199…`；porcelain 37 项；输入清单 92 项，sha256 `6aea1cc0b4db213d765af3514ce771d4199900cf0434eed47e7bbe1768ecffcc`，闭包 `8ca10fb98b8d97213ae4430fdb3e8f444cb7aa0ac12fbdff8a5986513fece0a9`；`execution_status=complete`，`baseline_consistent=true`，drift 为空；取证工具 `baseline.py` `9eb03345…` |
| BL-FINAL（历史） | 8 次最终取证（EV-01–EV-08） | HEAD `a4fa199…`；porcelain 319 项，sha256 `a84e68334b1f94e9c69694118c5994b2847a4bc00038466dbcf43913d3dc6088`；输入清单 373 项，sha256 `1406890ad081c59ff37c1cff6b466847f1a66d0ed8b368300657c0d479a108b2`，闭包 `2d8f2f71d6514b08e1f331009245d97e5f51a50a02f034651f87e17e2fa70b7d`；8 次都 complete、退出 0、`baseline_consistent=true`；取证工具 `dbb08466…`。收尾取证之后是历史证据：按 R-01 原口径保留（`bl-01final-test-dispatch-20260925` 读取了未计摘要的 pyc），不改写，不作为本修订任何 PASS 的依据 |
| BL-CLOSURE | 10 次收尾取证（EV-C01–EV-C10） | HEAD `a4fa199b0e5bdc658215765ee7558b9fe6723940`（sha1，commit）；porcelain 1019 项，sha256 `af6f80a3c5a70cb855d48ef61b2f3529672bced931b0db05c24550f118a00025`；输入清单 1073 项（tracked 63、untracked 1010），sha256 `3a559ca5cc328a9632831666f5f59137df0484b2fc5f778af351843cdd619982`，闭包 `81b4503e291166fd78632aab9163faac2f0e25c92db11c691dfbe753068f52a4`；20 次 pre/post 采样逐项相同，10 次之间工作区不变；10 次都 `execution_status=complete`、退出 0、未超时、未中断、无残留进程、`baseline_consistent=true`、drift 为空；closure_status=partial（被忽略文件不计摘要、子模块不展开、仓库外输入不纳入、gitattributes 效果不评估）；被忽略的名称只有 `scripts/__pycache__/`、`tests/__pycache__/`（R-01 以受控禁用处理，见 3.1）；取证工具 `baseline.py` `dbb08466…`；监督器 `run_supervised`（`pi_dispatch.py` `a00d6934…`，Job Object，时限 3600 s）。取证工具记录的 UTC 时间为 2026-09-26T14:47:10.580687Z 至 15:00:06.978434Z |

**受控环境**（01-L05 与 R-01，收尾取证）：

- **取证工具测得**（measured）：20 次采样中 `which.pi`、`which.claude`、`which.codex` 都是 null；13 个被检查的变量名中只有 `PI_CODING_AGENT_DIR` 存在（只记是否存在；这 13 个名称不含 `PYTHONPYCACHEPREFIX`）；被测进程环境新增 `GCM_INTERACTIVE`、`GIT_TERMINAL_PROMPT`、`PYTHONDONTWRITEBYTECODE`，没有移除的变量；20 份 `environment.json` 字节相同（sha256 `097cb8a45efdd7af3ea98666380a3db5031d74e071bd395163f239fbb4acb43b`），与最终取证、实施前基线的相同（本修订核对了 29 份）。
- **操作者记录**（source_reported，不是取证工具的输出；其中第 5 行的定位结果与第 6、7、18、19 行的计数由操作者脚本在取证前后现场得到，取证工具没有采集）：`evidence/run-controls-closure/closure-captures.txt`（EV-RCC）。第 3 行在 Git Bash 中运行；第 4 行 PATH 去掉两处存放真实 claude、pi、codex 的用户目录，unset `CLAUDE_CODE_MESSAGING_TOKEN`，`PI_CODING_AGENT_DIR` 指向空目录，`PYTHONPYCACHEPREFIX` 指向取证前为空的目录（R-01）；第 5 行受控条件下三者都定位不到；第 6 行前缀目录取证前 0 个条目；第 7、19 行受保护文件 diff 前后 0 行；第 8–17 行逐次记录中，capture-id、argv、executed、returncode、reason、timed_out、duration、baseline_consistent 与汇总行文字与各 `capture.json`、`run/*.bin` 一致（measured；`evidence/closure/INDEX.md` 2.2 节核对其中 7 项，第四次修订补核 executed、reason）；同一行的 `tool_exit=0`、`leaked=[]` 在 `capture.json` 中没有对应字段，无法核对，只有操作者记录（source_reported；第三次修订原写“与各 `capture.json` 逐字段一致”，说过头了，第四次修订更正）；第 18 行空目录取证后 0 个条目；第 20 行参照时刻偏晚，不作证据。
- 网络没有隔离，也没有监测（离线依据是 P0.2 的静态核实，EV-RC）。

**操作者记录的保存**：

- 最终取证的 `final2-captures.txt` 已正式归档到 `evidence/run-controls-final/`（EV-RCF）：1495 字节，sha256 `c362495cc389d37204e1250f8ff613585f5722cb8b0e63c60bcf668b9d11d6dd`，与此前登记的原件摘要相同；复制清单 `manifest.json` 846 字节，`bbd6c3a108257aedf1fbe8c95026f75e61866120b625426016d6d88c8ddd2e8a`。第 7 节第 19 项已关闭。这些条件对最终取证的证据等级仍是 source_reported；“PATH 去掉真实 CLI”“unset 令牌”“受保护文件 diff”对最终取证仍只来自派发说明。
- 收尾取证的记录在取证后即归档（EV-RCC），上述条件都写在同一份记录中；证据等级同样是 source_reported。

### 2.3 证据编号（evidence_refs）

路径都相对 `docs/code-kit-v2/01-baseline/`。`e3b0c442…b855` 是空内容的 sha256。所有摘要由本修订编写时按归档文件重算，与 [evidence/closure/INDEX.md](evidence/closure/INDEX.md) 第 1、3 节和 baseline-report 第 13.2 节一致。

编号说明：

- 收尾取证记为 EV-C01–EV-C10。其中 EV-C02、EV-C04、EV-C08 与兼容矩阵修订 11 第 9 节自用的编号指同一次取证。
- 实施前基线 EV-00 与最终取证 EV-01–EV-08 保留为历史引用（下面第二张表）；第 12、13 节中的 EV 编号都是这些历史编号。
- 上一版把 `evidence/run-controls/` 记作 EV-C，本修订改记 EV-RC，避免与 EV-C01–EV-C10 混淆。

**收尾取证（当前依据）**：

| 编号 | 取证 ID（`evidence/closure/<取证 ID>/`） | 被测命令与栏（01-A16） | 结果原文（文件:行） | 归档文件与 sha256 |
|---|---|---|---|---|
| EV-C01 | `bl-01closure-test-dispatch-20260926` | `python tests/test_dispatch.py`；legacy_project | `256 checks, 0 failed`（run/stdout.bin:282）；退出 0 | archive-manifest.json `fd4a0d3687e615c6ae06d70b79ded6a59924ff829d4a44265a8aeb12c5d7d31d`<br>capture.json `7a3d33148a117766d50fc9ab4e27e8ea3c1b0d41816f2d09594dd799541ca114`<br>run/stdout.bin（13423 B）`f40586e2376e2361bc962878059d732b95c2c8cb0f79d48c3fd069fc37e1080e`（与 EV-00、EV-01 逐字节相同） |
| EV-C02 | `bl-01closure-test-protocols-20260926` | `python tests/test_protocols.py`；project_protocols | `Ran 342 tests in 4.291s`（run/stderr.bin:687）；`OK (skipped=4)`（:689）；退出 0 | archive-manifest.json `d91e78995fbfa90790274f60139ffb52d58fb3b2c50c21cfe8eea6d589e56037`<br>capture.json `9bb0a5d272fad21fb7e565c084f03c86846fafe7cec51e51a2ede8121854aca3`<br>run/stderr.bin（77955 B）`5b81e659c60f296503dd99e836a938fa45134ffe597fb960a204b56ee65354c8` |
| EV-C03 | `bl-01closure-legacy-check-20260926` | `python tests/codekit01_legacy.py --check`；project_protocols（归栏是基线报告的分类，capture.json 没有栏字段） | 第 1–38 行都以 `SAME` 开头；`38 checks, 0 differ`（run/stdout.bin:39）；退出 0 | archive-manifest.json `b74b9513906ee3fb72602db703ebed6a37cebc3cfc843887a9dae0f8bb2619dc`<br>capture.json `35bceb51497f5573e86e6b7426deba71e60d1f8b8a258d27cd9f7537306a8e3c`<br>run/stdout.bin（3712 B）`2a06d6b3069d23cbb24649983cbced3770476d7b5a3fdf16e751dea94580f5d2` |
| EV-C04 | `bl-01closure-test-baseline-tool-20260926` | `python tests/test_baseline_tool.py`；baseline_tool | `Ran 40 tests in 57.652s`（run/stderr.bin:43）；`OK`（:45）；退出 0 | archive-manifest.json `22694ddf02256dabdace3bfe3e85aa039779cb80284d43fbf48b5ede7ccbd9f0`<br>capture.json `de6f1c35b459cec59df593b4b7a9cdc5d27c54a8bd06b4579b5579fc5786214d`<br>run/stderr.bin（5064 B）`024b9d508c236c504ee277b9aa07db14f45ad32235d547c1d161002121f22863` |
| EV-C05 | `bl-01closure-test-legacy-gates-20260926` | `python tests/test_legacy_gates.py`；legacy_characterization | `Ran 24 tests in 128.419s`（run/stderr.bin:52）；`OK`（:54）；退出 0 | archive-manifest.json `6e7a47cc1d8ba259297d9c6a3e30d4226782bb1483730318df685b02598d2f11`<br>capture.json `b8753abda447daa6de981c20eeb76b5f9caeb734bf9b80af859908a4e999983b`<br>run/stderr.bin（6459 B）`97af8357a3730e301a70d6890bfc1d1463186590d25f4db15d7348ea938138f6` |
| EV-C06 | `bl-01closure-test-legacy-lifecycle-20260926` | `python tests/test_legacy_lifecycle.py`；legacy_characterization | `Ran 26 tests in 140.098s`（run/stderr.bin:56）；`OK (skipped=2)`（:58）；退出 0 | archive-manifest.json `8b5d41c20fe4544fef6004862b3394495793bee0998b855951585e9e1b4b43bd`<br>capture.json `04d09d2514448074bf895b3b64e6afb5afb678163b1e9af94af234280ead95bc`<br>run/stderr.bin（7809 B）`e79ad9f8e4e9f8330f7677f2696ae9908dc6604b2735f955c62813924a2aa99f` |
| EV-C07 | `bl-01closure-test-legacy-cli-20260926` | `python tests/test_legacy_cli.py`；legacy_characterization | `Ran 75 tests in 92.991s`（run/stderr.bin:153）；`OK (skipped=1)`（:155）；退出 0 | archive-manifest.json `38734036c2d20153d9cd5f9b91aebc077b05b09920ae347078194bd52256ab5c`<br>capture.json `f1c7eb2453524c6be4383e3490006e3afcbdab26cc2962a95e18592b993f3f7f`<br>run/stderr.bin（19861 B）`26cce1cf6ad440b5f584180592d772bb4e720e2a54f353694f458bef6a16c3ae` |
| EV-C08 | `bl-01closure-test-codekit01-fixtures-v-20260926` | `python tests/test_codekit01_fixtures.py -v`；project_protocols | 75 个方法逐条 `ok`（run/stderr.bin:1–102）；`Ran 75 tests in 11.260s`（:105）；`OK`（:107）；退出 0 | archive-manifest.json `54b9132f3abcfa4cb79d065dec860290f2f3fa71fc8c58ccfb6cbd4c1ea69153`<br>capture.json `e661873ef738d4e19084e3386b6cef15001bf595987dc16b90e89fe620e45db1`<br>run/stderr.bin（13127 B）`95faa68cea9315a4a73cc4bfc4223916e56b8eb1b9e5694fa1415fdf1c8b169a` |
| EV-C09 | `bl-01closure-test-legacy-events-20260926` | `python tests/test_legacy_events.py`；legacy_characterization | `Ran 34 tests in 51.774s`（run/stderr.bin:71）；`OK`（:73）；退出 0 | archive-manifest.json `b341914ffa16dfc2e41a18491e2696a0b4bcadcae8499b15eaf9a638a487d302`<br>capture.json `e1da8d27a1df5e5fd9e48069f8e0d57a78b08a556792f7a64393b30ceb527109`<br>run/stderr.bin（8739 B）`e5cfa16608d66529963a69a7a10236c294873692b3efe19f5773b0c6bbe70166` |
| EV-C10 | `bl-01closure-legacy-check-stub-regen-20260926` | `python tests/codekit01_legacy.py --check-stub-regen`；project_protocols（同 EV-C03） | 第 1–10 行都以 `SAME stub regen` 开头；`10 checks, 0 differ`（run/stdout.bin:11）；退出 0 | archive-manifest.json `c8833dc2557af3eb99990a7fecd3cda742e6a9b7a6cc40410bb03330209f7237`<br>capture.json `d3a50b3545a381ddb5a6f6aa969247eba1b5251569dae106261491d344e2a141`<br>run/stdout.bin（273 B）`9a942083ceece639e010b0771c7c2f0efd68470d40f8cd72766d76d63de1a785` |

- 各归档的 `capture.json` 被 redact-v2 改写了 1 处 `<PYDIR>`，原件摘要见 INDEX.md 第 3 节；`run/*.bin` 的脱敏前后字节相同。
- 10 份 archive-manifest 各列 83 个文件（不含自身），目录各 84 个文件；830 个条目的 `archived_sha256` 与归档文件一致（INDEX.md 1.2 节、baseline-report 13.7 节；本修订只重算了上表 40 个关键文件）。

**其他证据**：

| 编号 | 目录 | 内容 | 摘要 |
|---|---|---|---|
| EV-R | `evidence/reference-appendix-b-windows/` | 附录 B 参考自测；reference_code 栏（与项目验证分开）：21 项，19 ok、1 FAIL（`test_static_resolution`，8.3 短名导致的测试写法问题）、1 skipped；退出 1 | manifest.json `3f4528043e85409494c203560026cbecae8bbeee67cf0e5a3f0c02a1026d9cbc` |
| EV-RC | `evidence/run-controls/` | 实施前基线的受控环境记录与 P0.2 离线边界静态核实（source_reported / source_inspected） | manifest.json `64bbb512be76d00f046414d8b1420977c70ded12eb690fcb702baf496cf9f6cd` |
| EV-RCF | `evidence/run-controls-final/` | 最终取证的操作者记录（历史；source_reported） | final2-captures.txt（1495 B）`c362495cc389d37204e1250f8ff613585f5722cb8b0e63c60bcf668b9d11d6dd`；manifest.json（846 B）`bbd6c3a108257aedf1fbe8c95026f75e61866120b625426016d6d88c8ddd2e8a` |
| EV-RCC | `evidence/run-controls-closure/` | 收尾取证的操作者记录（受控条件、R-01 的前缀目录、逐次汇总；source_reported） | closure-captures.txt（3133 B）`fb00af747f1ff3fd7b20a35d5902c918f7057f58bdfb7e9c660d4db57ccc0e86`；manifest.json（1147 B）`eed5de9213aa7aa88944b983905cd1b725711f2289e05f270558417309f4ac73` |
| EV-INV | `evidence/inventory-items/` | 旧行为清单 6 个区域的结构化条目（legacy-inventory.md 第 3–9 节的来源；条目中的“实测”“探针”是线索，不是运行证据） | manifest.json（1326 B）`cebbd8bfc9861f97ce21f81478b2574aef5fdd6a8acff3df1f5ca70d9ddba8c9`；6 个 `inventory-*.items.json` 的 sha256 与 manifest 一致（本修订核对） |

**历史取证**（不作为本修订任何 PASS 的依据）：

| 编号 | 取证 ID / 目录 | 被测命令 | 结果原文（文件:行） | archive-manifest.json sha256 |
|---|---|---|---|---|
| EV-00 | `bl-01t1-legacy-20260925`（`evidence/bl-01t1-legacy-20260925/`，实施前） | `python tests/test_dispatch.py` | `256 checks, 0 failed`（run/stdout.bin:282），stdout `f40586e2…` | `b46f72a21da6c4b1169c29d6c3a0df3e4c47b4186dedde104473348818e0f521` |
| EV-01 | `bl-01final-test-dispatch-20260925`（`evidence/final/…/`，下同） | `python tests/test_dispatch.py` | `256 checks, 0 failed`（run/stdout.bin:282） | `9b13a01dfd07d654be0b8b2c79c1d3accb4a823bfee6df5afae76a5a886c3ded` |
| EV-02 | `bl-01final-test-protocols-20260925` | `python tests/test_protocols.py` | `Ran 324 tests`（run/stderr.bin:651）；`OK (skipped=4)`（:653） | `3707e1cd88fe05c113eaf3acca35f22190b6f525d508c99d5c2fe782df4c3908` |
| EV-03 | `bl-01final-test-codekit01-fixtures-20260925` | `python tests/test_codekit01_fixtures.py` | 36 个“.”；`Ran 36 tests`（:3）；`OK`（:5）；无方法名 | `6406500f42cae518e8dce7d0616455a8cb4744a2a1af3043146548fab2599222` |
| EV-04 | `bl-01final-test-baseline-tool-20260925` | `python tests/test_baseline_tool.py` | `Ran 40 tests`（:43）；`OK`（:45） | `f9554817796edf2369e86b31c326eb85ae6b2f55cf1be099599ed5e7a50a0ce4` |
| EV-05 | `bl-01final-test-legacy-gates-20260925` | `python tests/test_legacy_gates.py` | `Ran 24 tests`（:52）；`OK`（:54） | `3508c6012489e573c246a141b60293252b9804c1d5b457961eaa16d5712a61e2` |
| EV-06 | `bl-01final-test-legacy-lifecycle-20260925` | `python tests/test_legacy_lifecycle.py` | `Ran 26 tests`（:56）；`OK (skipped=2)`（:58） | `c37c4f4866d8813a0cb0b6ff718c6d396568d1d819b5333ff0811ddbce3d187a` |
| EV-07 | `bl-01final-test-legacy-cli-20260925` | `python tests/test_legacy_cli.py` | `Ran 75 tests`（:153）；`OK (skipped=1)`（:155） | `5794ef531a6df45474f9639945f4260b7069e602f83c26369ec302599805cc59` |
| EV-08 | `bl-01final-test-legacy-events-20260925` | `python tests/test_legacy_events.py` | `Ran 34 tests`（:71）；`OK`（:73） | `4042d5cb7364cb0ed64e21655f5062e3c1124a494da3955b8c8d5d40120f5bba` |

EV-01–EV-08 的 capture.json 与输出文件摘要见 [evidence/final/INDEX.md](evidence/final/INDEX.md) 与 baseline-report 第 12.2 节。

**逐方法计数**（收尾取证；本修订按归档 `run/*.bin` 重算，与当前源码中的测试方法用 AST 逐一对应，集合相同；FAIL 与 ERROR 都是 0）：

| 取证 | 源码测试方法 / 检查项 | ok | skipped | 方法级可追溯 | 与最终取证相比 |
|---|---|---|---|---|---|
| EV-C02 test_protocols | 342 | 338 | 4（F017、F029、F030 NOT_RUN；jsonschema 元校验 BLOCKED） | 是 | 新增 18 个方法（M-01 5 个、R-P11 6 个、R-P10 7 个），没有减少，其余 324 个结果相同 |
| EV-C08 test_codekit01_fixtures `-v` | 75 | 75 | 0 | 是 | 最终取证只有 36 个“.”，不能逐方法比较；新增类见 3.2、3.12、3.13 |
| EV-C04 test_baseline_tool | 40 | 40 | 0 | 是 | 方法集合与结果相同 |
| EV-C05 test_legacy_gates | 24 | 24 | 0 | 是 | 相同 |
| EV-C06 test_legacy_lifecycle | 26 | 24 | 2（POSIX，NOT_RUN） | 是 | 相同 |
| EV-C07 test_legacy_cli | 75 | 74 | 1（POSIX，NOT_RUN） | 是 | 相同 |
| EV-C09 test_legacy_events | 34 | 34 | 0 | 是 | 相同 |
| EV-C01 test_dispatch | 24 个 `test_*` 函数，256 个 check | 256 行 PASS，0 行 FAIL | `test_wrapper_interpreters_and_literal_arguments` 没有 check（NOT_RUN） | check 级 | stdout 逐字节相同 |
| EV-C03 `--check` | 38 项 | 38 行 SAME，0 行 DIFF | — | 项级（每行一个对象） | 最终取证没有这条命令 |
| EV-C10 `--check-stub-regen` | 10 项 | 10 行 SAME | — | 项级 | 最终取证没有这条命令 |

`tests/test_protocols.py` 的 342 个方法：253 个以 `test_Axx_` 命名（`test_A11_F037_append_event_replay_of_older_seq_keeps_state` 计入 A11），89 个以 `test_Fxxx_` 命名，没有其他命名。第 3 节各项的“方法数”按“以该 A 编号命名的方法 + 附录 C.3 中关联该 A 的 F 编号方法”计。

## 3. 01-A01–A16 逐项（附录 C.5 模板）

共同字段（各项不再重复）：

- **implementation_revision**：历史收尾取证绑定 HEAD `a4fa199…` + 未提交工作区；当前第一阶段代码基线为提交 `182ef16`，关键文件字节与收尾取证相同，新增保护配置与索引修复不改变被测实现。
- **baseline_ref**：BL-CLOSURE（2.2）；A01、A07 另以 BL-PRE、BL-FINAL 作历史对照。
- **platform**：windows 为 Windows Server 2025 Standard 10.0.26100（AMD64）、CPython 3.12.10、git 2.55.0.windows.5；linux、macos 一律 NOT_RUN，不从 Windows 推导。
- **reviewer_or_owner**：映射与判定为本文（P4 验收映射子代理，收尾轮修订），A01、A07、A16 的判定为 baseline-report 修订 6 编写者；独立复审待进行（P4 4.5）；范围外部分的归属写在各项中。

### 3.1 01-A01 基准报告关联提交、平台、命令与结果

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A01 |
| platform | windows：PASS（范围限定，前提见 execution_status）；linux：NOT_RUN；macos：NOT_RUN |
| implementation_revision | 共同字段；被测旧源码 `scripts/pi_dispatch.py` `a00d6934…`（= HEAD blob `8e7df57c…`）；取证工具 `baseline.py` `9eb03345…`（BL-PRE）→ `dbb08466…`（BL-FINAL、BL-CLOSURE） |
| baseline_ref | BL-CLOSURE（判定依据）；BL-PRE、BL-FINAL（历史对照） |
| fixture_refs | 无（A01 不依赖 fixture） |
| command_or_assertion | 验收核对（baseline-report 修订 6 第 8、13 节）：报告是否把 10 次收尾取证逐一关联到 40 位 HEAD、对象格式、平台与工具链、argv 与 cwd、真实退出码与监督结果、汇总行（文件与行号）、前后采样与输入清单、归档路径与 sha256；失败、跳过、未运行与 BLOCKED 是否都没有记为通过；按 R-01，被测命令读取的字节是否都在取证时计摘要或受控禁用。<br>支撑测试：`GitOidTests.test_F035_interpret_constructed_output`、`GitOidTests.test_F035_real_git_temp_repository`（EV-C02 stderr 第 145–148 行）；F050 的取证工具方法（第 4 节 F050 行，EV-C04） |
| expected | 7.1：前后采样、输入清单、真实退出信息和日志齐全；漂移或缺输入时不得 PASS |
| actual | 10 次收尾取证都是 `execution_status=complete`、退出 0、未超时、未中断、无残留进程、`spawn_error=null`、`baseline_consistent=true`、drift 为空；20 次采样的工作区状态相同，闭包 `81b4503e…` pre 与 post 相同；汇总行都能按文件与行号找到（2.3）；7 个跳过方法记 NOT_RUN（6）与 BLOCKED（1），旧自测 `test_wrapper_interpreters_and_literal_arguments` 记 NOT_RUN；参考自测 FAIL 保留；Linux、macOS 记 NOT_RUN。<br>**R-01（pyc）**：输入清单 1073 项中 1067 项计了摘要，6 项是已删除的旧文档；不计摘要的只有被忽略的 `scripts/__pycache__/`、`tests/__pycache__/`（measured）。按操作者记录，取证时 `PYTHONPYCACHEPREFIX` 指向取证前为空的目录，使进程内导入不读这两个目录（受控禁用）；被测进程由 `child_env` 补设 `PYTHONDONTWRITEBYTECODE`，不写 pyc（measured）；`tests/test_protocols.py` 以 `-B -I` 启动的子进程不继承该变量，但只导入取证时没有 `__pycache__` 的 `scripts/codekit/`（measured 加 source_inspected，baseline-report 13.5 节）。<br>旁证：三次旧自测（EV-00、EV-01、EV-C01）的 stdout 逐字节相同，其中前两次读取了 pyc、EV-C01 禁用了 pyc；旁证不代替 R-01 的记录。<br>F035 两个方法 ok；F050 相关 9 个方法 ok（EV-C04） |
| execution_status | windows：**PASS**（R-01 严格 pyc 口径；范围：10 次收尾取证、只限 Windows；输入闭包 partial，不宣称输入完整或可严格复现）。<br>判定成立的两个前提**待规划端确认**：<br>① 接受操作者记录（`closure-captures.txt` 第 4、6 行）作为 R-01“受控禁用，并在取证记录中写明”的依据。不接受时，pyc 这一项只是操作者声明，本项为**不满足（不记 PASS）**，需要让取证工具记录该变量（是否设置、取证后前缀目录的条目数）后重新取证（第 7 节第 20 项）。<br>② R-01 只针对 pyc，不覆盖仓库外输入（标准库及其字节码、git 与全局配置、系统工具）。若覆盖，现有取证工具的任何一次取证都不满足，本项为 **FAIL**（第 7 节第 21 项）。<br>linux、macos：NOT_RUN |
| evidence_basis | measured（取证记录与归档输出）；pyc 受控禁用：source_reported（操作者记录；“前缀目录取证前为空”是操作者脚本在取证前统计的计数，取证工具没有测量）；被测进程继承该变量：source_inspected（`run.env_policy` 的文字与测试代码） |
| evidence_refs | EV-C01–EV-C10（2.3）；EV-RCC；[evidence/closure/INDEX.md](evidence/closure/INDEX.md) 第 2、5 节；[baseline-report.md](baseline-report.md) 第 8、13 节（13.5 R-01）；JSON `acceptance[01-A01]` 与 `closure_regression` |
| known_limitations | 历史取证 EV-00、EV-01 读取了未计摘要的 `scripts/__pycache__/pi_dispatch.cpython-312.pyc`，按 R-01 保留原口径、不改写，在严格口径下不满足，不作为本判定的依据。取证工具进程自身没有设 `PYTHONDONTWRITEBYTECODE`，设了前缀后可能把标准库字节码写进前缀目录，供之后的被测进程读取（推断，未测量；属于仓库外输入）。被忽略的两个目录只列名称；子模块、gitattributes 效果不评估；读取与使用之间的竞态没有消除；受控环境的其余条件只有操作者记录；网络未隔离 |
| reviewer_or_owner | 判定：baseline-report 修订 6；两个前提：规划端；独立复审：待进行 |

### 3.2 01-A02 v1 合同与历史证据迁移前后关键判断一致

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A02 |
| platform | windows：01 范围内 PASS（方法级）；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；`tests/test_codekit01_fixtures.py` `16b71bca…`、`tests/codekit01_legacy.py` `f1d20836…`、`tests/legacy_harness.py` `c4e87137…`；旧入口 `scripts/pi_dispatch.py` 未改动（`a00d6934…`） |
| baseline_ref | BL-CLOSURE |
| fixture_refs | `tests/fixtures/codekit01/manifest.json` `95c58a9b…`（188 条）；legacy 18 条（6 个合同：plan-task 技能示例 2 对与合同模板 1 对，a4fa199 原字节；10 条 stub 事件流；2 份旧预期）；从 legacy 派生的单一故障负例 22 个（合同 19，其中收尾轮为 D-20–D-23 新增 6 个；事件 3）；`expected/legacy-contracts.json` `5328bb62721095f07ac48350c53aa74e6a0e8dc64440ab15a713c618fc866ed0`（22 个合同用例）；`expected/legacy-events.json` `e889fef038d674d155a8b5cbb1403e07a8a469b36e9b8c8eec0ff44eba34973b`（13 个用例）；`expected/legacy-new-strict.json` `e936407998da7042596c68223cbb9fbfb6c94409e258a6ae9888a832be71af82`（18 份 JSON、13 条 JSONL）；比较投影 `codekit01-legacy-projection-v1`。<br>文档 6.6 的七类（超时、取消、恢复、候选漂移、候选/补丁判断、门禁结果、旧入口状态解释）按 R-P12 以代码内联 fixture 引用（`inline:<测试文件>::<类>.<方法>@<测试文件 sha256>`，比较投影 `codekit01-characterization-v1`；legacy-inventory.md 9.10.7、12.10，兼容矩阵第 8 节第 9 条）。<br>**仍缺样本**：缺字段类的“JSON 合同缺必填字段”“消息带 usage 但缺 token 字段”（不属于 R-P12 的七类，第 7 节第 24 项） |
| command_or_assertion | **EV-C08**（`python tests/test_codekit01_fixtures.py -v`）中与 A02 对应的 19 个方法（行号为 run/stderr.bin 的起始行–结果行）。对应关系都是静态的（source_inspected），依据分两种：**①** 13 个方法——`DifferentialTests` 7 个、`FileIntegrityTests` 4 个、`LegacySourceTests` 2 个——所在类的 docstring 标注了 01-A02；**②** 其余 6 个方法——`StubTests.test_stub_regeneration_matches_locked_bytes` 与 `CompatMatrixDCaseTests` 5 个——的类 docstring、方法 docstring 与方法源码都没有提到 A02，是规划端按内容归入 A02 的推断：前者核对 stub 事件流重跑与锁定字节相同，后者按兼容矩阵 4.3 节 D-20–D-23 逐项核对旧判断与新严格入口判断的锁定预期（第四次修订更正：此前写“对应关系取自类 docstring”，对这 6 个不成立）：<br>- `DifferentialTests` 7 个（①）：`test_legacy_contract_projection_unchanged`（26）、`test_legacy_event_projection_unchanged`（27）、`test_legacy_expected_headers_match_generator`（28）、`test_legacy_implementation_bytes_are_source_revision`（29）、`test_legacy_negative_derivations_reproducible`（30）、`test_new_strict_verdicts_are_separate_from_legacy_expectations`（31）、`test_new_strict_verdicts_unchanged`（32）；<br>- `FileIntegrityTests` 4 个（①）：`test_directory_has_no_unregistered_or_missing_files`（33）、`test_every_manifest_digest_matches_file_bytes`（34）、`test_git_attributes_disable_line_ending_conversion`（35）、`test_git_clean_filter_keeps_bytes`（36–37）；<br>- `LegacySourceTests` 2 个（①）：`test_generator_sources_at_revision`（64）、`test_legacy_copies_equal_git_show`（65）；<br>- `StubTests.test_stub_regeneration_matches_locked_bytes`（94；②）；<br>- `CompatMatrixDCaseTests` 5 个（D-20–D-23；②）：`test_d20_non_finite_cost_amount`（14）、`test_d21_deep_nesting`（15）、`test_d22_invalid_utf8`（16）、`test_d23_identifier_trailing_newline`（17）、`test_every_d_case_is_a_registered_single_fault_fixture`（18）。<br>**EV-C03**（`python tests/codekit01_legacy.py --check`）：38 行 SAME、0 行 DIFF——6 份 legacy 合同副本与 a4fa199 的 blob 相同、6 份工作区来源文件与该 blob 相同、22 个负例派生可复现（合同 19、事件 3）、三份 expected 由旧实现重算后逐字节相同、manifest 中的 legacy 条目 1 项。<br>**EV-C10**（`--check-stub-regen`）：10 条 stub 流重跑与锁定字节相同。<br>方法级支撑：`ResourceRefTests.test_F033_crlf_changes_hash`（EV-C02 第 299–300 行） |
| expected | 7.1：同一 fixture 摘要、旧结果、兼容结果、锁定比较投影；未取得旧结果不通过；不修改样本换取通过 |
| actual | EV-C08：上列 19 个方法都是 ok，75 个方法中没有 skipped、FAIL、ERROR。取不到 git 或提交 a4fa199 时这些检查默认判失败，只在显式设置 `CODEKIT01_ALLOW_NOT_RUN=1` 时改记 NOT_RUN（跳过）；取证工具不记录这个变量，但 EV-C08 中没有跳过项，所以这些检查在取证中都实际运行了。EV-C03 38/0、EV-C10 10/0。F033 ok。<br>01 没有迁移旧入口：旧入口字节不变，“迁移前后”在 01 中的含义是“按 a4fa199 字节重算的旧判断与锁定预期一致”（EV-C03 中三份 expected 行与 `DifferentialTests`）。新严格入口与旧入口的差异按 01-D09 登记为 D-01–D-23（兼容矩阵第 4 节），**没有宣称一致**：“旧接受、新严格入口拒绝”的是 D-01 与 D-20 的 Infinity 用例；D-23 两边都接受（新严格入口只判断 JSON 层）。<br>仓库中没有真实历史派遣证据（`.agent/runs/` 不存在，`.agent/plans/` 为空） |
| execution_status | windows：**01 范围内 PASS**（v1 合同样本与 stub 事件流在合同投影与事件摘要投影上的旧判断与锁定预期一致；fixture 字节与来源 blob 一致；新严格入口的判断与旧判断分开锁定）；文档 6.6 七类的新旧差分：**NOT_RUN**（新兼容路径不存在，归 07、10；旧路径已由特征化测试锁定，见 3.7）；缺字段类两种样本：NOT_COVERED；真实历史派遣证据的迁移比较：**NOT_RUN**（无此类输入）；linux、macos：NOT_RUN |
| evidence_basis | measured（EV-C08 方法级，EV-C03、EV-C10 项级）；方法与 A02 的对应为 source_inspected：13 个依据类 docstring 的 01-A02 标注，6 个是规划端按 stub 锁定字节与兼容矩阵 D-20–D-23 的归类推断（测试源码中没有 A02 标注）。判定不依赖这 6 个方法的归属：stub 事件流与锁定字节相同另由 EV-C10（10 行 SAME）支撑，D-20–D-23 的旧判断与新严格判断另由 ① 中的 `DifferentialTests` 逐字节锁定、EV-C03 中对应 6 行派生 SAME（run/stdout.bin 第 26–31 行） |
| evidence_refs | EV-C08、EV-C03、EV-C10、EV-C02；[compatibility-matrix.md](compatibility-matrix.md) 第 1–4、8 节（只引用，不重判）；legacy-inventory.md 9.10.6、9.10.7 |
| known_limitations | 旧预期中的 Python 报错原文只在 3.12.10 上锁定；stub 流的 CRLF 字节只在 Windows 生成（`StubTests` 的重跑核对在非 Windows 上跳过）；manifest 中 `platform_scope` 为 windows 的 40 条只在本机生成与核对。R-P12 的内联引用只记测试文件的摘要，这些方法的输入还经过公共夹具 `tests/legacy_harness.py`（`c4e87137…`），按字节复现输入时夹具也须相同（第 10 节 M-14）。**改判说明**：最终取证时（EV-03，历史）本项只有命令级证据、方法级 NOT_RUN，整项不记 PASS；改判的依据是 EV-C08 的方法级输出与 EV-C03、EV-C10 的归档（第 7 节第 6 项、第 10 节 M-06 已关闭） |
| reviewer_or_owner | 共同字段；合同 v1 字段语义的新校验归 09；D-01 等历史歧义输入的处理归 03、07、09（01-D09）；七类的新旧差分归 07、10 |

### 3.3 01-A03 快照字节与哈希

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A03 |
| platform | windows：01 范围内 PASS；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；`protocols.py` `64d75bb0…`（序列化 profile `codekit-config-json-py-v1`；收尾轮没有改动快照函数的行为） |
| baseline_ref | BL-CLOSURE |
| fixture_refs | `synthetic-golden-vectors-c.2`、`synthetic-protocol-sample-1`（manifest `95c58a9b…`） |
| command_or_assertion | EV-C02，21 个方法：`SnapshotTests` 以 A03 命名的 15 个（`test_A03_golden_vectors`、`test_A03_synthetic_sample_is_file_bytes_not_snapshot`、`test_A03_sha256_hex`、`test_A03_snapshot_matches_fixed_expression`、`test_A03_snapshot_is_not_jcs`、`test_A03_snapshot_does_not_mutate_input`、`test_A03_snapshot_root_must_be_object`、`test_A03_snapshot_root_type_checked_before_values`、`test_A03_snapshot_byte_limit`、`test_A03_snapshot_limit_after_serialization`、`test_A03_lower_bound_constants_do_not_reject_valid_values`、`test_A03_underflow_and_negative_zero_integer`、`test_A03_snapshot_does_not_project_machine_fields`、`test_A03_shared_containers_have_serialized_size_budget`、`test_A03_record_validators_budget_shared_dag`）；F015、F016、F018、F019（2 个）；F017（1 个）。<br>fixture 侧（EV-C08，方法级）：`SyntheticTests.test_golden_vectors_byte_exact`（第 97 行）、`test_golden_vectors_match_design_doc_table`（第 98 行）、`test_sample_1_exact_bytes_and_digest`（第 100 行） |
| expected | 7.1：相同有效配置产生相同快照字节与哈希；模型/授权变化改变哈希；机器路径另入环境锁；字节级 golden vectors，不能只比较对象相等 |
| actual | EV-C02：20 个 ok；`SnapshotTests.test_F017_machine_path_projection_belongs_to_02` skipped（第 503/504 行，原文：“01-D05：配置语义投影归 02，F017 由 02 验收；此处未测试，不代表通过”）。EV-C08 三个方法 ok |
| execution_status | windows：**01 范围内 PASS**（字节规则、黄金向量、键序无关、模型/授权变化改变摘要、数组次序与 Unicode 形式不归一化）；**机器路径进入环境锁（F017）：NOT_RUN，归 02**；linux、macos：NOT_RUN |
| evidence_basis | measured |
| evidence_refs | EV-C02、EV-C08 |
| known_limitations | 01 只证明快照器不擅自投影（`test_A03_snapshot_does_not_project_machine_fields`，第 481–482 行），配置语义投影与环境锁由 02 实现与验收（01-D05）。F016 中“重新判断审核有效性”属于 03，01 只断言摘要改变。fixture 侧黄金向量的方法级证据是收尾取证新增的（最终取证时只有命令级） |
| reviewer_or_owner | 共同字段；F017 与环境锁：02 |

### 3.4 01-A04 重复键、非法 schema、非有限数、路径越界、错误哈希的单一原因拒绝

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A04 |
| platform | windows：PASS；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；`protocols.py` `64d75bb0…`（收尾轮新增 `ResourceKind` 的三项声明与 `validate_resource_payload`，R-P10） |
| baseline_ref | BL-CLOSURE |
| fixture_refs | 协议负例 `negative-protocol-*` 135 个（每个从有效样本只改一处；收尾轮新增 11 个针对 R-P11 新字段）；方法级证据：EV-C08 `NegativeTests` 4 个方法（第 75–79 行，其中 `test_each_negative_yields_exactly_manifest_code` 第 75 行，逐个断言 code、field、reason） |
| command_or_assertion | EV-C02，73 个方法：<br>- 以 A04 命名的 32 个：`ConstantsAndErrorTests` 10、`StrictJsonTests` 4、`GitOidTests` 4、`ResourceRefTests` 14。`ResourceRefTests` 中 6 个是收尾轮按 R-P10 新增的：`test_A04_r_p10_declaration_values_validated`、`test_A04_r_p10_default_registry_declarations`、`test_A04_r_p10_public_schema_payload_validator`、`test_A04_r_p10_registration_requires_three_declarations`、`test_A04_r_p10_validate_resource_payload_representations`、`test_A04_r_p10_validator_exceptions_are_wrapped`（第 271–282 行）；<br>- F001–F013、F020、F024、F025、F031–F035 对应的 41 个方法（第 4 节） |
| expected | 7.1 与 7.4：从有效样本一次只改一个缺陷，断言稳定 code 与禁止副作用 |
| actual | 73 个全部 ok；EV-C08 `NegativeTests` 4 个 ok。P2 调和后所有负例断言唯一错误码（多数还断言 `field` 指针），接受多个错误码的断言已删除（protocols-api.md 第 19 节）；R-P10 的登记检查顺序（登记项类型 → 三项已声明 → 同名项）由 `test_A04_r_p10_registration_requires_three_declarations` 固定 |
| execution_status | windows：**PASS**；linux、macos：NOT_RUN |
| evidence_basis | measured |
| evidence_refs | EV-C02、EV-C08 |
| known_limitations | “禁止副作用”在协议函数层断言（不写文件、不调用索引、不修改输入）；新执行入口不存在，入口层副作用无法测试。多缺陷输入不承诺首错，只有恢复函数与 R-P10、R-P11 已固定的检查有固定顺序（protocols-api 第 3.2、8、11、14.2 节）。R-P10 的 `schema_ref` 只登记标识，01 不加载 Schema（jsonschema BLOCKED），`validate_resource_payload` 把 `resource_schema` 记入 skipped |
| reviewer_or_owner | 共同字段 |

### 3.5 01-A05 wait、退出 0、审核、verdict PASS 与 INTEGRATED 可区分

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A05 |
| platform | windows：PASS；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；`protocols.py` `64d75bb0…`（`build_run_dimensions`，维度规则 `codekit01-run-dimensions-v2`）；旧入口 `a00d6934…` |
| baseline_ref | BL-CLOSURE |
| fixture_refs | 无 |
| command_or_assertion | EV-C02，14 个方法：`ConstantsAndErrorTests.test_A05_legacy_verdicts_match_dispatcher`；`RunDimensionTests` 以 A05 命名的 11 个（含 `test_A05_wait_zero_is_only_a_query`、`test_A05_verdict_approval_integration_distinct`、`test_A05_cancel_is_not_success`、`test_A05_usage_unknown_separate_from_protocol`、`test_A05_protocol_complete_rules`）；`test_F040_exit_zero_without_end_evidence`、`test_F041_success_claim_with_nonzero_exit`。<br>旧入口现状（特征化，EV-C07）：`LegacyWaitTest` 14 个方法（P4-C32–C45，例如 `test_LB_EXIT_026_wait_exit_0_for_failed_terminal_state_without_summary`：已结束但失败的状态 wait 仍退出 0）；`LegacyMainInProcessTest.test_LB_EXIT_002_main_maps_keyboard_interrupt_to_130`（白盒）。旧自测 check“wait returns at once for a finished attempt”等（EV-C01） |
| expected | 7.1：数据视图或测试至少包含各维度不一致的反例 |
| actual | EV-C02 的 14 个方法全部 ok；EV-C07 的 14 个 wait 方法与 130 映射全部 ok；EV-C01 的 256 个 check 全部 PASS |
| execution_status | windows：**PASS**；linux、macos：NOT_RUN |
| evidence_basis | measured |
| evidence_refs | EV-C02、EV-C07、EV-C01 |
| known_limitations | 视图只保留旧 verdict、旧状态与集成观测，不提供聚合的“成功”键；审核（03）与集成（12）的新实现不存在。经子进程到达 main 的 130 只有 POSIX 用例（P4-L04，NOT_RUN） |
| reviewer_or_owner | 共同字段；状态展示的消费方为 07、10 |

### 3.6 01-A06 缺 token/费用保留 unknown、不混加币种、派生摘要不重复计费

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A06 |
| platform | windows：01 范围内 PASS；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；`protocols.py` `64d75bb0…`（`validate_usage_observation`、`usage_view`） |
| baseline_ref | BL-CLOSURE |
| fixture_refs | `synthetic-doc-4.3.9-usage-unknown`、`synthetic-usage-reported-cost-1`；负例 `negative-protocol-usage-unknown-*` 13 个、`negative-protocol-usage-cost-*` 17 个（EV-C08 `NegativeTests` 方法级） |
| command_or_assertion | EV-C02，54 个方法：`UsageTests` 以 A06 命名的 35 个；F037（3 个）、F044（3 个）、F045（8 个）、F046（1 个）、F047（4 个）。<br>旧实现现状对照（EV-C09，特征化）：`EventStreamRunTests.test_LB_EVENTS_018_missing_usage_tokens_are_zero_and_cost_unknown`（P4-E21）、`EventStreamRunTests.test_LB_EVENTS_017_duplicate_message_end_double_counts_usage`（P4-E17）、`SummarizeEventsWhiteBoxTests.test_LB_EVENTS_019_cost_status_rules`（P4-E30） |
| expected | 7.1：null、累计/增量、重放、混币种、缓存包含关系、修订样例 |
| actual | EV-C02 的 54 个全部 ok；视图标记 `is_accounting=false`。EV-C09 三个方法 ok：**旧调度器**把缺失 token 记为 0、重复的 message_end 会重复累计用量、未知费用为 null——这是 a4fa199 的现状，与 A06 的新规则冲突，已登记为 D-17、D-18、D-19（兼容矩阵 4.2，归 04、07） |
| execution_status | windows：**01 范围内 PASS**（单条观测与观测视图）；**唯一记账：不在 01（归 07，01-D08），未实现，NOT_RUN**；linux、macos：NOT_RUN |
| evidence_basis | measured |
| evidence_refs | EV-C02、EV-C09、EV-C08 |
| known_limitations | ISO 4217 成员资格、账户范围、估算规则未检查（protocols-api 第 16 节）；真实 Pi 的 usage 是增量还是累计仍未核实（legacy-inventory 11.3 第 1、2 条，归 04）；缺字段类的“消息带 usage 但缺 token 字段”没有 legacy fixture（第 7 节第 24 项） |
| reviewer_or_owner | 共同字段；记账：07；来源口径：04 |

### 3.7 01-A07 G0–G6、范围、候选漂移、预算竞争、取消、补丁完整性有回归映射

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A07 |
| platform | windows：PASS（范围限定，R-02）；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；被测对象 a4fa199 的 `scripts/pi_dispatch.py`（`a00d6934…`，测试中经 `legacy_harness.legacy_facts` 核对 LF 归一后的 blob 摘要）；4 个特征化测试文件与最终取证时字节相同；公共夹具 `tests/legacy_harness.py` 由 `3d133d5f…` 改为 `c4e87137…`（收尾轮加入清理前的归属核对） |
| baseline_ref | BL-CLOSURE；BL-PRE、BL-FINAL 为历史对照 |
| fixture_refs | 代码内联 fixture（R-P12）：legacy-inventory.md 第 12 节 159 个方法各自的 `inline:<测试文件>::<类>.<方法>@<测试文件 sha256>`，比较投影 `codekit01-characterization-v1`（该方法中的断言集合，清单 12.10）；输入经公共夹具 `tests/legacy_harness.py` 与 `tests/stub_pi.py` 场景构造 |
| command_or_assertion | 验收核对（baseline-report 修订 6 第 8 节），按 R-02：六类（G0–G6、范围、候选漂移、预算竞争、取消、补丁完整性）每类、G0–G6 每门都必须有已实测的失败路径断言；满足后记“PASS（Windows，范围限定）”，未覆盖的子分支逐条登记为 `unmet_within_scope`；某一类或某一门没有任何失败路径断言则为 FAIL。映射见 legacy-inventory.md 第 2、10、12 节；方法索引见 baseline-report 第 7.2 节（62 个方法，P4-G01–G24、L01–L16、L18–L22、C25–C28、C58、C59、C62、C63、C68–C75、E20；P4-L17 不在其中，清单第 12.4 节把它归在六类之外（01-A08））；逐门见本文第 6 节 |
| expected | 7.1：逐条来源测试与断言映射；旧名称含 v2 不构成证明 |
| actual | EV-C05、EV-C06、EV-C07、EV-C09：4 个特征化测试文件 159 个方法中 156 个 ok、3 个 POSIX 方法 skipped（P4-L03、L04、C52），方法集合与结果和最终取证相同（本修订按 legacy-inventory.md 第 12 节 159 行逐条在归档中定位核对）；第 7.2 节 62 个方法中 60 个 ok，P4-L03、L04 skipped。<br>逐类、逐门都有 measured / PASS 的失败路径方法（baseline-report 修订 6 第 8 节）：G0 P4-G01；G1 P4-G02–G05、G07、G24、L01、L05、L22、E20；G2 P4-G08、G09；G3 P4-G08、G10–G12、G14、G18；G4 P4-G10、G11、G13、G14、G18；G5 P4-G09、G23（见 execution_status）；G6 P4-G13、G15–G17；范围 P4-G08、C25–C28、C72–C75；候选漂移 P4-G09、G13–G15、C62；预算竞争 P4-G06、L06–L16、L18–L21；取消 P4-G07、L01、L02、L22、C68–C71；补丁完整性 P4-G16–G19、C63。<br>EV-C01 的 256 个 check 全部 PASS |
| execution_status | windows：**PASS（范围限定，按 R-02）**。<br>**G5**：a4fa199 的 G5 恒通过，没有可触发的失败路径；P4-G09、G23 断言它在 PASS 记录与失败记录中都保持通过并带固定备注，baseline-report 把这当作这一门的失败路径映射（与修订 3 相同）。R-02 原文没有单独说到这种门，**待规划端确认**（第 7 节第 22 项）；如果要求 G5 也有可触发的失败断言，那是旧实现中不存在的行为，本项为 **FAIL**。<br>linux、macos：NOT_RUN |
| evidence_basis | measured（运行结果）；方法断言了什么取自清单第 12 节登记的测试源码与 docstring（source_inspected，修订 3 抽查；4 个测试文件之后字节未变，修订 6 与本修订都没有重新核对断言内容） |
| evidence_refs | EV-C05、EV-C06、EV-C07、EV-C09、EV-C01；baseline-report 第 7.1、7.2、8、13.4 节；legacy-inventory.md 第 2、12 节与 12.10 |
| known_limitations | `unmet_within_scope`（baseline-report 第 8 节，迁移比较时记 NOT_COVERED）：POSIX SIGINT（P4-L03、L04）与经子进程到达的 130；:3319-3332 窗口、collect 期间中断、_terminate_tree 期间再收到信号、SIGTERM/SIGHUP；锁与预算的真实并发竞态；--fresh/mutate 只测了“补丁字节被改”一种情形、真实的 `apply --cached` 往返失败没有构造；G2/G3/G4 三条备注未经 verdict 断言、G6 重新快照写 Git 对象未断言、diff_error 时 G2 没有备注；submodule、mode_changed、sensitive_file、dependency_manifest_changed、真实的非 UTF-8 文件名、review_hints；Linux、macOS 与 Linux 的 PDEATHSIG 分支；**修订 6 补**：LB-EXIT-032（spawn 失败转 INFRA_FAILURE）、LB-LIFE-037（预检证据被覆盖）、LB-LIFE-038（claim 为普通文件时的判断不一致）、LB-EXIT-037（tasklist 失败时 pid_alive 的结果）。<br>PASS 只表示“a4fa199 现状如此”，不表示现状正确；49 个白盒方法只证明函数层现状；标“可疑”的现状仍按 legacy-inventory.md 11.2 待裁决。<br>**文档 3.2 的两个字段**：已按 R-P12 回填（legacy-inventory.md 9.10.6、9.10.7、12.10）：224 行中 NOT_COVERED 由 181 行降为 67 行；其中 (c) 类 23 行只有旧自测的 check，R-P12 没有规定它们的登记写法，待规划端决定（第 7 节第 23 项）；159 个 P4 方法都有内联 fixture 与 `codekit01-characterization-v1`。这些是旧路径的锁定，不是文档 6.6 的新旧差分（差分 NOT_RUN，新路径归 07、10） |
| reviewer_or_owner | 判定：baseline-report 修订 6；G5 读法：规划端；清单：legacy-inventory 编写任务；独立复审：待进行 |

### 3.8 01-A08 标识归属与恢复

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A08 |
| platform | windows：01 范围内 PASS；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；`protocols.py` `64d75bb0…`（`new_request_id`、`new_run_id`、`derive_run_context`、`validate_run_context`） |
| baseline_ref | BL-CLOSURE |
| fixture_refs | `synthetic-doc-4.1.3-run-context`；负例 `negative-protocol-run-context-*` 16 个（EV-C08 `NegativeTests` 方法级） |
| command_or_assertion | EV-C02，22 个方法：`IdentifierTests` 以 A08 命名的 5 个与 F021 的 2 个；`RunContextTests` 以 A08 命名的 13 个与 `test_F022_reconnect_and_replay_keep_identity`、`test_F023_executor_retry_new_run_same_request`。<br>旧 attempt 编号现状（EV-C06）：`AttemptNumberTests.test_LB_LIFE_002_first_attempt_is_1_and_only_prepare_advances`、`AttemptNumberTests.test_LB_LIFE_001_number_is_max_plus_one_and_never_zero`（P4-L25、L26） |
| expected | 7.2：重连不换 run，真正重试换 run，不换 request 预算根 |
| actual | 24 个方法全部 ok。executor_retry 的 attempt 由调用方传入受信分配器的值，只核对不小于 parent.attempt（R-P2）；旧实现首个 attempt 为 1、只有 prepare 使编号前进（01-D03） |
| execution_status | windows：**01 范围内 PASS**（格式、派生规则与绑定校验）；**标识的持久唯一性、分配方与 request 预算根：不在 01（归 07），NOT_RUN**；linux、macos：NOT_RUN |
| evidence_basis | measured |
| evidence_refs | EV-C02、EV-C06 |
| known_limitations | 合同引用、版本、任务与 request 的一致性只做形状与登记检查，与受信记录一致性未实现（07、09）；并发 prepare 撞名重试没有测试 |
| reviewer_or_owner | 共同字段；分配与预算根：07；plan_version 单调：09 |

### 3.9 01-A09 Schema 家族与降级防护

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A09 |
| platform | windows：PASS（元校验 BLOCKED）；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；`protocols.py` `64d75bb0…`；`schemas/codekit-public-v1.schema.json` `7895442d…`（`$id` `urn:codekit:public-protocol:1`） |
| baseline_ref | BL-CLOSURE |
| fixture_refs | `negative-protocol-run-context-schema-version-2`、`negative-protocol-run-event-schema-version-2`、`negative-protocol-usage-unknown-schema-version-2`（EV-C08 `NegativeTests` 方法级）；`legacy/contracts/` 下 3 份 JSON 合同与 manifest 本身（`PublicEntryRejectionTests`） |
| command_or_assertion | EV-C02，23 个方法：以 A09 命名的 18 个（`ConstantsAndErrorTests` 1、`SchemaRoutingTests` 8、`SchemaFileTests` 9）；`SchemaRoutingTests.test_F013_schema_version_type`、`test_F013_require_schema_version_reference_behavior`、`test_F014_unknown_version_no_legacy_fallback`；`StrictJsonTests.test_F013_integer_range`；`ResourceRefTests.test_F032_unknown_kind_and_unknown_field`。<br>EV-C08（收尾轮，M-04 把兼容矩阵第 1 节的抽查写成回归测试）：`PublicEntryRejectionTests.test_contract_v1_json_is_not_a_public_record`（第 81 行：合同 v1 交给公共入口报 `E_SCHEMA_RECORD_TYPE` 或 `E_COMPAT_UNSUPPORTED`，不降级、不回退 v1）、`test_fixture_manifest_set_is_internal_and_version_2_rejected`（第 82 行）、`test_baseline_records_are_internal`（第 80 行） |
| expected | 7.2：未知新版本拒绝；不得伪装成 v1 绕过审核 |
| actual | EV-C02：22 个 ok；`SchemaFileTests.test_A09_jsonschema_metaschema_optional` skipped（第 367/368 行，原文：“未安装 jsonschema，未做元校验（本机不得安装依赖，见 01-L01）”）。EV-C08 三个方法 ok |
| execution_status | windows：**PASS**（路由、版本与字段封闭；合同 v1 与 01 内部记录不被当作公共记录）；Draft 2020-12 元校验：**BLOCKED**（缺工具且未授权安装，01-L07）；linux、macos：NOT_RUN |
| evidence_basis | measured |
| evidence_refs | EV-C02、EV-C08 |
| known_limitations | 本地 Schema 文件不被程序加载；结构一致性由测试内的迷你校验器核对（`test_A09_mini_validator_and_protocols_agree_on_structure`，第 371–372 行），不是 jsonschema。是否安装 jsonschema 见第 9 节 (d)。`test_baseline_records_are_internal` 按目录现场查找 `evidence/` 中的取证记录，取证时读到 9、18、18、9 份，现在是 19、38、38、19 份（第 10 节 R-13） |
| reviewer_or_owner | 共同字段 |

### 3.10 01-A10 路径与实际消费一致

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A10 |
| platform | windows：01 范围内 PASS；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；`protocols.py` `64d75bb0…`（`validate_business_path`、`check_no_name_collisions`、`resolve_existing_path_for_review`；收尾轮没有改动路径检查） |
| baseline_ref | BL-CLOSURE |
| fixture_refs | 路径用例在 tempfile 目录中现场构造；协议负例 `negative-protocol-resource-ref-path-*` 等（EV-C08 `NegativeTests` 方法级） |
| command_or_assertion | EV-C02，42 个方法：以 A10 命名的 31 个（`BusinessPathTests` 6、`PhysicalPathTests` 25）；F024（1）、F025（5）、F026（1）、F027（1）、F028（1）、F029（1）、F030（1）。收尾轮没有新增 A10 方法，方法集合与结果和最终取证相同 |
| expected | 7.2：词法/物理/授权分层；竞态与特殊文件测试；未实现的平台能力不对外宣称 |
| actual | 40 个 ok，包括本机实际创建的 symlink（F027）、junction（F028）、用 FSCTL 写入的重解析点写法（`test_A10_windows_link_target_forms_measured`）、fsutil 启用大小写敏感的目录（`test_A10_case_sensitive_directory_sibling_is_escape`）、手工设置的短名（`test_A10_manual_short_name_alias_black_box`）。`PhysicalPathTests.test_F029_replacement_after_check`、`test_F030_fifo_device_hardlink` skipped（第 223/224、225/226 行，原文：“01-D06：……由后续访问实现模块验收，此处未测试，不代表通过”） |
| execution_status | windows：**01 范围内 PASS**（词法拒绝与静态审阅；物理检查按 R-P9 定位为“静态审阅 + 纵深防御”，**不是安全访问保证**）；**F029 检查后替换、F030 FIFO/设备/共享硬链接、生产级安全 open/create：NOT_RUN，归后续访问实现模块（01-D06）**；授权层（保护路径判断）未实现，归 03；linux、macos：NOT_RUN |
| evidence_basis | measured |
| evidence_refs | EV-C02 |
| known_limitations | 已知不检测：TOCTOU 与并发替换、检查后父目录或目标被替换、硬链接（`test_A13_hard_link_alias_is_known_not_detected` 固定的是当前限制）、挂载点、尚未枚举的 NT/Win32 写法、同账户篡改（protocols-api 第 7 节清单）。POSIX 的物理 `..` 分支在本机只有白盒注入（`test_A10_link_walk_physical_dotdot_branch`）。8.3 短名形态按 R-P3 勘误“以实现为准”（M-02 已关闭）：实现要求 `~` 之前至少 1 个字符，所以没有前缀的 `~1`、`~12` 照常接受（protocols-api 第 7 节）；不拒绝手工设置、不含 `~` 的短名与 ANSI best-fit 字符（R-P3、R-P5），只按字符串比较的下游须自行复核 |
| reviewer_or_owner | 共同字段；生产级访问：后续访问实现模块（01-D06，模块未指定）；保护与授权：03 |

### 3.11 01-A11 事件幂等与完整性

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A11 |
| platform | windows：01 范围内 PASS；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；`protocols.py` `64d75bb0…`（`validate_run_event`、`assess_event_log`（:2385）、`append_event`（:2442）、`recover_next_seq`（:2537）、`recover_append_state`（:2554）、`assess_stream_integrity`；收尾轮按 M-01 在四个日志函数中加入 request/role 绑定核对） |
| baseline_ref | BL-CLOSURE |
| fixture_refs | `synthetic-doc-4.3.1-run-event`、`synthetic-vendor-event-1`；负例 `negative-protocol-run-event-*` 31 个、`negative-protocol-vendor-event-*` 9 个（EV-C08 `NegativeTests` 方法级） |
| command_or_assertion | EV-C02，46 个方法：<br>- 以 A11 命名的 38 个（`TimeTests` 5、`EventTests` 33），其中收尾轮按 M-01 新增 5 个：`test_A11_m01_append_event_request_and_role_binding`、`test_A11_m01_binding_reason_order_is_fixed`、`test_A11_m01_entry_points_agree`、`test_A11_m01_event_log_request_and_role_binding`、`test_A11_m01_unreadable_binding_fields`（第 83–92 行）；另含 `test_A11_recover_next_seq_from_persisted_records`、`test_A11_recover_append_state_after_crash`、`test_A11_F037_append_event_replay_of_older_seq_keeps_state`；<br>- `EventTests.test_F037_duplicate_replay_is_idempotent`、`UsageTests.test_F037_usage_replay_counted_once`、F038（2）、F039（2）、F040、F041 |
| expected | 7.2：seq 重复、冲突、缺口、截断、崩溃恢复分别有结果 |
| actual | 46 个全部 ok。同一 run 中改写 request_id 或非空 role 的记录，`assess_event_log` 记入 binding_errors、`append_event` 报 `E_CONTEXT_BINDING`，恢复函数按 run → request → role 的固定顺序取 reason（protocols-api 第 11 节、第 19 节“收尾轮”） |
| execution_status | windows：**01 范围内 PASS**（协议函数层：给定持久记录列表时的判定与恢复，日志内部的 run/request/role 绑定一致）；**事务化的持久追加与序号分配、真实进程崩溃后的恢复：未实现，NOT_RUN，归 07、04**；日志与受信 RunContext 是否一致不由这些函数判断（04、07）；linux、macos：NOT_RUN |
| evidence_basis | measured |
| evidence_refs | EV-C02 |
| known_limitations | M-01 已关闭：绑定指日志内部一致，不指与受信 RunContext 一致（protocols-api 第 11 节写明 complete 的含义）。空日志 `complete=True` 只表示序列一致（R-P8）。真实 Pi 事件类型与结束判定未登记（01-D07，归 04）。M-11 已关闭：4.3.2 的“派生视图修订与 view_id”（04）与“跨 run 的先后关系”（10）的归属已写入 protocols-api.md 第 11、16、17 节，01 没有对应接口，实现在 04、10（第 8 节移交） |
| reviewer_or_owner | 共同字段；持久化与事务：07、04 |

### 3.12 01-A12 脱敏证据来源

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A12 |
| platform | windows：01 范围内 PASS；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；`protocols.py` `64d75bb0…`（`validate_raw_span`、`validate_fixture_manifest_entry`（:3522）、`validate_fixture_manifest_set`（:3551）；收尾轮按 R-P11 增加条目字段与第 3b、5 步，第 5 步按受控词表判定（R-P11 补充）；`fixture-manifest` 类型的载荷校验器，R-P10） |
| baseline_ref | BL-CLOSURE |
| fixture_refs | manifest `95c58a9b…`（188 条，全部 `synthetic_fixture` 表示，按 R-P11 登记 integrity：complete 184、truncated 2、corrupted 2；platform_scope：windows 40、any 148；capture 全部 null；protocol_structure_preserved：true 10、null 178；traceable 全部 true）；`synthetic-raw-segment-1`、`synthetic-doc-c.1-manifest-entry-completed`；负例 `negative-protocol-fixture-manifest-*` 26 个（收尾轮新增 11 个） |
| command_or_assertion | EV-C02，25 个方法：`EventTests` 以 A12 命名的 4 个；`ProvenanceTests` 以 A12 命名的 18 个，其中收尾轮按 R-P11 新增 6 个：`test_A12_r_p11_check_order_structure_then_steps`、`test_A12_r_p11_integrity_limits_complete_stream_claims`、`test_A12_r_p11_manifest_set_reports_entry_pointer`、`test_A12_r_p11_new_fields_structure`、`test_A12_r_p11_structure_preservation_limits_field_semantics_claims`、`test_A12_r_p11_traceable_and_capture_rules`（第 245–256 行），另 `test_A12_appendix_c1_example_needs_completion`（第 227–228 行）补齐新字段后逐项去掉一个新字段断言 `missing_field`；`ResourceRefTests.test_A12_r_p10_fixture_manifest_payload_validator`（第 293–294 行）；`EventTests.test_F042_redaction_changes_offsets`、`ProvenanceTests.test_F043_synthetic_cannot_claim_captured`。<br>fixture 清单侧（EV-C08，方法级）：`ManifestTests` 7 个（第 66–74 行，含 `test_provenance_consistency`、`test_claim_rule_rejects_real_and_unlisted_legacy_claims`、`test_claim_spelling_variants_rejected`）；`R11Tests` 6 个（第 83–92 行，含 `test_every_entry_follows_registration_rules`、`test_whole_manifest_bytes_pass_fixture_manifest_payload_validator`）；`CredentialScanTests` 4 个（第 19–25 行，文档 8.3“fixture 含真实凭据”的发现部分）；`StubTests.test_stub_cwd_placeholder_and_no_local_paths`（第 93 行） |
| expected | 7.2：captured/redacted/synthetic 不混淆；范围定位的是引用版本字节 |
| actual | EV-C02 的 25 个与 EV-C08 的 18 个全部 ok。`CredentialScanTests.test_fixture_files_contain_no_credential_shapes`（EV-C08 第 21 行 ok）扫描 `tests/fixtures/codekit01/` 下 189 个文件，15 类凭据形态没有**非白名单**命中（measured；该方法丢弃白名单放行结果，`found, _allowed = …`，`tests/test_codekit01_fixtures.py:2636`，只在非白名单命中不为空时失败，:2643-2646）。“也没有白名单放行”**不是运行结论**，只是静态核对（source_inspected）：第四次修订在 189 个文件的原字节、UTF-16 LE/BE 两种对齐与能解析的 JSON/JSONL 字符串中，不区分大小写查找三个白名单标记（`DEMO_REVIEW_SECRET`、`DEMO_TOKEN_FOR_REVIEW`、`SYNTHETIC_*CREDENTIAL`），0 处，由此推断没有放行（兼容矩阵修订 12 的 9.1 节、E19） |
| execution_status | windows：**01 范围内 PASS**（来源规则与能力声明；R-P11 条目字段与登记规则；原始段范围按被引用版本计；fixture 目录的凭据形态扫描）；**真实 captured 样本：仓库中没有（NOT_RUN，归 04 采集）**；脱敏前后偏移映射：未实现（归 04）；凭据发现后的处置流程：没有（规划端与用户）；linux、macos：NOT_RUN |
| evidence_basis | measured；方法与裁决的对应为 source_inspected；“fixture 中没有白名单放行”为 source_inspected（静态核对白名单标记，不是 EV-C08 的运行结论） |
| evidence_refs | EV-C02、EV-C08 |
| known_limitations | M-03 已关闭（R-P11）。测试不断言白名单放行结果为空，要把“没有白名单放行”变成运行结论，需要改测试后重新取证（第 10 节 M-16）。仍未证明：`platform_scope` 与 `traceable` 是登记者的声明，产品入口不核对追溯链是否完整，也不代表已在所列平台运行；`capture` 只有结构规则与负例，没有真实采集样本；captured 条目只有单元测试覆盖。第 5 步的受控词表比 R-P11 原文宽（失败关闭方向，R-P11 补充已采纳），词表之外的写法不受限制（protocols-api 14.2 节“现行规则的空缺”）。凭据扫描是形态匹配，只发现 15 类形态，清单之外的形态不会被发现（兼容矩阵 9.1 节） |
| reviewer_or_owner | 共同字段；真实采集与脱敏映射：04；凭据处置：规划端与用户 |

### 3.13 01-A13 不可变发布与补偿

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A13 |
| platform | windows：01 范围内 PASS；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；`sealing.py` `af92c1f9…`（`seal_bytes`、`read_sealed`；收尾轮没有改动）；`protocols.py`（`check_resource_dag`） |
| baseline_ref | BL-CLOSURE |
| fixture_refs | 无（在 tempfile 存储根中现场构造） |
| command_or_assertion | EV-C02，34 个方法：`SealingTests` 以 A13 命名的 29 个（含 `test_A13_seal_publishes_then_indexes`、`test_A13_seal_idempotent_same_bytes`、`test_A13_seal_conflict_does_not_overwrite`、`test_A13_seal_readback_mismatch_publishes_nothing`、`test_A13_read_sealed_missing_and_tampered`、`test_A13_seal_post_publish_escape_is_reported`）；`SealingTests.test_F048_index_failure_leaves_unreferenced_candidate`、`test_F048_index_failure_any_exception`；`ResourceRefTests` F036 的 3 个。收尾轮没有新增 A13 方法，方法集合与结果和最终取证相同 |
| expected | 7.2：写入成功/索引失败、索引不可见、摘要不符等故障均不发布可用假引用 |
| actual | 34 个全部 ok。索引失败时不返回引用、文件作为未引用候选保留、可用相同字节幂等补录；读回摘要不符不发布 |
| execution_status | windows：**01 范围内 PASS**（R-P9 限定的“发布与索引补偿”，存储根须由可信核心独占控制）；**崩溃持久性：NOT_RUN**——没有断电或进程崩溃注入，Windows 上不 fsync 父目录（`DIRECTORY_FSYNC_SUPPORTED=False`，`sealing.py:63`；`SEALING_LIMITATIONS` 第 1、2 条，即 protocols-api.md 第 15 节“已知不检测、不保证”清单第 8 项；第四次修订更正条号，此前误写为常量的第 8 条）；归持久存储的实现模块（事件日志事务化归 07、04，封存存储根的生产级访问归 01-D06 访问实现模块；具体合同未指定，见第 7 节第 2 项，事件日志部分见第 1 项）；linux、macos：NOT_RUN |
| evidence_basis | measured |
| evidence_refs | EV-C02 |
| known_limitations | 多个用例是白盒注入（读回不符、发布后越界、临时文件独占与 fsync），属于函数层证据；与根外共享数据的硬链接不检测；发布前失败会残留本次新建的空父目录（不回滚，8.4）。“受控清理未引用候选”没有实现（07、04，兼容矩阵 9.1 节）。**8.4 清理前的归属核对（测试工具侧，不计入本项的 PASS 依据）**：`tests/legacy_harness.py` 的 `remove_tree`（:1124，区域由 `make_temp_area` :996 建立）与 `tests/codekit01_legacy.py` 的 `_rmtree`（:814，核对函数 `ownership_problem` :776）在删除前核对归属，EV-C08 `HarnessCleanupOwnershipTests` 11 个（第 42–63 行）与 `CleanupOwnershipTests` 10 个（第 1–13 行）都是 ok（R-12 已关闭）；产品代码（`sealing.py`、`baseline.py`）不做递归删除（兼容矩阵 9.2 节） |
| reviewer_or_owner | 共同字段；持久化：07、04；生产级访问：后续访问实现模块 |

### 3.14 01-A14 无副作用导入

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A14 |
| platform | windows：PASS；linux、macos：NOT_RUN |
| implementation_revision | 共同字段；`scripts/codekit/__init__.py`、`protocols.py`、`sealing.py`、`baseline.py`（2.1，收尾取证输入清单的字节） |
| baseline_ref | BL-CLOSURE |
| fixture_refs | 无 |
| command_or_assertion | EV-C02：`ImportSideEffectTests.test_F049_import_has_no_side_effects`（第 167–168 行；子进程 `-B -I` 导入 codekit、protocols、sealing、baseline，审计钩子记录网络、进程、文件写入与删除、环境变量读取）、`test_A14_probe_detects_violations`（第 163–164 行；同一探针能捕获故意的违规）、`test_A14_sources_do_not_touch_environment`（第 165–166 行；源码不出现 environ/getenv 等名称）。EV-C04：`ImportSideEffectTests.test_import_runs_no_command_and_writes_nothing`（取证工具，第 20 行） |
| expected | 7.2：导入协议模块不读凭据、不启动 CLI、不联网、不修改工作区 |
| actual | 4 个方法全部 ok（针对收尾轮改动后的 `protocols.py` 字节） |
| execution_status | windows：**PASS**；linux、macos：NOT_RUN |
| evidence_basis | measured |
| evidence_refs | EV-C02、EV-C04 |
| known_limitations | 只覆盖导入阶段；函数调用时的副作用由各函数的测试断言 |
| reviewer_or_owner | 共同字段 |

### 3.15 01-A15 平台声明与能力

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A15 |
| platform | windows：已实测并单独记录；linux：NOT_RUN；macos：NOT_RUN |
| implementation_revision | 共同字段 |
| baseline_ref | BL-CLOSURE；BL-PRE、BL-FINAL 为历史对照 |
| fixture_refs | 无；manifest 中 `platform_scope` 为 windows 的 40 条只在本机生成与核对 |
| command_or_assertion | 10 次收尾取证的平台事实（20 份 `environment.json` 字节相同，sha256 `097cb8a4…`，与最终取证、实施前基线相同）；Windows 专属实测：`PhysicalPathTests.test_F028_junction_escape`、`test_F027_symlink_escape`、`test_A10_windows_link_target_forms_measured`、`test_A10_case_sensitive_directory_sibling_is_escape`（EV-C02）；`CancelTests.test_LB_LIFE_017_ctrl_break_during_pi_run_is_cancelled_exit_1_not_130`、`test_LB_LIFE_035_ctrl_break_before_claim_kills_dispatcher_without_130`（EV-C06）；旧自测 `test_timeout`、`test_dispatcher_killed` 的 Job Object 分支（EV-C01）；`StubTests.test_stub_regeneration_matches_locked_bytes`（EV-C08，只在 Windows 运行） |
| expected | 7.2：linux/macos/windows 分别记录结果；模拟 Windows 路径不算 Windows 实测 |
| actual | Windows：上述方法全部 ok，均为真实系统调用（不是模拟名字）。在 Windows 上跳过的 POSIX 分支：P4-L03、L04（EV-C06）、P4-C52（EV-C07）、旧自测 `test_wrapper_interpreters_and_literal_arguments`（0 个 check）、Linux 的“PDEATHSIG stops pi”。Linux、macOS：10 条命令都没有运行 |
| execution_status | windows：**已实测记录**（本项在 Windows 维度满足“分别记录、真实平台”）；linux：**NOT_RUN**；macos：**NOT_RUN**；**整项不记 PASS**（三平台中两个没有结果） |
| evidence_basis | measured（Windows）；linux、macos：unknown |
| evidence_refs | EV-C01–EV-C10 的 `pre/`、`post/environment.json`；EV-C02、EV-C06、EV-C08 |
| known_limitations | 附录 E.1 记载的 Linux 沙箱结果（Python 3.13.5，21 项通过）是文档自述，不对应本仓库提交，不计（source_reported）。旧预期中的报错原文只在 Python 3.12.10 上锁定；stub 流字节只在 Windows 生成 |
| reviewer_or_owner | 共同字段；其他平台：05（三平台运行）与第 9 节 (c) |

### 3.16 01-A16 参考与项目验证隔离

| 字段 | 内容 |
|---|---|
| acceptance_id | 01-A16 |
| platform | windows（分栏规则本身不分平台）；linux、macos：applicability=not_applicable，applicability_reason：分栏记录是报告与证据目录的结构规则，不随平台变化（01-L09）。这不表示 Linux、macOS 上有任何测试运行或通过，那里各栏的测试结果仍是 NOT_RUN |
| implementation_revision | 共同字段；附录 B 参考文件摘要与附录 E.2 一致（`protocols_reference.py` `ca149cef…`、`test_protocols_reference.py` `b6ed4dee…`、`public-protocol.schema.json` `7895442d…`） |
| baseline_ref | BL-CLOSURE；BL-PRE、BL-FINAL 为历史对照 |
| fixture_refs | 无 |
| command_or_assertion | 验收核对（baseline-report 修订 6 第 8 节）：报告、`evidence/closure/INDEX.md` 与证据目录是否把附录 B 参考代码的验证与项目测试分栏记录，结论互不代替。F050 的取证工具方法（EV-C04）另证“旧基准未运行或漂移时不形成一致基线” |
| expected | 7.2：沙箱参考代码测试和项目原有全量测试分栏记录，不能互相代替 |
| actual | 收尾取证分四栏：legacy_project（EV-C01）、legacy_characterization（EV-C05、C06、C07、C09）、project_protocols（EV-C02、C08，以及 `codekit01_legacy.py` 的 EV-C03、C10；这两条的归栏是基线报告的分类，capture.json 没有栏字段）、baseline_tool（EV-C04）；附录 B 参考自测单列在 reference_code 栏（EV-R，FAIL 保留），最终取证与收尾取证都没有重跑，也没有并入；`evidence/closure/INDEX.md` 第 2 节写明 10 次都是项目验证 |
| execution_status | **PASS** |
| evidence_basis | measured |
| evidence_refs | EV-C01–EV-C10、EV-R；baseline-report 第 6、8、13 节；closure/INDEX.md 第 2 节 |
| known_limitations | M-08 已关闭：legacy-inventory.md 第 0.5、12.1 节已改称“01 新代码测试（公共协议、fixtures、取证工具）”（本修订只读核对第 0.5 节原文） |
| reviewer_or_owner | 判定：baseline-report 修订 6；独立复审：待进行 |

## 4. 附录 C.3 的 01-F001–F050

- 方法名取自 `tests/test_protocols.py`（EV-C02），F050 取自 `tests/test_baseline_tool.py`（EV-C04）；结果按收尾取证归档 `run/stderr.bin` 逐方法匹配。本修订用 AST 列出当前源码的方法，与归档输出逐一对应：89 个 `test_Fxxx_` 方法与 `test_A11_F037_…` 都在，名称与下表一致；与最终取证（EV-02、EV-04，历史）相比，F 方法集合与结果都没有变化。
- “Windows”列的 PASS 都是 measured，范围只限该用例的断言；Linux、macOS 列除注明外都是 NOT_RUN。
- `tests/test_codekit01_fixtures.py`（EV-C08）中相关的 fixture 方法现在有方法级结果，只在“说明与归属”列引用，不计入本表的 PASS 计数。
- 合计：47 个用例在 Windows 上有方法级 PASS；F017、F029、F030 为 NOT_RUN。

| 用例 | C.3 场景 → 预期 | 测试方法（类.方法） | Windows | 关联验收 | 说明与归属 |
|---|---|---|---|---|---|
| 01-F001 | 合法 UTF-8 对象 → 解析成功且值不变 | `StrictJsonTests.test_F001_valid_utf8_object_unchanged`、`test_F001_scalars_and_surrounding_whitespace` | PASS（ok ×2） | A04 | |
| 01-F002 | 顶层重复键 → E_JSON_DUPLICATE_KEY | `StrictJsonTests.test_F002_top_level_duplicate_key` | PASS | A04 | |
| 01-F003 | 嵌套重复键 → 同错误并定位 | `StrictJsonTests.test_F003_nested_duplicate_key_pointer` | PASS | A04 | |
| 01-F004 | `a` 与 `a` 重复 | `StrictJsonTests.test_F004_escaped_duplicate_key` | PASS | A04 | |
| 01-F005 | NaN/Infinity → 拒绝非有限数 | `StrictJsonTests.test_F005_non_finite_literals` | PASS | A04 | 旧入口对 cost 的 Infinity 放行，登记为 D-20；收尾轮已落为 legacy 负例（EV-C08 `CompatMatrixDCaseTests.test_d20_non_finite_cost_amount`，第 14 行，ok） |
| 01-F006 | `1e10000` 溢出 → 拒绝 | `StrictJsonTests.test_F006_float_overflow` | PASS | A04 | |
| 01-F007 | 新 JSON 带 BOM → E_JSON_BOM | `StrictJsonTests.test_F007_bom_rejected` | PASS | A04 | |
| 01-F008 | 无效 UTF-8 → E_JSON_ENCODING | `StrictJsonTests.test_F008_invalid_utf8` | PASS | A04 | 旧入口的对应差异 D-22 已落为 legacy 负例（EV-C08 `test_d22_invalid_utf8`，第 16 行，ok） |
| 01-F009 | 孤立 surrogate → E_JSON_UNICODE | `StrictJsonTests.test_F009_lone_surrogate` | PASS | A04 | |
| 01-F010 | 合法 surrogate pair → 解码成功 | `StrictJsonTests.test_F010_surrogate_pair_accepted` | PASS | A04 | |
| 01-F011 | 尾随第二个文档 → E_JSON_SYNTAX | `StrictJsonTests.test_F011_trailing_document_and_syntax`、`test_F011_unescaped_quote_is_syntax_not_limit`、`test_F011_syntax_reason_is_fixed_position_in_hint` | PASS（ok ×3） | A04 | |
| 01-F012 | 输入/深度越限 → E_JSON_LIMIT，不发布 | `StrictJsonTests.test_F012_empty_and_byte_limit`、`test_F012_depth_limit`、`test_F012_depth_ignores_brackets_in_escaped_strings`、`test_F012_long_parent_pointer_is_not_quadratic`、`test_F012_recursion_is_limit_not_crash`；`SnapshotTests.test_F012_value_depth_same_as_parser` | PASS（ok ×6） | A04 | docstring 另引 F012：`RunContextTests.test_A08_derive_validates_contract_ref_before_copy`（ok）。旧入口深层嵌套抛 RecursionError，登记为 D-21，已落为 legacy 负例（EV-C08 `test_d21_deep_nesting`，第 15 行，ok） |
| 01-F013 | schema_version 为 true/字符串/1.0 → 类型拒绝 | `StrictJsonTests.test_F013_integer_range`；`SchemaRoutingTests.test_F013_schema_version_type`、`test_F013_require_schema_version_reference_behavior` | PASS（ok ×3） | A04、A09 | 旧合同入口接受 true 与 1.0（D-04、D-05，归 09） |
| 01-F014 | 未知版本 → 不支持，不回退 legacy | `SchemaRoutingTests.test_F014_unknown_version_no_legacy_fallback` | PASS | A09 | |
| 01-F015 | 仅键序不同 → 相同字节与摘要 | `SnapshotTests.test_F015_key_order_irrelevant` | PASS | A03 | |
| 01-F016 | 仅模型或授权改变 → 摘要改变 | `SnapshotTests.test_F016_model_or_authorization_change_changes_digest` | PASS | A03 | “重新判断审核有效性”归 03，01 只断言摘要改变 |
| 01-F017 | 仅机器 executable 路径改变 → 语义快照不变、环境锁变化 | `SnapshotTests.test_F017_machine_path_projection_belongs_to_02` | **NOT_RUN**（skipped，EV-C02 第 503/504 行） | A03 | 跳过原因：“01-D05：配置语义投影归 02，F017 由 02 验收；此处未测试，不代表通过”。**归 02**。01 只锁定快照器不投影：`SnapshotTests.test_A03_snapshot_does_not_project_machine_fields`（ok） |
| 01-F018 | 数组顺序改变 → 字节不同 | `SnapshotTests.test_F018_array_order_matters` | PASS | A03 | |
| 01-F019 | 组合/分解 Unicode → 不归一化 | `SnapshotTests.test_F019_unicode_not_normalized`、`test_F019_int_float_and_negative_zero_distinct` | PASS（ok ×2） | A03 | |
| 01-F020 | 非字符串键或非原生容器 → 拒绝 | `SnapshotTests.test_F020_non_string_keys`、`test_F020_non_native_values`、`test_F020_native_values_accepted`、`test_F020_numeric_and_unicode_checks`、`test_F020_cycles_and_shared_containers`、`test_F020_long_cycles_are_cycles_not_limits` | PASS（ok ×6） | A04 | |
| 01-F021 | 新标识非法字符/尾随换行 → 拒绝 | `IdentifierTests.test_F021_request_and_run_id_syntax`、`test_F021_task_logical_kind_sha_syntax` | PASS（ok ×2） | A08 | 旧 ID 正则接受末尾换行，登记为 D-23，已落为 legacy 负例（EV-C08 `test_d23_identifier_trailing_newline`，第 17 行，ok）；新严格入口只判断 JSON 层，同样接受合同 v1 中的这种标识（兼容矩阵 4.3 节） |
| 01-F022 | 重连旧 run → 标识不变 | `RunContextTests.test_F022_reconnect_and_replay_keep_identity` | PASS | A08 | |
| 01-F023 | 真正重试 → 新 run、同 request | `RunContextTests.test_F023_executor_retry_new_run_same_request` | PASS | A08 | request 预算根的实际记账归 07 |
| 01-F024 | 绝对、盘符、UNC、反斜杠 → 词法拒绝 | `BusinessPathTests.test_F024_absolute_drive_unc_backslash` | PASS | A04、A10 | |
| 01-F025 | 父目录、空段、点段、NUL → 词法拒绝 | `BusinessPathTests.test_F025_dot_segments_empty_nul`、`test_F025_length_and_segment_limits`、`test_F025_c1_control_characters`、`test_F025_line_separators_and_bidi_controls`、`test_F025_nonportable_characters_and_segment_endings` | PASS（ok ×5） | A04、A10 | |
| 01-F026 | Windows 保留设备名/ADS → 词法拒绝 | `BusinessPathTests.test_F026_reserved_device_names_and_ads` | PASS | A10 | |
| 01-F027 | 根内 symlink 指向根外 → 物理拒绝 | `PhysicalPathTests.test_F027_symlink_escape` | PASS（本机实际创建 symlink；建不了时会 skip，本次没有） | A10 | 静态审阅，不是安全访问保证（R-P9）；POSIX symlink：NOT_RUN |
| 01-F028 | junction/reparse point 越界 → Windows 实际拒绝 | `PhysicalPathTests.test_F028_junction_escape` | PASS（`_winapi.CreateJunction` 实际创建） | A10、A15 | Linux、macOS：applicability=not_applicable，applicability_reason：junction 是 Windows 的重解析点概念，测试以 skipUnless 限定（01-L09）。这**不代替**必需能力的结论：Linux、macOS 上对应的物理边界能力（F027 的 symlink 越界）仍是 NOT_RUN |
| 01-F029 | 检查后父目录/目标被替换 → 仍受控或阻断 | `PhysicalPathTests.test_F029_replacement_after_check` | **NOT_RUN**（skipped，第 223/224 行） | A10 | 跳过原因：“01-D06：01 只提供词法校验与静态解析，不实现抗 TOCTOU 的受控访问；F029 由后续访问实现模块验收”。**归后续访问实现模块（01-D06）** |
| 01-F030 | 目标替换为 FIFO/设备/共享硬链接 → 不因根内路径而放行 | `PhysicalPathTests.test_F030_fifo_device_hardlink` | **NOT_RUN**（skipped，第 225/226 行） | A10 | 跳过原因：“01-D06：01 不实现文件类型与硬链接受控读写”。**归后续访问实现模块（01-D06）**。`SealingTests.test_A13_hard_link_alias_is_known_not_detected`（ok）固定的是“硬链接不检测”这一当前限制，不是 F030 的通过 |
| 01-F031 | 文件资源缺 path → E_RESOURCE_PATH_REQUIRED | `ResourceRefTests.test_F031_file_resource_requires_path` | PASS | A04 | |
| 01-F032 | 未登记 kind/未知字段 → 拒绝 | `ResourceRefTests.test_F032_unknown_kind_and_unknown_field` | PASS | A04、A09 | 登记新 kind 时须声明 R-P10 的三项（`test_A04_r_p10_registration_requires_three_declarations`，ok） |
| 01-F033 | 只改 LF 为 CRLF → 哈希不匹配 | `ResourceRefTests.test_F033_crlf_changes_hash` | PASS | A02、A04 | fixture 侧 `negative-protocol-synthetic-sample-lf-to-crlf` 由 EV-C08 `NegativeTests.test_each_negative_yields_exactly_manifest_code`（第 75 行）与 `FileIntegrityTests`（第 33–37 行）方法级核对，都是 ok |
| 01-F034 | SHA 大写/截断/错误值 → 分别拒绝 | `ResourceRefTests.test_F034_sha_format_vs_content_mismatch` | PASS | A04 | |
| 01-F035 | Git commit/tree 类型错置 → E_GIT_OBJECT_TYPE | `GitOidTests.test_F035_interpret_constructed_output`、`test_F035_real_git_temp_repository` | PASS（ok ×2，含真实临时 git 仓库） | A01、A04 | |
| 01-F036 | 资源引用自环/多节点环 → E_RESOURCE_CYCLE | `ResourceRefTests.test_F036_resource_dag_order`、`test_F036_resource_cycles`、`test_F036_referenced_only_nodes_and_determinism` | PASS（ok ×3） | A13 | |
| 01-F037 | 相同 seq 相同内容重放 → 幂等，不新增记账 | `EventTests.test_F037_duplicate_replay_is_idempotent`、`EventTests.test_A11_F037_append_event_replay_of_older_seq_keeps_state`、`UsageTests.test_F037_usage_replay_counted_once` | PASS（ok ×3） | A06、A11 | “不新增记账”在观测视图层断言；记账归 07。旧调度器会重复累计（D-17，P4-E17，EV-C09） |
| 01-F038 | 相同 seq 不同内容 → E_EVENT_REPLAY_CONFLICT | `EventTests.test_F038_same_seq_different_content`、`test_F038_dict_equal_but_bytes_different_is_conflict` | PASS（ok ×2） | A11 | |
| 01-F039 | seq 缺口/尾部截断 → 不完整 | `EventTests.test_F039_tail_truncation_is_incomplete`、`test_F039_seq_gap` | PASS（ok ×2） | A11 | |
| 01-F040 | 退出 0 但缺结束证据 → 退出与协议分开 | `RunDimensionTests.test_F040_exit_zero_without_end_evidence` | PASS | A05、A11 | |
| 01-F041 | 结束成功与退出失败冲突 → 冲突，保留双方证据 | `RunDimensionTests.test_F041_success_claim_with_nonzero_exit` | PASS | A05、A11 | |
| 01-F042 | 脱敏改变长度 → 新偏移对应新字节 | `EventTests.test_F042_redaction_changes_offsets` | PASS | A12 | 脱敏前后偏移映射未实现，归 04 |
| 01-F043 | 合成样本冒充 captured → 拒绝 | `ProvenanceTests.test_F043_synthetic_cannot_claim_captured` | PASS | A12 | |
| 01-F044 | token/费用缺失 → null + 原因，不补零 | `UsageTests.test_F044_missing_values_need_reasons`、`test_F044_partial_unknown_propagates`、`test_F044_all_unknown_sample_view` | PASS（ok ×3） | A06 | 旧调度器缺失 token 记 0（D-18，P4-E21，EV-C09） |
| 01-F045 | 累计、delta、final 混合 → 按范围处理或阻断 | `UsageTests.test_F045_cumulative_takes_last`、`test_F045_deltas_add`、`test_F045_mixed_kinds_in_same_scope`、`test_F045_scopes_are_separate`、`test_F045_conflicting_finals`、`test_F045_final_revises_previous`、`test_F045_revision_keeps_logical_position`、`test_F045_cumulative_and_final_consistency` | PASS（ok ×8） | A06 | |
| 01-F046 | 缓存/reasoning 已含于总数 → 不重复相加 | `UsageTests.test_F046_cache_and_reasoning_not_added` | PASS | A06 | |
| 01-F047 | 同币种修订/不同币种合并 → 保留修订，不直接相加 | `UsageTests.test_F047_currencies_not_mixed`、`test_F047_same_currency_revision`、`test_F047_revision_currency_mismatch`、`test_F047_revision_chain_currency_through_null` | PASS（ok ×4） | A06 | |
| 01-F048 | 临时文件已写、索引提交失败 → 不暴露假引用，可补偿 | `SealingTests.test_F048_index_failure_leaves_unreferenced_candidate`、`test_F048_index_failure_any_exception` | PASS（ok ×2） | A13 | 函数层；真实崩溃持久性 NOT_RUN（3.13） |
| 01-F049 | 导入公共模块 → 无模型、网络、凭据或文件写入副作用 | `ImportSideEffectTests.test_F049_import_has_no_side_effects` | PASS | A14 | |
| 01-F050 | 输入漂移/旧基准未运行 → 不得生成一致基线 PASS | `tests/test_baseline_tool.py`（EV-C04）：`CaptureTests.test_modifying_tracked_file_is_drift`、`test_new_untracked_file_is_drift`、`test_ignored_name_change_is_drift`、`test_exclude_is_exact_prefix_and_does_not_hide_porcelain_changes`、`test_new_file_under_excluded_prefix_causes_no_unexplained_manifest_drift`、`test_missing_executable_is_null_returncode_and_incomplete`、`test_run_output_write_failure_is_incomplete_and_command_not_run`；`RunReasonTests.test_command_that_did_not_run_is_always_incomplete`；对照 `CaptureTests.test_unchanged_command_is_consistent` | PASS（ok ×9） | A01、A16 | 取证工具只记 `baseline_consistent=false` 与 `execution_status=incomplete`，本身不判 PASS（`run.interpretation=not_evaluated`）；“不生成 PASS”由报告规则保证（baseline-report 第 8 节，source_inspected）。19 次真实取证（EV-00、EV-01–EV-08、EV-C01–EV-C10）都没有发生漂移，漂移分支只在临时仓库中实测 |

## 5. 平台矩阵（文档 7.5）的实际结果

| 能力 | Windows | Linux | macOS | 证据与说明 |
|---|---|---|---|---|
| 严格 JSON/字节序列化 | 实测 PASS | NOT_RUN | NOT_RUN | EV-C02：F001–F013、F015、F018–F020 与 A03 黄金向量方法；EV-C08 黄金向量与样本字节。单平台通过不推导三平台 |
| 词法路径拒绝 | 实测 PASS | NOT_RUN（统一用例可以运行，但没有运行） | NOT_RUN | EV-C02：F024–F026、`BusinessPathTests` 以 A10 命名的 6 个。只证明词法逻辑 |
| symlink/junction 物理边界 | 实测 PASS（范围：静态审阅 + 纵深防御）：实际 symlink（F027）、实际 junction（F028）、FSCTL 写入的重解析点写法、大小写敏感目录、手工短名；F029、F030 NOT_RUN | NOT_RUN（实际 symlink 没有运行；POSIX 物理 `..` 分支只有 Windows 上的白盒注入） | NOT_RUN | EV-C02。不是安全访问保证（R-P9）；已知不检测清单见 protocols-api 第 7 节 |
| 原子发布与崩溃恢复 | 发布与索引补偿实测 PASS（EV-C02 `SealingTests`、F048）；**崩溃恢复 NOT_RUN**（没有断电或崩溃注入；Windows 不 fsync 父目录） | NOT_RUN | NOT_RUN | 不是只测 `replace()` 返回成功：发布用 `os.link` 不覆盖，读回核验摘要，索引失败不返回引用 |
| 原有调度自测 `tests/test_dispatch.py` | 实测：256 checks, 0 failed；三次取证 stdout 逐字节相同（EV-00、EV-01、EV-C01，EV-C01 按 R-01 禁用了仓库中的 pyc）；`test_wrapper_interpreters_and_literal_arguments` NOT_RUN（Windows 上直接 return） | NOT_RUN（“PDEATHSIG stops pi”分支没有产生） | NOT_RUN | 旧缺口按原样记录，没有为适配平台修改测试 |
| P4 旧实现特征化回归（4 个文件，159 个方法） | 156 个实测 PASS；P4-L03、L04、C52 为 POSIX 分支，NOT_RUN | NOT_RUN | NOT_RUN | EV-C05、EV-C06、EV-C07、EV-C09；49 个白盒方法只证明函数层现状 |
| fixture 字节完整性与差分 | **方法级**实测 PASS（EV-C08 75 个方法；EV-C03 38 行 SAME；EV-C10 10 行 SAME）；本机 `core.autocrlf=true`，`-text` 规则生效（`FileIntegrityTests.test_git_attributes_disable_line_ending_conversion`、`test_git_clean_filter_keeps_bytes`，ok） | NOT_RUN | NOT_RUN | stub 重跑核对只在 Windows 上执行；`platform_scope` 为 windows 的 40 条只在本机生成与核对；文档 6.6 七类的新旧差分 NOT_RUN（新路径不存在） |
| fixture 凭据形态扫描（文档 8.3） | 实测 PASS（EV-C08 `CredentialScanTests` 4 个，189 个文件无命中） | NOT_RUN | NOT_RUN | 只发现 15 类形态（兼容矩阵 9.1 节） |
| 测试工具清理前的归属核对（文档 8.4） | 实测 PASS（EV-C08 `HarnessCleanupOwnershipTests` 11 个、`CleanupOwnershipTests` 10 个，含联接与符号链接用例） | NOT_RUN | NOT_RUN | 不防同账户的 TOCTOU；只覆盖测试工具，不是产品能力 |
| 取证工具自测 | 实测 PASS（40 个方法，EV-C04） | NOT_RUN | NOT_RUN | Job Object 分支在 Windows；POSIX 的 killpg 分支没有运行 |
| 附录 B 参考自测（reference_code 栏） | **FAIL**：19 ok、1 FAIL（`test_static_resolution`，8.3 短名导致的测试写法问题）、1 skipped（EV-R） | NOT_RUN（附录 E.1 的 Linux 结果是文档自述，不计） | NOT_RUN | 与项目验证分栏（A16），不因项目测试通过而改判 |
| 公共 Schema 元校验（Draft 2020-12） | **BLOCKED**（本机没有 jsonschema，且未授权安装） | NOT_RUN | NOT_RUN | 第 9 节 (d) |

## 6. 文档 7.3 G0–G6 表的最终版本

- 引用 [legacy-inventory.md](legacy-inventory.md) 第 2 节（G0–G6 取证表，含“P4 更新”列）与第 12 节（P4 特征化回归）。本表只汇总，逐条 problem 原文与源码行见清单 5.6 节。
- 名称只来自 `.agents/skills/review-pi/gates.md:7-13`（source_reported），源码中只有编号；语义来自 `evaluate_gates`（`scripts/pi_dispatch.py:4152-4256`，source_inspected）。
- 旧自测 check 的结果见 EV-C01（与 EV-00、EV-01 的 stdout 逐字节相同）；P4 方法的结果见 EV-C05、EV-C06、EV-C07、EV-C09（方法集合与结果和最终取证相同）。

| 旧门禁 | 真实名称 / 语义要点 | 原测试标识（旧自测 check） | P4 特征化方法（失败路径） | Windows 结果 | Linux / macOS | 本次状态与剩余缺口 |
|---|---|---|---|---|---|---|
| G0 | **输入一致**：plan.md、contract.json 的 SHA-256 与 meta 记录一致；base_sha 可用（:4160-4163） | 只有正向：`test_happy`“PASS accepted” | P4-G01 `G0InputConsistency.test_lb_gates_024_g0_hash_base_and_contract_failures`（EV-C05） | measured / PASS | NOT_RUN | 失败路径已覆盖。锁定的现状含“可疑”项：meta.json 不校验；contract.json 被改后 G3/G4 仍按被改的合同判定；contract.json 缺失或损坏时回溯退出 1（legacy-inventory 11.2 第 5 条待设计决定） |
| G1 | **执行完整**：run.json 存在、未超时、未中断、Pi 退出码为 0、events-summary 无 problem（:4165-4182） | `test_events_and_thinking`“PASS refused on G1”等；`test_feedback_v12`“PASS is refused when the run ended on a textual tool call” | P4-G02–G05、G07、G24（EV-C05）；P4-L01、L05、L22（EV-C06）；P4-E20（EV-C09）；P4-L03 NOT_RUN | measured / PASS | NOT_RUN | POSIX 的 SIGINT 取消（P4-L03）NOT_RUN |
| G2 | **范围合规**：scope.json 存在且 violations 为空（:4188-4199） | `test_scope`“PASS refused on scope violation (G2)” | P4-G08、G09（EV-C05） | measured / PASS | NOT_RUN | “执行器访问了工作副本外路径”备注未经 verdict 断言；diff_error 时没有备注 |
| G3 | **行为正确**：有有效检查记录；DoD 引用的 scope 证据与检查 id 通过（:4183-4187、4200-4205、4228-4236） | 只有备注：`test_feedback_v12`“verdict prints the G3 note about undeclared ambiguity” | P4-G08、G10–G12、G14、G18（EV-C05） | measured / PASS | NOT_RUN | 合同矛盾备注未经 verdict 断言 |
| G4 | **回归检查**：最近一次检查记录有效、针对当前候选、覆盖必要检查、未改候选、无候选外新文件、必要检查通过（:4200-4227） | `test_candidate_drift_and_artifacts`“PASS refused when checks created files (G4)” | P4-G10、G11、G13、G14、G18（EV-C05） | measured / PASS | NOT_RUN | 干净副本模式的备注未经 verdict 断言 |
| G5 | **质量复审**：没有机械断言，恒为通过，只写固定备注（:4152-4154） | 无 | P4-G09、G23（恒通过与固定备注，EV-C05） | measured / PASS（恒通过） | NOT_RUN | 没有可触发的失败路径（旧实现如此，不是测试缺口）；R-02 下把 P4-G09、G23 当作这一门的失败路径映射，这一读法待规划端确认（3.7，第 7 节第 22 项） |
| G6 | **可集成**：重新快照无漂移（只差行尾给专门消息）；candidate_patch_ok（补丁存在、sha256 不变、往返通过）（:4237-4255） | 正向：`test_v22_netperf_feedback`“verdict PASS survives a later autocrlf change …”；`test_happy`“candidate roundtrip verified” | P4-G13、G15–G17（EV-C05）；补丁相关另有 P4-G18、G19、C63 | measured / PASS | NOT_RUN | 真实的往返失败没有构造（P4 改写记录字段模拟）；重新快照写 Git 对象未断言 |

verdict 拒绝分支（PASS 带 `--waive`、AWE 缺豁免或缺 `--decided-by`、REVISE/BLOCKED/ESCALATE 缺 `--class`、非 REVIEWABLE 状态、重复记录）由 P4-G20–G23、C58、C59 覆盖，Windows measured / PASS（EV-C05、EV-C07；legacy-inventory 第 2 节末）。

## 7. 附录 D.3 交接检查

| # | D.3 问题 | 回答 | 依据 |
|---|---|---|---|
| 1 | 实际测的是哪个提交和输入版本 | HEAD `a4fa199b0e5bdc658215765ee7558b9fe6723940`（sha1）加脏工作区。当前依据是收尾取证（BL-CLOSURE）：porcelain 1019 项、输入清单 1073 项（`3a559ca5…`）、闭包 `81b4503e…`，10 次之间工作区不变；闭包为 partial。历史：实施前基线 porcelain 37 项、清单 92 项、闭包 `8ca10fb9…`（BL-PRE）；最终取证 porcelain 319 项、清单 373 项、闭包 `2d8f2f71…`（BL-FINAL）。01 的新文件都未提交，字节见 2.1。取证之后有 4 份文档改变（两份基线报告、兼容矩阵、legacy-inventory），本修订又改了本文与 README；`evidence/closure/` 与 `run-controls-closure/` 在取证之后才加入。除 `test_baseline_records_are_internal` 按目录读取 `evidence/` 外，测试都不读取这些文件（2.1） | 2.1、2.2；baseline-report 第 13 节 |
| 2 | 有哪些旧失败与未运行项 | **失败**：只有附录 B 参考自测 1 项 FAIL（`test_static_resolution`，测试写法问题，EV-R）；项目测试 0 个 FAIL/ERROR。**未运行**：`test_protocols` 的 F017、F029、F030（NOT_RUN）与 jsonschema 元校验（BLOCKED）；P4-L03、L04、C52（POSIX）；旧自测 `test_wrapper_interpreters_and_literal_arguments` 与 Linux 的 PDEATHSIG 分支；文档 6.6 七类的新旧差分（新路径不存在）；Linux、macOS 全部。（最终取证时的“fixtures 方法级证据”与“`--check` 两条命令没有归档”已由 EV-C08、EV-C03、EV-C10 补上。）**旧实现的已知缺陷（特征化锁定的现状，不是测试失败）**：未捕获异常以 Traceback 退出 1、G0 范围、TaskLock 不核对归属、token 缺失记 0 等，见 legacy-inventory 11.2（17 项待设计决定） | 第 4、5 节；legacy-inventory 第 11、12 节 |
| 3 | 谁拥有各字段 | 标识格式、严格 JSON、快照字节、ResourceRef、事件封装、结构化错误、用量观测与视图：01。资源类型的 `schema_ref`、允许的载荷表示与语义校验器：登记该类型的模块（R-P10；01 预登记的 5 类由 01 声明）。配置字段、语义投影与 `_...` 例外、环境锁：02（01-D05）。审核主体、`input_refs` 的消费与失效、保护路径与授权：03。真实事件类型与载荷 Schema、adapter_revision、原始流完整性与脱敏映射、派生视图修订与 view_id：04（01-D07、M-11）。插件锁资源类型：06。标识分配与持久唯一性、attempt 分配（R-P2）、预算、锁、重试、事件日志事务化、唯一记账：07（01-D08）。合同生成、校验与发布、plan_version 单调：09。项目状态、跨 run 的先后关系与集成观测：10。生产级安全文件访问：后续访问实现模块（01-D06）。逐字段见 protocols-api.md 第 16 节“归属”列 | protocols-api 第 8、11、16、17 节；decisions.md |
| 4 | 采用了哪个 Schema 家族 | `codekit-public`，公共记录 `schema_version=1`，Schema `$id` `urn:codekit:public-protocol:1`，按 `record_type` 分派（run-context、run-event、usage-observation）；序列化 profile `codekit-config-json-py-v1`。与合同 schema v1、工具版本 2.2.2 相互独立（01-D02）。本地 Schema `schemas/codekit-public-v1.schema.json` 与附录 E.2 摘要一致；元校验 BLOCKED | 3.9；兼容矩阵第 5 节 |
| 5 | 哪些平台做了真实验证 | 只有 Windows Server 2025 Standard 10.0.26100（AMD64）+ CPython 3.12.10 + git 2.55.0.windows.5 + Git Bash 5.3.15。Linux、macOS 没有任何实测 | 第 5 节；3.15 |
| 6 | 未知用量如何传播 | 新协议：未知计量写 null 并必须给出原因，不补零；部分未知与全部未知在视图中向上传播为未知；不同币种不相加；重放按 seq/标识去重只计一次；视图标 `is_accounting=false`（EV-C02，F044–F047、F037）。旧调度器：token 缺失记 0、费用未知为 null、重复 message_end 重复累计（EV-C09，P4-E17、E21、E30），迁移时不能把旧的 0 当作“已知为 0”（D-17–D-19，归 04、07） | 3.6 |
| 7 | 哪个模块唯一记账 | 07（01-D08）。01 只提供观测校验与观测视图，不做记账或扣减 | decisions.md 01-D08 |
| 8 | 哪些新增核心文件应进入保护范围 | 已落实：`.agent/dispatch.config.json` 的 `extra_protected_paths` 登记 `scripts/codekit/`、`schemas/`、`tests/fixtures/codekit01/`、`tests/codekit01_legacy.py`、`tests/legacy_harness.py`、`tests/test_legacy_*.py`、三组第一阶段测试与 `docs/code-kit-v2/01-baseline/`（第 9 节 (a)） | 文档 5.2 |
| 9 | 回退时如何保留证据 | 按兼容矩阵第 6.3、6.4 节（修订 11 补上 `.agent/baseline/01-closure/` 与 `evidence/closure/`）：不删除 `.agent/baseline/`（`01-T1/`、`01-P4/`、`01-final/`、`01-closure/` 原件，`.gitignore` 忽略，只读）、`evidence/`（归档，含 `closure/`、`final/`、`run-controls-final/`、`run-controls-closure/`、`inventory-items/`，各有 manifest）、fixture 与 expected；不改写历史合同；不重新生成旧哈希或 expected；旧入口字节未改，所以回退不需要恢复旧入口，停用新消费者即可；首次失败证据（EV-R 的 FAIL）保留 | 兼容矩阵第 6 节 |

**回答不了、列为未完成项的问题**（第三次修订逐项标注状态；已关闭的项保留原文要点并写明依据，不删除）：

1. **仍未关闭**：标识的持久唯一性与分配方、事件日志的事务化持久追加、真实崩溃后的恢复：01 只有接口与内存模型，归 07、04，尚无合同。
2. **仍未关闭**：生产级安全文件访问（F029、F030）与封存存储根的崩溃持久性由哪个模块负责：01-D06 只写“后续访问实现模块”，模块与合同**未指定**。
3. **仍未关闭**：Linux、macOS 上的全部结论。
4. **仍未关闭**：真实 Pi 流、真实历史派遣证据、captured fixture：仓库中没有这些输入（04 采集）。
5. **已关闭**：保护范围已按第 9 节 (a) 的选项二登记，第一阶段核心成果已提交；仍需独立终审与跨平台/元校验验证。
6. **已关闭**：`tests/test_codekit01_fixtures.py` 的方法级证据——收尾取证 EV-C08（`bl-01closure-test-codekit01-fixtures-v-20260926`，`python tests/test_codekit01_fixtures.py -v`，run/stderr.bin 13127 字节，sha256 `95faa68cea9315a4a73cc4bfc4223916e56b8eb1b9e5694fa1415fdf1c8b169a`）：75 个方法都有方法名且都是 ok（closure/INDEX.md 4.3 节）。
7. **已关闭**：A01（pyc）与 A07（逐子项）的口径——decisions.md“收尾轮裁决”R-01（严格口径：计摘要或受控禁用）与 R-02（每类、每门有已实测的失败路径断言，子分支登记为 unmet_within_scope），按裁决的重判见 3.1、3.7。裁决之后仍待规划端确认的三点另列为第 20–22 项。
8. **仍未关闭**：legacy-inventory 11.2 的 17 项“旧行为保留还是修正”：01 不裁决，各归 03、07、09。
9. **已关闭（归档要求）**：旧行为清单的结构化条目已归档到 `evidence/inventory-items/`（EV-INV：`manifest.json` 1326 字节，sha256 `cebbd8bfc9861f97ce21f81478b2574aef5fdd6a8acff3df1f5ca70d9ddba8c9`；本修订核对 6 个 `inventory-*.items.json` 的 sha256 与 manifest 一致）；legacy-inventory 11.6 第 6 条已更新。条目中的“实测”“探针”仍只是线索，不是运行证据，证据等级不变（legacy-inventory 11.6 第 1 条，另项）。本项与 M-07 只涉及是否归档；基线报告修订 7 的 10.3 节与 JSON 用同一用词。

**完整性审查（2026-09-26）新增的未完成项**：

10. **仍未关闭（部分）**：总设计的读取与交叉检查（decisions.md 01-L08）。“实施前读取总设计”记 **NOT_RUN**，无法事后补成“实施前”；交叉检查已事后补做（source_inspected）。三项后续都**不需要改 01 的代码**：
    - “用量”作为事件类型（总设计第 148 行）与 01 的独立记录 usage-observation 如何对应：归 04；
    - `scripts/codekit/` 下 01 的文件名（protocols、sealing、baseline）与总设计第 9 节拟议的文件名不同：由后续模块决定是否合并或改名（规划端）；
    - 总设计第 358 行要求新核心模块纳入保护路径：已按第 9 节 (a) 的选项二落实。
11. **已关闭**：文档 3.2 回归映射的两个字段——按 R-P12 回填：legacy-inventory.md 9.10.6（224 行逐行回填，manifest 与代码内联两种 input_fixture_ref，NOT_COVERED 由 181 行降为 67 行）、12.10（第 12 节 159 个方法各自的 `inline:` 引用与 `codekit01-characterization-v1`）。剩余的 67 行 NOT_COVERED 按原因分四类（清单 9.10.6），其中 (c) 类 23 行的登记方式另列为第 23 项。
12. **部分关闭（七类与 D-20–D-23 已关闭）**：文档 6.6 选样——超时、取消、恢复、候选漂移、候选/补丁判断、门禁结果、旧入口状态解释七类按 R-P12 改为“旧路径已锁定（内联 fixture + 特征化断言），差分 NOT_RUN（新路径不存在，归 07、10）”，不再记为缺样本（legacy-inventory.md 9.10.7；兼容矩阵第 8 节第 9 条）；D-20–D-23 已落为 6 个 legacy 合同负例（EV-C08 `CompatMatrixDCaseTests` 5 个 ok；EV-C03 中对应 6 行派生 SAME；M-04 已关闭）。**仍未关闭的部分**：缺字段类的两种样本，另列为第 24 项。
13. **已关闭**：ResourceKind 缺 4.2.1 要求的三项——R-P10 已落实：`ResourceKind`（`scripts/codekit/protocols.py:1362`）增加 `schema_ref`、`payload_representations`、`payload_validator`，登记时缺任一项报 `E_SCHEMA_FIELDS`；新增 `validate_resource_payload`（:1632）；EV-C02 7 个 R-P10 方法 ok（第 271–282、293–294 行），EV-C08 `R11Tests.test_whole_manifest_bytes_pass_fixture_manifest_payload_validator` ok（第 91–92 行）；protocols-api.md 第 8 节与第 18 节第 22 项已补登（M-10 已关闭）。
14. **已关闭**：fixture 条目缺少的规定字段——R-P11（与 R-P11 补充）已落实：条目新增 `integrity`、`platform_scope`、`capture`、`redaction.protocol_structure_preserved`、`origin.traceable`，manifest 188 条全部按登记规则填写（兼容矩阵第 8 节第 10 条）；EV-C02 R-P11 的 6 个方法与 `test_A12_appendix_c1_example_needs_completion`、EV-C08 `R11Tests` 6 个都是 ok；protocols-api.md 第 14 节已更新（M-03 已关闭）。captured 样本的这些字段由 04 采集时填写。
15. **已关闭（文档归属）**：文档 4.3.2 的两行（M-11）——protocols-api.md 第 11 节末尾的归属表与第 16、17 节写明：派生视图修订与 view_id 归 04（与 adapter_revision 一并设计），跨 run 的先后关系归 10（项目游标）。01 没有对应接口；实现仍在 04、10（第 8 节移交）。
16. **部分关闭**：文档 8.3 故障恢复决策表中没有落实的部分——
    - **已关闭**：fixture 目录的凭据形态扫描（`CredentialScanTests`，EV-C08 第 19–25 行，4 个 ok；189 个文件、15 类形态无非白名单命中，兼容矩阵 9.1 节、E19；“没有白名单放行”只有静态核对，测试不断言，见 3.12 与 M-16）；
    - **仍未关闭**：“冻结受影响视图”“受控清理未引用候选”没有实现，归 04、07；凭据发现后的处置（停止分发、限制访问、凭据处置、事故记录）没有流程，归规划端与用户；扫描只覆盖 15 类形态；采集真实样本时的脱敏与扫描归 04；“磁盘满”只有模拟，没有真实注入。
17. **已关闭**：文档 8.4 清理前的归属核对——`tests/legacy_harness.py` 的 `remove_tree`（:1124，区域由 `make_temp_area` :996 建立并写入所有权标记）与 `tests/codekit01_legacy.py` 的 `_rmtree`（:814，`ownership_problem` :776）删除前核对父目录、目录名前缀、真实路径与所有权标记，任一不满足即拒绝；回归测试 EV-C08 `HarnessCleanupOwnershipTests` 11 个（第 42–63 行）、`CleanupOwnershipTests` 10 个（第 1–13 行）都是 ok；已按 01-L05 与 R-01 重新取证（收尾取证，绑定 harness 字节 `c4e87137…`）。剩余：两处都不防同账户的 TOCTOU；harness 的 `remove_tree` 只适用于目录（第 10 节 M-13）；本项范围之外的 `tests/test_baseline_tool.py` `TempArea`（只核对父目录与前缀）与 `tests/test_protocols.py` 的 `TemporaryDirectory`（兼容矩阵 9.2 节，M-15）。
18. **已关闭**：protocols-api.md 的待修订内容——第 3.2 节 `E_BASELINE_*`（M-12）、第 8 节与第 18 节第 22 项（M-10）、第 11、16、17 节（M-11）、第 14.1、14.2 节（M-03）、第 7 节 R-P3 勘误（M-02）都已由收尾轮实施者更新（source_inspected，protocols-api.md 第 19 节“收尾轮”逐条处理）；改动后的字节（301574，`785c75f6…`）就是收尾取证的输入，读取它的措辞与示例检查在 EV-C02、EV-C08 中通过。

**对抗性核验（2026-09-26）新增的未完成项**：

19. **已关闭（归档要求）**：最终取证操作者记录的正式归档——`evidence/run-controls-final/`（EV-RCF）：`final2-captures.txt` 1495 字节，sha256 `c362495cc389d37204e1250f8ff613585f5722cb8b0e63c60bcf668b9d11d6dd`，与此前登记的原件摘要相同；`manifest.json` 846 字节，`bbd6c3a108257aedf1fbe8c95026f75e61866120b625426016d6d88c8ddd2e8a`；基线报告 10.3 节 L-FINAL-OPERATOR 已引用；该条整体为部分关闭（归档要求已关闭；证据等级仍是 source_reported，2.2），基线报告修订 7 已把 JSON 状态由 closed 更正为 partially_closed。

**收尾轮（2026-09-26）新增的未完成项**：

20. **R-01 受控禁用的证据等级**（3.1 前提 ①）：`PYTHONPYCACHEPREFIX` 的设置与“取证前为空”只有操作者记录；取证工具不记录这个变量，也没有取证后前缀目录的条目数。规划端决定是否接受操作者记录；不接受时 A01 为不满足，需要改 `scripts/codekit/baseline.py`（及其测试）记录该变量与前缀目录的前后状态，然后按 01-L05 与 R-01 重新取证。归属：规划端。
21. **R-01 是否覆盖仓库外输入**（3.1 前提 ②）：标准库及其字节码（含取证工具进程可能写入前缀目录的字节码）、git 与全局配置、系统工具。若覆盖，现有取证工具的任何一次取证都不满足，A01 为 FAIL。归属：规划端。
22. **G5 在 R-02 下的读法**（3.7）：a4fa199 的 G5 恒通过，P4-G09、G23 断言它在失败记录中也保持通过；是否把这算作该门的失败路径映射，R-02 原文没有说。若要求可触发的失败断言，A07 为 FAIL。归属：规划端。
23. **legacy-inventory 9.10.6 (c) 类 23 行的登记方式**：这些行只有旧自测 `tests/test_dispatch.py` 的 check（bl-01t1 measured），旧自测是模块级函数加 check，不符合 R-P12 的 `<类>.<方法>` 写法；是否另定写法（按函数名或 check 名）把它们登记为代码内联 fixture，R-P12 没有规定。其中 12 行在第 12 节中有明显相关但未标注的断言（清单 9.10.6“线索”）。归属：规划端。
24. **缺字段类的两种样本**（文档 6.6）：“JSON 合同缺必填字段”“消息带 usage 但缺 token 字段”没有 legacy fixture 与锁定投影（不属于 R-P12 的七类，兼容矩阵第 8 节第 9 条）。**需要新增 fixture 并锁定投影（改测试与 fixture）**，改后须重新取证。归属：01 兼容 fixtures 的后续返工。
25. **基线报告中照录的 13 项与本文不一致**：baseline-report.json 的 `transcript_from_acceptance_md` 照录的是本文修订前的字节（138322，`f01f659c…`）；本修订改了 A02 的判定与各项的证据编号。按报告自身的规则以本文为准；下次修订报告时重新照录。归属：规划端（基线报告的编写者）。

## 8. 给 02/03/04 正式合同的绑定清单（文档 9.2）

下表说明每份正式合同在 9.2 要求的 11 项上如何引用本次产物。**前提**：Pi 的 worktree 从合同的基线提交创建，执行器只能看到提交内容。第一阶段核心成果现位于提交 `182ef16`，本轮保护配置与索引修复提交后，下游 02/03/04 合同应以最终提交的 `base_sha` 为准。

| 9.2 项 | 本次产物中的出处 | 合同中的写法 |
|---|---|---|
| 实际基线与输入 Manifest | 本次基线：BL-CLOSURE（2.2）；取证工具 `scripts/codekit/baseline.py capture`；输入清单格式见各 `pre/input-manifest.json` | 写合同的 `base_sha`（01 提交后的 OID），并在派遣前按 01-L05 与 R-01 受控环境重新取证：`python scripts/codekit/baseline.py capture --out-root .agent/baseline/<阶段> --capture-id <id> --timeout 3600 -- python tests/<文件>.py`；运行时设 `PYTHONDONTWRITEBYTECODE=1`，`PYTHONPYCACHEPREFIX` 指向取证前为空的目录，并在取证记录中写明（第 7 节第 20 项决定之后可能改由取证工具记录）。引用新取证的闭包摘要，不沿用 a4fa199 的取证结论 |
| 精确文件范围 | 2.1 的文件表；protocols-api 第 17 节列出各模块应调用的函数 | 写出确切文件，不用目录通配代替。02、03、04 一般只新增自己的模块文件并调用 01 的公共函数；需要修改 `scripts/codekit/protocols.py` 或 `schemas/` 时，按文档 5.2 由规划端直接处理，不委派（若第 9 节 (a) 选了选项二，这类路径写进合同允许集合会被 validate 拒绝） |
| 保护文件处理 | 调度器内置保护：`.agent/**`、`.agents/**`、`.claude/**`、`**/AGENTS.md`、`scripts/pi_dispatch.py`、`scripts/dispatch-pi.sh` 等（`scripts/pi_dispatch.py:88-92`）；01 新增文件的保护待定 | 在 Forbidden / `forbidden_paths` 中列出第 9 节 (a) 的 7 个路径（不论用户选哪种方式，合同都显式写出）；合同验收时核对受保护文件相对基线 diff 为 0 行（同 2.1） |
| 验证命令 | EV-C01–EV-C10 的 10 条命令；01-L04（按文件运行，不用 discover） | 必需检查：`python tests/test_dispatch.py`（旧自测）、`python tests/test_protocols.py`、`python tests/test_codekit01_fixtures.py -v`、`python tests/test_baseline_tool.py`；改动涉及旧调度器行为比较时加 4 个 `tests/test_legacy_*.py` 与 `python tests/codekit01_legacy.py --check`、`--check-stub-regen`。全部按 R-01 设 `PYTHONPYCACHEPREFIX`。判读同时看汇总行与退出码（旧自测拼错名字会输出 `0 checks` 而退出 0） |
| 允许的平台 / profile | 第 5 节：只有 Windows 实测 | 合同写明平台（当前只能是 windows）；Linux、macOS 的结论需要各自取证，不从 Windows 推导。执行模型与思考级别按 AGENTS.md 与 `.agent/environment.md` 的精确 ID |
| 模型 / 网络是否禁用 | 01 没有调用模型；全部测试用 `tests/stub_pi.py` 与离线夹具；网络没有隔离，只有静态核实（EV-RC） | 验证命令本身不需要模型与网络；派遣 Pi 本身需要执行模型的网络访问并产生费用，需用户在对话中明确要求。不得为补测安装依赖（jsonschema 见第 9 节 (d)） |
| 预算根 | A08：request 预算根不因重试改变（F023）；实际记账归 07（01-D08）；旧调度器预算规则见 legacy-inventory 6.3 与 P4-L06–L16 | 02、03、04 合同按旧调度器的 Budget 节（`max_attempts_total`、`max_wall_seconds_per_attempt`、`max_wall_seconds_total`）填写；不在 02/03/04 中实现记账 |
| 日志与证据保留 | `.agent/runs/` 只读、不提交（AGENTS.md）；01 的取证原件在 `.agent/baseline/`（忽略），脱敏归档在 `docs/code-kit-v2/01-baseline/evidence/`（redact-v2，archive-manifest 逐文件摘要）；操作者记录另建归档目录并附 manifest（`run-controls-final/`、`run-controls-closure/`）；`-text` 规则（01-L06） | 新模块的证据目录照此分“原件（忽略）/ 脱敏归档（入库）”；操作者记录当场归档；登记完整字节摘要的文件先加 `-text` 再暂存 |
| 失败升级路径 | 文档 6.7；decisions.md 各项的归属 | 授权或保护范围冲突 → 规划端 / 用户；真实协议不明 → 04；费用口径或重复账单 → 07；跨模块 Schema 分歧 → 先做显式协议决策（改 01 的公共接口时同步更新 protocols-api.md 与使用方的验收项） |
| 回退条件 | 兼容矩阵第 6 节（停用方式、回退七步、禁止事项） | 写明：旧入口字节改变、`test_legacy_implementation_bytes_are_source_revision` 失败或 `test_legacy_*_projection_unchanged` 出现差异时停止并回退；回退不删除证据、不重算 expected |
| 交接验收项 | 本文第 0、3 节的范围外 / 移交项 | **02**：F017（机器路径 → 环境锁，01-D05）、配置语义投影与 `_...` 例外；**03**：`input_refs` 用 `validate_resource_ref` + `verify_resource_bytes` / `validate_resource_payload` / `read_sealed` 核验、`check_resource_dag`、保护路径与授权（A10 授权层）、D-01 等历史歧义输入的处理（01-D09）；**04**：真实事件类型与载荷 Schema（01-D07）、adapter_revision 锁定、原始流按 raw-segment 封存、D-15–D-19 的映射、captured fixture（按 R-P11 填写 `capture` 与 `traceable`）、脱敏偏移映射、事件日志与受信 RunContext 的一致性（01 的 M-01 只核对日志内部的 request/role 一致）、POSIX 取消的旧观测（A07 缺口，迁移比较时记 NOT_COVERED）。<br>**完整性审查与收尾轮补充的移交**：<br>- **02、03、06、09**（登记资源类型的模块）：按 R-P10 登记时必须声明 `schema_ref`、`payload_representations`、`payload_validator`（缺任一项报 `E_SCHEMA_FIELDS`），并用 `validate_resource_payload` 核验载荷；`schema_ref` 只是标识，01 不加载 Schema，需要按 Schema 校验的模块在自己的校验器中实现并在合同中写明；不能把 `validate_resource_ref` 通过当作内容已校验；<br>- **04**：4.3.2 的“同一原始证据换新解析器重建视图 → 新建派生视图修订（独立 view_id 或版本记录），不覆盖旧已承诺事件”，与 adapter_revision 的锁定一并设计（M-11）；8.3 的“事件序号冲突 → 冻结受影响视图、对照持久日志与来源”（兼容矩阵第 9.1 节）；“用量”事件与 usage-observation 的关系（decisions.md 01-L08）；<br>- **07、04**：8.3 的“封存成功、索引失败 → 受控清理未引用候选”（01 只保留候选，不清理）；<br>- **07、10**：文档 6.6 七类（超时、取消、恢复、候选漂移、补丁、门禁、旧入口状态解释）的新兼容路径出现后，用同一代码内联输入做新旧差分（R-P12，legacy-inventory.md 9.10.7）；<br>- **10**：4.3.2 的“跨 run 的先后关系由项目游标和显式依赖表达，不按时间戳强造全序”（M-11） |

## 9. 用户决策与剩余事项

### (a) 保护范围（文档 5.2）

文档 5.2：新协议、Schema 注册表、保护路径判断、资源核验与兼容路由一旦成为可信核心，也应纳入保护范围。本次按**选项二**落实：新建并提交 `.agent/dispatch.config.json`，用 `extra_protected_paths` 机械保护 01 的核心代码、Schema、fixtures、legacy harness/tests、三组第一阶段测试与 `docs/code-kit-v2/01-baseline/`；`AGENTS.md` 作为共享模板保持不变。以下保留两种实现方式的说明，选项二是本次采用的方案。

**选项一（本次未采用）：在 AGENTS.md“Pi 执行器”一节加一行本仓库专属禁区**

- 位置：`AGENTS.md` 第 113 行是占位符“【按需补充本仓库额外的禁区：……执行器只读本节，写在别处它看不到】”。在它**下面**新增一行（第 114 行），占位符保留。
- 确切文本：

```markdown
- 本仓库（Code-Kit）专属禁区，不修改：`scripts/codekit/`、`schemas/`、`tests/fixtures/codekit01/`、`tests/codekit01_legacy.py`、`tests/legacy_harness.py`、`tests/test_legacy_*.py`、`docs/code-kit-v2/01-baseline/`（Code-Kit v2 模块 01 的公共协议、Schema、兼容 fixtures、旧行为特征化回归与基线证据；按文档 5.2 由规划端在明确授权下直接修改）。
```

- 效果与代价：
  - 执行器会读到这条规则，但调度器**不机械拦截**：合同若把这些路径写进允许集合，validate 不会拒绝，改动也不会记为范围违规，只能靠复审发现（没有写进允许集合的改动，照常按越界处理）。
  - 这份 AGENTS.md 同时是分发给其他仓库的模板（PI-Kit）。这一行写的是本仓库才有的路径，把 AGENTS.md 复制到其他仓库时必须删掉它，否则会在别的仓库里留下无意义的禁区。
  - AGENTS.md 是受保护文件：修改后必须**提交**才对执行器生效（worktree 从基线提交创建）；它的 sha256 `7571e9a9…` 会改变，01 的证据中“受保护文件相对 HEAD 无改动”的核对需要按新基线重做（兼容矩阵 6.2 已预告）。

**选项二（本次采用）：在 `.agent/dispatch.config.json` 的 `extra_protected_paths` 中登记**

- 该文件已按本次授权新建；AGENTS.md 对新建/修改的授权要求已满足。`.agent/README.md` 说它应当提交。
- 确切文本（新建文件的完整内容；其余键不写时取调度器缺省值，与没有这个文件时的行为相同）：

```json
{
  "extra_protected_paths": [
    "scripts/codekit/**",
    "schemas/**",
    "tests/fixtures/codekit01/**",
    "tests/codekit01_legacy.py",
    "tests/legacy_harness.py",
    "tests/test_legacy_*.py",
    "tests/test_protocols.py",
    "tests/test_codekit01_fixtures.py",
    "tests/test_baseline_tool.py",
    "docs/code-kit-v2/01-baseline/**"
  ]
}
```

- 效果与代价（依据 `scripts/pi_dispatch.py:990-995`、`1063-1113`、`1500-1518`、`2436-2460`，source_inspected；该文件相对 HEAD 没有改动，行号仍然有效）：
  - **机械拦截**：合同的允许集合中写到这些路径时，validate/prepare 报“包含受保护路径”并拒绝；以更宽的通配符允许、而实际改动落在这些路径时，范围判定记为 `protected_path` 违规，G2 失败。匹配不区分大小写。
  - 模式都通过 `pattern_error` 的检查（正斜杠、相对路径、无空段、不是 `*`/`**`）；`**` 匹配任意层级，`*` 只匹配单层。
  - 调度器在主工作区读取这个文件，不需要提交就对 validate/run 生效；执行器本身看不到这条规则（它只读 AGENTS.md），被拦截时才知道。
  - 以后若确要让 Pi 修改这些文件，需要先改这个配置（再次征得用户同意）。
- 本次一并保护三组第一阶段测试：`tests/test_protocols.py`、`tests/test_codekit01_fixtures.py`、`tests/test_baseline_tool.py`。它们锁定 01 协议、兼容 fixtures 与取证工具的行为，不能由委派任务改写。

### (b) 是否提交，以及提交范围

- 当前工作区里**属于 01** 的改动（本修订按 `git status --porcelain` 与文件计数核对）：
  - 已跟踪文件的改动：`.gitattributes`（新增 3 条 `-text` 规则与注释）、`.gitignore`（新增 `.agent/baseline/` 与注释）；
  - 未跟踪文件：`scripts/codekit/`（4 个文件）、`schemas/codekit-public-v1.schema.json`、`tests/test_protocols.py`、`tests/test_codekit01_fixtures.py`、`tests/test_baseline_tool.py`、`tests/test_legacy_gates.py`、`tests/test_legacy_lifecycle.py`、`tests/test_legacy_cli.py`、`tests/test_legacy_events.py`、`tests/legacy_harness.py`、`tests/codekit01_legacy.py`、`tests/fixtures/codekit01/`（189 个文件：manifest 与 188 个登记文件）、`docs/code-kit-v2/01-baseline/`（1626 个文件：8 份文档，另 `evidence/` 下 1618 个）。
  - `evidence/` 下各目录**都要纳入**，包括收尾轮新增的四个：`closure/`（841 个：10 个取证目录各 84 个文件与 `INDEX.md`）、`run-controls-final/`（2 个）、`run-controls-closure/`（2 个）、`inventory-items/`（7 个）；以及原有的 `bl-01t1-legacy-20260925/`（84 个）、`final/`（673 个）、`reference-appendix-b-windows/`（4 个）、`run-controls/`（5 个）。本文、基线报告与 INDEX.md 中的摘要都指向这些文件，缺任何一个，引用就追不到。
  - `.agent/baseline/`（取证原件，含机器路径）被 `.gitignore` 忽略，**不提交**。
- **不属于 01**、提交时不能混入的改动：根目录 `README.md` 的修改（用户原有的改动）；`docs/` 下 6 份中文名文档的删除，以及对应的 6 个乱码名新文件（文件名编码问题造成的重命名）；`docs/code-kit-v2-design.md`，以及 `docs/code-kit-v2/` 下 01–13 设计文档、两份 JSON 与 `README.md`。
- 因此**不能用 `git add -A`**，也不能用 `git add .`、`git add docs/` 或 `git add docs/code-kit-v2/`（后者会带上设计文档）。应逐路径暂存（例如 `git add -- .gitattributes .gitignore scripts/codekit schemas/codekit-public-v1.schema.json tests/<逐个文件> tests/fixtures/codekit01 docs/code-kit-v2/01-baseline`），再用 `git diff --cached --name-status` 核对暂存清单只含上面列出的路径。
- 需要用户一并考虑的依赖：
  - 01 的测试会读取设计文档（按前缀 `01-baseline-and-protocols-` 查找，当前已恢复为正确文件名的设计文件）。不提交它时，干净检出中有 5 个方法会 skip：`test_protocols.py` 的 `test_A09_doc_samples_are_verbatim`、`test_A12_appendix_c1_example_needs_completion`，`test_codekit01_fixtures.py` 的 `test_doc_samples_equal_design_doc_blocks`、`test_c1_completed_entry_matches_doc`、`test_golden_vectors_match_design_doc_table`。`protocols-api.md` 属于 01（在 `01-baseline/` 中）：`test_protocols.py` 核对它的节结构（第 1–19 节）与第 7、15、16、18 节的措辞，`test_codekit01_fixtures.py` 核对第 14.1 节的示例，缺失会使这些测试报错。
  - `-text` 规则必须先于或随同这些文件进入索引，否则本机 `core.autocrlf=true` 会改变提交的字节，登记的摘要失配（baseline-report 第 10 节）。暂存后可用 `git ls-files -s` 的 blob 与 `git hash-object --no-filters` 对照核对。
  - 提交后 HEAD 改变。本次证据只对 2.1 记录的字节成立；提交内容与这些字节相同时，结论仍可引用，但要让 PASS 绑定到提交，需要在新 HEAD 上按 01-L05 与 R-01 重新取证。
  - 提交与推送需要用户授权；本任务没有提交。

### (c) Linux / macOS 取证状态（本次保留 NOT_RUN）

- 现在两者全部 NOT_RUN，A15 因此不能记 PASS；A07 的 POSIX 取消（P4-L03、L04）、P4-C52、旧自测 `test_wrapper_interpreters_and_literal_arguments` 与 Linux 的 PDEATHSIG 分支只能在 POSIX 上产生结果。
- 需要的条件：Python 3.10 以上、git、bash；同样的受控环境（PATH 中没有真实 pi/claude/codex、空的 `PI_CODING_AGENT_DIR`、按 R-01 设 `PYTHONPYCACHEPREFIX`）；不需要模型与网络。取证工具在 POSIX 上走 killpg 分支，这一分支本身也没有实测过。
- 预期差异：`StubTests` 的 stub 重跑核对在非 Windows 上跳过（NOT_RUN）；F028 不适用；旧预期中的报错原文只在 Python 3.12.10 上锁定，解释器版本不同可能导致差分失败，需要单独判断而不是重生成 expected；manifest 中 `platform_scope` 为 windows 的 40 条在其他平台上不宣称适用。

### (d) Schema 元校验状态（本次保留 BLOCKED）

- 现状：`SchemaFileTests.test_A09_jsonschema_metaschema_optional` 跳过，记 BLOCKED（01-L07）。附录 E.1 记载作者在沙箱中用 jsonschema 4.26.0 通过了 Draft 2020-12 元校验，那是文档自述，不对应本仓库。
- 安装需要联网并引入依赖（`protocols.py` 本身不依赖它，只影响这一个测试；R-P10 的 `schema_ref` 也只登记标识，不加载 Schema），需要用户授权。替代做法：在另一台已安装 jsonschema 的机器上只运行这一项检查并归档输出。

### (e) `docs/code-kit-v2/README.md` 的失效索引链接（01 已修复）

- 事实（本修订重新核对）：索引中 01 的链接已指向 `01-baseline-and-protocols-审阅增强版.md`（第 11、91 行），该文件已恢复为正确的中文文件名。同样失效的还有 02（`02-config-and-profiles.md`）与 03（`03-approvals-and-locks.md`）；04 同时有普通名与审阅增强版两份。索引中也没有指向 `01-baseline/` 的链接。
- 本次处理：将乱码文件名恢复为正确的 `审阅增强版`，并把顶层索引的 01 链接指向它；02、03 的普通名链接仍留给各自阶段处理。
  - 文件实际路径现为 `docs/code-kit-v2/01-baseline-and-protocols-审阅增强版.md`；索引链接已同步，测试按 `01-baseline-and-protocols-` 前缀查找的约定不变。
- `docs/code-kit-v2/` 下 01–13 文档与 README 不在本任务可写范围内，本文没有修改。

## 10. 已知的 minor 与剩余风险

**minor**（来源：protocols-api.md 第 19 节、兼容矩阵、各复审记录；复审记录只作线索，下列各条都已在仓库文档中核对到）。第三次修订把已关闭的项改为“已关闭：<依据>”，不删除：

| 编号 | 内容 | 出处 | 状态与归属 |
|---|---|---|---|
| M-01 | 事件日志系列函数只按 run_id 绑定，不检查 request_id 与同一 run 内非空 role 是否一致 | protocols-api 第 19 节“P4 第 5 轮 · 已知未处理的 minor”第 2 条 | **已关闭**：四个日志函数核对日志内部的 request/role 绑定（`E_CONTEXT_BINDING`、binding_errors、固定 reason 顺序），protocols-api 第 11 节写明 complete 的含义；EV-C02 M-01 的 5 个方法 ok（第 83–92 行）。与受信 RunContext 的一致性仍归 04、07 |
| M-02 | 裁决 R-P3 的文字与实现（前缀允许含 `~`）不一致 | protocols-api 第 19 节 | **已关闭**：decisions.md“R-P3 勘误”裁定以实现为准；protocols-api 第 7 节已删去“待规划端确认”，并写明实现要求 `~` 之前至少 1 个字符（`~1`、`~12` 照常接受） |
| M-03 | fixture 条目结构缺少完整性、平台适用性、采集环境、截取范围、是否保留协议结构、来源是否可追溯 | protocols-api 14.2 节；兼容矩阵第 8 节第 3、10 条 | **已关闭**：R-P11 与 R-P11 补充（第 7 节第 14 项）。剩余：`platform_scope`、`traceable` 是登记者声明；没有真实 captured 样本（04） |
| M-04 | 为 D-20–D-23 补 legacy fixture；把兼容矩阵第 1 节的抽查写成回归测试 | 兼容矩阵 4.3 节、第 8 节第 8 条 | **已关闭**：6 个 legacy 合同负例与 `CompatMatrixDCaseTests`（5 个 ok）；`PublicEntryRejectionTests`（3 个 ok，EV-C08 第 80–82 行）。后者只覆盖入库的脱敏归档，不覆盖被忽略的 `.agent/baseline/` 原件 |
| M-05 | 兼容矩阵第 8 节第 6 条关于 `-text` 规则的说法已过时 | compatibility-matrix.md 第 8 节 | **已处理**（完整性审查返工，兼容矩阵修订 8） |
| M-06 | 兼容矩阵第 1 节两条 `codekit01_legacy.py` 命令的结果没有归档 | baseline-report 第 11 节 | **已关闭**：EV-C03（`38 checks, 0 differ`）、EV-C10（`10 checks, 0 differ`） |
| M-07 | 旧行为清单的结构化条目只在规划会话临时目录中 | legacy-inventory 11.6 第 6 条 | **已关闭（归档要求）**：`evidence/inventory-items/`（EV-INV，第 7 节第 9 项）；条目中的“实测”“探针”仍只是线索，证据等级不变（legacy-inventory 11.6 第 1 条，另项）。与基线报告修订 7 的 10.3 节用词一致 |
| M-08 | legacy-inventory 第 0.5、12.1 节把 01 新代码的测试称为“参考实现与取证工具测试” | baseline-report 第 8 节 A16 | **已关闭**：已改称“01 新代码测试（公共协议、fixtures、取证工具）”，原词写在注记中 |
| M-09 | 第 5 轮返工在仓库外留下的临时快照目录（`codekit-p4r5-orig-` 开头）与 Git 安装目录下的测试日志 `p.txt`；完整性审查时只读检查均已不存在，是谁清理的没有记录 | protocols-api 第 19 节“第 5 轮核验的后续处理”末尾 | **仍未关闭**：用户确认 |
| M-10 | `ResourceKind` 缺 4.2.1 要求的 schema、允许的载荷表示与语义校验器 | 完整性审查 | **已关闭**：R-P10（第 7 节第 13 项；`protocols.py:1362`、`:1632`；protocols-api 第 8 节、第 18 节第 22 项） |
| M-11 | 4.3.2 两行在 01 中没有落点，protocols-api.md 没有写归属 | 完整性审查 | **已关闭（文档归属）**：protocols-api 第 11、16、17 节（第 7 节第 15 项）；实现归 04、10 |
| M-12 | protocols-api.md 第 3.2 节说 `E_BASELINE_*`“登记供基线取证工具使用”，取证工具实际不发出 | 完整性审查 | **已关闭**：第 3.2 节已改为“登记待用；当前取证工具不发出，漂移与缺输入分别用 baseline_consistent 与 execution_status 表达”（protocols-api.md 第 166 行）；错误码仍在 `protocols.py:187-188` 登记 |
| M-13 | `tests/legacy_harness.py` 的 `remove_tree` 只适用于目录：对区域内的普通文件调用时 `shutil.rmtree` 报 `NotADirectoryError`，重试后原样抛出；现有调用都传目录 | 兼容矩阵 9.2 节；protocols-api 第 19 节“收尾轮返工 · 需要规划端知悉的事项”第 3 条 | 仍未关闭：01 测试的后续返工。改 harness 会改变 R-P12 内联引用所依赖的夹具字节，改后须重新取证 |
| M-14 | R-P12 的内联引用 `inline:<测试文件>::<类>.<方法>@<测试文件 sha256>` 只记测试文件摘要；这些方法的输入还经过公共夹具 `tests/legacy_harness.py`（`c4e87137…`），按字节复现输入时夹具也必须相同 | 兼容矩阵第 8 节第 9 条 | 仍未关闭：规划端决定是否在引用形式中加入夹具摘要 |
| M-15 | `tests/test_baseline_tool.py` 的 `TempArea.cleanup` 只核对父目录与前缀，没有标记文件与所有权核对；`tests/test_protocols.py` 用 `TemporaryDirectory` 的标准库递归清理 | 兼容矩阵 9.2 节 | 仍未关闭：不在第 7 节第 17 项的原范围；01 测试的后续返工 |
| M-16 | `CredentialScanTests.test_fixture_files_contain_no_credential_shapes` 丢弃白名单放行结果（`found, _allowed = …`，`tests/test_codekit01_fixtures.py:2636`），不断言它为空；“fixture 中没有白名单放行”只有静态核对 | 对抗性核验第二轮（第 15 节第 2 条） | 仍未关闭：01 测试的后续返工（加一条放行结果为空的断言）；改测试后须按 01-L05 与 R-01 重新取证 |

**剩余风险**：

| 编号 | 风险 | 影响与状态 |
|---|---|---|
| R-01 | A01 的 pyc 口径 | **已裁决**（decisions.md R-01），收尾取证按严格口径取证。剩余：受控禁用只有操作者记录；R-01 是否覆盖仓库外输入未明（第 7 节第 20、21 项）；取证工具进程可能把标准库字节码写入前缀目录（推断，未测量）。历史取证 EV-00、EV-01 在严格口径下不满足，保留原口径 |
| R-02 | A07 的口径与剩余缺口（3.7） | **已裁决**（decisions.md R-02）。剩余：G5 的读法待确认（第 7 节第 22 项）；`unmet_within_scope` 涉及的旧行为在迁移比较时须记 NOT_COVERED |
| R-03 | 01 产物未提交，且不在保护范围内 | **已关闭**：核心成果已提交，`.agent/dispatch.config.json` 已登记机械保护；后续合同仍须以最终提交为 `base_sha` |
| R-04 | 单平台 | 任何 Linux、macOS 结论都没有依据 |
| R-05 | 路径物理检查不是安全访问保证（R-P9）；TOCTOU、硬链接、挂载点等不检测 | 下游不能把 `resolve_existing_path_for_review` 或 `read_sealed` 当作访问凭证 |
| R-06 | 网络没有隔离与监测；受控环境的条件（PATH、unset 令牌、`PI_CODING_AGENT_DIR` 为空、`PYTHONPYCACHEPREFIX`、受保护文件 diff、临时目录残留）只有操作者记录 | 两份操作者记录都已归档（EV-RCF、EV-RCC）；离线结论依据静态核实；这些条件的证据等级是 source_reported |
| R-07 | 全部 fixture 都是合成；没有真实 Pi 流、真实历史派遣证据 | 不证明真实 CLI 兼容性或厂商协议 |
| R-08 | 49 个白盒方法依赖旧调度器的内部签名；部分用例用改写记录字段构造状态 | 旧实现内部改动会使这些方法失效；构造的状态不等于真实崩溃或运行路径 |
| R-09 | 旧自测的 `test_timeout`、`test_dispatcher_killed` 会对预期已结束的 PID 无条件执行 `taskkill /F /T` | PID 被复用时可能误杀无关进程树（静态发现，三次取证都没有残留进程） |
| R-10 | 本文与 baseline-report 修订 6 都还没有独立复审（本文第四次修订与报告修订 7 只是勘误，不改判定） | 判定可能在复审后改变 |
| R-11 | 文档 6.6 七类的新旧差分 NOT_RUN（新路径不存在，R-P12） | 新实现（07、10）出现之前，这些旧行为只有特征化测试锁定的现状；新旧差异要等新路径出现后用同一内联输入做差分才能发现 |
| R-12 | 8.4：`remove_tree` 与 `_rmtree` 在递归删除前不核对归属 | **已关闭**（第 7 节第 17 项）。剩余：不防同账户的 TOCTOU；M-13、M-15 |
| R-13 | `PublicEntryRejectionTests.test_baseline_records_are_internal` 按目录现场读取 `evidence/` 中的取证记录：取证时 9、18、18、9 份，`evidence/closure/` 归档后是 19、38、38、19 份 | EV-C08 中该方法的 ok 只对取证时的目录状态成立；以后再运行时输入不同（没有运行，未核对）。以后每新增一批归档，这个方法的输入都会变化 |
| R-14 | 收尾取证的结论只绑定取证输入清单记录的字节 | 代码、测试、fixture、Schema、`protocols-api.md` 或设计文档改动后，结论不再成立，须按 01-L05 与 R-01 重新取证；本文编写时这些字节都没有变化（2.1） |

## 11. 本文的核对方法（measured 与 source_inspected 分开）

第 1–10 条是此前几轮的核对，对象是最终取证（历史编号 EV-01–EV-08）与当时的文档字节，原文保留；第 11 条是第三次修订（收尾轮验收收尾）的核对。

measured（只读归档与工作区，没有重跑被测命令）：

1. 6 份逐条输出（EV-02、EV-04–EV-08）按“`<方法> (__main__.<类>.<方法>) … ok / skipped '<原因>'`”逐方法解析，与 AST 列出的源码测试方法一一对应，计数见当时的 2.3，没有 FAIL、ERROR，也没有输出中多出或缺少的方法。
2. EV-03 的 140 字节输出逐字节查看：36 个“.”、`Ran 36 tests`、`OK`；源码 36 个测试方法。
3. 8 次最终取证各 4 个关键归档文件（archive-manifest.json、capture.json、run/stdout.bin、run/stderr.bin）与实施前基线的 3 个关键文件重算 sha256，与 final/INDEX.md、baseline-report 第 9.1、12.2 节一致。
4. 8 份 `capture.json` 的 `execution_status`、退出码、`baseline_consistent`、输入清单摘要与闭包；16 份 pre/post 输入清单的 sha256 两两相同。
5. 当时 2.1 表中文件的当前 sha256，与最终取证输入清单逐项比较（完整性审查返工后：373 项中 367 项相同，6 项不同）。
6. `tests/fixtures/codekit01/manifest.json` 的条目数与分类计数；三份 expected 文件的 sha256。
7. 受保护路径的 `git diff HEAD --stat` 与 `git status --porcelain`（0 行、0 项）；`git status` 列出不属于 01 的改动（第 9 节 (b)）。
8. 第 10 节 M-09 的仓库外残留只做存在性检查，没有删除任何东西。
9. 完整性审查返工（2026-09-26）：重算最终取证输入清单与当前字节的差异；从归档输入清单读出总设计的 sha256，与当前文件相同（`82e8e668…`）；按 `run/stderr.bin` 逐方法核对兼容矩阵第 9.1 节引用的 15 个方法；manifest 171 条的键集合与当时 protocols-api.md 14.1 节的封闭结构相同。
10. 对抗性核验返工（2026-09-26）：3.7 的方法区间；`evidence/final/` 8 份 archive-manifest 的 664 个条目；`final2-captures.txt` 的摘要与转录。
11. **第三次修订（收尾轮验收收尾，2026-09-26）**：
    - 10 次收尾取证各 4 个关键归档文件（archive-manifest.json、capture.json、run/stdout.bin、run/stderr.bin，共 40 个）重算字节数与 sha256，与 closure/INDEX.md 第 1、3 节、baseline-report 第 13.2 节一致；`run-controls-final/`、`run-controls-closure/` 各 2 个文件、`inventory-items/` 7 个文件、两份 INDEX.md 重算 sha256，与各自 manifest 或登记值一致；`bl-01t1`、`final/` 的 9 份 archive-manifest 与 EV-R、EV-RC 的 manifest 摘要与此前登记的相同。
    - 7 个 unittest 套件的归档输出逐方法解析（起始行与结果行），与当前源码 AST 的方法集合逐一相同：protocols 342（338 ok、4 skipped）、fixtures `-v` 75（75 ok）、baseline_tool 40、legacy_gates 24、legacy_lifecycle 26（2 skipped）、legacy_cli 75（1 skipped）、legacy_events 34；`test_protocols.py` 按命名统计 253 个 A 方法、89 个 F 方法，各 A 编号与类的分布即第 3 节的计数；本文引用的全部测试方法名都在当前源码中，引用处的结果与归档一致。
    - legacy-inventory.md 第 12 节 159 行按方法名在 EV-C05、C06、C07、C09 中逐条定位：156 ok、3 skipped（P4-L03、L04、C52）。
    - EV-C03、EV-C10 的逐行输出：38 行、10 行 SAME，没有 DIFF 行；38 行的构成见 3.2。
    - 当前字节与收尾取证输入清单（1073 项）逐项比较：本修订写入前 1067 项带摘要的条目中 4 项不同（两份基线报告、兼容矩阵、legacy-inventory），其余相同；6 项不带摘要的旧文档仍不存在（2.1）。
    - `tests/fixtures/codekit01/manifest.json`：188 条，类别 legacy 18、negative 157（其中协议负例 135、legacy 派生 22）、synthetic 13，表示全部 `synthetic_fixture`；integrity、platform_scope 分布与兼容矩阵第 8 节第 10 条相同；三份 expected 的 sha256；目录共 189 个文件。
    - 29 份 `environment.json`（收尾取证 20 份、最终取证 pre 8 份、实施前 1 份）sha256 相同（`097cb8a4…`）。
    - 受保护路径的 `git diff HEAD --stat` 为 0 行，`git status --porcelain` 为 0 项；`git status` 列出的不属于 01 的改动与第 9 节 (b) 一致；`docs/code-kit-v2/01-baseline/` 共 1626 个文件、`tests/fixtures/codekit01/` 共 189 个文件；`.agent/runs/` 不存在，`.agent/plans/` 为空。

12. **第四次修订（对抗性核验第二轮，2026-09-26）**：`closure-captures.txt` 第 8–17 行与 10 份归档 `capture.json` 逐行比对（capture-id、argv、executed、returncode、reason、timed_out、duration、baseline_consistent 一致，汇总行与 `run/*.bin` 一致；`tool_exit`、`leaked` 在 capture.json 中没有对应字段）；`evidence/closure/` 下 840 个文件按字节数分类（偶数字节 602 个，其中 0 字节 470 个，非空偶数字节 132 个）；`.agent/baseline/01-closure/` 原件共 830 个文件（每个取证 83 个）；`evidence/inventory-items/` 6 个文件的 sha256 与 manifest 一致；10 份 `archive-manifest.json` 的 sha256 仍与 INDEX.md 第 1 节一致；本文引用的文档字节（第 15 节）；受保护路径 `git diff HEAD --stat` 0 行、`git status --porcelain` 0 项。

source_inspected：

- 此前几轮：总设计全文；两份 legacy 预期文件的 `projection`；`tests/stub_pi.py` 的场景列表；01 新增代码中的删除调用；`scripts/pi_dispatch.py` 中保护路径的实现（`PROTECTED_PATTERNS` :88-92、`extra_protected_paths` :990-995、`glob_regex` 与 `pattern_error` :1063-1113、合同校验 :1500-1518、`evaluate_scope` :2436-2460）；`.agent/dispatch.config.example.json`、`.agent/README.md`；`AGENTS.md` 第 113 行占位符。
- 第三次修订：decisions.md“收尾轮裁决”全文；protocols-api.md 第 3.2、7、8、11、14、16–18 节与第 19 节“收尾轮”“收尾轮返工”；兼容矩阵修订 9–11 的第 1、4.3、8、9 节；legacy-inventory.md 文首注记、9.10.6、9.10.7、11.6；baseline-report 修订 6 第 1、8、10.3、11、13 节；closure/INDEX.md 全文；`tests/test_codekit01_fixtures.py` 各测试类的 docstring 与读取文档、`evidence/` 的代码；`scripts/codekit/protocols.py` 中 `ResourceKind`、`validate_resource_payload`、事件日志函数与 fixture 清单校验函数的位置；`tests/legacy_harness.py`、`tests/codekit01_legacy.py` 中清理函数的位置；`docs/code-kit-v2/README.md` 的索引链接；`AGENTS.md` 第 113 行。
- 第四次修订：`tests/test_codekit01_fixtures.py`（`16b71bca…`）按 AST 读取各类与方法的 docstring 与源码（A02 标注只在 `FileIntegrityTests`、`LegacySourceTests`、`DifferentialTests` 的类 docstring 中）；`CredentialScanTests` 的断言（:2626-2646）与 `CREDENTIAL_ALLOWLIST`（:2430）；`tests/fixtures/codekit01/` 189 个文件中白名单标记的静态查找（原字节、UTF-16 LE/BE 两种对齐、JSON/JSONL 字符串，0 处）；`scripts/codekit/sealing.py`（`af92c1f9…`）的 `DIRECTORY_FSYNC_SUPPORTED`（:63）与 `SEALING_LIMITATIONS`（:66 起，13 条）；protocols-api.md 第 15 节清单（:993-1004）。

没有做的事：没有运行任何测试或取证，没有调用 pi、claude、codex，没有联网，没有安装依赖，没有修改代码、测试、fixture、Schema、受保护文件、`.agent/baseline/` 原件与已有归档目录，没有 git add、commit、stash、reset、checkout 或 clean。各轮使用的临时文件都放在 tempfile 建立的目录中，用后删除。第三次修订只写本文与 `README.md`。第四次修订写本文、`README.md`、两份基线报告、`compatibility-matrix.md` 与 `evidence/closure/INDEX.md`（手写索引，不是归档文件）；`legacy-inventory.md` 没有需要更正的内容，没有改动。

## 12. 完整性审查的逐条处理（2026-09-26）

- **范围**：完整性审查对 01 产物提出 14 个问题（7 个 major、7 个 minor）。本次返工的可写范围是 `acceptance.md`、`README.md`、两份基线报告、`legacy-inventory.md`、`compatibility-matrix.md` 与 `decisions.md`（只能追加）；不含代码、测试、fixture、Schema 与 `protocols-api.md`。
- **做法**：只读取工作区、设计文档与归档证据，没有运行任何被测命令，没有调用模型，没有联网。需要改代码、测试或 `protocols-api.md` 才能关闭的部分，登记在第 7 节第 10–18 项与第 10 节，不在本次修改。
- **判定**：没有任何一项验收的判定因本次返工改变。

| # | 问题（级别） | 处理 | 改动位置 | 仍未关闭的部分 |
|---|---|---|---|---|
| 1 | 没有读取与交叉检查总设计的记录（major） | 登记“实施前读取”为 NOT_RUN；事后补做交叉检查（source_inspected），记录文件摘要、事件封装字段、P0 完成标准与命名的对照结论 | decisions.md 01-L08 与对照表；baseline-report L-TOTAL-DESIGN（JSON `limitations`，MD 第 10.2 节）；README P0 行；本文第 7 节第 10 项 | “用量”事件与 usage-observation 的关系（04）；文件名差异（规划端）；新核心文件的保护路径（用户） |
| 2 | 回归映射的 input_fixture_ref 与 comparison_projection_revision 全部为空，11.6 第 2 条过时，未列入未完成项（major） | 按行回填：LB-CONTRACT、LB-EVENTS 逐行给出 fixture_id 与 `codekit01-legacy-projection-v1`，其余区域按组写明 NOT_COVERED 及原因；第 12 节 P4 方法两字段为空的原因；更正 0.4、9.1、11.6 第 1、2 条 | legacy-inventory.md 9.10、0.4、9.1、11.6、12.9；本文 3.7 known_limitations、第 7 节第 11 项；baseline-report 01-A07 的 known_limitations | 181 行 NOT_COVERED 与 159 个 P4 方法没有 fixture 与投影：**需要改测试与 fixture** |
| 3 | ResourceKind 缺 schema、允许的载荷表示、语义校验器，没有登记差异与移交（major） | 登记为 M-10；在第 8 节给 02、03、06、09 写明过渡期由登记模块挂接校验 | 本文第 1 节、第 8 节、第 10 节 M-10、第 7 节第 13 项 | protocols-api.md 第 18 节补登（规划端）；补字段**需要改 protocols.py 与测试**（先出规格） |
| 4 | 4.3.2 两行（派生视图修订、跨 run 顺序）没有落点与移交（major） | 登记为 M-11；写明归属：派生视图修订与 view_id 归 04（与 adapter_revision 一并），跨 run 顺序归 10；加入第 8 节的移交 | 本文 3.11、第 8 节、第 10 节 M-11、第 7 节第 15 项 | protocols-api.md 第 11、17 节补写（规划端）；实现归 04、10 |
| 5 | 6.6 选样缺超时、取消、恢复、候选漂移、补丁、门禁、旧入口状态解释，缺样本没有登记（major） | 登记缺样本清单，写明这些行为只由 P4 特征化测试锁定现状，不构成 fixture 差分，迁移比较记 NOT_COVERED | 兼容矩阵第 8 节第 9 条；本文 3.2 的 fixture_refs 与 known_limitations、第 7 节第 12 项、R-11 | 补 fixture 与锁定投影：**需要改测试与 fixture** |
| 6 | fixture 条目缺“完整性”“平台适用性”与真实样本的采集环境、截取范围（major） | 扩写 M-03，列全缺少的字段；第 1 节把 fixture manifest 的状态改为不宣称平台适用性与完整性“明确” | 本文第 1 节、3.12、第 10 节 M-03、第 7 节第 14 项；兼容矩阵第 8 节第 10 条 | protocols-api.md 14.2 节补登（规划端）；补字段**需要改 protocols.py、生成器、全部条目与测试**（先出规格） |
| 7 | 8.3 决策表 8 行没有逐行落点，8.4 清理归属只在一个测试文件中核对且没有登记（major） | 新增 8.3 逐行落点表与 8.4 清理代码核对表 | 兼容矩阵第 9 节（开头的“依据”同步写明各节对应）；本文 3.13、第 7 节第 16、17 项、R-12 | fixture 凭据扫描与 `remove_tree`、`_rmtree` 的归属核对：**需要改测试代码**；冻结视图、受控清理归 04、07；凭据处置流程归规划端与用户 |
| 8 | 取证后变化的文件数写错，关于 README 的说法不对（minor） | 重算：初稿编写时已有 4 项不同（含 README），返工后 6 项；删去“README 不在取证输入中” | 本文 2.1、第 7 节 D.3 第 1 条、第 11 节第 5 条 | — |
| 9 | decisions.md 小节标题写 R-P1–R-P8，表中有 R-P9（minor） | decisions.md 只能追加，没有改标题；追加勘误，写明以 R-P1–R-P9 为准、R-P9 来自 P4 | decisions.md 追加的“勘误” | 标题原文保留（按只追加规则） |
| 10 | protocols-api.md 说 E_BASELINE_* 供取证工具使用，但工具不使用（minor） | 登记为 M-12，写出准确说法 | 本文第 10 节 M-12、第 7 节第 18 项 | protocols-api.md 第 3.2 节修订（规划端；本次不可写该文件） |
| 11 | 报告与验收映射没有 applicability 字段（minor） | 增加 applicability 与理由（01-L09）；用于 F028 与 01-A16，并写明它不能代替必需能力的结论 | decisions.md 01-L09；baseline-report `identity.status_vocabulary.applicability`、`acceptance[01-A16].applicability_by_platform`、MD 文首与第 8 节；本文判定规则、第 0 节、3.16、第 4 节 F028 | — |
| 12 | M-03 与 A12 漏了“来源是否可追溯”（minor） | 两处补上 | 本文 3.12、第 10 节 M-03；兼容矩阵第 8 节第 3 条 | 同第 6 项 |
| 13 | 兼容矩阵第 6 节停在 P4 最终取证之前（minor） | 修订 8：6.1 补上 4 个 `test_legacy_*.py`、`legacy_harness.py`、第三条 `-text` 规则与 `01-final/`、`01-P4/`；6.2 更正 AGENTS.md 一行；6.3 第 3、4、7 步随之更新；第 8 节第 6 条标为已更正（M-05） | 兼容矩阵第 6、8 节；本文第 7 节 D.3 第 9 条、第 10 节 M-05 | — |
| 14 | 基线报告没有记录上传原文的摘要（minor） | 补记附录 F.1 的原文摘要（source_reported），写明本仓库没有原文、无法复算，只能以增强版为依据 | baseline-report `identity.source_document.original_upload`、L-SOURCE-ORIGINAL、MD 文首 | 原文不在仓库中，无法复算 |

**返工后的字节**（2026-09-26 重算，measured）：

| 文件 | 字节 | sha256 |
|---|---|---|
| `baseline-report.json`（修订 4） | 244425 | `2ee4eaf7c35aeff05e703f51a10a456bd1af3b2ff0640d869c719f73dd992aaf` |
| `baseline-report.md`（修订 4） | 91427 | `9a0b934de85375977e33fc4d4cb0486db2e7583b9c7e1855d06772010b77b40c` |
| `legacy-inventory.md` | 570632 | `a9d3d189f6153728d54b0bd146913193daaea235989391d34195b4f5e3f350a7` |
| `compatibility-matrix.md`（修订 8） | 73701 | `91e4ea22d14e677823b2c15e08d0d6e5857405332342083a1b6531c7d0f0f6ea` |
| `decisions.md` | 15168 | `7e5415b04ca95b246bd08081d74f416645dec5b63fde1da5fbe66aedecc06da7` |
| `protocols-api.md`（未改动） | 242742 | `4efea533cd5f564f0a857e0d316a36a5a402a6121e54bc119947ca881673c45e` |

`README.md` 与本文在最后修改，不在上表中列摘要（本文不内嵌自身摘要）。

## 13. 对抗性核验的逐条处理（2026-09-26）

- **范围**：对抗性核验确认了 7 个 minor 问题。本次返工的可写范围是本文、`README.md`、两份基线报告、`legacy-inventory.md`、`compatibility-matrix.md` 与 `evidence/final/INDEX.md`；不含代码、测试、fixture、Schema、归档原件，也不能新建目录。实际修改了本文、`README.md`、两份基线报告（报告修订 5）与 `INDEX.md`；`legacy-inventory.md` 与 `compatibility-matrix.md` 没有需要更正的内容，没有改动，摘要不变。
- **做法**：逐条先核对问题是否成立（结果见表中“核对”列，都是 measured 或对文档原文的核对），再改文档。没有运行任何被测命令，没有调用模型，没有联网。
- **判定**：没有任何一项验收的判定因本次返工改变。第 5 条只是把摘要中省掉的限定写全，第 3 条只是把基线报告里与本文冲突的记法撤回。

| # | 问题 | 核对 | 处理 | 改动位置 | 仍未关闭的部分 |
|---|---|---|---|---|---|
| 1 | 3 处引用不存在的“7.9” | 成立：全文没有 7.9 小节，第 7 节只有 D.3 表与编号的未完成项 | 第 0 节 A13 行改指第 7 节未完成项第 2 项；3.13 的 execution_status 改指第 2 项（事件日志部分见第 1 项）；3.2 的 known_limitations 改指第 6 项 | 第 0 节、3.2、3.13 | — |
| 2 | A07 的方法区间写成 L01–L22，与“62 个、60 个 ok”矛盾 | 成立：原区间展开得 63 个编号（61 ok、2 skipped），多出的是 P4-L17；baseline-report 7.2 为 62 行。按 7.2 的 62 个方法逐个在归档 `run/stderr.bin` 中定位：60 个 `ok`、P4-L03 与 L04 `skipped` | 区间改为 L01–L16、L18–L22，并注明 P4-L17 在清单第 12.4 节归六类之外（01-A08） | 3.7 | — |
| 3 | 基线报告 JSON 中 13 项仍是 NOT_RUN，与本文冲突 | 成立：JSON 的 01-A02–A06、A08–A15 为 `execution_status=NOT_RUN`、`evidence_basis=unknown`、`evidence_refs=[]`，理由停在修订 3；MD 第 1、8 节同样 | 报告修订 5：13 条改为 `judged_by_this_report=false`，指向本文第 0、3、2.3 节；照录本文的判定文字，并把证据编号解析为归档文件路径、字节数与 sha256；删去过时的两条理由（只在 `record_history` 留一句说明）；`conclusion` 的验收条与 `status_vocabulary` 同步；MD 文首、第 1、8 节同步。本文文首写明“以 JSON 为准”只适用于报告自己的两份文件 | baseline-report.json `acceptance[]`、`identity`、`conclusion`；baseline-report.md 文首、第 1、8 节；本文文首 | JSON 没有写入本文的 sha256：本文第 1 节与本节记录报告的摘要，反过来再记会形成循环。本文当前字节的摘要记在 `README.md` 文件索引中 |
| 4 | INDEX.md 写“全部 672 个归档文件”与 `archived_sha256` 一致 | 成立：每份 manifest 列 83 个文件，不含自身；664 个条目的 `archived_sha256` 与归档文件一致，`original_sha256` 与原件一致；8 份 manifest 的 sha256 与 INDEX.md 第 1 节、本文 2.3 一致 | 按任务授权直接更正 INDEX.md 第 1 节，附勘误与修订记录；报告第 12 节、12.7 节与 JSON `archive_integrity`、`index_ref` 写明 664 与 672 的区别，并记下修订 3 的复核漏了这句。INDEX.md 的摘要因此改变：报告 `index_ref` 与 01-A01、01-A07、01-A16 对它的引用按新字节重新固定，旧摘要进 `history`；本文第 1 节同步 | INDEX.md 第 1 节与修订记录；baseline-report.md 第 12、12.7、12.9 节；JSON 对应字段；本文第 1 节 | — |
| 5 | README 与“一句话”把 A01、A07 写成不附条件的 Windows PASS | 成立：README 中没有 pyc、R-01、R-02 或“更严口径”；本文“一句话”也省掉了第 0 节与 3.1、3.7、3.9 的限定 | “一句话”改成分项：A01 按现行口径 PASS、A07 为带 `unmet_within_scope` 的范围限定 PASS，两项口径待定（R-01、R-02），更严口径下都是 FAIL；A09 元校验 BLOCKED；范围外部分写明移交 02、03、04、07 或模块未指定。第 0 节表中 A01、A07 两行也补上“更严口径下为 FAIL”。README 总体结论同步 | 本文第 0 节（表与“一句话”）；README“总体结论” | 口径本身仍待规划端决定（第 10 节 R-01、R-02） |
| 6 | 第 0 节 A10 行漏了授权层 | 成立：3.10 的 execution_status 写了“授权层（保护路径判断）未实现，归 03”，第 0 节没有 | A10 行的范围外列补上“授权层（保护路径判断）：未实现，归 03”；基线报告 JSON 的照录随之包含这一句 | 第 0 节 | 授权层由 03 实现 |
| 7 | 最终取证的操作者记录 `final2-captures.txt` 没有归档 | 成立：`evidence/run-controls/manifest.json` 的 capture_id 只有 `bl-01t1-legacy-20260925`。原件仍在会话临时目录，1495 字节，sha256 `c362495c…d6dd`，与登记值相同。另发现：记录只含 `tool_exit`、运行结果、`leaked=[]` 与 `empty_dir_entries=0`；“在 Git Bash 中运行”“PATH 去掉真实 CLI”“unset 令牌”“受保护文件 diff 为 0 行”不在该文件中，只来自派发说明 | 可写范围不含新建归档目录，没有做正式归档。把内容逐字转录到 INDEX.md 第 5.2.1 节（按规则重建与原件逐字节相同），会话清理后仍可复算摘要；2.2、R-06、报告 L-FINAL-OPERATOR 与 JSON `environment_source_reported` 写明来源的拆分、转录位置与“尚未归档”；证据等级仍是 source_reported | 本文 2.2、第 7 节第 19 项、R-06；INDEX.md 5.2.1；baseline-report.md 10.1；JSON `limitations`、`environment_source_reported` | 正式归档：规划端（第 7 节第 19 项） |

**返工后的字节**（2026-09-26 重算，measured）：

| 文件 | 字节 | sha256 |
|---|---|---|
| `baseline-report.json`（修订 5） | 288103 | `d1ddf225dd3da970b820d0084867d6953189c67e6deb78ec3d7e9acc6cf8dc51` |
| `baseline-report.md`（修订 5） | 97583 | `209f9605cd799d0a579d30e955040e2743f49c09f90190b02952e305a8efce95` |
| `evidence/final/INDEX.md` | 25868 | `bc04e2c39cbf67301af0b7f387bdcd8c476e51d5d28478eddc67aa74536a496d` |
| `legacy-inventory.md`（未改动） | 570632 | `a9d3d189f6153728d54b0bd146913193daaea235989391d34195b4f5e3f350a7` |
| `compatibility-matrix.md`（修订 8，未改动） | 73701 | `91e4ea22d14e677823b2c15e08d0d6e5857405332342083a1b6531c7d0f0f6ea` |
| `decisions.md`（未改动） | 15168 | `7e5415b04ca95b246bd08081d74f416645dec5b63fde1da5fbe66aedecc06da7` |
| `protocols-api.md`（未改动） | 242742 | `4efea533cd5f564f0a857e0d316a36a5a402a6121e54bc119947ca881673c45e` |

`README.md` 与本文在最后修改，不在上表中列摘要；本文当前字节的摘要记在 `README.md` 的文件索引中。受保护文件相对 HEAD 的 `git diff --stat` 与 `git status --porcelain` 在返工后仍是 0 行、0 项（measured）。

## 14. 收尾轮验收收尾的逐条处理（2026-09-26）

- **范围**：本次可写的只有本文与 `README.md`。依据 decisions.md“收尾轮裁决”、收尾轮的代码改动（`protocols.py` 的 R-P10、R-P11、M-01；`tests/legacy_harness.py` 与 `tests/codekit01_legacy.py` 的清理前归属核对；`tests/test_codekit01_fixtures.py` 的凭据扫描、R-P11、D-20–D-23 与清理核对测试；fixtures 的新字段与新 case；protocols-api.md、兼容矩阵、legacy-inventory.md 与基线报告修订 6 已由各自的编写者更新）与 10 次收尾取证。
- **做法**：只读取归档、工作区与文档，按第 11 节第 11 条核对后改写；没有运行被测命令。

| # | 任务 | 处理 | 改动位置 |
|---|---|---|---|
| 1 | 证据引用切换到收尾取证 | 新增 EV-C01–EV-C10（与兼容矩阵的 EV-C02、C04、C08 一致），`evidence/run-controls/` 改记 EV-RC，新增 EV-RCF、EV-RCC、EV-INV；EV-00、EV-01–EV-08 移入“历史取证”表；2.1 的字节改为收尾取证输入清单的值；2.2 新增 BL-CLOSURE 与收尾取证的受控环境 | 文首、判定规则、2.1–2.3，第 3–8 节各处 |
| 2 | 第 0 节与“一句话” | A01 按 R-01 重判（PASS，两个前提待确认）；A07 按 R-02 重判（PASS，G5 读法待确认）；A02 由“整项不记 PASS”改为“01 范围内 PASS”；A11、A12、A13 的范围说明按 M-01、R-P11、凭据扫描更新 | 第 0 节 |
| 3 | 第 3 节各 A 项 | 逐项换证据编号并按当前源码重算方法数：A04 67→73（R-P10 6 个）、A11 41→46（M-01 5 个）、A12 18→25（R-P11 6 个、R-P10 1 个）；A02、A03、A04、A09、A12、A13 补 EV-C08 的方法级引用；A01、A07、A16 采用基线报告修订 6 的判定并写明前提；已关闭的 minor 在各项 known_limitations 中改写 | 3.1–3.16 |
| 4 | 第 4 节 F001–F050 | 按 AST 与归档逐方法核对，名称与计数不变（47 PASS、3 NOT_RUN）；证据改为 EV-C02、EV-C04；F005、F008、F012、F021 补 D-20–D-23 的 fixture 方法，F033 的 fixture 侧改为方法级，F050 的真实取证次数改为 19 | 第 4 节 |
| 5 | 第 7 节未完成项 | 第 6、7、9、11、13–15、17–19 项标为已关闭并写依据；第 12 项（七类与 D-20–D-23 已关闭，缺字段类样本仍缺）与第 16 项（凭据扫描已关闭，其余仍缺）标为部分关闭；第 1–5、8、10 项如实保留；新增第 20–25 项 | 第 7 节 |
| 6 | 第 9 节 | 内容保持，逐项核对：(b) 的提交清单加入 `evidence/` 下各目录（含新增的 `closure/`、`run-controls-final/`、`run-controls-closure/`、`inventory-items/`）与文件数，写明不能用 `git add -A`、`git add docs/` 等，逐路径暂存并核对；(a)、(c)、(d)、(e) 核对后补充 R-01 与 R-P10 的相关说明 | 第 9 节 |
| 7 | 第 10 节 | M-01–M-04、M-06–M-08、M-10–M-12 标为已关闭（M-05 早已处理），M-09 保留；新增 M-13–M-15；R-01、R-02 改为已裁决并写剩余部分，R-12 已关闭，R-11 按 R-P12 改写，新增 R-13、R-14 | 第 10 节 |
| 8 | README.md | 进度表各阶段的最终状态、收尾轮一行、总体结论（与第 0 节一致）、文件索引（含新增的 evidence 子目录与本文的当前摘要） | README.md |

**判定变化**：01-A01（重判，仍为 PASS，依据换为收尾取证并附前提）、01-A07（重判，仍为 PASS，附 G5 前提）、01-A02（整项不记 PASS → 01 范围内 PASS）。其余 13 项的判定不变，只更新了证据与方法清单。

**引用的文档与归档的字节**（本修订编写时测得，measured）：

| 文件 | 字节 | sha256 |
|---|---|---|
| `baseline-report.json`（修订 6） | 459146 | `6449e16bc19ca3ea870dad6ce90cffb8c16f700ad350c71e06180983e3298da6` |
| `baseline-report.md`（修订 6） | 163364 | `62dd941473716fa521b5d72dfe6709ac8c8ceb95ca10e93d309446230b4181e2` |
| `legacy-inventory.md` | 721294 | `9fdba24ca5de15b4cb75c206caf1e9633bb6866f0f2a8d12372ded225792adc4` |
| `compatibility-matrix.md`（修订 11） | 116258 | `f388c96fc4b0d579be55d083e4ef37552546c2e48b296fdd885b4c58095731d1` |
| `decisions.md` | 20186 | `8b460b2d57f1e0e8c1ea2cc2da140c66e186f92425a8d8a586a2eb51ececbb61` |
| `protocols-api.md` | 301574 | `785c75f6c3481065fcf8c7a04ea56018a6d69d0309203cc037e3c1b19b016fa0` |
| `evidence/closure/INDEX.md` | 44858 | `a6a84822352c761f3ca3e7f055a39284fcaae1f0183d61f475eb02c9410b0196` |
| `evidence/final/INDEX.md`（历史，未变） | 25868 | `bc04e2c39cbf67301af0b7f387bdcd8c476e51d5d28478eddc67aa74536a496d` |
| `evidence/run-controls-closure/closure-captures.txt` | 3133 | `fb00af747f1ff3fd7b20a35d5902c918f7057f58bdfb7e9c660d4db57ccc0e86` |
| `evidence/run-controls-final/final2-captures.txt` | 1495 | `c362495cc389d37204e1250f8ff613585f5722cb8b0e63c60bcf668b9d11d6dd` |
| `evidence/inventory-items/manifest.json` | 1326 | `cebbd8bfc9861f97ce21f81478b2574aef5fdd6a8acff3df1f5ca70d9ddba8c9` |

`README.md` 与本文在最后修改，不在上表中列摘要；本文当前字节的摘要记在 `README.md` 的文件索引中。受保护文件相对 HEAD 的 `git diff --stat` 与 `git status --porcelain` 在本修订后仍是 0 行、0 项（measured）。

## 15. 对抗性核验第二轮的逐条处理（2026-09-26）

- **范围**：对抗性核验确认了 8 个 minor 问题。可写范围是本文、`README.md`、两份基线报告、`legacy-inventory.md`、`compatibility-matrix.md` 与 `evidence/closure/INDEX.md`；不含代码、测试、fixture、Schema、受保护文件、`.agent/baseline/` 原件与已有归档文件。实际修改了本文、`README.md`、两份基线报告（报告修订 7）、`compatibility-matrix.md`（修订 12）与 `evidence/closure/INDEX.md`（第 9 节修订记录）；`legacy-inventory.md` 没有需要更正的内容，没有改动，摘要不变。
- **做法**：逐条先核对问题是否成立（“核对”列，measured 或 source_inspected 分开写），再改文档，宁可降级。没有运行任何被测命令或测试，没有调用模型，没有联网，没有安装依赖；临时脚本只放在 tempfile 建立的目录中，用后删除。
- **判定**：没有任何一项验收的判定因本次返工改变。第 1、2 条只把依据的写法降级为静态（A02、A12 的判定另有运行证据支撑）；第 3–8 条是证据等级、用词、条号与计数口径的更正。

| # | 问题 | 核对 | 处理 | 改动位置 | 仍未关闭的部分 |
|---|---|---|---|---|---|
| 1 | 3.2 说 A02 的 19 个方法“对应关系取自类 docstring”，其中 6 个不成立 | 成立（source_inspected）：按 AST 读取 `tests/test_codekit01_fixtures.py`（`16b71bca…`），只有 `FileIntegrityTests`、`LegacySourceTests`、`DifferentialTests` 的类 docstring 含“01-A02”（13 个方法）；`StubTests`、`CompatMatrixDCaseTests` 的类与方法 docstring、方法源码都不含 A02。19 个方法在 EV-C08 run/stderr.bin 中都是 ok，行号无误（measured） | 分成 ①（13 个，类 docstring 标注）与 ②（6 个，规划端按 stub 锁定字节与兼容矩阵 D-20–D-23 归入的推断）；evidence_basis 写明判定不依赖 ② 的归属（EV-C10、`DifferentialTests`、EV-C03 另有支撑）；文首判定规则补一句；第 0 节 A02 行注明 | 文首、第 0 节、3.2 | — |
| 2 | 3.12 把“没有白名单放行”写成 EV-C08 的运行结果；兼容矩阵 E19、9.1 节同样 | 成立（source_inspected）：`test_fixture_files_contain_no_credential_shapes` 为 `found, _allowed = scan_bytes_for_credentials(path, raw)`（:2636），只在非白名单命中不为空时失败（:2643-2646）。结论本身属实：189 个文件的原字节、UTF-16 LE/BE 两种对齐与 JSON/JSONL 字符串中三个白名单标记 0 处（静态核对） | “没有非白名单命中”保留为 measured；“没有白名单放行”改记 source_inspected，与运行结果分开写；兼容矩阵修订 12 同步 E19 与 9.1 节；第 7 节第 16 项补“无非白名单命中”；新增 M-16 | 3.12；第 7 节第 16 项；第 10 节 M-16；兼容矩阵文首、E19、9.1 节 | 测试加放行结果为空的断言后重新取证（M-16） |
| 3 | INDEX 5.2、5.3 把操作者记录记为“measured（操作者脚本）”，与基线报告、本文的 source_reported 不一致，且不在 2.4 词表中 | 成立：INDEX.md 原第 27、345、369 行；基线报告 JSON `closure_regression.r01_pyc_control` 与 MD 13.5、10.3 节为 source_reported；本文 2.2、3.1 同 | INDEX 文首证据等级写法全部对到 2.4 词表，操作者记录改为 source_reported（注明第 5–7、18、19 行的定位与计数由操作者脚本现场得到但取证工具没有采集，第 4 行是配置声明）；5.2 标题、5.3 节同步；5.3“结论”降级为“受控条件只有记录，本目录不能独立证明” | INDEX.md 文首、5.2、5.3、第 9 节 | R-01 受控禁用的证据等级仍待规划端决定（第 7 节第 20 项） |
| 4 | 2.2 与基线报告第 13 节导语说操作者记录第 8–17 行与各 capture.json“逐字段一致”，但 `tool_exit`、`leaked` 没有对应字段 | 成立（measured）：10 份 capture.json 中没有这两项；capture-id、argv、executed、returncode、reason、timed_out、duration、baseline_consistent 与 capture.json 一致，汇总行与 `run/*.bin` 一致（INDEX 2.2 原核 7 项，本修订补核 executed、reason） | 本文 2.2、基线报告第 13 节导语与 JSON `operator_record.evidence_basis`、INDEX 2.2 节改为列出实际一致的字段，`tool_exit`、`leaked` 记 source_reported | 2.2；基线报告第 13 节、13.10 节、JSON；INDEX.md 2.2 | — |
| 5 | L-FINAL-OPERATOR 的状态 MD 与 JSON 不一致；M-07 在基线报告与本文、README 中用词不一致 | 成立：基线报告 MD 10.3 节“归档部分关闭”，JSON `status_revision_6=closed`；M-07 在报告中为“归档部分关闭”，本文与 README 为“已关闭”。归档本身属实（measured）：6 个 `inventory-*.items.json` 的字节数与 sha256 与 manifest（`cebbd8bf…`）一致 | L-FINAL-OPERATOR 统一为“部分关闭（归档要求已关闭；证据等级仍是 source_reported）”，报告 JSON 改为 partially_closed 并记下原值；M-07 与第 7 节第 9 项统一为“已关闭（归档要求）；条目中的‘实测’‘探针’仍只是线索，证据等级不变”；第 7 节第 19 项同样标“（归档要求）”；README 同步 | 第 7 节第 9、19 项；第 10 节 M-07；基线报告 10.1、10.3 节与 JSON；README | 最终取证与收尾取证受控条件的证据等级仍是 source_reported（R-06） |
| 6 | 3.13 写 `SEALING_LIMITATIONS` 第 8 条，与代码不符 | 成立（source_inspected）：`scripts/codekit/sealing.py`（`af92c1f9…`）中该常量 13 条，崩溃持久性与 Windows 父目录 fsync 是第 1、2 条，第 8 条是 A13 的范围；被引用的文字是 protocols-api.md 第 15 节清单第 8 项（第 1002 行）；`DIRECTORY_FSYNC_SUPPORTED = os.name != "nt"`（:63）无误 | 改为“`SEALING_LIMITATIONS` 第 1、2 条，即 protocols-api.md 第 15 节清单第 8 项”；基线报告 JSON 照录的同一句保持原样，另加 `transcript_errata_revision_7` | 3.13；基线报告 JSON `acceptance[01-A13]` | 照录文字整体的同步仍按第 7 节第 25 项 |
| 7 | INDEX 称每一行都能追到归档文件，但第 1 节表“archive 退出码”“原件目录文件数”两列不在归档文件中 | 成立：`archive-manifest.json` 顶层没有退出码；原件目录被 Git 忽略。原件数字本身正确（measured，只读复核 830 个，每个 83 个） | INDEX 文首加“例外”、表头与 1.1 节标为归档时核对（不能从归档文件复算）；基线报告 13.7 节已把归档命令退出码与控制台输出记为 source_reported，不需要改 | INDEX.md 文首、第 1、1.1 节 | — |
| 8 | INDEX 7.1 节“字节数为偶数的 132 个文件”口径不符 | 成立（measured）：840 个文件中偶数字节 602 个，其中 0 字节 470 个，非空且偶数字节 132 个；空文件不影响扫描覆盖，残留检查的结论不变 | 改为“非空且字节数为偶数的 132 个文件”，并写出 602 与 470 | INDEX.md 7.1 节 | — |

**返工后的字节**（2026-09-26 重算，measured）：

| 文件 | 字节 | sha256 |
|---|---|---|
| `baseline-report.json`（修订 7） | 467608 | `b49b20236c9f806569b9772c785cc6f53a003615754396dfaf4ff55138140d5b` |
| `baseline-report.md`（修订 7） | 171426 | `592013782247ca086e6a0aec98a6a5a235b878b25a0db9e0390e8e1777de8541` |
| `compatibility-matrix.md`（修订 12） | 118604 | `07b3aa17a5e8ed1909f83f4cee7a239d3ea9a7875cdc92a62b52b4d0abe2af34` |
| `evidence/closure/INDEX.md`（勘误后） | 48511 | `85ae818f8a5de0b42cf0568b2a5b5205752012e9340519013c12a3706718f0ba` |
| `legacy-inventory.md`（未改动） | 721294 | `9fdba24ca5de15b4cb75c206caf1e9633bb6866f0f2a8d12372ded225792adc4` |
| `decisions.md`（未改动） | 20186 | `8b460b2d57f1e0e8c1ea2cc2da140c66e186f92425a8d8a586a2eb51ececbb61` |
| `protocols-api.md`（未改动） | 301574 | `785c75f6c3481065fcf8c7a04ea56018a6d69d0309203cc037e3c1b19b016fa0` |
| `evidence/run-controls-closure/closure-captures.txt`（归档，未改动） | 3133 | `fb00af747f1ff3fd7b20a35d5902c918f7057f58bdfb7e9c660d4db57ccc0e86` |
| `evidence/inventory-items/manifest.json`（归档，未改动） | 1326 | `cebbd8bfc9861f97ce21f81478b2574aef5fdd6a8acff3df1f5ca70d9ddba8c9` |

`README.md` 与本文在最后修改，不在上表中列摘要；本文当前字节的摘要记在 `README.md` 的文件索引中。受保护文件相对 HEAD 的 `git diff --stat` 与 `git status --porcelain` 在本修订后仍是 0 行、0 项（measured）。
