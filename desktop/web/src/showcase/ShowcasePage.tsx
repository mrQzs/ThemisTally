// 组件陈列页（合同第 11 条）：用 import.meta.glob 急切导入同目录的 ./*Showcase.tsx（不含子目录），
// 取各模块默认导出渲染，没有默认导出组件的模块跳过；自己的文件名不以 Showcase.tsx 结尾，收不到自己
// （Vite 本来也排除导入者自己）。排序按文件名 ASCII 编码顺序（JS 默认 sort，大写在前）。
// 每个模块包在 div[data-showcase=文件名去掉 .tsx] 里，用 display:contents 不改变节间距。
// 根元素是 div.showcase，页头 h1「组件陈列」加一行说明；不放主题按钮，不用 PageFrame。
import { useMemo, type ComponentType } from 'react';
import './showcase.css';

interface ShowcaseModule {
  default?: ComponentType;
}

export default function ShowcasePage() {
  const sections = useMemo(() => {
    const modules = import.meta.glob<ShowcaseModule>('./*Showcase.tsx', { eager: true });
    return Object.keys(modules)
      .sort()
      .map((path) => ({ path, Component: modules[path].default }))
      .filter((s): s is { path: string; Component: ComponentType } => typeof s.Component !== 'undefined');
  }, []);

  return (
    <div className="showcase">
      <header className="showcase__head">
        <div>
          <h1 className="showcase__title">组件陈列</h1>
          <p className="showcase__lede">组件与页面框架的演示；主题在标题栏的菜单里切换，五态在页面框架一节打开。</p>
        </div>
      </header>
      {sections.map(({ path, Component }) => {
        const name = path.replace(/^\.\//, '').replace(/\.tsx$/, '');
        return (
          <div key={path} data-showcase={name}>
            <Component />
          </div>
        );
      })}
    </div>
  );
}
