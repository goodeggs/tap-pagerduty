import pytest
import requests

from tap_pagerduty.streams import is_fatal_code


@pytest.mark.parametrize('status_code', [400, 401, 403, 404,
                                         pytest.param(429, marks=pytest.mark.xfail),
                                         pytest.param(500, marks=pytest.mark.xfail),
                                         pytest.param(502, marks=pytest.mark.xfail),
                                         pytest.param(503, marks=pytest.mark.xfail),
                                         pytest.param(504, marks=pytest.mark.xfail)])
def test_is_fatal_code(status_code):
    resp = requests.models.Response()
    resp.status_code = status_code
    exc = requests.exceptions.RequestException(response=resp)
    assert is_fatal_code(exc)
