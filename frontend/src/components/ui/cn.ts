// 조건부 className 결합 헬퍼. clsx 미설치 환경의 경량 대체.
// 사용: cn('base', condition && 'extra', { 'active': isActive })
export type ClassValue =
  | string
  | number
  | null
  | undefined
  | false
  | { [k: string]: unknown }
  | ClassValue[];

export function cn(...inputs: ClassValue[]): string {
  const out: string[] = [];
  for (const x of inputs) {
    if (!x) continue;
    if (typeof x === 'string' || typeof x === 'number') {
      out.push(String(x));
    } else if (Array.isArray(x)) {
      const joined = cn(...x);
      if (joined) out.push(joined);
    } else if (typeof x === 'object') {
      for (const k in x) if (x[k]) out.push(k);
    }
  }
  return out.join(' ');
}
