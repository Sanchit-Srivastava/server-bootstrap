#!/usr/bin/env bash
# Official prebuilt packages: https://yazi-rs.github.io/docs/installation/

install_yazi() (
	set -euo pipefail
	local version="26.9.1"
	local arch target checksum staging package
	arch="$(dpkg --print-architecture)"
	case "$arch" in
	amd64)
		target="x86_64"
		checksum="331d6247c0a0fd549f14cd599a928a529b8b22eded1bb1f61a518376c7621b45"
		;;
	arm64)
		target="aarch64"
		checksum="0384a3b7c28ad6aa05ac1bb434dd4e7594051b6be4a1b07d43ca19a86826a315"
		;;
	*) die "Yazi's pinned Debian package supports amd64 and arm64 (detected: $arch)." ;;
	esac

	staging="$(mktemp -d)"
	trap 'rm -rf -- "$staging"' EXIT
	package="yazi-${target}-unknown-linux-gnu.deb"
	log_info "Downloading Yazi ${version} for ${arch}..."
	curl -fsSL --retry 3 -o "$staging/$package" \
		"https://github.com/sxyazi/yazi/releases/download/v${version}/${package}"
	(cd "$staging" && printf '%s  %s\n' "$checksum" "$package" | sha256sum --check --status) ||
		die "Yazi package checksum verification failed."

	# Public release artifacts only; allow APT's _apt sandbox to read the package.
	chmod 755 "$staging"
	chmod 644 "$staging/$package"
	sudo apt-get install -y --no-install-recommends "$staging/$package"
	yazi --version
	ya --version
)
