# 07 发布门禁与阶段收尾

## 候选与证据

- 候选提交：`a64f3a836f5f5c0ca5f405c2b21efb210086b3e4`（当前离线实现候选；合同基线已刷新）。
- 远端：`origin/master` 与当前候选一致；工作树核验为干净。
- 当前验收矩阵定向套件：398 项通过、8 项跳过（`docs/code-kit-v2/07-acceptance-matrix.md` 中的组合命令）；此前三组 279 项结果仍作为历史分组记录保留。另有 happy/timeout/validate/stuck/budget/preflight/v2 planner 等 dispatch stub 场景通过，但完整调度回归仍未形成通过证据。
- 调度器回归：本轮 Windows `python tests/test_dispatch.py` 长时间无输出后停止，不能形成新的通过证据；此前 Windows/WSL stub 记录分别为 258/263 checks，均是历史本地证据。
- 结构门禁：`python -m compileall -q scripts/codekit tests` 与 `git diff --check` 通过。
- 全量 unittest（排除会长时间无输出的 dispatch 回归）：1067 项、38 项跳过、0 errors；3 项 legacy source-lock 失败仍未解决，因此不是全绿结果。

## 门禁结果

| 门禁 | 结果 | 说明 |
|---|---|---|
| G1 候选固定且工作树干净 | LOCAL_REFERENCE | `a64f3a836f5f5c0ca5f405c2b21efb210086b3e4` 为当前离线实现候选；仍缺独立 attempt 快照 |
| G2 定向实现与结构检查 | LOCAL_REFERENCE | 验收矩阵组合命令 398 项通过、8 项跳过，且 compileall/diff check 通过；不等价于生产阶段通过 |
| G3 旧调度器回归 | NOT_RUN | 本轮调度器回归未完成；历史 stub 结果不能替代当前复核 |
| G4 Pi 环境与执行器证据 | NOT_RUN | 最新 doctor 已确认 `bb/step-5-preview` 可用且认证 ready；按路线图约束本轮未运行 smoke 或派遣，因此没有 attempt 证据 |
| G5 真实 provider/隐藏调用 | NOT_RUN | 仅有离线 provider/economic identity 与 fixture |
| G6 真实 PID/boot/OS 锁和恢复 | NOT_RUN | 仅有纯模型门禁，无 OS adapter |
| G7 09/10 生产投影与连接器 | NOT_RUN | 仅有离线 readiness/outbox 投影 |
| G8 A/F 独立验收 | REVISE/BLOCKED | 没有当前 Pi attempt、原始证据包或独立复审 verdict；A/F 只能保留 LOCAL_REFERENCE/NOT_RUN |

## 当前决议

阶段结论为 `REVISE/BLOCKED`：可以保留并推送离线候选与合同材料；不能宣称 07 全部实现；本轮按路线图约束不派遣真实 Pi，不开启真实 provider 或外部连接器。环境恢复后，必须以新基线出合同 v3，重新派遣、独立复审并生成新的 S6 结论。

## 回滚边界

本阶段只引入可审计的离线模块、测试、合同和文档。回滚到上一阶段提交时使用已推送的父提交；不回写 `.agent/runs/` 原始证据，不删除既有合同或环境记录。


## 最新离线候选记录

`cf3a1cdff2302cfb89c3efbcfdc53d78b8f4be5b` 收紧运行时进程身份与租约边界，补充显式 `NOT_STARTED` 回放和仅可修复截断尾的持久投影恢复，并强化 09/10 投影的严格 JSON、来源向量、健康状态和问题列表一致性。组合验收命令扩展为 348 项通过、1 项跳过；运行时/投影定向套件 62 项通过，compileall 与 diff check 通过。该结果仍是 `LOCAL_REFERENCE`，没有 Pi attempt、真实 provider、原生平台或 09/10 生产连接器证据；最新环境虽可派遣，但执行门仍保持 `NOT_RUN`。


## 最新离线候选记录

`a64f3a836f5f5c0ca5f405c2b21efb210086b3e4` 收紧 atomic/budget/scheduler outbox 的严格 JSON、连续序列、请求/操作闭包和数据库范围 high-water；插件与业务 artifact 统一拒绝控制字符、代理字符、不安全整数和超大 canonical bytes，ResourceRef/manifest/lock 路径在摘要前规范化，离线配方拒绝网络命令与 URL。组合验收命令为 398 项通过、8 项环境跳过；新增账本/插件定向套件通过。该结果仍是 `LOCAL_REFERENCE`，环境虽已可派遣但本轮按约束未运行真实 Pi/provider，生产门禁继续关闭。

`python3 -m unittest` 在 Git Bash Python 3.12.3 上复核同一 398 项组合套件为 398 项通过、1 项跳过；Windows Python 3.9.23 的 8 项跳过来自环境能力差异。WSL/3.12 schema 实例 7 项全部通过。该复核仍是离线本地证据。
