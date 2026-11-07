.PHONY: format
format:
	uv run ruff format .
	uv run ruff check --fix .

.PHONY: lint
lint:
	uv run ruff format --check .
	uv run ruff check .

.PHONY: typecheck
typecheck:
	uv run ty check

.PHONY: check
check: lint typecheck tests

.PHONY: tests
tests:
	uv run pytest tests/ -v

.PHONY: test_bits
test_bits:
	uv run pytest tests/test_bits_stream.py -v

.PHONY: test_struct
test_struct:
	uv run pytest tests/test_d2s_struct.py -v

.PHONY: clean
clean:
	@find . -name '__pycache__' -type d -print -exec rm -rf {} \;
	@rm -rf build/ dist/ .pytest_cache/ .ruff_cache/
