# Product Requirements — Ditto

> 소비자를 가장 가까운 곳에 두고 대화하고 회의하며 인사이트를 얻는 **리서치 플랫폼**.

## 1. 서비스 개요

### 1.1 서비스명

**Ditto**.

### 1.2 서비스 컨셉

단발성 설문/인터뷰의 한계를 넘어, 응답 데이터를 **에이전트로 보존**하고 **1:1 대화 + FGI** 를 통해 지속적으로 성장시켜 가며 **심층 인사이트**를 발굴한다.

### 1.3 데이터 베이스

- **시범 단계 (Phase 2~5):** Twin-2K-500 한국어 로컬라이즈 v1.1 (`Twin2K500_KR_Localized_v1_1.pdf`) — 30명으로 시작, 이후 확장.
- **v1.0 출시 (Phase 6):** 사용자 자체 Survey 응답 → 6-Lens 매핑 → 에이전트 적재.

## 2. 타겟 사용자

자신의 서비스 유저들에 대한 리서치를 단발성 설문/인터뷰가 아닌, **에이전트로 저장하고 1:1로 대화하거나 FGI(Focus Group Interview)를 통해 지속적으로 자신의 맥락에 맞춰 성장시켜가며 인사이트를 얻고 싶은 스타트업·기업** (PO, UX 리서처, 마케터).

## 3. 사용자 흐름 (요약)

```
1. 초기 정보 입력 (Survey/Interview 질문 생성용)        ← v1.0 Phase 6
2. 질문 생성 + 배포 링크 발급                          ← v1.0 Phase 6
3. 설문 실시 (자체 풀 또는 외부)                       ← v1.0 Phase 6
4. 응답 → 6-Lens 매핑 → 에이전트 생성
5. 1:1 대화 또는 FGI 로 인사이트 도출
6. 대화·회의 누적 → 에이전트 메모리 성장
7. 성장한 에이전트 → 더 고품질의 인사이트
```

**MVP (Phase 2~5):** 1, 2, 3 단계는 Twin-2K-500 한국어 30명을 가짜 Survey 결과로 주입하여 우회하고, **4~7 단계만 검증**한다.

## 4. 핵심 기능

### 4.1 에이전트 생성 — 6-Lens 데이터 구조화 + Hybrid Persona Prompt

응답 데이터(234문항 등)를 다음 4개 Layer 로 가공한다.

#### 4.1.1 Raw Data Layer — 6-Lens 카테고리 분할

Twin-2K-500 의 234문항을 다음 카테고리로 그룹화. 자세한 매핑은 [`6-LENS_MAPPING.md`](./6-LENS_MAPPING.md) 참조.

| Lens | 영역 | 핵심 척도 |
|---|---|---|
| **L1 경제적 합리성** | 위험·손실 회피, 심적 회계, 소비 습관 | 위험 회피 점수, 손실 회피 비율, 심적 회계 분리도, 절약 성향 |
| **L2 의사결정 스타일** | 극대화 성향, 인지 욕구, 인지 반사 | Maximization Scale, Need for Cognition, CRT 정답 수 |
| **L3 동기 (조절초점)** | 향상/예방 초점, 미니멀리즘 | Promotion vs Prevention, 미니멀리즘 척도 |
| **L4 사회적 영향** | 자기 감시, 집단주의, 공감도, 정책 찬반 | Self-Monitoring, Collectivism, IRI 공감도 |
| **L5 가치 (자기/타인지향)** | 자기지향 / 타인지향 가치, 환경 가치 | Schwartz Values, 환경의식 |
| **L6 시간 지향** | 할인율, 현재 편향, 성실성 | 할인율(연환산), 현재 편향 β, 성실성(Big5) |
| **정성** | 실제 자기·이상적 자기·당위적 자기 + 독재자 게임 사고 | self_actual, self_aspire, self_ought, dictator_reasoning |

#### 4.1.2 Scoring Layer — 정량적 지표 산출

객관식 응답에 채점 공식을 적용하여 **에이전트 성격 파라미터**를 생성.

- **역채점 처리:** 성실성·인지 욕구 등 역방향 문항을 `(max + 1 - 응답)` 으로 변환.
- **경제 수치화:** L1-1 위험 회피, L6-1 할인율 문항에서 확실성 등가(CE) 와 연환산율 계산.
- **능력치 산출:** 금융 이해력(C-2) + 수리 능력(C-3) 정답 수 합산 → 지식 수준 파라미터.

산출 결과 = `Agent.persona_params` JSONB. 예:

```json
{
  "l1": { "risk_aversion": 0.9, "loss_aversion_ratio": 2.3, "ce": 4200 },
  "l2": { "maximization": 5.2, "need_for_cognition": 4.8, "crt_correct": 2 },
  "l3": { "promotion": 0.7, "prevention": 0.4, "minimalism": 3.1 },
  "l4": { "self_monitoring": 0.6, "collectivism": 5.5, "empathy": 4.2 },
  "l5": { "self_direction": 5.8, "benevolence": 4.9, "environment": 0.8 },
  "l6": { "discount_rate_annual": 0.18, "present_bias_beta": 0.7, "conscientiousness": 0.65 },
  "ability": { "financial_literacy": 4, "numeracy": 3 }
}
```

#### 4.1.3 Persona Layer — Hybrid Prompt 합성

수치 가이드 + 원문 가이드 + 제약 사항을 시스템 프롬프트로 조립. 시스템 프롬프트 ≤ 8k tokens (Lost-in-the-middle 회피).

```
[수치 기반 가이드]
당신은 위험 회피 점수가 0.9로 매우 높으며, 새로운 시도보다 안정을 추구합니다.
극대화 성향이 5.2점(7점 만점)으로 평균 이상이라, 결정 전에 가능한 옵션을 충분히 비교합니다.
연환산 할인율 18%로 미래의 큰 보상보다 가까운 작은 보상을 약간 선호합니다.

[원문 기반 가이드]
당신은 스스로를 다음과 같이 정의합니다:
"<self_actual 원문>"
당신이 이상적으로 되고 싶은 모습:
"<self_aspire 원문>"

[제약 사항]
1. 모든 답변은 위 성향과 당신이 직접 작성한 사고 방식에 근거합니다.
2. 데이터에 없는 상세는 추측하지 말고 "잘 모르겠다"고 답합니다.
3. 답변 끝에 [[CITE: <카테고리,...> | CONF: direct|inferred|guess|unknown]] 마커를 출력합니다.
```

#### 4.1.4 Evaluation Layer — V1/V4/V5 매핑

| 평가 단계 | 측정 항목 | 활용 데이터 |
|---|---|---|
| **Identity (S2)** | V1 응답 동기화 | 원본 설문지 234문항 + 실제 응답값 |
| **Logic (S3)** | V4 인격 자연스러움 | 전체 페르소나 프로필 + 에이전트 답변 |
| **Logic (S3)** | V5 상황 대응 일관성 | L1/L6 수치 + 반사실적(CF) 변형 질문 세트 |

### 4.2 에이전트 성능 평가 대시보드

대시보드 = **Identity Section** + **Logic Section** 두 영역.

#### 4.2.1 Identity Section — 정체성 검증

에이전트가 타겟의 프로필·과거 발언·취향 등 **정적 데이터(Fact)** 를 얼마나 완벽히 복제했는지 평가.

- **V1 응답 동기화율 (Response Sync)** — 인터뷰 원문 답변을 보지 않은 상태에서 동일 질문에 답하게 한 뒤, 원문과의 의미론적 유사도(cosine similarity) 측정.
- **V2 모델 신뢰도 (Model Stability)** — GPT-4o 와 Claude 3.5 등 서로 다른 LLM 에 동일한 페르소나 주입 후, 응답의 일치 여부로 모델 편향 제거 정도 측정.
- **V3 페르소나 독립성 (Persona Diversity)** — 전체 페르소나 간 응답 거리 계산. AI 가 평균적인 답변만 내놓는 모드 붕괴(mode collapse)가 없는지 검증.

#### 4.2.2 Logic Section — 사고방식 검증

타겟의 **의사결정 프로세스(Reasoning)** 와 가치관을 복제하여 새로운 상황에서도 그 사람처럼 판단하는지 평가.

- **V4 인격 자연스러움 (Humanity Score)** — Judge LLM (별도 고성능 모델) 이 페르소나 프로필을 바탕으로 에이전트의 답변 논리를 분석. 실제 사람이 할법한 자연스러운 추론인지 채점 (1~5).
- **V5 상황 대응 일관성 (Decision Reasoning)** — 반사실적 질문(CF) 으로 상황 변화에 따른 답변의 벡터 변화량(Δ) 측정. 민감도 높은 페르소나(L1 위험 회피 高 등)일수록 큰 Δ 가 나와야 논리적 일관성이 있다고 판단.

자세한 채점 공식·임계값·자극 세트는 [`EVAL_SPEC.md`](./EVAL_SPEC.md).

### 4.3 자연스러운 1:1 대화

에이전트와 사용자 간 1:1 대화. SSE(Server-Sent Events) 기반 실시간 토큰 스트리밍.

#### 수용 기준

- 메시지 송수신 응답 시간 < 3초 (첫 토큰 기준).
- 대화 종료 시 요약본이 `Agent.memories(source='conversation')` 에 자동 적재 → 다음 대화에 retrieval 컨텍스트로 사용.
- 답변 끝마다 인용 카테고리 + 신뢰도 시각화 (V1 입증 인프라 재활용).
- 채팅 히스토리는 DB 영속화 (`Conversation` + `Turn` 테이블) — 게스트 모드 없음, 인증 필수.

### 4.4 FGI (Focus Group Interview)

다자 에이전트 회의. **사용자가 토론에 개입할 수 있다** (BDML-FGI 와의 핵심 차이).

#### 수용 기준

- 모더레이터가 LangGraph 상태머신으로 라운드 진행.
- 매 라운드 종료 후 사용자 개입 hook — 사용자가 발언 입력 시 다음 라운드 시작 전에 메시지로 삽입.
- 사용자가 입력하지 않으면 자동으로 다음 라운드 진행.
- FGI 종료 시 회의록 자동 생성 + 참여 에이전트 모두에게 메모리 업데이트 (`source='fgi'`).
- 텍스트 기반만 지원 (음성 인터페이스 비범위).

## 5. MVP (Phase 2~5) 집중 영역

> **가정:** 에이전트의 재료가 되는 설문/인터뷰는 미리 확보 (Twin-2K-500 한국어 30명).
> **집중:** 4.1 에이전트 생성 + 4.2 평가 대시보드 + 4.3 1:1 대화 + 4.4 FGI.

### 5.1 단계별 산출물

| Phase | 산출물 | 핵심 검증 |
|---|---|---|
| **Phase 2** | 6-Lens 매핑 + Scoring Engine + Hybrid Prompt + Twin v2 적재 30명 | Smoke: 30명이 `agents` 테이블 적재, persona_params/full_prompt 정상 |
| **Phase 3** | 1:1 대화 SSE + V1 응답 동기화율 + 게이지 대시보드 | 트윈 1명에게 원본 5문항 → 평균 cosine sim ≥ 0.6 (목표 ≥ 0.8) |
| **Phase 4** | FGI + 사용자 개입 hook + V4 인격 자연스러움 + 레이더 차트 | 3명 FGI + 사용자 1회 개입 정상, V4 평균 ≥ 3.5/5 |
| **Phase 5** | V2 모델 신뢰도 (Claude 추가) + V3 페르소나 독립성 + V5 반사실적 + 5축 대시보드 | 5축 모두 채워진 EvaluationSnapshot 1세트 생성 |

### 5.2 비범위 (MVP)

- Survey 질문 생성·배포·응답 수집 (Phase 6 에서 도입).
- 에이전트 그룹 자동 추천 (현재는 사용자가 명시 선택).
- 다중 워크스페이스 / 조직 단위 권한 모델 (v1.1).
- 음성/영상 인터페이스.
- 다국어 (한국어 전용).

## 6. 전역 수용 기준

- 인증 미통과 사용자는 ResearchProject 페이지에 접근 불가 (`AuthGuard`).
- 프로젝트 자산(Survey/Agents/Conversations/FGISessions) 은 sessionStorage(`ProjectContext`) 로 즉시 전환 + DB 영속화.
- 토큰 사용량은 `ActivityLog` 에 기록되어 관리자가 `/api/usage/*` 로 조회 가능.
- 평가 점수(V1~V5) 는 `EvaluationSnapshot` 에 시계열로 저장되어 에이전트 성장 추이 확인 가능.
- 모든 LLM 호출은 사용자 워크스페이스 단위로 비용 집계 (v1.1).

## 7. 비범위 (전역)

- 음성·영상 채팅.
- PDF/DOCX 내보내기 (회의록은 Markdown 만 지원).
- 다국어 (한국어 전용).
- 실시간 동시 편집 (단일 사용자 가정).

## 관련 문서

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — 모듈 경계, 데이터 흐름, 외부 의존성.
- [`DATA_MODEL.md`](./DATA_MODEL.md) — DB 스키마, 마이그레이션.
- [`api-spec.md`](./api-spec.md) — 엔드포인트 명세.
- [`EVAL_SPEC.md`](./EVAL_SPEC.md) — V1~V5 평가 정의·채점·자극 세트.
- [`6-LENS_MAPPING.md`](./6-LENS_MAPPING.md) — Twin-2K-500 234문항 → L1~L6 매핑.
- [`adr/`](./adr/) — 아키텍처 결정 기록.
- [`plans/active/0001-archive-and-bootstrap-ditto.md`](./plans/active/0001-archive-and-bootstrap-ditto.md) — 마이그레이션 plan.
