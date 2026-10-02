# 07 本地实现独立复核记录

日期：2026-10-02。复核对象：工作区相对基线 `02ca295` 的 S1–S5 离线候选、S3.2 用量结算、S5.3 集成门禁及 S6 审计产物；最终远端提交为 `cbf0e38`。

## 建议结论

`ACCEPTED_WITH_EXCEPTION`：定向测试、编译和差异检查通过；纯模型与 SQLite 证据可以作为 `LOCAL_PARTIAL`。Pi doctor 阻塞，生产连接器与跨平台进程锁没有验收证据。

## 证据

- 扩展定向套件（含 `tests.test_integration_gates` 与 `tests.test_usage_settlement`）：272 项通过，1 项明确跳过。
- `python -m unittest discover -s tests -q`：895 项，31 项跳过；唯一失败是 Python 3.9 缺少 `sys.stdlib_module_names` 的既知 F049 环境探针。
- `python tests/test_dispatch.py`：255 checks，0 failed。
- `python -m compileall -q scripts/codekit tests`：通过。
- `git diff --check`：通过。

## 例外与后续

统一账本、用量结算和集成门禁仍是候选迁移层，不替换现有线上权威存储；attempt、cursor、migration 的生产迁移、outbox 消费 projection 和崩溃故障注入仍未运行。provider 适配器为离线 fixture，不读取凭据、不调用网络，不证明隐藏调用已被发现。A/F 逐项状态与生产/离线区分见 `docs/code-kit-v2/07-acceptance-matrix.md` 和 `07-fault-matrix.md`。
