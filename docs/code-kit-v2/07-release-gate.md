# 07 发布门禁与阶段收尾

当前固定代码候选为 `eae9bfca4cf7351b02b7b5eafd6f101664b418ee`，合同发布提交为 `db46200d75ff1462837996bab7450e09a9a88f46`；下方早期候选段落保留为历史记录，最新离线复核见文末。

## 候选与证据

- 历史候选提交：`ef5ff25e9f41cea1096f75d31b027ef4dafcb66b`（合同基线已刷新）。
- 远端：`origin/master` 已包含当前候选及其后续文档提交；工作树核验为干净。
- 当前验收矩阵定向套件：478 项通过、8 项跳过（`docs/code-kit-v2/07-acceptance-matrix.md` 中的组合命令）；此前三组 279 项结果仍作为历史分组记录保留。另有 happy/timeout/validate/stuck/budget/preflight/v2 planner 等 dispatch stub 场景通过，但完整调度回归仍未形成通过证据。
- 调度器回归：本轮 Windows `python tests/test_dispatch.py` 长时间无输出后停止，不能形成新的通过证据；此前 Windows/WSL stub 记录分别为 258/263 checks，均是历史本地证据。
- 结构门禁：`python -m compileall -q scripts/codekit tests` 与 `git diff --check` 通过。
- 全量 unittest（排除会长时间无输出的 dispatch 回归）：1067 项、38 项跳过、0 errors；3 项 legacy source-lock 失败仍未解决，因此不是全绿结果。

## 门禁结果

| 门禁 | 结果 | 说明 |
|---|---|---|
| G1 候选固定且工作树干净 | LOCAL_REFERENCE | 代码候选 `eae9bfca4cf7351b02b7b5eafd6f101664b418ee` 与合同发布提交 `db46200d75ff1462837996bab7450e09a9a88f46` 已推送且工作树干净；仍缺独立 attempt 快照 |
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

`dda848ddfadd28bb06ac8c5b603623f06a54c767` 继续收紧 adapter 事件闭集与安全整数、离线未知/错误终止、配置快照与平台覆盖、ResourceClaim 身份文本，以及授权 ResourceRef 和严格 JSON 输入边界；定向边界回归 105 项通过，组合套件保持 398 项通过、8 项环境跳过。该结果仍是 `LOCAL_REFERENCE`，没有 Pi/provider/native/connector 证据。

`24760ceec4c3350327a0cf194c58a48a9d9cabf2` 收紧统一账本 attempt/migration 状态边界、refund call_key 幂等和跨 operation 归属，并加固 builtin projection 与持久 journal 的文本、计数、generation/CAS 和生命周期安全整数 fence；扩展组合验收为 474 项通过、8 项环境跳过。该结果仍是 `LOCAL_REFERENCE`，没有 Pi/provider/native/connector 证据。

`ef5ff25e9f41cea1096f75d31b027ef4dafcb66b` 进一步统一旧 projections readiness/outbox 接口的 C1/代理字符、generation/cursor 安全整数和 event_id 早期拒绝；扩展组合验收为 478 项通过、8 项环境跳过。该结果仍是 `LOCAL_REFERENCE`，没有 Pi/provider/native/connector 证据。

## 2026-10-03 最新门禁记录

`ffce46b5400d1688ecb25bc754c487db3a1f05dc` 已推送到 `origin/master`。当前扩展组合为 484 项收集、476 项通过、8 项环境跳过；完整发现为 1164 项收集、38 项跳过和 3 项既有 legacy source-lock 失败。stub dispatch、compileall、diff-check 与 WSL Schema 复核均已用新的 baseline capture 记录，取证路径和命令见 `docs/code-kit-v2/07-acceptance-matrix.md` 最新条目。

本提交只推进离线边界：lease、资源 claim、retry 和 workflow Schema 的拒绝规则已跨运行时、账本和 Schema 对齐。G1/G2 仍为 `LOCAL_REFERENCE`；G3 的当前 stub 回归已通过但不是生产 dispatcher 证据；G4–G7（真实 Pi/provider、原生 OS、09/10）继续 `NOT_RUN/BLOCKED`；G8 继续 `REVISE/BLOCKED`，因为尚无 Pi attempt 和规定的独立复审 verdict。合同审计仍发现 01-2、08-s5-1、08-s6-3 的部分检查需要下一合同版本绑定实际测试函数和故障输入，不能用文件存在性结论放行阶段。

## 2026-10-03 最终离线门禁记录

`e8935e84f9b6c196394ac576115317ef3b2e1d1d` 已推送。插件全集为 102 项收集、95 项通过、7 项可选 Schema 依赖跳过；01–06/08 扩展组合为 542 项收集、534 项通过、8 项跳过。证据目录分别为 `.agent/runs/offline-01-06-08-20261003-builtin-all-03/` 和 `.agent/runs/offline-01-06-08-20261003-expanded-all-03/`，两者均无 baseline drift。

G1/G2 可保留为离线 `LOCAL_REFERENCE`；G3 当前候选没有新的 dispatch capture，G4–G7（Pi/provider、原生平台、09/10）继续 `NOT_RUN/BLOCKED`，G8 继续 `REVISE/BLOCKED`。离线测试通过不授予生产执行、批准或发布权限。

## 2026-10-03 最终候选（C1 边界修复后）

`8c16333ff8d3b80eda8c95216d1236d9f3fe23cf` 的插件和扩展 capture 分别为 `.agent/runs/offline-01-06-08-20261003-builtin-all-04/` 与 `.agent/runs/offline-01-06-08-20261003-expanded-all-04/`，结果为 102/95/7 与 542/534/8（收集/通过/跳过）。离线边界继续为 `LOCAL_REFERENCE`；没有新的 dispatcher、Pi attempt 或真实连接器证据，G3–G8 不放行。

## 2026-10-03 当前合同基线与离线复核

代码候选 `eae9bfca4cf7351b02b7b5eafd6f101664b418ee` 已推送；39 对 01–06/08 合同以新版本发布于 `db46200d75ff1462837996bab7450e09a9a88f46`，均绑定精确 `bb/step-5-preview` 元数据，并通过 `pi_dispatch validate`。当前原始取证目录为 `.agent/runs/offline-01-06-08-20261003-builtin-contracts-eae9bfc/` 与 `.agent/runs/offline-01-06-08-20261003-expanded-contracts-eae9bfc/`，两者均 `baseline_consistent=true`、无 drift。

插件全集为 117 项收集、109 项通过、8 项可选 Schema 依赖跳过，返回码 0。01–06/08 扩展组合为 1040 项收集、1 项既有 `scripts/pi_dispatch.py` legacy source-lock 失败、35 项环境跳过，返回码 1；失败不是本批业务模块新失败。`compileall` 与 `git diff --check` 通过。G1/G2 仍为离线 `LOCAL_REFERENCE`；G3 当前调度器回归未形成新通过证据；G4–G7（真实 Pi/provider、原生 OS、09/10）继续 `NOT_RUN/BLOCKED`；G8 继续 `REVISE/BLOCKED`，生产发布门禁关闭。
