#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
KEYS_DIR="${REPOSITORY_ROOT}/keys"

# shellcheck source=lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

validate_public_key() {
	local key_file="$1"
	local line_count
	line_count="$(awk 'NF { count++ } END { print count + 0 }' "$key_file")"
	[[ "$line_count" -eq 1 ]] || die "Expected exactly one public key in: $key_file"
	ssh-keygen -l -f "$key_file" >/dev/null 2>&1 || die "Invalid OpenSSH public key: $key_file"
}

authorize_key() {
	local key_file="$1"
	local authorized_keys="$2"
	local key_type
	local key_data
	key_type="$(awk 'NF { print $1 }' "$key_file")"
	key_data="$(awk 'NF { print $2 }' "$key_file")"

	if awk -v type="$key_type" -v data="$key_data" \
		'$1 == type && $2 == data { found = 1 } END { exit !found }' "$authorized_keys"; then
		log_info "Already authorized: $(basename "$key_file")"
		return 0
	fi

	printf '%s\n' "$(awk 'NF { print; exit }' "$key_file")" >>"$authorized_keys"
	log_info "Authorized: $(basename "$key_file")"
}

main() {
	[[ $EUID -ne 0 ]] || die "Run as the account that should receive SSH access, not root."
	command -v ssh-keygen >/dev/null 2>&1 || die "ssh-keygen is required."
	[[ -d "$KEYS_DIR" ]] || die "Public-key directory not found: $KEYS_DIR"

	local ssh_dir="${HOME}/.ssh"
	local authorized_keys="${ssh_dir}/authorized_keys"
	install -d -m 700 "$ssh_dir"
	touch "$authorized_keys"
	chmod 600 "$authorized_keys"

	local key_file
	local count=0
	for key_file in "${KEYS_DIR}"/*.pub; do
		[[ -f "$key_file" ]] || continue
		validate_public_key "$key_file"
		authorize_key "$key_file" "$authorized_keys"
		count=$((count + 1))
	done
	[[ "$count" -gt 0 ]] || die "No public keys found in: $KEYS_DIR"

	log_warn "Verify a new SSH session before changing any existing login method."
}

main "$@"
