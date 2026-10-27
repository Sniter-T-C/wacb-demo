.PHONY: run-demo test

PYTHON ?= python
PIP ?= $(PYTHON) -m pip

run-demo:
	$(PYTHON) main.py demo --verbose

test:
	$(PYTHON) -m pytest -q tests

install:
	$(PIP) install -r requirements.txt
