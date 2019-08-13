import os
import time
import inspect
from functools import wraps

import requests
import singer


LOGGER = singer.get_logger()


class PagerdutyStream():
    BASE_URL = "https://api.pagerduty.com"

    def __init__(self, token: str, email: str):
        self.token = token
        self.email = email


    def get(self, key):
        """Implements custom get method so that Singer can access Class attributes using dict syntax."""
        return inspect.getattr_static(self, key, default=None)


    def get_abs_path(self, path: str):
        return os.path.join(os.path.dirname(os.path.realpath(__file__)), path)


    def load_schema(self):
        """Loads a schema file for a given Pagerduty resource."""
        schema_path = self.get_abs_path("schemas")
        return singer.utils.load_json(f"{schema_path}/{self.tap_stream_id}.json")


    def write_schema(self):
        return singer.write_schema(stream_name=self.stream, schema=self.schema, key_properties=self.key_properties)


    def _construct_headers(self) -> dict:
        headers = requests.utils.default_headers()
        headers["Accept"] = "application/vnd.pagerduty+json;version=2"
        headers["User-Agent"] = "python-pagerduty-tap"
        headers["Authorization"] = f"Token token= {self.token}"
        headers["Content-Type"] = "application/json"
        headers["From"] = self.email
        return headers


    def _get(self, url_suffix: str, params: dict = None) -> dict:
        url = self.BASE_URL + url_suffix
        headers = self._construct_headers()
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 429:
            LOGGER.info("Rate limit reached. Trying again in 60 seconds.")
            time.sleep(60)
            response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


    def list_resource(self, url_suffix: str, params: dict = None):
        response = self._get(url_suffix=url_suffix, params=params)
        return PagerdutyResponse(self, url_suffix, params, response)


    def sync(self):
        with singer.metrics.job_timer(job_type=f"list_{self.tap_stream_id}") as timer:
            with singer.metrics.record_counter(endpoint=self.tap_stream_id) as counter:
                for page in self.list_resource(url_suffix=f"/{self.tap_stream_id}", params=self.params):
                    for incident in page.get(self.tap_stream_id):
                        with singer.Transformer() as transformer:
                            transformed_record = transformer.transform(data=incident, schema=self.schema)
                            singer.write_record(stream_name=self.stream, time_extracted=singer.utils.now(), record=transformed_record)
                            counter.increment()


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
    selected = True
    key_properties = 'id'
    replication_key = 'created_at'
    valid_replication_keys = ['created_at']
    replication_method = 'INCREMENTAL'

    def __init__(self, token, email, **kwargs):
        super().__init__(token, email)
        self.params = {
            "limit": kwargs.get("limit", 100),
            "offset": kwargs.get("offset", 0),
            "sort_by": kwargs.get("sort_by", "resolved_at:asc"),
            "statuses[]": kwargs.get("stauses", "resolved"),
            "since": kwargs.get("since", "2019-08-01"),
        }
        self.schema = self.load_schema()
        self.metadata = singer.metadata.get_standard_metadata(schema=self.load_schema(),
                                                              key_properties=self.key_properties,
                                                              valid_replication_keys=self.valid_replication_keys,
                                                              replication_method=self.replication_method)


AVAILABLE_STREAMS = [
    IncidentsStream
]
