"""처음부터 새 Estimation 연구를 설계하는 예제"""

from atlas_auto import FedernetClient, EstimationBuilder

# ── 1. Estimation 스펙 설계 ──
builder = EstimationBuilder("My New CES Study", "Drug A vs Drug B")

# 코호트 정의 (JSON 파일에서)
builder.add_cohort_from_json(1, "Target: Drug A", "cohorts/target.json")
builder.add_cohort_from_json(2, "Comparator: Drug B", "cohorts/comparator.json")
builder.add_cohort_from_json(3, "Outcome: MI", "cohorts/outcome_mi.json")
builder.add_cohort_from_json(4, "Outcome: Stroke", "cohorts/outcome_stroke.json")

# TCO 설정
builder.add_target_comparator_outcomes(
    target_id=1, comparator_id=2, outcome_ids=[3, 4]
)

# 분석 설정 (PS stratification + Cox)
builder.add_cm_analysis(
    analysis_id=1,
    description="PS stratification (5 strata), Cox",
    restrict_to_common_period=True,
    remove_prior_outcome=True,
    risk_window_start=1,
    risk_window_end=0,
    add_exposure_days_to_end=True,
    create_ps=True,
    ps_method="stratify",
    stratify_num_strata=5,
    model_type="cox",
    stratified_cox=True,
)

# 분석 설정 2 (PS matching + Cox)
builder.add_cm_analysis(
    analysis_id=2,
    description="PS 1:1 matching, Cox",
    restrict_to_common_period=True,
    remove_prior_outcome=True,
    risk_window_start=1,
    risk_window_end=0,
    add_exposure_days_to_end=True,
    create_ps=True,
    ps_method="match",
    match_max_ratio=1,
    match_caliper=0.2,
    model_type="cox",
    stratified_cox=True,
)

# JSON 저장
builder.save("my_study_spec.json")
print("스펙 저장: my_study_spec.json")


# ── 2. feedernet에 업로드 & 실행 ──
# client = FedernetClient()
# client.login_portal("your@email.com", "YOUR_PW")
# client.connect_site(7, 203)
#
# spec = builder.build()
# est = client.import_estimation(spec)
# client.run_estimation(est["id"], client.get_source_key())
# info = client.wait_for_estimation(est["id"])
# print(f"결과: {info.get('status', {}).get('name')}")
