<div align="center">

# ServerManager

**Manage your servers over SSH — from Telegram.**
Terminal, files, monitoring and one-tap tools, right inside a chat.

[English](README.md) · [فارسی](README.fa.md)

Made by **AtronixX-Core** · 📢 [@AtronixX_Core](https://t.me/AtronixX_Core) · 💬 [@AtronixX_Support](https://t.me/AtronixX_Support)

</div>

---

## What it does

| | |
|---|---|
| ⚡ **Live terminal** | A real PTY session shown in one message that updates live. Type to send, plus Ctrl+C, Tab, arrows and an editor key page (Ctrl+X/O, Home/End, PgUp/PgDn…) for `nano`, `less`, `htop`. |
| 📁 **Files (SFTP)** | Browse, download (≤ 50 MB), upload (≤ 20 MB), create folders, delete. Symlinks behave as you expect. |
| 📊 **Monitor** | CPU %, RAM, swap, disk, uptime, load, Docker containers, failed services and the hungriest processes. |
| 🧰 **Toolbox** | One-tap read-only tools — top processes, open ports, disk, Docker, failed services, recent errors, logins, pending updates — and a confirmed reboot. |
| 🔔 **Downtime alerts** | Turn on 🔔 for a server and get a message when it stops answering (and when it is back). |
| 🏠 **This server** | Optional, admin-only: manage the machine the bot runs on, with a dedicated key that only works from the bot's Docker network. |
| ⚡ **Saved commands, groups, favorites** | Keep your go-to commands one tap away; organize servers. |
| 💎 **Public or subscription mode** | Run it for yourself, a team, or sell plans: grant days + server limits by Telegram ID, expiry notices, forced channel join, broadcast. |
| 💾 **Encrypted backups** | Automatic encrypted backup to the admin every day; one-file restore on a new server. |
| 🌐 **Persian & English** | Per-user language switch. |

Built to be small: ~100–200 MB RAM, no database server, no open ports (Telegram long polling).

## Install

You need a Linux server (Debian/Ubuntu recommended), root access, a bot token from [@BotFather](https://t.me/BotFather)
and your numeric Telegram ID (a bot like @userinfobot shows it; once installed, `/id` does too).

```bash
sudo bash <(curl -fsSL https://raw.githubusercontent.com/AtronixX-Core-98/AtronixX-ServerManager/main/install.sh)
```

The installer checks your system, installs Docker if needed, validates your token with Telegram, creates a private
`.env`, pulls the image (or builds from source when no image is available), starts the bot and waits until it is
online. When it finishes, open your bot and send `/start`.

From a clone instead: `git clone https://github.com/AtronixX-Core-98/AtronixX-ServerManager && cd AtronixX-ServerManager && sudo ./install.sh`

Unattended: `SM_YES=1 SM_BOT_TOKEN=… SM_ADMIN_ID=… sudo -E ./install.sh` (more: `SM_BRAND`, `SM_SUPPORT`, `SM_BACKUP_PASS`, `SM_HOST_ACCESS=1`).

### The `servermanager` command

After installing, run `sudo servermanager` for the control panel, or:

```
servermanager status          dashboard (state, uptime, users, plans, memory)
servermanager doctor          health checks that explain what is wrong
servermanager logs -f         follow the log
servermanager update          update (backs up your data first)
servermanager settings        change token, admin, name, timezone, allowed networks
servermanager host-access     enable | disable | status | test  — manage THIS server from Telegram
servermanager backup          local tar.gz of data + settings
servermanager import-data D   import settings and data from another install folder
servermanager uninstall
```

## "This server" access

Lets **you, the admin**, open a terminal, browse files, see the monitor and use the toolbox on the machine the bot runs
on — the thing a container normally can't do.

```bash
sudo servermanager host-access enable
```

What it sets up: a dedicated ed25519 key in `data/host_key`; an `authorized_keys` entry limited with
`from="<bot network>",restrict,pty` so the key is useless from anywhere else; a firewall rule for the bot's private
network if `ufw` is active; and the server's SSH host keys pinned in `.env`, so the bot refuses to talk to an impostor.
It is **off by default**, shown **only to the admin**, and you can turn it off any time with `host-access disable`.

> ⚠️ This gives the Telegram admin account full control of the server. Enable Telegram two-step verification.

## Configuration

Everything lives in `/opt/servermanager/.env` (see [`.env.example`](.env.example)). Common options:

| Variable | Meaning |
|---|---|
| `BOT_TOKEN`, `ADMIN_ID` | Required. |
| `BACKUP_PASSPHRASE` | Encrypts backup files (8+ chars). Keep it safe. |
| `BOT_NAME` | Name shown in messages. |
| `SUPPORT_USERNAME` | Shows a "Support" button when set. |
| `MAX_LIVE_SESSIONS`, `IDLE_TIMEOUT_MIN`, `MAX_SESSION_HOURS` | Session limits. |
| `WATCH_INTERVAL_MIN`, `MAX_WATCH_PER_USER` | Downtime alert checks. |
| `BLOCKED_IPS` | Addresses users may never connect to (the installer adds this server's public IPs). |
| `ALLOWED_NETS` | Private CIDRs users **may** reach (LAN/VPN), e.g. `10.8.0.0/24,100.64.0.0/10`. |

By default users can only connect to **public** addresses; loopback, link-local (cloud metadata), private and
reserved ranges are refused.

## Modes

The admin panel (👑) switches between **public mode** (everyone not banned can use it) and **subscription mode**
(a plan is required). Grant a plan with the user's numeric ID, days and a server limit; users are warned 3 days and
1 day before expiry, and their data is kept after it ends.

## Backups and moving servers

A backup is one encrypted `.smbak` file (database + master key), sent to the admin automatically. To restore on a new
server: install, then send the file to the bot in **Admin → Backup & restore → Restore** and enter the backup password.

## Upgrading from a pre-release build

Install this version next to the old one or in place and run `servermanager import-data /path/to/old/install`. Existing
databases, encrypted credentials and backups keep working (`core/legacy_v1.py`; delete it if you never ran a pre-release build).

## Security

See [SECURITY.md](SECURITY.md). In short: AES-256-GCM for secrets, secret messages auto-deleted, host-key verification,
SSRF-safe destination checks, unprivileged read-only container — and the honest limit: whoever controls the server the
bot runs on can technically read stored credentials.

## Development

```bash
pip install -r requirements-dev.txt && python -m pytest -q
```
See [CONTRIBUTING.md](CONTRIBUTING.md). Forking? Point everything at your repository with `./scripts/set-repo.sh you/repo` (the project credit stays).

## Credits and support

Created and maintained by **[AtronixX-Core](https://github.com/AtronixX-Core)**.
News and releases: [@AtronixX_Core](https://t.me/AtronixX_Core) · Help: [@AtronixX_Support](https://t.me/AtronixX_Support)

> `SUPPORT_USERNAME` in `.env` is the support contact for **your** bot's users. The credits above are for the project itself.

## License

MIT — see [LICENSE](LICENSE). Please keep the copyright notice and the credit link in the bot when you fork it.
