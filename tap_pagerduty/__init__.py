import os

import rollbar
import singer

from .streams import AVAILABLE_STREAMS

LOGGER = singer.get_logger()


if "ROLLBAR_ACCESS_TOKEN" in os.environ:
    ROLLBAR_ACCESS_TOKEN = os.environ["ROLLBAR_ACCESS_TOKEN"]
    ROLLBAR_ENVIRONMENT = os.environ["ROLLBAR_ENVIRONMENT"]
    rollbar.init(ROLLBAR_ACCESS_TOKEN, ROLLBAR_ENVIRONMENT)


def discover(config, state={}):
    LOGGER.info('Starting discovery..')
    data = {}
    data['streams'] = []
    for available_stream in AVAILABLE_STREAMS:
        data['streams'].append(available_stream(config=config, state=state))
    catalog = singer.catalog.Catalog.from_dict(data=data)
    singer.catalog.write_catalog(catalog)
    LOGGER.info('Finished discovery..')


def sync(config, catalog, state={}):
    LOGGER.info('Starting sync..')
    selected_streams = {catalog_entry.stream for catalog_entry in catalog.get_selected_streams(state)}

    streams_to_sync = set()
    for available_stream in AVAILABLE_STREAMS:
        if available_stream.stream in selected_streams:
            streams_to_sync.add(available_stream(config=config, state=state))

    for stream in streams_to_sync:
        singer.bookmarks.set_currently_syncing(state=stream.state, tap_stream_id=stream.tap_stream_id)
        stream.write_state()
        stream.write_schema()
        stream.sync()
        singer.bookmarks.set_currently_syncing(state=stream.state, tap_stream_id=None)
        stream.write_state()


def main():
    args = singer.utils.parse_args(required_config_keys=["token", "email", "since"])
    if args.discover:
        try:
            discover(config=args.config)
        except:
            LOGGER.exception('Caught exception during Discovery..')
            rollbar.report_exc_info()
    else:
        try:
            sync(config=args.config, catalog=args.catalog, state=args.state)
        except:
            LOGGER.exception('Caught exception during Sync..')
            rollbar.report_exc_info()


if __name__ == "__main__":
    main()
