import json
import inspect

import singer

from .version import __version__
from .streams import AVAILABLE_STREAMS


LOGGER = singer.get_logger()


def discover():
    LOGGER.info('Starting discovery..')
    data = {}
    data['streams'] = []
    for stream in AVAILABLE_STREAMS:
        data['streams'].append(stream())
    catalog = singer.catalog.Catalog.from_dict(data=data)
    singer.catalog.write_catalog(catalog)
    LOGGER.info('Finished discovery..')

def sync(config, catalog, state):
    LOGGER.info('Starting sync..')
    selected_streams = [catalog_entry.stream for catalog_entry in catalog.get_selected_streams(state)]

    streams_to_sync = []
    for selected_stream in selected_streams:
        for available_stream in AVAILABLE_STREAMS:
            if selected_stream == available_stream.stream:
                streams_to_sync.append(available_stream(token=config.get('token'), email=config.get('email')))

    for stream in streams_to_sync:
        stream.write_schema()
        stream.sync()






def main():
    args = singer.utils.parse_args(required_config_keys=["token", "email"])
    if args.discover:
        discover()
    else:
        sync(config=args.config, catalog=args.catalog, state=args.state)


if __name__ == "__main__":
    main()
