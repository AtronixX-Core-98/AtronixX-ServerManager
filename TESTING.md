# Manual test checklist

Automated tests cover the logic; these steps cover what only a real Telegram client and a real server can show.

1. **Install** on a fresh Ubuntu/Debian VPS: `sudo ./install.sh` → the bot answers `/start`.
2. **Terms / modes** – public mode, then subscription mode: a user without a plan is blocked, `/id` works,
   granting a plan unlocks the bot and notifies the user.
3. **Add a server** with a password, then with a key (including one with a passphrase). Confirm the secret message is deleted.
4. **Terminal** – run `top`, `nano`, `less`; use the second key page; long output; `Ctrl+C`; idle timeout warning.
5. **Files** – browse, download (<50 MB), upload (<20 MB), new folder, delete (file, folder, symlink).
6. **Monitor and toolbox** on a Debian and an Alpine/busybox host.
7. **Downtime alerts** – watch a server, block its SSH port, wait for the alert, unblock, wait for "back online".
8. **"This server"** – `servermanager host-access enable`, open it in the bot, confirm a non-admin never sees it,
   then `disable` and confirm the key is gone from `authorized_keys`.
9. **Backup / restore** – manual backup, restore on a second install with the backup password.
10. **Update** – `servermanager update` keeps data and settings.
