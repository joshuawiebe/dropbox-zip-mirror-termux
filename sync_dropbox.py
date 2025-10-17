#!/usr/bin/env python3
"""
sync_dropbox.py

Dropbox ZIP Mirror Sync Script
==============================

This script downloads a Dropbox ZIP file (public link with ?dl=1),
extracts it safely, compares files via SHA256, and syncs the contents
into a local target directory.

Main features:
--------------
- Downloads ZIP from Dropbox with dynamic progress bar (like apt)
- Extracts ZIP safely with protection against path traversal
- Compares files via SHA256 to avoid unnecessary writes
- Copies new files, updates changed files, and optionally archives old versions
- Logs every action to a log file
- Interactive setup for first run (if config is missing)
- Dry-run mode to preview changes

Typical use:
------------
- As a Termux widget shortcut, job scheduler task, or manual execution
- Config file: 
    - Local: ./.dropbox_mirror.env
    - Fallback: ~/.dropbox_mirror.env
"""

import os
import sys
import shutil
import hashlib
import zipfile
import tempfile
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import requests
import time

# ------------------ Config paths ------------------
script_dir = Path(__file__).parent
ENV_PATH = script_dir / ".dropbox_mirror.env"
if not ENV_PATH.exists():
    ENV_PATH = Path.home() / ".dropbox_mirror.env"

# ------------------ Helpers ------------------
ANSI_RE = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
C0_RE = re.compile(r'[\x00-\x1F\x7F]')  # Control characters

def strip_ansi_and_control(s: str) -> str:
    """Remove ANSI escape sequences and control characters."""
    if not isinstance(s, str):
        return s
    s2 = ANSI_RE.sub('', s)
    s2 = C0_RE.sub('', s)
    return s2.strip()

def read_env(path=ENV_PATH):
    """Read environment variables from .env config file."""
    d = {}
    if not Path(path).exists():
        return d
    try:
        with open(path, "r", encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith("#") or "=" not in ln:
                    continue
                k, v = ln.split("=", 1)
                d[k.strip()] = strip_ansi_and_control(v.strip())
    except Exception as e:
        print(f"Warning: Could not read config file {path}: {e}", flush=True)
    return d

def ask(prompt, default=None):
    """Ask user interactively (used in first-time setup)."""
    if default:
        res = input(f"{prompt} [{default}]: ").strip()
        return res if res else default
    return input(f"{prompt}: ").strip()

def timestamp(fmt="%Y-%m-%d %H:%M:%S"):
    """Return current timestamp as string."""
    return datetime.now().strftime(fmt)

def ensure_dir(p):
    """Ensure a directory exists (mkdir -p equivalent)."""
    Path(p).mkdir(parents=True, exist_ok=True)

def sha256_file(path):
    """Compute SHA256 hash of file to detect changes."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024*1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        print(f"Error hashing file {path}: {e}", flush=True)
        return None

def is_interactive():
    """Check if running interactively (not Termux widget)."""
    return sys.stdin.isatty() and os.environ.get("TERMUX_WIDGET") != "1"

def expand_path(path_str):
    """Expand ~ and environment variables in path strings."""
    return str(Path(path_str).expanduser().resolve())

def validate_url(u: str) -> bool:
    """Basic validation for HTTP/HTTPS URLs."""
    try:
        parsed = urlparse(u)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False

def print_progress_bar(current, total, prefix="", length=40, speed=None, eta=None):
    """Print apt-like progress bar dynamically in one line."""
    percent = current / total if total else 0
    filled_length = int(length * percent)
    bar = "█" * filled_length + "░" * (length - filled_length)
    extra = ""
    if speed is not None:
        extra += f" | {speed/1024:.1f} KB/s"
    if eta is not None:
        extra += f" | ETA {int(eta)}s"
    sys.stdout.write(f"\r{prefix:12} |{bar}| {percent*100:6.2f}%{extra}")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")

def safe_log_write(log_fp, text):
    """Safely write logs to file or stdout if log writing fails."""
    try:
        if log_fp:
            log_fp.write(text)
            log_fp.flush()
    except Exception:
        print("LOG-ERROR: failed to write log, printing instead:", flush=True)
        print(text, flush=True)

# ------------------ Core Functions ------------------
def download_zip(url, out_path):
    """Download ZIP with visual progress bar and ETA."""
    out_path = Path(expand_path(out_path))
    ensure_dir(out_path.parent)
    safe_url = strip_ansi_and_control(url)
    print(f"📥 Downloading ZIP from {safe_url}", flush=True)

    if not validate_url(safe_url):
        raise ValueError(f"Invalid URL: {safe_url}")

    with requests.get(safe_url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total_size = int(r.headers.get("content-length", 0))
        downloaded = 0
        start_time = time.time()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    elapsed = time.time() - start_time
                    speed = downloaded / elapsed if elapsed > 0 else 0
                    eta = (total_size - downloaded) / speed if speed > 0 else 0
                    if total_size > 0:
                        print_progress_bar(downloaded, total_size, prefix="Downloading", speed=speed, eta=eta)
    print("✅ Download complete.", flush=True)
    return out_path

def extract_zip(zip_path, dest_dir):
    """Extract ZIP safely and show progress (apt-like)."""
    dest_dir = Path(expand_path(dest_dir))
    ensure_dir(dest_dir)
    print(f"📦 Extracting ZIP: {zip_path}", flush=True)

    with zipfile.ZipFile(str(zip_path), "r") as z:
        safe_members = []
        for zi in z.infolist():
            if ".." in Path(zi.filename).parts or zi.filename.startswith("/"):
                print(f"[!] Skipping suspicious file: {zi.filename}", flush=True)
                continue
            safe_members.append(zi)
        total_files = len(safe_members)
        for idx, member in enumerate(safe_members, 1):
            z.extract(member, path=str(dest_dir))
            print_progress_bar(idx, total_files, prefix="Extracting")
    print(f"✅ Extracted {total_files} files safely.", flush=True)
    return dest_dir

def sync_from_dir(src_dir, target_dir, keep_versions=True, dry_run=False, log_fp=None):
    """Sync files with hash comparison and archive old versions."""
    src_dir = Path(expand_path(src_dir))
    target_dir = Path(expand_path(target_dir))
    versions_dir = target_dir / ".old_versions"

    if keep_versions and not dry_run:
        ensure_dir(versions_dir)

    all_files = []
    for root, _, files in os.walk(src_dir):
        for fn in files:
            all_files.append(Path(root).joinpath(fn).relative_to(src_dir))

    total_files = len(all_files)
    copied = skipped = updated = errors = 0

    for counter, rel in enumerate(all_files, 1):
        src_file = src_dir / rel
        dest_file = target_dir / rel
        try:
            ensure_dir(dest_file.parent)
            if dest_file.exists():
                new_hash = sha256_file(src_file)
                old_hash = sha256_file(dest_file)
                if new_hash and old_hash and new_hash == old_hash:
                    skipped += 1
                else:
                    if not dry_run:
                        if keep_versions:
                            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                            archive_path = versions_dir / f"{rel}.{ts}"
                            ensure_dir(archive_path.parent)
                            shutil.move(str(dest_file), str(archive_path))
                        shutil.copy2(src_file, dest_file)
                    updated += 1
            else:
                if not dry_run:
                    shutil.copy2(src_file, dest_file)
                copied += 1
        except Exception as e:
            errors += 1
            safe_log_write(log_fp, f"{timestamp()} ERROR {rel}: {e}\n")

        print_progress_bar(counter, total_files, prefix="Syncing")

    summary = {
        "total": total_files,
        "copied": copied,
        "skipped": skipped,
        "updated": updated,
        "errors": errors,
    }
    print("\n📊 Sync Summary:")
    for k, v in summary.items():
        print(f"   {k:8}: {v}")
    return summary

# ------------------ Main ------------------
def main():
    print("🟢 Starting Dropbox ZIP Mirror Sync", flush=True)
    print(f"📄 Config file: {ENV_PATH}", flush=True)

    cfg = read_env()

    # Interactive setup if config is missing
    if not cfg.get("DROPBOX_URL") and is_interactive():
        print("💡 No config found, starting interactive setup...", flush=True)
        cfg["DROPBOX_URL"] = ask("Dropbox public URL (?dl=1)")
        cfg["DOWNLOAD_PATH"] = ask("Local ZIP path", str(script_dir / "dropbox_latest.zip"))
        cfg["TARGET_DIR"] = ask("Target directory", str(script_dir / "DropboxMirror"))
        cfg["KEEP_VERSIONS"] = ask("Keep old versions? (yes/no)", "yes")
        cfg["DRY_RUN"] = ask("Dry run? (yes/no)", "no")
        cfg["LOG_PATH"] = ask("Log file path", str(script_dir / "sync.log"))
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(f"{k}={v}" for k, v in cfg.items()) + "\n")
        print(f"✅ Wrote config to {ENV_PATH}", flush=True)

    # Config defaults
    url = strip_ansi_and_control(cfg.get("DROPBOX_URL", ""))
    download_path = expand_path(cfg.get("DOWNLOAD_PATH", str(script_dir / "dropbox_latest.zip")))
    target_dir = expand_path(cfg.get("TARGET_DIR", str(script_dir / "DropboxMirror")))
    keep_versions = cfg.get("KEEP_VERSIONS", "yes").lower().startswith("y")
    dry_run = cfg.get("DRY_RUN", "no").lower() in ("1", "true", "yes", "y")
    log_path = expand_path(cfg.get("LOG_PATH", str(script_dir / "sync.log")))

    if "--dry-run" in sys.argv:
        dry_run = True
        print("⚡ Dry-run mode enabled via CLI flag", flush=True)

    if not url or "dropbox.com" not in url:
        print("[!] ERROR: Missing or invalid DROPBOX_URL", flush=True)
        return 1

    # Normalize URL
    url = re.sub(r'(\?|&)+dl=[01]', '', url).rstrip("&?") + ("&dl=1" if "?" in url else "?dl=1")

    ensure_dir(target_dir)
    ensure_dir(Path(log_path).parent)

    print(f"🌐 URL: {url}", flush=True)
    print(f"📂 Target: {target_dir}", flush=True)
    print(f"💭 Dry run: {dry_run}", flush=True)

    # ----------------- Core workflow -----------------
    try:
        with open(log_path, "a", encoding="utf-8") as log_fp:
            safe_log_write(log_fp, f"{timestamp()} === RUN START ===\n")

            # Step 1: Download ZIP
            zip_path = download_zip(url, download_path)
            safe_log_write(log_fp, f"{timestamp()} Downloaded: {zip_path}\n")

            # Step 2: Extract ZIP
            tmpdir = Path(tempfile.mkdtemp(prefix="dbx_sync_"))
            extract_zip(zip_path, tmpdir)
            safe_log_write(log_fp, f"{timestamp()} Extracted to: {tmpdir}\n")

            # Step 3: Sync files
            summary = sync_from_dir(tmpdir, target_dir, keep_versions, dry_run, log_fp)
            safe_log_write(log_fp, f"{timestamp()} SYNC SUMMARY: {summary}\n")

            # Step 4: Cleanup
            if Path(zip_path).exists():
                Path(zip_path).unlink()
            shutil.rmtree(tmpdir)
            safe_log_write(log_fp, f"{timestamp()} Cleanup complete\n")
            safe_log_write(log_fp, f"{timestamp()} === RUN END ===\n")

    except Exception as e:
        print(f"[!] ERROR: {e}", flush=True)
        return 2

    print("🎉 Dropbox Mirror Sync finished successfully!", flush=True)
    return 0

# ------------------ Entry point ------------------
if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.", flush=True)
        sys.exit(130)
    except Exception as e:
        print(f"[!] Fatal error: {e}", flush=True)
        sys.exit(1)
