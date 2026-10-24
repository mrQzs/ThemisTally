// 按名字起程序时不查当前目录（内核第 77 轮，themistally-15 复核 T015 时实测）。当前目录里放改了名的 hostname.exe
// （只会打印主机名）冒充 git.exe、tasklist.exe；子进程的环境去掉 NoDefaultCurrentDirectoryInExePath（Claude Code
// 与 hub 的环境都设了它，不去掉的话测试会空过）。先做正对照，证明不加固时冒牌程序确实被执行；之后只认真程序才有
// 的特征：`git --version` 以 "git version" 开头，tasklist 的输出里有目标 pid。
import { spawnSync } from "node:child_process";
import { copyFileSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { hostname, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { bunExecutable } from "../src/native.ts";

const onWindows = process.platform === "win32";
const VAR = "NoDefaultCurrentDirectoryInExePath";
const HOST = hostname().toLowerCase();
const SRC = resolve(dirname(fileURLToPath(import.meta.url)), "..", "src");
const href = (name: string): string => JSON.stringify(pathToFileURL(join(SRC, name)).href);
const CLI_MAIN = resolve(SRC, "..", "..", "cli", "src", "main.ts");

/** 去掉了这个变量的环境。 */
function bareEnv(): NodeJS.ProcessEnv {
  return Object.fromEntries(Object.entries(process.env).filter(([name]) => name.toUpperCase() !== VAR.toUpperCase()));
}

describe.skipIf(!onWindows)("按名字起程序不查当前目录（第 77 轮）", () => {
  let plant = "";
  beforeEach(() => {
    plant = mkdtempSync(join(tmpdir(), "themis-plant-"));
    const fake = join(process.env["SystemRoot"] ?? "C:/Windows", "System32", "HOSTNAME.EXE");
    for (const name of ["git.exe", "tasklist.exe"]) copyFileSync(fake, join(plant, name));
  });
  afterEach(() => rmSync(plant, { recursive: true, force: true }));

  /** 在植入目录里、去掉变量的环境下跑一段 ESM 脚本，交回 stdout。 */
  function nodeIn(script: string): string {
    const done = spawnSync(process.execPath, ["--input-type=module", "-e", script], { cwd: plant, env: bareEnv(), encoding: "utf8" });
    expect(done.status, done.stderr).toBe(0);
    return done.stdout;
  }

  it("正对照：不加固时，Node 按名字起 git 执行的是当前目录里的冒牌程序", () => {
    const out = nodeIn('import { spawnSync } from "node:child_process"; process.stdout.write(spawnSync("git", { encoding: "utf8" }).stdout);');
    expect(out.trim().toLowerCase().startsWith(HOST)).toBe(true);
  });

  it("导入 harden 之后（Node）：git 是真的，pidAlive 认得出自己", () => {
    const out = nodeIn([
      `import ${href("harden.ts")};`,
      `import { pidAlive } from ${href("process.ts")};`,
      'import { spawnSync } from "node:child_process";',
      'process.stdout.write(JSON.stringify({ git: spawnSync("git", ["--version"], { encoding: "utf8" }).stdout, alive: pidAlive(process.pid) }));',
    ].join("\n"));
    const result = JSON.parse(out) as { git: string; alive: boolean | null };
    expect(result.git.startsWith("git version")).toBe(true);
    expect(result.alive).toBe(true);
  });

  it("第二道防线：不导入 harden，pidAlive 也用 System32 里的 tasklist", () => {
    const out = nodeIn(`import { pidAlive } from ${href("process.ts")}; process.stdout.write(String(pidAlive(process.pid)));`);
    expect(out).toBe("true");
  });

  it("Bun 的进程监督（bun:ffi 的 CreateProcessW）：不加固时执行冒牌程序，导入 harden 之后执行真的 tasklist", () => {
    const run = (withHarden: boolean, args: readonly string[]): string => {
      const out = join(plant, `ffi-${String(withHarden)}.out`);
      const script = [
        withHarden ? `import ${href("harden.ts")};` : "",
        `import { runSupervised } from ${href("supervise.ts")};`,
        "const env = Object.entries(process.env).filter((pair) => typeof pair[1] === 'string');",
        `await runSupervised(["tasklist", ...${JSON.stringify(args)}.map((a) => a.replace("<pid>", String(process.pid)))], { cwd: ${JSON.stringify(tmpdir())}, env, timeout: 60,`,
        `  grace: 1, handleSignals: false, stdout: { path: ${JSON.stringify(out)}, how: "truncate" }, stderr: { path: ${JSON.stringify(`${out}.err`)}, how: "truncate" } });`,
        "process.stdout.write(String(process.pid));",
      ].join("\n");
      const file = join(plant, `ffi-${String(withHarden)}.ts`);
      const write = spawnSync(process.execPath, ["-e", `require("node:fs").writeFileSync(${JSON.stringify(file)}, ${JSON.stringify(script)})`]);
      expect(write.status).toBe(0);
      const done = spawnSync(bunExecutable(), ["--no-env-file", file], { cwd: plant, env: bareEnv(), encoding: "utf8" });
      expect(done.status, done.stderr).toBe(0);
      return `${done.stdout}|${readFileSync(out, "utf8")}`;
    };
    // 正对照不带参数：冒牌的 hostname 打印主机名（带参数时它的 stdout 是空的，认不出来）；真的 tasklist 的输出里有
    // Bun 自己的 pid
    const bare = (run(false, []).split("|")[1] ?? "").trim().toLowerCase();
    expect(bare.startsWith(HOST)).toBe(true);
    const [pidHardened, hardened] = run(true, ["/FI", "PID eq <pid>", "/NH"]).split("|") as [string, string];
    expect(hardened.split(/\s+/u).includes(pidHardened)).toBe(true);
  });

  it("TS 的 status（cli 的 main.ts 第一个 import 就是 harden）在植入了 git.exe 的仓库里照常回答", () => {
    expect(spawnSync("git", ["init", "-q", plant]).status).toBe(0);
    const pyargs = Buffer.from(JSON.stringify({ command: ["status"], repo: plant, task_id: null, json: true })).toString("base64");
    const done = spawnSync(process.execPath, [CLI_MAIN, "--pyargs-b64", pyargs], { cwd: plant, env: bareEnv(), encoding: "utf8" });
    expect(done.status, done.stderr).toBe(0);
    expect(done.stdout.trim()).toBe("[]");
  });
});
