// 外壳窗口外框（src/shellpages/ShellWindow.tsx）：一条最简标题栏（Logo 18×20 与产品名，右侧留 140 给系统按钮，5.2 :352）
// + 居中卡片的主区。没有仓库菜单、连接胶囊、主题菜单与 Tab 栏，也不装快捷键。按 route.page 渲染首启或服务状态视图。
import { Logo } from '../shell/Logo';
import { useThemisShell } from './shellContext';
import { scenarioOf, useShellWindowRoute, type ShellWindowRoute } from './shellWindowRoute';
import { FirstRunView } from './FirstRunView';
import { ServiceStatusView } from './ServiceStatusView';
import './shell-window.css';

export { useShellWindowRoute } from './shellWindowRoute';

export interface ShellWindowProps {
  route: ShellWindowRoute;
  navigate: (path: string) => void;
}

export function ShellWindow({ route, navigate }: ShellWindowProps) {
  const shell = useThemisShell(scenarioOf(route.page, route.query));
  return (
    <div className="tt-app tt-shellwin" data-shell-window={route.page}>
      <div className="tt-shell-bar">
        <Logo />
        <span className="tt-shell-product">Themis Tally</span>
      </div>
      <main className="tt-shell-main">
        <div className="tt-shell-card">
          {route.page === 'first-run' ? (
            <FirstRunView shell={shell} navigate={navigate} />
          ) : (
            <ServiceStatusView shell={shell} navigate={navigate} />
          )}
        </div>
      </main>
    </div>
  );
}
