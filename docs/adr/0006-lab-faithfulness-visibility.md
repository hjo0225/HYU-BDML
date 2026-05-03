# ADR-0006: 실험실(Lab) — 데이터 충실도 시각화 + Faithfulness 평가

## Status

Accepted (2026-04-30)

## Context

[ADR-0005](./0005-lab-twin-2k-500-integration.md)는 Toubia et al. (2025) 풀-프롬프트 방식을 그대로 채택했다. 그러나 후속 연구에서 두 가지 한계가 드러났다:

1. **Mega-Study (arxiv 2509.19088)** — 풀-덤프 트윈의 5가지 결함(stereotyping, insufficient individuation 등)과 응답자 간 r=0.20 수준의 약한 개별 차이 예측력을 실증.
2. **"Lost in the middle" (Liu 2023)** — 42k 토큰 가운데 묻힌 자전적 메모리가 LLM에 의해 무시될 가능성.

Lab의 1차 목표는 "**입력된 페르소나 데이터에 기반한 정확한 답변**"이다. 그런데 사용자가 트윈과 대화하면서 답변이 정말 데이터에서 나왔는지, 아니면 LLM이 인구통계만 보고 추측한 건지 **알 수 없는 상태**였고, 우리도 정량적으로 측정할 수단이 없었다.

또한 Lab은 본 서비스(FGI 시뮬레이션)가 아닌 **연구·시연용 쇼케이스**이므로, 한계까지 투명하게 보여주는 편이 정체성에 부합한다.

검토한 대안:

- **A. Hybrid RAG로 전환** — 풀-덤프를 멈추고 압축 요약 + 자전적 메모리 RAG. 정확도/비용은 좋아지나 ADR-0005의 "Toubia 정확 재현" 결정을 뒤집어야 한다.
- **B. 풀-덤프 유지, 출력에 transparency 레이어 부착** — 답변마다 인용·신뢰도 시각화 + 사전 계산 충실도 점수.
- **C. Self-reflection 1턴** — 답변 후 자기 검증·재생성. 토큰 비용 ~2배.

## Decision

**B를 채택**. ADR-0005의 풀-덤프 방식은 그대로 유지하고, 출력 시각화와 평가 인프라를 추가한다.

### 1. 3개 층위의 사용자 노출

| 층위 | 내용 | 비용 | 라이브 |
|---|---|---|---|
| **L1. 트윈 카드 점수** | 카테고리별 충실도 막대 + 종합 % | 사전 계산 | 정적 |
| **L2. 메시지 인용** | A(LLM 자가 인용) + B(임베딩 검증) 하이브리드. 🟢/🟡/🟠/⚪ 신뢰도 배지 + 펼침 패널 | 답변 임베딩 1회/턴 | 자동 |
| **L3. 엄격 검증 버튼** | 메시지 hover 시 "🧪 엄격 검증" → judge 호출 → verdict 카드 | judge 1회/메시지 | 사용자 트리거 |

### 2. A+B 하이브리드 인용

- **A**: 시스템 프롬프트에 출력 형식 마커 추가 — 답변 끝에 `[[CITE: cat1, cat2 | CONF: direct|inferred|guess|unknown]]`. `parse_citation_marker`가 본문에서 분리하여 사용자에게 노출하지 않음.
- **B**: 답변 임베딩 → 해당 트윈의 `PanelMemory`(이미 적재된 카테고리별 청크 + 임베딩) 코사인 top-K. LLM이 자가 인용한 카테고리가 매칭에 존재하지 않으면 drop (할루시네이션 차단). 매칭에만 등장하는 보조 카테고리는 `via='embedding'`으로 추가.
- confidence는 임베딩 매칭 강도와 LLM 자가신호를 결합해 보정 (`unknown` + 강한 매칭 → `inferred`로 승격, `direct` + 매칭 약함 → `guess`로 강등).

### 3. Faithfulness 평가 (Toubia retest 대안)

Toubia 원논문은 같은 응답자가 2주 뒤 재응답한 결과(81.72%)를 인간 상한선으로 썼다. 우리는 retest 데이터가 없을뿐더러, **"트윈이 새 질문을 어떻게 외삽하는가"보다 "트윈이 자기 페르소나에 따라 답하는가"**가 1차 목표라 평가 셋업이 다르다.

- Ground truth = `PanelMemory.text` (페르소나에 이미 적힌 응답·점수)
- 평가셋 = 카테고리당 한국어 probe 질문 1개 (gpt-4o-mini로 사전 생성, `Panel.scratch.probe_questions`에 캐시)
- 트윈이 같은 `lab_service.stream_chat`로 답변 생성
- LLM-as-judge (gpt-4o, temp=0)가 verdict ∈ {consistent, partial, contradicts, evasive}로 채점
- 점수 매핑: consistent=1.0, partial=0.5, contradicts=0.0. evasive는 평균에서 제외.
- 카테고리별 평균 + 카테고리 평균의 평균 = `overall`. `Panel.scratch.faithfulness`에 저장.

### 4. ADR-0005와의 관계

- ADR-0005는 **여전히 유효** — 풀-프롬프트 방식·게스트 공개·IP 30회 한도 등 모두 그대로.
- 본 ADR은 ADR-0005의 출력 측에 시각화·측정 레이어를 추가할 뿐, supersede가 아니다.
- 만약 향후 Hybrid RAG로 전환하기로 결정하면 새 ADR(예: 0007)에서 ADR-0005를 superseded로 표기한다. 지금 시점에서는 측정 결과(L1) 데이터를 모아 그 결정을 후속에 미룬다.

### 5. 비용·운영

- L2 임베딩: 답변 1회당 ~$0.00002 (text-embedding-3-small)
- L3 judge: gpt-4o 기준 메시지당 ~$0.005~$0.01. IP당 일일 60회 한도(채팅 30회 외에) + 같은 답변 1시간 dedup.
- 평가 일괄 실행: 50명 × ~20 카테고리 × 채팅 + judge ≈ $5~$10 일회성.

## Consequences

**+** 사용자가 답변 신뢰도를 직접 가늠 → 투명성·신뢰감 ↑.
**+** Lab의 "연구 쇼케이스" 정체성과 일치 — Toubia 한계가 화면에 정직하게 드러남.
**+** 향후 프롬프트·모델 변경의 효과를 정량 비교할 인프라 확보.
**+** 같은 인프라(`PanelMemory` + 임베딩)로 L2 시각화와 평가 양쪽이 작동 → 코드 중복 없음.
**−** 매 메시지에 임베딩 호출 1회 추가 → 부가 레이턴시 100~300ms.
**−** L3 judge 호출은 비용·레이턴시 부담이 있어 사용자 트리거로만 운영.
**−** 자가 인용 마커는 모델이 가끔 누락하거나 잘못된 슬러그를 출력 가능 — 임베딩 검증으로 보완하나 100% 정확 보장 못함.

## Out of Scope (후속 PR 후보)

- 페르소나 한국어 압축 요약 시스템 프롬프트 상단 주입 (B1)
- Hybrid RAG 전환 (별도 ADR)
- self-reflection 1턴
- 메시지 분할(multi-bubble), 한국어 메신저 톤 few-shot
- 모델 업그레이드(gpt-4o-mini → gpt-4o for chat)

이 옵션들은 **L1 평가 결과로 약한 카테고리가 무엇인지 본 다음** 우선순위를 매겨 후속 PR로 진행한다.
