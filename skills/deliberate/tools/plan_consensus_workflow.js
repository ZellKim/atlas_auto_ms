export const meta = {
  name: 'deliberate-plan-consensus',
  description: '코딩 계획(plan+PLAN-DR)을 4개 독립 렌즈로 동시 검증(다중검증). CLEAR/WATCH/BLOCK. ralplan 이식.',
  phases: [
    { title: 'Critique', detail: '4 렌즈 병렬 (architecture / correctness / test / security)' },
    { title: 'Join', detail: 'verdict 집계 + gate 판정' },
  ],
}

// args: { plan_path, spec_path, iteration, repo_root }
const plan = args?.plan_path || '<plan.md>'
const spec = args?.spec_path || '<spec>'
const iter = args?.iteration ?? 1
const root = args?.repo_root || '.'

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
          evidence: { type: 'string', description: '근거로 읽은 파일:line 또는 실행결과. 없으면 [UNVERIFIED].' },
        },
      },
    },
    summary: { type: 'string' },
  },
}

const ROOT = `당신은 소프트웨어 설계 리뷰어다. 아래 구현 계획과 PLAN-DR을 읽고 담당 렌즈로만 심사한다.
- 계획 파일: ${plan}
- spec: ${spec}
- repo root: ${root}
- iteration: ${iter}
규칙: 근거 없는 지적 금지. 실제 관련 소스 파일을 읽고 finding의 evidence에 file:line 또는 명령 결과를 적어라.
확인 못 한 건 finding으로 올리되 evidence에 '[UNVERIFIED]'. 계획을 실제 코드베이스에 대조하라.
verdict: 실행/정합성을 깨는 결함 있으면 BLOCK, 주의할 약점이면 WATCH, 결함 없으면 CLEAR.`

const LENSES = [
  {
    key: 'architecture',
    prompt: `${ROOT}
[렌즈: architecture] 구조 적합성, 모듈 경계·결합도, 확장성, 기존 코드 패턴/컨벤션 정합, 과설계/설계부족,
대안 접근이 더 단순하지 않은지를 점검. 계획이 손대는 모듈의 실제 코드를 읽고 정합성 확인.`,
  },
  {
    key: 'correctness',
    prompt: `${ROOT}
[렌즈: correctness] 엣지케이스, 실패 모드, null/경계/race/동시성, 에러 처리, 숨은 가정, 하위호환 파괴,
데이터 마이그레이션 정합을 점검. 계획대로 하면 깨질 수 있는 구체 시나리오를 제시.`,
  },
  {
    key: 'test-verification',
    prompt: `${ROOT}
[렌즈: test-verification] 이 변경을 어떻게 검증하나? 테스트 가능한 구조인가? 회귀 위험은? 계획에 검증 방법이
있는가? 기존 테스트 스위트·CI 존재를 확인하고, 검증 계획 부재/불충분을 지적.`,
  },
  {
    key: 'security-ops',
    prompt: `${ROOT}
[렌즈: security-ops] 입력 검증, 인증·권한, 시크릿/자격증명 노출, 주입, 되돌리기(rollback)·배포 리스크,
파괴적/비가역 작업 여부를 점검. 안전하게 롤백 가능한 계획인지 확인.`,
  },
]

phase('Critique')
const verdicts = (await parallel(
  LENSES.map((l) => () =>
    agent(l.prompt, { label: `lens:${l.key}`, phase: 'Critique', schema: VERDICT_SCHEMA })
  )
)).filter(Boolean)

phase('Join')
const allFindings = verdicts.flatMap((v) => (v.findings || []).map((f) => ({ lens: v.lens, ...f })))
const blocks = verdicts.filter((v) => v.verdict === 'BLOCK')
const gate = blocks.length > 0 ? 'ITERATE' : 'PASS'

log(`iteration ${iter}: ${gate} — BLOCK=${blocks.length} WATCH=${verdicts.filter((v) => v.verdict === 'WATCH').length} CLEAR=${verdicts.filter((v) => v.verdict === 'CLEAR').length}`)

return {
  iteration: iter,
  gate, // PASS → reconciliation+승인 / ITERATE → 계획 수정 후 재실행 (최대 5)
  verdicts,
  blocking_findings: allFindings.filter((f) => f.severity === 'block'),
  watch_findings: allFindings.filter((f) => f.severity === 'watch'),
  note_findings: allFindings.filter((f) => f.severity === 'note'),
}
