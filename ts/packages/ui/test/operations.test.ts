// 操作记录表的单元用例（桌面端 §5.3、D10）：状态机每一步只走一次、八键投影、容量 100 与淘汰、active() 数非终态。
// 直接单测 OperationTable（不起子进程、不起服务）。
import { describe, expect, it } from "vitest";
import { markRunning, MAX_OPERATIONS, OperationTable, operationView, settle } from "../src/operations.ts";

const ARGV = ["config", "role", "set", "execution", "manual"];

describe("OperationTable", () => {
  it("O1：状态机每一步只走一次（重复 settle 忽略）", () => {
    const table = new OperationTable();
    const op = table.create("op-1", "role.set", ARGV, 90, 1000);
    if (op === null) throw new Error("建记录失败");
    expect(op.state).toBe("queued");
    markRunning(op, 1100);
    expect(op.state).toBe("running");
    markRunning(op, 1200); // 重复：忽略
    expect(op.started_ms, "started_ms 只记第一次").toBe(1100);
    settle(op, "succeeded", null, { ok: true }, 1300);
    settle(op, "failed", "exit", { ok: false }, 1400); // 重复：忽略
    expect(op.state, "终态只落第一次").toBe("succeeded");
    expect(op.finished_ms).toBe(1300);
  });

  it("O1b：退出 4 的终态是 stale、超时的终态是 timed_out", () => {
    const table = new OperationTable();
    const stale = table.create("op-stale", "role.set", ARGV, 90, 1000);
    const timedOut = table.create("op-timeout", "role.set", ARGV, 90, 1000);
    if (stale === null || timedOut === null) throw new Error("建记录失败");
    settle(stale, "stale", null, {}, 1100);
    settle(timedOut, "timed_out", null, {}, 1100);
    expect(stale.state).toBe("stale");
    expect(stale.reason).toBeNull();
    expect(timedOut.state).toBe("timed_out");
  });

  it("O2：operationView 的八键投影（键一个不少、值可为 null）", () => {
    const table = new OperationTable();
    const op = table.create("op-2", "role.set", ARGV, 90, 1000);
    if (op === null) throw new Error("建记录失败");
    const view = operationView(op);
    expect(Object.keys(view).sort()).toEqual(
      ["action", "created_ms", "envelope", "finished_ms", "id", "reason", "started_ms", "state"].sort(),
    );
    expect(view["id"]).toBe("op-2");
    expect(view["action"]).toBe("role.set");
    expect(view["created_ms"]).toBe(1000);
    expect(view["started_ms"]).toBeNull();
    expect(view["finished_ms"]).toBeNull();
    expect(view["envelope"]).toBeNull();
  });

  it("O3：容量 100，满了淘汰最早结束的终态；没有可淘汰的终态时 create 回 null（路由据此回 503）", () => {
    const table = new OperationTable();
    const ids: string[] = [];
    for (let i = 0; i < MAX_OPERATIONS; i += 1) {
      const op = table.create(`op-${i}`, "role.set", ARGV, 90, 1000 + i);
      if (op === null) throw new Error("建记录失败");
      settle(op, "succeeded", null, {}, 2000 + i); // 逐个落到终态，finished_ms 递增
      ids.push(`op-${i}`);
    }
    expect(table.size).toBe(MAX_OPERATIONS);
    const extra = table.create("op-extra", "role.set", ARGV, 90, 3000);
    expect(extra, "满了但淘汰了最早结束的终态").not.toBeNull();
    expect(table.get(ids[0] as string), "最早结束的被淘汰").toBeNull();
    expect(table.size).toBe(MAX_OPERATIONS);

    const busy = new OperationTable();
    for (let i = 0; i < MAX_OPERATIONS; i += 1) {
      const op = busy.create(`run-${i}`, "role.set", ARGV, 90, 1000 + i);
      if (op === null) throw new Error("建记录失败");
      markRunning(op, 1500 + i); // 全部在跑（非终态）
    }
    expect(busy.create("op-full", "role.set", ARGV, 90, 4000), "没有可淘汰的终态：回 null").toBeNull();
  });

  it("O4：active() 数的是非终态记录", () => {
    const table = new OperationTable();
    const a = table.create("op-a", "role.set", ARGV, 90, 1000);
    const b = table.create("op-b", "role.set", ARGV, 90, 1000);
    if (a === null || b === null) throw new Error("建记录失败");
    markRunning(a, 1100);
    expect(table.active(), "queued 加 running 都算非终态").toBe(2);
    settle(b, "succeeded", null, {}, 1200);
    expect(table.active()).toBe(1);
    settle(a, "failed", "exit", {}, 1300);
    expect(table.active(), "都终态了").toBe(0);
  });
});
