// 七端 hub 的常量（迁移第 ⑤a 片，kit_hub.py 1–131 行与 ROSTER）：退出码、信件类型、阶段与依赖、审核的退回对象、名册。
// 取值逐项照 kit_hub.py；名册的选型理由见那里的注释，这里不重复。
export const EXIT_OK = 0;
export const EXIT_FAIL = 1;
export const EXIT_USAGE = 2;
export const EXIT_BLOCKED = 3;

export const OWNER = "站主";
export const KERNEL = "内核";
export const COORDINATOR = "womovie-c8";
/** 发信人的 ASCII 别名：只用在 msg-id 与文件名里（与 @themis/base/clock 的 SENDER_ALIAS 相同）。 */
export const SENDER_ALIAS: Readonly<Record<string, string>> = { [OWNER]: "owner", [KERNEL]: "kernel" };

export const WORKER_TYPES = ["交付", "返工完成", "提问", "阻塞", "交接", "进度"] as const;
export const COORDINATOR_TYPES = ["开工", "返工", "通过", "等待", "停止", "汇报", "提问"] as const;
export const OWNER_TYPES = ["任务", "回复", "停止"] as const;
export const KERNEL_TYPES = ["核验", "阻塞"] as const;
/** 第 112 轮：内核代办例行流转时发给工人的信。 */
export const ROUTED_TYPES = ["开工", "返工", "通过"] as const;
/** 发给工人时只登记、不唤醒。 */
export const INFO_TYPES = ["通过", "等待", "停止"] as const;
export const FIELDS = ["摘要", "提交", "验证", "偏离", "需协调人决定", "证据"] as const;
export const VERDICT_FIELDS = ["结论", "退回", "阻塞项"] as const;
/** 第 111 轮：给后面阶段的提醒，内核原样附进下游各回合的输入。 */
export const HANDOFF_FIELD = "下游须知";
export const KERNEL_FIELDS = ["内核核验"] as const;
export const KNOWN_FIELDS: readonly string[] = [...FIELDS, ...VERDICT_FIELDS, HANDOFF_FIELD, ...KERNEL_FIELDS];
export const MAX_BODY_LINES = 40;
/** 站主一封信的字数上限（send 的正文）。 */
export const MAX_OWNER_CHARS = 2000;
export const VERDICTS = ["通过", "返工"] as const;

export const STAGES: readonly (readonly [string, string])[] = [
  ["1-plan", "planner-opus"],
  ["2-contract", "contract-glm"],
  ["3-gate-pre", "gate-sonnet"],
  ["3j-jev", "jev-judge"],
  ["4-audit-pre", "audit-sonnet"],
  ["5-exec", "exec-step"],
  ["6-gate-post", "gate-sonnet"],
  ["6j-jev", "jev-judge"],
  ["7-audit-post", "audit-sonnet"],
];
export const STAGE_ORDER: readonly string[] = STAGES.map(([suffix]) => suffix);
export const STAGE_WORKER: Readonly<Record<string, string>> = Object.fromEntries(STAGES);
/** 阶段之间的数据依赖：上游重新交付，下游（传递闭包）的结论一律作废。 */
export const DEPENDS: Readonly<Record<string, readonly string[]>> = {
  "1-plan": [],
  "2-contract": ["1-plan"],
  "3-gate-pre": ["2-contract"],
  "3j-jev": ["2-contract"],
  "4-audit-pre": ["3-gate-pre", "3j-jev"],
  "5-exec": ["4-audit-pre"],
  "6-gate-post": ["5-exec"],
  "6j-jev": ["5-exec"],
  "7-audit-post": ["6-gate-post", "6j-jev"],
};
/** 交付通过后由内核接着跑的 JEV。 */
export const AUTO_JEV: Readonly<Record<string, string>> = { "2-contract": "3j-jev", "6-gate-post": "6j-jev" };
/** 执行端以外的阶段，协调人最多让它返工几次。 */
export const MAX_STAGE_REWORKS = 3;
export const WORKER_RETRIES_AFTER_TIMEOUT = 2;
/** 第 180 轮：只读的岗位超时之后，内核开新会话重做那一回合收到的话。 */
export const TIMEOUT_RESTART_NOTE = "上一回合跑满时限，什么也没交出，作废了；这一回合是内核开的新会话。先把确定的部分交出来，"
  + "没核实的写进交付信：只读要用的文件，不要从头调查，读够了就交差。";
/** 审核端“退回”的对象 → 阶段（键序就是报错里列出的次序）。 */
export const RETURN_TARGETS: Readonly<Record<string, string>> = {
  合同端: "2-contract",
  门禁端: "3-gate-pre",
  战后门禁: "6-gate-post",
  执行端: "5-exec",
  规划端: "1-plan",
};
/** 工人这一回合没交付就停下了：阶段转为 paused，协调人可以再开工。 */
export const PAUSE_TYPES = ["提问", "阻塞", "交接", "进度"] as const;
/** 阶段已经开工时拒收开工、返工的理由。 */
export const BUSY_GUARD = "已经开工、还没交付";
/** 第 112 轮：交付通过之后例行的下一步；审核端按结论另算，执行端只在检查通过时。 */
export const ROUTINE_NEXT: Readonly<Record<string, string>> = {
  "1-plan": "2-contract",
  "2-contract": "3-gate-pre",
  "3-gate-pre": "4-audit-pre",
  "5-exec": "6-gate-post",
  "6-gate-post": "7-audit-post",
};

export interface RosterSpec {
  readonly role: string;
  readonly label: string;
  readonly adapter: "pi" | "claude" | "quizs" | "dispatcher" | "jev";
  readonly provider?: string;
  readonly model?: string;
  readonly thinking?: string;
  readonly effort?: string;
  readonly tools?: readonly string[];
  readonly allowed_rules?: readonly string[];
  readonly timeout?: number;
  readonly workspace?: "base" | "stage";
  readonly routing?: "kernel";
  /** 第 143 轮：quizs 岗位的替补：证书过期、文件没设时这一回合改用这些字段（例如退回 pi），开新会话。 */
  readonly fallback?: Partial<RosterSpec>;
  /** 第 154 轮：这个岗位的配置来自配置中心的哪个 profile；照名册缺省跑时没有这一项。 */
  readonly binding_profile?: string;
}

/** 七个岗位（键序与 kit_hub.ROSTER 相同：协调人在前）。 */
export const ROSTER: Readonly<Record<string, RosterSpec>> = {
  [COORDINATOR]: {
    // 第 138 轮：时限 1200 → 600 秒（446 个回合最长 419 秒、p99 291 秒；卡死时少等 10 分钟，用户 2026-11-07 同意）
    // 第 145 轮：换到 quizs 载体（模型不变，用户 2026-11-07“全部按你的推荐完成任务”）；证书过期、文件没设时退回 pi
    role: "coordinator", label: "调度代理端（协调人）", adapter: "quizs", provider: "deepseek", model: "deepseek-flash", thinking: "high",
    tools: ["read", "grep", "find", "ls"], timeout: 600, workspace: "base", routing: "kernel", fallback: { adapter: "pi", provider: "dsf" },
  },
  "planner-opus": {
    role: "planner", label: "规划端", adapter: "claude", model: "claude-opus-5-5", effort: "max",
    tools: ["Read", "Grep", "Glob", "Bash"], allowed_rules: ["Bash(npm view:*)"], timeout: 2400, workspace: "base",
  },
  "contract-glm": {
    role: "contract", label: "合同端", adapter: "pi", provider: "minimax", model: "MiniMax-M3.1-Flash", thinking: "high",
    tools: ["read", "grep", "find", "ls"], timeout: 2400, workspace: "base",
  },
  "gate-sonnet": {
    role: "gate", label: "门禁端", adapter: "pi", provider: "cc-switch-zhipu-glm", model: "glm-5.3", thinking: "high",
    tools: ["read", "grep", "find", "ls", "edit", "write", "bash"], timeout: 2400, workspace: "stage",
  },
  "audit-sonnet": {
    role: "audit", label: "审核端", adapter: "pi", provider: "minimax", model: "MiniMax-M3.1-Flash", thinking: "max",
    tools: ["read", "grep", "find", "ls"], timeout: 2400, workspace: "stage",
  },
  "exec-step": { role: "exec", label: "执行端", adapter: "dispatcher", provider: "cc-switch-step-fun", model: "step-5-preview", thinking: "high" },
  "jev-judge": { role: "jev", label: "JEV 端", adapter: "jev" },
};
export const WORKERS: readonly string[] = Object.keys(ROSTER).filter((name) => name !== COORDINATOR);
const EXEC = ROSTER["exec-step"] as RosterSpec;
export const EXECUTOR: readonly [string, string, string] = [EXEC.provider ?? "", EXEC.model ?? "", EXEC.thinking ?? ""];
export const CONTRACT_EXECUTOR_LINE = `- executor: ${EXECUTOR[0]}/${EXECUTOR[1]} · thinking ${EXECUTOR[2]}`;

// --- 回合审计（第 ⑤c 片）：kit_hub.py 的同名常量 ---------------------------------------------------------------------

/** pi 工人交差的工具（第 90 轮）。 */
export const DELIVER_TOOL = "deliver";
/** claude 的 --json-schema 交差时，CLI 自己加上的工具（第 101 轮）。 */
export const STRUCTURED_TOOL = "StructuredOutput";
/** 第 169 轮：交差的 letter 给模型看英文键，内核收下时按这张表换回中文栏目（kit_hub.py 的 LETTER_KEYS，逐项相同）。 */
export const LETTER_KEYS: readonly (readonly [string, string])[] = [
  ["summary", "摘要"], ["commits", "提交"], ["verification", "验证"], ["deviations", "偏离"],
  ["needs_coordinator_decision", "需协调人决定"], ["downstream_notes", "下游须知"], ["evidence", "证据"],
  ["conclusion", "结论"], ["return_to", "退回"], ["blockers", "阻塞项"],
];
/** 第 169 轮：交给 pi 的那份 schema（toolSchema）写在回合目录里，deliver.ts 读它。 */
export const TOOL_SCHEMA_FILE = "deliver-schema.json";
/** 守卫扩展（scripts/hub/guard.ts，第 106 轮）拦下的结果以这个前缀开头、以这个结尾收尾，与 guard.ts 的同名常量逐字相同。 */
export const GUARD_PREFIX = "内核拦下：";
export const GUARD_SUFFIX =
  "。这一步没有执行：在工作目录里写，读只读输入目录或工作目录里的那一份，已经装好的依赖用 read、grep、find、ls 按路径读，接着干；不要换写法绕过去";
/** 第 56 轮：审计读不出来的行不再静默跳过（%d 是行数）。 */
export const UNREADABLE_STREAM = "事件流里有 %d 行读不出来（不是 JSON 对象）：审计看不全这一回合，按越界处理";
/** claude 的工具名对应到 pi 的（第 88 轮）：碰没碰主工作区与 pi 用同一套判断。 */
export const CLAUDE_REACH_NAMES: Readonly<Record<string, string>> = {
  Read: "read", Grep: "grep", Glob: "find", LS: "ls", Write: "write", Edit: "edit", MultiEdit: "edit", NotebookEdit: "edit", Bash: "bash",
};
/** 工人可以按路径读的主工作区子树（第 88 轮）：已经装好的依赖，只许 READ_TOOLS 读。 */
export const DEPENDENCY_DIRS: readonly string[] = ["ts/node_modules", "desktop/web/node_modules"];
/** pi 上按路径读与搜索的工具：参数里的 path 就是读的位置。 */
export const READ_TOOLS: readonly string[] = ["read", "grep", "find", "ls"];

// --- 回合启动与输入（第 ⑤d 片）：kit_hub.py 的同名常量 ---------------------------------------------------------------

/** 回合输入超过这个长度就写进文件，命令行只给路径（Windows 命令行上限约 32K 字符）。 */
export const MAX_INLINE_PROMPT = 20000;
/** 只有内核调决策 API 时需要它；工人与调度器子进程一律拿不到。 */
export const DECISIONS_KEY_ENV = "TYPESAFE_API_KEY";
/** 工人进程不继承的会话变量：让 hub 无论从哪里启动，工人的行为都一样。 */
export const WORKER_ENV_DROP: readonly string[] = [DECISIONS_KEY_ENV, "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_SSE_PORT"];
export const CLAUDE_SETTINGS = { autoMemoryEnabled: false, advisorModel: "" } as const;
/** claude 工人另加的环境（第 28 轮）：每条 Bash 命令之后 shell 回到工作目录。 */
export const CLAUDE_WORKER_ENV: Readonly<Record<string, string>> = { CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR: "1" };
/** 模板读到空文件时再读几次（合入内核时文件正被替换，第 26 轮）。 */
export const TEMPLATE_READ_TRIES = 5;
/** 回合的只读输入目录（第 88 轮）：worktree 根目录下的 <仓库名>-hub-inputs/<键>；%s 是仓库名。 */
export const INPUTS_DIR = "%s-hub-inputs";
export const INPUTS_INDEX = "INPUTS.json";
/** 单个文件超过这么大就不复制进输入目录，清单里记进 skipped。 */
export const INPUT_FILE_LIMIT = 4 * 1024 * 1024;
/** 第 151 轮：quizs 回合的提示里逐个列出快照里的文件，最多这么多个；再多就按目录合计 */
export const SNAPSHOT_MANIFEST_LIMIT = 200;
/** 交差格式（逐字进提示词）。 */
export const OUTPUT_SPECS: Readonly<Record<string, string>> = {
  coordinator: "{\"letters\": [{\"to\": \"<收信人>\", \"type\": \"开工|返工|通过|等待|停止|汇报|提问\", \"task_id\": \"<阶段任务或主任务>\", \"in_reply_to\": \"<msg-id 或 none>\", \"摘要\": \"…\", \"提交\": \"无\", \"验证\": \"…\", \"偏离\": \"无\", \"需协调人决定\": \"无\", \"证据\": \"…\", \"brief\": \"<开工、返工时必填：下一阶段任务书的 Markdown 全文>\"}], \"state\": \"<你的进度断点，Markdown>\"}",
  worker: "{\"letter\": {\"type\": \"交付|返工完成|提问|阻塞|交接|进度\", \"in_reply_to\": \"<msg-id>\", \"summary\": \"<摘要>\", \"commits\": \"<提交>\", \"verification\": \"<验证>\", \"deviations\": \"<偏离>\", \"needs_coordinator_decision\": \"<需协调人决定>\", \"downstream_notes\": \"<下游须知>\", \"evidence\": \"<证据>\"}, \"report\": \"<report.md 全文>\", \"state\": \"<state.md 全文>\"}",
  /** 第 176 轮（候选 #51）：审核端的 letter 里就带结论、退回、阻塞项（原来示例里没有、另起一句，Quizs 上的一审一回漏写、一回写到 letter 外面）。 */
  audit: "{\"letter\": {\"type\": \"交付|返工完成|提问|阻塞|交接|进度\", \"in_reply_to\": \"<msg-id>\", \"summary\": \"<摘要>\", \"commits\": \"<提交>\", \"verification\": \"<验证>\", \"deviations\": \"<偏离>\", \"needs_coordinator_decision\": \"<需协调人决定>\", \"downstream_notes\": \"<下游须知>\", \"evidence\": \"<证据>\", \"conclusion\": \"<结论>\", \"return_to\": \"<退回>\", \"blockers\": \"<阻塞项>\"}, \"report\": \"<report.md 全文>\", \"state\": \"<state.md 全文>\"}",
};
/** 各岗位另加的输出要求（逐字进提示词）。 */
export const ROLE_EXTRA_OUTPUT: Readonly<Record<string, string>> = {
  planner: "另加 \"external_facts\": [{\"fact\": \"<计划依赖的仓库外事实>\", \"source\": \"<出处>\", \"verified\": \"<核实的命令与结果；没核实就写“未核实”>\"}]，没有仓库外事实就写 []",
  contract: "另加 \"contract_md\": \"<合同 Markdown 全文>\"",
  gate: "战后模式把变异清单写进工作目录根下的 mutation-spec.json：{\"commands\": [{\"id\": \"W1\", \"argv\": [\"python\", \"-m\", \"pytest\", \"<文件>\", \"-q\"]}], \"mutations\": [{\"name\": \"…\", \"file\": \"<相对路径>\", \"old\": \"<原文片段>\", \"new\": \"<改坏后的片段>\"}]}，输出里另加 \"mutation_spec_file\": \"mutation-spec.json\"，不要再把清单抄进输出（内核读的就是这个文件）；commands 里每一条都是检验命令，每条变异缺省要被每一条抓住，某条命令本来就测不到的变异（例如静态检查碰不到的行为改动），在那一条里加 \"expect_missed\": [\"<命令 id>\"]（至少留一条命令抓它，终审会看）；安装依赖这类准备步骤不要放进 commands：mutate 在你的工作目录里原地跑，依赖在你的回合里照合同的 setup 装好就在；交差前在工作目录里把 commands 每条跑一遍、都要退出 0（mutate 的基线就是这一步，缺依赖、cwd 错、路径错都能当场发现）；确实测不出来的等价改写，在那一条里加 \"equivalent\": \"<为什么改了行为也不变>\"（终审会逐条复核），其余每条都必须被抓住；执行端改动的每个非测试文件至少一条变异，确实没法变异的（例如二进制文件）另加 \"unmutated\": [{\"file\": \"<相对路径>\", \"reason\": \"<为什么>\"}]（终审会复核）；候选不满足合同写明的行为时另加 \"candidate_defects\": [{\"test\": \"<红的用例 node id 或函数名>\", \"contract\": \"<合同原文>\", \"where\": \"<候选文件:行>\"}]（这时可以不给 mutation_spec_file）",
  audit: "letter 里最后这三项都要写（在 letter 的花括号里面，不和 report 平级）：\"conclusion\"（结论）: \"通过|返工\"（交付以外的信写“无”）；\"return_to\"（退回）: \"合同端|门禁端|战后门禁|执行端|规划端\"（一审只能退回规划端、合同端、门禁端；几个对象都要改时用“、”隔开，例如 \"合同端、门禁端\"；不是返工写“无”）；\"blockers\"（阻塞项）: \"<逐条列出必须改的问题，只列会导致打回的；退回几个对象时注明每条归谁>\"（不是返工写“无”）",
};
/** 第 96 轮：这几个 pi 岗位带 --no-context-files，读不到 AGENTS.md，内核把“通用工程要求”一节拼进它们的角色提示词。 */
export const ENGINEERING_ROLES: readonly string[] = ["contract", "gate", "audit"];
export const ENGINEERING_HEADING = "## 通用工程要求（所有代理）";
/** 合同的总预算给这一版至少留几次 attempt：一次失败之后还能返工给执行端。 */
export const MIN_ATTEMPTS_LEFT = 2;
/** 门禁测试实际撞过的坑（第 52 轮）：开工时交给门禁端自查。 */
export const GATE_PITFALLS: readonly string[] = [
  "只用已安装版本里有的 API：先在 node_modules 里查。@testing-library/dom 10.4.0 的 fireEvent 没有 hashChange，要写 fireEvent(window, new HashChangeEvent('hashchange'))（T011）。",
  "每个探针文件自带它用到的辅助函数：探针之间不共享作用域，在一个探针里定义、另一个里调用会报 ReferenceError（T011）。",
  "期望值要算出来，不凭印象手写：排序后的数组按 JS 默认排序（UTF-16 码元序，'candidate.patch' 在 'checks/…' 前面）；依赖夹具的数量从夹具数，别写死（T011 的 setDetail 只给 1 行却断言 8 个选项；T012 的仓库数没算上保存进桩的那一个）。",
  "卸载、清理对准被测的那个根：用 mountApp / render 返回的结果，不要另渲染一个空元素再卸载它（T011）。",
  "jsdom 的局限：属性选择器匹配不了含 <、> 的值（改成遍历元素、比较 getAttribute）；写 location.hash 会用 setTimeout(fn, 0) 派发 hashchange，假计时器下它是一个挂起的计时器，数计时器之前先推进掉（T011、T012）。",
  "字样、白名单这类扫描不能误伤合同要求的元素：例如「待验收」分组胶囊含“验收”二字（T011）。",
  "用例之间不留状态：模块级的桩、mock 覆盖、计时器、地址在每条用例开头重置，cleanup 之后重挂载要拿到新的数据。",
  "同一行为在合同里只认一种说法：两条断言对同一行为的要求互相矛盾时，先发提问（T010 的 K25 与 D09）。",
  "辅助函数收几个参数就只传几个：rowOf 只收一个参数，logsCatRow 把覆盖值当第二个参数传进去，被悄悄丢掉，D05「取不到写—」、D09「checks 为 -」的夹具都没生效（T011）。写完夹具，先断言夹具本身取到了想要的值。",
  "断言命令文本照真实的连接方式写：信封的 command 按空格连接（logs cat <task>/<attempt> <路径>），正则别写成路径里的斜杠（T011 的 D06）。",
  "只断言合同写明的内容：合同没规定的细节（例如出错时读哪个文件、显示哪条路径）不写死；一条用例里不同时要求互斥的两种状态（T011 的 TRANS：既要缺省选中 ui-readonly-api，又要页面上有 logs-cat 的表，少点了一下）。",
  "流水线夹具在“候选里还没有本片的文件”时提前返回，后面起 vitest、跑探针的那段代码在基线上一次也跑不到，写错了要等执行端交付才炸（T042 的 Pipeline 少一个 group()，4 条流水线用例 AttributeError）：交付前在工作区里临时放一份最小的桩文件，让夹具完整走一遍（红只许红在 vitest 自己的结果上，不许是夹具代码报错），跑完删掉桩。",
  // 第 183 轮：T047 的门禁冻住了 T048 要改的文件，T048 开工前站主只好先改两份旧门禁（候选 #61）
  "基准测试落地后一直留在仓库里当回归门禁（之后每一片的 R01 都跑它），只钉本片带来的行为：合同 forbidden_paths 里的文件由调度器的范围检查管（越界数必须为 0），不要再按字节冻结它们，也不要断言它们“不出现某某”；列头整组、桩数据字节这类逐字的形状留给执行端写的前端测试（后面的片能照合同改），门禁里钉“含这几列、次序如此”。后面的片合法改到这些地方时，旧门禁必红，只能由站主先改门禁（T047 的 S10 冻结 RolesPage、RolesView，S07、S09 逐字钉十列，T048 加一列之前站主改了两份门禁）。",
  // 第 192 轮：T048 的 S05、T053 的 S01 静态记号与合同钉死的写法对不上，执行端写对了照样红，每次都热修补再派一轮（候选 #71）
  "静态记号检查（源码里有没有某段写法）的正则或子串，交付前拿合同“写法钉死”的那一行原样试一遍，要匹配得上：原始字符串里点号前只写一个反斜杠（写两个匹配的是字面反斜杠加任意字符），记号也别多带合同写法里没有的括号（T053 的 S01、T048 的 S05：执行端照合同写对了照样红，热修补之后再派一轮）。",
  // 第 194 轮：T055 的门禁探针取文档里第一个提示，读到的是对话框头部关闭钮的，执行端禁用关闭钮来迁就探针（候选 #75）
  "悬停提示按触发元素自己的 aria-describedby 取（照 t023 门禁的 tipOf：悬停 Tooltip 的包裹元素、推进 400ms，读触发元素 aria-describedby 指向的那个元素），不要取文档里第一个 [role=tooltip]：对话框打开时焦点落在头部关闭钮上，它自带的提示「关闭（Esc）」会先出来（T055 的 hoverTip 先取到它，执行端只好在作业运行时禁用对话框的关闭钮来迁就探针）。",
  // 第 195 轮：T054、T055 的门禁逐字钉了 JobKind 那一行，T055 还反查 t045 的「运行时页 1」，T056 加第四类作业只好连带改两份旧门禁（候选 #76）
  "后面的片还会接着扩的东西（联合类型的成员、KINDS 这类数组、白名单、“还剩几个禁用入口”这类计数），门禁只核对「含这几项」或「旧值已经不在」，不逐字钉整行，也不钉新的计数（确切的值留给包内测试，后面的片照合同改）；兼容性一节反查别的门禁、包内测试改得对不对时也照此写（T054、T055 的门禁逐字钉了 JobKind 那一行，T055 还反查 t054 的那一行与 t045 的「运行时页 1」，T056 加第四类作业时只好连带改 t054、t055 两份旧门禁）。",
  // 第 197 轮：T057 的门禁探针重挂载后没重新输入就点 [核验]，却期望发出上一次的记录值，与合同“不记住上次的值”打架（候选 #79）
  "卸载再挂载之后，组件自己的状态是新的（受控文本框的内容、没保存的选择都回到初值）：合同没写预填或记住上次的值时，重挂载之后要操作就先重新输入；交付前把每一步期望发出的请求与合同的“不做”、“值不合格不发请求”对一遍（T057 的 (h) 重挂载后没输入就点 [核验]，却期望发出上一次的记录值：实现只能记住上次的值，正好是合同写明不做的；执行端为凑它写了回退，自己按合同写的测试随即红了）。",
  // 第 197 轮：T057 的门禁探针在换值再点之后才把假服务改成 failed，作业库创建后立刻查一次，这个答案查不到（候选 #79）
  "探针要改假服务的答案（作业状态、返回的信封）时，放在触发请求的那次点击之前：作业库重新创建之后会立刻（0 毫秒）查一次，新作业当场落定、轮询随即停止，点击之后才改的答案永远查不到；合同不许改作业库的查询节奏时更要如此（T057 的 (h) 换值再点之后才改成 failed，执行端只好改 jobStore 的查询节奏来迁就）。",
  // 第 201 轮：T063 的单位探针用 new URL(…, import.meta.url) 读 Table.css，这套 Windows + vitest 下一读就抛 TypeError（候选 #83）
  "探针读仓库里的文件时按 process.cwd() 拼路径（探针在 desktop/web 下跑，例如 path.resolve(process.cwd(), 'src/components/Table.css')），不要用 new URL('…', import.meta.url)：这套 Windows + vitest 下 import.meta.url 不是 file: 地址，readFileSync 读之前就抛 TypeError（The URL must be of scheme file）。这一步在基线上常常跑不到，交付前照上面“放一份最小的桩文件让夹具完整走一遍”那条把探针跑一遍（T063 的 probe:units 就红在这里，执行端 1800 秒用满、白扣一次 attempt）。",
];
/** 第 38 轮：pi 的模型接口限流时扣信退避（秒），连着限流太多次就照旧按接口报错交给站主。 */
export const THROTTLE_BACKOFF_SECONDS = 300;
export const THROTTLE_BACKOFF_MAX = 3600;
export const THROTTLE_MAX_HOLDS = 5;
/** 第 158 轮：模型接口的临时报错照限流扣信退避（从 THROTTLE_BACKOFF_SECONDS 起加倍），连着这么多次还不好才交给站主；扣信不写信给站主。 */
export const TRANSIENT_MAX_HOLDS = 3;
export const TRANSIENT_HOLD_REASON = "模型接口临时报错";
/** 第 179 轮：提供方集群过载（529、overloaded_error）单独一类，扣 5 次（5、10、20、40、60 分钟）才交给站主；同 kit_hub.py 的 OVERLOAD_*。 */
export const OVERLOAD_MAX_HOLDS = 5;
export const OVERLOAD_HOLD_REASON = "模型接口过载";
/**
 * 限流报错里写着重置时刻（智谱的 1308：“…将在 2026-11-06 18:44:51 重置”）时扣到那之后一会儿，不再加倍试探。这个时刻不带时区，
 * 是北京时间：T026 的门禁端 08:42Z 撞上、报 18:44:51，10:59Z 的扣信到点接着做成了；按 UTC 读要到 18:44Z 才解除。
 * 换算出来已经过去、或在 24 小时以外的不认，照旧退避（时区读错了也只是早醒一次，下一回合照旧退避）。
 */
export const THROTTLE_RESET_OFFSET = 8 * 3600;
export const THROTTLE_RESET_MARGIN = 60;
export const THROTTLE_RESET_HORIZON = 86400;
/**
 * 第 137 轮：quizs 载体（P1：名册没换，协调人照旧走 pi；换载体要站主同意）。命令取 QUIZS_CMD（JSON 的字符串列表），缺省是 PATH 里的 quizs；
 * Quizs 的提供方状态放在信箱的 quizs-state 下。交付是最后回答里的一个 json 代码块。
 */
export const QUIZS_STATE_DIR = "quizs-state";
export const QUIZS_FENCE_OPEN = "```json";
export const QUIZS_FENCE_CLOSE = "```";
/** 第 143 轮：证书至少还要撑过这一回合的时限再加这么多秒，不然这一回合退回名册写的替补（fallback）。 */
export const QUIZS_CERT_MARGIN = 60;
/** 第 143 轮：quizs 每回合的预算。Quizs 默认请求 8 次、单次输入 512 KiB、单次回应 256 KiB；DeepSeek 的流式回应每个输出 token 约 290 字节，
 *  256 KiB 不到 900 个 token 就掐断（P2a 实测），协调人每回合开新会话还得重读输入。实际上限取它与 live plan 的较小者 */
export const QUIZS_TURN_BUDGETS: readonly (readonly [string, string])[] = [
  // 第 145 轮：请求 24 → 32、工具调用 48（P2a 30 个回合里 2 个用完 24 次请求还没交差，都是输入多的回合）
  // 第 152 轮：单次回应与单个对象放到 8 MiB（Quizs 的上限）：认证的单次输出上限从 8192 放到 16384 个 token，写满约 5.1 MB 的流（每个 token 约 313 字节）
  ["--max-requests", "32"], ["--max-tool-calls", "48"], ["--max-input-bytes", "2097152"], ["--max-response-bytes", "8388608"], ["--max-object-bytes", "8388608"],
];
/** 第 187 轮：每个 quizs 回合里单个工具结果放进对话的上限。Quizs 默认 4096 字节，超过的只放前 4 KiB 的预览（外加模型取不回的
 *  对象引用）；只读工具自己按 64 KiB 分页（与 pi 的 read 一页相同），4 KiB 把这一页截在中间，读文件时连 next_offset 也截掉了
 *  （键按字母排，content 在前）。放到与工具自己的上限相同，一页整页进对话 */
export const QUIZS_TOOL_PREVIEW: readonly [string, string] = ["--tool-preview-bytes", "65536"];
/** 第 145 轮：quizs 因模型的做法结束回合的错误类别（不是环境问题）：记成交差不合格，内核带着这段说明当场重交一次。 */
export const QUIZS_BEHAVIOR_ERRORS: Readonly<Record<string, string>> = {
  BUDGET_EXHAUSTED: "这一回合用完了请求或工具调用的预算还没交差。重交时少翻目录，只读要用的文件，尽早写出 json 代码块",
  // 第 198 轮：工作区模式里被拒的命令超过每回合的上限也是这一类
  POLICY: "调了没有授权的工具，或者被拒的命令超过了每回合的上限（门禁的 bash 没有 shell，只收 `python -m pytest`、`python -c`、"
    + "`python 文件.py`、`node 文件` 与只读 git）。交差不调用任何工具，把 json 代码块直接写在最后的回答里",
  TOOL_ERROR: "工具参数不合格式（JSON、路径写法或字段），回合被 Quizs 结束。重交时照工具说明写参数",
  // 第 149 轮：P2b 30 个回合里 1 个这样结束（回应完整、是工具调用，Quizs 不认）；提供方回应残缺也归这一类，同样重来一次
  PROVIDER_FORMAT: "Quizs 读不了模型这一次的回应，回合被结束（多半是工具调用的参数不是合法 JSON、不合工具说明里的格式，或者该写最后回答时还在调工具）。重交时照工具说明写参数，读够了就直接写 json 代码块",
  // 第 149 轮：Quizs 的 fenced 交差策略自己先让模型改一次，还不对就这样结束
  FINAL_OUTPUT_FORMAT: "最后的回答不是恰好一个 json 代码块，Quizs 让改过一次还是不对。重交时最后的回答只写一个 json 代码块，前后不加别的文字",
  // 第 152 轮：P2c 30 个回合里有协调人把单次输出上限全用在思考上（finish_reason 是 length），Quizs 报成 UPSTREAM 加 provider_code；这是模型这一次的做法，不是接口坏了
  OUTPUT_TOKEN_LIMIT: "这一次的回应写到单次输出的上限被截断了（思考也算在里面），回合被结束。重交时少想多写：要用的文件读完就直接写 json 代码块，任务书只写下一阶段要用的内容",
  // 第 187 轮：工具结果整页进对话之后，读得太多会先撑满单次请求的输入上限（live plan 的 max_input_bytes）
  CONTEXT_BUDGET_EXCEEDED: "这一回合读进对话的内容撑满了单次请求的输入上限，回合被结束。重交时先用 grep、find 定位，只读要用的文件与段落，同一处不重复读，读够了就直接写 json 代码块",
};
/** 第 152 轮：Quizs 把“写到单次输出上限被截断”报成 UPSTREAM，error_details 的 provider_code 是这个字面量。 */
export const QUIZS_OUTPUT_CUT = "OUTPUT_TOKEN_LIMIT";
/** 第 181 轮：Quizs 回合撞上提供方集群过载（MiniMax 的 HTTP 529），error_details 的 provider_code 是这个字面量；归过载一类。 */
export const QUIZS_OVERLOADED = "overloaded_error";
/** 第 142 轮：quizs 排队超时＝提供方的并发名额被占（Quizs 对一个提供方账户只开 1 个名额；结果不明的请求一直占着，要站主核实后释放）。 */
export const QUIZS_PERMIT_HELD = "quizs 退出码 5（QUEUE_TIMEOUT）：提供方的并发名额被占着。要么另一个 quizs 回合正在用（等它结束即可）；"
  + "要么之前有一次请求结果不明（例如 DeepSeek 回了 500 或连接中途断开），Quizs 不判定它已结束，名额一直占着，之后的回合都会排队超时。"
  + "站主处理：在信箱目录下运行 quizs permits list --provider-state-dir quizs-state 看占着的是哪一条；状态是 unknown_remote 的，"
  + "先到 DeepSeek 后台核实那次请求已经结束，再运行 quizs permits release --provider-state-dir quizs-state --attempt-id <那一条的 attempt_id> --confirm-terminal 释放";
/** 第 141 轮：真实请求要的三份文件（Quizs 的 live plan、提供方档案与资格证书）由环境给路径；测试与 fake 提供方都不设。 */
export const QUIZS_LIVE_FILES: readonly (readonly [string, string])[] = [
  ["--live-plan", "QUIZS_LIVE_PLAN"], ["--provider-profile", "QUIZS_PROVIDER_PROFILE"], ["--qualification", "QUIZS_QUALIFICATION"],
];
/** 第 148 轮：Quizs 的交差策略只认没用过的 plan（一份 plan 只给一个回合，用过再用按 USAGE 退出）：内核照环境给的那份每回合
 *  另写一份放进回合目录，plan_id 接上回合号。P2b 重放时同一份 plan 的第二个回合就起不来，才发现 */
export const QUIZS_TURN_PLAN = "live-plan.json";
/** 第 150 轮：quizs 自己没起来（result 事件的退出码 2：plan、证书、参数这类配置问题，请求没有发出去）时，名册写了替补的岗位
 *  记下这个标记（信箱的 quizs-state 下），协调人这一回合当场换替补重办；之后这么多秒内直接用替补，到点再试 quizs */
/** 第 156 轮：标记按提供方分开（down-<提供方>.json）：MiniMax 的 live 文件坏了，不该把协调人（DeepSeek）也推去替补。 */
export const QUIZS_DOWN_FILE = "down-%s.json";
export const QUIZS_DOWN_SECONDS = 900;
/** 第 156 轮：读仓库的岗位在 quizs 上读这一回合工作目录冻成的整棵仓库（Quizs 的仓库视图：已跟踪的文件与没被忽略的新文件，二进制与超过
 *  4 MiB 的不在里面），内核复制的输入照相对仓库的原样叠在上面；协调人照旧只读输入目录冻成的快照。 */
export const QUIZS_REPO_VIEW_ROLES: readonly string[] = ["contract", "audit"];
/** 第 156 轮：读仓库的岗位每回合的预算。pi 上 MiniMax 的合同端（52 个回合）工具调用中位 30、最多 107，审核端（45 个）最多 60；工具调用 128 是
 *  Quizs live plan 的上限。 */
export const QUIZS_VIEW_BUDGETS: readonly (readonly [string, string])[] = [
  ["--max-requests", "128"], ["--max-tool-calls", "128"], ["--max-input-bytes", "2097152"], ["--max-response-bytes", "8388608"], ["--max-object-bytes", "8388608"],
];
/** 第 198 轮（七端走 Quizs 二期）：在 quizs 上走工作区模式的岗位。Quizs M11 起工作区模式给的是活的 worktree、读写工具与受限的 bash
 *  （没有 shell，只收 pytest、python、node 与只读 git）；内核复制的输入用 read、grep、find、ls 的 root "inputs" 读 --readonly-root
 *  （工作区模式不能带快照）。只读岗位照旧冻快照。 */
export const QUIZS_WORKTREE_ROLES: readonly string[] = ["gate"];
/** 第 198 轮：门禁每回合的预算。pi 上 290 个门禁回合工具调用中位 32、九成在 69 以内、超过 128 的 3 个；128 也是 GLM live plan 的上限。 */
export const QUIZS_WORKTREE_BUDGETS: readonly (readonly [string, string])[] = [
  ["--max-requests", "160"], ["--max-tool-calls", "128"], ["--max-input-bytes", "2097152"], ["--max-response-bytes", "8388608"], ["--max-object-bytes", "8388608"],
];
/** 第 198 轮：被拒的命令回反馈、第 6 次才结束回合；参数格式错可以重来 2 次。命令输出：原始 256 KiB、摘要 4 KiB、交给模型的信封 8 KiB
 *  （QUIZS_TOOL_PREVIEW 装得下）；作业对象 128 个进程、8 GiB（11-19 实测三：T047 门禁的 npm ci 与 vitest 在这里面 51 秒跑完）。 */
export const QUIZS_WORKTREE_LIMITS: readonly (readonly [string, string])[] = [["--max-format-recoveries", "2"], ["--max-command-denials", "5"]];
export const QUIZS_OUTPUT_LIMITS: Readonly<Record<string, number>> = { raw_bytes: 262144, summary_bytes: 4096, envelope_bytes: 8192 };
export const QUIZS_JOB_LIMITS: Readonly<Record<string, number | string>> = { activeProcessLimit: 128, memoryLimitBytes: 8589934592, basis: "tt-gate" };
/** 第 198 轮：Quizs 原生组件（工作区模式的 runner 与文件后端）。QUIZS_NATIVE 是放它们的目录；没设时从 QUIZS_CMD 里的源码入口
 *  （…/ts/packages/quizs/cli/src/main.ts）往上推出 Quizs 根、拼 dist/native。 */
export const QUIZS_NATIVE_ENV = "QUIZS_NATIVE";
export const QUIZS_NATIVE_FILES: readonly [string, string] = ["worktree-runner.exe", "worktree-fs.exe"];
export const QUIZS_MAIN_TAIL = "ts/packages/quizs/cli/src/main.ts";
/** 第 198 轮：回合目录里交给 Quizs 的三份文件；门禁的 npm、bun 缓存根在信箱下，跨回合保留，第一次用时打上 Low 标签。 */
export const QUIZS_PROFILE_FILE = "command-profile.json";
export const QUIZS_OUTPUT_FILE = "output-limits.json";
export const QUIZS_JOB_FILE = "job-limits.json";
export const QUIZS_CACHE_DIR = "quizs-cache";
export const QUIZS_CACHE_MARK = ".low-labelled";
/** 第 198 轮：开门禁回合之前在 Medium 预装 ts/node_modules 的时限（实测三：执行域的低完整性令牌建不了 symlink）。 */
export const QUIZS_PREPARE_TIMEOUT = 300;
/** 第 198 轮：门禁在 quizs 上的工具说明。pi 上门禁 290 个回合 bash 四千多次，多半是 head、grep、cat 与内联 python；Quizs 的 bash
 *  没有 shell，照 shell 的习惯写会被拒（被拒的回反馈，第 6 次结束回合）。 */
export const QUIZS_WORKTREE_NOTE: readonly string[] = [
  "", "## 这一回合的工具（Quizs 的工作区模式）", "",
  "- bash 收的是 argv 数组，没有 shell：管道、重定向、&&、cd、变量都没有，也跑不了 ls、cat、head、grep、rm 这类命令。"
    + "看文件用 read、grep、find、ls；改文件用 edit、write。",
  "- bash 只收这几种：`python -m pytest …`（只认报告类选项，-q、-rfE 都行）、`python -c 代码`（代码可以多行）、"
    + "`python 文件.py …`、`node 文件.mjs …`（文件都在工作目录里），与只读的 git（status、log、diff、show、rev-parse、ls-files）。",
  "- 自己建的临时文件用 `python -c` 调 os.remove 删掉；不进仓库的探针、脚本交付前都要删。",
  "- 被拒的命令什么也没跑，结果里写明被拒的是哪个参数、这里收什么：照它改。一回合里被拒到第 6 次，回合就结束。",
];
/** 第 156 轮：每个提供方一套 live 文件，放在信箱的 quizs-live/<提供方>/ 下（续期脚本写的三个文件名）。三份不全时退回环境变量给的那一套
 *  （第 141 轮协调人原来的做法），但那一套的提供方档案认得出是别家的就不用（键是 Quizs 的 --provider，值是它的档案 id）。 */
export const QUIZS_LIVE_ROOT = "quizs-live";
export const QUIZS_LIVE_NAMES: readonly (readonly [string, string])[] = [
  ["--live-plan", "plan.json"], ["--provider-profile", "profile.json"], ["--qualification", "qualification.json"],
];
export const QUIZS_PROFILE_IDS: Readonly<Record<string, string>> = { deepseek: "deepseek-api", minimax: "minimax-m-plan", stepfun: "stepfun-cn-step-plan", glm: "glm-coding-plan" };
/** 第 156 轮：算工作目录的树时用的临时索引（回合目录里，用完就删）。 */
export const QUIZS_VIEW_INDEX = "view.index";
/** 第 175 轮：交差策略是代码块那一种的 plan，内核把这个岗位给模型看的 schema（toolSchema，letter 是英文键）写进回合目录、用
 *  --final-schema 交给 Quizs：代码块的 JSON 不合 schema，Quizs 在回合里退回修一次（逐条写明哪里不合），修过仍不合或来不及修就原样交回，
 *  内核照旧复核（候选 #47）。审核端在 Quizs 上的头一个真回合（T045 一审）交差缺了三个键，内核整回合重交又花了 706 秒 */
export const QUIZS_FINAL_SCHEMA = "final-schema.json";
export const QUIZS_FENCED_POLICY = "fenced_json_final_once_v1";
/** Quizs 当场按 schema 退回的记录（final_schema_rejected 事件，action 是 repair 或 deliver）写进这一回合的 warnings，带上头三条错误。 */
export const QUIZS_SCHEMA_NOTES: Readonly<Record<string, string>> = {
  repair: "交差 JSON 不合 schema，quizs 在回合里退回修了一次：%s",
  deliver: "交差 JSON 修过仍不合 schema（或来不及修），quizs 原样交回、由内核复核：%s",
};
/**
 * 第 177 轮：Quizs 当场退回解析不了的最后回答（final_format_rejected 事件；Quizs M8 起，给了 --final-schema 时退回的那一次修正写明哪里坏了：代码块
 * 外有字、代码块不止一个、JSON 在第几个字符解析不下去），也写进这一回合的 warnings，带上头三条原因。
 */
export const QUIZS_FORMAT_NOTE = "交差 JSON 解析不了，quizs 在回合里退回修了一次：%s";
/** 第 136 轮：被花费上限扣下的信，解除时刻写成一个不会自己到点的值；站主用 task cap 提高上限时改成当时。 */
export const SPEND_CAP_UNTIL = "2100-01-01T00:00:00Z";
