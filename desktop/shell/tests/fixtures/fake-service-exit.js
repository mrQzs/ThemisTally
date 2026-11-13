"use strict";

// 假本机服务（握手成功后退出版）：先写一行合法握手，再按 FAKE_SERVICE_EXIT_CODE（缺省 3）退出，
// 用来测「握手成功后服务自己退出」那条路（外壳没有停它，byShell 要为假）。
// 延迟一点再退：握手的 stdout 是管道，写完立刻退有可能把行截断。
const LINE =
  JSON.stringify({
    themis_ui: 1,
    bootstrap: "http://127.0.0.1:8123/bootstrap/nonceABC",
    origin: "http://127.0.0.1:8123",
    control: "ctrl-tok-XYZ",
    pid: 4242,
  }) + "\n";

process.stdout.write(LINE);

const code = Number(process.env.FAKE_SERVICE_EXIT_CODE || "3");
setTimeout(() => process.exit(code), 60);
