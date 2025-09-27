#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_DIR/.venv"
ENV_FILE="$REPO_DIR/.dropbox_mirror.env"
SHORTCUT_LINK="$HOME/.shortcuts/run-sync.sh"
RUN_SH="$REPO_DIR/run-sync.sh"
LOG_FILE="$REPO_DIR/sync_dropbox.log"
ZIP_FILE="$REPO_DIR/dropbox_latest.zip"
TARGET_DIR_DEFAULT="$REPO_DIR/DropboxMirror"

echo "=== Dropbox Mirror Removal ==="
echo "This will remove runtime files created by the setup:"
echo

# Read config to get custom paths if they exist
CUSTOM_TARGET_DIR=""
CUSTOM_LOG_PATH=""
CUSTOM_DOWNLOAD_PATH=""

if [ -f "$ENV_FILE" ]; then
    echo "Reading configuration to find custom paths..."
    
    # Extract custom paths from config
    while IFS='=' read -r key value || [ -n "$key" ]; do
        # Skip comments and empty lines
        [[ $key =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        
        key=$(echo "$key" | tr -d ' ')
        value=$(echo "$value" | tr -d ' ')
        
        case "$key" in
            "TARGET_DIR")
                CUSTOM_TARGET_DIR="$value"
                ;;
            "LOG_PATH")
                CUSTOM_LOG_PATH="$value"
                ;;
            "DOWNLOAD_PATH")
                CUSTOM_DOWNLOAD_PATH="$value"
                ;;
        esac
    done < "$ENV_FILE"
fi

# Function to expand paths like the Python script does
expand_path() {
    local path="$1"
    # Replace ~ with $HOME
    path="${path/#\~/$HOME}"
    # Convert to absolute path
    if [[ "$path" = /* ]]; then
        echo "$path"
    else
        echo "$REPO_DIR/$path"
    fi
}

# Expand custom paths
if [ -n "$CUSTOM_TARGET_DIR" ]; then
    CUSTOM_TARGET_DIR=$(expand_path "$CUSTOM_TARGET_DIR")
fi
if [ -n "$CUSTOM_LOG_PATH" ]; then
    CUSTOM_LOG_PATH=$(expand_path "$CUSTOM_LOG_PATH")
fi
if [ -n "$CUSTOM_DOWNLOAD_PATH" ]; then
    CUSTOM_DOWNLOAD_PATH=$(expand_path "$CUSTOM_DOWNLOAD_PATH")
fi

# Show what will be removed
echo "Files to be removed:"
echo " ✓ Virtual environment: $VENV_DIR"
echo " ✓ Configuration file: $ENV_FILE"
echo " ✓ Run script: $RUN_SH"
echo " ✓ Widget shortcut: $SHORTCUT_LINK"

if [ -f "$LOG_FILE" ]; then
    echo " ✓ Default log file: $LOG_FILE"
fi
if [ -n "$CUSTOM_LOG_PATH" ] && [ "$CUSTOM_LOG_PATH" != "$LOG_FILE" ] && [ -f "$CUSTOM_LOG_PATH" ]; then
    echo " ✓ Custom log file: $CUSTOM_LOG_PATH"
fi

if [ -f "$ZIP_FILE" ]; then
    echo " ✓ Default ZIP file: $ZIP_FILE"
fi
if [ -n "$CUSTOM_DOWNLOAD_PATH" ] && [ "$CUSTOM_DOWNLOAD_PATH" != "$ZIP_FILE" ] && [ -f "$CUSTOM_DOWNLOAD_PATH" ]; then
    echo " ✓ Custom ZIP file: $CUSTOM_DOWNLOAD_PATH"
fi

if [ -d "$TARGET_DIR_DEFAULT" ]; then
    echo " ? Default target folder: $TARGET_DIR_DEFAULT (will ask)"
fi
if [ -n "$CUSTOM_TARGET_DIR" ] && [ "$CUSTOM_TARGET_DIR" != "$TARGET_DIR_DEFAULT" ] && [ -d "$CUSTOM_TARGET_DIR" ]; then
    echo " ? Custom target folder: $CUSTOM_TARGET_DIR (will ask)"
fi

echo
read -p "Continue and remove these files? (type 'yes' to proceed): " ok
if [ "$ok" != "yes" ]; then
    echo "Aborted. Nothing removed."
    exit 0
fi

echo
echo "Removing files..."

# Remove symlink/wrapper
if [ -L "$SHORTCUT_LINK" ]; then
    echo "Removing symlink: $SHORTCUT_LINK"
    rm -f "$SHORTCUT_LINK"
elif [ -f "$SHORTCUT_LINK" ]; then
    if grep -q "sync_dropbox.py\|dropbox.*mirror" "$SHORTCUT_LINK" 2>/dev/null; then
        echo "Removing wrapper: $SHORTCUT_LINK"
        rm -f "$SHORTCUT_LINK"
    else
        echo "Found existing $SHORTCUT_LINK but it doesn't look like ours. Skipping."
    fi
fi

# Remove run script
if [ -f "$RUN_SH" ]; then
    echo "Removing run script: $RUN_SH"
    rm -f "$RUN_SH"
fi

# Remove virtual environment
if [ -d "$VENV_DIR" ]; then
    echo "Removing virtual environment: $VENV_DIR (may take a moment...)"
    rm -rf "$VENV_DIR"
fi

# Remove config file
if [ -f "$ENV_FILE" ]; then
    echo "Removing configuration: $ENV_FILE"
    rm -f "$ENV_FILE"
fi

# Remove log files
if [ -f "$LOG_FILE" ]; then
    echo "Removing default log: $LOG_FILE"
    rm -f "$LOG_FILE"
fi

if [ -n "$CUSTOM_LOG_PATH" ] && [ "$CUSTOM_LOG_PATH" != "$LOG_FILE" ] && [ -f "$CUSTOM_LOG_PATH" ]; then
    echo "Removing custom log: $CUSTOM_LOG_PATH"
    rm -f "$CUSTOM_LOG_PATH"
fi

# Remove ZIP files
if [ -f "$ZIP_FILE" ]; then
    echo "Removing default ZIP: $ZIP_FILE"
    rm -f "$ZIP_FILE"
fi

if [ -n "$CUSTOM_DOWNLOAD_PATH" ] && [ "$CUSTOM_DOWNLOAD_PATH" != "$ZIP_FILE" ] && [ -f "$CUSTOM_DOWNLOAD_PATH" ]; then
    echo "Removing custom ZIP: $CUSTOM_DOWNLOAD_PATH"
    rm -f "$CUSTOM_DOWNLOAD_PATH"
fi

# Handle target directories (ask user)
handle_target_removal() {
    local target_dir="$1"
    local description="$2"
    
    if [ -d "$target_dir" ]; then
        echo
        echo "$description contains your synced files:"
        echo "  Path: $target_dir"
        if [ -d "$target_dir/.old_versions" ]; then
            echo "  (includes .old_versions folder with file history)"
        fi
        echo
        read -p "Remove $description? (yes/NO): " remove_target
        if [ "$remove_target" = "yes" ]; then
            echo "Removing $description: $target_dir"
            rm -rf "$target_dir"
        else
            echo "Keeping $description: $target_dir"
        fi
    fi
}

# Remove target directories
handle_target_removal "$TARGET_DIR_DEFAULT" "default target folder"

if [ -n "$CUSTOM_TARGET_DIR" ] && [ "$CUSTOM_TARGET_DIR" != "$TARGET_DIR_DEFAULT" ]; then
    handle_target_removal "$CUSTOM_TARGET_DIR" "custom target folder"
fi

echo
echo "=== Cleanup Complete ==="
echo "✅ All runtime files have been removed"
echo
echo "Repository folder is still here: $REPO_DIR"
echo "You can:"
echo "  • Remove entire repo:  rm -rf '$REPO_DIR'"
echo "  • Reinstall:          bash setup_termux.sh"
echo "  • Clone fresh:        git pull && bash setup_termux.sh"
echo "=================================="