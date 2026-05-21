import Link from 'next/link';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cn } from './cn';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leftIcon?: ReactNode;
  /** 부모 폭을 가득 채움. 버튼을 세로로 쌓을 때 크기를 맞추는 용도. */
  fullWidth?: boolean;
  /** 지정 시 next/link 로 렌더 — `<Link><Button>` 래핑 없이 링크 버튼을 만든다. */
  href?: string;
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
  fullWidth = false,
  href,
  disabled,
  className,
  children,
  ...rest
}: ButtonProps) {
  const classes = cn(
    'inline-flex items-center justify-center font-medium transition-colors duration-150',
    VARIANT_CLASS[variant],
    SIZE_CLASS[size],
    fullWidth && 'w-full',
    className,
  );

  const inner = (
    <>
      {loading ? (
        <span
          aria-hidden
          className="w-3.5 h-3.5 rounded-full border-2 border-current border-r-transparent animate-spin"
        />
      ) : leftIcon}
      {children}
    </>
  );

  // href 가 있으면 링크 버튼(next/link). 비활성 시 클릭 차단 + 흐림 처리.
  if (href) {
    const inactive = disabled || loading;
    return (
      <Link
        href={href}
        aria-disabled={inactive || undefined}
        tabIndex={inactive ? -1 : undefined}
        className={cn(classes, inactive && 'pointer-events-none')}
      >
        {inner}
      </Link>
    );
  }

  return (
    <button {...rest} disabled={disabled || loading} className={classes}>
      {inner}
    </button>
  );
}
