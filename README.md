# tap-pagerduty
A singer.io tap for the Pagerduty API

## Install

```bash
cd tap-pagerduty
python3 -m venv ~/.venvs/tap-pagerduty
source ~/.venvs/tap-pagerduty/bin/activate
pip3 install .
deactivate

python3 -m venv ~/.venvs/target-stitch
source ~/.venvs/target-stitch/bin/activate
pip3 install target-stitch
deactivate
```

## Configuration

The tap accepts a JSON-formatted configuration file as an argument. This confiruation file houses things such as API tokens, user agents, and Stream-specific parameter information. Example:

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

## Run Locally

```bash
make tap-sync-local
```

## Run with Stitch Target

```bash
make tap-sync-stitch
```
