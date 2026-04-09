"""
atlas-auto: OHDSI ATLAS/feedernet Automation Toolkit
=====================================================
feedernet 포탈 로그인 → 기관별 ATLAS WebAPI를 통한
코호트 설계, Estimation 실행, 결과 다운로드 자동화 패키지
"""

from atlas_auto.client import FedernetClient
from atlas_auto.builder import EstimationBuilder
from atlas_auto.cohort_designer import CohortDesigner
from atlas_auto.protocol import StudyProtocol
from atlas_auto.runner import run_remote_site, run_local_r_study, run_study

__version__ = "0.2.0"

__all__ = [
    "FedernetClient",
    "EstimationBuilder",
    "CohortDesigner",
    "StudyProtocol",
    "run_remote_site",
    "run_local_r_study",
    "run_study",
]
