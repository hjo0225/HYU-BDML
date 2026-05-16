import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from './cn';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padding?: 'none' | 'sm' | 'md' | 'lg';
  elevated?: boolean;
}

const PADDING: Record<NonNullable<CardProps['padding']>, string> = {
  none: 'p-0',
  sm: 'p-3',
  md: 'p-6',
  lg: 'p-8',
};

export function Card({
  padding = 'md',
  elevated = false,
  className,
  children,
  ...rest
}: CardProps) {
  return (
    <div
      {...rest}
      className={cn(
        'bg-surface border border-border rounded-xl',
        elevated ? 'shadow-elevated' : 'shadow-card',
        PADDING[padding],
        className,
      )}
    >
      {children}
    </div>
  );
}

interface CardHeaderProps extends HTMLAttributes<HTMLDivElement> {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
}

export function CardHeader({ title, subtitle, action, className, ...rest }: CardHeaderProps) {
  return (
    <div
      {...rest}
      className={cn('flex items-start justify-between gap-3 mb-4', className)}
    >
      <div className="min-w-0">
        <h3 className="text-base font-bold text-text-primary truncate">{title}</h3>
        {subtitle && (
          <p className="text-sm text-text-muted mt-0.5">{subtitle}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
