.PHONY: install test lint clean

install:
	pip install -r requirements.txt

test:
	python -m pytest

lint:
	ruff check .

clean:
	rm -rf __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
