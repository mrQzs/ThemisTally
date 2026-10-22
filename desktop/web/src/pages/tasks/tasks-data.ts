// 任务页数据层（合同第 5 节）：readAttempt、readAttemptFile 与 loadAttemptDetail。
// 先调 api.ts；信封 ok、或当前开关是 error 时原样返回；否则在本片夹具里找，找到了用 api.ts 信封里的
// command 包成 ok 信封并做深拷贝，找不到返回 api.ts 的原信封。loading 开关下 api.ts 永不兑现，包装也一直等着。
import {
  getAttempt,
  getStatus,
  readFile,
  type AttemptData,
  type Envelope,
  type FileData,
  type StatusData,
  type StatusRow,
} from '../../api';
import { currentMock } from '../../mock/scenario';
import { attemptFixtureData, findAttemptFixture } from '../../mock/tasks-attempts';
import { fileFixtureData, findFileFixture } from '../../mock/tasks-files';
import { attemptSeg } from './tasks-model';

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function okEnvelope<T>(command: string[], data: T): Envelope<T> {
  return { ok: true, exit_code: 0, data, output: [], messages: [], command, elapsed_ms: 0 };
}

/** 一个 attempt 的详情：task、attempt、status 里的行与 logs show 的信封。 */
export interface AttemptDetailData {
  task: string;
  attempt: string;
  row: StatusRow | null;
  attemptEnv: Envelope<AttemptData>;
}

/** logs show <task>/<attempt>：api.ts 有的原样返回，报缺时才取本片夹具。 */
export function readAttempt(task: string, attempt: string): Promise<Envelope<AttemptData>> {
  return getAttempt(task, attempt).then((env) => {
    if (env.ok || currentMock() === 'error') return env;
    const entry = findAttemptFixture(task, attempt);
    if (entry == null) return env;
    return okEnvelope(env.command, clone(attemptFixtureData(entry)));
  });
}

/** logs cat <task>/<attempt> <path> [cursor]：同上，键里再加路径与游标。 */
export function readAttemptFile(
  task: string,
  attempt: string,
  path: string,
  cursor?: string,
): Promise<Envelope<FileData>> {
  return readFile(task, attempt, path, cursor).then((env) => {
    if (env.ok || currentMock() === 'error') return env;
    const entry = findFileFixture(task, attempt, path, cursor);
    if (entry == null) return env;
    return okEnvelope(env.command, clone(fileFixtureData(entry)));
  });
}

/** 详情页取数：并行读 getStatus 与 readAttempt；getStatus 失败返回它的信封。 */
export function loadAttemptDetail(task: string, attempt: string): Promise<Envelope<AttemptDetailData>> {
  return Promise.all([getStatus(), readAttempt(task, attempt)]).then(([status, attemptEnv]) => {
    if (!status.ok || status.data == null) return status as unknown as Envelope<AttemptDetailData>;
    const row = status.data.find((r) => r.task_id === task && attemptSeg(r.attempt) === attempt) ?? null;
    return okEnvelope(status.command, { task, attempt, row, attemptEnv });
  });
}

/** 找不到：status 里没有这一行，logs show 也没读到。 */
export function isAttemptMissing(data: AttemptDetailData): boolean {
  return data.row == null && !data.attemptEnv.ok;
}
