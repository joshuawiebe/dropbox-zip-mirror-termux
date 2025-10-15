# Dropbox ZIP Mirror (Termux) — simple, widget-triggered

A Termux-based tool that downloads a public Dropbox folder ZIP (`?dl=1`), extracts it, and copies only new or changed files to a target directory. Old local files are preserved; changed files can optionally be archived. The whole runtime lives inside the repo (venv, config, logs). Trigger with one tap using Termux:Widget.

## Features

- **One-click sync** via Termux:Widget (`~/.shortcuts/run-sync.sh`)
- **Repo-local install**: venv, env, logs and mirror live inside the repository
- **Smart setup**: `setup_termux.sh` creates everything needed with interactive configuration
- **Efficient sync**: Download → Extract → Compare (SHA256) → Copy new/changed → Archive old versions
- **Safe operation**: Dry-run mode, path traversal protection, error handling
- **Simple cleanup**: `remove_installation.sh` removes all runtime artifacts
- **Minimal dependencies**: Python + `requests` library only
- **Real-time feedback**: Prints live progress messages for major steps, both in Termux and log file

## Quick Install (Termux)

1. **Install Termux** (F-Droid recommended) and open it.

2. **Grant storage access**:

   ```bash
   termux-setup-storage
   ```

3. **Install dependencies and clone repo**:

   ```bash
   pkg update
   pkg install git python
   git clone https://github.com/joshuawiebe/dropbox-zip-mirror-termux.git
   cd dropbox-zip-mirror-termux
   ```

4. **Run setup** (interactive):

   ```bash
   bash setup_termux.sh
   ```

   This will:

   - Create Python venv at `./.venv`
   - Install `requests` into the venv
   - Interactively configure `./.dropbox_mirror.env`
   - Ask if you want a **widget** or **job scheduler**
   - Create `./run-sync.sh` and link it to `~/.shortcuts/run-sync.sh` (if widget selected)

5. **Add Termux:Widget** to your home screen and select `run-sync`. One tap triggers the sync!
   You can **watch output live** even from the widget since major progress steps are printed immediately.

## Manual Usage

- **Widget**: Tap the Termux widget (`run-sync`)
- **Command line**: `./run-sync.sh` or `./.venv/bin/python ./sync_dropbox.py`
- **Dry run**: `./.venv/bin/python ./sync_dropbox.py --dry-run`

## Configuration

Setup creates: `./.dropbox_mirror.env`

Example configuration:

```env
DROPBOX_URL=https://www.dropbox.com/s/XXXXX/yourfolder.zip?dl=1
DOWNLOAD_PATH=./dropbox_latest.zip
TARGET_DIR=./DropboxMirror
KEEP_VERSIONS=yes
DRY_RUN=no
LOG_PATH=./sync.log
VENV_DIR=./.venv
```

**Configuration Options:**

- `DROPBOX_URL` — **Required**. Public Dropbox link, must end with `?dl=1`
- `DOWNLOAD_PATH` — Where to save the downloaded ZIP file (default: repo folder)
- `TARGET_DIR` — Where to sync files to (default: `./DropboxMirror`)
- `KEEP_VERSIONS` — Archive replaced files in `TARGET_DIR/.old_versions` (`yes`/`no`)
- `DRY_RUN` — Simulate changes without writing (`yes`/`no`)
- `LOG_PATH` — Path to log file (default: `./sync.log`)
- `VENV_DIR` — Python virtual environment path (default: `./.venv`)

Edit manually: `nano ./.dropbox_mirror.env` or re-run `bash setup_termux.sh`

## How It Works

1. **Downloading…** Fetches your Dropbox ZIP file
2. **Extracting…** Safely extracts to a temporary directory (with path traversal protection)
3. **Comparing…** Uses SHA256 hashes to identify new/changed files
4. **Syncing…** Copies new files, updates changed files, archives old versions if configured
   Progress counters like `Copied 4/25 files…` appear live
5. **Done ✅** Cleans up temporary files and ZIP
   All major steps are printed **immediately** for real-time feedback, even from the widget

## Uninstall

Remove all runtime artifacts (keeps your synced files):

```bash
./remove_installation.sh
```

## Advanced Usage

**Different sync locations:**

- Repo folder: `TARGET_DIR=./DropboxMirror` (default)
- External storage: `TARGET_DIR=~/storage/shared/Documents/MyDropbox`
- SD card: `TARGET_DIR=/storage/XXXX-XXXX/DropboxMirror`

**Automation:**

- Use Termux:Tasker or Job Scheduler for periodic syncs
- Multiple Dropbox sources can be handled by creating separate repo folders
- Chain with other scripts using the run script

**Monitoring:**

```bash
# Watch live sync
tail -f ./sync.log

# Check last sync
tail -20 ./sync.log

# View sync history
grep "SUMMARY" ./sync.log
```

## Troubleshooting

### Widget doesn't work

- Ensure `~/.shortcuts/run-sync.sh` exists and is executable
- Check Termux:Widget is installed from F-Droid
- Verify config file exists: `./.dropbox_mirror.env`
- Check logs: `tail -f ./sync.log`

### Permission errors

```bash
termux-setup-storage
```

### Missing dependencies

```bash
./remove_installation.sh
bash setup_termux.sh
```

### Sync issues

- Verify Dropbox URL ends with `?dl=1`
- Check available storage space
- Test with dry run: `./.venv/bin/python ./sync_dropbox.py --dry-run`
- Check network connectivity

### Common error messages

- `"No config found and running non-interactively"` → Config file missing/unreadable
- `"Download failed"` → Network issue or invalid Dropbox URL
- `"Extraction failed"` → Corrupted ZIP or storage full
- `"ERROR: Could not create directories"` → Permission issues

## Development

**File structure:**

```text
dropbox-zip-mirror-termux/
├── sync_dropbox.py           # Main sync script
├── setup_termux.sh           # Interactive setup
├── remove_installation.sh    # Cleanup script  
├── requirements.txt          # Python dependencies
├── termux_shortcuts/
│   └── run-sync.sh.template  # Widget script template
├── .dropbox_mirror.env       # Config (created by setup)
├── .venv/                    # Python venv (created by setup)
├── sync.log                  # Log file (created at runtime)
└── DropboxMirror/            # Default sync target (created at runtime)
```

**Key improvements in this version:**

- ✅ Real-time progress output for major steps
- ✅ Config path resolution (repo-local first, then home)
- ✅ Non-interactive mode detection for widget usage
- ✅ Safe ZIP extraction (path traversal protection)
- ✅ SHA256 comparison + optional archiving
- ✅ Robust error handling and logging
- ✅ Progress counters for multiple files

## Security Notes

- ZIP files are safely extracted with path traversal protection
- Only files without `..` in paths are processed
- No elevation of privileges required
- All operations stay within specified directories
- Config file contains no sensitive authentication (uses public Dropbox links)

## Requirements

- Termux (Android)
- Python 3 (`pkg install python`)
- Git (`pkg install git`)
- Termux:Widget (optional)
- Storage permissions (`termux-setup-storage`)

## License

MIT License - see `LICENSE` file

## Contributing

1. Fork the repository
2. Create a feature branch
3. Test thoroughly on Termux
4. Submit a pull request with clear description
