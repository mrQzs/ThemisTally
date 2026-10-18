# Themis Tally 3.0 第二轮设计：角色绑定（轻量底座）与配置中心

状态：**闸一通过**（第 4 轮零 Blocking，“可以进入实现阶段”，2026-10-18）。第 4 轮的 Should-fix 与 Nit 在过闸后直接采纳，见 §0.0，由闸二一并核对。四轮的结论：

- 第 1 轮：7 个 Blocking、7 个 Should-fix、2 个 Nit；
- 第 2 轮：6 个 Blocking、7 个 Should-fix、2 个 Nit；
- 第 3 轮：2 个 Blocking、6 个 Should-fix、2 个 Nit；
- 第 4 轮：0 个 Blocking、3 个 Should-fix、3 个 Nit。

处置见 §0。第 2 轮之后用户做了两项决定，见 1.1：配置写入改为加锁；信任边界另立任务。

- 分支：`themis-3.0`（本地，不推送），起点 `106e94a`（2.11.0，已快进合并到本地 master）。
- 上位设计：`docs/themis-tally-3.0-四端分层解耦架构.md`。本轮涉及：
  - 3.4、6.3、7、8.1、8.5、8.6、11 节；
  - 12 节的 P1、M1。
- 调查：`.agent/design/3.0-r2-调查摘要.md`，在 `b5e9ea5` 上做的。
- 下文的源码 `file:line`：
  - 都在 `b525cb8` 上核对过；
  - 本稿提交之前，代码与它相同，中间只有文档提交。
- 缩写：
  - PD = `scripts/pi_dispatch.py`
  - KC = `scripts/kit_config.py`
  - TD = `tests/test_dispatch.py`

## 0. 审核变更对照表

### 0.0 第 4 轮（零 Blocking，“可以进入实现阶段”；Should-fix 与 Nit 过闸后直接采纳，由闸二一并核对）

| 编号 | 第 4 轮结论 | 本稿处置 |
|---|---|---|
| r4-S1 | D5 第 4 步无条件先解析当前绑定：已有有效记录、当前绑定已被删除时，到不了“采用记录”的分支 | D5 第 4 步改为：<br>① 已有记录就直接校验并采用；<br>② 没有记录时才构造候选，`publish_new` 返回 False 时，重新读取胜者并完整校验；<br>③ 最后统一检查合同哈希、`PI_EXEC_*` 与允许列表。<br>K9 覆盖 |
| r4-S2 | D8 把“检查时刻”说成了“写入时刻”：检查与替换之间领取的 attempt 会被漏掉 | D8 的承诺改为“状态检查时发现有在运行的 attempt 才确认；检查之后的领取不纳入这次提醒”，并写明时间差。被漏掉的 attempt 照样不受影响。M7b 让写入者停在检查与替换之间 |
| r4-S3 | 外部改动“只记一次”不覆盖事务后半段失败：observed 之后 intent 失败，重试会再记一次 | D7 第 4 步的比较基准，改为 R 上最后一条“已知内容”：已发布的 after 或 observed 的 after。重试不会重复记录。T7 覆盖 |
| r4-N1 | 令牌检查之后仍有人工换锁的窗口 | 措辞改为“释放检查时令牌不同就不动”，这个窗口归入人工删锁的残余 |
| r4-N2 | local 的历史会显示“疑似凭据” | history 按资源分别显示“疑似凭据，未存内容”与“本机配置只存哈希”；local 的 history show 没有逐键差异 |
| r4-N3 | T7、T10、`publish_new` 的错误分支、K4b 还缺几个明确的断言 | 补上：T7、T10、T12（`publish_new` 的四个分支）、K4b 拆成两个独立场景 |

### 0.1 第 3 轮

| 编号 | 第 3 轮结论 | 本稿处置 |
|---|---|---|
| r3-B1 | 300 秒清锁会让被挂起的旧持有者恢复后继续发布：版本记录被 `os.replace` 覆盖，同一版本出现两个模型；已经补判为未发布的事务又被发布；旧持有者退出时还会删掉新持有者的锁 | **版本记录**（D5）改为不覆盖的原子发布 `publish_new`：Windows 用 `os.rename`（目标存在时失败），POSIX 用 `os.link` 后删除临时文件。旧持有者恢复后发布会失败，转而读取并采用已有记录，所以唯一性不再依赖任何锁；任务锁只用来减少争用，行为不变。<br>**配置锁**（D7）不再复用 `TaskLock`，改为 `ConfigLock`：<br>① 从不自动抢占，等 30 秒后报错，写明持锁进程的 pid、主机与是否仍在运行（`pid_alive`，PD:905），由人确认后删除；<br>② 释放前核对令牌，只删自己的锁。<br>残余：手工删除仍被挂起的进程的锁，这一条写进 D7 |
| r3-B2 | 配置文件与本机文件共用审计，补判与外部改动的比较却不区分资源 | D7：每条记录带 `resource`（`config` 或 `local`）。补判、“最后发布的 after”、外部改动都按资源分别计算；只有 `config` 存快照。T10 覆盖两个文件交替写入，以及本机文件中断后补判 |
| r3-S1 | 采用别人抢先发布的记录之后，没有对最终模型重做允许列表与 `PI_EXEC_*` 检查 | D5 第 4 步：选定最终记录之后重做这两项检查。失败时抛 `BindingRecordError`，带相应的退出码（允许列表 3，环境变量 2），attempt 记 PREPARE_FAILED。K4b 覆盖 |
| r3-S2 | 运行中切换的确认只在写入时判定，承诺比实际强 | D8 写明语义：<br>① 确认在配置锁内、写入的那一刻判定；<br>② 判定之后才领取的 attempt 视为发生在切换之后，用自己版本记录里的模型，或者写入之后的绑定，所以不存在“运行中被切换”。<br>M7b 覆盖这个时间差的可观察结果 |
| r3-S3 | 两处缺口：<br>① `first_link_component` 不查 root 本身，`.agent/runs` 是 junction 时查不出；<br>② G0 由 meta 里有没有字段来决定是否核验 | ① D5：从仓库根查起，`first_link_component(repo.root, ".agent/runs/<task>/binding-v<N>.json")`，覆盖 `.agent` 与 `runs` 两级。<br>② G0 是否必须核验，由冻结合同的 raw 分类决定：按角色写的合同缺少 `executor_binding` 时，本身就是 G0 失败。<br>K14b、K16 覆盖 |
| r3-S4 | `kit_install` 检查“配置不存在”与真正写入之间有时间差，会覆盖配置中心刚写的配置 | D7：`kit_install` 写示例配置也改用 `publish_new`。写入时目标已经存在就不覆盖，那一行显示“已存在，未覆盖”。T11 覆盖 |
| r3-S5 | D3 的“本机文件不能指定命令”与“未提交的本机文件可以给出命令”自相矛盾 | D3、§0.2、1.1 改为：提交进仓库的内容不能指定命令，包括提交的配置，以及被 Git 跟踪、未被忽略或经过链接的本机文件；未提交并被忽略的本机文件是这台机器的设置，可以指定命令。这是对用户决定措辞的澄清，不是改变它 |
| r3-S6 | 事务步骤与“校验失败不写记录”互相矛盾；重复失败还会重复记外部改动 | D7 重排顺序：读取 → 修改 → 校验；没有变化就结束 → 补判 → 外部改动 → 快照 → intent → 替换 → commit。校验失败、dry-run、没有变化时一条记录也不写。外部改动只在随后真正写入时记一次。T7 改为断言“审计文件字节不变” |
| r3-N1 | “只影响下一次 attempt”不准确 | 改为“只影响尚未建立版本记录的合同版本” |
| r3-N2 | T4、K12、M3 的表述还需收紧 | 9 节相应修改 |

### 0.2 第 2 轮

| 编号 | 第 2 轮结论 | 本稿处置 |
|---|---|---|
| r2-B1 | D3 只核对了 PATH 目录，没有核对最终的程序与 npm 包装指向的 JS；UNC 别名未处理；新命令的调用链上仍有裸名 git，与“新命令不执行仓库里的程序”的保证冲突 | **用户 2026-10-18 决定：信任边界另立任务**。本稿删去 `trusted_which`，第 2 稿 10 节第 7、8 项随之撤销。D3 的保证收窄为“提交进仓库的内容不能指定命令”，措辞经第 3 轮 S5 澄清。新命令查找 CLI 的方式与现有 doctor 相同（`shutil.which` / `resolve_pi_command`），在 Windows 上会先查当前目录，涉及 pi、node、git 与各个 CLI。这是既有残余，写进 §6，由那个单独的任务修 |
| r2-B2 | O_EXCL 只保证文件名独占，记录不是原子发布：胜者写到一半时，后来者会读到空文件或半份 JSON，崩溃还会留下一份永久的空记录 | D5：版本记录先写独立的临时文件，再发布，所以看不到写了一半的记录。第 3 轮又改为不覆盖的发布，见 r3-B1。记录不完整、损坏或经过链接时，拒绝并说明，不自动修复 |
| r2-B3 | 冲突检测没有覆盖最初的读、改、写（KC:505-516），会丢更新；“当前文件等于后一条 published 的 after”也不成立 | **用户决定加锁**。D7：所有写配置的入口在配置锁内完成“读、改、写、记历史与审计”，不再需要 CAS。提交顺序就是持锁的顺序 |
| r2-B4 | Windows 的 O_APPEND 不是原子追加（CPython issue 42606），并发追加会覆盖 | D7：审计只在配置锁内追加，同一时间只有一个写入者。读取时容忍末尾的半行与损坏的行：列出它们的行号，不中断。追加前，若文件不以换行结尾，先补一个换行 |
| r2-B5 | 三个问题：<br>① 按当前哈希补判会误判；<br>② 已补判为发布的记录会在之后被改判；<br>③ 用“历史上见过这份内容”判断 external，会漏记 git checkout 回旧内容 | D7：<br>① 补判只由下一个持锁的写入者做一次，结果写成 `resolve` 记录，之后不再改判。判断规则：当前等于 after 是已发布，等于 before 是未发布，都不等是未知。没有锁外改动时，这个判断是确定的；锁外改动恰好凑成 before 或 after 的残余，写明在 D7。<br>② external 改为与“按日志顺序，最后一个已发布事务的 after”比较。有锁之后，日志顺序就是实际顺序 |
| r2-B6 | D8 的比较漏掉了 adapter（`runtime add --force` 改 adapter 可以免确认）；惰性导入的条件只看写入后的配置 | D8：比较每个角色完整的生效绑定（mode、profile、runtime、adapter、provider、model、thinking）；写入前后任一份配置有 v3 键时就计算 |
| r2-S1 | 已有的版本记录仍被“当前绑定必须就绪”挡住 | D5：首次建立记录时，要求当前绑定有效；已有有效记录时，以记录为准，当前配置只用来提示差异。允许列表与 `PI_EXEC_*` 照常独立检查。记录不随 PREPARE_FAILED 的 attempt 清理 |
| r2-S2 | 冻结之后的 EXIT_DRIFT 会被 prepare 的包装改成 3（PD:4276-4279） | D5：新分支抛专门的 `BindingRecordError`（`DispatchError` 的子类），包装原样重新抛出，保留退出码。现有路径的包装行为不变。补“预检之后才漂移”的用例 |
| r2-S3 | G0 只比较模型三项，`record_path` 没有约束；链接用例从测试表里消失了 | D5：`verify_inputs` 做三项核对，任一不符就以 G0 拒绝：<br>① 记录的路径由 meta 的 task_id 与 plan_version 推出，不读 meta 里的路径；<br>② 路径上没有链接；<br>③ 记录的全部字段与 meta 中的副本相同，`contract_json_sha256` 与 meta 一致。<br>K14、K16 覆盖 |
| r2-S4 | `_env` 后缀的豁免过宽：说明键 `_secret_env` 也能被豁免 | D7：只豁免 schema 明确规定的字段路径：`decisions.api_key_env`、`profiles.<id>.credential_env`、顶层的 `env_remove` 与 `env_keep` |
| r2-S5 | 只凭 `claim/` 不能说明 attempt 仍在运行 | D8：沿用 `collect --recover` 的判定（PD:4504）：状态为 RUNNING、COLLECTING，或者已领取的 PREPARED |
| r2-S6 | 变量存在但值为空，会被判为凭据可用 | D9：要求值非空。只判断，不输出值 |
| r2-S7 | 第 9 节还没有覆盖本稿新承担的保证 | 第 9 节按审核表补齐。信任边界那几项随 r2-B1 移出本轮 |
| r2-N1 | scan 与 probe 的调用规则前后有两种说法；probe 的模型从哪来没有定义 | D3、D10 与 4.1 统一：<br>① scan 只运行 `--version`；<br>② probe 运行 `--version`，pi 另加 `--help`；<br>③ models 运行 `--list-models`，不带过滤；<br>④ `config doctor` 按每个 profile 运行 `--list-models <模型>` 与 `auth check --no-refresh` |
| r2-N2 | 送审的基线标识与实际 HEAD 不一致 | 开头写明：源码行号在 `b525cb8` 上核对；本稿提交之前，代码与它相同 |
| r2 第 10 节意见 | 加锁与否影响正确性，不能只作为偏好；PATH 的收紧改变 2.10 的可观察行为，要在实现前定案 | 两项都已由用户决定（1.1），从第 10 节移除 |

### 0.3 第 1 轮（第 2 稿的处置；被后两轮推翻或修改的，以 0.1、0.2 为准）

| 编号 | 第 1 轮结论 | 处置 |
|---|---|---|
| r1-B1 | 本机文件被提交后读取时不会拒绝；PATH 解析会执行仓库里的程序 | 本机文件读写之前做三项检查（D3），这一部分保留。PATH 的部分见 r2-B1：另立任务 |
| r1-B2 | 同一版本的并发首次 prepare、没有绑定时的首次 prepare、解析与冻结用了不同的字节 | D4：按角色写的合同必须有绑定。D5：每个合同版本一份记录，用冻结后的字节解析；原子性见 r2-B2 |
| r1-B3 | 写死模型的合同本来就在 prepare 时提前解析；第 1 稿把论证写反了 | 写死合同的提前解析与拒绝顺序原样保留，NOTE 放在后面（第 2 轮确认已闭环） |
| r1-B4、B5 | 历史的补记与编号在崩溃和并发下不成立 | 第 2 稿改为无锁事务。第 2 轮指出无锁协议仍不成立，现改为加锁，见 r2-B3、B4、B5 |
| r1-B6 | 历史放在 kit_roles，与惰性导入冲突 | 历史放进 kit_config；检查函数在键缺省时立即返回（第 2 轮确认已闭环） |
| r1-B7 | “运行中切换要确认”不能删 | D8 的确认。比较的字段与运行中的判定见 r2-B6、S5 |
| r1-S1 | raw、normalized 与 resolved 要分清 | D4 按 raw 分三类（第 2 轮确认）。“写死”的判定沿用旧代码的真值条件，见 9.4 的 K12 |
| r1-S2 | 同一 runtime 只探测一次会误判 | D10：版本与帮助按 runtime 缓存，模型与登录按 profile 分别检查 |
| r1-S3 | 凭据可用性与实际子进程环境不一致 | D9；空值的情形见 r2-S6 |
| r1-S4 | 快照的凭据检测太弱 | D7；豁免范围见 r2-S4 |
| r1-S5 | 读回点没有收口 | D5 的 `attempt_executor` |
| r1-S6 | history 没有差异；actor 不是自声明；init、插件、decisions 的写入没有定义 | D7 |
| r1-S7 | 测试有缺口 | 第 9 节 |
| r1-N1、N2 | audit_id；返回协议的错误码 | 128 位随机数；D12 的 `(值, 错误)` 带退出码 |
| 自查 | 敏感键规则会命中合法的 `api_key_env` 与 `credential_env` | 豁免这两个字段；范围见 r2-S4 |
| 前置 | — | 两项前置已单独提交：<br>① `2aa8a61`：`tests/test_dispatch.py` 在 pytest 下能失败了；<br>② `b525cb8`：`resolve_run_dir` 不再跟随链接 |

## 1. 范围

### 1.1 用户决定（2026-10-18）

**开第二轮之初**：

- 开第二轮，走 2gate。
- **P1 做轻量底座**：
  - 做：解析 v3 的角色绑定与方案，登记适配器；内核按 execution 角色（以及声明为合同端的合同）解析执行模型；配置中心七项功能全做，`runtime scan` 只查 PATH。
  - 不做：把 Pi 抽成适配器，留到接第二个 CLI（P4）时再做。
- **执行模型以绑定为准**：
  - 新合同不写 provider 与 model；
  - prepare 按当前绑定解析，并按合同版本记一份快照，同一版本之后的 attempt 都沿用它；
  - 写死模型的合同仍以合同为准，与绑定不一致时提示；
  - AGENTS.md 的“换模型要写进新合同”改为“换绑定要用户同意”。

**闸一第 2 轮之后**：

- **配置写入加锁**：这一条改变了第一轮第 10 节第 3 项“本轮不加锁”的决定。
  - 原定做法是沿用调度器的任务锁；
  - 闸一第 3 轮之后改为单独的配置锁：从不自动抢占，见 D7。
- **“不执行仓库里的程序”这条信任边界另立任务，不放在第二轮**：
  - 第二轮只保证：提交进仓库的内容不能指定命令。具体是：提交的配置里不写命令；本机文件被 Git 跟踪、未被忽略或经过链接时不生效。未提交并被忽略的本机文件是这台机器的设置，可以指定命令（第 3 轮 S5 的澄清）；
  - 新命令查找 CLI 的方式与现有 doctor 相同；
  - Windows 上会先查当前目录，pi、node、git 与各个 CLI 都受影响。这是既有残余，在第二轮之后单独修、单独审。

### 1.2 本轮交付

1. **配置 v3 的五个键**：`runtimes`、`profiles`、`roles`、`presets`、`active_preset`（D1）。
   - 实现与校验在新模块 `scripts/kit_roles.py`；
   - 在 `kit_config` 的 KEYS 末尾登记；
   - 本机覆盖文件 `.agent/dispatch.local.json`（D3）。
2. **配置中心命令**：上位设计 8.1 的七项，加上 8.6 的审计（D7–D10）。
   - runtime：list / scan / add / remove / probe；
   - models；
   - profile：show / add / edit / remove；
   - role：show / set；
   - preset：list / show / save / use / diff / remove；
   - history、history show、rollback；
   - `config doctor`。
3. **配置锁、写入事务、历史与审计**（D7）：
   - 快照按内容寻址，存在 `.agent/config-history/`；
   - 审计写在 `.agent/audit/management.jsonl`；
   - 运行中切换要确认（D8）。
4. **内核**：
   - 合同 executor 的三类（D4）；
   - 按合同版本的记录：在任务锁内原子发布；prepare 用冻结后的字节解析，run 用记录（D5）；
   - 按 runtime 定位命令（D3）；
   - `attempt_executor` 统一读回；
   - 摘要写明执行模型的来源。
5. **规则、技能与文档**（D11）：
   - AGENTS.md；
   - plan-task、check-pi-env、review-pi；
   - README、CHANGELOG；
   - `gitignore.append.txt` 与本仓库的 `.gitignore`；
   - `.claude/settings.example.json`。

### 1.3 不在本轮

- **适配器层**：把 Pi 抽成适配器、接入 `scripts/codekit/adapters/`、generic 适配器，都是 P4 的事。
- **第二个 CLI 的无头调用**：P4，而且每次真实调用都要用户另行授权。
- **规划审核端与调度代理的无头调用**（P6、P5）：本轮只记录它们的绑定，并在就绪总览里报告。
- **审核与批准随配置失效**：P3 之前没有批准记录（D8）。
- **管理台与方案库**：管理台网页（M4）、用户级方案库（15.2 第 10 项的可选部分）。
- **其余配置键**：上位设计 6.3 的 `policies`、`feedback`、`logging`、`ui`。
- **信任边界**：只在可信位置查找程序（用户决定另立任务）。

## 2. 现状（承重事实）

### 2.1 合同里的执行模型

- **补默认值**：
  - `normalize_contract` 给 executor 补 thinking、tools、context_files，不补 provider、model（PD:1440-1450）；
  - `validate_contract` 先补默认值再校验（PD:1781）；
  - 加载 attempt 时还会再补一次（`load_attempt`，PD:3245-3248）。
- **校验**：
  - provider、model 可以缺省，也可以是 null，只在有值时才校验格式（PD:1814-1818）；
  - thinking 必须是已知的级别（PD:1819-1821）；
  - 旧合同不写模型也能通过校验，run 时由 `PI_EXEC_*` 补上。这是 `tests/test_legacy_cli.py:161`（LB-CONTRACT-003）钉住的合法输入。
- **Markdown**：
  - Identity 的 executor 行必须是 `provider/model · thinking <级别>` 的形式（`derive_contract_json`，PD:1652-1655，派生结果见 PD:1709-1714）；
  - JSON 写了 provider、model 时，Identity 必须写明它们与 thinking（PD:1939-1944）。
- **prepare**：
  - raw 合同的 provider 与 model **都为真值**时，prepare 提前调用 `resolve_executor`（PD:4212-4214）；
  - 遗留用例钉住了这一步的拒绝顺序：
    - 环境变量冲突退出 2，先于允许列表的退出 3（`tests/test_legacy_cli.py:802`）；
    - 允许列表未命中时，在分配 attempt 之前就拒绝（`tests/test_legacy_lifecycle.py:783`）；
    - 思考级别被固定、合同不符时拒绝（TD:534-540）。
  - 冻结合同字节、写 `plan.md` 与 `contract.json`，都在分配 attempt 之后（PD:4232-4252）；
  - 之后出错时标记 PREPARE_FAILED，并把错误重新包装成 `DispatchError`。包装时不带原来的退出码，所以都变成 3（PD:4276-4279、486）。
- **run**：
  - 再次解析执行模型（PD:4335）；
  - 领取之后写 `executor.json`（PD:4388）。
- **规则**（`resolve_executor`，PD:3282-3313）：
  - 以合同为准；
  - `PI_EXEC_*` 只补缺，与显式值冲突时报错；
  - `allowed_executors` 非空时检查。
- **读回点**：`executor.json` 不存在时，几处退回的值不同：
  - collect 退回 `contract["executor"]`（PD:4522）；
  - 摘要、branch、复审骨架、metrics 退回空对象（PD:3500、5967、6147、6818）。
- **attempt 与锁**：
  - `allocate_attempt` 只保证目录不重名（PD:3196-）；
  - 任务锁 `TaskLock` 是目录锁：等 30 秒，超过 300 秒视为持有者已崩溃并清除（PD:3163-3192）；现在只用在 run 的领取上（PD:4368）；
  - `write_json(…, exclusive=True)` 先以 `"x"` 打开再写入，不是原子发布（PD:530-535）。
- **“仍在运行”的判定**：`collect --recover` 用的是“状态为 RUNNING、COLLECTING，或者已领取的 PREPARED”（PD:4504）。

### 2.2 pi 的命令与就绪检查

- **`resolve_pi_command`**（PD:2293-2320）：
  - `PI_DISPATCH_PI_CMD` 优先；
  - 否则用 `shutil.which("pi")`；
  - Windows 上解析 npm 的 `.cmd` 包装。
- **Windows 上会先查当前目录**：`shutil.which` 与以裸名启动的子进程（例如 `git()`，PD:931）在 Windows 上都会先查当前目录。这是既有现象，信任边界的修复另立任务（1.1）。
- **`ensure_argv_safe`**（PD:2322-2328）：只防参数里的批处理特殊字符。
- **doctor**（PD:6955-7002）：
  - 运行 `--version` 与 `--help`，查找 claude、codex 也用 `shutil.which`；
  - 带 `--provider`、`--model` 时，再核对模型列表、`auth check --no-refresh` 与思考级别（PD:6972-7002）；
  - 不给子进程传过滤后的环境；
  - 钉住它的测试：TD:738-770、TD:2368-2375、`tests/test_legacy_cli.py:1039`。
- **预检**：`auth check` 不带 `--no-refresh`（PD:2591）。这是既有的不一致，本轮不改。
- **辅助函数**：`parse_help`（PD:2393-2404），`list_models_rows` / `list_models_empty_reason`（PD:2407-2429）。

### 2.3 配置管理器

- **KEYS 与校验**：
  - KEYS 在 KC:256-274，未知键是错误；
  - 每个注册的检查函数都会被无条件调用（KC:317-319）；
  - `split_path` 最多两层（KC:414-419）。
- **写入**：
  - `write_config` 用固定的临时文件名，再原子替换（KC:397-404）；
  - `write_checked` 整份校验后写入（KC:491-497）。
- **各入口都先读配置、在内存里改，再写**：
  - `config set` / `unset`（KC:502-538）；
  - `config init`，直接调用 `write_config`（KC:541-555）；
  - `config decisions`（KC:558-583）；
  - `kit_plugins` 的 enable / disable：传入 `new_config`，OSError 包成“写入失败”（`kit_plugins.py:628-640`）。
- **测试钉住的地方**：
  - `config show` 的第二个键必须是 `worktree_root`（TD:2749）；
  - `test_v270` 的临时仓库只拷 `kit_config.py` 与它原有的依赖（TD:2740-2743）。
- **`Repo.config()`**：宽松读取（PD:1150-1160）。

### 2.4 离线参考实现不接

- `scripts/codekit/config_profiles.py` 与本轮的形状不兼容：
  - v2 的角色名（CP:26）；
  - `schema_version` 2；
  - `credential_refs`。

  只有两个测试文件导入它。
- `scripts/codekit/adapters/` 的准入模型要求只读（调查摘要第 1 条）。

### 2.5 环境与凭据

- **`child_env`**（PD:599-617）：
  - 移除默认列表与 `env_remove` 里的变量；
  - `env_keep` 可以把名字留下；
  - 名字按大写比较，空值原样保留。
- **决策模型的 `Session`**：缺省读 `os.environ`（`codekit/decisions.py:672`；PD:3735）。
- **凭据库的 `describe`**：会读取凭据库（`codekit/secrets.py:306`、`366`）。
- **凭据形状的规则**：
  - `RELEASE_PATTERNS["api key"]`（PD:7314-7316）；
  - `_SECRET_KEY_RE` 与 `_SECRET_TOKEN_RE`（PD:2433-2439）。

### 2.6 忽略规则、安装与测试接线

- 本仓库 `.gitignore` 忽略 `.agent/runs/` 与 `.agent/baseline/`。
- `kit_install` 把 `gitignore.append.txt` 追加进目标仓库的 `.gitignore`（`kit_install.py:63`）。
- 主工作区指纹不含被忽略的文件（PD:1058-1083）。
- `KIT_LOADED_FILES`（PD:96-101）决定两件事：受保护，以及随 kit 发放（`kit_install.py:197`）。
- task 目录里的文件不会被当成 attempt：
  - 调度器只列子目录，并按 `ATTEMPT_DIR_RE` 识别（PD:3138-3143、4170）；
  - `kit_logs` 跳过名字不符的项（`kit_logs.py:202-205`）。
- 端到端测试的临时仓库只拷 `pi_dispatch.py` 与 `dispatch-pi.sh`（TD:196）。
- 遗留单元测试分两种：
  - 一种读锁定的历史源码（`tests/legacy_harness.py:203`、`266`）；
  - 一种是 CLI 用例，拷贝当前脚本（`tests/legacy_harness.py:1445`）。

### 2.7 规则与技能里写死的执行模型

- AGENTS.md:
  - 87-89：“更换模型或思考级别需要用户同意，并写进新合同”；
  - 103：改配置要征得用户同意。
- plan-task:
  - `contract-template.md:15`；
  - `SKILL.md:150`；
  - `contract-guide.md` 的第四节与第 192 行。

## 3. 决策与理由

### D1 配置形状

在 `.agent/dispatch.config.json` 增加五个可选键，形状取自上位设计 6.3：

```json
{
  "runtimes": {"pi": {"adapter": "pi"}},
  "profiles": {
    "exec-step": {"runtime": "pi", "model": {"provider": "bb", "id": "step-5-preview"},
                  "options": {"thinking": "high"}, "credential_env": []}
  },
  "roles": {
    "planning_review": {"mode": "interactive_host", "host": "claude-code"},
    "contract": {"mode": "manual"},
    "execution": {"mode": "headless", "profile": "exec-step"},
    "scheduler_agent": {"mode": "disabled"}
  },
  "presets": {
    "economy": {"description": "执行端用低价模型", "roles": {"execution": {"mode": "headless", "profile": "exec-step"}}}
  },
  "active_preset": "economy"
}
```

**通用规则**：

- **ID**：沿用 `TASK_ID_RE`（PD:62）。
- **严格形状**：每个对象只接受下面列出的键；下划线开头的是说明键。

**各键的规则**：

- **`runtimes.<id>`**：只有 `adapter` 一个键，值取 D2 表中的适配器。不能写命令或路径（D3）。
- **`profiles.<id>`**：
  - `runtime`：必须已登记；
  - `model`：`{provider, id}`，两项都要符合 `MODEL_TOKEN_RE`，且不命中 `PLACEHOLDER_RE`（PD:65、67）；
  - `options`：pi 只接受 `thinking`，取值在 `FALLBACK_THINKING_LEVELS` 里（PD:74），不写时按 high；其他适配器的 options 必须为空；
  - `credential_env`：环境变量名的列表，用 `env_remove` 的同一个检查（KC:131-136）。
- **`roles`**：只有四个角色。各角色允许的模式取自上位设计 6.3：

  | 角色 | 允许的模式 |
  |---|---|
  | planning_review | `interactive_host`（`host` 为 claude-code 或 codex）、`headless` |
  | contract | `manual`、`headless` |
  | execution | `headless` |
  | scheduler_agent | `disabled`、`headless`（可带 `cadence_seconds`，整数，至少 60） |

  - `headless` 必须带已登记的 `profile`；
  - 没写的角色取默认值：planning_review 是 `interactive_host`（宿主未声明），contract 是 `manual`，execution 由合同决定，scheduler_agent 是 `disabled`。
- **`presets.<名>`**：
  - `description` 可选；
  - `roles` 至少写一个角色，规则同上；
  - 方案只覆盖它列出的角色。
- **`active_preset`**：必须是已有的方案名。

**凭据**：五个键里所有的键与字符串，都用 D7 的规则检查，命中就报错。规则包括对 schema 字段路径的豁免。

**接入 `kit_config`**：

- 五个键追加在 KEYS 末尾；
- 检查函数在键缺省时立即返回，键存在时才惰性导入 `kit_roles`（D12）。

**不加 `schema_version`**：五个键都缺省时，等价于 2.10 的兼容预设（上位设计 11 节）。

**允许列表沿用 `allowed_executors`**（PD:3302-3312）：不新增 `policies.allowed_models`。

### D2 适配器登记

适配器是 `kit_roles` 里的一张静态表：

| 适配器 | 程序名 | 本轮接通的无头角色 | 交互式宿主 | 列模型 | 登录就绪 | options |
|---|---|---|---|---|---|---|
| pi | `pi` | execution、contract | 否 | `pi --list-models` | `pi auth check --no-refresh` | thinking |
| claude-code | `claude` | 无 | planning_review | 否 | 否 | 无 |
| codex | `codex` | 无 | planning_review | 否 | 否 | 无 |
| opencode | `opencode` | 无 | 否 | 否 | 否 | 无 |

**绑定到未接通的组合**：这是合法配置，可以提前登记。出现时会：

- `config role set` 与 `preset use` 打 WARN；
- `config doctor` 报未就绪；
- prepare 拒绝（D6）。

**为什么用静态表**：接入一个 CLI 要先实测（上位设计 7.3）。

### D3 命令路径（本轮的保证与既有残余）

**本轮保证**：提交进仓库的内容，不能指定会被运行的命令。未提交并被忽略的本机文件是这台机器的设置，可以指定命令（第 3 轮 S5 的澄清）。具体有三条：

- **提交的配置不写命令**：`runtimes.<id>` 只写 adapter。原因有两个：
  - 配置随仓库分发；
  - 本机路径会被 release-check 的家目录规则报出（PD:7317-7318）。
- **本机文件 `.agent/dispatch.local.json`**：
  - 只接受 `{"runtimes": {"<id>": {"command": ["<程序>", "<参数>", …]}}}` 这一种形状；
  - 读写它之前做三项检查，任一不满足就报一行 ERROR、不使用它：
    1. 不被 Git 跟踪（`git ls-files --error-unmatch` 失败）；
    2. 已被忽略（`git check-ignore` 成功）；
    3. 从仓库根到它的每一级都不是链接（`first_link_component`）。

    这样，把本机文件强行提交进仓库，也不会让它生效（r1-B1）。
  - 文件里出现提交的配置中没登记的 runtime ID 时，打 WARN；
  - 读写它的代码只在 `kit_roles` 里。
- **执行之前**，本机文件给出的命令过一遍 `ensure_argv_safe`。

**命令的解析顺序**（只用于按角色的合同与配置中心）：

1. `PI_DISPATCH_PI_CMD`（仅 pi）。这是本机的环境变量，不来自仓库。
2. 本机文件里该 runtime 的 `command`。
3. PATH 上的程序名。pi 沿用 `resolve_pi_command`，其他适配器用 `shutil.which`。

**写死合同与旧合同**：不引用 runtime，pi 的命令照 2.10 解析，不读本机文件。

**探测**：

| 命令 | 运行什么 |
|---|---|
| scan | 只运行 `--version` |
| probe | 运行 `--version`；pi 另加 `--help` |
| models | 运行 `--list-models` |
| `config doctor` | 见 D10 |

- 探测的环境用 `child_env(config)`。

**既有残余**（用户决定另立任务）：查找程序沿用 `shutil.which`、`resolve_pi_command` 与以裸名启动的 `git()`。在 Windows 上，它们会先查当前目录。所以：

- 在不可信仓库的根目录运行任何调度器命令，包括已有的 doctor 和本轮的新命令，都可能执行仓库根下同名的程序；
- 本轮不扩大也不修复这个面；
- 新命令与现有 doctor 口径相同。

### D4 合同的三类 executor（用户决定：绑定为准）

按 raw 合同分类。raw 指 JSON 解析之后、`normalize_contract` 补默认值之前的合同：

| 类别 | raw executor | 执行模型 | 绑定 |
|---|---|---|---|
| 按角色（新） | 有 `role`（`execution` 或 `contract`），provider、model、thinking 三个键都不出现 | 该角色的 headless 绑定；同一版本有记录时用记录（D5） | 首次建立记录时必须有效 |
| 写死（2.10） | `raw.get("provider")` 与 `raw.get("model")` 都为真值，与 PD:4213 的条件相同 | 合同 | 只比较，打 NOTE |
| 旧合同（2.10） | 其余情况，包括两项都是 null、只写了其中之一、只写了 thinking | 2.10 的规则 | 从不读 |

**混用检查**：

- 有 `role`，又出现 provider、model、thinking 任何一个键（哪怕值是 null），validate 报错；
- 判断只看 raw。

**按角色**：

- provider、model 取自 profile.model；thinking 取 profile.options.thinking，缺省 high；
- `PI_EXEC_*` 与解析结果不同时报错；
- contract 角色是 `manual`，而合同写了 `role:contract`：首次建立记录时报错。

**写死**：

- prepare 的提前解析与拒绝顺序原样保留（2.1）；
- 这些检查都通过之后，若配置了 execution 绑定，且它的 provider、model、thinking 有任何一项与合同不同，打 NOTE，并在 meta 里写 `executor_binding_note`；
- 比较只读配置，不运行 CLI，从不阻塞。

**旧合同**：行为与 2.10 完全相同。

**Markdown**：

- `- executor: role:execution` 或 `role:contract`，与 JSON 的 `executor.role` 必须一致，两边都要写；
- 其他写法与派生结果不变。

**validate**：按角色写的合同，既找不到绑定、也没有版本记录时，打 WARN。

**planner-v2 合同**：规则不变，本轮不支持按角色写。

### D5 按合同版本的记录（不覆盖的原子发布）

**记录文件**：`.agent/runs/<task-id>/binding-v<N>.json`，每个按角色写的合同版本一份。字段：

- 角色：`role`、`profile`、`runtime`、`adapter`、`active_preset`；
- 模型：`provider`、`model`、`thinking`；
- 来历：`config_sha256`（解析时配置文件字节的哈希）、`contract_json_sha256`（冻结合同的哈希）、`created_at`、`created_by_attempt`。

**发布**：由 PD 新增的 `publish_new(path, data)` 完成，原子发布，且从不覆盖已有文件。

- **步骤**：
  1. 在同一目录以 O_EXCL 新建独立的临时文件 `binding-v<N>.json.<随机>.tmp`，写入全部字节；
  2. 以“目标存在就失败”的方式换成正式文件：Windows 用 `os.rename`；POSIX 用 `os.link`，成功后删除临时文件；
  3. 目标已存在时返回 False，并删除临时文件。
  4. 文件系统不支持这种发布（例如 POSIX 上不能建硬链接）时报错，不退回会覆盖的写法：抛 `BindingRecordError`（EXIT_BLOCKED），提示“`.agent/runs` 所在的文件系统不支持不覆盖的原子发布”。
- **为什么这样就够了**：
  - 正式文件只能从“不存在”变成“完整”，永远不会被替换；
  - 任何持有者，包括锁被清除后恢复的旧持有者，发布失败后都读取并采用已有记录，所以同一版本只有一个模型（r3-B1）。
- **任务锁**：发布仍在 `TaskLock(repo, task_id)` 里进行，与 run 的领取共用（PD:3163-3192），只用来减少争用。唯一性不依赖它，它的行为不变。
- **崩溃**：可能留下临时文件，读取时忽略它。
- **记录已存在时**：读出来，检查三项，任一不满足就拒绝，不自动修复：
  - 必须是 JSON 对象，字段齐全，类型都对；
  - 从仓库根查起，路径上没有链接：`first_link_component(repo.root, ".agent/runs/<task>/binding-v<N>.json")`，覆盖 `.agent`、`runs`、task 目录与记录本身。`first_link_component` 不查 root 本身，所以不能从 runs 根查起（r3-S3）；
  - 损坏或不符时，抛 `BindingRecordError`（EXIT_DRIFT），提示“版本记录无效：…；确认后删除它，或出新版本合同”。

**prepare 的顺序**（只针对按角色的合同）：

1. 读一次配置字节，从中得到 dict 与哈希。
2. 预检，在分配 attempt 之前做，失败时不留 attempt：
   - **已有记录**：校验记录本身，以它为准。当前配置只用来提示差异；当前的绑定被删了或未接通，都不阻塞。
   - **没有记录**：当前绑定必须有效，即存在、模式是 headless、适配器已接通。
   - 两种情况下，记录或当前绑定解析出的模型都要过 `allowed_executors`，并检查与 `PI_EXEC_*` 是否冲突，这与写死合同的提前检查相同。
3. 分配 attempt，冻结合同字节（现有流程，PD:4232-4252）。
4. 发布或读取记录（r4-S1）：
   - **已有记录**：读取，完整校验后直接采用，不解析当前配置。当前绑定被删了或未接通，都不影响这一步。
   - **没有记录**：用冻结后的 raw 合同与第 1 步的配置字节构造候选记录，然后 `publish_new`。返回 False，说明别的 prepare 已经抢先发布：重新读取胜者，并完整校验后采用。
   - **最后统一检查选定的记录**：
     - 冻结合同的哈希与记录不符，抛 `BindingRecordError`；
     - 重做第 2 步的两项检查（r3-S1）：`allowed_executors`，以及与 `PI_EXEC_*` 是否冲突。失败时抛 `BindingRecordError`，允许列表的问题退出 3，环境变量冲突退出 2。
   - `BindingRecordError` 是 `DispatchError` 的子类，带自己的退出码。prepare 的包装（PD:4276-4279）遇到它时，先记 PREPARE_FAILED，再原样重新抛出，退出码不变；其他异常的包装不变（r2-S2）。
5. 在 `meta.json` 的 `executor_binding` 写入最终记录的完整副本。

记录不随 PREPARE_FAILED 的 attempt 清理：它记下的是这个合同版本的决定，与哪个 attempt 成败无关。

**run**：

- **是否核验，由冻结合同决定，不看 meta 里有没有字段**：`verify_inputs`（PD:3251-）读 attempt 的 `contract.json`（这份字节已由现有的哈希核对锁定），按 D4 的 raw 分类判断。
  - 按角色写的合同缺少 `executor_binding`，本身就是 G0 失败（r3-S3）。
  - 有 `executor_binding` 时，做三项核对，任一不符就以 G0 拒绝：
    1. 记录的路径由 meta 的 task_id 与 plan_version 推出，不读 meta 里写的路径；
    2. 从仓库根查起，路径上没有链接；
    3. 记录的全部字段与 meta 中的副本逐项相同，且 `contract_json_sha256` 与 meta 的 `contract_json_sha256` 一致。
- 执行模型的 provider、model、thinking 取自记录，tools、context_files 取自合同。
- 再检查一次 `allowed_executors` 与 `PI_EXEC_*` 的冲突。
- pi 的命令按记录里的 runtime 解析（D3）。

**`executor.json` 的形状不变**。

**读回收口**：PD 新增 `attempt_executor(run_dir, contract, fallback)`，按以下顺序取值：

1. `executor.json`；
2. meta 里 `executor_binding` 的模型三项，加上合同的 tools 与 context_files；
3. 调用处原来的后备值。

PD:3500、4522、5967、6147、6818 五处都改用它。

**摘要的“执行模型来源”**：

- 角色绑定：写 profile、runtime、方案、配置哈希的前 12 位，以及记录路径；
- 合同写死：与当时的绑定不同时，写明差异；
- 合同加 `PI_EXEC_*`。

### D6 拒绝与退出码

| 情形 | 退出码 |
|---|---|
| 首次建立记录时没有绑定、模式不是 headless、与 manual 冲突，或者写法混用 | `EXIT_USAGE` |
| 首次建立记录时，绑定指向本轮未接通的组合 | `EXIT_BLOCKED`（PD:3308） |
| 版本记录无效，或冻结合同与记录不符 | `EXIT_DRIFT` |

prepare 不运行任何 CLI。

### D7 配置锁、写入事务、历史与审计

**配置锁**（`ConfigLock`，在 kit_config 里）：

- **位置**：`.agent/.config.lock/`，是一个目录锁，`mkdir` 成功就算拿到。里面的 `owner.json` 记录持有者：pid、主机名、128 位随机令牌、创建时间。
- **从不自动抢占**（r3-B1）：
  - 锁被占用时最多等 30 秒，之后报错，退出 1；
  - 报错写明持有者的 pid、主机、持有时长，以及 `pid_alive`（PD:905）的判断：仍在运行、已退出，或无法判断；
  - 提示“确认没有别的写配置的命令在运行后，删除该目录再重试”。
  - 持有者已经退出时也不自动清除：自动清锁总有“两个等待者同时清、清掉了刚建好的新锁”这类交错，而写配置崩溃本来就罕见。
- **释放**：先读 `owner.json`，令牌与自己的一致才删除目录。释放检查时令牌不同，就不动它。
  - 检查与删除之间仍有窗口：在这段时间里人工删锁、别人又重建，这把新锁还是会被删掉。
  - 这属于下面“人工删除仍被挂起的进程的锁”的残余（r4-N1）。
- **为什么不复用 `TaskLock`**：`TaskLock` 超过 300 秒就按年龄清除，退出时也不核对所有权（PD:3184、3192）。对配置写入来说，这会让被挂起的旧持有者恢复后继续写。`TaskLock` 本身不改，它保护的版本记录已经不靠锁保证唯一（D5）。
- **残余**：人工删除了一个其实只是被挂起的进程的锁，那个进程恢复后仍会写入。删除之前要按报错里的 pid 确认它已经退出。
- **读改写都在锁内**：所有写配置的入口都在锁内完成“读当前配置 → 在内存里改 → 校验 → 记历史与审计 → 替换”。kit_config 提供上下文管理器 `config_transaction(repo, action, target)`：
  - 持锁读入配置，交给调用方修改；
  - 退出时提交。
- 下列入口全部改用它：
  - `config set`、`config unset`、`config init`、`config decisions`；
  - `kit_plugins` 的 enable / disable；
  - kit_roles 的各条写命令；
  - `config rollback`。
- dry-run 与没有变化的写入同样在锁内读取，这样得出的结论与真正写入时一致；但它们一条记录也不写（见下面的步骤）。
- **例外**：配置不存在时，`kit_install` 会写入示例配置（`kit_install.py:395-398`）。
  - 这是安装动作，不经过锁与事务。
  - 写入改用 `publish_new`，不覆盖（r3-S4）。检查之后、写入之前，配置若被配置中心建好了，安装就不覆盖它，那一行显示“已存在，未覆盖”。
  - 之后第一次经配置中心写入时，按下面的第 4 步记一条基线。

**快照**：

- 按内容寻址：`.agent/config-history/<sha256>.json`，存原始字节，已存在就不重写。
- 存之前做凭据检查，命中就不存内容，只记哈希与原因：
  - 键名用 `_SECRET_KEY_RE`，值为空的不算；
  - 字符串值用 `RELEASE_PATTERNS["api key"]` 与 `_SECRET_TOKEN_RE`（PD:2433-2439、7314-7316）。
- 豁免只针对 schema 规定的字段路径：
  - `decisions.api_key_env`；
  - `profiles.<id>.credential_env`；
  - 顶层的 `env_remove` 与 `env_keep`。

  这些位置的值是合法的环境变量名或其列表时，不算可疑（r2-S4）。

**审计**：

- 文件：`.agent/audit/management.jsonl`，只追加，只在配置锁内写。追加前，若文件不以换行结尾，先补一个换行，让中断留下的半行单独成行。
- 记录有四种：

  | 记录 | 内容 |
  |---|---|
  | `observed` | 外部改动 |
  | `intent` | 事务开始 |
  | `commit` | 事务完成 |
  | `resolve` | 补判中断的事务 |

- **每条记录都带 `resource`**（r3-B2）：取值 `config`（`.agent/dispatch.config.json`）或 `local`（`.agent/dispatch.local.json`）。
  - 补判、“最后发布的 after”与外部改动的比较，都只在同一资源的记录之间进行；
  - 只有 `config` 存快照，`local` 只记哈希。

**一次写入 = 一个事务**（`txn` 是 128 位随机数）。全部步骤在配置锁内，写的是资源 R：

1. 读 R 的当前字节 P。文件不存在时，P 为空。
2. 调用方修改，然后整份校验。
   - 校验不过、dry-run，或新字节与 P 相同：**到此结束，一条记录也不写**（r3-S6）。
3. **补判 R 上中断的事务**：若 R 有 intent 没有终结记录，它一定属于一个已经中断的写入者。持锁者总会先写完自己的事务再放锁；锁又从不自动抢占，所以中断者不会再回来写。判断规则：
   - 当前哈希等于它的 after，判为已发布（`published`）；
   - 等于它的 before，判为未发布（`aborted`）；
   - 两者都不等，判为未知（`unknown`）。

   结果写成一条 `resolve` 记录，之后不再改判。

   **前提与残余**：
   - 写配置的进程都持锁，所以在没有锁外改动时，能改动 R 的只有那个中断者，这时判断是确定的。
   - 锁外改动（编辑器、git checkout）若恰好把 R 改成了 before 或 after 的字节，补判会与事实不符。这类改动本来就只能当作外部改动来记。
   - 人工删除仍被挂起的进程的锁，那个进程恢复后写的记录也会与补判冲突，见上面“配置锁”的残余。
   - T4 覆盖这些可观察的结果。
4. **R 的外部改动**：
   - **比较基准**：按日志顺序，取 R 上最后一条“已知内容”的哈希（r4-S3）。“已知内容”指两种记录：
     - 已发布事务的 after，包括补判为已发布的；
     - `observed` 记录的 after。
   - P 的哈希与基准不同，或者 R 还没有任何已知内容而 P 不为空时：
     - 追加一条 `observed` 记录，action 为 `external`；
     - R 是 `config` 时，存 P 的快照。

   有锁之后，日志顺序就是实际顺序，所以 git checkout 回旧内容也会被记下。

   基准里含 `observed`，所以同一份外部内容只记一次：这一步之后，若快照或 intent 写失败，重试时 P 等于刚记下的那条 observed，不会再记。校验失败、dry-run 与没有变化的尝试，在第 2 步就已结束，不会走到这里。
5. R 是 `config` 时，存新字节 N 的快照。
6. 追加 `intent` 记录：resource、txn、action、target、actor、confirmation，以及前后两份内容的哈希。写不进时，不替换，退出 1，提示“没有写入：审计写不进去”。
7. 在同一目录用 `mkstemp` 建独立的临时文件，写入 N，再 `os.replace`。
8. 追加 `commit` 记录，result 为 `published`。写不进时，退出 1，提示“已写入，但审计记录不全；下一次写入会补判”。
9. 放锁。

**读取审计**（history 与补判）：

- 末尾的半行，或解析不了的行：列出行号，标“损坏的记录”，不中断。
- 只读的 `config history` 不持锁：
  - 看到没有终结记录的 intent，标“进行中或已中断”；
  - 它不补判。

**history**：

- `config history` 按 intent 在日志中的顺序编号，两种资源共用一套编号。编号稳定，因为日志只追加。每条给出：
  - 资源（`config` 或 `local`）、时间、动作、目标、执行者、确认方式；
  - 终结状态：已发布 / 未发布 / 未知 / 进行中或已中断；
  - 变化的键：比较前后两份快照，列出顶层键与子键。快照没存内容时，按资源写不同的说明（r4-N2）：
    - `config` 资源：写“疑似凭据，未存内容”；
    - `local` 资源：写“本机配置只存哈希”。
- `config history show <编号>`：
  - `config` 资源给出逐键差异，含键路径、旧值、新值；
  - `local` 资源只给出前后两份内容的哈希，没有逐键差异。
- `observed` 与 `resolve` 记录附在相关的位置，不占编号。

**rollback `<编号>`**：

1. 只接受 `config` 资源上已发布事务的 after 快照；没存内容的拒绝。
2. 解析成对象，整份校验。
3. 在新的事务里原样写回这份字节，action 为 `config.rollback`。

写完之后，文件与快照逐字节相同。

已发布事务的 after 快照，都是 `json.dumps(…, ensure_ascii=False, indent=2)` 的输出（LF、末尾有换行、非 ASCII 原样），或者 rollback 原样写回的这种字节。所以 T1 的逐字节比较覆盖的是 Unicode 与这种格式；CRLF、没有末尾换行这类字节，只会出现在外部改动的 observed 快照里，而那种快照不能作为 rollback 的目标。这一点是实现时核对出的事实。

**actor**：

- 取环境变量 `CODEKIT_ACTOR`，值为 `user` 或 `agent:<角色>`；没设时记 `undeclared`；值不合法时打 WARN，也记 `undeclared`。
- 这是自声明，不是认证（上位设计 8.6）。

**错误的透传**：

- `kit_plugins` 遇到“已写入但审计记录不全”时原样透传，不包成“写入失败”（`kit_plugins.py:634-635`）。
- 本机文件的写入走同样的锁与事务（resource 为 `local`），但不存快照，因为里面是本机路径。审计只记前后两份的哈希。

**不提交**：

- 以下几项加入忽略规则（D11）：
  - `.agent/config-history/`
  - `.agent/audit/`
  - `.agent/.config.lock/`

### D8 方案与切换

**方案命令**：

- `preset save <名> [--description …] [--roles a,b] [--force]`：
  - 把当前 roles 里列出的角色存为方案；不带 `--roles` 时，存全部已写出的角色；
  - 同名方案已存在时，要加 `--force`。
- `preset use <名>`：
  - 只覆盖方案里列出的角色，并写入 `active_preset`；
  - 写入之前列出影响：
    - 运行中与已准备的 attempt 不受影响；
    - 还没有版本记录的、按角色写的合同版本，会用新绑定；
    - 已有记录的版本，沿用各自的记录。
- 单独改了某个角色之后：`role set` 不清除 `active_preset`；`preset show <当前方案>` 与 `role show` 会标出不一致的角色。
- `preset diff A B`：逐个角色比较。
- `preset list`、`preset show`。
- `preset remove <名>`：拒绝删除当前在用的方案。上位设计 8.5 没有列 remove；不加的话，方案只增不减（10 节第 4 项）。

**运行中切换要确认**（上位设计 8.1）：

- **何时触发**：一次写入改变了 execution 或 contract 的生效绑定，并且有 attempt 正在运行。
  - 生效绑定按每个角色的元组比较：mode、profile、runtime、adapter、provider、model、thinking，任何一项变化都算（r2-B6）；
  - 写入前后两份配置中，任一份有 v3 键，就计算生效绑定；两份都没有时，两边都是“由合同决定”，无需计算；
  - “正在运行”沿用 `collect --recover` 的判定（PD:4504）：状态为 RUNNING、COLLECTING，或者已领取的 PREPARED。已经结束的 attempt 留着 `claim/` 也不算（r2-S5）。
- **判定的时刻**（r3-S2、r4-S2）：
  - 判定在配置锁内、替换文件之前做。
  - run 领取 attempt 用的是另一把锁（任务锁，PD:4368），所以判定与替换之间仍可能有 attempt 被领取。
- **承诺的范围**：做状态检查时发现有在运行的 attempt，才要求确认；检查之后才领取的 attempt，不纳入这次提醒。这是一个提醒，不是一致性保障。
- **被漏掉的 attempt 照样不受影响**：它的执行模型早在 prepare 时就已固定，来源是版本记录或合同，不会因为这次写入而变。
- **与上位设计的关系**：8.1 有两条要求。“运行中的 attempt 不受切换影响”由 D5 的版本记录保证；“运行时切换要确认”按上面的范围实现，时间差写明在这里。
- **要求**：带 `--yes`。没带就拒绝，退出 1，并列出这些 attempt；带了，审计记 `confirmation: flag`。其余写入记 `none`。
- **适用范围**：所有写入口都适用，因为判断依据是生效绑定有没有变化，与用的是哪条命令无关。
- **影响范围**：只影响尚未建立版本记录的合同版本（r3-N1）。已经建立记录的版本，之后的 attempt 也沿用记录（D5）。

**批准失效**：P3 之前没有批准记录。`invalidated_approvals` 固定为空列表，note 注明这一点。

### D9 凭据与环境

- **可用的判定**：一个 `credential_env` 名字算可用，要满足两条：
  - 它出现在 `child_env(config)` 的结果里，名字按大写比较；
  - 值非空（r2-S6）。
- **只判断，不输出**：配置中心不返回、不输出、不记录凭据值。
- **共用检查**（闸二第 2 片第 3 轮）：PD 的 `secret_config_error(config, key)`。
  - 判定（`secret_like_paths`）：键名像凭据且值非空、字符串有令牌的形状、键名本身有令牌的形状；最后一种在位置里写成“（疑似凭据的键名）”，不往下找。
  - 配置中心拿某个键的取值去校验、摘要、列表之前都先过它，命中时只报位置，不再跑会回显取值的检查：`validate_config`、`config show`（各键的取值与决策摘要）、plugins 的五个命令（经 `plugins_section_error`）、`secret set --verify`、`kit_roles.check_key`。
  - 记录：快照存内容之前查（D7）；审计的 `target` 有令牌形状时记成“（含疑似凭据，不显示）”。
  - 不在此列：命令行参数在报错里的回显（用户自己输入，已在终端里）。内核读配置不经过配置中心：doctor 的输出经 `redact_obj`，其中的文本脱敏与共用检查认得同样的令牌形状；第 3 步首次建立版本记录之前，角色绑定所在的键先过 `kit_roles.check_key`，不过就拒绝（EXIT_USAGE），取值不进记录与提示。
- **凭据库**：报告凭据库在哪一层，只作说明，不算就绪。本轮不定义从凭据库注入环境变量的链路。

### D10 `config doctor`（就绪总览）

**每个角色一行**，列出：

- 模式、profile、runtime、适配器；
- 命令及其来源（环境变量、本机文件或 PATH）；
- 版本；
- 模型是否在列表中；
- 登录是否就绪；
- 思考级别是否受支持；
- 是否在 `allowed_executors` 中；
- 凭据可用性（D9）；
- 接通状态。

**探测怎么跑**：

- 版本与 `--help` 按 runtime 缓存；
- 模型列表（`--list-models <模型>`）与 `auth check --no-refresh` 按（runtime, provider, model）分别运行。

**与 doctor 共用一个函数**：

- 把 `cmd_doctor` 中列模型、`auth check` 与思考级别的那一段（PD:6972-7002）抽成共用函数，显式接收环境参数：
  - 旧 doctor 传 `None`，照旧继承环境；
  - `config doctor` 传 `child_env(config)`。
- 旧 doctor 的参数条件、输出与退出码都不变。

**约束**：

- 不调用模型。
- 退出码：全部就绪为 0；有未就绪为 1；用法错误为 2。

### D11 忽略规则与规则文件

**忽略规则**：`gitignore.append.txt` 与本仓库的 `.gitignore` 追加四条，`kit_install update` 会补给已安装的仓库：

- `.agent/dispatch.local.json`
- `.agent/config-history/`
- `.agent/audit/`
- `.agent/.config.lock/`

**主工作区指纹**：因为这几项都被忽略，指纹不受影响（PD:1058-1083），不用加进 `planner_paths`。写配置时，若历史或审计的目录没有被忽略，打 WARN，提示运行 `kit_install update`。本机文件没有被忽略时，既不读也不写（D3）。

**AGENTS.md 的“必须遵守”**：执行模型一条改为三层：

- 执行模型由角色绑定决定（`config role show`）。新合同的 Identity 写 `role:execution`，不写 provider 与 model；合同写死了模型时以合同为准。
- provider 与 model 必须与 `.agent/environment.md` 和 `pi --list-models` 的精确 ID 一致。
- 以下改动要用户同意：
  - 改角色绑定或方案（`config role set`、`config preset use`、`config rollback`）；
  - 改写死的模型；
  - 改思考级别。

  规划端代为写配置时，设 `CODEKIT_ACTOR=agent:planning_review`。写死的模型要换，就出新版本合同。

**AGENTS.md 的“Codex 的沙箱”一节**：

| 命令 | 读写性质 |
|---|---|
| list / show / history / diff | 只读 |
| scan / probe / models / doctor | 运行本机 CLI 的只读命令；pi 列模型在沙箱里可能失败，与 doctor 相同 |
| add / edit / remove / set / save / use / rollback | 只写工作区：配置、本机文件、历史、审计与锁 |

**技能**：

- plan-task 的模板给出两种写法；
- contract-guide 的第四节与第九节；
- `SKILL.md:150`；
- check-pi-env 第 8 步改用 config 命令；
- review-pi 核对“执行模型来源”与版本记录；
- 改完运行 `sync-adapters`。

### D12 模块与接入

| 位置 | 内容 |
|---|---|
| `scripts/kit_roles.py`（新） | v3 的解析与校验（D1）、适配器表（D2）、本机文件（D3）、各条命令、给内核的 `resolve_role_executor` 与记录的校验 |
| `kit_config` | `ConfigLock`、`config_transaction`、快照与审计（D7）；运行中切换的确认（D8）。这里经惰性导入 kit_roles 计算生效绑定，写入前后两份配置都没有 v3 键时不导入 |
| PD | `publish_new`（版本记录与 `kit_install` 共用）、`attempt_executor`、版本记录的发布与读取、prepare 与 run 的接线、`BindingRecordError`；`TaskLock` 不改 |

**发放与保护**：`KIT_LOADED_FILES` 加入 `kit_roles.py`。

**惰性导入**：

- 五个键都不存在、合同也不是按角色写时，`kit_config` 与 PD 都不导入 kit_roles。只拷了旧文件的临时仓库照常工作（TD:196、2740-2743）。
- 需要它却缺文件时，报一行 ERROR，不冒堆栈。

**给内核的接口不抛异常**：

- **原因**：调度器以 `__main__` 运行时，`kit_roles` 的 `import pi_dispatch` 会再载入一份 PD（`kit_config` 也是这样，PD:7157-7163 → KC:44），于是两边的 `DispatchError` 不是同一个类。
- **返回值**：`(值, 错误)`，错误是 `None`，或 `{"message": …, "code": 2 | 3 | 4}`。
- **边界转换**：kit_roles 在边界处，把自己那份模块的 `pd.DispatchError`（取 code）、OSError、ValueError 转成错误返回值。
- **测试位置**：内核的场景放在以子进程运行的 `tests/test_dispatch.py` 里。

**`config` 的转发不变**（PD:7157-7163）：

- 新子命令由 `kit_config.build_parser` 登记，转交 `kit_roles`；
- `--yes` 是每个写入类子命令自己的选项，例如 `config set … --yes`、`config rollback 3 --yes`。
  - 实现时由“全局选项”改为子命令选项。
  - 原因是 argparse 的全局选项必须写在子命令之前，`config --yes set …` 不顺手；子命令解析器的缺省值还会覆盖全局选项的值。

## 4. 接口

### 4.1 命令

| 命令 | 读写 | 说明 |
|---|---|---|
| `config runtime list [--json]` | 读 | 已登记的 runtime、适配器，以及命令的来源 |
| `config runtime scan [--add]` | 读；`--add` 写配置 | 在 PATH 上找 pi、claude、codex、opencode，只运行 `--version`；`--add` 把找到但未登记的，登记成与适配器同名的 runtime |
| `config runtime add <id> --adapter <a> [--command '<JSON 数组>'] [--force]` | 写；`--command` 写本机文件 | 改已有 runtime 的 adapter 时要 `--force` |
| `config runtime remove <id>` | 写 | 有 profile 引用时拒绝；同时删去本机文件里的条目 |
| `config runtime probe <id> [--json]` | 读 | 运行 `--version`；pi 另加 `--help`，报缺少的参数 |
| `config models <runtime> [--json]` | 读 | pi：运行 `pi --list-models`（不带过滤），列出表格并标出允许列表；其他适配器退出 1 |
| `config profile show [<id>] [--json]` | 读 | |
| `config profile add <id> --runtime <r> --model <provider/id> [--thinking <级别>] [--credential-env <名>]…` | 写 | 不运行 CLI |
| `config profile edit <id> [--model …] [--thinking …] [--credential-env …] [--runtime …]` | 写 | |
| `config profile remove <id>` | 写 | 有角色或方案引用时拒绝 |
| `config role show [--json]` | 读 | |
| `config role set <role> <profile>\|manual\|disabled\|interactive_host [--host <h>] [--cadence-seconds <n>]` | 写 | 未接通、不在允许列表时打 WARN |
| `config preset list / show <名> / save <名> … / use <名> / diff <A> <B> / remove <名>` | 见 D8 | |
| `config history [--json]`、`config history show <编号>` | 读 | 不持锁、不补判 |
| `config rollback <编号>` | 写 | |
| `config doctor [--json]` | 读；运行 CLI 的只读命令 | D10 |

- **退出码**：0 成功；1 是校验失败、未就绪、需要确认，或审计记录不全；2 是用法错误。配置锁被占用、等不到时报 ERROR，退出 1。
- **确认选项**：写入类子命令都接受 `--yes`（D12）。
- **环境变量**：`CODEKIT_ACTOR`。
- `config set` / `unset` 照常可以改这五个键，同样经过锁、事务与确认。

### 4.2 合同的 executor

| 类别 | JSON | Markdown Identity |
|---|---|---|
| 写死（2.10） | `{"provider": "bb", "model": "step-5-preview", "thinking": "high", …}` | `- executor: bb/step-5-preview · thinking high` |
| 按角色 | `{"role": "execution", "tools": […], "context_files": "project"}` | `- executor: role:execution` |
| 按角色（合同端） | `{"role": "contract", …}` | `- executor: role:contract` |
| 旧合同（2.10） | 其余情况，例如 `{"thinking": "high", "tools": […]}`，或 provider、model 都是 null | 不变 |

### 4.3 版本记录与 `meta.json`

```json
{"role": "execution", "profile": "exec-step", "runtime": "pi", "adapter": "pi", "active_preset": "economy",
 "provider": "bb", "model": "step-5-preview", "thinking": "high",
 "config_sha256": "<64 位十六进制>", "contract_json_sha256": "<64 位十六进制>",
 "created_at": "2026-10-18T09:00:00Z", "created_by_attempt": "attempt-001"}
```

`meta.json` 里的相关字段：

- `executor_binding`：记录的完整副本；
- `executor_binding_note`：只在写死合同与绑定不同时出现。

### 4.4 审计记录（每行一条）

```json
{"record_type": "management-audit", "schema_version": 1, "phase": "intent", "resource": "config", "txn": "<32 位十六进制>",
 "audit_id": "aud-<32 位十六进制>", "at": "2026-10-18T09:00:00Z", "actor": "agent:planning_review",
 "action": "preset.use", "target": "economy",
 "before_ref": {"kind": "config-snapshot", "sha256": "…", "stored": true},
 "after_ref": {"kind": "config-snapshot", "sha256": "…", "stored": true},
 "invalidated_approvals": [], "confirmation": "flag", "note": "P3 之前没有批准记录"}
```

- **每条记录都带 `resource`**：取值是 `config` 或 `local`，补判与比较都只在同一资源内进行（D7）。
- **`commit`**：只有 `phase`、`resource`、`txn`、`audit_id`、`at`、`result`，其中 result 为 `published`。
- **`resolve`**：`phase`、`resource`、`txn`（被补判的那个事务）、`audit_id`、`at`、`result`（`published` / `aborted` / `unknown`）。
- **`observed`**：`phase`、`resource`、`audit_id`、`at`、`action: "external"`、`after_ref`。
- **`local` 资源**：`before_ref` 与 `after_ref` 的 kind 是 `local-file`，`stored` 永远为 false。
- **action 的取值**：

| 范围 | action |
|---|---|
| 配置 | `config.set`、`config.unset`、`config.init`、`config.decisions`、`config.rollback` |
| runtime | `runtime.add`、`runtime.remove`、`runtime.local_command` |
| profile | `profile.add`、`profile.edit`、`profile.remove` |
| 角色 | `role.set` |
| 方案 | `preset.save`、`preset.use`、`preset.remove` |
| 插件 | `plugin.enable`、`plugin.disable` |

## 5. 执行方式

- **由规划端直接做**。不派 Pi，不调用任何模型；测试都用替身。
- **两项前置已单独提交**（§0.2 的“前置”）。
- **另一个小任务待提交**：第一轮的残余“运行时加载题库与 doctor、config show 的展示读之前也查链接”。实现与测试已经做完，放在单独的 worktree 里，闸一通过后、本轮动手之前单独提交。
- **实现顺序**：闸一通过后调整了第 3、4 步，把内核放在命令之前。
  - 理由一：`config set roles.*` 与 `profiles.*` 经事务层就能写，所以不等增删改命令做出来，就能端到端证明“切换绑定，下一次 prepare 就用它”。
  - 理由二：现有测试与遗留刻画大多钉在内核上，回归问题早暴露，代价更小。

  调整后的顺序：
  1. `ConfigLock`、`publish_new` 与 `config_transaction`、快照与审计，以及四条忽略规则；
  2. kit_roles 的解析与校验，以及 D8 的确认；
  3. 内核：D3、D4、D5；
  4. 配置中心的各条命令；
  5. 规则、技能与文档。

  进度逐项记在 `.agent/design/3.0-r2-实现进度.md`。

  每一步都跑相关测试；最后跑全量，并以脚本方式运行 `tests/test_dispatch.py`。

## 6. 刻意不做

- **适配器层**：
  - 把 Pi 抽成适配器；
  - 改 `pi_preflight`、事件解析，以及带 Pi 品牌的输出。
- **doctor 与预检的不一致**：两处在 `--no-refresh` 上不一致，本轮不统一。
- **离线参考实现**：不接入 `codekit/adapters/` 与 `codekit/config_profiles.py`。
- **无头调用**：第二个 CLI、规划审核端与调度代理，本轮都不做无头调用。
- **命令写进配置**：命令或路径不写进提交的配置。
- **批准失效**：留到 P3。
- **凭据注入**：不从凭据库向执行器注入环境变量。
- **方案库与管理台**：不做用户级方案库、方案的导入导出与管理台网页。
- **doctor 与 prepare**：不改 doctor 的输出；不在 prepare 里运行 CLI。
- **planner-v2 合同**：不支持按角色写。
- **信任边界**（用户决定另立任务）：只在可信位置查找程序。范围包括：
  - pi、node、git 与各个 CLI 在 Windows 上先查当前目录；
  - 最终程序与 npm 包装的目标；
  - UNC 别名。

## 7. 影响面清单

### 7.1 要改的

| 位置 | 改动 |
|---|---|
| `scripts/kit_roles.py`（新） | D1–D3，以及 D8 与 D10 的命令部分 |
| KC:256-274 | 五个键追加在 KEYS 末尾；检查函数在键缺省时立即返回 |
| KC:397-404、491-497 | `ConfigLock` 与 `config_transaction`：锁、按资源的补判与外部改动、快照、审计、独立临时文件 |
| `kit_install.py:395-398、414-416` | 示例配置改用 `publish_new` 写入，不覆盖已存在的配置 |
| KC:502-583 | set / unset / init / decisions 改用 `config_transaction` |
| KC:757-796 | 新子命令与全局 `--yes` |
| `kit_plugins.py:600-640` | enable / disable 改用 `config_transaction`；错误透传 |
| PD:96-101 | `KIT_LOADED_FILES` 加入 `kit_roles.py` |
| PD:1641-1714、1814-1828、1939-1944 | 三类合同的派生、校验与一致性检查 |
| PD:2293-2320 | `resolve_pi_command` 可传 runtime，按 D3 的顺序解析 |
| PD（新函数） | `publish_new`：不覆盖的原子发布（Windows `os.rename`，POSIX `os.link`） |
| PD:3251- | `verify_inputs` 核对版本记录 |
| PD:3282-3313 | 按角色时用记录，与 `PI_EXEC_*` 比较 |
| PD:4194-4290 | prepare：预检、在任务锁内发布记录、写 meta、写死合同之后的 NOTE；对 `BindingRecordError` 原样重新抛出 |
| PD:4334-4342 | run：用记录，按 runtime 解析命令 |
| PD:3500、4522、5967、6147、6818 | 改用 `attempt_executor` |
| PD:3497-3514 | 摘要的“执行模型来源” |
| PD:6972-7002 | 抽出 pi 的就绪检查，`doctor` 与 `config doctor` 共用 |
| `gitignore.append.txt`、`.gitignore` | 四条忽略规则 |
| AGENTS.md:57-60、87-89 | D11 |
| `.agents/skills/plan-task/`、`check-pi-env/`、`review-pi/` | D11，改完运行 `sync-adapters` |
| README、CHANGELOG、`.claude/settings.example.json` | |
| `tests/` | 第 9 节 |

### 7.2 刻意不改的

- `scripts/codekit/**`。
- `pi_preflight` 与事件解析。
- doctor 的输出。
- 已有的合同与证据。
- `allowed_executors` 的形状。
- 查找程序的方式（§6，信任边界）。

## 8. 上线顺序与回滚

- **兼容**：五个键都缺省时，写死合同与旧合同的行为都与 2.10 一致。仍有两处变化：
  - 写配置会留下历史与审计，并且要拿配置锁；
  - `config show` 多出新键的行。

  全量回归、遗留刻画用例与 `tests/test_dispatch.py` 的 404 项检查，都不改期望值。
- **回滚**：
  - 删掉五个键，就回到 2.10 的行为；
  - meta 中多出的字段与版本记录文件，旧版本会忽略；
  - 历史、审计目录与锁目录可以直接删除。
- **本仓库的配置**：本轮不改 `.agent/dispatch.config.json`（10 节第 1 项）。

## 9. 测试计划

针对本轮候选的测试，都运行当前代码，方式是子进程或进程内调用。锁定历史的遗留单元测试只证明历史实现的刻画没有变，不算本轮的证据。

### 9.1 配置（`tests/test_kit_roles.py`）

| 编号 | 场景 | 防的失败 |
|---|---|---|
| C1 | 各键的未知子键、类型错误、ID 不合法；校验失败时配置字节不变 | 坏配置被写入 |
| C2 | 模式与角色不匹配 | 绑定语义被绕过 |
| C3 | 悬空引用：runtime、profile、`active_preset` | |
| C4 | 敏感键名或凭据形状被拒绝；`credential_env` 里的合法名字通过 | 内联密钥；豁免缺失 |
| C5 | runtime 带 `command` 或其他键时报错 | 命令进了提交的配置 |
| C6 | 本机文件只接受 `runtimes.<id>.command`；未登记的 ID 打 WARN | |
| C7 | pi 的 thinking：非 high 的值与缺省值都能解析，非法值报错；其他适配器的 options 非空时报错 | |
| C8 | `credential_env` 的名字不合法 | |
| C9 | 在只拷了旧文件、没有 `kit_roles.py` 的同一个临时仓库里，`config show`、`validate`、`set`、`decisions`，以及 `plugins enable` / `disable` 都可用，输出与 2.10 一致（新键行除外） | 兼容被破坏（r1-B6） |

### 9.2 锁与写入事务（`tests/test_kit_config.py`）

| 编号 | 场景 | 防的失败 |
|---|---|---|
| T1 | 每次写入依次产生快照、intent、commit；rollback 之后与快照逐字节相同，包括 CRLF、没有末尾换行、Unicode 与空白排版 | 回滚复现不了原快照 |
| T2 | 外部改动：手改之后记 `observed`；git checkout 回历史上出现过的内容，同样记 `observed`；前态含 `"api_key": "opaque"` 或 `"_secret_env": "x"` 时只存哈希；含 `decisions.api_key_env`、`credential_env`、`env_remove` 的正常配置照常存 | 漏记外部改动（r2-B5）；豁免过宽（r2-S4） |
| T3 | intent 写不进时，不替换，退出 1 | 没有记录的替换 |
| T4 | 补判的结果：<br>① 替换之后、写 commit 之前中断：下一次写入记 `resolve: published`；<br>② 替换之前中断：记 `aborted`；<br>③ 中断之后，文件又被外部改成既非 before 也非 after 的字节：记 `unknown`；<br>④ 已声明的残余：外部改动恰好恢复成 before 或 after 时，补判结果与 D7 写明的一致；<br>补判之后再写入，旧的判定不变 | 补判反复改判（r2-B5） |
| T5 | 读改写：A 持锁期间，B 等待；B 读到的是 A 写入之后的配置。用两个进程测，替身让 A 停在第 6 步 | 丢更新（r2-B3） |
| T6 | 两个进程交替追加审计，都持锁，记录都完整；末尾有半行时补换行，读取时报“损坏的记录”的行号 | 追加互相覆盖（r2-B4） |
| T7 | init 的前态为空；decisions、`plugins enable` / `disable` 的动作；插件“审计记录不全”的错误原样透传；校验失败、dry-run 与没有变化的写入之后，审计文件与历史目录的字节都不变；先造出外部改动，以及一条没有终结记录的 intent，再做这三种尝试，日志仍逐字节不变（补判没有提前执行）；observed 写入之后 intent 失败，再重试，只有一条 observed | 有写入绕过历史；失败的尝试写了记录（r3-S6）；外部改动重复记录（r4-S3） |
| T8 | 配置锁：<br>① 被占用时等 30 秒，然后报错，写明 pid、主机，以及“仍在运行 / 已退出 / 无法判断”；<br>② 持有者已退出、锁目录很旧，也不自动清除；<br>③ 释放时令牌不符就不删目录。<br>另外：`CODEKIT_ACTOR` 的取值；audit_id 不重复；历史目录没被忽略时打 WARN | 抢占仍在运行的持有者；删掉别人的锁（r3-B1） |
| T9 | history 列出资源、变化的键、终结状态与稳定的编号；history show 给出逐键差异；只读的 history 看到进行中的事务时，标“进行中或已中断” | 历史没有差异；编号漂移 |
| T10 | 两种资源交替：<br>① 配置 → 本机文件 → 配置，第三次写入不误报外部改动；<br>② 本机文件替换之后、写 commit 之前中断：之后只写配置，不补判本机文件；下一次真正写本机文件时，才按本机文件的哈希补判 | 资源混淆（r3-B2、r4-N3） |
| T12 | `publish_new` 的各个分支：<br>① 目标不存在时发布成功；<br>② 目标已存在时返回 False，目标字节不变；<br>③ 已存在的目标即使是只读文件，也属于“目标已存在”：返回 False，字节不变。目录没有写权限，以及 POSIX 上不支持硬链接时，都报错：不返回 False，也不覆盖（实现时更正：第 4 稿把只读目标误归为报错）；<br>④ 跨卷时直接失败，不退回复制 | 把其他错误当成“别人已抢先发布”；退回覆盖的写法（r4-N3） |
| T11 | `kit_install`：检查“配置不存在”之后、写入之前，配置被建好了，安装不覆盖它，那一行显示“已存在，未覆盖”。用替身让安装停在两步之间 | 安装覆盖配置（r3-S4） |

### 9.3 配置中心命令（`tests/test_kit_roles.py`；CLI 用 PATH 上的替身，pi 用 `tests/stub_pi.py`）

| 编号 | 场景 | 防的失败 |
|---|---|---|
| M1 | scan 只运行 `--version`；`--add` 登记 | 探测运行了别的命令 |
| M2 | runtime add / remove：`--command` 只写本机文件；本机文件已被跟踪、没被忽略或经过链接时，读和写都拒绝；有引用时拒绝 remove；命令的优先级 | 命令进了提交的配置；提交的本机文件生效（r1-B1） |
| M3 | probe：pi 运行 `--version` 与 `--help`，非 pi 的适配器只运行 `--version`；models：pi 列出表格与允许列表的标记，非 pi 的适配器退出 1 | 探测规则与 D3 不一致（r3-N2） |
| M4 | profile add 写对字段；edit 只改指定的项；非法的 edit 不写；有引用时拒绝 remove | |
| M5 | role set 的各种模式；未接通时打 WARN；`config unset roles.execution` 回到“由合同决定” | |
| M6 | preset save / use / diff / remove | 方案覆盖了未列出的角色 |
| M7 | 运行中的确认：<br>① RUNNING、COLLECTING、已领取的 PREPARED 时，role set、preset use、profile edit、改 adapter 的 runtime add、rollback（包括回滚到没有 v3 键的配置）、通用 set 都要 `--yes`；<br>② 已经结束、但留着 `claim/` 的 attempt 不触发；<br>③ 不改变生效绑定的写入不触发 | 免确认的切换（r1-B7、r2-B6、S5） |
| M7b | 判定的时刻：替身让写入者停在“检查之后、替换之前”，这时另一个进程领取 attempt，写入者再继续。断言：<br>① 这次写入不要求确认，审计记 `confirmation: none`；<br>② 被领取的 attempt 用的仍是 prepare 时固定的执行模型 | 确认语义与 D8 不一致（r3-S2、r4-S2） |
| M8 | doctor：替身 pi 就绪、模型不在列表、auth 失败、未接通的适配器；共用 runtime 的两个 profile 分别判断；`credential_env` 被默认列表或 `env_remove` 移除、被 `env_keep` 保留、值为空；退出码 | 就绪误判（r1-S2、S3，r2-S6） |
| M9 | 不调用模型：替身记录 argv，成功与失败的分支里都没有提示类调用；profile add 不运行 CLI | |
| M10 | 旧 doctor 的输出、退出码与“继承环境”的语义不变 | |

### 9.4 内核（`tests/test_dispatch.py` 的新场景，替身 pi，子进程方式运行）

| 编号 | 场景 | 防的失败 |
|---|---|---|
| K1 | 写死合同、绑定不同：用合同的模型，打 NOTE；允许列表与环境变量冲突时的拒绝顺序不变 | 写死的合同被改（r1-B3） |
| K2 | 按角色加绑定：prepare 发布记录，run 的 argv 用记录里的模型 | |
| K3 | 同一版本的第二个 attempt，在改了绑定之后：沿用记录，打 NOTE | |
| K4 | 发布的唯一性：<br>① 两个进程同时首次 prepare 同一版本，替身让第一个停在临时文件写完、发布之前：第二个等任务锁，之后读到完整的记录，两个 attempt 的 meta 相同；<br>② 旧持有者恢复：任务锁被清除，别人已发布了记录 Y，A 再发布自己的 X 时 `publish_new` 返回 False，A 改用 Y；记录始终是 Y | 读到半份记录（r2-B2）；记录被覆盖（r3-B1） |
| K4b | 最终采用的是别人抢先发布的 Y，分两个独立场景：<br>① A 设了 `PI_EXEC_MODEL=X`，按 X 预检通过：prepare 拒绝，退出 2，attempt 记 PREPARE_FAILED；<br>② 允许列表含 X、不含 Y：prepare 拒绝，退出 3，attempt 记 PREPARE_FAILED | 对错误的对象做了检查（r3-S1、r4-N3） |
| K5 | 预检之后、冻结之前改了合同：哈希不符，退出 4（不是 3），attempt 记 PREPARE_FAILED | 退出码被包装改掉（r2-S2） |
| K6 | 新版本用新绑定 | |
| K7 | 首次建立记录时没有绑定，或 contract 是 manual：退出 2，不留 attempt，不运行 CLI | |
| K8 | 首次建立记录时绑定未接通：退出 3，不留 attempt | |
| K9 | 已有记录之后删掉绑定，或改成未接通：prepare 照常沿用记录，打差异 NOTE | 已有记录被当前配置挡住（r2-S1） |
| K10 | `PI_EXEC_PROVIDER`、`PI_EXEC_MODEL`、`PI_EXEC_THINKING` 各自与记录冲突：拒绝，包括在 prepare 之后才设的情形 | |
| K11 | prepare 之后收紧 `allowed_executors`，或改了固定的 thinking：run 拒绝 | |
| K12 | 三类的派生与校验：<br>① `role:` 行与 JSON 的一致性；<br>② `role` 与 provider 或 thinking 同时出现（包括值为 null）时报错；<br>③ provider 与 model 都是 null，或只有其中一项为 null、另一项有值的合同，都按旧合同处理，不提前解析；<br>④ LB-CONTRACT-003 那种旧合同，派生结果与警告不变；<br>⑤ `role` 与 `model` 同时出现时报错 | 三类混淆（r1-S1、r2-S7、r3-N2） |
| K13 | 领取之后、写 `executor.json` 之前崩溃，再 `collect --recover`：summary 与 review-draft 显示的是记录里的模型 | 读回点没收口 |
| K14 | prepare 之后只改记录的 runtime，或改了它的合同哈希：G0 拒绝 | G0 核对不全（r2-S3） |
| K14b | 按角色写的合同，prepare 之后删掉 meta 里的 `executor_binding`：G0 拒绝。核验与否由冻结合同决定，不看 meta 的字段 | G0 被字段的缺失整体跳过（r3-S3） |
| K15 | 摘要中“执行模型来源”的三种写法 | |
| K16 | 链接与损坏：<br>① 版本记录、它所在的 task 目录、`.agent/runs`、`.agent` 任一级是链接或 junction 时，拒绝；<br>② 记录不完整或损坏时拒绝，不自动修复 | 跟随链接，包括 `first_link_component` 不查 root 本身的那一级（r3-S3）；半份记录被采信 |
| K17 | 本机文件的命令被 run 使用；`PI_DISPATCH_PI_CMD` 仍然优先 | |

### 9.5 接线

| 编号 | 场景 |
|---|---|
| W1 | `KIT_LOADED_FILES` 含 `kit_roles.py`；import 扫描一致；装进临时仓库后，`config role show` 与 `config doctor` 可用 |
| W2 | `gitignore.append.txt` 含四条规则；`kit_install update` 能补上 |
| W3 | 执行清单：全量 pytest，以及以脚本方式运行 `tests/test_dispatch.py` |

## 10. 待用户拍板（推荐项写在前）

1. **本仓库自己要不要现在就绑定**：
   - 推荐：本轮不改本仓库的配置，交付后由你决定；
   - 或者：交付时顺带配好。
2. **历史与审计要不要提交**：
   - 推荐：不提交，它们是本机的切换记录；
   - 或者：提交。
3. **本机覆盖文件**：
   - 推荐：新增 `.agent/dispatch.local.json`，只放命令路径；
   - 或者：本轮不做。
4. **`preset remove`**：
   - 推荐：加上；
   - 或者：照上位设计 8.5 不加。
5. **版本号**：
   - 推荐：合并时再定，记为 2.12.0。

第 2 稿的第 6、7、8 项已由用户决定，见 1.1。
