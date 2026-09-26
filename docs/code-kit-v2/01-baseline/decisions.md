# 01 决策采纳记录（01-D01–D10）

记录日期：2026-09-25。依据：01 审阅增强版 9.3 节。

采纳依据：用户在本次对话中要求“按 01 文档分阶段、分子任务完成”。据此，文档中标为“新增设计建议”且属于 01 自身职责的项，按文档推荐值采纳为**新协议**的规则；属于其他模块的项只登记接口与边界，不在 01 中实现。所有采纳项只适用于新写入的公共记录，不改写 v1 合同、历史证据或旧入口语义（附录 D.2）。

| 编号 | 决策 | 结论 | 状态 | 生效范围与说明 |
|---|---|---|---|---|
| 01-D01 | 新 request/run 格式 | `req-` / `run-` 加 32 位小写十六进制（UUID4 的 hex 形式） | 已采纳 | 只用于新记录；由可信核心分配，分配时仍需检查持久化唯一性（由 07 负责） |
| 01-D02 | 公共家族与记录版本 | 家族 `codekit-public`，公共记录 `schema_version=1`，按 `record_type` 分派 | 已采纳 | 与合同 schema v1、工具版本 2.2.2 相互独立；Schema `$id` 为 `urn:codekit:public-protocol:1` |
| 01-D03 | `attempt` 首次基数和恢复规则 | 旧实现首个编号为 **1**（`number = max(existing, default=0) + 1`，`scripts/pi_dispatch.py:2619-2623`）；只有 `prepare` 使编号前进，`collect --recover` 与预检失败后再次 `run` 沿用原编号 | 已取证（source_inspected，测试 `test_happy` 等在基线运行中通过） | 新 Schema 的 `attempt` 下界 0 只表示格式允许，不平移历史编号；详见 `legacy-inventory.md` LB-LIFE 区域 |
| 01-D04 | JSON 字节/深度/整数上限 | 单文档 1 MiB、嵌套 64 层、整数 `0..2^53-1`（带符号时绝对值不超过 2^53-1） | 已采纳 | 以函数参数形式可调；不是既有规模承诺 |
| 01-D05 | 配置投影与 `_...` 例外 | 01 不实现配置投影，不全局删除 `_...` 字段；快照函数只接受已由 02 完成投影的对象 | 已采纳（边界） | 字段分类规则归 02 |
| 01-D06 | 平台安全文件访问 | 01 只提供词法校验与静态解析（审阅用）；生产级安全 open/create 不在 01 实现 | 已采纳（边界） | 本机 Windows 的 symlink/junction 静态越界检查作为实测证据记录；不据此宣称消除 TOCTOU |
| 01-D07 | 关键协议类型与结束条件 | 01 只提供事件封装、`known_required/known_optional/unknown` 分类接口 | 移交 04 | 真实 Pi 事件类型与结束判定由 04 登记 |
| 01-D08 | 用量范围、去重与费用修订 | 01 提供用量观测校验与“观测视图”（按币种分组、未知传播、修订链、重放去重），不做记账或扣减 | 已采纳（边界） | 07 是唯一记账模块 |
| 01-D09 | 旧歧义输入与新入口收紧 | 历史输入只读保留并按旧规则解释；新入口按严格规则拒绝；差异登记在兼容矩阵 | 已采纳 | 见 `compatibility-matrix.md` |
| 01-D10 | 参考代码支持平台/解释器 | 代码以 Python 3.10+ 语法编写；本次实测平台为 Windows Server 2025 + Python 3.12.10 | 已采纳（有限） | Linux/macOS 记为 NOT_RUN，不从 Windows 结果推导 |

## 实施中新增的局部决定

| 编号 | 决定 | 理由 |
|---|---|---|
| 01-L01 | 公共协议模块位于 `scripts/codekit/protocols.py`，只依赖标准库 | 文档 4.4.3、5.1；本机无 `jsonschema`，且不授权安装依赖 |
| 01-L02 | 本地 Schema 位于 `schemas/codekit-public-v1.schema.json`，内容取自附录 A | 文档 5.1；以附录 E.2 摘要核对抽取字节 |
| 01-L03 | 原始取证写入 `.agent/baseline/`（加入 `.gitignore`，并在输入清单中精确排除）；脱敏后的归档副本放在 `docs/code-kit-v2/01-baseline/evidence/` | 文档 6.2：证据不写入尚未采集完成的输入范围；仓库外路径不进入业务 `path` |
| 01-L04 | 新测试使用标准库 `unittest`，按文件单独运行，不用 `unittest discover` | `tests/test_dispatch.py` 在导入时就创建临时目录，被 discover 导入会留下目录 |
| 01-L05 | 旧自测取证在受控环境运行：PATH 去掉真实 pi/claude/codex 所在目录、`PI_CODING_AGENT_DIR` 指向空目录、去掉会话令牌变量 | P0.2 静态核实：`doctor` 会运行 PATH 上真实的 claude/codex `--version`，`context_evidence` 会读取真实 `~/.pi/agent/settings.json`（文档 6.1：无真实凭据、受控网络） |
| 01-L06 | `docs/code-kit-v2/01-baseline/**`、`schemas/*.json`、`tests/fixtures/codekit01/**` 设为 `-text` | 本机系统级 `core.autocrlf=true`；这些文件登记了完整字节摘要，行尾转换会使摘要失配 |
| 01-L07 | 缺少 jsonschema 的 Schema 元校验记为 **BLOCKED**（缺工具且未授权安装，文档 2.4），不记 NOT_RUN | 统一 README 与报告口径 |

## P2 复审遗留的规格裁决（R-P1–R-P8）

裁决人：规划端，2026-09-25。依据：文档 4.1.2、4.1.5、4.3.3、4.3.6 及 01-D03、01-D07。

| 编号 | 问题 | 裁决 |
|---|---|---|
| R-P1 | `E_EVENT_*` 是否一律 `retryable=true` | 否。只有“可恢复读取”的码为 true：`E_EVENT_GAP`、`E_EVENT_REPLAY_CONFLICT`、`E_PROTOCOL_INCOMPLETE`（文档 4.3.6 表），以及 `E_EVENT_RAW_REF_UNKNOWN`（段可能尚未封存）、`E_RESOURCE_INDEX_FAILED`（可幂等补录）。`E_EVENT_RAW_RANGE`、`E_EVENT_TYPE_UNKNOWN`、`E_EVENT_SOURCE`、`E_EVENT_EVIDENCE_MISSING` 是输入缺陷，为 false |
| R-P2 | `executor_retry` 的 attempt 取值 | 不再由纯函数自行 +1。调用方必须传入受信分配器（旧实现 `allocate_attempt`，未来 07）给出的 attempt；必须 ≥ parent.attempt（相等表示同一 prepared attempt 的重新运行，符合旧规则“预检失败后再次 run 沿用原编号”）；缺失为 `E_CONTEXT_INCOMPLETE`，倒退为 `E_CONTEXT_BINDING` |
| R-P3 | 是否在词法层拒绝 8.3 短名形态 | 是。形如 `ABCDEF~1`、`PROGRA~1.TXT` 的分段（基名 1–6 个非 `~` 字符 + `~` + 数字，可带 ≤3 字符扩展名，大小写不敏感）以 `E_PATH_RESERVED` 拒绝：在 Windows 上它可能是另一文件的别名（例如 `AGENTS~1.MD`），会绕过保护路径比较 |
| R-P4 | 是否拒绝 U+2028/U+2029 | 是，并一并拒绝双向控制字符 U+061C、U+200E、U+200F、U+202A–U+202E、U+2066–U+2069，均为 `E_PATH_SYNTAX`（日志注入与 Trojan Source 风险）。其他格式字符（如 ZWNJ）不拒绝 |
| R-P5 | 是否增加 ANSI best-fit（WorstFit）严格 profile | 否。Python 与 Git for Windows 使用宽字符 API；在 protocols-api.md 限制中写明：把业务路径交给 ANSI API 程序的消费者必须自行复核 |
| R-P6 | 浮点下溢（`1e-400`→0.0）与整数 `-0` | 接受并写明：公共记录的数值字段都是整数；`-0` 解析为 0 属 JSON 文法允许；需要精确实数的字段（金额）用十进制字符串 |
| R-P7 | `raw_refs` 是否只能指向 `raw-segment` | 是。其他 kind 以 `E_RESOURCE_KIND` 拒绝（原始证据分段的语义归 04） |
| R-P8 | 空事件日志 `complete=True` | 保留：`complete` 只表示“序列一致”。返回值增加 `event_count`，文档写明空日志不证明运行产生过事件，协议完整性由 `assess_stream_integrity` 与 04 判定 |
| R-P9 | 路径物理检查的定位（P4 第 3、4 轮复审围绕链接逐跳核对连续发现 Windows 解析语义的绕过） | 物理检查（`resolve_existing_path_for_review`、链接逐跳核对、sealing 的路径步进）是“静态审阅 + 纵深防御”，**不是安全访问保证**（01-D06；文档 4.1.6–4.1.7）。无法确定语义的链接写法一律失败关闭；文档与 docstring 只写“已检测的情形”与“已知不检测/不保证”两张清单，不用绝对表述；sealing 的存储根必须由可信核心独占控制，A13 范围是“发布与索引补偿”。生产级安全访问由后续访问实现模块另行设计与验收，不在 01 继续扩展解析逻辑 |

## 完整性审查后的追加记录（2026-09-26，只追加）

记录人：规划端子代理（完整性审查返工）。本节只追加，不改动上文任何决定与裁决；需要规划端或用户决定的事项只登记，不在这里裁决。

### 勘误：上一小节的标题

上一小节标题写“P2 复审遗留的规格裁决（R-P1–R-P8）”，表中还有 R-P9：它来自 P4 第 3、4 轮复审围绕链接逐跳核对的连续发现，由规划端在 P4 第 5 轮裁决（protocols-api.md 第 19 节“P4 第 5 轮”）。按“只追加”的规则不改标题，引用时以“R-P1–R-P9”为准（README.md、acceptance.md 已这样写）。

### 新增局部记录与决定

| 编号 | 记录或决定 | 理由与依据 |
|---|---|---|
| 01-L08 | **总设计的读取与交叉检查**（文档 2.1“总设计：取得后做交叉检查”、6.1“实施前读取当前 AGENTS.md 与总设计”）。<br>- **实施前读取：NOT_RUN**。P0“0.1 读取规则与设计输入”没有留下读取总设计的记录；P0 的产物（`evidence/run-controls/offline-boundary.redacted.md`）只核实了 stub、AGENTS.md 与离线边界。事后无法补成“实施前”。<br>- **事后交叉检查：已做，source_inspected**（2026-09-26，只读，未运行任何命令）。对象是 `docs/code-kit-v2-design.md`：32912 字节，sha256 `82e8e668d8de46bee7b826951f346023220f35c51ea39be4ca0bd222df74d1d1`，未跟踪文件。实施前基线与最终取证的输入清单记录的是同一字节（measured：`evidence/bl-01t1-legacy-20260925/pre/input-manifest.json` 与 `evidence/final/*/pre/input-manifest.json` 中该路径的 sha256 相同）。<br>- 对照结论见下表“01-L08 对照表”。其中需要后续处理的三项：“用量”作为事件类型与 usage-observation 的关系（04）；`scripts/codekit/` 下的文件名与总设计第 9 节不同（后续模块决定是否合并或改名）；新核心文件的保护路径没有落实（用户决定，acceptance.md 第 9 节 (a)）。均已列入 acceptance.md 第 7 节的未完成项 | 完整性审查指出 01 的产物中没有读取或核对总设计的记录。按文档 2.4，没有执行的检查记 NOT_RUN，不能用事后的静态核对代替 |
| 01-L09 | **基线报告与验收映射增加 `applicability` 字段**：取值 `applicable` 或 `not_applicable`；取 `not_applicable` 时必须写 `applicability_reason`。它只表达“这项检查对该平台或范围没有意义”，**不能代替**必需能力的 execution_status：某项安全能力是宣称支持范围的必要条件时，不能标不适用来绕过；对应能力在该平台上仍按 NOT_RUN 等状态记录。首先用于 F028（junction 在 Linux、macOS 上）与 01-A16（分栏规则不分平台） | 文档 2.4：“不适用由 applicability 和理由表达”。修订前报告的状态词表没有这个字段，“不适用”只写在正文里 |

**01-L08 对照表**（总设计行号指上述字节）：

| 对照项 | 总设计原文 | 01 的实际 | 结论 |
|---|---|---|---|
| 统一事件字段 | 第 148 行：至少包含 `schema_version`、`run_id`、`seq`、时间、role、事件类型、payload 和原始记录引用 | 附录 A 的 run-event（`schemas/codekit-public-v1.schema.json` 的 `event`）：schema_version、record_type、request_id、run_id、seq、observed_at、role、type、source_kind、payload、raw_refs、integrity、adapter_revision | 一致，01 是超集：时间对应 observed_at，事件类型对应 type，原始记录引用对应 raw_refs |
| 事件类型种类 | 第 148 行：开始、消息、工具调用及结果、产物、用量、结束和错误 | 01 只登记示例类型 `run.prepared`，真实类型归 04（01-D07）；用量在 01 中是独立的记录类型 usage-observation，不是 run-event 的一种 | **待 04 对齐**：“用量”事件与 usage-observation 的关系（事件载荷引用观测，还是另行记录）没有定义 |
| 缺失值 | 第 150 行：请求配置、CLI 回报与提供商回报分别记录，缺失写 unknown，不能互相替代 | usage-observation 的 null 加 unknown_reasons，不补零（01-A06）；`build_run_dimensions` 保留双方证据（C-05）；能力声明本身未实现（04） | 一致；能力声明归 04 |
| 角色 | 第 3 节角色表（第 63–67 行）：supervisor、planner、executor、observer、dispatcher | `ROLES = ("planner", "executor", "observer")`（`scripts/codekit/protocols.py:55`）；核心事件的 role 可为 null | 一致：supervisor 是交互会话本身，不是一次 run；dispatcher 的事件是 core 来源、role 为 null。将来若把 supervisor 也作为 CLI run，须扩展枚举并升记录版本 |
| 版本命名 | 总设计称“v1/v2 schema”“v2 配置” | 01 按文档 1.3 区分架构名 Code-Kit v2、工具版本 2.2.2、合同 schema v1、公共家族 codekit-public 的 schema_version=1（01-D02） | 不冲突：总设计的“v2”指架构与配置格式，不是 codekit-public 的记录版本。下游文档引用版本时应写明是哪条版本轴 |
| 环境锁 | 第 130 行：机器路径、CLI 版本与入口指纹属于单独的环境锁 | 快照器不投影机器字段；F017 归 02（01-D05） | 一致 |
| v1 兼容 | 第 356 行：v1 合同与历史 attempt 按旧 schema 读取，不重写证据、不重算旧合同哈希；新流程不接受伪装成 v1 的草稿 | 01-D09；A09 未知版本不回退；兼容矩阵第 2、4 节 | 一致 |
| 目录与文件名 | 第 337–340 行：`scripts/codekit/` 下拟有 config、contracts、approvals、process、platforms、evidence、gates、workflow、planner、project_state 等 | 01 新增 `scripts/codekit/protocols.py`、`sealing.py`、`baseline.py`，不在总设计列出的文件名中；`.agent/baseline/` 也不在总设计第 9 节的 `.agent/` 列表中 | **命名差异，已登记**：总设计写明目录“只表示职责划分”；protocols、sealing 的职责接近其中的 evidence，是否合并或改名由后续模块决定 |
| 保护路径 | 第 358 行：新核心模块、插件定义与策略文件纳入保护路径 | 01 的新文件不在任何保护范围内 | **未落实**，待用户决定（acceptance.md 第 9 节 (a)） |
| P0 完成标准 | 第 370 行：现有回归结果可复现；关键 G0–G6、超时、恢复、保护路径有明确基准 | 旧自测实施前后 stdout 逐字节相同（acceptance.md 2.3 的 EV-00、EV-01），但输入闭包为 partial，不宣称可严格复现；G0–G6 见 legacy-inventory.md 第 2、12 节；超时见 LB-LIFE-016；恢复见 LB-LIFE-022、023；旧调度器的保护路径见 LB-CONTRACT-010、LB-GATES-017、018、LB-TEST-015（均为 Windows measured） | **部分满足**：只限 Windows；“可复现”只到“两次取证输出相同”；新核心文件的保护路径没有基准 |
| 项目事件与游标 | 第 303 行：项目事件使用唯一 ID、递增游标和单写者锁 | 01 的 seq 只在单个 run 内；跨 run 的先后没有实现 | 与 01 审阅增强版 4.3.2 一致：跨 run 顺序由 10 的项目游标表达（acceptance.md 第 8 节） |

## 收尾轮裁决（规划端，2026-09-26）

依据：acceptance.md 第 7 节未完成项第 7、11–14、16、17 项，第 10 节 M-01–M-04、M-10–M-12、R-01、R-02。

| 编号 | 问题 | 裁决 |
|---|---|---|
| R-01 | A01 的 pyc 口径 | 采用严格口径：被测命令读取的字节都必须在取证时计摘要或受控禁用。收尾轮的全部取证设 `PYTHONPYCACHEPREFIX` 指向取证前为空的临时目录，使解释器不读取仓库中的 `__pycache__`（受控禁用），并在取证记录中写明。此前两批取证仍按原口径保留，不改写 |
| R-02 | A07 的口径 | A07 要求的是“有回归映射”：六类（G0–G6、范围、候选漂移、预算竞争、取消、补丁完整性）每类、G0–G6 每门都必须有已实测的失败路径断言。满足后记“PASS（Windows，范围限定）”，未覆盖的子分支逐条登记为 `unmet_within_scope`，迁移比较时记 NOT_COVERED。不要求每个子分支都有断言；某一类或某一门没有任何失败路径断言则为 FAIL |
| R-P3 勘误 | 裁决文字与实现不一致（M-02） | 以实现为准：8.3 短名形态的基名前缀可以含 `~`（Windows 由含 `~` 的长名生成的短名也含 `~`），判定是“基名以 `~` 加 1–6 位数字结尾、基名总长 ≤ 8、扩展名 ≤ 3”。上文 R-P3 行的“1–6 个非 `~` 字符”作废 |
| R-P10 | 资源类型注册表缺文档 4.2.1 的三项（M-10） | `ResourceKind` 增加 `schema_ref`（本地受信 Schema 标识或 None）、`payload_representations`（允许的载荷表示集合，取自 `json`、`text`、`markdown`、`binary`）、`payload_validator`（可调用对象或 None）。新增 `validate_resource_payload(ref, raw, registry)`：先按 `verify_resource_bytes` 核验字节，再执行该类型的校验器。01 预登记的类型：`fixture`（json/text/markdown/binary，无校验器）、`fixture-manifest`（json，校验器为严格解析加 `validate_fixture_manifest_set`）、`public-schema`（json，校验器为严格解析加 `$id` 核对）、`baseline-evidence`（json/text/binary，无校验器）、`raw-segment`（binary，无校验器，语义归 04）。其他模块登记自己的类型时必须提供这三项 |
| R-P11 | fixture 条目缺规定字段（M-03） | 条目新增：`integrity`（`complete`、`partial`、`truncated`、`corrupted`，文档 6.6“封存”）；`platform_scope`（`["any"]` 或 PLATFORMS 的非空子集，文档 1.1）；`capture`（`null` 或 `{"environment_ref", "range"}`，class 为 captured 时必填，其他 class 必须为 null，附录 C.1）；`redaction.protocol_structure_preserved`（布尔或 null）与 `origin.traceable`（布尔）（文档 4.3.3）。规则：legacy 与 captured 的 `traceable` 必须为 true；`integrity` 不是 complete 的条目，其 `proves` 不得声称完整运行流；`protocol_structure_preserved=false` 的条目不得声称证明协议字段语义 |
| R-P12 | 文档 3.2 的 `input_fixture_ref` 与 `comparison_projection_revision`（未完成项第 11、12 项） | 两种形式都是合法的 input_fixture_ref：(a) manifest 登记的 fixture 文件；(b) **代码内联 fixture**，写成 `inline:<测试文件>::<类>.<方法>@<测试文件 sha256>`（输入由测试代码确定性构造，字节可由该文件复现）。比较投影：fixture 差分用 `codekit01-legacy-projection-v1`；特征化测试用 `codekit01-characterization-v1`，即“该方法中的断言集合”。文档 6.6 的“差分”（同一输入喂给旧路径与新兼容路径）要等新路径存在：超时、取消、恢复、候选漂移、补丁、门禁、旧入口状态解释七类的新路径归 07、10，届时由这些模块用同一内联输入做差分；在此之前，这七类在 01 中的状态是“旧路径已锁定，差分 NOT_RUN（新路径不存在）”，不是缺样本 |
| R-P11 补充 | 声明名称的判定词表（收尾轮返工提出，裁决原文未规定） | 采纳实现中的受控词表（`scripts/codekit/protocols.py` 的 `COMPLETENESS_CLAIM_STEMS`、`COMPLETENESS_CLAIM_PHRASES`、`COMPLETENESS_CLAIM_QUANTIFIERS`、`STREAM_SUBJECT_STEMS`、`FIELD_SEMANTICS_CLAIM_STEMS`、`PROTOCOL_SUBJECT_STEMS`、`FIELD_SUBJECT_STEMS`，说明见 protocols-api.md 第 2 节）：按 `_` 切词后命中完整性词根（或全称量词配流类主语）即视为“完整运行流”声明，命中语义词根配协议/字段主语即视为“协议字段语义”声明。词表比裁决原文更宽，属失败关闭方向，接受其误伤（例如 `complete_usage_totals` 在不完整条目上也被拒绝）；需要这类声明的条目应先如实把 `integrity` 记为 complete。另采纳实施者加的保守规则：`redaction.applied=true` 且 `protocol_structure_preserved` 为 null 时同样不得声称协议字段语义（文档 4.3.3：未记录是否保留结构即不能证明字段语义）。词表扩充须追加裁决并补测试，不得删减 |
