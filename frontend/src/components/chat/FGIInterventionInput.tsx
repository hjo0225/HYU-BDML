'use client';

import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { cn } from '@/components/ui/cn';

interface FGIInterventionInputProps {
  /** true 일 때만 입력 가능 + 펄스 애니메이션. false 면 안내 placeholder 만. */
  active: boolean;
  /** Enter 또는 명시적 전송 시 호출 (trim 된 값) */
  onSubmit: (text: string) => void;
  /** Esc 또는 빈 전송 시 호출 — 다음 에이전트 라운드로 양보 */
  onYield?: () => void;
  /** placeholder 오버라이드 ({ active?: string; idle?: string }) */
  placeholder?: { active?: string; idle?: string };
  /** 최대 글자수 (기본 500) */
  maxLength?: number;
}

const DEFAULT_PLACEHOLDER = {
  active: '발언하실 차례입니다. Enter 로 전송, Shift+Enter 줄바꿈, Esc 로 양보.',
  idle: '모더레이터가 발언 차례를 전달하면 입력할 수 있습니다.',
};

export function FGIInterventionInput({
  active,
  onSubmit,
  onYield,
  placeholder = {},
  maxLength = 500,
}: FGIInterventionInputProps) {
  const [value, setValue] = useState('');
  const ref = useRef<HTMLTextAreaElement>(null);
  const ph = { ...DEFAULT_PLACEHOLDER, ...placeholder };

  useEffect(() => {
    if (active) {
      ref.current?.focus();
    } else {
      setValue('');
    }
  }, [active]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (!active) return;
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      const trimmed = value.trim();
      if (trimmed) {
        onSubmit(trimmed);
        setValue('');
      } else {
        // 빈 Enter 는 양보로 해석
        onYield?.();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setValue('');
      onYield?.();
    }
  }

  return (
    <div className="w-full">
      <textarea
        ref={ref}
        value={value}
        onChange={e => setValue(e.target.value.slice(0, maxLength))}
        onKeyDown={handleKeyDown}
        rows={2}
        readOnly={!active}
        aria-label="FGI 사용자 개입 입력"
        placeholder={active ? ph.active : ph.idle}
        className={cn(
          'w-full resize-none px-3 py-2 rounded-xl text-sm transition-all duration-150',
          'bg-surface text-text-primary placeholder:text-text-muted',
          'focus:outline-none',
          active
            ? 'border-2 border-ditto-indigo animate-pulse-ring'
            : 'border border-border opacity-70 cursor-not-allowed',
        )}
      />
      {active && (
        <div className="flex items-center justify-between mt-1 text-[10px] text-text-muted">
          <span>{value.length} / {maxLength}</span>
          <span>Enter 전송 · Shift+Enter 줄바꿈 · Esc 양보</span>
        </div>
      )}
    </div>
  );
}
