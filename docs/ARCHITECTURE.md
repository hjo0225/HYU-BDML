# Architecture — Ditto

Ditto 의 모듈 경계, 데이터 흐름, 외부 의존성, 배포 토폴로지.

## 모노레포 경계

```
HYU_BDML/   (※ Phase 6에 GitHub repo 를 'Ditto'로 rename 예정)
├── archive/bdml-fgi/   # 동결된 BDML-FGI. read-only 참조용. 신규 코드는 import 금지.
├── frontend/           # (Phase 2 이후) Next.js — UI 전담
└── backend/            # (Phase 2 이후) FastAPI — LLM·데이터 전담
```

- **frontend** 책임: 사용자 입력, 화면 렌더링, sessionStorage 기반 프로젝트 상태 전달, SSE/NDJSON 수신, 대시보드 시각화.
- **backend** 책임: LLM 호출 (OpenAI/Anthropic), 임베딩, DB 영속화, 인증, 6-Lens 데이터 처리, 평가 엔진.
- 통신: HTTP/JSON + SSE + NDJSON. 프론트는 `frontend/src/lib/api.ts` 를 통해서만 호출.

## 백엔드 계층 구조

```
routers/  →  services/  →  (lenses / scoring / persona / conversation / fgi / evaluation)  →  prompts/ + embedding/  →  OpenAI / Anthropic / DB
```

| 계층 | 책임 |
|---|---|
| `routers/` | HTTP 엔드포인트, 요청 검증, 인증 체크. |
| `services/` | 비즈니스 로직, 트랜잭션, 외부 API 오케스트레이션. |
| `lenses/` | 6-Lens 매핑 (L1~L6 + 정성). 234문항 → 카테고리 분할. |
| `scoring/` | 정량 지표 (역채점, 경제 수치화 CE, 능력치 합산). |
| `persona/` | Hybrid Persona Prompt Builder (수치 + 원문). |
| `conversation/` | 1:1 대화 엔진 (SSE 스트리밍 + 메모리 업데이트 hook). |
| `fgi/` | FGI 다자 회의 엔진 (LangGraph 상태머신 + 사용자 개입 hook). |
| `evaluation/` | V1~V5 평가 엔진. |
| `embedding/` | OpenAI text-embedding-3-small + 캐시. |
| `prompts/` | 프롬프트 템플릿 (서비스에 인라인 금지). |

## 핵심 데이터 파이프라인

### 파이프라인 1 — 에이전트 생성 (Phase 2 산출물)

```
Twin-2K-500 한국어 응답 (또는 Survey 응답, v1.0)
   │
   ▼
backend/lenses/mapping.py
   ├─ 234문항 → L1~L6 + 정성 카테고리 분할
   └─ scratch (인구통계 + 정성 원문) 추출
   │
   ▼
backend/scoring/
   ├─ reverse_score.py  (역방향 문항 변환)
   ├─ economic.py       (위험회피 CE, 할인율 연환산)
   └─ ability.py        (금융이해/수리 합산)
   │
   ▼
backend/persona/builder.py
   ├─ persona_params (수치 JSONB) + 원문 (scratch)
   ├─ prompts/persona_system.py 로 시스템 프롬프트 합성 (≤ 8k tokens)
   └─ embedding/embedder.py 로 카테고리별 메모리 임베딩 (1536d)
   │
   ▼
DB:
  agents (persona_params, persona_full_prompt)
  agent_memories (category, text, embedding, source='base')
```

### 파이프라인 2 — 1:1 대화 (Phase 3)

```
사용자 메시지
   │
   ▼
backend/conversation/service.py
   ├─ Agent.persona_full_prompt 시스템 메시지로 주입
   ├─ Conversation.turns 히스토리 + 신규 사용자 메시지
   ├─ retriever.retrieve(agent_id, query=focal_message)
   │     - agent_memories (cosine top-K, source='base'|'conversation')
   ├─ prompts/conversation_utterance.py 합성
   └─ OpenAI gpt-4o SSE 스트리밍
        │
        ▼ (자가 인용 마커 [[CITE: ... | CONF: ...]] 분리)
        ▼
backend/services/citation_service.py (← archive lab_citation_service 진화)
   ├─ 답변 임베딩 vs agent_memories 코사인 top-K 검증
   └─ 인용·신뢰도 페이로드 반환
        │
        ▼
SSE end 이벤트 + 클라이언트 ChatBubble + ScoreBadge 렌더
        │
        ▼ (대화 종료 시)
backend/conversation/memory_updater.py
   ├─ 대화 요약 (LLM)
   └─ agent_memories 추가 (source='conversation', importance 산정)
```

### 파이프라인 3 — FGI 다자 회의 (Phase 4)

```
FGI 시작
   │
   ▼
backend/fgi/engine.py (LangGraph)
   ├─ moderator 노드: 질문 생성
   ├─ agent 노드 × N: 각 에이전트가 발언 (영감 연쇄 retrieval)
   ├─ user_intervention 노드: 사용자 입력 대기 (hook, optional)
   │     SSE: { type: "user_turn_required" } 송신 → timeout 또는 사용자 입력
   ├─ round_summary 노드: 라운드 요약 → 다음 라운드 retrieval 컨텍스트
   └─ end 조건: 모더레이터 포화도 판단 또는 라운드 상한
        │
        ▼
모든 참여 agent 의 agent_memories 에 FGI 요약 추가 (source='fgi')
        │
        ▼
FGISession.minutes (Markdown) 자동 생성 + DB 저장
```

### 파이프라인 4 — 평가 엔진 (Phase 3~5)

```
EvaluationRun 트리거 (사용자 요청 또는 nightly cron)
   │
   ├─ V1 응답 동기화: 원본 234문항 → agent.answer → cosine sim(answer, original)
   ├─ V2 모델 신뢰도: 동일 페르소나 + 동일 질문 → GPT-4o, Claude-3.5 답변 cosine sim
   ├─ V3 페르소나 독립성: 모든 agent 의 답변 임베딩 평균, 페르소나 간 평균 거리
   ├─ V4 인격 자연스러움: Judge LLM(gpt-4o) 채점 (1~5)
   └─ V5 상황 대응 일관성: CF 자극 → 답변 임베딩 Δ 측정
   │
   ▼
EvaluationSnapshot 저장 (agent_id, version, identity_stats, logic_stats, evaluated_at)
   │
   ▼
GET /api/dashboard/agents/{id}  →  Recharts 시각화
```

## 외부 의존성

| 서비스 | 용도 | 모듈 위치 | 도입 Phase |
|---|---|---|---|
| OpenAI `gpt-4o` | 발화·Judge·요약 | `services/openai_client.py` | Phase 2 |
| OpenAI `text-embedding-3-small` | 1536차원 임베딩 | `embedding/embedder.py` | Phase 2 |
| Anthropic `claude-3.5-sonnet` | V2 모델 신뢰도 평가 전용 | `services/anthropic_client.py` | Phase 5 |
| Cloud SQL PostgreSQL | 운영 DB | `database.py` | Phase 2 |
| SQLite (aiosqlite) | 로컬 개발 DB | `database.py` | Phase 2 |
| Recharts | 대시보드 시각화 | `frontend/src/components/dashboard/` | Phase 3 |
| Pretendard 웹폰트 | UI 폰트 | CDN 또는 self-host | Phase 2 |

> **archive 와의 차이:** Naver Search API · OpenAI Web Search 는 Ditto MVP 에서 사용하지 않음 (시장조사 모듈 폐기).

## 인증 아키텍처

- JWT 액세스 토큰 + httpOnly 쿠키 리프레시 토큰.
- bcrypt 패스워드 해싱.
- 리프레시 토큰은 SHA-256 해시로 DB(`refresh_tokens`)에 저장하여 무효화 가능.
- archive 에서 그대로 이식 (Phase 2).

## 배포 토폴로지 (Phase 6 에서 신규 작성 예정)

```
GitHub (main push)
   │
   ▼
GitHub Actions + Workload Identity Federation (OIDC)
   │
   ├─ Cloud Run frontend (port 3000)
   └─ Cloud Run backend  (port 8080)
              │
              ▼
       Cloud SQL PostgreSQL
       (asia-northeast3:bigmarlab-db ← 기존 DB 재사용 또는 신규 인스턴스 결정 미정)
```

### 환경변수 (런타임 주입, Phase 2 부터 단계적 정의)

- `DATABASE_URL`, `JWT_SECRET_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY` (Phase 5)
- `CORS_ORIGINS`, `ADMIN_EMAILS`
- `EVAL_DEFAULT_MODEL` (예: `gpt-4o`), `EVAL_JUDGE_MODEL` (예: `gpt-4o`), `EVAL_STABILITY_MODEL_2` (예: `claude-3-5-sonnet-20240620`)

## 성능·비용 주의사항

- **시스템 프롬프트 ≤ 8k tokens.** Toubia 풀-프롬프트(42k)와 달리 6-Lens 압축으로 Lost-in-the-middle 회피. archive `lab_service` 와의 명확한 차이.
- **임베딩 캐싱.** `embedding/cache.py` 가 동일 텍스트 재임베딩 차단. `embedding_cache.json` 은 git 미추적.
- **V2 모델 신뢰도 비용.** GPT-4o + Claude 양쪽 호출 = 약 2배. 사용자 트리거 또는 nightly cron 으로만 실행, 라이브 채팅에서는 호출 안 함.
- **Cloud Run 다중 인스턴스 환경에서 인메모리 카운터 부정확.** 사용량 집계는 항상 DB(`activity_logs`) 기반.

## 로컬 실행 (Phase 2 이후)

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000

# Frontend (별도 터미널)
cd frontend
npm install
npm run dev
# http://localhost:3000

# Twin-2K-500 한국어 30명 적재 (최초 1회)
cd backend
python -m scripts.seed_twin_v2 --limit 30
```

## archive 와의 데이터 격리

- archive 의 `panels` / `panel_memories` 테이블은 **건드리지 않음**. Phase 6 정리 시점에 통합/삭제 여부 ADR 결정.
- Ditto 신규 테이블은 `agents`, `agent_memories`, `evaluation_snapshots` 등으로 **이름 분리**.
- 기존 `users`, `refresh_tokens`, `activity_logs` 는 그대로 재사용.
- 기존 `projects`, `project_edits` 는 Alembic 마이그레이션으로 `projects_v1_bdml`, `project_edits_v1_bdml` 로 rename 후 신규 `projects` 도입 (DB 마이그레이션 plan 별도).

## 관련 ADR

- [ADR-0001 — Archive BDML, Bootstrap Ditto](./adr/0001-archive-bdml-bootstrap-ditto.md)
- [ADR-0002 — 6-Lens 카테고리 분할 채택](./adr/0002-six-lens-categorization.md)
- [ADR-0003 — Hybrid Persona Prompt (수치 + 원문)](./adr/0003-hybrid-persona-prompt.md)
- [ADR-0004 — V1~V5 평가 5지표 채택](./adr/0004-evaluation-v1-to-v5.md)
