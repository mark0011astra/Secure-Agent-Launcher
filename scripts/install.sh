#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_ROOT="${HOME}/.agent-locker"
VENV_DIR="${INSTALL_ROOT}/venv"
BIN_DIR="${HOME}/.local/bin"
TARGET_BIN="${BIN_DIR}/agent-locker"
UNINSTALL_SCRIPT="${INSTALL_ROOT}/uninstall.sh"
UNINSTALL_BIN="${BIN_DIR}/agent-locker-uninstall"
SOURCE_UNINSTALL="${ROOT_DIR}/scripts/uninstall.sh"

mkdir -p "${INSTALL_ROOT}"
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install "${ROOT_DIR}"

mkdir -p "${BIN_DIR}"
ln -sf "${VENV_DIR}/bin/agent-locker" "${TARGET_BIN}"

cp "${SOURCE_UNINSTALL}" "${UNINSTALL_SCRIPT}"
chmod +x "${UNINSTALL_SCRIPT}"
ln -sf "${UNINSTALL_SCRIPT}" "${UNINSTALL_BIN}"

"${TARGET_BIN}" init

echo "Installed agent-locker at ${TARGET_BIN}"
echo "Uninstall with: ${UNINSTALL_BIN} [--purge-config]"
echo "If needed, add ${BIN_DIR} to your PATH."
