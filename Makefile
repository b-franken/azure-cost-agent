.PHONY: setup run chat devui frontend mcp serve test lint format typecheck check docker-build docker-run

setup:
	pip install uv
	uv sync

run:
	uv run python -m src.main

chat:
	uv run chainlit run frontend-chainlit/app.py -w

api:
	uv run uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm install && npm run dev

devui:
	uv run devui src/ --port 8080

mcp:
	uv run python -m src.mcp

serve:
	FOUNDRY_HOSTED=true uv run python -m src.main

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy src/ --strict

check: lint format typecheck test

docker-build:
	docker build --platform linux/amd64 -t azure-cost-agent .

docker-run:
	docker run -p 8000:8000 --env-file .env azure-cost-agent
