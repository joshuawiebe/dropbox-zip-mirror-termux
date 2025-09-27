#!/data/data/com.termux/files/usr/bin/env bash
set -euo pipefail

# setup_termux.sh
# Usage: run this in Termux inside the repo folder: bash setup_termux.sh
# Creates a venv, installs requirements, writes ~/.dropbox_mirror.env if missing,
# copies widget script to ~/.shortcuts/run-sync.sh (ready for Termux:Widget).

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$HOME/.dropbox_mirror_venv"
ENV_FILE="$HOME/.dropbox_mirror.env"
SHORTCUT_DIR="$HOME/.shortcuts"
TEMPLATE="$REPO_DIR/termux_shortcuts/run-sync.sh.template"
TARGET_SHORTCUT="$SHORTCUT_DIR/run-sync.sh"
REQ_FILE="$REPO_DIR/requirements.txt"
SCRIPT_PATH="$HOME/sync_dropbox.py"

echo "=== Dropbox ZIP Mirror — setup (Termux) ==="

# 1) copy main script to home (if not yet)
if [ -f "$SCRIPT_PATH" ]; then
  echo "Found existing $SCRIPT_PATH"
  read -p "Overwrite existing sync_dropbox.py? (y/N): " resp
  if [[ "$resp" =~ ^[Yy]$ ]]; then
    cp -f "$REPO_DIR/sync_dropbox.py" "$SCRIPT_PATH"
    echo "Overwritten $SCRIPT_PATH"
  else
    echo "Keeping existing $SCRIPT_PATH"
  fi
else
  cp "$REPO_DIR/sync_dropbox.py" "$SCRIPT_PATH"
  echo "Copied sync_dropbox.py -> $SCRIPT_PATH"
fi

# 2) ensure python exists
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python3 not found in PATH. Install via: pkg install python"
  exit 1
fi

# 3) create venv
if [ -d "$VENV_DIR" ]; then
  echo "Found existing venv at $VENV_DIR"
  read -p "Recreate venv and reinstall packages? (y/N): " resp
  if [[ "$resp" =~ ^[Yy]$ ]]; then
    rm -rf "$VENV_DIR"
  fi
fi
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating venv at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# 4) install requirements inside venv
echo "Installing requirements into venv..."
# upgrade pip quietly
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null 2>&1 || true
"$VENV_DIR/bin/pip" install -r "$REQ_FILE"

# 5) create config env if missing
if [ -f "$ENV_FILE" ]; then
  echo "Found config $ENV_FILE"
else
  echo "Creating config $ENV_FILE (interactive)."
  read -p "Dropbox public URL (must end with ?dl=1): " DROPBOX_URL
  if [ -z "$DROPBOX_URL" ]; then
    echo "Dropbox URL is required. Exiting."
    exit 1
  fi
  DEFAULT_DL="$HOME/storage/shared/Download/dropbox_latest.zip"
  read -p "Local download path for ZIP [$DEFAULT_DL]: " DOWNLOAD_PATH
  DOWNLOAD_PATH="${DOWNLOAD_PATH:-$DEFAULT_DL}"
  DEFAULT_TARGET="$HOME/storage/shared/DropboxMirror"
  read -p "Target folder to store files [$DEFAULT_TARGET]: " TARGET_DIR
  TARGET_DIR="${TARGET_DIR:-$DEFAULT_TARGET}"
  read -p "Keep old versions when overwriting? (yes/no) [yes]: " KEEP_V
  KEEP_V="${KEEP_V:-yes}"
  read -p "Enable dry-run by default? (no = actually write) (yes/no) [no]: " DRY
  DRY="${DRY:-no}"

  cat > "$ENV_FILE" <<EOF
DROPBOX_URL=$DROPBOX_URL
DOWNLOAD_PATH=$DOWNLOAD_PATH
TARGET_DIR=$TARGET_DIR
KEEP_VERSIONS=$KEEP_V
DRY_RUN=$DRY
LOG_PATH=$HOME/sync_dropbox.log
VENV_DIR=$VENV_DIR
EOF

  echo "Wrote $ENV_FILE"
fi

# 6) install termux widget script
mkdir -p "$SHORTCUT_DIR"
if [ -f "$TARGET_SHORTCUT" ]; then
  echo "Found existing widget script $TARGET_SHORTCUT"
  read -p "Overwrite widget script? (y/N): " resp
  if [[ "$resp" =~ ^[Yy]$ ]]; then
    sed "s|__VENV_DIR__|$VENV_DIR|g; s|__SCRIPT_PATH__|$SCRIPT_PATH|g" "$TEMPLATE" > "$TARGET_SHORTCUT"
    chmod +x "$TARGET_SHORTCUT"
    echo "Overwrote widget script."
  else
    echo "Keeping existing widget script."
  fi
else
  sed "s|__VENV_DIR__|$VENV_DIR|g; s|__SCRIPT_PATH__|$SCRIPT_PATH|g" "$TEMPLATE" > "$TARGET_SHORTCUT"
  chmod +x "$TARGET_SHORTCUT"
  echo "Installed widget script to $TARGET_SHORTCUT"
fi

echo
echo "Setup finished."
echo "Run now (test): $VENV_DIR/bin/python $SCRIPT_PATH"
echo "Add Termux:Widget to your home screen and choose 'run-sync' to run by tap."
echo "Log file (if enabled) is at: $HOME/sync_dropbox.log"
echo "Edit config at: $ENV_FILE"
echo "============================================"