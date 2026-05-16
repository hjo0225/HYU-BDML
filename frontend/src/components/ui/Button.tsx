import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cn } from './cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leftIcon?: ReactNode;
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary:
    'bg-ditto-indigo text-white hover:bg-ditto-indigo-hover ' +
    'disabled:opacity-50 disabled:cursor-not-allowed',
  secondary:
    'bg-surface text-ditto-indigo border border-ditto-indigo ' +
    'hover:bg-ditto-indigo-light disabled:opacity-50 disabled:cursor-not-allowed',
  ghost:
    'bg-transparent text-text-secondary hover:bg-ditto-indigo-light hover:text-ditto-indigo ' +
    'disabled:opacity-50 disabled:cursor-not-allowed',
  danger:
    'bg-error text-white hover:opacity-90 ' +
    'disabled:opacity-50 disabled:cursor-not-allowed',
};

const SIZE_CLASS: Record<Size, string> = {
  sm: 'text-xs px-3 py-1.5 rounded-lg gap-1.5',
  md: 'text-sm px-4 py-2 rounded-lg gap-2',
  lg: 'text-base px-5 py-2.5 rounded-xl gap-2',
};

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  leftIcon,
  disabled,
  className,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center font-medium transition-colors duration-150',
        VARIANT_CLASS[variant],
        SIZE_CLASS[size],
        className,
      )}
    >
      {loading ? (
        <span
          aria-hidden
          className="w-3.5 h-3.5 rounded-full border-2 border-current border-r-transparent animate-spin"
        />
      ) : leftIcon}
      {children}
    </button>
  );
}
