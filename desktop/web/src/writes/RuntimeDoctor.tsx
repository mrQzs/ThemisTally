// 「就绪检查」一节的入口与结果（T056 的 doctor，T057 的「按版本记录核验」）：点 [运行就绪检查] 起一个 doctor 长作业，本节里用作业进度卡显示进度，
// 结束后逐个角色显示就绪卡（无头角色一张卡、其余角色一行）。有角色没就绪时作业落 failed 但带着 data，照样显示
// 结果块（不出现笼统的「就绪检查失败」）；没有 data 的失败才交回作业卡显示内核报错原文。同类作业同时只一个，
// 不用 useBusyRuntime；角色中文名与命令来源各照抄一张小表（不跨层引 src/pages）；逐字文案都放在本文件。
// 「按版本记录核验」是同一行里的另一组：一个文本框（值形如 <task-id>.v<N>）加一个 [核验]，起的是 doctor-record
// 作业（另一类作业，与 doctor 各管各的禁用、可以同时跑）；它的结果块写「版本记录 <那一行的 record>」，复用同一张
// 就绪卡、不加汇总行。
import { useState, type ReactNode } from 'react';
import { Button, TextField } from '../components';
import { PlayIcon } from '../icons';
import { JobCard } from '../jobs/JobCard';
import { cancelJob, ensureJob, restartJob, useJob } from '../jobs/jobStore';
import type { JobView } from '../api';
// 样式表接线：放在组件 import 之后（照仓库里组件带自己的样式表的写法）。
import './runtime-doctor.css';

// 角色中文名（照 roles-logic.ts 的 ROLE_NAMES 抄一张小表，不跨层引 src/pages）；未知角色码原样显示。
const ROLE_NAMES: Record<string, string> = {
  planning_review: '规划审核端',
  contract: '合同端',
  execution: '执行端',
  scheduler_agent: '调度代理',
};

// 命令来源的四个标签（与运行时表一致；照 RuntimeProbe.tsx 抄一张小表）。
const SOURCE_LABELS: Record<string, string> = {
  env: '环境变量',
  local: '本机文件',
  path: 'PATH',
  missing: '找不到',
};

// doctor 作业进度卡的失败标题与进度条 aria-label：这两个逐字文案由 JobCard 按 kind 查表给出（见 ../jobs/JobCard
// 的三张表），这里留一份与它对齐（静态核对会查它们是否在本文件里）。
const DOCTOR_CARD_LABELS = { failedTitle: '就绪检查失败', progressLabel: '就绪检查进行中' };

// doctor-record 作业进度卡的失败标题与进度条 aria-label：照 DOCTOR_CARD_LABELS 留一份与 JobCard 的表对齐。
const RECORD_CARD_LABELS = { failedTitle: '核验失败', progressLabel: '核验进行中' };

// 记录值的形状：照 ts/packages/ui/src/jobroutes.ts 的 PLAN_KEY_RE 抄同一份（服务与内核都按它校验，不合格回 400）。
const PLAN_KEY_RE = /^[a-z0-9][a-z0-9-]{0,63}\.v[1-9][0-9]{0,3}$/u;

// 记录值不合格时的提示（就地提示，不发请求）。
const RECORD_HINT = '写成 <task-id>.v<N>，例如 logs-cat.v2';

// 一个角色的就绪行：无头角色带下面这些键（内核找到命令时才有 command/source/version，是 pi 且有 provider/model
// 时才有 model_listed/auth_ready/thinking_supported）；不是无头的角色只有 role/mode/problems/text/ready。
interface DoctorRow {
  role: string;
  mode: string | null;
  ready: boolean;
  text: string | null;
  profile?: string;
  command?: string[];
  source?: string;
  version?: string;
  model_listed?: boolean;
  auth_ready?: boolean;
  thinking?: string;
  thinking_supported?: boolean;
  allowed?: boolean | null;
  credentials?: Record<string, boolean>;
  connected?: boolean;
  problems?: string[];
  notes?: string[];
  // 按版本记录核验时内核给的那一行多带一个 record 键（那一行当初记下的版本记录文件）。
  record?: string;
}

interface DoctorData {
  ready: boolean;
  roles: DoctorRow[];
}

function str(v: unknown): string | undefined {
  return typeof v === 'string' ? v : undefined;
}

function bool(v: unknown): boolean | undefined {
  return typeof v === 'boolean' ? v : undefined;
}

function strArray(v: unknown): string[] | undefined {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : undefined;
}

// 「有 data」的判定：envelope.data 是对象、roles 是数组（内核报错时没有 data）。
function doctorData(job: JobView | null): DoctorData | null {
  const data = job?.envelope?.data;
  if (typeof data !== 'object' || data === null) return null;
  const root = data as Record<string, unknown>;
  if (!Array.isArray(root.roles)) return null;
  const roles: DoctorRow[] = [];
  for (const item of root.roles) {
    if (typeof item !== 'object' || item === null) continue;
    const r = item as Record<string, unknown>;
    const credRaw = r.credentials;
    const credentials: Record<string, boolean> | undefined =
      typeof credRaw === 'object' && credRaw !== null
        ? Object.fromEntries(Object.entries(credRaw as Record<string, unknown>).map(([k, v]) => [k, v === true]))
        : undefined;
    roles.push({
      role: str(r.role) ?? '',
      mode: str(r.mode) ?? null,
      ready: r.ready === true,
      text: str(r.text) ?? null,
      profile: str(r.profile),
      command: strArray(r.command),
      source: str(r.source),
      version: str(r.version),
      model_listed: bool(r.model_listed),
      auth_ready: bool(r.auth_ready),
      thinking: str(r.thinking),
      thinking_supported: bool(r.thinking_supported),
      allowed: typeof r.allowed === 'boolean' ? r.allowed : r.allowed === null ? null : undefined,
      credentials,
      connected: bool(r.connected),
      problems: strArray(r.problems),
      notes: strArray(r.notes),
      record: str(r.record),
    });
  }
  return { ready: root.ready === true, roles };
}

// 三值格：真「是」、假「否」、缺键「—」。
function triText(v: boolean | undefined): string {
  if (v === true) return '是';
  if (v === false) return '否';
  return '—';
}

// 允许列表：真「是」、假「否」、null（没设允许列表）「不限制」。
function allowedText(v: boolean | null | undefined): string {
  if (v === true) return '是';
  if (v === false) return '否';
  return '不限制';
}

// 命令：数组空格连、后接来源；命令缺键写「—」。
function commandText(row: DoctorRow): string {
  if (row.command == null) return '—';
  const joined = row.command.join(' ');
  if (row.source == null) return joined;
  return `${joined}（来源：${SOURCE_LABELS[row.source] ?? row.source}）`;
}

// 思考级别：<thinking> 加本机 pi 是否接受这个档位；thinking 或 thinking_supported 缺键写「—」
//（不是 pi 或缺 provider/model 时内核不给 thinking_supported，这时整格写「—」）。
function thinkingText(row: DoctorRow): string {
  if (row.thinking == null || row.thinking_supported == null) return '—';
  return row.thinking_supported
    ? `${row.thinking}（本机 pi 接受这个档位）`
    : `${row.thinking}（本机 pi 不接受这个档位）`;
}

// 凭据：每个变量名后写可用/不可用，用「、」连；一个变量都没有写「无」。
function credentialsText(creds: Record<string, boolean> | undefined): string {
  const keys = creds == null ? [] : Object.keys(creds);
  if (keys.length === 0) return '无';
  return keys.map((k) => `${k} ${creds?.[k] === true ? '可用' : '不可用'}`).join('、');
}

function roleLabel(code: string): string {
  return ROLE_NAMES[code] ?? code;
}

// 无头角色的一张就绪卡：卡头（✓/✗ 与角色名与 profile）、八个键值行、问题列表、说明行。
function HeadlessCard({ row }: { row: DoctorRow }): ReactNode {
  const problems = row.problems ?? [];
  const notes = row.notes ?? [];
  return (
    <div className="rd-card">
      <p className="rd-card__head">
        <span className={row.ready ? 'rd-mark rd-mark--ok' : 'rd-mark rd-mark--bad'}>{row.ready ? '✓ 就绪' : '✗ 未就绪'}</span>
        {` · ${roleLabel(row.role)} · profile ${row.profile ?? '—'}`}
      </p>
      <dl className="rd-card__rows">
        <div className="rd-card__row"><dt>命令</dt><dd className="rd-mono">{commandText(row)}</dd></div>
        <div className="rd-card__row"><dt>版本</dt><dd>{row.version ?? '—'}</dd></div>
        <div className="rd-card__row"><dt>模型在列表中</dt><dd>{triText(row.model_listed)}</dd></div>
        <div className="rd-card__row"><dt>登录</dt><dd>{triText(row.auth_ready)}</dd></div>
        <div className="rd-card__row"><dt>思考级别</dt><dd>{thinkingText(row)}</dd></div>
        <div className="rd-card__row"><dt>允许列表</dt><dd>{allowedText(row.allowed)}</dd></div>
        <div className="rd-card__row"><dt>凭据</dt><dd>{credentialsText(row.credentials)}</dd></div>
        <div className="rd-card__row"><dt>接通状态</dt><dd>{row.connected === true ? '已接通' : '未接通'}</dd></div>
      </dl>
      {problems.length > 0 && (
        <ul className="rd-card__problems">
          {problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}
      {notes.length > 0 && (
        <ul className="rd-card__notes">
          {notes.map((n) => <li key={n}>{n}</li>)}
        </ul>
      )}
    </div>
  );
}

// 不是无头的角色：一行，✓/✗ 依 ready，后接角色中文名与内核那一行 text（没有 text 就只写到角色名）。
function SimpleRow({ row }: { row: DoctorRow }): ReactNode {
  const label = roleLabel(row.role);
  return (
    <p className="rd-simple">
      <span className={row.ready ? 'rd-mark rd-mark--ok' : 'rd-mark rd-mark--bad'}>{row.ready ? '✓' : '✗'}</span>
      {row.text != null ? ` ${label} · ${row.text}` : ` ${label}`}
    </p>
  );
}

// 结果块：第一行汇总（全部就绪 / 有未就绪的角色（N 个）），再逐个角色（无头一张卡、其余一行）。
function DoctorResult({ data }: { data: DoctorData }): ReactNode {
  const notReady = data.roles.filter((r) => !r.ready).length;
  return (
    <div className="rd-result">
      <p className="rd-summary">{data.ready ? '全部就绪' : `有未就绪的角色（${notReady} 个）`}</p>
      {data.roles.map((row) =>
        row.mode === 'headless' || row.profile != null
          ? <HeadlessCard key={row.role} row={row} />
          : <SimpleRow key={row.role} row={row} />,
      )}
    </div>
  );
}

// 版本记录核验的结果块：第一行标题「版本记录 <那一行的 record>」（缺键写「—」），下面每行一张就绪卡。
// 记录核验内核只给那一行，不加汇总行（全部就绪 / 有未就绪的角色那两句只属于 doctor）。
function RecordResult({ data }: { data: DoctorData }): ReactNode {
  const first = data.roles[0];
  return (
    <div className="rd-result">
      <p className="rd-summary">{`版本记录 ${first?.record ?? '—'}`}</p>
      {data.roles.map((row) =>
        row.mode === 'headless' || row.profile != null
          ? <HeadlessCard key={row.role} row={row} />
          : <SimpleRow key={row.role} row={row} />,
      )}
    </div>
  );
}

// 「就绪检查」一节：入口一行（[运行就绪检查] 与核验组）+ doctor 的结果区 + 版本记录核验的结果区。按钮文字始终
// 「运行就绪检查」，运行中只禁用不换字；没跑过时是虚线空框；运行中另起一行说明离开页面作业也会继续；有 data 的
// failed 走自己的结果块，没有 data 的失败与取消与超时交回作业卡。[核验] 的禁用只看 doctor-record 这一类作业。
export function RuntimeDoctor() {
  const { job, elapsedSeconds, createError, creating } = useJob('doctor');
  const { job: recordJob, elapsedSeconds: recordElapsed, createError: recordCreateError, creating: recordCreating } = useJob('doctor-record');
  const [record, setRecord] = useState('');
  const [recordError, setRecordError] = useState<string | undefined>(undefined);
  const data = doctorData(job);
  const recordData = doctorData(recordJob);
  const running = creating || (job != null && (job.state === 'queued' || job.state === 'running'));
  // [核验] 的禁用只看 doctor-record 这一类作业：在创建、排队或运行；空闲时一直可点（值不合格靠点了之后的提示）。
  const recordRunning = recordCreating || (recordJob != null && (recordJob.state === 'queued' || recordJob.state === 'running'));
  const neverRan = job == null && createError == null && !creating;
  const succeeded = job != null && job.state === 'succeeded';
  const failedWithData = job != null && job.state === 'failed' && data != null;
  const recordSucceeded = recordJob != null && recordJob.state === 'succeeded';
  const recordFailedWithData = recordJob != null && recordJob.state === 'failed' && recordData != null;
  const onRun = () => {
    // 已终态或创建失败 → 重新检查（新作业）；否则起第一个作业。
    if ((job != null && (job.state === 'succeeded' || job.state === 'failed' || job.state === 'cancelled' || job.state === 'timed_out')) || createError != null) {
      void restartJob('doctor');
    } else {
      void ensureJob('doctor');
    }
  };
  const onChangeRecord = (value: string) => {
    setRecord(value);
    // 改了文本框就清掉上一次的提示（点了一个合格的值时也清，见 onVerify）。
    if (recordError != null) setRecordError(undefined);
  };
  const onVerify = () => {
    // 值不合格（空文本、大写、没有 .v、v0、含空格、超长）就不发请求，只在文本框上提示。
    if (!PLAN_KEY_RE.test(record)) {
      setRecordError(RECORD_HINT);
      return;
    }
    setRecordError(undefined);
    // 起作业：restartJob 管终态且同值（新建，新的 t0 与作业号），ensureJob 管终态且换值与空槽（也是新建）；
    // 两者合起来覆盖终态同值、终态换值、空槽三种要新建的情形，在途的创建由 jobStore 共用，不会建出两个。
    void restartJob('doctor-record', record);
    void ensureJob('doctor-record', record);
  };

  return (
    <>
      <div className="rd-entries">
        <Button variant="secondary" size="md" disabled={running} onClick={onRun}>
          <PlayIcon width={16} height={16} />
          运行就绪检查
        </Button>
        <div className="rd-record">
          <TextField label="按版本记录核验" mono value={record} error={recordError} onChange={(e) => { onChangeRecord(e.target.value); }} />
          <Button variant="secondary" size="md" disabled={recordRunning} onClick={onVerify}>核验</Button>
        </div>
      </div>
      <div className="rd-body">
        {neverRan && (
          <p className="rt-ready">还没有运行过就绪检查。就绪检查会逐个核对无头角色的命令、模型、登录、思考级别与凭据。</p>
        )}
        {running && (
          <>
            <JobCard key={job?.id ?? 'creating'} kind="doctor" title="就绪检查" job={job} elapsedSeconds={elapsedSeconds} createError={createError} onCancel={() => { void cancelJob('doctor'); }} />
            <p className="rd-note">离开这个页面作业也会继续，回来时显示结果。</p>
          </>
        )}
        {!running && failedWithData && data != null && <DoctorResult data={data} />}
        {!running && !failedWithData && (createError != null || job != null) && (
          <JobCard key={job?.id ?? 'creating'} kind="doctor" title="就绪检查" job={job} elapsedSeconds={elapsedSeconds} createError={createError} onCancel={() => { void cancelJob('doctor'); }}>
            {succeeded && data != null ? <DoctorResult data={data} /> : null}
          </JobCard>
        )}
      </div>
      <div className="rd-record-body">
        {recordRunning && (
          <JobCard key={recordJob?.id ?? 'creating'} kind="doctor-record" title="版本记录核验" job={recordJob} elapsedSeconds={recordElapsed} createError={recordCreateError} onCancel={() => { void cancelJob('doctor-record'); }} />
        )}
        {!recordRunning && recordFailedWithData && recordData != null && <RecordResult data={recordData} />}
        {!recordRunning && !recordFailedWithData && (recordCreateError != null || recordJob != null) && (
          <JobCard key={recordJob?.id ?? 'creating'} kind="doctor-record" title="版本记录核验" job={recordJob} elapsedSeconds={recordElapsed} createError={recordCreateError} onCancel={() => { void cancelJob('doctor-record'); }}>
            {recordSucceeded && recordData != null ? <RecordResult data={recordData} /> : null}
          </JobCard>
        )}
      </div>
    </>
  );
}
