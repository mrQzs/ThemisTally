# 01 基准与公共协议：分阶段实施计划

依据：`docs/code-kit-v2/01-baseline-and-protocols-审阅增强版.md`（修订 `review-expanded-2026-09-25`）。

- 开始日期：2026-09-25
- 调查基线：`a4fa199b0e5bdc658215765ee7558b9fe6723940`（sha1 对象格式），与文档 2.1 记载的调查提交一致；实际取证以各阶段的采集结果为准。
- 执行方式：由规划端（Claude Code）直接完成，子任务交给 Claude 子代理并行处理。**本次没有派遣 Pi**：AGENTS.md 规定派遣需要用户在对话中明确要求，本次没有这项要求。
- 授权边界：不改现有调度器 `scripts/pi_dispatch.py`、`scripts/dispatch-pi.sh`、技能源与生成副本；不启动模型、不联网、不安装依赖（本机缺少 `jsonschema`，Schema 元校验记为 BLOCKED（缺工具且未授权安装，01-L07））；第一阶段文件已按验收清单逐路径提交；不推送。

## 阶段与子任务

| 阶段 | 子任务 | 产物 | 对应验收 |
|---|---|---|---|
| **P0 准备与边界** | 0.1 读取规则与设计输入 · 0.2 静态核实 stub 离线边界 · 0.3 记录工具链 · 0.4 记录决策采纳（01-D01–D10）· 0.5 划定证据目录与排除规则 | `decisions.md`、`.gitignore` 增加 `.agent/baseline/` | 前置 |
| **P1 基线取证（01-T1）** | 1.1 取证工具（Git 事实、`status --porcelain=v1 -z`、输入清单、二进制采集、前后采样）· 1.2 在当前基线运行 `python tests/test_dispatch.py` · 1.3 旧行为清单（合同规范化/校验、预检与事件、候选与 G0–G6、锁/监督/attempt、入口退出码与 wait、测试清单）· 1.4 基线报告与回归映射 | `scripts/codekit/baseline.py`、`baseline-report.{json,md}`、`legacy-inventory.md`、`evidence/` | A01、A07、A16 |
| **P2 公共协议（01-T2）** | 2.1 结构化错误、严格 JSON、固定快照、标识与 Schema 路由 · 2.2 业务路径、ResourceRef、Git OID、资源依赖环 · 2.3 事件封装、seq 重放与冲突、分维度状态视图、raw_refs · 2.4 用量观测与观测视图（不记账）· 2.5 本地 Schema 文件 · 2.6 协议测试与无副作用导入测试 | `scripts/codekit/protocols.py`、`schemas/codekit-public-v1.schema.json`、`tests/test_protocols.py` | A03、A04、A05、A06、A08、A09、A10、A11、A12、A13、A14 |
| **P3 兼容 fixtures（01-T3）** | 3.1 legacy 选样（原字节）· 3.2 合成样本与黄金向量 · 3.3 单一故障负例 · 3.4 用旧实现锁定预期判断 · 3.5 来源 Manifest · 3.6 差分与完整性测试 · 3.7 兼容矩阵 | `tests/fixtures/codekit01/`、`tests/test_codekit01_fixtures.py`、`compatibility-matrix.md` | A02、A09、A12 |
| **P4 验收与交接** | 4.1 全部新测试与旧自测复跑 · 4.2 A01–A16 验收映射 · 4.3 平台矩阵 · 4.4 保护范围与索引更新 · 4.5 多视角对抗复审与返工 · 4.6 交接检查（附录 D.3） | `acceptance.md`、`evidence/final/`（历史）、`evidence/closure/`；`.agent/dispatch.config.json` 已登记 01 核心保护范围，顶层索引已修复 01 设计文档链接 | 全部 |

依赖：P1 的取证运行必须先于 P2/P3 的任何文件写入（新文件会进入工作区清单）；P1 的只读源码清单可与取证工具编写并行；P2 与 P3 的合成部分可以并行，P3 的“旧实现预期”依赖 P1 清单；P4 依赖全部阶段。

## 进度

最终状态（2026-09-26，收尾轮之后）。“收尾取证”指规划端按 R-01 严格 pyc 口径做的 10 次取证 `bl-01closure-*-20260926`（[evidence/closure/](evidence/closure/INDEX.md)），它取代了 8 次最终取证 `bl-01final-*`（保留为历史证据）；证据编号 EV-C01–EV-C10 见 [acceptance.md](acceptance.md) 第 2.3 节。

| 阶段 | 状态 | 说明 |
|---|---|---|
| P0 | 已完成，0.1 有缺口 | 离线边界静态核实发现 2 个阻断项（doctor 会运行真实 claude/codex、读取真实 `~/.pi/agent`），均以受控环境消除，未改文件。0.1 没有留下读取总设计 `docs/code-kit-v2-design.md` 的记录，文档 6.1 的“实施前读取”记 NOT_RUN；文档 2.1 要求的交叉检查已事后补做（source_inspected），三项后续仍未关闭（[decisions.md](decisions.md) 01-L08；acceptance.md 第 7 节第 10 项） |
| P1 | 已完成 | 取证工具 `baseline.py`（40 项自测，收尾取证 EV-C04 全部 ok）；实施前基线 `bl-01t1-legacy-20260925`：旧自测 256 checks / 0 failed，前后采样一致；旧行为清单 224 行（6 区域 194 条加核对者补 30 条）与第 12 节 P4 特征化回归 159 个方法。收尾轮：清单按 R-P12 回填 input_fixture_ref 与 comparison_projection_revision（9.10.5–9.10.7、12.10，NOT_COVERED 由 181 行降为 67 行），更正 M-08 用词；结构化条目归档到 `evidence/inventory-items/`（M-07 已关闭（归档要求）；条目中的“实测”“探针”仍只是线索，证据等级不变）。基线报告为**修订 7**：修订 6 新增第 13 节收尾取证，按 R-01、R-02 重判 A01、A07、A16；修订 7 是对抗性核验勘误，不改判定 |
| P2 | 已完成（收尾取证已复跑；独立终审待进行，见 4.5） | `protocols.py`/`sealing.py`；实现与测试独立编写后调和，多视角复审多轮返工；裁决 R-P1–R-P9 已落实。收尾轮落实 R-P10（`ResourceKind` 三项声明与 `validate_resource_payload`）、R-P11（fixture 条目新字段与第 3b、5 步，第 5 步按受控词表判定）与 M-01（事件日志内部的 request/role 绑定），并经收尾轮复审返工（protocols-api.md 第 19 节“收尾轮”“收尾轮返工”）。收尾取证 EV-C02：`test_protocols.py` 342 个方法，338 个 ok，4 个跳过（F017、F029、F030 记 NOT_RUN，jsonschema 元校验记 BLOCKED） |
| P3 | 已完成（收尾取证已复跑；独立终审待进行，见 4.5） | 收尾轮：manifest 按 R-P11 重新生成为 188 条（目录 189 个文件）；D-20–D-23 落为 6 个 legacy 负例；新增 fixture 凭据形态扫描（15 类形态）与清理前归属核对的回归测试；兼容矩阵为修订 12（修订 12 是勘误：凭据扫描的“没有白名单放行”改记为静态核对，测试只断言没有非白名单命中）。收尾取证 EV-C08：`test_codekit01_fixtures.py -v` 75 个方法都有方法名且都是 ok；EV-C03：`codekit01_legacy.py --check` 38 行 SAME、0 行 DIFF；EV-C10：`--check-stub-regen` 10 行 SAME（M-06 已关闭）。文档 6.6 七类按 R-P12 为“旧路径已锁定，差分 NOT_RUN（新路径不存在，归 07、10）”；缺字段类仍缺两种样本 |
| P4 | 进行中：4.1–4.4、4.6 已完成；4.5 待独立复审 | 见下表 |

P4 子任务：

| 子任务 | 状态 | 说明 |
|---|---|---|
| 4.1 全部新测试与旧自测复跑 | 已完成（收尾取证） | 受控环境（01-L05）加 R-01（`PYTHONPYCACHEPREFIX` 指向取证前为空的目录，依据是已归档的操作者记录）中按文件取证 10 次，只在 Windows 上：全部退出 0，`baseline_consistent=true`，前后输入清单闭包都是 `81b4503e…`；旧自测 256 checks / 0 failed，stdout 与实施前、最终取证逐字节相同；7 个跳过方法记 NOT_RUN（6）与 BLOCKED（1）。原件在 `.agent/baseline/01-closure/`，脱敏归档在 `evidence/closure/`，操作者记录在 `evidence/run-controls-closure/`。此前的 8 次最终取证（`evidence/final/`）保留为历史证据，其操作者记录已归档到 `evidence/run-controls-final/`；中间一轮 `.agent/baseline/01-P4/` 已被取代，不归档 |
| 4.2 A01–A16 验收映射 | 已完成（待独立复审） | [acceptance.md](acceptance.md) 第 0、3、4 节（第三次修订；第四次修订为勘误，不改判定）；A01、A07、A16 采用基线报告修订 6 的判定并写明成立的前提 |
| 4.3 平台矩阵 | 已完成 | [acceptance.md](acceptance.md) 第 5 节：只有 Windows 实测，Linux、macOS 全部 NOT_RUN |
| 4.4 保护范围与索引更新 | 保护范围：**已按选项二落实**；索引：01 设计文档已恢复为正确文件名并修复顶层索引 | 具体路径与机械拦截说明见 [acceptance.md](acceptance.md) 第 9 节 (a)(e)。02、03 的普通名索引链接留给各自阶段处理 |
| 4.5 多视角对抗复审与返工 | 部分完成 | 协议与 fixtures 已经多轮复审返工，收尾轮另有一轮复审返工（protocols-api.md 第 19 节）；基线报告修订 6、7 与 acceptance.md 第三、四次修订的独立复审待进行 |
| 4.6 交接检查（附录 D.3） | 已完成，有未完成项 | [acceptance.md](acceptance.md) 第 7 节：原 19 项中第 6、7、9、11、13–15、17–19 项已关闭，第 12 项（缺字段类样本仍缺）与第 16 项（凭据扫描已关闭，其余仍缺）部分关闭，第 1–5、8、10 项仍未关闭；收尾轮新增第 20–25 项（R-01 的证据等级与范围、G5 的读法、清单 (c) 类 23 行的登记方式、缺字段类样本、基线报告照录的同步） |
| 完整性审查返工（2026-09-26） | 已完成（只改文档） | 14 个问题逐条处理见 [acceptance.md](acceptance.md) 第 12 节；需要改代码或测试的部分当时登记为未完成项，已由收尾轮处理 |
| 对抗性核验返工（2026-09-26） | 已完成（只改文档） | 7 个 minor 问题逐条处理见 [acceptance.md](acceptance.md) 第 13 节 |
| 对抗性核验第二轮返工（2026-09-26，收尾轮之后） | 已完成（只改文档） | 8 个 minor 问题逐条处理见 [acceptance.md](acceptance.md) 第 15 节，没有改变任何判定：A02 方法归属的依据分两种写（6 个为规划端推断）；“fixture 中没有白名单放行”改记静态核对（新增 M-16：测试不断言放行结果为空）；操作者记录不再说与 capture.json“逐字段一致”；L-FINAL-OPERATOR、M-07 的关闭状态统一用词；3.13 的 `SEALING_LIMITATIONS` 条号；`evidence/closure/INDEX.md` 的证据等级写法与两处计数口径。改动：acceptance.md 第四次修订、基线报告修订 7、兼容矩阵修订 12、`evidence/closure/INDEX.md`（手写索引）与本文件；`legacy-inventory.md` 未改动 |
| **收尾轮（2026-09-26）** | 已完成（代码、测试、fixture 与文档；取证已归档；独立复审待进行） | 裁决：[decisions.md](decisions.md)“收尾轮裁决”R-01（A01 严格 pyc 口径）、R-02（A07 口径）、R-P3 勘误、R-P10–R-P12 与 R-P11 补充。代码与测试：`protocols.py`（R-P10、R-P11、M-01）、`tests/legacy_harness.py` 与 `tests/codekit01_legacy.py`（8.4 清理前归属核对）、`tests/test_codekit01_fixtures.py`（凭据扫描、R-P11、D-20–D-23、清理核对，现 75 项）、fixtures（manifest 新字段、D-20–D-23 新 case）。取证：10 次收尾取证（`evidence/closure/`）。文档：protocols-api.md、兼容矩阵修订 9–11、legacy-inventory.md 收尾轮更新、基线报告修订 6、acceptance.md 第三次修订（第 14 节）。新增归档目录：`evidence/closure/`、`run-controls-final/`、`run-controls-closure/`、`inventory-items/` |

## 总体结论

只限所述范围，与 [acceptance.md](acceptance.md) 第 0 节一致：01 的历史收尾取证在 Windows Server 2025 + CPython 3.12.10、HEAD `a4fa199` 加未提交工作区上完成；当前第一阶段代码基线为提交 `182ef16`，判定依据是 10 次收尾取证（R-01 严格 pyc 口径；受控禁用的依据只有操作者记录）。只看 Windows：

- A04、A05、A14、A16：PASS；
- A09：PASS，但 Draft 2020-12 元校验 BLOCKED（缺 jsonschema，未授权安装）；
- A01：PASS（R-01 严格口径，范围限定；输入闭包 partial）。成立的两个前提待规划端确认：不接受操作者记录作为 pyc 受控禁用的依据时为**不满足**；R-01 若也覆盖仓库外输入（标准库及其字节码、git、系统工具）则为 **FAIL**；
- A07：PASS（R-02，范围限定，带 `unmet_within_scope`：POSIX 取消、真实并发竞态、备注层等子分支，迁移比较时记 NOT_COVERED）。G5 的读法待规划端确认，若要求 G5 有可触发的失败断言则为 **FAIL**；
- A02、A03、A06、A08、A10–A13：只在 01 范围内 PASS，范围外部分 NOT_RUN，已移交 02、03、04、07、09、10，或归属模块未指定（A10 的生产级安全访问、A13 的崩溃持久性）。A02 在收尾取证中有了方法级证据，由“整项不记 PASS”改为“01 范围内 PASS”；文档 6.6 七类的新旧差分 NOT_RUN（新路径不存在），真实历史派遣证据 NOT_RUN（仓库中没有）；
- A15：只有 Windows 实测，整项不记 PASS。

Linux 与 macOS 全部 NOT_RUN；jsonschema 元校验 BLOCKED；A01、A07 的前提与其他未完成项见 [acceptance.md](acceptance.md) 第 7 节。这不是“01 全部通过”。

## 文件索引

- [decisions.md](decisions.md)：01-D01–D10、01-L01–L09、裁决 R-P1–R-P9（01-L08 总设计的交叉检查、01-L09 applicability 为完整性审查追加），以及“收尾轮裁决”R-01、R-02、R-P3 勘误、R-P10–R-P12 与 R-P11 补充
- [closure-rulings.md](closure-rulings.md)：acceptance.md 第 7 节第 20–23 项的最终口径（R-01 证据等级与范围、G5 的读法、旧自测 check 的内联引用写法）；为不牵动已登记摘要而单独存放
- [baseline-report.md](baseline-report.md) / [baseline-report.json](baseline-report.json)：基线报告，**修订 7**（实施前基线、实施后回归（历史）与收尾取证；A01、A07、A16 的判定来自修订 6，修订 7 是勘误；两者分歧时以 JSON 为准）。报告只判定 A01、A07、A16；其余 13 项由 acceptance.md 判定，JSON 中标 `judged_by_this_report=false`，“以 JSON 为准”不适用于这 13 项。JSON 照录的 13 项文字取自 acceptance.md 第三次修订之前的字节，与之不一致处以 acceptance.md 为准（acceptance.md 第 7 节第 25 项）
- [legacy-inventory.md](legacy-inventory.md)：旧行为清单、G0–G6、回归映射、3.2 两个字段的回填（第 9.10 节，收尾轮 9.10.5–9.10.7）、P4 特征化回归（第 12 节，收尾轮 12.10 的代码内联引用）
- [compatibility-matrix.md](compatibility-matrix.md)：兼容能力矩阵（修订 12；第 4.3 节 D-20–D-23，第 8 节缺样本与 R-P11 字段，第 9 节为 8.3 故障恢复与 8.4 清理的落点）
- [protocols-api.md](protocols-api.md)：公共协议接口说明（供 02–10 使用；第 19 节为规格澄清与各轮复审处理，含“收尾轮”“收尾轮返工”）
- [acceptance.md](acceptance.md)：01-A01–A16 验收映射、F001–F050、平台矩阵、G0–G6 最终表、交接检查与未完成项、给 02/03/04 合同的绑定清单、用户决策与剩余事项、minor 与剩余风险、完整性审查（第 12 节）与对抗性核验（第 13 节）的逐条处理、收尾轮验收收尾（第 14 节）、对抗性核验第二轮（第 15 节）
  - 当前字节（本轮提交状态修订后）：196879 字节，sha256 `7dba52af49c6343dd13c71fe38b56e60c83fc83317c970ba5d0c749b34c93a1e`（第三次修订后为 179796 字节 `c0d3c99d…`）。基线报告不内嵌这个摘要：acceptance.md 记录基线报告的摘要，互相内嵌会形成循环，所以记在这里
- `evidence/`：脱敏归档的取证证据与操作者记录（redact-v2；原件在被 Git 忽略的 `.agent/baseline/`，不提交）
  - `evidence/closure/`：**10 次收尾取证（当前依据）**，每个取证目录 84 个文件，索引见 [evidence/closure/INDEX.md](evidence/closure/INDEX.md)（手写索引，不是归档文件；对抗性核验第二轮更正过一次，见其第 9 节）
  - `evidence/run-controls-closure/`：收尾取证的操作者记录 `closure-captures.txt`（受控条件、R-01 的前缀目录、逐次汇总）与复制清单 `manifest.json`
  - `evidence/final/`：8 次最终取证（历史证据，被收尾取证取代，保留不改写），索引见 [evidence/final/INDEX.md](evidence/final/INDEX.md)
  - `evidence/run-controls-final/`：最终取证的操作者记录 `final2-captures.txt` 的正式归档与复制清单
  - `evidence/inventory-items/`：旧行为清单 6 个区域的结构化条目（`inventory-*.items.json`）与复制清单；条目中的“实测”“探针”是线索，不是运行证据
  - `evidence/bl-01t1-legacy-20260925/`：实施前基线
  - `evidence/reference-appendix-b-windows/`：附录 B 参考代码验证（与项目验证分栏，01-A16）
  - `evidence/run-controls/`：实施前基线的受控环境记录与离线边界静态核实
- 提交时 `docs/code-kit-v2/01-baseline/` 下的全部文件（含上面各个 evidence 子目录）都要纳入；工作区里还有不属于 01 的改动（根目录 README.md、`docs/` 下的文件重命名与设计文档），不能用 `git add -A`，逐路径暂存，见 [acceptance.md](acceptance.md) 第 9 节 (b)
