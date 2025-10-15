#!/usr/bin/env bash
set -euo pipefail

# repo-local setup: venv, env, run-sync.sh (in-repo), symlink for Termux widget
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
VENV_DIR="$REPO_DIR/.venv"
ENV_FILE="$REPO_DIR/.dropbox_mirror.env"
SHORTCUT_LINK="$HOME/.shortcuts/run-sync.sh"
JOB_SHORTCUT_LINK="$HOME/.shortcuts/run-sync.job.sh"
TEMPLATE="$REPO_DIR/termux_shortcuts/run-sync.sh.template"
RUN_SH="$REPO_DIR/run-sync.sh"
REQ_FILE="$REPO_DIR/requirements.txt"

echo "=== Dropbox Mirror Setup (repo-local mode) ==="
echo "Repository: $REPO_DIR"
echo

# Check if running in Termux
if [[ ! "${PREFIX:-}" == *"com.termux"* ]]; then
    echo "⚠️  Warning: This script is designed for Termux. Some features may not work correctly."
    read -p "Continue anyway? (y/N): " resp
    if [[ ! "$resp" =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

# 1) Create virtual environment inside repo
echo "[1/6] Setting up Python virtual environment..."
if [ -d "$VENV_DIR" ]; then
    echo "Found existing virtual environment at: $VENV_DIR"
    read -p "Recreate virtual environment and reinstall packages? (y/N): " resp
    if [[ "$resp" =~ ^[Yy]$ ]]; then
        echo "Removing existing virtual environment..."
        rm -rf "$VENV_DIR"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    if ! command -v python3 >/dev/null 2>&1; then
        echo "❌ ERROR: python3 not found. Install it with: pkg install python"
        exit 1
    fi

    echo "Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✅ Virtual environment created at: $VENV_DIR"
fi

# 2) Install requirements into virtual environment
echo "[2/6] Installing Python dependencies..."
if [ ! -f "$REQ_FILE" ]; then
    echo "❌ ERROR: requirements.txt not found at: $REQ_FILE"
    exit 1
fi

echo "Upgrading pip..."
if ! "$VENV_DIR/bin/python" -m pip install --upgrade pip --quiet; then
    echo "⚠️  Warning: pip upgrade failed, continuing anyway..."
fi

echo "Installing requirements from: $REQ_FILE"
if ! "$VENV_DIR/bin/pip" install -r "$REQ_FILE" --quiet; then
    echo "❌ ERROR: Failed to install Python dependencies"
    echo "Try running: $VENV_DIR/bin/pip install -r $REQ_FILE"
    exit 1
fi
echo "✅ Dependencies installed successfully"

# 3) Interactive configuration inside repo (if missing)
echo "[3/6] Setting up configuration..."
if [ -f "$ENV_FILE" ]; then
    echo "Found existing configuration: $ENV_FILE"
    read -p "Recreate configuration file? (y/N): " resp
    if [[ ! "$resp" =~ ^[Yy]$ ]]; then
        echo "Using existing configuration"
    else
        rm -f "$ENV_FILE"
    fi
fi

if [ ! -f "$ENV_FILE" ]; then
    echo
    echo "🔧 Interactive Configuration Setup"
    echo "Creating configuration file: $ENV_FILE"
    echo

    # Helper: sanitize input to remove ANSI escape sequences and ESC char (\033)
    sanitize_input() {
        local in="$1"
        if command -v perl >/dev/null 2>&1; then
            # perl-based ANSI stripper (robust)
            printf "%s" "$in" | perl -pe 's/\e\[[\d;]*[A-Za-z]//g; s/\r//g'
        else
            # fallback: remove ESC (0x1B) bytes and CR
            printf "%s" "$in" | tr -d '\033' | tr -d '\r'
        fi
    }

    # Get Dropbox URL and normalize to ?dl=1
    while true; do
        read -p "Dropbox public URL: " DROPBOX_URL_RAW
        DROPBOX_URL="$(sanitize_input "$DROPBOX_URL_RAW")"
        if [ -z "$DROPBOX_URL" ]; then
            echo "❌ ERROR: Dropbox URL is required"
            continue
        fi

        if [[ "$DROPBOX_URL" != *"dropbox.com"* ]]; then
            echo "❌ ERROR: Not a Dropbox URL"
            continue
        fi

        # Remove existing dl=[01] params robustly
        DROPBOX_URL="$(printf "%s" "$DROPBOX_URL" | sed -E 's/(\?|\&)+dl=[01]//g')"
        DROPBOX_URL="${DROPBOX_URL%%&}"    # trim trailing &
        DROPBOX_URL="${DROPBOX_URL%%\?}"   # trim trailing ?
        # Add dl=1
        if [[ "$DROPBOX_URL" == *\?* ]]; then
            DROPBOX_URL="${DROPBOX_URL}&dl=1"
        else
            DROPBOX_URL="${DROPBOX_URL}?dl=1"
        fi

        echo "✅ Using Dropbox URL: $DROPBOX_URL"
        break
    done

    # Get download path
    DEFAULT_DL="$REPO_DIR/dropbox_latest.zip"
    read -p "Local download path for ZIP [$DEFAULT_DL]: " DOWNLOAD_PATH
    DOWNLOAD_PATH="${DOWNLOAD_PATH:-$DEFAULT_DL}"
    DOWNLOAD_PATH="$(sanitize_input "$DOWNLOAD_PATH")"

    # Get target directory
    DEFAULT_TARGET="$REPO_DIR/DropboxMirror"
    echo
    echo "Target directory options:"
    echo "  • Repo folder (default): $DEFAULT_TARGET"
    echo "  • External storage: ~/storage/shared/Documents/MyDropbox"
    echo "  • Custom path: /path/to/your/folder"
    read -p "Target folder to store synced files [$DEFAULT_TARGET]: " TARGET_DIR
    TARGET_DIR="${TARGET_DIR:-$DEFAULT_TARGET}"
    TARGET_DIR="$(sanitize_input "$TARGET_DIR")"

    # Get other settings
    read -p "Keep old file versions when overwriting? (yes/no) [yes]: " KEEP_V
    KEEP_V="${KEEP_V:-yes}"
    KEEP_V="$(sanitize_input "$KEEP_V")"

    read -p "Enable dry-run mode by default? (yes/no) [no]: " DRY
    DRY="${DRY:-no}"
    DRY="$(sanitize_input "$DRY")"

    # Optional: Custom log path
    DEFAULT_LOG="$REPO_DIR/sync.log"
    read -p "Log file path [$DEFAULT_LOG]: " LOG_PATH
    LOG_PATH="${LOG_PATH:-$DEFAULT_LOG}"
    LOG_PATH="$(sanitize_input "$LOG_PATH")"

    # Accept user choice: widget (default) or job scheduler or both
    echo
    echo "Automation options:"
    echo "  1) Create Termux:Widget shortcut (recommended — one-tap)"
    echo "  2) Create job wrapper script for Termux Job Scheduler (F-Droid Termux)"
    echo "  3) Create both (widget + job wrapper)"
    echo "  4) None"
    read -p "Choose automation option [1]: " AUTO_CHOICE
    AUTO_CHOICE="${AUTO_CHOICE:-1}"
    case "$AUTO_CHOICE" in
        1) CREATE_WIDGET=yes; CREATE_JOB=no ;;
        2) CREATE_WIDGET=no; CREATE_JOB=yes ;;
        3) CREATE_WIDGET=yes; CREATE_JOB=yes ;;
        *) CREATE_WIDGET=no; CREATE_JOB=no ;;
    esac

    # Convert yes/no to normalized values
    DRY_NUM=0
    if [[ "$DRY" =~ ^[Yy][Ee]?[Ss]?$ ]] || [[ "$DRY" =~ ^[1]$ ]]; then
        DRY_NUM=1
    fi

    # Write configuration file (values already sanitized)
    cat > "$ENV_FILE" <<EOF
# Dropbox Mirror Configuration
# Generated by setup_termux.sh on $(date)
DROPBOX_URL=$DROPBOX_URL
DOWNLOAD_PATH=$DOWNLOAD_PATH
TARGET_DIR=$TARGET_DIR
KEEP_VERSIONS=$KEEP_V
DRY_RUN=$DRY_NUM
LOG_PATH=$LOG_PATH
VENV_DIR=$VENV_DIR
EOF

    echo
    echo "✅ Configuration written to: $ENV_FILE"
    echo
fi

# 4) Create run script from template
echo "[4/6] Creating run script..."
if [ ! -f "$TEMPLATE" ]; then
    echo "❌ ERROR: Template not found at: $TEMPLATE"
    exit 1
fi

# Render template with actual paths (template uses LOG_PATH from env file)
sed "s|__VENV_DIR__|$VENV_DIR|g; s|__SCRIPT_PATH__|$REPO_DIR/sync_dropbox.py|g; s|__LOG_PATH__|$LOG_PATH|g" "$TEMPLATE" > "$RUN_SH"
chmod +x "$RUN_SH"
echo "✅ Created executable run script: $RUN_SH"

# 5) Create Termux widget shortcut (if requested)
echo "[5/6] Setting up Termux widget shortcut (if requested)..."
mkdir -p "$HOME/.shortcuts"

if [[ "${CREATE_WIDGET:-yes}" == "yes" ]]; then
    # Handle existing shortcut
    if [ -L "$SHORTCUT_LINK" ] || [ -f "$SHORTCUT_LINK" ]; then
        echo "Found existing shortcut: $SHORTCUT_LINK"
        read -p "Overwrite existing widget shortcut? (y/N): " resp
        if [[ "$resp" =~ ^[Yy]$ ]]; then
            rm -f "$SHORTCUT_LINK"
        else
            echo "Keeping existing shortcut"
            echo "⚠️  Setup completed but widget shortcut not updated"
        fi
    fi

    # Try to create symlink to run script for widget; fallback to simple wrapper that appends to log
    if [ ! -e "$SHORTCUT_LINK" ]; then
        if ln -s "$RUN_SH" "$SHORTCUT_LINK" 2>/dev/null; then
            echo "✅ Created widget symlink: $SHORTCUT_LINK"
        else
            echo "Creating wrapper script for widget..."
            cat > "$SHORTCUT_LINK" <<EOF
#!/usr/bin/env bash
# Termux widget wrapper for Dropbox Mirror
export TERMUX_WIDGET=1
cd "$REPO_DIR" || exit 1
"$VENV_DIR/bin/python" "$REPO_DIR/sync_dropbox.py" >> "$LOG_PATH" 2>&1
EOF
            chmod +x "$SHORTCUT_LINK"
            echo "✅ Created widget wrapper: $SHORTCUT_LINK"
        fi
    fi
else
    echo "Skipping widget shortcut creation (user chose not to create it)."
fi

# 6) Create a job wrapper (for termux-job-scheduler) if requested
echo "[6/6] Creating job wrapper script (if requested)..."
if [[ "${CREATE_JOB:-no}" == "yes" ]]; then
    if [ -f "$JOB_SHORTCUT_LINK" ]; then
        echo "Found existing job wrapper: $JOB_SHORTCUT_LINK"
        read -p "Overwrite existing job wrapper? (y/N): " resp
        if [[ "$resp" =~ ^[Yy]$ ]]; then
            rm -f "$JOB_SHORTCUT_LINK"
        else
            echo "Keeping existing job wrapper"
        fi
    fi

    cat > "$JOB_SHORTCUT_LINK" <<'EOF'
#!/usr/bin/env bash
# Termux job wrapper for Dropbox Mirror (suitable for termux-job-scheduler)
# This wrapper is intended to be scheduled via `termux-job-scheduler` (F-Droid termux).
# It writes output to the configured log file and exits with appropriate status.
export TERMUX_JOB_WRAPPER=1
REPO_DIR="__REPO_DIR__"
VENV_DIR="__VENV_DIR__"
LOG_PATH="__LOG_PATH__"

cd "$REPO_DIR" || exit 1
"$VENV_DIR/bin/python" "$REPO_DIR/sync_dropbox.py" >> "$LOG_PATH" 2>&1
EOF

    # substitute variables
    sed -i "s|__REPO_DIR__|$REPO_DIR|g; s|__VENV_DIR__|$VENV_DIR|g; s|__LOG_PATH__|$LOG_PATH|g" "$JOB_SHORTCUT_LINK"
    chmod +x "$JOB_SHORTCUT_LINK"
    echo "✅ Created job wrapper script: $JOB_SHORTCUT_LINK"

    # If termux-job-scheduler is installed, print instructions (do NOT attempt to schedule automatically)
    if command -v termux-job-scheduler >/dev/null 2>&1; then
        echo
        echo "termux-job-scheduler appears to be installed on this system."
        echo "You can schedule the job wrapper with a command like (example):"
        echo
        echo "  termux-job-scheduler --periodic --component='$JOB_SHORTCUT_LINK' --period=3600"
        echo
        echo "Exact scheduling flags depend on your Termux version. We did NOT schedule the job automatically."
    else
        echo
        echo "Note: termux-job-scheduler not found. Job wrapper was created but you must register it manually."
    fi
else
    echo "Skipping job wrapper creation (user chose not to create it)."
fi

# Verify setup (quick checks)
echo
echo "🔍 Verifying setup..."

# Check if Python script exists
if [ ! -f "$REPO_DIR/sync_dropbox.py" ]; then
    echo "❌ ERROR: sync_dropbox.py not found in repo"
    exit 1
fi

# Check if venv Python works
if ! "$VENV_DIR/bin/python" --version >/dev/null 2>&1; then
    echo "❌ ERROR: Virtual environment Python not working"
    exit 1
fi

# Check if requests is available
if ! "$VENV_DIR/bin/python" -c "import requests" 2>/dev/null; then
    echo "❌ ERROR: requests library not available in venv"
    exit 1
fi

echo "✅ All components verified successfully"

# Final summary
echo
echo "🎉 === Setup Complete ==="
echo
echo "📁 Installation Summary:"
echo "   Virtual environment: $VENV_DIR"
echo "   Configuration file:  $ENV_FILE"
echo "   Run script:          $RUN_SH"
echo "   Widget shortcut:     $SHORTCUT_LINK"
echo "   Job wrapper:         $JOB_SHORTCUT_LINK"
echo
echo "📱 Next Steps:"
echo "   • Add Termux:Widget to your home screen and select 'run-sync' (if created)."
echo "   • To register job wrapper with Termux Job Scheduler, use your Termux installation's job-scheduler commands (we provided a wrapper; see instructions above)."
echo
echo "🔧 Manual Usage:"
echo "   Test run:       $RUN_SH"
echo "   Dry run:        ./.venv/bin/python ./sync_dropbox.py --dry-run"
echo "   Edit config:    nano $ENV_FILE"
echo "   View logs:      tail -f $LOG_PATH"
echo "   Uninstall:      ./remove_installation.sh"
echo
echo "📋 Troubleshooting:"
echo "   • Check logs for errors: tail -f $LOG_PATH"
echo "   • Verify storage permissions: termux-setup-storage"
echo "   • Ensure Dropbox URL is a public shared link (dl param will be normalized)"
echo "=================================="
