# TestPyPI Release Smoke Test

This directory contains a standalone smoke-test harness for validating a published SAFRS release from TestPyPI.

## Run

```bash
tmp/release_test/test_testpypi_release.sh
```

## Options

- `RELEASE_VERSION` (default: `3.2.0`)
- `PYTHON_BIN` (default: `python`)
- `WORK_DIR` (default: `tmp/release_test/work-<version>`)
- `CLEAN` (default: `1`)

Example:

```bash
RELEASE_VERSION=3.2.0 CLEAN=1 tmp/release_test/test_testpypi_release.sh
```
