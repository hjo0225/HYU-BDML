import { forwardRef, type SelectHTMLAttributes } from 'react';
import { cn } from './cn';

interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
  options: SelectOption[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, error, hint, options, placeholder, className, id, ...rest },
  ref,
) {
  const selectId = id ?? rest.name;
  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={selectId}
          className="block text-sm font-medium text-text-secondary mb-1"
        >
          {label}
        </label>
      )}
      <div className="relative">
        <select
          ref={ref}
          id={selectId}
          aria-invalid={!!error || undefined}
          className={cn(
            'w-full appearance-none bg-surface border text-sm text-text-primary',
            'px-3 py-2 pr-9 rounded-lg transition-shadow duration-150',
            'focus:outline-none focus:ring-2 focus:border-transparent',
            error
              ? 'border-error focus:ring-error'
              : 'border-border focus:ring-ditto-indigo',
            className,
          )}
          {...rest}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((o) => (
            <option key={o.value} value={o.value} disabled={o.disabled}>
              {o.label}
            </option>
          ))}
        </select>
        {/* 화살표 인디케이터 (CSS triangle 대체로 SVG) */}
        <svg
          aria-hidden
          viewBox="0 0 12 12"
          className="absolute right-3 top-1/2 -translate-y-1/2 w-3 h-3 pointer-events-none text-text-muted"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path d="M3 4.5L6 7.5L9 4.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
      {error ? (
        <p className="text-xs text-error mt-1">{error}</p>
      ) : hint ? (
        <p className="text-xs text-text-muted mt-1">{hint}</p>
      ) : null}
    </div>
  );
});
