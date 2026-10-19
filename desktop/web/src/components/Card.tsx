import type { HTMLAttributes, ReactNode } from 'react';
import './Card.css';

export interface CardProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}

export function Card({ title, actions, className, children, ...rest }: CardProps) {
  const classes = ['tt-card'];
  if (className) classes.push(className);
  const hasHead = title != null || actions != null;
  return (
    <div className={classes.join(' ')} {...rest}>
      {hasHead && (
        <div className="tt-card__head">
          {title != null && <span className="tt-card__title">{title}</span>}
          {actions != null && <div className="tt-card__actions">{actions}</div>}
        </div>
      )}
      {children != null && <div className="tt-card__body">{children}</div>}
    </div>
  );
}
