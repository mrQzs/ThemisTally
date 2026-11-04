// 跑到静止（⑤i 设计稿第 5 节；⑤j2 起是真的 cmd_run，⑤j 设计稿第 5 节）。三边从同一个初始信箱、照同一份按种子生成的剧本，各自跑真的
// cmd_run（串行、空闲即退）直到它退出，逐字比交回值、stdout、跑完时的信箱与 tasks 下的文件、state.json、账本、git 状态与 runner 的调用序列。
// 探针换上四样：指纹交回常数、kernel_changes 交回 []、sleep 只把钉住的时钟往后挪、第 400 次 sleep 抛错（三边都抛，比的是崩溃）。
// 时刻与信编号钉住，不换占位；账本里进程自己的 pid 照 pidNormalized 换占位，回合出意外那封信照 crashNormalized 比（⑤i 设计稿第 7 节）。
// 与生产不同的一点：办了事的步之间时钟不动，同一步里投出的几封信时刻相同，在同一个信箱里按发件人别名排序，而不是按投递先后。两边一样，
// 对照照样成立。不写转义序列。
import { afterAll, describe, expect, it } from "vitest";
import { AT, agreeFlow, returned } from "./flow-fixtures.ts";
import { REPLAY_TIMEOUT } from "./harness.ts";
import { removeCreated, tempDir } from "./repo-fixtures.ts";
import { crashNormalized, events } from "./engine-fixtures.ts";
import { quiesceRequest, quiesceScene } from "./quiesce-script.ts";
import { pidNormalized } from "./runner-fixtures.ts";

afterAll(removeCreated);

const SEEDS = Array.from({ length: 30 }, (_, index) => index + 1);
const normalized = (state: Record<string, unknown>): unknown =>
  crashNormalized(pidNormalized(state, new Set([Number(state["self_pid"])])) as Record<string, unknown>);

describe("第 ⑤j2 片：跑到静止（真的 cmd_run，按种子生成剧本）", () => {
  it(`种子 ${SEEDS[0]}–${SEEDS[SEEDS.length - 1]}：三边照同一份剧本跑真的 cmd_run，交回值、stdout、信箱、state.json、账本与 runner 的调用序列逐字相同`, () => {
    const roots = tempDir("quiesce-inputs");
    const requests = SEEDS.map((seed) => quiesceRequest(seed, quiesceScene(), roots));
    // 每批 5 个种子，每批给 REPLAY_TIMEOUT：整套并行时探针会慢好几倍（746cebe 的教训）
    const states = Array.from({ length: Math.ceil(requests.length / 5) },
      (_, at) => agreeFlow(requests.slice(at * 5, at * 5 + 5), normalized, REPLAY_TIMEOUT)).flat();
    // 三边一致只说明走的是同一条路；下面核对这批种子确实走到了设计稿第 5 节要的几条：结项放行依赖、扣信与到点放回、内核代办、回合出意外、
    // JEV 自动跑、当场重交；⑤j2 另加两条：靠 sleep 挪时钟等到扣信放回，正常空闲退出
    const seen = (name: string): number => states.filter((state) => events(state).some((event) => event["event"] === name)).length;
    expect(seen("dependency.released"), "每个种子都放行了 T002").toBe(SEEDS.length);
    expect(["letters.held", "letters.released", "route.kernel", "step.error", "jev.auto", "delivery.retried"].map((name) => seen(name) > 0))
      .toEqual([true, true, true, true, true, true]);
    const moved = states.filter((state) => events(state).some((event) => event["event"] === "letters.released" && String(event["at"]) > AT));
    expect(moved.length, "有种子靠 sleep 把时钟挪过基准、等到扣信放回").toBeGreaterThan(0);
    const idle = states.filter((state) => returned(state) === 0n && String(state["stdout"]).includes("hub 退出：处理了 "));
    expect(idle.length, "有种子正常空闲退出").toBeGreaterThan(0);
  }, 3_600_000);
});
