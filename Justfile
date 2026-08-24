# server-bootstrap command surface

default:
    @just --list

# Install packages, dotfiles, compatibility links, and zsh.
install:
    ./install.sh install

# Reapply the Debian package baseline.
core:
    ./install.sh core

# Reapply user dotfiles.
dotfiles:
    ./install.sh dotfiles

# Explicitly add the repository's public keys to ~/.ssh/authorized_keys.
authorize-keys:
    ./install.sh authorize-keys

# Pull this repository and reapply the user environment.
sync:
    git pull --ff-only
    ./install.sh core
    ./install.sh dotfiles

# Static shell analysis. Never executes target-machine behavior.
lint:
    shellcheck -x -P SCRIPTDIR infra/lib/*.sh infra/*.sh install.sh remote-install.sh dots/bin/*

# Format shell files in place.
fmt:
    shfmt -w infra/lib/*.sh infra/*.sh install.sh remote-install.sh dots/bin/*

# Check shell formatting without modifying files.
check-fmt:
    shfmt -d infra/lib/*.sh infra/*.sh install.sh remote-install.sh dots/bin/*

# Check the working tree for common forms of accidentally committed secrets.
audit-public:
    ./infra/public-audit.sh

# Safe development validation.
check: lint check-fmt audit-public
