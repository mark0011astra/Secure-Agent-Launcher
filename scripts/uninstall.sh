#!/usr/bin/env bash
set -euo pipefail

PURGE_CONFIG=0
if [[ "${1:-}" == "--purge-config" ]]; then
  PURGE_CONFIG=1
fi

INSTALL_ROOT="${HOME}/.agent-locker"
BIN_PATH="${HOME}/.local/bin/agent-locker"
UNINSTALL_BIN="${HOME}/.local/bin/agent-locker-uninstall"
CONFIG_PATH="${HOME}/.config/agent-locker"
STATE_PATH="${HOME}/.local/state/agent-locker"

rm -f "${BIN_PATH}"
rm -f "${UNINSTALL_BIN}"
rm -rf "${INSTALL_ROOT}"

if [[ "${PURGE_CONFIG}" -eq 1 ]]; then
  rm -rf "${CONFIG_PATH}"
  rm -rf "${STATE_PATH}"
fi

echo "Uninstalled agent-locker."
