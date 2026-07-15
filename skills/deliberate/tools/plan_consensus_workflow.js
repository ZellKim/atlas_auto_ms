export const meta = {
  name: 'deliberate-plan-consensus',
  description: '어떤 작업이든 계획(plan+PLAN-DR)을 4개 보편 렌즈로 동시 검증(다중검증). CLEAR/WATCH/BLOCK. ralplan 이식.',
  phases: [
    { title: 'Critique', detail: '4 보편 렌즈 병렬 (soundness / completeness / feasibility / alternatives)' },
    { title: 'Join', detail: 'verdict 집계 + gate 판정' },
  ],
}

// args: {
//   plan_path, spec_path, iteration, work_root,
//   domain,        // 예: "coding" | "research" | "writing" | "planning" | "ops" (자유 텍스트)
//   lens_focus,    // { soundness, completeness, feasibility, alternatives } 작업별 초점 문자열 (선택)
//   evidence_hint, // 렌즈가 근거로 삼을 자료 위치 힌트 (선택, 예: "data/ 파일, src/ 소스")
// }
const plan = args?.plan_path || '<plan.md>'
const spec = args?.spec_path || '<spec>'
const iter = args?.iteration ?? 1
const root = args?.work_root || '.'
const domain = args?.domain || 'general'
const focus = args?.lens_focus || {}
const evHint = args?.evidence_hint || '관련 소스/문서/데이터 파일'

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['lens', 'verdict', 'findings'],
  properties: {
    lens: { type: 'string' },
    verdict: { enum: ['CLEAR', 'WATCH', 'BLOCK'] },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['severity', 'issue', 'suggestion'],
        properties: {
          severity: { enum: ['block', 'watch', 'note'] },
          issue: { type: 'string' },
          suggestion: { type: 'string' },
          evidence: { type: 'string', description: '근거로 확인한 파일:line/자료/실행결과. 없으면 [UNVERIFIED].' },
        },
      },
    },
    summary: { type: 'string' },
  },
}

const ROOT = `당신은 작업 계획 심사위원이다. 아래 계획과 PLAN-DR을 읽고 담당 렌즈로만 심사한다.
- 작업 도메인: ${domain}
- 계획 파일: ${plan}
- spec: ${spec}
- 작업 위치(root): ${root}
- iteration: ${iter}
규칙: 근거 없는 지적 금지. ${evHint} 를 실제로 확인하고 finding의 evidence에 파일:line/자료/명령결과를 적어라.
확인 못 한 건 finding으로 올리되 evidence에 '[UNVERIFIED]'. 계획을 실제 근거에 대조하라.
verdict: 실행/타당성을 깨는 결함 있으면 BLOCK, 주의할 약점이면 WATCH, 결함 없으면 CLEAR.`

const LENSES = [
  {
    key: 'soundness',
    base: '접근·논리·가정의 타당성과 실패 모드를 점검. 계획의 핵심 가정이 틀리면 어디서 깨지는지 구체 시나리오로 제시.',
  },
  {
    key: 'completeness',
    base: '빠진 것을 점검 — 놓친 케이스·시나리오·이해관계자·요구·엣지. 계획이 다루지 않은 공백을 나열.',
  },
  {
    key: 'feasibility',
    base: '실행 가능성·자원·의존성·리스크·되돌리기(rollback)를 점검. 실제로 완수 가능한지, 안전하게 되돌릴 수 있는지 확인.',
  },
  {
    key: 'alternatives',
    base: '더 단순하거나 나은 접근이 있는지, 과설계/과소설계 여부, tradeoff를 점검. PLAN-DR의 대안 비교가 충실한지 평가.',
  },
]

phase('Critique')
const verdicts = (await parallel(
  LENSES.map((l) => () => {
    const extra = focus[l.key] ? `\n[이 작업의 초점] ${focus[l.key]}` : ''
    const prompt = `${ROOT}\n[렌즈: ${l.key}] ${l.base}${extra}`
    return agent(prompt, { label: `lens:${l.key}`, phase: 'Critique', schema: VERDICT_SCHEMA })
  })
)).filter(Boolean)

phase('Join')
const allFindings = verdicts.flatMap((v) => (v.findings || []).map((f) => ({ lens: v.lens, ...f })))
const blocks = verdicts.filter((v) => v.verdict === 'BLOCK')
const gate = blocks.length > 0 ? 'ITERATE' : 'PASS'

log(`iteration ${iter} (${domain}): ${gate} — BLOCK=${blocks.length} WATCH=${verdicts.filter((v) => v.verdict === 'WATCH').length} CLEAR=${verdicts.filter((v) => v.verdict === 'CLEAR').length}`)

return {
  iteration: iter,
  domain,
  gate, // PASS → reconciliation+승인 / ITERATE → 계획 수정 후 재실행 (최대 5)
  verdicts,
  blocking_findings: allFindings.filter((f) => f.severity === 'block'),
  watch_findings: allFindings.filter((f) => f.severity === 'watch'),
  note_findings: allFindings.filter((f) => f.severity === 'note'),
}
