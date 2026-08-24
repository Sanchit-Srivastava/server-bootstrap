# server-bootstrap

server-bootstrap installs a small, familiar command-line environment on an
already working Debian 13 server. It is personal configuration, not a generic
server installer or an application deployment system.

The repository is intentionally public so a new machine can clone it without
credentials. It contains no secrets or host-specific information. The SSH keys
under `keys/` are public keys; private keys never belong in this repository.

## Ownership boundary

Debian owns boot, filesystems, storage, networking, SSH server configuration,
firewalling, updates, hardware, and the base operating system. Separate
application repositories own Docker, Compose deployments, services, data,
backups, upgrades, monitoring, and reverse proxies.

server-bootstrap owns only native CLI packages, user dotfiles, the login shell,
and explicitly requested SSH public-key authorization.

## Debian installation

Install Debian 13 from the official `netinst` image. At the software selection
screen, select **SSH server** and **standard system utilities**, and deselect all
desktop environments. Create a regular administrative user with sudo access.

## Installation

On a fresh machine, install the two bootstrap prerequisites and clone over
HTTPS:

```bash
sudo apt-get update
sudo apt-get install -y curl git
git clone https://github.com/Sanchit-Srivastava/server-bootstrap.git ~/server-bootstrap
cd ~/server-bootstrap
./install.sh
```

The pasteable entry point performs the same clone and installation:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Sanchit-Srivastava/server-bootstrap/main/remote-install.sh)
```

For reproducibility, use a known tag:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Sanchit-Srivastava/server-bootstrap/main/remote-install.sh) --ref vYYYY.MM.DD
```

The installer updates APT package metadata but does not upgrade the operating
system. It installs the package list, applies dotfiles, creates Debian command
compatibility links for `bat` and `fd`, and changes the current user's login
shell to zsh.

## Commands

```bash
just install          # packages, dotfiles, compatibility links, and zsh
just core             # reapply the native package baseline
just dotfiles         # reapply user dotfiles
just authorize-keys   # explicitly authorize the committed public SSH keys
just sync             # fast-forward pull, then reapply core and dotfiles
just check            # static checks for development
```

`just authorize-keys` modifies `~/.ssh/authorized_keys`. It is deliberately not
part of `just install`: review the keys first, run it from a local console or an
already authenticated session, and confirm a second SSH login before removing
any existing access method.

Git identity is machine-local and is never committed here. Configure it after
installation:

```bash
git config --file ~/.gitconfig.local user.name "Your Name"
git config --file ~/.gitconfig.local user.email "you@example.com"
```

## Secrets

No secret handling is currently required. If that changes, this repository will
use the same SOPS + age design and age recipient as Archway. Only SOPS-encrypted
documents and the public age recipient may be committed; the age private key and
all decrypted output must remain outside the repository.

## Development

Do not execute installer scripts on a development machine. Safe static checks:

```bash
just lint
just check-fmt
just audit-public
just check
```
