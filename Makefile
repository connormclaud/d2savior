.PHONY: tests
tests:
	python -m pytest tests/ -v

.PHONY: test_bits
test_bits:
	python -m pytest tests/test_bits_stream.py -v

.PHONY: test_struct
test_struct:
	python -m pytest tests/test_d2s_struct.py -v

.PHONY: clean
clean:
	@find . -name '__pycache__' -type d -print -exec rm -rf {} \;
	@rm -rf build/ dist/ .pytest_cache/
