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

### Debian 13 cloud images

A provider's Debian 13 image is also suitable; a new `netinst` installation is
not required. Before running this repository, confirm:

- the image really is Debian 13, with working Debian APT repositories;
- you have an existing **non-root operator account with sudo access**;
- initial SSH access or the provider console works, and you keep that access
  open until a second login succeeds; and
- DNS and network access to Debian mirrors and GitHub work.

For a root-only image, use the provider console or initial root login to prepare
that regular sudo-capable account first. Verify it in a separate login before
continuing. Account creation, SSH-server policy, firewall rules and provider
networking remain manual/provider responsibilities, not bootstrap operations.
Do not run these installers as root or with `sudo bash`.

## Install the command-line environment

As the regular operator, install the bootstrap prerequisites, clone over HTTPS,
and run the installer:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
git clone https://github.com/Sanchit-Srivastava/server-bootstrap.git ~/server-bootstrap
cd ~/server-bootstrap
./install.sh
```

Alternatively, after installing those prerequisites, use the pasteable entry
point:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Sanchit-Srivastava/server-bootstrap/main/remote-install.sh)
```

A release tag can be selected with `--ref`:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/Sanchit-Srivastava/server-bootstrap/main/remote-install.sh) --ref vYYYY.MM.DD
```

`--ref` accepts a branch, tag, or full lowercase 40-character commit ID. If a
branch and tag have the same name, use `refs/heads/NAME` or `refs/tags/NAME`.
For a repeatable code revision, pin **both the wrapper and the checkout** to a
reviewed commit (replace the placeholder below):

```bash
ref='<reviewed-full-40-character-commit-id>'
curl -fsSL -o server-bootstrap-install.sh \
  "https://raw.githubusercontent.com/Sanchit-Srivastava/server-bootstrap/$ref/remote-install.sh" &&
  bash server-bootstrap-install.sh --ref "$ref"
```

The default checkout is `~/server-bootstrap`; set `SERVER_BOOTSTRAP_DIR` to use
another location. An existing checkout is reused only if its single origin URL
matches the public HTTPS repository, it has no local changes (including
untracked/ignored files or hidden index entries), and HEAD already equals the
requested remote commit. A mismatch fails before executing its installer; the
wrapper never resets, switches or cleans an existing checkout. Fetching may
update Git metadata, not working files. Review/update the checkout manually or
choose a new directory. Worktrees and symlinked targets are not accepted.
A failed first fetch may leave an incomplete directory; inspect/remove that
unused directory before retrying rather than treating it as an installed clone.

New branch checkouts track their origin branch. Tags and commit IDs produce a
detached checkout; update those deliberately, not with `just sync`. Tags and
branches can move upstream; only a commit ID fixes the code identity. An
explicit commit must still be fetchable from the public remote.

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

The command validates **all** incoming keys before writing any authorization
files, creates `~/.ssh` with mode `0700` and `authorized_keys` with mode `0600`,
and adds only new key identities. Existing option-prefixed keys (for example
`restrict`, `from=...` or `command=...`) count as already present: their lines
are preserved, never supplemented with an unrestricted duplicate. Existing
restrictions are not changed or removed; review any policy conflict manually.
The complete update is staged before replacing the file, and missing final
newlines are handled. Symlinked authorization paths are refused. Run one copy
at a time and do not edit `authorized_keys` concurrently.

It configures access for the user running the command; run it while logged in
as the account that should receive SSH access. New keys get ordinary unrestricted
user authorization, so review `keys/` before running this optional command.

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
just check            # static checks and isolated regression fixtures
```

## Configure Git identity

The shared Git configuration loads identity settings from
`~/.gitconfig.local`. Configure them on each machine:

```bash
git config --file ~/.gitconfig.local user.name "Your Name"
git config --file ~/.gitconfig.local user.email "you@example.com"
```

## Dotfile locations and updates

Tmux, Neovim, lazygit and bat configuration is linked under
`${XDG_CONFIG_HOME:-$HOME/.config}`. If you use a custom XDG location, export the
same **absolute** path during installation and in subsequent login environments.
Tmux's reload binding uses that location too. Shell startup files and Git's local
identity include remain in the home directory. Machine-specific shell overrides
belong in `~/.zshrc.local`.

The sessionizer uses a readable basename plus a canonical-path hash. Two `api`
directories therefore get different sessions; relative paths and symlink aliases
of one directory reuse a session. A stored path is checked before reattaching.
Old basename-only sessions are left alone; close them manually when no longer
needed. Interactive directory discovery is line-based and `SESSIONIZER_DIRS` is
colon-separated, so use ordinary directory names without newlines or colons in
that search list.

### Dependency update policy

This is a versioned environment, not a bit-for-bit reproducible OS installation:

- Debian packages follow the configured Debian 13 repositories at install time.
- Oh My Zsh and its three external plugins are shallow-cloned from their current
  upstream default branches **once**. Existing checkouts are retained, including
  local edits; `just dotfiles` and `just sync` do not update them.
- Oh My Zsh's automatic update checks are disabled in the shared zsh config.
  Update shell dependencies deliberately, after reviewing upstream changes and
  saving any local work. For each checkout under `~/.oh-my-zsh` and its
  `custom/plugins/` directories, inspect `git status`, fetch, review the diff and
  then fast-forward the checked-out branch. Do not reset away local changes.
- To reproduce a particular shell environment, record each dependency's full
  `git rev-parse HEAD` and deliberately check out those revisions. Pinning the
  bootstrap commit alone does not pin these dependencies or Debian packages.

## Public repository contents

Configuration and OpenSSH public keys may be committed. Private keys,
passwords, access tokens, decrypted secrets, private addresses, and
host-specific inventory must not be committed. `just audit-public` checks the
working tree (including ignored and hidden files) for common private-key and
token formats. It requires ripgrep and fails if the scanner cannot complete;
reports contain filenames, not matched content. This is a guardrail, not a
complete secret detector or a replacement for reviewing the diff.

## Development

Installer commands target a Debian 13 server. Development checks do not install
packages or modify the local user account. They require Python 3 (stdlib only),
Bash, Git, OpenSSH's `ssh-keygen`, ripgrep, tmux, just, ShellCheck, shfmt, and the
usual POSIX/core utilities on PATH. Python is a development-test prerequisite,
not an added server package.

```bash
just lint
just check-fmt
just audit-public
just test
just check
```

`just check` includes isolated regression tests for restricted SSH entries,
validation-before-write, line boundaries, clone provenance/cleanliness/ref
selection, audit failures, XDG links and real tmux session creation. The tests
source helper definitions but never run installer entrypoints. They use existing
public keys and harmless scanner markers, local Git fixtures, a temporary HOME,
and private tmux sockets; interactive attach/switch is simulated. No network or
real account changes are needed. Fixtures respect `TMPDIR`, are outside the
checkout, and are removed afterwards. A passing check is not a Debian deployment
or real SSH-login drill; perform those separately on a disposable target.
