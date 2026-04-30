'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

export default function LandingPage() {
  const { user, isLoading } = useAuth();
  const router = useRouter();

  // 인증 사용자는 대시보드로 자동 이동
  useEffect(() => {
    if (!isLoading && user) {
      router.replace('/dashboard');
    }
  }, [user, isLoading, router]);

  if (isLoading || user) {
    return (
      <div className="landing-loading">
        <div className="auth-loading__spinner" />
      </div>
    );
  }

  return (
    <div className="landing-page">
      {/* 상단 네비 */}
      <header className="landing-header">
        <div className="landing-header__inner">
          <div className="landing-header__brand">
            <img src="/logo.png" alt="BDML" />
          </div>
          <nav className="landing-header__nav">
            <Link href="/lab" className="landing-header__nav-link">
              실험실
            </Link>
            <Link href="/login" className="landing-header__nav-link landing-header__nav-link--cta">
              로그인
            </Link>
          </nav>
        </div>
      </header>

      {/* 히어로 */}
      <section className="landing-hero">
        <div className="landing-hero__inner">
          <span className="landing-hero__eyebrow">Big Data Marketing Lab</span>
          <h1 className="landing-hero__title">
            AI 에이전트로
            <br />
            <span className="landing-hero__title-accent">정성조사를 자동화</span>합니다
          </h1>
          <p className="landing-hero__subtitle">
            연구 정보를 입력하면 AI가 시장조사 → 패널 구성 → FGI 회의 시뮬레이션 → 회의록까지
            자동으로 수행합니다.
          </p>
          <div className="landing-hero__cta">
            <Link href="/login" className="landing-cta landing-cta--primary">
              로그인하고 시작하기
            </Link>
            <Link href="/lab" className="landing-cta landing-cta--secondary">
              실험실 체험 →
            </Link>
          </div>
        </div>
      </section>

      {/* 기능 소개 */}
      <section className="landing-features">
        <div className="landing-features__inner">
          <h2 className="landing-section-title">5단계 자동화 흐름</h2>
          <div className="landing-features__grid">
            <div className="landing-feature">
              <div className="landing-feature__num">1</div>
              <h3 className="landing-feature__title">연구 정보 입력</h3>
              <p className="landing-feature__desc">
                연구 주제·타깃·핵심 질문을 자연어로 입력하면 AI가 브리프를 정제합니다.
              </p>
            </div>
            <div className="landing-feature">
              <div className="landing-feature__num">2</div>
              <h3 className="landing-feature__title">시장조사 자동화</h3>
              <p className="landing-feature__desc">
                Naver·OpenAI 검색을 결합해 시장 동향 보고서를 자동으로 합성합니다.
              </p>
            </div>
            <div className="landing-feature">
              <div className="landing-feature__num">3</div>
              <h3 className="landing-feature__title">패널 구성</h3>
              <p className="landing-feature__desc">
                실제 설문 패널 500명 풀에서 RAG 임베딩으로 주제 관련 N명을 선정합니다.
              </p>
            </div>
            <div className="landing-feature">
              <div className="landing-feature__num">4</div>
              <h3 className="landing-feature__title">FGI 시뮬레이션</h3>
              <p className="landing-feature__desc">
                LangGraph 상태머신과 RAG 메모리로 실시간 발언을 스트리밍합니다.
              </p>
            </div>
            <div className="landing-feature">
              <div className="landing-feature__num">5</div>
              <h3 className="landing-feature__title">회의록 생성</h3>
              <p className="landing-feature__desc">
                전체 발언을 구조화된 마크다운 회의록으로 자동 정리해 내보냅니다.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 실험실 카드 */}
      <section className="landing-lab-banner">
        <div className="landing-lab-banner__inner">
          <div className="landing-lab-banner__text">
            <span className="landing-lab-banner__tag">EXPERIMENT</span>
            <h2 className="landing-lab-banner__title">
              Twin-2K-500 디지털 트윈과 1:1 대화
            </h2>
            <p className="landing-lab-banner__desc">
              Toubia et al. (2025)의 Twin-2K-500 데이터셋 기반 디지털 트윈 페르소나와
              메신저 형태로 대화해 보세요. 로그인 없이 바로 체험할 수 있습니다.
            </p>
          </div>
          <Link href="/lab" className="landing-lab-banner__cta">
            실험실로 이동 →
          </Link>
        </div>
      </section>

      {/* 푸터 */}
      <footer className="landing-footer">
        <div className="landing-footer__inner">
          <div className="landing-footer__brand">
            <strong>Big Data Marketing Lab</strong>
            <span>한양대학교 경영대학</span>
          </div>
          <div className="landing-footer__meta">
            © {new Date().getFullYear()} BDML. AI 기반 정성조사 시뮬레이션 연구.
          </div>
        </div>
      </footer>
    </div>
  );
}
