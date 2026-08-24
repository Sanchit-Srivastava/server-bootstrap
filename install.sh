#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

usage() {
	cat <<EOF
Usage: $(basename "$0") [install|core|dotfiles|authorize-keys]

  install         Install packages and apply user dotfiles (default)
  core            Install/reapply native Debian packages
  dotfiles        Apply/reapply user dotfiles
  authorize-keys  Add the committed public keys to authorized_keys
EOF
}

operation="${1:-install}"
case "$operation" in
install)
	"${SCRIPT_DIR}/infra/bootstrap.sh"
	"${SCRIPT_DIR}/infra/dotfiles.sh"
	;;
core)
	"${SCRIPT_DIR}/infra/bootstrap.sh"
	;;
dotfiles)
	"${SCRIPT_DIR}/infra/dotfiles.sh"
	;;
authorize-keys)
	"${SCRIPT_DIR}/infra/authorize-keys.sh"
	;;
-h | --help)
	usage
	;;
*)
	usage >&2
	exit 2
	;;
esac
