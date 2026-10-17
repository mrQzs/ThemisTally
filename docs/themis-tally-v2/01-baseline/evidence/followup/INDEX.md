# 01 续接最终取证索引

当前判定见 [completion-review.md](../../completion-review.md)。归档文件的实际字节以各 archive-manifest 的 archived_bytes / archived_sha256 为准，原件引用摘要不因脱敏自动变成归档摘要。

| 组 / 被测命令（使用验证环境 Python） | 总数 | 通过 | 跳过 | 失败 | 证据 |
|---|---:|---:|---:|---:|---|
| `tests/test_dispatch.py` | 256 | 256 | 0 | 0 | [归档清单](bl-01followup-dispatch-20260926/archive-manifest.json) |
| `tests/test_protocols.py` | 342 | 338 | 4 | 0 | [归档清单](bl-01followup-protocols-20260926/archive-manifest.json) |
| `tests/test_codekit01_fixtures.py -v` | 77 | 77 | 0 | 0 | [归档清单](bl-01followup-fixtures-20260926/archive-manifest.json) |
| `tests/test_baseline_tool.py` | 45 | 45 | 0 | 0 | [归档清单](bl-01followup-baseline-20260926/archive-manifest.json) |
| `tests/test_legacy_gates.py` | 24 | 24 | 0 | 0 | [归档清单](bl-01followup-gates-20260926/archive-manifest.json) |
| `tests/test_legacy_lifecycle.py` | 26 | 24 | 2 | 0 | [归档清单](bl-01followup-lifecycle-20260926/archive-manifest.json) |
| `tests/test_legacy_cli.py` | 75 | 74 | 1 | 0 | [归档清单](bl-01followup-cli-20260926/archive-manifest.json) |
| `tests/test_legacy_events.py` | 34 | 34 | 0 | 0 | [归档清单](bl-01followup-events-20260926/archive-manifest.json) |
| `tests/codekit01_legacy.py --check` | 40 | 40 | 0 | 0 | [归档清单](bl-01followup-legacy-check-20260926/archive-manifest.json) |
| `tests/codekit01_legacy.py --check-stub-regen` | 10 | 10 | 0 | 0 | [归档清单](bl-01followup-stub-regen-20260926/archive-manifest.json) |

汇总：[verification-summary.json](verification-summary.json)。十组被测命令退出 0，前后采样各自一致；失败的基准工具初跑单独保留在 `../followup-initial-failure/`，不计入成功组。
