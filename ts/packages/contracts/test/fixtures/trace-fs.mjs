// status-inputs.test.ts 的追踪钩子，由 `node --import` 预载。改写 node:fs 的几个同步函数，记下碰过的路径；再调
// syncBuiltinESMExports()，让 `import { readFileSync } from "node:fs"` 这类具名导入也换成改写过的版本。进程退出时
// 把记录写到环境变量 THEMIS_TRACE_OUT 指的文件（用改写之前的 writeFileSync）。
import fs from "node:fs";
import { syncBuiltinESMExports } from "node:module";
import { fileURLToPath } from "node:url";

const KINDS = {
  statSync: "stat", lstatSync: "stat", existsSync: "stat", readdirSync: "list", opendirSync: "list", readFileSync: "read",
  openSync: "read",
};
const log = [];
const write = fs.writeFileSync;
for (const [name, kind] of Object.entries(KINDS)) {
  const original = fs[name];
  fs[name] = function traced(target, ...rest) {
    if (typeof target === "string") log.push([kind, target]);
    else if (target instanceof URL) log.push([kind, fileURLToPath(target)]);
    else if (Buffer.isBuffer(target)) log.push([kind, target.toString("utf8")]);
    return original.call(this, target, ...rest);
  };
}
syncBuiltinESMExports();
process.on("exit", () => write(process.env.THEMIS_TRACE_OUT, JSON.stringify(log)));
