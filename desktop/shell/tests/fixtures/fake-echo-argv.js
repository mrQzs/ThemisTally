// 参数回显替身：把拿到的 argv 原样印成 JSON，证明参数没有经 shell 解释。
process.stdout.write(`${JSON.stringify(process.argv.slice(2))}\n`);
process.stderr.write("err-line\n");
