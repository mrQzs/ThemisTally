# 07 发布门禁与阶段收尾

## 候选与证据

- 候选提交：`7a29008`（当前离线实现候选；合同基线随后刷新）。
- 远端：`origin/master` 与当前候选一致；工作树核验为干净。
- 当前定向套件：75 项边界测试通过；该结果只覆盖本轮离线边界修补。
- 调度器回归：本轮 Windows `python tests/test_dispatch.py` 长时间无输出后停止，不能形成新的通过证据；此前 Windows/WSL stub 记录分别为 258/263 checks，均是历史本地证据。
- 结构门禁：`python -m compileall -q scripts/codekit tests` 与 `git diff --check` 通过。
- 全量 unittest：没有用本轮未完成的运行宣称通过；此前记录的 1029 项、38 项跳过和 3 项既有源码锁定失败仍不是全绿结果。

## 门禁结果

| 门禁 | 结果 | 说明 |
|---|---|---|
| G1 候选固定且工作树干净 | LOCAL_REFERENCE | `7a29008` 为当前离线实现候选；合同与状态文档仍需随本批提交更新，且缺独立 attempt 快照 |
| G2 定向实现与结构检查 | LOCAL_REFERENCE | 75 项离线边界测试与结构检查通过，不等价于生产阶段通过 |
| G3 旧调度器回归 | NOT_RUN | 本轮调度器回归未完成；历史 stub 结果不能替代当前复核 |
| G4 Pi 环境与执行器证据 | BLOCKED | `step/step-5-preview` 不可用，认证未就绪；没有 attempt 证据 |
| G5 真实 provider/隐藏调用 | NOT_RUN | 仅有离线 provider/economic identity 与 fixture |
| G6 真实 PID/boot/OS 锁和恢复 | NOT_RUN | 仅有纯模型门禁，无 OS adapter |
| G7 09/10 生产投影与连接器 | NOT_RUN | 仅有离线 readiness/outbox 投影 |
| G8 A/F 独立验收 | REVISE/BLOCKED | 没有当前 Pi attempt、原始证据包或独立复审 verdict；A/F 只能保留 LOCAL_REFERENCE/NOT_RUN |

## 当前决议

阶段结论为 `REVISE/BLOCKED`：可以保留并推送离线候选与合同材料；不能宣称 07 全部实现、不能派遣未通过环境预检的 Pi、不能开启真实 provider 或外部连接器。环境恢复后，必须以新基线出合同 v3，重新派遣、独立复审并生成新的 S6 结论。

## 回滚边界

本阶段只引入可审计的离线模块、测试、合同和文档。回滚到上一阶段提交时使用已推送的父提交；不回写 `.agent/runs/` 原始证据，不删除既有合同或环境记录。
