# Security

## Reporting a vulnerability
Please **do not** open a public issue. Use GitHub's private vulnerability reporting
(Security → Report a vulnerability) on this repository, or message [@AtronixX_Support](https://t.me/AtronixX_Support) privately.
You will get a reply within a few days.

## How the bot protects your data
- SSH passwords, private keys and passphrases are encrypted with AES-256-GCM. Each value is bound to its owner and field.
  The master key lives in `data/secret.key` (mode 600), never in the database.
- Messages that contain secrets (passwords, keys) are deleted from the chat immediately.
- Server host keys are verified (trust on first use, with a loud warning if a key changes).
- Every destination is resolved and checked *before* connecting: loopback, link-local (cloud metadata), private,
  multicast and reserved ranges are refused, and the connection uses exactly the address that was checked.
  Operators can open private ranges deliberately with `ALLOWED_NETS`.
- The container runs as an unprivileged user with a read-only root filesystem, no published ports, no
  new privileges, and memory / CPU / process limits.
- Backups are encrypted with a key derived from your backup password (scrypt).

## What the bot cannot protect you from
- **Whoever controls the machine running the bot can technically decrypt stored credentials** (they hold the
  database *and* the key). Self-host it, or only trust an operator you know.
- **"This server" access gives the Telegram admin account full control of that machine.** Protect that account with
  Telegram two-step verification, and use a non-root user (with passwordless sudo only if you need it) if you prefer.
  Disable it any time with `servermanager host-access disable`.
- Anything typed into the terminal is executed as typed.

## Hardening checklist
- Keep `BACKUP_PASSPHRASE` somewhere safe; store backup files privately.
- Leave `ALLOWED_NETS` empty unless you really need private ranges.
- Keep the bot updated (`servermanager update`).
