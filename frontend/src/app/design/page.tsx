'use client';

import { useState, type ReactNode } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Select } from '@/components/ui/Select';
import { Card, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Spinner, LoadingState } from '@/components/ui/Spinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageHeader } from '@/components/layout/PageHeader';
import { Gauge } from '@/components/dashboard/Gauge';
import { RadarChart } from '@/components/dashboard/RadarChart';
import { ScoreBadge } from '@/components/dashboard/ScoreBadge';
import { ChatBubble } from '@/components/chat/ChatBubble';
import { FGIInterventionInput } from '@/components/chat/FGIInterventionInput';

// 색상 swatch 정의. CSS 변수에서 직접 읽어 칠한다.
const COLOR_SWATCHES: { name: string; cssVar: string; note?: string }[] = [
  { name: 'bg', cssVar: '--bg', note: '페이지 배경 (indigo tint)' },
  { name: 'surface', cssVar: '--surface', note: '카드·입력창' },
  { name: 'border', cssVar: '--border' },
  { name: 'indigo', cssVar: '--indigo', note: 'brand primary' },
  { name: 'indigo-hover', cssVar: '--indigo-hover' },
  { name: 'indigo-light', cssVar: '--indigo-light' },
  { name: 'violet', cssVar: '--violet', note: 'brand secondary' },
  { name: 'violet-hover', cssVar: '--violet-hover' },
  { name: 'violet-light', cssVar: '--violet-light' },
  { name: 'text-primary', cssVar: '--text-primary' },
  { name: 'text-secondary', cssVar: '--text-secondary' },
  { name: 'text-muted', cssVar: '--text-muted' },
  { name: 'success', cssVar: '--success' },
  { name: 'warning', cssVar: '--warning' },
  { name: 'error', cssVar: '--error' },
];

const RADAR_SAMPLE = [
  { axis: 'sync', value: 0.84 },
  { axis: 'stability', value: 0.72 },
  { axis: 'distinct', value: 0.65 },
  { axis: 'humanity', value: 0.78 },
  { axis: 'reasoning Δ', value: 0.58 },
];

const SELECT_OPTIONS = [
  { value: 'twin', label: 'Twin-2K-500 (30명)' },
  { value: 'survey', label: 'Survey 기반 (Phase 6)' },
  { value: 'soon', label: '신규 (준비 중)', disabled: true },
];

export default function DesignPage() {
  const [fgiActive, setFgiActive] = useState(true);
  const [lastFgiSubmit, setLastFgiSubmit] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-bg py-12 px-6">
      <div className="max-w-6xl mx-auto space-y-10">
        <header>
          <h1 className="text-3xl font-bold text-text-primary">Design Gallery</h1>
          <p className="text-sm text-text-muted mt-2">
            Slice 0a 공통 컴포넌트 시각 확인. DESIGN.md 토큰 + Tailwind 매핑 검증용 페이지 — 프로덕션 네비게이션에는 노출하지 않는다.
          </p>
        </header>

        {/* ──────── Colors ──────── */}
        <Section title="Colors — CSS 변수">
          <div className="grid grid-cols-3 md:grid-cols-5 gap-3">
            {COLOR_SWATCHES.map((s) => (
              <div key={s.name} className="space-y-1.5">
                <div
                  className="h-14 rounded-lg border border-border"
                  style={{ background: `var(${s.cssVar})` }}
                />
                <div className="text-xs font-mono text-text-secondary">{s.name}</div>
                {s.note && (
                  <div className="text-2xs text-text-muted">{s.note}</div>
                )}
              </div>
            ))}
          </div>
        </Section>

        {/* ──────── Typography ──────── */}
        <Section title="Typography">
          <div className="space-y-2">
            <p className="text-xs text-text-muted">xs · 12px · 라벨/배지</p>
            <p className="text-sm text-text-secondary">sm · 14px · 캡션/보조</p>
            <p className="text-base text-text-primary">base · 16px · 본문 기본</p>
            <p className="text-lg text-text-primary font-medium">lg · 18px · 소제목</p>
            <p className="text-3xl text-text-primary font-bold">xl · 30px · 페이지 타이틀</p>
            <p className="text-score font-bold text-ditto-indigo">48</p>
            <p className="text-xs text-text-muted">↑ score · 48px · 게이지 중앙</p>
          </div>
        </Section>

        {/* ──────── Buttons ──────── */}
        <Section title="Button — variant × size">
          <div className="space-y-3">
            {(['primary', 'secondary', 'ghost', 'danger'] as const).map((v) => (
              <div key={v} className="flex items-center gap-3">
                <span className="text-xs text-text-muted font-mono w-20">{v}</span>
                <Button variant={v} size="sm">Small</Button>
                <Button variant={v} size="md">Medium</Button>
                <Button variant={v} size="lg">Large</Button>
                <Button variant={v} disabled>Disabled</Button>
                <Button variant={v} loading>Loading</Button>
              </div>
            ))}
          </div>
          {/* fullWidth: 세로로 쌓을 때 크기 통일 / href: Link 래핑 없이 링크 버튼 */}
          <div className="mt-5 grid md:grid-cols-2 gap-4">
            <div className="w-52 flex flex-col gap-2">
              <p className="text-2xs text-text-muted font-mono">fullWidth (크기 통일)</p>
              <Button fullWidth>품질 평가 실행</Button>
              <Button variant="secondary" fullWidth>1:1 대화하기</Button>
            </div>
            <div className="flex flex-col gap-2">
              <p className="text-2xs text-text-muted font-mono">href → next/link 로 렌더</p>
              <Button href="#" leftIcon={<span>→</span>}>링크 버튼</Button>
            </div>
          </div>
        </Section>

        {/* ──────── Inputs ──────── */}
        <Section title="Input · Select">
          <div className="grid md:grid-cols-2 gap-4">
            <Input label="이메일" name="email" placeholder="your@email.com" />
            <Input label="비밀번호" name="pw" type="password" placeholder="8자 이상" hint="대소문자·숫자 포함 권장" />
            <Input label="에러 상태" name="bad" defaultValue="hello" error="이미 사용 중인 이름입니다" />
            <Input label="left addon" name="url" leftAddon="https://" placeholder="ditto.kr" />
            <Select label="에이전트 소스" name="src" options={SELECT_OPTIONS} placeholder="선택…" defaultValue="" />
            <Select label="비활성" name="dis" options={SELECT_OPTIONS} disabled defaultValue="twin" />
          </div>
        </Section>

        {/* ──────── Textarea ──────── */}
        <Section title="Textarea">
          <div className="grid md:grid-cols-2 gap-4">
            <Textarea label="자유 발화" name="msg" placeholder="메시지를 입력하세요…" />
            <Textarea label="에러 상태" name="bad" defaultValue="너무 짧음" error="10자 이상 입력하세요" rows={2} />
          </div>
        </Section>

        {/* ──────── Badge ──────── */}
        <Section title="Badge — 범용 캡슐 (cluster·status·source)">
          <div className="space-y-3">
            <div className="flex items-center gap-2 flex-wrap">
              {(['neutral', 'indigo', 'violet', 'success', 'warning', 'error'] as const).map((v) => (
                <Badge key={v} variant={v}>{v}</Badge>
              ))}
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <Badge variant="indigo" dot>cluster C2</Badge>
              <Badge variant="success" dot>active</Badge>
              <Badge variant="neutral" size="sm">size sm</Badge>
              <Badge variant="violet" size="sm">package</Badge>
            </div>
          </div>
        </Section>

        {/* ──────── Spinner · LoadingState ──────── */}
        <Section title="Spinner · LoadingState">
          <div className="flex items-center gap-8">
            <div className="flex items-end gap-4 text-ditto-indigo">
              <Spinner size="sm" />
              <Spinner size="md" />
              <Spinner size="lg" />
            </div>
            <div className="flex-1 border border-border rounded-lg">
              <LoadingState label="에이전트 불러오는 중…" />
            </div>
          </div>
        </Section>

        {/* ──────── EmptyState ──────── */}
        <Section title="EmptyState — 빈 상태 플레이스홀더">
          <div className="border border-dashed border-border rounded-xl">
            <EmptyState
              icon="💬"
              title="아직 대화가 없어요"
              description="첫 메시지를 보내 이 에이전트와 대화를 시작하세요."
              action={<Button size="sm">대화 시작</Button>}
            />
          </div>
        </Section>

        {/* ──────── PageHeader ──────── */}
        <Section title="PageHeader — 페이지 상단 (뒤로 + 제목 + 액션)">
          <div className="border border-border rounded-xl p-6 bg-bg">
            <PageHeader
              title="에이전트 카탈로그"
              subtitle="agent_package PoC (6명)"
              backHref="#"
              backLabel="프로젝트"
              actions={<Button size="sm">에이전트 추가</Button>}
            />
          </div>
        </Section>

        {/* ──────── Card ──────── */}
        <Section title="Card — padding × elevation">
          <div className="grid md:grid-cols-3 gap-4">
            <Card padding="sm">
              <CardHeader title="sm padding" subtitle="p-3" />
              <p className="text-sm text-text-muted">컴팩트 카드</p>
            </Card>
            <Card padding="md">
              <CardHeader
                title="md padding (default)"
                subtitle="p-6"
                action={<Button size="sm" variant="ghost">⋯</Button>}
              />
              <p className="text-sm text-text-muted">기본 카드 + 액션 슬롯</p>
            </Card>
            <Card padding="lg" elevated>
              <CardHeader title="elevated" subtitle="shadow-elevated" />
              <p className="text-sm text-text-muted">모달·드롭다운 톤의 그림자</p>
            </Card>
          </div>
        </Section>

        {/* ──────── ScoreBadge ──────── */}
        <Section title="ScoreBadge — V1 임계치(EVAL_SPEC §V1)">
          <div className="flex items-center gap-3 flex-wrap">
            <ScoreBadge score={0.92} label="V1" />
            <ScoreBadge score={0.84} label="sync" />
            <ScoreBadge score={0.75} label="warning 경계" />
            <ScoreBadge score={0.61} />
            <ScoreBadge score={0.48} label="error" />
            <ScoreBadge score={0.12} />
          </div>
          <p className="text-xs text-text-muted mt-3">
            ≥ 0.80 success · 0.60–0.80 warning · &lt; 0.60 error
          </p>
        </Section>

        {/* ──────── Gauge ──────── */}
        <Section title="Gauge — 단일 지표">
          <div className="flex items-end gap-8 flex-wrap">
            <Gauge value={0.84} label="V1 응답 동기화율" />
            <Gauge value={0.67} label="warning 영역" />
            <Gauge value={0.42} label="insufficient" />
            <Gauge value={0.84} label="raw 모드" display="raw" />
          </div>
        </Section>

        {/* ──────── RadarChart ──────── */}
        <Section title="RadarChart — V1~V5 종합 (mock)">
          <div className="max-w-md">
            <RadarChart data={RADAR_SAMPLE} />
          </div>
        </Section>

        {/* ──────── ChatBubble ──────── */}
        <Section title="ChatBubble — role 별 정렬·끝부리">
          <div className="space-y-3 max-w-2xl mx-auto">
            <ChatBubble role="moderator">
              본 세션은 “신규 구독형 단백질 서비스” 에 대한 첫 인상 청취를 목표로 합니다.
            </ChatBubble>
            <ChatBubble role="agent" author="에이전트 #03" meta="22:14">
              저는 기존 보충제 시장의 가격대가 부담스러워서, 월 구독 방식이라면 한번 시도해볼 의향이 있어요.
            </ChatBubble>
            <ChatBubble
              role="agent"
              author="에이전트 #11"
              footer={
                <>
                  <ScoreBadge score={0.83} label="sync" />
                  <ScoreBadge score={0.71} label="consistency" />
                </>
              }
            >
              저는 회의적입니다. 단백질은 음식으로 충분히 섭취 가능하고, 구독은 결국 락인 효과를 노리는 모델이라서요.
            </ChatBubble>
            <ChatBubble role="user">
              두 분 의견이 흥미롭네요. “구독 모델” 자체보다 “락인” 에 거부감이 있으신 거 같은데, 해지가 1클릭이라면 인식이 달라질까요?
            </ChatBubble>
          </div>
        </Section>

        {/* ──────── FGIInterventionInput ──────── */}
        <Section title="FGIInterventionInput — 사용자 개입">
          <div className="space-y-3">
            <div className="flex gap-2">
              <Button
                size="sm"
                variant={fgiActive ? 'primary' : 'secondary'}
                onClick={() => setFgiActive((a) => !a)}
              >
                {fgiActive ? '활성 (펄스 중)' : '비활성 (안내만)'}
              </Button>
              {lastFgiSubmit && (
                <span className="text-xs text-text-muted self-center">
                  마지막 전송: <span className="text-text-primary">{`“${lastFgiSubmit}”`}</span>
                </span>
              )}
            </div>
            <FGIInterventionInput
              active={fgiActive}
              onSubmit={(t) => setLastFgiSubmit(t)}
              onYield={() => setLastFgiSubmit('(양보)')}
            />
          </div>
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section>
      <h2 className="text-lg font-bold text-text-primary mb-3">{title}</h2>
      <Card padding="md">{children}</Card>
    </section>
  );
}
