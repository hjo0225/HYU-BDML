# 6-Lens Mapping — Twin-2K-500 한국어 v1.1

> **상태: COMPLETE (Phase 2 — 2026-05-07 AI 분석 완료).**
> 원본: `Twin2K500_KR_Localized_v1_1.pdf` (28개 척도 · 약 234문항)
>
> 본 문서는 `backend/lenses/mapping.py` 의 단일 진실 공급원(SSOT). 매핑이 바뀌면 이 문서 먼저 갱신 후 코드 수정.

## Lens 정의 요약

| Lens | 영역 | 핵심 척도 | 척도 수 | 문항 수 |
|---|---|---|---|---|
| **L1** 경제적 합리성 | 위험·손실 회피, 심적 회계, 소비 습관 | Risk/Loss Aversion, Mental Accounting, Tightwad-Spendthrift | 6 | 17 |
| **L2** 의사결정 스타일 | 극대화 성향, 인지 종결·욕구, 인지 반사 | Maximization, Need for Closure, NFC, CRT | 4 | 43 |
| **L3** 동기 구조 | 조절초점, 가치(자기/타인), 독특성, 자기 서술 | Regulatory Focus, Agentic/Communal Values, NFU, Selves Q | 4 | 49 |
| **L4** 사회적 영향 | 자기 감시, 집단주의, 공감, 정책 찬반, 게임 | Self-Monitoring, Individualism, Social Desirability, Empathy, FC, Dictator | 6 | 83 |
| **L5** 가치 사슬 | 소비자 미니멀리즘, 친환경 가치 | Minimalism, Green Values | 2 | 18 |
| **L6** 시간 지향 | 할인율, 현재 편향, 성실성 | Discount Rate, Present Bias, Conscientiousness | 3 | 14 |
| **통제 (C)** | 인구통계, 금융 이해력, 수리 능력 | Demographics, Financial Literacy, Numeracy | 3 | 30 |
| **합계** | | | **28** | **254** |

> 주: L3-2 (Agentic vs Communal Values 24항목)은 L5 가치 사슬에서 공유 사용 (별도 측정 없음).
> 정성 응답(Selves Q · Dictator Thought Listing)은 `qualitative.*` 에 저장.

---

## L1 — 경제적 합리성 (Economic Rationality)

총 6개 척도 · 17문항. 기반: Prospect Theory (Kahneman & Tversky) + Mental Accounting (Thaler).

| 척도 ID | 한국어 명칭 | 문항 수 | 응답 형식 | 채점 공식 | `persona_params` 키 | 입력 스키마 키 |
|---|---|---|---|---|---|---|
| **L1-1** | 위험 회피 (Risk Aversion) | 3 | MPL (이분 선택 × 14행 × 3셋) | 각 셋에서 우측 처음 선호한 최저 x = CE. `risk_aversion = (EV - CE) / EV`. 3문항 평균. | `l1.risk_aversion`, `l1.ce_q1`, `l1.ce_q2`, `l1.ce_q3` | `L1-1.Q1.row_first_certain`, `L1-1.Q2.row_first_certain`, `L1-1.Q3.row_first_certain` (정수, 해당 x값) |
| **L1-2** | 손실 회피 (Loss Aversion) | 4 | MPL 손실 영역 3셋 + 혼합 복권 1셋 | Q1-Q3: 손실 영역 CE 산출. Q4: x_gain 처음 수락한 값으로 λ = x_gain / 8000 추정. 3쌍 평균. | `l1.loss_aversion_lambda` | `L1-2.Q1.row_first_certain`, `L1-2.Q2.row_first_certain`, `L1-2.Q3.row_first_certain`, `L1-2.Q4.row_first_positive` (정수) |
| **L1-3** | 심적 회계 (Mental Accounting) | 4 | 이분 선택 (A or B) | 예측 답(Q1=A, Q2=A, Q3=B, Q4=B)과 일치 개수 / 4 → 비율. | `l1.mental_accounting` | `L1-3.Q1`, `L1-3.Q2`, `L1-3.Q3`, `L1-3.Q4` (문자열 "A" or "B") |
| **L1-4** | 구두쇠-낭비벽 (Tightwad-Spendthrift) | 4 | Q1: 11점 / Q2a·Q2b·Q3: 5점 | 4문항 합산(이론 범위 4~26). Q2b·Q3 역채점(max+1−x). | `l1.tightwad_spendthrift` | `L1-4.Q1` (1-11), `L1-4.Q2a` (1-5), `L1-4.Q2b` (1-5, 역채점), `L1-4.Q3` (1-5, 역채점) |
| **L1-5** | 프레이밍 문제 (Framing) | 1 | 6점 A/B 선호 (랜덤 이득/손실 프레임 배정) | 조건별 A선호(1~3) vs B선호(4~6). Framing effect = condition별 비교용. | `l1.framing_condition`, `l1.framing_response` | `L1-5.Q1.condition` ("gain" or "loss"), `L1-5.Q1.response` (1-6) |
| **L1-6** | 절대 vs 상대 절약 (Savings) | 1 | 이분 (예/아니오, 랜덤 계산기/재킷 조건 배정) | 조건(큰%=계산기, 작은%=재킷)별 이동 여부. | `l1.savings_condition`, `l1.savings_response` | `L1-6.Q1.condition` ("calculator" or "jacket"), `L1-6.Q1.response` ("yes" or "no") |

---

## L2 — 의사결정 스타일 (Decision-Making Style)

총 4개 척도 · 43문항.

| 척도 ID | 한국어 명칭 | 문항 수 | 응답 형식 | 채점 공식 | `persona_params` 키 | 입력 스키마 키 |
|---|---|---|---|---|---|---|
| **L2-1** | 극대화 척도 (Maximization Scale) | 6 | 5점 Likert | 6항목 평균 | `l2.maximization` | `L2-1.Q1` ~ `L2-1.Q6` (1-5) |
| **L2-2** | 인지적 종결 욕구 (Need for Closure) | 15 | 5점 Likert | 15항목 평균 | `l2.need_for_closure` | `L2-2.Q1` ~ `L2-2.Q15` (1-5) |
| **L2-3** | 인지 욕구 (Need for Cognition) | 18 | 5점 Likert (역채점: 3,4,5,7,8,9,12,16,17) | 역채점 후 18항목 평균 | `l2.need_for_cognition` | `L2-3.Q1` ~ `L2-3.Q18` (1-5) |
| **L2-4** | 인지 반사 검사 (CRT) | 4 | 주관식 (한국어/숫자) | 정답 수 (0~4). 정답: Q1=수아, Q2=0, Q3=2, Q4=8 | `l2.crt_score` | `L2-4.Q1`, `L2-4.Q2`, `L2-4.Q3`, `L2-4.Q4` (문자열 또는 숫자) |

---

## L3 — 동기 구조 (Motivation Structure)

총 4개 척도 · 49문항.

| 척도 ID | 한국어 명칭 | 문항 수 | 응답 형식 | 채점 공식 | `persona_params` 키 | 입력 스키마 키 |
|---|---|---|---|---|---|---|
| **L3-1** | 조절초점 척도 (Regulatory Focus) | 10 | 7점 Likert | 10항목 평균 | `l3.regulatory_focus` | `L3-1.Q1` ~ `L3-1.Q10` (1-7) |
| **L3-2** | 자기지향/타인지향 가치 (Agentic vs Communal) | 24 | 9점 (중요도 평정) | Agency = 항목 1,2,4,6,8,10,13,15,18,20,22,24 평균. Communion = 항목 3,5,7,9,11,12,14,16,17,19,21,23 평균. *(L5와 공유 — 한 번만 측정)* | `l3.agency`, `l3.communion` | `L3-2.V1` ~ `L3-2.V24` (1-9) |
| **L3-3** | 독특성 욕구 (Need for Uniqueness) | 12 | 5점 Likert | 12항목 평균 | `l3.need_for_uniqueness` | `L3-3.Q1` ~ `L3-3.Q12` (1-5) |
| **L3-4** | 자기 차이 질문 (Selves Questionnaire) | 3 | 자유응답 (최소 3문장) | 정성 텍스트 저장. 정량화는 후속 분석에서. | *(없음 — qualitative 저장)* | `L3-4.Q1` (self_aspire), `L3-4.Q2` (self_ought), `L3-4.Q3` (self_actual) |

---

## L4 — 사회적 영향 (Social Influence)

총 6개 척도 · 83문항.

| 척도 ID | 한국어 명칭 | 문항 수 | 응답 형식 | 채점 공식 | `persona_params` 키 | 입력 스키마 키 |
|---|---|---|---|---|---|---|
| **L4-1** | 자기 감시 (Self-Monitoring) | 13 | 6점 (0~5). 역채점: Q4, Q6 | 역채점 후 13항목 평균 | `l4.self_monitoring` | `L4-1.Q1` ~ `L4-1.Q13` (0-5) |
| **L4-2** | 개인주의 vs 집단주의 | 16 | 5점 Likert | 수평개인Q1-4 평균, 수직개인Q5-8 평균, 수평집단Q9-12 평균, 수직집단Q13-16 평균 | `l4.horizontal_individualism`, `l4.vertical_individualism`, `l4.horizontal_collectivism`, `l4.vertical_collectivism` | `L4-2.Q1` ~ `L4-2.Q16` (1-5) |
| **L4-3** | 사회적 바람직성 (Social Desirability) | 13 | 이분 (TRUE/FALSE) | TRUE on Q5,7,9,10,13 + FALSE on Q1,2,3,4,6,8,11,12 합산 (0~13) | `l4.social_desirability` | `L4-3.Q1` ~ `L4-3.Q13` ("TRUE" or "FALSE") |
| **L4-4** | 공감 (Empathy — BES-A) | 20 | 5점 Likert. 역채점: Q1,6,7,8,13,18,19,20 | 역채점 후 20항목 평균 | `l4.empathy` | `L4-4.Q1` ~ `L4-4.Q20` (1-5) |
| **L4-5** | 잘못된 합의 (False Consensus) | 10+10=20 | Part1: 5점 (자기 입장). Part2: 0-100 슬라이더 (지지율 예측) | 자기 입장과 예측 지지율의 회귀 기반 FC 효과 추정. 개별 정책 입장 평균도 저장. | `l4.false_consensus_effect`, `l4.policy_stance_avg` | `L4-5.P1.Q1`~`L4-5.P1.Q10` (1-5), `L4-5.P2.Q1`~`L4-5.P2.Q10` (0-100) |
| **L4-6** | 독재자 게임 (Dictator Game) | 1 + 선택응답 | 5개 선택지 (0/1000/2000/4000/5000원) + 자유응답 Thought Listing | dictator_send = 보낸 금액. dictator_send_ratio = 보낸 금액 / 5000. | `l4.dictator_send`, `l4.dictator_send_ratio` | `L4-6.Q1` (정수: 0, 1000, 2000, 4000, 5000). Thought listing → `qualitative.dictator_reasoning` |

---

## L5 — 가치 사슬 (Means-End Chain)

총 2개 척도 · 18문항 (+ L3-2 공유 24항목 → 별도 측정 없음).

| 척도 ID | 한국어 명칭 | 문항 수 | 응답 형식 | 채점 공식 | `persona_params` 키 | 입력 스키마 키 |
|---|---|---|---|---|---|---|
| **L5-1** | 소비자 미니멀리즘 (Consumer Minimalism) | 12 | 5점 Likert | 12항목 평균 | `l5.minimalism` | `L5-1.Q1` ~ `L5-1.Q12` (1-5) |
| **L5-2** | 친환경 가치 (Green Values) | 6 | 5점 Likert | 6항목 평균 | `l5.green_values` | `L5-2.Q1` ~ `L5-2.Q6` (1-5) |

> L3-2 (Agentic vs Communal Values)는 L5 가치 사슬의 궁극적 가치 측정으로 공유. L3 측정값 (`l3.agency`, `l3.communion`)을 L5 분석에서 직접 참조.

---

## L6 — 시간 지향 (Time Orientation)

총 3개 척도 · 14문항. 기반: Hyperbolic Discounting + Construal Level Theory.

| 척도 ID | 한국어 명칭 | 문항 수 | 응답 형식 | 채점 공식 | `persona_params` 키 | 입력 스키마 키 |
|---|---|---|---|---|---|---|
| **L6-1** | 할인율 (Discount Rate) | 3 | MPL (이분 선택, 1주·1주·2주 차이) | 처음 우측(빠른 금액 x) 선호한 최저 x = CE. 연환산: Q1·Q2: `(Y/x)^(52/1)−1`, Q3: `(Y/x)^(52/2)−1`. 3문항 평균. | `l6.discount_rate_annual` | `L6-1.Q1.row_first_certain`, `L6-1.Q2.row_first_certain`, `L6-1.Q3.row_first_certain` (정수) |
| **L6-2** | 현재 편향 (Present Bias) | 3 | MPL (좌측=미래 큰 금액, 우측=지금 작은 금액) | 각 Q에 대해 z=L6-1 CE, x=L6-2 CE, Y=좌측 큰 금액. β=(x−z)/Y. 3쌍 평균. | `l6.present_bias_beta` | `L6-2.Q1.row_first_certain`, `L6-2.Q2.row_first_certain`, `L6-2.Q3.row_first_certain` (정수) |
| **L6-3** | 성실성 (Conscientiousness) | 8 | 9점. 역채점: Q5,6,7,8 | 1~4번 중 응답>5 개수 + 5~8번 중 응답<5 개수의 합 (이론 범위 0~8) | `l6.conscientiousness` | `L6-3.Q1` ~ `L6-3.Q8` (1-9) |

---

## 통제 변수 (Control Variables)

총 3개 척도 · 30문항.

### C-1 — 인구통계 (Demographics) — 14 문항

저장 위치: `demographics.*` (별도 JSON 필드, `persona_params` 아님).

| 문항 | 한국어 라벨 | 응답 형식 | 저장 키 |
|---|---|---|---|
| C-1.Q1 | 거주 지역 (광역시도) | 범주형 17개 | `demographics.region` |
| C-1.Q2 | 출생 시 부여된 성별 | 남성/여성 | `demographics.gender` |
| C-1.Q3 | 연령대 | 범주형 6개 (18-29, 30-39, …) | `demographics.age_range` |
| C-1.Q4 | 최종 학력 | 범주형 7개 | `demographics.education` |
| C-1.Q5 | 국적/인종 | 범주형 3개 | `demographics.nationality` |
| C-1.Q6 | 체류 자격 (외국인) | 범주형 7개 | `demographics.visa_status` |
| C-1.Q7 | 결혼 상태 | 범주형 5개 | `demographics.marital_status` |
| C-1.Q8 | 현재 종교 | 범주형 7개 | `demographics.religion` |
| C-1.Q9 | 종교 활동 빈도 | 범주형 6개 | `demographics.religion_frequency` |
| C-1.Q10 | 지지 정당 | 범주형 7개 | `demographics.political_party` |
| C-1.Q11 | 월평균 가구 소득 | 범주형 7개 | `demographics.household_income` |
| C-1.Q12 | 정치 이념 자가 평가 | 5점 (진보~보수) | `demographics.political_views` |
| C-1.Q13 | 가구원 수 | 범주형 5개 | `demographics.household_size` |
| C-1.Q14 | 고용 상태 | 범주형 8개 | `demographics.employment` |

### C-2 — 금융 이해력 (Financial Literacy) — 8 문항

저장 위치: `ability.financial_literacy` (정답 수 0~8).

| 문항 | 입력 키 | 정답 |
|---|---|---|
| C-2.Q1 | `C-2.Q1` | "TRUE" |
| C-2.Q2 | `C-2.Q2` | 3 (정수) |
| C-2.Q3 | `C-2.Q3` | 2 (정수) |
| C-2.Q4 | `C-2.Q4` | "TRUE" |
| C-2.Q5 | `C-2.Q5` | 2 (정수) |
| C-2.Q6 | `C-2.Q6` | 2 (정수) |
| C-2.Q7 | `C-2.Q7` | "TRUE" |
| C-2.Q8 | `C-2.Q8` | "영원히" (문자열) |

### C-3 — 수리 능력 (Numeracy) — 8 문항

저장 위치: `ability.numeracy` (정답 수 0~8).

| 문항 | 입력 키 | 정답 |
|---|---|---|
| C-3.Q1 | `C-3.Q1` | 500 |
| C-3.Q2 | `C-3.Q2` | 10 |
| C-3.Q3 | `C-3.Q3` | 20 |
| C-3.Q4 | `C-3.Q4` | 0.1 |
| C-3.Q5 | `C-3.Q5` | 100 |
| C-3.Q6 | `C-3.Q6` | 5 |
| C-3.Q7 | `C-3.Q7` | 500 |
| C-3.Q8 | `C-3.Q8` | 47 |

---

## 정성 그룹 (Qualitative)

`persona_params` 외부 별도 저장 (`qualitative.*`). 임베딩용 텍스트로 변환됨.

| 문항 ID | 한국어 라벨 | 응답 형식 | 저장 위치 |
|---|---|---|---|
| L3-4.Q1 (= 3-4 Q1) | 이상적 자기 (aspire) | 자유응답 한국어 (최소 3문장) | `qualitative.self_aspire` |
| L3-4.Q2 (= 3-4 Q2) | 의무적 자기 (ought) | 자유응답 한국어 (최소 3문장) | `qualitative.self_ought` |
| L3-4.Q3 (= 3-4 Q3) | 실제 자기 (actual) | 자유응답 한국어 (최소 3문장) | `qualitative.self_actual` |
| L4-6 Thought Listing | 독재자 게임 사고 과정 | 자유응답 (텍스트 박스 6개, 선택) | `qualitative.dictator_reasoning` |

---

## 완성된 입력 스키마 예시 (1명분)

```json
{
  "respondent_id": "kr_001",
  "collected_at": "2026-05-15T10:00:00+09:00",
  "demographics": {
    "region": "서울특별시",
    "gender": "여성",
    "age_range": "30-39",
    "education": "대학교 졸업",
    "nationality": "한국인",
    "visa_status": "해당없음(한국인)",
    "marital_status": "기혼(법적)",
    "religion": "무교(없음)",
    "religion_frequency": "전혀 안 함",
    "political_party": "무당층(지지 정당 없음)",
    "household_income": "300~500만원",
    "political_views": 3,
    "household_size": "4명",
    "employment": "정규직 임금근로자"
  },
  "responses": {
    "L1-1.Q1.row_first_certain": 2500,
    "L1-1.Q2.row_first_certain": 5000,
    "L1-1.Q3.row_first_certain": 5000,
    "L1-2.Q1.row_first_certain": 3000,
    "L1-2.Q2.row_first_certain": 6000,
    "L1-2.Q3.row_first_certain": 7000,
    "L1-2.Q4.row_first_positive": 12000,
    "L1-3.Q1": "A",
    "L1-3.Q2": "A",
    "L1-3.Q3": "B",
    "L1-3.Q4": "A",
    "L1-4.Q1": 6,
    "L1-4.Q2a": 2,
    "L1-4.Q2b": 4,
    "L1-4.Q3": 4,
    "L1-5.Q1.condition": "gain",
    "L1-5.Q1.response": 2,
    "L1-6.Q1.condition": "calculator",
    "L1-6.Q1.response": "yes",
    "L2-1.Q1": 4, "L2-1.Q2": 4, "L2-1.Q3": 3, "L2-1.Q4": 4, "L2-1.Q5": 5, "L2-1.Q6": 3,
    "L2-2.Q1": 3, "L2-2.Q2": 2, "L2-2.Q3": 4, "L2-2.Q4": 3, "L2-2.Q5": 2,
    "L2-2.Q6": 3, "L2-2.Q7": 4, "L2-2.Q8": 3, "L2-2.Q9": 2, "L2-2.Q10": 2,
    "L2-2.Q11": 2, "L2-2.Q12": 4, "L2-2.Q13": 4, "L2-2.Q14": 3, "L2-2.Q15": 2,
    "L2-3.Q1": 4, "L2-3.Q2": 4, "L2-3.Q3": 2, "L2-3.Q4": 2, "L2-3.Q5": 2,
    "L2-3.Q6": 4, "L2-3.Q7": 3, "L2-3.Q8": 2, "L2-3.Q9": 2, "L2-3.Q10": 3,
    "L2-3.Q11": 4, "L2-3.Q12": 2, "L2-3.Q13": 4, "L2-3.Q14": 3, "L2-3.Q15": 4,
    "L2-3.Q16": 3, "L2-3.Q17": 2, "L2-3.Q18": 3,
    "L2-4.Q1": "수아", "L2-4.Q2": 0, "L2-4.Q3": 2, "L2-4.Q4": 8,
    "L3-1.Q1": 6, "L3-1.Q2": 5, "L3-1.Q3": 5, "L3-1.Q4": 5,
    "L3-1.Q5": 6, "L3-1.Q6": 5, "L3-1.Q7": 6, "L3-1.Q8": 5, "L3-1.Q9": 4, "L3-1.Q10": 4,
    "L3-2.V1": 5, "L3-2.V2": 6, "L3-2.V3": 7, "L3-2.V4": 4, "L3-2.V5": 8,
    "L3-2.V6": 7, "L3-2.V7": 6, "L3-2.V8": 6, "L3-2.V9": 7, "L3-2.V10": 4,
    "L3-2.V11": 8, "L3-2.V12": 7, "L3-2.V13": 3, "L3-2.V14": 7, "L3-2.V15": 3,
    "L3-2.V16": 8, "L3-2.V17": 8, "L3-2.V18": 3, "L3-2.V19": 7, "L3-2.V20": 6,
    "L3-2.V21": 8, "L3-2.V22": 4, "L3-2.V23": 7, "L3-2.V24": 2,
    "L3-3.Q1": 3, "L3-3.Q2": 3, "L3-3.Q3": 3, "L3-3.Q4": 3,
    "L3-3.Q5": 2, "L3-3.Q6": 2, "L3-3.Q7": 2, "L3-3.Q8": 2,
    "L3-3.Q9": 2, "L3-3.Q10": 2, "L3-3.Q11": 2, "L3-3.Q12": 2,
    "L4-1.Q1": 4, "L4-1.Q2": 3, "L4-1.Q3": 4, "L4-1.Q4": 1,
    "L4-1.Q5": 3, "L4-1.Q6": 1, "L4-1.Q7": 4, "L4-1.Q8": 3,
    "L4-1.Q9": 3, "L4-1.Q10": 3, "L4-1.Q11": 3, "L4-1.Q12": 3, "L4-1.Q13": 3,
    "L4-2.Q1": 4, "L4-2.Q2": 4, "L4-2.Q3": 4, "L4-2.Q4": 4,
    "L4-2.Q5": 3, "L4-2.Q6": 2, "L4-2.Q7": 3, "L4-2.Q8": 3,
    "L4-2.Q9": 4, "L4-2.Q10": 4, "L4-2.Q11": 4, "L4-2.Q12": 4,
    "L4-2.Q13": 4, "L4-2.Q14": 5, "L4-2.Q15": 4, "L4-2.Q16": 4,
    "L4-3.Q1": "TRUE", "L4-3.Q2": "TRUE", "L4-3.Q3": "TRUE", "L4-3.Q4": "TRUE",
    "L4-3.Q5": "TRUE", "L4-3.Q6": "FALSE", "L4-3.Q7": "TRUE", "L4-3.Q8": "FALSE",
    "L4-3.Q9": "TRUE", "L4-3.Q10": "TRUE", "L4-3.Q11": "FALSE", "L4-3.Q12": "FALSE", "L4-3.Q13": "TRUE",
    "L4-4.Q1": 2, "L4-4.Q2": 4, "L4-4.Q3": 4, "L4-4.Q4": 3, "L4-4.Q5": 3,
    "L4-4.Q6": 2, "L4-4.Q7": 2, "L4-4.Q8": 2, "L4-4.Q9": 4, "L4-4.Q10": 4,
    "L4-4.Q11": 4, "L4-4.Q12": 4, "L4-4.Q13": 2, "L4-4.Q14": 4, "L4-4.Q15": 3,
    "L4-4.Q16": 4, "L4-4.Q17": 3, "L4-4.Q18": 2, "L4-4.Q19": 2, "L4-4.Q20": 2,
    "L4-5.P1.Q1": 3, "L4-5.P1.Q2": 3, "L4-5.P1.Q3": 4, "L4-5.P1.Q4": 4,
    "L4-5.P1.Q5": 3, "L4-5.P1.Q6": 4, "L4-5.P1.Q7": 4, "L4-5.P1.Q8": 3,
    "L4-5.P1.Q9": 2, "L4-5.P1.Q10": 3,
    "L4-5.P2.Q1": 45, "L4-5.P2.Q2": 40, "L4-5.P2.Q3": 55, "L4-5.P2.Q4": 60,
    "L4-5.P2.Q5": 35, "L4-5.P2.Q6": 50, "L4-5.P2.Q7": 55, "L4-5.P2.Q8": 40,
    "L4-5.P2.Q9": 30, "L4-5.P2.Q10": 50,
    "L4-6.Q1": 2000,
    "L5-1.Q1": 4, "L5-1.Q2": 4, "L5-1.Q3": 4, "L5-1.Q4": 4,
    "L5-1.Q5": 3, "L5-1.Q6": 3, "L5-1.Q7": 3, "L5-1.Q8": 3,
    "L5-1.Q9": 4, "L5-1.Q10": 4, "L5-1.Q11": 4, "L5-1.Q12": 4,
    "L5-2.Q1": 4, "L5-2.Q2": 4, "L5-2.Q3": 4, "L5-2.Q4": 4, "L5-2.Q5": 4, "L5-2.Q6": 4,
    "L6-1.Q1.row_first_certain": 5000,
    "L6-1.Q2.row_first_certain": 7000,
    "L6-1.Q3.row_first_certain": 8000,
    "L6-2.Q1.row_first_certain": 5500,
    "L6-2.Q2.row_first_certain": 7500,
    "L6-2.Q3.row_first_certain": 8500,
    "L6-3.Q1": 7, "L6-3.Q2": 7, "L6-3.Q3": 7, "L6-3.Q4": 6,
    "L6-3.Q5": 3, "L6-3.Q6": 2, "L6-3.Q7": 3, "L6-3.Q8": 2,
    "C-2.Q1": "TRUE", "C-2.Q2": 3, "C-2.Q3": 2, "C-2.Q4": "TRUE",
    "C-2.Q5": 2, "C-2.Q6": 2, "C-2.Q7": "TRUE", "C-2.Q8": "영원히",
    "C-3.Q1": 500, "C-3.Q2": 10, "C-3.Q3": 20, "C-3.Q4": 0.1,
    "C-3.Q5": 100, "C-3.Q6": 5, "C-3.Q7": 500, "C-3.Q8": 47
  },
  "qualitative": {
    "self_aspire": "저는 가족과 가까이 지내면서도 경제적으로 안정된 삶을 원합니다. 직장에서는 전문성을 인정받고 싶고, 사회에 조금이라도 기여하는 사람이 되고 싶습니다. 건강하게 오래 살면서 주변 사람들에게 긍정적인 영향을 주는 삶이 이상입니다.",
    "self_ought": "부모님께 효도하고 아이를 잘 양육해야 한다고 생각합니다. 직장에서는 맡은 바 책임을 다해야 하고, 세금도 정직하게 내고 사회 규범을 지켜야 한다고 느낍니다. 가족의 생계를 책임지는 것이 저의 의무라고 생각합니다.",
    "self_actual": "저는 꼼꼼하고 책임감이 강한 편입니다. 새로운 일에 도전하기보다는 검증된 방식을 선호하고, 충동적인 소비보다 계획적인 소비를 합니다. 가족 중심적이며 주변 사람들의 감정에 민감한 편입니다.",
    "dictator_reasoning": "상대방도 필요한 게 있을 거라 생각해서 절반 이상 줬습니다. 그래도 내 몫은 챙겨야 한다고 생각했습니다."
  }
}
```

---

## 매핑 의사결정 로그

| 날짜 | 척도 | 결정 사유 |
|---|---|---|
| 2026-05-07 | L3-2 공유 | Agentic vs Communal Values 24항목은 L3(동기)와 L5(가치 사슬) 양쪽에서 이론적으로 필요. PDF가 L5에서 L3 측정값을 "공유 사용"으로 명시했으므로, L3에서 한 번만 측정하고 결과를 L5 분석에서 참조. 코드상 `l3.agency`·`l3.communion` 키를 L5 분석에서도 읽음. |
| 2026-05-07 | L3-4 → qualitative | Selves Questionnaire 3문항은 자유응답으로 `persona_params`에 수치화 불가. `qualitative.*`에 원문 보존 후 임베딩 생성. |
| 2026-05-07 | L4-5 FC 효과 | False Consensus 효과(회귀 추정)는 집단 수준 분석이 원론적이나, 개인 수준에서는 `(자기입장 - 예측지지율/20)` 편차를 대리 지표로 사용. 상세 회귀는 Phase 3 평가 시점에서 처리. |
| 2026-05-07 | L4-6 → dictator_send_ratio | 5000원 기준 비율로 정규화. 추후 금액 단위 변경에 대비. |
| 2026-05-07 | C-1 → demographics | 인구통계는 채점 대상이 아니므로 `persona_params` 외부 `demographics.*`에 별도 저장. |

---

## 검증 체크리스트 (M1 완료 기준)

- [x] 28 척도 모두 L1~L6 또는 C/Q 그룹 중 하나에 배정
- [x] 모든 행에 `persona_params` 키 또는 `qualitative.*` / `demographics.*` 저장 위치 명시
- [x] 입력 스키마 JSON 예시 1건 (kr_001)이 표의 모든 키를 채울 수 있음
- [x] 역채점 항목 명시 (L2-3, L4-1, L4-4, L6-3, L1-4)
- [x] 채점 공식 명세 완료

---

## 관련

- [ADR-0002 — 6-Lens 카테고리 분할](./adr/0002-six-lens-categorization.md)
- [PRD.md §4.1.1](./PRD.md)
- [DATA_MODEL.md — `agents.persona_params`](./DATA_MODEL.md)
- 원자료 PDF: `Twin2K500_KR_Localized_v1_1.pdf` (사용자 로컬 디스크)
