# 6-Lens Mapping — Twin-2K-500 234문항

> **상태: TODO (Phase 1 — 헤더만).** 실제 매핑 테이블은 Phase 2 진입 시 `Twin2K500_KR_Localized_v1_1.pdf` 분석 후 채워진다.

본 문서는 Twin-2K-500 한국어 로컬라이즈 v1.1 의 **234문항을 6-Lens(L1~L6) + 정성 그룹**에 1:1 매핑하는 룩업 테이블이다. `backend/lenses/mapping.py` 의 단일 진실 공급원이며, 매핑이 바뀌면 본 문서를 먼저 갱신한 뒤 코드를 수정한다.

## Lens 정의 요약

| Lens | 영역 | 핵심 척도 |
|---|---|---|
| **L1** 경제적 합리성 | 위험·손실 회피, 심적 회계, 소비 습관 | 위험 회피 점수, 손실 회피 비율, 심적 회계 분리도, 절약 성향 |
| **L2** 의사결정 스타일 | 극대화 성향, 인지 욕구, 인지 반사 | Maximization Scale, Need for Cognition, CRT 정답 수 |
| **L3** 동기 (조절초점) | 향상/예방 초점, 미니멀리즘 | Promotion vs Prevention, 미니멀리즘 척도 |
| **L4** 사회적 영향 | 자기 감시, 집단주의, 공감도, 정책 찬반 | Self-Monitoring, Collectivism, IRI 공감도 |
| **L5** 가치 (자기/타인지향) | 자기지향 / 타인지향 가치, 환경 가치 | Schwartz Values, 환경의식 |
| **L6** 시간 지향 | 할인율, 현재 편향, 성실성 | 할인율(연환산), 현재 편향 β, 성실성(Big5) |
| **정성** | 자기 서술 + 게임 사고 | self_actual, self_aspire, self_ought, dictator_reasoning |

## 룩업 테이블 (TODO — Phase 2 입구에서 작성)

### L1 — 경제적 합리성

| 문항 ID | 한국어 라벨 | 응답 형식 | 채점 처리 | 산출 파라미터 |
|---|---|---|---|---|
| L1-1 | (TODO) 위험 회피 시나리오 | 이지선다/금액 선택 | 확실성 등가(CE) 계산 | `l1.risk_aversion`, `l1.ce` |
| L1-2 | (TODO) 손실 회피 | 이지선다 | 손실/이득 비율 산정 | `l1.loss_aversion_ratio` |
| L1-3 | (TODO) 심적 회계 (커피숍 시나리오) | 이지선다 | 분리도 0~1 | `l1.mental_accounting` |
| ... | ... | ... | ... | ... |

### L2 — 의사결정 스타일

| 문항 ID | 한국어 라벨 | 응답 형식 | 채점 처리 | 산출 파라미터 |
|---|---|---|---|---|
| L2-1 | (TODO) Maximization Scale | 7점 척도 × N문항 | 평균 + 역채점 일부 | `l2.maximization` |
| L2-2 | (TODO) Need for Cognition | 7점 척도 | 역채점 변환 후 평균 | `l2.need_for_cognition` |
| C-1 | (TODO) CRT 3문항 | 정답/오답 | 정답 수 합산 | `l2.crt_correct` |
| ... | ... | ... | ... | ... |

### L3 — 동기 (조절초점)

| 문항 ID | 한국어 라벨 | 응답 형식 | 채점 처리 | 산출 파라미터 |
|---|---|---|---|---|
| L3-1 | (TODO) Promotion focus | 7점 척도 × N문항 | 평균 | `l3.promotion` |
| L3-2 | (TODO) Prevention focus | 7점 척도 × N문항 | 평균 | `l3.prevention` |
| L3-3 | (TODO) 미니멀리즘 | 7점 척도 | 평균 | `l3.minimalism` |
| ... | ... | ... | ... | ... |

### L4 — 사회적 영향

| 문항 ID | 한국어 라벨 | 응답 형식 | 채점 처리 | 산출 파라미터 |
|---|---|---|---|---|
| L4-1 | (TODO) Self-Monitoring | 5점 척도 × N문항 | 평균 + 역채점 | `l4.self_monitoring` |
| L4-2 | (TODO) Collectivism | 7점 척도 | 평균 | `l4.collectivism` |
| L4-3 | (TODO) IRI 공감도 | 5점 척도 × 4 sub-scale | sub-scale 별 평균 | `l4.empathy_*` |
| ... | ... | ... | ... | ... |

### L5 — 가치 (자기/타인지향)

| 문항 ID | 한국어 라벨 | 응답 형식 | 채점 처리 | 산출 파라미터 |
|---|---|---|---|---|
| L5-1 | (TODO) Schwartz Values (Self-Direction) | 9점 척도 | 평균 | `l5.self_direction` |
| L5-2 | (TODO) Schwartz Values (Benevolence) | 9점 척도 | 평균 | `l5.benevolence` |
| L5-3 | (TODO) 환경 가치 | 5점 척도 | 평균 | `l5.environment` |
| ... | ... | ... | ... | ... |

### L6 — 시간 지향

| 문항 ID | 한국어 라벨 | 응답 형식 | 채점 처리 | 산출 파라미터 |
|---|---|---|---|---|
| L6-1 | (TODO) 할인율 (지금 vs 6주 후) | 금액 선택 | 연환산 할인율 | `l6.discount_rate_annual` |
| L6-2 | (TODO) 현재 편향 β | 시간점 비교 | β 추정 | `l6.present_bias_beta` |
| L6-3 | (TODO) 성실성(Big5) | 5점 척도 × N문항 | 평균 + 역채점 | `l6.conscientiousness` |
| ... | ... | ... | ... | ... |

### 정성 그룹

| 문항 ID | 한국어 라벨 | 응답 형식 | 처리 | 저장 위치 |
|---|---|---|---|---|
| Q-1 | (TODO) 실제 자기 서술 | 자유응답 | 그대로 보존 (한국어) | `scratch.self_actual` |
| Q-2 | (TODO) 이상적 자기 (aspire) | 자유응답 | 그대로 보존 | `scratch.self_aspire` |
| Q-3 | (TODO) 당위적 자기 (ought) | 자유응답 | 그대로 보존 | `scratch.self_ought` |
| Q-4 | (TODO) 독재자 게임 사고 | 자유응답 | 그대로 보존 | `scratch.dictator_reasoning` |

### 능력치 (Ability)

| 문항 ID | 한국어 라벨 | 응답 형식 | 채점 처리 | 산출 파라미터 |
|---|---|---|---|---|
| C-2 | (TODO) 금융 이해력 | 정답/오답 × N문항 | 정답 수 | `ability.financial_literacy` |
| C-3 | (TODO) 수리 능력 | 정답/오답 × N문항 | 정답 수 | `ability.numeracy` |

### 인구통계 (Demographics)

| 문항 ID | 한국어 라벨 | 응답 형식 | 저장 위치 |
|---|---|---|---|
| D-age | (TODO) 연령대 | 범주형 | `scratch.age_range` |
| D-gender | (TODO) 성별 | 범주형 | `scratch.gender` |
| D-occupation | (TODO) 직업 | 범주형 | `scratch.occupation` |
| D-region | (TODO) 거주 지역 | 범주형 | `scratch.region` |
| D-education | (TODO) 학력 | 범주형 | `scratch.education` |
| ... | ... | ... | ... |

---

## 작성 절차 (Phase 2 진입 시)

1. `Twin2K500_KR_Localized_v1_1.pdf` 전체 문항을 추출 (수작업 또는 PDF parser).
2. 각 문항을 본 표의 7개 그룹(L1~L6 + 정성 + Ability + Demographics) 중 하나에 배정.
3. 채점 공식이 있는 문항은 `backend/scoring/` 의 함수 이름으로 매핑 명시.
4. 각 행에 대응하는 `persona_params` JSONB 키를 결정 (`l1.risk_aversion`, `l6.conscientiousness` 등).
5. 모호한 문항(2개 그룹에 걸치는 경우) 은 본 문서의 [§매핑 의사결정 로그] 섹션에 사유 기록 + ADR 참조.
6. 본 표 작성 완료 후 `backend/lenses/mapping.py` 의 코드 상수와 cross-check.

## 매핑 의사결정 로그 (TODO)

> 모호한 문항을 어느 그룹에 넣을지 결정한 사유를 시간순으로 기록. 예:
>
> - 2026-XX-XX: L3-7 미니멀리즘은 L3(동기)와 L5(가치) 양쪽에 가깝지만, 측정 도구(척도)가 동기 이론에 기반하므로 L3 으로 분류.

## 관련

- [ADR-0002 — 6-Lens 카테고리 분할](./adr/0002-six-lens-categorization.md)
- [PRD.md §4.1.1](./PRD.md)
- [DATA_MODEL.md — `agents.persona_params`](./DATA_MODEL.md)
- 원자료 PDF: `Twin2K500_KR_Localized_v1_1.pdf` (사용자 로컬 디스크, 외부 위치)
