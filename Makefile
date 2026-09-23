.PHONY: up down logs config verify clean

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

config:
	docker compose config

verify:
	docker compose config
	cd backend && pytest -q
	cd frontend && npm run build

clean:
	docker compose down -v --remove-orphans

