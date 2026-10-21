// 只读页面二自写的图标（合同「公共件」）：icons/index.tsx 里没有外链图标，这里补一个。
// 24×24 viewBox、stroke 用 currentColor；fill 与 stroke 只用 none 与 currentColor（门禁 S10）。
import type { ReactNode, SVGProps } from 'react';

export type CommonIconProps = SVGProps<SVGSVGElement>;

function Svg({ children, ...props }: CommonIconProps & { children: ReactNode }) {
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

/** 外链（录入…、一次性页面用），路径取自 Lucide 的 external-link（ISC 许可）。 */
export const ExternalLinkIcon = (props: CommonIconProps) => (
  <Svg {...props}>
    <path d="M15 3h6v6" />
    <path d="M10 14 21 3" />
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
  </Svg>
);
