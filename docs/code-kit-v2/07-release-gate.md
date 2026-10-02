# 07 发布门禁与阶段收尾

## 候选与证据

- 候选提交：`a2357b0`（S3.2/S5.3 实现候选；本审计文档另有审计提交）。
- 远端：`origin/master` 已与本文件所在最新审计提交一致；工作树干净。
- 定向套件：272 项通过，1 项跳过。
- 调度器回归：`python tests/test_dispatch.py`，255 checks，0 failed。
- 结构门禁：`python -m compileall -q scripts/codekit tests` 与 `git diff --check` 通过。
- 全量 unittest：895 项，31 项跳过，1 项已知环境失败（Python 3.9 不提供 `sys.stdlib_module_names`，影响 F049 导入副作用探针）。

## 门禁结果

| 门禁 | 结果 | 说明 |
|---|---|---|
| G1 候选固定且工作树干净 | PASS | `a2357b0` 实现候选已纳入当前审计提交；本地与远端一致 |
| G2 定向实现与结构检查 | PASS | 定向套件、compileall、diff check 均通过 |
| G3 旧调度器回归 | PASS | 255 checks，0 failed |
| G4 Pi 环境与执行器证据 | BLOCKED | `step/step-5-preview` 不可用，认证未就绪；没有 attempt 证据 |
| G5 真实 provider/隐藏调用 | NOT_RUN | 仅有离线 provider/economic identity 与 fixture |
| G6 真实 PID/boot/OS 锁和恢复 | NOT_RUN | 仅有纯模型门禁，无 OS adapter |
| G7 09/10 生产投影与连接器 | NOT_RUN | 仅有离线 readiness/outbox 投影 |
| G8 A/F 独立验收 | ACCEPTED_WITH_EXCEPTION | A 项至多 LOCAL_PARTIAL，F 项为 LOCAL_PARTIAL/NOT_RUN；不能发布为生产完成 |

## 当前决议

阶段收尾结论为 `ACCEPTED_WITH_EXCEPTION`：可以保留并推送离线候选与审计材料；不能宣称 07 全部实现、不能派遣未通过环境预检的 Pi、不能开启真实 provider 或外部连接器。环境恢复后，必须以新基线出合同 v2，重新派遣、独立复审并生成新的 S6 结论。

## 回滚边界

本阶段只引入可审计的离线模块、测试、合同和文档。回滚到上一阶段提交时使用已推送的父提交；不回写 `.agent/runs/` 原始证据，不删除既有合同或环境记录。
