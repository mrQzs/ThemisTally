// 浮层内部模块：挂载层。把浮层用 createPortal 挂到 document.body，外包一层带 tt-app 类、不占位的 div。
// 浮层才吃得到 base.css 的基础规则与焦点环；又因为产物里组件 CSS 排在 base.css 之前，同特异性时 .tt-app 规则胜出，
// 所以不能给浮层根直接加 tt-app（底色会被盖成 --tt-bg）——用这层外包的挂载层即可两全。
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';

export function MountLayer({ children }: { children: ReactNode }) {
  return createPortal(<div className="tt-app">{children}</div>, document.body);
}
