'use client';

// 페르소나 6-Lens 수치 프로파일 (plan 0008 v2 · item 2) — 키워드 + 렌즈별 막대.
import { Badge } from '@/components/ui/Badge';
import { groupedParams, personaKeywords } from '@/lib/persona';
import type { PersonaParams } from '@/lib/types';

export function PersonaProfile({ params }: { params: PersonaParams | null }) {
  const groups = groupedParams(params);
  const keywords = personaKeywords(params, 6);

  if (groups.length === 0) {
    return (
      <p className="text-sm text-text-muted">
        성향 수치 프로파일이 아직 준비되지 않았습니다.
      </p>
    );
  }

  return (
    <div>
      {keywords.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {keywords.map((k) => (
            <Badge key={k} variant="indigo" size="sm">{k}</Badge>
          ))}
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {groups.map((g) => (
          <div key={g.lens} className="rounded-xl border border-border bg-bg p-3">
            <p className="mb-2 text-xs font-semibold text-ditto-indigo">
              {g.lens === 'ability' ? '' : g.lens + ' '}{g.label}
            </p>
            <ul className="space-y-1.5">
              {g.items.map((it) => (
                <li key={it.key}>
                  <div className="flex items-center justify-between text-2xs text-text-secondary">
                    <span>{it.label}</span>
                    <span className="font-mono tabular-nums text-text-primary">{it.value}</span>
                  </div>
                  <div className="mt-0.5 h-1.5 w-full overflow-hidden rounded-full bg-ditto-indigo-light">
                    <div className="h-full bg-ditto-indigo" style={{ width: `${Math.round(it.norm * 100)}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
