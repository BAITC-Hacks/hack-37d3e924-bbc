.PHONY: setup run up verify models help
PYTHON ?= python3.12
PROFILE ?= mac
MODELS ?=

help:
	@echo 'make setup PROFILE=mac|cuda|fixture — зависимости и интерфейс'
	@echo 'make up PROFILE=mac MODELS=/path/to/models — приложение и worker; Ctrl+C останавливает оба'
	@echo 'make up PROFILE=fixture — явно синтетический сценарий без моделей'
	@echo 'make verify — тесты и сборка'
	@echo 'make models — собрать и проверить веса из папки models без сети'

run: up

setup:
	$(PYTHON) scripts/manage.py setup --profile $(PROFILE)

models:
	$(PYTHON) scripts/prepare_repo_models.py

up:
	$(PYTHON) scripts/manage.py run --profile $(PROFILE) $(if $(MODELS),--models "$(MODELS)",)

verify:
	$(PYTHON) scripts/manage.py verify
