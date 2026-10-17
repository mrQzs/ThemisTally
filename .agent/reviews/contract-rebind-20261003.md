# 01–06 / 08 合同重绑定复审

## 固定基线

- contract base: `6e6cba9caf026e22c11b5026f22525e352e1ed6f`
- contract publication commit: `94aee11d37bb582faba667d145a84dc0412a9d4f`
- review type: 规划端合同结构复审；不是 Pi attempt，也不是生产验收

## 重绑定结果

- 01–06 三子任务共 18 份合同；08 S0–S6 共 21 份合同。
- 每份合同均生成 Markdown/JSON 一对，版本为当前任务已有版本号的下一版。
- 每份合同均绑定真实存在的测试模块，V01 不再使用 `Path.exists()` 文件存在性探针。
- 每份合同均包含 V01 定向 unittest、V02 compileall、V03 `git diff --check`，并明确 `LOCAL_REFERENCE`、`NOT_RUN`、`BLOCKED` 与停止条件。
- `python scripts/pi_dispatch.py validate`：39/39 通过，0 个错误；旧的手工 v3 合同仍作为历史版本保留。

## 证据绑定

- `.agent/runs/offline-01-06-08-20261003-expanded-all-05/`：542 收集、534 通过、8 跳过；capture 绑定基线 `6e6cba9`。
- `.agent/runs/offline-01-06-08-20261003-builtin-all-05/`：102 收集、95 通过、7 跳过；capture 绑定基线 `6e6cba9`。
- 两份 capture 均返回码 0、`execution_status=complete`、`baseline_consistent=true`、无漂移。

## 未执行范围

本轮没有派遣 Pi，也没有运行真实 provider、Windows/macOS 原生进程、外部 09/10 consumer 或生产 dispatcher。合同可派遣性已经建立，但这些能力仍保持 `NOT_RUN/BLOCKED`，不能形成生产 PASS。
