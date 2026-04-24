"""
IPD Pooled Analysis - 1:2 PS Matching
7개 기관 환자 데이터 통합 → PS 적합 → 1:2 매칭 → Cox 모델

비교 3가지:
  t1072 (Appendectomy) vs c1074 (Cholecystectomy)
  t1072 (Appendectomy) vs c1076 (General Population)
  t1072 (Appendectomy) vs c1121 (Hernia repair)
"""
import sys, os, sqlite3, time, warnings
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from lifelines import CoxPHFitter
from lifelines import KaplanMeierFitter

warnings.filterwarnings("ignore")
sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(__file__)
CMDATA_DIR = os.path.join(BASE_DIR, "cmData")
OUTPUT_DIR = os.path.join(BASE_DIR, "matched_results")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SITES = sorted([d for d in os.listdir(CMDATA_DIR)
                if os.path.isdir(os.path.join(CMDATA_DIR, d))])

# 코호트 ID → 이름 매핑
COHORT_NAMES = {
    1072: "Appendectomy",
    1074: "Cholecystectomy",
    1076: "General_Population",
    1121: "Hernia_repair",
}

OUTCOME_NAMES = {
    1077: "Ulcerative_colitis",
    1078: "Crohns_disease",
    1079: "Asthma",
    1080: "Atopic_dermatitis",
    1090: "Rheumatoid_arthritis",
    1092: "C_difficile_infection",
    1093: "Parkinsons_disease",
    1094: "Biliary_calculus",
    1095: "Acute_MI",
    1096: "T2DM",
    1097: "Colorectal_cancer",
}

COMPARISONS = [
    (1072, 1074),
    (1072, 1076),
    (1072, 1121),
]

MAX_COMPARATOR_FOR_PS = 250000  # PS 적합 시 comparator 최대 수 (메모리 절약)


def load_site_data(site, target_id, comparator_id):
    """한 기관의 CmData SQLite에서 cohorts, outcomes, covariates 로드"""
    cm_name = f"CmData_l1_t{target_id}_c{comparator_id}"
    cm_dir = os.path.join(CMDATA_DIR, site, cm_name)
    if not os.path.isdir(cm_dir):
        return None, None, None, None

    sq = [f for f in os.listdir(cm_dir) if f.endswith(".sqlite")]
    if not sq:
        return None, None, None, None

    conn = sqlite3.connect(os.path.join(cm_dir, sq[0]))

    # cohorts
    cohorts = pd.read_sql("SELECT * FROM cohorts", conn)
    cohorts["site"] = site

    # outcomes
    outcomes = pd.read_sql("SELECT * FROM outcomes", conn)

    # covariates (sparse)
    covariates = pd.read_sql("SELECT rowId, covariateId, covariateValue FROM covariates", conn)

    # covariate reference
    cov_ref = pd.read_sql("SELECT covariateId, covariateName, analysisId FROM covariateRef", conn)

    conn.close()
    return cohorts, outcomes, covariates, cov_ref


def pool_data(target_id, comparator_id):
    """7개 기관 데이터 통합"""
    all_cohorts = []
    all_outcomes = []
    all_covariates = []
    all_cov_ref = {}

    print(f"\n  데이터 로딩:", end="", flush=True)
    for site in SITES:
        cohorts, outcomes, covariates, cov_ref = load_site_data(site, target_id, comparator_id)
        if cohorts is None:
            continue

        # rowId를 기관별로 유니크하게 (site prefix)
        site_idx = SITES.index(site)
        offset = site_idx * 10_000_000
        cohorts["rowId"] = cohorts["rowId"].astype(int) + offset
        if outcomes is not None and len(outcomes) > 0:
            outcomes["rowId"] = outcomes["rowId"].astype(int) + offset
        if covariates is not None and len(covariates) > 0:
            covariates["rowId"] = covariates["rowId"].astype(int) + offset

        all_cohorts.append(cohorts)
        all_outcomes.append(outcomes)
        all_covariates.append(covariates)
        for _, r in cov_ref.iterrows():
            all_cov_ref[r["covariateId"]] = r["covariateName"]

        n_t = (cohorts["treatment"] == 1).sum()
        n_c = (cohorts["treatment"] == 0).sum()
        print(f" {site.split('_')[0]}({n_t}+{n_c})", end="", flush=True)

    print()
    cohorts_df = pd.concat(all_cohorts, ignore_index=True)
    outcomes_df = pd.concat(all_outcomes, ignore_index=True)
    covariates_df = pd.concat(all_covariates, ignore_index=True)

    return cohorts_df, outcomes_df, covariates_df, all_cov_ref


def build_covariate_matrix(cohorts_df, covariates_df, fixed_cov_ids=None):
    """Sparse covariate matrix 생성. fixed_cov_ids로 컬럼 고정 가능."""
    row_ids = cohorts_df["rowId"].values
    row_id_to_idx = {rid: i for i, rid in enumerate(row_ids)}

    # site dummy variables
    site_labels = sorted(SITES)
    site_to_col = {s: i for i, s in enumerate(site_labels[1:])}  # 첫 사이트는 reference

    rows, cols, vals = [], [], []

    # 공변량 ID 목록 고정
    if fixed_cov_ids is not None:
        cov_ids = fixed_cov_ids
    else:
        cov_ids = sorted(covariates_df["covariateId"].unique())
    cov_id_to_col = {cid: j for j, cid in enumerate(cov_ids)}
    n_cov_cols = len(cov_ids)

    for _, r in covariates_df.iterrows():
        rid = r["rowId"]
        cid = r["covariateId"]
        if rid in row_id_to_idx and cid in cov_id_to_col:
            rows.append(row_id_to_idx[rid])
            cols.append(cov_id_to_col[cid])
            vals.append(r["covariateValue"])

    # site dummy 추가
    col_offset = n_cov_cols
    for i, row in cohorts_df.iterrows():
        site = row["site"]
        if site in site_to_col:
            rows.append(row_id_to_idx[row["rowId"]])
            cols.append(col_offset + site_to_col[site])
            vals.append(1.0)

    n_rows = len(row_ids)
    n_cols = n_cov_cols + len(site_to_col)

    X = sparse.csr_matrix((vals, (rows, cols)), shape=(n_rows, n_cols))
    return X, cov_ids


def fit_propensity_score(cohorts_df, covariates_df, max_comparator=MAX_COMPARATOR_FOR_PS):
    """Propensity Score 적합 (L1 regularized logistic regression)"""
    # comparator가 너무 많으면 서브샘플링
    n_target = (cohorts_df["treatment"] == 1).sum()
    n_comp = (cohorts_df["treatment"] == 0).sum()

    if n_comp > max_comparator:
        print(f"  Comparator 서브샘플링: {n_comp:,} → {max_comparator:,} (PS 적합용)")
        target_rows = cohorts_df[cohorts_df["treatment"] == 1]["rowId"].values
        comp_rows = cohorts_df[cohorts_df["treatment"] == 0]["rowId"].values
        sampled_comp = np.random.choice(comp_rows, max_comparator, replace=False)
        fit_row_ids = set(target_rows) | set(sampled_comp)
        fit_mask = cohorts_df["rowId"].isin(fit_row_ids)
        fit_cohorts = cohorts_df[fit_mask].reset_index(drop=True)
        fit_covariates = covariates_df[covariates_df["rowId"].isin(fit_row_ids)]
    else:
        fit_cohorts = cohorts_df
        fit_covariates = covariates_df

    print(f"  Covariate matrix 생성 중...", end="", flush=True)
    X, fixed_cov_ids = build_covariate_matrix(fit_cohorts, fit_covariates)
    y = fit_cohorts["treatment"].values
    print(f" shape={X.shape}")

    print(f"  Logistic regression (L1, CV) 적합 중...", end="", flush=True)
    t0 = time.time()
    model = LogisticRegression(
        penalty="l1",
        C=1.0,
        solver="saga",
        max_iter=500,
        tol=1e-4,
        n_jobs=-1,
        random_state=42,
    )
    model.fit(X, y)
    elapsed = time.time() - t0
    print(f" {elapsed:.1f}초")

    # PS 예측 - 서브샘플링한 경우 매칭 대상만 예측 (전체 예측은 메모리 초과)
    if n_comp > max_comparator:
        print(f"  매칭용 서브셋 PS 예측 중...", end="", flush=True)
        match_comp = cohorts_df[cohorts_df["treatment"] == 0].sample(
            n=min(max_comparator, n_comp), random_state=42)
        match_cohorts = pd.concat([cohorts_df[cohorts_df["treatment"] == 1], match_comp])
        match_cov = covariates_df[covariates_df["rowId"].isin(match_cohorts["rowId"])]
        X_match, _ = build_covariate_matrix(
            match_cohorts.reset_index(drop=True), match_cov, fixed_cov_ids=fixed_cov_ids)
        ps = model.predict_proba(X_match)[:, 1]
        match_cohorts = match_cohorts.reset_index(drop=True)
        match_cohorts["ps"] = ps
        print(f" 완료 ({len(match_cohorts):,}명)")
        return match_cohorts, model
    else:
        ps = model.predict_proba(X)[:, 1]

    cohorts_df = cohorts_df.copy()
    cohorts_df["ps"] = ps

    return cohorts_df, model


def match_1_to_n(cohorts_df, n_matches=2, caliper=0.2):
    """1:N PS matching (nearest neighbor, caliper on logit PS)

    소수군 기준 매칭: Target < Comparator이면 Target 1:N Comparator,
                     Target > Comparator이면 Comparator 1:N Target (방향 반전)
    """
    from scipy.spatial import cKDTree

    df = cohorts_df.copy()

    # Logit PS
    ps_clipped = np.clip(df["ps"].values, 1e-8, 1 - 1e-8)
    df["logit_ps"] = np.log(ps_clipped / (1 - ps_clipped))

    # Caliper = 0.2 * SD(logit PS)
    sd_logit = df["logit_ps"].std()
    caliper_val = caliper * sd_logit
    print(f"  Caliper: {caliper} x SD({sd_logit:.4f}) = {caliper_val:.4f}")

    targets = df[df["treatment"] == 1].copy()
    comparators = df[df["treatment"] == 0].copy()

    # 소수군 기준 매칭 방향 결정
    if len(targets) <= len(comparators):
        anchor = targets       # 매칭 기준 (1)
        pool = comparators     # 매칭 대상 (N)
        anchor_label = "Target"
        pool_label = "Comparator"
        reversed_match = False
    else:
        anchor = comparators
        pool = targets
        anchor_label = "Comparator"
        pool_label = "Target"
        reversed_match = True
        print(f"  ** Target({len(targets)}) > Comparator({len(comparators)}): "
              f"Comparator 기준 1:{n_matches} Target 매칭으로 전환 **")

    print(f"  매칭 중: {len(anchor)} {anchor_label} x {n_matches} from "
          f"{len(pool)} {pool_label}...", end="", flush=True)
    t0 = time.time()

    # KDTree for fast nearest neighbor
    pool_logit = pool["logit_ps"].values.reshape(-1, 1)
    tree = cKDTree(pool_logit)

    matched_anchor_idx = []
    matched_pool_idx = []
    used_pool = set()

    # anchor를 랜덤 순서로
    anchor_order = np.random.permutation(len(anchor))

    for ai in anchor_order:
        a_logit = anchor.iloc[ai]["logit_ps"]

        # 가까운 pool 후보 찾기
        dists, idxs = tree.query([a_logit], k=min(n_matches * 10, len(pool)))

        matches_found = 0
        for d, pi in zip(dists, idxs):
            if d > caliper_val:
                break
            if pi not in used_pool:
                matched_anchor_idx.append(anchor.index[ai])
                matched_pool_idx.append(pool.index[pi])
                used_pool.add(pi)
                matches_found += 1
                if matches_found >= n_matches:
                    break

    elapsed = time.time() - t0
    n_matched_anchors = len(set(matched_anchor_idx))
    n_matched_pools = len(matched_pool_idx)

    print(f" {elapsed:.1f}초")

    if reversed_match:
        n_matched_targets = n_matched_pools
        n_matched_comps = n_matched_anchors
        ratio = n_matched_targets / max(n_matched_comps, 1)
        print(f"  결과: {n_matched_comps} comparators matched, {n_matched_pools} targets "
              f"(평균 {ratio:.1f} targets per comparator)")
    else:
        n_matched_targets = n_matched_anchors
        n_matched_comps = n_matched_pools
        ratio = n_matched_comps / max(n_matched_targets, 1)
        print(f"  결과: {n_matched_targets} targets matched, {n_matched_comps} comparators "
              f"(평균 {ratio:.1f}:1)")

    # 매칭된 환자만 추출
    matched_indices = list(set(matched_anchor_idx)) + matched_pool_idx
    matched_df = df.loc[matched_indices].copy()

    return matched_df, n_matched_targets, n_matched_comps


def run_cox_analysis(matched_df, outcomes_df, outcome_ids, target_id, comparator_id):
    """매칭 후 Cox regression (site로 층화)"""
    results = []

    for oid in outcome_ids:
        oid_float = float(oid)
        # outcome 발생 여부 & 시간
        oc = outcomes_df[outcomes_df["outcomeId"] == oid_float].copy()

        # 환자별 최초 outcome 발생일 (양수 = 노출 후)
        oc_positive = oc[oc["daysToEvent"] > 0]
        first_event = oc_positive.groupby("rowId")["daysToEvent"].min().reset_index()
        first_event.columns = ["rowId", "time_to_event"]

        # matched cohort와 merge
        analysis_df = matched_df[["rowId", "treatment", "daysToObsEnd", "site"]].copy()

        # riskWindowStart=1, riskWindowEnd=3650 (현재 연구 설정)
        analysis_df["max_follow"] = np.minimum(analysis_df["daysToObsEnd"], 3650)
        analysis_df = analysis_df[analysis_df["max_follow"] > 0]

        analysis_df = analysis_df.merge(first_event, on="rowId", how="left")

        # event가 follow-up 내에 있는지
        analysis_df["event"] = 0
        has_event = analysis_df["time_to_event"].notna() & (analysis_df["time_to_event"] <= analysis_df["max_follow"])
        analysis_df.loc[has_event, "event"] = 1

        # 생존 시간
        analysis_df["time"] = analysis_df["max_follow"]
        analysis_df.loc[has_event, "time"] = analysis_df.loc[has_event, "time_to_event"]

        n_target = (analysis_df["treatment"] == 1).sum()
        n_comp = (analysis_df["treatment"] == 0).sum()
        n_events_t = analysis_df.loc[analysis_df["treatment"] == 1, "event"].sum()
        n_events_c = analysis_df.loc[analysis_df["treatment"] == 0, "event"].sum()

        outcome_name = OUTCOME_NAMES.get(oid, str(oid))

        if n_events_t + n_events_c < 2:
            results.append({
                "target_id": target_id,
                "comparator_id": comparator_id,
                "outcome_id": oid,
                "outcome_name": outcome_name,
                "n_target": n_target,
                "n_comparator": n_comp,
                "events_target": int(n_events_t),
                "events_comparator": int(n_events_c),
                "hr": None,
                "ci_lower": None,
                "ci_upper": None,
                "p_value": None,
                "note": "insufficient events",
            })
            continue

        try:
            # Cox model (site 층화)
            cox_df = analysis_df[["time", "event", "treatment", "site"]].copy()
            cox_df["time"] = cox_df["time"].clip(lower=0.5)

            cph = CoxPHFitter()
            if cox_df["site"].nunique() > 1:
                cph.fit(cox_df[["time", "event", "treatment", "site"]],
                        duration_col="time", event_col="event", strata=["site"])
            else:
                cph.fit(cox_df[["time", "event", "treatment"]],
                        duration_col="time", event_col="event")

            hr = np.exp(cph.params_["treatment"])
            ci = np.exp(cph.confidence_intervals_.values[0])
            p = cph.summary["p"].values[0]

            results.append({
                "target_id": target_id,
                "comparator_id": comparator_id,
                "outcome_id": oid,
                "outcome_name": outcome_name,
                "n_target": n_target,
                "n_comparator": n_comp,
                "events_target": int(n_events_t),
                "events_comparator": int(n_events_c),
                "hr": round(hr, 4),
                "ci_lower": round(ci[0], 4),
                "ci_upper": round(ci[1], 4),
                "p_value": round(p, 6),
                "note": "",
            })
        except Exception as e:
            results.append({
                "target_id": target_id,
                "comparator_id": comparator_id,
                "outcome_id": oid,
                "outcome_name": outcome_name,
                "n_target": n_target,
                "n_comparator": n_comp,
                "events_target": int(n_events_t),
                "events_comparator": int(n_events_c),
                "hr": None,
                "ci_lower": None,
                "ci_upper": None,
                "p_value": None,
                "note": str(e)[:100],
            })

    return results


def main():
    np.random.seed(42)

    all_results = []

    for target_id, comparator_id in COMPARISONS:
        t_name = COHORT_NAMES[target_id]
        c_name = COHORT_NAMES[comparator_id]
        print("=" * 80)
        print(f"비교: {t_name} (t{target_id}) vs {c_name} (c{comparator_id})")
        print("=" * 80)

        # 1. 데이터 통합
        print("\n[1] 데이터 통합")
        cohorts_df, outcomes_df, covariates_df, cov_ref = pool_data(target_id, comparator_id)
        n_t = (cohorts_df["treatment"] == 1).sum()
        n_c = (cohorts_df["treatment"] == 0).sum()
        print(f"  통합: Target={n_t:,}, Comparator={n_c:,}, 총 {n_t+n_c:,}명")

        # 2. PS 적합
        print("\n[2] Propensity Score 적합")
        cohorts_df, ps_model = fit_propensity_score(cohorts_df, covariates_df)
        print(f"  PS 분포: Target mean={cohorts_df.loc[cohorts_df['treatment']==1, 'ps'].mean():.4f}, "
              f"Comparator mean={cohorts_df.loc[cohorts_df['treatment']==0, 'ps'].mean():.4f}")

        # 3. 1:2 매칭
        print("\n[3] 1:2 PS Matching")
        matched_df, n_mt, n_mc = match_1_to_n(cohorts_df, n_matches=2, caliper=0.2)

        # 4. Cox 분석
        print("\n[4] Cox Regression (site-stratified)")
        outcome_ids = list(OUTCOME_NAMES.keys())
        results = run_cox_analysis(matched_df, outcomes_df, outcome_ids, target_id, comparator_id)

        for r in results:
            if r["hr"] is not None:
                sig = "*" if r["p_value"] < 0.05 else ""
                print(f"  {r['outcome_name']:30s} HR={r['hr']:.3f} ({r['ci_lower']:.3f}-{r['ci_upper']:.3f}) "
                      f"p={r['p_value']:.4f}{sig}  events={r['events_target']}+{r['events_comparator']}")
            else:
                print(f"  {r['outcome_name']:30s} -- ({r['note']})")

        all_results.extend(results)

    # 결과 저장
    results_df = pd.DataFrame(all_results)
    out_path = os.path.join(OUTPUT_DIR, "ipd_pooled_1to2_matched_results.csv")
    results_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n{'='*80}")
    print(f"결과 저장: {out_path}")
    print(f"총 {len(results_df)}개 분석 ({len(results_df[results_df['hr'].notna()])}개 HR 산출)")


if __name__ == "__main__":
    main()
