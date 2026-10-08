#!/usr/bin/env bash
set -euo pipefail

usage() {
	cat <<EOF
Usage: $(basename "$0") [--ref GIT_REF]

Clone the public server-bootstrap repository and run its installer.
Default ref: main. Accepts a branch, tag, or full 40-character commit ID.
Use refs/heads/NAME or refs/tags/NAME to disambiguate a branch and tag.
Existing clones must have the expected origin, be clean, and already be at
exactly the requested commit. They are never reset or switched automatically.
EOF
}

remote_die() {
	printf '%s\n' "$*" >&2
	exit 1
}

resolve_remote_ref() {
	local repository="$1"
	local ref="$2"
	local refs branch tag
	if [[ "$ref" =~ ^[0-9a-f]{40}$ ]]; then
		printf '%s\n' "$ref"
		return
	fi
	case "$ref" in
	refs/heads/* | refs/tags/*)
		git check-ref-format "$ref" >/dev/null || remote_die "Invalid ref: $ref"
		printf '%s\n' "$ref"
		return
		;;
	refs/* | -*) remote_die "Unsupported ref: $ref" ;;
	esac
	git check-ref-format "refs/heads/$ref" >/dev/null || remote_die "Invalid ref: $ref"
	refs="$(git ls-remote --heads --tags -- "$repository" "refs/heads/$ref" "refs/tags/$ref")" ||
		remote_die "Cannot resolve the requested remote ref: $ref"
	branch="$(printf '%s\n' "$refs" | awk -v ref="refs/heads/$ref" '$2 == ref { print $2 }')"
	tag="$(printf '%s\n' "$refs" | awk -v ref="refs/tags/$ref" '$2 == ref { print $2 }')"
	[[ -z "$branch" || -z "$tag" ]] || remote_die "Ambiguous ref: $ref; use refs/heads/ or refs/tags/."
	[[ -n "$branch$tag" ]] || remote_die "Remote ref not found: $ref"
	printf '%s\n' "$branch$tag"
}

prepare_repository() {
	local target="$1"
	local repository="$2"
	local requested_ref="$3"
	local existing=0 origin status index_flags ref commit head branch
	if [[ -e "$target" || -L "$target" ]]; then
		[[ ! -L "$target" && -d "$target/.git" && ! -L "$target/.git" ]] ||
			remote_die "Target exists and is not a standalone Git clone: $target"
		origin="$(git -C "$target" remote get-url --all origin)" || remote_die "Cannot read target origin."
		[[ "$origin" == "$repository" ]] || remote_die "Target origin does not match the expected repository."
		index_flags="$(git -C "$target" ls-files -v)" || remote_die "Cannot inspect target index."
		if printf '%s\n' "$index_flags" | LC_ALL=C awk '/^[a-zS] / { found = 1 } END { exit !found }'; then
			remote_die "Target has assume-unchanged or skip-worktree entries; restore normal index checks first."
		fi
		status="$(git -C "$target" -c core.fsmonitor=false status --porcelain=v1 --untracked-files=all --ignored)" ||
			remote_die "Cannot inspect target working tree."
		[[ -z "$status" ]] || remote_die "Target is dirty (including untracked or ignored files); review it manually."
		existing=1
	fi

	ref="$(resolve_remote_ref "$repository" "$requested_ref")" || exit 1
	if [[ "$existing" -eq 0 ]]; then
		git init -- "$target" || remote_die "Cannot create target repository."
		git -C "$target" remote add origin "$repository" || remote_die "Cannot set repository origin."
	fi
	# Fetch exactly the requested ref; a full commit ID also works with a fresh
	# checkout (unlike clone --branch). No existing worktree files are changed.
	git -C "$target" fetch --no-tags --no-recurse-submodules origin "$ref" ||
		remote_die "Cannot fetch requested ref: $requested_ref"
	commit="$(git -C "$target" rev-parse --verify 'FETCH_HEAD^{commit}')" || remote_die "Requested ref is not a commit."
	if [[ "$existing" -eq 1 ]]; then
		head="$(git -C "$target" rev-parse --verify HEAD)" || remote_die "Target has no checked-out commit."
		[[ "$head" == "$commit" ]] ||
			remote_die "Target HEAD does not match requested ref $requested_ref; update it manually or choose another SERVER_BOOTSTRAP_DIR."
		printf '%s\n' "Verified existing clone at $commit"
	elif [[ "$ref" == refs/heads/* ]]; then
		branch="${ref#refs/heads/}"
		git -C "$target" checkout -b "$branch" "$commit" || remote_die "Cannot check out requested branch."
		git -C "$target" config "branch.${branch}.remote" origin
		git -C "$target" config "branch.${branch}.merge" "$ref"
	else
		git -C "$target" checkout --detach "$commit" || remote_die "Cannot check out requested commit."
	fi
}

main() {
	local repository="https://github.com/Sanchit-Srivastava/server-bootstrap.git"
	local ref="main"
	local target="${SERVER_BOOTSTRAP_DIR:-${HOME}/server-bootstrap}"
	while [[ $# -gt 0 ]]; do
		case "$1" in
		--ref)
			[[ $# -ge 2 && -n "$2" ]] || {
				usage >&2
				exit 2
			}
			ref="$2"
			shift 2
			;;
		-h | --help)
			usage
			return
			;;
		*)
			usage >&2
			exit 2
			;;
		esac
	done

	[[ $EUID -ne 0 ]] || remote_die "Run this installer as a regular user, not root."
	[[ -r /etc/os-release ]] || remote_die "Cannot identify the operating system."
	# shellcheck disable=SC1091
	. /etc/os-release
	[[ "${ID:-}" == debian && "${VERSION_ID:-}" == 13 ]] || remote_die "Debian 13 is required."
	command -v sudo >/dev/null 2>&1 || remote_die "A regular user with sudo access is required."
	if ! command -v git >/dev/null 2>&1; then
		sudo apt-get update
		sudo apt-get install -y git ca-certificates
	fi

	prepare_repository "$target" "$repository" "$ref"
	exec "${target}/install.sh" install
}

# Sourcing defines helpers only, allowing isolated Git fixtures without running
# package installation or the checked-out installer.
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
	main "$@"
fi
