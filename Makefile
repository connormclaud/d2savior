# Makefile for Diablo II Character Editor

# 运行所有测试
.PHONY: tests
tests:
	python -m pytest tests/ -v

# 运行特定测试文件
.PHONY: test_bits
test_bits:
	python -m pytest tests/test_bits_stream.py -v

# 运行角色结构测试
.PHONY: test_struct
test_struct:
	python -m pytest tests/test_d2s_struct.py -v

# 清理临时文件
.PHONY: clean
clean:
	@find . -name '__pycache__' -type d -print -exec rm -rf {} \;
