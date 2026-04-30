# Playwright 1회성 UI 감사

빅데이터마케팅랩 프론트엔드의 주요 페이지를 자동으로 캡처하고 접근성/콘솔 에러를 점검하여 `docs/ui-audit.md` 작성에 필요한 원자료를 만든다.

## 산출물

- `screenshots/desktop/<route>.png` — 1440×900 풀페이지 캡처
- `screenshots/mobile/<route>.png` — 390×844 풀페이지 캡처
- `audit-results.json` — axe-core 위반 + 콘솔 에러 + 4xx/5xx 네트워크 응답
- 콘솔 출력 — P1(critical/serious) 위반 요약

## 사전 조건

1. **백엔드 가동**: `cd backend && uvicorn main:app --reload --port 8000`
2. **프론트엔드 가동**: `cd frontend && npm run dev` (기본 포트 3000)
3. **Playwright Chromium 브라우저 1회 설치**:
   ```bash
   npx --yes playwright@latest install chromium
   ```

   `playwright` 패키지는 `npx`가 자동으로 임시 설치한다. 프론트 `package.json`에는 추가하지 않는다.

## 실행

기본:

```bash
node scripts/playwright-audit/audit.mjs
```

다른 호스트를 감사하고 싶을 때:

```bash
node scripts/playwright-audit/audit.mjs --base https://staging.bdml.example
```

## 인증이 필요한 페이지 감사

Phase 1~5(`/research-input` 등)와 `/dashboard`는 로그인이 필요하다. 환경변수로 테스트 계정을 주입하면 자동 로그인 후 감사한다.

```bash
AUDIT_EMAIL=your@hanyang.ac.kr AUDIT_PASSWORD=yourpassword \
  node scripts/playwright-audit/audit.mjs
```

미설정 시 공개 페이지(`/`, `/login`, `/register`, `/lab`)만 감사한다.

## axe-core

CDN(`cdn.jsdelivr.net/npm/axe-core@4/axe.min.js`)을 페이지에 주입하여 동작한다. 별도 npm 의존성을 설치하지 않는다. 오프라인 환경에서는 실행할 수 없다.

## 결과 → 보고서

`audit-results.json`과 `screenshots/`를 종합해 `docs/ui-audit.md`에 페이지별 P1/P2/P3 정리 + 수정 제안 + 관련 컴포넌트 경로를 작성한다.
