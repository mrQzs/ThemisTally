# 12 集成记录离线复审（2026-10-04）

状态：`LOCAL_REFERENCE`。本复审固定离线候选和调用方提供的证据，不启动 collector、provider、进程或外部连接器。

## 实现范围

- `scripts/codekit/integration_records.py` 提供 `IntegrationTarget`、`CheckCatalog`、`CheckObservation`、`EvidenceManifest`、`CoverageReport`、`DeliveryDecision` 及闭集校验别名。
- `ResourceRef`、成员列表、候选、环境、观察和证据清单使用严格闭合字段、路径约束、大小/深度限制、确定性 JSON 字节和 SHA-256。
- 覆盖分母来自可信 `CheckCatalog`；`NOT_RUN`、`STALE`、`INCOMPLETE`、`WAIVED` 和缺证据不会被归约为 PASS。
- `DeliveryDecision` 明确固定 `dispatch_authorized=false`、`integration_authorized=false`，不授予批准、执行、预算、提交或发布权限。

## 验证

```text
python -B -m unittest tests.test_12_integration_records tests.test_integration_gates -q  # 27 项通过
python -B -m compileall -q scripts/codekit tests                                      # 通过
git diff --check                                                                       # 通过
wsl python3 ... Draft202012Validator.check_schema                                          # integration-records-v1 通过
```

## 结论与限制

集成记录、覆盖归约、WAIVED exception、候选/环境闭包和最小负例均有定向证据。真实三平台、第二 CLI、Pi/provider、受信采集器、外部 09/10 连接器和生产目标项目仍为 `NOT_RUN/BLOCKED`；离线记录不能提升为生产发布 PASS。

