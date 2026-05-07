# Evaluation Specification — Ditto

에이전트 성능 평가 V1~V5 의 정의·채점 공식·자극 세트·임계값. 본 문서는 **수치가 어떻게 만들어지는지의 단일 진실 공급원**이다. 코드와 어긋나면 본 문서를 먼저 갱신한다.

## 0. 평가 컨셉

| Section | 측정하려는 것 | 지표 |
|---|---|---|
| **Identity** (정체성 검증) | 정적 데이터(Fact) 복제 정도 | V1 응답 동기화 · V2 모델 신뢰도 · V3 페르소나 독립성 |
| **Logic** (사고방식 검증) | 의사결정 프로세스(Reasoning) 복제 정도 | V4 인격 자연스러움 · V5 상황 대응 일관성 |

각 평가 결과 → `EvaluationSnapshot` 테이블에 시계열로 저장. 대시보드에서 V1~V5 5축 레이더 + 게이지/막대/산점도로 표시.

---

## 1. V1 응답 동기화율 (Response Sync) — Identity

### 의미
"과거 인터뷰 데이터와 얼마나 일치하는가."

### 검증 방법
1. **자극 세트:** Twin-2K-500 원본 234문항 중 정성/객관식 답변이 명확한 N개 (기본 30개) 를 평가셋으로 사용.
2. **에이전트 답변 생성:** 에이전트가 원문 답변을 보지 않은 상태에서 동일 질문에 답하게 한다.
3. **비교:** 에이전트 답변 임베딩 vs 원문 답변 임베딩 cosine similarity.

### 채점 공식
```
sync = mean( cosine(emb(agent_answer_i), emb(original_answer_i)) for i in 1..N )
```
- 임베딩 모델: OpenAI `text-embedding-3-small` (1536d).
- 객관식 응답은 텍스트 라벨로 변환 후 임베딩.

### 임계값
| 점수 | 판정 | 시각화 색상 |
|---|---|---|
| ≥ 0.80 | Excellent | `status.success` |
| 0.60~0.80 | Acceptable | `status.warning` |
| < 0.60 | Insufficient | `status.error` |

### 출력 스키마
```json
{
  "metric": "v1",
  "score": 0.84,
  "n_eval": 30,
  "by_question": [
    { "question_id": "L1-3", "agent": "...", "original": "...", "cosine": 0.87 },
    ...
  ]
}
```

---

## 2. V2 모델 신뢰도 (Model Stability) — Identity

### 의미
"AI 엔진이 바뀌어도 같은 인격을 유지하는가."

### 검증 방법
1. **자극 세트:** V1 과 동일 또는 별도 N개 질문.
2. **두 LLM 으로 답변 생성:**
   - Model A (기본): OpenAI `gpt-4o`
   - Model B (기본): Anthropic `claude-3-5-sonnet-20240620`
   - 같은 시스템 프롬프트(`agent.persona_full_prompt`) 사용.
3. **비교:** 두 모델의 답변 임베딩 cosine similarity.

### 채점 공식
```
stability = mean( cosine(emb(answer_A_i), emb(answer_B_i)) for i in 1..N )
```

### 임계값
| 점수 | 판정 |
|---|---|
| ≥ 0.85 | Stable across models |
| 0.70~0.85 | Mild model bias |
| < 0.70 | Strong model bias (페르소나가 모델에 의존적) |

### 비용 주의
- GPT-4o + Claude-3.5 양쪽 호출 = 약 2배 비용.
- 사용자 명시 트리거 또는 nightly cron 으로만 실행. 라이브 채팅에서 호출 금지.

### Open Question
- Q3 — V5 와 동일 자극 세트를 재사용할지, V2 전용 세트를 둘지: Phase 5 에서 결정.

---

## 3. V3 페르소나 독립성 (Persona Diversity) — Identity

### 의미
"30명의 인격이 서로 겹치지 않고 고유한 개성을 갖는가." 모드 붕괴(mode collapse) 검출.

### 검증 방법
1. **자극 세트:** "당신을 5문장으로 소개해주세요" 등 페르소나 차이가 드러나는 정성 질문 K개 (기본 5개).
2. 모든 에이전트 (현재 30명) 가 같은 질문에 답.
3. 각 에이전트의 답변 임베딩 평균 → 30개의 페르소나 벡터.
4. 페어와이즈 평균 거리 = `distinct` 점수.

### 채점 공식
```
distinct = mean( euclidean(persona_vec_i, persona_vec_j) for all i < j )
```

### 임계값 (실험적, Phase 5 검증 필요)
| 점수 | 판정 |
|---|---|
| ≥ 3.0 | High diversity (좋음) |
| 1.5~3.0 | Moderate |
| < 1.5 | Mode collapse 의심 (LLM 이 평균적 답변만 생성) |

> 임계값은 30명 기준 실측치를 Phase 5 에서 확정. 인원이 늘면 재계산.

### 산출물
- 30 × 30 코사인/유클리드 거리 행렬 → 대시보드 산점도 (PCA/UMAP 2D 투영).

---

## 4. V4 인격 자연스러움 (Humanity Score) — Logic

### 의미
"제3자가 보기에 기계적이지 않고 사람다운 사고를 하는가."

### 검증 방법
1. **자극 세트:** 시나리오 기반 자유응답 질문 N개 (기본 10개). 일상 의사결정 상황 (예: "이번 주말에 친구가 갑자기 등산을 가자고 했는데, 어떻게 결정할지 생각 과정을 들려주세요").
2. **에이전트 답변 생성** (스트리밍 X, 단답).
3. **Judge LLM 채점** (gpt-4o, temp=0):
   - 입력: 페르소나 프로필(persona_params 요약 + scratch.self_actual) + 에이전트 답변
   - 출력: 1~5 점 (5 = 완전히 자연스러운 사람의 추론, 1 = 기계적/일관성 없음)
   - 판정 사유 (Markdown)

### Judge 프롬프트 (요약 — `prompts/eval_judge_v4.py` 참조)
```
당신은 페르소나 프로필을 보고, 다음 답변이 그 사람의 사고로서 자연스러운지 1~5로 채점합니다.
페르소나: {persona_summary}
질문: {question}
답변: {answer}
다음 4기준으로 평가합니다:
  1. 일관성 (페르소나 성향과 모순되지 않는가)
  2. 구체성 (개인의 실제 경험 같은가)
  3. 추론 명료성 (논리 연결이 명확한가)
  4. 자연스러운 톤 (실제 사람의 말투인가)
점수: <int 1~5>
사유: <Korean Markdown>
```

### 채점 공식
```
humanity = mean( judge_score_i for i in 1..N )
```

### 임계값
| 점수 | 판정 |
|---|---|
| ≥ 4.0 | Human-like |
| 3.0~4.0 | Acceptable |
| < 3.0 | Mechanical |

---

## 5. V5 상황 대응 일관성 (Decision Reasoning) — Logic

### 의미
"환경 변화(가격, 시간 등)에도 본인의 가치관에 따라 판단하는가." 민감도가 높은 사람일수록 큰 벡터 변화를 보여야 '논리적 일관성'이 있다고 판단.

### 검증 방법
1. **자극 세트:** 반사실적(Counterfactual) 변형 질문 K쌍 (기본 15쌍). 한 쌍 = 원문 시나리오 1개 + 변형 시나리오 1개.
   - 예: L6-1 "6주 후 6,000원 받기" (원문) vs "지금 당장 5,000원이 급한 상황" (변형).
   - 예: L1-3 "10만원짜리 코트 vs 2만원짜리 셔츠 — 둘 다 5천원 할인" (원문) vs "둘 다 5만원 할인" (변형).
2. **에이전트 답변 생성:** 각 질문 쌍에 대해 답변.
3. **벡터 변화량 측정:** 원문 답변 임베딩 vs 변형 답변 임베딩 거리 Δ.
4. **일관성 검증:** Δ 가 페르소나 민감도와 상관관계 (`persona_params.l1.risk_aversion` 또는 `l6.discount_rate_annual`) 가 있어야 한다.

### 채점 공식
```
delta_i = euclidean(emb(answer_original_i), emb(answer_cf_i))
reasoning_delta = mean(delta_i for i in 1..K)

# 일관성 보조 지표 — Phase 5 에서 도입
consistency = corr(delta_i, sensitivity_i_from_persona_params)
```

### 임계값 (실험적)
| 점수 | 판정 |
|---|---|
| 0.10 ≤ Δ ≤ 0.30 | 적절한 반응성 (페르소나 민감도와 일치) |
| Δ < 0.10 | 무반응 (CF 자극을 무시) |
| Δ > 0.30 | 과반응 (일관성 결여) |

> 페르소나에 따라 적정 Δ 가 다르므로, **Phase 5 에서 페르소나별 sensitivity 를 산정한 뒤 정규화**한다.

### 자극 세트 운영
- 버전 관리: `cf_set_v1.json` (Phase 5 초기) → `cf_set_v2.json` ...
- 위치: `backend/evaluation/stimuli/cf_set_v1.json`.
- API 호출 시 `cf_set_version` 으로 버전 명시.
- **Open Question Q3:** 자극 세트를 (a) 수작업 30~50개 vs (b) LLM 자동 생성 + 검수 — Phase 5 진입 시 결정. 권장은 하이브리드 (L1/L6 핵심 10~15쌍은 수작업, 나머지 LLM 생성 + 사람 검수).

---

## 6. 종합 — Verdict 산정

평가 스냅샷에 종합 판정을 부여.

```
verdict =
  "verified_s3"  if  V1 ≥ 0.80 AND V2 ≥ 0.85 AND V4 ≥ 4.0 AND 0.10 ≤ V5 ≤ 0.30
  "partial"      if  (V1 ≥ 0.60 AND V4 ≥ 3.0) AND (above 미달 항목 있음)
  "failed"       else
```

V3 (페르소나 독립성) 는 30명 전체의 분포 지표라 단일 에이전트 verdict 에는 직접 영향 X. 단, 분포에서 "이상치(이상하게 가까운 페르소나 쌍)"인 에이전트는 대시보드에 경고 표시.

---

## 7. 시각화 매핑

| 지표 | 컴포넌트 | 위치 |
|---|---|---|
| V1 sync | `<Gauge value={sync} ... />` | 에이전트 카드, 상세 페이지 상단 |
| V2 stability | `<Gauge value={stability} ... />` | 상세 페이지 |
| V3 distinct | 산점도 (PCA 2D) | 프로젝트 대시보드 — 30명 분포 |
| V4 humanity | `<Gauge value={humanity / 5} ... />` 또는 막대 | 상세 페이지 |
| V5 reasoning_delta | 막대 차트 (페르소나별 Δ + sensitivity 비교) | 상세 페이지 |
| 종합 5축 | `<RadarChart />` | 상세 페이지 헤더 |
| Verdict | `<ScoreBadge variant=verdict>` | 카드, 헤더 inline |

자세한 컴포넌트 규칙은 [`/DESIGN.md`](../DESIGN.md) §2 참조.

---

## 8. 평가 실행 모드

| 모드 | 트리거 | 비용 | 권장 빈도 |
|---|---|---|---|
| **Quick (V1, V4)** | 사용자가 에이전트 페이지에서 "평가 실행" 클릭 | ~$0.05/agent | 임의 시점 |
| **Full (V1~V5)** | 사용자 명시 트리거 또는 nightly cron | ~$0.30/agent | 주 1회 |
| **Diversity-only (V3)** | 에이전트 풀에 변동 발생 시 자동 | ~$0.50/30명 | 월 1회 또는 적재 직후 |

---

## 9. 데이터 흐름 (요약)

```
EvaluationRun 트리거
   │
   ├─ V1: 234문항 → agent → cosine sim
   ├─ V2: 동일 질문 → GPT-4o + Claude-3.5 → cosine sim
   ├─ V3: 5 정성 질문 → 30 agents → 페어와이즈 거리
   ├─ V4: 10 시나리오 → agent → Judge(gpt-4o) → 1~5점
   └─ V5: 15 CF 쌍 → agent → 답변 Δ
   │
   ▼
EvaluationSnapshot 저장 (identity_stats, logic_stats, verdict)
   │
   ▼
GET /api/agents/{id}/evaluations/latest → 대시보드
```

---

## 10. 향후 검토

- **에이전트 성장 검증:** V1 점수가 대화·FGI 누적 후에도 유지되는지 (특히 V3 distinct 가 떨어지지 않는지) 회기적으로 측정.
- **메모리 vs persona_params 의 영향력 분리:** 답변에서 retrieval 메모리가 차지한 비중을 측정해서, "페르소나 정체성"과 "메모리 영향" 을 구분하는 지표 추가.
- **사용자 피드백 통합:** 사용자가 답변을 thumbs-up/down 했을 때, 그 신호가 V4 Judge 점수와 얼마나 상관 있는지 측정.

## 관련 문서
- [PRD.md §4.2](./PRD.md) — 평가 대시보드 요구사항
- [ARCHITECTURE.md](./ARCHITECTURE.md) — 평가 엔진 모듈 위치
- [DATA_MODEL.md](./DATA_MODEL.md) — `evaluation_snapshots` 테이블
- [api-spec.md](./api-spec.md) — `/api/agents/{id}/evaluate` 페이로드
- [ADR-0004](./adr/0004-evaluation-v1-to-v5.md)
