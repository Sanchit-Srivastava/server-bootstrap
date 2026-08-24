# AGENTS.md — server-bootstrap coding-agent instructions

server-bootstrap is a public, Debian 13-only repository for installing a small,
familiar command-line environment on personal servers.

## Safety

The repository is developed on ordinary workstations but targets real servers.
Never run `install.sh`, `remote-install.sh`, `infra/bootstrap.sh`,
`infra/dotfiles.sh`, or `infra/authorize-keys.sh` on a development machine.

Safe development commands are:

```bash
just lint
just check-fmt
just audit-public
just check
```

Validate target behavior statically. Do not install packages, change login
shells, or modify SSH authorization while testing repository changes.

## Scope

Debian and its installer own boot, filesystems, storage, networking, SSH server
configuration, firewalling, updates, hardware, and the base operating system.

Application repositories own Docker, Compose, services, application data,
backups, upgrades, monitoring, and reverse proxies.

server-bootstrap owns only:

- a focused list of Debian command-line packages;
- user dotfiles and small compatibility links;
- the user's login shell; and
- explicitly requested incoming SSH public-key authorization.

Do not add Docker, service deployment, firewall rules, system hardening,
storage configuration, secrets, or host-specific configuration here.

## Public-repository boundary

Never commit private keys, passwords, tokens, decrypted secrets, private
addresses, internal hostnames, personal inventory, or generated runtime data.
OpenSSH public keys and age recipients are public material and may be committed.

There are currently no secrets in this repository. If one becomes necessary,
use SOPS with age, reuse Archway's age recipient, commit only the encrypted
document, and keep the age private key outside the repository.

## Shell conventions

Scripts use:

```bash
#!/usr/bin/env bash
set -euo pipefail
```

Use `set -eEuo pipefail` when an inherited ERR trap is required. Quote variable
expansions, use `UPPER_SNAKE_CASE` for exported/global constants and
`lower_snake_case` for locals, and keep commands idempotent.
