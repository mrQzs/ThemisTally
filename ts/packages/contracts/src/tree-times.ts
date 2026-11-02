// 快照与还原用（迁移第 ⑤g 片，themistally-15 定的）：拷好的树里文件与目录的修改时刻照源树设回去。kit_hub 有两处拿修改时刻跟记录比
// （3233 的 candidate.patch，4271 的 candidate.patch 或 attempt 目录本身），它们也是“调用当时的状态”。cpSync 的 preserveTimestamps 只管文件，
// 目录要在内容放好之后再设（往里放东西会改它的时刻），由深到浅。链接与联接不进、不设。对应 python_probe.py 的 _copy_dir_times。
// utimes 经过 double 换算，与源时刻可能差几百纳秒；kit_hub 只比到秒，只有正好落在进位边界几百纳秒以内才会不同。
import { lstatSync, readdirSync, statSync, utimesSync } from "node:fs";
import { join } from "node:path";

export function copyTreeTimes(source: string, target: string): void {
  for (const name of readdirSync(source)) {
    const from = join(source, name);
    const info = lstatSync(from);
    if (info.isSymbolicLink()) continue;
    if (info.isDirectory()) copyTreeTimes(from, join(target, name));
    else setTimes(from, join(target, name));
  }
  setTimes(source, target);
}

function setTimes(from: string, to: string): void {
  const info = statSync(from, { bigint: true });
  utimesSync(to, Number(info.atimeNs) / 1e9, Number(info.mtimeNs) / 1e9);
}
