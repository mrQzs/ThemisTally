# 01 公共协议接口说明（protocols.py / sealing.py）

本文给 02/03/04/06/07/09/10 的实现者使用，说明 `scripts/codekit/protocols.py` 与 `scripts/codekit/sealing.py` 的接口、错误码和能力边界。

- 依据：01 审阅增强版 1.3、4.1–4.4、附录 A.2、附录 B、附录 C；决策 01-D01–D10、01-L01–L04 与规划端裁决 R-P1–R-P9，以及收尾轮裁决 R-P3 勘误、R-P10–R-P12（[decisions.md](decisions.md) 末尾“收尾轮裁决”）。
- 起点：附录 B.2 参考实现。参考实现的错误码语义保持不变，在此基础上扩展。
- 运行环境：只用标准库，语法按 Python 3.10+ 编写（01-D10）。实测平台只有 Windows Server 2025 + Python 3.12.10，Linux/macOS 为 NOT_RUN。
- 测试：正式协议测试是 `tests/test_protocols.py`，由另一位实施者独立编写。实现与测试的对照调和结果及裁决见第 19 节“规格澄清”；规划端裁决 R-P1–R-P8 与第 2 轮复审 minor 的处理见第 19 节末尾“P4”；第 3 轮复审（32 条）的逐条处理见第 19 节的“P4 第 3 轮”；第 4 轮复审（5 条）的逐条处理见第 19 节的“P4 第 4 轮”；裁决 R-P9 的落实与第 5 轮复审（7 条 major）的逐条处理见第 19 节的“P4 第 5 轮”；收尾轮（裁决 R-P10、R-P11 与 acceptance.md 第 10 节 M-01、M-03、M-10–M-12 的处理）见第 19 节最后的“收尾轮”。本文不记录验收结论，验收见 `acceptance.md`。

> **结构校验已实现 ≠ 协议已完全安全。**
>
> 本模块实现了附录 A 的结构校验和一部分语义检查（逐项对照见第 16 节）。以下能力都不在本模块中：
>
> - 授权与保护范围；
> - 生产级安全文件访问：抵御 TOCTOU、按目录句柄逐级访问。业务路径的物理检查只是“静态审阅 + 纵深防御”，不是安全访问保证（裁决 R-P9，见第 7、15 节的两张清单）；
> - 真实厂商事件类型与结束判定；
> - 序号分配与持久提交的事务协调；
> - 预算与唯一记账；
> - 合同发布；
> - 项目集成。
>
> 任何消费者都不能因为 `validate_*` 通过，或 `structural: True`，就宣称输入可信、已授权或可执行。

---

## 1. 导入与副作用

两种导入方式：

```python
# 包方式（推荐）：把 scripts/ 放进 sys.path
from codekit import protocols, sealing

# 按文件加载（与 tests/test_baseline_tool.py 的约定一致，不登记到 sys.modules 也可用）
spec = importlib.util.spec_from_file_location("_codekit_protocols_under_test", ".../protocols.py")
```

- **导入无副作用（01-A14）**：导入 `protocols` 不读写文件、不启动进程、不联网、不读环境变量。审计钩子实测：导入期间只出现解释器加载模块本身的 `open` 事件；导入前把 `os.environ` 换成记录读取的包装，实测导入期间没有读取任何环境变量；源码 AST 检查确认两个模块都不出现 `environ`/`getenv`/`putenv` 等名称（见测试 F049、A14）。
  - 导入 `sealing` 只加载标准库模块（例如 secrets、hashlib、pathlib），**不加载 `protocols.py`**，也不读写任何数据文件。
- **纯函数为主**，例外如下：
  - `resolve_existing_path_for_review()`：被调用时只读地解析调用方给出的路径，并列出沿途目录的名称（核对拼写，见第 7 节）；
  - `append_event()`：按规格**就地更新调用方传入的 `state`**；
  - `sealing` 的两个函数：访问调用方传入的存储根；
  - `new_request_id()` 与 `new_run_id()`：使用随机数。
- **不执行命令**：本模块不执行 git，也不调用模型。
- **没有使用 dataclasses**：按文件加载且不登记到 `sys.modules` 时，带字符串注解的 dataclass 在类创建阶段会失败（本机实测）。因此 `ResourceKind` 和 `EventType` 是手写的不可变类。
- **`sealing` 与 `protocols` 的绑定**：`seal_bytes`/`read_sealed` 使用**传入的 `registry` 所属的那个 protocols 模块**做校验并抛错，所以调用方捕获到的总是自己那份 `ProtocolError`。
  - 模块属性 `sealing.ProtocolError` 采用惰性解析，按以下顺序取值：
    1. 以包方式导入时，用相对导入得到的 `protocols`；
    2. `sys.modules` 中按同一文件加载的模块；
    3. 以上都没有时，按文件加载一份。

## 2. 常量

| 名称 | 值 | 说明 |
|---|---|---|
| `PROTOCOL_FAMILY` | `"codekit-public"` | 公共协议家族（01-D02） |
| `PUBLIC_SCHEMA_VERSION` | `1` | 公共记录版本；与合同 v1、工具版本 2.2.2 无关 |
| `SCHEMA_ID` | `"urn:codekit:public-protocol:1"` | 本地 Schema `$id`（`schemas/codekit-public-v1.schema.json`，本模块不加载它） |
| `SNAPSHOT_PROFILE` | `"codekit-config-json-py-v1"` | 固定序列化 profile（4.2.6） |
| `MAX_SAFE_INTEGER` | `2**53-1` | 新协议整数上限（01-D04） |
| `DEFAULT_MAX_BYTES` / `DEFAULT_MAX_DEPTH` | `1_048_576` / `64` | 单文档与嵌套上限，可作参数调整 |
| `ROLES` / `PLATFORMS` | planner/executor/observer；linux/macos/windows | |
| `PUBLIC_RECORD_TYPES` | run-context、run-event、usage-observation | 可路由的公共记录 |
| `REPRESENTATIONS` / `ORIGIN_CLASSES` | 4.3.3 与 5.3 的枚举 | fixture 来源 |
| `LEGACY_VERDICTS` | PASS、ACCEPTED_WITH_EXCEPTION、REVISE、BLOCKED、ESCALATE | 抄自 `scripts/pi_dispatch.py:75` 的 `VERDICTS`，测试须断言两者相等 |
| `UNKNOWABLE_USAGE_FIELDS` | provider … estimated_cost 共 12 个 | 可为未知且必须写原因的用量字段 |
| `REAL_COMPATIBILITY_CLAIMS` / `REAL_CLAIM_PREFIXES` | 3 个声明；`real_`/`vendor_`/`legacy_` | 合成样本不得声称的能力 |
| `VENDOR_COMPATIBILITY_CLAIMS` / `VENDOR_CLAIM_PREFIXES` | real_cli_compatibility、vendor_protocol；`real_`/`vendor_` | 只有 captured + captured_raw/redacted_raw 条目可以声称（P4，第 14.2 节） |
| `LEGACY_DISPATCH_CLAIM` | `"legacy_dispatch_behavior"` | 只有 legacy + legacy-judgment 条目可以声称（P4） |
| `DIMENSIONS_RULE_REVISION` | `"codekit01-run-dimensions-v2"` | P4 起 cancelled 为三态，由 v1 升为 v2（第 12 节） |
| `PAYLOAD_REPRESENTATIONS` | json、text、markdown、binary | 资源类型允许的载荷表示（裁决 R-P10，第 8 节） |
| `RESOURCE_KIND_DECLARED_FIELDS` | schema_ref、payload_representations、payload_validator | 登记资源类型时必须声明的三项（R-P10） |
| `FIXTURE_INTEGRITY_VALUES` | complete、partial、truncated、corrupted | fixture 条目的 `integrity`（裁决 R-P11，第 14 节） |
| `PLATFORM_SCOPE_ANY` | `"any"` | fixture 条目 `platform_scope` 的“不限平台”取值（R-P11） |
| `COMPLETE_STREAM_CLAIM_PREFIXES` | complete_run_stream、full_run | “完整运行流”一类声明的典型前缀（R-P11；名称由收尾轮实施者选定，裁决原文未规定）。收尾轮返工起判定按下面的受控词表，这两个前缀开头的声明都在词表内 |
| `PROTOCOL_FIELD_SEMANTICS_CLAIM` | `"protocol_field_semantics"` | “协议字段语义”一类声明的典型前缀（R-P11；名称来源同上），判定同样按受控词表 |
| `COMPLETENESS_CLAIM_STEMS` / `COMPLETENESS_CLAIM_PHRASES` / `COMPLETENESS_CLAIM_QUANTIFIERS` / `STREAM_SUBJECT_STEMS` | complet、full、entire、whole、intact、untruncat、unabridg、endtoend、e2e / (end, to, end) / all、every / run、stream、event、log、record、line、message、transcript、session、output、trace、segment | “完整运行流”一类声明的受控词表（收尾轮返工，第 14.2 节第 5 步） |
| `FIELD_SEMANTICS_CLAIM_STEMS` / `PROTOCOL_SUBJECT_STEMS` / `FIELD_SUBJECT_STEMS` | semantic、meaning / protocol、wire / field | “协议字段语义”一类声明的受控词表（收尾轮返工，第 14.2 节第 5 步） |
| 其他 | `EVENT_SOURCE_KINDS`、`EVENT_INTEGRITY_VALUES`、`RAW_STREAMS`、`OBSERVATION_KINDS`、`BILLING_SOURCES`、`STREAM_CLASSIFICATIONS`、`DERIVE_ACTIONS`、`GIT_OBJECT_FORMATS`、`USAGE_COUNTERS`、`EXPECTED_OUTCOMES`、`UNKNOWN_CURRENCY` | 各节使用的封闭枚举 |

## 3. 错误模型

### 3.1 `ProtocolError` 与 `to_record()`

`ProtocolError(ValueError)` 的签名：`ProtocolError(code, *, field=None, phase=None, reason=None, hint=None, source_ref=None, retryable=None)`。

构造时的检查：

- `code` 不在 `ERROR_CODES` 中：直接抛 `ValueError`，不会得到 `ProtocolError`。
- `source_ref` 不是结构合法的 ResourceRef：抛 `ValueError`。
- `field`、`phase`、`reason`、`hint` 有非 str 值：抛 `ValueError`。

属性如下：

- `code`：固定错误码。
- `field`：JSON Pointer（RFC 6901，`~` 转成 `~0`，`/` 转成 `~1`）或 None。
- `phase`：检查阶段；不传时取错误码的类别。
- `reason`：固定的机器可读原因，例如 `duplicate_object_member`。reason 不随输入变化，下游可以按 reason 精确分派（P4 第 3 轮起 `E_JSON_SYNTAX` 的 reason 也固定为 `syntax_error`，见下）。
- `hint`：可选的处理提示。`strict_json_loads` 报 `E_JSON_SYNTAX` 时，hint 是文法错误的位置 `line=<行> column=<列>`（取自标准库 json，随输入与 json 实现变化，只是提示，不要按它分派）。
- `source_ref`：深拷贝的来源引用。
- `retryable`：不传时取错误码表中的值。
- 便利属性：`message`（取错误码表中的安全文案），`details`（与附录 A errorDetail 同形，未截断）。

`to_record()` 返回附录 A 的 `error` 结构：`{code, message, details{field, source_ref, phase, reason, hint}, retryable}`。

- 文字按 Schema 上限截断，以码点计：message、field、reason、hint 各 512，phase 64。
- message、phase、reason、hint 中的孤立代理项替换为 U+FFFD，使记录本身能通过 `stable_snapshot_bytes`。
- **field 不做字符替换，也不在字符中间截断**。field 含孤立代理项或超过 512 时，截到最长的、由完整引用 token 组成的**祖先指针**（最短是根 `""`），并在 reason 末尾追加固定标记 `;field_truncated_to_ancestor`（常量 `FIELD_TRUNCATED_MARK`）。这样得到的仍是合法的 RFC 6901 指针，指向真实存在的上层成员：不会停在 `~` 与其后的 `0`/`1` 之间，也不会因把代理项换成 U+FFFD 而误指向另一个真实存在的键。
- 便利属性 `details` 用同样的规则处理孤立代理项（不按长度截断），因此可以按 UTF-8 编码；原始指针仍在属性 `field` 上，可能含孤立代理项，不得原样外发。

**不回显输入值**：所有 message 与 reason 都是固定文字（P4 第 3 轮之前 `E_JSON_SYNTAX` 的 reason 带行列号，是唯一的例外，已改为固定的 `syntax_error`，位置移到 hint）。`field` 只含字段名构成的指针，例如重复键 `/a/0/x~1y`。hint 中的位置只含行号与列号两个数字，不含输入内容。

**`retryable` 只是提示**：本模块从不据此重试、调用模型或触发任何动作（1.2、4.3.6）。

### 3.2 错误码表

| 错误码 | 类别 | retryable | 抛出位置（公开函数） |
|---|---|---|---|
| `E_JSON_INPUT_TYPE` | input_format | 否 | strict_json_loads |
| `E_JSON_LIMIT` | input_format | 否 | strict_json_loads、check_json_value、stable_snapshot_bytes；各记录校验（整条记录的深度与字节下界） |
| `E_JSON_BOM` | input_format | 否 | strict_json_loads |
| `E_JSON_ENCODING` | input_format | 否 | strict_json_loads；validate_resource_payload（只允许 text/markdown 的类型遇到非 UTF-8 字节，reason `payload_not_utf8_text`；收尾轮 R-P10） |
| `E_JSON_SYNTAX` | input_format | 否 | strict_json_loads（reason 固定为 `syntax_error`，位置在 hint；P4 第 3 轮） |
| `E_JSON_DUPLICATE_KEY` | input_format | 否 | strict_json_loads |
| `E_JSON_NON_FINITE` | input_format | 否 | strict_json_loads、check_json_value（及调用它的函数）；两个入口对同一个值给出同一个 field（P4 第 3 轮） |
| `E_JSON_UNICODE` | input_format | 否 | strict_json_loads、check_json_value；各记录中的字符串字段 |
| `E_JSON_VALUE_TYPE` / `E_JSON_KEY_TYPE` / `E_JSON_CYCLE` | input_format | 否 | check_json_value（及调用它的函数）；环不论多长都是 `E_JSON_CYCLE`（P4 第 3 轮） |
| `E_INTEGER_RANGE` | input_format | 否 | strict_json_loads、check_json_value、require_int；usage_view（计量合计超过 2^53-1） |
| `E_SCHEMA_TYPE` | input_format | 否 | 类型错误：非 dict/list/str/bool，整数字段非精确 int；stable_snapshot_bytes 的根不是精确 dict（先于值检查，P4 第 3 轮）；收尾轮：append_event 的 request_id 不是 str、role 缺失或既不是 str 也不是 null（`/request_id`、`/role`，M-01）；recover_next_seq / recover_append_state 的不可读记录含绑定字段不可读的记录（M-01）；public-schema 载荷校验器的根不是对象（R-P10） |
| `E_SCHEMA_FIELDS` | input_format | 否 | 缺字段或未知字段；封闭枚举外的值（含类型不对）；字符串长度越界；derive_run_context 的动作或参数不适用；validate_public_record 的参数不适用于该记录类型；build_run_dimensions 的 process_exited=False 却给出 exit_code；validate_run_context(for_executor_dispatch=True) 的 role 不是 executor（P4）；P4 第 3 轮：validate_run_event 的 vendor 事件 role 为 null（`vendor_event_requires_role`）、assess_stream_integrity 的必需类型未登记（`required_kind_not_classified`）、fixture manifest 的能力声明不符合封闭词法（`claim_syntax`）；收尾轮：ResourceKindRegistry 构造或 extended() 时登记项缺 R-P10 三项（`resource_kind_registration_incomplete`）、validate_resource_payload 的校验器抛出 ProtocolError 以外的异常（`payload_validator_unexpected_exception`）、public-schema 载荷的 `$id` 不符（`public_schema_id_mismatch`）、fixture 条目的 platform_scope 为空、`any` 与平台并列或平台重复（`platform_scope_empty`、`platform_scope_any_must_be_alone`、`duplicate_platform`，R-P11） |
| `E_SCHEMA_VERSION_TYPE` | input_format | 否 | route_public_record、require_schema_version、各记录校验 |
| `E_SCHEMA_VERSION_UNSUPPORTED` | input_format | 否 | 同上 |
| `E_SCHEMA_RECORD_TYPE` | input_format | 否 | route_public_record、各记录校验、append_event；recover_next_seq / recover_append_state（日志中有非 run-event 记录，P4） |
| `E_ID_SYNTAX` | input_format | 否 | validate_request_id / run_id / task_id / logical_id / resource_kind / sha256；recover_next_seq / recover_append_state 的 run_id 参数 |
| `E_TIME_FORMAT` | input_format | 否 | format_observed_at、parse_observed_at |
| `E_CONTEXT_INCOMPLETE` | context | 否 | validate_run_context(for_executor_dispatch=True)、derive_run_context（含 executor_retry 未传入受信分配的 attempt，R-P2） |
| `E_CONTEXT_BINDING` | context | 否 | validate_run_event、validate_usage_observation、append_event、recover_next_seq、recover_append_state；derive_run_context（executor_retry 的 attempt 小于 parent.attempt，R-P2）；收尾轮 M-01：append_event 的 request_id 或非空 role 与已提交记录不一致（`request_binding_mismatch`、`role_binding_mismatch`），恢复函数遇到同一 run 内 request_id 或非空 role 不一致（`log_request_binding_mismatch`、`log_role_binding_mismatch`） |
| `E_PATH_SYNTAX` / `E_PATH_RESERVED` | path | 否 | validate_business_path（及所有带 path 的校验）；P4 起 `E_PATH_SYNTAX` 含行/段分隔符与双向控制字符（R-P4），`E_PATH_RESERVED` 含 8.3 短名形态（R-P3） |
| `E_PATH_ESCAPE` | path | 否 | resolve_existing_path_for_review、seal_bytes、read_sealed（某一级的最终目标在根外，reason `resolved_outside_trusted_root` / `resolved_outside_store_root`；或链接链上某个链接对象位于根外，reason `link_hop_outside_trusted_root`，P4 第 3 轮） |
| `E_PATH_RESOLUTION_FAILED` | path | 否 | resolve_existing_path_for_review、seal_bytes、read_sealed：未登记的文件系统别名（例如手工设置、不含 `~` 的短名，reason `noncanonical_filesystem_alias`）、目录无法列出、链接环等解析失败、逐跳展开链接链失败（跳数超限、目标写法不受支持或语义无法确定，reason `link_target_form_unsupported`；展开终点与 resolve 结果不同，reason `link_walk_diverged`，P4 第 4 轮；未识别的名称代理类重解析点，reason `link_kind_unsupported`，P4 第 5 轮，R-P9 失败关闭）。**仅 seal_bytes**：悬空的链接祖先（`target_not_found`）、已存在的祖先分段是普通文件（`ancestor_not_directory`）、最终名是悬空链接；同样两种情形在另两个函数中分别报 `E_PATH_NOT_FOUND` 与 `E_RESOURCE_MISSING`（P4 第 3 轮更正） |
| `E_PATH_NOT_FOUND` | path | 否 | resolve_existing_path_for_review（目标不存在，含中间段是普通文件、悬空的链接或链接祖先） |
| `E_PATH_ROOT` | path | 否 | resolve_existing_path_for_review、seal_bytes、read_sealed |
| `E_PATH_COLLISION` | path | 否 | check_no_name_collisions、validate_fixture_manifest_set；resolve_existing_path_for_review、seal_bytes、read_sealed（业务路径的拼写与磁盘上登记的名称只差大小写或 Unicode 形式） |
| `E_RESOURCE_FIELD` | resource | 否 | validate_resource_ref（kind/id/sha256 语法；verify_resource_bytes、validate_resource_payload 先调用它） |
| `E_RESOURCE_KIND` | resource | 否 | validate_resource_ref、fixture manifest、seal_bytes、read_sealed；validate_raw_span / validate_run_event（raw_refs 不是 raw-segment，R-P7）；validate_resource_payload（kind 未登记） |
| `E_RESOURCE_PATH_REQUIRED` | resource | 否 | validate_resource_ref（及调用它的 verify_resource_bytes、validate_resource_payload、fixture manifest） |
| `E_RESOURCE_BYTES` | resource | 否 | sha256_hex、verify_resource_bytes、validate_resource_payload、seal_bytes |
| `E_RESOURCE_HASH_MISMATCH` | resource | 否 | verify_resource_bytes、validate_resource_payload、seal_bytes（读回不符）、read_sealed |
| `E_RESOURCE_CYCLE` | resource | 否 | check_resource_dag |
| `E_RESOURCE_CONFLICT` | resource | 否 | seal_bytes（最终名已有不同字节，或被目录等非普通文件占用） |
| `E_RESOURCE_INDEX_FAILED` | resource | **是** | seal_bytes |
| `E_RESOURCE_MISSING` | resource | 否 | read_sealed（不存在，含悬空的链接或链接祖先、中间段是普通文件，reason `target_not_found` / `resource_not_found`；不是普通文件，reason `not_regular_file`）；seal_bytes 发布后发现最终名消失（写入路径上不再用它表示“被目录占用”） |
| `E_GIT_OID_SYNTAX` | git | 否 | validate_git_oid、git_cat_file_type_argv、fixture manifest |
| `E_GIT_OBJECT_MISSING` / `E_GIT_OBJECT_TYPE` | git | 否 | interpret_git_object_type |
| `E_GIT_FORMAT_UNSUPPORTED` | git | 否 | validate_git_oid |
| `E_EVENT_GAP` / `E_EVENT_REPLAY_CONFLICT` | event_integrity | **是** | append_event、recover_next_seq、recover_append_state（日志乱序也报 `E_EVENT_GAP`） |
| `E_PROTOCOL_INCOMPLETE` | event_integrity | **是** | 本模块不抛；登记供 04/07 使用 |
| `E_EVENT_RAW_REF_UNKNOWN` | event_integrity | **是** | validate_raw_span、validate_run_event |
| `E_EVENT_RAW_RANGE` | event_integrity | 否（R-P1） | validate_raw_span、validate_run_event |
| `E_EVENT_TYPE_UNKNOWN` / `E_EVENT_SOURCE` / `E_EVENT_EVIDENCE_MISSING` | event_integrity | 否（R-P1） | validate_run_event |
| `E_USAGE_CONFLICT` | usage | 否 | validate_usage_observation（自我替代）、usage_view |
| `E_USAGE_SCOPE_UNKNOWN` / `E_USAGE_CURRENCY_MISMATCH` | usage | 否 | usage_view（前者 P4 起也用于“provider 为 null、同一 billing_event_id 被多条有效链尾代表”，P4 第 3 轮起按修订链全部成员、不区分 request/run/role；后者用于修订链与同一累计序列） |
| `E_USAGE_UNKNOWN_REASON` / `E_USAGE_VALUE` | usage | 否 | validate_usage_observation（后者也用于“reported_cost 与 billing_source 不一致”） |
| `E_PROVENANCE_CLAIM` | provenance | 否 | validate_fixture_manifest_entry / set（P4 起能力声明规则作用于全部条目，第 14.2 节；P4 第 3 轮起清单级拒绝负例从负例派生，第 14.3 节；收尾轮起含 R-P11 的可追溯、采集记录、完整性与协议结构规则，第 14.2 节第 3b、5 步）；validate_resource_payload（fixture-manifest 载荷的校验器原样报出） |
| `E_BASELINE_DRIFT` / `E_BASELINE_INPUT_MISSING` | baseline_compat | 否 | 本模块不抛。登记待用；当前取证工具（`scripts/codekit/baseline.py`）不发出这两个码，漂移与缺输入分别用 `comparison.baseline_consistent`（漂移时为 false）与 `execution_status`（缺输入时为 incomplete）表达，见取证记录 `capture.json`（收尾轮更正，acceptance.md M-12；此前写“登记供基线取证工具使用”，与实现不符） |
| `E_COMPAT_UNSUPPORTED` | baseline_compat | 否 | route_public_record、platform_from_system、interpret_git_object_type |

- **表格来源**：“类别”“retryable”两列从 `ERROR_CODES` 生成。安全文案见源码 `_ERROR_TABLE`。
- **覆盖范围**：文档 4.2.7 与 4.3.6 表中的全部错误码、附录 B 参考实现用到的全部错误码，以及规格列出的 20 个本模块新增码（其中 E_PATH_NOT_FOUND、E_PATH_ROOT 参考实现已使用），都已登记，共 58 个。收尾轮没有新增错误码，只新增 reason。
- **validate_resource_payload 的间接错误码**（收尾轮 R-P10）：json 表示的检查与 fixture-manifest、public-schema 的校验器都调用 strict_json_loads，照报它的错误码（`E_JSON_*`、`E_INTEGER_RANGE`）；fixture-manifest 的校验器照报 validate_fixture_manifest_set 的错误码；登记模块自己的校验器抛出的 ProtocolError 原样传出。
- **retryable 取值**（裁决 R-P1，P4 落实）：
  - 为“是”的恰好 5 个：4.3.6 表“事件完整性”一行的 `E_EVENT_GAP`、`E_EVENT_REPLAY_CONFLICT`、`E_PROTOCOL_INCOMPLETE`（“可恢复读取，但不自动重新调用模型”）；分段可能稍后才完成封存的 `E_EVENT_RAW_REF_UNKNOWN`；可用相同字节幂等补录的 `E_RESOURCE_INDEX_FAILED`。
  - `E_EVENT_RAW_RANGE`、`E_EVENT_TYPE_UNKNOWN`、`E_EVENT_SOURCE`、`E_EVENT_EVIDENCE_MISSING` 是输入缺陷，同一记录重读仍会失败，为“否”（P2 时沿用 01-T2 原文“E_EVENT_*……设 retryable”，已收窄）。
  - 其余都为“否”。
- **错误码稳定性**：错误码是机器接口，message 可以改进措辞而不改变 code。
- **多缺陷输入**：多处损坏的输入不承诺报告同一个首错；单一故障输入返回稳定的错误码。明确的例外：`recover_next_seq` / `recover_append_state` 按缺陷类别的固定全序报错（第 11 节），与记录位置无关，测试固定（P4 第 3 轮）。

## 4. 严格 JSON 与固定快照（4.2.6、4.2.7）

| 函数 | 行为 |
|---|---|
| `strict_json_loads(raw, *, max_bytes=1 MiB, max_depth=64)` | 见下方检查阶段。检出嵌套重复键，`field` 指向重复成员；非有限数与整数越界的 `field` 同样指向该成员（P4 第 3 轮，与 `check_json_value` 对同一个值给出的 field 相同）。 |
| `check_json_value(value, *, max_depth=64, field="", max_bytes=None)` | 只接受 `type()` **精确**为 dict/list/str/int/float/bool/NoneType 的值，子类（OrderedDict、IntEnum、str 子类）一律 `E_JSON_VALUE_TYPE`。dict 键必须是 str（`E_JSON_KEY_TYPE`）。环为 `E_JSON_CYCLE`，不论环多长：环先于深度判断，环长超过剩余深度时在深度超限处另做一次不限深度的迭代环检测（线性，每个容器只访问一次），仍报 `E_JSON_CYCLE`，field 指向深度超限处；只有过深而无环才报 `E_JSON_LIMIT`（P4 第 3 轮；此前环长超过剩余深度时报 `E_JSON_LIMIT`，同一种单一故障的错误码随环长变化）。同一容器复用但不成环可以接受。深度按“容器嵌套层数”计，与 `strict_json_loads` 一致：`[[[]]]` 为 3 层。`max_bytes` 给出时，边遍历边累计“按固定快照紧凑序列化后的字节数”的**下界**，超过即 `E_JSON_LIMIT`（reason 为 `serialized_size_lower_bound_exceeded`）；共享容器每被引用一次计一次，所以展开后指数级的共享结构会在预算用完时停止。默认不限；处理调用方直接传入的不受信 Python 值时应给出上限。 |
| `stable_snapshot_bytes(value)` | 先要求根的 type 精确为 dict（`E_SCHEMA_TYPE`，不遍历根的内容；与附录 B.2 参考实现的顺序相同，P4 第 3 轮恢复），再 `check_json_value(value, max_bytes=1 MiB - 1)`，在生成输出之前按下界止损。输出严格为 `json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",",":"), allow_nan=False)+"\n"` 的 UTF-8 字节（无 BOM）；超过 1 MiB 为 `E_JSON_LIMIT`。 |
| `sha256_hex(raw)` | 完整字节的小写十六进制摘要，只接受 bytes。 |

`strict_json_loads` 的检查阶段与错误码（对应 4.2.7 的**概念阶段**，执行时机见下文）：

1. 输入必须是 bytes，bytearray 和 str 都拒绝：`E_JSON_INPUT_TYPE`。
2. 空输入或超出 `max_bytes`：`E_JSON_LIMIT`。
3. 带 UTF-8 BOM：`E_JSON_BOM`。
4. 不是有效 UTF-8：`E_JSON_ENCODING`。
5. 嵌套超过 `max_depth`，或解码器递归超限：`E_JSON_LIMIT`。
6. 文法错误，包括尾随第二个文档：`E_JSON_SYNTAX`。
7. 重复键，包括转义后相同的键（例如 `a` 与 `\u0061`）：`E_JSON_DUPLICATE_KEY`。
8. NaN、Infinity、-Infinity，以及 `1e10000` 这类溢出：`E_JSON_NON_FINITE`。
9. 整数绝对值大于 2^53-1：`E_INTEGER_RANGE`。
10. 孤立代理项（键和值都检查；合法代理对接受）：`E_JSON_UNICODE`。

**检查时机**（P2 返工后如实说明，见第 19 节 R-02；P4 第 3 轮调整了数值错误的报告时机）：

- 第 1–4 步严格按上述顺序执行。
- 之后由标准库 json 从左到右解析：文法错误（6）在解析失败的位置报告（reason 固定为 `syntax_error`，行/列只在 hint 中）；解码器递归超限报 `E_JSON_LIMIT`。非有限数（8）与整数范围（9）不在解析中途抛出：解析钩子返回内部哨兵，解析完成后再报告，这样才能带上 JSON Pointer（P4 第 3 轮；此前在钩子里直接抛错，field 恒为 None）。超长数字串仍按位数判定，不做整数转换。
- 解析成功后，按文档顺序遍历结果，检查嵌套深度（5）、重复键（7）、非有限数（8）、整数范围（9）与孤立代理项（10），报告遍历中遇到的第一处，field 指向该成员；顶层标量出错时 field 为 None。每个容器先查深度；对象的每个成员先查键（孤立代理项、重复），再查值。深度按 json 实际确定的字符串边界计算，字符串内的括号永远不计入，包括 `\"`、`\\`、`\u005b` 之后的括号。
- 因此第 5–10 步只是概念顺序，不是执行顺序。例如 `{"a":1,"a":NaN}` 报 `E_JSON_DUPLICATE_KEY`（`/a`：第二个 `a` 的值还没有检查），`{"a":NaN,"a":1}` 报 `E_JSON_NON_FINITE`（`/a`），`[1e400,]` 报 `E_JSON_SYNTAX`（数值错误不再在解析中途抛出），`{"a":"\ud800","b":1,"b":2}` 报 `E_JSON_UNICODE`（`/a`）。P4 第 3 轮之前，第一个与第三个示例都报 `E_JSON_NON_FINITE`。**多缺陷输入只保证返回其中一个缺陷的错误码**（4.2.7、4.3.6）；单一故障输入返回稳定的错误码。`test_A04_multi_defect_examples_in_document_order` 固定这里列出的示例，改动须同步本节。
- 字符串里漏写反斜杠（未转义的引号）是单一文法故障，无论后面跟多少个括号都报 `E_JSON_SYNTAX`；尾随的第二文档本身过深，也按尾随文档报 `E_JSON_SYNTAX`。
- 遍历时 JSON Pointer 用惰性路径链表示，只在构造错误时渲染。父路径很长（长键，或含 `/`、`~` 的键转义后更长）时，1 MiB 以内的输入仍在线性时间内完成。

**下溢与整数 `-0`（裁决 R-P6：接受并写明）**：4.2.6/4.2.7 只要求拒绝非有限数与溢出，没有定义下溢，也没有定义整数 `-0`。行为如下，下游（例如 02 的配置投影）不能假设源文本被原样保留：

- `1e-400` 解析为 `0.0`，下溢不报错；
- `-0` 解析为 int `0`，快照输出 `0`，符号丢失（JSON 文法允许 `-0`）；
- `-0.0` 保留为 `-0.0`。

公共记录的数值字段都是整数；需要精确实数的字段（金额）用十进制字符串，不经浮点，不受下溢影响。测试 `test_A03_underflow_and_negative_zero_integer` 固定这一行为。

快照的注意事项：

- 快照函数不排序数组、不做 Unicode 归一化、不把 `1.0` 变成 `1`，也不是 RFC 8785/JCS。
- 参数必须是 02 已完成语义投影的对象（01-D05）。快照函数不删除秘密、不补默认值、不判断授权。
- 附录 C.2 的 5 组黄金向量已复现。
- 4.2.2 合成样本的摘要 `0036dde3…c4e1` 算的是**文件字节** `{"fixture":"synthetic","ok":true}\n`，不是快照输出。这组字节恰好也等于 `{"fixture":"synthetic","ok":true}` 的快照输出，测试应把这两件事分开断言。

## 5. 标识、整数与运行上下文（4.1.1–4.1.4）

### 5.1 标识与整数

| 函数 | 规则 |
|---|---|
| `new_request_id()` / `new_run_id()` | 格式为 `req-`/`run-` 加 `uuid.uuid4().hex`。持久化唯一性与分配归 07。 |
| `validate_request_id` / `validate_run_id` / `validate_task_id` / `validate_logical_id` / `validate_resource_kind` / `validate_sha256` | 值必须是 str，并用 `re.fullmatch` 整串匹配（尾随换行被拒绝），否则为 `E_ID_SYNTAX`。task_id 长度 1–64。都接受关键字参数 `field`。在 ResourceRef 中，kind/id/sha256 的语法错误报 `E_RESOURCE_FIELD`。 |
| `require_int(value, *, field, minimum, maximum=2**53-1)` | `type(value) is int`，拒绝 bool、`1.0` 和 str，否则 `E_SCHEMA_TYPE`；越界为 `E_INTEGER_RANGE`。 |
| `validate_plan_version(v, *, allow_null=False)` | 正整数。`allow_null` 默认为 False（规格未给默认值，见第 18 节）。 |
| `validate_attempt(v)` | None 或非负整数。允许 0 只表示新格式允许；旧实现的首个编号为 1（01-D03），不平移历史编号。 |
| `validate_role(v, *, allow_null=False)` / `validate_platform(v)` | 封闭枚举，值不在集合内（包括类型不对）都为 `E_SCHEMA_FIELDS`。 |
| `platform_from_system(system)` | 精确映射：Linux 到 linux，Darwin 到 macos，Windows 到 windows。其他值（包括小写的 "linux"）为 `E_COMPAT_UNSUPPORTED`，不猜测为 linux。 |

### 5.2 运行上下文

**`validate_run_context(ctx, *, for_executor_dispatch=False, registry=None)`**：检查附录 A runContext 结构，字段封闭。检查顺序：

1. schema_version 与 record_type（与路由相同）；
2. 字段封闭：缺字段或有未知字段都为 `E_SCHEMA_FIELDS`；
3. 各字段本身。

`for_executor_dispatch=True` 时，`task_id`、`plan_version`、`attempt`、`contract_ref` 都必须非空，否则为 `E_CONTEXT_INCOMPLETE`；字段齐全后，`role` 还必须是 executor，否则为 `E_SCHEMA_FIELDS`（`/role`，reason 为 `executor_dispatch_requires_executor_role`；P4，与 C-04 一致）。planner、observer 上下文不能通过“进入 executor 派遣前”的检查（4.1.3）。

`registry` 给出时，`contract_ref.kind` 必须已登记；不给时只做形状与路径词法检查，并在返回值中声明。

**`derive_run_context(parent, action, *, attempt, new_task_id, new_plan_version, contract_ref, role)`**：按 4.1.2 表派生，不修改 parent，返回新字典，并用 `validate_run_context` 校验结果。

| action | request_id | run_id | attempt | 其他 |
|---|---|---|---|---|
| `reconnect` / `replay` | 保持 | 保持 | 保持 | 返回与 parent 相等的副本；不接受任何参数 |
| `executor_retry` | 保持 | 新建 | **取参数**（受信分配器给出，R-P2）：必须 ≥ parent.attempt，否则 `E_CONTEXT_BINDING`；未传入为 `E_CONTEXT_INCOMPLETE`；parent.attempt 为 None 时报 `E_CONTEXT_INCOMPLETE` | 父上下文 role 必须是 executor，否则 `E_SCHEMA_FIELDS`（`/role`，见 C-04）；只接受 `attempt` 参数；是否允许重试由 07 决定 |
| `observer_call` | 保持 | 新建 | 取参数（可为 None） | role 固定为 observer（传其他 role 报 `E_SCHEMA_FIELDS`） |
| `rework_new_contract` | 保持 | 新建 | 取参数（默认 None，“沿用调度器规则”由调用方给出） | `new_plan_version` 必填（否则 `E_CONTEXT_INCOMPLETE`）；contract_ref、role、new_task_id 可选 |
| `new_goal` | 新建 | 新建 | 取参数 | task_id、plan_version、contract_ref 取参数（默认 None） |

- 未知 action 报 `E_SCHEMA_FIELDS`。
- 传入不适用于该动作的非 None 参数也报 `E_SCHEMA_FIELDS`，不会静默忽略。
- 返回的是深拷贝（reconnect/replay 也不返回 parent 本身）；派生结果经 `validate_run_context` 校验，参数带入非法值时报对应码（例如 new_task_id 语法错误 `E_ID_SYNTAX`、attempt 为负 `E_INTEGER_RANGE`）。
- **先校验、再拷贝**（P4 第 3 轮，复审 json 视角）：parent 先经 `validate_run_context` 校验后才拷贝；`contract_ref` 参数先以原对象放进派生结果校验，通过后才深拷贝。所以过深（例如 5000 层、100000 层）、含不可拷贝对象（Lock、生成器）或 dict 子类的 `contract_ref`，与把它放进上下文直接调用 `validate_run_context` 得到同一个码与 field（`E_JSON_LIMIT` / `E_JSON_VALUE_TYPE`），不会漏出 RecursionError 或 TypeError；调用方对象的 `__deepcopy__`、`__reduce_ex__` 在校验前不会被执行，dict 子类也不能借 `__deepcopy__` 返回普通 dict 绕过类型精确检查。此前先拷贝后校验，这些输入漏出 RecursionError/TypeError（`test_A08_derive_validates_contract_ref_before_copy`）。
- **executor_retry 的 attempt 由调用方给出**（裁决 R-P2，P4 落实）：纯函数不再自行 `parent.attempt + 1`。调用方必须传入受信分配器给出的编号：现在是旧实现 `scripts/pi_dispatch.py` 的 allocate_attempt（第 2615–2623 行，“该任务已有 attempt 的最大值 + 1”），将来由 07 负责。
  - 编号必须 ≥ parent.attempt。相等表示同一 prepared attempt 的重新运行，符合旧规则“预检失败后再次 run 沿用原编号”（01-D03）；大于表示新的 prepared attempt（包括从非最新的 attempt 派生的情形）。
  - 缺失：`E_CONTEXT_INCOMPLETE`（`/attempt`，reason 为 `executor_retry_requires_allocated_attempt`）；倒退：`E_CONTEXT_BINDING`（`/attempt`，reason 为 `retry_attempt_below_parent`）；编号本身不合法按 `validate_attempt` 报码（`E_SCHEMA_TYPE` / `E_INTEGER_RANGE`）。
  - 本函数只核对单调性，不核对编号是否真由分配器给出、是否与持久记录一致（07）。

## 6. Schema 路由与记录校验（1.3、4.4.2）

### 6.1 路由

**`route_public_record(value, *, expected_record_type) -> int`** 按以下顺序检查：

1. `expected_record_type` 不在 `PUBLIC_RECORD_TYPES` 中：`E_COMPAT_UNSUPPORTED`。
2. value 不是 dict：`E_SCHEMA_TYPE`。
3. schema_version 不是精确正整数（true、"1"、1.0、0、缺失）：`E_SCHEMA_VERSION_TYPE`。
4. record_type 与期望不同（包括缺失）：`E_SCHEMA_RECORD_TYPE`。
5. 版本不受支持：`E_SCHEMA_VERSION_UNSUPPORTED`。

路由绝不回退到 v1，也不删除字段。家族由受信入口隐含决定，记录中没有 family 字段。

**`require_schema_version(value, supported)`** 保留参考实现的行为：只检查版本，不检查 record_type。

### 6.2 分派校验

**`validate_public_record(value, *, expected_record_type, registry, context=None, event_types=None, segment_sizes=None)`**：value 是 dict 且 expected_record_type 是公共记录类型时，先对整条记录做 JSON 原生值检查（P4，见下文），再路由，再分派到 `validate_run_context`、`validate_run_event` 或 `validate_usage_observation`。`registry` 必填，会传给三类记录中的**全部** ResourceRef 检查。返回检查报告：

```json
{"record_type": "run-event", "schema_version": 1, "structural": true,
 "payload_validated": false,
 "semantic_checks": ["identifier_syntax", "observed_at_calendar", "json_native_payload", "..."],
 "semantic_checks_skipped": ["seq_continuity", "raw_ref_bytes_digest", "core_event_claims", "..."]}
```

`payload_validated` 的含义：

- 对事件：只有 `event_types` 给出，且该类型的 `payload_validator` 实际运行过，才是 true。
- 对 run-context 和 usage-observation：没有开放载荷，所有字段都已封闭校验，所以恒为 true。

**不适用的参数不静默忽略**：参数不适用于该记录类型却给了非 None 值时，报 `E_SCHEMA_FIELDS`（reason 为 `parameter_not_applicable`），与 `derive_run_context` 的做法一致。

| 记录类型 | 接受的可选参数 |
|---|---|
| run-context | 无（`context`、`event_types`、`segment_sizes` 都不接受） |
| run-event | `context`、`event_types`、`segment_sizes` |
| usage-observation | `context` |

**整条记录先做 JSON 原生值检查**：三类记录的校验（以及 fixture manifest 条目与整份清单、单独调用的 `validate_raw_span`）在检查记录头之前，先对整条记录执行 `check_json_value(record, max_bytes=1 MiB)`。P4 起 `validate_public_record` 在路由之前做同样的检查，所以受信入口与直接调用的检查顺序相同（C-07）。因此：

- 整条记录（含 payload）共用 64 层上限：payload 自身 64 层时，整条记录 65 层，报 `E_JSON_LIMIT`。这与 `stable_snapshot_bytes`、`strict_json_loads`、`append_event` 的判断一致。
- 记录头字段的单一故障在两个入口得到同一个码与 field（`test_A09_public_entry_and_direct_validators_agree`）：schema_version 越出 ±(2^53-1) 报 `E_INTEGER_RANGE`，NaN/Infinity 报 `E_JSON_NON_FINITE`，IntEnum 等 int 子类与 str 子类的 `record_type` 报 `E_JSON_VALUE_TYPE`，含孤立代理项的 `record_type` 报 `E_JSON_UNICODE`。P4 之前经 `validate_public_record` 时这些情形报路由码（`E_SCHEMA_VERSION_UNSUPPORTED`、`E_SCHEMA_VERSION_TYPE`、`E_SCHEMA_RECORD_TYPE`），与直接调用不同。
- `route_public_record` 单独调用时的契约不变：它不做 JSON 原生值检查，要求 `record_type` 的类型精确为 str，否则报 `E_SCHEMA_RECORD_TYPE`。
- 记录中任何字符串（包括 path 字段）含孤立代理项时报 `E_JSON_UNICODE`。直接调用 `validate_business_path` 或 `validate_resource_ref` 时仍报 `E_PATH_SYNTAX`（C-17 不变）。
- 经 `strict_json_loads` 得到的值一定是 JSON 原生值、整数在范围内，所以这一顺序变化不影响任何 fixture 的期望错误码。

**受信 context 参数本身不合法**：这是调用方的错误，不是被校验记录的字段错误。错误码保持 `validate_run_context` 的原码，但 `field` 加前缀 `/context`（例如 `/context/platform`），`phase` 为 `context`。

### 6.3 语义检查名

| 名称 | 含义 | 何时出现在 skipped 中 |
|---|---|---|
| `json_native_record` | 整条记录是 JSON 原生值（类型、深度、整数范围、非有限数、孤立代理项、字节下界） | 不会 |
| `identifier_syntax` | request/run/task/usage 等标识语法 | 不会 |
| `resource_ref_shape` / `business_path_lexical` | ResourceRef 形状与 path 词法 | 没有引用时两类都不出现 |
| `resource_kind_registered` | kind 已登记，文件型带 path | 未提供 registry 时 |
| `executor_dispatch_fields` | executor 派遣所需字段非空，且 role 为 executor（P4） | 未要求 for_executor_dispatch 时 |
| `observed_at_calendar` / `json_native_payload` | 严格时间格式与日历；payload 为 JSON 原生值 | 不会 |
| `raw_span_range` / `raw_segment_size` | 字节区间；区间不超过被引用版本大小 | 未提供 segment_sizes 时（后者） |
| `context_binding` | 与受信上下文一致 | 未提供 context 时 |
| `event_type_registered` / `event_source_allowed` / `payload_validator` | 类型已登记、来源被允许、类型载荷校验 | 未提供 event_types，或该类型没有校验器时 |
| `vendor_evidence_present` | vendor 事件有 adapter_revision；声称 complete 时有 raw_refs | 非 vendor 事件不出现 |
| `usage_money_format` / `usage_billing_source_consistency` / `usage_unknown_reasons` / `usage_supersedes_self` | 单条用量语义 | 不会 |
| 恒为 skipped | `identifiers_allocated_by_trusted_core`、`contract_ref_matches_trusted_record`（07/09）、`resource_bytes_digest` / `raw_ref_bytes_digest` / `evidence_bytes_digest`（需要字节，见第 8 节）、`seq_continuity`（见第 11 节）、`core_event_claims`（04）、`usage_scope_dedup_and_revision`（见 usage_view）、`usage_accounting`（07） | — |

**注意**：各 `validate_*` 接收的是已经解析好的 dict，**不会**重新检查重复键、BOM 或 UTF-8。原始字节必须先经 `strict_json_loads`。

## 7. 业务路径（4.1.5–4.1.7）

**`validate_business_path(value, *, field="/path") -> str`**：只做可移植词法检查，原样返回，不做任何归一化。检查顺序：

1. 值必须是非空 str。
2. 不含孤立代理项。
3. 总长不超过 4096 个 UTF-8 字节（按字节计，不按码点计）。
4. 不以 `/` 开头；不含 `\`、`:`、`<`、`>`、`"`、`|`、`?`、`*`，从而拒绝反斜杠、盘符、UNC 与 ADS。
5. 不含控制字符。“控制字符”按 Unicode 类别 Cc 理解：C0（U+0000–U+001F）、DEL（U+007F）与 C1（U+0080–U+009F，例如 U+0085 NEL、U+009B CSI）。P2 返工前只拒绝 C0 与 DEL（沿用参考实现），见 R-05。
6. 不含行/段分隔符 U+2028、U+2029 与双向控制字符 U+061C、U+200E、U+200F、U+202A–U+202E、U+2066–U+2069（reason 为 `line_separator_or_bidi_control`；裁决 R-P4，P4 落实）。前者会被 `str.splitlines()` 断行（日志注入），后者可让显示顺序与实际字节顺序不同（Trojan Source）。其他格式字符（例如 ZWNJ U+200C、ZWJ U+200D、ZWSP U+200B）不拒绝。
7. 按 `/` 分段，每段检查：
   - 不能是空段、`.` 或 `..`；
   - 不能以点或空格结尾（末尾斜杠会产生空段）；
   - 不超过 255 个 UTF-8 字节。

第 1–6 步检查整条路径，任一项不满足报 `E_PATH_SYNTAX`。第 7 步按分段**依次**进行：每一段先做上面三项语法检查（`E_PATH_SYNTAX`），再检查下面的 Windows 保留名称（`E_PATH_RESERVED`），然后才轮到下一段。所以前一段的保留名先于后一段的语法错误报告：`NUL/a.` 与 `ABCDEF~1/a.` 报 `E_PATH_RESERVED`，`a./NUL` 报 `E_PATH_SYNTAX`。多缺陷输入不承诺首错（第 3.2 节）；P4 第 3 轮之前本节写成“全部分段的语法检查之后再检查保留名”，与实现不符，已更正。

每一段的 Windows 保留名称检查（命中时报 `E_PATH_RESERVED`）：

- 设备名（reason 为 `reserved_device_name`）：CON、PRN、AUX、NUL、CONIN$、CONOUT$、COM0–COM9、LPT0–LPT9、COM¹²³、LPT¹²³。
  - 大小写不敏感，但**只做 ASCII 大小写折叠**。`str.upper()` 按 Unicode 映射，会把 `CON\u0131N$`（U+0131 无点 i）误判为 CONIN$，而本机 Windows 把它当普通文件名。全角字母（`ＣＯＮ`）与全角数字（`COM１`）同样不算设备名，本机实测它们都是普通文件。
  - 带扩展名同样命中（NUL.txt、nul.tar.gz）。
  - 基名末尾有空格同样命中（`NUL .txt`）。
- 8.3 短名形态（reason 为 `windows_short_name_form`；裁决 R-P3，P4 落实，P4 第 3 轮扩展）：分段形如 `ABCDEF~1`、`PROGRA~1.TXT`，即基名是 1–6 个非 `.` 字符的前缀 + `~` + 数字、基名总长不超过 8（8.3 格式的上限），可带 1–3 个字符的扩展名；大小写不敏感。正则为 `([^.]{1,6}~[0-9]+)(?:\.[^.]{1,3})?`（整段匹配），另要求第一组不超过 8 个字符。在 Windows 上这样的名称可能是另一文件的别名（例如 `AGENTS~1.MD`、`.agent` 的短名 `AGENT~1`），会绕过只按字符串比较的保护路径（与 git 的 `core.protectNTFS` 同类）。
  - **前缀允许含 `~`**（P4 第 3 轮，复审 paths 视角 major）：长名前 6 个有效字符含 `~` 时，Windows 自动生成的短名前缀也含 `~`。本机实测：`~$document.docx` → `~$DOCU~1.DOC`，`a~bcdefghijk.txt` → `A~BCDE~1.TXT`，`.~agentconfig` → `~AGENT~1`，`中文~文档说明书.txt` → `~A4EF~1.TXT`（哈希形态）。P4 时的形态定义（前缀不含 `~`）漏掉了这一类，它们能绕过只按字符串比较的下游。代价是 `a~b~1`、`x~y~2.txt` 这类基名不超过 8、前缀含 `~` 的普通名称也被拒绝（保守方向）。这与裁决 R-P3 原文“1–6 个非 `~` 字符”不同，处理与理由见第 19 节“P4 第 3 轮”第 12 条。**收尾轮已由规划端确认**：decisions.md 末尾的“R-P3 勘误”裁定以实现为准，原文那一句作废。勘误把判定概括为“基名以 `~` 加 1–6 位数字结尾、基名总长 ≤ 8、扩展名 ≤ 3”；实现另要求 `~` 之前至少有 1 个字符（正则第一组的 `[^.]{1,6}`），所以没有前缀的 `~1`、`~12` 照常接受（见下一条），按勘误“以实现为准”处理。
  - 不是这一形态的 `~` 名称照常接受，例如 `~/notes.txt`、`a~b.txt`、`~1`、`backup~2024.tar`（基名超过 8）、`~~~~~~~~1`（基名 9 个字符）、`notes~1.json`、`PROGRA~1.HTML`（扩展名 4 个字符）、`notes~1.json5`。扩展名恰好 3 个字符时拒绝（`ABCDEF~1.JSO`）。
  - 手工设置、不含 `~` 的短名（`fsutil file setshortname`）不是这一形态，词法层接受，由物理层兜底（见下文）。

**词法合法只意味着进入下一层检查**，不代表允许访问（4.1.6），也**不代表对象身份唯一**：

- 大小写不同的拼写在词法层合法，却可能在磁盘上指向同一个对象；用 `fsutil file setshortname` 手工设置、不含 `~` 的短名同理。
- 物理层的 `resolve_existing_path_for_review` 与 `sealing` 会核对每一级拼写是否正是目录中登记的真实名称（见下文）：自动生成的 8.3 短名在词法层已被拒绝，物理层兜底的是手工设置的短名与大小写别名。只按字符串比较业务路径、不做物理核对的下游，对手工设置的短名没有保护。
- 只按字符串比较业务路径的下游（例如 03 的保护范围）仍须按 NFC + casefold 比较名称，或使用 `check_no_name_collisions`。

**ANSI best-fit 字符不拒绝（裁决 R-P5，不增加严格 profile）**：全角或兼容字符在 ANSI 代码页的 best-fit 转换后会变成路径元字符，例如本机代码页 1252 下 `．．＼victim.txt`（U+FF0E U+FF0E U+FF3C）会变成 `..\victim.txt`（WorstFit 类问题）。Python 与 Git for Windows 使用宽字符（W）API，01 内不能利用，所以词法层不拒绝这些字符（`test_A10_ansi_best_fit_characters_not_rejected` 固定这一裁决）。**限制**：把业务路径交给使用 ANSI 代码页 API 的程序（例如经 `CreateProcessA` 或窄字符命令行传递）的消费者，必须自行复核 best-fit 映射后的结果。

**`find_name_collisions(paths) -> list[list[str]]`**：

- 按 `unicodedata.normalize("NFC", p).casefold()` 对**整条路径**分组，返回含多个不同原始拼写的组。完全相同的拼写不算碰撞。结果已排序。
- 这是跨平台的保守近似，不等于任何一个文件系统的精确规则。
- 它不检查目录前缀，完整检查请用 `check_no_name_collisions`。

**`check_no_name_collisions(paths)`**：发现碰撞时报 `E_PATH_COLLISION`，不回显路径。按以下顺序检查（P2 返工扩展，见 R-06）：

1. 整条路径碰撞（reason 为 `case_or_normalization_collision`）；
2. 某一级目录前缀在 NFC + casefold 后同名、拼写不同，例如 `Fixtures/a.json` 与 `fixtures/b.json`：它们在 Windows/macOS 上落进同一目录，在 Linux 上是两个目录（reason 为 `directory_prefix_collision`）；
3. 同一名称（NFC + casefold 后）既是文件又是目录前缀，例如 `data` 与 `DATA/x.json`，或 `data` 与 `data/x.json`（reason 为 `file_directory_conflict`）。

`validate_fixture_manifest_set` 使用这个函数，因此清单层同样能检出。

### 物理检查的定位（裁决 R-P9）

- 物理检查指 `resolve_existing_path_for_review`（见下文）、它与 sealing 共用的链接逐跳核对 `_check_link_hops`，以及第 15 节 sealing 的路径步进。它们是“静态审阅 + 纵深防御”，**不是安全访问保证**（01-D06；设计文档 4.1.6–4.1.7：01 不提供安全写文件的万能函数）。生产级安全访问由后续访问实现模块另行设计与验收，01 不再继续扩展解析逻辑。
- 遇到无法确定语义的链接写法一律**失败关闭**（`E_PATH_RESOLUTION_FAILED`），不猜测放行。
- 本节只按下面两张清单描述能力：“已检测的情形”与“已知不检测、不保证”。代码中对应的常量是 `protocols.PATH_REVIEW_LIMITATIONS` 与 `sealing.SEALING_LIMITATIONS`（第 15 节）。
- P4 第 3、4 轮复审围绕逐跳核对连续发现了 Windows 解析语义的绕过，这是做出 R-P9 裁决的背景。所以下面的清单不表示“已检测之外的写法都安全”。

**已检测的情形**（本机 Windows Server 2025 + Python 3.12.10 实测，逐项有测试；Linux/macOS 为 NOT_RUN）：

| # | 情形 | 结果 | 测试 |
|---|---|---|---|
| 1 | 某一级 `resolve(strict=True)` 后的最终目标在根外：文件 symlink、目录 symlink、junction，目标本身是目录链接 | `E_PATH_ESCAPE`（`resolved_outside_trusted_root`） | `test_F027_symlink_escape`、`test_F028_junction_escape`、`test_A10_target_is_directory_link` |
| 2 | 多分段路径的中间一级落到根外、之后又经链接绕回根内（`out/back/ok.txt`） | `E_PATH_ESCAPE`，在中间那一级报告，不在根外列目录 | `test_A10_path_through_outside_is_escape` |
| 3 | 链接指向“只在 `str.lower()` 下与根同名”的兄弟目录：名称含 U+212A；用 `fsutil file setCaseSensitiveInfo` 启用大小写敏感的目录中的 `repo`/`REPO` | `E_PATH_ESCAPE` | `test_A10_kelvin_sign_sibling_is_escape`、`test_A10_case_sensitive_directory_sibling_is_escape`（fsutil 不可用时 skip） |
| 4 | 同一分段内经根外链接绕回根内的链：文件 symlink、目录 symlink、junction，以及目标文本经过根外 junction 的 symlink | `E_PATH_ESCAPE`（`link_hop_outside_trusted_root`） | `test_A10_single_segment_link_chain_through_outside_is_escape` |
| 5 | 以相对目标开头的越界链：`relhop → hop2`、`sub/up → ..\hop2`、目录链 `reld → dhop2` | 同上 | `test_A10_relative_link_chain_through_outside_is_escape` |
| 6 | Windows 相对目标中的 `..` 按词法折叠：`<根内链接>\..\<名称>` 形式的越界链（文件链与目录链） | 同上；`missing\..\y.txt`、`L\..\sub\inner.txt`、`L\..\..\repo\ok.txt` 形式的根内链照常接受 | `test_A10_windows_link_target_dotdot_is_lexical` |
| 7 | 名称末尾带点或空格、指向根外的链接（`hop.`、`hop `、`dhop.`，经 `\\?\` 创建） | 同上；根内名称为 `dd.` 的真实目录照常可用 | `test_A10_link_target_names_with_trailing_dot_or_space` |
| 8 | 目标写法不受支持或语义无法确定（清单见下文“逐跳核对”） | `E_PATH_RESOLUTION_FAILED`（`link_target_form_unsupported`） | `test_A10_split_link_target_forms`、`test_A10_windows_link_target_forms_measured`、`test_A10_link_walk_unsupported_form_and_divergence` |
| 9 | 未识别的名称代理类重解析点：标签带名称代理位 0x20000000，却不是 symlink，也不是 junction/挂载点（P4 第 5 轮） | `E_PATH_RESOLUTION_FAILED`（`link_kind_unsupported`） | `test_A10_unrecognized_name_surrogate_reparse_point_fails_closed`（白盒）；`test_A10_windows_link_target_forms_measured`（黑盒：本机没有处理该标签的过滤驱动，resolve 先行失败，报 `static_resolution_failed`） |
| 10 | 逐跳展开的终点与这一级 resolve 的结果不同 | `E_PATH_RESOLUTION_FAILED`（`link_walk_diverged`） | `test_A10_link_walk_unsupported_form_and_divergence` |
| 11 | 跳数超过 64、中间分段无法解析、读取链接时出错（P4 第 5 轮补测） | `E_PATH_RESOLUTION_FAILED`（`link_hop_limit_exceeded`、`link_hop_unresolvable`、`link_hop_unreadable`） | `test_A10_link_walk_failure_reasons_fail_closed`（白盒） |
| 12 | 链接环 | `E_PATH_RESOLUTION_FAILED`（`static_resolution_failed`） | `test_A10_symlink_loop_resolution_failed` |
| 13 | 悬空的目录 symlink 与悬空的 junction | `E_PATH_NOT_FOUND` | `test_A10_dangling_links_not_found` |
| 14 | 大小写或 Unicode 形式别名 | `E_PATH_COLLISION`（`spelling_differs_from_existing_name`） | `test_A10_filesystem_aliases_rejected` |
| 15 | 手工设置、不含 `~` 的短名（`fsutil file setshortname`） | `E_PATH_RESOLUTION_FAILED`（`noncanonical_filesystem_alias`） | `test_A10_manual_short_name_alias_black_box`、`test_A13_short_name_aliases_rejected_by_all_entries`（fsutil 不可用时 skip） |
| 16 | 自动生成的 8.3 短名，包括前缀含 `~` 的 | 词法层 `E_PATH_RESERVED` | `test_A10_generated_short_names_with_tilde_prefix_reserved` |

对照（照常接受）：根内的 symlink 与 junction，目标本身是根内目录链接时返回解析后的目录；以 junction 为根、以大小写不同的写法为根，返回值都相同（`test_A10_root_variants`）；根内的链接链，包括绝对目标、相对目标、含 `..` 的相对目标。

**已知不检测、不保证**（与 `PATH_REVIEW_LIMITATIONS` 一致）：

1. **TOCTOU 与并发替换**：返回的 Path 不是访问凭证，检查与使用之间路径可能被替换（01-D06）。
2. **检查之后父目录或目标被替换**（包括被换成指向根外的链接）：已完成的检查不再成立。sealing 中下一级 `mkdir` 或随后的发布可能因此落到根外（第 15 节）。01-F029 按 01-D06 为 skip。
3. **硬链接**：与根外文件共享数据的硬链接，在路径层面与普通文件无法区分。复审复现：`os.link(outside/secret.txt, repo/h.txt)` 之后，`resolve_existing_path_for_review` 接受 `h.txt`，`read_sealed` 返回根外文件的字节，`seal_bytes` 按幂等接受相同字节。`test_A13_hard_link_alias_is_known_not_detected` 固定这一行为，使清单与实际一致；它不是安全性测试，01-F030 仍为 skip。
4. **挂载点**：
   - Windows 上以卷 GUID 为目标（`\\?\Volume{GUID}\…`）的 junction，即卷挂载点的写法，按不受支持的写法失败关闭。本机用 FSCTL 造出这种 junction 实测：内核能跟随，`resolve_existing_path_for_review` 报 `link_target_form_unsupported`。经挂载管理器登记的真实卷挂载点未实测。
   - `_is_within` 按组件逐字比较，经挂载点解析到另一卷时会报越界（保守方向，可能误报）。
   - POSIX 的 bind mount 等挂载不是链接，不检测。
5. **NT 层与 Win32 层名称语义差异**：只覆盖已枚举的写法，即分段末尾的点与空格、下文列出的目标文本写法、名称代理类重解析点。尚未枚举的写法不保证被识别。
6. **不带名称代理位的重解析点**（去重、云文件、WOF 压缩、AppExecLink 等）按普通名称处理。处理它们的过滤驱动若在打开时重定向，不在检测范围内。
7. **POSIX 平台未实测**（NOT_RUN）：按物理语义处理 `..` 的分支只有白盒注入（`test_A10_link_walk_physical_dotdot_branch`）；把名称存成 NFD 的文件系统（例如 macOS 的 HFS+）上的拼写核对同样未实测。
8. **同一账户下其他进程的篡改**。
9. **根目录本身**：根（含其祖先与根路径上的链接）经 resolve 后作为可信起点，不做逐跳核对。根的可信性由调用方负责。

### `resolve_existing_path_for_review(root, business_path) -> Path`：静态审阅专用

**流程**（上面的已检测情形按下面的顺序出现）：

1. `root.resolve(strict=True)`，且结果必须是目录；任何失败都报 `E_PATH_ROOT`。
2. **逐级**解析：每一级都执行 `resolve(strict=True)`，会跟随 symlink 与 Windows junction。
   - 不存在（包括中间段是文件、悬空的链接）报 `E_PATH_NOT_FOUND`；
   - 其他 OSError 或 RuntimeError（例如链接环，或内核拒绝解析的链接写法）报 `E_PATH_RESOLUTION_FAILED`（`static_resolution_failed`）；
   - 这一级解析后的最终目标在根外，报 `E_PATH_ESCAPE`（`resolved_outside_trusted_root`）。多分段路径的中间一级落到根外、之后又绕回根内时，在中间那一级报告；只在已确认位于根内的目录中列目录名称。
   - **逐跳核对链接链**（`_check_link_hops`，protocols 与 sealing 共用；P4 第 3 轮引入，第 4、5 轮修正）：`resolve(strict=True)` 只给出一个分段的最终目标。同一分段内的链接链（根内链接 → 根外链接 → 根内目标，例如 `repo/hop → outside/hop2 → repo/ok.txt`，或目录链 `repo/dhop → outside/dhop2 → repo/sub`）最终目标在根内，P4 时被接受，解析结果却依赖根外对象。现在对每一级用 `os.lstat`/`os.readlink` 按下述规则逐跳展开。展开时遇到的链接对象（symlink 或 junction，包括目标文本中经过的中间链接），若它所在目录解析后的真实路径不在根内（按 `_is_within` 逐字比较），报 `E_PATH_ESCAPE`（`link_hop_outside_trusted_root`）。
     - 目标文本中经过的非链接目录（例如根的祖先目录、8.3 形式的用户目录 `C:\Users\EXAMPL~1`）只决定名称如何拼接，不单独判定。
     - Windows 相对目标中的 `.` 与 `..`（P4 第 4 轮，复审 fidelity 与 paths 视角 major）：本机实测 I/O 管理器处理相对 symlink 时，把链接所在目录与目标文本拼接，再按**词法**折叠 `.` 与 `..`：`x\..\y` 等同于 `y`，不访问 x。x 是指向 `deep\dir` 的目录链接时，OS 经过的仍是链接所在目录下的 y，而不是 `deep\y`。逐跳核对同样先按词法折叠目标文本：目标内部的 `<名称>\..` 成对消去，空分段与 `.` 跳过；折叠后剩下的开头 `..` 作用于链接所在的真实目录。这个目录来自 resolve，其中没有链接，所以词法上一级就是物理上一级。
       - P4 第 3 轮的实现按“先跟随 `..` 前面的链接，再取真实目录的上一级”处理，与 OS 走的不是同一条链。结果有两个方向的错误：
         - 漏报：`a/l → x\..\y`，其中 `a/y → outside/hop2 → repo/ok.txt`，这条链被接受；目录链 `a/ld → xd\..\yd` 让 `seal_bytes` 经根外链接写入文件。
         - 误报：`missing\..\y.txt`、`L\..\sub\file.txt` 这类根内的链被报为 `E_PATH_RESOLUTION_FAILED`。
     - 逐字绝对目标（`\\?\C:\…`）中的 `.`、`..` 与空分段（P4 第 5 轮更正）：本机实测内核**不**按词法折叠，而是拒绝解析（`..` 与空分段为 ERROR_INVALID_NAME，`.` 为 ERROR_PATH_NOT_FOUND），所以 resolve 先行失败。P4 第 4 轮文档写“绝对目标同样按词法折叠”，与实测不符，已删除；逐跳核对对这类文本返回“不受支持”，只是保守兜底。
     - POSIX：设计意图是按物理语义处理 `..`（先跟随前面的链接），逐跳核对同样如此。NOT_RUN，只有白盒注入。
     - Windows 上逐跳核对按逐字路径（`\\?\` 前缀）调用 lstat、readlink 与 resolve（P4 第 4 轮，复审 paths 视角 major）。内核在 NT 层逐字使用目标文本中的名称，Win32 路径规范化却会去掉分段末尾的点与空格。NTFS 允许 `hop.`、`hop ` 这类名称（经 `\\?\` 创建）；它们是指向根外的链接时，经 Win32 访问看到的是不存在的 `hop`。P4 第 3 轮的实现因此漏掉了链上的根外链接，这是与 `..` 无关的另一条绕过途径。
     - 兜底检查（P4 第 4 轮）：这一级的链上至少有一个链接时，逐跳展开的终点必须与这一级 `resolve(strict=True)` 的结果逐字相同（`_exact_parts`），否则报 `E_PATH_RESOLUTION_FAILED`（`link_walk_diverged`）。终点相同不能证明途经的链接相同，所以它只兜住“展开走到了别处”的情形，不能代替上面几条规则。
     - 以下情形失败关闭，报 `E_PATH_RESOLUTION_FAILED`：
       - 跳数超过 64（`link_hop_limit_exceeded`）；中间分段无法解析（`link_hop_unresolvable`）；读取链接出错（`link_hop_unreadable`）。
       - 未识别的名称代理类重解析点（`link_kind_unsupported`；P4 第 5 轮，R-P9 (1)）：lstat 报告的标签带名称代理位（0x20000000），却既不是 IO_REPARSE_TAG_SYMLINK，也不是 IO_REPARSE_TAG_MOUNT_POINT，例如 GLOBAL_REPARSE、LX_SYMLINK、WCI_LINK 或第三方标签。CPython 的 lstat 对这类对象报告普通文件或目录；P4 第 4 轮之前把它们当作普通名称，逐跳核对跳过它们。过滤驱动会跟随这类对象的机器上，经根外绕回根内的链因此被接受。
       - 目标写法不受支持或语义无法确定（`link_target_form_unsupported`）。受支持的只有两种写法：
         - 相对目标（不以 `\` 开头、不带盘符），按上面的词法规则处理；
         - 逐字绝对目标 `\\?\<盘符>:\…` 与 `\\?\UNC\…`，也就是 os.symlink 与 junction 写下的 `\??\` 形式。末尾的一个分隔符忽略（本机实测带末尾分隔符的目录 symlink 照常解析，`test_A10_windows_link_target_forms_measured`）。
       - 以下写法都不受支持：
         - 只有盘符的半相对路径（`C:x`）；
         - 不带 `\\?\` 的盘符绝对路径（`C:\x`）：本机实测相对、绝对两种标志位下内核都拒绝（ERROR_INVALID_NAME）；
         - **只有根、没有盘符的目标（`\x`）**（P4 第 5 轮起不受支持，此前按“从链接所在盘的根起算”支持）。`os.readlink` 不给出相对/绝对标志位，同一形状的文本有两种语义：在相对标志下从链接所在盘的根起算（本机实测，`..` 按词法折叠）；在绝对标志下是 NT 命名空间路径。本机实测 `\Device\HarddiskVolumeN\…`、`\GLOBAL??\C:\…` 形式的绝对链接都能被内核跟随。语义无法确定，所以失败关闭；
         - 逐字绝对目标中含 `.`、`..` 或空分段（见上）；
         - 卷 GUID 等其他逐字设备路径（包括卷挂载点的目标），以及 `\\.\` 设备路径；
         - 不带 `\\?\` 的 UNC 文本；
         - 含 `/` 的目标：NT 层不把 `/` 当分隔符，本机实测这类链接无法解析；
         - `..` 越过盘符根：本机实测内核同样拒绝。
       - 标志位与文本不一致的写法（相对标志配 `\??\` 文本、绝对标志配相对文本）：本机实测内核拒绝解析（ERROR_INVALID_NAME），resolve 先行失败，逐跳核对不会执行（`test_A10_windows_link_target_forms_measured`）。
     - 只读元数据（lstat、readlink、resolve），不读文件内容，不消除 TOCTOU。
   - “位于根内”的判定（`_is_within`，protocols 与 sealing 共用）：resolve 后根的路径组件必须是目标路径组件的**逐字**前缀。两边都来自 `resolve(strict=True)`，Windows 上是 GetFinalPathNameByHandle 给出的磁盘真实拼写，所以按组件逐字比较。它只比较两个路径字符串，不核对对象身份：硬链接、挂载点与检查之后的替换不在它的判断范围内（见“已知不检测”）。
     - **不用** `PurePath.relative_to`：`PureWindowsPath` 按 `str.lower()` 比较，而 NTFS 的名称等价规则不同。K 与 U+212A（开尔文符号）、å 与 U+212B、ω 与 U+2126、ß 与 U+1E9E 等在 `lower()` 后相同，在 NTFS 上却是两个名称；按目录启用了大小写敏感的 NTFS 目录（WSL 建的目录默认如此）中任何字母都是如此。P2 第二轮返工前，指向这类兄弟目录的链接会被判为根内（复审 paths 视角 blocker，见 R-14）。
     - 拼写不同一律算越界，例如经卷挂载点解析到另一卷时会误报 `E_PATH_ESCAPE`，这是有意的保守方向。
     - Windows 路径比较前去掉 resolve 可能保留的 `\\?\` 前缀：超长路径，或路径中有名称以点或空格结尾的目录（例如经链接到达的根内目录 `dd.`）时，resolve 会保留这个前缀。
3. 每一级的拼写必须正是上一级目录中登记的真实名称（按 `os.listdir` 逐字比较）：
   - 只差大小写或 Unicode 形式（大小写不敏感的文件系统上能解析到同一对象）报 `E_PATH_COLLISION`，reason 为 `spelling_differs_from_existing_name`；
   - 其他未列出的别名报 `E_PATH_RESOLUTION_FAILED`，reason 为 `noncanonical_filesystem_alias`。自动生成的 8.3 短名形态在第一步的词法检查中已报 `E_PATH_RESERVED`（R-P3），这里兜底的是手工设置、不含 `~` 的短名；
   - 目录无法列出时报 `E_PATH_RESOLUTION_FAILED`，reason 为 `directory_listing_failed`（没有单独的用例）。
   - 在把名称存成 NFD 的文件系统（例如 macOS 的 HFS+）上，NFC 拼写会报 `E_PATH_COLLISION`（NOT_RUN）。

- 返回值基于 **resolve 后的根** 计算。根的写法是 8.3 短名（例如 `C:\Users\EXAMPL~1\…`，本机账户的短名按 baseline-report 的约定记为 `<X:8.3>`）、junction，或大小写不同时，返回值都是长名路径，测试应与 `root.resolve() / …` 比较。
- 返回的 Path **不是访问凭证**：不能在之后按这个路径 `open()`，它也**不消除 TOCTOU**（01-D06）。
- Linux/macOS 为 NOT_RUN。

## 8. ResourceRef、类型注册表与依赖环（4.2.1–4.2.3、4.2.8）

- **`ResourceKind(name, is_file, owner_module, description, *, schema_ref, payload_representations, payload_validator)`**：不可变。name 必须匹配 `^[a-z][a-z0-9-]{0,63}$`。后三项由裁决 R-P10（收尾轮，acceptance.md M-10）新增，对应文档 4.2.1“kind 注册表应包含 schema、是否文件资源、允许的载荷表示、语义校验器及所属模块”，都是关键字参数：
  - `schema_ref`：本地受信 Schema 标识（1–256 个可打印 ASCII 字符，不含空白），或 None（没有独立的 Schema 文件）。01 只登记这个标识，**不加载 Schema 文件**（本机无 jsonschema，01-L01、01-L07）；非 None 时 `validate_resource_payload` 把 `resource_schema` 列入 skipped。
  - `payload_representations`：允许的载荷表示，`PAYLOAD_REPRESENTATIONS`（json、text、markdown、binary）的非空子集，保存为 frozenset。
  - `payload_validator`：可调用对象 `payload_validator(raw: bytes, registry) -> None`，载荷不合法时抛 ProtocolError；或 None。它接收的是已核验摘要的同一份字节，以及调用方传入的注册表（fixture-manifest 的校验器要用它核对清单中的引用）。
  - 三项都可以不传，这时属性值是内部的“未声明”标记，`undeclared_fields()` 按 `RESOURCE_KIND_DECLARED_FIELDS` 的顺序列出未声明的项；但**未声明的登记项不能进入注册表**（见下一条）。显式传入的值不合法时抛 `ValueError`（与 name 等字段相同，不是 ProtocolError）。
- **`ResourceKindRegistry(kinds)`**：构造后不可变，不能增删改。
  - 提供 `get`、`in`、`[]`、`names()`、`items()`、`is_file_kind()`。
  - `extended(kinds)` 返回新对象；遇到同名项报 `ValueError`，不覆盖（测试断言 06 等下游不能把 `fixture` 改成非文件型，也不能给 `run.prepared` 加上 vendor 来源）。
  - **登记时必须声明三项**（R-P10）：构造与 `extended()` 都检查每个登记项，缺 `schema_ref`、`payload_representations`、`payload_validator` 中的哪一项都报 `E_SCHEMA_FIELDS`（field 为 `/<首个缺失项>`，reason 为 `resource_kind_registration_incomplete`，phase 为 resource），原注册表不变。显式声明为 None（schema_ref、payload_validator）不算缺失。检查顺序：登记项类型（`TypeError`）→ 三项已声明 → 同名项（`ValueError`）。
  - 不可变性的具体表现：`reg[name] = …`、`del reg[name]`、`reg._items[…] = …` 报 `TypeError`（内部表是只读映射）；给注册表或登记项的属性赋值、删除属性报 `AttributeError`。`EventTypeRegistry` 与 `EventType` 相同。
- **`build_default_registry()`**：只登记 01 自己的 `fixture`、`fixture-manifest`、`public-schema`、`baseline-evidence`（文件型，owner "01"），以及 `raw-segment`（文件型，owner "04"）。`raw-segment` 由 01 预登记引用封装，分段语义归 04。各类型的三项（R-P10）：

  | kind | schema_ref | payload_representations | payload_validator |
  |---|---|---|---|
  | fixture | None | json、text、markdown、binary | None |
  | fixture-manifest | None | json | 严格解析（`strict_json_loads`）加 `validate_fixture_manifest_set` |
  | public-schema | None | json | 严格解析；根必须是对象（否则 `E_SCHEMA_TYPE`），`$id` 必须恰为 `SCHEMA_ID`（否则 `E_SCHEMA_FIELDS`，`/$id`，reason `public_schema_id_mismatch`）；不做元校验 |
  | baseline-evidence | None | json、text、binary | None |
  | raw-segment | None | binary | None（分段语义归 04） |

  - schema_ref 都为 None：01 没有为这五类单独登记 Schema 文件。fixture-manifest 的结构（附录 C.1 所说“需在正式实施时登记 fixture-manifest Schema”）由校验器代码表达，即第 14 节的规则。
  - 其他模块用 `extended()` 登记自己的类型，例如 09 的合同、06 的插件锁、03 的审核记录，**必须同时声明三项**。本模块不提供“任意内容都可信”的通用类型。
- **`validate_resource_payload(ref, raw, registry) -> dict`**（R-P10 新增）：按资源类型登记的三项核验载荷。检查顺序：
  1. registry 必须是 `ResourceKindRegistry`（否则 `TypeError`）；
  2. 按 `verify_resource_bytes` 核验引用与字节：结构、kind 已登记、文件型带 path、path 词法、raw 为 bytes、完整 SHA-256（错误码同该函数）；
  3. 字节符合该类型的 `payload_representations` 之一：binary 接受任何字节；json 要求 `strict_json_loads` 通过（默认 1 MiB、64 层）；text 与 markdown 要求严格 UTF-8 解码成功（两者的字节检查相同，区别只是登记用的标签）。都不符合时，允许 json 就报严格解析的原错误码（例如 `E_JSON_SYNTAX`、`E_JSON_BOM`、`E_JSON_LIMIT`），否则报 `E_JSON_ENCODING`（reason `payload_not_utf8_text`）；
  4. 执行该类型的 `payload_validator(raw, registry)`。它抛出的 ProtocolError 原样传出；抛出其他异常（包括 KeyError、TypeError、RecursionError）时，包装为 `E_SCHEMA_FIELDS`（reason `payload_validator_unexpected_exception`，phase resource，field 为 None）。包装后的错误只含固定文案，不含原异常的文字，也不链接原异常（`__cause__` 与 `__context__` 都为 None），不回显输入。

  返回检查报告 `{"kind", "payload_validated", "semantic_checks", "semantic_checks_skipped"}`：

  | 检查名 | 含义 | 何时出现在 skipped 中 |
  |---|---|---|
  | `resource_ref_shape` / `resource_kind_registered` / `business_path_lexical` | 引用结构、kind 已登记、path 词法（没有 path 时不出现） | 不会 |
  | `resource_bytes_digest` | 完整 SHA-256 与引用一致 | 不会 |
  | `payload_representation` | 字节符合登记的载荷表示之一 | 不会 |
  | `payload_validator` | 该类型的语义校验器已运行（此时 `payload_validated=true`） | 该类型没有校验器时 |
  | `resource_schema` | 按 schema_ref 做 Schema 校验 | schema_ref 非 None 时恒为 skipped（01 不加载 Schema 文件）；为 None 时不出现 |

  通过只说明字节与登记的表示、校验器一致，**不说明来源可信、已授权或已审核**。
- **`validate_resource_ref(ref, registry, *, field="")`**：按以下顺序检查。
  1. 值不是 dict：`E_SCHEMA_TYPE`。
  2. 缺必需字段或有未知字段：`E_SCHEMA_FIELDS`。
  3. kind、id、sha256 语法错误：`E_RESOURCE_FIELD`（大写、短摘要、`sha256:` 前缀、尾随换行都拒绝）。
  4. kind 未登记：`E_RESOURCE_KIND`。
  5. 文件型缺 path：`E_RESOURCE_PATH_REQUIRED`。
  6. 按 `validate_business_path` 检查 path。

  不读取资源，也不核对字节。
- **`verify_resource_bytes(ref, raw, registry)`**：raw 必须是 bytes（`E_RESOURCE_BYTES`）。在调用方**已固定的同一份字节**上用 `hmac.compare_digest` 比较，不符为 `E_RESOURCE_HASH_MISMATCH`。例如把 LF 改成 CRLF 就会不符。
- **`check_resource_dag(edges) -> list[str]`**：`edges[a]` 是 a 引用的节点。
  - 返回确定性的拓扑序，被引用者在前。
  - 自环或多节点环报 `E_RESOURCE_CYCLE`，其 `field` 是环上某个节点的指针 `/<节点>`。
  - 采用迭代实现，深链不会触发递归上限。

## 9. Git OID（4.2.3）

- **`validate_git_oid(value, object_format, *, field="/oid")`**：sha1 为 40 位小写十六进制，sha256 为 64 位。
  - 其他对象格式报 `E_GIT_FORMAT_UNSUPPORTED`，不按长度猜测。
  - 分支名、短 OID、大写、revision 表达式、前导 `-`、非 str 都报 `E_GIT_OID_SYNTAX`。
- **`git_cat_file_type_argv(oid, object_format)`**：先校验 OID，再返回受信 argv `["git","cat-file","-t",oid]`。调用方负责执行，不经 shell；本模块不执行。
- **`interpret_git_object_type(expected_type, returncode, stdout)`**：
  - expected_type 只接受 commit 或 tree，其他报 `E_COMPAT_UNSUPPORTED`。
  - returncode 非 0 或为 None 报 `E_GIT_OBJECT_MISSING`。
  - 输出与期望类型不符报 `E_GIT_OBJECT_TYPE`，例如 candidate_tree 实为 commit。
  - stdout 允许带一个结尾的 `\n` 或 `\r\n`。
  - 已在本仓库对真实 commit、tree 和不存在的对象做只读实测。
- 仓库对象格式（`git rev-parse --show-object-format=storage`）由调用方查询并传入。

## 10. 时间（4.3.1）

- **`format_observed_at(dt)`**：dt 必须是带时区的 datetime，转成 UTC，格式为 `YYYY-MM-DDTHH:MM:SS.ffffffZ`；年份补足 4 位。naive datetime 或 date 报 `E_TIME_FORMAT`；转成 UTC 时越出 datetime 可表示的年份（例如 9999 年末的西五区时间）同样报 `E_TIME_FORMAT`（reason 为 `utc_conversion_failed`），不泄漏 OverflowError。
- **`parse_observed_at(s, *, field="/observed_at")`**：严格匹配上述格式并检查日历有效性，返回带 UTC 时区的 datetime；不合格报 `E_TIME_FORMAT`。以下都拒绝：`2026-02-30`、24 时、60 秒、0000 年、`+00:00` 后缀、尾随换行。
- 表示精度不等于时钟真实精度。时间来源与单调时钟计时归 04/07。

## 11. 事件（4.3.1–4.3.5，01-D07 移交 04）

**注册表**

- **`EventType(name, allowed_sources, payload_validator, category)`**：不可变。
  - allowed_sources 必须是 {core, vendor} 的非空子集。
  - `payload_validator(payload)` 在载荷不合法时抛 ProtocolError。
- **`EventTypeRegistry`**：不可变，用 `extended()` 追加。
- **`build_default_event_types()`**：只登记 01 的示例类型 `run.prepared`（core，载荷为对象，值为 JSON 原生值）。真实 Pi 类型由 04 登记。
  - `run.prepared` 的载荷校验器被单独调用时也自己拒绝非对象载荷（`E_SCHEMA_TYPE`，`/payload`），并按 1 MiB 字节下界止损（P4，共享容器不会指数级遍历）。

**原始证据区间**：`validate_raw_span(span, *, registry, segment_sizes=None)`

- 单独调用时先对整个区间对象做 JSON 原生值检查（P4），与它嵌在事件中经 `validate_run_event` 校验时的顺序一致：例如 `byte_end=2**60` 在两处都报 `E_INTEGER_RANGE`（field 分别为 `/byte_end` 与 `/raw_refs/<i>/byte_end`）。
- 字段封闭：`{ref, byte_start, byte_end, stream}`；stream 取 stdout、stderr 或 file。
- ref 按 `validate_resource_ref` 检查，并且**必须是 raw-segment**（裁决 R-P7，P4 落实）：已登记但不是 raw-segment 的 kind 报 `E_RESOURCE_KIND`（`/ref/kind`，reason 为 `raw_ref_requires_raw_segment`）；未登记的 kind 仍按登记规则报 `E_RESOURCE_KIND`（reason 为 `resource_kind_not_registered`）。原始证据分段的语义归 04。
- `byte_start`、`byte_end` 必须是精确整数，且 `0 <= start < end <= 2^53-1`；类型错误也报 `E_EVENT_RAW_RANGE`。
- `segment_sizes` 的键是**已封存分段版本**的 sha256，值是该版本的字节数。给出时：
  - 引用不在其中报 `E_EVENT_RAW_REF_UNKNOWN`；
  - `byte_end` 超过该版本大小报 `E_EVENT_RAW_RANGE`；
  - 实际用到的那个值必须是精确 int（`True`、`10.5`、字符串都不行），否则抛 `TypeError`；不在 0..2^53-1 内抛 `ValueError`。segment_sizes 来自受信封存索引，值不合法是调用方错误。只检查实际用到的条目，开销为 O(1)。
- 偏移按被引用版本的字节计。脱敏改变长度后，旧偏移不能用到新版本上（01-F042）。
- stream 为 file 时同样只能引用 raw-segment：需要引用其他文件型资源的原始证据，由 04 先把它封存为 raw-segment（R-P7）。`test_A12_raw_refs_only_reference_raw_segments` 对 stdout、stderr、file 三种 stream 都断言（P4 第 3 轮补测）。

**`validate_run_event(event, *, registry, context=None, event_types=None, segment_sizes=None)`**

- 附录 A event 结构检查：
  - 整条记录先做 JSON 原生值检查（与 payload 共用 64 层上限，见第 6.2 节）；
  - 字段封闭；
  - seq 是 ≥1 的精确整数；
  - observed_at 符合严格格式；
  - role 只有核心事件可以为 null（4.3.1“无角色核心事件可为空”）：vendor 事件 role 为 null 报 `E_SCHEMA_FIELDS`（`/role`，reason 为 `vendor_event_requires_role`），不论是否给出 context（P4 第 3 轮，复审 fidelity 与 events-usage 视角：context 只在 role 非空时核对，vendor 事件把 role 置空就能脱离角色绑定）。JSON Schema 允许 null，这是 Schema 之外的领域检查；
  - type 长 1–96；
  - source_kind 取 core 或 vendor；
  - payload 是由 JSON 原生值构成的对象；
  - raw_refs 最多 256 条；
  - integrity 取 complete、incomplete 或 pending；
  - adapter_revision 为 null 或 1–128 字符。
- 可选的语义检查：
  - **context 给出时**：request_id、run_id 必须与受信 RunContext 一致；事件 role 非空时必须等于 context.role（vendor 事件的 role 一定非空，所以一定核对）。否则报 `E_CONTEXT_BINDING`，厂商数据不能改写绑定。context 本身不合法时，错误的 field 以 `/context` 开头，phase 为 `context`（第 6.2 节）。
  - **event_types 给出时**：类型必须已登记（`E_EVENT_TYPE_UNKNOWN`）；来源必须被允许（`E_EVENT_SOURCE`，例如核心事件不能冒用厂商类型，厂商事件也不能冒用核心类型）；载荷经该类型的校验器检查。
  - **vendor 事件**：必须有 adapter_revision；声称 `integrity=complete` 时 raw_refs 必须非空。否则报 `E_EVENT_EVIDENCE_MISSING`。

**`assess_stream_integrity(observed_kinds, classification, required_kinds)`**：给 04 的完整性接口。

- classification 的值取 known_required、known_optional 或 ignorable_optional，其他值报 `E_SCHEMA_FIELDS`。
- classification 中没有的内容视为 unknown，不能被忽略。
- 必须出现的类型 = `required_kinds` ∪ classification 中标为 known_required 的类型；缺少其中任一类型即不完整（见 C-06）。可能不出现的关键内容应登记为 known_optional，它仍是已知内容，不会被当作 unknown。
- `required_kinds` 中的每个类型都必须出现在 classification 中（任一分类均可），否则报 `E_SCHEMA_FIELDS`（`/required_kinds/<i>`，reason 为 `required_kind_not_classified`；P4 第 3 轮，复审 events-usage 视角）。未登记的必需类型出现时会被判为 unknown、缺失时判为 missing，流永远不会 complete；这是调用方（04）的配置错误，明确报出，不静默表现为“流永远不完整”（`test_A11_required_kinds_must_be_classified`）。
- **known_optional 与 ignorable_optional 在本接口中判定结果完全相同**（P4 写明，`test_A11_optional_classifications_equivalent`）：接口只接收类型名，不接收“这条内容是否被理解/解析”，无法表达 4.3.4 中两者的区别（已知但没有被理解的可选内容是否影响完整性）。这一区别由 04 在自己的解析层定义（01-D07），两个取值在 01 中只是登记用的标签。
- 返回 `{"integrity", "unknown": 排序去重后的列表, "missing_required": 排序去重后的列表}`。

**序号相关函数**（4.3.2）：

- **`assess_event_log(records, *, run_id=None)`**：纯函数，不抛异常。输入是按持久化顺序读出的已封存事件，按固定快照字节比较，不按 Python 字典相等：payload `{"x":1}` 与 `{"x":true}`、`1` 与 `1.0` 在 Python 中相等，快照字节不同，是冲突而不是重复投递（恢复与追加同样报 `E_EVENT_REPLAY_CONFLICT`；`test_F038_dict_equal_but_bytes_different_is_conflict`，P4 第 3 轮补测）。返回：
  - `events`：去重后按 seq 排序；冲突的 seq 被隔离，不在其中。
  - `event_count`：`events` 中的事件数（裁决 R-P8，P4 新增）。
  - `duplicates`、`conflicts`、`binding_errors`：按 seq 列出。
  - 绑定按以下顺序核对，不一致的记录列入 `binding_errors`，不参与其他判断（不进入 events，也不参与重复与冲突的判定）：
    1. **run_id**。参照 run_id：参数 `run_id` 不为 None 时就用它；它不是合法 run id（不是 str，例如 123；或是 str 但不符合 `run-` 加 32 位小写十六进制，例如 `"garbage"`）时，每条可读记录都记为 binding_errors，不静默回退，也不因记录恰好带同一个非法字符串而判为一致（P4 第 3 轮更正：此前只有非 str 的参照值才生效，`"garbage"` 参照值配同样的记录会得到 complete=true）。参数为 None 时取第一条可读记录的 run_id（不校验其语法，逐条结构校验请用 `validate_run_event`）。**建议总是给出**，否则误读另一个 run 的整份日志时无法发现。
    2. **request_id**（收尾轮，acceptance.md M-01）：同一 run 内必须一致。参照值取第一条通过第 1 步的记录的 request_id。
    3. **非空 role**（收尾轮，M-01）：同一 run 内必须一致。参照值取第一条通过前两步、role 非空的记录的 role；role 为 null 的无角色核心事件（4.3.1）不参与比较，也不成为参照。
    - 第 2、3 步只核对日志**内部**是否一致（参照值来自日志本身），不核对受信 RunContext。与受信上下文的 request/role 绑定，仍用 `validate_run_event(context=...)` 逐条核对。参照值取自第一条记录，所以被改写的恰好是第一条时，其余记录都会被列入 binding_errors；无论哪种情形，日志都不完整。
    - M-01 之前只核对 run_id：同一 run 中改写 request_id 或 role 的记录仍判 complete=true，并且可以追加与恢复。
  - `gaps`：`[(expected, got)]`，按排序后的 seq 计算。
  - `out_of_order`：按持久化顺序，新 seq 出现在更大的 seq 之后的那些 seq。例如 `[1, 3, 2]` 排序后连续，但 3 在 2 之前写入，说明单写入方曾经跳号，得 `out_of_order=[2]`。重复投递不算乱序。（P2 返工新增，R-08）
  - `record_type_errors`：seq 与 run_id 可读、但 record_type 不是精确的 `"run-event"` 的记录下标（例如带 seq 的 usage-observation、缺 record_type、str 子类；P4 新增，第 2 轮复审 events-usage 视角）。这些记录不进入 events，判断与 `append_event` 的 `E_SCHEMA_RECORD_TYPE` 一致。
  - `invalid`：无法读取 seq 或 run_id，绑定字段不可读（request_id 不是 str；role 字段缺失，或既不是 str 也不是 null；收尾轮 M-01，在记录类型检查之后判断，所以不是 run-event 的记录仍列入 record_type_errors），或无法形成快照的记录下标。
  - `last_contiguous_seq`。
  - `complete`：没有冲突、缺口、乱序、绑定错误、记录类型错误和不可读记录时为 true。

  **`complete` 只表示“序号、绑定与记录类型一致”，不表示协议完整**。这里的“绑定”指同一 run 内 run_id 一致（与参数 `run_id` 或第一条记录一致）、request_id 一致、非空 role 一致（收尾轮 M-01 起），不指与受信 RunContext 一致。裁决 R-P8 保留这一含义，不改名，空日志不改为 false：空日志与尾部截断的日志都可以是 `complete=true`，空日志不证明运行产生过事件（据 `event_count=0` 可以看出；同模块的 `usage_view` 把空输入视为不完整，两者含义不同）。协议完整性由 `assess_stream_integrity` 与 04 的结束证据判定（`build_run_dimensions` 的 `protocol_complete`）。本函数只判定序号、绑定、记录类型和重复，逐条的结构校验请先用 `validate_run_event`。
- **`append_event(state, record) -> "appended" | "duplicate"`**：`state = {"run_id", "last_committed_seq", "committed": {seq: bytes}}`。成功追加时**就地更新调用方传入的 state**。
  - record_type 必须精确为 `run-event`，否则 `E_SCHEMA_RECORD_TYPE`。
  - 首条必须是 seq=1；之后必须是 last+1。
  - 已存在的 seq 且字节相同：返回 "duplicate"，不修改 state，不再次计费。
  - 已存在的 seq 但内容不同：`E_EVENT_REPLAY_CONFLICT`。
  - 跳号：`E_EVENT_GAP`。
  - run_id 不同：`E_CONTEXT_BINDING`。
  - request_id 与 role（收尾轮，acceptance.md M-01）：
    - request_id 必须是 str，否则 `E_SCHEMA_TYPE`（`/request_id`，reason `string_required`）；role 字段必须存在且为 str 或 null，否则 `E_SCHEMA_TYPE`（`/role`，reason `string_or_null_required`）。
    - 已有提交时，request_id 必须等于已提交记录的 request_id，否则 `E_CONTEXT_BINDING`（`/request_id`，reason `request_binding_mismatch`）；非空 role 必须等于已提交记录中第一个非空 role，否则 `E_CONTEXT_BINDING`（`/role`，reason `role_binding_mismatch`）。role 为 null 的核心事件不参与比较；已提交记录的 role 都为 null 时，第一条非空 role 成为参照。
    - 参照值从 `committed` 中的快照字节读出，**state 的形状不变**（仍是三个键）；`recover_append_state` 重建的 state 同样适用。committed 中的字节无法读出绑定字段（不是 run-event 快照）时，state 不满足不变式，抛 `ValueError`。
    - 检查顺序：record_type → run_id → 绑定字段可读 → request_id → role → seq（重复、冲突、跳号）。绑定先于序号，所以同一 seq 改写 request_id 或 role 的重放报 `E_CONTEXT_BINDING`，与 run_id 的处理对称。
  - state 的不变式：`committed` 的键恰好是 1..last_committed_seq 的**精确** int（不接受 bool、字符串），值为对应记录的固定快照字节（bytes）。每次调用都完整核对键集合与值类型（P4，第 2 轮复审 events-usage 视角；开销 O(已提交条数)，本函数是内存参考模型）。不满足时抛 `ValueError`（不是 ProtocolError），例如崩溃后只恢复了 last_committed_seq、state 从 JSON 读回（键变成字符串，包括随后追加下一个 seq 的情形）、键稀疏（`{1, 3}` 且 last=2）。这样重放不会被误报成 `E_EVENT_GAP`，也不会掩盖真正的 `E_EVENT_REPLAY_CONFLICT`，不会得到混合键的 state，也不会把从未按序提交的 seq 判为 duplicate。
  - 任何错误都不修改 state。本函数只维护内存结构；持久提交与序号分配的事务协调归 07/04。
- **`recover_next_seq(records, *, run_id=None)`**：从持久记录恢复下一个 seq，空日志返回 1。按以下顺序报错（P4 调整：先报记录本身的缺陷，再报序号问题；他 run 记录、非事件记录或不可读记录位于日志中间时同时造成缺口，按原因报码，错误码才不随故障记录的位置变化，7.4）：绑定不一致 `E_CONTEXT_BINDING`、有非 run-event 记录 `E_SCHEMA_RECORD_TYPE`、有不可读记录 `E_SCHEMA_TYPE`（含绑定字段不可读，收尾轮 M-01）、冲突 `E_EVENT_REPLAY_CONFLICT`、缺口 `E_EVENT_GAP`（reason 为 `log_contains_gap`）、乱序 `E_EVENT_GAP`（reason 为 `log_out_of_order`）。给出 `run_id` 时日志必须属于该 run；`run_id` 不是合法 run id 时报 `E_ID_SYNTAX`。
  - 绑定不一致的 reason（收尾轮 M-01）：run_id 不一致为 `log_contains_foreign_run`；同一 run 内 request_id 不一致为 `log_request_binding_mismatch`；非空 role 不一致为 `log_role_binding_mismatch`。同一日志含多类时按 run → request → role 的固定顺序取 reason，与记录位置无关（`test_A11_m01_binding_reason_order_is_fixed`）。
  - 这一全序是明确承诺，对同时含多类缺陷的日志同样成立：按缺陷类别判定，与故障记录的先后无关，是第 3.2 节“多缺陷输入不承诺首错”的例外（P4 第 3 轮，复审 tests-mutation M27/M30：此前只有单一故障的测试，顺序没有被固定；`test_A11_recovery_multi_fault_order_is_fixed` 对相邻两类缺陷的每一对、两种先后都断言码与 reason）。
- **`recover_append_state(records, *, run_id) -> state`**（P2 返工新增）：崩溃后从持久记录重建 `append_event` 所需的完整 state。先按 `recover_next_seq` 的规则核验日志，再返回 `{"run_id", "last_committed_seq", "committed": {seq: 固定快照字节}}`。重建后，重放已提交的相同事件得到 "duplicate"，内容不同得到 `E_EVENT_REPLAY_CONFLICT`。`run_id` 必填。

**文档 4.3.2 处理规则表中不在 01 落点的两行**（收尾轮，acceptance.md M-11）：01 的序号函数只处理单个 run 内的已提交事件，下面两行没有对应的 01 接口，归属如下。

| 4.3.2 的行 | 规则原文要点 | 归属 | 01 现状 |
|---|---|---|---|
| 同一原始证据换新解析器重建视图 | 新建派生视图修订，保留来源；不覆盖旧已承诺事件；派生视图应有独立的 `view_id` 或版本记录，不属于新增模型 run | **04**（与 adapter_revision 的锁定一并设计） | 没有 view_id 或派生视图修订的记录类型；run-event 的 `adapter_revision` 只记录解释它的适配器修订。`append_event` 拒绝同一 seq 的不同内容（`E_EVENT_REPLAY_CONFLICT`），所以重建视图不能写回原 run 的事件日志 |
| 跨 run 的先后关系 | 由项目游标和显式依赖表达，不按时间戳强造全序 | **10**（项目游标） | seq 只在单个 run 内有意义；`assess_event_log` 与恢复函数只看一个 run，observed_at 不用于跨 run 排序 |

## 12. 分维度状态视图（01-A05，4.1.4、4.3.4）

`build_run_dimensions(*, process_exited, exit_code, cancelled_by, end_evidence, protocol_integrity, usage_complete, wait_returncode, legacy_attempt_state, legacy_verdict, approval_ref, integration_observation, cancellation_checked)` 的参数都有默认值 None（`cancellation_checked` 为 P4 新增）。exit_code 与 wait_returncode 必须是精确 int（bool、`1.0` 报 `E_SCHEMA_TYPE`），cancelled_by 与 end_evidence 必须是 str，usage_complete 与 cancellation_checked 必须是 bool。返回值包含以下键：

- `process_observation{exited, exit_code, cancelled_by}`。
- `protocol_observation{end_evidence, integrity}`：原样保留结束证据与完整性。结束证据与退出码冲突时，两方都留在视图中（01-F041“保留双方证据”，见 C-05）。
- `wait_observation{returncode, note: "wait 返回值只说明查询动作"}`。
- `protocol_complete`，取值规则：
  - integrity 为 incomplete 或 pending：false。
  - 进程已退出但缺少结束证据：false（含“退出 0 但缺结束证据”）。
  - integrity 为 complete 且有结束证据：true。
  - 其他：null。
- `protocol_conflict`：01 只认识结束证据 `"success"`（P2 返工收紧，R-09）：
  - `end_evidence=="success"` 且 exit_code 非 0（包括 POSIX 被信号终止时的负数）：true；
  - `end_evidence=="success"` 且 exit_code 为 0：false；
  - exit_code 未知，或结束证据是其他任何值（例如 `"failure"`、`"error"`，其含义由 04 定义）：null。不会对“结束证据声称失败、进程却退出 0”这类组合断言“没有冲突”。是否把 end_evidence 定为封闭枚举并识别失败类冲突，由 04 与规划端决定。
- `process_exited=False` 却给出 exit_code 是自相矛盾的输入，报 `E_SCHEMA_FIELDS`（`/exit_code`）。
- `cancelled`：三态（P4，第 2 轮复审 events-usage 视角；4.1.4“某维度未知时该维度保持未知”）。
  - `cancelled_by` 不是 None：True（空串同样算给出了取消来源，按“是否为 None”判断）；
  - `cancelled_by` 是 None 且 `cancellation_checked=True`（调用方已核对取消来源，确认没有取消）：False；
  - 其余：None（未知）。P4 之前没有任何取消信息时输出 False，等于断言“未取消”。
- `usage_complete`。
- `legacy_attempt_state`：原样返回。
- `legacy_verdict`：原样返回；值必须在 `LEGACY_VERDICTS` 中或为 None，否则 `E_SCHEMA_FIELDS`。
- `approval_present` 与 `approval_note`：存在审核引用，不证明当前字节仍与审核输入匹配，也不证明审核仍有效。`approval_present` 按“approval_ref 是否为 None”判断，`{}`、`""` 这类假值也算存在。
- `contract_approval_ref`：原样保留（深拷贝）传入的审核引用，以便追溯是哪份审核记录（4.1.4 建议的视图字段；P2 返工新增，R-10）。未给出时为 null。
- `integration_observation`：原样返回。
- `rule_revision`：`codekit01-run-dimensions-v2`（P4 因 cancelled 改为三态由 v1 升为 v2）。

**没有** success、ok、passed、overall 之类的聚合键。01 不定义新的状态转换。

## 13. 用量观测与观测视图（4.3.7–4.3.9，01-D08）

### 13.1 单条观测校验

**`validate_usage_observation(obs, *, context=None, registry=None)`** 检查附录 A usage 结构（字段封闭），规则如下：

| 项目 | 规则 | 错误码 |
|---|---|---|
| 计量 | 精确整数 0..2^53-1 或 None | 类型错 `E_SCHEMA_TYPE`，越界 `E_INTEGER_RANGE` |
| money | 形如 `{amount, currency}`，且只有这两个字段。amount 整串匹配 `^(0|[1-9][0-9]*)(\.[0-9]+)?$`（不带符号、千分位、指数、空格或全角数字，最长 64）；currency 匹配 `^[A-Z]{3}$` | `E_USAGE_VALUE` |
| billing_source | 封闭枚举 | `E_SCHEMA_FIELDS` |
| reported_cost 与 billing_source | reported_cost 非 null 时，billing_source 必须是 vendor_reported 或 provider_invoice；adapter_estimated、unavailable 的费用只能写在 estimated_cost（估算不能冒充实际费用，4.3.7；P2 返工新增） | `E_USAGE_VALUE`（`/reported_cost`） |
| supersedes_usage_id | 不能等于自身的 usage_id | `E_USAGE_CONFLICT` |
| unknown_reasons | 见下方 | `E_USAGE_UNKNOWN_REASON` |
| context 绑定 | context 给出时，request_id、run_id、role 必须一致；context 本身不合法时 field 以 `/context` 开头 | `E_CONTEXT_BINDING` |

unknown_reasons 的规则：

- 键必须属于 `UNKNOWABLE_USAGE_FIELDS`，不支持子路径。
- 值必须是 1–512 字符的字符串。
- 只能写在对应字段为 null 时；observation_kind 以 "unknown" 视为 null。
- 每个为 null 的可未知字段都必须有原因。
- supersedes_usage_id、billing_event_id 这类合法的空关联不需要原因。

附录 4.3.9 的全未知样例可以通过校验。

### 13.2 观测视图

**`usage_view(observations)`** 返回观测视图，**不是记账**：结果带 `"view_kind": "usage-observation-view"` 与 `"is_accounting": false`。处理顺序（P2 返工后，见 R-11）：

1. 逐条校验（`validate_usage_observation` 的规则，不含 context 绑定）。
2. 同一 usage_id：快照字节相同时只算一次（duplicates 加 1）；内容不同报 `E_USAGE_CONFLICT`。
3. **重复投递归并**（P2 第二轮返工改写，见 R-15）：
   - 先沿 supersedes 指针求每个观测在修订链上的深度；修订链成环报 `E_USAGE_CONFLICT`（reason 为 `revision_cycle`）。
   - 再按深度从低到高归并“同一观测的多次投递”：`(provider, billing_event_id)` 都非 null 且相同、数值（`_usage_numbers`，含 billing_source）相同、修订目标也相同（目标按已归并的规范观测比较）的观测，归并为到达最早的那一条（规范观测）。
   - 同一账单事件中数值不同或修订目标不同的观测**不**归并：它们是修订链上的不同版本，或是冲突，由第 4、5 步处理。例如“更正回原值”（100 → 120 → 100）的第三版不会与第一版归并，也不会因此成环。
4. supersedes 修订链（在规范观测上解析）：
   - 修订只替代它**明确指向**的目标，连同目标的重复投递。因此“同一账单事件以两个 usage_id 投递、修订只指向其中一条（且修订换了或没有 billing_event_id）”时，两条一起被替代，不会有一条失去去重对象后与修订一起计入（第一轮返工前得 220 且标完整）。
   - **边界**：同一账单事件中与目标数值不同、也不在这条修订链上的观测，**不会**随目标一起被替代。第一轮返工曾让修订替代“整个账单事件等价类”，结果这类观测被静默吞掉、视图仍标完整；线性修订链 a←b←c（各版沿用同一 billing_event_id）又被误报为分叉。这两点都与 01-T2“数值不同 → E_USAGE_CONFLICT”和 4.3.8“按修订链替代”相悖，已改正。
   - 被替代的观测不计入。
   - 指向不存在的 id 时，把**发起修订的观测**的 usage_id 记入 `unresolved_supersedes`（据此可查到它指向的缺失目标）；该观测仍按口径计入，但全部计量、全部费用组与顶层 `is_complete` 都为 false（见 C-11）。
   - 以下情况报 `E_USAGE_CONFLICT`：同一观测（按规范观测计）被两条不同的修订替代（分叉，reason 为 `observation_superseded_twice`）、修订改变了 request/run/role。同一修订的重复投递（账单号相同、数值相同、指向同一目标或目标的重复投递）已在第 3 步归并，不算分叉；没有 billing_event_id、或账单号不同的两条修订指向同一目标，无法认定为重复，仍算分叉。
   - 没有分叉，所以每个修订分量都是一条链，链尾是有效值。
   - 币种按**整条修订链**检查：链上全部观测中，同一费用字段只要出现两种币种就报 `E_USAGE_CURRENCY_MISMATCH`，经由费用为 null 的中间版本也一样（不再只比较相邻两项）。
   - 修订继承被替代观测中最早的到达位置（逻辑顺序）。因此对较早累计值的更正晚到时，不会覆盖更新的累计值：c1=100、c2=150、c3 更正 c1 为 120，当前累计为 150。
5. 同一外部账单事件在修订之后只能有一个有效值：一条修订链代表链上**全部**观测的账单事件（不只是链尾自己的 billing_event_id）。代表同一账单事件的各有效观测（链尾）：
   - 数值相同视为重复，只计一次，保留逻辑位置最早的那条；
   - 数值不同报 `E_USAGE_CONFLICT`（reason 为 `same_billing_event_different_values`），与到达顺序无关，也与修订自身带同一账单号、另一账单号还是不带无关。例如 a(bx,100)、c(bx,999)、b(修订 a,120)：c 与“bx 修订后的有效值 120”不一致，报冲突。
   - 比较的数值包括 billing_source：同一账单事件的厂商报告与账单来源（或估算）不是“重复”。
   - `duplicates` 计入第 2 步的同 id 重放、有效观测的重复投递与本步的重复；被替代观测的重复投递随目标一起列在 `superseded` 中，不计入 `duplicates`。
   - **provider 为 null 时账单号无法去重**（P4，第 2 轮复审 events-usage 视角；P4 第 3 轮修正口径；P4 第 4 轮起同号的 provider 已知观测也参与判定；P4 第 5 轮起按成员判定登记）：账单号的命名空间属于 provider，provider 未知时无法判断同一 billing_event_id 的两条有效观测是同一账单事件的重复投递还是两个事件，所以不相加：P4 之前两条相同的投递会相加成翻倍的 known_total，只标 is_complete=false，而不完整的 known_total 应当是已知部分的下界，不能是高估。规则：
     - 与本步前半部分（provider 已知）同一口径，一条修订链代表链上**全部**成员的账单号，不只看链尾自己的 billing_event_id；
     - **登记规则：按成员判定**（P4 第 5 轮统一，复审 events-usage 视角 major）：带 billing_event_id 的成员，只要它自身的 observation_kind 不是 unknown（它带有已知数值），或者它所在链的有效链尾可计入，这条链（第 5 步去重后的保留者）就代表这个账单号。成员自身与所在链的链尾都是 unknown 时不登记：它不计入，也不代表任何已知数值。所以链尾为 unknown 的链 a(BX,delta) ← r(unknown) 仍代表 a 的账单号 BX；
     - 某个账单号只要有一个登记成员的 provider 为 null，就无法去重。这时同号的全部代表链都参与判定，包括 provider **已知**的（P4 第 4 轮，复审 events-usage 视角 major）：provider 为 null 的账单号与任何 provider（包括已知的）的同号观测都不能相加，同样无法判断它们是不是同一账单事件；
     - 只按 billing_event_id 分组，**不区分 request/run/role**：provider 已知时同一账单号跨 run 或 role 是 `E_USAGE_CONFLICT`（数值键含 request/run/role），信息更少的 null provider 不能更宽松；
     - 无法去重的账单号有两条以上不同的代表链、且其中至少一条可计入（链尾的 observation_kind 不是 unknown）时，报 `E_USAGE_SCOPE_UNKNOWN`（reason 为 `billing_event_without_provider_repeated`）。同一条修订链的多个成员带同一账单号只算一次，所以修订链 a(null,BX) ← b(P,BX) 只计 b；
     - 不触发的情形：provider 为 null 的成员只有 unknown 观测、所在链的链尾也不可计入时，这个成员不登记，不同 provider 的同号观测属于不同的命名空间，照常相加；全部代表链都不可计入时（例如 a←r1、b←r2，r1、r2 都是 unknown）没有值被计入，不触发；
     - 判定时机：在第 6 步开头的范围歧义判定之后执行（P4 第 4 轮调整）。同一 (request, run, role) 下，provider 或 model 为 null 的范围与其他含可计入观测的范围并存时，先报 `scope_provider_or_model_unknown`（两者的错误码都是 `E_USAGE_SCOPE_UNKNOWN`）。所以 provider 已知与为 null 的同号观测在同一 (request, run, role) 时报 `scope_provider_or_model_unknown`，跨 run、role 或 request 时报 `billing_event_without_provider_repeated`。副作用：两条 provider 为 null、model 不同、同号的观测在同一 (request, run, role) 时，reason 由 `billing_event_without_provider_repeated` 变为 `scope_provider_or_model_unknown`，错误码不变；
     - P4 第 3 轮之前的两处缺口（复审 events-usage 视角）：只看链尾自己的账单号，所以 a(BX,100) 被 b(无账单号,120) 修订后 c(BX,100) 再次投递时，provider 已知时 c 随 a 去重得 120，provider 为 null 时却把 b 与 c 相加成 220；分组键含 (request_id, run_id, role)，跨 run 或 role 的同一账单号直接相加。原文“修订链只留链尾，不受影响”不成立，已删除。回归测试：`test_A06_billing_event_without_provider_uses_whole_revision_chain`、`test_A06_billing_event_without_provider_not_summed`（跨 run、跨 role、跨 request 都报错，与 provider 已知时的 `E_USAGE_CONFLICT` 对照）。
     - P4 第 4 轮之前的缺口（复审 events-usage 视角 major）：本步只收 provider 为 null 的成员。a(P,BX) 与 b(null,BX) 跨 run、role 或 request 时直接相加得 200；修订链变体 a(null,BX,100) ← b(P,无账单号,120) 与 c(P,BX,100)（c 是 a 的同号重投）在 6 种到达顺序下都得 220、USD 2.20，并且标为完整，属于重复计费。只把 a 的 provider 改为 P，同样的输入就得 120（c 随 a 去重）：信息更少的 null provider 反而更宽松。回归测试：`test_A06_billing_event_null_and_known_provider_not_summed`（跨 run、role、request 的两种到达顺序；修订链变体与 c=120 变体的全部到达顺序；provider 全部已知时的 120 对照；同一修订链内只计一次；只有 unknown 观测时不触发）。
     - P4 第 5 轮之前的缺口（复审 events-usage 视角 major）：登记只看成员所在链的链尾是否可计入。a(null,BX,delta,100) 被 r(observation_kind=unknown) 修订后，a 的账单号不再登记，同号的 c 被单独计入：c=100 是 a 的重投（被替代的值复活），c=150 是冲突值（冲突被静默接受）；只把 a 或只把 c 的 provider 设为 null、或把 c 放到另一个 run，结果相同。provider 全部已知时，同样的输入随 a 一起被替代（计 0，superseded 为 [a, c]）或报 `E_USAGE_CONFLICT`。原文两处写法对这一输入给出不同结论：一处是“该成员所在链的有效链尾可计入时”（与当时的代码一致），另一处是“provider 为 null 的成员所在链只有 unknown 观测（不计入）时不触发”（本例中 a 所在的链含 delta 成员 a，按这一句应当触发）。现统一为上面的按成员规则。回归测试：`test_A06_billing_event_chain_revised_to_unknown`（a、c 的 provider 取 null/已知的四种组合，c 取 100 与 150，同 run 与跨 run，全部到达顺序；provider 全部已知时的 0 / `E_USAGE_CONFLICT` 对照；没有 c 时计 0；两条代表链都不可计入时不触发；成员自身是 unknown、链尾可计入时照常登记）。
6. 按范围 `(request_id, run_id, role, provider, model)` 解释：
   - **来源不明的范围**：provider 或 model 为 null 的范围来源不明（4.3.8 末行）。同一 `(request_id, run_id, role)` 下还有其他含可计入观测的范围时，报 `E_USAGE_SCOPE_UNKNOWN`（reason 为 `scope_provider_or_model_unknown`），不把两个范围相加成“完整”的数字。单独存在时照常解释，但它计入的计量与费用组都标为不完整，scope 报告中 `ambiguous_scope=true`。只含 unknown 观测的范围不参与这一判断（它本来就不计入，只使结果不完整）。
   - delta 相加。
   - 同范围内既有 delta 又有 cumulative 或 final，报 `E_USAGE_SCOPE_UNKNOWN`，不猜口径。
   - cumulative/final 按逻辑顺序检查自洽：同一费用字段的币种不得变化（`E_USAGE_CURRENCY_MISMATCH`）；各计量与同币种金额不得回退（`E_USAGE_CONFLICT`，reason 为 `cumulative_value_decreased`）。
   - cumulative 取最后一条。
   - final 视为最终累计：同范围内多个 final 数值不同报 `E_USAGE_CONFLICT`；final 之后又出现 cumulative 是终止后的新内容（4.3.4），报 `E_USAGE_CONFLICT`（reason 为 `observation_after_final`）。final 之前较小的 cumulative 合法，但不计入。
   - **计入观测的 null 字段取已证明的下界**（P4 第 3 轮，复审 events-usage 视角）：cumulative/final 计入的那条观测某个计量为 null 时，known_total 取同一序列中此前最后一个已知值（序列已校验单调不减，这个值是合法下界），同时 is_complete=false、unknown_count 加 1；某个费用为 null 时，按序列已校验的唯一币种归组，known_total 取此前最后一个已知金额，标为不完整、unknown_count 加 1，不再落入 unknown_currency。序列中没有任何已知值时，仍是 0 或 unknown_currency 组。P4 第 3 轮之前，此前已证明的累计值整体丢失（known_total 退回 0，费用的原币种组消失），比把同一条观测换成 observation_kind=unknown（信息更少）得到的结果还少，违背“已知部分的下界”。delta 不做这种替代（各条独立相加）。`test_A06_cumulative_null_field_keeps_known_lower_bound` 固定。
   - 没有计入的已知观测列在该范围的 `ignored_usage_ids` 中，不静默丢弃；其中可能有为计入观测的 null 字段提供下界的观测（上一条）。
   - observation_kind 为 unknown 的观测，数值不计入，并使全部计量不完整。
7. 每个计量与每个币种分别给出结果；计量合计超过 2^53-1 报 `E_INTEGER_RANGE`，视图本身不输出越界整数。

返回值：

- 每个计量（`input_tokens` 等 5 个）作为顶层键，值为 `{known_total:int, is_complete:bool, unknown_count:int}`。cache 与 reasoning **从不**加进 input 或 output；`input_includes_cache` 与 `output_includes_reasoning` 只记录在 `distributions` 中。
- `reported_cost` 与 `estimated_cost` 分开，各自按币种给出 `{known_total: 十进制字符串, is_complete, unknown_count}`。
  - 用 `decimal` 精确相加：精度 1000 位，出现任何舍入即报错；输出不用科学计数法。超过默认 28 位有效数字的金额也精确相加（测试覆盖）。
  - 缺失的费用计入 `unknown_currency` 组。该组存在未知时，同类费用的所有币种组都标为不完整（未知费用可能属于任何币种）。
  - 估算费用永不并入 reported。
- 其他键：`duplicates`、`superseded`（被替代的 usage_id，含被替代目标的重复投递，排序）、`unresolved_supersedes`、`counted_usage_ids`、`observation_count`、顶层 `is_complete`，以及 `scopes`。`scopes` 中每个范围给出 `mode`、`ambiguous_scope`、`counted_usage_ids`、`ignored_usage_ids`、`unknown_kind_usage_ids`。
- **输入为空（没有任何有效观测）时**，`is_complete=false`：没有观测不等于零用量。此时各计量为 `{known_total: 0, is_complete: false, unknown_count: 0}`，两类费用各有一个 `unknown_currency` 组 `{known_total: "0", is_complete: false, unknown_count: 0}`（P4，第 2 轮复审 events-usage 视角：原来费用为 `{}`，只读费用分组的下游会把“没有观测”读成“费用为 0 且没有未知”）。
- **只含 unknown 观测时**（有有效观测，但都没有计入）：各计量 known_total 为 0、is_complete 为 false、unknown_count 等于 unknown 观测数；费用按每条观测自身的币种分组（费用为 null 时计入 unknown_currency 组），各组 known_total 为 "0"、都标为不完整；`counted_usage_ids` 为空，scope 的 mode 为 `unknown_only`（`test_A06_only_unknown_observations_shape`、`test_F044_all_unknown_sample_view`）。P4 第 3 轮更正：原文把上一条写成“没有任何可计入的观测时”，而按第 5 步“可计入”指 observation_kind 不是 unknown，只含 unknown 观测的输入得到的是本条的形状。

预算在未知用量下是暂停、预留还是转人工复核，由 07 决定。01 不把未知视作免费。

## 14. fixture 来源清单（4.3.3、5.3、附录 C.1，01-A12）

### 14.1 条目结构

下游 fixture 代理按以下结构写条目，字段封闭：

```text
{"schema_version": 1, "record_type": "fixture-manifest", "fixture_id": logicalId,
 "origin": {"class": legacy|captured|synthetic|negative, "source_revision": 完整 OID|null,
            "source_test_id": str|null, "source_path": 业务路径|null, "generator_revision": str|null,
            "derived_from": fixture_id|null, "fault": str|null, "description": str,
            "traceable": bool},
 "representation": captured_raw|redacted_raw|normalized_event|synthetic_fixture,
 "redaction": {"applied": bool, "rule_revision": str|null, "length_changed": bool|null, "reason": str,
               "protocol_structure_preserved": bool|null},
 "resource": ResourceRef（kind 必须是 fixture，必须有 path）,
 "proves": [str], "does_not_prove": [str],
 "expected": {"outcome": accept|reject|legacy-judgment, "code": str|null, "entry": str, "expected_ref": ResourceRef|null},
 "integrity": complete|partial|truncated|corrupted,
 "platform_scope": ["any"] | PLATFORMS 的非空无重复子集,
 "capture": null | {"environment_ref": ResourceRef, "range": str}}
```

整份文件是 `{"schema_version":1, "record_type":"fixture-manifest-set", "entries":[...]}`，不含自身摘要。

**收尾轮新增的字段**（裁决 R-P11，acceptance.md M-03；字段仍然封闭，缺字段或多字段都是 `E_SCHEMA_FIELDS`）：

| 字段 | 取值 | 依据 | 结构层错误 |
|---|---|---|---|
| `integrity` | `FIXTURE_INTEGRITY_VALUES`：complete、partial、truncated、corrupted | 文档 6.6“封存”一步的“完整性” | 取值之外（含 null、非 str）`E_SCHEMA_FIELDS`（reason `value_not_in_enum`） |
| `platform_scope` | `["any"]`，或 `PLATFORMS`（linux、macos、windows）的非空、无重复子集，顺序不限 | 文档 1.1 兼容 fixtures 最低标准中的“平台适用性” | 不是数组 `E_SCHEMA_TYPE`（`array_required`）；空数组 `E_SCHEMA_FIELDS`（`platform_scope_empty`）；`any` 与其他值并列（`platform_scope_any_must_be_alone`）；重复（`duplicate_platform`）；其他值（含大小写不同的 `Windows`、`ANY`）`value_not_in_enum`。后三种的 field 指向数组元素，例如 `/platform_scope/1` |
| `capture` | null，或封闭对象 `{"environment_ref": ResourceRef, "range": str}`：environment_ref 是采集环境记录的引用（按 `validate_resource_ref` 检查，kind 须已登记，文件型须带 path），range 是截取范围的说明（1–512 个字符） | 附录 C.1“采集环境”“截取范围” | 不是对象 `E_SCHEMA_TYPE`；缺字段或多字段 `E_SCHEMA_FIELDS`；引用的错误码同 `validate_resource_ref`（field 以 `/capture/environment_ref` 开头）；range 不是 str `E_SCHEMA_TYPE`，长度越界 `E_SCHEMA_FIELDS` |
| `redaction.protocol_structure_preserved` | true、false 或 null | 文档 4.3.3 脱敏元数据的“是否保留协议结构” | 其他值 `E_SCHEMA_TYPE`（`boolean_required`） |
| `origin.traceable` | true 或 false（不接受 null） | 文档 4.3.3 脱敏元数据的“来源是否可追溯” | 其他值（含 null）`E_SCHEMA_TYPE` |

- 三个顶层新字段排在 `expected` 之后：缺字段按字段表的顺序报告，所以附录 C.1 示例（缺 expected）仍先报 `/expected`。
- `capture` 与来源类别的关系、`integrity` 与 `protocol_structure_preserved` 对能力声明的限制属于来源一致性规则，见第 14.2 节第 3b、5 步。
- 平台适用性是登记者的声明，不是实测结论：`["any"]` 只表示该 fixture 的判断不依赖平台，不表示已在各平台运行过（Linux、macOS 的执行状态仍按基线报告记 NOT_RUN）。

**能力声明的词法**（P4 第 3 轮，复审 tests-mutation 视角 major）：`proves` 与 `does_not_prove` 中的每个声明都必须整串匹配 `[a-z][a-z0-9_]{0,127}`（小写 ASCII 字母开头，只含小写字母、数字与下划线，最长 128），否则报 `E_SCHEMA_FIELDS`（`/proves/<i>` 或 `/does_not_prove/<i>`，reason 为 `claim_syntax`；超过 128 个字符时 reason 为 `string_length_out_of_range`）。第 14.2 节的来源规则按精确名称与 `real_`/`vendor_`/`legacy_` 前缀判定，P4 时 `_claim_list` 接受任意 1–256 字符的字符串，大小写或连字符变体（`REAL_CLI_COMPATIBILITY`、`Vendor_Protocol`、`vendor-protocol`、`Legacy_dispatch_behavior`）能绕过这些规则；封闭词法让变体在结构层就被拒绝。本清单现有的全部声明都符合该词法。

**与附录 C.1 示例的关系**（P2 返工补充，收尾轮更新）：附录 C.1 只是建议稿，按上述封闭结构**会被拒绝**（`E_SCHEMA_FIELDS`，field 为 `/expected`）。照抄 C.1 需要补齐以下字段：

- `expected`（整个对象）；
- `origin.source_path`、`origin.derived_from`、`origin.fault`；
- `redaction.rule_revision`、`redaction.length_changed`；
- 收尾轮（R-P11）起还有：`integrity`、`platform_scope`、`capture`、`origin.traceable`、`redaction.protocol_structure_preserved`。

按新结构补齐后的完整示例（测试 `test_A12_appendix_c1_example_needs_completion` 从设计文档取出 C.1、补齐同样的字段后断言通过，并逐项去掉一个新字段断言 `E_SCHEMA_FIELDS`）：

```json
{
  "schema_version": 1,
  "record_type": "fixture-manifest",
  "fixture_id": "synthetic-protocol-sample-1",
  "origin": {
    "class": "synthetic",
    "source_revision": null,
    "source_test_id": null,
    "source_path": null,
    "generator_revision": "review-expanded-2026-09-25",
    "derived_from": null,
    "fault": null,
    "description": "用于完整字节哈希和来源标签的合成示例，不是厂商输出。",
    "traceable": true
  },
  "representation": "synthetic_fixture",
  "redaction": {
    "applied": false,
    "rule_revision": null,
    "length_changed": null,
    "reason": "构造时不包含真实凭据或真实用户数据。",
    "protocol_structure_preserved": null
  },
  "resource": {
    "kind": "fixture",
    "id": "synthetic-protocol-sample-1",
    "sha256": "0036dde35a13e287320b6399674c46649365553a0ab6d3edf2a2111d6f83c4e1",
    "path": "tests/fixtures/synthetic-protocol-sample-1.json"
  },
  "proves": ["exact_byte_digest", "synthetic_provenance_label"],
  "does_not_prove": ["real_cli_compatibility", "legacy_dispatch_behavior"],
  "expected": {"outcome": "accept", "code": null, "entry": "strict_json_loads", "expected_ref": null},
  "integrity": "complete",
  "platform_scope": ["any"],
  "capture": null
}
```

captured 条目的 `capture` 示例（引用的 kind 须已登记；这里用 01 的 baseline-evidence，04 采集时可登记自己的环境记录类型）：

```json
"capture": {
  "environment_ref": {"kind": "baseline-evidence", "id": "capture-env-1",
                      "sha256": "<采集环境记录的完整摘要>", "path": "evidence/capture-env-1.json"},
  "range": "stdout 全部字节"
}
```

### 14.2 单条校验

**`validate_fixture_manifest_entry(entry, registry)`**：先做结构检查（整条条目先做 JSON 原生值检查，1 MiB 字节下界预算），再做以下来源一致性检查，不满足时报 `E_PROVENANCE_CLAIM`。检查顺序与 reason：

1. proves 与 does_not_prove 不得有交集（`claim_both_proved_and_not_proved`，`/proves`）。
2. 脱敏元数据（4.3.3“至少记录……脱敏规则修订、是否改变字节长度”）：
   - redaction.applied=true（任何表示）时 rule_revision 必须非空（`redaction_requires_rule_revision`）；
   - redaction.applied=true 时 length_changed 必须非空（`redaction_requires_length_changed`，P4）；
   - redacted_raw 必须 applied=true（`redacted_raw_requires_applied_redaction`）；
   - captured_raw 必须 applied=false：脱敏过的字节不能称为“原始”（`captured_raw_must_not_be_redacted`，P4）。
3. 来源类别：
   - **synthetic**：只能配 `synthetic_fixture`（`synthetic_requires_synthetic_fixture`）；proves 不得含 `REAL_COMPATIBILITY_CLAIMS`，也不得含以 `real_`、`vendor_`、`legacy_` 开头的声明（`synthetic_cannot_prove_real_compatibility`）。
   - **captured**：只能配 `captured_raw`、`redacted_raw` 或 `normalized_event`（`captured_requires_captured_redacted_or_normalized`；P4 允许 normalized_event，4.3.3“标准化事件保留其来源”）；source_revision 与 source_test_id 至少一个非空（`captured_requires_source`，field 为 `/origin/source_revision`；只有 source_path 不算来源，它只说明位置）；配 normalized_event 时 generator_revision（解释它的适配器修订）必须非空（`normalized_event_requires_generator_revision`，P4）。
   - **legacy**：必须有完整 OID 形式的 source_revision（`legacy_requires_source_revision`），还必须有 source_path 或 source_test_id（`legacy_requires_source_path_or_test`）。
   - **negative**：必须有 derived_from 与 fault（`negative_requires_derived_from_and_fault`）；derived_from 不能等于自身的 fixture_id（`negative_cannot_derive_from_itself`）；不能配 captured_raw/redacted_raw，注入故障后的字节不再是采集字节（`negative_cannot_use_captured_representation`，P4）。

   3b. 可追溯与采集记录（收尾轮，裁决 R-P11），在上面各来源类别自身的规则之后检查：
   - legacy 与 captured 的 `origin.traceable` 必须为 true（`traceable_required_for_legacy_or_captured`，field 为 `/origin/traceable`）；synthetic 与 negative 可以为 false；
   - captured 必须有 `capture`（`captured_requires_capture`，field 为 `/capture`），三种采集表示（captured_raw、redacted_raw、normalized_event）都一样；
   - 其他来源类别的 `capture` 必须为 null（`capture_only_for_captured`，field 为 `/capture`）。
4. 能力声明（P4 起作用于**全部**条目，不再只看 origin.class=synthetic；fixtures 复审 major 的协议层根因），field 都是 `/proves`：
   - `real_cli_compatibility`、`vendor_protocol` 与 `real_`/`vendor_` 前缀的声明，只允许 origin.class=captured 且 representation 为 captured_raw 或 redacted_raw（`real_compatibility_claim_requires_captured_raw`）。所以 legacy 类的 stub 流、negative 类、captured 的 normalized_event 都不能声称真实 CLI 或厂商兼容。
   - `legacy_dispatch_behavior` 只允许 origin.class=legacy 且 expected.outcome=legacy-judgment（`legacy_dispatch_claim_requires_legacy_judgment`）。
   - 其他 `legacy_` 前缀的声明只允许 legacy 或 negative（`legacy_claim_requires_legacy_or_negative_origin`）；negative 的来源另由清单级规则核对（第 14.3 节）。
   - synthetic 类在第 3 步已按原规则拒绝，reason 保持 `synthetic_cannot_prove_real_compatibility`（P4 第 3 轮起测试逐一断言这个 reason，不接受声明循环给出的 `real_compatibility_claim_requires_captured_raw`）。
   - `origin.class=captured` 这一条件本身被测试固定：legacy 类的表示不受限制（C-12），legacy + captured_raw/redacted_raw 声称真实或厂商兼容同样拒绝（P4 第 3 轮补测，`test_A12_real_compatibility_claims_by_origin_and_representation`）。
5. 完整性与协议结构对能力声明的限制（收尾轮，裁决 R-P11；作用于全部条目，field 都是 `/proves`）。R-P11 原文只写“不得声称完整运行流”“不得声称证明协议字段语义”，没有规定声明名称；两类声明的判定由实施者按下面的**受控词表**给出（收尾轮返工起，此前只看两个前缀，同义名称能绕过）。声明先按 `_` 切成词元，词干都按**词元开头**匹配，不做子串匹配：
   - **完整运行流一类**（`_is_complete_stream_claim`）：满足任一条即是——以 `COMPLETE_STREAM_CLAIM_PREFIXES`（complete_run_stream、full_run）开头；某个词元以 `COMPLETENESS_CLAIM_STEMS` 之一开头（complet、full、entire、whole、intact、untruncat、unabridg、endtoend、e2e，覆盖 complete、completed、completeness、completion、full、fully、fullrun、entirely 等）；含连续词元 end、to、end；含词元 all 或 every，且另有词元以 `STREAM_SUBJECT_STEMS` 之一开头（run、stream、event、log、record、line、message、transcript、session、output、trace、segment）。例：complete_run、run_stream_complete、fullrun、complete_event_stream、full_event_log、entire_run_stream、end_to_end_run、all_events_present 都在词表内；partial_run_stream、incomplete_stream_detected、truncation_detected、successfully_parsed（full 不在词元开头）、all_fields_typed（all 没有运行流对象）不在。
   - **协议字段语义一类**（`_is_field_semantics_claim`）：以 `PROTOCOL_FIELD_SEMANTICS_CLAIM` 开头；或某个词元以 `FIELD_SEMANTICS_CLAIM_STEMS` 之一开头（semantic、meaning）；或同时含以 `PROTOCOL_SUBJECT_STEMS`（protocol、wire）开头的词元与以 `FIELD_SUBJECT_STEMS`（field）开头的词元。例：field_semantics、protocol_fields、wire_field_types、session_header_semantics 在词表内；field_order、protocol_version_string、nonsemantic_bytes_equal 不在。
   - `integrity` 不是 complete 时，proves 不得含完整运行流一类的声明（reason `incomplete_fixture_cannot_prove_complete_stream`）。判定比“完整运行流”宽（例如 `full_runtime`、`complete_usage_totals` 也被拒绝），是保守方向；写在 does_not_prove 中不受限制。
   - `redaction.protocol_structure_preserved=false` 时，proves 不得含协议字段语义一类的声明（reason `structure_not_preserved_cannot_prove_field_semantics`）。
   - 收尾轮的保守补充：`redaction.applied=true` 而 `protocol_structure_preserved` 为 null（脱敏过，却没有记录是否保留协议结构）时，同样不得声称（reason `structure_preservation_unrecorded_cannot_prove_field_semantics`）。依据是文档 4.3.3“无法保证语义字段未被脱敏破坏时，该 fixture 不能证明该字段的真实协议兼容性”。null 本身仍然合法，R-P11 允许它；没有脱敏（applied=false）且为 null 时可以声称。

检查顺序：结构检查（含能力声明的封闭词法与收尾轮新增字段的结构）→ 第 1 步 → 第 2 步 → 第 3 步 → 第 3b 步 → 第 4 步 → 第 5 步。所以同一条目同时违反两步时报前一步的 reason，例如 synthetic 条目标为 redacted_raw 且 applied=false，报第 2 步的 `redacted_raw_requires_applied_redaction`（`/redaction/applied`），不是第 3 步的 `synthetic_requires_synthetic_fixture`；legacy 条目缺 source_revision 且 traceable=false，报第 3 步的 `legacy_requires_source_revision`；synthetic 条目 integrity=partial、同时声称 complete_run_stream 与 real_cli_compatibility，报第 3 步的 `synthetic_cannot_prove_real_compatibility`。

以下为结构检查，报 `E_SCHEMA_FIELDS`：

- outcome 为 reject 时必须有 code；
- outcome 为 accept 时 code 必须为 null。

**现行规则的空缺**（P4 写明；收尾轮按裁决 R-P11 补上“是否保留协议结构”“来源是否可追溯”，以及 acceptance.md M-03 列出的完整性、平台适用性、采集环境与截取范围，这些项已从本清单删除）：

- 本清单目前没有 captured 条目；captured 规则（含第 3b 步的 capture 与 traceable）只有单元测试覆盖，没有真实采集样本。captured 样本的 capture 与 traceable 由 04 采集时填写。
- `capture.environment_ref` 只按 ResourceRef 检查结构与登记，不核对被引用记录的内容（采集环境记录的格式由 04 定义）；`capture.range` 是自由文本，不做机器解释。
- `origin.traceable` 与 `platform_scope` 是登记者的声明：前者不核对追溯链是否真的完整（legacy 的追溯依据仍是 source_revision 与 source_path/source_test_id），后者不代表已在所列平台运行过。
- 第 5 步的两条规则**只按受控词表生效**（收尾轮返工写明）：声明的词法是开放的（`[a-z][a-z0-9_]{0,127}`），词表之外的同义写法不受限制，例如把词干接在其他词后面（`runcomplete`、`streamfull`）、换用词表外的近义词（`exhaustive_log`、`field_interpretation`）或其他语言的拼写。词表与规则名称由实施者选定，decisions.md 的 R-P11 没有登记；要让名称有据可查，或改为“凡表示完整运行流或协议字段语义的声明必须使用登记的名称”的命名规则，需要规划端在 decisions.md 中登记（第 19 节“收尾轮返工”）。

### 14.3 整份清单校验

**`validate_fixture_manifest_set(doc, registry)`**：先对整份清单做 JSON 原生值检查（与单条记录相同的 1 MiB 字节下界预算；P4 之前没有预算，调用方直接传入的共享结构会被指数级遍历），再逐条校验，再检查：

- fixture_id 不得重复（`E_SCHEMA_FIELDS`）。
- resource.path 在大小写或 Unicode 归一化后不得碰撞；同一拼写只允许对应同一摘要（`E_PATH_COLLISION`）。碰撞按 `check_no_name_collisions` 检查，也包括目录前缀碰撞与“文件/目录同名”（第 7 节）。
- negative 的 derived_from 必须是本清单中的 fixture_id（`E_PROVENANCE_CLAIM`，`derived_from_unknown_fixture`）。
- negative 的 derived_from 目标不能是另一个 negative（`E_PROVENANCE_CLAIM`，field 为 `/entries/<i>/origin/derived_from`，reason 为 `negative_must_derive_from_valid_sample`；P4 第 3 轮，复审 tests-mutation 视角）：7.4 要求“每个负例从一份通过该层全部前置校验的有效样本复制”。单条目只能看到自引用（`negative_cannot_derive_from_itself`），链式派生（负例 → 负例）与负例之间的二元派生环此前都被接受；规则按目标的来源类别判定，不按目标的 expected.outcome。本清单的负例都从 synthetic 或 legacy 条目派生（`test_provenance_consistency` 另有同样的断言）。
- 声明 `legacy_` 前缀能力的 negative 必须从 origin.class=legacy 的条目派生（`E_PROVENANCE_CLAIM`，field 为 `/entries/<i>/proves`，reason 为 `negative_legacy_claim_requires_legacy_base`；P4）：从合成样本派生的负例不能声称旧实现的判断。上一条先检查，所以 legacy → negative → negative 的链式派生报 `negative_must_derive_from_valid_sample`。
- 收尾轮（R-P11）新增的字段只在单条目层检查，清单级没有新规则；单条目的错误 field 带 `/entries/<i>` 前缀（例如 `/entries/1/platform_scope`）。负例的 integrity、platform_scope 由登记者按负例自身填写，不从派生目标继承。
- 整份清单作为资源载荷核验时，用 `validate_resource_payload`（kind 为 fixture-manifest，第 8 节）：它先核对完整字节摘要，再严格解析并调用本函数。

## 15. 不可变发布（sealing.py，4.2.8、8.3，01-A13）

**范围与前提（裁决 R-P9）**：

- **A13 的范围是“发布与索引补偿”**：独占创建临时文件、读回核验、不覆盖已有文件、索引失败不返回引用、可用相同字节幂等补录（下面第 3–9 步）。路径安全不在 A13 范围内。
- **`store_root` 必须是可信核心独占控制的目录**。sealing 不防御被攻击者控制（或可被其他主体写入）的存储根，也不防御其中预置的硬链接、链接或并发替换。复审复现：存储根中已有一个与根外文件共享数据的硬链接 `h.txt` 时，`seal_bytes(root, "h.txt", <根外文件的字节>, …)` 按幂等成功，返回引用，并调用一次 index_commit；`read_sealed` 返回根外文件的字节。存储根若不由可信核心独占，“不可变版本”的内容可以从根外改写，路径核对发现不了，只有读取时的摘要核验能在内容变化后报 `E_RESOURCE_HASH_MISMATCH`（`test_A13_hard_link_alias_is_known_not_detected`）。
- 存储根内的路径步进（第 2 步、第 5 步对已存在最终名的核对，以及 `read_sealed` 的逐级核对）与第 7 节共用 `_check_link_hops`、`_is_within`、`_check_listed_name`，是静态审阅 + 纵深防御，**不是安全访问保证**。已检测的情形与已知不检测的情形见本节末尾的两张清单。

**`seal_bytes(store_root, business_path, raw, *, kind, resource_id, registry, index_commit) -> ResourceRef`**

1. 校验：business_path 用 `validate_business_path`（8.3 短名形态报 `E_PATH_RESERVED`，所以以临时文件自动获得的短名 `CODEKI~1.TMP` 为业务名时，不会让 `os.link` 命中临时文件自己的短名，R-P3）；raw 必须是 bytes（`E_RESOURCE_BYTES`）；index_commit 必须可调用，否则在写入任何东西之前抛 `TypeError`；kind 必须已登记且为文件型（`E_RESOURCE_KIND`）；store_root 必须存在且是目录（`E_PATH_ROOT`）。
2. 父目录在根内逐级确认，必要时创建。每一级的核对与第 7 节相同：先解析，确认最终目标在根内；再逐跳核对这一级的链接链（`_check_link_hops`）；再确认拼写正是上一级目录中登记的真实名称。已检测的情形：
   - 已存在的越界链接或 junction → `E_PATH_ESCAPE`；经根外链接绕回根内的链接链 → `E_PATH_ESCAPE`（`link_hop_outside_trusted_root`；P4 第 3 轮，此前 `seal_bytes(root, "dhop/new.json", …)` 经 `repo/dhop → outside/dhop2 → repo/sub` 把文件写进 `repo/sub`）。测试断言：这时存储根中没有新文件，也没有调用 index_commit（`test_A13_seal_and_read_reject_link_chain_through_outside`）。
   - 逐跳核对的规则与第 7 节相同（P4 第 4 轮）：Windows 相对目标按词法折叠 `.` 与 `..`，按逐字路径访问名称，展开终点必须与这一级 resolve 的结果相同。第 3 轮之后仍有两条链能绕过核对，把文件写进 `store/evidence`：`segd → L\..\yd`（`yd → outside/dhop → store/evidence`），以及 `segd → dhop.`（`dhop.` 是指向根外的链接）。现在两者都报 `E_PATH_ESCAPE`，测试断言不写入、不调用索引（`test_A13_seal_and_read_windows_lexical_and_trailing_dot_chains`）。以相对目标开头的越界链见 `test_A13_seal_and_read_reject_relative_link_chain_through_outside`；展开终点不一致（白盒注入）报 `E_PATH_RESOLUTION_FAILED`（`link_walk_diverged`），见 `test_A13_link_walk_divergence_rejected_by_seal_and_read`。
   - 未识别的名称代理类重解析点（目录分段、已存在的最终名）→ `E_PATH_RESOLUTION_FAILED`（`link_kind_unsupported`；P4 第 5 轮，白盒注入，测试断言不写入、不调用索引：`test_A13_unrecognized_name_surrogate_rejected_by_seal_and_read`）。
   - 大小写别名 → `E_PATH_COLLISION`；其他未登记的别名 → `E_PATH_RESOLUTION_FAILED`。否则会经别名写进另一个名字的目录，返回的 path 拼写在磁盘上并不存在。自动生成的 8.3 短名形态（包括前缀含 `~` 的）在第 1 步已按 `E_PATH_RESERVED` 拒绝（R-P3）。
   - 悬空的链接祖先报 `E_PATH_RESOLUTION_FAILED`（reason 为 `target_not_found`）；已存在的祖先分段是普通文件时报 `E_PATH_RESOLUTION_FAILED`（reason 为 `ancestor_not_directory`）。这两种情形只有 seal_bytes 报 `E_PATH_RESOLUTION_FAILED`：`resolve_existing_path_for_review` 报 `E_PATH_NOT_FOUND`，`read_sealed` 报 `E_RESOURCE_MISSING`（第 3.2 节表格已按此更正）。
   - “在根内”与第 7 节相同，按 resolve 后路径组件逐字比较（共用 `protocols._is_within`），不按 `str.lower()`：指向“只在 lower() 下与根同名”的兄弟目录的链接或 junction 同样报 `E_PATH_ESCAPE`，测试断言根外没有写入（`test_A13_seal_and_read_reject_kelvin_sign_sibling`）。P2 第二轮返工前这里用 `relative_to`，复审实测可把文件写到根外（R-14）。
   - `mkdir` 只在这一次核对通过的目录下执行。**已知不检测**：核对之后祖先被其他进程换成指向根外的链接（TOCTOU、并发替换）时，下一级 `mkdir` 或随后的发布会落到根外（01-D06，复审已用注入实测）。
   - 本次按需新建的父目录在随后的步骤失败时**不回滚**（P4 写明，第 2 轮复审 paths 视角）：发布之前失败（读回摘要不符、`os.link` 抛环境类 OSError）时不残留文件，但会残留本次新建的**空**目录。原因：并发写入者可能正要在同一目录中写入，按 8.4 不在不确定时清理。`SEALING_LIMITATIONS` 已列出这一项，`test_A13_seal_failure_leaves_only_empty_new_parents` 固定这一语义。
3. 在目标所在目录用 `O_CREAT|O_EXCL` 独占创建临时文件（`.codekit-seal-<随机>.tmp`），完整写入后 fsync 并关闭。创建时传入的权限 0600 只在 POSIX 上有意义；Windows 上它只影响只读属性，ACL 仍从父目录继承。随机名连续 16 次与已有文件重名时抛 `FileExistsError`，不截断、不删除其他写入者的同名文件。
4. 重新打开临时文件读回字节，计算 SHA-256，必须等于 `sha256(raw)`。不等时删除临时文件，报 `E_RESOURCE_HASH_MISMATCH`。
5. 用 `os.link(临时文件, 最终名)` 发布，不会覆盖已有文件。写临时文件之前，若最终名已存在，先按第 2 步的规则核对一次；`os.link` 报 FileExistsError 时再核对一次：
   - 最终名已存在且字节相同：视为幂等；
   - 字节不同：报 `E_RESOURCE_CONFLICT`，不覆盖；
   - 最终名被目录（包括指向根内目录的 junction）等非普通文件占用：报 `E_RESOURCE_CONFLICT`，reason 为 `immutable_path_occupied_by_non_file`（P2 返工前误报为 `E_RESOURCE_MISSING`）；
   - 最终名是越界链接（包括指向根外文件的 symlink）：报 `E_PATH_ESCAPE`，测试断言根外文件没有被读取比较，也没有被改写；
   - 最终名是悬空链接：报 `E_PATH_RESOLUTION_FAILED`；
   - 最终名的拼写与磁盘上登记的名称只差大小写：报 `E_PATH_COLLISION`（例如已有 `Sample.json` 时封存 `sample.json`，不会以幂等成功返回一个磁盘上不存在的拼写）。
   - 最终名是与根外文件共享数据的硬链接：**不检测**（见上文“范围与前提”）。
   - 无论成功还是失败，都删除临时文件。
6. 发布后再次确认最终路径解析后的最终目标仍在根内。这一步只能**事后报告**越界（`E_PATH_ESCAPE`，reason 为 `resolved_outside_store_root`）：已经创建的链接不会删除，因为无法确认它仍是本次创建的对象（01-D06）；也不调用 index_commit、不返回引用。`test_A13_seal_post_publish_escape_is_reported`（P4 第 3 轮新增，白盒：替换 sealing 模块内的 os 引用，让“发布”落成指向根外文件的 symlink）固定这一步；此前删除这一步的变异没有被任何测试发现（复审 tests-mutation S01）。这一步只核对最终目标，不逐跳核对链接链。
7. POSIX 上 fsync 父目录；**Windows 跳过**（`DIRECTORY_FSYNC_SUPPORTED=False`）。
8. 构造 `{kind, id, sha256, path}`，以它的副本调用 `index_commit`（索引修改参数不影响返回值）。index_commit 被调用时，文件已经可读。
   - 若 index_commit 抛异常：**不返回引用**，文件作为“未引用候选”保留，报 `E_RESOURCE_INDEX_FAILED`（retryable=true）。
   - 错误中不带 source_ref，以免被误当成已发布的引用。
   - 用相同字节再次调用 `seal_bytes` 是幂等的，可用来补录。
9. 返回值只是 ResourceRef，不附带状态字段。fsync 等限制通过模块常量 `DIRECTORY_FSYNC_SUPPORTED` 与 `SEALING_LIMITATIONS`，以及本文说明。
10. 环境类 OSError（磁盘满、权限、文件系统不支持硬链接）原样抛出，不返回引用。

**`read_sealed(store_root, ref, registry) -> bytes`**：

- `store_root` 的前提与 seal_bytes 相同：必须由可信核心独占控制。
- 先校验 ref，并要求其为文件型（非文件型 kind 报 `E_RESOURCE_KIND`，`/kind`）；存储根不存在或不是目录报 `E_PATH_ROOT`。
- 逐级核对路径（与 seal_bytes 共用，判定同第 7 节）。已检测的情形：
  - 某一级解析后的最终目标在根外，或逐跳展开时遇到位于根外的链接对象（经根外绕回根内）→ `E_PATH_ESCAPE`。P4 第 3 轮起逐跳核对，此前 `read_sealed` 经 `repo/hop → outside/hop2 → repo/ok.txt` 返回字节；P4 第 4 轮起 Windows 相对目标按词法折叠 `..`、名称按逐字路径访问，此前经 `seg → L\..\y` 或 `segdot → hop.` 的越界链仍返回字节。
  - 目标写法不受支持或语义无法确定、未识别的名称代理类重解析点（P4 第 5 轮）、展开终点不一致 → `E_PATH_RESOLUTION_FAILED`。
  - 拼写不是磁盘上登记的真实名称：大小写别名报 `E_PATH_COLLISION`，其他未登记的别名（手工设置、不含 `~` 的短名）报 `E_PATH_RESOLUTION_FAILED`。自动生成的 8.3 短名形态在校验 ref 时已按 `E_PATH_RESERVED` 拒绝。
  - 不存在（含悬空链接、中间段是普通文件），或不是普通文件（目录、FIFO），报 `E_RESOURCE_MISSING`（reason 分别为 `target_not_found`/`resource_not_found` 与 `not_regular_file`）。
  - 已知不检测：检查之后的并发替换；与根外文件共享数据的硬链接（读到的是根外文件的字节，只要摘要相符就返回）；其余见下方清单。
- 环境类 OSError 原样抛出，例如文件被其他进程独占打开时的 PermissionError。**异常消息可能含本机绝对路径（包括用户目录），调用方不得原样外发**；与 seal_bytes 相同。
- **只读一次**字节，核验摘要（不符为 `E_RESOURCE_HASH_MISMATCH`），然后返回**这同一份**字节。调用方应消费返回的字节，不应之后再按路径重新读取。`test_A13_read_sealed_reads_once_returns_verified_bytes` 用白盒注入断言恰好读一次、返回的正是核验过的字节（R-16）。

**已检测的情形（sealing）**（逐项有测试；两个入口的覆盖范围见第一项）：

- 第 7 节“已检测的情形”第 1、3–7、9、10、14、15 项的路径核对，由 seal_bytes 与 read_sealed 共用，两个入口各有用例（见上文各步）；第 8、11 项走同一段代码（`_check_link_hops`），只在 `resolve_existing_path_for_review` 上有用例。越界时测试断言存储根中没有新文件、根外没有写入、没有调用 index_commit。
- 最终名被目录、越界链接、悬空链接占用，或拼写只差大小写（第 5 步）。
- 发布后复查发现最终路径解析到根外：事后报告 `E_PATH_ESCAPE`，不调用索引（第 6 步）。
- 读回摘要不符、已存在的最终名字节不同、读取时摘要不符（`E_RESOURCE_HASH_MISMATCH`、`E_RESOURCE_CONFLICT`）。

**已知不检测、不保证（01-D06、R-P9；代码中为 `SEALING_LIMITATIONS`）**：

1. 存储根不由可信核心独占控制的情形：被攻击者控制或可被其他主体写入的存储根，以及其中预置的硬链接、链接、并发替换，都不在防御范围内。
2. 与根外文件共享数据的硬链接（见上文“范围与前提”）。
3. TOCTOU 与并发替换；同一账户下其他进程的篡改。
4. 检查之后父目录或目标被替换：已完成的检查不再成立，下一级 `mkdir` 或发布可能落到根外，发布后复查只能事后报告。
5. 挂载点：卷 GUID 目标的链接按不受支持的写法失败关闭；经挂载管理器登记的真实卷挂载点未实测；POSIX 的 bind mount 等挂载不检测。
6. NT 层与 Win32 层名称语义差异之外尚未枚举的写法；不带名称代理位的重解析点按普通名称处理。
7. POSIX 平台未实测（NOT_RUN）。
8. 不提供崩溃持久性证明，没有做断电或崩溃注入测试；Windows 上不 fsync 父目录。
9. 没有按目录句柄逐级访问；只要解析后仍在根内，就接受根内的链接。不是生产级安全访问实现。
10. 发布依赖文件系统支持硬链接（`os.link`）；发布之前失败时可能残留本次新建的空父目录（不回滚，8.4）。

## 16. 附录 A.2 逐行对照

| A.2 对象 | 必需的额外检查 | 01 已实现（函数） | 部分实现 / 未实现 | 归属 |
|---|---|---|---|---|
| 全部新记录 | 字节大小/深度限制 | `strict_json_loads`（1 MiB、64 层，可调）、`check_json_value`（可选字节下界预算）、`stable_snapshot_bytes`；各记录校验先对整条记录做同样的检查 | 分段读取大文件未实现 | 01（上限值 01-D04）；分段由 04 |
| | 重复键、UTF-8、非有限数 | `strict_json_loads` | `validate_*` 接收的是已解析的 dict，调用方必须先对原始字节用 `strict_json_loads` | 01 |
| | 严格整数类型 | `require_int`，各记录中的整数字段，`route_public_record` | — | 01 |
| | 受信入口家族 | `route_public_record` 按入口声明的 record_type + 版本路由 | 家族由入口隐含决定，记录中没有 family 字段；Schema 文件没有被程序加载（本机无 jsonschema，01-L01） | 01；新入口接线由 07/09 |
| ResourceRef | kind 已登记 | `validate_resource_ref` + `ResourceKindRegistry`；收尾轮（裁决 R-P10）起登记项包含 4.2.1 要求的 schema、允许的载荷表示与语义校验器（`schema_ref`、`payload_representations`、`payload_validator`），登记时必须声明；`validate_resource_payload` 按这三项核验载荷 | 仅登记 01 的类型与 raw-segment；schema_ref 只登记不加载（01 不加载 Schema 文件） | 01；各模块登记自己的 kind 并提供三项 |
| | 文件类型要求 path | `validate_resource_ref` | — | 01 |
| | 合法路径与保护范围 | 词法：`validate_business_path`；静态解析：`resolve_existing_path_for_review`（静态审阅 + 纵深防御，不是安全访问保证，裁决 R-P9；已检测的情形见第 7 节清单：每一级最终目标在根外、逐跳展开时遇到根外的链接对象（P4 第 3 轮；P4 第 4 轮起 Windows 相对目标按词法折叠 `.`、`..`，名称按逐字路径访问，并核对展开终点与 resolve 结果相同）、拼写不是登记的真实名称、无法确定语义的链接写法与未识别的名称代理类重解析点失败关闭（P4 第 5 轮））；碰撞：`check_no_name_collisions`（含目录前缀与文件/目录同名） | **保护范围未实现**；静态解析不是访问凭证；已知不检测、不保证的情形见第 7 节清单（TOCTOU 与并发替换、检查后父目录或目标被替换、硬链接与挂载点、尚未枚举的 NT/Win32 写法、POSIX 未实测、同账户进程篡改）；词法层拒绝 8.3 短名形态（R-P3，P4 第 3 轮起含前缀带 `~` 的自动短名），但不拒绝手工设置、不含 `~` 的短名（只有物理层兜底，只按字符串比较的下游须自行物理核对）与 ANSI best-fit 字符（R-P5，消费者自行复核） | 03（保护与授权）、07；生产访问见 01-D06 |
| | 相同已固定字节上的完整 SHA-256 | `verify_resource_bytes`（对调用方给出的字节）、`read_sealed`（读一次、核验、返回同一份；存储根必须由可信核心独占控制，R-P9，见第 15 节） | 生产级受控读取未实现；硬链接等别名不检测（第 15 节清单） | 01（参考）；生产访问由对应访问实现模块负责 |
| RunContext | 标识由核心分配/绑定 | `new_request_id` / `new_run_id` 给出格式，`validate_*_id` 校验语法 | **持久唯一性与分配方未实现** | 07 |
| | executor 所需字段非空 | `validate_run_context(for_executor_dispatch=True)`（字段非空，且 role 为 executor） | planner/observer 是否需要合同由调用 profile 决定，未实现 | 01；profile 由 02/07 |
| | 合同引用、版本、任务与 request 一致 | 只做形状与登记检查 | **与受信记录一致性未实现** | 07、09 |
| 结构化错误 | 不泄露输入秘密 | `ProtocolError.to_record`：固定文案与原因（P4 第 3 轮起 `E_JSON_SYNTAX` 的 reason 也固定，行列号只在 hint）、只含字段名指针、按上限截断、清除代理项 | 字段名本身会出现在指针中 | 01 |
| | 来源引用可信 | 构造时检查 `source_ref` 形状 | **可信与否由调用方负责** | 调用方 |
| | retryable 不执行任何动作 | 本模块从不据此动作 | — | 01；重试决策由 07 |
| 时间 | 日历日期确实有效 | `parse_observed_at` | — | 01 |
| | 启用格式断言 | 代码中直接检查，不依赖 jsonschema 的 format | — | 01 |
| | 固定 UTC 表示 | `format_observed_at` | — | 01 |
| | 不以格式精度声称时钟精度 | 只在文档中声明 | 时钟来源、单调计时未实现 | 04、07 |
| 运行事件 | seq 连续/重复/冲突判断 | `assess_event_log`（含持久化顺序的乱序检查）、`append_event`、`recover_next_seq`、`recover_append_state`（崩溃后重建 state） | **持久追加与序号分配的事务协调未实现**（只有内存模型）；4.3.2 的两行没有 01 接口（收尾轮 M-11，见第 11 节末尾）：派生视图修订与 view_id、跨 run 的先后关系 | 07、04；派生视图修订与 view_id 归 04；跨 run 先后归 10（项目游标） |
| | type 注册及 payload Schema | `EventTypeRegistry` 接口 + `validate_run_event(event_types=...)` | 只登记示例 `run.prepared`；**真实类型与载荷 Schema 未登记** | 04（01-D07） |
| | 角色和 run 绑定 | `validate_run_event(context=...)`；vendor 事件的 role 必须非空（P4 第 3 轮，此前 vendor 事件置空 role 即可脱离角色绑定）；事件日志系列函数核对同一 run 内 run_id、request_id 一致与非空 role 一致（收尾轮 M-01，第 11 节） | 无角色的核心事件（role 为 null）不做角色核对，只核对 request/run（4.3.1 允许）；事件日志系列函数只核对日志内部一致，与受信 RunContext 的绑定仍须逐条用 `validate_run_event(context=...)` | 01；受信 context 由 07 提供 |
| | 事件来源 | `EventType.allowed_sources` → `E_EVENT_SOURCE` | — | 01 接口；具体类型归 04 |
| raw_refs | start < end <= 真实段大小 | `validate_raw_span(segment_sizes=...)`；ref 只能是 raw-segment（R-P7） | segment_sizes 必须来自受信封存索引，本模块不查询 | 01；索引由 04/07 |
| | stream 合法 | `validate_raw_span` | — | 01 |
| | 脱敏后偏移与引用版本匹配 | 偏移按被引用版本（sha256）的字节计，超出即拒绝 | **脱敏前后偏移映射未实现** | 04 |
| vendor 事件 | 解析修订必须已知 | adapter_revision 非空 | **该修订是否为已知/锁定的适配器版本未检查** | 04、06 |
| | 没有可引用来源的事件不得声称证据完整 | `integrity=complete` 且 raw_refs 为空时报 `E_EVENT_EVIDENCE_MISSING` | — | 01 |
| 核心事件 | 空 raw_refs 不能伪装厂商成功、模型身份或用量 | 核心来源不能使用只允许 vendor 的类型（`E_EVENT_SOURCE`） | **核心载荷内容是否冒充上述信息未检查** | 04（类型校验器） |
| 用量 | 计数口径 | include 标志只记录分布，不相加 | 口径含义未解释 | 04（来源口径）、07 |
| | 累计/增量范围 | `usage_view` 按范围解释；混用、以及 provider/model 未知的范围与其他范围并存时报 `E_USAGE_SCOPE_UNKNOWN`；累计序列回退、终止后又有累计报 `E_USAGE_CONFLICT` | 范围键不含账户范围 | 01 视图；07 记账 |
| | unknown 原因 | `validate_usage_observation` | 不支持子路径 | 01 |
| | 费用来源 | billing_source 为封闭枚举；reported_cost 非 null 时来源必须是 vendor_reported 或 provider_invoice（`E_USAGE_VALUE`）；同一账单事件的不同来源在视图中是冲突 | 估算规则本身、账户范围未检查 | 01（单条与视图）；07 |
| | 币种是否识别 | 只检查三位大写字母的语法 | **ISO 4217 成员资格未检查** | 07 |
| | 修订链 | `usage_view` | — | 01 视图 |
| | 唯一记账 | 视图标记 `is_accounting=false` | **记账未实现（按设计）** | 07（01-D08） |
| Schema 路由 | 新版本不能回退 v1 | `route_public_record`、各记录的版本检查 | — | 01 |
| | 未知字段不能静默丢弃 | 所有记录字段封闭 | 扩展容器未定义 | 01；扩展容器由各模块定义 |
| | 加载 Schema 不允许外发 | 本模块不加载 Schema，也不访问网络 | — | 01 |

## 17. 下游模块使用指引

- **02 配置**：
  - 原始字节先经 `strict_json_loads`；
  - 完成字段级验证与语义投影后，再用 `stable_snapshot_bytes` 和 `sha256_hex`；
  - 快照函数不替你删除秘密、补默认值或排序集合字段（01-D05）；
  - 机器定位字段放进环境锁，不进入快照。
- **03 审核与锁**：
  - `input_refs` 用 `validate_resource_ref` 检查，再用 `verify_resource_bytes`/`read_sealed` 在同一份固定字节上核验；
  - 审核记录不能反向嵌入被审核对象的摘要，依赖顺序用 `check_resource_dag` 检查；
  - 错误出口用 `ProtocolError.to_record()`。
- **04 适配器**：
  - 用 `EventTypeRegistry.extended()` 登记真实类型与载荷校验器（设置 allowed_sources）；
  - 用 `assess_stream_integrity` 判定关键未知内容；known_optional 与 ignorable_optional 在 01 中判定相同，“已知但未被理解”的区别由 04 的解析层定义；
  - 原始流按 raw-segment 封存（`seal_bytes`），事件用 `raw_refs` + `segment_sizes` 引用封存版本；raw_refs 只能引用 raw-segment（R-P7）；封存的存储根必须由可信核心独占控制，sealing 不防御被攻击者控制的存储根（R-P9，第 15 节）；
  - vendor 事件必须带 adapter_revision；
  - **派生视图修订与 view_id**（4.3.2“同一原始证据换新解析器重建视图”，收尾轮 M-11）：由 04 与 adapter_revision 的锁定一并设计。01 没有对应的记录类型；重建的视图不能写回原 run 的事件日志（同一 seq 的不同内容是 `E_EVENT_REPLAY_CONFLICT`）；
  - 事件日志系列函数自收尾轮（M-01）起核对同一 run 内 request_id 与非空 role 一致；与受信 RunContext 的绑定仍须逐条调用 `validate_run_event(context=...)`；
  - captured fixture 由 04 采集时填写 `capture`（采集环境引用与截取范围）、`origin.traceable=true`、`integrity`、`platform_scope` 与 `redaction.protocol_structure_preserved`（R-P11，第 14 节）；环境记录若用 04 自己的资源类型，先登记该类型。
- **登记资源类型的模块（02、03、06、09 等）**：登记时必须声明 `schema_ref`、`payload_representations`、`payload_validator`（R-P10，第 8 节），否则 `E_SCHEMA_FIELDS`；载荷核验用 `validate_resource_payload`。`validate_resource_ref` 通过不代表内容已校验。
- **06 插件**：用 `ResourceKindRegistry.extended()` 登记插件锁类型，owner 为 "06"，不能改动 01 的登记。
- **07 调度**：
  - 用 `new_request_id`/`new_run_id` 分配标识，并自行检查持久唯一性；
  - 用 `derive_run_context` 区分重连、重放与真实重试；executor_retry 必须传入分配器给出的 attempt（R-P2），01 只核对它不小于 parent.attempt；
  - 派遣前调用 `validate_run_context(..., for_executor_dispatch=True)`（要求 role 为 executor），并核对受信记录；
  - 事件日志用 `append_event`/`recover_next_seq` 的语义，做成事务化实现；
  - 状态展示用 `build_run_dimensions`；
  - 记账**不要**直接使用 `usage_view` 的结果（它不是记账）。
- **09 规划与合同**：
  - 登记合同资源类型；
  - `plan_version` 用 `validate_plan_version`；
  - 返工时用 `derive_run_context(..., "rework_new_contract", new_plan_version=...)`；
  - 版本是否单调由 09 检查。
- **10 项目状态**：
  - 运行结果按 `build_run_dimensions` 的各维度分别引用，不聚合成“成功”；
  - 集成观测放在 `integration_observation`，由 10 定义其内容；
  - **跨 run 的先后关系**（4.3.2，收尾轮 M-11）由 10 的项目游标和显式依赖表达，不按 observed_at 强造全序；01 的 seq 只在单个 run 内有意义。

## 18. 与规格的差异和取舍

1. **不用 dataclasses**：`ResourceKind` 与 `EventType` 改为手写的不可变类（见第 1 节）。
2. **`validate_run_context` / `validate_usage_observation` 增加可选参数 `registry`**。`validate_public_record` 会把 registry 传给这两类记录的 contract_ref/evidence_refs：通过公共入口时，这些引用的 kind 必须已登记。直接调用两者且不给 registry 时，只做形状检查，并如实声明。
3. **`validate_plan_version` 的 `allow_null` 默认为 False**：规格没有给默认值，这里取较严格的一侧。
4. **错误码的统一口径**：
   - 封闭枚举外的值（包括类型不对）都为 `E_SCHEMA_FIELDS`。
   - 字符串长度越界为 `E_SCHEMA_FIELDS`；非字符串为 `E_SCHEMA_TYPE`。
   - 记录字符串中的孤立代理项为 `E_JSON_UNICODE`（路径字段仍为 `E_PATH_SYNTAX`）。
5. **直接调用记录校验函数时，先检查 schema_version/record_type，再检查字段封闭**，与路由的顺序一致。因此缺少 schema_version 时报 `E_SCHEMA_VERSION_TYPE`，而不是 `E_SCHEMA_FIELDS`。
6. **返回报告多了 `semantic_checks_skipped` 键**。run-context 与 usage 的 `payload_validated` 恒为 true。
7. **`derive_run_context` 比规格更严**：
   - 不适用于该动作的参数会被拒绝，不会忽略；
   - rework 必须给出 new_plan_version；
   - executor_retry 要求 parent.role 为 executor（P2 调和时改为检查，见 C-04）。
8. **`build_run_dimensions`**：
   - 参数都有默认值 None；
   - 进程以非 0 退出且缺结束证据时，protocol_complete 也为 false（规格只写了“退出 0”）；
   - protocol_conflict 在未知时为 null；
   - 增加了 `rule_revision`、`approval_note` 与 `protocol_observation` 三个键（最后一个在 P2 调和时加入，见 C-05）。
9. **`assess_event_log`**：
   - 增加 `invalid` 键和可选参数 `run_id`；
   - 各列表按 seq 列出；
   - 冲突的 seq 不进入 events，被隔离。
10. **`recover_next_seq`**：遇到绑定错误和不可读记录时，分别报 `E_CONTEXT_BINDING` 和 `E_SCHEMA_TYPE`。
11. **`usage_view` 的结构与传播规则**：
    - 结构：计量在顶层，并有 distributions、scopes 等附加键。
    - 空输入视为不完整。
    - 未知币种会传播到同类费用的所有币种组。
    - 以下情况视为冲突：修订分叉、修订成环、修订改变绑定。
    - 未解析的修订使全部计量不完整。
12. **fixture manifest 增加的检查**：
    - applied=true 时 rule_revision 必须非空；
    - proves 与 does_not_prove 不得有交集；
    - reject 必须有 code，accept 的 code 必须为 null；
    - negative 的 derived_from 不能是自身，且必须在清单中；
    - 同一拼写的路径对应不同摘要时报 `E_PATH_COLLISION`；
    - 重复的 fixture_id 报 `E_SCHEMA_FIELDS`；
    - source_revision 接受 40 或 64 位 OID（清单中没有对象格式字段）；
    - 真实兼容声明另按前缀判定。
13. **`seal_bytes`**：
    - 返回纯 ResourceRef；
    - 会创建父目录；
    - 环境类 OSError 原样抛出；
    - 按 registry 绑定 protocols 模块；
    - `sealing.ProtocolError` 采用惰性解析。
14. **`ERROR_CODES` 按规格是普通 dict**，运行时可变。它属于可信核心，调用方不应修改。
15. **`interpret_git_object_type`**：未知的 expected_type 报 `E_COMPAT_UNSUPPORTED`；stdout 允许结尾是 `\r\n`。
16. **`resolve_existing_path_for_review`**：根目录的任何解析失败都报 `E_PATH_ROOT`；中间段是文件（NotADirectoryError）按 `E_PATH_NOT_FOUND` 处理，与 Windows 行为一致。
17. **P2 返工新增的扩展**（逐项理由见第 19 节“P2 返工”）：
    - `validate_public_record` 拒绝不适用于该记录类型的参数（`E_SCHEMA_FIELDS`）；
    - 三类记录与 fixture manifest 条目先对整条记录做 JSON 原生值检查；受信 context 参数不合法时 field 加前缀 `/context`；
    - `check_json_value` 增加可选参数 `max_bytes`；`stable_snapshot_bytes` 在生成输出前按下界预算止损；
    - `strict_json_loads` 不再做解析前的文本深度预检查，深度在解析后按真实字符串边界计算；
    - `check_no_name_collisions` 增加目录前缀碰撞与“文件/目录同名”检查（`find_name_collisions` 的输出不变）；
    - `resolve_existing_path_for_review`、`seal_bytes`、`read_sealed` 逐级核对“仍在根内”与“拼写是登记的真实名称”；
    - `assess_event_log` 增加 `out_of_order`；`recover_next_seq` 增加可选参数 `run_id`；新增 `recover_append_state`；`append_event` 检查 record_type 与 state 不变式；
    - `build_run_dimensions` 增加 `contract_approval_ref`，非 "success" 的结束证据使 `protocol_conflict` 为 null，`process_exited=False` 与 exit_code 同时出现时报错；
    - `usage_view` 增加重复投递归并（第二轮返工改为“修订只替代明确指向的目标及其重复投递”，R-15）、整条修订链的币种检查、逻辑顺序、来源不明范围、累计序列自洽与合计上限，scope 报告增加 `ambiguous_scope` 与 `ignored_usage_ids`；`validate_usage_observation` 检查 reported_cost 与 billing_source 的一致性；
    - `ProtocolError.details` 与 `to_record()` 的 field 截到祖先指针并加标记；
    - 业务路径的控制字符扩大到 Unicode Cc（含 C1），设备名只做 ASCII 大小写折叠；
    - `seal_bytes` 的最终名被非普通文件占用时报 `E_RESOURCE_CONFLICT`。
18. **P4 新增的扩展与改动**（逐项理由见第 19 节“P4”）：
    - 裁决 R-P1–R-P8 的落实：retryable 收窄；executor_retry 的 attempt 取参数；词法层拒绝 8.3 短名形态、行/段分隔符与双向控制字符；raw_refs 只能引用 raw-segment；`assess_event_log` 增加 `event_count`；
    - `validate_public_record` 在路由前做整条记录的 JSON 原生值检查；单独调用的 `validate_raw_span`、`validate_fixture_manifest_set` 与 run.prepared 载荷校验器都按 1 MiB 字节下界止损；
    - `validate_run_context(for_executor_dispatch=True)` 要求 role 为 executor；
    - `assess_event_log` 增加 `record_type_errors`；恢复函数先报记录本身的缺陷；`append_event` 完整核对 state 不变式；
    - `build_run_dimensions` 的 cancelled 改为三态并增加参数 `cancellation_checked`，规则修订升为 v2；
    - `usage_view`：provider 为 null 时同一账单号的多条有效观测报 `E_USAGE_SCOPE_UNKNOWN`；没有有效观测时两类费用各有一个不完整的 unknown_currency 组；
    - fixture 清单：能力声明规则作用于全部条目，captured 可配 normalized_event，脱敏元数据与负例表示的新规则，清单级的 legacy 派生规则；
    - `sealing`：写明失败时可能残留新建的空父目录（不回滚）。
19. **P4 第 3 轮的改动**（逐项理由见第 19 节“P4 第 3 轮”）：
    - 与参考实现的顺序差异已恢复：`stable_snapshot_bytes` 先检查根类型，再检查值（附录 B.2）；
    - 比参考实现与原规格更严或更具体的地方：`strict_json_loads` 的非有限数与整数越界带 JSON Pointer（多缺陷输入的首错因此变化，见第 4 节）；`E_JSON_SYNTAX` 的 reason 固定、位置移到 hint；环不论多长都报 `E_JSON_CYCLE`；vendor 事件的 role 必须非空；`assess_stream_integrity` 拒绝未登记的必需类型；`assess_event_log` 对 str 型的非法参照 run_id 也记绑定错误；`derive_run_context` 先校验再拷贝；
    - 业务路径：8.3 短名形态的前缀允许含 `~`（与裁决 R-P3 原文不同，待规划端确认）；静态解析与封存逐跳核对链接链；
    - `usage_view`：provider 为 null 的账单号按修订链全部成员、只按 billing_event_id 分组；cumulative/final 的 null 字段取此前已证明的下界；
    - fixture 清单：能力声明的封闭词法；负例不能从负例派生。
20. **P4 第 4 轮的改动**（逐项理由见第 19 节“P4 第 4 轮”）：
    - 逐跳核对链接链：Windows 上按词法折叠相对目标文本中的 `.` 与 `..`（本机实测 I/O 管理器处理相对 symlink 时按词法折叠；此前按物理语义），按逐字路径访问名称（名称末尾的点与空格不被 Win32 规范化去掉）；展开终点必须与 resolve 结果相同（`link_walk_diverged`）；含 `/` 的 Windows 目标、`\\.\` 设备路径、`..` 越过盘符根都按不受支持的写法处理；POSIX 仍按物理语义（设计意图，NOT_RUN）；
    - 该轮对逐字绝对目标也做同样的词法折叠，并把整条规则写成与 OS 的处理相同。已由 R-P9 / P4 第 5 轮更正：本机实测内核对逐字绝对目标中的 `.`、`..` 与空分段不折叠，而是拒绝解析；第 5 轮起逐跳核对把这类写法按不受支持的写法拒绝（见第 21 项与第 7 节）；
    - `usage_view` 第 5b 步：provider 为 null 的账单号与 provider 已知的同号观测同样不能相加；判定移到第 6 步的范围歧义判定之后。
21. **P4 第 5 轮的改动**（逐项理由见第 19 节“P4 第 5 轮”）：
    - 裁决 R-P9：业务路径的物理检查定位为“静态审阅 + 纵深防御”，不是安全访问保证；第 7、15 节与相关 docstring 改为“已检测的情形”与“已知不检测、不保证”两张清单；新增常量 `PATH_REVIEW_LIMITATIONS`；`SEALING_LIMITATIONS` 补充存储根由可信核心独占控制、A13 范围、检查后替换、硬链接、挂载点、尚未枚举的写法、POSIX 未实测等项；
    - 逐跳核对的失败关闭范围扩大：未识别的名称代理类重解析点报 `link_kind_unsupported`；只有根、没有盘符的目标（此前受支持）、不带 `\\?\` 的盘符绝对路径、逐字绝对目标中的 `.`、`..` 与空分段，都按不受支持的写法处理；
    - `usage_view` 第 5b 步按成员判定登记账单号：链尾为 unknown 的链也登记其已知成员的账单号。
22. **收尾轮的改动**（逐项理由见第 19 节“收尾轮”）：
    - **裁决 R-P10（acceptance.md M-10）**：文档 4.2.1 要求 kind 注册表包含 schema、是否文件资源、允许的载荷表示、语义校验器及所属模块；收尾轮之前 `ResourceKind` 只有 name、is_file、owner_module、description 四个字段，缺 schema、允许的载荷表示与语义校验器三项，这一差异此前没有在本节登记。现在 `ResourceKind` 增加 `schema_ref`、`payload_representations`、`payload_validator`，登记时必须声明（`E_SCHEMA_FIELDS`），并新增 `validate_resource_payload`（第 8 节）。与规格仍有的差异与取舍：
      - schema_ref 只登记、不加载：本机无 jsonschema 且不授权安装（01-L01、01-L07），所以 `validate_resource_payload` 不按 Schema 校验，把 `resource_schema` 列入 skipped；01 预登记的五类 schema_ref 都为 None，结构由校验器代码表达；
      - 校验器的签名是 `(raw, registry)`，接收已核验摘要的同一份字节，不接收解析后的对象（不同类型的载荷表示不同）；
      - text 与 markdown 的字节检查相同（严格 UTF-8），区别只是登记用的标签；
      - 校验器抛出 ProtocolError 以外的异常时包装为 `E_SCHEMA_FIELDS`（没有新增错误码），不带原异常的文字；
      - 显式传入的非法值抛 `ValueError`（构造登记项时的程序错误），缺失三项是登记时的 `E_SCHEMA_FIELDS`。
    - **裁决 R-P11（M-03）**：fixture 条目新增 `integrity`、`platform_scope`、`capture`、`redaction.protocol_structure_preserved`、`origin.traceable`（第 14.1 节），新增第 14.2 节第 3b、5 步的来源规则。比裁决原文多出的一条是保守补充：`applied=true` 而 `protocol_structure_preserved` 为 null 时也不得声称 `protocol_field_semantics`（4.3.3）。两类声明的名称由实施者选定，裁决原文未规定；收尾轮按 `complete_run_stream`、`full_run`、`protocol_field_semantics` 三个前缀判定，收尾轮返工起改按受控词表判定（第 14.2 节第 5 步），词表外的同义写法不受限制。
    - **M-01**：`assess_event_log`、`append_event`、`recover_next_seq`、`recover_append_state` 除 run_id 外，还核对同一 run 内 request_id 一致与非空 role 一致（第 11 节）；绑定字段不可读的记录列入 invalid；`append_event` 的 state 形状不变。
    - **R-P3 勘误**：8.3 短名形态的判定以实现为准（第 7 节），代码不变。
    - **M-11**：4.3.2 的两行（派生视图修订与 view_id、跨 run 的先后）在 01 中没有接口，归属写入第 11、16、17 节。
    - **M-12**：第 3.2 节 `E_BASELINE_*` 的说明改为“登记待用；当前取证工具不发出”，代码不变。

## 19. 规格澄清（P2 调和与 P4 裁决落实）

实现（`protocols.py`、`sealing.py`）与测试（`tests/test_protocols.py`）由两位实施者按同一份 01-T2 规格各自独立编写。P2 调和时对照了规格、设计文档与两边的歧义清单。

**调和经过**

- 第一次合并运行：`Ran 191 tests`，`OK (skipped=3)`，没有失败。
- 虽然全部通过，但测试中约有 30 个调用点（按调用点计，循环展开前）只断言“被拒绝”、接受多个错误码，或按键名模糊查找返回结构。它们对应规格没写死的地方，下游模块无法依赖。
- 下面逐条裁决：规格含糊时，取更严格、更符合设计文档原意的解释，再把实现与测试改成一致。
- 调和后，所有负例都断言唯一的稳定错误码，多数还断言 `field` 指针。测试中原有的 `assertCodeIn`（接受多个码）与 `assertRejected`（只要求被拒绝）已删除。
- 最终运行：`Ran 198 tests`，`OK (skipped=3)`。
- 判别力抽查：在临时副本中对实现做 8 处反向改动，对应测试全部失败。

**本节改动了实现的三项**：C-04 的 executor_retry 父角色、C-05 的 `protocol_observation`、C-06 的 known_required 语义。其余各项只改了测试的断言，或者只在本文写明原有行为。

### C-01 错误码表

- `ERROR_CODES` 恰好是 58 个码，来源为：
  - 4.2.7 与 4.3.6 两张表；
  - 附录 B.2 参考实现用到的码；
  - 01-T2 规格列出的 20 个新增码。
- 测试断言集合**相等**，不只是包含。
- 以后新增错误码，要同时修改本文第 3.2 节和测试。

### C-02 retryable 取值

- **P4 起按裁决 R-P1 收窄**：为 true 的恰好 5 个码：`E_EVENT_GAP`、`E_EVENT_REPLAY_CONFLICT`、`E_PROTOCOL_INCOMPLETE`、`E_EVENT_RAW_REF_UNKNOWN`、`E_RESOURCE_INDEX_FAILED`；其余 53 个码为 false（含 `E_EVENT_RAW_RANGE`、`E_EVENT_TYPE_UNKNOWN`、`E_EVENT_SOURCE`、`E_EVENT_EVIDENCE_MISSING`）。
- P2 调和时的取值（已被 R-P1 取代）：全部 7 个 `E_EVENT_*` 与 `E_PROTOCOL_INCOMPLETE`、`E_RESOURCE_INDEX_FAILED` 为 true，依据是 01-T2 规格原文“E_EVENT_*、E_RESOURCE_INDEX_FAILED 这类……设 retryable”。
- 4.3.6 表中的路径、资源、Git、用量、基线类都写明“不能靠放宽边界修复”“不重算期望摘要”“先确认基线”等，不自动重试。
- 原测试只断言了其中 4 个码，现在逐码断言。
- retryable 仍然只是提示，不触发任何动作。

### C-03 规格只写“拒绝”时的通用错误码

适用于只规定“拒绝”、未写错误码的情形：

| 情形 | 错误码 |
|---|---|
| 封闭枚举外的值，包括 None 和非 str。涉及 role、platform、source_kind、integrity、stream、observation_kind、billing_source、origin.class、representation、expected.outcome、legacy_verdict、protocol_integrity、classification 的值 | `E_SCHEMA_FIELDS` |
| 字符串长度越界；数组超过上限（raw_refs、evidence_refs 超过 256 条） | `E_SCHEMA_FIELDS` |
| 应为字符串、对象、数组或布尔值，类型却不对（例如 payload 不是对象） | `E_SCHEMA_TYPE` |
| payload 中有非 JSON 原生值 | `check_json_value` 的对应码（例如 `E_JSON_VALUE_TYPE`），field 指向具体位置，如 `/payload/x` |
| money 不是对象、缺字段或多字段；金额或币种格式错误 | `E_USAGE_VALUE` |

依据：

- 7.4 要求单一故障负例断言稳定错误码。
- 参考实现里 `E_SCHEMA_FIELDS` 表示“字段集合不符合封闭定义”，本模块把它扩展到取值集合与长度范围，错误码表的文案已写明。

### C-04 `derive_run_context`（实现已改）

**executor_retry 的父上下文**

- 父上下文 role 必须是 executor，否则报 `E_SCHEMA_FIELDS`，field 为 `/role`。
- 依据：4.1.2 这一行写的是“原执行失败后再次启动 executor”，planner 或 observer 运行不能派生 executor 重试。
- 原实现不检查角色。
- **P4（裁决 R-P2）**：executor_retry 的 attempt 取参数（受信分配器给出，≥ parent.attempt），不再是 parent.attempt+1；未传入 `E_CONTEXT_INCOMPLETE`，倒退 `E_CONTEXT_BINDING`（第 5.2 节）。同一理由，P4 起 `validate_run_context(for_executor_dispatch=True)` 也要求 role 为 executor（`E_SCHEMA_FIELDS`，`/role`）。

**参数与各动作的取值**（与实现原行为一致，测试现已断言）：

- 参数不适用于该动作时报 `E_SCHEMA_FIELDS`，不会静默忽略。
- observer_call 传入非 observer 的 role，报 `E_SCHEMA_FIELDS`。
- rework_new_contract：
  - 缺 new_plan_version 报 `E_CONTEXT_INCOMPLETE`（`/plan_version`）；
  - attempt 取参数，未给出时为 null，不自动加 1。4.1.2 写的“沿用调度器规则”由 07 计算后传入；
  - task_id、role、platform 没给新值时保持不变。
- new_goal：task_id、plan_version、contract_ref、attempt 都取参数，未给出时为 null；role 与 platform 保持不变。
- observer_call：task_id、plan_version、contract_ref、platform 保持不变。
- plan_version 是否单调递增，由 09 检查。

### C-05 `build_run_dimensions` 保留双方证据（实现已改）

- 新增 `protocol_observation{end_evidence, integrity}`，原样保留这两个输入。
- 依据：
  - C.3 的 01-F041 要求“冲突/失败，保留双方证据”；
  - 4.3.4 把“只保留成功结束事件”列为不允许的做法。
- 原视图只保留了退出码与冲突标志，结束证据本身丢失了。
- 同时断言了以下既有行为：
  - 非零退出且没有结束证据时，`protocol_complete=false`；
  - 冲突的任一方未知时，`protocol_conflict=null`；
  - 退出 0、有结束证据且 integrity 为 complete 时，`protocol_complete=true`。

### C-06 `assess_stream_integrity` 中 known_required 的含义（实现已改）

- 必须出现的类型 = `required_kinds` ∪ classification 中标为 known_required 的类型。
- 依据：4.3.4 把内容分为 known_required、known_optional 与 unknown，按字面理解，required 就是“必须出现”。
- 原实现只看 `required_kinds`。那样的话，调用方漏传参数时，缺少结束类内容也会被判为 complete，classification 中 known_required 与 known_optional 的区别也就没有作用。
- 给 04 的提示：可能不出现、但一旦出现就必须理解的关键内容，应登记为 known_optional。它仍是已知内容，不会被当作 unknown。
- **P4 写明**：known_optional 与 ignorable_optional 在本接口中判定结果完全相同（接口不接收“内容是否被理解”），两者的区别由 04 定义；测试 docstring 原先写“只有 ignorable_optional 可忽略”，与实现不符，已更正（第 11 节）。

### C-07 记录头的检查顺序与 schema_version 下界

- 直接调用 `validate_run_context` 等记录校验函数时，与 `route_public_record` 相同，先检查记录头，再检查字段封闭：
  - 缺 schema_version：`E_SCHEMA_VERSION_TYPE`；
  - 缺 record_type：`E_SCHEMA_RECORD_TYPE`。
- 这样同一输入无论经过路由还是直接校验，都得到同一个错误码。
- **P4 更正**：P2 返工（R-03）让直接的记录校验函数先做整条记录的 JSON 原生值检查，而 `validate_public_record` 先路由，于是上一条对 JSON 层故障不成立（第 2 轮复审 fidelity/json 视角）：schema_version=2^60 在两个入口分别报 `E_SCHEMA_VERSION_UNSUPPORTED` 与 `E_INTEGER_RANGE`，NaN 分别报 `E_SCHEMA_VERSION_TYPE` 与 `E_JSON_NON_FINITE`，str 子类的 record_type 分别报 `E_SCHEMA_RECORD_TYPE` 与 `E_JSON_VALUE_TYPE`。P4 让 `validate_public_record` 在路由前做同样的检查，单独调用的 `validate_raw_span` 也先做 JSON 原生值检查，上一条现在对这些情形同样成立（`test_A09_public_entry_and_direct_validators_agree`）。`route_public_record` 单独调用时仍不做 JSON 原生值检查。
- schema_version 为 0 或负数时报 `E_SCHEMA_VERSION_TYPE`，沿用参考实现的 `version < 1`。只有大于等于 1 的精确整数，才进入“是否受支持”的判断。

### C-08 检查报告

- `validate_public_record` 的返回值另有 `semantic_checks_skipped`，与 `semantic_checks` 不相交。
- 对 run-event 报告：
  - 没有提供 context 或 event_types 时，`context_binding`、`event_type_registered`、`payload_validator` 出现在 skipped 中；
  - `seq_continuity` 与 `core_event_claims` 始终在 skipped 中。

### C-09 用量计量值的错误码

- 计量字段是新协议的整数字段，与 seq、plan_version 一样按 `require_int` 检查：
  - 类型不对（bool、`1.0`、字符串）：`E_SCHEMA_TYPE`；
  - 负数或大于 2^53-1：`E_INTEGER_RANGE`。
- `E_USAGE_VALUE` 只用于 money（金额与币种）。
- 原测试三个码都接受。
- 同理，事件的 `seq=1.0` 与计量的 `100.0` 都报 `E_SCHEMA_TYPE`。

### C-10 事件日志的返回形态

- `assess_event_log` 的返回值：
  - `duplicates`、`conflicts`、`binding_errors`：按 seq 列出的列表；
  - `gaps`：`(expected, got)` 元组的列表；
  - `invalid`：不可读记录的下标列表；
  - `record_type_errors`：record_type 不是精确 `"run-event"` 的记录下标（P4 新增）；
  - `event_count`：events 中的事件数（P4 新增，裁决 R-P8）。
- 冲突的 seq 被隔离，不进入 `events`；`last_contiguous_seq` 停在冲突之前。
- `append_event` 的 `committed[seq]` 保存该记录的 `stable_snapshot_bytes`。依据：4.3.2 “比较已封存的标准记录版本/字节”。
- F038 同时断言：`append_event` 与 `recover_next_seq` 在冲突时报 `E_EVENT_REPLAY_CONFLICT`。

### C-11 `usage_view` 的输出结构

- 五个计量是顶层键，每个的值恰好是 `{known_total:int, is_complete:bool, unknown_count:int}`。
- 费用在顶层的 `reported_cost` 与 `estimated_cost` 下按币种分组。缺失的费用归入 `"unknown_currency"` 组。每组恰好是 `{known_total:十进制字符串, is_complete, unknown_count}`。
- `duplicates` 是整数计数。
- `unresolved_supersedes` 列出发起修订的观测的 usage_id：
  - 该观测仍计入；
  - 五个计量、全部费用组与顶层 `is_complete` 都为 false。
- 同类费用中只要有一条币种未知，该类的**所有**币种组都不完整，因为未知费用可能属于任何币种。
- 估算费用不会在 reported 下生成任何币种组。
- 空输入时各计量 `known_total=0`、`is_complete=false`：没有观测不等于零用量。P4 起两类费用各有一个 `unknown_currency` 组（`known_total="0"`、`is_complete=false`、`unknown_count=0`），原来是 `{}`。

### C-12 fixture 来源清单

- origin.source_revision 不是完整小写 OID（短 OID、大写、尾随换行、分支名）时，对任何来源类别都报 `E_GIT_OID_SYNTAX`（`/origin/source_revision`）。这是结构层的语法错误。
- `E_PROVENANCE_CLAIM` 只用于结构合法、但来源、表示或声明不一致的情形：
  - synthetic、captured、redacted_raw、legacy、negative 各自的规则；
  - proves 与 does_not_prove 有交集；
  - derived_from 不在本清单中。
- 其他情形：

  | 情形 | 错误码 |
  |---|---|
  | resource.kind 不是 fixture | `E_RESOURCE_KIND` |
  | fixture_id 重复 | `E_SCHEMA_FIELDS`，field 指向后一条的 `/entries/<i>/fixture_id` |
  | outcome 为 reject 但没有 code；outcome 为 accept 却带 code | `E_SCHEMA_FIELDS` |
  | 同一拼写的路径指向不同摘要 | `E_PATH_COLLISION` |

- legacy 条目的 representation 不作限制。P3 的草稿清单 `tests/fixtures/codekit01/manifest.legacy.draft.json` 中，legacy 条目使用 synthetic_fixture。调和后已复核：该草稿 32 条仍全部通过（草稿已并入 manifest.json 并删除）。
- **P4 改动**（第 14.2、14.3 节）：negative 不能配 captured_raw/redacted_raw；captured 可以配 normalized_event（要求 generator_revision）；脱敏元数据要求 length_changed，captured_raw 不能是脱敏过的字节；能力声明规则作用于全部条目，不再只看 origin.class=synthetic；清单级增加“声明 legacy_ 能力的负例必须从 legacy 条目派生”。当前 manifest.json 的 169 条全部通过。

### C-13 `seal_bytes`

- 返回值与交给 `index_commit` 的参数，都**恰好**是 ResourceRef 的四个字段，可直接交给 `read_sealed`。测试不再接受 `{"ref": ...}` 包装。
- 错误码：

  | 情形 | 错误码 |
  |---|---|
  | kind 不是文件型 | `E_RESOURCE_KIND`（`/kind`） |
  | resource_id 非法 | `E_RESOURCE_FIELD`（`/id`） |
  | raw 不是 bytes | `E_RESOURCE_BYTES` |
  | 存储根不存在 | `E_PATH_ROOT`，且不创建根目录 |
  | 存储根是普通文件（P2 返工补测） | `E_PATH_ROOT`，不创建任何文件 |
  | 最终名被目录等非普通文件占用（P2 返工） | `E_RESOURCE_CONFLICT`，reason 为 `immutable_path_occupied_by_non_file` |
  | index_commit 抛出任何异常（不限 RuntimeError） | `E_RESOURCE_INDEX_FAILED`，retryable=true |

- 临时文件读回的摘要不符时报 `E_RESOURCE_HASH_MISMATCH`：不发布、不残留、不调用索引。
  - 这一项用白盒注入测试：替换 sealing 内部的 `_read_all`；
  - 黑盒无法制造“写入后读回不一致”，所以用白盒注入。P2 返工又增加了一个白盒用例 `test_A13_seal_temp_file_is_exclusive_and_fsynced`：固定临时名的随机部分并预置同名文件，断言独占创建失败时不截断、不删除他人文件，并用计数桩确认调用了 fsync（只替换 sealing 模块内的引用，不改全局 os）。

### C-14 `ResourceKindRegistry` 的查询接口

- 固定为：
  - `get(name)`：未登记时返回 None；
  - `registry[name]`：未登记时抛 KeyError；
  - `name in registry`、`names()`、`items()`、`is_file_kind(name)`。
- 默认登记恰好是 5 类。
- 原测试在找不到查询接口时会 skip，现在改为必须通过。

### C-15 `check_resource_dag`

- 出现环时，错误的 `field` 是指向环上某个节点的 JSON Pointer `"/<节点>"`，按 RFC 6901 转义。
- 只作为被引用方出现、自身不是键的节点，也进入拓扑序。
- 结果与映射的插入次序无关。
- 空图返回 `[]`。

### C-16 `interpret_git_object_type`

- expected_type 只接受 commit 与 tree，其他值报 `E_COMPAT_UNSUPPORTED`。
- stdout 允许带一个结尾的 LF 或 CRLF；其他任何差异（多余空行、空格、空输出、非 bytes）都报 `E_GIT_OBJECT_TYPE`。

### C-17 两边原本就一致的裁决（写明以免下游另作解释）

- **`validate_plan_version`**：`allow_null` 默认为 False；`None` 报 `E_SCHEMA_TYPE`。
- **`resolve_existing_path_for_review`**：根目录不存在报 `E_PATH_ROOT`。参考实现报 `E_PATH_NOT_FOUND`，这里按 01-T2 规格改为 `E_PATH_ROOT`。
- **孤立代理项**：
  - 直接调用 `validate_business_path` / `validate_resource_ref` 时，业务路径中报 `E_PATH_SYNTAX`（参考实现报 `E_JSON_UNICODE`，这里按 01-T2 规格）；路径位于记录中时，P2 返工后整条记录先做 JSON 原生值检查，报 `E_JSON_UNICODE`（第 6.2 节）；
  - 其他记录字符串中报 `E_JSON_UNICODE`。
- **只有空白的输入**：`b" "` 报 `E_JSON_SYNTAX`，不算空输入。
- **`check_json_value` 的深度**：与 `strict_json_loads` 相同，64 层接受、65 层报 `E_JSON_LIMIT`。参考实现在这里允许 65 层。
- **`to_record()`**：孤立代理项替换为 U+FFFD，保证错误记录本身能通过 `check_json_value`。
- **`for_executor_dispatch`**：规格中“或 role==executor 且 for_executor_dispatch”这句化简后只看该标志。标志为 False 时，缺字段的 executor 上下文在结构上合法。P4 起标志为 True 时还要求 role 为 executor（C-04）。
- **`observation_kind="unknown"`**：必须在 unknown_reasons 中给出原因。
- **registry 参数**：`validate_run_context` 与 `validate_usage_observation` 接受可选的 registry；`validate_public_record` 必须给出 registry，并传给全部引用。

### 仍未实测或不在 01 范围

- **F029、F030**：写成 skip。原因见 01-D06：01 只做词法校验与静态解析，不做抗 TOCTOU 的受控访问；skip 不代表通过。
- **jsonschema 元校验**：本机未安装 jsonschema 且不得安装，已 skip。
- **Linux 与 macOS**：NOT_RUN。
- **导入时读取环境变量**：P2 返工后已可检测。F049 在导入前把 `os.environ` 换成记录读取的包装，A14 另用 AST 检查源码中不出现 `environ`/`getenv` 等名称；A14 反例证明探针能捕获写模式 open、建目录、起进程与读环境变量。
- **F017**：P2 返工改为 skip。它要求的“仅机器路径改变 → 语义快照不变”依赖 02 的语义投影（01-D05）；原断言改名为 `test_A03_snapshot_does_not_project_machine_fields`，skip 不代表通过。

### P2 返工（多视角复审后）

多视角复审（fidelity、json、paths、events-usage、tests-mutation 五个视角）提出的问题逐条处理如下。凡是改了行为的，都补了回归测试，测试方法名带对应的 F/A 编号。

**第一轮结果**：`Ran 245 tests`，`OK (skipped=4)`；跳过的是 F017、F029、F030 与 jsonschema 元校验。变异抽查：在临时副本中对复审列出的变异与本次新增规则做了 69 处反向改动，除 1 个等价变异外全部被测试发现（其中 1 个以超时挂起的方式被发现，见下文）。

#### 已实施的裁决

- **R-01 用量范围不明**（major）：provider 或 model 为 null 的范围与同一 run/role 下其他范围并存时报 `E_USAGE_SCOPE_UNKNOWN`；单独存在时计入但标为不完整。依据：4.3.8 末行“两个来源范围不明的观测 → E_USAGE_SCOPE_UNKNOWN 或待核对”。
- **R-02 严格 JSON 的检查时机**：去掉解析前按引号奇偶计数的文本预检查（它在“漏写反斜杠”这类单一文法故障下会把字符串里的括号当成嵌套，报 `E_JSON_LIMIT`），改为解析后按 json 确定的真实字符串边界计算深度；JSON Pointer 改为惰性渲染，消除长父路径下的二次方开销（major）。第 4 节如实写明第 5–10 步只是概念顺序。
- **R-03 共享容器与记录深度**：`check_json_value` 增加 `max_bytes` 下界预算，`stable_snapshot_bytes` 在生成输出前止损；三类记录先做整条记录的 JSON 原生值检查，payload 不再能比记录多一层，str 子类的 record_type 不再通过。
- **R-04 错误记录的 field**：截到祖先指针并在 reason 追加标记，不再输出以 `~` 结尾或误指向另一个键的指针；`details` 可按 UTF-8 编码。
- **R-05 控制字符**：按 Unicode Cc 理解设计文档 4.1.5 的“控制字符”，加入 C1（U+0080–U+009F）。这是对参考实现的收紧，只影响新入口（01-D09）。
- **R-06 名称碰撞与文件系统别名**（major）：`check_no_name_collisions` 检出目录前缀碰撞与“文件/目录同名”；物理层逐级核对拼写，拒绝 8.3 短名与大小写别名（本机实测 C: 卷启用了 8.3 名）。词法层是否直接拒绝 8.3 形式的分段，当时待裁决（R-P3，P4 已落实为词法层拒绝）。
- **R-07 设备名**：只做 ASCII 大小写折叠，不再把 `CON\u0131N$` 误报为设备名。
- **R-08 事件日志**：`out_of_order` 检出持久化顺序中的跳号；`recover_next_seq` 可核对 run_id；新增 `recover_append_state` 供崩溃后重建 state；`append_event` 检查 record_type 与 state 不变式，不再把重放误报成 `E_EVENT_GAP`。
- **R-09 结束证据**：01 只认识 `"success"`，其他结束证据的冲突为 null，不断言“没有冲突”；`process_exited=False` 与 exit_code 并存报 `E_SCHEMA_FIELDS`。
- **R-10 审核引用**：视图增加 `contract_approval_ref`（4.1.4 建议字段），只是新增键，可以按规划端意见撤回。
- **R-11 用量视图的组合场景**（major）：账单事件的重复投递随修订目标一起被替代，避免重复计费（第一轮写成“等价类整体被替代”，第二轮收窄，见 R-15）；整条修订分量检查币种；修订继承逻辑位置；累计序列回退、终止后又有累计视为冲突，未计入的观测列入 `ignored_usage_ids`；合计超过 2^53-1 报错；reported_cost 与 billing_source 必须一致（估算不能冒充实际费用）。
- **R-12 sealing**：最终名被目录占用报 `E_RESOURCE_CONFLICT`；文档写明 TOCTOU 前提、悬空链接的错误码、0600 只适用于 POSIX、发布后越界复查只能事后报告、read_sealed 的环境类 OSError 可能含本机路径。
- **R-13 验收映射**：F017 改为 skip（归 02）；A14 增加反例与环境变量检测。

#### 第二轮返工（P2 复审后续）

第二轮多视角复审（fidelity、paths、events-usage、tests-mutation）确认的问题逐条处理如下，每条都补了回归测试，测试方法名带对应的 F/A 编号。

**第二轮结果**：`Ran 254 tests`，`OK (skipped=4)`，跳过项与第一轮相同。在临时副本中逐一植入复审列出的变异（越界判定改回 `relative_to`、`usage_view` 改回“替代整个等价类”、S021、P144、Q025、Q027），每个都被对应的新测试发现；植入变异后失败的只有本次新增或扩展的用例，其余原有用例仍通过，与复审“变异存活”的结论一致。

- **R-14 越界判定按组件逐字比较**（blocker，paths）：`protocols._is_within` 与 `sealing._within` 原来都用 `PureWindowsPath.relative_to`，它按 `str.lower()` 比较。名称只在 `lower()` 下与根的某级祖先相同的根外兄弟目录（含 U+212A 等字符，或位于大小写敏感的 NTFS 目录中）会被当成根内。于是 `resolve_existing_path_for_review` 漏报越界，`seal_bytes` 把文件写到根外，`read_sealed` 读出根外文件。现改为共用的 `_is_within`：resolve 后根的组件必须是目标组件的逐字前缀；sealing 删除自己的 `_within`，经 `_PROTOCOL_NAMES` 取用同一实现。复审建议的第二层“根深度处祖先与根 samefile”核对没有加：两边组件逐字相同时，这一祖先与根就是同一个路径字符串，samefile 必然为真，不提供额外信息（已由 R-P9 / P4 第 5 轮更正：逐字比较只比较路径字符串，不核对对象身份；硬链接、挂载点与检查之后的替换列入已知不检测，见第 7 节清单）。回归测试：`test_A10_kelvin_sign_sibling_is_escape`、`test_A10_case_sensitive_directory_sibling_is_escape`（本机 fsutil 可用，已实测）、`test_A10_is_within_compares_components_exactly`（白盒，纯路径对象，与平台无关）、`test_A13_seal_and_read_reject_kelvin_sign_sibling`。第 7、15 节与 sealing 的 docstring 已改为写明判定依据与 TOCTOU 前提。
- **R-15 修订只替代明确指向的目标**（major ×4，fidelity 与 events-usage）：第一轮让修订替代“目标所在账单事件等价类的全部成员”，带来两个问题：同一账单事件的线性修订链 a←b←c 被误报为分叉；与目标数值不同、又不在链上的同账单事件观测被静默吞掉，视图仍标完整。现改为：先把“账单号相同、数值相同、修订目标相同”的观测归并为重复投递；修订只替代明确指向的目标及其重复投递；每条修订链代表链上全部观测的账单事件，代表同一账单事件的各链尾数值必须相同（相同视为重复，不同报冲突）。第 13.2 节第 3–5 步已改写并写明边界。回归测试：`test_A06_same_billing_event_revision_chain_takes_tail`（2 级、3 级链的全部到达顺序，链尾不带账单号，更正回原值，500 级长链）、`test_A06_billing_conflict_not_swallowed_by_revision`（冲突观测早于或晚于修订到达，修订带同一账单号、另一账单号或不带，全部报冲突；数值与修订后有效值相同的投递视为重复）、`test_A06_duplicate_revision_delivery_counted_once`（同一修订重复投递、漏掉 supersedes 的重复投递、整条修订重复投递；账单号不同或没有账单号的两条修订仍是分叉）。原有断言全部保留且通过。
- **R-16 read_sealed 只读一次**（major，tests-mutation S021）：实现本来就只读一次，缺的是测试。新增 `test_A13_read_sealed_reads_once_returns_verified_bytes`：白盒替换 `_read_all`，让第 2 次读取返回不同字节，断言恰好读 1 次、返回核验过的字节。
- **R-17 append_event 重放较早的 seq**（major，tests-mutation P144）：实现正确，缺测试。新增 `test_A11_F037_append_event_replay_of_older_seq_keeps_state`：追加到 seq=3 后重放 seq 1、2，断言返回 duplicate 且 state 完全不变；内容不同的重放报 `E_EVENT_REPLAY_CONFLICT` 且 state 不变；之后追加 seq 4 照常成功。
- **R-18 fixture 条目的 expected_ref 与 source_path**（major，tests-mutation Q025/Q027）：实现正确，缺测试。`test_A12_manifest_entry_structure` 的单一故障表增加 6 行：expected_ref 的 id 非法（`E_RESOURCE_FIELD`，`/expected/expected_ref/id`）、kind 未登记（`E_RESOURCE_KIND`）、不是对象（`E_SCHEMA_TYPE`）；source_path 为 `../outside\x.py`、`../x`、`tests\x.py`（`E_PATH_SYNTAX`，`/origin/source_path`）。另加一个合法 expected_ref 的正例。

#### 规划端裁决 R-P1–R-P8（已裁决，P4 落实）

裁决记录见 [decisions.md](decisions.md)“P2 复审遗留的规格裁决”。P2 第二轮返工时这些项只写明了现状；P4 按裁决改实现、补测试，并在正文对应小节写明。

| 编号 | 状态 | 结论 | 落实（正文位置） | 回归测试 |
|---|---|---|---|---|
| R-P1 | **已裁决** | `E_EVENT_*` 不再一律 retryable：只有可恢复读取的 `E_EVENT_GAP`、`E_EVENT_REPLAY_CONFLICT`、`E_PROTOCOL_INCOMPLETE`、`E_EVENT_RAW_REF_UNKNOWN` 与 `E_RESOURCE_INDEX_FAILED` 为 true；`E_EVENT_RAW_RANGE`、`E_EVENT_TYPE_UNKNOWN`、`E_EVENT_SOURCE`、`E_EVENT_EVIDENCE_MISSING` 为 false | 错误码表（第 3.2 节、C-02） | `test_A04_retryable_semantics`（逐码断言） |
| R-P2 | **已裁决** | executor_retry 的 attempt 由调用方传入受信分配器（旧 allocate_attempt，将来 07）给出的编号；必须 ≥ parent.attempt（相等表示同一 prepared attempt 的重新运行）；缺失 `E_CONTEXT_INCOMPLETE`，倒退 `E_CONTEXT_BINDING` | `derive_run_context`（第 5.2 节、C-04） | `test_F023_executor_retry_new_run_same_request`、`test_A08_executor_retry_requires_attempt`、`test_A08_derive_rejects_inapplicable_parameters` |
| R-P3 | **已裁决** | 词法层拒绝 8.3 短名形态的分段（基名 1–6 个非 `~` 字符 + `~` + 数字，基名总长 ≤ 8，可带 ≤3 字符扩展名，大小写不敏感），`E_PATH_RESERVED`（reason `windows_short_name_form`）。“基名总长 ≤ 8”与“前缀不含 `.`”是按 8.3 格式对裁决文字的精确化，避免误拒 `backup~2024.tar` 这类不可能是短名的名称。**P4 第 3 轮**：前缀改为允许含 `~`（Windows 对前缀含 `~` 的长名生成的短名，原文字漏掉），与本行裁决文字不同，待规划端确认，见“P4 第 3 轮”第 12 条 | `validate_business_path`（第 7 节）；物理层的别名核对保留为兜底 | `test_A10_windows_short_name_form_reserved`、`test_A10_filesystem_aliases_rejected`、`test_A13_seal_rejects_filesystem_aliases`、`test_A13_seal_temp_short_name_is_lexically_reserved` |
| R-P4 | **已裁决** | 拒绝 U+2028、U+2029 与双向控制字符 U+061C、U+200E、U+200F、U+202A–U+202E、U+2066–U+2069，`E_PATH_SYNTAX`（reason `line_separator_or_bidi_control`）；ZWNJ 等其他格式字符不拒绝 | `validate_business_path`（第 7 节） | `test_F025_line_separators_and_bidi_controls` |
| R-P5 | **已裁决** | 不增加 ANSI best-fit（WorstFit）严格 profile；Python 与 Git for Windows 用宽字符 API。限制已写明：把业务路径交给 ANSI API 程序的消费者必须自行复核 | 第 7 节“ANSI best-fit 字符不拒绝”、第 16 节 | `test_A10_ansi_best_fit_characters_not_rejected`（固定“不拒绝”） |
| R-P6 | **已裁决** | 接受并写明：`1e-400` → 0.0、整数 `-0` → 0（JSON 文法允许）、`-0.0` 保留；公共记录的数值字段都是整数，金额用十进制字符串 | 第 4 节 | `test_A03_underflow_and_negative_zero_integer` |
| R-P7 | **已裁决** | raw_refs 只能指向 raw-segment；其他 kind `E_RESOURCE_KIND`（reason `raw_ref_requires_raw_segment`） | `validate_raw_span` / `validate_run_event`（第 11 节） | `test_A12_raw_refs_only_reference_raw_segments`、`test_A09_schema_gaps_need_semantic_checks` |
| R-P8 | **已裁决** | 保留 `complete` 的含义（只表示序列一致，空日志仍为 true）；返回值增加 `event_count`；文档写明空日志不证明运行产生过事件，协议完整性由 `assess_stream_integrity` 与 04 判定 | `assess_event_log`（第 11 节、C-10） | `test_A11_event_log_binding_errors_and_empty`、`test_A11_event_log_event_count_and_keys` |

#### 变异抽查的说明

- 等价变异：把 final 范围的计入对象从 `finals[-1:]` 换成 `known[-1:]`。在“final 之后不得再有 cumulative、多个 final 数值必须相同”的新规则下，最后一条已知观测总是最后一个 final，两者等价，测试无法也无需区分。
- 去掉修订成环检查时，后续的逻辑位置计算会无限循环，测试以挂起的方式暴露问题（变异抽查按超时计为已发现）。第二轮返工后成环检查并入求修订深度的循环，去掉它同样会让该循环不终止。P4 起成环用例在子进程中运行，60 秒超时即判为失败，不再挂起（见下文 P4 第 29 条）。

### P4：裁决落实与复审遗留项处理

P4 落实规划端裁决 R-P1–R-P8（见上文“规划端裁决”），修复 fixtures 复审 major 问题在协议层的根因，并逐条处理第 2 轮协议复审中未返工的 30 个 minor 与 fixtures 复审的 9 个 minor。凡改了行为的都补了回归测试；测试 docstring 写明“P4”与复审视角或变异编号。

**结果**：`python tests/test_protocols.py` 为 `Ran 285 tests`、`OK (skipped=4)`，跳过项与 P2 相同（F017、F029、F030、jsonschema 元校验）；`python tests/test_codekit01_fixtures.py` 为 `Ran 33 tests`、`OK`。两个测试文件开头把 stdout/stderr 设为 UTF-8（errors=backslashreplace），中文的 skip 原因在 Git Bash 中可读。

**变异抽查**：在 tempfile 建的副本中逐一植入 53 个变异（R-P1–R-P8 与本节各项新规则的反向改动，以及第 2 轮复审列出的 P017、P105、P156、P157、P202、P251、P254、P256、Q001、Q002、Q012、Q016、Q017、Q022、Q032、Q043、Q045、M1、M2、M3、M5、M12、S027、S028、S102、S105），每个都被测试发现。P202（修订成环检查失效导致不终止）现在由子进程超时判为失败，而不是让测试挂起。
（P4 第 3 轮更正：这 53 个变异之外，第 3 轮复审又找出 P4 新规则与既有规则的一批存活变异——P06、X25、P10、X17、X19、P12、P13、M10、M11、M27、M30、X13、X23、S01——所以“P4 新规则的反向改动均被发现”不成立。它们在“P4 第 3 轮”中逐一补测或随规则调整处理。）

#### 行为与错误码变化清单（P4）

| 位置 | 变化前 | 变化后 |
|---|---|---|
| `ERROR_CODES` retryable | 全部 `E_EVENT_*` 为 true | 只有 GAP、REPLAY_CONFLICT、RAW_REF_UNKNOWN 与 `E_PROTOCOL_INCOMPLETE`、`E_RESOURCE_INDEX_FAILED` 为 true（R-P1） |
| `derive_run_context(executor_retry)` | attempt = parent.attempt+1，不接受参数 | attempt 必须由参数给出且 ≥ parent.attempt；缺失 `E_CONTEXT_INCOMPLETE`，倒退 `E_CONTEXT_BINDING`（R-P2） |
| `validate_business_path` | 8.3 短名形态、U+2028/U+2029、双向控制字符都接受 | 前者 `E_PATH_RESERVED`（R-P3），后两类 `E_PATH_SYNTAX`（R-P4）；物理层对 8.3 短名的拒绝因此提前到词法层 |
| `validate_raw_span` / `validate_run_event` | raw_refs 可引用任一已登记 kind；单独调用时不做 JSON 原生值检查 | 只能引用 raw-segment，否则 `E_RESOURCE_KIND`（R-P7）；单独调用时先做 JSON 原生值检查（`byte_end=2**60` 报 `E_INTEGER_RANGE`） |
| `assess_event_log` | 无 event_count；非 run-event 记录当作事件 | 增加 `event_count`（R-P8）与 `record_type_errors`；非 run-event 记录不进入 events |
| `recover_next_seq` / `recover_append_state` | 先报冲突/缺口/乱序，再报绑定/不可读 | 先报绑定（`E_CONTEXT_BINDING`）、记录类型（`E_SCHEMA_RECORD_TYPE`，新）、不可读（`E_SCHEMA_TYPE`），再报冲突与缺口 |
| `append_event` | 只按 len 核对 state 不变式 | 完整核对键集合（精确 int 1..last）与值类型（bytes），否则 `ValueError` |
| `validate_public_record` | 先路由；JSON 层故障报路由码 | 先做整条记录的 JSON 原生值检查，与直接调用得到同一个码 |
| `validate_run_context(for_executor_dispatch=True)` | 不检查 role | role 必须是 executor，否则 `E_SCHEMA_FIELDS`（`/role`） |
| `validate_fixture_manifest_set`、run.prepared 载荷校验器 | 没有字节下界预算 | 按 1 MiB 字节下界止损（共享结构报 `E_JSON_LIMIT`） |
| `build_run_dimensions` | cancelled 为 `cancelled_by is not None` | 三态，新增参数 `cancellation_checked`；规则修订 v1 → v2 |
| `usage_view` | provider 为 null 的同账单号观测直接相加；空输入的费用为 `{}` | 前者 `E_USAGE_SCOPE_UNKNOWN`（`billing_event_without_provider_repeated`）；后者两类费用各有一个不完整的 unknown_currency 组 |
| `validate_fixture_manifest_entry` / `_set` | 能力声明只约束 origin.class=synthetic；captured 只能配 captured_raw/redacted_raw | 能力声明规则作用于全部条目；captured 可配 normalized_event（要求 generator_revision）；applied=true 要求 length_changed；captured_raw 不能 applied；negative 不能配采集表示；清单级要求声明 legacy_ 能力的负例从 legacy 条目派生。reason `captured_requires_captured_or_redacted_raw` 改名为 `captured_requires_captured_redacted_or_normalized` |
| `seal_bytes` | — | 行为不变；写明失败时残留本次新建的空父目录（`SEALING_LIMITATIONS` 增加一项） |

fixture 的变化：`tests/test_codekit01_fixtures.py --write` 重新生成了 manifest.json 与协议负例（生成修订 `codekit01-protocol-fixtures-v3`），共 169 条、协议负例 122 个。legacy 预期文件没有变化（`tests/codekit01_legacy.py --check`：32 checks, 0 differ），符合“legacy 期望只能由旧实现生成、不因协议改动而变化”。

#### fixtures 复审 major：能力声明的协议层根因

- **问题**：产品入口只在 origin.class=synthetic 时拒绝真实兼容声明；stub 生成的流（legacy 类）与负例（negative 类）的 representation 都是 synthetic_fixture，却可以在 proves 中声称 real_cli_compatibility、vendor_protocol 而不被发现。
- **处理（采纳，改产品规则）**：能力声明按来源类别与表示判定，作用于全部条目（第 14.2 节第 4 步）；清单级增加 legacy 派生规则（第 14.3 节）。`real_cli_compatibility`、`vendor_protocol` 只允许 captured + captured_raw/redacted_raw；`legacy_dispatch_behavior` 只允许 legacy + legacy-judgment。
- **负例 fixture**：`negative-protocol-fixture-manifest-claims-legacy-stub-claims-real-cli-compatibility` 改由产品入口拒绝（reason `real_compatibility_claim_requires_captured_raw`）；新增 `…-legacy-stub-claims-vendor-protocol`（产品入口）与 `…-legacy-stub-claims-unlisted-legacy-capability`（测试层白名单规则，产品入口接受 legacy 类的 legacy_ 能力）。
- **测试**：`test_A12_real_compatibility_claims_by_origin_and_representation`、`test_A12_negative_legacy_claims_require_legacy_base`；fixtures 侧 `ManifestTests.test_claim_rule_rejects_real_and_unlisted_legacy_claims` 逐项断言产品入口与测试层规则各自的 reason。复审的复现实验（改生成器让 stub 条目声称 real_cli_compatibility 再 `--write`）现在在生成时就被 `validate_fixture_manifest_set` 拒绝。
- 测试层规则 `check_synthetic_fixture_claims` 保留为本清单的额外约定：synthetic_fixture 条目连 legacy_dispatch_behavior 也不得声明，legacy_ 前缀只放行与旧实现差分入口对应的白名单。

#### 第 2 轮协议复审的 minor（30 条）

编号按复审文件中 minor 出现的顺序。“采纳”表示已改实现或补测试；“部分采纳”写明未采纳部分的理由。

| # | 视角 | 问题 | 处理 | 回归测试 |
|---|---|---|---|---|
| 1 | fidelity | C-07 声称两个入口同码，JSON 层故障不成立；validate_raw_span 单独调用与嵌入事件时码不同 | 采纳：`validate_public_record` 路由前做 JSON 原生值检查；`validate_raw_span` 单独调用先做同样检查；C-07 更正 | `test_A09_public_entry_and_direct_validators_agree`、`test_A09_record_type_must_be_exact_str` |
| 2 | fidelity | for_executor_dispatch 不检查 role | 采纳：role 必须是 executor，`E_SCHEMA_FIELDS`（`/role`），与 C-04 一致 | `test_A08_executor_dispatch_requires_executor_role` |
| 3 | fidelity | known_optional 与 ignorable_optional 等价，测试 docstring 与实现不符 | 部分采纳：文档写明 01 中两者等价、区别由 04 定义，更正 docstring 并固定等价。**不扩展接口**：“内容是否被理解”由 04 的解析层产生，01-D07 把真实类型与结束判定移交 04，在 01 预设数据形状会限制 04 | `test_A11_optional_classifications_equivalent`、`test_A11_stream_integrity_classification` |
| 4 | fidelity | 来源规则比 4.3.3 宽 | 部分采纳：captured_raw 不能 applied；applied 要求 length_changed；negative 不能配采集表示、不能声称真实兼容；captured 可配 normalized_event（要求 generator_revision）。**不增加“是否保留协议结构”字段**：这是封闭结构的格式变更，全部清单与生成器都要改，需要规划端出新规格；空缺已写入第 14.2 节 | `test_A12_redaction_metadata_and_representation_rules`、`test_A12_provenance_rule_details`、`test_A12_real_compatibility_claims_by_origin_and_representation` |
| 5 | json | 同第 1 条（两个入口码不同） | 采纳，与第 1 条同一处修改 | 同第 1 条 |
| 6 | json | validate_fixture_manifest_set 与 run.prepared 载荷校验器没有字节预算 | 采纳：两处都按 1 MiB 下界止损 | `test_A03_record_validators_budget_shared_dag` |
| 7 | json | 快照 1 MiB 的两道防线没有边界测试 | 采纳 | `test_A03_snapshot_limit_after_serialization`、`test_A03_lower_bound_constants_do_not_reject_valid_values` |
| 8 | json | 记录校验的字节预算没有测试（M12） | 采纳 | `test_A03_record_validators_budget_shared_dag`（8 个入口） |
| 9 | paths | 以临时文件的短名 CODEKI~1.TMP 为业务名时 os.link 命中临时文件自己 | 采纳，由 R-P3 解决：这类名称在写入前以 `E_PATH_RESERVED` 拒绝。复审建议的 samefile 重试没有加：R-P3 之后能命中临时文件的只剩大小写别名，需要猜中 128 位随机名，且即使发生也由逐级拼写核对报 `E_PATH_COLLISION`，不会误发布（已由 R-P9 / P4 第 5 轮更正：这是没有并发替换时的已检测情形；检查之后的替换、同一账户的其他进程篡改列入已知不检测，见第 15 节清单） | `test_A13_seal_temp_short_name_is_lexically_reserved` |
| 10 | paths | 失败后残留新建的空父目录 | 采纳“写明语义”：不回滚，因为并发写入者可能正要使用同一目录，8.4 不允许在不确定时清理；docstring、`SEALING_LIMITATIONS` 与第 15 节已写明 | `test_A13_seal_failure_leaves_only_empty_new_parents` |
| 11 | paths | `\\.\`、`//./COM1`、`//?/C:/x`、`::$DATA` 等写法没有测试 | 采纳 | `test_F024_absolute_drive_unc_backslash`、`test_F026_reserved_device_names_and_ads` |
| 12 | events-usage | append_event 只按 len 核对不变式 | 采纳：完整核对键集合与值类型（每次 O(已提交条数)，内存参考模型可接受） | `test_A11_append_event_state_invariant_checked_fully` |
| 13 | events-usage | 恢复函数的错误码随故障记录位置变化 | 采纳：先报记录本身的缺陷 | `test_A11_recovery_error_code_independent_of_position` |
| 14 | events-usage | 恢复函数不检查 record_type | 采纳：`record_type_errors`，恢复报 `E_SCHEMA_RECORD_TYPE` | `test_A11_event_log_rejects_non_event_records` |
| 15 | events-usage | provider 为 null、同账单号的观测相加成高估 | 采纳（规格问题，取不猜、拒绝聚合的一侧，与 4.3.8 末行一致）：`E_USAGE_SCOPE_UNKNOWN` | `test_A06_billing_event_without_provider_not_summed` |
| 16 | events-usage | 没有取消信息时 cancelled=False | 采纳（规格冲突，按 4.1.4“未知保持未知”）：三态，新增 `cancellation_checked`，规则修订升为 v2 | `test_A05_cancel_is_not_success` |
| 17 | events-usage | 空输入时费用为 `{}`，没有不完整标记 | 采纳：两类费用各有一个不完整的 unknown_currency 组 | `test_A06_empty_view_is_incomplete` |
| 18 | tests-mutation | index_commit 不可调用、传副本没有测试（S102/S105） | 采纳 | `test_A13_seal_index_commit_argument_checks` |
| 19 | tests-mutation | 拓扑序与插入次序无关没有真正测到（P105） | 采纳 | `test_F036_referenced_only_nodes_and_determinism` |
| 20 | tests-mutation | to_record 的 phase/reason/hint 截断、代理项清除、retryable 类型没有测试 | 采纳 | `test_A04_error_record_text_limits_and_retryable_type` |
| 21 | tests-mutation | str 子类键没有测试（P017） | 采纳 | `test_F020_non_string_keys` |
| 22 | tests-mutation | approval_ref、cancelled_by 的假值没有测试（P156/P157） | 采纳 | `test_A05_verdict_approval_integration_distinct`、`test_A05_cancel_is_not_success` |
| 23 | tests-mutation | exit_code 为 bool 没有测试（Q016） | 采纳 | `test_A05_exit_codes_must_be_exact_int` |
| 24 | tests-mutation | UTC 转换溢出没有测试（Q022） | 采纳 | `test_A11_format_utc_conversion_overflow` |
| 25 | tests-mutation | 派生前校验 parent 没有测试（Q045） | 采纳 | `test_A08_derive_validates_parent_first` |
| 26 | tests-mutation | 口径分布的 unknown 桶没有测试（Q043） | 采纳 | `test_F046_cache_and_reasoning_not_added` |
| 27 | tests-mutation | 用量字符串长度上限没有边界测试（Q032） | 采纳：provider、model、billing_event_id 各一对，并与迷你 Schema 校验器一致 | `test_A06_usage_string_length_bounds` |
| 28 | tests-mutation | 祖先是普通文件、read_sealed 读目录两条映射没有测试（S027/S028） | 采纳 | `test_A13_seal_and_read_non_directory_ancestor_and_directory_target` |
| 29 | tests-mutation | 成环检查失效时测试挂起（P202） | 采纳：成环用例改在子进程中运行，60 秒超时判为失败 | `test_A06_revision_cycle_detected_within_timeout` |
| 30 | tests-mutation | usage_view 的 Sequence 检查、run.prepared 校验器的类型检查没有测试（Q017/Q012） | 采纳 | `test_A06_usage_view_requires_sequence`、`test_A11_run_prepared_validator_called_directly` |

#### fixtures 复审的 minor（9 条）

这 9 条中有 8 条在 P3 返工（兼容矩阵修订 2）时已经处理，P4 逐条核实后记录如下；第 2 条随产品规则落地再次更新。

| # | 问题 | 处理 | 核实依据 |
|---|---|---|---|
| 1 | 3 个协议负例同时改变不止一个条件；只断言 code 与 field | P3 已处理：3 个变体改为单一故障，`NegativeSpec` 增加 reason 并逐个断言。P4 把 synthetic-relabelled-captured 的期望 reason 改为新名称 | `NegativeTests.test_each_negative_yields_exactly_manifest_code` |
| 2 | 矩阵两格的“拒绝”不符合定义 | P3 已改为“只读标签（产品入口未强制）”。P4 产品规则落地后，这两格改为“拒绝”，写明产品错误码与 reason（矩阵修订 3） | compatibility-matrix.md 第 2 节 |
| 3 | 矩阵把测试辅助的逐行判断写成新入口的支持 | P3 已处理：写明是测试辅助，不是产品入口 | compatibility-matrix.md 第 2、4 节 |
| 4 | 结论摘要第 3 条缺限定语 | P3 已处理：限定为“在 P3 fixture 中”，并列出 D-20、D-23 | compatibility-matrix.md 第 0.2 节 |
| 5 | 计数口径不对 | P3 已处理；P4 按新计数更新（协议负例 122、清单 169 条） | `NegativeTests.test_negative_counts_by_group` |
| 6 | 默认测试不重跑 stub、不查 cwd 占位 | P3 已处理：`StubTests` 两项（重跑只在 Windows） | 本次运行通过 |
| 7 | “核对工作区字节与 blob 相同”的描述没有对应检查 | P3 已处理：`write_legacy_contracts` 断言，`--check` 输出每个来源文件的比较结果 | `codekit01_legacy.py --check`：32 checks, 0 differ |
| 8 | 差分测试实质上是实现字节门禁 | P3 已处理：字节门禁拆成 `test_legacy_implementation_bytes_are_source_revision`，差分只比较 cases 并列出不同的 case_id 与字段 | `DifferentialTests` |
| 9 | 取不到 git 或 a4fa199 时跳过、退出码仍为 0 | P3 已处理：默认判为失败，只有 `CODEKIT01_ALLOW_NOT_RUN=1` 时记为 NOT_RUN | `not_run_or_fail` |

### P4 第 3 轮：第 3 轮复审的逐条处理

第 3 轮复审（fidelity、json、paths、events-usage、tests-mutation 五个视角）共 32 条：major 6 条、minor 26 条。每条都先在本机复现，再修复；blocker/major 与存活变异都补了断言。新增与修改的测试在 docstring 中写明“P4 第 3 轮”与复审视角或变异编号。编号按复审清单的顺序。

**结果**：`python tests/test_protocols.py` 为 `Ran 306 tests`、`OK (skipped=4)`（跳过项与 P4 相同：F017、F029、F030、jsonschema 元校验）；`python tests/test_codekit01_fixtures.py` 为 `Ran 36 tests`、`OK`。依赖 symlink、junction、8.3 短名与 `fsutil file setshortname` 的新用例在本机都实际运行，没有跳过。

**fixture 的变化**：生成修订升为 `codekit01-protocol-fixtures-v4`。`python tests/codekit01_legacy.py --write-expected` 重算三份预期文件：`legacy-contracts.json`、`legacy-events.json` 字节不变，`legacy-new-strict.json` 中两条 JSONL 文法错误的 reason 由带行列号改为 `syntax_error`（该文件以当前 protocols.py 重算，本来就随协议变化）。`python tests/test_codekit01_fixtures.py --write` 重新生成 manifest：171 条（协议负例 124 个），已有负例的字节全部不变，只新增 2 个负例（`vendor-event/role-null`、`fixture-manifest-claims/legacy-stub-claims-uppercase-real-cli-compatibility`）；5 个已有负例的期望随协议改动更新（`json-trailing-second-document` 的 reason，`json-nan`、`json-negative-infinity`、`json-overflow-1e10000`、`json-integer-out-of-range` 的 field 由 null 改为 `/seq`）。`python tests/codekit01_legacy.py --check`：`32 checks, 0 differ`。

**变异抽查**：在 tempfile 建的副本中逐一植入 33 个变异（本轮每项修复的反向改动，以及复审列出的 X13、X17、X19、X23、X25、P06、P10、P12、P13、M10、M11、M27、M30、S01），用两份测试运行。除下面 2 个等价变异外全部被发现：

- M08b（环检查只在深度未超限时做）：深度超限处的迭代环检测（第 10 条）会在同一位置、以同一 field 报 `E_JSON_CYCLE`，两者等价。
- P10（清单级 legacy 派生规则允许 negative 作 base）：第 22 条的新规则先于它拒绝“负例从负例派生”，这条分支已不可达，两者等价。

#### 逐条处理

| # | 视角 | 严重度 | 问题 | 处理 | 回归测试 / 变异 |
|---|---|---|---|---|---|
| 1 | fidelity | major | 同一分段内的链接链（根内链接 → 根外链接 → 根内目标）被接受，“经根外绕回根内同样越界”的声明夸大 | 采纳（a）：新增共用的 `_check_link_hops`，对每一级用 lstat/readlink 逐跳展开，链上任一个链接对象位于根外即 `E_PATH_ESCAPE`（`link_hop_outside_trusted_root`）；`resolve_existing_path_for_review`、`seal_bytes`、`read_sealed` 都调用（sealing 经 `_PROTOCOL_NAMES` 取用）。第 7、15、16 节与 docstring 改写。（已由 R-P9 / P4 第 5 轮更正：前一句是被取代的绝对表述。现按“已检测的情形”表述：逐跳展开时遇到的链接对象，若它所在目录解析后的真实路径不在根内，报 `E_PATH_ESCAPE`；这是静态审阅 + 纵深防御，不是安全访问保证，已知不检测的情形见第 7 节清单） | `test_A10_single_segment_link_chain_through_outside_is_escape`、`test_A13_seal_and_read_reject_link_chain_through_outside`；M01、M01b 被发现 |
| 2 | fidelity | minor | vendor 事件可以 role=null 绕过角色绑定 | 采纳，与第 15 条同一处修改 | 同第 15 条 |
| 3 | fidelity | minor | `assess_event_log` 的参照 run_id 是非法字符串时，同样非法的记录被判为一致 | 采纳：参照值不是合法 run id（非 str 或不符合语法）时每条可读记录都记为 binding_errors | `test_A11_event_log_run_id_parameter`（"garbage"、"run-x"、大写、尾随换行、空串）；M03 |
| 4 | fidelity | minor | `E_JSON_SYNTAX` 的 reason 含行列号，与“reason 固定”矛盾，fixture 锁定了位置 | 采纳（a）：reason 固定为 `syntax_error`，位置移到 hint；第 3.1 节写明 hint 的内容；负例 `json-trailing-second-document` 与 `legacy-new-strict.json` 随之更新 | `test_F011_syntax_reason_is_fixed_position_in_hint`；M04（两份测试都发现） |
| 5 | fidelity | minor | 错误码表把悬空链接祖先、祖先是普通文件写成三个函数都报 `E_PATH_RESOLUTION_FAILED` | 采纳（文档）：该行标注“仅 seal_bytes”，`E_PATH_NOT_FOUND`、`E_RESOURCE_MISSING` 两行补上对应情形 | 既有 `test_A13_seal_and_read_non_directory_ancestor_and_directory_target`、`test_A10_dangling_links_not_found` |
| 6 | fidelity | minor | 第 7 节把保留名检查写成在全部分段的语法检查之后，与实现不符 | 采纳（改文档）：按实现写明“按分段依次，每段先语法、再保留名”，并注明多缺陷不承诺首错；docstring 同步。不改实现：两种顺序都合规，改实现会改变现有多缺陷输入的结果而没有收益 | 文档示例 `NUL/a.`、`ABCDEF~1/a.`、`a./NUL` 已在本机复现 |
| 7 | fidelity | minor | `stable_snapshot_bytes` 先检查值、后检查根类型，与附录 B.2 参考实现的错误码不同且未登记 | 采纳（恢复参考实现顺序）：先检查根的 type 是否精确为 dict，再检查值。先查根类型不遍历任何内容，比原先“先按字节预算止损”更省 | `test_A03_snapshot_root_type_checked_before_values`；M06 |
| 8 | json | minor | `derive_run_context` 先 deepcopy 再校验，过深或不可拷贝的 contract_ref 漏出 RecursionError/TypeError，并在校验前执行调用方的 `__deepcopy__` | 采纳：先把原对象放进派生结果调用 `validate_run_context`，通过后再深拷贝；第 5.2 节写明 | `test_A08_derive_validates_contract_ref_before_copy`（5000 层、100000 层、Lock、生成器、dict 子类 × new_goal/rework，断言与直接校验同码同 field，且 `__deepcopy__` 未被调用）；M07 |
| 9 | json | minor | 同第 4 条（reason 不是固定文字） | 采纳，与第 4 条同一处修改 | 同第 4 条 |
| 10 | json | minor | 深度检查先于环检查，环长超过剩余深度时报 `E_JSON_LIMIT` | 采纳（b）：环先于深度判断；深度超限处另做一次不限深度的迭代环检测（每个容器只访问一次），有环报 `E_JSON_CYCLE`，只有过深而无环才报 `E_JSON_LIMIT`；第 4 节写明 | `test_F020_long_cycles_are_cycles_not_limits`（L=1、2、63、64、65、100、500 的 list/dict 环，check_json_value、快照、事件 payload；过深无环与深共享结构仍为 LIMIT）；M08 被发现，M08b 等价（见上） |
| 11 | json | minor | 严格解析的 `E_JSON_NON_FINITE` / `E_INTEGER_RANGE` 不带 field，与 `check_json_value` 不一致 | 采纳（a）：解析钩子返回内部哨兵，`_materialize` 按文档顺序遍历时带指针报告；超长整数仍按位数判定。第 4 节“检查时机”与多缺陷示例改写（`{"a":1,"a":NaN}` 现在报重复键，`[1e400,]` 现在报文法错误）；4 个数值负例的期望 field 改为 `/seq` | `test_A04_numeric_errors_carry_pointer`、`test_A04_multi_defect_examples_in_document_order`；M05（两份测试都发现） |
| 12 | paths | major | 裁决 R-P3 的形态定义（前缀不含 `~`）漏掉 Windows 真实生成的一类短名（`~$DOCU~1.DOC`、`A~BCDE~1.TXT`、`~AGENT~1`、哈希形态 `~~1BC3~1.MD`），多处文档称“自动生成的 8.3 短名已在词法层拒绝”不成立 | 采纳方案一：前缀改为 1–6 个非 `.` 字符（允许含 `~`），基名总长仍 ≤ 8。理由：R-P3 的目的是防止别名绕过只按字符串比较的保护路径；方案二只改文档，会把一类真实生成的别名留给下游，而下游（03 的保护范围）正是 R-P3 的立论对象。代价：`a~b~1`、`x~y~2.txt` 这类基名 ≤ 8、前缀含 `~` 的名称也被拒绝（保守方向）。**这改变了裁决 R-P3 的文字（“1–6 个非 `~` 字符”），decisions.md 不在本轮可写范围内，需规划端确认并修订 R-P3 的文字**。另按建议增加黑盒用例：`.~agentconfig` 的自动短名 `~AGENT~1` 在三个入口都报 `E_PATH_RESERVED`；物理层兜底改用手工设置、不含 `~` 的短名（`fsutil file setshortname`）黑盒验证三个入口都报 `E_PATH_RESOLUTION_FAILED`，替换“黑盒无法到达物理层”的说法；`test_A13_seal_rejects_filesystem_aliases` 的 docstring 已更正 | `test_A10_windows_short_name_form_reserved`（扩展）、`test_A10_generated_short_names_with_tilde_prefix_reserved`（GetShortPathNameW 实测）、`test_A13_short_name_aliases_rejected_by_all_entries`、`test_A10_manual_short_name_alias_black_box`；M09（改回“前缀不含 ~”）被发现 |
| 13 | paths | minor | 扩展名上限 3 没有“不误伤”一侧的边界测试（放宽到 4 时测试全过） | 采纳：接受列表加入 `notes~1.json`、`ABCDEF~1.JSON`、`PROGRA~1.HTML`、`file~2.yaml`，拒绝列表加入 `ABCDEF~1.JSO`；另加基名 9 个字符的 `~~~~~~~~1`、`a~b~c~d~1` | `test_A10_windows_short_name_form_reserved`；M10、M10b（去掉基名 ≤ 8 检查）被发现 |
| 14 | paths | minor | 生成模式的写入护栏只做字符串前缀比较，含 `..` 或反斜杠的路径可写出允许前缀甚至仓库 | 采纳：新增 `_check_write_target`（先 `validate_business_path`，再按解析后的真实路径逐组件确认位于仓库根下对应的允许目录；目标已存在且是链接或非普通文件时拒绝）；`write_all` 在写任何文件之前先检查全部待写路径 | `GeneratorGuardTests.test_guard_rejects_paths_outside_allowed_prefixes`、`test_guard_rejects_linked_directory_leaving_allowed_prefix`（只调用检查函数，不写文件） |
| 15 | events-usage | major | vendor 事件 role=null 时结构校验与 context 绑定都通过，脱离角色绑定；第 16 节记为无缺口 | 采纳：vendor 事件 role 必须非空，否则 `E_SCHEMA_FIELDS`（`/role`，`vendor_event_requires_role`），不论是否给出 context（JSON Schema 允许 null，这是 Schema 之外的领域检查）；第 11、16、18 节改写。新增负例 `negative-protocol-vendor-event-role-null` | `test_A11_vendor_event_requires_role`、`test_A09_schema_gaps_need_semantic_checks`（新增一行）；M02（两份测试都发现） |
| 16 | events-usage | major | usage_view 第 5b 步只看链尾自己的账单号，provider 为 null 时被修订观测的同账单号重投与修订一起计入（220 而非拒绝） | 采纳：5b 与第 5 步同一口径，一条修订链代表链上全部成员（provider 为 null）的账单号；第 13.2 节删去“修订链只留链尾，不受影响” | `test_A06_billing_event_without_provider_uses_whole_revision_chain`（复审两个变体及其组合，provider 已知时的 120 对照）；M11 |
| 17 | events-usage | minor | 5b 的键含 (request, run, role)，null provider 跨 run/role 直接相加，比 provider 已知（报冲突）更宽松 | 采纳：只按 billing_event_id 分组，跨 run、role、request 都报 `E_USAGE_SCOPE_UNKNOWN`。原测试 `other_run` 断言 200 是按旧规则写的，现改为断言报错——这是有意收紧规则，不是削弱断言；同时加 provider 已知时的 `E_USAGE_CONFLICT` 对照 | `test_A06_billing_event_without_provider_not_summed`；M11b、M11c 被发现 |
| 18 | events-usage | minor | cumulative/final 最后一条的字段为 null 时，此前已证明的累计值整体丢失（0，费用组消失） | 采纳：计入观测的 null 字段取序列中此前最后一个已知值作为下界，标不完整、unknown_count+1；费用按序列已校验的唯一币种归组。第 13.2 节写明 | `test_A06_cumulative_null_field_keeps_known_lower_bound`；M12、M12b、M12c |
| 19 | events-usage | minor | 第 13.2 节把“没有任何可计入的观测”的形状写成只有空输入才有的形状 | 采纳（文档）：改为“输入为空（没有任何有效观测）时”，另写明只含 unknown 观测时的形状 | `test_A06_only_unknown_observations_shape` |
| 20 | events-usage | minor | `assess_stream_integrity` 中未登记的必需类型永远得不到 complete，配置错误被静默掩盖 | 采纳（拒绝，不隐式视为 known_required）：`E_SCHEMA_FIELDS`（`/required_kinds/<i>`，`required_kind_not_classified`）；第 11 节与 docstring 写明。拒绝而不是自动补登记，因为必需类型的分类（是否需要被理解）应由 04 明确给出 | `test_A11_required_kinds_must_be_classified`；M13 |
| 21 | tests-mutation | major | 能力声明按精确名称与前缀判定，大小写与连字符变体能绕过来源规则（产品入口与测试层规则都被绕过） | 采纳：产品入口按封闭词法 `[a-z][a-z0-9_]{0,127}` 拒绝（`E_SCHEMA_FIELDS`，`claim_syntax`，proves 与 does_not_prove 都适用）；测试层 `check_synthetic_fixture_claims` 先按 ASCII 小写化、`-` 归一为 `_` 再判定。第 14.1 节写明词法。新增负例 `…-legacy-stub-claims-uppercase-real-cli-compatibility` | `test_A12_claim_lexicon`（stub、negative、synthetic、captured × 10 种变体，128/129 边界，整份清单）、fixtures 侧 `ManifestTests.test_claim_spelling_variants_rejected`；M14（两份测试都发现） |
| 22 | tests-mutation | minor | 产品入口只拒绝负例自引用，链式派生与二元派生环都被接受 | 采纳：清单级要求 negative 的 derived_from 目标不是 negative（`negative_must_derive_from_valid_sample`，field 为 `/entries/<i>/origin/derived_from`）；按来源类别判定。第 14.3 节与第 18 节写明 | `test_A12_negative_cannot_derive_from_negative`（二元环、链式、前向引用）；M15 |
| 23 | tests-mutation | minor | 没有“字典相等、字节不同”的重放用例（X23 存活） | 采纳（补测）：`{"x":1}`/`{"x":true}`、`1`/`1.0`、`0`/`false` 三组，断言 assess_event_log、recover_next_seq、recover_append_state、append_event | `test_F038_dict_equal_but_bytes_different_is_conflict`；X23 |
| 24 | tests-mutation | minor | 真实兼容声明规则中的 `origin.class=captured` 条件没有被固定（P06、X25 存活） | 采纳（补测）：legacy + captured_raw、legacy + redacted_raw 分别声称 real_cli_compatibility、vendor_protocol、real_pi_stream、vendor_usage_totals、real_x、vendor_x，断言 reason | `test_A12_real_compatibility_claims_by_origin_and_representation`；P06、X25 |
| 25 | tests-mutation | minor | legacy → negative → negative（后者声称 legacy_ 能力）的链没有测试（P10 存活） | 采纳（补测，按第 22 条的新 reason）：该链现在先由 `negative_must_derive_from_valid_sample` 拒绝。P10 因此成为等价变异（见上） | `test_A12_negative_legacy_claims_require_legacy_base`（新增链式用例） |
| 26 | tests-mutation | minor | R-P3 的两条边界（扩展名 ≤ 3、前缀不含 `~`）没有被固定（M10、M11 存活） | 部分采纳：扩展名边界按第 13 条补测（M10 被发现）。**前缀部分不按建议把 `a~b~1`、`x~y~2.txt` 加入接受列表**：第 12 条已把“前缀允许含 `~`”定为新规则（M11 的变异体正是新实现），这两个名称改列入拒绝列表；把规则改回“前缀不含 `~`”的反向变异 M09 被发现 | `test_A10_windows_short_name_form_reserved` |
| 27 | tests-mutation | minor | stream 为 file 时只能引用 raw-segment 的规则没有 file 流用例（X17 存活） | 采纳（补测）：对 stdout、stderr、file 三种 stream，单独调用与嵌在事件中两种入口都断言码、field 与 reason | `test_A12_raw_refs_only_reference_raw_segments`；X17 |
| 28 | tests-mutation | minor | synthetic 声明前缀型能力时只断言 code 与 field，synthetic 专用规则可被删弱（X19、P12） | 采纳（补测）：`test_A12_provenance_rule_details` 的前缀声明循环与 `test_F043_synthetic_cannot_claim_captured` 的声明循环都断言 reason 为 `synthetic_cannot_prove_real_compatibility`；F043 的表示循环也断言 field 与 reason（redacted_raw 按检查顺序先报 `redacted_raw_requires_applied_redaction`，第 14.2 节写明顺序） | 同左；X19、P12 |
| 29 | tests-mutation | minor | `captured_requires_source` 没有“只有 source_path”的对照，负例只断言 code（P13 存活） | 采纳（补测）：增加 source_path-only 负例，该用例的全部 E_PROVENANCE_CLAIM 都断言 field 与 reason，并加“source_path + source_test_id”正例 | `test_A12_captured_and_redacted_entries`；P13 |
| 30 | tests-mutation | minor | 恢复函数文档承诺的全序没有多故障测试，且与“多缺陷不承诺首错”冲突（M27、M30 存活） | 采纳选项 1：保留全序承诺，补多故障用例（相邻两类缺陷的每一对、两种先后，以及冲突+缺口、缺口+乱序）；第 3.2 节写明恢复函数是“多缺陷不承诺首错”的明确例外，第 11 节与 docstring 同步 | `test_A11_recovery_multi_fault_order_is_fixed`；M27、M30 |
| 31 | tests-mutation | minor | 5b 的键去掉 role 的变异存活（X13） | 随第 17 条处理：实现改为只按 billing_event_id 分组（X13 的变异体方向成为新规则），`other_role` 用例断言 `E_USAGE_SCOPE_UNKNOWN`；把 run/role 加回键的反向变异 M11b、M11c 被发现 | `test_A06_billing_event_without_provider_not_summed` |
| 32 | tests-mutation | minor | seal_bytes 第 6 步“发布后复查”没有测试（S01 存活） | 采纳（补测，白盒）：替换 sealing 模块内的 os 引用，让 os.link 改为在最终名处创建指向根外文件的 symlink；断言 `E_PATH_ESCAPE`（`resolved_outside_store_root`）、不调用 index_commit、链接不删除、临时文件已删除 | `test_A13_seal_post_publish_escape_is_reported`；S01 |

#### 需要规划端确认的事项

- **裁决 R-P3 的文字**（第 12 条）：实现与本文已按“前缀允许含 `~`”执行；decisions.md 中 R-P3 仍写“基名 1–6 个非 `~` 字符”，需规划端确认后修订（本轮不可写 decisions.md）。若规划端改选方案二（维持原裁决），需要把 `_SHORT_NAME_RE` 改回 `[^~.]`、把第 7 节改为“只拒绝前缀不含 `~` 的短名形态”并登记剩余的别名类别，`test_A10_windows_short_name_form_reserved` 与 `test_A10_generated_short_names_with_tilde_prefix_reserved` 相应调整。
- 其余各条都在 01 的职责与已有裁决范围内处理，没有新的跨模块决定。

### P4 第 4 轮：第 4 轮复审的逐条处理

第 4 轮复审共 5 条，都是 major：fidelity 视角 1 条，paths 视角 2 条，events-usage 视角 1 条，tests-mutation 视角 1 条。每条都先在本机复现（tempfile 建的目录，用后删除），再修复并补断言。5 条都成立，没有不采纳的条目；其中 3 条的做法与建议不同，理由写在对应条目中。第 1、2 条描述的是同一个缺陷（`..` 的语义），合并处理。新增测试的 docstring 写明“P4 第 4 轮”与复审视角。

**结果**：
- `python tests/test_protocols.py`：`Ran 316 tests`、`OK (skipped=4)`。跳过项与前几轮相同：F017、F029、F030 与 jsonschema 元校验。
- `python tests/test_codekit01_fixtures.py`：`Ran 36 tests`、`OK`。
- 新用例要用到 symlink、目录 symlink，以及经 `\\?\` 创建的、名称末尾带点或空格的链接。这些用例在本机都实际运行，没有跳过。

**fixture**：不受影响，没有重新生成。
- manifest 仍是 171 条，sha256 不变。
- `python tests/codekit01_legacy.py --check` 为 `32 checks, 0 differ`，三份 expected 都是 SAME。
- 协议负例都是单条记录的校验，不涉及链接链与 `usage_view` 的多条观测，所以没有期望随本轮改动变化。

**变异抽查**：在 tempfile 建的副本中逐一植入 19 个变异，用 `tests/test_protocols.py` 的 PhysicalPathTests、SealingTests、UsageTests、ResourceRefTests 运行，全部被发现。19 个变异包括：
- 本轮每项修复的反向改动：内部 `..` 被忽略；内部 `..` 当作开头的 `..`；开头的 `..` 被忽略；恢复 P4 第 3 轮的物理语义拆分；去掉逐字路径；去掉终点核对；展开后不把终点设为起点目录；sealing 不传 resolve 结果；接受 `/`；接受 `\\.\`；`..` 越过盘符根时截断而不是拒绝；去掉逐跳越界判定；5b 的三处改动。
- 复审列出的四个变异：
  - P61 对应“相对目标从盘符根起算”；
  - P66 对应“只有根的目标不受支持”；
  - P67 对应“只有盘符的目标被接受”；
  - P60 是“`..` 改成空操作”。
- P60 的说明：修复后，`_check_link_hops` 中按物理语义处理 `..` 的分支只在 POSIX 上由 `_split_link_target` 触发，在 Windows 上走不到，所以 P60 起初存活。现在由白盒用例 `test_A10_link_walk_physical_dotdot_branch` 发现：该用例注入 POSIX 形式的分段，在 Windows 上走这个分支。POSIX 的黑盒实测仍为 NOT_RUN。

#### 逐条处理

| # | 视角 | 严重度 | 问题 | 处理 | 回归测试 / 变异 |
|---|---|---|---|---|---|
| 1 | fidelity | major | `_check_link_hops` 把目标文本中的 `..` 按物理语义处理（先跟随前面的链接、再取真实目录的上一级），而 Windows 按词法折叠。结果：`a/l → x\..\y` 经 `a/y → outside/hop2` 绕到根外的链被接受，`read_sealed` 返回字节，`seal_bytes(repo, "a/ld/new.json")` 经 `xd\..\yd` 写入 `repo/sub`；反方向 `missing\..\y.txt` 被误报 | 采纳（按 OS 语义实现，不用“`..` 前有分段就拒绝”的保守方案，因为后者会误伤合法的根内链）。`_split_link_target` 在 Windows 上按词法折叠目标文本，折叠后开头的 `..` 作用于链接所在的真实目录，绝对目标同样折叠（已由 R-P9 / P4 第 5 轮更正：本机实测内核对逐字绝对目标中的 `.`、`..` 与空分段不折叠，而是拒绝解析；第 5 轮起逐跳核对把这类写法按不受支持的写法拒绝，见第 7 节与“P4 第 5 轮”措辞修改清单第 3 条。本条的折叠规则只适用于相对目标）；POSIX 保持物理语义（设计意图，NOT_RUN）。另加兜底：展开终点必须与这一级 resolve 的结果逐字相同，否则报 `link_walk_diverged`。本机复现了复审的两个场景：修复前被接受或写入，修复后三个入口都报 `E_PATH_ESCAPE`，不写入，不调用索引；`missing\..\y.txt` 与 `L\..\sub\file.txt` 被接受。第 7 节原第 389 行的“`..` 按所在真实目录的上一级处理”已删除，改写为按平台分述；原第 407 行补充了本轮用例；第 15、16 节与 docstring 同步 | `test_A10_windows_link_target_dotdot_is_lexical`、`test_A13_seal_and_read_windows_lexical_and_trailing_dot_chains`、`test_A10_split_link_target_forms`、`test_A10_link_walk_unsupported_form_and_divergence`、`test_A13_link_walk_divergence_rejected_by_seal_and_read`；变异 M01、M02、M03、M08、M15、M16、S01 |
| 2 | paths | major | 与第 1 条相同（`L\..\y`、`L\..\yd` 的读与写；`L\..\sub\file.txt` 被误报） | 与第 1 条合并处理 | 同第 1 条；复审的 `store/seg`、`segd` 场景见 `test_A13_seal_and_read_windows_lexical_and_trailing_dot_chains` |
| 3 | paths | major | 逐跳核对用 Win32 路径做 lstat、readlink、resolve，分段末尾的点与空格被去掉，而内核在 NT 层逐字解析。名称为 `hop.`、`hop `、`dhop.` 且指向根外的链接因此不会被识别，`read_sealed` 返回字节，`seal_bytes` 写入 | 采纳建议中的第一种做法：逐跳核对对 lstat、readlink 与中间分段的 resolve 都使用 `\\?\` 逐字路径（`_os_path`）。没有采用“目标文本中以 `.` 或空格结尾的分段一律拒绝”，理由有二：一是逐字访问与内核看到的是同一对象，不会误伤（已由 R-P9 / P4 第 5 轮更正：这只针对已枚举的写法，即分段末尾的点与空格；NT 层与 Win32 层名称语义差异中尚未枚举的写法列入已知不检测，见第 7 节清单）；二是它同时覆盖了根内真实目录名本身以点结尾的情形（resolve 对这类路径保留 `\\?\` 前缀），只拒绝目标文本覆盖不到这种情形。第 7 节写明 NT 层与 Win32 层名称不一致的情形 | `test_A10_link_target_names_with_trailing_dot_or_space`（resolve 入口：文件链末尾点与空格、目录链末尾点，另测根内 `dd.` 目录照常可用）、`test_A13_seal_and_read_windows_lexical_and_trailing_dot_chains`（read_sealed 与 seal_bytes，seal 不写入、不调用索引）、`test_A10_split_link_target_forms`（`_os_path` 形式）；变异 M07 |
| 4 | events-usage | major | provider 为 null 的观测与 provider 已知的观测带同一 billing_event_id 时，既不去重也不拒绝：跨 run、role 时相加得 200；修订链变体 a(null,BX) ← b(P,无账单号)、c(P,BX) 的 6 种到达顺序都得 220、USD 2.20，并标为完整 | 采纳：5b 分组时，只要某个 billing_event_id 由 provider 为 null、且所在链可计入的成员代表，同号下 provider 已知的可计入链尾也一并参与，两条以上即报 `E_USAGE_SCOPE_UNKNOWN`（`billing_event_without_provider_repeated`），不区分 request/run/role。与建议不同的一点是判定时机：5b 移到第 6 步开头的范围歧义判定之后，这样同一 (request, run, role) 下已知与 null 并存的输入仍报 `scope_provider_or_model_unknown`，已有断言 `test_A06_null_provider_or_model_scope_is_ambiguous` 不变。副作用：两条 provider 为 null、model 不同的同号观测在同一 (request, run, role) 时，reason 由 billing 改为 scope，错误码不变；第 13.2 节已写明。provider 为 null 的成员只有 unknown 观测时不触发，不同 provider 的同号观测照常相加 | `test_A06_billing_event_null_and_known_provider_not_summed`（跨 run、role、request 的两种顺序；修订链变体与 c=120 变体的全部顺序；全部已知时 120、USD 1.20、完整的对照；同链只计一次；只有 unknown 时不触发）；变异 M12、M13、M14 |
| 5 | tests-mutation | major | 相对目标的越界分支没有拒绝用例：P60（`..` 改为空操作）、P61（相对目标从盘符根起算）存活；同类的 P66（只有根的目标返回 None）、P67（不拒绝只有盘符的目标）也存活 | 采纳，补测三组：（1）以相对目标开头的越界链 `relhop → hop2`、`sub/up → ..\hop2`、目录链 `reld → dhop2`，在三个入口都断言 `E_PATH_ESCAPE`（`link_hop_outside_trusted_root`）；只有根的目标 `\Users\…\ok.txt` 在根内时接受，经根外链接时越界。（2）`C:x` 目标断言 `E_PATH_RESOLUTION_FAILED`（`link_target_form_unsupported`），用白盒注入：本机实测 `os.symlink` 在创建时就把 `C:x` 转成绝对路径（readlink 得到 `\\?\C:\<当前目录>\ok.txt`），黑盒造不出这种链接。（3）P60 的处理见上文“变异抽查” | `test_A10_relative_link_chain_through_outside_is_escape`、`test_A13_seal_and_read_reject_relative_link_chain_through_outside`、`test_A10_link_walk_unsupported_form_and_divergence`、`test_A10_link_walk_physical_dotdot_branch`、`test_A10_split_link_target_forms`；P60、P61（本轮 M04）、P66（M05）、P67（M06） |

#### 需要规划端知悉的事项

- 本轮改动了 protocols.py 中函数的行号：`_check_link_hops` 一带增加约 80 行，`usage_view` 第 5b 步增加约 11 行。compatibility-matrix.md 依据索引中的行号已同步；01-baseline 下的其他文档没有引用 `protocols.py` 的具体行号（已检索）。
- 没有新的跨模块决定。第 5b 步判定时机的调整只影响 reason，不影响错误码。本轮所有行为变化都向“拒绝或更贴近 OS 语义”的方向。

### P4 第 5 轮：裁决 R-P9 的落实与第 5 轮复审的逐条处理

第 5 轮复审共 7 条 major：paths 视角 3 条，fidelity 视角 3 条，events-usage 视角 1 条。另有 3 条 minor 按要求不处理，只登记在本节末尾。

- 7 条都成立，没有不采纳的条目。
- 第 1、2、3、5、6 条都是裁决 R-P9 (2)(3) 没有落实，合并处理；第 7 条是 R-P9 (1) 的代码缺口；第 4 条是 `usage_view` 第 5b 步的缺陷。
- 每条都先在本机复现（tempfile 建的目录，用后删除），再修复并补断言。新增与修改的测试在 docstring 中写明“P4 第 5 轮”与复审视角。
- 路径类问题按 R-P9 优先选择失败关闭，没有继续扩展解析逻辑。

**接手时的状态**：本轮开始时，`protocols.py` 与 `tests/test_protocols.py` 已经含有一部分本轮的改动，来源应是本任务上一次未完成的执行。这些改动包括：`PATH_REVIEW_LIMITATIONS`、名称代理类重解析点的失败关闭、`_split_link_target` 收紧的写法、第 5b 步按成员登记及其回归测试。`sealing.py` 与本文当时都还没有改。

- 本轮逐项复核了这些改动：用 FSCTL 实测了它们引用的内核行为，并做了变异抽查。复核后保留。
- 缺失的部分已补齐。例如测试 docstring 引用的 `test_A10_windows_link_target_forms_measured` 当时并不存在，本轮补写。

#### 裁决 R-P9（规划端，2026-09-25）

原文见 [decisions.md](decisions.md)。要点：

1. 业务路径的物理检查是“静态审阅 + 纵深防御”，**不是安全访问保证**（01-D06；设计文档 4.1.6–4.1.7：01 不提供安全写文件的万能函数）。物理检查指 `resolve_existing_path_for_review`、`_check_link_hops` 逐跳核对与 sealing 的路径步进。
2. 遇到无法确定语义的链接写法必须失败关闭，不得猜测放行。
3. 文档、docstring 与测试 docstring 不用“保证”“杜绝”“任一级越界都会被发现”这类绝对表述，改为“已检测的情形”与“已知不检测、不保证”两张清单。后一张至少列出：TOCTOU 与并发替换、检查后父目录或目标被替换、硬链接与挂载点、NT 层与 Win32 层名称语义差异之外尚未枚举的写法、POSIX 平台未实测、同账户进程篡改。
4. sealing 的 `store_root` 必须是可信核心独占控制的目录；sealing 不防御被攻击者控制的存储根；A13 的范围是“发布与索引补偿”。

落实位置：

- 文档：
  - 第 7 节新增“物理检查的定位（裁决 R-P9）”，含两张清单：已检测的情形 16 项，逐项列出测试名；已知不检测 9 项；
  - 第 15 节开头新增“范围与前提”，末尾的“明确限制”改为两张清单：已检测的情形 4 项，已知不检测 10 项；
  - 第 16 节“合法路径与保护范围”“完整 SHA-256”两行引用这两张清单；开头“以下能力都不在本模块中”一段加上 R-P9 的定位。
- 代码：
  - 新增常量 `protocols.PATH_REVIEW_LIMITATIONS`（9 项，列入 `__all__`）；
  - `sealing.SEALING_LIMITATIONS` 由 6 项增至 13 项，原有 6 项的文字不变；
  - 两个模块中相关函数的 docstring 改为“已检测的情形”加“见限制清单”。
- 失败关闭（第 7 条）：
  - 未识别的名称代理类重解析点报 `link_kind_unsupported`；
  - 只有根、没有盘符的目标，不带 `\\?\` 的盘符绝对路径，逐字绝对目标中的 `.`、`..` 与空分段，都按不受支持的写法处理。
- 固定措辞的测试：`test_A10_physical_check_wording_follows_r_p9`。它检查以下内容：
  - 11 个相关 docstring 与本文第 7、15、16 节不含禁止的绝对表述；“保证”只允许出现在“不保证”“不是安全访问保证”中；
  - 第 7、15 节含两张清单，第 15 节写明“可信核心独占控制”“发布与索引补偿”；
  - 两份限制清单列出 R-P9 点名的各项。
  - 第 5 轮核验后，检查范围扩大到整份文档与全部测试 docstring，另由 `test_A10_r_p9_wording_covers_changelog_history_and_tests` 固定，见本小节末尾“第 5 轮核验的后续处理”。

#### 措辞修改清单

| # | 位置 | 原表述 | 改为 |
|---|---|---|---|
| 1 | 本文第 7 节（原第 387 行） | “任何一级解析后的最终目标越出根目录，都报 `E_PATH_ESCAPE`” | 已检测情形第 1、2 项；流程第 2 步写成“这一级解析后的最终目标在根外，报 …” |
| 2 | 第 7 节（原第 388 行） | “链上**每一个链接对象**……都必须位于根内” | “展开时遇到的链接对象，若它所在目录解析后的真实路径不在根内，报 …”（已检测情形第 4–7 项） |
| 3 | 第 7 节（原第 390–391 行） | “`.` 与 `..` 的处理与本平台内核一致”；“绝对目标同样按词法折叠” | 分成三条：<br>- Windows 相对目标：本机实测按词法折叠；<br>- 逐字绝对目标：本机实测内核拒绝，resolve 先行失败，逐跳核对的拒绝只是保守兜底；<br>- POSIX：设计意图，NOT_RUN。<br>“绝对目标同样按词法折叠”与实测不符，已删除（复审用 FSCTL 造出 `\??\<T>\repo\x\..\hop`，报 winerror 123；本轮复测相同，`.` 为 winerror 3，空分段为 winerror 123） |
| 4 | 第 7 节（原第 400 行） | “只有根、没有盘符的目标……是受支持的写法” | 列入不受支持的写法（语义无法确定），见第 7 条 |
| 5 | 第 7 节（原第 402 行） | “所以逐字比较可靠” | “所以按组件逐字比较。它只比较两个路径字符串，不核对对象身份：硬链接、挂载点与检查之后的替换不在它的判断范围内” |
| 6 | 第 7 节（原第 410–423 行） | “本机 Windows 已实测以下情况”（列表） | “已检测的情形”表（16 项，逐项列测试名），另加“已知不检测、不保证”（9 项） |
| 7 | 第 15 节第 2 步（原第 778–779 行） | “链上每一个链接对象都必须位于根内”；“不在其下创建目录、不发布文件” | “已检测的情形：……测试断言这时存储根中没有新文件，也没有调用 index_commit” |
| 8 | 第 15 节第 2 步（原第 784 行） | “所以在**没有并发替换**的前提下不会在根外创建目录” | “mkdir 只在这一次核对通过的目录下执行。已知不检测：核对之后祖先被替换时……会落到根外” |
| 9 | 第 15 节 read_sealed（原第 807 行） | “任一级的最终目标越界，或链接链上任一个链接对象位于根外……报 `E_PATH_ESCAPE`”；“`..` 与名称的处理与本平台内核一致” | 按“已检测的情形”分项，另加“已知不检测”一项（并发替换、硬链接） |
| 10 | 第 15 节“明确限制”（原第 811–816 行，4 条） | 4 条限制 | “已检测的情形（sealing）”与“已知不检测、不保证”（10 条）两张清单 |
| 11 | 第 16 节（原第 828 行） | “逐跳确认链接链上每个链接对象在根内……与本平台内核一致” | “静态审阅 + 纵深防御，不是安全访问保证”；已检测与已知不检测的情形见第 7 节清单 |
| 12 | 第 16 节“来源引用可信”一行 | “可信与否由调用方保证” | “可信与否由调用方负责”（与路径无关；改动是为了让第 16 节的措辞检查不设例外） |
| 13 | 本文开头“以下能力都不在本模块中” | — | 新增一句：业务路径的物理检查只是静态审阅 + 纵深防御 |
| 14 | `protocols.py` 的 `_is_within`、`_check_link_hops`、`resolve_existing_path_for_review`、`_split_link_target`、`_check_listed_name`、`_link_target_text` | 复审引用的原文：<br>- “宁可误报 `E_PATH_ESCAPE`，也不放过根外对象”；<br>- “链上**每一个链接对象**……都必须位于根内”；<br>- “与本平台内核一致”；<br>- “这与 POSIX 内核一致”；<br>- “同一个字符串在同一时刻只能指向同一个对象” | - 前三处改为“已检测的情形”，并引用 `PATH_REVIEW_LIMITATIONS`；<br>- `_is_within` 改为“拼写不同一律视为越界（保守方向，可能误报）”，并写明不核对对象身份；<br>- POSIX 分支注明“设计意图，NOT_RUN”；<br>- 模块说明加一条 R-P9 定位 |
| 15 | `sealing.py` 的模块说明、`_step`、`_ensure_parent`、`seal_bytes`、`read_sealed` | - “调用方传入的受信存储根目录”；<br>- “链接链上的每一个链接对象都必须位于根内”；<br>- “这一保证只在没有并发替换的前提下成立”；<br>- “store_root 由调用方信任”；<br>- “任一级的最终目标越出 store_root，或链接链上任一个链接对象位于根外” | - 按“已检测的情形”分项；<br>- 写明存储根必须由可信核心独占控制、sealing 不防御被攻击者控制的存储根、A13 的范围是发布与索引补偿；<br>- 指向 `SEALING_LIMITATIONS` |
| 16 | `tests/test_protocols.py` 的三个测试 docstring | - `test_A10_single_segment_link_chain_through_outside_is_escape`：“链上任一个链接对象位于根外 →”；<br>- `test_A10_windows_link_target_dotdot_is_lexical`：“现在两个方向都与 OS 一致”；<br>- `test_A10_link_walk_physical_dotdot_branch`：“都会被发现”（指变异） | 分别改为：<br>- “已检测的情形……逐跳展开时遇到位于根外的链接对象 →”；<br>- “本机实测两个方向现在都与 OS 的解析一致”；<br>- “两种情形都会让本用例失败” |

#### 逐条处理

| # | 视角 | 严重度 | 问题 | 处理 | 回归测试 / 变异 |
|---|---|---|---|---|---|
| 1 | paths | major | 接口文档没有落实 R-P9 (2)(3)：<br>- 第 7、15 节没有两张清单；<br>- 第 15 节“明确限制”缺硬链接、挂载点、未枚举的写法、检查后替换；<br>- 没有写存储根独占与 A13 范围；<br>- 第 19 节没有 R-P9 | 采纳。落实位置见上文，措辞修改见清单第 1–13 条；第 19 节新增本小节 | `test_A10_physical_check_wording_follows_r_p9` |
| 2 | paths | major | sealing 的 docstring 与 `SEALING_LIMITATIONS` 用了 R-P9 禁止的措辞，缺存储根前提 | 采纳。措辞修改见清单第 15 条。`SEALING_LIMITATIONS` 新增 7 项：存储根独占、A13 范围、检查后替换、硬链接、挂载点、NT/Win32 尚未枚举的写法、POSIX 未实测 | 同第 1 条；`test_A13_hard_link_alias_is_known_not_detected` |
| 3 | paths | major | protocols.py 的路径 docstring 有超出 R-P9 的绝对表述，也没有已知不检测清单 | 采纳。措辞修改见清单第 14 条；新增 `PATH_REVIEW_LIMITATIONS`（9 项） | 同第 1 条 |
| 4 | events-usage | major | 第 5b 步只按链尾是否可计入登记账单号。a(null,BX,100) 被 r(unknown) 修订后，同号的 c 被单独计入：c 为重投时，被替代的值复活；c 为冲突值时，冲突被静默接受。provider 全部已知时，同样的输入计 0 或报 `E_USAGE_CONFLICT`。第 13.2 节两处写法对这一输入给出不同结论 | 采纳，按建议改为**按成员判定**：带 billing_event_id 的成员，自身 observation_kind 不是 unknown 时登记（新增），所在链的链尾可计入时也登记（P4 第 4 轮的口径，保留）。<br>- 与建议不同的一点：建议的写法只看成员自身的 kind。那样会丢掉“成员自身是 unknown、链尾可计入”这一类：u(null,BX,unknown) ← b，另有同号的 c，会被静默相加；provider 全部已知时同样的输入是 `E_USAGE_CONFLICT`。所以两者取并集。<br>- 复审列出的已有断言都不变：`with_unknown`、`distinct_providers`、同链只计一次、单独 a←r(unknown) 计 0。<br>- 第 13.2 节第 5b 步的两处写法统一为一条规则；docstring 第 5 步同步 | `test_A06_billing_event_chain_revised_to_unknown`：<br>- a、c 的 provider 取 null/已知的四种组合；c 取 100 与 150；同 run 与跨 run；全部到达顺序；<br>- provider 全部已知时的 0 / `E_USAGE_CONFLICT` 对照；没有 c 时计 0；两条代表链都不可计入时不触发；<br>- 反方向：成员自身是 unknown、链尾可计入时照常登记。<br>变异 M2、M3、M6 |
| 5 | fidelity | major | R-P9 (2) 没有落实：<br>- 仍有绝对表述，没有两张清单，硬链接没有列入；<br>- “与本平台内核一致”对绝对目标不成立（逐字绝对目标中的 `..` 内核并不折叠，而是拒绝） | 采纳，与第 1–3 条合并。另外三点：<br>- 删去“绝对目标同样按词法折叠”（清单第 3 条）；<br>- 硬链接列入不检测清单，并用测试固定复审的复现；<br>- protocols.py 的“与 POSIX 内核一致”改为“设计意图，NOT_RUN” | `test_A10_windows_link_target_forms_measured`（黑盒：逐字绝对目标含 `..`、`.` 或空分段时内核拒绝）、`test_A13_hard_link_alias_is_known_not_detected`、`test_A10_physical_check_wording_follows_r_p9` |
| 6 | fidelity | major | R-P9 (3) 没有落实：没有写存储根独占、不防御攻击者控制的存储根、A13 的范围；第 15 节第 2 步与 read_sealed 仍是保证式表述 | 采纳，与第 2 条合并。sealing 模块说明、`seal_bytes`/`read_sealed` 的 docstring、`SEALING_LIMITATIONS`、第 15 节“范围与前提”都写明了这三点；第 2 步与 read_sealed 的表述改为已检测的情形（清单第 7–9 条） | 同第 1、2 条 |
| 7 | fidelity | major | 违反 R-P9 (1)：`_link_target_text` 把未识别的名称代理类重解析点当作普通名称。有过滤驱动跟随这类对象时，经根外绕回根内的链会被接受 | 采纳建议 1–3。lstat 报告的标签带名称代理位，又不是 SYMLINK 或 MOUNT_POINT 时，抛内部异常 `_UnsupportedLinkKind`，`_check_link_hops` 报 `E_PATH_RESOLUTION_FAILED`（`link_kind_unsupported`），三个入口共用。<br>同属 R-P9 (1)，一并收紧三类写法：<br>- 只有根、没有盘符的目标：本机实测，同一形状的文本在相对标志下从盘根起算，在绝对标志下是 `\Device\HarddiskVolumeN\…`、`\GLOBAL??\C:\…` 这类 NT 路径，内核都能跟随，而 readlink 不给出标志位；<br>- 不带 `\\?\` 的盘符绝对路径；<br>- 逐字绝对目标中的 `.`、`..` 与空分段。<br>后两类内核本来就拒绝，所以入口的结果不变，只是逐跳核对不再猜测它们可以解析。不带名称代理位的重解析点仍按普通名称处理，已列入已知不检测清单 | - `test_A10_unrecognized_name_surrogate_reparse_point_fails_closed`、`test_A13_unrecognized_name_surrogate_rejected_by_seal_and_read`：白盒，按复审的注入方式覆盖三个入口，seal 不写入、不调用索引；<br>- `test_A10_windows_link_target_forms_measured`：黑盒；<br>- `test_A10_split_link_target_forms`、`test_A10_relative_link_chain_through_outside_is_escape`：修改，见下；<br>- 另补 `test_A10_link_walk_failure_reasons_fail_closed`，覆盖已检测清单第 11 项此前没有用例的三个 reason；<br>- 变异 M1、M4、M5 |

**对已有断言的修改**（有意收紧，不是削弱断言）：`test_A10_relative_link_chain_through_outside_is_escape` 中只有根、没有盘符的两条链：

- `rootrel`（在根内）由“接受”改为 `E_PATH_RESOLUTION_FAILED`（`link_target_form_unsupported`）；
- `rootrel-out`（经根外链接）由 `E_PATH_ESCAPE` 改为同一个失败关闭的码，仍然被拒绝；
- `test_A10_split_link_target_forms` 的接受列表中，对应写法移入拒绝列表。

**行为与错误码变化**：

- 错误码表仍是 58 个码，retryable 不变。
- `E_PATH_RESOLUTION_FAILED` 新增 reason `link_kind_unsupported`。
- 只有根、没有盘符的链接目标由接受改为 `E_PATH_RESOLUTION_FAILED`。`os.symlink` 用带盘符的绝对路径创建的链接写下的是 `\??\C:\…`，不受影响。
- `usage_view` 在上述输入上由“计入”改为 `E_USAGE_SCOPE_UNKNOWN`。
- 其余变化都只是文档与 docstring 的措辞，以及新增的两个常量内容。

**结果**：

- `python tests/test_protocols.py`：`Ran 323 tests`、`OK (skipped=4)`。跳过项与前几轮相同：F017、F029、F030 与 jsonschema 元校验。本轮新增 7 个测试（含接手时已有的第 5b 步测试），修改 2 个测试的断言（见上），另改 3 个测试的 docstring 措辞（清单第 16 条）。依赖 symlink、junction 与 FSCTL_SET_REPARSE_POINT 的新用例在本机都实际运行，没有跳过。
- `python tests/test_codekit01_fixtures.py`：`Ran 36 tests`、`OK`。

**fixture**：不受影响，没有重新生成。

- manifest 仍是 171 条，sha256 不变（`50dc2fc3…`）。
- `python tests/codekit01_legacy.py --check` 为 `32 checks, 0 differ`，三份 expected 与 manifest 中的 legacy 条目都是 SAME。
- `python tests/codekit01_legacy.py --check-stub-regen` 为 `10 checks, 0 differ`。
- `test_codekit01_fixtures.py` 的 `test_manifest_matches_generator_definitions` 与负例逐个断言都通过。协议负例都是单条记录的校验，不涉及链接与 `usage_view` 的多条观测。

**变异抽查**：在 tempfile 建的副本中逐一植入 6 个变异（本轮修复的反向改动），用 `tests/test_protocols.py` 的 PhysicalPathTests、SealingTests、UsageTests 运行：

| 变异 | 内容 | 结果 |
|---|---|---|
| M1 | 名称代理位不再失败关闭 | 被发现（3 个用例失败） |
| M2 | 第 5b 步回到只看链尾 | 被发现 |
| M3 | 第 5b 步只看成员自身的 kind（复审建议的写法） | 起初存活。补上“成员自身是 unknown、链尾可计入”的反方向用例后被发现 |
| M4 | 接受不带逐字前缀的带锚点写法（只有根的目标、`C:\x`） | 被发现 |
| M5 | 逐字绝对目标中的 `.`、`..`、空分段不再拒绝 | 被发现 |
| M6 | 第 5b 步触发时不要求至少一条可计入 | 被发现 |

#### 已知未处理的 minor（交接信息）

按要求不处理，原样登记：

1. paths 视角，本文：个别句子仍写成笼统的保证，接近 R-P9 明确禁止的“任一级越界都会被发现”，其中一句是条件式的绝对表述（“不会在根外创建目录”）。注：本轮按第 1、5 条 major 改写第 7、15、16 节时，被点名的“不会在根外创建目录”一句已改为已知不检测的写法（清单第 8 条）；其余章节没有逐句检查。再注：第 5 轮核验后已检查其余章节，处理见下文“第 5 轮核验的后续处理”。
2. events-usage 视角，`protocols.py`：事件日志系列函数（`assess_event_log`、`recover_next_seq`、`recover_append_state`、`append_event`）只按 run_id 绑定。它们不检查 request_id，也不检查非空 role 在同一 run 内是否一致，所以同一 run 中改写 request_id 或 role 的记录被判为 complete=True，并且可以追加。本文把 complete 写成“序号与绑定一致”，容易被下游理解为已经包含 request/role 绑定（4.3.1）。
3. fidelity 视角，本文：正文写“验收见 `acceptance.md`”，但仓库中没有这个文件。它是 README 中列出的 P4 交付物，尚未生成，读者按引用找不到。

#### 需要规划端知悉的事项

- **只有根、没有盘符的链接目标现在失败关闭**。下游若用这种写法创建链接，例如 `os.symlink` 的目标是不带盘符的 `\x`，三个入口都会报 `E_PATH_RESOLUTION_FAILED`。
- **不带名称代理位的重解析点仍按普通名称处理**，已列入已知不检测清单。去重、云文件、WOF 压缩等很常见，一律拒绝会误伤普通文件；是否需要进一步收紧，由后续访问实现模块决定。
- **`test_A13_hard_link_alias_is_known_not_detected` 固定的是当前的限制**（硬链接被接受），不是期望的安全行为。后续模块加入硬链接检测时，应同时修改这个用例与两份限制清单。
- **裁决 R-P3 的文字仍待规划端确认**（见“P4 第 3 轮”）。decisions.md 本轮不在可写范围内。
- **行号变化**：protocols.py 在模块说明中增加 3 行，路径检查一带增加约 63 行，`usage_view` 第 5b 步增加约 15 行。compatibility-matrix.md 依据索引中的全部 `protocols.py` 行号已按内容逐一核对并更新（修订 6）。
- 没有新的跨模块决定。本轮所有行为变化的方向都是拒绝或失败关闭。

#### 第 5 轮核验的后续处理

第 5 轮返工经独立核验：7 条 major 没有未修好或回归的条目；另报本文措辞的 minor 2 条，以及 2 条仓库之外的操作遗留（info）。本次只改本文措辞与测试，`protocols.py`、`sealing.py` 的行为不变。

| # | 严重度 | 问题 | 处理 | 回归测试 |
|---|---|---|---|---|
| 1 | minor | 第 18 节第 20 项（P4 第 4 轮的改动）仍写“按词法折叠目标文本中的 `.` 与 `..`（与 I/O 管理器一致，此前按物理语义）”，没有限定相对目标。第 5 轮起逐字绝对目标中的 `.`、`..` 被拒绝，本机实测内核也是拒绝而不是折叠，这句已过时。原措辞检查只覆盖第 7、15、16 节，没有发现它 | 采纳：<br>- 第 20 项改为“按词法折叠相对目标文本中的 `.` 与 `..`”，括注改为本机实测的范围（I/O 管理器处理相对 symlink 时按词法折叠）；POSIX 注明设计意图、NOT_RUN；<br>- 另加一条带更正标记的说明：该轮对逐字绝对目标也做了折叠，第 5 轮起按不受支持的写法拒绝 | `test_A10_r_p9_wording_covers_changelog_history_and_tests`：第 18 节整节按第 7、15、16 节的规则检查；第 20 项必须含“按词法折叠相对目标”“逐字绝对目标”与更正标记 |
| 2 | minor | 第 19 节的历史行保留被取代的绝对表述，没有更正说明：<br>- “P4 第 3 轮”第 1 条：“链上任一个链接对象位于根外即 …”，是 R-P9 禁止的写法；<br>- “P4 第 4 轮”第 1 条：“绝对目标同样折叠”，已被第 5 轮的实测推翻。<br>上一轮的交接信息也写明“其余章节没有逐句检查” | 两种建议都采纳：<br>- 历史行保留原文，因为它们记录的是当时的处理；在原句后加更正标记“（已由 R-P9 / P4 第 5 轮更正：……）”，写明现行表述及所在清单；<br>- 措辞检查扩大到整份文档与全部测试 docstring，见下文。<br>逐句检查其余章节后，另有 3 处同类的历史表述，也加了更正标记：<br>- “P4 第 4 轮”第 3 条的“逐字访问与内核看到的是同一对象”：只针对已枚举的末尾点与空格；<br>- “P2 返工”R-14 的“samefile 必然为真”：逐字比较不核对对象身份；<br>- “P4”第 2 轮 minor 第 9 条的“不会误发布”：这是没有并发替换时的已检测情形 | 同上。第 19 节中，引号外出现禁止表述的行必须带更正标记；被点名的两条历史行必须带标记 |

**措辞检查的新范围**：由 `test_A10_r_p9_wording_covers_changelog_history_and_tests` 检查。它与原用例 `test_A10_physical_check_wording_follows_r_p9` 共用禁止表述清单 `R_P9_FORBIDDEN` 与检查函数。

- 第 18 节整节：规则与第 7、15、16 节相同，包括“保证”只能出现在“不保证”“不是安全访问保证”中。
- 开头与第 1–6、8–14、17 节：不得出现禁止的表述。
- 第 19 节：允许在中文引号中引用原表述，例如“P4 第 5 轮”的措辞修改清单。引号外出现禁止表述的行，必须带更正标记 `已由 R-P9 / P4 第 5 轮更正`。
- 测试文件：模块 docstring、全部测试类与测试方法的 docstring，去掉引号中的引用后，不得出现禁止的表述。PhysicalPathTests、SealingTests 两个类另按“保证”的限制检查。
- 禁止表述清单增补三项：“管理器一致”“同样折叠”“不会在根外”。原用例也随之适用，清单只增不减。

**变异抽查**：在 tempfile 建的副本中逐一植入 6 个变异，运行两个措辞用例，全部被发现：

1. 第 20 项恢复原文；
2. 去掉“P4 第 3 轮”第 1 条的更正标记；
3. 去掉“P4 第 4 轮”第 1 条的更正标记；
4. 第 17 节加入“任一级越界都会被发现”；
5. SealingTests 的一个测试 docstring 加入“保证”；
6. TimeTests 的一个测试 docstring 加入“杜绝”。

对照：同一 docstring 在引号中引用“杜绝越界”时，用例不失败。副本目录用后已删除。

**结果**：

- `python tests/test_protocols.py`：`Ran 324 tests`、`OK (skipped=4)`。跳过项不变：F017、F029、F030 与 jsonschema 元校验。本次新增 1 个测试；`test_A10_physical_check_wording_follows_r_p9` 改为调用共用的清单与检查函数，检查内容只增不减。
- `python tests/test_codekit01_fixtures.py`：`Ran 36 tests`、`OK`。
- fixture 不受影响，没有重新生成：本次没有改 `protocols.py`、`sealing.py`，协议负例的期望不变。

**仓库之外的操作遗留**（核验报告的 info 与 minor，本次没有处理，由用户确认后清理）：

- 第 5 轮返工在系统临时目录下留下一个快照目录（`codekit-p4r5-orig-` 开头），内含本轮范围内 5 个文件的副本。第 5 轮“用后删除”的说法对这个目录不成立。
- 核验运行测试时，输出重定向到由未设置的变量拼成的路径，在 Git 安装目录下留下一份测试日志（`p.txt`，只有 unittest 输出）。删除它需要用户操作。

### 收尾轮：裁决 R-P10、R-P11 与 M-01、M-03、M-10–M-12 的处理

依据：decisions.md 末尾“收尾轮裁决”（R-01、R-02、R-P3 勘误、R-P10、R-P11、R-P12，2026-09-26）与 acceptance.md 第 7 节第 13、14、15、18 项、第 10 节 M-01、M-03、M-10、M-11、M-12。本轮的可写范围是 `scripts/codekit/protocols.py`、`tests/test_protocols.py` 与本文；`sealing.py` 没有改。R-01（取证的 pyc 口径）、R-02（A07 口径）、R-P12（input_fixture_ref 与比较投影）不涉及本模块的接口，由取证与 fixture 的后续工作落实；M-04、R-12 不在本轮范围。

#### 逐条处理

| 编号 | 问题 | 处理 | 测试 |
|---|---|---|---|
| M-10 / R-P10 | `ResourceKind` 缺文档 4.2.1 要求的 schema、允许的载荷表示与语义校验器，第 18 节没有登记这一差异 | 按裁决增加 `schema_ref`、`payload_representations`、`payload_validator`；注册表的构造与 `extended()` 要求三项都已声明，缺失报 `E_SCHEMA_FIELDS`（`resource_kind_registration_incomplete`）；新增 `validate_resource_payload`（先核验字节，再查载荷表示，再执行校验器；校验器抛出的其他异常包装为 `E_SCHEMA_FIELDS`，reason `payload_validator_unexpected_exception`，不带原文字、不链接原异常）；按裁决更新 5 个预登记类型。见第 8 节，第 18 节第 22 项登记与规格的差异 | `test_A04_r_p10_default_registry_declarations`、`test_A04_r_p10_registration_requires_three_declarations`、`test_A04_r_p10_declaration_values_validated`、`test_A04_r_p10_validate_resource_payload_representations`、`test_A12_r_p10_fixture_manifest_payload_validator`、`test_A04_r_p10_public_schema_payload_validator`、`test_A04_r_p10_validator_exceptions_are_wrapped` |
| M-03 / R-P11 | fixture 条目缺完整性、平台适用性、采集环境、截取范围、是否保留协议结构、来源是否可追溯 | 条目新增 `integrity`、`platform_scope`、`capture`、`redaction.protocol_structure_preserved`、`origin.traceable`，字段仍然封闭；第 14.2 节新增第 3b 步（legacy 与 captured 必须 traceable；captured 必须有 capture，其他类别必须为 null）与第 5 步（integrity 不是 complete 时不得声称以 `complete_run_stream`、`full_run` 开头的声明；协议结构未保留时不得声称以 `protocol_field_semantics` 开头的声明）；删除第 14.2 节“现行规则的空缺”中已补上的项 | `test_A12_r_p11_new_fields_structure`、`test_A12_r_p11_traceable_and_capture_rules`、`test_A12_r_p11_integrity_limits_complete_stream_claims`、`test_A12_r_p11_structure_preservation_limits_field_semantics_claims`、`test_A12_r_p11_manifest_set_reports_entry_pointer`；`test_A12_appendix_c1_example_needs_completion`（补齐新字段，并逐项去掉一个新字段断言 `missing_field`） |
| M-01 | 事件日志系列函数只按 run_id 绑定，同一 run 中改写 request_id 或 role 的记录仍判 complete=true 且可以追加；文档把 complete 写成“序号与绑定一致”容易误读 | 四个函数都核对同一 run 内 request_id 一致与非空 role 一致：`assess_event_log` 记入 binding_errors，绑定字段不可读的记录记入 invalid；`append_event` 报 `E_CONTEXT_BINDING`（`request_binding_mismatch`、`role_binding_mismatch`），参照值从 committed 的快照字节读出，state 形状不变；恢复函数按 run → request → role 的固定顺序取 reason。第 11 节写清 complete 的含义：绑定指日志内部一致，不指与受信 RunContext 一致 | `test_A11_m01_event_log_request_and_role_binding`、`test_A11_m01_binding_reason_order_is_fixed`、`test_A11_m01_unreadable_binding_fields`、`test_A11_m01_append_event_request_and_role_binding`、`test_A11_m01_entry_points_agree` |
| M-12 | 第 3.2 节说 `E_BASELINE_*`“登记供基线取证工具使用”，取证工具实际不发出 | 改为“登记待用；当前取证工具不发出，漂移与缺输入分别用 baseline_consistent 与 execution_status 表达” | 文档修改，无代码变化 |
| M-11 | 4.3.2 的两行在 01 中没有落点，第 11、17 节没有写归属 | 第 11 节末尾新增归属表：派生视图修订与 view_id 归 04（与 adapter_revision 一并设计），跨 run 的先后关系归 10（项目游标）；第 16 节“seq 连续”一行与第 17 节 04、10 两条同步 | 文档修改，无代码变化 |
| M-02 / R-P3 勘误 | 裁决 R-P3 的文字（前缀为“1–6 个非 `~` 字符”）与实现不一致 | 规划端已裁定以实现为准；第 7 节删去“待规划端确认”，写明勘误的概括与实现的一处细节：实现要求 `~` 之前至少 1 个字符，没有前缀的 `~1`、`~12` 照常接受 | 代码不变；既有 `test_A10_generated_short_names_with_tilde_prefix_reserved` 等不变 |

#### 行为与错误码变化清单（收尾轮）

| 位置 | 变化前 | 变化后 |
|---|---|---|
| `ResourceKind` | 四个字段 | 增加关键字参数 `schema_ref`、`payload_representations`（保存为 frozenset）、`payload_validator` 与方法 `undeclared_fields()`；显式传入的非法值抛 `ValueError` |
| `ResourceKindRegistry` 构造、`extended()` | 只检查类型与同名项 | 登记项缺三项之一报 `E_SCHEMA_FIELDS`（`/schema_ref` 等，`resource_kind_registration_incomplete`） |
| `build_default_registry` | 五类没有载荷信息 | 五类按裁决声明三项；fixture-manifest、public-schema 有校验器 |
| `validate_resource_payload` | 无 | 新增 |
| `validate_fixture_manifest_entry` / `_set` | 条目 10 个顶层字段 | 13 个顶层字段，origin 与 redaction 各多一个字段；新增 reason：`platform_scope_empty`、`platform_scope_any_must_be_alone`、`duplicate_platform`（`E_SCHEMA_FIELDS`），`traceable_required_for_legacy_or_captured`、`captured_requires_capture`、`capture_only_for_captured`、`incomplete_fixture_cannot_prove_complete_stream`、`structure_not_preserved_cannot_prove_field_semantics`、`structure_preservation_unrecorded_cannot_prove_field_semantics`（`E_PROVENANCE_CLAIM`）。旧结构的条目（缺新字段）报 `E_SCHEMA_FIELDS`（`missing_field`） |
| `assess_event_log` | 只按 run_id 记绑定错误 | 同一 run 内 request_id 不一致、非空 role 不一致也记入 binding_errors；绑定字段不可读记入 invalid；返回的键不变 |
| `append_event` | 只核对 run_id | 另核对 request_id 与非空 role（`E_CONTEXT_BINDING`），request_id 不是 str、role 缺失或类型不对报 `E_SCHEMA_TYPE`；committed 中的字节读不出绑定字段时抛 `ValueError` |
| `recover_next_seq` / `recover_append_state` | 绑定错误的 reason 只有 `log_contains_foreign_run` | 新增 `log_request_binding_mismatch`、`log_role_binding_mismatch`，按 run → request → role 取 reason；错误码的全序不变 |
| 错误码表 | 58 个码 | 不变，retryable 不变 |

#### 对已有测试的修改（适应更严的接口，不是削弱断言）

- `make_manifest_entry` 与 `ProvenanceTests.captured` 补上五个新字段（captured 默认带 capture 与 traceable=true）；两处整份替换 redaction 的用例补上 `protocol_structure_preserved`。
- 4 处用 `ResourceKind` 登记测试类型的用例改用新的辅助函数 `make_kind`（声明三项）。
- `test_A04_registry_extension_cannot_override`：登记项声明三项，并新增断言异常不是 ProtocolError，确保触发的是“同名不覆盖”而不是“三项未声明”（ProtocolError 也是 ValueError 的子类，原断言对两者都成立）。
- `test_A12_appendix_c1_example_needs_completion`：补齐新字段后通过，另逐项去掉一个新字段断言 `E_SCHEMA_FIELDS`。

#### 变异抽查

在 tempfile 建的目录中复制最小运行布局（protocols.py、sealing.py、测试文件、本地 Schema 与设计文档），逐一植入 33 个变异（R-P10 10 个、R-P11 13 个、M-01 10 个），运行 ResourceRefTests、ProvenanceTests、EventTests，用后删除目录。32 个被发现；另 1 个是植入时写成了不改变行为的空分支（等价变异），另补一个交换 request 与 role 两类 reason 顺序的变异重跑，被发现。被发现的变异包括：注册表不查三项、校验器异常不包装或在 except 块内包装（保留了原异常的链接）、跳过载荷表示检查、text 放宽为替换解码、public-schema 不核对 `$id`、fixture-manifest 校验器只做解析、traceable/capture 规则去掉或放宽、完整流声明改为精确匹配或只看 partial、两条协议结构规则分别去掉、platform_scope 三条规则分别去掉、request/role 绑定在各入口分别去掉、null role 参与比较、committed 只看 seq 1 的 role、恢复函数的 reason 顺序对调。

#### 结果

- `python tests/test_protocols.py`：`Ran 341 tests`、`OK (skipped=4)`。跳过项不变：F017、F029、F030 与 jsonschema 元校验。本轮新增 17 个测试，修改的已有测试见上。
- `python tests/test_codekit01_fixtures.py`：`Ran 36 tests`、`FAILED (failures=33, errors=24)`。原因是 `tests/fixtures/codekit01/manifest.json`（sha256 `50dc2fc3…`，本轮没有改）与 fixture-manifest 类的协议负例仍是旧结构，缺 R-P11 的新字段；按收尾轮的分工，manifest 与负例由另一位实施者按新结构重新生成，之后再运行。这不是本模块的回归。
  - **后续状态**（收尾轮返工补记）：上面这一条是协议实施者当时的中间状态。fixtures 由另一位实施者按新结构重新生成后，`python tests/test_codekit01_fixtures.py` 为 `Ran 61 tests`、`OK`，manifest.json 的 sha256 为 `95c58a9b5a68166e104ee8a719385d43a8f346bff96ab96806518d6c94a830e0`（188 条）；收尾轮返工后的结果见下一节。

#### 需要规划端知悉的事项

1. **比裁决原文多出的一条保守规则**：`redaction.applied=true` 而 `protocol_structure_preserved` 为 null 时，也不得声称以 `protocol_field_semantics` 开头的声明（reason `structure_preservation_unrecorded_cannot_prove_field_semantics`）。R-P11 只写了 false；依据是 4.3.3“无法保证语义字段未被脱敏破坏时，该 fixture 不能证明该字段的真实协议兼容性”。null 本身仍合法，现有 manifest 没有条目声明 `protocol_field_semantics`，重新生成时不受影响。若不采纳，删去第 5 步的第二个分支与对应断言即可。
2. **前缀判定**：`complete_run_stream` 与 `full_run` 都按前缀判定；`protocol_field_semantics` 同样按前缀判定。**更正（收尾轮返工）**：这三个名称由实施者选定，decisions.md 的 R-P11 原文只写“不得声称完整运行流”“不得声称证明协议字段语义”，没有规定名称；此前这里写的“裁决写的是‘complete_run_stream 或 full_run 前缀’”在 decisions.md、acceptance.md 与设计文档中都查不到出处（可能来自当轮的派发说明，未归档，无法核对），应读作“名称由实施者选定，裁决原文未规定”。收尾轮返工起判定改按受控词表（第 14.2 节第 5 步），这三个前缀都在词表内。
3. **R-P3 勘误的概括与实现的一处差别**：勘误写“基名以 `~` 加 1–6 位数字结尾、基名总长 ≤ 8、扩展名 ≤ 3”，实现另要求 `~` 之前至少 1 个字符，所以 `~1`、`~12` 被接受。勘误已写明以实现为准，本文按实现描述；decisions.md 的文字不在本轮可写范围内。
4. **capture.environment_ref 的 kind**：只要求已登记（文件型须带 path），没有限定为某一类。测试与第 14.1 节示例用 01 的 baseline-evidence；04 采集时若用自己的环境记录类型，需先登记该类型（并声明 R-P10 的三项）。
5. **其他文档中的 protocols.py 行号已过时**：本轮在 `ResourceKind` 一带、事件日志一带与 fixture 清单一带增加了代码，第 1300 行之后的行号都后移了。compatibility-matrix.md 与 acceptance.md 中引用的下列行号需要更新（这两份文件不在本轮可写范围内）：`ResourceKind` 1338-1354 → 1362 起；`build_default_registry` 1418-1427 → 1513 起；`_validate_ref` 1459-1469 → 1571 起；`route_public_record` 1797-1803 → 1979 起；`validate_public_record` 1813 → 1995；vendor 事件的 adapter_revision 检查 2042-2044 → 2224-2226；`assess_stream_integrity` 2052 → 2234；`build_run_dimensions` 2293 → 2570；`_validate_fixture_entry` 3006 → 3317；能力声明循环 3027-3035 → 3439 起；清单级规则 3087-3105 → 3522 起；`validate_fixture_manifest_set` 3136 → 3488。第 1300 行之前的引用（例如 48–57、93、187-188、408、420-421、808-810）不变。

### 收尾轮返工：收尾轮复审发现的逐条处理

依据：收尾轮复审的 13 条发现（fidelity 视角 5 条、tests-mutation 视角 8 条；major 4 条、minor 9 条）。本次可写范围是 `scripts/codekit/protocols.py`、`tests/test_protocols.py`、`tests/legacy_harness.py`、`tests/codekit01_legacy.py`、`tests/test_codekit01_fixtures.py`、`tests/fixtures/codekit01/**`、本文与 compatibility-matrix.md。实际改动的是 `protocols.py`、`test_protocols.py`、`test_codekit01_fixtures.py`、本文与兼容矩阵（修订 10）。`legacy_harness.py`（sha256 `c4e87137…4b974`，与兼容矩阵第 8 节第 9 条记录的相同）、`codekit01_legacy.py` 与全部 fixture 的字节都没有改：本次改动不影响任何 fixture 的判断，不需要重新生成（manifest.json 的 sha256 仍为 `95c58a9b…30e0`，三份 expected 的摘要与兼容矩阵第 1 节相同）。decisions.md 与 acceptance.md 不在可写范围内，需要它们配合的事项列在本节末尾。

#### 逐条处理

| # | 严重度 | 位置 | 发现 | 处理 | 测试 |
|---|---|---|---|---|---|
| 1 | major | `tests/test_codekit01_fixtures.py` 凭据扫描 | 9 类形态漏掉 Stripe（`sk_live_`、`rk_live_`）、Hugging Face（`hf_`）、GitLab（`glpat-`）、npm（`npm_`）、`Authorization: Basic`、URL 内嵌口令；兼容矩阵说只漏掉“没有固定前缀、也不在凭据类键名下的口令”，低估了缺口 | `CREDENTIAL_RULES` 按建议补 6 条（`stripe_key`、`huggingface_token`、`gitlab_token`、`npm_token`、`basic_auth`、`url_credentials`），共 15 条，每条都有运行时拼出的样本；现有 189 个文件扫描后没有新命中。兼容矩阵 9.1 节“fixture 含真实凭据”一行与 E19 改为如实列出 15 类形态，并写明清单之外的形态不会被发现 | `test_scanner_detects_every_rule_in_every_view`（断言样本集合与规则集合相等、规则数为 15）；`test_fixture_files_contain_no_credential_shapes` |
| 2 | major | `protocols.py` 第 5 步 | R-P11 的两条规则只按 `complete_run_stream`、`full_run`、`protocol_field_semantics` 前缀生效，complete_run、run_stream_complete、complete_event_stream、full_event_log、entire_run_stream、field_semantics 等同义名称能绕过，测试还把其中几个固定成“无关名称”；14.2 节没有登记这一限制 | 改为按**受控词表**判定（第 14.2 节第 5 步，新增导出常量 `COMPLETENESS_CLAIM_STEMS`、`COMPLETENESS_CLAIM_PHRASES`、`COMPLETENESS_CLAIM_QUANTIFIERS`、`STREAM_SUBJECT_STEMS`、`FIELD_SEMANTICS_CLAIM_STEMS`、`PROTOCOL_SUBJECT_STEMS`、`FIELD_SUBJECT_STEMS`）：声明按 `_` 切成词元，按词元开头匹配词干。复审实测能绕过的名称都在词表内，改为拒绝；错误码与 reason 不变。词表之外的写法仍不受限制，写入 14.2 节“现行规则的空缺”。删去测试中把 complete_run、run_stream_complete、fullrun、field_semantics、protocol_fields 当作无关名称接受的断言，改为断言拒绝；另断言词表外的正当名称（partial_run_stream、incomplete_stream_detected、successfully_parsed、all_fields_typed、field_order 等）仍被接受。这是在 decisions.md 没有登记词表或命名规则时的实施者选择，见本节末尾第 1 条 | `test_A12_r_p11_integrity_limits_complete_stream_claims`、`test_A12_r_p11_structure_preservation_limits_field_semantics_claims`（均已修改）；`R11Tests.test_manifest_level_errors_carry_entry_prefix`（在真实条目 `negative-legacy-events-ok-truncated-tail` 与 stub 条目上补同义名称） |
| 3 | minor | 本文“收尾轮·需要规划端知悉的事项”第 2 条 | 把三个前缀说成来自裁决，decisions.md 的 R-P11 没有这些名称 | 该条改为“名称由实施者选定，裁决原文未规定”，写明原说法查不到出处；第 2 节常量表、第 18 节第 22 项同步 | 文档修改 |
| 4 | minor | compatibility-matrix.md 第 19、364、375 行 | 仍说 `legacy_harness.py` 的 `remove_tree`“不核对”，引用旧行号 865-883 | 兼容矩阵修订 10：三处改为“已核对”，写明 `make_temp_area` 与 `remove_tree` 的五项核对与回归测试（E23），行号改为当前行号；9.1 节剩余风险一列删去“harness 不核对”，改为注明 harness 字节在最终取证之后已变化、需要按 01-L05 重新取证 | 文档修改 |
| 5 | minor | 本文“收尾轮·结果” | 仍把 `test_codekit01_fixtures.py` 记为失败，说 manifest 没有改 | 在该条后追加“后续状态”：fixtures 重新生成后 `Ran 61 tests`、`OK`，manifest sha256 `95c58a9b…`（188 条）；并注明原条是协议实施者当时的中间状态 | 文档修改 |
| 6 | major | `tests/legacy_harness.py` 的归属核对 | R-12 在 harness 一侧（`make_temp_area`、`remove_tree`、`_remove_owned_once`）没有回归测试，10 个单点变异全部存活 | 在 `tests/test_codekit01_fixtures.py` 新增 `HarnessCleanupOwnershipTests`（11 个方法），把自检项落成断言：每项都断言 `remove_tree` 抛出 `CleanupOwnershipError`（不是返回，也不是重试后的其他异常）且目标仍在。覆盖建议列出的全部场景（未登记目录含伪造标记与真实令牌、区域外路径、标记篡改/末尾多换行/截短/缺失/是目录/是链接、不是临时目录的直接子目录、`gettempdir` 改变、目录被替换并复制标记、待删路径或区域根是联接、已删区域中新出现的路径），另加“前缀不再属于本工具”一项；正向对照为区域内含指向外部的联接与符号链接时，删除区域不影响外部文件。所有路径都由本测试自建，不向 `remove_tree` 传仓库路径。harness 本身不改 | `HarnessCleanupOwnershipTests` 全部方法 |
| 7 | minor | `protocols.py` M-01 的检查顺序 | append_event 的 request → role、run → 绑定字段可读，以及 assess 对同一记录先 request 后 role 的顺序没有被测试固定 | 按建议补 3 个用例，另加 2 个：他 run 且 role 类型不对仍报 `/run_id`；request_id 与 role 都不可读时先报 `/request_id` | `test_A11_m01_append_event_request_and_role_binding`、`test_A11_m01_binding_reason_order_is_fixed` |
| 8 | minor | `protocols.py` 14.2 的检查顺序 | 新字段结构先于来源规则、第 4 步先于第 5 步没有被固定 | 新增多缺陷用例：synthetic 条目带结构非法的 capture（空 range、非对象、未登记 kind、多字段）报结构错误；platform_scope 为空或重复、integrity 非法、traceable 为 null，且同时带合法 capture，报结构错误；negative 条目 integrity=truncated，同时声称 vendor_protocol 与 full_run，报第 4 步（两种排列）；协议结构为 false，同时声称 legacy_dispatch_behavior 与 protocol_field_semantics，报第 4 步；各缺陷单独出现时的结论作对照 | 新增 `test_A12_r_p11_check_order_structure_then_steps` |
| 9 | minor | `ResourceKindRegistry` 的检查顺序 | “三项已声明”先于“同名项”没有被固定 | 用未声明三项、与已有项同名（fixture、raw-segment）的登记项经 `extended()` 与直接构造，断言报 `E_SCHEMA_FIELDS`（`resource_kind_registration_incomplete`），不是同名的普通 ValueError | `test_A04_r_p10_registration_requires_three_declarations` |
| 10 | minor | `_check_payload_representation` | 只覆盖 json+text 组合的回退 | 登记 (json, markdown) 类型：JSON、`# title\n`、中文 UTF-8 文本接受，`\xff` 报 `E_JSON_ENCODING` | `test_A04_r_p10_validate_resource_payload_representations` |
| 11 | minor | `tests/codekit01_legacy.py` 的 `_rmtree` | 标记不是链接、标记末尾不能多出字节、删除后注销登记三项没有测试；测试中“删除后也注销了登记”的注释与断言不符 | 补 3 个用例；原 `test_owned_directory_is_removed` 的末尾断言改为精确断言“目标不是目录”，注释如实说明它不检验注销，注销改由新用例检验（`_owned_key` 不在 `_OWNED_TEMP_DIRS` 中，且同一路径重建并写入同一令牌后仍被拒绝） | `CleanupOwnershipTests.test_marker_with_trailing_newline_refused`、`test_marker_link_to_valid_token_refused`、`test_removal_unregisters_directory` |
| 12 | minor | 凭据扫描的测试缺口 | 真实扫描循环没有正向对照；AWS 的 ASIA 等前缀没有样本；熵阈值没有反向对照 | 真实扫描累计文件数与字节数，断言等于文件数与各文件大小之和（期望值按文件大小独立计算）；新增 `_credential_variant_samples`，为 AWS 的 6 个前缀、GitHub 的 6 种、Slack 的 6 种、`sk-proj-`/`sk-ant-api03-`、Stripe 的其余 5 种组合、PEM 的 4 种、小写 bearer、大写 BASIC、3 种 URL 协议、4 种赋值写法各加样本（共 38 个），每个都在 6 种载体中核对；benign 列表加低熵值 `{"api_key": "AAAA…A11"}` | `test_scanner_detects_every_rule_in_every_view`、`test_fixture_files_contain_no_credential_shapes`、`test_secret_key_in_json_with_random_value_detected` |
| 13 | minor | `COMPAT_MATRIX_D_CASES` | 只核对表中已列出的变体，不核对表是否完整 | 反向核对：故障说明写“兼容矩阵 D-xx”的合同负例变体集合与映射表逐项相等；事件负例的故障说明不得引用 D 编号；映射表内没有重复 | `CompatMatrixDCaseTests.test_every_d_case_is_a_registered_single_fault_fixture` |

#### 行为与错误码变化清单（收尾轮返工）

| 位置 | 变化前 | 变化后 |
|---|---|---|
| `validate_fixture_manifest_entry` / `_set` 第 5 步 | 只拒绝以 `complete_run_stream`、`full_run`（integrity 不是 complete 时）或 `protocol_field_semantics`（协议结构为 false，或 applied=true 而它为 null 时）开头的声明 | 按受控词表拒绝两类声明（第 14.2 节第 5 步）；原三个前缀开头的声明仍被拒绝，另外拒绝词表内的同义名称。错误码（`E_PROVENANCE_CLAIM`）、field（`/proves`）与三个 reason 不变 |
| 导出常量 | — | 新增 `COMPLETENESS_CLAIM_STEMS`、`COMPLETENESS_CLAIM_PHRASES`、`COMPLETENESS_CLAIM_QUANTIFIERS`、`STREAM_SUBJECT_STEMS`、`FIELD_SEMANTICS_CLAIM_STEMS`、`PROTOCOL_SUBJECT_STEMS`、`FIELD_SUBJECT_STEMS`；`COMPLETE_STREAM_CLAIM_PREFIXES`、`PROTOCOL_FIELD_SEMANTICS_CLAIM` 保留，值不变 |
| 其他接口 | — | 不变；错误码表仍为 58 个，retryable 不变 |

本清单 188 条条目的 proves 都不在词表内，改为词表判定后整份 manifest 仍通过 `validate_fixture_manifest_set` 与 `validate_resource_payload`。

#### 对已有测试的修改（按新规则断言，不是削弱）

- `test_A12_r_p11_integrity_limits_complete_stream_claims`：删去“run_stream_complete、fullrun、complete_run 被接受”的断言，这三个与复审列出的其他同义名称一起改为断言拒绝（三种来源类别 × 三种不完整取值）；partial_run_stream 仍断言接受，另加 5 个词表外名称的接受断言；新增词表常量的值断言。
- `test_A12_r_p11_structure_preservation_limits_field_semantics_claims`：删去“field_semantics、protocol_fields 被接受”的断言，改为断言拒绝（连同 5 个同义名称）；field_semantics、protocol_fields 也加入 6 种脱敏组合的逐一断言；另加 5 个词表外名称的接受断言。
- `CleanupOwnershipTests.test_owned_directory_is_removed`：末尾断言由 `assertIsNotNone` 改为精确的 `assertEqual(..., "目标不是目录")`，注释如实说明；注销登记改由新用例检验。

#### 变异抽查

在 tempfile 建的目录中复制 `scripts/`、`schemas/`、`tests/` 与 `docs/code-kit-v2/`，逐一植入 42 个变异。协议侧运行 `ResourceRefTests`、`EventTests`、`ProvenanceTests`（未变异时 `Ran 84 tests`、`OK`）；fixtures 侧运行 `CredentialScanTests`、`CleanupOwnershipTests`、`HarnessCleanupOwnershipTests`、`CompatMatrixDCaseTests`、`R11Tests`（未变异时 `Ran 36 tests`、`OK`）。用后删除目录。

- **被发现（40 个）**：
  - 受控词表 8 个：两条规则分别退回前缀判定、去掉量词规则、去掉词组规则、改为子串匹配、量词不要求运行流对象、字段语义只看 field、去掉语义词干；
  - 复审列出的检查顺序变异 Q01、Q02、Q03、Q05、Q06、P42、P20、P12b，另加 P42b（协议结构规则挪到第 4 步之前）；
  - 凭据扫描：S19（只扫第一个文件）、S06b（删 ASIA），另加删 `gho_`、删 `xoxp-`；S16（去掉熵条件）；新规则的 5 个弱化（Stripe 只认 `sk`、HF 只认小写、Basic 区分大小写、删 GitLab、npm 长度改为 40）；
  - D05（D-20 映射删去 nan 变体）；
  - `_rmtree` 的 C06、C07、C10；
  - harness 的 H01、H02、H03、H05、H06、H07、H08、H09、H10。
- **存活（2 个），都判为等价变异**：
  - H04（根目录是联接也放行）：根目录换成联接后，`os.path.realpath` 解析出的真实路径落在登记区域之外，`_owning_area` 先行拒绝；`_verify_area_root` 在链接检查之前还有“真实路径与创建时相同”一项。单独放宽这一道检查不改变任何可达路径的结果，它是纵深防御。测试 `test_link_target_or_link_root_refused` 仍断言这种情形被拒绝。
  - URL 规则的协议名字符集收窄为 `[a-z][a-z0-9]*`：正则不锚定开头，`git+ssh://` 仍能从 `ssh://` 起匹配，发现能力不变。
- 复审列出的存活变异中，本次复现并确认被发现的有：Q01、Q02、Q03、Q05、Q06、P42、P20、P12b、S19、S06b、S16、D05、C06、C07、C10、H01–H03、H05–H10。复审在 R-P11 上实测能绕过的 complete_run、run_stream_complete、complete_event_stream、full_event_log、entire_run_stream，现在都报 `incomplete_fixture_cannot_prove_complete_stream`。

#### 结果（收尾轮返工）

在仓库中直接运行（不是 `baseline.py capture` 取证，输出没有归档），设 `PYTHONDONTWRITEBYTECODE=1`，并按 R-01 设 `PYTHONPYCACHEPREFIX` 指向运行前新建的空 tempfile 目录（运行后其中没有文件，目录已删除）：

| 命令 | 结果原文 |
|---|---|
| `python tests/test_protocols.py` | `Ran 342 tests in 4.470s` / `OK (skipped=4)`（跳过项不变：F017、F029、F030 与 jsonschema 元校验；新增 1 个测试） |
| `python tests/test_codekit01_fixtures.py -v` | `Ran 75 tests in 14.832s` / `OK`（75 个方法各输出一行 `... ok`，没有跳过项；新增 14 个：`HarnessCleanupOwnershipTests` 11 个、`CleanupOwnershipTests` 3 个。文件符号链接在本机可以创建，两处链接用例都实际运行） |
| `python tests/codekit01_legacy.py --check` | `38 checks, 0 differ` |
| `python tests/codekit01_legacy.py --check-stub-regen` | `10 checks, 0 differ` |
| `python tests/test_legacy_gates.py` | `Ran 24 tests in 185.077s` / `OK` |
| `python tests/test_legacy_events.py` | `Ran 34 tests in 80.694s` / `OK` |

#### 需要规划端知悉的事项（收尾轮返工）

1. **R-P11 的声明词表需要登记**（发现 2、3）：R-P11 没有规定两类声明的名称。本次在产品入口按受控词表拒绝（第 14.2 节第 5 步），词表与三个典型前缀都是实施者选定的，decisions.md 中没有依据。建议规划端在 decisions.md 的 R-P11 或新增勘误行中二选一登记：(a) 采纳本词表；(b) 改为命名规则（“凡表示完整运行流或协议字段语义的声明，必须使用登记的名称”），再由实施者把词表换成登记的名称。无论哪种，词表之外的写法都只能靠登记者自律与复审发现（14.2 节“现行规则的空缺”）。
2. **词表判定比 R-P11 原文宽**：integrity 不是 complete 时，任何以 complet、full、entire、whole、intact 等开头的词元都算完整性声明（例如 `complete_usage_totals`、`fully_redacted`、否定写法 `not_complete_*` 也被拒绝），是保守方向；需要表达“不完整”时用 partial_、truncated_、incomplete_ 开头的名称，或写进 does_not_prove。若不采纳，可把完整性词干也改为要求运行流对象词元（与量词规则相同）。
3. **harness 的 `remove_tree` 只适用于目录**：对区域内的普通文件调用时，`_remove_owned_once` 用 `shutil.rmtree` 删除，报 `NotADirectoryError`，重试 5 次后原样抛出。现有三处调用都传目录，不受影响；为保持 R-P12 内联引用所依赖的 harness 字节（sha256 `c4e87137…`）不变，本次没有修改 harness，只在兼容矩阵 9.2 节登记。
4. **acceptance.md 需要同步**（不在本次可写范围）：第 7 节第 16 项（凭据扫描现在覆盖 15 类形态，清单外的形态不会被发现）；第 7 节第 17 项与第 10 节 R-12（`legacy_harness.py` 的 `remove_tree` 已核对归属，回归测试为 `HarnessCleanupOwnershipTests`；`codekit01_legacy.py` 的 `_rmtree` 另补三项断言）；A12 相关表述（第 5 步按受控词表判定）。
5. **需要重新取证**：`HarnessCleanupOwnershipTests`、修订后的 `CredentialScanTests`、`CleanupOwnershipTests` 与 `test_protocols.py` 的新断言都不在任何归档中。`tests/legacy_harness.py` 的字节在最终取证之后已由收尾轮改变，特征化测试的归档证据绑定的是旧字节。要把结论绑定到当前字节，须按 01-L05 与 R-01 重新取证。
6. **行号**：`protocols.py` 第 3264 行之前不变；之后的行号后移，`_validate_fixture_entry` 3317 → 3374，结构检查 3436-3444，第 3b 步 3488-3493，能力声明循环 3439 → 3496，第 5 步 3511-3519，`validate_fixture_manifest_set` 3488 → 3551，清单级规则 3522 → 3585；受控词表在 3264-3328。`tests/test_codekit01_fixtures.py` 的行号相对兼容矩阵修订 9 的记录后移 11 行以上（例如 `check_synthetic_fixture_claims` 259 → 270，`check_manifest_claims` 277 → 288）。兼容矩阵修订 10 已按当前字节更新；acceptance.md 中的同类引用需要规划端更新。
