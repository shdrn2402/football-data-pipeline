import pytest

from football_pipeline.extractors import football_api

PLAN_ERROR = {"plan": "Free plans do not have access to the Ids parameter."}


class FakeResponse:
    def __init__(self, data, status_code=200, headers=None):
        self.data = data
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise football_api.requests.exceptions.HTTPError(str(self.status_code))

    def json(self):
        return self.data


def make_page(records, current, total, errors=None):
    return {
        "errors": errors or [],
        "results": len(records),
        "paging": {"current": current, "total": total},
        "response": records,
    }


def fake_pages(monkeypatch, pages):
    responses = iter(pages)
    monkeypatch.setattr(
        football_api.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(next(responses)),
    )


def fetch():
    return football_api.fetch_data(url="https://api.test", headers={}, timeout=(1, 1))


def test_fetch_data_combines_all_pages(monkeypatch):
    fake_pages(monkeypatch, [make_page([1, 2], 1, 2), make_page([3], 2, 2)])

    payload = fetch()

    assert payload["response"] == [1, 2, 3]
    assert payload["results"] == 3
    assert payload["paging"] == {"current": 2, "total": 2}


@pytest.mark.parametrize(
    "pages",
    [
        pytest.param([make_page([], 1, 1, PLAN_ERROR)], id="first-page"),
        pytest.param(
            [make_page([1], 1, 2), make_page([], 2, 2, PLAN_ERROR)],
            id="later-page",
        ),
    ],
)
def test_fetch_data_fails_on_plan_error(monkeypatch, pages):
    fake_pages(monkeypatch, pages)

    with pytest.raises(ValueError, match=f"on page {len(pages)}.*plan"):
        fetch()


OK_PAGE = make_page([1], 1, 1)
RATE_LIMITED = make_page([], 1, 1, {"rateLimit": "Too many requests."})
EXHAUSTED = {"x-ratelimit-requests-remaining": "0"}


def fake_attempts(monkeypatch, outcomes):
    """Replays responses or exceptions and records the waits between them."""
    attempts = iter(outcomes)
    waits = []

    def fake_get(*args, **kwargs):
        outcome = next(attempts)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(football_api.requests, "get", fake_get)
    monkeypatch.setattr(football_api.time, "sleep", waits.append)
    return waits


def fetch_with_retries():
    return football_api.fetch_data(
        url="https://api.test",
        headers={},
        timeout=(1, 1),
        max_retries=2,
        retry_delay_seconds=15,
    )


@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(
            football_api.requests.exceptions.ConnectionError(), id="connection"
        ),
        pytest.param(football_api.requests.exceptions.ReadTimeout(), id="timeout"),
        pytest.param(FakeResponse({}, status_code=429), id="http-429"),
        pytest.param(FakeResponse({}, status_code=503), id="http-503"),
        pytest.param(FakeResponse(RATE_LIMITED), id="rate-limit-in-body"),
    ],
)
def test_temporary_failure_is_retried_with_backoff(monkeypatch, failure):
    waits = fake_attempts(monkeypatch, [failure, failure, FakeResponse(OK_PAGE)])

    assert fetch_with_retries()["response"] == [1]
    assert waits == [15, 30]


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        pytest.param(
            football_api.requests.exceptions.ConnectionError(),
            football_api.requests.exceptions.ConnectionError,
            id="connection",
        ),
        pytest.param(
            FakeResponse({}, status_code=500),
            football_api.requests.exceptions.HTTPError,
            id="http-500",
        ),
        pytest.param(FakeResponse(RATE_LIMITED), ValueError, id="rate-limit-in-body"),
    ],
)
def test_lasting_failure_raises_after_all_retries(monkeypatch, failure, error):
    waits = fake_attempts(monkeypatch, [failure] * 3)

    with pytest.raises(error):
        fetch_with_retries()

    assert waits == [15, 30]


@pytest.mark.parametrize(
    ("response", "error"),
    [
        pytest.param(
            FakeResponse({}, status_code=429, headers=EXHAUSTED),
            football_api.requests.exceptions.HTTPError,
            id="daily-quota-http",
        ),
        pytest.param(
            FakeResponse(RATE_LIMITED, headers=EXHAUSTED),
            ValueError,
            id="daily-quota-body",
        ),
        pytest.param(
            FakeResponse({}, status_code=403),
            football_api.requests.exceptions.HTTPError,
            id="client-error",
        ),
        pytest.param(
            FakeResponse(make_page([], 1, 1, PLAN_ERROR)), ValueError, id="plan"
        ),
    ],
)
def test_permanent_failure_is_not_retried(monkeypatch, response, error):
    waits = fake_attempts(monkeypatch, [response])

    with pytest.raises(error):
        fetch_with_retries()

    assert waits == []
