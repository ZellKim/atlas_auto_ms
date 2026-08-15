"""Small HTTP fakes used by unit tests."""

from dataclasses import dataclass
from typing import Any, List, Optional


@dataclass
class FakeResponse:
    status_code: int = 200
    json_data: Any = None
    text: str = ""

    def json(self) -> Any:
        if isinstance(self.json_data, Exception):
            raise self.json_data
        return self.json_data


class FakeSession:
    def __init__(self, outcomes: Optional[List[Any]] = None):
        self.outcomes = list(outcomes or [])
        self.calls = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        if not self.outcomes:
            raise AssertionError("No fake response configured")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
