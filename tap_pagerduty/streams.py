import inspect
import os
from datetime import datetime
import time
from typing import Dict

import requests
import singer
from dateutil import tz

LOGGER = singer.get_logger()


class PagerdutyStream:
    BASE_URL = "https://api.pagerduty.com"

    def __init__(self, config, state):
        self.config = config
        self.token = config.get('token')
        self.email = config.get('email')
        self.state = state
        self.params = {
            "limit": config.get('limit', 100),
            "offset": 0,
            "since": f"{self.replication_key}>={config.get('since')}",
            "time_zone": config.get('time_zone', 'UTC')
        }
        self.schema = self.load_schema()
        self.metadata = singer.metadata.get_standard_metadata(schema=self.load_schema(),
                                                              key_properties=self.key_properties,
                                                              valid_replication_keys=self.valid_replication_keys,
                                                              replication_method=self.replication_method)

        config_stream_params = config.get('streams', {}).get(self.tap_stream_id)

        if config_stream_params is not None:
            for key in config_stream_params.keys():
                if key not in self.valid_params:
                    raise RuntimeError(f"/{self.tap_stream_id} endpoint does not support '{key}' parameter.")

            self.params.update(config_stream_params)

        for param in self.required_params:
            if param not in self.params.keys():
                if param == 'until':
                    self.params.update({"until": datetime.now(tz=tz.gettz(config.get('time_zone', 'UTC')))})
                else:
                    raise RuntimeError(f"Parameter '{param}' required but not supplied for /{self.tap_stream_id} endpoint.")

    def get(self, key: str):
        '''Custom get method so that Singer can
        access Class attributes using dict syntax.
        '''
        return inspect.getattr_static(self, key, default=None)

    def _get_abs_path(self, path: str) -> str:
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)

    def load_schema(self) -> Dict:
        '''Loads a JSON schema file for a given
        Pagerduty resource into a dict representation.
        '''
        schema_path = self._get_abs_path("schemas")
        return singer.utils.load_json(f"{schema_path}/{self.tap_stream_id}.json")

    def write_schema(self):
        '''Writes a Singer schema message.'''
        return singer.write_schema(stream_name=self.stream, schema=self.schema, key_properties=self.key_properties)

    def write_state(self):
        return singer.write_state(self.state)

    def _construct_headers(self) -> Dict:
        headers = requests.utils.default_headers()
        headers["Accept"] = "application/vnd.pagerduty+json;version=2"
        headers["User-Agent"] = "python-pagerduty-tap"
        headers["Authorization"] = f"Token token= {self.token}"
        headers["Content-Type"] = "application/json"
        headers["From"] = self.email
        return headers

    def _get(self, url_suffix: str, params: dict = None) -> Dict:
        url = self.BASE_URL + url_suffix
        headers = self._construct_headers()
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 429:
            LOGGER.warn("Rate limit reached. Trying again in 60 seconds.")
            time.sleep(60)
            response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def _list_resource(self, url_suffix: str, params: Dict = None):
        response = self._get(url_suffix=url_suffix, params=params)
        return PagerdutyResponse(self, url_suffix, params, response)

    def sync(self):
        if self.replication_method == 'INCREMENTAL':
            current_bookmark = singer.bookmarks.get_bookmark(state=self.state,
                                                             tap_stream_id=self.tap_stream_id,
                                                             key=self.replication_key,
                                                             default=None)
            if current_bookmark is not None:
                self.params.update({"since": f"{self.replication_key}>{current_bookmark}"})
                running_bookmark_dtime = datetime.strptime(current_bookmark, '%Y-%m-%dT%H:%M:%SZ')
            else:
                running_bookmark_dtime = None

        with singer.metrics.job_timer(job_type=f"list_{self.tap_stream_id}"):
            with singer.metrics.record_counter(endpoint=self.tap_stream_id) as counter:
                for page in self._list_resource(url_suffix=f"/{self.tap_stream_id}", params=self.params):
                    for record in page.get(self.tap_stream_id):
                        with singer.Transformer() as transformer:
                            transformed_record = transformer.transform(data=record, schema=self.schema)
                            singer.write_record(stream_name=self.stream, time_extracted=singer.utils.now(), record=transformed_record)
                            counter.increment()
                            if self.replication_method == 'INCREMENTAL':
                                record_bookmark_dtime = datetime.strptime(record.get(self.replication_key), '%Y-%m-%dT%H:%M:%SZ')
                                if (running_bookmark_dtime is None) or (record_bookmark_dtime > running_bookmark_dtime):
                                    running_bookmark_dtime = record_bookmark_dtime
                                    singer.bookmarks.write_bookmark(state=self.state,
                                                                    tap_stream_id=self.tap_stream_id,
                                                                    key=self.replication_key,
                                                                    val=record.get(self.replication_key))


class PagerdutyResponse:
    def __init__(self, client, url_suffix, params, response):
        self.client = client
        self.url_suffix = url_suffix
        self.params = params
        self.response = response

    def __iter__(self):
        self._iteration = 0
        return self

    def __next__(self):
        self._iteration += 1
        if self._iteration == 1:
            return self

        if self.response.get("more") is False:
            raise StopIteration

        if self.response.get("more") is True:
            self.params["offset"] += self.params["limit"]
            self.response = self.client._get(
                url_suffix=self.url_suffix, params=self.params
            )
            return self
        else:
            raise StopIteration

    def get(self, key, default=None):
        return self.response.get(key, default)


class IncidentsStream(PagerdutyStream):
    tap_stream_id = 'incidents'
    stream = 'IncidentsStream'
    key_properties = 'id'
    replication_key = 'last_status_change_at'
    valid_replication_keys = ['last_status_change_at']
    replication_method = 'FULL_TABLE'
    valid_params = [
        'since',
        'until',
        'date_range',
        'statuses[]',
        'incident_key',
        'service_ids[]',
        'team_ids[]',
        'user_ids[]',
        'urgencies[]',
        'time_zone',
        'sort_by',
        'include[]'
    ]
    required_params = []

    def __init__(self, config, state, **kwargs):
        super().__init__(config, state)


class ServicesStream(PagerdutyStream):
    tap_stream_id = 'services'
    stream = 'ServicesStream'
    key_properties = 'id'
    replication_key = 'created_at'
    valid_replication_keys = ['created_at']
    replication_method = 'FULL_TABLE'
    valid_params = [
        'team_ids[]',
        'time_zone',
        'sort_by',
        'query',
        'include[]',
    ]
    required_params = []

    def __init__(self, config, state, **kwargs):
        super().__init__(config, state)


class NotificationsStream(PagerdutyStream):
    tap_stream_id = 'notifications'
    stream = 'NotificationsStream'
    key_properties = 'id'
    replication_key = 'started_at'
    valid_replication_keys = ['started_at']
    replication_method = 'INCREMENTAL'
    valid_params = ['time_zone', 'since', 'until', 'filter', 'include']
    required_params = ['since', 'until']

    def __init__(self, config, state):
        super().__init__(config, state)


AVAILABLE_STREAMS = [
    IncidentsStream,
    ServicesStream,
    NotificationsStream
]
