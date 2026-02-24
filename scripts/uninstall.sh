#!/usr/bin/env bash
set -euo pipefail

PURGE_CONFIG=0
if [[ "${1:-}" == "--purge-config" ]]; then
  PURGE_CONFIG=1
fi

INSTALL_ROOT="${HOME}/.secure-agent-locker"
OLD_INSTALL_ROOT="${HOME}/.agent-locker"
BIN_PATH="${HOME}/.local/bin/secure-agent-locker"
OLD_BIN_PATH="${HOME}/.local/bin/agent-locker"
UNINSTALL_BIN="${HOME}/.local/bin/secure-agent-locker-uninstall"
OLD_UNINSTALL_BIN="${HOME}/.local/bin/agent-locker-uninstall"
CONFIG_PATH="${HOME}/.config/secure-agent-locker"
OLD_CONFIG_PATH="${HOME}/.config/agent-locker"
STATE_PATH="${HOME}/.local/state/secure-agent-locker"
OLD_STATE_PATH="${HOME}/.local/state/agent-locker"

rm -f "${BIN_PATH}"
rm -f "${OLD_BIN_PATH}"
rm -f "${UNINSTALL_BIN}"
rm -f "${OLD_UNINSTALL_BIN}"
rm -rf "${INSTALL_ROOT}"
rm -rf "${OLD_INSTALL_ROOT}"

if [[ "${PURGE_CONFIG}" -eq 1 ]]; then
  rm -rf "${CONFIG_PATH}"
  rm -rf "${OLD_CONFIG_PATH}"
  rm -rf "${STATE_PATH}"
  rm -rf "${OLD_STATE_PATH}"
fi

echo "Uninstalled secure-agent-locker."
