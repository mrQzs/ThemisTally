// 外壳页新增图标（src/shellpages/icons.tsx）：ArrowRightIcon（首启画布 :358）、FileTextIcon（设置画布 :427）、
// ExternalLinkIcon（设置画布 :428），path d 逐个等于画布对应行。包装照 icons/index.tsx :7–26
// （tt-i、stroke currentColor、aria-hidden）；24×24 viewBox，fill/stroke 由 .tt-i 提供。
import type { ReactNode, SVGProps } from 'react';

export type IconProps = SVGProps<SVGSVGElement>;

function Svg({ children, ...props }: IconProps & { children: ReactNode }) {
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

export const ArrowRightIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M5 12h14" />
    <path d="m12 5 7 7-7 7" />
  </Svg>
);

export const FileTextIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
    <path d="M14 2v4a2 2 0 0 0 2 2h4" />
    <path d="M10 9H8" />
    <path d="M16 13H8" />
    <path d="M16 17H8" />
  </Svg>
);

export const ExternalLinkIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M15 3h6v6" />
    <path d="M10 14 21 3" />
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
  </Svg>
);
