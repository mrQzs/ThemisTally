# Code-Kit v2：09 追踪矩阵

基线：`330d3716d65e068c38a5861e2a1a4bf4c84cf043`。附件 09 设计文档只作为需求参考；授权和执行范围以 `AGENTS.md` 与对应合同为准。

## 记录规则

- `A01–A28` 是离线可验收项；每个条目必须有代码/fixture、定向测试和 `.agent/runs/` 证据。
- `I01–I30` 是真实集成/故障矩阵；不能用 mock 或离线 PASS 伪装生产证据，缺少真实能力时填 `NOT_RUN` 或 `BLOCKED`。
- `LOCAL_REFERENCE` 表示可复核的离线实现或录制结果，不授予批准、执行、计费或发布权限。
- 下表 `A01–A28` 沿用附件增强版的原始验收编号；“合同覆盖”是本轮内部映射，允许一个验收项跨多个合同，不能把合同编号当作通过结论。

## A 项追踪

| ID | 合同覆盖 | 原始验收主题 | 状态 |
|---|---|---|---|
| A01 | `09-s1-1` | 规划器返回任务图与结构化草稿，事实与建议分开；来源不存在或未决设计明确暴露 | PARTIAL |
| A02 | `09-s1-1 / 09-s4-2` | 空、截断、畸形或矛盾 bundle 不发布；格式修复有次数和 request 总预算上限 | PARTIAL |
| A03 | `09-s5-2` | planner 不直接写 `.agent/plans/` 或 `.agent/runs/`；任意输出路径被拒绝或忽略 | PARTIAL |
| A04 | `09-s5-2` | 未审 setup/check 只静态校验；发布前探针必须是单独受审阅请求 | PARTIAL |
| A05 | `09-s3-1` | 假 approved、旧审核或自声明 supervisor 身份无法发布合同 | PARTIAL |
| A06 | `09-s0-2 / 09-s4-1` | 未来任务不伪造基线；上游无可用提交或授权时等待；满足可细化条件即可起草 | PARTIAL |
| A07 | `09-s3-1 / 09-s3-3` | 有效审核原样发布成对合同；审核 ID 不回填改写字节；输入或规则改变后拒绝旧审核 | PARTIAL |
| A08 | `09-s1-1 / 09-s5-3` | 规划与执行使用不同 stub 适配器可交接，不依赖共享会话或模型默认值 | GAP |
| A09 | `09-s3-2 / 09-s4-3` | 发布中断不会出现可派遣半成品；重启可识别已发布版本且不覆盖历史版本 | PARTIAL |
| A10 | `09-s0-1 / 09-s6-1` | 旧人工合同仍可按既有入口处理，普通执行器保护范围和证据不可变规则不退化 | LOCAL_REFERENCE |
| A11 | `09-s0-2 / 09-s1-3` | 请求上下文、预算根、目标 task 与输入引用错配时拒绝；planner 不能分配版本或路径 | PARTIAL |
| A12 | `09-s1-1 / 09-s4-1` | 调查基线与未来合同基线分开；模板无假 SHA；上游就绪不会自动获得模型调用权限 | PARTIAL |
| A13 | `09-s1-2` | 事实引用校验完整资源、字节坐标和片段摘要；来源存在不被标为语义支持已证实 | PARTIAL |
| A14 | `09-s1-1` | 调查不完整、来源冲突和缺失事实明确暴露；未决设计未经真实决定不能关闭 | PARTIAL |
| A15 | `09-s1-2 / 09-s1-3` | 两层图分别校验；类型映射、需求覆盖与平台检查缺口不会靠样例或自然语言补齐 | PARTIAL |
| A16 | `09-s1-2 / 09-s5-1` | 核心只接受唯一来源明确的最终结果；重放与多份输出区分；截断不修拼成正式合同 | LOCAL_REFERENCE |
| A17 | `09-s2-1` | 正式 task 名称跨 request 冲突被拒；版本槽幂等且不复用，旧版本不倒退 current head | PARTIAL |
| A18 | `09-s2-2 / 09-s3-1` | MD/JSON、渲染器、输入闭包和目标路径均在冻结前确定；字节变化使原审核不可复用 | PARTIAL |
| A19 | `09-s2-3 / 09-s3-1` | 发布候选必须有两个正确成员；源位置与最终位置映射经过审核，不接受任意重定向 | PARTIAL |
| A20 | `09-s3-2` | 发布事务的记录、head、幂等和事件一致；冲突、竞争和响应丢失不会双发布 | PARTIAL |
| A21 | `09-s3-2 / 09-s3-3` | 登记成功但只存在一份文件时所有执行入口拒绝；目录扫描不能绕过 | PARTIAL |
| A22 | `09-s2-1 / 09-s3-1` | 恢复仅恢复精确原字节；已撤销、被替代或输入过期的审核不会复活 | PARTIAL |
| A23 | `09-s2-2 / 09-s4-2` | 修复次数有机械上限，结构修复不静默改变模型、权限、图、基线或关键检查 | PARTIAL |
| A24 | `09-s2-2 / 09-s4-1` | 所有规划、修复、细化、调查调用同 request 计量；unknown 费用与 START_UNKNOWN 不被当免费重试 | PARTIAL |
| A25 | `09-s2-3 / 09-s5-2` | planner 只读能力分级有真实负例；工作目录、工具声明、受控入口不冒充 OS 隔离 | PARTIAL |
| A26 | `09-s5-3` | 执行器在独立会话中只靠固定合同与资源工作，不需要 planner 历史对话 | GAP |
| A27 | `09-s0-1 / 09-s6-1` | 旧人工路径可用但 v2 来源不可改标签退回 v1；旧证据完整字节保持不变 | LOCAL_REFERENCE |
| A28 | `09-s0-2 / 09-s6-2` | 草稿、审核、发布与执行状态分别恢复；控制器交接不会重复启动或重写历史合同 | PARTIAL |

合同覆盖映射按增强版原始 `09-A01–09-A28` 记录；旧合同中的阶段编号是执行边界，不代表单项已通过。

## I 项追踪

| ID | 契约 | 集成/故障主题 | 离线证据或环境记录 | 状态 |
|---|---|---|---|---|
| I01 | `09-s0-1` | v1 来源路由 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I02 | `09-s0-1` | 旧证据保护 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I03 | `09-s0-1` | 降级绕过拒绝 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I04 | `09-s0-2` | 字段状态投影 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I05 | `09-s0-2` | outbox 注册顺序 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I06 | `09-s0-2` | cursor 重建 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I07 | `09-s0-3` | 重复/截断终态 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I08 | `09-s0-3` | Invocation 资源允许集 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I09 | `09-s0-3` | 跨会话交接 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I10 | `09-s0-3` | 真实 provider 阻塞 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I11 | `09-s1-1` | 请求预算根 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I12 | `09-s1-1` | 绑定基线 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I13 | `09-s1-1` | 格式修复上限 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I14 | `09-s1-2` | SourceAnchor 错位 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I15 | `09-s1-2` | 尾随 JSON | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I16 | `09-s1-2` | 事实支持不足 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I17 | `09-s1-3` | 输入漂移 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I18 | `09-s1-3` | 只读能力边界 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I19 | `09-s1-3` | DAG 环检测 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I20 | `09-s2-1` | plan currentness | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I21 | `09-s2-1` | head CAS 竞争 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I22 | `09-s2-2` | 半合同成员 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I23 | `09-s2-2` | 渲染字节漂移 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I24 | `09-s2-3` | 候选摘要伪造 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I25 | `09-s3-1` | 撤销审核 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I26 | `09-s3-2` | 登记幂等 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I27 | `09-s3-3` | 响应丢失恢复 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I28 | `09-s4-3` | START_UNKNOWN | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I29 | `09-s4-3` | 未知终止 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |
| I30 | `09-s5-3` | 原生平台/外部连接器 | 注入 fixture 或 `.agent/environment.md` 记录 | NOT_RUN/BLOCKED |

## 门禁结论

- 只有 A 项离线证据齐全且 I 项逐项有故障注入或明确阻塞记录时，阶段才可进入独立复审。
- S6 之前不得迁移生产连接器；S6 也只能输出 release gate，不能把 `NOT_RUN/BLOCKED` 改成 PASS。
- 若合同 Scope、基线或接口变化，必须出新版本合同并保留旧版本。

## 当前离线证据状态

离线实现的状态按逐项复审记录为 PARTIAL、LOCAL_REFERENCE 或 GAP，不把未覆盖的生产语义标成 PASS。LOCAL_REFERENCE 项包括严格唯一结果提取、候选双成员校验和 v1/v2 兼容门；A08/A26 的独立执行器交接仍为 GAP。03 ApprovalLedger currentness/revocation 已提供可选离线接线并有撤销回归，真实 provider、Pi、原生平台和外部连接器仍为 NOT_RUN/BLOCKED。