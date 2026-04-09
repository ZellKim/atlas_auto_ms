"""
Common OMOP Concept ID Reference
=================================
자주 사용되는 OMOP Standard Concept ID 모음.
코호트 설계 시 concept_id 참고용.

Claude가 연구설계 YAML을 생성할 때 이 파일을 참조하면
정확한 concept_id를 사용할 수 있습니다.

Usage:
    from atlas_auto.data.concepts import PROCEDURES, CONDITIONS, DRUGS
    print(PROCEDURES["appendectomy"])  # 4198190
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Procedures (시술/수술)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PROCEDURES = {
    # 일반외과
    "appendectomy": 4198190,                    # 충수절제술
    "cholecystectomy": 4239323,                 # 담낭절제술
    "hernia_repair": 4331820,                   # 탈장 수리
    "colectomy": 4301351,                       # 대장절제술

    # 정형외과
    "total_knee_replacement": 4322471,          # 인공슬관절 전치환술
    "total_hip_replacement": 4202434,           # 인공고관절 전치환술

    # 심혈관
    "coronary_artery_bypass": 4336464,          # 관상동맥우회술 (CABG)
    "percutaneous_coronary_intervention": 4336465,  # PCI

    # 기타
    "cesarean_section": 4015701,                # 제왕절개
    "hysterectomy": 4297550,                    # 자궁적출술
    "tonsillectomy": 4180248,                   # 편도절제술
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Conditions (진단)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONDITIONS = {
    # 소화기
    "ulcerative_colitis": 81893,                # 궤양성 대장염
    "crohns_disease": 201606,                   # 크론병
    "appendicitis": 440448,                     # 충수염
    "biliary_calculus": 196455,                 # 담석

    # 심혈관
    "myocardial_infarction": 4329847,           # 심근경색
    "acute_myocardial_infarction": 312327,      # 급성 심근경색
    "stroke": 372924,                           # 뇌졸중
    "ischemic_stroke": 443454,                  # 허혈성 뇌졸중
    "heart_failure": 316139,                    # 심부전
    "atrial_fibrillation": 313217,              # 심방세동
    "venous_thromboembolism": 4322025,          # 정맥혈전색전증
    "pulmonary_embolism": 440417,               # 폐색전증

    # 대사
    "type_2_diabetes": 201826,                  # 제2형 당뇨
    "type_1_diabetes": 201254,                  # 제1형 당뇨
    "hypertension": 316866,                     # 고혈압
    "hyperlipidemia": 432867,                   # 고지혈증
    "obesity": 433736,                          # 비만

    # 호흡기
    "asthma": 317009,                           # 천식
    "copd": 255573,                             # 만성폐쇄성폐질환
    "pneumonia": 255848,                        # 폐렴

    # 자가면역/알레르기
    "rheumatoid_arthritis": 80809,              # 류마티스 관절염
    "atopic_dermatitis": 200160,                # 아토피 피부염
    "psoriasis": 257628,                        # 건선
    "systemic_lupus": 257628,                   # SLE

    # 감염
    "c_difficile": 4307981,                     # C. difficile 감염
    "sepsis": 132797,                           # 패혈증
    "covid_19": 37311061,                       # COVID-19

    # 신경계
    "parkinsons_disease": 381270,               # 파킨슨병
    "alzheimers_disease": 378419,               # 알츠하이머병
    "epilepsy": 380378,                         # 간질

    # 종양
    "colorectal_cancer": 4180790,               # 대장암
    "breast_cancer": 4112853,                   # 유방암
    "lung_cancer": 4115276,                     # 폐암
    "gastric_cancer": 4247120,                  # 위암
    "liver_cancer": 4246127,                    # 간암
    "pancreatic_cancer": 4344500,               # 췌장암

    # 정신건강
    "major_depression": 440383,                 # 주요우울장애
    "anxiety_disorder": 441542,                 # 불안장애
    "bipolar_disorder": 436665,                 # 양극성 장애

    # 근골격
    "osteoporosis": 80502,                      # 골다공증
    "fracture": 4278672,                        # 골절

    # 신장
    "acute_kidney_injury": 197320,              # 급성 신손상
    "chronic_kidney_disease": 46271022,         # 만성 신장병

    # 간
    "liver_cirrhosis": 4212540,                 # 간경변
    "hepatitis_b": 4291005,                     # B형 간염
    "hepatitis_c": 192671,                      # C형 간염

    # 기타
    "anaphylaxis": 441202,                      # 아나필락시스
    "gi_bleeding": 192671,                      # 소화관 출혈
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Drugs (약물 - Ingredient level)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DRUGS = {
    # 진통제/소염제
    "aspirin": 1112807,
    "ibuprofen": 1177480,
    "acetaminophen": 1125315,
    "celecoxib": 1118084,
    "naproxen": 1115171,
    "diclofenac": 1124300,

    # 심혈관
    "atorvastatin": 1545958,
    "rosuvastatin": 40165636,
    "simvastatin": 1539403,
    "metoprolol": 1307046,
    "amlodipine": 1332418,
    "lisinopril": 1308216,
    "losartan": 1367500,
    "warfarin": 1310149,
    "rivaroxaban": 40228152,
    "apixaban": 43013024,
    "clopidogrel": 1322184,

    # 당뇨
    "metformin": 1503297,
    "insulin_glargine": 35602717,
    "empagliflozin": 46221581,
    "sitagliptin": 1580747,
    "pioglitazone": 1525215,
    "glimepiride": 1597756,
    "dapagliflozin": 43526465,

    # 항생제
    "amoxicillin": 1713332,
    "azithromycin": 1734104,
    "ciprofloxacin": 1797513,
    "levofloxacin": 1742253,
    "metronidazole": 1707687,
    "vancomycin": 1707164,

    # 호흡기
    "salbutamol": 1154343,              # albuterol
    "fluticasone": 1149560,
    "montelukast": 1154615,
    "tiotropium": 1150770,

    # 자가면역
    "methotrexate": 1305058,
    "adalimumab": 1119119,
    "infliximab": 937368,
    "tofacitinib": 42904205,

    # 정신건강
    "sertraline": 739138,
    "escitalopram": 715939,
    "fluoxetine": 755695,
    "quetiapine": 766814,
    "lithium": 715259,

    # PPI
    "omeprazole": 923645,
    "esomeprazole": 911735,
    "pantoprazole": 948078,
    "lansoprazole": 929887,

    # 기타
    "prednisone": 1518254,
    "dexamethasone": 1518254,
    "heparin": 1367571,
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Measurements (검사)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MEASUREMENTS = {
    # 혈액검사
    "glucose": 3004410,                         # 혈당
    "hba1c": 3004410,                           # HbA1c (glycated hemoglobin)
    "hemoglobin": 3000963,                      # 혈색소
    "wbc": 3000905,                             # 백혈구
    "platelet": 3024929,                        # 혈소판
    "creatinine": 3016723,                      # 크레아티닌
    "bun": 3013682,                             # BUN
    "egfr": 3049187,                            # eGFR
    "alt": 3006923,                             # ALT
    "ast": 3013721,                             # AST
    "total_bilirubin": 3024128,                 # 총빌리루빈
    "albumin": 3024561,                         # 알부민

    # 지질
    "total_cholesterol": 3027114,               # 총콜레스테롤
    "ldl": 3028437,                             # LDL
    "hdl": 3007070,                             # HDL
    "triglycerides": 3022192,                   # 중성지방

    # 기타
    "crp": 3010156,                             # CRP
    "tsh": 3016502,                             # TSH
    "potassium": 3023103,                       # 칼륨
    "sodium": 3019550,                          # 나트륨
    "inr": 3010813,                             # INR
    "systolic_bp": 3004249,                     # 수축기 혈압
    "diastolic_bp": 3012888,                    # 이완기 혈압
    "bmi": 3038553,                             # BMI
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Visit Types (방문 유형)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

VISIT_TYPES = {
    "inpatient": 9201,
    "outpatient": 9202,
    "er": 9203,
    "long_term_care": 42898160,
}


def search_concept(keyword: str) -> list:
    """키워드로 concept 검색 (로컬 레퍼런스에서)

    Args:
        keyword: 검색 키워드 (대소문자 무관)
    Returns:
        [(name, concept_id, category), ...]
    """
    keyword = keyword.lower()
    results = []
    for category_name, category_dict in [
        ("condition", CONDITIONS),
        ("procedure", PROCEDURES),
        ("drug", DRUGS),
        ("measurement", MEASUREMENTS),
    ]:
        for name, cid in category_dict.items():
            if keyword in name.lower():
                results.append((name, cid, category_name))
    return results
