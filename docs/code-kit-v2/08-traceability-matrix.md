# 08 验收追踪矩阵

状态含义：`PLANNED` 表示已有合同但未执行；`LOCAL_REFERENCE` 只表示离线参考覆盖；`NOT_RUN` 表示缺少真实接线；`BLOCKED` 表示环境或前置条件缺失。任何状态都不能替代生产 PASS。

## 原有验收项

| ID | 责任合同 | 验证焦点 | 初始状态 |
|---|---|---|---|
| 08-A01 | 08-s2-3 | manifest、lock、DAG、阶段类型，检查无循环 | PLANNED |
| 08-A02 | 08-s2-1/2/3 | 原缺陷、正确修复、失败修复对照 | PLANNED |
| 08-A03 | 08-s3-2/3 | 坏链接与错误内容独立拒绝 | PLANNED |
| 08-A04 | 08-s4-1/2/3 | 有效回归与受控变异 | PLANNED |
| 08-A05 | 08-s0-2/08-s5-1 | 核心范围、授权和门禁不可绕过 | PLANNED |
| 08-A06 | 08-s2-3/08-s5-1 | 未审草稿无 setup/check 副作用 | PLANNED |
| 08-A07 | 08-s0-2/08-s6-1 | 不绑定 Pi/Step 品牌 | PLANNED |
| 08-A08 | 08-s5-2 | 声明平台有检查或具体阻塞 | PLANNED |
| 08-A09 | 08-s0-3/08-s5-1 | 离线检查不调用模型、网络或已有 runs | PLANNED |

## 增强验收项

| ID | 责任合同 | 验证焦点 | 初始状态 |
|---|---|---|---|
| 08-A10 | 08-s2-1 | 来源与字节坐标完整 | PLANNED |
| 08-A11 | 08-s1-2 | 相关漂移失效、无关变化不误伤 | PLANNED |
| 08-A12 | 08-s2-2 | 新旧文件两端、删除、新增、模式和链接 | PLANNED |
| 08-A13 | 08-s1-2/08-s5-1 | 候选、检查集、环境精确绑定 | PLANNED |
| 08-A14 | 08-s4-1 | 未收集、skip/xfail、零测试不通过 | PLANNED |
| 08-A15 | 08-s4-2 | 变异使用同一测试和可比环境 | PLANNED |
| 08-A16 | 08-s4-3 | 参考失败、存活变异和环境失败分离 | PLANNED |
| 08-A17 | 08-s4-3 | 重复反测全部保留，不使用 best-of | PLANNED |
| 08-A18 | 08-s3-2 | AST 区分代码、引用、图片和链接 | PLANNED |
| 08-A19 | 08-s3-2 | 相对路径、越界、控制字符和危险 scheme | PLANNED |
| 08-A20 | 08-s3-2 | Markdown/render profile 明确 | PLANNED |
| 08-A21 | 08-s3-3 | 外链未访问，内容复审仍可拒绝 | PLANNED |
| 08-A22 | 08-s0-2/08-s5-1 | 确定性检查不启动模型 | PLANNED |
| 08-A23 | 08-s1-2 | 技能源和派生快照 provenance | PLANNED |
| 08-A24 | 08-s2-3 | 草稿编译纯静态 | PLANNED |
| 08-A25 | 08-s4-2/3 | 副本、缓存和残留不污染候选 | PLANNED |
| 08-A26 | 08-s5-3 | 发布/登记失败与响应丢失可恢复 | PLANNED |
| 08-A27 | 08-s1-3/08-s6-3 | 伪造报告、错误检查集和未授权字段拒绝 | PLANNED |
| 08-A28 | 08-s6-1/3 | 七插件、三配方支持/限制/证据完整 | PLANNED |

## 集成与故障矩阵

| ID | 责任合同 | 场景 | 初始状态 |
|---|---|---|---|
| T01 | 08-s1/2 | 三组合 manifest、workflow、lock、类型校验 | NOT_RUN |
| T02 | 08-s2 | 原缺陷、正确修复、失败修复 | LOCAL_REFERENCE |
| T03 | 08-s3 | 坏链接与错误内容 | LOCAL_REFERENCE |
| T04 | 08-s4 | 有效测试、空测试和变异 | LOCAL_REFERENCE |
| T05 | 08-s2/5 | 未审草稿 setup 不启动 | NOT_RUN |
| T06 | 08-s1/5 | 插件伪造 PASS 或审核字段 | LOCAL_REFERENCE |
| T07 | 08-s6 | 两个受支持 profile 切换 | NOT_RUN |
| T08 | 08-s5 | 非当前平台缺检查实现 | LOCAL_REFERENCE |
| T09 | 08-s5 | Windows 原生无 Bash | BLOCKED |
| T10 | 08-s5 | macOS 原生 shell/路径 | BLOCKED |
| T11 | 08-s2 | UTF-8 来源坐标错误 | LOCAL_REFERENCE |
| T12 | 08-s1/2 | 调查输入变更后缓存失效 | NOT_RUN |
| T13 | 08-s2 | 受保护文件重命名或范围外删除 | LOCAL_REFERENCE |
| T14 | 08-s1/5 | 候选 K→K2 不复用检查 | LOCAL_REFERENCE |
| T15 | 08-s4 | 目标测试缺失、skip、xfail | LOCAL_REFERENCE |
| T16 | 08-s4 | conftest/环境插件/发现变化 | NOT_RUN |
| T17 | 08-s4 | 语法/导入错误不算反测失败 | LOCAL_REFERENCE |
| T18 | 08-s4 | 反例更换测试或 runner | LOCAL_REFERENCE |
| T19 | 08-s5 | 超时、取消、日志丢失 | LOCAL_REFERENCE |
| T20 | 08-s4 | 重复运行结果冲突 | LOCAL_REFERENCE |
| T21 | 08-s3 | 引用式链接、图片、代码围栏 | LOCAL_REFERENCE |
| T22 | 08-s3 | 编码穿越、反斜杠、危险 scheme | LOCAL_REFERENCE |
| T23 | 08-s3 | 自动锚点、目录路由、MDX | LOCAL_REFERENCE |
| T24 | 08-s3 | 本地链接正确但业务说明错误 | LOCAL_REFERENCE |
| T25 | 08-s1/6 | 技能源同步后派生副本漂移 | NOT_RUN |
| T26 | 08-s4/5 | 检查改写源码、测试或配置 | NOT_RUN |
| T27 | 08-s4/5 | 反测残留或 scratch 污染 | NOT_RUN |
| T28 | 08-s5 | 完成后登记响应丢失 | BLOCKED |
| T29 | 08-s5 | handoff 后调度器崩溃 | BLOCKED |
| T30 | 08-s6 | v2 停用、旧入口继续、历史保留 | NOT_RUN |

## 规划端复核后的当前状态

上表的“初始状态”保留合同建立时的基线。当前复核结论如下：

- `LOCAL_REFERENCE`：A02–A04、A10、A12、A18–A21、A23–A25，以及 T02–T04、T06、T08、T11、T13–T15、T17–T24；这些条目有离线纯函数、fixture、显式 argv runner 或持久 journal 证据，但没有核心 dispatcher、真实候选或平台证据。
- `REVISE/BLOCKED`：A01、A05–A09、A11、A13–A17、A22、A26–A28，以及 T01、T05、T07、T12、T16、T25–T30；核心 dispatcher 绑定的可信候选与环境身份、真实测试/变异执行、生产 outbox/consumer、发布 CAS 和 handoff 响应丢失恢复尚未闭合。
- 真实 Pi、provider、Windows/macOS 原生进程和 09/10 连接器统一为 `BLOCKED/NOT_RUN`。任何离线 `PASS` 只能作为 `REFERENCE_ONLY`，不能转成生产发布 PASS。
