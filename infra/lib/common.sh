#!/usr/bin/env bash

if [[ -t 1 ]]; then
	COLOR_BLUE=$'\033[34m'
	COLOR_YELLOW=$'\033[33m'
	COLOR_RED=$'\033[31m'
	COLOR_RESET=$'\033[0m'
else
	COLOR_BLUE=""
	COLOR_YELLOW=""
	COLOR_RED=""
	COLOR_RESET=""
fi

log_info() {
	printf '%s[info]%s %s\n' "$COLOR_BLUE" "$COLOR_RESET" "$*"
}

log_warn() {
	printf '%s[warn]%s %s\n' "$COLOR_YELLOW" "$COLOR_RESET" "$*" >&2
}

log_error() {
	printf '%s[error]%s %s\n' "$COLOR_RED" "$COLOR_RESET" "$*" >&2
}

die() {
	log_error "$*"
	exit 1
}
