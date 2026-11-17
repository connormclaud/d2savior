export UV_OFFLINE ?= 1

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
	uv run ty check d2savior tests

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

.PHONY: build-rust
build-rust:
	cargo build --manifest-path rust/Cargo.toml --release
	uv run python -c 'import shutil, sys; src, dst = {"darwin": ("lib_native.dylib", "_native.abi3.so"), "win32": ("_native.dll", "_native.pyd")}.get(sys.platform, ("lib_native.so", "_native.abi3.so")); shutil.copy2(f"rust/target/release/{src}", f"d2savior/{dst}")'

.PHONY: test-rust
test-rust:
	cargo test --manifest-path rust/Cargo.toml --no-default-features

.PHONY: clean
clean:
	@find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	@rm -rf build/ dist/ .pytest_cache/ .ruff_cache/
