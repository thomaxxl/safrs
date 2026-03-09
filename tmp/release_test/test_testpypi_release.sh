#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RELEASE_VERSION="${RELEASE_VERSION:-3.2.0}"
PYTHON_BIN="${PYTHON_BIN:-python}"
TEST_PYPI_URL="${TEST_PYPI_URL:-https://test.pypi.org/simple/}"
PYPI_URL="${PYPI_URL:-https://pypi.org/simple/}"
WORK_DIR="${WORK_DIR:-${SCRIPT_DIR}/work-${RELEASE_VERSION}}"
VENV_DIR="${WORK_DIR}/venv"
TARGET_SITE_DIR="${WORK_DIR}/site-packages"
SMOKE_SCRIPT="${SCRIPT_DIR}/smoke_test_release.py"
CLEAN="${CLEAN:-1}"

if [[ "${CLEAN}" == "1" ]]; then
  rm -rf "${WORK_DIR}"
fi

mkdir -p "${WORK_DIR}"

RUN_PYTHON="${PYTHON_BIN}"
RUN_ENV_PREFIX=()

echo "[release-test] Creating venv: ${VENV_DIR}"
if "${PYTHON_BIN}" -m venv "${VENV_DIR}"; then
  RUN_PYTHON="${VENV_DIR}/bin/python"
  echo "[release-test] Upgrading installer tooling"
  "${RUN_PYTHON}" -m pip install --upgrade pip setuptools wheel

  echo "[release-test] Installing safrs==${RELEASE_VERSION} from TestPyPI"
  "${RUN_PYTHON}" -m pip install \
    --index-url "${TEST_PYPI_URL}" \
    --extra-index-url "${PYPI_URL}" \
    "safrs==${RELEASE_VERSION}"

  echo "[release-test] Installed package metadata"
  "${RUN_PYTHON}" -m pip show safrs
else
  echo "[release-test] WARNING: python -m venv unavailable for ${PYTHON_BIN}; using --target install fallback" >&2
  rm -rf "${TARGET_SITE_DIR}"
  mkdir -p "${TARGET_SITE_DIR}"

  echo "[release-test] Installing safrs==${RELEASE_VERSION} into ${TARGET_SITE_DIR}"
  "${RUN_PYTHON}" -m pip install --upgrade \
    --target "${TARGET_SITE_DIR}" \
    --index-url "${TEST_PYPI_URL}" \
    --extra-index-url "${PYPI_URL}" \
    "safrs==${RELEASE_VERSION}"

  RUN_ENV_PREFIX=("PYTHONPATH=${TARGET_SITE_DIR}${PYTHONPATH:+:${PYTHONPATH}}")
fi

echo "[release-test] Running smoke checks"
env "${RUN_ENV_PREFIX[@]}" SAFRS_EXPECTED_VERSION="${RELEASE_VERSION}" \
  "${RUN_PYTHON}" "${SMOKE_SCRIPT}"

echo "[release-test] SUCCESS: safrs ${RELEASE_VERSION} passed smoke checks"
