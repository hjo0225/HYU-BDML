import { forwardRef, type TextareaHTMLAttributes } from 'react';
import { cn } from './cn';

// Input 과 동일한 API(label/error/hint)의 멀티라인 입력. 채팅·FGI·자유서술 폼 재사용.
interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, error, hint, className, id, rows = 3, ...rest },
  ref,
) {
  const textareaId = id ?? rest.name;
  return (
    <div className="w-full">
      {label && (
        <label
          htmlFor={textareaId}
          className="block text-sm font-medium text-text-secondary mb-1"
        >
          {label}
        </label>
      )}
      <textarea
        ref={ref}
        id={textareaId}
        rows={rows}
        aria-invalid={!!error || undefined}
        className={cn(
          'w-full bg-surface border text-sm text-text-primary placeholder:text-text-muted',
          'px-3 py-2 rounded-lg transition-shadow duration-150 resize-y',
          'focus:outline-none focus:ring-2 focus:border-transparent',
          error
            ? 'border-error focus:ring-error'
            : 'border-border focus:ring-ditto-indigo',
          className,
        )}
        {...rest}
      />
      {error ? (
        <p className="text-xs text-error mt-1">{error}</p>
      ) : hint ? (
        <p className="text-xs text-text-muted mt-1">{hint}</p>
      ) : null}
    </div>
  );
});
