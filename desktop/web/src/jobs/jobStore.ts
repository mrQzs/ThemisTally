// 作业状态模块（T054）：runtime-scan 作业的状态放在页面之外的模块里，按 kind 分开存。
// 关掉对话框再打开接着看同一个作业；在途的创建大家共用；每秒轮询（setTimeout 链、卸载即停、重开先查一次）；
// 已用秒数从创建回应到达时算起；查询 404 按失败处理（错误信封并进 job.envelope、状态落 failed），其他失败当暂时的。
import { useCallback, useEffect, useSyncExternalStore } from 'react';
import { cancelJob as apiCancelJob, getJob, startJob, type Envelope, type JobKind, type JobState, type JobView } from '../api';

interface StoreState {
  job: JobView | null;
  // 创建回应到达时的本地时间戳（毫秒）；没有作业时是 null。
  t0: number | null;
  createError: Envelope<unknown> | null;
  creating: boolean;
  // 每次提交都 +1：让 useSyncExternalStore 的快照换引用（已用秒数每秒也走一格）。
  tick: number;
}

const KINDS: readonly JobKind[] = ['runtime-scan'];

const snaps: Record<JobKind, StoreState> = {
  'runtime-scan': { job: null, t0: null, createError: null, creating: false, tick: 0 },
};

const listeners = new Set<() => void>();
const subscribers: Record<JobKind, number> = { 'runtime-scan': 0 };
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
function doCreate(kind: JobKind): Promise<JobView | null> {
  commit(kind, { creating: true, createError: null, job: null });
  const p = startJob(kind).then(
    (reply) => {
      const view = reply.status === 201 ? reply.body.data : null;
      if (view != null) {
        commit(kind, { job: view, t0: Date.now(), creating: false });
        // 重新扫描时旧作业已终态、轮询已停：新作业要接着轮询（有组件挂着才起；初始创建由挂载时的 startPolling 负责）。
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

// 没有作业也没有在途的创建时才创建；在途的创建大家共用；已有作业（排队、运行中或已结束）直接返回，不另开一个。
export function ensureJob(kind: JobKind): Promise<JobView | null> {
  const s = snaps[kind];
  if (s.job != null) return Promise.resolve(s.job);
  if (s.creating && inflight[kind] != null) return inflight[kind] as Promise<JobView | null>;
  return doCreate(kind);
}

// 只在作业已到终态或创建失败时可用：丢掉旧作业，重新创建一个（新的 t0）。
export function restartJob(kind: JobKind): Promise<JobView | null> {
  const s = snaps[kind];
  const terminal = s.job != null && isTerminal(s.job.state);
  if (!terminal && s.createError == null) return Promise.resolve(s.job);
  return doCreate(kind);
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

export function useJob(kind: JobKind): {
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
  useEffect(() => {
    subscribers[kind] = (subscribers[kind] ?? 0) + 1;
    startPolling(kind);
    return () => {
      subscribers[kind] = Math.max(0, (subscribers[kind] ?? 0) - 1);
      if ((subscribers[kind] ?? 0) <= 0) stopPolling(kind);
    };
  }, [kind]);
  const restart = useCallback(() => {
    void restartJob(kind);
  }, [kind]);
  const cancel = useCallback(() => {
    void cancelJob(kind);
  }, [kind]);
  return { job: snap.job, elapsedSeconds, createError: snap.createError, creating: snap.creating, restart, cancel };
}

// 只给包内测试用的复位导出（照 setLiveClientForTests 的既有做法）：清掉全部 kind 的状态并停掉轮询计时器。
export function resetJobStoreForTests(): void {
  for (const kind of KINDS) {
    stopPolling(kind);
    snaps[kind] = { job: null, t0: null, createError: null, creating: false, tick: 0 };
    subscribers[kind] = 0;
    inflight[kind] = undefined;
  }
  listeners.clear();
}
