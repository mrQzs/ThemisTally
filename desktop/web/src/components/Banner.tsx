import type { HTMLAttributes, ReactNode } from 'react';
import { InfoIcon, TriangleAlertIcon, XIcon } from '../icons';
import './Banner.css';

export type BannerTone = 'info' | 'warning' | 'danger';

export interface BannerProps extends HTMLAttributes<HTMLDivElement> {
  tone?: BannerTone;
  onClose?: () => void;
  children?: ReactNode;
}

export function Banner({ tone = 'info', onClose, className, children, ...rest }: BannerProps) {
  const classes = ['tt-banner', `tt-banner--${tone}`];
  if (className) classes.push(className);
  const Icon = tone === 'info' ? InfoIcon : TriangleAlertIcon;
  const showClose = tone === 'info';
  return (
    <div
      className={classes.join(' ')}
      data-tone={tone}
      role={tone === 'danger' ? 'alert' : undefined}
      {...rest}
    >
      <Icon width={16} height={16} className="tt-banner__icon" />
      <span className="tt-banner__text">{children}</span>
      {showClose && (
        <button
          type="button"
          className="tt-banner__close"
          aria-label="关闭提示"
          onClick={onClose}
        >
          <XIcon width={14} height={14} />
        </button>
      )}
    </div>
  );
}
