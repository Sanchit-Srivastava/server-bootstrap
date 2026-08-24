#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# shellcheck source=lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

check_prerequisites() {
	[[ $EUID -ne 0 ]] || die "Run as a regular user, not root."
	[[ -r /etc/os-release ]] || die "Cannot identify the operating system."

	local distro_id=""
	local distro_version=""
	# shellcheck disable=SC1091
	. /etc/os-release
	distro_id="${ID:-}"
	distro_version="${VERSION_ID:-}"
	[[ "$distro_id" == "debian" && "$distro_version" == "13" ]] ||
		die "Debian 13 is required (detected: ${distro_id:-unknown} ${distro_version:-unknown})."

	command -v apt-get >/dev/null 2>&1 || die "apt-get is required."
	command -v sudo >/dev/null 2>&1 || die "sudo is required for package installation."

	if ! sudo -n true 2>/dev/null; then
		log_info "Sudo authentication required."
		sudo -v
	fi
}

read_package_list() {
	local file="$1"
	local -n output="$2"
	local line

	output=()
	while IFS= read -r line || [[ -n "$line" ]]; do
		[[ "$line" =~ ^[[:space:]]*# ]] && continue
		[[ -z "${line//[[:space:]]/}" ]] && continue
		output+=("$line")
	done <"$file"
}

install_packages() {
	local packages=()
	read_package_list "${SCRIPT_DIR}/pkgs/core.txt" packages
	[[ ${#packages[@]} -gt 0 ]] || die "The package list is empty."

	log_info "Refreshing Debian package metadata..."
	sudo apt-get update
	log_info "Installing ${#packages[@]} command-line packages..."
	sudo apt-get install -y --no-install-recommends "${packages[@]}"
}

set_login_shell() {
	local zsh_path
	local current_shell
	zsh_path="$(command -v zsh)"
	current_shell="$(getent passwd "$USER" | cut -d: -f7)"
	if [[ "$current_shell" == "$zsh_path" ]]; then
		log_info "Login shell is already zsh."
		return 0
	fi

	sudo chsh -s "$zsh_path" "$USER"
	log_info "Changed the login shell to zsh for the next login."
}

main() {
	check_prerequisites
	install_packages
	set_login_shell
	log_info "Debian command-line baseline is installed."
}

main "$@"
