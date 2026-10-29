// 还原启动器换过名的运行时注入变量（迁移计划 D3，pi_dispatch.handoff_env 的对应）。BUN_OPTIONS、NODE_OPTIONS、NODE_PATH、
// BUN_INSPECT* 能往 TS 进程里塞代码，启动器不让它们以原名进本进程：原值换名成 THEMIS_PARENT_<原名>，换过的原名用逗号连起来
// 放进 THEMIS_PARENT_NAMES。这里照这份名单还原，之后 process.env 与这条命令走 Python 时的 os.environ 一致，pi、检查命令、
// git 钩子这些子进程照 Python 拿到它们。本进程不受影响：这几个变量都只在启动时读（实测 Bun 1.4.2：运行中改 NODE_PATH
// 不多出解析来源，tests/test_kernel_impl.py 锁着）。名单外的 THEMIS_PARENT_ 变量原样留着，与 Python 一样交给子进程。
//
// 副作用模块，自己不 import 任何东西：cli 的 main.ts 的第一个 import 就是它，赶在别的模块的顶层代码读环境之前。
export const TS_PARENT_ENV_PREFIX = "THEMIS_PARENT_";
export const TS_PARENT_NAMES_ENV = "THEMIS_PARENT_NAMES";

export function restoreParentEnv(env: Record<string, string | undefined>): void {
  const names = env[TS_PARENT_NAMES_ENV];
  if (names === undefined) return;
  delete env[TS_PARENT_NAMES_ENV];
  for (const name of names.split(",")) {
    const value = env[TS_PARENT_ENV_PREFIX + name];
    if (value === undefined) continue;
    delete env[TS_PARENT_ENV_PREFIX + name];
    env[name] = value;
  }
}

restoreParentEnv(process.env);
