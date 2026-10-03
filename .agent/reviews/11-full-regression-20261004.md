# 11 全量回归记录（2026-10-04）

## 结果

```text
python -B -m unittest discover -s tests -q
Ran 1347 tests in 380.715s
FAILED (failures=3, skipped=40)
```

11 相关定向集合（S4 handoff、S5 gap、S6 matrix、runtime、second-cli、schema、adapter、授权、planner publication、legacy adapter/runtime）为 **128 项通过**；`compileall`、Schema 检查和 `git diff --check` 通过。

## 已归属失败

三个失败均来自历史 legacy source-lock：

- `test_codekit01_fixtures.DifferentialTests.test_legacy_implementation_bytes_are_source_revision`；
- `test_legacy_cli.LegacySourceTest.test_source_under_test_is_a4fa199`；
- `test_legacy_events.SourceFactsTest.test_legacy_source_is_locked_revision`。

它们都报告 `scripts/pi_dispatch.py` 当前 SHA-256 为 `90a5b1523d9c179da2827d1634eca1b307da842cc7d88bb02cb7d5f1836fda7d`，而历史锁定值为 `a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4`。本轮没有修改 `scripts/pi_dispatch.py`，因此该结果归入已知 legacy source-lock 基线失败；没有发现新的 11 定向回归失败。

真实第二 CLI 模型请求、provider/认证、Pi、05 原生进程和外部连接器仍为 `NOT_RUN/BLOCKED`。
