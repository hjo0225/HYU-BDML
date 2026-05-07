# 빅데이터마케팅랩 — 명세서 인덱스

본 디렉토리는 프로젝트의 **단일 진실 공급원(Single Source of Truth)**입니다. 코드 변경이 명세와 어긋나면 반드시 해당 문서를 먼저 갱신한 뒤 코드를 수정하세요.

## 문서 목록

| 문서 | 용도 | 갱신 트리거 |
|---|---|---|
| [PRD.md](./PRD.md) | 제품 요구사항 (Phase 플로우, 수용 기준) | 새 Phase 추가, 사용자 흐름 변경 |
| [api-spec.md](./api-spec.md) | API 엔드포인트, 요청·응답 스키마, 스트리밍 규약 | 엔드포인트 추가/변경, 페이로드 변경 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 모듈 경계, RAG 파이프라인 런타임, 배포 토폴로지 | frontend/backend 경계 변경, 외부 의존성 추가 |
| [DATA_MODEL.md](./DATA_MODEL.md) | DB 스키마, 마이그레이션, 패널 데이터 파이프라인 | 스키마 변경, 데이터 변환 로직 변경 |
| [adr/](./adr/) | 아키텍처 결정 기록 (Decision Log) | 새 결정 시 새 ADR 추가 |

## ADR 작성 규칙

- 새 아키텍처 결정 시 `adr/NNNN-제목.md` 형식으로 추가 (4자리 일련번호).
- 기존 ADR은 수정하지 말고, 대체될 경우 이전 ADR에 `## Status: Superseded by ADR-XXXX`를 추가합니다.
- 템플릿: Status / Context / Decision / Consequences.

## 갱신 워크플로

1. 코드 변경 전 해당 문서 식별 → 명세 갱신.
2. 코드 수정 → PR.
3. API 시그니처 변경 시 `frontend/src/lib/types.ts` 동기화 필수.
4. DB 스키마 변경 시 Alembic 마이그레이션 + DATA_MODEL.md 동시 갱신.

## 부속 산출물

- [ui-audit.md](./ui-audit.md) — Playwright 1회성 UI 감사 결과 (생성 후 갱신).
