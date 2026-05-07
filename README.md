# Ditto

> 소비자를 가장 가까운 곳에 두고 대화하고, 회의하며, 인사이트를 얻는 **리서치 플랫폼**.

Ditto 는 단발성 설문/인터뷰의 한계를 넘어, 응답 데이터를 **에이전트로 보존**하고 **1:1 대화 + FGI** 를 통해 지속적으로 성장시켜 가며 심층 인사이트를 발굴하도록 돕습니다.

> **상태:** Active migration — 이전 프로젝트(빅데이터마케팅랩 BDML-FGI)는 [`archive/bdml-fgi/`](./archive/bdml-fgi/) 에 동결 보존됨. 마이그레이션 plan: [`docs/plans/active/0001-archive-and-bootstrap-ditto.md`](./docs/plans/active/0001-archive-and-bootstrap-ditto.md).

## MVP 범위 (현재)

1. **에이전트 생성 — 6-Lens 데이터 구조화**
   - Twin-2K-500 한국어 응답(우선 30명) → 234문항 → L1~L6(경제·의사결정·동기·사회·가치·시간) + 정성 그룹
   - Scoring Engine (역채점 / 경제 수치화 / 능력치)
   - Hybrid Persona Prompt (수치 가이드 + 원문 가이드)
2. **1:1 대화** — SSE 메신저, 답변 인용 + 신뢰도 시각화
3. **FGI** — 다자 회의 (사용자 토론 개입 가능)
4. **에이전트 성능 평가 대시보드** (Recharts)
   - **Identity**: V1 응답 동기화율 · V2 모델 신뢰도 · V3 페르소나 독립성
   - **Logic**: V4 인격 자연스러움 · V5 상황 대응 일관성

## 비범위 (Out of Scope)

- 실시간 음성 회의 (텍스트 기반 FGI 만 지원)
- 다국어 지원 (한국어 전용)
- Survey 질문 자동 생성·배포 (v1.0 Phase 6 에서 도입)
- 다중 워크스페이스 / 조직 모델 (v1.1)

## Tech Stack

| 영역 | 기술 |
|---|---|
| Frontend | Next.js 14 (App Router) · TypeScript 5 · Tailwind 3.4 · Pretendard · Recharts |
| Backend | FastAPI 0.115+ (Python 3.12) · SQLAlchemy 2.0 async · Alembic · LangGraph + LangChain |
| LLM | OpenAI `gpt-4o` · `text-embedding-3-small` · Anthropic `claude-3.5-sonnet` (V2 평가 전용) |
| DB | Cloud SQL PostgreSQL (운영) · SQLite aiosqlite (로컬 개발) |
| 인증 | JWT + httpOnly 쿠키 + bcrypt |
| 배포 | GCP Cloud Run · GitHub Actions + Workload Identity Federation (Phase 6 에서 신규 작성) |

## 디렉터리 구조

```
.
├── archive/bdml-fgi/   # 동결된 BDML-FGI 코드/문서 (read-only)
├── backend/            # (Phase 2 이후 신규) FastAPI
├── frontend/           # (Phase 2 이후 신규) Next.js
├── docs/               # SSOT — PRD, Architecture, Data Model, API Spec, Eval Spec, 6-Lens Mapping, ADRs, plans
├── DESIGN.md           # 디자인 토큰 + 컴포넌트 규칙 (UI 작업 시 SSOT)
├── CLAUDE.md           # 에이전트 컨벤션
└── .cursorrules        # Cursor 워크플로우 규칙 (Plan-First)
```

자세한 트리 구조는 [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) 참조.

## SSOT 문서

다음은 단일 진실 공급원입니다. 코드와 어긋나면 **문서를 먼저 갱신**한 뒤 코드를 수정합니다.

- [`docs/PRD.md`](./docs/PRD.md) — 제품 요구사항
- [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) — 모듈 경계, 데이터 흐름, 외부 의존성
- [`docs/DATA_MODEL.md`](./docs/DATA_MODEL.md) — 도메인 모델, DB 스키마, 마이그레이션 규칙
- [`docs/api-spec.md`](./docs/api-spec.md) — 엔드포인트 명세 (SSE/NDJSON 포함)
- [`docs/EVAL_SPEC.md`](./docs/EVAL_SPEC.md) — V1~V5 평가 지표 정의 · 자극 세트 · 채점 공식
- [`docs/6-LENS_MAPPING.md`](./docs/6-LENS_MAPPING.md) — Twin-2K-500 234문항 → L1~L6 매핑 테이블
- [`docs/adr/`](./docs/adr/) — 아키텍처 결정 기록
- [`DESIGN.md`](./DESIGN.md) — 디자인 토큰 + 컴포넌트 규칙

## 빠른 시작

> **현재 단계 (2026-05-07):** Phase 0+1 진행 중. 코드 디렉터리(`backend/`, `frontend/`) 는 Phase 2 진입 시 생성됩니다.

Phase 2 이후 가이드는 [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) 의 "로컬 실행" 섹션을 참조하세요.

## 라이선스 / 데이터

- 본 리포의 코드는 비공개 (private). 외부 공개 시점은 미정.
- **개인정보 보호:** 패널 응답 원본·임베딩 캐시·DB 덤프는 **절대 git 커밋 금지**. `.gitignore` 가 강제하는 항목 외에도 신중히 다룰 것.
- Twin-2K-500 데이터셋 출처: Toubia, O., Gui, G. Z., Peng, T., Merlau, D. J., Li, A., & Chen, H. (2025). *Database Report: Twin-2K-500.* Marketing Science, 44(6), 1446–1455.
