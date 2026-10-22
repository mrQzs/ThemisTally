// 本片自写的图标（合同 §5.5 S6、K17）：FileTextIcon 的路径等于详情页画布「summary.md」那一行。
// SearchIcon 用 src/icons/index.tsx 的导出（路径等于任务页画布搜索框那一行），本片不重写。
import type { ReactNode, SVGProps } from 'react';

type IconProps = SVGProps<SVGSVGElement> & { children?: ReactNode };

function Svg({ children, ...props }: IconProps) {
  const { width = 24, height = 24, className, ...rest } = props;
  return (
    <svg
      className={className ? `tt-i ${className}` : 'tt-i'}
      width={width}
      height={height}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  );
}

/** 摘要页签的文件行图标（详情页画布 :324「summary.md」那一行）。 */
export const FileTextIcon = (props: SVGProps<SVGSVGElement>) => (
  <Svg {...props}>
    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
    <path d="M14 2v4a2 2 0 0 0 2 2h4" />
    <path d="M10 9H8" />
    <path d="M16 13H8" />
    <path d="M16 17H8" />
  </Svg>
);
