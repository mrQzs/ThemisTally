// pi_dispatch 合同解析与校验的契约（迁移第 ④b1 片）：derive_contract_json、validate_contract、invisible_char_warnings。
// 语料是仓库里 .agent/plans 下的真实合同（Markdown 与 JSON 成对），再加按种子改坏的变体：Markdown 删行、重复行、插字符、
// 插占位符；JSON 删键、换类型、plan_version 写成 1.0/true/"1"、expect_on_base 写成列表（Python 在这里抛 TypeError）、
// 用户正则写成 (?a)(?u)x（re.compile 抛 ValueError）。每条先由 Python 回答，Node、Bun 逐字一致；另断言每种结局都走到了。
// 不写转义序列，特殊字符用 ch() 拼。
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { REPO, type ProbeRequest, type ProbeResult, prng, runAgreeing } from "./harness.ts";
import { type Json, jsonOf, mdOf, text } from "./plan-fixtures.ts";

const ch = (...codes: number[]): string => String.fromCodePoint(...codes);
const LF = ch(10);
const PLANS = join(REPO, ".agent", "plans");

interface Pair {
  readonly key: string;
  readonly md: string;
  readonly json: string | null;
}

/** .agent/plans 下的合同：按文件名排序，Markdown 必有，JSON 可能没有。 */
function corpus(): Pair[] {
  const names = readdirSync(PLANS).sort();
  return names
    .filter((name) => name.endsWith(".md"))
    .map((name) => {
      const key = name.slice(0, -3);
      const jsonName = `${key}.json`;
      return { key, md: readFileSync(join(PLANS, name), "utf8"), json: names.includes(jsonName) ? readFileSync(join(PLANS, jsonName), "utf8") : null };
    });
}

const derive = (md: string, title: string | null = null): ProbeRequest => ({ op: "contract.call", fn: "derive", md, title });
const validate = (md: string, json: string, key: string, extra: string[] = []): ProbeRequest => ({
  op: "contract.call",
  fn: "validate",
  md,
  json_text: json,
  plan_key: key,
  extra_protected: extra,
});

/** 分批交给探针（一个探针进程有 60 秒的时限），汇总 Python 的结果与不一致。 */
function agreeInBatches(requests: readonly ProbeRequest[], size = 250): ProbeResult[] {
  const python: ProbeResult[] = [];
  let mismatches = 0;
  const samples: unknown[] = [];
  for (let start = 0; start < requests.length; start += size) {
    const batch = runAgreeing(requests.slice(start, start + size));
    python.push(...batch.python);
    mismatches += batch.mismatches.length;
    samples.push(...batch.mismatches.slice(0, 2).map((item) => ({ ...item, request: { ...item.request, md: "…", json_text: "…" } })));
  }
  expect(samples.slice(0, 2), `共 ${mismatches} 条不一致`).toEqual([]);
  return python;
}

const PAIRS = corpus();

describe("合同的解析与校验（真实合同）", () => {
  it("derive_contract_json：每份 Markdown", () => {
    const python = agreeInBatches([...PAIRS.map((pair) => derive(pair.md)), derive(PAIRS[0]?.md ?? "", "手写的标题"), derive(""), derive(LF)]);
    expect(python.length).toBeGreaterThan(300);
    expect(python.some((result) => result.ok && (result["problems"] as string[]).length === 0)).toBe(true);
    expect(python.some((result) => result.ok && (result["problems"] as string[]).length > 0)).toBe(true);
  });

  it("validate_contract：每对 Markdown 与 JSON，一部分另加仓库的保护路径", () => {
    const requests = PAIRS.filter((pair) => pair.json !== null).map((pair, index) =>
      validate(pair.md, pair.json as string, pair.key, index % 5 === 0 ? ["docs/**", "tests/test_gate_*"] : []),
    );
    const python = agreeInBatches(requests);
    expect(python.some((result) => result.ok && result["contract"] !== null)).toBe(true);
    expect(python.some((result) => result.ok && (result["errors"] as string[]).length > 0)).toBe(true);
    expect(python.some((result) => result.ok && (result["warnings"] as string[]).length > 0)).toBe(true);
  });
});

describe("合同的解析与校验（按种子改坏）", () => {
  const pieces = ["【待填", "REPLACE_WITH", "`", "（", "）", "：", ":", "- ", "* ", "## Scope", "## budget", "  - src/a.ts", "V01", "D01", "约 30 分钟", "时间分配", " ", "\t", "１２", "²", ch(0x200b), ch(0xfeff), ch(0x200e), ch(0xad), ch(0x17f)];

  function mutateMd(md: string, next: () => number): string {
    const lines = md.split(LF);
    const at = Math.floor(next() * lines.length);
    const roll = next();
    if (roll < 0.25) lines.splice(at, 1);
    else if (roll < 0.45) lines.splice(at, 0, lines[at] ?? "");
    else {
      const line = lines[at] ?? "";
      const cut = Math.floor(next() * (line.length + 1));
      lines[at] = line.slice(0, cut) + (pieces[Math.floor(next() * pieces.length)] as string) + line.slice(cut);
    }
    return lines.join(LF);
  }

  /** 改坏 JSON：只用解析出来的普通对象（语料里没有大整数与重复键），改完再写回。 */
  function mutateJson(text: string, next: () => number): string {
    const data = JSON.parse(text) as Record<string, unknown>;
    const pick = <T>(items: readonly T[]): T => items[Math.floor(next() * items.length)] as T;
    const checks = Array.isArray(data["checks"]) ? (data["checks"] as Record<string, unknown>[]) : [];
    const first = checks[0];
    const choices: (() => void)[] = [
      () => delete data[pick(Object.keys(data))],
      () => (data[pick(Object.keys(data))] = pick([null, 3, "x", [], {}, true, 1.5])),
      () => (data["plan_version"] = pick([1.0, true, "1", 2, null])),
      () => (data["schema_version"] = pick([1.0, true, 2])),
      () => first && (first["expect_on_base"] = pick([["x"], { a: 1 }, "fail", "pass", 3])),
      () => first && (first["output_must_match"] = pick([["(?a)(?u)x"], ["(unclosed"], ["a{2,1}"], ["ok"], "x", [1]])),
      () => first && (first["argv"] = pick([[], [""], ["a", 3], "x"])),
      () => first && (first["timeout_seconds"] = pick([0, 86401, true, 1.0, "60"])),
      () => first && (first["expected_exit_code"] = pick([true, 1.0, "0"])),
      () => first && (first["env"] = pick([{ "1A": "x" }, { A: 1 }, []])),
      () => (data["scope"] = { ...(data["scope"] as object), allowed_modified_files: pick([["../x"], [".agent/x"], ["*"], ["a//b"], [3], "x"]) }),
      () => (data["executor"] = pick([{ role: "execution" }, { role: "execution", provider: "p" }, { provider: 3 }, { tools: ["bash", "x"] }, { thinking: "huge" }])),
      () => (data["budget"] = pick([{ max_attempts_total: 0 }, { cost_budget: { amount: -1, currency: "USD" } }, { cost_budget: { amount: 1.5, currency: "USD" } }, { max_wall_seconds_per_attempt: 30 }])),
      () => (data["definition_of_done"] = pick([[], [{ id: "D01", text: "", evidence: [] }], [{ id: "V01", text: "x", evidence: ["nope"] }], "x"])),
      () => (data["authorization"] = pick([{ executor: ["network"] }, { executor: ["local_edit", "bad"] }, { integration: "x" }])),
      () => (data["contract_family"] = "planner-v2"),
    ];
    pick(choices)();
    return JSON.stringify(data);
  }

  it("每个种子 200 份：Markdown 与 JSON 各自改坏", () => {
    const usable = PAIRS.filter((pair) => pair.json !== null);
    const requests: ProbeRequest[] = [];
    for (const seed of [71, 72]) {
      const next = prng(seed);
      for (let index = 0; index < 200; index += 1) {
        const pair = usable[Math.floor(next() * usable.length)] as Pair;
        const md = next() < 0.6 ? mutateMd(pair.md, next) : pair.md;
        const json = next() < 0.6 ? mutateJson(pair.json as string, next) : (pair.json as string);
        requests.push(validate(md, json, pair.key), derive(md));
      }
    }
    const python = agreeInBatches(requests);
    const errors = python.flatMap((result) => (result.ok && Array.isArray(result["errors"]) ? (result["errors"] as string[]) : []));
    // 结局都走到了：校验通过、普通错误、合同结构无效（TypeError 与 ValueError 两条）
    expect(python.some((result) => result.ok && result["contract"] !== null && result["errors"] !== undefined)).toBe(true);
    expect(errors.some((error) => error.startsWith("合同结构无效：TypeError"))).toBe(true);
    expect(errors.some((error) => error.startsWith("合同结构无效：ValueError"))).toBe(true);
    expect(errors.some((error) => error.includes("正则无效"))).toBe(true);
  });

  it("第 129 轮：输出模式的反向引用与条件分组在校验时拒绝；八进制、字符类、引用不存在的组与编译阶段的错误照旧", () => {
    const bs = ch(92);
    const refused = [
      `(a)${bs}1`, `(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)${bs}10`, "(?P<x>a)(?P=x)", "(a)?(?(1)b|c)", "(?P<n>a)?(?(n)b)", `(?i:(a)${bs}1)`,
      `x|(?:(a)${bs}1)+`,
    ];
    const kept = [`${bs}0`, `${bs}012`, `[${bs}1]`, `[${bs}1-${bs}3]`, "(a)", "(?P<x>a)x", `${bs}${bs}1`];
    const invalid = [`(a)${bs}2`, "(?P=y)", "(?(2)a|b)", `(a)${bs}1(?<=a+)`, `(?<=a+)(a)${bs}1`];
    // 后顾里的引用、条件分组一支里的后顾：结局由 Python 定，两边一致即可
    const either = [`(a)(?<=${bs}1)`, `(?<=(a)${bs}1)`, `(a)?(?(1)(?<=a+)|c)`, `(a)?(?(1)b|(?<=a+))`];
    const patterns = [...refused, ...kept, ...invalid, ...either];
    const head = "0123456789abcdef0123456789abcdef01234567";
    const keys = ["output_must_match", "output_must_not_match"];
    const requests = patterns.flatMap((pattern) => keys.map((key) => {
      const data = jsonOf("t1", head);
      const checks = data["checks"] as Json[];
      checks[0] = { ...checks[0], [key]: [pattern] };
      return validate(mdOf("t1", head), text(data), "t1.v1");
    }));
    const python = agreeInBatches(requests);
    const errorsOf = (index: number): string[] => ((python[index] as ProbeResult)["errors"] as string[] | undefined) ?? [];
    patterns.forEach((pattern, at) => {
      keys.forEach((key, side) => {
        const errors = errorsOf(at * 2 + side);
        if (refused.includes(pattern)) expect(errors, pattern).toEqual([`V01 ${key} 不支持反向引用与条件分组：${pattern}`]);
        if (kept.includes(pattern)) expect(errors, pattern).toEqual([]);
        if (invalid.includes(pattern)) expect(errors.length === 1 && (errors[0] as string).startsWith(`V01 ${key} 正则无效：`), pattern).toBe(true);
      });
    });
  });

  it("branch_subject：标题里的各种空白、已带 task-id 前缀的写法、没有标题时的版本与 attempt 编号", () => {
    const ws = [ch(9), ch(10), ch(13), ch(11), ch(12), ch(0x1c), ch(0x85), ch(0xa0), ch(0x3000), ch(0x2028), ch(0x200b)];
    const titles: unknown[] = [
      "修复 登录", `t1: 已带前缀`, "t1：全角冒号", "t1 空格", "t1-x 不算前缀", "t1", `${ws.join("a")}b${ws.join("")}`,
      ws.join(""), "", null, 3, ["x"], `t1${ch(0x3000)}标题`, `${ch(0x130)}stanbul`,
    ];
    const requests: ProbeRequest[] = [];
    const cases: [unknown, number][] = [[1, 1], ["2", 12], [1.0, 123], [null, 1234], [true, 0], [3, -1], [3, -12], [3, -1234]];
    for (const title of titles) {
      for (const [version, attempt] of cases) {
        requests.push({ op: "contract.call", fn: "branch_subject", task_id: "t1", title_json: JSON.stringify(title),
          plan_version_json: JSON.stringify(version), attempt_no: attempt });
      }
    }
    const python = agreeInBatches(requests);
    expect(python.map((result) => result["value"])).toContain("t1: Pi 候选 v3 attempt -01");
  });

  it("invisible_char_warnings：塞进 Cf 字符的行，每份最多报 5 行", () => {
    const next = prng(73);
    const cf = [ch(0x200b), ch(0xfeff), ch(0x200e), ch(0xad), ch(0x2066), ch(0xe0001)];
    const requests = PAIRS.slice(0, 60).map((pair) => {
      const lines = pair.md.split(LF);
      for (let count = Math.floor(next() * 8); count > 0; count -= 1) {
        const at = Math.floor(next() * lines.length);
        lines[at] = `${lines[at] ?? ""}${cf[Math.floor(next() * cf.length)] as string}${cf[Math.floor(next() * cf.length)] as string}`;
      }
      return { op: "contract.call", fn: "invisible", text: lines.join(LF), label: "Markdown" } as ProbeRequest;
    });
    const python = agreeInBatches(requests);
    expect(python.some((result) => (result["value"] as string[]).length === 5)).toBe(true);
  });
});

describe("合同的解析与校验（手写的边界）", () => {
  // 真实合同与随机改坏都碰不到的写法（变异反测漏掉的几条）：节名的大小写与 Python 的 re.I 才认的字母、时间分配的同级条目与
  // 70%–80% 之间的合计、Scope 用顿号分隔、检查行写 optional、程序名对不上、一行 DoD 里两个“；证据：”、JSON 的检查没写 required
  it("derive 与 validate", () => {
    const BT = "`";
    const md = mdOf("hand", "a".repeat(40));
    const budget = "- max_wall_seconds_total: 2400";
    const variants: [string, (data: Json) => void][] = [
      [md.replace("## Budget", "## budget").replace("## Scope", "## SCOPE").replace("## Goal", "## gOAL")
        .replace("## Validation commands", `## Validation command${ch(0x17f)}`).replace("## Identity", `## ${ch(0x130)}dentity`), () => undefined],
      [md.replace(budget, [budget, "- 时间分配：", "  - 读代码约 10 分钟", "  - 写代码约 15 分钟", "- 其他：约 20 分钟"].join(LF)), () => undefined],
      [md.replace(budget, [budget, "- 时间分配：", "  - 全部约 15 分钟"].join(LF)), () => undefined],
      [md.replace("- allowed_modified_files: src/a.ts", "- allowed_modified_files: src/a.ts、src/b.ts"),
        (data) => void ((data["scope"] as Json)["allowed_modified_files"] = ["src/a.ts", "src/b.ts"])],
      [md.replace("## Definition of done", `- V02（optional）：${BT}node -v${BT} · 超时：60s${LF}${LF}## Definition of done`),
        (data) => void (data["checks"] as Json[]).push({ id: "V02", argv: ["node", "-v"], cwd: ".", timeout_seconds: 60, required: false, expected_exit_code: 0 })],
      [md, (data) => void (((data["checks"] as Json[])[0] as Json)["argv"] = ["pytest-x", "tests"])],
      [md.replace("- D01: 行为正确；证据：V01", "- D01: 行为正确；证据：V01；再说一句；证据：V01"), () => undefined],
      [md, (data) => void delete ((data["checks"] as Json[])[0] as Json)["required"]],
    ];
    const requests = variants.flatMap(([variant, change]) => {
      const data = jsonOf("hand", "a".repeat(40));
      change(data);
      return [derive(variant), validate(variant, text(data), "hand.v1")];
    });
    const python = agreeInBatches(requests);
    const seen = JSON.stringify(python);
    for (const fragment of ["时间分配合计 25 分钟", "时间分配合计 15 分钟", "的命令与 JSON argv 不一致", "行为正确；证据：V01；再说一句", "src/b.ts"]) {
      expect(seen, fragment).toContain(fragment);
    }
  });
});
