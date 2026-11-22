.PHONY: install test lint run demo demo-live eval docker-build docker-up docker-down

install:
	python -m pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check src tests

run:
	uvicorn agentic_rag.api:app --host 0.0.0.0 --port 8000

demo:
	python -m agentic_rag demo

demo-live:
	python -m agentic_rag demo --live

eval:
	python -m agentic_rag eval --mode both --runs 1

docker-build:
	docker build -t agentic-rag:local .

docker-up:
	docker compose up --build

docker-down:
	docker compose down
