import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        border: 'var(--border)',
        'border-light': 'var(--border-light)',
        'text-primary': 'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
        'text-muted': 'var(--text-muted)',
        accent: 'var(--accent)',
        'accent-light': 'var(--accent-light)',
        cyan: 'var(--cyan)',
        'cyan-light': 'var(--cyan-light)',
        placeholder: 'var(--placeholder)',
        'tag-bg': 'var(--tag-bg)',
        'phase-active': 'var(--phase-active)',
        'phase-done': 'var(--phase-done)',
        'phase-upcoming': 'var(--phase-upcoming)',
      },
      fontFamily: {
        sans: ['IBM Plex Sans KR', '-apple-system', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
