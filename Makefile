isort:
	isort --recursive

flake8:
	flake8 . --ignore=E501 --count --statistics

run-tap:
	@echo "Running Pagerduty tap.."
	@tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json

run-tap-to-stitch:
	@echo "Running Pagerduty tap with Stitch Data target.."
	@tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json | ~/.venvs/target-stitch/bin/target-stitch --config=config/stitch.config.json >> state.json
	@echo "Persisting state.."
	@tail -1 state.json > state.tmp.json
	@mv state.tmp.json state.json

run-tap-to-stitch-with-state:
	@echo "Running Pagerduty tap with Stitch Data target.."
	@echo "State file provided. Picking up from where we left off.."
	@tap-pagerduty --config=config/pagerduty.config.json --catalog=catalog.json --state=state.json | ~/.venvs/target-stitch/bin/target-stitch --config=config/stitch.config.json >> state.json
	@echo "Persisting state.."
	@tail -1 state.json > state.tmp.json
	@mv state.tmp.json state.json
