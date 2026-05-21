/**
 * 페르소나 6-Lens 표시 유틸 (plan 0008 v2 · item 2).
 *
 * 복원된 persona_params(L1~L6 척도 점수)를 ① 카드용 키워드 특징,
 * ② 상세용 렌즈별 수치 그룹으로 변환한다. backend/services/persona_param_restore.py 의
 * TARGET_PARAMS 와 키·범위를 맞춰 유지한다.
 */
import type { PersonaParams } from './types';

export const LENS_LABELS: Record<string, string> = {
  L1: '경제적 합리성',
  L2: '의사결정 스타일',
  L3: '동기 구조',
  L4: '사회적 영향',
  L5: '가치 사슬',
  L6: '시간 지향',
  ability: '능력 (통제)',
};

interface ParamMeta {
  key: string;
  lens: keyof typeof LENS_LABELS;
  label: string;
  min: number;
  max: number;
}

// 상세 화면에 렌즈별로 묶어 보여줄 수치 메타 (복원 대상 23개와 일치).
export const PARAM_META: ParamMeta[] = [
  { key: 'l1.tightwad_spendthrift', lens: 'L1', label: '구두쇠–낭비벽', min: 4, max: 26 },
  { key: 'l1.risk_aversion', lens: 'L1', label: '위험 회피', min: 0, max: 1 },
  { key: 'l1.mental_accounting', lens: 'L1', label: '심적 회계', min: 0, max: 1 },
  { key: 'l2.maximization', lens: 'L2', label: '극대화 성향', min: 1, max: 5 },
  { key: 'l2.need_for_closure', lens: 'L2', label: '인지적 종결 욕구', min: 1, max: 5 },
  { key: 'l2.need_for_cognition', lens: 'L2', label: '인지 욕구', min: 1, max: 5 },
  { key: 'l2.crt_score', lens: 'L2', label: '인지 반사(CRT)', min: 0, max: 4 },
  { key: 'l3.regulatory_focus', lens: 'L3', label: '조절초점', min: 1, max: 7 },
  { key: 'l3.agency', lens: 'L3', label: '자기지향 가치', min: 1, max: 9 },
  { key: 'l3.communion', lens: 'L3', label: '타인지향 가치', min: 1, max: 9 },
  { key: 'l3.need_for_uniqueness', lens: 'L3', label: '독특성 욕구', min: 1, max: 5 },
  { key: 'l4.self_monitoring', lens: 'L4', label: '자기 감시', min: 1, max: 5 },
  { key: 'l4.horizontal_individualism', lens: 'L4', label: '수평적 개인주의', min: 1, max: 5 },
  { key: 'l4.vertical_individualism', lens: 'L4', label: '수직적 개인주의', min: 1, max: 5 },
  { key: 'l4.horizontal_collectivism', lens: 'L4', label: '수평적 집단주의', min: 1, max: 5 },
  { key: 'l4.vertical_collectivism', lens: 'L4', label: '수직적 집단주의', min: 1, max: 5 },
  { key: 'l4.empathy', lens: 'L4', label: '공감', min: 1, max: 5 },
  { key: 'l5.minimalism', lens: 'L5', label: '소비자 미니멀리즘', min: 1, max: 5 },
  { key: 'l5.green_values', lens: 'L5', label: '친환경 가치', min: 1, max: 5 },
  { key: 'l6.conscientiousness', lens: 'L6', label: '성실성', min: 0, max: 8 },
  { key: 'l6.present_bias_beta', lens: 'L6', label: '현재 편향 β', min: 0, max: 1 },
  { key: 'ability.financial_literacy', lens: 'ability', label: '금융 이해력', min: 0, max: 5 },
  { key: 'ability.numeracy', lens: 'ability', label: '수리 능력', min: 0, max: 11 },
];

function num(params: PersonaParams, key: string): number | null {
  const v = params[key];
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/** 0~1 정규화 (범위 밖이면 클램프). */
export function normParam(key: string, value: number): number {
  const m = PARAM_META.find((p) => p.key === key);
  if (!m) return value;
  const n = (value - m.min) / (m.max - m.min);
  return Math.max(0, Math.min(1, n));
}

// 카드 키워드 후보 — 정규화 편차가 큰 척도를 골라 high/low 라벨을 붙인다.
interface KwRule {
  key: string;
  high: string;
  low?: string;
}
const KEYWORD_RULES: KwRule[] = [
  { key: 'l2.maximization', high: '극대화 추구', low: '만족 추구형' },
  { key: 'l1.tightwad_spendthrift', high: '소비 적극형', low: '절약형' },
  { key: 'l5.minimalism', high: '미니멀리스트' },
  { key: 'l5.green_values', high: '친환경 지향' },
  { key: 'l2.need_for_cognition', high: '사색형', low: '직관형' },
  { key: 'l4.self_monitoring', high: '상황 적응형', low: '소신형' },
  { key: 'l6.conscientiousness', high: '계획형', low: '즉흥형' },
  { key: 'l2.need_for_closure', high: '확실성 선호' },
  { key: 'l3.need_for_uniqueness', high: '개성 추구' },
  { key: 'l4.empathy', high: '공감형' },
  { key: 'l4.vertical_collectivism', high: '집단·가족 중시' },
];

/** persona_params → 카드용 키워드 특징 (최대 maxTags개, 편차 큰 순). */
export function personaKeywords(params: PersonaParams | null, maxTags = 4): string[] {
  if (!params) return [];
  const scored: { dev: number; label: string }[] = [];
  for (const rule of KEYWORD_RULES) {
    const v = num(params, rule.key);
    if (v === null) continue;
    const dev = normParam(rule.key, v) - 0.5; // -0.5~0.5
    if (Math.abs(dev) < 0.18) continue; // 중간값은 키워드화하지 않음
    const label = dev > 0 ? rule.high : rule.low;
    if (label) scored.push({ dev: Math.abs(dev), label });
  }
  scored.sort((a, b) => b.dev - a.dev);
  return scored.slice(0, maxTags).map((s) => s.label);
}

export interface LensGroup {
  lens: string;
  label: string;
  items: { key: string; label: string; value: number; norm: number }[];
}

/** persona_params → 렌즈별 수치 그룹 (상세 표시용). */
export function groupedParams(params: PersonaParams | null): LensGroup[] {
  if (!params) return [];
  const byLens = new Map<string, LensGroup>();
  for (const m of PARAM_META) {
    const v = num(params, m.key);
    if (v === null) continue;
    if (!byLens.has(m.lens)) byLens.set(m.lens, { lens: m.lens, label: LENS_LABELS[m.lens], items: [] });
    byLens.get(m.lens)!.items.push({ key: m.key, label: m.label, value: v, norm: normParam(m.key, v) });
  }
  return Array.from(byLens.values()).filter((g) => g.items.length > 0);
}
