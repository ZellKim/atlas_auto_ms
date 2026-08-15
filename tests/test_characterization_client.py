"""Contract tests for Characterization-related WebAPI methods."""

import pytest
import requests

from atlas_auto.client import FedernetClient

from .fakes import FakeResponse, FakeSession


def make_client(session: FakeSession) -> FedernetClient:
    client = FedernetClient("https://example.test/atlas-resolve/v2.12.0/7/203/main")
    client.session = session
    client.webapi_url = "https://example.test/WebAPI/"
    return client


def test_safe_feature_analysis_list_retries_transient_response(monkeypatch):
    session = FakeSession(
        [
            FakeResponse(status_code=503, text="temporarily unavailable"),
            FakeResponse(json_data={"content": [{"id": 17, "name": "FA"}]}),
        ]
    )
    client = make_client(session)
    monkeypatch.setattr("atlas_auto.client.time.sleep", lambda _seconds: None)

    result = client.list_feature_analyses(size=200)

    assert result == [{"id": 17, "name": "FA"}]
    assert len(session.calls) == 2
    assert all(call[2]["timeout"] == (10, 30) for call in session.calls)


def test_feature_analysis_create_never_retries_mutation():
    session = FakeSession([requests.ConnectionError("network down")])
    client = make_client(session)

    with pytest.raises(requests.ConnectionError):
        client.create_feature_analysis({"name": "FA"})

    assert len(session.calls) == 1


def test_api_error_redacts_secrets_and_identifies_endpoint():
    session = FakeSession(
        [
            FakeResponse(
                status_code=400,
                text='{"password":"do-not-leak","message":"invalid"}',
            )
        ]
    )
    client = make_client(session)

    with pytest.raises(requests.RequestException) as exc_info:
        client.create_feature_analysis({"password": "also-secret"})

    message = str(exc_info.value)
    assert exc_info.type.__name__ == "AtlasApiError"
    assert "POST /feature-analysis/" in message
    assert "400" in message
    assert "do-not-leak" not in message
    assert "also-secret" not in message


ENDPOINT_CASES = [
    ("get_feature_analysis", (372,), "GET", "/feature-analysis/372", None, None, (10, 30), {"id": 372}),
    ("copy_feature_analysis", (372,), "GET", "/feature-analysis/372/copy", None, None, (10, 30), {"id": 901}),
    ("update_feature_analysis", (901, {"id": 901}), "PUT", "/feature-analysis/901", None, {"id": 901}, (10, 30), {"id": 901}),
    ("delete_feature_analysis", (901,), "DELETE", "/feature-analysis/901", None, None, (10, 30), None),
    ("list_characterizations", (), "GET", "/cohort-characterization/", {"size": 200}, None, (10, 30), [{"id": 121}]),
    ("get_characterization", (121,), "GET", "/cohort-characterization/121", None, None, (10, 30), {"id": 121}),
    ("create_characterization", ({"name": "cc"},), "POST", "/cohort-characterization/", None, {"name": "cc"}, (10, 30), {"id": 121}),
    ("update_characterization", (121, {"id": 121}), "PUT", "/cohort-characterization/121", None, {"id": 121}, (10, 30), {"id": 121}),
    ("delete_characterization", (121,), "DELETE", "/cohort-characterization/121", None, None, (10, 30), None),
    ("export_characterization", (121,), "GET", "/cohort-characterization/121/export", None, None, (10, 30), {"name": "cc"}),
    ("import_characterization", ({"name": "cc"},), "POST", "/cohort-characterization/import", None, {"name": "cc"}, (10, 30), {"id": 122}),
    ("generate_characterization", (121, "cdm"), "POST", "/cohort-characterization/121/generation/cdm", None, None, (10, 30), {"id": 77}),
    ("get_characterization_generations", (121,), "GET", "/cohort-characterization/121/generation", None, None, (10, 30), [{"id": 77}]),
    ("get_characterization_result_count", (77,), "GET", "/cohort-characterization/generation/77/result/count", None, None, (10, 30), 3),
    # thresholdLevel must default to 0. A non-zero default silently drops
    # sub-threshold covariate rows, and a missing row reads as a zero
    # downstream (KHNMC 2026-08-14: 57 reported, 51 returned).
    ("get_characterization_results", (77,), "GET", "/cohort-characterization/generation/77/result", {"thresholdLevel": 0}, None, (10, 120), [{"featureId": 1}]),
    ("delete_characterization_generation", (77,), "DELETE", "/cohort-characterization/generation/77", None, None, (10, 30), None),
]


@pytest.mark.parametrize(
    "method_name,args,http_method,path,params,json_body,timeout,json_result",
    ENDPOINT_CASES,
)
def test_characterization_endpoint_contracts(
    method_name,
    args,
    http_method,
    path,
    params,
    json_body,
    timeout,
    json_result,
):
    response = (
        FakeResponse(status_code=204)
        if json_result is None
        else FakeResponse(json_data=json_result)
    )
    session = FakeSession([response])
    client = make_client(session)

    result = getattr(client, method_name)(*args)

    assert result == json_result
    assert len(session.calls) == 1
    called_method, called_url, kwargs = session.calls[0]
    assert called_method == http_method
    assert called_url.endswith(path)
    assert kwargs["timeout"] == timeout
    assert kwargs.get("params") == params
    assert kwargs.get("json") == json_body


RETRY_CASES = [
    ("get_feature_analysis", (372,), True, {"id": 372}),
    ("copy_feature_analysis", (372,), False, {"id": 901}),
    ("update_feature_analysis", (901, {"id": 901}), False, {"id": 901}),
    ("delete_feature_analysis", (901,), False, None),
    ("list_characterizations", (), True, []),
    ("get_characterization", (121,), True, {"id": 121}),
    ("create_characterization", ({"name": "cc"},), False, {"id": 121}),
    ("update_characterization", (121, {"id": 121}), False, {"id": 121}),
    ("delete_characterization", (121,), False, None),
    ("export_characterization", (121,), True, {"name": "cc"}),
    ("import_characterization", ({"name": "cc"},), False, {"id": 122}),
    ("generate_characterization", (121, "cdm"), False, {"id": 77}),
    ("get_characterization_generations", (121,), True, []),
    ("get_characterization_result_count", (77,), True, 0),
    ("get_characterization_results", (77,), True, []),
    ("delete_characterization_generation", (77,), False, None),
]


@pytest.mark.parametrize("method_name,args,retry_safe,json_result", RETRY_CASES)
def test_only_explicitly_safe_characterization_calls_retry(
    monkeypatch, method_name, args, retry_safe, json_result
):
    monkeypatch.setattr("atlas_auto.client.time.sleep", lambda _seconds: None)
    response = (
        FakeResponse(status_code=204)
        if json_result is None
        else FakeResponse(json_data=json_result)
    )
    session = FakeSession([requests.Timeout("temporary"), response])
    client = make_client(session)

    if retry_safe:
        getattr(client, method_name)(*args)
        assert len(session.calls) == 2
    else:
        with pytest.raises(requests.Timeout):
            getattr(client, method_name)(*args)
        assert len(session.calls) == 1


def test_feature_analysis_list_sends_type_filter():
    session = FakeSession([FakeResponse(json_data=[])])
    client = make_client(session)

    client.list_feature_analyses(size=50, analysis_type="PRESET")

    assert session.calls[0][2]["params"] == {"size": 50, "type": "PRESET"}


def test_pathway_list_requests_enough_rows_for_exact_name_preflight():
    session = FakeSession(
        [FakeResponse(json_data={"content": [{"id": 140, "name": "P1"}]})]
    )
    client = make_client(session)

    result = client.list_pathway_analyses(size=2000)

    assert result == [{"id": 140, "name": "P1"}]
    assert session.calls[0][2]["params"] == {"size": 2000}
