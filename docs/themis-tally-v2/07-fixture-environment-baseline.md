# Code-Kit v2 Fixture 与环境基线

## 可复现检查

| 检查 | 命令 | 结果 |
|---|---|---|
| 07 定向原型 | python -m unittest tests.test_workflow tests.test_readiness tests.test_baseline_binding tests.test_git_probe tests.test_git_ancestor tests.test_coverage tests.test_claim_model tests.test_scheduler_store tests.test_parallel tests.test_budget tests.test_budget_store_v2 tests.test_retry tests.test_atomic_claim_budget tests.test_acceptance tests.test_recovery | 195 tests OK |
| 调度器回归 | python tests/test_dispatch.py | 255 checks，0 failed |
| 编译 | python -m compileall -q scripts/codekit tests | 通过 |
| 差异检查 | git diff --check | 通过 |

## 现有离线夹具

- workflow 合法样本：tests/fixtures/workflow/valid.json
- workflow/schema、readiness、baseline binding、acceptance、coverage：使用内存对象和固定 ref。
- Git probe：使用注入式 ProbeRunner，不执行 fetch、checkout 或 lazy fetch。
- claim/budget/atomic ledger：使用 SQLite :memory: 和临时数据库，测试事务、幂等、unknown、stop、rollover。
- provider 适配：S3.3 新增的 fixture 必须只读 fixture bytes/records，不联网、不读环境变量、不访问凭据。

## 环境事实

- 当前 Windows 主工作区：Python 3.9.23；Git 2.52.0.windows.1。
- Git Bash 运行时：Python 3.12.3；定向 195 项同样通过。
- Pi doctor：pi 可执行入口依赖的 Node 未在当前 WSL 环境可用；模型列表为空，认证检查退出 127；因此 Pi 当前不可派遣。
- .agent/environment.md 已记录环境事实；不得在其中写入 API key、token 或完整环境变量。

## 未运行能力

Windows/macOS/WSL 进程残留、OS 强杀/断电、真实 provider 账单、真实 03–10 接线、WAL/网络文件系统、跨平台路径别名和 F01–F30 故障注入均保持 NOT_RUN，直到对应环境与合同可用。
