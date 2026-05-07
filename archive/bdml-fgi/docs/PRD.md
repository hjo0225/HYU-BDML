# Product Requirements — 빅데이터마케팅랩 (BDML)

AI 에이전트 기반 정성조사(FGI) 시뮬레이션 웹앱. 사용자가 연구 정보를 입력하면 AI가 시장조사 → RAG 기반 패널 구성 → FGI 회의 시뮬레이션 → 회의록 생성까지 자동 수행한다.

## 목적

- 정성조사(FGI)의 패널 모집·진행·기록 비용을 AI 에이전트로 대체하여 빠른 가설 검증을 제공한다.
- 실제 설문 패널 500명의 행동 데이터를 RAG로 활용하여, 가상 응답이 아닌 데이터 기반 응답을 생성한다.

## 사용자 흐름 (Phase 1~5)

```
Phase 1: 연구 정보 입력 → Phase 2: 시장조사
→ Phase 3: 주제 · 에이전트 (3-step 위저드)
    Step 1: 회의 주제 입력 (textarea)
    Step 2: 모드 선택 — RAG 실제 패널 / LLM 가상 에이전트
    Step 3: 에이전트 생성 결과 + 편집
→ Phase 4: 회의 시뮬레이션 (주제 Phase 3에서 설정됨, 진입 시 자동 시작)
→ Phase 5: 회의록 · 내보내기
```

### Phase 1 — 연구 정보 입력

- 입력: 연구 주제, 타겟 고객, 핵심 질문 등의 brief.
- 출력: `project.brief` 저장. 정제 요청 시 `POST /api/research/refine` → `project.refined`.
- 수용 기준
  - 미입력 필드 검증.
  - 정제 결과는 사용자 확인 후 저장.

### Phase 2 — 시장조사

- 백엔드가 Naver/OpenAI 검색을 수행하여 보고서를 합성한다.
- 엔드포인트: `POST /api/research` (NDJSON 스트리밍).
- 출력: `project.market_report` 저장.
- 수용 기준
  - 스트리밍 진행률을 사용자에게 표시.
  - 검색 실패 시 부분 결과라도 보고서를 합성한다.

### Phase 3 — 주제 · 에이전트 (3-step 위저드)

- **Step 1 — 회의 주제 입력**: textarea로 자유 입력. `project.meetingTopic`에 저장.
- **Step 2 — 모드 선택**:
  - `rag`: 실제 패널 500명 풀에서 주제 관련성 + 클러스터 다양성으로 N명 선정.
  - `llm`: LLM이 brief/report를 보고 가상 에이전트 N명을 생성.
- **Step 3 — 에이전트 생성**:
  - 엔드포인트: `POST /api/agents/stream/v2` (SSE).
  - 페이로드: `AgentStreamRequest { brief, refined, report, topic, mode }`.
  - 사용자는 생성된 에이전트를 수정/삭제 가능.
- 수용 기준
  - `meetingTopic`이 없으면 Step 1부터 시작 (이전 프로젝트 하위호환).
  - RAG 모드에서 패널 부족 시 가용 인원만큼 반환.

### Phase 4 — 회의 시뮬레이션

- AI 자동 진행만 (사용자 개입 없음).
- 엔드포인트: `POST /api/meeting` (SSE).
- 진입 시 `project.meetingTopic`에서 주제를 받아 자동 시작 (topic input UI 없음).
- 오른쪽 패널은 회의 아젠다만 표시 — 회의 정보·발언 횟수·메모리 활성화 UI 없음.
- 채팅 메시지에 메모리 배지 없음.
- 수용 기준
  - 발언 스트리밍 중 사용자가 페이지를 이탈해도 백엔드 진행은 계속됨.
  - 모더레이터가 포화도 도달을 판단하면 회의 종료.

### Phase 5 — 회의록 · 내보내기

- 엔드포인트: `POST /api/minutes`.
- 출력 형식: Markdown.
- 내보내기 옵션: 클립보드 복사만 (별도 파일 저장 기능 없음).

## 수용 기준 (전역)

- 모든 Phase 데이터는 sessionStorage(`ProjectContext`)로 전달되며, 새로고침 후에도 복원된다.
- 인증 미통과 사용자는 Phase 페이지에 접근 불가 (`AuthGuard`).
- 토큰 사용량은 `ActivityLog`에 기록되어 관리자가 `/api/usage/*`로 조회 가능.

## 비범위 (Out of Scope)

- 사용자 개입형 실시간 회의 진행 (관전만 가능).
- PDF/DOCX 내보내기.
- 다국어 지원 (한국어 전용).

---

## 실험실 (Lab) — Twin-2K-500 1:1 메신저

본 서비스의 5-Phase 흐름과는 **별개의 분기**. 인증 없이 게스트가 접근하여 Twin-2K-500 데이터셋 기반 디지털 트윈 페르소나와 1:1로 대화한다. 시연·연구용이며 실서비스 영역이 아니다.

### 데이터셋 출처

- **Twin-2K-500** (Toubia, O., Gui, G. Z., Peng, T., Merlau, D. J., Li, A., & Chen, H., 2025). "Database Report: Twin-2K-500." *Marketing Science*, 44(6), 1446–1455. https://doi.org/10.1287/mksc.2025.0262
- Hugging Face: https://huggingface.co/datasets/LLM-Digital-Twin/Twin-2K-500
- 시범 단계: 전체 ~2,058명 중 50명을 샘플링 적재.

### 사용자 흐름

```
랜딩(/) → "실험실 체험" CTA
       → /lab (실험 종류 선택 메뉴)
            └─ "디지털 트윈 1:1 메신저" 카드 → /lab/twin-chat (Twin 50명 카드 그리드)
                                              └─ 카드 선택 → /lab/twin-chat/{twinId} (1:1 메신저)
            └─ (추후 추가될 실험은 비활성 카드로 표시)
```

### 인증 / 접근 정책

- **완전 공개** — 로그인 불필요, AuthGuard 미적용.
- 토큰 비용 폭주 방지를 위해 **IP 단위 일일 메시지 30회 한도** (인메모리 카운터, Redis 미도입).

### 입출력

- **Twin 페르소나**: 영어 원본 설문 응답을 기반으로 영어 메모리 임베딩.
- **채팅 응답**: LLM 프롬프트로 한국어 1인칭 수다 톤 변환. 사용자도 한국어로 입력.

### 수용 기준

- `/lab` 진입 시 50명 카드(이름·연령·직업·지역·이모지·짧은 소개) 표시.
- 카드 선택 → `/lab/chat/{twinId}`에서 입력창 + 메신저 형태 채팅.
- 메시지 전송 시 SSE 스트리밍으로 한국어 응답 수신.
- 채팅 히스토리는 `sessionStorage[lab-chat-${twinId}]`에 저장 (DB 영속화 없음). 새로고침 시 복원.
- 게스트 안내 배너: "체험용 모드 — 대화는 저장되지 않습니다."
- 동일 IP 31번째 메시지 → 429 응답 + 사용자 안내.

### 비범위 (Lab)

- 채팅 영속화·검색·내보내기.
- 회원 단위 사용량 추적 (게스트는 IP 단위만).
- 영어 응답 모드.
- 다중 트윈 회의 (1:1만 지원).
