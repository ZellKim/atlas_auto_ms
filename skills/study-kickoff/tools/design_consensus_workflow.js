export const meta = {
  name: 'study-design-consensus',
  description: '연구 설계 spec+DR을 4개 독립 렌즈로 동시 검증(다중검증). 각 렌즈 CLEAR/WATCH/BLOCK verdict 반환. ralplan 이식.',
  phases: [
    { title: 'Critique', detail: '4 렌즈 병렬 리뷰 (causal / feedernet / data / stats)' },
    { title: 'Join', detail: 'verdict 집계 + gate 판정' },
  ],
}

// args: { spec_path, dr_path, study_code, iteration }
// orchestrator가 Phase 2a에서 spec/DR 파일 경로를 넘겨준다.
const spec = args?.spec_path || 'studies/<study>/docs/study_design_spec.json'
const dr = args?.dr_path || 'studies/<study>/docs/design_dr.md'
const iter = args?.iteration ?? 1

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
          evidence: { type: 'string', description: '근거로 읽은 data/ 파일 또는 API. 없으면 [UNVERIFIED] 명시.' },
        },
      },
    },
    summary: { type: 'string' },
  },
}

const ROOT = `당신은 임상연구 설계 심사위원이다. 아래 설계 spec과 DESIGN-DR을 읽고 담당 렌즈로만 심사한다.
- spec 파일: ${spec}
- DESIGN-DR 파일: ${dr}
- iteration: ${iter}
규칙(프로젝트 No-Guessing): 근거 없는 지적 금지. 각 finding의 evidence에 실제로 읽은 data/ 파일 경로나 API를 적어라.
확인 못 한 값은 finding으로 올리되 evidence에 '[UNVERIFIED: 확인 필요]'라고 명시.
verdict 규칙: 실행/타당성을 깨는 결함 있으면 BLOCK, 주의할 약점이면 WATCH, 결함 없으면 CLEAR.`

const LENSES = [
  {
    key: 'causal-methodology',
    prompt: `${ROOT}
[렌즈: causal-methodology] confounding by indication, active comparator 타당성, immortal time bias,
selection/collider bias, index event/washout 정의, new-user 여부를 점검하라.`,
  },
  {
    key: 'feedernet-execution',
    prompt: `${ROOT}
[렌즈: feedernet-execution] 설계가 feedernet에서 실제로 실행 가능한지 점검하라. 반드시 참조:
- docs/system_knowledge_base.md (API 함정)
- data/atlas_reference/ (endpoints)
- data/site_mapping/ (sourceKey/site ID 4종)
특히 estimation spec의 cohortDefinitions에 코호트 full expression 누락 위험, cohort 정의의
operationalizability(concept_id list 존재), sourceKey≠cdmName 혼동을 점검.`,
  },
  {
    key: 'data-availability',
    prompt: `${ROOT}
[렌즈: data-availability] 대상 site에서 필요한 concept/measurement가 실제 존재하고 event 수/power가
충분한지 점검하라. 반드시 참조:
- data/concept_frequency/ (Achilles 기관×domain)
- data/measurement/ (site_concept_matrix, stability_summary)
- data/biomarker/ (unit 매핑)
site_set의 각 sourceKey에 대해 target/comparator/outcome concept 가용성을 cross-check.`,
  },
  {
    key: 'statistical',
    prompt: `${ROOT}
[렌즈: statistical] PS model 구성(covariate/LASSO), matching(caliper), negative control outcome 구성,
empirical calibration(Schuemie 2014), sensitivity/subgroup 설계, 다중비교, 검정력을 점검하라.`,
  },
]

phase('Critique')
const verdicts = (await parallel(
  LENSES.map((l) => () =>
    agent(l.prompt, { label: `lens:${l.key}`, phase: 'Critique', schema: VERDICT_SCHEMA })
  )
)).filter(Boolean)

phase('Join')
const blocks = verdicts.filter((v) => v.verdict === 'BLOCK')
const watches = verdicts.filter((v) => v.verdict === 'WATCH')
const gate = blocks.length > 0 ? 'ITERATE' : 'PASS'

log(`iteration ${iter}: ${gate} — BLOCK=${blocks.length} WATCH=${watches.length} CLEAR=${verdicts.length - blocks.length - watches.length}`)

return {
  iteration: iter,
  gate, // PASS → reconciliation+승인 단계로 / ITERATE → spec 수정 후 재실행 (최대 5)
  verdicts,
  blocking_findings: blocks.flatMap((v) => v.findings.filter((f) => f.severity === 'block').map((f) => ({ lens: v.lens, ...f }))),
  watch_findings: watches.flatMap((v) => v.findings.filter((f) => f.severity === 'watch').map((f) => ({ lens: v.lens, ...f }))),
}
