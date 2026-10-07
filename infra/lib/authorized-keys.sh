#!/usr/bin/env bash
# Source with common.sh. Only explicit paths passed by the caller are modified.

read_public_key() {
	local key_file="$1"
	local line key_type key_data
	[[ "$(awk 'NF { n++ } END { print n + 0 }' "$key_file")" -eq 1 ]] ||
		die "Expected exactly one public key in: $key_file"
	line="$(awk 'NF { print; exit }' "$key_file")"
	# Incoming files are plain public keys, never authorized_keys option lines.
	[[ "$line" =~ ^(ssh-|ecdsa-|sk-)[^[:space:]]+[[:space:]] ]] ||
		die "Expected a public key without authorization options: $key_file"
	# Validate the captured key fields, not a second read of a mutable file.
	# Omitting the comment also prevents an option-like first field from being
	# mistaken by ssh-keygen for an authorized_keys options prefix.
	read -r key_type key_data _ <<<"$line"
	ssh-keygen -l -f /dev/stdin <<<"$key_type $key_data" >/dev/null 2>&1 ||
		die "Invalid OpenSSH public key: $key_file"
	printf '%s\n' "$line"
}

key_is_authorized() {
	local key_line="$1"
	local authorized_keys="$2"
	local key_type key_data
	read -r key_type key_data _ <<<"$key_line"
	# Options are a single field, but may contain quoted whitespace and escaped
	# quotes. Only examine the key fields, never an option value or a comment.
	awk -v type="$key_type" -v data="$key_data" '
		function field(    out, c, quoted, escaped) {
			sub(/^[ \t]+/, "", rest)
			out = ""; quoted = 0; escaped = 0
			while (length(rest)) {
				c = substr(rest, 1, 1); rest = substr(rest, 2)
				if (!quoted && c ~ /[ \t]/) break
				out = out c
				if (escaped) escaped = 0
				else if (c == "\\" && quoted) escaped = 1
				else if (c == "\"") quoted = !quoted
			}
			if (quoted || escaped) bad = 1
			return out
		}
		/^[ \t]*(#|$)/ { next }
		{
			rest = $0
			first = field(); second = field()
			if (first == type && second == data) found = 1
			else if (second == type && field() == data) found = 1
		}
		END { if (bad) exit 2; exit !found }
	' "$authorized_keys"
}

authorize_key_line() {
	local key_line="$1"
	local authorized_keys="$2"
	local status
	if key_is_authorized "$key_line" "$authorized_keys"; then
		log_info "Key already present; retaining its existing authorization policy."
		return 0
	else
		status=$?
		[[ "$status" -eq 1 ]] || die "Cannot safely inspect existing authorized_keys; review it manually."
	fi
	# Command substitution strips a trailing newline, but not another last byte.
	if [[ -s "$authorized_keys" && -n "$(tail -c 1 -- "$authorized_keys")" ]]; then
		printf '\n' >>"$authorized_keys"
	fi
	printf '%s\n' "$key_line" >>"$authorized_keys"
	log_info "Authorized a new public key."
}

authorize_keys() (
	local keys_dir="$1"
	local ssh_dir="$2"
	local key_file line staged
	local -a keys=()
	# Validate the entire batch and retain the validated bytes before any writes.
	for key_file in "${keys_dir}"/*.pub; do
		[[ -f "$key_file" ]] || continue
		line="$(read_public_key "$key_file")" || exit 1
		keys+=("$line")
	done
	[[ ${#keys[@]} -gt 0 ]] || die "No public keys found in: $keys_dir"

	local authorized_keys="${ssh_dir}/authorized_keys"
	[[ ! -L "$ssh_dir" && ! -L "$authorized_keys" ]] || die "Refusing symlinked SSH authorization paths."
	[[ ! -e "$authorized_keys" || -f "$authorized_keys" ]] || die "authorized_keys must be a regular file."
	umask 077
	mkdir -p -- "$ssh_dir"
	staged="$(mktemp "${ssh_dir}/.authorized_keys.XXXXXXXX")"
	trap 'rm -f -- "$staged"' EXIT
	if [[ -e "$authorized_keys" ]]; then
		cat -- "$authorized_keys" >"$staged"
	fi
	for line in "${keys[@]}"; do
		authorize_key_line "$line" "$staged"
	done
	chmod 600 "$staged"
	mv -f -- "$staged" "$authorized_keys"
	chmod 700 "$ssh_dir"
)
