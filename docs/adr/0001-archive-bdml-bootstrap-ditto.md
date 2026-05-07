# ADR-0001 — Archive BDML-FGI, Bootstrap Ditto

## Status

Accepted (2026-05-07)

## Context

기존 리포(`HYU_BDML`)는 **빅데이터마케팅랩(BDML) 5-Phase FGI 시뮬레이션 + Lab Twin-2K-500 1:1 메신저** 두 모듈로 굳어진 상태였다. 새 프로덕트 **Ditto** 는 다음과 같이 본질적으로 다른 컨셉이다.

| 축 | BDML | Ditto |
|---|---|---|
| 포지셔닝 | "정성조사 시뮬레이터" (단발 회의 자동화) | "리서치 플랫폼" (지속적 에이전트 성장) |
| 타겟 사용자 | BDML 연구원 + 데모 | 스타트업/기업 PO·리서처 |
| 에이전트 재료 | FGI 패널 500명 + Twin 50명 | Twin-2K-500 한국어 + 사용자 자체 Survey |
| 에이전트 수명 | 회의 1회 후 폐기 | 장기 메모리 + 대화/FGI 누적 성장 |
| 핵심 산출물 | 회의록 Markdown | 인사이트 + V1~V5 평가 대시보드 |
| FGI 사용자 개입 | 관전만 | 토론 참여 가능 |

리포를 어떻게 재구조화할지 결정해야 했다.

## Decision

### A. 동결 박제 + Fresh build

`backend/`, `frontend/`, `RAG/`, `scripts/`, `docs/*` (`plans/` 제외), 루트 메타파일(`README.md`, `claude.md`, `.cursorrules`) 을 통째로 `archive/bdml-fgi/` 로 `git mv`. Ditto 코드는 신규 디렉터리 트리에서 fresh 시작.

선택한 이유:

1. **격리.** archive 안 코드는 read-only 참조용. 신규 코드가 직접 import 하지 않으므로, 두 프로젝트가 의존성·스키마 충돌을 일으키지 않는다.
2. **선별 이식 가능.** 재사용 가능한 모듈(Twin 적재기·임베더·LangGraph FGI 엔진·Lab citation·인증)은 Phase 2 이후 신규 위치에 명시적으로 복사·재작성한다. 무엇이 옮겨졌는지 git blame 으로 추적 가능.
3. **데이터 자산 보존.** Cloud SQL `panels` / `panel_memories` 테이블은 그대로 둔다. 5,373건 메모리 임베딩 (~$50 비용) 을 잃지 않으면서, 신규 `agents` / `agent_memories` 테이블과 별도 운영.
4. **git 히스토리 유지.** 통째 `git mv` 는 rename 으로 인식되어 `git log --follow` 가 archive 경로로 정상 동작한다.

대안 비교:

- ❌ **별도 리포 분리.** archive 와 Ditto 가 한 GitHub repo 에 같이 있는 편이 리뷰·이슈 추적·CI 설정에 유리.
- ❌ **순차 리팩터.** BDML 코드를 점진적으로 Ditto 형태로 변형. 5-Phase wizard → "프로젝트 자산" 모델 변경, FGI 패널 500명 → Twin-only 변경 등 너무 큰 손질이라 회귀 위험 큼.
- ❌ **archive 폴더 삭제.** 명세 작성을 위해 BDML 의 ADR/구조를 자주 참조해야 한다. 1년간 보관 후 ADR 결정으로 삭제.

### B. plan 위치

마이그레이션 plan 파일 (`docs/plans/active/0001-archive-and-bootstrap-ditto.md`) 은 archive 에 들어가지 않고 Ditto 의 신규 `docs/` 트리에 그대로 남는다. archive 에 옮기면 향후 Ditto 작업 중 plan 을 수정할 때마다 archive 를 건드려야 한다.

### C. DESIGN.md 처리

루트 `DESIGN.md` 는 archive 에 옮기지 않고 그대로 유지한다. 토큰(Indigo `#4F46E5` + Violet `#8B5CF6` + Pretendard) 은 Ditto 에 그대로 채택. Ditto 신규 컴포넌트(`Gauge`, `RadarChart`, `ScoreBadge`, `ChatBubble`, `FGIInterventionInput`) 규칙은 같은 문서에 추가 섹션으로 기재.

## Consequences

### 긍정적

- 신규 코드 작성 시 archive 의 의존성을 신경 쓰지 않아도 된다.
- 명세 SSOT(`docs/`) 가 archive 와 분리되어, Ditto 의 진실 공급원이 깨끗하게 출발한다.
- BDML 의 의사결정 기록(ADR 0001~0006) 을 보존하므로, 향후 "왜 X 가 그랬는지" 질문에 답할 수 있다.

### 부정적

- 디스크 사용량 증가 (archive 가 통째로 남음). 그러나 BDML 의 이미지·캐시·node_modules 는 이미 `.gitignore` 로 제외.
- archive 의 코드를 신규 위치에 다시 적는 비용. **그러나 Ditto 의 데이터 모델·도메인이 다르므로** 어차피 거의 다 새로 써야 했다.
- archive 안 README/CLAUDE 가 git 히스토리에서 검색될 때 혼동 가능. `archive/README.md` 에 명시적 안내 작성으로 완화.

### Open Followups

- **Q5 (워크스페이스 모델):** v1.1 로 미룸.
- **Q7 (`panels` 테이블 통합 vs 병존):** Phase 6 정리 시점에 별도 ADR.

## 관련

- [Plan 0001 — Archive BDML-FGI + Bootstrap Ditto](../plans/active/0001-archive-and-bootstrap-ditto.md)
- archive 위치: [archive/bdml-fgi/](../../archive/bdml-fgi/)
- archive 안 BDML ADR: `archive/bdml-fgi/docs/adr/0001~0006`
