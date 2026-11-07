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
/** 交差格式（逐字进提示词）。 */
export const OUTPUT_SPECS: Readonly<Record<string, string>> = {
  coordinator: "{\"letters\": [{\"to\": \"<收信人>\", \"type\": \"开工|返工|通过|等待|停止|汇报|提问\", \"task_id\": \"<阶段任务或主任务>\", \"in_reply_to\": \"<msg-id 或 none>\", \"摘要\": \"…\", \"提交\": \"无\", \"验证\": \"…\", \"偏离\": \"无\", \"需协调人决定\": \"无\", \"证据\": \"…\", \"brief\": \"<开工、返工时必填：下一阶段任务书的 Markdown 全文>\"}], \"state\": \"<你的进度断点，Markdown>\"}",
  worker: "{\"letter\": {\"type\": \"交付|返工完成|提问|阻塞|交接|进度\", \"in_reply_to\": \"<msg-id>\", \"摘要\": \"…\", \"提交\": \"…\", \"验证\": \"…\", \"偏离\": \"…\", \"需协调人决定\": \"…\", \"下游须知\": \"…\", \"证据\": \"…\"}, \"report\": \"<report.md 全文>\", \"state\": \"<state.md 全文>\"}",
};
/** 各岗位另加的输出要求（逐字进提示词）。 */
export const ROLE_EXTRA_OUTPUT: Readonly<Record<string, string>> = {
  planner: "另加 \"external_facts\": [{\"fact\": \"<计划依赖的仓库外事实>\", \"source\": \"<出处>\", \"verified\": \"<核实的命令与结果；没核实就写“未核实”>\"}]，没有仓库外事实就写 []",
  contract: "另加 \"contract_md\": \"<合同 Markdown 全文>\"",
  gate: "战后模式把变异清单写进工作目录根下的 mutation-spec.json：{\"commands\": [{\"id\": \"W1\", \"argv\": [\"python\", \"-m\", \"pytest\", \"<文件>\", \"-q\"]}], \"mutations\": [{\"name\": \"…\", \"file\": \"<相对路径>\", \"old\": \"<原文片段>\", \"new\": \"<改坏后的片段>\"}]}，输出里另加 \"mutation_spec_file\": \"mutation-spec.json\"，不要再把清单抄进输出（内核读的就是这个文件）；commands 里每一条都是检验命令，每条变异缺省要被每一条抓住，某条命令本来就测不到的变异（例如静态检查碰不到的行为改动），在那一条里加 \"expect_missed\": [\"<命令 id>\"]（至少留一条命令抓它，终审会看）；安装依赖这类准备步骤不要放进 commands：mutate 在你的工作目录里原地跑，依赖在你的回合里照合同的 setup 装好就在；交差前在工作目录里把 commands 每条跑一遍、都要退出 0（mutate 的基线就是这一步，缺依赖、cwd 错、路径错都能当场发现）；确实测不出来的等价改写，在那一条里加 \"equivalent\": \"<为什么改了行为也不变>\"（终审会逐条复核），其余每条都必须被抓住；执行端改动的每个非测试文件至少一条变异，确实没法变异的（例如二进制文件）另加 \"unmutated\": [{\"file\": \"<相对路径>\", \"reason\": \"<为什么>\"}]（终审会复核）；候选不满足合同写明的行为时另加 \"candidate_defects\": [{\"test\": \"<红的用例 node id 或函数名>\", \"contract\": \"<合同原文>\", \"where\": \"<候选文件:行>\"}]（这时可以不给 mutation_spec_file）",
  audit: "letter 里另加三项，都要写：\"结论\": \"通过|返工\"（交付以外的信写“无”）；\"退回\": \"合同端|门禁端|战后门禁|执行端|规划端\"（一审只能退回规划端、合同端、门禁端；几个对象都要改时用“、”隔开，例如 \"合同端、门禁端\"；不是返工写“无”）；\"阻塞项\": \"<逐条列出必须改的问题，只列会导致打回的；退回几个对象时注明每条归谁>\"（不是返工写“无”）",
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
];
/** 第 38 轮：pi 的模型接口限流时扣信退避（秒），连着限流太多次就照旧按接口报错交给站主。 */
export const THROTTLE_BACKOFF_SECONDS = 300;
export const THROTTLE_BACKOFF_MAX = 3600;
export const THROTTLE_MAX_HOLDS = 5;
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
  ["--max-requests", "32"], ["--max-tool-calls", "48"], ["--max-input-bytes", "2097152"], ["--max-response-bytes", "4194304"],
];
/** 第 145 轮：quizs 因模型的做法结束回合的错误类别（不是环境问题）：记成交差不合格，内核带着这段说明当场重交一次。 */
export const QUIZS_BEHAVIOR_ERRORS: Readonly<Record<string, string>> = {
  BUDGET_EXHAUSTED: "这一回合用完了请求或工具调用的预算还没交差。重交时少翻目录，只读要用的文件，尽早写出 json 代码块",
  POLICY: "调了没有授权的工具。交差不调用任何工具，把 json 代码块直接写在最后的回答里",
  TOOL_ERROR: "工具参数不合格式（JSON、路径写法或字段），回合被 Quizs 结束。重交时照工具说明写参数",
};
/** 第 142 轮：quizs 排队超时＝提供方的并发名额被占（Quizs 对一个提供方账户只开 1 个名额；结果不明的请求一直占着，要站主核实后释放）。 */
export const QUIZS_PERMIT_HELD = "quizs 退出码 5（QUEUE_TIMEOUT）：提供方的并发名额被占着。要么另一个 quizs 回合正在用（等它结束即可）；"
  + "要么之前有一次请求结果不明（例如 DeepSeek 回了 500 或连接中途断开），Quizs 不判定它已结束，名额一直占着，之后的回合都会排队超时。"
  + "站主处理：在信箱目录下运行 quizs permits list --provider-state-dir quizs-state 看占着的是哪一条；状态是 unknown_remote 的，"
  + "先到 DeepSeek 后台核实那次请求已经结束，再运行 quizs permits release --provider-state-dir quizs-state --attempt-id <那一条的 attempt_id> --confirm-terminal 释放";
/** 第 141 轮：真实请求要的三份文件（Quizs 的 live plan、提供方档案与资格证书）由环境给路径；测试与 fake 提供方都不设。 */
export const QUIZS_LIVE_FILES: readonly (readonly [string, string])[] = [
  ["--live-plan", "QUIZS_LIVE_PLAN"], ["--provider-profile", "QUIZS_PROVIDER_PROFILE"], ["--qualification", "QUIZS_QUALIFICATION"],
];
/** 第 136 轮：被花费上限扣下的信，解除时刻写成一个不会自己到点的值；站主用 task cap 提高上限时改成当时。 */
export const SPEND_CAP_UNTIL = "2100-01-01T00:00:00Z";
