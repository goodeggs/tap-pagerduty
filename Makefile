.PHONY: discover
SHELL := /bin/bash

lint:
	@tox

run-tap:
	@echo "Running Pagerduty tap.."
	@tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json

run-tap-to-stitch:
	@echo "Running Pagerduty tap with Stitch Data target.."
	@tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json | ./.venvs/target-stitch/bin/target-stitch --config=config/stitch.config.json >> state.json
	@echo "Persisting state.."
	@tail -1 state.json > state.tmp.json
	@mv state.tmp.json state.json

run-tap-to-stitch-with-state:
	@echo "Running Pagerduty tap with Stitch Data target.."
	@echo "State file provided. Picking up from where we left off.."
	@tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json --state=state.json | ./.venvs/target-stitch/bin/target-stitch --config=config/stitch.config.json >> state.json
	@echo "Persisting state.."
	@tail -1 state.json > state.tmp.json
	@mv state.tmp.json state.json

discover:
	@tap-pagerduty --config=config/pagerduty.config.json --discover > catalog.json

basic-sync:
	@tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json

sync:
	bash -c ' if [ -f state.json ]; then \
		tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json >> state.json && tail -1 state.json > state.json.tmp && mv state.json.tmp state.json; \
		else; \
		tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json --state=state.json >> state.json && tail -1 state.json > state.json.tmp && mv state.json.tmp state.json; \
		fi'

develop:
	pipenv install --three -dev

prod-env:
	@python3 -m venv ./.venvs/tap-pagerduty
	@source ./.venvs/tap-pagerduty/bin/activate && \
	pip3 install tap-pagerduty && \
	deactivate
	@python3 -m venv ./.venvs/target-stitch
	@source ./.venvs/target-stitch/bin/activate && \
	pip3 install target-stitch && \
	deactivate

clean:
	rm -fR ./.venvs
	rm -fR ./.venv
	rm -f state.json
