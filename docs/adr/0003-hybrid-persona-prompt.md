# ADR-0003 — Hybrid Persona Prompt (수치 + 원문)

## Status

Accepted (2026-05-07)

## Context

에이전트의 시스템 프롬프트 합성 방식을 결정해야 했다. archive(BDML-Lab)는 **Toubia 풀-프롬프트** 방식을 채택했다 (`panels.persona_full` ~170k chars / ~42k tokens 을 매 턴 시스템 프롬프트에 통째 주입, [archive/bdml-fgi/docs/adr/0005](../../archive/bdml-fgi/docs/adr/0005-lab-twin-2k-500-integration.md) 참조). 그러나 후속 ADR-0006 에서 다음 한계가 실증되었다.

1. **Lost-in-the-middle (Liu 2023):** 42k 토큰 가운데 묻힌 자전적 메모리가 LLM 에 의해 무시될 가능성.
2. **Mega-Study (arxiv 2509.19088):** 풀-덤프 트윈의 5가지 결함 (stereotyping, insufficient individuation 등) 과 응답자 간 r=0.20 수준의 약한 개별 차이 예측력.
3. **비용:** GPT-4o 풀-프롬프트 = 입력 42k × $2.5/1M = ~$0.105/턴. 1000 턴 시연 시 $100+.

후보 합성 방식:

- **A. Toubia 풀-프롬프트** (archive 방식) — 정확 재현, 비용·Lost-in-the-middle 위험.
- **B. Hybrid (수치 + 원문)** — 6-Lens 정량 지표를 자연어로 풀고 + 정성 원문을 포함. ≤ 8k tokens.
- **C. RAG-only** — 시스템 프롬프트 최소화 + 매 턴 retrieval. 답변마다 다른 컨텍스트라 일관성 위험.

## Decision

**B. Hybrid (수치 + 원문)** 채택. 시스템 프롬프트 ≤ 8k tokens 을 목표로 한다.

### 합성 구조

```
[수치 기반 가이드] (~2-3k tokens)
당신은 위험 회피 점수 0.9 (매우 높음) 로 새로운 시도보다 안정을 추구합니다.
극대화 성향 5.2/7 로 결정 전 옵션을 충분히 비교합니다.
연환산 할인율 18% 로 미래의 큰 보상보다 가까운 작은 보상을 약간 선호합니다.
... (6-Lens 별 정량 지표를 자연어로 풀어 기재)

[원문 기반 가이드] (~2-3k tokens)
당신은 스스로를 다음과 같이 정의합니다:
"<self_actual 한국어 원문 — 수백 토큰>"
당신이 이상적으로 되고 싶은 모습:
"<self_aspire 한국어 원문>"
당신이 의무라고 느끼는 모습:
"<self_ought 한국어 원문>"

[제약 사항]
1. 모든 답변은 위 성향과 당신이 직접 작성한 사고 방식에 근거합니다.
2. 데이터에 없는 상세는 추측하지 말고 "잘 모르겠다"고 답합니다.
3. 답변은 자연스러운 한국어 1인칭으로.
4. 답변 끝에 [[CITE: <카테고리,...> | CONF: direct|inferred|guess|unknown]] 마커를 출력합니다.
```

### 추가 컨텍스트

매 턴 retrieval 로 가져온 카테고리별 메모리(`agent_memories.source='base'|'conversation'|'fgi'`)는 **시스템 프롬프트 외부**의 user/assistant 턴에 합성. 이로써 시스템 프롬프트는 정체성(identity)에 집중하고, retrieval 은 발화 컨텍스트(working memory)에 집중하는 분리.

```
system: <Hybrid Persona Prompt, ≤8k tokens>
[메모리 컨텍스트 (assistant 턴으로 위장)]: "오늘 떠오르는 기억 — <retrieval top-K 메모리>"
user: <대화 히스토리>
user: <현재 메시지>
```

## Consequences

### 긍정적

1. **Lost-in-the-middle 회피.** 8k tokens 안에서 핵심 정체성 + 정성 원문이 모두 들어가므로 LLM 이 무시할 위험 ↓.
2. **비용 ~80% 절감.** GPT-4o 입력 8k tokens = ~$0.02/턴 (vs Toubia 42k tokens = ~$0.105/턴).
3. **수치 가이드가 V5 일관성 검증을 보강.** "위험 회피 0.9" 같은 명시적 수치가 있으면, CF 자극에서 위험 변화 시나리오에 대해 일관된 반응 (큰 Δ 또는 작은 Δ) 을 보일 가능성 ↑.
4. **정성 원문 보존.** 사용자가 직접 쓴 "실제 자기" 서술문은 압축하지 않고 그대로 주입 — Mega-Study 가 지적한 "stereotyping" 회피.
5. **6-Lens 와 직접 매핑.** [수치 기반 가이드] 가 6 그룹으로 떨어지므로 가독성·디버깅 ↑.

### 부정적

1. **압축 손실.** Toubia 풀-프롬프트가 매 턴 LLM 에 노출하는 정보의 일부는 8k 압축본에서 빠진다. 이로 인해 V1 응답 동기화율이 archive (Toubia) 대비 낮아질 가능성. Phase 3 평가 결과로 검증 필요.
2. **수치 가이드 자연어화 비용.** 매번 LLM 으로 "위험 회피 0.9를 자연어 한 문장으로" 변환할지, 정적 템플릿(if-else)으로 처리할지 결정 필요. 잠정: 정적 템플릿 (Phase 2 에서 `prompts/persona_system.py`).
3. **archive 의 Toubia 정확 재현은 불가능.** archive 의 ADR-0005 가 강조한 "Toubia 논문 재현성" 은 Ditto 에선 비범위. 만약 재현이 필요해지면 별도 ADR 로 archive 모듈 일부를 부활시킬 수 있다.

### Open Question

- 8k tokens 에서 더 압축할지 (예: ~5k) — Phase 3 V1 측정 결과로 결정.
- self_actual 원문 길이가 매우 긴 응답자(>2k tokens)는 LLM 으로 압축 vs trim 결정 필요.

## 관련

- [PRD.md §4.1.3](../PRD.md)
- [ARCHITECTURE.md — 파이프라인 1](../ARCHITECTURE.md)
- [DATA_MODEL.md — `agents.persona_full_prompt`](../DATA_MODEL.md)
- [archive/bdml-fgi/docs/adr/0005 — Toubia 풀-프롬프트 (Superseded for Ditto)](../../archive/bdml-fgi/docs/adr/0005-lab-twin-2k-500-integration.md)
- [archive/bdml-fgi/docs/adr/0006 — Lab faithfulness 가시화](../../archive/bdml-fgi/docs/adr/0006-lab-faithfulness-visibility.md)
