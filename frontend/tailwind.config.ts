import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      colors: {
        // Ditto 기본 토큰 (DESIGN.md 기반)
        // 주의: Tailwind 기본 indigo/violet 스케일(text-indigo-200 등)을 쓰려면
        // 브랜드 색은 ditto- 접두로만 등록한다 (단색 덮어쓰기 금지).
        bg:       "var(--bg)",
        surface:  "var(--surface)",
        border:   "var(--border)",
        "ditto-indigo":       "var(--indigo)",
        "ditto-indigo-hover": "var(--indigo-hover)",
        "ditto-indigo-light": "var(--indigo-light)",
        "ditto-violet":       "var(--violet)",
        "ditto-violet-hover": "var(--violet-hover)",
        "ditto-violet-light": "var(--violet-light)",
        // Text
        "text-primary":   "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "text-muted":     "var(--text-muted)",
        // 상태
        success:  "var(--success)",
        warning:  "var(--warning)",
        error:    "var(--error)",
      },
      fontSize: {
        // DESIGN.md font.size.2xs (마이크로 라벨 — 배지·캡션·메타)
        "2xs": ["10px", { lineHeight: "1.4" }],
        // DESIGN.md font.size.score (게이지 차트 중앙 점수)
        score: ["48px", { lineHeight: "1", fontWeight: "700" }],
      },
      boxShadow: {
        // DESIGN.md size.shadow.*
        card:     "0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.03)",
        elevated: "0 10px 15px rgba(0,0,0,0.07), 0 4px 6px rgba(0,0,0,0.05)",
      },
      keyframes: {
        // DESIGN.md FGIInterventionInput 활성 시 펄스 (≤1.5s)
        "ditto-pulse-ring": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(79, 70, 229, 0.4)" },
          "50%":      { boxShadow: "0 0 0 6px rgba(79, 70, 229, 0)" },
        },
      },
      animation: {
        "pulse-ring": "ditto-pulse-ring 1.5s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
