# 01 最终取证归档索引（evidence/final）

本目录收的是 01 P4 的最终取证：实施完成后，在受控环境里对旧自测和 01 新增的 7 个测试文件各取证一次，共 8 个。

- 原件位置：`.agent/baseline/01-final/<capture-id>/`。该目录被 Git 忽略，只读，不提交。
- 归档方式：用 `python scripts/codekit/baseline.py archive .agent/baseline/01-final/<capture-id> --dest docs/themis-tally-v2/01-baseline/evidence/final` 逐个生成，归档时设了 `PYTHONDONTWRITEBYTECODE=1`。
- 脱敏规则：`redact-v2`。
- 工具版本：取证与归档都用 `scripts/codekit/baseline.py`，sha256 `dbb08466778db639966336902653525fa26a4f9f9152c5827594ea9313e49ce8`。归档 manifest 的 `tool.sha256` 和各 `capture.json` 的 `tool.sha256` 都是这个值。
- 监督器：`scripts/pi_dispatch.py` 的 `run_supervised`，module_sha256 `a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4`，tool_version 2.2.2。
- 基线提交：`a4fa199b0e5bdc658215765ee7558b9fe6723940`（sha1）。

本索引由规划端子代理手写，本身不是取证产物。表中的数字都取自同目录下的归档文件：`capture.json`、`archive-manifest.json`、`run/*.bin`。每一行都能按 capture-id 追到对应文件。

本目录与其他取证的关系：

- 实施前基线见 `../bl-01t1-legacy-20260925/`。
- 中间一轮取证在 `.agent/baseline/01-P4/`，已被本目录取代。原件保留，没有归档。
- 本目录与 `INDEX.md` 都是在 8 次取证结束后才创建的，不在任何一次取证的输入清单里。

修订记录：

- 初版（20570 字节，sha256 `7d4dbcf0b863b821b236eb359bb5de54e60cb102d459af2abdf97e3c914dfbe4`）：归档子代理编写。基线报告修订 3、4 与 `acceptance.md` 引用的是这一版。
- 2026-09-26 对抗性核验返工（规划端子代理）：只改本文件，没有改动任何归档文件。
  - 第 1 节：更正“全部 672 个归档文件的 sha256 都与 `archived_sha256` 一致”这句计数，并附勘误说明；
  - 第 5.2 节：新增 5.2.1，逐字转录操作者记录 `final2-captures.txt`，并写明哪些条件只来自派发说明；
  - 其余各节（表格、摘要、行号、跳过用例、残留检查）没有改动。第 6 节的残留检查针对的是 8 个归档目录，不含本文件；本次新增的文字不含本机用户名、仓库路径、会话 ID 或主机名（写入后按这些类别检查过本文件）。

## 1. 归档结果与完整性

| capture-id | archive 退出码 | manifest 条目数（含 capture.json） | 目录内文件数（含 manifest） | capture.json 列出的文件数 | 摘要不符数 | `unredacted_files` | 脱敏后字节有变的文件数 | `archive-manifest.json` sha256 |
|---|---|---|---|---|---|---|---|---|
| `bl-01final-test-dispatch-20260925` | 0 | 83 | 84 | 82 | 0 | `[]` | 5 | `9b13a01dfd07d654be0b8b2c79c1d3accb4a823bfee6df5afae76a5a886c3ded` |
| `bl-01final-test-protocols-20260925` | 0 | 83 | 84 | 82 | 0 | `[]` | 5 | `3707e1cd88fe05c113eaf3acca35f22190b6f525d508c99d5c2fe782df4c3908` |
| `bl-01final-test-codekit01-fixtures-20260925` | 0 | 83 | 84 | 82 | 0 | `[]` | 5 | `6406500f42cae518e8dce7d0616455a8cb4744a2a1af3043146548fab2599222` |
| `bl-01final-test-baseline-tool-20260925` | 0 | 83 | 84 | 82 | 0 | `[]` | 5 | `f9554817796edf2369e86b31c326eb85ae6b2f55cf1be099599ed5e7a50a0ce4` |
| `bl-01final-test-legacy-gates-20260925` | 0 | 83 | 84 | 82 | 0 | `[]` | 5 | `3508c6012489e573c246a141b60293252b9804c1d5b457961eaa16d5712a61e2` |
| `bl-01final-test-legacy-lifecycle-20260925` | 0 | 83 | 84 | 82 | 0 | `[]` | 5 | `c37c4f4866d8813a0cb0b6ff718c6d396568d1d819b5333ff0811ddbce3d187a` |
| `bl-01final-test-legacy-cli-20260925` | 0 | 83 | 84 | 82 | 0 | `[]` | 5 | `5794ef531a6df45474f9639945f4260b7069e602f83c26369ec302599805cc59` |
| `bl-01final-test-legacy-events-20260925` | 0 | 83 | 84 | 82 | 0 | `[]` | 5 | `4042d5cb7364cb0ed64e21655f5062e3c1124a494da3955b8c8d5d40120f5bba` |

- **归档工具控制台输出**：每个取证都是 `files: 83  redacted_changed: 5  raw_copies: 0  rule: redact-v2`。
- **脱敏改动**：每个归档都改动了同样的 5 个文件。
  - `capture.json`：`<PYDIR>` ×1。
  - `pre/environment.json`、`post/environment.json`：各 `<PYDIR>` ×1。
  - `pre/02-rev-parse-toplevel.stdout.bin`、`post/02-rev-parse-toplevel.stdout.bin`：各 `<REPO>` ×1。
- **run/ 下的文件没有改动**：`run/stdout.bin` 和 `run/stderr.bin` 脱敏前后字节相同。三处摘要一致：
  - 归档文件的实际 sha256；
  - manifest 中的 `original_sha256` 与 `archived_sha256`；
  - `capture.json` 中 `run.stdout.sha256` 与 `run.stderr.sha256`。
- **归档后逐一核对**：8 份 manifest 共列出 664 个文件（每份 83 个），它们的 sha256 都与各自 manifest 的 `archived_sha256` 一致。目录中共有 672 个文件，多出的 8 个是 `archive-manifest.json` 本身：manifest 不列出自身，这 8 个文件没有 `archived_sha256` 可比，它们的 sha256 只记在上表最后一列（由本索引与基线报告手工记录）。每个 manifest 的 `files` 都没有 `listed_in_capture_json=false` 的条目。
  - 勘误（2026-09-26，对抗性核验返工）：本句原写“全部 672 个归档文件的 sha256 都与各自 manifest 的 `archived_sha256` 一致”，把不自列的 8 份 manifest 也算了进去，已按上文更正。更正时重算（measured）：664 个条目的 `archived_sha256` 与归档文件一致，`original_sha256` 与 `.agent/baseline/01-final/` 原件一致；8 份 `archive-manifest.json` 的 sha256 与上表最后一列一致。

## 2. 被测命令与结果（项目验证）

下表 8 个取证的被测对象都是本仓库的代码，全部属于**项目验证**。

- 01 文档附录 B 参考代码的验证是另一栏，证据在 `../reference-appendix-b-windows/`，本目录不含（01-A16）。
- 各行的“结果汇总行”是 `run/*.bin` 中的原文，括号内是文件和行号。
- 退出码、耗时、`timed_out`、`baseline_consistent`、`drift` 取自该取证的 `capture.json`，字段依次为：
  - `run.returncode`；
  - `run.duration_seconds`，单位为秒；
  - `run.timed_out`；
  - `comparison.baseline_consistent`；
  - `comparison.drift`。

| capture-id | 被测命令（cwd=仓库根） | 结果汇总行（原文） | 退出码 | 耗时 (s) | timed_out | baseline_consistent | drift |
|---|---|---|---|---|---|---|---|
| `bl-01final-test-dispatch-20260925` | `python tests/test_dispatch.py` | `256 checks, 0 failed`（run/stdout.bin:282） | 0 | 216.828 | false | true | `[]` |
| `bl-01final-test-protocols-20260925` | `python tests/test_protocols.py` | `Ran 324 tests in 4.075s`（run/stderr.bin:651）；`OK (skipped=4)`（run/stderr.bin:653） | 0 | 4.437 | false | true | `[]` |
| `bl-01final-test-codekit01-fixtures-20260925` | `python tests/test_codekit01_fixtures.py` | `Ran 36 tests in 7.771s`（run/stderr.bin:3）；`OK`（run/stderr.bin:5） | 0 | 7.969 | false | true | `[]` |
| `bl-01final-test-baseline-tool-20260925` | `python tests/test_baseline_tool.py` | `Ran 40 tests in 51.525s`（run/stderr.bin:43）；`OK`（run/stderr.bin:45） | 0 | 51.844 | false | true | `[]` |
| `bl-01final-test-legacy-gates-20260925` | `python tests/test_legacy_gates.py` | `Ran 24 tests in 118.065s`（run/stderr.bin:52）；`OK`（run/stderr.bin:54） | 0 | 118.265 | false | true | `[]` |
| `bl-01final-test-legacy-lifecycle-20260925` | `python tests/test_legacy_lifecycle.py` | `Ran 26 tests in 128.438s`（run/stderr.bin:56）；`OK (skipped=2)`（run/stderr.bin:58） | 0 | 128.672 | false | true | `[]` |
| `bl-01final-test-legacy-cli-20260925` | `python tests/test_legacy_cli.py` | `Ran 75 tests in 84.147s`（run/stderr.bin:153）；`OK (skipped=1)`（run/stderr.bin:155） | 0 | 84.265 | false | true | `[]` |
| `bl-01final-test-legacy-events-20260925` | `python tests/test_legacy_events.py` | `Ran 34 tests in 45.589s`（run/stderr.bin:71）；`OK`（run/stderr.bin:73） | 0 | 45.734 | false | true | `[]` |

8 个取证的 `capture.json` 还有以下共同记录：

- 取证过程本身：
  - `execution_status=complete`，`incomplete_reasons=[]`；
  - `run.executed=true`，`run.interrupted=false`，`run.stray_processes=false`；
  - `run.kill_method=job-object`，`run.stdin=devnull`；
  - `run.interpretation=not_evaluated`：取证工具不判定被测命令是否通过。本表的结论来自上面的汇总行和退出码。
- 前后比较：
  - `comparison.unavailable=[]`，`comparison.observations=[]`，`comparison.input_manifest_closure_sha256_equal=true`；
  - `comparison.checked` 覆盖 head、object_format、porcelain_raw_bytes、input_manifest_sha256、diff_unstaged_bytes、diff_staged_bytes、ls_files_bytes、head_object_type、git_version、git_config、bash_version_first_line、environment_facts_sha256。
- 8 次取证前采样的工作区状态完全相同：
  - HEAD 为 `a4fa199b0e5bdc658215765ee7558b9fe6723940`；
  - porcelain 有 319 项，sha256 为 `a84e68334b1f94e9c69694118c5994b2847a4bc00038466dbcf43913d3dc6088`；
  - 输入清单 373 项，closure_sha256 为 `2d8f2f71d6514b08e1f331009245d97e5f51a50a02f034651f87e17e2fa70b7d`。
- 本组取证之间工作区没有变化。

## 3. 输出文件与取证记录的摘要

| capture-id | run/stdout.bin sha256 | run/stderr.bin sha256 | 原件 capture.json sha256（`source_capture_json_sha256`） | run 起止（UTC） |
|---|---|---|---|---|
| `bl-01final-test-dispatch-20260925` | `f40586e2376e2361bc962878059d732b95c2c8cb0f79d48c3fd069fc37e1080e`（13423 字节） | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `6d18f459c86cec60a84c458ea2c57cddc925b3a3e4981d0731f9e8a7a1a9ced8` | 2026-09-26T04:16:50.453876Z → 04:20:27.285669Z |
| `bl-01final-test-protocols-20260925` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `1f30be24ba3b38c4b56e54a01a076e74b630c5cdcb89c4eeb975e84211e9de36`（73321 字节） | `5433610acdc37b9228de047840be97c7ee0c37b76b7c18292cf262161c689904` | 2026-09-26T04:20:30.846233Z → 04:20:35.293611Z |
| `bl-01final-test-codekit01-fixtures-20260925` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `689389be7fbd34cdcb40ebe00a954113c293ed9384157b991f72cfee60aa8261`（140 字节） | `22486c7ec68bdd460d4ad0fb729e0895516f3812df84a4058b886b0db68b2a20` | 2026-09-26T04:20:38.113586Z → 04:20:46.089919Z |
| `bl-01final-test-baseline-tool-20260925` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `1cf45a96ef531b7df6f8eec633302127c9e77186ae44a6670f8fe1509840eb4a`（5064 字节） | `f490d6524a6b177919dc38c3f1ab19e142ef03d26e27099f8a7588398175519e` | 2026-09-26T04:20:49.428520Z → 04:21:41.272929Z |
| `bl-01final-test-legacy-gates-20260925` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `80d945cd781a868e666fbfb89e2c5a39edd527291d77e92f96d63ac3b4cdffe1`（6459 字节） | `f8a58dcf62ae8b8919adb7f5f647ec7c6bae5656cba3030c17d0a573fae82439` | 2026-09-26T04:21:44.142372Z → 04:23:42.418930Z |
| `bl-01final-test-legacy-lifecycle-20260925` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `45e9ec9f0b232815ebbd0c9159090c1f3d10aa95cd65e8d523ab8c2812b1a69b`（7809 字节） | `e62c6798e9ee63b015a79aa489d0cd1378ecee2a8a5701141552568b5ad3167c` | 2026-09-26T04:23:45.280345Z → 04:25:53.953610Z |
| `bl-01final-test-legacy-cli-20260925` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `484493ae4f7412a21b7c473fbfcbb663d891ff5a0e3575943366e242c4440c8c`（19861 字节） | `e396bca1bf75e72d51e585e6decbf4e234907965e96bb6094a34fb900502aa23` | 2026-09-26T04:25:56.605996Z → 04:27:20.864208Z |
| `bl-01final-test-legacy-events-20260925` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `9dc7c9843ac13b2bf001439f7011214c8d227136113567a0bbc622c3d9be1010`（8739 字节） | `941b77004022405486d4e6148e9e1c2916400e062999662c29391f5cf2adb4ad` | 2026-09-26T04:27:23.559966Z → 04:28:09.284115Z |

`e3b0c442…b855` 是空内容的 sha256。

## 4. 用例级可追溯性

### 4.1 各套件能追到哪一级

逐条计数都来自该取证的 `run/*.bin`。

- **test_protocols、test_baseline_tool、test_legacy_gates、test_legacy_lifecycle、test_legacy_cli、test_legacy_events**：
  - 这 6 个套件用 unittest 的逐条输出。每个用例在 `run/stderr.bin` 里有一行“`<方法名> (__main__.<类>.<方法名>)` + 说明 + `... ok` / `... skipped`”，可以按方法名检索。
  - 逐条计数与汇总行一致，`... FAIL` 与 `... ERROR` 都是 0：

    | 套件 | ok | skipped | 合计 |
    |---|---|---|---|
    | protocols | 320 | 4 | 324 |
    | baseline_tool | 40 | 0 | 40 |
    | legacy_gates | 24 | 0 | 24 |
    | legacy_lifecycle | 24 | 2 | 26 |
    | legacy_cli | 74 | 1 | 75 |
    | legacy_events | 34 | 0 | 34 |

- **test_codekit01_fixtures**：输出是非逐条模式，`run/stderr.bin` 第 1 行只有 36 个 `.`，不含方法名。
  - 运行型证据只能证明 36 个用例运行且没有失败或跳过：点号中没有 `s`、`F`、`E`，汇总行为 `OK`。
  - `tests/test_codekit01_fixtures.py` 中有 36 个 `def test`。这个对应是静态核对，不是运行记录。
  - 要把某个方法单独判为 PASS，需要以逐条模式重新取证。
- **test_dispatch**：这是自带的检查脚本，不是 unittest。
  - `run/stdout.bin` 中有 256 行 `PASS <描述>`，没有以 `FAIL` 开头的行。
  - 每条检查以描述文字标识，没有方法名。

### 4.2 跳过的用例（未运行，不算通过）

方法名与跳过原因都摘自 `run/stderr.bin` 原文。

| capture-id | 方法 | 跳过原因（原文） |
|---|---|---|
| `bl-01final-test-protocols-20260925` | `SnapshotTests.test_F017_machine_path_projection_belongs_to_02` | 01-D05：配置语义投影归 02，F017 由 02 验收；此处未测试，不代表通过 |
| `bl-01final-test-protocols-20260925` | `PhysicalPathTests.test_F029_replacement_after_check` | 01-D06：01 只提供词法校验与静态解析，不实现抗 TOCTOU 的受控访问；F029 由后续访问实现模块验收，此处未测试，不代表通过 |
| `bl-01final-test-protocols-20260925` | `PhysicalPathTests.test_F030_fifo_device_hardlink` | 01-D06：01 不实现文件类型与硬链接受控读写；F030 由后续访问实现模块验收，此处未测试，不代表通过 |
| `bl-01final-test-protocols-20260925` | `SchemaFileTests.test_A09_jsonschema_metaschema_optional` | 未安装 jsonschema，未做元校验（本机不得安装依赖，见 01-L01） |
| `bl-01final-test-legacy-lifecycle-20260925` | `CancelTests.test_LB_LIFE_017_sigint_during_pi_run_is_cancelled_exit_1_posix` | 只在 POSIX 上运行：SIGINT 到达调度器的语义（KeyboardInterrupt/_Interrupted）；Windows 用 CTRL_BREAK 用例 |
| `bl-01final-test-legacy-lifecycle-20260925` | `CancelTests.test_LB_LIFE_035_sigint_before_claim_exits_130_posix` | 只在 POSIX 上运行：SIGINT 到达调度器的语义（KeyboardInterrupt/_Interrupted）；Windows 用 CTRL_BREAK 用例 |
| `bl-01final-test-legacy-cli-20260925` | `LegacyMainEntryTest.test_LB_EXIT_029_repo_missing_path_posix_reported_as_git_missing_3` | POSIX 分支；本机 Windows 的结果见上一用例（本次 NOT_RUN） |

## 5. 受控环境

来源不同，证据等级也不同，下面分三类列出。

### 5.1 取证工具自己记录的事实（运行型，见各归档）

- **执行器 CLI 不可见**：pre 与 post 的 `environment.json` 中，`which.pi`、`which.claude`、`which.codex` 在 8 次取证里都是 `null`。
- **环境变量**：`env_names_present` 只记录名称是否存在，不记录值。其中只有 `PI_CODING_AGENT_DIR` 为 true。
- **被测进程的环境**：
  - `run.env_added_names` 为 `GCM_INTERACTIVE`、`GIT_TERMINAL_PROMPT`、`PYTHONDONTWRITEBYTECODE`；
  - `run.env_removed_names=[]`；
  - 策略见 `run.env_policy`。
- **平台**：
  - Windows 10.0.26100（2025Server，AMD64）；
  - CPython 3.12.10；
  - `git version 2.55.0.windows.5`；
  - `GNU bash, version 5.3.15(2)-release (x86_64-pc-cygwin)`；
  - `core.autocrlf=true`。

### 5.2 操作者记录（source_reported，取证工具没有采集）

来源有两处：

- 规划端写在会话临时目录里的取证记录 `final2-captures.txt`：1495 字节，sha256 `c362495cc389d37204e1250f8ff613585f5722cb8b0e63c60bcf668b9d11d6dd`，修改时间 2026-09-26T04:28:10Z。该文件没有随仓库保存。
- 派发本任务时的说明。

记录内容：

- 取证在 Git Bash 中运行。PATH 去掉了真实 pi、claude、codex 所在的目录。
- `PI_CODING_AGENT_DIR` 指向一个空目录。取证后该目录的条目数为 0（记录原文 `empty_dir_entries=0`）。
- 运行前 unset 了会话令牌变量。`environment.json` 不检查这些变量名，所以这一条没有工具记录。
- 8 次取证的取证工具退出码都是 0（记录原文 `tool_exit=0`）。每次取证后，系统临时目录没有新增的残留目录（记录原文 `leaked=[]`）。
- 取证后，受保护文件相对 HEAD 的 diff 为 0 行。受保护文件为：
  - `scripts/pi_dispatch.py`、`scripts/dispatch-pi.sh`；
  - `tests/test_dispatch.py`、`tests/stub_pi.py`、`tests/stub_pi_help.txt`；
  - `AGENTS.md`、`.agents/`、`.claude/`。

#### 5.2.1 `final2-captures.txt` 的逐字转录（2026-09-26 对抗性核验返工补记）

- **为什么转录**：这份记录一直只在会话临时目录中，会话清理后，上面登记的 sha256 就无法再核对。正式归档（独立文件加 manifest，类似 `../run-controls/`）需要新建归档目录，不在本次返工的可写范围内，已列为规划端的未完成项（`../../acceptance.md` 第 7 节第 19 项）。在那之前，先把内容逐字转录在这里。
- **转录时的核对**（measured，2026-09-26）：原件仍在会话临时目录，1495 字节，sha256 `c362495cc389d37204e1250f8ff613585f5722cb8b0e63c60bcf668b9d11d6dd`，与上面登记的相同。内容只有 ASCII 字符，不含路径、用户名或主机名，不需要脱敏。
- **怎样由转录重建原件**：取下面代码块中的 9 行（不含两行围栏），每行以 LF 结尾（最后一行后面也有一个 LF），行内空格原样保留（例如 `True  |` 中是两个空格）。这样重建的字节是 1495 字节，sha256 应为上面的值；本次写入后已按这个规则从本文件重建并核对过。
- **证据等级不变**：转录只让“这份记录的内容”可以核对，不把记录中的条件变成取证工具的测量。记录中的条件仍是 source_reported。
- **记录实际包含什么**：逐行是 8 次取证各自的取证工具退出码（`tool_exit=0`）、运行结果与前后一致性、汇总行、系统临时目录的新增残留（`leaked=[]`），最后一行是取证后空目录中的条目数（`empty_dir_entries=0`）。上面“记录内容”中的“在 Git Bash 中运行”“PATH 去掉了真实 pi、claude、codex 所在的目录”“unset 了会话令牌变量”“受保护文件 diff 为 0 行”**不在这份文件中**，只来自派发说明；其中受保护文件未改动另有输入清单的 measured 记录（`../../baseline-report.md` 第 12.5 节）。
- `empty_dir_entries=0` 所对应的目录名与产生它的命令没有随文件记录（与实施前基线 `../run-controls/manifest.json` 中控制台输出的说明相同）。

```text
test_dispatch | tool_exit=0 | run: executed=True returncode=0 reason=None timed_out=False duration=216.828s baseline_consistent: True  | 256 checks, 0 failed  | leaked=[]
test_protocols | tool_exit=0 | run: executed=True returncode=0 reason=None timed_out=False duration=4.437s baseline_consistent: True  | Ran 324 tests in 4.075s OK (skipped=4)  | leaked=[]
test_codekit01_fixtures | tool_exit=0 | run: executed=True returncode=0 reason=None timed_out=False duration=7.969s baseline_consistent: True  | Ran 36 tests in 7.771s OK  | leaked=[]
test_baseline_tool | tool_exit=0 | run: executed=True returncode=0 reason=None timed_out=False duration=51.844s baseline_consistent: True  | Ran 40 tests in 51.525s OK  | leaked=[]
test_legacy_gates | tool_exit=0 | run: executed=True returncode=0 reason=None timed_out=False duration=118.265s baseline_consistent: True  | Ran 24 tests in 118.065s OK  | leaked=[]
test_legacy_lifecycle | tool_exit=0 | run: executed=True returncode=0 reason=None timed_out=False duration=128.672s baseline_consistent: True  | Ran 26 tests in 128.438s OK (skipped=2)  | leaked=[]
test_legacy_cli | tool_exit=0 | run: executed=True returncode=0 reason=None timed_out=False duration=84.265s baseline_consistent: True  | Ran 75 tests in 84.147s OK (skipped=1)  | leaked=[]
test_legacy_events | tool_exit=0 | run: executed=True returncode=0 reason=None timed_out=False duration=45.734s baseline_consistent: True  | Ran 34 tests in 45.589s OK  | leaked=[]
empty_dir_entries=0
```

### 5.3 归档时子代理做的核对（静态，不属于这 8 次取证）

- 归档后，上面列出的受保护文件执行 `git diff HEAD` 输出 0 行。
- `.agent/baseline/01-final/` 下没有比归档开始时更新的文件。原件未改。
- 仓库中新增或改动的只有 `docs/themis-tally-v2/01-baseline/evidence/final/`，以及上级 `evidence/` 目录因新增子目录而更新的时间戳。
- 归档前后比对了系统临时目录的列表，没有新增目录。
  - 期间两次看到以 UUID 命名的 `.tmp` 文件，都是在最后一次 archive 结束之后出现，复查时都已被所属进程删除（已查到时间的一个是 0 字节）。它们不是 `baseline.py archive` 产生的。
- 这次核对中 `scripts/codekit/baseline.py` 的 sha256 仍是 `dbb08466…9ce8`，`scripts/pi_dispatch.py` 仍是 `a00d6934…e3ad4`。两者都与取证记录一致。

## 6. 残留机器信息检查

### 6.1 检查方法

扫描范围是 8 个归档目录下的全部 672 个文件，不含本文件。每个文件都按 UTF-8 解码扫描一遍；字节数为偶数时，再按 UTF-16-LE 解码扫描一遍。匹配不区分大小写。

检查的项目：

- 本机用户名及其 8.3 短名；
- 用户应用数据目录名；
- 仓库所在桌面项目目录片段。分隔符包括正斜杠、1–4 个反斜杠（覆盖 JSON 转义）、`\u005c`、`%5c`、`%2f`；
- 本会话 ID，包括全称和 8 位前缀；
- 会话临时目录中由仓库绝对路径转写成的目录名（以盘符和双连字符开头）；
- 本机主机名：只统计次数，不输出值；
- 附加检查：
  - 盘符绝对路径，包括 `X:/` 与 `X:\` 两种写法；
  - MSYS 写法 `/x/`；
  - 用户目录片段 `/Users/`。

### 6.2 检查结果

| 检查项 | 命中 | 说明 |
|---|---|---|
| 本机用户名（长名、8.3 短名） | 0 | |
| 仓库所在桌面项目目录片段（各种分隔符与转义） | 0 | |
| 本会话 ID（全称与前缀）、会话临时目录名 | 0 | |
| 本机主机名 | 0 | |
| MSYS 盘符写法 | 0 | |
| 用户应用数据目录名 | 16 个文件，每个 1 处 | 每个归档的 `pre/08-diff-unstaged.stdout.bin` 与 `post/08-diff-unstaged.stdout.bin` 第 766 行，原因见 6.3 |
| 其他盘符路径（文档正文） | 同上 16 个文件 | 第 298、1296、1997 行，原因见 6.3 |
| 系统程序目录（Program Files）下的工具路径 | 每个归档 3 个文件，8 个归档共 24 个文件、352 处 | 每个归档的 `capture.json` 有 38 处；`pre/environment.json`、`post/environment.json` 各 3 处。原因见 6.4 |

### 6.3 文档正文中的路径（不是本机信息）

8 个归档的 `pre/`、`post/08-diff-unstaged.stdout.bin` 都是同一内容，sha256 `83c0de2f0468ae280b560fa50c0c53dffd6af6e5b5d669acc44a6d43878fac80`。

取证时，工作区删除了 HEAD 已跟踪的几份文档，但删除没有暂存。所以 `git diff` 输出了这些文档的全部删除行（以 `-` 开头）。命中的行都是 HEAD 中已提交文档的正文：

- **第 766 行**：属于 `docs/Codex审查-2.1.md` 那一段 diff。内容是一个示例工作目录，路径中的用户名是示例值，不是本机用户名。
- **第 298、1296 行**：出处同上，内容是列举 Windows 系统临时目录写法的文字。
- **第 1997 行**：属于 `docs/审阅意见.md` 那一段 diff，内容是文档记载的另一个项目的目录。

这些内容已在仓库历史中，脱敏规则也不应改写被测数据，所以保持原样。

### 6.4 工具安装目录（redact-v2 未覆盖的范围）

- `capture.json` 中各次 Git 采样的 `executable` 字段共 38 处：36 处是 Git 可执行文件，2 处是 Git Bash 可执行文件。
- `environment.json` 的 `which.bash`、`which.git`、`which.node` 在 pre 和 post 中各 3 处。
- 这些都是系统程序目录下的安装路径。`archive-manifest.json` 的 `redaction.not_covered` 已声明它们不在脱敏范围内（“其他机器路径（例如 Git/工具安装目录）”）。
- 这些路径不含用户名、仓库位置或会话信息，保持原样。

按任务约束，以上残留都**没有手工修改归档文件**。

## 7. 本索引不证明的内容

- 本目录只证明上表 8 条命令在记录的环境、记录的时刻得到了记录的输出。
- 以下内容本目录不涉及，见 01 的验收映射 `../../acceptance.md`（P4 产物，写本索引时该文件尚未生成）与 `../../baseline-report.md`：
  - 01-A01–A16 各项验收是否通过；
  - 跳过用例对应能力的结论；
  - POSIX 平台的结果。
- 第 4.2 节的 7 个跳过用例都**未运行**，不能计为通过。
