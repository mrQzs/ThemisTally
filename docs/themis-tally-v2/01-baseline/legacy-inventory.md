# 01 旧行为清单与回归映射

本文件是 01 基准与公共协议实施计划的 P1.3（旧行为清单）与 P1.4（回归映射）产物，计划见 [README.md](README.md)，决策见 [decisions.md](decisions.md)（01-D01–D10 已采纳；attempt 编号依据 01-D03）。依据文档：`docs/themis-tally-v2/01-baseline-and-protocols-审阅增强版.md`（仓库中文件名因编码显示为 `01-baseline-and-protocols-╔≤╘─╘÷╟┐░µ.md`，修订 `review-expanded-2026-09-25`）。

本文只记录旧实现的事实与证据，不做设计裁定；需要裁定的事项汇总在第 11 节。

**目录**：0 来源与证据口径 · 1 3.3 待核验项总表 · 2 G0–G6 取证表 · 3–8 区域章节（合同、事件、门禁、生命周期、退出码、自测）· 9 回归映射表 · 10 C.4 必需旧回归覆盖 · 11 未解决事项汇总 · 12 P4 特征化回归

> **P4 更新（2026-09-25）**：新增第 0.5 节（最终取证）与第 12 节（P4 特征化回归，159 个测试方法）；第 2、10 节的表格增加标“P4 更新”的列，第 9 节原 NOT_RUN 行的备注末尾加“P4 更新”标注并新增 9.9，11.5 节各条下加“P4 更新”注记。原有文字、结论与源码行号都不改；第 0–11 节原有文字中的“本次”仍指 `bl-01t1-legacy-20260925`。
>
> **完整性审查更新（2026-09-26）**：新增第 9.10 节，按行回填文档 3.2 的 input_fixture_ref 与 comparison_projection_revision（P3 已定义比较投影 `codekit01-legacy-projection-v1`）；第 0.4 节两行、第 9.1 节末条、第 11.6 节第 1、2 条与第 12.9 节末尾加“完整性审查更新”注记。原有文字、结论与源码行号都不改。
>
> **收尾轮更新（2026-09-26）**：依据 decisions.md“收尾轮裁决”R-01、R-P12 与 acceptance.md 第 10 节 M-08，只追加或加注：
> - 第 0.5 节末尾追加收尾取证 `bl-01closure-*`（R-01 严格 pyc 口径）；第 12 节各方法的结果引用切换到收尾取证，原 `bl-01final-*` 引用保留为历史；
> - 第 0.5、12.1 节把 01 新代码的测试改称“01 新代码测试（公共协议、fixtures、取证工具）”（M-08），原词写在注记中；
> - 新增 9.10.5（收尾轮新增合同负例 D-20–D-23 的 manifest 回填）、9.10.6（按 R-P12 用 manifest 与代码内联两种 fixture 逐行回填第 9 节，并给出新统计）、9.10.7（文档 6.6 七类的状态）与 12.10（第 12 节 159 个方法的 input_fixture_ref 与 comparison_projection_revision）；
> - 第 0.4、9.1、9.10、9.10.1、9.10.3、9.10.4、11.6、12.1–12.6、12.9 的相关位置加“收尾轮更新”注记。源码行号与既有结论不改。

## 0. 来源、证据口径与记录单位

### 0.1 来源

| 项 | 值 |
|---|---|
| 被读源码提交 | `a4fa199b0e5bdc658215765ee7558b9fe6723940`（sha1 对象格式），与文档 2.1 记载的调查提交一致 |
| 源码与测试的 Git blob（工作区文件经 `git hash-object` 与 `git rev-parse HEAD:<path>` 核对，二者相同） | `scripts/pi_dispatch.py` 8e7df57c91fc589895c171254e71cbc3d056c313；`tests/test_dispatch.py` b8fdd332566ceb33049240c39d2faf1258bad43b；`tests/stub_pi.py` bb106194c3fb75efc14d1a625bfa7b5a26f53f19；`scripts/dispatch-pi.sh` 99acff8c9a898818be00ecb4d0259e6d52b40e1b |
| 工作区字节 SHA-256（取证输入清单 `pre/input-manifest.json`；本机 core.autocrlf=true，工作区字节与 blob 规范化前的内容不同） | `scripts/pi_dispatch.py` a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4；`tests/test_dispatch.py` c6fed33534b096b764145257ba5c2ce340f50cbaf483b5007097874c3bbd543e；`tests/stub_pi.py` 96c0d4a5ba775e9c23ce104176f1e2f0fbe6eb2925eafef5b0c5fd5c248e916a；`tests/stub_pi_help.txt` 5668cff3cf34fd6f0dbcb7b0d10667761219ca47879ba09d11c137507245824c；`scripts/dispatch-pi.sh` e2e12058ef5d58b4126527b158bef8dcc04653527f7ce20544c0d7cd77bdb2f4 |
| 工具版本 | `TOOL_VERSION = "2.2.2"`（scripts/pi_dispatch.py:48）；合同 `CONTRACT_SCHEMA_VERSION = 1`（:49） |
| 取证 ID | `bl-01t1-legacy-20260925`；原始证据在 `.agent/baseline/01-T1/bl-01t1-legacy-20260925/`（已被 .gitignore 忽略，并在输入清单中排除）；归档副本在 [evidence/bl-01t1-legacy-20260925/](evidence/bl-01t1-legacy-20260925/)（`run/stdout.bin` 的 SHA-256 与原始证据相同） |
| 被测命令 | `python tests/test_dispatch.py`（cwd 为仓库根，stdin 为 DEVNULL，shell=false），由 `pi_dispatch.run_supervised` 以 Windows Job Object 监督，超时上限 3600 s、grace 15 s |
| 运行时间 | 2026-09-25T12:47:49Z 至 12:51:59Z，共 250.2 s |
| 运行结果 | 退出码 0；timed_out=false，interrupted=false，spawn_error=null，stray_processes=false；stdout 13423 字节（sha256 f40586e2376e2361bc962878059d732b95c2c8cb0f79d48c3fd069fc37e1080e），stderr 0 字节；汇总行 `256 checks, 0 failed`（按 `== test_x` 分段逐行统计：256 个 check，0 个失败） |
| 前后采样 | baseline_consistent=true，drift 为空。比较项：HEAD、对象格式、porcelain 原始字节、输入清单摘要（closure sha256 8ca10fb98b8d97213ae4430fdb3e8f444cb7aa0ac12fbdff8a5986513fece0a9，92 项，含未跟踪的 `scripts/codekit/` 与 `tests/test_baseline_tool.py`）、未暂存与已暂存差异、ls-files、git 版本、`core.*` 配置、bash 版本、环境事实摘要 |
| 平台 | Windows Server 2025 Standard 10.0.26100；Python 3.12.10（`<PYDIR>\python.EXE`，`<PYDIR>` 为解释器所在目录，写法与归档 `evidence/bl-01t1-legacy-20260925/pre/environment.json` 一致）；git 2.55.0.windows.5；GNU bash 5.3.15（Git Bash）；core.autocrlf=true、core.symlinks=false、core.ignorecase=true |
| 区域清单来源 | 6 个区域的章节原稿与结构化条目（`inventory-{1..6}-*.md`、`.items.json`）由规划端子代理只读起草，另一子代理逐条对抗核对（verdict 为 confirmed 或 corrected），原稿位于规划端会话 scratchpad。本文第 3–8 节纳入章节正文，第 9 节由结构化条目生成 |

### 0.2 证据等级（evidence_basis）与执行状态（execution_status）

- **source_inspected**：阅读源码或测试源码得到的规则。所有 LB 条目的规则本身都是 source_inspected。区域章节里标“实测”“探针”的内容，是起草或核对者在会话临时目录中做的一次性复现（进程内调用或临时仓库中的 CLI），没有归档为 fixture，不满足文档 3.2 的 input_fixture_ref，仍记为 source_inspected。
- **source_reported**：只来自技能文档或 AGENTS.md 的说法（LB-GATES-002、LB-LIFE-032、LB-EXIT-027），不当作源码事实。
- **measured**：只用于本次 `bl-01t1-legacy-20260925` 中实际执行并 PASS 的旧自测 check，**只限 Windows**。一个 LB 条目记为 measured / PASS 的条件是：它登记的 related_tests 在本次 stdout 中全部 PASS。measured / PASS 只证明这些 check 的断言在本机成立；条目规则中没有被这些 check 断言的部分，仍是 source_inspected。
- **NOT_RUN**：条目没有登记相关测试，或至少一个相关 check 在本次运行中没有产生（平台分支）。本次没有 FAIL、ERROR、BLOCKED 的 check。
- **Linux / macOS**：全部 NOT_RUN（01-D10），不从 Windows 结果推导。

check 名的匹配规则：

1. 按 `== test_x` 分段，逐字匹配 `PASS <check 名>`。
2. 名称中含 `%s`、`%r`、`<…>` 占位的，按本次实际输出匹配，例如 “grandchild process killed (%s)” 对应 “grandchild process killed (job-object)”，“an invalid --trailer is a usage error: %r” 对应 3 个实际 check。
3. `test_v2_review_fixes` 中 “directory links unavailable here; …”“file symlinks unavailable here; …” 是建不了链接时的替代 check，与真实 check 互斥。本次该函数产生 16 个 check，全部走真实分支，替代名没有产生，不算缺失。
4. “PDEATHSIG stops pi”（仅 Linux）与 `test_wrapper_interpreters_and_literal_arguments` 的 check（仅 POSIX，Windows 上直接 return）本次没有产生；登记了它们的条目记为 NOT_RUN，并在备注中写明其余 check 的结果。

### 0.3 本次运行的 check 分布

| 测试函数 | check 数 | PASS | 说明 |
|---|---|---|---|
| `test_happy` | 18 | 18 |  |
| `test_candidate_drift_and_artifacts` | 5 | 5 |  |
| `test_cleanup_protects_unsaved_work` | 2 | 2 |  |
| `test_budget_race` | 1 | 1 |  |
| `test_scope` | 7 | 7 |  |
| `test_events_and_thinking` | 11 | 11 | 源码 7 处 `check(`，循环展开后 11 个 |
| `test_commit_outside_main` | 6 | 6 |  |
| `test_timeout` | 3 | 3 | kill_method 为 job-object |
| `test_dispatcher_killed` | 3 | 3 | Windows 分支：“Job Object reaps pi and grandchild”；Linux 的 “PDEATHSIG stops pi” 未产生 |
| `test_stuck_states` | 3 | 3 |  |
| `test_preflight_and_budget` | 7 | 7 |  |
| `test_validate` | 18 | 18 | 源码 3 处 `check(`，`expect_error` 与示例循环展开后 18 个 |
| `test_output_paths` | 3 | 3 |  |
| `test_units` | 3 | 3 |  |
| `test_repo_config_features` | 6 | 6 |  |
| `test_wrapper_interpreters_and_literal_arguments` | 0 | 0 | Windows 上直接 return（tests/test_dispatch.py:658-659），0 个 check |
| `test_setup_wrapper_doctor` | 11 | 11 | 找到 bash，“bash wrapper finds python” 已执行 |
| `test_feedback_v11` | 28 | 28 |  |
| `test_feedback_v12` | 34 | 34 |  |
| `test_mutate` | 7 | 7 |  |
| `test_v2_planner_adapters` | 18 | 18 |  |
| `test_v2_review_fixes` | 16 | 16 | 目录链接、junction、文件符号链接分支全部真实执行，没有 “… unavailable here …” 替代 check |
| `test_v21_codex_trial_feedback` | 29 | 29 | “an invalid --trailer is a usage error: %r” 展开为 3 个 |
| `test_v22_netperf_feedback` | 17 | 17 |  |
| 合计 | 256 | 256 | 24 个函数；汇总行 `256 checks, 0 failed`，退出码 0 |

### 0.4 文档 3.2 “回归映射的最低记录单位”在本文中的落点

文档 3.2 要求每条回归映射至少包含下表 11 个字段。比较投影只能删除已说明理由的机器定位或时间字段，不能删除 verdict、检查结果、门禁失败原因、模型证据缺失状态、候选树或费用未知状态来制造一致。

| 字段 | 本文的填写方式 |
|---|---|
| legacy_behavior_id | `LB-<区域>-NNN`，区域前缀为 CONTRACT、EVENTS、GATES、LIFE、EXIT、TEST；第 9 节每条一行 |
| source_location + full_source_revision | 第 9 节 source_location 列（文件:行）；revision 统一为 `a4fa199b0e5bdc658215765ee7558b9fe6723940`，工作区中这些文件的 blob 与 HEAD 相同（0.1） |
| input_fixture_ref | measured 行的输入是 `tests/test_dispatch.py` 的 `make_repo` 临时仓库、`contract()` 合同样本与 `tests/stub_pi.py` 场景（见 8.1、8.2），没有单独归档的 fixture；source_inspected 行没有 fixture。独立 fixture 由 P3（01-T3）建立，本文暂不填写 **完整性审查更新（2026-09-26）**：P3 已建立 legacy fixture（`tests/fixtures/codekit01/`），合同与 stub 事件流相关行的回填见 9.10；其余行 NOT_COVERED，原因同见 9.10。 **收尾轮更新（2026-09-26）**：按裁决 R-P12，代码内联 fixture 也是合法的 input_fixture_ref，写法为 `inline:<测试文件>::<类>.<方法>@<测试文件 sha256>`；第 12 节 159 个方法的写法见 12.10，第 9 节各行的回填与新统计见 9.10.6（224 行中 NOT_COVERED 由 181 行降为 67 行）。 |
| legacy_command_or_test_id | 第 9 节：`测试函数` + “check 名”；命令统一为 `python tests/test_dispatch.py` |
| legacy_observation | 第 9 节给出条目标题（规则全文见所在区域章节 §N）；measured 行的观测是所列 check 在本次运行中 PASS |
| comparison_projection_revision | 尚未定义，由 P3 兼容 fixtures 与 `compatibility-matrix.md` 负责；本文全部留空 **完整性审查更新（2026-09-26）**：“尚未定义”已过时。P3 定义了 `codekit01-legacy-projection-v1`（`tests/codekit01_legacy.py:55`，两份 legacy 预期文件的 projection_revision），按行回填见 9.10。 **收尾轮更新（2026-09-26）**：R-P12 另定义 `codekit01-characterization-v1`，即特征化测试方法中的断言集合，用于代码内联 fixture；收尾轮改动后，`PROJECTION_REVISION` 位于 `tests/codekit01_legacy.py:69`（上文的 :55 是完整性审查时的行号）。 |
| new_consumer_module | 第 9 节，按文档 4.4.1 的职责边界初判（02 配置与 profiles、03 审核与锁、04 CLI 适配器与 Pi、07 工作流与调度、09 规划与合同、10 项目状态）；不能确定的写“待定”，括号内是候选 |
| acceptance_ids | 第 9 节，按文档 7.1、7.2 初判（01-A01–A16）；不能确定的写“待定” |
| platform_scope | “windows 实测”（measured 行）或“源码层面” |
| evidence_basis + execution_status | 按 0.2 的规则 |
| notes_and_limitations | 第 9 节备注列；汇总见第 11 节 |

### 0.5 P4 更新：最终取证（01-final）

0.1–0.4 描述的是实施前基线 `bl-01t1-legacy-20260925`，第 0–11 节原有文字中的“本次”都指它。P4 实施之后，规划端在同一受控环境（01-L05）中按文件逐个重新取证（01-L04），原始件在 `.agent/baseline/01-final/<capture-id>/`（被 .gitignore 忽略，只读），脱敏归档副本在 [evidence/final/](evidence/final/)。第 12 节与各处“P4 更新”注记引用的就是这些取证。中间一轮 `.agent/baseline/01-P4/` 已被最终取证取代，本文不引用。 **收尾轮更新（2026-09-26）**：规划端按裁决 R-01 的严格 pyc 口径再次逐文件取证（收尾取证 `bl-01closure-*`，见本节末尾“收尾取证”）。第 12 节的结果引用已切换到收尾取证；本节上文的最终取证 `bl-01final-*` 保留为历史证据。

取证条件分两类来源记录：

- **取证工具记录**（measured，见各取证的 `capture.json` 与 `pre/environment.json`）：
  - 平台：Windows Server 2025（10.0.26100）、CPython 3.12.10、git 2.55.0.windows.5；`which` 中 pi、claude、codex 均为 null；`PI_CODING_AGENT_DIR` 存在（只记是否存在）。
  - 命令：argv 为 `python tests/<文件>`，cwd 为仓库根，stdin 为 DEVNULL，shell=false；由 `pi_dispatch.run_supervised` 以 Job Object 监督，timeout 3600 s、grace 15 s。监督模块 `scripts/pi_dispatch.py` 的 sha256 为 a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4，与 0.1 相同。
  - 运行时间（UTC）：2026-09-26T04:16:49Z 至 04:28:10Z，8 次取证依次进行。
- **规划端记录**（source_reported，取证工具没有采集）：
  - 在 Git Bash 中运行；PATH 去掉了真实 pi、claude、codex 所在目录；`PI_CODING_AGENT_DIR` 指向的空目录在运行后仍为空；会话令牌变量已 unset。
  - 每次取证后系统临时目录没有新增残留目录。
  - 受保护文件（scripts/pi_dispatch.py、scripts/dispatch-pi.sh、tests/test_dispatch.py、tests/stub_pi.py、tests/stub_pi_help.txt、AGENTS.md、.agents/、.claude/）相对 HEAD 的 diff 为 0 行。

8 次取证的共同事实：

- HEAD 为 `a4fa199b0e5bdc658215765ee7558b9fe6723940`；前后采样 baseline_consistent=true，drift 为空。
- 输入清单 373 项（tracked 63、untracked 310）；闭包摘要 pre 与 post 相同，均为 2d8f2f71d6514b08e1f331009245d97e5f51a50a02f034651f87e17e2fa70b7d。
- closure_status=partial，声明的缺口是：被忽略文件不计哈希、子模块内容不展开、仓库外输入不纳入、gitattributes 的效果不评估。bl-01t1 用的是同一工具，口径相同。
- run 的 timed_out=false、interrupted=false、spawn_error=null、stray_processes=false，退出码 0。
- 每个归档目录的 `archive-manifest.json`：integrity_check 为 82 个文件、0 个不符；表中 run 输出文件的归档字节与原始件相同（bytes_changed=false）。

下表按 01-A16 分栏：旧自测、P4 旧实现特征化回归、01 新代码测试（公共协议、fixtures、取证工具）三类分开，互不代替。（收尾轮 M-08 更正用词：原写“参考实现与取证工具测试”。这三个测试文件的被测对象是本仓库的 01 新代码，不是附录 B 的参考代码。）

| 类别 | 取证 ID | 被测命令 | 结果（run 输出原文） | 归档的结果文件（字节数，sha256） | 本文中的用途 |
|---|---|---|---|---|---|
| 项目原有旧自测 | `bl-01final-test-dispatch-20260925` | `python tests/test_dispatch.py` | `256 checks, 0 failed`；退出 0 | [run/stdout.bin](evidence/final/bl-01final-test-dispatch-20260925/run/stdout.bin)（13423，f40586e2376e2361bc962878059d732b95c2c8cb0f79d48c3fd069fc37e1080e）；stderr 0 字节 | 复核：P4 实施后旧自测的 stdout 与 `bl-01t1-legacy-20260925` 的 run/stdout.bin 字节相同（sha256 相同）。第 0–11 节原有的 measured 仍以 bl-01t1 为依据 |
| P4 旧实现特征化回归（新增测试；被测对象为 a4fa199 的 scripts/pi_dispatch.py） | `bl-01final-test-legacy-gates-20260925` | `python tests/test_legacy_gates.py` | `Ran 24 tests`、`OK`；退出 0 | [run/stderr.bin](evidence/final/bl-01final-test-legacy-gates-20260925/run/stderr.bin)（6459，80d945cd781a868e666fbfb89e2c5a39edd527291d77e92f96d63ac3b4cdffe1）；stdout 0 字节 | 第 12.3 节 |
| 同上 | `bl-01final-test-legacy-lifecycle-20260925` | `python tests/test_legacy_lifecycle.py` | `Ran 26 tests`、`OK (skipped=2)`；退出 0 | [run/stderr.bin](evidence/final/bl-01final-test-legacy-lifecycle-20260925/run/stderr.bin)（7809，45e9ec9f0b232815ebbd0c9159090c1f3d10aa95cd65e8d523ab8c2812b1a69b）；stdout 0 字节 | 第 12.4 节 |
| 同上 | `bl-01final-test-legacy-cli-20260925` | `python tests/test_legacy_cli.py` | `Ran 75 tests`、`OK (skipped=1)`；退出 0 | [run/stderr.bin](evidence/final/bl-01final-test-legacy-cli-20260925/run/stderr.bin)（19861，484493ae4f7412a21b7c473fbfcbb663d891ff5a0e3575943366e242c4440c8c）；stdout 0 字节 | 第 12.5 节 |
| 同上 | `bl-01final-test-legacy-events-20260925` | `python tests/test_legacy_events.py` | `Ran 34 tests`、`OK`；退出 0 | [run/stderr.bin](evidence/final/bl-01final-test-legacy-events-20260925/run/stderr.bin)（8739，9dc7c9843ac13b2bf001439f7011214c8d227136113567a0bbc622c3d9be1010）；stdout 0 字节 | 第 12.6 节 |
| 01 新代码测试（公共协议、fixtures、取证工具；M-08 更正，原写“参考实现与取证工具测试”） | `bl-01final-test-protocols-20260925` | `python tests/test_protocols.py` | `Ran 324 tests`、`OK (skipped=4)`；退出 0 | [run/stderr.bin](evidence/final/bl-01final-test-protocols-20260925/run/stderr.bin)（73321，1f30be24ba3b38c4b56e54a01a076e74b630c5cdcb89c4eeb975e84211e9de36） | 只作引用，不作为任何 LB 行的证据。跳过的 4 项为 01-F017、01-F029、01-F030 与 jsonschema 元校验（跳过原因见该文件） |
| 同上 | `bl-01final-test-codekit01-fixtures-20260925` | `python tests/test_codekit01_fixtures.py` | `Ran 36 tests`、`OK`；退出 0 | [run/stderr.bin](evidence/final/bl-01final-test-codekit01-fixtures-20260925/run/stderr.bin)（140，689389be7fbd34cdcb40ebe00a954113c293ed9384157b991f72cfee60aa8261） | 只作引用 |
| 同上 | `bl-01final-test-baseline-tool-20260925` | `python tests/test_baseline_tool.py` | `Ran 40 tests`、`OK`；退出 0 | [run/stderr.bin](evidence/final/bl-01final-test-baseline-tool-20260925/run/stderr.bin)（5064，1cf45a96ef531b7df6f8eec633302127c9e77186ae44a6670f8fe1509840eb4a） | 只作引用 |

表中 run 输出链接都在 `evidence/final/<capture-id>/` 下。退出码 0 与 `OK` 只说明取证中的断言全部成立（跳过的除外），不代表未运行的平台或未编写的用例通过。

**收尾轮更新（2026-09-26）：收尾取证（01-closure，R-01 严格 pyc 口径）**

第 12 节自本轮起引用下表的收尾取证；上表的最终取证保留为历史，不删除。

- **原件与归档**：
  - 原件在 `.agent/baseline/01-closure/<capture-id>/`（被 .gitignore 忽略，只读）。
  - 脱敏归档副本在 [evidence/closure/](evidence/closure/)`<capture-id>/`，由 `scripts/codekit/baseline.py archive` 生成（规则 redact-v2），各有 `archive-manifest.json`。10 份清单的 `integrity_check` 都是 82 个文件、0 个不符；`run/stdout.bin` 与 `run/stderr.bin` 的 `bytes_changed` 都是 false。
  - 本次修订逐个核对（只读）：这 20 个 run 输出文件的归档字节与原件的 sha256 相同；10 份归档清单的 sha256 与 [evidence/closure/INDEX.md](evidence/closure/INDEX.md) 第 1 节所记相同。INDEX.md 由规划端子代理手写，只作索引，不是取证产物。
  - 操作者记录另归档在 [evidence/run-controls-closure/closure-captures.txt](evidence/run-controls-closure/closure-captures.txt)（3133 字节，sha256 fb00af747f1ff3fd7b20a35d5902c918f7057f58bdfb7e9c660d4db57ccc0e86，清单为同目录的 `manifest.json`）。它记录了受控条件、逐次汇总行与残留检查，没有逐方法输出。
- **取证工具记录**（measured；各取证的 `capture.json` 与 `pre/environment.json`）：
  - HEAD `a4fa199b0e5bdc658215765ee7558b9fe6723940`（sha1）；Windows Server 2025（10.0.26100）、CPython 3.12.10、git 2.55.0.windows.5；core.autocrlf=true；`which` 中 pi、claude、codex 均为 null；`PI_CODING_AGENT_DIR` 存在（只记是否存在）。
  - argv 为 `python tests/<文件>`：fixtures 测试这一次带 `-v`，另有两次是 `python tests/codekit01_legacy.py --check` 与 `--check-stub-regen`。cwd 为仓库根，stdin 为 DEVNULL，shell=false；由 `pi_dispatch.run_supervised` 以 Job Object 监督，timeout 3600 s、grace 15 s。
  - 监督模块 sha256 为 a00d6934…（与 0.1 相同）；取证工具 `scripts/codekit/baseline.py` 的 sha256 为 dbb08466778db639966336902653525fa26a4f9f9152c5827594ea9313e49ce8。子进程环境由 `child_env` 补上 GCM_INTERACTIVE、GIT_TERMINAL_PROMPT、PYTHONDONTWRITEBYTECODE（`run.env_added_names`）。
  - 运行时间（UTC）：2026-09-26T14:47:10Z 至 15:00:06Z，10 次依次进行。
- **操作者记录**（closure-captures.txt；这是操作者脚本的输出，不是取证工具的输出）：
  - PATH 去掉了真实 claude、pi、codex 所在的两个目录；会话令牌变量已 unset；受控条件下 pi、claude、codex 均为 absent。
  - `PI_CODING_AGENT_DIR` 与 `PYTHONPYCACHEPREFIX` 各指向取证前为空的临时目录（`pycache_prefix_entries_before=0`）。这就是 R-01 的“受控禁用”：解释器不读取仓库中的 `__pycache__`。
  - 受保护文件相对 HEAD 的 diff 前后均为 0 行；每次 `leaked=[]`；取证后空目录的条目数为 0。
  - `PYTHONPYCACHEPREFIX` 不在取证工具记录的变量名单中，这一条只有操作者记录。该记录的清单写明 `repo_pycache_dirs_newer_than_start` 的参照时刻偏晚，此项不作证据。
- **10 次取证的共同事实**：
  - baseline_consistent=true，drift 为空，execution_status=complete；
  - 输入清单 1073 项（tracked 63、untracked 1010），闭包摘要 pre 与 post 相同，均为 81b4503e291166fd78632aab9163faac2f0e25c92db11c691dfbe753068f52a4；closure_status=partial，缺口与上文相同；忽略项 2 个（`scripts/__pycache__/`、`tests/__pycache__/`，只记名称）；
  - run 的 returncode=0、timed_out=false、interrupted=false、spawn_error=null、stray_processes=false、kill_method=job-object。
- **与最终取证相比变化了的输入字节**（收尾取证输入清单的记录值；本次只读核对，与工作区字节相同）：
  - `tests/legacy_harness.py` 由 3d133d5f… 变为 c4e871372a35f35c59a76172ccc366a50316c5af9ad3ec4703d1fb6c27d4b974（收尾轮加入 8.4 清理前的归属核对）；
  - `tests/test_codekit01_fixtures.py` 为 16b71bca5f0c86378a00b59fcfc6426de4772b79f04cf356ae6ee4525131a57b（75 项）；
  - `tests/fixtures/codekit01/manifest.json` 为 95c58a9b5a68166e104ee8a719385d43a8f346bff96ab96806518d6c94a830e0（188 条）；`expected/legacy-contracts.json` 为 5328bb62721095f07ac48350c53aa74e6a0e8dc64440ab15a713c618fc866ed0（22 个用例）；
  - 四个 P4 测试文件、`expected/legacy-events.json`、`scripts/pi_dispatch.py`、`tests/stub_pi.py`、`tests/stub_pi_help.txt`、`tests/test_dispatch.py` 的字节不变。

| 类别（01-A16 分栏） | 取证 ID | 被测命令 | 结果（run 输出原文） | 归档的结果文件（字节数，sha256；与原件相同） | 归档清单 `archive-manifest.json` 的 sha256 | 本文中的用途 |
|---|---|---|---|---|---|---|
| 项目原有旧自测 | `bl-01closure-test-dispatch-20260926` | `python tests/test_dispatch.py` | `256 checks, 0 failed`；退出 0 | [run/stdout.bin](evidence/closure/bl-01closure-test-dispatch-20260926/run/stdout.bin)（13423，f40586e2376e2361bc962878059d732b95c2c8cb0f79d48c3fd069fc37e1080e）；stderr 0 字节 | fd4a0d3687e615c6ae06d70b79ded6a59924ff829d4a44265a8aeb12c5d7d31d | 复核：stdout 与 `bl-01t1-legacy-20260925`、`bl-01final-test-dispatch-20260925` 字节相同。第 0–11 节原有的 measured 仍以 bl-01t1 为依据 |
| P4 旧实现特征化回归（被测对象为 a4fa199 的 scripts/pi_dispatch.py） | `bl-01closure-test-legacy-gates-20260926` | `python tests/test_legacy_gates.py` | `Ran 24 tests`、`OK`；退出 0 | [run/stderr.bin](evidence/closure/bl-01closure-test-legacy-gates-20260926/run/stderr.bin)（6459，97af8357a3730e301a70d6890bfc1d1463186590d25f4db15d7348ea938138f6）；stdout 0 字节 | 6e7a47cc1d8ba259297d9c6a3e30d4226782bb1483730318df685b02598d2f11 | 第 12.3 节：24 个方法 ok |
| 同上 | `bl-01closure-test-legacy-lifecycle-20260926` | `python tests/test_legacy_lifecycle.py` | `Ran 26 tests`、`OK (skipped=2)`；退出 0 | [run/stderr.bin](evidence/closure/bl-01closure-test-legacy-lifecycle-20260926/run/stderr.bin)（7809，e79ad9f8e4e9f8330f7677f2696ae9908dc6604b2735f955c62813924a2aa99f）；stdout 0 字节 | 8b5d41c20fe4544fef6004862b3394495793bee0998b855951585e9e1b4b43bd | 第 12.4 节：24 个 ok，2 个 skipped（POSIX 分支） |
| 同上 | `bl-01closure-test-legacy-cli-20260926` | `python tests/test_legacy_cli.py` | `Ran 75 tests`、`OK (skipped=1)`；退出 0 | [run/stderr.bin](evidence/closure/bl-01closure-test-legacy-cli-20260926/run/stderr.bin)（19861，26cce1cf6ad440b5f584180592d772bb4e720e2a54f353694f458bef6a16c3ae）；stdout 0 字节 | 38734036c2d20153d9cd5f9b91aebc077b05b09920ae347078194bd52256ab5c | 第 12.5 节：74 个 ok，1 个 skipped（POSIX 分支） |
| 同上 | `bl-01closure-test-legacy-events-20260926` | `python tests/test_legacy_events.py` | `Ran 34 tests`、`OK`；退出 0 | [run/stderr.bin](evidence/closure/bl-01closure-test-legacy-events-20260926/run/stderr.bin)（8739，e5cfa16608d66529963a69a7a10236c294873692b3efe19f5773b0c6bbe70166）；stdout 0 字节 | b341914ffa16dfc2e41a18491e2696a0b4bcadcae8499b15eaf9a638a487d302 | 第 12.6 节：34 个方法 ok |
| 01 新代码测试（公共协议、fixtures、取证工具） | `bl-01closure-test-protocols-20260926` | `python tests/test_protocols.py` | `Ran 342 tests`、`OK (skipped=4)`；退出 0 | [run/stderr.bin](evidence/closure/bl-01closure-test-protocols-20260926/run/stderr.bin)（77955，5b81e659c60f296503dd99e836a938fa45134ffe597fb960a204b56ee65354c8）；stdout 0 字节 | d91e78995fbfa90790274f60139ffb52d58fb3b2c50c21cfe8eea6d589e56037 | 只作引用，不作为任何 LB 行的证据。跳过的 4 项仍是 01-F017、01-F029、01-F030 与 jsonschema 元校验（原因见该文件），跳过不算通过 |
| 同上 | `bl-01closure-test-codekit01-fixtures-v-20260926` | `python tests/test_codekit01_fixtures.py -v` | `Ran 75 tests`、`OK`；退出 0；方法级输出为 75 个 `... ok` | [run/stderr.bin](evidence/closure/bl-01closure-test-codekit01-fixtures-v-20260926/run/stderr.bin)（13127，95faa68cea9315a4a73cc4bfc4223916e56b8eb1b9e5694fa1415fdf1c8b169a）；stdout 0 字节 | 54b9132f3abcfa4cb79d065dec860290f2f3fa71fc8c58ccfb6cbd4c1ea69153 | 不作为任何 LB 行 evidence_basis 的证据。9.10 的“证据状态”注记与 9.10.5 引用其中 `DifferentialTests`、`CompatMatrixDCaseTests` 的方法级结果，说明锁定投影的回归比较已经运行 |
| 同上 | `bl-01closure-test-baseline-tool-20260926` | `python tests/test_baseline_tool.py` | `Ran 40 tests`、`OK`；退出 0 | [run/stderr.bin](evidence/closure/bl-01closure-test-baseline-tool-20260926/run/stderr.bin)（5064，024b9d508c236c504ee277b9aa07db14f45ad32235d547c1d161002121f22863）；stdout 0 字节 | 22694ddf02256dabdace3bfe3e85aa039779cb80284d43fbf48b5ede7ccbd9f0 | 只作引用 |
| 同上（fixture 生成器 `tests/codekit01_legacy.py` 的锁定核对） | `bl-01closure-legacy-check-20260926` | `python tests/codekit01_legacy.py --check` | `38 checks, 0 differ`；退出 0 | [run/stdout.bin](evidence/closure/bl-01closure-legacy-check-20260926/run/stdout.bin)（3712，2a06d6b3069d23cbb24649983cbced3770476d7b5a3fdf16e751dea94580f5d2）；stderr 0 字节 | b74b9513906ee3fb72602db703ebed6a37cebc3cfc843887a9dae0f8bb2619dc | 9.10.5：以当前字节重算后全部 SAME，包括 6 个 legacy 合同文件的源字节与工作区字节、19 个合同负例与 3 个事件负例的派生字节、三份预期文件（legacy-contracts、legacy-events、legacy-new-strict）与 manifest 的 legacy 条目 |
| 同上 | `bl-01closure-legacy-check-stub-regen-20260926` | `python tests/codekit01_legacy.py --check-stub-regen` | `10 checks, 0 differ`；退出 0 | [run/stdout.bin](evidence/closure/bl-01closure-legacy-check-stub-regen-20260926/run/stdout.bin)（273，9a942083ceece639e010b0771c7c2f0efd68470d40f8cd72766d76d63de1a785）；stderr 0 字节 | c8833dc2557af3eb99990a7fecd3cda742e6a9b7a6cc40410bb03330209f7237 | 9.10.5：10 条 stub 事件流重新生成后与锁定字节相同 |

退出码 0、`OK` 与 `0 differ` 只说明取证中的断言或比较全部成立（跳过的除外），不代表未运行的平台、未编写的用例，或文档 6.6 意义上的新旧路径差分已经通过。

## 1. 文档 3.3 待核验项总表

每行给出旧实现的结论、主要依据和本次运行中直接相关的 check。结论中的规则都是 source_inspected；列出的 check 在本次 Windows 运行中全部 PASS。

| # | 3.3 待核验项 | 旧行为结论 | 依据（LB 条目；scripts/pi_dispatch.py 行号） | 本次运行（Windows） | 证据等级 |
|---|---|---|---|---|---|
| 1 | attempt 的起始值、递增条件与恢复复用规则 | - **首个编号为 1**：`number = max(existing, default=0) + 1`，目录名 `attempt-%03d`（≥1000 时为 `attempt-1000`）；工具从不生成 0（01-D03）。<br>- 作用域是 `.agent/runs/<task_id>/`，跨 plan_version 连续，新版本合同不从 1 重新开始。<br>- 只有 `prepare` 分配编号，且要先通过合同校验（2）、`.agent/runs/` 已被忽略（3）、执行器核对（2/3）、预算预检（3）；编号分配后不释放、不回填。<br>- `collect --recover` 和预检失败后再次 `run` 都在原目录上进行，不分配新编号。状态不是未领取的 PREPARED 时 `run` 拒绝（3），返工必须重新 `prepare`。<br>- verdicts、checks、mutations 的 `NN` 同样从 01 开始。 | LB-LIFE-001–004、033、040；:2619-2623、3255-3257、3285、3413、3440、3453-3455 | `test_happy` “branch subject without a title”（主题行为 “normalize-query: Pi 候选 v1 attempt 001”）<br>`test_happy` “branch tree == candidate tree”（分支名含 `a001`）<br>`test_preflight_and_budget` “model not listed -> preflight fail, stays PREPARED”、“run after fixing env”、“budget: 3rd attempt refused”<br>`test_stuck_states` “claimed PREPARED attempt cannot run again”、“claimed-but-not-started attempt recovers as INFRA_FAILURE”<br>条目状态：LB-LIFE-001 measured/PASS；LB-LIFE-002 measured/PASS；LB-LIFE-003 measured/PASS；LB-LIFE-004 measured/PASS | 规则 source_inspected；所列 check measured / PASS（Windows）。并发 prepare 撞名重试、跨版本连续编号没有测试 |
| 2 | 退出码 0/1/2/3/4 的逐入口含义 | - 常量 `EXIT_OK/FAIL/USAGE/BLOCKED/DRIFT = 0/1/2/3/4`；`DispatchError` 缺省码是 3。<br>- main：DispatchError 写 stderr `ERROR: <msg>` 并返回其码；KeyboardInterrupt 打印 `已取消。` 返回 130；其他异常不捕获，Traceback 退出 1（与 EXIT_FAIL 同码）；argparse 用法错误退出 2，没有 `ERROR:` 前缀；没有子命令时打印帮助返回 2。<br>- 逐入口（完整表见 7.3）：validate 0 有效、2 无效（`git rev-parse HEAD` 失败时 3）；derive-json 0/2（推导有问题时即使打印“合同有效”也是 2，JSON 已写入）；prepare 0/1（setup 失败或变脏）/2/3；run 只有最终 NEEDS_REVIEW 且 events ok 为 0，其余收集结果为 1，拒绝为 2/3；collect --recover 恢复完成一律 0（拒绝为 2/3）；check 0/1/2/3，**4 只用于 check 运行前的候选漂移**（全文件唯一）；baseline 0（无期望不符）/1/2/3；mutate 流程完成即 0（含 missed）/2/3；verdict 结论已记录即 0（含 REVISE），PASS 被门禁拒绝为 1，其余拒绝为 2/3；branch、mark 0/2/3；cleanup 0/3；sync-adapters 0/1/3；status、metrics 成功即 0，不反映 attempt 状态（参数或 `--out` 非法时 2）；doctor 0/1（给了 `--out` 时还可能 2/3）；smoke 0/1/2/3；wait 0/1/2/3。<br>- 同码异义：0 不代表验收通过；3 同时表示阻断类错误与 wait 的“仍在运行/未开始”；1 同时表示负面结果与未捕获异常；Pi 运行期间的中断最终退出 1 而不是 130。 | LB-EXIT-001–028、029–040；LB-CONTRACT-023、026、034；:53、304-309、4953-4975、3349、4014 | `test_candidate_drift_and_artifacts` “in-place check refuses unexpected extra file”、“check creating unexpected file -> exit 1”（== EXIT_DRIFT、== 1）<br>`test_events_and_thinking` “error stopReason -> exit 1 but NEEDS_REVIEW”<br>`test_output_paths` “metrics --out README.md refused, README untouched”、“doctor --out into evidence refused”（== EXIT_USAGE）<br>`test_v21_codex_trial_feedback` “an invalid --trailer is a usage error: 'Bad trailer'” 等 3 项（== EXIT_USAGE）<br>`test_mutate` “invalid mutation spec is rejected with every problem listed”（== 2）<br>`test_v2_planner_adapters` “sync-adapters --check reports missing copies”（== 1）<br>wait 的 0/3/1 见第 3 行 | 规则 source_inspected；所列退出码断言 measured / PASS（Windows）。多数拒绝路径只断言“非 0”；main 的 130、argparse 的 2、未捕获异常的 1、run 在 TIMEOUT/CANCELLED/INFRA_FAILURE 时的 1 都没有测试 |
| 3 | `wait` 仍在运行与已结束的输出结构 | stdout 每种情形一行中文文本，没有 `--json`：<br>- **已结束**（TERMINAL_STATES，含 NEEDS_REVIEW、TIMEOUT、CANCELLED、INFRA_FAILURE、PREPARE_FAILED、五种结论、INTEGRATED、ABANDONED、SUPERSEDED）：`已结束：<run-dir> · <STATE>`，有 summary.md 时另起一行 `摘要：<路径>`，退出 0。<br>- **仍在运行**（PREPARING/RUNNING/COLLECTING 且等满 `--timeout`，缺省 540 s）：`仍在运行：<run-dir> · <STATE>。再次运行 wait 继续等待。`，只有 RUNNING 在 STATE 后附 ` · live:…`，退出 3。<br>- **未开始**（PREPARED 且等满 min(60, --timeout) 秒）：`attempt 仍是 PREPARED：run 没有开始（或启动前就失败了）。检查后台命令的输出：<run-dir>`，退出 3。<br>- **无法确定**（state.json 缺失、损坏、无 state 键，显示 UNKNOWN；`"state": null` 显示 None）：`无法确定 attempt 的状态（<STATE>）：…`，退出 1；state.json 是非对象 JSON 时 Traceback、退出 1、stdout 为空。<br>- 找不到 attempt 或 `--timeout` < 1：stderr `ERROR: …`，退出 2。<br>**wait 退出 0 只表示已结束，不表示验收通过**；退出 3 与 DispatchError 缺省码重叠。 | LB-EXIT-023–026、030；LB-LIFE-029；LB-EVENTS-029；:3914-3950、81-82、4518-4548 | `test_v2_planner_adapters` “wait returns at once for a finished attempt”、“wait times out on a running attempt with exit code 3”、“wait reports an attempt that never started”<br>`test_v2_review_fixes` “wait does not report an unreadable state as finished”（state.json 写成 `{`，退出 1）<br>条目状态：LB-EXIT-023 measured/PASS；LB-EXIT-024 measured/PASS；LB-EXIT-026 measured/PASS；LB-LIFE-029 measured/PASS | 规则 source_inspected；所列 check measured / PASS（Windows）。`--timeout`<1、PREPARING/COLLECTING 到时、60 s 宽限、state.json 缺失、非对象 state.json、live 片段与“摘要：”行没有测试 |
| 4 | G0–G6 的真实名称、顺序与断言 | - 源码只有编号（`GATES`，:79），没有名称字符串。名称只见于 `.agents/skills/review-pi/gates.md:7-13`（source_reported）：G0 输入一致、G1 执行完整、G2 范围合规、G3 行为正确、G4 回归检查、G5 质量复审、G6 可集成。<br>- 求值顺序：G0 → G1（同时写 G3 备注）→ G2 → G3/G4（没有有效检查记录时两门同时失败，否则先 G4 后 G3 的 DoD）→ G6；结果与 verdict 的失败列表按 G0…G6 排列；G5 恒通过。<br>- PASS 要求七门全过且不带 `--waive`（门禁失败时退出 1，先打印 `GATE <Gx> …`）；ACCEPTED_WITH_EXCEPTION 要求每个失败门禁都有 `--waive`，且至少一项 `--waive` 与 `--decided-by`；REVISE/BLOCKED/ESCALATE 要求 `--class`。<br>- 逐门断言与测试见第 2 节。 | LB-GATES-001、002、023–033；:75-80、4152-4256、4263-4316 | 见第 2 节 | 名称 source_reported；语义 source_inspected；测试结果 measured（Windows），G0、G5 无测试，G3、G6 无失败路径断言 |
| 5 | Markdown/JSON 冲突时的优先级和报错 | - **不设优先级**。被比较的项任何一处不一致都是 ERROR：validate 退出 2（stdout 末行 `合同无效：N 个错误，M 个警告。`），prepare 抛 `合同校验失败，未创建 attempt。`（2），baseline 抛 `合同校验失败，无法运行基线检查。`（2），不会自动采用任何一方。<br>- 被比较的项：占位符（两边）、13 个必需章节、`# TASK:` 标题、Identity 的 plan_version/base_sha/risk_level、authorized_actions/integration_actions、executor 的 provider/model 与 thinking、Scope 路径（JSON 到 Markdown 单向、全文子串）、dependency_changes、Budget 三项、检查 id 行与 argv、DoD 编号。<br>- 运行时：执行说明要求执行器在 plan.md 与“机器合同摘要”（由 JSON 生成）冲突时停止并报告。<br>- 不在比较范围的字段（setup、checks 的 cwd/timeout/输出模式/required/expect_on_base/env、DoD 的 text 与 evidence、tools、context_files、cost_budget、repository、title）只按 JSON 执行。<br>- derive-json 由 Markdown 生成 JSON；JSON 已存在时需要 `--force` 才覆盖。 | LB-CONTRACT-014–018、023–026；:1582-1634、3172-3173、4083-4084、2713、2732-2733、3029-3031 | `test_validate` “argv change detected”、“budget change detected”、“integration change detected”、“forbidden path change detected”、“thinking change detected”<br>`test_validate` “missing md section rejected”、“placeholder rejected”<br>`test_feedback_v11` “derive-json writes a contract that validates”、“derive-json refuses to overwrite without --force”<br>条目状态：LB-CONTRACT-014 measured/PASS；LB-CONTRACT-015 measured/PASS；LB-CONTRACT-016 measured/PASS；LB-CONTRACT-017 measured/PASS；LB-CONTRACT-018 measured/PASS | 规则 source_inspected；所列 check measured / PASS（Windows）。只测了“改 JSON、Markdown 不变”一个方向 |
| 6 | 缺失模型、思考级别、token、费用的旧输出 | - **模型**：actual_models 取所有 assistant 消息的 (str(provider), str(model)) 去重排序；字段缺失时是 `('None', 'None')`，没有 assistant 时是 `[]`。model_match 要求至少一条 assistant 且每对都等于要求值，否则 problem “实际模型 %s 与要求 %s 不一致或缺失”，events.ok 为假、G1 失败、run 退出 1。responseModel 只记录，不参与比较。summary.md 在没有实际模型时写“无”。<br>- **思考级别**：提供商一条都没回报时 thinking_evidence 为 “not_reported：…”，**不算** problem，只在 G1 记备注“提供商未回报思考级别：只能确认请求的级别（%s）”；部分消息回报时按 provider_reported 处理，不告警；回报值与要求不同时记 problem。<br>- **token**：缺失时输出 **0**，不是 null；events-summary 的 usage 恒为五个数字，没有“用量完整性”字段，不产生 problem（与文档 4.3.7 的 null 语义冲突）。<br>- **费用**：未知时 `cost.total` 为 **null**，status 为 unknown（已有部分定价时为 partial），unpriced_messages 计数；没有币种字段；费用状态不产生 problem，也不参与门禁；status 的 COST 列写 `unknown`，metrics 计入 unknown_cost_attempts。 | LB-EVENTS-012–014、016–020；:2323-2337、2350-2352、2081-2093、2179-2180、2334-2336、2390-2394、4177-4179 | `test_happy` “thinking not reported -> evidence says so, no problem”、“usage sums assistant message_end only”<br>`test_events_and_thinking` “events case model {}”、“events case ok {'STUB_PTL': 'low'}”、“events case ok {'STUB_NOCOST': '1'}”、“status shows unknown cost”<br>条目状态：LB-EVENTS-013 measured/PASS；LB-EVENTS-014 measured/PASS；LB-EVENTS-018 source_inspected/NOT_RUN；LB-EVENTS-019 measured/PASS；LB-EVENTS-020 measured/PASS | 规则 source_inspected；所列 check measured / PASS（Windows）。token 缺失输出 0、partial 费用、部分回报思考级别、provider/model 字段缺失没有测试 |
| 7a | 取消的旧结果 | - Pi 运行期间（run_supervised 内）收到 SIGINT/SIGTERM/SIGHUP/SIGBREAK：转为 `_Interrupted`，终止进程树，run.json 记 interrupted=true；collect 按优先级判为 CANCELLED（排在 spawn_error/收集错误/无候选树→INFRA_FAILURE、timed_out→TIMEOUT 之后）；**run 退出 1，不是 130**；G1 记“运行被取消或调度器中断”，PASS 被拒。<br>- run_supervised 之外按 Ctrl+C：KeyboardInterrupt，stderr `已取消。`，退出 130。状态取决于阶段：领取前保持 PREPARED；已建 claim 未写 reservation 时为已领取的 PREPARED；:3319-3332 期间先标 INFRA_FAILURE；collect 中停在 COLLECTING；prepare 的 setup 中为 PREPARE_FAILED（退出 1）。<br>- 调度器被强杀后 `collect --recover`：缺 run.json 时合成 interrupted=True、recovered=True，Pi 已启动时通常得到 CANCELLED、未启动时 INFRA_FAILURE，一律退出 0；G1 必然失败。 | LB-LIFE-017、021–023、035；LB-EXIT-031；:571-585、703-706、3395-3404、3426-3434、4169-4172、4969-4971 | `test_dispatcher_killed` “recover after dispatcher death”（断言同时接受 CANCELLED 与 INFRA_FAILURE，未锁定取消分支）<br>条目状态：LB-LIFE-017 source_inspected/NOT_RUN；LB-LIFE-021 source_inspected/NOT_RUN；LB-LIFE-023 measured/PASS | 规则 source_inspected；**没有信号用例**，取消分支 NOT_RUN |
| 7b | 超时的旧结果 | - 本轮时限 = `int(min(per_attempt, total - used))`，`run --timeout N` 只能收紧。<br>- 到期时 timed_out=true，以 grace（`kill_grace_seconds`，缺省 15 s）终止进程树（Windows：CTRL_BREAK → 等 grace → TerminateJobObject → 再等 30 s；POSIX：killpg SIGTERM → SIGKILL）。<br>- collect 判 TIMEOUT（候选缺失或收集出错时 INFRA_FAILURE），run 退出 1；G1 记“运行超时”，PASS 被拒，只能 ACCEPTED_WITH_EXCEPTION 豁免，或标 SUPERSEDED/ABANDONED。<br>- 实际 wall_seconds 包括 grace 与回收等待，可能超过预留与 max_wall_seconds_total。 | LB-LIFE-011、016、018–020、039；:678、691-699、596-626、3307-3309、3395-3398、4169-4170 | `test_timeout` “timeout -> TIMEOUT state”、“timeout enforced quickly (<40s)”、“grandchild process killed (job-object)”<br>条目状态：LB-LIFE-016 measured/PASS；LB-LIFE-018 measured/PASS | 规则 source_inspected；所列 check measured / PASS（Windows）。超时后 run 退出 1、verdict 的 G1 失败没有断言 |
| 7c | 已有锁的旧结果 | - 任务锁是目录 `.agent/runs/<task>/.task.lock`，`mkdir` 原子获取，每 0.2 s 重试、最多 30 s；仍被占用时 DispatchError “任务锁被占用：<路径>（另一个 run 正在领取；如确认无人使用可删除该目录）”，退出 3，不写 history，attempt 保持未领取的 PREPARED。<br>- 只看锁目录 mtime：超过 300 s 视为过期，删除后接管；`owner.json` 只写不读，不做归属校验；锁只保护 run 的预算复核与领取临界区，prepare、collect、mark、verdict、cleanup 都不取锁。<br>- attempt 级互斥靠 `claim/`：已存在时报“该 attempt 已被领取，不能重复运行。”（3）；入口处对非“未领取 PREPARED”报“…只能运行未领取的 PREPARED attempt；返工请重新 prepare。”（3）。<br>- 争最后一次额度时只有一个 attempt 能建 claim，落败方报 “BUDGET_EXCEEDED：已达到 max_attempts_total=%d。”（3），保持 PREPARED、没有 claim。 | LB-LIFE-005–007、012、013、038；:2583-2613、3255-3257、3300-3315 | `test_budget_race` “exactly one attempt claims the last budget slot”<br>`test_stuck_states` “claimed PREPARED attempt cannot run again”<br>条目状态：LB-LIFE-005 measured/PASS；LB-LIFE-006 source_inspected/NOT_RUN；LB-LIFE-007 measured/PASS；LB-LIFE-012 measured/PASS | 规则 source_inspected；预算竞争与已领取拒绝 measured / PASS（Windows）。锁等待超时、过期接管、归属缺失没有测试 |
| 7d | 候选漂移的旧结果 | - **check 运行前**：执行 worktree（原地）或干净副本（`--fresh`）与 candidate.tree 比较；有被修改的候选文件，或去掉缓存类后仍有候选之外的新文件时，写 `{"aborted":"candidate_drift"}`，报“工作副本与候选不一致…”，**退出 4**。<br>- **check 运行后**：检查改动了候选文件或产生候选外新文件时，记录 modified_by_checks / unexpected_files_by_checks，退出 1，之后 G4 失败。<br>- **verdict 的 G6**：重新快照执行 worktree，被修改或删除的候选文件 → “候选文件在记录后被修改：…”（整树只差行尾时给专门消息）；候选外新文件只作备注；worktree 不存在时跳过比较。<br>- **cleanup**：有未保存内容时逐行 `LOSS`，不带 `--force` 拒绝（3）。<br>- branch 不比较漂移，只用 candidate.tree。 | LB-GATES-010–014、030、035、037；:858-870、4002-4052、4237-4253、4444-4467 | `test_candidate_drift_and_artifacts` “in-place check refuses unexpected extra file”、“fresh check ignores worktree extras”、“python cache files are allowed artifacts”、“check creating unexpected file -> exit 1”、“PASS refused when checks created files (G4)”<br>`test_cleanup_protects_unsaved_work` “cleanup refuses when candidate files were modified”、“cleanup --force removes and logs discarded content”<br>`test_v22_netperf_feedback` “line_endings_only recognises CRLF-only drift” | 规则 source_inspected；check 与 cleanup 层 measured / PASS（Windows）。verdict 层 G6 漂移失败没有断言 |
| 7e | 补丁不完整的旧结果 | - collect 用 `git diff --binary --no-ext-diff --no-textconv --no-renames --full-index <base> <tree>` 生成 candidate.patch（独占创建），再用临时索引 `apply --cached` 往返校验，结果写入 candidate.json 的 patch_roundtrip_verified；**往返失败不改变收集状态**。<br>- `candidate_patch_ok` = verified 为真、candidate.patch 是文件、其 sha256 等于记录值；为假时 G6 失败“候选补丁缺失、被改动或未通过往返校验”（PASS 被拒），`check --fresh` 与 mutate 拒绝（3）；原地 check 不检查。<br>- branch 不调用 candidate_patch_ok；树对象丢失时按补丁重建，不校验 patch_sha256，重建结果不一致时退出 3，补丁也缺失时推断为未捕获异常。 | LB-GATES-005–007、012、030、035；:816-830、2517-2532、3474-3477、3987-3988、4254-4255、4344-4352 | `test_happy` “candidate roundtrip verified”、“fresh check passes in clean copy and removes it”、“branch tree == candidate tree”<br>条目状态：LB-GATES-005 measured/PASS；LB-GATES-006 measured/PASS；LB-GATES-030 measured/PASS | 规则 source_inspected；只有正向用例 measured / PASS（Windows）。补丁缺失、被篡改、sha256 不符、往返失败都没有测试 |

## 2. G0–G6 取证表（替换文档 7.3 占位表）

名称只来自 `.agents/skills/review-pi/gates.md:7-13`（source_reported）；语义与源码行来自 `evaluate_gates`（scripts/pi_dispatch.py:4152-4256，source_inspected）；测试结果来自本次 `bl-01t1-legacy-20260925`（measured，只限 Windows）。每门初始为 `{passed: true, problems: [], notes: []}`，求值顺序见第 1 节第 4 行，逐条 problem 原文见 5.6。

| 旧门禁 | 真实名称/语义 | 源码行 | 原测试标识与 check 名 | 平台与结果（本次 Windows） | 本次状态 | P4 更新（第 12 节；最终取证，只限 Windows） |
|---|---|---|---|---|---|---|
| G0 | **输入一致**。run_dir 中 plan.md、contract.json 的 SHA-256 与 meta 记录一致（文件缺失也失败）；`rev-parse --verify --quiet <base>^{commit}` 等于 meta.base_sha。meta.json 本身不校验；contract.json 被改后 G3/G4 仍按被改的合同判定 | :4160-4163、2659-2665、768-770 | 只有正向：`test_happy` “PASS accepted”（七门全过） | 正向 PASS | 语义 source_inspected；**没有失败路径测试**（NOT_RUN） | **P4**：失败路径 measured / PASS（P4-G01）：plan.md 被改或缺失、contract.json 被改 → 哈希不一致；base_sha 不可用 →“基线提交不可用”（同时 G6 无法重新快照）；meta.json 不校验；contract.json 缺失或不是 JSON 时 load_attempt 回溯、退出 1，G0 来不及报告（可疑）。run 入口的同一核对见 P4-C56（退出 3）。仍未覆盖：无 |
| G1 | **执行完整**。run.json 存在；未超时；未中断；Pi 退出码为 0（None 也失败）；events-summary 的每条 problem 都是一项失败，文件缺失记“缺少事件摘要”。备注：提供商未回报思考级别、执行报告状态不是 json_ok | :4165-4182（problem 来源 :2338-2365） | `test_events_and_thinking` “PASS refused on G1”、“ACCEPTED_WITH_EXCEPTION with waiver”、“missing JSON report does not block PASS”<br>`test_feedback_v12` “PASS is refused when the run ended on a textual tool call” | 4/4 PASS | 事件类失败路径（stopReason=error、文本工具调用）measured / PASS；缺少 run.json、超时、取消、非 0 退出码经 verdict 触发的 G1 失败**没有测试** | **P4**：measured / PASS：缺 run.json（同时报“Pi 退出码为 None”）与缺事件摘要（P4-G02）；没有 agent_settled（P4-G03）；Pi 非 0 退出而 run 为 0（P4-G04、E20）；超时（P4-G05、L05）；取消（Windows CTRL_BREAK：P4-G07、L01；恢复合成 run.json：P4-L22）；INFRA_FAILURE 可复审（P4-G24）。仍未覆盖：POSIX 的 SIGINT 取消（P4-L03，本机 NOT_RUN） |
| G2 | **范围合规**。scope.json 存在，且 violations 为空（每条违规记为 `<kind> <path>`）。备注：主工作区规划路径之外的变化、执行器访问工作副本外路径；mode_changed、sensitive_file、dependency_manifest_changed 与可疑命令不进入 G2 | :4188-4199 | `test_scope` “PASS refused on scope violation (G2)”<br>（evaluate_scope 层另有 `test_scope` “README out_of_scope”；`test_commit_outside_main` “HEAD moved is a violation”） | 3/3 PASS | 范围违规失败路径 measured / PASS；缺少 scope.json 与 G2 备注没有经 verdict 断言 | **P4**：measured / PASS：违规逐行与缺 scope.json（P4-G08）；主工作区变化的备注写入 verdict 记录（P4-G09）。仍未覆盖：“执行器访问了工作副本外路径”备注（:4199）未经 verdict 断言 |
| G3 | **行为正确**。有有效的检查记录；DoD 引用的 `scope` 证据要求 scope.json 存在且无违规；引用的检查 id 在最近一次记录中通过（`review` 跳过）。备注：执行报告列出的合同矛盾、未申报的歧义提及 | :4183-4187、4200-4205、4228-4236 | 只有备注：`test_feedback_v12` “verdict prints the G3 note about undeclared ambiguity” | PASS（备注） | **没有失败路径断言**：scope 证据失败在 test_scope 中实际发生（默认 D02 evidence=['scope']）但只断言 G2；检查引用失败没有测试（NOT_RUN） | **P4**：失败路径 measured / PASS：“没有有效的独立检查记录”（:4204；未 check、aborted 记录、空 checks/NN：P4-G14、G18、G21）；scope 证据失败（:4232；P4-G08）；检查引用失败（:4236；P4-G10–G12）；review 证据被跳过（P4-G12）。仍未覆盖：执行报告列出合同矛盾时的备注（:4184）未经 verdict 断言 |
| G4 | **回归检查**。最近一次 `checks/NN/checks.json` 存在、非空、没有 aborted；针对当前候选树；covers_all_required 为真；未修改候选文件；未产生候选外新文件；合同中每个 required 检查都通过。备注：缓存文件、原地或干净副本模式 | :4200-4227 | `test_candidate_drift_and_artifacts` “PASS refused when checks created files (G4)” | PASS | 只有“产生候选外新文件”一种失败路径 measured / PASS；无有效记录、非当前候选、未覆盖必要检查、修改候选文件、必要检查失败**没有测试** | **P4**：失败路径 measured / PASS：无有效记录（P4-G14、G18、G21）；非当前候选与未覆盖必要检查（P4-G10）；修改候选文件（P4-G13）；必要检查失败（P4-G11）。仍未覆盖：干净副本模式的备注（:4219）未经 verdict 断言 |
| G5 | **质量复审**。没有机械断言，恒为通过，只写固定备注“质量复审（测试是否弱化、兼容性、残余风险）由复审报告负责，工具不做机械判断” | :4152、4153-4154 | 无 | —（没有 check） | **没有测试**（也没有可测的失败路径） | **P4**：measured / PASS：恒通过与固定备注出现在 PASS 记录（P4-G09）和 REVISE 记录（P4-G23）中。仍没有可测的失败路径 |
| G6 | **可集成**。执行 worktree 是目录时重新快照（label gate，会写 Git 对象）：被修改或删除的候选文件为失败（整树只差行尾时给专门消息，快照抛错也失败），候选外新文件只作备注；不论前面结果都检查 candidate_patch_ok（补丁存在、sha256 不变、往返通过） | :4237-4255 | 正向：`test_v22_netperf_feedback` “verdict PASS survives a later autocrlf change (snapshot pinned to the recorded value)”<br>单元：`test_v22_netperf_feedback` “line_endings_only recognises CRLF-only drift”<br>间接：`test_happy` “candidate roundtrip verified” | 3/3 PASS | 只有正向 measured / PASS；**没有失败路径断言**（“记录后修改”在 test_cleanup_protects_unsaved_work 的 REVISE verdict 中触发但未断言；只差行尾、补丁缺失或被改、往返失败、无法重新快照都没有测试） | **P4**：失败路径 measured / PASS：记录后修改与删除（:4248）、只差行尾的专门消息（:4244，含运行后 autocrlf 改变）、只差行尾 + 新文件被报成修改（可疑）、无法重新快照（:4253）（P4-G15）；检查改写候选（P4-G13）；新增文件只作备注（P4-G09）；worktree 不存在时跳过漂移、只查补丁（P4-G16）；补丁缺失、字节被改、sha256 不符、往返标记为 false（:4255，P4-G17）。仍未覆盖：真实的往返失败（P4 改的是记录字段）；重新快照写 Git 对象未断言 |

没有失败路径测试的门禁：**G0**（全部）、**G3**（失败未断言）、**G5**（无机械判定）、**G6**（失败未断言）；G1、G2、G4 只覆盖部分失败原因。verdict 的以下拒绝分支也没有测试：PASS 带 `--waive`、ACCEPTED_WITH_EXCEPTION 缺某个失败门禁的豁免或缺 `--decided-by`、没有门禁失败时 AWE 仍需至少一项 `--waive`、REVISE/BLOCKED/ESCALATE 缺 `--class`。

**P4 更新**（第 12 节，只限 Windows）：上一段列出的门禁与 verdict 缺口已由 P4 方法 measured / PASS。

- 门禁：G0（P4-G01）、G3（P4-G08、G10–G12、G14、G18）、G5（P4-G09、G23）、G6（P4-G13、G15–G17）；G1、G2、G4 的其余原因见上表 P4 列。
- verdict 拒绝分支：PASS 带 `--waive`（P4-G22）；ACCEPTED_WITH_EXCEPTION 缺某个失败门禁的豁免或缺 `--decided-by`（P4-G21、C59）；没有门禁失败时仍需至少一项 `--waive`（P4-G22）；REVISE/BLOCKED/ESCALATE 缺 `--class`（P4-G21、C59）；另有非 REVIEWABLE 状态被拒（P4-G20、C58）与重复记录（P4-G22、G23）。
- P4 后仍未覆盖：G2“执行器访问了工作副本外路径”、G3 合同矛盾、G4 干净副本模式三条备注未经 verdict 断言；G1 取消的 POSIX 路径（P4-L03，NOT_RUN）；G5 仍没有可测的失败路径；Linux、macOS 全部 NOT_RUN。

## 3. v1 合同规范化与校验（LB-CONTRACT）

> **纳入说明**：本节是区域章节原稿（已经对抗核对），正文照录，只统一了标题层级并修正排版。
> - 原稿编写时尚未取得 `bl-01t1-legacy-20260925` 的运行结果，文中“没有运行”“未运行”“NOT_RUN”“结果未知”等说法描述的是原稿编写时的状态；本次运行结果见本文第 0.3、2、9、10 节。
> - 正文中的“第 k 节”“见第 k 节”指本区域内的 3.k 小节，不是本文的第 k 节。
> - 标“实测”“探针”的内容是起草或核对者在会话临时目录中的一次性复现，没有归档为 fixture，证据等级仍按 source_inspected 记。

**来源与取证方式**

- 源码：`scripts/pi_dispatch.py`。
  - 提交：a4fa199b0e5bdc658215765ee7558b9fe6723940，文件 blob 为 8e7df57c91fc589895c171254e71cbc3d056c313。
  - 工作区中的这个文件与该 blob 相同。
  - 工具版本：`TOOL_VERSION = "2.2.2"`（scripts/pi_dispatch.py:48）。
- 测试：`tests/test_dispatch.py`，blob 为 b8fdd332566ceb33049240c39d2faf1258bad43b。
- 技能资料：`.agents/skills/plan-task/contract-template.md`、`contract-template.json`，以及 `examples/normalize-query.v1.*`。
- 证据基础：全部条目都来自源码阅读（source_inspected）。
  - 标“实测”的条目，核对者另在 scratchpad 中复现过，方式有两种：
    - 内存探针：`import pi_dispatch` 后直接调用函数；
    - 在临时 Git 仓库中运行 CLI：`python scripts/pi_dispatch.py --repo <临时仓库> validate|derive-json …`。
  - 实测平台：Windows Server 2025，Python 3.12.10。
  - 探针脚本是临时文件，没有归档成 fixture。
- 本节**没有**运行 `tests/test_dispatch.py`。表中的测试名只是源码里的 check 名称，没有本次的执行结果。

### 3.1 常量与词表（LB-CONTRACT-001、002）

| 名称 | 取值或规则 | 位置 |
|---|---|---|
| `CONTRACT_SCHEMA_VERSION` | `1` | scripts/pi_dispatch.py:49 |
| 退出码常量 | `EXIT_OK=0`、`EXIT_FAIL=1`、`EXIT_USAGE=2`、`EXIT_BLOCKED=3`、`EXIT_DRIFT=4` | scripts/pi_dispatch.py:53 |
| `PLAN_KEY_RE` | `task-id.vN`。task 为 1–64 个 `[a-z0-9-]`，首字符不能是 `-`；N 为 1–9999，不能有前导 0。实测 v0、v01、v10000 和以 `-` 开头的 task 都被拒绝，64 字符的 task 通过，65 字符的被拒绝 | scripts/pi_dispatch.py:55 |
| `TASK_ID_RE` | 与 task 组的规则相同；合同校验不用它，只在 :2636 与 :4554 使用 | scripts/pi_dispatch.py:56 |
| `SHA_RE` | 40 或 64 位小写十六进制 | scripts/pi_dispatch.py:57 |
| `ITEM_ID_RE` | 大写字母开头，其后 0–31 个 `[A-Z0-9_-]`；用于 setup、checks 与 DoD 的 id | scripts/pi_dispatch.py:58 |
| `MODEL_TOKEN_RE` | provider 与 model：字母或数字开头，其后 0–199 个 `[A-Za-z0-9._:/@+-]` | scripts/pi_dispatch.py:59 |
| `ENV_NAME_RE` | setup 与 checks 项 `env` 的变量名：字母或下划线开头，其后 0–127 个 `[A-Za-z0-9_]` | scripts/pi_dispatch.py:60 |
| `PLACEHOLDER_RE` | 字面 `【待填` 或 `REPLACE_WITH`，区分大小写，不锚定，用 `.search` 调用 | scripts/pi_dispatch.py:61 |
| `KNOWN_TOOLS` | read, bash, powershell, edit, write, grep, find, ls | scripts/pi_dispatch.py:65 |
| `DEFAULT_TOOLS` | read, grep, find, ls, edit, write, bash | scripts/pi_dispatch.py:66 |
| `DEFAULT_THINKING` | `high` | scripts/pi_dispatch.py:67 |
| `FALLBACK_THINKING_LEVELS` | off, minimal, low, medium, high, xhigh, max。validate 把它当作硬性词表使用 | scripts/pi_dispatch.py:68、scripts/pi_dispatch.py:1489 |
| `EXECUTOR_ACTIONS` | local_edit, local_test, local_commit, network | scripts/pi_dispatch.py:71 |
| `INTEGRATION_ACTIONS` | local_branch, commit, push, open_pr, merge, deploy | scripts/pi_dispatch.py:72 |
| `RISK_LEVELS` | low, medium, high | scripts/pi_dispatch.py:73 |
| `EVIDENCE_TOKENS` | scope, review | scripts/pi_dispatch.py:74 |
| `REQUIRED_MD_SECTIONS` | 共 13 个：Identity, Goal, Non-goals, Repository facts, Scope, Behavior contract, Steps, Validation commands, Definition of done, Stop conditions, Budget, Report back, Forbidden。Setup 不在其中 | scripts/pi_dispatch.py:83-85 |
| `PROTECTED_PATTERNS` | `.agent/**` `.claude/**` `.codex/**` `.pi/**` `.agents/**` `.gitmodules` `**/AGENTS.md` `**/AGENTS.override.md` `**/CLAUDE.md` `**/CLAUDE.local.md` `scripts/pi_dispatch.py` `scripts/dispatch-pi.sh`。校验时忽略大小写，并与 `extra_protected_paths` 合并 | scripts/pi_dispatch.py:88-92、scripts/pi_dispatch.py:1500 |

**`$` 与末尾换行**

- 锚定的正则（PLAN_KEY_RE、TASK_ID_RE、SHA_RE、ITEM_ID_RE、MODEL_TOKEN_RE、ENV_NAME_RE）都写成 `^…$`，用 `.match` 调用。`$` 也匹配末尾换行之前的位置。
  - 实测：SHA、ITEM、PLAN、MODEL、ENV 这 5 个正则对带一个末尾 `\n` 的值都返回匹配。
- glob 匹配已为同一原因改用 `fullmatch`，见 scripts/pi_dispatch.py:1092 的注释与 `test_units` 中的 “glob uses fullmatch (no trailing newline match)”。上述 ID 正则没有改。
- 实际影响：
  - CLI 的计划标识会先 `strip()`（scripts/pi_dispatch.py:1013），带不进换行。
  - JSON 中 `base_sha` 带末尾换行时，能通过 SHA_RE。但实测会报两条错误：Identity 的 base_sha 与 JSON 不一致；`base_sha 在本仓库中不存在或不是提交`。退出码 2。

### 3.2 schema v1 缺省值（`normalize_contract`，scripts/pi_dispatch.py:1189-1214；LB-CONTRACT-003、004）

| 字段 | 缺省值 | 位置 |
|---|---|---|
| `executor.thinking` | `"high"` | scripts/pi_dispatch.py:1193 |
| `executor.tools` | `["read","grep","find","ls","edit","write","bash"]` | scripts/pi_dispatch.py:1193 |
| `executor.context_files` | `"project"` | scripts/pi_dispatch.py:1193 |
| `scope.allowed_modified_files`、`allowed_new_files`、`allowed_deleted_files`、`forbidden_paths` | `[]` | scripts/pi_dispatch.py:1194 |
| `scope.dependency_changes` | `"forbidden"` | scripts/pi_dispatch.py:1195 |
| `authorization.executor` | `["local_edit","local_test"]` | scripts/pi_dispatch.py:1196 |
| `authorization.integration` | `[]` | scripts/pi_dispatch.py:1196 |
| `budget.max_attempts_total` | `2` | scripts/pi_dispatch.py:1197 |
| `budget.max_wall_seconds_per_attempt` | `1200` | scripts/pi_dispatch.py:1197 |
| `budget.max_wall_seconds_total` | `2400` | scripts/pi_dispatch.py:1198 |
| `budget.cost_budget` | `null` | scripts/pi_dispatch.py:1198 |
| `setup`、`checks`、`definition_of_done` | `[]` | scripts/pi_dispatch.py:1205-1206 |
| `checks[]` 中是对象的项 | `cwd="."`、`required=true`、`expected_exit_code=0` | scripts/pi_dispatch.py:1207、scripts/pi_dispatch.py:1209-1213 |
| `setup[]` 中是对象的项 | `cwd="."`、`expected_exit_code=0`，不补 `required` | scripts/pi_dispatch.py:1208-1213 |
| 只在读取时生效，不写回 | `expect_on_base="any"`、`output_must_match=[]`、`output_must_not_match=[]`、`env={}`；判断必要检查时 `required` 按 True 处理 | scripts/pi_dispatch.py:1171、scripts/pi_dispatch.py:1174、scripts/pi_dispatch.py:1183、scripts/pi_dispatch.py:1533、scripts/pi_dispatch.py:1562 |
| 没有缺省，校验要求必须合法 | `schema_version`、`task_id`、`plan_version`、`base_sha`、`risk_level`；命令项的 `id`、`argv`、`timeout_seconds`；DoD 项的 `id`、`text`、`evidence` | scripts/pi_dispatch.py:1459-1469、scripts/pi_dispatch.py:1149-1166、scripts/pi_dispatch.py:1545-1555 |
| 没有缺省，也不要求 | `executor.provider`、`executor.model`：缺失或为 null 时 validate 通过（CLI 实测退出码 0），非 null 时才检查格式。`title`、`repository` 与其他未知字段不校验，只受 JSON 占位符检查约束 | scripts/pi_dispatch.py:1484-1487、scripts/pi_dispatch.py:1586-1587 |

补齐方式：

- 先深拷贝：`json.loads(json.dumps(raw))`（scripts/pi_dispatch.py:1191）。
  - raw 中有不能序列化的对象时抛 `TypeError`，被包装成 `合同结构无效：TypeError: …`（实测：set）。
  - 经 CLI 调用时，raw 来自 `json.loads`，所以这个分支只在进程内直接调用时可达。
- 用 `setdefault` 补齐，只处理**缺失的键**；**显式 `null` 保留**（scripts/pi_dispatch.py:1200-1206）。
  - 实测：`"thinking": null` 只报一条取值错误，不再报 Markdown 中 thinking 不一致，因为那项比较要求值是 str（scripts/pi_dispatch.py:1610）。
- 节存在但类型不对时不补，交给校验报错；数组中不是对象的项也不补（scripts/pi_dispatch.py:1202、scripts/pi_dispatch.py:1209-1211）。
- 实测 `normalize_contract({})` 的输出与上表一致。
- `load_attempt` 读取 attempt 内的 `contract.json` 时，会再做一次 normalize（scripts/pi_dispatch.py:2655）。
  - prepare 复制进 attempt 的是**原始 JSON 文件**，不是补齐后的合同（scripts/pi_dispatch.py:3196）。

### 3.3 拒绝条件与检查顺序（`_validate_contract`，scripts/pi_dispatch.py:1440-1634；LB-CONTRACT-005–013）

- “级别”一列中，“返回”表示命中后立即返回；没有注明的一律是 ERROR，并继续累积。
- 从第 4 步起不再提前返回。最后只要有 error，就返回 `contract=None`（scripts/pi_dispatch.py:1634）。
- 包装层 `validate_contract` 只捕获 `TypeError`、`AttributeError`、`ValueError` 与 `KeyError`，其他异常原样抛出。

| # | 条件 | 级别 | 报错文本（关键片段） | 位置 |
|---|---|---|---|---|
| 0 | 包装层捕获上述四类异常 | ERROR，丢弃已收集的警告 | `合同结构无效：<类名>: <消息>` | scripts/pi_dispatch.py:1432-1437 |
| 1 | plan_key 不匹配 `PLAN_KEY_RE`（经 CLI 不可达：`plan_key_from_arg` 已先拒绝） | ERROR，返回 | `计划标识不合法：<key>（格式 task-id.vN）` | scripts/pi_dispatch.py:1444-1446 |
| 2 | raw 不是 dict | ERROR，返回 | `机器合同顶层必须是 JSON 对象` | scripts/pi_dispatch.py:1447-1448 |
| 3 | normalize 后，executor、scope、authorization、budget 不是对象；setup、checks、definition_of_done 不是数组 | ERROR，本组收齐后返回（实测 `executor=["x"]` 加 `checks={}` 只得到这两条） | `<节> 必须是对象`、`<节> 必须是数组` | scripts/pi_dispatch.py:1450-1458 |
| 4 | `schema_version != 1`（Python 相等比较：true 与 1.0 能通过，字符串 "1" 被拒，均已实测） | ERROR | `schema_version 必须为 1` | scripts/pi_dispatch.py:1459-1460 |
| 5 | task_id 与文件名中的 task 不同 | ERROR | `task_id 应为 <task>，实际为 <repr>` | scripts/pi_dispatch.py:1461-1462 |
| 6 | plan_version 与文件名中的版本不同（1.0 与 true 对 v1 能通过，已实测） | ERROR | `plan_version 应为 <N>，实际为 <repr>` | scripts/pi_dispatch.py:1463-1464 |
| 7 | base_sha 不是 str，或不匹配 `SHA_RE` | ERROR | `base_sha 必须是完整的 40/64 位小写提交 ID` | scripts/pi_dispatch.py:1465-1467 |
| 8 | risk_level 不在词表中 | ERROR | `risk_level 必须是 low/medium/high 之一` | scripts/pi_dispatch.py:1468-1469 |
| 9 | authorization.executor 不是字符串数组，或含词表外的值。命中后该值记为 None，local_test 警告与 Markdown 比较都跳过它 | ERROR | `authorization.executor 只能包含：local_edit, local_test, local_commit, network` | scripts/pi_dispatch.py:1472-1475 |
| 10 | authorization.executor 格式合法但不含 local_edit（重复项不报错，已实测） | ERROR | `authorization.executor 必须包含 local_edit` | scripts/pi_dispatch.py:1476-1477 |
| 11 | authorization.integration 不是字符串数组，或含词表外的值。命中后同样记为 None | ERROR | `authorization.integration 只能包含：local_branch, commit, push, open_pr, merge, deploy` | scripts/pi_dispatch.py:1478-1481 |
| 12 | provider 或 model 不为 null，且不是合法字符串（空串也拒绝，已实测） | ERROR | `executor.<field> 不合法：<repr>` | scripts/pi_dispatch.py:1484-1487 |
| 13 | thinking 不是词表中的 str | ERROR | `executor.thinking 必须是 off, minimal, low, medium, high, xhigh, max 之一` | scripts/pi_dispatch.py:1488-1490 |
| 14 | tools 为空、不是字符串数组，或含 `KNOWN_TOOLS` 以外的值 | ERROR | `executor.tools 必须是非空字符串数组，且只含：read, bash, powershell, edit, write, grep, find, ls` | scripts/pi_dispatch.py:1491-1493 |
| 15 | tools 合法、authorization.executor 合法且含 local_test，但 tools 中既没有 bash 也没有 powershell | **WARN** | `授权了 local_test 但工具集没有 bash/powershell：执行器无法自检，检查将只由验收端运行` | scripts/pi_dispatch.py:1494-1495 |
| 16 | context_files 不是 project 或 none | ERROR | `executor.context_files 必须是 project 或 none` | scripts/pi_dispatch.py:1496-1497 |
| 17 | scope 的四个列表之一不是数组 | ERROR | `scope.<field> 必须是数组` | scripts/pi_dispatch.py:1503-1507 |
| 18 | 路径模式不合法，只报第一个问题，依次检查：非空字符串 → 控制字符 → 含反斜杠 → 绝对路径（以 `/`、`<字母>:` 或 `~` 开头；实测 `a:b` 也被拒）→ 空段、`.` 或 `..` → 恰为 `*`、`**` 或 `**/*` | ERROR | `scope.<field> 中的 <repr> <问题>` | scripts/pi_dispatch.py:1508-1511、scripts/pi_dispatch.py:1100-1113 |
| 19 | 三个 allowed 集合中合法的模式，按**字面文本**命中受保护模式（包括 extra_protected_paths，忽略大小写） | ERROR | `scope.<field> 包含受保护路径 <p>（合同、代理规则与调度器不得委派修改）` | scripts/pi_dispatch.py:1500、scripts/pi_dispatch.py:1512-1518 |
| 20 | allowed_modified_files 与 allowed_new_files 的**原值**都为假值。判断的是原值真假，不是合法模式的个数：`[""]` 或非数组字符串都不触发（已实测） | ERROR | `scope 至少要允许修改或新增一个文件` | scripts/pi_dispatch.py:1519-1520 |
| 21 | 不含 `*` 的允许模式被 forbidden glob 完整匹配，区分大小写。含 `?` 的模式按字面参与比较 | ERROR | `路径 <p> 同时出现在允许集合与 forbidden_paths` | scripts/pi_dispatch.py:1521-1524 |
| 22 | dependency_changes 不是 forbidden 或 allowed | ERROR | `scope.dependency_changes 必须是 forbidden 或 allowed` | scripts/pi_dispatch.py:1525-1526 |
| 23 | setup 与 checks 的各项（见下表） | ERROR | 见下表 | scripts/pi_dispatch.py:1528-1531 |
| 24 | 在是对象且 id 为 str 的检查中，没有一项 `required is True`。required 写成 "yes" 这类非布尔真值也不算（实测会同时报类型错误） | ERROR | `至少需要一个 required 为 true 的检查：没有可独立运行的检查，验收门禁无法通过` | scripts/pi_dispatch.py:1532-1534 |
| 25 | DoD 为空 | ERROR | `definition_of_done 必须是非空数组` | scripts/pi_dispatch.py:1539-1540 |
| 26 | DoD 项不是对象 | ERROR | `definition_of_done 项必须是对象` | scripts/pi_dispatch.py:1542-1544 |
| 27 | DoD id 不合法、与前面的 DoD 重复，或与某个检查 id 同名。与 setup id 同名不报错（已实测） | ERROR | `DoD id 不合法或重复：<repr>` | scripts/pi_dispatch.py:1545-1549 |
| 28 | text 不是非空 str | ERROR | `<id> 缺少 text` | scripts/pi_dispatch.py:1550-1551 |
| 29 | evidence 不是非空字符串数组；命中后该项其余的检查跳过 | ERROR | `<id> 的 evidence 必须是非空字符串数组（检查 id、scope 或 review）` | scripts/pi_dispatch.py:1552-1555 |
| 30 | evidence 中有既不是检查 id、也不是 scope 或 review 的值；引用 setup id 也报这条（已实测） | ERROR | `<id> 的证据 <repr> 不是已定义的检查 id，也不是 scope/review` | scripts/pi_dispatch.py:1556-1560 |
| 31 | required 为真值的检查没有被任何 DoD 引用；required=false 的检查不警告（已实测） | **WARN** | `必要检查 <id> 没有被任何 DoD 引用` | scripts/pi_dispatch.py:1561-1563 |
| 32 | max_attempts_total 不是 1..20 的 int（bool 拒绝） | ERROR | `budget.max_attempts_total 必须是 1..20 的整数` | scripts/pi_dispatch.py:1569-1570 |
| 33 | max_wall_seconds_per_attempt 不是 60..86400 的 int。命中后记为 None，见下方“级联错误” | ERROR | `budget.max_wall_seconds_per_attempt 必须是 60..86400 的整数` | scripts/pi_dispatch.py:1571-1573 |
| 34 | max_wall_seconds_total 不是 int（bool 拒绝），或小于单轮上限。没有上限；单轮上限不合法时只检查类型 | ERROR | `budget.max_wall_seconds_total 必须是整数且不小于单轮上限` | scripts/pi_dispatch.py:1574-1575 |
| 35 | cost_budget 既不是 null，也不是 `{amount: 非 bool 的 int/float 且 >=0, currency: str}`。实测 amount 为 Infinity 时通过，为 NaN 时被拒 | ERROR | `budget.cost_budget 必须为 null 或 {amount, currency}` | scripts/pi_dispatch.py:1576-1580 |
| 36+ | Markdown 与 JSON 的比较（见第 4 节） | ERROR | 见第 4 节 | scripts/pi_dispatch.py:1582-1633 |

命令项的检查（`_validate_command`）。先检查 setup 再检查 checks，两组共用一个 `seen`：

| # | 条件 | 报错文本（关键片段） | 位置 |
|---|---|---|---|
| a | 不是对象（该项到此为止） | `<group> 项 必须是对象` | scripts/pi_dispatch.py:1145-1148 |
| b | id 不是 str，或不匹配 `ITEM_ID_RE` | `<group> 项 的 id 不合法：<repr>（例如 V01、S01）` | scripts/pi_dispatch.py:1150-1152 |
| c | id 与前面的 setup 或 checks 重复（已实测） | `id 重复：<id>` | scripts/pi_dispatch.py:1153-1155 |
| d | argv 不是非空字符串数组（元素也不能为空串）；或 argv 含 NUL | `<id> argv 必须是非空字符串数组`；`<id> argv 含 NUL 字符` | scripts/pi_dispatch.py:1156-1160 |
| e | cwd（读取时缺省为 `.`）不等于 `.`，且 pattern_error 报了问题。实测 `""` 得到 `必须是非空字符串` | `<id> cwd 不合法：<问题>` | scripts/pi_dispatch.py:1161-1163 |
| f | timeout_seconds 不是 1..86400 的 int（没有缺省，bool 拒绝；缺失时报错，已实测） | `<id> timeout_seconds 必须是 1..86400 的整数` | scripts/pi_dispatch.py:1164-1166 |
| g | expected_exit_code 不是 int（bool 能通过，已实测；没有范围限制） | `<id> expected_exit_code 必须是整数` | scripts/pi_dispatch.py:1167-1168 |
| h | 仅 checks：required 不是 bool | `<id> required 必须是布尔值` | scripts/pi_dispatch.py:1169-1170 |
| i | 仅 checks：expect_on_base 不在 any、fail、pass 中 | `<id> expect_on_base 只能是 fail、pass 或 any` | scripts/pi_dispatch.py:1171-1172 |
| j | output_must_match 或 output_must_not_match 不是字符串数组；或 `re.compile` 抛 `re.error`。**抛 OverflowError 时不捕获**（例如 `a{4294967296}`，CLI 实测 traceback，退出码 1） | `<id> <key> 必须是字符串数组`；`<id> <key> 正则无效：<异常>` | scripts/pi_dispatch.py:1173-1182 |
| k | env 不是 `{ENV_NAME_RE 变量名: str}` | `<id> env 必须是 {变量名: 字符串}` | scripts/pi_dispatch.py:1183-1186 |

不合法的 id 仍以 `str(id)` 记入 `seen`，并继续参与后面的判断：check_ids、必要检查警告与 Markdown 比较（scripts/pi_dispatch.py:1152、scripts/pi_dispatch.py:1532）。实测 id 写成 `v01` 时，还会报 `必要检查 v01 没有被任何 DoD 引用`。报错文本中出现的 `<id>` 也是这个 `str(id)`。

**级联错误**（均已实测）：

- per_attempt 不合法时，JSON 侧记为 None，Budget 比较会多报一条。例如 per=10、total=5 时得到两条错误：范围错误，以及 `Markdown Budget 的 max_wall_seconds_per_attempt（10）与 JSON（None）不一致`。不报 total 错误（scripts/pi_dispatch.py:1573、scripts/pi_dispatch.py:1619-1622）。
- Budget 章节缺失，或标题写成 `## Budget (v1)`、`### Budget` 时，报缺少章节，外加 3 条 Budget 不一致。
- JSON 的 risk_level 为 `Low`、Markdown 为 `low` 时报两条：取值错误与 Identity 不一致。两边都写 `Low` 时只报取值错误一条。

### 3.4 Markdown 与 JSON 的一致性（scripts/pi_dispatch.py:1582-1633；LB-CONTRACT-014–017）

| 顺序 | 比较项 | 规则 | 报错文本（关键片段） | 位置 |
|---|---|---|---|---|
| 1 | Markdown 占位符 | 全文 search，区分大小写。出现在任何位置（包括 Forbidden 节）都拒绝；小写 `replace_with` 不拦（均已实测） | `Markdown 合同仍包含占位符（【待填…】或 REPLACE_WITH…）` | scripts/pi_dispatch.py:1584-1585 |
| 2 | JSON 占位符 | 在**原始** raw（未 normalize）上检查，先用 `ensure_ascii=False` 重新序列化。未知字段也检查（实测 `title="REPLACE_WITH x"`）；文件中用 Unicode 转义写的 `【待填` 同样检出（已实测） | `JSON 合同仍包含占位符（…）` | scripts/pi_dispatch.py:1583、scripts/pi_dispatch.py:1586-1587 |
| 3 | 13 个必需章节 | 正则 `^##\s+<名称>\s*$`，多行模式，忽略大小写。`## budget` 算存在；`## Budget (v1)`、`### Budget` 算缺失（已实测）。节体到下一个“`##` 后跟空白”的行或文末为止，`###` 小标题不结束章节（已实测）；同名章节取第一个 | `Markdown 缺少章节：## <名称>` | scripts/pi_dispatch.py:1588-1590、scripts/pi_dispatch.py:1120-1122 |
| 4 | 标题 | 全文第一处行首 `#` + 空白 + `TASK:`，可带反引号，捕获 `[a-z0-9-]+` 后与 task 比较。捕获在第一个不属于该字符集的字符处停止，所以 `# TASK: normalize-queryX`、`# TASK: normalize-query_v2 …` 也能通过。报错的情形：`# TASK: normalize-query-x`；`#TASK:`（`#` 后没有空白）；以 BOM 开头且没有别的标题行。以上均已实测 | `Markdown 标题应为 '# TASK: <task>'` | scripts/pi_dispatch.py:1591-1593 |
| 5 | Identity 的 plan_version、base_sha、risk_level | 字符串完全相等。plan_version 与**文件名中的版本**比较，不与 JSON 比较，文本却写“与 JSON（'N'）”（实测：v2 文件中两边都写 1 时，报 `（'1'）与 JSON（'2'）不一致`）。键缺失，或用全角冒号写导致解析不到时，报的是“（None）与 JSON（…）不一致”，不报“缺少”（已实测） | `Markdown Identity 的 <field>（<md repr>）与 JSON（<repr>）不一致` | scripts/pi_dispatch.py:1594-1598 |
| 6 | authorized_actions、integration_actions | 键缺失时报“缺少”。`- integration_actions:` 冒号后没有任何字符也算缺失（已实测）。冒号后只有空白、写“无”或 none 时为空集（已实测）。其余情况取值中的所有 `[a-z_]+` 片段组成集合（去掉 none），与 JSON 比较；JSON 侧不合法时跳过。写 `local_edit and local_test` 会多出 `and`；大写的 `Local_Branch` 被拆成 `ocal_`、`ranch`（均已实测） | `Markdown Identity 缺少 <field>`；`Markdown Identity 的 <field>（<排序后逗号分隔，空集为 none>）与 JSON（…）不一致` | scripts/pi_dispatch.py:1599-1605、scripts/pi_dispatch.py:1409-1413 |
| 7 | executor 的 provider/model | provider 与 model 都为真值时，Identity 的 executor 值要包含子串 `provider/model` | `Markdown Identity 的 executor 应写明 <p>/<m>` | scripts/pi_dispatch.py:1606-1609 |
| 8 | executor 的 thinking | 只在 thinking 是 str 时检查（取值不合法的 str 也检查）。要求匹配 `thinking\s+<级别>\b`：JSON 为 high、Markdown 写 xhigh 时报错（已实测） | `Markdown Identity 的 executor 应写明 thinking <t>` | scripts/pi_dispatch.py:1610-1611 |
| 9 | Scope 路径 | JSON 中每个通过 pattern_error 的 allowed_* 与 forbidden 模式（包括已报受保护的），都要以**子串**形式出现在 Markdown **全文**某处。只检查 JSON 到 Markdown 这一个方向。实测：只出现在 Goal 中也算；`package.json.bak` 满足 `package.json`；写在非 scope 的键下也通过；Markdown 多列的路径不报错 | `Markdown 未列出 JSON 中的路径：<p>` | scripts/pi_dispatch.py:1612-1614 |
| 10 | dependency_changes | 取 Scope 节中第一处 `dependency_changes` + 半角冒号 + 可选反引号 + 小写字母词，与 normalize 后的 JSON 值比较。全角冒号不识别；散文中先出现的写法优先（均已实测） | `Markdown Scope 的 dependency_changes 与 JSON（<v>）不一致` | scripts/pi_dispatch.py:1615-1617 |
| 11 | Budget 三项 | 在 Budget 节中按 `^\s*[-*]\s*<key>\s*:\s*` + 可选反引号 + `(\d+)` 取值，键名区分大小写。数字必须紧跟冒号（可隔一个反引号），`约 3` 取不到，`` `3`（说明） `` 可以（均已实测）。与 JSON 值的 `str()` 比较；cost_budget 不比较 | `Markdown Budget 的 <key>（<md>）与 JSON（<json>）不一致` | scripts/pi_dispatch.py:1618-1622、scripts/pi_dispatch.py:1221-1228 |
| 12 | 检查 id 所在行 | 对每个是对象且 id 为 str 的检查，Validation commands 节中要有一行以 `\b<id>\b` 含该 id | `Markdown Validation commands 未列出 <id>` | scripts/pi_dispatch.py:1623-1628 |
| 13 | 检查的 argv | argv 是非空字符串数组时，上一项找到的行中至少一行满足以下条件：程序名取最后一段路径，去掉 .exe/.cmd/.bat 后不区分大小写地在行内任意位置查找；其后的各参数区分大小写，按顺序以子串出现。实测 `python3 run_tests.pyx` 也满足 `["python","run_tests.py"]`，顺序颠倒则报错 | `Markdown 中 <id> 的命令与 JSON argv 不一致：<argv 以空格连接>` | scripts/pi_dispatch.py:1629-1630、scripts/pi_dispatch.py:1416-1429 |
| 14 | DoD 编号 | 每个 DoD id（包括非法 id 的 `str()`）都要以 `\b<id>\b` 出现在 Markdown 全文某处 | `Markdown 未出现 JSON 中的编号：<id>` | scripts/pi_dispatch.py:1631-1633 |

Identity 行的解析方式（scripts/pi_dispatch.py:1134-1141、scripts/pi_dispatch.py:1126-1131）：

- 只读 Identity 节，行格式为 `^\s*[-*]\s*([A-Za-z_]+)\s*:\s*(.+?)\s*$`：
  - **只认半角冒号**；
  - 键名区分大小写；
  - 缩进的行也算；
  - 同名键以后出现的为准（已实测）。
- 取值用 `_md_value` 处理：先去掉首尾的反引号与空格，再去掉结尾一个不嵌套的全角或半角括号说明（实测 `` `low`（说明） `` 能通过）。

**不比较的内容**（均属于 scripts/pi_dispatch.py:1582-1633 的覆盖范围之外）：

- setup 与 Markdown 的 Setup 节；
- repository、title；
- checks 的 cwd、timeout、expected_exit_code、output 模式、required、expect_on_base、env；
- DoD 的 text 与 evidence（实测改动后仍通过）；
- executor.tools 与 context_files；
- cost_budget；
- 路径写在 Markdown 的哪个键下；
- Markdown 中多出来的路径、检查或 DoD。

### 3.5 冲突时的优先级（LB-CONTRACT-018）

| 场景 | 旧行为 | 位置 |
|---|---|---|
| validate、prepare 或 baseline 时，被比较的项不一致 | **不设优先级**：一律 ERROR。validate 返回 2；prepare 与 baseline 抛 DispatchError(2) 拒绝继续，不会自动采用任何一方 | scripts/pi_dispatch.py:1634、scripts/pi_dispatch.py:3172-3173、scripts/pi_dispatch.py:4083-4084 |
| 各方读哪一份 | 注释：“Pi 读 Markdown，调度器执行 JSON，与执行相关的内容必须一致”。调度器执行 normalize 之后的 JSON（prepare 与 baseline 用 validate 的返回值，之后的命令用 load_attempt） | scripts/pi_dispatch.py:1582、scripts/pi_dispatch.py:2655 |
| 运行时两者不一致 | 执行说明开头写明二者冲突时停止并报告；“机器合同摘要”由 JSON 生成，要求执行器“停止并在报告中指出，不要自行选择其一” | scripts/pi_dispatch.py:2713、scripts/pi_dispatch.py:2732-2733 |
| 不在比较范围内的字段（见第 4 节） | 只按 JSON 执行，Markdown 写成别的值也不会被发现 | scripts/pi_dispatch.py:1582-1633 |
| derive-json | 由 Markdown 生成 JSON；已有 JSON 需要 `--force` 才覆盖 | scripts/pi_dispatch.py:3029-3031 |

### 3.6 警告与提示（不影响退出码；LB-CONTRACT-009、012、020、021、022）

| 提示 | 触发条件 | 文本（关键片段） | 位置 |
|---|---|---|---|
| WARN | 授权了 local_test，但没有 shell 工具 | `授权了 local_test 但工具集没有 bash/powershell：执行器无法自检，检查将只由验收端运行` | scripts/pi_dispatch.py:1494-1495 |
| WARN | 必要检查没有被 DoD 引用 | `必要检查 <id> 没有被任何 DoD 引用` | scripts/pi_dispatch.py:1561-1563 |
| WARN | Markdown 或 JSON 原文含 Unicode 类别 Cf 的字符（零宽字符、双向控制符、BOM、软连字符等）。按 `splitlines` 逐行检查，行号从 1 开始，每行一条；同一行的多个字符按码位排序、去重后合成一条（实测 `U+200E、U+200F`）。每个文件最多 5 条（实测 8 行只报前 5 行）。JSON 中写成转义文本 `‎` 的不算（已实测）。JSON 解析失败（包括带 BOM）时不产生这类警告；Markdown 以 BOM 开头时报 U+FEFF（CLI 实测） | `<Markdown/JSON> 第 N 行含不可见格式字符 U+XXXX：如果本意是写转义序列，请改回转义文本（或在探针里用 chr()）` | scripts/pi_dispatch.py:1637-1653、scripts/pi_dispatch.py:1674-1675 |
| WARN | 基线提交根目录没有 AGENTS.md（`git cat-file -e <base>:AGENTS.md` 失败；已实测） | `基线提交中没有 AGENTS.md：worktree 基于基线创建，执行器将看不到执行规则` | scripts/pi_dispatch.py:1682-1683 |
| NOTE | HEAD 不等于 base，`git diff --name-only base HEAD` 成功、差异非空，且全部匹配 planner_paths（缺省为 `.agent/plans/**`、`.agent/reviews/**`、`.agent/design/**`、`.agent/*.md`；Windows 上忽略大小写） | `NOTE  base_sha 不是当前 HEAD（<HEAD 前 12 位>），但差异只在规划路径（<前 5 个，用、连接，超出时加 …>）：按「先提交合同再派遣」的流程属正常` | scripts/pi_dispatch.py:1743-1749、scripts/pi_dispatch.py:1000-1008 |
| WARN | HEAD 不等于 base 的其他情况，包括差异为空（例如空提交，已实测） | `base_sha 不是当前 HEAD（<HEAD 前 12 位>）；确认这是有意选择的输入版本` | scripts/pi_dispatch.py:1750 |
| WARN | Repository facts 中用反引号写出的文件，在根目录和各 cwd 下都不存在（规则见下） | `Repository facts 提到的文件在基线 <base 前 12 位> 中不存在：<最多 8 个，用、连接>——若它由同批的另一份合同产出，等那份集成后再以新 HEAD 为基线` | scripts/pi_dispatch.py:1699-1734 |
| WARN | `.agent/runs/probe` 没有被 gitignore | `.agent/runs/ 尚未被 .gitignore 忽略；prepare 会拒绝运行` | scripts/pi_dispatch.py:1688-1689 |
| WARN（仅 derive-json） | 解析问题 | `WARN  <问题>` | scripts/pi_dispatch.py:3019-3020 |
| NOTE（仅 derive-json） | 没有 `--title`，且截断后的标题超过 60 字。显示的字数最大为 120（实测 130 字的 Goal 显示 120） | `NOTE  标题取自 Goal 第一行（N 字），会成为分支提交的主题行…` | scripts/pi_dispatch.py:3021-3024、scripts/pi_dispatch.py:1310 |

Repository facts 检查的规则（`missing_fact_path_warnings`，scripts/pi_dispatch.py:1696-1734）：

- **何时运行**：只在原始 base_sha 是合法格式、并且在仓库中存在时才运行。
- **候选路径**：
  - 取 Repository facts 节中被反引号整体括起、匹配 FACT_PATH_RE 的内容。FACT_PATH_RE 的要求：首字符为 `[A-Za-z0-9_]`；至少含一个 `/`；以 `.` 加 1–8 位字母或数字的扩展名结尾。
  - 以下候选被跳过：重复的；与**原始** JSON 的 `scope.allowed_new_files` 中某一项字面相等的。
  - 源码还会跳过含 `* ? { }` 的路径，但 FACT_PATH_RE 的字符集本来就不含这些字符，这个分支实际不会触发（实测 `` `src/**/*.py` `` 不被当作候选，扩展名超过 8 位的也不算）。
- **查找位置**：先在仓库根目录查，再依次以原始 checks 与 setup 中每个非根 cwd（去掉首尾的 `/`）为前缀，执行 `git cat-file -e <base>:<path>`。
- **输出**：缺失超过 8 个时只列前 8 个，没有省略标记（已实测）。
- **缺陷**：原始 `scope.allowed_new_files` 含不可哈希的元素（例如 `[{}]`）或是非可迭代值（例如 `5`），或 checks、setup 是非可迭代值（例如 `5`）时，会抛 `TypeError`，不被捕获，CLI 输出 traceback、退出码 1（均已实测）。即使 validate_contract 已经报出对应错误也一样（scripts/pi_dispatch.py:1708、scripts/pi_dispatch.py:1718）。

### 3.7 validate_plan 的整体顺序（scripts/pi_dispatch.py:1656-1690；LB-CONTRACT-019、020）

| # | 步骤 | 失败时的表现 | 位置 |
|---|---|---|---|
| 1 | 检查计划标识（经 CLI 不可达，`plan_key_from_arg` 已先检查） | ERROR `计划标识不合法：<key>（格式 task-id.vN，例如 normalize-query.v1）`，返回 | scripts/pi_dispatch.py:1657-1658 |
| 2 | 分别检查 .md 与 .json：是否存在（exists 会跟随链接，悬空链接算缺失）、是否为符号链接 | ERROR `缺少文件：<相对路径>` 或 `合同不能是符号链接：<相对路径>`（本机实测）。两个文件都检查完，有错误就返回，警告为空 | scripts/pi_dispatch.py:1659-1667 |
| 3 | 以 UTF-8 的文本模式读取 Markdown | 解码错误**不捕获**：非 UTF-8 时输出 traceback，退出码 1（已实测）。CRLF 被规范成 LF，CRLF 合同能通过（已实测） | scripts/pi_dispatch.py:1668 |
| 4 | 读取并解析 JSON（读取与解析在同一个 try 中） | 捕获 `ValueError`，报 ERROR `JSON 合同解析失败：<异常>` 并立即返回，不产生不可见字符警告。已实测的情形：语法错误；BOM（`Unexpected UTF-8 BOM`）；非 UTF-8（`UnicodeDecodeError` 属于 ValueError，退出码 2）。深度嵌套时抛 `RecursionError`，**不捕获**，退出码 1（已实测）。重复键以后出现的为准，NaN 与 Infinity 被接受（已实测） | scripts/pi_dispatch.py:1669-1672 |
| 5 | 先求值 `extra_protected_paths(repo.config())`，再调用 validate_contract | 配置不能解析、顶层不是对象，或 extra_protected_paths 不合法时抛 DispatchError(2)，validate 整体中止（已实测）。其余见第 3、4 节 | scripts/pi_dispatch.py:1673、scripts/pi_dispatch.py:969-979、scripts/pi_dispatch.py:990-995 |
| 6 | 不可见字符警告：Markdown 一组，JSON 文件再读一次后一组 | WARN | scripts/pi_dispatch.py:1674-1675 |
| 7 | 仅当原始 raw 是 dict、base_sha 是 str 且匹配 SHA_RE 时，在仓库中核验 base_sha | `resolve_commit` 的结果不等于 base 时：ERROR `base_sha 在本仓库中不存在或不是提交：<sha>`，contract 置为 None，本组其余检查跳过（实测退出码 2）。否则依次给出三类提示：AGENTS.md；HEAD（`git rev-parse HEAD` 以 check=True 运行，失败时抛 DispatchError(3)；planner_paths 只在 HEAD 不等于 base 时读取，这时配置不合法会抛 DispatchError(2)，实测 HEAD 等于 base 时不报错）；Repository facts | scripts/pi_dispatch.py:1676-1687、scripts/pi_dispatch.py:768-770、scripts/pi_dispatch.py:1737-1750 |
| 8 | 检查 gitignore | WARN | scripts/pi_dispatch.py:1688-1689 |

第 5 步已经报错时，第 6–8 步照样执行。顶层为数组的 JSON 会报 `机器合同顶层必须是 JSON 对象`，并跳过第 7 步（已实测）。

### 3.8 退出码（LB-CONTRACT-023、026）

| 入口与情形 | 退出码 | 输出 | 位置 |
|---|---|---|---|
| validate：没有 error（可以有 WARN 或 NOTE） | 0 | stdout：先打印警告，再打印 `合同有效：<key>（<m> 个警告）。`；NOTE 也计入警告数 | scripts/pi_dispatch.py:3007-3008 |
| validate：有任一 error | 2 | stdout：警告（`NOTE  …` 或 `WARN  …`，两个空格）→ `ERROR <文本>`（一个空格）→ `合同无效：<n> 个错误，<m> 个警告。` | scripts/pi_dispatch.py:3003-3006、scripts/pi_dispatch.py:2988-2996 |
| 不在 Git 仓库中，或在 worktree 中运行 | 2 | stderr：`ERROR: 当前目录不在 Git 仓库中：…`，或 `ERROR: 请在主工作区运行本工具，而不是在 worktree 中：…` | scripts/pi_dispatch.py:958-963、scripts/pi_dispatch.py:4966-4968 |
| 计划标识不合法，或合同路径不在 .agent/plans 下 | 2 | stderr：`ERROR: 计划标识不合法：…`，或 `ERROR: 合同文件必须位于 .agent/plans 下：…`（已实测） | scripts/pi_dispatch.py:1022-1028 |
| argparse 用法错误：缺少 plan_key、未知子命令或选项 | 2 | stderr 打印 usage 与 error（已实测） | scripts/pi_dispatch.py:4960、scripts/pi_dispatch.py:4854-4863 |
| `--version`、`-h` | 0 | `pi_dispatch 2.2.2`（已实测） | scripts/pi_dispatch.py:4835 |
| 没有子命令 | 2 | stdout 打印帮助（已实测） | scripts/pi_dispatch.py:4961-4963 |
| dispatch.config.json 不能解析（包括非 UTF-8）或顶层不是对象 | 2 | stderr：`ERROR: <配置文件绝对路径> 顶层必须是对象`，或 `ERROR: 无法解析 …`（已实测） | scripts/pi_dispatch.py:973-978 |
| extra_protected_paths 不合法（每次 validate 都会读） | 2 | stderr `ERROR: dispatch.config.json 的 extra_protected_paths 必须是仓库相对路径模式的数组`（已实测） | scripts/pi_dispatch.py:993-994 |
| planner_paths 不合法（仅在 base 合法、存在且 HEAD 不等于 base 时） | 2 | stderr `ERROR: dispatch.config.json 的 planner_paths 必须是仓库相对路径模式的数组`（已实测） | scripts/pi_dispatch.py:1006-1007、scripts/pi_dispatch.py:1746 |
| 配置中的其他键不合法（例如 allowed_executors、commit_trailers） | 不影响，0 | validate 不读取它们（已实测） | scripts/pi_dispatch.py:1673 |
| 找不到 git | 3 | stderr `ERROR: 未找到 git，请先安装 Git。`（已实测：PATH 中去掉 git） | scripts/pi_dispatch.py:756-757、scripts/pi_dispatch.py:304-309 |
| `git rev-parse HEAD` 失败 | 3 | DispatchError 的缺省 code 是 EXIT_BLOCKED（未实测） | scripts/pi_dispatch.py:758-760、scripts/pi_dispatch.py:1684 |
| 未捕获的异常：Markdown 非 UTF-8；JSON 深度嵌套（RecursionError）；输出模式正则 OverflowError；facts 检查中的 TypeError | 1 | Python traceback（四种都已通过 CLI 实测） | scripts/pi_dispatch.py:1668、scripts/pi_dispatch.py:1670、scripts/pi_dispatch.py:1180、scripts/pi_dispatch.py:1708、scripts/pi_dispatch.py:1718 |
| KeyboardInterrupt | 130 | stderr `已取消。` | scripts/pi_dispatch.py:4969-4971 |
| derive-json：Markdown 不存在 | 2 | stderr `ERROR: 缺少文件：…`（已实测） | scripts/pi_dispatch.py:3016-3017 |
| derive-json `--print` | 没有问题时 0，有问题时 2 | 打印 JSON，不写文件，不校验；在“已存在”检查之前返回，JSON 已存在时也能用（已实测） | scripts/pi_dispatch.py:3026-3028 |
| derive-json：JSON 已存在且没有 `--force` | 2 | stderr `ERROR: <路径> 已存在；确认要覆盖时加 --force`（已实测） | scripts/pi_dispatch.py:3029-3030 |
| derive-json：写入后校验有 error | 2 | 有解析问题时也会写入（已实测） | scripts/pi_dispatch.py:3031-3037 |
| derive-json：写入后校验通过 | 有解析问题时 2，否则 0 | `合同有效：…`（已实测：有问题时 2） | scripts/pi_dispatch.py:3038-3039 |
| derive-json：Identity 的 plan_version 为上标数字等 Unicode 数字 | 1 | `str.isdigit()` 为真，但 `int()` 抛 ValueError，输出 traceback（已实测） | scripts/pi_dispatch.py:1369 |

validate 从不主动返回 1（EXIT_FAIL）或 4（EXIT_DRIFT）。退出码 1 只来自未捕获的异常。

### 3.9 derive-json 的生成规则（scripts/pi_dispatch.py:1221-1406、scripts/pi_dispatch.py:3011-3039；LB-CONTRACT-024–026）

| 项目 | 规则 | 位置 |
|---|---|---|
| task_id | 第一行（`md.splitlines()[0]`）必须匹配 `^#\s*TASK:\s*([a-z0-9][a-z0-9-]*)\s*$`：不允许反引号，但允许 `#` 后没有空白（validate 反而不允许）。不匹配时记问题 ``第一行必须是 `# TASK: <task-id>` ``，task_id 为 null | scripts/pi_dispatch.py:1334-1337 |
| executor | 必须匹配 `^([^/\s]+)/(\S+)\s*·\s*thinking\s+(\S+)`，否则记问题，provider 与 model 为 null，thinking 为 high。模板中的 `【待填：provider/model】` 会被解析成 provider=`【待填：provider`、model=`model】`（已实测），只能靠占位符检查拦下。tools 与 context_files 固定为缺省值，Markdown 无法表达 | scripts/pi_dispatch.py:1338-1341、scripts/pi_dispatch.py:1378-1383 |
| title | 取 `--title`；没有时取 Goal 节第一条非空行，并去掉首尾的 `-`、`*` 与空格。两种来源都截断到 120 字（已实测）。都没有时记问题 `没有标题：请用 --title 指定，或在 Goal 第一行写一句话概括` | scripts/pi_dispatch.py:1342-1345、scripts/pi_dispatch.py:1370 |
| checks 与 setup 的行格式 | 对行做 strip 后匹配：``- <ID>（kind）或 (kind)：`cmd` <rest>``。ID 必须是一个大写字母加两位以上数字，比 ITEM_ID_RE 严格。不匹配的行静默忽略（实测 `X1:` 被忽略）。cmd 中不能含反引号 | scripts/pi_dispatch.py:1257-1270 |
| argv | cmd 以 `python -c "` 开头并以 `"` 结尾时，argv 为 `[python, -c, 中间原文]`。否则用 `shlex.split(posix=True)`：抛 ValueError 时记问题 `<id> 的命令无法拆分：<异常>`（实测 `No closing quotation`）；任一 token 不在原行中时记问题 `<id> 的命令含引号或转义，无法可靠地还原参数；请手写 JSON 中的 argv`。两种情况都**丢弃该项**。`echo 'a  b'` 的 token 仍在原行中，所以能通过（已实测） | scripts/pi_dispatch.py:1271-1283 |
| 其他命令字段 | cwd：取 rest 中“cwd”+冒号后的值；仓库根、`.`、repo root 记为 `.`。timeout：`超时：Ns` 或 `timeout: N`，缺省 600；写 `超时：90秒` 时静默取 600（已实测）。required（仅 Validation commands）：kind 含“可选”或 optional 时为 false。expected_exit_code：`期望退出码：N`，缺省 0。output_must_match：“输出须匹配”到“，不得”之间的反引号内容。output_must_not_match：“不得出现”或“不得匹配”之后的反引号内容。expect_on_base（仅 Validation commands）：kind 加 rest 中含“基线应失败”时为 fail，否则含“基线应通过”时为 pass | scripts/pi_dispatch.py:1284-1305 |
| DoD | 只识别 Definition of done 节中形如 `- D<两位以上数字>：…` 的行（可缩进）。在第一个“证据”处分割：前半去掉末尾的 `；;，, ` 作为 text；后半中独立出现的 `[A-Z]\d{2,}`、scope、review 按出现顺序去重，作为 evidence。行中没有“证据”时 evidence 为 `[]`，review 写进了 text（已实测） | scripts/pi_dispatch.py:1349-1359 |
| scope | 只识别 Scope 节中不缩进、形如 `- key: value` 的行，只认半角冒号。dependency_changes 的值用 `_md_value` 处理。其他键：值不以“无”开头、且整个值（不区分大小写）不等于 none 或 `[]` 时，按 `,`、`，`、`、` 分割并去掉反引号，列表项的括号说明**不去掉**（实测 `tests/a.py（新建）`）；否则收集紧随其后的“缩进 - item”行，遇到第一条不匹配的行即停止，空行也会停止（实测空一行后得到 `[]`）。`none（无）` 会被当作一个路径（已实测）。缺失的键取 `[]`，dependency_changes 取 `forbidden` | scripts/pi_dispatch.py:1231-1254、scripts/pi_dispatch.py:1384-1390 |
| budget | 三个键各自缺失时记问题 `Budget 缺少 <key>`，JSON 中省略该键。validate 时 normalize 补上缺省值，再与 Markdown 中的缺失值比较，报不一致（已实测）。cost_budget 固定为 null，不读取 Markdown 中的 cost_budget 行 | scripts/pi_dispatch.py:1361-1364、scripts/pi_dispatch.py:1394-1396 |
| 其他字段 | schema_version=1。plan_version：`isdigit()` 为真时取 `int()`，否则为 null（例如 `v1`），不与文件名核对；Unicode 数字会导致崩溃（见第 8 节）。repository、base_sha、risk_level 原样取 Identity 的值。authorization 用 `_md_action_list` 解析：保留书写顺序、去重、去掉 none；Identity 缺少该键时写入 `[]`，不用 normalize 的缺省值（已实测） | scripts/pi_dispatch.py:1365-1377、scripts/pi_dispatch.py:1400-1406 |
| 写文件 | `json.dumps(indent=2, ensure_ascii=False)` 加换行，用 `Path.write_text` 以文本模式写入：Windows 上是 CRLF 换行，无 BOM（已实测）。有解析问题时照样写入；`--force` 直接覆盖，不备份 | scripts/pi_dispatch.py:3025、scripts/pi_dispatch.py:3031 |

用 contract-template.md 做实测：

- 只报 `第一行必须是…` 一条问题。
- integration 被解析成 local_branch、commit、open_pr。
- 写入后 validate 报 10 条错误，其中包括两条占位符错误，退出码 2。

### 3.10 计划标识解析与其他调用方（LB-CONTRACT-027、028）

| 行为 | 规则 | 位置 |
|---|---|---|
| `plan_key_from_arg` | 参数 strip 后若匹配 PLAN_KEY_RE，直接使用。否则按路径处理：文件名去掉 `.md` 或 `.json` 后要匹配 PLAN_KEY_RE，并且解析后的父目录（相对路径按**进程当前目录**解析，不按 `--repo`；用 normcase 比较）必须等于 `.agent/plans`。文件不必存在 | scripts/pi_dispatch.py:1011-1028 |
| `plan_key_from_arg` 的报错（退出码 2） | 父目录不符：`合同文件必须位于 .agent/plans 下：<原文>`。其余情况：`计划标识不合法：<原文>（格式 task-id.vN，例如 normalize-query.v1；也可以写成 .agent/plans/<task-id>.vN.md）` | scripts/pi_dispatch.py:1026-1028 |
| prepare | 调用 validate_plan；contract 不为 None 时追加范围重叠警告，然后打印。有 error 或 contract 为 None 时抛 `合同校验失败，未创建 attempt。`（2）。`.agent/runs` 没有被忽略时报 `请先把 .agent/runs/ 加入 .gitignore：运行证据含源码与日志，不应进入提交。`（3），validate 对此只给 WARN。原始 executor 中 provider 与 model 都有值时，才预先调用 resolve_executor | scripts/pi_dispatch.py:3162-3180 |
| baseline | 调用 validate_plan 并打印；失败时抛 `合同校验失败，无法运行基线检查。`（2） | scripts/pi_dispatch.py:4079-4084 |
| attempt 中的合同 | prepare 复制原始的 .md 与 .json 文件；之后的命令通过 load_attempt 再 normalize | scripts/pi_dispatch.py:3195-3196、scripts/pi_dispatch.py:2653-2656 |

### 3.11 相关测试（`tests/test_dispatch.py`，没有运行）

| 测试函数与 check | 覆盖的行为 | 位置 |
|---|---|---|
| `test_happy` “validate ok” | 合法合同返回 0 | tests/test_dispatch.py:243-244 |
| `test_validate` “invalid thinking rejected” | thinking 词表 | tests/test_dispatch.py:532 |
| `test_validate` “protected path in scope rejected”、“codex config dir is protected” | 受保护路径 | tests/test_dispatch.py:533-534 |
| `test_validate` “parent traversal rejected” | pattern_error 拒绝 `..` | tests/test_dispatch.py:535 |
| `test_validate` “wrong executor type reported, no crash” | 节类型错误后提前返回 | tests/test_dispatch.py:536 |
| `test_validate` “non-string authorization items, no crash (Codex #11)” | authorization 类型 | tests/test_dispatch.py:537-538 |
| `test_validate` “non-string evidence items, no crash” | evidence 类型 | tests/test_dispatch.py:539-540 |
| `test_validate` “contract without required checks rejected (Codex #13)” | 至少一个必要检查 | tests/test_dispatch.py:541-542 |
| `test_validate` “missing md section rejected” | 必需章节（把标题改成 `## Budgets`） | tests/test_dispatch.py:543-544 |
| `test_validate` “placeholder rejected” | 仅 Markdown 占位符 | tests/test_dispatch.py:545 |
| `test_validate` 中 argv、budget、integration、forbidden path、thinking 五个 “change detected” | Markdown 与 JSON 的一致性（只改 JSON） | tests/test_dispatch.py:546-559 |
| `test_validate` “prepare refuses when .agent/runs not ignored” | prepare 对 gitignore 的硬性要求 | tests/test_dispatch.py:560-562 |
| `test_validate` “example normalize-query.v1 validates”、“example auth-refresh-401.v1 validates” | 技能示例校验通过且 0 个警告 | tests/test_dispatch.py:563-581 |
| `test_units` “glob uses fullmatch (no trailing newline match)” | glob 不接受末尾换行（ID 正则没有对应测试） | tests/test_dispatch.py:599-601 |
| `test_units` “control chars / decode errors are invalid_path violations” | 只把 normalize_contract 的结果当作 evaluate_scope 的输入，不断言缺省值 | tests/test_dispatch.py:602-608 |
| `test_repo_config_features` “repo-level protected path rejected in scope” | extra_protected_paths | tests/test_dispatch.py:629-634 |
| `test_repo_config_features` “invalid commit_trailers config is ignored by validate” | validate 不读取其他配置键 | tests/test_dispatch.py:649-651 |
| `test_setup_wrapper_doctor` “bash wrapper finds python” | 经包装脚本调用 validate | tests/test_dispatch.py:713-714 |
| `test_feedback_v11` 中路径形式计划标识的四项 | plan_key_from_arg | tests/test_dispatch.py:818-825 |
| `test_feedback_v11` “invisible format character is warned” | Markdown 中 U+200E 的警告 | tests/test_dispatch.py:826-829 |
| `test_feedback_v11` “invalid expect_on_base rejected” | expect_on_base | tests/test_dispatch.py:891-893 |
| `test_feedback_v11` 中 derive-json 的五项 | 生成、拒绝覆盖、`--print` | tests/test_dispatch.py:895-915 |
| `test_feedback_v12` 中长标题 NOTE 两项、“annotated single values are derived without the note” | 标题 NOTE 与 `_md_value` | tests/test_dispatch.py:1115-1125、tests/test_dispatch.py:1208-1217 |
| `test_v22_netperf_feedback` 中 NOTE 与 WARN 两项、facts 三项 | 基线提示与 facts 警告 | tests/test_dispatch.py:1784-1800、tests/test_dispatch.py:1869-1895 |

以下行为**没有测试断言**（按 check 名称和报错文本在测试文件中检索确认）：

- schema_version、task_id、plan_version、base_sha、risk_level 五项取值；
- local_edit 必选；context_files；
- scope 中的“至少允许”与“允许和禁止重叠”；dependency_changes 的取值；
- 命令项中除 expect_on_base 以外的全部检查；
- DoD 的 id、text 与未定义证据；
- budget 的取值范围与 cost_budget；
- JSON 占位符；
- 缺少文件、JSON 解析失败、符号链接、顶层不是对象、“合同结构无效”；
- 基线中缺少 AGENTS.md 的警告；
- derive-json 的解析问题（无法拆分、含引号、Budget 缺少）；
- normalize_contract 的缺省值；
- 全部未捕获异常。

### 3.12 实测边界行为汇总

以下每条都已在内存探针或 scratchpad 临时仓库中复现：

| 行为 | 位置 |
|---|---|
| `schema_version` 写成 true 或 1.0、`plan_version` 写成 1.0 或 true 都能通过（比较用 `!=`）；字符串 "1" 被拒 | scripts/pi_dispatch.py:1459-1464 |
| `expected_exit_code: true` 能通过 | scripts/pi_dispatch.py:1167 |
| 显式 `"thinking": null` 不补缺省值，报取值错误 | scripts/pi_dispatch.py:1200-1204、scripts/pi_dispatch.py:1488-1490 |
| provider 与 model 都缺失时 validate 返回 0；provider 为空串时报错 | scripts/pi_dispatch.py:1484-1487 |
| 受保护检查只看模式字面值：`*.md`、`**/*.md` 不被拒；`agents.md`、`docs/CLAUDE.md`、`.Agent/x`、`scripts/PI_DISPATCH.py`、`.agent/*` 被拒；`.github/workflows/ci.yml` 不被拒（SENSITIVE_PATTERNS 只在 evaluate_scope 中使用，scripts/pi_dispatch.py:2446） | scripts/pi_dispatch.py:1516 |
| 通配允许模式与禁止路径重叠（`src/*.txt` 对 `src/a.txt`），或只差大小写（`src/normalize.py` 对 `SRC/normalize.py`），都不报错；精确路径被 `src/*.py` 禁止时报错 | scripts/pi_dispatch.py:1521-1524 |
| JSON 路径只要以子串形式出现在 Markdown 任意位置就算已列出（例如只写在 Goal 中；或 `package.json.bak` 满足 `package.json`） | scripts/pi_dispatch.py:1612-1614 |
| 标题不在第一行、带反引号、task 后接大写字母或下划线，都能通过 validate；`#TASK:` 和 BOM 开头时报错 | scripts/pi_dispatch.py:1591-1593 |
| Identity 用全角冒号写的键视为缺失；`- integration_actions:` 冒号后没有任何字符时视为缺失，冒号后有空白时为空集 | scripts/pi_dispatch.py:1138、scripts/pi_dispatch.py:1599-1605 |
| JSON 中 base_sha 带末尾换行：通过 SHA_RE，但报 Identity 不一致与“不存在”两条错误 | scripts/pi_dispatch.py:57、scripts/pi_dispatch.py:1595-1598、scripts/pi_dispatch.py:1678-1680 |
| JSON 中重复的键以后出现的为准；`Infinity` 作为 cost 金额能通过，`NaN` 被拒 | scripts/pi_dispatch.py:1670、scripts/pi_dispatch.py:1576-1580 |
| 非 UTF-8 的 JSON 返回 2（解析失败），非 UTF-8 的 Markdown 返回 1（traceback） | scripts/pi_dispatch.py:1668-1672 |
| 深度嵌套的 JSON 抛 RecursionError，退出码 1 | scripts/pi_dispatch.py:1670 |
| `allowed_new_files: [{}]` 或 `5`、`checks: 5` 导致 facts 检查抛 TypeError，退出码 1 | scripts/pi_dispatch.py:1708、scripts/pi_dispatch.py:1718 |
| 输出模式 `a{4294967296}` 抛 OverflowError，不被捕获，退出码 1 | scripts/pi_dispatch.py:1180、scripts/pi_dispatch.py:1436 |
| derive-json 在 Windows 上写出 CRLF 的 JSON；plan_version 写成 `²` 时崩溃，退出码 1 | scripts/pi_dispatch.py:3031、scripts/pi_dispatch.py:1369 |

### 未解决事项（第 3 节）

- 需要设计决定（本清单只记录事实，不做裁定）：下列宽松行为，v2 是作为旧行为保留，还是作为缺陷修复？(1) ID 正则的 `$` 接受末尾换行，而 glob 已改用 fullmatch；(2) schema_version、plan_version 接受 true 或 1.0，expected_exit_code 接受 bool；(3) 受保护检查只看模式的字面值；(4) 路径只做全文子串匹配，且只比较 JSON 到 Markdown 一个方向；(5) 允许与禁止的重叠检查区分大小写，忽略含 * 的模式，含 ? 的模式按字面比较；(6) 标题的捕获在第一个不属于 [a-z0-9-] 的字符处停止；(7) JSON 接受重复键、NaN 与 Infinity；(8) Identity 与 dependency_changes 只认半角冒号。
- 有 5 条路径导致 traceback、退出码 1（都已通过 CLI 实测）：Markdown 不是 UTF-8（scripts/pi_dispatch.py:1668）；JSON 深度嵌套时抛 RecursionError（:1670）；输出模式正则抛 OverflowError（:1180）；missing_fact_path_warnings 中的 TypeError（:1708、:1718）；derive-json 中 plan_version 为 Unicode 数字时抛 ValueError（:1369）。这些算应复现的旧行为还是缺陷，需要规划端判断。
- Markdown 与 JSON 冲突时，源码不设优先级，一律报 error 拒绝。设计文档 3.3 要求核实「冲突时的优先级」，本清单的结论是「无优先级，拒绝」，需要规划端确认 v2 是否沿用。另有一批字段不在比较范围内（checks 的 cwd、timeout、输出模式，DoD 的 text 与 evidence 等），只按 JSON 执行。
- provider、model 缺失时 validate 能通过。源码显示，run 阶段的 resolve_executor 从 PI_EXEC_PROVIDER / PI_EXEC_MODEL / PI_EXEC_THINKING 补值（scripts/pi_dispatch.py:2670-2685，调用点 :3271）；原始 JSON 没写 thinking 时，已与 Markdown 核对为 high 的值也可能在运行时被环境变量替换。这部分没有实测，属于执行器解析与预检区域。
- 运行时的范围判定 evaluate_scope（受保护、依赖、敏感路径，以及增删改状态的对应）属于候选与门禁区域。本节只记录合同校验阶段的范围检查。
- 本次没有运行 tests/test_dispatch.py 全量。表中的测试名只是源码中的 check 名称，没有本次的执行结果。设计文档 3.1 要求的「被测提交 + 结果」需要规划端在受控取证中补齐。
- 所有「实测」都只在 Windows Server 2025 + Python 3.12.10 上做过，使用的是 scratchpad 中的临时探针脚本，没有归档成 fixture，不满足设计文档 3.2 要求的 input_fixture_ref。至少以下三项在 Linux 或 macOS 上可能不同，尚未验证：derive-json 写出的 CRLF、plan_key_from_arg 的 normcase、planner_paths 在 IS_WINDOWS 时忽略大小写。符号链接分支在本机能创建链接的账户下实测通过，无权限账户下的表现未验证。
- 许多拒绝分支没有测试断言（见最终小节第 11 节末尾）。迁移时需要新建 fixture，才能形成可比较的旧观测。
- `git rev-parse HEAD` 失败时的退出码 3 只来自源码推断（scripts/pi_dispatch.py:758-760、:1684），没有实测。在 worktree 中运行 validate 时的退出码 2（:962-963）也没有实测。

## 4. Pi 预检、事件摘要与用量证据

> **纳入说明**：本节是区域章节原稿（已经对抗核对），正文照录，只统一了标题层级并修正排版。
> - 原稿编写时尚未取得 `bl-01t1-legacy-20260925` 的运行结果，文中“没有运行”“未运行”“NOT_RUN”“结果未知”等说法描述的是原稿编写时的状态；本次运行结果见本文第 0.3、2、9、10 节。
> - 正文中的“第 k 节”“见第 k 节”指本区域内的 4.k 小节，不是本文的第 k 节。
> - 标“实测”“探针”的内容是起草或核对者在会话临时目录中的一次性复现，没有归档为 fixture，证据等级仍按 source_inspected 记。

取证对象：
- `scripts/pi_dispatch.py`（HEAD `a4fa199b0e5bdc658215765ee7558b9fe6723940`，TOOL_VERSION 2.2.2）；
- `tests/stub_pi.py`、`tests/stub_pi_help.txt`；
- `tests/test_dispatch.py`。

对应设计文档的 3.1 第二行（`pi_preflight`、`summarize_events`）、3.3“缺失模型、思考级别、token、费用的旧输出”和 4.3.4。文档引文（4.3.4 的对照表、4.3.7 的“0 表示确有证据的零；null 表示未知”）只作为对照，不当作源码事实。

证据等级：下表都来自源码阅读（source_inspected）。另外做了探针核对，方式如下：
- 在规划端 scratchpad 临时目录里，设置 `PYTHONDONTWRITEBYTECODE=1`；
- 用合成事件流直接调用 `summarize_events`；
- 让 `pi_preflight` 指向 `tests/stub_pi.py`，以及一个不存在的程序。

探针没有调用真实 pi，也没有修改仓库。标有“探针”的行已被探针复现，但探针输出不是正式取证记录，要在 P1 取证中用固定的 fixture、被测提交和命令重新记录。

### 4.1 定位 pi、版本与参数安全

| ID | 旧行为 | 位置 |
|---|---|---|
| LB-EVENTS-001 | **版本常量**：`MIN_PI_VERSION=(0,80,4)`。源码注释说 agent_settled 自 0.80.4 起提供，这只是注释说法。<br>**版本解析**：`parse_version` 取文本中第一个“数字.数字.数字”。“0.87”这类两段版本解析不出（探针）。<br>**`_expects_settled`**：版本解析不出时为 None；≥0.80.4 时为 True；其余为 False（探针）。<br>**run**：用预检返回的 `pi_version`（已脱敏的 --version 文本）计算，写入 run-started.json 和 run.json 的 `expects_agent_settled`。<br>**recover**：run.json 缺失时，先读 run-started.json 中的这个字段；没有该字段时，再从 `preflight/pi-version.txt` 计算。<br>**smoke**：只读 `--version` 的 stdout。<br>**版本偏低**：预检只记 note，不阻止运行；doctor 记 note“pi 版本低于 %s，建议升级”。 | scripts/pi_dispatch.py:50、373-375、2044-2046、3245-3247、3288、3316-3318、3427-3433、4689-4690、4774-4775 |
| LB-EVENTS-002 | **设置了 `PI_DISPATCH_PI_CMD`（非空）**：先按 JSON 解析，解析失败才当作单个路径。结果必须是非空的非空字符串数组；JSON 合法但不是数组时（例如带引号的字符串、数字）也会拒绝，不回退为路径。拒绝时的退出码为 2，报“PI_DISPATCH_PI_CMD 必须是 JSON 字符串数组或单个可执行文件路径”。<br>**未设置**：用 `which pi` 查找。找不到时退出码为 3，报“PATH 中找不到 pi；请安装 @earendil-works/pi-coding-agent 或设置 PI_DISPATCH_PI_CMD”。<br>**Windows 下找到的是 .cmd/.bat**：按 UTF-8（errors=replace）读取 shim，不区分大小写地匹配带引号的 `%dp0%\…(.js/.cjs/.mjs)`。入口文件存在、且找到 node（优先同目录的 node.exe）时，返回 `[node, 入口]`；否则返回 `[exe]`。<br>**调用方的处理**：doctor 把这个错误记为 problem；smoke 和 run 直接抛出。 | scripts/pi_dispatch.py:1760-1786、3277、4681-4683、4727-4728、4767 |
| LB-EVENTS-003 | **检查条件**：只在 Windows 上、且 argv[0] 以 .cmd/.bat 结尾时检查。<br>**拒绝规则**：后续参数中只要含 &、竖线、<、>、^、%、!、双引号、CR 或 LF 之一，就以退出码 2 报“参数 %r 含批处理特殊字符，不能安全传给 %s；请改用 PI_DISPATCH_PI_CMD 指向 node 与入口脚本”。<br>**调用位置**：<br>- run：在预检和上下文取证之后、领取之前调用，失败时 attempt 仍是未领取的 PREPARED；<br>- smoke：每一步都调用；<br>- check/setup 命令项（`_run_command_item`）：命中时记为 `status=blocked`，不抛出。<br>预检自己运行的 --help、--version、--list-models、auth 命令都不经过这项检查。 | scripts/pi_dispatch.py:1757-1795、3079-3084、3296、4791 |

### 4.2 预检 `pi_preflight`：步骤、产物与失败结果（LB-EVENTS-005/006/007）

- 各步依次执行，前一步失败不会跳过后面的步骤。最后 `ok = not problems`。
- 产物位于 `<run_dir>/preflight/`，每次覆盖写，再次 run 后只剩最后一次的结果。
- `run_capture` 的 stdin 为 DEVNULL。找不到程序时返回 127 和异常文本；超时返回 124 和“timeout after Ns”；其他 OSError 返回 126。

| 步 | 命令或检查 | 产物 | 失败时的 problems / notes 原文 | 位置 |
|---|---|---|---|---|
| 1 | `pi + RESOURCE_FLAGS + --help`（90s） | pi-help.txt：stdout 与 stderr 合并，去 ANSI 并脱敏 | 退出码非 0：“pi --help 退出码 %s：%s”。摘要优先取 stderr，先脱敏再截前 300 字符 | scripts/pi_dispatch.py:2020-2024 |
| 2 | 必需参数：`--provider --model --thinking --mode --no-session --tools --no-approve --no-extensions --no-skills --no-prompt-templates --no-themes`。`context_files=none` 时再加 `--no-context-files`。参数从**原始** help 输出中解析：取前面不是 `[\w-]` 的 `--[a-z][a-z0-9-]*` | — | “本机 pi 不支持参数：%s”（逗号分隔） | scripts/pi_dispatch.py:69-70、1860-1862、2025-2030 |
| 3 | 请求的 thinking 必须在 help 的“`--thinking <level> …: a, b, c`”一行中。匹配不到这一行时，静默退回固定列表 off/minimal/low/medium/high/xhigh/max | — | “思考级别 %s 不在本机 pi 支持列表 %s 中（Pi 对无效值只警告并忽略）”（探针：ultra） | scripts/pi_dispatch.py:68、1863-1866、2031-2033 |
| 4 | help 中有“Built-in Tool Names:”一节时，核对 executor.tools；没有这一节就跳过 | — | “本机 pi 没有这些内置工具：%s（Pi 会静默忽略未知工具名）”（探针：nosuch） | scripts/pi_dispatch.py:1867-1870、2034-2037 |
| 5 | `pi --version`（60s，不带 RESOURCE_FLAGS） | pi-version.txt：stdout 为空时取 stderr，已脱敏 | 退出码非 0 或解析不出版本：“无法读取 pi 版本：%s”（截前 200）。版本偏低时只记 note：“pi %s 低于 %s，缺少 agent_settled 事件；将退回用 agent_end 判断结束” | scripts/pi_dispatch.py:2038-2046 |
| 6 | `pi + RESOURCE_FLAGS + --list-models <model>`（90s）。只解析 stdout 中表头前两列恰为 `provider model` 之后的行，按 (provider, model) 精确匹配，区分大小写 | list-models.txt：stdout 与 stderr 合并，去 ANSI 并脱敏 | 退出码非 0：“pi --list-models 失败：%s”（优先取 stderr，截前 300）。<br>否则 (provider, model) 不在表中：“模型 %s/%s 不在本机可用模型列表中（可能是拼写错误、缺少凭据或未在 models.json 定义；Pi 对未知模型可能只警告并按自定义 ID 发送）”。<br>预检不区分 no_models 和 no_match，两种情况给出同一条（探针） | scripts/pi_dispatch.py:1874-1886、2047-2055 |
| 7 | 重新读取**已脱敏**的 pi-help.txt。其中出现单词 `pi auth` 时，运行 `auth check --provider P --model M --json`（90s，**不带** `--no-refresh`，也不带 RESOURCE_FLAGS） | auth-check.json：stdout 非空时写 stdout，否则写 stderr；已脱敏；内容不保证是 JSON | 退出码非 0：“pi auth check 未就绪（退出码 %s）：%s”（优先取 **stdout**，截前 300）。<br>没有 auth 子命令时记 note：“本机 pi 没有 auth 子命令，跳过凭据检查” | scripts/pi_dispatch.py:2056-2064 |
| 8 | 汇总 | preflight.json = redact_obj({checked_at, pi_command, pi_version, help, problems, notes, ok})，函数返回同一对象 | — | scripts/pi_dispatch.py:2065-2068 |

探针结果：
- pi 程序不存在时：同时出现 4 条 problem，即 --help 退出码 127、缺全部参数、无法读取版本、list-models 失败，文本为“[WinError 2] The system cannot find the file specified”；另有一条跳过 auth 的 note。思考级别检查因为退回固定列表而通过。
- 用 stub 预检：ok=true，preflight/ 下有 auth-check.json、list-models.txt、pi-help.txt、pi-version.txt、preflight.json。

**预检在 run 中的结果**（LB-EVENTS-008）

| 情形 | 旧表现 | 位置 |
|---|---|---|
| run 的顺序 | 状态与领取检查 → verify_inputs 与 worktree（G0）→ resolve_executor → 预算检查 → child_env → resolve_pi_command → pi_preflight → context_evidence，并**无条件**写出 preflight/context-files.json | scripts/pi_dispatch.py:3254-3280 |
| ok=false | history.jsonl 追加 `{event: preflight_failed, at, problems}`，problems 已脱敏。<br>stdout 逐条打印“`PREFLIGHT <problem>`”。<br>退出码 3，stderr 为“ERROR: 预检失败：attempt 保持 PREPARED，未计入尝试次数。修正环境后可再次 run。”。<br>不创建 claim，不改 state.json | scripts/pi_dispatch.py:3281-3285、2547-2551、307、4966-4968 |
| ok=true | notes 和上下文警告打印为“NOTE  …”；然后计算 expects_settled，组装命令，调用 ensure_argv_safe，最后领取 | scripts/pi_dispatch.py:3286-3315 |

### 4.3 上下文文件取证 `context_evidence`（LB-EVENTS-004）

| 行为 | 位置 |
|---|---|
| agent 目录：设置了 `PI_CODING_AGENT_DIR`（非空）时用它（先展开 `~`），否则用 `~/.pi/agent` | scripts/pi_dispatch.py:1798-1800 |
| 每个目录只取第一个存在的文件，查找顺序为 AGENTS.override.md、AGENTS.md、AGENTS.MD、CLAUDE.md、CLAUDE.MD | scripts/pi_dispatch.py:1803、1808-1813 |
| project 模式：<br>- agent 目录中的文件记为 global，不告警；<br>- 从 `work_dir.resolve()` 向上逐级查找到根，按从根到 worktree 的顺序列出；<br>- 目录在 worktree 外的记为 ancestor，并告警“工作副本之外的上下文文件也会被执行器读取：%s”；<br>- 每个文件记 sha256 和字节数。<br>其他模式（none）下 context_files 为空 | scripts/pi_dispatch.py:1821-1842 |
| 任何模式下：<br>- agent 目录中存在 SYSTEM.md 或 APPEND_SYSTEM.md 时，记路径和 sha256，并告警“全局 %s 会改变执行器系统提示词：%s”；<br>- worktree 中存在的 `.pi/settings.json`、`.pi/extensions`、`.pi/skills`、`.pi/prompts`、`.pi/themes`、`.pi/SYSTEM.md`、`.pi/APPEND_SYSTEM.md`、`.agents/skills` 列为 project_resources_ignored_by_no_approve；<br>- agent 目录的 settings.json 只记排序后的键名 | scripts/pi_dispatch.py:1843-1857 |
| run：预检之后无条件写出 context-files.json；警告只在预检通过后打印成 NOTE，不影响结果。doctor：以仓库根按 project 模式调用，警告并入 notes | scripts/pi_dispatch.py:3279-3287、4751-4752 |

### 4.4 事件流解析与识别的事件类型（LB-EVENTS-009/010）

| 事件 / 情形 | 旧处理 | 位置 |
|---|---|---|
| 读入与逐行 | 读取 events.jsonl 的全部字节，文件不存在视为空。<br>按 `\n` 分行，跳过空白行。每行去掉结尾的 `\r`，再按严格 UTF-8 解码，然后 json.loads。解析失败，或结果不是对象，就把行号（从 1 起）记入 parse_errors 并继续；摘要只保留前 50 个。<br>探针：以 BOM 开头的行、数组或字符串行都记为无法解析；`\r\n` 行尾正常。<br>`type` 转成字符串后计入 event_counts，缺少 type 时计为 "None"；未知类型只计数，不产生 problem。<br>`lines` 是非空白行数 | scripts/pi_dispatch.py:2172-2213、2367-2369 |
| agent_start、turn_start、message_start、tool_execution_start | 属于 WORK_EVENTS，把 pending_work 置为 True | scripts/pi_dispatch.py:2078、2214-2215 |
| session | 只取第一条的 version、id、timestamp、cwd，作为 session_header | scripts/pi_dispatch.py:2216-2217 |
| message_end，role=assistant | 追加到 assistant 列表，作为最终消息、模型和思考级别的证据；扫描 text 和 thinking 块中的歧义提及；累加 message.usage | scripts/pi_dispatch.py:2218-2226 |
| message_end，role=toolResult | 累加 message.usage | scripts/pi_dispatch.py:2227-2228 |
| message_end，role=system，且 sections 为对象 | system_prompt_sections 记为排序后的键名，以最后一条为准 | scripts/pi_dispatch.py:2229-2230 |
| entry_appended，且 entry.type=usage | 累加 entry.usage | scripts/pi_dispatch.py:2231-2234 |
| compaction_end | compactions 加 1，累加 result.usage | scripts/pi_dispatch.py:2235-2238 |
| tool_execution_start | tool_calls[toolName] 加 1。<br>bash/powershell 的命令截前 500 字符原样记录，同时记录可疑命令和临时路径。<br>args 的 path/file_path 在 worktree 外时记入 outside_worktree_paths；落在 allowed_outside 内时记入 own_run_paths | scripts/pi_dispatch.py:2239-2287 |
| tool_execution_end | isError 为真时 tool_errors 加 1，并回填对应 outside 记录的 failed | scripts/pi_dispatch.py:2288-2293 |
| agent_end / agent_settled | 计数，并更新 last_will_retry 和 pending_work（见第 5 节） | scripts/pi_dispatch.py:2294-2301 |
| auto_retry_start；auto_retry_end 且 success 为假 | 分别追加 `{attempt, error}` 或 `{final_error}`，错误文本先脱敏再截前 300 | scripts/pi_dispatch.py:2302-2306 |
| message_update、turn_end、queue_update、agent_end.messages 等 | 只计数，不读内容，其中的 usage 不累加（探针） | scripts/pi_dispatch.py:2201-2306 |
| agent_settled 之后到来的非 WORK 事件 | 照常处理：例如一条没有 message_start 的 assistant message_end，会累加用量，并成为新的最终消息，complete 不变（探针） | scripts/pi_dispatch.py:2218-2226、2309-2311、2319 |
| `QUIET_EVENTS` | 已定义，但整个文件没有引用 | scripts/pi_dispatch.py:2076-2077 |

### 4.5 完整性判定（LB-EVENTS-011）

| 条件 | terminal_event | complete | problems 原文 | 位置 |
|---|---|---|---|---|
| 至少有一个 agent_settled | `agent_settled` | 等于 `not pending_work`：settled 之后再出现 WORK_EVENTS 就不完整（探针）。settled 之后的 agent_end（即使 willRetry=true）不改变结果（探针） | 不完整时：“没有观察到完整的结束事件（agent_settled / agent_end）” | scripts/pi_dispatch.py:2299-2311、2345-2349 |
| 没有 agent_settled，但有 agent_end | `agent_end` | 同时满足以下三条才完整：`expects_settled is False`；`not pending_work`；最后一个 agent_end 的 willRetry 为假（缺字段按假处理）。<br>在 expects_settled 为 False 时，agent_end(willRetry=true) → agent_start → … → agent_end(willRetry=false) 判为完整（探针） | expects_settled 为 True 或 None 时：“没有 agent_settled：该 pi 版本应以它结束，事件流可能被截断或运行被中断”。<br>为 False 但仍不完整时：“没有观察到完整的结束事件（agent_settled / agent_end）” | scripts/pi_dispatch.py:2294-2298、2312-2315、2346-2349 |
| 两种事件都没有 | null | false | “没有观察到完整的结束事件（agent_settled / agent_end）” | scripts/pi_dispatch.py:2316-2318 |
| 与 complete 无关的检查 | — | complete 可以同时为 true（探针） | 空流：“事件流为空”。<br>有无法解析的行：“事件流有 %d 行无法解析”。<br>数据非空且不以 `\n` 结尾：“事件流最后一行不完整（可能被截断）”；最后一行本身是合法 JSON 时也报（探针） | scripts/pi_dispatch.py:2308、2339-2344 |

expects_settled 什么时候为 None：
- run 的预检要求版本可解析，所以 run 只传 True 或 False。
- None 只在三种情况下出现：smoke 的 stdout 中解析不出版本；recover 时 run-started.json 缺这个字段且 pi-version.txt 不存在；run.json 来自不写这个字段的旧版本。
- 这些情况下，旧实现按“应以 agent_settled 结束”处理。

位置：scripts/pi_dispatch.py:3288、3357、3426-3433、4774-4775。进程退出码不参与这项判定。

与文档 4.3.4 的观察组合对照：

| 观察组合 | 旧表现 | 位置 |
|---|---|---|
| 退出码为 0，但没有结束事件 | 事件摘要出现 problem，events.ok=false，G1 失败，run 退出码为 1。只要有 assistant 消息，且没有超时、取消或收集错误，状态仍是 NEEDS_REVIEW | scripts/pi_dispatch.py:2345-2349、3348-3349、3395-3404、4175-4176 |
| 结束事件完整，但进程退出码非 0 | 事件摘要和 collect 状态都**不看**退出码：events.ok 可以为 true，状态为 NEEDS_REVIEW，run 退出码可以是 0。只有 G1 单独记“Pi 退出码为 %s”，exit_code 为 None 时也记。这一行是源码推断，未做端到端验证 | scripts/pi_dispatch.py:3348-3349、3395-3404、4173-4174 |
| 有无法解析的行 | 记录 parse_errors 并出现 problem，其余行照常统计，complete 可以仍为 true。旧实现没有 integrity=incomplete 这样的独立字段 | scripts/pi_dispatch.py:2204-2211、2341-2342 |
| 用量缺失，其他证据完整 | token 全部为 0，cost.total 为 null，status 为 unknown，**不**产生 problem，ok 可以为 true（探针） | scripts/pi_dispatch.py:2179-2180、2334-2336 |
| 取消后进程退出 | 事件摘要不知道取消，只按流内容判定。取消由 run_info.interrupted 表达：collect 状态为 CANCELLED（优先于 assistant 判断），G1 记“运行被取消或调度器中断” | scripts/pi_dispatch.py:3399-3400、4171-4172 |
| 同一事件重复投递 | token 和费用重复累加，assistant_messages 也翻倍（探针） | scripts/pi_dispatch.py:2218-2226 |
| 终止后出现新的关键内容 | settled 之后出现 WORK_EVENTS：complete=false。出现非 WORK 事件：complete 仍为 true，最终消息被替换，用量被累加，只有新最终消息自身的问题（如 stopReason）会进入 problems（探针） | scripts/pi_dispatch.py:2214-2215、2309-2311、2319 |

### 4.6 最终消息、实际模型与思考级别（LB-EVENTS-012–015）

**最终消息**
- **旧规则**：取最后一条 assistant 的 message_end，按出现顺序，不看 stopReason。`_message_text` 的取法：content 是字符串时原样返回；是列表时，把 type=text 块的 text 用换行拼接；其他情况返回空串。
- **缺失或不符时的输出**：
  - stopReason 不等于 stop：“最终 assistant stopReason=%s”（没有 assistant 时为 None）；
  - errorMessage 为真值：“最终 assistant 错误：%s”（先脱敏，再截前 300）；
  - 正文命中 `<tool_call>`、`</tool_call>`、`<function=名称>` 或 `<|tool_call`（不区分大小写）：“最终 assistant 消息的正文里有未执行的工具调用（%s）：模型把工具调用写成了文本，Pi 没有执行，回合随之结束，运行没有做完”；
  - `final_error` 字段是整段脱敏后的 errorMessage，不截断；没有时为 null。
- 位置：scripts/pi_dispatch.py:299、2096-2103、2319-2320、2353-2360、2375

**实际模型**
- **旧规则**：
  - actual 是所有 assistant 消息的 (str(provider), str(model)) 去重排序后的列表。
  - model_match 要求至少有一条 assistant，且每一对都等于 (executor.provider, executor.model)。
  - responseModel 只记录到 response_models，**不参与比较**。
- **缺失或不符时的输出**：
  - problem 原文：“实际模型 %s 与要求 %s 不一致或缺失”。第一个 %s 是元组列表的 repr，例如 `[]`（空流）或 `[('None', 'None')]`（字段缺失）（探针）；第二个 %s 是 provider/model。
  - actual_models 可能为空，也可能含字符串 "None"。
- 位置：scripts/pi_dispatch.py:2323-2328、2361-2362、2376-2378

**思考级别**
- **旧规则**：取 assistant 消息中值为真的 providerThinkingLevel，转成字符串，去重排序。
- **缺失或不符时的输出**：
  - 与要求不同：“提供商报告的思考级别 %s 与要求的 %s 不一致”。第一个 %s **只包含不一致的级别**（探针：级别为 ['high','low'] 时写 ['low']），第二个 %s 是请求级别字符串。
  - 一条都没有回报：thinking_evidence 为长文本“not_reported：该协议或配置不回报 providerThinkingLevel，只能确认请求的级别；…”。这**不算** problem，只在 G1 记 note“提供商未回报思考级别：只能确认请求的级别（%s）”。
  - 部分消息回报、部分不回报：仍为 provider_reported，不告警（探针）。
  - 其他证据：预检核对请求级别在 help 的列表中（第 2 节第 3 步）。
- 位置：scripts/pi_dispatch.py:2326-2327、2337、2350-2352、2379-2382、4177-4179

**stderr**
- **旧规则**：只在传入 stderr_path 且文件存在时检查。按 UTF-8（errors=replace）读取、去 ANSI 后，依次查找 Using custom model id、Invalid thinking level、Unknown option、Extension error。
- **缺失或不符时的输出**：
  - 前三种各记一条 problem：“stderr 出现 %s 警告”（%s 为 custom_model_id / invalid_thinking / unknown_option）。
  - extension_error 只进入 stderr_flags。
  - summary.md 的“## 复审需要关注”对 stderr_flags 中**每一个**标记都写“stderr 标记：%s”（探针复现了 4 个 flag 和 3 条 problem）。
- 位置：scripts/pi_dispatch.py:261-266、2329-2332、2363-2365、2954-2955、2972

### 4.7 用量与费用（LB-EVENTS-016–019）

**`_add_usage` 的精确语义**
- usage 不是对象就直接返回。
- input、output、cacheRead、cacheWrite、totalTokens 中凡是 int 或 float 的，一律 `+=`。bool 也算：True 计为 1。
- 每个 usage 都被当作独立的**增量**：不取最大值，不替换，不按 id 或时间戳去重，也不检查分项与 totalTokens 是否一致。
- 费用只看 `cost.total`，不读 cost 的分项：
  - cost.total 是大于 0 的 int 或 float：累加到 cost_total，用二进制浮点累加，输出时 round(…, 6)；
  - 否则，如果 `(usage.totalTokens or 0) > 0`，priced_missing 加 1。
- 0 和负数费用都按“未定价”处理。只有 input、没有 totalTokens 的无价 usage 不计入 unpriced（探针）。
- priced_missing 按 **usage 对象**计数，包括 toolResult、entry_appended、compaction_end 的 usage，不只统计 assistant 消息。
- cost.total 为 inf 或 token 为 NaN 时，events-summary.json 会写出非标准 JSON 的 `Infinity`/`NaN`（探针）。

位置：scripts/pi_dispatch.py:2075、2081-2093、2392

| 用量来源 | 是否累加 | 位置 |
|---|---|---|
| assistant 的 message_end.message.usage | 累加 | scripts/pi_dispatch.py:2226 |
| toolResult 的 message_end.message.usage | 累加 | scripts/pi_dispatch.py:2227-2228 |
| entry_appended{entry.type=usage}.entry.usage | 累加 | scripts/pi_dispatch.py:2231-2234 |
| compaction_end.result.usage | 累加；compactions 加 1 | scripts/pi_dispatch.py:2235-2238 |
| message_start、message_update（stub 在它的顶层带 usage）、turn_end.message、agent_end.messages | 不累加（探针） | scripts/pi_dispatch.py:2201-2306；tests/stub_pi.py:131 |

| 重复累加风险 | 旧结果 | 位置 |
|---|---|---|
| 同一条 assistant message_end 出现两次 | 计两次：input 从 100 变成 200，assistant_messages=2（探针） | scripts/pi_dispatch.py:2218-2226 |
| 同一次调用既有 message_end 的 usage，又有 entry_appended 的 usage | 两者都加：input 从 100 变成 200（探针） | scripts/pi_dispatch.py:2226、2234 |
| toolResult 或 compaction 的用量与 assistant 的用量是否重叠 | 未去重，直接相加 | scripts/pi_dispatch.py:2228、2238 |

下表的位置：scripts/pi_dispatch.py:2179-2180、2334-2336、2339-2362、2390-2394。

| 情形 | usage | cost.total | cost.status | unpriced_messages | problem |
|---|---|---|---|---|---|
| 至少一条 assistant，累计 cost_total>0，没有“totalTokens>0 但无正数费用”的 usage，也没有 compaction | 各项之和 | round(和, 6) | estimated | 0 | 无。不要求每条 assistant 都带费用：探针中费用只来自 entry_appended，仍为 estimated |
| 同上，但存在 totalTokens>0 而无正数费用的 usage | 各项之和 | 已知部分，是下界 | partial | 这类 usage 对象的个数 | 无（探针） |
| 出现过 compaction_end，有 assistant，且 cost_total>0 | 包含压缩用量 | 已知部分 | partial | 按上述规则 | 无（探针） |
| 出现过 compaction_end，但 cost_total 为 0 | 包含压缩用量 | **null** | unknown（**不是** partial） | 包含压缩 usage 在内（探针：2） | 无 |
| 费用全部为 0 或缺失（STUB_NOCOST） | 各项之和 | **null** | unknown | totalTokens>0 的 usage 对象数 | 无 |
| 没有 usage 字段，或字段不是数值 | **全部为 0** | null | unknown | 0 | 无，ok 仍可为 true（探针） |
| 空事件流 | 全部为 0 | null | unknown | 0 | 空流、结束事件、stopReason、模型等 problem 照常出现（探针） |
| 没有 assistant，但 toolResult、entry 或 compaction 有用量 | token **照常累加**（不是 0，探针） | null | unknown（即使有费用） | 按规则计数 | stopReason=None、实际模型 [] 两条 problem；collect 状态为 INFRA_FAILURE |

结论：
- 旧实现中 **token 缺失时输出 0，而不是 null**，也没有“用量完整性”字段。
- **费用未知时 total 为 null**，status 为 unknown 或 partial，没有币种字段。
- 费用状态不产生 problem，也不参与门禁。
- `budget.cost_budget` 只出现在三处：默认值（1198）、derive-json 固定写 null（1396）、校验（1576-1580），运行时不据此拦截。

### 4.8 事件摘要会抛出未捕获异常的输入（LB-EVENTS-026）

| 输入 | 结果 | 位置 |
|---|---|---|
| `cost.total` 不是正数，且 `totalTokens` 是真值的非数值：非空字符串（如 "12"）、非空列表、非空对象。空串、空列表、空对象经过 `or 0` 不会报错 | TypeError：'>' not supported between instances of 'str' and 'int'（探针） | scripts/pi_dispatch.py:2092 |
| 最终 assistant 消息中，type=text 块的 text 不是字符串（例如 null） | TypeError：sequence item 0: expected str instance, NoneType found（探针） | scripts/pi_dispatch.py:2101、2320 |
| tool_execution_start 的 args.path 或 file_path 含 NUL | ValueError：stat: embedded null character in path（探针，由 Path.resolve 抛出） | scripts/pi_dispatch.py:2276-2277 |

`summarize_events` 不捕获这些异常。collect 在 try 之外调用它（3356）；main 只捕获 DispatchError 和 KeyboardInterrupt（4964-4971）。

按源码推断（未做端到端验证）：
- run 以 traceback 和 Python 默认退出码 1 结束；
- run.json 已写出（3343），state 停在 COLLECTING（3344），events-summary.json、report-status.json、summary.md 都不会写出；
- `wait` 把 COLLECTING 视为仍在运行，会一直返回 3（3914、3933-3937）；
- `collect --recover` 重跑同一解析，同样失败；
- smoke 同样以 traceback 结束，不打印报告，并保留临时目录（4796、4822-4823）。

### 4.9 事件摘要的字段、截断上限与写出方式

| 行为 | 位置 |
|---|---|
| **字段**：lines、event_counts、parse_error_lines、truncated、session_header、terminal_event、complete、final_stop_reason、final_error、requested_model{provider,model,thinking}、actual_models、response_models、provider_thinking_levels、thinking_evidence、model_match、assistant_messages、tool_calls、tool_errors、auto_retries、compactions、system_prompt_sections、usage、cost{total,status,unpriced_messages,note}、stderr_flags、shell_commands、suspicious_commands、temp_path_uses、temp_path_use_count、cache_dir_cleanups、outside_worktree_paths、own_run_paths、ambiguity_mention_count、ambiguity_domain_words、ambiguity_mentions、problems、ok（= not problems）。<br>cost.note 固定为“Pi 按模型目录价格估算；以提供商或网关账单为准” | scripts/pi_dispatch.py:2366-2408 |
| **截断上限**：parse_error_lines 50；shell_commands 200 条（每条前 500 字符）；suspicious_commands 100；temp_path_uses 50（另记总数）；cache_dir_cleanups 50；outside_worktree_paths 100；own_run_paths 50；ambiguity_mentions 20 | scripts/pi_dispatch.py:2245、2369、2396-2405 |
| **problems 的固定顺序**：空流 → 无法解析 → 截断 → 结束事件 → 思考级别不符 → stopReason → errorMessage → 文本工具调用 → 模型不符 → stderr（custom_model_id、invalid_thinking、unknown_option） | scripts/pi_dispatch.py:2339-2365 |
| **写出方式**：collect 每次都以非独占方式覆盖写 events-summary.json 和 report-status.json，recover 时会重写。smoke 的摘要不落盘到 run 目录，只进入 smoke 报告 | scripts/pi_dispatch.py:3360-3361、4796-4814 |

### 4.10 下游输出与门禁（LB-EVENTS-020/021/029）

| 输出 | 旧表现 | 位置 |
|---|---|---|
| summary.md 头部 | 实际模型行为空时写“无”；思考级别未回报时写“未回报（只能确认请求的级别；映射方式取决于协议）”。<br>用量行印出 input/output/cacheRead/cacheWrite 的原值（缺失为 0；没有 events-summary 时为 None），不显示 totalTokens。<br>费用为 null 时写“未知”，并附上 status | scripts/pi_dispatch.py:2861-2874 |
| summary.md 正文 | events problems 列在“## 执行完整性问题”；stderr 标记列在“## 复审需要关注” | scripts/pi_dispatch.py:2881-2882、2954-2955、2972 |
| status 的 COST 列 | 没有 events-summary 时为 `-`；total 为 null 时为 `unknown`；否则为 `<total>(<status>)`。<br>`status --json` 的 tokens 取 usage.totalTokens，没有摘要时为 null | scripts/pi_dispatch.py:4494、4505-4515 |
| status 和 wait 在运行中（LB-EVENTS-029） | `_live_progress` 不解析 JSON，只在字节里统计紧凑标记 `"type":"tool_execution_end"` 的次数；统计最后一个标记之后 `"type":"message_update"` 的次数，≥6000 时附“长时间没有工具调用（%d 个增量）”。输出为 `live:<N>t <秒>s…`。<br>status 对 RUNNING 行用它替换 EVENTS 列；wait 超时时打印它 | scripts/pi_dispatch.py:4518-4548、4562-4564、3935-3936 |
| metrics | tokens 是 totalTokens 之和，null 按 0 计。已知费用只累加非 null 的 total（partial 的也算）。<br>cost 为 null 或 status≠estimated 的轮次计入 unknown_cost_attempts。<br>汇总行“已知执行费用（估算，仅 Pi 执行端）”用 %.4f，并附“（另有 %d 轮费用未知或不完整，实际更高）”。<br>任务行没有已知费用时写 unknown，有部分未知时加“（不完整）” | scripts/pi_dispatch.py:4607-4617、4623-4647 |
| G1 | events-summary 中的每条 problem 都是一项 G1 失败；没有摘要文件时记“缺少事件摘要”。Pi 退出码不为 0（包括 None）时另记“Pi 退出码为 %s”。未回报思考级别和报告状态不是 json_ok 时只记 note | scripts/pi_dispatch.py:4165-4182 |
| collect 状态 | 依次判断：spawn_error、收集错误或没有候选树 → INFRA_FAILURE；超时 → TIMEOUT；中断 → CANCELLED；assistant_messages 为 0 → INFRA_FAILURE；其余 → NEEDS_REVIEW。events.ok 只写入 state 的 events_ok 字段，不改变状态 | scripts/pi_dispatch.py:3395-3406 |
| run 退出码 | 状态为 NEEDS_REVIEW 且 events.ok 为真时是 0，其他情况都是 1。Pi 自己的退出码不参与 | scripts/pi_dispatch.py:3348-3349 |

### 4.11 doctor、smoke 与预检的差异（LB-EVENTS-027）

| 方面 | 预检 | doctor | smoke | 位置 |
|---|---|---|---|---|
| 版本 | 退出码非 0 或解析失败时记 problem；偏低时记 note | 只看能否解析，不看退出码，失败时记“无法读取 pi 版本”；偏低时记 note | 只读 stdout；解析不出时 expects_settled=None | scripts/pi_dispatch.py:2038-2046、4684-4690、4774-4775 |
| 必需参数 | `--no-context-files` 只在 context_files=none 时要求 | 恒要求 `--no-context-files`，缺失时报“pi 缺少参数：%s” | 恒传 `--no-context-files` | scripts/pi_dispatch.py:2025-2030、4693-4697、4776-4777 |
| 模型列表 | 不区分 no_models 和 no_match | 只在同时给出 --provider 和 --model 时运行。退出码非 0 时报“pi --list-models 执行失败（退出码 %s）：%s。在 Codex 等沙箱中运行时，沙箱可能阻止了 pi 读取配置或联网：改在沙箱外运行 doctor 再判断”，并把 executor_model_listed 置为 null。模型未列出时按 empty_reason 附加说明 | 不检查 | scripts/pi_dispatch.py:4698-4717 |
| 凭据 | help 含 `pi auth` 时运行，**不带** `--no-refresh` | 同时给出 --provider 和 --model 时运行，**带** `--no-refresh`，失败时报“执行模型凭据未就绪（pi auth check --no-refresh 退出码 %s）” | 不检查 | scripts/pi_dispatch.py:2056-2064、4718-4724 |
| 思考级别 | 按 help 解析出的列表 | 还要求给出 --thinking，失败时报“思考级别 %s 不受本机 pi 支持” | 按 FALLBACK 固定列表，否则以退出码 2 拒绝 | scripts/pi_dispatch.py:2031-2033、4725-4726、4772-4773 |
| 事件摘要 | — | — | 每步调用 summarize_events，不传 allowed_outside 和 plan_text。一步通过的条件：退出码为 0、摘要 ok，并且满足 PI_SMOKE_OK 文本，或 smoke.txt=PI_TOOL_OK、write 和 read 各至少一次、tool_errors=0。遇到第一个失败步骤就停止 | scripts/pi_dispatch.py:4789-4816 |
| 输出与退出码 | 写 preflight.json | 整份输出经过 redact_obj；有 problem 时退出码为 1 | 整份输出经过 redact_obj，final_text 先脱敏再截前 500；失败时退出码为 1，并保留临时目录 | scripts/pi_dispatch.py:4758-4762、4810、4817-4824 |

### 4.12 脱敏规则（LB-EVENTS-022/023）

| 规则 | 内容 | 位置 |
|---|---|---|
| 预处理 | 去掉 ANSI 转义，删除 NUL | scripts/pi_dispatch.py:63、1980 |
| 嵌入的 JSON | 只在看起来像 JSON 开头的位置尝试解析：`{` 后面是引号或 `}`；`[` 后面是 `[`、`{`、引号、`]`、true、false、null，或是数字且紧接逗号或 `]`。所以 `[2026-09-23 12:34:56]` 不算（探针）。<br>结果必须是对象或数组。它会按结构脱敏，再用 json.dumps 重新序列化，所以格式会变，重复的键只剩最后一个；孤立代理码点恢复为转义形式。<br>解析失败或 RecursionError 时交给文本规则 | scripts/pi_dispatch.py:1939-1968、1981-1989 |
| 结构脱敏 `_redact_json` | 键名完整匹配疑似凭据键时，其下所有非空字符串（包括嵌套的）换成 `<redacted>`；数字、布尔、null 和空串保留。其余字符串继续做文本脱敏 | scripts/pi_dispatch.py:1926-1936 |
| 疑似凭据键 | 键名的任意位置（可带 `[\w.-]` 前后缀）含以下之一，不区分大小写：api key、apikey、access key、secret key、private key、auth token（分隔符可以是空格、_、- 或没有）、token、secret、password、passwd、credential、authorization。<br>因此纯文本中的 `totalTokens=1200`、`max_tokens: 8192` 的数值也会被遮蔽（探针）；JSON 中的数字则保留 | scripts/pi_dispatch.py:1900-1902 |
| PEM 私钥 | 从 BEGIN … PRIVATE KEY 到对应的 END 行整块替换；没有 END 行时替换到文本结尾 | scripts/pi_dispatch.py:1907、1990 |
| 令牌 | 不区分大小写：Bearer 后接至少 8 个令牌字符；或 sk、pk、rk、ghp、gho、ghu、ghs、github_pat、xox[abpr] 后接 - 或 _，再加至少 8 个字符（探针） | scripts/pi_dispatch.py:1904-1905、1991 |
| 键值 | 键（可带任意层转义引号）后接 : 或 = 时，值一直遮到行尾，缩进的续行一并删除并遮蔽。<br>值在本行确定不了结束时，遮蔽整段文本的其余部分。这类值包括：空值；以 `{`、`[`、`(` 开头；以逗号、反斜杠、`{`、`[`、`(` 或冒号结尾；YAML 块标量指示符；引号开头但本行没有闭合（探针） | scripts/pi_dispatch.py:1910-1923、1992-1999 |
| redact_obj | 只对 str 做文本脱敏，递归处理 list 和 dict，**不看字典键名**，也不遍历 tuple：`{"apiKey": "zz"}` 中的 zz 会保留（探针） | scripts/pi_dispatch.py:2003-2011 |
| 已脱敏的输出 | 预检的全部产物文件、各条 problem（先脱敏再截断）、preflight.json（history.jsonl 中的 problems 也取自它）。<br>auto_retries 的错误文本。<br>最终 errorMessage：problems 中先脱敏再截断；final_error 字段整段脱敏、不截断。<br>doctor 和 smoke 的整份输出 | scripts/pi_dispatch.py:2021-2067、2304-2306、2356、2375、4758、4818 |
| **未脱敏**的输出 | 原始 events.jsonl 和 stderr.log（注释说明它们位于被 Git 忽略的 .agent/runs/）。<br>events-summary.json 中的 shell_commands、suspicious_commands.command、cache_dir_cleanups、路径记录、歧义摘录。<br>summary.md 中引用的上述内容。<br>executor-report.md（最终文本原样写出）和 executor-report.json | scripts/pi_dispatch.py:1976-1977、2245、2265、2268、2281-2283、2415、2424 |

### 4.13 执行报告与歧义提示（LB-EVENTS-024/025）

| 行为 | 位置 |
|---|---|
| **执行报告**：<br>- 最终文本去空白后为空：status=missing，不写文件；<br>- 否则覆盖写 executor-report.md（补结尾换行），再用非贪婪 DOTALL 正则找 `` ```json `` 代码块，取最后一个：没有代码块时为 no_json；json.loads 失败时为 json_invalid（带 error）；成功时写 executor-report.json，返回 json_ok 和 executor_status。<br>- contract_conflicts 和 unresolved_questions 是列表时记长度，否则记 0。<br>- 结果写入 report-status.json；不是 json_ok 时只作为 G1 note | scripts/pi_dispatch.py:2412-2429、3361、4180-4182 |
| **歧义提示**：<br>- 在每条 assistant 的 text 和 thinking 块中查找 ambigu、contradict、inconsisten、矛盾、歧义、含义不明、前后不一致、说法不一。<br>- 以下情况不计：合同领域用语（plan.md 中，停止条件和禁止章节之外出现至少 2 次的词）；紧前 24 个字符内有否定（80 个字符内有双重否定时仍计）；紧跟的 80 个字符内是独立的否定答案；前后 240 个字符内没有提到合同、规范、步骤或要求。<br>- 同一段中相邻的命中只记一次；摘录取命中前 100 到后 140 个字符，压缩空白后截 260。<br>- 最后一条 assistant 的 text 块中的命中被剔除。<br>- 只影响 summary.md 的关注项和备注，以及 G3 note，不进入 problems | scripts/pi_dispatch.py:269-301、2106-2157、2322、2961-2970、4183-4187 |

### 4.14 测试映射与覆盖缺口（LB-EVENTS-028）

| 测试检查 | 覆盖的旧行为 | 位置 |
|---|---|---|
| test_happy：“events complete via agent_settled”“usage sums assistant message_end only”“thinking not reported -> evidence says so, no problem” | 以 settled 结束时判为完整。两条 assistant 的 input 相加为 2000，message_update 顶层的 usage 不计，status 为 estimated。思考级别未回报不算 problem | tests/test_dispatch.py:247-252；tests/stub_pi.py:103-104、129-132 |
| test_events_and_thinking：“error stopReason -> exit 1 but NEEDS_REVIEW”“PASS refused on G1” | stopReason=error 产生 problem，run 退出码为 1，状态为 NEEDS_REVIEW，G1 失败 | tests/test_dispatch.py:370-374；tests/stub_pi.py:225-226 |
| “events case model {}”“startfail {}”“nosettle {}”“ok {'STUB_PTL': 'low'}”“ok {'STUB_NOCOST': '1'}”“status shows unknown cost” | model 场景只断言 model_match 为假；startfail 只断言状态为 INFRA_FAILURE，**不断言**模型证据；nosettle 断言缺 settled 的 problem；STUB_PTL 断言思考级别不符；STUB_NOCOST 断言 null/unknown；status 显示 unknown | tests/test_dispatch.py:382-395 |
| test_preflight_and_budget：“model not listed -> preflight fail, stays PREPARED”“auth not ready -> preflight fail”“run after fixing env” | 预检失败后不领取，修正后可再次 run（此处 stub 走的是 no_match 分支）。只断言退出码非 0，没有断言等于 3 | tests/test_dispatch.py:495-506 |
| test_feedback_v12：文本工具调用和 G1 | 最终正文含工具调用时产生 problem | tests/test_dispatch.py:1094-1101 |
| test_feedback_v12 的“live status flags a long stretch without tool calls” | _live_progress 的计数和阈值提示。测试自己写入紧凑 JSON | tests/test_dispatch.py:1142-1155 |
| test_v21_codex_trial_feedback：脱敏系列、“a long final error is redacted before it is cut”“model table parsing ignores pi's no-model messages”“preflight records and output are redacted” | 脱敏；list-models 表格解析；预检产物和输出中不含凭据 | tests/test_dispatch.py:1600-1699 |
| test_setup_wrapper_doctor：doctor 和 smoke 的检查 | doctor 区分 list-models 失败、no_models、no_match，以及模型挂在其他 provider 下的情况；smoke 两步都通过 | tests/test_dispatch.py:715-750 |

stub 的模拟范围：
- **命令行响应**：
  - `--help` 输出 stub_pi_help.txt，其中含 `pi auth` 和“Built-in Tool Names:”一节；
  - `--version` 恒为 0.87.0；
  - auth 由 STUB_AUTH 和 STUB_AUTH_DETAIL 控制；
  - `--list-models` 按 STUB_MODELS 过滤：为空时输出“No models available…”，无匹配时输出“No models matching …”；STUB_LIST_FAIL=1 时以退出码 1 结束，并在 stderr 带出伪凭据。
- **任务流**：session → agent_start → turn_start → system 的 message_start/message_end（带 sections）→ 第一条 assistant（toolUse）的 message_start、顶层带 usage 的 message_update、message_end → 工具事件 → turn_end → turn_start → 最终 assistant 的 message_start/message_end → turn_end → agent_end(willRetry=false) → agent_settled。
  - nosettle 场景省略 agent_settled；
  - startfail 场景只发 session 后以退出码 1 结束；
  - 提示中缺 TASK: 或执行说明时，发 session 后以退出码 3 结束。
- **任务流中的 assistant 消息**：带 api=anthropic-messages、provider、model、responseModel、usage（input 1000、output 200、totalTokens 1200、cost.total 0.00043；STUB_NOCOST=1 时费用全为 0）。model 场景只把 model 和 responseModel 改为 stepfun/step-3.5-flash，provider 不变。只有设置了 STUB_PTL 才带 providerThinkingLevel。
- **smoke 模式**（没有 @文件、有消息）：不发 message_start 和 turn 事件；assistant 不带 api 和 responseModel，usage 为 10/2/12，cost 为 0.00001，也不看 STUB_PTL。
- **序列化格式**：stub 用 `json.dumps` 的默认分隔符（`"type": "x"` 带空格），与 _live_progress 查找的紧凑标记不匹配，所以端到端的 live 计数为 0。
- 位置：tests/stub_pi.py:33-65、72-100、102-116、125-235；tests/test_dispatch.py:29

没有测试覆盖的行为：
- resolve_pi_command 的 which 和 shim 分支，以及 ensure_argv_safe（测试一律经 `PI_DISPATCH_PI_CMD` 启动 stub）；
- context_evidence；
- expects_settled 为 False 或 None 的分支；
- 空流、无法解析的行、截断；
- settled 之后的工作事件或非工作事件；
- entry_appended、compaction_end、toolResult 的用量，auto_retry；
- partial 费用；
- stderr_flags；
- responseModel 与要求不同；
- provider 或 model 字段缺失；
- 部分消息回报思考级别；
- 重复的 message_end；
- 非数值 usage、NUL 路径、非字符串 text 引起的异常；
- Pi 非零退出但事件完整的情况；
- 预检中缺参数、思考级别不支持、未知工具、版本不可读、list-models 失败的分支（这些只有探针复现）。

### 4.15 未决事项

- **用量口径**：真实 Pi 0.87 的 assistant `usage` 是单次请求的增量还是累计值？旧实现按增量相加。
- **用量重叠**：entry_appended 的 usage、toolResult 的 usage、compaction_end 的 usage 与 assistant 的 usage 是否重叠？真实 Pi 是否对同一次调用重复发出？旧实现不去重。
- **模型字段来源**：`message.provider/model` 是 Pi 按配置填写的，还是来自提供商的响应？responseModel 不参与比较。
- **版本依据**：“0.80.4 起提供 agent_settled”只有源码注释这一来源。
- **凭据刷新**：预检的 auth check 不带 `--no-refresh`，会不会刷新或改写凭据？
- **脱敏设计**：纯文本中的 token 计数被遮蔽、redact_obj 不按键名遮蔽、events-summary 中的命令文本不脱敏，这些是否是有意的设计？
- **异常输入**：三类未捕获异常输入（非数值 totalTokens、非字符串 text、含 NUL 的路径）的端到端结果尚未验证；真实 Pi 是否可能产生这些输入，也未知。
- **退出码**：Pi 非零退出但事件完整时，run 仍可能以 0 退出、状态为 NEEDS_REVIEW。这是源码推断，没有测试，也没有端到端探针。
- **序列化格式**：真实 Pi 的 JSONL 是否是紧凑格式（没有空格）？这决定 `_live_progress` 能否计数；stub 输出带空格。
- **终止后的内容**：agent_settled 之后到来的非工作事件会静默替换最终消息，真实 Pi 是否会发出这类事件？
- **维度与零值语义**：旧实现只有 `complete` 和 `ok` 两个维度，没有文档 4.3.4 要求的 protocol_complete、usage_complete、process_exited 独立维度。token 缺失时输出 0，与 4.3.7“null 表示未知”冲突。迁移比较投影时，要保留 cost.status、unpriced_messages 和 problems，并说明 token 的 0 可能代表未知。
- **探针记录**：本节“探针”结论来自 scratchpad 中的合成事件流和 stub 预检，要在 P1 取证中用固定的 fixture、被测提交和命令重新记录。

### 未解决事项（第 4 节）

- 真实 Pi 0.87 的 assistant message.usage 是单次请求的增量还是累计值？旧实现按增量相加（_add_usage，scripts/pi_dispatch.py:2081-2093），源码和 stub 都不能证明是哪一种。
- 真实 Pi 是否对同一次调用同时发出 message_end 的 usage 和 entry_appended{type:usage}？toolResult 和 compaction_end 的 usage 是否与 assistant 的 usage 重叠？旧实现全部相加，存在重复累加风险（探针已复现）。stub 不发这些事件，也没有测试。
- message.provider/model 是 Pi 按配置填写的，还是来自提供商的响应？responseModel 只记录、不比较（scripts/pi_dispatch.py:2325），网关替换了模型也不会被判为不符。
- “agent_settled 自 0.80.4 起提供”只有源码注释这一来源（scripts/pi_dispatch.py:50）。expects_settled 为 False 或 None 的分支没有测试；None 可以从 smoke、recover（缺 run-started.json 且缺 pi-version.txt）或旧 run.json 进入。
- 预检的 auth check 不带 --no-refresh（scripts/pi_dispatch.py:2058），doctor 带（4719）。预检会不会刷新或改写凭据，尚未核实。
- 纯文本脱敏会遮蔽 totalTokens=…、max_tokens: … 这类计数；redact_obj 不按键名遮蔽普通字符串值，也不遍历 tuple；events-summary 中的 shell_commands 和路径不脱敏。这些是否是有意的设计，源码中没有说明。
- summarize_events 遇到以下三类输入会抛出未捕获的异常：非数值的真值 totalTokens（TypeError，2092）、最终消息中不是字符串的 text（TypeError，2101）、含 NUL 的工具路径（ValueError，2277），均已由探针复现。按源码推断：run 以 traceback 结束，状态停在 COLLECTING，wait 会一直返回 3，recover 同样失败。端到端尚未验证，真实 Pi 是否可能产生这些输入也未知。
- Pi 非零退出、但事件完整且 ok 时，collect 状态为 NEEDS_REVIEW，run 退出码为 0，只有 G1 记录退出码（3348-3349、3395-3404、4173-4174）。这是源码推断，没有测试，也没有端到端探针。
- 真实 Pi 输出的 JSONL 是否是紧凑格式（没有空格）？_live_progress 依赖紧凑标记 `"type":"tool_execution_end"`（4543），stub 用带空格的 json.dumps，端到端的 live 计数为 0。
- agent_settled 之后到来的非工作事件（例如没有 message_start 的 assistant message_end）会静默替换最终消息并累加用量，complete 不变（探针）。真实 Pi 是否会发出这类事件，尚未核实。
- 旧实现没有 usage_complete，也没有 token 未知标记：token 缺失一律为 0，与文档 4.3.7 的 null 语义冲突；费用未知时为 null。比较投影要保留 cost.status、unpriced_messages 和 problems，并单独说明 token 的 0 可能代表未知。cost.total 为 inf 或 token 为 NaN 时会写出非标准 JSON。
- 本清单中的“探针”结论来自规划端 scratchpad 中的合成事件流和 stub 预检，要在 P1 取证中用固定的 fixture、被测提交和命令重新记录。

## 5. 候选树、补丁、范围与 G0–G6 门禁

> **纳入说明**：本节是区域章节原稿（已经对抗核对），正文照录，只统一了标题层级并修正排版。
> - 原稿编写时尚未取得 `bl-01t1-legacy-20260925` 的运行结果，文中“没有运行”“未运行”“NOT_RUN”“结果未知”等说法描述的是原稿编写时的状态；本次运行结果见本文第 0.3、2、9、10 节。
> - 正文中的“第 k 节”“见第 k 节”指本区域内的 5.k 小节，不是本文的第 k 节。
> - 标“实测”“探针”的内容是起草或核对者在会话临时目录中的一次性复现，没有归档为 fixture，证据等级仍按 source_inspected 记。
> - 5.10 小节是按源码填写的 7.3 占位表；它的“平台与结果”列已由本文第 2 节按本次运行结果取代。

> **取证范围**
> - 读取对象：`scripts/pi_dispatch.py`、`tests/test_dispatch.py`（只读）；`.agents/skills/review-pi/gates.md` 只算 source_reported。
> - 被读提交：`a4fa199b0e5bdc658215765ee7558b9fe6723940`。
> - 没有运行 `tests/test_dispatch.py`，表中所有测试标识的状态都是 NOT_RUN。
> - 以 `PYTHONDONTWRITEBYTECODE=1` 在内存中调用了 `evaluate_scope`、`matches`、`line_ending_args`，不写仓库文件。
> - 在会话临时目录的一次性 Git 仓库中，验证了 `git diff --quiet --ignore-cr-at-eol` 对“只差 CRLF”和“只差 CRLF 再加一个新文件”两种情况的返回码，验证后已删除该仓库。
> - 行号未注明文件时均指 `scripts/pi_dispatch.py`。ID 列对应结构化清单中的 `LB-GATES-NNN`。

### 5.1 枚举、退出码与门禁名称

| 项 | 旧值 | 来源 | ID |
|---|---|---|---|
| GATES | `G0`…`G6`。源码只有编号，没有名称 | :79 | 001 |
| VERDICTS | PASS、ACCEPTED_WITH_EXCEPTION、REVISE、BLOCKED、ESCALATE | :75 | 001 |
| PASSING_VERDICTS | PASS、ACCEPTED_WITH_EXCEPTION | :76 | 001 |
| FAILURE_CLASSES | PLAN_ERROR、EXECUTION_ERROR、INFRA_FAILURE、SCOPE_VIOLATION、REQUIREMENT_BLOCKED、TIMEOUT、BUDGET_EXCEEDED、CANCELLED | :77-78 | 001 |
| REVIEWABLE_STATES | NEEDS_REVIEW、TIMEOUT、CANCELLED、INFRA_FAILURE，加上全部 VERDICTS | :80 | 001 |
| 退出码 | OK=0、FAIL=1、USAGE=2、BLOCKED=3、DRIFT=4。EXIT_DRIFT 只用于 check 的漂移拒绝 | :53, :4014 | 001 |
| DispatchError | 缺省 code=3 | :304-309 | 001 |
| main 的异常处理 | 未给子命令时打印帮助并返回 2。DispatchError：向 stderr 打印 `ERROR: <msg>`，返回其 code。KeyboardInterrupt：打印 `已取消。`，返回 130。其他异常不捕获，以 Python 回溯退出 | :4953-4971 | 001 |
| verdict 参数 | `--verdict` 必填，取值限 VERDICTS；`--review` 必填；`--class` 取值限 FAILURE_CLASSES；`--waive` 可重复；`--decided-by`、`--human-minutes`（float）、`--note` 可选 | :4908-4917 | 001 |
| 门禁名称（source_reported） | G0 输入一致、G1 执行完整、G2 范围合规、G3 行为正确、G4 回归检查、G5 质量复审、G6 可集成 | gates.md:7-13 | 002 |

### 5.2 候选树与补丁往返

| 步骤 | 旧行为 | 来源 | ID |
|---|---|---|---|
| 固定行尾配置 | prepare 在 meta 中写 `git_autocrlf`：取 `git config --get core.autocrlf` 去空白后的小写值，没有值时记 `unset`。快照和补丁重建时，`true`/`false`/`input` 加 `-c core.autocrlf=<值>`，`unset` 加 `-c core.autocrlf=false`。其他取值（meta 中没有该字段，或 `yes`/`1` 这类布尔同义写法）不加参数，沿用当时的配置。只有 snapshot_tree 的 `add` 和 tree_from_patch 的 `apply --cached` 使用它；prepare 与干净副本的检出、干净副本上的 `git apply`、主工作区指纹都不固定 | :3210, :773-790, :805, :825 | 003 |
| 快照 snapshot_tree | 用临时索引 `<scratch>/.<label>.index`，前后都删除它和 `.lock`。步骤：`read-tree <base>` → `add -A -- .` → `write-tree`。结果包含已跟踪文件和未被忽略的新文件，不含被忽略的文件。不改真实索引和 HEAD，不建提交 | :793-813 | 004 |
| 生成补丁 | `candidate.patch` 以 `xb` 独占创建，内容为 `git diff --binary --no-ext-diff --no-textconv --no-renames --full-index <base> <tree>`。`candidate.stat.txt` 覆盖写 | :2517-2524 | 005 |
| 往返校验 | 临时索引 `.roundtrip.index`（开始前只删索引，不删 `.lock`）：`read-tree base`；补丁非空时 `apply --cached --binary --whitespace=nowarn`；再 `write-tree`。`patch_roundtrip_verified` 为重建树与 tree 是否相等。只捕获 DispatchError，此时记 `roundtrip_tree="error: …"`、verified 为 false | :816-830, :2525-2529 | 005 |
| candidate.json | 字段：tree、base、patch、patch_sha256、patch_bytes、patch_roundtrip_verified、roundtrip_tree、recorded_at。以 exclusive 写入 | :2530-2532, :3366 | 005 |
| 完整性判定 candidate_patch_ok | 三者同时成立：verified 为真、`candidate.patch` 是文件、文件 sha256 等于 patch_sha256。不重做往返。原地 check 与 branch 不调用 | :3474-3477 | 006 |
| collect 顺序 | record_candidate → candidate.json → `rev-parse HEAD` → diff_raw → changes.json → evaluate_scope（含配置的 extra_protected_paths）→ scope.json（加入 head_after）。任一步抛 DispatchError 或 OSError，都记入 collect_errors | :3364-3374 | 007 |
| collect 状态 | 有 spawn_error 或 collect_errors，或没有 tree → INFRA_FAILURE。否则依次判：timed_out → TIMEOUT；interrupted → CANCELLED；没有 assistant 回复 → INFRA_FAILURE；其余 → NEEDS_REVIEW。往返失败和越界都不改变状态 | :3395-3406 | 007 |
| collect --recover | 已有的 candidate.json、changes.json、scope.json、candidate.patch 改名为 `*.partial`，再重新 collect。stat 文件直接覆盖 | :3436-3440 | 008 |
| diff_raw | 命令为 `--raw -z --no-renames --no-abbrev --no-ext-diff --no-textconv`。每项为 `{path,status(首字母),old_mode,new_mode}`；路径不是合法 UTF-8 时加 `path_decode_error` | :833-855 | 009 |

### 5.3 候选漂移在各入口的旧行为

`tree_drift`（:864-870）：两树相同时返回空；否则 status≠A（包括 M、D、T）归入 modified，status=A 归入 added。

`line_endings_only`（:858-861）：`git diff --quiet --ignore-cr-at-eol` 比较**整棵树**。已核实：另有新增文件时它返回 False。

缓存类文件默认为 `**/__pycache__/**`、`**/*.pyc`、`**/.pytest_cache/**`、`**/.mypy_cache/**`、`**/.ruff_cache/**`，另加配置 `check_artifact_patterns` 中合法的项（无效项静默丢弃），匹配区分大小写（:3458-3471）。

被忽略的文件从不进入快照，所以在任何入口都不算漂移。

| 入口 | 比较对象 | modified 非空 | added 非空 | 结果 | 来源 | ID |
|---|---|---|---|---|---|---|
| check 运行前 | 原地时为执行 worktree，--fresh 时为干净副本；都与 candidate.tree 比较 | 拒绝 | 去掉缓存类后仍非空则拒绝 | 写 `{"aborted":"candidate_drift",…}`，报 `工作副本与候选不一致，检查结果无法代表候选：被修改的候选文件 %s；候选之外的新文件 %s。删除这些额外文件、重新派遣以固定新候选，或用 --fresh 在干净副本上验收。`。其中 %s 是 Python 列表的 repr（如 `['src/helper.py']`），为空时为 `无`。退出码 **4** | :4002-4014 | 013 |
| check 运行后 | 同上 | 记 `modified_by_checks=true`，打印 WARN | 去掉缓存类后仍非空则记入 `unexpected_files_by_checks`，打印 WARN | 仍写记录，退出码 1 | :4022-4052 | 014 |
| check --fresh 建副本 | 基线 + 补丁 + setup | 快照≠tree 时报 `干净副本与候选树不一致：<ws>` | setup 后快照≠tree 时报 `setup 改动了干净副本中的候选文件或产生了未忽略的新文件` | 执行 worktree 中的额外文件不影响结果；失败时不移除已登记的临时 worktree | :3480-3503, :3989-3995 | 012 |
| mutate 结束后 | 干净副本与 tree | 写入 `candidate_files_left_modified`，打印 WARN | 不看 | 退出码仍为 0 | :3667-3689 | 016 |
| verdict 的 G6 | 执行 worktree 与 tree（label gate，会写 Git 对象） | 整树只差行尾时给专门消息，否则报 `候选文件在记录后被修改：…`，G6 失败 | 只作备注，不过滤缓存类 | worktree 目录不存在时整段跳过 | :4237-4253 | 030 |
| cleanup | 执行 worktree 与 tree | 记 LOSS | 去掉缓存类后仍非空则记 LOSS | 不带 --force 时拒绝，退出码 3；被忽略的文件不记 LOSS | :4444-4467 | 037 |
| branch | 不比较 | — | — | 只用 candidate.tree；树对象丢失时按补丁重建，不校验 patch_sha256 | :4344-4352 | 035 |

### 5.4 范围判定 evaluate_scope

模式规则（:1063-1093）：

- `**/` 对应 `(?:[^/]+/)*`，`**` 对应 `.*`，`*` 对应 `[^/]*`，`?` 对应 `[^/]`，匹配用 fullmatch。
- 实测：`**/AGENTS.md` 能匹配根目录的 `AGENTS.md`；`tests/*.py` 不匹配 `tests/x/y.py`；带末尾换行的路径不匹配。

大小写：

- 受保护路径（内置 PROTECTED_PATTERNS 加配置 extra_protected_paths）不区分大小写，例如 `docs/agents.md` 也命中。
- scope 各列表、依赖清单、敏感清单区分大小写，例如 `Package.json` 不算依赖清单（:2439-2446）。

| 序 | 条件 | kind | 级别 | detail 原文 | 来源 |
|---|---|---|---|---|---|
| 1 | `path_decode_error`，或路径含控制字符 | invalid_path（path 用 repr 表示） | 违规，跳过后续判定 | 路径含控制字符或不是合法 UTF-8 | :2453-2458 |
| 2 | 命中受保护路径 | protected_path | 违规 | 合同、证据、代理规则或调度器文件 | :2459-2461 |
| 3 | 否则命中 forbidden_paths | forbidden_path | 违规 | 命中 forbidden_paths | :2462-2464 |
| 4 | 否则不在按状态选定的允许集合中（A 用 allowed_new_files，D 用 allowed_deleted_files，其余用 allowed_modified_files） | out_of_scope | 违规 | 状态 X 不在允许集合 | :2465-2467 |
| 5 | new_mode 为 120000 | symlink | 违规 | 新增或改为符号链接 | :2468-2470 |
| 6 | old_mode 或 new_mode 为 160000 | submodule | 违规 | 子模块或嵌入仓库变化 | :2471-2473 |
| 7 | 状态为 M/T，模式有变化，且都不是 120000 | mode_changed | 警告 | `old -> new` | :2474-2477 |
| 8a | 命中依赖清单、dependency_changes=forbidden，且路径**字面**等于 allowed_modified_files 或 allowed_new_files 中的某一项 | dependency_manifest_changed | 警告 | 合同允许修改此文件，但禁止依赖变更：需人工确认 | :2478-2481 |
| 8b | 同上，但路径不在上述列表中 | dependency_change | 违规 | 合同禁止依赖变更 | :2482-2484 |
| 9 | 命中敏感清单 | sensitive_file | 警告 | 测试/CI/构建或环境配置被修改 | :2485-2486 |
| 10 | head_after≠base | head_moved（path 为 `HEAD`） | authorization.executor 含 local_commit 时为警告，否则为违规 | 执行器改变了 HEAD（前12位） | :2488-2491 |

- 第 2、3、4 行是互斥的 elif；第 5、6、8 行与前面的结果叠加。例如 test_scope 中的 package.json 同时记了 forbidden_path 和 dependency_change。
- 输出为 `{files, counts{A,M,D,T}, violations, warnings, ok}`，其中 `ok` 表示没有违规（:2487-2494）。
- 已实测的空档：符号链接改回普通文件（T，120000 → 100644）既不记违规也不记警告。

合同阶段的静态校验在 `_validate_contract`（:1440）的 :1499-1526，由 validate_plan（:1656）经 :1673 的 validate_contract（:1432）调用：

- 四个列表都必须是数组。
- 每个模式都要通过 pattern_error，否则拒绝。拒绝的情况有：空串、控制字符、反斜杠、绝对路径（包括以 `~` 开头）、空段、`.`、`..`，以及以“范围过宽”拒绝 `*`、`**`、`**/*`（:1100-1113）。
- 允许集合中的模式文本命中受保护路径时，报“包含受保护路径”。因为比的是模式文本，`**/*.md` 这类通配能通过校验，运行时再判为 protected_path（已在内存中核实）。
- 允许修改和允许新增都为空时报错。
- 不含 `*` 的允许项命中 forbidden 时报错。
- dependency_changes 不是 forbidden/allowed 时报错；缺省为 forbidden（:1194-1195）。

### 5.5 主工作区指纹（只作 G2 备注）

| 项 | 旧行为 | 来源 |
|---|---|---|
| 指纹 | `{head, content_tree}`：用临时索引 `.main-fingerprint.index`，HEAD 存在时 `read-tree HEAD`，然后 `add -A` → `write-tree`；出错时为 `error: …`。不固定 autocrlf | :879-904 |
| 采集时机 | run 在领取前采一次，写入 run-started.json 和 run.json；collect 再采一次 | :3298, :3317, :3382-3391 |
| 变化分类 | changed 表示 before 非空且与 after 不同；head_changed 同理只比 head。然后用 `diff-tree -r --no-renames --name-status -z` 按 planner_paths 分成 planner_paths 和 other_paths，各截到 200 条。planner_paths 缺省为 `.agent/plans/**`、`.agent/reviews/**`、`.agent/design/**`、`.agent/*.md`，可在配置中修改，只在 Windows 上不区分大小写。指纹不完整时 diff_error 为 `指纹不完整，无法列出变化的路径`；diff-tree 失败时取 stderr 的前 300 字符，为空时取 `git diff-tree 失败` | :907-940, :1000-1008 |
| 进入门禁 | head_changed 为真或 other_paths 非空时，只加一条 G2 备注，从不判失败。有 diff_error 时两者都为空，G2 没有备注，只在 summary 中提示 | :4194-4196, :2945-2947 |

### 5.6 G0–G6：evaluate_gates 的精确断言

每个门禁初始化为 `{"passed":True,"problems":[],"notes":[]}`，键顺序同 GATES。代码中的求值顺序：

1. G0；
2. G1 的失败项与备注；
3. G3 备注；
4. G2 与备注；
5. 最近一次检查记录无效时，G3、G4 同时失败；有效时先判 G4 的各项与备注，再判 G3 的 DoD；
6. G6。

返回结果和 verdict 的失败列表都按 G0…G6 排列（:4152-4158, :4256, :4281）。

| 门禁 | 失败条件 | problem 原文 | 来源 |
|---|---|---|---|
| G0 | run_dir 中的 plan.md 不存在，或 SHA-256 与 meta.plan_md_sha256 不同 | `plan.md 的哈希与 prepare 时记录的不一致` | :2659-2665, :4160-4161 |
| G0 | contract.json 同上 | `contract.json 的哈希与 prepare 时记录的不一致` | 同上 |
| G0 | `rev-parse --verify --quiet <base>^{commit}` 的结果不等于 meta.base_sha | `基线提交不可用` | :768-770, :4162-4163 |
| G1 | run.json 缺失或无法解析 | `缺少 run.json`，同时 exit_code 为 None 还会触发下一条 | :4165-4168 |
| G1 | timed_out 为真 | `运行超时` | :4169-4170 |
| G1 | interrupted 为真 | `运行被取消或调度器中断` | :4171-4172 |
| G1 | exit_code≠0（包括 None） | `Pi 退出码为 <code>` | :4173-4174 |
| G1 | events-summary.problems 的每一条；文件缺失或没有该键时计一条 | 原文照录，或 `缺少事件摘要` | :4175-4176（条目来源 :2338-2365） |
| G2 | scope.json 缺失或无法解析 | `缺少 scope.json` | :4188-4190 |
| G2 | scope.violations 的每一条 | `<kind> <path>`，例如 `out_of_scope README.md`、`head_moved HEAD` | :4191-4193 |
| G3 与 G4 | 最近一次 `checks/NN/checks.json` 缺失、无法解析、为空，或含 aborted。“最近一次”取名字符合 `^\d{2,}(\.json\|\.md)?$` 的最大编号项 | `没有有效的独立检查记录`（两门同时失败，且不再判 DoD） | :4200-4205, :3446-3450 |
| G4 | checks.candidate_tree≠candidate.tree | `最近一次检查不是针对当前候选` | :4208-4209 |
| G4 | covers_all_required 为假 | `最近一次检查没有覆盖全部必要检查（使用了 --only？）` | :4210-4211 |
| G4 | modified_by_checks 为真 | `检查过程修改了候选文件：<前10，逗号分隔>` | :4212-4213 |
| G4 | unexpected_files_by_checks 非空 | `检查产生了候选之外的新文件：<前10>` | :4214-4215 |
| G4 | 合同中每个 required（缺省 true）的检查，在最近一次记录中缺失或未通过 | `必要检查 <id>：<status 或 not_run>` | :4223-4227 |
| G3 | DoD 的 evidence 含 `scope`，而 scope.json 缺失或有违规 | `<DoD> 依赖的范围证据未通过` | :4228-4232 |
| G3 | DoD 的 evidence 是检查 id（`review` 被跳过），最近一次记录中该项缺失或未通过 | `<DoD> 依赖的 <ref> 未通过或未运行` | :4233-4236 |
| G5 | 没有机械断言，恒为通过 | — | :4153-4154 |
| G6 | 有 tree，worktree 是目录，modified 非空，且整树只差行尾 | `候选文件与记录只差行尾（CRLF / LF）：<n> 个文件。多半是 core.autocrlf 在运行后被改动（prepare 时记录 <值/未记录>，现在 <值>）；先恢复配置再重新 verdict` | :4237-4246 |
| G6 | 同上，但不只是行尾，包括同时存在新增文件的情况 | `候选文件在记录后被修改：<前10>` | :4247-4248 |
| G6 | 快照抛出 DispatchError | `无法重新快照：<msg>` | :4252-4253 |
| G6 | candidate_patch_ok 为假（不论上面结果如何都检查） | `候选补丁缺失、被改动或未通过往返校验` | :4254-4255 |

G0 相关补充：

- meta.json 本身不做校验。
- contract.json 哈希不一致时，G3/G4 仍按 run_dir 中被改动的合同判定（:2653-2656）。
- contract.json 被删除或不是合法 JSON 时，verdict 在 load_attempt 就会抛出未捕获的异常，G0 来不及报告（推断）。

备注（不影响通过与否）：

| 门禁 | 条件 | note 原文 | 来源 |
|---|---|---|---|
| G1 | events 非空，且 provider_thinking_levels 为空 | `提供商未回报思考级别：只能确认请求的级别（<thinking>）` | :4177-4179 |
| G1 | report-status.status≠json_ok（包括缺失时的 None） | `执行报告状态：<status>` | :4180-4182 |
| G2 | main_repo_changes 的 head_changed 为真，或 other_paths 非空 | `运行期间主工作区有规划路径之外的变化，复审时确认来源（见 summary.md）` | :4194-4196 |
| G2 | outside_worktree_paths（最多 100 条）中 failed 不为 True 的每一项 | `执行器访问了工作副本外路径：<path>（<tool>）` | :4197-4199 |
| G3 | report.contract_conflicts（计数）为真 | `执行报告列出了 <n> 处合同矛盾：PASS 前在复审中逐条裁定` | :4183-4185, :2426-2427 |
| G3 | 否则 ambiguity_mention_count 为真，且没有 unresolved_questions | `执行过程中提到合同的歧义、矛盾或一致性，报告没有列出：复审时核对（见 summary.md）` | :4186-4187 |
| G4 | artifact_files 非空 | `忽略的缓存文件：<前10>` | :4216-4217 |
| G4 | mode 为 fresh，或为其他值 | `检查在干净副本（基线 + 候选补丁 + setup）上运行`，或 `检查在执行 worktree 中运行：被 .gitignore 忽略的文件（依赖、构建产物）也可能影响结果；中高风险任务建议 check --fresh` | :4218-4222 |
| G5 | 恒有 | `质量复审（测试是否弱化、兼容性、残余风险）由复审报告负责，工具不做机械判断` | :4154 |
| G6 | added 非空 | `工作副本有候选之外的新文件（不会被集成）：<前10>` | :4249-4251 |

verdict 只把 G3 的备注打印为 `NOTE  G3 …`（:4282-4283），其余备注只写进 `verdicts/NN.json`。

### 5.7 verdict 与门禁要求

前置校验顺序（在 load_attempt 之后）：

| 序 | 条件 | 消息 | 退出码 | 来源 |
|---|---|---|---|---|
| 1 | 状态不在 REVIEWABLE_STATES 中（包括没有 state.json 时的 UNKNOWN） | `状态 <s> 不能记录验收结论` | 3 | :4263-4265 |
| 2 | --review 不是文件，或大小为 0 | `找不到复审报告：<path>` | 2 | :4267-4269 |
| 3 | 按 UTF-8 读取报告，第一个多行匹配 `^\s*Verdict:\s*([A-Z_]+)\s*$` 的值不存在或与 --verdict 不同。报告不是 UTF-8 时抛出未捕获的异常（推断） | `复审报告中的 'Verdict:' 行必须恰好是 <v>` | 2 | :4270-4273 |
| 4 | 某个 --waive 按第一个 `=` 拆开后，门禁不在 GATES 中（区分大小写），或理由去空白后为空；同一门禁重复时保留最后一条 | `--waive 格式应为 G2=原因` | 2 | :4274-4279 |

各结论对门禁的要求：

| 结论 | 门禁要求 | 附加要求 | 拒绝消息（退出码） | 来源 |
|---|---|---|---|---|
| PASS | 7 个门禁全部通过（G5 恒通过） | 不得带 --waive；--class 不要求，也不拒绝 | 有失败门禁时，先逐条打印 `GATE <Gx> <problem>`，再报 `PASS 被拒绝：门禁 <列表> 未通过。修正后重新验收，或按授权使用 ACCEPTED_WITH_EXCEPTION 并逐项豁免。`（1）。门禁全过但带豁免时报 `PASS 不接受豁免；有豁免时使用 ACCEPTED_WITH_EXCEPTION`（2）。先判门禁，再判豁免 | :4284-4292 |
| ACCEPTED_WITH_EXCEPTION | 每个失败门禁都要有 --waive；也可以豁免已通过的门禁 | 至少一项 --waive 且有 --decided-by，即使没有门禁失败 | `以下失败门禁没有豁免理由：<列表>`（2）；`ACCEPTED_WITH_EXCEPTION 需要至少一项 --waive 与 --decided-by`（2） | :4293-4298 |
| REVISE / BLOCKED / ESCALATE | 没有要求；门禁照样求值并写入记录 | 必须带 --class；--waive 不拒绝，照样记录 | `<v> 需要 --class（<全部分类>）`（2） | :4299-4300 |

通过校验后（:4301-4316）：

- 编号取 `_next_number(verdicts/)`，NN.md 和 NN.json 都计入编号。
- 先把复审报告复制为 `verdicts/NN.md`，再以 exclusive 写 `verdicts/NN.json`。字段为：number、verdict、failure_class、decided_by、waivers、human_minutes、note、review_source、review_sha256（副本的哈希）、candidate_tree、gates（完整的 problems 与 notes）、state_before、recorded_at。
- 然后 `set_state(<verdict>, verdict_no, failure_class)`，打印 `<v> 已记录（<path>）。`。
- 结论不是 PASS 且有失败门禁时，另打印 `未通过的门禁：…`。
- 退出码 0。
- REVIEWABLE_STATES 包含全部结论，所以已有结论的 attempt 仍可再次 verdict，编号递增。INTEGRATED、ABANDONED、SUPERSEDED、PREPARED、PREPARE_FAILED 以及运行中的状态都不能下结论（:80, :4264）。

### 5.8 结论之后的入口

`latest_verdict`（:4319-4324）把 `verdicts/*.json` 按 `int(文件名主干)` 排序，读取最后一个。branch、mark INTEGRATED、status 和 metrics（经 `_attempt_row` :4493）都用它，不看 state.json。

| 命令 | 对结论的要求 | 关键旧行为 | 来源 |
|---|---|---|---|
| branch | 最新结论为 PASS 或 AWE，或带 --rework 且为 REVISE（--rework 配 PASS 也可以）。否则报 `最新结论为 <v>：只有 PASS / ACCEPTED_WITH_EXCEPTION（或 --rework 时的 REVISE）可以建分支。`（3） | 见下方列表 | :4327-4392 |
| mark INTEGRATED | 最新结论为 PASS 或 AWE，并带 --ref；不检查当前状态 | 否则报 `只有通过验收的候选可以标记为 INTEGRATED；候选已并入后续提交（返工或规划器补齐）时用 SUPERSEDED`（3）；缺 --ref 时报错（2） | :4399-4404 |
| mark SUPERSEDED | 状态为 REVISE、ESCALATE、BLOCKED、NEEDS_REVIEW、TIMEOUT、CANCELLED、INFRA_FAILURE 之一，并带 --ref 和 --reason | 否则报 `SUPERSEDED 只用于已结束、尚未集成的 attempt（当前 <s>）`（2），或 `SUPERSEDED 需要 --ref（包含该候选的提交）与 --reason（由谁、怎样收尾）`（2） | :4405-4411 |
| cleanup | 与结论无关 | 见下方列表 | :4430-4482 |

branch 的关键旧行为：

- 不看状态，不重跑门禁，不调用 candidate_patch_ok，也不检查 worktree 漂移。
- 先核对 Git 身份，缺失时报错（3）。
- 再核对尾注：配置尾注或 --trailer 不合法时报错（2）；`--no-config-trailers` 跳过配置中的尾注。
- 树对象丢失时用 `tree_from_patch(meta.git_autocrlf)` 按补丁重建，结果不一致时报 `候选树对象已丢失，且补丁重建结果不一致`（3）。补丁文件也缺失时抛出未捕获的异常（推断）。
- 默认分支名为 `pi[-rework]/<task>-v<ver>-a<NNN>`。名字不合法时报错（2），分支已存在时报错（3）。
- 用 `commit-tree <tree> -p <base>` 建提交，说明以 LF 写入，含 `Pi-Dispatch-Attempt:`、`Pi-Executor:`、`Candidate-Tree:`、`Verdict:` 与尾注。

cleanup 的关键旧行为：

- 状态为 RUNNING 或 COLLECTING 时拒绝（3）；PREPARED 或 PREPARING 需要 --force（3）。
- worktree 已登记时，逐项收集 LOSS（见第 3 节）。有 LOSS 且没有 --force 时，报 `拒绝清理：以上内容不在已保存的候选中，删除 worktree 会丢失它们。先保存需要的内容；确认放弃请加 --force。`（3）。
- 目录存在、非空、但未登记为 worktree 时，报 `<path> 存在但不是本仓库登记的 worktree，拒绝删除`（3）。
- 只移除 checks 记录中 workspace_kept 为真的干净副本；mutate、baseline 保留的副本不清理。
- 不改变状态，只写 history 事件。

### 5.9 gates.md 与源码对照

| 主题 | gates.md（source_reported） | 源码（source_inspected） | 来源 |
|---|---|---|---|
| 名称 | 七个门禁都有中文名 | 只有编号 | gates.md:7-13；:79 |
| G0 | 哈希一致，基线提交存在 | 一致；另外 meta.json 不校验 | gates.md:7；:4160-4163 |
| G1 | 没有超时或取消；退出码 0；事件完整结束（agent_settled）；stopReason=stop；模型一致；思考级别（若有）一致；stderr 没有三类警告 | 以上都有。gates.md 没有明写的：缺少 run.json、缺少事件摘要、事件流为空/无法解析/最后一行截断、最终 assistant errorMessage、正文里的未执行工具调用 | gates.md:8；:4165-4176, :2338-2365 |
| G2 | 机械项：受保护、forbidden、不在允许集合、符号链接、子模块、依赖、未授权 HEAD。由复审者判断：执行位、敏感配置、可疑命令、worktree 外路径、主工作区变化 | 机械项一致；gates.md 没有提 invalid_path 和“缺少 scope.json”。G2 备注只有主工作区变化（diff_error 时没有）和 worktree 外路径；mode_changed、sensitive_file、dependency_manifest_changed、可疑命令都不进入 G2 | gates.md:9；:4188-4199 |
| G3 | DoD 引用的检查通过，引用 scope 的 DoD 没有越界 | 另外：没有有效检查记录时 G3 也失败；只看最近一次检查；review 引用被跳过；合同矛盾只作备注 | gates.md:10；:4183-4187, :4201-4236 |
| G4 | 针对当前候选、覆盖全部必要检查、全部通过；检查前有额外文件时 check 拒绝运行；检查不改候选、不产生新文件（缓存除外） | 一致。被拒绝那次写下的 aborted 记录若是最近一次，G3/G4 都会失败 | gates.md:11；:4002-4014, :4203-4227 |
| G6 | worktree 中的候选文件与记录一致；补丁存在、哈希不变、往返通过 | 另外：worktree 不存在时跳过比较；新增文件只作备注；只差行尾时有专门消息，但它要求整树只差行尾，另有新增文件时不给这条消息 | gates.md:13；:4237-4255 |
| PASS | G0–G6 全部通过，且复审没有发现需要修正的问题 | 工具只核对门禁和 Verdict 行；拒绝 --waive，不拒绝 --class | gates.md:36；:4284-4292 |
| AWE | 每个失败门禁都要 --waive，并提供 --decided-by | 另外：即使没有门禁失败，也至少要一项 --waive；可以豁免已通过的门禁 | gates.md:37；:4293-4298 |
| 状态 | PASS/AWE 之后只能到 INTEGRATED/ABANDONED；REVISE 等之后只能到 ABANDONED | 已有结论的 attempt 可以再次 verdict；另有 SUPERSEDED；mark INTEGRATED 只看最新结论 | gates.md:68-69；:80, :4399-4411 |

### 5.10 7.3 取证占位表（按源码填写）

| 旧门禁 | 真实名称与语义 | 原测试标识 | 平台与结果 | 本次状态 |
|---|---|---|---|---|
| G0 | 输入一致（名称来自 gates.md）：run_dir 中 plan.md、contract.json 的哈希与 meta 一致；base_sha 能解析为同一提交（:4160-4163） | 没有失败路径测试。正向：`test_happy` "PASS accepted" | 未运行 | 源码已读；测试 NOT_RUN |
| G1 | 执行完整：run.json 存在，未超时，未中断，exit_code=0，且 events.problems 为空（:4165-4176） | `test_events_and_thinking` "PASS refused on G1"、"ACCEPTED_WITH_EXCEPTION with waiver"、"missing JSON report does not block PASS"；`test_feedback_v12` "PASS is refused when the run ended on a textual tool call" | 未运行 | 源码已读；测试 NOT_RUN |
| G2 | 范围合规：scope.json 存在，且 violations 为空（:4188-4193） | `test_scope` "PASS refused on scope violation (G2)" | 未运行 | 源码已读；测试 NOT_RUN |
| G3 | 行为正确：有有效的检查记录；DoD 引用的 scope 与检查都通过（:4201-4205, :4228-4236） | 备注：`test_feedback_v12` "verdict prints the G3 note about undeclared ambiguity"。scope 证据失败会在 `test_scope` 的 PASS 被拒绝场景中触发（默认 D02 evidence=['scope']），但测试只断言 G2。检查引用失败没有测试 | 未运行 | 源码已读；测试 NOT_RUN |
| G4 | 回归检查：最近一次检查针对当前候选，覆盖全部必要项，没有改候选，没有意外新文件，必要项全部通过（:4203-4227） | `test_candidate_drift_and_artifacts` "PASS refused when checks created files (G4)" | 未运行 | 源码已读；测试 NOT_RUN |
| G5 | 质量复审：工具不判定，恒为通过（:4153-4154） | 没有专门测试 | 未运行 | 源码已读；测试 NOT_RUN |
| G6 | 可集成：worktree 中的候选文件没有被修改或删除；补丁完整且往返通过（:4237-4255） | 正向：`test_v22_netperf_feedback` "verdict PASS survives a later autocrlf change (snapshot pinned to the recorded value)"。“记录后修改”会在 `test_cleanup_protects_unsaved_work` 的 REVISE verdict 中触发，但没有断言。其余失败路径没有测试 | 未运行 | 源码已读；测试 NOT_RUN |

### 5.11 没有测试覆盖、需要裁定的旧行为

- **没有断言的失败路径**：
  - G0 全部；
  - G3 检查引用失败；
  - G4 的“不是针对当前候选”、`--only` 未覆盖、not_run/failed；
  - G6 的只差行尾消息、补丁被篡改、往返失败；
  - PASS 带 --waive；AWE 缺豁免或缺 --decided-by；REVISE 缺 --class。
- **只触发未断言**：G3 的 scope 证据失败、G6 的“记录后修改”。
- **临时 worktree 残留**：`prepare_fresh_workspace` 失败时不移除临时 worktree（:3480-3503, :3989-3995, :3616-3621）。cleanup 只清理 workspace_kept 的记录，清不掉它。
- **空 checks/NN**：`check --fresh` 补丁不完整时（:3987），或原地检查时 worktree 已不存在（:3999），会留下没有 checks.json 的 `checks/NN`。它成为“最近一次”后，G3/G4 报“没有有效的独立检查记录”。
- **G6 的两个边界**：worktree 不存在时只检查补丁（:4238）；只差行尾的判定会被新增文件破坏（:4243）。
- **行尾配置未固定**：主工作区指纹不固定 autocrlf（:893）；非规范的 autocrlf 值不被固定（:780-790）。
- **范围判定**：
  - 静态校验只比模式文本，运行时才拦住通配允许项中的受保护路径（:1516 对 :2459）；
  - 符号链接改回普通文件不会被标记（:2468-2477）；
  - symlink、submodule、mode_changed、sensitive_file、dependency_manifest_changed、local_commit 下的 head_moved 在仓库测试中都没有覆盖；
  - review_hints 也没有测试覆盖。
- **推断的未捕获异常**：
  - verdict 的复审报告不是 UTF-8；
  - branch 树对象丢失且补丁也缺失；
  - verdicts/ 中出现非数字文件名的 .json（:4323）；
  - Windows 上 collect --recover 改名时目标已存在。

### 未解决事项（第 5 节）

- 门禁名称只出现在 .agents/skills/review-pi/gates.md:7-13（source_reported），scripts/pi_dispatch.py:79 只有编号。新架构是否采用这些名称，需要规划端决定。
- G0 没有任何失败路径测试。meta.json 不做哈希校验（scripts/pi_dispatch.py:2659-2665）。contract.json 哈希不一致时，G3/G4 仍按被改动的合同判定。contract.json 缺失或不是合法 JSON 时，load_attempt（:2653-2656）抛出的异常不被 main（:4964-4971）捕获，这是推断，没有实测。需要裁定新架构是否校验 meta.json、G0 失败时是否继续使用该合同。
- G6：记录后修改候选这条路径会在 test_cleanup_protects_unsaved_work 的 REVISE verdict 中触发，但没有断言。只差行尾的专门消息、candidate.patch 被篡改、往返失败都没有测试。worktree 目录不存在时跳过漂移比较（:4238），意图未知。line_endings_only 比较整棵树（:858-861），worktree 另有新增文件时，只差 CRLF 的修改会被报成“候选文件在记录后被修改”；这在临时仓库中用同一条 git 命令核实过，但没有通过 pi_dispatch 端到端验证。
- G3：scope 证据失败会在 test_scope 中触发（默认 D02 evidence=['scope']），但测试只断言 G2。检查引用失败没有测试。G4 的“不是针对当前候选”、--only 覆盖不全、必要检查 not_run/failed 也没有测试。
- verdict 以下拒绝分支没有测试：PASS 带 --waive、AWE 缺某个失败门禁的豁免、AWE 缺 --decided-by、REVISE/BLOCKED/ESCALATE 缺 --class，以及“AWE 在没有门禁失败时也需要至少一项 --waive”。
- prepare_fresh_workspace 失败时，check（:3989-3995）和 mutate（:3616-3621）都不移除已登记的临时 worktree；cleanup 只移除 checks 记录中 workspace_kept 的副本（:4475-4480），也不清理 mutate、baseline 用 --keep-workspace 保留的副本。需要裁定新架构是否保留这一行为。
- check --fresh 在 candidate_patch_ok 为假时（:3987-3988），或原地检查时 worktree 已不存在时（:3999-4000），会留下没有 checks.json 的空 checks/NN。它成为“最近一次检查”后，G3/G4 报“没有有效的独立检查记录”，即使更早的检查有效。没有测试，意图未知。
- 行尾配置固定不完整：main_repo_fingerprint 的 git add 不固定 core.autocrlf（:893）；line_ending_args 对 yes/1/on 这类非规范值返回 []，不固定（:780-790）。运行期间配置变化是否造成误报，没有验证。
- test_v22_netperf_feedback 的 "branch rebuilds the tree with the recorded autocrlf"（tests/test_dispatch.py:1837）没有删除树对象，走不到 :4348 的重建分支。按补丁重建与 autocrlf 结合的路径实际没有测试。重建时不校验 patch_sha256。
- 范围判定：静态校验只拿模式文本匹配受保护路径（:1516），通配允许项要到运行时才由 evaluate_scope 拦下，需要裁定是否有意。符号链接改回普通文件（old 120000）既不算违规也不算警告（:2468-2477，已在内存中核实）。symlink、submodule、mode_changed、sensitive_file、dependency_manifest_changed、local_commit 下 head_moved 降为警告，在仓库测试中都没有覆盖。
- main_repo_changes 有 diff_error 时，G2 没有备注，只在 summary 的“复审需要关注”中提示（:4194-4196、:2945-2947）。需要裁定新架构是否在门禁中体现。
- review_hints（:2497-2512）在 tests/test_dispatch.py 中没有任何测试。
- 推断的未捕获异常，均未实测：verdict 的复审报告不是 UTF-8（:4270）；branch 树对象丢失且 candidate.patch 缺失（:4349 → :824）；verdicts/ 中出现非数字文件名的 .json（:4323）；Windows 上 collect --recover 改名时 .partial 已存在（:3436-3439）。
- G1 所依赖的 summarize_events 各 problem 的判定细节属于事件/预检区域，本节没有逐条核实。
- 本节所有测试标识都没有运行（NOT_RUN），平台与结果未取得。按任务约束，全量 tests/test_dispatch.py 由规划端在受控取证中运行。

## 6. 锁、预算、监督进程与 attempt 生命周期

> **纳入说明**：本节是区域章节原稿（已经对抗核对），正文照录，只统一了标题层级并修正排版。
> - 原稿编写时尚未取得 `bl-01t1-legacy-20260925` 的运行结果，文中“没有运行”“未运行”“NOT_RUN”“结果未知”等说法描述的是原稿编写时的状态；本次运行结果见本文第 0.3、2、9、10 节。
> - 正文中的“第 k 节”“见第 k 节”指本区域内的 6.k 小节，不是本文的第 k 节。
> - 标“实测”“探针”的内容是起草或核对者在会话临时目录中的一次性复现，没有归档为 fixture，证据等级仍按 source_inspected 记。

> **取证范围**
> - 源码：`scripts/pi_dispatch.py`（TOOL_VERSION 2.2.2，`scripts/pi_dispatch.py:48`）与 `tests/test_dispatch.py`。工作区中两个文件的 blob 与 HEAD `a4fa199b0e5bdc658215765ee7558b9fe6723940` 中的一致（`8e7df57c91fc…`、`b8fdd332566c…`，已用 `git hash-object` 与 `git rev-parse HEAD:<path>` 核对）。
> - 方式：只读源码与测试源码，**没有运行** `tests/test_dispatch.py`。“测试”只表示测试源码中有这条断言，不代表本次有运行结果。
> - 辅助探针：在会话临时目录中直接调用 `allocate_attempt`、`budget_usage`、`TaskLock`、`pid_alive`、`get_state`。环境为 Windows、Python 3.12.10；不调用 pi，不写仓库。探针只作旁证，不是正式取证。
> - 标“推导”的内容只来自阅读源码，没有测试，也没有探针。
> - 设计文档与技能文档的说法只在第 10 节登记，不当作源码事实。
>
> **01-D03 结论：旧实现的首个 attempt 编号是 1**（`scripts/pi_dispatch.py:2621`、`:2623`；`tests/test_dispatch.py:208-209`、`:273-277`）。只有 `prepare` 会让编号前进；恢复（`collect --recover`）和预检失败后再次 `run` 都沿用原编号。

### 6.1 attempt 编号

| 规则 | 旧行为 | 来源 |
|---|---|---|
| **首次编号** | **1**。按 `number = max(existing, default=0) + 1` 计算：<br>- 空任务目录得到 `attempt-001`，attempt_id 后缀为 `.a001`<br>- 工具从不生成 0；即使手工放入 `attempt-000`，下一次仍得到 1 | `scripts/pi_dispatch.py:2619-2623` |
| 目录名 | 正则 `^attempt-(?P<n>\d{3,})$`，按整数 n 取值：<br>- 生成格式为 `attempt-%03d`；≥1000 时为 `attempt-1000`，仍匹配正则<br>- 不足 3 位的目录（如 `attempt-01`）被忽略<br>- 多补零的目录（如 `attempt-0007`）按 7 参与取最大值 | `:62`、`:2619-2623`；探针 |
| 列举与排序 | `task_attempts` 只收 `.agent/runs/<task_id>/` 下匹配正则的目录，按整数 n 升序 | `:2558-2563`、`:952` |
| 派生标识 | 各标识的格式：<br>- attempt_id：`<task>.v<ver>.a%03d`<br>- `meta.attempt_no`：整数<br>- worktree 前缀：`<仓库名前16字符>-<task前24字符>-a%03d-`<br>- 默认分支：`pi/<task>-v<ver>-a%03d`；`--rework` 时为 `pi-rework/…`；`--name` 可以覆盖 | `:3193`、`:3204`、`:3198`、`:4353-4354` |
| 作用域 | `.agent/runs/<task_id>/`，跨 plan_version 连续，新版本合同不从 1 重新开始 | `:2617` |
| 递增条件 | 只有 `prepare` 分配编号，而且要先依次通过以下检查：<br>1. 合同校验，失败退出码 2<br>2. `.agent/runs/` 已被 Git 忽略，否则退出码 3<br>3. 执行器核对：仅当 JSON 合同显式写了 provider 与 model 时进行；env 冲突、模型或思考级别无效时退出码 2，不在 allowed_executors 或思考级别不符时退出码 3<br>4. 预算预检，失败退出码 3<br>5. 创建 worktree_root | `:3172-3192`、`:2668-2699` |
| 不释放、不回填 | 编号分配后目录一直保留，以下情况都不释放：<br>- PREPARE_FAILED<br>- 预检失败<br>- 从未 run<br>- run 时 BUDGET_EXCEEDED<br>编号取 max+1，不回填空缺 | `:2619-2621` |
| 并发撞名 | prepare 不取锁。mkdir 遇到 `FileExistsError` 时编号加一重试，最多 1000 次；全部失败时报“无法分配 attempt 目录”，退出码 3 | `:2622-2629` |
| 恢复复用 | 以下操作都在原目录上进行，**不分配新编号**：<br>- `collect --recover`<br>- 预检失败后再次 `run`（提示“预检失败：attempt 保持 PREPARED，未计入尝试次数。修正环境后可再次 run。”） | `:3413`、`:3440`、`:3285` |
| 重试必须重新 prepare | 状态不是 PREPARED，或者 `claim` 已存在时，run 报“attempt 状态为 %s%s，只能运行未领取的 PREPARED attempt；返工请重新 prepare。”；已领取时在状态后插入“（已领取）”；退出码 3 | `:3255-3257` |
| 其他编号基数 | `verdicts/NN`、`checks/NN`、`mutations/NN` 也从 01 开始：`_next_number` 在没有记录时返回 1 | `:3453-3455`、`:4303-4304`、`:3612-3613` |
| 测试佐证 | 测试源码中与编号有关的断言：<br>- `rd(repo, n=1)` 指向 attempt-001<br>- test_happy 断言分支为 `pi/normalize-query-v1-a001`，主题行为 “normalize-query: Pi 候选 v1 attempt 001”<br>- 第二次 prepare 得到 attempt-002 | `tests/test_dispatch.py:208-209`、`:273-277`、`:489-492`、`:507-508` |
| 探针 | 调用 `allocate_attempt` 的结果：<br>- 空目录 → 1<br>- 已有 000 → 1<br>- 已有 001、005 → 6<br>- 已有 999 → `attempt-1000`<br>- 已有 01、0007 → 8 | 探针 |

### 6.2 任务锁 TaskLock

| 项目 | 旧行为 | 来源 |
|---|---|---|
| 位置 | 目录 `.agent/runs/<task_id>/.task.lock`，父目录不存在时先创建；名字不匹配 attempt 正则，不会被当成 attempt | `scripts/pi_dispatch.py:2587`、`:2592` |
| 获取 | 用 `mkdir` 原子创建；成功后以独占模式写 `owner.json`：`{"pid": 调度器 pid, "at": UTC}` | `:2596-2598`、`:364-366` |
| 等待 | 每 0.2s 重试一次，最多 30s | `:2586`、`:2593`、`:2607-2610` |
| 被占用时 | DispatchError：“任务锁被占用：<路径>（另一个 run 正在领取；如确认无人使用可删除该目录）”，退出码 3。<br>不写 history；attempt 保持 PREPARED，未领取 | `:2607-2609`、`:307`；探针（wait=0.5s 时约 0.6s 后拒绝） |
| 过期判定 | 只看锁目录的 mtime：`time.time() - st_mtime > 300` 时视为持有者已崩溃，rmtree 后重试；stat 失败时按 age=0 处理 | `:2599-2606` |
| 归属 | `owner.json` 只写不读（全文件只在 2597 出现），不检查 pid 是否存活。<br>持有者已死、但锁不足 300s 时，其他 run 等满 30s 后仍失败。<br>探针：owner pid=999999 的新锁被拒绝；mtime 改为 400s 前的锁被接管，owner 改写为当前 pid | `:2597`；探针 |
| 释放 | `__exit__` 无条件 `rmtree(ignore_errors=True)`，不核对归属。<br>顺序模拟探针：A 持锁 → mtime 改为 400s 前 → B 接管 → A 退出时删除了 B 的锁目录。没有正式测试 | `:2612-2613`；探针 |
| 异常残留 | mkdir 成功后，写 owner.json 时抛出的异常分两种：<br>- 不是 `FileExistsError`：直接上抛，`__exit__` 不执行，锁目录残留到 300s 后过期<br>- 是 `FileExistsError`：被当作“锁已存在”，继续等待（推导） | `:2595-2599` |
| 使用范围 | 全文件只在 `cmd_run` 的领取临界区使用一次。prepare、collect、mark、verdict、cleanup 都不取锁 | `:3300` |
| 临界区内容 | 依次执行：<br>1. `budget_usage(exclude=本 attempt)`，复核次数<br>2. 检查剩余墙钟 ≥60s<br>3. 计算本轮时限<br>4. `mkdir claim/`<br>5. 独占写 `claim/reservation.json`：`{"timeout_seconds", "pid"（调度器）, "at"}`<br>离开临界区后才写 executor.json、instruction.md、ignored-before.json、run-started.json，并设为 RUNNING | `:3300-3315`、`:3319-3326` |
| attempt 级互斥 | `claim/` 已存在时报“该 attempt 已被领取，不能重复运行。”，退出码 3。<br>判断方式不一致：run 入口用 `claim.exists()`，budget_usage、collect、status 用 `is_dir()` | `:3310-3313`、`:3255`、`:2572`、`:3416`、`:4498` |

### 6.3 预算

| 项目 | 旧行为 | 来源 |
|---|---|---|
| 默认值 | max_attempts_total=2，max_wall_seconds_per_attempt=1200，max_wall_seconds_total=2400，cost_budget=None | `scripts/pi_dispatch.py:1197-1198` |
| 默认值的实际效果 | JSON 缺省时会补上默认值，但 Markdown Budget 的三项必须与 JSON 逐项相等，所以 Markdown 仍要写出同样的数。derive-json 要求 Markdown 三项齐全 | `:1618-1622`、`:1362-1364` |
| 校验 | 各字段的要求：<br>- attempts：1..20 的 int，不接受 bool<br>- per_attempt：60..86400 的 int<br>- total：int，且不小于 per_attempt；per_attempt 本身无效时只检查是否为 int<br>- cost_budget：null，或 `{amount: ≥0 的数值, currency: 字符串}` | `:1565-1580` |
| cost_budget | 只校验，不参与核算与拦截；全文件只在 1198、1396、1576-1580 出现 | 同左 |
| 计次 | 只数存在 `claim/` 目录的 attempt，覆盖同一 task 的全部 plan_version | `:2566-2573` |
| 计时 | 对每个已领取的 attempt：<br>- run.json 可读且 `wall_seconds` 不为 None 时，取实际值<br>- 否则取 `reservation.timeout_seconds`，缺失时按 0<br>合计结果保留 3 位小数 | `:2574-2580` |
| 限额来源 | 两个入口读取的合同不同：<br>- prepare：正在准备的 `.agent/plans/<key>` 合同<br>- run：attempt 目录中复制的 `contract.json`（`load_attempt`）<br>计次跨所有版本，限额按各自的合同版本 | `:3165`、`:3182`、`:2653-2656`、`:3272` |
| prepare 预检（锁外） | 两种拒绝，都是退出码 3，不创建 attempt：<br>- 次数达上限：“BUDGET_EXCEEDED：任务 %s 已运行 %d 次，达到 max_attempts_total=%d。”<br>- 累计时长达上限：“BUDGET_EXCEEDED：累计运行 %.0fs，达到 max_wall_seconds_total=%d。” | `:3183-3189` |
| run 锁外预检 | 位于 G0 与执行器核对之后、Pi 预检之前。次数达上限时报“BUDGET_EXCEEDED：已达到 max_attempts_total=%d。” | `:3272-3275` |
| run 锁内复核 | 次数复核的报错文本同上；剩余墙钟不足 60s 时报“BUDGET_EXCEEDED：剩余墙钟预算 %.0fs，不足 60s。” | `:3301-3306` |
| 本轮时限 | `int(min(per_attempt, total-used))`。<br>`--timeout N` 只能收紧：N 非 0 时取 `max(1, min(timeout, N))`，N 为负数时得到 1，N=0 时不生效 | `:3307-3309`、`:4877` |
| 实际用时可超预留 | wall_seconds 从启动计到回收结束；超时后还包括 grace 与最多两次 30s 等待。所以 TIMEOUT 的 attempt 可能超出 reservation，累计值也可能超过 total（推导） | `:678`、`:696`、`:715`、`:720` |
| 两个时长门槛不同 | prepare 只在 used ≥ total 时拒绝；run 要求 total-used ≥60。剩余 1..59s 时，prepare 成功而 run 拒绝 | `:3187`、`:3305` |
| 超额 PREPARED | prepare 只数已领取的 attempt，而且不取锁，所以可以准备出多于剩余额度的 PREPARED，由 run 拦截 | `:3183`、`:3301-3303` |
| 竞争结果 | 争最后一次额度时，锁保证只有一个 attempt 能 `mkdir claim`：<br>- 落败方的拒绝点取决于时序：对方先领取时在锁外预检被拒，否则在锁内复核被拒<br>- 两处的文本都是“BUDGET_EXCEEDED：已达到 max_attempts_total=%d。”，退出码 3<br>- 落败方保持 PREPARED、没有 claim，worktree 保留 | `:3273-3275`、`:3301-3303`；`tests/test_dispatch.py:330-343` |
| 拒绝不留痕 | BUDGET_EXCEEDED 与锁被占用都不写 history | `:3275`、`:3303`、`:3306` |
| 探针 | 构造五个 attempt，调用 `budget_usage` 的结果：<br>- 输入：reservation 600；run.json 的 wall 为 None、reservation 300；run.json 12.5；一个已领取但没有 reservation；一个未领取<br>- 结果：attempts_started=4，wall=912.5<br>- 排除第一个后：3 次，312.5 | 探针 |

### 6.4 监督进程 run_supervised

| 项目 | 旧行为 | 来源 |
|---|---|---|
| stdin | 固定为 `DEVNULL` | `scripts/pi_dispatch.py:659` |
| Windows 隔离 | 步骤：<br>1. 创建 Job Object，设 `KILL_ON_JOB_CLOSE`（0x2000）<br>2. 以 `CREATE_NEW_PROCESS_GROUP\|CREATE_SUSPENDED` 创建进程<br>3. 先 `AssignProcessToJobObject`，再 `NtResumeProcess`；失败时 `TerminateProcess`<br>kill_method=`job-object` | `:505`、`:669`、`:512-533`、`:670` |
| Windows 启动失败 | 两种情况：<br>- 建不成 Job：spawn_error 为“无法创建 Windows Job Object，拒绝在没有进程树监督的情况下运行：…”。不启动进程，在安装信号处理器之前返回，wall=0.0，kill_method=None<br>- 加入 Job 失败：spawn_error 为“进程未能加入 Job Object，已在启动前终止”，不写 pid.txt | `:663-667`、`:686-688` |
| POSIX 隔离 | `start_new_session=True`；Linux 另在 preexec 中设 `PR_SET_PDEATHSIG=SIGTERM`，失败时静默；kill_method=`process-group` | `:672-675`、`:551-558` |
| Popen 失败 | spawn_error 为 `"<类型>: <消息>"` | `:681-684` |
| pid 记录 | 进程加入 Job 并恢复运行后才调用 `on_spawn`，以独占模式写 `pid.txt`，内容为 Pi 顶层进程的 pid | `:689-690`、`:3336-3337` |
| 超时 | 按单调时钟计算 deadline，每次最多 wait 1s；到期时置 `timed_out=True`，并用 grace 终止进程树 | `:678`、`:691-699` |
| 取消 | 为 SIGINT、SIGTERM、SIGHUP、SIGBREAK 中平台存在的信号安装处理器，收到时抛 `_Interrupted`；随后置 `interrupted=True`，并终止进程树 | `:571-585`、`:676`、`:703-706` |
| 其他异常 | 用 `min(grace, 5)` 终止进程树后重新抛出 | `:707-710` |
| 终止顺序 | Windows：CTRL_BREAK → 等 grace → TerminateJobObject（没有 Job 时用 `taskkill /T /F`）→ 再等 30s。<br>POSIX：killpg SIGTERM → 等 grace → killpg SIGKILL → 再等 30s | `:596-626` |
| grace | 取 `dispatch.config.json` 的 `kill_grace_seconds`，默认 15 | `:3334` |
| 收尾（finally） | 依次：<br>1. 恢复原信号处理器<br>2. wait 30s<br>3. `_reap_stragglers`<br>4. 记录 exit_code 与 wall_seconds<br>5. 关闭 Job 句柄 | `:711-722` |
| 残留回收 | Windows 看 Job 的 ActiveProcesses：>0 时终止并返回 True；=0 返回 False；查询失败或没有 Job 返回 None。<br>POSIX 用 `killpg(pid,0)` 探测：进程组仍在时 SIGKILL 并返回 True；ProcessLookupError 返回 False；PermissionError 返回 None。<br>结果写入 `stray_processes`，summary.md 中显示为“残留进程” | `:629-646`、`:718`、`:2865-2867` |
| 返回字段 | exit_code、timed_out、interrupted、spawn_error、wall_seconds、stray_processes、kill_method、pid | `:656-658` |

### 6.5 超时、取消、调度器被杀：结果与恢复入口

| 场景 | 记录 | 最终状态 | 退出码 | 恢复或收尾入口 | 来源 | 测试 |
|---|---|---|---|---|---|---|
| 超时 | `run.json.timed_out=true` | TIMEOUT；候选缺失或收集出错时为 INFRA_FAILURE | run：1 | verdict（G1 记“运行超时”，不能 PASS，可用 ACCEPTED_WITH_EXCEPTION 加豁免）；也可标 SUPERSEDED 或 ABANDONED | `scripts/pi_dispatch.py:3395-3398`、`:4169-4170`、`:4293-4298` | `test_timeout` |
| run_supervised 期间收到信号 | `interrupted=true` | CANCELLED（判定顺序在 TIMEOUT 之后） | run：1 | 同上；G1 记“运行被取消或调度器中断” | `:703-706`、`:3399-3400`、`:4171-4172` | 无直接测试 |
| 终止进程树期间再收到信号 | 没有 run.json | 停在 RUNNING | 1（`_Interrupted` 未被 main 捕获，打印 traceback；推导） | `collect --recover` | `:703-706`、`:4964-4971` | 无 |
| Job 创建或加入失败、Popen 失败 | `run.json.spawn_error` | INFRA_FAILURE | run：1 | verdict | `:663-688`、`:3395-3396` | 无 |
| 领取后、启动前异常（3319-3326） | run.json：`spawn_error="领取后、启动前失败：…"`，wall 为 0.0（非独占写） | INFRA_FAILURE | 重新抛出：DispatchError→3，KeyboardInterrupt→130，其他→traceback、1 | verdict | `:3327-3332` | 无 |
| setup 期间 Ctrl+C（prepare） | setup 项记为“被取消” | PREPARE_FAILED | prepare：1 | 重新 prepare；mark ABANDONED | `:3087`、`:3097-3098`、`:3225-3229` | 无 |
| prepare 其他位置（3194-3219）异常或 Ctrl+C | `reason="<类型>: <消息>"` | PREPARE_FAILED | DispatchError/OSError→3；KeyboardInterrupt→130 | 同上 | `:3220-3224` | 无 |
| run 领取前 Ctrl+C | 无 | 保持 PREPARED | 130 | 再次 run | `:4969-4971` | 无 |
| run 在 3311-3318 之间中断 | 有 `claim/`，可能没有 reservation | PREPARED（已领取） | 130 | `collect --recover` → INFRA_FAILURE | `:3311-3315`、`:3417`、`:3432` | 无 |
| run 在 RUNNING 之后、Pi 启动前，或 run_supervised 返回之后收到 Ctrl+C | 可能已有 run.json | 停在 RUNNING 或 COLLECTING | 130 | `collect --recover` | `:3326-3345` | 无 |
| 调度器被强制结束（Windows） | Job 句柄关闭时，KILL_ON_JOB_CLOSE 回收 Pi 及其子孙进程 | 停在死亡时的状态，通常是 RUNNING | — | `collect --recover` → CANCELLED 或 INFRA_FAILURE | `:505` | `test_dispatcher_killed` |
| 调度器被强制结束（Linux/macOS） | Linux 的 PDEATHSIG 只让 Pi 收到 SIGTERM，普通孙进程可能残留；macOS 没有父进程死亡通知 | 同上 | — | 先确认进程已退出，再 `collect --recover` | `:551-558`、`tests/test_dispatch.py:465-470` | `test_dispatcher_killed`（平台条件） |
| 领取后调度器立即退出 | 有 `claim/`，状态 PREPARED，没有 run-started.json | 恢复后为 INFRA_FAILURE（“领取后调度器退出，未启动 Pi”） | collect：0 | `collect --recover` | `:3417`、`:3432` | `test_stuck_states` |
| prepare 中途进程崩溃 | 停在 PREPARING；若死在 3213 之前，则没有 state.json（UNKNOWN） | — | — | `mark … ABANDONED --force`；cleanup 需要 `--force` | `:3212-3213`、`:4412-4419`、`:4437` | `test_stuck_states` |

`collect --recover` 细则：

| 项目 | 旧行为 | 来源 |
|---|---|---|
| 前提 | 满足以下两条，否则报“collect 只用于调度器异常退出后的恢复：需要状态 RUNNING/COLLECTING（或已领取的 PREPARED）且指定 --recover（当前 %s）。”，退出码 2：<br>- 状态为 RUNNING 或 COLLECTING，或者是已领取的 PREPARED（`claim` 为目录）<br>- 带 `--recover` | `scripts/pi_dispatch.py:3416-3420` |
| 进程检查 | `pid.txt` 中的 pid 经 `pid_alive` 判为真时，报“记录的 Pi 进程 %s 可能仍在运行；确认终止后再恢复。”，退出码 3 | `:3421-3425` |
| pid_alive | 空值或 0 返回 None。<br>Windows：`tasklist /FI "PID eq N" /NH`（超时 20s）；命令失败、超时（124）或找不到命令（127）都返回 None，否则看输出分词中是否有该 pid。<br>POSIX：`os.kill(pid,0)` 成功返回 True；ProcessLookupError 返回 False；PermissionError 返回 True；其他异常不捕获，直接上抛。<br>调用方只在返回真值时拒绝 | `:726-740`、`:393-405`；探针（Windows：自身 pid→True，999999→False） |
| run.json 缺失 | 合成一份，以独占模式写入：<br>- 继承 run-started.json 的字段<br>- `exit_code=None, timed_out=False, interrupted=True, recovered=True, wall_seconds=None`<br>- 有 run-started 时 `spawn_error=None`，否则为“领取后调度器退出，未启动 Pi”<br>- `expects_agent_settled` 在 run-started 中有这个键时取其值，否则按 `preflight/pi-version.txt` 推断 | `:3426-3434` |
| run.json 已存在 | 原样沿用其中全部字段（包括 timed_out、interrupted、exit_code、wall_seconds）。以下时机都会出现这种情况：<br>- 调度器死在 3343 写 run.json 与 3344 设 COLLECTING 之间，此时状态仍为 RUNNING<br>- 调度器死在 COLLECTING 期间 | `:3343-3344`、`:3426` |
| 旧证据处理 | 已存在的 candidate.json、changes.json、scope.json、candidate.patch 改名为 `*.partial`（candidate.patch 之后要以 `xb` 独占重写），然后重跑 collect；不经过 COLLECTING | `:3436-3440`、`:2520` |
| 结束 | `log_event "recovered_collection"`，打印“<状态>（恢复收集；事件可能不完整）”，一律返回 0 | `:3441-3443` |
| 结果与门禁 | 合成的 run.json：<br>- Pi 未启动时为 INFRA_FAILURE；已启动时通常为 CANCELLED，候选缺失或收集出错时为 INFRA_FAILURE<br>- 不会得到 TIMEOUT<br>- G1 必然失败（“运行被取消或调度器中断”“Pi 退出码为 None”），PASS 被拒<br>沿用已有 run.json 时按原记录判定：可能是 NEEDS_REVIEW，G1 也可能通过 | `:3395-3404`、`:4169-4174` |
| 预算影响 | claim 仍在，计 1 次。合成的 run.json 按预留时限计时；已有 run.json 按其中的实际值计时 | `:2572-2579` |

### 6.6 旧 attempt 状态枚举（17 个，另有读取时的伪状态 UNKNOWN）

| 状态 | 写入位置 | REVIEWABLE | wait 视为已结束（TERMINAL） | 待集成（PENDING_INTEGRATION） | wait 视为进行中（WAIT_ACTIVE） |
|---|---|---|---|---|---|
| PREPARING | `scripts/pi_dispatch.py:3213` | | | ✓ | ✓ |
| PREPARED | `:3234` | | （最多再等 min(60, --timeout) 秒，之后退出码 3） | ✓ | |
| PREPARE_FAILED | `:3221`、`:3226`、`:3231` | | ✓ | | |
| RUNNING | `:3326` | | | ✓ | ✓ |
| COLLECTING | `:3344` | | | ✓ | ✓ |
| NEEDS_REVIEW | `:3404`（经 `:3405`） | ✓ | ✓ | ✓ | |
| TIMEOUT | `:3398` | ✓ | ✓ | | |
| CANCELLED | `:3400` | ✓ | ✓ | | |
| INFRA_FAILURE | `:3331`、`:3396`、`:3402` | ✓ | ✓ | | |
| PASS / ACCEPTED_WITH_EXCEPTION | `:4312` | ✓ | ✓ | ✓ | |
| REVISE | `:4312` | ✓ | ✓ | ✓ | |
| BLOCKED / ESCALATE | `:4312` | ✓ | ✓ | | |
| INTEGRATED / ABANDONED / SUPERSEDED | `:4420` | | ✓ | | |
| UNKNOWN（伪状态） | `:2555`：state.json 缺失、JSON 损坏或没有 state 字段（探针已确认三种情况） | | ✗（wait 退出码 1） | | |

四个集合的定义：

| 集合 | 来源 |
|---|---|
| REVIEWABLE_STATES | `scripts/pi_dispatch.py:80` |
| TERMINAL_STATES | `:81-82` |
| PENDING_INTEGRATION_STATES | `:3112-3113` |
| WAIT_ACTIVE_STATES | `:3914` |

持久化：
- `set_state` 先向 `history.jsonl` 追加 `{"state","at",...}`（UTF-8、LF），再用 `state.json.tmp` + `os.replace` 原子覆盖 `state.json`。
- `log_event` 只追加 `{"event","at",...}`，不改变状态。事件名共 7 个：run_refused、preflight_failed、recovered_collection、checks、mutations、branch_created、cleanup。
- 没有集中的转换表，各命令自己检查前置状态。

来源：`scripts/pi_dispatch.py:2539-2555`、`:351-361`。

### 6.7 状态转换（源码实际允许）

| 从 | 到 | 触发与条件 | 来源 |
|---|---|---|---|
| （新目录，没有 state） | PREPARING | prepare 写完 meta.json 之后。在此之前读到的是 UNKNOWN | `scripts/pi_dispatch.py:3212-3213` |
| PREPARING | PREPARED / PREPARE_FAILED | 分三种情况：<br>- 一切正常 → PREPARED，退出码 0<br>- 异常 → PREPARE_FAILED，退出码 3 或 130<br>- setup 失败（含被取消）或 setup 后有变更 → PREPARE_FAILED，退出码 1 | `:3220-3234` |
| PREPARED | PREPARED（不变） | 以下情况只拒绝，不改状态：<br>- 执行器核对失败（退出码 2 或 3，不写 history）<br>- G0 拒绝（`run_refused`，退出码 3）<br>- 预检失败（`preflight_failed`，退出码 3）<br>- BUDGET_EXCEEDED（退出码 3）<br>- 锁被占用（退出码 3）<br>- 领取前 Ctrl+C（130） | `:3258-3285`、`:3300-3306` |
| PREPARED（已领取） | RUNNING / INFRA_FAILURE | 启动前准备成功 → RUNNING；准备过程中任一异常 → INFRA_FAILURE | `:3319-3332` |
| RUNNING | COLLECTING | run_supervised 返回、写入 run.json 之后 | `:3341-3344` |
| COLLECTING | INFRA_FAILURE / TIMEOUT / CANCELLED / NEEDS_REVIEW | 按顺序判定：<br>1. spawn_error、收集错误（record_candidate、diff、scope 抛 DispatchError 或 OSError）或没有候选树 → INFRA_FAILURE<br>2. timed_out → TIMEOUT<br>3. interrupted → CANCELLED<br>4. 没有助手消息 → INFRA_FAILURE<br>5. 其余 → NEEDS_REVIEW（不看 Pi 退出码与 events.ok）<br>这一阶段其他位置抛出的异常会让状态停在 COLLECTING（推导） | `:3364-3405` |
| RUNNING / COLLECTING / 已领取的 PREPARED | 同上四种 | `collect --recover`（不经过 COLLECTING） | `:3417`、`:3440` |
| REVIEWABLE 中任一状态 | 五种 verdict 之一 | `verdict`，可以重复记录，verdicts/NN 递增，记录带 `state_before`。<br>PASS 在门禁失败时被拒，退出码 1。其他状态报“状态 %s 不能记录验收结论”，退出码 3 | `:4263-4265`、`:4284-4312` |
| 任意状态 | INTEGRATED | 最新 verdict 为 PASS 或 ACCEPTED_WITH_EXCEPTION（否则退出码 3），并带 `--ref`（否则退出码 2）；不检查当前状态 | `:4399-4404` |
| REVISE、ESCALATE、BLOCKED、NEEDS_REVIEW、TIMEOUT、CANCELLED、INFRA_FAILURE | SUPERSEDED | 须带 `--ref` 与 `--reason`。当前状态不在列表中时报“SUPERSEDED 只用于已结束、尚未集成的 attempt（当前 %s）”，退出码 2 | `:4405-4411` |
| RUNNING / COLLECTING / PREPARING | ABANDONED | 须加 `--force`，否则报“attempt 处于 %s；如果确认调度器已退出，可加 --force 放弃”；pid.txt 记录的进程存活时报“记录的 Pi 进程 %s 仍在运行，不能放弃”；两者都是退出码 3 | `:4412-4419` |
| 其他任何状态（含 PREPARED、PREPARE_FAILED、PASS、INTEGRATED、UNKNOWN） | ABANDONED | 直接允许，不需要 `--force`。新记录带 ref、reason、previous_state；不删 claim，已领取的仍计入预算 | `:4412`、`:4420` |

各命令的状态要求：

| 命令 | 状态要求 | 来源 |
|---|---|---|
| cleanup | 不改变状态，只追加 `cleanup` 事件：<br>- 拒绝 RUNNING、COLLECTING<br>- PREPARED、PREPARING 需要 `--force`<br>- 没有候选记录且 worktree 已登记时出现 LOSS，也需要 `--force` | `:4435-4467` |
| check | 需要 REVIEWABLE 状态，否则报“状态 %s 不能运行验收检查” | `:3961-3963` |
| mutate | 需要 REVIEWABLE 状态，另外允许 INTEGRATED | `:3596` |

### 6.8 入口定位与退出码

| 项目 | 旧行为 | 来源 |
|---|---|---|
| attempt 定位 | `resolve_run_dir` 接受以下形式：<br>- attempt 路径<br>- `task-id/attempt-NNN`<br>- `task-id`：取编号最大的目录，不看版本，也不看 meta.json<br>- `task-id.vN`：取该版本编号最大的目录<br>目录必须位于 `.agent/runs` 下，否则退出码 2；找不到时报“找不到 attempt：%s”，退出码 2。<br>`collect --recover <task-id>` 会定位到最新的 attempt，未必是卡住的那个（推导） | `scripts/pi_dispatch.py:2632-2650` |
| 输入读取 | `load_attempt` 读取 attempt 目录中的 meta.json 与 contract.json 副本 | `:2653-2656` |
| 退出码常量 | EXIT_OK=0、EXIT_FAIL=1、EXIT_USAGE=2、EXIT_BLOCKED=3、EXIT_DRIFT=4 | `:53` |
| run 的返回 | 只有最终状态为 NEEDS_REVIEW 且 `events-summary.ok` 为真时返回 0。其余返回 1，包括：<br>- TIMEOUT<br>- CANCELLED<br>- INFRA_FAILURE<br>- NEEDS_REVIEW 但事件有问题 | `:3349` |
| main 的异常处理 | 按异常类型区分：<br>- DispatchError：返回其 code，默认 3<br>- KeyboardInterrupt：打印“已取消。”，返回 130<br>- 其他异常（OSError、`_Interrupted` 等）：不捕获，Python 打印 traceback，退出码 1 | `:307`、`:4964-4971` |
| collect --recover | 恢复成功后一律返回 0 | `:3443` |
| 退出码 3 的歧义 | 同时表示阻断错误和 wait 的“仍在运行”，要按入口区分 | `:3937`、`:3942` |

### 6.9 回归测试映射（测试源码，未运行）

| 测试 | 断言名 | 覆盖的条目 |
|---|---|---|
| `test_budget_race`（`tests/test_dispatch.py:330-343`） | exactly one attempt claims the last budget slot（只断言恰好一个 claim、输出含 BUDGET_EXCEEDED，不断言落败方的状态与退出码） | LB-LIFE-007、010、012 |
| `test_timeout`（`:425-440`） | timeout -> TIMEOUT state；timeout enforced quickly (<40s)；grandchild process killed (%s) | LB-LIFE-016、018 |
| `test_dispatcher_killed`（`:443-476`） | Job Object reaps pi and grandchild；PDEATHSIG stops pi；mark ABANDONED on RUNNING requires --force；recover after dispatcher death | LB-LIFE-021、022、023、025 |
| `test_stuck_states`（`:479-492`） | claimed PREPARED attempt cannot run again；claimed-but-not-started attempt recovers as INFRA_FAILURE；PREPARING can be abandoned with --force | LB-LIFE-004、022、025、028 |
| `test_preflight_and_budget`（`:495-517`） | model not listed -> preflight fail, stays PREPARED；auth not ready -> preflight fail；env/contract model conflict refused（执行器核对，退出码 2）；run after fixing env；budget: 3rd attempt refused | LB-LIFE-003、004、009、010、013 |
| `test_cleanup_protects_unsaved_work`（`:315-327`） | cleanup refuses when candidate files were modified；cleanup --force removes and logs discarded content | LB-LIFE-030 |
| `test_happy`（`:241-284`） | claim records reserved timeout（测试合同 per_attempt=600，`:121-122`）；run ok -> NEEDS_REVIEW；branch tree == candidate tree；branch subject without a title；mark integrated | LB-LIFE-001、002、011、019、025 |
| `test_feedback_v12`（`:1051-1084`） | overlap warning names the latest pending attempt only；no overlap warning once the latest attempt is integrated；a superseded attempt is not pending integration；SUPERSEDED needs --ref and --reason；REVISE attempt can be marked SUPERSEDED；SUPERSEDED is refused for an attempt that never ran | LB-LIFE-025、031 |
| `test_v2_planner_adapters`（`:1329-1341`） | wait returns at once for a finished attempt；wait times out on a running attempt with exit code 3；wait reports an attempt that never started | LB-LIFE-029 |

以下分支没有测试：
- 锁被占用的报错与 30s 等待；
- 过期接管；
- 同一 attempt 并发 run 时的“已被领取”；
- 剩余墙钟不足 60s；
- 领取后、启动前异常；
- Job 创建或加入失败；
- 信号直接产生的 CANCELLED；
- run.json 已存在时的恢复；
- 状态为 UNKNOWN 时 wait 退出码 1；
- 重新记录 verdict；
- 非 REVIEWABLE 状态下记录 verdict 被拒。

### 6.10 与文档的差异（文档说法，不是源码事实）

| 文档 | 文档说法 | 源码实际 |
|---|---|---|
| `.agents/skills/review-pi/gates.md:60-69` | 没有 SUPERSEDED；PASS 之后只能到 INTEGRATED 或 ABANDONED；REVISE、BLOCKED、ESCALATE 之后只能到 ABANDONED | 源码还允许：<br>- REVIEWABLE 状态下重新记录任意 verdict（`scripts/pi_dispatch.py:4264`）<br>- 七种状态转为 SUPERSEDED（`:4408`）<br>- 任意非运行中状态直接转为 ABANDONED（`:4412`） |
| `.agents/skills/dispatch-pi/troubleshooting.md:33` | 锁“超过 5 分钟未释放会被视为过期” | 一致：300s，`scripts/pi_dispatch.py:2586`、`:2604` |
| `.agents/skills/dispatch-pi/SKILL.md:87-91` | 恢复步骤：先 `collect --recover`；PREPARING 用 `mark ABANDONED --force` | 一致 |
| `.agents/skills/dispatch-pi/SKILL.md:90` | 恢复的证据“不能直接作为 PASS 依据” | 只在合成 run.json 时由 G1 强制；沿用已有 run.json 时不强制（`scripts/pi_dispatch.py:3426`、`:4167-4174`） |
| 设计文档 01 §4.1.1（第 239 行） | 新封装的 `attempt` 允许非负整数或空值，首次基数待核验 | 旧实现的首个编号是 1，下界是 1；0 只可能来自手工建立的目录 |

### 6.11 未决事项

1. 所有测试映射都还没有运行结果，由规划端在受控取证中运行后补上。
2. TaskLock 没有归属校验。过期接管后，原持有者退出时会删掉新持有者的锁：探针已顺序模拟复现，但没有正式测试。锁只看 mtime，owner.json 从不读取。
3. 以下内容只是源码推导或探针，没有正式测试：
   - 并发 prepare 撞名时的重试；
   - 跨 plan_version 的编号连续与计次；
   - 删除最高编号目录后编号会被复用。
4. 以下异常分支是推导，未验证：
   - 二次恢复时 `*.partial` 已存在，Windows 上 `Path.rename` 会抛 FileExistsError，main 不捕获；
   - 终止进程树期间再收到信号，`_Interrupted` 未被捕获，状态停在 RUNNING；
   - prepare 在写 meta.json 之前失败，按 task-id 定位后 `load_attempt` 抛出未捕获的 OSError；
   - collect 中非 DispatchError/OSError 的异常让状态停在 COLLECTING。
5. pid_alive 有三处风险，都未验证：
   - PID 复用会被误判为存活；
   - Windows 上 tasklist 失败返回 None，会被当作可以继续；
   - POSIX 上 os.kill 的非常规异常会直接上抛。
6. Linux 与 macOS 上调度器被杀后的残留行为，本机（Windows）无法取证。
7. 以下旧语义是否在 v2 保留，由 07 决定：
   - cost_budget 只校验、不拦截；
   - 计次跨版本，但限额按各自的合同版本；
   - 实际用时可以超过预留；
   - mark INTEGRATED 不检查当前状态。

### 未解决事项（第 6 节）

- 没有运行 tests/test_dispatch.py（按约束由规划端受控取证），所有测试映射都只说明测试源码中有这条断言，结果未知。
- TaskLock 没有归属校验：过期接管后，原持有者 `__exit__` 会无条件 rmtree，删掉新持有者的锁（scripts/pi_dispatch.py:2604-2606、2612-2613）。顺序模拟探针已复现，没有正式测试，也没有真实并发取证。
- 锁的归属只看目录 mtime，owner.json 只写不读（scripts/pi_dispatch.py:2597、2601）；mtime 在不同文件系统上的更新语义与时钟偏差的影响未验证。
- 写 owner.json 时出现 FileExistsError 会被当作“锁已存在”继续等待，最终以“任务锁被占用”失败并留下锁目录（scripts/pi_dispatch.py:2595-2599）；源码推导，未验证。
- 并发 prepare 撞名重试（scripts/pi_dispatch.py:2622-2628）、跨 plan_version 的编号连续与计次，都没有直接测试。
- 删除最高编号的 attempt 目录后，按 max+1 会复用该编号（scripts/pi_dispatch.py:2621）；源码推导，未验证，且流程规则禁止删除 runs 证据。
- 预算竞争中落败方的拒绝点（锁外 3273-3275 还是锁内 3301-3303）取决于时序，测试没有断言落败方的状态与退出码（tests/test_dispatch.py:330-343）。
- 二次 collect --recover 时 *.partial 已存在，Windows 上 Path.rename 会抛 FileExistsError，main 不捕获，得到 traceback、退出码 1（scripts/pi_dispatch.py:3436-3439、4964-4971）；未验证。
- _terminate_tree 期间再收到信号时，_Interrupted 从 run_supervised 抛出，main 不捕获，状态停在 RUNNING 且没有 run.json（scripts/pi_dispatch.py:703-706、4964-4971）；源码推导，未验证。
- 没有测试通过向调度器发送 SIGINT/CTRL_BREAK 验证 run_supervised 期间产生的 CANCELLED，也没有测试各阶段 Ctrl+C 的状态（scripts/pi_dispatch.py:703-706、3087、3097-3098、3220-3224、3327-3332）。
- prepare 在写 meta.json 之前异常时，目录中只有 state.json=PREPARE_FAILED（scripts/pi_dispatch.py:3194-3221）：按 task-id 定位（2643-2649）后，load_attempt 抛出未捕获的 FileNotFoundError；未验证。
- 按 task-id 定位总是取编号最大的 attempt（scripts/pi_dispatch.py:2643-2649），`collect --recover <task-id>` 可能指向错误的 attempt；源码推导。
- collect 中 summarize_events、extract_report、main_repo_fingerprint 等抛出非 DispatchError/OSError 异常时，状态停在 COLLECTING（scripts/pi_dispatch.py:3356-3394）；源码推导。
- pid_alive：Windows 上 PID 复用会被误判为存活，tasklist 失败或超时返回 None 会被当作可以继续；POSIX 上 os.kill 的非常规异常直接上抛（scripts/pi_dispatch.py:726-740）。均未验证。
- Linux 孙进程残留、macOS 没有父进程死亡通知，是测试源码登记的已知限制（tests/test_dispatch.py:465-470），本机（Windows）无法取证。
- 实际 wall_seconds 包含 grace 与回收等待，可能超过 reservation，累计用量可能超过 max_wall_seconds_total（scripts/pi_dispatch.py:678、696、715、720）；源码推导，没有测试。
- 以下旧语义是否在新协议中保留，待 07 决定：cost_budget 只校验、不参与核算（scripts/pi_dispatch.py:1576-1580）；计次跨版本但限额按各自合同版本（3182、3272、2653-2656）；prepare 与 run 的时长门槛不同（3187、3305）。
- mark INTEGRATED 不检查当前状态，只看最新 verdict（scripts/pi_dispatch.py:4399-4404），例如已 ABANDONED 的 attempt 仍可标为 INTEGRATED；没有测试。
- 合成 run.json 的 timed_out 固定为 False，Pi 实际超时后被恢复也不会得到 TIMEOUT（scripts/pi_dispatch.py:3430）；沿用已有 run.json 时 G1 可能通过，与 SKILL.md:90“恢复证据不能直接作为 PASS 依据”不完全一致。
- gates.md 的状态表与源码允许的转换不一致：缺 SUPERSEDED，verdict 可以重新记录，ABANDONED 几乎不受限。是否更新文档由 12 决定。
- 设计文档 01 §4.1.1 称新封装 attempt 允许非负整数；旧实现的下界是 1，是否把 0 视为非法的历史值，由 01-D03 与 07 决定。

## 7. 入口退出码与 wait 语义

> **纳入说明**：本节是区域章节原稿（已经对抗核对），正文照录，只统一了标题层级并修正排版。
> - 原稿编写时尚未取得 `bl-01t1-legacy-20260925` 的运行结果，文中“没有运行”“未运行”“NOT_RUN”“结果未知”等说法描述的是原稿编写时的状态；本次运行结果见本文第 0.3、2、9、10 节。
> - 正文中的“第 k 节”“见第 k 节”指本区域内的 7.k 小节，不是本文的第 k 节。
> - 标“实测”“探针”的内容是起草或核对者在会话临时目录中的一次性复现，没有归档为 fixture，证据等级仍按 source_inspected 记。

> 取证范围：`scripts/pi_dispatch.py`（TOOL_VERSION 2.2.2，HEAD a4fa199）、`scripts/dispatch-pi.sh`、`tests/test_dispatch.py`；文档与技能中的说法单列为 source_reported。行号以当前工作区文件为准。
>
> 另做过只读实测：没有调用 pi，也没有写仓库；临时仓库放在会话 scratchpad 中。实测内容：
> - 用法错误：无子命令、`--version`、未知子命令、缺参数、`wait --timeout abc`、`verdict --verdict NOPE`、`mark x FOO`、smoke 缺 required 参数；
> - wait：未知 attempt（直接运行与经 wrapper 运行）；在临时仓库中对各种 state.json 运行 wait 和 status；
> - `--repo` 指向不存在路径和非仓库目录；
> - 进程内注入 RuntimeError、KeyboardInterrupt、DispatchError、SystemExit。

### 7.1 常量与全局映射

| 项 | 规则 | 来源 |
|---|---|---|
| 常量 | EXIT_OK=0、EXIT_FAIL=1、EXIT_USAGE=2、EXIT_BLOCKED=3、EXIT_DRIFT=4 | scripts/pi_dispatch.py:53 |
| DispatchError 默认码 | `DispatchError(message, code=EXIT_BLOCKED)`：未写 code 的 raise 一律退出 3 | scripts/pi_dispatch.py:304-309 |
| 显式写码的位置 | `return EXIT_BLOCKED` 只在 wait（:3937、:3942）；DispatchError 显式带 EXIT_BLOCKED 的在 :2694、:2698、:3175；EXIT_DRIFT 只在 :4014；EXIT_FAIL 作为 DispatchError code 只在 :4290 | 同左 |
| 无子命令 | `parser.print_help()` 输出到 **stdout**，`return EXIT_USAGE`（2） | scripts/pi_dispatch.py:4961-4963 |
| argparse 用法错误 | `parse_args` 在 try 之外。以下情况都会在 stderr 输出 `usage:` 与 `pi_dispatch.py[ <sub>]: error: …`，SystemExit(2)，**没有** `ERROR:` 前缀（已实测）：<br>- 未知子命令；<br>- 缺位置参数；<br>- `type=int/float` 解析失败（wait/run/smoke 的 `--timeout`、`--interval`、`--human-minutes`）；<br>- choices 不符（verdict `--verdict`/`--class`、mark 的 state）；<br>- required 缺失（smoke `--provider`/`--model`、mutate `--spec`、verdict `--verdict`/`--review`） | scripts/pi_dispatch.py:4960、4831-4950 |
| --version / --help | stdout 输出 `pi_dispatch 2.2.2` 或帮助，退出 0 | scripts/pi_dispatch.py:4835、48 |
| DispatchError | stderr 输出 `ERROR: <message>`，退出 `exc.code` | scripts/pi_dispatch.py:4966-4968 |
| KeyboardInterrupt | stderr 输出 `已取消。`，退出 130 | scripts/pi_dispatch.py:4969-4971 |
| 其他未捕获异常 | 不捕获，经 `sys.exit(main())` 传出。Python 打印 Traceback，退出 **1**，与 EXIT_FAIL 同码（已实测） | scripts/pi_dispatch.py:4964-4975 |
| 正常返回 | `return int(args.func(args))`；全文件只有 :4975 一处 sys.exit | scripts/pi_dispatch.py:4965 |
| dispatch-pi.sh | 依次试运行 python3、python、`py -3`，要求 ≥3.8。找到后用 `exec` 运行 pi_dispatch.py，退出码原样透传（实测 2、0）。都不可用时 stderr 输出 `ERROR: 需要 Python 3.8+（python3、python 或 py -3）`，`exit 2`，与 EXIT_USAGE 同码 | scripts/dispatch-pi.sh:4、9-16、21-22 |
| 输出流 | DispatchError 写到 stderr。逐项诊断写到 **stdout**，并先于 stderr 的 ERROR 行输出：`ERROR <msg>`（validate/derive-json/prepare/baseline/mutate，无冒号）、`WARN  `、`NOTE  `、`PREFLIGHT `、`GATE `、`LOSS  `、`DRIFT `。测试把两路输出合并后再断言 | scripts/pi_dispatch.py:2988-2996、3283-3284、4286-4288、4464-4465、3893-3894；tests/test_dispatch.py:44 |

### 7.2 公共前置错误（多个子命令共用）

| 码 | 触发与原文片段 | 来源 |
|---|---|---|
| 2 | `当前目录不在 Git 仓库中：<路径>`（含 `--repo` 指向非仓库目录，已实测）/ `请在主工作区运行本工具，而不是在 worktree 中` | scripts/pi_dispatch.py:960、963 |
| 2 | `无法解析 <config>` / `顶层必须是对象` / `worktree_root 不能位于仓库内部` | scripts/pi_dispatch.py:976、978、986 |
| 2 | extra_protected_paths、planner_paths、commit_trailers 配置格式错 | scripts/pi_dispatch.py:994、1007、1058 |
| 2 | `合同文件必须位于 …` / `计划标识不合法` | scripts/pi_dispatch.py:1026、1027 |
| 2 | `attempt 目录必须位于 … 下` / `找不到 attempt：<值>` | scripts/pi_dispatch.py:2641、2650 |
| 2 | `PI_DISPATCH_PI_CMD 必须是 JSON 字符串数组…` / `参数 … 含批处理特殊字符` | scripts/pi_dispatch.py:1769、1794 |
| 2 | `… 与合同 executor.… 冲突` / `缺少或无效的执行模型` / `无效的思考级别` | scripts/pi_dispatch.py:2677、2684、2687 |
| 3 | `未找到 git，请先安装 Git。`（只捕获 FileNotFoundError）/ `git <cmd> 失败：…`（check=True 时） | scripts/pi_dispatch.py:756-757、760 |
| 3 | `PATH 中找不到 pi…` | scripts/pi_dispatch.py:1773 |
| 3 | 执行模型不在 allowed_executors / `该执行模型的思考级别固定为 …`（显式 EXIT_BLOCKED） | scripts/pi_dispatch.py:2693-2694、2697-2698 |
| 3 | `任务锁被占用` / `无法分配 attempt 目录` | scripts/pi_dispatch.py:2608、2629 |
| 1 | `--repo` 指向不存在的路径：Windows 上 subprocess 抛 NotADirectoryError，未被 :756 捕获，出现 Traceback（已实测） | scripts/pi_dispatch.py:957-958、754-757 |
| 1 | meta.json 或 contract.json 缺失或损坏：`load_attempt` 用 `read_json`，ValueError/OSError 未被捕获。只影响 run、collect、check、mutate、verdict、branch、cleanup；wait、mark、status 不调用它 | scripts/pi_dispatch.py:332-334、2653-2656 |
| 1 | state.json 是合法 JSON 但不是对象时，`get_state` 的 `.get` 抛 AttributeError（wait 已实测）；dispatch.config.json 读取时出现 OSError（只捕获 ValueError） | scripts/pi_dispatch.py:2555、973-976 |

- `resolve_run_dir` 接受以下参数形式（scripts/pi_dispatch.py:2632-2650）：
  - attempt 路径或 `task-id/attempt-NNN`：要求目录中有 meta.json；
  - `task-id` 或 `task-id.vN`：取最新的 attempt，**不要求** meta.json 存在；这种情况下，需要 load_attempt 的入口会以 Traceback 退出 1。

### 7.3 逐子命令退出码表

“—”表示源码没有返回该码的语句。各行另有三种情况：
- 未捕获异常：退出 1；
- KeyboardInterrupt：退出 130；
- 第 2 节的公共前置码。

行号均指 `scripts/pi_dispatch.py`。

| 子命令 | 0 | 1 | 2 | 3 | 4 | 其他 |
|---|---|---|---|---|---|---|
| validate | 合同有效（允许警告）:3007-3008 | 只有未捕获异常，例如 md 非 UTF-8（在 try 外读取 :1668） | 合同无效 `合同无效：N 个错误，M 个警告。`（return）:3004-3006；标识或路径 :1026-1028；配置错 :1673 | 公共码；`git rev-parse HEAD` 失败 :1684 | — | — |
| derive-json | 写入并校验有效，且推导无问题 :3038-3039；`--print` 无问题 :3028 | — | 缺 md :3017；已存在但未加 --force :3029-3030；校验无效 :3035-3037；**打印了“合同有效”，但推导有 WARN 时仍为 2** :3039；`--print` 有问题 :3028。JSON 在校验前已写入 :3031 | 仅公共码 | — | — |
| prepare | PREPARED :3234-3242 | setup 失败 :3225-3229；setup 后 worktree 变脏 :3230-3233（均标 PREPARE_FAILED） | 合同校验失败 :3172-3173；执行模型冲突或无效 :3180；config、worktree_root :3176、3190 | `.agent/runs/` 未被忽略（显式 EXIT_BLOCKED）:3174-3175；BUDGET_EXCEEDED :3184-3189；allowlist :3180；分配失败 :3192；try 内的 DispatchError/OSError 重包为 `prepare 失败（… 已标记 PREPARE_FAILED）`，原 code 丢失 :3220-3223 | — | 其他 BaseException 先标 PREPARE_FAILED 再原样抛出 :3224（130 或 1） |
| run | 收集后为 NEEDS_REVIEW 且 events ok :3348-3349 | 其余收集结果：TIMEOUT、CANCELLED、INFRA_FAILURE，或 NEEDS_REVIEW 但 events 不 ok :3349；spawn 失败写成 spawn_error，结果 INFRA_FAILURE :663-667、682-688、3395-3396 | 执行模型冲突或无效 :3271；PI_DISPATCH_PI_CMD :3277；argv 不安全 :3296 | 非“未领取的 PREPARED”（状态保持原样）:3255-3257；G0 输入不一致 :3267-3269（其中的 git rev-parse :3263）；BUDGET_EXCEEDED :3275、3303、3306；预检先输出 `PREFLIGHT …` 再抛出，仍为 PREPARED :3281-3285；任务锁 :3300；重复领取 :3313；PATH 无 pi :3277 | — | 见本表下方的“run 的中断” |
| collect | 恢复完成，**不论** collect 得出什么状态（INFRA_FAILURE、TIMEOUT、CANCELLED 或 NEEDS_REVIEW）:3440-3443 | — | 状态不可恢复或未加 --recover :3416-3420 | 记录的 Pi 进程仍存活 :3424-3425（pid_alive 返回 None 时放行 :730-732） | — | — |
| check | 必要检查通过、候选未被修改、没有意外文件 :4051-4052。非必要检查失败不影响结果 :4030；`--only` 子集也可以得到 0 | 以上任一不满足 :4051-4052 | `未知检查` :3972；`合同没有可运行的检查` :3975 | 状态不可验收 :3962-3963；缺 candidate.json :3965-3966；--fresh 补丁不可用 :3987-3988；干净副本失败 :3992-3995；worktree 不存在 :3999-4000；snapshot 的 git 失败 | **运行前候选漂移**（全文件唯一的 4，不区分 --fresh）:4005-4014 | — |
| baseline | 没有 expect_on_base 不符 :4149（expect any 的检查失败也是 0 :4134-4138） | 有不符 :4126-4131、4149 | 合同无效 :4083-4084；未知检查 :4090；没有检查 :4093 | 基线副本 setup 失败 :4113；worktree add 失败 :4109（try/finally 仍会移除副本 :4117-4119） | — | — |
| mutate | 流程完成，**即使有 missed 或 error** :3672-3690 | — | 变异清单无效（先逐行 `ERROR <p>`）:3603-3606 | 状态不允许（允许 REVIEWABLE_STATES 与 INTEGRATED）:3596-3597；补丁不可用 :3599-3600；干净副本失败 :3618-3621；不变异时 command 未通过 :3631-3635 | — | — |
| verdict | 结论已记录（含 REVISE/BLOCKED/ESCALATE）:4313-4316 | PASS 被门禁拒绝：DispatchError(EXIT_FAIL)，先逐行输出 `GATE <G> …`；即使同时带了豁免也是 1 :4284-4290 | 报告缺失或为空 :4268-4269；Verdict 行不符 :4271-4273；`--waive` 格式错 :4278；PASS 带豁免且门禁全部通过 :4291-4292；缺豁免理由 :4295-4296；AWE 缺 --waive 或 --decided-by :4297-4298；缺 --class :4299-4300 | `状态 <S> 不能记录验收结论` :4264-4265 | — | — |
| branch | 分支已建，输出 `commit=… branch=…` :4381-4392 | — | `--trailer` 非法 :4340-4342；分支名非法 :4355-4356；commit_trailers 配置 :4339 | 结论不允许 :4332-4334；缺 Git 身份 :4336-4338；缺候选 :4346-4347；树丢失且重建不一致 :4351-4352；分支已存在 :4357-4358；commit-tree 或 branch 失败 :4375-4376 | — | — |
| mark | 已标记 :4420-4422（ABANDONED 在非活动状态下无其他限制） | — | INTEGRATED 缺 --ref :4403-4404；SUPERSEDED 状态不符 :4408-4409；SUPERSEDED 缺 --ref 或 --reason :4410-4411 | INTEGRATED 但结论不是 PASS/AWE（先于 --ref 检查）:4400-4402；活动状态未加 --force :4412-4415；Pi 进程仍存活 :4418-4419 | — | — |
| cleanup | 已移除，或 worktree 已不存在 :4468-4482 | — | — | RUNNING/COLLECTING（--force 也不行）:4435-4436；PREPARED/PREPARING 未加 --force :4437-4438；会丢内容（先逐行 `LOSS …`）:4463-4467；不是登记的 worktree :4470-4471；worktree list 或 remove 失败 :4426、4468 | — | — |
| sync-adapters | `--check` 一致 :3900-3901；同步完成且没有缺源 :3902-3910 | `--check` 有 DRIFT 或缺源 :3892-3899；同步模式下仍有缺源 :3907-3909 | — | 全部技能缺源（1.x 布局）:3887-3889；链接或 junction :3757 | — | — |
| status | 成功时为 0，**不反映 attempt 状态**：`--json`、`没有 attempt 记录。`、文本表 :4565-4578 | 只有未捕获异常（如非对象 state.json :2555） | 非 task-id 形式的参数解析失败 :4554-4556 | 仅公共码 | — | — |
| metrics | 成功时为 0 :4654 | 只有未捕获异常 | `--out` 不在 _env/_reports 下，或等于这两个目录本身 :4597→4589-4591 | 仅公共码（给了 --out 时，safe_output_path 的 discover :4585 先于 --out 校验） | — | — |
| doctor | 没有 problems :4757、4762 | 有 problems :4762（pi 相关的 DispatchError 被吞入 problems :4727-4728） | `--out` 非法；给了 --out 且不在仓库中 :4659→4585、4589-4591 | 只在给了 --out 且找不到 git 时 :4659→4585→757；不带 --out 时仓库错误只写进 notes :4753-4754 | — | — |
| smoke | 全部步骤 ok :4822-4824 | 任一步失败（含 spawn_error）:4824 | `--out` :4766；provider/model 非法 :4769-4771；思考级别非法 :4772-4773；PI_DISPATCH_PI_CMD :4767；argv :4791 | PATH 无 pi :4767（先于参数校验）；不带 --out 时不需要 Git 仓库 | — | — |
| wait | 进入 TERMINAL_STATES :3946-3950 | 状态缺失、损坏或未知 :3943-3945；state.json 为非对象 JSON 时是 Traceback 的 1 :2555 | `--timeout 必须是正整数（秒）` :3926-3927（在 resolve_run_dir 之后） | 到时仍在活动状态 :3933-3937；PREPARED 未开始 :3940-3942；另有 DispatchError 默认码（:757） | — | — |

**run 的中断**：
- 中断处理器只在 run_supervised 内有效（安装 :676，恢复 :712）。Pi 运行期间收到 SIGINT、SIGTERM、SIGHUP 或 SIGBREAK，都会转为 `_Interrupted`（:571-585、703-706）。
- 这之后照常 collect。按 :3395-3404 的优先级，最终状态可能是 INFRA_FAILURE、TIMEOUT 或 CANCELLED，都退出 **1**，不是 130。
- 预检、领取或 collect 阶段按 Ctrl+C，得到 KeyboardInterrupt，退出 130：
  - 领取后写文件阶段（:3319-3332）会先标 INFRA_FAILURE；
  - collect 阶段中断时状态停在 COLLECTING（:3344）。

### 7.4 wait 的输出结构

| 情形 | 判定 | stdout 原文模板 | 码 | 来源 |
|---|---|---|---|---|
| 仍在运行 | state ∈ {PREPARING, RUNNING, COLLECTING}，且已等待 ≥ `--timeout` | `仍在运行：<run-dir> · <STATE>。再次运行 wait 继续等待。`；STATE 为 RUNNING 时**必定**在 STATE 后附加 ` · live:…`，PREPARING/COLLECTING 从不附加（已实测） | 3 | scripts/pi_dispatch.py:3914、3933-3937、4548 |
| 未开始 | state = PREPARED，且已等待 ≥ min(60, `--timeout`) | `attempt 仍是 PREPARED：run 没有开始（或启动前就失败了）。检查后台命令的输出：<run-dir>` | 3 | scripts/pi_dispatch.py:3933、3940-3942 |
| 无法确定 | 不是上述状态，也不在 TERMINAL_STATES。state.json 缺失、不是合法 JSON 或没有 state 键时显示 `UNKNOWN`；`"state": null` 时显示 `None` | `无法确定 attempt 的状态（<STATE>）：state.json 缺失、损坏或状态未知。检查 <run-dir>` | 1 | scripts/pi_dispatch.py:3943-3945、2554-2555、344-348 |
| state.json 不是对象 | 合法 JSON 但不是对象（如 `[]`） | stdout 为空；stderr 为 Traceback（AttributeError） | 1 | scripts/pi_dispatch.py:2555、4964-4975（已实测） |
| 已结束 | state ∈ TERMINAL_STATES | `已结束：<run-dir> · <STATE>`；summary.md 存在时再加一行 `摘要：<仓库相对路径>` | 0 | scripts/pi_dispatch.py:3946-3950、81-82 |
| 参数或定位错误 | resolve_run_dir 失败，或 `--timeout` < 1（attempt 不存在时先报“找不到”） | stdout 为空；stderr 为 `ERROR: 找不到 attempt：<值>` 或 `ERROR: --timeout 必须是正整数（秒）` | 2 | scripts/pi_dispatch.py:3924-3927、2650、4966-4968（已实测） |
| git 缺失 | Repo.discover 找不到 git | stderr 为 `ERROR: 未找到 git，请先安装 Git。` | 3 | scripts/pi_dispatch.py:3924→958→757 |

- `<run-dir>` 由 `display_path` 生成，是仓库相对、正斜杠的路径（scripts/pi_dispatch.py:3929、387-390）。wait 没有 `--json`，每种情形各输出一行中文文本；已结束时可能另加一行“摘要：…”。
- TERMINAL_STATES = PASS、ACCEPTED_WITH_EXCEPTION、REVISE、BLOCKED、ESCALATE、INTEGRATED、ABANDONED、SUPERSEDED、TIMEOUT、CANCELLED、INFRA_FAILURE、PREPARE_FAILED、NEEDS_REVIEW（scripts/pi_dispatch.py:75、81-82）。**wait 退出 0 只表示已结束，不表示通过。**
- PREPARED 不会用“仍在运行”的文案：外层条件要求 elapsed < min(60, timeout) ≤ timeout，内层 `elapsed >= timeout` 不可能成立（scripts/pi_dispatch.py:3933-3934）。
- 每轮重新读 state。sleep 时长为 `max(0.2, min(--interval, timeout-elapsed))`，`--interval` ≤ 0 时按 0.2 秒。`--interval` 默认 5.0，在 help 中隐藏；`--timeout` 默认 540，help 写“到时仍在运行时退出码 3”（scripts/pi_dispatch.py:3938、4900-4901）。
- 源码 docstring 自述了 0、3、PREPARED 60 秒宽限与状态未知时的 1（scripts/pi_dispatch.py:3918-3922）。

### 7.5 live 进度（wait 与 status 共用）

| 项 | 规则 | 来源 |
|---|---|---|
| 格式 | `live:<N>t[ <秒>s][ 长时间没有工具调用（<M> 个增量）]`，总是返回非空字符串 | scripts/pi_dispatch.py:4548 |
| N | events.jsonl 中字节串 `"type":"tool_execution_end"`（紧凑写法）的出现次数。不解析 JSON，带空格的写法不计入（已实测）；文件读不到时按空处理 | scripts/pi_dispatch.py:4531-4534、4543、4548 |
| 秒 | 从 run-started.json 的 started_at（`%Y-%m-%dT%H:%M:%SZ`）算到现在，`%d` 截断；缺失或格式错误时省略 | scripts/pi_dispatch.py:4535-4542 |
| 长思考提示 | 最后一次 tool_execution_end 之后，`"type":"message_update"` ≥ 6000 次；文件里没有 tool_execution_end 时按整个文件统计 | scripts/pi_dispatch.py:4522、4544-4547 |
| 使用处 | wait 只在 RUNNING 且到时限时附加。status 对 RUNNING 行把 events_ok 替换为该字符串，文本表 EVENTS 列与 `--json` 字段都是如此（已实测） | scripts/pi_dispatch.py:3935、4562-4564 |
| status 的 EXIT 列 | 是 run.json 中 **Pi 进程**的 exit_code，不是调度器的退出码 | scripts/pi_dispatch.py:4498、4572 |

### 7.6 同码异义

| 码 | 含义集合 | 来源 |
|---|---|---|
| 0 | 成功。不同入口含义不同：<br>- wait：已结束（不论结论）；<br>- collect：恢复完成（不论状态）；<br>- mutate：流程完成（可有 missed）；<br>- baseline：没有期望不符（检查可以失败）；<br>- verdict：结论已记录（含 REVISE）；<br>- status、metrics：成功执行即为 0，不反映 attempt 状态 | scripts/pi_dispatch.py:3950、3443、3690、4149、4316、4578、4654 |
| 1 | EXIT_FAIL 的负面结果：run、check、baseline、prepare 的 setup、sync-adapters、doctor、smoke；verdict 的 PASS 被门禁拒绝；wait 状态未知。**另外**任何未捕获的 Python 异常也是 1，包括 Windows 上 `--repo` 不存在、非对象 state.json、损坏的 meta.json | scripts/pi_dispatch.py:3349、4052、4149、3229、3233、3899、3909、4762、4824、4290、3945、4964-4975 |
| 2 | EXIT_USAGE（DispatchError，以及 validate/derive-json 的 return）；argparse 的 SystemExit(2)，没有 `ERROR:` 前缀；wrapper 找不到 Python | scripts/pi_dispatch.py:4960、3006、3028、3037、3039；scripts/dispatch-pi.sh:22 |
| 3 | DispatchError 默认码（拒绝、阻断、环境、状态、预算、预检、锁、git 失败）；显式 EXIT_BLOCKED（allowlist、.gitignore）；wait 显式返回的“仍在运行”或“未开始” | scripts/pi_dispatch.py:307、2694、2698、3175、3937、3942 |
| 4 | 只有 check 运行前的候选漂移 | scripts/pi_dispatch.py:4014 |
| 130 | KeyboardInterrupt。例外：Pi 运行期间的中断被 run_supervised 接管，run 最终退出 1（状态为 CANCELLED、TIMEOUT 或 INFRA_FAILURE） | scripts/pi_dispatch.py:4969-4971、703-706、3395-3404 |

### 7.7 文档声明与源码对照（source_reported）

| 声明 | 位置 | 源码核对 |
|---|---|---|
| wait 每次最多等 9 分钟；退出码 3 表示仍在运行，可以重复调用 | AGENTS.md:52-54；.agents/skills/dispatch-pi/SKILL.md:44 | 540 秒与 scripts/pi_dispatch.py:4900 一致。但 3 还表示 PREPARED 未开始（:3942）和默认码 DispatchError（如 :757）；只看 3 就重复调用，可能一直循环 |
| 结束时退出 0；仍在运行时退出 3 **并打印进度** | SKILL.md:44 | 退出 0 与 :3950 一致，但 0 也包括 INFRA_FAILURE、TIMEOUT、REVISE 等。只有 RUNNING 打印 live 进度（:3935）；PREPARING/COLLECTING 只打印状态；PREPARED 用另一条文案 |
| PowerShell 中要加 `; exit $LASTEXITCODE`，否则 3 可能显示成 1 | AGENTS.md:55；SKILL.md:44 | 源码无法核实，属于宿主行为 |
| `PREFLIGHT …` 且退出码 3 | SKILL.md:52 | 一致：`PREFLIGHT` 行在 stdout，随后默认码 3 的 ERROR 在 stderr（:3281-3285），attempt 仍为 PREPARED |
| sync-adapters `--check` 不一致时退出码 1 | scripts/pi_dispatch.py:4905（help） | 一致。另外缺源也是 1，全部缺源是 3（:3887-3889） |
| 进程退出码 0 不代表通过 | AGENTS.md:83；.agents/skills/dispatch-pi/troubleshooting.md:4 | 说的是 Pi 进程。调度器的 run 要 NEEDS_REVIEW 且 events ok 才返回 0（:3349） |
| （AGENTS.md 与 SKILL.md 未提）wait 的 1、2，check 的 4，argparse 的 2，130 | — | 源码 docstring :3918-3922 写了 wait 的 1；其余见第 3、4 节 |

### 7.8 测试对退出码的锁定情况

| 断言 | 测试 |
|---|---|
| 各入口成功路径 `== 0`（validate、run、check、verdict、branch、cleanup、mark、collect --recover、doctor、smoke、baseline、derive-json、status、metrics --out） | tests/test_dispatch.py 的 test_happy、test_dispatcher_killed、test_stuck_states、test_setup_wrapper_doctor、test_feedback_v11、test_output_paths 等 |
| check 漂移 `== pd.EXIT_DRIFT`；产生意外文件 `== 1` | tests/test_dispatch.py::test_candidate_drift_and_artifacts（:294、:309） |
| run 的 events 不 ok `== 1`，且状态为 NEEDS_REVIEW | tests/test_dispatch.py::test_events_and_thinking “error stopReason -> exit 1 but NEEDS_REVIEW”（:370） |
| wait 已结束 `== 0`、运行中 `== 3`、PREPARED `== 3` | tests/test_dispatch.py::test_v2_planner_adapters（:1332、:1335、:1341） |
| wait 状态不可读 `== 1`（state.json 写成 `{`） | tests/test_dispatch.py::test_v2_review_fixes “wait does not report an unreadable state as finished”（:1524） |
| mutate 清单无效 `== 2`；有 missed 仍 `== 0` | tests/test_dispatch.py::test_mutate（:1263、:1244） |
| sync-adapters `--check` 不一致或缺源 `== 1`；同步模式缺源 `== 1` | tests/test_dispatch.py::test_v2_planner_adapters（:1296、:1305）、test_v2_review_fixes（:1397、:1399） |
| `--out` 非法 `== pd.EXIT_USAGE` | tests/test_dispatch.py::test_output_paths（:590、:592） |
| branch 的 `--trailer` 或 commit_trailers `== pd.EXIT_USAGE` | tests/test_dispatch.py::test_v21_codex_trial_feedback（:1760、:1764）、test_repo_config_features（:653） |
| wrapper 无 Python `== 2`、透传 `== 7`（Windows 上跳过，:658-659）；Windows 上只覆盖 wrapper 的 0（:714） | tests/test_dispatch.py::test_wrapper_interpreters_and_literal_arguments、test_setup_wrapper_doctor |
| live 格式只做单元调用 `pd._live_progress`，没有经过 status/wait | tests/test_dispatch.py::test_feedback_v12（:1152） |
| 其余拒绝路径大多只断言 `code != 0`，不区分 2 和 3 | 见各 LB-EXIT 条目 |

### 7.9 未决

- PowerShell 把 3 显示成 1 的说法无法从源码核实。
- run 在 TIMEOUT、CANCELLED、INFRA_FAILURE 时退出 1，没有测试锁定；test_timeout 不检查退出码。
- main 的几条行为都没有测试：无子命令→2、argparse→2、130、未捕获异常→1。
- wait 有几条路径没有测试：`--timeout<1`→2；PREPARING/COLLECTING 超时；60 秒宽限；非对象 state.json；输出中的 live 片段和 `摘要：` 行。
- 各辅助函数可能抛出的非 DispatchError 异常没有逐一列举，它们都会以 Traceback 退出 1。
- POSIX 上 `--repo` 指向不存在路径时的退出码没有实测：推断会被误报为“未找到 git”，退出 3。
- live 进度按紧凑 JSON 的字节匹配；真实 pi 的输出是否总是紧凑，本任务无法核实。
- 源码没有说明以下重叠是否有意：wait 的 3 与默认码 3 重叠；崩溃与 EXIT_FAIL 共用 1。

### 未解决事项（第 7 节）

- AGENTS.md:55 与 SKILL.md:44 说 PowerShell 外层可能把 wait 的退出码 3 显示成 1。这是宿主或调用环境的行为，无法从源码或测试核实。
- run 以 TIMEOUT、CANCELLED、INFRA_FAILURE 结束时退出 1（scripts/pi_dispatch.py:3349），没有测试断言；test_timeout（tests/test_dispatch.py:425-440）只检查状态。
- main 的几条行为只做过只读实测，没有测试覆盖：无子命令返回 2（:4961-4963）；argparse SystemExit(2)；KeyboardInterrupt 返回 130（:4969-4971）；未捕获异常退出 1。
- wait 有几条路径没有测试覆盖：--timeout<1 返回 2（:3926-3927）；PREPARING/COLLECTING 到时返回 3；timeout≥60 时 PREPARED 的 60 秒宽限；非对象 state.json 的 Traceback 1；到时输出中的 live 片段；已结束时的“摘要：”行。
- wait 的退出码 3 与 DispatchError 默认码 3 重叠，例如 Repo.discover 找不到 git（:757）时也是 3；只看退出码重复调用的调用方可能一直循环。源码没有说明这是否有意。
- 未捕获的 Python 异常同样退出 1，与 EXIT_FAIL 无法区分，例如 Windows 上 --repo 不存在、state.json 或 run-started.json 为非对象 JSON、meta.json 损坏、md 非 UTF-8。源码没有说明这是否有意，也没有逐一列出 pi_preflight、summarize_events、record_candidate、snapshot_tree、_run_command_item、normalize_contract 等可能抛出的非 DispatchError 异常。
- POSIX 上 --repo 指向不存在的路径时，Python 一般抛 FileNotFoundError，git()（:756）会把它误报为“未找到 git，请先安装 Git。”并退出 3。本机是 Windows，实测结果是 NotADirectoryError→1，POSIX 行为未实测。
- SIGTERM、SIGHUP 等信号若在 run_supervised 之外到达，退出码由 Python 或操作系统决定，源码没有处理（只处理 KeyboardInterrupt→130）。调度器被 taskkill /F 等方式强杀时的退出码同样取决于操作系统。
- _live_progress 按紧凑 JSON 字节串 "type":"tool_execution_end" 计数（已实测带空格写法不计入）。本任务禁止调用 pi，测试只用 stub，所以无法核实真实 pi 的事件输出是否总是紧凑。
- test_wrapper_interpreters_and_literal_arguments 在 Windows 上直接 return（tests/test_dispatch.py:658-659），Windows 上 wrapper 的“无 Python→2”与非零退出码透传都没有测试覆盖。本次只在本机实测了透传 2 和 0。
- 许多拒绝路径的测试只断言 code != 0，没有锁定具体是 2 还是 3，涉及 prepare、run、collect、verdict、branch、mark、cleanup、baseline、smoke、doctor 的 problems。

## 8. 旧自测清单与回归覆盖映射

> **纳入说明**：本节是区域章节原稿（已经对抗核对），正文照录，只统一了标题层级并修正排版。
> - 原稿编写时尚未取得 `bl-01t1-legacy-20260925` 的运行结果，文中“没有运行”“未运行”“NOT_RUN”“结果未知”等说法描述的是原稿编写时的状态；本次运行结果见本文第 0.3、2、9、10 节。
> - 正文中的“第 k 节”“见第 k 节”指本区域内的 8.k 小节，不是本文的第 k 节。
> - 标“实测”“探针”的内容是起草或核对者在会话临时目录中的一次性复现，没有归档为 fixture，证据等级仍按 source_inspected 记。
> - 8.3 小节中“运行时（Windows）”的 check 数是按源码推算的值；本次实际分布见本文 0.3 节（共 256 个）。

> **取证范围**
> - 只读源码，基准提交 `a4fa199b0e5bdc658215765ee7558b9fe6723940`。`tests/`、`scripts/pi_dispatch.py`、`scripts/dispatch-pi.sh`、`AGENTS.md`、`.agents/`、`.claude/` 的已跟踪文件相对 HEAD 没有改动。`git status --porcelain` 在这些路径下只列出未跟踪的 `scripts/codekit/`（含 `__init__.py`、`baseline.py`）：测试不导入它，但 `sys.path[0]` 是 KIT/scripts，基线输入清单需要记录它。
> - **没有运行** `python tests/test_dispatch.py`。check 数分两列：“静态”是 AST 统计的 `check(` 调用处；“运行时”是按循环和平台分支推算的值。两者都以 01-T1 受控运行的输出为准。本节所有条目的 execution_status 都是“未运行”，evidence_basis 都是 source_inspected。
> - 函数名中的 `v11`、`v12`、`v2`、`v21`、`v22` 是工具的历史版本号（1.1.0、1.2.x、2.0.0、2.1.0、2.2.x，见各函数 docstring），不代表覆盖了新架构（3.1 末段、7.1 的 01-A07）。

### 8.1 入口、夹具与结果格式

| 项 | 旧行为（源码事实） | 来源 |
|---|---|---|
| 运行方式 | `python tests/test_dispatch.py [test_名 ...] [--keep]`；需要 Python 3.8+、git、bash（Windows 上为 Git Bash） | tests/test_dispatch.py:1-9 |
| 导入副作用 | 导入时就执行 `tempfile.mkdtemp(prefix="pi-dispatch-e2e-")`；把 stdout/stderr 重设为 UTF-8；把 KIT/scripts 插入 `sys.path` 后执行 `import pi_dispatch as pd`（导入的是 KIT **工作区**中的版本） | tests/test_dispatch.py:24, 34-38, 39-40 |
| 执行器替身 | `PI_DISPATCH_PI_CMD=json.dumps([sys.executable, tests/stub_pi.py])`<br>清除 `PI_EXEC_PROVIDER/MODEL/THINKING` 与 `STUB_SCENARIO/MODELS/AUTH/PTL/NOCOST/LIST_FAIL/AUTH_DETAIL`<br>**不清除** `STUB_MAIN_REPO`：只有 outside、touchmain、planner 三个场景读取它，这三处测试都显式传入，现有场景不受影响<br>其余环境变量（含 HOME、用户全局 git 配置）原样继承 | tests/test_dispatch.py:28-32 |
| 真实 pi 不可达 | `PI_DISPATCH_PI_CMD` 只在 :29 设置、从不删除；test_v21 的 `bare` 环境也由 BASE_ENV 派生；test_wrapper 只在 POSIX 上运行，调用的是假的 pi_dispatch.py | tests/test_dispatch.py:29, 1732, 656-698 |
| CLI 调用 | `tool()` 在临时仓库中运行 `[PY, "scripts/pi_dispatch.py", ...]`：该文件由 make_repo 从 KIT **工作区**复制；stdout 与 stderr 合并；非 0 不抛错；`sh()` 不设超时 | tests/test_dispatch.py:43-58, 189-190 |
| 临时仓库 | `git init`；user.email=t@example.invalid；`core.autocrlf false`；`commit.gpgsign false`；`normalize()` 为恒等实现<br>`run_tests.py` 在 `testsRun>0` 且成功时输出 `Tests N passed`，否则输出 `FAILED`<br>**提交 base 之后**才写 `.agent/dispatch.config.json`（`worktree_root=WORK/worktrees`）和 `normalize-query.v1.{md,json}`，所以它们在主仓库中是未跟踪文件（test_v22 在 :1786-1788 特意先提交） | tests/test_dispatch.py:162-205 |
| 合同样本 | step/step-5-preview，thinking high；7 个工具；允许修改 `src/normalize.py`、新增 `tests/test_normalize.py`；禁止 `package.json`；预算 3/600/1800/None<br>V01 为必要检查（`Tests [1-9][0-9]* passed`）；DoD 为 D01(V01)、D02(scope)<br>`build_md()` 由 JSON 生成一致的 Markdown | tests/test_dispatch.py:103-159 |
| check 输出 | 通过打印 `PASS <name>`；失败打印 `FAIL <name>  <- <detail 前 1500 字>` | tests/test_dispatch.py:61-63 |
| 调度 | 按 `globals()` 的定义顺序运行各 `test_*`，每个函数前打印 `== <name>`<br>函数抛出 `Exception` 时打印 traceback，追加一条 `(name, False, repr(exc))`，该函数剩余的 check 不再执行<br>`KeyboardInterrupt`、`SystemExit` 不会被捕获，此时没有汇总行 | tests/test_dispatch.py:1907-1919 |
| 汇总行 | `"\n%d checks, %d failed"`：N 为全部记录数（含异常记录），M 为失败记录数，不区分异常记录和普通 check | tests/test_dispatch.py:1920-1921 |
| 退出码 | 有失败为 1，否则为 0<br>测试名拼错时静默忽略；全部拼错时输出 `0 checks, 0 failed` 并**退出 0** | tests/test_dispatch.py:1910-1912, 1929 |
| 清理 | 带 `--keep` 时打印 `保留测试目录：<WORK>`<br>否则先对含 `.git` 的子目录执行 `git worktree prune`，再 `remove_tree(WORK)`（出错时 chmod 0o700 后重试）<br>清理在汇总行**之后**进行：二次删除仍失败时异常未被捕获，进程以 1 退出，即使汇总为 0 failed | tests/test_dispatch.py:94-100, 1922-1928 |
| 超时 | 函数级和整体都没有超时，挂起风险取决于被测的 `run --timeout` 和轮询上限 | tests/test_dispatch.py:43-48, 451-454 |
| 依赖 kit 工作区 | 导入 pd（:39-40）；复制脚本（:189-190、:664）<br>plan-task/examples（:563-579）<br>`adapter_drift(KIT)`、CLAUDE.md、`.claude/rules`、AGENTS.md 大小（:1277-1282）<br>AGENTS.md 与 plan-task/SKILL.md 原文（:1702-1709）<br>当前工作区这些前提经只读核对成立：没有 CLAUDE.md，没有 `.claude/rules`，AGENTS.md 为 10932 字节，技能副本经 `diff -rq` 一致，所需短语与示例 SHA 都存在。未经运行确认 | 见左 |

### 8.2 stub_pi.py 模拟面（Pi 0.87 JSON 模式）

| 命令或场景 | 模拟行为 | 使用它的测试 | 来源 |
|---|---|---|---|
| `--help` | 原样打印 `tests/stub_pi_help.txt`（186 行），exit 0。帮助内容包括 `pi auth <command>`（预检用正则 `\bpi auth\b` 判断，scripts/pi_dispatch.py:2057）、思考级别 `off…max`、全部 REQUIRED_PI_FLAGS（含 `--no-approve`）、`--no-context-files`、Built-in Tool Names（read、bash、powershell、edit、write、grep、find、ls） | 所有 run、doctor | tests/stub_pi.py:33-35；tests/stub_pi_help.txt:13, 40, 177-185 |
| `--version` | 输出 `0.87.0` | 预检 | tests/stub_pi.py:36-38 |
| `auth` | 输出 JSON `{status, provider, model[, error=STUB_AUTH_DETAIL]}`；ready 时 exit 0，否则 exit 1 | test_preflight_and_budget、test_v21 | tests/stub_pi.py:39-45 |
| `--list-models [pattern]` | `STUB_LIST_FAIL=1`：stderr 带出 DEMO_TOKEN 和 EPERM，exit 1<br>列表为空：输出 `No models available…`，exit 0<br>没有匹配：输出 `No models matching "…"`，exit 0<br>否则输出以 `provider    model` 开头的表格。调度器传入的 pattern 就是 model，按子串匹配 | test_setup_wrapper_doctor、test_preflight_and_budget | tests/stub_pi.py:46-65 |
| 冒烟消息 | 没有 `@` 文件但带消息时：消息含 smoke.txt 则写入再读取，回复 `DONE`，否则回复 `PI_SMOKE_OK`；usage input 为 10 | test_setup_wrapper_doctor（smoke） | tests/stub_pi.py:76-97 |
| 任务运行的前置条件 | `@` 附带内容必须同时含 `TASK:` 和 `执行说明`，否则 exit 3 | 所有 run | tests/stub_pi.py:98-100 |
| 公共事件序列 | session(v3)、agent_start、turn_start、system 消息、toolUse assistant（start、update、end）、写入两个文件、[场景]、turn_end、turn_start、最终消息（start、end）、turn_end、agent_end、agent_settled<br>每条 assistant 消息：usage 1000/200/1200，cost 0.00043 | ok（默认） | tests/stub_pi.py:72, 125-146, 210-235 |
| scope | 改 README.md 和 package.json（加 left-pad），直接写 .env，发出 bash `git push origin HEAD`（isError） | test_scope:348 | tests/stub_pi.py:147-153 |
| error | 最终消息 content=[]，stopReason 为 error，errorMessage 为 `429 rate limited`；进程仍 exit 0 | test_events_and_thinking:369 | tests/stub_pi.py:225-226 |
| model / startfail / nosettle | model：实际模型为 `stepfun/step-3.5-flash`<br>startfail：发出 session 后 stderr 报错并 exit 1<br>nosettle：不发 agent_settled | test_events_and_thinking:382-384 | tests/stub_pi.py:102, 73-75, 233-234 |
| noreport / textcall | 最终文本分别为 `Done.` 和 Hermes 风格的 `<tool_call>` | test_events_and_thinking:397；test_feedback_v12:1095 | tests/stub_pi.py:221-224 |
| hang | 启动孙进程 sleep 600，写 `child.pid`，自身 sleep 600 | test_timeout:430；test_dispatcher_killed:447 | tests/stub_pi.py:206-209 |
| commit / outside / touchmain / planner | commit：在 worktree 内 `git add -A` 后提交<br>outside：写 `STUB_MAIN_REPO/leak.txt`（发 write 事件）<br>touchmain：改写主仓库 README.md<br>planner：写 `.agent/plans/next-task.v1.md`<br>后两者不发事件 | test_commit_outside_main:406-415；test_feedback_v11:861 | tests/stub_pi.py:154-157, 182-184, 171-172, 192-194 |
| readplan / typo | readplan：读取 files[0]，也就是 plan.md（调度器先附 plan.md，后附 instruction.md）<br>typo：edit 访问 `<cwd 的父目录>/<名>-typo/src/normalize.py`，isError | test_feedback_v11:838, 846 | tests/stub_pi.py:185-191 |
| ambiguous / conflict / checkonly | 追加一条只发 message_end 的思考消息；conflict 另在报告中带 `contract_conflicts` 1 条，D01 为 blocked | test_feedback_v12:939, 957；test_v21:1593 | tests/stub_pi.py:195-205, 216-219 |
| tmpclean / tempsequence | 分别发出 5 条和 54 条 bash 命令事件，只作证据，不执行。**tempsequence 未列入 docstring** | test_feedback_v12:1161, 1188 | tests/stub_pi.py:158-170, 173-181 |

环境变量：

| 变量 | 默认值 | 作用 | 来源 |
|---|---|---|---|
| `STUB_SCENARIO` | `ok` | 选择场景 | tests/stub_pi.py:67 |
| `STUB_MODELS` | `step step-5-preview` | 条目以 `;` 分隔，每条用空白分开 provider 与 model | tests/stub_pi.py:53 |
| `STUB_AUTH` | `ready` | 凭据检查结果 | tests/stub_pi.py:40 |
| `STUB_AUTH_DETAIL` | 无 | auth 输出中的 error 字段 | tests/stub_pi.py:42-43 |
| `STUB_LIST_FAIL` | 无 | 为 1 时 `--list-models` 失败 | tests/stub_pi.py:47 |
| `STUB_PTL` | 无 | assistant 消息中的 providerThinkingLevel | tests/stub_pi.py:112-113 |
| `STUB_NOCOST` | 无 | 为 1 时 cost 各项为 0，调度器据此判为 unknown，total 为 null | tests/stub_pi.py:105-106；scripts/pi_dispatch.py:2334-2336, 2392 |
| `STUB_MAIN_REPO` | 无 | outside、touchmain、planner 必需，缺少时 KeyError | tests/stub_pi.py:172, 183, 193 |

**stub 不覆盖真实启动入口。** 所有测试都经 `PI_DISPATCH_PI_CMD` 的 JSON 数组接入（scripts/pi_dispatch.py:1762-1770）。补充两点：
- `PI_DISPATCH_PI_CMD` 不是 JSON 时，会被当作单个可执行路径接受（:1764-1767）；只有解码成 JSON 但不是非空字符串数组时，才报 EXIT_USAGE。
- `PATH 中找不到 pi` 的退出码为 3（:1771-1773）。

以下路径没有测试：
- `shutil.which("pi")` 查找
- Windows 下从 npm `.cmd` 包装解析出 node 和入口脚本（:1774-1786）
- `ensure_argv_safe` 拒绝批处理特殊字符（:1789-1795）

stub 也不模拟以下情况，并且不校验收到的 `--thinking`、`--tools`、`--mode`、`--no-session` 及 RESOURCE_FLAGS：
- stderr 警告（`Using custom model id`、`Invalid thinking level`、`Unknown option`）
- compaction、自动重试、`thinking_level_changed`
- 截断或不可解析的事件行
- pi 版本低于 0.80.4

### 8.3 测试函数清单

依赖缩写：G=git 仓库，W=git worktree，B=bash，P=后台或并发进程，K=读取 kit 工作区的真实文件。

| ID | 函数（file:line） | 旧行为区域 | check 数：静态 / 运行时（Windows） | 代表性 check | stub 场景 / 环境变量 | 平台分支 | 依赖 |
|---|---|---|---|---|---|---|---|
| LB-TEST-001 | test_happy（tests/test_dispatch.py:241） | 完整生命周期：validate → run → 事件 → 领取 → 候选 → check（原地和 --fresh）→ verdict → branch → metrics → cleanup → mark | 18 / 18 | "events complete via agent_settled"、"candidate roundtrip verified"、"branch tree == candidate tree" | ok | 无 | G W |
| LB-TEST-002 | test_candidate_drift_and_artifacts（:287） | 候选漂移（EXIT_DRIFT=4）、缓存产物、检查产生新文件时 G4 失败 | 5 / 5 | "in-place check refuses unexpected extra file"、"PASS refused when checks created files (G4)" | ok | 无 | G W |
| LB-TEST-003 | test_cleanup_protects_unsaved_work（:315） | cleanup 保护候选之外的改动 | 2 / 2 | "cleanup refuses when candidate files were modified" | ok | 无 | G W |
| LB-TEST-004 | test_budget_race（:330） | 并发领取最后一次额度；失败一方的退出码（3）没有断言 | 1 / 1 | "exactly one attempt claims the last budget slot" | ok | 无 | G W P |
| LB-TEST-005 | test_scope（:346） | 范围违规、依赖变更、新增被忽略路径、git 写操作、G2、REVISE、rework 分支。G3 同样失败（scripts/pi_dispatch.py:4232），但没有断言 | 7 / 7 | "PASS refused on scope violation (G2)" | scope | 无 | G W |
| LB-TEST-006 | test_events_and_thinking（:367） | 事件完整性、G1、豁免、实际模型、思考级别、费用 unknown、缺少报告 | 7 / 11 | "PASS refused on G1"、"events case model {}" | error、model、startfail、nosettle、STUB_PTL=low、STUB_NOCOST=1、noreport | 无 | G W |
| LB-TEST-007 | test_commit_outside_main（:404） | HEAD 移动、越界写入、主工作区变化 | 6 / 6 | "HEAD moved is a violation" | commit、outside、touchmain + STUB_MAIN_REPO | 无 | G W |
| LB-TEST-008 | test_timeout（:425） | 超时状态与孙进程回收（kill_method：Windows 为 job-object，其他平台为 process-group，scripts/pi_dispatch.py:670, 675） | 3 / 3 | "timeout -> TIMEOUT state" | hang；kill_grace_seconds=2；`--timeout 6` | `alive` / `kill_hard`：Windows 用 tasklist / taskkill（:66-91） | G W P |
| LB-TEST-009 | test_dispatcher_killed（:443） | 调度器被强杀后的回收与恢复；恢复时合成 interrupted=True，多半得到 CANCELLED，但断言不锁定 | 4 / Windows 3、Linux 3、其他 2 | "Job Object reaps pi and grandchild"、"recover after dispatcher death" | hang | Windows：`taskkill /F`（不带 /T）后断言 Job Object 回收；Linux：断言 PDEATHSIG；其他平台只打印 NOTE（:457-470） | G W P |
| LB-TEST-010 | test_stuck_states（:479） | 已领取未启动的恢复；PREPARING 强制放弃；状态由 `pd.set_state` 或手工建 claim/ 注入 | 3 / 3 | "claimed-but-not-started attempt recovers as INFRA_FAILURE" | 无（不启动 pi） | 无 | G W |
| LB-TEST-011 | test_preflight_and_budget（:495） | 预检（模型、凭据，均为码 3）、环境变量冲突（EXIT_USAGE=2）、次数预算（3）、允许列表固定思考级别（prepare 阶段，3） | 7 / 7 | "model not listed -> preflight fail, stays PREPARED"、"budget: 3rd attempt refused" | STUB_MODELS、STUB_AUTH=not_ready、PI_EXEC_MODEL | 无 | G W |
| LB-TEST-012 | test_validate（:520） | 合同拒绝原因（validate 返回 EXIT_USAGE=2）、Markdown/JSON 一致性、.gitignore 前置条件（prepare 返回 EXIT_BLOCKED=3）、示例合同 | 3 / 18 | "argv change detected"、"placeholder rejected" | 无 | 无 | G K |
| LB-TEST-013 | test_output_paths（:584） | `--out` 路径保护（EXIT_USAGE） | 3 / 3 | "metrics --out README.md refused, README untouched" | ok | 无 | G W |
| LB-TEST-014 | test_units（:597） | glob fullmatch、invalid_path、on_spawn 失败处理 | 3 / 3 | "on_spawn failure terminates the child (Codex #2)" | 无 | alive() | P（不建 git 仓库） |
| LB-TEST-015 | test_repo_config_features（:625） | 仓库级受保护路径、提交尾注 | 6 / 6 | "branch commit carries executor and trailers" | ok | 无 | G W |
| LB-TEST-016 | test_wrapper_interpreters_and_literal_arguments（:656） | dispatch-pi.sh 的解释器选择与参数原样传递 | 2 / **0**（POSIX 上为 4 × shell 数） | "wrapper preserves argv and exit code via %s: %s" | 无 | Windows 上直接 `return`（:658-659） | B、符号链接（仅 POSIX） |
| LB-TEST-017 | test_setup_wrapper_doctor（:701） | setup、bash 包装、doctor 的模型列表与脱敏、smoke（在系统临时目录 `pi-smoke-*` 中运行，scripts/pi_dispatch.py:4778） | 11 / 11（找不到 bash 时 10） | "doctor reports a failing list-models run as such" | STUB_LIST_FAIL、三种 STUB_MODELS 取值、smoke | Windows 优先使用 `C:\Program Files\Git\bin\bash.exe`；找不到 bash 时静默跳过（:710-714） | G W B |
| LB-TEST-018 | test_feedback_v11（:814） | 计划路径、不可见字符、status、运行目录读取、越界失败、规划路径、范围重叠、baseline、derive-json、只读 git 命令识别 | 28 / 28 | "baseline flags a probe that already passes on base" | ok、readplan、typo、planner | 无 | G W |
| LB-TEST-019 | test_feedback_v12（:936） | 合同矛盾提示、SUPERSEDED、文本工具调用导致 G1 失败、分支主题、缓存清理、可疑命令、临时路径证据 | 34 / 34 | "ambiguity detector handles negation and context"（63 条语句合在 1 个 check 中） | ambiguous、conflict、textcall、tmpclean、tempsequence | 无 | G W |
| LB-TEST-020 | test_mutate（:1220） | mutate 的抓住、漏掉、跳过；拒绝无效 spec（退出 2）；基线失败时中止 | 7 / 7 | "mutate reports caught / missed / skipped" | ok | 无 | G W（spec 写在 WORK 下） |
| LB-TEST-021 | test_v2_planner_adapters（:1275） | 技能副本同步、规划端文件提示、wait 退出码 | 18 / 18 | "wait times out on a running attempt with exit code 3" | ok | 无 | G W K |
| LB-TEST-022 | test_v2_review_fixes（:1380） | 链接与 junction 边界、缺失源、wait 读不到状态 | 22 / 12–16（推断：Windows 上 junction 不需要特权，第 2–5 组多半会真实执行；文件符号链接取决于权限） | "wait does not report an unreadable state as finished" | ok | `_dir_link` / `_junction_or_link`（:1344-1370）；建不了链接时 `check(..., True)` 空通过 | G W、链接 |
| LB-TEST-023 | test_v21_codex_trial_feedback（:1531） | 临时路径识别、脱敏、模型表解析、预检脱敏、规则文本一致、尾注、Git 身份 | 27 / 29 | "branch refuses before rebuilding the tree or creating anything when the identity is missing" | checkonly；STUB_AUTH 与 STUB_AUTH_DETAIL；GIT_CONFIG_GLOBAL、GIT_CONFIG_NOSYSTEM | 无平台分支；:1741 的 chmod 0o600 无条件执行（为 Windows 只读对象文件准备） | G W K |
| LB-TEST-024 | test_v22_netperf_feedback（:1782） | base_sha 落后的分级、集成命令提示、固定 autocrlf、line_endings_only、setup 说明、`变异检查（mutate）` 提示（断言针对 instruction **全文**）、Repository facts、`commit=` 行 | 17 / 17 | "verdict PASS survives a later autocrlf change (snapshot pinned to the recorded value)" | ok | 无 | G W |

合计：24 个函数，静态 244 处 `check(`。Windows 上运行时总数按源码推算为 **252–256**，前提是找到 bash、没有函数抛异常；差值来自 LB-TEST-022，未经运行核实。任一函数抛异常时，它剩余的 check 不再计入，另加 1 条异常记录。

### 8.4 C.4 旧回归覆盖映射

| C.4 项 | 覆盖的测试与 check（tests/test_dispatch.py:行） | 覆盖性质 | 未覆盖部分（scripts/pi_dispatch.py:行） |
|---|---|---|---|
| 旧合同默认值 | 没有直接断言。间接：test_units 在 :602 调用 normalize_contract，只用于准备输入；setup 省略 expected_exit_code（:702-703、:1856） | **缺口** | normalize_contract 的全部默认值（:1189-1213）：<br>- executor：thinking=DEFAULT_THINKING="high"、tools=DEFAULT_TOOLS 7 项（:66-67）、context_files=project<br>- scope：各列表为空，dependency_changes=forbidden<br>- authorization：executor=[local_edit, local_test]，integration=[]<br>- budget：2/1200/2400/None<br>- setup、checks、definition_of_done 缺省为 []<br>- checks 默认 cwd="."、required=True、expected_exit_code=0；setup 默认 cwd="."、expected_exit_code=0 |
| Markdown/JSON 一致性 | test_validate：只改 JSON 的 5 例（:547-559，check 在 :529）、:543、:545<br>test_feedback_v11：:898、:901、:906<br>test_feedback_v12：:1091、:1216<br>test_happy：:254<br>test_v22：:1876、:1882、:1895 | 直接 | JSON 中 scope 各列表、DoD、checks 其余字段的不一致；改 Markdown 而 JSON 不变的方向；拒绝顺序；多个缺陷同时存在 |
| 范围检查 | test_scope：:350、:351、:353、:359<br>test_units：:607<br>test_repo_config_features：:634、:638<br>test_validate：:533-535<br>test_commit_outside_main：:408<br>范围重叠：:877、:1062、:1066、:1082 | 直接 | 删除越界（allowed_deleted_files）；文件模式变化；大小写不同的受保护路径；真实的非 UTF-8 文件名（只注入了 path_decode_error 字段） |
| G0–G6 | G1：:374、:1101；豁免 :378<br>G2：:359<br>G3：只断言过 NOTE（:954）。失败在 test_scope 中实际发生（:4232），但没有断言<br>G4：:312（:4215）<br>G6：只有正向 :1835 和单元测试 :1851<br>全部通过：:271 | **部分** | G0 失败（:4161、:4163）<br>G1 的缺少 run.json、超时、取消、非 0 退出码（:4168-4174）<br>G3 失败的断言（:4204、:4232、:4236）<br>G4 的无有效检查记录（:4205）、不是针对当前候选（:4209）、未覆盖必要检查（:4211）、修改候选文件（:4213）、必要检查失败（:4227）<br>G5 只有固定提示（:4154）<br>G6 失败（:4244、:4248、:4253、:4255）<br>G2 的 notes（:4196、:4199）没有经 verdict 断言 |
| 候选树漂移 | :294（EXIT_DRIFT）、:296、:302、:324、:327、:1252、:1830-1837、:1851 | check 与 cleanup 层直接覆盖 | check 前修改候选文件（drift_before.modified）；verdict 时的 G6 漂移失败；G6 中多出文件只写入 notes（:4250） |
| 补丁往返与完整性 | :259、:264、:273、:275、:1748、:1770、:1837 | 只有正向用例 | candidate.patch 缺失、被篡改、sha256 不符、往返失败（:3988-3989、:4255） |
| 锁与预算竞争 | :342（并发领取）、:510（次数预算）、:257（预留时长）、:499（预检失败不领取） | 部分 | TaskLock 等待 30s 超时、300s 过期锁清理（:2583-2613）；墙钟预算耗尽（:3186-3188、:3305-3306）；`--timeout` 被预算截短；allowed_executors 未命中 |
| 超时 | :433、:434、:438、:622、:1335 | 直接 | 检查命令和 setup 超时；超时后 verdict 的 G1 失败（:4170） |
| 取消 | 没有信号用例。test_dispatcher_killed 的 `collect --recover` 在缺少 run.json 时合成 interrupted=True（:3430），collect 据此多半走 CANCELLED 分支（:3399-3400），但 :476 同时接受 INFRA_FAILURE | **缺口**（该分支可能被执行，但没有断言） | 信号经 `_Interrupted` 进入中断分支（:576、:703-706）；G1“运行被取消或调度器中断”（:4172）；main 的 KeyboardInterrupt 输出“已取消。”并返回 130（:4969-4971，run 期间的 SIGINT 走 `_Interrupted`） |
| 进程恢复 | :464（Windows）、:466（Linux）、:474、:476、:485、:487、:492 | 直接，但断言宽松 | pid 存活时拒绝恢复（:3424-3425）；COLLECTING 状态的恢复；`.partial` 重命名（:3436-3439）；非可恢复状态或缺 `--recover` 时的 EXIT_USAGE（:3418-3420）；非 Windows、非 Linux 平台上的调度器被强杀场景（test_timeout 的孙进程回收断言仍对所有平台有效） |
| 实际模型与思考级别证据 | :251、:393（model 例和 STUB_PTL 例）、:499、:504、:514、:517、:532（check 在 :529）、:717-746、:1685、:647、:1770 | 直接 | 预检的思考级别、工具名、版本、低于 0.80.4 的分支（:2032、:2037、:2043、:2045）；不支持的参数；doctor 的“思考级别不受本机 pi 支持”（:4726）；stderr 警告（:261-266、:2363-2365）；提供商回报的思考级别与要求一致的正例 |
| wait 与退出码语义 | wait：:1332（0）、:1335（3）、:1341（3）、:1524（1）<br>其他：:294（4）、:309（1）、:370（1，但状态为 NEEDS_REVIEW）<br>EXIT_USAGE（2）：:589、:592、:653、:1760、:1764、:1262<br>sync-adapters 退出 1：:1296、:1305、:1397、:1399<br>wrapper：:694、:697（仅 POSIX） | 直接 | wait `--timeout<1` 的 EXIT_USAGE（:3926-3927）；state.json 缺失（UNKNOWN，:2554-2555）只测了损坏；main 返回 130；多数拒绝只断言“非 0”，没有锁定默认码 3 |

退出码常量与规则（源码事实）：
- `EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_BLOCKED, EXIT_DRIFT = 0, 1, 2, 3, 4`（:53）。
- DispatchError 的默认码是 EXIT_BLOCKED（:304-309）；main 把 `ERROR: …` 写到 stderr 并返回该码（:4966-4968）。
- wait 的“仍在运行 / 未开始”复用 EXIT_BLOCKED（:3937、:3942）。
- run 只有在 NEEDS_REVIEW 且 events ok 时退出 0，否则退出 1（:3349）。

### 8.5 基线取证时要注意

1. 汇总为 `0 checks, 0 failed` 时退出码也是 0；测试名拼错也会被静默忽略。这两种情况都不能记为基线 PASS。
2. 汇总之后的清理异常会让进程以 1 退出；KeyboardInterrupt 不会产生汇总行。判定时要同时看汇总行和退出码。
3. LB-TEST-022 在建不了链接时产生空通过的 check，需要按 check 名称区分“未执行”和“通过”。
4. LB-TEST-016 在 Windows 上没有任何 check；LB-TEST-009 在非 Windows、非 Linux 平台上没有回收断言。
5. 以下测试依赖 kit 工作区：导入与复制脚本、LB-TEST-012、LB-TEST-021、LB-TEST-023。输入清单要包含 `scripts/pi_dispatch.py`、`scripts/dispatch-pi.sh`、AGENTS.md、`.agents/skills/**`、`.claude/skills/**`、`tests/stub_pi*.{py,txt}` 的哈希，并记录未跟踪的 `scripts/codekit/`。
6. 以下样本合在单个 check 中，失败粒度比 check 数显示的更粗：63 条歧义语句、34 个凭据样本、25 个临时路径样本、7 例分支主题、9 例缓存清理。
7. 测试继承宿主的全部环境变量（只删掉少数几个）；LB-TEST-023 的 Git 身份隔离依赖本机 git 配置层级。基线要记录 git 版本和相关环境。
8. 多处状态由 `pd.set_state` 直接注入：LB-TEST-010、LB-TEST-019、LB-TEST-021。这些不等于真实的崩溃或运行路径。

### 8.6 与 3.2 最低记录单位的对应

本节从源码提供了以下字段：
- `legacy_behavior_id`：LB-TEST-*
- `source_location`：file:line
- `full_source_revision`：a4fa199 加工作区哈希，后者待 01-T1 计算
- `input_fixture_ref`：make_repo、contract()、stub 场景与环境变量
- `legacy_command_or_test_id`：函数名加 check 名
- `platform_scope`
- `evidence_basis`：source_inspected

`legacy_observation`、`execution_status` 需要 01-T1 受控运行后才能填写；`comparison_projection_revision`、`new_consumer_module`、`acceptance_ids` 不在旧源码中，本节不填写。

### 未解决事项（第 8 节）

- 运行时 check 总数（Windows 上按源码推算为 252–256）没有经过运行核实；本机能建哪类链接（目录符号链接、junction、文件符号链接）只能从运行输出的 check 名称判断。
- G0 失败、G1 的非事件路径（缺少 run.json、超时、取消、非 0 退出码）、G3 失败、G4 除“产生新文件”之外的原因、G5、G6 失败，都没有断言。G3 失败在 test_scope 中实际发生但没有断言。仅凭旧测试不能满足 01-A07 的逐条映射。
- 取消语义没有测试：信号经 _Interrupted 进入中断分支、G1“运行被取消”、main 返回 130。test_dispatcher_killed 的恢复多半经过 CANCELLED 分支，但断言同时接受 INFRA_FAILURE，结果没有锁定。
- normalize_contract 的默认值没有直接断言；旧合同默认值的回归需要新增样本，否则记为 NOT_COVERED。
- 补丁完整性没有负向用例：candidate.patch 缺失、被篡改、sha256 不符、往返失败都没有测试。
- TaskLock 等待超时、过期锁清理、max_wall_seconds_total 墙钟预算耗尽、allowed_executors 未命中，都没有测试。
- stub 不覆盖真实 pi 的启动入口：PATH 查找、Windows .cmd 包装解析、ensure_argv_safe、PI_DISPATCH_PI_CMD 非 JSON 或非法 JSON 都没有测试。stub_pi_help.txt 与真实 pi 0.87 的帮助是否一致无法核实（不允许调用 pi）。
- 预检的“不支持的参数”“思考级别不在列表中”“未知工具名”“版本不可读或低于 0.80.4（退回 agent_end 判断）”、doctor 的思考级别检查，以及 stderr 警告模式，都没有测试。
- Windows 上 dispatch-pi.sh 的参数原样传递、解释器回退和退出码透传没有测试（test_wrapper_interpreters_and_literal_arguments 在 Windows 上直接 return）。
- stub_pi.py 的 docstring 没有列出已实现的 tempsequence 场景。
- 测试名不存在或拼错时输出 0 checks 并退出 0；汇总之后的清理异常会把退出码变成 1。基线规则需要显式处理这两种情况。
- kit 工作区的前提目前经只读核对成立，但没有运行 adapter_drift。工作区还有未跟踪的 scripts/codekit/，基线输入清单必须记录这些文件的哈希。
- test_v21 的 Git 身份隔离（GIT_CONFIG_GLOBAL 置空加 GIT_CONFIG_NOSYSTEM=1）在本机 Git for Windows 上是否完全生效，需要运行确认。
- 清理阶段的 git worktree prune 是否真的修剪过任何条目，只是推断，没有源码或运行证据。
- 3.2 要求的 legacy_observation、comparison_projection_revision、new_consumer_module、acceptance_ids 无法从旧源码得到，需要 01-T1 受控运行和后续模块补齐。

## 9. 回归映射表

### 9.1 列说明

- 每条 legacy_behavior_id 一行，按区域分表。前 194 条来自 6 个区域的结构化条目；各区域末尾标“核对者补充条目”的 30 条是核对者新增编号的条目，没有登记 related_tests，一律 source_inspected / NOT_RUN。
- **source_location**：文件:行，全部指提交 `a4fa199b0e5bdc658215765ee7558b9fe6723940` 中的文件（工作区 blob 与 HEAD 相同）。
- **legacy_command_or_test_id**：命令统一为 `python tests/test_dispatch.py`；列中是 `测试函数` 与 “check 名”。一个函数的全部 check 都相关时写“全部 N 个 check”。
- **legacy_observation**：条目标题，规则全文见括号中的区域章节；measured 行的观测是所列 check 在本次运行中 PASS。
- **new_consumer_module / acceptance_ids**：规划端按文档 4.4.1 与 7.1/7.2 的初判，需各模块确认。模块：02 配置与 profiles、03 审核与锁、04 CLI 适配器与 Pi、07 工作流与调度、09 规划与合同、10 项目状态。
- **evidence_basis / execution_status**：按 0.2。measured / PASS 只说明所列 check 的断言在 Windows 上成立。
- input_fixture_ref 与 comparison_projection_revision 本文不填写（见 0.4）。**完整性审查更新（2026-09-26）**：两列的按行回填见 9.10，下表各行原文不改。 **收尾轮更新（2026-09-26）**：按裁决 R-P12 的逐行回填（manifest 与代码内联两种 input_fixture_ref）与新统计见 9.10.6。

### 9.2 LB-CONTRACT：v1 合同规范化与校验（第 3 节）

共 36 条（结构化条目 28，核对者补充 8）：measured/PASS 27，source_inspected/NOT_RUN 9。

| legacy_behavior_id | source_location（@a4fa199） | legacy_command_or_test_id | legacy_observation | new_consumer_module | acceptance_ids | platform_scope | evidence_basis / execution_status | 备注 |
|---|---|---|---|---|---|---|---|---|
| LB-CONTRACT-001 | scripts/pi_dispatch.py:49、55、56、57、58、59、60、61 | `test_feedback_v11` “bad plan key still explains the format” | 标识正则与 schema 版本常量（§3） | 09 | 01-A02、01-A08、01-A09 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-CONTRACT-002 | scripts/pi_dispatch.py:65、66、67、68、71、72、73、74、83-85、88-92 | `test_validate` “invalid thinking rejected”、“codex config dir is protected” | 枚举词表、受保护模式与必需章节（§3） | 09 | 01-A02、01-A07 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-CONTRACT-003 | scripts/pi_dispatch.py:1189-1214、1193、1194-1195、1196、1197-1198、1205-1206、1207-1208 | `test_units` “control chars / decode errors are invalid_path violations”<br>`test_feedback_v11` “derived scope and DoD” | normalize_contract 的 schema v1 缺省值（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-CONTRACT-004 | scripts/pi_dispatch.py:1191、1200-1213、1161、1167、1169-1171、1174、1183、2653-2656 | `test_validate` “wrong executor type reported, no crash” | 缺省值补齐方式与读取时缺省（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-CONTRACT-005 | scripts/pi_dispatch.py:1432-1437、1178-1182 | `test_validate` “wrong executor type reported, no crash”、“non-string authorization items, no crash (Codex #11)”、“non-string evidence items, no crash” | validate_contract 的异常包装与未捕获异常（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-CONTRACT-006 | scripts/pi_dispatch.py:1444-1446、1447-1448、1450-1458、1634 | `test_validate` “wrong executor type reported, no crash” | 校验前置的早退出顺序（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-CONTRACT-007 | scripts/pi_dispatch.py:1459-1469 | 无相关测试 | 顶层身份字段校验（§3） | 09 | 01-A02、01-A09 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：部分覆盖，见 9.9 |
| LB-CONTRACT-008 | scripts/pi_dispatch.py:1471-1481、1217-1218 | `test_validate` “non-string authorization items, no crash (Codex #11)” | authorization 校验（§3） | 09、03 | 01-A02 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-CONTRACT-009 | scripts/pi_dispatch.py:1483-1497 | `test_validate` “invalid thinking rejected” | executor 字段校验与 local_test 警告（§3） | 09、04 | 01-A02 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-CONTRACT-010 | scripts/pi_dispatch.py:1499-1526、1100-1113、1063-1093、990-995 | `test_validate` “protected path in scope rejected”、“codex config dir is protected”、“parent traversal rejected”<br>`test_repo_config_features` “repo-level protected path rejected in scope” | scope 路径模式与依赖策略校验（§3） | 09 | 01-A02、01-A07 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-CONTRACT-011 | scripts/pi_dispatch.py:1144-1186、1528-1531 | `test_feedback_v11` “invalid expect_on_base rejected” | setup/checks 命令项校验（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-CONTRACT-012 | scripts/pi_dispatch.py:1532-1563 | `test_validate` “contract without required checks rejected (Codex #13)”、“non-string evidence items, no crash” | 必要检查与 Definition of done 校验（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-CONTRACT-013 | scripts/pi_dispatch.py:1565-1580 | `test_validate` “budget change detected” | budget 校验（§3） | 09、07 | 01-A02 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-CONTRACT-014 | scripts/pi_dispatch.py:1583-1587、61 | `test_validate` “placeholder rejected” | 占位符拒绝（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-CONTRACT-015 | scripts/pi_dispatch.py:1588-1593、1120-1122 | `test_validate` “missing md section rejected” | Markdown 必需章节与标题行（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-CONTRACT-016 | scripts/pi_dispatch.py:1594-1611、1134-1141、1126-1131、1409-1413 | `test_validate` “integration change detected”、“thinking change detected”<br>`test_feedback_v12` “annotated single values are derived without the note” | Identity 一致性（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-CONTRACT-017 | scripts/pi_dispatch.py:1612-1633、1221-1228、1416-1429 | `test_validate` “argv change detected”、“budget change detected”、“forbidden path change detected” | Scope 路径、依赖策略、Budget、检查命令与 DoD 编号的一致性（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-CONTRACT-018 | scripts/pi_dispatch.py:1582、1634、3011-3039、2732-2733 | `test_validate` “argv change detected”、“thinking change detected” | Markdown/JSON 冲突时的优先级（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-CONTRACT-019 | scripts/pi_dispatch.py:1656-1690、966-967 | `test_happy` “validate ok”<br>`test_validate` “example normalize-query.v1 validates”、“example auth-refresh-401.v1 validates” | validate_plan 的文件层检查与整体顺序（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-CONTRACT-020 | scripts/pi_dispatch.py:1676-1687、768-770、1737-1750、1000-1008 | `test_v22_netperf_feedback` “base behind HEAD by planner paths only is a NOTE”、“base behind HEAD by code is still a WARN” | base_sha 的仓库核验与基线相关提示（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-CONTRACT-021 | scripts/pi_dispatch.py:1637-1653、1674-1675 | `test_feedback_v11` “invisible format character is warned” | 不可见格式字符警告（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-CONTRACT-022 | scripts/pi_dispatch.py:1696、1699-1734 | `test_v22_netperf_feedback` “validate warns about a Repository-facts file missing from the base”、“validate is quiet when every Repository-facts file exists in the base”、“validate resolves Repository-facts paths against each check cwd too” | Repository facts 文件在基线中缺失的警告（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-CONTRACT-023 | scripts/pi_dispatch.py:2999-3008、2988-2996、4953-4971、304-309、955-979、747-761 | `test_happy` “validate ok”<br>`test_setup_wrapper_doctor` “bash wrapper finds python”<br>`test_repo_config_features` “invalid commit_trailers config is ignored by validate” | validate 子命令的输出与退出码（§3） | 09 | 01-A02、01-A05 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-CONTRACT-024 | scripts/pi_dispatch.py:1327-1397、1400-1406、1310 | `test_feedback_v11` “derived checks keep argv, cwd, timeout and patterns”、“derived scope and DoD”<br>`test_feedback_v12` “annotated single values are derived without the note” | derive_contract_json 的生成规则（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-CONTRACT-025 | scripts/pi_dispatch.py:1231-1254、1257-1258、1261-1306 | `test_feedback_v11` “derived checks keep argv, cwd, timeout and patterns”、“derived scope and DoD” | derive-json 的 Scope 与命令行解析（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-CONTRACT-026 | scripts/pi_dispatch.py:3011-3039、4858-4863 | `test_feedback_v11` “derive-json writes a contract that validates”、“derive-json refuses to overwrite without --force”、“derive-json --print takes the title from Goal”<br>`test_feedback_v12` “derive-json notes a long title taken from Goal”、“no title note when --title is given” | derive-json 子命令的流程与退出码（§3） | 09 | 01-A02、01-A05 | windows 实测 | measured / PASS（5/5 check） |  |
| LB-CONTRACT-027 | scripts/pi_dispatch.py:1011-1028 | `test_feedback_v11` “validate accepts a relative md path”、“validate accepts an absolute json path”、“plan path outside .agent/plans rejected”、“bad plan key still explains the format” | 计划标识参数解析 plan_key_from_arg（§3） | 09 | 01-A02 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-CONTRACT-028 | scripts/pi_dispatch.py:3162-3175、4073-4084、2653-2656 | `test_validate` “prepare refuses when .agent/runs not ignored” | validate_plan 在 validate 之外的调用方（§3） | 09、07 | 01-A02 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-CONTRACT-029 | scripts/pi_dispatch.py:1670、1577-1580 | 未登记 | JSON 入口的宽松行为（重复键、NaN/Infinity、CRLF 规范化）（§3） | 09 | 01-A02、01-A04 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：未覆盖，见 9.9 |
| LB-CONTRACT-030 | scripts/pi_dispatch.py:1668、1670、1671、1180、1708、1718 | 未登记 | validate 入口未捕获的异常汇总（traceback、退出码 1）（§3） | 09 | 01-A02、01-A05 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |
| LB-CONTRACT-031 | scripts/pi_dispatch.py:1444-1446、1657-1658、1011-1028、1436-1437 | 未登记 | CLI 到达不了的报错分支（§3） | 09 | 01-A02 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |
| LB-CONTRACT-032 | scripts/pi_dispatch.py:3179-3180、3271、2445-2446、1673 | 未登记 | validate 不检查的内容（allowed_executors、敏感与依赖清单、路径存在性、其余配置键）（§3） | 09、02 | 01-A02 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：未覆盖，见 9.9 |
| LB-CONTRACT-033 | scripts/pi_dispatch.py:2670-2680、3271 | 未登记 | 运行时 resolve_executor 从 `PI_EXEC_*` 改写 executor 缺省值（源码推断）（§3） | 待定（候选 02、04） | 01-A02 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：未覆盖，见 9.9 |
| LB-CONTRACT-034 | scripts/pi_dispatch.py:4834-4835、4961-4963 | 未登记 | argparse 与 main 入口的退出码（缺参数/未知子命令 2、--version/-h 0、无子命令 2）（§3） | 待定（各入口模块） | 01-A05 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |
| LB-CONTRACT-035 | scripts/pi_dispatch.py:1152、1532、1573、1595-1598、1619-1622 | 未登记 | 合同校验的级联错误（§3） | 09 | 01-A02 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |
| LB-CONTRACT-036 | scripts/pi_dispatch.py:3031、1369、3026-3028 | 未登记 | derive-json 的额外可观测行为（Windows 上写出 CRLF、Unicode 数字崩溃、--print 早返回）（§3） | 09 | 01-A02 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：未覆盖，见 9.9 |

### 9.3 LB-EVENTS：Pi 预检、事件摘要与用量证据（第 4 节）

共 30 条（结构化条目 28，核对者补充 2）：measured/PASS 21，source_inspected/NOT_RUN 9。

| legacy_behavior_id | source_location（@a4fa199） | legacy_command_or_test_id | legacy_observation | new_consumer_module | acceptance_ids | platform_scope | evidence_basis / execution_status | 备注 |
|---|---|---|---|---|---|---|---|---|
| LB-EVENTS-001 | scripts/pi_dispatch.py:50、373、3245、2038、3288、3316、3427、4774、4689 | `test_events_and_thinking` “events case nosettle {}” | 最低 Pi 版本与 agent_settled 预期（expects_settled）（§4） | 04 | 01-A11 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-EVENTS-002 | scripts/pi_dispatch.py:1760、3277、4682、4767 | 无相关测试 | resolve_pi_command 定位 pi（§4） | 04 | 01-A15 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：部分覆盖，见 9.9 |
| LB-EVENTS-003 | scripts/pi_dispatch.py:1757、1789、3296、4791 | 无相关测试 | ensure_argv_safe 拒绝批处理特殊字符（§4） | 04 | 01-A15 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：未覆盖，见 9.9 |
| LB-EVENTS-004 | scripts/pi_dispatch.py:1798、1803、1808、1816、3279、4751 | 无相关测试 | pi_agent_dir 与 context_evidence 上下文文件取证（§4） | 04 | 待定 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：未覆盖，见 9.9 |
| LB-EVENTS-005 | scripts/pi_dispatch.py:1860、1874、1889、68 | `test_v21_codex_trial_feedback` “model table parsing ignores pi's no-model messages”<br>`test_setup_wrapper_doctor` “doctor explains that pi has no models at all”、“doctor explains that no model matches” | parse_help、list_models_rows、list_models_empty_reason 解析规则（§4） | 04 | 01-A02 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-EVENTS-006 | scripts/pi_dispatch.py:2014、69、70、393、351 | `test_preflight_and_budget` “model not listed -> preflight fail, stays PREPARED”、“auth not ready -> preflight fail”<br>`test_v21_codex_trial_feedback` “preflight records and output are redacted” | pi_preflight 步骤顺序与产物文件（§4） | 04 | 01-A02 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-EVENTS-007 | scripts/pi_dispatch.py:2023、2029、2031、2034、2042、2051、2061 | `test_preflight_and_budget` “model not listed -> preflight fail, stays PREPARED”、“auth not ready -> preflight fail”<br>`test_v21_codex_trial_feedback` “preflight records and output are redacted” | 预检每种失败的 problems / notes 原文（§4） | 04 | 01-A02 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-EVENTS-008 | scripts/pi_dispatch.py:3277、3281、3286、2547、307、4966 | `test_preflight_and_budget` “model not listed -> preflight fail, stays PREPARED”、“auth not ready -> preflight fail”、“run after fixing env” | 预检失败在 run 中的结果（§4） | 04、07 | 01-A08 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-EVENTS-009 | scripts/pi_dispatch.py:2172、2201、2308、2339、2367 | 无相关测试 | 事件流逐行解析、解析失败与截断（§4） | 04 | 01-A11 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：已覆盖（Windows measured / PASS），见 9.9 |
| LB-EVENTS-010 | scripts/pi_dispatch.py:2076、2078、2212、2216、2218、2231、2235、2239、2288、2294、2299、2302 | `test_happy` “usage sums assistant message_end only”<br>`test_scope` “git push flagged”<br>`test_commit_outside_main` “outside path flagged”<br>`test_feedback_v11` “reading the attached plan.md is not an outside access”、“failed outside access is marked failed and missing” | summarize_events 识别的事件类型（§4） | 04 | 01-A11 | windows 实测 | measured / PASS（5/5 check） |  |
| LB-EVENTS-011 | scripts/pi_dispatch.py:2214、2294、2299、2309、2345 | `test_happy` “events complete via agent_settled”<br>`test_events_and_thinking` “events case nosettle {}” | 事件流完整性判定（complete / terminal_event）（§4） | 04 | 01-A05、01-A11 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-EVENTS-012 | scripts/pi_dispatch.py:2096、2319、2333、2353、2357、299 | `test_events_and_thinking` “error stopReason -> exit 1 but NEEDS_REVIEW”、“PASS refused on G1”<br>`test_feedback_v12` “textual tool call in the final message is an integrity problem”、“PASS is refused when the run ended on a textual tool call”<br>`test_v21_codex_trial_feedback` “a long final error is redacted before it is cut” | 最终 assistant 消息相关问题（§4） | 04 | 01-A02 | windows 实测 | measured / PASS（5/5 check） |  |
| LB-EVENTS-013 | scripts/pi_dispatch.py:2323、2324、2325、2328、2361、2376 | `test_events_and_thinking` “events case model {}”、“events case startfail {}” | 实际模型证据（actual_models / model_match / response_models）（§4） | 04 | 01-A02 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-EVENTS-014 | scripts/pi_dispatch.py:2326、2337、2350、2380、4177、2031 | `test_happy` “thinking not reported -> evidence says so, no problem”<br>`test_events_and_thinking` “events case ok {'STUB_PTL': 'low'}” | 思考级别证据（provider_thinking_levels / thinking_evidence）（§4） | 04 | 01-A02 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-EVENTS-015 | scripts/pi_dispatch.py:261、2329、2363、2954 | 无相关测试 | stderr 警告标记（§4） | 04 | 01-A02 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：已覆盖（Windows measured / PASS），见 9.9 |
| LB-EVENTS-016 | scripts/pi_dispatch.py:2075、2081、2179 | `test_happy` “usage sums assistant message_end only”<br>`test_events_and_thinking` “events case ok {'STUB_NOCOST': '1'}” | _add_usage 的精确累加语义（§4） | 04、07 | 01-A06 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-EVENTS-017 | scripts/pi_dispatch.py:2226、2228、2234、2238 | `test_happy` “usage sums assistant message_end only” | 用量来源与重复累加风险（§4） | 04、07 | 01-A06 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-EVENTS-018 | scripts/pi_dispatch.py:2179、2390、2872、4505、4615 | 无相关测试 | token 缺失时的旧输出为 0（§4） | 04、07 | 01-A06 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：已覆盖（Windows measured / PASS），见 9.9 |
| LB-EVENTS-019 | scripts/pi_dispatch.py:2334、2391、2392 | `test_happy` “usage sums assistant message_end only”<br>`test_events_and_thinking` “events case ok {'STUB_NOCOST': '1'}”、“status shows unknown cost” | 费用 total / status / unpriced_messages 规则（§4） | 04、07 | 01-A06 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-EVENTS-020 | scripts/pi_dispatch.py:2861、2872、2881、4494、4510、4607、4634、4796 | `test_events_and_thinking` “status shows unknown cost”<br>`test_setup_wrapper_doctor` “smoke both steps ok” | 模型、思考级别、用量与费用的下游呈现（§4） | 10、07 | 01-A06 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-EVENTS-021 | scripts/pi_dispatch.py:4166、4175、3395、3401、3348 | `test_events_and_thinking` “error stopReason -> exit 1 but NEEDS_REVIEW”、“PASS refused on G1”、“ACCEPTED_WITH_EXCEPTION with waiver”、“events case startfail {}” | 事件摘要对 G1、collect 状态与 run 退出码的影响（§4） | 03、07 | 01-A05、01-A07 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-EVENTS-022 | scripts/pi_dispatch.py:1900、1904、1907、1910、1914、1943、1971 | `test_v21_codex_trial_feedback` “embedded JSON keeps metadata and a JSON value of a secret key is masked whole”、“PEM blocks are masked whole, NUL and deep nesting are harmless”、“lone surrogates stay escaped so the output can be written as UTF-8”、“redact_secrets masks common credential forms”、“redacted JSON stays valid JSON”、“structured redaction keeps counts and flags”<br>`test_setup_wrapper_doctor` “doctor redacts credentials echoed by pi” | redact_secrets 文本脱敏规则（§4） | 04 | 01-A12 | windows 实测 | measured / PASS（7/7 check） |  |
| LB-EVENTS-023 | scripts/pi_dispatch.py:1926、2003、2021、2065、2245、2304、2356、2375、2415、4758、4818 | `test_v21_codex_trial_feedback` “preflight records and output are redacted”、“a long final error is redacted before it is cut”<br>`test_setup_wrapper_doctor` “doctor redacts credentials echoed by pi” | 结构脱敏与脱敏的应用范围（§4） | 04 | 01-A12 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-EVENTS-024 | scripts/pi_dispatch.py:2412、3361 | `test_events_and_thinking` “missing JSON report does not block PASS”<br>`test_feedback_v12` “report-status counts contract conflicts” | extract_report 执行报告抽取（§4） | 04、03 | 01-A02 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-EVENTS-025 | scripts/pi_dispatch.py:269、2106、2121、2322、4183 | `test_feedback_v12` “ambiguity mention in thinking is recorded”、“ambiguity detector handles negation and context”、“domain words come from the plan body, not stop conditions”、“domain words are skipped”<br>`test_v21_codex_trial_feedback` “a checking sentence is still mentioned, with a softened hint” | 歧义与矛盾提及（不参与判定）（§4） | 04、03 | 01-A02 | windows 实测 | measured / PASS（5/5 check） |  |
| LB-EVENTS-026 | scripts/pi_dispatch.py:2092、3344、3356、4964 | 无相关测试 | 非数值 totalTokens 使事件摘要抛出 TypeError（§4） | 04 | 01-A06、01-A11 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：部分覆盖，见 9.9 |
| LB-EVENTS-027 | scripts/pi_dispatch.py:4684、4694、4699、4719、4774、4796 | `test_setup_wrapper_doctor` “doctor ok with stub”、“doctor reports a failing list-models run as such”、“doctor explains that pi has no models at all”、“doctor explains that no model matches”、“a model listed under another provider keeps the short message”、“smoke both steps ok” | doctor、smoke 与预检的差异（§4） | 04 | 待定 | windows 实测 | measured / PASS（6/6 check） |  |
| LB-EVENTS-028 | tests/stub_pi.py:33、39、46、72、103、109、125、225、232；tests/test_dispatch.py:29 | `test_happy` “events complete via agent_settled”<br>`test_events_and_thinking` “events case nosettle {}” | stub_pi 的事件模拟范围与覆盖缺口（§4） | 04 | 01-A16 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-EVENTS-029 | scripts/pi_dispatch.py:4518-4548、4562-4564、3935-3936 | 未登记 | 运行中进度 _live_progress（按紧凑字节标记计数）（§4） | 07、10 | 01-A05 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；条目正文引用 tests/test_dispatch.py:1142-1155（test_feedback_v12 “live status flags a long stretch without tool calls”，本次 PASS），但未登记为 related_tests；**P4 更新**：已覆盖（Windows measured / PASS），见 9.9 |
| LB-EVENTS-030 | scripts/pi_dispatch.py:2366-2408、2339-2365、3360-3361 | 未登记 | events-summary.json 的字段集合、截断上限、problems 顺序与覆盖写（§4） | 04 | 01-A11 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |

### 9.4 LB-GATES：候选树、补丁、范围与 G0–G6（第 5 节）

共 38 条（结构化条目 38，核对者补充 0）：measured/PASS 35，source_inspected/NOT_RUN 2，source_reported/NOT_RUN 1。

| legacy_behavior_id | source_location（@a4fa199） | legacy_command_or_test_id | legacy_observation | new_consumer_module | acceptance_ids | platform_scope | evidence_basis / execution_status | 备注 |
|---|---|---|---|---|---|---|---|---|
| LB-GATES-001 | scripts/pi_dispatch.py:53、75、76、77、79、80、304、4964、4908 | `test_candidate_drift_and_artifacts` “in-place check refuses unexpected extra file”<br>`test_scope` “REVISE recorded” | 门禁、结论、失败分类枚举与退出码常量（§5） | 03 | 01-A05、01-A07 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-GATES-002 | .agents/skills/review-pi/gates.md:5；scripts/pi_dispatch.py:79 | 无相关测试 | 门禁名称只见于 review-pi/gates.md（§5） | 03 | 01-A07 | 源码层面 | source_reported / NOT_RUN | 只来自技能文档或 AGENTS.md 的说法；**P4 更新**：不适用（文档说法或旧自测夹具），见 9.9 |
| LB-GATES-003 | scripts/pi_dispatch.py:3210、773、780、805、825、3491、893 | `test_v22_netperf_feedback` “prepare records the effective core.autocrlf”、“check passes with autocrlf=true worktree”、“verdict PASS survives a later autocrlf change (snapshot pinned to the recorded value)”、“branch rebuilds the tree with the recorded autocrlf” | 行尾配置在 prepare 时固定（git_autocrlf / line_ending_args）（§5） | 待定（候选 07、10） | 01-A07、01-A15 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-GATES-004 | scripts/pi_dispatch.py:793、2518、4002、4240、4454 | `test_happy` “candidate roundtrip verified”、“branch tree == candidate tree” | 候选树快照 snapshot_tree（§5） | 待定（候选 07、10） | 01-A07 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-GATES-005 | scripts/pi_dispatch.py:2515、816、3365 | `test_happy` “candidate roundtrip verified”、“branch tree == candidate tree”、“branch parent == base” | record_candidate：补丁生成与往返校验（§5） | 待定（候选 07、10） | 01-A07 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-GATES-006 | scripts/pi_dispatch.py:3474、3987、3599、4254、4451 | `test_happy` “fresh check passes in clean copy and removes it” | 补丁完整性判定 candidate_patch_ok（§5） | 03 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-007 | scripts/pi_dispatch.py:3352、3395 | `test_happy` “run ok -> NEEDS_REVIEW”<br>`test_scope` “README out_of_scope”<br>`test_commit_outside_main` “HEAD moved is a violation” | collect 的候选与范围取证顺序、对状态的影响（§5） | 07 | 01-A07 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-GATES-008 | scripts/pi_dispatch.py:3436 | `test_dispatcher_killed` “recover after dispatcher death” | collect --recover 时旧候选证据的处理（§5） | 07 | 01-A07、01-A08 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-009 | scripts/pi_dispatch.py:833 | `test_units` “control chars / decode errors are invalid_path violations” | diff_raw 变更解析（§5） | 07 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-010 | scripts/pi_dispatch.py:864、858 | `test_v22_netperf_feedback` “line_endings_only recognises CRLF-only drift”<br>`test_candidate_drift_and_artifacts` “in-place check refuses unexpected extra file”<br>`test_cleanup_protects_unsaved_work` “cleanup refuses when candidate files were modified” | 候选漂移计算 tree_drift 与只差行尾判定 line_endings_only（§5） | 待定（候选 03、10） | 01-A07 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-GATES-011 | scripts/pi_dispatch.py:3458、3462、3468、4004、4456、4216 | `test_candidate_drift_and_artifacts` “python cache files are allowed artifacts”、“check creating unexpected file -> exit 1” | 缓存类文件（artifact）不算漂移（§5） | 待定（候选 03、07） | 01-A07 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-GATES-012 | scripts/pi_dispatch.py:3480、3989、3616 | `test_happy` “fresh check passes in clean copy and removes it”<br>`test_candidate_drift_and_artifacts` “fresh check ignores worktree extras”<br>`test_mutate` “mutate leaves the executor worktree and candidate untouched” | 干净验收副本 prepare_fresh_workspace（§5） | 待定（候选 03、07） | 01-A07 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-GATES-013 | scripts/pi_dispatch.py:3957 | `test_candidate_drift_and_artifacts` “in-place check refuses unexpected extra file”、“fresh check ignores worktree extras” | check 的前置条件与运行前候选漂移拒绝（§5） | 待定（候选 03、07） | 01-A05、01-A07 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-GATES-014 | scripts/pi_dispatch.py:4015、3065、1207 | `test_happy` “in-place check passes”、“fresh check passes in clean copy and removes it”<br>`test_candidate_drift_and_artifacts` “check creating unexpected file -> exit 1” | check 的结果记录与退出码（§5） | 待定（候选 03、07） | 01-A05、01-A07 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-GATES-015 | scripts/pi_dispatch.py:4073、4056 | `test_feedback_v11` “baseline runs checks on base without an attempt”、“baseline flags a probe that already passes on base”、“baseline record lists the mismatch”<br>`test_v22_netperf_feedback` “baseline explains a missing test file instead of implying a fix task” | baseline 在基线上跑检查（不参与门禁）（§5） | 待定 | 待定 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-GATES-016 | scripts/pi_dispatch.py:3585、3510、3564 | `test_mutate`（全部 7 个 check） | mutate 变异检查（不参与门禁）（§5） | 待定 | 待定 | windows 实测 | measured / PASS（7/7 check） |  |
| LB-GATES-017 | scripts/pi_dispatch.py:1063、1091、88、93、102、990、2444 | `test_units` “glob uses fullmatch (no trailing newline match)”<br>`test_repo_config_features` “repo-level protected path is a violation”、“repo-level protected path rejected in scope” | 路径模式语义、大小写与受保护/依赖/敏感清单（§5） | 09、03 | 01-A07 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-GATES-018 | scripts/pi_dispatch.py:2436 | `test_scope` “README out_of_scope”、“package.json forbidden + dependency”<br>`test_units` “control chars / decode errors are invalid_path violations”<br>`test_repo_config_features` “repo-level protected path is a violation” | evaluate_scope 逐文件判定顺序与输出（§5） | 03 | 01-A07 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-GATES-019 | scripts/pi_dispatch.py:2488、3367 | `test_commit_outside_main` “HEAD moved is a violation” | HEAD 移动的判定（§5） | 03 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-020 | scripts/pi_dispatch.py:1499、1194 | `test_repo_config_features` “repo-level protected path rejected in scope” | 合同阶段的范围静态校验（validate_plan）（§5） | 09 | 01-A02、01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-021 | scripts/pi_dispatch.py:2497、257、260、2948 | 无相关测试 | review_hints 只进摘要，不参与门禁（§5） | 03 | 01-A07 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：未覆盖，见 9.9 |
| LB-GATES-022 | scripts/pi_dispatch.py:879、907、1000、3298、3382、4194 | `test_commit_outside_main` “main repo change detected”、“re-modification of an already dirty file detected (Codex #12)”、“main repo change lists the non-planner path”、“summary names the changed main repo file”<br>`test_feedback_v11` “planner change is a note, not an attention item” | 主工作区指纹与变化分类（只作 G2 备注）（§5） | 07 | 01-A07 | windows 实测 | measured / PASS（5/5 check） |  |
| LB-GATES-023 | scripts/pi_dispatch.py:4152、4281 | `test_happy` “PASS accepted” | evaluate_gates 的结构与求值顺序（§5） | 03 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-024 | scripts/pi_dispatch.py:4160、2659、768、3205 | `test_happy` “PASS accepted” | G0：输入一致（§5） | 03 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-025 | scripts/pi_dispatch.py:4164、2338 | `test_events_and_thinking` “PASS refused on G1”、“ACCEPTED_WITH_EXCEPTION with waiver”、“missing JSON report does not block PASS”<br>`test_feedback_v12` “PASS is refused when the run ended on a textual tool call” | G1：执行完整（§5） | 03 | 01-A07 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-GATES-026 | scripts/pi_dispatch.py:4188 | `test_scope` “PASS refused on scope violation (G2)” | G2：范围合规（§5） | 03 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-027 | scripts/pi_dispatch.py:4183、4201、4228、3446 | `test_feedback_v12` “verdict prints the G3 note about undeclared ambiguity” | G3：行为正确（DoD 证据）（§5） | 03 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-028 | scripts/pi_dispatch.py:4200、4223 | `test_candidate_drift_and_artifacts` “PASS refused when checks created files (G4)” | G4：回归检查（§5） | 03 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-029 | scripts/pi_dispatch.py:4153、4154 | `test_happy` “PASS accepted” | G5：质量复审（无机械判定）（§5） | 03 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-030 | scripts/pi_dispatch.py:4237、4254 | `test_v22_netperf_feedback` “verdict PASS survives a later autocrlf change (snapshot pinned to the recorded value)” | G6：可集成（候选未漂移、补丁完整）（§5） | 03、10 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-031 | scripts/pi_dispatch.py:4259 | `test_happy` “verdict line mismatch refused” | verdict 的前置校验顺序（§5） | 03 | 01-A05、01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-GATES-032 | scripts/pi_dispatch.py:4284、4293、4299 | `test_happy` “PASS accepted”<br>`test_scope` “PASS refused on scope violation (G2)”、“REVISE recorded”<br>`test_events_and_thinking` “ACCEPTED_WITH_EXCEPTION with waiver”<br>`test_candidate_drift_and_artifacts` “PASS refused when checks created files (G4)” | 各结论对门禁的要求（§5） | 03 | 01-A05、01-A07 | windows 实测 | measured / PASS（5/5 check） |  |
| LB-GATES-033 | scripts/pi_dispatch.py:4301、80、3453 | `test_happy` “PASS accepted”<br>`test_scope` “REVISE recorded” | verdict 记录、状态迁移与重复下结论（§5） | 03 | 01-A05 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-GATES-034 | scripts/pi_dispatch.py:4319 | `test_scope` “rework branch from REVISE”<br>`test_happy` “mark integrated” | latest_verdict（§5） | 03、10 | 01-A05 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-GATES-035 | scripts/pi_dispatch.py:4327 | `test_happy` “branch tree == candidate tree”、“branch parent == base”、“branch subject without a title”<br>`test_scope` “rework branch from REVISE”<br>`test_repo_config_features` “branch commit carries executor and trailers”<br>`test_v21_codex_trial_feedback` “branch refuses before rebuilding the tree or creating anything when the identity is missing”、“branch rebuilds the tree and uses the per-run trailer instead of the configured one”、“branch commit message has LF line endings only”<br>`test_v22_netperf_feedback` “branch suggests ff-only while HEAD is still the base”、“branch suggests cherry-pick once HEAD moved past the base” | branch：结论门槛与候选树的使用（§5） | 10 | 01-A05、01-A07 | windows 实测 | measured / PASS（10/10 check） |  |
| LB-GATES-036 | scripts/pi_dispatch.py:4395 | `test_happy` “mark integrated”<br>`test_feedback_v12` “REVISE attempt can be marked SUPERSEDED” | mark INTEGRATED / SUPERSEDED 对结论的要求（§5） | 10 | 01-A05 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-GATES-037 | scripts/pi_dispatch.py:4430 | `test_cleanup_protects_unsaved_work` “cleanup refuses when candidate files were modified”、“cleanup --force removes and logs discarded content”<br>`test_happy` “cleanup removes worktree” | cleanup 对未保存候选内容的保护（§5） | 07 | 01-A07 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-GATES-038 | .agents/skills/review-pi/gates.md:7、36、68；scripts/pi_dispatch.py:4152、4284、80 | 无相关测试 | gates.md 与 evaluate_gates 的不一致之处（§5） | 03 | 01-A07 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：部分覆盖，见 9.9 |

### 9.5 LB-LIFE：锁、预算、监督进程与 attempt 生命周期（第 6 节）

共 40 条（结构化条目 32，核对者补充 8）：measured/PASS 26，source_inspected/NOT_RUN 13，source_reported/NOT_RUN 1。

| legacy_behavior_id | source_location（@a4fa199） | legacy_command_or_test_id | legacy_observation | new_consumer_module | acceptance_ids | platform_scope | evidence_basis / execution_status | 备注 |
|---|---|---|---|---|---|---|---|---|
| LB-LIFE-001 | scripts/pi_dispatch.py:62、2558-2563、2623、3193、3198、3204、4354 | `test_happy` “branch tree == candidate tree”、“branch subject without a title” | attempt 目录名、编号格式与派生标识（§6） | 07 | 01-A08 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-LIFE-002 | scripts/pi_dispatch.py:2619-2621、2623、3192-3193；tests/test_dispatch.py:208-209 | `test_happy` “claim records reserved timeout”、“branch subject without a title”、“mark integrated” | 首次 attempt 编号为 1（决策 01-D03 的依据）（§6） | 07 | 01-A08 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-LIFE-003 | scripts/pi_dispatch.py:2616-2629、3165-3192、3220-3233 | `test_preflight_and_budget` “budget: 3rd attempt refused”<br>`test_stuck_states` “PREPARING can be abandoned with --force”<br>`test_feedback_v12` “overlap warning names the latest pending attempt only” | 编号递增条件与作用域（§6） | 07 | 01-A08 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-LIFE-004 | scripts/pi_dispatch.py:3254-3257、3281-3285、3310-3313、3411-3443 | `test_preflight_and_budget` “model not listed -> preflight fail, stays PREPARED”、“run after fixing env”<br>`test_stuck_states` “claimed PREPARED attempt cannot run again”<br>`test_dispatcher_killed` “recover after dispatcher death” | 恢复和预检失败复用同一 attempt；重试必须重新 prepare（§6） | 07 | 01-A08 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-LIFE-005 | scripts/pi_dispatch.py:2583-2610、307、3300 | `test_budget_race` “exactly one attempt claims the last budget slot” | TaskLock 的位置、获取与等待（§6） | 07 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-LIFE-006 | scripts/pi_dispatch.py:2599-2606、2612-2613、2597 | 无相关测试 | TaskLock 的过期接管与归属判断（§6） | 07 | 01-A07 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：已覆盖（Windows measured / PASS），见 9.9 |
| LB-LIFE-007 | scripts/pi_dispatch.py:3300-3315、3316-3326、3183-3192 | `test_happy` “claim records reserved timeout”<br>`test_budget_race` “exactly one attempt claims the last budget slot” | 锁只串行化 run 的预算复核与领取；claim/ 是 attempt 级互斥（§6） | 07 | 01-A07 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-LIFE-008 | scripts/pi_dispatch.py:1197-1198、1565-1580、1618-1622 | 无相关测试 | 预算字段默认值与校验范围（§6） | 07、09 | 01-A02、01-A07 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：部分覆盖，见 9.9 |
| LB-LIFE-009 | scripts/pi_dispatch.py:2566-2580、2558-2563、3430-3431 | `test_preflight_and_budget` “budget: 3rd attempt refused”<br>`test_happy` “claim records reserved timeout” | budget_usage 的计算规则（§6） | 07 | 01-A07 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-LIFE-010 | scripts/pi_dispatch.py:3182-3189 | `test_preflight_and_budget` “budget: 3rd attempt refused”<br>`test_budget_race` “exactly one attempt claims the last budget slot” | prepare 的预算预检（在锁外）（§6） | 07 | 01-A07 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-LIFE-011 | scripts/pi_dispatch.py:3272-3275、3300-3315、4877 | `test_happy` “claim records reserved timeout”<br>`test_timeout` “timeout -> TIMEOUT state” | run 的预算复核与本轮时限（§6） | 07 | 01-A07 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-LIFE-012 | scripts/pi_dispatch.py:3300-3313、2566-2580；tests/test_dispatch.py:330-343 | `test_budget_race` “exactly one attempt claims the last budget slot” | 预算竞争的结果（§6） | 07 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-LIFE-013 | scripts/pi_dispatch.py:3254-3269、2659-2665、3278-3285 | `test_preflight_and_budget` “model not listed -> preflight fail, stays PREPARED”、“auth not ready -> preflight fail”、“env/contract model conflict refused” | run 启动前的拒绝路径：状态不变（§6） | 07 | 01-A07、01-A08 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-LIFE-014 | scripts/pi_dispatch.py:3316-3332 | 无相关测试 | 领取后、启动前失败时转为 INFRA_FAILURE（§6） | 07 | 01-A07、01-A08 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：未覆盖，见 9.9 |
| LB-LIFE-015 | scripts/pi_dispatch.py:649-690、444-548、551-558、3336-3340 | `test_timeout` “grandchild process killed (job-object)”<br>`test_dispatcher_killed` “Job Object reaps pi and grandchild” | run_supervised 的进程隔离与启动失败（§6） | 07 | 01-A07、01-A15 | windows 实测（规则中的 POSIX 分支仅源码层面） | measured / PASS（2/2 check） |  |
| LB-LIFE-016 | scripts/pi_dispatch.py:678、691-697、720、3334、3395-3398、4169-4170 | `test_timeout` “timeout -> TIMEOUT state”、“timeout enforced quickly (\<40s)”、“grandchild process killed (job-object)” | 超时（§6） | 07 | 01-A07 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-LIFE-017 | scripts/pi_dispatch.py:571-585、703-710、3399-3400、4171-4172、4969-4971 | 无相关测试 | 取消（调度器收到信号）（§6） | 07 | 01-A07 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：已覆盖（Windows measured / PASS；POSIX 方法本机 NOT_RUN），见 9.9 |
| LB-LIFE-018 | scripts/pi_dispatch.py:596-626、629-646、561-568、711-722 | `test_timeout` “grandchild process killed (job-object)” | 终止进程树与回收残留进程（§6） | 07 | 01-A07 | windows 实测（规则中的 POSIX 分支仅源码层面） | measured / PASS（1/1 check） |  |
| LB-LIFE-019 | scripts/pi_dispatch.py:3364-3374、3395-3408 | `test_happy` “run ok -> NEEDS_REVIEW”<br>`test_events_and_thinking` “error stopReason -> exit 1 but NEEDS_REVIEW”、“events case startfail {}”<br>`test_timeout` “timeout -> TIMEOUT state” | collect 的最终状态判定顺序（§6） | 07 | 01-A05、01-A07 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-LIFE-020 | scripts/pi_dispatch.py:53、307、3349、3443、4966-4971 | `test_happy` “run ok -> NEEDS_REVIEW”<br>`test_events_and_thinking` “error stopReason -> exit 1 but NEEDS_REVIEW”<br>`test_dispatcher_killed` “recover after dispatcher death” | run 与 collect 的退出码（§6） | 07 | 01-A05 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-LIFE-021 | scripts/pi_dispatch.py:505、551-558、672-675；tests/test_dispatch.py:443-470 | `test_dispatcher_killed` “Job Object reaps pi and grandchild”、“PDEATHSIG stops pi”（本机未产生） | 调度器被强制结束后的进程回收（§6） | 07 | 01-A07、01-A08、01-A15 | 源码层面 | source_inspected / NOT_RUN（本次 1/2 check PASS） | “PDEATHSIG stops pi”仅 Linux 分支，本机不产生；**P4 更新**：部分覆盖，见 9.9 |
| LB-LIFE-022 | scripts/pi_dispatch.py:3411-3434、4880-4883 | `test_dispatcher_killed` “recover after dispatcher death”<br>`test_stuck_states` “claimed-but-not-started attempt recovers as INFRA_FAILURE” | collect --recover 的入口条件与合成 run.json（§6） | 07 | 01-A08 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-LIFE-023 | scripts/pi_dispatch.py:3435-3443、4167-4174、2577-2579 | `test_dispatcher_killed` “recover after dispatcher death”<br>`test_stuck_states` “claimed-but-not-started attempt recovers as INFRA_FAILURE” | 恢复收集的结果与证据处理（§6） | 07 | 01-A08 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-LIFE-024 | scripts/pi_dispatch.py:726-740、3422-3425、4416-4419 | `test_dispatcher_killed` “recover after dispatcher death” | pid_alive 的判定（§6） | 07 | 01-A08 | windows 实测（规则中的 POSIX 分支仅源码层面） | measured / PASS（1/1 check） |  |
| LB-LIFE-025 | scripts/pi_dispatch.py:4395-4422、4319-4324、4938-4944 | `test_dispatcher_killed` “mark ABANDONED on RUNNING requires --force”<br>`test_stuck_states` “PREPARING can be abandoned with --force”<br>`test_happy` “mark integrated”<br>`test_feedback_v12` “SUPERSEDED needs --ref and --reason”、“REVISE attempt can be marked SUPERSEDED”、“SUPERSEDED is refused for an attempt that never ran” | mark 的状态转换（§6） | 07、10 | 01-A05 | windows 实测 | measured / PASS（6/6 check） |  |
| LB-LIFE-026 | scripts/pi_dispatch.py:80、4263-4265、4301-4312、3961-3963、3596 | `test_happy` “PASS accepted”<br>`test_scope` “REVISE recorded” | verdict 的状态转换与 REVIEWABLE_STATES（§6） | 03、07 | 01-A05 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-LIFE-027 | scripts/pi_dispatch.py:2539-2544、2547-2551、2554-2555、351-361、75 | `test_happy` “run ok -> NEEDS_REVIEW”<br>`test_v2_planner_adapters` “wait returns at once for a finished attempt” | 旧 attempt 状态全集与持久化方式（§6） | 07 | 01-A05 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-LIFE-028 | scripts/pi_dispatch.py:3192-3242 | `test_stuck_states` “PREPARING can be abandoned with --force” | prepare 的状态转换（§6） | 07 | 01-A08 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-LIFE-029 | scripts/pi_dispatch.py:3913-3950、81-82、4898-4902 | `test_v2_planner_adapters` “wait returns at once for a finished attempt”、“wait times out on a running attempt with exit code 3”、“wait reports an attempt that never started” | wait 的状态分类与退出码（§6） | 07 | 01-A05 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-LIFE-030 | scripts/pi_dispatch.py:4430-4482 | `test_cleanup_protects_unsaved_work` “cleanup refuses when candidate files were modified”、“cleanup --force removes and logs discarded content”<br>`test_happy` “cleanup removes worktree” | cleanup 在生命周期中的限制（§6） | 07 | 01-A07 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-LIFE-031 | scripts/pi_dispatch.py:3111-3113、3126-3159、3166-3171 | `test_feedback_v12` “overlap warning names the latest pending attempt only”、“no overlap warning once the latest attempt is integrated”、“a superseded attempt is not pending integration” | 并行提示使用的“待集成”状态集合（§6） | 10 | 01-A05 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-LIFE-032 | .agents/skills/review-pi/gates.md:60-69；.agents/skills/dispatch-pi/SKILL.md:85-93；.agents/skills/dispatch-pi/troubleshooting.md:33；scripts/pi_dispatch.py:4264、4408、4412 | 无相关测试 | 技能文档中的状态表与源码的差异（§6） | 待定 | 待定 | 源码层面 | source_reported / NOT_RUN | 只来自技能文档或 AGENTS.md 的说法；**P4 更新**：不适用（文档说法或旧自测夹具），见 9.9 |
| LB-LIFE-033 | scripts/pi_dispatch.py:2632-2650 | 未登记 | 恢复与各命令的 attempt 定位 resolve_run_dir（§6） | 07 | 01-A08 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |
| LB-LIFE-034 | scripts/pi_dispatch.py:2653-2656、3165、3182、3272 | 未登记 | 预算限额来源不同（prepare 读计划目录合同，run 读 attempt 内副本）（§6） | 07 | 01-A07 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：未覆盖，见 9.9 |
| LB-LIFE-035 | scripts/pi_dispatch.py:3087、3097-3098、3194-3229、3300-3345、703-710、4969-4971 | 未登记 | 各阶段收到 Ctrl+C 或信号后的状态（§6） | 07 | 01-A07 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |
| LB-LIFE-036 | scripts/pi_dispatch.py:3271、2668-2699 | 未登记 | run 领取前 resolve_executor 的拒绝（2 或 3，保持 PREPARED）（§6） | 待定（候选 02、07） | 01-A08 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：已覆盖（Windows measured / PASS），见 9.9 |
| LB-LIFE-037 | scripts/pi_dispatch.py:2017-2067、3280 | 未登记 | 预检证据在再次 run 时被覆盖（§6） | 04、07 | 01-A08 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：未覆盖，见 9.9 |
| LB-LIFE-038 | scripts/pi_dispatch.py:3255、2572、3416、4498 | 未登记 | claim 的判断方式不一致（exists 与 is_dir）（§6） | 07 | 01-A07 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：未覆盖，见 9.9 |
| LB-LIFE-039 | scripts/pi_dispatch.py:678、696、715、720、2575-2576 | 未登记 | 实际用时可超过预留（§6） | 07 | 01-A07 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |
| LB-LIFE-040 | scripts/pi_dispatch.py:3453-3455、4303-4304、3612-3613 | 未登记 | verdicts、checks、mutations 的编号也从 01 开始（§6） | 07 | 01-A08 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |

### 9.6 LB-EXIT：入口退出码与 wait 语义（第 7 节）

共 40 条（结构化条目 28，核对者补充 12）：measured/PASS 25，source_inspected/NOT_RUN 14，source_reported/NOT_RUN 1。

| legacy_behavior_id | source_location（@a4fa199） | legacy_command_or_test_id | legacy_observation | new_consumer_module | acceptance_ids | platform_scope | evidence_basis / execution_status | 备注 |
|---|---|---|---|---|---|---|---|---|
| LB-EXIT-001 | scripts/pi_dispatch.py:53、304-309 | `test_candidate_drift_and_artifacts` “in-place check refuses unexpected extra file” | 退出码常量与 DispatchError 默认码（§7） | 待定（各入口模块） | 01-A05 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-EXIT-002 | scripts/pi_dispatch.py:4953-4971、4974-4975 | `test_validate` “wrong executor type reported, no crash”、“non-string authorization items, no crash (Codex #11)” | main 的异常与返回值映射（§7） | 待定（各入口模块） | 01-A05 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-EXIT-003 | scripts/pi_dispatch.py:4831-4950、4835、48、4960 | 无相关测试 | argparse 用法错误、--version 与 --help（§7） | 待定（各入口模块） | 01-A05 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；**P4 更新**：部分覆盖，见 9.9 |
| LB-EXIT-004 | scripts/dispatch-pi.sh:4、9-19、21-22 | `test_wrapper_interpreters_and_literal_arguments` “wrapper reports unsupported interpreters: \<shell>”（本机未产生）、“wrapper preserves argv and exit code via \<accepted>: \<shell>”（本机未产生）<br>`test_setup_wrapper_doctor` “bash wrapper finds python” | dispatch-pi.sh 的退出码传递（§7） | 待定 | 01-A05、01-A15 | 源码层面 | source_inspected / NOT_RUN（本次 1/3 check PASS） | “wrapper reports unsupported interpreters: \<shell>”：仅 POSIX，Windows 上直接 return，本机 0 个 check；“wrapper preserves argv and exit code via \<accepted>: \<shell>”：仅 POSIX，Windows 上直接 return，本机 0 个 check；**P4 更新**：未覆盖，见 9.9 |
| LB-EXIT-005 | scripts/pi_dispatch.py:956-964、969-979、981-987、990-1008、1011-1028、1054-1060、747-761、1760-1795、2583-2629、2632-2650、2668-2699 | `test_feedback_v11` “plan path outside .agent/plans rejected”、“bad plan key still explains the format”<br>`test_preflight_and_budget` “env/contract model conflict refused”、“pinned thinking mismatch refused”<br>`test_repo_config_features` “invalid commit_trailers config rejected by branch” | 多个子命令共用的前置错误码（§7） | 待定（各入口模块） | 01-A05 | windows 实测 | measured / PASS（5/5 check） |  |
| LB-EXIT-006 | scripts/pi_dispatch.py:2999-3008、2988-2996 | `test_happy` “validate ok”<br>`test_validate` “invalid thinking rejected”<br>`test_feedback_v11` “validate accepts a relative md path”、“invalid expect_on_base rejected”、“invisible format character is warned” | validate 的退出码（§7） | 09 | 01-A05 | windows 实测 | measured / PASS（5/5 check） |  |
| LB-EXIT-007 | scripts/pi_dispatch.py:3011-3039 | `test_feedback_v11` “derive-json writes a contract that validates”、“derive-json refuses to overwrite without --force”、“derive-json --print takes the title from Goal”<br>`test_feedback_v12` “annotated single values are derived without the note” | derive-json 的退出码（推导问题也返回 2）（§7） | 09 | 01-A05 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-EXIT-008 | scripts/pi_dispatch.py:3162-3242 | `test_setup_wrapper_doctor` “setup command runs in prepare”、“setup modifying tracked file -> PREPARE_FAILED”<br>`test_validate` “prepare refuses when .agent/runs not ignored”<br>`test_preflight_and_budget` “budget: 3rd attempt refused”、“allowlisted executor with pinned high thinking ok”、“pinned thinking mismatch refused”<br>`test_v21_codex_trial_feedback` “prepare without setup points to a new contract version” | prepare 的退出码（§7） | 07 | 01-A05 | windows 实测 | measured / PASS（7/7 check） |  |
| LB-EXIT-009 | scripts/pi_dispatch.py:3250-3349、3352-3408、571-585、649-723 | `test_happy` “run ok -> NEEDS_REVIEW”<br>`test_events_and_thinking` “error stopReason -> exit 1 but NEEDS_REVIEW”<br>`test_stuck_states` “claimed PREPARED attempt cannot run again”<br>`test_preflight_and_budget` “model not listed -> preflight fail, stays PREPARED”、“auth not ready -> preflight fail”、“env/contract model conflict refused”<br>`test_timeout` “timeout -> TIMEOUT state” | run 的退出码（§7） | 07 | 01-A05 | windows 实测 | measured / PASS（7/7 check） |  |
| LB-EXIT-010 | scripts/pi_dispatch.py:3411-3443 | `test_dispatcher_killed` “recover after dispatcher death”<br>`test_stuck_states` “claimed-but-not-started attempt recovers as INFRA_FAILURE” | collect 的退出码（§7） | 07 | 01-A05、01-A08 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-EXIT-011 | scripts/pi_dispatch.py:3957-4052、80 | `test_happy` “in-place check passes”、“fresh check passes in clean copy and removes it”<br>`test_candidate_drift_and_artifacts` “in-place check refuses unexpected extra file”、“fresh check ignores worktree extras”、“python cache files are allowed artifacts”、“check creating unexpected file -> exit 1”<br>`test_mutate` “check still passes after mutate”<br>`test_v22_netperf_feedback` “check passes with autocrlf=true worktree” | check 的退出码（唯一的 4）（§7） | 待定（候选 03、07） | 01-A05、01-A07 | windows 实测 | measured / PASS（8/8 check） |  |
| LB-EXIT-012 | scripts/pi_dispatch.py:4073-4149 | `test_feedback_v11` “baseline runs checks on base without an attempt”、“baseline flags a probe that already passes on base”<br>`test_v22_netperf_feedback` “baseline explains a missing test file instead of implying a fix task” | baseline 的退出码（§7） | 待定 | 01-A05 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-EXIT-013 | scripts/pi_dispatch.py:3585-3690 | `test_mutate` “mutate reports caught / missed / skipped”、“invalid mutation spec is rejected with every problem listed”、“mutate refuses when the command fails without mutations” | mutate 的退出码（§7） | 待定 | 01-A05 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-EXIT-014 | scripts/pi_dispatch.py:4259-4316 | `test_happy` “verdict line mismatch refused”、“PASS accepted”<br>`test_candidate_drift_and_artifacts` “PASS refused when checks created files (G4)”<br>`test_scope` “PASS refused on scope violation (G2)”、“REVISE recorded”<br>`test_events_and_thinking` “PASS refused on G1”、“ACCEPTED_WITH_EXCEPTION with waiver”<br>`test_feedback_v12` “PASS is refused when the run ended on a textual tool call” | verdict 的退出码（§7） | 03 | 01-A05 | windows 实测 | measured / PASS（8/8 check） |  |
| LB-EXIT-015 | scripts/pi_dispatch.py:4327-4392 | `test_happy` “branch tree == candidate tree”<br>`test_scope` “rework branch from REVISE”<br>`test_repo_config_features` “invalid commit_trailers config rejected by branch”<br>`test_v21_codex_trial_feedback` “branch refuses before rebuilding the tree or creating anything when the identity is missing”、“an invalid --trailer is a usage error: 'Bad trailer'”、“an invalid --trailer is a usage error: 'Key: value\r'”、“an invalid --trailer is a usage error: 'Key: value\rInjected: extra'”、“a configured trailer with CR is rejected”<br>`test_v22_netperf_feedback` “branch prints a machine-readable commit= line” | branch 的退出码（§7） | 10 | 01-A05 | windows 实测 | measured / PASS（9/9 check） |  |
| LB-EXIT-016 | scripts/pi_dispatch.py:4395-4422 | `test_happy` “mark integrated”<br>`test_dispatcher_killed` “mark ABANDONED on RUNNING requires --force”<br>`test_stuck_states` “PREPARING can be abandoned with --force”<br>`test_feedback_v12` “SUPERSEDED needs --ref and --reason”、“REVISE attempt can be marked SUPERSEDED”、“SUPERSEDED is refused for an attempt that never ran” | mark 的退出码（§7） | 10 | 01-A05 | windows 实测 | measured / PASS（6/6 check） |  |
| LB-EXIT-017 | scripts/pi_dispatch.py:4430-4482 | `test_happy` “cleanup removes worktree”<br>`test_cleanup_protects_unsaved_work` “cleanup refuses when candidate files were modified”、“cleanup --force removes and logs discarded content” | cleanup 的退出码（§7） | 07 | 01-A05 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-EXIT-018 | scripts/pi_dispatch.py:3883-3910、3747-3759、4905 | `test_v2_planner_adapters` “sync-adapters refuses a repo without .agents/skills”、“sync-adapters --check reports missing copies”、“sync-adapters copies whole skill directories”、“sync-adapters --check passes after sync”、“sync-adapters --check reports edited and stray copies”<br>`test_v2_review_fixes` “sync-adapters --check fails when one source is missing”、“sync-adapters reports skills it could not sync”、“sync-adapters refuses a linked .claude/skills and leaves the target alone” | sync-adapters 的退出码（§7） | 待定 | 01-A05 | windows 实测 | measured / PASS（8/8 check） |  |
| LB-EXIT-019 | scripts/pi_dispatch.py:4551-4578、4485-4507 | `test_feedback_v11` “status accepts an attempt ref”、“status accepts an attempt path”<br>`test_events_and_thinking` “status shows unknown cost” | status 的退出码与 live 列（§7） | 10 | 01-A05 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-EXIT-020 | scripts/pi_dispatch.py:4596-4654、4581-4593 | `test_output_paths` “metrics --out README.md refused, README untouched”、“metrics --out under _reports allowed”<br>`test_happy` “metrics first PASS 100%” | metrics 的退出码（§7） | 10、07 | 01-A05、01-A06 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-EXIT-021 | scripts/pi_dispatch.py:4657-4762 | `test_output_paths` “doctor --out into evidence refused”<br>`test_setup_wrapper_doctor` “doctor ok with stub”、“doctor reports a failing list-models run as such”、“doctor explains that pi has no models at all”、“doctor explains that no model matches”、“a model listed under another provider keeps the short message” | doctor 的退出码（不会返回 3）（§7） | 04 | 01-A05 | windows 实测 | measured / PASS（6/6 check） |  |
| LB-EXIT-022 | scripts/pi_dispatch.py:4765-4824 | `test_setup_wrapper_doctor` “smoke both steps ok” | smoke 的退出码（§7） | 04 | 01-A05 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-EXIT-023 | scripts/pi_dispatch.py:3913-3950、81-82、4898-4902 | `test_v2_planner_adapters` “wait returns at once for a finished attempt”、“wait times out on a running attempt with exit code 3”、“wait reports an attempt that never started”<br>`test_v2_review_fixes` “wait does not report an unreadable state as finished” | wait 的退出码（§7） | 07 | 01-A05 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-EXIT-024 | scripts/pi_dispatch.py:3929-3950、387-390、2554-2555、344-348 | `test_v2_planner_adapters` “wait returns at once for a finished attempt”、“wait times out on a running attempt with exit code 3”、“wait reports an attempt that never started”<br>`test_v2_review_fixes` “wait does not report an unreadable state as finished” | wait 的 stdout 结构（仍在运行 / 未开始 / 无法确定 / 已结束）（§7） | 07 | 01-A05 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-EXIT-025 | scripts/pi_dispatch.py:4522、4525-4548 | `test_feedback_v12` “live status flags a long stretch without tool calls” | _live_progress 进度字符串格式（§7） | 07、10 | 01-A05 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-EXIT-026 | scripts/pi_dispatch.py:3946-3950、3937、3942、757、4966-4968 | `test_v2_planner_adapters` “wait returns at once for a finished attempt”、“wait reports an attempt that never started” | wait 语义边界：0 不代表通过，3 有多种含义（§7） | 07 | 01-A05 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-EXIT-027 | AGENTS.md:52-55、83；scripts/pi_dispatch.py:3917-3950；.agents/skills/dispatch-pi/SKILL.md:44、52；.agents/skills/dispatch-pi/troubleshooting.md:4 | 无相关测试 | 文档与技能中的退出码声明（仅文档来源）（§7） | 待定 | 01-A05 | 源码层面 | source_reported / NOT_RUN | 只来自技能文档或 AGENTS.md 的说法；**P4 更新**：不适用（文档说法或旧自测夹具），见 9.9 |
| LB-EXIT-028 | scripts/pi_dispatch.py:53、307、4960-4971；scripts/dispatch-pi.sh:22 | `test_candidate_drift_and_artifacts` “in-place check refuses unexpected extra file”<br>`test_events_and_thinking` “error stopReason -> exit 1 but NEEDS_REVIEW”<br>`test_v2_planner_adapters` “wait times out on a running attempt with exit code 3” | 跨入口同码异义汇总（§7） | 待定（各入口模块） | 01-A05 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-EXIT-029 | scripts/pi_dispatch.py:957-958、756 | 未登记 | 全局 --repo 的退出码（非仓库 2；Windows 上不存在路径为 Traceback 1）（§7） | 待定（各入口模块） | 01-A05、01-A15 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：已覆盖（Windows measured / PASS；POSIX 方法本机 NOT_RUN），见 9.9 |
| LB-EXIT-030 | scripts/pi_dispatch.py:2555 | 未登记 | state.json 为非对象 JSON 时以 Traceback 退出 1（§7） | 07 | 01-A05 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：已覆盖（Windows measured / PASS），见 9.9 |
| LB-EXIT-031 | scripts/pi_dispatch.py:676、712、3319-3332、3344、3395-3404 | 未登记 | run 的中断窗口与退出码（§7） | 07 | 01-A05、01-A07 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |
| LB-EXIT-032 | scripts/pi_dispatch.py:663-667、682-684、686-688 | 未登记 | spawn 失败不抛异常（INFRA_FAILURE，run 退出 1）（§7） | 07 | 01-A05 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：未覆盖，见 9.9 |
| LB-EXIT-033 | scripts/pi_dispatch.py:4967 | 未登记 | 输出流约定（stderr 的 ERROR: 与 stdout 的逐项诊断）（§7） | 待定（各入口模块） | 01-A05 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |
| LB-EXIT-034 | scripts/pi_dispatch.py:4498、4572、4562-4564 | 未登记 | status 的 EXIT 列是 Pi 进程退出码（§7） | 10 | 01-A05 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：未覆盖，见 9.9 |
| LB-EXIT-035 | scripts/pi_dispatch.py:4284-4291、4400-4403、4767、4336-4339、4585-4589 | 未登记 | 拒绝顺序决定退出码（§7） | 待定（各入口模块） | 01-A05 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |
| LB-EXIT-036 | scripts/pi_dispatch.py:4030 | 未登记 | check 只按 required 检查计算 required_ok（§7） | 待定（候选 03、07） | 01-A05、01-A07 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：已覆盖（Windows measured / PASS），见 9.9 |
| LB-EXIT-037 | scripts/pi_dispatch.py:730-732、3424、4418 | 未登记 | pid_alive 在 Windows 上 tasklist 失败时放行（§7） | 07 | 01-A05、01-A08 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：未覆盖，见 9.9 |
| LB-EXIT-038 | scripts/pi_dispatch.py:2643-2649 | 未登记 | resolve_run_dir 按 task-id 选最新 attempt 时不要求 meta.json（§7） | 07 | 01-A05、01-A08 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：已覆盖（Windows measured / PASS），见 9.9 |
| LB-EXIT-039 | scripts/pi_dispatch.py:3031、3037、3039、3026-3028 | 未登记 | derive-json 在校验之前写 JSON（§7） | 09 | 01-A05 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：未覆盖，见 9.9 |
| LB-EXIT-040 | scripts/pi_dispatch.py:1668、1684、1673 | 未登记 | validate 可能返回 1 或 3（§7） | 09 | 01-A05 | 源码层面 | source_inspected / NOT_RUN | 核对者补充条目，未登记 related_tests；**P4 更新**：部分覆盖，见 9.9 |

### 9.7 LB-TEST：旧自测清单与回归覆盖（第 8 节）

共 40 条（结构化条目 40，核对者补充 0）：measured/PASS 35，source_inspected/NOT_RUN 5。

| legacy_behavior_id | source_location（@a4fa199） | legacy_command_or_test_id | legacy_observation | new_consumer_module | acceptance_ids | platform_scope | evidence_basis / execution_status | 备注 |
|---|---|---|---|---|---|---|---|---|
| LB-TEST-H01 | tests/test_dispatch.py:1、22-39、43、55、61、108、128、169、231；scripts/pi_dispatch.py:1760 | 无相关测试 | 自测夹具：临时目录、执行器替身、临时仓库与合同样本（§8） | 待定 | 01-A01、01-A16 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；夹具在本次运行中被全部 24 个函数使用，但没有 check 直接断言其行为；**P4 更新**：不适用（文档说法或旧自测夹具），见 9.9 |
| LB-TEST-H02 | tests/test_dispatch.py:1907-1929、94 | 无相关测试 | `__main__` 入口：选择、汇总行与退出码（§8） | 待定 | 01-A01、01-A16 | 源码层面 | source_inspected / NOT_RUN | 没有登记相关测试；本次运行直接观察到 `== <函数>` 分段、`PASS <check>` 行、汇总行 `256 checks, 0 failed` 与退出码 0，与规则一致，但没有 check 断言；**P4 更新**：不适用（文档说法或旧自测夹具），见 9.9 |
| LB-TEST-S01 | tests/stub_pi.py:1-9、67、72-75、98-100、102-116、125-146、147-209、210-235 | `test_scope` “README out_of_scope”<br>`test_events_and_thinking` “events case model {}”<br>`test_timeout` “timeout -> TIMEOUT state”<br>`test_feedback_v12` “summary makes truncated temp evidence explicit” | stub_pi.py 运行场景与事件序列（模拟 Pi 0.87 JSON 模式）（§8） | 04 | 01-A16 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-TEST-S02 | tests/stub_pi.py:33-35、36-38、39-45、46-65、76-97；tests/stub_pi_help.txt:13、40、177-185；scripts/pi_dispatch.py:1760-1787、1789-1795、2014-2062 | `test_setup_wrapper_doctor` “doctor ok with stub”、“doctor reports a failing list-models run as such”、“smoke both steps ok”<br>`test_preflight_and_budget` “auth not ready -> preflight fail” | stub 的非运行命令（--help/--version/auth/--list-models/冒烟）与真实启动入口的覆盖边界（§8） | 04 | 01-A16 | windows 实测 | measured / PASS（4/4 check） |  |
| LB-TEST-001 | tests/test_dispatch.py:241；scripts/pi_dispatch.py:3214、3488、2515 | `test_happy`（全部 18 个 check） | test_happy：成功路径的完整生命周期（§8） | 07、03、10 | 01-A05、01-A07、01-A08 | windows 实测 | measured / PASS（18/18 check） |  |
| LB-TEST-002 | tests/test_dispatch.py:287；scripts/pi_dispatch.py:4001-4014、4214-4215 | `test_candidate_drift_and_artifacts`（全部 5 个 check） | test_candidate_drift_and_artifacts：候选漂移、缓存产物与 G4（§8） | 待定（候选 03、10） | 01-A07 | windows 实测 | measured / PASS（5/5 check） |  |
| LB-TEST-003 | tests/test_dispatch.py:315；scripts/pi_dispatch.py:4430 | `test_cleanup_protects_unsaved_work` “cleanup refuses when candidate files were modified”、“cleanup --force removes and logs discarded content” | test_cleanup_protects_unsaved_work：cleanup 不静默丢弃候选外改动（§8） | 07 | 01-A07 | windows 实测 | measured / PASS（2/2 check） |  |
| LB-TEST-004 | tests/test_dispatch.py:330；scripts/pi_dispatch.py:2583-2613、3272-3310 | `test_budget_race` “exactly one attempt claims the last budget slot” | test_budget_race：并发争用最后一次额度（§8） | 07 | 01-A07 | windows 实测 | measured / PASS（1/1 check） |  |
| LB-TEST-005 | tests/test_dispatch.py:346；scripts/pi_dispatch.py:2436、4189-4193 | `test_scope`（全部 7 个 check） | test_scope：范围违规、依赖变更、可疑命令与 G2（§8） | 09、03 | 01-A07 | windows 实测 | measured / PASS（7/7 check） |  |
| LB-TEST-006 | tests/test_dispatch.py:367、383-393；scripts/pi_dispatch.py:2326-2366、3395-3404 | `test_events_and_thinking`（全部 11 个 check） | test_events_and_thinking：事件完整性、G1、豁免、实际模型/思考级别/费用证据（§8） | 04、03 | 01-A02、01-A06、01-A07 | windows 实测 | measured / PASS（11/11 check） |  |
| LB-TEST-007 | tests/test_dispatch.py:404 | `test_commit_outside_main`（全部 6 个 check） | test_commit_outside_main：HEAD 移动、越界写入与主工作区变化（§8） | 03 | 01-A07 | windows 实测 | measured / PASS（6/6 check） |  |
| LB-TEST-008 | tests/test_dispatch.py:425、66、84；scripts/pi_dispatch.py:649、670 | `test_timeout` “timeout -> TIMEOUT state”、“timeout enforced quickly (\<40s)”、“grandchild process killed (job-object)” | test_timeout：超时判定与孙进程回收（§8） | 07 | 01-A07 | windows 实测（规则中的 POSIX 分支仅源码层面） | measured / PASS（3/3 check） |  |
| LB-TEST-009 | tests/test_dispatch.py:443；scripts/pi_dispatch.py:501-505、556、3411-3440 | `test_dispatcher_killed` “Job Object reaps pi and grandchild”、“PDEATHSIG stops pi”（本机未产生）、“mark ABANDONED on RUNNING requires --force”、“recover after dispatcher death” | test_dispatcher_killed：调度器被强杀后的进程回收与恢复（§8） | 07 | 01-A07、01-A08 | 源码层面 | source_inspected / NOT_RUN（本次 3/4 check PASS） | “PDEATHSIG stops pi”仅 Linux 分支，本机不产生；**P4 更新**：未覆盖，见 9.9 |
| LB-TEST-010 | tests/test_dispatch.py:479；scripts/pi_dispatch.py:3255-3257、3428-3433 | `test_stuck_states` “claimed PREPARED attempt cannot run again”、“claimed-but-not-started attempt recovers as INFRA_FAILURE”、“PREPARING can be abandoned with --force” | test_stuck_states：已领取未启动的恢复与 PREPARING 强制放弃（§8） | 07 | 01-A08 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-TEST-011 | tests/test_dispatch.py:495；scripts/pi_dispatch.py:2014、2668-2700、3183-3186 | `test_preflight_and_budget`（全部 7 个 check） | test_preflight_and_budget：预检、次数预算与固定思考级别（§8） | 04、07 | 01-A07、01-A08 | windows 实测 | measured / PASS（7/7 check） |  |
| LB-TEST-012 | tests/test_dispatch.py:520、524-530、547-557、563-581；scripts/pi_dispatch.py:1656 | `test_validate`（全部 18 个 check） | test_validate：合同拒绝原因、Markdown/JSON 一致性与示例合同（§8） | 09 | 01-A02 | windows 实测 | measured / PASS（18/18 check） |  |
| LB-TEST-013 | tests/test_dispatch.py:584 | `test_output_paths` “metrics --out README.md refused, README untouched”、“doctor --out into evidence refused”、“metrics --out under _reports allowed” | test_output_paths：--out 路径保护（§8） | 待定 | 待定 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-TEST-014 | tests/test_dispatch.py:597；scripts/pi_dispatch.py:649、2436 | `test_units` “glob uses fullmatch (no trailing newline match)”、“control chars / decode errors are invalid_path violations”、“on_spawn failure terminates the child (Codex #2)” | test_units：glob fullmatch、invalid_path 与 on_spawn 失败处理（§8） | 待定 | 01-A07 | windows 实测 | measured / PASS（3/3 check） |  |
| LB-TEST-015 | tests/test_dispatch.py:625 | `test_repo_config_features`（全部 6 个 check） | test_repo_config_features：仓库级受保护路径与提交尾注（§8） | 02、10 | 01-A07 | windows 实测 | measured / PASS（6/6 check） |  |
| LB-TEST-016 | tests/test_dispatch.py:656、658-659 | `test_wrapper_interpreters_and_literal_arguments` “wrapper reports unsupported interpreters: \<shell>”（本机未产生）、“wrapper preserves argv and exit code via \<python3\|python\|py>: \<shell>”（本机未产生） | test_wrapper_interpreters_and_literal_arguments：dispatch-pi.sh 的解释器选择与参数原样传递（仅 POSIX）（§8） | 待定 | 01-A05、01-A15 | 源码层面 | source_inspected / NOT_RUN（本次 0/2 check PASS） | “wrapper reports unsupported interpreters: \<shell>”：仅 POSIX，Windows 上直接 return，本机 0 个 check；“wrapper preserves argv and exit code via \<python3\|python\|py>: \<shell>”：仅 POSIX，Windows 上直接 return，本机 0 个 check；**P4 更新**：未覆盖，见 9.9 |
| LB-TEST-017 | tests/test_dispatch.py:701、710-714；scripts/pi_dispatch.py:4657、4765 | `test_setup_wrapper_doctor`（全部 11 个 check） | test_setup_wrapper_doctor：setup、bash 包装、doctor 与 smoke（§8） | 04、07 | 01-A15 | windows 实测 | measured / PASS（11/11 check） |  |
| LB-TEST-018 | tests/test_dispatch.py:814、753 | `test_feedback_v11`（全部 28 个 check） | test_feedback_v11（1.1.0 反馈）：计划路径、status、运行目录读取、越界失败、规划路径、范围重叠、baseline、derive-json（§8） | 待定（多模块） | 01-A02、01-A07 | windows 实测 | measured / PASS（28/28 check） |  |
| LB-TEST-019 | tests/test_dispatch.py:936、926、969-1044；scripts/pi_dispatch.py:4183-4187 | `test_feedback_v12`（全部 34 个 check） | test_feedback_v12（1.2.x 反馈）：合同矛盾提示、SUPERSEDED、文本工具调用、可疑命令与临时路径证据（§8） | 待定（多模块） | 01-A07 | windows 实测 | measured / PASS（34/34 check） |  |
| LB-TEST-020 | tests/test_dispatch.py:1220；scripts/pi_dispatch.py:3585、3617 | `test_mutate`（全部 7 个 check） | test_mutate（1.3.0）：变异检查的抓住、漏掉与跳过（§8） | 待定 | 待定 | windows 实测 | measured / PASS（7/7 check） |  |
| LB-TEST-021 | tests/test_dispatch.py:1275；scripts/pi_dispatch.py:3694、3917-3950 | `test_v2_planner_adapters`（全部 18 个 check） | test_v2_planner_adapters（2.0.0）：技能副本同步、规划端文件提示与 wait 退出码（§8） | 待定 | 01-A05 | windows 实测 | measured / PASS（18/18 check） |  |
| LB-TEST-022 | tests/test_dispatch.py:1380、1344、1361、1373；scripts/pi_dispatch.py:3943-3945 | `test_v2_review_fixes`（全部 16 个 check） | test_v2_review_fixes（2.0.0 审查修正）：链接与 junction 边界、缺失源、wait 读不到状态（§8） | 待定 | 01-A05、01-A15 | windows 实测 | measured / PASS（16/16 check） | “… unavailable here …”为建不了链接时的替代 check，本次真实分支已执行 |
| LB-TEST-023 | tests/test_dispatch.py:1531、1528、1740-1748 | `test_v21_codex_trial_feedback`（全部 29 个 check） | test_v21_codex_trial_feedback（2.1.0）：临时路径识别、脱敏、模型表解析、规则文本、尾注与 Git 身份（§8） | 04 | 01-A12 | windows 实测 | measured / PASS（29/29 check） |  |
| LB-TEST-024 | tests/test_dispatch.py:1782；scripts/pi_dispatch.py:4238-4253 | `test_v22_netperf_feedback`（全部 17 个 check） | test_v22_netperf_feedback（2.2.x）：基线落后分级、集成命令提示、autocrlf 固定与 Repository facts（§8） | 待定（多模块） | 01-A07 | windows 实测 | measured / PASS（17/17 check） |  |
| LB-TEST-COV-01 | scripts/pi_dispatch.py:1189-1213；tests/test_dispatch.py:602、702 | `test_units` “control chars / decode errors are invalid_path violations”<br>`test_setup_wrapper_doctor` “setup command runs in prepare” | C.4 旧合同默认值：没有直接覆盖（§8） | 09 | 01-A02 | windows 实测 | measured / PASS（2/2 check） | 所列 check 只间接用到缺省值，缺省值本身没有断言；C.4 缺口（第 10 节） |
| LB-TEST-COV-02 | tests/test_dispatch.py:543-557、896-915、1116-1124、1206-1216、1869-1895 | `test_validate` “argv change detected”、“budget change detected”、“integration change detected”、“forbidden path change detected”、“thinking change detected”、“missing md section rejected”、“placeholder rejected”<br>`test_feedback_v11` “derive-json writes a contract that validates”、“derived checks keep argv, cwd, timeout and patterns”、“derived scope and DoD”<br>`test_feedback_v12` “annotated single values are derived without the note”、“machine summary explains a base-failing probe”<br>`test_happy` “instruction has machine summary from JSON”<br>`test_v22_netperf_feedback` “validate warns about a Repository-facts file missing from the base” | C.4 Markdown/JSON 一致性：直接覆盖（§8） | 09 | 01-A02 | windows 实测 | measured / PASS（14/14 check） |  |
| LB-TEST-COV-03 | tests/test_dispatch.py:346-364、603-607、633-638、533-535、406-408 | `test_scope` “README out_of_scope”、“package.json forbidden + dependency”、“.env reported as new ignored path”<br>`test_units` “control chars / decode errors are invalid_path violations”<br>`test_repo_config_features` “repo-level protected path is a violation”<br>`test_validate` “protected path in scope rejected”、“parent traversal rejected”<br>`test_commit_outside_main` “HEAD moved is a violation”<br>`test_feedback_v11` “prepare warns about an overlapping pending attempt”<br>`test_feedback_v12` “overlap warning names the latest pending attempt only” | C.4 范围检查：直接覆盖（§8） | 09、03 | 01-A07 | windows 实测 | measured / PASS（10/10 check） |  |
| LB-TEST-COV-04 | scripts/pi_dispatch.py:4152-4257；tests/test_dispatch.py:374、359、312、954、1101、1835 | `test_events_and_thinking` “PASS refused on G1”、“ACCEPTED_WITH_EXCEPTION with waiver”<br>`test_feedback_v12` “PASS is refused when the run ended on a textual tool call”、“verdict prints the G3 note about undeclared ambiguity”<br>`test_scope` “PASS refused on scope violation (G2)”<br>`test_candidate_drift_and_artifacts` “PASS refused when checks created files (G4)”<br>`test_v22_netperf_feedback` “verdict PASS survives a later autocrlf change (snapshot pinned to the recorded value)”、“line_endings_only recognises CRLF-only drift”<br>`test_happy` “PASS accepted” | C.4 G0–G6：部分覆盖（G0、G5 无，G3 与 G6 只有提示或正向用例）（§8） | 03 | 01-A07 | windows 实测 | measured / PASS（9/9 check） | 部分覆盖：G0、G5 无测试，G3、G6 无失败路径断言（第 2 节） |
| LB-TEST-COV-05 | tests/test_dispatch.py:290-302、318-327、1252、1826-1851；scripts/pi_dispatch.py:4001-4014 | `test_candidate_drift_and_artifacts` “in-place check refuses unexpected extra file”、“fresh check ignores worktree extras”、“python cache files are allowed artifacts”<br>`test_cleanup_protects_unsaved_work` “cleanup refuses when candidate files were modified”、“cleanup --force removes and logs discarded content”<br>`test_mutate` “mutate leaves the executor worktree and candidate untouched”<br>`test_v22_netperf_feedback` “verdict PASS survives a later autocrlf change (snapshot pinned to the recorded value)” | C.4 候选树漂移：check 与 cleanup 层直接覆盖，verdict 层缺失（§8） | 待定（候选 03、10） | 01-A07 | windows 实测 | measured / PASS（7/7 check） | verdict 层 G6 漂移失败没有断言（第 10 节） |
| LB-TEST-COV-06 | tests/test_dispatch.py:258-275、1738-1770、1837；scripts/pi_dispatch.py:2515-2533、3988-3989 | `test_happy` “candidate roundtrip verified”、“fresh check passes in clean copy and removes it”、“branch tree == candidate tree”、“branch parent == base”<br>`test_v21_codex_trial_feedback` “branch refuses before rebuilding the tree or creating anything when the identity is missing”、“branch rebuilds the tree and uses the per-run trailer instead of the configured one”<br>`test_v22_netperf_feedback` “branch rebuilds the tree with the recorded autocrlf” | C.4 补丁往返与完整性：只有正向用例（§8） | 待定（候选 07、10） | 01-A07 | windows 实测 | measured / PASS（7/7 check） | 只有正向用例，完整性负例是缺口（第 10 节） |
| LB-TEST-COV-07 | tests/test_dispatch.py:330-343、507-510、256-257；scripts/pi_dispatch.py:2583-2613、2562-2580 | `test_budget_race` “exactly one attempt claims the last budget slot”<br>`test_preflight_and_budget` “budget: 3rd attempt refused”、“model not listed -> preflight fail, stays PREPARED”<br>`test_happy` “claim records reserved timeout” | C.4 锁与预算竞争：部分覆盖（§8） | 07 | 01-A07 | windows 实测 | measured / PASS（4/4 check） | 部分覆盖：锁等待与过期接管、墙钟预算耗尽没有测试（第 10 节） |
| LB-TEST-COV-08 | tests/test_dispatch.py:425-440、610-622、1334-1335 | `test_timeout` “timeout -> TIMEOUT state”、“timeout enforced quickly (\<40s)”、“grandchild process killed (job-object)”<br>`test_units` “on_spawn failure terminates the child (Codex #2)”<br>`test_v2_planner_adapters` “wait times out on a running attempt with exit code 3” | C.4 超时：直接覆盖（§8） | 07 | 01-A07 | windows 实测 | measured / PASS（5/5 check） |  |
| LB-TEST-COV-09 | scripts/pi_dispatch.py:440、576、703-706、3399-3400；tests/test_dispatch.py:475-476 | `test_dispatcher_killed` “recover after dispatcher death” | C.4 取消：没有直接覆盖（§8） | 07 | 01-A07 | windows 实测 | measured / PASS（1/1 check） | 所列 check 只断言恢复后状态为 CANCELLED 或 INFRA_FAILURE，不覆盖信号取消分支；C.4 取消仍是缺口（第 10 节） |
| LB-TEST-COV-10 | tests/test_dispatch.py:443-476、479-492；scripts/pi_dispatch.py:3411-3440 | `test_dispatcher_killed` “Job Object reaps pi and grandchild”、“PDEATHSIG stops pi”（本机未产生）、“mark ABANDONED on RUNNING requires --force”、“recover after dispatcher death”<br>`test_stuck_states` “claimed PREPARED attempt cannot run again”、“claimed-but-not-started attempt recovers as INFRA_FAILURE”、“PREPARING can be abandoned with --force” | C.4 进程恢复：直接覆盖，但部分断言宽松（§8） | 07 | 01-A07、01-A08 | 源码层面 | source_inspected / NOT_RUN（本次 6/7 check PASS） | “PDEATHSIG stops pi”仅 Linux 分支，本机不产生；**P4 更新**：部分覆盖，见 9.9 |
| LB-TEST-COV-11 | tests/test_dispatch.py:251、383-393、495-517、715-746；scripts/pi_dispatch.py:2326-2362 | `test_happy` “thinking not reported -> evidence says so, no problem”<br>`test_events_and_thinking` “events case model {}”、“events case ok {'STUB_PTL': 'low'}”<br>`test_preflight_and_budget` “model not listed -> preflight fail, stays PREPARED”、“env/contract model conflict refused”、“pinned thinking mismatch refused”<br>`test_validate` “invalid thinking rejected”<br>`test_setup_wrapper_doctor` “doctor ok with stub”<br>`test_v21_codex_trial_feedback` “model table parsing ignores pi's no-model messages”<br>`test_repo_config_features` “branch commit carries executor and trailers” | C.4 实际模型与思考级别证据：直接覆盖，预检分支有缺口（§8） | 04 | 01-A02 | windows 实测 | measured / PASS（10/10 check） | 预检的思考级别、工具、版本分支与 stderr 警告没有测试（第 10 节） |
| LB-TEST-COV-12 | tests/test_dispatch.py:1329-1341、1517-1525；scripts/pi_dispatch.py:53、307、3917-3950 | `test_v2_planner_adapters` “wait returns at once for a finished attempt”、“wait times out on a running attempt with exit code 3”、“wait reports an attempt that never started”、“sync-adapters --check reports missing copies”<br>`test_v2_review_fixes` “wait does not report an unreadable state as finished”<br>`test_candidate_drift_and_artifacts` “in-place check refuses unexpected extra file”、“check creating unexpected file -> exit 1”<br>`test_events_and_thinking` “error stopReason -> exit 1 but NEEDS_REVIEW”<br>`test_output_paths` “metrics --out README.md refused, README untouched”<br>`test_mutate` “invalid mutation spec is rejected with every problem listed” | C.4 wait 与退出码语义：直接覆盖（§8） | 07、10 | 01-A05 | windows 实测（规则中的 POSIX 分支仅源码层面） | measured / PASS（10/10 check） |  |

### 9.8 未编号的核对补充

以下是核对者对区域原稿的补充与修正说明，没有单独的 legacy_behavior_id，不进入上表。其中大部分事实已写入对应区域章节正文，这里照录原文，以免遗漏。

| 区域 | 核对补充原文 | 说明 |
|---|---|---|
| 第 4 节 | LB-EVENTS-026 的补充：另有两种输入会让 summarize_events 抛出未捕获的异常：最终 assistant text 块的 text 不是字符串（TypeError，2101）；工具参数 path/file_path 含 NUL（ValueError，2277）。状态停在 COLLECTING 后，wait 会持续返回 3。 |  |
| 第 4 节 | LB-EVENTS-011 的补充：agent_settled 之后到来的非 WORK 事件（例如没有 message_start 的 assistant message_end）不影响 complete，但会替换最终消息并累加用量；settled 之后再来 agent_end(willRetry=true) 仍判完整。 |  |
| 第 4 节 | 4.3.4 对照表缺两行：“取消后进程退出”（事件摘要不看取消，取消只体现在 run_info.interrupted→CANCELLED 和 G1，3399-3400、4171-4172）；“终止后出现新关键内容”（见上一条）。 | 终稿 4.5 对照表已含这两行 |
| 第 4 节 | “结束事件完整但进程非零退出”：collect 状态和 run 退出码都不看 Pi 退出码（3348-3349、3395-3404），只有 G1 记录。 |  |
| 第 4 节 | ensure_argv_safe 的第三个调用点 _run_command_item（3079-3084），命中时记为 blocked，不抛出。 |  |
| 第 4 节 | 预检检测 auth 子命令时读的是已脱敏的 pi-help.txt（2056-2057）；auth 的 problem 优先取 stdout。 |  |
| 第 4 节 | 草稿 markdown 没有 LB-EVENTS-027（doctor/smoke 与预检的差异）的小节。 | 终稿已补上，见 4.11 |
| 第 4 节 | summary.md 对所有 stderr_flags 都写“stderr 标记”，不只写 extension_error（2954-2955）。 |  |
| 第 4 节 | 费用表中“没有 assistant 消息 → usage 全部为 0”不对：toolResult、entry、compaction 的用量照常累加。 | 终稿 4.7 费用表已按此修正 |
| 第 5 节 | G6 行尾判定的限制：line_endings_only（:858-861）比较整棵树，worktree 中另有未忽略的新文件时，只差 CRLF 的修改会被报成“候选文件在记录后被修改”（在临时仓库中用同一条 git 命令核实过） |  |
| 第 5 节 | verdict 的 G6 会重新快照（:4240），向仓库写入 Git 对象 |  |
| 第 5 节 | G0 不校验 meta.json；contract.json 哈希不一致时，G3/G4 仍按 run_dir 中被改动的合同判定（:2655、:4223-4236） |  |
| 第 5 节 | run.json 缺失时 G1 同时记“缺少 run.json”和“Pi 退出码为 None”两条（:4167-4174） |  |
| 第 5 节 | check 漂移报错文本中，文件列表以 Python 列表 repr 格式化（:4014），例如 ['src/helper.py'] |  |
| 第 5 节 | collect 状态：spawn_error 也会导致 INFRA_FAILURE（:3395）；extra_protected_paths 配置不合法时记入 collect_errors（:3370、:3373） |  |
| 第 5 节 | main_repo_changes 在 diff-tree 失败或指纹不完整时给出 diff_error，此时 G2 不加备注，只在 summary 中提示（:922-928、:2945-2947） |  |
| 第 5 节 | line_ending_args 对 true/false/input/unset 以外的 autocrlf 取值（如 yes、1）返回 []，不固定配置（:780-790） |  |
| 第 5 节 | 范围静态校验在 _validate_contract（:1440）中，不在 validate_plan；受保护路径检查只拿模式文本匹配，`**/*.md` 这类通配允许项可以通过 validate，运行时再判 protected_path；pattern_error 以“范围过宽”拒绝 `*`、`**`、`**/*`（:1111-1112） |  |
| 第 5 节 | evaluate_scope 的空档：符号链接改回普通文件（old 120000 → new 100644）既不算 symlink 违规，也不算 mode_changed（:2468-2477，已在内存中核实） |  |
| 第 5 节 | _run_command_item 在 argv 安全检查失败时记 blocked（:3080-3084） |  |
| 第 5 节 | cleanup 拒绝删除未登记但非空的目录（:4470-4471）；不清理 mutate、baseline 用 --keep-workspace 保留的副本；被忽略的文件不记 LOSS |  |
| 第 5 节 | branch：身份缺失退出码为 3；有 --no-config-trailers；树对象和补丁都丢失时抛出未捕获的异常（推断） |  |
| 第 5 节 | baseline：setup 失败时副本被移除，但不写 checks.json（:4108-4119） |  |
| 第 5 节 | verdict 的 --review 是必填参数（:4911）；main 未给子命令时返回 2（:4961-4963） |  |
| 第 5 节 | 测试覆盖修正：G3 的 scope 证据失败在 test_scope 中被触发但没有断言；G6 的“记录后修改”在 test_cleanup_protects_unsaved_work 中被触发但没有断言；test_v22 的 "branch rebuilds the tree with the recorded autocrlf" 没有走重建分支 |  |
| 第 8 节 | test_dispatch 导入时把 stdout/stderr 重设为 UTF-8（tests/test_dispatch.py:34-38），影响 Windows 上的输出取证 |  |
| 第 8 节 | BASE_ENV 只删除列出的变量，其余环境（含 HOME、用户全局 git 配置等）原样继承；PI_DISPATCH_PI_CMD 只在 :29 设置、从不删除，test_v21 的 bare 环境（:1732）也由它派生，所以任何测试路径都调用不到本机真实的 pi |  |
| 第 8 节 | fixture 仓库在提交 base 之后才写 .agent/dispatch.config.json 和合同，主仓库因此带未跟踪文件（source_worktree_dirty），test_v22 在 :1786-1788 特意先提交 |  |
| 第 8 节 | `__main__` 的 except Exception 捕获不到 KeyboardInterrupt，中断时没有汇总行；汇总之后的清理异常会让进程以 1 退出，即使汇总为 0 failed；混入的拼错测试名被静默忽略 |  |
| 第 8 节 | run 的退出码规则：只有 NEEDS_REVIEW 且 events ok 时才为 0（scripts/pi_dispatch.py:3349）；main 在 DispatchError 时输出 'ERROR: ...' 并返回 exc.code（:4966-4968） |  |
| 第 8 节 | collect --recover 缺 run.json 时合成 interrupted=True（:3430），test_dispatcher_killed 多半经过 CANCELLED 分支，但没有锁定 |  |
| 第 8 节 | G3 失败在 test_scope 中实际发生（:4232）但没有断言；G4/G3 的“没有有效的独立检查记录”（:4204-4205）以及 G1 的“缺少 run.json”“运行被取消”（:4168、:4172）没有测试 |  |
| 第 8 节 | resolve_pi_command 把非 JSON 的 PI_DISPATCH_PI_CMD 当作单个可执行路径接受（:1764-1767）；'PATH 中找不到 pi' 的退出码是 3 |  |
| 第 8 节 | test_validate 的退出码：validate 错误为 EXIT_USAGE=2，prepare 的 .gitignore 拒绝为 EXIT_BLOCKED=3；test_preflight 的固定思考级别拒绝发生在 prepare 阶段，为 3 |  |
| 第 8 节 | wait 的“仍在运行”复用 EXIT_BLOCKED=3 常量；state.json 缺失（UNKNOWN）的情况没有测试 |  |
| 第 8 节 | doctor 的“思考级别不受本机 pi 支持”（:4726）和 allowed_executors 未命中都没有测试 |  |
| 第 8 节 | test_events_and_thinking 的“status shows unknown cost”依赖循环顺序（最后一个仓库是 STUB_NOCOST 例） |  |
| 第 8 节 | 工作区有未跟踪的 scripts/codekit/（`__init__.py`、`baseline.py`），而 sys.path[0] 是 KIT/scripts；测试不导入它，但基线输入清单应记录 |  |
| 第 8 节 | kit 前提的当前状态已只读核对：没有 CLAUDE.md，没有 .claude/rules，AGENTS.md 为 10932 字节，技能副本经 diff -rq 一致，test_v21 所需短语与示例 SHA 都存在 |  |
| 第 8 节 | 3.2 最低记录单位中，legacy_observation、comparison_projection_revision、new_consumer_module、acceptance_ids 无法从源码得到，需要 01-T1 运行和后续模块补齐 |  |

### 9.9 P4 更新：原 NOT_RUN 行的复核

9.2–9.7 中 execution_status 为 NOT_RUN 的行共 55 条（含 source_reported 3 条），逐条对照第 12 节的 P4 方法后，结果如下：

| 覆盖程度 | 条数 |
|---|---|
| 已覆盖 | 11 |
| 部分覆盖 | 21 |
| 未覆盖 | 18 |
| 不适用 | 5 |

- **不改原列**：第 9 节原有的 legacy_command_or_test_id、evidence_basis / execution_status 两列只描述旧自测，本节不改。P4 的结论单独列在下表，并在各行备注末尾加“P4 更新”标注（01-A16：旧自测与 P4 新测试分栏）。
- **四种覆盖程度的含义**：
  - **已覆盖**：条目规则中登记的行为，都由所列 P4 方法在 Windows 上 measured / PASS；
  - **部分覆盖**：只有写明的部分被断言，其余部分仍是 source_inspected；
  - **未覆盖**：没有 P4 方法断言；
  - **不适用**：条目是文档说法（source_reported），或是旧自测夹具本身，运行 P4 测试不能改变其状态。
- **平台**：只限 Windows；Linux、macOS 仍为 NOT_RUN。

| legacy_behavior_id | 第 9 节原状态（不改） | P4 方法（第 12 节编号） | P4 后的覆盖 | 仍未覆盖的部分与原因 |
|---|---|---|---|---|
| LB-CONTRACT-007 | source_inspected / NOT_RUN | P4-C21、C22（白盒） | 部分：risk_level 的大小写取值 | schema_version、task_id、plan_version、base_sha 的取值检查没有用例（P4 未编写） |
| LB-CONTRACT-029 | source_inspected / NOT_RUN | — | 未覆盖 | P4 未编写。重复键与 Infinity 的旧行为另见 compatibility-matrix.md D-01、D-02、D-20（P3），本节不据此改动状态 |
| LB-CONTRACT-030 | source_inspected / NOT_RUN | P4-C49 | 部分：Markdown 不是 UTF-8 时 UnicodeDecodeError 回溯、退出 1 | RecursionError、OverflowError、missing_fact_path_warnings 的 TypeError 等其余未捕获异常没有用例（P4 未编写） |
| LB-CONTRACT-031 | source_inspected / NOT_RUN | P4-C06（白盒） | 部分：不能序列化的 raw 经 :1432-1437 包装为“合同结构无效” | :1444-1446、1657-1658 两个 CLI 不可达分支没有用例（只能在进程内构造，P4 未编写） |
| LB-CONTRACT-032 | source_inspected / NOT_RUN | —（相关：P4-L17、C55 断言 prepare、run 拒绝 allowed_executors 未命中） | 未覆盖 | 没有断言 validate 对 allowed_executors、敏感与依赖清单、路径存在性、其余配置键放行（P4 未编写） |
| LB-CONTRACT-033 | source_inspected / NOT_RUN | —（相关：P4-C07 断言合同可以不写 provider/model；P4-C55、C56 断言 PI_EXEC_* 与合同冲突时拒绝） | 未覆盖 | run 时由 PI_EXEC_* 补齐缺失的 provider/model，没有用例（P4 未编写） |
| LB-CONTRACT-034 | source_inspected / NOT_RUN | P4-C46、C47、C48 | 部分：无子命令 2；缺参数与未知子命令 2；--version 0 | -h/--help 的 0 没有用例 |
| LB-CONTRACT-035 | source_inspected / NOT_RUN | P4-C21（白盒） | 部分：risk_level 取值错误与 Identity 不一致的级联 | :1152、1532、1573、1619-1622 的其余级联没有用例 |
| LB-CONTRACT-036 | source_inspected / NOT_RUN | — | 未覆盖 | derive-json 在 Windows 上写出 CRLF、Unicode 数字崩溃、--print 早返回，都没有用例（P4 未编写） |
| LB-EVENTS-002 | source_inspected / NOT_RUN | P4-C56 | 部分：PI_DISPATCH_PI_CMD 为 `[]` 时退出 2（:1768-1769） | 没有用例的有：`shutil.which("pi")`、Windows `.cmd` 包装解析、非 JSON 值按单个路径接受。原因：01-L05 要求受控环境必须设置 PI_DISPATCH_PI_CMD，legacy_harness 在未设置时拒绝运行，which 分支会去找真实的 pi；`.cmd` 分支 P4 未构造 |
| LB-EVENTS-003 | source_inspected / NOT_RUN | — | 未覆盖 | ensure_argv_safe 只对 `.cmd`/`.bat` 生效，P4 没有构造批处理形式的 pi 命令 |
| LB-EVENTS-004 | source_inspected / NOT_RUN | — | 未覆盖 | context_evidence 没有用例（test_legacy_events.py 模块说明列为未覆盖）。P4-L02 只把 preflight/context-files.json 当作时机标记，不断言其内容 |
| LB-EVENTS-009 | source_inspected / NOT_RUN | P4-E18、E19、E23、E24 | 已覆盖：空流、没有行尾的合法末行、不可解析行计数、末行截断与 expects_settled 的关系 | —（E23、E24 为白盒） |
| LB-EVENTS-015 | source_inspected / NOT_RUN | P4-E22、E33 | 已覆盖：四种 stderr 标记的 problem 或 flag、summary.md 的呈现；不传 stderr_path 与文件缺失的情形 | —（E33 为白盒） |
| LB-EVENTS-018 | source_inspected / NOT_RUN | P4-E21、E18、E30 | 已覆盖：usage 为空时 token 为 0（不是 null）；status --json 的 tokens 为 0 | — |
| LB-EVENTS-026 | source_inspected / NOT_RUN | P4-E32（白盒） | 部分：totalTokens 为非空字符串、且没有正数费用时抛 TypeError；空字符串不报错 | 非字符串的 text、含 NUL 的工具路径两类输入没有用例；run 停在 COLLECTING、wait 持续返回 3 的端到端后果也没有（模块说明列为未覆盖） |
| LB-EVENTS-029 | source_inspected / NOT_RUN | P4-C38、C39 | 已覆盖：只数紧凑写法、带空格计 0、附已运行秒数、长时间没有工具调用时的提示 | — |
| LB-EVENTS-030 | source_inspected / NOT_RUN | P4-E18 | 部分：空流时 problems 的顺序与多个字段的取值 | 字段全集、截断上限、覆盖写都没有专门断言 |
| LB-GATES-002 | source_reported / NOT_RUN | —（P4-G09 只锁定门禁键 G0…G6 的顺序） | 不适用 | 名称只见于 gates.md，运行测试不能证明文档说法；仍为 source_reported |
| LB-GATES-021 | source_inspected / NOT_RUN | — | 未覆盖 | review_hints 没有用例（P4 未编写） |
| LB-GATES-038 | source_inspected / NOT_RUN | P4-G22、G23、C61 | 部分（源码一侧）：<br>- 没有失败门禁时，AWE 仍要至少一项 --waive<br>- 已有结论后可以再次 verdict<br>- 已 ABANDONED 仍可 INTEGRATED | gates.md 一侧的说法仍是 source_reported；以哪一方为准属于 11.2 第 12 条 |
| LB-LIFE-006 | source_inspected / NOT_RUN | P4-L19、L20、L21 | 已覆盖：<br>- 300 s 过期接管（黑盒、白盒）<br>- 释放时不核对归属，导致互斥失效（白盒） | 真实并发竞态与文件系统的 mtime 语义没有验证 |
| LB-LIFE-008 | source_inspected / NOT_RUN | P4-C02（白盒）、C08、C53 | 部分：<br>- budget 缺省值 2/1200/2400/null<br>- Markdown Budget 不一致时的报错，prepare 退出 2 | :1565-1580 的取值范围校验（非正数、单次上限大于总额、cost_budget 格式）没有用例 |
| LB-LIFE-014 | source_inspected / NOT_RUN | — | 未覆盖 | 领取后、启动前失败时转为 INFRA_FAILURE（:3316-3332）：需要在这个窗口注入失败，P4 未构造 |
| LB-LIFE-017 | source_inspected / NOT_RUN | P4-G07、L01、C69；POSIX 的 P4-L03 为 NOT_RUN | 已覆盖（Windows CTRL_BREAK）：CANCELLED、run 退出 1、不输出“已取消。”、G1 拒绝 | POSIX 的 SIGINT 用例本机跳过（NOT_RUN） |
| LB-LIFE-021 | source_inspected / NOT_RUN（本次 1/2 check PASS） | P4-L22（Windows：`taskkill /F` 后 Pi 被 Job Object 回收） | 部分：Windows 分支另有 P4 实测 | “PDEATHSIG stops pi”只在 Linux 分支产生，本机不产生；P4 没有 Linux 用例，macOS 同样没有 |
| LB-LIFE-032 | source_reported / NOT_RUN | 源码一侧：P4-G22、G23、C61 | 不适用 | 技能文档中的状态表是文档说法，运行测试不能证明；源码实际允许的转换已由所列方法实测 |
| LB-LIFE-033 | source_inspected / NOT_RUN | P4-C45、C33 | 部分：<br>- 按 task-id 取编号最大的 attempt，不要求 meta.json<br>- 找不到 attempt 时退出 2 | `collect --recover <task-id>` 指向错误 attempt 的端到端情形没有用例 |
| LB-LIFE-034 | source_inspected / NOT_RUN | — | 未覆盖 | prepare 读计划目录中的合同、run 读 attempt 内的副本，两者限额不同，没有用例（P4-L25 只测编号跨版本连续） |
| LB-LIFE-035 | source_inspected / NOT_RUN | P4-L02、C70、C71；POSIX 的 P4-L04 为 NOT_RUN | 部分（Windows）：<br>- 领取前收到 CTRL_BREAK，以 0xC000013A 结束<br>- prepare 的 setup 中为 PREPARE_FAILED，退出 1<br>- wait 轮询中没有输出就结束 | POSIX 领取前 SIGINT→130 本机跳过；:3319-3332 窗口与 collect 期间的中断没有用例 |
| LB-LIFE-036 | source_inspected / NOT_RUN | P4-L17、C55、C56 | 已覆盖：<br>- allowed_executors 未命中（prepare、run 都退出 3）<br>- PI_EXEC_* 冲突退出 2<br>- 思考级别固定冲突退出 3 | — |
| LB-LIFE-037 | source_inspected / NOT_RUN | —（P4-L25 在预检失败后再次 run，但不断言 preflight/ 的内容） | 未覆盖 | 预检证据被覆盖，没有断言 |
| LB-LIFE-038 | source_inspected / NOT_RUN | —（P4-C56 只构造了 claim/ 为目录的情形） | 未覆盖 | claim 为普通文件时 exists 与 is_dir 的判断不一致，没有构造 |
| LB-LIFE-039 | source_inspected / NOT_RUN | P4-L08 | 部分：budget_usage 按 run.json 的实际用时计入（实际用时构造为超过预留） | 真实运行中 grace 与回收等待使 wall_seconds 超过预留，没有断言 |
| LB-LIFE-040 | source_inspected / NOT_RUN | P4-G23（verdicts 01–04）、G10 与 G18（checks 01–03） | 部分：verdicts 与 checks 都从 01 起连续编号 | mutations/ 的编号没有断言 |
| LB-EXIT-003 | source_inspected / NOT_RUN | P4-C47、C48 | 部分：8 种 argparse 用法错误退出 2，且没有“ERROR:”；--version 退出 0 | --help/-h 没有用例 |
| LB-EXIT-004 | source_inspected / NOT_RUN（本次 1/3 check PASS） | — | 未覆盖 | dispatch-pi.sh 的解释器选择与退出码透传，只有旧自测的 POSIX 用例（本机 0 个 check）；P4 没有 wrapper 用例 |
| LB-EXIT-027 | source_reported / NOT_RUN | 源码一侧：P4-C32–C45 | 不适用 | 文档与技能中的退出码声明是文档说法；PowerShell 外层把 3 显示成 1 属于宿主行为（11.3 第 10 条） |
| LB-EXIT-029 | source_inspected / NOT_RUN | P4-C50、C51；POSIX 的 P4-C52 为 NOT_RUN | 已覆盖（Windows）：<br>- 非仓库目录退出 2<br>- 不存在的路径 NotADirectoryError 回溯，退出 1 | POSIX 分支（推断为 3）本机跳过 |
| LB-EXIT-030 | source_inspected / NOT_RUN | P4-C36 | 已覆盖 | — |
| LB-EXIT-031 | source_inspected / NOT_RUN | P4-G07、L01、C69、L02；POSIX 的 P4-L03 为 NOT_RUN | 部分：<br>- Pi 运行期间中断：CANCELLED，退出 1<br>- 领取前收到 CTRL_BREAK：0xC000013A | :3319-3332 窗口与 :3344 之后收集阶段的中断没有用例；POSIX 本机跳过 |
| LB-EXIT-032 | source_inspected / NOT_RUN | — | 未覆盖 | spawn 失败（spawn_error → INFRA_FAILURE，run 退出 1）没有用例。P4-C66 的 INFRA_FAILURE 来自“没有 assistant 回复” |
| LB-EXIT-033 | source_inspected / NOT_RUN | P4-C53–C65、C32–C45（assert_refused 等：stderr 恰为一行“ERROR: …”，逐项诊断在 stdout） | 部分：prepare、run、collect、verdict、branch、mark、cleanup、baseline、doctor、wait | smoke、derive-json、sync-adapters、mutate 的输出流没有逐项断言 |
| LB-EXIT-034 | source_inspected / NOT_RUN | — | 未覆盖 | status 的 EXIT 列没有断言（P4-C39 只断言 events_ok 列） |
| LB-EXIT-035 | source_inspected / NOT_RUN | P4-C55、C59、C60、C61、G20、G21 | 部分：prepare、verdict、branch、mark 的拒绝顺序 | smoke（:4767）与 metrics（:4585-4589）的拒绝顺序没有用例 |
| LB-EXIT-036 | source_inspected / NOT_RUN | P4-G10、G12 | 已覆盖：`check --only` 或非必要检查失败时，required_ok 只看运行了的必要检查 | — |
| LB-EXIT-037 | source_inspected / NOT_RUN | — | 未覆盖 | P4 有意在 Pi 存活时保留 PID 句柄，使 pid_alive 的结果确定（test_legacy_lifecycle.py 模块说明）；tasklist 失败需要替换系统命令，未构造 |
| LB-EXIT-038 | source_inspected / NOT_RUN | P4-C45 | 已覆盖 | — |
| LB-EXIT-039 | source_inspected / NOT_RUN | — | 未覆盖 | derive-json 在校验之前就写 JSON，没有用例 |
| LB-EXIT-040 | source_inspected / NOT_RUN | P4-C49 | 部分：返回 1（Markdown 不是 UTF-8） | 返回 3（`git rev-parse HEAD` 失败）没有用例 |
| LB-TEST-H01 | source_inspected / NOT_RUN | — | 不适用 | 这是旧自测的夹具，P4 不改变它。最终取证 `bl-01final-test-dispatch-20260925` 再次使用这些夹具，256 个 check 全部 PASS，但仍没有 check 直接断言夹具的行为 |
| LB-TEST-H02 | source_inspected / NOT_RUN | — | 不适用 | 最终取证再次观察到分段、PASS 行、汇总行 `256 checks, 0 failed` 与退出 0，与规则一致，但没有 check 断言 |
| LB-TEST-009 | source_inspected / NOT_RUN（本次 3/4 check PASS） | 相关：P4-L22（Windows 上的恢复） | 未覆盖 | 登记的 “PDEATHSIG stops pi” 只在 Linux 分支产生，本机不产生；P4 没有 Linux 用例 |
| LB-TEST-016 | source_inspected / NOT_RUN（本次 0/2 check PASS） | — | 未覆盖 | 只在 POSIX 上运行；P4 没有 wrapper 用例 |
| LB-TEST-COV-10 | source_inspected / NOT_RUN（本次 6/7 check PASS） | P4-L22、L23、L24、C57 | 部分：第 10 节列出的 Windows 缺口已覆盖，包括 pid 存活时拒绝、COLLECTING 恢复、沿用 run.json、*.partial 改名、缺 --recover 时的 2 | 登记的 Linux check 仍不产生；macOS、pid_alive 失败与 PID 复用都没有覆盖 |

### 9.10 完整性审查更新：3.2 的 input_fixture_ref 与 comparison_projection_revision 回填（2026-09-26）

0.4 与 9.1 写着这两列“本文不填写”“由 P3 负责”，但 P3 建立 legacy fixture 之后没有回填，11.6 第 2 条的“尚未定义”也已过时。本节按行补齐，第 9.2–9.7 各表的原有列不改。

**来源（source_inspected，2026-09-26 只读核对，没有运行命令）**：

- 比较投影修订：`codekit01-legacy-projection-v1`，定义在 `tests/codekit01_legacy.py:55`（`PROJECTION_REVISION`）。两份 legacy 预期文件的 `projection_revision` 都是这个值，并在 `projection.included` 与 `projection.excluded` 中逐项写明比较与排除的字段及理由：
  - `tests/fixtures/codekit01/expected/legacy-contracts.json`（manifest 条目 `expected-legacy-contracts`，sha256 `71613d0082c5aa52808aeb31d136ea0097204934050ef0414ae428518addaf6b`）：16 个用例，比较 read、normalize_contract、validate_contract、validate_plan 第 3–6 步（进程内）、临时仓库中的旧 CLI `validate`、进程内 `derive_contract_json`；
  - `tests/fixtures/codekit01/expected/legacy-events.json`（manifest 条目 `expected-legacy-events`，sha256 `e889fef038d674d155a8b5cbb1403e07a8a469b36e9b8c8eec0ff44eba34973b`）：13 个用例 × expects_settled 为 true、false、null 三种取值，比较 `summarize_events` 输出的 26 个字段，排除 12 项。
- 下表中的 fixture_id 都是 `tests/fixtures/codekit01/manifest.json`（sha256 `50dc2fc3416385b4b33dc731e21416b42f74ad3753149bbc75038c3f2e4fef45`）中的条目。两个简写：
  - **合同全组**：legacy-contracts.json 的 16 个用例，即 `legacy-contract-{normalize-query-v1,auth-refresh-401-v1,template}-{md,json}` 这 3 对原合同，加 13 个 `negative-legacy-contract-*`；
  - **事件全组**：legacy-events.json 的 13 个用例，即 10 个 `legacy-stub-events-*` 加 3 个 `negative-legacy-events-*`。
- 表中所说的“投影中观察到”，指该行的规则在锁定预期中有对应的观察值；判断依据是预期文件内容与生成函数源码。
- **收尾轮更新（2026-09-26）**：收尾轮改动后，`PROJECTION_REVISION` 位于 `tests/codekit01_legacy.py:69`；`expected/legacy-contracts.json` 现为 22 个用例（sha256 5328bb62721095f07ac48350c53aa74e6a0e8dc64440ab15a713c618fc866ed0，新增 D-20–D-23 的 6 个负例）；manifest 现为 188 条（sha256 95c58a9b5a68166e104ee8a719385d43a8f346bff96ab96806518d6c94a830e0）。上文的摘要是完整性审查时的字节，保留为历史。9.10.1 的“合同全组”仍指原 16 个用例，新增的 6 个见 9.10.5。

**覆盖程度的含义**：

- **覆盖**：该行规则的主要分支（包括拒绝或关键判定）在所列 fixture 的锁定投影中都有观察值；表中另列没有样本的边界写法。
- **部分**：只有写明的部分有观察值。
- **仅通过路径**：有效样本经过了该规则，但它的拒绝或警告分支没有样本。迁移比较时，这些分支按 NOT_COVERED 处理。
- **NOT_COVERED**：没有 fixture 或锁定投影观察到该行规则，原因写在最后一列。

**证据状态（回填不改变任何一行的 evidence_basis / execution_status）**：

- 这些锁定投影的差分由 `tests/test_codekit01_fixtures.py` 的 `DifferentialTests` 执行。最终取证 `bl-01final-test-codekit01-fixtures-20260925` 只有命令级证据（归档 `run/stderr.bin` 140 字节，sha256 `689389be7fbd34cdcb40ebe00a954113c293ed9384157b991f72cfee60aa8261`：36 个“.”、`Ran 36 tests`、`OK`），**方法级 NOT_RUN**；`python tests/codekit01_legacy.py --check` 的结果没有归档，不计。 **收尾轮更新（2026-09-26）**：收尾取证以 `-v` 运行了 fixtures 测试（`bl-01closure-test-codekit01-fixtures-v-20260926`，归档 [run/stderr.bin](evidence/closure/bl-01closure-test-codekit01-fixtures-v-20260926/run/stderr.bin) 13127 字节，sha256 95faa68cea9315a4a73cc4bfc4223916e56b8eb1b9e5694fa1415fdf1c8b169a，与原件相同，见 0.5 末尾）：`DifferentialTests` 的 7 个方法（包括 `test_legacy_contract_projection_unchanged`、`test_legacy_event_projection_unchanged`）与 `CompatMatrixDCaseTests` 的 5 个方法都是 `... ok`；`python tests/codekit01_legacy.py --check` 另有收尾取证 `bl-01closure-legacy-check-20260926`（`38 checks, 0 differ`）。它们比较的是“以当前旧实现字节重算的结果”与锁定预期，即旧路径的回归比较，不是文档 6.6 的新旧路径差分；属于 01 新代码测试一栏（01-A16），不改变第 9.2–9.7 节任何一行的 evidence_basis / execution_status。
- 锁定预期只在 Windows Server 2025 + Python 3.12.10 上生成与核对；Linux、macOS 为 NOT_RUN。
- 第 9.2–9.7 节的 evidence_basis / execution_status 两列仍只描述旧自测 `tests/test_dispatch.py`（01-A16 分栏），本节不改。

#### 9.10.1 LB-CONTRACT（36 行：覆盖 5、部分 16、仅通过路径 4、NOT_COVERED 11）

| legacy_behavior_id | input_fixture_ref | comparison_projection_revision | 投影中观察到的内容 | 覆盖 | 没有覆盖的部分与原因 |
|---|---|---|---|---|---|
| LB-CONTRACT-001 | `negative-legacy-contract-json-schema-version-true`、`negative-legacy-contract-json-base-sha-short-oid`、`negative-legacy-contract-json-base-sha-trailing-newline`、`legacy-contract-template-json` | `codekit01-legacy-projection-v1` | schema_version 为 true 时 `== 1` 成立、0 个错误；7 位短 OID 被 SHA_RE 拒绝；末尾带换行的 base_sha 不报格式错误（只报 Markdown 不一致）；模板中 task_id、provider、model 的占位值被拒绝 | 部分 | PLAN_KEY_RE、ITEM_ID_RE 只经过合法值；其余常量没有专门样本 **收尾轮更新**：ITEM_ID_RE 另有末尾换行被接受的样本，见 9.10.5 |
| LB-CONTRACT-002 | `negative-legacy-contract-md-missing-scope-section`、`legacy-contract-template-md`、`legacy-contract-template-json` | `codekit01-legacy-projection-v1` | 缺 `## Scope` 时报“缺少章节”；模板的授权与集成取值合法，只经过通过路径 | 部分 | 词表外取值、受保护模式（PROTECTED_PATTERNS 与 extra_protected_paths）没有样本 |
| LB-CONTRACT-003 | 合同全组中 normalize_contract 可执行的 15 例（`negative-legacy-contract-json-utf8-bom` 在读取时失败，不到这一步） | `codekit01-legacy-projection-v1` | 规范化后的完整合同；`defaults_added` 在 14 例中是 `/setup/0/expected_exit_code`，模板为空 | 部分 | 3.2 表中其余缺省值没有被触发（样本都写全了这些字段）；`normalize_contract({})` 没有样本 |
| LB-CONTRACT-004 | 同 LB-CONTRACT-003 | `codekit01-legacy-projection-v1` | 只补缺失的键（setup 项的 expected_exit_code） | 部分 | 显式 null 保留、类型不对时不补、load_attempt 的读取时缺省没有样本 |
| LB-CONTRACT-005 | — | — | — | NOT_COVERED | 没有样本触发 TypeError、AttributeError、ValueError、KeyError 的包装分支；能解析的样本顶层都是对象 |
| LB-CONTRACT-006 | — | — | — | NOT_COVERED | 没有顶层不是对象、节类型错误的样本；`negative-legacy-contract-json-utf8-bom` 在 validate_plan 第 4 步就返回，不到这一层（见 LB-CONTRACT-019） |
| LB-CONTRACT-007 | `negative-legacy-contract-json-schema-version-true`、`negative-legacy-contract-json-plan-version-float`、`negative-legacy-contract-json-plan-version-string`、`negative-legacy-contract-json-task-id-mismatch`、`negative-legacy-contract-json-base-sha-short-oid`、`negative-legacy-contract-json-base-sha-trailing-newline`、`legacy-contract-template-json` | `codekit01-legacy-projection-v1` | schema_version=true 与 plan_version=1.0 被接受（兼容矩阵 D-04、D-05）；plan_version="1"、task_id 不符、短 OID 被拒绝，报错原文锁定 | 覆盖 | risk_level 的词表外取值没有样本（只有与 Markdown 不一致的样本，见 LB-CONTRACT-016） |
| LB-CONTRACT-008 | 合同全组中的有效取值 | `codekit01-legacy-projection-v1` | 授权取值合法，只经过通过路径 | 仅通过路径 | 词表外取值、缺 local_edit 的拒绝没有样本 |
| LB-CONTRACT-009 | `legacy-contract-template-json` | `codekit01-legacy-projection-v1` | provider、model 为占位文本时报“不合法” | 部分 | thinking、tools、context_files 的拒绝与 local_test 警告没有样本 |
| LB-CONTRACT-010 | `negative-legacy-contract-md-missing-scope-section`（经 derive_contract_json） | `codekit01-legacy-projection-v1` | 由缺 Scope 节的 Markdown 派生的 JSON 报“scope 至少要允许修改或新增一个文件”（3.3 第 20 条）；其余样本只经过通过路径 | 部分 | 路径模式错误、受保护路径、forbidden 重叠、dependency_changes 取值错误没有样本 |
| LB-CONTRACT-011 | 合同全组中的有效命令项 | `codekit01-legacy-projection-v1` | 合法的 setup 与 checks 项通过 | 仅通过路径 | 3.3 命令项表 a–k 的拒绝没有样本 **收尾轮更新**：另有 setup id 带末尾换行被接受的边界样本，仍是仅通过路径，见 9.10.5 |
| LB-CONTRACT-012 | 合同全组的 derive_contract_json（由 Markdown 派生的 JSON） | `codekit01-legacy-projection-v1` | 派生合同的 DoD evidence 报“不是已定义的检查 id，也不是 scope/review”（3.3 第 30 条） | 部分 | 缺必要检查、DoD 为空、id 重复、text 缺失，以及“必要检查没有被 DoD 引用”的警告没有样本 |
| LB-CONTRACT-013 | 合同全组中的有效取值 | `codekit01-legacy-projection-v1` | budget 取值合法 | 仅通过路径 | 越界值与 cost_budget（含 Infinity，D-20）没有样本 **收尾轮更新**：cost_budget 为 NaN、Infinity 的负例已加入，改为部分，见 9.10.5 |
| LB-CONTRACT-014 | `legacy-contract-template-md`、`legacy-contract-template-json` | `codekit01-legacy-projection-v1` | Markdown 与 JSON 的占位符都被拒绝，报错原文锁定 | 覆盖 | 小写 `replace_with`、Unicode 转义写法没有样本 |
| LB-CONTRACT-015 | `negative-legacy-contract-md-missing-scope-section`、`negative-legacy-contract-md-utf8-bom`、`legacy-contract-template-md` | `codekit01-legacy-projection-v1` | 缺章节；以 BOM 开头时标题不匹配（D-13）；模板标题不匹配 | 覆盖 | `## Budget (v1)` 等写法、捕获在字符集外停止的边界没有样本 |
| LB-CONTRACT-016 | `negative-legacy-contract-json-base-sha-short-oid`、`negative-legacy-contract-json-base-sha-trailing-newline`、`negative-legacy-contract-json-duplicate-key-last-differs`、`legacy-contract-template-md`、`legacy-contract-template-json` | `codekit01-legacy-projection-v1` | base_sha、risk_level、plan_version、integration_actions 与 executor 的 Markdown/JSON 不一致，报错原文与顺序锁定 | 覆盖 | thinking 不一致、全角冒号导致取值为 None 没有样本 |
| LB-CONTRACT-017 | `negative-legacy-contract-md-missing-scope-section`、`legacy-contract-template-md`、`legacy-contract-template-json` | `codekit01-legacy-projection-v1` | “Markdown 未列出 JSON 中的路径”、dependency_changes 不一致；模板中 V01 的命令与 argv 不一致 | 部分 | Budget 三项、检查 id 所在行、DoD 编号的不一致没有样本 |
| LB-CONTRACT-018 | LB-CONTRACT-016 所列样本；合同全组的 derive_contract_json | `codekit01-legacy-projection-v1` | 不一致时一律 ERROR，不采用任何一方；派生 JSON 与原 JSON 不同（`derived_equals_parsed_json=false`） | 部分 | prepare、baseline 的拒绝与运行时执行说明没有样本 |
| LB-CONTRACT-019 | `negative-legacy-contract-json-utf8-bom`、`negative-legacy-contract-md-crlf-line-endings`；合同全组的临时仓库 CLI `validate` | `codekit01-legacy-projection-v1` | JSON 带 BOM 时第 4 步报解析失败并立即返回，没有不可见字符警告；Markdown 的 CRLF 规范化后通过（D-12）；第 5–7 步的输出顺序 | 部分 | 缺文件、符号链接、Markdown 非 UTF-8 的 traceback、RecursionError 没有样本 **收尾轮更新**：Markdown 非 UTF-8 与 RecursionError 已有样本，见 9.10.5 |
| LB-CONTRACT-020 | 合同全组的临时仓库 CLI `validate` | `codekit01-legacy-projection-v1` | base_sha 不在临时仓库中：报“不存在或不是提交”，退出 2 | 部分 | base_sha 存在时的 AGENTS.md、HEAD、Repository facts 提示被投影排除（`projection.excluded` 第 2 条：fixture 的 base_sha 都是虚构值） |
| LB-CONTRACT-021 | `negative-legacy-contract-md-utf8-bom`、`negative-legacy-contract-json-utf8-bom` | `codekit01-legacy-projection-v1` | Markdown 以 BOM 开头时报 U+FEFF 警告；JSON 解析失败时不产生这类警告 | 部分 | 每个文件 5 条的上限、同一行多个字符合并、JSON 中转义文本不算等没有样本 |
| LB-CONTRACT-022 | — | — | — | NOT_COVERED | 只在 base_sha 存在时运行，被投影排除（同 LB-CONTRACT-020） |
| LB-CONTRACT-023 | 合同全组的临时仓库 CLI `validate`（16 例） | `codekit01-legacy-projection-v1` | stdout 的逐项诊断与汇总行“合同无效：N 个错误，M 个警告。”，stderr 为空，退出 2 | 部分 | 16 例的 base_sha 都不在临时仓库中，只有退出 2；退出 0、1、3 没有样本 **收尾轮更新**：已有退出 1 的样本，见 9.10.5 |
| LB-CONTRACT-024 | 合同全组的 derive_contract_json（Markdown 侧） | `codekit01-legacy-projection-v1` | 进程内 `derive_contract_json(title=None)` 的派生 JSON 与问题列表，以及派生 JSON 的 validate_contract 结果 | 覆盖（进程内） | CLI 写文件、`--title`、`--force`、长标题 NOTE 被投影排除（`projection.excluded` 第 5 条） |
| LB-CONTRACT-025 | 同 LB-CONTRACT-024 | `codekit01-legacy-projection-v1` | 3 份原合同及其 Markdown 负例的 Scope 与命令行解析结果 | 部分 | 解析规则的边界写法没有专门样本 |
| LB-CONTRACT-026 | — | — | — | NOT_COVERED | derive-json 子命令的流程与退出码不在投影中（投影只在进程内调用 derive_contract_json） |
| LB-CONTRACT-027 | 合同全组的临时仓库 CLI `validate` | `codekit01-legacy-projection-v1` | 合法的计划标识（`normalize-query.v1`、`auth-refresh-401.v1`、`contract-template.v1`）通过 | 仅通过路径 | 非法标识与路径形式的参数没有样本 |
| LB-CONTRACT-028 | — | — | — | NOT_COVERED | prepare、baseline 对 validate_plan 的调用不在投影中 |
| LB-CONTRACT-029 | `negative-legacy-contract-json-duplicate-key-first-differs`、`negative-legacy-contract-json-duplicate-key-last-differs`、`negative-legacy-contract-md-crlf-line-endings` | `codekit01-legacy-projection-v1` | 重复键以后出现的为准（first-differs 0 个错误，last-differs 只报 Markdown 不一致，D-01）；CRLF 规范化后通过（D-12） | 部分 | NaN、Infinity 没有 legacy fixture（D-20，acceptance.md 第 10 节 M-04） **收尾轮更新**：D-20 的 NaN、Infinity 负例已加入，改为覆盖，见 9.10.5 |
| LB-CONTRACT-030 | — | — | — | NOT_COVERED | 没有样本触发未捕获异常；投影规定出现 traceback 时只记最后一行，锁定时全部用例都没有出现 **收尾轮更新**：D-21、D-22 的负例触发了 RecursionError 与 UnicodeDecodeError，改为部分，见 9.10.5 |
| LB-CONTRACT-031 | — | — | — | NOT_COVERED | 经 CLI 不可达；进程内投影也没有用非法 plan_key 调用 |
| LB-CONTRACT-032 | `negative-legacy-contract-json-unknown-top-level-field` | `codekit01-legacy-projection-v1` | 顶层未知字段不校验，0 个错误 | 部分 | allowed_executors、敏感与依赖清单、路径存在性、其余配置键没有样本 |
| LB-CONTRACT-033 | — | — | — | NOT_COVERED | 运行时的 resolve_executor 不在投影中 |
| LB-CONTRACT-034 | — | — | — | NOT_COVERED | argparse 与 main 的退出码不在投影中（投影只运行 `validate <plan_key>`） |
| LB-CONTRACT-035 | — | — | — | NOT_COVERED | 本行登记的级联（非法 id、per_attempt、Identity 与 Budget 比较）没有样本；缺 Scope 节造成的另一种级联见 LB-CONTRACT-017 |
| LB-CONTRACT-036 | — | — | — | NOT_COVERED | 写文件、`--print`、Unicode 数字崩溃都在 CLI 写入路径上，被投影排除 |

#### 9.10.2 LB-EVENTS（30 行：覆盖 9、部分 4、仅通过路径 2、NOT_COVERED 15）

| legacy_behavior_id | input_fixture_ref | comparison_projection_revision | 投影中观察到的内容 | 覆盖 | 没有覆盖的部分与原因 |
|---|---|---|---|---|---|
| LB-EVENTS-001 | 事件全组 | `codekit01-legacy-projection-v1` | 同一流在 expects_settled 为 true、false、null 时的 complete 与 problems，例如 `legacy-stub-events-nosettle` 在 true 与 null 时不完整、false 时完整 | 部分 | 由 `--version` 推出 expects_settled 的 `_expects_settled` 不在投影中（投影把它作为参数固定，`projection.primary_expects_settled`） |
| LB-EVENTS-002 | — | — | — | NOT_COVERED | 投影只调用 summarize_events，不定位 pi |
| LB-EVENTS-003 | — | — | — | NOT_COVERED | 同上，ensure_argv_safe 不在投影中 |
| LB-EVENTS-004 | — | — | — | NOT_COVERED | 同上，context_evidence 不在投影中 |
| LB-EVENTS-005 | — | — | — | NOT_COVERED | stub 的 `--help`、`--list-models` 输出没有做成 fixture |
| LB-EVENTS-006 | — | — | — | NOT_COVERED | 预检不在投影中 |
| LB-EVENTS-007 | — | — | — | NOT_COVERED | 预检不在投影中 |
| LB-EVENTS-008 | — | — | — | NOT_COVERED | 预检与 run 不在投影中 |
| LB-EVENTS-009 | `negative-legacy-events-ok-unparseable-line`、`negative-legacy-events-ok-truncated-tail` | `codekit01-legacy-projection-v1` | parse_error_lines（第 2 行；第 19 行）、truncated=true，可读的行照常计入 | 覆盖 | 空行、超长行没有样本 |
| LB-EVENTS-010 | 事件全组中的 10 条 `legacy-stub-events-*` | `codekit01-legacy-projection-v1` | event_counts 中 stub 产生的各类事件 | 覆盖（限 stub 产生的类型） | stub 不产生的事件类型没有样本 |
| LB-EVENTS-011 | `legacy-stub-events-ok`、`legacy-stub-events-nosettle`、`legacy-stub-events-startfail`、`negative-legacy-events-ok-truncated-tail` | `codekit01-legacy-projection-v1` | complete 与 terminal_event：以 agent_settled 结束；只有 agent_end；没有结束事件；尾部截断 | 覆盖 | — |
| LB-EVENTS-012 | `legacy-stub-events-error`、`legacy-stub-events-textcall`、`legacy-stub-events-startfail` | `codekit01-legacy-projection-v1` | stopReason=error 与错误文本；正文里写成文本的工具调用；没有 assistant 消息时 stopReason=None | 覆盖 | — |
| LB-EVENTS-013 | `legacy-stub-events-model`、`legacy-stub-events-startfail`、`legacy-stub-events-ok` | `codekit01-legacy-projection-v1` | 实际模型不符、缺失、相符（actual_models、response_models、model_match） | 覆盖 | — |
| LB-EVENTS-014 | `legacy-stub-events-ok-ptl-high`、`legacy-stub-events-ok-ptl-low`、`legacy-stub-events-ok` | `codekit01-legacy-projection-v1` | 回报 high 且相符；回报 low 与要求的 high 不符；不回报（not_reported） | 覆盖 | — |
| LB-EVENTS-015 | — | — | — | NOT_COVERED | 投影不采集 stderr，stderr_flags 恒为空列表（`projection.excluded` 最后一条） |
| LB-EVENTS-016 | `legacy-stub-events-ok`、`negative-legacy-events-ok-duplicate-final-message-end` | `codekit01-legacy-projection-v1` | 两条 assistant 消息累加为 input 2000、output 400；重复一条后为 3000、600 | 覆盖 | — |
| LB-EVENTS-017 | `negative-legacy-events-ok-duplicate-final-message-end` | `codekit01-legacy-projection-v1` | 重复投递的 message_end 被再次累计用量与费用（兼容矩阵 D-17） | 覆盖 | — |
| LB-EVENTS-018 | `legacy-stub-events-startfail` | `codekit01-legacy-projection-v1` | 没有任何用量事件时 token 全为 0、费用 unknown（`projection.token_zero_semantics` 写明这里的 0 可能表示未知） | 部分 | 消息带 usage 但缺 token 字段的情形没有 fixture（只有 P4-E21 在测试中现场构造） |
| LB-EVENTS-019 | `legacy-stub-events-ok`、`legacy-stub-events-ok-nocost`、`legacy-stub-events-startfail` | `codekit01-legacy-projection-v1` | 费用 status 为 estimated；unknown 且 unpriced_messages=2；unknown 且没有消息 | 覆盖 | — |
| LB-EVENTS-020 | — | — | — | NOT_COVERED | status、summary.md 与 verdict 中的呈现不在投影中 |
| LB-EVENTS-021 | — | — | — | NOT_COVERED | 投影止于 summarize_events 的 problems 与 ok；G1、collect 状态与 run 退出码没有执行 |
| LB-EVENTS-022 | 事件全组 | `codekit01-legacy-projection-v1` | 流中没有像凭据的文本，脱敏只经过通过路径 | 仅通过路径 | 各类凭据模式的替换没有样本 |
| LB-EVENTS-023 | 事件全组 | `codekit01-legacy-projection-v1` | 同 LB-EVENTS-022 | 仅通过路径 | 结构脱敏的替换没有样本 |
| LB-EVENTS-024 | — | — | — | NOT_COVERED | summarize_events 的第二个返回值（最终 assistant 文本）被投影排除，extract_report 不在投影中 |
| LB-EVENTS-025 | — | — | — | NOT_COVERED | ambiguity_* 字段被投影排除，调用时 plan_text 为空 |
| LB-EVENTS-026 | — | — | — | NOT_COVERED | 没有非数值 totalTokens 的样本（P4-E32 在测试中现场构造） |
| LB-EVENTS-027 | — | — | — | NOT_COVERED | doctor、smoke 不在投影中 |
| LB-EVENTS-028 | 事件全组中的 10 条 `legacy-stub-events-*` | `codekit01-legacy-projection-v1` | stub 在 a4fa199 的输出字节：7 个 STUB_SCENARIO 取值（ok、nosettle、startfail、model、error、scope、textcall），其中 ok 另有 STUB_NOCOST=1、STUB_PTL=low、STUB_PTL=high 三种变体 | 部分 | 其余场景（hang、commit、outside、touchmain、noreport、tmpclean、tempsequence、readplan、typo、planner、ambiguous、conflict、checkonly）与非运行命令（`--help`、`--version`、auth、`--list-models`）没有做成 fixture |
| LB-EVENTS-029 | — | — | — | NOT_COVERED | _live_progress 不在投影中 |
| LB-EVENTS-030 | 事件全组 | `codekit01-legacy-projection-v1` | `projection.included` 列出的 26 个字段，以及 problems 的原文与顺序 | 部分 | `projection.excluded` 列出的 12 项、截断上限与覆盖写没有样本 |

#### 9.10.3 其余区域（158 行）

| 区域 | input_fixture_ref | comparison_projection_revision | 覆盖 | 原因 |
|---|---|---|---|---|
| LB-GATES-001–038（38 行） | — | — | NOT_COVERED | 没有候选树、补丁、范围与门禁结果的 fixture，也没有锁定的比较投影（兼容矩阵第 8 节第 9 条的缺样本清单）。这些行为只由旧自测与 P4 特征化回归在临时仓库中现场构造并断言（见 9.10.4） **收尾轮更新**：按 R-P12 改由代码内联 fixture 回填，38 行中 30 行有内联引用，见 9.10.6 |
| LB-LIFE-001–040（40 行） | — | — | NOT_COVERED | 没有超时、取消、恢复、锁与预算、attempt 状态的 fixture 与投影；原因同上 **收尾轮更新**：按 R-P12 改由代码内联 fixture 回填，40 行中 30 行有 fixture 引用（LB-LIFE-008 另有 manifest 负例），见 9.10.5、9.10.6 |
| LB-EXIT-006 | 合同全组的临时仓库 CLI `validate` | `codekit01-legacy-projection-v1` | 部分 | 只有退出 2（原因同 LB-CONTRACT-023）；退出 0、1、3 没有样本 **收尾轮更新**：已有退出 1 的样本，见 9.10.5 |
| LB-EXIT-033 | 合同全组的临时仓库 CLI `validate` | `codekit01-legacy-projection-v1` | 部分 | 只有 validate：逐项诊断在 stdout，stderr 为空；其他子命令的输出流没有 fixture **收尾轮更新**：已有出现 traceback 时 stdout 为空的样本，见 9.10.5 |
| LB-EXIT 其余 38 行 | — | — | NOT_COVERED | 各子命令的退出码、wait 的输出与状态解释没有 fixture 与投影 **收尾轮更新**：LB-EXIT-002、040 已有 manifest 负例（9.10.5）；按 R-P12 回填后，40 行中 29 行有 fixture 引用，见 9.10.6 |
| LB-TEST-S01 | 事件全组中的 10 条 `legacy-stub-events-*` | `codekit01-legacy-projection-v1` | 部分 | 同 LB-EVENTS-028 |
| LB-TEST 其余 39 行 | — | — | NOT_COVERED | 这些行描述旧自测本身（夹具、测试函数、C.4 覆盖统计），不是被测行为，fixture 差分不以它们为对象。LB-TEST-COV-01（旧合同默认值）所说的行为，由 LB-CONTRACT-003、004 的部分覆盖间接涉及 **收尾轮更新**：LB-TEST-COV-01–12 按 C.4 项归属有代码内联引用；其余 27 行仍为 NOT_COVERED，见 9.10.6 |

合计 224 行：覆盖、部分或仅通过路径 43 行（LB-CONTRACT 25、LB-EVENTS 15、LB-EXIT 2、LB-TEST 1），NOT_COVERED 181 行。 **收尾轮更新（2026-09-26）**：新统计见 9.10.6：有 fixture 引用的 157 行（manifest 47 行，其中 23 行同时有代码内联引用；只有代码内联引用的 110 行），NOT_COVERED 67 行。

#### 9.10.4 第 12 节 P4 特征化方法的这两个字段

- 第 12 节 159 个方法的 input_fixture_ref 与 comparison_projection_revision **都为空**：
  - 输入由 `tests/legacy_harness.py` 在每个用例的临时区域中现场构造（临时 Git 仓库、合同、stub 场景、用 `set_state` 或改写证据文件构造的状态），没有 manifest 条目，也没有封存的输入字节；
  - 断言直接写在测试代码中，不经过带修订号的比较投影。
- 它们是 a4fa199 旧实现现状的 measured 观测（只限 Windows，第 12 节），**不是**文档 6.6 意义上的 fixture 差分：同一输入没有同时喂给旧路径与新兼容路径，也没有比较投影可以复用。迁移比较时，这些行为按 NOT_COVERED 处理，直到补上 fixture 与投影。
- 补齐需要改测试代码（把相关场景的输入固定为 fixture、登记 manifest、定义投影并锁定旧预期）。本次审查不改代码，已登记为 acceptance.md 第 7 节的未完成项。
- **收尾轮更新（2026-09-26，裁决 R-P12）**：上面第 1、2 条“都为空”“迁移比较时按 NOT_COVERED 处理”的判断已被 R-P12 取代。输入由测试代码确定性构造的方法，其 input_fixture_ref 写成 `inline:<测试文件>::<类>.<方法>@<测试文件 sha256>`，comparison_projection_revision 为 `codekit01-characterization-v1`（该方法中的断言集合）。159 个方法的写法见 12.10，第 9 节各行的回填见 9.10.6。第 2 条中“不是文档 6.6 意义上的 fixture 差分”仍然成立：新路径不存在，差分 NOT_RUN，七类的状态见 9.10.7。第 3 条所说的“补齐需要改测试代码”不再需要；acceptance.md 第 7 节第 11、12 项的同步不在本文件的修订范围内。

#### 9.10.5 收尾轮更新：新增合同负例（D-20–D-23）的 manifest 回填（2026-09-26）

**来源（source_inspected，本次只读核对，没有运行命令）**：

- manifest `tests/fixtures/codekit01/manifest.json`：188 条，sha256 95c58a9b5a68166e104ee8a719385d43a8f346bff96ab96806518d6c94a830e0。
- 锁定预期 `tests/fixtures/codekit01/expected/legacy-contracts.json`：manifest 条目 `expected-legacy-contracts`，22 个用例，sha256 5328bb62721095f07ac48350c53aa74e6a0e8dc64440ab15a713c618fc866ed0，`projection_revision` 为 `codekit01-legacy-projection-v1`。
- 收尾轮新增 6 个合同负例。每个都由 `legacy-contract-normalize-query-v1-json` 或 `-md` 单一故障派生（`generator_revision` 为 `codekit01-legacy-fixtures-v2`），判断时与未修改的另一半配对。
- 锁定投影的变化：`projection.included` 新增一条，非有限数写成 `<non-finite:…>` 字符串；出现 traceback 时，按 `projection.excluded` 第 4 条只记录最后一行（调用栈含本机路径，属于机器定位）。

**锁定状态（01 新代码测试一栏，只作引用）**：收尾取证 `bl-01closure-legacy-check-20260926` 为 `38 checks, 0 differ`；`bl-01closure-test-codekit01-fixtures-v-20260926` 中，`DifferentialTests.test_legacy_contract_projection_unchanged` 与 `CompatMatrixDCaseTests` 的 `test_d20_non_finite_cost_amount`、`test_d21_deep_nesting`、`test_d22_invalid_utf8`、`test_d23_identifier_trailing_newline` 都是 ok（归档副本在 `evidence/closure/`，见 0.5 末尾）。这说明以当前旧实现字节重算的结果与锁定预期一致；不改变任何 LB 行的 evidence_basis / execution_status。

| fixture_id | 故障（兼容矩阵编号） | 锁定投影中旧实现的观察值 |
|---|---|---|
| `negative-legacy-contract-json-cost-budget-infinity` | D-20：`budget.cost_budget` 为 `{amount: Infinity, currency: USD}` | 读取成功，金额投影为 `<non-finite:Infinity>`；validate_contract 0 个错误、0 个警告，合同被接受；临时仓库 CLI `validate` 只报 base_sha 不存在，退出 2 |
| `negative-legacy-contract-json-cost-budget-nan` | D-20：金额为 NaN | validate_contract 报“budget.cost_budget 必须为 null 或 {amount, currency}”；CLI 另报 base_sha，共 2 个错误，退出 2 |
| `negative-legacy-contract-json-deep-nesting` | D-21：新增的顶层字段是 100000 层嵌套的空数组 | 读取时抛出未捕获的 RecursionError；CLI `validate` 以 traceback 退出 1，stdout 为空，最后一行为“RecursionError: maximum recursion depth exceeded while decoding a JSON array from a unicode string” |
| `negative-legacy-contract-json-invalid-utf8` | D-22：JSON 中插入字节 0xFF | validate_plan 第 4 步报“JSON 合同解析失败：'utf-8' codec can't decode byte 0xff in position 257: invalid start byte”后返回；CLI 退出 2 |
| `negative-legacy-contract-md-invalid-utf8` | D-22：Markdown 中插入字节 0xFF | 读取 Markdown 时抛出未捕获的 UnicodeDecodeError；CLI `validate` 以 traceback 退出 1，stdout 为空 |
| `negative-legacy-contract-json-setup-id-trailing-newline` | D-23：setup 项的 id 为 `S01` 加末尾换行 | ITEM_ID_RE（`^…$` 配 re.match）接受末尾换行，validate_contract 0 个错误；CLI 只报 base_sha，退出 2 |

按行回填如下，其余行不变。“原覆盖”指 9.10.1–9.10.3 中的值；表中 `…` 代表 `negative-legacy-contract`。

| legacy_behavior_id | 新增 input_fixture_ref（manifest） | comparison_projection_revision | 原覆盖 → 收尾轮后 | 新增的观察值 | 仍没有样本的部分 |
|---|---|---|---|---|---|
| LB-CONTRACT-001 | `…-json-setup-id-trailing-newline` | `codekit01-legacy-projection-v1` | 部分 → 部分 | ITEM_ID_RE 接受末尾换行 | PLAN_KEY_RE 只经过合法值；其余常量没有专门样本 |
| LB-CONTRACT-011 | `…-json-setup-id-trailing-newline` | 同上 | 仅通过路径 → 仅通过路径 | 多一个被接受的边界样本（setup id 带末尾换行） | 3.3 命令项表 a–k 的拒绝 |
| LB-CONTRACT-013 | `…-json-cost-budget-nan`、`…-json-cost-budget-infinity` | 同上 | 仅通过路径 → 部分 | 金额为 NaN 时被拒绝，为 Infinity 时被接受 | 非正数、单次上限大于总额等其余越界值 |
| LB-CONTRACT-019 | `…-json-deep-nesting`、`…-json-invalid-utf8`、`…-md-invalid-utf8` | 同上 | 部分 → 部分 | RecursionError 与 Markdown 非 UTF-8 没有被捕获；JSON 非 UTF-8 在第 4 步报解析失败 | 缺文件、符号链接 |
| LB-CONTRACT-023 | `…-json-deep-nesting`、`…-md-invalid-utf8` | 同上 | 部分 → 部分 | validate 以 traceback 退出 1，stdout 为空 | 退出 0、3 |
| LB-CONTRACT-029 | `…-json-cost-budget-nan`、`…-json-cost-budget-infinity` | 同上 | 部分 → 覆盖 | 旧 JSON 入口接受 NaN、Infinity 字面量（D-20） | `-Infinity` 没有样本 |
| LB-CONTRACT-030 | `…-json-deep-nesting`、`…-md-invalid-utf8` | 同上 | NOT_COVERED → 部分 | RecursionError、UnicodeDecodeError 以 traceback 退出 1（只比较最后一行） | OverflowError、missing_fact_path_warnings 的 TypeError 等其余未捕获异常 |
| LB-LIFE-008 | `…-json-cost-budget-nan`、`…-json-cost-budget-infinity` | 同上 | NOT_COVERED → 部分 | cost_budget 的格式检查：NaN 被拒绝，Infinity 被接受 | 缺省值（样本都写全了 budget）、非正数、单次上限大于总额 |
| LB-EXIT-002 | `…-json-deep-nesting`、`…-md-invalid-utf8` | 同上 | NOT_COVERED → 部分 | main 不捕获其他异常：traceback，退出 1 | DispatchError、KeyboardInterrupt 的映射不在 manifest 投影中（有代码内联引用，见 9.10.6） |
| LB-EXIT-006 | `…-json-deep-nesting`、`…-md-invalid-utf8` | 同上 | 部分 → 部分 | validate 退出 1 | 退出 0、3 |
| LB-EXIT-033 | `…-json-deep-nesting`、`…-md-invalid-utf8` | 同上 | 部分 → 部分 | 出现 traceback 时 stdout 为空 | validate 以外的子命令 |
| LB-EXIT-040 | `…-json-deep-nesting`、`…-md-invalid-utf8` | 同上 | NOT_COVERED → 部分 | validate 返回 1 | 返回 3（`git rev-parse HEAD` 失败） |

锁定预期只在 Windows Server 2025 + Python 3.12.10 上生成与核对（这些条目的 platform_scope 为 windows）；Linux、macOS 为 NOT_RUN。

#### 9.10.6 收尾轮更新：按裁决 R-P12 逐行回填 input_fixture_ref 与 comparison_projection_revision（2026-09-26）

裁决 R-P12 规定两种 input_fixture_ref 都合法：

- (a) manifest 登记的 fixture 文件，比较投影为 `codekit01-legacy-projection-v1`；
- (b) 代码内联 fixture，写成 `inline:<测试文件>::<类>.<方法>@<测试文件 sha256>`，比较投影为 `codekit01-characterization-v1`，即该方法中的断言集合。

本节按这两种形式重做 9.10.1–9.10.3 的统计。9.10.1–9.10.3 与 9.10.5 的原文不改。

**回填规则**：

- **manifest 一列**：取 9.10.1–9.10.3 的回填，加上 9.10.5 的更新。
- **代码内联一列**：取第 12 节的 P4 方法（完整写法见 12.10）。方法与行的对应取以下三个来源的并集：
  1. 第 12 节“LB 条目 / 源码行”列，即测试 docstring 的标注；
  2. 9.9 中判为“已覆盖”或“部分”的行，取 9.9 的“P4 方法”列。9.9 判为“未覆盖”或“不适用”的行不取，即使 9.9 提到了“相关”方法；
  3. LB-TEST-COV-01–12 这 12 行描述 C.4 项的回归覆盖，取第 12 节“C.4 项 / 01-A07 类别”列归入该项的方法。
- 本机跳过的 POSIX 方法（P4-L03、L04、C52）照列，但不计入；没有哪一行只靠它们。
- 没有逐分支核对的对应一律按“部分”计，不写“覆盖”。
- **证据状态不变**：回填只补文档 3.2 的两个字段。第 9.2–9.7 节的 evidence_basis / execution_status 两列仍只描述旧自测（01-A16）。代码内联引用对应的执行结果，是第 12 节的特征化结论（收尾取证，只限 Windows），不是文档 6.6 的新旧路径差分（9.10.7）。

**统计**（224 行）：

| 区域 | 行数 | manifest＋内联 | 仅 manifest | 仅内联 | NOT_COVERED | 完整性审查时的 NOT_COVERED（9.10.1–9.10.3） |
|---|---|---|---|---|---|---|
| LB-CONTRACT | 36 | 8 | 18 | 4 | 6 | 11 |
| LB-EVENTS | 30 | 11 | 4 | 10 | 5 | 15 |
| LB-GATES | 38 | 0 | 0 | 30 | 8 | 38 |
| LB-LIFE | 40 | 1 | 0 | 29 | 10 | 40 |
| LB-EXIT | 40 | 3 | 1 | 25 | 11 | 38 |
| LB-TEST | 40 | 0 | 1 | 12 | 27 | 39 |
| 合计 | 224 | 23 | 24 | 110 | **67** | 181 |

- 有 fixture 引用的共 157 行：manifest 47 行，即 9.10 的 43 行加上 9.10.5 的 LB-CONTRACT-030、LB-LIFE-008、LB-EXIT-002、LB-EXIT-040；代码内联 133 行；两者都有的 23 行。
- NOT_COVERED 由 181 行降为 67 行。下降的 114 行中，110 行只靠代码内联引用；另外 4 行（LB-CONTRACT-030、LB-LIFE-008、LB-EXIT-002、LB-EXIT-040）同时有 9.10.5 的新 manifest 负例与代码内联引用。
- manifest 部分的覆盖程度（按 9.10 的定义）：覆盖 15、部分 27、仅通过路径 5。
  - LB-CONTRACT：覆盖 6、部分 17、仅通过路径 3、NOT_COVERED 10。与 9.10.1 相比有三处变化：LB-CONTRACT-029 由部分改为覆盖，LB-CONTRACT-013 由仅通过路径改为部分，LB-CONTRACT-030 由 NOT_COVERED 改为部分。
  - LB-EVENTS 不变：覆盖 9、部分 4、仅通过路径 2。
  - 其余区域有 manifest 引用的 6 行都是部分。
- 代码内联的 133 行中：9.9 判为已覆盖的 11 行，9.9 判为部分的 20 行，按 C.4 项归属的 12 行，只按测试标注对应的 90 行。后两类没有逐分支核对，都按部分计。

**仍为 NOT_COVERED 的 67 行与原因**：

| 原因 | 行数 | 行 |
|---|---|---|
| （a）9.9 判为未覆盖：P4 没有编写，或需要特殊构造（批处理形式的 pi、领取后启动前的失败窗口、替换系统命令、Linux 分支等），manifest 也没有样本 | 16 | LB-CONTRACT-033、036；LB-EVENTS-003、004；LB-GATES-021；LB-LIFE-014、034、037、038；LB-EXIT-004、032、034、037、039；LB-TEST-009、016 |
| （b）不适用：条目是文档说法（source_reported）或旧自测夹具，运行测试不能改变其状态 | 5 | LB-GATES-002；LB-LIFE-032；LB-EXIT-027；LB-TEST-H01、H02 |
| （c）只有旧自测 `tests/test_dispatch.py` 的 check（bl-01t1 measured）：第 12 节没有方法标注这些行，manifest 也没有样本 | 23 | LB-CONTRACT-006、022、026、028；LB-EVENTS-006、024、025；LB-GATES-001、004、008、011、020、034；LB-LIFE-015、018、027、028、031；LB-EXIT-007、018、020、022、028 |
| （d）旧自测本身：这些行描述 `tests/test_dispatch.py` 的测试函数或 stub 的非运行命令，不是被测行为（9.10.3） | 23 | LB-TEST-S02、LB-TEST-001–008、010–015、017–024 |

- **（c）需要规划端决定**：
  - 旧自测的输入同样由测试代码构造（`make_repo`、`contract()`、stub 场景），但它是模块级函数加 check，不符合 R-P12 的 `<类>.<方法>` 写法，一个函数又对应许多 LB 行。是否另定写法（例如按函数名或 check 名）把旧自测登记为代码内联 fixture，R-P12 没有规定，本文不自行扩展。
  - 其中 12 行在第 12 节的描述中能找到明显相关的断言，但测试没有标注这些行，见下表各行的“线索”。本文不据此计入；是否补登，由规划端核对后决定。
- **平台**：代码内联引用的执行结果只限 Windows；manifest 锁定预期同样只在本机生成与核对。Linux、macOS 为 NOT_RUN。

逐行回填（224 行）：

| legacy_behavior_id | input_fixture_ref：manifest（`codekit01-legacy-projection-v1`） | input_fixture_ref：代码内联（`codekit01-characterization-v1`；P4 编号，完整写法见 12.10） | 回填后 | 覆盖程度与说明 |
|---|---|---|---|---|
| LB-CONTRACT-001 | 9.10.1：部分；9.10.5 新增 `negative-legacy-contract-json-setup-id-trailing-newline` | — | 仅 manifest |  |
| LB-CONTRACT-002 | 9.10.1：部分 | — | 仅 manifest |  |
| LB-CONTRACT-003 | 9.10.1：部分 | P4-C02、C03、C07 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-CONTRACT-004 | 9.10.1：部分 | P4-C03–C05 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-CONTRACT-005 | — | P4-C06 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-CONTRACT-006 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture |
| LB-CONTRACT-007 | 9.10.1：覆盖 | P4-C21、C22 | manifest＋内联 | 内联：9.9 判为部分 |
| LB-CONTRACT-008 | 9.10.1：仅通过路径 | — | 仅 manifest |  |
| LB-CONTRACT-009 | 9.10.1：部分 | — | 仅 manifest |  |
| LB-CONTRACT-010 | 9.10.1：部分 | — | 仅 manifest |  |
| LB-CONTRACT-011 | 9.10.1：仅通过路径；9.10.5 新增 `negative-legacy-contract-json-setup-id-trailing-newline`（被接受的边界样本，仍是仅通过路径） | — | 仅 manifest |  |
| LB-CONTRACT-012 | 9.10.1：部分 | — | 仅 manifest |  |
| LB-CONTRACT-013 | 9.10.1：仅通过路径 → 部分（9.10.5 新增 `negative-legacy-contract-json-cost-budget-nan`、`negative-legacy-contract-json-cost-budget-infinity`） | — | 仅 manifest |  |
| LB-CONTRACT-014 | 9.10.1：覆盖 | — | 仅 manifest |  |
| LB-CONTRACT-015 | 9.10.1：覆盖 | P4-C24 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-CONTRACT-016 | 9.10.1：覆盖 | P4-C09–C11、C17、C18、C20、C23 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-CONTRACT-017 | 9.10.1：部分 | P4-C08、C12–C16、C19 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-CONTRACT-018 | 9.10.1：部分 | P4-C16、C53 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-CONTRACT-019 | 9.10.1：部分；9.10.5 新增 `negative-legacy-contract-json-deep-nesting`、`negative-legacy-contract-json-invalid-utf8`、`negative-legacy-contract-md-invalid-utf8` | — | 仅 manifest |  |
| LB-CONTRACT-020 | 9.10.1：部分 | — | 仅 manifest |  |
| LB-CONTRACT-021 | 9.10.1：部分 | — | 仅 manifest |  |
| LB-CONTRACT-022 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture；manifest 投影排除了 base_sha 存在时才执行的分支（9.10.1） |
| LB-CONTRACT-023 | 9.10.1：部分；9.10.5 新增 `negative-legacy-contract-json-deep-nesting`、`negative-legacy-contract-md-invalid-utf8`（退出 1） | — | 仅 manifest |  |
| LB-CONTRACT-024 | 9.10.1：覆盖（进程内） | — | 仅 manifest |  |
| LB-CONTRACT-025 | 9.10.1：部分 | — | 仅 manifest |  |
| LB-CONTRACT-026 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture；derive-json 子命令不在 manifest 投影中（9.10.1） |
| LB-CONTRACT-027 | 9.10.1：仅通过路径 | — | 仅 manifest |  |
| LB-CONTRACT-028 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture。线索：P4-C53、C54、C64 断言了 prepare、baseline 调用 validate_plan 之后的拒绝（测试未标注本行） |
| LB-CONTRACT-029 | 9.10.1：部分 → 覆盖（9.10.5 新增 `negative-legacy-contract-json-cost-budget-nan`、`negative-legacy-contract-json-cost-budget-infinity`） | — | 仅 manifest |  |
| LB-CONTRACT-030 | NOT_COVERED → 部分（9.10.5：`negative-legacy-contract-json-deep-nesting`、`negative-legacy-contract-md-invalid-utf8`） | P4-C49 | manifest＋内联 | 内联：9.9 判为部分 |
| LB-CONTRACT-031 | — | P4-C06 | 仅内联 | 内联：9.9 判为部分 |
| LB-CONTRACT-032 | 9.10.1：部分 | — | 仅 manifest |  |
| LB-CONTRACT-033 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：run 时由 PI_EXEC_* 补齐缺失的 provider/model，没有用例（P4 未编写） |
| LB-CONTRACT-034 | — | P4-C46–C48 | 仅内联 | 内联：9.9 判为部分 |
| LB-CONTRACT-035 | — | P4-C21、C22 | 仅内联 | 内联：9.9 判为部分 |
| LB-CONTRACT-036 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：derive-json 在 Windows 上写出 CRLF、Unicode 数字崩溃、--print 早返回，都没有用例（P4 未编写） |
| LB-EVENTS-001 | 9.10.2：部分 | P4-E03、E06、E07 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-002 | — | P4-C56 | 仅内联 | 内联：9.9 判为部分 |
| LB-EVENTS-003 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：ensure_argv_safe 只对 `.cmd`/`.bat` 生效，P4 没有构造批处理形式的 pi 命令 |
| LB-EVENTS-004 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：context_evidence 没有用例（test_legacy_events.py 模块说明列为未覆盖）。P4-L02 只把 preflight/context-files.json 当作时机标记，不断言其内容 |
| LB-EVENTS-005 | — | P4-E09、E12 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-006 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture。线索：P4-E01 断言预检只调用 help、version、list-models、auth 四次及其参数，P4-E04、E05 断言 list-models.txt、auth-check.json 的内容（测试未标注本行） |
| LB-EVENTS-007 | — | P4-E01–E05、E08–E12 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-008 | — | P4-E01–E05 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-009 | 9.10.2：覆盖 | P4-E18、E19、E23、E24 | manifest＋内联 | 内联：9.9 判为已覆盖 |
| LB-EVENTS-010 | 9.10.2：覆盖（限 stub 产生的类型） | — | 仅 manifest |  |
| LB-EVENTS-011 | 9.10.2：覆盖 | P4-E06、E18、E19、E24–E26 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-012 | 9.10.2：覆盖 | P4-E26 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-013 | 9.10.2：覆盖 | P4-E15、E16、E28 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-014 | 9.10.2：覆盖 | P4-E27 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-015 | — | P4-E22、E33 | 仅内联 | 内联：9.9 判为已覆盖 |
| LB-EVENTS-016 | 9.10.2：覆盖 | P4-E17、E29 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-017 | 9.10.2：覆盖 | P4-E17、E29、E31 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-018 | 9.10.2：部分 | P4-E18、E21、E30 | manifest＋内联 | 内联：9.9 判为已覆盖 |
| LB-EVENTS-019 | 9.10.2：覆盖 | P4-E18、E21、E30、E31 | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-020 | — | P4-E17、E21 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-021 | — | P4-G03、E16、E18、E20 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-022 | 9.10.2：仅通过路径 | — | 仅 manifest |  |
| LB-EVENTS-023 | 9.10.2：仅通过路径 | — | 仅 manifest |  |
| LB-EVENTS-024 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture。线索：P4-E18 断言 report-status 为 missing（测试未标注本行） |
| LB-EVENTS-025 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture |
| LB-EVENTS-026 | — | P4-E32 | 仅内联 | 内联：9.9 判为部分 |
| LB-EVENTS-027 | — | P4-E13、E14 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EVENTS-028 | 9.10.2：部分 | — | 仅 manifest |  |
| LB-EVENTS-029 | — | P4-C38、C39 | 仅内联 | 内联：9.9 判为已覆盖 |
| LB-EVENTS-030 | 9.10.2：部分 | P4-E18 | manifest＋内联 | 内联：9.9 判为部分 |
| LB-GATES-001 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture。线索：P4-G09 断言七门按 G0…G6 排列，P4-G21 断言未知 --class 被 argparse 拒为 2，P4-C30 断言 DispatchError 缺省码为 3（测试未标注本行） |
| LB-GATES-002 | — | — | **NOT_COVERED** | （b）不适用（9.9）：名称只见于 gates.md，运行测试不能证明文档说法；仍为 source_reported |
| LB-GATES-003 | — | P4-G15 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-004 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture。线索：P4-G15 断言 worktree 的 .git 损坏时“无法重新快照”（测试未标注本行） |
| LB-GATES-005 | — | P4-G17 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-006 | — | P4-G17、G18 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-007 | — | P4-C72 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-008 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture。线索：P4-L23、L24 断言恢复时 *.partial 改名（测试未标注本行） |
| LB-GATES-009 | — | P4-C74 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-010 | — | P4-G15 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-011 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture |
| LB-GATES-012 | — | P4-G18 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-013 | — | P4-G14 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-014 | — | P4-G11、G13 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-015 | — | P4-C64 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-016 | — | P4-G18 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-017 | — | P4-C26、C73 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-018 | — | P4-G08、C25–C27、C72、C74 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-019 | — | P4-C28、C75 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-020 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture |
| LB-GATES-021 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：review_hints 没有用例（P4 未编写） |
| LB-GATES-022 | — | P4-G09 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-023 | — | P4-G01、G09 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-024 | — | P4-G01 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-025 | — | P4-G02–G05、G07 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-026 | — | P4-G08 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-027 | — | P4-G08、G10–G12、G14 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-028 | — | P4-G10、G11、G13、G14 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-029 | — | P4-G09、G23 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-030 | — | P4-G09、G13、G15–G17 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-031 | — | P4-G20、G21、C58、C59 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-032 | — | P4-G21、G22、C59 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-033 | — | P4-G20、G22–G24 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-034 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture。线索：P4-C60 断言“最新结论为 None”时 branch 退出 3，P4-C61 断言 mark INTEGRATED 缺结论时退出 3（测试未标注本行） |
| LB-GATES-035 | — | P4-G19、C60 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-036 | — | P4-C61 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-037 | — | P4-G16、C62、C63 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-GATES-038 | — | P4-G22、G23、C61 | 仅内联 | 内联：9.9 判为部分 |
| LB-LIFE-001 | — | P4-L25、L26 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-002 | — | P4-L25、L26 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-003 | — | P4-L17、L25 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-004 | — | P4-L25 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-005 | — | P4-L06、L18、L20 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-006 | — | P4-L19–L21 | 仅内联 | 内联：9.9 判为已覆盖 |
| LB-LIFE-007 | — | P4-L06、L07 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-008 | NOT_COVERED → 部分（9.10.5：`negative-legacy-contract-json-cost-budget-nan`、`negative-legacy-contract-json-cost-budget-infinity`） | P4-C02、C08、C53 | manifest＋内联 | 内联：9.9 判为部分 |
| LB-LIFE-009 | — | P4-L08–L10、L16 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-010 | — | P4-L06–L08、L10、L11 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-011 | — | P4-G06、L05、L08–L16 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-012 | — | P4-L06、L07 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-013 | — | P4-L18、C56 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-014 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：领取后、启动前失败时转为 INFRA_FAILURE（:3316-3332）：需要在这个窗口注入失败，P4 未构造 |
| LB-LIFE-015 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture。线索：P4-L01 断言 run.json 的 kill_method=job-object、spawn_error=null（测试未标注本行） |
| LB-LIFE-016 | — | P4-G05、L05、C67 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-017 | — | P4-G07、L01、L03、C69（其中 P4-L03 是 POSIX 分支，本机 NOT_RUN，不计） | 仅内联 | 内联：9.9 判为已覆盖 |
| LB-LIFE-018 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture。线索：P4-L01、L05 断言孙进程被回收（测试未标注本行） |
| LB-LIFE-019 | — | P4-G04、G24、L01、C66、C68 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-020 | — | P4-G04、G05、L01、L03、L05（其中 P4-L03 是 POSIX 分支，本机 NOT_RUN，不计） | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-021 | — | P4-L22 | 仅内联 | 内联：9.9 判为部分 |
| LB-LIFE-022 | — | P4-L09、L22、L23、C57 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-023 | — | P4-L22–L24、C68 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-024 | — | P4-L22、C57 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-025 | — | P4-C61 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-026 | — | P4-C58 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-027 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture。线索：P4-C34、C35 断言 UNKNOWN 伪状态与未知状态值原样显示（测试未标注本行） |
| LB-LIFE-028 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture。线索：P4-L01 断言 history 从 PREPARING→PREPARED 开始，P4-C70 断言 setup 被中断时为 PREPARE_FAILED（测试未标注本行） |
| LB-LIFE-029 | — | P4-C34、C42 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-030 | — | P4-C62 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-LIFE-031 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture |
| LB-LIFE-032 | — | — | **NOT_COVERED** | （b）不适用（9.9）：技能文档中的状态表是文档说法，运行测试不能证明；源码实际允许的转换已由所列方法实测 |
| LB-LIFE-033 | — | P4-C33、C45 | 仅内联 | 内联：9.9 判为部分 |
| LB-LIFE-034 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：prepare 读计划目录中的合同、run 读 attempt 内的副本，两者限额不同，没有用例（P4-L25 只测编号跨版本连续） |
| LB-LIFE-035 | — | P4-L02、L04、C70、C71（其中 P4-L04 是 POSIX 分支，本机 NOT_RUN，不计） | 仅内联 | 内联：9.9 判为部分 |
| LB-LIFE-036 | — | P4-L17、C55、C56 | 仅内联 | 内联：9.9 判为已覆盖 |
| LB-LIFE-037 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：预检证据被覆盖，没有断言 |
| LB-LIFE-038 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：claim 为普通文件时 exists 与 is_dir 的判断不一致，没有构造 |
| LB-LIFE-039 | — | P4-L08 | 仅内联 | 内联：9.9 判为部分 |
| LB-LIFE-040 | — | P4-G10、G23 | 仅内联 | 内联：9.9 判为部分 |
| LB-EXIT-001 | — | P4-C30 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-002 | NOT_COVERED → 部分（9.10.5：`negative-legacy-contract-json-deep-nesting`、`negative-legacy-contract-md-invalid-utf8`） | P4-L04、C29–C31、C46、C49、C71（其中 P4-L04 是 POSIX 分支，本机 NOT_RUN，不计） | manifest＋内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-003 | — | P4-C47、C48 | 仅内联 | 内联：9.9 判为部分 |
| LB-EXIT-004 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：dispatch-pi.sh 的解释器选择与退出码透传，只有旧自测的 POSIX 用例（本机 0 个 check）；P4 没有 wrapper 用例 |
| LB-EXIT-005 | — | P4-L17、C33、C50 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-006 | 9.10.3：部分（合同全组的临时仓库 CLI `validate`）；9.10.5 新增 `negative-legacy-contract-json-deep-nesting`、`negative-legacy-contract-md-invalid-utf8`（退出 1） | — | 仅 manifest |  |
| LB-EXIT-007 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture |
| LB-EXIT-008 | — | P4-C53–C55、C70 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-009 | — | P4-L05、C56、C66、C67 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-010 | — | P4-L22、L23、C57 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-011 | — | P4-G18 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-012 | — | P4-C64 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-013 | — | P4-G18 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-014 | — | P4-G21、C58、C59 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-015 | — | P4-G19、C60 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-016 | — | P4-C61 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-017 | — | P4-C62、C63 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-018 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture |
| LB-EXIT-019 | — | P4-C39 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-020 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture |
| LB-EXIT-021 | — | P4-C65 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-022 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture |
| LB-EXIT-023 | — | P4-C32、C33 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-024 | — | P4-C34、C35、C37、C38、C40、C42、C43 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-025 | — | P4-C38、C39 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-026 | — | P4-C41、C44 | 仅内联 | 内联：测试 docstring 标注本行（第 12 节“LB 条目”列），未逐分支核对，按部分计 |
| LB-EXIT-027 | — | — | **NOT_COVERED** | （b）不适用（9.9）：文档与技能中的退出码声明是文档说法；PowerShell 外层把 3 显示成 1 属于宿主行为（11.3 第 10 条） |
| LB-EXIT-028 | — | — | **NOT_COVERED** | （c）仅旧自测：只有 tests/test_dispatch.py 的 check（bl-01t1 measured）；第 12 节没有方法标注本行，也没有 manifest fixture。线索：P4-C41、C44、G04 断言了同码异义中的几种情形（测试未标注本行） |
| LB-EXIT-029 | — | P4-C50–C52（其中 P4-C52 是 POSIX 分支，本机 NOT_RUN，不计） | 仅内联 | 内联：9.9 判为已覆盖 |
| LB-EXIT-030 | — | P4-C36 | 仅内联 | 内联：9.9 判为已覆盖 |
| LB-EXIT-031 | — | P4-G07、L01–L03、C69（其中 P4-L03 是 POSIX 分支，本机 NOT_RUN，不计） | 仅内联 | 内联：9.9 判为部分 |
| LB-EXIT-032 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：spawn 失败（spawn_error → INFRA_FAILURE，run 退出 1）没有用例。P4-C66 的 INFRA_FAILURE 来自“没有 assistant 回复” |
| LB-EXIT-033 | 9.10.3：部分（合同全组的临时仓库 CLI `validate`）；9.10.5 新增 `negative-legacy-contract-json-deep-nesting`、`negative-legacy-contract-md-invalid-utf8` | P4-C32–C45、C53–C65 | manifest＋内联 | 内联：9.9 判为部分 |
| LB-EXIT-034 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：status 的 EXIT 列没有断言（P4-C39 只断言 events_ok 列） |
| LB-EXIT-035 | — | P4-G20、G21、C55、C59–C61 | 仅内联 | 内联：9.9 判为部分 |
| LB-EXIT-036 | — | P4-G10、G12 | 仅内联 | 内联：9.9 判为已覆盖 |
| LB-EXIT-037 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：P4 有意在 Pi 存活时保留 PID 句柄，使 pid_alive 的结果确定（test_legacy_lifecycle.py 模块说明）；tasklist 失败需要替换系统命令，未构造 |
| LB-EXIT-038 | — | P4-C45 | 仅内联 | 内联：9.9 判为已覆盖 |
| LB-EXIT-039 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：derive-json 在校验之前就写 JSON，没有用例 |
| LB-EXIT-040 | NOT_COVERED → 部分（9.10.5：`negative-legacy-contract-json-deep-nesting`、`negative-legacy-contract-md-invalid-utf8`，返回 1） | P4-C49 | manifest＋内联 | 内联：9.9 判为部分 |
| LB-TEST-H01 | — | — | **NOT_COVERED** | （b）不适用（9.9）：这是旧自测的夹具，P4 不改变它。最终取证 `bl-01final-test-dispatch-20260925` 再次使用这些夹具，256 个 check 全部 PASS，但仍没有 check 直接断言夹具的行为 |
| LB-TEST-H02 | — | — | **NOT_COVERED** | （b）不适用（9.9）：最终取证再次观察到分段、PASS 行、汇总行 `256 checks, 0 failed` 与退出 0，与规则一致，但没有 check 断言 |
| LB-TEST-S01 | 9.10.3：部分（事件全组中的 10 条 `legacy-stub-events-*`） | — | 仅 manifest |  |
| LB-TEST-S02 | — | — | **NOT_COVERED** | （d）旧自测本身：stub 的非运行命令没有做成 fixture（9.10.2 的 LB-EVENTS-028）；P4 的预检用例用 legacy_harness 的假 pi，不经过 stub 的这些命令 |
| LB-TEST-001 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-002 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-003 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-004 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-005 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-006 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-007 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-008 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-009 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：登记的 “PDEATHSIG stops pi” 只在 Linux 分支产生，本机不产生；P4 没有 Linux 用例 |
| LB-TEST-010 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-011 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-012 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-013 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-014 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-015 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-016 | — | — | **NOT_COVERED** | （a）9.9 判为未覆盖：只在 POSIX 上运行；P4 没有 wrapper 用例 |
| LB-TEST-017 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-018 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-019 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-020 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-021 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-022 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-023 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-024 | — | — | **NOT_COVERED** | （d）旧自测本身：本行描述 tests/test_dispatch.py 的测试函数（9.10.3），不是被测行为；函数内各 check 涉及的行为登记在对应 LB 行 |
| LB-TEST-COV-01 | — | P4-C02–C07 | 仅内联 | 内联：第 12 节“C.4 项”列归入“旧合同默认值”的方法；本行描述旧回归对这一 C.4 项的覆盖，剩余缺口见第 10 节“P4 更新：仍未覆盖”列，按部分计 |
| LB-TEST-COV-02 | — | P4-C08–C24、C53 | 仅内联 | 内联：第 12 节“C.4 项”列归入“Markdown/JSON 一致性”的方法；本行描述旧回归对这一 C.4 项的覆盖，剩余缺口见第 10 节“P4 更新：仍未覆盖”列，按部分计 |
| LB-TEST-COV-03 | — | P4-G08、C25–C28、C72–C75 | 仅内联 | 内联：第 12 节“C.4 项”列归入“范围检查”的方法；本行描述旧回归对这一 C.4 项的覆盖，剩余缺口见第 10 节“P4 更新：仍未覆盖”列，按部分计 |
| LB-TEST-COV-04 | — | P4-G01–G05、G07–G13、G15、G16、G20–G24、C58、C59、E20 | 仅内联 | 内联：第 12 节“C.4 项”列归入“G0–G6”的方法；本行描述旧回归对这一 C.4 项的覆盖，剩余缺口见第 10 节“P4 更新：仍未覆盖”列，按部分计 |
| LB-TEST-COV-05 | — | P4-G09、G13–G15、C62、C63 | 仅内联 | 内联：第 12 节“C.4 项”列归入“候选树漂移”的方法；本行描述旧回归对这一 C.4 项的覆盖，剩余缺口见第 10 节“P4 更新：仍未覆盖”列，按部分计 |
| LB-TEST-COV-06 | — | P4-G16–G19、C60、C63 | 仅内联 | 内联：第 12 节“C.4 项”列归入“补丁往返/完整性”的方法；本行描述旧回归对这一 C.4 项的覆盖，剩余缺口见第 10 节“P4 更新：仍未覆盖”列，按部分计 |
| LB-TEST-COV-07 | — | P4-G06、L06–L21、C56 | 仅内联 | 内联：第 12 节“C.4 项”列归入“锁与预算竞争”的方法；本行描述旧回归对这一 C.4 项的覆盖，剩余缺口见第 10 节“P4 更新：仍未覆盖”列，按部分计 |
| LB-TEST-COV-08 | — | P4-G05、L05、L15、C67、C68 | 仅内联 | 内联：第 12 节“C.4 项”列归入“超时”的方法；本行描述旧回归对这一 C.4 项的覆盖，剩余缺口见第 10 节“P4 更新：仍未覆盖”列，按部分计 |
| LB-TEST-COV-09 | — | P4-G07、L01–L04、L22、C29、C68–C71（其中 P4-L03、P4-L04 是 POSIX 分支，本机 NOT_RUN，不计） | 仅内联 | 内联：第 12 节“C.4 项”列归入“取消”的方法；本行描述旧回归对这一 C.4 项的覆盖，剩余缺口见第 10 节“P4 更新：仍未覆盖”列，按部分计 |
| LB-TEST-COV-10 | — | P4-L22–L24、C57 | 仅内联 | 内联：第 12 节“C.4 项”列归入“进程恢复”的方法；本行描述旧回归对这一 C.4 项的覆盖，剩余缺口见第 10 节“P4 更新：仍未覆盖”列，按部分计 |
| LB-TEST-COV-11 | — | P4-L17、C55、E01–E16、E22、E27、E28、E33 | 仅内联 | 内联：第 12 节“C.4 项”列归入“实际模型与思考级别证据”的方法；本行描述旧回归对这一 C.4 项的覆盖，剩余缺口见第 10 节“P4 更新：仍未覆盖”列，按部分计 |
| LB-TEST-COV-12 | — | P4-C29–C62、C64–C67、C71（其中 P4-C52 是 POSIX 分支，本机 NOT_RUN，不计） | 仅内联 | 内联：第 12 节“C.4 项”列归入“wait/退出码语义”的方法；本行描述旧回归对这一 C.4 项的覆盖，剩余缺口见第 10 节“P4 更新：仍未覆盖”列，按部分计 |

#### 9.10.7 收尾轮更新：文档 6.6 七类的状态（裁决 R-P12，2026-09-26）

文档 6.6 要求选样覆盖超时、取消、恢复、候选漂移等旧场景，兼容比较至少包括候选/补丁判断、门禁结果与旧入口状态解释；其中“差分”一步要把同一 fixture 同时喂给旧路径与新兼容路径。按裁决 R-P12，下面七类在 01 中的状态统一为：

**旧路径已锁定（内联 fixture + 特征化断言），差分 NOT_RUN（新路径不存在，归 07、10）。**

- **旧路径已锁定**：a4fa199 在这些内联输入上的现状由第 12 节的方法断言，收尾取证 measured / PASS，只限 Windows（12.10）。
- **差分 NOT_RUN**：这七类的新兼容路径归 07、10，目前还不存在，所以没有执行差分。这是“未执行”，不是失败，也不是缺样本。新路径出现后，由 07、10 用同一内联输入做差分。
- **方法归属**：按第 12 节“C.4 项 / 01-A07 类别”列（取自测试 docstring），一个方法可以属于多类。各方法的完整写法见 12.10。

| 文档 6.6 类别 | 第 12 节 C.4 项 | 代码内联 fixture（P4 编号） | 代表写法 | 主要 LB 行（按所列方法的标注） | 状态 |
|---|---|---|---|---|---|
| 超时 | 超时 | P4-G05、L05、L15、C67、C68 | `inline:tests/test_legacy_lifecycle.py::TimeoutTests.test_LB_LIFE_016_timeout_run_exits_1_and_pass_refused_by_g1@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | LB-LIFE-011、016、019、020；LB-EXIT-009；LB-GATES-025 | 旧路径已锁定（Windows），差分 NOT_RUN（新路径不存在，归 07、10） |
| 取消 | 取消 | P4-G07、L01、L02、L22、C29、C68–C71；POSIX 的 P4-L03、L04 本机跳过 | `inline:tests/test_legacy_lifecycle.py::CancelTests.test_LB_LIFE_017_ctrl_break_during_pi_run_is_cancelled_exit_1_not_130@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | LB-LIFE-017、035；LB-EXIT-002、031；LB-GATES-025 | 同上，只限 Windows 的 CTRL_BREAK；POSIX 上 SIGINT 的旧路径没有锁定（NOT_RUN） |
| 恢复 | 进程恢复 | P4-L22–L24、C57 | `inline:tests/test_legacy_lifecycle.py::RecoverTests.test_LB_LIFE_023_recover_from_collecting_reuses_run_json_and_can_pass@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | LB-LIFE-022–024；LB-EXIT-010 | 同上 |
| 候选漂移 | 候选树漂移 | P4-G09、G13–G15、C62、C63 | `inline:tests/test_legacy_gates.py::CandidateDrift.test_lb_gates_013_check_refuses_modified_candidate_and_aborted_record_blocks@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | LB-GATES-010、013、014、030、037 | 同上 |
| 候选/补丁判断 | 补丁往返/完整性 | P4-G16–G19、C60、C63 | `inline:tests/test_legacy_gates.py::PatchIntegrity.test_lb_gates_006_g6_patch_missing_tampered_sha_and_roundtrip@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | LB-GATES-005、006、012、030、035、037 | 同上；“往返失败”是改写记录字段构造的，不是真实的 `apply --cached` 失败（12.9） |
| 门禁结果 | G0–G6 | P4-G01–G05、G07–G13、G15、G16、G20–G24、C58、C59、E20 | `inline:tests/test_legacy_gates.py::G0InputConsistency.test_lb_gates_024_g0_hash_base_and_contract_failures@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | LB-GATES-023–033 | 同上；P4-G06、G14、G17–G19 也断言了门禁结果，但 C.4 项列把它们归入其他类 |
| 旧入口状态解释 | wait/退出码语义 | P4-C29–C51、C53–C62、C64–C67、C71；POSIX 的 P4-C52 本机跳过 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_024_wait_terminal_prints_summary_line@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | LB-EXIT-023–026、030 与 LB-LIFE-029（wait）；LB-EXIT-008–010、012、014–017、021（各子命令的拒绝码） | 同上 |

- 本表不含文档 6.6 的“缺字段”一类：它不在 R-P12 的七类中，仍按缺样本登记（compatibility-matrix.md 第 8 节第 9 条）。
- 本表取代 9.10.3、9.10.4 与 12.9 末条中“迁移比较时这些行为按 NOT_COVERED 处理”的说法；那些原文保留，并已加注记。

## 10. 文档 C.4 必需旧回归覆盖表

C.4 要求保留的旧回归共 12 项。下表每项对应一条 LB-TEST-COV 条目；“本次结果”按 0.2 的规则从 stdout 核对。

| C.4 项 | 条目 | 覆盖的测试函数与 check | 本次结果（Windows） | 覆盖性质 | 缺口（旧测试没有覆盖的部分） | P4 更新：已由第 12 节关闭（Windows measured / PASS） | P4 更新：仍未覆盖（原因） |
|---|---|---|---|---|---|---|---|
| 旧合同默认值 | LB-TEST-COV-01 | `test_units` “control chars / decode errors are invalid_path violations”<br>`test_setup_wrapper_doctor` “setup command runs in prepare” | 2/2 PASS（measured；所列 check 只间接用到缺省值） | **缺口**：没有直接断言，只间接用到缺省值 | normalize_contract 的全部缺省值（scripts/pi_dispatch.py:1189-1213：thinking=high、7 个默认工具、context_files=project、scope 各列表为空、dependency_changes=forbidden、authorization=[local_edit, local_test]/[]、budget 2/1200/2400/null、setup/checks/DoD 为 []、checks 的 cwd="."/required=true/expected_exit_code=0）都没有断言；需要在 01-A02 中补样本 | normalize_contract({}) 的全部节级缺省值；checks 项的 cwd/required/expected_exit_code；setup 不补 required；显式 null 保留；类型不对的节整节不补；深拷贝；结构异常的包装；provider/model 没有缺省（P4-C02–C07，白盒） | 读取时的缺省（expect_on_base="any"、输出模式 []、env {}、required 按 True）只断言了“不写回”，没有断言消费点（:1171、1174、1183、1533、1562）读到的值；缺省值经 CLI（validate/prepare/run）端到端生效没有单独用例。原因：P4 用进程内调用锁定 normalize_contract 的输出，未编写端到端样本 |
| Markdown/JSON 一致性 | LB-TEST-COV-02 | `test_validate` “argv change detected”、“budget change detected”、“integration change detected”、“forbidden path change detected”、“thinking change detected”、“missing md section rejected”、“placeholder rejected”<br>`test_feedback_v11` “derive-json writes a contract that validates”、“derived checks keep argv, cwd, timeout and patterns”、“derived scope and DoD”<br>`test_feedback_v12` “annotated single values are derived without the note”、“machine summary explains a base-failing probe”<br>`test_happy` “instruction has machine summary from JSON”<br>`test_v22_netperf_feedback` “validate warns about a Repository-facts file missing from the base” | 14/14 PASS（measured） | 直接覆盖 | 只测了“改 JSON、Markdown 不变”方向；JSON 中 scope 各列表、DoD、checks 其余字段的不一致；改 Markdown 而 JSON 不变；拒绝顺序；多个缺陷同时存在 | 改 Markdown、JSON 不变的 8 类：Budget、risk_level、thinking、integration_actions、dependency_changes、检查 argv、检查行缺失、forbidden 路径缺失（P4-C08–C15）；比较范围之外的方向（P4-C16）；全角冒号 3 例、括号说明的去除、risk_level 大小写 3 例、标题捕获（P4-C17–C24）；prepare 与 baseline 遇到不一致时的退出码和 stderr（P4-C53、C64） | JSON 中 allowed_modified/new/deleted 列表与 Markdown 的不一致、DoD 编号不一致、checks 的 cwd/timeout 等其余字段；多个独立缺陷同时存在时的错误顺序（只有 risk_level 级联一例）。原因：P4 未编写这些用例 |
| 范围检查 | LB-TEST-COV-03 | `test_scope` “README out_of_scope”、“package.json forbidden + dependency”、“.env reported as new ignored path”<br>`test_units` “control chars / decode errors are invalid_path violations”<br>`test_repo_config_features` “repo-level protected path is a violation”<br>`test_validate` “protected path in scope rejected”、“parent traversal rejected”<br>`test_commit_outside_main` “HEAD moved is a violation”<br>`test_feedback_v11` “prepare warns about an overlapping pending attempt”<br>`test_feedback_v12` “overlap warning names the latest pending attempt only” | 10/10 PASS（measured） | 直接覆盖 | 删除越界（allowed_deleted_files）；文件模式变化；大小写不同的受保护路径；真实的非 UTF-8 文件名（只注入了 path_decode_error）；symlink、submodule、sensitive_file、dependency_manifest_changed、local_commit 下的 head_moved | 删除越界（P4-C25、C72）；大小写不同的受保护路径（P4-C26、C73）；新增或改为符号链接，以及符号链接改回普通文件不报（P4-C27、C74）；local_commit 下 head_moved 降为警告（P4-C28、C75） | 普通文件的模式变化 mode_changed（如 100644→100755）、submodule、sensitive_file、dependency_manifest_changed、真实的非 UTF-8 文件名。原因：P4 未编写这些用例（test_legacy_cli.py 的覆盖范围只列删除越界、大小写、符号链接、local_commit） |
| G0–G6 | LB-TEST-COV-04 | `test_events_and_thinking` “PASS refused on G1”、“ACCEPTED_WITH_EXCEPTION with waiver”<br>`test_feedback_v12` “PASS is refused when the run ended on a textual tool call”、“verdict prints the G3 note about undeclared ambiguity”<br>`test_scope` “PASS refused on scope violation (G2)”<br>`test_candidate_drift_and_artifacts` “PASS refused when checks created files (G4)”<br>`test_v22_netperf_feedback` “verdict PASS survives a later autocrlf change (snapshot pinned to the recorded value)”、“line_endings_only recognises CRLF-only drift”<br>`test_happy` “PASS accepted” | 9/9 PASS（measured） | 部分覆盖 | G0 全部失败路径（:4161、4163）；G1 的缺少 run.json、超时、取消、非 0 退出码经 verdict 触发（:4168-4174）；G3 失败断言（:4204、4232、4236）；G4 的无有效检查记录、非当前候选、未覆盖必要检查、修改候选文件、必要检查失败（:4205-4227）；G5 无测试；G6 失败（:4244、4248、4253、4255）；G2 的缺少 scope.json（:4188-4190）与 G2 备注未经 verdict 断言；verdict 拒绝分支（见第 2 节末） | G0 全部失败路径（P4-G01）；G1 的缺 run.json、缺事件摘要、超时、取消、非 0 退出码经 verdict（P4-G02、G04、G05、G07、L01、L05、L22、E20）；G2 的缺 scope.json 与主工作区变化备注（P4-G08、G09）；G3 失败（:4204、4232、4236；P4-G08、G10–G12、G14、G18）；G4 的全部失败原因（P4-G10、G11、G13、G14）；G5 恒通过与固定备注（P4-G09、G23）；G6 失败（:4244、4248、4253、4255）与新增文件备注（P4-G09、G13、G15–G17）；verdict 全部拒绝分支（P4-G20–G23、C58、C59） | G2 的“执行器访问了工作副本外路径”备注（:4199）未经 verdict 断言（P4 未编写）；G1 取消的 POSIX 路径（P4-L03 本机跳过，NOT_RUN）；Linux、macOS 全部 NOT_RUN |
| 候选树漂移 | LB-TEST-COV-05 | `test_candidate_drift_and_artifacts` “in-place check refuses unexpected extra file”、“fresh check ignores worktree extras”、“python cache files are allowed artifacts”<br>`test_cleanup_protects_unsaved_work` “cleanup refuses when candidate files were modified”、“cleanup --force removes and logs discarded content”<br>`test_mutate` “mutate leaves the executor worktree and candidate untouched”<br>`test_v22_netperf_feedback` “verdict PASS survives a later autocrlf change (snapshot pinned to the recorded value)” | 7/7 PASS（measured） | check 与 cleanup 层直接覆盖，verdict 层缺失 | check 前修改候选文件（drift_before.modified）；verdict 时 G6 的漂移失败（在 test_cleanup_protects_unsaved_work 中触发但未断言）；G6 中新增文件只作备注；只差行尾的专门消息 | check 前修改候选文件（P4-G14）；verdict 时 G6 的漂移失败（P4-G13、G15）；G6 中新增文件只作备注（P4-G09）；只差行尾的专门消息（P4-G15）；cleanup 对补丁被改的 LOSS（P4-C63） | 本项列出的缺口都已由 P4 覆盖（Windows）。“只差行尾 + 新增文件被报成修改”已实测，但属于 11.2 第 6 条待裁决事项；Linux、macOS NOT_RUN |
| 补丁往返/完整性 | LB-TEST-COV-06 | `test_happy` “candidate roundtrip verified”、“fresh check passes in clean copy and removes it”、“branch tree == candidate tree”、“branch parent == base”<br>`test_v21_codex_trial_feedback` “branch refuses before rebuilding the tree or creating anything when the identity is missing”、“branch rebuilds the tree and uses the per-run trailer instead of the configured one”<br>`test_v22_netperf_feedback` “branch rebuilds the tree with the recorded autocrlf” | 7/7 PASS（measured） | **只有正向用例** | candidate.patch 缺失、被篡改、sha256 不符、往返失败时 `--fresh`/mutate 的拒绝与 G6 失败；“branch rebuilds the tree with the recorded autocrlf” 没有删除树对象，未走按补丁重建的分支（:4348）；重建时不校验 patch_sha256 | G6 对补丁缺失、字节被改、patch_sha256 不符、往返标记为 false 的失败（P4-G17）；worktree 已移除时 G6 仍查补丁（P4-G16）；--fresh 与 mutate 对补丁被改的拒绝（P4-G18）；branch 按补丁重建（:4348）、重建结果不一致时退出 3、重建时不校验 patch_sha256、树与补丁都缺失时回溯（P4-G19）；cleanup 的 LOSS（P4-C63） | --fresh 与 mutate 对补丁缺失、sha256 不符、往返标记为 false 三种情形的拒绝：P4 只测了“字节被改”一例，三者经同一个 candidate_patch_ok（:3474-3477），但没有端到端断言；真实的往返失败（record_candidate 中 `apply --cached` 失败）：P4 改写 candidate.json 的记录字段来模拟。原因：P4 只取代表性样本，没有构造真实的 apply 失败 |
| 锁与预算竞争 | LB-TEST-COV-07 | `test_budget_race` “exactly one attempt claims the last budget slot”<br>`test_preflight_and_budget` “budget: 3rd attempt refused”、“model not listed -> preflight fail, stays PREPARED”<br>`test_happy` “claim records reserved timeout” | 4/4 PASS（measured） | 部分覆盖 | TaskLock 等待 30 s 后“任务锁被占用”；300 s 过期接管与归属缺失；max_wall_seconds_total 耗尽（prepare 与 run 两种文本）；`--timeout` 被预算截短；allowed_executors 未命中；预算竞争落败方的状态与退出码 | TaskLock 等待 30 s 后“任务锁被占用”（P4-L18、L20）；300 s 过期接管（P4-L19、L20）与归属缺失（P4-L21）；max_wall_seconds_total 耗尽时 prepare 与 run 的两种文本（P4-L10）；剩余不足 60 s 与边界（P4-L11–L13）；--timeout 被单次上限与剩余总预算截短、0 不生效、负数得 1 s（P4-G06、L14–L16）；allowed_executors 未命中（P4-L17、C55）；预算竞争落败方（P4-L06、L07）；按实际 wall_seconds 或按预留计入（P4-L08、L09） | 真实并发下的过期接管竞态（P4-L21 是按顺序构造的白盒）；不同文件系统的 mtime 语义与时钟偏差；owner.json 写入时的 FileExistsError（:2595-2599）；同一 attempt 并发 run 时 claim 冲突报“该 attempt 已被领取”（P4-C56 只测了入口处的已领取拒绝）；预算限额来源不同（LB-LIFE-034）。原因：P4 未编写，真实竞态需要多进程时序控制 |
| 超时 | LB-TEST-COV-08 | `test_timeout` “timeout -> TIMEOUT state”、“timeout enforced quickly (\<40s)”、“grandchild process killed (job-object)”<br>`test_units` “on_spawn failure terminates the child (Codex #2)”<br>`test_v2_planner_adapters` “wait times out on a running attempt with exit code 3” | 5/5 PASS（measured） | 直接覆盖 | 检查命令与 setup 的超时；超时后 run 退出 1、verdict 的 G1“运行超时” | 超时后 run 退出 1、verdict 的 G1“运行超时”、AWE 豁免（P4-G05、L05、C67）；负数 --timeout 得 1 s 后超时（P4-L15）；timed_out 与 interrupted 同为真时判 TIMEOUT（P4-C68） | 检查命令与 setup 的超时。原因：P4 未编写 |
| 取消 | LB-TEST-COV-09 | `test_dispatcher_killed` “recover after dispatcher death” | 1/1 PASS（measured；该 check 不覆盖信号取消分支） | **缺口**：没有信号用例 | 信号经 `_Interrupted` 进入 run_supervised 的中断分支（:576、703-706）；G1“运行被取消或调度器中断”（:4172）；main 的 KeyboardInterrupt 与 130（:4969-4971）；各阶段 Ctrl+C 的状态。唯一相关 check 同时接受 CANCELLED 与 INFRA_FAILURE | Windows：CTRL_BREAK 经 _Interrupted 进入 run_supervised 的中断分支，结果 CANCELLED、run 退出 1（P4-G07、L01、C69）；G1“运行被取消或调度器中断”（P4-G07、L01、L22）；main 的 KeyboardInterrupt→130（P4-C29，白盒）；各阶段：领取前 CTRL_BREAK 直接结束于 0xC000013A（P4-L02），prepare 的 setup 中为 PREPARE_FAILED、退出 1（P4-C70），wait 轮询中 0xC000013A 且没有输出（P4-C71）；恢复结果锁定为 CANCELLED（P4-L22） | POSIX 的 SIGINT 两个方法（P4-L03、L04，本机跳过，NOT_RUN）；经子进程到达 main 的 130（Windows 上 CTRL_BREAK 不经过该分支，SIGINT 用例只在 POSIX）；:3319-3332 窗口（先标 INFRA_FAILURE）与 collect 期间的中断；_terminate_tree 期间再收到信号；SIGTERM、SIGHUP。原因：平台限制，以及 P4 未编写 |
| 进程恢复 | LB-TEST-COV-10 | `test_dispatcher_killed` “Job Object reaps pi and grandchild”、“PDEATHSIG stops pi”（本机未产生）、“mark ABANDONED on RUNNING requires --force”、“recover after dispatcher death”<br>`test_stuck_states` “claimed PREPARED attempt cannot run again”、“claimed-but-not-started attempt recovers as INFRA_FAILURE”、“PREPARING can be abandoned with --force” | 6/7 PASS；“PDEATHSIG stops pi”仅 Linux 分支，本机不产生（source_inspected / NOT_RUN） | 直接覆盖，但断言宽松 | “PDEATHSIG stops pi” 只在 Linux 运行，本机没有产生（本条因此记 NOT_RUN）；pid 仍存活时拒绝恢复（:3424-3425）；COLLECTING 状态的恢复；run.json 已存在时的恢复；`.partial` 重命名（:3436-3439）；非可恢复状态或缺 `--recover` 时的 2（:3418-3420）；macOS 等平台的调度器被强杀场景没有断言 | Windows：pid 存活时拒绝恢复（P4-L22、C57）；COLLECTING 状态的恢复、沿用已有 run.json、*.partial 改名（P4-L23）；二次恢复时 *.partial 已存在导致回溯（P4-L24）；非可恢复状态或缺 --recover 时退出 2（P4-L23、C57）；`taskkill /F` 之后 Job Object 回收 Pi（P4-L22） | “PDEATHSIG stops pi”（Linux 分支，本机不产生）；macOS；pid_alive 在 tasklist 失败时放行（LB-EXIT-037）与 PID 复用误判（11.4 第 6 条）。原因：P4 有意在 Pi 存活时保留 PID 句柄，使结果确定，因此不覆盖这两种情况 |
| 实际模型与思考级别证据 | LB-TEST-COV-11 | `test_happy` “thinking not reported -> evidence says so, no problem”<br>`test_events_and_thinking` “events case model {}”、“events case ok {'STUB_PTL': 'low'}”<br>`test_preflight_and_budget` “model not listed -> preflight fail, stays PREPARED”、“env/contract model conflict refused”、“pinned thinking mismatch refused”<br>`test_validate` “invalid thinking rejected”<br>`test_setup_wrapper_doctor` “doctor ok with stub”<br>`test_v21_codex_trial_feedback` “model table parsing ignores pi's no-model messages”<br>`test_repo_config_features` “branch commit carries executor and trailers” | 10/10 PASS（measured） | 直接覆盖，预检分支有缺口 | 预检的思考级别不在列表、未知工具、版本不可读、低于 0.80.4（:2032、2037、2043、2045）；不支持的参数；doctor 的思考级别检查（:4726）；allowed_executors 未命中；stderr 警告（:261-266、2363-2365）；回报级别与要求一致的正例；responseModel 与要求不同；provider/model 字段缺失 | 预检的思考级别不在列表、未知工具、版本不可读、低于 0.80.4、缺必需参数、help 非 0、list-models 失败、auth 未就绪（P4-E01–E06、E08、E10–E12）；doctor 的思考级别检查（P4-E13、E14）；allowed_executors 未命中（P4-L17）；stderr 警告（P4-E22、E33）；部分回报与一致的正例（P4-E27）；responseModel 不同（P4-E15）；provider/model 字段缺失（P4-E16、E28） | 预检第 1 步取 stderr、第 7 步取 stdout 的优先顺序（假 pi 的 --help 与 auth 不写 stderr）；help 中没有 `pi auth` 时的 note；预检 run_capture 超时与找不到程序；smoke 的思考级别检查（按固定列表）。原因：test_legacy_events.py 的模块说明列为未覆盖 |
| wait/退出码语义 | LB-TEST-COV-12 | `test_v2_planner_adapters` “wait returns at once for a finished attempt”、“wait times out on a running attempt with exit code 3”、“wait reports an attempt that never started”、“sync-adapters --check reports missing copies”<br>`test_v2_review_fixes` “wait does not report an unreadable state as finished”<br>`test_candidate_drift_and_artifacts` “in-place check refuses unexpected extra file”、“check creating unexpected file -> exit 1”<br>`test_events_and_thinking` “error stopReason -> exit 1 but NEEDS_REVIEW”<br>`test_output_paths` “metrics --out README.md refused, README untouched”<br>`test_mutate` “invalid mutation spec is rejected with every problem listed” | 10/10 PASS（measured） | 直接覆盖 | wait `--timeout`<1 的 2（:3926-3927）；state.json 缺失（UNKNOWN）只测了损坏；PREPARING/COLLECTING 到时；60 s 宽限；main 的 130、argparse 的 2、未捕获异常的 1；多数拒绝只断言“非 0”，未锁定缺省码 3；dispatch-pi.sh 的无 Python→2 与退出码透传只在 POSIX 测试（本机 0 个 check） | --timeout<1 时退出 2（P4-C32）；state.json 缺失、为 null、无 state 键、未知值、非对象（P4-C34–C36）；PREPARING/COLLECTING 到时退出 3（P4-C37）；live 片段与“摘要：”行（P4-C38–C40）；timeout<60 时 PREPARED 退出 3，宽限内继续轮询（P4-C42、C43）；main 的无子命令 2、argparse 2、未捕获异常 1（P4-C46、C47、C49）与 130（P4-C29，白盒）；prepare、run、collect、verdict、branch、mark、cleanup、baseline、doctor 的精确退出码（P4-C53–C66）；run 在 TIMEOUT、CANCELLED、INFRA_FAILURE 时退出 1（P4-C66、C67、C69） | PREPARED 宽限的 60 s 上限本身（要等满 60 s，P4-C43 说明未测）；dispatch-pi.sh 的无 Python→2 与退出码透传（只有 POSIX 用例，P4 未覆盖）；smoke 的拒绝码；--help/-h 的 0；status 的 EXIT 列（LB-EXIT-034）。原因：P4 未编写，或受平台限制 |

**C.4 缺口汇总**（旧测试不能提供可比较的旧观测，迁移时需要新建样本或记为 NOT_COVERED）：旧合同默认值；取消；补丁完整性负例；G0 与 G3、G5、G6 的失败路径（G1、G2、G4 只部分覆盖）；锁等待与过期接管、墙钟预算耗尽；进程恢复的 Linux 分支（本机不产生）与 pid 存活拒绝；预检的思考级别/工具/版本分支与 stderr 警告；wait 的 `--timeout`<1、state.json 缺失与 main 的 130/argparse 2。

**P4 更新后的 C.4 缺口汇总**（第 12 节，只限 Windows）：

- 原汇总中已由 P4 关闭（measured / PASS）的：
  - 旧合同默认值（白盒）；
  - 取消的 Windows 路径；
  - 补丁完整性负例：G6 层的四种情形、--fresh/mutate 的“字节被改”一例、branch 按补丁重建；
  - G0 与 G3、G5、G6 的失败路径，以及 G1、G2、G4 的其余原因；
  - 锁等待与过期接管、墙钟预算耗尽；
  - pid 存活时拒绝恢复；
  - 预检的思考级别、工具、版本分支与 stderr 警告；
  - wait 的 `--timeout`<1、state.json 缺失、argparse 的 2，以及 main 的 130（白盒）。
- 仍未覆盖：
  - 进程恢复的 Linux 分支（本机不产生）；
  - 取消的 POSIX 路径（P4-L03、L04 本机跳过），以及经子进程到达 main 的 130；
  - 检查命令与 setup 的超时；
  - 范围检查中的 submodule、mode_changed、sensitive_file、dependency_manifest_changed、非 UTF-8 文件名；
  - Markdown/JSON 一致性中 scope 各列表、DoD 编号与 checks 其余字段的不一致；
  - --fresh/mutate 对补丁缺失、sha256 不符、往返标记为 false 的拒绝，以及真实的往返失败；
  - 三条门禁备注未经 verdict 断言；
  - wait 宽限的 60 s 上限本身；
  - dispatch-pi.sh 的 wrapper 行为（POSIX）；
  - Linux、macOS 全部 NOT_RUN。

## 11. 未解决事项汇总

本节合并第 3–8 节各自的“未解决事项”“未决事项”并去重，按性质分组；括号中是来源小节。已由本次取证关闭的事项单列在 11.1。

### 11.1 已由本次取证关闭的事项

| 原事项 | 关闭依据 |
|---|---|
| 各区域“没有运行 `tests/test_dispatch.py`，测试标识 NOT_RUN，平台与结果未取得”（3.11、5.10、6.9、8 节开头） | `bl-01t1-legacy-20260925`：256 checks / 0 failed，退出 0，前后采样一致（0.1）。只限 Windows；Linux、macOS 仍为 NOT_RUN |
| 运行时 check 总数（按源码推算 252–256）未经运行核实；本机能建哪类链接只能从 check 名判断（8.3、第 8 节未解决事项） | 实际 256 个（0.3）。`test_v2_review_fixes` 产生 16 个 check，没有任何 “… unavailable here …” 替代 check：目录链接（`_dir_link` 先试符号链接、再试 junction，输出不能区分用了哪一种）、junction 与文件符号链接分支都真实执行，不存在空通过 |
| kit 工作区前提只经只读核对，没有运行 adapter_drift（8.1、第 8 节未解决事项） | `test_v2_planner_adapters` “kit adapters are in sync with .agents/skills”“kit has no CLAUDE.md and no legacy rules”“kit AGENTS.md fits Codex project_doc_max_bytes” 本次 PASS |
| `test_v21` 的 Git 身份隔离（GIT_CONFIG_GLOBAL 置空加 GIT_CONFIG_NOSYSTEM=1）在 Git for Windows 上是否生效（第 8 节未解决事项） | “doctor notes a missing git identity early”“branch refuses before rebuilding the tree or creating anything when the identity is missing” 本次 PASS，本机上隔离生效 |
| 基线输入清单须记录未跟踪的 `scripts/codekit/`（8 节开头、8.5 第 5 条） | 取证输入清单 92 项中含 `scripts/codekit/__init__.py`、`scripts/codekit/baseline.py`（source=untracked，按工作区字节计算 sha256） |
| 汇总为 `0 checks` 时也退出 0、汇总之后的清理异常会退出 1，基线判读须同时看汇总行和退出码（8.5 第 1、2 条） | 本次汇总行为 `256 checks, 0 failed`，退出 0，stderr 为空，不属于这两种情况。判读规则本身仍应由基线工具固化 |

### 11.2 需要设计决定：旧行为保留还是修正

按 01-D09，历史输入只读保留并按旧规则解释，新入口按严格规则拒绝，差异登记在 `compatibility-matrix.md`。下列事项仍需逐项确定归属与处理方式。

1. **合同校验的宽松行为**（3.12、第 3 节未解决事项）：(1) ID 正则用 `^…$` 加 `re.match`，接受末尾换行，而 glob 已改用 fullmatch；(2) schema_version、plan_version 接受 true 与 1.0，expected_exit_code 接受 bool；(3) 受保护路径检查只看模式的字面值，`**/*.md` 这类通配允许项能通过 validate，运行时才被 evaluate_scope 判为 protected_path；(4) Scope 路径只做 JSON 到 Markdown 单向、全文子串匹配；(5) 允许与禁止的重叠检查区分大小写，忽略含 `*` 的模式，含 `?` 的模式按字面比较；(6) 标题捕获在第一个不属于 `[a-z0-9-]` 的字符处停止；(7) JSON 接受重复键、NaN 与 Infinity（cost_budget.amount 为 Infinity 时通过）；(8) Identity 与 dependency_changes 只认半角冒号。
2. **Markdown/JSON 冲突不设优先级**（3.5、第 3 节未解决事项）：一律报 error 拒绝；不在比较范围的字段（checks 的 cwd、timeout、输出模式，DoD 的 text 与 evidence 等）只按 JSON 执行。v2 是否沿用，需要规划端确认。
3. **未捕获异常与退出码 1**（3.8、4.8、5.11、6.11、7.9）：以下路径以 Traceback 退出 1，与 EXIT_FAIL 无法区分。
   - 已由起草或核对者复现：Markdown 不是 UTF-8（:1668）；JSON 深度嵌套 RecursionError（:1670）；输出模式正则 OverflowError（:1180）；missing_fact_path_warnings 的 TypeError（:1708、:1718）；derive-json 中 plan_version 为 Unicode 数字（:1369）；summarize_events 遇到非数值的真值 totalTokens（:2092）、非字符串的 text（:2101）、含 NUL 的工具路径（:2277）；state.json 为非对象 JSON（:2555）；Windows 上 `--repo` 指向不存在的路径（NotADirectoryError）。
   - 只来自源码推断：summarize_events 异常后 run 停在 COLLECTING、wait 一直返回 3、recover 同样失败；load_attempt 读 meta.json 或 contract.json 失败；verdict 的复审报告不是 UTF-8（:4270）；branch 树对象与 candidate.patch 都缺失（:4349 → :824）；verdicts/ 中出现非数字文件名的 .json（:4323）；Windows 上二次 `collect --recover` 时 `*.partial` 已存在（:3436-3439）；`_terminate_tree` 期间再收到信号，`_Interrupted` 未被捕获，状态停在 RUNNING 且没有 run.json（:703-706）；prepare 在写 meta.json 之前失败，再按 task-id 定位后 load_attempt 失败（:3194-3221、2643-2649）；collect 中非 DispatchError/OSError 的异常让状态停在 COLLECTING（:3356-3394）。
   - 需要规划端判断哪些算应复现的旧行为、哪些算缺陷。
4. **门禁名称**（5.1、第 5 节未解决事项）：名称只见于 `.agents/skills/review-pi/gates.md:7-13`，源码只有编号。新架构是否采用这些名称，需要决定。
5. **G0 的范围**（5.6、第 5 节未解决事项）：meta.json 不做哈希校验；contract.json 哈希不一致时 G3/G4 仍按被改动的合同判定；contract.json 缺失或损坏时 load_attempt 先抛出未捕获异常，G0 来不及报告（推断）。需要裁定是否校验 meta.json、G0 失败时是否继续使用该合同。
6. **G6 的边界**（5.3、5.11、第 5 节未解决事项）：worktree 目录不存在时跳过漂移比较（:4238），意图未知；line_endings_only 比较整棵树（:858-861），另有新增文件时只差 CRLF 的修改会被报成“候选文件在记录后被修改”（只在临时仓库用同一条 git 命令核实，未经 pi_dispatch 端到端验证）；verdict 的 G6 重新快照会向仓库写 Git 对象（:4240）。
7. **检查记录与临时副本**（5.11、第 5 节未解决事项）：`check --fresh` 补丁不完整时（:3987-3988）或原地检查时 worktree 已不存在（:3999-4000），会留下没有 checks.json 的空 `checks/NN`，它成为“最近一次”后 G3/G4 报“没有有效的独立检查记录”，即使更早的检查有效；prepare_fresh_workspace 失败时 check（:3989-3995）与 mutate（:3616-3621）都不移除已登记的临时 worktree；cleanup 只移除 workspace_kept 的副本（:4475-4480），不清理 mutate、baseline 用 `--keep-workspace` 保留的副本。
8. **行尾配置固定不完整**（5.2、第 5 节未解决事项）：main_repo_fingerprint 的 git add 不固定 core.autocrlf（:893）；line_ending_args 对 yes、1、on 这类非规范值返回 []，不固定（:780-790）。运行期间配置变化是否造成误报，没有验证。
9. **范围判定的空档**（5.4、5.5、第 5 节未解决事项）：符号链接改回普通文件（old 120000 → new 100644）既不算违规也不算警告（:2468-2477，已在内存中核实）；main_repo_changes 有 diff_error 时 G2 没有备注，只在 summary 的“复审需要关注”中提示（:4194-4196、:2945-2947）。
10. **TaskLock 没有归属校验**（6.2、6.11、第 6 节未解决事项）：过期接管后，原持有者 `__exit__` 无条件 rmtree，会删掉新持有者的锁（:2604-2606、2612-2613，顺序模拟探针复现，没有正式测试或真实并发取证）；锁只看目录 mtime，owner.json 只写不读，不同文件系统上的 mtime 语义与时钟偏差未验证；写 owner.json 时出现 FileExistsError 会被当作“锁已存在”继续等待，最终失败并留下锁目录（:2595-2599，推断）。
11. **预算语义**（6.3、6.11、第 6 节未解决事项；由 07 决定）：cost_budget 只校验、不参与核算与拦截（:1576-1580）；计次跨 plan_version、限额按各自合同版本（:3182、3272、2653-2656）；prepare（used ≥ total）与 run（剩余 < 60 s）门槛不同（:3187、3305）；实际 wall_seconds 包含 grace 与回收等待，可能超过预留与 max_wall_seconds_total（:678、696、715、720，推导）；prepare 不取锁、只数已领取的 attempt，可以准备出超额的 PREPARED。
12. **状态转换语义**（6.7、6.10、第 6 节未解决事项）：mark INTEGRATED 只看最新结论，不检查当前状态，例如已 ABANDONED 的 attempt 仍可标为 INTEGRATED（:4399-4404，没有测试）；ABANDONED 对非活动状态不受限；已有结论的 attempt 可以再次 verdict；gates.md 的状态表缺 SUPERSEDED，是否更新文档由 12 决定。
13. **恢复语义**（6.5、6.8、第 6 节未解决事项）：合成 run.json 的 timed_out 固定为 False，Pi 实际超时后被恢复也不会得到 TIMEOUT（:3430）；沿用已有 run.json 时 G1 可能通过，与 SKILL.md:90“恢复证据不能直接作为 PASS 依据”不完全一致；按 task-id 定位总是取编号最大的 attempt，`collect --recover <task-id>` 可能指向错误的 attempt（:2643-2649，推导）；删除最高编号目录后按 max+1 会复用该编号（:2621，推导，流程规则禁止删除 runs 证据）。
14. **attempt 编号下界**（6.10、第 6 节未解决事项）：旧实现首个编号为 1、下界为 1，0 只可能来自手工建立的目录；设计文档 4.1.1 称新封装的 attempt 允许非负整数。是否把 0 视为非法历史值，由 01-D03 与 07 决定。
15. **退出码重叠与语义**（7.6、7.9、4.5、第 4、7 节未解决事项）：wait 的 3 与 DispatchError 缺省码 3 重叠（例如 Repo.discover 找不到 git 时也是 3），只看退出码重复调用可能一直循环；未捕获异常与 EXIT_FAIL 共用 1；Pi 运行期间的中断最终退出 1 而不是 130；Pi 非零退出但事件完整且 ok 时，collect 状态为 NEEDS_REVIEW、run 退出 0，只有 G1 记录退出码（:3348-3349、3395-3404、4173-4174，源码推断，没有测试或端到端探针）。源码没有说明这些重叠是否有意。
16. **用量与费用的零值语义**（4.7、4.15、第 4 节未解决事项）：旧实现没有 usage_complete，也没有 token 未知标记，token 缺失一律为 0，与文档 4.3.7“null 表示未知”冲突；费用未知时为 null，没有币种；旧实现只有 complete 与 ok 两个维度，没有文档 4.3.4 的 protocol_complete、usage_complete、process_exited 独立维度；cost.total 为 inf 或 token 为 NaN 时 events-summary.json 写出非标准 JSON。比较投影要保留 cost.status、unpriced_messages 与 problems，并说明 token 的 0 可能代表未知。
17. **脱敏设计**（4.12、第 4 节未解决事项）：纯文本脱敏会遮蔽 `totalTokens=…`、`max_tokens: …` 这类计数；redact_obj 不按键名遮蔽普通字符串值，也不遍历 tuple；events-summary 中的 shell_commands、路径记录与歧义摘录，以及 executor-report.md/json 不脱敏。源码没有说明这些是否有意。

### 11.3 需要真实 Pi 或宿主环境才能核实

1. 真实 Pi 0.87 的 assistant `message.usage` 是单次请求的增量还是累计值；旧实现按增量相加（:2081-2093），源码和 stub 都不能证明是哪一种（4.15）。
2. 真实 Pi 是否对同一次调用同时发出 message_end 的 usage 与 entry_appended{type:usage}；toolResult、compaction_end 的 usage 是否与 assistant 重叠。旧实现全部相加，重复累加已由探针复现；stub 不发这些事件，也没有测试（4.7、4.15）。
3. `message.provider/model` 是 Pi 按配置填写的，还是来自提供商响应；responseModel 只记录、不比较（:2325），网关替换模型也不会被判为不符（4.6、4.15）。
4. “agent_settled 自 0.80.4 起提供”只有源码注释这一来源（:50）；expects_settled 为 False 或 None 的分支没有测试，None 可以从 smoke、recover（缺 run-started.json 且缺 pi-version.txt）或旧 run.json 进入（4.1、4.5）。
5. 预检的 auth check 不带 `--no-refresh`（:2058），doctor 带（:4719）；预检会不会刷新或改写凭据，未核实（4.11、4.15）。
6. 真实 Pi 输出的 JSONL 是否是紧凑格式；`_live_progress` 依赖紧凑标记 `"type":"tool_execution_end"`（:4543），stub 用带空格的 json.dumps，端到端 live 计数为 0（4.10、7.5）。
7. agent_settled 之后到来的非工作事件会静默替换最终消息并累加用量、complete 不变（探针）；真实 Pi 是否会发出这类事件，未核实（4.5）。
8. 真实 Pi 是否可能产生导致 summarize_events 抛异常的输入（11.2 第 3 条）（4.8）。
9. `tests/stub_pi_help.txt` 与真实 pi 0.87 的帮助是否一致，无法核实（8.2）。
10. AGENTS.md:55 与 SKILL.md:44 说 PowerShell 外层可能把 wait 的 3 显示成 1，这是宿主行为，无法从源码或测试核实（7.7）。
11. SIGTERM、SIGHUP 在 run_supervised 之外到达时，或调度器被 `taskkill /F` 等方式强杀时，退出码由 Python 或操作系统决定，源码没有处理（7.9）。

### 11.4 本机以外的平台与环境

1. Linux、macOS 全部 NOT_RUN（01-D10）。已知差异点：调度器被强杀后，Linux 只有 PDEATHSIG 让 Pi 收到 SIGTERM，普通孙进程可能残留；macOS 没有父进程死亡通知（tests/test_dispatch.py:465-470）；“PDEATHSIG stops pi” 在本机不产生（6.5、6.11）。
2. POSIX 上 `--repo` 指向不存在的路径时，推断会被误报为“未找到 git，请先安装 Git。”并退出 3；本机 Windows 实测为 NotADirectoryError、退出 1（7.9）。
3. derive-json 写出 CRLF、plan_key_from_arg 的 normcase、planner_paths 在 IS_WINDOWS 时忽略大小写，都只在 Windows 上观察，Linux、macOS 可能不同（3.12、第 3 节未解决事项）。
4. `test_wrapper_interpreters_and_literal_arguments` 在 Windows 上直接 return（tests/test_dispatch.py:658-659），dispatch-pi.sh 的“无 Python→2”、解释器回退与非零退出码透传在 Windows 上没有测试；本机只由起草者实测过透传 2 和 0（7.8、8.3）。
5. 本次运行账户能创建 junction 与文件符号链接，目录链接分支也都执行；无特权账户下的链接分支（以及 3.7 的“合同不能是符号链接”分支）未验证（第 3 节未解决事项、8.5）。
6. pid_alive 的风险均未验证：Windows 上 PID 复用会被误判为存活；tasklist 失败或超时返回 None，collect 与 `mark --force` 会当作可以继续；POSIX 上 os.kill 的非常规异常直接上抛（:726-740）（6.11）。

### 11.5 旧测试没有覆盖的行为（回归缺口）

详见第 10 节。按主题汇总：

1. **门禁与 verdict**：G0 全部失败路径；G1 的缺少 run.json、超时、取消、非 0 退出码；G2 的缺少 scope.json 与 G2 备注（未经 verdict 断言）；G3 失败断言（scope 证据失败在 test_scope 中实际发生但未断言）；G4 除“产生候选外新文件”以外的原因；G5；G6 的只差行尾、记录后修改（在 test_cleanup_protects_unsaved_work 中触发但未断言）、补丁被篡改、往返失败、无法重新快照；verdict 的 PASS 带 `--waive`、AWE 缺豁免或 `--decided-by`、无门禁失败时 AWE 仍需 `--waive`、REVISE/BLOCKED/ESCALATE 缺 `--class`、非 REVIEWABLE 状态下被拒、重复记录（5.10、5.11、6.9）。
   - **P4 更新**：已关闭（Windows measured / PASS）：G0 全部失败路径（P4-G01）；G1 的缺少 run.json、超时、取消、非 0 退出码（P4-G02、G04、G05、G07、L01、L05、L22、E20）；G2 的缺少 scope.json 与主工作区变化备注（P4-G08、G09）；G3 失败断言（P4-G08、G10–G12、G14、G18）；G4 的其余五种原因（P4-G10、G11、G13、G14、G18）；G5（P4-G09、G23）；G6 的只差行尾、记录后修改、补丁被篡改、往返失败、无法重新快照（P4-G13、G15–G17）；verdict 的全部拒绝分支、非 REVIEWABLE 状态被拒、重复记录（P4-G20–G23、C58、C59）。仍未覆盖：G2 的“执行器访问了工作副本外路径”备注未经 verdict 断言（P4 未编写）；取消的 POSIX 路径（P4-L03，本机跳过）。
2. **补丁完整性**：candidate.patch 缺失、被篡改、sha256 不符、往返失败都没有负向用例；“branch rebuilds the tree with the recorded autocrlf”（tests/test_dispatch.py:1837）没有删除树对象，走不到 :4348 的重建分支；重建时不校验 patch_sha256（5.11、8.4）。
   - **P4 更新**：已关闭：G6 对缺失、篡改、sha256 不符、往返标记为 false 的失败（P4-G17）；--fresh 与 mutate 的拒绝（“字节被改”一例，P4-G18）；:4348 的按补丁重建、重建结果不一致时退出 3、重建时不校验 patch_sha256、树与补丁都缺失时回溯（P4-G19）；cleanup 的 LOSS（P4-C63）。仍未覆盖：--fresh/mutate 对补丁缺失、sha256 不符、往返标记为 false 的端到端拒绝（只测了“字节被改”一例）；真实的往返失败（P4 改写记录字段来模拟）。
3. **取消**：没有信号用例；`_Interrupted` 分支、G1“运行被取消”、main 的 130、各阶段 Ctrl+C 的状态都没有测试；test_dispatcher_killed 的恢复断言同时接受 CANCELLED 与 INFRA_FAILURE（6.9、8.4）。
   - **P4 更新**：已关闭（Windows）：CTRL_BREAK 经 _Interrupted 分支，结果 CANCELLED、run 退出 1（P4-G07、L01、C69）；G1“运行被取消”（P4-G07、L01、L22）；main 的 130（P4-C29，白盒）；领取前、prepare 的 setup 中、wait 轮询中三个阶段（P4-L02、C70、C71）；恢复结果锁定为 CANCELLED（P4-L22）。仍未覆盖：POSIX 的 SIGINT 两个方法本机跳过（P4-L03、L04，NOT_RUN）；经子进程到达 main 的 130（Windows 上 CTRL_BREAK 不经过该分支）；:3319-3332 窗口与 collect 期间的中断、_terminate_tree 期间再收到信号（P4 未构造）。
4. **锁、预算与生命周期**：锁等待 30 s 超时、过期接管；同一 attempt 并发 run 的“已被领取”；剩余墙钟不足 60 s 与 max_wall_seconds_total 耗尽；`--timeout` 被预算截短；allowed_executors 未命中；领取后、启动前异常；Job 创建或加入失败；run.json 已存在时的恢复；pid 存活时拒绝恢复；COLLECTING 状态恢复；`.partial` 重命名；状态为 UNKNOWN 时 wait 的 1；预算竞争落败方的状态与退出码；并发 prepare 撞名重试与跨 plan_version 的编号连续（6.9、6.11、8.4）。
   - **P4 更新**：已关闭：锁等待 30 s 超时、过期接管（P4-L18–L21）；剩余墙钟不足 60 s 与 max_wall_seconds_total 耗尽（P4-L10–L13）；--timeout 被预算截短（P4-G06、L14–L16）；allowed_executors 未命中（P4-L17）；run.json 已存在时的恢复、pid 存活时拒绝恢复、COLLECTING 状态恢复、.partial 重命名（P4-L22–L24、C57）；状态为 UNKNOWN 时 wait 的 1（P4-C34、C35）；预算竞争落败方的状态与退出码（P4-L06、L07）；跨 plan_version 的编号连续（P4-L25）。仍未覆盖：同一 attempt 并发 run 时 claim 冲突的“已被领取”（P4-C56 只测了入口处的已领取拒绝）；领取后、启动前的异常（LB-LIFE-014）；Job 创建或加入失败；并发 prepare 撞名重试。原因：需要在进程内部的窗口注入失败，或需要多进程时序控制，P4 未构造。
5. **合同**：normalize_contract 的缺省值没有直接断言；schema_version、task_id、plan_version、base_sha、risk_level 五项取值，local_edit 必选，context_files，scope 的“至少允许”与“允许和禁止重叠”，dependency_changes 取值，命令项中除 expect_on_base 以外的检查，DoD 的 id、text 与未定义证据，budget 的取值范围与 cost_budget，JSON 占位符，缺少文件、JSON 解析失败、符号链接、顶层不是对象、“合同结构无效”，基线中缺少 AGENTS.md 的警告，derive-json 的解析问题，全部未捕获异常，都没有测试断言（3.11）。
   - **P4 更新**：已关闭：normalize_contract 的缺省值（P4-C02–C07，白盒）；risk_level 的大小写取值（P4-C21、C22）；“合同结构无效”（P4-C06，白盒）；未捕获异常中的“Markdown 不是 UTF-8”（P4-C49）。仍未覆盖：其余取值检查（schema_version、task_id、plan_version、base_sha、local_edit 必选、context_files、scope 的“至少允许”与“允许和禁止重叠”、dependency_changes、命令项、DoD、budget 的范围与 cost_budget）；JSON 占位符；文件层错误；AGENTS.md 缺失的警告；derive-json 的解析问题；其余未捕获异常。原因：这些属于合同拒绝原因（01-A02、01-A04），不在 C.4 的 12 项中，P4 未编写。P3 fixture 中的旧投影见 compatibility-matrix.md 4.1，本节不据此关闭。
6. **事件与预检**：预检的缺参数、思考级别不支持、未知工具、版本不可读或偏低、list-models 失败分支（只有探针复现）；doctor 的思考级别检查；stderr 警告；responseModel 不同；provider 或 model 字段缺失；部分回报思考级别；重复的 message_end；空流、不可解析行、截断；settled 之后的事件；entry_appended、compaction_end、toolResult 的用量与 auto_retry；partial 费用；Pi 非零退出但事件完整；context_evidence（4.14、8.4）。
   - **P4 更新**：已关闭：预检的缺参数、思考级别不支持、未知工具、版本不可读或偏低、list-models 失败、help 非 0、auth 未就绪（P4-E01–E06、E08–E12）；doctor 的思考级别检查（P4-E13、E14）；stderr 警告（P4-E22、E33）；responseModel 不同与字段缺失（P4-E15、E16、E28）；部分回报思考级别（P4-E27）；重复的 message_end（P4-E17）；空流、不可解析行、截断（P4-E18、E19、E23、E24）；settled 之后的事件（P4-E26）；entry_appended、compaction_end、toolResult 的用量（P4-E29）；partial 费用（P4-E30、E31）；Pi 非零退出但事件完整（P4-E20、G04）。仍未覆盖：auto_retry 记录；context_evidence；entry_appended 与 message_end 重复计同一次调用的端到端形态；Infinity/NaN 的写出；预检取 stderr/stdout 的优先顺序；run_capture 超时。这些都被 test_legacy_events.py 的模块说明列为未覆盖。
7. **启动入口**：stub 不覆盖真实启动入口：`shutil.which("pi")`、Windows 下 npm `.cmd` 包装解析、ensure_argv_safe、PI_DISPATCH_PI_CMD 非 JSON 或非法 JSON 都没有测试（4.14、8.2）。
   - **P4 更新**：部分：PI_DISPATCH_PI_CMD 为 `[]` 时退出 2（P4-C56）。仍未覆盖：`shutil.which("pi")`、`.cmd` 包装解析、ensure_argv_safe、非 JSON 值按单个路径接受。原因：01-L05 要求受控环境必须设置 PI_DISPATCH_PI_CMD，legacy_harness 在未设置时拒绝运行，而 which 分支会去查找真实的 pi；`.cmd` 与 ensure_argv_safe 需要批处理形式的 pi 命令，P4 未构造。
8. **范围**：symlink、submodule、mode_changed、sensitive_file、dependency_manifest_changed、local_commit 下 head_moved 降为警告；删除越界；大小写不同的受保护路径；真实的非 UTF-8 文件名；review_hints（:2497-2512）（5.11、8.4）。
   - **P4 更新**：已关闭：symlink（新增、改为符号链接、改回普通文件不报，P4-C27、C74）；local_commit 下 head_moved 降为警告（P4-C28、C75）；删除越界（P4-C25、C72）；大小写不同的受保护路径（P4-C26、C73）。仍未覆盖：submodule、普通文件的 mode_changed、sensitive_file、dependency_manifest_changed、真实的非 UTF-8 文件名、review_hints（P4 未编写）。
9. **wait 与入口**：wait 的 `--timeout`<1 返回 2、PREPARING/COLLECTING 到时返回 3、timeout ≥ 60 时 PREPARED 的 60 s 宽限、非对象 state.json、state.json 缺失（UNKNOWN）、到时输出中的 live 片段、已结束时的“摘要：”行；main 的无子命令 2、argparse 2、130、未捕获异常 1；run 在 TIMEOUT、CANCELLED、INFRA_FAILURE 时退出 1（test_timeout 只检查状态）；许多拒绝路径只断言 code != 0，没有锁定是 2 还是 3（涉及 prepare、run、collect、verdict、branch、mark、cleanup、baseline、smoke、doctor）（7.8、7.9）。
   - **P4 更新**：已关闭：--timeout<1 时退出 2（P4-C32）；PREPARING/COLLECTING 到时退出 3（P4-C37）；timeout<60 时 PREPARED 退出 3，宽限内继续等待（P4-C42、C43）；非对象 state.json（P4-C36）；state.json 缺失（P4-C34）；到时输出中的 live 片段（P4-C38、C39）；已结束时的“摘要：”行（P4-C40）；main 的无子命令 2、argparse 2、未捕获异常 1（P4-C46、C47、C49）与 130（P4-C29，白盒）；run 在 TIMEOUT、CANCELLED、INFRA_FAILURE 时退出 1（P4-C66、C67、C69，另有 P4-G05、L01、L05）；prepare、run、collect、verdict、branch、mark、cleanup、baseline、doctor 的精确退出码（P4-C53–C65）。仍未覆盖：PREPARED 宽限的 60 s 上限本身（要等满 60 s）；smoke 的拒绝码；--help 的 0。

### 11.6 证据与记录缺口

1. 区域章节中的“实测”“探针”都来自会话临时目录中的一次性脚本，没有归档为 fixture，不满足文档 3.2 的 input_fixture_ref；需要在 P3（01-T3）中用固定 fixture、被测提交与命令重新记录（第 3、4、6 节未解决事项）。 **完整性审查更新（2026-09-26）**：P3 的 legacy fixture 只覆盖合同与 stub 事件流，按行回填见 9.10；区域章节中其余“实测”“探针”仍没有 fixture，第 12 节的 P4 方法也没有（9.10.4）。 **收尾轮更新（2026-09-26）**：按裁决 R-P12，第 12 节的 P4 方法以代码内联 fixture 作为 input_fixture_ref（12.10）；区域章节中一次性的“实测”“探针”仍没有 fixture。
2. 3.2 的 comparison_projection_revision 尚未定义；第 9 节的 new_consumer_module 与 acceptance_ids 是规划端初判，需要各模块确认（8.6、第 8 节未解决事项）。 **完整性审查更新（2026-09-26）**：“尚未定义”已过时，P3 定义了 `codekit01-legacy-projection-v1`（`tests/codekit01_legacy.py:55`），按行回填见 9.10。仍未关闭的是：224 行中 181 行 NOT_COVERED；第 12 节 159 个 P4 方法没有 fixture 与比较投影（9.10.4）。两项都已列入 acceptance.md 第 7 节的未完成项与 3.7 节的 known_limitations。 **收尾轮更新（2026-09-26）**：按 R-P12 回填后，224 行中 NOT_COVERED 为 67 行，原因分四类（9.10.6）；159 个 P4 方法都有代码内联 fixture 与 `codekit01-characterization-v1`（12.10）。acceptance.md 第 7 节第 11、12 项的同步不在本文件的修订范围内。
3. 只来自源码推断、没有实测的退出码：validate 中 `git rev-parse HEAD` 失败时退出 3（:758-760、1684）；在 worktree 中运行 validate 时退出 2（:962-963）（第 3 节未解决事项）。
4. provider、model 缺失时 validate 能通过；run 阶段 resolve_executor 从 PI_EXEC_PROVIDER / PI_EXEC_MODEL / PI_EXEC_THINKING 补值（:2670-2685，调用点 :3271），原始 JSON 没写 thinking 时，已与 Markdown 核对为 high 的值也可能在运行时被环境变量替换；没有实测（第 3 节未解决事项）。
5. 测试夹具的已知性质（8.1、8.5、第 8 节未解决事项）：`STUB_MAIN_REPO` 不从 BASE_ENV 清除，外部已设置时会传入所有运行；测试继承宿主的全部环境变量（只删掉少数几个），test_v21 的 Git 身份隔离依赖本机 git 配置层级；导入测试模块即在系统临时目录建目录（01-L04）；`tests/stub_pi.py` 的 docstring 没有列出已实现的 tempsequence 场景；清理阶段的 `git worktree prune` 是否真的修剪过条目，只是推断；“status shows unknown cost”依赖循环顺序（最后一个仓库是 STUB_NOCOST 例）；多处状态由 `pd.set_state` 直接注入，不等于真实的崩溃或运行路径；63 条歧义语句、34 个凭据样本等合在单个 check 中，失败粒度比 check 数显示的更粗。
6. 第 9 节所依据的结构化条目（`inventory-{1..6}-*.items.json`）目前只在规划端会话 scratchpad 中；是否把它们归档到 `docs/themis-tally-v2/01-baseline/evidence/`，由规划端决定。 **收尾轮更新（2026-09-26）**：已归档到 [evidence/inventory-items/](evidence/inventory-items/)（6 个文件；清单 `manifest.json`，sha256 cebbd8bfc9861f97ce21f81478b2574aef5fdd6a8acff3df1f5ca70d9ddba8c9）。

## 12. P4 特征化回归（补第 10 节与 11.5 节的回归缺口）

> 本节是 P4 新增内容。第 0–11 节原有文字中的“本次”指 `bl-01t1-legacy-20260925`；本节的“本次”指第 0.5 节列出的最终取证。
>
> **收尾轮更新（2026-09-26）**：自收尾轮起，本节的结果引用切换到第 0.5 节末尾的收尾取证 `bl-01closure-*`（R-01 严格 pyc 口径）：各方法“本次结果”一列先写收尾取证，原最终取证写在“历史：”之后；12.2–12.6 各加收尾取证的记录。收尾取证与最终取证的逐方法结果相同（156 个 ok、3 个 skipped，跳过的方法与原因相同）。收尾取证的归档副本在 `evidence/closure/`（见 0.5 末尾）。新增 12.10：159 个方法的 input_fixture_ref 与 comparison_projection_revision（R-P12）。

### 12.1 来源、口径与判读规则

- **被测对象**：提交 a4fa199 的 `scripts/pi_dispatch.py`，工作区字节 sha256 为 a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4（与 0.1 相同）。被测字节在测试中核对了两次：
  - P4-C01 与 P4-E34 都经 `legacy_harness.legacy_facts` 核对：把 CRLF 归一为 LF 之后的摘要，等于锁定值 `LOCKED_PI_DISPATCH_SHA256`（a4fa199 的 blob 字节，LF 行尾）；
  - P4-C01 另外断言 TOOL_VERSION 为 2.2.2。
  - 本次的原始字节摘要也是 a00d6934…：test_legacy_gates.py 与 test_legacy_lifecycle.py 把它打印在输出首行，两份归档 stderr.bin 的首行都写着“与 a4fa199 一致：True”；各取证 `capture.json` 的 supervisor.module_sha256 也是这个值。 **收尾轮更新**：收尾取证中同样如此：test_legacy_gates.py 与 test_legacy_lifecycle.py 两份归档 stderr.bin（`evidence/closure/`，与原件字节相同）的首行都写着“与 a4fa199 一致：True”，10 次取证的 `capture.json` 中 supervisor.module_sha256 都是 a00d6934…。
- **测试文件**：4 个测试文件与公共夹具 `tests/legacy_harness.py` 都是 P4 新增、尚未提交的工作区文件。它们的字节以最终取证输入清单（`pre/input-manifest.json`，source=untracked）记录的 sha256 为准，见 12.2。以后文件有改动，须重新取证。 **收尾轮更新**：收尾取证的输入清单中，4 个测试文件的 sha256 与 12.2 相同；`tests/legacy_harness.py` 变为 c4e871372a35f35c59a76172ccc366a50316c5af9ad3ec4703d1fb6c27d4b974（收尾轮加入 8.4 清理前的归属核对）。收尾轮已按新字节重新取证，本节结论改以收尾取证为准，对照见 12.2 末尾。
- **隔离**：每个用例在 legacy_harness 建立的独立临时区域中运行，子进程环境按 01-L05 重设：
  - `PI_DISPATCH_PI_CMD` 指向 `tests/stub_pi.py`，或用例临时区域内的假 pi。未设置、或指向临时区域外名为 pi/claude/codex 的程序时，legacy_harness 拒绝运行；
  - `PI_CODING_AGENT_DIR` 指向用例自建的空目录；
  - 按 01-L04 逐文件运行，不用 discover。
- **性质**：这是特征化（characterization）回归，断言旧实现的**现状**，不修缺陷。
  - measured / PASS 只表示“a4fa199 在 Windows 上确实如此”，不表示这个行为正确；
  - 测试 docstring 标“可疑”的现状照录在下表，是否保留由第 11.2 节的设计决定处理。
- **结果判读**：逐方法匹配归档 `run/stderr.bin` 中 unittest（verbosity=2）的输出：（**收尾轮更新**：收尾取证的 `run/stderr.bin` 归档在 `evidence/closure/<取证 ID>/run/stderr.bin`，与原件字节相同，路径与 sha256 见 0.5 末尾与 12.2 末尾；按同一规则逐方法匹配，159 个方法的名称与结果都与最终取证相同。）
  - `... ok` 记 **measured / PASS（Windows）**；
  - `... skipped '<原因>'` 记 **NOT_RUN**，原因照录；
  - 一个方法内的 subTest 全部通过，才报 ok；
  - 记 PASS 的前提是所在取证 baseline_consistent=true、退出 0（第 0.5 节）；
  - 本节没有 FAIL、ERROR、BLOCKED 的方法。
- **条件执行**：带 `skipUnless` 条件的方法（Windows 控制台、Windows 专属、能否建符号链接），在“本次结果”列注明条件，以及本次是否执行。
- **白盒**：标“白盒”的方法在进程内加载同一份被测字节（`legacy_harness.load_legacy_module`），直接调用内部函数：normalize_contract、validate_contract、evaluate_scope、main、TaskLock、pi_preflight、_expects_settled、summarize_events。它们只证明函数层面的现状，并依赖内部签名。
- **构造的状态**：部分用例用 `set_state`，或改写证据文件（run.json、candidate.json、meta.json、checks.json、state.json、candidate.patch），构造旧实现可达的状态。这不等于真实的崩溃或运行路径，各行写明了构造方式。
- **与第 9 节的关系（01-A16 分栏）**：
  - 第 9 节的 legacy_command_or_test_id、evidence_basis / execution_status 两列只描述旧自测 `tests/test_dispatch.py`，本节不改动；
  - P4 方法对原 NOT_RUN 行的覆盖另列在 9.9 与各行备注的“P4 更新”中；
  - 旧自测与 P4 新测试互不代替；
  - test_protocols.py、test_codekit01_fixtures.py、test_baseline_tool.py 是 01 新代码测试（公共协议、fixtures、取证工具），不作为任何 LB 行的证据。（收尾轮 M-08 更正用词：原写“参考实现与取证工具的测试”。被测对象是本仓库的 01 新代码，不是附录 B 的参考代码。）
- **平台**：只限 Windows（第 0.5 节）。Linux、macOS 全部 NOT_RUN（01-D10）。本机跳过的 3 个方法都是 POSIX 分支。
- **编号**：按测试文件中的源码顺序编号，第 2、9、10、11.5 节的“P4 更新”引用这些编号：
  - P4-Gnn：test_legacy_gates.py；
  - P4-Lnn：test_legacy_lifecycle.py；
  - P4-Cnn：test_legacy_cli.py；
  - P4-Enn：test_legacy_events.py。
- **列的含义**：
  - “C.4 项 / 01-A07 类别”一列：01-A07 的六类是 G0–G6、范围、候选漂移、预算竞争、取消、补丁完整性；不属于这六类的写“六类之外”，括号中是相关的其他验收项；
  - “对应缺口”一列：指出该方法关闭了第 2、10、11.5 节中的哪一项缺口。
- **不作为证据的材料**：各阶段子代理的自述与复审记录只作线索；本节只依据测试源码、docstring 与归档的 unittest 输出。

### 12.2 汇总

| 测试文件 | 文件 sha256（最终取证输入清单） | 取证 ID | 方法数 | ok（measured / PASS） | skipped（NOT_RUN） | 归档输出（字节数，sha256） |
|---|---|---|---|---|---|---|
| `tests/test_legacy_gates.py` | d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7 | `bl-01final-test-legacy-gates-20260925` | 24 | 24 | 0 | [evidence/final/bl-01final-test-legacy-gates-20260925/run/stderr.bin](evidence/final/bl-01final-test-legacy-gates-20260925/run/stderr.bin)（6459，80d945cd781a868e666fbfb89e2c5a39edd527291d77e92f96d63ac3b4cdffe1） |
| `tests/test_legacy_lifecycle.py` | f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd | `bl-01final-test-legacy-lifecycle-20260925` | 26 | 24 | 2 | [evidence/final/bl-01final-test-legacy-lifecycle-20260925/run/stderr.bin](evidence/final/bl-01final-test-legacy-lifecycle-20260925/run/stderr.bin)（7809，45e9ec9f0b232815ebbd0c9159090c1f3d10aa95cd65e8d523ab8c2812b1a69b） |
| `tests/test_legacy_cli.py` | 1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532 | `bl-01final-test-legacy-cli-20260925` | 75 | 74 | 1 | [evidence/final/bl-01final-test-legacy-cli-20260925/run/stderr.bin](evidence/final/bl-01final-test-legacy-cli-20260925/run/stderr.bin)（19861，484493ae4f7412a21b7c473fbfcbb663d891ff5a0e3575943366e242c4440c8c） |
| `tests/test_legacy_events.py` | f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7 | `bl-01final-test-legacy-events-20260925` | 34 | 34 | 0 | [evidence/final/bl-01final-test-legacy-events-20260925/run/stderr.bin](evidence/final/bl-01final-test-legacy-events-20260925/run/stderr.bin)（8739，9dc7c9843ac13b2bf001439f7011214c8d227136113567a0bbc622c3d9be1010） |
| `tests/legacy_harness.py`（公共夹具，不含测试） | 3d133d5fcef2aaf41286d739d14133914f3fb8910b9177dc9d4f946f5963d6fb | 上面 4 次取证 | — | — | — | — |
| 合计 |  |  | **159** | **156** | **3** |  |

**收尾轮更新（2026-09-26）**：收尾取证的对照。归档副本在 `evidence/closure/<取证 ID>/`，其中 `run/stderr.bin` 与原件字节相同（0.5 末尾）。

| 测试文件 | 文件 sha256（收尾取证输入清单） | 取证 ID | 方法数 | ok（measured / PASS） | skipped（NOT_RUN） | 归档输出（字节数，sha256） |
|---|---|---|---|---|---|---|
| `tests/test_legacy_gates.py` | d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7（不变） | `bl-01closure-test-legacy-gates-20260926` | 24 | 24 | 0 | [evidence/closure/bl-01closure-test-legacy-gates-20260926/run/stderr.bin](evidence/closure/bl-01closure-test-legacy-gates-20260926/run/stderr.bin)（6459，97af8357a3730e301a70d6890bfc1d1463186590d25f4db15d7348ea938138f6） |
| `tests/test_legacy_lifecycle.py` | f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd（不变） | `bl-01closure-test-legacy-lifecycle-20260926` | 26 | 24 | 2 | [evidence/closure/bl-01closure-test-legacy-lifecycle-20260926/run/stderr.bin](evidence/closure/bl-01closure-test-legacy-lifecycle-20260926/run/stderr.bin)（7809，e79ad9f8e4e9f8330f7677f2696ae9908dc6604b2735f955c62813924a2aa99f） |
| `tests/test_legacy_cli.py` | 1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532（不变） | `bl-01closure-test-legacy-cli-20260926` | 75 | 74 | 1 | [evidence/closure/bl-01closure-test-legacy-cli-20260926/run/stderr.bin](evidence/closure/bl-01closure-test-legacy-cli-20260926/run/stderr.bin)（19861，26cce1cf6ad440b5f584180592d772bb4e720e2a54f353694f458bef6a16c3ae） |
| `tests/test_legacy_events.py` | f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7（不变） | `bl-01closure-test-legacy-events-20260926` | 34 | 34 | 0 | [evidence/closure/bl-01closure-test-legacy-events-20260926/run/stderr.bin](evidence/closure/bl-01closure-test-legacy-events-20260926/run/stderr.bin)（8739，e5cfa16608d66529963a69a7a10236c294873692b3efe19f5773b0c6bbe70166） |
| `tests/legacy_harness.py`（公共夹具，不含测试） | c4e871372a35f35c59a76172ccc366a50316c5af9ad3ec4703d1fb6c27d4b974（最终取证时为 3d133d5f…） | 上面 4 次取证 | — | — | — | — |
| 合计 |  |  | **159** | **156** | **3** |  |

- 与最终取证的归档 stderr.bin 逐行比较（本次只读核对）：四份输出只有“Ran N tests in …s”一行的耗时不同，逐方法的名称与结果（ok，或 skipped 及原因）都相同。
- 这 4 次取证与其余 6 次的共同条件见 0.5 末尾。

### 12.3 test_legacy_gates.py：G0–G6、verdict、候选漂移与补丁完整性（24 个方法）

- **取证与结果**：取证 `bl-01final-test-legacy-gates-20260925`，归档 `evidence/final/bl-01final-test-legacy-gates-20260925/run/stderr.bin`（sha256 80d945cd781a868e666fbfb89e2c5a39edd527291d77e92f96d63ac3b4cdffe1），24 个方法全部 ok。 **收尾轮更新**：收尾取证 `bl-01closure-test-legacy-gates-20260926`，归档 `evidence/closure/bl-01closure-test-legacy-gates-20260926/run/stderr.bin`（sha256 97af8357a3730e301a70d6890bfc1d1463186590d25f4db15d7348ea938138f6，与原件相同），24 个方法全部 ok；与上述最终取证的归档输出相比，只有“Ran N tests in …s”一行的耗时不同。
- **公共流程**：见 `LegacyGateCase`：make_repo → prepare → run（stub 或 legacy_harness 生成的假 pi）→ 原地 check → verdict。
- **记号**：门禁问题写成“G\<n> <原文>”，这是 verdict 输出中 `GATE G<n> …` 行的内容。

| 编号 | 测试方法 | 锁定的旧行为（“可疑”照录测试 docstring） | LB 条目 / 源码行（@a4fa199） | C.4 项 / 01-A07 类别 | 对应缺口 | 本次结果 |
|---|---|---|---|---|---|---|
| P4-G01 | `G0InputConsistency.test_lb_gates_024_g0_hash_base_and_contract_failures` | - plan.md 被改或缺失、contract.json 被改：G0“<文件> 的哈希与 prepare 时记录的不一致”，PASS 退出 1<br>- contract.json 被改并新增必要检查：G4 同时报“必要检查 V02：not_run”，仍按被改的合同判定（可疑）<br>- meta.json 的 base_sha 改为不存在的提交：G0“基线提交不可用”，G6“无法重新快照：git read-tree … 失败：”；不报 meta.json 的哈希（可疑）<br>- contract.json 缺失或不是合法 JSON：FileNotFoundError / JSONDecodeError 回溯，退出 1，状态不变（可疑）<br>- 全部恢复后 PASS 被接受 | LB-GATES-024、LB-GATES-023；:4160-4163、2659-2665、768-770、2653-2656 | C.4：G0–G6<br>A07：G0–G6 | §2 G0；§10 G0–G6“G0 全部失败路径（:4161、4163）”；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G02 | `G1ExecutionComplete.test_lb_gates_025_g1_missing_run_json_and_events_summary` | - 缺 run.json：G1“缺少 run.json”与“Pi 退出码为 None”<br>- 缺 events-summary.json：G1“缺少事件摘要” | LB-GATES-025；:4165-4176 | C.4：G0–G6<br>A07：G0–G6 | §2 G1；§10 G0–G6“G1 的缺少 run.json”；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G03 | `G1ExecutionComplete.test_lb_gates_025_g1_event_problem_nosettle` | - 事件流没有 agent_settled：run 退出 1，状态仍为 NEEDS_REVIEW；check 通过<br>- PASS 被 G1 拒绝，problem 原文为“没有 agent_settled：该 pi 版本应以它结束，事件流可能被截断或运行被中断” | LB-GATES-025、LB-EVENTS-021；:4175-4176、2344-2348、3349 | C.4：G0–G6<br>A07：G0–G6 | §2 G1（补充一种事件类失败） | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G04 | `G1ExecutionComplete.test_lb_gates_025_g1_nonzero_pi_exit_only_caught_by_gate` | - Pi 以 3 退出，但事件完整、没有 problem：collect 状态 NEEDS_REVIEW，run 退出 0<br>- 只有 G1 记“Pi 退出码为 3”（可疑，11.2 第 15 条，原为源码推断） | LB-GATES-025、LB-LIFE-019、LB-LIFE-020；:4173-4174、3349、3395-3406 | C.4：G0–G6<br>A07：G0–G6 | §2 G1；§10 G0–G6“非 0 退出码经 verdict”；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G05 | `G1ExecutionComplete.test_lb_life_016_timeout_run_exit_1_and_g1_timeout` | - `run --timeout 5`：RUNNING 行“时限 5s”，结果 TIMEOUT；run 退出 1，事件 ok=true 时也是 1<br>- run.json：timeout_seconds=5、timed_out=true<br>- TIMEOUT 状态可以 check；PASS 被 G1“运行超时”“Pi 退出码为 <非 0>”拒绝<br>- ACCEPTED_WITH_EXCEPTION 豁免 G1 并带 --decided-by 后可以记录，state_before=TIMEOUT | LB-LIFE-016、LB-LIFE-020、LB-GATES-025；:678、691-699、3346、3349、3395-3398、4169-4170 | C.4：超时、G0–G6<br>A07：G0–G6（G1） | §2 G1“超时”；§10 超时“超时后 run 退出 1、verdict 的 G1 运行超时”；§11.5 第 1、9 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G06 | `G1ExecutionComplete.test_lb_life_011_timeout_flag_cannot_exceed_budget` | `run --timeout 3600` 大于 max_wall_seconds_per_attempt=600 时，时限仍为 600。RUNNING 行、run.json、claim/reservation.json 都记 600 | LB-LIFE-011；:3307-3309、3314-3315、3333 | C.4：锁与预算竞争<br>A07：预算竞争 | §10 锁与预算竞争“--timeout 被预算截短”（按单次上限）；§11.5 第 4 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G07 | `G1ExecutionComplete.test_lb_life_017_interrupt_during_run_is_cancelled_exit_1` | - Pi 运行中向调度器进程组发 CTRL_BREAK_EVENT：CANCELLED，run 退出 1，不打印“已取消。”<br>- run.json：interrupted=true、timed_out=false；check 可以运行<br>- PASS 被 G1“运行被取消或调度器中断”“Pi 退出码为 <非 0>”拒绝 | LB-LIFE-017、LB-EXIT-031、LB-GATES-025；:571-585、703-706、3399-3400、4171-4172 | C.4：取消、G0–G6<br>A07：取消、G0–G6 | §2 G1“取消”；§10 取消“_Interrupted 分支、G1 运行被取消”；§11.5 第 3 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证；条件执行，本次已执行）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925`（条件执行：skipUnless(has_console())，本次已执行） |
| P4-G08 | `G2Scope.test_lb_gates_026_g2_violation_missing_scope_and_g3_scope_evidence` | - 越界时 G2 逐条记“out_of_scope README.md”“forbidden_path package.json”“dependency_change package.json”<br>- G3 同时报“D02 依赖的范围证据未通过”<br>- 删除 scope.json：G2“缺少 scope.json”，G3 报同一条 | LB-GATES-026、LB-GATES-027、LB-GATES-018；:4188-4193、4228-4232 | C.4：范围检查、G0–G6<br>A07：范围、G0–G6 | §2 G2“缺少 scope.json”、G3“scope 证据失败”；§10 G0–G6（:4188-4190、4232）；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G09 | `GateNotes.test_lb_gates_023_notes_never_block_pass_and_g5_constant` | - 运行中改写主工作区的 README.md、check 之后在 worktree 新增 notes.txt，PASS 仍被接受（退出 0）<br>- 记录中七门按 G0…G6 排列，全部 passed<br>- 备注逐字断言：G1 思考级别未回报、G2 主工作区变化、G4 原地检查、G5 固定备注、G6“工作副本有候选之外的新文件（不会被集成）：notes.txt”<br>- 除 G3 外，备注不打印 | LB-GATES-023、LB-GATES-022、LB-GATES-029、LB-GATES-030；:4152-4158、4194-4196、4153-4154、4249-4251、4282-4283 | C.4：G0–G6、候选树漂移<br>A07：G0–G6、候选漂移 | §2 G5、G2 备注（主工作区变化）；§10 候选树漂移“G6 中新增文件只作备注”；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G10 | `G3G4Checks.test_lb_gates_028_g4_partial_coverage_and_stale_candidate` | - 合同有 V01、V02 两个必要检查。`check --only V01` 退出 0（covers_all_required=false、all_required_passed=true）<br>- PASS 被拒：G3“D03 依赖的 V02 未通过或未运行”；G4“最近一次检查没有覆盖全部必要检查（使用了 --only？）”“必要检查 V02：not_run”<br>- 完整 check 之后，把记录的 candidate_tree 改为基线树：G4“最近一次检查不是针对当前候选” | LB-GATES-028、LB-GATES-027、LB-EXIT-036；:4208-4211、4223-4227、4233-4236、4030 | C.4：G0–G6<br>A07：G0–G6 | §2 G3、G4；§10 G0–G6“G4 非当前候选、未覆盖必要检查”；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G11 | `G3G4Checks.test_lb_gates_028_g4_required_check_failed` | - 候选实现错误：CHECK V01 failed，check 退出 1<br>- PASS 被拒：G3“D01 依赖的 V01 未通过或未运行”，G4“必要检查 V01：failed” | LB-GATES-028、LB-GATES-027、LB-GATES-014；:4223-4227、4233-4236 | C.4：G0–G6<br>A07：G0–G6 | §10 G0–G6“必要检查失败（:4227）、G3（:4236）”；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G12 | `G3G4Checks.test_lb_gates_027_g3_dod_evidence_on_optional_check` | - 非必要检查 V02 失败时，check 仍退出 0，G4 通过<br>- DoD 引用 V02：只有 G3 失败<br>- 引用 review 的 DoD 被跳过 | LB-GATES-027、LB-EXIT-036；:4228-4236、4030 | C.4：G0–G6<br>A07：G0–G6 | §2 G3“检查引用失败”；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G13 | `G3G4Checks.test_lb_gates_014_g4_check_modified_candidate` | - 检查命令改写候选文件：打印 WARN“检查修改了候选文件：src/normalize.py（结果不能作为 PASS 证据）”，仍写记录，退出 1<br>- PASS 被拒：G4“检查过程修改了候选文件：…”，G6“候选文件在记录后被修改：…” | LB-GATES-014、LB-GATES-028、LB-GATES-030；:4022-4052、4212-4213、4247-4248 | C.4：G0–G6、候选树漂移<br>A07：G0–G6、候选漂移 | §10 G0–G6“修改候选文件（:4213）”；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G14 | `CandidateDrift.test_lb_gates_013_check_refuses_modified_candidate_and_aborted_record_blocks` | - check 之前改写候选文件：写 `{"aborted":"candidate_drift"}`，退出 4；消息中的列表是 Python repr，空列表写“无”<br>- 恢复文件后 PASS 仍被 G3/G4“没有有效的独立检查记录”拒绝：aborted 记录成了最近一次 | LB-GATES-013、LB-GATES-027、LB-GATES-028；:4002-4014、4200-4205、3446-3450 | C.4：候选树漂移<br>A07：候选漂移 | §10 候选树漂移“check 前修改候选文件（drift_before.modified）”；§2 G3/G4“无有效检查记录”；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G15 | `G6Integrable.test_lb_gates_030_g6_drift_after_record` | verdict 时逐项改动 worktree：<br>- 内容被改、候选文件被删除：“候选文件在记录后被修改：<路径>”<br>- 只改行尾：专门消息“候选文件与记录只差行尾（CRLF / LF）：1 个文件……（prepare 时记录 false，现在 <当前值>）……”<br>- 只改行尾且另有新文件：报成“被修改”（可疑，11.2 第 6 条；原只用同一条 git 命令核实）<br>- worktree 的 .git 损坏：“无法重新快照：git read-tree \<base> 失败：”<br>- 运行后把 core.autocrlf 改为 true：快照仍按记录值，PASS 照常；只改行尾时消息报“现在 true” | LB-GATES-030、LB-GATES-010、LB-GATES-003；:4237-4253、858-870、773-790 | C.4：G0–G6、候选树漂移<br>A07：G0–G6、候选漂移 | §2 G6；§10 G0–G6（:4244、4248、4253）；§10 候选树漂移“verdict 层 G6 漂移失败”“只差行尾的专门消息”；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G16 | `G6Integrable.test_lb_gates_030_g6_worktree_missing_skips_drift_but_checks_patch` | - cleanup 移除 worktree 后，G6 不比较漂移，只查补丁：补丁被改时 G6 失败<br>- 恢复后 PASS 被接受，G6 没有问题也没有备注（可疑，11.2 第 6 条“worktree 不存在时跳过”） | LB-GATES-030、LB-GATES-037；:4238、4254-4255 | C.4：G0–G6、补丁往返/完整性<br>A07：G0–G6、补丁完整性 | §2 G6（跳过条件）；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G17 | `PatchIntegrity.test_lb_gates_006_g6_patch_missing_tampered_sha_and_roundtrip` | - 四种改动：candidate.patch 缺失、字节被改、candidate.json 的 patch_sha256 不符、patch_roundtrip_verified=false<br>- 四种都只报同一条 G6“候选补丁缺失、被改动或未通过往返校验”，PASS 退出 1<br>- 恢复后 PASS 被接受 | LB-GATES-006、LB-GATES-030、LB-GATES-005；:3474-3477、4254-4255 | C.4：补丁往返/完整性<br>A07：补丁完整性 | §10 补丁往返/完整性“缺失、被篡改、sha256 不符、往返失败时的 G6 失败”；§11.5 第 1、2 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G18 | `PatchIntegrity.test_lb_gates_012_fresh_check_and_mutate_refuse_bad_patch` | 补丁字节被改时：<br>- `check --fresh` 退出 3；`mutate` 在读取变异清单之前退出 3，不建 mutations/<br>- 原地 check 不查补丁，退出 0<br>- 被拒的 `check --fresh` 留下空的 checks/02；恢复补丁后 PASS 仍被 G3/G4“没有有效的独立检查记录”拒绝（可疑，11.2 第 7 条）<br>- 再做一次原地 check（checks/03）后 PASS 被接受 | LB-GATES-006、LB-GATES-012、LB-GATES-016、LB-EXIT-011、LB-EXIT-013；:3987-3988、3599-3600 | C.4：补丁往返/完整性<br>A07：补丁完整性 | §10 补丁往返/完整性“--fresh/mutate 的拒绝”（只测字节被改一例）；§11.5 第 2 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G19 | `PatchIntegrity.test_lb_gates_035_branch_patch_rebuild_paths` | PASS 之后：<br>- 树对象存在时，branch 不查补丁：补丁缺失或为空都照常建分支，分支的树等于候选树<br>- 删除松散树对象：按补丁重建，树等于候选树，父提交为基线<br>- 树对象丢失且补丁为空：退出 3“候选树对象已丢失，且补丁重建结果不一致”，不校验 patch_sha256<br>- 树对象与补丁都缺失：FileNotFoundError 回溯，退出 1（可疑，11.2 第 3 条，原为推断） | LB-GATES-035、LB-EXIT-015；:4327-4392、4348-4352、824 | C.4：补丁往返/完整性<br>A07：补丁完整性 | §10 补丁往返/完整性“未走按补丁重建的分支（:4348）”“重建时不校验 patch_sha256”；§11.5 第 2 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G20 | `VerdictRules.test_lb_gates_031_state_not_reviewable` | - PREPARED、ABANDONED（由 mark 设置）、UNKNOWN（删除 state.json）三种状态的 verdict 都退出 3<br>- 状态检查先于复审报告检查<br>- 不写 verdicts/ | LB-GATES-031、LB-GATES-033、LB-EXIT-035；:4263-4265、80 | C.4：G0–G6<br>A07：G0–G6（verdict；另见 01-A05） | §11.5 第 1 条“非 REVIEWABLE 状态下被拒” | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G21 | `VerdictRules.test_lb_gates_032_verdict_rejection_branches` | - 复审报告不存在或为空：2；Verdict 行不符：2<br>- --waive 格式错（G7、小写 g3、理由为空、缺“=”）：2；PASS 带错格式的豁免也是 2，不打印 GATE 行<br>- --waive 格式校验先于门禁求值：meta.json 缺 worktree 键时，格式正确的 PASS 以 KeyError 回溯退出 1（可疑）<br>- 未知 --class 被 argparse 拒为 2<br>- 有失败门禁时，PASS 带合法豁免仍按门禁拒绝（1）<br>- AWE 缺失败门禁的豁免：2，并列出缺哪些；缺 --decided-by：2<br>- REVISE/BLOCKED/ESCALATE 缺 --class：2<br>- 所有拒绝都不改状态、不写 verdicts/ | LB-GATES-031、LB-GATES-032、LB-EXIT-014、LB-EXIT-035；:4237、4267-4300 | C.4：G0–G6<br>A07：G0–G6（verdict；另见 01-A05） | §2 末段“verdict 的拒绝分支”；§11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G22 | `VerdictRules.test_lb_gates_032_waiver_rules_when_all_gates_pass` | 七门全过时：<br>- PASS 带豁免：2“PASS 不接受豁免”<br>- AWE 没有失败门禁也要至少一项 --waive 与 --decided-by，缺一为 2（可疑：gates.md 没有这项要求）<br>- 可以豁免已通过的门禁；同一门禁重复豁免时保留最后一条，理由去掉首尾空白<br>- AWE 之后可以再记 PASS；PASS 带 --class 不被拒，failure_class 写入记录与 state.json<br>- PASS 之后还能再记 REVISE（可疑：gates.md 称只能到 INTEGRATED/ABANDONED） | LB-GATES-032、LB-GATES-033、LB-GATES-038；:4279、4291-4298、4306、4312、80 | C.4：G0–G6<br>A07：G0–G6（verdict；另见 01-A05） | §2 末段“PASS 带 --waive”“没有门禁失败时 AWE 仍需至少一项 --waive”；§11.5 第 1 条“重复记录” | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G23 | `VerdictRules.test_lb_gates_033_repeat_verdict_increments_number` | - REVISE 带 --class，--waive 不被拒并照样记录；写 verdicts/01.{md,json}，记录字段（number、failure_class、waivers、note、state_before、candidate_tree、review_sha256、各门结果）逐项断言<br>- 之后依次记 ESCALATE（02）、BLOCKED（03）、REVISE（04），state_before 为上一结论（可疑：gates.md 称 REVISE 之后只能到 ABANDONED）<br>- 失败记录中 G5 仍恒通过 | LB-GATES-033、LB-GATES-029；:4301-4316、80 | C.4：G0–G6<br>A07：G0–G6（verdict；另见 01-A05） | §11.5 第 1 条“重复记录”；LB-LIFE-040（verdicts 编号） | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |
| P4-G24 | `VerdictRules.test_lb_gates_033_infra_failure_attempt_is_reviewable` | - stub startfail（没有 assistant 消息）：INFRA_FAILURE，run 退出 1<br>- 不 check 也可以记 REVISE --class INFRA_FAILURE（退出 0），state_before=INFRA_FAILURE<br>- G1 未通过，含“Pi 退出码为 1” | LB-GATES-033、LB-LIFE-019；:80、4264、3401-3402 | C.4：G0–G6<br>A07：G0–G6（verdict；另见 01-A05） | §11.5 第 9 条“run 在 INFRA_FAILURE 时退出 1” | measured / PASS · `bl-01closure-test-legacy-gates-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-gates-20260925` |

### 12.4 test_legacy_lifecycle.py：取消、超时、预算、任务锁、恢复与 attempt 编号（26 个方法）

- **取证与结果**：取证 `bl-01final-test-legacy-lifecycle-20260925`，归档 `evidence/final/bl-01final-test-legacy-lifecycle-20260925/run/stderr.bin`（sha256 45e9ec9f0b232815ebbd0c9159090c1f3d10aa95cd65e8d523ab8c2812b1a69b）。26 个方法中 24 个 ok；2 个 skipped，都是 POSIX 分支，记 NOT_RUN。 **收尾轮更新**：收尾取证 `bl-01closure-test-legacy-lifecycle-20260926`，归档 `evidence/closure/bl-01closure-test-legacy-lifecycle-20260926/run/stderr.bin`（sha256 e79ad9f8e4e9f8330f7677f2696ae9908dc6604b2735f955c62813924a2aa99f，与原件相同），24 个 ok，2 个 skipped（POSIX 分支，原因与本节下一条相同）；与上述最终取证的归档输出相比，只有“Ran N tests in …s”一行的耗时不同。
- **跳过原因原文**：“只在 POSIX 上运行：SIGINT 到达调度器的语义（KeyboardInterrupt/_Interrupted）；Windows 用 CTRL_BREAK 用例”。
- **构造方式**：标“白盒”的方法在进程内调用 TaskLock。多个预算用例用 `fake_claim` 构造“已领取、预留 N 秒”的 attempt，用构造的 run.json 设定 wall_seconds。
- **PID 处理**：恢复用例在 Pi 存活时就保留它的进程句柄，使 pid_alive 的结果确定。

| 编号 | 测试方法 | 锁定的旧行为（“可疑”照录测试 docstring） | LB 条目 / 源码行（@a4fa199） | C.4 项 / 01-A07 类别 | 对应缺口 | 本次结果 |
|---|---|---|---|---|---|---|
| P4-L01 | `CancelTests.test_LB_LIFE_017_ctrl_break_during_pi_run_is_cancelled_exit_1_not_130` | - Pi 运行中发 CTRL_BREAK_EVENT：CANCELLED，run 退出 1，不输出“已取消。”<br>- run.json：interrupted=true、timed_out=false、spawn_error=null、kill_method=job-object<br>- history 为 PREPARING→PREPARED→RUNNING→COLLECTING→CANCELLED；保留 claim/；Pi 与孙进程被回收<br>- PASS 被 G1“运行被取消或调度器中断”“Pi 退出码为 \<exit_code>”拒绝，状态不变，不写 verdicts/ | LB-LIFE-017、LB-LIFE-019、LB-LIFE-020、LB-EXIT-031；:571-585、703-706、2572、3349、3399-3400、4171-4174 | C.4：取消<br>A07：取消 | §10 取消；§11.5 第 3 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证；条件执行，本次已执行）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925`（条件执行：Windows 且有控制台，本次已执行） |
| P4-L02 | `CancelTests.test_LB_LIFE_035_ctrl_break_before_claim_kills_dispatcher_without_130` | - 调度器停在任务锁等待（领取前）时收到 CTRL_BREAK。Windows 上此时没有 Python 处理器，进程以 0xC000013A（STATUS_CONTROL_C_EXIT）结束，不输出“已取消。”，也不是 130（可疑：与 6.5、7.3 中按 SIGINT 写的“130”不同）<br>- 状态保持 PREPARED；没有 claim/、run-started.json、run.json、pid.txt；history 不变；别人的锁目录保持原样 | LB-LIFE-035、LB-EXIT-031；:676、712、3300、4969-4971 | C.4：取消<br>A07：取消 | §10 取消“各阶段 Ctrl+C 的状态”（领取前，Windows）；§11.5 第 3 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证；条件执行，本次已执行）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925`（条件执行：Windows 且有控制台，本次已执行） |
| P4-L03 | `CancelTests.test_LB_LIFE_017_sigint_during_pi_run_is_cancelled_exit_1_posix` | （POSIX）Pi 运行中收到 SIGINT：CANCELLED，run 退出 1，kill_method=process-group；PASS 被 G1 拒绝 | LB-LIFE-017、LB-LIFE-020、LB-EXIT-031；:571-585、617-622、703-706 | C.4：取消<br>A07：取消 | 无（本机未执行） | NOT_RUN · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）：skipped（POSIX 分支，原因与历史记录相同）<br>历史：NOT_RUN · `bl-01final-test-legacy-lifecycle-20260925`：skipped（POSIX 分支，原因见本节开头） |
| P4-L04 | `CancelTests.test_LB_LIFE_035_sigint_before_claim_exits_130_posix` | （POSIX）领取前收到 SIGINT：main 输出“已取消。”，退出 130；状态 PREPARED，没有 claim/ | LB-LIFE-035、LB-EXIT-002；:3300、4969-4971 | C.4：取消<br>A07：取消 | 无（本机未执行） | NOT_RUN · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）：skipped（POSIX 分支，原因与历史记录相同）<br>历史：NOT_RUN · `bl-01final-test-legacy-lifecycle-20260925`：skipped（POSIX 分支，原因见本节开头） |
| P4-L05 | `TimeoutTests.test_LB_LIFE_016_timeout_run_exits_1_and_pass_refused_by_g1` | - `--timeout 6`：reservation 与 run.json 都记 6；结果 TIMEOUT，run 退出 1<br>- run.json：timed_out=true、interrupted=false；history 经 COLLECTING 到 TIMEOUT；孙进程被回收<br>- PASS 被 G1“运行超时”拒绝（没有“被取消”），状态不变 | LB-LIFE-016、LB-LIFE-011、LB-LIFE-020、LB-EXIT-009；:691-697、3308-3309、3349、3397-3398、4169-4170 | C.4：超时<br>A07：G0–G6（G1） | §10 超时；§11.5 第 9 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L06 | `BudgetTests.test_LB_LIFE_012_budget_race_loser_stays_prepared_exit_3` | 两个 PREPARED attempt 并发争最后一次额度：<br>- 胜方 NEEDS_REVIEW，退出 0<br>- 落败方报“BUDGET_EXCEEDED：已达到 max_attempts_total=2。”，退出 3；保持 PREPARED，没有 claim/，history 不留痕，worktree 保留。拒绝点在锁外或锁内都可能，文本相同，两者都接受<br>- 之后 prepare 被拒（3），不分配新编号 | LB-LIFE-012、LB-LIFE-005、LB-LIFE-007、LB-LIFE-010；:3183-3185、3273-3275、3301-3303 | C.4：锁与预算竞争<br>A07：预算竞争 | §10 锁与预算竞争“预算竞争落败方的状态与退出码”；§11.5 第 4 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L07 | `BudgetTests.test_LB_LIFE_012_run_count_precheck_outside_lock_refuses_before_preflight` | - max_attempts_total=2 时，prepare 连续准备出 3 个 PREPARED，即超额的 PREPARED（11.2 第 11 条）<br>- 把其中两个构造为已领取后，run attempt-003 在锁外次数预检被拒（3）：没有 preflight/，没有 claim/<br>- 之后 prepare 被拒，不分配 attempt-004 | LB-LIFE-012、LB-LIFE-010、LB-LIFE-007；:3183-3185、3273-3275 | C.4：锁与预算竞争<br>A07：预算竞争 | 同 P4-L06（确定性覆盖锁外预检） | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L08 | `BudgetTests.test_LB_LIFE_009_wall_budget_counts_actual_wall_seconds_from_run_json` | 已领取的 attempt 的 run.json 记 wall_seconds=1750（预留 600，构造值）时，按实际用时计入：<br>- prepare 放行（1750<1800）<br>- run 在锁内被拒“BUDGET_EXCEEDED：剩余墙钟预算 50s，不足 60s。”（3），保持 PREPARED | LB-LIFE-009、LB-LIFE-010、LB-LIFE-011；:2574-2576、3304-3306 | C.4：锁与预算竞争<br>A07：预算竞争 | §10 锁与预算竞争（墙钟预算）；§11.5 第 4 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L09 | `BudgetTests.test_LB_LIFE_009_wall_seconds_null_falls_back_to_reservation` | run.json 存在但 wall_seconds=null（collect --recover 合成的 run.json 就是这样）时，按预留 1750 计入；run 被拒“剩余墙钟预算 50s，不足 60s。” | LB-LIFE-009、LB-LIFE-022、LB-LIFE-011；:2577-2579、3430-3431 | C.4：锁与预算竞争<br>A07：预算竞争 | 同 P4-L08 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L10 | `BudgetTests.test_LB_LIFE_010_wall_total_exhausted_refused_by_run_and_prepare` | 预留已达 max_wall_seconds_total=1800：<br>- run 在 Pi 预检之后、锁内被拒“剩余墙钟预算 0s，不足 60s。”（3）<br>- prepare 被拒“累计运行 1800s，达到 max_wall_seconds_total=1800。”（3），不分配新编号 | LB-LIFE-010、LB-LIFE-011、LB-LIFE-009；:3187-3189、3304-3306 | C.4：锁与预算竞争<br>A07：预算竞争 | §10 锁与预算竞争“max_wall_seconds_total 耗尽（prepare 与 run 两种文本）”；§11.5 第 4 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L11 | `BudgetTests.test_LB_LIFE_011_remaining_wall_under_60s_run_refused_but_prepare_allowed` | 预留 1750/1800：<br>- prepare 分配 attempt-002（退出 0）<br>- 它的 run 被拒“剩余墙钟预算 50s，不足 60s。”（3）<br>- 可疑：prepare 与 run 的门槛不同（11.2 第 11 条） | LB-LIFE-011、LB-LIFE-010；:3187、3305 | C.4：锁与预算竞争<br>A07：预算竞争 | §11.5 第 4 条“剩余墙钟不足 60 s” | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L12 | `BudgetTests.test_LB_LIFE_011_remaining_wall_exactly_60s_is_allowed` | - 剩余恰好 60 s 时放行：门槛是严格小于 60<br>- 本轮时限为 60，reservation、run-started.json、run.json 都记 60；NEEDS_REVIEW，退出 0 | LB-LIFE-011；:3305、3307 | C.4：锁与预算竞争<br>A07：预算竞争 | 同 P4-L11（边界） | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L13 | `BudgetTests.test_LB_LIFE_011_remaining_wall_59s_is_refused` | 剩余 59 s 时 run 被拒“剩余墙钟预算 59s，不足 60s。”（3），保持 PREPARED，没有 claim/ | LB-LIFE-011；:3304-3306 | C.4：锁与预算竞争<br>A07：预算竞争 | 同 P4-L11（边界） | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L14 | `BudgetTests.test_LB_LIFE_011_timeout_flag_capped_by_per_attempt_budget` | - `--timeout 5000` 截为 600；`--timeout 0` 不生效，仍为 600<br>- reservation、run-started.json、run.json 与 RUNNING 行一致 | LB-LIFE-011；:3307-3309 | C.4：锁与预算竞争<br>A07：预算竞争 | §10 锁与预算竞争“--timeout 被预算截短”；§11.5 第 4 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L15 | `BudgetTests.test_LB_LIFE_011_negative_timeout_flag_becomes_1s` | - `--timeout=-5` 得到时限 1 s，即 max(1, min(600, -5))<br>- hang 场景在 1 s 后超时，结果 TIMEOUT，run 退出 1 | LB-LIFE-011；:691、3308-3309 | C.4：锁与预算竞争、超时<br>A07：预算竞争 | 同 P4-L14 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L16 | `BudgetTests.test_LB_LIFE_011_timeout_flag_capped_by_remaining_total_budget` | 预留 1500/1800 时本轮时限为 300，`--timeout 1000` 被截为 300；NEEDS_REVIEW，退出 0 | LB-LIFE-011、LB-LIFE-009；:3307、3309 | C.4：锁与预算竞争<br>A07：预算竞争 | 同 P4-L14（按剩余总预算） | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L17 | `ExecutorAllowlistTests.test_LB_LIFE_036_allowed_executors_miss_refused_at_prepare_and_run` | allowed_executors 未命中时：<br>- prepare 退出 3“执行模型 step/step-5-preview 不在 .agent/dispatch.config.json 的 allowed_executors 中”，不建 .agent/runs/\<task>/<br>- prepare 之后才收紧列表时，run 在 Pi 预检之前退出 3；保持 PREPARED，没有 claim/ 与 preflight/，history 不留痕 | LB-LIFE-036、LB-LIFE-003、LB-EXIT-005；:2688-2694、3178-3180、3271 | C.4：锁与预算竞争、实际模型与思考级别证据<br>A07：六类之外（01-A08） | §10 锁与预算竞争、实际模型与思考级别证据“allowed_executors 未命中”；§11.5 第 4 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L18 | `TaskLockTests.test_LB_LIFE_005_held_task_lock_run_waits_30s_then_exit_3` | 黑盒，另一方持有新鲜的锁：<br>- run 等待约 30 s 后退出 3“任务锁被占用：<锁路径>（另一个 run 正在领取；如确认无人使用可删除该目录）”<br>- 不读 owner.json，锁目录保持原样；保持 PREPARED，没有 claim/<br>- 删除锁后再次 run，沿用同一编号并成功<br>- 耗时下界 30 s，上界 60 s（宽松值） | LB-LIFE-005、LB-LIFE-013；:2586、2593、2597、2607-2610 | C.4：锁与预算竞争<br>A07：预算竞争 | §10 锁与预算竞争“TaskLock 等待 30 s 后任务锁被占用”；§11.5 第 4 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L19 | `TaskLockTests.test_LB_LIFE_006_stale_task_lock_taken_over_by_run` | 黑盒：<br>- 锁目录 mtime 早于 300 s 时，run 删除它后重新取得，领取并运行成功<br>- 离开临界区时删除锁目录，原 owner.json 随之消失 | LB-LIFE-006；:2601-2606、2612-2613 | C.4：锁与预算竞争<br>A07：预算竞争 | §10 锁与预算竞争“300 s 过期接管”；§11.5 第 4 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L20 | `TaskLockTests.test_LB_LIFE_005_task_lock_wait_timeout_and_stale_takeover_whitebox` | 白盒：<br>- 默认参数为 (30.0, 300.0)<br>- 把等待改为 1.5 s：约 wait_seconds 后抛 DispatchError（code=3），消息逐字；不读、不改别人的 owner.json<br>- 过期锁被 rmtree 后取得，owner.json 改写为本进程 pid；退出时删除锁目录 | LB-LIFE-005、LB-LIFE-006；:2586、2593、2597、2604-2610 | C.4：锁与预算竞争<br>A07：预算竞争 | 同 P4-L18、L19 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925`（白盒） |
| P4-L21 | `TaskLockTests.test_LB_LIFE_006_task_lock_release_ignores_ownership_whitebox` | 白盒：<br>- A（子进程）持锁 → 锁变旧 → B 接管<br>- A 退出时无条件 rmtree，删掉 B 的锁；B 仍在临界区时，C 立即取得锁，互斥失效（可疑，11.2 第 10 条）<br>- B 退出时 ignore_errors，不报错 | LB-LIFE-006；:2612-2613 | C.4：锁与预算竞争<br>A07：预算竞争 | §10 锁与预算竞争“归属缺失”；11.2 第 10 条由探针升级为白盒实测 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925`（白盒） |
| P4-L22 | `RecoverTests.test_LB_LIFE_024_recover_refused_while_pi_alive_then_recovers_cancelled` | - RUNNING 且记录的 Pi 存活时，`collect --recover` 退出 3“记录的 Pi 进程 \<pid> 可能仍在运行；确认终止后再恢复。”；不写 run.json，不改名证据<br>- `taskkill /F`（不带 /T）结束调度器后，Pi 被 Job Object 回收<br>- 恢复合成 run.json（exit_code=None、timed_out=false、interrupted=true、recovered=true、wall_seconds=None、spawn_error=None），输出“CANCELLED（恢复收集；事件可能不完整）”，退出 0<br>- history 从 RUNNING 直接到 CANCELLED，不分配新编号<br>- PASS 被 G1“运行被取消或调度器中断”“Pi 退出码为 None”拒绝（1） | LB-LIFE-024、LB-LIFE-022、LB-LIFE-023、LB-EXIT-010；:3421-3425、3426-3434、3440-3443 | C.4：进程恢复、取消<br>A07：取消（G1）；另见 01-A08 | §10 进程恢复“pid 仍存活时拒绝恢复”；§10 取消（原唯一相关 check 同时接受 CANCELLED 与 INFRA_FAILURE，本例锁定为 CANCELLED）；§11.5 第 4 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L23 | `RecoverTests.test_LB_LIFE_023_recover_from_collecting_reuses_run_json_and_can_pass` | 把状态改回 COLLECTING 之后：<br>- 不带 --recover：退出 2<br>- `collect --recover`：原样沿用已有 run.json（字节不变）；candidate.json、changes.json、scope.json、candidate.patch 改名为 *.partial 后重新收集，候选树不变；直接 NEEDS_REVIEW，记 recovered_collection，退出 0<br>- 再次恢复：退出 2<br>- check 之后 PASS 被接受（可疑，11.2 第 13 条：恢复证据可以直接作为 PASS 依据） | LB-LIFE-023、LB-LIFE-022、LB-EXIT-010；:3416-3420、3426、3436-3440 | C.4：进程恢复<br>A07：六类之外（01-A08） | §10 进程恢复“COLLECTING 状态的恢复”“run.json 已存在时的恢复”“.partial 重命名”“非可恢复状态或缺 --recover 时的 2”；§11.5 第 4 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L24 | `RecoverTests.test_LB_LIFE_023_second_recover_with_partial_present_crashes_on_windows` | - 第一次恢复留下 *.partial，状态再停在 COLLECTING 后做第二次恢复<br>- 改名撞上已存在的 candidate.json.partial：Windows 上 FileExistsError 回溯，退出 1<br>- 状态停在 COLLECTING，不记 recovered_collection（可疑，11.2 第 3 条，原为推断） | LB-LIFE-023；:3436-3439、4964-4971 | C.4：进程恢复<br>A07：六类之外（01-A08） | §10 进程恢复“.partial 重命名”；§11.5 第 4 条 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证；条件执行，本次已执行）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925`（条件执行：skipUnless(IS_WINDOWS)，本次已执行） |
| P4-L25 | `AttemptNumberTests.test_LB_LIFE_002_first_attempt_is_1_and_only_prepare_advances` | - 首次 prepare 得到 attempt-001（attempt_no=1）<br>- 预检失败：退出 3，记 preflight_failed，不领取，不换编号；修正后 run 沿用 001<br>- 第二次 prepare 得到 002；v2 合同的 prepare 得到 attempt-003（normalize-query.v2.a003），编号跨 plan_version 连续 | LB-LIFE-002、LB-LIFE-001、LB-LIFE-003、LB-LIFE-004；:2617-2623、3193、3281-3285 | C.4：不在 12 项中（01-D03）<br>A07：六类之外（01-A08） | §11.5 第 4 条“跨 plan_version 的编号连续” | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |
| P4-L26 | `AttemptNumberTests.test_LB_LIFE_001_number_is_max_plus_one_and_never_zero` | - 手工建的 attempt-000、attempt-01 不影响结果，首个编号仍为 1<br>- attempt-0007 按 7 参与取最大值，下一次得到 attempt-008，不回填空缺 | LB-LIFE-001、LB-LIFE-002；:62、2619-2621 | C.4：不在 12 项中（01-D03）<br>A07：六类之外（01-A08） | 第 1 节第 1 行（编号规则）的补测 | measured / PASS · `bl-01closure-test-legacy-lifecycle-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-lifecycle-20260925` |

### 12.5 test_legacy_cli.py：合同缺省值、Markdown/JSON 一致性、范围、入口与退出码（75 个方法）

- **取证与结果**：取证 `bl-01final-test-legacy-cli-20260925`，归档 `evidence/final/bl-01final-test-legacy-cli-20260925/run/stderr.bin`（sha256 484493ae4f7412a21b7c473fbfcbb663d891ff5a0e3575943366e242c4440c8c）。75 个方法中 74 个 ok；1 个 skipped，是 POSIX 分支，记 NOT_RUN。 **收尾轮更新**：收尾取证 `bl-01closure-test-legacy-cli-20260926`，归档 `evidence/closure/bl-01closure-test-legacy-cli-20260926/run/stderr.bin`（sha256 26cce1cf6ad440b5f584180592d772bb4e720e2a54f353694f458bef6a16c3ae，与原件相同），74 个 ok，1 个 skipped（POSIX 分支）；与上述最终取证的归档输出相比，只有“Ran N tests in …s”一行的耗时不同。
- **白盒部分**：`LegacyContractDefaultsTest`、`LegacyMarkdownJsonConsistencyTest`、`LegacyScopeInProcessTest`、`LegacyMainInProcessTest` 四个类在进程内调用被测函数。
- **子进程部分**：其余各类都在子进程中运行被测脚本。`assert_refused` 断言退出码精确相等，且 stderr 恰为一行 `ERROR: <消息>`。

| 编号 | 测试方法 | 锁定的旧行为（“可疑”照录测试 docstring） | LB 条目 / 源码行（@a4fa199） | C.4 项 / 01-A07 类别 | 对应缺口 | 本次结果 |
|---|---|---|---|---|---|---|
| P4-C01 | `LegacySourceTest.test_source_under_test_is_a4fa199` | 被测 scripts/pi_dispatch.py 把 CRLF 归一为 LF 之后的 sha256，等于 legacy_harness.LOCKED_PI_DISPATCH_SHA256（a00d6934…）；load_legacy_module 加载后 TOOL_VERSION 为 2.2.2 | 新增：被测字节核对（没有 LB 条目） | C.4：不在 12 项中<br>A07：回归映射须指明被测提交 | — | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；条件执行，本次已执行）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（条件执行：没有设置 CODEKIT_LEGACY_KIT_DIR，本次已执行） |
| P4-C02 | `LegacyContractDefaultsTest.test_LB_CONTRACT_003_normalize_empty_contract_defaults` | 白盒：normalize_contract({}) 的完整输出：<br>- executor：thinking=high、7 个默认工具、context_files=project<br>- scope：四个列表为空，dependency_changes=forbidden<br>- authorization：[local_edit, local_test] / []<br>- budget：2/1200/2400/null<br>- setup、checks、DoD 为 []<br>- 不补 schema_version、task_id、plan_version、base_sha、risk_level，也不补 provider/model | LB-CONTRACT-003（另见 LB-LIFE-008 的缺省值部分）；:1189-1214 | C.4：旧合同默认值<br>A07：六类之外（01-A02） | §10 旧合同默认值；§11.5 第 5 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C03 | `LegacyContractDefaultsTest.test_LB_CONTRACT_003_command_item_defaults_setup_has_no_required` | 白盒：<br>- checks 的对象项补 cwd="."、required=true、expected_exit_code=0；setup 项不补 required<br>- expect_on_base、输出模式、env 不写回<br>- 数组中不是对象的项原样保留 | LB-CONTRACT-003、LB-CONTRACT-004；:1207-1213 | C.4：旧合同默认值<br>A07：六类之外（01-A02） | 同 P4-C02 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C04 | `LegacyContractDefaultsTest.test_LB_CONTRACT_004_explicit_null_and_wrong_types_not_filled` | 白盒：<br>- 显式 thinking=null 保留<br>- 类型不对的节（scope=["x"]、checks={}）整节不补<br>- cost_budget 为对象时不检查，也不补内部键 | LB-CONTRACT-004；:1200-1211 | C.4：旧合同默认值<br>A07：六类之外（01-A02） | 同 P4-C02 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C05 | `LegacyContractDefaultsTest.test_LB_CONTRACT_004_normalize_deep_copies_input` | 白盒：normalize 不修改调用方传入的对象（先深拷贝） | LB-CONTRACT-004；:1191 | C.4：旧合同默认值<br>A07：六类之外（01-A02） | 同 P4-C02 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C06 | `LegacyContractDefaultsTest.test_LB_CONTRACT_005_unserializable_raw_wrapped_as_structure_error` | 白盒：raw 含 set 时返回 (None, ["合同结构无效：TypeError: Object of type set is not JSON serializable"], [])。这个分支只在进程内调用时可达 | LB-CONTRACT-005、LB-CONTRACT-031（部分）；:1191、1432-1437 | C.4：旧合同默认值<br>A07：六类之外（01-A02） | §11.5 第 5 条“合同结构无效” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C07 | `LegacyContractDefaultsTest.test_LB_CONTRACT_003_provider_model_have_no_default_and_validate_passes` | 白盒：合同不写 provider/model 时，validate_contract 无错误、无警告，结果中也没有这两个键（可疑，11.6 第 4 条） | LB-CONTRACT-003；:1484-1487 | C.4：旧合同默认值<br>A07：六类之外（01-A02） | 同 P4-C02 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C08 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_017_md_budget_changed_json_unchanged` | 白盒：只改 Markdown 的 max_attempts_total，报“Markdown Budget 的 max_attempts_total（5）与 JSON（3）不一致” | LB-CONTRACT-017；:1618-1622 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | §10 Markdown/JSON 一致性“改 Markdown 而 JSON 不变”；§11.5 第 5 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C09 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_md_identity_risk_level_changed` | 白盒：只在 Markdown 中把 risk_level 从 low 改为 medium，报 Identity 不一致（原文） | LB-CONTRACT-016；:1594-1598 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | 同 P4-C08 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C10 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_md_thinking_changed` | 白盒：thinking 从 high 改为 xhigh，报“Markdown Identity 的 executor 应写明 thinking high” | LB-CONTRACT-016；:1610-1611 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | 同 P4-C08 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C11 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_md_integration_actions_changed` | 白盒：integration_actions 多写 push，报不一致（原文） | LB-CONTRACT-016；:1599-1605、1409-1413 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | 同 P4-C08 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C12 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_017_md_dependency_changes_changed` | 白盒：dependency_changes 从 forbidden 改为 allowed，报“Markdown Scope 的 dependency_changes 与 JSON（forbidden）不一致” | LB-CONTRACT-017；:1615-1617 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | 同 P4-C08 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C13 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_017_md_validation_argv_changed` | 白盒：改写 V01 的命令，报“Markdown 中 V01 的命令与 JSON argv 不一致：…” | LB-CONTRACT-017；:1416-1429、1623-1630 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | 同 P4-C08 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C14 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_017_md_validation_line_removed` | 白盒：删掉 V01 行，报“Markdown Validation commands 未列出 V01” | LB-CONTRACT-017；:1623-1628 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | 同 P4-C08 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C15 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_017_md_forbidden_path_removed` | 白盒：删掉 forbidden 路径，报“Markdown 未列出 JSON 中的路径：package.json” | LB-CONTRACT-017；:1612-1614 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | 同 P4-C08 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C16 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_018_md_only_additions_and_dod_text_not_compared` | 白盒：Markdown 多列允许路径、多一条检查行、改写 DoD 文字，都没有错误和警告。只检查 JSON→Markdown 一个方向（可疑，11.2 第 1 条 (4)、第 2 条） | LB-CONTRACT-017、LB-CONTRACT-018；:1582-1633 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | §10 Markdown/JSON 一致性（比较范围之外的方向） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C17 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_fullwidth_colon_identity_value_reads_as_none` | 白盒：“- risk_level：low”（全角冒号）报“Markdown Identity 的 risk_level（None）与 JSON（'low'）不一致”（可疑，11.2 第 1 条 (8)） | LB-CONTRACT-016；:1134-1141 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | §11.5 第 5 条（边界） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C18 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_fullwidth_colon_action_list_reads_as_missing` | 白盒：authorized_actions 用全角冒号，报“Markdown Identity 缺少 authorized_actions”（可疑） | LB-CONTRACT-016；:1599-1603 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | 同 P4-C17 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C19 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_017_fullwidth_colon_dependency_changes_not_recognised` | 白盒：dependency_changes 用全角冒号，报不一致（可疑） | LB-CONTRACT-017；:1615 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | 同 P4-C17 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C20 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_identity_value_note_is_stripped` | 白盒：“- risk_level: `low`（改动集中）”去掉反引号与括号说明后一致，没有错误 | LB-CONTRACT-016；:1126-1131 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | 同 P4-C17 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C21 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_035_risk_level_upper_in_json_lower_in_md` | 白盒：JSON 为 "Low"、Markdown 为 low 时有两条错误，依次是取值错误与 Identity 不一致（级联） | LB-CONTRACT-035、LB-CONTRACT-007；:1468-1469、1594-1598 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | §10 Markdown/JSON 一致性“多个缺陷同时存在”（一例）；§11.5 第 5 条（risk_level 取值） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C22 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_035_risk_level_upper_in_both` | 白盒：两边都写 Low 时只有“risk_level 必须是 low/medium/high 之一”，取值检查区分大小写 | LB-CONTRACT-035、LB-CONTRACT-007；:1468-1469 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | §11.5 第 5 条（risk_level 取值） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C23 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_risk_level_upper_in_md_only` | 白盒：只有 Markdown 写 Low 时报不一致，Identity 按字符串完全相等比较 | LB-CONTRACT-016；:1594-1598 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | 同 P4-C08 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C24 | `LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_015_title_capture_stops_at_first_foreign_char` | 白盒：“# TASK: normalize-queryX”通过；“# TASK: normalize-query-x”报“Markdown 标题应为 …”。标题捕获在第一个不属于 [a-z0-9-] 的字符处停止（可疑，11.2 第 1 条 (6)） | LB-CONTRACT-015；:1591-1593 | C.4：Markdown/JSON 一致性<br>A07：六类之外（01-A02） | 同 P4-C17 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C25 | `LegacyScopeInProcessTest.test_LB_GATES_018_deleted_file_outside_allowed_deleted_is_out_of_scope` | 白盒 evaluate_scope：<br>- 删除不在 allowed_deleted_files 中的文件（包括允许修改的文件）：记 out_of_scope“状态 D 不在允许集合”<br>- 列入 allowed_deleted_files 后通过 | LB-GATES-018；:2465-2467 | C.4：范围检查<br>A07：范围 | §10 范围检查“删除越界”；§11.5 第 8 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C26 | `LegacyScopeInProcessTest.test_LB_GATES_017_protected_paths_ignore_case_scope_lists_do_not` | 白盒：<br>- 受保护路径忽略大小写：Agents.md、docs/CLAUDE.MD、.Agent/plans/x.md、Scripts/Pi_Dispatch.py 都记 protected_path<br>- scope 列表与依赖清单区分大小写：Package.json 只算 out_of_scope，不算依赖变更 | LB-GATES-017、LB-GATES-018；:1063-1093、2459-2467、2478-2484 | C.4：范围检查<br>A07：范围 | §10 范围检查“大小写不同的受保护路径”；§11.5 第 8 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C27 | `LegacyScopeInProcessTest.test_LB_GATES_018_new_symlink_is_violation_symlink_to_file_is_silent` | 白盒：<br>- 新增符号链接（000000→120000）与普通文件改为符号链接（100644→120000）都记 symlink 违规，不报 mode_changed<br>- 符号链接改回普通文件（120000→100644）既不算违规也不算警告（可疑，11.2 第 9 条，原为内存核实） | LB-GATES-018；:2465-2477 | C.4：范围检查<br>A07：范围 | §10 范围检查“symlink”；§11.5 第 8 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C28 | `LegacyScopeInProcessTest.test_LB_GATES_019_head_moved_is_warning_only_with_local_commit` | 白盒：HEAD 移动在没有 local_commit 时是违规；有 local_commit 时降为警告，ok=true | LB-GATES-019；:2488-2491 | C.4：范围检查<br>A07：范围 | §10 范围检查“local_commit 下的 head_moved”；§11.5 第 8 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C29 | `LegacyMainInProcessTest.test_LB_EXIT_002_main_maps_keyboard_interrupt_to_130` | 白盒：子命令抛 KeyboardInterrupt 时，main 返回 130，stderr 为“已取消。” | LB-EXIT-002；:4969-4971 | C.4：wait/退出码语义、取消<br>A07：六类之外（01-A05） | §10 取消、wait/退出码语义“main 的 130”；§11.5 第 3、9 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒；经子进程到达 130 的只有 POSIX 用例 P4-L04，本机 NOT_RUN） |
| P4-C30 | `LegacyMainInProcessTest.test_LB_EXIT_002_main_maps_dispatch_error_to_its_code` | 白盒：DispatchError 的缺省码为 3，带 EXIT_USAGE 时为 2；stderr 为“ERROR: \<msg>” | LB-EXIT-002、LB-EXIT-001；:304-309、4966-4968 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §10 wait/退出码语义“未锁定缺省码 3” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C31 | `LegacyMainInProcessTest.test_LB_EXIT_002_main_does_not_catch_other_exceptions` | 白盒：其他异常（RuntimeError）从 main 传出 | LB-EXIT-002；:4964-4971 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §10 wait/退出码语义“未捕获异常的 1”（子进程层见 P4-C49） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（白盒） |
| P4-C32 | `LegacyWaitTest.test_LB_EXIT_023_wait_timeout_below_one_is_usage_2` | `--timeout 0` 与 `-5`：退出 2，stdout 为空，stderr 为“ERROR: --timeout 必须是正整数（秒）” | LB-EXIT-023；:3926-3927 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §10 wait“--timeout<1 的 2”；§11.5 第 9 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C33 | `LegacyWaitTest.test_LB_EXIT_023_wait_unknown_attempt_reported_before_timeout_check` | 找不到 attempt 时先报“找不到 attempt：…”（2），早于 --timeout 检查 | LB-EXIT-023、LB-EXIT-005；:2650、3924-3927 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | —（补充拒绝顺序） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C34 | `LegacyWaitTest.test_LB_EXIT_024_wait_missing_state_json_is_unknown_exit_1` | state.json 缺失时，stdout 为“无法确定 attempt 的状态（UNKNOWN）：state.json 缺失、损坏或状态未知。检查 \<run>”，退出 1 | LB-EXIT-024、LB-LIFE-029；:2554-2555、3943-3945 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §10 wait“state.json 缺失（UNKNOWN）”；§11.5 第 4、9 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C35 | `LegacyWaitTest.test_LB_EXIT_024_wait_null_missing_key_or_unknown_state_exit_1` | 以下情形都退出 1：<br>- `{"state": null}` 显示为 None（可疑）<br>- 没有 state 键、内容为 `{`：显示 UNKNOWN<br>- 未知值 FOO：原样显示 | LB-EXIT-024；:2555 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | 同 P4-C34 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C36 | `LegacyWaitTest.test_LB_EXIT_030_wait_non_object_state_json_traceback_exit_1` | state.json 为 `[]`：AttributeError 回溯，退出 1，stdout 为空，没有“ERROR:”（可疑，11.2 第 3 条） | LB-EXIT-030；:2555 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §11.5 第 9 条“非对象 state.json” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C37 | `LegacyWaitTest.test_LB_EXIT_024_wait_preparing_and_collecting_time_out_with_3_without_live` | PREPARING、COLLECTING 等满 --timeout 后退出 3，输出“仍在运行：\<run> · \<STATE>。再次运行 wait 继续等待。”，不附 live 片段 | LB-EXIT-024；:3933-3937 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §10 wait“PREPARING/COLLECTING 到时”；§11.5 第 9 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C38 | `LegacyWaitTest.test_LB_EXIT_025_wait_running_time_out_appends_live_fragment` | RUNNING 到时，输出附“ · live:2t”，退出 3 | LB-EXIT-025、LB-EXIT-024；:3935、4525-4548 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §11.5 第 9 条“到时输出中的 live 片段” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C39 | `LegacyWaitTest.test_LB_EXIT_025_live_progress_variants_via_status_json` | `status --json` 对 RUNNING 行把 events_ok 换成 live 字符串，退出 0：<br>- 紧凑写法计为 live:2t；带空格的 JSON 计为 live:0t（可疑，11.3 第 6 条）<br>- 附已运行的秒数<br>- 6000 个增量没有工具调用时附提示<br>- NEEDS_REVIEW 行为 null | LB-EXIT-025、LB-EXIT-019、LB-EVENTS-029；:4522、4531-4548、4562-4564 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §11.5 第 9 条（live 片段） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C40 | `LegacyWaitTest.test_LB_EXIT_024_wait_terminal_prints_summary_line` | 已结束且有 summary.md 时输出两行：“已结束：… · NEEDS_REVIEW”与“摘要：…/summary.md”；退出 0 | LB-EXIT-024；:3946-3950 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §11.5 第 9 条“已结束时的摘要：行” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C41 | `LegacyWaitTest.test_LB_EXIT_026_wait_exit_0_for_failed_terminal_state_without_summary` | INFRA_FAILURE、REVISE、PREPARE_FAILED 都退出 0。wait 的 0 只表示已结束（可疑） | LB-EXIT-026；:81-82、3946-3950 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | —（补充 LB-EXIT-026） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C42 | `LegacyWaitTest.test_LB_EXIT_024_wait_prepared_returns_3_after_min_60_timeout` | timeout=2（<60）时，PREPARED 等满 2 s 后退出 3，用“attempt 仍是 PREPARED：run 没有开始…”的文案 | LB-EXIT-024、LB-LIFE-029；:3933、3940-3942 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §10 wait“60 s 宽限”（timeout<60 一侧） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C43 | `LegacyWaitTest.test_LB_EXIT_024_wait_prepared_grace_keeps_polling` | timeout=120 时，PREPARED 不立即返回；状态变为 NEEDS_REVIEW 后退出 0。60 s 上限本身没有测 | LB-EXIT-024；:3933 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §10 wait“60 s 宽限”（部分） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C44 | `LegacyWaitTest.test_LB_EXIT_026_wait_git_missing_is_3` | PATH 中没有 git 时，wait 退出 3“ERROR: 未找到 git，请先安装 Git。”。它与“仍在运行”的 3 同码（可疑，11.2 第 15 条） | LB-EXIT-026；:756-757、958、3924 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §10 wait“未锁定缺省码 3” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C45 | `LegacyWaitTest.test_LB_EXIT_038_resolve_by_task_id_picks_latest_attempt_without_meta` | 按 task-id 取编号最大的 attempt，不要求 meta.json（可疑，11.2 第 13 条） | LB-EXIT-038、LB-LIFE-033；:2643-2649 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | 原 NOT_RUN 条目，见 9.9 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C46 | `LegacyMainEntryTest.test_LB_EXIT_002_no_subcommand_prints_help_to_stdout_exit_2` | 没有子命令时，帮助写到 stdout，退出 2，stderr 为空 | LB-EXIT-002、LB-CONTRACT-034；:4961-4963 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §11.5 第 9 条“main 的无子命令 2” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C47 | `LegacyMainEntryTest.test_LB_EXIT_003_argparse_usage_errors_exit_2_without_error_prefix` | 8 种用法错误都退出 2，stdout 为空，stderr 以 usage 开头，没有“ERROR:”：<br>- 未知子命令、缺参数<br>- 非法 int、非法 choice<br>- verdict 缺 --review<br>- smoke 缺 --provider/--model<br>- mutate 缺 --spec | LB-EXIT-003；:4960 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §10 wait“argparse 的 2”；§11.5 第 9 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C48 | `LegacyMainEntryTest.test_LB_EXIT_003_version_exit_0` | `--version` 输出“pi_dispatch 2.2.2”，退出 0 | LB-EXIT-003；:48、4835 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | — | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C49 | `LegacyMainEntryTest.test_LB_EXIT_002_uncaught_exception_traceback_exit_1` | Markdown 不是 UTF-8 时，validate 以 UnicodeDecodeError 回溯退出 1，stdout 为空，没有“ERROR:”（可疑：同类问题出现在 JSON 时是 2，兼容矩阵 D-22） | LB-EXIT-002、LB-CONTRACT-030、LB-EXIT-040；:1668 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §10 wait“未捕获异常的 1”；§11.5 第 5、9 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C50 | `LegacyMainEntryTest.test_LB_EXIT_029_repo_not_a_repository_is_2` | `--repo <非仓库目录>` 退出 2“ERROR: 当前目录不在 Git 仓库中：…” | LB-EXIT-029、LB-EXIT-005；:958-960 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | 原 NOT_RUN 条目，见 9.9 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C51 | `LegacyMainEntryTest.test_LB_EXIT_029_repo_missing_path_windows_traceback_1` | Windows：`--repo <不存在的路径>` 抛 NotADirectoryError [WinError 267]，回溯，退出 1（可疑，11.4 第 2 条） | LB-EXIT-029；:754-757、957-958 | C.4：wait/退出码语义<br>A07：六类之外（01-A05、01-A15） | 同 P4-C50 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；条件执行，本次已执行）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（条件执行：skipUnless(IS_WINDOWS)，本次已执行） |
| P4-C52 | `LegacyMainEntryTest.test_LB_EXIT_029_repo_missing_path_posix_reported_as_git_missing_3` | （POSIX）同一输入被报为“未找到 git，请先安装 Git。”，退出 3（依据源码推断） | LB-EXIT-029；:756-757 | C.4：wait/退出码语义<br>A07：六类之外（01-A05、01-A15） | 无（本机未执行） | NOT_RUN · `bl-01closure-test-legacy-cli-20260926`（收尾取证）：skipped（POSIX 分支，原因与历史记录相同）<br>历史：NOT_RUN · `bl-01final-test-legacy-cli-20260925`：skipped“POSIX 分支；本机 Windows 的结果见上一用例（本次 NOT_RUN）” |
| P4-C53 | `LegacyRefusalCodesTest.test_LB_EXIT_008_prepare_contract_invalid_is_2_without_attempt` | Markdown Budget 被改：<br>- prepare 退出 2，stderr 恰为“ERROR: 合同校验失败，未创建 attempt。”，stdout 列出错误，不建 attempt 目录<br>- validate 同样退出 2，并打印“合同无效：1 个错误，0 个警告。” | LB-EXIT-008、LB-CONTRACT-018；:3172-3173 | C.4：wait/退出码语义、Markdown/JSON 一致性<br>A07：六类之外（01-A05） | §11.5 第 9 条“拒绝路径只断言 code != 0”（prepare） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C54 | `LegacyRefusalCodesTest.test_LB_EXIT_008_prepare_runs_not_ignored_is_3` | .agent/runs/ 没有被忽略时，prepare 退出 3；stdout 带 validate 的 WARN | LB-EXIT-008；:1688-1689、3174-3175 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | 同 P4-C53 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C55 | `LegacyRefusalCodesTest.test_LB_EXIT_035_prepare_env_conflict_2_precedes_allowlist_3` | prepare：<br>- PI_EXEC_MODEL 与合同冲突为 2，先于 allowed_executors 未命中的 3<br>- 思考级别固定为 low 而合同为 high 时为 3<br>- 均不建 attempt 目录 | LB-EXIT-035、LB-EXIT-008；:2668-2699 | C.4：wait/退出码语义、实际模型与思考级别证据<br>A07：六类之外（01-A05） | 同 P4-C53；§11.5 第 4 条（allowed_executors） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C56 | `LegacyRefusalCodesTest.test_LB_EXIT_009_run_refusals_keep_prepared` | run 的各种拒绝都不领取，状态保持 PREPARED：<br>- PI_EXEC_PROVIDER 冲突：2<br>- PI_DISPATCH_PI_CMD 为 `[]`：2<br>- 模型不在列表中，预检失败：3<br>- run 目录中的 plan.md 被改：“输入不一致（G0）：…”，3<br>- claim/ 已存在：“（已领取）…”，3<br>- ABANDONED：3 | LB-EXIT-009、LB-LIFE-013、LB-LIFE-036、LB-EVENTS-002（部分）；:1768-1769、3254-3285 | C.4：wait/退出码语义、锁与预算竞争<br>A07：六类之外（01-A05） | §11.5 第 9 条（run 的精确码）；§11.5 第 7 条（PI_DISPATCH_PI_CMD 非法值一例） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C57 | `LegacyRefusalCodesTest.test_LB_EXIT_010_collect_refusals_2_and_live_pid_3` | collect：<br>- PREPARED（带或不带 --recover）、RUNNING 不带 --recover：2<br>- RUNNING 且记录的 pid 存活时带 --recover：3，不写 run.json | LB-EXIT-010、LB-LIFE-022、LB-LIFE-024；:3416-3425 | C.4：wait/退出码语义、进程恢复<br>A07：六类之外（01-A08） | §10 进程恢复“pid 仍存活”“缺 --recover 时的 2” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C58 | `LegacyRefusalCodesTest.test_LB_EXIT_014_verdict_on_unreviewable_state_is_3` | PREPARED 时 verdict 退出 3“状态 PREPARED 不能记录验收结论” | LB-EXIT-014、LB-GATES-031、LB-LIFE-026；:4263-4265 | C.4：G0–G6、wait/退出码语义<br>A07：G0–G6（verdict） | §11.5 第 1 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C59 | `LegacyRefusalCodesTest.test_LB_EXIT_014_verdict_usage_2_and_gate_refusal_1` | 没有 check 时：<br>- 找不到复审报告、Verdict 行不符、--waive 格式错、REVISE 缺 --class、AWE 缺豁免、AWE 缺 --decided-by：都是 2<br>- PASS 被 G3/G4 拒绝为 1；带 --waive 也是 1，门禁先于豁免<br>- stderr 恰为一行“ERROR: …”；状态不变，不写 verdicts/ | LB-EXIT-014、LB-EXIT-035、LB-GATES-031、LB-GATES-032；:4266-4300 | C.4：G0–G6、wait/退出码语义<br>A07：G0–G6（verdict） | §11.5 第 1、9 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C60 | `LegacyRefusalCodesTest.test_LB_EXIT_015_branch_without_passing_verdict_is_3` | 没有结论时，branch（含 --rework、非法 --trailer）一律退出 3“最新结论为 None：…”。结论检查先于 --trailer 的 2 | LB-EXIT-015、LB-GATES-035、LB-EXIT-035；:4331-4342 | C.4：补丁往返/完整性、wait/退出码语义<br>A07：六类之外（01-A05） | §11.5 第 9 条（branch 的精确码） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C61 | `LegacyRefusalCodesTest.test_LB_EXIT_016_mark_refusal_codes` | mark：<br>- INTEGRATED：缺结论 3，缺 --ref 2，先查结论<br>- SUPERSEDED：对 PREPARED 为 2，缺 --reason 为 2<br>- PREPARING、COLLECTING、RUNNING 不带 --force 放弃：3；RUNNING 且 pid 存活时带 --force 仍为 3<br>- 已 ABANDONED 但最新结论为 PASS 时，仍可标 INTEGRATED（可疑，11.2 第 12 条） | LB-EXIT-016、LB-LIFE-025、LB-GATES-036、LB-EXIT-035；:4395-4419 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §11.5 第 9 条（mark） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C62 | `LegacyRefusalCodesTest.test_LB_EXIT_017_cleanup_refusal_codes` | cleanup：<br>- PREPARED、PREPARING 不带 --force：3<br>- RUNNING、COLLECTING 带 --force 也是 3<br>- 没有候选记录时报 LOSS 并拒绝（3）；带 --force 后移除 worktree<br>- 拒绝时 worktree 保留 | LB-EXIT-017、LB-LIFE-030、LB-GATES-037；:4435-4467 | C.4：候选树漂移、wait/退出码语义<br>A07：候选漂移 | §11.5 第 9 条（cleanup） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C63 | `LegacyRefusalCodesTest.test_LB_GATES_037_cleanup_refuses_when_candidate_patch_tampered` | 补丁末尾多一个字节时：<br>- cleanup 只报一条“LOSS  候选补丁缺失、被改动或未通过往返校验：删除后无法重建候选”，退出 3，worktree 保留<br>- 带 --force 后退出 0；history 的 cleanup 记录把这一条列入 discarded | LB-GATES-037、LB-EXIT-017；:3474-3477、4451-4452、4463-4467、4481 | C.4：补丁往返/完整性、候选树漂移<br>A07：补丁完整性 | §10 补丁往返/完整性（cleanup 层） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C64 | `LegacyRefusalCodesTest.test_LB_EXIT_012_baseline_refusal_codes` | baseline：<br>- --only 指定未知检查：2；合同无效：2<br>- 基线副本的 setup 失败：3，副本仍被移除<br>- expect_on_base 不符：1 | LB-EXIT-012、LB-GATES-015；:4081-4149 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §11.5 第 9 条（baseline） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C65 | `LegacyRefusalCodesTest.test_LB_EXIT_021_doctor_codes` | doctor：<br>- .agent/runs/ 没有被忽略：记入 problems，退出 1<br>- --out 非法：2<br>- 在非 Git 目录中运行：只记入 notes，退出 0 | LB-EXIT-021；:4657-4762 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §11.5 第 9 条（doctor） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C66 | `LegacyRunOutcomeTest.test_LB_EXIT_009_run_infra_failure_exits_1` | startfail 场景：INFRA_FAILURE，run 退出 1 | LB-EXIT-009、LB-LIFE-019；:3349、3401-3402 | C.4：wait/退出码语义<br>A07：六类之外（01-A05） | §11.5 第 9 条“run 在 INFRA_FAILURE 时退出 1” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C67 | `LegacyRunOutcomeTest.test_LB_EXIT_009_run_timeout_exits_1` | `--timeout 2`：TIMEOUT，run 退出 1；run.json 的 timeout_seconds=2 | LB-EXIT-009、LB-LIFE-016；:691-697、3397-3398 | C.4：超时、wait/退出码语义<br>A07：六类之外（01-A05） | §10 超时；§11.5 第 9 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C68 | `LegacyRunOutcomeTest.test_LB_LIFE_019_timed_out_and_interrupted_resolves_to_timeout` | 经 collect --recover 构造 timed_out 与 interrupted 同为 true 的 run.json：判为 TIMEOUT（先于 CANCELLED），run.json 原样沿用 | LB-LIFE-019、LB-LIFE-023；:3395-3404、3426 | C.4：超时、取消<br>A07：取消 | —（补充判定顺序） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C69 | `LegacyRunOutcomeTest.test_LB_EXIT_031_interrupt_during_pi_is_cancelled_exit_1` | Pi 运行中收到中断（Windows 为 CTRL_BREAK）：CANCELLED，run 退出 1，不输出“已取消。” | LB-EXIT-031、LB-LIFE-017；:571-585、703-706、3349、3399-3400 | C.4：取消<br>A07：取消 | §10 取消；§11.5 第 3、9 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C70 | `LegacyRunOutcomeTest.test_LB_LIFE_035_interrupt_during_prepare_setup_is_prepare_failed_exit_1` | prepare 的 setup 运行中收到中断：<br>- setup 项 failed、interrupted=true、reason 为“被取消”<br>- 状态 PREPARE_FAILED，退出 1（不是 130），不输出“已取消。”，没有 claim/ | LB-LIFE-035、LB-EXIT-008；:3087、3097-3098、3225-3229 | C.4：取消<br>A07：取消 | §10 取消“各阶段 Ctrl+C 的状态”（setup）；§11.5 第 3 条 | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C71 | `LegacyRunOutcomeTest.test_LB_LIFE_035_ctrl_break_in_wait_loop_is_not_handled` | - wait 在轮询中收到 CTRL_BREAK：以 STATUS_CONTROL_C_EXIT 结束，没有任何输出，不是 130（可疑，11.3 第 11 条）<br>- 用 GIT_TRACE2_EVENT 确认已进入循环后才发送 | LB-LIFE-035、LB-EXIT-002；:676、3930-3939、4964-4971 | C.4：取消、wait/退出码语义<br>A07：取消 | §11.5 第 3 条（wait 阶段） | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；条件执行，本次已执行）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（条件执行：skipUnless(IS_WINDOWS)，本次已执行） |
| P4-C72 | `LegacyScopeEndToEndTest.test_LB_GATES_018_e2e_deleted_file_is_out_of_scope_run_still_0` | 端到端，假 pi 删除 README.md：<br>- scope.json 记 out_of_scope“状态 D 不在允许集合”，counts 中 D=1<br>- run 仍为 NEEDS_REVIEW、退出 0（可疑：违规只在 G2 拦下） | LB-GATES-018、LB-GATES-007；:2465-2467、3395-3406 | C.4：范围检查<br>A07：范围 | §10 范围检查“删除越界” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C73 | `LegacyScopeEndToEndTest.test_LB_GATES_017_e2e_case_variant_protected_paths` | 端到端：.Agent/notes.md、sub/Agents.md 记 protected_path | LB-GATES-017；:2459-2461 | C.4：范围检查<br>A07：范围 | §10 范围检查“大小写不同的受保护路径” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |
| P4-C74 | `LegacyScopeEndToEndTest.test_LB_GATES_018_e2e_new_symlink_is_violation` | 端到端：新增符号链接 src/link.py（在允许集合内），changes.json 记 000000→120000，scope.json 记 symlink 违规 | LB-GATES-018、LB-GATES-009；:2468-2470 | C.4：范围检查<br>A07：范围 | §10 范围检查“symlink” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证；条件执行，本次已执行）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925`（不能建符号链接时本用例会 skipTest；本次报 ok，已执行） |
| P4-C75 | `LegacyScopeEndToEndTest.test_LB_GATES_019_e2e_local_commit_head_moved_is_warning` | 端到端：授权 local_commit，stub 运行 commit 场景，violations 为空，warnings 为 head_moved，ok=true | LB-GATES-019；:2488-2491、3367 | C.4：范围检查<br>A07：范围 | §10 范围检查“local_commit 下的 head_moved” | measured / PASS · `bl-01closure-test-legacy-cli-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-cli-20260925` |

### 12.6 test_legacy_events.py：Pi 预检、事件完整性、模型与思考级别证据、用量与费用（34 个方法）

- **取证与结果**：取证 `bl-01final-test-legacy-events-20260925`，归档 `evidence/final/bl-01final-test-legacy-events-20260925/run/stderr.bin`（sha256 9dc7c9843ac13b2bf001439f7011214c8d227136113567a0bbc622c3d9be1010），34 个方法全部 ok。 **收尾轮更新**：收尾取证 `bl-01closure-test-legacy-events-20260926`，归档 `evidence/closure/bl-01closure-test-legacy-events-20260926/run/stderr.bin`（sha256 e5cfa16608d66529963a69a7a10236c294873692b3efe19f5773b0c6bbe70166，与原件相同），34 个方法全部 ok；与上述最终取证的归档输出相比，只有“Ran N tests in …s”一行的耗时不同。
- **端到端部分**：用 legacy_harness 的 make_fake_pi 生成假 pi，经 prepare、run、check、verdict、status、doctor 驱动。
- **白盒部分**：直接调用 pi_preflight（假 pi 仍以子进程运行）、_expects_settled、summarize_events，处理本文件构造的事件文件。
- **未覆盖项**：测试文件的模块说明列出了本文件没有覆盖的相关旧行为，照录在第 10 节与 11.5 节的“P4 更新”中。

| 编号 | 测试方法 | 锁定的旧行为（“可疑”照录测试 docstring） | LB 条目 / 源码行（@a4fa199） | C.4 项 / 01-A07 类别 | 对应缺口 | 本次结果 |
|---|---|---|---|---|---|---|
| P4-E01 | `PreflightRunTests.test_LB_EVENTS_007_thinking_not_in_help_list_blocks_run` | - help 的 thinking 行只列到 medium、合同要求 high 时，预检拒绝，run 退出 3，保持 PREPARED<br>- 假 pi 只被调用 help、version、list-models、auth 四次<br>- help 与 list-models 带资源参数，--version 不带<br>- auth check 的参数为 `auth check --provider P --model M --json`，不带 --no-refresh（doctor 才带） | LB-EVENTS-007、LB-EVENTS-008；:2031-2033、2058、3281-3285 | C.4：实际模型与思考级别证据<br>A07：六类之外 | §10 实际模型与思考级别证据“预检的思考级别不在列表（:2032）”；§11.5 第 6 条 | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E02 | `PreflightRunTests.test_LB_EVENTS_007_unknown_builtin_tool_blocks_run` | help 的 Built-in Tool Names 缺 bash，而合同 tools 含 bash：预检只报这一条，退出 3 | LB-EVENTS-007、LB-EVENTS-008；:2034-2037 | C.4：实际模型与思考级别证据<br>A07：六类之外 | 同上“未知工具（:2037）” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E03 | `PreflightRunTests.test_LB_EVENTS_007_two_part_version_is_unreadable` | --version 输出两段版本“0.87”：报“无法读取 pi 版本：0.87”，退出 3 | LB-EVENTS-001、LB-EVENTS-007、LB-EVENTS-008；:373-375、2038-2043 | C.4：实际模型与思考级别证据<br>A07：六类之外 | 同上“版本不可读（:2043）” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E04 | `PreflightRunTests.test_LB_EVENTS_007_list_models_failure_blocks_run` | --list-models 退出非 0，且 stdout、stderr 都有内容：<br>- problem 取 stderr（strip 后脱敏，截取前 300 个字符）<br>- list-models.txt 记 stdout 在前、stderr 在后<br>- 退出 3 | LB-EVENTS-007、LB-EVENTS-008；:2047-2052 | C.4：实际模型与思考级别证据<br>A07：六类之外 | §11.5 第 6 条“list-models 失败分支” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E05 | `PreflightRunTests.test_LB_EVENTS_007_auth_not_ready_blocks_run` | auth check 退出 1：<br>- problem 全文为“pi auth check 未就绪（退出码 1）：\<stdout>”<br>- auth-check.json 写入 stdout<br>- run 退出 3，保持 PREPARED | LB-EVENTS-007、LB-EVENTS-008；:2056-2062 | C.4：实际模型与思考级别证据<br>A07：六类之外 | 旧测试“auth not ready”只断言非 0，本方法补上精确值 | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E06 | `PreflightRunTests.test_LB_EVENTS_001_low_version_is_note_and_agent_end_completes` | - 版本 0.80.3 低于 MIN_PI_VERSION，只记 note，不阻止运行<br>- expects_agent_settled=false，以 agent_end(willRetry=false) 结束的流判为完整，run 退出 0 | LB-EVENTS-001、LB-EVENTS-011；:50、2044-2046、2312-2315、3288、3316 | C.4：实际模型与思考级别证据<br>A07：六类之外 | 同上“低于 0.80.4（:2045）” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E07 | `PreflightWhiteBoxTests.test_LB_EVENTS_001_expects_settled_from_version_text` | 白盒：_expects_settled 取文本中第一个三段版本。解析不出为 None；≥0.80.4 为 True；其余为 False | LB-EVENTS-001；:50、373-375、3245-3247 | C.4：实际模型与思考级别证据<br>A07：六类之外 | 11.3 第 4 条中 expects_settled 为 False 或 None 的分支（函数层） | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E08 | `PreflightWhiteBoxTests.test_LB_EVENTS_007_version_problem_variants` | 白盒：<br>- 不输出版本：“无法读取 pi 版本：”<br>- 输出 0.87.0 但退出 1：报同一条 problem<br>- 0.80.3：ok，只有 note<br>- 0.80.4：没有 note | LB-EVENTS-007；:2038-2046 | C.4：实际模型与思考级别证据<br>A07：六类之外 | 同上（版本分支） | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E09 | `PreflightWhiteBoxTests.test_LB_EVENTS_005_help_parse_fallbacks_skip_checks` | 白盒：<br>- help 中匹配不到 thinking 行时，静默退回固定列表，high 通过<br>- 没有 Built-in Tool Names 一节时，跳过工具核对<br>- 可疑：两处退回都不留 note | LB-EVENTS-005、LB-EVENTS-007；:1860-1871 | C.4：实际模型与思考级别证据<br>A07：六类之外 | — | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E10 | `PreflightWhiteBoxTests.test_LB_EVENTS_007_missing_required_flags` | 白盒：<br>- help 缺 --no-themes：报“本机 pi 不支持参数：--no-themes”<br>- 缺 --no-context-files：只在 context_files=none 时报 | LB-EVENTS-007；:69-70、2025-2030 | C.4：实际模型与思考级别证据<br>A07：六类之外 | §10 实际模型与思考级别证据“不支持的参数”；§11.5 第 6 条“缺参数” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E11 | `PreflightWhiteBoxTests.test_LB_EVENTS_007_help_nonzero_exit_is_problem` | 白盒：--help 退出 1、stderr 为空时，problem 为“pi --help 退出码 1：”加 stdout 的前 300 个字符；其余步骤照常通过 | LB-EVENTS-007；:2020-2024 | C.4：实际模型与思考级别证据<br>A07：六类之外 | — | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E12 | `PreflightWhiteBoxTests.test_LB_EVENTS_007_no_models_and_no_match_share_one_problem` | 白盒：没有任何模型、没有匹配、同名模型挂在别的 provider 下，三种情形在预检中给出同一条 problem（doctor 才区分） | LB-EVENTS-005、LB-EVENTS-007；:1874-1886、2047-2055 | C.4：实际模型与思考级别证据<br>A07：六类之外 | — | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E13 | `DoctorThinkingTests.test_LB_EVENTS_027_doctor_rejects_unsupported_thinking` | `doctor --thinking ultra`：只多一条“思考级别 ultra 不受本机 pi 支持”，退出 1；auth check 带 --no-refresh | LB-EVENTS-027；:4725-4726、4758-4762 | C.4：实际模型与思考级别证据<br>A07：六类之外 | §10 实际模型与思考级别证据“doctor 的思考级别检查（:4726）”；§11.5 第 6 条 | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E14 | `DoctorThinkingTests.test_LB_EVENTS_027_doctor_thinking_uses_help_list` | doctor 按本机 help 的列表判定，不按固定列表：<br>- help 只到 medium 时，high 被拒（1）<br>- help 多出 ultra 时，ultra 通过（0） | LB-EVENTS-027；:4725-4726 | C.4：实际模型与思考级别证据<br>A07：六类之外 | 同 P4-E13 | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E15 | `EventStreamRunTests.test_LB_EVENTS_013_response_model_differs_is_recorded_not_compared` | responseModel 与要求不同时只记入 response_models，不影响 model_match；ok=true，run 退出 0（可疑：网关换了模型也不会被判为不符） | LB-EVENTS-013；:2323-2328、2361-2362、2376-2378 | C.4：实际模型与思考级别证据<br>A07：六类之外 | §10 实际模型与思考级别证据“responseModel 与要求不同”；§11.5 第 6 条 | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E16 | `EventStreamRunTests.test_LB_EVENTS_013_missing_provider_and_model_fields` | assistant 消息缺 provider/model：<br>- actual_models 记为字符串 "None"，model_match=false<br>- problem 中是元组列表的 repr<br>- 状态 NEEDS_REVIEW，run 退出 1 | LB-EVENTS-013、LB-EVENTS-021；:2324、2328、2361-2362、3348-3349、3401-3404 | C.4：实际模型与思考级别证据<br>A07：六类之外 | 同上“provider/model 字段缺失” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E17 | `EventStreamRunTests.test_LB_EVENTS_017_duplicate_message_end_double_counts_usage` | 最后一条 assistant message_end 重复投递：<br>- 用量与费用重复累计：input/output 2000/400 变为 3000/600，费用 0.00086 变为 0.00129<br>- assistant_messages 从 2 变为 3<br>- ok 仍为 true，run 退出 0（兼容矩阵 D-17） | LB-EVENTS-016、LB-EVENTS-017、LB-EVENTS-020；:2081-2093、2218-2226、2872、4505-4515 | C.4：不在 12 项中（01-A06 的旧对照）<br>A07：六类之外 | §11.5 第 6 条“重复的 message_end” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E18 | `EventStreamRunTests.test_LB_EVENTS_009_empty_stream_is_infra_failure` | 假 pi 不输出任何事件，退出 0：<br>- problems 依次为：空流、没有结束事件、stopReason=None、实际模型 []<br>- token 全为 0；费用 null/unknown；report-status 为 missing<br>- assistant_messages=0，因此 INFRA_FAILURE，run 退出 1 | LB-EVENTS-009、LB-EVENTS-011、LB-EVENTS-018、LB-EVENTS-019、LB-EVENTS-021、LB-EVENTS-030（部分）；:2172、2179-2180、2316-2318、2334-2336、2339-2362、3401-3402 | C.4：不在 12 项中（01-A11 的旧对照）<br>A07：六类之外 | §11.5 第 6 条“空流” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E19 | `EventStreamRunTests.test_LB_EVENTS_009_unterminated_valid_last_line_is_truncated` | 最后一行是合法 JSON（agent_settled）但没有行尾：<br>- complete=true，仍报“最后一行不完整”，ok=false<br>- 状态 NEEDS_REVIEW，run 退出 1 | LB-EVENTS-009、LB-EVENTS-011；:2308、2343-2344 | C.4：不在 12 项中（01-A11 的旧对照）<br>A07：六类之外 | §11.5 第 6 条“截断” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E20 | `EventStreamRunTests.test_LB_EVENTS_021_nonzero_pi_exit_with_complete_events` | 事件完整，Pi 以 5 退出：<br>- collect 与 run 都不看退出码：NEEDS_REVIEW，退出 0<br>- 只有 verdict 的 G1 记“Pi 退出码为 5”；check 之后 PASS 仍被拒（1），状态不变<br>- 可疑：原为源码推断 | LB-EVENTS-021；:3348-3349、3395-3404、4173-4174 | C.4：G0–G6<br>A07：G0–G6（G1） | §11.5 第 6 条“Pi 非零退出但事件完整”；§10 G0–G6 | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E21 | `EventStreamRunTests.test_LB_EVENTS_018_missing_usage_tokens_are_zero_and_cost_unknown` | assistant 消息的 usage 为空对象：<br>- token 各项为 0（不是 null），没有用量完整性字段<br>- 费用 total=null、status=unknown、unpriced_messages=0，不产生 problem，run 退出 0<br>- summary.md 用量印 0、费用写“未知”；status --json 的 tokens 为 0，COST 列为 unknown（D-18、D-19） | LB-EVENTS-018、LB-EVENTS-019、LB-EVENTS-020；:2179-2180、2390-2392、2872、4494-4515 | C.4：不在 12 项中（01-A06 的旧对照）<br>A07：六类之外 | 第 1 节第 6 行“token 缺失输出 0”的补测 | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E22 | `EventStreamRunTests.test_LB_EVENTS_015_stderr_warning_flags` | stderr.log 去掉 ANSI 后匹配四种标记：<br>- custom_model_id、invalid_thinking、unknown_option 各产生一条 problem（run 退出 1，状态 NEEDS_REVIEW）<br>- extension_error 只进 stderr_flags<br>- summary.md 的“复审需要关注”对四者都写“stderr 标记：…” | LB-EVENTS-015；:261-266、2329-2332、2363-2365、2954-2955、2972 | C.4：实际模型与思考级别证据<br>A07：六类之外 | §10 实际模型与思考级别证据“stderr 警告”；§11.5 第 6 条 | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |
| P4-E23 | `SummarizeEventsWhiteBoxTests.test_LB_EVENTS_009_unparseable_lines_are_counted_not_fatal` | 白盒：<br>- CRLF 行尾正常解析；空白行跳过，但占行号<br>- 普通文本、以 BOM 开头的对象、JSON 数组、JSON 字符串、非 UTF-8 字节都记入 parse_error_lines<br>- complete 仍为 true，只有一条“事件流有 5 行无法解析”，ok=false（D-16） | LB-EVENTS-009；:2201-2213、2341-2342、2367-2369 | C.4：不在 12 项中（01-A11 的旧对照）<br>A07：六类之外 | §11.5 第 6 条“不可解析行” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E24 | `SummarizeEventsWhiteBoxTests.test_LB_EVENTS_009_truncated_tail_depends_on_expects_settled` | 白盒：最后一行 agent_settled 只留前一半：<br>- expects_settled 为 True 或 None 时 complete=false<br>- 为 False 时按 agent_end 判为完整，但 ok 仍为 false（D-15） | LB-EVENTS-009、LB-EVENTS-011；:2294-2318、2343-2349 | C.4：不在 12 项中（01-A11 的旧对照）<br>A07：六类之外 | §11.5 第 6 条“截断”；11.3 第 4 条（函数层） | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E25 | `SummarizeEventsWhiteBoxTests.test_LB_EVENTS_011_agent_end_fallback_by_expects_settled` | 白盒：没有 agent_settled、以 agent_end(false) 结束的流：<br>- expects_settled 为 True/None 时不完整；为 False 时完整<br>- False 且最后一个 willRetry=true：不完整<br>- 重试之后再 agent_end(false)：完整<br>- willRetry 缺失或为 null：按假处理 | LB-EVENTS-011；:2294-2298、2312-2315、2346-2349 | C.4：不在 12 项中（01-A11 的旧对照）<br>A07：六类之外 | 11.3 第 4 条（函数层） | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E26 | `SummarizeEventsWhiteBoxTests.test_LB_EVENTS_011_events_after_agent_settled` | 白盒，agent_settled 之后：<br>- 没有 message_start 的 assistant message_end 替换最终消息并累加用量，complete 仍为 true（可疑）<br>- 再来 WORK 事件（四种之一）：不完整<br>- turn_start 之后 agent_end(false)：仍不完整<br>- 再来 agent_settled：恢复完整<br>- agent_end(true)：不改变结果 | LB-EVENTS-011、LB-EVENTS-012；:2214-2215、2299-2311、2319 | C.4：不在 12 项中（01-A11 的旧对照）<br>A07：六类之外 | §11.5 第 6 条“settled 之后的事件”；9.8 核对补充 | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E27 | `SummarizeEventsWhiteBoxTests.test_LB_EVENTS_014_partial_thinking_level_reporting` | 白盒：<br>- 只有最终消息回报 high：provider_reported，不告警<br>- 两条分别回报 low 与 high：problem 只列 ['low']<br>- 都不回报：not_reported，不算 problem | LB-EVENTS-014；:2326-2327、2337、2350-2352、2379-2382 | C.4：实际模型与思考级别证据<br>A07：六类之外 | §10 实际模型与思考级别证据“回报级别与要求一致的正例”；§11.5 第 6 条“部分回报思考级别” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E28 | `SummarizeEventsWhiteBoxTests.test_LB_EVENTS_013_every_assistant_pair_must_match` | 白盒：<br>- 只缺 model：记为 step/None<br>- 一条匹配、一条是别的模型：去重后两项，model_match=false | LB-EVENTS-013；:2323-2328、2361-2362 | C.4：实际模型与思考级别证据<br>A07：六类之外 | 同 P4-E16 | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E29 | `SummarizeEventsWhiteBoxTests.test_LB_EVENTS_017_usage_sources_and_non_sources` | 白盒：<br>- 累加：assistant 与 toolResult 的 message_end、entry_appended{type=usage}、compaction_end.result.usage<br>- 不累加：message_update 顶层、turn_end、agent_end.messages[]<br>- bool 按数值累加<br>- 没有正数费用且 totalTokens>0 的 usage 计入 unpriced_messages<br>- 可疑：各来源是否重叠未核实 | LB-EVENTS-016、LB-EVENTS-017；:2081-2093、2226、2228、2234、2238 | C.4：不在 12 项中（01-A06 的旧对照）<br>A07：六类之外 | §11.5 第 6 条“entry_appended、compaction_end、toolResult 的用量” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E30 | `SummarizeEventsWhiteBoxTests.test_LB_EVENTS_019_cost_status_rules` | 白盒，estimated、partial、unknown 的判定：<br>- 费用为 0 或负数按未定价计<br>- 没有 totalTokens 的 usage 不计入 unpriced<br>- 只有 toolResult 有价时仍为 unknown<br>- 只有 session 一行时 token 为 0、费用 unknown<br>- 费用状态不产生 problem | LB-EVENTS-019、LB-EVENTS-018；:2089-2093、2334-2336、2390-2392 | C.4：不在 12 项中（01-A06 的旧对照）<br>A07：六类之外 | §11.5 第 6 条“partial 费用” | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E31 | `SummarizeEventsWhiteBoxTests.test_LB_EVENTS_019_compaction_cost_status` | 白盒：<br>- 出现 compaction_end（有 assistant、有正数费用）时为 partial，与压缩 usage 是否存在无关<br>- 所有费用都为 0：unknown<br>- 没有 assistant：unknown | LB-EVENTS-017、LB-EVENTS-019；:2235-2238、2334-2336、2390-2392 | C.4：不在 12 项中（01-A06 的旧对照）<br>A07：六类之外 | 同 P4-E30 | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E32 | `SummarizeEventsWhiteBoxTests.test_LB_EVENTS_026_non_numeric_total_tokens_raises` | 白盒：<br>- totalTokens 为非空字符串、且没有正数费用时，summarize_events 抛 TypeError<br>- 空字符串不报错<br>- 端到端后果不在本用例验证 | LB-EVENTS-026；:2092 | C.4：不在 12 项中（01-A06 的旧对照）<br>A07：六类之外 | 11.2 第 3 条（函数层实测） | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E33 | `SummarizeEventsWhiteBoxTests.test_LB_EVENTS_015_stderr_flags_need_existing_file` | 白盒：<br>- 不传 stderr_path 时，不读取同目录的 stderr.log<br>- 路径不存在时不抛异常<br>- 只有 Extension error 时不产生 problem<br>- 非 UTF-8 字节按 replace 读取 | LB-EVENTS-015；:2329-2332、2363-2365 | C.4：实际模型与思考级别证据<br>A07：六类之外 | 同 P4-E22 | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证；白盒）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925`（白盒） |
| P4-E34 | `SourceFactsTests.test_legacy_source_is_locked_revision` | 被测 scripts/pi_dispatch.py 把 CRLF 归一为 LF 之后，摘要等于 a4fa199 的 blob 摘要；原始字节摘要一并记录 | 新增：被测字节核对（没有 LB 条目） | C.4：不在 12 项中<br>A07：回归映射须指明被测提交 | — | measured / PASS · `bl-01closure-test-legacy-events-20260926`（收尾取证）<br>历史：measured / PASS · `bl-01final-test-legacy-events-20260925` |

### 12.7 第 11.2–11.4 节事项的 P4 实测情况

本小节只记录现状有没有实测，不作裁定；各事项的处理仍按第 11.2 节。

| 事项 | P4 实测到的现状（Windows，measured / PASS） | 仍然只是推断、或没有覆盖的部分 |
|---|---|---|
| 11.2 第 3 条：未捕获异常 | 原为源码推断、现已实测的：<br>- branch 在树对象与补丁都缺失时 FileNotFoundError（P4-G19）<br>- Windows 上二次 `collect --recover` 时 *.partial 已存在，FileExistsError（P4-L24）<br>- contract.json 缺失或不是 JSON 时 load_attempt 回溯（P4-G01）<br>另外实测：<br>- meta.json 缺 worktree 键时 evaluate_gates 抛 KeyError（P4-G21）<br>- 非对象 state.json（P4-C36）；Markdown 不是 UTF-8（P4-C49）<br>- Windows 上 `--repo` 指向不存在的路径（P4-C51）<br>- 非数值 totalTokens（P4-E32，函数层） | 仍是推断：<br>- summarize_events 抛异常后 run 停在 COLLECTING、wait 一直返回 3<br>- verdict 的复审报告不是 UTF-8；verdicts/ 中出现非数字文件名<br>- _terminate_tree 期间再收到信号<br>- prepare 在写 meta.json 之前失败<br>- collect 中出现其他异常 |
| 11.2 第 5 条：G0 的范围 | - meta.json 不做哈希校验<br>- contract.json 被改后，G4 按被改的合同判定<br>- contract.json 缺失或损坏时回溯，G0 来不及报告<br>（均为 P4-G01） | — |
| 11.2 第 6 条：G6 的边界 | - worktree 不存在时跳过漂移比较（P4-G16）<br>- 只差行尾且另有新文件时，报成“被修改”（P4-G15，端到端）<br>- 快照按记录的 autocrlf，消息报当前值（P4-G15） | 重新快照会写 Git 对象，未断言 |
| 11.2 第 7 条：检查记录与临时副本 | 空的 checks/NN、aborted 记录成为“最近一次”，使 G3/G4 失败（P4-G18、G14） | prepare_fresh_workspace 失败后不移除临时 worktree；cleanup 不清理 `--keep-workspace` 副本。均未覆盖 |
| 11.2 第 9 条：范围判定的空档 | 符号链接改回普通文件，不报违规也不报警告（P4-C27，白盒） | main_repo_changes 有 diff_error 时 G2 没有备注，未覆盖 |
| 11.2 第 10 条：TaskLock 没有归属校验 | 释放时不核对归属，导致互斥失效：原为顺序模拟探针，现由白盒测试实测（P4-L21） | 真实并发下的竞态、文件系统 mtime 语义与时钟偏差、owner.json 写入时的 FileExistsError，均未覆盖 |
| 11.2 第 11 条：预算语义 | - prepare 与 run 的门槛不同（P4-L11）<br>- 可以准备出超额的 PREPARED（P4-L07）<br>- 按 run.json 的实际用时计入（P4-L08，构造值）<br>- 剩余不足 60 s 的边界（P4-L12、L13） | cost_budget 不参与核算、跨 plan_version 的限额来源，均未覆盖 |
| 11.2 第 12 条：状态转换 | - 已 ABANDONED 的 attempt 仍可凭旧 PASS 标为 INTEGRATED（P4-C61）<br>- 已有结论后可以再次 verdict（P4-G22、G23） | — |
| 11.2 第 13 条：恢复语义 | - 沿用已有 run.json 时，PASS 可以被接受（P4-L23）<br>- 合成的 run.json 中 timed_out=false（P4-L22）<br>- 按 task-id 取编号最大的 attempt（P4-C45） | 未覆盖：“Pi 实际超时后再被恢复”的情形；按 task-id 恢复到错误 attempt 的端到端情形 |
| 11.2 第 15 条：退出码重叠 | - Pi 非零退出但事件完整时，run 退出 0（P4-G04、E20）<br>- Pi 运行期间的中断退出 1（P4-G07、L01、C69）<br>- wait 找不到 git 时退出 3（P4-C44） | — |
| 11.2 第 16 条：用量与费用的零值 | token 缺失为 0，费用为 null/unknown，没有用量完整性字段（P4-E21、E18、E30） | — |
| 11.3 第 4 条：expects_settled | 为 False 与 None 的分支：函数层白盒实测（P4-E07、E24、E25）；run 层的 False 分支实测（P4-E06） | 真实 Pi 的版本与 agent_settled 之间的关系，仍未核实 |
| 11.3 第 5 条：预检的 auth check | 预检的 auth check 不带 --no-refresh，doctor 带（P4-E01、E13，只断言参数） | 是否会刷新或改写凭据，仍未核实 |
| 11.3 第 6 条：live 进度 | 只数紧凑写法，带空格的 JSON 计为 0（P4-C39） | 真实 Pi 的 JSONL 格式，仍未核实 |
| 11.3 第 7 条：settled 之后的事件 | 函数层实测（P4-E26） | 真实 Pi 是否会发出这类事件，仍未核实 |
| 11.3 第 11 条：run_supervised 之外的信号 | Windows 上的 CTRL_BREAK：领取前与 wait 轮询中都以 0xC000013A 结束（P4-L02、C71）；prepare 的 setup 在 run_supervised 内，得到 PREPARE_FAILED（P4-C70） | SIGTERM、SIGHUP，以及 `taskkill /F` 时调度器自身的退出码，均未断言 |
| 11.4 第 2 条：`--repo` 指向不存在的路径 | Windows：NotADirectoryError，退出 1（P4-C51） | POSIX 分支（P4-C52）本机跳过，NOT_RUN |
| 11.4 第 6 条：pid_alive | — | 未覆盖：P4 有意在 Pi 存活时保留 PID 句柄，使结果确定，因此不测 PID 复用与 tasklist 失败 |

### 12.8 第 1 节 3.3 待核验项的 P4 补测索引

| # | 3.3 待核验项 | 第 1 节原来写的缺口 | P4 方法 | P4 之后仍缺 |
|---|---|---|---|---|
| 1 | attempt 编号 | 并发 prepare 撞名重试、跨版本连续编号 | P4-L25（跨 plan_version 连续）、L26（max+1，不生成 0） | 并发 prepare 撞名重试 |
| 2 | 退出码 | main 的 130、argparse 的 2、未捕获异常的 1；run 在 TIMEOUT/CANCELLED/INFRA_FAILURE 时的 1；多数拒绝只断言非 0 | P4-C29（130，白盒）、C46、C47、C49、C66、C67、C69、C53–C65 | 经子进程到达 main 的 130（只有 POSIX 用例 P4-L04，NOT_RUN）；smoke 的拒绝码 |
| 3 | wait 的输出结构 | --timeout<1、PREPARING/COLLECTING 到时、60 s 宽限、state.json 缺失、非对象 state.json、live 片段、“摘要：”行 | P4-C32–C45 | 60 s 宽限上限本身 |
| 4 | G0–G6 | G0、G5 无测试；G3、G6 没有失败路径断言 | P4-G01–G24 | 见第 2 节 P4 列 |
| 5 | Markdown/JSON 冲突 | 只测了“改 JSON、Markdown 不变”一个方向 | P4-C08–C24、C53 | JSON 中 scope 各列表、DoD 编号的不一致 |
| 6 | 缺失的模型、思考级别、token、费用 | token 缺失输出 0、partial 费用、部分回报思考级别、provider/model 字段缺失 | P4-E16、E18、E21、E27、E28、E30、E31 | — |
| 7a | 取消 | 没有信号用例 | P4-G07、L01、L02、C69–C71、L22 | POSIX SIGINT（P4-L03、L04 本机跳过） |
| 7b | 超时 | 超时后 run 退出 1、verdict 的 G1 失败没有断言 | P4-G05、L05、C67、L15 | 检查命令与 setup 的超时 |
| 7c | 已有锁 | 锁等待超时、过期接管、归属缺失 | P4-L18–L21 | 真实并发竞态 |
| 7d | 候选漂移 | verdict 层 G6 漂移失败没有断言 | P4-G13–G15 | — |
| 7e | 补丁不完整 | 补丁缺失、被篡改、sha256 不符、往返失败都没有测试 | P4-G16–G19、C63 | --fresh/mutate 对其余三种情形的拒绝；真实的往返失败 |

### 12.9 本节的限制

- **平台**：只有 Windows 的结果。Linux、macOS 全部 NOT_RUN（01-D10）；P4-L03、L04、C52 三个 POSIX 方法本机跳过。
- **白盒**：白盒方法只证明函数层面的现状，经 CLI 的端到端后果不一定相同。例如 P4-E32 的 TypeError 在 run 中的后果没有验证。
- **构造的状态**：用 `set_state`、改写记录字段构造的状态，不等于真实路径。例如：
  - “往返失败”是把 patch_roundtrip_verified 改为 false，不是真实的 `apply --cached` 失败；
  - COLLECTING 状态由 `set_state` 注入；
  - 预算用例的 wall_seconds 是构造值。
- **PASS 的含义**：measured / PASS 是特征化结论，意思是“a4fa199 现状如此”。它不表示现状正确，也不改变第 11.2 节待裁决事项的状态。
- **测试文件未提交**：测试文件与夹具尚未提交，结论只对第 12.2 节记录的字节成立。 **收尾轮更新**：收尾取证时仍未提交；结论只对 12.2 末尾收尾取证对照表记录的字节成立（legacy_harness 为 c4e87137…）。
- **取证条件的来源**：第 0.5 节中的受控环境条件部分来自规划端记录（source_reported）。 **收尾轮更新**：收尾取证的受控条件（包括 R-01 的 PYTHONPYCACHEPREFIX）同样有一部分只来自操作者记录，见 0.5 末尾。
- **没有 LB 条目的方法**：P4-C01 与 P4-E34 只核对被测字节，不对应 LB 条目；P4-C33、C41、C48、C68 补充了已有 measured 条目的细节，不关闭第 10 节列出的缺口。
- **文档 3.2 的两个字段（完整性审查更新，2026-09-26）**：本节 159 个方法的 input_fixture_ref 与 comparison_projection_revision 都为空：输入在临时区域中现场构造，没有 manifest 条目与封存字节，断言不经过比较投影。它们是旧实现现状的观测，不是文档 6.6 意义上的 fixture 差分，迁移比较时按 NOT_COVERED 处理（9.10.4）。 **收尾轮更新（2026-09-26，R-P12）**：这一判断已被取代：159 个方法的 input_fixture_ref 写成代码内联 fixture，comparison_projection_revision 为 `codekit01-characterization-v1`，见 12.10。它们仍不是 6.6 意义上的差分，七类的状态见 9.10.7。

### 12.10 收尾轮更新：各方法的 input_fixture_ref 与 comparison_projection_revision（裁决 R-P12，2026-09-26）

- **写法**：R-P12 形式 (b)，`inline:<测试文件>::<类>.<方法>@<测试文件 sha256>`。测试文件的 sha256 取收尾取证输入清单的记录值，本次只读核对与工作区字节相同：
  - `tests/test_legacy_gates.py`：d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7
  - `tests/test_legacy_lifecycle.py`：f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd
  - `tests/test_legacy_cli.py`：1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532
  - `tests/test_legacy_events.py`：f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7
- **构造还经过的文件**：
  - 输入由测试代码经公共夹具 `tests/legacy_harness.py` 构造，其当前 sha256 为 c4e871372a35f35c59a76172ccc366a50316c5af9ad3ec4703d1fb6c27d4b974（最终取证时为 3d133d5f…）；
  - 还用到 `tests/stub_pi.py`（96c0d4a5…）、`tests/stub_pi_help.txt`（5668cff3…）与被测的 `scripts/pi_dispatch.py`（a00d6934…），完整摘要见 0.1；
  - R-P12 的引用只记测试文件的摘要。要按字节复现输入，这些文件也必须相同。
- **内联 fixture 固定的范围**：测试代码构造的输入，包括临时仓库、合同、stub 场景、假 pi，以及用 `set_state` 或改写证据文件构造的状态。临时区域的路径每次不同，不在断言之内。超时、信号、进程回收等运行时现象依赖本机的进程调度，是被观察的行为，不是封存的输入字节。
- **comparison_projection_revision**：`codekit01-characterization-v1`，即该方法中的断言集合（R-P12）。没有单独的投影文件，断言集合由测试文件的字节确定。
- **结果**：取自 0.5 末尾所列收尾取证的归档 `evidence/closure/<取证 ID>/run/stderr.bin`（与原件字节相同），按 12.1 的判读规则逐方法匹配：156 个 `... ok`，记 measured / PASS（Windows）；3 个 `... skipped`（POSIX 分支），记 NOT_RUN，不算通过。“方法定义行”是本次在当前字节中读到的 `def` 所在行。
- **性质**：这些是 a4fa199 旧路径的特征化锁定，不是文档 6.6 的新旧路径差分；七类的差分状态见 9.10.7。第 9 节各行对这些方法的引用见 9.10.6。

| 编号 | input_fixture_ref（R-P12 形式 (b)） | comparison_projection_revision | 方法定义行（当前字节） | 收尾取证结果 |
|---|---|---|---|---|
| P4-G01 | `inline:tests/test_legacy_gates.py::G0InputConsistency.test_lb_gates_024_g0_hash_base_and_contract_failures@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:213 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G02 | `inline:tests/test_legacy_gates.py::G1ExecutionComplete.test_lb_gates_025_g1_missing_run_json_and_events_summary@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:277 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G03 | `inline:tests/test_legacy_gates.py::G1ExecutionComplete.test_lb_gates_025_g1_event_problem_nosettle@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:294 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G04 | `inline:tests/test_legacy_gates.py::G1ExecutionComplete.test_lb_gates_025_g1_nonzero_pi_exit_only_caught_by_gate@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:307 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G05 | `inline:tests/test_legacy_gates.py::G1ExecutionComplete.test_lb_life_016_timeout_run_exit_1_and_g1_timeout@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:321 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G06 | `inline:tests/test_legacy_gates.py::G1ExecutionComplete.test_lb_life_011_timeout_flag_cannot_exceed_budget@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:353 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G07 | `inline:tests/test_legacy_gates.py::G1ExecutionComplete.test_lb_life_017_interrupt_during_run_is_cancelled_exit_1@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:369 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G08 | `inline:tests/test_legacy_gates.py::G2Scope.test_lb_gates_026_g2_violation_missing_scope_and_g3_scope_evidence@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:408 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G09 | `inline:tests/test_legacy_gates.py::GateNotes.test_lb_gates_023_notes_never_block_pass_and_g5_constant@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:428 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G10 | `inline:tests/test_legacy_gates.py::G3G4Checks.test_lb_gates_028_g4_partial_coverage_and_stale_candidate@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:461 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G11 | `inline:tests/test_legacy_gates.py::G3G4Checks.test_lb_gates_028_g4_required_check_failed@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:493 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G12 | `inline:tests/test_legacy_gates.py::G3G4Checks.test_lb_gates_027_g3_dod_evidence_on_optional_check@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:512 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G13 | `inline:tests/test_legacy_gates.py::G3G4Checks.test_lb_gates_014_g4_check_modified_candidate@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:530 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G14 | `inline:tests/test_legacy_gates.py::CandidateDrift.test_lb_gates_013_check_refuses_modified_candidate_and_aborted_record_blocks@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:555 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G15 | `inline:tests/test_legacy_gates.py::G6Integrable.test_lb_gates_030_g6_drift_after_record@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:579 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G16 | `inline:tests/test_legacy_gates.py::G6Integrable.test_lb_gates_030_g6_worktree_missing_skips_drift_but_checks_patch@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:641 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G17 | `inline:tests/test_legacy_gates.py::PatchIntegrity.test_lb_gates_006_g6_patch_missing_tampered_sha_and_roundtrip@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:665 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G18 | `inline:tests/test_legacy_gates.py::PatchIntegrity.test_lb_gates_012_fresh_check_and_mutate_refuse_bad_patch@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:692 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G19 | `inline:tests/test_legacy_gates.py::PatchIntegrity.test_lb_gates_035_branch_patch_rebuild_paths@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:721 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G20 | `inline:tests/test_legacy_gates.py::VerdictRules.test_lb_gates_031_state_not_reviewable@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:784 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G21 | `inline:tests/test_legacy_gates.py::VerdictRules.test_lb_gates_032_verdict_rejection_branches@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:807 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G22 | `inline:tests/test_legacy_gates.py::VerdictRules.test_lb_gates_032_waiver_rules_when_all_gates_pass@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:872 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G23 | `inline:tests/test_legacy_gates.py::VerdictRules.test_lb_gates_033_repeat_verdict_increments_number@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:917 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-G24 | `inline:tests/test_legacy_gates.py::VerdictRules.test_lb_gates_033_infra_failure_attempt_is_reviewable@d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` | `codekit01-characterization-v1` | tests/test_legacy_gates.py:960 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-gates-20260926` |
| P4-L01 | `inline:tests/test_legacy_lifecycle.py::CancelTests.test_LB_LIFE_017_ctrl_break_during_pi_run_is_cancelled_exit_1_not_130@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:302 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L02 | `inline:tests/test_legacy_lifecycle.py::CancelTests.test_LB_LIFE_035_ctrl_break_before_claim_kills_dispatcher_without_130@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:354 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L03 | `inline:tests/test_legacy_lifecycle.py::CancelTests.test_LB_LIFE_017_sigint_during_pi_run_is_cancelled_exit_1_posix@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:383 | NOT_RUN（`... skipped`，POSIX 分支）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L04 | `inline:tests/test_legacy_lifecycle.py::CancelTests.test_LB_LIFE_035_sigint_before_claim_exits_130_posix@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:409 | NOT_RUN（`... skipped`，POSIX 分支）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L05 | `inline:tests/test_legacy_lifecycle.py::TimeoutTests.test_LB_LIFE_016_timeout_run_exits_1_and_pass_refused_by_g1@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:438 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L06 | `inline:tests/test_legacy_lifecycle.py::BudgetTests.test_LB_LIFE_012_budget_race_loser_stays_prepared_exit_3@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:490 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L07 | `inline:tests/test_legacy_lifecycle.py::BudgetTests.test_LB_LIFE_012_run_count_precheck_outside_lock_refuses_before_preflight@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:532 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L08 | `inline:tests/test_legacy_lifecycle.py::BudgetTests.test_LB_LIFE_009_wall_budget_counts_actual_wall_seconds_from_run_json@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:566 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L09 | `inline:tests/test_legacy_lifecycle.py::BudgetTests.test_LB_LIFE_009_wall_seconds_null_falls_back_to_reservation@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:592 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L10 | `inline:tests/test_legacy_lifecycle.py::BudgetTests.test_LB_LIFE_010_wall_total_exhausted_refused_by_run_and_prepare@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:616 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L11 | `inline:tests/test_legacy_lifecycle.py::BudgetTests.test_LB_LIFE_011_remaining_wall_under_60s_run_refused_but_prepare_allowed@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:644 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L12 | `inline:tests/test_legacy_lifecycle.py::BudgetTests.test_LB_LIFE_011_remaining_wall_exactly_60s_is_allowed@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:666 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L13 | `inline:tests/test_legacy_lifecycle.py::BudgetTests.test_LB_LIFE_011_remaining_wall_59s_is_refused@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:688 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L14 | `inline:tests/test_legacy_lifecycle.py::BudgetTests.test_LB_LIFE_011_timeout_flag_capped_by_per_attempt_budget@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:708 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L15 | `inline:tests/test_legacy_lifecycle.py::BudgetTests.test_LB_LIFE_011_negative_timeout_flag_becomes_1s@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:728 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L16 | `inline:tests/test_legacy_lifecycle.py::BudgetTests.test_LB_LIFE_011_timeout_flag_capped_by_remaining_total_budget@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:756 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L17 | `inline:tests/test_legacy_lifecycle.py::ExecutorAllowlistTests.test_LB_LIFE_036_allowed_executors_miss_refused_at_prepare_and_run@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:783 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L18 | `inline:tests/test_legacy_lifecycle.py::TaskLockTests.test_LB_LIFE_005_held_task_lock_run_waits_30s_then_exit_3@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:831 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L19 | `inline:tests/test_legacy_lifecycle.py::TaskLockTests.test_LB_LIFE_006_stale_task_lock_taken_over_by_run@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:867 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L20 | `inline:tests/test_legacy_lifecycle.py::TaskLockTests.test_LB_LIFE_005_task_lock_wait_timeout_and_stale_takeover_whitebox@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:885 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L21 | `inline:tests/test_legacy_lifecycle.py::TaskLockTests.test_LB_LIFE_006_task_lock_release_ignores_ownership_whitebox@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:949 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L22 | `inline:tests/test_legacy_lifecycle.py::RecoverTests.test_LB_LIFE_024_recover_refused_while_pi_alive_then_recovers_cancelled@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:999 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L23 | `inline:tests/test_legacy_lifecycle.py::RecoverTests.test_LB_LIFE_023_recover_from_collecting_reuses_run_json_and_can_pass@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:1063 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L24 | `inline:tests/test_legacy_lifecycle.py::RecoverTests.test_LB_LIFE_023_second_recover_with_partial_present_crashes_on_windows@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:1115 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L25 | `inline:tests/test_legacy_lifecycle.py::AttemptNumberTests.test_LB_LIFE_002_first_attempt_is_1_and_only_prepare_advances@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:1150 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-L26 | `inline:tests/test_legacy_lifecycle.py::AttemptNumberTests.test_LB_LIFE_001_number_is_max_plus_one_and_never_zero@f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` | `codekit01-characterization-v1` | tests/test_legacy_lifecycle.py:1196 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-lifecycle-20260926` |
| P4-C01 | `inline:tests/test_legacy_cli.py::LegacySourceTest.test_source_under_test_is_a4fa199@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:77 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C02 | `inline:tests/test_legacy_cli.py::LegacyContractDefaultsTest.test_LB_CONTRACT_003_normalize_empty_contract_defaults@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:100 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C03 | `inline:tests/test_legacy_cli.py::LegacyContractDefaultsTest.test_LB_CONTRACT_003_command_item_defaults_setup_has_no_required@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:117 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C04 | `inline:tests/test_legacy_cli.py::LegacyContractDefaultsTest.test_LB_CONTRACT_004_explicit_null_and_wrong_types_not_filled@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:128 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C05 | `inline:tests/test_legacy_cli.py::LegacyContractDefaultsTest.test_LB_CONTRACT_004_normalize_deep_copies_input@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:143 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C06 | `inline:tests/test_legacy_cli.py::LegacyContractDefaultsTest.test_LB_CONTRACT_005_unserializable_raw_wrapped_as_structure_error@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:149 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C07 | `inline:tests/test_legacy_cli.py::LegacyContractDefaultsTest.test_LB_CONTRACT_003_provider_model_have_no_default_and_validate_passes@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:157 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C08 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_017_md_budget_changed_json_unchanged@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:199 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C09 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_md_identity_risk_level_changed@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:204 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C10 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_md_thinking_changed@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:209 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C11 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_md_integration_actions_changed@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:214 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C12 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_017_md_dependency_changes_changed@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:220 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C13 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_017_md_validation_argv_changed@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:225 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C14 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_017_md_validation_line_removed@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:230 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C15 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_017_md_forbidden_path_removed@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:235 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C16 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_018_md_only_additions_and_dod_text_not_compared@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:240 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C17 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_fullwidth_colon_identity_value_reads_as_none@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:253 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C18 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_fullwidth_colon_action_list_reads_as_missing@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:262 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C19 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_017_fullwidth_colon_dependency_changes_not_recognised@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:268 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C20 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_identity_value_note_is_stripped@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:273 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C21 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_035_risk_level_upper_in_json_lower_in_md@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:277 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C22 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_035_risk_level_upper_in_both@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:285 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C23 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_016_risk_level_upper_in_md_only@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:291 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C24 | `inline:tests/test_legacy_cli.py::LegacyMarkdownJsonConsistencyTest.test_LB_CONTRACT_015_title_capture_stops_at_first_foreign_char@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:296 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C25 | `inline:tests/test_legacy_cli.py::LegacyScopeInProcessTest.test_LB_GATES_018_deleted_file_outside_allowed_deleted_is_out_of_scope@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:328 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C26 | `inline:tests/test_legacy_cli.py::LegacyScopeInProcessTest.test_LB_GATES_017_protected_paths_ignore_case_scope_lists_do_not@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:344 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C27 | `inline:tests/test_legacy_cli.py::LegacyScopeInProcessTest.test_LB_GATES_018_new_symlink_is_violation_symlink_to_file_is_silent@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:358 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C28 | `inline:tests/test_legacy_cli.py::LegacyScopeInProcessTest.test_LB_GATES_019_head_moved_is_warning_only_with_local_commit@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:379 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C29 | `inline:tests/test_legacy_cli.py::LegacyMainInProcessTest.test_LB_EXIT_002_main_maps_keyboard_interrupt_to_130@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:420 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C30 | `inline:tests/test_legacy_cli.py::LegacyMainInProcessTest.test_LB_EXIT_002_main_maps_dispatch_error_to_its_code@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:424 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C31 | `inline:tests/test_legacy_cli.py::LegacyMainInProcessTest.test_LB_EXIT_002_main_does_not_catch_other_exceptions@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:429 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C32 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_023_wait_timeout_below_one_is_usage_2@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:503 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C33 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_023_wait_unknown_attempt_reported_before_timeout_check@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:513 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C34 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_024_wait_missing_state_json_is_unknown_exit_1@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:521 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C35 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_024_wait_null_missing_key_or_unknown_state_exit_1@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:530 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C36 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_030_wait_non_object_state_json_traceback_exit_1@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:546 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C37 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_024_wait_preparing_and_collecting_time_out_with_3_without_live@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:559 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C38 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_025_wait_running_time_out_appends_live_fragment@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:572 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C39 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_025_live_progress_variants_via_status_json@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:581 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C40 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_024_wait_terminal_prints_summary_line@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:609 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C41 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_026_wait_exit_0_for_failed_terminal_state_without_summary@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:617 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C42 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_024_wait_prepared_returns_3_after_min_60_timeout@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:630 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C43 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_024_wait_prepared_grace_keeps_polling@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:644 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C44 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_026_wait_git_missing_is_3@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:660 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C45 | `inline:tests/test_legacy_cli.py::LegacyWaitTest.test_LB_EXIT_038_resolve_by_task_id_picks_latest_attempt_without_meta@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:672 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C46 | `inline:tests/test_legacy_cli.py::LegacyMainEntryTest.test_LB_EXIT_002_no_subcommand_prints_help_to_stdout_exit_2@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:692 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C47 | `inline:tests/test_legacy_cli.py::LegacyMainEntryTest.test_LB_EXIT_003_argparse_usage_errors_exit_2_without_error_prefix@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:699 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C48 | `inline:tests/test_legacy_cli.py::LegacyMainEntryTest.test_LB_EXIT_003_version_exit_0@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:722 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C49 | `inline:tests/test_legacy_cli.py::LegacyMainEntryTest.test_LB_EXIT_002_uncaught_exception_traceback_exit_1@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:727 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C50 | `inline:tests/test_legacy_cli.py::LegacyMainEntryTest.test_LB_EXIT_029_repo_not_a_repository_is_2@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:741 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C51 | `inline:tests/test_legacy_cli.py::LegacyMainEntryTest.test_LB_EXIT_029_repo_missing_path_windows_traceback_1@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:749 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C52 | `inline:tests/test_legacy_cli.py::LegacyMainEntryTest.test_LB_EXIT_029_repo_missing_path_posix_reported_as_git_missing_3@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:761 | NOT_RUN（`... skipped`，POSIX 分支）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C53 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_EXIT_008_prepare_contract_invalid_is_2_without_attempt@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:779 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C54 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_EXIT_008_prepare_runs_not_ignored_is_3@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:791 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C55 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_EXIT_035_prepare_env_conflict_2_precedes_allowlist_3@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:798 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C56 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_EXIT_009_run_refusals_keep_prepared@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:812 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C57 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_EXIT_010_collect_refusals_2_and_live_pid_3@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:838 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C58 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_EXIT_014_verdict_on_unreviewable_state_is_3@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:856 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C59 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_EXIT_014_verdict_usage_2_and_gate_refusal_1@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:862 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C60 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_EXIT_015_branch_without_passing_verdict_is_3@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:897 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C61 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_EXIT_016_mark_refusal_codes@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:906 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C62 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_EXIT_017_cleanup_refusal_codes@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:946 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C63 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_GATES_037_cleanup_refuses_when_candidate_patch_tampered@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:978 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C64 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_EXIT_012_baseline_refusal_codes@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:1011 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C65 | `inline:tests/test_legacy_cli.py::LegacyRefusalCodesTest.test_LB_EXIT_021_doctor_codes@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:1035 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C66 | `inline:tests/test_legacy_cli.py::LegacyRunOutcomeTest.test_LB_EXIT_009_run_infra_failure_exits_1@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:1062 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C67 | `inline:tests/test_legacy_cli.py::LegacyRunOutcomeTest.test_LB_EXIT_009_run_timeout_exits_1@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:1069 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C68 | `inline:tests/test_legacy_cli.py::LegacyRunOutcomeTest.test_LB_LIFE_019_timed_out_and_interrupted_resolves_to_timeout@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:1086 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C69 | `inline:tests/test_legacy_cli.py::LegacyRunOutcomeTest.test_LB_EXIT_031_interrupt_during_pi_is_cancelled_exit_1@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:1109 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C70 | `inline:tests/test_legacy_cli.py::LegacyRunOutcomeTest.test_LB_LIFE_035_interrupt_during_prepare_setup_is_prepare_failed_exit_1@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:1134 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C71 | `inline:tests/test_legacy_cli.py::LegacyRunOutcomeTest.test_LB_LIFE_035_ctrl_break_in_wait_loop_is_not_handled@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:1165 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C72 | `inline:tests/test_legacy_cli.py::LegacyScopeEndToEndTest.test_LB_GATES_018_e2e_deleted_file_is_out_of_scope_run_still_0@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:1224 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C73 | `inline:tests/test_legacy_cli.py::LegacyScopeEndToEndTest.test_LB_GATES_017_e2e_case_variant_protected_paths@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:1238 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C74 | `inline:tests/test_legacy_cli.py::LegacyScopeEndToEndTest.test_LB_GATES_018_e2e_new_symlink_is_violation@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:1250 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-C75 | `inline:tests/test_legacy_cli.py::LegacyScopeEndToEndTest.test_LB_GATES_019_e2e_local_commit_head_moved_is_warning@1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` | `codekit01-characterization-v1` | tests/test_legacy_cli.py:1273 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-cli-20260926` |
| P4-E01 | `inline:tests/test_legacy_events.py::PreflightRunTests.test_LB_EVENTS_007_thinking_not_in_help_list_blocks_run@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:235 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E02 | `inline:tests/test_legacy_events.py::PreflightRunTests.test_LB_EVENTS_007_unknown_builtin_tool_blocks_run@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:265 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E03 | `inline:tests/test_legacy_events.py::PreflightRunTests.test_LB_EVENTS_007_two_part_version_is_unreadable@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:280 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E04 | `inline:tests/test_legacy_events.py::PreflightRunTests.test_LB_EVENTS_007_list_models_failure_blocks_run@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:291 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E05 | `inline:tests/test_legacy_events.py::PreflightRunTests.test_LB_EVENTS_007_auth_not_ready_blocks_run@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:310 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E06 | `inline:tests/test_legacy_events.py::PreflightRunTests.test_LB_EVENTS_001_low_version_is_note_and_agent_end_completes@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:326 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E07 | `inline:tests/test_legacy_events.py::PreflightWhiteBoxTests.test_LB_EVENTS_001_expects_settled_from_version_text@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:355 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E08 | `inline:tests/test_legacy_events.py::PreflightWhiteBoxTests.test_LB_EVENTS_007_version_problem_variants@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:367 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E09 | `inline:tests/test_legacy_events.py::PreflightWhiteBoxTests.test_LB_EVENTS_005_help_parse_fallbacks_skip_checks@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:387 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E10 | `inline:tests/test_legacy_events.py::PreflightWhiteBoxTests.test_LB_EVENTS_007_missing_required_flags@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:406 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E11 | `inline:tests/test_legacy_events.py::PreflightWhiteBoxTests.test_LB_EVENTS_007_help_nonzero_exit_is_problem@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:423 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E12 | `inline:tests/test_legacy_events.py::PreflightWhiteBoxTests.test_LB_EVENTS_007_no_models_and_no_match_share_one_problem@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:437 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E13 | `inline:tests/test_legacy_events.py::DoctorThinkingTests.test_LB_EVENTS_027_doctor_rejects_unsupported_thinking@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:450 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E14 | `inline:tests/test_legacy_events.py::DoctorThinkingTests.test_LB_EVENTS_027_doctor_thinking_uses_help_list@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:472 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E15 | `inline:tests/test_legacy_events.py::EventStreamRunTests.test_LB_EVENTS_013_response_model_differs_is_recorded_not_compared@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:504 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E16 | `inline:tests/test_legacy_events.py::EventStreamRunTests.test_LB_EVENTS_013_missing_provider_and_model_fields@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:521 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E17 | `inline:tests/test_legacy_events.py::EventStreamRunTests.test_LB_EVENTS_017_duplicate_message_end_double_counts_usage@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:548 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E18 | `inline:tests/test_legacy_events.py::EventStreamRunTests.test_LB_EVENTS_009_empty_stream_is_infra_failure@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:578 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E19 | `inline:tests/test_legacy_events.py::EventStreamRunTests.test_LB_EVENTS_009_unterminated_valid_last_line_is_truncated@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:603 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E20 | `inline:tests/test_legacy_events.py::EventStreamRunTests.test_LB_EVENTS_021_nonzero_pi_exit_with_complete_events@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:621 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E21 | `inline:tests/test_legacy_events.py::EventStreamRunTests.test_LB_EVENTS_018_missing_usage_tokens_are_zero_and_cost_unknown@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:646 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E22 | `inline:tests/test_legacy_events.py::EventStreamRunTests.test_LB_EVENTS_015_stderr_warning_flags@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:675 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E23 | `inline:tests/test_legacy_events.py::SummarizeEventsWhiteBoxTests.test_LB_EVENTS_009_unparseable_lines_are_counted_not_fatal@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:710 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E24 | `inline:tests/test_legacy_events.py::SummarizeEventsWhiteBoxTests.test_LB_EVENTS_009_truncated_tail_depends_on_expects_settled@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:730 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E25 | `inline:tests/test_legacy_events.py::SummarizeEventsWhiteBoxTests.test_LB_EVENTS_011_agent_end_fallback_by_expects_settled@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:749 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E26 | `inline:tests/test_legacy_events.py::SummarizeEventsWhiteBoxTests.test_LB_EVENTS_011_events_after_agent_settled@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:776 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E27 | `inline:tests/test_legacy_events.py::SummarizeEventsWhiteBoxTests.test_LB_EVENTS_014_partial_thinking_level_reporting@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:815 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E28 | `inline:tests/test_legacy_events.py::SummarizeEventsWhiteBoxTests.test_LB_EVENTS_013_every_assistant_pair_must_match@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:842 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E29 | `inline:tests/test_legacy_events.py::SummarizeEventsWhiteBoxTests.test_LB_EVENTS_017_usage_sources_and_non_sources@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:863 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E30 | `inline:tests/test_legacy_events.py::SummarizeEventsWhiteBoxTests.test_LB_EVENTS_019_cost_status_rules@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:903 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E31 | `inline:tests/test_legacy_events.py::SummarizeEventsWhiteBoxTests.test_LB_EVENTS_019_compaction_cost_status@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:947 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E32 | `inline:tests/test_legacy_events.py::SummarizeEventsWhiteBoxTests.test_LB_EVENTS_026_non_numeric_total_tokens_raises@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:990 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E33 | `inline:tests/test_legacy_events.py::SummarizeEventsWhiteBoxTests.test_LB_EVENTS_015_stderr_flags_need_existing_file@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:1002 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
| P4-E34 | `inline:tests/test_legacy_events.py::SourceFactsTests.test_legacy_source_is_locked_revision@f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` | `codekit01-characterization-v1` | tests/test_legacy_events.py:1029 | measured / PASS（`... ok`）· `bl-01closure-test-legacy-events-20260926` |
