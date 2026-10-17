# 01 当前验收与独立复审（2026-09-26 续接）

本记录是当前验收入口。原 acceptance.md 第 0–6 节、baseline-report 修订 7 与 EV-C 记录保留历史时点，不用当前结果倒改历史。用户要求验证成果、按推荐处理问题、完善第一阶段；本轮直接实施，无 Pi 派遣。

## 本轮修复与复审

| 项目 | 原问题 | 当前处理与证据 |
|---|---|---|
| B-01 | baseline 的 lstat 失败或打开后类型变化没有被计入采样不完整 | 统一归入 read_error；两个故障注入先红后绿，合法已跟踪删除对照通过。独立审查者另用纯内存复现，修后 complete=false、baseline_consistent=null |
| B-02 | capture-id 正则 match 接受尾 LF，含 129 字符变体 | 使用 fullmatch；尾 LF、128+LF 先红后绿，合法 128 字符与 129 字符边界覆盖 |
| T-01 | Windows 重解析能力缺失时 subTest 跳过后仍索引缺失文本 | 方法外能力探针；文本形状断言留在各自 subTest，局部跳过也不跨块访问 |
| T-02 / M-15 | baseline TempArea 只凭父目录/前缀递归清理 | 复用 legacy_harness 的进程内所有权、目录身份和标记核对，并绑定本实例创建路径。路径改指、标记篡改两测试先红后绿 |
| F-01 / 第7节24 | 缺 JSON 合同必填字段与 usage token 缺失两类 legacy 样本 | 新增两个单一故障样本及锁定投影，原有全部 case 0 变化；详见 fixture-completion.md |
| F-02 / M-16 | fixture 扫描丢弃白名单放行结果 | 实际 fixture 扫描断言 allowed 为空；临时加入合成白名单标记的反测先通过、强化后失败、恢复后通过 |
| D-01 / 第7节25 | 基线报告 13 项照录过时 | JSON 新增 current_acceptance_ref 和 transcript_status，原13项历史内容完整保留；当前检索转到本文 |
| A09 元校验 | jsonschema 未安装导致跳过 | 独立 venv 安装 4.26.0，Draft 2020-12 check_schema 与五个文档样例实测通过；依赖版本固定在 verification-requirements.txt |

独立代码审查由未参与代码实现的子代理完成；收尾口径和最终证据复审由另一子代理完成（该代理参与了基线报告历史/当前指针整理，其审查阶段只读）。第三代理实施 fixture 后由代码审查者核对 diff。审查发现的 B-01、B-02 已处理；最终 diff 的取证修复、TempArea、Windows subTest 和 fixture 变更未发现新的重要问题。代码审查者只做只读检查与自包含故障注入；全量重跑与归档由主代理执行。这是直接实现的独立子代理审查，不称为 Pi 验收或 codex exec 记录。

## 最终复跑

**Windows 当前验收：十组被测命令退出 0，零失败；每组取证 execution_status=complete、baseline_consistent=true。** unittest 合计 623 个方法，616 个通过、7 个跳过；另有旧自测 256 checks、兼容比对 40 checks、stub 重生成 10 checks，全部零失败/零差异。总数包含跳过项，不把跳过计成通过。

| 组 / 被测命令（使用验证环境 Python） | 总数 | 通过 | 跳过 | 失败 | 证据 |
|---|---:|---:|---:|---:|---|
| `tests/test_dispatch.py` | 256 | 256 | 0 | 0 | [归档清单](evidence/followup/bl-01followup-dispatch-20260926/archive-manifest.json) |
| `tests/test_protocols.py` | 342 | 338 | 4 | 0 | [归档清单](evidence/followup/bl-01followup-protocols-20260926/archive-manifest.json) |
| `tests/test_codekit01_fixtures.py -v` | 77 | 77 | 0 | 0 | [归档清单](evidence/followup/bl-01followup-fixtures-20260926/archive-manifest.json) |
| `tests/test_baseline_tool.py` | 45 | 45 | 0 | 0 | [归档清单](evidence/followup/bl-01followup-baseline-20260926/archive-manifest.json) |
| `tests/test_legacy_gates.py` | 24 | 24 | 0 | 0 | [归档清单](evidence/followup/bl-01followup-gates-20260926/archive-manifest.json) |
| `tests/test_legacy_lifecycle.py` | 26 | 24 | 2 | 0 | [归档清单](evidence/followup/bl-01followup-lifecycle-20260926/archive-manifest.json) |
| `tests/test_legacy_cli.py` | 75 | 74 | 1 | 0 | [归档清单](evidence/followup/bl-01followup-cli-20260926/archive-manifest.json) |
| `tests/test_legacy_events.py` | 34 | 34 | 0 | 0 | [归档清单](evidence/followup/bl-01followup-events-20260926/archive-manifest.json) |
| `tests/codekit01_legacy.py --check` | 40 | 40 | 0 | 0 | [归档清单](evidence/followup/bl-01followup-legacy-check-20260926/archive-manifest.json) |
| `tests/codekit01_legacy.py --check-stub-regen` | 10 | 10 | 0 | 0 | [归档清单](evidence/followup/bl-01followup-stub-regen-20260926/archive-manifest.json) |

机器记录：[verification-summary.json](evidence/followup/verification-summary.json)。协议的 4 个跳过是 F017、F029、F030 和 Windows FSCTL_SET_REPARSE_POINT 权限不足（winerror 1314）；旧生命周期 2 个、CLI 1 个为 POSIX 专用。Schema 元校验在该次 342 项运行中实际通过，五样例也通过。

最初基准工具取证得到 45 tests / 1 failure：TempArea 引入所有权标记后，导入测试仍断言目录绝对为空。已改为导入前后条目与字节完全一致，保留原进程/模块加载限制；独立审查确认未弱化。随后完整重跑 45 项通过。[失败归档](evidence/followup-initial-failure/bl-01followup-baseline-20260926/archive-manifest.json) 完整保留，不当成成功证据。旧取证 CLI 的退出 0 只代表采集完成；本次逐项核对 run.returncode 与汇总行，后续 runner v2 也同时判这两者与 baseline_consistent。

九组结果来自 `.agent/baseline/01-followup-20260926-r2/`；基准组最终结果来自 `-r3/`。两组原件均被忽略，脱敏归档独立于原 EV-C。本轮全套之前一次 runner 环境自检拒绝 PYTHONIOENCODING，发生在任何被测进程启动之前，已修正后使用新目录运行；没有把该次启动失败算成测试结果。

每组独立创建空 Pi 设置目录、空 pyc 前缀与空 Git 用户配置；PATH 上 pi/claude/codex 均不可发现；按名称过滤凭据变量。十组 pyc/Pi 目录运行前后条目数均为 0，见归档 controls。网络没有操作系统级隔离，不宣称网络沙箱。验证依赖只在取证前从 PyPI 安装进独立 venv。

前后输入闭包分别一致；基准重跑因测试修正及新增 runner 文件而使用另一闭包，不声称十组共用单一闭包：

- `15d03d78da68ef11143ec58f4f1cdb1f8edbab08a513be44cd681f586c5a57f5`
- `b24a979b7327911332937d6dbed30b3da61d65167fa703c3a04c2adab9f5149e`

归档时逐一复核 11 份 archive-manifest 中全部文件的 archived_bytes 与 archived_sha256；完成后对各组测试入口、核心实现及共享 harness 做 78 项当前字节/取证输入摘要核对，全部相等。旧自测 stdout 与最初 bl-01t1 输出逐字节相同。原 48 个调度器、规则、自测、stub、技能文件与 a4fa199 字节相同；公共 protocols.py、sealing.py、Schema 与 182ef16 字节相同。配置的 10 条模式做了 21 个真实 evaluate_scope 检查（原拼写、大写与未保护路径对照），结果正确，见 [protection-check.json](evidence/run-controls-followup/protection-check.json)。原有全部 expected case 逐 key 不变，仅追加两类案例。

## A01–A16 当前判定

本表沿用 acceptance.md 的方法级需求映射，以本轮输出更新运行结果，不扩大 01 的约定范围。

| 验收项 | Windows 当前结论 | 主要依据与范围 |
|---|---|---|
| A01 | PASS（限定范围） | 十组完整采样及前后不变；闭包仍 partial；工具读取失败不再误报完整 |
| A02 | 01 范围内 PASS | 190 个登记 fixture；77 项测试、40/10 比对通过；缺字段两类已补齐；未来新路径与真实历史事件未测 |
| A03 | 01 范围内 PASS | 公共协议快照/字节用例；配置语义投影归 02 |
| A04、A05 | PASS | 严格 JSON、错误与状态区分用例 |
| A06 | 01 范围内 PASS | unknown 与币种/观测语义；真实 Pi usage 解释、记账归 04/07 |
| A07 | PASS（限定范围） | 159 个旧特征化方法，156 通过、3 个 POSIX 跳过；G5 采用已裁定的不变式映射；真实竞态等缺口保留 |
| A08 | 01 范围内 PASS | 标识、归属与预算根协议；持久恢复由后续模块完成 |
| A09 | PASS | Schema 摘要、路由与降级防护；jsonschema 元校验及五样例实际通过 |
| A10 | 01 范围内 PASS | 静态路径审核的已运行用例；Windows 特殊重解析点实测本环境跳过；不承诺生产安全访问 |
| A11 | 01 范围内 PASS | seq/幂等/冲突与完整性协议；事务日志归 07 |
| A12 | 01 范围内 PASS | provenance/来源规则及191文件扫描；扫描白名单命中为0；真实 captured 归 04 |
| A13 | 01 范围内 PASS | 封存发布/补偿用例；崩溃持久性与跨组件事务未实现 |
| A14 | PASS | 无副作用导入；基准工具组的所有权标记适配后完整通过 |
| A15 | 不记 PASS | 仅 Windows；Linux/macOS NOT_RUN，不能从本机结果推导 |
| A16 | PASS | 参考验证、公共协议与旧自测分组；受控环境隔离及记录明确 |

## 当前裁决与限制

- 第7节20–23 项沿用 closure-rulings：pyc 操作者记录可以按 source_reported 接受；仓库外工具/标准库不纳入工作区字节闭包；G5 以恒通过不变式映射；旧函数/check 使用扩展 inline 写法。
- M-13：remove_tree 明确定义为只接收目录，现有调用符合；不扩展成通用文件删除 API，普通文件调用错误属于边界，作为文档约束关闭。
- M-14：inline 只含测试摘要时，必须连同对应 input-manifest 中 legacy_harness.py 摘要消费；不用孤立 inline 字符串声称可复现。该规则关闭引用口径事项。
- M-15：自定义 TempArea 已补强；protocols 测试的标准库 TemporaryDirectory 由测试自行创建并管理，接受其既有使用边界，不把它声明为生产级安全删除。
- M-09：谁删除过历史临时物无可靠记录，保留历史未知，不要求用户凭记忆补证，不伪造完成记录。
- 只有 Windows 实测。**用户于 2026-09-26 明确决定：Linux/macOS 现在不推进，后续由插件实现。** 因此跨平台实测移交后续插件，不阻断本轮已授权范围的收尾；Linux/macOS 仍为 NOT_RUN，A15 整项不记 PASS。本轮没有创建或启动 CI workflow，没有推送。
- F017 归 02；F029/F030 与生产级文件安全归后续模块（01-D06/R-P9）；真实 Pi/captured 流归 04；事务日志、唯一记账与崩溃持久性归 07（与04集成）；未来兼容新路径差分归 07/10。这些都不由本轮补齐冒称通过。

## 复跑入口与提交边界

验证环境：`python -m venv <venv>`，再用该环境 Python 执行 `-m pip install -r docs/themis-tally-v2/01-baseline/verification-requirements.txt`。随后按归档的 [verification-runner-v2.py](evidence/run-controls-followup/verification-runner-v2.py) 使用该解释器、仓库根、全新的 `.agent/baseline/` 输出目录运行；解释器加 `-B -X pycache_prefix=<新空目录>`。后续插件取得 Linux/macOS 环境后，先确保 Git 历史包含 `a4fa199`、固定依赖已安装、隔离后的 PATH 可找到 Git/Bash/dirname；推荐沿用 CPython 3.12.10。使用 runner 的标签参数选择 `dispatch protocols fixtures baseline gates lifecycle cli events legacy-check` 九组。`stub-regen` 锁定 Windows CRLF 原字节，非 Windows 不执行该比对，也不能通过重生成 expected 消除差异。各平台使用独立、全新的输出与归档目录；真实结果须独立审查，不能预填 PASS。

只提交本轮逐路径核对的代码、测试、fixture 与阶段文档/脱敏归档。原始 evidence、被忽略 venv 与取证原件、用户根 README 修改、docs 六项重命名、根 themis-tally-v2 与字体目录不进入提交。不推送。

最终证据归档后只更新验收说明和提交记录；被测代码字节经上述摘要核对保持一致。P0–P4 在 Windows、01 约定范围内完成；A15 与明确移交项保持上述限制，不把本结论写成“三平台全部通过”。

最终独立复审报告见 [independent-review.md](independent-review.md)：复算全部结果、核对十组 capture 与首次失败、抽验九份输出文件，未发现重要文案或验收缺口。归档后另跑 PublicEntryRejectionTests，3 项通过，覆盖新增内部证据记录仍被公共入口拒绝。代码与手写文档的 diff whitespace 检查通过；原始输出和 CRLF 字节 fixture 按证据保真保留，不据此做空白格式化。

## 用户确认的阶段收尾边界

2026-09-26，用户回复：“现在可以不推进这个，后续会推出插件来实现这个”，所指为待补的 Linux/macOS 实测。第一阶段的分阶段实施、代码补齐、Windows 验收、独立复审、证据归档和本地提交已完成；跨平台验证按用户决定移交，不继续准备 CI、安装操作系统或请求主机。此决定不把 A15 改判 PASS，也不取消已有的平台限制。
