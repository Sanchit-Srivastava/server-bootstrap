# SSH public keys

Each `*.pub` file in this directory contains one OpenSSH public key. Running the
following command on a server authorizes every key for the current user:

```bash
cd ~/server-bootstrap
just authorize-keys
```

The keys are added to `~/.ssh/authorized_keys` without duplicating entries that
are already present.

## Add a key

Copy the public half of an SSH key from a client machine into a descriptively
named `.pub` file:

```bash
cp ~/.ssh/id_ed25519.pub keys/<key-name>.pub
ssh-keygen -l -f keys/<key-name>.pub
```

The file must contain the complete public-key line, including the key type and
encoded key data. Commit the `.pub` file, pull the repository on the server,
and run `just authorize-keys` again.

OpenSSH public keys are not secret. Do not place private keys, FIDO key handles,
certificates containing private keys, tokens, or decrypted secrets in this
directory.

## Manual installation

To authorize a public key without the script, edit the target account's file:

```bash
install -d -m 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
${EDITOR:-vi} ~/.ssh/authorized_keys
```

Paste one complete public-key line per line, save the file, and verify a new SSH
login before closing the existing console or session.
