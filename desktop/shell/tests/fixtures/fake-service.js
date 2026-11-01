"use strict";

// 假本机服务：按 FAKE_SERVICE_MODE 切换行为，供 service.test.js 驱动 startService/stopService。
// 收到 stdin 的任何字节都以 9 退出（外壳的 stdin 一个字节都不写，所以正常应以 0 退出）。
const fs = require("node:fs");

const mode = process.env.FAKE_SERVICE_MODE || "ok";
const LINE = JSON.stringify({
  themis_ui: 1,
  bootstrap: "http://127.0.0.1:8123/bootstrap/nonceABC",
  origin: "http://127.0.0.1:8123",
  control: "ctrl-tok-XYZ",
  pid: 4242,
}) + "\n";

if (process.env.FAKE_SERVICE_ARGV_FILE) {
  fs.writeFileSync(process.env.FAKE_SERVICE_ARGV_FILE, JSON.stringify(process.argv.slice(2)));
}

if (mode === "exit2") {
  process.exit(2);
}

if (mode === "bad") {
  process.stdout.write("not-json\n");
} else if (mode !== "silent") {
  if (mode === "split") {
    process.stdout.write(LINE.slice(0, 20));
    setTimeout(() => process.stdout.write(LINE.slice(20)), 60);
  } else {
    process.stdout.write(LINE);
  }
}

if (mode === "after") {
  // 握手行之后再写一行带标记的内容：外壳只认第一行，标记不得泄漏
  setTimeout(() => process.stdout.write("MARKER-SECOND-LINE-MUST-NOT-APPEAR\n"), 60);
}

if (mode === "ignore-eof") {
  setInterval(() => {}, 1000);
}

let gotData = false;
process.stdin.on("data", () => {
  gotData = true;
});
process.stdin.on("end", () => {
  if (mode === "ignore-eof") return;
  if (gotData) process.exit(9);
  process.exit(mode === "exit7" ? 7 : 0);
});
process.stdin.on("error", () => {});
process.stdin.resume();

setTimeout(() => process.exit(0), 8000).unref();
