import {
  AgentSchema,
  ResearchBrief,
  FitnessResult,
  FitnessCheck,
} from './types';

type FitnessStatus = FitnessCheck['status'];

export function parseAgeRange(text: string): [number, number] | null {
  const decadeRangeMatch = text.match(/(\d+)-(\d+)대/);
  if (decadeRangeMatch) {
    const start = Number(decadeRangeMatch[1]);
    const end = Number(decadeRangeMatch[2]) + 9;
    return [start, end];
  }

  const decadeMatch = text.match(/(\d+)대/);
  if (decadeMatch) {
    const start = Number(decadeMatch[1]);
    return [start, start + 9];
  }

  const ageRangeMatch = text.match(/(\d+)-(\d+)세/);
  if (ageRangeMatch) {
    return [Number(ageRangeMatch[1]), Number(ageRangeMatch[2])];
  }

  return null;
}

export function checkFitness(
  agents: AgentSchema[],
  brief: ResearchBrief
): FitnessResult {
  const checks: FitnessCheck[] = [
    checkAgeCoverage(agents, brief),
    checkGenderMatch(agents, brief),
    checkExpertPresence(agents, brief),
    checkDiversity(agents),
  ];

  let overall: FitnessResult['overall'] = 'warning';
  if (checks.every((check) => check.status === 'good')) {
    overall = 'good';
  } else if (checks.some((check) => check.status === 'poor')) {
    overall = 'poor';
  }

  return { overall, checks };
}

function checkAgeCoverage(
  agents: AgentSchema[],
  brief: ResearchBrief
): FitnessCheck {
  const range = parseAgeRange(brief.target_customer);
  if (!range) {
    return {
      label: '타깃 연령 커버리지',
      status: 'good',
      detail: '타깃 연령 정보가 명확하지 않아 검증을 생략했습니다.',
    };
  }

  const personaAgents = agents.filter((agent) => agent.persona_profile?.age != null);
  if (personaAgents.length === 0) {
    return {
      label: '타깃 연령 커버리지',
      status: 'good',
      detail: '페르소나 정보가 없어 연령 검증을 생략했습니다.',
    };
  }

  const [minAge, maxAge] = range;
  const matched = personaAgents.filter((agent) => {
    const age = agent.persona_profile?.age;
    return age != null && age >= minAge && age <= maxAge;
  }).length;
  const ratio = matched / personaAgents.length;

  return {
    label: '타깃 연령 커버리지',
    status: ratio >= 0.5 ? 'good' : ratio >= 0.2 ? 'warning' : 'poor',
    detail: `타깃 연령 ${minAge}-${maxAge}세 기준 에이전트 ${matched}/${personaAgents.length}명 포함`,
  };
}

function checkGenderMatch(
  agents: AgentSchema[],
  brief: ResearchBrief
): FitnessCheck {
  const targetGender = detectTargetGender(brief.target_customer);
  if (!targetGender) {
    return {
      label: '타깃 성별 매칭',
      status: 'good',
      detail: '성별 조건이 없거나 혼합 타깃으로 간주되어 통과했습니다.',
    };
  }

  const matched = agents.filter(
    (agent) => agent.persona_profile?.gender === targetGender
  ).length;

  return {
    label: '타깃 성별 매칭',
    status: matched >= 1 ? 'good' : 'warning',
    detail:
      matched >= 1
        ? `타깃 성별과 일치하는 에이전트 ${matched}명이 포함되어 있습니다.`
        : '타깃 성별과 일치하는 에이전트가 없습니다.',
  };
}

function checkExpertPresence(
  agents: AgentSchema[],
  brief: ResearchBrief
): FitnessCheck {
  const expertCount = agents.filter((agent) => agent.type === 'expert').length;

  return {
    label: '연구 카테고리 전문가 포함',
    status: expertCount >= 1 ? 'good' : 'warning',
    detail:
      expertCount >= 1
        ? `${brief.category} 카테고리를 해석할 전문가 에이전트 ${expertCount}명이 포함되어 있습니다.`
        : `${brief.category} 카테고리를 해석할 expert 에이전트가 없습니다.`,
  };
}

function checkDiversity(agents: AgentSchema[]): FitnessCheck {
  const personaAgents = agents.filter((agent) => agent.persona_profile?.age != null);
  if (personaAgents.length === 0) {
    return {
      label: '에이전트 간 다양성',
      status: 'warning',
      detail: '페르소나 정보 없음',
    };
  }

  const ageGroups = new Set(
    personaAgents.map((agent) =>
      Math.floor((agent.persona_profile!.age ?? 0) / 10) * 10
    )
  );

  const status: FitnessStatus =
    ageGroups.size >= 3 ? 'good' : ageGroups.size === 2 ? 'warning' : 'poor';

  return {
    label: '에이전트 간 다양성',
    status,
    detail: `연령 그룹 ${ageGroups.size}개(${Array.from(ageGroups)
      .sort((a, b) => a - b)
      .map((age) => `${age}대`)
      .join(', ')})로 구성되어 있습니다.`,
  };
}

function detectTargetGender(text: string): 'male' | 'female' | null {
  if (text.includes('남녀') || text.includes('직장인')) {
    return null;
  }
  if (text.includes('여성')) {
    return 'female';
  }
  if (text.includes('남성')) {
    return 'male';
  }
  return null;
}
