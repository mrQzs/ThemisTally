# 01 收尾取证归档索引（evidence/closure）

本目录收的是 01 收尾轮的取证。收尾轮代码改动（`scripts/codekit/protocols.py` 的 R-P10、R-P11、M-01；`tests/legacy_harness.py` 与 `tests/codekit01_legacy.py` 的清理前归属核对；fixtures 的 manifest 新字段与 D-20–D-23 新 case）完成后，规划端在受控环境中按 R-01 严格 pyc 口径取证 10 次：

- 旧自测 `tests/test_dispatch.py` 1 次；
- 01 新增的 7 个测试文件各 1 次，其中 `tests/test_codekit01_fixtures.py` 改用 `-v` 逐条模式；
- `tests/codekit01_legacy.py` 的 `--check` 与 `--check-stub-regen` 各 1 次。

基本信息：

- **原件位置**：`.agent/baseline/01-closure/<capture-id>/`。该目录被 Git 忽略，只读，不提交。
- **归档方式**：cwd 为仓库根，设 `PYTHONDONTWRITEBYTECODE=1`，逐个运行 `python scripts/codekit/baseline.py archive .agent/baseline/01-closure/<capture-id> --dest docs/code-kit-v2/01-baseline/evidence/closure`。10 份 manifest 的 `created_at` 在 2026-09-26T15:02:30.406285Z 到 15:02:33.292296Z 之间。
- **脱敏规则**：`redact-v2`。
- **工具版本**：取证与归档都用 `scripts/codekit/baseline.py`，sha256 `dbb08466778db639966336902653525fa26a4f9f9152c5827594ea9313e49ce8`。10 份归档 manifest 的 `tool.sha256` 与 10 份 `capture.json` 的 `tool.sha256` 都是这个值。
- **监督器**：`scripts/pi_dispatch.py` 的 `run_supervised`，module_sha256 `a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4`，tool_version 2.2.2（10 份 `capture.json` 的 `supervisor` 字段相同）。
- **基线提交**：`a4fa199b0e5bdc658215765ee7558b9fe6723940`（sha1）。

本索引由规划端子代理手写，本身不是取证产物。

- 表中数字取自同目录下的归档文件：`capture.json`、`archive-manifest.json`、`run/*.bin`，以及 `pre/`、`post/` 下的 json 文件。每一行都能按 capture-id 追到对应文件。
- **例外（勘误补记，见第 9 节）**：第 1 节表中“archive 退出码”与“原件目录文件数”两列不在任何归档文件中，不能从归档文件复算：`archive-manifest.json` 不记录归档命令的退出码；原件目录 `.agent/baseline/01-closure/` 被 Git 忽略，不入库。这两列是本子代理归档时观察的结果（归档时核对）。第 1.2 节的“原件 capture.json”“归档工具控制台输出”与第 5.4 节同属归档时核对。
- 受控条件取自 `../run-controls-closure/`。
- 本文件是在 10 次取证和 10 次归档都结束后才创建的，不在任何一次取证的输入清单里，也不被任何 manifest 列出。本文件的 sha256 不写在本文件内。

证据等级的写法（等级只用文档 2.4 的词表 measured / source_inspected / source_reported / proposed / unknown，括号内只说明来源，不是新的等级）：

- **measured（取证工具）**：取证工具写进 `capture.json` 或 `pre|post/` 的记录。
- **source_reported（操作者记录）**：规划端取证循环写出的记录，即 `../run-controls-closure/closure-captures.txt`。它不是取证工具的输出，取证工具没有采集其中的条件。其中第 5 行的定位结果与第 6、7、18、19 行的计数是操作者脚本在取证前后现场得到的，但取证工具没有采集，本索引也无法复算；第 4 行的 `PYTHONPYCACHEPREFIX=…` 等是循环脚本对自身配置的声明，不是测量。与 baseline-report 13.5 节、acceptance.md 2.2 与 3.1 的记法一致。（勘误：本索引原把这类记录写作“measured（操作者脚本）”，该写法不在 2.4 词表中，已改，见第 9 节。）
- **measured（归档时核对）**：本子代理在归档前后做的检查，不属于这 10 次取证。
- **source_inspected（静态）**：只读文件内容得出的对应关系，不是运行记录。

## 1. 归档结果与完整性

| capture-id | archive 退出码（归档时核对，不在归档文件中） | manifest 列出的文件数（含 capture.json） | 磁盘文件数（含 archive-manifest.json） | capture.json `files` 列出的文件数 | 原件目录文件数（归档时核对，原件不入库） | 摘要不符数（`integrity_check.mismatches`） | `unredacted_files` | 脱敏后字节有变的文件数 | `archive-manifest.json` sha256（字节数） |
|---|---|---|---|---|---|---|---|---|---|
| `bl-01closure-test-dispatch-20260926` | 0 | 83 | 84 | 82 | 83 | 0 | `[]` | 5 | `fd4a0d3687e615c6ae06d70b79ded6a59924ff829d4a44265a8aeb12c5d7d31d`（43723 字节） |
| `bl-01closure-test-protocols-20260926` | 0 | 83 | 84 | 82 | 83 | 0 | `[]` | 5 | `d91e78995fbfa90790274f60139ffb52d58fb3b2c50c21cfe8eea6d589e56037`（43724 字节） |
| `bl-01closure-test-baseline-tool-20260926` | 0 | 83 | 84 | 82 | 83 | 0 | `[]` | 5 | `22694ddf02256dabdace3bfe3e85aa039779cb80284d43fbf48b5ede7ccbd9f0`（43726 字节） |
| `bl-01closure-test-legacy-gates-20260926` | 0 | 83 | 84 | 82 | 83 | 0 | `[]` | 5 | `6e7a47cc1d8ba259297d9c6a3e30d4226782bb1483730318df685b02598d2f11`（43725 字节） |
| `bl-01closure-test-legacy-lifecycle-20260926` | 0 | 83 | 84 | 82 | 83 | 0 | `[]` | 5 | `8b5d41c20fe4544fef6004862b3394495793bee0998b855951585e9e1b4b43bd`（43729 字节） |
| `bl-01closure-test-legacy-cli-20260926` | 0 | 83 | 84 | 82 | 83 | 0 | `[]` | 5 | `38734036c2d20153d9cd5f9b91aebc077b05b09920ae347078194bd52256ab5c`（43725 字节） |
| `bl-01closure-test-legacy-events-20260926` | 0 | 83 | 84 | 82 | 83 | 0 | `[]` | 5 | `b341914ffa16dfc2e41a18491e2696a0b4bcadcae8499b15eaf9a638a487d302`（43726 字节） |
| `bl-01closure-test-codekit01-fixtures-v-20260926` | 0 | 83 | 84 | 82 | 83 | 0 | `[]` | 5 | `54b9132f3abcfa4cb79d065dec860290f2f3fa71fc8c58ccfb6cbd4c1ea69153`（43735 字节） |
| `bl-01closure-legacy-check-20260926` | 0 | 83 | 84 | 82 | 83 | 0 | `[]` | 5 | `b74b9513906ee3fb72602db703ebed6a37cebc3cfc843887a9dae0f8bb2619dc`（43720 字节） |
| `bl-01closure-legacy-check-stub-regen-20260926` | 0 | 83 | 84 | 82 | 83 | 0 | `[]` | 5 | `c8833dc2557af3eb99990a7fecd3cda742e6a9b7a6cc40410bb03330209f7237`（43729 字节） |

### 1.1 文件数的口径

四种计数不要混用：

- **capture.json 的 `files` 列表**：每个取证 82 个，不含 `capture.json` 自身。归档工具按这份列表核对原件摘要，manifest 的 `integrity_check.files_listed_in_capture_json` 都是 82。
- **原件目录的文件数**：每个取证 83 个，即上面 82 个加上 `capture.json`。这是归档时对被 Git 忽略的原件目录的观察，不能从归档文件复算（勘误轮只读复核：原件目录共 830 个文件，每个取证 83 个）。
- **manifest `files` 条目数**：每份 83 条，与原件目录的 83 个文件一一对应。每条都是 `listed_in_capture_json=true`：`capture.json` 自身按工具规则记为 true。
- **归档目录的磁盘文件数**：每个 84 个，即 83 个加上 `archive-manifest.json`。manifest 不列出自身。

合计：

- 10 份 manifest 共列出 830 个文件；
- 10 个归档目录的磁盘上共有 840 个文件；
- 本目录连同 `INDEX.md` 共 841 个文件。

### 1.2 归档后的逐一核对（归档时核对，measured）

- **manifest 条目**：830 个条目的 `archived_sha256` 与 `archived_bytes`，都与归档目录中的文件一致；`original_sha256` 都与 `.agent/baseline/01-closure/` 中的原件一致。
- **manifest 自身**：10 份 `archive-manifest.json` 没有 `archived_sha256` 可比，它们的 sha256 只记在上表最后一列，由本索引手工记录。
- **原件 capture.json**：每份 manifest 的 `source_capture_json_sha256`，都与原件 `capture.json` 的 sha256 一致（见第 3 节）。
- **表示形式**：830 个条目的 `representation` 都是 `redacted_raw`，没有 `captured_raw_copy`；`unredacted_files` 都是 `[]`。
- **归档工具控制台输出**：10 次都是 `files: 83  redacted_changed: 5  raw_copies: 0  rule: redact-v2`，stderr 为空，退出码 0。`archive_dir` 行都指向 `docs/code-kit-v2/01-baseline/evidence/closure/<capture-id>`，完整路径含本机信息，不在此转录。

### 1.3 脱敏改动

每个归档都改动了同样的 5 个文件（条目 `bytes_changed=true`，`length_changed=true`）：

- `capture.json`：`<PYDIR>` ×1，位置是 `run.argv0_which`。
- `pre/environment.json`、`post/environment.json`：各 `<PYDIR>` ×1，位置是 `python.executable`。
- `pre/02-rev-parse-toplevel.stdout.bin`、`post/02-rev-parse-toplevel.stdout.bin`：各 `<REPO>` ×1。

其余 78 个文件脱敏前后字节相同。

- `run/stdout.bin`、`run/stderr.bin` 没有改动。三处摘要一致：
  - 归档文件的实际 sha256；
  - manifest 中的 `original_sha256` 与 `archived_sha256`；
  - `capture.json` 中的 `run.stdout.sha256` 与 `run.stderr.sha256`。
- manifest 的 `redaction.pattern_counts` 在 10 份中都是 `{"<HOME>": 1, "<PYDIR>": 1, "<REPO>": 1, "<TEMP>": 1}`。
  - 这是各类别生成的**匹配模式条数**，不是替换次数（见 `baseline.py` 的 `Redactor.pattern_counts`）。
  - 替换次数看各条目的 `replacements`：`<HOME>` 与 `<TEMP>` 在 10 个归档中都是 0 次。

## 2. 被测命令与结果（项目验证）

10 个取证的被测对象都是本仓库的代码，全部属于**项目验证**。

- 01 文档附录 B 参考代码的验证是另一栏，证据在 `../reference-appendix-b-windows/`，本目录不含（01-A16）。
- “结果汇总行”是 `run/*.bin` 中的原文，括号内是文件和行号（从 1 起算，文件为 CRLF 换行）。
- 退出码、耗时、`timed_out`、`baseline_consistent`、`drift` 取自该取证的 `capture.json`，字段依次为：
  - `run.returncode`；
  - `run.duration_seconds`，单位为秒；
  - `run.timed_out`；
  - `comparison.baseline_consistent`；
  - `comparison.drift`。

| capture-id | 被测命令（cwd=仓库根） | 结果汇总行（原文） | 退出码 | 耗时 (s) | timed_out | baseline_consistent | drift |
|---|---|---|---|---|---|---|---|
| `bl-01closure-test-dispatch-20260926` | `python tests/test_dispatch.py` | `256 checks, 0 failed`（run/stdout.bin:282） | 0 | 235.828 | false | true | `[]` |
| `bl-01closure-test-protocols-20260926` | `python tests/test_protocols.py` | `Ran 342 tests in 4.291s`（run/stderr.bin:687）；`OK (skipped=4)`（run/stderr.bin:689） | 0 | 4.578 | false | true | `[]` |
| `bl-01closure-test-baseline-tool-20260926` | `python tests/test_baseline_tool.py` | `Ran 40 tests in 57.652s`（run/stderr.bin:43）；`OK`（run/stderr.bin:45） | 0 | 58.063 | false | true | `[]` |
| `bl-01closure-test-legacy-gates-20260926` | `python tests/test_legacy_gates.py` | `Ran 24 tests in 128.419s`（run/stderr.bin:52）；`OK`（run/stderr.bin:54） | 0 | 128.735 | false | true | `[]` |
| `bl-01closure-test-legacy-lifecycle-20260926` | `python tests/test_legacy_lifecycle.py` | `Ran 26 tests in 140.098s`（run/stderr.bin:56）；`OK (skipped=2)`（run/stderr.bin:58） | 0 | 140.469 | false | true | `[]` |
| `bl-01closure-test-legacy-cli-20260926` | `python tests/test_legacy_cli.py` | `Ran 75 tests in 92.991s`（run/stderr.bin:153）；`OK (skipped=1)`（run/stderr.bin:155） | 0 | 93.234 | false | true | `[]` |
| `bl-01closure-test-legacy-events-20260926` | `python tests/test_legacy_events.py` | `Ran 34 tests in 51.774s`（run/stderr.bin:71）；`OK`（run/stderr.bin:73） | 0 | 52.0 | false | true | `[]` |
| `bl-01closure-test-codekit01-fixtures-v-20260926` | `python tests/test_codekit01_fixtures.py -v` | `Ran 75 tests in 11.260s`（run/stderr.bin:105）；`OK`（run/stderr.bin:107） | 0 | 11.61 | false | true | `[]` |
| `bl-01closure-legacy-check-20260926` | `python tests/codekit01_legacy.py --check` | `38 checks, 0 differ`（run/stdout.bin:39） | 0 | 9.703 | false | true | `[]` |
| `bl-01closure-legacy-check-stub-regen-20260926` | `python tests/codekit01_legacy.py --check-stub-regen` | `10 checks, 0 differ`（run/stdout.bin:11） | 0 | 0.703 | false | true | `[]` |

- `OK (skipped=N)` 中被跳过的用例没有运行，不算通过，逐条见 4.6 节。
- 退出码 0 本身不是通过的依据。取证工具记录 `run.interpretation=not_evaluated`，不判定被测命令是否通过；本表只转录汇总行与退出码。

### 2.1 10 个取证 `capture.json` 的共同记录（measured，取证工具）

取证过程本身：

- `execution_status=complete`，`incomplete_reasons=[]`；
- `run.executed=true`，`run.interrupted=false`，`run.stray_processes=false`；
- `run.reason=null`，`run.spawn_error=null`；
- `run.kill_method=job-object`，`run.stdin=devnull`，`run.shell=false`，`run.timeout_seconds=3600.0`；
- `run.interpretation=not_evaluated`。

前后比较：

- `comparison.command_executed=true`；
- `comparison.unavailable=[]`，`comparison.observations=[]`；
- `comparison.input_manifest_closure_sha256_equal=true`；
- `comparison.checked` 共 12 项：head、object_format、porcelain_raw_bytes、input_manifest_sha256、diff_unstaged_bytes、diff_staged_bytes、ls_files_bytes、head_object_type、git_version、git_config、bash_version_first_line、environment_facts_sha256。

前后采样：

- pre 与 post 采样都是 `complete=true`，`problems=[]`。
- 10 次取证的 pre 与 post 采样，工作区状态完全相同（20 次采样逐项相同）：
  - HEAD 为 `a4fa199b0e5bdc658215765ee7558b9fe6723940`，object_format 为 sha1，head_object_type 为 commit，`toplevel_matches_repo_root=true`；
  - porcelain 有 1019 项，sha256 为 `af6f80a3c5a70cb855d48ef61b2f3529672bced931b0db05c24550f118a00025`；
  - 输入清单 1073 项（tracked 63，untracked 1010），`closure_sha256` 为 `81b4503e291166fd78632aab9163faac2f0e25c92db11c691dfbe753068f52a4`，`input-manifest.json` 的 sha256 为 `3a559ca5cc328a9632831666f5f59137df0484b2fc5f778af351843cdd619982`；
  - 输入清单的 `closure_status=partial`，`closure_gaps` 为 ignored_files_not_hashed、submodule_contents_not_expanded、out_of_repo_inputs_not_included、gitattributes_effects_not_evaluated；
  - 被忽略的只有 2 个名称：`scripts/__pycache__/`、`tests/__pycache__/`，不计摘要。R-01 与它们的关系见 5.3 节；
  - 排除规则只有 `.agent/baseline/`（prefix）。`exclusion_counts` 为 ignored_names 1、inputs 0。
- 本组取证之间工作区没有变化。

### 2.2 与操作者记录的逐行对照（measured，本子代理的核对）

`../run-controls-closure/closure-captures.txt` 第 8–17 行逐次记录了 10 次取证。按行核对了以下各项，都与该取证的 `capture.json` 和 `run/*.bin` 一致：

- capture-id；
- `argv`；
- `returncode`；
- `timed_out`；
- `duration`；
- `baseline_consistent`；
- 汇总行文字。

| 操作者记录行 | capture-id |
|---|---|
| 8 | `bl-01closure-test-dispatch-20260926` |
| 9 | `bl-01closure-test-protocols-20260926` |
| 10 | `bl-01closure-test-baseline-tool-20260926` |
| 11 | `bl-01closure-test-legacy-gates-20260926` |
| 12 | `bl-01closure-test-legacy-lifecycle-20260926` |
| 13 | `bl-01closure-test-legacy-cli-20260926` |
| 14 | `bl-01closure-test-legacy-events-20260926` |
| 15 | `bl-01closure-test-codekit01-fixtures-v-20260926` |
| 16 | `bl-01closure-legacy-check-20260926` |
| 17 | `bl-01closure-legacy-check-stub-regen-20260926` |

勘误轮补核（measured）：第 8–17 行的 `executed=True`、`reason=None` 也与各 `capture.json` 的 `run.executed`、`run.reason` 一致。

操作者记录中的 `tool_exit=0` 是取证工具自身的退出码，`leaked=[]` 是系统临时目录的新增残留目录。这两项在 `capture.json` 中没有对应字段，无法与取证工具的记录核对，只有操作者记录（source_reported）。所以第 8–17 行不能说与 `capture.json`“逐字段一致”，只能说上列字段一致。

## 3. 输出文件与取证记录的摘要

| capture-id | run/stdout.bin sha256 | run/stderr.bin sha256 | 原件 capture.json sha256（`source_capture_json_sha256`） | run 起止（UTC） |
|---|---|---|---|---|
| `bl-01closure-test-dispatch-20260926` | `f40586e2376e2361bc962878059d732b95c2c8cb0f79d48c3fd069fc37e1080e`（13423 字节） | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `a5d1c5ecd4fa80d1b6a0051e8ab950ca0fb099b27688bb02912705b596105659` | 2026-09-26T14:47:11.933559Z → 14:51:07.756117Z |
| `bl-01closure-test-protocols-20260926` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `5b81e659c60f296503dd99e836a938fa45134ffe597fb960a204b56ee65354c8`（77955 字节） | `c0df97cd6dcd90a4467810de7ae8bdd7825827974fb2e533ee0cbaf5d12f94aa` | 2026-09-26T14:51:11.780950Z → 14:51:16.367920Z |
| `bl-01closure-test-baseline-tool-20260926` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `024b9d508c236c504ee277b9aa07db14f45ad32235d547c1d161002121f22863`（5064 字节） | `5b05e0a3efa2bcdb3e477dfd2a26fade461940986c302cf8943a3f11d5846c18` | 2026-09-26T14:51:20.240815Z → 14:52:18.296680Z |
| `bl-01closure-test-legacy-gates-20260926` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `97af8357a3730e301a70d6890bfc1d1463186590d25f4db15d7348ea938138f6`（6459 字节） | `c6ea48d5a0c1820f58dcd031ee499dc98f325542a120fa82ff05c43534b4db86` | 2026-09-26T14:52:22.161116Z → 14:54:30.897457Z |
| `bl-01closure-test-legacy-lifecycle-20260926` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `e79ad9f8e4e9f8330f7677f2696ae9908dc6604b2735f955c62813924a2aa99f`（7809 字节） | `82582d8e2d57c4c6e9e186fffada8f5c404350dbb3e426394934e41fa04f1d48` | 2026-09-26T14:54:35.841086Z → 14:56:56.308380Z |
| `bl-01closure-test-legacy-cli-20260926` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `26cce1cf6ad440b5f584180592d772bb4e720e2a54f353694f458bef6a16c3ae`（19861 字节） | `81eb9fe0daa980cd15c48c03e922b048e7af9e6ad0a51f68c69e491ec0e482f0` | 2026-09-26T14:57:00.516082Z → 14:58:33.753821Z |
| `bl-01closure-test-legacy-events-20260926` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `e5cfa16608d66529963a69a7a10236c294873692b3efe19f5773b0c6bbe70166`（8739 字节） | `1fcd3f46f74cf197800b49a454a04d160dbaedbd1a5f686c214969949e9cdaa5` | 2026-09-26T14:58:37.842713Z → 14:59:29.842166Z |
| `bl-01closure-test-codekit01-fixtures-v-20260926` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `95faa68cea9315a4a73cc4bfc4223916e56b8eb1b9e5694fa1415fdf1c8b169a`（13127 字节） | `1a05c650637907fc0bbc990b2c2f421a725ee05b696109dd2639d008d100dcde` | 2026-09-26T14:59:33.945406Z → 14:59:45.553670Z |
| `bl-01closure-legacy-check-20260926` | `2a06d6b3069d23cbb24649983cbced3770476d7b5a3fdf16e751dea94580f5d2`（3712 字节） | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `92d7edd3fafd04ce8d4e64234c8fb6331c798d7afe94c116a09ec4057de9bae9` | 2026-09-26T14:59:50.037533Z → 14:59:59.734961Z |
| `bl-01closure-legacy-check-stub-regen-20260926` | `9a942083ceece639e010b0771c7c2f0efd68470d40f8cd72766d76d63de1a785`（273 字节） | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`（0 字节） | `c9dbf242c2b907526bed2607150ddb1bbf391fc0c3abb272c4c3d1a6927ef871` | 2026-09-26T15:00:04.642120Z → 15:00:05.353917Z |

`e3b0c442…b855` 是空内容的 sha256。

## 4. 逐方法统计与可追溯性

### 4.1 统计方法（measured，本子代理对 `run/*.bin` 的解析）

- **unittest 逐条输出**：
  - 以 `^<方法名> (__main__.<类>.<方法名>)` 开头的行，作为一个用例的起始行。
  - 其后第一行以 ` ... ok`、` ... skipped '<原因>'`、` ... FAIL`、` ... ERROR`、` ... expected failure` 或 ` ... unexpected success` 结尾的行，作为该用例的结果行。
  - 带说明文字的用例，结果行是起始行的下一行。
  - 7 个 unittest 套件中，每个起始行都恰有一个结果行，方法名（类.方法）没有重复。逐条计数与汇总行 `Ran N tests` 一致。
  - 7 个套件的输出中，`Traceback`、`FAIL:`、`ERROR:` 都出现 0 次。
- **`tests/test_dispatch.py`**：这是自带的检查脚本，不是 unittest。统计行首为 `PASS ` 与 `FAIL` 的行。
- **`tests/codekit01_legacy.py`**：统计行首为 `SAME` 的行，以及其他非空行。

### 4.2 各取证的逐条计数

| capture-id | 输出形式 | 逐条记录数 | ok | skipped | FAIL | ERROR | 类数 | 逐条记录所在行 |
|---|---|---|---|---|---|---|---|---|
| `bl-01closure-test-protocols-20260926` | unittest 逐条（stderr） | 342 | 338 | 4 | 0 | 0 | 18 | stderr 1–684 |
| `bl-01closure-test-baseline-tool-20260926` | unittest 逐条（stderr） | 40 | 40 | 0 | 0 | 0 | 9 | stderr 1–40 |
| `bl-01closure-test-legacy-gates-20260926` | unittest 逐条（stderr） | 24 | 24 | 0 | 0 | 0 | 9 | stderr 2–49 |
| `bl-01closure-test-legacy-lifecycle-20260926` | unittest 逐条（stderr） | 26 | 24 | 2 | 0 | 0 | 7 | stderr 2–53 |
| `bl-01closure-test-legacy-cli-20260926` | unittest 逐条（stderr） | 75 | 74 | 1 | 0 | 0 | 10 | stderr 1–150 |
| `bl-01closure-test-legacy-events-20260926` | unittest 逐条（stderr） | 34 | 34 | 0 | 0 | 0 | 6 | stderr 1–68 |
| `bl-01closure-test-codekit01-fixtures-v-20260926` | unittest 逐条（stderr，`-v`） | 75 | 75 | 0 | 0 | 0 | 14 | stderr 1–102 |

`test_legacy_gates` 与 `test_legacy_lifecycle` 的 `run/stderr.bin` 第 1 行，是测试文件自己打印的被测 `pi_dispatch.py` 摘要（`test_legacy_gates` 的这一行另有 Python 与平台版本），不是用例，所以逐条记录从第 2 行开始。

另外三个取证不是 unittest，按行计数：

- **`bl-01closure-test-dispatch-20260926`**：`run/stdout.bin` 中有 256 行以 `PASS ` 开头，0 行以 `FAIL` 开头，另有 24 行 `== <分组名>` 的分组标题。每条检查以描述文字标识，没有方法名。
- **`bl-01closure-legacy-check-20260926`**：`run/stdout.bin` 第 1–38 行都以 `SAME` 开头，第 39 行是汇总行。没有其他非空行，没有以 `DIFF` 开头的行。
- **`bl-01closure-legacy-check-stub-regen-20260926`**：`run/stdout.bin` 第 1–10 行都以 `SAME stub regen` 开头，第 11 行是汇总行。没有其他非空行。

### 4.3 `test_codekit01_fixtures`：75 个方法名（`bl-01closure-test-codekit01-fixtures-v-20260926`）

- 这次取证用 `-v` 运行，每个用例都有方法名。上一轮 `../final/` 的非逐条模式只有 36 个点号。
- 下表列出全部 75 个用例，结果都是 `ok`。括号内是 `run/stderr.bin` 的行号：起始行与结果行相同时只写一个，否则写“起始行–结果行”。

| 类 | 用例数 | 方法（stderr 行号） |
|---|---|---|
| `CleanupOwnershipTests` | 10 | `test_link_to_owned_directory_refused`（1）；`test_marker_link_to_valid_token_refused`（2–3）；`test_marker_with_trailing_newline_refused`（4–5）；`test_nested_directory_and_foreign_prefix_refused`（6）；`test_owned_directory_is_removed`（7）；`test_removal_unregisters_directory`（8–9）；`test_repository_paths_refused_by_read_only_check`（10）；`test_tampered_or_missing_marker_refused`（11）；`test_unregistered_directory_refused_even_with_forged_marker`（12）；`test_unregistered_prefix_cannot_be_created`（13） |
| `CompatMatrixDCaseTests` | 5 | `test_d20_non_finite_cost_amount`（14）；`test_d21_deep_nesting`（15）；`test_d22_invalid_utf8`（16）；`test_d23_identifier_trailing_newline`（17）；`test_every_d_case_is_a_registered_single_fault_fixture`（18） |
| `CredentialScanTests` | 4 | `test_allowlist_is_exact_and_documented`（19–20）；`test_fixture_files_contain_no_credential_shapes`（21）；`test_scanner_detects_every_rule_in_every_view`（22–23）；`test_secret_key_in_json_with_random_value_detected`（24–25） |
| `DifferentialTests` | 7 | `test_legacy_contract_projection_unchanged`（26）；`test_legacy_event_projection_unchanged`（27）；`test_legacy_expected_headers_match_generator`（28）；`test_legacy_implementation_bytes_are_source_revision`（29）；`test_legacy_negative_derivations_reproducible`（30）；`test_new_strict_verdicts_are_separate_from_legacy_expectations`（31）；`test_new_strict_verdicts_unchanged`（32） |
| `FileIntegrityTests` | 4 | `test_directory_has_no_unregistered_or_missing_files`（33）；`test_every_manifest_digest_matches_file_bytes`（34）；`test_git_attributes_disable_line_ending_conversion`（35）；`test_git_clean_filter_keeps_bytes`（36–37） |
| `GeneratorGuardTests` | 2 | `test_guard_rejects_linked_directory_leaving_allowed_prefix`（38–39）；`test_guard_rejects_paths_outside_allowed_prefixes`（40–41） |
| `HarnessCleanupOwnershipTests` | 11 | `test_area_is_created_owned_and_removed`（42–43）；`test_area_not_direct_child_of_tempdir_refused`（44–45）；`test_gettempdir_changed_refused`（46–47）；`test_link_target_or_link_root_refused`（48–49）；`test_marker_tampered_extended_missing_directory_or_link_refused`（50–51）；`test_new_path_in_removed_area_refused`（52–53）；`test_paths_outside_any_area_refused`（54–55）；`test_prefix_no_longer_owned_refused`（56–57）；`test_removing_area_does_not_follow_links_to_outside`（58–59）；`test_replaced_directory_with_copied_marker_refused`（60–61）；`test_unregistered_directory_refused_even_with_forged_marker`（62–63） |
| `LegacySourceTests` | 2 | `test_generator_sources_at_revision`（64）；`test_legacy_copies_equal_git_show`（65） |
| `ManifestTests` | 7 | `test_claim_rule_rejects_real_and_unlisted_legacy_claims`（66–67）；`test_claim_spelling_variants_rejected`（68–69）；`test_counts_by_class_and_representation`（70）；`test_legacy_draft_merged_and_removed`（71）；`test_manifest_is_strict_json_and_validates`（72）；`test_manifest_matches_generator_definitions`（73）；`test_provenance_consistency`（74） |
| `NegativeTests` | 4 | `test_each_negative_yields_exactly_manifest_code`（75）；`test_negative_bytes_reproducible_from_base`（76）；`test_negative_catalog_is_unique`（77）；`test_negative_counts_by_group`（78–79） |
| `PublicEntryRejectionTests` | 3 | `test_baseline_records_are_internal`（80）；`test_contract_v1_json_is_not_a_public_record`（81）；`test_fixture_manifest_set_is_internal_and_version_2_rejected`（82） |
| `R11Tests` | 6 | `test_c1_completed_entry_matches_protocols_api_example`（83–84）；`test_every_entry_follows_registration_rules`（85）；`test_manifest_level_errors_carry_entry_prefix`（86–87）；`test_registration_counts`（88–89）；`test_two_step_negatives_each_step_alone_accepted`（90）；`test_whole_manifest_bytes_pass_fixture_manifest_payload_validator`（91–92） |
| `StubTests` | 2 | `test_stub_cwd_placeholder_and_no_local_paths`（93）；`test_stub_regeneration_matches_locked_bytes`（94） |
| `SyntheticTests` | 8 | `test_c1_completed_entry_matches_doc`（95）；`test_doc_samples_equal_design_doc_blocks`（96）；`test_golden_vectors_byte_exact`（97）；`test_golden_vectors_match_design_doc_table`（98）；`test_literal_synthetic_files_reproducible`（99）；`test_sample_1_exact_bytes_and_digest`（100）；`test_stub_entry_copy_equals_manifest_entry`（101）；`test_synthetic_positives_accepted`（102） |

收尾轮新增的几类测试，**按类名和方法名**对应如下。这是静态对应，本索引没有核对各方法的断言内容是否覆盖对应裁决：

- 凭据扫描：`CredentialScanTests`，4 个；
- R-P11：`R11Tests`，6 个；
- D-20–D-23：`CompatMatrixDCaseTests`，5 个；
- 清理前归属核对：`CleanupOwnershipTests` 10 个，`HarnessCleanupOwnershipTests` 11 个。

静态核对（归档时，不是运行记录）：

- `tests/test_codekit01_fixtures.py` 中有 75 个 `def test`。
- 它在本组取证 pre 输入清单中的 sha256 是 `16b71bca5f0c86378a00b59fcfc6426de4772b79f04cf356ae6ee4525131a57b`，归档时工作区中的字节与之相同。

### 4.4 `test_protocols`：按类统计与新增方法（`bl-01closure-test-protocols-20260926`）

| 类 | 用例数 | ok | skipped | stderr 行范围 |
|---|---|---|---|---|
| `BusinessPathTests` | 13 | 13 | 0 | 1–26 |
| `ConstantsAndErrorTests` | 12 | 12 | 0 | 27–50 |
| `EventTests` | 43 | 43 | 0 | 51–136 |
| `GitOidTests` | 6 | 6 | 0 | 137–148 |
| `IdentifierTests` | 7 | 7 | 0 | 149–162 |
| `ImportSideEffectTests` | 3 | 3 | 0 | 163–168 |
| `PhysicalPathTests` | 29 | 27 | 2 | 169–226 |
| `ProvenanceTests` | 19 | 19 | 0 | 227–264 |
| `ResourceRefTests` | 22 | 22 | 0 | 265–308 |
| `RunContextTests` | 15 | 15 | 0 | 309–338 |
| `RunDimensionTests` | 13 | 13 | 0 | 339–364 |
| `SchemaFileTests` | 9 | 8 | 1 | 365–382 |
| `SchemaRoutingTests` | 11 | 11 | 0 | 383–404 |
| `SealingTests` | 31 | 31 | 0 | 405–466 |
| `SnapshotTests` | 28 | 27 | 1 | 467–522 |
| `StrictJsonTests` | 24 | 24 | 0 | 523–570 |
| `TimeTests` | 5 | 5 | 0 | 571–580 |
| `UsageTests` | 52 | 52 | 0 | 581–684 |
| 合计 | 342 | 338 | 4 | |

与 `../final/bl-01final-test-protocols-20260925/run/stderr.bin` 按“类.方法”比较：本次新增 18 个方法，没有减少的方法，两次都有的 324 个方法结果相同。新增的 18 个方法结果都是 `ok`，括号内为起始行–结果行：

- M-01（`EventTests`）：
  - `test_A11_m01_append_event_request_and_role_binding`（83–84）
  - `test_A11_m01_binding_reason_order_is_fixed`（85–86）
  - `test_A11_m01_entry_points_agree`（87–88）
  - `test_A11_m01_event_log_request_and_role_binding`（89–90）
  - `test_A11_m01_unreadable_binding_fields`（91–92）
- R-P11（`ProvenanceTests`）：
  - `test_A12_r_p11_check_order_structure_then_steps`（245–246）
  - `test_A12_r_p11_integrity_limits_complete_stream_claims`（247–248）
  - `test_A12_r_p11_manifest_set_reports_entry_pointer`（249–250）
  - `test_A12_r_p11_new_fields_structure`（251–252）
  - `test_A12_r_p11_structure_preservation_limits_field_semantics_claims`（253–254）
  - `test_A12_r_p11_traceable_and_capture_rules`（255–256）
- R-P10（`ResourceRefTests`）：
  - `test_A04_r_p10_declaration_values_validated`（271–272）
  - `test_A04_r_p10_default_registry_declarations`（273–274）
  - `test_A04_r_p10_public_schema_payload_validator`（275–276）
  - `test_A04_r_p10_registration_requires_three_declarations`（277–278）
  - `test_A04_r_p10_validate_resource_payload_representations`（279–280）
  - `test_A04_r_p10_validator_exceptions_are_wrapped`（281–282）
  - `test_A12_r_p10_fixture_manifest_payload_validator`（293–294）

### 4.5 其余套件与 `../final/` 的比较

- **test_baseline_tool、test_legacy_gates、test_legacy_lifecycle、test_legacy_cli、test_legacy_events**：方法集合与 `../final/` 中对应取证完全相同，每个方法的结果也相同。`run/stderr.bin` 的 sha256 不同，原因是汇总行中的耗时不同。
- **test_dispatch**：本次 `run/stdout.bin` 与 `../final/bl-01final-test-dispatch-20260925/run/stdout.bin` 字节相同，sha256 都是 `f40586e2…080e`。

### 4.6 跳过的用例（未运行，不算通过）

方法名与跳过原因都摘自 `run/stderr.bin` 原文，行号为“起始行 / 结果行”。

| capture-id | 方法 | 行号 | 跳过原因（原文） |
|---|---|---|---|
| `bl-01closure-test-protocols-20260926` | `PhysicalPathTests.test_F029_replacement_after_check` | 223 / 224 | 01-D06：01 只提供词法校验与静态解析，不实现抗 TOCTOU 的受控访问；F029 由后续访问实现模块验收，此处未测试，不代表通过 |
| `bl-01closure-test-protocols-20260926` | `PhysicalPathTests.test_F030_fifo_device_hardlink` | 225 / 226 | 01-D06：01 不实现文件类型与硬链接受控读写；F030 由后续访问实现模块验收，此处未测试，不代表通过 |
| `bl-01closure-test-protocols-20260926` | `SchemaFileTests.test_A09_jsonschema_metaschema_optional` | 367 / 368 | 未安装 jsonschema，未做元校验（本机不得安装依赖，见 01-L01） |
| `bl-01closure-test-protocols-20260926` | `SnapshotTests.test_F017_machine_path_projection_belongs_to_02` | 503 / 504 | 01-D05：配置语义投影归 02，F017 由 02 验收；此处未测试，不代表通过 |
| `bl-01closure-test-legacy-lifecycle-20260926` | `CancelTests.test_LB_LIFE_017_sigint_during_pi_run_is_cancelled_exit_1_posix` | 30 / 31 | 只在 POSIX 上运行：SIGINT 到达调度器的语义（KeyboardInterrupt/_Interrupted）；Windows 用 CTRL_BREAK 用例 |
| `bl-01closure-test-legacy-lifecycle-20260926` | `CancelTests.test_LB_LIFE_035_sigint_before_claim_exits_130_posix` | 34 / 35 | 只在 POSIX 上运行：SIGINT 到达调度器的语义（KeyboardInterrupt/_Interrupted）；Windows 用 CTRL_BREAK 用例 |
| `bl-01closure-test-legacy-cli-20260926` | `LegacyMainEntryTest.test_LB_EXIT_029_repo_missing_path_posix_reported_as_git_missing_3` | 21 / 22 | POSIX 分支；本机 Windows 的结果见上一用例（本次 NOT_RUN） |

这 7 个方法与 `../final/` 中跳过的 7 个相同。

## 5. 受控环境

来源不同，证据等级也不同，下面分四类列出。

### 5.1 取证工具自己记录的事实（measured，取证工具，见各归档）

- **执行器 CLI 不可见**：10 次取证 pre 与 post 的 `environment.json` 中，`which.pi`、`which.claude`、`which.codex` 都是 `null`。
- **环境变量**：`env_names_present` 只记录 13 个指定名称是否存在，不记录值，其中只有 `PI_CODING_AGENT_DIR` 为 true。这 13 个名称不含 `PYTHONPYCACHEPREFIX`。
- **被测进程的环境**：
  - `run.env_added_names` 为 `GCM_INTERACTIVE`、`GIT_TERMINAL_PROMPT`、`PYTHONDONTWRITEBYTECODE`；
  - `run.env_removed_names=[]`；
  - `run.env_policy` 原文：“pi_dispatch.child_env({})：继承当前环境，移除仓库重定向变量与推送/发布类凭据，设置 GIT_TERMINAL_PROMPT/GCM_INTERACTIVE，缺省时设置 PYTHONDONTWRITEBYTECODE=1”。
- **取证解释器的启动事实**：输入清单的 `python_startup` 描述的是运行取证工具的解释器，只记录 `PYTHONHOME`、`PYTHONPATH`、`PYTHONSTARTUP` 是否设置（都为 false），不记录 `PYTHONPYCACHEPREFIX`。
- **平台**：
  - Windows 10.0.26100（2025Server，AMD64）；
  - CPython 3.12.10；
  - `git version 2.55.0.windows.5`；
  - `GNU bash, version 5.3.15(2)-release (x86_64-pc-cygwin)`；
  - `core.autocrlf=true`，`core.filemode=false`，`core.ignorecase=true`，`core.symlinks=false`；`core.eol`、`core.fsmonitor`、`core.longpaths`、`core.safecrlf` 未设置。

### 5.2 操作者记录（source_reported；不是取证工具的输出）

- **出处**：`../run-controls-closure/closure-captures.txt`，3133 字节，sha256 `fb00af747f1ff3fd7b20a35d5902c918f7057f58bdfb7e9c660d4db57ccc0e86`，与该目录 `manifest.json` 的登记一致。
- **manifest.json**：sha256 `eed5de9213aa7aa88944b983905cd1b725711f2289e05f270558417309f4ac73`，`record_type=evidence-copy-manifest`，逐字复制，未脱敏。内容用 `<HOME>`、`<TEMP>` 书写。

记录内容（按行号）：

- 第 2 行：记录时刻 `2026-09-26T14:47:09Z`，早于第一次取证的开始时刻 14:47:10.580687Z。
- 第 3 行：在 Git Bash 5.3.15 中运行。
- 第 4 行：受控条件。
  - PATH 去掉了两处用户目录下存放真实 claude、pi、codex 的目录；
  - unset 了 `CLAUDE_CODE_MESSAGING_TOKEN`；
  - `PI_CODING_AGENT_DIR` 指向系统临时目录下一个空目录；
  - `PYTHONPYCACHEPREFIX` 指向系统临时目录下一个取证前为空的目录（原文注明 R-01）。
- 第 5 行：在受控条件下定位 pi、claude、codex，结果都是 absent。
- 第 6 行：`pycache_prefix_entries_before=0`。
- 第 7 行：`protected_diff_lines_before=0`。
- 第 8–17 行：逐次记录，与取证工具记录的对照见 2.2 节。每行都有 `tool_exit=0` 与 `leaked=[]`。
- 第 18 行：`empty_dir_entries_after=0`。
- 第 19 行：`protected_diff_lines_after=0`。
- 第 20 行：`repo_pycache_dirs_newer_than_start=0`。`manifest.json` 已声明这一项的参照时刻偏晚，不作证据使用，本索引也不引用它作任何结论。

### 5.3 R-01（严格 pyc 口径）在本组证据中的等级

- **受控禁用的依据**：只有操作者记录第 4、6 行，证据等级是 source_reported（与 baseline-report 13.5 节、acceptance.md 3.1 一致）。第 4 行的 `PYTHONPYCACHEPREFIX=…` 是循环脚本对自身配置的声明，不是测量；第 6 行的 0 是操作者脚本在取证前统计的条目数，取证工具没有采集。
  - 取证工具没有记录被测进程是否带有 `PYTHONPYCACHEPREFIX`（见 5.1 节）。
  - 也没有记录取证后前缀目录中的条目数。第 6 行只记录了取证前为 0。
- **仓库中的 pyc 目录**：取证时仓库中存在被忽略、不计摘要的 `scripts/__pycache__/` 与 `tests/__pycache__/`（2.1 节）。R-01 的做法不是给它们计摘要，而是让解释器不读它们。
- **子进程能否拿到该变量**：`run.env_policy` 写明子进程“继承当前环境”，只移除仓库重定向变量与推送/发布类凭据。按这段文字推断，操作者设置的 `PYTHONPYCACHEPREFIX` 会传给被测进程。这是依据文字的推断，不是测量。
- **被测进程不写 pyc**：`PYTHONDONTWRITEBYTECODE` 在 `run.env_added_names` 中，是取证工具记录的事实。
- **结论**：本目录能证明取证工具测到的部分；操作者脚本声明的受控条件只有记录（source_reported），本目录不能独立证明。“被测进程未读取仓库中的 pyc”这一点，取证工具没有独立测量。是否据此判定 A01，由规划端或复审决定，本索引不下结论。

### 5.4 归档时的核对（归档时核对，不属于这 10 次取证）

以下由本子代理在归档前后测量：

- **原件未改**：`.agent/baseline/01-closure/` 共 830 个文件，归档前后的 sha256、字节数、修改时间逐一相同。
- **系统临时目录**：归档前后都列出了 `tempfile.gettempdir()` 及其上一级目录的顶层条目，没有新增，也没有减少。从第一次 archive 开始到归档后快照结束，共约 3.4 秒。
- **pyc 目录**：仓库中 `scripts/`、`tests/` 下的 2 个 `__pycache__` 目录，修改时间在归档前后不变。
- **Git 状态**：归档前后比较 `git status --porcelain=v1 -z --untracked-files=all`，新增的 840 项都在 `docs/code-kit-v2/01-baseline/evidence/closure/` 下，没有减少的项。
- **受保护文件**：归档后执行 `git diff HEAD`，输出 0 行。受保护文件为：
  - `scripts/pi_dispatch.py`、`scripts/dispatch-pi.sh`；
  - `tests/test_dispatch.py`、`tests/stub_pi.py`、`tests/stub_pi_help.txt`；
  - `AGENTS.md`、`.agents/`、`.claude/`。
- **工具摘要**：归档后，`scripts/codekit/baseline.py` 的 sha256 仍是 `dbb08466…9ce8`，`scripts/pi_dispatch.py` 仍是 `a00d6934…e3ad4`，与取证记录一致。
- **已有归档目录**：`evidence/` 下 `closure/` 以外的文件，没有一个比 `../run-controls-closure/manifest.json` 更新。`../final/` 中 8 份 `archive-manifest.json` 的 sha256，仍与 `../final/INDEX.md` 第 1 节所列相同。
- **被测代码未变（静态）**：本组 pre 输入清单共 1073 项。
  - 其中 1067 项有 sha256，归档时工作区中这些文件的字节与之全部相同。
  - 另 6 项是工作区中已删除的已跟踪文档（`type=missing`）。
  - 归档时工作区中有而输入清单中没有的文件，除 `closure/` 外只有 `../run-controls-closure/` 的 2 个文件：它们是取证之后才加入的。

## 6. 与其他取证的关系

- **`../final/`（`bl-01final-*`，8 个取证，run 时段 2026-09-26T04:16:50Z–04:28:09Z）**：
  - 就“01 实施完成后的项目验证”而言，被本目录**取代**。
  - 它**保留**为历史证据，本次没有改动其中任何文件。它的 `INDEX.md` 对它所记录的内容仍然有效。
  - 按 R-01，那一批按原口径取证（没有 `PYTHONPYCACHEPREFIX`），保留，不改写。
- **`../bl-01t1-legacy-20260925/`**：实施前的基线，与本目录无取代关系。
- **中间一轮 01-P4**：原件在 `.agent/baseline/01-P4/`，没有归档，已先后被 `../final/` 与本目录取代。
- **`../run-controls-closure/`**：本组取证的操作者记录，见 5.2 节。

本目录与 `../final/` 的差异：

| 项目 | `../final/` | 本目录 |
|---|---|---|
| 取证数 | 8 | 10（新增 `codekit01_legacy.py --check` 与 `--check-stub-regen`） |
| pyc 口径 | 原口径 | R-01 严格口径（依据只有操作者记录，见 5.3 节） |
| test_codekit01_fixtures | 非逐条模式，36 个用例，无方法名 | `-v`，75 个用例，有方法名 |
| test_protocols | 324 个用例（320 ok，4 skipped） | 342 个用例（338 ok，4 skipped），新增 18 个，见 4.4 节 |
| 其余 5 个 unittest 套件 | 40、24、26、75、34 个用例 | 方法集合与结果相同 |
| test_dispatch | 256 checks，0 failed | 相同，`run/stdout.bin` 字节相同 |
| 跳过的用例 | 7 个 | 相同的 7 个 |
| HEAD | `a4fa199b…6723940` | 相同 |
| porcelain 项数 | 319 | 1019 |
| 输入清单项数 | 373 | 1073 |
| `pre/`、`post/08-diff-unstaged.stdout.bin` | sha256 `83c0de2f…ac80` | 相同（20 个文件 sha256 都相同） |
| 取证工具与监督器摘要 | `dbb08466…9ce8`、`a00d6934…e3ad4` | 相同 |
| 每个归档的文件数 | manifest 83 条，磁盘 84 个 | 相同 |

第一列的数字取自 `../final/INDEX.md` 与 `../final/` 中的归档文件。

## 7. 残留机器信息检查

### 7.1 检查方法

- **范围**：10 个归档目录下的全部 840 个文件，不含本文件。
- **解码**：
  - 每个文件都按 UTF-8 解码扫描一遍；
  - 非空且字节数为偶数的 132 个文件，再分别按 UTF-16-LE 与 UTF-16-BE 解码扫描。840 个文件中字节数为偶数的共 602 个，其中 470 个是 0 字节，没有可解码的内容，不影响扫描覆盖（勘误轮按归档文件重算，measured）。
- **匹配**：不区分大小写。

检查的项目：

- 本机用户名的长名与 8.3 短名；
- 用户应用数据目录名；
- 仓库所在桌面项目目录片段，以及项目目录与仓库目录相连的片段。分隔符包括：正斜杠、1–4 个反斜杠（覆盖 JSON 转义）、`\u005c`、`%5c`、`%2f`；
- 本会话 ID 的全称与 8 位前缀；
- 会话临时目录中由仓库绝对路径转写成的目录名（以盘符和双连字符开头）；
- 本机主机名：只统计次数，不输出值；
- 操作者记录中两个临时目录的名称前缀；
- 附加检查：
  - 盘符绝对路径，包括 `X:/` 与 `X:\` 两种写法；
  - MSYS 写法 `/x/`；
  - 用户目录片段 `Users` 加分隔符；
  - `cygdrive`；
  - 系统程序目录 `Program Files`。

### 7.2 检查结果

| 检查项 | 命中 | 说明 |
|---|---|---|
| 本机用户名（长名、8.3 短名） | 0 | UTF-8、UTF-16-LE、UTF-16-BE 都是 0 |
| 仓库所在桌面项目目录片段（各种分隔符与转义） | 0 | |
| 本会话 ID（全称与前缀）、会话临时目录名 | 0 | |
| 本机主机名 | 0 | |
| 操作者记录中的临时目录名前缀 | 0 | |
| MSYS 盘符写法 | 0 | |
| 用户应用数据目录名 | 20 个文件，每个 1 处 | 每个归档的 `pre/08-diff-unstaged.stdout.bin` 与 `post/08-diff-unstaged.stdout.bin` 第 766 行，原因见 7.3 |
| 用户目录片段 | 同上 20 个文件，每个 1 处 | 同在第 766 行 |
| 盘符绝对路径 | 50 个文件，520 处 | 每个归档 52 处：`capture.json` 38 处；`pre/environment.json`、`post/environment.json` 各 3 处；`pre/`、`post/08-diff-unstaged.stdout.bin` 各 4 处（第 298、766、1296、1997 行）。原因见 7.3、7.4 |
| 系统程序目录下的工具路径 | 30 个文件，440 处 | 每个归档 44 处：`capture.json` 38 处，两份 `environment.json` 各 3 处。原因见 7.4 |
| `cygdrive` | 10 个文件，每个 1 处 | 每个归档的 `archive-manifest.json` 的 `redaction.not_covered` 说明文字，其中提到 `/cygdrive/c` 写法未覆盖。不是路径值 |

### 7.3 文档正文中的路径（不是本机信息）

- 10 个归档的 `pre/`、`post/08-diff-unstaged.stdout.bin` 共 20 个文件，内容相同，sha256 `83c0de2f0468ae280b560fa50c0c53dffd6af6e5b5d669acc44a6d43878fac80`，与 `../final/` 中的同名文件也相同。所以 `../final/INDEX.md` 第 6.3 节的说明原样适用。
- **来由**：取证时，工作区删除了 HEAD 已跟踪的几份文档，但删除没有暂存，所以 `git diff` 输出了这些文档的全部删除行（以 `-` 开头）。命中的行都是 HEAD 中已提交文档的正文：
  - 第 298、766、1296 行：属于 `docs/Codex审查-2.1.md` 那一段 diff。第 766 行是一个示例工作目录，路径中的用户名是示例值，不是本机用户名（本机用户名命中为 0）；第 298、1296 行是列举 Windows 系统临时目录写法的文字。
  - 第 1997 行：属于 `docs/审阅意见.md` 那一段 diff，内容是文档记载的另一个项目的目录。
- 这些内容已在仓库历史中，脱敏规则也不应改写被测数据，所以保持原样。

### 7.4 工具安装目录（redact-v2 未覆盖的范围）

- `capture.json` 中各次 Git 采样的 `executable` 字段共 38 处：36 处是 Git 可执行文件，2 处是 Git Bash 可执行文件。
- `environment.json` 的 `which.bash`、`which.git`、`which.node`，在 pre 和 post 中各 3 处。
- 这些都是系统程序目录下的安装路径。`archive-manifest.json` 的 `redaction.not_covered` 已声明它们不在脱敏范围内（“其他机器路径（例如 Git/工具安装目录）”）。
- 这些路径不含用户名、仓库位置或会话信息，保持原样。
- 被测解释器的路径（`run.argv0_which`、`python.executable`）已按 `<PYDIR>` 脱敏。

按任务约束，以上残留都**没有手工修改归档文件**。

## 8. 本索引不证明的内容

- 本目录只证明：上表 10 条命令在记录的环境、记录的时刻，得到了记录的输出。
- 以下内容本目录不涉及，见 `../../acceptance.md` 与 `../../baseline-report.md`：
  - 01-A01–A16 各项验收是否通过；
  - 跳过用例所对应能力的结论；
  - POSIX 平台的结果。
- 第 4.6 节的 7 个跳过用例都**未运行**，不能计为通过。
- 第 4.3 节中方法名与收尾轮裁决（R-P11、D-20–D-23、清理核对、凭据扫描）的对应，只按名称做了静态对应，没有核对断言内容。
- R-01 受控禁用的依据只有操作者记录（5.3 节）。
- 取证工具不提供网络隔离、凭据隔离或沙箱（见各 `capture.json` 的 `limitations`）。

## 9. 修订记录

- **2026-09-26 勘误**（规划端子代理，对抗性核验返工）：只改本索引的文字，没有改动任何归档文件、原件或 manifest；第 1–4 节的数字与第 7 节的检查结论都不变。
  1. 证据等级：原“measured（操作者脚本）”不在文档 2.4 的词表中，文首的写法说明、5.2 节标题与 5.3 节改为 source_reported，与 baseline-report 13.5 节、acceptance.md 2.2 与 3.1 一致；文首四种写法都对到 2.4 词表。5.3 节“结论”改为：操作者脚本声明的受控条件只有记录，本目录不能独立证明。
  2. 第 1 节表的“archive 退出码”“原件目录文件数”两列不在归档文件中，在文首、表头与 1.1 节标为归档时核对。勘误轮只读复核原件目录：共 830 个文件，每个取证 83 个。
  3. 2.2 节补核 `executed`、`reason`（与 capture.json 一致），并写明 `tool_exit`、`leaked` 在 capture.json 中没有对应字段，只有操作者记录（source_reported）。
  4. 7.1 节 UTF-16 扫描的文件数口径改为“非空且字节数为偶数的 132 个”（840 个文件中偶数字节 602 个，其中 0 字节 470 个）。
- 本文件的 sha256 仍不写在本文件内；勘误后的字节摘要由 baseline-report 修订 7、兼容矩阵修订 12 与 acceptance.md 第四次修订引用。
