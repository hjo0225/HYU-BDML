'use client';

import type { LabFaithfulness } from '@/lib/types';

const CATEGORY_KO: Record<string, string> = {
  demographics:           '인구통계',
  personality_big5:       'Big5 성격',
  values_environment:     '환경 가치관',
  values_minimalism:      '미니멀리즘',
  values_agency:          '주체성/공동체',
  values_individualism:   '개인주의/집단주의',
  values_uniqueness:      '고유성 욕구',
  values_regulatory:      '조절 초점',
  decision_risk:          '위험 회피',
  decision_loss:          '손실 회피',
  decision_maximization:  '최대화 성향',
  emotion_anxiety:        '불안',
  emotion_depression:     '우울',
  emotion_empathy:        '공감',
  social_trust:           '신뢰 게임',
  social_ultimatum:       '최후통첩 게임',
  social_dictator:        '독재자 게임',
  social_desirability:    '사회적 바람직성',
  cognition_general:      '인지 욕구',
  cognition_reflection:   '인지 반영',
  cognition_intelligence: '유동/결정 지능',
  cognition_logic:        '삼단논법',
  cognition_numeracy:     '수리력',
  cognition_closure:      '폐쇄 욕구',
  finance_mental:         '심적 회계',
  finance_literacy:       '금융 이해도',
  finance_time_pref:      '시간 선호',
  finance_tightwad:       '인색함/씀씀이',
  self_aspire:            '이상적 자아',
  self_ought:             '의무적 자아',
  self_actual:            '실제 자아',
  self_clarity:           '자기 개념 명료성',
  self_monitoring:        '자기 모니터링',
};

function pct(v: number): number {
  return Math.max(0, Math.min(100, Math.round(v * 100)));
}

function label(slug: string): string {
  return CATEGORY_KO[slug] || slug.replace(/_/g, ' ');
}

interface BadgeProps {
  faithfulness: LabFaithfulness;
  compact?: boolean;
}

export function FaithfulnessBadge({ faithfulness, compact }: BadgeProps) {
  const score = pct(faithfulness.overall);
  const tone = score >= 80 ? 'high' : score >= 60 ? 'mid' : 'low';
  return (
    <span
      className={`lab-faith-badge lab-faith-badge--${tone}${compact ? ' lab-faith-badge--compact' : ''}`}
      title={`${faithfulness.n_eval}개 카테고리 평균${faithfulness.evaluated_at ? ` · 측정 ${faithfulness.evaluated_at.slice(0, 10)}` : ''}`}
    >
      충실도 {score}%
    </span>
  );
}

interface BarsProps {
  faithfulness: LabFaithfulness;
  maxRows?: number;
}

export function FaithfulnessBars({ faithfulness, maxRows }: BarsProps) {
  const entries = Object.entries(faithfulness.by_category)
    .sort((a, b) => a[1] - b[1]); // 약한 카테고리부터
  const rows = maxRows ? entries.slice(0, maxRows) : entries;

  if (rows.length === 0) {
    return <div className="lab-faith-empty">아직 충실도 데이터가 없습니다.</div>;
  }

  return (
    <ul className="lab-faith-bars">
      {rows.map(([slug, score]) => {
        const p = pct(score);
        const tone = p >= 80 ? 'high' : p >= 60 ? 'mid' : 'low';
        return (
          <li key={slug} className="lab-faith-bars__row">
            <span className="lab-faith-bars__name">{label(slug)}</span>
            <span className="lab-faith-bars__bar-wrap" aria-label={`${label(slug)} ${p}%`}>
              <span
                className={`lab-faith-bars__bar lab-faith-bars__bar--${tone}`}
                style={{ width: `${Math.max(2, p)}%` }}
              />
            </span>
            <span className="lab-faith-bars__value">{p}</span>
          </li>
        );
      })}
    </ul>
  );
}

export default FaithfulnessBars;
