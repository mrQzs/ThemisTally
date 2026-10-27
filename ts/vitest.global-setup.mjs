// 装好戳记过期时整轮先停（④b4a，themistally-15 建议）：经启动器的契约会全报“TS 依赖与 bun.lock 不一致”，跑几分钟才看到
// 一片红；变异工具单跑一个契约文件时也一样先停。比对与启动器（pi_dispatch.ts_launch_command）是同一个算法。没有戳记时不拦：
// 不是用 bun install 装的环境（例如 npm ci）本来就不经启动器。
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { depsDigest } from "./tools/stamp-install.mjs";

export default function checkInstallStamp() {
  const root = dirname(fileURLToPath(import.meta.url));
  let stamp;
  try {
    stamp = JSON.parse(readFileSync(join(root, "node_modules", ".themis-installed"), "utf8"));
  } catch {
    return;
  }
  if (stamp?.deps_sha256 !== depsDigest(root)) {
    throw new Error("TS 依赖与 bun.lock 不一致：先在 ts/ 下运行 bun install --frozen-lockfile（只按锁文件重新链接，不改依赖）");
  }
}
