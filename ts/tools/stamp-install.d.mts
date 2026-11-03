// stamp-install.mjs 给 TS 用的声明：hub 的 ts_install_if_stale 直接引它的 depsDigest（与 pi_dispatch.ts_deps_digest 同一个算法，
// tests/test_kernel_impl.py 对照），不另写一份。
export function depsDigest(tsRoot: string): string;
