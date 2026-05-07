# ADR-0001: Frontend/Backend 모노레포 분리

## Status

Accepted (2026-04-10)

## Context

초기 PoC는 Next.js 단일 앱에서 API Routes를 통해 OpenAI/RAG를 호출하는 구조였다. 다음 한계가 드러났다:

- LLM 호출이 길어지면 Vercel/Cloud Run의 함수 타임아웃에 걸림.
- 패널 임베딩(1536차원 × 5,373건)을 Node.js 메모리에 적재하기 어려움.
- pandas/numpy 기반 패널 가공 로직을 Python으로 작성하는 것이 효율적.
- 인증·DB 연결 풀·SSE 스트리밍을 한 프로세스에서 다루기 부담.

## Decision

`frontend/`(Next.js)와 `backend/`(FastAPI)를 **모노레포 안에서 완전히 분리**한다. 두 패키지는 각자의 Dockerfile, 의존성, 배포 파이프라인을 갖는다.

- `frontend/` — UI 전담. LLM/DB 직접 호출 금지.
- `backend/` — LLM·데이터 전담. UI 로직 인지 금지.
- 통신: HTTP/JSON + SSE + NDJSON. 프론트는 `frontend/src/lib/api.ts`를 통해서만 호출.

## Consequences

**긍정적**

- LLM 작업 타임아웃을 백엔드 단에서 제어 가능 (Cloud Run min-instances, 동시성 조정).
- Python 생태계(LangGraph, pandas, OpenAI SDK)를 자유롭게 활용.
- 프론트는 정적 자산처럼 빠르게 빌드/배포.
- Pydantic ↔ TypeScript 타입 동기화로 계약을 명시적으로 관리.

**부정적**

- 두 환경(Node, Python)을 병행 운영. 개발 시 두 터미널 필요.
- 타입 동기화가 깨지기 쉬움 → Workflow Rules에 동기화 강제.
- CORS, 인증 토큰 전송 방식(httpOnly 쿠키)을 별도로 설계해야 함.

## 관련

- [ARCHITECTURE.md](../ARCHITECTURE.md)
