PYTHON ?= python
MAVEN ?= $(or $(MAVEN_CMD),mvn)
DOCKER_COMPOSE ?= docker compose

COMPOSE_ENV ?= .env.example
COMPOSE_FILE ?= infra/docker-compose.yml

JAVA_MIGRATION_DB_URL ?= jdbc:postgresql://localhost:5432/corp_rag_java
JAVA_DB_USER ?= corp_rag_java
JAVA_DB_PASSWORD ?= corp_rag_java_password
FLYWAY_MAVEN_PLUGIN_VERSION ?= 10.20.1

.PHONY: verify-contracts compose-up compose-ps compose-down migrate-java migrate-python

verify-contracts:
	$(PYTHON) scripts/verify-contracts.py

compose-up:
	$(DOCKER_COMPOSE) --env-file $(COMPOSE_ENV) -f $(COMPOSE_FILE) up -d --build

compose-ps:
	$(DOCKER_COMPOSE) --env-file $(COMPOSE_ENV) -f $(COMPOSE_FILE) ps

compose-down:
	$(DOCKER_COMPOSE) --env-file $(COMPOSE_ENV) -f $(COMPOSE_FILE) down

migrate-java:
	cd backend && $(MAVEN) -q -N install && $(MAVEN) -q -pl corp-rag-contracts install -DskipTests && $(MAVEN) -q -pl corp-rag-app org.flywaydb:flyway-maven-plugin:$(FLYWAY_MAVEN_PLUGIN_VERSION):migrate -Dflyway.url="$(JAVA_MIGRATION_DB_URL)" -Dflyway.user="$(JAVA_DB_USER)" -Dflyway.password="$(JAVA_DB_PASSWORD)" -Dflyway.locations="filesystem:corp-rag-app/src/main/resources/db/migration"

migrate-python:
	cd ai-service && uv run alembic upgrade head
