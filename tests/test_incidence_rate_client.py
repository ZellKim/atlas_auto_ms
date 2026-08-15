"""Contract tests for Incidence Rate WebAPI methods."""

from copy import deepcopy
from inspect import signature
from typing import Any
from unittest.mock import Mock

import pytest
import requests

from atlas_auto.client import FedernetClient


def make_client() -> FedernetClient:
    client = FedernetClient("https://example.test/atlas-resolve/v2.12.0/7/203/main")
    client.session = Mock()
    client.webapi_url = "https://example.test/WebAPI"
    return client


def test_incidence_rate_sql_posts_exact_payload_once_without_mutating_input():
    client = make_client()
    request = {
        "analysisId": 0,
        "expression": {"targetIds": [2684, 2685], "outcomeIds": [2636]},
    }
    expected_request = deepcopy(request)
    response = client.session.post.return_value
    response.json.return_value = {"templateSql": "select 1"}

    result = client.get_incidence_rate_sql(request)

    assert result == {"templateSql": "select 1"}
    client.session.post.assert_called_once_with(
        "https://example.test/WebAPI/ir/sql",
        json=expected_request,
    )
    response.raise_for_status.assert_called_once_with()
    assert request == expected_request


def test_incidence_rate_sql_does_not_retry_transport_failure():
    client = make_client()
    request = {"analysisId": 0, "expression": {"targetIds": [2687, 2688]}}
    expected_request = deepcopy(request)
    client.session.post.side_effect = [
        requests.ConnectionError("network down"),
        Mock(),
    ]

    with pytest.raises(requests.ConnectionError, match="network down"):
        client.get_incidence_rate_sql(request)

    client.session.post.assert_called_once_with(
        "https://example.test/WebAPI/ir/sql",
        json=expected_request,
    )
    assert request == expected_request


def test_incidence_rate_sql_exposes_declared_return_contract():
    method_signature = signature(FedernetClient.get_incidence_rate_sql)

    assert method_signature.parameters["request"].annotation is dict
    assert method_signature.return_annotation is Any
