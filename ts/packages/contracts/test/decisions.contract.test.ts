// codekit/decisions.py 里配置中心用到的部分的契约（迁移第 ③a1 片）：问题的形状、问题清单与内容锁、配置解析与生效模式，
// 以及 pi_dispatch.battery_link_problem。报错会经 validate、show 进输出，逐字比较。每条先断言 Python 的结果，再要求
// TS 两种运行方式与 Python 逐字一致。磁盘上的用例都在临时目录里，从 plugins/decisions 复制一份再改坏，不碰仓库。
import { cpSync, mkdirSync, readFileSync, renameSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterAll, describe, expect, it } from "vitest";
import { type ProbeRequest, type ProbeResult, REPO, removeDir, runAgreeing, scratchDir } from "./harness.ts";

type Json = null | boolean | number | string | Json[] | { [key: string]: Json };

interface Case {
  readonly name: string;
  readonly request: ProbeRequest;
  /** 对 Python 结果的断言：返回 null 表示符合，否则返回说明。 */
  readonly check: (result: ProbeResult) => string | null;
}

const decisions = (fn: string, fields: Record<string, unknown>): ProbeRequest => ({ op: "decisions.call", fn, ...fields });
const question = (name: string, value: Json | string): ProbeRequest =>
  decisions("check_question", { name, question: typeof value === "string" ? value : JSON.stringify(value) });
const settings = (config: Json | string, agentDir?: string, pluginDir?: string): ProbeRequest =>
  decisions("settings_from_config", { config: typeof config === "string" ? config : JSON.stringify(config), agent_dir: agentDir ?? "", plugin_dir: pluginDir ?? "" });

const ok = (name: string, request: ProbeRequest): Case => ({ name, request, check: (result) => (result.ok ? null : JSON.stringify(result)) });
const valueError = (name: string, request: ProbeRequest, message: string): Case => ({
  name,
  request,
  check: (result) => (result["error"] === "ValueError" && result["message"] === message ? null : JSON.stringify(result)),
});
const decisionError = (name: string, request: ProbeRequest, code: string, detail: string | RegExp): Case => ({
  name,
  request,
  check: (result) => {
    const actual = String(result["detail"]);
    const matches = typeof detail === "string" ? actual === detail : detail.test(actual);
    return result["error"] === "DecisionError" && result["code"] === code && matches ? null : JSON.stringify(result);
  },
});
const crash = (name: string, request: ProbeRequest, kind: string): Case => ({ name, request, check: (result) => (result["error"] === kind ? null : JSON.stringify(result)) });
/** settings_from_config 通过时，结果里的某个字段等于期望值。 */
const settled = (name: string, request: ProbeRequest, field: string, expected: string): Case => ({
  name,
  request,
  check: (result) => {
    const pairs = (result["value"] as { v: [{ v: string }, { v: unknown }][] } | undefined)?.v ?? [];
    const found = pairs.find(([key]) => key.v === field)?.[1].v;
    return result.ok && found === expected ? null : JSON.stringify(result);
  },
});

function verifyAll(cases: readonly Case[]): void {
  const { python, mismatches } = runAgreeing(cases.map((item) => item.request));
  const wrong = cases.flatMap((item, index) => {
    const problem = item.check(python[index] as ProbeResult);
    return problem === null ? [] : [{ name: item.name, python: problem }];
  });
  expect(wrong, "Python 的结果不符合契约").toEqual([]);
  expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
}

const NOUL = { type: "noul", instructions: "Did every test pass?" };

describe("问题的形状（check_question）", () => {
  it("契约", () => {
    verifyAll([
      ok("合法的 noul", question("passed", NOUL)),
      ok("noul 的 criteria 为 null 当作没有", question("passed", { ...NOUL, criteria: null })),
      ok("合法的 choice（选项描述可以为 null）", question("pick", { type: "choice", instructions: "Which?", criteria: { a: null, b: "B" } })),
      ok("合法的 score", question("rate", { type: "score", instructions: "How good?", criteria: ["low", { x: 1 }, ["y"]] })),
      valueError("不是对象", question("q", [1]), 'question "q" must be an object like {"type": ..., "instructions": ...}'),
      valueError("未知键按码点排序", question("q", { ...NOUL, zz: 1, "😀": 1, aa: 1 }), "question \"q\" has unknown keys ['aa', 'zz', '😀']"),
      valueError("没有 type", question("q", { instructions: "x" }), 'question "q" has type None; use one of choice, score, noul'),
      valueError("type 是对象", question("q", { type: { a: [1, 2.5, true] }, instructions: "x" }), "question \"q\" has type {'a': [1, 2.5, True]}; use one of choice, score, noul"),
      valueError("type 是浮点数", question("q", '{"type": 1e16, "instructions": "x"}'), 'question "q" has type 1e+16; use one of choice, score, noul'),
      valueError("instructions 只有全角空格", question("q", { type: "noul", instructions: "　\n" }), 'question "q" has no instructions: the text of the question, as a string'),
      valueError("instructions 只是重复名字", question("Is it_OK?", { type: "noul", instructions: "is-it ok" }), 'question "Is it_OK?" asks nothing: its instructions only repeat its own name'),
      valueError("名字里的 Σ 与 σ 小写后相同", question("ΑΣ", { type: "noul", instructions: "ας" }), 'question "ΑΣ" asks nothing: its instructions only repeat its own name'),
      ok("名字与 instructions 只差一个非 ASCII 的单词字符", question("abc", { type: "noul", instructions: "abcé" })),
      valueError("名字正好 81 个码点时截短", question("x".repeat(81), { type: "bad", instructions: "x" }), `question "${"x".repeat(77)}..." has type 'bad'; use one of choice, score, noul`),
      valueError("名字正好 80 个码点时不截短", question("x".repeat(80), { type: "bad", instructions: "x" }), `question "${"x".repeat(80)}" has type 'bad'; use one of choice, score, noul`),
      valueError("名字超过 80 个码点时截短", question("😀".repeat(100), { type: "bad", instructions: "x" }), `question "${"😀".repeat(77)}..." has type 'bad'; use one of choice, score, noul`),
      valueError("noul 的 criteria 有别的键", question("q", { ...NOUL, criteria: { true: "a", maybe: "b" } }), 'question "q" is a noul: criteria can only be {"true": ..., "false": ...}'),
      valueError("noul 的 criteria 是空对象", question("q", { ...NOUL, criteria: {} }), 'question "q" is a noul: criteria can only be {"true": ..., "false": ...}'),
      valueError("noul 的 criteria 值是数字", question("q", { ...NOUL, criteria: { true: 1 } }), 'question "q": noul criteria must be text, objects or arrays'),
      valueError("choice 只有一个选项", question("q", { type: "choice", instructions: "x", criteria: { a: "A" } }), 'question "q": a choice needs an object of at least two options'),
      valueError(
        "choice 有 256 个选项",
        question("q", { type: "choice", instructions: "x", criteria: Object.fromEntries(Array.from({ length: 256 }, (_, index) => [`o${index}`, null])) }),
        'question "q": a choice takes at most 255 options',
      ),
      valueError("choice 的选项名是空串", question("q", { type: "choice", instructions: "x", criteria: { "": "A", b: "B" } }), 'question "q": choice options map names to descriptions (or null)'),
      valueError("score 只有一级", question("q", { type: "score", instructions: "x", criteria: ["a"] }), 'question "q": a score needs a list of 2 to 10 levels, lowest first'),
      valueError("score 的级别是 null", question("q", { type: "score", instructions: "x", criteria: ["a", null] }), 'question "q": score levels must be text, objects or arrays'),
      valueError("questions 是空对象", decisions("check_questions", { questions: "{}" }), "questions must be a non-empty mapping of {name: question}"),
      ok("questions 按插入次序", decisions("check_questions", { questions: JSON.stringify({ z: NOUL, a: { ...NOUL, label: "A" } }) })),
    ]);
  });
});

describe("配置解析与生效模式（settings_from_config）", () => {
  const dir = scratchDir("decisions-settings");
  const agent = join(dir, ".agent");
  const marked = join(dir, "marked");
  const plugin = join(dir, "plugin");
  mkdirSync(agent);
  mkdirSync(join(marked));
  writeFileSync(join(marked, "DECISIONS_OFF"), "decisions are off while this file exists\n");
  mkdirSync(join(plugin, "questions"), { recursive: true });
  afterAll(() => removeDir(dir));
  const on = (extra: { [key: string]: Json } = {}): Json => ({ decisions: { mode: "on", ...extra } });
  const url = (base: string, env = "MY_KEY"): ProbeRequest => settings(on({ base_url: base, api_key_env: env }), agent, plugin);
  const bad = "decisions.base_url must be https://host[:port] or http://127.0.0.1:port";

  it("契约", () => {
    verifyAll([
      settled("没有配置", settings({}), "reason", "not_configured"),
      settled("decisions 为 null 也算没有配置", settings({ decisions: null }), "reason", "not_configured"),
      settled("配置了 off", settings({ decisions: { mode: "off" } }), "reason", "configured_off"),
      settled("配置了 on、插件目录在", settings(on(), agent, plugin), "mode", "on"),
      settled("插件目录没有 questions/", settings(on(), agent, dir), "reason", "plugin_missing"),
      settled("标记文件一票否决", settings(on(), marked, plugin), "reason", "marker"),
      settled("plugins.enabled 里没有 decisions", settings({ ...(on() as object), plugins: { enabled: [] } }, agent, plugin), "reason", "plugin_disabled"),
      settled("plugins.allowed_permissions 里没有 network-decisions", settings({ ...(on() as object), plugins: { allowed_permissions: ["x"] } }, agent, plugin), "reason", "permission_missing"),
      decisionError("decisions 不是对象", settings({ decisions: 1 }), "config", "decisions must be an object"),
      decisionError("未知键", settings({ decisions: { zz: 1, aa: 2 } }), "config", "decisions has unknown keys ['aa', 'zz']"),
      decisionError("mode 不认识", settings({ decisions: { mode: "maybe" } }), "config", "decisions.mode must be one of off, shadow, on"),
      decisionError("api_key_env 以数字开头", settings({ decisions: { api_key_env: "1KEY" } }), "config", "decisions.api_key_env must be an environment variable name"),
      settled("api_key_env 末尾的换行照 Python 的 $ 放过", settings({ decisions: { api_key_env: "KEY\n" } }), "api_key_env", "KEY\n"),
      decisionError("base_url 不是字符串", settings({ decisions: { base_url: 1 } }), "config", "decisions.base_url must be a string"),
      settled("https 的端点，末尾的斜杠去掉", url("https://api.example.com/"), "base_url", "https://api.example.com"),
      decisionError("路径是两个斜杠", url("https://api.example.com//"), "config", bad),
      settled("开头的空白在解析时去掉，返回值照留", url("  https://api.example.com"), "base_url", "  https://api.example.com"),
      settled("http 的本机端点", url("http://127.0.0.1:8080"), "base_url", "http://127.0.0.1:8080"),
      settled("http 的 IPv6 本机端点", url("http://[::1]:8080"), "base_url", "http://[::1]:8080"),
      settled("主机名大写也是本机", url("http://LOCALHOST:1"), "base_url", "http://LOCALHOST:1"),
      settled("端口为空", url("https://host:"), "base_url", "https://host:"),
      decisionError("http 的外部端点", url("http://example.com"), "config", bad),
      decisionError("带用户名", url("https://user@example.com"), "config", bad),
      settled("用户名与密码都是空串时放过（真值为假）", url("https://:@example.com"), "base_url", "https://:@example.com"),
      decisionError("带路径", url("https://example.com/v1"), "config", bad),
      decisionError("带查询串", url("https://example.com?x=1"), "config", bad),
      decisionError("带片段", url("https://example.com#x"), "config", bad),
      decisionError("端口为 0", url("https://example.com:0"), "config", bad),
      decisionError("没有 //", url("https:example.com"), "config", bad),
      decisionError("ftp", url("ftp://example.com"), "config", bad),
      decisionError("端口超出范围", url("https://example.com:65536"), "config", "decisions.base_url is not a URL"),
      decisionError("端口不是数字", url("https://example.com:8o"), "config", "decisions.base_url is not a URL"),
      decisionError("端口是全角数字", url("https://example.com:８"), "config", "decisions.base_url is not a URL"),
      decisionError("方括号里是 IPv4", url("https://[127.0.0.1]"), "config", "decisions.base_url is not a URL"),
      decisionError("方括号没配对", url("https://[::1"), "config", "decisions.base_url is not a URL"),
      decisionError("方括号里不是地址", url("https://[zz]"), "config", "decisions.base_url is not a URL"),
      settled("方括号里是 IPvFuture", url("https://[v1.x]"), "base_url", "https://[v1.x]"),
      settled("IPv6 带区域标识", url("https://[fe80::1%25eth0]:443"), "base_url", "https://[fe80::1%25eth0]:443"),
      decisionError("网络位置 NFKC 之后冒出斜杠", url("https://ex℀ample.com"), "config", "decisions.base_url is not a URL"),
      decisionError("自定义端点用了官方凭据名（不分大小写）", url("https://api.example.com", "typesafe_api_key"), "config", "a custom decisions.base_url needs its own decisions.api_key_env (never the official TYPESAFE_API_KEY)"),
      decisionError("模型名有空格", settings({ decisions: { model: "bad model" } }), "config", "decisions.model is not a model id"),
      settled("模型名末尾的换行放过", settings({ decisions: { model: "m-1\n" } }), "model", "m-1\n"),
      decisionError("超时太短", settings({ decisions: { timeout_seconds: 0.4 } }), "config", "decisions.timeout_seconds must be a number between 0.5 and 60.0"),
      decisionError("超时是 true", settings({ decisions: { timeout_seconds: true } }), "config", "decisions.timeout_seconds must be a number between 0.5 and 60.0"),
      decisionError("超时是 NaN", settings('{"decisions": {"timeout_seconds": NaN}}'), "config", "decisions.timeout_seconds must be a number between 0.5 and 60.0"),
      crash("超时是超出 double 的整数（Python 打堆栈）", settings(`{"decisions": {"timeout_seconds": 1${"0".repeat(400)}}}`), "OverflowError"),
      decisionError("预算超出", settings({ decisions: { budget_seconds: 600.5 } }), "config", "decisions.budget_seconds must be a number between 1.0 and 600.0"),
      decisionError("状态字数是浮点数", settings('{"decisions": {"max_state_chars": 500.0}}'), "config", "decisions.max_state_chars must be an integer between 500 and 120000"),
      decisionError("测点重复", settings({ decisions: { points: ["run-health", "run-health"] } }), "config", "decisions.points must list distinct names from report-screen, mutation-equivalence, run-health"),
      decisionError("测点是列表里的列表", settings({ decisions: { points: [["run-health"]] } }), "config", "decisions.points must list distinct names from report-screen, mutation-equivalence, run-health"),
    ]);
  });
});

// --- 问题清单与内容锁：在临时目录里复制一份 plugins/decisions 再改坏 ------------------------------------

const SOURCE = join(REPO, "plugins", "decisions");
const QUESTION_NAMES = ["mutation-equivalence.json", "report-screen.json", "run-health.json"];

function pluginCopy(root: string, name: string): string {
  const target = join(root, name, "plugins", "decisions");
  cpSync(SOURCE, target, { recursive: true });
  return target;
}

describe("问题清单与内容锁（verify_battery_lock、load_battery、load_batteries）", () => {
  const root = scratchDir("decisions-lock");
  afterAll(() => removeDir(root));
  const verify = (dir: string): ProbeRequest => decisions("verify_battery_lock", { plugin_dir: dir });
  const tail = (dir: string): string => `; after a reviewed change run: python scripts/codekit/decisions.py --write-lock ${dir}`;
  const drift = (name: string, dir: string, detail: string): Case => decisionError(name, verify(dir), "battery_drift", detail);

  it("契约", () => {
    const clean = pluginCopy(root, "clean");
    const extra = pluginCopy(root, "extra");
    writeFileSync(join(extra, "questions", "extra.json"), "{}");
    const missing = pluginCopy(root, "missing");
    rmSync(join(missing, "questions", "report-screen.json"));
    const changed = pluginCopy(root, "changed");
    writeFileSync(join(changed, "questions", "run-health.json"), `${readFileSync(join(changed, "questions", "run-health.json"), "utf8")} `);
    const crlf = pluginCopy(root, "crlf");
    const crlfFile = join(crlf, "questions", "run-health.json");
    writeFileSync(crlfFile, readFileSync(crlfFile, "utf8").replaceAll("\n", "\r\n"));
    const asDir = pluginCopy(root, "as-dir");
    rmSync(join(asDir, "questions", "run-health.json"));
    mkdirSync(join(asDir, "questions", "run-health.json"));
    const upper = pluginCopy(root, "upper");
    renameSync(join(upper, "questions", "run-health.json"), join(upper, "questions", "RUN-HEALTH.JSON"));
    const longS = pluginCopy(root, "long-s");
    writeFileSync(join(longS, "questions", "x.jſon"), "{}");
    const noManifest = pluginCopy(root, "no-manifest");
    rmSync(join(noManifest, "manifest.json"));
    const badJson = pluginCopy(root, "bad-json");
    writeFileSync(join(badJson, "manifest.json"), "{\r\n  \"a\": ,\r\n}");
    const badUtf8 = pluginCopy(root, "bad-utf8");
    writeFileSync(join(badUtf8, "lock.json"), Buffer.from([0x7b, 0x22, 0xe4, 0xb8, 0x22, 0x7d]));
    const bom = pluginCopy(root, "bom");
    writeFileSync(join(bom, "manifest.json"), `\uFEFF${readFileSync(join(bom, "manifest.json"), "utf8")}`);
    const listManifest = pluginCopy(root, "list-manifest");
    writeFileSync(join(listManifest, "manifest.json"), "[]");
    const lockDrift = pluginCopy(root, "lock-drift");
    const lock = JSON.parse(readFileSync(join(lockDrift, "lock.json"), "utf8")) as { [key: string]: Json };
    writeFileSync(join(lockDrift, "lock.json"), JSON.stringify({ ...lock, lock_sha256: "1".repeat(64) }));
    const noQuestions = pluginCopy(root, "no-questions");
    rmSync(join(noQuestions, "questions"), { recursive: true });
    writeFileSync(join(noQuestions, "questions"), "");
    const locked = QUESTION_NAMES.map((name) => `${name} is locked but missing`).join("; ");

    verifyAll([
      ok("复制出来的一份原样通过", verify(clean)),
      drift("多出一份清单", extra, `extra.json is not in the lock${tail(extra)}`),
      drift("少了一份清单", missing, `report-screen.json is locked but missing${tail(missing)}`),
      drift("字节变了", changed, `run-health.json differs from the locked bytes${tail(changed)}`),
      drift(
        "只差换行",
        crlf,
        `run-health.json differs from the locked bytes only in line endings (checked out with CRLF; .gitattributes keeps plugins/decisions/** -text)${tail(crlf)}`,
      ),
      drift("清单换成了同名目录", asDir, `run-health.json cannot be read: [Errno 13] Permission denied: '${join(asDir, "questions", "run-health.json").replaceAll("\\", "\\\\")}'${tail(asDir)}`),
      drift("文件名大写（Windows 上 glob 不分大小写，锁里的名字分）", upper, `RUN-HEALTH.JSON is not in the lock; run-health.json is locked but missing${tail(upper)}`),
      drift("glob 在 re.IGNORECASE 下 s 也配 ſ", longS, `x.jſon is not in the lock${tail(longS)}`),
      drift("没有 manifest.json", noManifest, `plugin manifest or lock unreadable: [Errno 2] No such file or directory: '${join(noManifest, "manifest.json").replaceAll("\\", "\\\\")}'`),
      drift("manifest 不是合法 JSON（位置按通用换行之后算）", badJson, "plugin manifest or lock unreadable: Expecting value: line 2 column 8 (char 9)"),
      drift("lock 不是合法 UTF-8", badUtf8, "plugin manifest or lock unreadable: 'utf-8' codec can't decode bytes in position 2-3: invalid continuation byte"),
      drift("manifest 带 BOM", bom, "plugin manifest or lock unreadable: Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)"),
      drift("manifest 是列表", listManifest, "plugin manifest has no plugin_id"),
      drift("锁的摘要对不上", lockDrift, "lock does not verify: E_PLUGIN_LOCK_DRIFT at /lock_sha256: lock bytes do not match"),
      drift("questions 是文件", noQuestions, `${locked}${tail(noQuestions)}`),
      ok("真实的一份清单", decisions("load_battery", { path: join(clean, "questions", "run-health.json") })),
      ok("真实的清单目录", decisions("load_batteries", { root: join(clean, "questions") })),
      decisionError("清单目录不存在", decisions("load_batteries", { root: join(root, "nowhere") }), "plugin_missing", `no battery directory at ${join(root, "nowhere")}`),
    ]);
  });

  it("单份清单的各种坏法", () => {
    const dir = join(root, "batteries");
    mkdirSync(dir);
    const write = (name: string, value: Json | string): string => {
      const path = join(dir, name);
      writeFileSync(path, typeof value === "string" ? value : JSON.stringify(value));
      return path;
    };
    const battery = (extra: { [key: string]: Json }): Json => ({ id: "b", version: "1.0.0", questions: { passed: NOUL }, ...extra });
    const load = (path: string): ProbeRequest => decisions("load_battery", { path });
    const invalid = (name: string, file: string, value: Json | string, detail: string): Case => {
      const path = write(file, value);
      return decisionError(name, load(path), "battery_invalid", `${path}: ${detail}`);
    };
    verifyAll([
      ok("最小的一份", load(write("min.json", battery({})))),
      ok("state_fields 是字符串时拆成字符", load(write("chars.json", battery({ state_fields: "ab" })))),
      crash("state_fields 是数字（Python 打堆栈）", load(write("int-fields.json", battery({ state_fields: 5 }))), "TypeError"),
      ok("label 为空串、0、列表时的写法", load(write("labels.json", battery({ questions: { a: { ...NOUL, label: "" }, b: { ...NOUL, label: 0 }, c: { ...NOUL, label: [1, "x"] } } })))),
      ok("thresholds 的整数写成浮点数", load(write("thresholds.json", battery({ thresholds: { a: 1, b: 0.5 } })))),
      ok("id 末尾的换行照 Python 的 $ 放过", load(write("newline-id.json", battery({ id: "b\n" })))),
      invalid("不是对象", "list.json", "[]", "top level must be an object"),
      invalid("未知键", "unknown.json", battery({ zz: 1 }), "unknown keys ['zz']"),
      invalid("id 大写", "upper-id.json", battery({ id: "B" }), "id must match ^[a-z][a-z0-9-]{0,63}$"),
      invalid("version 两段", "version.json", battery({ version: "1.0" }), "version must be an exact semantic version"),
      invalid("问题不合法", "question.json", battery({ questions: { q: { type: "x", instructions: "y" } } }), "question \"q\" has type 'x'; use one of choice, score, noul"),
      invalid("thresholds 为负", "negative.json", battery({ thresholds: { a: -1 } }), "thresholds must map names to non-negative numbers"),
      invalid("thresholds 是 true", "bool.json", battery({ thresholds: { a: true } }), "thresholds must map names to non-negative numbers"),
      invalid("thresholds 是 Infinity", "inf.json", '{"id": "b", "version": "1.0.0", "questions": {"q": {"type": "noul", "instructions": "x?"}}, "thresholds": {"a": Infinity}}', "thresholds must map names to non-negative numbers"),
      invalid("thresholds 为 null", "null-thresholds.json", battery({ thresholds: null }), "thresholds must map names to non-negative numbers"),
      crash("thresholds 是超出 double 的整数", load(write("huge.json", `{"id": "b", "version": "1.0.0", "questions": {"q": {"type": "noul", "instructions": "x?"}}, "thresholds": {"a": 1${"0".repeat(400)}}}`)), "OverflowError"),
      decisionError("读不出", load(join(dir, "absent.json")), "battery_unreadable", `${join(dir, "absent.json")}: [Errno 2] No such file or directory: '${join(dir, "absent.json").replaceAll("\\", "\\\\")}'`),
      decisionError("不是合法 JSON", load(write("broken.json", "{\n")), "battery_unreadable", `${join(dir, "broken.json")}: Expecting property name enclosed in double quotes: line 2 column 1 (char 2)`),
    ]);
  });

  it("目录：文件名必须等于 id；Windows 上按小写排序，先报排在前面的那一份", () => {
    const dir = join(root, "ordered");
    mkdirSync(dir);
    writeFileSync(join(dir, "B.json"), JSON.stringify({ id: "x", version: "1.0.0", questions: { q: NOUL } }));
    writeFileSync(join(dir, "a.json"), JSON.stringify({ id: "y", version: "1.0.0", questions: { q: NOUL } }));
    const both = join(root, "both-ok");
    mkdirSync(both);
    writeFileSync(join(both, "b.json"), JSON.stringify({ id: "b", version: "1.0.0", questions: { q: NOUL } }));
    writeFileSync(join(both, "a.json"), JSON.stringify({ id: "a", version: "1.0.0", questions: { q: NOUL } }));
    verifyAll([
      decisionError("a.json 先于 B.json", decisions("load_batteries", { root: dir }), "battery_invalid", `${join(dir, "a.json")}: file name must equal the battery id y`),
      ok("两份都对：按排序后的次序索引", decisions("load_batteries", { root: both })),
    ]);
  });
});

describe("问题清单经过链接（battery_link_problem）", () => {
  const root = scratchDir("decisions-link");
  afterAll(() => removeDir(root));
  const link = (kitRoot: string, pluginDir: string): ProbeRequest => decisions("battery_link_problem", { kit_root: kitRoot, plugin_dir: pluginDir });
  const found = (name: string, request: ProbeRequest, expected: string | null): Case => ({
    name,
    request,
    check: (result) => {
      const value = result["value"] as { t: string; v?: string } | undefined;
      const actual = value?.t === "none" ? null : value?.v;
      return result.ok && actual === expected ? null : JSON.stringify(result);
    },
  });

  it("契约", () => {
    const plain = join(root, "plain");
    pluginCopy(root, "plain");
    const questionsLink = join(root, "questions-link");
    const questionsDir = pluginCopy(root, "questions-link");
    const elsewhere = join(root, "elsewhere-questions");
    renameSync(join(questionsDir, "questions"), elsewhere);
    symlinkSync(elsewhere, join(questionsDir, "questions"), "junction");
    const fileLink = join(root, "file-link");
    const fileDir = pluginCopy(root, "file-link");
    const target = join(root, "lock-target.json");
    renameSync(join(fileDir, "lock.json"), target);
    symlinkSync(target, join(fileDir, "lock.json"), "file");
    const dirNamedJson = join(root, "dir-json");
    const dirJson = pluginCopy(root, "dir-json");
    mkdirSync(join(root, "junction-target"));
    symlinkSync(join(root, "junction-target"), join(dirJson, "questions", "zz.json"), "junction");
    const outside = join(root, "outside", "decisions");
    mkdirSync(join(root, "outside"));
    symlinkSync(SOURCE, outside, "junction");
    verifyAll([
      found("没有链接", link(plain, join(plain, "plugins", "decisions")), null),
      found("questions/ 是 junction", link(questionsLink, join(questionsDir)), "plugins/decisions/questions"),
      found("lock.json 是文件符号链接", link(fileLink, fileDir), "plugins/decisions/lock.json"),
      found("questions 下一个叫 zz.json 的 junction", link(dirNamedJson, dirJson), "plugins/decisions/questions/zz.json"),
      found("插件目录不在 kit 之下、本身是 junction", link(plain, outside), outside),
      found("kit 根的大小写不同也算在其下（返回相对 kit 的写法）", link(questionsLink.toUpperCase(), questionsDir), "plugins/decisions/questions"),
    ]);
  });
});
