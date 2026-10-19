import type { HTMLAttributes } from 'react';
import { resolveAttemptState } from '../domain/attemptStates';
import './StatusTag.css';

export type StatusTagSize = 'md' | 'sm';

export interface StatusTagProps extends HTMLAttributes<HTMLSpanElement> {
  state: string;
  size?: StatusTagSize;
}

export function StatusTag({ state, size = 'md', className, ...rest }: StatusTagProps) {
  const info = resolveAttemptState(state);
  const classes = ['tt-status', `tt-status--${size}`];
  if (className) classes.push(className);
  const Icon = info.icon;
  const dim = size === 'sm' ? 12 : 14;
  const iconNode = <Icon width={dim} height={dim} className={info.spin ? 'tt-spin' : undefined} />;
  return (
    <span
      className={classes.join(' ')}
      data-tone={info.tone}
      data-size={size}
      title={state}
      {...rest}
    >
      {info.dot ? (
        <span className="tt-status__icon">
          {iconNode}
          <span className="tt-status__dot" aria-hidden="true" />
        </span>
      ) : (
        iconNode
      )}
      {info.display}
    </span>
  );
}
