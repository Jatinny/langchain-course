.PHONY: help setup dev up down build push test lint migrate logs clean kafka-setup seed

COMPOSE = docker-compose
COMPOSE_DEV = docker-compose -f docker-compose.yml -f docker-compose.dev.yml
ECR_REGISTRY ?= 123456789.dkr.ecr.ap-south-1.amazonaws.com
IMAGE_TAG ?= latest
SERVICES = api-gateway employer-discovery recruiter-intelligence outreach-engine candidate-matching crm-service analytics-service frontend

help:
	@echo "AI Recruitment Platform — Make Commands"
	@echo ""
	@echo "  make setup          — Install deps, create .env, init DB"
	@echo "  make dev            — Start services in dev mode (hot reload)"
	@echo "  make up             — Start all services (production mode)"
	@echo "  make down           — Stop all services"
	@echo "  make build          — Build all Docker images"
	@echo "  make push           — Push images to ECR"
	@echo "  make test           — Run all tests"
	@echo "  make lint           — Run linters"
	@echo "  make migrate        — Run database migrations"
	@echo "  make kafka-setup    — Create Kafka topics"
	@echo "  make seed           — Seed demo data"
	@echo "  make logs           — Tail all service logs"
	@echo "  make clean          — Remove containers and volumes"

setup:
	@echo "Setting up AI Recruitment Platform..."
	cp -n .env.example .env || true
	pip install -r common/requirements.txt
	@echo "✅ Setup complete. Edit .env with your API keys."

dev:
	$(COMPOSE_DEV) up --build

up:
	$(COMPOSE) up -d --build
	@echo "✅ Platform running. API: http://localhost:8000, Dashboard: http://localhost:3000"

down:
	$(COMPOSE) down

build:
	@for service in $(SERVICES); do \
		echo "Building $$service..."; \
		docker build -t $(ECR_REGISTRY)/$$service:$(IMAGE_TAG) -f services/$$(echo $$service | tr '-' '_')/Dockerfile . || \
		docker build -t $(ECR_REGISTRY)/$$service:$(IMAGE_TAG) ./frontend; \
	done

push: build
	aws ecr get-login-password --region ap-south-1 | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	@for service in $(SERVICES); do \
		docker push $(ECR_REGISTRY)/$$service:$(IMAGE_TAG); \
	done

test:
	pytest tests/ -v --cov=. --cov-report=term-missing

lint:
	black --check .
	isort --check-only .
	flake8 . --max-line-length=100 --exclude=migrations

migrate:
	python -m alembic upgrade head

kafka-setup:
	python scripts/kafka_setup.py

seed:
	python scripts/seed_data.py

init-db:
	python scripts/init_db.py

deploy-staging:
	kubectl apply -f infrastructure/kubernetes/namespace.yaml
	kubectl apply -f infrastructure/kubernetes/configmaps/
	kubectl apply -f infrastructure/kubernetes/services/
	kubectl apply -f infrastructure/kubernetes/deployments/
	kubectl apply -f infrastructure/kubernetes/ingress.yaml
	@echo "✅ Deployed to staging"

deploy-prod:
	@read -p "Deploy to PRODUCTION? [y/N] " confirm && [ "$$confirm" = "y" ]
	kubectl apply -f infrastructure/kubernetes/ --context=production
	@echo "✅ Deployed to production"

logs:
	$(COMPOSE) logs -f --tail=100

logs-service:
	$(COMPOSE) logs -f $(SERVICE) --tail=200

clean:
	$(COMPOSE) down -v --remove-orphans
	docker system prune -f

ps:
	$(COMPOSE) ps

restart-service:
	$(COMPOSE) restart $(SERVICE)
