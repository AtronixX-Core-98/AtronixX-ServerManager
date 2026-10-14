# Changelog

## 1.0.0 — first public release

A ground-up polish of the private pre-release builds. Everything below is relative to those builds.

### New
- **"This server" access** – the admin can open a terminal, browse files, see the monitor and use the toolbox on
  the machine the bot itself runs on. Opt-in (`servermanager host-access enable`): a dedicated ed25519 key that only
  works from the bot's private Docker network, pinned SSH host keys, admin only.
- **Toolbox** – one-tap read-only tools (top processes, disk, ports, Docker, failed services, recent errors, logins,
  pending updates) and a confirmed reboot.
- **Downtime alerts** – 🔔 per server: a TCP check of the SSH port, with "down" and "back up" notifications.
- **Richer monitor** – CPU %, RAM, swap, disk, uptime, load, containers, failed services, top processes.
- **Terminal** – a second page of keys (Ctrl+X/O/A/E/R/U/W/K, Home/End, PgUp/PgDn) for nano, less and readline.
- **Friendly connection errors** – wrong password, refused, timed out, unknown host, changed host key…
- `ALLOWED_NETS` to let users reach private ranges (LAN / VPN); `/id` command; configurable bot name.
- A completely new installer and control panel (`servermanager`): guided install, token validation, health checks
  (`doctor`), safe `update` with automatic backup, `settings`, local `backup`, build-from-source fallback.

### Fixed
- The live terminal message could exceed Telegram's 4096-character limit when the output contained `<`, `>` or `&`,
  which froze the live view.
- Symlinks to files were shown as folders; symlinks to folders now open correctly.
- The domain validator accepted malformed names such as `a..b`.
- Password logins could try keys from the container's home directory.
- Unanswered host-key confirmations kept their SSH connection open forever (now closed after 2 minutes).
- The installer dashboard counters (users, plans…) never worked: the snippet was a Python syntax error.
- Texts promised limits that the code did not enforce (1–365 days vs 3650, 1–100 servers vs 1000).
- Admin notifications ignored the admin's language.

### Changed
- The bot's display name is configurable (`BOT_NAME`) and the operator's support button is optional (`SUPPORT_USERNAME`);
  the project credit (AtronixX-Core) stays in the help page, the main menu, the installer and the docs.
- All texts were rewritten (Persian and English).
- Data created by the pre-release builds (database, encrypted fields, backups) is still readable via
  `core/legacy_v1.py`; delete that file if you never ran one.
