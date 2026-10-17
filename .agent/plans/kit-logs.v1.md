# TASK: kit-logs

<!-- 保存为 .agent/plans/kit-logs.v1.md。章节标题（英文）由校验器检查，不要改名。
     JSON 由 derive-json 从本文件生成。 -->

## Identity
- plan_version: 1
- repository: ThemisTally
- base_sha: ce04541889a5b6cfbc34ce603a65b42afd08c241
- risk_level: medium（路径边界与链接判断，安全相关；需要独立复审）
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge（用户决定）
- executor: bb/step-5-preview · thinking high

## Goal
新增只读的 `scripts/kit_logs.py`，提供 `logs list`、`logs show`、`logs search`、`logs usage` 四个子命令：列出与查看运行证据（`.agent/runs`）、在证据里搜索、汇总执行端用量（Pi 的 `events-summary.json`），并汇总规划端用量（只读命令行显式给出的宿主会话记录路径）。输入是仓库的 `.agent/runs` 与命令行参数；输出是文本或 `--json` 对象；运行前后 `.agent/` 逐字节相同。

## Non-goals
- 不写、不改、不删 `.agent/` 下的任何文件或目录；不导出、不归档、不实时跟随、不计算费用。
- 不自动查找或读取任何会话文件（不访问 `~/.claude` 等用户目录）；不读取、不输出会话记录的 `content` 或其它字段。
- `search` 没有 `--json`；不接入调度器（`pi_dispatch.py` 的转发与 `KIT_LOADED_FILES` 由规划端在集成后另做）。
- 不修复调度器 `resolve_run_dir` 与 `task_attempts` 的边界缺口（另立任务）；本模块不复用它们。
- `.agent/runs` 根目录本身是否为链接，本合同不规定（它是调用方指定的根，不做链接检查）。

## Repository facts
- 入口与约定（均在 `scripts/pi_dispatch.py`，行号约略）：
  - `TASK_ID_RE = ^[a-z0-9][a-z0-9-]{0,63}$`（约 60 行）；`ATTEMPT_DIR_RE = ^attempt-(?P<n>\d{3,})$`（约 66 行，编号组名为 `n`）；`PLAN_KEY_RE = ^(?P<task>…)\.v(?P<ver>[1-9][0-9]{0,3})$`（约 59 行，组名为 `task`、`ver`）。
  - `DispatchError(Exception)` 带 `.code`（约 480 行）；`is_within(path, root)`（约 558 行，按绝对路径字符串比较，大小写在 Windows 上不敏感，`root` 本身返回真）。
  - `Repo(root)`：`runs_dir = root / ".agent" / "runs"`（约 1123 行）；`Repo.discover(start)` 要求在 Git 仓库的主工作区内运行，否则抛 `DispatchError`（退出码 2）。
  - `is_link_or_junction(path)`（约 5203 行）：符号链接、Windows junction 与其它重解析点都返回真。
  - `first_link_component(root, rel)`（约 5227 行）：从 `root` 往下逐级检查相对路径 `rel`，返回第一个是链接的那一级（相对 `root` 的 POSIX 路径），没有则 None；`rel` 含 `..` 或绝对路径时抛 `ValueError`。
  - `pi_dispatch` 的 `resolve_run_dir`（约 3207 行）与 `task_attempts`（约 3133 行）有边界缺口，本模块不得调用。
- 调用方式与模块结构：照 `scripts/kit_config.py` 写。`import pi_dispatch as pd`（kit_config.py 约 44 行的做法，`sys.path` 中先插入脚本目录）。`main(argv=None, repo=None) -> int`；`args.repo` 缺省时用 `repo` 参数（kit_config.py 约 737 行）；`_repo` 把 `DispatchError` 转成退出码（kit_config.py 约 225 行）。
- 证据文件（调度器写入，格式以本合同为准）：
  - `meta.json`：含 `task_id`、`plan_version`（整数）、`attempt_no`、`attempt_id`。
  - `state.json`：`{"state": "…", "at": "YYYY-MM-DDTHH:MM:SSZ", …}`（`set_state` 约 3114 行）；缺失时 `get_state` 返回 `UNKNOWN`。
  - `summary.md`：attempt 的摘要，可能较大。
  - `events-summary.json`：`usage` 对象含 `input`、`output`、`cacheRead`、`cacheWrite`、`totalTokens` 五个整数（`USAGE_KEYS` 约 2603 行）；`requested_model` 为对象 `{"provider", "model", "thinking"}`（约 2943 行）；`complete`、`truncated`、`parse_error_lines`（列表，约 2936–2940 行）。还有 `cost` 等字段，本模块不读。
- 宿主会话记录（Claude Code，非公开接口，以本合同为准）：每行一个 JSON 对象；顶层 `timestamp`（ISO 8601，通常以 `Z` 结尾）与 `isSidechain`；`message.id`（字符串）、`message.model`、`message.stop_reason`、`message.usage` 对象含 `input_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`、`output_tokens`。
  - 主会话记录：同一次回复写成多行，它们的 `message.id`、usage 与 `stop_reason` 都相同。
  - 子代理的会话记录（`<会话目录>/subagents/agent-<id>.jsonl`，`isSidechain` 全为真）不同：同一次回复先写若干条中间记录（`stop_reason` 为 null，`output_tokens` 未到终值，输入与缓存两项已是终值），最后一条是最终记录（`stop_reason` 为 `tool_use`、`end_turn` 等，带终值）。B7.2 按此处理。
- Python 与时间：本机 `python` 为 3.10.19。3.10 的 `datetime.fromisoformat` 不接受结尾的 `Z`，小数秒只认 3 位或 6 位。解析时间一律按 Behavior contract B7 的写法（先把结尾的 `Z` 换成 `+00:00`，再要求结果带时区）。
- 环境：本机 `python` 指向的解释器的 site-packages 里有一个第三方的 `tests` 包，会遮住仓库的 `tests/`。所以检查只运行具体的测试文件（它们经 `sys.path` 导入模块），不运行全量测试，也不写 `from tests.… import`。
- 测试风格：`tests/test_kit_config.py` 开头：`sys.path` 插入 `scripts/`，在临时目录里 `git init` 建仓库，清理时删除临时目录。
- 链接用例的平台：Windows 上用 `cmd /c mklink /J` 建 junction（不需要管理员权限）；其它平台用指向目录的符号链接。本机不能建文件符号链接（WinError 1314），所以本模块的链接只测目录链接。
- 背景文档：`docs/themis-tally-3.0-r1-日志与插件管理.md` 的 §3 D2–D4、§4.1、§9 L 组（在基线中）。它只作背景；执行所需的规则已完整写在本合同的 Behavior contract 中，以本合同为准。
- 基线检查：基线（HEAD）上 V01–V04 都失败，原因是 `scripts/kit_logs.py`、`tests/test_kit_logs_oracle.py` 与 `tests/test_kit_logs.py` 尚不存在（V01 在 oracle 进入基线后表现为 `ModuleNotFoundError: No module named 'kit_logs'`）。这是缺模块与缺用例，不是既有缺陷。

## Scope
- allowed_modified_files: 无
- allowed_new_files:
  - scripts/kit_logs.py
  - tests/test_kit_logs.py
- allowed_deleted_files: 无
- forbidden_paths:
  - tests/test_kit_logs_oracle.py
  - scripts/pi_dispatch.py
  - scripts/kit_config.py
  - scripts/kit_install.py
  - scripts/codekit/**
  - README.md
  - CHANGELOG.md
  - .claude/settings.example.json
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract

以下规则是完整的行为规格。规则编号 B0–B9 用于 DoD 与复审引用。

### B0 总则
1. 模块是 `scripts/kit_logs.py`，只用标准库，Python 3.10 可运行（不使用 3.11 才有的 API 或语法）。入口 `main(argv=None, repo=None) -> int`；文件末尾 `if __name__ == "__main__": sys.exit(main())`。
2. 参数：顶层 `--repo PATH`（缺省为当前目录）。子命令：`list`、`show`、`search`、`usage`。`main` 的 `repo` 参数只在 argv 里没有 `--repo` 时使用（与 `kit_config.main` 相同）。argparse 的参数错误退出码为 2。
3. 仓库：`pd.Repo.discover(repo)`。`pd.DispatchError` 转为一行 `ERROR: <消息>`（stderr）并以其 `.code` 退出（不在 Git 仓库里时为 2）。runs 根为 `repo.runs_dir`；它不存在时视为没有任何条目，不是错误。runs 根本身不做链接检查；它之下的每一级都检查。
4. 只读：不得在 `.agent/` 下创建、修改或删除任何文件或目录。
5. 错误：命令级错误只向 stderr 写一行 `ERROR: <消息>`，不输出堆栈。访问某个条目时遇到 `OSError`、`ValueError`（包括含 NUL 的路径、含孤立代理字符的字符串，以及 `UnicodeEncodeError`）：该条目按不可用处理，不得让异常冒出。目标解析（B5）中的此类错误按“找不到”处理，退出码 2。
6. 输出：stdout 与 stderr 以 UTF-8 写出（与 `kit_config.main` 相同：`reconfigure(encoding="utf-8", errors="replace")`，失败时忽略）。
7. 链接与边界只调用 `pi_dispatch`，并且通过 `import pi_dispatch as pd` 之后的属性调用：`pd.is_link_or_junction(path)`、`pd.first_link_component(root, rel)`、`pd.is_within(path, root)`。不得使用 `from pi_dispatch import …`（测试会替换 `pi_dispatch` 模块上的属性来确认调用发生）。不得调用 `pd.resolve_run_dir` 与 `pd.task_attempts`。源码（包括注释）中不得出现 `islink(`、`is_symlink(`、`isjunction(`、`st_reparse_point`、`FILE_ATTRIBUTE_REPARSE_POINT`。
8. 枚举不得使用 `os.walk`（Windows 上它会进入 junction）。对每个目录项：先用 `pd.is_link_or_junction` 判断；是链接就计入 `skipped_links` 并且不进入；不是链接时才用 `os.lstat` 判断目录或普通文件（`stat.S_ISDIR` / `stat.S_ISREG`）。不要用 `DirEntry.is_dir()` 或 `Path.is_dir()` 作为第一判断，它们会跟随链接。

### B1 枚举（list、search、usage 共用）
1. 任务：runs 根下名字匹配 `pd.TASK_ID_RE` 的目录项。
2. attempt：任务目录下名字匹配 `pd.ATTEMPT_DIR_RE` 的目录项，编号 `n` 为其 `n` 组转成整数。
3. 链接：任务目录或 attempt 目录是链接时，计入 `skipped_links` 一次，且不进入。同名的非目录项忽略、不计数。名字不匹配的项（例如 `_tmp`、`attempt-1`、`notes`）忽略、不计数。
4. 排序：任务按名字的字符串升序；attempt 按编号的整数升序（`attempt-002` 在 `attempt-010` 之前；`attempt-999` 在 `attempt-1000` 之前）。
5. 证据：attempt 目录下递归枚举，逐级检查。每个条目先过链接判断（是链接则计入 `skipped_links`、不进入、不计入证据）；是目录则递归；是普通文件则计入证据；其它类型忽略。证据的相对路径用 POSIX 分隔符，相对于 attempt 目录（例如 `sub/x.txt`）。
6. `skipped_links` 的口径：本命令访问过程中遇到的链接条目数，每个条目计一次。`list` 与 `show` 包括 attempt 内的所有条目；`search` 包括 attempt 内的所有条目；`usage` 只计任务目录、attempt 目录与 `events-summary.json`。

### B2 状态（list、show）
- 读取 attempt 根下的 `state.json`：必须是普通文件（非链接）。内容为 UTF-8 JSON 对象，且 `state` 为字符串时，`state` 取该字符串；否则（缺失、不可读、不是对象、`state` 不是字符串、是链接）`state` 为 `UNKNOWN`。
- `state_at`：同一对象的 `at` 为字符串时取之，否则为 null。

### B3 list
- 命令：`list [--task ID] [--state S] [--json]`。`--task` 的值必须匹配 `pd.TASK_ID_RE`，否则退出码 2。`--state S` 按字符串完全相等过滤（区分大小写）。
- 每个 attempt 给出：`task`（任务名）、`attempt`（目录名，如 `attempt-002`）、`state`、`state_at`、`evidence_files`（B1.5 的普通文件数）、`evidence_bytes`（这些文件的大小之和）、`has_summary`（attempt 根下的 `summary.md` 是普通文件）。
- 文本输出：每个 attempt 一行，包括 `task/attempt`、状态、状态时间、证据文件数与字节数、有没有摘要。没有 attempt 时输出 `没有 attempt`。`skipped_links` 大于 0 时，在末尾另起一行 `跳过的链接：K`。
- 退出码 0（包括没有 attempt）。

### B4 show
- 命令：`show TARGET [--json]`。TARGET 的解析见 B5；找不到、越界或含链接，退出码 2。
- 输出字段：`task`、`attempt`、`state`、`state_at`、`summary`、`evidence`、`skipped_links`（JSON 键名见 B10）。
- `summary`：attempt 根下的 `summary.md` 是普通文件时，`bytes` 为文件大小（`os.lstat` 的 `st_size`）；`text` 为前 `min(bytes, 65536)` 个字节按 UTF-8 解码（`errors="replace"`）的结果；`truncated` 为 `bytes > 65536`。JSON 的 `text` 不含截断注明。`summary.md` 缺失、是链接或不是普通文件时，`summary` 为 null。
- 文本输出：打印摘要文本；被截断时，在其后另起一行注明“已截断”并给出总字节数。
- `evidence`：B1.5 的证据清单，每项 `{"path": 相对路径, "bytes": 字节数}`，按 `path` 字符串升序。
- `skipped_links`：目标 attempt 内遍历时遇到的链接数（B1.6）。解析目标时读取其它 attempt 的 `meta.json` 不计入。
- 除 `summary.md` 之外，不输出任何证据文件的内容。

### B5 目标解析（show）
对命令行的 TARGET 字符串 T，按顺序判断，第一个匹配的形式生效：
1. **形式 A，`task.vN`**：T 匹配 `pd.PLAN_KEY_RE`。在该 task 的 attempt 中（B1，不含链接），取 `meta.json` 为普通文件、内容为 JSON 对象、且 `plan_version` 是整数（不含布尔值）并且等于 N 的那些 attempt，取编号最大者。读取或解析失败的 attempt 视为不匹配。没有则退出码 2。
2. **形式 B，`task`**：T 匹配 `pd.TASK_ID_RE`。取该 task 的 attempt（B1，不含链接）中编号最大者。task 目录本身是链接、或没有 attempt，退出码 2。
3. **形式 C，`task/attempt-NNN`**：T 恰好含一个 `/`，前段匹配 `pd.TASK_ID_RE`，后段匹配 `pd.ATTEMPT_DIR_RE`。目标是 `runs/task/attempt-NNN`：`pd.first_link_component(runs, "task/attempt-NNN")` 不为 None 时退出码 2；目标必须是目录，否则退出码 2。
4. **形式 D，显式路径**（其余所有 T，包括绝对路径、含分隔符或 `..` 的写法）。**不做任何规范化**：不用 `normpath`、`abspath` 或 `resolve` 消去 `..`，而是按原样逐段处理：
   a. `raw` = T（若是绝对路径）或 `os.path.join(os.getcwd(), T)`。
   b. 把 `raw` 与 runs 根目录（`repo.runs_dir`）分别按路径分隔符切成段（POSIX 只认 `/`；Windows 认 `\` 与 `/`，盘符是第一段）。空段与 `.` 段不影响路径含义，忽略；`..` 段保留。
   c. `raw` 的开头必须与 runs 根的段逐段相同（Windows 上段名不区分大小写，POSIX 区分）；否则退出码 2。
   d. 从 runs 根之后的第一段开始，按顺序处理每一段，维护栈 S（初始为空）：
      - 段是 `..`：若 S 为空，退出码 2（出栈越过 runs 根）；否则弹出 S 的末段。
      - 其它段（普通名字）：压入 S，然后用 `pd.is_link_or_junction(runs / S 的各段)` 检查，为真则退出码 2。这一检查在压入时进行，所以名字随后被 `..` 抵消掉的那一级也会被检查。
   e. 处理完毕后，S 必须恰好两段：第一段匹配 `pd.TASK_ID_RE`，第二段匹配 `pd.ATTEMPT_DIR_RE`（按写法原样，区分大小写）；否则退出码 2。
   f. `runs / S` 必须是非链接的目录；否则退出码 2。
   g. 规则举例（oracle 据此断言）：`runs/task-a/attempt-001/../attempt-001` 成功；`runs/task-a/../task-b/attempt-001`（`task-a` 是普通目录）成功；`runs/<链接>/../task-b/attempt-001` 退出码 2（压入链接时即检查，即使它随后被 `..` 抵消）；`runs/../runs/task-b/attempt-001` 退出码 2（出栈越过 runs 根）。
   h. 大小写：在 Windows 上，`raw` 中 runs 根的段大小写可以与磁盘不同；S 的两段必须与正则完全匹配。
5. 所有形式解析出的目标目录，还要满足 `pd.is_within(Path(target).resolve(), runs.resolve())` 作为兜底（前面的规则已保证不经过链接）；否则退出码 2。
6. 空字符串、含 NUL 或孤立代理字符的 T，按形式 D 处理；任何 `OSError` 或 `ValueError` 都按“找不到”，退出码 2。
7. 相对路径相对于当前工作目录。

### B6 search
- 命令：`search PATTERN [--task ID] [--max N]`。PATTERN 按 Python `re` 语法编译，编译失败退出码 2。`--max` 缺省为 50，必须是不小于 1 的整数，否则退出码 2。`--task` 同 B3。
- 范围：B1 枚举到的 attempt（或 `--task` 指定的任务）下，证据中相对路径的**后缀**（区分大小写）为 `.md`、`.txt`、`.log`、`.json`、`.jsonl` 之一的普通文件（链接不进入，计入 `skipped_links`）。
- 顺序：任务名升序；attempt 编号升序；证据相对路径的字符串升序；行号升序。
- 逐行读取：UTF-8 解码（`errors="replace"`），去掉行尾的 `\n` 与 `\r`，用 `re.search` 匹配。
- 每条匹配输出一行：`<任务>/<attempt>/<证据相对路径>:<行号>: <内容>`。`<任务>/<attempt>/<证据相对路径>` 相对于 runs 根，用 POSIX 分隔符。`<内容>` 为匹配行的前 200 个字符（不加省略号）。
- 截断：已输出 N 条匹配后，若还有更多匹配，停止搜索，并在输出末尾另起一行注明，且该行含数字 N。恰好 N 条、没有更多时不注明。
- `skipped_links` 大于 0 时，在末尾另起一行 `跳过的链接：K`。
- 没有匹配：退出码 0，不输出匹配行。
- 不提供 `--json`。

### B7 usage
1. 参数：`usage [--task ID] [--transcript PATH]… [--since TIME] [--until TIME] [--json]`。
   - `--task` 同 B3；`--task` 只过滤执行端。
   - `--transcript` 可以重复给出，每次一个路径。每个路径必须存在（`os.path.exists`），否则退出码 2，且在读取任何文件之前检查。
   - `--since` 与 `--until` 的解析：字符串结尾的 `Z` 换成 `+00:00` 之后用 `datetime.fromisoformat` 解析；结果必须带时区（`utcoffset()` 不为 None），否则退出码 2。同时给出两者、且 `--since` 晚于 `--until` 时，退出码 2。
2. 输出两段：执行端（B7.1）与规划端（B7.2）。没有给出 `--transcript` 时，`planner` 为 null，文本输出注明“未给 --transcript，未统计规划端”。
3. 退出码：找不到路径、时间格式错误、任务 ID 格式错误、`--since` 晚于 `--until` 时为 2；其它情况为 0。

**B7.1 执行端**（对 B1 枚举到的 attempt，`--task` 过滤；不做证据遍历）：
- 读取 attempt 根下的 `events-summary.json`。它是链接时计入 `skipped_links`，并按缺失处理。
- 状态判定，先判 unknown，再判 partial，最后是 known：
  - **unknown**：文件缺失、不是普通文件、不是合法的 UTF-8 JSON 对象；或 `usage` 缺失、不是对象；或 `usage` 的五个键 `input`、`output`、`cacheRead`、`cacheWrite`、`totalTokens` 中任何一个缺失或不是整数（不含布尔值）。
  - **partial**（不是 unknown，并且满足下列任一）：`complete` 不是 JSON 的 `true`；`truncated` 是 JSON 的 `true`；`parse_error_lines` 不是空列表（包括缺失）。
  - **known**：其它情况。
- 数值：unknown 的 attempt 的 `usage` 为 null，不计入任何合计，也不计为 0。known 与 partial 的 attempt 的五个数值计入合计（partial 是下界）。
- `requested_model`：`events-summary.json` 的 `requested_model` 是对象、且 `provider` 与 `model` 都是字符串时，为 `"<provider>/<model>"`；否则为 null。`events-summary.json` 不可解析时为 null。
- `counts`：known、partial、unknown 的个数。
- `by_model`：按 `requested_model` 分组（null 排最前，其余按字符串升序）。每组给出 known、partial、unknown 的个数，以及 known 与 partial 的 usage 合计。

**B7.2 规划端**（只读 `--transcript` 给出的路径）：
1. 文件：对每个 `--transcript` 路径 P（按给出的顺序）：
   - P 是目录（`os.path.isdir(P)`）：读取它直接一层、名字以 `.jsonl` 结尾的条目，按名字排序。链接（`pd.is_link_or_junction`）计入 `planner.skipped_links` 并且不读；不是普通文件（`os.lstat`）的忽略；普通文件则读取。
   - P 不是目录：读取 P 本身。即使 P 是链接也读取（它是用户明确给出的路径）。
   - 不得读取 P 之外的任何文件，也不得搜索其它目录。
2. 逐文件读取：以二进制方式打开，按 `\n` 切分行，去掉行尾的 `\r\n` 或 `\n`。读取该文件时发生 `OSError`（包括权限不足）或 `ValueError`：该文件的全部行都不计入（包括跳过的计数与记录），`unreadable_files` 加 1，然后继续下一个文件。
3. 逐行分类：**空行与只含空白字符的行直接忽略，不计入任何计数**（与 `pi_dispatch.py` 解析 Pi 事件流时跳过空行的做法一致）。其余行：
   - UTF-8 严格解码失败，或 `json.loads` 失败：`skipped_lines.bad_json` 加 1。
   - 解析结果不是对象（`dict`）：`skipped_lines.not_object` 加 1。
   - 是对象，但不是候选记录：`skipped_lines.not_candidate` 加 1。
   - 候选记录：顶层是对象；`message` 是对象；`message.id` 是非空字符串；`message.usage` 是对象。
4. 记录的种类与规范值：
   - **最终记录**：`message.stop_reason` 是非空字符串（`tool_use`、`end_turn`、`max_tokens` 等一律算，不限定取值）。其余候选记录是**中间记录**：`stop_reason` 为 null、缺失或空字符串。子代理的会话记录里，同一回复先写若干条中间记录（`output_tokens` 可能还未到终值），最后一条才是最终记录（2.2）。
   - 四个计数字段（`input_tokens`、`cache_creation_input_tokens`、`cache_read_input_tokens`、`output_tokens`）：取 `message.usage` 中的原始 JSON 值；键缺失时记为特殊标记 MISSING。
   - `model`：`message.model` 是字符串则取之，否则为 null。
   - `sidechain`：顶层 `isSidechain` 是 JSON 的 `true` 时为 true，否则为 false。
   - 比较两个值是否相同：计数字段按 `json.dumps(值, sort_keys=True)` 的文本比较（因此 `1` 与 `1.0` 不同，`null` 与 MISSING 不同）；`model` 与 `sidechain` 按规范值比较。
5. 时间可用性：顶层 `timestamp` 是字符串，结尾的 `Z` 换成 `+00:00` 之后 `datetime.fromisoformat` 能解析，并且结果带时区（`utcoffset()` 不为 None）；换算到 UTC 后即为可用时间。否则为不可用时间。每条候选记录的不可用时间各计一次到 `unusable_timestamps`，不论它属于哪一组、是否冲突。
6. 分组与判定（所有文件读完之后，按 `message.id` 分组，结果与文件顺序和行顺序无关）。对每个组依次判定：
   - **冲突**，满足下列任一即是：
     a. 组内任意两条记录（中间记录与最终记录都算）的 `model` 或 `sidechain` 不同。这保证中间记录的 `model` 与 `isSidechain` 必须与最终记录相同；没有最终记录的组，组内各条也必须彼此一致；
     b. 最终记录之间，四个计数字段任一不同（中间记录的计数不参与比较）。
     冲突组：`conflict_ids` 加 1，`conflict_records` 加上组内全部记录数（含中间记录）；该 id 不计入后续任何类别；`partial` 为真。
   - **未完成**（非冲突，且没有最终记录）：`incomplete_ids` 加 1，不计入；`partial` 为真。
   - 其余组（非冲突且有最终记录）：`duplicate_records` 加上（组内最终记录数减 1）；继续第 7 条。
7. 分类（每个 id 恰好落入五类之一；判定顺序：冲突 → 未完成 → 无可用时间 → 窗口外 → 计入）：
   - **无可用时间**：组内（含中间记录）没有可用时间的 id。`ids_without_time` 加 1，跳过。
   - 否则代表时间 = 组内**所有记录**（含中间记录）的可用时间的最小值（UTC）。
   - **窗口外**：`--since` 含（代表时间 ≥ since），`--until` 不含（代表时间 < until）；不在窗口内的 id。`outside_window_ids` 加 1，跳过。
   - **计入**：`included_messages` 加 1。取该组任一最终记录（同组的最终记录相同）的 `(model 或 null, sidechain)` 分组，累加其四个计数字段：只累加整数（不含布尔值）的值；每个非整数的字段，`non_integer_fields` 加 1。中间记录的计数不累加。
8. 其它计数（全部，与读取顺序无关）：`intermediate_records` 为所有组（含冲突组与未完成组）中中间记录的条数。`partial` 为真，当且仅当 `conflict_ids > 0`，或 `incomplete_ids > 0`，或 `unreadable_files > 0`。`lower_bound` 恒为 true。
9. `by_model` 排序：`model` 为 null 的排最前，其余按字符串升序；同一模型下 `sidechain` 为 false 的排前。每行给出 `messages`（该组计入的 id 数）与四个计数字段的合计。
10. 输出只含上述计数与合计。只读 `message.id`、`message.usage` 的四个计数字段、`message.model`、`message.stop_reason`、顶层 `isSidechain` 与 `timestamp`；不读、不输出会话记录的 `content` 或其它字段。
11. 覆盖范围：只统计会话记录里有的调用。输出（文本与 JSON）注明这是下界。

### B8 输出与一致性
- `--json`：`json.dumps(对象, ensure_ascii=False, indent=2)` 写到 stdout，末尾换行。键集、类型与 B10 完全一致，不增加其它键。
- 列表顺序按 B1、B7 的规则写死，同一输入的输出必须逐字节相同。
- 不带 `--json` 时是自由格式的文本，但必须包含 B3、B4、B6、B7 要求的信息（如 `没有 attempt`、`跳过的链接：K`、已截断注明、下界注明）。

### B9 退出码
- 0：正常完成，包括没有 attempt、没有匹配、没有给出 `--transcript`。
- 1：运行错误，例如 runs 根存在但无法列出（`os.scandir` 抛 `OSError`）；打印 `ERROR:` 一行。
- 2：用法或目标错误：argparse 错误；`DispatchError`（例如不在 Git 仓库里，使用其 `.code`）；目标找不到、越界或含链接；`--task`、`--since`、`--until`、`--max`、PATTERN 的格式错误；`--transcript` 路径不存在。

### B10 输出结构（JSON，键名固定）

`list --json`：
```json
{"attempts": [{"task": "…", "attempt": "attempt-002", "state": "…", "state_at": "…或 null",
               "evidence_files": 0, "evidence_bytes": 0, "has_summary": true}],
 "skipped_links": 0}
```

`show --json`：
```json
{"task": "…", "attempt": "attempt-002", "state": "…", "state_at": "…或 null",
 "summary": null或{"bytes": 0, "truncated": false, "text": "…"},
 "evidence": [{"path": "sub/x.txt", "bytes": 0}],
 "skipped_links": 0}
```

`usage --json`：
```json
{"executor": {
   "attempts": [{"task": "…", "attempt": "attempt-001", "requested_model": "bb/step-5-preview或null",
                 "status": "known或partial或unknown",
                 "usage": null或{"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 0}}],
   "totals": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 0},
   "counts": {"known": 0, "partial": 0, "unknown": 0},
   "by_model": [{"requested_model": "…或null", "known": 0, "partial": 0, "unknown": 0,
                 "usage": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 0}}],
   "skipped_links": 0},
 "planner": null或{
   "lower_bound": true,
   "partial": false,
   "included_messages": 0,
   "by_model": [{"model": "…或null", "sidechain": false, "messages": 0,
                 "input_tokens": 0, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0, "output_tokens": 0}],
   "skipped_lines": {"bad_json": 0, "not_object": 0, "not_candidate": 0},
   "skipped_links": 0,
   "unreadable_files": 0,
   "duplicate_records": 0,
   "conflict_ids": 0,
   "conflict_records": 0,
   "incomplete_ids": 0,
   "intermediate_records": 0,
   "unusable_timestamps": 0,
   "ids_without_time": 0,
   "outside_window_ids": 0,
   "non_integer_fields": 0}}
```
- `executor.attempts` 与 `list` 的顺序相同（任务名升序、attempt 编号升序）。
- `executor.by_model` 按 B7.1 排序。`planner` 为 null 时，只有这一个键的值是 null。
- `search` 没有 JSON 输出。

## Steps
1. 读取 Repository facts 中列出的符号，确认 `scripts/pi_dispatch.py` 中的 `TASK_ID_RE`、`ATTEMPT_DIR_RE`、`PLAN_KEY_RE`、`DispatchError`、`Repo`、`is_within`、`is_link_or_junction`、`first_link_component` 存在且与本合同一致。不一致就停止并报告。
2. 新建 `scripts/kit_logs.py`，按 Behavior contract B0–B9 实现，结构照 `scripts/kit_config.py`。
3. 新建 `tests/test_kit_logs.py`，只补 oracle 没有覆盖的内部细节，例如：时间解析的 `Z`、`+08:00` 与小数位；`--max`、`--state` 的参数错误；`--since` 晚于 `--until`；`requested_model` 不是对象时的分组。不要照抄 oracle 的辅助函数或用例。临时目录用 pytest 的 `tmp_path`，不用 `tempfile`（AGENTS.md 的临时目录规定）。
4. 先运行与改动相关的检查：先跑单个用例或失败的用例，不要每改一处就跑整个文件。V01 的 oracle 是完整的验收依据；只读它的失败输出，不要修改它。
5. 写执行报告，列出所有合同未规定的取舍（`interpretations`）与合同冲突（`contract_conflicts`）。遇到合同未定义的行为，记入 interpretations 时必须写出合同原文与采用的做法，不得静默决定。

## Validation commands

必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。需要截短输出时，照抄执行说明“机器合同摘要”里每条检查的“自检照抄”写法（bash 的写法以 `set -o pipefail;` 开头，管道的退出码就是被测程序自己的）；自己临时写的测试命令要接 `| tail` 之类的管道时，开头同样加 `set -o pipefail;`。不要把输出写到 `/tmp/v01.txt` 这类固定路径。不要自己做变异检查（故意改坏实现，包括把仓库复制到临时目录去改）：验收端会在固定候选上做。

- V01（必要，基线应失败）：`python -m pytest tests/test_kit_logs_oracle.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配 `[1-9]\d* passed`，不得出现 `\bskipped\b`
- V02（必要）：`python -m pytest tests/test_kit_logs.py -q` · cwd：仓库根 · 超时：600s · 期望退出码：0 · 输出须匹配 `[1-9]\d* passed`，不得出现 `\bskipped\b`
- V03（必要，基线应失败）：`python -m py_compile scripts/kit_logs.py` · cwd：仓库根 · 超时：120s · 期望退出码：0
- V04（必要，基线应失败）：`python scripts/kit_logs.py --help` · cwd：仓库根 · 超时：120s · 期望退出码：0 · 输出须匹配 `usage:`

## Definition of done
- D01：四个子命令与顶层 `--repo` 的参数形式按 B0、B3、B4、B6、B7 工作；参数错误与目标错误的退出码为 2，只打印一行 `ERROR:`，不输出堆栈；证据：V01；目的：调用方靠退出码与 ERROR 行区分用法错误与证据缺失，不会看到堆栈（V01 中的参数、错误与退出码用例）。
- D02：只读：四个子命令运行前后 `.agent/` 逐字节相同，也不新建任何文件或目录；证据：V01；目的：证据只读（AGENTS.md），运维查看证据不会改动它（V01 中的只读用例）。
- D03：枚举与链接按 B1、B2、B3 工作：名字不符、非目录、链接的条目不进入也不计入证据；每一级链接都跳过并计数，不跟随（junction 形式的中间目录不进入）；证据：V01；目的：不能读到 runs 之外的内容，链接也不能被当成证据（V01 中的枚举与链接用例）。
- D04：目标解析按 B5 工作：四种写法、`task` 取编号最大的非链接 attempt、`task.vN` 按 `meta.json` 的 `plan_version` 选择、显式路径按段栈逐段处理（每压入一级都查链接，名字被 `..` 抵消的那一级也查；出栈越过 runs 根即拒绝）、大小写与合法的 `..` 写法；证据：V01；目的：`..` 不能越过链接（含被抵消的链接级）读到外部文件，而合法写法不能被误拒（V01 中的目标解析与 `..` 用例）。
- D05：JSON 键集与类型与 B10 完全一致；`show` 的摘要按 65536 字节截断并注明；证据：V01；目的：键名固定，测试与调用方按键名读取，大文件不会整份输出（V01 中的键集与截断用例）。
- D06：`search` 按 B6 工作：后缀过滤、顺序、200 字符截断、`--max` 缺省 50、截断注明；证据：V01；目的：长行与大量匹配不会让输出失控（V01 中的 search 与输出上限用例）。
- D07：执行端用量按 B7.1 工作：known、partial、unknown 的判定与合计（unknown 不计为 0，partial 计入下界）、按 `requested_model` 分组、输出不含 `cost`；证据：V01；目的：缺失的数不能当作 0，费用不由本命令计算（V01 中的执行端用量用例）。
- D08：规划端用量按 B7.2 工作：最终记录（`stop_reason` 非空）与中间记录的区分、冲突、未完成、去重（只数最终记录）、代表时间（组内所有记录的最小值）、窗口（`--since` 含、`--until` 不含）、五类计数口径、部分标记、空行忽略、与文件和行顺序无关、主线与子代理分开；证据：V01；目的：子代理的流式中间记录不能被当成独立消息，结果与读取顺序无关，计数口径不漂移（V01 中的规划端用量用例）。
- D09：规划端不输出会话记录的 `content` 与其它字段，也不自动查找会话文件；证据：V01；目的：会话记录可能含密钥与隐私，只读用户明确给出的路径（V01 中的内容保密与目录参数用例）。
- D10：链接判断只调用 `pi_dispatch` 的 `is_link_or_junction`、`first_link_component`、`is_within`，不复用 `resolve_run_dir` 与 `task_attempts`，源码中不出现 B0.7 列出的直接判断写法；证据：V01；目的：D11 要求单一实现，不许另写同类判断（V01 中的替身与源码扫描用例）。
- D11：范围：除 `scripts/kit_logs.py` 与 `tests/test_kit_logs.py` 外没有任何改动；证据：scope；目的：不改调度器、配置与其它模块，接入由规划端在集成后做。
- D12：执行端自测 `tests/test_kit_logs.py` 通过，且只覆盖合同未被 oracle 覆盖的细节；`py_compile`、`--help` 通过；证据：V02、V03、V04；目的：模块可导入、可运行，自测不是空壳。
- D13：执行报告列出所有 `interpretations` 与 `contract_conflicts`（格式见执行说明），每条写出合同原文与采用的做法；证据：review；目的：验收端能核对每个未经合同规定的取舍。
- D14：没有删除、跳过或弱化既有测试；证据：review。

## Stop conditions
- Repository facts 中的符号或数值与基线不符（例如 `TASK_ID_RE` 的正则、`is_link_or_junction` 不存在）。
- 必须修改允许范围之外的文件才能继续。
- 需要新增或升级依赖、远程写入、访问凭据、提升权限，或读取 `~` 下的任何会话文件。
- oracle（V01）与本合同矛盾：此时停止并报告，不得修改 oracle。
- 验收要求互相冲突，或出现合同没有定义、又无法按 B 条合理取舍的业务行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id 汇总，包括返工版本）
- max_wall_seconds_per_attempt: 1800
- max_wall_seconds_total: 3600
- cost_budget: tracking-only（bb/step-5-preview 只报 token，费用记 unknown）
- 强制方：调度器强制次数与墙钟；费用只统计（Pi 没有费用或轮次上限参数）
- 时间分配：调查 120 秒；实现 `scripts/kit_logs.py` 600 秒；执行端自测 240 秒；必要检查 180 秒；执行报告 90 秒；合计 1230 秒，留出约 570 秒余量。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D14，列出自检命令与结果、`interpretations`、`contract_conflicts`、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。

## Forbidden
- 不修改本合同、`tests/test_kit_logs_oracle.py`、调度脚本、代理规则或权限配置。
- 不修改 `scripts/pi_dispatch.py`、`scripts/kit_config.py`、`scripts/kit_install.py`、`scripts/codekit/**`（只调用其中的函数）。
- 不删除、跳过或弱化测试来获得通过；不用 `tempfile` 在仓库外建目录。
- 不提交（除非 authorized_actions 含 local_commit）；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
