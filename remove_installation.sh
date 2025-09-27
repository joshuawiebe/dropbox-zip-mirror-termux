#!/data/data/com.termux/files/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
ENV_FILE="$REPO_DIR/.dropbox_mirror.env"
SHORTCUT_LINK="$HOME/.shortcuts/run-sync.sh"
RUN_SH="$REPO_DIR/run-sync.sh"
LOG_FILE="$REPO_DIR/sync_dropbox.log"
ZIP_FILE="$REPO_DIR/dropbox_latest.zip"
TARGET_DIR_DEFAULT="$REPO_DIR/DropboxMirror"

echo "This will remove runtime files created by the repo:"
echo " - venv: $VENV_DIR"
echo " - env: $ENV_FILE"
echo " - log: $LOG_FILE"
echo " - zip: $ZIP_FILE"
echo " - repo run script: $RUN_SH"
echo " - shortcut link: $SHORTCUT_LINK"
echo " - default target folder: $TARGET_DIR_DEFAULT"
read -p "Continue and remove these files? (type 'yes' to proceed): " ok
if [ "$ok" != "yes" ]; then
  echo "Abort. Nothing removed."
  exit 0
fi

# remove symlink/wrapper if it points to our run script or wrapper
if [ -L "$SHORTCUT_LINK" ]; then
  echo "Removing symlink $SHORTCUT_LINK"
  rm -f "$SHORTCUT_LINK"
elif [ -f "$SHORTCUT_LINK" ]; then
  # could be wrapper file created earlier; check content for repo path
  if grep -q "sync_dropbox.py" "$SHORTCUT_LINK" ; then
    echo "Removing wrapper $SHORTCUT_LINK"
    rm -f "$SHORTCUT_LINK"
  else
    echo "Found existing $SHORTCUT_LINK but it doesn't look like ours. Skipping."
  fi
fi

# remove run script if created
if [ -f "$RUN_SH" ]; then
  echo "Removing $RUN_SH"
  rm -f "$RUN_SH"
fi

# remove venv
if [ -d "$VENV_DIR" ]; then
  echo "Removing venv $VENV_DIR (this may take a while)"
  rm -rf "$VENV_DIR"
fi

# remove env, log, zip
[ -f "$ENV_FILE" ] && { echo "Removing $ENV_FILE"; rm -f "$ENV_FILE"; }
[ -f "$LOG_FILE" ] && { echo "Removing $LOG_FILE"; rm -f "$LOG_FILE"; }
[ -f "$ZIP_FILE" ] && { echo "Removing $ZIP_FILE"; rm -f "$ZIP_FILE"; }

# prompt to remove target folder (mirror) - BE CAREFUL
if [ -d "$TARGET_DIR_DEFAULT" ]; then
  read -p "Remove default target mirror folder $TARGET_DIR_DEFAULT? (yes/NO): " remt
  if [ "$remt" = "yes" ]; then
    rm -rf "$TARGET_DIR_DEFAULT"
    echo "Removed target folder."
  else
    echo "Kept target folder."
  fi
fi

echo "Cleanup finished."
echo "You can now remove the repo folder if you want: $REPO_DIR"
echo "==============================="
echo "To reinstall, clone the repo again and run setup.sh"
echo "==============================="