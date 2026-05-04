'use client';

import { useEffect, useMemo, useState } from 'react';
import { fetchLabTwinDetail } from '@/lib/api';
import type { LabTwinDetail, MemoryCitation } from '@/lib/types';
import { categoryLabel } from './categoryLabels';

interface Props {
  twinId: string;
  citations?: MemoryCitation[];
}

type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

/**
 * 답변 인용 카테고리(slug) → persona_full 섹션 키워드 매칭용 사전.
 *
 * 인용은 PanelMemory(=`persona_summary` 기반) 카테고리이고, 우측 패널은
 * `persona_json`(=persona_full) 기반이라 텍스트 일치는 어렵다.
 * 그래서 카테고리별로 persona_full 섹션 키/내용에 등장할 법한 핵심 키워드
 * 몇 개를 두고, 섹션 키 또는 직렬화된 내용에 한 개라도 포함되면 그 섹션을
 * "근거 사용"으로 본다. 키워드는 모두 lowercase.
 */
const CATEGORY_KEYWORDS: Record<string, string[]> = {
  demographics: ['demographic', 'age', 'gender', 'race', 'education', 'income', 'household', 'marital', 'religion', 'region', 'occupation'],
  personality_big5: ['big5', 'big_5', 'big 5', 'personality', 'extraversion', 'openness', 'conscientiousness', 'agreeableness', 'neuroticism'],
  values_environment: ['environment', 'climate', 'green'],
  values_minimalism: ['minimal'],
  values_agency: ['agency', 'community', 'collective'],
  values_individualism: ['individual', 'collectivis'],
  values_uniqueness: ['uniqueness', 'unique'],
  values_regulatory: ['regulatory', 'promotion', 'prevention'],
  decision_risk: ['risk'],
  decision_loss: ['loss', 'aversion'],
  decision_maximization: ['maximiz'],
  emotion_anxiety: ['anxiety', 'anxious'],
  emotion_depression: ['depress'],
  emotion_empathy: ['empathy'],
  social_trust: ['trust'],
  social_ultimatum: ['ultimatum'],
  social_dictator: ['dictator'],
  social_desirability: ['desirab'],
  cognition_general: ['cognition', 'cognitive'],
  cognition_reflection: ['reflection', 'reflective'],
  cognition_intelligence: ['intelligence', 'iq'],
  cognition_logic: ['logic'],
  cognition_numeracy: ['numeracy'],
  cognition_closure: ['closure'],
  finance_mental: ['mental account', 'budget', 'finance'],
  finance_literacy: ['literacy', 'finance'],
  finance_time_pref: ['time pref', 'discount'],
  finance_tightwad: ['tightwad', 'spendthrift'],
  self_aspire: ['aspire', 'ideal self'],
  self_ought: ['ought self'],
  self_actual: ['actual self', 'real self'],
  self_clarity: ['self clarity', 'self-clarity'],
  self_monitoring: ['monitoring', 'self-monitor'],
  political_views: ['political', 'politics'],
  occupation: ['occupation', 'job', 'career'],
  religion: ['religion', 'religious', 'faith'],
  marital_status: ['marital', 'marriage'],
  household: ['household'],
  income: ['income'],
};

/**
 * 우측 사이드바 — 트윈을 구성한 "에이전트 입력값" 가시화 + 인용 하이라이트.
 *
 * persona_full은 Toubia 풀-프롬프트로 시스템 프롬프트에 그대로 주입된 JSON
 * 텍스트(~170k chars). 여기서는 JSON.parse 후 최상위 키를 섹션 헤더로,
 * 중첩 객체를 들여쓴 key/value 트리로 풀어준다. 직전 답변에 인용된 카테고리에
 * 매칭되는 섹션은 초록 하이라이트로 강조된다.
 */
export default function PersonaInputPanel({ twinId, citations = [] }: Props) {
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

  const sections = useMemo<{ key: string; value: JsonValue; haystack: string }[] | null>(() => {
    const raw = detail?.persona_full;
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as JsonValue;
      const entries: [string, JsonValue][] =
        parsed && typeof parsed === 'object' && !Array.isArray(parsed)
          ? Object.entries(parsed)
          : [['persona', parsed]];
      return entries.map(([key, value]) => ({
        key,
        value,
        // 매칭에 쓸 lowercase 직렬화 텍스트. 너무 길면 자른다(매칭 비용 제한).
        haystack: (key + ' ' + JSON.stringify(value)).toLowerCase().slice(0, 4000),
      }));
    } catch {
      return null;
    }
  }, [detail?.persona_full]);

  // 인용된 카테고리들 → 매칭되는 persona_full 섹션 키 집합.
  const citedSectionKeys = useMemo<Set<string>>(() => {
    const matched = new Set<string>();
    if (!sections || citations.length === 0) return matched;
    const cats = citations.map((c) => c.category);
    for (const sec of sections) {
      for (const cat of cats) {
        const keywords = CATEGORY_KEYWORDS[cat];
        if (!keywords) continue;
        if (keywords.some((kw) => sec.haystack.includes(kw))) {
          matched.add(sec.key);
          break;
        }
      }
    }
    return matched;
  }, [sections, citations]);

  // 섹션 → 매칭된 인용 카테고리 목록 (배지 표시용).
  const sectionCitedCategories = useMemo<Map<string, string[]>>(() => {
    const map = new Map<string, string[]>();
    if (!sections || citations.length === 0) return map;
    const cats = Array.from(new Set(citations.map((c) => c.category)));
    for (const sec of sections) {
      const hits: string[] = [];
      for (const cat of cats) {
        const keywords = CATEGORY_KEYWORDS[cat];
        if (!keywords) continue;
        if (keywords.some((kw) => sec.haystack.includes(kw))) {
          hits.push(cat);
        }
      }
      if (hits.length) map.set(sec.key, hits);
    }
    return map;
  }, [sections, citations]);

  return (
    <aside className="lab-input">
      <div className="lab-input__header">
        <div className="lab-input__title">에이전트 입력값</div>
        <div className="lab-input__hint">
          이 트윈을 구성한 설문 응답 원본 — 매 턴 시스템 프롬프트에 주입돼요.
          {citations.length > 0 && ' 직전 답변의 근거 섹션은 초록색으로 강조돼요.'}
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
              <PersonaSection
                key={s.key}
                sectionKey={s.key}
                value={s.value}
                cited={citedSectionKeys.has(s.key)}
                citedCategories={sectionCitedCategories.get(s.key) || []}
              />
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
  cited,
  citedCategories,
}: {
  sectionKey: string;
  value: JsonValue;
  cited: boolean;
  citedCategories: string[];
}) {
  const [open, setOpen] = useState(true);
  return (
    <li className={`lab-input__section${cited ? ' lab-input__section--cited' : ''}`}>
      <button
        type="button"
        className="lab-input__section-header"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="lab-input__section-toggle">{open ? '▾' : '▸'}</span>
        <span className="lab-input__section-title">{humanize(sectionKey)}</span>
        {cited && (
          <span
            className="lab-input__cited-badge"
            title={`이번 답변의 근거: ${citedCategories.map(categoryLabel).join(', ')}`}
          >
            🟢 근거
          </span>
        )}
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
