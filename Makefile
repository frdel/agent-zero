## CONTAINER
.PHONY: up down build shell shell-root logs

build:
	@docker compose build \
		--build-arg UID=$(shell id -u) \
		--build-arg GID=$(shell id -g) \
		--build-arg USER=$(shell id -un) \
		--build-arg GROUP=$(shell id -gn)
up:
	@docker compose up -d --remove-orphans --no-build
down:
	@docker compose down -v
shell:
	@docker compose exec app /bin/bash
shell-root:
	@docker compose exec -u 0:0 app /bin/bash
logs:
	@docker compose logs -f

## APP
.PHONY: python pip install start

python:
	@docker compose exec app python $(filter-out $@,$(MAKECMDGOALS))
pip:
	@docker compose exec app pip $(filter-out $@,$(MAKECMDGOALS))
install:
	@docker compose exec app pip install -r requirements.txt
start:
	@docker compose exec app python main.py

%:
	@:
