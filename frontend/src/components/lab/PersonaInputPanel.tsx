'use client';

import { useEffect, useMemo, useState } from 'react';
import { fetchLabTwinDetail } from '@/lib/api';
import type { LabTwinDetail } from '@/lib/types';

interface Props {
  twinId: string;
}

type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

/**
 * 우측 사이드바 — 트윈을 구성한 "에이전트 입력값" 가시화.
 *
 * persona_full은 Toubia 풀-프롬프트로 시스템 프롬프트에 그대로 주입된 JSON
 * 텍스트(~170k chars). 여기서는 JSON.parse 후 최상위 키를 섹션 헤더로,
 * 중첩 객체를 들여쓴 key/value 트리로 풀어준다. JSON 파싱이 실패하면
 * 원문을 preformatted로 보여 준다.
 */
export default function PersonaInputPanel({ twinId }: Props) {
  const [detail, setDetail] = useState<LabTwinDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchLabTwinDetail(twinId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch(() => {
        if (!cancelled) setError('입력값을 불러오지 못했어요.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [twinId]);

  const sections = useMemo<{ key: string; value: JsonValue }[] | null>(() => {
    const raw = detail?.persona_full;
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as JsonValue;
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return Object.entries(parsed).map(([key, value]) => ({ key, value }));
      }
      return [{ key: 'persona', value: parsed }];
    } catch {
      return null;
    }
  }, [detail?.persona_full]);

  return (
    <aside className="lab-input">
      <div className="lab-input__header">
        <div className="lab-input__title">에이전트 입력값</div>
        <div className="lab-input__hint">
          이 트윈을 구성한 설문 응답 원본 — 매 턴 시스템 프롬프트에 주입돼요.
        </div>
      </div>
      <div className="lab-input__body">
        {loading && <div className="lab-input__empty">불러오는 중...</div>}
        {error && !loading && <div className="lab-input__empty">{error}</div>}
        {!loading && !error && detail && !detail.persona_full && (
          <div className="lab-input__empty">이 트윈은 풀 페르소나가 비어있어요.</div>
        )}
        {!loading && !error && sections && (
          <ul className="lab-input__sections">
            {sections.map((s) => (
              <PersonaSection key={s.key} sectionKey={s.key} value={s.value} />
            ))}
          </ul>
        )}
        {!loading && !error && detail?.persona_full && !sections && (
          <pre className="lab-input__raw">{detail.persona_full}</pre>
        )}
      </div>
    </aside>
  );
}

function PersonaSection({
  sectionKey,
  value,
}: {
  sectionKey: string;
  value: JsonValue;
}) {
  const [open, setOpen] = useState(true);
  return (
    <li className="lab-input__section">
      <button
        type="button"
        className="lab-input__section-header"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="lab-input__section-toggle">{open ? '▾' : '▸'}</span>
        <span className="lab-input__section-title">{humanize(sectionKey)}</span>
      </button>
      {open && (
        <div className="lab-input__section-body">
          <JsonNode value={value} depth={0} />
        </div>
      )}
    </li>
  );
}

function JsonNode({ value, depth }: { value: JsonValue; depth: number }) {
  if (value === null || value === undefined) {
    return <span className="lab-input__scalar lab-input__scalar--null">없음</span>;
  }
  if (typeof value === 'string') {
    return <span className="lab-input__scalar">{value || '—'}</span>;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return <span className="lab-input__scalar">{String(value)}</span>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <span className="lab-input__scalar lab-input__scalar--null">[]</span>;
    }
    const allScalar = value.every(isScalar);
    if (allScalar) {
      return (
        <ul className="lab-input__inline-list">
          {value.map((v, i) => (
            <li key={i}>
              <JsonNode value={v} depth={depth + 1} />
            </li>
          ))}
        </ul>
      );
    }
    return (
      <ul className="lab-input__list">
        {value.map((v, i) => (
          <li key={i} className="lab-input__list-item">
            <div className="lab-input__list-index">#{i + 1}</div>
            <JsonNode value={v} depth={depth + 1} />
          </li>
        ))}
      </ul>
    );
  }
  // object
  const entries = Object.entries(value);
  if (entries.length === 0) {
    return <span className="lab-input__scalar lab-input__scalar--null">{'{}'}</span>;
  }
  return (
    <dl className="lab-input__kv">
      {entries.map(([k, v]) => (
        <div key={k} className="lab-input__kv-row">
          <dt className="lab-input__kv-key">{humanize(k)}</dt>
          <dd className="lab-input__kv-val">
            <JsonNode value={v} depth={depth + 1} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function isScalar(v: JsonValue): boolean {
  return (
    v === null ||
    typeof v === 'string' ||
    typeof v === 'number' ||
    typeof v === 'boolean'
  );
}

function humanize(key: string): string {
  if (!key) return key;
  return key
    .replace(/[_\-]+/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
