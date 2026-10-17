# 11 S5 边界强化复审（2026-10-04）

## 结论

离线 S5 通过 `LOCAL_REFERENCE`；真实第二 CLI 调用、Pi dispatcher、05 进程清理和重试协调仍为 `NOT_RUN/BLOCKED`。

## 实现

- `PreflightResult` 拒绝字段互相矛盾的伪造 `READY`，包括未支持 profile、阻塞原因、未就绪认证、版本不兼容和模型漂移。
- facade/router 校验 adapter 返回值的类型、adapter/profile/role/platform/session 身份，避免错误 adapter 伪造调用结果。
- malformed handoff、budget、fallback、recovery 输入返回结构化拒绝，不泄露 `AttributeError` 或隐式放行。
- 取消记录新增 `NOT_CANCELLED`，并约束取消、退出、响应丢失和进程观察事实的一致性；RecoveryLedger 保持幂等并拒绝身份漂移。
- 独立发布门禁拒绝非法 evidence key，并要求每个真实条件拥有 ResourceRef 证据。

## 验证

```text
python -B -m unittest tests.test_11_s5_gap_cases tests.test_11_runtime_boundaries tests.test_11_second_cli tests.test_11_schema_fixtures -q
Ran  ... tests ... OK
python -B -m compileall -q scripts/codekit tests
git diff --check
```

相关恢复 Schema 和全部现有第二 CLI Schema 通过 WSL Python 3.12 的 Draft 2020-12 `check_schema`；真实能力不因离线测试通过而升级为生产 PASS。
