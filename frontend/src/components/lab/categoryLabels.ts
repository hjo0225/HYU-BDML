// PanelMemory.category 슬러그 → 한국어 라벨.
// CitationToggle, SurveyQuestionsPanel 등 Lab 컴포넌트가 공유한다.
export const CATEGORY_KO: Record<string, string> = {
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

export function categoryLabel(slug: string): string {
  if (CATEGORY_KO[slug]) return CATEGORY_KO[slug];
  return slug.replace(/_/g, ' ');
}
