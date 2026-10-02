# 08 offline planner review

Verdict: REVISE

审查对象是规划端直接实现的提交 `04d37e5` 相对基线 `f52dc20058b0997a2abce80711a372bb463f0558`。本轮没有 Pi attempt、`candidate.patch`、`scope.json` 或调度器 verdict，因此不能用 Pi 执行证据签发 PASS。独立 Codex 复审会话因本机 rollout 不可用而 BLOCKED；没有用执行器自述替代证据。

## 已核对事实

- 08 新增离线聚焦测试 32 项通过；`compileall`、`git diff --check` 通过。
- `tests/test_dispatch.py` 在 WSL Python 3.12 的本地 stub 环境通过 260 项检查、0 failed；该结果只覆盖调度器自测，不证明真实 Pi/provider 接线。
- 六份 builtin artifact Schema 通过 Draft 2020-12 元校验，且公共 artifact 示例通过实例校验。
- 01–06 新增模块只完成结构和最小 happy-path，增强验收所需的权限、持久化、原始事件、进程和锁闭包证据不足；01–06 门保持 `REVISE/BLOCKED`。

## 必须返工或保持阻塞的发现

1. `plugins/` 下没有七个实际插件目录、manifest、lock 和三份可选择配方；catalog 只消费调用方传入的任意行，不能证明 A01/A28/T01。
2. `deterministic_check.py` 已拒绝没有 dispatcher receipt 的 PASS，但仍没有真实 dispatcher receipt、候选/环境账本或生产检查登记；A13/A27/T14/T28 只能是 `REFERENCE_ONLY/BLOCKED`。
3. regression/mutation 目前只归约调用方状态，没有真实测试收集、测试字节/runner/environment 绑定、受控副本、语法/导入/环境失败分类和重复结果记录；A14–A17、T04、T15–T20 不能签发。
4. projection 是内存 helper，没有持久 outbox、consumer cursor、high-water、响应丢失或 handoff 崩溃恢复；T28/T29 保持 `BLOCKED`。
5. 01–06 的配置、授权、adapter、runtime、plugin lock 仍缺增强验收要求的权限交集、撤销/currentness、原始事件、PID fence、资源闭包和防伪绑定。不得把 `docs/code-kit-v2/01-06-local-implementation-status.md` 的离线结果当成阶段 PASS。

## 后续放行条件

先补齐上述离线 fixtures、可信身份绑定、七插件/三配方目录和独立复审证据，再重新运行逐项 A/T 矩阵。真实 Pi、provider、Windows/macOS、外部 09/10 连接器仍需另行环境和授权；在此之前生产发布门禁关闭。
