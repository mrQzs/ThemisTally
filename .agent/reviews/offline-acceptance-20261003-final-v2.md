# 2026-10-03 最终离线候选复审（规划端）

## 固定候选

- candidate: `8c16333ff8d3b80eda8c95216d1236d9f3fe23cf`
- remote: `origin/master`
- review type: 固定工作树的规划端复核；不是 Pi attempt，也不是 `review-pi` verdict

## 原始证据

1. `.agent/runs/offline-01-06-08-20261003-builtin-all-04/`
   - 命令：`python -B -m unittest discover -s tests -p "test_builtin_*.py" -q`
   - `Ran 102 tests`、`OK (skipped=7)`；95 项执行通过，7 项为 Windows 环境缺少可选 Schema 依赖。
2. `.agent/runs/offline-01-06-08-20261003-expanded-all-04/`
   - 01–06/08 离线扩展组合，包含全部实际 `test_builtin_*` 模块。
   - `Ran 542 tests`、`OK (skipped=8)`；534 项执行通过，8 项为可选 Schema 依赖。

两份 capture 的 `run.returncode=0`、`execution_status=complete`、`comparison.baseline_consistent=true`、`timed_out=false`，且漂移为空。`compileall` 与 `git diff --check` 在提交前通过。

## 复审结论

- `LOCAL_REFERENCE`：上述离线测试覆盖的 recipe DAG/catalog 绑定、docs-change scope 与状态重放、review readiness 输入闭包，以及授权/配置边界。
- `REVISE`：大多数 01–06/08 合同仍需 v3+ 合同绑定实际测试函数、固定候选和故障输入；既有合同中存在文件存在性检查或不存在的测试路径，不能据此放行。
- `NOT_RUN/BLOCKED`：当前候选没有 Pi attempt；真实 Pi/provider、Windows/macOS 原生进程、外部 09/10 consumer、生产 dispatcher、真实计费和恢复故障演练均未运行。
- 历史全量发现中的三项 `a4fa199` source-lock 失败仍是既有锁定事实；本轮没有重新运行全量发现，不将其改写成新失败或新通过。

最终阶段结论：`REVISE/BLOCKED`。离线候选和证据可继续作为下一阶段合同基线，生产发布门禁保持关闭。
