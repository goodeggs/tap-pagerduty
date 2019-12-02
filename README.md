# tap-pagerduty
[![PyPI version](https://badge.fury.io/py/tap-pagerduty.svg)](https://badge.fury.io/py/tap-pagerduty)
![PyPI - Status](https://img.shields.io/pypi/status/tap-pagerduty)
[![Build Status](https://travis-ci.com/goodeggs/tap-pagerduty.svg?branch=goodeggs/prod)](https://travis-ci.com/goodeggs/tap-pagerduty)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/tap-pagerduty)

A [Singer](https://www.singer.io/) tap for extracting data from the [Pagerduty REST API v2](https://v2.developer.pagerduty.com/docs/rest-api).

## Installation

Since package dependencies tend to conflict between various taps and targets, Singer [recommends](https://github.com/singer-io/getting-started/blob/master/docs/RUNNING_AND_DEVELOPING.md#running-singer-with-python) installing taps and targets into their own isolated virtual environments:

### Install Pagerduty Tap

```bash
$ make prod-env
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
$ ./.venvs/tap-pagerduty/bin/tap-pagerduty --config=config/pagerduty.config.json --discover
```

The tap will generate a [Catalog](https://github.com/singer-io/getting-started/blob/master/docs/DISCOVERY_MODE.md#the-catalog) to stdout. To pass the Catalog to a file instead, simply redirect it to a file:

```bash
$ ./.venvs/tap-pagerduty/bin/tap-pagerduty --config=config/pagerduty.config.json --discover > catalog.json
```

## Sync Locally

Running a tap in [Sync mode](https://github.com/singer-io/getting-started/blob/master/docs/SYNC_MODE.md#sync-mode) will extract data from the various Streams. In order to run a tap in Sync mode, pass a configuration file and catalog file:

```bash
$ ./.venvs/tap-pagerduty/bin/tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json
```

The tap will emit occasional [State messages](https://github.com/singer-io/getting-started/blob/master/docs/SPEC.md#state-message). You can persist State between runs by redirecting State to a file:

```bash
$ ./.venvs/tap-pagerduty/bin/tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json >> state.json
$ tail -1 state.json > state.json.tmp
$ mv state.json.tmp state.json
```

To pick up from where the tap left off on subsequent runs, simply supply the [State file](https://github.com/singer-io/getting-started/blob/master/docs/CONFIG_AND_STATE.md#state-file) at runtime:

```bash
$ ./.venvs/tap-pagerduty/bin/tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json --state=state.json >> state.json
$ tail -1 state.json > state.json.tmp
$ mv state.json.tmp state.json
```

## Sync to Stitch

You can also send the output of the tap to [Stitch Data](https://www.stitchdata.com/) for loading into the data warehouse. To do this, first create a JSON-formatted configuration for Stitch. This configuration file has two required fields:
1. `client_id`: The ID associated with the Stitch Data account you'll be sending data to.
2. `token` The token associated with the specific [Import API integration](https://www.stitchdata.com/docs/integrations/import-api/) within the Stitch Data account.

An example configuration file will look as follows:

```json
{
  "client_id": 1234,
  "token": "foobarfoobar"
}
```

Once the configuration file is created, simply pipe the output of the tap to the Stitch Data target and supply the target with the newly created configuration file:

```bash
$ ./.venvs/tap-pagerduty/bin/tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json --state=state.json | ./.venvs/target-stitch/bin/target-stitch --config=config/stitch.config.json >> state.json
$ tail -1 state.json > state.json.tmp
$ mv state.json.tmp state.json
```

## Contributing

### Required Tools [Pipenv] (https://docs.pipenv.org/en/latest/) and [Direnv](https://direnv.net/)

The first step to contributing is getting a copy of the source code, and setting up your environment. First, [fork `tap-pagerduty` on GitHub](https://github.com/goodeggs/tap-pagerduty/fork). Then, `cd` into the directory where you want your copy of the source code to live and clone the source code enabling direnv:

```bash
$ git clone git@github.com:YourGitHubName/tap-pagerduty.git
$ direnv allow
```

For example, to format your code using [isort](https://github.com/timothycrosley/isort) and [flake8](http://flake8.pycqa.org/en/latest/index.html) before commiting changes, run the following commands:

```bash
$ make isort
$ make flake8
```

You can also run the entire testing suite before committing using [tox](https://tox.readthedocs.io/en/latest/):

```bash
$ make lint
```

Finally, you can run your local version of the tap within the virtual environment using a command like the following:

```bash
$ tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json
```

There's also a few useful shortcuts avainable in the `Makefile` take a look!

Once you've confirmed that your changes work and the testing suite passes, feel free to put out a PR!
