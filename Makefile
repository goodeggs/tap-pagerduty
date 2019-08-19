tap-discover:
	~/.venvs/tap-pagerduty/bin/tap-pagerduty --config=.config/pagerduty.config.json --discover

tap-sync-local:
	~/.venvs/tap-pagerduty/bin/tap-pagerduty --config=.config/pagerduty.config.json --catalog=catalog.json >> state.json
	tail -1 state.json > state.json.tmp
	mv state.json.tmp state.json

tap-sync-stitch:
	~/.venvs/tap-pagerduty/bin/tap-pagerduty --config=.config/pagerduty.config.json --catalog=catalog.json | ~/.venvs/target-stitch/bin/target-stitch --config=.config/stitch.config.json >> state.json
	tail -1 state.json > state.json.tmp
	mv state.json.tmp state.json
