#!/data/data/com.termux/files/usr/bin/env bash
set -euo pipefail

# repo-local setup: venv, env, run-sync.sh (in-repo), symlink for Termux widget
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
ENV_FILE="$REPO_DIR/.dropbox_mirror.env"
SHORTCUT_LINK="$HOME/.shortcuts/run-sync.sh"
TEMPLATE="$REPO_DIR/termux_shortcuts/run-sync.sh.template"
RUN_SH="$REPO_DIR/run-sync.sh"
REQ_FILE="$REPO_DIR/requirements.txt"

echo "=== Setup (repo-local mode) ==="
echo "Repo: $REPO_DIR"

# 1) create virtual env inside repo
if [ -d "$VENV_DIR" ]; then
  echo "Found existing venv at $VENV_DIR"
  read -p "Recreate venv and reinstall packages? (y/N): " resp
  if [[ "$resp" =~ ^[Yy]$ ]]; then
    rm -rf "$VENV_DIR"
  fi
fi
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
  echo "Created venv at $VENV_DIR"
fi

# 2) install requirements into venv
echo "Installing requirements into venv..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null 2>&1 || true
"$VENV_DIR/bin/pip" install -r "$REQ_FILE"

# 3) interactive .env inside repo (if missing)
if [ -f "$ENV_FILE" ]; then
  echo "Found existing config: $ENV_FILE"
else
  echo "Creating config $ENV_FILE (interactive)."
  read -p "Dropbox public URL (must end with ?dl=1): " DROPBOX_URL
  if [ -z "$DROPBOX_URL" ]; then
    echo "Dropbox URL is required. Exiting."
    exit 1
  fi
  DEFAULT_DL="$REPO_DIR/dropbox_latest.zip"
  read -p "Local download path for ZIP [$DEFAULT_DL]: " DOWNLOAD_PATH
  DOWNLOAD_PATH="${DOWNLOAD_PATH:-$DEFAULT_DL}"
  DEFAULT_TARGET="$REPO_DIR/DropboxMirror"
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
LOG_PATH=$REPO_DIR/sync_dropbox.log
VENV_DIR=$VENV_DIR
EOF

  echo "Wrote $ENV_FILE"
fi

# 4) render run-sync.sh into repo (executable)
sed "s|__VENV_DIR__|$VENV_DIR|g; s|__SCRIPT_PATH__|$REPO_DIR/sync_dropbox.py|g; s|__LOG_PATH__|$REPO_DIR/sync_dropbox.log|g" "$TEMPLATE" > "$RUN_SH"
chmod +x "$RUN_SH"
echo "Created run script at $RUN_SH"

# 5) create symlink in ~/.shortcuts pointing to repo run script
mkdir -p "$HOME/.shortcuts"
# remove existing link if it's ours
if [ -L "$SHORTCUT_LINK" ] || [ -f "$SHORTCUT_LINK" ]; then
  read -p "Overwrite existing $SHORTCUT_LINK? (y/N): " resp
  if [[ "$resp" =~ ^[Yy]$ ]]; then
    rm -f "$SHORTCUT_LINK"
  else
    echo "Keeping existing $SHORTCUT_LINK"
  fi
fi
ln -s "$RUN_SH" "$SHORTCUT_LINK" || { echo "Could not create symlink. Creating a small wrapper instead."; printf '#!/data/data/com.termux/files/usr/bin/env bash\n'"$VENV_DIR/bin/python $REPO_DIR/sync_dropbox.py >> $REPO_DIR/sync_dropbox.log 2>&1\n" > "$SHORTCUT_LINK"; chmod +x "$SHORTCUT_LINK"; }
echo "Installed shortcut at $SHORTCUT_LINK (symlink or wrapper)"

echo
echo "Done. Use Termux:Widget and select 'run-sync' to trigger."
echo "All runtime files are inside the repo. To remove everything later run ./remove_installation.sh"
echo "To run manually: $RUN_SH"
echo "To edit config: $ENV_FILE"
echo "To uninstall: ./remove_installation.sh"
echo "=============================="