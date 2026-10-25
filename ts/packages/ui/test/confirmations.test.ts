// 预览确认号表的单元用例（桌面端 §5.3、D6）：TTL 边界、一次性、表满先清过期再挤最早发出的未用号、argv 绑定核对、43 位
// base64url。直接单测 ConfirmationTable（不起子进程、不起服务），时钟用可注入的 now 拨过 60 秒。
import { describe, expect, it } from "vitest";
import { argvMatches, CONFIRMATION_TTL_MS, ConfirmationTable, MAX_CONFIRMATIONS } from "../src/confirmations.ts";

const TOKEN = `v1;config=${"0".repeat(64)}`;
const ARGV = ["config", "role", "set", "execution", "manual"];

describe("ConfirmationTable", () => {
  it("C1：TTL 边界——正好 60 秒仍有效、过 60 秒无效（过期即失效）", () => {
    let now = 1000;
    const table = new ConfirmationTable({ now: () => now });
    const record = table.issue("role.set", ARGV, TOKEN, false);
    now = 1000 + 60_000; // 正好 60 秒
    expect(table.get(record.id), "正好 60 秒仍有效").not.toBeNull();
    now = 1000 + 60_000 + 1; // 过 60 秒
    expect(table.get(record.id), "过 60 秒过期").toBeNull();
    expect(CONFIRMATION_TTL_MS).toBe(60_000);
  });

  it("C2：确认号一次性——取走后不在表里，再取回 null", () => {
    const table = new ConfirmationTable({ now: () => 1000 });
    const record = table.issue("role.set", ARGV, TOKEN, false);
    expect(table.get(record.id)).not.toBeNull();
    expect(table.consume(record.id), "第一次用掉").toBe(true);
    expect(table.get(record.id), "一次性：用掉即不在表里").toBeNull();
    expect(table.consume(record.id), "第二次取不到").toBe(false);
  });

  it("C3：表满先清过期；清完还满就挤掉最早发出、还没用的那个", () => {
    let now = 1000;
    const table = new ConfirmationTable({ now: () => now });
    const ids: string[] = [];
    for (let i = 0; i < MAX_CONFIRMATIONS; i += 1) {
      ids.push(table.issue("role.set", ARGV, TOKEN, false).id);
      now += 1; // 逐个晚一步签发，issued_ms 互不相同
    }
    expect(table.size).toBe(MAX_CONFIRMATIONS);
    const extra = table.issue("role.set", ARGV, TOKEN, false);
    expect(table.get(ids[0] as string), "最早发出的被挤掉").toBeNull();
    expect(table.get(extra.id), "第 101 个能用").not.toBeNull();
    expect(table.size).toBe(MAX_CONFIRMATIONS);
  });

  it("C3b：表满时先清掉全部过期的（清完就不再挤）", () => {
    let now = 1000;
    const table = new ConfirmationTable({ now: () => now });
    for (let i = 0; i < MAX_CONFIRMATIONS; i += 1) {
      table.issue("role.set", ARGV, TOKEN, false); // 同一时刻签发，issued_ms 相同
    }
    now = 1000 + 60_000 + 1; // 全部过期
    const extra = table.issue("role.set", ARGV, TOKEN, false);
    expect(table.size, "过期的全被清掉，只剩新签发的").toBe(1);
    expect(table.get(extra.id)).not.toBeNull();
  });

  it("C4：绑定核对——argv 长度不同或有一项不同即判不符；action/state/needsYes 记在表里", () => {
    const table = new ConfirmationTable({ now: () => 1000 });
    const record = table.issue("role.set", ARGV, TOKEN, true);
    expect(record.action).toBe("role.set");
    expect(record.state).toBe(TOKEN);
    expect(record.needsYes).toBe(true);
    expect(argvMatches(record.argv, ARGV), "完全一致").toBe(true);
    expect(argvMatches(record.argv, ["config", "role", "set", "execution"]), "长度不同").toBe(false);
    expect(argvMatches(record.argv, ["config", "role", "set", "execution", "disabled"]), "有一项不同").toBe(false);
    expect(argvMatches(record.argv, [...ARGV, "--extra"]), "多一项").toBe(false);
  });

  it("C5：编号是 43 位 base64url、彼此不同", () => {
    const table = new ConfirmationTable();
    const seen = new Set<string>();
    for (let i = 0; i < 5; i += 1) {
      const id = table.issue("role.set", ARGV, TOKEN, false).id;
      expect(id).toMatch(/^[A-Za-z0-9_-]{43}$/u);
      seen.add(id);
    }
    expect(seen.size).toBe(5);
  });
});
