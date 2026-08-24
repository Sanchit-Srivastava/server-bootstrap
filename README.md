# server-bootstrap

server-bootstrap configures a Debian 13 server with a focused command-line
toolset and shared user dotfiles. Application deployment remains separate, so
the resulting system is ready for service-specific repositories and Compose
projects.

## What it installs

- zsh with Oh My Zsh and interactive plugins;
- tmux, Neovim, Git, lazygit, and familiar command-line utilities;
- shared aliases, editor settings, and the tmux sessionizer;
- compatibility commands for Debian's `batcat` and `fdfind` executables; and
- an optional command for installing the public SSH keys in `keys/`.

The Debian installation continues to manage boot, storage, networking, SSH,
firewalling, system updates, and hardware. This repository does not install
Docker or deploy applications.

## Install Debian

Install Debian 13 from the official `netinst` image. At the software selection
screen:

1. select **SSH server**;
2. select **standard system utilities**; and
3. deselect **Debian desktop environment** and all desktop options.

Create a regular administrative user with sudo access. After installation, log
in as that user from the local console or through the initial SSH access method
configured during installation.

## Install the command-line environment

Install the bootstrap prerequisites, clone the repository over HTTPS, and run
the installer:

```bash
sudo apt-get update
sudo apt-get install -y curl git
git clone https://github.com/Sanchit-Srivastava/server-bootstrap.git ~/server-bootstrap
cd ~/server-bootstrap
./install.sh
```

Alternatively, use the pasteable entry point:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Sanchit-Srivastava/server-bootstrap/main/remote-install.sh)
```

A release tag can be selected with `--ref`:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Sanchit-Srivastava/server-bootstrap/main/remote-install.sh) --ref vYYYY.MM.DD
```

The installer refreshes APT package metadata, installs the packages in
`infra/pkgs/core.txt`, applies the dotfiles, and changes the current user's
login shell to zsh. Log out and back in after the first installation.

## Configure SSH access

The repository contains the authorized public keys in [`keys/`](keys/). To add
all `*.pub` files there to the current user's `~/.ssh/authorized_keys`, run on
the server:

```bash
cd ~/server-bootstrap
just authorize-keys
```

The command validates each public key, creates `~/.ssh` with mode `0700`,
creates `authorized_keys` with mode `0600`, and skips keys that are already
present. It configures access for the user running the command; run it while
logged in as the account that should receive SSH access.

Then open a new terminal on the client machine and test the connection:

```bash
ssh <username>@<server-address>
```

Keep the console or existing SSH session open until the new key-based session
has succeeded.

### Add another public key

Place one complete OpenSSH public-key line in a new file ending in `.pub`:

```text
keys/<key-name>.pub
```

For example, from a workstation clone of this repository:

```bash
cp ~/.ssh/id_ed25519.pub keys/<key-name>.pub
ssh-keygen -l -f keys/<key-name>.pub
```

Commit and push the public-key file, pull the repository on the server, and run
`just authorize-keys` again. OpenSSH public keys may be published; private-key
files must remain on the client machine.

### Add a key manually

Without using the repository script, prepare the authorization file on the
server:

```bash
install -d -m 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
${EDITOR:-vi} ~/.ssh/authorized_keys
```

Paste the complete public-key line into `authorized_keys`, save it, and test a
new SSH connection.

## Commands

```bash
just install          # packages, dotfiles, compatibility links, and zsh
just core             # reapply the native package baseline
just dotfiles         # reapply user dotfiles
just authorize-keys   # add keys/*.pub to ~/.ssh/authorized_keys
just sync             # fast-forward pull, then reapply core and dotfiles
just check            # run static development checks
```

## Configure Git identity

The shared Git configuration loads identity settings from
`~/.gitconfig.local`. Configure them on each machine:

```bash
git config --file ~/.gitconfig.local user.name "Your Name"
git config --file ~/.gitconfig.local user.email "you@example.com"
```

## Public repository contents

Configuration and OpenSSH public keys may be committed. Private keys,
passwords, access tokens, decrypted secrets, private addresses, and
host-specific inventory must not be committed. `just audit-public` checks the
working tree for common private-key and token formats.

## Development

Installer commands target a Debian 13 server. Development checks do not install
packages or modify the local user account:

```bash
just lint
just check-fmt
just audit-public
just check
```
