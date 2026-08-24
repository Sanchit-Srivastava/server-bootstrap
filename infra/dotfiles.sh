#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DOTFILES_DIR="${REPOSITORY_ROOT}/dots"

# shellcheck source=lib/common.sh
. "${SCRIPT_DIR}/lib/common.sh"

backup_path() {
	local path="$1"
	local backup="${path}.pre-server-bootstrap.bak"
	if [[ -e "$backup" || -L "$backup" ]]; then
		backup="${backup}.$(date -u +%Y%m%dT%H%M%SZ)"
	fi
	mv -- "$path" "$backup"
	log_warn "Backed up existing path: $path -> $backup"
}

link_dotfile() {
	local source="$1"
	local target="$2"
	local current_target

	mkdir -p -- "$(dirname "$target")"
	if [[ -L "$target" ]]; then
		current_target="$(readlink "$target")"
		if [[ "$current_target" == "$source" ]]; then
			log_info "Already linked: $target"
			return 0
		fi
		rm -- "$target"
	elif [[ -e "$target" ]]; then
		backup_path "$target"
	fi

	ln -s -- "$source" "$target"
	log_info "Linked: $target"
}

clone_if_missing() {
	local repository="$1"
	local target="$2"

	if [[ -d "${target}/.git" ]]; then
		log_info "Already cloned: $target"
		return 0
	fi
	if [[ -e "$target" ]]; then
		backup_path "$target"
	fi
	git clone --depth=1 "$repository" "$target"
}

install_zsh_framework() {
	local framework="${HOME}/.oh-my-zsh"
	local custom="${framework}/custom"

	log_info "Installing the zsh framework and interactive plugins..."
	clone_if_missing "https://github.com/ohmyzsh/ohmyzsh.git" "$framework"
	clone_if_missing "https://github.com/zsh-users/zsh-autosuggestions" \
		"${custom}/plugins/zsh-autosuggestions"
	clone_if_missing "https://github.com/zsh-users/zsh-syntax-highlighting" \
		"${custom}/plugins/zsh-syntax-highlighting"
	clone_if_missing "https://github.com/Aloxaf/fzf-tab" \
		"${custom}/plugins/fzf-tab"
}

install_compatibility_links() {
	local local_bin="${HOME}/.local/bin"
	mkdir -p "$local_bin"

	if ! command -v bat >/dev/null 2>&1 && command -v batcat >/dev/null 2>&1; then
		ln -sfn "$(command -v batcat)" "${local_bin}/bat"
		log_info "Linked Debian's batcat executable as ~/.local/bin/bat."
	fi
	if ! command -v fd >/dev/null 2>&1 && command -v fdfind >/dev/null 2>&1; then
		ln -sfn "$(command -v fdfind)" "${local_bin}/fd"
		log_info "Linked Debian's fdfind executable as ~/.local/bin/fd."
	fi
}

ensure_local_git_config() {
	local local_config="${HOME}/.gitconfig.local"
	if [[ ! -e "$local_config" ]]; then
		install -m 600 /dev/null "$local_config"
		log_info "Created empty machine-local Git identity file: $local_config"
	fi
}

main() {
	[[ $EUID -ne 0 ]] || die "Run as a regular user, not root."
	[[ -d "$DOTFILES_DIR" ]] || die "Dotfiles directory not found: $DOTFILES_DIR"
	command -v git >/dev/null 2>&1 || die "git is required; run ./install.sh core first."

	install_zsh_framework
	install_compatibility_links

	link_dotfile "${DOTFILES_DIR}/zsh/.zshrc" "${HOME}/.zshrc"
	link_dotfile "${DOTFILES_DIR}/zsh/.zshenv" "${HOME}/.zshenv"
	link_dotfile "${DOTFILES_DIR}/tmux/tmux.conf" "${HOME}/.config/tmux/tmux.conf"
	link_dotfile "${DOTFILES_DIR}/nvim" "${HOME}/.config/nvim"
	link_dotfile "${DOTFILES_DIR}/git/.gitconfig" "${HOME}/.gitconfig"
	link_dotfile "${DOTFILES_DIR}/lazygit/config.yml" "${HOME}/.config/lazygit/config.yml"
	link_dotfile "${DOTFILES_DIR}/bat/config" "${HOME}/.config/bat/config"

	mkdir -p "${HOME}/bin"
	local script
	for script in "${DOTFILES_DIR}"/bin/*; do
		[[ -f "$script" ]] || continue
		link_dotfile "$script" "${HOME}/bin/$(basename "$script")"
	done

	ensure_local_git_config
	log_info "User dotfiles are installed. Start a new login shell to use them."
}

main "$@"
