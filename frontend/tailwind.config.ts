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
        bg:       "var(--bg)",
        surface:  "var(--surface)",
        border:   "var(--border)",
        // Indigo (기본 강조)
        indigo:   "var(--indigo)",
        "indigo-hover": "var(--indigo-hover)",
        "indigo-light": "var(--indigo-light)",
        // Violet (포인트)
        violet:   "var(--violet)",
        "violet-hover": "var(--violet-hover)",
        "violet-light": "var(--violet-light)",
        // Text
        "text-primary":   "var(--text-primary)",
        "text-secondary": "var(--text-secondary)",
        "text-muted":     "var(--text-muted)",
        // 상태
        success:  "var(--success)",
        warning:  "var(--warning)",
        error:    "var(--error)",
      },
    },
  },
  plugins: [],
};

export default config;
