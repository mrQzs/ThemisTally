// 作业状态模块（T054，T055 泛化成三类，T056/T057 再加 doctor 与 doctor-record 两类）：runtime-scan / runtime-probe /
// models / doctor / doctor-record 作业的状态放在页面之外的模块里，按 kind 分开存（每类一个槽，槽里记这个作业的
// 对象——runtime id 或 <task>.vN；同类作业同时只许有一个）。关掉对话框再打开接着看同一个作业；
// 在途的创建大家共用；每秒轮询（setTimeout 链、卸载即停、重开先查一次、没有作业时不排计时器）；
// 已用秒数从创建回应到达时算起；查询 404 按失败处理（错误信封并进 job.envelope、状态落 failed），其他失败当暂时的。
import { useCallback, useEffect, useSyncExternalStore } from 'react';
import { cancelJob as apiCancelJob, getJob, startJob, type Envelope, type JobKind, type JobState, type JobView } from '../api';

interface StoreState {
  job: JobView | null;
  // 槽里那个作业是哪个对象的（扫描是 null；探测与列模型是 runtime id，按版本记录核验是 <task>.vN；创建失败时是刚才想建的那个）。
  runtime: string | null;
  // 创建回应到达时的本地时间戳（毫秒）；没有作业时是 null。
  t0: number | null;
  createError: Envelope<unknown> | null;
  creating: boolean;
  // 每次提交都 +1：让 useSyncExternalStore 的快照换引用（已用秒数每秒也走一格）。
  tick: number;
}

const KINDS: readonly JobKind[] = ['runtime-scan', 'runtime-probe', 'models', 'doctor', 'doctor-record'];

function emptyState(): StoreState {
  return { job: null, runtime: null, t0: null, createError: null, creating: false, tick: 0 };
}

const snaps: Record<JobKind, StoreState> = {
  'runtime-scan': emptyState(),
  'runtime-probe': emptyState(),
  models: emptyState(),
  doctor: emptyState(),
  'doctor-record': emptyState(),
};

const listeners = new Set<() => void>();
const subscribers: Record<JobKind, number> = { 'runtime-scan': 0, 'runtime-probe': 0, models: 0, doctor: 0, 'doctor-record': 0 };
const timers: Partial<Record<JobKind, ReturnType<typeof setTimeout>>> = {};
const inflight: Partial<Record<JobKind, Promise<JobView | null>>> = {};

function isTerminal(state: JobState): boolean {
  return state === 'succeeded' || state === 'failed' || state === 'cancelled' || state === 'timed_out';
}

function commit(kind: JobKind, patch: Partial<Omit<StoreState, 'tick'>>): void {
  const prev = snaps[kind];
  snaps[kind] = { ...prev, ...patch, tick: prev.tick + 1 };
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function disconnectEnvelope(): Envelope<unknown> {
  return { ok: false, exit_code: null, data: null, output: [], messages: ['ERROR: 连不上本机服务（请求没有到达服务）'], command: [], elapsed_ms: 0 };
}

// 创建作业：在途的创建记在 inflight 里让大家共用；201 且正文是合法作业才落 job 与 t0，否则记 createError。
function doCreate(kind: JobKind, runtime?: string): Promise<JobView | null> {
  commit(kind, { creating: true, createError: null, job: null, runtime: runtime ?? null });
  const p = startJob(kind, runtime).then(
    (reply) => {
      const view = reply.status === 201 ? reply.body.data : null;
      if (view != null) {
        commit(kind, { job: view, t0: Date.now(), creating: false });
        // 重新创建时旧作业已终态、轮询已停：新作业要接着轮询（有组件挂着才起；初始创建由挂载时的 startPolling 负责）。
        if ((subscribers[kind] ?? 0) > 0) startPolling(kind);
      } else {
        commit(kind, { job: null, createError: reply.body as Envelope<unknown>, creating: false });
      }
      inflight[kind] = undefined;
      return snaps[kind].job;
    },
    () => {
      commit(kind, { job: null, createError: disconnectEnvelope(), creating: false });
      inflight[kind] = undefined;
      return null;
    },
  );
  inflight[kind] = p;
  return p;
}

// 没有作业也没有在途的创建时才创建；在途的创建本对象的大家共用、别的对象挡住（同类同时只一个）；
// 槽里是本对象的作业（排队、运行中或已结束）直接返回；槽里是别的对象的未终态作业时不建。
export function ensureJob(kind: JobKind, runtime?: string): Promise<JobView | null> {
  const s = snaps[kind];
  const want = runtime ?? null;
  if (s.creating && inflight[kind] != null) {
    return s.runtime === want ? (inflight[kind] as Promise<JobView | null>) : Promise.resolve(null);
  }
  if (s.job != null && s.runtime === want) return Promise.resolve(s.job);
  if (s.job != null && !isTerminal(s.job.state)) return Promise.resolve(null);
  return doCreate(kind, runtime);
}

// 只在作业已到终态或创建失败时可用：丢掉旧作业，重新创建一个（新的 t0）。
// 带 runtime 时要求槽里作业的 runtime 相同（或槽空、创建失败）才新建，否则不新建。
export function restartJob(kind: JobKind, runtime?: string): Promise<JobView | null> {
  const s = snaps[kind];
  const want = runtime ?? null;
  const terminal = s.job != null && isTerminal(s.job.state);
  if (!terminal && s.createError == null) return Promise.resolve(s.job);
  if (terminal && s.runtime !== want) return Promise.resolve(s.job);
  return doCreate(kind, runtime);
}

// 取消：只发一次 cancel；作业已经结束（409）不当成失败，终态由下一次查询给出。
export function cancelJob(kind: JobKind): Promise<void> {
  const id = snaps[kind].job?.id;
  if (id == null) return Promise.resolve();
  return apiCancelJob(id).then(
    () => undefined,
    () => undefined,
  );
}

function doQuery(kind: JobKind): Promise<void> {
  const id = snaps[kind].job?.id;
  if (id == null) return Promise.resolve();
  return getJob(id).then(
    (reply) => {
      const cur = snaps[kind];
      if (cur.job == null || cur.job.id !== id) return;
      if (reply.status === 404) {
        // 服务重启过、作业已不在表里：错误信封原样并进 job.envelope，状态落 failed（同一个 JobView）。
        commit(kind, { job: { ...cur.job, state: 'failed', envelope: reply.body as Envelope<unknown> } });
      } else if (reply.status === 200 && reply.body.data != null) {
        commit(kind, { job: reply.body.data });
      } else {
        // 其他状态码或正文不是合法作业：暂时的，保留原状态（重渲染让已用秒数走格）。
        commit(kind, {});
      }
    },
    () => {
      // 断线 / reject：暂时的，保留原状态，下一秒再查。
      commit(kind, {});
    },
  );
}

function scheduleNext(kind: JobKind): void {
  const s = snaps[kind];
  if ((subscribers[kind] ?? 0) <= 0) return;
  if (s.job != null && isTerminal(s.job.state)) return;
  // 没有作业时不排计时器：整页常驻着也不该每秒空转（对话框关着时靠行内入口的订阅照查到底）。
  if (s.job == null) return;
  timers[kind] = setTimeout(() => {
    timers[kind] = undefined;
    void queryOnce(kind);
  }, 1000);
}

function queryOnce(kind: JobKind): Promise<void> {
  return doQuery(kind).then(() => scheduleNext(kind));
}

// 只在有组件挂着时轮询；先查一次，再每 1000 毫秒查一次（setTimeout 链，不用 setInterval）。
function startPolling(kind: JobKind): void {
  if (timers[kind] != null) return;
  timers[kind] = setTimeout(() => {
    timers[kind] = undefined;
    void queryOnce(kind);
  }, 0);
}

function stopPolling(kind: JobKind): void {
  if (timers[kind] != null) {
    clearTimeout(timers[kind]);
    timers[kind] = undefined;
  }
}

// 订阅时把自己算成订阅者（卸载即递减）：对话框关着时行内入口还挂着，作业照查到底、别的行不会一直灰着。
function useSubscriber(kind: JobKind): void {
  useEffect(() => {
    subscribers[kind] = (subscribers[kind] ?? 0) + 1;
    startPolling(kind);
    return () => {
      subscribers[kind] = Math.max(0, (subscribers[kind] ?? 0) - 1);
      if ((subscribers[kind] ?? 0) <= 0) stopPolling(kind);
    };
  }, [kind]);
}

export function useJob(kind: JobKind, runtime?: string): {
  job: JobView | null;
  elapsedSeconds: number;
  createError: Envelope<unknown> | null;
  creating: boolean;
  restart: () => void;
  cancel: () => void;
} {
  const snap = useSyncExternalStore(subscribe, () => snaps[kind]);
  const t0 = snap.t0;
  const elapsedSeconds = t0 === null ? 0 : Math.floor((Date.now() - t0) / 1000);
  useSubscriber(kind);
  const restart = useCallback(() => {
    void restartJob(kind, runtime);
  }, [kind, runtime]);
  const cancel = useCallback(() => {
    void cancelJob(kind);
  }, [kind]);
  return { job: snap.job, elapsedSeconds, createError: snap.createError, creating: snap.creating, restart, cancel };
}

// 这一类作业正忙于哪个 runtime（没有未到终态的作业时是 null）：行内入口用它决定自己该可点还是让给别人。
export function useBusyRuntime(kind: JobKind): string | null {
  const snap = useSyncExternalStore(subscribe, () => snaps[kind]);
  useSubscriber(kind);
  return snap.job != null && !isTerminal(snap.job.state) ? snap.runtime : null;
}

// 只给包内测试用的复位导出（照 setLiveClientForTests 的既有做法）：清掉全部 kind 的状态并停掉轮询计时器。
export function resetJobStoreForTests(): void {
  for (const kind of KINDS) {
    stopPolling(kind);
    snaps[kind] = emptyState();
    subscribers[kind] = 0;
    inflight[kind] = undefined;
  }
  listeners.clear();
}
