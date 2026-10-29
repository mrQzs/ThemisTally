// 常量表逐项对照（迁移计划第 ④ 步的切换）：TS 里照抄的 pi_dispatch 常量与 Python 的当前值一致，Python 改了而 TS 没跟上，
// 这里就红。命令行契约只覆盖走得到的分支，常量里没用到的那几项（例如某个状态）靠这里核。
import { spawnSync } from "node:child_process";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { TS_PARENT_ENV_PREFIX, TS_PARENT_NAMES_ENV } from "@themis/base/parent-env";
import { WAIT_ACTIVE_STATES } from "@themis/dispatcher/attempt-commands";
import { REVIEWABLE_STATES } from "@themis/dispatcher/check-commands";
import { TERMINAL_STATES, VERDICTS } from "@themis/dispatcher/evidence";
import { FAILURE_CLASSES } from "@themis/dispatcher/gates";
import { MUTATION_DEFAULT_TIMEOUT } from "@themis/dispatcher/mutate";
import { RESOURCE_FLAGS } from "@themis/dispatcher/pi-cli";
import { PENDING_INTEGRATION_STATES, TOOL_VERSION } from "@themis/dispatcher/prepare";
import { REPO } from "./harness.ts";

const TS = {
  TOOL_VERSION, RESOURCE_FLAGS, MUTATION_DEFAULT_TIMEOUT: Number(MUTATION_DEFAULT_TIMEOUT), VERDICTS, FAILURE_CLASSES,
  REVIEWABLE_STATES, TERMINAL_STATES, PENDING_INTEGRATION_STATES, WAIT_ACTIVE_STATES, TS_PARENT_ENV_PREFIX, TS_PARENT_NAMES_ENV,
};

describe("常量表", () => {
  it("与 pi_dispatch 一致", () => {
    const program = [
      "import json, sys",
      `sys.path.insert(0, ${JSON.stringify(join(REPO, "scripts"))})`,
      "import pi_dispatch as pd",
      `print(json.dumps({name: getattr(pd, name) for name in ${JSON.stringify(Object.keys(TS))}}))`,
    ].join(String.fromCharCode(10));
    const done = spawnSync(process.env["THEMIS_PYTHON"] ?? "python", ["-c", program], { encoding: "utf8" });
    expect(done.status, done.stderr).toBe(0);
    expect(JSON.parse(done.stdout)).toEqual(TS);
  });
});
