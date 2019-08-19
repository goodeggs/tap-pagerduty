import singer

from .streams import AVAILABLE_STREAMS


LOGGER = singer.get_logger()


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
    selected_streams = [catalog_entry.stream for catalog_entry in catalog.get_selected_streams(state)]

    streams_to_sync = []
    for selected_stream in selected_streams:
        for available_stream in AVAILABLE_STREAMS:
            if selected_stream == available_stream.stream:
                streams_to_sync.append(available_stream(config=config, state=state))

    for stream in streams_to_sync:
        singer.bookmarks.set_currently_syncing(state=stream.state, tap_stream_id=stream.tap_stream_id)
        stream.write_state()
        stream.write_schema()
        stream.sync()
        stream.write_state()


def main():
    args = singer.utils.parse_args(required_config_keys=["token", "email", "since"])
    if args.discover:
        discover(config=args.config)
    else:
        sync(config=args.config, catalog=args.catalog, state=args.state)


if __name__ == "__main__":
    main()
