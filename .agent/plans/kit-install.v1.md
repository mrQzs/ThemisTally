# TASK: kit-install

## Identity
- plan_version: 1
- repository: Code-Kit
- base_sha: b0f762544d792f69169080750cd42577a0c7ad58
- risk_level: medium
- authorized_actions: local_edit, local_test
- integration_actions: local_branch, merge
- executor: step/step-5-preview · thinking high

## Goal
按设计说明 `docs/themis-tally-2.9-安装与更新.md`（用户决定第 6 节四项均选推荐项）新建 `scripts/kit_install.py`：`check` / `install` / `update` 三个命令把 kit 的运行时、技能与示例复制进另一个 Git 仓库，留安装记录 `.agent/kit-install.json`，并按记录分辨“kit 更新了”与“目标本地改过”；让规划端 oracle `tests/test_kit_install_oracle.py`（16 个用例）全部通过；新建执行器测试 `tests/test_kit_install.py`（清单见 Step 4，刻意不长）。

## Non-goals
- 不改调度器 `scripts/pi_dispatch.py` 与它加载的文件，不改技能、AGENTS.md、README、CHANGELOG：doctor 的完整性检查、调度器的转发与文档由规划端在集成后补。
- 不做打包，不联网下载 kit，不删除目标里的任何文件，不自动合并已有 AGENTS.md 的正文。
- 不碰目标仓库的 `.agent/plans`、`.agent/reviews`、`.agent/runs`；在目标仓库里不运行任何写 Git 的命令，不提交。

## Repository facts
- 基线 = master 上的规划端 oracle 提交 `b0f762544d792f69169080750cd42577a0c7ad58`，含新文件 `tests/test_kit_install_oracle.py`（16 个用例，一个类 `KitInstallOracle`，Windows 上约 7 秒；基线上全部失败：`scripts/kit_install.py` 不存在）。
- oracle 全部经真实子进程 `python <kit>/scripts/kit_install.py …` 驱动：
  - 多数用例把发放文件加上 `scripts/kit_install.py`、`AGENTS.md`、`gitignore.append.txt`、`gitattributes.append.txt` 复制到临时目录当作 kit（不是 Git 仓库，所以 `kit_commit` 为 `null`），借此改 kit 来模拟升级、放进缓存文件；最后一个用例用本仓库本身当 kit（是 Git 仓库）。
  - 目标仓库都是临时目录里 `git init` 的空仓库。Windows 上目录链接用 junction（`_winapi.CreateJunction`，它不是符号链接），其它平台用符号链接。
- `scripts/pi_dispatch.py` 里直接复用的常量：`TOOL_VERSION`；`KIT_LOADED_FILES`（2.8.0 新增，九项，最后一项是 `plugins/decisions/**`）；`KIT_SKILLS`（四个技能名）；`SKILL_SOURCE_DIR`（`.agents/skills`）；`CLAUDE_SKILL_DIR`（`.claude/skills`）。`scripts/kit_config.py` 第 40 行左右是从脚本自己的目录导入 `pi_dispatch` 的写法（`HERE = Path(__file__).resolve().parent`，不在 `sys.path` 时插到最前，然后 `import pi_dispatch as pd`），照它写；导入 `pi_dispatch` 没有副作用。Windows 控制台的 UTF-8 输出照 `pi_dispatch.main()` 开头的 `reconfigure` 写法。
- kit 根目录里与安装有关的文件：
  - `AGENTS.md`：五个二级标题（角色判定、通用工程要求（所有代理）、规划端（Claude Code / Codex）、.agent/ 目录（读写其中文件时）、Pi 执行器（收到 `TASK:` 合同与“执行说明”时））；
  - `gitignore.append.txt`：一条规则 `.agent/runs/`；`gitattributes.append.txt`：两条规则 `*.sh text eol=lf`、`.agent/** text eol=lf`（两个文件里其余的行是 `#` 注释或空行）；
  - 五个附加文件：`.claude/agents/pi-reviewer.md`、`.agent/README.md`、`.agent/dispatch.config.example.json`、`.codex/config.example.toml`、`.claude/settings.example.json`。
- 规划端草稿实测（Windows，约 260 行）：oracle 16/16；35 条故意偏差全部被 oracle 抓住（运行时不含 `KIT_LOADED_FILES`、技能只装一份、不装附加文件、复制 `__pycache__` 或 `.pyc`、kit 里的链接不拦、只认符号链接不认 junction、子目录当仓库根、装进 kit 自己、相同文件不算 `SAME`、`UPDATE` 与 `KEEP` 颠倒、没有记录的不同文件直接覆盖、已有 AGENTS.md 也覆盖、缺少章节列全部、已有规则再追加、追加块前的换行写死、注释行改写、已有 `dispatch.config.json` 也覆盖、不报告不再发放的文件、允许重复 install、没有记录也能 update、`--force` 不备份或不起作用、`KEEP` 的记录哈希丢掉、不再发放的文件留在记录里、`kit_commit` 写成 null、有冲突也退出 0、check 也写记录、check 接受 `--force`、目标路径上的链接不拦、`schema_version` 写错、`counts` 只列出现过的状态、AGENTS.md 永远 `MANUAL`、备份放在 `.agent` 之外、记录的哈希写错）。草稿树（新检出的 worktree）上全量 pytest 1460 passed、6 failed：6 个都是新检出时系统级 core.autocrlf=true 把按字节核对的插件说明与探针证据转成了 CRLF，与本合同无关；基线之前的提交 `c2eb96b` 已用 `.gitattributes` 修好（新检出的 worktree 上这 4 个测试文件 51 passed）。除此之外没有别的测试钉住新文件。
- 本仓库 `.agent/dispatch.config.json` 把 `scripts/codekit/**`、`schemas/**` 等列为执行器只读；`KIT_LOADED_FILES` 与调度器本身是内置只读。

## Scope
- allowed_modified_files: 无
- allowed_new_files:
  - scripts/kit_install.py
  - tests/test_kit_install.py
- allowed_deleted_files: 无
- forbidden_paths: `tests/test_kit_install_oracle.py`, `scripts/pi_dispatch.py`, `scripts/dispatch-pi.sh`, `scripts/kit_config.py`, `scripts/codekit/**`, `plugins/**`, `schemas/**`, `docs/**`, `README.md`, `CHANGELOG.md`, `AGENTS.md`, `gitignore.append.txt`, `gitattributes.append.txt`, `tests/test_dispatch.py`, `tests/stub_pi.py`, `tests/test_kit_v280.py`, `tests/test_kit_config.py`, `tests/test_decisions.py`
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
下列名字由本合同固定：文件 `scripts/kit_install.py`；函数 `payload(kit_root)`（返回排序、不重复的仓库相对 POSIX 路径列表）与 `main(argv=None)`；常量 `STATUSES = ("ADD", "SAME", "UPDATE", "KEEP", "CONFLICT", "APPEND", "MANUAL", "REMOVED")`、`RECORD = ".agent/kit-install.json"`。执行器测试可以用私有名字；oracle 只通过子进程驱动。

1. **发放内容** `payload(kit_root)`：
   - 条目依次是：`scripts/pi_dispatch.py`、`scripts/dispatch-pi.sh`；`pd.KIT_LOADED_FILES` 的每一项；`pd.KIT_SKILLS` 的每个技能的 `<SKILL_SOURCE_DIR>/<技能>/**` 与 `<CLAUDE_SKILL_DIR>/<技能>/**`；五个附加文件（见 Repository facts）。
   - 以 `/**` 结尾的条目是目录：递归收集其中的文件，跳过名为 `__pycache__` 的目录（连同其中一切）与以 `.pyc` 结尾的文件。其它条目必须是普通文件。
   - 缺少任何一项，或任何条目、条目里的任何目录或文件是符号链接或 junction（`os.lstat` 的 `stat.S_ISLNK`，或 `st_file_attributes` 带重解析点标志 `0x400`；注意 `os.walk` 会进入 junction），都是拒绝（第 6 条）。
   - `AGENTS.md`、两个 `.append.txt` 与 `scripts/kit_install.py` 不在发放内容里（前三个按第 3 条处理）。
2. **每个发放文件的状态**（按 `payload` 的顺序，每个一行）：目标里没有 → `ADD`；字节与 kit 相同 → `SAME`；不同，而安装记录有这个路径：目标的 sha256 等于记录里的 → `UPDATE`（kit 更新了，目标是上次装的原样），否则 → `KEEP`（本地改过）；不同，而记录里没有这个路径 → `CONFLICT`。
3. **其它条目**（在发放文件之后，依次如下）：
   - `AGENTS.md`：目标没有 → `ADD`（写入 kit 的 `AGENTS.md`）。已有 → 取 kit `AGENTS.md` 里以 `## ` 开头的行，目标里没有相同一行的（两边都去掉首尾空白比较）按 kit 中的顺序列出：有缺少的 → `MANUAL`，说明是 `缺少 kit 章节：` 加上这些标题（去掉 `## ` 与首尾空白，以 `、` 相连）；一个不缺 → `SAME`（没有说明）。已有的 AGENTS.md 永远不写（`--force` 也不写），它不进安装记录。
   - `.gitignore`，然后 `.gitattributes`：规则是 kit 对应片段（`gitignore.append.txt`、`gitattributes.append.txt`）里去掉首尾空白后非空、且不以 `#` 开头的行；目标文件里没有相同一行（去掉首尾空白比较）的规则就是缺少的。有缺少的 → `APPEND`，说明是 `补上 ` 加上这些规则（以 `、` 相连）；没有 → `SAME`。写入时原内容一个字节不改，只在末尾追加：原文件非空且不以 `\n` 结尾时先补一个 `\n`；原文件非空时再加一个空行 `\n`；然后一行 `# Code-Kit（kit_install.py 追加）`，接着每条缺少的规则一行，每行以 `\n` 结尾。目标没有这个文件时就以这一块新建它。
   - `.agent/dispatch.config.json`：目标没有 → `ADD`（写入 kit 的 `.agent/dispatch.config.example.json` 的字节）；已有 → 不列出、不写。
   - 安装记录里有、`payload` 里已经没有的路径（按路径排序）→ `REMOVED`，说明非空（例如 `kit 已不再发放，没有删除`），文件不删。
4. **三个命令**：`python scripts/kit_install.py {check,install,update} <目标> [--force]`。
   - `check`：只读，不写任何文件（包括记录与备份）；带 `--force` 是用法错误（退出 2）。
   - `install`：目标已有安装记录 → 拒绝（第 6 条，消息里提到 `update`）。`ADD` 写入（`AGENTS.md`、`dispatch.config.json` 按第 3 条）；`APPEND` 按第 3 条追加；`SAME` 不写；`CONFLICT` 不写（`--force` 时按第 5 条覆盖）。最后写记录（第 7 条）。
   - `update`：目标没有安装记录 → 拒绝（消息里提到 `install`）。`ADD` 与 `UPDATE` 写入 kit 字节；`KEEP` 与 `CONFLICT` 不写（`--force` 时按第 5 条）；`APPEND`、`REMOVED`、`AGENTS.md`、`dispatch.config.json` 同上。最后写记录。
   - 所有写入都按字节（不转换换行），先写同一目录里的临时文件再 `os.replace`；父目录不存在就建。
5. **`--force`**：`KEEP` 与 `CONFLICT` 的文件先把目标里的原字节复制到备份目录 `<目标>/.agent/kit-backup/<UTC 时间 YYYYMMDDTHHMMSSZ>/<路径>`（同一次运行共用一个备份目录；目录已存在时在时间后加 `-2`、`-3`…），再写入 kit 字节；这一行的状态改为 `UPDATE`，说明是 `--force：原文件备份到 <备份目录相对目标的 POSIX 路径>/<路径>`。
6. **拒绝**（退出码 2；stdout 不输出；stderr 一行，以 `ERROR: ` 开头；目标里什么也不写）：目标不存在或不是目录；目标（解析后）就是 kit 根目录；目标不是 Git 工作区的根目录（`git -C <目标> rev-parse --show-toplevel` 失败，或解析后不等于目标）；第 1 条的 kit 问题；目标里要读写的任何路径（发放文件、`AGENTS.md`、两个规则文件、`dispatch.config.json`、记录、备份）从目标根往下的任何一级是符号链接或 junction，或该路径已存在却不是普通文件；`install` 时已有记录；`update` 时没有记录；记录不是 JSON 对象、`record_type` 不是 `code-kit-install`、或 `files` 不是对象；未知命令（argparse 的退出 2）。这些检查都在第一次写入之前完成。
7. **安装记录** `<目标>/.agent/kit-install.json`，以 `json.dumps(…, ensure_ascii=False, indent=2, sort_keys=True)` 加换行写入，键恰好是：
   - `record_type`（`"code-kit-install"`）、`schema_version`（`1`）、`kit_version`（`pd.TOOL_VERSION`）；
   - `kit_commit`：kit 根目录是 Git 工作区时为 `git -C <kit> rev-parse --verify HEAD` 的完整 sha，否则 `null`；`kit_dirty`：有提交时为 `git -C <kit> diff --quiet HEAD -- <全部发放文件>` 的退出码是否非 0，否则 `null`；
   - `installed_at`、`updated_at`：UTC `YYYY-MM-DDTHH:MM:SSZ`，update 保留原来的 `installed_at`；
   - `files`：这次运行之后目标里与 kit 字节相同的发放文件（`ADD`、`SAME`、`UPDATE`，含 `--force` 覆盖的）→ kit 字节的 sha256；没有覆盖的 `KEEP` 保留记录里原来的哈希；没有覆盖的 `CONFLICT` 不进记录；`REMOVED` 的路径从记录里去掉。
8. **输出与退出码**：stdout 先是每个条目一行 `<状态> <路径>`，有说明时再加两个空格与说明（路径是相对目标根的 POSIX 路径；`--force` 覆盖的行按第 5 条）；最后一行是 `json.dumps(…, ensure_ascii=False, sort_keys=True)` 的汇总，键恰好是：`command`；`target`（解析后的目标绝对路径）；`kit_root`（解析后的 kit 根目录）；`kit_version`；`kit_commit`；`counts`（八个状态都在，值是该状态的行数）；`unresolved`（这次运行之后仍是 `KEEP` 或 `CONFLICT` 的路径，按输出顺序）；`backup`（备份目录相对目标的 POSIX 路径，没有备份为 `null`）；`record`（install、update 为 `".agent/kit-install.json"`；check 在记录已存在时为它，否则 `null`）。退出码：`unresolved` 非空为 1，否则 0；拒绝为 2。stdout 与 stderr 用 UTF-8。
9. **文档串与导入**：模块文档串写明用法（三个命令与 `--force`；这是“把 kit 装进目标仓库”的布局，另一种是从 kit 目录直接运行调度器，不需要安装）、八个状态的含义与拒绝的情形；导入无副作用（只在 `__main__` 下运行 `main`）；只用标准库。

## Steps
1. 读 AGENTS.md、本合同、设计说明、oracle 文件，`scripts/kit_config.py` 开头导入 `pi_dispatch` 的写法，`scripts/pi_dispatch.py` 里 Repository facts 列出的常量与 `main()` 开头。基线与 Repository facts 不符就停止并报告。
2. 写 `scripts/kit_install.py`（第 1–9 条；约 250 行连文档串）。
3. 跑 V01 直到 oracle 全过（约 7 秒）。
4. 新建 `tests/test_kit_install.py`，只覆盖下面这些（oracle 已覆盖三个命令的完整流程、冲突与备份、链接与记录；可以沿用 oracle 的 harness 写法，但不要照抄 oracle 的用例；每个用例先验证合法基线，再只改一处）：
   - 直接导入模块调用 `payload(<本仓库根>)`：返回值排序、不重复、都是 POSIX 相对路径；包含 `pd.KIT_LOADED_FILES` 里每个不以 `/**` 结尾的条目；不含 `AGENTS.md`、`scripts/kit_install.py` 与任何 `__pycache__` 路径；
   - 目标的 `.gitattributes` 以 CRLF 换行、末尾没有换行、已含其中一条规则时，install 只追加缺少的那一条，原字节在前；
   - `update` 时某个发放文件在目标里被删掉 → 那一行是 `ADD`，写回 kit 字节，退出 0；
   - 汇总的 `counts` 八个键都在，值的和等于条目行数；
   - 拒绝时 stdout 为空、stderr 以 `ERROR: ` 开头（用一个不存在的目标）。
   写测试时先跑单个用例，不要每改一处就跑整个文件；整文件只在最后跑一次。
5. 运行 V01–V03、V05–V07。**不要运行 V04**（全量约 7 分钟，验收端会跑）。**不要自己做变异检查**：不要故意改坏实现来测试，也不要把仓库复制到临时目录去改；验收端会在固定候选上做。
6. 写执行报告；遇到合同没有定义的行为，停止并在 `unresolved_questions` 中说明。

## Validation commands

必要检查优先直接执行；输出管道必须保留被检查程序的真实失败状态，不能以 tail/echo 的成功退出码作为检查通过证据。需要截短输出又要保留真实退出码时，直接运行检查命令即可（工具会返回完整输出与退出码）；确要截短，写成 `T=$(mktemp -d); <命令> > "$T/out" 2>&1; echo "exit=$?"; tail -n 20 "$T/out"; rm -rf "$T"`，删除之后不再接任何命令，也不要写到 `/tmp/v01.txt` 这类固定路径。探针里不要用 `tempfile`。不要自己做变异检查。只读写工作副本内的路径。

- V01（必要，基线应失败）：`python -m pytest -q -p no:cacheprovider tests/test_kit_install_oracle.py` · cwd：仓库根 · 超时：300s · 期望退出码：0 · 输出须匹配：`[1-9]\d* passed`
- V02（必要，基线应失败）：`python -m pytest -q -p no:cacheprovider tests/test_kit_install.py` · cwd：仓库根 · 超时：300s · 期望退出码：0 · 输出须匹配：`[1-9]\d* passed`
- V03（必要）：`python -m pytest -q -p no:cacheprovider tests/test_kit_v280.py tests/test_kit_config.py tests/test_decisions.py` · cwd：仓库根 · 超时：300s · 期望退出码：0 · 输出须匹配：`[1-9]\d* passed`
- V04（必要，基线应失败）：`python -m pytest -q -p no:cacheprovider --ignore=tests/test_dispatch.py` · cwd：仓库根 · 超时：1200s · 期望退出码：0 · 输出须匹配：`[1-9]\d* passed`
- V05（必要）：`python -m compileall -q scripts tests` · cwd：仓库根 · 超时：120s · 期望退出码：0
- V06（必要）：`git diff --check` · cwd：仓库根 · 超时：60s · 期望退出码：0
- V07（必要，基线应失败）：`python -c "import sys; sys.path.insert(0, 'scripts'); import kit_install as k; assert k.STATUSES == ('ADD', 'SAME', 'UPDATE', 'KEEP', 'CONFLICT', 'APPEND', 'MANUAL', 'REMOVED') and k.RECORD == '.agent/kit-install.json' and callable(k.payload) and callable(k.main); print('kit_install ok')"` · cwd：仓库根 · 超时：60s · 期望退出码：0 · 输出须匹配：`kit_install ok`

V01、V04、V07 在基线上失败，是因为 `scripts/kit_install.py` 还不存在；V02 是因为测试文件还不存在。V03 保护 2.8 的单元测试、配置管理器与决策模块。检查命令按 argv 直接执行，不经 shell。全量约 7 分钟。

## Definition of done
- D01：发放内容与每个发放文件的状态（第 1–2 条）；证据：V01、V02；目的：装进目标仓库的 kit 与 kit 本身逐字节一致，kit 一升级就能分清哪些文件过期、哪些被本地改过。
- D02：AGENTS.md、两个规则文件与 dispatch 配置（第 3 条）；证据：V01、V02；目的：目标仓库自己的规则与配置一个字节都不被改写，缺什么都说清楚。
- D03：三个命令与 `--force`（第 4–5 条）；证据：V01、V02；目的：本地改过的东西不会在更新时悄悄丢失，覆盖之前一定有备份。
- D04：拒绝（第 6 条）；证据：V01、V02；目的：链接与仓库之外的路径一个字节都不写，拒绝时目标原封不动。
- D05：安装记录、输出与退出码（第 7–8 条）；证据：V01、V02、V07；目的：被脚本调用时最后一行就能读到结果，记录足以支撑下一次 update 与 doctor。
- D06：其它模块与测试不受影响，文档串与导入按第 9 条，Step 4 的测试齐全，不自行做变异检查，所有修改在允许集合内，无依赖变更；证据：V03、V04、V05、V06、scope、review。

## Stop conditions
- 基线、oracle、已有接口或 Repository facts 与本机不符。
- 必须修改允许范围之外的文件才能继续。
- 需要新增或升级依赖、联网、访问凭据或启动真实 pi。
- 本合同对同一行为说法不同，或出现合同没有定义的行为。
- 达到单轮时限。

## Budget
- max_attempts_total: 2（按 task-id 汇总，包括返工版本）
- max_wall_seconds_per_attempt: 1800
- max_wall_seconds_total: 3600
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计
- 时间分配（上限 30 分钟，按 20 分钟规划、留 10 分钟余量）：
  - 阅读约 5 分钟；
  - 实现约 7 分钟（一个文件，约 250 行）；
  - 测试约 5 分钟（5 组用例，先跑单个用例）；
  - 运行检查约 2 分钟（oracle 约 7 秒，V03 约 3 秒；不跑 V04）；
  - 执行报告约 1 分钟。

## Report back
- 最后一条消息必须是执行报告：逐项说明 D01–D06，列出自检命令与结果、遗留问题与阻塞原因，末尾附上执行说明规定的 JSON 代码块。
- 自检结果是自述；最终是否通过由验收端决定。
- 对合同的任何解读或取舍，写进 `contract_conflicts` 或 `unresolved_questions`，不要只写在 limitations 里。

## Forbidden
- 不修改本合同、oracle、调度器与它加载的文件、技能、代理规则或权限配置，不修改允许集合之外的已有文件。
- 不删除、跳过或弱化测试来获得通过。
- 不自己做变异检查，也不把仓库复制到临时目录运行。
- 不访问工作副本以外的路径（包括主仓库与 `.agent/runs`）。测试代码里的临时目标仓库照 oracle 的写法（`tempfile.mkdtemp` 加清理）；命令与探针里不另建临时目录。
- 不提交；不推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
