// 假的本机 CLI（迁移第 ③d 片起，配置中心会运行本机 CLI 的命令用）：fake-pi.mjs 按旁边的 fake-pi.json 回答 --version、
// --help、--list-models [模型] 与 auth check，并把收到的 argv 与 child_env 的几项结果记进 FAKE_PI_LOG。pi.cmd 是 npm
// 样式的垫片（resolve_pi_command 绕过它直接起 node；scan 与 PI_DISPATCH_PI_CMD 指向它时经 CreateProcessW 起 cmd.exe）。
// claude.cmd 只回答版本，codex.exe 是起不来的文件。转义的反斜杠用 String.fromCharCode(92) 拼。
import { spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { BUN } from "./harness.ts";

const BS = String.fromCharCode(92);
const LF = String.fromCharCode(10);
const CRLF = String.fromCharCode(13, 10);
const WIN = process.platform === "win32";

/** PATH 上某个程序所在的目录（改 PATH 之前查）。 */
export function dirOf(program: string): string {
  const done = spawnSync(WIN ? "where" : "which", [program], { encoding: "utf8" });
  const first = done.stdout.split(/\r?\n/u).find(Boolean);
  if (!first) throw new Error(`PATH 上没有 ${program}`);
  return dirname(first);
}

export const FAKE_PI = [
  'import { appendFileSync, readFileSync } from "node:fs";',
  'import { dirname, join } from "node:path";',
  'import { fileURLToPath } from "node:url";',
  "const here = dirname(fileURLToPath(import.meta.url));",
  'const spec = JSON.parse(readFileSync(join(here, "fake-pi.json"), "utf8"));',
  "const argv = process.argv.slice(2);",
  'const at = argv.indexOf("--list-models");',
  'const mode = argv.includes("--version") ? "version" : argv.includes("--help") ? "help" : at >= 0 ? (argv[at + 1] ? `list:${argv[at + 1]}` : "list") : argv[0] === "auth" ? "auth" : "other";',
  'const reply = spec[mode] ?? spec[mode.split(":")[0]] ?? { code: 9 };',
  "const seen = (name) => process.env[name] ?? null;",
  "if (process.env.FAKE_PI_LOG) {",
  '  const env = Object.fromEntries(["GIT_TERMINAL_PROMPT", "GCM_INTERACTIVE", "PYTHONDONTWRITEBYTECODE", "GITHUB_TOKEN", "FAKE_KEY", "NoDefaultCurrentDirectoryInExePath"].map((name) => [name, seen(name)]));',
  "  appendFileSync(process.env.FAKE_PI_LOG, JSON.stringify({ mode, argv, env }) + String.fromCharCode(10));",
  "}",
  'if (reply.out) process.stdout.write(Buffer.from(reply.out, "utf8"));',
  'if (reply.err) process.stderr.write(Buffer.from(reply.err, "utf8"));',
  "process.exitCode = reply.code ?? 0;",
  "",
].join(LF);

/**
 * 在 bin 里放假的 pi、claude、codex，返回只留它们、git、node、python、bun 与系统目录的 PATH（scan 找到的只有这几个假的）。
 * 经启动器的那一种要在 PATH 上找到装依赖时用的 bun.exe（启动器核对两者是同一个）；它所在的目录里只有 bun.exe。
 */
export function installFakeCli(bin: string): string {
  const keep = [bin, dirOf("git"), dirname(process.execPath), dirOf(process.env["THEMIS_PYTHON"] ?? "python"), dirname(BUN)];
  const system = WIN ? [join(process.env["SystemRoot"] ?? "C:/Windows", "System32"), process.env["SystemRoot"] ?? "C:/Windows"] : ["/usr/bin", "/bin"];
  mkdirSync(bin, { recursive: true });
  writeFileSync(join(bin, "fake-pi.mjs"), FAKE_PI);
  writeFileSync(join(bin, "pi.cmd"), ["@ECHO off", "SET dp0=%~dp0", `node "%dp0%${BS}fake-pi.mjs" %*`, ""].join(CRLF));
  writeFileSync(join(bin, "claude.cmd"), ["@echo off", "echo claude 9.9.9 (fake)", ""].join(CRLF));
  writeFileSync(join(bin, "codex.exe"), "not a program");
  return [...keep, ...system].join(WIN ? ";" : ":");
}
