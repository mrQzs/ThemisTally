# 01–06 / 08 离线验收复核（2026-10-03，v6）

## 固定候选与已发布基线

- 实现候选：\`5d141298d052b291c1dba3fe35075d6303f0bbc8\`。
- 已发布合同重绑定提交：\`99bda89b9f61754b7bbdc206f4a1ed97425e16a5\`。
- 最新 39 对合同（01–06 各 3 个、08 S0–S6 各 3 个）已绑定实现候选；在候选源码上执行 \`pi_dispatch validate\` 时为 39/39 有效、0 警告。
- 当前没有 Pi attempt，因此本报告是规划端离线复核，不替代 \`review-pi\` 独立验收。

## 已通过的离线证据

- \`.agent/runs/offline-01-06-08-20261003-builtin-all-08/\`：107 收集、100 执行通过、7 个可选 Schema 依赖跳过，监督返回码 0，\`baseline_consistent=true\`，无漂移。
- \`.agent/runs/offline-01-06-08-20261003-expanded-all-08/\`：552 收集、544 执行通过、8 个可选 Schema 依赖跳过，监督返回码 0，\`baseline_consistent=true\`，无漂移。
- 已完成 \`python -m compileall -q scripts/codekit tests\` 与 \`git diff --check\`。
- SourceAnchor 构建器现在要求冻结资源字节，并验证 ResourceRef、完整资源摘要、半开字节区间和 excerpt 摘要；授权锁回执探针使用 strict JSON 并覆盖重复键负例。

## 全量发现结果

- 新 capture：\`.agent/runs/offline-01-06-08-20261003-full-discover-09/\`。
- 命令：\`python -B -m unittest discover -s tests -q\`。
- 监督器运行 900.031 秒后超时；\`returncode=null\`、\`timed_out=true\`、\`termination_confirmed=true\`、\`stray_processes=false\`，stdout/stderr 均为空，\`comparison.drift=[]\`。
- 该 capture 的 \`execution_status=complete\` 只表示取证文件完整，不表示测试通过。该结果标记为 \`TIMEOUT/BLOCKED\`，不能解释为 PASS。
- 历史全量发现曾记录 3 项 legacy source-lock 失败；当前超时没有产生新的失败指纹，因此不能据此改变已知失败归属。

## 门禁结论

01–06 与 08 继续为 \`REVISE/BLOCKED\` 的规划端离线状态。真实 Pi/provider、原生 Windows/macOS 进程、生产 dispatcher、计费系统及 09/10 外部 consumer 均为 \`NOT_RUN/BLOCKED\`；离线 fixture 和本地通过项不能提升为生产 PASS。下一步应先收集仍缺失的执行器/平台/连接器证据，再对对应合同建立 attempt 并交由独立复审。