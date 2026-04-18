# ─── Bale Registration Bot — Makefile ─────────────────────────────────────────
# Usage: make <target>

.PHONY: help install migrate seed run-web run-bot test lint shell \
        docker-up docker-down docker-logs docker-rebuild export-csv

# ── Variables ──────────────────────────────────────────────────────────────────
PYTHON   = python
MANAGE   = $(PYTHON) manage.py
DC       = docker compose
DC_WEB   = $(DC) exec web
DC_BOT   = $(DC) exec bot

# ── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Bale Registration Bot — available targets"
	@echo "  ─────────────────────────────────────────"
	@echo "  make install        Install Python dependencies"
	@echo "  make migrate        Run Django migrations"
	@echo "  make seed           Seed sample questions & final message"
	@echo "  make run-web        Start Django admin (local)"
	@echo "  make run-bot        Start Bale bot (local)"
	@echo "  make test           Run full test suite"
	@echo "  make lint           Run flake8 linter"
	@echo "  make shell          Open Django shell"
	@echo "  make export-csv     Export registrations to CSV"
	@echo ""
	@echo "  Docker targets:"
	@echo "  make docker-up      Start all services (detached)"
	@echo "  make docker-down    Stop all services"
	@echo "  make docker-logs    Follow all logs"
	@echo "  make docker-rebuild Rebuild images and restart"
	@echo ""

# ── Local dev ──────────────────────────────────────────────────────────────────
install:
	pip install -r requirements.txt

migrate:
	$(MANAGE) migrate

seed:
	$(MANAGE) seed_sample_data

run-web:
	$(MANAGE) runserver 0.0.0.0:8000

run-bot:
	$(MANAGE) runbot

test:
	$(MANAGE) test tests --verbosity=2 --settings=config.test_settings

lint:
	@flake8 apps/ --max-line-length=110 --exclude=migrations || true

shell:
	$(MANAGE) shell

export-csv:
	$(MANAGE) export_registrations

superuser:
	$(MANAGE) createsuperuser

# ── Docker ─────────────────────────────────────────────────────────────────────
docker-up:
	$(DC) up -d --build

docker-down:
	$(DC) down

docker-logs:
	$(DC) logs -f

docker-rebuild:
	$(DC) down
	$(DC) build --no-cache
	$(DC) up -d

docker-seed:
	$(DC_BOT) python manage.py seed_sample_data

docker-migrate:
	$(DC_WEB) python manage.py migrate

docker-shell:
	$(DC_WEB) python manage.py shell

docker-export:
	$(DC_BOT) python manage.py export_registrations
