"""Contract tests for the cohort-definition SQL generation WebAPI method.

`POST /cohortdefinition/sql` is the working pre-deployment gate for cohort
expressions on this WebAPI: `POST /cohortdefinition/check` answered HTTP 500 for
a valid nested-correlated expression on 2026-08-13.
"""

from copy import deepcopy
from inspect import signature
from unittest.mock import Mock

import pytest
import requests

from atlas_auto.client import FedernetClient


def make_client() -> FedernetClient:
    client = FedernetClient("https://example.test/atlas-resolve/v2.12.0/7/203/main")
    client.session = Mock()
    client.webapi_url = "https://example.test/WebAPI"
    return client


def test_cohort_definition_sql_posts_exact_payload_once_without_mutating_input():
    client = make_client()
    request = {
        "expression": {"PrimaryCriteria": {"CriteriaList": []}},
        "options": {"generateStats": False},
    }
    expected_request = deepcopy(request)
    response = client.session.post.return_value
    response.text = "SELECT 1"

    result = client.get_cohort_definition_sql(request)

    assert result == "SELECT 1"
    client.session.post.assert_called_once_with(
        "https://example.test/WebAPI/cohortdefinition/sql",
        json=expected_request,
    )
    response.raise_for_status.assert_called_once_with()
    assert request == expected_request


def test_cohort_definition_sql_does_not_retry_transport_failure():
    client = make_client()
    request = {"expression": {}, "options": {"generateStats": False}}
    expected_request = deepcopy(request)
    client.session.post.side_effect = [requests.ConnectionError("network down"), Mock()]

    with pytest.raises(requests.ConnectionError, match="network down"):
        client.get_cohort_definition_sql(request)

    client.session.post.assert_called_once_with(
        "https://example.test/WebAPI/cohortdefinition/sql",
        json=expected_request,
    )
    assert request == expected_request


def test_cohort_definition_sql_exposes_declared_return_contract():
    method_signature = signature(FedernetClient.get_cohort_definition_sql)

    assert method_signature.parameters["request"].annotation is dict
    assert method_signature.return_annotation is str
