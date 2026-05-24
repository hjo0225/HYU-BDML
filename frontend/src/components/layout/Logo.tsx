'use client';

// 원본 로고 비율 (frontend/public/logo.png — 575×293, 투명 배경 단색 실루엣)
const LOGO_W = 575;
const LOGO_H = 293;

// 마크 그라데이션 — 워드마크·랜딩 'Mind-Bridge' 글자와 동일(from-ditto-indigo → to-ditto-violet).
// PNG 알파(물결 모양)를 CSS mask 로 쓰고 그 뒤에 그라데이션을 깔아, 단색 실루엣을
// 라이브 그라데이션으로 칠한다(토큰 바뀌면 자동 반영, 벡터처럼 어느 크기든 선명).
const MARK_MASK_STYLE = {
  WebkitMaskImage: 'url(/logo.png)',
  maskImage: 'url(/logo.png)',
  WebkitMaskRepeat: 'no-repeat',
  maskRepeat: 'no-repeat',
  WebkitMaskSize: 'contain',
  maskSize: 'contain',
  WebkitMaskPosition: 'center',
  maskPosition: 'center',
} as const;

interface LogoProps {
  /** 로고 마크 높이(px). 너비는 원본 비율을 유지해 자동 계산. */
  height?: number;
  /** 'Mind-Bridge' 워드마크에 적용할 클래스(색·크기). 빈 문자열이면 텍스트 숨김. */
  wordmarkClassName?: string;
  className?: string;
}

/**
 * Mind-Bridge 브랜드 로고 — 마크 이미지 + 워드마크.
 * 사이드바·랜딩·인증 페이지에서 공용으로 사용한다.
 */
// 기본 워드마크 스타일 — 인디고→바이올렛 그라데이션. 어두운 배경(login/register)에서는
// 호출 측에서 text-white 등으로 override.
const DEFAULT_WORDMARK = 'text-lg bg-gradient-to-br from-ditto-indigo to-ditto-violet bg-clip-text text-transparent';

export function Logo({
  height = 24,
  wordmarkClassName = DEFAULT_WORDMARK,
  className = '',
}: LogoProps) {
  const width = Math.round((LOGO_W / LOGO_H) * height);
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <span
        role="img"
        aria-label="Mind-Bridge 로고"
        className="inline-block shrink-0 bg-gradient-to-br from-ditto-indigo to-ditto-violet"
        style={{ width, height, ...MARK_MASK_STYLE }}
      />
      {wordmarkClassName && (
        <span className={`font-bold tracking-tight ${wordmarkClassName}`}>Mind-Bridge</span>
      )}
    </span>
  );
}
