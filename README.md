# Dropbox ZIP Mirror (Termux) — simple, widget-triggered

Short: A Termux-based tool that downloads a public Dropbox folder ZIP (`?dl=1`), extracts it, and copies only new or changed files to a target directory. Old local files are preserved; changed files can optionally be archived. The whole runtime lives inside the repo (venv, config, logs). Trigger with one tap using Termux:Widget.

## Features

- One-click sync via Termux:Widget (`~/.shortcuts/run-sync.sh`)
- Repo-local install: venv, env, logs and mirror live inside the repository
- First-run setup via `setup_termux.sh` (creates `.venv`, installs requirements, writes `.dropbox_mirror.env`)
- Workflow: Download → Extract → Compare (SHA256) → Copy new/changed → Archive old versions
- Dry-run mode (`--dry-run` or `DRY_RUN=yes` in env) for safe testing
- Simple uninstall via `remove_installation.sh` (removes repo runtime artifacts)
- Minimal external deps: Python + `requests`

## Quick install (Termux)

1. Install Termux (F-Droid recommended) and open it.

2. Grant storage access:

   ```bash
   termux-setup-storage
   ```

3. Clone the repo into Termux home (or copy files there):

   ```bash
   pkg update
   pkg install git
   git clone https://github.com/YOURNAME/dropbox-zip-mirror-termux.git
   cd dropbox-zip-mirror-termux
   ```

4. Run setup (repo-local mode):

   ```bash
   bash setup_termux.sh
   ```

   - Creates a Python venv at `./.venv` (inside the repo)
   - Installs `requests` into the venv
   - Interactively writes `./.dropbox_mirror.env` (if missing)
   - Renders `./run-sync.sh` and creates a symlink or wrapper at `~/.shortcuts/run-sync.sh` for the widget

5. Add Termux:Widget to your home screen and select `run-sync`. A single tap triggers the sync.

## Run (manual)

- Via widget: Tap the Termux widget (`run-sync`).

- From Termux (test run):

  ```bash
  ./.venv/bin/python ./sync_dropbox.py
  ```

- Dry run:

  ```bash
  ./.venv/bin/python ./sync_dropbox.py --dry-run
  ```

## Configuration

Default config file (created by setup): `./.dropbox_mirror.env`

Example entries:

``` .env
DROPBOX_URL=https://www.dropbox.com/s/XXXXX/yourfolder.zip?dl=1
DOWNLOAD_PATH=./dropbox_latest.zip
TARGET_DIR=./DropboxMirror
KEEP_VERSIONS=yes
DRY_RUN=no
LOG_PATH=./sync_dropbox.log
VENV_DIR=./.venv
```

- `DROPBOX_URL` — required, must end with `?dl=1`
- `DOWNLOAD_PATH` — where the ZIP will be saved (repo default)
- `TARGET_DIR` — where files are copied (repo default)
- `KEEP_VERSIONS` — `yes` to archive replaced files in `TARGET_DIR/.old_versions`
- `DRY_RUN` — `yes` to simulate changes without writing
- `LOG_PATH` — path to log file (repo default)
- `VENV_DIR` — python venv path (repo default `./.venv`)

Edit `./.dropbox_mirror.env` manually or re-run `bash setup_termux.sh` to regenerate.

## Uninstall / clean

If you want to remove all runtime artifacts produced by setup (venv, env, logs, symlink), run:

```bash
./remove_installation.sh
```

The script prompts before deleting and will keep your mirrored `TARGET_DIR` unless you explicitly confirm removal.

## Notes & tips

- Use `./DropboxMirror` (repo default) if you want mirrored files inside the repo. If you prefer external storage, set `TARGET_DIR` to a path under `~/storage/shared/...`.
- The script extracts the ZIP into a temporary folder and streams file hashes to avoid excessive memory use.
- Large ZIPs require storage space for extraction—ensure enough free space.
- Check `./sync_dropbox.log` for operation details and errors.
- If `termux-notification` (Termux:API) is installed, the script sends a completion notification.

## Troubleshooting

- **Permission errors writing to `/sdcard`** — run `termux-setup-storage` and re-grant permissions in Android.
- **Missing `requests`** — run `bash setup_termux.sh` to recreate the venv and install dependencies.
- **Widget doesn't show `run-sync`** — ensure `~/.shortcuts/run-sync.sh` exists and is executable; remove and re-run `setup_termux.sh` if needed.

## License

MIT — see `LICENSE`.

## Contributing

Small improvements and fixes welcome. Fork → PR. Keep changes focused and document behavior changes in PR descriptions. Thank you!
