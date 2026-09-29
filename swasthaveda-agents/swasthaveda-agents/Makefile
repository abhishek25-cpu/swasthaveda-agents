.PHONY: install run live test lint

install:
	pip install -e ".[dev]"

run:
	swasthaveda run --cycles 1

live:
	swasthaveda run --cycles 1 --live

test:
	pytest -q

lint:
	ruff check src tests
