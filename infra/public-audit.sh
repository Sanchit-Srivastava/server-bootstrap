#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck source=lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

cd "$REPOSITORY_ROOT"
command -v rg >/dev/null 2>&1 || die "ripgrep (rg) is required for the public audit."
command -v find >/dev/null 2>&1 || die "find is required for the public audit."

failed=0
private_key_pattern='BEGIN (OPENSSH|RSA|DSA|EC|PGP)'" PRIVATE KEY"
age_secret_pattern='AGE-SECRET-'"KEY-[A-Z0-9]+"
token_pattern='(github_pat_|ghp_|gho_|ghu_|ghs_|AKIA)[A-Za-z0-9_]+'

scan_pattern() {
	local description="$1"
	local pattern="$2"
	local matches status
	# Ignore user rg configuration and Git ignore rules. Never print matched
	# content, including on scanner errors; status 1 alone means no matches.
	if matches="$(rg --no-config -l --hidden --no-ignore --text \
		--glob '!.git/**' --glob '!infra/public-audit.sh' -e "$pattern" . 2>/dev/null)"; then
		status=0
	else
		status=$?
	fi
	[[ "$status" -le 1 ]] || die "Public audit scanner failed (exit $status); no clean result is available."
	if [[ -n "$matches" ]]; then
		log_error "$description detected in:"
		printf '%s\n' "$matches" >&2
		failed=1
	fi
}

scan_pattern "Private-key material" "$private_key_pattern"
scan_pattern "An age private key" "$age_secret_pattern"
scan_pattern "A likely access token" "$token_pattern"

forbidden_files="$(find . -path './.git' -prune -o -type f \
	\( -name '*.key' -o -name '*.pem' -o -name '.env' -o -name '.env.local' \) \
	-print)"
if [[ -n "$forbidden_files" ]]; then
	log_error "Forbidden secret-like filenames detected:"
	printf '%s\n' "$forbidden_files" >&2
	failed=1
fi

[[ "$failed" -eq 0 ]] || exit 1
log_info "Public-repository audit passed."
