// 桌面端的本机服务 @themis/ui（docs/themis-tally-3.0-桌面端.md，第 7 版 §0.0a）。入口有两种，跑的是同一个程序（T6）：
// 内核仓库里 `pi_dispatch.py ui …` 由调度器无条件转交给 TS（@themis/cli 的 `ui` 分支调用 runUi）；桌面应用里外壳
// 直接起打包好的单文件程序。两种都把参数整理成 UiArgs 交给 runUi，退出码照 §5.1：0 正常关闭，2 用法错误或找不到
// 前端资源，1 已有服务在运行或其他错误。
//
// 骨架（规划端提交）只做参数的检查；服务本身（握手、监听、会话、控制接口、安全基线、空闲退出、stdin EOF 的
// 关停）由 hub 的 D1-B 第 1 片实现，在 server.ts 的 serveUi 里（Bun 运行）。本包不在内核禁区里，经 hub 派给
// 执行器（T11）。serveUi 用动态导入：它那边要引用本文件的退出码常量，静态导入会成环。
import "@themis/base/harden"; // 第一个 import：桌面应用直接起打包好的程序时，这里就是入口（第 77 轮）
import { statSync } from "node:fs";

/** 交给 runUi 的参数：`pi_dispatch.py ui` 的 argparse 结果加上调度器补的几项（cmd_ui，pyargs-v1 的 ui 一支）。 */
export interface UiArgs {
  readonly command: readonly ["ui"];
  /** 仓库根目录（调度器已经 Repo.discover 过） */
  readonly repo: string;
  readonly desktop: boolean;
  readonly assets: string | null;
  /** 用量路由原样交给 `logs usage` 的会话记录（可以为空） */
  readonly transcript: readonly string[];
  /** 空闲多少秒之后退出；null 时读配置 ui.idle_timeout_seconds（缺省 1800） */
  readonly idle_timeout: number | bigint | null;
  /** 服务起子进程回调内核用的 Python 解释器与 pi_dispatch.py（T2：`<python> <kernel> --repo <repo> <argv…> --json`） */
  readonly python: string;
  readonly kernel: string;
}

export interface UiIo {
  readonly stdout: NodeJS.WritableStream;
  readonly stderr: NodeJS.WritableStream;
}

export const EXIT_OK = 0;
export const EXIT_ERROR = 1;
export const EXIT_USAGE = 2;

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

/** 参数的检查（§5.1）：不带 --desktop、前端资源目录不在、空闲时限不是正整数，都是用法错误。通过时返回 null。 */
export function checkArgs(args: UiArgs): string | null {
  if (!args.desktop) return "管理台只由桌面应用启动";
  if (args.assets === null || !isDirectory(args.assets)) return `找不到前端资源目录：${String(args.assets)}`;
  if (args.idle_timeout !== null && !(Number(args.idle_timeout) > 0)) return `--idle-timeout 必须是正整数：${String(args.idle_timeout)}`;
  return null;
}

/** 跑服务：参数检查通过之后转交 serveUi（server.ts）。 */
export async function runUi(args: UiArgs, io: UiIo = { stdout: process.stdout, stderr: process.stderr }): Promise<number> {
  const problem = checkArgs(args);
  if (problem !== null) {
    io.stderr.write(`ERROR: ${problem}\n`);
    return EXIT_USAGE;
  }
  const { serveUi } = await import("./server.ts");
  return serveUi(args, io);
}
