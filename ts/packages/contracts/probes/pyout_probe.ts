// PyOut 对照的探针（TS 实现）：读 argv[2] 里的一串操作，经 PyOut({ bufferStdout: true }) 往 stdout、stderr 写，最后 flush
// （照 cli 的 runBuffered）。同一份源码由 `node`（类型擦除）与 `bun` 各跑一遍；Python 一侧写在 pyout.compare.test.ts 里。
import { readFileSync } from "node:fs";
import { PyOut } from "@themis/base/pyfmt";

type Op = ["print", string, boolean] | ["write", string] | ["flush"] | ["err", string];

const out = new PyOut({ bufferStdout: true });
for (const op of JSON.parse(readFileSync(process.argv[2] as string, "utf8")) as Op[]) {
  if (op[0] === "print") out.print(op[1], { flush: op[2] });
  else if (op[0] === "write") out.write(op[1]);
  else if (op[0] === "flush") out.flush();
  else out.printErr(op[1]);
}
out.flush();
