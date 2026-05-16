import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';
import { cn } from './cn';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  leftAddon?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, hint, leftAddon, className, id, ...rest },
  ref,
) {
  const inputId = id ?? rest.name;
  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={inputId}
          className="block text-sm font-medium text-text-secondary mb-1"
        >
          {label}
        </label>
      )}
      <div className={cn('relative', leftAddon && 'flex items-stretch')}>
        {leftAddon && (
          <span className="inline-flex items-center px-3 rounded-l-lg border border-r-0 border-border bg-surface text-sm text-text-muted">
            {leftAddon}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={!!error || undefined}
          className={cn(
            'w-full bg-surface border text-sm text-text-primary placeholder:text-text-muted',
            'px-3 py-2 transition-shadow duration-150',
            'focus:outline-none focus:ring-2 focus:border-transparent',
            leftAddon ? 'rounded-r-lg' : 'rounded-lg',
            error
              ? 'border-error focus:ring-error'
              : 'border-border focus:ring-ditto-indigo',
            className,
          )}
          {...rest}
        />
      </div>
      {error ? (
        <p className="text-xs text-error mt-1">{error}</p>
      ) : hint ? (
        <p className="text-xs text-text-muted mt-1">{hint}</p>
      ) : null}
    </div>
  );
});
