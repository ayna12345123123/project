.PHONY: install venv ui cli test clean

VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
STREAMLIT := $(VENV)/bin/streamlit
PYTEST := $(VENV)/bin/pytest

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

ui: install
	$(STREAMLIT) run ui_app.py --server.headless=true --server.port=8501

cli: install
	@echo 'Usage: make cli IDEA="your project idea here"'
	@if [ -z "$(IDEA)" ]; then exit 1; fi
	$(PY) -m orgos "$(IDEA)"

test:
	PYTHONPATH=. $(PYTEST) tests/ -v

clean:
	rm -rf $(VENV) __pycache__ */__pycache__ */*/__pycache__ .pytest_cache *.egg-info
