# 固定离线候选复审（2026-10-03）

## 候选

- commit: `ffce46b5400d1688ecb25bc754c487db3a1f05dc`
- branch: `master`
- push: `origin/master` 已更新
- 范围：claim receipt、SQLite scheduler lease、parallel resource claim、retry 边界、workflow currency cap 与公开 Schema；未修改 AGENTS、调度脚本、依赖或凭据。

## 证据

| 检查 | 结果 | 原始目录 |
|---|---|---|
| 定向 5 模块 | 85/85 通过（提交前直接复核） | 无独立 capture；扩展 capture 含同一模块 |
| 扩展 01–06/08 组合 | 484 收集；476 通过；8 跳过 | `offline-01-06-08-20261003-final-expanded-01` |
| 完整 unittest discover | 1164 收集；1126 执行；38 跳过；3 失败 | `offline-01-06-08-20261003-full-discover-01` |
| dispatch stub | 255 checks 通过 | `offline-01-06-08-20261003-dispatch-01` |
| compileall / diff-check | 通过 | `compile-01` / `diffcheck-01` |
| WSL Python 3.12 Schema | 7/7 通过 | `schema-wsl-01` |

完整发现的 3 个失败是 `a4fa199` legacy source-lock：当前 `scripts/pi_dispatch.py` 摘要为 `61872030…`，锁定摘要为 `a00d6934…`。本复审保留失败，不改弱锁定断言；它们不属于本提交触碰的文件。

## 结论

这是规划端对固定离线候选的复核，不是 `review-pi` 的 Pi attempt verdict。建议 `REVISE/BLOCKED`：离线边界和失败分类有可复核证据，但 39 份路线合同中仍有文件存在性检查、实际测试文件名不一致和逐项故障证据缺口。真实 Pi、provider、Windows/macOS 原生进程及 09/10 连接器保持 `NOT_RUN/BLOCKED`，不得形成生产发布 PASS。
