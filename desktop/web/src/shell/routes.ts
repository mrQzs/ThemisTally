// 路由表（合同第 1 条）：有序的 9 个 Tab，每项有 id、标题、路径、图标、快捷键与页面组件。
// #/showcase 组件陈列不是 Tab，由 App 单独处理。快捷键 Ctrl+1…8 切前 8 个 Tab，Ctrl+, 切设置。
import type { ComponentType, SVGProps } from 'react';
import { ListChecksIcon } from '../icons';
import {
  OverviewIcon,
  RolesIcon,
  RuntimesIcon,
  SecretsIcon,
  LogsIcon,
  PluginsIcon,
  HistoryIcon,
  SettingsIcon,
} from '../icons/frame';
import OverviewPage from '../pages/OverviewPage';
import TasksPage from '../pages/TasksPage';
import RolesPage from '../pages/RolesPage';
import RuntimesPage from '../pages/RuntimesPage';
import SecretsPage from '../pages/SecretsPage';
import LogsPage from '../pages/LogsPage';
import PluginsPage from '../pages/PluginsPage';
import HistoryPage from '../pages/HistoryPage';
import SettingsPage from '../pages/SettingsPage';

export type TabIcon = ComponentType<SVGProps<SVGSVGElement>>;

export interface TabDef {
  id: string;
  title: string;
  /**  hash 路径，如 /overview。 */
  path: string;
  Icon: TabIcon;
  /** 快捷键（Ctrl 组合下的 event.key）。 */
  shortcut: string;
  Page: ComponentType;
}

export const TABS: readonly TabDef[] = [
  { id: 'overview', title: '总览', path: '/overview', Icon: OverviewIcon, shortcut: '1', Page: OverviewPage },
  { id: 'tasks', title: '任务', path: '/tasks', Icon: ListChecksIcon, shortcut: '2', Page: TasksPage },
  { id: 'roles', title: '角色与模型', path: '/roles', Icon: RolesIcon, shortcut: '3', Page: RolesPage },
  { id: 'runtimes', title: 'CLI 运行时', path: '/runtimes', Icon: RuntimesIcon, shortcut: '4', Page: RuntimesPage },
  { id: 'secrets', title: '凭据', path: '/secrets', Icon: SecretsIcon, shortcut: '5', Page: SecretsPage },
  { id: 'logs', title: '日志与用量', path: '/logs', Icon: LogsIcon, shortcut: '6', Page: LogsPage },
  { id: 'plugins', title: '插件', path: '/plugins', Icon: PluginsIcon, shortcut: '7', Page: PluginsPage },
  { id: 'history', title: '历史与审计', path: '/history', Icon: HistoryIcon, shortcut: '8', Page: HistoryPage },
  { id: 'settings', title: '设置', path: '/settings', Icon: SettingsIcon, shortcut: ',', Page: SettingsPage },
];
