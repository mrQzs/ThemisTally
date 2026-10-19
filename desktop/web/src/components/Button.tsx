import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { LoaderCircleIcon } from '../icons';
import './Button.css';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  loadingText?: ReactNode;
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  loadingText,
  disabled,
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  const isDisabled = Boolean(disabled) || loading;
  const classes = ['tt-btn', `tt-btn--${variant}`, `tt-btn--${size}`];
  if (className) classes.push(className);
  return (
    <button
      type={type}
      className={classes.join(' ')}
      data-variant={variant}
      data-size={size}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? (
        <>
          <LoaderCircleIcon width={16} height={16} className="tt-spin" />
          <span>{loadingText ?? children}</span>
        </>
      ) : (
        children
      )}
    </button>
  );
}
