#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Install secure-agent-locker macOS binary from GitHub Releases.

Usage:
  ./scripts/install-from-github.sh --repo OWNER/REPO [--tag TAG]

Environment variables:
  AGENT_LOCKER_REPO  GitHub repository in OWNER/REPO format
  AGENT_LOCKER_TAG   Release tag (default: latest)
EOF
}

REPO="${AGENT_LOCKER_REPO:-}"
TAG="${AGENT_LOCKER_TAG:-latest}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO="${2:-}"
      shift 2
      ;;
    --tag)
      TAG="${2:-}"
      shift 2
      ;;
    --ref)
      TAG="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${REPO}" ]]; then
  echo "--repo is required." >&2
  usage >&2
  exit 2
fi
if [[ ! "${REPO}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "Invalid --repo format. Use OWNER/REPO." >&2
  exit 2
fi
if [[ ! "${TAG}" =~ ^[A-Za-z0-9._/-]+$ ]]; then
  echo "Invalid --tag format." >&2
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required." >&2
  exit 1
fi

if ! command -v tar >/dev/null 2>&1; then
  echo "tar is required." >&2
  exit 1
fi

if ! command -v uname >/dev/null 2>&1; then
  echo "uname is required." >&2
  exit 1
fi

ARCH_RAW="$(uname -m)"
ASSET_ARCH=""
case "${ARCH_RAW}" in
  arm64|aarch64)
    ASSET_ARCH="arm64"
    ;;
  x86_64)
    ASSET_ARCH="x64"
    ;;
  *)
    echo "Unsupported architecture: ${ARCH_RAW}" >&2
    exit 1
    ;;
esac

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "${WORK_DIR}"' EXIT

API_BASE="https://api.github.com/repos/${REPO}/releases"
if [[ "${TAG}" == "latest" ]]; then
  RELEASE_URL="${API_BASE}/latest"
else
  RELEASE_URL="${API_BASE}/tags/${TAG}"
fi

RELEASE_JSON="${WORK_DIR}/release.json"
if ! curl -fsSL -H "Accept: application/vnd.github+json" "${RELEASE_URL}" -o "${RELEASE_JSON}"; then
  echo "Failed to fetch release metadata from ${RELEASE_URL}" >&2
  exit 1
fi

ASSET_URL="$(
  grep -Eo "https://[^\"]*secure-agent-locker-macos-${ASSET_ARCH}\\.tar\\.gz" "${RELEASE_JSON}" | head -n 1 || true
)"
if [[ -z "${ASSET_URL}" ]]; then
  echo "Release asset secure-agent-locker-macos-${ASSET_ARCH}.tar.gz was not found." >&2
  exit 1
fi

ARCHIVE_PATH="${WORK_DIR}/secure-agent-locker.tar.gz"
curl -fL "${ASSET_URL}" -o "${ARCHIVE_PATH}"

EXTRACT_DIR="${WORK_DIR}/extract"
mkdir -p "${EXTRACT_DIR}"
tar -xzf "${ARCHIVE_PATH}" -C "${EXTRACT_DIR}"

TARGET_PAYLOAD="${EXTRACT_DIR}/secure-agent-locker"
TARGET_UNINSTALL_PAYLOAD="${EXTRACT_DIR}/secure-agent-locker-uninstall"
if [[ ! -f "${TARGET_PAYLOAD}" || ! -f "${TARGET_UNINSTALL_PAYLOAD}" ]]; then
  echo "Invalid release archive format." >&2
  exit 1
fi

INSTALL_ROOT="${HOME}/.secure-agent-locker"
BIN_DIR="${HOME}/.local/bin"
TARGET_BIN="${BIN_DIR}/secure-agent-locker"
UNINSTALL_SCRIPT="${INSTALL_ROOT}/uninstall.sh"
UNINSTALL_BIN="${BIN_DIR}/secure-agent-locker-uninstall"

mkdir -p "${INSTALL_ROOT}" "${BIN_DIR}"
install -m 0755 "${TARGET_PAYLOAD}" "${TARGET_BIN}"
install -m 0755 "${TARGET_UNINSTALL_PAYLOAD}" "${UNINSTALL_SCRIPT}"
ln -sf "${UNINSTALL_SCRIPT}" "${UNINSTALL_BIN}"

"${TARGET_BIN}" init

echo "Installed secure-agent-locker at ${TARGET_BIN}"
echo "Uninstall with: ${UNINSTALL_BIN} [--purge-config]"
echo "If needed, add ${BIN_DIR} to your PATH."
