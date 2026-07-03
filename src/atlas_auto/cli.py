"""
atlas-auto CLI
==============
커맨드라인에서 실행:
    atlas-auto run --config config.yaml
    atlas-auto run --config config.yaml --sites remote_only
    atlas-auto status --config config.yaml --project 2908 --analysis 10858
    atlas-auto download --config config.yaml --project 2908 --analysis 10858
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import yaml


def cmd_run(args):
    """통합 실행"""
    from atlas_auto.runner import run_study

    results = run_study(
        config_path=args.config,
        sites=args.sites,
        estimation_spec_path=args.estimation_spec,
    )

    print("\n" + "=" * 60)
    print("실행 결과 요약")
    print("=" * 60)
    for site, result in results.items():
        status = result.get("status", "unknown") if isinstance(result, dict) else result
        print(f"  {site}: {status}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n상세 결과: {args.output}")


def cmd_status(args):
    """실행 상태 확인"""
    from atlas_auto.client import FedernetClient, classify_execution_status

    config = _load_config(args.config)
    client = _login(config)

    summary = client.get_analysis_execution_summary(args.project, args.analysis)

    # 정렬 우선순위는 요약 버킷(classify) 기준 — 원시 상태값 누락으로 인한 오정렬 방지.
    bucket_order = {"RUNNING": 0, "WAITING": 1, "COMPLETE": 2, "FAILED": 3, "CANCELED": 4}

    print("=" * 100)
    print(f"Project {args.project} / Analysis {args.analysis} 실행 현황")
    print("=" * 100)
    print(f"{'상태':<12} {'기관명':<30} {'CDM':<28} {'시작':<18} {'소요시간':<12}")
    print("-" * 100)

    sorted_cdms = sorted(
        summary["by_cdm"].items(),
        key=lambda x: bucket_order.get(
            classify_execution_status(x[1].get("executionStatus", "")), 99),
    )

    for cdm, ex in sorted_cdms:
        status = ex.get("executionStatus", "?")
        org = ex.get("orgName", "?")
        started = (ex.get("startedAt") or "?")[:16]
        exec_time = ex.get("executingTime") or "-"

        tag = classify_execution_status(status)
        print(f"{tag:<12} {org:<30} {cdm:<28} {started:<18} {exec_time:<12}")

    print("-" * 100)
    c = summary["counts"]
    print(f"\n총 {summary['total']}개 기관")
    print(f"  COMPLETE: {c['COMPLETE']}  |  RUNNING: {c['RUNNING']}  |  "
          f"FAILED: {c['FAILED']}  |  CANCELED: {c['CANCELED']}  |  WAITING: {c['WAITING']}")


def cmd_download(args):
    """완료 기관 결과 일괄 다운로드"""
    from atlas_auto.client import FedernetClient

    config = _load_config(args.config)
    client = _login(config)

    output_dir = Path(args.output_dir or "./results")
    output_dir.mkdir(parents=True, exist_ok=True)

    groups = client.get_analysis_executions(args.project, args.analysis)

    latest_completed = {}
    for group in groups:
        if args.research and group.get("researchName") != args.research:
            continue
        for ex in group.get("executionList", []):
            if ex.get("executionStatus") == "FINISHED_SUCCESSFULLY":
                cdm = ex.get("cdmName", "?")
                if cdm not in latest_completed:
                    latest_completed[cdm] = ex

    print(f"완료된 기관: {len(latest_completed)}개")

    success, fail = 0, 0
    for cdm, ex in sorted(latest_completed.items()):
        exec_id = ex["id"]
        save_name = f"{cdm}_{exec_id}_result.zip"
        save_path = str(output_dir / save_name)

        if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
            size_mb = os.path.getsize(save_path) / (1024 * 1024)
            print(f"  [{cdm}] 이미 존재: {save_name} ({size_mb:.1f} MB)")
            success += 1
            continue

        try:
            print(f"  [{cdm}] {ex.get('orgName', '?')} 다운로드 중...", end="", flush=True)
            client.download_execution_result(
                args.project, args.analysis, exec_id, save_path)
            size_mb = os.path.getsize(save_path) / (1024 * 1024)
            print(f" {size_mb:.1f} MB")
            success += 1
        except Exception as e:
            print(f" FAILED: {e}")
            fail += 1

    print(f"\n완료: {success}건 성공, {fail}건 실패")


def cmd_protocol(args):
    """프로토콜 YAML로 전체 파이프라인 실행"""
    from atlas_auto.protocol import StudyProtocol

    protocol = StudyProtocol.from_yaml(args.study)

    print(protocol.summary())
    print()

    if args.dry_run:
        result = protocol.run(
            config_path=args.config,
            output_dir=args.output_dir,
            dry_run=True,
        )
        print(f"\nDry run 완료:")
        print(f"  코호트 JSON: {result.get('cohort_jsons')}")
        print(f"  Estimation 스펙: {result.get('estimation_spec')}")
    else:
        result = protocol.run(
            config_path=args.config,
            output_dir=args.output_dir,
        )
        print(f"\n실행 결과: {result.get('status')}")
        if result.get("result_file"):
            print(f"결과 파일: {result['result_file']}")


def cmd_concepts(args):
    """concept 검색"""
    from atlas_auto.data.concepts import search_concept
    results = search_concept(args.keyword)
    if not results:
        print(f"'{args.keyword}'에 대한 결과 없음")
        return
    print(f"{'Name':<35} {'Concept ID':>12}  {'Category':<15}")
    print("-" * 65)
    for name, cid, cat in results:
        print(f"{name:<35} {cid:>12}  {cat:<15}")


def _load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _login(config: dict) -> "FedernetClient":
    from atlas_auto.client import FedernetClient

    portal = config.get("portal", {})
    client = FedernetClient(portal.get("url"))

    if portal.get("bearer_token"):
        client.login_with_bearer_token(portal["bearer_token"])
    elif portal.get("cookie_string"):
        client.login_with_cookie_string(portal["cookie_string"])
    elif portal.get("email") and portal.get("password"):
        client.login_portal(portal["email"], portal["password"])
    else:
        print("경고: 인증 정보 없음", file=sys.stderr)

    return client


def main():
    parser = argparse.ArgumentParser(
        prog="atlas-auto",
        description="OHDSI ATLAS/feedernet Automation Toolkit",
    )
    sub = parser.add_subparsers(dest="command")

    # run
    p_run = sub.add_parser("run", help="연구 실행 (본원+타기관)")
    p_run.add_argument("--config", required=True, help="config.yaml 경로")
    p_run.add_argument("--sites", choices=["all", "local_only", "remote_only"], default="all")
    p_run.add_argument("--estimation-spec", default=None, help="Estimation JSON 스펙 파일")
    p_run.add_argument("--output", default=None, help="결과 JSON 저장 경로")

    # status
    p_status = sub.add_parser("status", help="실행 상태 확인")
    p_status.add_argument("--config", required=True)
    p_status.add_argument("--project", type=int, required=True, help="프로젝트 ID")
    p_status.add_argument("--analysis", type=int, required=True, help="Analysis ID")

    # download
    p_dl = sub.add_parser("download", help="결과 일괄 다운로드")
    p_dl.add_argument("--config", required=True)
    p_dl.add_argument("--project", type=int, required=True)
    p_dl.add_argument("--analysis", type=int, required=True)
    p_dl.add_argument("--research", default=None, help="연구 패키지명 필터")
    p_dl.add_argument("--output-dir", default="./results", help="저장 디렉토리")

    # protocol
    p_proto = sub.add_parser("protocol", help="프로토콜 YAML로 전체 파이프라인 실행")
    p_proto.add_argument("--study", required=True, help="연구설계 YAML 파일")
    p_proto.add_argument("--config", default=None, help="config.yaml (인증 정보)")
    p_proto.add_argument("--output-dir", default="./output", help="결과 저장 디렉토리")
    p_proto.add_argument("--dry-run", action="store_true", help="JSON 생성만 (ATLAS 실행 안 함)")

    # concepts
    p_concepts = sub.add_parser("concepts", help="OMOP Concept ID 검색")
    p_concepts.add_argument("keyword", help="검색 키워드")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if args.command == "run":
        cmd_run(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "download":
        cmd_download(args)
    elif args.command == "protocol":
        cmd_protocol(args)
    elif args.command == "concepts":
        cmd_concepts(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
