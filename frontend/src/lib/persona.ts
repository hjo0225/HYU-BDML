import { PersonaProfile } from './types';

export function buildSystemPromptFromPersona(
  name: string,
  type: 'customer' | 'expert' | 'custom',
  profile: PersonaProfile
): string {
  const genderMap: Record<PersonaProfile['gender'], string> = {
    male: '남성',
    female: '여성',
    other: '',
  };
  const genderKr = genderMap[profile.gender] ?? '';

  let intro: string;
  if (type === 'customer') {
    const introParts = [`당신은 ${name}입니다.`, `${profile.age}세`];
    if (genderKr) {
      introParts.push(genderKr);
    }
    introParts.push(`${profile.occupation}입니다.`);
    intro = introParts.join(' ');
  } else if (type === 'expert') {
    intro = `당신은 ${name}입니다. ${profile.occupation} 분야의 전문가입니다.`;
  } else {
    intro = `당신은 ${name}입니다.`;
  }

  const sections: Array<[string, string]> = [
    ['성격 및 성향', profile.personality],
    ['소비 스타일', profile.consumption_style],
    ['관련 경험', profile.experience],
    ['불만/니즈', profile.pain_points],
    ['말투와 표현 방식', profile.communication_style],
  ];

  const lines = [intro];
  for (const [label, value] of sections) {
    const text = value.trim();
    if (text) {
      lines.push(`${label}: ${text}`);
    }
  }

  return lines.join('\n');
}
