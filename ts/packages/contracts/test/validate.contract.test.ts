// kit_config 整份校验的契约（迁移第 ③a2 片）：validate_config 的每个键、plugins 的修复提示、读配置文件、kit_roles 的 v3 键。
// 报错会进 validate 与 show 的输出、桌面端的预览，逐字比较。每条先断言 Python 的结果，再要求 TS 两种运行方式逐字一致。
// kit_root 用仓库本身（只读 plugins/）或临时目录里复制的一份；仓库也是临时目录，不碰真实配置。
import { cpSync, mkdirSync, realpathSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { type ProbeRequest, type ProbeResult, REPO, removeDir, runAgreeing, scratchDir } from "./harness.ts";

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };

// 仓库根照 Repo.discover 的写法用解析过的真实路径（临时目录可能带 8.3 短名，is_within 只做词法比较）
const ROOT = realpathSync.native(scratchDir("validate"));
const REPO_DIR = join(ROOT, "repo");
mkdirSync(join(REPO_DIR, ".agent"), { recursive: true });
afterAll(() => removeDir(ROOT));

const KNOWN = "allowed_executors, worktree_root, kill_grace_seconds, check_artifact_patterns, extra_protected_paths, planner_paths, commit_trailers, env_remove, env_keep, release_check, pricing, decisions, plugins, runtimes, profiles, roles, presets, active_preset";
const TOKEN = `sk-${"a1".repeat(12)}`;

const call = (fn: string, config: Json | string | undefined, extra: Record<string, unknown> = {}): ProbeRequest => ({
  op: "config.call",
  fn,
  kit_root: REPO,
  repo: REPO_DIR,
  ...(config === undefined ? {} : { config: typeof config === "string" ? config : JSON.stringify(config) }),
  ...extra,
});
const validate = (config: Json | string, extra: Record<string, unknown> = {}): ProbeRequest => call("validate_config", config, extra);

interface Case {
  readonly name: string;
  readonly request: ProbeRequest;
  readonly check: (result: ProbeResult) => string | null;
}

/** 结果里的字符串列表（validate_config、config_errors）。 */
function strings(result: ProbeResult): string[] | null {
  const value = result["value"] as { t: string; v: { v: string }[] } | undefined;
  return value?.t === "list" ? value.v.map((item) => item.v) : null;
}

const errors = (name: string, request: ProbeRequest, expected: string[]): Case => ({
  name,
  request,
  check: (result) => (JSON.stringify(strings(result)) === JSON.stringify(expected) ? null : JSON.stringify(result)),
});
const contains = (name: string, request: ProbeRequest, fragment: string): Case => ({
  name,
  request,
  check: (result) => ((strings(result) ?? []).some((item) => item.includes(fragment)) ? null : JSON.stringify(result)),
});
const raised = (name: string, request: ProbeRequest, error: string, message?: string): Case => ({
  name,
  request,
  check: (result) => (result["error"] === error && (message === undefined || result["message"] === message) ? null : JSON.stringify(result)),
});
const okCase = (name: string, request: ProbeRequest): Case => ({ name, request, check: (result) => (result.ok ? null : JSON.stringify(result)) });

function verifyAll(cases: readonly Case[]): void {
  const { python, mismatches } = runAgreeing(cases.map((item) => item.request));
  const wrong = cases.flatMap((item, index) => {
    const problem = item.check(python[index] as ProbeResult);
    return problem === null ? [] : [{ name: item.name, python: problem }];
  });
  expect(wrong, "Python 的结果不符合契约").toEqual([]);
  expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
}

const PRICE = { input: 1, output: 2, source: "price page 2026-10-01", as_of: "2026-10-01" };
const RUNTIMES = { pi: { adapter: "pi" } };
const PROFILES = { exec: { runtime: "pi", model: { provider: "step", id: "step-5" }, options: { thinking: "high" }, credential_env: ["STEP_KEY"] } };

describe("validate_config：各键", () => {
  it("契约", () => {
    verifyAll([
      errors("空配置", validate({}), []),
      errors("未知键", validate({ zz: 1 }), [`未知键 'zz'（已知：${KNOWN}）`]),
      errors("像令牌的未知键不回显", validate({ [TOKEN]: 1 }), [`未知键 （疑似凭据的键名）（已知：${KNOWN}）`]),
      errors("说明键里有令牌", validate({ _note: TOKEN }), ["_note 里有疑似凭据（_note）：配置里只写环境变量名，凭据的值用 config secret set 存"]),
      errors(
        "疑似凭据超过五处时只列前五处",
        validate({ _note: { a: TOKEN, b: TOKEN, c: TOKEN, d: TOKEN, e: TOKEN, f: TOKEN } }),
        ["_note 里有疑似凭据（_note.a、_note.b、_note.c、_note.d、_note.e）：配置里只写环境变量名，凭据的值用 config secret set 存"],
      ),
      {
        name: "两个像令牌的说明键报同一句时只报一次",
        request: validate({ [`_a ${TOKEN}`]: 1, [`_b sk-${"b2".repeat(12)}`]: 2 }),
        check: (result) => (strings(result)?.length === 1 ? null : JSON.stringify(result)),
      },
      errors("allowed_executors 不是数组", validate({ allowed_executors: {} }), ["allowed_executors 必须是数组"]),
      errors("allowed_executors 的项缺 model", validate({ allowed_executors: [{ provider: "step" }] }), ["allowed_executors[0] 必须是 {provider, model[, thinking]}"]),
      errors("allowed_executors 的标识不合法", validate({ allowed_executors: [{ provider: "st ep", model: "m" }] }), ["allowed_executors[0].provider 不是合法的标识：'st ep'"]),
      errors("allowed_executors 的 thinking 不认识", validate({ allowed_executors: [{ provider: "s", model: "m", thinking: "huge" }] }), ["allowed_executors[0].thinking 必须是 off/minimal/low/medium/high/xhigh/max 之一"]),
      errors("allowed_executors 有未知键", validate({ allowed_executors: [{ provider: "s", model: "m", zz: 1, aa: 2 }] }), ["allowed_executors[0] 有未知键：aa, zz"]),
      errors("worktree_root 不是字符串", validate({ worktree_root: 5 }), ["worktree_root 必须是路径字符串或 null"]),
      contains("worktree_root 在仓库里", validate({ worktree_root: join(REPO_DIR, "wt") }), "worktree_root 不能位于仓库内部："),
      contains("环境变量指的 worktree_root 在仓库里", validate({}, { env: { PI_DISPATCH_WORKTREE_ROOT: join(REPO_DIR, "x") } }), "worktree_root 不能位于仓库内部："),
      contains("临时目录在仓库里，缺省的 worktree_root 也就在仓库里", validate({}, { env: { TMPDIR: REPO_DIR, PI_DISPATCH_WORKTREE_ROOT: null } }), "worktree_root 不能位于仓库内部："),
      errors("worktree_root 用 ~", validate({ worktree_root: "~/pi-worktrees" }), []),
      errors("kill_grace_seconds 为 0", validate({ kill_grace_seconds: 0 }), ["kill_grace_seconds 必须是 0 到 600 之间的秒数"]),
      errors("kill_grace_seconds 为 null", validate({ kill_grace_seconds: null }), ["kill_grace_seconds 必须是 0 到 600 之间的秒数"]),
      errors("kill_grace_seconds 为 600", validate({ kill_grace_seconds: 600 }), []),
      raised("kill_grace_seconds 超出 double（Python 打堆栈）", validate(`{"kill_grace_seconds": 1${"0".repeat(400)}}`), "OverflowError"),
      errors("check_artifact_patterns 有空串", validate({ check_artifact_patterns: [""] }), ["check_artifact_patterns 必须是仓库相对 glob 的数组"]),
      errors("check_artifact_patterns 是绝对路径", validate({ check_artifact_patterns: ["C:x"] }), ["check_artifact_patterns 的 'C:x'：不能是绝对路径"]),
      errors("check_artifact_patterns 有反斜杠", validate({ check_artifact_patterns: ["a\\b"] }), ["check_artifact_patterns 的 'a\\\\b'：请使用正斜杠"]),
      errors("check_artifact_patterns 太宽", validate({ check_artifact_patterns: ["**/*"] }), ["check_artifact_patterns 的 '**/*'：范围过宽"]),
      errors("extra_protected_paths 有 ..", validate({ extra_protected_paths: ["a/../b"] }), ["dispatch.config.json 的 extra_protected_paths 必须是仓库相对路径模式的数组"]),
      errors("planner_paths 不是数组", validate({ planner_paths: "x" }), ["dispatch.config.json 的 planner_paths 必须是仓库相对路径模式的数组"]),
      errors("commit_trailers 合法", validate({ commit_trailers: ["Co-Authored-By: someone"] }), []),
      errors("commit_trailers 冒号后是全角空格（Python 的 \\S 不配它）", validate({ commit_trailers: ["Key: 　x"] }), ["dispatch.config.json 的 commit_trailers 必须是单行 `Key: value` 字符串数组，不能含回车、换行等控制字符"]),
      errors("env_remove 有不合法的名字", validate({ env_remove: ["1X"] }), ["env_remove 必须是环境变量名的数组"]),
      errors("release_check 有未知键", validate({ release_check: { x: 1 } }), ["release_check 只能有 allow（规则数组）与 denylist（路径）两个键"]),
      errors("release_check.denylist 不是字符串", validate({ release_check: { denylist: 1 } }), ["release_check.denylist 必须是路径字符串"]),
      errors("release_check 的规则没有冒号", validate({ release_check: { allow: ["nocolon"] } }), ["release-check 的允许规则要写成 <glob>:<模式名>，例如 tests/fixtures/**:home path：'nocolon'"]),
      errors("release_check 的模式名不认识", validate({ release_check: { allow: ["a/**: bogus "] } }), ["release-check 没有名为 'bogus' 的模式（可用：api key、home path、private address 或 *）"]),
      errors("release_check.allow 是字符串时按字符拆", validate({ release_check: { allow: "a:b" } }), ["release-check 的允许规则要写成 <glob>:<模式名>，例如 tests/fixtures/**:home path：'a'"]),
      raised("release_check.allow 为 null（Python 打堆栈）", validate({ release_check: { allow: null } }), "TypeError"),
      errors("release_check 合法", validate({ release_check: { allow: ["tests/**:home path", "x:*"], denylist: "d.txt" } }), []),
      errors("release_check 的 glob 里有冒号：按最后一个冒号切", validate({ release_check: { allow: ["C:/fixtures/**:home path"] } }), []),
      errors("pricing 合法", validate({ pricing: { "step/step-5": PRICE } }), []),
      errors("pricing 的键不是 <provider>/<model>", validate({ pricing: { step: PRICE } }), ["dispatch.config.json 的 pricing 无效：键 'step' 必须是 <provider>/<model>"]),
      errors("pricing 缺 output", validate({ pricing: { "s/m": { ...PRICE, output: null } } }), ["dispatch.config.json 的 pricing 无效：s/m 缺少 output 单价"]),
      errors("pricing 的单价为负", validate({ pricing: { "s/m": { ...PRICE, cache_read: -1 } } }), ["dispatch.config.json 的 pricing 无效：s/m.cache_read 必须是非负数"]),
      // 第 125 轮：pricing.<模型>.per_tokens 的值是数字时不算疑似凭据；写成字符串照算
      errors("pricing 写了 per_tokens（数字）", validate({ pricing: { "s/m": { ...PRICE, per_tokens: 1000 } } }), []),
      errors("pricing 的 per_tokens 写成字符串：照算疑似凭据", validate({ pricing: { "s/m": { ...PRICE, per_tokens: "1000" } } }), ["pricing 里有疑似凭据（pricing.s/m.per_tokens）：配置里只写环境变量名，凭据的值用 config secret set 存"]),
      errors("pricing 的币种末尾换行照 Python 的 $ 放过", validate({ pricing: { "s/m": { ...PRICE, currency: "EUR\n" } } }), []),
      errors("pricing 的日期是阿拉伯-印度数字（Python 的 \\d 认）", validate({ pricing: { "s/m": { ...PRICE, as_of: "٢٠٢٦-١٠-٢٦" } } }), []),
      errors("pricing 的来源只有空白", validate({ pricing: { "s/m": { ...PRICE, source: "　" } } }), ["dispatch.config.json 的 pricing 无效：s/m.source 必须写明价格来源（例如价格页与访问日期）"]),
      errors("pricing 有未知字段", validate({ pricing: { "s/m": { ...PRICE, zz: 1, aa: 1 } } }), ["dispatch.config.json 的 pricing 无效：s/m 有未知字段 aa, zz"]),
      errors("decisions 的 mode 不认识", validate({ decisions: { mode: "x" } }), ["decisions 无效：decisions.mode must be one of off, shadow, on"]),
      errors("decisions 生效、仓库里的题库与锁一致", validate({ decisions: { mode: "on" } }), []),
      errors("plugins 合法", validate({ plugins: { enabled: ["decisions"], allowed_permissions: ["network-decisions"], _note: "x" } }), []),
      errors("plugins.enabled 有重复", validate({ plugins: { enabled: ["b", "a", "b", "a"] } }), ["plugins.enabled 有重复项：a, b"]),
      errors("plugins.enabled 有大写", validate({ plugins: { enabled: ["Bad"] } }), ['plugins.enabled[0] 不是合法的插件 ID："Bad"']),
      errors("plugins 有未知子键", validate({ plugins: { zz: 1 } }), ["plugins 有未知子键：zz（只允许 enabled、allowed_permissions 与下划线开头的说明）"]),
      errors("plugins.allowed_permissions 有空串", validate({ plugins: { allowed_permissions: [""] } }), ['plugins.allowed_permissions[0] 必须是非空字符串：""']),
      errors("plugins.enabled 不是列表：修复提示删掉这个子键", validate({ plugins: { enabled: "decisions" } }), ['plugins.enabled 必须是列表，现在是 "decisions"；不写这个子键表示不限制；修复：config unset plugins.enabled']),
      errors("plugins 不是对象：修复提示删掉整段", validate({ plugins: [1, "a"] }), ['plugins 必须是对象（子键 enabled、allowed_permissions），现在是 [1, "a"]；修复：config unset plugins']),
      errors("不要修复提示时只报格式", validate({ plugins: { enabled: 1 } }, { hints: false }), ["plugins.enabled 必须是列表，现在是 1；不写这个子键表示不限制"]),
      errors("runtimes 的 adapter 不认识", validate({ runtimes: { pi: { adapter: "x" } } }), ["runtimes.pi.adapter 必须是 pi、claude-code、codex、opencode 之一"]),
      errors("profiles 合法", validate({ runtimes: RUNTIMES, profiles: PROFILES }), []),
      errors(
        "profiles 的几处毛病一起报（中文分号连接）",
        validate({ runtimes: RUNTIMES, profiles: { Bad: { runtime: "nope", model: { provider: "s", id: "REPLACE_WITH_ID" }, options: { thinking: "x" }, credential_env: "K", zz: 1 } } }),
        ["profiles.Bad：ID 不合法；profiles.Bad 有未知键：zz；profiles.Bad.runtime 'nope' 没有登记（或它的 adapter 无效）；profiles.Bad.model.id 必须是精确的 ID；profiles.Bad.credential_env 必须是环境变量名的数组"],
      ),
      errors("profiles 里有令牌：只报位置", validate({ runtimes: RUNTIMES, profiles: { exec: { ...PROFILES.exec, note: TOKEN } } }), ["profiles 里有疑似凭据（profiles.exec.note）：配置里只写环境变量名，凭据的值用 config secret set 存"]),
      errors("roles 的 mode 不对", validate({ roles: { execution: { mode: "manual" } } }), ["roles.execution.mode 必须是 headless 之一（当前 'manual'）"]),
      errors("roles 的 profile 没登记", validate({ roles: { execution: { mode: "headless", profile: "ghost" } } }), ["roles.execution.profile 'ghost' 没有登记"]),
      errors("角色绑定里的说明键不算多余的键", validate({ runtimes: RUNTIMES, profiles: PROFILES, roles: { execution: { mode: "headless", profile: "exec", _why: "说明" } } }), []),
      errors("scheduler_agent 的节奏太短", validate({ runtimes: RUNTIMES, profiles: PROFILES, roles: { scheduler_agent: { mode: "headless", profile: "exec", cadence_seconds: 59 } } }), ["roles.scheduler_agent.cadence_seconds 必须是至少 60 的整数"]),
      errors("roles 有未知角色", validate({ roles: { boss: { mode: "x" }, zed: 1 } }), ["roles 有未知角色：boss、zed（只有 planning_review、contract、execution、scheduler_agent）"]),
      errors("presets 没写角色", validate({ presets: { day: { roles: { _note: "x" } } } }), ["presets.day.roles 至少写一个角色"]),
      errors("active_preset 不是已有的方案", validate({ active_preset: "night" }), ["active_preset 'night' 不是已有的方案"]),
      errors("active_preset 像令牌时不显示", validate({ active_preset: TOKEN }), ["active_preset 里有疑似凭据（active_preset）：配置里只写环境变量名，凭据的值用 config secret set 存"]),
      errors("active_preset 是数字", validate({ active_preset: 1 }), ["active_preset （值不显示） 不是已有的方案"]),
    ]);
  });
});

describe("plugins 的修复提示与题库", () => {
  it("决策插件生效、题库不一致时，换成“已安装插件减去 decisions”", () => {
    const kit = join(ROOT, "drift-kit");
    cpSync(join(REPO, "plugins"), join(kit, "plugins"), { recursive: true });
    writeFileSync(join(kit, "plugins", "decisions", "questions", "extra.json"), "{}");
    const broken = join(ROOT, "no-plugins-kit");
    mkdirSync(broken);
    verifyAll([
      contains("题库多出一份", validate({ decisions: { mode: "on" } }, { kit_root: kit }), "decisions 的问题清单与插件内容锁不符：extra.json is not in the lock"),
      errors(
        "plugins.enabled 非法且决策插件生效：删掉子键不够，只能换成显式列表",
        validate({ decisions: { mode: "on" }, plugins: { enabled: 1, _keep: "'quoted'" } }, { kit_root: kit }),
        [
          `decisions 的问题清单与插件内容锁不符：extra.json is not in the lock; after a reviewed change run: python scripts/codekit/decisions.py --write-lock ${join(kit, "plugins", "decisions")}`,
          'plugins.enabled 必须是列表，现在是 1；不写这个子键表示不限制；修复：config set plugins \'{"_keep":"\\u0027quoted\\u0027","enabled":["code-change","docs-change","docs-checks","mutation-review","python-checks","regression-tests","repo-analysis"]}\'',
        ],
      ),
      okCase("修复提示单独算", call("plugins_fix_hint", { plugins: { enabled: 1, allowed_permissions: 2 } })),
      okCase("plugins 段的格式错误（不带提示）", call("plugins_section_error", { plugins: { enabled: 1 } })),
      okCase("kit 下没有 plugins/ 时没有插件可列", call("plugins_fix_hint", { decisions: { mode: "on" }, plugins: "x" }, { kit_root: broken })),
    ]);
  });
});

describe("读配置文件与其他入口", () => {
  it("load_config、config_errors、pricing_table、worktree_root", () => {
    const cases: [string, string | Buffer][] = [
      ["ok", '{"kill_grace_seconds": 20, "_note": "x"}'],
      ["bad-json", "{\r\n  \"a\": \r\n}"],
      ["bom", '\uFEFF{"a": 1}'],
      ["bad-utf8", Buffer.from([0x7b, 0x22, 0xff, 0x22, 0x3a, 0x31, 0x7d])],
      ["list", "[1]"],
      ["deep", `${"[".repeat(5000)}${"]".repeat(5000)}`],
    ];
    const requests: Case[] = [];
    for (const [name, content] of cases) {
      const repo = join(ROOT, `load-${name}`);
      mkdirSync(join(repo, ".agent"), { recursive: true });
      writeFileSync(join(repo, ".agent", "dispatch.config.json"), content);
      requests.push({ name, request: call("load_config", undefined, { repo }), check: () => null });
    }
    const asDir = join(ROOT, "load-dir");
    mkdirSync(join(asDir, ".agent", "dispatch.config.json"), { recursive: true });
    const missing = join(ROOT, "load-missing");
    mkdirSync(join(missing, ".agent"), { recursive: true });
    verifyAll([
      ...requests,
      raised("配置文件是目录", call("load_config", undefined, { repo: asDir }), "ConfigError"),
      okCase("配置文件不存在", call("load_config", undefined, { repo: missing })),
      okCase("config_errors", call("config_errors", { runtimes: { pi: { adapter: "x" } }, active_preset: "y" })),
      okCase("pricing_table 补上缺省的 per_tokens 与币种", call("pricing_table", { pricing: { "s/m": PRICE } })),
      okCase("worktree_root 缺省在临时目录下", call("worktree_root", {}, { env: { PI_DISPATCH_WORKTREE_ROOT: null } })),
      okCase("worktree_root 的 ~ 展开", call("worktree_root", { worktree_root: "~\\wt" })),
    ]);
  });
});
