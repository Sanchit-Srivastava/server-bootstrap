#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
KEYS_DIR="${REPOSITORY_ROOT}/keys"

# shellcheck source=lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=lib/authorized-keys.sh
. "${SCRIPT_DIR}/lib/authorized-keys.sh"

main() {
	[[ $EUID -ne 0 ]] || die "Run as the account that should receive SSH access, not root."
	command -v ssh-keygen >/dev/null 2>&1 || die "ssh-keygen is required."
	[[ -d "$KEYS_DIR" ]] || die "Public-key directory not found: $KEYS_DIR"

	authorize_keys "$KEYS_DIR" "${HOME}/.ssh"
	log_warn "Verify a new SSH session before changing any existing login method."
}

main "$@"
