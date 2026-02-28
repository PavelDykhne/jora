.PHONY: help install up down restart logs status backup update health sync-skills

COMPOSE = docker compose -f docker-compose.yml

help: ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Full install from scratch
	bash scripts/install.sh

up: ## Start all services
	$(COMPOSE) up -d

down: ## Stop all services
	$(COMPOSE) down

restart: ## Restart all
	$(COMPOSE) restart

restart-scanner: ## Restart scanner only
	$(COMPOSE) restart scanner

logs: ## Follow all logs
	$(COMPOSE) logs -f

logs-scanner: ## Follow scanner logs
	$(COMPOSE) logs -f scanner

logs-enrichment: ## Follow enrichment logs
	$(COMPOSE) logs -f enrichment

status: ## Service status + health
	$(COMPOSE) ps
	@echo "---"
	@bash scripts/healthcheck.sh

backup: ## Backup MongoDB + configs
	bash scripts/backup.sh

update: ## Pull latest and restart
	bash scripts/update.sh

health: ## Health check
	bash scripts/healthcheck.sh

mongo-shell: ## Open MongoDB shell
	docker exec -it $$($(COMPOSE) ps -q mongo) mongosh job_hunter_db

sync-skills: ## Sync skills from repo to OpenClaw workspace
	@SKILLS_SRC="$(shell git -C .. rev-parse --show-toplevel 2>/dev/null || echo ..)/skills"; \
	SKILLS_DST="$$HOME/.openclaw/workspace/skills"; \
	echo "Syncing $$SKILLS_SRC → $$SKILLS_DST"; \
	for skill in $$SKILLS_SRC/*/; do \
		name=$$(basename $$skill); \
		mkdir -p "$$SKILLS_DST/$$name"; \
		cp "$$skill/SKILL.md" "$$SKILLS_DST/$$name/SKILL.md"; \
		echo "  ✓ $$name"; \
	done; \
	echo "Done."

clean: ## Remove all data (DANGER!)
	@read -p "Delete ALL data? [y/N] " c && [ "$$c" = "y" ] && $(COMPOSE) down -v || echo "Cancelled"
