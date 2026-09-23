.PHONY: setup run up verify prototype help
PYTHON ?= python3.12
PROFILE ?= mac
MODELS ?=

help:
	@echo 'make setup PROFILE=mac|cuda|fixture — зависимости и интерфейс'
	@echo 'make up PROFILE=mac MODELS=/path/to/models — приложение и worker; Ctrl+C останавливает оба'
	@echo 'make up PROFILE=fixture — явно синтетический сценарий без моделей'
	@echo 'make verify — тесты и сборка; make prototype — прежний Streamlit'

run: up

setup:
	$(PYTHON) scripts/manage.py setup --profile $(PROFILE)

up:
	$(PYTHON) scripts/manage.py run --profile $(PROFILE) $(if $(MODELS),--models "$(MODELS)",)

verify:
	$(PYTHON) scripts/manage.py verify

prototype:
	$(PYTHON) -m streamlit run prototypes/meeting-mvp/app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
