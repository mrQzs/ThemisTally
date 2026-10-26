// pi_dispatch 探测 CLI 的部分的契约（迁移第 ③d 片）：parse_help 与 --list-models 的解析、child_env、run_capture。
// 每条先由 Python 回答，Node、Bun 两种运行方式逐字一致；解析另有按种子拼出来的文字。
//   - child_env：探针继承本进程的环境，用例先改 process.env 再起探针。环境的键序只在大小写不同的同名变量留哪个上看得出，
//     比较排好序的键值、实际生效的环境与被移除的变量名。
//   - run_capture：退出码与输出的字节、找不到程序（127）、起不来（126）、目录不存在、正常超时（124）。超时后孙进程握着
//     管道时 Python 一直挂着（迁移文档第 10 节接受的差别），另有一条只测 TS 的用例：经 .cmd 起的进程树按时结束。
// 转义的反斜杠一律用 String.fromCharCode(92) 拼（源码里不写 \u 转义）。
import { copyFileSync, mkdirSync, realpathSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { runCapture } from "@themis/dispatcher/pi-cli";
import { afterAll, describe, expect, it } from "vitest";
import { type ProbeRequest, type ProbeResult, prng, removeDir, runAgreeing, scratchDir } from "./harness.ts";

const ROOT = realpathSync.native(scratchDir("pi-cli"));
afterAll(() => removeDir(ROOT));

const BS = String.fromCharCode(92);
const LF = String.fromCharCode(10);
const CR = String.fromCharCode(13);
const CRLF = CR + LF;
const ESC = String.fromCharCode(27);
const ch = (...codes: number[]): string => String.fromCodePoint(...codes);

function agree(requests: readonly ProbeRequest[]): ProbeResult[] {
  const { python, mismatches } = runAgreeing(requests);
  expect(mismatches.slice(0, 3), `共 ${mismatches.length} 条不一致`).toEqual([]);
  return python;
}

const parse = (text: string): ProbeRequest => ({ op: "dispatch.parse_cli", text });

const RESOURCE = ["--no-approve", "--no-extensions", "--no-skills", "--no-prompt-templates", "--no-themes", "--no-mcp"];
const HELP = [
  "Usage: pi [options] [prompt]",
  "",
  "Options:",
  "  --provider <name>        Provider",
  "  --model <id>             Model ID",
  "  --thinking <level>       Thinking level: off, minimal, low, medium, high, xhigh",
  "  --mode <mode>            Output mode",
  "  --no-session             Do not save the session",
  "  --tools <list>           Allowed tools",
  ...RESOURCE.map((flag) => `  ${flag}`),
  "  --no-context-files       Skip AGENTS.md",
  "  --list-models [search]   List models",
  "",
  "Built-in Tool Names:",
  "  read     - Read file contents",
  "  bash     - Run commands",
  "  edit_x   - Edit files",
  "",
  "Examples:",
  "  pi --help",
].join(LF);

const TABLE = [
  "provider   model            context  max-out  thinking  images",
  "step       step-5           256K     32K      yes       no",
  "step       step-5-preview   256K     32K      yes       no",
  "anthropic  claude-x         200K     64K      yes       yes",
].join(LF);

describe("parse_help 与 --list-models 的解析", () => {
  it("手写的用例", () => {
    const python = agree([
      parse(HELP),
      parse(HELP.replaceAll("--provider", `${ESC}[1m--provider${ESC}[0m`).replaceAll(LF, CRLF)),
      parse(HELP.replace("Thinking level: off, minimal, low, medium, high, xhigh", "Level (default high): off, high")),
      parse(HELP.replace("Thinking level: off, minimal, low, medium, high, xhigh", "Thinking level: Off, High")),
      parse(HELP.replace("  --thinking <level>       Thinking level: off, minimal, low, medium, high, xhigh", "")),
      parse("x--flag _--under é--accent ---triple --9digit --a –--en --UPPER --ok-2-x"),
      parse(`Built-in Tool Names:${LF}  read - a${LF}  tool2 - b${LF}${ch(0x3000)}grep${ch(0x3000)}- c`),
      parse(`Built-in Tool Names:   ${LF}  read - a${LF}  \t  ${LF}  bash - b`),
      parse(`Built-in Tool Names:${CRLF}  read - a${CRLF}  bash - b${CRLF}${CRLF}  late - c`),
      parse(`Built-in Tool Names:${LF}  read - a${ch(0x2028)}  bash - b${CR}  edit - c${LF}  write - d`),
      parse(`Built-in Tool Names: read - a`),
      parse(TABLE),
      parse(TABLE.replace("provider", `${ESC}[2mprovider${ESC}[0m`).replaceAll(LF, CRLF)),
      parse(`${TABLE}${LF}openai     sk-abcdefghijklmnop  1K${LF}custom     Bearer   abcdefghijklmnop${LF}lonely`),
      parse(["provider model", `a${ch(0xa0)}b`, `c${ch(0x200b)}d e`, "provider model", "f g"].join(ch(0x1c))),
      parse(["x", "provider model", "a b"].join(ch(0x85)) + ch(0x2028) + "c d" + ch(0x0b) + "e f" + CR + "g h"),
      parse("No models available. Configure a provider first."),
      parse("  No models available"),
      parse(`x${LF}No models matching "q"`),
      parse("No models availableX"),
      parse("No models available_"),
      parse("No models availableé"),
      parse(`${ESC}[33mNo models available${ESC}[0m`),
      parse(`x${CR}No models available`),
      parse(`No models matching${LF}No models available`),
      parse(""),
    ]);
    // 场景确实走到了：表格读出三行、凭据行打上记号、两种空表原因、思考级别解析不出时用后备
    expect(python[0]?.["help"]).toMatchObject({ thinking_levels: ["off", "minimal", "low", "medium", "high", "xhigh"], builtin_tools: ["read", "bash", "edit_x"] });
    expect(python[3]?.["help"]).toMatchObject({ thinking_levels: [] });
    expect(python[4]?.["help"]).toMatchObject({ thinking_levels: ["off", "minimal", "low", "medium", "high", "xhigh", "max"] });
    expect(python[11]?.["rows"]).toHaveLength(3);
    expect(JSON.stringify(python[13]?.["lines"])).toContain('"sk-abcdefghijklmnop",true');
    expect([python[16]?.["empty_reason"], python[18]?.["empty_reason"], python[19]?.["empty_reason"]]).toEqual(["no_models", "no_match", null]);
  });

  it("按种子拼出来的文字：每个种子 400 段", () => {
    const pieces = [
      "provider", "model", "step", "step-5", "--thinking", "<level>", "Thinking level:", "off, high", "Off", ":", ",", " ",
      "  ", "\t", LF, CRLF, CR, ch(0x85), ch(0x2028), ch(0x1c), ch(0xa0), ch(0x3000), "Built-in Tool Names:", "  read - x",
      "No models available", "No models matching", "--no-mcp", "x--y", "_", "é", `${ESC}[1m`, `${ESC}[0m`, "sk-abcdefghijkl12",
      "Bearer", "abcdefghijklmnop", "-", "--", "---", "--a-b", BS,
    ];
    const requests: ProbeRequest[] = [];
    for (const seed of [41, 42, 43]) {
      const next = prng(seed);
      for (let index = 0; index < 400; index += 1) {
        const size = 1 + Math.floor(next() * 24);
        requests.push(parse(Array.from({ length: size }, () => pieces[Math.floor(next() * pieces.length)] as string).join("")));
      }
    }
    agree(requests);
  });
});

describe("child_env", () => {
  const VARIABLES: Record<string, string> = {
    GIT_DIR: "x",
    git_work_tree: "y",
    GITHUB_TOKEN: "x",
    Npm_Token: "x",
    VAULT_TOKEN: "x",
    KEEP_ME: "1",
    GIT_TERMINAL_PROMPT: "1",
    Gcm_Interactive: "always",
    PYTHONDONTWRITEBYTECODE: "0",
  };

  it("移除、保留、配置追加、extra 与强制带上的变量", () => {
    const saved = Object.fromEntries(Object.keys(VARIABLES).map((name) => [name, process.env[name]]));
    Object.assign(process.env, VARIABLES);
    try {
      const request = (config: unknown, extra: [string, string][] | null = null): ProbeRequest => ({ op: "dispatch.child_env", config_json: JSON.stringify(config), extra });
      const python = agree([
        request({}),
        request({ env_remove: ["KEEP_ME", "keep_me"], env_keep: ["vault_token"] }),
        request({ env_keep: ["GIT_DIR", "GITHUB_TOKEN"] }),
        request({}, [["PI_EXTRA", "1"], ["Path", "C:/x"], ["GITHUB_TOKEN", "back"], ["NoDefaultCurrentDirectoryInExePath", "0"]]),
      ]);
      expect(python[1]?.["removed"]).toEqual(expect.arrayContaining(["GIT_DIR", "GIT_WORK_TREE", "GITHUB_TOKEN", "KEEP_ME", "NPM_TOKEN"]));
      expect(python[1]?.["removed"]).not.toContain("VAULT_TOKEN");
    } finally {
      for (const [name, value] of Object.entries(saved)) {
        if (value === undefined) delete process.env[name];
        else process.env[name] = value;
      }
    }
  });
});

describe("cwd_relative_parts", () => {
  it("不是绝对路径、却在当前目录下存在的部分；第一项不带目录时是程序名", () => {
    const dir = join(ROOT, "relative");
    mkdirSync(join(dir, "sub"), { recursive: true });
    writeFileSync(join(dir, "a.txt"), "");
    writeFileSync(join(dir, "sub", "b.txt"), "");
    const commands = [
      ["a.txt"], ["x", "a.txt"], ["sub/b.txt"], [`.${BS}a.txt`], ["x", `sub${BS}b.txt`, "missing.txt"], ["x", dir, join(dir, "a.txt")],
      ["x", `${BS}Windows`, "/Windows", "C:Windows", `${BS}${BS}?${BS}C:${BS}Windows`], ["x", "sub", ".", ".."], ["x", ""],
    ];
    const python = agree(commands.map((command) => ({ op: "roles.cwd_relative", cwd: dir, command })));
    expect(python.map((result) => result["parts"])).toEqual([[], ["a.txt"], ["sub/b.txt"], [`.${BS}a.txt`], [`sub${BS}b.txt`], [], process.platform === "win32" ? [] : ["/Windows"], ["sub", ".", ".."], []]);
  });
});

describe.runIf(process.platform === "win32")("run_capture", () => {
  const dir = join(ROOT, "capture");
  mkdirSync(join(dir, "missing-parent"), { recursive: true });
  const script = join(dir, "emit.mjs");
  writeFileSync(
    script,
    [
      'const mode = process.argv[2];',
      'if (mode === "bytes") { process.stdout.write(Buffer.from([0xef, 0xbb, 0xbf, 0x61, 0xff, 0x0d, 0x0a, 0xe2, 0x80, 0xa8, 0xc3])); process.stderr.write("err"); process.exitCode = 7; }',
      'if (mode === "env") process.stdout.write(`${process.env.FOO_CASE}|${process.env.CAPTURE_ONLY ?? "-"}`);',
      'if (mode === "stdin") { let size = 0; process.stdin.on("data", (chunk) => { size += chunk.length; }); process.stdin.on("end", () => process.stdout.write(`stdin ${size}`)); }',
      'if (mode === "cwd") process.stdout.write(process.cwd());',
      'if (mode === "exit") process.exit(Number(process.argv[3]));',
      'if (mode === "sleep") setTimeout(() => process.stdout.write("late"), 20000);',
    ].join(LF),
  );
  const batch = join(dir, "echo.cmd");
  writeFileSync(batch, ["@echo off", "echo out %1", "echo err 1>&2", "exit /b 3", ""].join(CRLF));
  const badExe = join(dir, "bad.exe");
  writeFileSync(badExe, "not a program");
  const node = process.execPath;
  const capture = (cmd: string[], options: { timeout?: number; env?: [string, string][] | null; cwd?: string | null } = {}): ProbeRequest => ({
    op: "dispatch.run_capture",
    cmd,
    timeout: options.timeout ?? 30,
    env: options.env ?? null,
    cwd: options.cwd ?? null,
  });

  it("退出码、输出的字节、批处理、环境、stdin、cwd、找不到与起不来、正常超时", () => {
    const environment = Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined);
    const python = agree([
      capture([node, script, "bytes"]),
      capture([batch, "arg"]),
      capture([node, script, "env"], { env: [...environment, ["Foo_Case", "1"], ["FOO_CASE", "2"], ["CAPTURE_ONLY", "yes"]] }),
      capture([node, script, "stdin"]),
      capture([node, script, "cwd"], { cwd: dir }),
      capture([node, script, "exit", "-1"]),
      capture([node, script, "exit", "255"]),
      capture([join(dir, "nope.exe")]),
      capture(["themis-no-such-program-xyz"]),
      capture([badExe]),
      capture([node, script, "cwd"], { cwd: join(dir, "missing-parent", "missing") }),
      capture([node, script, "sleep"], { timeout: 2 }),
    ]);
    expect(python.map((result) => result["code"])).toEqual([7, 3, 0, 0, 0, 4294967295, 255, 127, 127, 126, 126, 124]);
    expect(python[11]).toMatchObject({ stdout: "", stderr: "timeout after 2s" });
    expect(String(python[7]?.["stderr"])).toMatch(/^\[WinError 2\] /u);
    expect(String(python[9]?.["stderr"])).toMatch(/^\[WinError 216\] /u);
  });

  it("只测 TS：经 .cmd 起的进程树超时之后整棵树一起结束，按时返回 124（Python 会挂到孙进程退出）", async () => {
    const wrapper = join(dir, "sleepy.cmd");
    copyFileSync(script, join(dirname(wrapper), "sleepy.mjs"));
    writeFileSync(wrapper, ["@echo off", `"${node}" "%~dp0sleepy.mjs" sleep`, ""].join(CRLF));
    const started = performance.now();
    const result = await runCapture([wrapper], { timeout: 2 });
    expect(result).toEqual([124, "", "timeout after 2s"]);
    expect(performance.now() - started).toBeLessThan(15_000);
  });
});
