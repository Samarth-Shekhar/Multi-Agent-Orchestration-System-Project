.PHONY: install test lint demo run docker-build docker-run benchmark clean

install:
	python -m pip install -e ".[dev]"

test:
	python -m pytest -v --cov=src/gitpilot

lint:
	python -m ruff check src tests

demo:
	python -m gitpilot.demo

run:
	python -m gitpilot.main

docker-build:
	docker build -t gitpilot:latest .

docker-run:
	docker run -p 8000:8000 --env-file .env gitpilot:latest

benchmark:
	python scripts/benchmark.py

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache/ .ruff_cache/ htmlcov/ .coverage
