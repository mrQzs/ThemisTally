"use strict";

// 启动分支判定：argv 里出现 --repo（原样一项，或以 --repo= 开头）就走服务分支，否则走外壳页分支。
// 纯函数、在主进程编排里、调 runShell 之前调用——外壳分支不解析参数、不起服务。
// --repox、--repo-x 都不算：它们既不是 --repo 这一项，也不以 --repo= 开头。
function launchMode(argv) {
  if (!Array.isArray(argv)) return "shell";
  for (const item of argv) {
    if (item === "--repo") return "service";
    if (typeof item === "string" && item.startsWith("--repo=")) return "service";
  }
  return "shell";
}

module.exports = { launchMode };
