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
   - Create `./run-sync.sh` and link it to `~/.shortcuts/run-sync.sh`

5. **Add Termux:Widget** to your home screen and select `run-sync`. One tap triggers the sync!

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
LOG_PATH=./sync_dropbox.log
VENV_DIR=./.venv
```

**Configuration Options:**

- `DROPBOX_URL` — **Required**. Public Dropbox link, must end with `?dl=1`
- `DOWNLOAD_PATH` — Where to save the downloaded ZIP file (default: repo folder)
- `TARGET_DIR` — Where to sync files to (default: `./DropboxMirror`)
- `KEEP_VERSIONS` — Archive replaced files in `TARGET_DIR/.old_versions` (`yes`/`no`)
- `DRY_RUN` — Simulate changes without writing (`yes`/`no`)
- `LOG_PATH` — Path to log file (default: `./sync_dropbox.log`)
- `VENV_DIR` — Python virtual environment path (default: `./.venv`)

Edit manually: `nano ./.dropbox_mirror.env` or re-run `bash setup_termux.sh`

## How It Works

1. **Download**: Fetches your Dropbox ZIP file using the public link
2. **Extract**: Safely extracts to temporary directory (with path traversal protection)
3. **Compare**: Uses SHA256 hashes to identify new/changed files
4. **Sync**: Copies only new files, updates changed files
5. **Archive**: Optionally keeps old versions in `.old_versions/` folder
6. **Cleanup**: Removes temporary files and ZIP

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

- Use Termux:Tasker for scheduled syncs
- Add multiple Dropbox sources by creating separate repo folders
- Chain with other scripts using the run script

**Monitoring:**

```bash
# Watch live sync
tail -f ./sync_dropbox.log

# Check last sync
tail -20 ./sync_dropbox.log

# View sync history
grep "SUMMARY" ./sync_dropbox.log
```

## Troubleshooting

### Widget doesn't work

- Ensure `~/.shortcuts/run-sync.sh` exists and is executable
- Check Termux:Widget is installed from F-Droid
- Verify config file exists: `./.dropbox_mirror.env`
- Check logs: `tail -f ./sync_dropbox.log`

### Permission errors

```bash
# Re-grant storage permissions
termux-setup-storage
```

### Missing dependencies

```bash
# Recreate environment
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

``` tree
dropbox-zip-mirror-termux/
├── sync_dropbox.py           # Main sync script
├── setup_termux.sh           # Interactive setup
├── remove_installation.sh    # Cleanup script  
├── requirements.txt          # Python dependencies
├── termux_shortcuts/
│   └── run-sync.sh.template  # Widget script template
├── .dropbox_mirror.env       # Config (created by setup)
├── .venv/                    # Python venv (created by setup)
├── sync_dropbox.log          # Log file (created at runtime)
└── DropboxMirror/           # Default sync target (created at runtime)
```

**Key improvements in this version:**

- ✅ Fixed config file path resolution (repo-local first, then home)
- ✅ Non-interactive mode detection for widget usage
- ✅ Proper path traversal protection during ZIP extraction
- ✅ Robust error handling and logging
- ✅ Progress indicators for large downloads
- ✅ Better path expansion (handles `~` and environment variables)
- ✅ Comprehensive setup validation and user feedback

## Security Notes

- ZIP files are safely extracted with path traversal protection
- Only files without `..` in paths are processed
- No elevation of privileges required
- All operations stay within specified directories
- Config file contains no sensitive authentication (uses public Dropbox links)

## Requirements

- **Termux** (Android terminal emulator)
- **Python 3** (`pkg install python`)
- **Git** (`pkg install git`)
- **Termux:Widget** (for one-tap sync)
- **Storage permissions** (`termux-setup-storage`)

## License

MIT License - see `LICENSE` file

## Contributing

Improvements welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Test thoroughly on Termux
4. Submit a pull request with clear description

Keep changes focused and document any behavior modifications.
