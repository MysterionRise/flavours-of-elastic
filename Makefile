# flavours-of-elastic task runner (GNU make 3.81+). Run `make` for the list of targets.
# Windows users without make: every target maps to a plain `python ...` / `docker compose ...` command.

PYTHON     ?= python3
VENV       ?= .venv
PY         := $(VENV)/bin/python
ENV_FILE   ?= $(if $(wildcard .env),.env,.env.example)
STACK      ?= elk-single
STACKS     := $(notdir $(patsubst %/,%,$(dir $(wildcard docker/*/docker-compose.yml))))
# hybrid_rrf uses the rrf retriever on a trial licence and client-side fusion elsewhere.
EVAL_MODES ?= bm25,dense,hybrid_rrf

COMPOSE     = docker compose -f docker/$(1)/docker-compose.yml --env-file $(ENV_FILE)
check_stack = $(if $(filter $(1),$(STACKS)),,$(error Unknown stack '$(1)'. Known: $(STACKS)))
# Slides are rendered with the Marp CLI Docker image (no local Node.js needed).
MARP_IMAGE ?= marpteam/marp-cli:v4.5.1
MARP       ?= docker run --rm --init -v "$(CURDIR)":/home/marp/app -e MARP_USER="$$(id -u):$$(id -g)" \
	-e LANG=C.UTF-8 $(MARP_IMAGE)
DECKS      := $(sort $(wildcard course/day*/day*-slides.md course/day*/day*-exercises.md))
SLIDES_OUT ?= dist/slides

# Runs a command against the already running $(STACK) with its connection details exported.
ATTACH      = $(PY) -m scripts.with_stack --attach $(STACK) --env-file $(ENV_FILE) --
# $(1): extra data/load_data.py flags (the connection comes from the exported environment).
load_movies = $(ATTACH) $(PY) data/load_data.py --dataset movies $(1)

.DEFAULT_GOAL := help
.NOTPARALLEL:
.PHONY: help setup lint fmt test validate validate-all up down load-small load-embeddings evaluate demo \
	up-single down-single reset-single slides slides-serve slides-clean course-test

help: ## List the targets
	@grep -hE '^[a-zA-Z0-9_%-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  %-18s %s\n", $$1, $$2}'
	@echo
	@echo "  stacks: $(STACKS)"
	@echo "  current: STACK=$(STACK) ENV_FILE=$(ENV_FILE)"

$(VENV)/.installed: requirements.txt requirements-dev.txt
	@$(PYTHON) -c 'import sys; sys.exit(sys.version_info < (3, 11))' || { echo "Python 3.11+ is required"; exit 1; }
	@test -x $(PY) || $(PYTHON) -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements-dev.txt
	@touch $@

setup: $(VENV)/.installed ## Create .venv (PEP 668-safe), install dependencies and the git hooks
	$(VENV)/bin/pre-commit install

lint: $(VENV)/.installed ## Run every pre-commit hook on every file (same as CI)
	$(VENV)/bin/pre-commit run --all-files

fmt: $(VENV)/.installed ## Auto-fix and format Python with ruff
	-$(VENV)/bin/pre-commit run ruff-check --all-files
	$(VENV)/bin/pre-commit run ruff-format --all-files

test: $(VENV)/.installed ## Unit tests + compose policy + doc version check (no running stack needed)
	$(PY) -m unittest discover -s tests
	$(PY) -m scripts.check_compose --env-file $(ENV_FILE)
	$(PY) -m scripts.check_doc_versions

validate: $(VENV)/.installed ## Validate STACK in an isolated project (your own stack and data are untouched)
	$(PY) validate.py --stack $(STACK) --env-file $(ENV_FILE)

validate-all: $(VENV)/.installed ## Validate every stack, one after another (~20 min)
	$(PY) validate.py --stack all --env-file $(ENV_FILE)

up-%: ## Start docker/<stack> and wait until it is healthy (e.g. make up-elk-9)
	$(call check_stack,$*)$(call COMPOSE,$*) up -d --wait --wait-timeout 600

down-%: ## Stop docker/<stack>, keeping its data
	$(call check_stack,$*)$(call COMPOSE,$*) down

reset-%: ## Stop docker/<stack> and DELETE its data volumes
	$(call check_stack,$*)@echo "Deleting all data of $* in 5s (Ctrl-C to abort)"; sleep 5
	$(call COMPOSE,$*) down -v

logs-%: ## Follow the logs of docker/<stack>
	$(call check_stack,$*)$(call COMPOSE,$*) logs -f --tail=200

ps-%: ## Show the containers of docker/<stack>
	$(call check_stack,$*)$(call COMPOSE,$*) ps -a

up: up-$(STACK) ## Start STACK (default elk-single)
down: down-$(STACK) ## Stop STACK, keeping its data

# Backwards-compatible names.
up-single: up-elk-single
down-single: down-elk-single
reset-single: reset-elk-single

load-small: $(VENV)/.installed ## Load the small movies dataset into the running STACK
	$(call load_movies,--size small)

load-embeddings: $(VENV)/.installed ## Load the small movies dataset with embeddings into the running STACK
	$(call load_movies,--size small --embeddings hash)

evaluate: $(VENV)/.installed ## Run the search evaluation against the running STACK (EVAL_MODES)
	$(ATTACH) $(PY) search/evaluate.py --mode $(EVAL_MODES) --queries evaluation/movie_queries.yml

demo: up-$(STACK) load-small load-embeddings evaluate ## Start STACK, load data, evaluate, then open the Streamlit demo
	$(PY) -m pip install -q -r requirements-demo.txt
	$(ATTACH) $(PY) -m streamlit run apps/search_demo/Home.py

DAY ?= 1
course-test: $(VENV)/.installed ## Run DAY's course snippets on a fresh STACK (e.g. make course-test DAY=2 STACK=elk-9)
	$(PY) -m scripts.with_stack $(STACK) --env-file $(ENV_FILE) -- $(PY) -m tests.course.run --day $(DAY)

slides: ## Render every slide and exercise deck to PDF in dist/slides (needs Docker)
	@mkdir -p $(SLIDES_OUT)
	@for deck in $(DECKS); do \
		name=$$(basename "$$deck" .md); \
		echo "$$deck -> $(SLIDES_OUT)/$$name.pdf"; \
		$(MARP) --config-file .marprc.yml --pdf "$$deck" -o "$(SLIDES_OUT)/$$name.pdf" >/dev/null || exit 1; \
	done

slides-serve: ## Live preview of the decks on http://localhost:8080 (needs Docker)
	docker run --rm --init -it -v "$(CURDIR)":/home/marp/app -e MARP_USER="$$(id -u):$$(id -g)" \
		-p 8080:8080 -p 37717:37717 $(MARP_IMAGE) --config-file .marprc.yml --server course

slides-clean: ## Remove rendered slides
	rm -rf $(SLIDES_OUT)
