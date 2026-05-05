# Makefile for Diablo II Character Editor

VERSION := 1.0.0
SEVENZIP := "C:\Program Files\7-Zip\7z.exe"
SFX_MODULE := "C:\Program Files\7-Zip\7z.sfx"

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
	@rm -rf build/ dist/

.PHONY: build
build:
	pyinstaller d2savior.spec --noconfirm

.PHONY: installer
installer: build
	@rm -rf dist/sfx_temp
	@mkdir -p dist/sfx_temp
	$(SEVENZIP) a -mx9 dist/sfx_temp/archive.7z ./dist/D2Savior/*
	powershell -Command "Get-Content $(SFX_MODULE),'sfx_config.txt','dist\sfx_temp\archive.7z' -Encoding Byte -ReadCount 0 | Set-Content 'dist\D2Savior_$(VERSION)_Setup.exe' -Encoding Byte"
	@rm -rf dist/sfx_temp
	@echo "Installer created: dist/D2Savior_$(VERSION)_Setup.exe"
