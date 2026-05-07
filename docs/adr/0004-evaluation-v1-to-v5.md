# ADR-0004 — V1~V5 평가 5지표 채택

## Status

Accepted (2026-05-07)

## Context

Ditto 의 핵심 차별점은 **에이전트 성능 평가 대시보드**이다 ([PRD §4.2](../PRD.md)). 단순히 에이전트를 만들어 대화하게 하는 것을 넘어, 그 에이전트가 **실제 사람을 얼마나 충실히 복제했는지** 정량적으로 측정해야 사용자가 인사이트의 신뢰도를 판단할 수 있다.

archive(BDML-Lab)는 [ADR-0006](../../archive/bdml-fgi/docs/adr/0006-lab-faithfulness-visibility.md) 에서 **사전 계산 충실도** + **답변 인용 + 신뢰도 배지** 를 도입했지만, 다음이 빠져 있었다.

1. 모델 편향 검출 (LLM 이 바뀌면 다른 페르소나가 되는지) — 없음.
2. 페르소나 간 차별성 (mode collapse) — 없음.
3. 의사결정 일관성 (반사실적 변화 시 답변 변동성) — 없음.

사용자(§4.2 PRD)가 정의한 5지표 (V1~V5) 중 어느 것을 채택할지 검토했다.

## Decision

**5지표 모두 채택**, 단 도입 Phase 를 분산.

| 지표 | Section | 정의 | 도입 Phase |
|---|---|---|---|
| **V1 응답 동기화율** | Identity | 에이전트 답변 vs 원문 답변 cosine similarity | Phase 3 |
| **V2 모델 신뢰도** | Identity | GPT-4o vs Claude-3.5 답변 cosine similarity | Phase 5 |
| **V3 페르소나 독립성** | Identity | 모든 에이전트 간 평균 답변 거리 (mode collapse 검출) | Phase 5 |
| **V4 인격 자연스러움** | Logic | Judge LLM (gpt-4o) 1~5 점 채점 | Phase 4 |
| **V5 상황 대응 일관성** | Logic | 반사실적 자극 시 답변 임베딩 Δ | Phase 5 |

자세한 채점 공식·임계값·자극 세트는 [`EVAL_SPEC.md`](../EVAL_SPEC.md).

### 단계 분산 사유

1. **Phase 3 (V1 + 1:1 대화):** V1 만으로도 "이 에이전트가 작동은 한다" 를 보여줄 수 있다. 가장 토대가 되는 지표.
2. **Phase 4 (V4 + FGI):** FGI 발화는 자연스러움(Humanity)이 핵심 — V4 가 가장 빠르게 시각적 가치를 줌.
3. **Phase 5 (V2 + V3 + V5):** Anthropic API 추가 + CF 자극 세트 설계 + 다중 에이전트 거리 행렬 — 인프라 작업이 많아 마지막에 묶음.

### 종합 verdict 산정

```
verdict =
  "verified_s3"  if  V1≥0.80 AND V2≥0.85 AND V4≥4.0 AND 0.10≤V5≤0.30
  "partial"      if  (V1≥0.60 AND V4≥3.0) AND (above 미달 항목 있음)
  "failed"       else
```

V3 는 30명 분포 지표라 단일 에이전트 verdict 에는 직접 영향 X. 분포에서 이상치인 에이전트만 대시보드에 경고 표시.

## Consequences

### 긍정적

1. **사용자가 에이전트 신뢰도를 정량적으로 판단** 할 수 있다 — Ditto 의 핵심 가치.
2. **Identity vs Logic 분리** 로 "이 에이전트는 사실 복제(V1)는 좋은데 추론 일관성(V5)이 낮다" 같은 진단이 가능.
3. **V3 mode collapse 검출** 로 LLM 이 "평균적인 한국 직장인" 같은 무난한 답을 모든 페르소나에 똑같이 생성하는 위험을 모니터링.
4. **archive 의 인용·신뢰도 인프라 재활용** — V1 입증 인프라가 사실상 archive 의 `lab_citation_service` + `eval_lab_faithfulness` 의 진화형이라, Phase 3 진입이 빠름.

### 부정적

1. **비용 증가.** V1+V4 만으로도 1 에이전트 평가에 ~$0.05. V1~V5 풀 평가는 ~$0.30. 30명 풀 평가 = ~$9.
2. **V3·V5 임계값 미정.** 이론적 적정값을 모르므로 Phase 5 에서 30명 실측치를 기반으로 임계값 확정. 임계값 변경 시 본 ADR 또는 별도 ADR 추가.
3. **V2 multi-LLM 의존성.** Anthropic API 키 + 비용 추가. v1.0 출시 시 V2 를 옵션으로 (사용자가 끄면 GPT-4o 만 사용).

### 모니터링 후속

- Phase 5 종료 시 30명 첫 평가 결과로 임계값 조정 필요한지 확인.
- 에이전트 성장 (대화·FGI 누적) 후 V1 점수가 낮아지는지 (메모리 오염) 측정.
- V4 Judge 의 점수 분포가 천장 효과(모두 4-5점)인지 검토 → 필요 시 Judge 프롬프트 강화.

## 관련

- [PRD.md §4.2](../PRD.md)
- [EVAL_SPEC.md](../EVAL_SPEC.md)
- [DATA_MODEL.md — `evaluation_snapshots`](../DATA_MODEL.md)
- [api-spec.md — `/api/agents/{id}/evaluate`](../api-spec.md)
- [archive/bdml-fgi/docs/adr/0006 — Lab faithfulness 가시화 (전신)](../../archive/bdml-fgi/docs/adr/0006-lab-faithfulness-visibility.md)
