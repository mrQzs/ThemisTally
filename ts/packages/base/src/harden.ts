// 按名字起程序时不查当前目录（内核第 77 轮，pi_dispatch.harden_executable_search 的对应）。Windows 上
// CreateProcessW 与 libuv 按名字找程序时，本进程自己的当前目录排在 System32 之前：仓库里放一个 git.exe 或
// tasklist.exe，在仓库里跑就会执行它。环境里有 NoDefaultCurrentDirectoryInExePath（值不论）就不查；实测 Node 与
// Bun 在运行时给 process.env 赋值就生效（Bun 的 bun:ffi CreateProcessW 也认）。
//
// 这是一个副作用模块：每个入口（cli 的 main.ts、native-helper.ts、ui 的 main.ts）的第一个 import 就是它。ESM 的
// import 会被提升、按次序深度优先求值，排在第一个才能赶在其他模块的顶层代码之前（themistally-15）。
export const EXE_SEARCH_GUARD = "NoDefaultCurrentDirectoryInExePath";

if (process.platform === "win32") process.env[EXE_SEARCH_GUARD] = "1";
