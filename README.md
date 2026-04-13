# Interactive Multiagent - AI FGI Simulation

> **한 줄 요약:** 연구 브리프 입력 하나로 시장조사 → 가상 참여자 구성 → FGI 시뮬레이션 → 회의록 생성까지 자동 수행하는 멀티 에이전트 리서치 워크플로우

[![Deploy to GCP](https://github.com/hjo0225/interactive-multiagent/actions/workflows/deploy.yml/badge.svg?style=for-the-badge)](https://github.com/hjo0225/interactive-multiagent/actions/workflows/deploy.yml)
![Next.js](https://img.shields.io/badge/Next.js-14-black?style=for-the-badge&logo=next.js&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-3.4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?style=for-the-badge&logo=openai&logoColor=white)
![GCP](https://img.shields.io/badge/GCP-Cloud_Run-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)

## 1. 개요

- **핵심 가치:** 정성조사 기획에 필요한 시장 탐색 → 참여자 설계 → 토론 시뮬레이션 → 문서화를 하나의 사용자 흐름으로 통합. 리서처의 반복 작업을 AI 오케스트레이션으로 대체합니다.
- **배포 URL:** GCP Cloud Run (프론트엔드 · 백엔드 분리 배포)
- **주요 기술:** `Next.js 14`, `FastAPI`, `OpenAI API`, `LangGraph`, `RAG Pipeline`, `SSE`

### 사용자 흐름 (5단계)

| 단계 | 라우트             | 기능                               |
| ---- | ------------------ | ---------------------------------- |
| 1    | `/research-input`  | 연구 브리프 입력                   |
| 2    | `/market-research` | 연구 정보 정제 + 시장조사 스트리밍 |
| 3    | `/agent-setup`     | 주제 설정 → 모드 선택(RAG/LLM) → 에이전트 추천 및 편집 |
| 4    | `/meeting`         | FGI 회의 시뮬레이션 (SSE)          |
| 5    | `/minutes`         | 회의록 생성 및 Markdown 내보내기   |

## 2. 핵심 문제 해결

### Architecture

```text
Browser (Next.js 14)
  ├─ sessionStorage  ← 단계 간 상태 유지
  ├─ NDJSON 스트림 수신  ← 시장조사
  └─ SSE 스트림 수신    ← 에이전트 생성 / 회의 시뮬레이션
       │  HTTP / SSE
       ▼
FastAPI (Backend)
  ├─ POST /api/research/refine        브리프 정제
  ├─ POST /api/research               시장조사 NDJSON 스트림
  ├─ POST /api/agents/stream/v2       에이전트 추천 SSE (RAG/LLM 모드 분기)
  ├─ POST /api/meeting                회의 시뮬레이션 SSE
  ├─ POST /api/minutes                회의록 생성
  ├─ CRUD /api/projects               프로젝트 저장/로드
  ├─ AUTH /api/auth/*                 JWT 인증 (httpOnly 쿠키)
  └─ GET  /api/health                 헬스체크
       │
       ▼
LLM + RAG Orchestration
  ├─ OpenAI SDK (GPT-4o)              연구·에이전트·사회자·회의록
  ├─ text-embedding-3-small           1536차원 RAG 임베딩
  ├─ LangGraph                        회의 흐름 상태머신
  ├─ Cloud SQL (PostgreSQL)           패널 500명 + 7,000건 기억 + 임베딩
  ├─ Naver Search API                 한국 시장 맥락
  └─ OpenAI Web Search                글로벌 시장 데이터
```

### RAG 파이프라인 (패널 기반 에이전트)

실제 설문 데이터(500명, 510컬럼)를 기반으로 가상 FGI 참여자를 구성합니다:

1. **패널 데이터 적재** — CSV 원본 → 인구통계 추출(`scratch`) + 14개 카테고리 자전적 기억 생성 → 1536차원 임베딩 → Cloud SQL 저장
2. **패널 선택** (Phase 3) — 전체 500명 풀에서 클러스터 다양성 + 주제 관련성 복합 스코어로 N명 선택 (연령 필터 없음)
3. **회의 발언** (Phase 4) — retrieval 쿼리(모더레이터 질문 + 직전 참여자 발언)로 관련 기억을 검색 → 1인칭 서사형 프로필 + 기억을 프롬프트에 주입 → 자연스러운 발언 생성. 다른 참여자 발언이 메모리를 트리거하는 "영감 연쇄" 구조

### Trade-offs

| 선택한 기술                  | 도입 이유                                                            | 고려했던 대안 및 포기한 이유                                                    |
| ---------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **LangGraph**                | 회의 시뮬레이션의 라운드 전환·종료 조건을 상태머신으로 명확하게 표현 | LangChain LCEL만으로는 분기·루프 로직 표현이 장황해짐                           |
| **SSE (Server-Sent Events)** | 회의 발언을 토큰 단위로 실시간 스트리밍, 연결 유지 단순              | WebSocket은 양방향이 필요 없는 단방향 스트림에 과도한 설계                      |
| **NDJSON 스트리밍**          | 시장조사 섹션을 순서대로 점진적 렌더링 가능                          | 단일 JSON 응답은 전체 완료 전까지 화면이 비어있어 UX 저하                       |
| **RAG + Cloud SQL**          | 실제 설문 기반 패널로 에이전트 발언의 근거와 일관성 확보             | LLM만으로 페르소나 생성 시 발언이 피상적이고 설문 데이터 활용 불가              |
| **Naver Search API**         | 한국어 시장 정보의 밀도·신뢰도 확보                                  | OpenAI Web Search만 사용 시 한국 시장 맥락 데이터 부족                          |
| **sessionStorage**           | 별도 DB 없이 단계 간 상태 전달, 프로토타입 속도 우선                 | Redux/Zustand는 새로고침 시 소실 문제 동일하면서 설정 비용 높음                 |
| **GCP Cloud Run**            | 컨테이너 단위 분리 배포, Workload Identity로 키 관리 불필요          | EC2/GCE는 인스턴스 관리 부담, Vercel은 백엔드 장시간 SSE 스트림에 타임아웃 이슈 |

## 3. 핵심 기능 및 트러블슈팅

### 회의 시뮬레이션 SSE — Next.js 프록시 타임아웃

- **상황:** 회의 시뮬레이션은 수 분간 지속되는 SSE 스트림인데, Next.js rewrites 프록시를 경유하면 30초 타임아웃으로 연결이 끊어짐
- **해결:** 개발 환경에서는 프론트엔드가 `http://localhost:8000/api`를 직접 호출하도록 분기 처리. 운영 환경에서는 백엔드 Cloud Run URL을 `NEXT_PUBLIC_BACKEND_URL`로 직접 지정해 프록시 우회
- **결과:** 긴 회의(20+ 라운드)에서도 스트림 단절 없이 전체 발언 수신 가능

### 시장조사 스트리밍 — 섹션별 점진적 렌더링

- **상황:** 시장조사 보고서 전체 생성에 30~60초 소요. 단일 응답 방식은 빈 화면 대기 시간이 길어 UX 저하
- **해결:** 5개 고정 섹션(`market_overview`, `competitive_landscape`, `target_analysis`, `trends`, `implications`)을 NDJSON으로 순차 스트리밍. 각 섹션 완료 시 즉시 렌더링
- **결과:** 첫 번째 섹션이 3~5초 내 표시되어 체감 대기 시간 대폭 감소

### RAG 에이전트 — 주제 관련성 기반 패널 선택

- **상황:** 500명 패널 중 임의로 선택하면 회의 주제와 무관한 참여자가 배정됨
- **해결:** 연령 필터 없이 전체 500명 풀에서 각 패널의 14개 카테고리 기억을 주제 임베딩과 코사인 유사도로 스코어링. 클러스터 다양성(0.7) + 주제 관련성(0.3) 복합 스코어로 최종 선택
- **결과:** 주제에 관련 경험이 풍부한 패널이 우선 선택되면서도 인구통계적 다양성 유지

### 에이전트 페르소나 일관성 — system prompt 합성

- **상황:** 사용자가 편집한 페르소나 필드(나이·성향·말투 등)와 회의에서 실제 사용되는 system prompt가 불일치하는 문제
- **해결:** `POST /api/agents/synthesize-prompt`에서 편집된 페르소나 프로필을 받아 LLM이 일관된 system prompt로 재합성. 저장 전 프리뷰 가능
- **결과:** 페르소나 편집 내용이 회의 발언 톤·관점에 실제로 반영됨

## 4. 실행 방법

### Local

**환경 변수 설정**

```env
# backend/.env
OPENAI_API_KEY=your_openai_api_key
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
JWT_SECRET_KEY=your_jwt_secret
DATABASE_URL=sqlite+aiosqlite:///./app.db          # 로컬 SQLite (기본값)
# DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname  # Cloud SQL 사용 시
ENVIRONMENT=development
ADMIN_EMAILS=admin@example.com

# frontend/.env.local
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

**백엔드 실행**

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# http://localhost:8000/docs (Swagger UI)
```

**프론트엔드 실행**

```bash
cd frontend
npm install
npm run dev
# http://localhost:3000
```

**패널 데이터 적재 (RAG 모드 사용 시, 최초 1회)**

> **현재 상태:** Cloud SQL에 500명 패널 + 5,373개 메모리(1536차원 임베딩) 적재 완료. 재적재가 필요한 경우에만 아래 명령 실행.

```bash
# Cloud SQL Proxy 실행 필요
cloud-sql-proxy bdml-492404:asia-northeast3:bigmarlab-db --port=5432

cd backend
python -m scripts.seed_panels
# 확인 없이 자동 적재, 중복 건너뜀, 전체 500명 약 10~20분
# CSV 원본(backend/raw/fgi_500_panels.csv) 필요 — 별도 백업에서 복원
```

### Docker (배포)

```bash
# 백엔드
docker build -t interactive-multiagent-backend ./backend
docker run -p 8000:8080 \
  -e OPENAI_API_KEY=your_key \
  -e JWT_SECRET_KEY=your_secret \
  -e DATABASE_URL=your_db_url \
  -e CORS_ORIGINS=http://localhost:3000 \
  interactive-multiagent-backend

# 프론트엔드
docker build -t interactive-multiagent-frontend ./frontend \
  --build-arg NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
docker run -p 3000:3000 interactive-multiagent-frontend
```

## 5. DB 스키마

| 테이블 | 설명 | 주요 컬럼 |
|--------|------|-----------|
| **users** | 사용자 | id(UUID), email, hashed_pw, name, role, is_active |
| **refresh_tokens** | JWT 리프레시 토큰 | token_hash(SHA-256), expires_at, is_revoked |
| **projects** | 연구 세션 | brief, refined, market_report, agents, meeting_topic, meeting_messages, minutes (각 JSONB/Text) |
| **project_edits** | 수정 이력 감사 로그 | field, old_value, new_value |
| **activity_logs** | 토큰 사용량 추적 | action, model, input_tokens, output_tokens, cost_usd |
| **panels** | FGI 패널 500명 | panel_id, cluster, age, gender, 8개 행동 차원(dim_*), scratch(JSONB) |
| **panel_memories** | 패널별 자전적 기억 | panel_id, category(14종), text, importance, embedding(1536차원) |

## 6. 유지보수

- **CI/CD:** GitHub Actions + GCP Workload Identity Federation → Cloud Run 자동 배포 (`deploy.yml`)
  - OIDC 기반 인증으로 서비스 계정 키 불필요
  - 필요 secrets: `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `BACKEND_URL`, `FRONTEND_URL`

- **API Document:** `http://localhost:8000/docs` (FastAPI 자동 생성 Swagger UI)

- **Test Strategy:**
  - 현재 E2E 위주 수동 검증 (각 Phase 입출력 확인)
  - 핵심 검증 대상: SSE 스트림 단절 여부, RAG 패널 선택 정합성, 페르소나 합성 일관성, 단계 초기화 규칙 (상위 단계 변경 시 하위 단계 결과 리셋), RAG 영감 연쇄 (다른 참여자 발언에 의한 메모리 검색 변화)

- **주의사항:**
  - 사용량 추적은 서버 메모리 기반 → 프로세스 재시작 시 초기화 (ActivityLog DB 기록은 유지)
  - 프론트엔드 상태는 `sessionStorage` 기반 → 브라우저 세션 종료 시 소실 (프로젝트 DB 저장으로 복원 가능)
  - 회의 시뮬레이션·회의록은 AI 생성 결과이므로 실제 의사결정 전 반드시 검토 필요
  - RAG 모드 사용 시 Cloud SQL에 패널 데이터 사전 적재 필요
