import json

import pytest

from tap_pagerduty.streams import (EscalationPoliciesStream, IncidentsStream,
                                   NotificationsStream, ServicesStream)


@pytest.fixture(scope='function')
def config(shared_datadir):
    with open(shared_datadir / 'test.config.json') as f:
        return json.load(f)


@pytest.fixture(scope='function')
def state(shared_datadir):
    with open(shared_datadir / 'test.state.json') as f:
        return json.load(f)


@pytest.fixture(scope='function', params={IncidentsStream, ServicesStream, NotificationsStream, EscalationPoliciesStream})
def client(config, state, shared_datadir, request):
    return request.param(token=config.get("token"),
                         email=config.get("email"),
                         config=config,
                         state=state)
