.PHONY: setup run up verify doctor models deploy stop logs help
PYTHON ?= python3.12
PROFILE ?= brev
MODELS ?=

help:
	@echo 'make setup PROFILE=brev|mac|windows|cuda|fixture — зависимости и интерфейс'
	@echo 'make up PROFILE=brev MODELS=/path/to/models — API и worker'
	@echo 'make doctor PROFILE=brev — проверка исходных весов'
	@echo 'make verify — тесты и production-сборка'
	@echo 'make models — собрать веса из репозитория без сети'
	@echo 'make deploy / stop / logs — Docker Compose на Brev'

run: up

setup:
	$(PYTHON) scripts/manage.py setup --profile $(PROFILE)

up:
	$(PYTHON) scripts/manage.py run --profile $(PROFILE) $(if $(MODELS),--models "$(MODELS)",)

models:
	$(PYTHON) scripts/prepare_repo_models.py

doctor:
	$(PYTHON) scripts/manage.py doctor --profile $(PROFILE) $(if $(MODELS),--models "$(MODELS)",)

verify:
	$(PYTHON) scripts/manage.py verify

deploy:
	docker compose up -d --build

stop:
	docker compose stop

logs:
	docker compose logs -f app
