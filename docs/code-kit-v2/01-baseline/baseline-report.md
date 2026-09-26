# 01 基线报告：实施前基线 bl-01t1-legacy-20260925、实施后回归与收尾取证

本文是 [baseline-report.json](baseline-report.json) 的人读版，两者内容一致，出现分歧时以 JSON 为准。这条先后规则只适用于本报告自己的两份文件：本报告只判定 01-A01、01-A07、01-A16，其余 13 项（01-A02–A06、A08–A15）由 [acceptance.md](acceptance.md) 判定，JSON 中这些条目标 `judged_by_this_report=false`，不能读作 NOT_RUN（修订 5 更正，见第 8 节）。

- **依据**：`docs/code-kit-v2/01-baseline-and-protocols-审阅增强版.md`。仓库中文件名因编码显示为乱码。修订 `review-expanded-2026-09-25`，SHA-256 `c5fca7b163d6e8d42f0c79dc0b5d6755c508ec832e8a87f514a294c8a300f42d`。
  - **上传的原文**（修订 4 补记）：附录 F.1 给出原文 `01-baseline-and-protocols.md` 的 SHA-256 `49b880b87c037b00f73de0214c6859d60f268fb10d569f7186d1dae7834b18c2`（source_reported）。本仓库中没有原文，无法复算，也无法核对增强版相对原文的修订关系，所以本报告只能以增强版为依据（JSON `identity.source_document.original_upload`，限制 L-SOURCE-ORIGINAL）。
- **字段规则**：遵循文档 2.4、6.3、6.4。
  - `execution_status` 取 PASS / FAIL / ERROR / BLOCKED / NOT_RUN / UNSUPPORTED；
  - `evidence_basis` 取 measured / source_inspected / source_reported / proposed / unknown；
  - 每条 PASS 都带基线引用，以及归档证据的仓库相对路径和 SHA-256；
  - 静态核实不配运行型 PASS；
  - `applicability` 取 applicable / not_applicable，取 not_applicable 时必须写理由（修订 4 增加，01-L09）。它只表示检查对该平台或范围没有意义，不能代替必需能力的 execution_status：必需的安全能力不能标不适用来绕过，对应能力仍按 NOT_RUN 等状态记录。修订 3 以前的条目没有这个字段，缺省视为 applicable。
  - `judged_by_this_report`（修订 5 增加）：JSON `acceptance[]` 中取 false 的条目是本报告不判定的验收项，不带 execution_status、evidence_basis 与 evidence_refs，不能读作 NOT_RUN；其中 `transcript_from_acceptance_md` 只是照录 acceptance.md 的判定文字与证据编号，分歧时以 acceptance.md 为准。
- **报告本体**：不内嵌自身摘要（2.3）。JSON 用固定序列化：`json.dumps(ensure_ascii=False, sort_keys=True, separators=(",",":"))` 加 LF。
- **编写者**：规划端（Claude Code）子代理。修订 1、2 属于 P1.4 任务，验收判定是初判；修订 3 由 P4 报告更新子代理依据最终取证给出 01-A01、01-A07、01-A16 的判定，待独立复审。修订 4 由完整性审查返工子代理编写，不改判定。修订 5 由对抗性核验返工子代理编写，不改判定。修订 6 由收尾取证后的报告更新子代理编写，依据收尾取证与 R-01、R-02 重新判定这三项，待独立复审。修订 7 由对抗性核验返工子代理编写，不改判定。
- **修订**：当前为修订 7（UTC 2026-09-26，对抗性核验勘误）。修订 7 只改报告自身的记录，**不改 01-A01、01-A07、01-A16 的判定**（JSON `identity.revision_history` 修订 7 一条、`closure_regression.verification_revision_7`；第 13.10 节）：
  - 第 13 节导语与 JSON `closure_regression.operator_record.evidence_basis`：操作者记录第 8–17 行不再写“与各 capture.json 逐字段一致”，改为列出实际核对的字段；`tool_exit`、`leaked` 在 capture.json 中没有对应字段，只有操作者记录（source_reported）。
  - 第 10.1、10.3 节与 JSON `limitations[L-FINAL-OPERATOR]`：状态统一为“部分关闭（归档要求已关闭；证据等级仍是 source_reported）”，JSON `status_revision_6` 由 closed 更正为 partially_closed（原值与理由记在 `status_revision_6_errata`）；M-07 统一为“已关闭（归档要求）；条目中的‘实测’‘探针’仍只是线索，证据等级不变”，JSON `legacy_inventory.inventory_items_archive.closes` 同步。
  - [evidence/closure/INDEX.md](evidence/closure/INDEX.md) 与兼容矩阵（修订 12）由同一轮勘误更新，引用按新字节重新固定（第 11、13、13.8 节；JSON `closure_regression.index_ref`、`compatibility.ref` 与三项判定的 evidence_refs，旧摘要移入 history）。
  - JSON 中 01-A13 的照录文字含“`SEALING_LIMITATIONS` 第 8 条”，与代码不符；照录保持原样，另加 `transcript_errata_revision_7`（acceptance.md 3.13 已更正）。
- **修订 6**（UTC 2026-09-26，收尾取证之后）。派发说明把本次任务写作“修订 5”，但报告此前已有修订 5，为不覆盖既有记录，本次记为修订 6（JSON `identity.revision_numbering_note`）。修订 6 的改动：
  - 新增第 13 节与 JSON `closure_regression` 分区：10 次收尾取证（`bl-01closure-*-20260926`，R-01 严格 pyc 口径）逐条记录命令、结果、执行状态、归档路径与 sha256，以及 [evidence/closure/INDEX.md](evidence/closure/INDEX.md) 的引用；另记 R-01 受控禁用的证据等级、旧自测三次对照、受保护文件、归档完整性与残留复扫。
  - 第 12 节（最终取证 `bl-01final-*`）标为被收尾取证取代的历史证据，内容不改写；其操作者记录已正式归档到 `evidence/run-controls-final/`。
  - 第 8 节：01-A01 按 R-01、01-A07 按 R-02、01-A16 用收尾证据重新判定，三项仍为 PASS，范围与依据见该节；修订 3 的判定移入“判定历史”。
  - 按当前字节重新固定 legacy-inventory.md 与 compatibility-matrix.md 的摘要（第 7.1、11 节），新增 `evidence/inventory-items/` 的引用；兼容矩阵中的取证引用、测试计数与 `protocols.py` 行号由本修订更新（矩阵修订 11，不改兼容结论）。
  - 第 10 节标注已关闭或部分关闭的限制，新增第 10.3 节（L-CLOSURE-*）；第 1 节增补收尾取证各栏。
- **修订 5**（UTC 2026-09-26，对抗性核验返工）只改报告自身的记录，**不改 01-A01、01-A07、01-A16 的判定**：
  - 把 JSON `acceptance[]` 中 01-A02–A06、A08–A15 的记法从 `execution_status=NOT_RUN`、`evidence_basis=unknown` 改为 `judged_by_this_report=false` 并指向 acceptance.md，另照录其判定文字与证据编号（第 1、8 节）；
  - `evidence/final/INDEX.md` 更正了一处计数并逐字转录操作者记录，本报告对它的引用按新字节重新固定（第 12 节，JSON `index_ref` 与三项判定的 evidence_refs，旧摘要移入 history）；
  - 更新 L-FINAL-OPERATOR（第 10.1 节），在第 12.7 节写明 664 与 672 的区别，新增第 12.9 节（修订 5 的核对方法）。
- **修订 4**（UTC 2026-09-26，完整性审查返工）只改报告自身的记录，**不改任何判定**：补记上传原文的摘要、增加 applicability 字段与 01-A16 的平台适用性、新增第 10.2 节（L-TOTAL-DESIGN、L-SOURCE-ORIGINAL）、在 01-A07 的限制中补上文档 3.2 两个字段的缺口，并按当前字节重新固定 legacy-inventory.md 与 compatibility-matrix.md 的摘要（第 7.1、11 节）。更早的修订：修订 2 处理复审意见；修订 3（UTC 2026-09-26，P4 最终取证之后）新增第 12 节“实施后回归”，并更新第 1、7、8、10、11 节。JSON 的 `identity.revision_history` 记录了各次改动。
  - 第 2–6、9 节描述实施前基线 `bl-01t1-legacy-20260925`，修订 3–7 都没有改动（修订 4 只在文首“依据”下加了一条）；其中的“本次”都指这次取证。
  - 已有归档目录（`evidence/bl-01t1-legacy-20260925/`、`reference-appendix-b-windows/`、`run-controls/`、`final/`、`closure/`、`run-controls-final/`、`run-controls-closure/`、`inventory-items/`）中的归档文件没有改动；修订 6、7 只读取它们。修订 5 时 `final/` 下手写的 `INDEX.md`（不是归档文件，不在任何 manifest 中）按任务授权更正过一次，见第 12 节；修订 7 时 `closure/` 下手写的 `INDEX.md`（同样不是归档文件）由同一轮勘误按任务授权更正过一次，见第 13.10 节。
- **路径占位符**：`<REPO>` 仓库根，`<HOME>` 用户主目录，`<TEMP>` 系统临时目录，`<PYDIR>` 解释器所在目录，`<SCRATCHPAD>` 规划会话临时目录。`<X:8.3>` 表示同一目录的 8.3 短名写法。

## 1. 分范围结论

表中前 5 行是实施前基线 `bl-01t1-legacy-20260925` 的结论，修订 3 以后没有改动；“实施后回归”各行来自第 12 节的 8 次最终取证，修订 6 起是**被收尾取证取代的历史证据**（保留，不改写，按 R-01 原口径）；“收尾取证”各行来自第 13 节的 10 次收尾取证；“验收”一行是修订 6 的判定（修订 3 的判定见第 8 节“判定历史”）。

| 范围 | 结论 | 状态 |
|---|---|---|
| 项目旧自测 · Windows | 在 HEAD `a4fa199b0e5bdc658215765ee7558b9fe6723940`（sha1）上运行 `python tests/test_dispatch.py`：<br>- 工作区是取证时的脏工作区，输入清单闭包为 `8ca10fb98b8d97213ae4430fdb3e8f444cb7aa0ac12fbdff8a5986513fece0a9`；<br>- 退出码 0，输出 `256 checks, 0 failed`，stderr 为空，前后采样一致；<br>- 24 个 `test_*` 函数中，23 个产生了检查并全部通过；`test_wrapper_interpreters_and_literal_arguments` 在 Windows 上没有运行。<br>所以只能说“Windows 上已运行的 256 项旧断言全部通过”，不能说 Windows 全量通过，也不宣称可以严格复现 | PASS（限上述范围） |
| 项目旧自测 · Linux、macOS | 没有运行，没有结论 | NOT_RUN |
| 基线取证 | 取证完整，前后 12 个采样项一致，没有漂移。归档的 83 个文件与取证原件摘要一致，`unredacted_files` 为空 | PASS |
| 环境与离线边界 | 取证前后 PATH 上都没有真实的 pi、claude、codex（实测）。<br>`PI_CODING_AGENT_DIR` 已设置（实测，只记录是否存在）；它指向空目录，依据是操作者记录（source_reported）。<br>受控环境使 doctor 运行真实 CLI、读取真实 agent 目录等旧分支没有执行（见第 10 节）。<br>网络隔离既没有由环境实现，也没有监测，离线的依据是静态核实 | 受控 CLI 缺席：PASS<br>运行时隔离：NOT_RUN |
| 参考代码验证 · Windows | 三个参考文件的摘要与附录 E.2 一致。附录 B 参考自测共 21 项：<br>- 19 项通过；<br>- 1 项失败：`test_static_resolution`，原因是 8.3 短名，属于测试写法问题，对照运行已确认；<br>- 1 项跳过：非 POSIX 平台。<br>本栏与项目旧自测分栏记录，互不替代 | 摘要：PASS<br>自测：FAIL<br>Schema 元校验：BLOCKED |
| 实施后回归 · 旧自测 · Windows | `bl-01final-test-dispatch-20260925`：`python tests/test_dispatch.py` 退出 0，`256 checks, 0 failed`，stderr 为空，前后采样一致。<br>run/stdout.bin 与实施前逐字节相同。被测旧源码与受保护文件相对 HEAD 没有改动。<br>只能说“Windows 上已运行的 256 项旧断言在实施前后都通过”；`test_wrapper_interpreters_and_literal_arguments` 仍未运行 | PASS（限上述范围） |
| 实施后回归 · P4 特征化回归 · Windows | 4 个文件共 159 个方法：156 个 ok，3 个 POSIX 方法跳过。<br>锁定的是 a4fa199 旧实现的现状，其中 49 个方法是白盒 | 156 个方法 PASS<br>3 个 NOT_RUN |
| 实施后回归 · 01 协议与 fixtures · Windows | `test_protocols.py`：324 个方法，320 个 ok；F017、F029、F030 跳过（NOT_RUN），jsonschema 元校验跳过（BLOCKED）。<br>`test_codekit01_fixtures.py`：36 个用例运行，OK，没有跳过；输出不含方法名，只有命令级结论 | 命令级 PASS<br>3 项 NOT_RUN，1 项 BLOCKED<br>fixtures 无方法级结论 |
| 实施后回归 · 取证工具自测 · Windows | `test_baseline_tool.py`：40 个方法全部 ok | PASS |
| 实施后回归 · 证据归档 | 8 个归档目录各 83 个清单条目、84 个文件，修订 3 重算 664 个文件摘要全部一致；`unredacted_files` 都为空；重扫没有可识别本机用户的残留 | PASS |
| 实施后回归 · Linux、macOS | 8 条命令都没有运行，没有结论 | NOT_RUN |
| 收尾取证 · 旧自测 · Windows | `bl-01closure-test-dispatch-20260926`：`python tests/test_dispatch.py` 退出 0，`256 checks, 0 failed`，stderr 为空，前后采样一致。<br>run/stdout.bin 与实施前、最终取证逐字节相同；这一次按 R-01 以 `PYTHONPYCACHEPREFIX` 禁用了仓库中的 pyc（依据只有操作者记录）。<br>被测旧源码与受保护文件相对 HEAD 没有改动。`test_wrapper_interpreters_and_literal_arguments` 仍未运行 | PASS（限 Windows 已运行的 256 项） |
| 收尾取证 · P4 特征化回归 · Windows | 4 个文件共 159 个方法：156 个 ok，3 个 POSIX 方法跳过；方法集合与结果和最终取证相同。锁定的是 a4fa199 旧实现的现状，其中 49 个方法是白盒 | 156 个方法 PASS<br>3 个 NOT_RUN |
| 收尾取证 · 01 协议与 fixtures · Windows | `test_protocols.py`：342 个方法，338 个 ok；F017、F029、F030 跳过（NOT_RUN），jsonschema 元校验跳过（BLOCKED）。<br>`test_codekit01_fixtures.py -v`：75 个方法都有方法名且都是 ok，没有跳过。<br>`codekit01_legacy.py --check`：38 行 SAME、0 行 DIFF；`--check-stub-regen`：10 行 SAME | 方法级 PASS（338 + 75）<br>两条核对命令 PASS<br>3 项 NOT_RUN，1 项 BLOCKED |
| 收尾取证 · 取证工具自测 · Windows | `test_baseline_tool.py`：40 个方法全部 ok | PASS |
| 收尾取证 · 证据归档 | 10 个归档目录各 83 个清单条目、84 个文件；修订 6 重算 830 个条目的归档摘要与原件摘要，全部一致；`unredacted_files` 都为空；识别类残留复扫 852 个文件 0 命中 | PASS |
| 收尾取证 · 环境 | 取证前后 PATH 上都没有真实的 pi、claude、codex（实测，20 次采样）。`PI_CODING_AGENT_DIR` 已设置（实测，只记是否存在），指向空目录依据操作者记录。<br>`PYTHONPYCACHEPREFIX` 指向取证前为空的目录只有操作者记录（R-01，取证工具没有记录这个变量）。<br>网络隔离没有由环境实现，也没有监测 | 受控 CLI 缺席：PASS<br>pyc 受控禁用：只有操作者记录（source_reported）<br>运行时隔离：NOT_RUN |
| 收尾取证 · Linux、macOS | 10 条命令都没有运行，没有结论 | NOT_RUN |
| 验收（修订 6） | 01-A01 PASS（限 Windows；以 10 次收尾取证为依据，R-01 严格 pyc 口径；pyc 的受控禁用只有操作者记录，取证工具没有测量；输入闭包 partial）。<br>01-A07 PASS（Windows，范围限定，按 R-02）：六类与 G0–G6 逐门都有已实测的失败路径断言；子分支、POSIX 与备注层的缺口登记为 unmet_within_scope，迁移比较时记 NOT_COVERED；G5 的读法待规划端确认。<br>01-A16 PASS。<br>其余 13 项（01-A02–A06、A08–A15）本报告**不判定**，不是 NOT_RUN：判定见 [acceptance.md](acceptance.md) 第 0、3 节。<br>修订 2、3 的判定见第 8 节“判定历史” | 部分完成 |

## 2. 基线身份

| 项 | 值 |
|---|---|
| 调查提交 / 实际 HEAD | `a4fa199b0e5bdc658215765ee7558b9fe6723940`，两者一致；对象格式 sha1，对象类型 commit |
| 仓库根 | `<REPO>`，与 toplevel 一致。它是环境定位，不作业务路径 |
| 取证 ID / 时间（UTC） | `bl-01t1-legacy-20260925`，2026-09-25T12:47:48.285Z 至 12:52:00.437Z |
| 取证工具 | `scripts/codekit/baseline.py`，SHA-256 `9eb033456fe9aa90914c44783fb078b0b42a0977d877103593db657d4cdc2d69` |
| 监督器 | `scripts/pi_dispatch.py::run_supervised`，工具版本 2.2.2，SHA-256 `a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4` |
| 输入清单 | 共 92 项：已跟踪 63 项，未跟踪 29 项。<br>被忽略的名称有 2 个（`scripts/__pycache__/`、`tests/__pycache__/`），不计摘要。其中 `scripts/__pycache__/pi_dispatch.cpython-312.pyc` 会被测试进程导入时读取，见第 10 节。<br>闭包 `8ca10fb98b8d…fece0a9`，状态 partial。<br>排除规则只有 `.agent/baseline/`，被排除的输入数为 0 |
| 工作区状态 | 脏工作区，如实记录，没有为制造干净基线做重置或清理：<br>- porcelain 37 项；<br>- 未暂存差异 242653 字节；<br>- 已暂存差异 0 字节 |

被测源码在取证时的状态如下。这些文件的已跟踪版本都与 HEAD 一致。报告生成时再次核对：字节没有变化，`git diff HEAD` 对这些路径为空。

| 文件 | 字节 | SHA-256（前 16 位） |
|---|---|---|
| `scripts/pi_dispatch.py` | 274717 | `a00d693452b4345d` |
| `tests/test_dispatch.py` | 121490 | `c6fed33534b096b7` |
| `tests/stub_pi.py` | 14376 | `96c0d4a5ba775e9c` |
| `tests/stub_pi_help.txt` | 10176 | `5668cff3cf34fd6f` |
| `scripts/dispatch-pi.sh` | 1010 | `e2e12058ef5d58b4` |
| `AGENTS.md` | 10932 | `7571e9a9e68046f4` |

取证之后，工作区仍被其他任务修改，例如 `.gitattributes` 新增了 `-text` 规则，`01-baseline/` 下新增了文档与本证据目录。本报告的基线结论只对应取证时刻。

## 3. 受控环境

### 3.1 平台与工具链

这些数据来自取证工具的实测。

| 项 | 值 |
|---|---|
| 平台 | Windows，release 2025Server，版本 10.0.26100，AMD64，`os.name=nt` |
| Python | CPython 3.12.10（tags/v3.12.10:0cc8128，MSC v.1943 64 bit），`<PYDIR>\python.exe` |
| Git | git version 2.55.0.windows.5 |
| Bash | GNU bash 5.3.15(2)-release（x86_64-pc-cygwin），即 Git Bash |
| Git 配置 | `core.autocrlf=true`、`core.filemode=false`、`core.ignorecase=true`、`core.symlinks=false`。<br>`core.eol`、`core.fsmonitor`、`core.longpaths`、`core.safecrlf` 未设置 |
| 平台能力 | Job Object 可用：超时与强杀用例的回收断言都通过了。<br>目录 junction 和文件符号链接可以创建：`test_v2_review_fixes` 的链接用例全部实际执行 |

### 3.2 受控条件

依据操作者记录（source_reported）与取证工具实测（measured）。

- **shell**：在 Git Bash 中运行，因为 PowerShell 的 PATH 上没有 bash。
- **PATH**：运行时从 PATH 去掉 `<HOME>/.local/bin` 与 `<HOME>/AppData/Roaming/npm`，使真实的 pi、claude、codex 都不在 PATH 上。
  - 实测：取证前后 `shutil.which` 对三者都返回 null。
- **PI_CODING_AGENT_DIR**：操作者记录为指向新建的空目录 `<TEMP>/codekit-empty-pi-agent-*`，用来避免读取真实的 `~/.pi/agent`（source_reported）。
  - 实测：取证前后该变量都存在。只记录是否存在，不记录值。
  - 控制台记录的最后一行 `0` 是该目录在取证后的条目数。产生这一行的命令没有随记录保存，所以这一条按 source_reported 处理。
  - 取证前该目录是否为空，也只有操作者记录。
- **对被测代码的影响**：受控 PATH 与空 agent 目录使部分旧分支没有执行，见第 10 节“受控环境改变的代码路径”。
- **unset**：取消了名为 `CLAUDE_CODE_MESSAGING_TOKEN` 的会话令牌变量，这里只记录名称。
- **子进程环境**：由 `pi_dispatch.child_env({})` 生成。
  - 新增 `GCM_INTERACTIVE`、`GIT_TERMINAL_PROMPT`、`PYTHONDONTWRITEBYTECODE`；
  - 没有移除任何变量；
  - 其余变量原样继承。
- **操作命令**：`python scripts/codekit/baseline.py capture --out-root .agent/baseline/01-T1 --capture-id bl-01t1-legacy-20260925 --timeout 3600 -- python tests/test_dispatch.py`

### 3.3 隔离事实

- **网络**：没有隔离，也没有监测。取证工具本身不提供网络隔离、凭据隔离或沙箱。
- **凭据**：只做到部分隔离。
  - 真实的 `~/.pi/agent` 由空目录代替，会话令牌变量已取消；
  - 测试把其余环境变量原样传给子进程（`BASE_ENV = dict(os.environ)`）；
  - 静态核实没有发现打印或写出变量值的路径。
- **离线边界静态核实**：P0.2，属于 source_inspected。
  - 按原样运行时 `safe_to_run=false`，有两个阻断项：doctor 会运行真实的 `claude/codex --version`；run 与 doctor 会读取真实的 `~/.pi/agent/settings.json`。
  - 两项都由上述受控条件消除，没有修改任何文件。
  - 真实 CLI 的 `--version` 是否联网，无法从本仓库证明。
- **进程监督**：`run_supervised` 使用 Windows Job Object，时限 3600 秒，宽限 15 秒。本次没有超时、没有中断，也没有残留进程。

## 4. 前后采样对比

- 取证前采样：12:47:48.287Z–12:47:49.382Z。
- 取证后采样：12:51:59.596Z–12:52:00.437Z。
- 两次采样都完整（complete），problems 为空。
- 比较结果：`baseline_consistent=true`，`drift=[]`，`observations=[]`，`unavailable=[]`。

| 采样项 | 取证前 | 取证后 | 一致 |
|---|---|---|---|
| HEAD | `a4fa199b0e5b…6723940` | 同左 | 是 |
| 对象格式 / HEAD 类型 | sha1 / commit | 同左 | 是 |
| porcelain（`-z --untracked-files=all`） | 1562 B，37 项，`9a2b8af012ab7e6e…` | 同左 | 是 |
| 含忽略项的 porcelain | 1628 B，`7739631de3661655…` | 同左 | 是 |
| 输入清单 / 闭包 | `6aea1cc0b4db213d…` / `8ca10fb98b8d9721…` | 同左 | 是 |
| 未暂存差异 | 242653 B，`9e3f081efa6d7699…` | 同左 | 是 |
| 已暂存差异 | 0 B | 0 B | 是 |
| `ls-files` | 2293 B，`28508ea17db03d87…` | 同左 | 是 |
| Git 版本 / core.* 配置 | 见 3.1 | 同左 | 是 |
| bash 版本首行 | GNU bash 5.3.15(2)-release | 同左 | 是 |
| 环境事实（environment.json） | 原始 `e21e2d2fbc7d39ca…` | 同左 | 是 |
| 忽略项名称 / 排除计数 | 2 个 / `.agent/baseline/`：忽略名 1，输入 0 | 同左 | 是 |

这项一致只说明取证期间上述采样项没有变化，有两点不能由此推出：
- 不能证明被测命令实际读取的就是这些字节：读取与使用之间的竞态没有消除，采样也不是原子快照。
- 不覆盖被忽略文件的内容，也不覆盖仓库外的输入。

## 5. 项目旧自测（legacy_project 栏）

- **命令**：`python tests/test_dispatch.py`，cwd 为仓库根，argv[0] 解析为 `<PYDIR>\python.EXE`。
  - 在 `run_supervised` 中运行，stdin 接 devnull，`shell=False`；
  - 开始 12:47:49.383Z，结束 12:51:59.594Z，耗时 250.219 秒。这只是一次记录，不是性能基准。
- **结果**（measured）：
  - 退出码 0，没有超时、中断或残留进程；
  - 汇总行为 `256 checks, 0 failed`；
  - PASS 行 256 条，FAIL 行 0 条；
  - stderr 0 字节，没有 traceback；
  - 24 个分节，与源码中 24 个 `test_*` 函数逐一对应、顺序相同；
  - 没有 `not exercised` 占位检查，也没有 `NOTE` 行。
- **旧框架的两个陷阱都没有触发**：
  - 测试名拼错时会输出 `0 checks` 却退出 0；
  - 汇总之后如果清理出错，退出码会变成 1。
  - 本次同时核对了汇总行、分节数和退出码。

以下每个函数一条子检查。证据是 `evidence/bl-01t1-legacy-20260925/run/stdout.bin`，SHA-256 为 `f40586e2376e2361bc962878059d732b95c2c8cb0f79d48c3fd069fc37e1080e`；“行”指该文件的行号。

| # | 函数 | 源码行 | 检查数 | 状态 | stdout 行 | Windows 平台说明 |
|---|---|---|---|---|---|---|
| 1 | test_happy | 241 | 18 | PASS | 1–19 | |
| 2 | test_candidate_drift_and_artifacts | 287 | 5 | PASS | 20–25 | |
| 3 | test_cleanup_protects_unsaved_work | 315 | 2 | PASS | 26–28 | |
| 4 | test_budget_race | 330 | 1 | PASS | 29–30 | 失败一方的退出码没有断言 |
| 5 | test_scope | 346 | 7 | PASS | 31–38 | |
| 6 | test_events_and_thinking | 367 | 11 | PASS | 39–50 | |
| 7 | test_commit_outside_main | 404 | 6 | PASS | 51–57 | |
| 8 | test_timeout | 425 | 3 | PASS | 58–61 | 用 tasklist/taskkill 判断和结束进程；kill_method=job-object |
| 9 | test_dispatcher_killed | 443 | 3 | PASS | 62–65 | 断言 Job Object 回收（Linux 分支断言 PDEATHSIG，其他平台只打印 NOTE）；恢复后的状态接受 CANCELLED 或 INFRA_FAILURE，不锁定其一 |
| 10 | test_stuck_states | 479 | 3 | PASS | 66–69 | |
| 11 | test_preflight_and_budget | 495 | 7 | PASS | 70–77 | |
| 12 | test_validate | 520 | 18 | PASS | 78–96 | |
| 13 | test_output_paths | 584 | 3 | PASS | 97–100 | |
| 14 | test_units | 597 | 3 | PASS | 101–104 | alive() 用 tasklist |
| 15 | test_repo_config_features | 625 | 6 | PASS | 105–111 | |
| 16 | test_wrapper_interpreters_and_literal_arguments | 656 | **0** | **NOT_RUN** | 112 | 源码第 658–659 行在 Windows 上直接 return；该分节没有任何检查行。<br>这是测试自身的平台条件，没有确认 Windows 缺少被测能力，所以不记 UNSUPPORTED。<br>POSIX 分支中的解释器候选回退、字面参数保留本次没有验证 |
| 17 | test_setup_wrapper_doctor | 701 | 11 | PASS | 113–124 | 用 Git Bash 运行 `dispatch-pi.sh validate`（bash wrapper finds python），只覆盖包装脚本能找到 python |
| 18 | test_feedback_v11 | 814 | 28 | PASS | 125–153 | |
| 19 | test_feedback_v12 | 936 | 34 | PASS | 154–188 | |
| 20 | test_mutate | 1220 | 7 | PASS | 189–196 | |
| 21 | test_v2_planner_adapters | 1275 | 18 | PASS | 197–215 | |
| 22 | test_v2_review_fixes | 1380 | 16 | PASS | 216–232 | junction 与文件符号链接用例都实际执行，没有空通过 |
| 23 | test_v21_codex_trial_feedback | 1531 | 29 | PASS | 233–262 | |
| 24 | test_v22_netperf_feedback | 1782 | 17 | PASS | 263–280 | |
| | **合计** | | **256** | 23 PASS / 1 NOT_RUN | 282：汇总行 | |

函数名中的 `v11`、`v12`、`v2`、`v21`、`v22` 是工具的历史版本号，不表示覆盖了新架构（3.1、7.1）。

Linux 与 macOS 上的旧自测都记为 **NOT_RUN**（01-D10、7.5）：本次只有一台 Windows 主机，不从 Windows 结果推导其他平台。

## 6. 参考代码验证（reference_code 栏，与第 5 节分栏）

本栏只验证 01 文档附录 B 的参考代码，不是项目自测。本栏的结果不影响第 5 节的判定，第 5 节的 PASS 也不能代替本栏（01-A16）。证据在 `evidence/reference-appendix-b-windows/`。

### 6.1 参考文件摘要（reference-hash-e2：PASS，measured）

| 文件 | 字节 | SHA-256 | 附录 E.2 | 仓库文档代码块（围栏行） |
|---|---|---|---|---|
| protocols_reference.py | 11033 | `ca149cef68097bb00969b79051ad2fae7fb0eba58bd610cf377c38f21a089da1` | 一致 | 1781，一致 |
| test_protocols_reference.py | 6822 | `b6ed4dee87999fca951cc5f9084632393928f56681ca8928802ff6b825897d78` | 一致 | 2055，一致 |
| public-protocol.schema.json | 13335 | `7895442dc9907b6ab1a0c1dd946a1b0caaf2cdd49caaa1ebabff94fa10cdf291` | 一致 | 1117，一致 |

### 6.2 参考自测（reference-appendix-b-selftest-windows：FAIL，measured）

命令 `python -m unittest -v test_protocols_reference`，在参考文件所在目录运行，并设置 `PYTHONDONTWRITEBYTECODE=1`。

| 运行 | 说明 | 结果 | 退出码 |
|---|---|---|---|
| original | 规划端较早的运行，是本任务的输入。<br>在 Git Bash 中于 `<SCRATCHPAD>/ref` 执行；命令取自规划端的工具调用记录（source_reported）。<br>输出中没有记录解释器版本 | 21 项：19 ok、1 FAIL、1 skipped | 1 |
| rerun | 报告生成时的复核运行，在一次性临时目录中执行，结束后已删除。解释器为 CPython 3.12.10 | 21 项：19 ok、1 FAIL、1 skipped | 1 |
| diagnostic-long-temp | 对照运行：把 TMPDIR、TEMP、TMP 设为不含 8.3 短名的长名路径 | 21 项：20 ok、1 skipped | 0 |

- **失败项 `test_static_resolution`**：
  - 测试把 `resolve_existing_path_for_review()` 的返回值与 `TemporaryDirectory()` 给出的根路径直接比较。前者由 `Path.resolve` 得到，是长名路径；后者是本机系统临时目录的 8.3 短名写法。
  - 两者文字不同，断言失败。脱敏后的断言消息保留了这一区别：`WindowsPath('<TEMP>/tmp…/ok.txt') != WindowsPath('<TEMP:8.3>/tmp…/ok.txt')`。
  - 对照运行改用长名后，该用例通过。
  - 结论：这是测试写法的平台问题，比较前期望值没有做 resolve。它不能证明参考实现在 Windows 上的静态解析正确，也不能证明它错误。
- **跳过项 `test_static_symlink_escape`**：非 POSIX 平台上跳过，单列，不计为 Windows 物理边界能力通过（附录 B.3、01-D06）。
- 参考代码与参考测试都没有修改。失败记录保留，不靠改写测试换取通过。

### 6.3 其他参考项

| 检查 | 状态 | 依据 | 说明 |
|---|---|---|---|
| reference-schema-metavalidation-windows | BLOCKED | measured | 本机没有 jsonschema（`import jsonschema` 报 ModuleNotFoundError），且不授权安装。按 2.4，缺工具与授权属于 BLOCKED。`01-baseline/README.md` 在本报告修订 2 时仍写作 NOT_RUN，与本报告和 2.4 不一致，已提请规划端改为 BLOCKED |
| reference-appendix-b-selftest-linux | NOT_RUN | source_reported | 附录 E.1 记载作者在 Linux 沙箱（Python 3.13.5）上 21 项通过。这是文档自述，不对应本仓库提交，不计为本项目实测 |
| reference-appendix-b-selftest-macos | NOT_RUN | unknown | 没有 macOS 环境，也没有任何来源记载 macOS 结果 |

## 7. 旧行为清单与 G0–G6（引用）

旧行为清单、G0–G6 表与回归映射由并行任务写在 [legacy-inventory.md](legacy-inventory.md)。

- **引用版本**：本报告初版生成时该文件尚未产生。修订 2 核对的版本为 399136 字节，SHA-256 `f8aab15808c8629b3e1a322c48efc20d1e07fa538a7576615bb55a83eea7d8ac`（LF 行尾）。清单尚待 P4 定稿与独立复审，再修改时由 P4 重新固定摘要。
- **修订 2 的核对**（measured，按清单 0.2 的匹配规则逐行比对 `run/stdout.bin`）：
  - 第 9 节共 224 行。169 行 measured/PASS 登记的 check 全部在对应分节中以 PASS 出现，所标计数一致；
  - 5 行带测试的 NOT_RUN（LB-LIFE-021、LB-EXIT-004、LB-TEST-009、LB-TEST-016、LB-TEST-COV-10）各缺本机不产生的 “PDEATHSIG stops pi” 或 POSIX 包装脚本 check；
  - 50 行没有登记测试；
  - 第 10 节 C.4 覆盖表 12 行，计数一致。

下表由两部分合并而成，最终以清单为准：
- 本报告对 `tests/test_dispatch.py` 的独立源码核对，属于 source_inspected；
- 本次运行结果，属于 measured。

门禁名称来自 `.agents/skills/review-pi/gates.md`（source_reported）；`scripts/pi_dispatch.py` 中只有编号。

| 门禁 | 名称 | 有断言的失败路径测试 | 已有测试（Windows 结果） | 缺口 |
|---|---|---|---|---|
| G0 | 输入一致 | **无** | 只有正向用例：test_happy 中 PASS 被接受。PASS | plan.md 或 contract.json 哈希不符、基线提交不可用，都没有测试 |
| G1 | 执行完整 | 部分 | test_events_and_thinking：“PASS refused on G1”。<br>test_feedback_v12：textual tool call 被拒。<br>均 PASS | run.json 缺失、超时、中断、退出码非 0，在 verdict 层没有断言 |
| G2 | 范围合规 | 部分 | test_scope：“PASS refused on scope violation (G2)”。PASS | scope.json 缺失没有测试 |
| G3 | 行为正确 | **无** | 只有备注：test_feedback_v12 打印 G3 备注。PASS | DoD 引用的检查失败、没有有效检查记录，都没有断言。<br>scope 证据失败会在 test_scope 中触发，但测试只断言了 G2 |
| G4 | 回归检查 | 部分 | test_candidate_drift_and_artifacts：“PASS refused when checks created files (G4)”。PASS | 检查不是针对当前候选、`--only` 未覆盖必要检查、必要检查未运行或失败、检查修改了候选文件，都没有测试 |
| G5 | 质量复审 | **无** | 没有专门测试 | 工具不做机械判定，恒为通过，由复审报告负责 |
| G6 | 可集成 | **无** | 只有正向用例：test_v22 中 autocrlf 改动后 PASS 仍然成立。PASS | “记录后被修改”在 test_cleanup_protects_unsaved_work 中触发，但没有断言。<br>只差行尾的专门消息、candidate.patch 被篡改、往返校验失败，都没有测试 |

01-A07 的其他项：

| 项 | 测试 | Windows 结果 | 缺口 |
|---|---|---|---|
| 范围 | test_scope、test_commit_outside_main、test_repo_config_features | PASS | |
| 候选漂移 | test_candidate_drift_and_artifacts：check 拒绝，退出码 4 | PASS | |
| 预算竞争 | test_budget_race | PASS | 失败一方的退出码没有断言 |
| 取消 | test_dispatcher_killed：调度器被强杀后恢复 | PASS | 最终状态不锁定；KeyboardInterrupt 路径没有测试 |
| 补丁完整性 | test_happy：“candidate roundtrip verified” | PASS | 只有正向用例；补丁缺失、被篡改、sha256 不符、往返失败，都没有负向测试 |

以上两张表描述实施前的覆盖，只针对 `tests/test_dispatch.py`，对旧自测本身仍然成立。

### 7.1 修订 3 更新：P4 之后（只限 Windows）

- **引用版本**：545582 字节，2700 行，LF 行尾，SHA-256 `f6279547b8f780e28b11c371fb137bd4dd9aa8c868bdddf831a6b9b32cf56ee8`。
  - **修订 4 更新**：清单在完整性审查后更新为 570632 字节，2828 行，SHA-256 `a9d3d189f6153728d54b0bd146913193daaea235989391d34195b4f5e3f350a7`（JSON `legacy_inventory.ref`）。只新增第 9.10 节（文档 3.2 的 input_fixture_ref 与 comparison_projection_revision 按行回填：224 行中 43 行关联到 legacy fixture 与比较投影 `codekit01-legacy-projection-v1`，181 行 NOT_COVERED；第 12 节 159 个方法两个字段都为空），并在第 0.4、9.1、11.6、12.9 节与开头加注记；第 2、10 节与第 12.1–12.8 节没有改动。下面“修订 3 的核对”与 01-A07 的判定对应上一行的修订 3 版本，该版本已移入 `legacy_inventory.ref_history`。
  - **修订 6 更新**：清单在收尾取证之后由清单代理更新为 **721294 字节，3419 行，SHA-256 `9fdba24ca5de15b4cb75c206caf1e9633bb6866f0f2a8d12372ded225792adc4`**（JSON `legacy_inventory.ref`；修订 4、5 引用的 570632 字节版本 `a9d3d189…` 移入 `ref_history`，它也是收尾取证输入清单记录的版本）。清单代理只追加或加注：
    - 第 0.5 节末尾追加收尾取证表（10 次取证的归档路径、字节数与 sha256）；
    - 新增 9.10.5（D-20–D-23 新增合同负例的 manifest 回填）、9.10.6（按 R-P12 逐行回填：224 行中 157 行至少有一种 fixture 引用，NOT_COVERED 由 181 行降为 67 行）、9.10.7（文档 6.6 七类标为“旧路径已锁定，差分 NOT_RUN（新路径不存在）”）、12.10（159 个方法的 `inline:<测试文件>::<类>.<方法>@<sha256>` 与 `codekit01-characterization-v1`）；
    - 第 12 节 159 个结果格先引用 `bl-01closure-*`，原 `bl-01final-*` 写在“历史：”之后；M-08 的三处措辞改为“01 新代码测试（公共协议、fixtures、取证工具）”。
    - 修订 6 的只读核对（measured）：12.10 有 159 行内联引用，159 个编号各不相同，156 行记 measured / PASS、3 行记 NOT_RUN，所引 4 个测试文件的 sha256 与收尾取证输入清单相同；第 12 节 159 个结果格都引用 `bl-01closure-*`；收尾取证 4 份归档输出中 159 个方法 156 个 ok、3 个 skipped，与清单一致（JSON `legacy_inventory.verification_revision_6`）。
    - 9.10.6 的 67 行 NOT_COVERED 中，(c) 类 23 行只有旧自测模块级函数的 check，R-P12 没有规定其写法，清单代理没有自行扩展；是否补登由规划端决定（第 8 节 01-A07）。
  - 清单编写者交付时报告的摘要与此相同，修订 3 写入前后各核对一次，字节没有变化。
  - 修订 2 核对的版本（399136 字节，`f8aab158…`）记在 JSON `legacy_inventory.ref_history`；上面的“修订 2 的核对”对应那一版。
  - `docs/code-kit-v2/01-baseline/**` 已设 `-text`（01-L06），本机 autocrlf 不会改变检出字节。清单再修改时须重新固定摘要。
- **清单新增的内容**：第 0.5 节（最终取证）、第 12 节（P4 特征化回归，159 个方法），以及第 2、9、10、11.5 节的“P4 更新”。第 9 节中描述旧自测的两列没有改动，P4 对原 NOT_RUN 行的覆盖另列在 9.9（01-A16 分栏）。
- **修订 3 的核对**（measured）：
  - 第 12 节 159 行逐条同 4 份归档 `run/stderr.bin` 的 unittest 逐条输出比对。159 行都能在输出中找到，输出中也没有第 12 节之外的方法；156 行 ok，都记 measured / PASS；3 行 skipped，都记 NOT_RUN；状态不符 0。
  - 第 0.5、12.2 节登记的摘要与归档文件、最终取证输入清单一致。
  - 最终取证的旧自测输出与 bl-01t1 逐字节相同，所以修订 2 对第 9、10 节的逐行核对结论同样适用。
  - 另抽查了 `test_legacy_gates.py`、`test_legacy_lifecycle.py` 中的关键断言字符串，确认它们出现在 assert 调用中。这只是抽查（source_inspected），不代替逐条复核。

P4 之后 01-A07 各项的覆盖如下。方法都在 Windows 上 measured / PASS，只有注明 NOT_RUN 的除外；方法名与所属取证见第 7.2 节。

| 项 | 实施前（bl-01t1） | P4 方法 | P4 关闭的缺口 | 仍有的缺口 |
|---|---|---|---|---|
| G0 输入一致 | 没有失败路径测试 | P4-G01 | plan.md 被改或缺失、contract.json 被改 → 哈希不一致；base_sha 不可用 →“基线提交不可用”；meta.json 不校验；contract.json 缺失或不是 JSON 时回溯退出 1（可疑） | 无 |
| G1 执行完整 | 只有事件类失败 | P4-G02–G05、G07、G24、L01、L05、L22、E20；<br>P4-L03 NOT_RUN | 缺 run.json 与缺事件摘要、没有 agent_settled、Pi 非 0 退出而 run 为 0、超时、取消（Windows CTRL_BREAK）、恢复合成 run.json、INFRA_FAILURE 可复审 | POSIX 的 SIGINT 取消 |
| G2 范围合规 | 只有范围违规一种失败 | P4-G08、G09 | 违规逐行、缺 scope.json；主工作区变化的备注写入 verdict 记录 | “执行器访问了工作副本外路径”备注未经 verdict 断言；diff_error 时没有备注 |
| G3 行为正确 | 只有备注 | P4-G08、G10–G12、G14、G18 | 没有有效的独立检查记录、scope 证据失败、检查引用失败、review 证据被跳过 | 合同矛盾备注未经 verdict 断言 |
| G4 回归检查 | 只有“产生候选外新文件” | P4-G10、G11、G13、G14、G18 | 无有效记录、非当前候选、未覆盖必要检查、修改候选文件、必要检查失败 | 干净副本模式的备注未经 verdict 断言 |
| G5 质量复审 | 没有测试 | P4-G09、G23 | 恒通过与固定备注出现在 PASS 记录与失败记录中 | 没有可测的失败路径（不是测试缺口） |
| G6 可集成 | 只有正向 | P4-G13、G15–G17 | 记录后修改与删除、只差行尾的专门消息、无法重新快照、worktree 不存在时只查补丁、补丁缺失/字节被改/sha256 不符/往返标记为 false | 真实的往返失败（P4 改写记录字段模拟）；重新快照写 Git 对象未断言 |
| verdict 拒绝分支 | 没有测试 | P4-G20–G23、C58、C59 | 全部拒绝分支、非 REVIEWABLE 状态、重复记录 | 无 |
| 范围 | 越界、受保护路径、依赖变更、head_moved | P4-G08、C25–C28（白盒）、C72–C75（端到端） | 删除越界、大小写不同的受保护路径、符号链接、local_commit 下 head_moved 降为警告 | submodule、普通文件 mode_changed、sensitive_file、dependency_manifest_changed、真实的非 UTF-8 文件名、review_hints |
| 候选漂移 | verdict 层没有断言 | P4-G09、G13–G15、C62 | check 前修改候选文件（退出 4）、verdict 时 G6 漂移、新增文件只作备注、只差行尾的专门消息、cleanup 拒绝码 | 无 |
| 预算竞争 | 落败方退出码没有断言 | P4-G06、L06–L16、L18–L21 | 落败方退出 3 且保持 PREPARED、锁外次数预检、墙钟预算、剩余不足 60 s 及其边界、--timeout 被截短、锁等待 30 s、300 s 过期接管、释放锁时不核对归属（L20、L21 为白盒） | 真实并发竞态、mtime 语义与时钟偏差、owner.json 的 FileExistsError、同一 attempt 的 claim 冲突、限额来源不同 |
| 取消 | 没有信号用例 | P4-G07、L01、L02、L22、C68–C71；<br>P4-L03、L04 NOT_RUN | Windows CTRL_BREAK：CANCELLED 且 run 退出 1、G1“运行被取消或调度器中断”；领取前与 wait 轮询中以 0xC000013A 结束；setup 中为 PREPARE_FAILED；恢复结果锁定为 CANCELLED | POSIX SIGINT；经子进程到达的 130；:3319-3332 窗口与 collect 期间；_terminate_tree 期间再收到信号；SIGTERM、SIGHUP |
| 补丁完整性 | 只有正向 | P4-G16–G19、C63 | G6 的四种补丁失败；--fresh 与 mutate 对“字节被改”的拒绝；branch 按补丁重建及其失败；cleanup 的 LOSS | --fresh/mutate 对其余三种情形的拒绝；真实的 apply --cached 失败 |

另外，P4-C29（白盒）锁定 main 把 KeyboardInterrupt 映射为 130；清单把它归入六类之外（01-A05）。

### 7.2 01-A07 相关方法索引

各方法的结果都取自所属取证的归档 `run/stderr.bin`，sha256 见第 12.2 节。下表的“取证 ID”列是修订 3 写下的最终取证，保留不改；**修订 6 的判定依据收尾取证**：同样 62 个方法在 `bl-01closure-test-legacy-{gates,lifecycle,cli,events}-20260926` 的归档输出中逐个定位，60 个 ok，P4-L03、L04 skipped，结果与下表相同。各方法在收尾取证中的 stderr 行号见第 13.4 节与 JSON `closure_regression.method_results.a07_indexed_methods`，归档路径与 sha256 见第 13.2 节。

| 编号 | 测试方法（类.方法） | 取证 ID | 结果 |
|---|---|---|---|
| P4-G01 | `G0InputConsistency.test_lb_gates_024_g0_hash_base_and_contract_failures` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G02 | `G1ExecutionComplete.test_lb_gates_025_g1_missing_run_json_and_events_summary` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G03 | `G1ExecutionComplete.test_lb_gates_025_g1_event_problem_nosettle` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G04 | `G1ExecutionComplete.test_lb_gates_025_g1_nonzero_pi_exit_only_caught_by_gate` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G05 | `G1ExecutionComplete.test_lb_life_016_timeout_run_exit_1_and_g1_timeout` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G06 | `G1ExecutionComplete.test_lb_life_011_timeout_flag_cannot_exceed_budget` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G07 | `G1ExecutionComplete.test_lb_life_017_interrupt_during_run_is_cancelled_exit_1` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G08 | `G2Scope.test_lb_gates_026_g2_violation_missing_scope_and_g3_scope_evidence` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G09 | `GateNotes.test_lb_gates_023_notes_never_block_pass_and_g5_constant` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G10 | `G3G4Checks.test_lb_gates_028_g4_partial_coverage_and_stale_candidate` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G11 | `G3G4Checks.test_lb_gates_028_g4_required_check_failed` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G12 | `G3G4Checks.test_lb_gates_027_g3_dod_evidence_on_optional_check` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G13 | `G3G4Checks.test_lb_gates_014_g4_check_modified_candidate` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G14 | `CandidateDrift.test_lb_gates_013_check_refuses_modified_candidate_and_aborted_record_blocks` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G15 | `G6Integrable.test_lb_gates_030_g6_drift_after_record` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G16 | `G6Integrable.test_lb_gates_030_g6_worktree_missing_skips_drift_but_checks_patch` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G17 | `PatchIntegrity.test_lb_gates_006_g6_patch_missing_tampered_sha_and_roundtrip` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G18 | `PatchIntegrity.test_lb_gates_012_fresh_check_and_mutate_refuse_bad_patch` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G19 | `PatchIntegrity.test_lb_gates_035_branch_patch_rebuild_paths` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G20 | `VerdictRules.test_lb_gates_031_state_not_reviewable` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G21 | `VerdictRules.test_lb_gates_032_verdict_rejection_branches` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G22 | `VerdictRules.test_lb_gates_032_waiver_rules_when_all_gates_pass` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G23 | `VerdictRules.test_lb_gates_033_repeat_verdict_increments_number` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-G24 | `VerdictRules.test_lb_gates_033_infra_failure_attempt_is_reviewable` | `bl-01final-test-legacy-gates-20260925` | measured / PASS |
| P4-L01 | `CancelTests.test_LB_LIFE_017_ctrl_break_during_pi_run_is_cancelled_exit_1_not_130` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L02 | `CancelTests.test_LB_LIFE_035_ctrl_break_before_claim_kills_dispatcher_without_130` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L03 | `CancelTests.test_LB_LIFE_017_sigint_during_pi_run_is_cancelled_exit_1_posix` | `bl-01final-test-legacy-lifecycle-20260925` | NOT_RUN（skipped，POSIX 分支） |
| P4-L04 | `CancelTests.test_LB_LIFE_035_sigint_before_claim_exits_130_posix` | `bl-01final-test-legacy-lifecycle-20260925` | NOT_RUN（skipped，POSIX 分支） |
| P4-L05 | `TimeoutTests.test_LB_LIFE_016_timeout_run_exits_1_and_pass_refused_by_g1` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L06 | `BudgetTests.test_LB_LIFE_012_budget_race_loser_stays_prepared_exit_3` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L07 | `BudgetTests.test_LB_LIFE_012_run_count_precheck_outside_lock_refuses_before_preflight` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L08 | `BudgetTests.test_LB_LIFE_009_wall_budget_counts_actual_wall_seconds_from_run_json` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L09 | `BudgetTests.test_LB_LIFE_009_wall_seconds_null_falls_back_to_reservation` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L10 | `BudgetTests.test_LB_LIFE_010_wall_total_exhausted_refused_by_run_and_prepare` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L11 | `BudgetTests.test_LB_LIFE_011_remaining_wall_under_60s_run_refused_but_prepare_allowed` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L12 | `BudgetTests.test_LB_LIFE_011_remaining_wall_exactly_60s_is_allowed` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L13 | `BudgetTests.test_LB_LIFE_011_remaining_wall_59s_is_refused` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L14 | `BudgetTests.test_LB_LIFE_011_timeout_flag_capped_by_per_attempt_budget` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L15 | `BudgetTests.test_LB_LIFE_011_negative_timeout_flag_becomes_1s` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L16 | `BudgetTests.test_LB_LIFE_011_timeout_flag_capped_by_remaining_total_budget` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L18 | `TaskLockTests.test_LB_LIFE_005_held_task_lock_run_waits_30s_then_exit_3` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L19 | `TaskLockTests.test_LB_LIFE_006_stale_task_lock_taken_over_by_run` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-L20 | `TaskLockTests.test_LB_LIFE_005_task_lock_wait_timeout_and_stale_takeover_whitebox` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS（白盒） |
| P4-L21 | `TaskLockTests.test_LB_LIFE_006_task_lock_release_ignores_ownership_whitebox` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS（白盒） |
| P4-L22 | `RecoverTests.test_LB_LIFE_024_recover_refused_while_pi_alive_then_recovers_cancelled` | `bl-01final-test-legacy-lifecycle-20260925` | measured / PASS |
| P4-C25 | `LegacyScopeInProcessTest.test_LB_GATES_018_deleted_file_outside_allowed_deleted_is_out_of_scope` | `bl-01final-test-legacy-cli-20260925` | measured / PASS（白盒） |
| P4-C26 | `LegacyScopeInProcessTest.test_LB_GATES_017_protected_paths_ignore_case_scope_lists_do_not` | `bl-01final-test-legacy-cli-20260925` | measured / PASS（白盒） |
| P4-C27 | `LegacyScopeInProcessTest.test_LB_GATES_018_new_symlink_is_violation_symlink_to_file_is_silent` | `bl-01final-test-legacy-cli-20260925` | measured / PASS（白盒） |
| P4-C28 | `LegacyScopeInProcessTest.test_LB_GATES_019_head_moved_is_warning_only_with_local_commit` | `bl-01final-test-legacy-cli-20260925` | measured / PASS（白盒） |
| P4-C58 | `LegacyRefusalCodesTest.test_LB_EXIT_014_verdict_on_unreviewable_state_is_3` | `bl-01final-test-legacy-cli-20260925` | measured / PASS |
| P4-C59 | `LegacyRefusalCodesTest.test_LB_EXIT_014_verdict_usage_2_and_gate_refusal_1` | `bl-01final-test-legacy-cli-20260925` | measured / PASS |
| P4-C62 | `LegacyRefusalCodesTest.test_LB_EXIT_017_cleanup_refusal_codes` | `bl-01final-test-legacy-cli-20260925` | measured / PASS |
| P4-C63 | `LegacyRefusalCodesTest.test_LB_GATES_037_cleanup_refuses_when_candidate_patch_tampered` | `bl-01final-test-legacy-cli-20260925` | measured / PASS |
| P4-C68 | `LegacyRunOutcomeTest.test_LB_LIFE_019_timed_out_and_interrupted_resolves_to_timeout` | `bl-01final-test-legacy-cli-20260925` | measured / PASS |
| P4-C69 | `LegacyRunOutcomeTest.test_LB_EXIT_031_interrupt_during_pi_is_cancelled_exit_1` | `bl-01final-test-legacy-cli-20260925` | measured / PASS |
| P4-C70 | `LegacyRunOutcomeTest.test_LB_LIFE_035_interrupt_during_prepare_setup_is_prepare_failed_exit_1` | `bl-01final-test-legacy-cli-20260925` | measured / PASS |
| P4-C71 | `LegacyRunOutcomeTest.test_LB_LIFE_035_ctrl_break_in_wait_loop_is_not_handled` | `bl-01final-test-legacy-cli-20260925` | measured / PASS |
| P4-C72 | `LegacyScopeEndToEndTest.test_LB_GATES_018_e2e_deleted_file_is_out_of_scope_run_still_0` | `bl-01final-test-legacy-cli-20260925` | measured / PASS |
| P4-C73 | `LegacyScopeEndToEndTest.test_LB_GATES_017_e2e_case_variant_protected_paths` | `bl-01final-test-legacy-cli-20260925` | measured / PASS |
| P4-C74 | `LegacyScopeEndToEndTest.test_LB_GATES_018_e2e_new_symlink_is_violation` | `bl-01final-test-legacy-cli-20260925` | measured / PASS |
| P4-C75 | `LegacyScopeEndToEndTest.test_LB_GATES_019_e2e_local_commit_head_moved_is_warning` | `bl-01final-test-legacy-cli-20260925` | measured / PASS |
| P4-E20 | `EventStreamRunTests.test_LB_EVENTS_021_nonzero_pi_exit_with_complete_events` | `bl-01final-test-legacy-events-20260925` | measured / PASS |

## 8. 验收判定

修订 6 依据第 13 节的 10 次收尾取证与 [decisions.md](decisions.md) 的收尾轮裁决 R-01（A01 的 pyc 口径）、R-02（A07 的口径）给出判定；所依据的 decisions.md 为 20186 字节，sha256 `8b460b2d57f1e0e8c1ea2cc2da140c66e186f92425a8d8a586a2eb51ececbb61`，与收尾取证输入清单的记录相同。判定由报告编写者给出，待独立复审。修订 3 的判定原文保留在本节第二张表，修订 2 的初判见本节末尾的“判定历史”。

| 编号 | 判定（修订 6） | 依据 | 证据与说明 |
|---|---|---|---|
| 01-A01 | **PASS**（限 Windows；以 10 次收尾取证为依据；R-01 严格 pyc 口径，受控禁用的依据是操作者记录；输入闭包 partial） | measured（pyc 的受控禁用：source_reported） | **核对内容**：报告把 10 次收尾取证（第 13 节）逐一关联到：<br>- 40 位 HEAD `a4fa199…`（sha1，与调查提交一致）、平台与工具链、argv 与 cwd；<br>- 退出码 0，timed_out、interrupted、stray_processes 都为 false，spawn_error 为 null；<br>- 汇总行的文件与行号；<br>- 前后采样：10 次都 `baseline_consistent=true`，drift 为空，20 次采样的工作区状态相同；<br>- 输入清单：1073 项，闭包 `81b4503e…`，pre 与 post 相同；<br>- archive-manifest.json、capture.json、run/stdout.bin、run/stderr.bin 的仓库相对路径与 sha256（第 13.2 节）。<br>**没有把未通过或未运行的项记为通过**：7 个跳过方法记 NOT_RUN（6）与 BLOCKED（1）；`test_wrapper_interpreters_and_literal_arguments` 仍为 NOT_RUN；参考自测仍为 FAIL；Linux、macOS 为 NOT_RUN。fixtures 这次以 `-v` 运行，75 个方法都有方法名。<br>**缺输入的判断（R-01）**：<br>- 仓库内：输入清单 1073 项中 1067 项计了摘要，另 6 项是已删除的旧文档；不计摘要的只有被忽略的 `scripts/__pycache__/`、`tests/__pycache__/`（measured）。收尾取证以 `PYTHONPYCACHEPREFIX` 指向取证前为空的目录，使进程内导入不读这两个目录中的 pyc；被测进程由 child_env 补设 `PYTHONDONTWRITEBYTECODE`，不写 pyc（measured）；`tests/test_protocols.py` 以 `-B -I` 启动、不继承该变量的子进程只导入 `scripts/codekit/` 下的模块，取证时那里没有 `__pycache__`（source_inspected 加 measured）。所以在操作者记录成立的前提下，pyc 缺口按 R-01 规定的方式关闭。<br>- 证据等级：设置该变量与“取证前为空”只有操作者记录（`evidence/run-controls-closure/closure-captures.txt` 第 4、6 行，source_reported）；取证工具不记录这个变量，也没有取证后前缀目录的条目数（第 13.5 节）。R-01 要求的是“受控禁用，并在取证记录中写明”，操作者记录满足这一写法，所以判 PASS；如果复审要求由取证工具测得，这一部分只能算操作者声明，本条须改为不满足，待改进取证工具后重新取证。<br>- 旁证：三次旧自测的 stdout 逐字节相同，其中两次读取了 pyc、收尾取证禁用了 pyc（第 13.6 节）；它不代替 R-01 的记录。<br>- 仍在闭包之外：仓库外输入（标准库及其字节码、git 与全局配置、系统工具）与 gitattributes 效果。R-01 针对 pyc，本报告不把它们读作“缺输入”，但 PASS 的范围不含“输入闭包完整”；如果 R-01 也覆盖仓库外输入，现有取证工具的任何一次取证都不满足，本条应改为 FAIL。<br>- 历史证据：`bl-01t1` 与 `bl-01final-test-dispatch` 读取了未计摘要的 pyc，按 R-01 原口径保留、不改写，在严格口径下不满足，不作为本判定的依据。<br>**待规划端决定**：是否接受操作者记录作为受控禁用的依据；R-01 是否覆盖仓库外输入 |
| 01-A07 | **PASS（Windows，范围限定）** | measured | **口径**：decisions.md R-02。六类（G0–G6、范围、候选漂移、预算竞争、取消、补丁完整性）每类、G0–G6 每门都必须有已实测的失败路径断言；满足后记“PASS（Windows，范围限定）”，未覆盖的子分支逐条登记为 unmet_within_scope，迁移比较时记 NOT_COVERED；某一类或某一门没有任何失败路径断言则为 FAIL。<br>**结果**（收尾取证）：4 个特征化测试文件 159 个方法中 156 个 ok、3 个 POSIX 方法跳过，方法集合与结果和最终取证相同；第 7.2 节 62 个方法中 60 个 ok，P4-L03、L04 跳过（第 13.4 节逐个给出 stderr 行号）。逐类、逐门都有 measured / PASS 的失败路径断言方法：G0 P4-G01；G1 P4-G02–G05、G07、G24、L01、L05、L22、E20；G2 P4-G08、G09；G3 P4-G08、G10–G12、G14、G18；G4 P4-G10、G11、G13、G14、G18；G5 P4-G09、G23；G6 P4-G13、G15–G17；范围 P4-G08、C25–C28、C72–C75；候选漂移 P4-G09、G13–G15、C62；预算竞争 P4-G06、L06–L16、L18–L21；取消 P4-G07、L01、L02、L22、C68–C71；补丁完整性 P4-G16–G19、C63。<br>**G5 的读法**：a4fa199 的 G5 恒通过，没有可触发的失败路径；P4-G09、G23 断言它在 PASS 记录与失败记录中都保持通过并带固定备注，本报告把它当作这一门的失败路径映射（与修订 3 相同）。R-02 原文没有单独说到这种门，**请规划端确认**；如果要求 G5 也有可触发的失败断言，那是旧实现中不存在的行为，A07 无法满足。<br>**依据的性质**：方法的运行结果是 measured（收尾取证归档输出）；方法断言了什么取自清单第 12 节登记的测试源码与 docstring（source_inspected），修订 3 抽查过，这 4 个测试文件之后字节未变，修订 6 没有重新核对断言内容。<br>**范围**：Windows Server 2025 + CPython 3.12.10；被测对象为 a4fa199 的 `scripts/pi_dispatch.py`（`a00d6934…`）；测试文件与公共夹具以收尾取证输入清单的字节为准（未提交；夹具由 `3d133d5f…` 改为 `c4e87137…`）。<br>**文档 3.2 的两个字段**：已按 R-P12 回填（清单 12.10、9.10.6、9.10.7），不改变本条口径；9.10.6 仍有 67 行 NOT_COVERED，(c) 类 23 行的登记方式待规划端决定。<br>**性质**：特征化结论，“a4fa199 的现状如此”，不表示现状正确；清单中标“可疑”的现状仍按 legacy-inventory.md 第 11.2 节待裁决 |
| 01-A16 | **PASS** | measured | **分栏**：收尾取证的 10 条命令分四栏记录（JSON `closure_regression.captures[].column`）：<br>- `legacy_project`：tests/test_dispatch.py；<br>- `legacy_characterization`：4 个 P4 特征化回归文件；<br>- `project_protocols`：test_protocols.py、test_codekit01_fixtures.py -v，以及 codekit01_legacy.py 的 `--check`、`--check-stub-regen`（核对 01 新增的兼容 fixtures；归栏是本报告的分类，capture.json 没有栏字段）；<br>- `baseline_tool`：test_baseline_tool.py。<br>附录 B 参考代码的沙箱验证仍在 `reference_code` 栏，证据只在 `evidence/reference-appendix-b-windows/`，最终取证与收尾取证都没有重跑，也没有并入。<br>**互不代替**：旧自测的 PASS 不代替新测试，新测试不代替旧自测，参考自测的 FAIL（`test_static_resolution`）不因项目测试通过而改判。`evidence/closure/INDEX.md` 第 2 节写明 10 次取证都是项目验证、附录 B 参考代码验证是另一栏。<br>**用词差异已关闭**：legacy-inventory.md 第 0.5、12.1 节已按 M-08 改为“01 新代码测试（公共协议、fixtures、取证工具）”（修订 6 只读核对）。<br>**平台适用性**：同修订 4，windows 为 applicable；linux、macos 为 not_applicable（分栏规则不随平台变化），不表示那里有任何测试运行或通过 |
| 01-A02–A06、A08–A15 | **本报告不判定**（不是 NOT_RUN） | — | 同修订 5，见下表同一行。修订 6 按当前 acceptance.md 重新核对了 13 条照录文字，与原文一致；照录所依据的 acceptance.md 字节（138322 字节，sha256 `f01f659ce0b9c5a211e763de4474c844bea6123df6c7b6dc18c8951f0953098e`）与收尾取证输入清单的记录相同。acceptance.md 尚未按收尾取证更新，它更新后以它为准 |

**修订 3 的判定**（修订 4、5 没有改判；修订 6 起为历史记录，原文保留，JSON 中在各条的 `judgment_history` 里）：

| 编号 | 判定（修订 3） | 依据 | 证据与说明 |
|---|---|---|---|
| 01-A01 | **PASS**（限 Windows；输入闭包 partial） | measured | **核对内容**：报告关联两组运行证据，即实施前基线 `bl-01t1-legacy-20260925`（第 2–5 节）与 8 次最终取证（第 12 节）。每一条都记录了：<br>- 40 位 HEAD `a4fa199…`（sha1，与调查提交一致）、平台与工具链、argv 与 cwd；<br>- 退出码 0，timed_out、interrupted、stray_processes 都为 false；<br>- 汇总行的文件与行号；<br>- 前后采样：9 次取证都 `baseline_consistent=true`，drift 为空；<br>- 输入清单：最终取证 373 项，闭包 `2d8f2f71…`，pre 与 post 相同；<br>- archive-manifest.json、capture.json、run/stdout.bin、run/stderr.bin 的仓库相对路径与 sha256。<br>**没有把未通过或未运行的项记为通过**：7 个跳过方法记 NOT_RUN（6）与 BLOCKED（1）；fixtures 只记命令级；`test_wrapper_interpreters_and_literal_arguments` 仍为 NOT_RUN；参考自测仍为 FAIL；Linux、macOS 为 NOT_RUN。<br>**缺输入的判断**：修订 2 留给 P4 的是旧自测在进程内导入时读取、取证时没有计摘要的 `scripts/__pycache__/pi_dispatch.cpython-312.pyc`。最终取证 `bl-01final-test-dispatch-20260925` 同样读取了它，修订 2 的建议没有被采用。<br>- 本报告的判断：它属于取证工具声明的闭包缺口（closure_status=partial，ignored_files_not_hashed），已如实登记，没有据此宣称输入完整；两次事后核对中它的 sha256（`c5b2545e…`）、字节数、mtime（早于两次取证）与头部字段都不变，两次旧自测的 stdout 逐字节相同。因此不把它当作否决 PASS 的“缺输入”，但 PASS 的范围不含“输入闭包完整”。<br>- 其余 7 次取证不读这份 pyc（source_inspected：`legacy_harness`、`codekit01_legacy` 与 `baseline.load_supervisor` 都从源码字节编译执行）。<br>- 如果规划端采用更严的读法（凡被读取的字节都须在取证时计摘要），两条旧自测证据不满足 A01，本条应改为 FAIL；其余 7 条不受影响 |
| 01-A07 | **PASS**（范围限定：Windows） | measured | **口径**：与修订 2 相同。按 7.1 的最低证据“逐条来源测试与断言映射”，六类（G0–G6 逐门计）中每一项都要有可引用、已实测通过的失败路径断言；G5 没有失败路径，以恒通过与固定备注的断言代替；已登记的缺口不算满足。<br>**结果**：修订 2 判 FAIL 的全部理由都已由 P4 特征化回归关闭（第 7.1 节表）：G0 失败路径（P4-G01）；G3、G6 的失败断言；G5 的恒通过；G1、G2、G4 的其余失败原因；取消的信号用例与锁定为 CANCELLED 的恢复；补丁完整性负例；预算竞争落败方的退出码与状态。每个方法都能追到取证 ID、归档 `run/stderr.bin` 的路径与 sha256（第 12.2 节）以及方法名（第 7.2 节）。<br>**依据的性质**：方法的运行结果是 measured；每个方法断言了什么，取自测试源码与 docstring，由清单第 12 节登记，修订 3 只做了抽查。判定不依据测试名称或版本号。<br>**范围**：Windows Server 2025 + CPython 3.12.10；被测对象为 a4fa199 的 `scripts/pi_dispatch.py`（sha256 `a00d6934…`）；测试文件以最终取证输入清单记录的字节为准，尚未提交。<br>**仍有的缺口**（下表）都在某一类的子分支、POSIX 平台或备注层面，没有哪一类或哪一门缺少失败路径断言。按更严的口径（每一条 LB 子行为都须有断言），这些缺口会使 A07 仍为 FAIL；采用哪种口径由规划端决定。<br>**性质**：这是特征化结论，意思是“a4fa199 的现状如此”，不表示现状正确；清单中标“可疑”的现状仍按 legacy-inventory.md 第 11.2 节待裁决 |
| 01-A16 | **PASS** | measured | **分栏**：最终取证的 8 条命令分四栏记录（JSON `post_implementation_regression.captures[].column`）：<br>- `legacy_project`：tests/test_dispatch.py；<br>- `legacy_characterization`：4 个 P4 特征化回归文件；<br>- `project_protocols`：test_protocols.py、test_codekit01_fixtures.py；<br>- `baseline_tool`：test_baseline_tool.py。<br>附录 B 参考代码的沙箱验证仍在 `reference_code` 栏，证据只在 `evidence/reference-appendix-b-windows/`，最终取证没有重跑，也没有并入。<br>**互不代替**：旧自测的 PASS 不代替新测试，新测试不代替旧自测，参考自测的 FAIL（`test_static_resolution`）不因项目测试通过而改判。INDEX.md 第 2 节与 legacy-inventory.md 第 12.1 节也是这样分开的。<br>**用词差异**：legacy-inventory.md 第 0.5、12.1 节把 test_protocols.py、test_codekit01_fixtures.py、test_baseline_tool.py 称为“参考实现与取证工具测试”。它们的被测对象是本仓库的 01 新代码，不是附录 B 参考代码本身，本报告按被测对象归栏。两份文档都把它们与旧自测、附录 B 参考自测分开，所以不影响本条判定<br>**平台适用性**（修订 4，JSON `acceptance[01-A16].applicability_by_platform`）：windows 为 applicable；linux、macos 为 not_applicable，理由是分栏记录是报告与证据目录的结构规则，不随平台变化。这不表示 Linux、macOS 上有任何测试运行或通过，那里各栏的测试结果仍是 NOT_RUN |
| 01-A02–A06、A08–A15 | **本报告不判定**（不是 NOT_RUN） | — | 这 13 项的判定与证据见 [acceptance.md](acceptance.md) 第 0、3 节（证据编号见其第 2.3 节）。JSON 中这些条目标 `judged_by_this_report=false`，不带 execution_status、evidence_basis 与 evidence_refs；`transcript_from_acceptance_md` 照录 acceptance.md 的判定文字，并把证据编号解析为归档文件的路径、字节数与 sha256，分歧时以 acceptance.md 为准。<br>JSON 不固定 acceptance.md 的摘要：acceptance.md 记录本报告的摘要，互相内嵌会形成循环；acceptance.md 当前字节的摘要记在 [README.md](README.md) 的文件索引中。<br>**记法更正**（修订 5）：修订 3、4 把这 13 项写成 `execution_status=NOT_RUN`、`evidence_basis=unknown`，理由是 acceptance.md 当时尚未产生；修订 4 写于 acceptance.md 产生之后却没有更新。这种记法会被读成“这些项没有运行”，与 acceptance.md 的判定冲突，修订 5 已撤回 |

01-A07 在 PASS 范围之外仍有的缺口（JSON `acceptance[01-A07].unmet_within_scope`；按 R-02 逐条登记，迁移比较时记 NOT_COVERED；最后两行由修订 4、6 补）：

| 项 | 缺口 | 影响 |
|---|---|---|
| 取消（含 G1） | POSIX 的 SIGINT 两个方法（P4-L03、L04）本机跳过，NOT_RUN；经子进程到达 main 的 130 没有测到（Windows 上 CTRL_BREAK 不经过该分支，P4-C29 只在进程内锁定映射） | POSIX 上取消的旧结果没有旧观测，迁移比较时须记 NOT_COVERED；不能宣称 Linux、macOS 上的取消回归（01-A15） |
| 取消 | :3319-3332 窗口、collect 期间的中断、_terminate_tree 期间再收到信号、SIGTERM 与 SIGHUP 都没有构造 | 这些窗口的旧状态只有源码推断，04、07 的新实现无法与旧观测对照 |
| 预算竞争 | 真实并发下的过期接管竞态、mtime 语义与时钟偏差、owner.json 写入时的 FileExistsError、同一 attempt 并发 run 的 claim 冲突、预算限额来源不同 | 锁与预算的并发语义只有顺序构造与白盒证据（P4-L21 证实释放锁时不核对归属）；03、07 不能把这些当作已锁定的旧行为 |
| 补丁完整性 | --fresh 与 mutate 对补丁缺失、sha256 不符、往返标记为 false 的拒绝只测了“字节被改”一例；真实的 apply --cached 往返失败没有构造 | 真实往返失败时“收集状态不变、G6 失败”的端到端链路缺少直接观测 |
| G0–G6 的备注 | G2“执行器访问了工作副本外路径”、G3 合同矛盾、G4 干净副本模式三条备注未经 verdict 断言；G6 重新快照写 Git 对象未断言；diff_error 时 G2 没有备注 | 备注不影响门禁结果；新实现的备注文本与副作用缺少对照 |
| 范围 | submodule、普通文件的 mode_changed、sensitive_file、dependency_manifest_changed、真实的非 UTF-8 文件名、review_hints | 这些范围类别的旧判定只有源码依据（source_inspected） |
| 平台 | Linux、macOS 全部 NOT_RUN；Linux 的 PDEATHSIG 分支没有产生 | 本条 PASS 不外推到其他平台 |
| 文档 3.2 的两个字段（修订 4 补） | 修订 3 判定时 legacy-inventory.md 第 9、12 节没有填写 input_fixture_ref 与 comparison_projection_revision。清单第 9.10 节已按行回填：LB-GATES、LB-LIFE 全部 NOT_COVERED；第 12 节 159 个 P4 方法没有 fixture 与比较投影 | 不改变本条按 7.1“逐条来源测试与断言映射”的判定；但这些方法是旧实现现状的观测，不是文档 6.6 意义上的 fixture 差分，迁移比较时须记 NOT_COVERED。**修订 6 更新**：按 R-P12，159 个方法已登记为代码内联 fixture（清单 12.10），9.10.6 的 NOT_COVERED 降为 67 行；文档 6.6 七类的状态是“旧路径已锁定，差分 NOT_RUN（新路径不存在）”（9.10.7）。这一行在 JSON 中是 known_limitations，不是 unmet_within_scope |
| 各类的其余子分支（修订 6 补，清单 9.10.6 的 (a) 类） | 9.9 判为未覆盖、P4 没有方法、上面各行没有点名的：LB-EXIT-032（spawn 失败转 INFRA_FAILURE、run 退出 1）、LB-LIFE-037（预检证据被覆盖）、LB-LIFE-038（claim 为普通文件时的判断不一致）、LB-EXIT-037（tasklist 失败时 pid_alive 的结果）。LB-GATES-021、LB-LIFE-014、LB-LIFE-034、LB-TEST-009 已在上面各行；其余 (a) 类行属于合同、事件、包装脚本与 status 输出，不在 A07 的六类之内 | 没有锁定的旧观测，迁移比较时记 NOT_COVERED；归类按清单描述（source_inspected），没有逐行核对源码 |

**判定历史**（修订 2 的初判，只依据实施前取证；原文保留在 JSON `acceptance[].judgment_history`；修订 3 的判定见上面第二张表）：

| 编号 | 修订 2 初判 | 依据 | 要点 |
|---|---|---|---|
| 01-A01 | PASS（限 Windows） | measured | 被读取但未计摘要的 pyc 待 P4 判断 |
| 01-A07 | FAIL | source_inspected | 映射完整，但 G0 没有失败路径测试，G3、G6 的失败没有断言，G5 没有机械判定；G1、G2、G4 只覆盖部分失败原因；取消没有信号用例；补丁完整性只有正向用例；预算竞争不断言落败方退出码。FAIL 指验收核对不满足 7.1，不表示旧测试失败 |
| 01-A16 | PASS | measured | 当时只有 legacy_project 与 reference_code 两栏；P2 的协议测试产生后需要再分栏 |

## 9. 证据归档

### 9.1 基线取证归档（evidence-archive-integrity：PASS，measured）

- **命令**：`python scripts/codekit/baseline.py archive .agent/baseline/01-T1/bl-01t1-legacy-20260925 --dest docs/code-kit-v2/01-baseline/evidence`，退出码 0。
- **归档文件**：共 83 个，即 capture.json 登记的 82 个加上 capture.json 本身。
  - 摘要不符 0 个；
  - 被脱敏改动 5 个：`capture.json`、pre/post 的 `02-rev-parse-toplevel.stdout.bin`、pre/post 的 `environment.json`；
  - 原样复制 0 个；
  - `unredacted_files` 为空。
- **脱敏规则**：redact-v2，共替换 `<PYDIR>` 3 处、`<REPO>` 2 处。
- **archive-manifest.json**：`evidence/bl-01t1-legacy-20260925/archive-manifest.json`，SHA-256 `b46f72a21da6c4b1169c29d6c3a0df3e4c47b4186dedde104473348818e0f521`。
- **关键归档文件**：

| 归档文件 | SHA-256 | 说明 |
|---|---|---|
| `capture.json` | `cf821420aa122ad6ea78cd823dfbfd712c402ad804dd82f174a68cd8334cec39` | 原始 `1089266169ff2af6…`，替换了 1 处 `<PYDIR>` |
| `run/stdout.bin` | `f40586e2376e2361bc962878059d732b95c2c8cb0f79d48c3fd069fc37e1080e` | 与原始字节相同，13423 B |
| `run/stderr.bin` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 B |

### 9.2 其他证据目录

- **`evidence/reference-appendix-b-windows/`**：参考代码验证。
  - `manifest.json` 记录了：原输出与脱敏后输出的 SHA-256、脱敏规则、三个参考文件与附录 E.2 的对照、每次运行的命令与解释器。
  - 另有三份脱敏输出：original、rerun、diagnostic-long-temp。
  - 原始输出含机器路径，不入库；manifest 只记录其摘要。
- **`evidence/run-controls/`**：受控环境记录、取证控制台输出、P0.2 离线边界静态核实（md 与 json），均为脱敏副本，另有 `manifest.json`。
  - 这些记录由操作者写下，不是取证工具采集的，按 source_reported 或 source_inspected 使用。

### 9.3 残留机器信息检查

- **检查方法**：大小写不敏感地搜索以下几类模式，兼顾反斜杠、正斜杠与 JSON 转义写法。
  - 识别类：当前用户名及其 8.3 短名、用户主目录、仓库上级目录名与仓库目录的路径组合、规划会话标识与编码后的项目目录名、主机名。
  - 通用类：`AppData`、`Users/`、`Local/Temp`、盘符路径、`/c/`。
  - 识别类的具体模式在扫描时由当前工作目录、8.3 短名接口与主机名现场生成，不写入报告：写进报告会重新暴露归档已经脱敏的信息。报告只记录类别与个数（JSON `evidence-archive-integrity.actual.residual_scan`）。
  - 初版报告曾把具体模式原样列在这里，修订 2 已删去。
- **扫描范围**：修订 2 重新扫描了 `evidence/` 全部 93 个文件、两份报告和 `legacy-inventory.md`。
- **没有发现**可识别本机用户或仓库位置的残留，例如用户名、8.3 短名、仓库所在目录、会话临时目录、主机名。
- **残留项**如下，都没有手工修改归档文件：
  1. `capture.json` 与 pre/post 的 `environment.json` 中有工具安装目录：`C:\Program Files\Git\mingw64\bin\git.EXE`、`C:\Program Files\Git\usr\bin\bash.EXE`、`C:\Program Files\nodejs\node.EXE`。redact-v2 已声明不覆盖“其他机器路径”。
  2. pre/post 的 `08-diff-unstaged.stdout.bin` 是工作区差异原文。其中被删除的旧文档含示例或历史路径：`C:/Users/me/AppData/Local/Temp/pi-worktrees/wt-a001`、`C:\Windows\Temp`、`C:\Code\WoMovieSubCheck`。它们是仓库文档的内容，不是本机的取证定位。
  3. `run-controls/` 脱敏后仍保留 `<HOME>\AppData\Roaming\npm` 这类 Windows 通用子目录名，以及 `C:\Program Files\Git`、`C:\WINDOWS\system32` 等系统路径。
- **凭据样式扫描**（修订 2 重做，模式见 JSON `evidence-archive-integrity.actual.credential_scan`）：
  - 合成标记模式 `(DEMO|SYNTHETIC|FAKE|DUMMY|TEST)_[A-Z_]{3,}` 命中的都是合成示例值。
    - pre/post `08-diff-unstaged.stdout.bin` 各含：`DEMO_REVIEW_SECRET`×13、`DEMO_TOKEN_FOR_REVIEW`×1（出现在 `apiKey=…` 中）、`SYNTHETIC_REVIEW_CREDENTIAL`×4、`SYNTHETIC_DUPLICATE_VALUE`×1、`SYNTHETIC_YAML_VALUE`×1；
    - `run-controls/offline-boundary.redacted.json` 的说明文字中有 `DEMO_REVIEW_SECRET`、`DEMO_TOKEN_FOR_REVIEW`、`SYNTHETIC_CREDENTIAL`。
  - 键值模式（`api_key`、`secret`、`token`、`password` 等后接 `:` 或 `=`）在每份差异中另有 7 处不带合成标记，值为 `demo`、`null`、`false`、`<redacted>` 或说明文字片段，不是凭据。
  - 常见令牌格式（`sk-`、`ghp_`、`AKIA`、`xox?-`、私钥块、JWT 等）没有命中。
  - 没有发现真实凭据的迹象。这不是完整的秘密扫描。初版“只命中 `DEMO_REVIEW_SECRET`”的说法不准确，已更正。

## 10. 限制与未运行项

修订 6 在 JSON `limitations[]` 的部分条目上加了 `status_revision_6`（open 仍存在；partially_closed 部分关闭；closed 已关闭，文字作为历史保留；historical 只描述被取代的最终取证）。本节与 10.1 的原文不删，状态汇总见 10.3 节开头的表；收尾取证的限制见 10.3 节。

- **输入闭包为 partial**：被忽略的文件只列名称；子模块没有展开；仓库外输入没有纳入，包括解释器标准库、全局 Git 配置和系统工具。本报告不宣称可以严格复现。
- **被读取但未计摘要的字节码**（修订 6：部分关闭。收尾取证按 R-01 受控禁用了 pyc，依据只有操作者记录；本条对实施前基线仍成立，见 10.3 节）：被忽略的 `scripts/__pycache__/pi_dispatch.cpython-312.pyc` 确实被测试读取。
  - `tests/test_dispatch.py:39-40` 把 `scripts/` 加入 `sys.path` 后在进程内 `import pi_dispatch`，测试中的 `pd.*` 调用执行的就是这份字节码。以脚本方式启动的 `pi_dispatch.py` 子进程不读取它。
  - `PYTHONDONTWRITEBYTECODE` 只阻止写 pyc，不阻止读。
  - 修订 2 的事后核对（measured）：
    - pyc 头部 magic 等于 `importlib.util.MAGIC_NUMBER`，记录的源码 mtime 与 size 都与 `scripts/pi_dispatch.py` 一致，所以导入时直接使用它；
    - pyc 主体与用同一 `co_filename` 编译当前源码得到的 marshal 字节相同；
    - 文件 mtime 为 2026-09-25T02:46:35Z，早于取证开始；
    - 当前 SHA-256 为 `c5b2545e101f81922328a2001c5208e075056105abb4d695fe7676a39a41c3bf`，357593 字节。
  - 这些核对发生在取证之后，不能替代取证时的摘要。它属于 01-A01 所说的“缺输入”一类，由 P4 判断对 A01 的影响（见第 8 节）。
  - 以后取证应记录这份 pyc 的摘要，或把 `PYTHONPYCACHEPREFIX` 指向空的临时目录，避免读入未计摘要的字节码。
  - `tests/__pycache__/` 中只有 `test_dispatch` 的 pyc；测试以脚本方式运行，不读取它。
- **受控环境改变的代码路径**：以下旧行为本次没有执行。
  1. doctor 在 PATH 上找到 claude 或 codex 后运行其 `--version` 并写入 facts 的分支（`scripts/pi_dispatch.py:4670-4674`）。本次两者都不在 PATH 上，只走了记 note“PATH 中没有 claude 或 codex”的分支（:4675-4676）。
  2. `resolve_pi_command` 在 `PI_DISPATCH_PI_CMD` 缺失或为空时用 `shutil.which("pi")` 查找、解析 npm `.cmd` 包装的回退（:1771-1786）。测试经 `BASE_ENV` 始终设置该变量，本来就不走这一分支；受控 PATH 只保证万一走到时报“PATH 中找不到 pi”，不会启动真实 pi。
  3. 读取真实 `~/.pi/agent` 的路径：`context_evidence`（:1816-1857，经 run :3279 与 doctor :4751 调用）读取全局上下文文件、`SYSTEM.md`/`APPEND_SYSTEM.md` 与 `settings.json` 的顶层键名；doctor 查找 agent 目录下的 `bin/rg`、`bin/fd`（:4677-4680）。本次这些读取只见到操作者记录的空目录。

  因此，`test_setup_wrapper_doctor`（`tests/test_dispatch.py:715-747`）与 `test_v21_codex_trial_feedback`（:1734）中的 doctor 检查，以及经 run 生成上下文证据的检查，在 Windows 上的 PASS 只代表“真实 CLI 缺席、agent 目录为空”这一条件下的行为。按原样运行时，doctor 会运行真实的 `claude/codex --version` 并读取真实的 `settings.json`（`evidence/run-controls/offline-boundary.redacted.md`）。
- **读取与使用之间的竞态**：输入清单按采样时刻计算，前后采样也不是原子快照。
- **没有网络隔离与监测**：离线依据是静态核实。其余环境变量原样传给测试，没有运行时证明它们未被写出。
- **只运行了 Windows**：Linux、macOS 上的项目旧自测与参考自测都是 NOT_RUN。`test_wrapper_interpreters_and_literal_arguments` 在 Windows 上没有运行。
- **G0–G6 与补丁完整性的失败路径缺少测试**：见第 7 节。本次的 PASS 不能证明这些路径的旧行为。
  - 修订 3：这一条对 `tests/test_dispatch.py` 本身仍成立；P4 特征化回归在 Windows 上补测了这些失败路径，剩余缺口见第 8 节与下面的“01-A07 的剩余缺口”。
- **PID 复用风险**：`test_timeout` 与 `test_dispatcher_killed` 会对预期已经结束的 PID 无条件执行 `taskkill /F /T`，PID 被复用时可能误杀无关的进程树。这是静态核实发现的残余风险；本次没有残留进程。
- **证据与报告的行尾**：`docs/code-kit-v2/01-baseline/` 下这些文件没有任何 `.gitattributes` 属性（`git check-attr -a` 为空），本机 `core.autocrlf=true`（来自系统级 Git 配置）。
  - **本机提交再检出就会变**：修订 2 在一次性临时仓库中用同样的 autocrlf 设置，以 `git hash-object -w --path` 与 `git cat-file --filters` 模拟提交再检出。`evidence/` 下 93 个文件中有 36 个摘要改变：
    - 34 个只含 LF 的文本文件，例如 `capture.json`（`cf821420…` → `6717c500…`）、`archive-manifest.json`、pre/post 的 `environment.json`（`097cb8a4…` → `259d9503…`）与 `input-manifest.json`、pre/post `08-diff-unstaged` 的 stdout 与 stderr、两个 `manifest.json`；
    - 2 个 CRLF 与 LF 混合的文件：`unittest-original.redacted.txt`、`capture-console.redacted.txt`。
  - **不变的文件**：47 个空文件，以及 6 个以 `-z` 输出、含 NUL 的文件（pre/post 的 `06-status-porcelain`、`07-status-ignored`、`18-ls-files` 的 stdout）。
  - **纯 CRLF 文件**：`run/stdout.bin`、`unittest-rerun`、`unittest-diagnostic-long-temp`、`offline-boundary.redacted.json` 这 4 个文件在 Windows 上往返后字节不变；但提交时 CRLF 被转成 LF，在 LF 平台（autocrlf 为 false 或 input）检出后摘要不符。2 个混合文件同样如此。
  - **证据目录之外**：`baseline-report.json`、`baseline-report.md`、`legacy-inventory.md` 都只含 LF，本机往返后同样会变（例如本报告初版 `4558b96d…` → `a8a89eee…`）。只为 `evidence/**` 加规则覆盖不到它们。
  - **建议**：规划端在提交这些文件之前，在 `.gitattributes` 中加入 `docs/code-kit-v2/01-baseline/** -text`，一并覆盖 `evidence/`、两份报告，以及 P4 将固定摘要的 `legacy-inventory.md`、`compatibility-matrix.md` 等。文件如果已经先被 `git add`，加规则后需要重新暂存（`git add --renormalize`）。本任务没有修改 `.gitattributes`。
  - **修订 3 核对**：`.gitattributes` 已有 `docs/code-kit-v2/01-baseline/** -text`（01-L06）。`git check-attr` 对两份报告、`legacy-inventory.md` 与 `evidence/final/` 下的文件显示 `text: unset`。
- **参考自测原运行**：输出中没有记录解释器版本；命令来自规划端的工具调用记录。
- **未产生或未定稿的文档**（修订 6：已关闭，两份文档的摘要按当前字节重新固定，见第 7.1、11 节）：`legacy-inventory.md` 在本报告初版生成时尚未产生；修订 2 按当时的工作区字节固定了摘要（第 7 节），但清单尚待 P4 定稿与复审。`compatibility-matrix.md` 在修订 2 时仍未产生，报告中它的摘要为 null。
  - 修订 3：清单已加入 P4 更新，摘要按修订 3 核对的字节重新固定（第 7.1 节）；兼容矩阵已产生，摘要见第 11 节。
- **jsonschema**：未安装，Schema 元校验为 BLOCKED（2.4：缺工具与授权）。`01-baseline/README.md` 在修订 2 时仍写作 NOT_RUN，已提请规划端改为 BLOCKED。
  - 修订 3：README 已改为 BLOCKED（01-L07）。最终取证中 `SchemaFileTests.test_A09_jsonschema_metaschema_optional` 因同一原因跳过，记 BLOCKED，不计通过；附录 A Schema 的 Draft 2020-12 元校验仍未执行。
- **超时**：旧测试没有函数级或整体超时，只依赖监督器的 3600 秒时限。

### 10.1 修订 3 增补：实施后回归的限制

以下各条对应 JSON `limitations` 中的 L-FINAL-* 与 L-A07-RESIDUAL-GAPS。

- **只有 Windows**（L-FINAL-PLATFORM）：8 次最终取证都只在 Windows Server 2025 + CPython 3.12.10 上运行。
  - Linux、macOS 上的旧自测、P4 特征化回归、协议测试、fixture 测试与取证工具自测全部 NOT_RUN，不从 Windows 结果推导（01-D10、7.5）。
  - 本机跳过的 3 个 POSIX 方法（P4-L03、L04、C52）与 `test_wrapper_interpreters_and_literal_arguments` 也是 NOT_RUN。
  - Linux 的“PDEATHSIG stops pi”仍没有产生。
- **跳过的方法**（L-FINAL-SKIPS）：最终取证共 7 个跳过方法，都没有运行，不计通过。
  - `test_protocols.py`：F017（NOT_RUN，01-D05，归 02）；F029、F030（NOT_RUN，01-D06，归后续访问实现模块）；A09 jsonschema 元校验（BLOCKED）。
  - `test_legacy_lifecycle.py` 的 P4-L03、L04 与 `test_legacy_cli.py` 的 P4-C52：NOT_RUN，POSIX 分支。
  - 跳过原因原文见第 12.3 节。
- **fixtures 测试没有方法级证据**（L-FINAL-FIXTURES-TRACE；修订 6：已关闭，收尾取证以 `-v` 运行，75 个方法都有方法名，见第 13.4 节；下文对最终取证那一次仍然成立）：`test_codekit01_fixtures.py` 以非逐条模式运行，归档 `run/stderr.bin` 第 1 行只有 36 个“.”。
  - 它只证明 36 个用例运行、没有失败或跳过，任何单个方法都不能据此记 PASS。
  - 文件中 36 个 `def test` 与之对应只是静态核对。要逐方法判定，须以 `-v` 重新取证。
- **白盒与构造的状态**（L-FINAL-WHITEBOX）：P4 特征化回归中有 49 个白盒方法。
  - `test_legacy_cli.py`：`LegacyContractDefaultsTest` 6、`LegacyMarkdownJsonConsistencyTest` 17、`LegacyScopeInProcessTest` 4、`LegacyMainInProcessTest` 3，即 P4-C02–C31。
  - `test_legacy_events.py`：`PreflightWhiteBoxTests` 6、`SummarizeEventsWhiteBoxTests` 11，即 P4-E07–E12、E23–E33。
  - `test_legacy_lifecycle.py`：P4-L20、L21。
  - 它们在进程内加载同一份被测字节并直接调用内部函数，只证明函数层面的现状，并依赖内部签名；经 CLI 的端到端后果不一定相同。
  - 另有用例用 `set_state` 或改写证据文件构造状态，例如把 `patch_roundtrip_verified` 改为 false、改写 `candidate_tree`、构造 `wall_seconds`。这些都不等于真实的崩溃或运行路径。
- **受控环境没有执行的分支**（L-FINAL-CONTROLLED-PATHS）：最终取证沿用 01-L05 的受控环境。
  - 取证进程 PATH 上没有 pi、claude、codex（measured）；`PI_CODING_AGENT_DIR` 指向空目录（source_reported）。
  - `tests/legacy_harness.py` 还会从子进程 PATH 中去掉任何含 pi/claude/codex 的目录，并要求设置 `PI_DISPATCH_PI_CMD`，否则拒绝运行。
  - 因此 8 次取证中都没有执行：
    1. doctor 在 PATH 上找到 claude 或 codex 后运行其 `--version` 并写入 facts 的分支（`scripts/pi_dispatch.py:4670-4674`）；
    2. `resolve_pi_command` 在 `PI_DISPATCH_PI_CMD` 缺失或为空时用 `shutil.which("pi")` 查找、解析 npm `.cmd` 包装的回退（:1771-1786），以及 `ensure_argv_safe`；
    3. 读取真实 `~/.pi/agent` 的路径（`context_evidence` :1816-1857，doctor 的 `bin/rg`、`bin/fd` :4677-4680）。
  - doctor 与 run 相关断言的 PASS 只代表“真实 CLI 缺席、agent 目录为空、`PI_DISPATCH_PI_CMD` 已设置”这一条件下的行为。
- **输入闭包与未计摘要的 pyc**（L-FINAL-CLOSURE；修订 6：历史，对最终取证仍成立，按 R-01 原口径保留；收尾取证见 10.3 节）：最终取证的输入闭包仍为 partial（373 项；被忽略的 `scripts/__pycache__/`、`tests/__pycache__/` 只列名称）。
  - `bl-01final-test-dispatch-20260925` 中旧自测在进程内 `import pi_dispatch`，读取了未计摘要的 `scripts/__pycache__/pi_dispatch.cpython-312.pyc`；修订 2 的建议（记录其摘要，或把 `PYTHONPYCACHEPREFIX` 指向空的临时目录）没有被采用。
  - 修订 3 事后核对（measured，在取证之后）：sha256 `c5b2545e…`、357593 字节，与修订 2 核对时相同；mtime 2026-09-25T02:46:35Z，早于两次取证；头部 magic、源码 mtime 与 size 字段与当前 `scripts/pi_dispatch.py` 一致。
  - 其余 7 次取证不读这份 pyc。对 01-A01 的影响见第 8 节。
- **操作者记录的条件**（L-FINAL-OPERATOR；修订 6：归档要求已关闭，`final2-captures.txt` 已正式归档到 `evidence/run-controls-final/`，见 10.3 节；证据等级仍是 source_reported，所以本条整体为**部分关闭**，JSON `status_revision_6=partially_closed`，修订 7 统一用词）：以下条件只有操作者记录（source_reported），取证工具没有采集：
  - PATH 去掉的目录；`PI_CODING_AGENT_DIR` 指向的目录在取证后为空（`empty_dir_entries=0`）；unset 会话令牌变量；
  - 取证工具退出码 0；系统临时目录没有新增残留（`leaked=[]`）；每次取证后受保护文件 diff 为 0 行。
  - 来源是规划会话临时目录中的 `final2-captures.txt`（sha256 `c362495c…d6dd`，1495 字节，没有随仓库保存）与派发说明。受保护文件未改动另有输入清单的 measured 记录（第 12.5 节）。
  - **修订 5 更新**：
    - 两处来源分开看：`empty_dir_entries=0`、`leaked=[]` 与各次 `tool_exit=0` 在 `final2-captures.txt` 中；“在 Git Bash 中运行”、PATH 去掉的目录、unset 令牌与受保护文件 diff 为 0 行不在该文件中，只来自派发说明。
    - 该文件仍没有正式归档：实施前基线的同类记录已脱敏归档到 `evidence/run-controls/`（其 manifest 的 capture_id 只有 `bl-01t1-legacy-20260925`），最终取证的这份没有。2026-09-26 核对时原件仍在，字节数与 sha256 与上面相同（measured）。
    - 内容已逐字转录到 [evidence/final/INDEX.md](evidence/final/INDEX.md) 第 5.2.1 节，按转录重建的字节与原件相同，会话清理后仍可复算摘要（JSON `post_implementation_regression.common.environment_source_reported.record.transcript`）。转录不改变这些条件的证据等级，仍是 source_reported。
    - 正式归档（新建归档目录并附 manifest）需要规划端处理，登记为 acceptance.md 第 7 节未完成项第 19 项。
- **新文件尚未提交**（L-FINAL-UNCOMMITTED）：01 的新代码、测试、夹具、fixtures 与 Schema 都是未跟踪的工作区文件。结论只对最终取证输入清单记录的字节成立（第 12.6 节）；以后文件改动，须重新取证。
- **两次取证的输入状态不同**（L-FINAL-WORKTREE）：porcelain 37 → 319 项，输入清单 92 → 373 项，闭包 `8ca10fb9…` → `2d8f2f71…`，取证工具 `baseline.py` `9eb03345…` → `dbb08466…`；被测旧源码字节相同。8 次最终取证之间工作区没有变化。
- **归档残留**（L-FINAL-RESIDUAL）：最终归档保留了工具安装目录（Program Files 下的 git、bash、node）与已删除旧文档正文中的路径，见第 12.7 节。没有手工修改归档文件。
- **耗时**（L-FINAL-DURATION）：旧自测 216.828 秒（实施前 250.219 秒），其余 4.437–128.672 秒，都只是一次记录，不是性能基准。
- **中间一轮取证**（L-FINAL-INTERMEDIATE）：`.agent/baseline/01-P4/` 已被最终取证取代，原件保留、没有归档，本报告不引用。
- **01-A07 的剩余缺口**（L-A07-RESIDUAL-GAPS）：逐条见第 8 节的缺口表。这些子行为没有锁定的旧观测，迁移比较时须记 NOT_COVERED。

### 10.2 修订 4 增补

以下两条对应 JSON `limitations` 中的 L-TOTAL-DESIGN 与 L-SOURCE-ORIGINAL。

- **总设计的读取与交叉检查**（L-TOTAL-DESIGN，decisions.md 01-L08）：
  - 对象：`docs/code-kit-v2-design.md`，32912 字节，SHA-256 `82e8e668d8de46bee7b826951f346023220f35c51ea39be4ca0bd222df74d1d1`，未跟踪文件。实施前基线与最终取证的输入清单记录的是同一字节（measured，读取归档的 `pre/input-manifest.json`）。
  - 文档 6.1 要求“实施前读取”：P0 没有留下读取记录，记 **NOT_RUN**，事后无法补成“实施前”。
  - 文档 2.1 要求的交叉检查：2026-09-26 事后补做，source_inspected。事件封装字段一致（01 是超集）；“用量”事件与 usage-observation 的关系待 04 对齐；`scripts/codekit/` 下的文件名与总设计第 9 节不同；新核心文件的保护路径没有落实；总设计 P0 完成标准只部分满足（只限 Windows，“可复现”只到两次取证输出相同，新核心文件的保护路径没有基准）。
- **上传的原文不可复算**（L-SOURCE-ORIGINAL）：见文首“依据”。设计依据只能固定到审阅增强版。

### 10.3 修订 6 增补：已关闭的项与收尾取证的限制

**已关闭或部分关闭的项**（JSON `limitations[].status_revision_6`）：

| 条目 | 状态 | 说明 |
|---|---|---|
| L-CLOSURE（被读取但未计摘要的 pyc） | 部分关闭 | 收尾取证按 R-01 以 `PYTHONPYCACHEPREFIX` 受控禁用仓库中的 `__pycache__`，在操作者记录成立的前提下关闭；证据等级见下面 L-CLOSURE-R01-EVIDENCE。对实施前基线 `bl-01t1` 仍然成立（按原口径保留）。被忽略的目录只列名称、仓库外输入不纳入等其余部分仍存在（L-CLOSURE-INPUT） |
| L-FINAL-CLOSURE | 历史 | 对最终取证仍然成立，按 R-01 原口径保留，不改写 |
| L-FINAL-OPERATOR（最终取证操作者记录未归档） | 部分关闭（归档要求已关闭；证据等级仍是 source_reported） | `final2-captures.txt` 已正式归档到 `evidence/run-controls-final/`：1495 字节，sha256 `c362495cc389d37204e1250f8ff613585f5722cb8b0e63c60bcf668b9d11d6dd`，与原件相同；`manifest.json` 846 字节，sha256 `bbd6c3a108257aedf1fbe8c95026f75e61866120b625426016d6d88c8ddd2e8a`。acceptance.md 第 7 节第 19 项的归档要求已满足（该项的状态由 acceptance.md 更新）。条件的证据等级仍是 source_reported；PATH、unset 令牌与受保护文件 diff 对最终取证仍只来自派发说明。修订 7：JSON `status_revision_6` 原记 closed，与本表不一致，已更正为 partially_closed |
| M-06（兼容矩阵第 1 节两条 `codekit01_legacy.py` 命令没有归档） | 关闭 | 已有收尾取证归档：`bl-01closure-legacy-check-20260926`（`38 checks, 0 differ`）与 `bl-01closure-legacy-check-stub-regen-20260926`（`10 checks, 0 differ`），见第 11、13 节 |
| M-07（旧行为清单的结构化条目只在会话临时目录） | 已关闭（归档要求） | 已归档到 `evidence/inventory-items/`：6 个 `inventory-*.items.json` 与 `manifest.json`（1326 字节，sha256 `cebbd8bfc9861f97ce21f81478b2574aef5fdd6a8acff3df1f5ca70d9ddba8c9`），修订 6 核对 6 个文件的字节数与 sha256 与 manifest 一致（JSON `legacy_inventory.inventory_items_archive`）。manifest 自述条目中的“实测”“探针”来自一次性脚本，仍只是线索，证据等级不变（legacy-inventory 11.6 第 1 条，另项，不属于 M-07）。修订 7 统一用词：M-07 只涉及是否归档，与 acceptance.md、README 一样记“已关闭（归档要求）” |
| L-FINAL-FIXTURES-TRACE | 关闭 | 收尾取证 `-v`：75 个方法都有方法名且都是 ok |
| L-PENDING-DOCS | 关闭 | 两份文档都已产生，摘要按当前字节重新固定 |
| L-FINAL-PLATFORM、L-FINAL-JSONSCHEMA、L-FINAL-SKIPS、L-FINAL-UNCOMMITTED、L-FINAL-WORKTREE、L-FINAL-RESIDUAL、L-FINAL-DURATION | 历史 | 只描述最终取证；收尾取证的对应情况见下面各条 |
| L-FINAL-WHITEBOX、L-FINAL-CONTROLLED-PATHS、L-CONTROLLED-PATHS、L-PLATFORM、L-WRAPPER、L-GATES、L-JSONSCHEMA、L-FINAL-INTERMEDIATE、L-A07-RESIDUAL-GAPS | 仍存在 | 收尾取证中同样成立（L-A07-RESIDUAL-GAPS 按 R-02 登记为 unmet_within_scope，修订 6 补一行） |

**收尾取证的限制**（JSON `limitations[]` 中的 L-CLOSURE-*）：

- **R-01 受控禁用只有操作者记录**（L-CLOSURE-R01-EVIDENCE）：`PYTHONPYCACHEPREFIX` 指向取证前为空的目录，依据是 `evidence/run-controls-closure/closure-captures.txt` 第 4、6 行（source_reported）。
  - 取证工具的 `environment.json` 只检查 13 个指定名称，不含该变量；`input-manifest.json` 的 `python_startup` 不记录它；没有取证后前缀目录的条目数；第 20 行 `repo_pycache_dirs_newer_than_start` 参照时刻偏晚，不作证据。
  - 被测进程继承该变量只依据 `run.env_policy` 文字与测试代码的静态核对；`tests/test_protocols.py` 的 `-B -I` 子进程不继承它，但只导入没有 `__pycache__` 的 `scripts/codekit/`。
  - 取证工具进程本身没有设 `PYTHONDONTWRITEBYTECODE`，可能把标准库字节码写进前缀目录供之后的被测进程读取；这属于仓库外输入（推断，未测量）。
  - 要由取证工具测得，需要改进 `baseline.py` 后重新取证（第 13.5 节）。
- **输入闭包仍为 partial**（L-CLOSURE-INPUT）：1073 项，闭包 `81b4503e…`。被忽略的两个 `__pycache__` 目录只列名称（R-01 让解释器不读它们，而不是计摘要）；6 项是已删除的旧文档，没有字节；仓库外输入与 gitattributes 效果不纳入；没有子模块；读取与使用之间的竞态没有消除。不宣称输入完整或可严格复现。
- **只有 Windows**（L-CLOSURE-PLATFORM）：10 次都只在 Windows Server 2025 + CPython 3.12.10 上运行；Linux、macOS 全部 NOT_RUN；3 个 POSIX 方法与 `test_wrapper_interpreters_and_literal_arguments` 也是 NOT_RUN；Linux 的“PDEATHSIG stops pi”仍没有产生。
- **操作者记录的条件**（L-CLOSURE-OPERATOR）：PATH 去掉真实 CLI 所在目录、unset 会话令牌变量、`PI_CODING_AGENT_DIR` 指向空目录且取证后仍为空、`PYTHONPYCACHEPREFIX`、各次 `tool_exit=0`、系统临时目录没有新增残留、受保护文件 diff 前后 0 行，都只有操作者记录，已归档（sha256 `fb00af74…`），证据等级 source_reported。取证工具只测量了 which 的结果与 13 个变量名是否存在；受保护文件未改动另有输入清单的 measured 记录。
- **新文件仍未提交**（L-CLOSURE-UNCOMMITTED）：结论只对收尾取证输入清单记录的字节成立（第 13.1 节）；修订 6 编写时这些字节都没有变化。以后文件改动，须重新取证。
- **输入状态与取证之后的变化**（L-CLOSURE-WORKTREE）：
  - 与最终取证相比：porcelain 319 → 1019 项，输入清单 373 → 1073 项，闭包 `2d8f2f71…` → `81b4503e…`；取证工具与监督器字节相同；`protocols.py`、`test_protocols.py`、`test_codekit01_fixtures.py`、`legacy_harness.py`、`codekit01_legacy.py` 与 fixtures 在收尾轮改动过，4 个特征化测试文件、取证工具测试与被测旧源码字节不变。10 次收尾取证之间工作区没有变化。
  - 取证之后：`legacy-inventory.md` 被清单代理更新，两份基线报告与 `compatibility-matrix.md` 被本修订更新，`evidence/closure/` 与 `evidence/run-controls-closure/` 新增。测试不读取这些文档，但 `PublicEntryRejectionTests.test_baseline_records_are_internal` 按目录现场读取 `evidence/` 下的记录：取证时是 9、18、18、9 份，现在是 19、38、38、19 份，以后再运行时它的输入不同（没有运行，未核对）。
- **归档残留**（L-CLOSURE-RESIDUAL）：保留了工具安装目录（30 个文件 440 处）与已删除旧文档正文中的路径（20 个 `08-diff-unstaged.stdout.bin`），见第 13.7 节。没有手工修改归档文件。
- **耗时**（L-CLOSURE-DURATION）：旧自测 235.828 秒，其余 0.703–140.469 秒，只是一次记录。
- **新增测试与裁决的对应只是静态的**（L-CLOSURE-STATIC-MAPPING）：`CredentialScanTests`、`R11Tests`、`CompatMatrixDCaseTests`、`CleanupOwnershipTests`、`HarnessCleanupOwnershipTests` 与 `test_protocols.py` 新增的 18 个方法对应哪条裁决，只按类名与方法名判断，修订 6 没有复核断言内容；它们的运行结果是 measured，是否充分覆盖对应裁决由 acceptance.md 与复审判断。

## 11. 兼容矩阵

修订 2 时兼容矩阵还没有产生，本节当时为 pending。修订 3 的状态如下（JSON `compatibility`）。

- **引用版本**：[compatibility-matrix.md](compatibility-matrix.md)，58197 字节，LF 行尾，SHA-256 `6c5f6fedafdfed6864925cde84aaba8073bfe2000df4713bf048ebf8d98ab332`。文档自述为修订 7（P4 第 5 轮核验后续）。`-text` 规则已覆盖（01-L06）；文档再修改时须重新固定摘要。
  - **修订 4 更新**：兼容矩阵在完整性审查后更新为修订 8：73701 字节，SHA-256 `91e4ea22d14e677823b2c15e08d0d6e5857405332342083a1b6531c7d0f0f6ea`（JSON `compatibility.ref`；修订 7 的摘要移入 `compatibility.history`）。修订 8 只改文档：新增第 9 节（8.3 故障恢复决策表的逐行落点、8.4 各清理代码是否核对归属），第 8 节增加缺样本清单与 fixture 条目结构缺少的字段，第 6 节补上 P4 新增的文件与取证目录。
- **本报告只引用，不判定**：本报告只固定其字节摘要，不复述、也不重判其中的兼容结论。矩阵自述“不是验收结论”。
- **与最终取证的关系**：
  - 矩阵第 1 节中 `test_codekit01_fixtures.py`（`Ran 36 tests` / `OK`）与 `test_protocols.py`（`Ran 324 tests` / `OK (skipped=4)`）的结果来自会话内运行，没有归档。本报告以最终取证 `bl-01final-test-codekit01-fixtures-20260925`、`bl-01final-test-protocols-20260925` 的归档输出作为这两条命令的运行证据，计数一致。
  - 矩阵第 1 节中 `python tests/codekit01_legacy.py --check`（`32 checks, 0 differ`）与 `--check-stub-regen`（`10 checks, 0 differ`）不在 8 次最终取证中，没有归档输出。本报告不据此记任何 PASS。
- **修订 6 更新**：
  - **引用版本**：兼容矩阵修订 9、10 由收尾轮实施者更新（修订 10 为 105770 字节，sha256 `6a5defe929b6349718d9f5502c053cd02505cbcf6040cbd20b9be9ec935826d9`，与收尾取证输入清单的记录相同）。修订 11 由本报告修订 6 的编写者写，修订 6 固定时为 **116258 字节，415 行，LF 行尾，SHA-256 `f388c96fc4b0d579be55d083e4ef37552546c2e48b296fdd885b4c58095731d1`**（修订 7 起引用修订 12，见下一条）（JSON `compatibility.ref`；修订 8 与修订 10 的摘要记在 `compatibility.history`）。
  - **修订 11 只改取证引用、测试计数与 `protocols.py` 行号，不改兼容结论**：第 1 节新增“收尾取证”表，把 6 条命令对到归档输出的路径与 sha256；第 9 节补上收尾取证的证据编号（矩阵自用的 EV-C02、EV-C04、EV-C08）与 `CredentialScanTests`、`CleanupOwnershipTests`、`HarnessCleanupOwnershipTests` 的逐条结果；第 6.1、6.3 节补上 `01-closure` 原件与 `evidence/closure/`；E01、E03、E06、E20 补收尾取证的结果；`protocols.py` 的行号按当前字节（`64d75bb0…`，3634 行）逐个核对，改了三处（E09 的 `build_default_registry` 1513-1539、`_validate_ref` 1571-1583，E18 的受控词表常量 3268-3294 与函数 3297-3327）。其他文件的行号没有改动。
  - **M-06 关闭**：两条 `codekit01_legacy.py` 命令已有收尾取证归档，计数与矩阵第 1 节一致（38/0、10/0），本报告在第 13 节据此记 PASS。上一条“本报告不据此记任何 PASS”对最终取证时的状态仍然成立。
  - 矩阵第 1 节原表仍是实施者的仓库内运行（没有归档）；它与收尾取证是否用同一批字节，矩阵没有记录，本报告不作推定，只以收尾取证的归档输出为运行证据。
- **修订 7 更新**：兼容矩阵修订 12 由对抗性核验返工子代理写，当前为 **118604 字节，418 行，LF 行尾，SHA-256 `07b3aa17a5e8ed1909f83f4cee7a239d3ea9a7875cdc92a62b52b4d0abe2af34`**（JSON `compatibility.ref`；修订 11 的摘要移入 `compatibility.history`）。修订 12 只改一处证据等级的写法与一处索引摘要，**不改兼容结论**：E19 与第 9.1 节“fixture 含真实凭据”一行原写“本次没有命中，也没有白名单放行”，而 `CredentialScanTests.test_fixture_files_contain_no_credential_shapes` 丢弃白名单放行结果（`found, _allowed = …`，`tests/test_codekit01_fixtures.py:2636`），只断言非白名单命中为空，所以“没有白名单放行”改记为静态核对（source_inspected）；第 1 节对 `evidence/closure/INDEX.md` 的摘要引用按勘误后的字节更新。

## 12. 实施后回归（post_implementation_regression）

> **修订 6 注**：就“01 实施完成后的项目验证”而言，本节的 8 次最终取证已被第 13 节的收尾取证取代，**是历史证据**：内容与 `evidence/final/` 的归档都保留、不改写，按 R-01 原口径解释（`bl-01final-test-dispatch-20260925` 读取了未计摘要的 pyc）。JSON 中对应 `post_implementation_regression.status_revision_6`。第 12.1 节提到的操作者记录 `final2-captures.txt` 已正式归档到 `evidence/run-controls-final/`（第 10.3 节）。

本节对应 JSON 的 `post_implementation_regression` 分区，是修订 3 新增的，不改写第 2–6、9 节的实施前基线。

- **取证方式**：P4 实施完成后，规划端在受控环境（01-L05）中按测试文件逐个取证（01-L04），共 8 次，全部在 Windows 上运行。
- **原件与归档**：原件在 `.agent/baseline/01-final/<capture-id>/`（被 .gitignore 忽略，只读）；脱敏归档在 `evidence/final/<capture-id>/`。
- **索引**：[evidence/final/INDEX.md](evidence/final/INDEX.md)，它是归档子代理手写的索引，不是取证产物，也不在任何 archive-manifest.json 中。
  - 当前版本（修订 5 固定）：25868 字节，SHA-256 `bc04e2c39cbf67301af0b7f387bdcd8c476e51d5d28478eddc67aa74536a496d`。
  - 修订 3、4 固定的初版：20570 字节，SHA-256 `7d4dbcf0b863b821b236eb359bb5de54e60cb102d459af2abdf97e3c914dfbe4`（JSON `index_ref.history`）。
  - 修订 3 逐项复核了其中的摘要、计数与行号（第 12.8 节），但漏了第 1 节一句计数：初版写“全部 672 个归档文件的 sha256 都与各自 manifest 的 `archived_sha256` 一致”，能比对的其实只有清单列出的 664 个，另 8 个是不列出自身的 `archive-manifest.json`（第 12.7 节）。修订 5 时已在 INDEX.md 中更正并附勘误，同时新增第 5.2.1 节逐字转录操作者记录；其余各节没有改动。01-A01、01-A07、01-A16 对 INDEX.md 的引用按新字节重新固定，旧摘要记在各自的 `history` 中，判定不受影响。
- **被取代的一轮**：中间一轮 `.agent/baseline/01-P4/` 已被最终取证取代，原件保留、没有归档，本报告不引用。
- **日期**：capture-id 中的日期取规划端本地日期；取证工具记录的 UTC 时间是 2026-09-26。

### 12.1 共同条件

- **基线**：8 次取证的 HEAD 都是 `a4fa199b0e5bdc658215765ee7558b9fe6723940`（sha1，commit），与调查提交一致。前采样的工作区状态完全相同，取证之间工作区没有变化：
  - porcelain 319 项，sha256 `a84e68334b1f94e9c69694118c5994b2847a4bc00038466dbcf43913d3dc6088`；
  - 输入清单 373 项（已跟踪 63、未跟踪 310），清单 sha256 `1406890ad081c59ff37c1cff6b466847f1a66d0ed8b368300657c0d479a108b2`，闭包 `2d8f2f71d6514b08e1f331009245d97e5f51a50a02f034651f87e17e2fa70b7d`；每次取证 pre 与 post 的闭包相同；
  - closure_status=partial，缺口为：被忽略文件不计摘要、子模块不展开、仓库外输入不纳入、gitattributes 效果不评估；被忽略的名称为 `scripts/__pycache__/`、`tests/__pycache__/`。
- **取证工具**：`scripts/codekit/baseline.py`，sha256 `dbb08466778db639966336902653525fa26a4f9f9152c5827594ea9313e49ce8`。实施前基线用的是 `9eb03345…`，工具在两次取证之间有修订；`comparison.checked` 的 12 个采样项名称相同。
- **监督器**：`scripts/pi_dispatch.py::run_supervised`，module_sha256 `a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4`，工具版本 2.2.2。
- **运行方式**：
  - cwd 为仓库根，stdin 接 devnull，shell=false；Job Object 监督，时限 3600 秒，宽限 15 秒；
  - 子进程环境新增 `GCM_INTERACTIVE`、`GIT_TERMINAL_PROMPT`、`PYTHONDONTWRITEBYTECODE`，没有移除任何变量。
- **时间（UTC）**：2026-09-26T04:16:49Z 至 04:28:10Z，按第 12.2 节的顺序依次进行。
- **环境**（measured，各取证的 pre/post `environment.json`）：
  - Windows 10.0.26100（2025Server，AMD64），CPython 3.12.10，git 2.55.0.windows.5，GNU bash 5.3.15；
  - `core.autocrlf=true`，其余 core.* 与第 3.1 节相同；
  - pi、claude、codex 在 8 次取证的 pre 与 post 中都不在 PATH 上；白名单变量中只有 `PI_CODING_AGENT_DIR` 存在（只记是否存在）；
  - 16 份 `environment.json` 的归档字节相同（sha256 `097cb8a4…`），也与实施前基线的相同。
- **环境**（source_reported，取证工具没有采集）：在 Git Bash 中运行；PATH 去掉了真实 pi、claude、codex 所在目录；`PI_CODING_AGENT_DIR` 指向的目录在取证后仍为空；会话令牌变量已 unset；每次取证后系统临时目录没有新增残留目录。来源见第 10.1 节 L-FINAL-OPERATOR。

### 12.2 逐条结果

8 条命令都在仓库根运行。“结果”是 `run/*.bin` 中的原文，括号内是文件与行号；退出码、耗时与前后一致性取自该取证的 `capture.json`。8 次都满足：`execution_status=complete`，timed_out、interrupted、stray_processes 都为 false，`spawn_error=null`，drift 为空。

| # | 取证 ID | 栏 | 命令 | 结果（原文） | 退出码 | 耗时 (s) | 前后一致 | 执行状态 |
|---|---|---|---|---|---|---|---|---|
| 1 | `bl-01final-test-dispatch-20260925` | legacy_project | `python tests/test_dispatch.py` | `256 checks, 0 failed`（stdout:282） | 0 | 216.828 | 是 | PASS（限 Windows 已运行的 256 项） |
| 2 | `bl-01final-test-protocols-20260925` | project_protocols | `python tests/test_protocols.py` | `Ran 324 tests in 4.075s`（stderr:651）；`OK (skipped=4)`（stderr:653） | 0 | 4.437 | 是 | PASS（命令级）；3 项 NOT_RUN、1 项 BLOCKED |
| 3 | `bl-01final-test-codekit01-fixtures-20260925` | project_protocols | `python tests/test_codekit01_fixtures.py` | `Ran 36 tests in 7.771s`（stderr:3）；`OK`（stderr:5） | 0 | 7.969 | 是 | PASS（只有命令级） |
| 4 | `bl-01final-test-baseline-tool-20260925` | baseline_tool | `python tests/test_baseline_tool.py` | `Ran 40 tests in 51.525s`（stderr:43）；`OK`（stderr:45） | 0 | 51.844 | 是 | PASS |
| 5 | `bl-01final-test-legacy-gates-20260925` | legacy_characterization | `python tests/test_legacy_gates.py` | `Ran 24 tests in 118.065s`（stderr:52）；`OK`（stderr:54） | 0 | 118.265 | 是 | PASS |
| 6 | `bl-01final-test-legacy-lifecycle-20260925` | legacy_characterization | `python tests/test_legacy_lifecycle.py` | `Ran 26 tests in 128.438s`（stderr:56）；`OK (skipped=2)`（stderr:58） | 0 | 128.672 | 是 | PASS（24 个方法）；2 项 NOT_RUN |
| 7 | `bl-01final-test-legacy-cli-20260925` | legacy_characterization | `python tests/test_legacy_cli.py` | `Ran 75 tests in 84.147s`（stderr:153）；`OK (skipped=1)`（stderr:155） | 0 | 84.265 | 是 | PASS（74 个方法）；1 项 NOT_RUN |
| 8 | `bl-01final-test-legacy-events-20260925` | legacy_characterization | `python tests/test_legacy_events.py` | `Ran 34 tests in 45.589s`（stderr:71）；`OK`（stderr:73） | 0 | 45.734 | 是 | PASS |

栏的含义：
- `legacy_project`：项目原有全量自测。
- `legacy_characterization`：P4 新增的旧实现特征化回归，被测对象是 a4fa199 的 `scripts/pi_dispatch.py`。它断言旧实现的现状，不修缺陷。
- `project_protocols`：01 新增项目代码（`scripts/codekit/protocols.py`、`sealing.py`、`schemas/`、`tests/fixtures/codekit01/`）的测试。被测对象不是附录 B 的沙箱参考代码。
- `baseline_tool`：取证工具的自测。
- 附录 B 参考代码的验证仍在第 6 节的 `reference_code` 栏，最终取证没有重跑。

逐方法计数（修订 3 按 `run/*.bin` 重算；FAIL、ERROR 行与 Traceback 都是 0）：

| 套件 | 运行 | ok | skipped | 方法级可追溯 |
|---|---|---|---|---|
| test_dispatch | 24 个分节，256 个 check | 256 行 PASS，0 行 FAIL | — | check 级：`PASS <描述>`，按分节对应 test_* 函数；stdout 与实施前逐字节相同，第 5 节的逐函数表原样适用 |
| test_protocols | 324 | 320 | 4 | 是（unittest 逐条输出） |
| test_codekit01_fixtures | 36 | — | 0 | **否**：只有 36 个“.”，没有方法名 |
| test_baseline_tool | 40 | 40 | 0 | 是 |
| test_legacy_gates | 24 | 24 | 0 | 是 |
| test_legacy_lifecycle | 26 | 24 | 2 | 是 |
| test_legacy_cli | 75 | 74 | 1 | 是 |
| test_legacy_events | 34 | 34 | 0 | 是 |

归档文件与摘要。路径都在 `evidence/final/<capture-id>/` 下。`run/*.bin` 的脱敏前后字节相同；`capture.json` 被脱敏改写了 1 处 `<PYDIR>`，括号内是原件摘要。`e3b0c442…b855` 是空内容的 sha256。

| 取证 ID | archive-manifest.json（字节，sha256） | capture.json（sha256；原件） | run/stdout.bin（字节，sha256） | run/stderr.bin（字节，sha256） |
|---|---|---|---|---|
| `bl-01final-test-dispatch-20260925` | 43709，`9b13a01dfd07d654be0b8b2c79c1d3accb4a823bfee6df5afae76a5a886c3ded` | `3a15cf5132802cd33083cd74f2d442e948845c4c1f87b2c636bef74923fb4d44`；原件 `6d18f459…9ced8` | 13423，`f40586e2376e2361bc962878059d732b95c2c8cb0f79d48c3fd069fc37e1080e` | 0，`e3b0c442…b855` |
| `bl-01final-test-protocols-20260925` | 43710，`3707e1cd88fe05c113eaf3acca35f22190b6f525d508c99d5c2fe782df4c3908` | `754c3807fb96f3c04573a5f30261cd3aaa1573fbd54a10bbf05f1e38bbfe5829`；原件 `5433610a…89904` | 0，`e3b0c442…b855` | 73321，`1f30be24ba3b38c4b56e54a01a076e74b630c5cdcb89c4eeb975e84211e9de36` |
| `bl-01final-test-codekit01-fixtures-20260925` | 43715，`6406500f42cae518e8dce7d0616455a8cb4744a2a1af3043146548fab2599222` | `d0e5238ecb1a22be001cd382bf1655730788df5531af7439bc59190d2a88ecf9`；原件 `22486c7e…b2a20` | 0，`e3b0c442…b855` | 140，`689389be7fbd34cdcb40ebe00a954113c293ed9384157b991f72cfee60aa8261` |
| `bl-01final-test-baseline-tool-20260925` | 43712，`f9554817796edf2369e86b31c326eb85ae6b2f55cf1be099599ed5e7a50a0ce4` | `5bce384103bc452b24be555861964919934be87d947134370226dbdab7edfcfe`；原件 `f490d652…5519e` | 0，`e3b0c442…b855` | 5064，`1cf45a96ef531b7df6f8eec633302127c9e77186ae44a6670f8fe1509840eb4a` |
| `bl-01final-test-legacy-gates-20260925` | 43711，`3508c6012489e573c246a141b60293252b9804c1d5b457961eaa16d5712a61e2` | `c66490737c73f1a4c88c4d347c080880e12689c22a054cc2e7afe5dad8c00501`；原件 `f8a58dcf…82439` | 0，`e3b0c442…b855` | 6459，`80d945cd781a868e666fbfb89e2c5a39edd527291d77e92f96d63ac3b4cdffe1` |
| `bl-01final-test-legacy-lifecycle-20260925` | 43715，`c37c4f4866d8813a0cb0b6ff718c6d396568d1d819b5333ff0811ddbce3d187a` | `6c3acdb0d01666d702627f329648883a9584e7a67a79f391565e852e62ac3f21`；原件 `e62c6798…3167c` | 0，`e3b0c442…b855` | 7809，`45e9ec9f0b232815ebbd0c9159090c1f3d10aa95cd65e8d523ab8c2812b1a69b` |
| `bl-01final-test-legacy-cli-20260925` | 43711，`5794ef531a6df45474f9639945f4260b7069e602f83c26369ec302599805cc59` | `e62c951a7a4fe163179a8911da33a714f015de16a9235c03f7c13ff3b751c016`；原件 `e396bca1…2aa23` | 0，`e3b0c442…b855` | 19861，`484493ae4f7412a21b7c473fbfcbb663d891ff5a0e3575943366e242c4440c8c` |
| `bl-01final-test-legacy-events-20260925` | 43712，`4042d5cb7364cb0ed64e21655f5062e3c1124a494da3955b8c8d5d40120f5bba` | `5cf8ffb1d835d9870ca1ee8d2e443c5dd0c86ec3ffe7713047537f20e8b70d79`；原件 `941b7700…db4ad` | 0，`e3b0c442…b855` | 8739，`9dc7c9843ac13b2bf001439f7011214c8d227136113567a0bbc622c3d9be1010` |

### 12.3 跳过的方法（未运行，不计通过）

跳过原因摘自归档 `run/stderr.bin` 原文。

| 取证 ID | 方法 | 状态 | 跳过原因（原文） |
|---|---|---|---|
| `bl-01final-test-protocols-20260925` | `SnapshotTests.test_F017_machine_path_projection_belongs_to_02` | NOT_RUN | 01-D05：配置语义投影归 02，F017 由 02 验收；此处未测试，不代表通过 |
| `bl-01final-test-protocols-20260925` | `PhysicalPathTests.test_F029_replacement_after_check` | NOT_RUN | 01-D06：01 只提供词法校验与静态解析，不实现抗 TOCTOU 的受控访问；F029 由后续访问实现模块验收，此处未测试，不代表通过 |
| `bl-01final-test-protocols-20260925` | `PhysicalPathTests.test_F030_fifo_device_hardlink` | NOT_RUN | 01-D06：01 不实现文件类型与硬链接受控读写；F030 由后续访问实现模块验收，此处未测试，不代表通过 |
| `bl-01final-test-protocols-20260925` | `SchemaFileTests.test_A09_jsonschema_metaschema_optional` | BLOCKED | 未安装 jsonschema，未做元校验（本机不得安装依赖，见 01-L01） |
| `bl-01final-test-legacy-lifecycle-20260925` | `CancelTests.test_LB_LIFE_017_sigint_during_pi_run_is_cancelled_exit_1_posix` | NOT_RUN | 只在 POSIX 上运行：SIGINT 到达调度器的语义（KeyboardInterrupt/_Interrupted）；Windows 用 CTRL_BREAK 用例 |
| `bl-01final-test-legacy-lifecycle-20260925` | `CancelTests.test_LB_LIFE_035_sigint_before_claim_exits_130_posix` | NOT_RUN | 同上 |
| `bl-01final-test-legacy-cli-20260925` | `LegacyMainEntryTest.test_LB_EXIT_029_repo_missing_path_posix_reported_as_git_missing_3` | NOT_RUN | POSIX 分支；本机 Windows 的结果见上一用例（本次 NOT_RUN） |

jsonschema 一项按 2.4 与 01-L07 记 BLOCKED（缺工具且未授权安装），其余记 NOT_RUN。

### 12.4 旧自测实施前后对照

| 项 | 实施前 `bl-01t1-legacy-20260925` | 实施后 `bl-01final-test-dispatch-20260925` |
|---|---|---|
| 汇总行 | `256 checks, 0 failed` | `256 checks, 0 failed` |
| 退出码 | 0 | 0 |
| PASS / FAIL 行 | 256 / 0 | 256 / 0 |
| stderr | 0 字节 | 0 字节 |
| run/stdout.bin | 13423 字节，`f40586e2376e2361…` | 13423 字节，`f40586e2376e2361…`（**逐字节相同**） |
| 被测旧源码 | 第 2 节表中 6 个文件，相对 HEAD 未改 | 同左，sha256 相同 |
| 取证前工作区 | porcelain 37 项；输入清单 92 项；闭包 `8ca10fb9…` | porcelain 319 项；输入清单 373 项；闭包 `2d8f2f71…` |
| 取证工具 | `baseline.py` `9eb03345…` | `baseline.py` `dbb08466…` |
| 耗时 | 250.219 秒 | 216.828 秒 |

- **结论**（measured）：实施前后旧自测结果一致，256/0 → 256/0。两次 stdout 逐字节相同，所以 24 个分节、各函数的 check 数与行号都不变，`test_wrapper_interpreters_and_literal_arguments` 两次都没有运行。状态为 PASS。
- **范围**：两次取证的输入状态不同，工作区增加了 01 的新文件，取证工具版本也不同。“一致”只说明在这两个记录的输入状态下旧自测输出相同；只限 Windows；耗时变化只是记录，不是性能比较。

### 12.5 受保护文件

受保护文件为 `scripts/pi_dispatch.py`、`scripts/dispatch-pi.sh`、`tests/test_dispatch.py`、`tests/stub_pi.py`、`tests/stub_pi_help.txt`、`AGENTS.md`、`.agents/`、`.claude/`。

- **取证时**（measured，8 次取证的 `pre/input-manifest.json`）：
  - 前 6 个文件与 `.agents/`、`.claude/` 下的 42 个文件都是 source=tracked、status_xy=null，即相对 HEAD 与索引没有改动；
  - 前 6 个文件的 sha256 与实施前取证时相同（第 2 节表）。
- **操作者记录**（source_reported）：每次取证后 `git diff HEAD` 对受保护文件为 0 行。
- **报告编写时**（measured，修订 3 核对，不属于取证）：`git diff HEAD` 对这些路径输出 0 行，`git status --porcelain` 为 0 项，sha256 与取证时相同。
- **结论**：相对 HEAD 的差异为 0 行，状态为 PASS，只覆盖列出的路径。

### 12.6 01 新文件的字节（最终取证输入清单）

这些文件都是未跟踪的工作区文件（source=untracked），结论只对下列字节成立。修订 3 编写时逐个核对，都没有变化。

| 文件 | 字节 | SHA-256 |
|---|---|---|
| `scripts/codekit/baseline.py` | 80514 | `dbb08466778db639966336902653525fa26a4f9f9152c5827594ea9313e49ce8` |
| `scripts/codekit/protocols.py` | 188693 | `d980e8ca37c461cbee65b8e11476b133a46bc649323113a4cca97e502f7c6933` |
| `scripts/codekit/sealing.py` | 25001 | `af92c1f97af0d762d59b37c4411c477e39246e8e9fb9d9ccddfd8af42f84f265` |
| `schemas/codekit-public-v1.schema.json` | 13335 | `7895442dc9907b6ab1a0c1dd946a1b0caaf2cdd49caaa1ebabff94fa10cdf291` |
| `tests/test_protocols.py` | 494529 | `5db9c197491a3f3c24e3c070c3f177ed330afe55931351f1e322c5bdacdf2925` |
| `tests/test_codekit01_fixtures.py` | 133849 | `c3c8f1b9a3d68208c46150d7594733cc2cac267d7376bce7ace54fbdb2d50153` |
| `tests/test_baseline_tool.py` | 54951 | `1b7842099e434292124e7354ee77117b4bfb98a4847647ecf7b5df5e5386ee8b` |
| `tests/test_legacy_gates.py` | 66481 | `d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` |
| `tests/test_legacy_lifecycle.py` | 77345 | `f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` |
| `tests/test_legacy_cli.py` | 84800 | `1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` |
| `tests/test_legacy_events.py` | 72723 | `f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` |
| `tests/legacy_harness.py` | 65866 | `3d133d5fcef2aaf41286d739d14133914f3fb8910b9177dc9d4f946f5963d6fb` |
| `tests/codekit01_legacy.py` | 72970 | `9ce7318b35870e208f910716d52880a9161fc04913347b70d1670c1a690dd68d` |

另有 `tests/fixtures/codekit01/` 下 172 个文件，其中 `manifest.json` 的 sha256 为 `50dc2fc3416385b4b33dc731e21416b42f74ad3753149bbc75038c3f2e4fef45`。

### 12.7 归档完整性与残留检查

- **归档命令**：`python scripts/codekit/baseline.py archive .agent/baseline/01-final/<capture-id> --dest docs/code-kit-v2/01-baseline/evidence/final`。8 次退出码都是 0，这一条来自归档子代理的记录（source_reported）。
- **完整性**（measured，修订 3 重算）：
  - 8 个归档目录各有 83 个清单条目、84 个文件（含 archive-manifest.json），共 672 个文件；
  - 清单列出的 664 个文件逐个重算 sha256 与字节数，全部与 `archived_sha256` 一致；
  - 另外 8 个是 `archive-manifest.json` 本身：manifest 不列出自身，这 8 个文件没有 `archived_sha256` 可比，它们的 sha256 只由 INDEX.md 第 1 节与 JSON `acceptance[01-A16].evidence_refs` 手工记录（修订 5 补记；INDEX.md 初版把它们也算进“与 `archived_sha256` 一致”的 672 个，已更正）；
  - 8 份 `archive-manifest.json` 的 `unredacted_files` 都为 `[]`，规则为 redact-v2；
  - 每个归档被脱敏改写的都是同样 5 个文件：`capture.json`、pre/post 的 `environment.json`、pre/post 的 `02-rev-parse-toplevel.stdout.bin`；`run/` 下的文件没有被改动。
- **残留重扫**（measured，修订 3）：
  - 范围是 `evidence/final/` 下 673 个文件（672 个归档文件与 INDEX.md）。每个文件按 UTF-8 解码扫描一遍，字节数为偶数时再按 UTF-16-LE 扫描一遍，不区分大小写。
  - 类别：当前用户名、用户主目录的 8.3 短名、仓库上级目录与桌面目录的路径组合（含多种分隔符与转义）、主机名、规划会话 ID、会话临时目录名、MSYS 盘符写法。
  - 识别类模式在扫描时现场生成，不写入任何文件。
  - 结果：0 个文件命中。
- **已知残留**（没有手工修改归档文件）：
  1. 工具安装目录（Program Files 下的 git、bash、node）：每个归档的 `capture.json` 38 处，pre/post `environment.json` 各 3 处，共 24 个文件 352 处。redact-v2 在 `redaction.not_covered` 中声明不覆盖。
  2. 16 个 `08-diff-unstaged.stdout.bin`（内容相同，sha256 `83c0de2f…`）中已删除旧文档的正文：示例用户名为 `me` 的工作目录、`C:\Windows\Temp`、另一个项目的目录。它们是 HEAD 中已提交文档的内容，不是本机取证定位。
- **结论**：PASS。只说明归档与取证原件一致、按 redact-v2 完成脱敏、没有可识别本机用户的残留。

### 12.8 修订 3 的核对方法

修订 3 编写时只读取归档文件与工作区，没有重跑任何被测命令。核对内容如下，都是 measured：

1. 8 份 `archive-manifest.json` 列出的 664 个文件逐个重算 sha256 与字节数。
2. 8 份 `capture.json` 的退出码、耗时、timed_out、interrupted、stray_processes、baseline_consistent、drift 与 INDEX.md 第 2 节核对。
3. 汇总行与行号按 `run/*.bin` 重新定位；统计逐方法结果，并检查 FAIL:/ERROR: 行与 Traceback。
4. 8 次取证前采样的 porcelain 摘要与输入清单闭包互相比较，并比较每次 pre 与 post 的闭包。
5. 16 份 `environment.json` 的归档字节互相比较，并与实施前基线比较。
6. 13 个源码/测试文件与 172 个 fixture 文件的当前 sha256 同最终取证输入清单比较。
7. 两次旧自测的 `run/stdout.bin` 逐字节比较。
8. legacy-inventory.md 第 12 节 159 行同 4 份归档输出逐条比较（第 7.1 节）。
9. 受保护文件的 `git diff HEAD` 与 `git status --porcelain`。

### 12.9 修订 5 的核对方法

修订 5 编写时只读取归档文件、`.agent/baseline/01-final/` 原件、规划会话临时目录中的操作者记录与工作区，没有重跑任何被测命令。核对内容如下，都是 measured（JSON `post_implementation_regression.verification_revision_5`）：

1. 8 份 `archive-manifest.json`：每份 `files` 83 条、目录 84 个文件，多出的是 manifest 自身；664 个条目的 `archived_sha256` 与归档文件一致，`original_sha256` 与原件一致；8 份 manifest 的 sha256 与 INDEX.md 第 1 节一致。
2. `final2-captures.txt`：1495 字节，sha256 `c362495cc389d37204e1250f8ff613585f5722cb8b0e63c60bcf668b9d11d6dd`；INDEX.md 第 5.2.1 节的转录按规则重建后与原件逐字节相同。
3. 第 7.2 节的 62 个方法逐个在 4 份归档 `run/stderr.bin` 中定位：60 个 `ok`，P4-L03、L04 `skipped`；方法名与 legacy-inventory.md 第 12 节一致。P4-L17 不在 7.2 中，清单把它归在六类之外（01-A08）。
4. JSON 中 13 条 `judged_by_this_report=false` 条目的照录文字由程序从 acceptance.md 第 0、3 节原文复制；证据编号按 acceptance.md 第 2.3 节解析，归档文件的字节数与 sha256 为重算值。

## 13. 收尾取证（closure_regression）

本节对应 JSON 的 `closure_regression` 分区，是修订 6 新增的，不改写第 2–6、9 节的实施前基线与第 12 节的最终取证。

- **取证方式**：收尾轮代码改动（`protocols.py` 的 R-P10、R-P11、M-01；`tests/legacy_harness.py` 与 `tests/codekit01_legacy.py` 的清理前归属核对；fixtures 的 manifest 新字段与 D-20–D-23 新 case）完成后，规划端在受控环境（01-L05）中按 R-01 严格 pyc 口径逐条取证（01-L04），共 10 次，全部在 Windows 上运行。
- **原件与归档**：原件在 `.agent/baseline/01-closure/<capture-id>/`（被 .gitignore 忽略，只读）；脱敏归档在 `evidence/closure/<capture-id>/`。
- **索引**：[evidence/closure/INDEX.md](evidence/closure/INDEX.md)，48511 字节，SHA-256 `85ae818f8a5de0b42cf0568b2a5b5205752012e9340519013c12a3706718f0ba`（修订 7 按勘误后的字节重新固定；修订 6 固定的是 44858 字节 `a6a84822…`，见 JSON `closure_regression.index_ref.history`）。它是归档子代理手写的索引，不是取证产物，不在任何 archive-manifest.json 或取证输入清单中。修订 6 核对了其中第 1–4 节的摘要、计数与行号，都与按归档文件重算的结果一致；修订 7 的勘误只改文字（证据等级写法、第 1 节两列的来源标注、7.1 节计数口径、2.2 节补核），这些数字不变（第 13.10 节）。
- **操作者记录**：[evidence/run-controls-closure/closure-captures.txt](evidence/run-controls-closure/closure-captures.txt)，3133 字节，SHA-256 `fb00af747f1ff3fd7b20a35d5902c918f7057f58bdfb7e9c660d4db57ccc0e86`；复制清单 `manifest.json` 1147 字节，SHA-256 `eed5de9213aa7aa88944b983905cd1b725711f2289e05f270558417309f4ac73`。它是操作者脚本的输出，不是取证工具的输出，按 source_reported 使用。第 8–17 行中能与取证工具记录对照的字段——capture-id、argv、executed、returncode、reason、timed_out、duration、baseline_consistent 与汇总行文字——与各 capture.json、run/*.bin 一致（measured；INDEX.md 2.2 节核对其中 7 项，修订 7 补核 executed、reason）；同一行的 `tool_exit`、`leaked` 在 capture.json 中没有对应字段，无法核对，只有操作者记录（source_reported）。修订 6 原写“与各 capture.json 逐字段一致”，说过头了，修订 7 更正。第 20 行参照时刻偏晚，不作证据。
- **与最终取证的关系**：就实施后的项目验证而言，本节取代第 12 节；`bl-01final-*` 与 `evidence/final/` 保留为历史证据，按 R-01 原口径解释。中间一轮 `01-P4` 没有归档，本报告不引用。
- **日期**：capture-id 中的日期取规划端本地日期；取证工具记录的 UTC 时间是 2026-09-26T14:47:10.580687Z 至 2026-09-26T15:00:06.978434Z。

### 13.1 共同条件

- **基线**：10 次取证的 HEAD 都是 `a4fa199b0e5bdc658215765ee7558b9fe6723940`（sha1，commit），与调查提交一致。20 次采样的工作区状态完全相同，取证之间工作区没有变化：
  - porcelain 1019 项，sha256 `af6f80a3c5a70cb855d48ef61b2f3529672bced931b0db05c24550f118a00025`；
  - 输入清单 1073 项（已跟踪 63、未跟踪 1010），清单 sha256 `3a559ca5cc328a9632831666f5f59137df0484b2fc5f778af351843cdd619982`，闭包 `81b4503e291166fd78632aab9163faac2f0e25c92db11c691dfbe753068f52a4`；每次取证 pre 与 post 的闭包相同；
  - closure_status=partial，缺口为：被忽略文件不计摘要、子模块不展开、仓库外输入不纳入、gitattributes 效果不评估；被忽略的名称只有 `scripts/__pycache__/`、`tests/__pycache__/`；排除规则只有 `.agent/baseline/`；没有子模块；
  - 6 项是工作区中已删除、未暂存的已跟踪旧文档，没有字节可计摘要。
- **取证工具**：`scripts/codekit/baseline.py`，sha256 `dbb08466778db639966336902653525fa26a4f9f9152c5827594ea9313e49ce8`，与最终取证相同。
- **监督器**：`scripts/pi_dispatch.py::run_supervised`，module_sha256 `a00d693452b4345d6093efa9864de6e1b4cefacece867b617e68e6a8efce3ad4`，工具版本 2.2.2。
- **运行方式**：cwd 为仓库根，stdin 接 devnull，shell=false；Job Object 监督，时限 3600 秒，宽限 15 秒；子进程环境新增 `GCM_INTERACTIVE`、`GIT_TERMINAL_PROMPT`、`PYTHONDONTWRITEBYTECODE`，没有移除任何变量。
- **环境**（measured，各取证的 pre/post `environment.json`）：Windows 10.0.26100（2025Server，AMD64），CPython 3.12.10，git 2.55.0.windows.5，GNU bash 5.3.15；core.* 与第 3.1 节相同；pi、claude、codex 在 20 次采样中都不在 PATH 上；13 个被检查的变量名中只有 `PI_CODING_AGENT_DIR` 存在（不含 `PYTHONPYCACHEPREFIX`，取证工具不检查它）；20 份 `environment.json` 的归档字节相同（sha256 `097cb8a4…`），与最终取证、实施前基线的相同。
- **环境**（source_reported，操作者记录第 3–7、18–19 行）：在 Git Bash 中运行；PATH 去掉了真实 pi、claude、codex 所在目录；unset 了会话令牌变量；`PI_CODING_AGENT_DIR` 指向空目录，取证后仍为空；`PYTHONPYCACHEPREFIX` 指向取证前为空的目录（R-01）；受控条件下 pi、claude、codex 都定位不到；取证前后受保护文件 diff 为 0 行；每次取证 `tool_exit=0`、`leaked=[]`。与最终取证不同，这些条件都写在同一份已归档的记录中。

取证时 01 相关文件的字节（收尾取证 `pre/input-manifest.json`，measured；修订 6 编写时逐个重算，都没有变化）：

| 文件 | 字节 | SHA-256 |
|---|---|---|
| `docs/code-kit-v2-design.md` | 32912 | `82e8e668d8de46bee7b826951f346023220f35c51ea39be4ca0bd222df74d1d1` |
| `docs/code-kit-v2/01-baseline/protocols-api.md` | 301574 | `785c75f6c3481065fcf8c7a04ea56018a6d69d0309203cc037e3c1b19b016fa0` |
| `schemas/codekit-public-v1.schema.json` | 13335 | `7895442dc9907b6ab1a0c1dd946a1b0caaf2cdd49caaa1ebabff94fa10cdf291` |
| `scripts/codekit/__init__.py` | 82 | `145ff733182c785d097833d8402adc0ee4487de1998ce917f3b4102be88cb8f9` |
| `scripts/codekit/baseline.py` | 80514 | `dbb08466778db639966336902653525fa26a4f9f9152c5827594ea9313e49ce8` |
| `scripts/codekit/protocols.py` | 215838 | `64d75bb0a5b37a5dd93240eac3f58455538a12e58c91b324a72b3d14708bc42b` |
| `scripts/codekit/sealing.py` | 25001 | `af92c1f97af0d762d59b37c4411c477e39246e8e9fb9d9ccddfd8af42f84f265` |
| `tests/codekit01_legacy.py` | 87792 | `f1d208361aabfff72e98005ed9e5e7003506a72e7bab7b9c7e8ff392962d6e86` |
| `tests/fixtures/codekit01/expected/legacy-contracts.json` | 254437 | `5328bb62721095f07ac48350c53aa74e6a0e8dc64440ab15a713c618fc866ed0` |
| `tests/fixtures/codekit01/expected/legacy-events.json` | 107353 | `e889fef038d674d155a8b5cbb1403e07a8a469b36e9b8c8eec0ff44eba34973b` |
| `tests/fixtures/codekit01/expected/legacy-new-strict.json` | 15638 | `e936407998da7042596c68223cbb9fbfb6c94409e258a6ae9888a832be71af82` |
| `tests/fixtures/codekit01/manifest.json` | 408977 | `95c58a9b5a68166e104ee8a719385d43a8f346bff96ab96806518d6c94a830e0` |
| `tests/legacy_harness.py` | 79723 | `c4e871372a35f35c59a76172ccc366a50316c5af9ad3ec4703d1fb6c27d4b974` |
| `tests/test_baseline_tool.py` | 54951 | `1b7842099e434292124e7354ee77117b4bfb98a4847647ecf7b5df5e5386ee8b` |
| `tests/test_codekit01_fixtures.py` | 214461 | `16b71bca5f0c86378a00b59fcfc6426de4772b79f04cf356ae6ee4525131a57b` |
| `tests/test_legacy_cli.py` | 84800 | `1add8bda0c5478f9899220df5db1e76e3caba2c3bd8c6e1af2783cb07d0de532` |
| `tests/test_legacy_events.py` | 72723 | `f1f7a3b330502eec4027e7c32b07e022dc843776e49567561319647fb5c714b7` |
| `tests/test_legacy_gates.py` | 66481 | `d5d1a478ed62832a3283a82c1b50dfaf173d8cb85876de664c745d6ebe67a1f7` |
| `tests/test_legacy_lifecycle.py` | 77345 | `f3be8b623cfbe766a3b06acc349acafb0dd1d54cb3c3313e7b1c9af57a2d95fd` |
| `tests/test_protocols.py` | 558783 | `b0d354a1d33d7d7e592e9e78f26a0896531f256e4f1eba2a59d98b80b917859b` |

另有 `tests/fixtures/codekit01/` 下 189 个文件（188 个登记文件加 manifest.json）。被测旧源码 6 个文件（第 2 节表）的 sha256 与实施前基线、最终取证时相同，都是 source=tracked、相对 HEAD 没有改动；`.agents/`、`.claude/` 下 42 个文件同样没有改动。

### 13.2 逐条结果

10 条命令都在仓库根运行。“结果”是 `run/*.bin` 中的原文，括号内是文件与行号；退出码、耗时与前后一致性取自该取证的 `capture.json`。10 次都满足：`execution_status=complete`，timed_out、interrupted、stray_processes 都为 false，`spawn_error=null`，drift 为空。执行状态是本报告对该命令结果的判定，跳过的方法不计通过。

| # | 取证 ID | 栏 | 命令 | 结果（原文） | 退出码 | 耗时 (s) | 前后一致 | 执行状态 |
|---|---|---|---|---|---|---|---|---|
| 1 | `bl-01closure-test-dispatch-20260926` | legacy_project | `python tests/test_dispatch.py` | `256 checks, 0 failed`（stdout.bin:282） | 0 | 235.828 | 是 | PASS（限 Windows 已运行的 256 项） |
| 2 | `bl-01closure-test-protocols-20260926` | project_protocols | `python tests/test_protocols.py` | `Ran 342 tests in 4.291s`（stderr.bin:687）；`OK (skipped=4)`（stderr.bin:689） | 0 | 4.578 | 是 | PASS（338 个方法）；3 项 NOT_RUN；1 项 BLOCKED |
| 3 | `bl-01closure-test-baseline-tool-20260926` | baseline_tool | `python tests/test_baseline_tool.py` | `Ran 40 tests in 57.652s`（stderr.bin:43）；`OK`（stderr.bin:45） | 0 | 58.063 | 是 | PASS（40 个方法） |
| 4 | `bl-01closure-test-legacy-gates-20260926` | legacy_characterization | `python tests/test_legacy_gates.py` | `Ran 24 tests in 128.419s`（stderr.bin:52）；`OK`（stderr.bin:54） | 0 | 128.735 | 是 | PASS（24 个方法） |
| 5 | `bl-01closure-test-legacy-lifecycle-20260926` | legacy_characterization | `python tests/test_legacy_lifecycle.py` | `Ran 26 tests in 140.098s`（stderr.bin:56）；`OK (skipped=2)`（stderr.bin:58） | 0 | 140.469 | 是 | PASS（24 个方法）；2 项 NOT_RUN |
| 6 | `bl-01closure-test-legacy-cli-20260926` | legacy_characterization | `python tests/test_legacy_cli.py` | `Ran 75 tests in 92.991s`（stderr.bin:153）；`OK (skipped=1)`（stderr.bin:155） | 0 | 93.234 | 是 | PASS（74 个方法）；1 项 NOT_RUN |
| 7 | `bl-01closure-test-legacy-events-20260926` | legacy_characterization | `python tests/test_legacy_events.py` | `Ran 34 tests in 51.774s`（stderr.bin:71）；`OK`（stderr.bin:73） | 0 | 52.0 | 是 | PASS（34 个方法） |
| 8 | `bl-01closure-test-codekit01-fixtures-v-20260926` | project_protocols | `python tests/test_codekit01_fixtures.py -v` | `Ran 75 tests in 11.260s`（stderr.bin:105）；`OK`（stderr.bin:107） | 0 | 11.61 | 是 | PASS（75 个方法） |
| 9 | `bl-01closure-legacy-check-20260926` | project_protocols | `python tests/codekit01_legacy.py --check` | `38 checks, 0 differ`（stdout.bin:39） | 0 | 9.703 | 是 | PASS（38 项 SAME，0 项 DIFF） |
| 10 | `bl-01closure-legacy-check-stub-regen-20260926` | project_protocols | `python tests/codekit01_legacy.py --check-stub-regen` | `10 checks, 0 differ`（stdout.bin:11） | 0 | 0.703 | 是 | PASS（10 项 SAME，0 项 DIFF） |

栏的含义同第 12.2 节；`project_protocols` 在本节还包含 `codekit01_legacy.py` 的两条核对命令（它们核对 01 新增的兼容 fixtures 与锁定预期，归栏是本报告的分类）。附录 B 参考代码的验证仍在第 6 节的 `reference_code` 栏，收尾取证没有重跑。

逐方法计数（修订 6 按 `run/*.bin` 重算；FAIL:、ERROR: 行与 Traceback 都是 0）：

| 套件 | 运行 | ok | skipped | 方法级可追溯 | 与最终取证相比 |
|---|---|---|---|---|---|
| test_dispatch.py | 24 个分节，256 个 check | 256 行 PASS，0 行 FAIL | — | check 级，按分节对应 test_* 函数；第 5 节逐函数表原样适用 | stdout 逐字节相同 |
| test_protocols.py | 342 | 338 | 4 | 是 | 新增 18 个方法，没有减少，其余结果相同 |
| test_baseline_tool.py | 40 | 40 | 0 | 是 | 方法集合与结果相同 |
| test_legacy_gates.py | 24 | 24 | 0 | 是 | 方法集合与结果相同 |
| test_legacy_lifecycle.py | 26 | 24 | 2 | 是 | 方法集合与结果相同 |
| test_legacy_cli.py | 75 | 74 | 1 | 是 | 方法集合与结果相同 |
| test_legacy_events.py | 34 | 34 | 0 | 是 | 方法集合与结果相同 |
| test_codekit01_fixtures.py -v | 75 | 75 | 0 | 是 | 最终取证只有 36 个“.”，不能逐方法比较 |
| codekit01_legacy.py --check | 38 项 | 38 行 SAME | — | 项级（每行一个对象） | 最终取证没有这条命令 |
| codekit01_legacy.py --check-stub-regen | 10 项 | 10 行 SAME | — | 项级（每行一个对象） | 最终取证没有这条命令 |

归档文件与摘要。路径都在 `evidence/closure/<capture-id>/` 下。`run/*.bin` 的脱敏前后字节相同；`capture.json` 被脱敏改写了 1 处 `<PYDIR>`，括号内是原件摘要。`e3b0c442…b855` 是空内容的 sha256。

| 取证 ID | archive-manifest.json（字节，sha256） | capture.json（字节，sha256；原件） | run/stdout.bin（字节，sha256） | run/stderr.bin（字节，sha256） |
|---|---|---|---|---|
| `bl-01closure-test-dispatch-20260926` | 43723，`fd4a0d3687e615c6ae06d70b79ded6a59924ff829d4a44265a8aeb12c5d7d31d` | 37048，`7a3d33148a117766d50fc9ab4e27e8ea3c1b0d41816f2d09594dd799541ca114`；原件 `a5d1c5ec…` | 13423，`f40586e2376e2361bc962878059d732b95c2c8cb0f79d48c3fd069fc37e1080e` | 0，`e3b0c442…b855` |
| `bl-01closure-test-protocols-20260926` | 43724，`d91e78995fbfa90790274f60139ffb52d58fb3b2c50c21cfe8eea6d589e56037` | 37048，`9bb0a5d272fad21fb7e565c084f03c86846fafe7cec51e51a2ede8121854aca3`；原件 `c0df97cd…` | 0，`e3b0c442…b855` | 77955，`5b81e659c60f296503dd99e836a938fa45134ffe597fb960a204b56ee65354c8` |
| `bl-01closure-test-baseline-tool-20260926` | 43726，`22694ddf02256dabdace3bfe3e85aa039779cb80284d43fbf48b5ede7ccbd9f0` | 37063，`de6f1c35b459cec59df593b4b7a9cdc5d27c54a8bd06b4579b5579fc5786214d`；原件 `5b05e0a3…` | 0，`e3b0c442…b855` | 5064，`024b9d508c236c504ee277b9aa07db14f45ad32235d547c1d161002121f22863` |
| `bl-01closure-test-legacy-gates-20260926` | 43725，`6e7a47cc1d8ba259297d9c6a3e30d4226782bb1483730318df685b02598d2f11` | 37059，`b8753abda447daa6de981c20eeb76b5f9caeb734bf9b80af859908a4e999983b`；原件 `c6ea48d5…` | 0，`e3b0c442…b855` | 6459，`97af8357a3730e301a70d6890bfc1d1463186590d25f4db15d7348ea938138f6` |
| `bl-01closure-test-legacy-lifecycle-20260926` | 43729，`8b5d41c20fe4544fef6004862b3394495793bee0998b855951585e9e1b4b43bd` | 37077，`04d09d2514448074bf895b3b64e6afb5afb678163b1e9af94af234280ead95bc`；原件 `82582d8e…` | 0，`e3b0c442…b855` | 7809，`e79ad9f8e4e9f8330f7677f2696ae9908dc6604b2735f955c62813924a2aa99f` |
| `bl-01closure-test-legacy-cli-20260926` | 43725，`38734036c2d20153d9cd5f9b91aebc077b05b09920ae347078194bd52256ab5c` | 37054，`f1c7eb2453524c6be4383e3490006e3afcbdab26cc2962a95e18592b993f3f7f`；原件 `81eb9fe0…` | 0，`e3b0c442…b855` | 19861，`26cce1cf6ad440b5f584180592d772bb4e720e2a54f353694f458bef6a16c3ae` |
| `bl-01closure-test-legacy-events-20260926` | 43726，`b341914ffa16dfc2e41a18491e2696a0b4bcadcae8499b15eaf9a638a487d302` | 37060，`e1da8d27a1df5e5fd9e48069f8e0d57a78b08a556792f7a64393b30ceb527109`；原件 `1fcd3f46…` | 0，`e3b0c442…b855` | 8739，`e5cfa16608d66529963a69a7a10236c294873692b3efe19f5773b0c6bbe70166` |
| `bl-01closure-test-codekit01-fixtures-v-20260926` | 43735，`54b9132f3abcfa4cb79d065dec860290f2f3fa71fc8c58ccfb6cbd4c1ea69153` | 37099，`e661873ef738d4e19084e3386b6cef15001bf595987dc16b90e89fe620e45db1`；原件 `1a05c650…` | 0，`e3b0c442…b855` | 13127，`95faa68cea9315a4a73cc4bfc4223916e56b8eb1b9e5694fa1415fdf1c8b169a` |
| `bl-01closure-legacy-check-20260926` | 43720，`b74b9513906ee3fb72602db703ebed6a37cebc3cfc843887a9dae0f8bb2619dc` | 37066，`35bceb51497f5573e86e6b7426deba71e60d1f8b8a258d27cd9f7537306a8e3c`；原件 `92d7edd3…` | 3712，`2a06d6b3069d23cbb24649983cbced3770476d7b5a3fdf16e751dea94580f5d2` | 0，`e3b0c442…b855` |
| `bl-01closure-legacy-check-stub-regen-20260926` | 43729，`c8833dc2557af3eb99990a7fecd3cda742e6a9b7a6cc40410bb03330209f7237` | 37106，`d3a50b3545a381ddb5a6f6aa969247eba1b5251569dae106261491d344e2a141`；原件 `c9dbf242…` | 273，`9a942083ceece639e010b0771c7c2f0efd68470d40f8cd72766d76d63de1a785` | 0，`e3b0c442…b855` |

### 13.3 跳过的方法（未运行，不计通过）

跳过原因摘自归档 `run/stderr.bin` 原文；行号为起始行 / 结果行。与最终取证中跳过的 7 个方法相同。

| 取证 ID | 方法 | 行号 | 状态 | 跳过原因（原文） |
|---|---|---|---|---|
| `bl-01closure-test-protocols-20260926` | `PhysicalPathTests.test_F029_replacement_after_check` | 223 / 224 | NOT_RUN | 01-D06：01 只提供词法校验与静态解析，不实现抗 TOCTOU 的受控访问；F029 由后续访问实现模块验收，此处未测试，不代表通过 |
| `bl-01closure-test-protocols-20260926` | `PhysicalPathTests.test_F030_fifo_device_hardlink` | 225 / 226 | NOT_RUN | 01-D06：01 不实现文件类型与硬链接受控读写；F030 由后续访问实现模块验收，此处未测试，不代表通过 |
| `bl-01closure-test-protocols-20260926` | `SchemaFileTests.test_A09_jsonschema_metaschema_optional` | 367 / 368 | BLOCKED | 未安装 jsonschema，未做元校验（本机不得安装依赖，见 01-L01） |
| `bl-01closure-test-protocols-20260926` | `SnapshotTests.test_F017_machine_path_projection_belongs_to_02` | 503 / 504 | NOT_RUN | 01-D05：配置语义投影归 02，F017 由 02 验收；此处未测试，不代表通过 |
| `bl-01closure-test-legacy-lifecycle-20260926` | `CancelTests.test_LB_LIFE_017_sigint_during_pi_run_is_cancelled_exit_1_posix` | 30 / 31 | NOT_RUN | 只在 POSIX 上运行：SIGINT 到达调度器的语义（KeyboardInterrupt/_Interrupted）；Windows 用 CTRL_BREAK 用例 |
| `bl-01closure-test-legacy-lifecycle-20260926` | `CancelTests.test_LB_LIFE_035_sigint_before_claim_exits_130_posix` | 34 / 35 | NOT_RUN | 只在 POSIX 上运行：SIGINT 到达调度器的语义（KeyboardInterrupt/_Interrupted）；Windows 用 CTRL_BREAK 用例 |
| `bl-01closure-test-legacy-cli-20260926` | `LegacyMainEntryTest.test_LB_EXIT_029_repo_missing_path_posix_reported_as_git_missing_3` | 21 / 22 | NOT_RUN | POSIX 分支；本机 Windows 的结果见上一用例（本次 NOT_RUN） |

另有旧自测的 `test_wrapper_interpreters_and_literal_arguments`：在 Windows 上直接 return，没有 check，记 NOT_RUN。jsonschema 一项按 2.4 与 01-L07 记 BLOCKED，其余记 NOT_RUN。

### 13.4 逐方法可追溯性

**`test_codekit01_fixtures.py -v`**（`bl-01closure-test-codekit01-fixtures-v-20260926`）：75 个方法都有方法名且都是 ok，没有跳过。按类汇总如下，逐个方法与行号见 JSON `closure_regression.method_results.fixtures_v_methods_by_class` 与 INDEX.md 4.3 节。

| 类 | 方法数 | stderr 行范围 | 结果 |
|---|---|---|---|
| `CleanupOwnershipTests` | 10 | 1–13 | 全部 ok |
| `CompatMatrixDCaseTests` | 5 | 14–18 | 全部 ok |
| `CredentialScanTests` | 4 | 19–25 | 全部 ok |
| `DifferentialTests` | 7 | 26–32 | 全部 ok |
| `FileIntegrityTests` | 4 | 33–37 | 全部 ok |
| `GeneratorGuardTests` | 2 | 38–41 | 全部 ok |
| `HarnessCleanupOwnershipTests` | 11 | 42–63 | 全部 ok |
| `LegacySourceTests` | 2 | 64–65 | 全部 ok |
| `ManifestTests` | 7 | 66–74 | 全部 ok |
| `NegativeTests` | 4 | 75–79 | 全部 ok |
| `PublicEntryRejectionTests` | 3 | 80–82 | 全部 ok |
| `R11Tests` | 6 | 83–92 | 全部 ok |
| `StubTests` | 2 | 93–94 | 全部 ok |
| `SyntheticTests` | 8 | 95–102 | 全部 ok |

收尾轮新增的几类（凭据扫描 `CredentialScanTests`、R-P11 `R11Tests`、D-20–D-23 `CompatMatrixDCaseTests`、清理前归属核对 `CleanupOwnershipTests` 与 `HarnessCleanupOwnershipTests`）与裁决的对应只按名称，修订 6 没有复核断言内容（L-CLOSURE-STATIC-MAPPING）。

**`test_protocols.py` 相对最终取证新增的 18 个方法**（`bl-01closure-test-protocols-20260926`，都是 ok；按方法名归类：M-01 5 个、R-P11 6 个、R-P10 7 个；没有减少的方法，两次都有的 324 个方法结果相同）：

| 方法 | stderr 行 |
|---|---|
| `EventTests.test_A11_m01_append_event_request_and_role_binding` | 83–84 |
| `EventTests.test_A11_m01_binding_reason_order_is_fixed` | 85–86 |
| `EventTests.test_A11_m01_entry_points_agree` | 87–88 |
| `EventTests.test_A11_m01_event_log_request_and_role_binding` | 89–90 |
| `EventTests.test_A11_m01_unreadable_binding_fields` | 91–92 |
| `ProvenanceTests.test_A12_r_p11_check_order_structure_then_steps` | 245–246 |
| `ProvenanceTests.test_A12_r_p11_integrity_limits_complete_stream_claims` | 247–248 |
| `ProvenanceTests.test_A12_r_p11_manifest_set_reports_entry_pointer` | 249–250 |
| `ProvenanceTests.test_A12_r_p11_new_fields_structure` | 251–252 |
| `ProvenanceTests.test_A12_r_p11_structure_preservation_limits_field_semantics_claims` | 253–254 |
| `ProvenanceTests.test_A12_r_p11_traceable_and_capture_rules` | 255–256 |
| `ResourceRefTests.test_A04_r_p10_declaration_values_validated` | 271–272 |
| `ResourceRefTests.test_A04_r_p10_default_registry_declarations` | 273–274 |
| `ResourceRefTests.test_A04_r_p10_public_schema_payload_validator` | 275–276 |
| `ResourceRefTests.test_A04_r_p10_registration_requires_three_declarations` | 277–278 |
| `ResourceRefTests.test_A04_r_p10_validate_resource_payload_representations` | 279–280 |
| `ResourceRefTests.test_A04_r_p10_validator_exceptions_are_wrapped` | 281–282 |
| `ResourceRefTests.test_A12_r_p10_fixture_manifest_payload_validator` | 293–294 |

**P4 特征化回归**：4 个文件共 159 个方法，156 个 ok，3 个 skipped（`CancelTests.test_LB_LIFE_017_sigint_during_pi_run_is_cancelled_exit_1_posix`、`CancelTests.test_LB_LIFE_035_sigint_before_claim_exits_130_posix`、`LegacyMainEntryTest.test_LB_EXIT_029_repo_missing_path_posix_reported_as_git_missing_3`）；方法集合与每个方法的结果都与最终取证相同。

**01-A07 的 62 个方法**（第 7.2 节索引）在收尾取证归档中的位置。取证 ID 缩写：gates、lifecycle、cli、events 分别指 `bl-01closure-test-legacy-{gates,lifecycle,cli,events}-20260926`；行号是 `run/stderr.bin` 的起始行–结果行：

| 编号 | 取证 | 行号 | 结果 |
|---|---|---|---|
| P4-G01 | gates | 4–5 | measured / PASS |
| P4-G02 | gates | 8–9 | measured / PASS |
| P4-G03 | gates | 6–7 | measured / PASS |
| P4-G04 | gates | 10–11 | measured / PASS |
| P4-G05 | gates | 14–15 | measured / PASS |
| P4-G06 | gates | 12–13 | measured / PASS |
| P4-G07 | gates | 16–17 | measured / PASS |
| P4-G08 | gates | 18–19 | measured / PASS |
| P4-G09 | gates | 32–33 | measured / PASS |
| P4-G10 | gates | 24–25 | measured / PASS |
| P4-G11 | gates | 26–27 | measured / PASS |
| P4-G12 | gates | 22–23 | measured / PASS |
| P4-G13 | gates | 20–21 | measured / PASS |
| P4-G14 | gates | 2–3 | measured / PASS |
| P4-G15 | gates | 28–29 | measured / PASS |
| P4-G16 | gates | 30–31 | measured / PASS |
| P4-G17 | gates | 34–35 | measured / PASS |
| P4-G18 | gates | 36–37 | measured / PASS |
| P4-G19 | gates | 38–39 | measured / PASS |
| P4-G20 | gates | 40–41 | measured / PASS |
| P4-G21 | gates | 42–43 | measured / PASS |
| P4-G22 | gates | 44–45 | measured / PASS |
| P4-G23 | gates | 48–49 | measured / PASS |
| P4-G24 | gates | 46–47 | measured / PASS |
| P4-L01 | lifecycle | 28–29 | measured / PASS |
| P4-L02 | lifecycle | 32–33 | measured / PASS |
| P4-L03 | lifecycle | 30–31 | NOT_RUN（skipped，POSIX 分支） |
| P4-L04 | lifecycle | 34–35 | NOT_RUN（skipped，POSIX 分支） |
| P4-L05 | lifecycle | 52–53 | measured / PASS |
| P4-L06 | lifecycle | 24–25 | measured / PASS |
| P4-L07 | lifecycle | 26–27 | measured / PASS |
| P4-L08 | lifecycle | 6–7 | measured / PASS |
| P4-L09 | lifecycle | 8–9 | measured / PASS |
| P4-L10 | lifecycle | 10–11 | measured / PASS |
| P4-L11 | lifecycle | 18–19 | measured / PASS |
| P4-L12 | lifecycle | 16–17 | measured / PASS |
| P4-L13 | lifecycle | 14–15 | measured / PASS |
| P4-L14 | lifecycle | 20–21 | measured / PASS |
| P4-L15 | lifecycle | 12–13 | measured / PASS |
| P4-L16 | lifecycle | 22–23 | measured / PASS |
| P4-L18 | lifecycle | 44–45 | measured / PASS |
| P4-L19 | lifecycle | 48–49 | measured / PASS |
| P4-L20 | lifecycle | 46–47 | measured / PASS（白盒） |
| P4-L21 | lifecycle | 50–51 | measured / PASS（白盒） |
| P4-L22 | lifecycle | 42–43 | measured / PASS |
| P4-C25 | cli | 115–116 | measured / PASS（白盒） |
| P4-C26 | cli | 113–114 | measured / PASS（白盒） |
| P4-C27 | cli | 117–118 | measured / PASS（白盒） |
| P4-C28 | cli | 119–120 | measured / PASS（白盒） |
| P4-C58 | cli | 77–78 | measured / PASS |
| P4-C59 | cli | 79–80 | measured / PASS |
| P4-C62 | cli | 85–86 | measured / PASS |
| P4-C63 | cli | 91–92 | measured / PASS |
| P4-C68 | cli | 99–100 | measured / PASS |
| P4-C69 | cli | 97–98 | measured / PASS |
| P4-C70 | cli | 103–104 | measured / PASS |
| P4-C71 | cli | 101–102 | measured / PASS |
| P4-C72 | cli | 107–108 | measured / PASS |
| P4-C73 | cli | 105–106 | measured / PASS |
| P4-C74 | cli | 109–110 | measured / PASS |
| P4-C75 | cli | 111–112 | measured / PASS |
| P4-E20 | events | 19–20 | measured / PASS |

方法名见第 7.2 节；各方法断言了什么以 legacy-inventory.md 第 12 节为准（source_inspected）。

### 13.5 R-01：pyc 的受控禁用与证据等级

- **规则**：decisions.md R-01：被测命令读取的字节都必须在取证时计摘要或受控禁用；收尾轮的全部取证设 PYTHONPYCACHEPREFIX 指向取证前为空的临时目录，使解释器不读取仓库中的 __pycache__（受控禁用），并在取证记录中写明。
- **仓库中的 pyc**：输入清单只列两个被忽略的目录名，不计摘要（measured）；修订 6 编写时两个目录中分别只有 pi_dispatch.cpython-312.pyc 与 test_dispatch.cpython-312.pyc（只列了文件名，不属于取证）。
- **受控禁用的设置**：只有操作者记录（`closure-captures.txt` 第 4 行设置、第 6 行取证前前缀目录条目数为 0），source_reported；没有记录取证后前缀目录的条目数，也没有记录被测进程环境中是否确有该变量。
- **取证工具的测量**：没有测量这个变量。environment.json 的 env_names_present 只检查 13 个指定名称，不含 PYTHONPYCACHEPREFIX；input-manifest.json 的 python_startup 只记 PYTHONHOME、PYTHONPATH、PYTHONSTARTUP；capture.json 的 run.env_added_names 为 GCM_INTERACTIVE、GIT_TERMINAL_PROMPT、PYTHONDONTWRITEBYTECODE，env_removed_names 为空（measured）。
- **被测进程是否继承**（source_inspected）：run.env_policy 写明子进程继承当前环境，只移除仓库重定向变量与推送/发布类凭据；按这段文字，操作者设置的变量会传给被测进程。测试内部：tests/test_dispatch.py 的 BASE_ENV=dict(os.environ)、tests/legacy_harness.py 的受控环境（REMOVED_NAMES 不含 PYTHONPYCACHEPREFIX）、tests/test_baseline_tool.py 的 base_env 都继承；tests/test_protocols.py 用 python -B -I 与最小环境启动的子进程不继承（-I 忽略全部 PYTHON* 变量），这些子进程只导入 scripts/codekit/ 下的模块，而取证时仓库中没有 scripts/codekit/__pycache__/（输入清单的忽略名只有两个，measured），所以不读仓库中的 pyc。pi_dispatch.py 与 stub_pi.py 在子进程中以脚本方式运行，脚本本身不经 pyc。
- **被测进程不写 pyc**：PYTHONDONTWRITEBYTECODE 在 run.env_added_names 中（measured），被测进程不写 pyc。
- **仓库外的字节码**：取证工具进程本身没有设置 PYTHONDONTWRITEBYTECODE（environment.json 中该名称为 false，python_startup.sys_flags.dont_write_bytecode=0，measured）。按 CPython 的行为，设了 PYTHONPYCACHEPREFIX 时它自身导入的标准库字节码会写到前缀目录，之后的被测进程可能读到这些字节码。取证工具只导入标准库，并以 compile 执行 pi_dispatch.py 的字节（scripts/codekit/baseline.py:277-295，source_inspected），所以前缀目录中不会出现仓库模块的字节码；标准库字节码属于已声明的闭包缺口 out_of_repo_inputs_not_included。前缀目录取证后的条目数没有记录，这一段是推断，不是测量。
- **旁证**：三次旧自测的 run/stdout.bin 逐字节相同（sha256 f40586e2376e2361bc962878059d732b95c2c8cb0f79d48c3fd069fc37e1080e，13423 字节，measured）：bl-01t1 与 bl-01final 读取了未计摘要的 pyc，bl-01closure 按操作者记录禁用了 pyc。这说明输出不依赖那份 pyc，但不能代替 R-01 要求的“取证时受控禁用”的记录。
- **结论**：在操作者记录成立的前提下，仓库中 __pycache__ 这一缺口按 R-01 的规定关闭（受控禁用，不是计摘要）；受控禁用本身的证据等级是 source_reported，取证工具没有独立测量。被忽略的两个目录仍只列名称、不计摘要；仓库外输入与 gitattributes 效果仍不在闭包内。
- **历史取证**：bl-01t1-legacy-20260925 与 bl-01final-test-dispatch-20260925 读取了未计摘要的 scripts/__pycache__/pi_dispatch.cpython-312.pyc；按 R-01 它们按原口径保留、不改写，在严格口径下不满足 pyc 要求，不作为 01-A01 修订 6 判定的依据。其余 7 次最终取证不读这份 pyc（修订 3，source_inspected）。

### 13.6 旧自测三次对照

| 项 | `bl-01t1-legacy-20260925`（实施前） | `bl-01final-test-dispatch-20260925`（最终，历史） | `bl-01closure-test-dispatch-20260926`（收尾） |
|---|---|---|---|
| 汇总行 | `256 checks, 0 failed` | 同左 | 同左 |
| 退出码 / stderr | 0 / 0 字节 | 同左 | 同左 |
| run/stdout.bin | 13423 字节，`f40586e2376e2361…` | 同左（逐字节相同） | 同左（逐字节相同） |
| 取证前工作区 | porcelain 37 项；输入清单 92 项；闭包 `8ca10fb9…` | porcelain 319 项；输入清单 373 项；闭包 `2d8f2f71…` | porcelain 1019 项；输入清单 1073 项；闭包 `81b4503e…` |
| pyc | 进程内导入读取了未计摘要的 scripts/__pycache__/pi_dispatch.cpython-312.pyc（原口径） | 同上（原口径） | PYTHONPYCACHEPREFIX 指向取证前为空的目录（R-01，依据只有操作者记录） |
| 耗时 | 250.219 秒 | 216.828 秒 | 235.828 秒 |

- **结论**（measured）：三次旧自测都是 256 checks, 0 failed、退出码 0、stderr 为空；run/stdout.bin 三份逐字节相同（13423 字节，sha256 f40586e2376e2361bc962878059d732b95c2c8cb0f79d48c3fd069fc37e1080e），所以第 5 节的逐函数表（24 个分节、各函数的 check 数与行号）对三次都适用，test_wrapper_interpreters_and_literal_arguments 三次都没有运行。被测旧源码 6 个文件三次字节相同。状态为 PASS（限 Windows 已运行的 256 项）。
- **范围**：三次取证的输入状态不同（工作区增加了 01 的新文件与文档、取证工具版本在第一、二次之间不同）。“相同”只说明在这三个记录的输入状态下旧自测输出相同；只限 Windows；耗时变化只是记录。

受保护文件（`scripts/pi_dispatch.py`、`scripts/dispatch-pi.sh`、`tests/test_dispatch.py`、`tests/stub_pi.py`、`tests/stub_pi_help.txt`、`AGENTS.md`、`.agents/`、`.claude/`）：

- **取证时**（measured）：10 次取证中，6 个受保护文件与 .agents/、.claude/ 下 42 个文件都是 source=tracked、status_xy=null（相对 HEAD 与索引没有改动）；6 个文件的 sha256 与实施前基线、最终取证时相同。
- **操作者记录**（source_reported）：取证前后 protected_diff_lines 都是 0（操作者记录第 7、19 行）。
- **报告编写时**（measured，修订 6 核对，不属于取证）：`git diff HEAD --stat` 对这些路径输出 0 行，`git status --porcelain` 为 0 项。
- **结论**：相对 HEAD 的差异为 0 行，状态为 PASS，只覆盖列出的路径。

### 13.7 归档完整性与残留检查

- **归档命令**：`python scripts/codekit/baseline.py archive .agent/baseline/01-closure/<capture-id> --dest docs/code-kit-v2/01-baseline/evidence/closure`。10 次都是 0，控制台都是 files: 83  redacted_changed: 5  raw_copies: 0  rule: redact-v2（source_reported）。
- **完整性**（measured，修订 6 重算）：
  - 10 个归档目录各有 83 个清单条目、84 个文件（含不自列的 archive-manifest.json），共 840 个文件，连同 INDEX.md 共 841 个；
  - 830 个清单条目的 `archived_sha256` 与字节数都与归档文件一致；`original_sha256` 都与 `.agent/baseline/01-closure/` 中的原件一致（只读核对）；
  - 10 份 `source_capture_json_sha256` 与原件 `capture.json` 一致；`run/stdout.bin`、`run/stderr.bin` 的归档 sha256 与 `capture.json` 中 `run.stdout.sha256`、`run.stderr.sha256` 一致；
  - 10 份 archive-manifest.json 自身没有 `archived_sha256` 可比，它们的 sha256 只记在第 13.2 节与 INDEX.md 第 1 节，两处一致；
  - `unredacted_files` 都为 `[]`，规则 redact-v2；每个归档被脱敏改写的都是同样 5 个文件：`capture.json`、pre/post 的 `environment.json`、pre/post 的 `02-rev-parse-toplevel.stdout.bin`。
- **残留复扫**（measured，修订 6）：范围是 `evidence/closure/` 841 个文件、`run-controls-closure/` 与 `run-controls-final/` 各 2 个、`inventory-items/` 7 个，共 852 个；每个文件按 UTF-8 扫描，字节数为偶数时再按 UTF-16-LE、UTF-16-BE 扫描，不区分大小写。类别：当前用户名、用户主目录的 8.3 短名、主机名、规划会话 ID、仓库上级目录与桌面目录的路径组合。识别类模式在扫描时现场生成，不写入任何文件。结果：0 命中。归档子代理的扫描（INDEX.md 第 7 节）结果相同。
- **已知残留**（没有手工修改归档文件）：
  1. 工具安装目录（Program Files 下的 git、bash、node）：每个归档的 capture.json 38 处（36 处 Git、2 处 Git Bash）、pre/post environment.json 各 3 处，共 30 个文件 440 处；redact-v2 在 redaction.not_covered 中声明不覆盖（INDEX.md 7.4 节）。
  2. 20 个 08-diff-unstaged.stdout.bin（内容相同，sha256 83c0de2f0468ae280b560fa50c0c53dffd6af6e5b5d669acc44a6d43878fac80，与最终取证的同名文件相同）中已删除旧文档的正文：第 766 行一个示例用户名的工作目录，第 298、766、1296、1997 行的盘符路径；它们是 HEAD 中已提交文档的内容，不是本机取证定位（INDEX.md 7.3 节）。
- **结论**：PASS。只说明归档与取证原件一致、按 redact-v2 完成脱敏、没有可识别本机用户的残留。

### 13.8 引用的其他文档与归档（修订 6 核对的字节；兼容矩阵与 INDEX.md 两行为修订 7 重新固定的字节）

| 文件 | 字节 | SHA-256 | 说明 |
|---|---|---|---|
| `legacy-inventory.md` | 721294 | `9fdba24ca5de15b4cb75c206caf1e9633bb6866f0f2a8d12372ded225792adc4` | 旧行为清单，清单代理在收尾取证之后更新（第 7.1 节） |
| `compatibility-matrix.md` | 118604 | `07b3aa17a5e8ed1909f83f4cee7a239d3ea9a7875cdc92a62b52b4d0abe2af34` | 兼容矩阵修订 12（第 11 节；修订 6 固定的是修订 11，116258 字节 `f388c96f…`） |
| `decisions.md` | 20186 | `8b460b2d57f1e0e8c1ea2cc2da140c66e186f92425a8d8a586a2eb51ececbb61` | R-01、R-02、R-P12 的原文；与收尾取证输入清单的记录相同 |
| `evidence/closure/INDEX.md` | 48511 | `85ae818f8a5de0b42cf0568b2a5b5205752012e9340519013c12a3706718f0ba` | 收尾取证索引（手写；修订 7 勘误后的字节，修订 6 固定的是 44858 字节 `a6a84822…`） |
| `evidence/run-controls-closure/closure-captures.txt` | 3133 | `fb00af747f1ff3fd7b20a35d5902c918f7057f58bdfb7e9c660d4db57ccc0e86` | 收尾取证操作者记录 |
| `evidence/run-controls-closure/manifest.json` | 1147 | `eed5de9213aa7aa88944b983905cd1b725711f2289e05f270558417309f4ac73` | 上一行的复制清单 |
| `evidence/run-controls-final/final2-captures.txt` | 1495 | `c362495cc389d37204e1250f8ff613585f5722cb8b0e63c60bcf668b9d11d6dd` | 最终取证操作者记录（已归档，与原件相同） |
| `evidence/run-controls-final/manifest.json` | 846 | `bbd6c3a108257aedf1fbe8c95026f75e61866120b625426016d6d88c8ddd2e8a` | 上一行的复制清单 |
| `evidence/inventory-items/manifest.json` | 1326 | `cebbd8bfc9861f97ce21f81478b2574aef5fdd6a8acff3df1f5ca70d9ddba8c9` | 旧行为清单结构化条目（6 个文件）的复制清单 |
| `evidence/final/INDEX.md` | 25868 | `bc04e2c39cbf67301af0b7f387bdcd8c476e51d5d28478eddc67aa74536a496d` | 最终取证索引（历史，修订 5 固定的版本，未变） |

acceptance.md 的摘要仍不在本报告中固定（它记录本报告的摘要，互相固定会形成循环，第 8 节）；修订 6 照录所依据的字节与收尾取证输入清单的记录相同（138322 字节，`f01f659c…`）。acceptance.md 在修订 6 时还没有按收尾取证更新：其中 01-A01、01-A07、01-A16 的判定文字、证据编号（第 2.3 节没有收尾取证）、对本报告与 legacy-inventory.md 的摘要，以及第 7、10 节的未完成项与剩余风险，需要由它的编写者更新。

### 13.9 修订 6 的核对方法

修订 6 编写时只读取归档文件、`.agent/baseline/01-closure/` 原件、操作者记录、`decisions.md`、`acceptance.md`、`legacy-inventory.md` 与工作区，没有重跑任何被测命令，没有修改代码、测试、fixture、Schema 与已有归档。核对内容如下，都是 measured（JSON `closure_regression.verification_revision_6`）：

1. 10 份 archive-manifest.json：每份 files 83 条、目录 84 个文件；830 个条目的 archived_sha256 与字节数与归档文件一致，original_sha256 与 .agent/baseline/01-closure/ 原件一致；10 份 source_capture_json_sha256 与原件 capture.json 一致；10 份 manifest 的 sha256 与 INDEX.md 第 1 节一致。
2. 10 份 capture.json：run.returncode 0、timed_out/interrupted/stray_processes 为 false、spawn_error 为 null、execution_status complete、comparison.baseline_consistent true、drift/observations/unavailable 为空；pre 与 post 的输入清单闭包都是 81b4503e…；10 次 pre 采样的 porcelain 摘要与输入清单摘要相同。
3. 汇总行与行号按 run/*.bin 重新定位；7 个 unittest 套件逐条计数：protocols 338 ok / 4 skipped，baseline_tool 40，legacy_gates 24，legacy_lifecycle 24 / 2 skipped，legacy_cli 74 / 1 skipped，legacy_events 34，codekit01_fixtures -v 75；FAIL:/ERROR: 行与 Traceback 都是 0。
4. test_dispatch：256 行 PASS、0 行 FAIL、24 个分节，run/stdout.bin 与 bl-01t1、bl-01final 逐字节相同；--check 38 行 SAME、0 行 DIFF；--check-stub-regen 10 行 SAME。
5. 与最终取证按“类.方法”比较：protocols 新增 18 个、没有减少、其余结果相同；另 5 个 unittest 套件方法集合与结果相同。
6. 第 7.2 节 62 个方法在收尾取证归档中逐个定位：60 个 ok，P4-L03、L04 skipped。
7. 20 份 environment.json 归档字节相同（097cb8a4…），与最终取证相同；which 的 pi/claude/codex 都是 null；env_names_present 只有 PI_CODING_AGENT_DIR 为 true。
8. 输入清单中 20 个关键源码、测试、fixture 与文档文件的当前字节与取证记录相同；1067 个带摘要的条目中只有 legacy-inventory.md 在取证后改变（修订 6 写入之前）。
9. INDEX.md、run-controls-closure/、run-controls-final/、inventory-items/ 各文件的字节数与 sha256 与各自 manifest 或派发说明一致。
10. 受保护文件：git diff HEAD --stat 输出 0 行，git status --porcelain 0 项。
11. 识别类残留复扫：852 个文件 0 命中。
12. JSON `acceptance[]` 中 13 条 `judged_by_this_report=false` 条目的照录文字按当前 acceptance.md 第 0、3 节重新比对，0 处不一致。
13. `protocols.py` 在兼容矩阵中的全部行号引用按当前字节逐个核对（第 11 节）。

### 13.10 修订 7（对抗性核验勘误）的更正与核对方法

修订 7 只改报告自身的记录，不改 01-A01、01-A07、01-A16 的判定，也不改第 2–6、9、12 节与收尾取证的任何数字。更正如下：

| # | 问题 | 更正 | 位置 |
|---|---|---|---|
| 1 | 第 13 节导语与 JSON `operator_record.evidence_basis` 写操作者记录第 8–17 行与各 capture.json“逐字段一致”；其中 `tool_exit`、`leaked` 在 capture.json 中没有对应字段，无法核对 | 改为列出实际一致的字段（capture-id、argv、executed、returncode、reason、timed_out、duration、baseline_consistent、汇总行），`tool_exit`、`leaked` 记 source_reported | 第 13 节导语；JSON `closure_regression.operator_record` |
| 2 | L-FINAL-OPERATOR：MD 10.3 节写“归档部分关闭”，JSON `status_revision_6` 为 closed；M-07：本报告写“归档部分关闭”，acceptance.md 与 README 写“已关闭” | L-FINAL-OPERATOR 统一为部分关闭（归档要求已关闭；证据等级仍是 source_reported），JSON 改为 partially_closed 并记下原值；M-07 只涉及是否归档，统一为“已关闭（归档要求）”，附“条目中的‘实测’‘探针’仍只是线索，证据等级不变” | 第 10.1、10.3 节；JSON `limitations[L-FINAL-OPERATOR]`、`legacy_inventory.inventory_items_archive.closes` |
| 3 | `evidence/closure/INDEX.md` 与兼容矩阵在同一轮勘误中改动（INDEX：证据等级写法、第 1 节两列来源、7.1 节计数口径、2.2 节补核；矩阵修订 12：E19 与 9.1 节“没有白名单放行”改记静态核对） | 按新字节重新固定，旧摘要移入 history | 第 11、13、13.8 节；JSON `closure_regression.index_ref`、`compatibility`、01-A01/A07/A16 的 evidence_refs |
| 4 | JSON 01-A13 照录的 acceptance.md 文字含“`SEALING_LIMITATIONS` 第 8 条”，与代码不符（常量中是第 1、2 条；protocols-api.md 第 15 节清单第 8 项） | 照录保持原样，加 `transcript_errata_revision_7` | JSON `acceptance[01-A13]` |

核对方法（measured，只读归档文件、`.agent/baseline/01-closure/` 原件、工作区源码与文档，没有重跑任何被测命令；JSON `closure_regression.verification_revision_7`）：

1. `closure-captures.txt` 第 8–17 行与 10 份归档 capture.json 逐行比对：capture-id、argv、executed、returncode、reason、timed_out、duration、baseline_consistent 一致，汇总行文字与 run/*.bin 一致；capture.json 中没有 tool_exit、leaked 的对应字段。
2. `evidence/closure/` 下 10 个归档目录共 840 个文件：字节数为偶数的 602 个，其中 0 字节 470 个，非空且偶数字节 132 个；`.agent/baseline/01-closure/` 原件共 830 个文件，每个取证 83 个。
3. `evidence/inventory-items/` 6 个 `inventory-*.items.json` 的 sha256 与 manifest.json（`cebbd8bf…`）登记一致。
4. `tests/test_codekit01_fixtures.py`（`16b71bca…`）按 AST 读取 docstring：`FileIntegrityTests`、`LegacySourceTests`、`DifferentialTests` 的类 docstring 含 01-A02（13 个方法）；`StubTests`、`CompatMatrixDCaseTests` 的类与方法 docstring 和方法源码都不含 A02（acceptance.md 3.2 据此更正归属依据）。
5. `scripts/codekit/sealing.py`（`af92c1f9…`）的 `SEALING_LIMITATIONS` 共 13 条，崩溃持久性与 Windows 父目录 fsync 是第 1、2 条；protocols-api.md 第 15 节“已知不检测、不保证”清单第 8 项（第 1002 行）为同一内容。
6. 静态核对（source_inspected）：`tests/fixtures/codekit01/` 下 189 个文件的原字节、UTF-16 LE/BE 两种对齐与能解析的 JSON/JSONL 字符串中，不区分大小写查找三个白名单标记，0 处（兼容矩阵修订 12 的依据）。
7. INDEX.md 与兼容矩阵勘误后的字节数与 sha256（第 13.8 节）。
