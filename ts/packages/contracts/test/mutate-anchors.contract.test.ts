// mutate 的清单校验与 --check-anchors（迁移第 ④b5a 片）：Python 与 TS（Node、Bun）逐字一致。--check-anchors 只读，
// 不运行命令、不写文件，所以真数据可以直接用：仓库 ts/mutations/ 下的全部清单，对当前的树核对一遍，再对一棵“改坏了的”
// 副本核对一遍（清单引用到的文件按固定规则改几处，锚点大量对不上，“最相近的行”、第一处不同与后续行的提示都会出来）。
// 命令行这一层另用手造的树与清单，比退出码、标准输出与标准错误。
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, describe, expect, it } from "vitest";
import { IMPLS, runBatch } from "./harness.ts";
import { CONTEXT, LF, RUNNERS, type Runner, newRepo, put, removeCreated, runCommand, shownOf, tempDir } from "./repo-fixtures.ts";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..");
const CR = String.fromCharCode(13);
const SPECS = readdirSync(join(REPO, "ts", "mutations")).filter((name) => name.endsWith(".json")).sort().map((name) => join(REPO, "ts", "mutations", name));

afterAll(() => removeCreated());

/** 清单引用到的文件（在仓库里存在的）。 */
function referencedFiles(): string[] {
  const files = new Set<string>();
  for (const spec of SPECS) {
    const parsed = JSON.parse(readFileSync(spec, "utf8")) as { mutations?: { file?: unknown }[] };
    for (const item of parsed.mutations ?? []) if (typeof item.file === "string" && existsSync(join(REPO, item.file))) files.add(item.file);
  }
  return [...files].sort();
}

/** 按固定规则改坏一行：const 换 let、等号前加空格、行尾加注释、删一个字符、改缩进，轮着来；每 11 行删掉一行。 */
function perturb(text: string): string {
  const eol = text.includes(CR + LF) ? CR + LF : LF;
  const lines = text.split(eol);
  const out: string[] = [];
  lines.forEach((line, index) => {
    if (index % 11 === 10) return;
    if (index % 5 !== 2 || !line.trim()) {
      out.push(line);
      return;
    }
    const rule = Math.floor(index / 5) % 5;
    if (rule === 0 && line.includes("const ")) out.push(line.replace("const ", "let "));
    else if (rule === 1 && line.includes(" = ")) out.push(line.replace(" = ", "  = "));
    else if (rule === 2) out.push(`${line} // x`);
    else if (rule === 3 && line.length > 4) out.push(line.slice(0, 3) + line.slice(4));
    else out.push(`  ${line}`);
  });
  return out.join(eol);
}

function checkAll(tree: string): unknown[][] {
  const results = IMPLS.map((impl) => {
    const [result] = runBatch(impl, [{ op: "mutate.check_anchors", tree, specs: SPECS }]);
    return (result?.["results"] ?? result) as unknown[];
  });
  for (const other of results.slice(1)) {
    const diffs = (other ?? []).flatMap((value, index) => (JSON.stringify(value) === JSON.stringify(results[0]?.[index]) ? [] : [{ spec: SPECS[index], python: results[0]?.[index], other: value }]));
    expect(diffs.slice(0, 2)).toEqual([]);
  }
  return results;
}

describe("真数据：仓库里的全部变异清单", () => {
  it(`当前的树（${SPECS.length} 份清单）`, () => {
    const [python] = checkAll(REPO);
    expect((python ?? []).length).toBe(SPECS.length);
  }, 300_000);

  it("改坏了的副本：锚点大量对不上", () => {
    const tree = tempDir("perturbed");
    for (const file of referencedFiles()) {
      const target = join(tree, file);
      mkdirSync(dirname(target), { recursive: true });
      const data = readFileSync(join(REPO, file));
      // 每三个文件留一个原样（混着 OK 行）；其余按行改坏
      if (file.length % 3 === 0) copyFileSync(join(REPO, file), target);
      else writeFileSync(target, perturb(data.toString("utf8")));
    }
    const [python] = checkAll(tree);
    const text = JSON.stringify(python);
    for (const needle of ["MISMATCH", "最相近 L", "第一处不同在", "首行对上了", "出现 0 次"]) expect(text).toContain(needle);
  }, 300_000);
});

// ---------------------------------------------------------------------------
// 命令行
// ---------------------------------------------------------------------------

/** 手造的树：LF 与 CRLF 的源文件、不是 UTF-8 的文件、重复行。 */
function fixtureTree(): string {
  const tree = tempDir("tree");
  put(tree, "src/a.ts", [
    "export function add(a: number, b: number): number {", "  const total = a + b;", "  return total;", "}", "",
    "export function twice(x: number): number {", "  return add(x, x);", "}", "// repeated", "const marker = 1;", "const marker = 1;", "",
  ].join(LF));
  put(tree, "src/crlf.ts", ["line one", "line two", "const value = compute(input);", ""].join(CR + LF));
  put(tree, "src/bin.dat", new Uint8Array([0xff, 0xfe, 0x00, 0x41]));
  put(tree, "src/many.ts", `x = 1;${LF}`.repeat(7));
  put(tree, "src/emoji.ts", `const face = "${String.fromCodePoint(0x1f600)}中文";${LF}`);
  return tree;
}

const m = (name: string, file: string, old: string, extra: Record<string, unknown> = {}): Record<string, unknown> => ({ name, file, old, new: `${old} /*x*/`, ...extra });

const ANCHORS = [
  m("M01 对上", "src/a.ts", "  const total = a + b;"),
  m("M02 一个字符不同", "src/a.ts", "  const total = a - b;"),
  m("M03 old 多了字符", "src/a.ts", "  const totals = a + b;"),
  m("M04 文件多了字符", "src/a.ts", "  const total = a+b;"),
  m("M05 首行对上、第二行不同", "src/a.ts", `export function add(a: number, b: number): number {${LF}  const total = a * b;`),
  m("M06 文件提前结束", "src/a.ts", `const marker = 1;${LF}const marker = 1;${LF}const marker = 2;`),
  m("M07 只差缩进", "src/a.ts", `export function twice(x: number): number {${LF}    return add(x, x);`),
  m("M08 没有相近的行", "src/a.ts", "zzzzzzzzzzqqqqq"),
  m("M09 出现两次", "src/a.ts", "const marker = 1;"),
  m("M10 出现七次只列五处", "src/many.ts", "x = 1;"),
  m("M11 CRLF 的文件、LF 的 old", "src/crlf.ts", `line two${LF}const value`),
  m("M12 old 里带 CRLF", "src/crlf.ts", `line one${CR}${LF}line two`),
  m("M13 不是 UTF-8", "src/bin.dat", "A"),
  m("M14 文件不在", "src/nope.ts", "x"),
  m("M15 是目录", "src", "x"),
  m("M16 期望两次", "src/a.ts", "const marker = 1;", { count: 2 }),
  m("M17 补充平面字符", "src/emoji.ts", `const face = "${String.fromCodePoint(0x1f601)}中文";`),
  // 孤立的低位代理只对得上补充平面字符的半边：按码点数是 0 次
  m("M18 孤立的低位代理", "src/emoji.ts", String.fromCharCode(0xde00)),
];

const BAD_SPEC = {
  cwd: "../x", timeout_seconds: 0,
  commands: [
    { id: "1bad", argv: [], cwd: "/abs", timeout_seconds: true }, { id: "ok", argv: ["x"] }, { id: "ok", argv: ["y"], extra: 1 }, { id: "ok", argv: ["z"] }, "notdict",
  ],
  mutations: [
    "notdict", { name: " ", file: "", old: "", new: 5 },
    { name: "a", file: "a/../b", old: "x", new: "x", count: 0, expect_missed: ["nope"], equivalent: "e" },
    { name: "a", file: "f", old: "o", new: "n", expect_missed: [], equivalent: "" },
    { name: "b", file: "f", old: "o", new: "n", expect_missed: ["ok", "ok"] },
    { name: "c", file: "f", old: "o", new: "n", equivalent: "x", expect_missed: ["ok"] },
    { name: "d", file: "C:/abs/f", old: "o", new: "n", count: true },
  ],
};

interface Case {
  readonly label: string;
  /** 清单的内容（字符串原样写，其余写成 JSON）；null 表示清单文件不存在。 */
  readonly spec: unknown;
  readonly tree?: "fixture" | "missing";
  readonly runDir?: boolean;
  readonly anchors?: boolean;
  readonly status: number;
  readonly text?: string;
  readonly crash?: boolean;
  readonly merged?: boolean;
}

const CASES: Case[] = [
  { label: "锚点：各种对上与对不上", spec: { command: ["x"], mutations: ANCHORS }, status: 1, text: "锚点核对：18 条，" },
  { label: "锚点：全部对上", spec: { command: ["x"], mutations: [ANCHORS[0], ANCHORS[10], ANCHORS[15]] }, status: 0, text: "锚点核对：3 条，0 条不符" },
  { label: "清单的各种坏法", spec: BAD_SPEC, status: 2, text: "ERROR: 变异清单无效：" },
  { label: "清单的各种坏法：合并输出的次序", spec: BAD_SPEC, status: 2, merged: true },
  { label: "command 与 commands 都写了", spec: { command: ["x"], commands: [{ id: "a", argv: ["x"] }], mutations: [ANCHORS[0]] }, status: 2, text: "command 与 commands 只能写一个" },
  { label: "commands 太多", spec: { commands: Array.from({ length: 9 }, (_, i) => ({ id: `c${i}`, argv: ["x"] })), mutations: [ANCHORS[0]] }, status: 2, text: "commands 必须是 1 到 8 个对象的数组" },
  { label: "命令 id 带结尾换行也算合法（$ 的老毛病）", spec: { commands: [{ id: `a${LF}`, argv: ["x"] }], mutations: [ANCHORS[0]] }, status: 0 },
  { label: "命令 id 是列表：Python 在建集合时崩", spec: { commands: [{ id: [1], argv: ["x"] }], mutations: [ANCHORS[0]] }, status: 1, crash: true },
  { label: "不是合法 JSON", spec: "{", status: 2, text: "变异清单无法读取或不是合法 JSON：Expecting property name enclosed in double quotes" },
  { label: "带 BOM", spec: `${String.fromCharCode(0xfeff)}{}`, status: 2, text: "Unexpected UTF-8 BOM" },
  { label: "顶层是列表", spec: "[]", status: 2, text: "变异清单必须是 JSON 对象" },
  { label: "清单文件不在", spec: null, status: 2, text: "No such file or directory" },
  { label: "--tree 不是目录", spec: { command: ["x"], mutations: [ANCHORS[0]] }, tree: "missing", status: 2, text: "--tree 不是目录：" },
  { label: "--tree 与 run_dir 都给了", spec: { command: ["x"], mutations: [ANCHORS[0]] }, runDir: true, status: 2, text: "--tree 与 run_dir 二选一" },
];

function runCase(item: Case): void {
  const results = (RUNNERS as readonly Runner[]).map((runner) => {
    const { repo } = newRepo(`anchors-${runner}`);
    const tree = item.tree === "missing" ? join(repo, "no-such-tree") : fixtureTree();
    const dir = tempDir("spec");
    const specPath = join(dir, "spec.json");
    if (item.spec !== null) writeFileSync(specPath, typeof item.spec === "string" ? item.spec : JSON.stringify(item.spec, null, 2));
    const argv = ["mutate", ...(item.runDir ? ["t1"] : []), "--tree", tree, "--spec", specPath, "--check-anchors"];
    const args = { command: ["mutate"], run_dir: item.runDir ? "t1" : null, spec: specPath, keep_workspace: false, tree, out: null, check_anchors: true, context: CONTEXT };
    const result = runCommand(runner, repo, argv, args, repo, item.merged === true);
    return shownOf(result, { "<TREE>": tree, "<SPEC>": dir, "<REPO>": repo }, item.crash);
  });
  for (const result of results.slice(1)) expect(result).toEqual(results[0]);
  const first = results[0] as (typeof results)[number];
  expect(first.status, JSON.stringify(first)).toBe(item.status);
  if (item.text) expect(first.stdout + first.stderr).toContain(item.text);
}

describe("mutate --check-anchors：命令行", () => {
  for (const item of CASES) it(item.label, () => runCase(item), 120_000);
});

describe("mutate 的参数组合", () => {
  it("没有 --tree 也没有 run_dir；run_dir 配 --check-anchors", () => {
    for (const [argv, args, text] of [
      [["mutate", "--spec", "s.json"], { command: ["mutate"], run_dir: null, spec: "s.json", keep_workspace: false, tree: null, out: null, check_anchors: false }, "缺少 run_dir"],
      [["mutate", "t1", "--spec", "s.json", "--check-anchors"], { command: ["mutate"], run_dir: "t1", spec: "s.json", keep_workspace: false, tree: null, out: null, check_anchors: true }, "--out 与 --check-anchors 只在 --tree 模式下有效"],
    ] as const) {
      const results = (RUNNERS as readonly Runner[]).map((runner) => {
        const { repo } = newRepo(`margs-${runner}`);
        return shownOf(runCommand(runner, repo, argv, { ...args, context: CONTEXT }, repo), { "<REPO>": repo });
      });
      for (const result of results.slice(1)) expect(result).toEqual(results[0]);
      expect(results[0]?.status).toBe(2);
      expect(results[0]?.stderr).toContain(text);
    }
  }, 120_000);
});
