/**
 * Playwright 1회성 UI 감사 스크립트.
 *
 * 빅데이터마케팅랩 프론트엔드의 주요 페이지를
 * 데스크톱(1440×900) + 모바일(390×844) 두 뷰포트로 캡처하고,
 * axe-core로 접근성 위반을 추출하여 audit-results.json에 저장한다.
 *
 * 사용:
 *   1. 백엔드: cd backend && uvicorn main:app --reload --port 8000
 *   2. 프론트: cd frontend && npm run dev
 *   3. Playwright 브라우저 설치 (1회):
 *        npx --yes playwright@latest install chromium
 *   4. 감사 실행 (CLI 인자로 도메인 경로 지정 가능):
 *        node scripts/playwright-audit/audit.mjs
 *        node scripts/playwright-audit/audit.mjs --base http://localhost:3000
 *
 * 출력:
 *   - scripts/playwright-audit/screenshots/<viewport>/<route>.png
 *   - scripts/playwright-audit/audit-results.json
 *   - 콘솔: 페이지별 P1 위반 요약
 *
 * 인증 필요한 페이지(/dashboard, /research-input 등)는
 *   AUDIT_EMAIL / AUDIT_PASSWORD 환경변수 설정 시 자동 로그인 후 캡처.
 */

import { chromium } from 'playwright';
import { promises as fs } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SHOT_ROOT = path.join(__dirname, 'screenshots');
const RESULT_PATH = path.join(__dirname, 'audit-results.json');

// ── 설정 ─────────────────────────────────────────────────────────────────
const args = process.argv.slice(2);
const baseFlagIdx = args.indexOf('--base');
const BASE_URL = baseFlagIdx >= 0 ? args[baseFlagIdx + 1] : 'http://localhost:3000';

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 },
];

const PUBLIC_ROUTES = [
  { path: '/', name: 'landing' },
  { path: '/login', name: 'login' },
  { path: '/register', name: 'register' },
  { path: '/lab', name: 'lab-list' },
];

const AUTH_ROUTES = [
  { path: '/dashboard', name: 'dashboard' },
  { path: '/research-input', name: 'phase1-research-input' },
  { path: '/market-research', name: 'phase2-market-research' },
  { path: '/agent-setup', name: 'phase3-agent-setup' },
  { path: '/meeting', name: 'phase4-meeting' },
  { path: '/minutes', name: 'phase5-minutes' },
];

const AUDIT_EMAIL = process.env.AUDIT_EMAIL || '';
const AUDIT_PASSWORD = process.env.AUDIT_PASSWORD || '';

// ── axe-core 주입 ────────────────────────────────────────────────────────
// CDN에서 axe-core를 inline으로 페이지에 주입하여 별도 npm 의존성 없이 동작.
const AXE_CDN = 'https://cdn.jsdelivr.net/npm/axe-core@4/axe.min.js';

async function injectAxe(page) {
  await page.addScriptTag({ url: AXE_CDN });
}

async function runAxe(page) {
  return await page.evaluate(async () => {
    // @ts-ignore — runtime axe 글로벌
    const result = await window.axe.run({
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'best-practice'] },
    });
    return {
      url: window.location.href,
      violations: result.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        description: v.description,
        help: v.help,
        nodes: v.nodes.length,
      })),
    };
  });
}

// ── 페이지 캡처 + 감사 ────────────────────────────────────────────────────
async function auditPage(context, viewport, route, networkErrors) {
  const page = await context.newPage();
  const consoleErrors = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text());
  });
  page.on('response', (resp) => {
    if (resp.status() >= 400) {
      networkErrors.push({ url: resp.url(), status: resp.status() });
    }
  });

  const url = BASE_URL + route.path;
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
  } catch (e) {
    console.log(`  ✗ ${viewport.name}/${route.name} — 진입 실패: ${e.message}`);
    await page.close();
    return null;
  }

  await page.waitForTimeout(800); // 애니메이션·SSR 안정화

  // 스크린샷
  const dir = path.join(SHOT_ROOT, viewport.name);
  await fs.mkdir(dir, { recursive: true });
  const shotPath = path.join(dir, `${route.name}.png`);
  await page.screenshot({ path: shotPath, fullPage: true });

  // 접근성 검사
  let axeResult = { violations: [], url };
  try {
    await injectAxe(page);
    axeResult = await runAxe(page);
  } catch (e) {
    console.log(`  ! axe 실행 실패 (${route.name}): ${e.message}`);
  }

  await page.close();

  return {
    viewport: viewport.name,
    route: route.name,
    path: route.path,
    screenshot: path.relative(__dirname, shotPath).replace(/\\/g, '/'),
    consoleErrors,
    axe: axeResult,
  };
}

// ── 인증 (선택) ──────────────────────────────────────────────────────────
async function attemptLogin(context) {
  if (!AUDIT_EMAIL || !AUDIT_PASSWORD) {
    console.log('[auth] AUDIT_EMAIL/AUDIT_PASSWORD 미설정 — 비인증 페이지만 감사');
    return false;
  }
  const page = await context.newPage();
  try {
    await page.goto(BASE_URL + '/login', { waitUntil: 'networkidle' });
    await page.fill('#login-email', AUDIT_EMAIL);
    await page.fill('#login-password', AUDIT_PASSWORD);
    await Promise.all([
      page.waitForURL((url) => !url.pathname.startsWith('/login'), { timeout: 10000 }),
      page.click('#login-submit'),
    ]);
    console.log('[auth] 로그인 성공');
    return true;
  } catch (e) {
    console.log(`[auth] 로그인 실패: ${e.message} — 비인증 페이지만 감사`);
    return false;
  } finally {
    await page.close();
  }
}

// ── 메인 ─────────────────────────────────────────────────────────────────
async function main() {
  console.log(`[audit] BASE_URL=${BASE_URL}`);
  console.log(`[audit] 스크린샷 저장: ${SHOT_ROOT}`);

  const browser = await chromium.launch();
  const results = [];
  const networkErrors = [];

  for (const viewport of VIEWPORTS) {
    console.log(`\n=== Viewport: ${viewport.name} (${viewport.width}×${viewport.height}) ===`);
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      deviceScaleFactor: 1,
    });

    // 공개 페이지
    for (const route of PUBLIC_ROUTES) {
      console.log(`  → ${route.path}`);
      const r = await auditPage(context, viewport, route, networkErrors);
      if (r) results.push(r);
    }

    // 인증 페이지
    const loggedIn = await attemptLogin(context);
    if (loggedIn) {
      for (const route of AUTH_ROUTES) {
        console.log(`  → ${route.path} (auth)`);
        const r = await auditPage(context, viewport, route, networkErrors);
        if (r) results.push(r);
      }
    }

    await context.close();
  }

  await browser.close();

  // ── 결과 요약 ──
  const summary = {
    base_url: BASE_URL,
    generated_at: new Date().toISOString(),
    pages_audited: results.length,
    network_errors: networkErrors,
    results,
  };
  await fs.writeFile(RESULT_PATH, JSON.stringify(summary, null, 2), 'utf-8');
  console.log(`\n[audit] 결과: ${RESULT_PATH}`);

  // 콘솔 P1 요약
  console.log('\n=== P1 / Critical 위반 요약 ===');
  let p1Count = 0;
  for (const r of results) {
    const critical = r.axe.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );
    if (critical.length || r.consoleErrors.length) {
      console.log(`\n[${r.viewport}] ${r.route} (${r.path})`);
      for (const v of critical) {
        console.log(`  - axe ${v.impact} : ${v.id} — ${v.help} (${v.nodes} elements)`);
        p1Count++;
      }
      for (const err of r.consoleErrors.slice(0, 3)) {
        console.log(`  - console error: ${err.slice(0, 120)}`);
      }
    }
  }
  console.log(`\n총 critical/serious 위반: ${p1Count}건`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
