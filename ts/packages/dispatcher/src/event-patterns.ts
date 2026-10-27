// 由 ts/packages/dispatcher/tools/gen_event_patterns.py 生成，不要手改：改了 pi_dispatch 的这些正则就重新生成。
// 原文交给 @themis/base/pyregex 的 sre 移植编译（compilePy），语义与 Python 逐字一致。

export const EVENT_PATTERNS = {
  TEMP_PATH_RE: "(?i)\\btempfile\\.\\w+|\\bfrom\\s+tempfile\\s+import\\b|\\b(?:mkdtemp|mkstemp|TemporaryDirectory|NamedTemporaryFile|SpooledTemporaryFile|gettempdir)\\s*\\(|\\bmktemp\\b|New-TemporaryFile|GetTempPath|GetTempFileName|(?<![\\w./~-])(?<!<worktree>)(?:/private)?(?:/var)?/tmp\\b|\\$\\{?(?:TMPDIR|TEMP|TMP)\\b|\\$env:(?:TEMP|TMP)\\b|%(?:TEMP|TMP)%|\\b(?:environ(?:\\.get)?\\s*[\\[(]|getenv\\s*\\()\\s*[\\\"'](?:TMPDIR|TEMP|TMP)[\\\"']|AppData[\\\\/]+Local[\\\\/]+Temp\\b|Windows[\\\\/]+Temp\\b",
  _ABS_PATH_START_RE: "(?m)(?:^|(?<=[\\s=(;|&<>,`\\\"']))(?<!<worktree>)(?:/(?=[\\w.~-])|~(?=[/\\s;|&)<>\\\"'`]|$)|[A-Za-z]:[\\\\/])",
  _DEVICE_PATH_RE: "^/dev/(?:null|stdin|stdout|stderr|tty|fd/\\d+)$",
  _RM_CALL_RE: "\\brm\\s+((?:-[A-Za-z-]+\\s+)+)([^;&|\\n]*)",
  SKIP_MARKER_RE: "\\.(?:skip|only|todo)\\s*\\(|\\b(?:xit|xdescribe|xtest)\\s*\\(|@pytest\\.mark\\.(?:skip|xfail)|@unittest\\.skip|\\bt\\.Skip\\(|#\\[ignore\\]|@Disabled\\b|@Ignore\\b",
  ASSERT_RE: "\\b(?:expect|assert\\w*|should)\\b",
  AMBIGUITY_RE: "(?i)ambigu|contradict|inconsisten|矛盾|歧义|含义不明|前后不一致|说法不一",
  INTERPRETATION_RE: "(?i)judge?ment call|(?:I(?:'ll| will| am going to)?|we(?:'ll| will)?)\\s+(?:note|record|treat|take|log|flag)\\s+(?:this|it|that)\\s+as\\s+(?:an?\\s+|my\\s+|our\\s+)?interpretation|\\b(?:I|we)(?:'ll| will)?\\s+interpret\\b|\\bmy interpretation\\b|\\binterpreting (?:this|the contract|the spec)\\b|\\b(?:I|we)(?:'ll| will)\\s+(?:go with|assume)\\b|我(?:就|暂)?理解为|按我的理解|我的理解是|我把[^，。；\\n]{0,20}(?:理解|解读)(?:成|为)|自行裁定|(?:就|暂)按[^，。；\\n]{0,16}(?:解读|处理|实现)",
  MASKED_EXIT_RE: "(?m)\\|\\s*(?:tail|head|grep|egrep|sed|awk|cut|sort|uniq|wc|cat|less|more|tee)\\b|\\|\\|\\s*(?:true|:)(?=\\s|$)|;\\s*(?:true|exit\\s+0)\\s*$",
  _PIPEFAIL_RE: "pipefail|PIPESTATUS",
  _CHECK_COMMAND_RE: "\\b(?:pytest|unittest|run_tests|npm (?:run )?test|yarn test|pnpm test|go test|cargo test|tox|nox|ctest|make (?:test|check)|compileall|mypy|ruff|flake8|eslint|tsc)\\b",
  _TEMP_DIR_CREATE_RE: "(?i)\\bmkdtemp\\s*\\(|\\bmktemp\\b|New-TemporaryFile|GetTempFileName\\s*\\(",
  _TEMP_DIR_CLEANUP_RE: "(?i)\\brmtree\\b|\\brm\\s+-[A-Za-z]*[rRf]|\\bRemove-Item\\b|\\baddCleanup\\b|\\bcleanup\\s*\\(|\\bunlink\\b|\\bos\\.remove\\b|\\brmdir\\b|\\bDelete\\s*\\(",
  AMBIGUITY_NEGATION_RE: "(?i)(?:\\bun|\\bnon-?)$|(?:\\b(?:no|any|without|never)\\b|(?:\\bnot|n't)\\b)(?:\\s+(?:any|an?|the|real|obvious|apparent|actual|further|other|such|seem|seems|appear|appears|to|be|been|at|all|really|truly|actually|found|detected|see|find|notice|spot|detect|observe|internal|logical|major|significant|material|direct|clear|explicit|evident|remaining|new|unresolved|serious|substantive|meaningful))*\\s+$|(?:没有|并无|不存在|无|并不|不)(?:任何|什么|明显的?|实质性?的?|内在的?|内部的?|逻辑上?的?|发现|看到|找到)*$",
  AMBIGUITY_DOUBLE_NEGATION_RE: "(?i)(?:\\b(?:not|cannot|never|impossible)\\b|n't\\b)[^.;:!?\\n]{0,40}\\bwithout\\b(?:\\s+(?:any|an?|the|real|obvious|apparent|actual|further|other|such|seem|seems|appear|appears|to|be|been|at|all|really|truly|actually|found|detected|see|find|notice|spot|detect|observe|internal|logical|major|significant|material|direct|clear|explicit|evident|remaining|new|unresolved|serious|substantive|meaningful))*\\s+$|(?:\\bnot|n't)\\s+(?:un|non-?)$|(?:并非|不是|并不是|绝非|不)(?:没有|无)(?:任何|什么|明显的?|实质性?的?|内在的?|内部的?|逻辑上?的?|发现|看到|找到)*$",
  AMBIGUITY_RESOLVED_RE: "(?i)^[A-Za-z]{0,12}[ \\t]*[:：?？]?[ \\t]*(?:\\n[ \\t]*(?:[-*>][ \\t]*)?)?(?:none(?: found)?|nothing found|found none|无|没有|未发现|没有发现|没有矛盾|无矛盾|no (?:conflicts?|contradictions?|inconsistenc(?:y|ies)|ambiguit(?:y|ies)|issues?|problems?)(?:[ \\t]+(?:found|detected))?)(?=[ \\t]*(?:(?:[。．；;!！]|\\.(?![\\w(]))(?![ \\t]*\\d)|$|\\n[ \\t]*(?:\\n|[#>*-]|$)))",
  TEXTUAL_TOOL_CALL_RE: "(?i)<tool_call>|</tool_call>|<function=[\\w.-]+>|<\\|tool_call",
  AMBIGUITY_CONTEXT_RE: "(?i)contract|plan|spec|requirement|\\bDoD\\b|\\bstep\\s*\\d|合同|规范|步骤|验收|要求",
  LEFT_EDGE: "(?<![\\w./\\\\~-])",
  PATH_TAIL: "(?:[/\\\\]|$)",
  REMOVE_ITEM: "(?i)\\bRemove-Item\\b",
  SKIP_HEADING: "(?i)## +(?:Stop conditions|Forbidden|停止条件|禁止)",
} as const;

export const SUSPICIOUS_COMMANDS: readonly (readonly [string, string])[] = [
  ["\\bgit\\s+(?:push|commit|merge|rebase|reset|clean|stash(?!\\s+(?:list|show)\\b)|restore|switch|tag(?!\\s+(?:-l|--list)\\b)|checkout\\s+--|branch\\s+-[dD])\\b", "git 写操作"],
  ["\\brm\\s+-[A-Za-z]*[rRf]|\\bRemove-Item\\b.*-Recurse", "递归或强制删除"],
  ["\\b(?:curl|wget|Invoke-WebRequest|iwr|Invoke-RestMethod)\\b", "网络下载"],
  ["\\b(?:npm|pnpm|yarn|bun)\\s+(?:add|install|i|update|upgrade|remove|uninstall|publish)\\b|\\bpip3?\\s+install\\b|\\buv\\s+(?:add|pip)\\b|\\bpoetry\\s+add\\b|\\bcargo\\s+(?:add|install|publish)\\b|\\bgo\\s+get\\b", "依赖变更或发布"],
  ["\\bsudo\\b|\\bchmod\\b|\\bchown\\b|\\bicacls\\b", "权限变更"],
  ["\\b(?:ssh|scp|rsync)\\b", "远程访问"],
  ["(?:^|[;&|]\\s*)(?:env|printenv)\\s*(?:$|[;&|])|\\$env:|Get-ChildItem\\s+env:", "读取环境变量"],
  ["\\.ssh[/\\\\]|id_rsa|id_ed25519|\\.aws[/\\\\]credentials|\\.npmrc|\\.pypirc|auth\\.json", "凭据相关路径"],
];

export const STDERR_WARNING_PATTERNS: readonly (readonly [string, string])[] = [
  ["custom_model_id", "Using custom model id"],
  ["invalid_thinking", "Invalid thinking level"],
  ["unknown_option", "Unknown option"],
  ["extension_error", "Extension error"],
];

export const CACHE_DIR_NAMES: readonly string[] = ["__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis"];
