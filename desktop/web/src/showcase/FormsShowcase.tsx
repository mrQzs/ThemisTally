// 第 4 片（T005）陈列页演示：11 节，data-demo 依次为 text-field、form-dialog、segmented、switch-checkbox、tabs、
// table、key-value、empty-state、skeleton、connection、breadcrumb，渲染在轻提示一节之后。复用 App.css 的 showcase__* 类。
import { useEffect, useRef, useState } from 'react';
import {
  Button,
  Dialog,
  TextField,
  Select,
  SegmentedControl,
  Switch,
  Checkbox,
  Tabs,
  Table,
  KeyValueList,
  EmptyState,
  Skeleton,
  ConnectionPill,
  Breadcrumb,
  type TableColumn,
} from '../components';
import './showcase-forms.css';

const ENV_OPTIONS = [
  { value: 'dev', label: '开发' },
  { value: 'prod', label: '生产' },
  { value: 'test', label: '测试' },
];

function TextFieldSection() {
  return (
    <section className="showcase__section" data-demo="text-field">
      <h2 className="showcase__h2">输入框与下拉</h2>
      <div className="showcase__row">
        <div className="showcase-field">
          <TextField label="用户名" placeholder="输入名称" />
        </div>
        <div className="showcase-field">
          <TextField label="用户名" help="三到十六个字符" />
        </div>
        <div className="showcase-field">
          <TextField label="用户名" error="名称已被占用" defaultValue="admin" />
        </div>
        <div className="showcase-field">
          <TextField label="用户名" defaultValue="locked" disabled />
        </div>
        <div className="showcase-field">
          <Select label="环境" options={ENV_OPTIONS} defaultValue="dev" />
        </div>
      </div>
      <p className="showcase__muted">高 32；出错时 aria-invalid 与危险色边框；帮助与出错文字经 aria-describedby 关联；下拉用原生 select。</p>
    </section>
  );
}

function FormDialogSection() {
  const [open, setOpen] = useState(false);
  return (
    <section className="showcase__section" data-demo="form-dialog">
      <h2 className="showcase__h2">表单对话框</h2>
      <div className="showcase__row">
        <Button variant="secondary" onClick={() => setOpen(true)}>打开表单对话框</Button>
      </div>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="新建任务"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>取消</Button>
            <Button variant="primary" onClick={() => setOpen(false)}>确定</Button>
          </>
        }
      >
        <div className="showcase__stack">
          <TextField label="任务名称" placeholder="输入名称" />
          <Select label="环境" options={ENV_OPTIONS} defaultValue="dev" />
        </div>
      </Dialog>
      <p className="showcase__muted">模态框里放输入框与下拉：点进输入框、拖选文字都不被遮罩拦截；遮罩本身的按下仍被阻止。</p>
    </section>
  );
}

function SegmentedSection() {
  const [value, setValue] = useState('list');
  return (
    <section className="showcase__section" data-demo="segmented">
      <h2 className="showcase__h2">分段选择</h2>
      <div className="showcase__row">
        <SegmentedControl
          aria-label="视图"
          value={value}
          onChange={setValue}
          options={[
            { value: 'list', label: '列表' },
            { value: 'grid', label: '网格' },
            { value: 'board', label: '看板' },
          ]}
        />
        <span className="showcase__label">当前：{value}</span>
      </div>
      <p className="showcase__muted">左右方向键选中上一段、下一段并移焦点，到头循环；只处理左右键。</p>
    </section>
  );
}

function SwitchCheckboxSection() {
  const [auto, setAuto] = useState(false);
  const [onlyFail, setOnlyFail] = useState(true);
  return (
    <section className="showcase__section" data-demo="switch-checkbox">
      <h2 className="showcase__h2">开关与复选框</h2>
      <div className="showcase__row">
        <Switch label="自动刷新" checked={auto} onChange={setAuto} />
        <Switch label="自动刷新（禁用）" checked disabled onChange={() => {}} />
        <Checkbox label="仅看失败" checked={onlyFail} onChange={setOnlyFail} />
        <Checkbox label="半选不可用" checked={false} disabled onChange={() => {}} />
      </div>
      <p className="showcase__muted">ARIA 自绘的 span；空格或点击切换；禁用时不可聚焦、不切换；复选框只认空格。</p>
    </section>
  );
}

function TabsSection() {
  const [tab, setTab] = useState('overview');
  return (
    <section className="showcase__section" data-demo="tabs">
      <h2 className="showcase__h2">页签</h2>
      <Tabs
        aria-label="任务视图"
        value={tab}
        onChange={setTab}
        items={[
          { id: 'overview', label: '概览' },
          { id: 'logs', label: '日志' },
          { id: 'settings', label: '设置' },
        ]}
      >
        <p className="showcase__muted">当前面板：{tab}</p>
      </Tabs>
      <p className="showcase__muted">左右方向键循环切换并移焦点，Home/End 到首尾；选中跟着焦点走。</p>
    </section>
  );
}

interface TaskRow {
  id: string;
  task: string;
  dur: string;
  tok: string;
  code: string;
}

const TASK_COLUMNS: TableColumn<TaskRow>[] = [
  { key: 'task', header: '任务' },
  { key: 'dur', header: '用时', numeric: true },
  { key: 'tok', header: 'token', numeric: true },
  { key: 'code', header: '编号', mono: true },
];

const TASK_ROWS: TaskRow[] = [
  { id: 'r1', task: '整理第七片合同', dur: '12.5', tok: '1200', code: 'a1b2c3d' },
  { id: 'r2', task: '桌面端表单与数据原子', dur: '8.0', tok: '640', code: 'e4f5a6b' },
  { id: 'r3', task: '应用框架与夹具数据层', dur: '31.2', tok: '5120', code: 'c7d8e9f' },
  { id: 'r4', task: '接本机服务与写操作', dur: '4.4', tok: '300', code: '0a1b2c3' },
  { id: 'r5', task: '七端视图与工具链升级', dur: '19.9', tok: '2048', code: 'd4e5f60' },
  { id: 'r6', task: '门禁回归与结项', dur: '6.6', tok: '880', code: '1b2c3d4' },
];

const HEIGHT_OPTIONS = [
  { value: '40', label: '40' },
  { value: '44', label: '44' },
  { value: '52', label: '52' },
];

function TableSection() {
  const [rowHeight, setRowHeight] = useState<40 | 44 | 52>(40);
  const [lastOpen, setLastOpen] = useState<string | null>(null);
  return (
    <section className="showcase__section" data-demo="table">
      <h2 className="showcase__h2">表格</h2>
      <div className="showcase__stack">
        <SegmentedControl
          aria-label="行高"
          value={String(rowHeight)}
          onChange={(v) => setRowHeight(Number(v) as 40 | 44 | 52)}
          options={HEIGHT_OPTIONS}
        />
        <Table
          aria-label="任务表"
          className="showcase-table"
          columns={TASK_COLUMNS}
          rows={TASK_ROWS}
          rowKey={(r) => r.id}
          rowHeight={rowHeight}
          onRowOpen={setLastOpen}
        />
        <span className="showcase__label">上次打开：{lastOpen ?? '（无）'}</span>
      </div>
      <p className="showcase__muted">上下键移动、Home/End 到首尾、Enter 或点击行打开；表头在限高容器里吸顶，窄了横向滚动。</p>
    </section>
  );
}

function KeyValueSection() {
  return (
    <section className="showcase__section" data-demo="key-value">
      <h2 className="showcase__h2">键值列表</h2>
      <KeyValueList
        items={[
          { label: '分支', value: 'main' },
          { label: '提交', value: 'a1b2c3d', mono: true },
          { label: '状态', value: '已通过' },
          { label: '用时', value: '12.5' },
        ]}
      />
      <p className="showcase__muted">dl 里每项一对 dt、dd；等宽值用 mono-sm。</p>
    </section>
  );
}

function EmptyStateSection() {
  return (
    <section className="showcase__section" data-demo="empty-state">
      <h2 className="showcase__h2">空状态</h2>
      <EmptyState
        title="还没有任务"
        description="创建第一个任务开始"
        action={<Button variant="secondary" size="sm">新建任务</Button>}
      />
      <EmptyState title="没有匹配的结果" description="换个筛选条件试试" />
    </section>
  );
}

function SkeletonSection() {
  const [loading, setLoading] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => () => {
    if (timerRef.current !== null) clearTimeout(timerRef.current);
  }, []);
  const load = (ms: number) => {
    if (timerRef.current !== null) clearTimeout(timerRef.current);
    setLoading(true);
    timerRef.current = setTimeout(() => setLoading(false), ms);
  };
  return (
    <section className="showcase__section" data-demo="skeleton">
      <h2 className="showcase__h2">骨架屏</h2>
      <div className="showcase__row">
        <Button variant="secondary" onClick={() => load(2000)}>加载 2 秒</Button>
        <Button variant="secondary" onClick={() => load(200)}>加载 0.2 秒</Button>
      </div>
      {loading && <Skeleton />}
      <p className="showcase__muted">挂载后 300ms 才出现骨架；短于 300ms 的加载不闪骨架。</p>
    </section>
  );
}

function ConnectionSection() {
  return (
    <section className="showcase__section" data-demo="connection">
      <h2 className="showcase__h2">连接胶囊</h2>
      <div className="showcase__row">
        <ConnectionPill state="connected" pid={4242} startedAt="2026-10-20 10:00" stream="事件流正常" />
        <ConnectionPill state="reconnecting" attempt={2} pid={4242} startedAt="2026-10-20 10:00" stream="正在重连" />
        <ConnectionPill state="disconnected" pid={4242} startedAt="2026-10-20 10:00" stream="已断开" />
      </div>
      <p className="showcase__muted">点胶囊开合详情浮层；Esc 关闭、焦点留胶囊；点外面也关闭。</p>
    </section>
  );
}

function BreadcrumbSection() {
  return (
    <section className="showcase__section" data-demo="breadcrumb">
      <h2 className="showcase__h2">面包屑</h2>
      <Breadcrumb
        items={[
          { label: '项目', href: '/projects' },
          { label: '任务', onClick: () => {} },
          { label: '详情' },
        ]}
      />
      <p className="showcase__muted">前项有 href 渲染链接、否则按钮；末项是 aria-current=page 的当前页。</p>
    </section>
  );
}

export default function FormsShowcase() {
  return (
    <>
      <TextFieldSection />
      <FormDialogSection />
      <SegmentedSection />
      <SwitchCheckboxSection />
      <TabsSection />
      <TableSection />
      <KeyValueSection />
      <EmptyStateSection />
      <SkeletonSection />
      <ConnectionSection />
      <BreadcrumbSection />
    </>
  );
}
