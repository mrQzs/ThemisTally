// 标题栏（合同第 2 条，照 Main 画布 :19–37 与 UI 文档 5.2）：高 40、titlebar 底、下边框 1px border；
// 左内边距 space-3、元素间距 space-2、右内边距 140（留给 Electron 原生窗口控件，本片不渲染拖动区与窗口钮）。
// 不设 overflow:hidden、不建低于内容区的层叠上下文，胶囊浮层与两个菜单要盖在内容之上。
import { Button, IconButton, ConnectionPill } from '../components';
import { ChevronDownIcon } from '../icons';
import { FolderOpenIcon, FolderPlusIcon, MoonIcon, SunIcon, MonitorIcon } from '../icons/frame';
import { Logo } from './Logo';
import { ShellMenu, type ShellMenuItem } from './ShellMenu';
import { currentMock } from '../mock/scenario';
import { SHELL_PID, SHELL_STARTED_AT, SHELL_RECENT_REPOS, shellConnectionState, shellStreamText } from '../mock/shell';
import type { ThemePref } from './theme';
import './TitleBar.css';

export interface TitleBarProps {
  theme: ThemePref;
  onThemeChange: (pref: ThemePref) => void;
  repoName: string;
}

export function TitleBar({ theme, onThemeChange, repoName }: TitleBarProps) {
  const connState = shellConnectionState(currentMock());

  const repoItems: ShellMenuItem[] = [
    { kind: 'group', label: '最近的仓库' },
    ...SHELL_RECENT_REPOS.map((name) => ({
      kind: 'radio' as const,
      id: name,
      label: <span className="tt-titlebar__repo">{name}</span>,
      checked: name === repoName,
    })),
    { kind: 'separator' },
    {
      kind: 'item',
      id: 'add-repo',
      label: '添加仓库…',
      icon: <FolderPlusIcon width={14} height={14} />,
      trailing: '第二阶段接入',
      disabled: true,
    },
  ];

  const themeItems: ShellMenuItem[] = [
    { kind: 'radio', id: 'system', label: '跟随系统', checked: theme === 'system' },
    { kind: 'radio', id: 'light', label: '亮', checked: theme === 'light' },
    { kind: 'radio', id: 'dark', label: '暗', checked: theme === 'dark' },
  ];

  const themeLabel = theme === 'dark' ? '暗' : theme === 'light' ? '亮' : '跟随系统';
  const themeIcon =
    theme === 'dark' ? (
      <MoonIcon width={16} height={16} />
    ) : theme === 'light' ? (
      <SunIcon width={16} height={16} />
    ) : (
      <MonitorIcon width={16} height={16} />
    );

  return (
    <header className="tt-titlebar">
      <Logo />
      <span className="tt-titlebar__product">Themis Tally</span>
      <span className="tt-titlebar__divider" aria-hidden="true" />
      <ShellMenu label="仓库" items={repoItems} onSelect={() => {}}>
        {(trigger) => (
          <Button variant="ghost" size="sm" title="切换仓库" {...trigger}>
            <FolderOpenIcon width={16} height={16} />
            <span className="tt-titlebar__repo">{repoName}</span>
            <ChevronDownIcon width={14} height={14} className="tt-titlebar__chev" />
          </Button>
        )}
      </ShellMenu>
      <div className="tt-titlebar__spacer" />
      <ConnectionPill
        state={connState}
        pid={SHELL_PID}
        startedAt={SHELL_STARTED_AT}
        stream={shellStreamText(connState)}
      />
      <ShellMenu label="主题" align="right" items={themeItems} onSelect={(id) => onThemeChange(id as ThemePref)}>
        {(trigger) => (
          <IconButton size="sm" label={`主题：${themeLabel}`} icon={themeIcon} {...trigger} />
        )}
      </ShellMenu>
    </header>
  );
}
