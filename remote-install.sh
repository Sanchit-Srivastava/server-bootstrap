#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_URL="https://github.com/Sanchit-Srivastava/server-bootstrap.git"
REPOSITORY_REF="main"
TARGET_DIR="${SERVER_BOOTSTRAP_DIR:-${HOME}/server-bootstrap}"

usage() {
	cat <<EOF
Usage: $(basename "$0") [--ref GIT_REF]

Clone the public server-bootstrap repository and run its installer.
Default ref: main
EOF
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	--ref)
		[[ $# -ge 2 ]] || {
			usage >&2
			exit 2
		}
		REPOSITORY_REF="$2"
		shift 2
		;;
	-h | --help)
		usage
		exit 0
		;;
	*)
		usage >&2
		exit 2
		;;
	esac
done

[[ $EUID -ne 0 ]] || {
	printf '%s\n' "Run this installer as a regular user, not root." >&2
	exit 1
}

if ! command -v git >/dev/null 2>&1; then
	command -v sudo >/dev/null 2>&1 || {
		printf '%s\n' "git is missing and sudo is unavailable." >&2
		exit 1
	}
	sudo apt-get update
	sudo apt-get install -y git ca-certificates
fi

if [[ -e "$TARGET_DIR" ]]; then
	if [[ ! -d "${TARGET_DIR}/.git" ]]; then
		printf '%s\n' "Target exists and is not a Git clone: $TARGET_DIR" >&2
		exit 1
	fi
	printf '%s\n' "Using existing clone: $TARGET_DIR"
else
	git clone --branch "$REPOSITORY_REF" --single-branch "$REPOSITORY_URL" "$TARGET_DIR"
fi

exec "${TARGET_DIR}/install.sh" install
