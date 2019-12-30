import inspect
import os
from datetime import datetime, timedelta
from typing import ClassVar, Dict, List, Optional

import backoff
import requests
import singer

LOGGER = singer.get_logger()


def is_fatal_code(e: requests.exceptions.RequestException) -> bool:
    '''Helper function to determine if a Requests reponse status code
    is a "fatal" status code. If it is, the backoff decorator will giveup
    instead of attemtping to backoff.'''
    return 400 <= e.response.status_code < 500 and e.response.status_code != 429


class PagerdutyStream:
    base_url: ClassVar[str] = "https://api.pagerduty.com"
    tap_stream_id: ClassVar[Optional[str]] = None

    def __init__(self, config, state):
        self.config = config
        self.token = config.get('token')
        self.email = config.get('email')
        self.state = state
        self.params = {
            "limit": config.get('limit', 100),
            "offset": 0,
            "since": config.get('since'),
            "time_zone": "UTC"
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
                    self.params.update({"until": datetime.strftime(datetime.utcnow(), '%Y-%m-%dT%H:%M:%SZ')})
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

    @backoff.on_exception(backoff.fibo,
                          requests.exceptions.HTTPError,
                          max_time=120,
                          giveup=is_fatal_code,
                          logger=LOGGER)
    @backoff.on_exception(backoff.fibo,
                          (requests.exceptions.ConnectionError,
                           requests.exceptions.Timeout),
                          max_time=120,
                          logger=LOGGER)
    def _get(self, url_suffix: str, params: Dict = None) -> Dict:
        url = self.base_url + url_suffix
        headers = self._construct_headers()
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def update_bookmark(self, bookmark, value):
        if bookmark is None:
            new_bookmark = value
        else:
            new_bookmark = max(bookmark, value)
        return new_bookmark

    def _list_resource(self, url_suffix: str, params: Dict = None):
        response = self._get(url_suffix=url_suffix, params=params)
        return PagerdutyResponse(self, url_suffix, params, response)


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
    tap_stream_id: ClassVar[str] = 'incidents'
    stream: ClassVar[str] = 'incidents'
    key_properties: ClassVar[str] = 'id'
    replication_key: ClassVar[str] = 'last_status_change_at'
    valid_replication_keys: ClassVar[List[str]] = ['last_status_change_at']
    replication_method: ClassVar[str] = 'FULL_TABLE'
    valid_params: ClassVar[List[str]] = [
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
    required_params: ClassVar[List[str]] = ['until']

    def __init__(self, config, state, **kwargs):
        super().__init__(config, state)

    def sync(self):
        current_bookmark = singer.bookmarks.get_bookmark(state=self.state,
                                                         tap_stream_id=self.tap_stream_id,
                                                         key=self.replication_key,
                                                         default=None)

        if current_bookmark is not None:
            current_bookmark_dtime = datetime.strptime(current_bookmark, '%Y-%m-%dT%H:%M:%SZ')
        else:
            current_bookmark_dtime = None

        since_dtime = datetime.strptime(self.params.get("since"), '%Y-%m-%dT%H:%M:%SZ')
        until_dtime = datetime.strptime(self.params.get("until"), '%Y-%m-%dT%H:%M:%SZ')
        request_range_limit = timedelta(days=179)

        running_bookmark_dtime = None
        with singer.metrics.job_timer(job_type=f"list_{self.tap_stream_id}"):
            with singer.metrics.record_counter(endpoint=self.tap_stream_id) as counter:
                while since_dtime < until_dtime:
                    range = {
                        "offset": 0,  # Reset the offset each time.
                        "since": datetime.strftime(since_dtime, '%Y-%m-%dT%H:%M:%SZ'),
                        "until": datetime.strftime(min(since_dtime + request_range_limit, until_dtime), '%Y-%m-%dT%H:%M:%SZ')
                    }
                    self.params.update(range)
                    for page in self._list_resource(url_suffix=f"/{self.tap_stream_id}", params=self.params):
                        for record in page.get(self.tap_stream_id):
                            record_replication_key_dtime = datetime.strptime(record.get(self.replication_key), '%Y-%m-%dT%H:%M:%SZ')

                            substream_params = {
                                "limit": 100,
                                "offset": 0,
                                "time_zone": "UTC"
                            }
                            record['log_entries'] = []
                            for page in self._list_resource(url_suffix=f"/{self.tap_stream_id}/{record.get('id')}/log_entries", params=substream_params):
                                record['log_entries'].extend(page.get('log_entries'))

                            record['alerts'] = []
                            for page in self._list_resource(url_suffix=f"/{self.tap_stream_id}/{record.get('id')}/alerts", params=substream_params):
                                record['alerts'].extend(page.get('alerts'))

                            if self.replication_method == 'INCREMENTAL':
                                if (current_bookmark_dtime is None) or (record_replication_key_dtime >= current_bookmark_dtime):
                                    with singer.Transformer() as transformer:
                                        transformed_record = transformer.transform(data=record, schema=self.schema)
                                        singer.write_record(stream_name=self.stream, time_extracted=singer.utils.now(), record=transformed_record)
                                        counter.increment()
                                        running_bookmark_dtime = self.update_bookmark(running_bookmark_dtime, record_replication_key_dtime)
                            else:
                                with singer.Transformer() as transformer:
                                    transformed_record = transformer.transform(data=record, schema=self.schema)
                                    singer.write_record(stream_name=self.stream, time_extracted=singer.utils.now(), record=transformed_record)
                                    counter.increment()

                    since_dtime += request_range_limit

        if self.replication_method == 'INCREMENTAL':
            running_bookmark_str = datetime.strftime(running_bookmark_dtime, '%Y-%m-%dT%H:%M:%SZ')
            singer.bookmarks.write_bookmark(state=self.state,
                                            tap_stream_id=self.tap_stream_id,
                                            key=self.replication_key,
                                            val=running_bookmark_str)


class EscalationPoliciesStream(PagerdutyStream):
    tap_stream_id: ClassVar[str] = 'escalation_policies'
    stream: ClassVar[str] = 'escalation_policies'
    key_properties: ClassVar[str] = 'id'
    valid_replication_keys: ClassVar[List[str]] = []
    replication_method: ClassVar[str] = 'FULL_TABLE'
    valid_params: ClassVar[List[str]] = [
        'user_ids[]',
        'team_ids[]',
        'sort_by',
        'query',
        'include[]',
    ]
    required_params: ClassVar[List[str]] = []

    def __init__(self, config, state, **kwargs):
        super().__init__(config, state)

    def sync(self):
        with singer.metrics.job_timer(job_type=f"list_{self.tap_stream_id}"):
            with singer.metrics.record_counter(endpoint=self.tap_stream_id) as counter:
                for page in self._list_resource(url_suffix=f"/{self.tap_stream_id}", params=self.params):
                    for record in page.get(self.tap_stream_id):
                        with singer.Transformer() as transformer:
                            transformed_record = transformer.transform(data=record, schema=self.schema)
                            singer.write_record(stream_name=self.stream, time_extracted=singer.utils.now(), record=transformed_record)
                            counter.increment()


class ServicesStream(PagerdutyStream):
    tap_stream_id: ClassVar[str] = 'services'
    stream: ClassVar[str] = 'services'
    key_properties: ClassVar[str] = 'id'
    valid_replication_keys: ClassVar[List[str]] = []
    replication_method: ClassVar[str] = 'FULL_TABLE'
    valid_params: ClassVar[List[str]] = [
        'team_ids[]',
        'time_zone',
        'sort_by',
        'query',
        'include[]',
    ]
    required_params: ClassVar[List[str]] = []

    def __init__(self, config, state, **kwargs):
        super().__init__(config, state)

    def sync(self):

        with singer.metrics.job_timer(job_type=f"list_{self.tap_stream_id}"):
            with singer.metrics.record_counter(endpoint=self.tap_stream_id) as counter:
                for page in self._list_resource(url_suffix=f"/{self.tap_stream_id}", params=self.params):
                    for record in page.get(self.tap_stream_id):
                        with singer.Transformer() as transformer:
                            transformed_record = transformer.transform(data=record, schema=self.schema)
                            singer.write_record(stream_name=self.stream, time_extracted=singer.utils.now(), record=transformed_record)
                            counter.increment()


class NotificationsStream(PagerdutyStream):
    tap_stream_id: ClassVar[str] = 'notifications'
    stream: ClassVar[str] = 'notifications'
    key_properties: ClassVar[str] = 'id'
    replication_key: ClassVar[str] = 'started_at'
    valid_replication_keys: ClassVar[List[str]] = ['started_at']
    replication_method: ClassVar[str] = 'INCREMENTAL'
    valid_params: ClassVar[List[str]] = ['time_zone', 'since', 'until', 'filter', 'include']
    required_params: ClassVar[List[str]] = ['since', 'until']

    def __init__(self, config, state, **kwargs):
        super().__init__(config, state)

    def sync(self):
        current_bookmark = singer.bookmarks.get_bookmark(state=self.state,
                                                         tap_stream_id=self.tap_stream_id,
                                                         key=self.replication_key,
                                                         default=None)

        if current_bookmark is not None:
            current_bookmark_dtime = datetime.strptime(current_bookmark, '%Y-%m-%dT%H:%M:%SZ')
        else:
            current_bookmark_dtime = None

        since_dtime = datetime.strptime(self.params.get("since"), '%Y-%m-%dT%H:%M:%SZ')
        until_dtime = datetime.strptime(self.params.get("until"), '%Y-%m-%dT%H:%M:%SZ')
        request_range_limit = timedelta(days=89)

        running_bookmark_dtime = None
        with singer.metrics.job_timer(job_type=f"list_{self.tap_stream_id}"):
            with singer.metrics.record_counter(endpoint=self.tap_stream_id) as counter:
                while since_dtime < until_dtime:
                    range = {
                        "offset": 0,  # Reset the offset each time.
                        "since": datetime.strftime(since_dtime, '%Y-%m-%dT%H:%M:%SZ'),
                        "until": datetime.strftime(min(since_dtime + request_range_limit, until_dtime), '%Y-%m-%dT%H:%M:%SZ')
                    }
                    self.params.update(range)
                    for page in self._list_resource(url_suffix=f"/{self.tap_stream_id}", params=self.params):
                        for record in page.get(self.tap_stream_id):
                            record_replication_key_dtime = datetime.strptime(record.get(self.replication_key), '%Y-%m-%dT%H:%M:%SZ')
                            if (current_bookmark_dtime is None) or (record_replication_key_dtime >= current_bookmark_dtime):
                                with singer.Transformer() as transformer:
                                    transformed_record = transformer.transform(data=record, schema=self.schema)
                                    singer.write_record(stream_name=self.stream, time_extracted=singer.utils.now(), record=transformed_record)
                                    counter.increment()
                                    running_bookmark_dtime = self.update_bookmark(running_bookmark_dtime, record_replication_key_dtime)

                    since_dtime += request_range_limit

        running_bookmark_str = datetime.strftime(running_bookmark_dtime, '%Y-%m-%dT%H:%M:%SZ')
        singer.bookmarks.write_bookmark(state=self.state,
                                        tap_stream_id=self.tap_stream_id,
                                        key=self.replication_key,
                                        val=running_bookmark_str)


AVAILABLE_STREAMS = {
    IncidentsStream,
    ServicesStream,
    NotificationsStream,
    EscalationPoliciesStream
}
