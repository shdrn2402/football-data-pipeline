import pytest

from football_pipeline.extractors import football_api

PLAN_ERROR = {"plan": "Free plans do not have access to the Ids parameter."}


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

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
