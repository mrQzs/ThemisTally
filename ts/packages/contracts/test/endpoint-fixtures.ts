// 决策端点的替身（迁移第 ④b4b 片写在决策命令的契约里，④b5b 挪出来给 mutate 共用）：单独的 node 进程跑
// probes/fake_endpoint.mjs，按顺序交回预先写好的回答，把收到的请求记进 requests.jsonl。被测命令照常用同步的 spawnSync 起。
import { spawn } from "node:child_process";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { LF, tempDir } from "./repo-fixtures.ts";

const PROBES = resolve(dirname(fileURLToPath(import.meta.url)), "..", "probes");
/** 假 key 的环境变量名：只用假 key，不碰凭据库。 */
export const KEY_NAME = "THEMIS_CONTRACT_DECISIONS_KEY";

export interface Reply {
  readonly status: number;
  readonly body: string;
}

export interface Endpoint {
  readonly port: number;
  requests(): unknown[];
  stop(): void;
}

export async function startEndpoint(replies: readonly Reply[]): Promise<Endpoint> {
  const dir = tempDir("endpoint");
  writeFileSync(join(dir, "replies.json"), JSON.stringify(replies));
  const child = spawn("node", [join(PROBES, "fake_endpoint.mjs"), dir], { stdio: "ignore" });
  const portFile = join(dir, "port");
  for (let waited = 0; !existsSync(portFile); waited += 50) {
    if (waited > 20_000) {
      child.kill();
      throw new Error("假端点 20 秒没起来");
    }
    await new Promise((done) => setTimeout(done, 50));
  }
  const log = join(dir, "requests.jsonl");
  return {
    port: Number(readFileSync(portFile, "utf8")),
    requests: () => (existsSync(log) ? readFileSync(log, "utf8").split(LF).filter(Boolean).map((line) => JSON.parse(line) as unknown) : []),
    stop: () => void child.kill(),
  };
}
