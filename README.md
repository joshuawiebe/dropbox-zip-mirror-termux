# Dropbox ZIP Mirror (Termux) — simple, widget-triggered

Short: A Termux-based tool that downloads a public Dropbox folder ZIP (`?dl=1`), extracts it, and copies only new or changed files to a target directory. Old local files are not deleted; changed files can optionally be archived. Designed to run with a one-tap Termux:Widget.

## Features

- One-click sync via Termux:Widget (`~/.shortcuts/run-sync.sh`)
- First-time setup through `setup_termux.sh` (creates Python venv, installs requirements, writes `~/.dropbox_mirror.env`)
- Workflow: Download → Extract → Compare (SHA256) → Copy new/changed files → Archive old versions
- Optional dry-run mode (`--dry-run` or set `DRY_RUN=yes` in env)
- Logfile: `~/sync_dropbox.log`
- Simple and robust — no external APIs or tokens required (only public Dropbox link)

## Quick Install (Termux)

1. Install Termux (F-Droid recommended) and open it.

2. Grant storage access:

   ```bash
   termux-setup-storage
    ```

3. Clone this repo into Termux home (or copy files there):

   ```bash
   pkg update
   pkg install git
   git clone https://github.com/YOURNAME/dropbox-zip-mirror-termux.git
   cd dropbox-zip-mirror-termux
   ```

4. Run setup:

   ```bash
   bash setup_termux.sh
   ```

   - Creates Python venv at `~/.dropbox_mirror_venv`
   - Installs `requests` in the venv
   - Prompts for Dropbox URL and local paths (if `.dropbox_mirror.env` is missing)
   - Installs the widget script at `~/.shortcuts/run-sync.sh`

5. Add Termux:Widget to your home screen and select `run-sync`. A single tap triggers the synchronization.

## Run (manual)

- Via widget: Tap on the Termux widget (`run-sync`)

- Directly in Termux (for testing):

  ```bash
  ~/.dropbox_mirror_venv/bin/python ~/sync_dropbox.py
  ```

- Dry run:

  ```bash
  ~/.dropbox_mirror_venv/bin/python ~/sync_dropbox.py --dry-run
  ```

## Config

The file `~/.dropbox_mirror.env` contains:

- `DROPBOX_URL` (required) — public Dropbox link, must end with `?dl=1`
- `DOWNLOAD_PATH` — local path to save the ZIP
- `TARGET_DIR` — directory to store files
- `KEEP_VERSIONS` — `yes` or `no`
- `DRY_RUN` — `yes` or `no`
- `LOG_PATH` — log file path
- `VENV_DIR` — Python virtual environment path (default created by setup)

## Notes & Tips

- Use `~/storage/shared/...` paths to access files in the Android file manager
- Large ZIPs take time — script extracts to a temporary folder; ensure enough space
- Check `~/sync_dropbox.log` for errors or details
- If `termux-notification` is available (Termux:API), the script sends a notification after completion

## License

MIT — see LICENSE

## Contribute

Small fixes or improvements are welcome. Please fork → PR. Thank you!
