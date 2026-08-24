# Authorized SSH public keys

Files ending in `.pub` contain public OpenSSH keys and are safe to publish. They
grant incoming access only when explicitly added to an account's
`~/.ssh/authorized_keys` by `just authorize-keys`.

Review every key before authorization. Never place a private key, FIDO key
handle, certificate private key, token, hostname inventory, or decrypted secret
in this directory.
