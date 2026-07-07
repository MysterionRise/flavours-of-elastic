PYTHON ?= python3
ELK_SINGLE_COMPOSE := docker/elk-single/docker-compose.yml
ENV_FILE := .env

.PHONY: setup validate-config validate-python test up-single load-small load-embeddings evaluate demo down-single

setup:
	$(PYTHON) -m pip install -r requirements-demo.txt

validate-config:
	docker compose -f docker/elk/docker-compose.yml --env-file $(ENV_FILE) config -q
	docker compose -f docker/elk-single/docker-compose.yml --env-file $(ENV_FILE) config -q
	docker compose -f docker/elk-ml/docker-compose.yml --env-file $(ENV_FILE) config -q
	docker compose -f docker/elk-9/docker-compose.yml --env-file $(ENV_FILE) config -q
	docker compose -f docker/opensearch/docker-compose.yml --env-file $(ENV_FILE) config -q
	docker compose -f docker/opensearch-3/docker-compose.yml --env-file $(ENV_FILE) config -q
	docker compose -f docker/elk-oss/docker-compose.yml --env-file $(ENV_FILE) config -q

validate-python:
	$(PYTHON) -m py_compile validate.py data/load_data.py data/index.py data/generate_descriptions.py data/generate_embeddings.py search/client.py search/evaluate.py search/embeddings.py apps/search_demo/Home.py
	$(PYTHON) -m unittest discover -s tests

test: validate-python validate-config

up-single:
	docker compose -f $(ELK_SINGLE_COMPOSE) --env-file $(ENV_FILE) up -d

load-small:
	$(PYTHON) data/load_data.py --dataset movies --size small --url http://localhost:9200 --user $${ELASTIC_USER:-elastic} --password $${ELASTIC_PASSWORD:-elastic}

load-embeddings:
	$(PYTHON) data/load_data.py --dataset movies --size small --with-embeddings --url http://localhost:9200 --user $${ELASTIC_USER:-elastic} --password $${ELASTIC_PASSWORD:-elastic}

evaluate:
	$(PYTHON) search/evaluate.py --mode bm25,dense,hybrid_rrf --queries evaluation/movie_queries.yml

demo: up-single load-small load-embeddings
	streamlit run apps/search_demo/Home.py

down-single:
	docker compose -f $(ELK_SINGLE_COMPOSE) down -v
