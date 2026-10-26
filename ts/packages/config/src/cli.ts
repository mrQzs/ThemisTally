// config 命令的 TS 入口（迁移第 ③ 步）：@themis/cli 收到 command 以 config 开头的 pyargs 时交给这里。
// 报错照 kit_config.main：ConfigError 写 `ERROR: ` 加 redact_tokens 之后的消息，退出码是它带的码。
// kit_root 与 lock_wait_seconds 只从 pyargs 的 context 取（迁移计划第 ③ 步：不设环境变量、也不设默认值），缺了按内部错误退出。
import { PyOut } from "@themis/base/pyfmt";
import { redactTokens } from "@themis/base/secrets";
import { type ConfigArgs, cmdHistory, cmdSecret, cmdShow, cmdValidate } from "./commands.ts";
import { ConfigError, kitAt } from "./validate.ts";

export interface ConfigContext {
  readonly kit_root?: unknown;
  readonly lock_wait_seconds?: unknown;
}

/** 已经转交给 TS 的 config 子命令；其余的仍由 Python 回答（③c 起逐片加进来）。 */
export const CONFIG_COMMANDS = [
  "config validate",
  "config show",
  "config history",
  "config secret",
];

export async function runConfig(args: ConfigArgs & { readonly context?: ConfigContext }, out: PyOut): Promise<number> {
  const kitRoot = args.context?.kit_root;
  const rawWait = args.context?.lock_wait_seconds;
  // 启动器交的是 Python 的 float（30.0），JSON 里写成整数时 pyjson 读成 bigint：两种都收
  const lockWait = typeof rawWait === "bigint" ? Number(rawWait) : rawWait;
  if (typeof kitRoot !== "string" || !kitRoot || typeof lockWait !== "number") {
    out.printErr("ERROR: 内部错误：启动器没有经 pyargs 的 context 交来 kit_root 与 lock_wait_seconds");
    return 1;
  }
  const kit = kitAt(kitRoot);
  try {
    switch (args.command.join(" ")) {
      case "config validate":
        return cmdValidate(args, kit, out);
      case "config show":
        return await cmdShow(args, kit, out);
      case "config history":
        return cmdHistory(args, out);
      case "config secret":
        if (args.action === "set") throw new ConfigError("内部错误：secret set 不转交给 TS（迁移计划第 ③ 步的不转交名单）");
        return await cmdSecret(args, out);
      default:
        out.printErr(`ERROR: TS 实现还没有这条命令：${args.command.join(" ")}`);
        return 2;
    }
  } catch (error) {
    if (error instanceof ConfigError) {
      out.printErr(`ERROR: ${redactTokens(error.message)}`);
      return error.code;
    }
    throw error;
  }
}
