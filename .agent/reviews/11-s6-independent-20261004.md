# 11 S6 独立审计（离线候选，2026-10-04）

审计基线为已提交的 `dc869ca`（包含 S4/S5 离线补强）；本审计没有调用真实模型、provider、Pi、05 进程或外部连接器。

## 结论

结论为 **REVISE / 生产门禁 BLOCKED**。

S6 的离线边界现在有可复核测试：独立发布门禁的闭合记录形状、缺少真实事实时的阻塞、非法 evidence key、`READY` preflight 的内部一致性，以及 planner runtime A / executor runtime B 与反向组合的 profile、adapter、session 和 handoff 绑定。测试中的“完整发布门禁”仅验证控制器输入齐全时的确定性记录形状；布尔事实和 ResourceRef 由外部控制器提供，离线 fixture 不能作为真实发布证据。

## A 项状态

| 项 | 状态 | 证据与限制 |
|---|---|---|
| A01 | PARTIAL | facade、router 和双方向异构 profile 测试通过；未接入生产 dispatcher。 |
| A02 | PARTIAL | capability snapshot、preflight 和身份漂移拒绝已覆盖；未核验真实模型、认证或目标平台。 |
| A03 | PARTIAL | 畸形、截断、未知终止、重复终态和非零退出离线拒绝已有证据。 |
| A04 | PARTIAL | 配置模型不能替代事件模型；`READY` 记录的内部一致性由 preflight 构造器约束。真实模型未运行。 |
| A05 | PARTIAL | 原始记录引用、半开范围、闭合事件和资源闭包已有实现；持久 spool 与生产跨进程回查未接入。 |
| A06 | BLOCKED | 没有一组真实不同 CLI 的规划→审核→执行→验收链路证据。 |
| A07 | BLOCKED | 真实入口、shell、取消、进程和环境锁没有运行。 |
| A08 | PARTIAL | unknown 用量、认证缺失、版本不兼容、fallback/recovery 输入已有离线状态；真实认证和版本回退未运行。 |

## F 项和发布门禁

F01–F10 的离线负例可以作为 `LOCAL_REFERENCE`；真实第二 CLI、provider、平台进程、取消、计量和宿主接线仍为 `NOT_RUN/BLOCKED`。`evaluate_independent_release_gate` 要求每个真实条件都有对应证据引用，但它只能验证调用方提交的事实和引用，不能把 fixture 自己升级为真实来源。因此本审计不关闭生产发布门禁。

## 验证

```text
python -B -m unittest tests.test_11_s6_matrix -q
Ran 5 tests ... OK
python -m compileall -q scripts/codekit tests
git diff --check
```

主模型已在合并 S4/S5 改动后重跑 11 定向回归；当前实现头仍需在阶段提交后更新。真实 provider、Pi、05 原生 runner、Windows/macOS 和外部连接器必须在另行授权和具备证据后才能转为 PASS。
