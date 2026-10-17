# TASK: normalize-query

<!-- 示例：假设的 TypeScript + pnpm + vitest 仓库。路径、函数与基线 ID 都是虚构的，
     真实使用时必须在仓库中调查后替换；base_sha 不替换会被校验器拒绝。 -->

## Identity
- plan_version: 1
- repository: example-search-app
- base_sha: 0123456789abcdef0123456789abcdef01234567
- risk_level: low
- authorized_actions: local_edit, local_test
- integration_actions: local_branch
- executor: step/step-5-preview · thinking high

## Goal
`normalizeQuery(input)` 返回用于检索的规范化查询串：去掉首尾空白，内部连续空白压成一个 ASCII 空格，全角字符做 NFKC 规范化，然后转成小写。

## Non-goals
- 不改变 `src/search/index.ts` 的调用方式与检索逻辑。
- 不处理非字符串输入（类型系统已约束），不增加长度限制。
- 不引入新依赖，不修改 lint、tsconfig 或测试配置。

## Repository facts
- 入口：`src/search/normalize.ts` 导出 `export function normalizeQuery(input: string): string`，当前实现只有 `return input.trim();`。
- 调用方：`src/search/index.ts` 的 `search()` 在查询前调用一次 `normalizeQuery`；没有其他调用方（`rg -n normalizeQuery src` 确认）。
- 工具链：Node 22、pnpm 9（`pnpm-lock.yaml`）、vitest 3、TypeScript 5（`tsconfig.json` 开启 strict）。
- 基线检查：`pnpm exec vitest run` 全部通过（42 tests）；`pnpm exec tsc --noEmit -p tsconfig.json` 通过。

## Scope
- allowed_modified_files:
  - src/search/normalize.ts
- allowed_new_files:
  - src/search/normalize.test.ts
- allowed_deleted_files: 无
- forbidden_paths: package.json、pnpm-lock.yaml、tsconfig.json、vitest.config.ts
- dependency_changes: forbidden
- 始终禁止：本合同、AGENTS.md（及 CLAUDE.md，如有）、.agent/、.agents/、.claude/、.codex/、.pi/、scripts/pi_dispatch.py、scripts/dispatch-pi.sh

## Behavior contract
- 正常输入：`"  Hello   World "` → `"hello world"`。
- 边界输入：`""` 与只含空白的串（包括全角空格 U+3000、制表符、换行）→ `""`。
- 全角：`"ＡＢＣ　１２３"` → `"abc 123"`（先 NFKC，再压缩空白，再小写）。
- 大小写：使用 `String.prototype.toLowerCase()`，不使用 locale 相关的方法；`"İSTANBUL"` 的结果与 `toLowerCase()` 一致即可。
- 错误与重试：纯函数，不抛出新的异常。
- 并发、取消与状态：不适用（无状态纯函数）。
- 兼容性：函数签名与导出名不变。

## Steps
1. 读取 `src/search/normalize.ts` 与 `src/search/index.ts`，确认签名与 Repository facts 一致；不一致就停止并报告。
2. 按 Behavior contract 的顺序实现：`input.normalize("NFKC")` → 用 `/\s+/gu` 压缩并 trim → `toLowerCase()`。
3. 新建 `src/search/normalize.test.ts`，为 Behavior contract 的每一条写至少一个用例，用例名以 D01…D04 开头。
4. 运行 V01 与 V02，记录结果。
5. 写执行报告。

## Validation commands
- V01（必要）：`pnpm exec vitest run src/search/normalize.test.ts` · cwd：仓库根 · 超时：300s · 期望退出码：0 · 输出须匹配 `Tests\s+[1-9]\d* passed`，不得出现 `No test files found`
- V02（必要）：`pnpm exec tsc --noEmit -p tsconfig.json` · cwd：仓库根 · 超时：300s · 期望退出码：0

## Definition of done
- D01：首尾空白去除、内部空白压缩；证据：V01 中 `D01` 开头的用例。
- D02：空串与纯空白（含全角空格）返回空串；证据：V01 中 `D02` 开头的用例。
- D03：全角字符经 NFKC 规范化；证据：V01 中 `D03` 开头的用例。
- D04：小写化不依赖 locale；证据：V01 中 `D04` 开头的用例。
- D05：类型检查通过，签名不变；证据：V02。
- D06：所有修改都在允许集合内；证据：scope。
- D07：没有删除、跳过或弱化既有测试；证据：review。

## Stop conditions
- `normalizeQuery` 的签名或调用方与 Repository facts 不符。
- 需要修改允许范围之外的文件（包括测试配置）才能让测试运行。
- 需要新增依赖。
- 发现 Behavior contract 没有覆盖、且会影响检索结果的输入类别。
- 达到单轮时限。

## Budget
- max_attempts_total: 2
- max_wall_seconds_per_attempt: 1200
- max_wall_seconds_total: 2400
- cost_budget: tracking-only
- 强制方：调度器强制次数与墙钟；费用只统计

## Report back
- 最后一条消息是执行报告：逐项说明 D01–D07，列出实际运行的 V01、V02 命令与结果、遗留问题，末尾附执行说明规定的 JSON 代码块。

## Forbidden
- 不修改本合同、调度脚本、代理规则或权限配置。
- 不删除、跳过或弱化测试。
- 不提交、推送、合并或部署。
- 不更换模型或提供商，不调用未授权的外部服务，不读取或输出凭据。
