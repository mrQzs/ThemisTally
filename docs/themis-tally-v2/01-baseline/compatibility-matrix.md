# 01 兼容能力矩阵（P3.7）

> 本文保留修订 12 的历史矩阵。本轮已补齐两类缺字段样本并强化扫描：当前登记 190 项、目录 191 文件；旧判断 40 项零差异，stub 重生成 10 项零差异。当前差异见 [fixture-completion.md](fixture-completion.md)，最终判定见 [completion-review.md](completion-review.md)。


- 依据：01 审阅增强版 1.3、8.1–8.4、附录 D.2（8.1 见第 2 节，8.2 见第 6 节，8.3 与 8.4 的逐行落点见第 9 节，修订 8 补；仓库文件名因编码显示为 `01-baseline-and-protocols-╔≤╘─╘÷╟┐░µ.md`，修订 `review-expanded-2026-09-25`）；决策 01-D02、01-D07、01-D08、01-D09、01-D10（[decisions.md](decisions.md)）。
- 基线：HEAD `a4fa199b0e5bdc658215765ee7558b9fe6723940`（sha1 对象格式）。
- 输入材料：`tests/fixtures/codekit01/manifest.json`、`expected/` 下三份预期文件、`tests/test_codekit01_fixtures.py`、[protocols-api.md](protocols-api.md)、[legacy-inventory.md](legacy-inventory.md)。
- 状态：修订 12（对抗性核验勘误），2026-09-26。本文只记录本次实际结果与已登记的处理决定，不是验收结论（验收见 `acceptance.md`）。
- 修订 2 的变化：按复审意见更正第 2 节中“拒绝”“支持”用词不符 0.1 定义的格子与计数口径，更正结论摘要第 3 条的范围；同步 P3 返工后的测试结果（新增测试层能力声明规则、差分测试与实现字节门禁拆开、默认测试重跑 stub、取不到 git 时默认失败）。
- 修订 3 的变化（P4）：产品入口的能力声明规则改为按来源类别与表示作用于全部条目（fixtures 复审 major 的协议层根因），第 2 节“stub 生成的旧事件流”“合成 fixture”两行与依据 E12、E13 随之改为产品入口“拒绝”；manifest 重新生成（169 条，协议负例 122 个，生成修订 `codekit01-protocol-fixtures-v3`）；同步 P4 的测试结果、裁决 R-P1–R-P8 带来的版本轴变化（维度规则 v2），并更正依据索引中的源码行号。legacy 预期文件没有变化。
- 修订 4 的变化（P4 第 3 轮，第 3 轮协议复审返工，逐条处理见 protocols-api.md 第 19 节“P4 第 3 轮”）：产品入口的能力声明改为封闭词法（`[a-z][a-z0-9_]{0,127}`，大小写与连字符变体在结构层报 `E_SCHEMA_FIELDS`/`claim_syntax`），清单级拒绝负例从负例派生（`negative_must_derive_from_valid_sample`），vendor 事件的 role 必须非空（`vendor_event_requires_role`），静态解析与封存逐跳核对链接链，8.3 短名形态的前缀允许含 `~`；第 2 节“stub 生成的旧事件流”“本次新增公共记录 v1”“合成 fixture”三行随之更新。manifest 重新生成（171 条，协议负例 124 个，生成修订 `codekit01-protocol-fixtures-v4`：新增 2 个负例，5 个已有负例的期望 reason 或 field 随协议改动更新，已有负例字节不变）；`expected/legacy-new-strict.json` 中两条文法错误的 reason 由带行列号改为固定的 `syntax_error`（该文件以当前 protocols.py 重算）；两份 legacy 预期文件没有变化。同步测试结果与依据索引中的源码行号。
- 修订 5 的变化（P4 第 4 轮，第 4 轮协议复审返工，逐条处理见 protocols-api.md 第 19 节“P4 第 4 轮”）：逐跳核对链接链在 Windows 上按词法折叠相对目标文本中的 `.` 与 `..`（该轮对逐字绝对目标也做了折叠，修订 6 起改为失败关闭），并按逐字路径（`\\?\`）访问名称，展开终点必须与 resolve 结果相同；`usage_view` 第 5b 步把 provider 已知、与 provider 为 null 的观测同号的有效链尾一并纳入判定。第 7 节“symlink/junction 静态越界检查”一行随之更新。fixture 不受影响，没有重新生成：manifest 与三份 expected 的摘要不变，`python tests/codekit01_legacy.py --check` 仍为 `32 checks, 0 differ`。同步了测试结果，以及依据索引中 `protocols.py` 第 1018 行之后的源码行号：`_check_link_hops` 一带增加约 80 行，`usage_view` 第 5b 步增加约 11 行。
- 修订 6 的变化（P4 第 5 轮，裁决 R-P9 落实与第 5 轮协议复审返工，逐条处理见 protocols-api.md 第 19 节“P4 第 5 轮”）：业务路径的物理检查按 R-P9 定位为“静态审阅 + 纵深防御”，不是安全访问保证；逐跳核对对未识别的名称代理类重解析点（`link_kind_unsupported`），以及只有根、没有盘符的目标、不带逐字前缀的盘符绝对路径、逐字绝对目标中的 `.`/`..`/空分段一律失败关闭；`usage_view` 第 5b 步按成员判定登记账单号（链尾为 unknown 的链也登记其已知成员）。第 7 节“symlink/junction 静态越界检查”一行随之更新。fixture 不受影响，没有重新生成：manifest 与三份 expected 的摘要不变，`python tests/codekit01_legacy.py --check` 仍为 `32 checks, 0 differ`，`--check-stub-regen` 仍为 `10 checks, 0 differ`，`test_codekit01_fixtures.py` 的生成器一致性检查通过。同步了测试结果，以及依据索引中 `protocols.py` 的全部源码行号：模块说明增加 3 行，路径检查一带（`PATH_REVIEW_LIMITATIONS`、`_link_target_text`、`_split_link_target`）增加约 63 行，`usage_view` 第 5b 步增加约 15 行。
- 修订 7 的变化（P4 第 5 轮核验后续，处理见 protocols-api.md 第 19 节“P4 第 5 轮”末尾的“第 5 轮核验的后续处理”）：只改文档措辞与测试，`protocols.py`、`sealing.py` 不变，依据索引中的源码行号不变。修订 5 一条与第 7 节“symlink/junction 静态越界检查”一行把词法折叠限定为相对目标；第 1 节的 `test_protocols.py` 结果同步为本次运行（新增措辞检查用例 1 个）。fixture 不受影响，没有重新生成；两条 legacy 核对命令的结果仍是修订 6 的记录，本次没有改动它们依赖的文件。
- 修订 8 的变化（完整性审查返工，2026-09-26，只改文档，代码、测试、fixture 与预期文件都没有改动）：新增第 9 节，逐行给出 8.3 故障恢复决策表的落点，并登记 8.4 各清理代码是否核对归属；第 8 节增加第 9 条（文档 6.6 要求的选样类别中缺样本的清单）与第 10 条（fixture 条目结构缺少的规定字段），更正第 3 条漏写的“来源是否可追溯”，并把已过时的第 6 条标为已更正；第 6.1 节补上 P4 新增的 4 个特征化测试文件与公共夹具、`.gitattributes` 的第三条 `-text` 规则、`.agent/baseline/01-final/` 与 `01-P4/` 两个取证原件目录；第 6.2 节更正 AGENTS.md 一行（P4 没有修改 AGENTS.md）；第 6.3 节第 3、4、7 步随之更新。第 1 节的命令结果仍是修订 6、7 的记录，本次没有重跑。
- 修订 9 的变化（收尾轮，依据 decisions.md“收尾轮裁决”的 R-P10、R-P11、R-P12 与 acceptance.md 第 10 节 M-03、M-04、R-12；本轮改了 `tests/codekit01_legacy.py`、`tests/test_codekit01_fixtures.py`、fixture 与预期文件，`protocols.py` 的接口变更由另一位实施者完成，见 protocols-api.md 第 19 节“收尾轮”）：
  - **R-P11 新字段**：manifest 全部条目填写 integrity、platform_scope、capture、redaction.protocol_structure_preserved、origin.traceable，登记规则见第 8 节第 10 条；manifest 重新生成（188 条，生成修订 `codekit01-protocol-fixtures-v5` 与 `codekit01-legacy-fixtures-v2`）。两个基样本（C.1 补齐条目、legacy stub 条目副本）随之增加新字段，从它们派生的 15 个 fixture-manifest 类负例字节改变（变换与期望不变）；新增 11 个针对新字段与新规则的负例。其他负例、legacy 原字节与 stub 事件字节不变。
  - **D-20–D-23 落为 fixture**（M-04）：新增 6 个合同单一故障负例，旧判断由 a4fa199 的旧实现生成、进入 `expected/legacy-contracts.json` 的新用例，新严格入口的判断进入 `expected/legacy-new-strict.json`；已有 16 个合同用例与 13 个事件用例的投影逐字节不变（与改动前备份逐用例比较），`legacy-events.json` 整个文件字节不变。第 4.3 节改写；第 0.2 节第 3 条随之更正。
  - **第 1 节抽查写成回归测试**（M-04）：`PublicEntryRejectionTests`。
  - **fixture 凭据扫描**（文档 8.3）：`CredentialScanTests`，第 9.1 节对应行更新。
  - **递归删除的归属核对**（文档 8.4，R-12）：`tests/codekit01_legacy.py` 的 `_rmtree` 删除前核对归属，`tests/test_codekit01_fixtures.py` 不再用无核对的 `TemporaryDirectory`；第 9.2 节更新。`tests/legacy_harness.py` 的 `remove_tree` 不在本部分的范围（修订 10 更正：同一轮由另一位实施者改为核对归属，即 `make_temp_area` 建区域并写所有权标记、`remove_tree` 删除前做五项核对，本条原写“仍不核对”与当时的代码不符；回归测试在修订 10 补上，见 E23）。
  - **R-P12**：第 8 节第 9 条的七类改为“旧路径已锁定，差分 NOT_RUN（新路径不存在）”，并写出代码内联 fixture 的引用形式。
  - 第 1 节命令结果与数据文件摘要按本轮运行更新；依据索引中 `protocols.py`（第 1300 行之后，收尾轮的接口变更使其后移）、`sealing.py`、`baseline.py` 与两个测试文件的源码行号按当前字节重新核对。
- 修订 10 的变化（收尾轮返工，逐条处理见 protocols-api.md 第 19 节“收尾轮返工”；改了 `protocols.py`、`tests/test_protocols.py`、`tests/test_codekit01_fixtures.py`，`tests/legacy_harness.py`、`tests/codekit01_legacy.py`、fixture 与预期文件的字节都没有改，fixture 不需要重新生成）：
  - **R-P11 第 5 步改按受控词表判定**：complete_run、run_stream_complete、full_event_log、field_semantics 等同义名称此前能绕过只看前缀的规则，现在同样拒绝；词表外的写法不受限制。第 2 节“合成 fixture”一行、第 8 节第 10 条、E18 随之更新。
  - **凭据扫描由 9 条规则增加到 15 条**，并如实列出覆盖的形态（第 9.1 节“fixture 含真实凭据”一行、E19）；修订 9 对缺口的描述低估了缺口，已更正。
  - **harness 的归属核对**：修订 9 第 19 行、第 9.1 节“临时目录归属不明”一行、第 9.2 节 harness 一行把 `tests/legacy_harness.py` 的 `remove_tree` 记为“不核对”，与当时的代码不符（同一轮已由另一位实施者加入核对），改为“已核对”并更新行号；回归测试 `HarnessCleanupOwnershipTests` 为本修订新增（新依据 E23）。
  - `CleanupOwnershipTests` 补三项断言（E22）；`CompatMatrixDCaseTests` 反向核对 D-xx 映射表的完整性（E21）。
  - 第 1 节命令结果按本修订的运行更新；依据索引中 `protocols.py` 第 3264 行之后与 `tests/test_codekit01_fixtures.py` 的源码行号按当前字节重新核对。
- 修订 11 的变化（收尾取证之后，由基线报告修订 6 的编写者更新；**只改取证引用、测试计数与 `protocols.py` 行号，不改任何兼容结论**；代码、测试、fixture 与预期文件都没有改动，没有运行任何被测命令）：
  - **取证引用**：规划端按 R-01 严格 pyc 口径做了 10 次收尾取证（`bl-01closure-*-20260926`，归档在 `evidence/closure/`，索引 [evidence/closure/INDEX.md](evidence/closure/INDEX.md)）。第 1 节新增“收尾取证”表，把第 1 节 6 条命令逐条对到归档输出的路径与 sha256；第 9 节证据列补上收尾取证的编号（EV-C02、EV-C04、EV-C08）；第 6.1、6.3 节补上 `.agent/baseline/01-closure/` 与 `evidence/closure/`；依据 E01、E03、E06、E20 补上收尾取证的结果与行号。
  - **acceptance.md M-06 已关闭**：第 1 节两条 `codekit01_legacy.py` 命令（`--check`、`--check-stub-regen`）现在有归档输出（`bl-01closure-legacy-check-20260926`、`bl-01closure-legacy-check-stub-regen-20260926`），计数与第 1 节记录一致（38/0、10/0）。
  - **测试计数**：收尾取证的计数与第 1 节记录一致（`test_protocols.py` 342 项、跳过 4 项；`test_codekit01_fixtures.py -v` 75 项；`test_legacy_gates.py` 24 项；`test_legacy_events.py` 34 项），第 1 节原表不改。E20 补记：`test_baseline_records_are_internal` 按目录现场查找 `evidence/` 中的记录，收尾取证时读到的是 9、18、18、9 份；`evidence/closure/` 在取证之后才归档，之后再运行会读到 19、38、38、19 份（本修订没有运行，未核对）。
  - **`protocols.py` 行号**（按当前字节核对，sha256 `64d75bb0a5b37a5dd93240eac3f58455538a12e58c91b324a72b3d14708bc42b`，3634 行，与收尾取证输入清单记录的字节相同）：依据索引中 `protocols.py` 的全部行号逐个核对，改了三处：E09 `build_default_registry` 由 1513-1535 改为 1513-1539（R-P10 给每个类型加了三项声明）；E09 `_validate_ref` 由 1571-1584 改为 1571-1583（原范围多含一个空行）；E18 受控词表常量与判定函数由 3264-3328 改为常量 3268-3294、函数 3297-3327（3264 是 `PLATFORM_SCOPE_ANY`，不属于词表）。其余行号与当前字节一致。其他文件的行号本修订没有改动。
- 修订 12 的变化（对抗性核验返工，2026-09-26，由规划端子代理更新；**只改一处证据等级的写法与一处索引摘要，不改任何兼容结论**；代码、测试、fixture 与预期文件都没有改动，没有运行任何被测命令）：
  - **E19 与第 9.1 节“fixture 含真实凭据”一行**：修订 9–11 写“本次没有命中，也没有白名单放行”，把两件事都记成运行结果。`CredentialScanTests.test_fixture_files_contain_no_credential_shapes` 调用 `scan_bytes_for_credentials` 后丢弃白名单放行结果（`found, _allowed = …`，`tests/test_codekit01_fixtures.py:2636`），只在非白名单命中不为空时失败（:2643-2646），所以收尾取证 EV-C08 第 21 行的 ok 只证明“没有非白名单命中”。“没有白名单放行”改记为静态核对（source_inspected）：修订 12 在 189 个文件的原字节、UTF-16 LE/BE 两种对齐的解码视图与能解析的 JSON/JSONL 字符串中，不区分大小写查找三个白名单标记（`DEMO_REVIEW_SECRET`、`DEMO_TOKEN_FOR_REVIEW`、`SYNTHETIC_*CREDENTIAL`），0 处；白名单只放行整串匹配这些标记的值，由此推断扫描中没有放行任何值。要把它变成运行结论，需要在测试中断言放行结果为空后重新取证（acceptance.md 第 10 节 M-16，归 01 测试的后续返工）。结论本身（fixture 中没有凭据形态）不变。
  - **收尾取证索引的摘要**：第 1 节“收尾取证”一段引用的 `evidence/closure/INDEX.md` 经同一轮勘误更新（证据等级写法、第 1 节两列的来源标注、7.1 节计数口径与 2.2 节补核，归档文件未改），摘要改为新字节（修订 11 引用的是 44858 字节，`a6a84822…`）。

## 0. 读法与结论摘要

### 0.1 格子里的词

| 词 | 含义 |
|---|---|
| 支持 | 有实现，并有测试或 fixture 证据 |
| 拒绝 | 有实现，按稳定错误码拒绝，并有测试或 fixture 证据 |
| 只读 | 只保留原字节或按旧规则审计，不产生新判断，也不授予新能力 |
| 不适用 | 该能力对这类输入没有意义 |
| 未实现 | 01 没有提供；括号里写归属模块 |

- 同一格同时涉及旧入口与新入口时，分别写“旧：”“新：”。
- “旧入口”指未改动的 `scripts/pi_dispatch.py`（TOOL_VERSION 2.2.2）。“新入口”指 01 新增的 `scripts/codekit/protocols.py` 与 `sealing.py` 中的校验函数。
- “新执行入口”指 Code-Kit v2 将来的派遣与运行入口（04 适配器、07 调度、09 合同发布）。01 没有实现任何新执行入口：
  - 写“拒绝”的格子，表示 01 的协议函数在路由或校验层已经拒绝；
  - 写“未实现”的格子，表示没有入口可测。
- 方括号 `[E01]` 等指第 3 节的依据索引。

### 0.2 结论摘要

1. **旧入口没有改动**。`scripts/pi_dispatch.py` 当前 sha256 `a00d6934…3ad4` 与基线取证清单中的记录相同，git blob 与 HEAD 相同。HEAD 中没有任何文件引用 `codekit`（第 6.2 节）。
2. **新入口只覆盖 JSON 层和公共记录 v1**。01 不对合同 v1 做新的字段语义判断，这一缺口归 09。所以“新严格入口接受”不等于“合同合法”。
3. **在 fixture 中，“旧接受、新严格入口拒绝”有两条**：JSON 顶层重复键且先出现的值与 Markdown 不一致（D-01）；cost 金额为 `Infinity`（D-20，收尾轮落为 fixture：旧实现进程内 0 个错误，新严格入口报 `E_JSON_NON_FINITE`）。D-23（setup 标识末尾带换行）旧实现接受，新严格入口只判断 JSON 层，**同样接受**；新协议的标识规则（fullmatch，`E_ID_SYNTAX`）只作用于公共记录中的标识，不作用于合同 v1（第 4.3 节）。BOM 开头的 JSON 合同在旧入口同样被拒绝，只是错误表示不同（D-03）。
4. **历史只读能力不是派遣许可**（8.1）。已知家族的未知版本、未知资源类型、未登记事件类型，在路由和校验层都被拒绝，不降级、不回退 v1。
5. **只有 Windows 实测**。Linux、macOS 为 NOT_RUN。旧预期中的 Python 报错原文只在 Python 3.12.10 上锁定。

## 1. 本次核对的命令与原始结果（Windows）

环境：Windows Server 2025 Standard 10.0.26100，Python 3.12.10，git 2.55.0.windows.5；设置了 `PYTHONDONTWRITEBYTECODE=1`，并按裁决 R-01 设 `PYTHONPYCACHEPREFIX` 指向运行前新建的空 tempfile 目录（运行后其中没有任何文件，目录已删除）。

修订 10（收尾轮返工）由实施者在仓库中直接运行，不是 `baseline.py capture` 取证，输出没有归档；要把结论绑定到这些字节，须按 01-L05 与 R-01 重新取证。修订 9 的结果（`test_codekit01_fixtures.py` `Ran 61 tests` / `OK`，`test_protocols.py` `Ran 341 tests` / `OK (skipped=4)`，两条 legacy 核对命令同下）被本表取代。

| 命令 | 结果原文 |
|---|---|
| `python tests/test_protocols.py` | `Ran 342 tests in 4.470s` / `OK (skipped=4)`（跳过项不变：F017、F029、F030 与 jsonschema 元校验；新增 1 个测试） |
| `python tests/test_codekit01_fixtures.py -v` | `Ran 75 tests in 14.832s` / `OK`（75 个方法各输出一行 `... ok`，没有跳过项；新增 14 个：`HarnessCleanupOwnershipTests` 11 个、`CleanupOwnershipTests` 3 个。文件符号链接在本机可以创建，两处链接用例都实际运行） |
| `python tests/codekit01_legacy.py --check` | `38 checks, 0 differ`（6 项 legacy 副本与 a4fa199 的 blob 相同、6 项工作区来源文件与该 blob 相同、22 项负例派生（合同 19，其中 D-20–D-23 6 项；事件 3）、三份 expected 与 manifest 中的 legacy 条目各 1 项，都是 SAME；本修订没有改动它依赖的文件） |
| `python tests/codekit01_legacy.py --check-stub-regen` | `10 checks, 0 differ` |
| `python tests/test_legacy_gates.py` | `Ran 24 tests in 185.077s` / `OK` |
| `python tests/test_legacy_events.py` | `Ran 34 tests in 80.694s` / `OK` |

`test_codekit01_fixtures.py` 中依赖 git 或提交 a4fa199 的检查（`FileIntegrityTests` 的两项 git 检查、`LegacySourceTests` 两项、`DifferentialTests` 中需要在临时仓库运行旧 CLI 的两项）在取不到 git 或 a4fa199 时**默认判为失败**（01-A02：未取得旧结果不通过）。只有显式设置 `CODEKIT01_ALLOW_NOT_RUN=1` 时才跳过，跳过项记为 NOT_RUN，不算通过。本次在仓库中运行，没有设置该变量，也没有跳过项。

**收尾取证（修订 11 补）**：上表是实施者的仓库内运行，仍然没有归档。规划端随后在受控环境（01-L05）中按 R-01 严格 pyc 口径，用 `baseline.py capture` 把这 6 条命令连同另外 4 条（旧自测、`test_baseline_tool.py`、`test_legacy_lifecycle.py`、`test_legacy_cli.py`）逐条取证，归档在 `evidence/closure/<取证 ID>/`（索引 [evidence/closure/INDEX.md](evidence/closure/INDEX.md)，48511 字节，sha256 `85ae818f8a5de0b42cf0568b2a5b5205752012e9340519013c12a3706718f0ba`；修订 12 更新为勘误后的字节，修订 11 引用的是 44858 字节 `a6a84822…`）。10 次取证都是 HEAD `a4fa199…`、退出码 0、没有超时、`baseline_consistent=true`、drift 为空，取证前后输入清单闭包都是 `81b4503e291166fd78632aab9163faac2f0e25c92db11c691dfbe753068f52a4`（1073 项）。下表的计数与上表一致；行号从 1 起算：

| 命令 | 取证 ID | 结果原文（归档文件:行） | 归档输出（相对本目录，字节，sha256） |
|---|---|---|---|
| `python tests/test_protocols.py` | `bl-01closure-test-protocols-20260926` | `Ran 342 tests in 4.291s`（run/stderr.bin:687）/ `OK (skipped=4)`（:689）；逐条 338 个 ok，跳过 4 个（F017、F029、F030 记 NOT_RUN，jsonschema 元校验记 BLOCKED） | `evidence/closure/bl-01closure-test-protocols-20260926/run/stderr.bin`，77955，`5b81e659c60f296503dd99e836a938fa45134ffe597fb960a204b56ee65354c8` |
| `python tests/test_codekit01_fixtures.py -v` | `bl-01closure-test-codekit01-fixtures-v-20260926` | `Ran 75 tests in 11.260s`（run/stderr.bin:105）/ `OK`（:107）；75 个方法逐条 ok，没有跳过（方法名与行号见 INDEX.md 4.3 节） | `evidence/closure/bl-01closure-test-codekit01-fixtures-v-20260926/run/stderr.bin`，13127，`95faa68cea9315a4a73cc4bfc4223916e56b8eb1b9e5694fa1415fdf1c8b169a` |
| `python tests/codekit01_legacy.py --check` | `bl-01closure-legacy-check-20260926` | 第 1–38 行都以 `SAME` 开头，`38 checks, 0 differ`（run/stdout.bin:39），没有 `DIFF` 行 | `evidence/closure/bl-01closure-legacy-check-20260926/run/stdout.bin`，3712，`2a06d6b3069d23cbb24649983cbced3770476d7b5a3fdf16e751dea94580f5d2` |
| `python tests/codekit01_legacy.py --check-stub-regen` | `bl-01closure-legacy-check-stub-regen-20260926` | 第 1–10 行都以 `SAME stub regen` 开头，`10 checks, 0 differ`（run/stdout.bin:11） | `evidence/closure/bl-01closure-legacy-check-stub-regen-20260926/run/stdout.bin`，273，`9a942083ceece639e010b0771c7c2f0efd68470d40f8cd72766d76d63de1a785` |
| `python tests/test_legacy_gates.py` | `bl-01closure-test-legacy-gates-20260926` | `Ran 24 tests in 128.419s`（run/stderr.bin:52）/ `OK`（:54） | `evidence/closure/bl-01closure-test-legacy-gates-20260926/run/stderr.bin`，6459，`97af8357a3730e301a70d6890bfc1d1463186590d25f4db15d7348ea938138f6` |
| `python tests/test_legacy_events.py` | `bl-01closure-test-legacy-events-20260926` | `Ran 34 tests in 51.774s`（run/stderr.bin:71）/ `OK`（:73） | `evidence/closure/bl-01closure-test-legacy-events-20260926/run/stderr.bin`，8739，`e5cfa16608d66529963a69a7a10236c294873692b3efe19f5773b0c6bbe70166` |

- 各取证的 `archive-manifest.json`、`capture.json` 与另外 4 次取证的结果见 INDEX.md 第 1–3 节与基线报告第 13 节。
- 取证时被测文件的字节以收尾取证输入清单为准，例如 `scripts/codekit/protocols.py` `64d75bb0…`、`tests/test_protocols.py` `b0d354a1…`、`tests/test_codekit01_fixtures.py` `16b71bca…`、`tests/codekit01_legacy.py` `f1d20836…`、`tests/legacy_harness.py` `c4e87137…`、`tests/fixtures/codekit01/manifest.json` `95c58a9b…`；下表三份 expected 的摘要与该清单记录的相同。上表的仓库内运行是否用的是同一批字节，本文没有记录，不能据此推定。
- R-01 的受控禁用（`PYTHONPYCACHEPREFIX` 指向取证前为空的目录）只有操作者记录（`evidence/run-controls-closure/closure-captures.txt` 第 4、6 行），取证工具没有记录该变量，见 INDEX.md 5.3 节。
- 这些归档只证明所列命令在记录的环境与时刻得到所列输出，只限 Windows；跳过的用例没有运行，不算通过。

本文引用的数据文件摘要（sha256，编写时测得）：

| 文件 | sha256 | 说明 |
|---|---|---|
| `tests/fixtures/codekit01/manifest.json` | `95c58a9b5a68166e104ee8a719385d43a8f346bff96ab96806518d6c94a830e0` | 188 条（收尾轮按 R-P11 的新结构重新生成；修订 8 及以前为 171 条，sha256 `50dc2fc3…`），`validate_fixture_manifest_set`、`validate_resource_payload`（kind fixture-manifest）与测试层 `check_manifest_claims` 都通过 |
| `tests/fixtures/codekit01/expected/legacy-contracts.json` | `5328bb62721095f07ac48350c53aa74e6a0e8dc64440ab15a713c618fc866ed0` | 旧实现合同投影，22 个用例（收尾轮新增 D-20–D-23 的 6 个；原 16 个用例的投影逐字节不变，文件头的 `projection` 说明增加非有限数的表示与 traceback 的出现情况；修订 8 及以前为 `71613d00…`） |
| `tests/fixtures/codekit01/expected/legacy-events.json` | `e889fef038d674d155a8b5cbb1403e07a8a469b36e9b8c8eec0ff44eba34973b` | 旧实现事件投影，13 个用例 × 3 种 expects_settled（收尾轮没有变化） |
| `tests/fixtures/codekit01/expected/legacy-new-strict.json` | `e936407998da7042596c68223cbb9fbfb6c94409e258a6ae9888a832be71af82` | 新严格入口预期：18 份 JSON 文档（收尾轮新增 5 份）、13 条 JSONL 流；原有判断逐字节不变（修订 8 及以前为 `bf7f8ad4…`） |

另外做过一次**抽查**（修订 2 起记录，进程内、只读）。收尾轮已把它写成回归测试 `PublicEntryRejectionTests`（acceptance.md M-04），第 3 节依据 E20：

- 把 `legacy/contracts/` 下 3 份 JSON 合同交给 `validate_public_record(expected_record_type="run-context")`，结果为 `E_SCHEMA_RECORD_TYPE`（`/record_type`，`record_type_mismatch`）；交给 `route_public_record(expected_record_type="contract")`，结果为 `E_COMPAT_UNSUPPORTED`（`record_type_unsupported`）；
- `manifest.json` 交给 `route_public_record(expected_record_type="fixture-manifest-set")`，结果为 `E_COMPAT_UNSUPPORTED`；交给 `validate_public_record(run-context)`，结果为 `E_SCHEMA_RECORD_TYPE`；把它的 schema_version 改成 2 后交给 `validate_fixture_manifest_set`，结果为 `E_SCHEMA_VERSION_UNSUPPORTED`，输入不被改写；
- 归档 `evidence/` 中全部 `capture.json`（9 份）、`input-manifest.json`（18 份）、`environment.json`（18 份）、`archive-manifest.json`（9 份）：
  - 都被 `strict_json_loads` 接受，record_type 依次为 baseline-capture、baseline-input-manifest、baseline-environment、baseline-archive-manifest；
  - 按自身 record_type 交给 `route_public_record`，结果为 `E_COMPAT_UNSUPPORTED`；
  - 交给 `validate_public_record(run-context)`，结果为 `E_SCHEMA_RECORD_TYPE`；
  - 每次调用前后输入的固定序列化相同。
- 修订 8 的抽查还包括 `.agent/baseline/` 中的取证原件。原件被 Git 忽略，回归测试不依赖它，只用入库的脱敏归档；原件没有再核对。

## 2. 能力矩阵

| 输入类型 | 本次实例 | 读取/审计 | 校验 | 新执行入口 | 审核 | 集成 | 平台 |
|---|---|---|---|---|---|---|---|
| **已支持且来源完整的 v1 历史合同/证据** | 6 个合同 fixture：plan-task 技能示例 2 对、合同模板 1 对，均为 a4fa199 原字节，base_sha 为虚构值。**真实历史派遣证据没有**：`.agent/plans/` 为空，仓库中没有 `.agent/runs/` | 支持（旧规则）：按旧实现读取与规范化，投影已锁定 [E01][E02] | 旧：支持，未改动 [E01][E16]<br>新：只做 JSON 层，3 份 JSON 都接受 [E04]<br>合同 v1 字段语义的新校验：未实现（09） | 未实现：01 没有新执行入口；执行仍只走旧 `run`，未改动 [E16] | 旧：verdict 入口未改动<br>新：只读，`build_run_dimensions` 原样保留 legacy_verdict [E15]<br>新审核：未实现（03） | 旧：未改动<br>新：只读，integration_observation 原样保留 [E15]<br>新集成：未实现（12） | Windows 实测<br>Linux/macOS NOT_RUN<br>真实历史证据：无此类输入 |
| **stub 生成的旧事件流** | 10 条（`tests/stub_pi.py` @ a4fa199，Windows 生成，CRLF 行尾），另有 3 条派生负例 | 支持（旧规则）：`summarize_events` 的投影按 expects_settled 为 true、false、null 三种锁定 [E03] | 新：原始流的读取与完整性判断未实现（04）。测试辅助函数 `tests/codekit01_legacy.py::new_strict_jsonl_verdict` 逐行调用 `strict_json_loads`，不是产品入口；10 条原始流的所有行都被接受 [E04]<br>转成 run-event：不适用（原始流没有 schema_version 和 record_type；映射归 04，01-D07） | 拒绝作为厂商证据（产品入口，P4）：条目在 proves 中声称 real_cli_compatibility、vendor_protocol 或 real_/vendor_ 前缀的能力时，`validate_fixture_manifest_entry` 报 `E_PROVENANCE_CLAIM`（`/proves`，reason `real_compatibility_claim_requires_captured_raw`；只有 captured + captured_raw/redacted_raw 可以声称）。声明的大小写或连字符变体（例如 `REAL_CLI_COMPATIBILITY`）在结构层即报 `E_SCHEMA_FIELDS`（`/proves/<i>`，reason `claim_syntax`；P4 第 3 轮）。条目的 does_not_prove 另写 legacy_end_to_end_run、cross_platform_bytes；声称白名单之外的 legacy_ 能力由测试层规则 `check_synthetic_fixture_claims` 拒绝（产品入口接受 legacy 类的 legacy_ 能力）[E12]<br>消费入口：未实现 | 旧：G1 按 `summarize_events` 的 problems 判定，未改动 [E17]<br>新审核：未实现（03） | 不适用 | Windows 实测（CRLF 字节只在 Windows 生成）<br>Linux/macOS NOT_RUN |
| **本次新增公共记录 v1** | run-context、run-event（core 与 vendor）、usage-observation、ResourceRef、结构化错误。<br>合成正例 8 个：run-context 1、run-event 2（core、vendor）、usage-observation 2、ResourceRef 1、sample-1 字节 1、结构化错误 1。<br>相关协议负例 107 个：run-context 16、run-event 31、vendor-event 9、resource-ref 20、usage-unknown 13、usage-cost 17、error-record 1；另有 sample-1 字节摘要不符 2 个（synthetic-sample）。<br>计数见 `NegativeTests.test_negative_counts_by_group`。synthetic 类的其余 5 条（C.1 manifest 条目、C.2 黄金向量、原始分段、legacy stub 条目副本、`expected/legacy-new-strict.json`）与 manifest 负例 26 个（fixture-manifest-entry 22、fixture-manifest-claims 4；收尾轮由 11 + 4 增加）不属于公共记录，见“合成 fixture”与“01 内部记录”两行 | 支持：先 `strict_json_loads`，再 `validate_public_record`、`validate_resource_ref` 或 `verify_resource_bytes` [E05] | 支持：结构校验加部分语义检查，报告中列出 `semantic_checks_skipped` [E05][E06]；vendor 事件的 role 必须非空（P4 第 3 轮，`negative-protocol-vendor-event-role-null`）<br>结构化错误：只由 `ProtocolError.to_record()` 生成，没有校验外部错误记录的函数（未实现）<br>把合同 v1 当公共记录：拒绝，`E_SCHEMA_RECORD_TYPE` 或 `E_COMPAT_UNSUPPORTED` [E07] | 未实现：没有消费者。`validate_run_context(for_executor_dispatch=True)` 只检查字段非空与 role 为 executor（P4），不是派遣入口（04/07/09） | 未实现（03） | 未实现（12） | Windows 实测<br>Linux/macOS NOT_RUN |
| **已知家族、未知版本** | codekit-public 的 schema_version=2（3 个负例）；fixture-manifest-set v2（收尾轮写成回归测试 [E20]）；合同 schema_version=2（没有 fixture） | 只读：校验不修改输入，原字节可以按摘要保存 [E08]<br>专门的待升级存放区：未实现 | 新：拒绝，`E_SCHEMA_VERSION_UNSUPPORTED`，不删字段回退 v1 [E08]<br>旧：合同 v2 报“schema_version 必须为 1”（`scripts/pi_dispatch.py:1459-1460`，源码核对，没有测试断言） | 拒绝（路由层）[E08] | 新审核：未实现（03）<br>旧审核：不读取公共记录 | 不适用 | Windows 实测<br>Linux/macOS NOT_RUN |
| **未知资源类型** | 未登记 kind 的 ResourceRef 与 evidence_refs；manifest 中 resource.kind 不是 fixture；未登记的事件类型；不在公共家族中的记录类型 | 未实现隔离保存：`seal_bytes`、`read_sealed` 对未登记或非文件型的类型报 `E_RESOURCE_KIND` [E09]<br>注册表是静态的，不加载远程 Schema | 拒绝：<br>- 资源类型 `E_RESOURCE_KIND`<br>- 事件类型 `E_EVENT_TYPE_UNKNOWN`<br>- 记录类型 `E_COMPAT_UNSUPPORTED`<br>[E09][E07] | 拒绝 [E09] | 不适用 | 不适用 | Windows 实测<br>Linux/macOS NOT_RUN |
| **重复键/歧义的历史记录** | `negative-legacy-contract-json-duplicate-key-first-differs`、`-last-differs`；同类歧义见第 4 节 D-03 至 D-06、D-12、D-13；收尾轮落为 fixture 的 D-20–D-23（非有限金额、深层嵌套、非 UTF-8、标识末尾换行，6 个，第 4.3 节）[E21] | 只读：原字节与已核实的旧解释（后出现的键生效）已锁定 [E01][E04] | 旧：first-differs 静默通过（0 个错误）；last-differs 只因 Markdown 与 JSON 不一致而报错<br>新：拒绝，`E_JSON_DUPLICATE_KEY`，field 为 `/risk_level` [E04][E10] | 新：拒绝，没有 legacy 放行开关 [E10]<br>旧 `run` 入口仍按旧规则使用这类输入（已登记风险 D-01，未做端到端验证） | 新审核：未实现（03）<br>旧审核：沿用旧解释 | 新集成：未实现（12） | Windows 实测；旧报错原文只在 Python 3.12.10 锁定<br>Linux/macOS NOT_RUN |
| **损坏/截断证据** | `negative-legacy-events-ok-truncated-tail`、`-ok-unparseable-line`；摘要不符的 fixture、封存资源与取证文件。收尾轮起条目的 integrity 如实登记：truncated 2 条（`negative-legacy-events-ok-truncated-tail`、`negative-protocol-synthetic-sample-missing-final-lf`），corrupted 2 条（`negative-legacy-events-ok-unparseable-line`、`negative-protocol-synthetic-sample-lf-to-crlf`）[E18] | 旧：支持，`summarize_events` 记录 parse_error_lines、truncated，可读的行照常计入 [E03]<br>新：原始流的读取与完整性判断未实现（04）。测试辅助函数 `new_strict_jsonl_verdict` 逐行调用 `strict_json_loads`，坏行得到 `E_JSON_SYNTAX`、其余行照常判断；这是测试辅助，不是产品入口 [E04]<br>摘要不符时保留原字节与不符事实：见“校验”列 [E11] | 拒绝 [E11]：<br>- 单个 JSON 文档：`strict_json_loads` 报 `E_JSON_SYNTAX`（事件流的逐行调用来自上述测试辅助函数）<br>- `E_RESOURCE_HASH_MISMATCH`<br>- 基线归档拒绝摘要不符的取证 | 协议函数层拒绝形成完整成功证明 [E11][E15]：<br>- `assess_stream_integrity` 返回 incomplete<br>- 退出码 0 但缺结束证据时，`protocol_complete=False`<br>入口本身：未实现（04/07） | 旧：ok=false，记为 G1 失败，未改动 [E17]<br>新审核：未实现（03） | 不适用 | Windows 实测<br>Linux/macOS NOT_RUN |
| **合成 fixture** | manifest 中 188 条全部是 `representation=synthetic_fixture`：legacy 18、negative 157、synthetic 13（收尾轮由 171 条增加：D-20–D-23 的 6 个 legacy 负例、11 个 fixture-manifest-entry 负例） | 支持（测试 profile）：逐文件核对摘要、目录完整性、`-text` 属性以及 hash-object 过滤前后的摘要 [E12]；整份 manifest 按资源类型 fixture-manifest 核验（`validate_resource_payload`，R-P10）[E18]；逐文件凭据形态扫描（收尾轮，文档 8.3）[E19] | 支持：`validate_fixture_manifest_set` [E13]<br>拒绝（产品入口，P4 起作用于全部 171 条）[E12]：<br>- 能力声明不符合封闭词法 `[a-z][a-z0-9_]{0,127}`（大小写或连字符变体）：`E_SCHEMA_FIELDS`（reason `claim_syntax`，P4 第 3 轮）<br>- synthetic 冒充 captured，或声称 real_、vendor_、legacy_ 前缀或 3 个真实兼容声明：`E_PROVENANCE_CLAIM`（reason `synthetic_requires_synthetic_fixture` / `synthetic_cannot_prove_real_compatibility`）<br>- legacy、negative 条目声称 real_cli_compatibility、vendor_protocol 或 real_/vendor_ 前缀：`E_PROVENANCE_CLAIM`（`real_compatibility_claim_requires_captured_raw`）<br>- legacy_dispatch_behavior 只允许 legacy + legacy-judgment；声明 legacy_ 能力的负例必须从 legacy 条目派生（清单级，`negative_legacy_claim_requires_legacy_base`）<br>- 负例不能从另一个负例派生（清单级，`negative_must_derive_from_valid_sample`，P4 第 3 轮）<br>- 收尾轮（R-P11）：缺新字段的旧结构条目 `E_SCHEMA_FIELDS`（`missing_field`）；legacy 与 captured 的 traceable 不为 true、captured 缺 capture、其他类别带 capture、不完整的条目声称完整运行流、协议结构未保留的条目声称协议字段语义：`E_PROVENANCE_CLAIM`（负例 11 个，另有清单级改写用例；修订 10 起后两条按受控词表判定，complete_run、full_event_log、field_semantics 等同义名称同样拒绝，词表外的写法不受限制）[E18]<br>测试层规则 `check_synthetic_fixture_claims` 另加本清单的约定：synthetic_fixture 条目不声明 legacy_dispatch_behavior，legacy_ 前缀只放行与旧实现差分入口对应的白名单；只在测试与 `--write` 时生效，不是产品入口 [E12] | 不适用：不得作为业务授权或厂商证据；proves 与 does_not_prove 随条目保存 [E12] | 不适用 | 不适用 | Windows 实测<br>Linux/macOS NOT_RUN |
| **01 内部记录**（fixture-manifest、baseline-capture 等） | fixture-manifest 与 fixture-manifest-set v1；baseline-capture、baseline-input-manifest、baseline-environment、baseline-archive-manifest v1 | fixture-manifest：支持（严格解析；收尾轮起整份字节可按资源类型 fixture-manifest 经 `validate_resource_payload` 核验）[E13][E18]<br>baseline-*：支持；`archive` 用普通 `json.loads`，核对 capture_id 与逐文件摘要 [E14] | fixture-manifest：支持，含结构与来源一致性 [E13]<br>baseline-*：结构校验未实现，只核对摘要 [E14]<br>两者都不是公共记录：`route_public_record` 返回 `E_COMPAT_UNSUPPORTED`，`validate_public_record` 返回 `E_SCHEMA_RECORD_TYPE`，收尾轮写成回归测试 [E07][E14][E20] | 不适用 | 不适用（只作为 01 的验收证据） | 不适用 | Windows 实测<br>Linux/macOS NOT_RUN |

## 3. 依据索引

| 编号 | 依据（测试方法、fixture id、源码行） |
|---|---|
| E01 | `expected/legacy-contracts.json`；`tests/codekit01_legacy.py --check`（生成函数 `compute_expected_contracts`，`tests/codekit01_legacy.py:847`；收尾取证 `bl-01closure-legacy-check-20260926`：`38 checks, 0 differ`，归档 run/stdout.bin:39，修订 11 补）。差分测试分三项报告：<br>- `DifferentialTests.test_legacy_contract_projection_unchanged`：按当前 `scripts/pi_dispatch.py` 的字节重算，只比较 cases，失败时列出不同的 case_id 与字段；<br>- `test_legacy_expected_headers_match_generator`：预期文件头与生成器定义一致（头部的实现摘要是锁定时的记录，不参与判断内容的比较）；<br>- `test_legacy_implementation_bytes_are_source_revision`：实现字节是否仍为 a4fa199，单独报告。<br>预期只由 a4fa199 字节的旧实现生成（`--write-expected` 要求字节相同）。旧函数：<br>- `normalize_contract`（`scripts/pi_dispatch.py:1189`）<br>- `validate_contract`（1432）<br>- `validate_plan`（1656） |
| E02 | `LegacySourceTests.test_legacy_copies_equal_git_show`：6 个合同与 `git show a4fa199:<path>`、`git cat-file blob` 的字节相同。来源是 `.agents/skills/plan-task/examples/{normalize-query,auth-refresh-401}.v1.{md,json}` 与 `.agents/skills/plan-task/contract-template.{md,json}`。工作区中的来源文件与该 blob 相同，由生成（`write_legacy_contracts`）与 `--check` 核对，默认测试不核对。<br>`LegacySourceTests.test_generator_sources_at_revision`：`scripts/pi_dispatch.py` 与 `tests/stub_pi.py` 在 a4fa199 的摘要与锁定值相同。<br>取不到 git 或 a4fa199 时这两项默认失败，只有 `CODEKIT01_ALLOW_NOT_RUN=1` 时记为 NOT_RUN（第 1 节） |
| E03 | `expected/legacy-events.json`；`DifferentialTests.test_legacy_event_projection_unchanged`（只比较 cases，同 E01）、`test_legacy_negative_derivations_reproducible`；`StubTests.test_stub_regeneration_matches_locked_bytes`（默认测试在 Windows 上重跑 stub，与锁定字节和退出码比较；其他平台 NOT_RUN）、`StubTests.test_stub_cwd_placeholder_and_no_local_paths`（各平台：session.cwd 是占位值，stub 流、事件负例与事件预期中没有本机路径痕迹）；`--check-stub-regen`（10 checks, 0 differ；收尾取证 `bl-01closure-legacy-check-stub-regen-20260926`，归档 run/stdout.bin:11，修订 11 补）。旧函数 `summarize_events`（`scripts/pi_dispatch.py:2160`） |
| E04 | `expected/legacy-new-strict.json`；`DifferentialTests.test_new_strict_verdicts_unchanged`、`test_new_strict_verdicts_are_separate_from_legacy_expectations`。计算函数（都是测试辅助，不是产品入口；产品函数只有其中调用的 `strict_json_loads`）：<br>- `new_strict_verdict`（`tests/codekit01_legacy.py:1318`）<br>- `new_strict_jsonl_verdict`（1336，按 LF 切行后逐行调用）<br>- `compute_new_strict_expected`（1374） |
| E05 | `SyntheticTests.test_synthetic_positives_accepted`、`test_doc_samples_equal_design_doc_blocks`、`test_c1_completed_entry_matches_doc`。fixture：<br>- `synthetic-doc-4.1.3-run-context`、`synthetic-doc-4.2.2-resource-ref`、`synthetic-doc-4.3.1-run-event`、`synthetic-doc-4.3.6-error-record`、`synthetic-doc-4.3.9-usage-unknown`<br>- `synthetic-vendor-event-1`、`synthetic-usage-reported-cost-1`<br>`validate_public_record` 在 `protocols.py:1995` |
| E06 | `NegativeTests.test_each_negative_yields_exactly_manifest_code`（135 个 `negative-protocol-*`（收尾轮由 124 个增加），每个都断言错误码、field 与 reason；reason 用来区分同码同位置的规则）、`test_negative_bytes_reproducible_from_base`、`test_negative_counts_by_group`。P3 返工把 3 个同时违反两个条件的变体改为只违反目标条件：`fixture-manifest-entry-claim-both-proved-and-not`（改为把已有的 exact_byte_digest 加进 does_not_prove）、`run-event-core-type-claimed-by-vendor`（基样本改为 `synthetic-vendor-event-1`，入口在测试内登记一个只允许 vendor 的合成类型）、`fixture-manifest-entry-synthetic-relabelled-captured`（同时补上 source_test_id）。`tests/test_protocols.py` 342 项（修订 10；收尾轮为 341 项），跳过 4 项（F017、F029、F030、jsonschema 元校验）；收尾取证 `bl-01closure-test-protocols-20260926` 同为 342 项、338 个 ok、跳过 4 项（归档 run/stderr.bin:687、689，修订 11 补）。P4 第 3 轮（生成修订 v4）：`run-event-json-trailing-second-document` 的期望 reason 改为固定的 `syntax_error`；`run-event-json-nan`、`-json-negative-infinity`、`-json-overflow-1e10000`、`-json-integer-out-of-range` 的期望 field 由 null 改为 `/seq`（严格解析的数值错误带指针）；新增 `negative-protocol-vendor-event-role-null`；负例字节不变。P4 把 `fixture-manifest-entry-synthetic-relabelled-captured` 的期望 reason 改为 `captured_requires_captured_redacted_or_normalized`（captured 允许 normalized_event 后规则改名），负例字节不变 |
| E07 | `route_public_record`（`protocols.py:1979-1985`）、`_check_record_header`（798-811）；`SchemaRoutingTests.test_A09_route_expected_type_and_record_type`：<br>- 期望类型为 "contract" 或 "fixture-manifest" 时报 `E_COMPAT_UNSUPPORTED`；<br>- 缺 record_type 时报 `E_SCHEMA_RECORD_TYPE`。<br>另有第 1 节的抽查（收尾轮写成回归测试，见 E20） |
| E08 | `SchemaRoutingTests.test_F014_unknown_version_no_legacy_fallback`：v2 以及带新字段的 v2 都报 `E_SCHEMA_VERSION_UNSUPPORTED`，并断言输入没有被修改。fixture：<br>- `negative-protocol-run-context-schema-version-2`<br>- `negative-protocol-run-event-schema-version-2`<br>- `negative-protocol-usage-unknown-schema-version-2`<br>源码 `protocols.py:808-810` |
| E09 | `_validate_ref`（`protocols.py:1571-1583`；修订 11 按当前字节更正，原写 1571-1584）；静态注册表 `build_default_registry`（1513-1539，只有 fixture、fixture-manifest、public-schema、baseline-evidence、raw-segment 五种；修订 11 按当前字节更正，原写 1513-1535）；`ResourceRefTests.test_F032_unknown_kind_and_unknown_field`。fixture：<br>- `negative-protocol-resource-ref-kind-unregistered`<br>- `negative-protocol-usage-cost-evidence-ref-kind-unregistered`<br>- `negative-protocol-fixture-manifest-entry-resource-kind-not-fixture`<br>- `negative-protocol-run-event-type-unregistered`（`E_EVENT_TYPE_UNKNOWN`；默认事件类型只有 `run.prepared`，见 `protocols.py:2074-2078`）<br>- raw_refs 引用已登记但不是 raw-segment 的 kind：`E_RESOURCE_KIND`（裁决 R-P7，P4；`test_A12_raw_refs_only_reference_raw_segments`）<br>封存：`sealing.py:322-325`、`379-382`；`SealingTests.test_A13_seal_rejects_unregistered_or_non_file_kind` |
| E10 | 重复键检查（`protocols.py:408`）。`strict_json_loads` 只有 `max_bytes`、`max_depth` 两个参数，没有 legacy 放行参数（`protocols.py:420-421`）。测试：`StrictJsonTests.test_F002_top_level_duplicate_key`、`test_F003_nested_duplicate_key_pointer`、`test_F004_escaped_duplicate_key`。fixture：<br>- `negative-legacy-contract-json-duplicate-key-first-differs`、`-last-differs`<br>- `negative-protocol-run-event-json-duplicate-key-seq`、`-json-escaped-duplicate-key-seq`、`-json-nested-duplicate-key` |
| E11 | 截断与损坏的 fixture：`negative-legacy-events-ok-truncated-tail`、`-ok-unparseable-line`。<br>测试：<br>- `EventTests.test_F039_tail_truncation_is_incomplete`（`assess_stream_integrity`，`protocols.py:2234`）<br>- `RunDimensionTests.test_F040_exit_zero_without_end_evidence`<br>- `SealingTests.test_A13_read_sealed_missing_and_tampered`<br>- `FileIntegrityTests.test_every_manifest_digest_matches_file_bytes`<br>- `tests/test_baseline_tool.py` 的 `ArchiveTests.test_archive_refuses_capture_with_wrong_digest`<br>摘要不符的 fixture（均为 `E_RESOURCE_HASH_MISMATCH`）：`negative-protocol-synthetic-sample-lf-to-crlf`、`-missing-final-lf`、`negative-protocol-resource-ref-sha256-wrong-value` |
| E12 | 产品来源规则（`protocols.py` 的 `_validate_fixture_entry`，3374 起；能力声明循环 3496-3504；清单级 3585-3603），P4 起作用于**全部**条目：<br>- 能力声明必须符合封闭词法 `[a-z][a-z0-9_]{0,127}`（`_claim_list`，P4 第 3 轮），大小写与连字符变体在结构层报 `E_SCHEMA_FIELDS`（`claim_syntax`）；<br>- synthetic 只能是 synthetic_fixture，不得声称 `real_`、`vendor_`、`legacy_` 前缀或 3 个真实兼容声明；<br>- 任何条目声称 real_cli_compatibility、vendor_protocol 或 `real_`/`vendor_` 前缀，只允许 captured + captured_raw/redacted_raw；<br>- legacy_dispatch_behavior 只允许 legacy + legacy-judgment；其他 `legacy_` 前缀只允许 legacy 或 negative，且声明它的负例必须从 legacy 条目派生（清单级）；负例不能从负例派生（清单级，P4 第 3 轮）。<br>测试层规则 `check_synthetic_fixture_claims`（`tests/test_codekit01_fixtures.py:270`；P4 第 3 轮起先按 ASCII 小写化、`-` 归一为 `_` 再判定）与清单级 `check_manifest_claims`（288）是本清单的额外约定：representation=synthetic_fixture 的条目不声明 legacy_dispatch_behavior；`legacy_` 前缀只放行 legacy_source_bytes、legacy_contract_judgment、legacy_event_summary_judgment，且要求来源是 legacy 条目或其派生负例、期望入口是对应的旧实现差分入口。它不是产品入口，reason 以 `test_rule_` 开头。<br>测试：<br>- `ManifestTests.test_provenance_consistency`（逐条断言上述规则）、`test_claim_rule_rejects_real_and_unlisted_legacy_claims`（每个分支分别断言产品入口与测试层规则的 reason）、`test_claim_spelling_variants_rejected`（P4 第 3 轮：大小写与连字符变体被产品入口与测试层规则分别拒绝）、`test_counts_by_class_and_representation`（断言全部为 synthetic_fixture）、`test_manifest_is_strict_json_and_validates`；生成（`--write`）时先经 `validate_fixture_manifest_set`，再经 `check_manifest_claims`<br>- `tests/test_protocols.py` 的 `test_A12_real_compatibility_claims_by_origin_and_representation`、`test_A12_negative_legacy_claims_require_legacy_base`、`test_A12_claim_lexicon`、`test_A12_negative_cannot_derive_from_negative`<br>- `FileIntegrityTests.test_directory_has_no_unregistered_or_missing_files`、`test_git_attributes_disable_line_ending_conversion`、`test_git_clean_filter_keeps_bytes`<br>负例：<br>- `negative-protocol-fixture-manifest-entry-synthetic-*`，4 个，均为 `E_PROVENANCE_CLAIM`（产品规则）<br>- `negative-protocol-fixture-manifest-claims-legacy-stub-claims-real-cli-compatibility`、`-vendor-protocol`：从 legacy-stub-events-ok 条目的副本（`synthetic-manifest-entry-legacy-stub-events-ok`）派生，把 real_cli_compatibility 或 vendor_protocol 从 does_not_prove 移到 proves；产品入口报 `E_PROVENANCE_CLAIM`（`real_compatibility_claim_requires_captured_raw`）<br>- `negative-protocol-fixture-manifest-claims-legacy-stub-claims-unlisted-legacy-capability`：把 legacy_end_to_end_run 移到 proves；产品入口接受（legacy 类可以声明 legacy_ 能力），测试层规则报 `E_PROVENANCE_CLAIM`（`test_rule_legacy_claim_not_whitelisted`）<br>- `negative-protocol-fixture-manifest-claims-legacy-stub-claims-uppercase-real-cli-compatibility`（P4 第 3 轮）：在 proves 末尾加上大写变体 `REAL_CLI_COMPATIBILITY`；产品入口在结构层报 `E_SCHEMA_FIELDS`（`/proves/3`，`claim_syntax`） |
| E13 | `validate_fixture_manifest_set`（`protocols.py:3551`）与 `_validate_fixture_entry`（3374）；`negative-protocol-fixture-manifest-entry-*`，共 22 个（收尾轮新增 11 个，见 E18）；另有 `negative-protocol-fixture-manifest-claims-*` 4 个（3 个由产品入口拒绝，1 个由测试层规则拒绝，见 E12） |
| E14 | `record_type: "baseline-capture"`（`scripts/codekit/baseline.py:993`）；`CAPTURE_SCHEMA_VERSION = 1`（46）。`cmd_archive`（1268 起）：用普通 `json.loads` 读取，核对 capture_id 与逐文件的 sha256 和大小。另有第 1 节的抽查（收尾轮写成回归测试，见 E20） |
| E15 | `build_run_dimensions`（`protocols.py:2570` 起）：legacy_verdict、legacy_attempt_state、integration_observation 原样保留，不提供聚合的成功键。测试：`test_A05_legacy_verdicts_match_dispatcher`（`LEGACY_VERDICTS` 与 `scripts/pi_dispatch.py:75` 相同）、`test_A05_unknown_legacy_verdict_rejected` |
| E16 | 第 6.2 节的摘要对照；`git diff HEAD` 对受保护路径为空；`git grep -l codekit HEAD` 没有输出 |
| E17 | [legacy-inventory.md](legacy-inventory.md) 4.5 节与 4.10 节：G1 把事件摘要中的每条 problem 记为一项失败（`scripts/pi_dispatch.py:4165-4182`）；run 退出码只在 NEEDS_REVIEW 且 events.ok 为真时为 0（3348-3349） |
| E18 | 收尾轮，裁决 R-P11（acceptance.md M-03）。产品规则：`_validate_fixture_entry`（`protocols.py:3374` 起；结构 3436-3444，第 3b 步 3488-3493，第 5 步 3511-3519）；修订 10 起第 5 步按受控词表判定（词表常量 3268-3294，`_claim_tokens`、`_has_token_stem`、`_is_complete_stream_claim`、`_is_field_semantics_claim` 3297-3327；修订 11 按当前字节更正，原写 3264-3328；protocols-api.md 14.2 第 5 步）。本清单的登记：`tests/codekit01_legacy.py` 的 `LEGACY_PLATFORM_SCOPE`、`NEGATIVE_EVENT_INTEGRITY` 与 `_entry`，`tests/test_codekit01_fixtures.py` 的 `platform_scope_for`、`_entry`、`NegativeSpec.integrity`。测试：<br>- `R11Tests.test_every_entry_follows_registration_rules`（逐条断言五个字段的登记规则）、`test_registration_counts`（分布计数，见第 8 节第 10 条）、`test_manifest_level_errors_carry_entry_prefix`（清单级错误带 `/entries/<i>` 前缀，含 truncated 条目声称 `full_run_replay`、stub 条目的协议结构改为 false 后声称 `protocol_field_semantics_*` 两个真实条目上的规则与对照；修订 10 补上复审实测能绕过前缀规则的同义名称：truncated 条目声称 complete_run、run_stream_complete、complete_event_stream、full_event_log、entire_run_stream 都被拒绝，partial_run_stream 被接受；stub 条目的协议结构为 false 时声称 field_semantics 被拒绝）、`test_two_step_negatives_each_step_alone_accepted`、`test_c1_completed_entry_matches_protocols_api_example`（C.1 补齐条目与 protocols-api.md 14.1 的示例逐值相同）、`test_whole_manifest_bytes_pass_fixture_manifest_payload_validator`（整份 manifest 经 `validate_resource_payload`；旧结构、schema_version=2、BOM 被拒绝，校验器的错误码原样传出）；<br>- `SyntheticTests.test_c1_completed_entry_matches_doc`（去掉补齐的 11 个字段后与设计文档 C.1 相同）。<br>负例（`negative-protocol-fixture-manifest-entry-*`，收尾轮新增 11 个）：`integrity-not-in-enum`、`platform-scope-empty`、`platform-scope-any-with-platform`、`platform-scope-uname-spelling`、`platform-scope-duplicate`（`E_SCHEMA_FIELDS`）；`traceable-null`（`E_SCHEMA_TYPE`）；`capture-field-missing`（`E_SCHEMA_FIELDS`，`missing_field`）；`capture-on-synthetic`、`legacy-untraceable`、`incomplete-claims-complete-stream`、`structure-not-preserved-claims-field-semantics`（`E_PROVENANCE_CLAIM`）。后两个的目标条件本身由两处字节构成，测试核对单独一步时条目仍被接受 |
| E19 | 收尾轮，文档 8.3“fixture 含真实凭据”。`tests/test_codekit01_fixtures.py` 的 `CREDENTIAL_RULES`，覆盖的形态**只有**以下 15 条（修订 10 由 9 条增加 6 条，复审 fidelity 视角 major）：Bearer 令牌；`sk-` 前缀密钥（含 `sk-proj-`、`sk-ant-api03-` 这类带一段前缀的写法）；GitHub `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_` 与 `github_pat_`；Slack `xoxa-`/`xoxb-`/`xoxp-`/`xoxo-`/`xoxs-`/`xoxr-`；PEM 私钥块（`-----BEGIN … PRIVATE KEY-----`）；AWS 访问键 ID（AKIA、ASIA、AGPA、AIDA、AROA、ANPA 加 16 位）；Google API key（`AIza` 加 35 位）；JWT（两段 `eyJ` 开头）；`api_key`/`secret`/`token`/`password`/`passwd`/`access_key`/`auth` 等键名的赋值且值像长随机串（至少 20 个字符、两类字符、熵不低于 3.0 位），JSON 中键名像凭据字段且值像长随机串；**修订 10 新增** Stripe（`sk_`/`rk_`/`pk_` 加 `live_`/`test_`）、Hugging Face（`hf_` 加至少 30 个字母）、GitLab（`glpat-`）、npm（`npm_` 加 36 位）、HTTP Basic 认证头（`Basic` 加至少 16 位 base64）、URL 内嵌口令（`scheme://用户:口令@`，口令至少 8 个字符）。**清单之外的形态不会被发现**，例如没有固定前缀、也不在凭据类键名、Bearer/Basic 认证头或 URL 写法中的口令，其他厂商的专有前缀，以及短于各条规则最小长度的值。`CREDENTIAL_ALLOWLIST`（DEMO_REVIEW_SECRET、DEMO_TOKEN_FOR_REVIEW、SYNTHETIC_CREDENTIAL，逐条写明来源；只按命中的值整串放行）、`scan_bytes_for_credentials`（原字节、UTF-16 LE/BE 各两种对齐的 ASCII 视图、能严格解析的 JSON/JSONL 中的每个字符串，以及“键名像凭据字段且值像长随机串”）。测试：`CredentialScanTests.test_fixture_files_contain_no_credential_shapes`（189 个文件，即 188 个登记文件加 manifest.json；本次没有非白名单命中，收尾取证 EV-C08 第 21 行 ok（measured）。该方法丢弃白名单放行结果（`found, _allowed = …`，:2636），只断言非白名单命中为空，所以“没有白名单放行”不是运行结论：修订 12 静态核对 fixture 目录中没有三个白名单标记（source_inspected），由此推断没有放行；修订 10 起累计实际扫描的文件数与字节数，断言等于文件数与各文件大小之和）、`test_scanner_detects_every_rule_in_every_view`（15 条规则各一个样本，另有同一规则中其他前缀或写法的 38 个对照样本，每个样本 × 6 种载体；断言样本集合与规则集合相等，失败信息不含样本值）、`test_secret_key_in_json_with_random_value_detected`（修订 10 加一个低熵对照 `{"api_key": "AAAA…A11"}`，固定熵阈值）、`test_allowlist_is_exact_and_documented` |
| E20 | 收尾轮，acceptance.md M-04（第 1 节抽查的回归测试）：`PublicEntryRejectionTests.test_contract_v1_json_is_not_a_public_record`（3 份 legacy JSON 合同）、`test_fixture_manifest_set_is_internal_and_version_2_rejected`、`test_baseline_records_are_internal`（归档 `evidence/` 中 baseline-capture 9 份、baseline-input-manifest 18 份、baseline-environment 18 份、baseline-archive-manifest 9 份）。每项断言 code、field、reason，并断言输入不被修改。修订 11 补：该方法按目录现场查找 `evidence/` 下的记录，不写死份数；收尾取证 `bl-01closure-test-codekit01-fixtures-v-20260926` 时读到的仍是上面的 9、18、18、9 份（该取证输入清单中 `evidence/` 的记录如此），`evidence/closure/` 在取证之后才归档，之后再运行会读到 19、38、38、19 份（本修订没有运行，未核对） |
| E21 | 收尾轮，acceptance.md M-04（D-20–D-23 的 legacy 负例）：`tests/codekit01_legacy.py` 的 `NEGATIVE_CONTRACT_VARIANTS` 末尾 6 项与 `COMPAT_MATRIX_D_CASES`；旧判断在 `expected/legacy-contracts.json`，新严格入口判断在 `expected/legacy-new-strict.json`，两者由 `DifferentialTests` 逐字节锁定。`CompatMatrixDCaseTests`（`test_every_d_case_is_a_registered_single_fault_fixture`、`test_d20_non_finite_cost_amount`、`test_d21_deep_nesting`、`test_d22_invalid_utf8`、`test_d23_identifier_trailing_newline`）按第 4.3 节的表述逐项断言要点。修订 10：`test_every_d_case_is_a_registered_single_fault_fixture` 另做反向核对，故障说明写“兼容矩阵 D-xx”的合同负例变体集合必须与映射表逐项相等，事件负例不得引用 D 编号 |
| E22 | 收尾轮，文档 8.4、acceptance.md R-12：`tests/codekit01_legacy.py` 的 `_make_owned_tempdir`（763）、`ownership_problem`（776）、`_rmtree`（814）。`CleanupOwnershipTests`：自建目录可删除；未登记（即使带伪造标记）、标记被改或缺失、不直接位于系统临时目录下、前缀不属于本工具、目标是指向自建目录的链接，都报 `CleanupRefused` 且不删除；仓库内路径只做只读核对；未登记的前缀不能建立。修订 10 补三项（复审 tests-mutation 视角）：`test_marker_with_trailing_newline_refused`（标记末尾多出换行、CRLF 或空格）、`test_marker_link_to_valid_token_refused`（标记是指向正确令牌副本的符号链接；无法创建文件符号链接时跳过，本机实测运行）、`test_removal_unregisters_directory`（删除后登记被注销，同一路径重建目录并写入同一令牌后仍被拒绝；原 `test_owned_directory_is_removed` 末尾的断言由“目标不是目录”满足，注释改为如实说明） |
| E23 | 修订 10，文档 8.4、acceptance.md R-12（复审 tests-mutation 视角 major：harness 一侧的归属核对此前没有回归测试）：`tests/legacy_harness.py` 的 `make_temp_area`（996）、`_verify_area_location`（946）、`_verify_area_root`（958）、`_verify_area_marker`（973）、`_remove_owned_once`（1071）、`remove_tree`（1124）。`tests/test_codekit01_fixtures.py` 的 `HarnessCleanupOwnershipTests`（11 个方法），每项断言 `remove_tree` 抛出 `CleanupOwnershipError`（不是静默返回，也不是重试后的其他异常）且目标仍在：未登记的 `codekit-legacy-*` 目录（无标记、伪造标记、标记内容恰是另一已登记区域的真实令牌）；区域外路径（含不存在的路径）；标记同长度改写、末尾多出字节、截短、缺失、是目录、是指向正确令牌副本的链接；区域不是系统临时目录的直接子目录；建立后 `tempfile.gettempdir()` 改变；目录名前缀不再属于本工具；根目录被替换为同名新目录并复制了标记（目录身份不同）；待删路径本身是联接、区域根目录被换成联接；已删除区域中新出现的路径。正向对照：区域与区域内子目录可删除（含只读文件）；区域内有指向区域外目录的联接（以及指向区域外文件的符号链接）时，删除区域后区域外的文件不受影响。只向 `remove_tree` 传本测试自建的路径 |

## 4. 新旧入口判断差异

- **数据来源**：
  - 旧判断取自 `expected/legacy-contracts.json` 与 `legacy-events.json`；
  - 新判断取自 `expected/legacy-new-strict.json`；
  - 两边分开存放（E04），不同之处是本节的输入，不是测试失败。
- **新入口的范围**：
  - 合同整份交给 `strict_json_loads`，只判断 JSON 层；
  - 事件流：测试辅助函数 `new_strict_jsonl_verdict` 按 LF 切行，每行原样（含行尾 CR）交给 `strict_json_loads`。这只说明每行能否作为单个严格 JSON 文档；它不是产品入口，也不是新入口对事件流的判断。原始流的读取与完整性判断未实现（归 04）。
- **旧 CLI 的退出码**：所有合同用例的旧 CLI `validate` 都退出 2，因为 base_sha 是虚构值，在构造的临时仓库中不存在。所以判断合同层是否有问题，要看进程内的 `validate_plan` 第 3–6 步，而不是 CLI 退出码。

**01-D09 的统一处理决定**（下文简写为“D09 标准处理”）：

1. 历史只读保留：原字节与旧判断保存在 fixture 与 expected 中，不改写，不重算哈希；
2. 新入口拒绝：`strict_json_loads` 不设 legacy 放行开关；
3. 需要时重新发布明确输入：历史合同需要在新入口使用时，出新版本合同（`.agent/plans/<task>.vN+1`）重新发布，不修补原文件。

各条如有额外决定，写在该条中。

### 4.1 合同（P3 的 16 个用例；收尾轮新增的 6 个见 4.3 节）

| 编号 | 用例（fixture） | 旧：进程内 validate_plan 第 3–6 步 | 旧：CLI validate（临时仓库） | 新严格入口 | 差异类型 | 登记的处理决定 |
|---|---|---|---|---|---|---|
| D-01 | `json-duplicate-key-first-differs`：risk_level 先写 high，后写 low | 0 个错误，返回合同；后出现的 low 生效，与 Markdown 一致，**静默通过** | 退出 2，1 个错误（只有 base_sha 不存在） | 拒绝，`E_JSON_DUPLICATE_KEY`，`/risk_level` | **旧接受、新拒绝** | D09 标准处理。<br>- 历史按“后值生效”审计。<br>- 登记风险：先出现的 high 被丢弃，按“先值生效”解析的读者会得到不同的 risk_level。<br>- 旧 `run` 入口在 base_sha 存在的仓库中会继续使用这份合同（未做端到端验证）。<br>- 旧入口是否收紧，归 09 裁决（legacy-inventory 11.2 第 1 条第 7 项） |
| D-02 | `json-duplicate-key-last-differs`：先 low 后 high | 1 个错误：Identity 的 risk_level（low）与 JSON（high）不一致 | 退出 2，2 个错误 | 拒绝，`E_JSON_DUPLICATE_KEY`，`/risk_level` | 两边都拒绝，理由不同：旧实现没有发现重复键本身 | 保留旧错误原文，不改写成新错误码；新错误码只用于新入口 |
| D-03 | `json-utf8-bom`：JSON 以 EF BB BF 开头 | 1 个错误：“JSON 合同解析失败：Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)” | 退出 2，1 个错误 | 拒绝，`E_JSON_BOM` | 两边都拒绝。旧错误原文来自 Python json，依赖解释器版本 | 同 D-02；旧原文只在 Python 3.12.10 锁定 |
| D-04 | `json-plan-version-float`：plan_version 为 1.0 | 0 个错误（`1.0 == 1`） | 退出 2（只有 base_sha） | 接受（JSON 层） | 旧接受；新入口不判断合同字段。在公共记录中，同样的写法报 `E_SCHEMA_TYPE`（`negative-protocol-run-context-plan-version-float`） | D09 标准处理。合同 v1 的字段语义是否收紧归 09（legacy-inventory 11.2 第 1 条第 2 项）。不能把“新严格入口接受”理解为合同合法 |
| D-05 | `json-schema-version-true`：schema_version 为 true | 0 个错误（`True == 1`） | 退出 2 | 接受 | 同 D-04。公共记录中报 `E_SCHEMA_VERSION_TYPE`（`negative-protocol-run-context-schema-version-true`） | 同 D-04 |
| D-06 | `json-unknown-top-level-field` | 0 个错误（忽略未知字段） | 退出 2 | 接受 | 同 D-04。公共记录中报 `E_SCHEMA_FIELDS`（`negative-protocol-run-context-unknown-top-level-field`） | 同 D-04 |
| D-07 | `json-plan-version-string`：plan_version 为 "1" | 1 个错误：“plan_version 应为 1，实际为 '1'” | 退出 2，2 个错误 | 接受 | 旧拒绝；新入口不判断 | 合同只由旧入口校验；新严格入口接受不构成合法性 |
| D-08 | `json-task-id-mismatch` | 1 个错误：task_id 不符 | 退出 2，2 个错误 | 接受 | 同 D-07 | 同 D-07 |
| D-09 | `json-base-sha-short-oid`：7 位 OID | 2 个错误：格式不对，且与 Markdown 不一致 | 退出 2，2 个错误 | 接受 | 同 D-07 | 同 D-07 |
| D-10 | `json-base-sha-trailing-newline` | 1 个错误：**只有** Markdown 与 JSON 不一致。旧的格式正则用 `$`，放过了末尾换行 | 退出 2，2 个错误 | 接受 | 旧的格式检查放过了末尾换行，靠一致性检查拦下；新的 `validate_git_oid` 用 fullmatch，但不在本入口中 | 同 D-07；ID 正则是否收紧归 09（legacy-inventory 11.2 第 1 条第 1 项） |
| D-11 | `legacy-contract-template`（模板） | 13 个错误（占位符等） | 退出 2，13 个错误 | 接受 | 同 D-07 | 同 D-07 |
| D-12 | `md-crlf-line-endings`：Markdown 全部改成 CRLF | **0 个错误**：旧实现按通用换行读取，接受 CRLF | 退出 2，1 个错误（只有 base_sha） | 不判断 Markdown（JSON 部分是原正例，接受） | 旧接受；01 新入口没有 Markdown 判断 | 历史只读；Markdown 合同的新规则归 09 |
| D-13 | `md-utf8-bom` | 1 个错误（标题应为 `# TASK: normalize-query`），1 个警告（第 1 行含 U+FEFF） | 退出 2，2 个错误，1 个警告 | 不判断 Markdown | 旧拒绝；新入口不判断 | 同 D-12 |
| D-14 | `md-missing-scope-section` | 4 个错误 | 退出 2，5 个错误 | 不判断 Markdown | 旧拒绝；新入口不判断 | 同 D-12 |
| — | 正例：`normalize-query.v1`、`auth-refresh-401.v1` | 0 个错误 | 退出 2，1 个错误（只有 base_sha，属于虚构值） | 接受 | 一致 | 无需处理 |

### 4.2 事件流（13 个用例）

| 编号 | 用例 | 旧：summarize_events（主视图 expects_settled=true） | 逐行 `strict_json_loads`（测试辅助） | 差异类型 | 登记的处理决定 |
|---|---|---|---|---|---|
| D-15 | `ok-truncated-tail`：最后一行只留前一半字节 | lines 19，parse_error_lines [19]，truncated true，ok false，complete false。<br>**expects_settled=false 时 complete 为 true**，但 ok 仍为 false | 18 行接受；第 19 行 `E_JSON_SYNTAX`；final_line_terminated false | 都判为失败，表示方式不同。旧的 complete 与截断无关 | D09 标准处理。新协议把完整性作为独立维度（F039），不从旧的 complete 继承。原始流到 run-event 的完整性判定归 04 |
| D-16 | `ok-unparseable-line`：第 2 行插入非 JSON 文本 | parse_error_lines [2]，ok false，complete true | 第 2 行 `E_JSON_SYNTAX`，其余 19 行接受 | 都判为有问题；旧的 complete 可以同时为 true | 同 D-15 |
| D-17 | `ok-duplicate-final-message-end`：最后一条 message_end 重复投递 | ok true。用量 input/output 为 3000/600（原流为 2000/400），cost 0.00129（原流为 0.00086）：**重复累计** | 20 行全部接受 | 旧接受并多计用量；新 JSON 层也接受。重复投递要靠 seq 或 usage_id 发现（`assess_event_log`、`usage_view`，F037），而 Pi 原始流两者都没有 | 历史只读。登记风险：旧摘要中的用量和费用可能重复计数。新记账归 07（01-D08），不继承旧摘要；映射到带 seq 的事件归 04 |
| D-18 | `startfail`：只有 1 行 | complete false，ok false；usage 的 token 全为 0，cost.total null，status unknown | 1 行接受 | 旧实现用 0 表示缺失的 token。新协议要求写 null 并给出原因，写 0 同时给原因会报 `E_USAGE_UNKNOWN_REASON`（`negative-protocol-usage-unknown-unknown-counter-filled-with-zero`） | 历史只读。旧的 0 不能当作“已知为 0”；转成新观测时写 unknown 与原因（04/07） |
| D-19 | `ok-nocost` | ok true；cost.total null，status unknown，不产生 problem | 19 行接受 | 旧实现不把未知费用当作问题；新协议要求写明未知原因 | 同 D-18 |
| — | 其余 8 条 stub 流：error、model、nosettle、ok、ok-ptl-high、ok-ptl-low、scope、textcall | 按旧规则判断：<br>- ok 为 true：ok、ok-ptl-high、scope<br>- ok 为 false：error、model、ok-ptl-low、textcall<br>- nosettle 在 expects_settled=false 时 ok 为 true，为 true 或 null 时 ok 为 false | 所有行都接受（CRLF 行尾中的 CR 属于 JSON 空白） | 新入口只判断 JSON 层，**没有**对运行成败作出不同判断 | 新入口“每行接受”不等于运行成功；旧判断原样保留 |

### 4.3 收尾轮落为 fixture 的差异（D-20–D-23）

这四项原是 [legacy-inventory.md](legacy-inventory.md) 3.12 节内存探针或源码核对的结果，修订 8 以前没有 legacy fixture。收尾轮（acceptance.md M-04）把它们做成从 `normalize-query.v1` 派生的 6 个单一故障负例（fixture_id 为 `negative-legacy-contract-` 加下表的用例名；判断时与未修改的另一半合同配对）：

- 旧判断由 a4fa199 字节的旧实现生成，进入 `expected/legacy-contracts.json`（合同用例由 16 个增加到 22 个）；
- 新严格入口的判断进入 `expected/legacy-new-strict.json`（JSON 文档由 13 份增加到 18 份；Markdown 不判断）；
- 两者由 `DifferentialTests` 逐字节锁定，下表的要点由 `CompatMatrixDCaseTests` 逐项断言 [E21]；
- 与 4.1 节一样，临时仓库中的旧 CLI 另报 base_sha 不存在（虚构值），所以合同层的判断看进程内结果。

| 编号 | 用例 | 旧：进程内 validate_plan 第 3–6 步 | 旧：CLI validate（临时仓库） | 新严格入口 | 差异类型 |
|---|---|---|---|---|---|
| D-20 | `json-cost-budget-infinity`：budget.cost_budget 改为 `{"amount": Infinity, "currency": "USD"}` | 0 个错误，返回合同：旧 `json.loads` 接受 Infinity，金额检查（`amount >= 0`，`scripts/pi_dispatch.py:1576-1580`）也通过。投影把非有限数写成 `<non-finite:Infinity>` | 退出 2，1 个错误（只有 base_sha） | 拒绝，`E_JSON_NON_FINITE`，`/budget/cost_budget/amount` | **旧接受、新拒绝** |
| D-20 | `json-cost-budget-nan`：金额改为 `NaN`（与上一行只差金额字面量） | 1 个错误：“budget.cost_budget 必须为 null 或 {amount, currency}”（NaN 与 0 比较为假） | 退出 2，2 个错误 | 拒绝，`E_JSON_NON_FINITE`，`/budget/cost_budget/amount` | 两边都拒绝，理由不同 |
| D-21 | `json-deep-nesting`：顶层增加 100000 层嵌套的空数组 | 未捕获的 RecursionError（本机 Python 3.12.10 的 json 实测 2000 层可解析、5000 层抛出） | 退出 1，stdout 为空，stderr 的 traceback 末行为 `RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string` | 拒绝，`E_JSON_LIMIT`（reason `decoder_recursion_limit_exceeded`） | 两边都拒绝；旧入口以未捕获异常退出（LB-EXIT-002 同类） |
| D-22 | `json-invalid-utf8`：risk_level 字符串中插入字节 0xFF | 1 个错误：“JSON 合同解析失败：'utf-8' codec can't decode byte 0xff in position 257: invalid start byte” | 退出 2 | 拒绝，`E_JSON_ENCODING`（`utf8_decoding_failed`） | 两边都拒绝；旧错误原文来自 Python，只在 3.12.10 锁定 |
| D-22 | `md-invalid-utf8`：Markdown 的 risk_level 行末插入字节 0xFF | 未捕获的 UnicodeDecodeError | 退出 1，stdout 为空，traceback 末行为 `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 369: invalid start byte` | 不判断 Markdown | 旧入口以未捕获异常退出（同一类输入在 JSON 中是 2，legacy-inventory P4-C49 已登记为可疑） |
| D-23 | `json-setup-id-trailing-newline`：setup 项的 id 由 `S01` 改为 `S01` 加换行 | 0 个错误，返回合同：`ITEM_ID_RE` 用 `$` 加 `re.match`（`scripts/pi_dispatch.py:58`、`1150`），放过末尾换行；setup 不与 Markdown 比较 | 退出 2，1 个错误（只有 base_sha） | **接受**：新严格入口只判断 JSON 层 | 旧接受，新严格入口也接受。新协议的标识规则整串匹配（`validate_task_id`、`validate_logical_id` 等对末尾换行报 `E_ID_SYNTAX`，公共记录见 `negative-protocol-run-context-request-id-trailing-newline`），但合同 v1 的字段不经过这些规则（归 09） |

处理决定：全部按 D09 标准处理。旧入口是否收紧（包括两类未捕获异常与 `$` 正则），由 09 决定；01 只锁定现状。

### 4.4 待裁决事项

- legacy-inventory 11.2 节第 1 条列出的合同宽松行为（第 1、2、7 项与本节直接相关），v2 是作为旧行为保留，还是作为缺陷修复：**01 不裁决**，归 09 合同发布。01 的立场只有 01-D09：新入口拒绝，历史只读。
- 事件重复投递、完整性与用量未知的映射（D-15 至 D-19）归 04；记账归 07。

## 5. 版本轴（1.3，实际值）

| 版本轴 | 本次实际值 | 来源 | 决定什么 | 不决定什么与备注 |
|---|---|---|---|---|
| 架构名称 | Code-Kit v2 | `docs/themis-tally-v2/README.md` | 目标模块组织 | 不代表已实现的能力 |
| 工具发布版本 | `TOOL_VERSION = "2.2.2"` | `scripts/pi_dispatch.py:48`（blob `8e7df57c91fc…`，sha256 `a00d6934…3ad4`）；两份 legacy 预期的 `legacy_implementation.tool_version` 也是这个值 | 旧调度器的发布 | 01 新增模块没有独立的发布版本号：`scripts/codekit/` 中没有版本常量，`baseline.py:45` 只有 `TOOL_NAME = "codekit-baseline"` |
| 合同 Schema | `CONTRACT_SCHEMA_VERSION = 1` | `scripts/pi_dispatch.py:49`；检查在 1459-1460，用 `!=` 比较，所以 true 与 1.0 也能通过 | 合同字段与解释规则 | 没有迁移到公共家族；v1 合同没有 record_type，交给公共入口时被拒绝（E07） |
| 公共协议家族 | `codekit-public` | `protocols.py:48`；Schema `$id` 为 `urn:codekit:public-protocol:1`（`protocols.py:50`，`schemas/codekit-public-v1.schema.json:3`） | 公共记录的分派命名空间（01-D02） | 不取代合同 v1 |
| 公共记录版本 | `schema_version = 1`；记录类型为 run-context、run-event、usage-observation | `protocols.py:49`、`57` | 公共家族首版 | 与合同 v1 数值相同，但互不相关；未知版本报 `E_SCHEMA_VERSION_UNSUPPORTED`，不回退 |
| 序列化 profile | `codekit-config-json-py-v1` | `protocols.py:51`；黄金向量 `synthetic-golden-vectors-c.2` | 语义快照的字节规则 | 以下文件都不是这个 profile：<br>- `manifest.json` 与三份 expected 用 indent=2、sort_keys、ensure_ascii=False，末尾 LF；<br>- 基线取证清单用紧凑的固定序列化（`baseline.py:104`） |
| 适配器修订 | **待定（04）** | 01 只要求 vendor 事件的 adapter_revision 非空（`protocols.py:2224-2226`）；`synthetic-vendor-event-1` 用的是合成值 `synthetic-adapter-r1` | 原始流到标准事件的解释版本 | 01 不检查它是否为已锁定的修订（protocols-api 第 16 节）；合成值不是真实修订 |
| 01 内部记录版本 | fixture-manifest 与 fixture-manifest-set 为 1；baseline-capture、baseline-input-manifest、baseline-environment、baseline-archive-manifest 为 1；两类 expected 文件（codekit01-legacy-expected、codekit01-new-strict-expected）为 1 | `protocols.py:808`（fixture-manifest 复用 `PUBLIC_SCHEMA_VERSION` 做检查）；`baseline.py:46` | 各自文件的格式 | 都不在 `PUBLIC_RECORD_TYPES` 中，不能经 `route_public_record` 路由，也不在本地 Schema 文件中。收尾轮按 R-P11 改变了 fixture-manifest 条目的封闭结构（13 个顶层字段，origin 与 redaction 各多一个字段），schema_version 仍为 1：旧结构的条目按缺字段报 `E_SCHEMA_FIELDS`（`missing_field`），不按旧结构解释；01 之外没有这份清单的消费者 |
| 规则修订 | 投影：`codekit01-legacy-projection-v1`、`codekit01-new-strict-projection-v1`；stub cwd 规则：`codekit01-legacy-stub-cwd-v1`；fixture 生成：`codekit01-legacy-fixtures-v2`（收尾轮新增 D-20–D-23 的 6 个合同负例，已有 legacy fixture 的派生与字节不变，由 v1 升为 v2）、`codekit01-protocol-fixtures-v5`（P3 返工改了 3 个负例的定义并新增 2 条，由 v1 升为 v2；P4 按产品来源规则改了 1 个负例的期望入口、新增 2 个负例、1 个负例的期望 reason 改名，升为 v3；P4 第 3 轮新增 2 个负例、5 个负例的期望 reason 或 field 随协议改动更新，升为 v4；收尾轮按 R-P11 给条目加字段，两个基样本随之改变、从它们派生的 15 个负例字节改变，另新增 11 个负例，升为 v5）；维度规则：`codekit01-run-dimensions-v2`（P4 cancelled 改为三态，由 v1 升为 v2）；脱敏规则：`redact-v2` | expected 文件头；manifest 条目的 origin.generator_revision；`protocols.py:93`；`baseline.py:56` | 对应产物的生成规则 | 与上面各版本轴无关 |
| 文档修订 | `review-expanded-2026-09-25` | 设计文档头部 | 设计文本的版本 | 不是工具、合同或协议版本 |
| 运行环境 | Git 对象格式 sha1；Windows Server 2025 Standard 10.0.26100；Python 3.12.10；git 2.55.0.windows.5 | 本次运行 | 本矩阵结论的适用范围 | Linux/macOS 没有运行 |

## 6. 回退（8.2 落到本次新增文件）

### 6.1 本次新增与改动，以及停用方式

| 新增或改动项 | 类型 | 旧入口是否调用 | 停用方式 | 停用后的影响 |
|---|---|---|---|---|
| `scripts/codekit/protocols.py`、`sealing.py`、`__init__.py` | 库 | 否 | 不导入即停用 | `tests/test_protocols.py`、`tests/test_codekit01_fixtures.py`，以及 `tests/codekit01_legacy.py` 中新严格预期的计算都无法运行 |
| `scripts/codekit/baseline.py` | CLI（capture、archive） | 否 | 不运行 | 不能重新取证。它按字节加载 `scripts/pi_dispatch.py` 的 `run_supervised`（`baseline.py:277-295`），只读取，不修改旧入口 |
| `schemas/codekit-public-v1.schema.json` | 数据 | 否 | 不使用 | protocols 本身不加载它（protocols-api 第 2 节） |
| `tests/test_protocols.py`、`tests/test_baseline_tool.py`、`tests/test_codekit01_fixtures.py`、`tests/codekit01_legacy.py` | 测试 | 否，不在 `tests/test_dispatch.py` 中 | 不运行：按文件单独运行（01-L04），仓库没有 CI 配置（没有 `.github/`） | 无 |
| `tests/test_legacy_gates.py`、`tests/test_legacy_lifecycle.py`、`tests/test_legacy_cli.py`、`tests/test_legacy_events.py`，公共夹具 `tests/legacy_harness.py`（P4 新增，修订 8 补列） | 测试（旧实现特征化回归） | 否，不在 `tests/test_dispatch.py` 中；它们以子进程或按字节加载的方式调用未改动的旧入口，只读，不修改它 | 不运行（01-L04） | 无；失去的是 a4fa199 现状的 159 个方法级观测（legacy-inventory.md 第 12 节），旧入口本身不受影响 |
| `tests/fixtures/codekit01/**` | 数据 | 否 | 不使用 | 无 |
| `docs/themis-tally-v2/01-baseline/**` | 文档与脱敏证据 | 否 | 不需要停用 | 无 |
| `.gitignore` 新增 `.agent/baseline/` | 已跟踪文件的改动 | 不适用 | **建议保留** | 去掉后，含机器路径的取证原件可能被暂存 |
| `.gitattributes` 新增 `schemas/*.json -text`、`tests/fixtures/codekit01/** -text`、`docs/themis-tally-v2/01-baseline/** -text`（第三条修订 8 补列，01-L06） | 已跟踪文件的改动 | 不适用 | **建议保留**；确要去掉时，同时移除对应文件 | 去掉后行尾会被转换，fixture 摘要不再相符（`FileIntegrityTests` 会发现）；`01-baseline/` 下登记了完整字节摘要的报告、清单与归档证据在提交再检出后也会失配（baseline-report 第 10 节） |
| `.agent/baseline/01-T1/bl-01t1-legacy-20260925/` | 取证原件（被 Git 忽略） | 不适用 | 不停用，保留 | 回退不删除证据 |
| `.agent/baseline/01-final/`（8 次最终取证）、`.agent/baseline/01-P4/`（被最终取证取代的中间一轮，原件保留、没有归档）（修订 8 补列） | 取证原件（被 Git 忽略） | 不适用 | 不停用，保留 | 回退不删除证据；`01-final/` 的脱敏归档在 `docs/themis-tally-v2/01-baseline/evidence/final/` |
| `.agent/baseline/01-closure/`（10 次收尾取证，R-01 严格 pyc 口径）（修订 11 补列） | 取证原件（被 Git 忽略） | 不适用 | 不停用，保留 | 回退不删除证据；脱敏归档在 `docs/themis-tally-v2/01-baseline/evidence/closure/`，操作者记录在 `evidence/run-controls-closure/`；就实施后的项目验证而言，它取代 `evidence/final/`，后者保留为历史证据 |

### 6.2 旧入口没有改动的证据

对照三组值：

- 基线值：取证原件 `.agent/baseline/01-T1/bl-01t1-legacy-20260925/pre/input-manifest.json` 中的记录。该清单本身的 sha256 为 `6aea1cc0b4db213d765af3514ce771d4199900cf0434eed47e7bbe1768ecffcc`（21679 字节），record_type 为 baseline-input-manifest，hash_basis 为 worktree_bytes；
- 当前值：本次对工作区文件计算的 sha256；
- blob：当前工作区的 `git hash-object --no-filters` 与 `git rev-parse HEAD:<path>`。

| 文件 | 基线记录的 sha256 | 当前 sha256 | 当前 blob = HEAD blob | 结论 |
|---|---|---|---|---|
| `scripts/pi_dispatch.py` | `a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4`（274717 字节） | 相同（274717 字节） | `8e7df57c91fc589895c171254e71cbc3d056c313`，相同 | 未改动 |
| `scripts/dispatch-pi.sh` | `e2e12058ef5d58b4126527b158bef8dcc04653527f7ce20544c0d7cd77bdb2f4` | 相同 | `99acff8c9a898818be00ecb4d0259e6d52b40e1b`，相同 | 未改动 |
| `tests/stub_pi.py` | `96c0d4a5ba775e9c23ce104176f1e2f0fbe6eb2925eafef5b0c5fd5c248e916a` | 相同 | `bb106194c3fb75efc14d1a625bfa7b5a26f53f19`，相同 | 未改动 |
| `tests/test_dispatch.py` | `c6fed33534b096b764145257ba5c2ce340f50cbaf483b5007097874c3bbd543e` | 相同 | `b8fdd332566ceb33049240c39d2faf1258bad43b`，相同 | 未改动 |
| `AGENTS.md` | `7571e9a9e68046f421909995ab58070f45e5aea2d48176389d8cb2c892245cc2` | 相同 | `b54cb2fcb47fcdac228eebefd4808ec715e5e528`，相同 | 未改动（修订 8 更正：P4 没有修改 AGENTS.md。保护范围的两种落实方式待用户决定，见 acceptance.md 第 9 节 (a)；若选用在 AGENTS.md 中加一行的方式，须按新基线重新核对本行） |

补充：

- `git diff HEAD --` 对上述路径以及 `.agents/`、`.claude/` 输出为空，`git status` 中也没有这些路径；
- `git grep -l codekit HEAD` 没有输出，即 HEAD 中没有文件引用 codekit；
- 工作区中引用 codekit 的只有 01 新增的文件（第 6.1 节）。
- 修订 8 补充（measured，只读核对归档）：8 次最终取证的输入清单（`evidence/final/*/pre/input-manifest.json`）中，上表 5 个文件的 sha256 与“基线记录”列相同，status 都不是修改状态。

### 6.3 回退顺序（8.2 的七步）

| 步骤 | 8.2 要求 | 本次的落点 |
|---|---|---|
| 1 | 停止新派遣进入新增入口 | 本次**没有**新增派遣入口，也没有派遣 Pi（README）。无需操作 |
| 2 | 按现有监督器处理已在运行的任务 | 没有运行中的派遣任务。基线取证用的是旧监督器 `run_supervised`，已结束，前后采样一致（baseline-report 第 4 节） |
| 3 | 封存新增证据 | 保留 `.agent/baseline/01-T1/bl-01t1-legacy-20260925/`、`.agent/baseline/01-final/`、`.agent/baseline/01-P4/` 与 `.agent/baseline/01-closure/` 的原件（修订 8 补上 `01-final/`、`01-P4/`，修订 11 补上 `01-closure/`），以及 `docs/themis-tally-v2/01-baseline/evidence/` 归档（含 `evidence/final/`、`evidence/closure/`，以各自的 `archive-manifest.json` 核对；`run-controls-final/`、`run-controls-closure/`、`inventory-items/` 以各自的 `manifest.json` 核对）；fixture 以 `manifest.json` 的逐文件摘要核对 |
| 4 | 停用新消费者 | 按第 6.1 节，不运行 01 新增的 8 个测试文件（`test_protocols.py`、`test_baseline_tool.py`、`test_codekit01_fixtures.py`、`codekit01_legacy.py` 与 4 个 `test_legacy_*.py`；修订 7 写作“4 个”，漏了 P4 新增的 4 个）与 `baseline.py`，不导入 `scripts/codekit/` |
| 5 | 恢复经核验的旧入口 | **不需要恢复**：第 6.2 节表明旧入口的字节与基线相同 |
| 6 | 新格式资源保留只读或明确不支持 | codekit-public v1 记录只存在于 fixture 中；旧入口不认识 record_type，不读取这些记录（明确不支持）；fixture 作为测试数据只读保留 |
| 7 | 重新核实基线与关键旧回归 | 运行 `python tests/test_dispatch.py`（基线为 256 checks, 0 failed，只限 Windows）。新增文件还在时，另运行 `python tests/codekit01_legacy.py --check`，确认旧投影仍然 `0 differ`；需要方法级的旧行为观测时，再按文件运行 4 个 `tests/test_legacy_*.py`（最终取证：159 个方法中 156 个 ok、3 个 POSIX 方法跳过，只限 Windows；收尾取证 `bl-01closure-test-legacy-*-20260926` 的方法集合与结果相同，修订 11 补） |

### 6.4 回退时禁止的事

- 不删除 `.agent/baseline/`、`evidence/`、fixture 或 expected 文件；
- 不改写历史合同；
- 不重新生成旧哈希，也不为了消除差异而更新 expected。旧入口字节一旦改变（包括将来经 09 裁决的合法收紧），`test_legacy_implementation_bytes_are_source_revision` 失败是预期结果，需要单独的锁定决定；判断是否漂移看 `test_legacy_*_projection_unchanged` 逐 case 列出的差异，不能靠重新生成 expected 让它们变绿（`--write-expected` 本身也要求字节等于 a4fa199）；
- 不把未知的新格式转换成空配置或旧格式；
- 不对用户仓库执行递归清理（8.4）。

## 7. 平台

| 能力 | Windows | Linux | macOS | 说明 |
|---|---|---|---|---|
| 严格 JSON 与固定快照字节（含黄金向量） | 实测通过 | NOT_RUN | NOT_RUN | 单平台通过不推导三平台（7.5） |
| fixture 字节完整性（`-text`，hash-object 过滤前后一致） | 实测通过；本机 `core.autocrlf=true` | NOT_RUN | NOT_RUN | 另有对照：未标 `-text` 的路径在 autocrlf 下摘要会变 |
| 旧实现投影的锁定 | 实测一致 | NOT_RUN | NOT_RUN | 含 Python json 的报错原文，只在 Python 3.12.10 上锁定 |
| fixture 条目的 platform_scope 登记（收尾轮，R-P11） | 188 条都在本机核对过 | NOT_RUN | NOT_RUN | 登记是声明，不是实测：expected.outcome=legacy-judgment 的 40 条（legacy 合同 6、合同负例 19、stub 流 10、事件负例 3、两份 legacy 预期）为 `["windows"]`，因为期望含临时仓库中旧 CLI 的输出、Python 报错原文或 Windows 上生成的 CRLF 字节；其余 148 条的判断由 `codekit.protocols` 对固定字节作出，登记 `["any"]`（protocols-api.md 14.1：`["any"]` 不表示已在各平台运行过） |
| stub 事件流字节 | CRLF 行尾，实测；默认测试重跑 stub 核对（`StubTests`） | NOT_RUN | NOT_RUN | 其他平台上 stub 输出的行尾与摘要没有验证，重跑核对在非 Windows 上跳过并记为 NOT_RUN；条目的 does_not_prove 已写 cross_platform_bytes |
| 词法路径拒绝 | 实测通过 | NOT_RUN | NOT_RUN | 只证明词法逻辑 |
| symlink/junction 静态越界检查 | 实测通过（01-D06）；含逐跳核对链接链（P4 第 3 轮），以及按词法折叠相对目标中的 `..`、逐字访问名称末尾带点或空格的链接（P4 第 4 轮）；P4 第 5 轮起按裁决 R-P9 定位为“静态审阅 + 纵深防御”，未识别的名称代理类重解析点与语义无法确定的链接写法失败关闭（用 FSCTL 造出的写法实测） | NOT_RUN | NOT_RUN | 不是安全访问保证（R-P9），不据此宣称消除了 TOCTOU；已检测的情形与已知不检测的情形（TOCTOU 与并发替换、检查后替换、硬链接、挂载点、尚未枚举的 NT/Win32 写法、同账户篡改）见 protocols-api.md 第 7 节；F029、F030 跳过。POSIX 上 `..` 按物理语义处理，这个分支在本机只有白盒注入（`test_A10_link_walk_physical_dotdot_branch`），没有黑盒实测 |
| 旧自测 `tests/test_dispatch.py` | 256 checks, 0 failed（1 个测试函数在 Windows 上没有运行） | NOT_RUN | NOT_RUN | 见 baseline-report 第 1 节 |

## 8. 限制、未证明事项与待办

1. **没有真实历史证据**：仓库中没有 `.agent/runs/`，`.agent/plans/` 为空。矩阵第一行的“历史合同”只是仓库内的示例与模板，真实历史运行证据的读取与审计没有测试（NOT_RUN）。
2. **没有真实 Pi 流**：事件只来自 stub，不证明真实 CLI 兼容性或厂商协议。
3. **全部是合成 fixture**：manifest 中没有 captured 条目。`test_counts_by_class_and_representation` 断言全部是 synthetic_fixture，今后加入采集原件时要改这条断言。
   - legacy、negative 条目“不声称真实兼容”P4 起由产品入口 `validate_fixture_manifest_entry` 保证（按来源类别与表示判定，作用于全部条目）；测试层规则 `check_synthetic_fixture_claims` 只再加本清单的白名单约定。captured 条目目前只有单元测试覆盖，没有真实采集样本；4.3.3 要求的“是否保留协议结构”与“来源是否可追溯”两个字段尚未进入条目结构（protocols-api 第 14.2 节“现行规则的空缺”；修订 8 补上后者）。条目结构还缺少其他规定字段，见第 10 条。**修订 9**：两个字段已按裁决 R-P11 进入条目结构（`redaction.protocol_structure_preserved`、`origin.traceable`），见第 10 条；captured 的 capture 与 traceable 规则仍只有单元测试与本清单的负例，没有真实采集样本（04）。
4. **Schema 元校验没有运行**：本机没有安装 `jsonschema`，也不得安装，所以跳过（baseline-report 记为 BLOCKED）。另外，F017（归 02）与 F029、F030（01-D06）也是跳过，不代表通过。
5. **适配器修订没有锁定**：归 04。vendor 事件的类型名与 adapter_revision 目前都是合成值。
6. **本文件的行尾**：`docs/themis-tally-v2/01-baseline/**` 还没有 `-text` 规则（baseline-report 第 10 节建议加入）。本文件为 LF，在 `core.autocrlf=true` 下提交再检出后，摘要可能改变。本任务没有修改 `.gitattributes`。**修订 8 更正：本条已过时**，`.gitattributes` 现有 `docs/themis-tally-v2/01-baseline/** -text`（01-L06），最终取证的输入清单中 `.gitattributes` 已含这条规则（acceptance.md 第 10 节 M-05）。
7. **与 P3 第二部分自述的出入**，本文按 expected 文件的实际内容填写：
   - 自述中“3 个 Markdown 负例各自报错”不准确：`md-crlf-line-endings` 在旧实现中是 0 个错误，被接受（D-12）；
   - 任务示例中“BOM 在旧入口被接受”也不准确：JSON 合同以 BOM 开头时，旧入口同样拒绝（D-03）；Markdown 以 BOM 开头时，旧入口报标题错误（D-13）；
   - 在 P3 fixture 中，“旧接受、新拒绝”的只有 D-01；清单中已实测、没有做成 fixture 的还有 D-20、D-23（第 4.3 节）。**修订 9**：D-20–D-23 已落为 fixture。现在“旧接受、新严格入口拒绝”的是 D-01 与 D-20 的 Infinity 用例；D-23 旧实现与新严格入口都接受（新严格入口不判断合同字段），修订 8 以前第 4.3 节写的“新入口 `E_ID_SYNTAX`”指的是公共记录中的标识规则，不是合同 v1 的新入口。
8. **抽查的锁定情况**：第 1 节的抽查没有被测试锁定。是否把“合同 v1 与 baseline 记录交给公共入口会被拒绝”写成回归测试，由 P4 决定。**修订 9：已处理**，收尾轮写成回归测试 `PublicEntryRejectionTests`（E20，acceptance.md M-04）；只覆盖入库的脱敏归档，不覆盖 `.agent/baseline/` 中被 Git 忽略的原件。
9. **文档 6.6 要求的选样类别（修订 8 补登；修订 9 按裁决 R-P12 更新七类的状态）**：6.6 要求选样覆盖正常、缺字段、失败、超时、取消、恢复、候选漂移等旧场景，每类有来源、缺样本如实登记；兼容比较至少包括 normalize 后的关键默认值、合同校验判断、缺证据状态、候选/补丁判断、门禁结果与旧入口状态解释。P3 的 legacy fixture 只有 `legacy/contracts/`（6 个文件）与 `legacy/stub-events/`（10 条流），锁定预期只有合同投影与 `summarize_events` 投影两类。逐类情况：

   | 类别 | 现有 fixture | 状态 |
   |---|---|---|
   | 正常 | 3 对原合同；`legacy-stub-events-ok` 等正常结束的流 | 有 |
   | 缺字段 | 合同：缺 `## Scope` 节（`negative-legacy-contract-md-missing-scope-section`）；事件：没有任何结束事件与模型证据的 `legacy-stub-events-startfail` | 部分：JSON 合同缺必填字段、消息带 usage 但缺 token 字段都没有样本 |
   | 失败 | 合同负例 19 个（收尾轮新增 D-20–D-23 的 6 个）；事件：error、model、ok-ptl-low、textcall、nosettle，以及截断、夹入坏行、重复投递 3 个负例 | 有（限合同校验与事件摘要） |
   | 超时 | 代码内联：`inline:tests/test_legacy_lifecycle.py::TimeoutTests.test_LB_LIFE_016_timeout_run_exits_1_and_pass_refused_by_g1@<L>`、`inline:tests/test_legacy_gates.py::G1ExecutionComplete.test_lb_life_016_timeout_run_exit_1_and_g1_timeout@<G>` | **旧路径已锁定，差分 NOT_RUN（新路径不存在）** |
   | 取消 | `inline:tests/test_legacy_lifecycle.py::CancelTests.test_LB_LIFE_017_ctrl_break_during_pi_run_is_cancelled_exit_1_not_130@<L>`（POSIX 的 `test_LB_LIFE_017_sigint_during_pi_run_is_cancelled_exit_1_posix` 在本机跳过，旧路径在 POSIX 上没有锁定） | 同上（限 Windows） |
   | 恢复 | `inline:tests/test_legacy_lifecycle.py::RecoverTests.test_LB_LIFE_023_recover_from_collecting_reuses_run_json_and_can_pass@<L>`、`RecoverTests.test_LB_LIFE_024_recover_refused_while_pi_alive_then_recovers_cancelled` | 同上 |
   | 候选漂移 | `inline:tests/test_legacy_gates.py::CandidateDrift.test_lb_gates_013_check_refuses_modified_candidate_and_aborted_record_blocks@<G>`、`G6Integrable.test_lb_gates_030_g6_drift_after_record` | 同上 |
   | 候选/补丁判断 | `inline:tests/test_legacy_gates.py::PatchIntegrity.test_lb_gates_006_g6_patch_missing_tampered_sha_and_roundtrip@<G>`、`PatchIntegrity.test_lb_gates_012_fresh_check_and_mutate_refuse_bad_patch` | 同上 |
   | 门禁结果 | `inline:tests/test_legacy_gates.py::G0InputConsistency.test_lb_gates_024_g0_hash_base_and_contract_failures@<G>`、`VerdictRules.test_lb_gates_032_verdict_rejection_branches` 等（G0–G6 各门见 acceptance.md 3.7） | 同上 |
   | 旧入口状态解释 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_024_wait_terminal_prints_summary_line@<C>` 等 `LegacyWaitTest` 方法 | 同上 |

   - 表中 `<L>`、`<G>`、`<C>` 依次是 `tests/test_legacy_lifecycle.py`、`tests/test_legacy_gates.py`、`tests/test_legacy_cli.py` 的完整 sha256，编写修订 9 时测得：`f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd`、`d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7`、`1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532`。收尾轮没有改动这三个文件。所列方法只是每类的代表，完整的方法与行为对应见 legacy-inventory.md 第 12 节。
   - **修订 9（裁决 R-P12）**：这七类不再记为“缺样本”。旧路径的输入由测试代码确定性构造，按 R-P12 是合法的 input_fixture_ref（形式 (b)，`inline:<测试文件>::<类>.<方法>@<测试文件 sha256>`），比较投影为 `codekit01-characterization-v1`（该方法中的断言集合）；a4fa199 在这些输入上的现状已由 P4 特征化测试锁定（最终取证 `bl-01final-test-legacy-*`，只限 Windows；修订 11 补：收尾取证 `bl-01closure-test-legacy-*-20260926` 的结果相同）。文档 6.6 的“差分”要把同一输入喂给旧路径与新兼容路径，而超时、取消、恢复、候选漂移、补丁、门禁、旧入口状态解释的新路径归 07、10，**还不存在**，所以状态是“旧路径已锁定，差分 NOT_RUN（新路径不存在）”，不是缺样本。新路径出现后，由 07、10 用同一内联输入做差分。
   - 需要规划端知悉：这些方法的输入还经过公共夹具 `tests/legacy_harness.py`（编写时 sha256 `c4e871372a35f35c59a76172ccc366a50316c5af9ad3ec4703d1fb6c27d4b974`）构造；R-P12 的引用形式只记测试文件的摘要，按字节复现输入时夹具也必须相同。
   - 缺字段一类仍如上表所列只有部分样本；这不属于 R-P12 的七类，仍按缺样本登记。
   - 修订 8 把这七类记为“缺样本”，迁移比较记 NOT_COVERED，并据此写了 legacy-inventory.md 9.10.3、9.10.4 与 acceptance.md 第 7 节第 11、12 项。那两份文件不在收尾轮本部分的可写范围内，尚未按 R-P12 同步。修订 11 补（只读核对）：legacy-inventory.md 已按 R-P12 同步，见其 9.10.6（逐行回填）、9.10.7（七类的状态）与 12.10（159 个方法的内联引用），当前 721294 字节，sha256 `9fdba24ca5de15b4cb75c206caf1e9633bb6866f0f2a8d12372ded225792adc4`；acceptance.md 第 7 节第 11、12 项在本修订时仍未同步。

10. **fixture 条目结构缺少的规定字段（修订 8 补登）**：protocols-api.md 第 14.1 节的封闭结构（manifest.json 的 171 条条目键集合与之相同）没有以下字段：6.6“封存”一步的“完整性”；1.1 对兼容 fixtures 最低标准中的“平台适用性”（现在只在 15 条的 `does_not_prove` 中以 `cross_platform_bytes` 间接表达）；附录 C.1 对真实样本要求的“采集环境”与“截取范围”；4.3.3 的“是否保留协议结构”与“来源是否可追溯”（第 3 条）。加字段会改变封闭结构、全部条目与生成器，需要规划端先出新规格。在此之前，本文不宣称 fixture 的平台适用性与完整性“明确”（acceptance.md 第 10 节 M-03）。

    **修订 9：已按裁决 R-P11 补上**（acceptance.md M-03）。条目新增 `integrity`、`platform_scope`、`capture`、`redaction.protocol_structure_preserved`、`origin.traceable`，manifest 188 条全部按下列登记规则填写（`R11Tests` 逐条断言，E18）：

    | 字段 | 登记规则 | 分布（188 条） |
    |---|---|---|
    | `integrity` | 文件是它所代表样本的完整字节时为 complete，包括值、语法或编码层面的单一故障负例（故障本身就是被测输入）；代表“证据或引用字节被截断/被破坏”的负例如实登记 | complete 184；truncated 2（`negative-legacy-events-ok-truncated-tail`、`negative-protocol-synthetic-sample-missing-final-lf`）；corrupted 2（`negative-legacy-events-ok-unparseable-line`、`negative-protocol-synthetic-sample-lf-to-crlf`）。重复投递 `negative-legacy-events-ok-duplicate-final-message-end` 没有丢失或损坏字节，登记 complete |
    | `platform_scope` | expected.outcome=legacy-judgment（旧实现判断，含临时仓库中旧 CLI 的输出、Python 3.12.10 的报错原文或 Windows 上生成的 CRLF 字节）为 `["windows"]`；其余由 `codekit.protocols` 对固定字节判断，为 `["any"]` | windows 40（legacy 18 与从 legacy 派生的负例 22）；any 148（synthetic 13、协议负例 135） |
    | `capture` | 本清单没有 captured 条目，全部为 null | null 188 |
    | `redaction.protocol_structure_preserved` | redaction.applied=false 的条目没有脱敏步骤，写 null；stub 流的 session.cwd 占位替换（applied=true）只换一个字符串值，写 true | true 10；null 178 |
    | `origin.traceable` | 全部为 true：legacy 按 source_revision 与 source_path/source_test_id 追溯；synthetic 按设计文档修订或生成代码的确定性构造追溯；negative 按 derived_from 与确定性字节变换复现 | true 188 |

    按来源类别合计：legacy 18（complete、windows）；negative 157（从 legacy 派生 22：windows，complete 20、truncated 1、corrupted 1；协议负例 135：any，complete 133、truncated 1、corrupted 1）；synthetic 13（complete、any）。本清单没有条目声明第 14.2 节第 5 步受控词表中的完整运行流或协议字段语义一类能力（修订 10 按受控词表重新核对：188 条的 proves 都不在词表内，改为词表判定后整份清单仍通过），所以该步的限制对现有条目不起作用；它们在清单级的效果由 `R11Tests.test_manifest_level_errors_carry_entry_prefix` 在真实条目的改写副本上核对。

    仍未证明的部分：`platform_scope` 与 `traceable` 是登记者的声明，产品入口不核对追溯链是否完整，也不代表已在所列平台运行（Linux、macOS 仍为 NOT_RUN）；`capture` 只有结构规则与负例，没有真实采集样本（04）。

## 9. 故障恢复（8.3）与临时目录清理（8.4）的落点（修订 8 补）

修订 7 以前，本文开头写“依据 8.1–8.4”，但只有第 2 节对应 8.1、第 6 节对应 8.2，8.3 没有逐行落点，8.4 只有第 6.4 节末条一行。本节逐行补齐。

- 证据列只引用最终取证中能逐方法追溯的结果，编号与 acceptance.md 2.3 相同：
  - EV-02：`bl-01final-test-protocols-20260925`，`evidence/final/bl-01final-test-protocols-20260925/run/stderr.bin`，sha256 `1f30be24ba3b38c4b56e54a01a076e74b630c5cdcb89c4eeb975e84211e9de36`；
  - EV-04：`bl-01final-test-baseline-tool-20260925`，`evidence/final/bl-01final-test-baseline-tool-20260925/run/stderr.bin`，sha256 `1cf45a96ef531b7df6f8eec633302127c9e77186ae44a6670f8fe1509840eb4a`。
- **修订 11 补**：最终取证已被收尾取证取代（保留为历史证据）。下表引用 EV-02、EV-04 的方法，在收尾取证的对应归档中也都逐条是 `ok`（修订 11 逐条核对，measured）。本文另用以下三个编号指收尾取证的归档；它们是本文自用的编号，acceptance.md 2.3 尚未收录收尾取证：
  - EV-C02：`bl-01closure-test-protocols-20260926`，`evidence/closure/bl-01closure-test-protocols-20260926/run/stderr.bin`，sha256 `5b81e659c60f296503dd99e836a938fa45134ffe597fb960a204b56ee65354c8`；
  - EV-C04：`bl-01closure-test-baseline-tool-20260926`，`evidence/closure/bl-01closure-test-baseline-tool-20260926/run/stderr.bin`，sha256 `024b9d508c236c504ee277b9aa07db14f45ad32235d547c1d161002121f22863`；
  - EV-C08：`bl-01closure-test-codekit01-fixtures-v-20260926`（`-v` 逐条模式），`evidence/closure/bl-01closure-test-codekit01-fixtures-v-20260926/run/stderr.bin`，sha256 `95faa68cea9315a4a73cc4bfc4223916e56b8eb1b9e5694fa1415fdf1c8b169a`。
- 下表所列方法在上述归档输出中都是 `ok`（修订 8 逐条核对，measured）。只限 Windows，Linux、macOS 为 NOT_RUN。
- 修订 9 新增的 `CredentialScanTests`、`CleanupOwnershipTests` 与修订 10 新增的 `HarnessCleanupOwnershipTests`（`tests/test_codekit01_fixtures.py`）不在上述归档中：它们只有第 1 节记录的仓库内运行结果（逐方法 `ok`，没有归档），要作为证据引用须重新取证。**修订 11 补**：收尾取证 EV-C08 已归档这三类的逐条结果，`CredentialScanTests` 4 个（stderr 第 19–25 行）、`CleanupOwnershipTests` 10 个（第 1–13 行）、`HarnessCleanupOwnershipTests` 11 个（第 42–63 行）都是 `ok`；同一归档中 `StubTests.test_stub_cwd_placeholder_and_no_local_paths` 也有逐条结果（第 93 行，`ok`）。方法名与这些裁决的对应只是按名称的静态对应，本文没有复核断言内容（INDEX.md 4.3 节）。
- “01 的落点”一列是源码与文档的静态核对（source_inspected）。

### 9.1 8.3 故障恢复决策表的逐行落点

| 8.3 的故障 | 8.3 的要求（立即处理 → 恢复与升级） | 01 的落点 | 证据（Windows） | 未落实的部分与归属 |
|---|---|---|---|---|
| 日志目录写入失败或磁盘满 | 标记采集不完整，停止发布有效引用 → 修复环境后新建取证记录，保留旧失败 | 取证工具：run 输出目录写不出时记 `execution_status=incomplete`，被测命令不运行。封存：`seal_bytes` 在发布前遇到环境类 OSError 时原样抛出，不返回引用，不残留文件（protocols-api.md 第 18 节第 13 条） | EV-04 `CaptureTests.test_run_output_write_failure_is_incomplete_and_command_not_run`（用预先存在的 run/ 目录制造 FileExistsError，模拟写失败）；EV-02 `SealingTests.test_A13_seal_failure_leaves_only_empty_new_parents`（白盒注入 `os.link` 的 OSError） | 没有真实的磁盘满注入。“修复环境后新建取证记录、保留旧失败”是操作规程，取证工具不自动执行（规划端） |
| 封存文件成功、索引失败 | 记录未引用候选，不伪造索引成功 → 按相同字节或身份幂等补录，或受控清理 | `seal_bytes`：index_commit 失败时报 `E_RESOURCE_INDEX_FAILED`（retryable），不返回引用，文件作为未引用候选保留；相同字节再次封存是幂等的 | EV-02 `SealingTests.test_F048_index_failure_leaves_unreferenced_candidate`、`test_F048_index_failure_any_exception`、`test_A13_seal_idempotent_same_bytes` | “受控清理”没有实现：01 不清理未引用候选（8.4），由持久存储的实现模块决定（07、04） |
| 索引引用的文件不可读或哈希不符 | 阻断消费与审核 → 核对来源、权限或损坏，不更新期望哈希来消错 | `read_sealed`：文件不存在报 `E_RESOURCE_MISSING`，内容被改报 `E_RESOURCE_HASH_MISMATCH`，不返回字节，也不修改引用中的期望摘要；`verify_resource_bytes` 同样在固定字节上核对 | EV-02 `SealingTests.test_A13_read_sealed_missing_and_tampered`、`ResourceRefTests.test_F034_sha_format_vs_content_mismatch` | “阻断审核”由消费方执行（03）；核对来源与权限是人工流程 |
| 事件序号冲突 | 隔离冲突并冻结受影响视图 → 对照持久日志与来源，交给 04、07 | `assess_event_log` 把冲突的 seq 隔离在 events 之外，`complete=false`；`recover_next_seq`、`append_event` 报 `E_EVENT_REPLAY_CONFLICT`，不修改 state | EV-02 `EventTests.test_F038_same_seq_different_content`、`test_F038_dict_equal_but_bytes_different_is_conflict` | “冻结受影响视图”没有实现：01 没有派生视图层（4.3.2 的派生视图修订归 04，见 acceptance.md 第 8 节）；对照持久日志与来源归 04、07 |
| 基线前后漂移 | 保留日志，但撤销该运行作为一致基线证明的资格 → 重新绑定实际输入再运行 | 取证工具前后双采样，发生漂移时记 `baseline_consistent=false`，保留全部输出；报告规则不把它记为 PASS（baseline-report 第 8 节） | EV-04 `CaptureTests.test_modifying_tracked_file_is_drift`、`test_new_untracked_file_is_drift`、`test_ignored_name_change_is_drift`（01-F050 的其余方法见 acceptance.md 第 4 节） | 9 次真实取证都没有发生漂移，漂移分支只在临时仓库中实测 |
| fixture 含真实凭据 | 停止分发，限制访问并启动凭据处置 → 脱敏后新建修订，保留受控事故记录 | 修订 8：**没有实现**；修订 9：**发现**已由测试实现（凭据形态扫描，见下一列），**处置**仍没有实现。现有的预防措施：fixture 都是合成样本或 a4fa199 的仓库原字节，manifest 中除 stub 流的 cwd 占位替换外全部条目 `redaction.applied=false`；stub 流中的本机工作目录替换为占位值（`StubTests.test_stub_cwd_placeholder_and_no_local_paths`，只有命令级证据）；取证归档另有脱敏与凭据模式扫描（baseline-report L-EVID-SECRETS，只针对 `evidence/`） | 修订 8：无。**修订 9**：`CredentialScanTests`（收尾轮，E19）逐字节扫描 `tests/fixtures/codekit01/` 下的全部 189 个文件（原字节、UTF-16 LE/BE 各两种对齐的 ASCII 视图、能严格解析的 JSON/JSONL 中的每个字符串），命中非白名单的凭据形态即失败，失败信息只给文件、视图、偏移与规则名，不回显值；本次没有非白名单命中（测试只断言这一点）。“没有白名单放行”是修订 12 的静态核对（fixture 目录中没有白名单标记，source_inspected），不是运行结论（E19）。对照用例核对 9 条规则在 6 种载体中都能发现。**修订 10**：规则增加到 15 条（Stripe、Hugging Face、GitLab、npm 令牌，HTTP Basic 认证头，URL 内嵌口令），每条规则另有其他前缀的对照样本（共 38 个），真实扫描核对已扫描的文件数与字节数（E19） | 扫描是形态匹配，不是完整的秘密检测。**只发现 E19 列出的 15 类形态**：Bearer 令牌、`sk-` 前缀密钥、GitHub、Slack、PEM 私钥块、AWS 访问键 ID、Google API key、JWT、凭据类键名的长随机值、Stripe、Hugging Face、GitLab、npm、HTTP Basic、URL 内嵌口令；清单之外的形态不会被发现（例如没有固定前缀、也不在凭据类键名、Bearer/Basic 认证头或 URL 写法中的口令，其他厂商的专有前缀，短于规则最小长度的值；修订 9 写的“只漏掉没有固定前缀、也不在凭据类键名下的口令”低估了缺口，修订 10 更正）。发现后的处置（停止分发、限制访问、凭据处置、事故记录）仍没有流程，归规划端与用户（授权主体）；测试失败本身只起“停止”的作用。采集真实样本时的脱敏与扫描归 04 |
| 未知 Schema 或平台功能 | 拒绝对应能力 → 升级实现或收窄能力声明，不猜默认值 | `route_public_record` 与各记录的版本检查：未知版本报 `E_SCHEMA_VERSION_UNSUPPORTED`，不回退 v1；未知记录类型报 `E_COMPAT_UNSUPPORTED`；`platform_from_system` 对未知系统报 `E_COMPAT_UNSUPPORTED`，不猜 linux | EV-02 `SchemaRoutingTests.test_F014_unknown_version_no_legacy_fallback`、`test_A09_route_expected_type_and_record_type`、`IdentifierTests.test_A08_platform_from_system` | — |
| 临时目录归属不明 | 停止清理 → 人工确认；不对用户仓库执行递归删除 | 见 9.2：`tests/test_baseline_tool.py` 的 `TempArea`、（修订 9 起）`tests/codekit01_legacy.py` 的 `_rmtree` 与 `tests/legacy_harness.py` 的 `remove_tree` 在删除前核对归属，不满足时拒绝删除；产品代码（`baseline.py`、`sealing.py`）不做递归删除 | 修订 9：`CleanupOwnershipTests`（E22）。修订 10：`HarnessCleanupOwnershipTests`（E23，harness 一侧此前没有回归测试） | 两处测试工具都不防核对与删除之间的并发替换（同账户的 TOCTOU）。`tests/legacy_harness.py` 的字节在最终取证之后已改变（归属核对由收尾轮加入），按 01-L05 重新取证之前，特征化测试的归档证据绑定的是旧字节；acceptance.md 第 7 节第 17 项与 R-12 的“harness 不核对”需要规划端按本行更新。**修订 11 补**：收尾取证已按 01-L05 与 R-01 重新取证，`bl-01closure-test-legacy-*-20260926` 与 EV-C08 绑定的是收尾取证输入清单记录的 harness 字节（sha256 `c4e871372a35f35c59a76172ccc366a50316c5af9ad3ec4703d1fb6c27d4b974`），4 个特征化测试文件的方法集合与结果和最终取证相同 |

### 9.2 8.4 清理代码的归属核对

8.4 要求清理前同时核对预期父目录、本任务创建的随机目录名或标记、真实路径与任务所有权；不确定时不递归删除。01 新增代码中所有删除文件或目录的位置如下（source_inspected，2026-09-26）。

| 位置 | 删除方式 | 是否核对归属 | 结论 |
|---|---|---|---|
| `scripts/codekit/baseline.py:980-986`（capture 拒绝未被忽略的仓库内取证目录时） | 对本次刚创建的取证目录及其新建的父目录调用 `os.rmdir`，遇到非空目录即停止 | 只删空目录，不递归 | 符合“不确定时不递归删除” |
| `scripts/codekit/sealing.py:245-248` `_remove_quietly` | `os.unlink` 本次写入的 `.codekit-seal-` 临时文件，失败时保留 | 只删自己创建的单个文件；发布前失败时本次新建的父目录不回滚（只会残留空目录，`test_A13_seal_failure_leaves_only_empty_new_parents`） | 符合 |
| `tests/test_baseline_tool.py:75-91` `TempArea.cleanup` | `shutil.rmtree` | **核对**：真实路径的父目录必须是系统临时目录，目录名必须以本测试的前缀开头，否则报错、不删除 | 部分符合：核对了父目录与前缀，没有标记文件与所有权核对 |
| `tests/legacy_harness.py:1124` `remove_tree`（经 `_remove_owned_once`，:1071；修订 8 记录时在 :865-883，不核对）。区域由 `make_temp_area`（:996）建立。调用处：`_cleanup_work`（:1259，删除本用例的临时区域）、`make_repo`（:1398，删除临时区域下的同名仓库）、`tests/test_legacy_lifecycle.py:862`（删除测试仓库中的锁目录） | 区域内的子路径：`shutil.rmtree`（按核对过的真实路径）；区域本身：先逐项删除标记以外的内容（链接与联接只删条目本身，不进入目标），最后删标记与根目录。只读文件先改权限；`OSError` 时最多重试 5 次，每次重试前重新核对 | **核对**（修订 10 更正，同一轮已由另一位实施者加入）：`make_temp_area` 用 `mkdtemp(prefix="codekit-legacy-")` 建区域，记录根目录的真实路径与目录身份，以独占方式写入随机令牌标记（令牌只在本进程内存中）；`remove_tree` 删除前核对五项：路径落在本进程登记的区域内；区域根是 `realpath(tempfile.gettempdir())` 的直接子目录（逐段比较）且目录名以 `codekit-legacy-` 开头（`_verify_area_location`，:946）；根目录的真实路径与目录身份（st_dev, st_ino）与创建时相同、不是链接或联接（`_verify_area_root`，:958）；标记是普通文件，内容与令牌逐字节相同（`_verify_area_marker`，:973）；待删路径本身不是链接或联接。任一不满足抛 `CleanupOwnershipError`，不删除、不重试。已删除区域中新出现的路径一律拒绝 | 符合 8.4 的核对要求（`HarnessCleanupOwnershipTests` 逐项对照，E23；修订 10 之前没有回归测试）。不防同账户的 TOCTOU。区域根是联接时由“真实路径落在登记区域外”先行拒绝，根目录的链接检查是纵深防御（单独放宽它不改变结果）。`remove_tree` 只用于目录：对区域内的普通文件调用时，`shutil.rmtree` 报 `NotADirectoryError`，重试后原样抛出（现有调用都传目录，修订 10 实测发现，未改 harness） |
| `tests/codekit01_legacy.py:814` `_rmtree`（修订 9 起；修订 8 记录时在 :645-650，不核对）。调用处 :710、:992、:1081 删除同一函数内 `_make_owned_tempdir`（:763）建的目录；`tests/test_codekit01_fixtures.py` 的生成护栏链接实测（:2216）、`CleanupOwnershipTests` 与 `HarnessCleanupOwnershipTests` 的替身目录也经它删除 | `shutil.rmtree`（按核对过的真实路径） | **核对**（`ownership_problem`，:776）：目标不是链接或重解析点且是目录；真实路径的父目录就是 `tempfile.gettempdir()` 的真实路径（逐段比较，不做字符串前缀比较）；目录名以本工具登记的前缀开头；目录由本进程建立并登记；目录内的所有权标记是普通文件，内容与本进程保存的随机令牌相同（令牌不写入其他地方，不能从磁盘伪造）。任一不满足报 `CleanupRefused`，不删除任何东西；删除时先注销登记 | 符合 8.4 的四项核对（`CleanupOwnershipTests` 逐项对照，E22；修订 10 补上标记末尾多字节、标记是链接、删除后注销登记三项的断言）。不防检查与删除之间的并发替换（同账户的 TOCTOU） |
| `tests/test_protocols.py` 中的 `tempfile.TemporaryDirectory`（`tests/test_codekit01_fixtures.py` 修订 9 起不再使用） | 标准库的递归清理 | 只删除它自己创建的目录，没有另行核对真实路径；测试建的目录链接先用 `os.rmdir` 单独删除（例如 `test_codekit01_fixtures.py:2211` 的生成护栏实测，修订 9 起它的临时区域改由 `_rmtree` 删除） | 依赖标准库，没有 8.4 所说的真实路径与所有权核对（`test_protocols.py` 不在收尾轮本部分的范围） |
| `addCleanup(os.rmdir)`、`addCleanup(os.unlink)` 与测试仓库内的单个文件删除（例如 `tests/codekit01_legacy.py:693`、`tests/test_legacy_gates.py:95`、`tests/test_codekit01_fixtures.py` 的 `CleanupOwnershipTests`） | 删除单个链接、空目录或文件 | 路径在测试自建的临时区域内 | 非递归，影响限于临时区域 |

旧自测 `tests/test_dispatch.py` 的清理（`remove_tree`，:94-100）属于受保护的旧文件，不在 01 的修改范围内，本表不列。
