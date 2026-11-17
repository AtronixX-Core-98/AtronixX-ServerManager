# Contributing

Thanks for helping! Bug reports, ideas and pull requests are welcome.

## Development setup
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
sudo apt-get install -y openssh-server shellcheck   # optional: enables the SSH integration tests
python -m pytest -q
```
The suite has three layers: pure unit tests, end-to-end flows through the real handlers with a fake Telegram
(`tests/fake_telegram.py`), and integration tests against a real `sshd` on 127.0.0.1:2222 (skipped when sshd is missing).

## Guidelines
- Keep it small and dependency-light; the bot targets low-RAM servers.
- User-facing text lives in `locales/` (Persian + English). Run `python -m pytest tests/test_strings.py` after editing it.
- Never log or echo secrets. Anything that touches destinations must go through `core/security.py`.
- Shell scripts must pass `shellcheck -S warning`.

## Manual checklist before a release
See [TESTING.md](TESTING.md).
