# tap-pagerduty
A [Singer](https://www.singer.io/) tap for extracting data from the [Pagerduty REST API v2](https://v2.developer.pagerduty.com/docs/rest-api).

## Installation

Since package dependencies tend to conflict between various taps and targets, Singer [recommends](https://github.com/singer-io/getting-started/blob/master/docs/RUNNING_AND_DEVELOPING.md#running-singer-with-python) installing taps and targets into their own isolated virtual environments:

### Install Pagerduty Tap

If you haven't already, clone the `tap-pagerduty` repo:

```bash
git clone git@github.com:goodeggs/tap-pagerduty.git
```

Then install the tap:

```bash
cd tap-pagerduty
python3 -m venv ~/.venvs/tap-pagerduty
source ~/.venvs/tap-pagerduty/bin/activate
pip3 install .
deactivate
```

### Install Singer Target

```bash
python3 -m venv ~/.venvs/target-stitch
source ~/.venvs/target-stitch/bin/activate
pip3 install target-stitch
deactivate
```

## Configuration

The tap accepts a JSON-formatted configuration file as arguments. This configuration file has three required fields:

1. `token`: A valid [Pagerduty REST API key](https://support.pagerduty.com/docs/generating-api-keys).
2. `email`: A valid email address to be inserted into the `From` header of the [HTTP Request headers](https://v2.developer.pagerduty.com/docs/rest-api#http-request-headers)
3. `since` A date to be used as the default `since` parameter for all API endpoints that support that parameter.

An bare-bones Pagerduty confirguration may file may look like the following:

```json
{
  "token": "foobarfoobar",
  "email": "foo.bar@gmail.com",
  "since": "2019-01-01"
}
```

Additionally, you may specify more granular configurations for individual streams. Each key under a stream should represent a valid API request parameter for that endpoint. A more fleshed-out configuration file may look similar to the following:

```json
{
  "token": "foobarfoobar",
  "email": "foo.bar@gmail.com",
  "since": "2019-08-01",
  "streams": {
    "incidents": {
      "since": "last_status_change_at>=2019-08-01",
      "sort_by": "created_at:asc"
    }
  }
}
```

## Streams

The current version of the tap syncs three distinct [Streams](https://github.com/singer-io/getting-started/blob/master/docs/SYNC_MODE.md#streams):
1. `Incidents`: ([Endpoint](https://api-reference.pagerduty.com/#!/Incidents/get_incidents), [Schema](https://github.com/goodeggs/tap-pagerduty/blob/master/tap_pagerduty/schemas/incidents.json))
2. `Notifications`: ([Endpoint](https://api-reference.pagerduty.com/#!/Notifications/get_notifications), [Schema](https://github.com/goodeggs/tap-pagerduty/blob/master/tap_pagerduty/schemas/notifications.json))
3. `Services`: ([Endpoint](https://api-reference.pagerduty.com/#!/Services/get_services), [Schema](https://github.com/goodeggs/tap-pagerduty/blob/master/tap_pagerduty/schemas/services.json))

## Discovery

Singer taps describe the data that a stream supports via a [Discovery](https://github.com/singer-io/getting-started/blob/master/docs/DISCOVERY_MODE.md#discovery-mode) process. You can run the Pagerduty tap in Discovery mode by passing the `--discover` flag at runtime:

```bash
~/.venvs/tap-pagerduty/bin/tap-pagerduty --config=config/pagerduty.config.json --discover
```

The tap will generate a [Catalog](https://github.com/singer-io/getting-started/blob/master/docs/DISCOVERY_MODE.md#the-catalog) to stdout. To pass the Catalog to a file instead, simply redirect it to a file:

```bash
~/.venvs/tap-pagerduty/bin/tap-pagerduty --config=config/pagerduty.config.json --discover > catalog.json
```

## Sync Locally

Running a tap in [Sync mode](https://github.com/singer-io/getting-started/blob/master/docs/SYNC_MODE.md#sync-mode) will extract data from the various Streams. In order to run a tap in Sync mode, pass a configuration file and catalog file:

```bash
~/.venvs/tap-pagerduty/bin/tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json
```

The tap will emit occasional [State messages](https://github.com/singer-io/getting-started/blob/master/docs/SPEC.md#state-message). You can persist State between runs by redirecting State to a file:

```bash
~/.venvs/tap-pagerduty/bin/tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json >> state.json
tail -1 state.json > state.json.tmp
mv state.json.tmp state.json
```

To pick up from where the tap left off on subsequent runs, simply supply the [State file](https://github.com/singer-io/getting-started/blob/master/docs/CONFIG_AND_STATE.md#state-file) at runtime:

```bash
~/.venvs/tap-pagerduty/bin/tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json --state=state.json >> state.json
```

## Sync to Stitch

```bash
make tap-sync-stitch
```
