// 第 1 片组件用到的图标，路径取自 Lucide（lucide.dev，ISC 许可）。
// 24×24 viewBox，stroke 用 currentColor，aria-hidden 为 true；fill/stroke 由 .tt-i 提供，这里也显式写上以保证自包含。
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

export const HourglassIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M5 22h14" />
    <path d="M5 2h14" />
    <path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22" />
    <path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2" />
  </Svg>
);

export const CircleDashedIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M10.1 2.182a10 10 0 0 1 3.8 0" />
    <path d="M13.9 21.818a10 10 0 0 1-3.8 0" />
    <path d="M17.609 3.721a10 10 0 0 1 2.69 2.7" />
    <path d="M2.182 13.9a10 10 0 0 1 0-3.8" />
    <path d="M20.279 17.609a10 10 0 0 1-2.7 2.69" />
    <path d="M21.818 10.1a10 10 0 0 1 0 3.8" />
    <path d="M3.721 6.391a10 10 0 0 1 2.7-2.69" />
    <path d="M6.391 20.279a10 10 0 0 1-2.69-2.7" />
  </Svg>
);

export const CircleXIcon = (props: IconProps) => (
  <Svg {...props}>
    <circle cx="12" cy="12" r="10" />
    <path d="m15 9-6 6" />
    <path d="m9 9 6 6" />
  </Svg>
);

export const LoaderCircleIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M21 12a9 9 0 1 1-6.219-8.56" />
  </Svg>
);

export const ArchiveIcon = (props: IconProps) => (
  <Svg {...props}>
    <rect width="20" height="5" x="2" y="3" rx="1" />
    <path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8" />
    <path d="M10 12h4" />
  </Svg>
);

export const ScaleIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
    <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
    <path d="M7 21h10" />
    <path d="M12 3v18" />
    <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2" />
  </Svg>
);

export const CircleCheckIcon = (props: IconProps) => (
  <Svg {...props}>
    <circle cx="12" cy="12" r="10" />
    <path d="m9 12 2 2 4-4" />
  </Svg>
);

export const BadgeCheckIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z" />
    <path d="m9 12 2 2 4-4" />
  </Svg>
);

export const RotateCcwIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
    <path d="M3 3v5h5" />
  </Svg>
);

export const OctagonXIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="m15 9-6 6" />
    <path d="M2.586 16.726A2 2 0 0 1 2 15.312V8.688a2 2 0 0 1 .586-1.414l4.688-4.688A2 2 0 0 1 8.688 2h6.624a2 2 0 0 1 1.414.586l4.688 4.688A2 2 0 0 1 22 8.688v6.624a2 2 0 0 1-.586 1.414l-4.688 4.688a2 2 0 0 1-1.414.586H8.688a2 2 0 0 1-1.414-.586z" />
    <path d="m9 9 6 6" />
  </Svg>
);

export const CircleArrowUpIcon = (props: IconProps) => (
  <Svg {...props}>
    <circle cx="12" cy="12" r="10" />
    <path d="m16 12-4-4-4 4" />
    <path d="M12 16V8" />
  </Svg>
);

export const ServerCrashIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M6 10H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2" />
    <path d="M6 14H4a2 2 0 0 0-2 2v4a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-4a2 2 0 0 0-2-2h-2" />
    <path d="M6 6h.01" />
    <path d="M6 18h.01" />
    <path d="m13 6-4 6h6l-4 6" />
  </Svg>
);

export const TimerOffIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M10 2h4" />
    <path d="M4.6 11a8 8 0 0 0 1.7 8.7 8 8 0 0 0 8.7 1.7" />
    <path d="M7.4 7.4a8 8 0 0 1 10.3 1 8 8 0 0 1 .9 10.2" />
    <path d="m2 2 20 20" />
    <path d="M12 12v-2" />
  </Svg>
);

export const BanIcon = (props: IconProps) => (
  <Svg {...props}>
    <circle cx="12" cy="12" r="10" />
    <path d="m4.9 4.9 14.2 14.2" />
  </Svg>
);

export const GitMergeIcon = (props: IconProps) => (
  <Svg {...props}>
    <circle cx="18" cy="18" r="3" />
    <circle cx="6" cy="6" r="3" />
    <path d="M6 21V9a9 9 0 0 0 9 9" />
  </Svg>
);

export const ArchiveXIcon = (props: IconProps) => (
  <Svg {...props}>
    <rect width="20" height="5" x="2" y="3" rx="1" />
    <path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8" />
    <path d="m9.5 17 5-5" />
    <path d="m9.5 12 5 5" />
  </Svg>
);

export const LayersIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z" />
    <path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65" />
    <path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65" />
  </Svg>
);

export const CircleHelpIcon = (props: IconProps) => (
  <Svg {...props}>
    <circle cx="12" cy="12" r="10" />
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
    <path d="M12 17h.01" />
  </Svg>
);

export const InfoIcon = (props: IconProps) => (
  <Svg {...props}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 16v-4" />
    <path d="M12 8h.01" />
  </Svg>
);

export const TriangleAlertIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3" />
    <path d="M12 9v4" />
    <path d="M12 17h.01" />
  </Svg>
);

export const XIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </Svg>
);

export const ChevronDownIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="m6 9 6 6 6-6" />
  </Svg>
);

export const ChevronRightIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="m9 18 6-6-6-6" />
  </Svg>
);

export const CheckIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M20 6 9 17l-5-5" />
  </Svg>
);

export const ListChecksIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="m3 17 2 2 4-4" />
    <path d="m3 7 2 2 4-4" />
    <path d="M13 6h8" />
    <path d="M13 12h8" />
    <path d="M13 18h8" />
  </Svg>
);

// 第 5 片（T007）新增的三个图标，路径取自领域板 :404、:409 与 Lucide 1.59.0 的 eye-off（ISC）。
export const LockIcon = (props: IconProps) => (
  <Svg {...props}>
    <rect width="18" height="11" x="3" y="11" rx="2" ry="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </Svg>
);

export const CopyIcon = (props: IconProps) => (
  <Svg {...props}>
    <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
    <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
  </Svg>
);

export const EyeOffIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M10.733 5.076a10.744 10.744 0 0 1 11.205 6.575 1 1 0 0 1 0 .696 10.747 10.747 0 0 1-1.444 2.49" />
    <path d="M14.084 14.158a3 3 0 0 1-4.242-4.242" />
    <path d="M17.479 17.499a10.75 10.75 0 0 1-15.417-5.151 1 1 0 0 1 0-.696 10.75 10.75 0 0 1 4.446-5.143" />
    <path d="m2 2 20 20" />
  </Svg>
);

// 第 7 片（T008）新增的三个图标，路径照画布（领域板 :381、详情页 :638 与 :389）。
export const PauseIcon = (props: IconProps) => (
  <Svg {...props}>
    <rect width="4" height="14" x="6" y="5" rx="1" />
    <rect width="4" height="14" x="14" y="5" rx="1" />
  </Svg>
);

export const FilterIcon = (props: IconProps) => (
  <Svg {...props}>
    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3" />
  </Svg>
);

export const FileDiffIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
    <path d="M9 10h6" />
    <path d="M12 13V7" />
    <path d="M9 17h6" />
  </Svg>
);

// 第 8 片（T009）新增的四个图标，路径照合同第 3 节。
export const PlusIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M5 12h14" />
    <path d="M12 5v14" />
  </Svg>
);

export const SearchIcon = (props: IconProps) => (
  <Svg {...props}>
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.3-4.3" />
  </Svg>
);

export const PlayIcon = (props: IconProps) => (
  <Svg {...props}>
    <polygon points="6 3 20 12 6 21 6 3" />
  </Svg>
);

export const ArrowRightIcon = (props: IconProps) => (
  <Svg {...props}>
    <path d="M5 12h14" />
    <path d="m12 5 7 7-7 7" />
  </Svg>
);
