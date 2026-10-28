VENV ?= .venv
PY := $(VENV)/bin/python

.PHONY: setup run test

$(PY):
	python3 -m venv $(VENV)
	$(PY) -m pip install -q -r requirements.txt

setup: $(PY)

# One command to start: creates the venv on first use, then serves on http://localhost:8000
run: $(PY)
	$(PY) -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

test: $(PY)
	$(PY) -m pytest -q
