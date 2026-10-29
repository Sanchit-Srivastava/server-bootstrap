#!/usr/bin/env bash
# Official Debian installation: https://github.com/cli/cli/blob/trunk/docs/install_linux.md

install_github_cli() (
	set -euo pipefail
	local staging
	staging="$(mktemp -d)"
	trap 'rm -rf -- "$staging"' EXIT

	log_info "Configuring the official GitHub CLI APT repository..."
	curl -fsSL --retry 3 -o "$staging/keyring.gpg" \
		https://cli.github.com/packages/githubcli-archive-keyring.gpg
	[[ -s "$staging/keyring.gpg" ]] || die "The GitHub CLI signing key download is empty."
	printf 'deb [arch=%s signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main\n' \
		"$(dpkg --print-architecture)" >"$staging/github-cli.list"

	sudo install -d -m 755 /etc/apt/keyrings /etc/apt/sources.list.d
	sudo install -m 644 "$staging/keyring.gpg" /etc/apt/keyrings/githubcli-archive-keyring.gpg
	sudo install -m 644 "$staging/github-cli.list" /etc/apt/sources.list.d/github-cli.list
	sudo apt-get update
	sudo apt-get install -y --no-install-recommends gh
	gh --version
)
