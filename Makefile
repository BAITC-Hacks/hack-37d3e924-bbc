PYTHON ?= python
.PHONY: help run up verify

help:
	@echo "make run: local Streamlit prototype; make verify: AI and prototype tests"
	@echo "Set PYTHON to the prepared virtual environment executable. See README.md."

run:
	$(PYTHON) -m streamlit run prototypes/meeting-mvp/app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false

up: run

verify:
	$(PYTHON) -m pytest --import-mode=importlib ai/tests prototypes/meeting-mvp/tests -q

