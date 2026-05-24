'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { Logo } from '@/components/layout/Logo';
import { useAuth } from '@/contexts/AuthContext';

// 인증 상태에 따라 1차 CTA의 도착지가 달라진다 — 로그인 됨이면 프로젝트 목록, 아니면 회원가입.
function useStartHref() {
  const { user } = useAuth();
  return user ? '/projects' : '/register';
}

// 상단 우측 액션 — 비로그인: [회원가입] [로그인] [데모 사용해보기], 로그인: [내 프로젝트] [로그아웃] [데모 사용해보기]
// 데모는 항상 노출(주요 CTA), 로그인/회원가입은 인증 상태에 따라 스왑.
function HeaderActions() {
  const { user, logout } = useAuth();
  return (
    <div className="flex items-center gap-1.5">
      {user ? (
        <>
          <HeaderLink href="/projects">내 프로젝트</HeaderLink>
          <button
            onClick={logout}
            className="px-3.5 py-1.5 rounded-lg text-sm font-medium text-text-muted hover:text-text-primary hover:bg-bg transition"
          >
            로그아웃
          </button>
        </>
      ) : (
        // 회원가입은 별도 노출하지 않음 — 로그인 페이지에서 "계정이 없으신가요? 회원가입" 링크로 이어짐.
        <HeaderLink href="/login">로그인</HeaderLink>
      )}
      <Link
        href="/demo"
        className="ml-1 inline-flex items-center justify-center px-4 py-1.5 rounded-lg text-sm font-medium text-white
                   bg-gradient-to-br from-ditto-indigo to-ditto-violet
                   shadow-[0_2px_8px_rgba(79,70,229,0.25)]
                   hover:opacity-90 active:scale-[0.98] transition"
      >
        데모 사용해보기
      </Link>
    </div>
  );
}

function HeaderLink({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className="px-3.5 py-1.5 rounded-lg text-sm font-medium text-text-muted hover:text-text-primary hover:bg-bg transition"
    >
      {children}
    </Link>
  );
}

// ───────── Hero FGI 미리보기: 라운드 발화를 순차 재생 → 끝나면 다시 처음부터 ─────────

type PreviewMessage =
  | { type: 'moderator'; text: string }
  | { type: 'user'; text: string }
  | { type: 'agent'; name: string; colorClass: string; text: string };

const PREVIEW_MESSAGES: PreviewMessage[] = [
  { type: 'moderator', text: '라운드를 시작합니다. 최근 해지한 구독 서비스가 있다면 이유를 공유해주세요.' },
  { type: 'agent', name: '김서연', colorClass: 'text-ditto-violet', text: '저는 OTT 하나를 해지했어요. 한 달에 2~3번밖에 안 봤는데 월 13,900원이라... 시간당 비용 계산하면 극장보다 비싸더라고요.' },
  { type: 'agent', name: '박지훈', colorClass: 'text-pink-500', text: '저는 가격보다 감정적인 부분이 컸어요. 콘텐츠가 제 취향이랑 안 맞아지면서 "나를 위한 서비스"란 느낌이 사라졌거든요.' },
  { type: 'user', text: '해지를 결심하는 데 가장 결정적인 순간은 언제였나요?' },
  { type: 'agent', name: '이하은', colorClass: 'text-amber-500', text: '두 분 다 공감해요. 저는 해지까진 안 갔지만 "이걸 왜 쓰고 있지?" 싶은 순간이 있었어요. 근데 해지 버튼이 너무 깊숙이 숨겨져 있어서 귀찮아서 유지한 적도 있어요.' },
  { type: 'agent', name: '최준호', colorClass: 'text-emerald-500', text: '저는 아직 해지한 적 없어요. 주변에서 다 쓰니까 안 쓰면 대화에 못 끼거든요. 비용보다 소속감 때문에 유지하는 것 같아요.' },
  { type: 'moderator', text: '흥미롭네요. 비용 효율, 감성 이탈, UX 마찰, 사회적 소속감 — 네 가지 관점이 나왔습니다.' },
  { type: 'user', text: '그러면 다시 재구독하게 만드는 요인은 뭘까요?' },
  { type: 'agent', name: '김서연', colorClass: 'text-ditto-violet', text: '저는 독점 콘텐츠요. "이건 여기서만 볼 수 있다"는 게 확실하면 다시 결제할 의향 있어요.' },
  { type: 'agent', name: '박지훈', colorClass: 'text-pink-500', text: '무료 체험 기간을 다시 주면 좋겠어요. 한 달 써보고 결정할 수 있으면 부담이 줄어들거든요.' },
  { type: 'agent', name: '최준호', colorClass: 'text-emerald-500', text: '친구가 "이거 꼭 봐야 해"라고 하면 바로 재구독해요. SNS에서 화제가 되는 것도 큰 영향이 있어요.' },
  { type: 'moderator', text: '좋습니다. 다음 라운드로 넘어가겠습니다. 주제: 구독료 인상 시 반응.' },
];

type Visible = { msg: PreviewMessage; key: number };
type Typing = { who: 'moderator' | 'user' | 'agent'; name?: string } | null;

function HeroLivePreview() {
  // 메시지 0번(모더레이터 오프닝)부터 자연스럽게 시작. 컨테이너 자체는 아래 min-h 로
  // 처음부터 큰 사이즈가 고정되어 있어서 "단계적으로 자라는" 인상은 안 생긴다.
  const [visible, setVisible] = useState<Visible[]>([]);
  const [typing, setTyping] = useState<Typing>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const timeouts = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    // 채팅 스크롤이 최신 메시지를 따라가도록.
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [visible, typing]);

  useEffect(() => {
    let cancelled = false;
    let keyCounter = 0;

    const schedule = (fn: () => void, delay: number) => {
      const t = setTimeout(() => {
        if (!cancelled) fn();
      }, delay);
      timeouts.current.push(t);
    };

    const step = (idx: number) => {
      if (cancelled) return;
      if (idx >= PREVIEW_MESSAGES.length) {
        // 루프: 잠시 멈췄다가 처음부터 다시.
        schedule(() => {
          setVisible([]);
          keyCounter = 0;
          schedule(() => step(0), 1000);
        }, 2000);
        return;
      }
      const msg = PREVIEW_MESSAGES[idx];
      const who: NonNullable<Typing>['who'] = msg.type;
      const name = msg.type === 'agent' ? msg.name : msg.type === 'user' ? '리서처' : '모더레이터';
      setTyping({ who, name });

      const typingDelay = msg.type === 'user' ? 800 : 1200;
      schedule(() => {
        setTyping(null);
        const key = keyCounter++;
        setVisible(v => [...v, { msg, key }]);
        const nextDelay = 1800 + Math.random() * 1200;
        schedule(() => step(idx + 1), nextDelay);
      }, typingDelay);
    };

    schedule(() => step(0), 800);
    return () => {
      cancelled = true;
      timeouts.current.forEach(clearTimeout);
      timeouts.current = [];
    };
  }, []);

  return (
    // text-left — hero <section>의 text-center 가 내려와서 말풍선 안 텍스트까지
    // 가운데 정렬되는 걸 이 경계에서 끊는다. 채팅 메타포는 좌측 정렬이 기본.
    <div className="mt-14 w-full max-w-6xl rounded-xl p-6 pb-0 relative shadow-elevated text-left
                    bg-gradient-to-br from-[#1E1B4B] to-[#312E81]
                    ring-1 ring-white/5">
      {/* 윈도우 도트 */}
      <div className="flex gap-1.5 mb-4">
        <span className="w-2.5 h-2.5 rounded-full bg-error/90" />
        <span className="w-2.5 h-2.5 rounded-full bg-warning/90" />
        <span className="w-2.5 h-2.5 rounded-full bg-success/90" />
      </div>
      <div className="bg-surface rounded-t-[10px] p-6 flex gap-5 min-h-[520px]">
        {/* 채팅 영역 — min-w-0 으로 flex-1 이 빈 상태에서도 안 흔들리게. */}
        <div
          ref={scrollRef}
          className="flex-1 min-w-0 flex flex-col gap-3 overflow-y-auto max-h-[520px] scrollbar-none"
          style={{ scrollbarWidth: 'none' }}
        >
          <div className="text-xs font-bold text-text-muted mb-1">FGI · 구독 서비스 소비 패턴</div>
          {visible.map(({ msg, key }) => (
            <PreviewBubble key={key} msg={msg} />
          ))}
          {typing && <TypingBubble who={typing.who} name={typing.name} />}
        </div>

        {/* 참여 에이전트 사이드바 */}
        <div className="w-[220px] border-l border-border pl-5 hidden md:flex flex-col gap-2.5">
          <div className="text-2xs font-bold text-text-muted mb-1">참여 에이전트</div>
          <AgentRow initial="김" name="김서연" cluster="합리적 소비" gradient="from-ditto-indigo to-ditto-violet" active />
          <AgentRow initial="박" name="박지훈" cluster="감성 소비"   gradient="from-pink-500 to-pink-400" />
          <AgentRow initial="이" name="이하은" cluster="가치 지향"   gradient="from-amber-500 to-amber-300" />
          <AgentRow initial="최" name="최준호" cluster="트렌드 민감" gradient="from-emerald-500 to-emerald-400" />
        </div>
      </div>
    </div>
  );
}

function PreviewBubble({ msg }: { msg: PreviewMessage }) {
  if (msg.type === 'agent') {
    return (
      <div className="self-start max-w-[85%] bg-bg rounded-xl px-3.5 py-2.5 text-[13px] leading-snug landing-fade-in-up">
        <div className={`text-2xs font-bold mb-1 ${msg.colorClass}`}>{msg.name}</div>
        {msg.text}
      </div>
    );
  }
  if (msg.type === 'user') {
    return (
      <div className="self-end max-w-[85%] bg-ditto-indigo text-white rounded-xl px-3.5 py-2.5 text-[13px] leading-snug text-right landing-fade-in-up">
        {msg.text}
      </div>
    );
  }
  return (
    <div className="self-end max-w-[90%] bg-surface border border-dashed border-border rounded-xl px-3.5 py-2.5 text-xs text-text-muted text-right landing-fade-in-up">
      <strong className="text-text-secondary">모더레이터</strong> — {msg.text}
    </div>
  );
}

function TypingBubble({ who, name }: { who: NonNullable<Typing>['who']; name?: string }) {
  const isRight = who !== 'agent';
  return (
    <div
      className={`flex items-center gap-2 landing-fade-in-up
                  ${isRight ? 'self-end flex-row-reverse' : 'self-start'}`}
    >
      {name && <span className="text-2xs font-bold text-text-muted">{name}</span>}
      <div className="flex items-center gap-1 bg-bg rounded-xl px-3 py-2.5 w-fit">
        <span className="w-1.5 h-1.5 rounded-full bg-text-muted landing-typing-dot" />
        <span className="w-1.5 h-1.5 rounded-full bg-text-muted landing-typing-dot" style={{ animationDelay: '0.15s' }} />
        <span className="w-1.5 h-1.5 rounded-full bg-text-muted landing-typing-dot" style={{ animationDelay: '0.3s' }} />
      </div>
    </div>
  );
}

function AgentRow({
  initial, name, cluster, gradient, active,
}: { initial: string; name: string; cluster: string; gradient: string; active?: boolean }) {
  return (
    <div className={`flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs ${active ? 'bg-ditto-indigo-light' : ''}`}>
      <div className={`w-7 h-7 rounded-full bg-gradient-to-br ${gradient}
                       flex items-center justify-center text-white text-[11px] font-bold flex-shrink-0`}>
        {initial}
      </div>
      <div>
        <div className="font-semibold text-text-primary">{name}</div>
        <div className="text-2xs text-text-muted">{cluster}</div>
      </div>
    </div>
  );
}

// ───────── 페이지 ─────────

export default function LandingPage() {
  const { isLoading } = useAuth();
  const startHref = useStartHref();

  if (isLoading) return null;

  return (
    <div className="min-h-screen bg-surface text-text-primary">
      {/* ── 고정 네비 ─────────────────────────────────────────────────── */}
      <nav className="fixed inset-x-0 top-0 z-50 backdrop-blur-md bg-white/90 border-b border-border">
        <div className="max-w-[1200px] mx-auto h-14 px-6 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Logo height={28} wordmarkClassName="text-lg bg-gradient-to-br from-ditto-indigo to-ditto-violet bg-clip-text text-transparent" />
          </Link>
          <HeaderActions />
        </div>
      </nav>

      <div className="pt-14">
        {/* ── Hero ─────────────────────────────────────────────────── */}
        {/* 히어로 컨텐츠 컨테이너를 채팅 미리보기와 동일한 max-w-6xl 로 고정 →
            상단(뱃지·타이틀·CTA)과 하단(채팅창)이 같은 가로폭 안에서 정렬되어,
            애니메이션 시작~종료 내내 폭이 안 흔들리도록. */}
        <section className="landing-hero-glow relative flex flex-col items-center justify-center text-center px-6 pt-20 pb-16 overflow-hidden">
          <div className="relative z-10 flex flex-col items-center w-full max-w-6xl mx-auto">
            {/* 핵심 키워드 3개를 독립 칩으로 분리 — 서비스 범위를 한눈에 인지시키기 위해. */}
            <div className="flex flex-wrap justify-center gap-2 mb-5">
              {['AI 소비자 패널', 'FGI', '인사이트 보고서'].map((kw) => (
                <span
                  key={kw}
                  className="px-3.5 py-1.5 rounded-full text-2xs font-medium text-ditto-indigo
                             bg-gradient-to-r from-ditto-indigo-light to-ditto-violet-light
                             border border-ditto-indigo/10"
                >
                  {kw}
                </span>
              ))}
            </div>
            <h1 className="text-[clamp(32px,5vw,52px)] leading-[1.15] font-extrabold tracking-[-1.5px] mb-4">
              소비자를 가장 가까이에서<br />
              이해하는 방법,<br />
              <span className="bg-gradient-to-br from-ditto-indigo to-ditto-violet bg-clip-text text-transparent">
                Mind-Bridge
              </span>
            </h1>
            <p className="text-text-muted max-w-[520px] mb-9 text-[18px] leading-[1.7]">
              AI 에이전트가 실제 소비자처럼 생각하고 대화합니다.<br />
              FGI를 통해 기업이 필요한 인사이트를 빠르고 깊게 발굴하세요.
            </p>
            {/* 단일 주 CTA — 로그인 가입 없이 즉시 제품을 경험할 수 있는 데모로 직결. */}
            <Link
              href="/demo"
              className="inline-flex items-center justify-center px-8 py-3.5 rounded-full text-base font-medium text-white
                         bg-gradient-to-br from-ditto-indigo to-ditto-violet
                         shadow-[0_4px_16px_rgba(79,70,229,0.3)]
                         hover:opacity-90 active:scale-[0.98] transition"
            >
              데모 사용해보기
            </Link>

            <HeroLivePreview />
          </div>
        </section>

        {/* ── Stats ───────────────────────────────────────────────── */}
        <section className="max-w-[900px] mx-auto px-6 py-14 flex flex-wrap justify-center gap-x-16 gap-y-8 border-b border-border">
          <StatItem value="30명"      label="동시 생성 가능 에이전트" />
          <StatItem value="V1~V5"     label="과학적 신뢰성 검증" />
          <StatItem value="AI 에이전트" label="섭외 없이 에이전트로 즉시 FGI" />
          <StatItem value="지속 성장"   label="대화할수록 높아지는 인사이트 품질" />
        </section>

        {/* ── Features ─────────────────────────────────────────────── */}
        <section className="max-w-[1200px] mx-auto px-6 py-20">
          <div className="text-center mb-14">
            <h2 className="text-3xl md:text-[32px] font-extrabold tracking-[-0.5px] mb-3
                           bg-gradient-to-br from-ditto-indigo to-ditto-violet bg-clip-text text-transparent">
              리서치 한 사이클을 한 화면에서
            </h2>
            <p className="text-text-muted text-[18px]">
              의뢰서 작성부터 AI 소비자 생성·품질 검증·FGI 진행·인사이트 보고서까지,<br />
              한 프로젝트 안에서 완결됩니다.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <FeatureCard
              emoji="📝"
              title="의뢰서 → 질문지 자동 설계"
              body={<>조사 목적·타겟·활용 방안을 입력하면 공통·도메인 특화·인터뷰 질문지를 AI가 자동으로 구성합니다.<br />문항은 자유롭게 수정·추가할 수 있어요.</>}
            />
            <FeatureCard
              emoji="🧪"
              title="품질 검증된 AI 소비자"
              body="응답으로 만든 AI 소비자가 실제 사람과 얼마나 닮았는지(닮음), 서로 얼마나 다양한지(다양성)를 통계와 분포도로 보여줍니다."
            />
            <FeatureCard
              emoji="🗣"
              title="FGI 토론 + 인사이트 보고서"
              body={<>여러 AI 소비자가 모더레이터 진행으로 토론합니다.<br />리서처가 중간에 직접 질문을 던질 수 있고, 종료되면 라운드별 인사이트 보고서가 자동 생성됩니다.</>}
            />
          </div>
        </section>

        {/* ── V1~V5 Evaluation ─────────────────────────────────────── */}
        <section className="max-w-[1000px] mx-auto px-6 py-20">
          <h2 className="text-center text-3xl md:text-[32px] font-extrabold tracking-[-0.5px] mb-3
                         bg-gradient-to-br from-ditto-indigo to-ditto-violet bg-clip-text text-transparent">
            5가지 지표로 검증된 에이전트
          </h2>
          <p className="text-center text-text-muted text-[18px] mb-12">
            에이전트가 실제 소비자를 얼마나 정확히 재현하는지 과학적으로 평가합니다.
          </p>
          {/* 가로 1열 — 한 줄에 하나씩 쌓기. 카드 자체가 아이콘+텍스트 가로 레이아웃이라 폭이 넓어도 자연스럽다. */}
          <div className="flex flex-col gap-4">
            <EvalCard emoji="🎯" tint="bg-emerald-50" title="V1. 응답 동기화율"
              body="에이전트 응답이 원본 설문 데이터와 얼마나 일치하는지 의미론적 유사도로 측정합니다." />
            <EvalCard emoji="🔒" tint="bg-blue-50" title="V2. 모델 신뢰도"
              body="AI 엔진이 바뀌어도 동일한 페르소나를 유지하는지 교차 검증합니다." />
            <EvalCard emoji="🧬" tint="bg-amber-50" title="V3. 페르소나 독립성"
              body="30명의 에이전트가 고유한 개성을 유지하며 '모드 붕괴' 없이 구분되는지 검증합니다." />
            <EvalCard emoji="🧠" tint="bg-ditto-violet-light" title="V4. 인격 자연스러움"
              body="제3자가 봤을 때 기계적이지 않고 실제 사람다운 사고를 하는지 평가합니다." />
            <EvalCard emoji="⚖️" tint="bg-pink-50" title="V5. 상황 대응 일관성"
              body="환경이 변해도 본인의 가치관에 따라 논리적으로 판단하는지 반사실적 질문으로 측정합니다." />
          </div>
        </section>

        {/* ── 다크 CTA ─────────────────────────────────────────────── */}
        <section className="relative text-center px-6 py-20 text-white overflow-hidden
                            bg-gradient-to-br from-[#1E1B4B] to-[#312E81]">
          <div className="pointer-events-none absolute -top-48 -right-48 w-[500px] h-[500px] rounded-full bg-ditto-violet/15" />
          <div className="pointer-events-none absolute -bottom-36 -left-36 w-[400px] h-[400px] rounded-full bg-ditto-indigo/10" />
          <div className="relative z-10 max-w-2xl mx-auto">
            <h2 className="text-3xl md:text-[32px] font-extrabold tracking-[-0.5px] mb-3">
              지금 바로 AI 리서치를 시작하세요
            </h2>
            <p className="text-white/70 text-[18px] mb-8">
              의뢰서 작성부터 인사이트 보고서까지,<br />
              Mind-Bridge가 기존 리서치의 시간과 비용을 혁신합니다.
            </p>
            <Link
              href={startHref}
              className="inline-flex items-center justify-center px-10 py-4 rounded-full text-base font-bold
                         bg-white text-ditto-indigo shadow-[0_4px_20px_rgba(0,0,0,0.2)]
                         hover:opacity-90 transition"
            >
              에이전트 생성하고 인사이트 얻기
            </Link>
          </div>
        </section>

        {/* ── Footer ───────────────────────────────────────────────── */}
        <footer className="px-6 py-8 text-center text-xs text-text-muted border-t border-border">
          &copy; {new Date().getFullYear()} Mind-Bridge. AI-Powered Consumer Research Platform.
        </footer>
      </div>
    </div>
  );
}

// ───────── 보조 컴포넌트 ─────────

function StatItem({ value, label }: { value: string; label: string }) {
  return (
    <div className="text-center">
      <div className="text-[36px] font-extrabold tracking-[-1px]
                      bg-gradient-to-br from-ditto-indigo to-ditto-violet
                      bg-clip-text text-transparent">
        {value}
      </div>
      <div className="text-sm text-text-muted mt-1">{label}</div>
    </div>
  );
}

function FeatureCard({ emoji, title, body }: { emoji: string; title: string; body: React.ReactNode }) {
  return (
    <div className="group relative overflow-hidden p-8 rounded-xl border border-border
                    transition hover:-translate-y-1 hover:shadow-elevated hover:border-ditto-indigo/30">
      <div className="absolute inset-x-0 top-0 h-[3px] opacity-0 group-hover:opacity-100 transition
                      bg-gradient-to-r from-ditto-indigo to-ditto-violet" />
      <div className="w-12 h-12 rounded-lg mb-5 text-2xl flex items-center justify-center
                      bg-gradient-to-br from-ditto-indigo-light to-ditto-violet-light">
        {emoji}
      </div>
      <h3 className="text-base font-bold mb-2.5">{title}</h3>
      <p className="text-sm text-text-muted leading-[1.7]">{body}</p>
    </div>
  );
}

function EvalCard({ emoji, tint, title, body }: { emoji: string; tint: string; title: string; body: string }) {
  return (
    <div className="p-6 rounded-xl border border-border flex gap-4 items-start h-full">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-lg flex-shrink-0 ${tint}`}>
        {emoji}
      </div>
      <div>
        <h4 className="text-sm font-bold mb-1">{title}</h4>
        <p className="text-xs text-text-muted leading-[1.5]">{body}</p>
      </div>
    </div>
  );
}
