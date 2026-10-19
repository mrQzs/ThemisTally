import type { HTMLAttributes, ReactNode } from 'react';
import './Tag.css';

export type TagTone =
  | 'neutral'
  | 'info'
  | 'attention'
  | 'success'
  | 'warning'
  | 'danger'
  | 'escalate'
  | 'brand';

export interface TagProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: TagTone;
  mono?: boolean;
  children?: ReactNode;
}

export function Tag({ tone = 'neutral', mono = false, className, children, ...rest }: TagProps) {
  const classes = ['tt-tag', `tt-tag--${tone}`];
  if (mono) classes.push('tt-tag--mono');
  if (className) classes.push(className);
  return (
    <span className={classes.join(' ')} data-tone={tone} {...rest}>
      {children}
    </span>
  );
}
