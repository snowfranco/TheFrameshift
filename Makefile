.PHONY: test regression update-baselines smoke

test:
	python3 -m pytest tests/ -v

regression:
	python3 -m pytest tests/regression/ -v

update-baselines:
	python3 tests/regression/generate_baselines.py

smoke:
	python3 tests/smoke.py
